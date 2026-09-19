"""Real-Blender verification for a Stage-7 multi-ring ScenePackage.

Recommended quick smoke test:

    PYTHONPATH=src python examples/generate_stage7_tunnel.py --rings 5
    blender --background --python scripts/blender_verify_stage7.py -- \
        examples/stage7_tunnel_scene.json \
        --report examples/blender_stage7_runtime_report.json \
        --save-blend examples/stage7_tunnel_scene.blend
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
    parser.add_argument("--root-collection", default="TunnelScanner_Stage7_Verify")
    parser.add_argument("--no-booleans", action="store_true")
    return parser.parse_args(_argv_after_double_dash())


def main() -> None:
    import bpy  # type: ignore
    import bmesh  # type: ignore

    args = parse_args()
    package = read_scene_package_json(args.scene_json)
    ring_count = int(package.metadata.get("ringCount", 0))
    ring_width = float(package.metadata.get("ringWidthM", 0.0))
    heads = [o for o in package.objects if o.object_type == "bolt_head"]
    cutters = [o for o in package.objects if o.object_type == "bolt_pocket_cutter"]

    result = build_scene_package_in_blender(
        package,
        root_collection_name=args.root_collection,
        clear_existing_root=True,
        validate_mesh=True,
        set_metric_units=True,
        apply_bolt_booleans=not args.no_booleans,
    )

    root = bpy.data.collections.get(result.root_collection_name)
    if root is None:
        raise RuntimeError(
            f"missing imported root collection {result.root_collection_name!r}"
        )

    def collect_objects(collection):
        found = list(collection.objects)
        for child in collection.children:
            found.extend(collect_objects(child))
        return found

    imported_objects = collect_objects(root)
    errors: list[str] = []
    ring_stats: list[dict] = []
    for ring_id in range(ring_count):
        ring_objects = [
            obj for obj in imported_objects if int(obj.get("ringID", -1)) == ring_id
        ]
        if not ring_objects:
            errors.append(f"ring {ring_id}: no Blender objects")
            continue
        expected_y = ring_id * ring_width
        lining = [obj for obj in ring_objects if obj.get("objectType") == "lining_segment"]
        if len(lining) != 6:
            errors.append(f"ring {ring_id}: lining segment count {len(lining)} != 6")
        non_manifold_total = 0
        for obj in lining:
            if not math.isclose(
                float(obj.get("ringChainageM", -999)),
                expected_y,
                abs_tol=1e-9,
            ):
                errors.append(f"{obj.name}: wrong ringChainageM")
            if not args.no_booleans:
                bm = bmesh.new()
                bm.from_mesh(obj.data)
                non_manifold_total += sum(1 for edge in bm.edges if not edge.is_manifold)
                volume = float(bm.calc_volume(signed=True))
                bm.free()
                if not math.isfinite(volume) or volume <= 0.0:
                    errors.append(f"{obj.name}: non-positive signed volume {volume}")
        if non_manifold_total:
            errors.append(
                f"ring {ring_id}: {non_manifold_total} non-manifold lining edges"
            )
        ring_stats.append(
            {
                "ringID": ring_id,
                "objects": len(ring_objects),
                "liningSegments": len(lining),
                "expectedChainageM": expected_y,
                "nonManifoldLiningEdges": non_manifold_total,
            }
        )

    if not args.no_booleans and heads:
        expected_ops = 2 * len(heads)
        if result.boolean_operations_applied != expected_ops:
            errors.append(
                f"Boolean operation count {result.boolean_operations_applied} != {expected_ops}"
            )
        if len(result.removed_tool_names) != len(cutters):
            errors.append(
                f"removed cutters {len(result.removed_tool_names)} != {len(cutters)}"
            )
        for cutter in cutters:
            if bpy.data.objects.get(cutter.name) is not None:
                errors.append(f"cutter survived: {cutter.name}")

    report = {
        "stage": 7,
        "ringCount": ring_count,
        "packageObjects": len(package.objects),
        "survivingObjects": len(result.object_names),
        "boltHeads": len(heads),
        "boltPocketCutters": len(cutters),
        "booleansEnabled": not args.no_booleans,
        "booleanOperationsApplied": result.boolean_operations_applied,
        "removedPocketCutters": len(result.removed_tool_names),
        "rings": ring_stats,
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
