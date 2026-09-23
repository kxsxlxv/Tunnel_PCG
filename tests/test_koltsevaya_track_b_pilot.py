from __future__ import annotations

import json
import math
from pathlib import Path

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
    assert chunk.objects_of_type("lining_segment")
    assert chunk.objects_of_type("production_lvt_block")
    assert chunk.objects_of_type("production_rail")
    assert chunk.metadata["productionChunk"]["vertexCoordinatesLocalized"] is True

    vertices = [
        vertex
        for obj in chunk.objects_of_type("lining_segment")
        for vertex in obj.vertices
    ]
    assert vertices
    assert all(
        math.isfinite(component)
        for vertex in vertices
        for component in vertex
    )
