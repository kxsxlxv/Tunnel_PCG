import json
import math

import numpy as np

import tunnel_scanner_core.production as production_module

from tunnel_scanner_core import (
    AlignmentStation,
    AncillaryConfig,
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    RailProfile,
    RingConfig,
    RingRotationStrategy,
    TunnelAssemblyConfig,
    alignment_station_frame,
    audit_exact_coincident_faces,
    build_chunk_scene_packages,
    build_production_tunnel,
    iter_chunk_scene_packages,
    clipped_alignment_stations,
    load_frame_alignment_geojson,
    build_procedural_nominal_tunnel,
    finalize_production_render_scene,
    plan_chunks,
    production_alignment_stations,
    sample_tunnel_assembly,
    sample_alignment_station,
    stable_instance_id,
    transform_alignment_local_point,
    strip_exact_coincident_lining_interface_faces,
    strip_internal_lining_cap_faces,
    strip_lining_segment_boundary_faces,
)


def _production(
    n_rings=5,
    *,
    namespace="test-tunnel",
    include_bolts=False,
    axis_noise_sigma_m=0.005,
):
    return build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=n_rings,
            ring_width_m=1.35,
            axis_noise_sigma_m=axis_noise_sigma_m,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        include_bolts=include_bolts,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(namespace=namespace),
        seed=5812,
    )


def test_alignment_frame_identity_preserves_legacy_xyz_mapping():
    station = AlignmentStation(
        chainage_m=0.0,
        world_y_m=20.0,
        offset_x_m=10.0,
        offset_z_m=30.0,
        source="identity",
    )
    assert transform_alignment_local_point(
        station,
        2.0,
        3.0,
        4.0,
    ) == (12.0, 23.0, 34.0)


def test_alignment_frame_rotates_local_y_to_route_tangent_without_roll():
    station = AlignmentStation(
        chainage_m=0.0,
        world_y_m=20.0,
        offset_x_m=10.0,
        offset_z_m=30.0,
        source="turn-east",
        tangent_world=(1.0, 0.0, 0.0),
    )
    right, tangent, up = alignment_station_frame(station)
    assert right == (0.0, -1.0, 0.0)
    assert tangent == (1.0, 0.0, 0.0)
    assert up == (0.0, 0.0, 1.0)
    assert transform_alignment_local_point(
        station,
        2.0,
        3.0,
        4.0,
    ) == (13.0, 18.0, 34.0)


