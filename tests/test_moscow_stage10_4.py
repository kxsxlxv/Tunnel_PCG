import math

from tunnel_scanner_core import (
    ChunkBoundaryPolicy,
    ProductionConfig,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_annular_shell_sweep,
    build_chunk_scene_packages,
    build_production_tunnel,
    civil_ring_ranges,
    load_stage10_initial_moscow_profile,
    r65_rail_center_offsets_for_gauge,
    R65ProductionProfile,
    track_concrete_profile_xz,
    walkway_profile_xz,
)


def _rail_centers(profile):
    r65 = R65ProductionProfile()
    return r65_rail_center_offsets_for_gauge(
        profile.track.gauge_m,
        profile=r65,
        measurement_below_top_m=profile.track.gauge_measurement_below_ugr_m,
    )


def test_stage10_4_profile_closes_civil_shell_and_walkway_contract():
    profile = load_stage10_initial_moscow_profile()
    w = profile.walkway

    assert profile.schema_version == "2.2"
    assert profile.civil_family == "CAST_IRON_5500_R1000"
    assert profile.civil_geometry_mode == "smooth_concentric_ringwise_shell_v1"
    assert profile.civil_segment_surface_mode == (
        "disabled_exact_NCK_angles_unresolved"
    )
    assert math.isclose(profile.intrados_radius_m, 2.55, abs_tol=1e-12)
    assert math.isclose(profile.extrados_radius_m, 2.75, abs_tol=1e-12)
    assert math.isclose(profile.ring_pitch_m, 1.0, abs_tol=1e-12)

    assert w.side_profile_x_sign == 1
    assert math.isclose(w.top_z_m, 0.2, abs_tol=1e-12)
    assert math.isclose(w.inner_edge_x_m, 1.66, abs_tol=1e-12)
    assert math.isclose(w.outer_edge_x_m, 2.083650643, abs_tol=1e-9)
    assert math.isclose(w.top_clear_width_m, 0.423650643, abs_tol=1e-9)
    assert w.geometry_mode == "raised_integrated_wedge_to_physical_intrados_v1"


def test_stage10_4_walkway_and_track_concrete_partition_without_overlap():
    profile = load_stage10_initial_moscow_profile()
    centers = _rail_centers(profile)
    concrete = track_concrete_profile_xz(
        profile,
        rail_centers_profile_x=centers,
        walkway_inner_edge_x_m=profile.walkway.inner_edge_x_m,
    )
    walkway = walkway_profile_xz(profile)

    assert math.isclose(
        max(x for x, _z in concrete),
        profile.walkway.inner_edge_x_m,
        abs_tol=2e-12,
    )
    concrete_top_at_walkway = (
        profile.track_concrete.surface_reference_z_m
        + profile.track_concrete.surface_cross_slope_to_drain
        * (
            profile.walkway.inner_edge_x_m
            - profile.track_concrete.surface_reference_abs_x_m
        )
    )
    assert math.isclose(concrete_top_at_walkway, -0.21995, abs_tol=2e-12)

    inner_points = [
        z for x, z in walkway
        if math.isclose(x, profile.walkway.inner_edge_x_m, abs_tol=2e-12)
    ]
    assert any(math.isclose(z, concrete_top_at_walkway, abs_tol=2e-12) for z in inner_points)
    assert any(math.isclose(z, profile.walkway.top_z_m, abs_tol=2e-12) for z in inner_points)

    outer_candidates = [
        (x, z)
        for x, z in walkway
        if math.isclose(z, profile.walkway.top_z_m, abs_tol=2e-12)
        and x > profile.walkway.inner_edge_x_m
    ]
    assert len(outer_candidates) == 1
    outer_top = outer_candidates[0]
    assert math.isclose(
        outer_top[0],
        profile.walkway.outer_edge_x_m,
        abs_tol=1e-9,
    )
    circle_error = (
        outer_top[0] ** 2
        + (outer_top[1] - profile.datums.lining_axis_z_m) ** 2
        - profile.intrados_radius_m ** 2
    )
    assert abs(circle_error) < 2e-12


def test_stage10_4_annular_shell_uses_exact_moscow_radii_without_fake_segmentation():
    profile = load_stage10_initial_moscow_profile()
    mesh = build_annular_shell_sweep(
        profile,
        ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0)),
        angular_segments=96,
    )

    assert mesh.angular_segments == 96
    assert mesh.station_count == 2
    assert len(mesh.vertices) == 2 * 2 * 96
    assert len(mesh.faces) == 2 * 96

    first_station_inner = mesh.vertices[:96]
    first_station_outer = mesh.vertices[96:192]
    assert all(
        math.isclose(math.hypot(x, z), 2.55, abs_tol=2e-12)
        for x, _y, z in first_station_inner
    )
    assert all(
        math.isclose(math.hypot(x, z), 2.75, abs_tol=2e-12)
        for x, _y, z in first_station_outer
    )


def test_stage10_4_ring_ranges_are_one_metre_and_allow_partial_final_ring():
    ranges = civil_ring_ranges(5.4, ring_pitch_m=1.0)
    assert len(ranges) == 6
    assert ranges[:5] == tuple((i, float(i), float(i + 1)) for i in range(5))
    assert ranges[-1] == (5, 5.0, 5.4)


