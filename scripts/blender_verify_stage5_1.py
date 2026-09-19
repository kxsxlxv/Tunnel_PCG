"""Runtime smoke verifier for a Stage-5.1 scene inside a real Blender build.

Example:

    blender --background --python scripts/blender_verify_stage5_1.py -- \
        examples/stage5_1_nominal_scene.json

The verifier imports the package with the production adapter, then compares the
actual Blender mesh/object data against the engine-neutral package.
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
    parser.add_argument("--root-collection", default="TunnelScanner_Stage5_1_Verify")
    parser.add_argument("--report", type=Path, default=None)
    return parser.parse_args(_argv_after_double_dash())


def _equal_property(actual, expected) -> bool:
    if isinstance(expected, float):
        return math.isclose(float(actual), expected, rel_tol=0.0, abs_tol=1e-9)
    return actual == expected


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
    )

    errors: list[str] = []
    lining_counts: list[dict[str, int | str]] = []

    if len(result.object_names) != len(package.objects):
        errors.append(
            f"object count mismatch: Blender={len(result.object_names)} package={len(package.objects)}"
        )

    for source in package.objects:
        obj = bpy.data.objects.get(source.name)
        if obj is None:
            errors.append(f"missing Blender object: {source.name}")
            continue
        if obj.type != "MESH":
            errors.append(f"{source.name}: expected MESH, got {obj.type}")
            continue
        if len(obj.data.vertices) != len(source.vertices):
            errors.append(
                f"{source.name}: vertex count {len(obj.data.vertices)} != {len(source.vertices)}"
            )
        if len(obj.data.polygons) != len(source.faces):
            errors.append(
                f"{source.name}: polygon count {len(obj.data.polygons)} != {len(source.faces)}"
            )

        for key, expected in source.custom_properties.items():
            if key not in obj:
                errors.append(f"{source.name}: missing custom property {key}")
                continue
            if not _equal_property(obj[key], expected):
                errors.append(
                    f"{source.name}: property {key}={obj[key]!r} != {expected!r}"
                )

        if source.object_type == "lining_segment":
            lining_counts.append(
                {
                    "name": source.name,
                    "vertices": len(obj.data.vertices),
                    "faces": len(obj.data.polygons),
                }
            )
            if len(obj.data.vertices) <= 8:
                errors.append(
                    f"{source.name}: still has <=8 vertices; curved Stage-5.1 mesh was not imported"
                )

    units = bpy.context.scene.unit_settings
    if units.system != "METRIC":
        errors.append(f"scene units are {units.system!r}, expected METRIC")
    if not math.isclose(float(units.scale_length), 1.0, abs_tol=1e-12):
        errors.append(f"scene scale_length={units.scale_length}, expected 1.0")

    report = {
        "stage": "5.1",
        "scene": package.name,
        "objects": len(package.objects),
        "liningSegments": lining_counts,
        "metricUnits": units.system == "METRIC",
        "scaleLength": float(units.scale_length),
        "errors": errors,
        "result": "PASS" if not errors else "FAIL",
    }

    encoded = json.dumps(report, indent=2)
    print(encoded)
    if args.report is not None:
        path = args.report.resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(encoded + "\n", encoding="utf-8")

    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