def test_load_frame_alignment_geojson_uses_explicit_chainage_and_3d_tangent(
    tmp_path,
):
    path = tmp_path / "alignment.geojson"
    path.write_text(
        json.dumps(
            {
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "properties": {
                            "track_id": "TRACK_B",
                            "direction": "counterclockwise",
                            "vertex_chainage_m": [0.0, 100.0, 200.0],
                        },
                        "geometry": {
                            "type": "LineString",
                            "coordinates": [
                                [37.0, 55.0, -40.0],
                                [37.001, 55.0, -39.0],
                                [37.002, 55.001, -38.0],
                            ],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    stations = load_frame_alignment_geojson(
        path,
        expected_track_id="TRACK_B",
        expected_direction="counterclockwise",
    )
    assert [station.chainage_m for station in stations] == [
        0.0,
        100.0,
        200.0,
    ]
    assert math.isclose(stations[0].offset_x_m, 0.0, abs_tol=1e-9)
    assert math.isclose(stations[0].world_y_m, 0.0, abs_tol=1e-9)
    assert stations[0].offset_z_m == -40.0
    assert stations[-1].offset_z_m == -38.0
    for station in stations:
        right, tangent, up = alignment_station_frame(station)
        assert math.isclose(
            sum(value * value for value in tangent),
            1.0,
            abs_tol=1e-12,
        )
        assert math.isclose(
            sum(right[i] * tangent[i] for i in range(3)),
            0.0,
            abs_tol=1e-12,
        )
        assert math.isclose(
            sum(up[i] * tangent[i] for i in range(3)),
            0.0,
            abs_tol=1e-12,
        )


def test_external_alignment_sampling_uses_c1_cubic_hermite_between_vertices():
    quarter_turn_length = 0.5 * math.pi
    stations = (
        AlignmentStation(
            chainage_m=0.0,
            world_y_m=0.0,
            offset_x_m=1.0,
            offset_z_m=0.0,
            source="external_geojson:test:vertex_0000",
            tangent_world=(0.0, 1.0, 0.0),
        ),
        AlignmentStation(
            chainage_m=quarter_turn_length,
            world_y_m=1.0,
            offset_x_m=0.0,
            offset_z_m=0.0,
            source="external_geojson:test:vertex_0001",
            tangent_world=(-1.0, 0.0, 0.0),
        ),
    )
    middle = sample_alignment_station(
        stations,
        0.5 * quarter_turn_length,
    )
    assert middle.source.startswith("external_cubic_hermite:")
    assert middle.offset_x_m > 0.68
    assert middle.world_y_m > 0.68
    assert math.isclose(
        math.hypot(middle.offset_x_m, middle.world_y_m),
        1.0,
        abs_tol=0.02,
    )
    assert middle.offset_x_m - 0.5 > 0.15
    assert middle.world_y_m - 0.5 > 0.15


def test_external_curve_sweep_refinement_is_error_driven_and_legacy_safe():
    quarter_turn_length = 0.5 * math.pi * 300.0
    external = (
        AlignmentStation(
            chainage_m=0.0,
            world_y_m=0.0,
            offset_x_m=300.0,
            offset_z_m=0.0,
            source="external_geojson:test:vertex_0000",
            tangent_world=(0.0, 1.0, 0.0),
        ),
        AlignmentStation(
            chainage_m=quarter_turn_length,
            world_y_m=300.0,
            offset_x_m=0.0,
            offset_z_m=0.0,
            source="external_geojson:test:vertex_0001",
            tangent_world=(-1.0, 0.0, 0.0),
        ),
    )
    coarse = production_module.refine_external_alignment_for_sweep(
        external,
        max_chord_error_m=0.010,
    )
    rail = production_module.refine_external_alignment_for_sweep(
        external,
        max_chord_error_m=0.002,
    )
    assert len(coarse) > len(external)
    assert len(rail) > len(coarse)

    legacy = (
        AlignmentStation(0.0, 0.0, 0.0, 0.0, "legacy-a"),
        AlignmentStation(25.0, 25.0, 0.0, 0.0, "legacy-b"),
    )
    assert (
        production_module.refine_external_alignment_for_sweep(
            legacy,
            max_chord_error_m=0.002,
        )
        == legacy
    )


def test_stable_instance_ids_are_deterministic_positive_and_key_sensitive():
    a = stable_instance_id("tunnel/a/rail/0")
    b = stable_instance_id("tunnel/a/rail/0")
    c = stable_instance_id("tunnel/a/rail/1")
    assert a == b
    assert a > 0
    assert a < 2**63
    assert a != c


def test_generic_rail_profile_is_symmetric_low_poly_and_preserves_envelope():
    cfg = AncillaryConfig.reference(3.0)
    profile = RailProfile.generic_from_ancillary(cfg)
    points = profile.points_xz(center_x_m=0.0, base_z_m=-2.25)

    assert len(points) == 16
    xs = [p[0] for p in points]
    zs = [p[1] for p in points]
    assert math.isclose(max(xs) - min(xs), cfg.rail_width_m, abs_tol=1e-12)
    assert math.isclose(max(zs) - min(zs), cfg.rail_depth_m, abs_tol=1e-12)

    # Mirror symmetry about the rail centreline.
    mirrored = {(round(-x, 12), round(z, 12)) for x, z in points}
    original = {(round(x, 12), round(z, 12)) for x, z in points}
    assert mirrored == original

    assert profile.web_thickness_m < profile.head_width_m < profile.foot_width_m
    assert profile.head_height_m > profile.foot_height_m


def test_production_scene_replaces_ring_local_ancillary_with_ten_global_assets():
    prod = _production(5)
    assert not any(
        obj.object_type.startswith("ancillary_") for obj in prod.scene.objects
    )
    assert len(prod.scene.objects_of_type("production_pavement")) == 1
    assert len(prod.scene.objects_of_type("production_walkway")) == 1
    assert len(prod.scene.objects_of_type("production_rail")) == 2
    assert len(prod.scene.objects_of_type("production_tube")) == 6

    for obj in (
        *prod.scene.objects_of_type("production_pavement"),
        *prod.scene.objects_of_type("production_walkway"),
        *prod.scene.objects_of_type("production_rail"),
        *prod.scene.objects_of_type("production_tube"),
    ):
        assert obj.custom_properties["productionContinuous"] is True
        assert obj.custom_properties["sourceRingScope"] == "global"
        assert obj.custom_properties["persistentInstanceID"] == obj.instance_id
        assert obj.collection_path[:3] == ("Tunnel", "test-tunnel", "Infrastructure")


def test_production_rails_use_rail_profile_not_rectangles():
    prod = _production(3)
    rails = prod.scene.objects_of_type("production_rail")
    assert len(rails) == 2
    for rail in rails:
        props = rail.custom_properties
        assert props["railProfile"] == "stage9_generic_lowpoly_16"
        assert props["railProfileVertices"] == 16
        assert props["railWebThicknessM"] < props["railHeadWidthM"]
        assert props["railHeadWidthM"] < props["railFootWidthM"]
        assert props["productionCrossSectionVertices"] == 16


def test_alignment_has_front_center_boundaries_and_end_with_exact_total_length():
    prod = _production(5, axis_noise_sigma_m=0.0)
    stations = production_alignment_stations(prod.assembly)
    assert len(stations) == 2 * 5 + 1
    assert stations[0].chainage_m == 0.0
    assert math.isclose(stations[-1].chainage_m, 5 * 1.35, abs_tol=1e-12)
    assert math.isclose(stations[0].world_y_m, -0.675, abs_tol=1e-12)
    assert math.isclose(stations[-1].world_y_m, 5.4 + 0.675, abs_tol=1e-12)


def test_alignment_sampling_snaps_only_ulp_scale_fuzz_at_3000_ring_end():
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=3000,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        seed=5812,
    )
    stations = production_alignment_stations(assembly)
    end = stations[-1].chainage_m
    assert end > 4000.0

    # Reproduce the scale of the Stage-10 Moscow civil-ring composition bug:
    # a mathematically identical tunnel-end chainage may land a handful of
    # floating-point ulps outside the station range.
    fuzzed_end = end
    for _ in range(8):
        fuzzed_end = math.nextafter(fuzzed_end, math.inf)
    sampled = sample_alignment_station(stations, fuzzed_end)
    assert sampled is stations[-1]

    # The tolerance is numerical only; a material overrun must still fail.
    try:
        sample_alignment_station(stations, end + 1e-6)
    except ValueError as exc:
        assert "chainage outside station range" in str(exc)
    else:
        raise AssertionError("material chainage overrun was incorrectly accepted")


def test_clipped_alignment_stations_matches_legacy_scan_without_full_iteration():
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=3000,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        seed=5812,
    )
    stations = production_alignment_stations(assembly)
    start = 1234.125
    end = 1267.875
    tol = 1e-10

    expected = (
        sample_alignment_station(stations, start),
        *tuple(
            station
            for station in stations
            if (
                station.chainage_m > start + tol
                and station.chainage_m < end - tol
            )
        ),
        sample_alignment_station(stations, end),
    )

    class IndexedOnlyStations:
        def __len__(self):
            return len(stations)

        def __getitem__(self, index):
            if isinstance(index, slice):
                raise AssertionError("clipped lookup must not slice the full station set")
            return stations[index]

        def __iter__(self):
            raise AssertionError("clipped lookup must not scan every alignment station")

    actual = clipped_alignment_stations(
        IndexedOnlyStations(),
        start_chainage_m=start,
        end_chainage_m=end,
    )
    assert actual == expected


def test_stage8_ring_local_ancillary_contains_duplicate_internal_caps_but_stage9_does_not():
    cfg = TunnelAssemblyConfig(
        n_rings=4,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
    )
    stage8 = build_procedural_nominal_tunnel(
        assembly_config=cfg,
        include_bolts=False,
        include_ancillary=True,
        label_policy=LabelPolicy.STSD_COARSE,
        seed=33,
    )
    audit8 = audit_exact_coincident_faces(
        stage8.scene,
        object_filter=lambda obj: obj.object_type.startswith("ancillary_"),
    )
    # 10 logical ancillary assets across 3 internal ring boundaries.
    assert audit8.duplicate_group_count == 30

    stage9 = build_production_tunnel(
        assembly_config=cfg,
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(namespace="topology-test"),
        seed=33,
    )
    audit9 = audit_exact_coincident_faces(
        stage9.scene,
        object_filter=lambda obj: obj.object_type.startswith("production_"),
    )
    assert audit9.duplicate_group_count == 0


def test_full_production_assets_have_only_two_end_caps_each():
    prod = _production(5)
    for obj in prod.scene.objects:
        if not obj.object_type.startswith("production_"):
            continue
        assert obj.custom_properties["capStart"] is True
        assert obj.custom_properties["capEnd"] is True
        n = obj.custom_properties["productionCrossSectionVertices"]
        station_count = obj.custom_properties["productionStationCount"]
        omitted = obj.custom_properties["omittedLongitudinalEdgeCount"]
        expected_side_faces = (station_count - 1) * (n - omitted)
        assert len(obj.faces) == expected_side_faces + 2


def test_exact_length_chunk_plan_matches_legacy_full_ring_scan():
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=3000,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        seed=5812,
    )
    chunk_length = 17.3
    chunks = plan_chunks(
        assembly,
        chunk_length_m=chunk_length,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )
    total = assembly.length_by_chainage_m
    L = assembly.config.ring_width_m

    for chunk in chunks:
        expected = tuple(
            i
            for i in range(assembly.config.n_rings)
            if chunk.start_chainage_m <= (i + 0.5) * L < chunk.end_chainage_m
            or (
                math.isclose(chunk.end_chainage_m, total, abs_tol=1e-12)
                and math.isclose(
                    (i + 0.5) * L,
                    chunk.end_chainage_m,
                    abs_tol=1e-12,
                )
            )
        )
        assert chunk.ring_ids == expected


def test_chunk_plan_is_optional_and_global_coordinates_are_preserved():
    prod = _production(12)
    chunks = plan_chunks(
        prod.assembly,
        chunk_length_m=5.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )
    assert len(chunks) == math.ceil(prod.assembly.length_by_chainage_m / 5.0)
    packages = build_chunk_scene_packages(
        prod,
        chunk_length_m=5.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )

    assert len(packages) == len(chunks)
    for package, chunk in zip(packages, chunks):
        meta = package.metadata["productionChunk"]
        assert meta["globalCoordinatesPreserved"] is True
        assert meta["internalLongitudinalCaps"] is False
        assert meta["startChainageM"] == chunk.start_chainage_m
        assert meta["endChainageM"] == chunk.end_chainage_m


def test_lazy_chunk_iterator_matches_materialized_wrapper_exactly():
    prod = _production(12)
    for policy, localize in (
        (ChunkBoundaryPolicy.EXACT_LENGTH, False),
        (ChunkBoundaryPolicy.RING_ALIGNED, True),
    ):
        lazy = tuple(
            iter_chunk_scene_packages(
                prod,
                chunk_length_m=5.0,
                boundary_policy=policy,
                localize_coordinates=localize,
            )
        )
        materialized = build_chunk_scene_packages(
            prod,
            chunk_length_m=5.0,
            boundary_policy=policy,
            localize_coordinates=localize,
        )
        assert lazy == materialized


def test_internal_chunk_boundaries_have_no_coincident_end_caps():
    prod = _production(12)
    packages = build_chunk_scene_packages(
        prod,
        chunk_length_m=5.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )
    total = prod.assembly.length_by_chainage_m

    for package in packages:
        for obj in package.objects:
            if not obj.object_type.startswith("production_"):
                continue
            start = obj.custom_properties["chunkStartChainageM"]
            end = obj.custom_properties["chunkEndChainageM"]
            assert obj.custom_properties["capStart"] is math.isclose(
                start, 0.0, abs_tol=1e-12
            )
            assert obj.custom_properties["capEnd"] is math.isclose(
                end, total, abs_tol=1e-12
            )


def test_chunk_piece_boundaries_are_geometrically_identical():
    prod = _production(12)
    packages = build_chunk_scene_packages(prod, chunk_length_m=5.0)

    for left_pkg, right_pkg in zip(packages, packages[1:]):
        left_assets = {
            obj.custom_properties["sourcePersistentKey"]: obj
            for obj in left_pkg.objects
            if obj.object_type.startswith("production_")
        }
        right_assets = {
            obj.custom_properties["sourcePersistentKey"]: obj
            for obj in right_pkg.objects
            if obj.object_type.startswith("production_")
        }
        assert left_assets.keys() == right_assets.keys()
        for key in left_assets:
            left = left_assets[key]
            right = right_assets[key]
            n = left.custom_properties["productionCrossSectionVertices"]
            assert n == right.custom_properties["productionCrossSectionVertices"]
            assert np.allclose(
                np.asarray(left.vertices[-n:]),
                np.asarray(right.vertices[:n]),
                atol=2e-12,
                rtol=0,
            )


def test_source_asset_identity_is_independent_of_chunk_length():
    prod = _production(20)
    a = build_chunk_scene_packages(prod, chunk_length_m=7.0)
    b = build_chunk_scene_packages(prod, chunk_length_m=11.0)

    source_ids_a = {
        obj.custom_properties["sourcePersistentKey"]: obj.custom_properties[
            "sourceInstanceID"
        ]
        for package in a
        for obj in package.objects
        if obj.object_type.startswith("production_")
    }
    source_ids_b = {
        obj.custom_properties["sourcePersistentKey"]: obj.custom_properties[
            "sourceInstanceID"
        ]
        for package in b
        for obj in package.objects
        if obj.object_type.startswith("production_")
    }
    assert source_ids_a == source_ids_b
    assert len(source_ids_a) == 10


def test_ring_object_persistent_ids_do_not_change_when_scene_gets_longer():
    short = _production(5, namespace="same-route")
    long = _production(10, namespace="same-route")

    short_ring0 = {
        obj.name: obj.instance_id
        for obj in short.scene.objects
        if obj.ring_id == 0 and not obj.object_type.startswith("production_")
    }
    long_ring0 = {
        obj.name: obj.instance_id
        for obj in long.scene.objects
        if obj.ring_id == 0 and not obj.object_type.startswith("production_")
    }
    assert short_ring0 == long_ring0


def test_namespace_separates_persistent_id_spaces():
    a = _production(3, namespace="route-A")
    b = _production(3, namespace="route-B")
    ids_a = {obj.instance_id for obj in a.scene.objects}
    ids_b = {obj.instance_id for obj in b.scene.objects}
    assert ids_a.isdisjoint(ids_b)


def test_production_scene_instance_ids_are_unique_with_bolts():
    prod = _production(8, include_bolts=True)
    ids = [obj.instance_id for obj in prod.scene.objects]
    assert len(ids) == len(set(ids))


def test_one_kilometre_alignment_uses_global_double_coordinates_without_rebasing():
    ring_width = 1.35
    n = math.ceil(1000.0 / ring_width)
    prod = _production(
        n,
        namespace="kilometre",
        include_bolts=False,
        axis_noise_sigma_m=0.0,
    )
    assert prod.assembly.length_by_chainage_m >= 1000.0
    assert prod.assembly.length_by_chainage_m < 1000.0 + ring_width

    rails = prod.scene.objects_of_type("production_rail")
    assert len(rails) == 2
    max_y = max(v[1] for rail in rails for v in rail.vertices)
    min_y = min(v[1] for rail in rails for v in rail.vertices)
    assert max_y - min_y >= 1000.0
    assert max_y > 999.0
    assert prod.scene.metadata["productionGeometry"]["globalCoordinates"] is True
    assert "no mandatory rebasing" in prod.scene.metadata["productionGeometry"][
        "coordinatePrecisionIntent"
    ]


def test_production_hierarchy_is_deterministic_and_semantic():
    prod = _production(3, namespace="hierarchy")
    for obj in prod.scene.objects:
        assert obj.collection_path[0:2] == ("Tunnel", "hierarchy")
        assert "persistentKey" in obj.custom_properties
        assert obj.custom_properties["persistentInstanceID"] > 0


def test_default_chunking_keeps_complete_rings_and_ring_aligned_boundaries():
    prod = _production(20)
    chunks = plan_chunks(prod.assembly, chunk_length_m=5.0)
    L = prod.assembly.config.ring_width_m
    for chunk in chunks:
        assert math.isclose(chunk.start_chainage_m / L, round(chunk.start_chainage_m / L), abs_tol=1e-12)
        assert math.isclose(chunk.end_chainage_m / L, round(chunk.end_chainage_m / L), abs_tol=1e-12)
        if chunk.ring_ids:
            assert chunk.ring_ids == tuple(range(chunk.ring_ids[0], chunk.ring_ids[-1] + 1))
            for ring_id in chunk.ring_ids:
                assert chunk.start_chainage_m <= ring_id * L
                assert (ring_id + 1) * L <= chunk.end_chainage_m + 1e-12


def test_exact_length_chunking_remains_available_for_blender_or_export_tools():
    prod = _production(10)
    chunks = plan_chunks(
        prod.assembly,
        chunk_length_m=5.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )
    assert math.isclose(chunks[0].length_m, 5.0, abs_tol=1e-12)
    assert not math.isclose(chunks[0].end_chainage_m / 1.35, round(chunks[0].end_chainage_m / 1.35), abs_tol=1e-12)


def test_internal_lining_caps_can_be_stripped_after_boolean_tools_are_absent():
    prod = _production(4, include_bolts=False, axis_noise_sigma_m=0.0)
    before_faces = sum(
        len(obj.faces) for obj in prod.scene.objects_of_type("lining_segment")
    )
    cleaned = strip_internal_lining_cap_faces(prod.scene)
    after_faces = sum(
        len(obj.faces) for obj in cleaned.objects_of_type("lining_segment")
    )
    assert after_faces < before_faces
    assert cleaned.metadata["productionLiningCapStrip"]["removedFaces"] > 0

    L = prod.assembly.config.ring_width_m
    internal_boundaries = {0.5 * L, 1.5 * L, 2.5 * L}
    for obj in cleaned.objects_of_type("lining_segment"):
        for face in obj.faces:
            ys = [obj.vertices[index][1] for index in face]
            for boundary in internal_boundaries:
                assert not all(abs(y - boundary) < 1e-9 for y in ys)


def test_lining_cap_strip_refuses_pre_boolean_scene_with_cutters():
    prod = _production(2, include_bolts=True)
    try:
        strip_internal_lining_cap_faces(prod.scene)
    except ValueError as exc:
        assert "after bolt cutters are baked" in str(exc)
    else:
        raise AssertionError("cap stripping before Boolean bake must be rejected")


def test_lining_cap_strip_preserves_tunnel_outer_end_caps():
    prod = _production(3, include_bolts=False, axis_noise_sigma_m=0.0)
    cleaned = strip_internal_lining_cap_faces(prod.scene)
    L = prod.assembly.config.ring_width_m
    front_y = -0.5 * L
    back_y = (3 - 0.5) * L

    first = [o for o in cleaned.objects_of_type("lining_segment") if o.ring_id == 0]
    last = [o for o in cleaned.objects_of_type("lining_segment") if o.ring_id == 2]
    assert any(
        all(abs(obj.vertices[i][1] - front_y) < 1e-9 for i in face)
        for obj in first
        for face in obj.faces
    )
    assert any(
        all(abs(obj.vertices[i][1] - back_y) < 1e-9 for i in face)
        for obj in last
        for face in obj.faces
    )


def test_hidden_contact_faces_are_omitted_from_production_pavement_and_rails():
    prod = _production(4)
    pavement = prod.scene.objects_of_type("production_pavement")[0]
    rails = prod.scene.objects_of_type("production_rail")
    assert pavement.custom_properties["omittedLongitudinalEdgeCount"] > 0
    assert pavement.custom_properties["contactSurfacePolicy"] == "hidden_coplanar_contact_faces_omitted"
    for rail in rails:
        assert rail.custom_properties["omittedLongitudinalEdgeCount"] == 1
        assert rail.custom_properties["contactSurfacePolicy"] == "hidden_coplanar_contact_faces_omitted"

    for tube in prod.scene.objects_of_type("production_tube"):
        assert tube.custom_properties["omittedLongitudinalEdgeCount"] == 0


def test_localized_chunks_preserve_world_origin_and_source_ids():
    prod = _production(12, namespace="localized")
    global_chunks = build_chunk_scene_packages(
        prod,
        chunk_length_m=5.0,
        boundary_policy=ChunkBoundaryPolicy.RING_ALIGNED,
        localize_coordinates=False,
    )
    local_chunks = build_chunk_scene_packages(
        prod,
        chunk_length_m=5.0,
        boundary_policy=ChunkBoundaryPolicy.RING_ALIGNED,
        localize_coordinates=True,
    )
    assert len(global_chunks) == len(local_chunks)

    for global_pkg, local_pkg in zip(global_chunks, local_chunks):
        meta = local_pkg.metadata["productionChunk"]
        assert meta["vertexCoordinatesLocalized"] is True
        ox, oy, oz = meta["chunkWorldOrigin"]
        assert meta["worldTransformRestoresGlobalCoordinates"] is True

        global_by_name = {obj.name: obj for obj in global_pkg.objects}
        local_by_name = {obj.name: obj for obj in local_pkg.objects}
        assert global_by_name.keys() == local_by_name.keys()
        for name in global_by_name:
            g = global_by_name[name]
            l = local_by_name[name]
            assert g.instance_id == l.instance_id
            assert g.faces == l.faces
            restored = np.asarray(l.vertices) + np.asarray((ox, oy, oz))
            assert np.allclose(restored, np.asarray(g.vertices), atol=2e-12, rtol=0)


def test_global_production_scene_never_requires_chunk_localization():
    prod = _production(100, namespace="global-double")
    assert prod.scene.metadata["productionGeometry"]["globalCoordinates"] is True
    assert all(
        not obj.custom_properties.get("coordinatesLocalizedToChunk", False)
        for obj in prod.scene.objects
    )


def test_production_default_omits_hidden_stage4_outer_joint_solids():
    prod = _production(4, include_bolts=False)
    assert len(prod.scene.objects_of_type("prescribed_radial_joint")) == 0
    assert len(prod.scene.objects_of_type("prescribed_circumferential_joint")) == 0
    assert prod.scene.metadata["productionGeometry"]["prescribedOuterJointSolidsRemoved"] is True


def test_production_can_keep_stage4_outer_joint_solids_for_debugging():
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=3,
            ring_width_m=1.35,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="keep-joints",
            keep_prescribed_outer_joint_solids=True,
        ),
        seed=5812,
    )
    assert len(build.scene.objects_of_type("prescribed_radial_joint")) == 18
    assert len(build.scene.objects_of_type("prescribed_circumferential_joint")) == 12


