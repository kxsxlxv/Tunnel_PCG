from __future__ import annotations

"""Blender representation adapter for Stage-5 scene packages.

This module intentionally imports `bpy` lazily. The mathematical core and all
unit tests therefore remain importable on ordinary Python installations. The
actual object creation path is meant for Blender's bundled Python.

The implementation uses Blender's data-block API (`meshes.new`,
`Mesh.from_pydata`, `objects.new`, collection linking) rather than context-heavy
operators. Custom properties are assigned with ID-property `obj["key"] = value`
syntax, including the exact `labelID` and `ringID` names used by Tunnel Scanner.
"""

from dataclasses import dataclass
import json
import math
import struct
import time
from typing import Any

from .scene import (
    SceneObject,
    ScenePackage,
    scene_object_mesh_prototype_payload,
)


@dataclass(frozen=True)
class BlenderBuildResult:
    root_collection_name: str
    object_names: tuple[str, ...]
    mesh_names: tuple[str, ...]
    boolean_operations_applied: int = 0
    boolean_modifier_applications: int = 0
    bolt_boolean_batching_enabled: bool = False
    removed_tool_names: tuple[str, ...] = ()
    lining_cap_faces_removed: int = 0
    lining_interface_faces_removed: int = 0
    lining_extrados_faces_removed: int = 0
    mesh_prototype_count: int = 0
    mesh_prototype_instance_count: int = 0
    shared_mesh_data_blocks_saved: int = 0
    object_creation_seconds: float = 0.0
    boolean_seconds: float = 0.0
    cleanup_seconds: float = 0.0


@dataclass(frozen=True)
class BoltBooleanOperation:
    target_name: str
    tool_name: str
    ring_id: int
    bolt_index: int
    tool_type: str
    remove_tool_after: bool


def blender_available() -> bool:
    try:
        import bpy  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return True


def _require_bpy():
    try:
        import bpy  # type: ignore
    except ImportError as exc:
        raise RuntimeError(
            "Blender Python module 'bpy' is unavailable. Run this function inside Blender."
        ) from exc
    return bpy


def _ensure_child_collection(bpy, parent, logical_name: str):
    # Collection data-block names are global in Blender. Use a qualified name so
    # Ring_0001/Segments and Ring_0002/Segments never accidentally become the
    # same collection linked under two parents. The short logical name is kept
    # as a custom property for tooling/UI.
    qualified_name = f"{parent.name}::{logical_name}"
    existing = bpy.data.collections.get(qualified_name)
    if existing is None:
        existing = bpy.data.collections.new(qualified_name)
        existing["logicalName"] = logical_name
    if existing.name not in {c.name for c in parent.children}:
        parent.children.link(existing)
    return existing


def _remove_collection_tree(bpy, collection) -> None:
    # Copy child/object lists because Blender collections mutate as we remove.
    for child in list(collection.children):
        _remove_collection_tree(bpy, child)
    for obj in list(collection.objects):
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(collection)


def _ensure_collection_path(bpy, root, path: tuple[str, ...]):
    current = root
    for part in path:
        current = _ensure_child_collection(bpy, current, part)
    return current


_BLENDER_IDPROP_INT_MIN = -(2**31)
_BLENDER_IDPROP_INT_MAX = 2**31 - 1


