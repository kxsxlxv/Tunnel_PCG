"""Polygon/mesh budget profiler for Stage-10 ScenePackage JSON.

Run from the repository root inside Blender, for example:

    blender --background --python scripts/blender_profile_stage10.py -- \
        examples/stage10_production_scene_rc6100_kba_chunks/chunk_00100.json \
        --report examples/stage10_chunk_00100_polygon_profile.json \
        --save-blend examples/stage10_chunk_00100_profiled.blend

The default build matches the production Blender verification path:
bolt Booleans are applied, hidden internal lining caps are stripped, exact
coincident lining interfaces are stripped, and translation-only mesh
prototypes are reused.

The report deliberately separates logical geometry from unique mesh-data
geometry.  Repeated prototype instances still contribute to logical viewport /
sensor geometry even though Blender stores a shared mesh datablock for them.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
from pathlib import Path
import sys
from typing import Any, Iterable


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
    parser = argparse.ArgumentParser(
        description=(
            "Profile Stage-10 polygon/vertex cost by objectType before and "
            "after Blender Boolean/cleanup processing."
        )
    )
    parser.add_argument("scene_json", type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--save-blend", type=Path, default=None)
    parser.add_argument(
        "--root-collection",
        default="TunnelPCG_Stage10_Profile",
    )
    parser.add_argument(
        "--no-bolt-booleans",
        action="store_true",
        help="Do not apply bolt pocket/head Boolean operations.",
    )
    parser.add_argument(
        "--keep-internal-lining-caps",
        action="store_true",
        help="Keep hidden internal lining end-cap faces.",
    )
    parser.add_argument(
        "--keep-coincident-lining-interfaces",
        action="store_true",
        help="Keep exact coincident segment-interface faces.",
    )
    parser.add_argument(
        "--keep-hidden-lining-extrados",
        action="store_true",
        help="Keep the hidden outer RC lining surface after bolt Booleans.",
    )
    parser.add_argument(
        "--no-mesh-prototype-reuse",
        action="store_true",
        help="Disable Blender mesh-datablock reuse for declared prototypes.",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=0,
        help="Print only the top N final object types by logical polygons; 0 prints all.",
    )
    return parser.parse_args(_argv_after_double_dash())


def _new_bucket() -> dict[str, Any]:
    return {
        "objects": 0,
        "logicalVertices": 0,
        "logicalPolygons": 0,
        "logicalTriangles": 0,
        "uniqueMeshDataBlocks": 0,
        "uniqueMeshVertices": 0,
        "uniqueMeshPolygons": 0,
        "uniqueMeshTriangles": 0,
        "prototypeInstances": 0,
        "prototypeKeys": 0,
    }


def _triangles_from_faces(faces: Iterable[Iterable[int]]) -> int:
    total = 0
    for face in faces:
        n = len(face)  # tuple/list in SceneObject
        if n >= 3:
            total += n - 2
    return total


def _profile_scene_package(package) -> dict[str, Any]:
    by_type: dict[str, dict[str, Any]] = defaultdict(_new_bucket)
    global_unique_meshes: dict[tuple[str, str], tuple[int, int, int]] = {}
    prototype_keys_by_type: dict[str, set[str]] = defaultdict(set)
    objects_by_type: dict[str, list[Any]] = defaultdict(list)

    for obj in package.objects:
        object_type = str(obj.object_type)
        bucket = by_type[object_type]
        objects_by_type[object_type].append(obj)
        vertices = len(obj.vertices)
        polygons = len(obj.faces)
        triangles = _triangles_from_faces(obj.faces)

        bucket["objects"] += 1
        bucket["logicalVertices"] += vertices
        bucket["logicalPolygons"] += polygons
        bucket["logicalTriangles"] += triangles

        prototype_key = obj.extra_properties.get("meshPrototypeKey")
        if prototype_key is None:
            mesh_key = ("object", obj.name)
        else:
            prototype_key = str(prototype_key)
            mesh_key = ("prototype", prototype_key)
            bucket["prototypeInstances"] += 1
            prototype_keys_by_type[object_type].add(prototype_key)

        if mesh_key not in global_unique_meshes:
            global_unique_meshes[mesh_key] = (vertices, polygons, triangles)

    # A prototype key is expected to stay within one semantic object type, but
    # calculate per-type unique geometry independently so the report stays
    # useful even if that invariant changes later.
    for object_type, objects in objects_by_type.items():
        bucket = by_type[str(object_type)]
        seen: set[tuple[str, str]] = set()
        for obj in objects:
            prototype_key = obj.extra_properties.get("meshPrototypeKey")
            mesh_key = (
                ("object", obj.name)
                if prototype_key is None
                else ("prototype", str(prototype_key))
            )
            if mesh_key in seen:
                continue
            seen.add(mesh_key)
            bucket["uniqueMeshDataBlocks"] += 1
            bucket["uniqueMeshVertices"] += len(obj.vertices)
            bucket["uniqueMeshPolygons"] += len(obj.faces)
            bucket["uniqueMeshTriangles"] += _triangles_from_faces(obj.faces)
        bucket["prototypeKeys"] = len(prototype_keys_by_type[object_type])

    totals = _new_bucket()
    totals["objects"] = len(package.objects)
    totals["logicalVertices"] = sum(v["logicalVertices"] for v in by_type.values())
    totals["logicalPolygons"] = sum(v["logicalPolygons"] for v in by_type.values())
    totals["logicalTriangles"] = sum(v["logicalTriangles"] for v in by_type.values())
    totals["uniqueMeshDataBlocks"] = len(global_unique_meshes)
    totals["uniqueMeshVertices"] = sum(v[0] for v in global_unique_meshes.values())
    totals["uniqueMeshPolygons"] = sum(v[1] for v in global_unique_meshes.values())
    totals["uniqueMeshTriangles"] = sum(v[2] for v in global_unique_meshes.values())
    totals["prototypeInstances"] = sum(v["prototypeInstances"] for v in by_type.values())
    totals["prototypeKeys"] = len(
        {
            str(obj.extra_properties["meshPrototypeKey"])
            for obj in package.objects
            if obj.extra_properties.get("meshPrototypeKey") is not None
        }
    )

    return {
        "totals": totals,
        "byObjectType": {
            key: dict(value)
            for key, value in sorted(by_type.items())
        },
    }


def _mesh_counts(mesh) -> tuple[int, int, int]:
    vertices = len(mesh.vertices)
    polygons = len(mesh.polygons)
    mesh.calc_loop_triangles()
    triangles = len(mesh.loop_triangles)
    return vertices, polygons, triangles


def _profile_blender_objects(bpy, object_names: Iterable[str]) -> dict[str, Any]:
    by_type: dict[str, dict[str, Any]] = defaultdict(_new_bucket)
    per_type_seen_meshes: dict[str, set[str]] = defaultdict(set)
    global_seen_meshes: set[str] = set()
    global_unique_counts: dict[str, tuple[int, int, int]] = {}
    prototype_keys_by_type: dict[str, set[str]] = defaultdict(set)
    mesh_count_cache: dict[str, tuple[int, int, int]] = {}

    for name in object_names:
        obj = bpy.data.objects.get(name)
        if obj is None or getattr(obj, "type", None) != "MESH":
            continue
        mesh = obj.data
        object_type = str(obj.get("objectType", "<missing>"))
        mesh_key = str(mesh.name)
        counts = mesh_count_cache.get(mesh_key)
        if counts is None:
            counts = _mesh_counts(mesh)
            mesh_count_cache[mesh_key] = counts
        vertices, polygons, triangles = counts
        bucket = by_type[object_type]

        bucket["objects"] += 1
        bucket["logicalVertices"] += vertices
        bucket["logicalPolygons"] += polygons
        bucket["logicalTriangles"] += triangles

        prototype_key = obj.get("meshPrototypeKey")
        if prototype_key is not None:
            bucket["prototypeInstances"] += 1
            prototype_keys_by_type[object_type].add(str(prototype_key))

        if mesh_key not in per_type_seen_meshes[object_type]:
            per_type_seen_meshes[object_type].add(mesh_key)
            bucket["uniqueMeshDataBlocks"] += 1
            bucket["uniqueMeshVertices"] += vertices
            bucket["uniqueMeshPolygons"] += polygons
            bucket["uniqueMeshTriangles"] += triangles

        if mesh_key not in global_seen_meshes:
            global_seen_meshes.add(mesh_key)
            global_unique_counts[mesh_key] = (vertices, polygons, triangles)

    for object_type, keys in prototype_keys_by_type.items():
        by_type[object_type]["prototypeKeys"] = len(keys)

    totals = _new_bucket()
    totals["objects"] = sum(v["objects"] for v in by_type.values())
    totals["logicalVertices"] = sum(v["logicalVertices"] for v in by_type.values())
    totals["logicalPolygons"] = sum(v["logicalPolygons"] for v in by_type.values())
    totals["logicalTriangles"] = sum(v["logicalTriangles"] for v in by_type.values())
    totals["uniqueMeshDataBlocks"] = len(global_unique_counts)
    totals["uniqueMeshVertices"] = sum(v[0] for v in global_unique_counts.values())
    totals["uniqueMeshPolygons"] = sum(v[1] for v in global_unique_counts.values())
    totals["uniqueMeshTriangles"] = sum(v[2] for v in global_unique_counts.values())
    totals["prototypeInstances"] = sum(v["prototypeInstances"] for v in by_type.values())
    totals["prototypeKeys"] = len(
        {key for keys in prototype_keys_by_type.values() for key in keys}
    )

    return {
        "totals": totals,
        "byObjectType": {
            key: dict(value)
            for key, value in sorted(by_type.items())
        },
    }


def _build_delta(
    input_profile: dict[str, Any],
    final_profile: dict[str, Any],
) -> dict[str, dict[str, int]]:
    before = input_profile["byObjectType"]
    after = final_profile["byObjectType"]
    keys = sorted(set(before) | set(after))
    result: dict[str, dict[str, int]] = {}
    for key in keys:
        b = before.get(key, _new_bucket())
        a = after.get(key, _new_bucket())
        result[key] = {
            "objects": int(a["objects"] - b["objects"]),
            "logicalVertices": int(a["logicalVertices"] - b["logicalVertices"]),
            "logicalPolygons": int(a["logicalPolygons"] - b["logicalPolygons"]),
            "logicalTriangles": int(a["logicalTriangles"] - b["logicalTriangles"]),
            "uniqueMeshDataBlocks": int(
                a["uniqueMeshDataBlocks"] - b["uniqueMeshDataBlocks"]
            ),
            "uniqueMeshVertices": int(
                a["uniqueMeshVertices"] - b["uniqueMeshVertices"]
            ),
            "uniqueMeshPolygons": int(
                a["uniqueMeshPolygons"] - b["uniqueMeshPolygons"]
            ),
            "uniqueMeshTriangles": int(
                a["uniqueMeshTriangles"] - b["uniqueMeshTriangles"]
            ),
        }
    return result


def _fmt_int(value: int) -> str:
    return f"{int(value):,}".replace(",", " ")


def _print_summary(
    input_profile: dict[str, Any],
    final_profile: dict[str, Any],
    delta: dict[str, dict[str, int]],
    *,
    top: int,
) -> None:
    inp = input_profile["totals"]
    fin = final_profile["totals"]
    print("")
    print("Stage-10 polygon budget")
    print("=" * 100)
    print(
        "Input ScenePackage : "
        f"{_fmt_int(inp['objects'])} objects, "
        f"{_fmt_int(inp['logicalVertices'])} logical vertices, "
        f"{_fmt_int(inp['logicalPolygons'])} logical polygons, "
        f"{_fmt_int(inp['logicalTriangles'])} logical triangles"
    )
    print(
        "Final Blender      : "
        f"{_fmt_int(fin['objects'])} objects, "
        f"{_fmt_int(fin['logicalVertices'])} logical vertices, "
        f"{_fmt_int(fin['logicalPolygons'])} logical polygons, "
        f"{_fmt_int(fin['logicalTriangles'])} logical triangles"
    )
    print(
        "Unique Blender mesh: "
        f"{_fmt_int(fin['uniqueMeshDataBlocks'])} datablocks, "
        f"{_fmt_int(fin['uniqueMeshVertices'])} vertices, "
        f"{_fmt_int(fin['uniqueMeshPolygons'])} polygons, "
        f"{_fmt_int(fin['uniqueMeshTriangles'])} triangles"
    )
    logical = max(1, int(fin["logicalPolygons"]))

    rows = sorted(
        final_profile["byObjectType"].items(),
        key=lambda item: (
            -int(item[1]["logicalPolygons"]),
            item[0],
        ),
    )
    # Types removed entirely by the build (notably bolt cutters) are useful in
    # the table too, so append them after surviving contributors.
    surviving = {name for name, _ in rows}
    removed = [
        (name, _new_bucket())
        for name in input_profile["byObjectType"]
        if name not in surviving
    ]
    rows.extend(sorted(removed, key=lambda item: item[0]))
    if top > 0:
        rows = rows[:top]

    print("")
    print(
        f"{'objectType':48} {'objs':>7} {'verts':>11} {'polys':>11} "
        f"{'tris':>11} {'share':>7} {'poly Δ':>11}"
    )
    print("-" * 115)
    for object_type, stats in rows:
        polygons = int(stats["logicalPolygons"])
        share = 100.0 * polygons / logical
        d = delta.get(object_type, {}).get("logicalPolygons", 0)
        print(
            f"{object_type[:48]:48} "
            f"{_fmt_int(stats['objects']):>7} "
            f"{_fmt_int(stats['logicalVertices']):>11} "
            f"{_fmt_int(polygons):>11} "
            f"{_fmt_int(stats['logicalTriangles']):>11} "
            f"{share:6.2f}% "
            f"{int(d):+11,d}".replace(",", " ")
        )


def main() -> None:
    import bpy  # type: ignore

    args = parse_args()
    if args.top < 0:
        raise SystemExit("--top must be >= 0")

    scene_path = args.scene_json.resolve()
    package = read_scene_package_json(scene_path)
    input_profile = _profile_scene_package(package)

    result = build_scene_package_in_blender(
        package,
        root_collection_name=args.root_collection,
        clear_existing_root=True,
        validate_mesh=True,
        set_metric_units=True,
        apply_bolt_booleans=not args.no_bolt_booleans,
        strip_internal_lining_caps=not args.keep_internal_lining_caps,
        strip_coincident_lining_interfaces=(
            not args.keep_coincident_lining_interfaces
        ),
        strip_hidden_lining_extrados=(
            not args.keep_hidden_lining_extrados
        ),
        reuse_mesh_prototypes=not args.no_mesh_prototype_reuse,
    )
    final_profile = _profile_blender_objects(bpy, result.object_names)
    delta = _build_delta(input_profile, final_profile)

    report = {
        "schemaVersion": 1,
        "sceneJson": str(scene_path),
        "scenePackageName": package.name,
        "settings": {
            "applyBoltBooleans": not args.no_bolt_booleans,
            "stripInternalLiningCaps": not args.keep_internal_lining_caps,
            "stripCoincidentLiningInterfaces": (
                not args.keep_coincident_lining_interfaces
            ),
            "stripHiddenLiningExtrados": (
                not args.keep_hidden_lining_extrados
            ),
            "reuseMeshPrototypes": not args.no_mesh_prototype_reuse,
        },
        "inputScenePackage": input_profile,
        "finalBlenderScene": final_profile,
        "deltaByObjectType": delta,
        "blenderBuild": {
            "rootCollectionName": result.root_collection_name,
            "booleanLogicalOperations": result.boolean_operations_applied,
            "booleanModifierApplications": result.boolean_modifier_applications,
            "boltBooleanBatchingEnabled": result.bolt_boolean_batching_enabled,
            "removedToolCount": len(result.removed_tool_names),
            "liningCapFacesRemoved": result.lining_cap_faces_removed,
            "liningInterfaceFacesRemoved": result.lining_interface_faces_removed,
            "liningExtradosFacesRemoved": result.lining_extrados_faces_removed,
            "meshPrototypeCount": result.mesh_prototype_count,
            "meshPrototypeInstanceCount": result.mesh_prototype_instance_count,
            "sharedMeshDataBlocksSaved": result.shared_mesh_data_blocks_saved,
            "objectCreationSeconds": result.object_creation_seconds,
            "booleanSeconds": result.boolean_seconds,
            "cleanupSeconds": result.cleanup_seconds,
        },
    }

    _print_summary(
        input_profile,
        final_profile,
        delta,
        top=args.top,
    )
    print("")
    print(
        "Cleanup: "
        f"{result.boolean_operations_applied} logical Boolean cuts in "
        f"{result.boolean_modifier_applications} modifiers, "
        f"{len(result.removed_tool_names)} cutters removed, "
        f"{result.lining_cap_faces_removed} lining-cap faces removed, "
        f"{result.lining_interface_faces_removed} coincident interface faces removed, "
        f"{result.lining_extrados_faces_removed} hidden extrados faces removed; "
        f"timing create={result.object_creation_seconds:.2f}s, "
        f"boolean={result.boolean_seconds:.2f}s, "
        f"cleanup={result.cleanup_seconds:.2f}s"
    )
    print(
        "Prototype reuse: "
        f"{result.mesh_prototype_count} prototypes, "
        f"{result.mesh_prototype_instance_count} instances, "
        f"{result.shared_mesh_data_blocks_saved} mesh datablocks saved"
    )

    report_path = (
        args.report.resolve()
        if args.report is not None
        else scene_path.with_name(scene_path.stem + "_polygon_profile.json")
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Report: {report_path}")

    if args.save_blend is not None:
        output = args.save_blend.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output))
        print(f"Saved: {output}")


if __name__ == "__main__":
    main()