def test_segment_boundary_cleanup_is_independent_of_neighbour_tessellation():
    prod = _production(5, include_bolts=False, axis_noise_sigma_m=0.0)
    before = audit_exact_coincident_faces(
        prod.scene,
        object_filter=lambda obj: obj.object_type == "lining_segment",
    )
    # Exact polygon matching deliberately under-counts when neighbours use
    # different longitudinal subdivisions.
    assert before.duplicate_group_count > 0

    stripped = strip_lining_segment_boundary_faces(prod.scene)
    after = audit_exact_coincident_faces(
        stripped,
        object_filter=lambda obj: obj.object_type == "lining_segment",
    )
    assert after.duplicate_group_count == 0
    meta = stripped.metadata["productionSegmentBoundaryStrip"]
    assert meta["tessellationIndependent"] is True
    assert meta["objectsAffected"] == 5 * 6
    # Two radial sides per segment, with one or more longitudinal faces each.
    assert meta["facesRemoved"] >= 5 * 6 * 2


def test_full_production_render_finalizer_reaches_zero_exact_duplicate_faces():
    prod = _production(5, include_bolts=False, axis_noise_sigma_m=0.0)
    finalized = finalize_production_render_scene(prod.scene)
    audit = audit_exact_coincident_faces(finalized)
    assert audit.duplicate_group_count == 0
    assert finalized.metadata["productionLiningCapStrip"]["removedFaces"] > 0
    assert finalized.metadata["productionSegmentBoundaryStrip"]["facesRemoved"] >= 60


