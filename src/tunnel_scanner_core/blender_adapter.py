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
from typing import Any

from .scene import SceneObject, ScenePackage


@dataclass(frozen=True)
class BlenderBuildResult:
    root_collection_name: str
    object_names: tuple[str, ...]
    mesh_names: tuple[str, ...]
    boolean_operations_applied: int = 0
    removed_tool_names: tuple[str, ...] = ()


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


def _set_custom_properties(blender_object, properties: dict[str, Any]) -> None:
    for key, value in properties.items():
        # Current Stage-5 metadata consists only of Blender ID-property-friendly
        # scalar/string values. Reject nested data early instead of relying on
        # version-specific implicit conversion.
        if not isinstance(value, (str, int, float, bool)):
            raise TypeError(
                f"custom property {key!r} has unsupported Blender scalar type: {type(value)!r}"
            )
        blender_object[key] = value


def create_blender_object(scene_object: SceneObject, collection, *, validate_mesh: bool = True):
    bpy = _require_bpy()
    mesh = bpy.data.meshes.new(f"{scene_object.name}_MESH")
    mesh.from_pydata(scene_object.vertices, [], scene_object.faces)
    if validate_mesh:
        mesh.validate(verbose=False)
    mesh.update(calc_edges=True)

    obj = bpy.data.objects.new(scene_object.name, mesh)
    collection.objects.link(obj)
    _set_custom_properties(obj, scene_object.custom_properties)
    return obj


def plan_bolt_boolean_operations(package: ScenePackage) -> tuple[BoltBooleanOperation, ...]:
    """Build deterministic Stage-6 Boolean order without importing bpy.

    Each bolt first cuts its pocket volume, then cuts the head seating volume.
    The pocket cutter is removed afterwards; the head remains as visible clutter.
    """
    grouped: dict[tuple[int, int], dict[str, SceneObject]] = {}
    for obj in package.objects:
        if obj.object_type not in {"bolt_pocket_cutter", "bolt_head"}:
            continue
        props = obj.custom_properties
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
        if set(slot) != {"bolt_pocket_cutter", "bolt_head"}:
            raise ValueError(
                f"ringID={ring_id}, boltIndex={idx}: expected pocket cutter + head, got {sorted(slot)}"
            )
        cutter = slot["bolt_pocket_cutter"]
        head = slot["bolt_head"]
        cutter_target = str(cutter.custom_properties["booleanTarget"])
        head_target = str(head.custom_properties["booleanTarget"])
        if cutter_target != head_target:
            raise ValueError(
                f"ringID={ring_id}, boltIndex={idx}: cutter/head target mismatch"
            )
        operations.extend(
            (
                BoltBooleanOperation(
                    target_name=cutter_target,
                    tool_name=cutter.name,
                    ring_id=ring_id,
                    bolt_index=idx,
                    tool_type="bolt_pocket_cutter",
                    remove_tool_after=True,
                ),
                BoltBooleanOperation(
                    target_name=head_target,
                    tool_name=head.name,
                    ring_id=ring_id,
                    bolt_index=idx,
                    tool_type="bolt_head",
                    remove_tool_after=False,
                ),
            )
        )
    return tuple(operations)


def _apply_boolean_difference(bpy, target, tool, *, modifier_name: str) -> None:
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
    if hasattr(target.data, "validate"):
        target.data.validate(verbose=False)
    if hasattr(target.data, "update"):
        target.data.update(calc_edges=True)


def _apply_stage6_bolt_booleans(bpy, package: ScenePackage) -> tuple[int, tuple[str, ...]]:
    operations = plan_bolt_boolean_operations(package)
    if not operations:
        return 0, ()

    removed: list[str] = []
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
        )
        if op.remove_tool_after:
            mesh = tool.data
            bpy.data.objects.remove(tool, do_unlink=True)
            removed.append(op.tool_name)
            if getattr(mesh, "users", 1) == 0:
                bpy.data.meshes.remove(mesh)

    return len(operations), tuple(removed)


def build_scene_package_in_blender(
    package: ScenePackage,
    *,
    root_collection_name: str = "TunnelScanner",
    clear_existing_root: bool = True,
    validate_mesh: bool = True,
    set_metric_units: bool = True,
    apply_bolt_booleans: bool = True,
) -> BlenderBuildResult:
    bpy = _require_bpy()

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
    for scene_object in package.objects:
        target = _ensure_collection_path(bpy, root, scene_object.collection_path)
        obj = create_blender_object(scene_object, target, validate_mesh=validate_mesh)
        object_names.append(obj.name)
        mesh_names.append(obj.data.name)

    boolean_count = 0
    removed_tools: tuple[str, ...] = ()
    if apply_bolt_booleans:
        boolean_count, removed_tools = _apply_stage6_bolt_booleans(bpy, package)

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
        removed_tool_names=removed_tools,
    )
