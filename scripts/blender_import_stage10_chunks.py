from __future__ import annotations

"""Import one, many, or all Stage-10 chunk JSON files into one Blender scene."""

import argparse
import json
from pathlib import Path
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tunnel_scanner_core.blender_adapter import build_scene_package_in_blender
from tunnel_scanner_core.scene_io import read_scene_package_json


def _argv_after_double_dash() -> list[str]:
    if "--" not in sys.argv:
        return []
    return sys.argv[sys.argv.index("--") + 1 :]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("manifest", type=Path)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument("--all", action="store_true")
    selection.add_argument("--chunk", type=int)
    selection.add_argument(
        "--chunk-range",
        help="Python-style half-open chunk range START:END",
    )
    parser.add_argument("--save-blend", type=Path, default=None)
    parser.add_argument("--root-collection", default="TunnelScanner")
    parser.add_argument("--no-bolt-booleans", action="store_true")
    parser.add_argument(
        "--no-batch-bolt-booleans",
        action="store_true",
        help=(
            "Debug/performance comparison: apply each pocket cutter with its "
            "own Boolean modifier instead of batching cutters by lining segment."
        ),
    )
    parser.add_argument(
        "--validate-meshes",
        action="store_true",
        help=(
            "Run Blender Mesh.validate() on every generated object and after "
            "each applied Boolean. Off by default for trusted Tunnel_PCG "
            "ScenePackages because it is costly on multi-chunk imports."
        ),
    )
    parser.add_argument(
        "--fast-route-preview",
        action="store_true",
        help=(
            "Skip bolt-pocket cutter objects and all bolt-pocket Booleans while "
            "keeping visible bolt heads. This preserves route/civil/track "
            "placement but is NOT final LiDAR geometry."
        ),
    )
    parser.add_argument(
        "--keep-internal-lining-caps",
        action="store_true",
    )
    parser.add_argument(
        "--keep-coincident-lining-interfaces",
        action="store_true",
    )
    parser.add_argument(
        "--keep-hidden-lining-extrados",
        action="store_true",
    )
    parser.add_argument(
        "--no-mesh-prototype-reuse",
        action="store_true",
    )
    parser.add_argument(
        "--merge-chunk-by-object-type",
        action="store_true",
        help=(
            "After Boolean/cleanup, merge repeated objects inside each chunk "
            "by objectType/label/semantic class. Recommended for --all."
        ),
    )
    return parser.parse_args(_argv_after_double_dash())


def _selected_entries(manifest: dict, args: argparse.Namespace) -> list[dict]:
    entries = sorted(
        manifest["chunks"],
        key=lambda item: int(item["chunkID"]),
    )
    if args.all:
        return entries
    if args.chunk is not None:
        result = [
            entry
            for entry in entries
            if int(entry["chunkID"]) == args.chunk
        ]
        if not result:
            raise ValueError(f"chunk {args.chunk} not present in manifest")
        return result

    raw = str(args.chunk_range)
    if ":" not in raw:
        raise ValueError("--chunk-range must be START:END")
    start_text, end_text = raw.split(":", 1)
    start = int(start_text)
    end = int(end_text)
    if not 0 <= start < end:
        raise ValueError("--chunk-range must satisfy 0 <= START < END")
    result = [
        entry
        for entry in entries
        if start <= int(entry["chunkID"]) < end
    ]
    if not result:
        raise ValueError("selected chunk range is empty")
    return result


def _restore_chunk_world_origin(bpy, object_names, origin) -> None:
    ox, oy, oz = (float(value) for value in origin)
    if ox == 0.0 and oy == 0.0 and oz == 0.0:
        return
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj is None:
            continue
        obj.location.x += ox
        obj.location.y += oy
        obj.location.z += oz


def _ensure_child_collection(bpy, parent, logical_name: str):
    qualified = f"{parent.name}::{logical_name}"
    collection = bpy.data.collections.get(qualified)
    if collection is None:
        collection = bpy.data.collections.new(qualified)
        collection["logicalName"] = logical_name
    if collection.name not in {child.name for child in parent.children}:
        parent.children.link(collection)
    return collection


