"""Real-Blender Stage-9 production geometry verifier."""

from __future__ import annotations

import argparse
import json
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
    parser.add_argument("--root-collection", default="TunnelPCG_Stage9_Verify")
    return parser.parse_args(_argv_after_double_dash())


def main() -> None:
    import bpy  # type: ignore

    args = parse_args()
    package = read_scene_package_json(args.scene_json)
    result = build_scene_package_in_blender(
        package,
        root_collection_name=args.root_collection,
        clear_existing_root=True,
        validate_mesh=True,
        set_metric_units=True,
        apply_bolt_booleans=True,
        strip_internal_lining_caps=True,
        strip_coincident_lining_interfaces=True,
    )

    errors = []
    production = [
        obj
        for obj in package.objects
        if obj.object_type.startswith("production_")
    ]
    if any(obj.object_type.startswith("ancillary_") for obj in package.objects):
        errors.append("ring-local Stage-8 ancillary objects remain in production scene")

    expected_counts = {
        "production_pavement": 1,
        "production_walkway": 1,
        "production_rail": 2,
        "production_tube": 6,
    }
    actual_counts = {
        key: len([obj for obj in production if obj.object_type == key])
        for key in expected_counts
    }
    for key, expected in expected_counts.items():
        if actual_counts[key] != expected:
            errors.append(f"{key}: {actual_counts[key]} != {expected}")

    for scene_object in production:
        obj = bpy.data.objects.get(scene_object.name)
        if obj is None:
            errors.append(f"missing production object {scene_object.name}")
            continue
        if int(obj.get("persistentInstanceID", -1)) != scene_object.instance_id:
            errors.append(f"{scene_object.name}: persistentInstanceID mismatch")

    for rail in [o for o in production if o.object_type == "production_rail"]:
        if int(rail.custom_properties.get("railProfileVertices", -1)) != 16:
            errors.append(f"{rail.name}: rail profile is not 16-vertex production profile")
        if not (
            rail.custom_properties["railWebThicknessM"]
            < rail.custom_properties["railHeadWidthM"]
            < rail.custom_properties["railFootWidthM"]
        ):
            errors.append(f"{rail.name}: invalid head/web/foot width ordering")

    ring_count = int(package.metadata.get("ringCount", 0))
    if ring_count > 1 and result.lining_cap_faces_removed <= 0:
        errors.append("no internal lining cap faces were removed")
    if result.lining_interface_faces_removed <= 0:
        errors.append("no coincident segment-interface faces were removed")

    report = {
        "stage": 9,
        "ringCount": ring_count,
        "packageObjectsBeforeBoolean": len(package.objects),
        "survivingObjects": len(result.object_names),
        "productionAssetCounts": actual_counts,
        "booleanOperationsApplied": result.boolean_operations_applied,
        "removedPocketCutters": len(result.removed_tool_names),
        "liningCapFacesRemoved": result.lining_cap_faces_removed,
        "liningInterfaceFacesRemoved": result.lining_interface_faces_removed,
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
