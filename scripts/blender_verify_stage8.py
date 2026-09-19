"""Real-Blender verification for Stage-8 ancillary structures.

Example:

    PYTHONPATH=src python examples/generate_stage8_tunnel.py --rings 5
    blender --background --python scripts/blender_verify_stage8.py -- \
        examples/stage8_tunnel_scene.json \
        --report examples/blender_stage8_runtime_report.json \
        --save-blend examples/stage8_tunnel_scene.blend
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
    parser.add_argument("--root-collection", default="TunnelScanner_Stage8_Verify")
    return parser.parse_args(_argv_after_double_dash())


def main() -> None:
    import bpy  # type: ignore
    import bmesh  # type: ignore

    args = parse_args()
    package = read_scene_package_json(args.scene_json)
    result = build_scene_package_in_blender(
        package,
        root_collection_name=args.root_collection,
        clear_existing_root=True,
        validate_mesh=True,
        set_metric_units=True,
        apply_bolt_booleans=True,
    )

    root = bpy.data.collections.get(result.root_collection_name)
    if root is None:
        raise RuntimeError("imported root collection is missing")

    def collect_objects(collection):
        objects = list(collection.objects)
        for child in collection.children:
            objects.extend(collect_objects(child))
        return objects

    imported = collect_objects(root)
    errors: list[str] = []
    stats: dict[str, int] = {}
    ancillary = [
        obj
        for obj in imported
        if str(obj.get("objectType", "")).startswith("ancillary_")
    ]
    for obj in ancillary:
        object_type = str(obj.get("objectType"))
        stats[object_type] = stats.get(object_type, 0) + 1
        if bool(obj.get("followRingAxialRotation", True)):
            errors.append(f"{obj.name}: ancillary unexpectedly follows ring axial rotation")
        if not math.isclose(
            float(obj.get("objectAppliedAxialRotationDeg", 999.0)),
            0.0,
            abs_tol=1e-9,
        ):
            errors.append(f"{obj.name}: applied axial rotation is not zero")

        bm = bmesh.new()
        bm.from_mesh(obj.data)
        non_manifold = sum(1 for edge in bm.edges if not edge.is_manifold)
        volume = float(bm.calc_volume(signed=True))
        bm.free()
        if non_manifold:
            errors.append(f"{obj.name}: {non_manifold} non-manifold edges")
        if not math.isfinite(volume) or volume <= 0.0:
            errors.append(f"{obj.name}: non-positive volume {volume}")

        label = int(obj.get("labelID", -1))
        if package.label_policy.value == "stsd_coarse":
            if object_type == "ancillary_walkway" and label != 2:
                errors.append(f"{obj.name}: STSD walkway label {label} != 2")
            elif object_type == "ancillary_tube" and label != 3:
                errors.append(f"{obj.name}: STSD tube label {label} != 3")
            elif object_type in {"ancillary_pavement", "ancillary_rail"} and label != 0:
                errors.append(f"{obj.name}: STSD clutter ancillary label {label} != 0")
        elif label != 0:
            errors.append(f"{obj.name}: Seg2Tunnel ancillary label {label} != 0")

    ring_count = int(package.metadata.get("ringCount", len(package.ring_ids)))
    expected = {
        "ancillary_pavement": ring_count,
        "ancillary_walkway": ring_count,
        "ancillary_rail": 2 * ring_count,
        "ancillary_tube": 6 * ring_count,
    }
    for object_type, count in expected.items():
        if stats.get(object_type, 0) != count:
            errors.append(
                f"{object_type}: Blender count {stats.get(object_type,0)} != expected {count}"
            )

    report = {
        "stage": 8,
        "ringCount": ring_count,
        "labelPolicy": package.label_policy.value,
        "packageObjects": len(package.objects),
        "survivingObjects": len(result.object_names),
        "ancillaryObjects": len(ancillary),
        "ancillaryCounts": stats,
        "booleanOperationsApplied": result.boolean_operations_applied,
        "removedPocketCutters": len(result.removed_tool_names),
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
