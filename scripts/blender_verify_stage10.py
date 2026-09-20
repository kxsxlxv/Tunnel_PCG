"""Real-Blender verifier for the current Stage-10 production scene.

Stage 10 currently means the bounded Stage 10.1 contract: the existing Stage-9
production/chunking architecture plus the Moscow data model, local UGR datum,
R65 running-rail cross-section and gauge placement by inner working faces.
Permanent way, contact rail and Moscow civil shell are intentionally deferred.
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

from tunnel_scanner_core import (
    R65ProductionProfile,
    load_stage10_initial_moscow_profile,
)
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
    parser.add_argument("--root-collection", default="TunnelPCG_Stage10_Verify")
    return parser.parse_args(_argv_after_double_dash())


def _close(a: object, b: float, tol: float = 2e-12) -> bool:
    return math.isclose(float(a), b, abs_tol=tol)


def main() -> None:
    import bpy  # type: ignore

    args = parse_args()
    package = read_scene_package_json(args.scene_json)
    profile = load_stage10_initial_moscow_profile()
    r65 = R65ProductionProfile()
    expected_profile_vertices = len(r65.closed_profile_base_coordinates())

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

    errors: list[str] = []
    production_meta = package.metadata.get("productionGeometry", {})
    if production_meta.get("domainStage") != "10.1":
        errors.append(
            f"domainStage: {production_meta.get('domainStage')!r} != '10.1'"
        )
    if production_meta.get("moscowProfileID") != profile.profile_id:
        errors.append("Moscow profile ID mismatch")
    if (
        production_meta.get("moscowProfileSHA256")
        != profile.provenance.canonical_sha256
    ):
        errors.append("Moscow profile SHA256 mismatch")
    if (
        production_meta.get("railProfile")
        != "stage10_1_r65_gost_r51685_2022"
    ):
        errors.append("production metadata does not select Stage 10.1 R65")
    expected_deferred = {
        "permanentWayStatus": "deferred_to_stage10_2",
        "contactRailStatus": "deferred_to_stage10_3",
        "civilShellStatus": "deferred_to_stage10_4",
    }
    for key, expected in expected_deferred.items():
        if production_meta.get(key) != expected:
            errors.append(f"{key}: {production_meta.get(key)!r} != {expected!r}")

    production = [
        obj
        for obj in package.objects
        if obj.object_type.startswith("production_")
    ]
    if any(obj.object_type.startswith("ancillary_") for obj in package.objects):
        errors.append("ring-local Stage-8 ancillary objects remain in production scene")

    # In Stage 10.1 only the two running rails are replaced by Moscow/R65
    # geometry. These other objects intentionally remain the Stage-8/9
    # transitional baseline until Stage 10.2-10.4.
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

    rails = [o for o in production if o.object_type == "production_rail"]
    working_faces: list[float] = []
    profile_vertex_counts: list[int] = []
    for rail in rails:
        props = rail.custom_properties
        if props.get("railProfile") != "stage10_1_r65_gost_r51685_2022":
            errors.append(f"{rail.name}: wrong rail profile")
        vertices = int(props.get("railProfileVertices", -1))
        profile_vertex_counts.append(vertices)
        if vertices != expected_profile_vertices:
            errors.append(
                f"{rail.name}: R65 profile vertices {vertices} != "
                f"{expected_profile_vertices}"
            )
        dimensional_checks = {
            "railOverallHeightM": 0.180,
            "railNominalHeadWidthM": 0.07459,
            "railWebThicknessM": 0.018,
            "railFootWidthM": 0.150,
            "railTopProfileZLocalM": 0.0,
            "railBaseProfileZLocalM": -0.180,
            "railTopCoreZLocalM": -1.670,
            "railBaseCoreZLocalM": -1.850,
            "railTopZLocalM": -1.670,
            "railBaseZLocalM": -1.850,
            "ugrProfileZLocalM": 0.0,
            "ugrCoreZLocalM": -1.670,
            "ugrZLocalM": -1.670,
            "gaugeM": 1.520,
            "gaugeMeasurementBelowUGRM": 0.013,
            "gaugeMeasurementZLocalM": -0.013,
        }
        for key, expected in dimensional_checks.items():
            if key not in props or not _close(props[key], expected):
                errors.append(
                    f"{rail.name}: {key}={props.get(key)!r} != {expected!r}"
                )
        if props.get("gaugePlacementRule") != (
            "inner_working_faces_at_ugr_minus_13mm"
        ):
            errors.append(f"{rail.name}: wrong gauge placement rule")
        if props.get("moscowProfileID") != profile.profile_id:
            errors.append(f"{rail.name}: Moscow profile ID mismatch")
        if (
            props.get("moscowProfileSHA256")
            != profile.provenance.canonical_sha256
        ):
            errors.append(f"{rail.name}: Moscow profile SHA mismatch")
        try:
            working_faces.append(float(props["railInnerWorkingFaceX"]))
        except (KeyError, TypeError, ValueError):
            errors.append(f"{rail.name}: missing/invalid inner working face")

        blender_obj = bpy.data.objects.get(rail.name)
        if blender_obj is not None:
            if blender_obj.get("railProfile") != "stage10_1_r65_gost_r51685_2022":
                errors.append(f"{rail.name}: Blender railProfile property mismatch")
            if int(blender_obj.get("railProfileVertices", -1)) != expected_profile_vertices:
                errors.append(f"{rail.name}: Blender railProfileVertices mismatch")

    working_face_gauge = None
    if len(working_faces) == 2:
        working_faces.sort()
        working_face_gauge = working_faces[1] - working_faces[0]
        if not math.isclose(
            working_face_gauge,
            profile.track.gauge_m,
            abs_tol=2e-12,
        ):
            errors.append(
                f"working-face gauge {working_face_gauge!r} != "
                f"{profile.track.gauge_m!r}"
            )

    ring_count = int(package.metadata.get("ringCount", 0))
    if ring_count > 1 and result.lining_cap_faces_removed <= 0:
        errors.append("no internal lining cap faces were removed")
    if result.lining_interface_faces_removed <= 0:
        errors.append("no coincident segment-interface faces were removed")

    report = {
        "stage": "10.1",
        "moscowProfileID": profile.profile_id,
        "moscowProfileSHA256": profile.provenance.canonical_sha256,
        "ringCount": ring_count,
        "packageObjectsBeforeBoolean": len(package.objects),
        "survivingObjects": len(result.object_names),
        "productionAssetCounts": actual_counts,
        "railProfile": "stage10_1_r65_gost_r51685_2022",
        "railProfileVertices": (
            profile_vertex_counts[0] if profile_vertex_counts else None
        ),
        "innerWorkingFacesX": working_faces,
        "workingFaceGaugeM": working_face_gauge,
        "ugrProfileZLocalM": profile.datums.ugr_z_m,
        "ugrCoreZLocalM": production_meta.get("ugrCoreZLocalM"),
        "profileZToCoreZOffsetM": production_meta.get("profileZToCoreZOffsetM"),
        "gaugeMeasurementBelowUGRM": profile.track.gauge_measurement_below_ugr_m,
        "booleanOperationsApplied": result.boolean_operations_applied,
        "removedPocketCutters": len(result.removed_tool_names),
        "liningCapFacesRemoved": result.lining_cap_faces_removed,
        "liningInterfaceFacesRemoved": result.lining_interface_faces_removed,
        "permanentWayStatus": production_meta.get("permanentWayStatus"),
        "contactRailStatus": production_meta.get("contactRailStatus"),
        "civilShellStatus": production_meta.get("civilShellStatus"),
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
