"""Real-Blender verification for Stage-6 bolt Boolean geometry.

Usage:
    blender --background --python scripts/blender_verify_stage6.py -- \
        examples/stage6_nominal_bolts_scene.json \
        --report examples/blender_stage6_runtime_report.json \
        --save-blend examples/stage6_nominal_bolts_scene.blend
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


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
    parser.add_argument("scene_json", type=Path)
    parser.add_argument("--report", type=Path, default=None)
    parser.add_argument("--save-blend", type=Path, default=None)
    parser.add_argument("--root-collection", default="TunnelScanner_Stage6_Verify")
    return parser.parse_args(_argv_after_double_dash())


def main() -> None:
    import bpy  # type: ignore
    import bmesh  # type: ignore

    args = parse_args()
    package = read_scene_package_json(args.scene_json)
    pre_segments = {
        o.name: (len(o.vertices), len(o.faces))
        for o in package.objects
        if o.object_type == "lining_segment"
    }
    expected_cutters = [o for o in package.objects if o.object_type == "bolt_pocket_cutter"]
    expected_heads = [o for o in package.objects if o.object_type == "bolt_head"]

    result = build_scene_package_in_blender(
        package,
        root_collection_name=args.root_collection,
        clear_existing_root=True,
        validate_mesh=True,
        set_metric_units=True,
        apply_bolt_booleans=True,
    )

    errors: list[str] = []
    segment_stats: list[dict] = []
    if result.boolean_operations_applied != 2 * len(expected_heads):
        errors.append(
            f"boolean count={result.boolean_operations_applied}, expected={2*len(expected_heads)}"
        )
    if len(result.removed_tool_names) != len(expected_cutters):
        errors.append(
            f"removed cutters={len(result.removed_tool_names)}, expected={len(expected_cutters)}"
        )

    for cutter in expected_cutters:
        if bpy.data.objects.get(cutter.name) is not None:
            errors.append(f"cutter survived Boolean pipeline: {cutter.name}")

    for head in expected_heads:
        obj = bpy.data.objects.get(head.name)
        if obj is None:
            errors.append(f"missing bolt head: {head.name}")
            continue
        if int(obj.get("labelID", -1)) != 0:
            errors.append(f"bolt head labelID != 0: {head.name}")

    for name, (pre_v, pre_f) in pre_segments.items():
        obj = bpy.data.objects.get(name)
        if obj is None:
            errors.append(f"missing lining segment after Boolean: {name}")
            continue
        post_v = len(obj.data.vertices)
        post_f = len(obj.data.polygons)
        if post_v == pre_v and post_f == pre_f:
            errors.append(f"segment topology unchanged after bolt Booleans: {name}")

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
        volume = float(bm.calc_volume(signed=True))
        bm.free()
        if non_manifold:
            errors.append(f"{name}: {non_manifold} non-manifold edges after Boolean")
        if not math.isfinite(volume) or volume <= 0.0:
            errors.append(f"{name}: non-positive signed volume {volume}")
        segment_stats.append(
            {
                "name": name,
                "preVertices": pre_v,
                "preFaces": pre_f,
                "postVertices": post_v,
                "postFaces": post_f,
                "nonManifoldEdges": non_manifold,
                "signedVolumeM3": volume,
            }
        )

    report = {
        "stage": 6,
        "packageObjectsBeforeBoolean": len(package.objects),
        "survivingObjects": len(result.object_names),
        "boltHeads": len(expected_heads),
        "removedPocketCutters": len(result.removed_tool_names),
        "booleanOperationsApplied": result.boolean_operations_applied,
        "segments": segment_stats,
        "errors": errors,
        "result": "PASS" if not errors else "FAIL",
    }
    encoded = json.dumps(report, indent=2)
    print(encoded)

    if args.report is not None:
        path = args.report.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded + "\n", encoding="utf-8")

    if args.save_blend is not None:
        output = args.save_blend.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=str(output))

    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