def test_full_render_finalizer_refuses_unbaked_bolt_tools():
    prod = _production(2, include_bolts=True)
    try:
        finalize_production_render_scene(prod.scene)
    except ValueError as exc:
        assert "after bolt cutters are baked" in str(exc)
    else:
        raise AssertionError("render finalization before Boolean bake must be rejected")


def test_stitched_lining_ring_boundaries_share_one_physical_cross_section_centre():
    prod = _production(
        6,
        include_bolts=False,
        axis_noise_sigma_m=0.005,
    )
    r = RingConfig().inner_radius_m
    R = RingConfig().outer_radius_m
    L = prod.assembly.config.ring_width_m

    for boundary_index in range(1, prod.assembly.config.n_rings):
        chainage = boundary_index * L
        station = next(
            s
            for s in prod.alignment_stations
            if math.isclose(s.chainage_m, chainage, abs_tol=1e-12)
        )
        world_y = station.world_y_m
        for ring_id in (boundary_index - 1, boundary_index):
            boundary_vertices = []
            for obj in prod.scene.objects_of_type("lining_segment"):
                if obj.ring_id != ring_id:
                    continue
                boundary_vertices.extend(
                    v
                    for v in obj.vertices
                    if math.isclose(v[1], world_y, abs_tol=1e-10)
                )
            assert boundary_vertices
            max_radial_error = 0.0
            for x, _y, z in boundary_vertices:
                rho = math.hypot(
                    x - station.offset_x_m,
                    z - station.offset_z_m,
                )
                max_radial_error = max(
                    max_radial_error,
                    min(abs(rho - r), abs(rho - R)),
                )
            assert max_radial_error < 2e-12


