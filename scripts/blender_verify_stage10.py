"""Real-Blender verifier for the current Stage-10 production scene.

The verifier is stage-aware for Moscow Stage 10.1 through 10.5. Stage 10.5
keeps the Stage-10.4 civil shell/walkway and makes the modern Moscow service
preset the default: LVT-M/APC-4 permanent way, segmented low protective cover,
dedicated contact-rail supports, and R2K11 wall cable racks. The Stage-10.5
legacy preset remains selectable for timber/KD-65 compatibility.
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
    production_meta = package.metadata.get("productionGeometry", {})
    civil_family = str(
        production_meta.get("civilArchetypeID", "CAST_IRON_5500_R1000")
    )
    civil_archetype = (
        "rc_block_6100_5600"
        if civil_family == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
        else "cast_iron_5500_5100"
    )
    profile = load_stage10_initial_moscow_profile(
        civil_archetype=civil_archetype
    )
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
    domain_stage = str(production_meta.get("domainStage", ""))
    if domain_stage not in {"10.1", "10.2", "10.3", "10.4", "10.5"}:
        errors.append(
            f"unsupported/missing Moscow domainStage: {domain_stage!r}"
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
    service_preset = str(production_meta.get("servicePreset", "legacy"))
    modern_10_5 = domain_stage == "10.5" and service_preset == "modern"
    legacy_10_5 = domain_stage == "10.5" and service_preset == "legacy"
    expected_status = {
        "permanentWayStatus": (
            "implemented_stage10_5_modern_LVT_M_APC4"
            if modern_10_5
            else (
                "implemented_stage10_2_initial_geometry"
                if domain_stage in {"10.2", "10.3", "10.4"} or legacy_10_5
                else "deferred_to_stage10_2"
            )
        ),
        "contactRailStatus": (
            "implemented_stage10_5_modern_segmented_cover_and_dedicated_support"
            if modern_10_5
            else (
                "implemented_stage10_3_initial_geometry_with_explicit_fallbacks"
                if domain_stage in {"10.3", "10.4"} or legacy_10_5
                else "deferred_to_stage10_3"
            )
        ),
        "civilShellStatus": (
            "implemented_stage10_4_smooth_concentric_shell"
            if domain_stage in {"10.4", "10.5"}
            else "deferred_to_stage10_4"
        ),
    }
    for key, expected in expected_status.items():
        if production_meta.get(key) != expected:
            errors.append(f"{key}: {production_meta.get(key)!r} != {expected!r}")

    production = [
        obj
        for obj in package.objects
        if obj.object_type.startswith("production_")
    ]
    if any(obj.object_type.startswith("ancillary_") for obj in package.objects):
        errors.append("ring-local Stage-8 ancillary objects remain in production scene")

    if modern_10_5:
        lvt_count = int(production_meta.get("modernLVTSupportCount", 0))
        support_count = int(production_meta.get("contactRailSupportCount", 0))
        civil_count = int(production_meta.get("moscowCivilRingCount", 0))
        expected_counts = {
            "production_pavement": 0,
            "production_track_concrete": 1,
            "production_walkway": 0,
            "production_moscow_walkway": 1,
            "production_rail": 2,
            "production_tube": 0,
            "production_sleeper": 0,
            "production_baseplate": 0,
            "production_lvt_block": lvt_count,
            "production_lvt_rubber_boot": lvt_count,
            "production_apc4_rail_pad": lvt_count,
            "production_apc4_fastening": lvt_count,
            "production_contact_rail": 1,
            "production_contact_rail_cover": 0,
            "production_contact_rail_cover_span": int(
                production_meta.get("contactRailCoverSpanCount", 0)
            ),
            "production_contact_rail_support_block": support_count,
            "production_contact_rail_base_plate": support_count,
            "production_contact_rail_bracket": support_count,
            "production_contact_rail_insulator": support_count,
            "production_contact_rail_fastening_unit": support_count,
            "production_contact_rail_clamp_bolts": support_count,
            "production_contact_rail_attachment_dowels": support_count,
            "production_contact_rail_support_hood": support_count,
            "production_service_cable": 16,
            "production_water_main": 1,
            "production_water_main_support": int(
                production_meta.get("serviceWaterMainSupportCount", 0)
            ),
            "production_cable_rack_r2k11": int(
                production_meta.get("serviceCableRackCount", 0)
            ),
            "production_moscow_civil_shell_ring": civil_count,
        }
    elif domain_stage in {"10.2", "10.3", "10.4"} or legacy_10_5:
        sleeper_count = int(production_meta.get("sleeperCount", 0))
        expected_counts = {
            "production_pavement": 0,
            "production_track_concrete": 1,
            "production_walkway": 0 if domain_stage in {"10.4", "10.5"} else 1,
            "production_moscow_walkway": 1 if domain_stage in {"10.4", "10.5"} else 0,
            "production_rail": 2,
            "production_tube": 6,
            "production_sleeper": sleeper_count,
            "production_under_baseplate_pad": sleeper_count,
            "production_baseplate": sleeper_count,
            "production_rail_pad": sleeper_count,
            "production_track_screw": sleeper_count,
            "production_clamp_hardware": sleeper_count,
        }
        if domain_stage in {"10.3", "10.4"} or legacy_10_5:
            support_count = int(
                production_meta.get("contactRailSupportCount", 0)
            )
            expected_counts.update(
                {
                    "production_contact_rail": 1,
                    "production_contact_rail_cover": 1,
                    "production_contact_rail_bracket": support_count,
                    "production_contact_rail_insulator": support_count,
                    "production_contact_rail_attachment_screws": support_count,
                    "production_contact_rail_fastening_unit": support_count,
                }
            )
        if domain_stage in {"10.4", "10.5"}:
            expected_counts["production_moscow_civil_shell_ring"] = int(
                production_meta.get("moscowCivilRingCount", 0)
            )
    else:
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
            "gaugeMeasurementProfileZLocalM": -0.013,
            "gaugeMeasurementCoreZLocalM": -1.683,
            "gaugeMeasurementZLocalM": -1.683,
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
        if domain_stage in {"10.2", "10.3", "10.4", "10.5"}:
            if bool(props.get("railFootBottomContactFaceOmitted", True)):
                errors.append(
                    f"{rail.name}: continuous R65 underside was incorrectly omitted"
                )
            if int(props.get("omittedLongitudinalEdgeCount", -1)) != 0:
                errors.append(
                    f"{rail.name}: unexpected continuous rail-edge omission"
                )
            if props.get("supportContactSurfacePolicy") != (
                "discrete_rail_pad_top_contact_span_omitted"
            ):
                errors.append(f"{rail.name}: wrong support contact policy")
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

    if domain_stage in {"10.2", "10.3", "10.4", "10.5"}:
        concrete = [
            o for o in production
            if o.object_type == "production_track_concrete"
        ]
        if len(concrete) == 1:
            cp = concrete[0].custom_properties
            concrete_checks = {
                "surfaceCrossSlopeToDrain": 0.03,
                "concreteSurfaceReferenceAbsXM": 1.325,
                "concreteSurfaceReferenceProfileZM": -0.230,
                "centralDrainClearWidthM": 0.900,
                "centralDrainBottomProfileZM": -0.530,
                "waterReleaseGrooveWidthM": 0.050,
                "waterReleaseGrooveDepthM": 0.025,
            }
            for key, expected in concrete_checks.items():
                if key not in cp or not _close(cp[key], expected):
                    errors.append(
                        f"{concrete[0].name}: {key}={cp.get(key)!r} != {expected!r}"
                    )
        for sleeper in [
            o for o in production
            if o.object_type == "production_sleeper"
        ]:
            sp = sleeper.custom_properties
            if not _close(sp.get("sleeperLengthM", -1), 2.650):
                errors.append(f"{sleeper.name}: wrong sleeper length")
            if not _close(sp.get("sleeperThicknessM", -1), 0.165):
                errors.append(f"{sleeper.name}: wrong sleeper thickness")
            if not _close(sp.get("sleeperTopProfileZM", 1), -0.220):
                errors.append(f"{sleeper.name}: wrong sleeper top datum")
        for baseplate in [
            o for o in production
            if o.object_type == "production_baseplate"
        ]:
            bp = baseplate.custom_properties
            if not _close(bp.get("baseplatePlanTransverseM", -1), 0.370):
                errors.append(f"{baseplate.name}: wrong KD-65 transverse size")
            if not _close(bp.get("baseplatePlanLongitudinalM", -1), 0.165):
                errors.append(f"{baseplate.name}: wrong KD-65 longitudinal size")

    if (
        domain_stage in {"10.2", "10.3", "10.4"} or legacy_10_5
    ):
        for pad in [
            o for o in production
            if o.object_type == "production_rail_pad"
        ]:
            if not bool(
                pad.custom_properties.get("railFootContactFaceOmitted", False)
            ):
                errors.append(f"{pad.name}: rail-foot contact span retained")

    if domain_stage in {"10.3", "10.4"} or legacy_10_5:
        contact = [
            o for o in production
            if o.object_type == "production_contact_rail"
        ]
        cover = [
            o for o in production
            if o.object_type == "production_contact_rail_cover"
        ]
        if len(contact) == 1:
            cp = contact[0].custom_properties
            checks = {
                "contactRailAxisProfileXM": -1.450,
                "horizontalOffsetFromInnerWorkingFaceM": 0.690,
                "workingSurfaceProfileZM": 0.160,
                "workingSurfaceCoreZM": -1.510,
                "overallHeightM": 0.118,
                "topWidthM": 0.080,
                "baseWidthM": 0.090,
                "webWidthM": 0.020,
            }
            for key, expected in checks.items():
                if key not in cp or not _close(cp[key], expected):
                    errors.append(
                        f"{contact[0].name}: {key}={cp.get(key)!r} != {expected!r}"
                    )
            if cp.get("horizontalReference") != (
                "nearest_running_rail_inner_working_face"
            ):
                errors.append(
                    f"{contact[0].name}: wrong horizontal reference"
                )
            if cp.get("eraMismatch") is not True:
                errors.append(
                    f"{contact[0].name}: RK legacy-era fallback not tagged"
                )
        if len(cover) == 1:
            cv = cover[0].custom_properties
            if cv.get("eraMismatch") is not True:
                errors.append(f"{cover[0].name}: cover eraMismatch missing")
            if cv.get("modernFallbackIsNotHistoricalClaim") is not True:
                errors.append(
                    f"{cover[0].name}: modern fallback provenance missing"
                )
            cover_checks = {
                "historicalSideGapM": 0.020,
                "outerTopWidthM": 0.112,
                "outerBaseWidthM": 0.134,
                "heightM": 0.200,
                "lowerEdgeAboveContactSurfaceM": 0.023,
            }
            for key, expected in cover_checks.items():
                if key not in cv or not _close(cv[key], expected):
                    errors.append(
                        f"{cover[0].name}: {key}={cv.get(key)!r} != {expected!r}"
                    )
        supports = [
            o for o in production
            if o.object_type == "production_contact_rail_bracket"
        ]
        for support in supports:
            sp = support.custom_properties
            if sp.get("snappedToNearestTimberSleeper") is not True:
                errors.append(
                    f"{support.name}: support was not snapped to sleeper"
                )
            if not _close(sp.get("targetPitchM", -1), 5.0):
                errors.append(f"{support.name}: wrong target support pitch")
        for insulator in [
            o for o in production
            if o.object_type == "production_contact_rail_insulator"
        ]:
            ip = insulator.custom_properties
            if ip.get("exactPorcelainProfileResolved") is not False:
                errors.append(
                    f"{insulator.name}: porcelain fallback marker missing"
                )

    if modern_10_5:
        if production_meta.get("contactRailSupportSeparateFromRunningSupport") is not True:
            errors.append("Stage 10.5 contact supports overlap running-support contract")
        if production_meta.get("contactRailCoverEraMismatch") is not False:
            errors.append("Stage 10.5 modern cover incorrectly carries eraMismatch")
        if production_meta.get("serviceCableRackFamily") != "R2K11":
            errors.append("Stage 10.5 cable-rack family is not R2K11")
        if int(production_meta.get("serviceCableRackHornCount", -1)) != 11:
            errors.append("Stage 10.5 R2K11 horn count is not 11")
        if production_meta.get("serviceCableRackUprightDesignation") != "K1351.001-09":
            errors.append("Stage 10.5 wrong R2K11 upright designation")
        if production_meta.get("serviceCableRackHornDesignation") != "K1350.002":
            errors.append("Stage 10.5 wrong R2K11 horn designation")
        if int(production_meta.get("serviceCablePlacesPerHorn", -1)) != 2:
            errors.append("Stage 10.5 R2K11 must expose two cable places per horn")
        if int(production_meta.get("serviceCableOccupiedPlacesPerHorn", -1)) != 1:
            errors.append(
                "Stage 10.5 modern visual preset must occupy one cable place per used level"
            )
        if int(production_meta.get("serviceCableCount", -1)) != 16:
            errors.append("Stage 10.5 modern service cable count must be 16")
        cables = [
            o for o in production
            if o.object_type == "production_service_cable"
        ]
        for cable in cables:
            cp = cable.custom_properties
            if cp.get("cableSagApplied") is not True:
                errors.append(f"{cable.name}: cable sag marker missing")
            if not _close(cp.get("cableSagMidspanM", -1), 0.025):
                errors.append(f"{cable.name}: wrong cable sag amount")
        if production_meta.get("servicePipeStatus") != (
            "implemented_normative_DN80_with_explicit_placement_fallback"
        ):
            errors.append("Stage 10.5 modern water-main status mismatch")
        if int(production_meta.get("serviceWaterMainCount", -1)) != 1:
            errors.append("Stage 10.5 must contain one tunnel water main")
        if int(production_meta.get("serviceWaterMainSupportCount", -1)) <= 0:
            errors.append("Stage 10.5 water main has no periodic supports")
        if not _close(
            production_meta.get("serviceWaterMainSupportMaxPitchM", -1),
            4.0,
        ):
            errors.append("Stage 10.5 water-main support pitch must be 4 m max")
        if int(production_meta.get("serviceWaterMainMinNominalDNmm", -1)) != 80:
            errors.append("Stage 10.5 water main must remain at least DN80")
        water = [
            o for o in production
            if o.object_type == "production_water_main"
        ]
        if len(water) == 1:
            wp = water[0].custom_properties
            if wp.get("positionRule") != "above_UGR_weak_current_side":
                errors.append(f"{water[0].name}: wrong water-main routing rule")
            if wp.get("exactProjectRouteResolved") is not False:
                errors.append(
                    f"{water[0].name}: placement fallback incorrectly marked exact"
                )
            if not _close(wp.get("previewOuterDiameterM", -1), 0.089):
                errors.append(f"{water[0].name}: wrong DN80-class preview diameter")
            if not _close(wp.get("centerProfileZM", -1), 0.600):
                errors.append(f"{water[0].name}: wrong collision-free water-main z")
            if not _close(wp.get("supportMaxPitchM", -1), 4.0):
                errors.append(f"{water[0].name}: wrong water-main support pitch")

        for block in [
            o for o in production if o.object_type == "production_lvt_block"
        ]:
            bp = block.custom_properties
            if bp.get("bridgesCentralDrain") is not False:
                errors.append(f"{block.name}: LVT block bridges central drain")
        for pad in [
            o for o in production if o.object_type == "production_apc4_rail_pad"
        ]:
            pp = pad.custom_properties
            if not _close(pp.get("padThicknessM", -1), 0.014):
                errors.append(f"{pad.name}: wrong APC-4 rail-pad thickness")
        for base_plate in [
            o for o in production
            if o.object_type == "production_contact_rail_base_plate"
        ]:
            pp = base_plate.custom_properties
            if int(pp.get("anchorCount", -1)) != 4:
                errors.append(f"{base_plate.name}: expected four base anchors")
            if not _close(pp.get("transverseM", -1), 0.220):
                errors.append(f"{base_plate.name}: wrong base-plate transverse size")
            if not _close(
                pp.get("actualInboardClearanceToLVTBlockM", -1),
                0.035,
            ):
                errors.append(
                    f"{base_plate.name}: LVT clearance is not 35 mm"
                )

        for bracket in [
            o for o in production
            if o.object_type == "production_contact_rail_bracket"
        ]:
            bp = bracket.custom_properties
            if bp.get("legacySleeperAttachment") is not False:
                errors.append(f"{bracket.name}: modern bracket still marked sleeper-mounted")
            if bp.get("dedicatedConcreteSupportBlock") is not True:
                errors.append(f"{bracket.name}: modern bracket lacks dedicated support block")
            if bp.get("geometryMode") != "dimensioned_hook_channel_873x373_v3":
                errors.append(f"{bracket.name}: wrong dimensioned bracket mode")
            bracket_checks = {
                "drawingReferenceToAxisM": 0.683,
                "drawingReferenceToOuterEnvelopeM": 0.873,
                "drawingUpperReturnM": 0.180,
                "drawingTopAboveUGRM": 0.373,
                "drawingLowerBendCalloutM": 0.155,
                "drawingUpperBendCalloutM": 0.090,
                "outerEnvelopeProfileAbsXM": 1.633,
                "minimumClearanceToLVTBlockM": 0.035,
                "actualLowerLegClearanceToLVTBlockM": 0.035,
            }
            for key, expected in bracket_checks.items():
                if not _close(bp.get(key, -1), expected, 2e-9):
                    errors.append(
                        f"{bracket.name}: {key}={bp.get(key)!r} != {expected!r}"
                    )

        for clamp in [
            o for o in production
            if o.object_type == "production_contact_rail_fastening_unit"
        ]:
            cp = clamp.custom_properties
            if cp.get("geometryMode") != (
                "upper_flange_saddle_insulated_two_bolt_v3"
            ):
                errors.append(f"{clamp.name}: wrong modern clamp mode")
            if int(cp.get("boltCount", -1)) != 2:
                errors.append(f"{clamp.name}: expected two clamp bolts")

        for bolts in [
            o for o in production
            if o.object_type == "production_contact_rail_clamp_bolts"
        ]:
            bp = bolts.custom_properties
            if int(bp.get("quantity", -1)) != 2:
                errors.append(f"{bolts.name}: wrong clamp-bolt count")

        for dowels in [
            o for o in production
            if o.object_type == "production_contact_rail_attachment_dowels"
        ]:
            dp = dowels.custom_properties
            if int(dp.get("quantity", -1)) != 4:
                errors.append(f"{dowels.name}: wrong base-anchor count")
        for hood in [
            o for o in production
            if o.object_type == "production_contact_rail_support_hood"
        ]:
            hp = hood.custom_properties
            if hp.get("mainCoverInterruptedHere") is not True:
                errors.append(f"{hood.name}: support hood does not mark cover interruption")
            if hp.get("geometryMode") != "rounded_local_fastening_hood_v2":
                errors.append(f"{hood.name}: wrong support-hood geometry mode")
            if hp.get("coversClampAndBoltHeads") is not True:
                errors.append(f"{hood.name}: hood does not cover clamp/bolt heads")
            if not _close(hp.get("dimensionedBracketTopProfileZM", -1), 0.373):
                errors.append(f"{hood.name}: wrong dimensioned bracket-top datum")
        cover_spans = [
            o for o in production
            if o.object_type == "production_contact_rail_cover_span"
        ]
        for span in cover_spans:
            sp = span.custom_properties
            if sp.get("geometryMode") != (
                "rounded_wrap_profile_from_exact_envelope"
            ):
                errors.append(f"{span.name}: wrong modern cover profile mode")
            if not _close(sp.get("heightM", -1), 0.111):
                errors.append(f"{span.name}: wrong modern cover height")
            if not _close(sp.get("outerTopWidthM", -1), 0.092):
                errors.append(f"{span.name}: wrong modern cover top width")
            if not _close(sp.get("outerBaseWidthM", -1), 0.114):
                errors.append(f"{span.name}: wrong modern cover base width")
            if sp.get("supportZonesInterrupted") is not True:
                errors.append(f"{span.name}: cover is not interrupted at support zones")
            if sp.get("supportHoodSeparate") is not True:
                errors.append(f"{span.name}: local support hood contract missing")

    if domain_stage in {"10.4", "10.5"}:
        if any(o.object_type == "lining_segment" for o in package.objects):
            errors.append("Stage 10.4+ retained Stage-9 lining_segment objects")
        if any(o.object_type == "bolt_head" for o in package.objects):
            errors.append("Stage 10.4+ retained Stage-9 lining bolt heads")
        if any(o.object_type == "bolt_pocket_cutter" for o in package.objects):
            errors.append("Stage 10.4+ retained Stage-9 lining bolt cutters")
        if production_meta.get("walkwayStatus") != (
            "implemented_stage10_4_source_backed_geometry"
        ):
            errors.append("Stage 10.4+ walkway status mismatch")
        if production_meta.get("transitionalCivilGapStatus") != (
            "closed_by_stage10_4_moscow_shell"
        ):
            errors.append("Stage 10.4+ civil-gap status is not closed")

        civil = [
            o for o in production
            if o.object_type == "production_moscow_civil_shell_ring"
        ]
        if not civil:
            errors.append("Stage 10.4+ generated no Moscow civil rings")
        for ring in civil:
            rp = ring.custom_properties
            civil_checks = {
                "intradosRadiusM": profile.intrados_radius_m,
                "extradosRadiusM": profile.extrados_radius_m,
                "structuralDepthM": (
                    profile.extrados_radius_m - profile.intrados_radius_m
                ),
                "moscowCivilRingPitchM": profile.ring_pitch_m,
                "liningAxisProfileZM": profile.datums.lining_axis_z_m,
                "liningAxisCoreZM": 0.000,
            }
            for key, expected in civil_checks.items():
                if key not in rp or not _close(rp[key], expected):
                    errors.append(
                        f"{ring.name}: {key}={rp.get(key)!r} != {expected!r}"
                    )
            if rp.get("seriesAccurateTubingLOD0") is not False:
                errors.append(f"{ring.name}: false series-accurate tubing LOD0 claim")
            if rp.get("seriesAccurateCivilLOD0") is not False:
                errors.append(f"{ring.name}: false series-accurate civil LOD0 claim")
            if rp.get("civilFamily") != profile.civil_family:
                errors.append(f"{ring.name}: civil-family metadata mismatch")
            if rp.get("coarseSegmentCountIsGeometry") is not False:
                errors.append(f"{ring.name}: coarse segment reference used as geometry")
            if rp.get("internalRingEndCaps") is not False:
                errors.append(f"{ring.name}: internal ring end caps retained")

        walkway = [
            o for o in production
            if o.object_type == "production_moscow_walkway"
        ]
        if len(walkway) == 1:
            wp = walkway[0].custom_properties
            walkway_checks = {
                "walkwayTopProfileZM": profile.walkway.top_z_m,
                "walkwayTopCoreZM": (
                    profile.walkway.top_z_m
                    + profile.coordinate.profile_z_to_core_z_offset_m
                ),
                "walkwayInnerEdgeProfileXM": profile.walkway.inner_edge_x_m,
                "walkwayOuterEdgeProfileXM": profile.walkway.outer_edge_x_m,
                "walkwayTopClearWidthM": profile.walkway.top_clear_width_m,
            }
            for key, expected in walkway_checks.items():
                if key not in wp or not _close(wp[key], expected, 2e-9):
                    errors.append(
                        f"{walkway[0].name}: {key}={wp.get(key)!r} != {expected!r}"
                    )
            if wp.get("trackConcreteContactFacesOmitted") is not True:
                errors.append(f"{walkway[0].name}: concrete contact faces retained")
            if wp.get("liningContactFacesOmitted") is not True:
                errors.append(f"{walkway[0].name}: lining contact faces retained")

        concrete = [
            o for o in production
            if o.object_type == "production_track_concrete"
        ]
        if len(concrete) == 1:
            cp = concrete[0].custom_properties
            expected_bottom_surface = (
                f"moscow_{int(round(2000.0 * profile.intrados_radius_m))}_intrados"
            )
            if cp.get("physicalBottomSurface") != expected_bottom_surface:
                errors.append(
                    f"{concrete[0].name}: concrete does not close on selected Moscow intrados"
                )
            if cp.get("walkwayShoulderPartitioned") is not True:
                errors.append(
                    f"{concrete[0].name}: walkway shoulder was not partitioned"
                )
            if cp.get("liningContactFacesOmitted") is not True:
                errors.append(
                    f"{concrete[0].name}: lining contact faces retained"
                )

    ring_count = int(package.metadata.get("ringCount", 0))
    if domain_stage in {"10.4", "10.5"}:
        if result.lining_cap_faces_removed != 0:
            errors.append("Stage 10.4 unexpectedly stripped legacy lining caps")
        if result.lining_interface_faces_removed != 0:
            errors.append("Stage 10.4 unexpectedly stripped legacy lining interfaces")
    else:
        if ring_count > 1 and result.lining_cap_faces_removed <= 0:
            errors.append("no internal lining cap faces were removed")
        if result.lining_interface_faces_removed <= 0:
            errors.append("no coincident segment-interface faces were removed")

    report = {
        "stage": domain_stage,
        "servicePreset": service_preset,
        "continuousSweepAlignmentCompaction": production_meta.get(
            "continuousSweepAlignmentCompaction"
        ),
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
        "permanentWayPresetID": production_meta.get("permanentWayPresetID"),
        "modernLVTSupportCount": production_meta.get("modernLVTSupportCount"),
        "modernLVTSupportPitchM": production_meta.get("modernLVTSupportPitchM"),
        "trackConcreteStatus": production_meta.get("trackConcreteStatus"),
        "sleeperCount": production_meta.get("sleeperCount"),
        "sleeperPitchM": production_meta.get("sleeperPitchM"),
        "contactRailStatus": production_meta.get("contactRailStatus"),
        "contactRailPresetID": production_meta.get("contactRailPresetID"),
        "contactRailSupportCount": production_meta.get(
            "contactRailSupportCount"
        ),
        "contactRailCoverSpanCount": production_meta.get(
            "contactRailCoverSpanCount"
        ),
        "contactRailSupportHoodCount": production_meta.get(
            "contactRailSupportHoodCount"
        ),
        "contactRailSupportSeparateFromRunningSupport": production_meta.get(
            "contactRailSupportSeparateFromRunningSupport"
        ),
        "contactRailAxisProfileXM": production_meta.get(
            "contactRailAxisProfileXM"
        ),
        "contactRailWorkingSurfaceProfileZM": production_meta.get(
            "contactRailWorkingSurfaceProfileZM"
        ),
        "contactRailCoverEraMismatch": production_meta.get(
            "contactRailCoverEraMismatch"
        ),
        "civilShellStatus": production_meta.get("civilShellStatus"),
        "civilArchetypeID": production_meta.get("civilArchetypeID"),
        "serviceCableCount": production_meta.get("serviceCableCount"),
        "serviceCableRackCount": production_meta.get("serviceCableRackCount"),
        "serviceCableRackFamily": production_meta.get("serviceCableRackFamily"),
        "serviceCableRackUprightDesignation": production_meta.get(
            "serviceCableRackUprightDesignation"
        ),
        "serviceCableRackHornDesignation": production_meta.get(
            "serviceCableRackHornDesignation"
        ),
        "serviceCablePlacesPerHorn": production_meta.get(
            "serviceCablePlacesPerHorn"
        ),
        "serviceCableOccupiedPlacesPerHorn": production_meta.get(
            "serviceCableOccupiedPlacesPerHorn"
        ),
        "servicePipeStatus": production_meta.get("servicePipeStatus"),
        "serviceWaterMainCount": production_meta.get(
            "serviceWaterMainCount"
        ),
        "serviceWaterMainSupportCount": production_meta.get(
            "serviceWaterMainSupportCount"
        ),
        "serviceWaterMainSupportMaxPitchM": production_meta.get(
            "serviceWaterMainSupportMaxPitchM"
        ),
        "serviceWaterMainMinNominalDNmm": production_meta.get(
            "serviceWaterMainMinNominalDNmm"
        ),
        "walkwayStatus": production_meta.get("walkwayStatus"),
        "moscowCivilRingCount": production_meta.get("moscowCivilRingCount"),
        "moscowCivilRingPitchM": production_meta.get("moscowCivilRingPitchM"),
        "moscowCivilIntradosRadiusM": production_meta.get(
            "moscowCivilIntradosRadiusM"
        ),
        "moscowCivilExtradosRadiusM": production_meta.get(
            "moscowCivilExtradosRadiusM"
        ),
        "transitionalCivilGapStatus": production_meta.get(
            "transitionalCivilGapStatus"
        ),
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
