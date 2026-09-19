from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Mapping

from .deformed_mesh import DeformedRingMesh
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


class LabelPolicy(str, Enum):
    """Semantic ID policy written to Blender's `labelID` custom property.

    SEG2TUNNEL_LIKE reproduces the labeling strategy described in Yang et al.
    (2026): background/clutter is 0 and the six lining segment classes are 1..6.
    The paper does not publish a K/B/A -> S1..S6 lookup, so Stage 5 assigns 1..6
    in the generator's canonical physical order and records that convention in
    package metadata. Joints are class 0, matching the paper's statement that
    joints and bolts are merged into clutter for Seg2Tunnel synthesis.
    """

    SEG2TUNNEL_LIKE = "seg2tunnel_like"


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
        """Blender-safe object custom properties used by Stage 5.

        The two names explicitly used by Tunnel Scanner/BlAInder (`labelID` and
        `ringID`) are kept verbatim. The additional properties are ours and are
        intentionally descriptive rather than benchmark-specific.
        """
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


@dataclass(frozen=True)
class ScenePackage:
    """Serializable engine-neutral scene boundary for Blender/other back ends."""

    name: str
    mode: SceneMode
    label_policy: LabelPolicy
    objects: tuple[SceneObject, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("scene package name must not be empty")
        names = [o.name for o in self.objects]
        if len(names) != len(set(names)):
            raise ValueError("scene object names must be unique")
        ids = [o.instance_id for o in self.objects]
        if len(ids) != len(set(ids)):
            raise ValueError("scene instance IDs must be unique")

    @property
    def ring_ids(self) -> tuple[int, ...]:
        return tuple(sorted({o.ring_id for o in self.objects}))

    def objects_of_type(self, object_type: str) -> tuple[SceneObject, ...]:
        return tuple(o for o in self.objects if o.object_type == object_type)

    def custom_property_keys(self) -> tuple[str, ...]:
        keys: set[str] = set()
        for obj in self.objects:
            keys.update(obj.custom_properties)
        return tuple(sorted(keys))


def _segment_label_map(ring: RingMesh) -> dict[str, int]:
    """Assign six fine labels in canonical generator order.

    Yang et al. state that Seg2Tunnel uses classes 1..6 for lining segments but
    do not publish the correspondence between those dataset class numbers and
    the K/B/A names used in their procedural geometry section. Stage 5 therefore
    records and exposes its convention instead of pretending it is author code.
    """
    if len(ring.segments) != 6:
        raise ValueError("SEG2TUNNEL_LIKE currently requires exactly six segments")
    return {segment.name: i + 1 for i, segment in enumerate(ring.segments)}


def _instance_id(ring_id: int, local_index: int) -> int:
    # Stable across independent ring builds while leaving room for future object
    # categories. 1000 objects/ring is ample for the current staged prototype.
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
) -> ScenePackage:
    if ring_id < 0:
        raise ValueError("ring_id must be non-negative")
    if label_policy is not LabelPolicy.SEG2TUNNEL_LIKE:
        raise NotImplementedError(label_policy)

    label_map = _segment_label_map(ring)
    segment_id_map = {segment.name: i for i, segment in enumerate(ring.segments)}
    objects: list[SceneObject] = []
    local_index = 0

    for segment in ring.segments:
        seg_id = segment_id_map[segment.name]
        objects.append(
            SceneObject(
                name=f"R{ring_id:04d}_SEG_{seg_id:02d}_{segment.name}",
                vertices=segment.vertices,
                faces=segment.faces,
                object_type="lining_segment",
                ring_id=ring_id,
                label_id=label_map[segment.name],
                instance_id=_instance_id(ring_id, local_index),
                semantic_class=f"lining_segment_{label_map[segment.name]}",
                segment_id=seg_id,
                segment_name=segment.name,
                segment_kind=segment.kind,
                reconstruction="stage1_hexahedral_segment",
                collection_path=(f"Ring_{ring_id:04d}", "Segments"),
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
            objects.append(
                SceneObject(
                    name=f"R{ring_id:04d}_JCIRC_{side.upper()}_{i:02d}_{joint.segment_name}",
                    vertices=joint.vertices,
                    faces=joint.faces,
                    object_type="prescribed_circumferential_joint",
                    ring_id=ring_id,
                    label_id=0,
                    instance_id=_instance_id(ring_id, local_index),
                    semantic_class="clutter",
                    segment_id=seg_id,
                    segment_name=joint.segment_name,
                    reconstruction=joint.reconstruction.value,
                    collection_path=(f"Ring_{ring_id:04d}", "Joints", f"Circumferential_{side}"),
                    extra_properties={
                        "jointSide": side,
                        "jointWidthM": float(joint.width_m),
                        "jointAddedThicknessM": float(joint.added_thickness_m),
                    },
                )
            )
            local_index += 1

    if include_circumferential_front:
        append_circ(joints.circumferential_front, "front")
    if include_circumferential_back:
        append_circ(joints.circumferential_back, "back")

    mapping = {name: label for name, label in label_map.items()}
    return ScenePackage(
        name=f"tunnel_scanner_nominal_ring_{ring_id:04d}",
        mode=SceneMode.NOMINAL_WITH_PRESCRIBED_JOINTS,
        label_policy=label_policy,
        objects=tuple(objects),
        metadata={
            "sourceStages": [1, 4, 5],
            "coordinateConvention": {
                "longitudinalAxis": "+Y",
                "crossSection": "XZ",
                "alphaZero": "+Z crown",
                "units": "metres",
            },
            "segmentLabelConvention": mapping,
            "segmentLabelConventionStatus": (
                "Stage-5 generator order; article states labels 1..6 but does not "
                "publish K/B/A-to-S1..S6 correspondence"
            ),
            "jointLabelConvention": "labelID=0 clutter, following Seg2Tunnel synthesis described by Yang et al. (2026)",
            "physicalCoherence": (
                "nominal Stage-1 segments + Stage-4 prescribed joints; no Stage-3 deformation"
            ),
        },
    )


def build_deformed_scene_package(
    deformed: DeformedRingMesh,
    *,
    ring_id: int = 0,
    include_displacement_joints: bool = True,
    label_policy: LabelPolicy = LabelPolicy.SEG2TUNNEL_LIKE,
) -> ScenePackage:
    if ring_id < 0:
        raise ValueError("ring_id must be non-negative")
    if label_policy is not LabelPolicy.SEG2TUNNEL_LIKE:
        raise NotImplementedError(label_policy)

    base_ring = deformed.base_ring
    label_map = _segment_label_map(base_ring)
    segment_id_map = {segment.name: i for i, segment in enumerate(base_ring.segments)}
    transform_map = {t.segment_name: t for t in deformed.segment_transforms}
    objects: list[SceneObject] = []
    local_index = 0

    for segment in deformed.segments:
        seg_id = segment_id_map[segment.name]
        transform = transform_map[segment.name]
        objects.append(
            SceneObject(
                name=f"R{ring_id:04d}_SEG_{seg_id:02d}_{segment.name}",
                vertices=segment.vertices,
                faces=segment.faces,
                object_type="lining_segment",
                ring_id=ring_id,
                label_id=label_map[segment.name],
                instance_id=_instance_id(ring_id, local_index),
                semantic_class=f"lining_segment_{label_map[segment.name]}",
                segment_id=seg_id,
                segment_name=segment.name,
                segment_kind=segment.kind,
                reconstruction="stage3_rigid_segment_transform",
                collection_path=(f"Ring_{ring_id:04d}", "Segments"),
                extra_properties={
                    "rotationDeg": float(transform.rotation_deg),
                    "centerOffsetX": float(transform.center_offset_xz_m[0]),
                    "centerOffsetZ": float(transform.center_offset_xz_m[1]),
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
            "physicalCoherence": (
                "Stage-3 deformed segments + Stage-3 displacement gap meshes; "
                "nominal prescribed joints intentionally excluded"
            ),
            "kinematicIndexing": deformed.deformation.indexing.value,
            "closureTranslationErrorM": float(deformed.deformation.translation_closure_error_m),
            "closureAngularErrorDeg": float(deformed.deformation.angular_closure_error_deg),
        },
    )