def test_production_stitches_bolt_tools_with_the_same_ring_alignment_map():
    prod = _production(3, include_bolts=True)
    for object_type in ("lining_segment", "bolt_pocket_cutter", "bolt_head"):
        objects = prod.scene.objects_of_type(object_type)
        assert objects
        assert all(
            obj.custom_properties["productionRingAlignmentStitched"] is True
            for obj in objects
        )


def test_rigid_ring_debug_mode_remains_available():
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=3,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.005,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="rigid-debug",
            stitch_ring_geometry=False,
        ),
        seed=5812,
    )
    assert build.scene.metadata["productionGeometry"]["ringGeometryStitchedToAlignment"] is False
    assert all(
        "productionRingAlignmentStitched" not in obj.custom_properties
        for obj in build.scene.objects_of_type("lining_segment")
    )


def test_tunnel_and_infrastructure_ids_are_stable_semantic_parents():
    prod = _production(4, namespace="identity-contract")
    tunnel_id = prod.scene.metadata["productionGeometry"]["tunnelInstanceID"]
    assert tunnel_id == stable_instance_id("identity-contract/tunnel")
    assert all(
        obj.custom_properties["tunnelInstanceID"] == tunnel_id
        for obj in prod.scene.objects
    )
    for obj in prod.scene.objects:
        if obj.object_type.startswith("production_"):
            assert obj.custom_properties["infrastructureID"] == obj.instance_id


