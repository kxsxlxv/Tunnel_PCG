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
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    RingConfig,
    RingRotationStrategy,
    SurfaceMeshingConfig,
    TunnelAssemblyConfig,
    build_chunk_scene_packages,
    build_production_tunnel,
    load_stage10_initial_moscow_profile,
)
from tunnel_scanner_core.scene_io import write_scene_package_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the Moscow Stage 10 production scene. Stage 10.5 modern "
            "service preset is the default; Stage 10.1-10.4 remain compatibility modes."
        )
    )
    size = parser.add_mutually_exclusive_group()
    size.add_argument("--rings", type=int, default=None)
    size.add_argument("--length-m", type=float, default=None)
    parser.add_argument("--seed", type=int, default=5812)
    parser.add_argument("--namespace", default="stage10")
    parser.add_argument(
        "--domain-stage",
        choices=["10.1", "10.2", "10.3", "10.4", "10.5"],
        default="10.5",
        help="Moscow production domain stage; default: 10.5",
    )
    parser.add_argument(
        "--service-preset",
        choices=["auto", "modern", "legacy"],
        default="auto",
        help=(
            "Moscow service preset. Stage 10.5 auto resolves to modern; "
            "use legacy to retain timber/KD-65 and the legacy contact assembly."
        ),
    )
    parser.add_argument(
        "--dense-continuous-sweeps",
        action="store_true",
        help=(
            "Disable Stage-10.5 zero-error removal of mathematically collinear "
            "continuous-sweep stations. Intended only for regression comparison."
        ),
    )
    parser.add_argument("--no-bolts", action="store_true")
    parser.add_argument(
        "--label-policy",
        choices=[x.value for x in LabelPolicy],
        default=LabelPolicy.STSD_COARSE.value,
    )
    parser.add_argument(
        "--rotation-strategy",
        choices=[x.value for x in RingRotationStrategy],
        default=RingRotationStrategy.RINGWISE_GAUSSIAN.value,
    )
    parser.add_argument("--lateral-wavelength-m", type=float, default=50.0)
    parser.add_argument("--vertical-wavelength-m", type=float, default=100.0)
    parser.add_argument("--axis-noise-sigma", type=float, default=0.005)
    parser.add_argument("--sagitta-mm", type=float, default=2.0)
    parser.add_argument("--chunk-m", type=float, default=None)
    parser.add_argument(
        "--chunks-only",
        action="store_true",
        help=(
            "When --chunk-m is set, skip writing the monolithic full-scene JSON. "
            "The geometry is still generated in global coordinates internally; only "
            "the serialized output is partitioned."
        ),
    )
    parser.add_argument(
        "--chunk-policy",
        choices=[x.value for x in ChunkBoundaryPolicy],
        default=ChunkBoundaryPolicy.RING_ALIGNED.value,
    )
    parser.add_argument(
        "--localize-chunks-for-blender",
        action="store_true",
        help="Keep full scene global, but subtract per-chunk origins in optional chunk JSONs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "examples" / "stage10_production_scene.json",
    )
    return parser.parse_args()