def _merge_chunk_objects(
    bpy,
    *,
    root_name: str,
    object_names,
    chunk_id: int,
    section_name: str,
) -> tuple[str, ...]:
    root = bpy.data.collections.get(root_name)
    if root is None:
        raise RuntimeError(f"root collection not found: {root_name}")
    merged_root = _ensure_child_collection(bpy, root, "WholeRouteMerged")
    section = _ensure_child_collection(
        bpy,
        merged_root,
        section_name or "UNRESOLVED_SECTION",
    )
    target = _ensure_child_collection(
        bpy,
        section,
        f"Chunk_{chunk_id:05d}",
    )

    groups = {}
    passthrough = []
    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        object_type = str(obj.get("objectType", "unknown"))
        label_id = str(obj.get("labelID", "0"))
        semantic = str(obj.get("semanticClass", "unknown"))
        key = (object_type, label_id, semantic)
        groups.setdefault(key, []).append(obj)

    surviving = []
    for (object_type, label_id, semantic), objects in groups.items():
        if len(objects) == 1:
            surviving.append(objects[0].name)
            continue

        vertices = []
        faces = []
        for obj in objects:
            matrix = obj.matrix_world
            base = len(vertices)
            vertices.extend(
                tuple(matrix @ vertex.co)
                for vertex in obj.data.vertices
            )
            faces.extend(
                tuple(base + int(index) for index in polygon.vertices)
                for polygon in obj.data.polygons
            )

        mesh_name = (
            f"CH{chunk_id:05d}__MERGED__{object_type}__MESH"
        )
        object_name = f"CH{chunk_id:05d}__MERGED__{object_type}"
        mesh = bpy.data.meshes.new(mesh_name)
        mesh.from_pydata(
            [tuple(float(value) for value in vertex) for vertex in vertices],
            [],
            faces,
        )
        mesh.update(calc_edges=True)
        merged = bpy.data.objects.new(object_name, mesh)
        merged["objectType"] = object_type
        merged["labelID"] = int(label_id)
        merged["semanticClass"] = semantic
        merged["chunkID"] = int(chunk_id)
        merged["mergedSourceObjectCount"] = len(objects)
        merged["mergeMode"] = "post_boolean_chunk_object_type_v1"
        target.objects.link(merged)
        surviving.append(merged.name)

        for obj in objects:
            old_mesh = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if getattr(old_mesh, "users", 1) == 0:
                bpy.data.meshes.remove(old_mesh)

    return tuple(surviving)


