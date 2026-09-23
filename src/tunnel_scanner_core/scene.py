from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Any, Iterable, Mapping

from .deformed_mesh import DeformedRingMesh
from .ancillary import AncillarySet
from .bolts import BoltSet, build_pocket_boolean_cutter
from .curved_mesh import (
    SurfaceMeshingConfig,
    apply_rigid_transform_to_curved_segment,
    build_curved_circumferential_collar_mesh,
    build_curved_ring_mesh,
    sagitta_m,
)
from .joints import PrescribedJointSet
from .mesh import Face, RingMesh, Vec3


class SceneMode(str, Enum):
    """Physically coherent Stage-5 scene variants.

    NOMINAL_WITH_PRESCRIBED_JOINTS:
        Undeformed Stage-1 segments plus Stage-4 prescribed joints.

    DEFORMED_WITH_DISPLACEMENT_JOINTS:
        Stage-3 rigidly deformed segments plus displacement-induced gap meshes.

    The two modes are deliberately separate. Stage 4 did not yet derive how the
    prescribed nominal outer-rib joints themselves deform, so combining both
    representations into one physical scene would silently mix incompatible
    geometry frames.
    """

    NOMINAL_WITH_PRESCRIBED_JOINTS = "nominal_with_prescribed_joints"
    DEFORMED_WITH_DISPLACEMENT_JOINTS = "deformed_with_displacement_joints"
    MULTI_RING_TUNNEL = "multi_ring_tunnel"


class LabelPolicy(str, Enum):
    """Semantic ID policy written to Blender's `labelID` custom property."""

    SEG2TUNNEL_LIKE = "seg2tunnel_like"
    STSD_COARSE = "stsd_coarse"


@dataclass(frozen=True)
class SceneObject:
    """Engine-neutral mesh object with sensor/semantic metadata."""

    name: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    object_type: str
    ring_id: int
    label_id: int
    instance_id: int
    semantic_class: str
    segment_id: int | None = None
    segment_name: str | None = None
    segment_kind: str | None = None
    reconstruction: str | None = None
    collection_path: tuple[str, ...] = ()
    extra_properties: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("scene object name must not be empty")
        if self.ring_id < 0:
            raise ValueError("ring_id must be non-negative")
        if self.instance_id < 0:
            raise ValueError("instance_id must be non-negative")
        if not self.vertices:
            raise ValueError(f"{self.name}: mesh must have vertices")
        if not self.faces:
            raise ValueError(f"{self.name}: mesh must have faces")
        n = len(self.vertices)
        for face in self.faces:
            if len(face) < 3:
                raise ValueError(f"{self.name}: face must have >=3 vertices")
            if min(face) < 0 or max(face) >= n:
                raise ValueError(f"{self.name}: face index outside vertex range")

    @property
    def custom_properties(self) -> dict[str, Any]:
        props: dict[str, Any] = {
            "labelID": int(self.label_id),
            "ringID": int(self.ring_id),
            "instanceID": int(self.instance_id),
            "objectType": self.object_type,
            "semanticClass": self.semantic_class,
        }
        if self.segment_id is not None:
            props["segmentID"] = int(self.segment_id)
        if self.segment_name is not None:
            props["segmentName"] = self.segment_name
        if self.segment_kind is not None:
            props["segmentKind"] = self.segment_kind
        if self.reconstruction is not None:
            props["reconstruction"] = self.reconstruction
        for key, value in self.extra_properties.items():
            if key in props and props[key] != value:
                raise ValueError(f"extra property {key!r} conflicts with canonical metadata")
            props[key] = value
        return props



