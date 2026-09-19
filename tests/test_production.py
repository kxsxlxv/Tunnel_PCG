import math

import numpy as np

from tunnel_scanner_core import (
    AncillaryConfig,
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    RailProfile,
    RingConfig,
    RingRotationStrategy,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_chunk_scene_packages,
    build_production_tunnel,
    build_procedural_nominal_tunnel,
    plan_chunks,
    production_alignment_stations,
    stable_instance_id,
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
        expected_side_faces = (station_count - 1) * n
        assert len(obj.faces) == expected_side_faces + 2


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
