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


def build_scene_package_in_blender(
    package: ScenePackage,
    *,
    root_collection_name: str = "TunnelScanner",
    clear_existing_root: bool = True,
    validate_mesh: bool = True,
    set_metric_units: bool = True,
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

    return BlenderBuildResult(
        root_collection_name=root.name,
        object_names=tuple(object_names),
        mesh_names=tuple(mesh_names),
    )