def _mesh_prototype_transform_matrix(
    scene_object: SceneObject,
) -> tuple[float, ...] | None:
    """Return a row-major local-to-world rigid transform for a prototype."""
    props = scene_object.extra_properties
    if props.get("meshPrototypeKey") is None:
        return None
    mode = props.get("meshPrototypeMode")
    if mode == "translation_only_shared_mesh_v1":
        raw_translation = props.get("meshPrototypeTranslationM")
        if (
            not isinstance(raw_translation, (list, tuple))
            or len(raw_translation) != 3
        ):
            raise ValueError(
                f"{scene_object.name}: meshPrototypeTranslationM must contain 3 values"
            )
        tx, ty, tz = (float(value) for value in raw_translation)
        matrix = (
            1.0, 0.0, 0.0, tx,
            0.0, 1.0, 0.0, ty,
            0.0, 0.0, 1.0, tz,
            0.0, 0.0, 0.0, 1.0,
        )
    elif mode == "rigid_transform_shared_mesh_v2":
        raw_matrix = props.get("meshPrototypeTransformMatrix4x4")
        if (
            not isinstance(raw_matrix, (list, tuple))
            or len(raw_matrix) != 16
        ):
            raise ValueError(
                f"{scene_object.name}: meshPrototypeTransformMatrix4x4 "
                "must contain 16 row-major values"
            )
        matrix = tuple(float(value) for value in raw_matrix)
    else:
        raise ValueError(
            f"{scene_object.name}: unsupported meshPrototypeMode {mode!r}"
        )

    if not all(math.isfinite(value) for value in matrix):
        raise ValueError(f"{scene_object.name}: non-finite mesh prototype transform")
    if any(
        abs(actual - expected) > 1e-10
        for actual, expected in zip(matrix[12:16], (0.0, 0.0, 0.0, 1.0))
    ):
        raise ValueError(f"{scene_object.name}: prototype transform is not affine")

    axes = (
        (matrix[0], matrix[4], matrix[8]),
        (matrix[1], matrix[5], matrix[9]),
        (matrix[2], matrix[6], matrix[10]),
    )
    for axis in axes:
        if abs(sum(value * value for value in axis) - 1.0) > 1e-8:
            raise ValueError(
                f"{scene_object.name}: prototype transform rotation is not unit"
            )
    for i in range(3):
        for j in range(i + 1, 3):
            if abs(sum(axes[i][k] * axes[j][k] for k in range(3))) > 1e-8:
                raise ValueError(
                    f"{scene_object.name}: prototype transform rotation is not orthogonal"
                )

    if bool(props.get("coordinatesLocalizedToChunk", False)):
        values = list(matrix)
        values[3] -= float(props.get("chunkWorldOriginX", 0.0))
        values[7] -= float(props.get("chunkWorldOriginY", 0.0))
        values[11] -= float(props.get("chunkWorldOriginZ", 0.0))
        matrix = tuple(values)
    return matrix


def _inverse_rigid_transform_point(
    matrix: tuple[float, ...],
    point: tuple[float, float, float],
) -> tuple[float, float, float]:
    dx = float(point[0]) - matrix[3]
    dy = float(point[1]) - matrix[7]
    dz = float(point[2]) - matrix[11]
    return (
        matrix[0] * dx + matrix[4] * dy + matrix[8] * dz,
        matrix[1] * dx + matrix[5] * dy + matrix[9] * dz,
        matrix[2] * dx + matrix[6] * dy + matrix[10] * dz,
    )


def scene_object_mesh_prototype_payload(
    scene_object: SceneObject,
) -> tuple[
    str,
    tuple[float, ...],
    tuple[tuple[float, float, float], ...],
] | None:
    """Recover a declared exact shared mesh plus its rigid instance transform."""
    props = scene_object.extra_properties
    key = props.get("meshPrototypeKey")
    if key is None:
        return None
    matrix = _mesh_prototype_transform_matrix(scene_object)
    if matrix is None:
        return None

    expected_vertices = int(
        props.get("meshPrototypeVertexCount", len(scene_object.vertices))
    )
    expected_faces = int(
        props.get("meshPrototypeFaceCount", len(scene_object.faces))
    )
    if expected_vertices != len(scene_object.vertices):
        raise ValueError(
            f"{scene_object.name}: mesh prototype vertex-count mismatch"
        )
    if expected_faces != len(scene_object.faces):
        raise ValueError(
            f"{scene_object.name}: mesh prototype face-count mismatch"
        )

    local_vertices = tuple(
        _inverse_rigid_transform_point(matrix, vertex)
        for vertex in scene_object.vertices
    )
    return str(key), matrix, local_vertices