def test_chunk_piece_ids_are_technical_but_parent_infrastructure_ids_are_stable():
    prod = _production(10, namespace="chunk-identity")
    packages = build_chunk_scene_packages(prod, chunk_length_m=5.0)
    parent_ids = {
        spec.persistent_key: spec.instance_id for spec in prod.asset_specs
    }
    for package in packages:
        for obj in package.objects:
            if not obj.object_type.startswith("production_"):
                continue
            key = obj.custom_properties["sourcePersistentKey"]
            assert obj.custom_properties["sourceInfrastructureID"] == parent_ids[key]
            assert obj.custom_properties["sourceInstanceID"] == parent_ids[key]
            assert obj.instance_id != parent_ids[key]


def test_chunk_package_hierarchy_prefixes_every_object_without_changing_ids():
    prod = _production(8, namespace="chunk-hierarchy")
    packages = build_chunk_scene_packages(
        prod,
        chunk_length_m=5.0,
        boundary_policy=ChunkBoundaryPolicy.RING_ALIGNED,
    )
    source_ids = {
        obj.name: obj.instance_id
        for obj in prod.scene.objects
        if not obj.object_type.startswith("production_")
    }
    for package in packages:
        chunk_id = package.metadata["productionChunk"]["chunkID"]
        prefix = ("Chunks", f"Chunk_{chunk_id:05d}")
        for obj in package.objects:
            assert obj.collection_path[:2] == prefix
            if not obj.object_type.startswith("production_"):
                assert obj.instance_id == source_ids[obj.name]
                assert obj.custom_properties["chunkID"] == chunk_id