def _validate_stage10_build(
    build,
    profile,
    domain_stage: str,
    service_preset: str,
) -> tuple[float, list[float]]:
    meta = build.scene.metadata["productionGeometry"]
    if meta.get("domainStage") != domain_stage:
        raise AssertionError(
            f"generated scene domainStage {meta.get('domainStage')!r} "
            f"does not match requested {domain_stage!r}"
        )
    if meta.get("moscowProfileID") != profile.profile_id:
        raise AssertionError("generated scene Moscow profile ID mismatch")
    if meta.get("moscowProfileSHA256") != profile.provenance.canonical_sha256:
        raise AssertionError("generated scene Moscow profile SHA mismatch")
    if meta.get("railProfile") != "stage10_1_r65_gost_r51685_2022":
        raise AssertionError("generated scene does not use the Stage 10.1 R65 profile")

    rails = build.scene.objects_of_type("production_rail")
    if len(rails) != 2:
        raise AssertionError(f"expected two production rails, got {len(rails)}")
    working_faces = sorted(
        float(rail.custom_properties["railInnerWorkingFaceX"])
        for rail in rails
    )
    gauge = working_faces[1] - working_faces[0]
    if not math.isclose(gauge, profile.track.gauge_m, abs_tol=2e-12):
        raise AssertionError(
            f"working-face gauge {gauge!r} does not match {profile.track.gauge_m!r}"
        )
    for rail in rails:
        props = rail.custom_properties
        if props.get("railProfile") != "stage10_1_r65_gost_r51685_2022":
            raise AssertionError(f"{rail.name}: unexpected rail profile")
        if not math.isclose(
            float(props["railTopProfileZLocalM"]),
            0.0,
            abs_tol=2e-12,
        ):
            raise AssertionError(f"{rail.name}: rail top is not at profile UGR")
        if not math.isclose(
            float(props["railTopCoreZLocalM"]),
            profile.coordinate.profile_z_to_core_z_offset_m,
            abs_tol=2e-12,
        ):
            raise AssertionError(f"{rail.name}: profile UGR was not translated to core Z")
        if not math.isclose(
            float(props["gaugeMeasurementBelowUGRM"]),
            0.013,
            abs_tol=2e-12,
        ):
            raise AssertionError(f"{rail.name}: unexpected gauge measurement plane")
    resolved_service = str(meta.get("servicePreset", "legacy"))
    if service_preset != "auto" and resolved_service != service_preset:
        raise AssertionError(
            f"resolved service preset {resolved_service!r} != requested {service_preset!r}"
        )
    modern_10_5 = domain_stage == "10.5" and resolved_service == "modern"
    legacy_pw = (
        domain_stage in {"10.2", "10.3", "10.4"}
        or (domain_stage == "10.5" and resolved_service == "legacy")
    )

    if legacy_pw:
        if meta.get("permanentWayStatus") != (
            "implemented_stage10_2_initial_geometry"
        ):
            raise AssertionError("Stage 10.2 permanent way is not implemented")
        if len(build.scene.objects_of_type("production_pavement")) != 0:
            raise AssertionError("Stage 10.2 must replace Stage-9 pavement")
        if len(build.scene.objects_of_type("production_track_concrete")) != 1:
            raise AssertionError("Stage 10.2 requires one track-concrete asset")
        sleeper_count = len(build.scene.objects_of_type("production_sleeper"))
        if sleeper_count <= 0:
            raise AssertionError("Stage 10.2 generated no sleepers")
        if sleeper_count != int(meta.get("sleeperCount", -1)):
            raise AssertionError("Stage 10.2 sleeper metadata mismatch")
        for obj_type in (
            "production_under_baseplate_pad",
            "production_baseplate",
            "production_rail_pad",
            "production_track_screw",
            "production_clamp_hardware",
        ):
            if len(build.scene.objects_of_type(obj_type)) != sleeper_count:
                raise AssertionError(
                    f"{obj_type}: count does not match sleeper count"
                )
        for rail in rails:
            props = rail.custom_properties
            if props.get("railFootBottomContactFaceOmitted", True):
                raise AssertionError(
                    f"{rail.name}: continuous R65 underside must remain visible"
                )
            if int(props.get("omittedLongitudinalEdgeCount", -1)) != 0:
                raise AssertionError(
                    f"{rail.name}: unexpected continuous rail-edge omission"
                )
            if props.get("supportContactSurfacePolicy") != (
                "discrete_rail_pad_top_contact_span_omitted"
            ):
                raise AssertionError(
                    f"{rail.name}: wrong discrete support contact policy"
                )
        for pad in build.scene.objects_of_type("production_rail_pad"):
            if not pad.custom_properties.get(
                "railFootContactFaceOmitted",
                False,
            ):
                raise AssertionError(
                    f"{pad.name}: rail-foot contact span was not omitted"
                )
    if (
        domain_stage in {"10.3", "10.4"}
        or (domain_stage == "10.5" and resolved_service == "legacy")
    ):
        if meta.get("contactRailStatus") != (
            "implemented_stage10_3_initial_geometry_with_explicit_fallbacks"
        ):
            raise AssertionError("Stage 10.3 contact rail is not implemented")
        contact = build.scene.objects_of_type("production_contact_rail")
        cover = build.scene.objects_of_type("production_contact_rail_cover")
        if len(contact) != 1:
            raise AssertionError("Stage 10.3 requires one contact rail")
        if len(cover) != 1:
            raise AssertionError("Stage 10.3 requires one protective cover")
        cp = contact[0].custom_properties
        if not math.isclose(
            float(cp["contactRailAxisProfileXM"]),
            -1.450,
            abs_tol=2e-12,
        ):
            raise AssertionError("Stage 10.3 contact-rail X datum mismatch")
        if not math.isclose(
            float(cp["workingSurfaceProfileZM"]),
            0.160,
            abs_tol=2e-12,
        ):
            raise AssertionError("Stage 10.3 contact working surface mismatch")
        cover_props = cover[0].custom_properties
        if cover_props.get("eraMismatch") is not True:
            raise AssertionError("Stage 10.3 cover must retain eraMismatch=true")
        if cover_props.get("modernFallbackIsNotHistoricalClaim") is not True:
            raise AssertionError("Stage 10.3 cover fallback provenance missing")
        support_count = int(meta.get("contactRailSupportCount", 0))
        if support_count <= 0:
            raise AssertionError("Stage 10.3 generated no contact-rail supports")
        for obj_type in (
            "production_contact_rail_bracket",
            "production_contact_rail_insulator",
            "production_contact_rail_attachment_screws",
            "production_contact_rail_fastening_unit",
        ):
            if len(build.scene.objects_of_type(obj_type)) != support_count:
                raise AssertionError(
                    f"{obj_type}: count does not match contact support count"
                )
    if modern_10_5:
        if meta.get("permanentWayStatus") != (
            "implemented_stage10_5_modern_LVT_M_APC4"
        ):
            raise AssertionError("Stage 10.5 modern LVT-M permanent way is not implemented")
        if meta.get("contactRailStatus") != (
            "implemented_stage10_5_modern_segmented_cover_and_dedicated_support"
        ):
            raise AssertionError("Stage 10.5 modern contact rail is not implemented")
        if build.scene.objects_of_type("production_sleeper"):
            raise AssertionError("modern preset must not instantiate timber sleepers")
        if build.scene.objects_of_type("production_baseplate"):
            raise AssertionError("modern preset must not instantiate KD-65 baseplates")
        lvt_count = len(build.scene.objects_of_type("production_lvt_block"))
        if lvt_count <= 0:
            raise AssertionError("modern preset generated no LVT-M supports")
        if lvt_count != int(meta.get("modernLVTSupportCount", -1)):
            raise AssertionError("modern LVT support metadata mismatch")
        for obj_type in (
            "production_lvt_rubber_boot",
            "production_apc4_rail_pad",
            "production_apc4_fastening",
        ):
            if len(build.scene.objects_of_type(obj_type)) != lvt_count:
                raise AssertionError(
                    f"{obj_type}: count does not match LVT support count"
                )

        contact = build.scene.objects_of_type("production_contact_rail")
        if len(contact) != 1:
            raise AssertionError("modern preset requires one contact rail")
        if build.scene.objects_of_type("production_contact_rail_cover"):
            raise AssertionError("modern preset must not use the legacy continuous cover")
        cover_spans = build.scene.objects_of_type(
            "production_contact_rail_cover_span"
        )
        if not cover_spans:
            raise AssertionError("modern preset generated no segmented cover spans")
        support_count = int(meta.get("contactRailSupportCount", 0))
        if support_count <= 0:
            raise AssertionError("modern preset generated no contact supports")
        for obj_type in (
            "production_contact_rail_support_block",
            "production_contact_rail_base_plate",
            "production_contact_rail_bracket",
            "production_contact_rail_insulator",
            "production_contact_rail_fastening_unit",
            "production_contact_rail_clamp_bolts",
            "production_contact_rail_attachment_dowels",
            "production_contact_rail_support_hood",
        ):
            if len(build.scene.objects_of_type(obj_type)) != support_count:
                raise AssertionError(
                    f"{obj_type}: count does not match modern contact support count"
                )
        bracket = build.scene.objects_of_type(
            "production_contact_rail_bracket"
        )[0]
        bp = bracket.custom_properties
        if bp.get("geometryMode") != "dimensioned_hook_channel_873x373_v3":
            raise AssertionError("modern bracket did not use dimensioned v3 geometry")
        for key, expected in (
            ("drawingReferenceToAxisM", 0.683),
            ("drawingReferenceToOuterEnvelopeM", 0.873),
            ("drawingUpperReturnM", 0.180),
            ("drawingTopAboveUGRM", 0.373),
            ("outerEnvelopeProfileAbsXM", 1.633),
            ("minimumClearanceToLVTBlockM", 0.035),
            ("actualLowerLegClearanceToLVTBlockM", 0.035),
        ):
            if not math.isclose(float(bp.get(key, -1)), expected, abs_tol=2e-9):
                raise AssertionError(f"modern bracket {key} mismatch")
        clamp = build.scene.objects_of_type(
            "production_contact_rail_fastening_unit"
        )[0]
        if clamp.custom_properties.get("geometryMode") != (
            "upper_flange_saddle_insulated_two_bolt_v3"
        ):
            raise AssertionError("modern contact clamp topology mismatch")
        if int(clamp.custom_properties.get("boltCount", -1)) != 2:
            raise AssertionError("modern contact clamp requires two bolts")
        dowels = build.scene.objects_of_type(
            "production_contact_rail_attachment_dowels"
        )[0]
        if int(dowels.custom_properties.get("quantity", -1)) != 4:
            raise AssertionError("modern contact base requires four anchors")

        if meta.get("contactRailSupportSeparateFromRunningSupport") is not True:
            raise AssertionError("contact supports must remain separate from running supports")
        if bool(meta.get("contactRailCoverEraMismatch", True)):
            raise AssertionError("modern contact cover must not carry legacy era mismatch")

        if len(build.scene.objects_of_type("production_tube")) != 0:
            raise AssertionError("modern preset must remove Stage-8 tube previews")
        if len(build.scene.objects_of_type("production_service_cable")) != 22:
            raise AssertionError("modern preset requires 22 continuous service cables")
        if len(build.scene.objects_of_type("production_water_main")) != 1:
            raise AssertionError("modern preset requires one tunnel water main")
        if meta.get("servicePipeStatus") != (
            "implemented_normative_DN80_with_explicit_placement_fallback"
        ):
            raise AssertionError("modern DN80 water-main status mismatch")
        if int(meta.get("serviceWaterMainMinNominalDNmm", -1)) != 80:
            raise AssertionError("modern tunnel water main must remain at least DN80")
        civil_count = int(meta.get("moscowCivilRingCount", 0))
        if len(build.scene.objects_of_type("production_cable_rack_r2k11")) != 2 * civil_count:
            raise AssertionError("modern preset requires one R2K11 rack per side per civil ring")

    if domain_stage in {"10.4", "10.5"}:
        if meta.get("civilShellStatus") != (
            "implemented_stage10_4_smooth_concentric_shell"
        ):
            raise AssertionError("Stage 10.4 civil shell is not implemented")
        if meta.get("walkwayStatus") != (
            "implemented_stage10_4_source_backed_geometry"
        ):
            raise AssertionError("Stage 10.4 walkway is not implemented")
        if meta.get("transitionalCivilGapStatus") != (
            "closed_by_stage10_4_moscow_shell"
        ):
            raise AssertionError("Stage 10.4 civil gap is not marked closed")
        if build.scene.objects_of_type("lining_segment"):
            raise AssertionError("Stage 10.4 retained Stage-9 lining segments")
        if build.scene.objects_of_type("bolt_head"):
            raise AssertionError("Stage 10.4 retained Stage-9 lining bolt heads")
        if build.scene.objects_of_type("bolt_pocket_cutter"):
            raise AssertionError("Stage 10.4 retained Stage-9 bolt cutters")
        if build.scene.objects_of_type("production_walkway"):
            raise AssertionError("Stage 10.4 retained Stage-8/9 walkway")
        civil = build.scene.objects_of_type(
            "production_moscow_civil_shell_ring"
        )
        if not civil:
            raise AssertionError("Stage 10.4 generated no Moscow civil rings")
        if len(civil) != int(meta.get("moscowCivilRingCount", -1)):
            raise AssertionError("Stage 10.4 civil ring metadata mismatch")
        if len(build.scene.objects_of_type("production_moscow_walkway")) != 1:
            raise AssertionError("Stage 10.4 requires one Moscow walkway")
        for ring in civil:
            p = ring.custom_properties
            if not math.isclose(float(p["intradosRadiusM"]), 2.55, abs_tol=2e-12):
                raise AssertionError(f"{ring.name}: wrong intrados radius")
            if not math.isclose(float(p["extradosRadiusM"]), 2.75, abs_tol=2e-12):
                raise AssertionError(f"{ring.name}: wrong extrados radius")
            if p.get("seriesAccurateTubingLOD0") is not False:
                raise AssertionError(f"{ring.name}: false LOD0 accuracy claim")
    return gauge, working_faces