def test_stage10_4_production_replaces_stage9_shell_and_walkway_and_closes_gap_contract():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=True,
        production_config=ProductionConfig(
            namespace="stage10-4-integration",
            moscow_profile=profile,
            moscow_stage="10.4",
        ),
        seed=5812,
    )

    meta = build.scene.metadata["productionGeometry"]
    assert meta["domainStage"] == "10.4"
    assert meta["stage9CivilGeometryRemoved"] is True
    assert meta["civilShellStatus"] == (
        "implemented_stage10_4_cast_iron_smooth_envelope_detail_deferred"
    )
    assert meta["moscowCivilCompositeDetailStatus"] == (
        "cast_iron_detail_deferred_pending_research"
    )
    assert meta["walkwayStatus"] == "implemented_stage10_4_source_backed_geometry"
    assert meta["transitionalCivilGapStatus"] == "closed_by_stage10_4_moscow_shell"
    assert meta["contactRailStatus"] == (
        "implemented_stage10_3_initial_geometry_with_explicit_fallbacks"
    )
    assert meta["permanentWayStatus"] == "implemented_stage10_2_initial_geometry"

    assert not build.scene.objects_of_type("lining_segment")
    assert not build.scene.objects_of_type("bolt_head")
    assert not build.scene.objects_of_type("bolt_pocket_cutter")
    assert not build.scene.objects_of_type("production_walkway")
    assert len(build.scene.objects_of_type("production_moscow_walkway")) == 1
    assert len(build.scene.objects_of_type("production_track_concrete")) == 1
    assert len(build.scene.objects_of_type("production_contact_rail")) == 1
    assert len(build.scene.objects_of_type("production_contact_rail_cover")) == 1

    civil = build.scene.objects_of_type("production_moscow_civil_shell_ring")
    assert len(civil) == 6
    assert meta["moscowCivilRingCount"] == 6
    assert math.isclose(meta["moscowCivilRingPitchM"], 1.0, abs_tol=1e-12)
    assert math.isclose(meta["moscowCivilIntradosRadiusM"], 2.55, abs_tol=1e-12)
    assert math.isclose(meta["moscowCivilExtradosRadiusM"], 2.75, abs_tol=1e-12)
    assert civil[-1].custom_properties["partialFinalRing"] is True

    assert not build.scene.objects_of_type(
        "production_moscow_civil_detail_ribs"
    )
    assert not build.scene.objects_of_type(
        "production_moscow_civil_bolt_heads"
    )
    assert meta["moscowCivilSegmentObjectCount"] == 0
    assert meta["moscowCivilPrescribedRadialJointCount"] == 0
    assert meta["moscowCivilPrescribedCircumferentialJointCount"] == 0
    assert meta["moscowCivilBoltPocketCount"] == 0
    assert meta["moscowCivilBoltHeadCount"] == 0
    assert meta["moscowCivilBoltsEnabled"] is False
    assert meta["moscowCivilRenderedBlockCount"] == 0
    assert meta["moscowCivilTopology"] == "cast_iron_detail_deferred"
    for ring in civil:
        p = ring.custom_properties
        assert p["civilRenderMode"] == (
            "source_sized_smooth_cast_iron_envelope_detail_deferred"
        )
        assert p["coarseSegmentCountReference"] == 11
        assert p["coarseSegmentCountIsGeometry"] is False
        assert p["stage9LikeCurvedSegmentConstruction"] is False

    concrete = build.scene.objects_of_type("production_track_concrete")[0]
    assert concrete.custom_properties["walkwayShoulderPartitioned"] is True
    assert concrete.custom_properties["liningContactFacesOmitted"] is True
    walkway = build.scene.objects_of_type("production_moscow_walkway")[0]
    assert walkway.custom_properties["trackConcreteContactFacesOmitted"] is True
    assert walkway.custom_properties["liningContactFacesOmitted"] is True


def test_stage10_4_has_no_exact_duplicate_production_faces_and_civil_ids_survive_chunking():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=5,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-4-topology",
            moscow_profile=profile,
            moscow_stage="10.4",
        ),
        seed=5812,
    )

    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: obj.object_type.startswith("production_"),
    )
    assert audit.duplicate_group_count == 0
    assert not build.scene.objects_of_type(
        "production_moscow_civil_detail_ribs"
    )
    assert not build.scene.objects_of_type(
        "production_moscow_civil_bolt_heads"
    )
    assert build.scene.metadata["productionGeometry"][
        "moscowCivilBoltsEnabled"
    ] is False

    source = {
        obj.custom_properties["persistentKey"]: obj.instance_id
        for obj in build.scene.objects_of_type(
            "production_moscow_civil_shell_ring"
        )
    }
    for chunk_m in (1.3, 2.2):
        packages = build_chunk_scene_packages(
            build,
            chunk_length_m=chunk_m,
            boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        )
        seen = {}
        occurrences = []
        for package in packages:
            for obj in package.objects:
                if obj.object_type != "production_moscow_civil_shell_ring":
                    continue
                key = obj.custom_properties["persistentKey"]
                occurrences.append(key)
                seen[key] = obj.instance_id
                assert obj.custom_properties["chunkAssignmentRule"] == "event_chainage"
        assert len(occurrences) == len(set(occurrences))
        assert seen == source