def _blender_custom_property_scalar(value: Any) -> str | int | float | bool:
    """Convert an engine-neutral scalar to a Blender-safe ID property value.

    Blender 5.2.x can route Python integer assignment through a C int for scalar
    custom properties. Stage-9 persistent IDs are positive 63-bit values, so
    assigning them directly can raise OverflowError. Preserve the exact integer
    losslessly as a decimal string when it exceeds the signed 32-bit range.
    Small integers remain native Blender integer properties.

    The engine-neutral ScenePackage/JSON representation is unchanged and keeps
    the original Python integer.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if _BLENDER_IDPROP_INT_MIN <= value <= _BLENDER_IDPROP_INT_MAX:
            return value
        return str(value)
    if isinstance(value, (str, float)):
        return value
    raise TypeError(f"unsupported Blender scalar type: {type(value)!r}")


def _blender_custom_property_value(value: Any) -> str | int | float | bool:
    """Convert engine-neutral metadata to a Blender-safe ID property value.

    Blender ID properties do not provide a stable cross-version representation
    for arbitrary Python/JSON containers. Stage-10 production metadata contains
    structured values such as the contact-rail resourceEnvelopeM vector.
    Preserve those containers losslessly as compact canonical JSON strings.

    Scalar behavior remains unchanged, including decimal-string encoding for
    positive 63-bit persistent IDs.
    """
    try:
        return _blender_custom_property_scalar(value)
    except TypeError:
        pass

    if isinstance(value, (list, tuple, dict)):
        try:
            return json.dumps(
                value,
                sort_keys=isinstance(value, dict),
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"unsupported Blender structured property value: {type(value)!r}"
            ) from exc

    raise TypeError(f"unsupported Blender property type: {type(value)!r}")


def _set_custom_properties(blender_object, properties: dict[str, Any]) -> None:
    for key, value in properties.items():
        try:
            blender_object[key] = _blender_custom_property_value(value)
        except TypeError as exc:
            raise TypeError(
                f"custom property {key!r} has unsupported Blender property type: "
                f"{type(value)!r}"
            ) from exc


def _mesh_prototype_payload(
    scene_object: SceneObject,
) -> tuple[str, tuple[float, float, float], tuple[tuple[float, float, float], ...]] | None:
    """Backward-compatible private alias for the engine-neutral prototype helper."""
    return scene_object_mesh_prototype_payload(scene_object)


def create_blender_object(
    scene_object: SceneObject,
    collection,
    *,
    validate_mesh: bool = True,
    mesh_prototypes: dict[str, Any] | None = None,
):
    bpy = _require_bpy()
    prototype = (
        _mesh_prototype_payload(scene_object)
        if mesh_prototypes is not None
        else None
    )

    if prototype is None:
        mesh = bpy.data.meshes.new(f"{scene_object.name}_MESH")
        mesh.from_pydata(scene_object.vertices, [], scene_object.faces)
        object_translation = None
    else:
        prototype_key, object_translation, local_vertices = prototype
        mesh = mesh_prototypes.get(prototype_key)
        if mesh is None:
            mesh = bpy.data.meshes.new(f"{scene_object.name}_PROTO_MESH")
            mesh.from_pydata(local_vertices, [], scene_object.faces)
            if validate_mesh:
                mesh.validate(verbose=False)
            mesh.update(calc_edges=True)
            mesh_prototypes[prototype_key] = mesh

    if prototype is None:
        if validate_mesh:
            mesh.validate(verbose=False)
        mesh.update(calc_edges=True)

    obj = bpy.data.objects.new(scene_object.name, mesh)
    if object_translation is not None:
        obj.location = object_translation
    collection.objects.link(obj)
    _set_custom_properties(obj, scene_object.custom_properties)
    return obj


def plan_bolt_boolean_operations(package: ScenePackage) -> tuple[BoltBooleanOperation, ...]:
    """Build deterministic Stage-6 Boolean order without importing bpy.

    Production head-only RC bolts always cut the pocket recess, then remove the
    transient cutter. Legacy/debug mode additionally cuts the head seating
    volume with the visible head mesh.
    """
    grouped: dict[tuple[int, int], dict[str, SceneObject]] = {}
    for obj in package.objects:
        if obj.object_type not in {"bolt_pocket_cutter", "bolt_head"}:
            continue
        props = obj.custom_properties
        if (
            obj.object_type == "bolt_head"
            and props.get("cutTargetBeforeDisplay") is False
        ):
            continue
        if "boltIndex" not in props or "booleanTarget" not in props:
            raise ValueError(f"{obj.name}: incomplete Stage-6 Boolean metadata")
        idx = int(props["boltIndex"])
        key = (int(obj.ring_id), idx)
        slot = grouped.setdefault(key, {})
        if obj.object_type in slot:
            raise ValueError(
                f"duplicate {obj.object_type} for ringID={obj.ring_id}, boltIndex={idx}"
            )
        slot[obj.object_type] = obj

    operations: list[BoltBooleanOperation] = []
    for ring_id, idx in sorted(grouped):
        slot = grouped[(ring_id, idx)]
        if "bolt_pocket_cutter" not in slot:
            raise ValueError(
                f"ringID={ring_id}, boltIndex={idx}: pocket cutter is required"
            )
        if set(slot) not in (
            {"bolt_pocket_cutter"},
            {"bolt_pocket_cutter", "bolt_head"},
        ):
            raise ValueError(
                f"ringID={ring_id}, boltIndex={idx}: unexpected Boolean tools {sorted(slot)}"
            )

        cutter = slot["bolt_pocket_cutter"]
        cutter_target = str(cutter.custom_properties["booleanTarget"])
        operations.append(
            BoltBooleanOperation(
                target_name=cutter_target,
                tool_name=cutter.name,
                ring_id=ring_id,
                bolt_index=idx,
                tool_type="bolt_pocket_cutter",
                remove_tool_after=True,
            )
        )

        head = slot.get("bolt_head")
        if head is not None:
            head_target = str(head.custom_properties["booleanTarget"])
            if cutter_target != head_target:
                raise ValueError(
                    f"ringID={ring_id}, boltIndex={idx}: cutter/head target mismatch"
                )
            operations.append(
                BoltBooleanOperation(
                    target_name=head_target,
                    tool_name=head.name,
                    ring_id=ring_id,
                    bolt_index=idx,
                    tool_type="bolt_head",
                    remove_tool_after=False,
                )
            )
    return tuple(operations)


def plan_bolt_boolean_batches(
    package: ScenePackage,
    *,
    batch_pocket_cutters: bool = True,
) -> tuple[tuple[BoltBooleanOperation, ...], ...]:
    """Group safe production pocket cuts by lining target.

    Batching is enabled only when every planned Boolean is a removable pocket
    cutter. If visible bolt heads also participate as Boolean tools, return
    singleton batches so historical cutter/head ordering remains unchanged.
    """
    operations = plan_bolt_boolean_operations(package)
    if not operations:
        return ()
    production_cutter_only = all(
        op.tool_type == "bolt_pocket_cutter"
        and op.remove_tool_after
        for op in operations
    )
    if not batch_pocket_cutters or not production_cutter_only:
        return tuple((op,) for op in operations)

    grouped: dict[str, list[BoltBooleanOperation]] = {}
    target_order: list[str] = []
    for op in operations:
        if op.target_name not in grouped:
            grouped[op.target_name] = []
            target_order.append(op.target_name)
        grouped[op.target_name].append(op)
    return tuple(tuple(grouped[target]) for target in target_order)


def _apply_boolean_difference(
    bpy,
    target,
    tool,
    *,
    modifier_name: str,
    validate_mesh: bool = True,
) -> None:
    modifier = target.modifiers.new(name=modifier_name, type="BOOLEAN")
    modifier.operation = "DIFFERENCE"
    if hasattr(modifier, "solver"):
        modifier.solver = "EXACT"
    modifier.object = tool

    try:
        if hasattr(bpy.context, "temp_override"):
            with bpy.context.temp_override(
                object=target,
                active_object=target,
                selected_objects=[target],
                selected_editable_objects=[target],
            ):
                result = bpy.ops.object.modifier_apply(modifier=modifier.name)
        else:
            for obj in getattr(bpy.context, "selected_objects", []):
                obj.select_set(False)
            target.select_set(True)
            bpy.context.view_layer.objects.active = target
            result = bpy.ops.object.modifier_apply(modifier=modifier.name)
    except Exception as exc:  # pragma: no cover - requires real Blender
        raise RuntimeError(
            f"Boolean DIFFERENCE failed: target={target.name!r}, tool={tool.name!r}"
        ) from exc

    if result is not None and "CANCELLED" in result:
        raise RuntimeError(
            f"Boolean DIFFERENCE cancelled: target={target.name!r}, tool={tool.name!r}"
        )
    if validate_mesh and hasattr(target.data, "validate"):
        target.data.validate(verbose=False)
    if hasattr(target.data, "update"):
        target.data.update(calc_edges=True)


def _remove_blender_mesh_object(bpy, obj) -> None:
    mesh = obj.data
    bpy.data.objects.remove(obj, do_unlink=True)
    if getattr(mesh, "users", 1) == 0:
        bpy.data.meshes.remove(mesh)


def _combined_boolean_tool_for_target(
    bpy,
    target,
    tools,
    *,
    name: str,
):
    """Combine disconnected cutter solids into target-local coordinates.

    Difference by one mesh containing disjoint closed components is
    geometrically equivalent to sequential differences by those components.
    Keeping the combined mesh in target-local coordinates also makes this safe
    if a future importer places the target with a non-identity object transform.
    """
    if not tools:
        raise ValueError("combined Boolean tool requires at least one source tool")

    target_inverse = target.matrix_world.inverted()
    vertices = []
    faces = []
    for tool in tools:
        transform = target_inverse @ tool.matrix_world
        base = len(vertices)
        vertices.extend(
            tuple(float(value) for value in (transform @ vertex.co))
            for vertex in tool.data.vertices
        )
        faces.extend(
            tuple(base + int(index) for index in polygon.vertices)
            for polygon in tool.data.polygons
        )

    mesh = bpy.data.meshes.new(f"{name}_MESH")
    mesh.from_pydata(vertices, [], faces)
    mesh.update(calc_edges=True)
    combined = bpy.data.objects.new(name, mesh)
    combined.matrix_world = target.matrix_world.copy()

    source_collections = list(getattr(tools[0], "users_collection", ()))
    collection = (
        source_collections[0]
        if source_collections
        else bpy.context.scene.collection
    )
    collection.objects.link(combined)
    return combined


def _apply_stage6_bolt_booleans(
    bpy,
    package: ScenePackage,
    *,
    batch_pocket_cutters: bool = True,
    validate_mesh: bool = True,
) -> tuple[int, int, tuple[str, ...]]:
    """Apply Stage-6 Booleans, batching production pocket cutters per segment.

    Production visible-head mode contains only pocket-cutter Boolean operations:
    three disjoint cutters target each TYPE1 lining segment. Applying their
    disconnected union in one Exact Boolean reduces modifier evaluation count
    by 3x without changing the set-theoretic result. Legacy/debug scenes that
    also use bolt heads as Boolean tools keep the historical sequential order.
    """
    operations = plan_bolt_boolean_operations(package)
    if not operations:
        return 0, 0, ()

    batches = plan_bolt_boolean_batches(
        package,
        batch_pocket_cutters=batch_pocket_cutters,
    )
    batched_production_mode = (
        len(batches) < len(operations)
        and all(
            len(batch) >= 1
            and all(op.tool_type == "bolt_pocket_cutter" for op in batch)
            for batch in batches
        )
    )
    if batched_production_mode:
        removed: list[str] = []
        modifier_count = 0
        for batch_index, batch in enumerate(batches):
            target_name = batch[0].target_name
            target = bpy.data.objects.get(target_name)
            if target is None:
                raise RuntimeError(
                    f"Boolean target missing in Blender: {target_name}"
                )
            tools = []
            for op in batch:
                tool = bpy.data.objects.get(op.tool_name)
                if tool is None:
                    raise RuntimeError(
                        f"Boolean tool missing in Blender: {op.tool_name}"
                    )
                tools.append(tool)

            if len(tools) == 1:
                boolean_tool = tools[0]
                combined_tool = None
            else:
                boolean_tool = _combined_boolean_tool_for_target(
                    bpy,
                    target,
                    tools,
                    name=(
                        f"TS_BATCH_R{batch[0].ring_id:04d}_"
                        f"{batch_index:04d}_CUTTERS"
                    ),
                )
                combined_tool = boolean_tool

            _apply_boolean_difference(
                bpy,
                target,
                boolean_tool,
                modifier_name=(
                    f"TS_R{batch[0].ring_id:04d}_"
                    f"BATCH_{batch_index:04d}_bolt_pocket_cutters"
                ),
                validate_mesh=validate_mesh,
            )
            modifier_count += 1

            if combined_tool is not None:
                _remove_blender_mesh_object(bpy, combined_tool)
            for op, tool in zip(batch, tools):
                _remove_blender_mesh_object(bpy, tool)
                removed.append(op.tool_name)

        return len(operations), modifier_count, tuple(removed)

    removed: list[str] = []
    modifier_count = 0
    for op in operations:
        target = bpy.data.objects.get(op.target_name)
        tool = bpy.data.objects.get(op.tool_name)
        if target is None:
            raise RuntimeError(f"Boolean target missing in Blender: {op.target_name}")
        if tool is None:
            raise RuntimeError(f"Boolean tool missing in Blender: {op.tool_name}")
        _apply_boolean_difference(
            bpy,
            target,
            tool,
            modifier_name=(
                f"TS_R{op.ring_id:04d}_BOLT_{op.bolt_index:03d}_{op.tool_type}"
            ),
            validate_mesh=validate_mesh,
        )
        modifier_count += 1
        if op.remove_tool_after:
            _remove_blender_mesh_object(bpy, tool)
            removed.append(op.tool_name)

    return len(operations), modifier_count, tuple(removed)


def _float32_vertex_key(vertex_xyz) -> bytes:
    """Canonical key matching Blender mesh coordinate storage precision."""
    x, y, z = (float(v) for v in vertex_xyz)
    return struct.pack("<fff", x, y, z)


def _source_lining_extrados_vertex_keys(
    scene_object: SceneObject,
) -> frozenset[bytes]:
    """Return exact pre-Boolean extrados vertices from curved-mesh topology.

    build_curved_segment_mesh stores every grid point as an
    intrados/extrados vertex pair. All subsequent Stage-10 transforms preserve
    vertex order. For transferred RC lining segments, odd vertex indices are
    therefore the outer layer irrespective of ring rotation or alignment warp.
    """
    if scene_object.object_type != "lining_segment":
        raise ValueError("extrados topology classifier requires lining_segment")
    props = scene_object.custom_properties
    if props.get("analyticalSource") != "stage1_hexahedral_segment":
        raise ValueError(
            f"{scene_object.name}: unsupported lining analytical source"
        )
    vertices = scene_object.vertices
    if len(vertices) == 0 or len(vertices) % 2 != 0:
        raise ValueError(
            f"{scene_object.name}: curved lining vertex pairing is malformed"
        )

    nu = int(props.get("surfaceSubdivisions", 0))
    nv = int(props.get("surfaceLongitudinalSubdivisions", 0))
    if nu <= 0 or nv <= 0:
        raise ValueError(
            f"{scene_object.name}: missing curved-surface subdivision metadata"
        )
    expected_vertices = 2 * (nu + 1) * (nv + 1)
    if len(vertices) != expected_vertices:
        raise ValueError(
            f"{scene_object.name}: curved lining vertex count {len(vertices)} "
            f"does not match topology contract {expected_vertices}"
        )

    return frozenset(
        _float32_vertex_key(vertices[i])
        for i in range(1, len(vertices), 2)
    )


def _source_lining_boundary_vertex_keys(
    scene_object: SceneObject,
    boundary: str,
) -> frozenset[bytes]:
    """Return source curved-mesh vertices on one topological boundary."""
    props = scene_object.custom_properties
    vertices = scene_object.vertices
    nu = int(props.get("surfaceSubdivisions", 0))
    nv = int(props.get("surfaceLongitudinalSubdivisions", 0))
    expected_vertices = 2 * (nu + 1) * (nv + 1)
    if (
        scene_object.object_type != "lining_segment"
        or nu <= 0
        or nv <= 0
        or len(vertices) != expected_vertices
    ):
        raise ValueError(
            f"{scene_object.name}: invalid curved lining topology metadata"
        )

    def index(iv: int, iu: int, layer: int) -> int:
        return 2 * (iv * (nu + 1) + iu) + layer

    indices: list[int] = []
    if boundary == "front":
        for iu in range(nu + 1):
            indices.extend((index(0, iu, 0), index(0, iu, 1)))
    elif boundary == "back":
        for iu in range(nu + 1):
            indices.extend((index(nv, iu, 0), index(nv, iu, 1)))
    elif boundary == "start":
        for iv in range(nv + 1):
            indices.extend((index(iv, 0, 0), index(iv, 0, 1)))
    elif boundary == "end":
        for iv in range(nv + 1):
            indices.extend((index(iv, nu, 0), index(iv, nu, 1)))
    else:
        raise ValueError(f"unknown curved lining boundary: {boundary!r}")
    return frozenset(
        _float32_vertex_key(vertices[index])
        for index in indices
    )

def _strip_internal_lining_caps_in_blender(
    bpy,
    package: ScenePackage,
    *,
    tolerance_m: float = 1e-8,
) -> int:
    """Post-Boolean cleanup of hidden internal ring end faces.

    Transferred Moscow RC segments are classified from their source curved-mesh
    topology, so cleanup remains exact after arbitrary 3D route yaw/pitch.
    Legacy Stage-9 scenes retain the historical global-Y plane classifier.
    """
    try:
        import bmesh  # type: ignore
    except ImportError as exc:  # pragma: no cover - Blender runtime only
        raise RuntimeError("bmesh is required for lining cap cleanup") from exc

    if "ringWidthM" not in package.metadata:
        raise ValueError("scene metadata lacks ringWidthM for lining cap cleanup")
    ring_width_m = float(package.metadata["ringWidthM"])
    lining_objects = [
        obj for obj in package.objects
        if obj.object_type == "lining_segment"
    ]
    if not lining_objects:
        return 0
    global_ring_count = int(
        package.metadata.get(
            "ringCount",
            max(obj.ring_id for obj in lining_objects) + 1,
        )
    )
    global_max_ring_id = global_ring_count - 1
    removed_total = 0

    for scene_object in lining_objects:
        obj = bpy.data.objects.get(scene_object.name)
        if obj is None:
            raise RuntimeError(
                f"lining object missing during cap cleanup: {scene_object.name}"
            )
        props = scene_object.custom_properties
        transferred_moscow = bool(
            props.get(
                "stage9SegmentJointFastenerArchitectureTransferred",
                False,
            )
        )
        lining_ring_index = int(
            props.get("liningRingIndex", scene_object.ring_id)
        )
        lining_ring_count = int(
            props.get("liningGlobalRingCount", global_ring_count)
        )
        strip_front = lining_ring_index > 0
        strip_back = lining_ring_index < lining_ring_count - 1

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        remove = []

        if transferred_moscow:
            front_keys = _source_lining_boundary_vertex_keys(
                scene_object,
                "front",
            )
            back_keys = _source_lining_boundary_vertex_keys(
                scene_object,
                "back",
            )
            for face in bm.faces:
                keys = tuple(
                    _float32_vertex_key(
                        (
                            float(vertex.co.x),
                            float(vertex.co.y),
                            float(vertex.co.z),
                        )
                    )
                    for vertex in face.verts
                )
                if (
                    (strip_front and all(key in front_keys for key in keys))
                    or (strip_back and all(key in back_keys for key in keys))
                ):
                    remove.append(face)
            cleanup_mode = "source_curved_mesh_end_vertex_topology_v1"
        else:
            origin_y = (
                float(props.get("chunkWorldOriginY", 0.0))
                if bool(props.get("coordinatesLocalizedToChunk", False))
                else 0.0
            )
            if (
                "liningRingFrontWorldYM" in props
                and "liningRingBackWorldYM" in props
            ):
                front_y = float(props["liningRingFrontWorldYM"]) - origin_y
                back_y = float(props["liningRingBackWorldYM"]) - origin_y
            else:
                front_y = (
                    (scene_object.ring_id - 0.5) * ring_width_m - origin_y
                )
                back_y = (
                    (scene_object.ring_id + 0.5) * ring_width_m - origin_y
                )
                strip_front = scene_object.ring_id > 0
                strip_back = scene_object.ring_id < global_max_ring_id
            for face in bm.faces:
                ys = [float(vertex.co.y) for vertex in face.verts]
                on_front = strip_front and all(
                    abs(y - front_y) <= tolerance_m for y in ys
                )
                on_back = strip_back and all(
                    abs(y - back_y) <= tolerance_m for y in ys
                )
                if on_front or on_back:
                    remove.append(face)
            cleanup_mode = "legacy_metadata_y_plane"

        for face in remove:
            bm.faces.remove(face)
        removed = len(remove)
        removed_total += removed
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update(calc_edges=True)
        obj["internalLongitudinalCapsStripped"] = True
        obj["longitudinalCapFacesRemoved"] = int(removed)
        obj["renderSurfaceOpenAtInternalRingBoundaries"] = True
        obj["liningCapCleanupPlaneMode"] = cleanup_mode

    return removed_total


def _strip_coincident_lining_interfaces_in_blender(
    bpy,
    package: ScenePackage,
    *,
    angle_tolerance_deg: float = 1e-3,
    radial_span_tolerance_m: float = 1e-5,
    y_span_tolerance_m: float = 1e-8,
) -> int:
    """Remove hidden radial segment-boundary surfaces.

    Transferred Moscow RC segments use source curved-mesh boundary topology,
    which is invariant under arbitrary route yaw/pitch. Legacy Stage-9 geometry
    retains the analytical global-Y classifier for backward compatibility.
    """
    try:
        import bmesh  # type: ignore
    except ImportError as exc:  # pragma: no cover - Blender runtime only
        raise RuntimeError(
            "bmesh is required for lining interface cleanup"
        ) from exc

    if "ringWidthM" not in package.metadata:
        raise ValueError(
            "scene metadata lacks ringWidthM for lining interface cleanup"
        )
    ring_width_m = float(package.metadata["ringWidthM"])

    def angle_delta(a_deg: float, b_deg: float) -> float:
        return (a_deg - b_deg + 180.0) % 360.0 - 180.0

    removed_total = 0
    for scene_object in package.objects:
        if scene_object.object_type != "lining_segment":
            continue
        props = scene_object.custom_properties
        obj = bpy.data.objects.get(scene_object.name)
        if obj is None:
            raise RuntimeError(
                f"lining object missing during interface cleanup: "
                f"{scene_object.name}"
            )

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        remove = []
        transferred_moscow = bool(
            props.get(
                "stage9SegmentJointFastenerArchitectureTransferred",
                False,
            )
        )

        if transferred_moscow:
            start_keys = _source_lining_boundary_vertex_keys(
                scene_object,
                "start",
            )
            end_keys = _source_lining_boundary_vertex_keys(
                scene_object,
                "end",
            )
            for face in bm.faces:
                keys = tuple(
                    _float32_vertex_key(
                        (
                            float(vertex.co.x),
                            float(vertex.co.y),
                            float(vertex.co.z),
                        )
                    )
                    for vertex in face.verts
                )
                if (
                    all(key in start_keys for key in keys)
                    or all(key in end_keys for key in keys)
                ):
                    remove.append(face)
            cleanup_mode = "source_curved_mesh_radial_vertex_topology_v1"
        else:
            required = (
                "segmentFrontStartDeg",
                "segmentFrontEndDeg",
                "segmentBackStartDeg",
                "segmentBackEndDeg",
                "ringTranslationX",
                "ringTranslationY",
                "ringTranslationZ",
                "ringRotationDeg",
            )
            if any(key not in props for key in required):
                bm.free()
                raise ValueError(
                    f"{scene_object.name}: missing angular boundary metadata "
                    "for Stage-9 cleanup"
                )

            local_ring_width_m = float(
                props.get("liningRingWidthM", ring_width_m)
            )
            tx = float(props["ringTranslationX"])
            ty = float(props["ringTranslationY"])
            tz = float(props["ringTranslationZ"])
            localized = bool(
                props.get("coordinatesLocalizedToChunk", False)
            )
            origin_x = (
                float(props.get("chunkWorldOriginX", 0.0))
                if localized
                else 0.0
            )
            origin_y = (
                float(props.get("chunkWorldOriginY", 0.0))
                if localized
                else 0.0
            )
            origin_z = (
                float(props.get("chunkWorldOriginZ", 0.0))
                if localized
                else 0.0
            )
            tx -= origin_x
            ty -= origin_y
            tz -= origin_z
            stitched = bool(
                props.get("productionRingAlignmentStitched", False)
            )
            rotation = math.radians(float(props["ringRotationDeg"]))
            c = math.cos(rotation)
            sr = math.sin(rotation)
            fs = float(props["segmentFrontStartDeg"])
            fe = float(props["segmentFrontEndDeg"])
            bs = float(props["segmentBackStartDeg"])
            be = float(props["segmentBackEndDeg"])

            for face in bm.faces:
                samples = []
                for vertex in face.verts:
                    x = float(vertex.co.x)
                    y = float(vertex.co.y)
                    z = float(vertex.co.z)
                    local_y = y - ty
                    center_x = tx
                    center_z = tz
                    if stitched:
                        front_x = (
                            float(props["productionRingFrontOffsetX"])
                            - origin_x
                        )
                        front_z = (
                            float(props["productionRingFrontOffsetZ"])
                            - origin_z
                        )
                        centre_x = (
                            float(props["productionRingCenterOffsetX"])
                            - origin_x
                        )
                        centre_z = (
                            float(props["productionRingCenterOffsetZ"])
                            - origin_z
                        )
                        back_x = (
                            float(props["productionRingBackOffsetX"])
                            - origin_x
                        )
                        back_z = (
                            float(props["productionRingBackOffsetZ"])
                            - origin_z
                        )
                        if local_y <= 0.0:
                            u = min(
                                1.0,
                                max(
                                    0.0,
                                    (
                                        local_y
                                        + 0.5 * local_ring_width_m
                                    )
                                    / (0.5 * local_ring_width_m),
                                ),
                            )
                            center_x = (
                                front_x + u * (centre_x - front_x)
                            )
                            center_z = (
                                front_z + u * (centre_z - front_z)
                            )
                        else:
                            u = min(
                                1.0,
                                max(
                                    0.0,
                                    local_y
                                    / (0.5 * local_ring_width_m),
                                ),
                            )
                            center_x = (
                                centre_x + u * (back_x - centre_x)
                            )
                            center_z = (
                                centre_z + u * (back_z - centre_z)
                            )

                    dx = x - center_x
                    dz = z - center_z
                    local_x = c * dx - sr * dz
                    local_z = sr * dx + c * dz
                    samples.append(
                        (
                            local_y,
                            math.hypot(local_x, local_z),
                            math.degrees(math.atan2(local_x, local_z)),
                        )
                    )

                ys = [sample[0] for sample in samples]
                radii = [sample[1] for sample in samples]
                if max(ys) - min(ys) <= y_span_tolerance_m:
                    continue
                if max(radii) - min(radii) <= radial_span_tolerance_m:
                    continue

                start_match = True
                end_match = True
                for local_y, _radius, alpha in samples:
                    v = (
                        local_y + 0.5 * local_ring_width_m
                    ) / local_ring_width_m
                    v = min(1.0, max(0.0, v))
                    expected_start = fs + v * (bs - fs)
                    expected_end = fe + v * (be - fe)
                    start_match = start_match and (
                        abs(angle_delta(alpha, expected_start))
                        <= angle_tolerance_deg
                    )
                    end_match = end_match and (
                        abs(angle_delta(alpha, expected_end))
                        <= angle_tolerance_deg
                    )
                if start_match or end_match:
                    remove.append(face)
            cleanup_mode = "legacy_analytical_angular_boundary_v1"

        for face in remove:
            bm.faces.remove(face)
        removed = len(remove)
        removed_total += removed
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update(calc_edges=True)
        obj["segmentBoundaryFacesStripped"] = True
        obj["segmentBoundaryFacesRemoved"] = int(removed)
        obj["renderSurfaceOpenAtSegmentInterfaces"] = True
        obj["segmentBoundaryCleanupMode"] = cleanup_mode

    return removed_total


def _strip_hidden_lining_extrados_in_blender(
    bpy,
    package: ScenePackage,
) -> int:
    """Remove untouched hidden RC extrados faces after bolt Booleans.

    The source curved-segment topology provides an exact outer-layer vertex
    set before Blender runs Boolean operations. A surviving Blender face is
    classified as extrados only when every one of its vertices is one of
    those original outer-layer vertices. Intrados, radial/end faces and all
    Boolean-generated pocket surfaces therefore remain.
    """
    try:
        import bmesh  # type: ignore
    except ImportError as exc:  # pragma: no cover - Blender runtime only
        raise RuntimeError("bmesh is required for lining extrados cleanup") from exc

    removed_total = 0
    for scene_object in package.objects:
        if scene_object.object_type != "lining_segment":
            continue
        props = scene_object.custom_properties
        if not bool(
            props.get("stage9SegmentJointFastenerArchitectureTransferred", False)
        ):
            continue
        if props.get("civilFamily") != "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000":
            continue

        extrados_vertices = _source_lining_extrados_vertex_keys(scene_object)
        obj = bpy.data.objects.get(scene_object.name)
        if obj is None:
            raise RuntimeError(
                f"lining object missing during extrados cleanup: {scene_object.name}"
            )

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        remove = [
            face
            for face in bm.faces
            if face.verts
            and all(
                _float32_vertex_key(
                    (
                        float(vertex.co.x),
                        float(vertex.co.y),
                        float(vertex.co.z),
                    )
                )
                in extrados_vertices
                for vertex in face.verts
            )
        ]

        for face in remove:
            bm.faces.remove(face)
        removed = len(remove)
        removed_total += removed
        bm.to_mesh(obj.data)
        bm.free()
        obj.data.update(calc_edges=True)
        obj["hiddenExtradosFacesStripped"] = True
        obj["hiddenExtradosFacesRemoved"] = int(removed)
        obj["renderSurfaceOpenAtExtrados"] = True
        obj["extradosCleanupMode"] = "source_curved_mesh_outer_vertex_topology_v2"

    return removed_total

def build_scene_package_in_blender(
    package: ScenePackage,
    *,
    root_collection_name: str = "TunnelScanner",
    clear_existing_root: bool = True,
    validate_mesh: bool = True,
    set_metric_units: bool = True,
    apply_bolt_booleans: bool = True,
    strip_internal_lining_caps: bool = False,
    strip_coincident_lining_interfaces: bool = False,
    strip_hidden_lining_extrados: bool = False,
    reuse_mesh_prototypes: bool = True,
    batch_bolt_pocket_booleans: bool = True,
    omit_bolt_boolean_tools: bool = False,
) -> BlenderBuildResult:
    bpy = _require_bpy()
    if apply_bolt_booleans and omit_bolt_boolean_tools:
        raise ValueError(
            "omit_bolt_boolean_tools requires apply_bolt_booleans=False"
        )

    existing = bpy.data.collections.get(root_collection_name)
    if clear_existing_root and existing is not None:
        _remove_collection_tree(bpy, existing)
        existing = None

    if existing is None:
        root = bpy.data.collections.new(root_collection_name)
        bpy.context.scene.collection.children.link(root)
    else:
        root = existing
    root["scenePackageName"] = package.name
    root["sceneMode"] = package.mode.value
    root["labelPolicy"] = package.label_policy.value
    root["sceneSchemaVersion"] = 1

    if set_metric_units:
        bpy.context.scene.unit_settings.system = "METRIC"
        bpy.context.scene.unit_settings.scale_length = 1.0
        bpy.context.scene.unit_settings.length_unit = "METERS"

    object_names: list[str] = []
    mesh_names: list[str] = []
    mesh_prototypes: dict[str, Any] | None = (
        {} if reuse_mesh_prototypes else None
    )
    mesh_prototype_instance_count = 0
    object_creation_started = time.perf_counter()
    for scene_object in package.objects:
        if (
            omit_bolt_boolean_tools
            and scene_object.object_type == "bolt_pocket_cutter"
        ):
            continue
        target = _ensure_collection_path(bpy, root, scene_object.collection_path)
        if (
            mesh_prototypes is not None
            and scene_object.extra_properties.get("meshPrototypeKey") is not None
        ):
            mesh_prototype_instance_count += 1
        obj = create_blender_object(
            scene_object,
            target,
            validate_mesh=validate_mesh,
            mesh_prototypes=mesh_prototypes,
        )
        object_names.append(obj.name)
        mesh_names.append(obj.data.name)

    object_creation_seconds = time.perf_counter() - object_creation_started
    mesh_prototype_count = len(mesh_prototypes or {})
    root["meshPrototypeReuseEnabled"] = bool(reuse_mesh_prototypes)
    root["meshValidationEnabled"] = bool(validate_mesh)
    root["postBooleanMeshValidationEnabled"] = bool(validate_mesh)
    root["meshPrototypeCount"] = int(mesh_prototype_count)
    root["meshPrototypeInstanceCount"] = int(mesh_prototype_instance_count)
    root["sharedMeshDataBlocksSaved"] = int(
        max(0, mesh_prototype_instance_count - mesh_prototype_count)
    )

    boolean_count = 0
    boolean_modifier_count = 0
    removed_tools: tuple[str, ...] = ()
    boolean_started = time.perf_counter()
    if apply_bolt_booleans:
        (
            boolean_count,
            boolean_modifier_count,
            removed_tools,
        ) = _apply_stage6_bolt_booleans(
            bpy,
            package,
            batch_pocket_cutters=batch_bolt_pocket_booleans,
            validate_mesh=validate_mesh,
        )
    boolean_seconds = time.perf_counter() - boolean_started

    cleanup_started = time.perf_counter()
    lining_cap_faces_removed = 0
    if strip_internal_lining_caps:
        lining_cap_faces_removed = _strip_internal_lining_caps_in_blender(
            bpy, package
        )

    lining_interface_faces_removed = 0
    if strip_coincident_lining_interfaces:
        lining_interface_faces_removed = (
            _strip_coincident_lining_interfaces_in_blender(bpy, package)
        )

    lining_extrados_faces_removed = 0
    if strip_hidden_lining_extrados:
        lining_extrados_faces_removed = (
            _strip_hidden_lining_extrados_in_blender(bpy, package)
        )

    cleanup_seconds = time.perf_counter() - cleanup_started

    surviving_object_names = tuple(
        name for name in object_names if bpy.data.objects.get(name) is not None
    )
    surviving_mesh_names = tuple(
        bpy.data.objects.get(name).data.name
        for name in surviving_object_names
        if getattr(bpy.data.objects.get(name), "data", None) is not None
    )
    return BlenderBuildResult(
        root_collection_name=root.name,
        object_names=surviving_object_names,
        mesh_names=surviving_mesh_names,
        boolean_operations_applied=boolean_count,
        boolean_modifier_applications=boolean_modifier_count,
        bolt_boolean_batching_enabled=bool(
            batch_bolt_pocket_booleans and apply_bolt_booleans
        ),
        removed_tool_names=removed_tools,
        lining_cap_faces_removed=lining_cap_faces_removed,
        lining_interface_faces_removed=lining_interface_faces_removed,
        lining_extrados_faces_removed=lining_extrados_faces_removed,
        mesh_prototype_count=mesh_prototype_count,
        mesh_prototype_instance_count=mesh_prototype_instance_count,
        shared_mesh_data_blocks_saved=max(
            0,
            mesh_prototype_instance_count - mesh_prototype_count,
        ),
        object_creation_seconds=object_creation_seconds,
        boolean_seconds=boolean_seconds,
        cleanup_seconds=cleanup_seconds,
    )