@dataclass(frozen=True)
class ScenePackage:
    """Serializable engine-neutral scene boundary for Blender/other back ends."""

    name: str
    mode: SceneMode
    label_policy: LabelPolicy
    objects: tuple[SceneObject, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
    _objects_by_type: Mapping[str, tuple[SceneObject, ...]] = field(
        init=False,
        repr=False,
        compare=False,
        default_factory=dict,
    )
    _ring_ids: tuple[int, ...] = field(
        init=False,
        repr=False,
        compare=False,
        default=(),
    )

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("scene package name must not be empty")

        # Build all structural indexes during the same validation pass. Large
        # Stage-10 scenes query objects_of_type() dozens of times during
        # validation/reporting, so repeatedly scanning hundreds of thousands
        # of objects is avoidable post-build work.
        names: set[str] = set()
        ids: set[int] = set()
        ring_ids: set[int] = set()
        by_type: dict[str, list[SceneObject]] = {}
        for obj in self.objects:
            if obj.name in names:
                raise ValueError("scene object names must be unique")
            names.add(obj.name)
            if obj.instance_id in ids:
                raise ValueError("scene instance IDs must be unique")
            ids.add(obj.instance_id)
            ring_ids.add(obj.ring_id)
            by_type.setdefault(obj.object_type, []).append(obj)

        object.__setattr__(
            self,
            "_objects_by_type",
            {
                object_type: tuple(objects)
                for object_type, objects in by_type.items()
            },
        )
        object.__setattr__(self, "_ring_ids", tuple(sorted(ring_ids)))

    @property
    def ring_ids(self) -> tuple[int, ...]:
        return self._ring_ids

    def objects_of_type(self, object_type: str) -> tuple[SceneObject, ...]:
        return self._objects_by_type.get(object_type, ())

    def custom_property_keys(self) -> tuple[str, ...]:
        keys: set[str] = set()
        for obj in self.objects:
            keys.update(obj.custom_properties)
        return tuple(sorted(keys))


def _segment_label_map(ring: RingMesh, label_policy: LabelPolicy) -> dict[str, int]:
    if label_policy is LabelPolicy.SEG2TUNNEL_LIKE:
        if len(ring.segments) != 6:
            raise ValueError("SEG2TUNNEL_LIKE currently requires exactly six segments")
        return {segment.name: i + 1 for i, segment in enumerate(ring.segments)}
    if label_policy is LabelPolicy.STSD_COARSE:
        return {segment.name: 1 for segment in ring.segments}
    raise NotImplementedError(label_policy)


def _segment_semantic_class(label_policy: LabelPolicy, label_id: int) -> str:
    if label_policy is LabelPolicy.STSD_COARSE:
        return "segments"
    return f"lining_segment_{label_id}"


def _ancillary_semantics(
    label_policy: LabelPolicy, category: str
) -> tuple[int, str]:
    if label_policy is LabelPolicy.SEG2TUNNEL_LIKE:
        return 0, "clutter"
    if label_policy is LabelPolicy.STSD_COARSE:
        if category == "walkway":
            return 2, "walkway"
        if category == "tube":
            return 3, "tubes"
        return 0, "clutter"
    raise NotImplementedError(label_policy)


def _instance_id(ring_id: int, local_index: int) -> int:
    if local_index >= 1000:
        raise ValueError("local object index exceeds Stage-5 instance-ID namespace")
    return ring_id * 1000 + local_index


def build_nominal_scene_package(
    ring: RingMesh,
    joints: PrescribedJointSet,
    *,
    ring_id: int = 0,
    include_radial_joints: bool = True,
    include_circumferential_front: bool = False,
    include_circumferential_back: bool = True,
    label_policy: LabelPolicy = LabelPolicy.SEG2TUNNEL_LIKE,
    surface_meshing: SurfaceMeshingConfig | None = None,
    bolts: BoltSet | None = None,
    bolt_boolean_overlap_m: float = 0.005,
    visible_bolt_heads_only: bool = False,
    ancillary: AncillarySet | None = None,
) -> ScenePackage:
    if ring_id < 0:
        raise ValueError("ring_id must be non-negative")
    label_map = _segment_label_map(ring, label_policy)
    segment_id_map = {segment.name: i for i, segment in enumerate(ring.segments)}
    surface_meshing = surface_meshing or SurfaceMeshingConfig()
    curved_ring = build_curved_ring_mesh(ring, meshing=surface_meshing)
    curved_by_name = {segment.name: segment for segment in curved_ring.segments}
    objects: list[SceneObject] = []
    local_index = 0

    for segment in ring.segments:
        seg_id = segment_id_map[segment.name]
        surface = curved_by_name[segment.name]
        objects.append(
            SceneObject(
                name=f"R{ring_id:04d}_SEG_{seg_id:02d}_{segment.name}",
                vertices=surface.vertices,
                faces=surface.faces,
                object_type="lining_segment",
                ring_id=ring_id,
                label_id=label_map[segment.name],
                instance_id=_instance_id(ring_id, local_index),
                semantic_class=_segment_semantic_class(label_policy, label_map[segment.name]),
                segment_id=seg_id,
                segment_name=segment.name,
                segment_kind=segment.kind,
                reconstruction="stage5_1_adaptive_cylindrical_surface",
                collection_path=(f"Ring_{ring_id:04d}", "Segments"),
                extra_properties={
                    "analyticalSource": "stage1_hexahedral_segment",
                    "surfaceToleranceM": float(surface.requested_max_sagitta_m),
                    "surfaceAchievedMaxSagittaM": float(surface.achieved_max_sagitta_m),
                    "surfaceSubdivisions": int(surface.circumferential_subdivisions),
                    "surfaceLongitudinalSubdivisions": int(surface.longitudinal_subdivisions),
                    "segmentFrontStartDeg": float(surface.angular_extent.front_start_deg),
                    "segmentFrontEndDeg": float(surface.angular_extent.front_end_deg),
                    "segmentBackStartDeg": float(surface.angular_extent.back_start_deg),
                    "segmentBackEndDeg": float(surface.angular_extent.back_end_deg),
                },
            )
        )
        local_index += 1

    if include_radial_joints:
        for i, joint in enumerate(joints.radial):
            next_seg_id = segment_id_map[joint.next_segment]
            objects.append(
                SceneObject(
                    name=f"R{ring_id:04d}_JRAD_{i:02d}_{joint.previous_segment}_{joint.next_segment}",
                    vertices=joint.vertices,
                    faces=joint.faces,
                    object_type="prescribed_radial_joint",
                    ring_id=ring_id,
                    label_id=0,
                    instance_id=_instance_id(ring_id, local_index),
                    semantic_class="clutter",
                    segment_id=next_seg_id,
                    segment_name=joint.next_segment,
                    reconstruction=joint.reconstruction.value,
                    collection_path=(f"Ring_{ring_id:04d}", "Joints", "PrescribedRadial"),
                    extra_properties={
                        "previousSegment": joint.previous_segment,
                        "nextSegment": joint.next_segment,
                        "jointWidthM": float(joint.width_m),
                        "jointAddedThicknessM": float(joint.added_thickness_m),
                    },
                )
            )
            local_index += 1

    def append_circ(pieces: Iterable[Any], side: str) -> None:
        nonlocal local_index
        for i, joint in enumerate(pieces):
            seg_id = segment_id_map[joint.segment_name]
            collar_surface = build_curved_circumferential_collar_mesh(
                joint, meshing=surface_meshing
            )
            objects.append(
                SceneObject(
                    name=f"R{ring_id:04d}_JCIRC_{side.upper()}_{i:02d}_{joint.segment_name}",
                    vertices=collar_surface.vertices,
                    faces=collar_surface.faces,
                    object_type="prescribed_circumferential_joint",
                    ring_id=ring_id,
                    label_id=0,
                    instance_id=_instance_id(ring_id, local_index),
                    semantic_class="clutter",
                    segment_id=seg_id,
                    segment_name=joint.segment_name,
                    reconstruction=f"{joint.reconstruction.value}+stage5_1_curved_surface",
                    collection_path=(f"Ring_{ring_id:04d}", "Joints", f"Circumferential_{side}"),
                    extra_properties={
                        "jointSide": side,
                        "jointWidthM": float(joint.width_m),
                        "jointAddedThicknessM": float(joint.added_thickness_m),
                        "surfaceToleranceM": float(collar_surface.requested_max_sagitta_m),
                        "surfaceAchievedMaxSagittaM": float(collar_surface.achieved_max_sagitta_m),
                        "surfaceSubdivisions": int(collar_surface.circumferential_subdivisions),
                    },
                )
            )
            local_index += 1

    if include_circumferential_front:
        append_circ(joints.circumferential_front, "front")
    if include_circumferential_back:
        append_circ(joints.circumferential_back, "back")

    if bolts is not None:
        for assembly in bolts.assemblies:
            placement = assembly.placement
            if placement.segment_name not in segment_id_map:
                raise ValueError(f"bolt references unknown segment {placement.segment_name}")
            seg_id = segment_id_map[placement.segment_name]
            target_name = f"R{ring_id:04d}_SEG_{seg_id:02d}_{placement.segment_name}"
            bolt_index = placement.index
            cutter = build_pocket_boolean_cutter(
                assembly.pocket, overlap_m=bolt_boolean_overlap_m
            )
            objects.append(
                SceneObject(
                    name=f"R{ring_id:04d}_BCUT_{bolt_index:03d}_{placement.segment_name}",
                    vertices=cutter.vertices,
                    faces=cutter.faces,
                    object_type="bolt_pocket_cutter",
                    ring_id=ring_id,
                    label_id=0,
                    instance_id=_instance_id(ring_id, local_index),
                    semantic_class="clutter",
                    segment_id=seg_id,
                    segment_name=placement.segment_name,
                    reconstruction=cutter.reconstruction,
                    collection_path=(f"Ring_{ring_id:04d}", "Bolts", "Cutters"),
                    extra_properties={
                        "boltIndex": int(bolt_index),
                        "boltLayout": placement.layout.value,
                        "boltAlphaDeg": float(placement.alpha_deg),
                        "boltYM": float(placement.y_m),
                        "booleanTarget": target_name,
                        "booleanOperation": "DIFFERENCE",
                        "booleanEntryOverlapM": float(cutter.overlap_m),
                        "removeAfterBoolean": True,
                        "visibleHeadOnlyMode": bool(visible_bolt_heads_only),
                        "booleanParticipation": True,
                        "cutterPurpose": "visible_bolt_pocket_recess",
                    },
                )
            )
            local_index += 1

            head = assembly.head
            head_faces = (
                (head.faces[0], *head.faces[2:])
                if visible_bolt_heads_only
                else head.faces
            )
            objects.append(
                SceneObject(
                    name=f"R{ring_id:04d}_BHEAD_{bolt_index:03d}_{placement.segment_name}",
                    vertices=head.vertices,
                    faces=head_faces,
                    object_type="bolt_head",
                    ring_id=ring_id,
                    label_id=0,
                    instance_id=_instance_id(ring_id, local_index),
                    semantic_class="clutter",
                    segment_id=seg_id,
                    segment_name=placement.segment_name,
                    reconstruction=head.reconstruction,
                    collection_path=(f"Ring_{ring_id:04d}", "Bolts", "Heads"),
                    extra_properties={
                        "boltIndex": int(bolt_index),
                        "boltLayout": placement.layout.value,
                        "boltAlphaDeg": float(placement.alpha_deg),
                        "boltYM": float(placement.y_m),
                        **(
                            {
                                "booleanTarget": target_name,
                                "booleanOperation": "DIFFERENCE",
                                "cutTargetBeforeDisplay": True,
                                "visibleHeadOnlyMode": False,
                            }
                            if not visible_bolt_heads_only
                            else {
                                "cutTargetBeforeDisplay": False,
                                "visibleHeadOnlyMode": True,
                                "hiddenBoltBodyOmitted": True,
                                "boltPocketRecessOmitted": False,
                                "boltPocketCutterPresent": True,
                                "hiddenEmbeddedHeadBottomCapOmitted": True,
                                "booleanParticipation": False,
                            }
                        ),
                        "boltHeadRadiusM": float(head.top_radius_m),
                        "boltEmbeddedRadiusM": float(head.bottom_radius_m),
                        "boltHeadThicknessM": float(head.thickness_m),
                        "boltHeadRingVertices": int(bolts.config.head_ring_vertices),
                        "boltHeadSurfaceToleranceM": float(
                            surface_meshing.max_sagitta_m
                        ),
                        "boltHeadAchievedMaxSagittaM": float(
                            sagitta_m(
                                head.top_radius_m,
                                360.0 / bolts.config.head_ring_vertices,
                            )
                        ),
                        "boltHeadTessellationMode": (
                            "sagitta_bounded_adaptive_v1"
                        ),
                    },
                )
            )
            local_index += 1

    if ancillary is not None:
        if not math.isclose(
            ancillary.inner_radius_m,
            ring.config.inner_radius_m,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("ancillary inner radius does not match ring inner radius")
        if not math.isclose(
            ancillary.length_m,
            ring.config.width_m,
            rel_tol=0.0,
            abs_tol=1e-12,
        ):
            raise ValueError("ancillary extrusion length does not match ring width")
        for mesh in ancillary.meshes:
            label_id, semantic_class = _ancillary_semantics(
                label_policy, mesh.category
            )
            object_type = f"ancillary_{mesh.category}"
            objects.append(
                SceneObject(
                    name=f"R{ring_id:04d}_ANC_{mesh.name.upper()}",
                    vertices=mesh.vertices,
                    faces=mesh.faces,
                    object_type=object_type,
                    ring_id=ring_id,
                    label_id=label_id,
                    instance_id=_instance_id(ring_id, local_index),
                    semantic_class=semantic_class,
                    reconstruction="stage8_table4_extruded_cross_section",
                    collection_path=(
                        f"Ring_{ring_id:04d}",
                        "Ancillary",
                        mesh.category.capitalize(),
                    ),
                    extra_properties={
                        "ancillaryCategory": mesh.category,
                        "ancillaryTransformPolicy": ancillary.config.transform_policy.value,
                        "followRingAxialRotation": (
                            ancillary.config.reconstruction_metadata["followRingAxialRotation"]
                        ),
                        "followSceneAlignment": (
                            ancillary.config.reconstruction_metadata["followSceneAlignment"]
                        ),
                        **mesh.properties,
                    },
                )
            )
            local_index += 1

    mapping = {name: label for name, label in label_map.items()}
    return ScenePackage(
        name=f"tunnel_scanner_nominal_ring_{ring_id:04d}",
        mode=SceneMode.NOMINAL_WITH_PRESCRIBED_JOINTS,
        label_policy=label_policy,
        objects=tuple(objects),
        metadata={
            "sourceStages": [1, 4, 5] + ([8] if ancillary is not None else []),
            "coordinateConvention": {
                "longitudinalAxis": "+Y",
                "crossSection": "XZ",
                "alphaZero": "+Z crown",
                "units": "metres",
            },
            "segmentLabelConvention": mapping,
            "segmentLabelConventionStatus": (
                (
                    "Stage-5 generator order; article states labels 1..6 but does not "
                    "publish K/B/A-to-S1..S6 correspondence"
                )
                if label_policy is LabelPolicy.SEG2TUNNEL_LIKE
                else "STSD-coarse: all lining segments merged into class 1"
            ),
            "jointLabelConvention": "labelID=0 clutter",
            "ancillaryLabelConvention": (
                "Seg2Tunnel-like: all ancillary objects are class 0 clutter"
                if label_policy is LabelPolicy.SEG2TUNNEL_LIKE
                else "STSD-coarse reclassification: clutter=0, segments=1, walkway=2, tubes=3; pavement/rails remain clutter"
            ),
            "ancillaryGeometry": (
                None
                if ancillary is None
                else {
                    "stage": 8,
                    "meshCount": len(ancillary.meshes),
                    "pavement": len(ancillary.meshes_of_category("pavement")),
                    "walkway": len(ancillary.meshes_of_category("walkway")),
                    "rails": len(ancillary.meshes_of_category("rail")),
                    "tubes": len(ancillary.meshes_of_category("tube")),
                    "transformPolicy": ancillary.config.transform_policy.value,
                    "followRingAxialRotation": ancillary.config.reconstruction_metadata["followRingAxialRotation"],
                    "followSceneAlignment": ancillary.config.reconstruction_metadata["followSceneAlignment"],
                    "reconstruction": ancillary.config.reconstruction_metadata,
                }
            ),
            "surfaceMeshing": {
                "stage": "5.1",
                "representation": "adaptive cylindrical chord tessellation",
                "maxSagittaM": float(surface_meshing.max_sagitta_m),
                "minSubdivisions": int(surface_meshing.min_subdivisions),
                "maxSubdivisions": int(surface_meshing.max_subdivisions),
            },
            "boltBooleanPipeline": (
                None
                if bolts is None
                else {
                    "stage": "6",
                    "layout": bolts.layout.value,
                    "pocketMode": bolts.pocket_mode.value,
                    "assemblies": len(bolts.assemblies),
                    "entryOverlapM": float(bolt_boolean_overlap_m),
                    "headHeightRatio": float(bolts.config.head_height_ratio),
                    "headHeightRatioStatus": "engineering assumption; paper defines eta but publishes no value",
                    "perturbationSigmaM": float(bolts.perturbation_config.sigma_m),
                    "perturbationSigmaFraction": float(bolts.perturbation_config.sigma_fraction),
                    "perturbationStatus": (
                        "engineering interpretation of ambiguous printed N(0,0.001 m^2): "
                        "sigma=1 mm, truncated at configured sigma bound"
                    ),
                    "operations": [
                        "segment DIFFERENCE pocket_cutter",
                        "segment DIFFERENCE bolt_head",
                        "remove pocket_cutter",
                        "retain bolt_head as labelID=0 clutter",
                    ],
                    "semanticLimitation": (
                        "cavity wall remains part of lining segment label; the paper's "
                        "separate pocket-shell clutter reconstruction is deferred"
                    ),
                }
            ),
            "physicalCoherence": (
                "Stage-1 analytical segments rendered as Stage-5.1 curved surfaces + "
                "Stage-4 prescribed joints"
                + (
                    "; Stage-6 physical bolt cavity/head Boolean tools"
                    if bolts is not None
                    else ""
                )
                + ("; Stage-8 ancillary structures" if ancillary is not None else "")
                + "; no Stage-3 deformation"
            ),
        },
    )


def build_deformed_scene_package(
    deformed: DeformedRingMesh,
    *,
    ring_id: int = 0,
    include_displacement_joints: bool = True,
    label_policy: LabelPolicy = LabelPolicy.SEG2TUNNEL_LIKE,
    surface_meshing: SurfaceMeshingConfig | None = None,
) -> ScenePackage:
    if ring_id < 0:
        raise ValueError("ring_id must be non-negative")
    base_ring = deformed.base_ring
    label_map = _segment_label_map(base_ring, label_policy)
    segment_id_map = {segment.name: i for i, segment in enumerate(base_ring.segments)}
    transform_map = {t.segment_name: t for t in deformed.segment_transforms}
    surface_meshing = surface_meshing or SurfaceMeshingConfig()
    curved_base = build_curved_ring_mesh(base_ring, meshing=surface_meshing)
    curved_base_by_name = {segment.name: segment for segment in curved_base.segments}
    objects: list[SceneObject] = []
    local_index = 0

    for segment in deformed.segments:
        seg_id = segment_id_map[segment.name]
        transform = transform_map[segment.name]
        surface = apply_rigid_transform_to_curved_segment(
            curved_base_by_name[segment.name], transform
        )
        objects.append(
            SceneObject(
                name=f"R{ring_id:04d}_SEG_{seg_id:02d}_{segment.name}",
                vertices=surface.vertices,
                faces=surface.faces,
                object_type="lining_segment",
                ring_id=ring_id,
                label_id=label_map[segment.name],
                instance_id=_instance_id(ring_id, local_index),
                semantic_class=_segment_semantic_class(label_policy, label_map[segment.name]),
                segment_id=seg_id,
                segment_name=segment.name,
                segment_kind=segment.kind,
                reconstruction="stage5_1_curved_surface_plus_stage3_rigid_transform",
                collection_path=(f"Ring_{ring_id:04d}", "Segments"),
                extra_properties={
                    "analyticalSource": "stage1_hexahedral_segment",
                    "rotationDeg": float(transform.rotation_deg),
                    "centerOffsetX": float(transform.center_offset_xz_m[0]),
                    "centerOffsetZ": float(transform.center_offset_xz_m[1]),
                    "surfaceToleranceM": float(surface.requested_max_sagitta_m),
                    "surfaceAchievedMaxSagittaM": float(surface.achieved_max_sagitta_m),
                    "surfaceSubdivisions": int(surface.circumferential_subdivisions),
                    "surfaceLongitudinalSubdivisions": int(surface.longitudinal_subdivisions),
                },
            )
        )
        local_index += 1

    if include_displacement_joints:
        for i, joint in enumerate(deformed.displacement_joints):
            next_seg_id = segment_id_map[joint.next_segment]
            objects.append(
                SceneObject(
                    name=f"R{ring_id:04d}_JDISP_{i:02d}_{joint.previous_segment}_{joint.next_segment}",
                    vertices=joint.vertices,
                    faces=joint.faces,
                    object_type="displacement_joint",
                    ring_id=ring_id,
                    label_id=0,
                    instance_id=_instance_id(ring_id, local_index),
                    semantic_class="clutter",
                    segment_id=next_seg_id,
                    segment_name=joint.next_segment,
                    reconstruction="stage3_displacement_gap_mesh",
                    collection_path=(f"Ring_{ring_id:04d}", "Joints", "Displacement"),
                    extra_properties={
                        "previousSegment": joint.previous_segment,
                        "nextSegment": joint.next_segment,
                        "dislocationM": float(joint.dislocation_m),
                        "relativeRotationDeg": float(joint.relative_rotation_deg),
                        "maxCornerSeparationM": float(joint.max_corner_separation_m),
                    },
                )
            )
            local_index += 1

    return ScenePackage(
        name=f"tunnel_scanner_deformed_ring_{ring_id:04d}",
        mode=SceneMode.DEFORMED_WITH_DISPLACEMENT_JOINTS,
        label_policy=label_policy,
        objects=tuple(objects),
        metadata={
            "sourceStages": [1, 2, 3, 5],
            "coordinateConvention": {
                "longitudinalAxis": "+Y",
                "crossSection": "XZ",
                "alphaZero": "+Z crown",
                "units": "metres",
            },
            "segmentLabelConvention": {name: label for name, label in label_map.items()},
            "segmentLabelConventionStatus": (
                "Stage-5 generator order; article states labels 1..6 but does not "
                "publish K/B/A-to-S1..S6 correspondence"
            ),
            "jointLabelConvention": "labelID=0 clutter, following Seg2Tunnel synthesis described by Yang et al. (2026)",
            "surfaceMeshing": {
                "stage": "5.1",
                "representation": "adaptive cylindrical chord tessellation",
                "maxSagittaM": float(surface_meshing.max_sagitta_m),
                "minSubdivisions": int(surface_meshing.min_subdivisions),
                "maxSubdivisions": int(surface_meshing.max_subdivisions),
            },
            "physicalCoherence": (
                "Stage-1 analytical segments rendered as Stage-5.1 curved surfaces, "
                "then transformed by Stage-3 rigid kinematics + Stage-3 displacement "
                "gap meshes; nominal prescribed joints intentionally excluded"
            ),
            "kinematicIndexing": deformed.deformation.indexing.value,
            "closureTranslationErrorM": float(deformed.deformation.translation_closure_error_m),
            "closureAngularErrorDeg": float(deformed.deformation.angular_closure_error_deg),
        },
    )