def main() -> None:
    args = parse_args()
    profile = load_stage10_initial_moscow_profile()
    ring_cfg = RingConfig()
    if args.rings is not None:
        if args.rings <= 0:
            raise ValueError("--rings must be positive")
        n_rings = args.rings
    elif args.length_m is not None:
        if args.length_m <= 0:
            raise ValueError("--length-m must be positive")
        n_rings = math.ceil(args.length_m / ring_cfg.width_m)
    else:
        n_rings = 20

    assembly_cfg = TunnelAssemblyConfig(
        n_rings=n_rings,
        ring_width_m=ring_cfg.width_m,
        lateral_wavelength_m=args.lateral_wavelength_m,
        vertical_wavelength_m=args.vertical_wavelength_m,
        axis_noise_sigma_m=args.axis_noise_sigma,
        ring_rotation_strategy=RingRotationStrategy(args.rotation_strategy),
    )
    build = build_production_tunnel(
        ring_config=ring_cfg,
        assembly_config=assembly_cfg,
        surface_meshing=SurfaceMeshingConfig(
            max_sagitta_m=args.sagitta_mm / 1000.0
        ),
        include_bolts=not args.no_bolts,
        label_policy=LabelPolicy(args.label_policy),
        production_config=ProductionConfig(
            namespace=args.namespace,
            moscow_profile=profile,
            moscow_stage=args.domain_stage,
            moscow_service_preset=args.service_preset,
            compact_exact_collinear_continuous_stations=(
                False if args.dense_continuous_sweeps else None
            ),
        ),
        seed=args.seed,
    )
    working_face_gauge, working_faces = _validate_stage10_build(
        build,
        profile,
        args.domain_stage,
        args.service_preset,
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.chunks_only and args.chunk_m is None:
        raise ValueError("--chunks-only requires --chunk-m")
    if not args.chunks_only:
        write_scene_package_json(build.scene, output)

    production_objects = [
        obj for obj in build.scene.objects if obj.object_type.startswith("production_")
    ]
    production_meta = build.scene.metadata["productionGeometry"]
    rails = build.scene.objects_of_type("production_rail")
    summary = {
        "stage": args.domain_stage,
        "seed": args.seed,
        "namespace": args.namespace,
        "ringCount": n_rings,
        "requestedLengthM": args.length_m,
        "generatedLengthM": build.assembly.length_by_chainage_m,
        "globalCoordinates": True,
        "sourceRingWidthM": ring_cfg.width_m,
        "includeBolts": (
            not args.no_bolts and args.domain_stage not in {"10.4", "10.5"}
        ),
        "stage9CivilBoltsSuppressedForStage10_4Plus": (
            args.domain_stage in {"10.4", "10.5"}
        ),
        "servicePreset": production_meta.get("servicePreset"),
        "continuousSweepAlignmentCompaction": production_meta.get(
            "continuousSweepAlignmentCompaction"
        ),
        "labelPolicy": args.label_policy,
        "sceneObjects": len(build.scene.objects),
        "productionInfrastructureObjects": len(production_objects),
        "productionRails": len(rails),
        "productionTubes": len(build.scene.objects_of_type("production_tube")),
        "productionWalkways": len(build.scene.objects_of_type("production_walkway")),
        "productionPavements": len(build.scene.objects_of_type("production_pavement")),
        "productionTrackConcrete": len(
            build.scene.objects_of_type("production_track_concrete")
        ),
        "productionSleepers": len(
            build.scene.objects_of_type("production_sleeper")
        ),
        "productionKD65Baseplates": len(
            build.scene.objects_of_type("production_baseplate")
        ),
        "productionLVTBlocks": len(
            build.scene.objects_of_type("production_lvt_block")
        ),
        "productionLVTRubberBoots": len(
            build.scene.objects_of_type("production_lvt_rubber_boot")
        ),
        "productionAPC4Fastenings": len(
            build.scene.objects_of_type("production_apc4_fastening")
        ),
        "productionContactRails": len(
            build.scene.objects_of_type("production_contact_rail")
        ),
        "productionContactRailCovers": len(
            build.scene.objects_of_type("production_contact_rail_cover")
        ),
        "productionContactRailCoverSpans": len(
            build.scene.objects_of_type("production_contact_rail_cover_span")
        ),
        "productionContactRailSupportHoods": len(
            build.scene.objects_of_type("production_contact_rail_support_hood")
        ),
        "productionContactRailBrackets": len(
            build.scene.objects_of_type("production_contact_rail_bracket")
        ),
        "productionContactRailBasePlates": len(
            build.scene.objects_of_type("production_contact_rail_base_plate")
        ),
        "productionContactRailClampBolts": len(
            build.scene.objects_of_type("production_contact_rail_clamp_bolts")
        ),
        "productionMoscowCivilRings": len(
            build.scene.objects_of_type("production_moscow_civil_shell_ring")
        ),
        "productionMoscowWalkways": len(
            build.scene.objects_of_type("production_moscow_walkway")
        ),
        "productionServiceCables": len(
            build.scene.objects_of_type("production_service_cable")
        ),
        "productionR2K11Racks": len(
            build.scene.objects_of_type("production_cable_rack_r2k11")
        ),
        "sleeperPitchM": (
            profile.sleeper.pitch_m
            if (
                args.domain_stage in {"10.2", "10.3", "10.4"}
                or (
                    args.domain_stage == "10.5"
                    and production_meta.get("servicePreset") == "legacy"
                )
            )
            else None
        ),
        "railProfile": production_meta["railProfile"],
        "railProfileVertices": int(rails[0].custom_properties["railProfileVertices"]),
        "railSourceAlignmentStations": int(
            rails[0].custom_properties.get("sourceAlignmentStationCount", 0)
        ),
        "railSweepAlignmentStations": int(
            rails[0].custom_properties.get("sweepAlignmentStationCount", 0)
        ),
        "railExactCollinearStationsRemoved": int(
            rails[0].custom_properties.get(
                "exactCollinearAlignmentStationsRemoved",
                0,
            )
        ),
        "railFaceCountEach": len(rails[0].faces),
        "workingFaceGaugeM": working_face_gauge,
        "innerWorkingFacesX": working_faces,
        "gaugeMeasurementBelowUGRM": profile.track.gauge_measurement_below_ugr_m,
        "ugrProfileZLocalM": profile.datums.ugr_z_m,
        "ugrCoreZLocalM": production_meta["ugrCoreZLocalM"],
        "profileZToCoreZOffsetM": production_meta["profileZToCoreZOffsetM"],
        "moscowProfileID": profile.profile_id,
        "moscowProfileSHA256": profile.provenance.canonical_sha256,
        "permanentWayStatus": production_meta["permanentWayStatus"],
        "permanentWayPresetID": production_meta.get("permanentWayPresetID"),
        "modernLVTSupportCount": production_meta.get("modernLVTSupportCount"),
        "modernLVTSupportPitchM": production_meta.get("modernLVTSupportPitchM"),
        "contactRailStatus": production_meta["contactRailStatus"],
        "contactRailPresetID": production_meta.get("contactRailPresetID"),
        "contactRailAxisProfileXM": production_meta.get(
            "contactRailAxisProfileXM"
        ),
        "contactRailWorkingSurfaceProfileZM": production_meta.get(
            "contactRailWorkingSurfaceProfileZM"
        ),
        "contactRailSupportCount": production_meta.get("contactRailSupportCount"),
        "contactSupportDrawingReferenceToAxisM": (
            profile.modern_contact_rail.drawing_reference_to_axis_m
            if args.domain_stage == "10.5"
            else None
        ),
        "contactSupportDrawingOuterEnvelopeM": (
            profile.modern_contact_rail.drawing_reference_to_outer_envelope_m
            if args.domain_stage == "10.5"
            else None
        ),
        "contactSupportDrawingUpperReturnM": (
            profile.modern_contact_rail.drawing_upper_return_m
            if args.domain_stage == "10.5"
            else None
        ),
        "contactSupportDrawingTopAboveUGRM": (
            profile.modern_contact_rail.drawing_top_above_ugr_m
            if args.domain_stage == "10.5"
            else None
        ),
        "contactSupportDrawingLowerBendCalloutM": (
            profile.modern_contact_rail.drawing_lower_bend_callout_m
            if args.domain_stage == "10.5"
            else None
        ),
        "contactSupportDrawingUpperBendCalloutM": (
            profile.modern_contact_rail.drawing_upper_bend_callout_m
            if args.domain_stage == "10.5"
            else None
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
        "contactRailTargetPitchM": production_meta.get("contactRailTargetPitchM"),
        "contactRailCoverEraMismatch": production_meta.get(
            "contactRailCoverEraMismatch"
        ),
        "civilShellStatus": production_meta["civilShellStatus"],
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
        "nonRailInfrastructureStatus": production_meta["nonRailInfrastructureStatus"],
        "serviceCableCount": production_meta.get("serviceCableCount"),
        "serviceCableRackCount": production_meta.get("serviceCableRackCount"),
        "serviceCableRackFamily": production_meta.get("serviceCableRackFamily"),
        "servicePipeStatus": production_meta.get("servicePipeStatus"),
        "serviceWaterMainCount": production_meta.get(
            "serviceWaterMainCount"
        ),
        "serviceWaterMainMinNominalDNmm": production_meta.get(
            "serviceWaterMainMinNominalDNmm"
        ),
        "productionWaterMains": len(
            build.scene.objects_of_type("production_water_main")
        ),
        "alignmentStations": len(build.alignment_stations),
        "sceneJson": None if args.chunks_only else output.name,
        "fullSceneSerialized": not args.chunks_only,
        "tunnelInstanceID": production_meta["tunnelInstanceID"],
        "infrastructureAssets": [
            {
                "persistentKey": spec.persistent_key,
                "instanceID": spec.instance_id,
                "objectType": spec.object_type,
                "category": spec.category,
            }
            for spec in build.asset_specs
        ],
    }

    if args.chunk_m is not None:
        packages = build_chunk_scene_packages(
            build,
            chunk_length_m=args.chunk_m,
            boundary_policy=ChunkBoundaryPolicy(args.chunk_policy),
            localize_coordinates=args.localize_chunks_for_blender,
        )
        chunk_dir = output.with_name(output.stem + "_chunks")
        chunk_dir.mkdir(parents=True, exist_ok=True)
        manifest = []
        for package in packages:
            chunk_meta = package.metadata["productionChunk"]
            chunk_id = int(chunk_meta["chunkID"])
            chunk_path = chunk_dir / f"chunk_{chunk_id:05d}.json"
            write_scene_package_json(package, chunk_path)
            manifest.append(
                {
                    "chunkID": chunk_id,
                    "path": chunk_path.name,
                    "startChainageM": chunk_meta["startChainageM"],
                    "endChainageM": chunk_meta["endChainageM"],
                    "ringIDs": chunk_meta["ringIDs"],
                    "vertexCoordinatesLocalized": chunk_meta[
                        "vertexCoordinatesLocalized"
                    ],
                    "chunkWorldOrigin": chunk_meta["chunkWorldOrigin"],
                }
            )
        manifest_path = chunk_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "stage": args.domain_stage,
                    "namespace": args.namespace,
                    "moscowProfileID": profile.profile_id,
                    "moscowProfileSHA256": profile.provenance.canonical_sha256,
                    "tunnelInstanceID": production_meta["tunnelInstanceID"],
                    "chunkLengthRequestedM": args.chunk_m,
                    "boundaryPolicy": args.chunk_policy,
                    "localizedForBlender": args.localize_chunks_for_blender,
                    "globalCoordinatesAreCanonical": True,
                    "infrastructureAssets": [
                        {
                            "persistentKey": spec.persistent_key,
                            "instanceID": spec.instance_id,
                            "objectType": spec.object_type,
                            "category": spec.category,
                        }
                        for spec in build.asset_specs
                    ],
                    "chunks": manifest,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        summary.update(
            {
                "chunkCount": len(packages),
                "chunkLengthRequestedM": args.chunk_m,
                "chunkPolicy": args.chunk_policy,
                "chunksLocalizedForBlender": args.localize_chunks_for_blender,
                "chunkManifest": str(manifest_path.relative_to(output.parent)),
            }
        )

    summary_path = output.with_name(output.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