def main() -> None:
    args = parse_args()
    manifest_path = args.manifest.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries = _selected_entries(manifest, args)

    import bpy  # type: ignore

    total_boolean = 0
    total_boolean_modifiers = 0
    total_object_creation_seconds = 0.0
    total_boolean_seconds = 0.0
    total_cleanup_seconds = 0.0
    total_caps = 0
    total_interfaces = 0
    total_extrados = 0
    total_mesh_prototype_instances = 0
    shared_mesh_prototypes = (
        None if args.no_mesh_prototype_reuse else {}
    )
    current_names = []
    first = True

    if args.fast_route_preview and args.no_bolt_booleans:
        raise ValueError(
            "--fast-route-preview already disables bolt Booleans; "
            "do not combine it with --no-bolt-booleans"
        )

    wall_started = time.perf_counter()
    print(
        f"Importing {len(entries)} chunks from {manifest_path.name}; "
        f"route={manifest.get('trackID', 'unknown')} "
        f"direction={manifest.get('direction', 'unknown')}"
    )

    for ordinal, entry in enumerate(entries, start=1):
        chunk_id = int(entry["chunkID"])
        chunk_path = manifest_path.parent / str(entry["path"])
        package = read_scene_package_json(chunk_path)
        result = build_scene_package_in_blender(
            package,
            root_collection_name=args.root_collection,
            clear_existing_root=first,
            validate_mesh=args.validate_meshes,
            apply_bolt_booleans=(
                not args.no_bolt_booleans
                and not args.fast_route_preview
            ),
            strip_internal_lining_caps=not args.keep_internal_lining_caps,
            strip_coincident_lining_interfaces=(
                not args.keep_coincident_lining_interfaces
            ),
            strip_hidden_lining_extrados=(
                not args.keep_hidden_lining_extrados
            ),
            reuse_mesh_prototypes=not args.no_mesh_prototype_reuse,
            mesh_prototype_cache=shared_mesh_prototypes,
            batch_bolt_pocket_booleans=(
                not args.no_batch_bolt_booleans
            ),
            omit_bolt_boolean_tools=args.fast_route_preview,
        )
        first = False
        names = tuple(result.object_names)

        if bool(entry.get("vertexCoordinatesLocalized", False)):
            _restore_chunk_world_origin(
                bpy,
                names,
                entry.get("chunkWorldOrigin", (0.0, 0.0, 0.0)),
            )

        if args.merge_chunk_by_object_type:
            names = _merge_chunk_objects(
                bpy,
                root_name=args.root_collection,
                object_names=names,
                chunk_id=chunk_id,
                section_name=str(
                    entry.get(
                        "interstationSection",
                        "UNRESOLVED_SECTION",
                    )
                ),
            )

        current_names.extend(names)
        total_boolean += result.boolean_operations_applied
        total_boolean_modifiers += result.boolean_modifier_applications
        total_object_creation_seconds += result.object_creation_seconds
        total_boolean_seconds += result.boolean_seconds
        total_cleanup_seconds += result.cleanup_seconds
        total_caps += result.lining_cap_faces_removed
        total_interfaces += result.lining_interface_faces_removed
        total_extrados += result.lining_extrados_faces_removed
        total_mesh_prototype_instances += result.mesh_prototype_instance_count

        print(
            f"[{ordinal}/{len(entries)}] chunk {chunk_id:05d}: "
            f"{len(names)} surviving objects, "
            f"{result.boolean_operations_applied} logical pocket cuts in "
            f"{result.boolean_modifier_applications} Boolean modifiers; "
            f"timing create={result.object_creation_seconds:.2f}s, "
            f"boolean={result.boolean_seconds:.2f}s, "
            f"cleanup={result.cleanup_seconds:.2f}s; "
            f"{result.lining_cap_faces_removed} caps, "
            f"{result.lining_interface_faces_removed} interfaces, "
            f"{result.lining_extrados_faces_removed} extrados faces removed"
        )

    root = bpy.data.collections.get(args.root_collection)
    if root is not None:
        root["chunkManifest"] = str(manifest_path)
        root["importedChunkCount"] = len(entries)
        root["trackID"] = str(manifest.get("trackID", ""))
        root["direction"] = str(manifest.get("direction", ""))
        root["routeLengthM"] = float(manifest.get("routeLengthM", 0.0))
        root["runtimeVerticalStatus"] = str(
            manifest.get("runtimeVerticalStatus", "")
        )
        root["mayClaimAsBuilt"] = bool(
            manifest.get("mayClaimAsBuilt", False)
        )
        if shared_mesh_prototypes is not None:
            root["meshPrototypeCount"] = len(shared_mesh_prototypes)
            root["meshPrototypeInstanceCount"] = (
                total_mesh_prototype_instances
            )
            root["sharedMeshDataBlocksSaved"] = max(
                0,
                total_mesh_prototype_instances
                - len(shared_mesh_prototypes),
            )

    wall_seconds = time.perf_counter() - wall_started
    print(
        "Whole-route import complete: "
        f"{len(current_names)} surviving objects; "
        f"{total_boolean} logical pocket cuts in "
        f"{total_boolean_modifiers} Boolean modifiers; "
        f"{total_caps} cap faces, {total_interfaces} interface faces, "
        f"{total_extrados} extrados faces removed. "
        f"Timing totals: create={total_object_creation_seconds:.2f}s, "
        f"boolean={total_boolean_seconds:.2f}s, "
        f"cleanup={total_cleanup_seconds:.2f}s, "
        f"wall={wall_seconds:.2f}s. "
        + (
            f"Shared mesh prototypes: {len(shared_mesh_prototypes)} data blocks "
            f"for {total_mesh_prototype_instances} instances."
            if shared_mesh_prototypes is not None
            else "Shared mesh prototype reuse disabled."
        )
    )

    if args.save_blend is not None:
        output = args.save_blend.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
        print(f"Saved: {output}")


if __name__ == "__main__":
    main()
