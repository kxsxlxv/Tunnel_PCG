from __future__ import annotations

import json
import math
from pathlib import Path
import subprocess
import sys

from tunnel_scanner_core import (
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    RingConfig,
    RingRotationStrategy,
    SurfaceMeshingConfig,
    TunnelAssemblyConfig,
    build_stage10_5_rc_modern_chunk_plan,
    build_stage10_5_rc_modern_chunk_scene_package,
    load_frame_alignment_geojson,
    load_stage10_initial_moscow_profile,
)


ROOT = Path(__file__).resolve().parents[1]
RESEARCH = (
    ROOT
    / "research"
    / "moscow_metro_tunnels"
    / "examples"
    / "koltsevaya_line_v0"
)
ALIGNMENT = (
    RESEARCH
    / "koltsevaya_track_b_belorusskaya_park_kultury_geometry_test_3d.geojson"
)
HANDOFF = (
    RESEARCH
    / "koltsevaya_track_b_belorusskaya_park_kultury_handoff.json"
)


def test_koltsevaya_track_b_geometry_test_alignment_contract():
    handoff = json.loads(HANDOFF.read_text(encoding="utf-8"))
    stations = load_frame_alignment_geojson(
        ALIGNMENT,
        expected_track_id="KOLTSEVAYA_TRACK_B",
        expected_direction="counterclockwise",
    )

    assert len(stations) == 257
    assert math.isclose(stations[0].chainage_m, 0.0, abs_tol=1e-12)
    assert math.isclose(
        stations[-1].chainage_m,
        5947.519,
        abs_tol=1e-6,
    )
    assert stations[0].offset_z_m == -42.5
    assert stations[-1].offset_z_m == -40.0
    assert handoff["scope"]["engineering_z_status"] == "Z_UNRESOLVED"
    assert handoff["scope"]["track_id"] == "KOLTSEVAYA_TRACK_B"
    assert handoff["scope"]["direction"] == "counterclockwise"


def test_koltsevaya_unigine_spline_only_skips_chunk_generation(tmp_path):
    output = tmp_path / "koltsevaya_refresh.json"
    script = ROOT / "examples" / "generate_koltsevaya_track_b_pilot.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--unigine-spline-only",
            "--output",
            str(output),
        ],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    spline = output.with_name(output.stem + "_track.spl")
    summary_path = output.with_name(output.stem + "_summary.json")
    chunk_dir = output.with_name(output.stem + "_chunks")

    assert spline.is_file()
    assert summary_path.is_file()
    assert not output.exists()
    assert not chunk_dir.exists()

    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    stdout_summary = json.loads(completed.stdout)
    assert stdout_summary == summary
    assert summary["mode"] == "unigine_spline_only"
    assert summary["chunkGenerationSkipped"] is True
    assert summary["chunkManifest"] is None
    assert summary["sceneJson"] is None
    assert summary["unigineRailSpline"] == spline.name
    assert summary["unigineRailSplineDatum"] == "TRACK_AXIS_UGR"
    assert math.isclose(
        summary["unigineRailSplineLocalZOffsetM"],
        -1.67,
        abs_tol=1e-12,
    )


def test_koltsevaya_track_b_first_chunk_builds_on_frame_aware_route():
    stations = load_frame_alignment_geojson(
        ALIGNMENT,
        expected_track_id="KOLTSEVAYA_TRACK_B",
        expected_direction="counterclockwise",
    )
    route_length = stations[-1].chainage_m
    nominal_width = 1.35
    n_rings = math.ceil(route_length / nominal_width)
    scaffold_width = route_length / n_rings

    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    plan = build_stage10_5_rc_modern_chunk_plan(
        chunk_length_m=5.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        ring_config=RingConfig(width_m=scaffold_width),
        assembly_config=TunnelAssemblyConfig(
            n_rings=n_rings,
            ring_width_m=scaffold_width,
            displacement_amplitude_m=0.0,
            axis_noise_sigma_m=0.0,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=0.002),
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(
            namespace="koltsevaya-track-b-ci-first-chunk",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_service_preset="modern",
            moscow_civil_topology="kba",
            mesh_cluster_identical_civil_rings=True,
        ),
        seed=5812,
        alignment_stations=stations,
        alignment_metadata={
            "trackID": "KOLTSEVAYA_TRACK_B",
            "direction": "counterclockwise",
            "runtimeVerticalStatus": (
                "SYNTHETIC_GEOMETRY_TEST_ONLY_NOT_AS_BUILT"
            ),
        },
    )
    meta = plan.metadata["productionGeometry"]
    assert meta["externalAlignment"] is True
    assert meta["alignmentFrameAware"] is True
    assert (
        meta["externalAlignmentInterpolation"]
        == "cubic_hermite_c1_between_source_samples"
    )
    assert math.isclose(
        meta["runningRailCurveChordToleranceM"],
        0.002,
        abs_tol=1e-12,
    )
    assert math.isclose(
        plan.assembly.length_by_chainage_m,
        route_length,
        abs_tol=1e-9,
    )

    chunk = build_stage10_5_rc_modern_chunk_scene_package(
        plan,
        0,
        localize_coordinates=True,
    )
    rings = chunk.objects_of_type("production_moscow_civil_ring_cluster")
    assert rings
    assert chunk.objects_of_type("lining_segment") == ()
    assert chunk.objects_of_type("production_lvt_block")
    assert chunk.objects_of_type("production_rail")
    winding_types = {
        "production_track_concrete",
        "production_rail",
        "production_moscow_walkway",
        "production_service_cable",
        "production_cable_rack_r2k11",
        "production_water_main",
        "production_contact_rail_bracket",
        "production_contact_rail_cover_span",
        "production_contact_rail",
    }
    present_winding_types = {
        obj.object_type for obj in chunk.objects
        if obj.object_type in winding_types
    }
    assert present_winding_types
    for obj in chunk.objects:
        if obj.object_type in present_winding_types:
            assert obj.custom_properties["faceOrientationInverted"] is True
            assert (
                obj.custom_properties["faceOrientationPolicy"]
                == "stage10_requested_reverse_winding_v1"
            )
    assert chunk.metadata["faceOrientationPolicy"][
        "geometryCoordinatesChanged"
    ] is False
    assert chunk.metadata["productionChunk"]["vertexCoordinatesLocalized"] is True

    vertices = [
        vertex
        for obj in rings
        for vertex in obj.vertices
    ]
    assert vertices
    assert all(
        math.isfinite(component)
        for vertex in vertices
        for component in vertex
    )

    # Around chainage 300 m the geometry-test alignment is visibly curved.
    # A 5 m chunk must no longer be represented by one straight rail chord.
    curved_chunk = build_stage10_5_rc_modern_chunk_scene_package(
        plan,
        60,
        localize_coordinates=True,
    )
    curved_rail = curved_chunk.objects_of_type("production_rail")[0]
    assert math.isclose(
        curved_rail.custom_properties["longitudinalCurveChordToleranceM"],
        0.002,
        abs_tol=1e-12,
    )
    assert curved_rail.custom_properties[
        "smoothExternalAlignmentInterpolation"
    ] is True
    assert (
        curved_rail.custom_properties["curveRefinedAlignmentStationCount"]
        > curved_rail.custom_properties["sourceAlignmentStationCount"]
    )
