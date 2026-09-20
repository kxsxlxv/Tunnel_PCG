import math

from tunnel_scanner_core import (
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_chunk_scene_packages,
    build_production_tunnel,
    build_stage10_3_local_support_meshes,
    contact_rail_axis_profile_x,
    contact_support_chainages,
    load_stage10_initial_moscow_profile,
    protective_cover_profile_xz,
    rk_contact_rail_profile_xz,
    sleeper_chainages,
)


CONTACT_TYPES = {
    "production_contact_rail",
    "production_contact_rail_cover",
    "production_contact_rail_bracket",
    "production_contact_rail_insulator",
    "production_contact_rail_attachment_screws",
    "production_contact_rail_fastening_unit",
}


def test_stage10_3_profile_closes_contact_rail_contract():
    profile = load_stage10_initial_moscow_profile()
    cr = profile.contact_rail

    assert profile.schema_version == "1.5"
    assert cr.side_profile_x_sign == -1
    assert cr.collection == "bottom"
    assert math.isclose(
        cr.horizontal_from_inner_working_face_m,
        0.690,
        abs_tol=1e-12,
    )
    assert math.isclose(cr.working_surface_z_m, 0.160, abs_tol=1e-12)
    assert math.isclose(cr.rail_overall_height_m, 0.118, abs_tol=1e-12)
    assert math.isclose(cr.rail_top_width_m, 0.080, abs_tol=1e-12)
    assert math.isclose(cr.rail_base_width_m, 0.090, abs_tol=1e-12)
    assert math.isclose(cr.rail_web_width_m, 0.020, abs_tol=1e-12)
    assert cr.rail_vertical_callouts_m == (0.023, 0.040, 0.046)
    assert cr.cover_era_mismatch is True
    assert math.isclose(cr.cover_outer_base_width_m, 0.134, abs_tol=1e-12)
    assert math.isclose(cr.cover_outer_top_width_m, 0.112, abs_tol=1e-12)
    assert math.isclose(cr.cover_historical_side_gap_m, 0.020, abs_tol=1e-12)
    assert math.isclose(cr.support_target_pitch_m, 5.0, abs_tol=1e-12)
    assert math.isclose(cr.support_target_phase_m, 2.5, abs_tol=1e-12)
    assert cr.support_snap_to_sleeper is True
    assert math.isclose(cr.insulator_axial_length_m, 0.150, abs_tol=1e-12)
    assert math.isclose(cr.insulator_diameter_m, 0.112, abs_tol=1e-12)


def test_stage10_3_nominal_contact_rail_placement_and_rk_profile():
    profile = load_stage10_initial_moscow_profile()
    cr = profile.contact_rail

    axis_x = contact_rail_axis_profile_x(profile)
    assert math.isclose(axis_x, -1.450, abs_tol=1e-12)

    poly = rk_contact_rail_profile_xz(profile)
    xs = [x for x, _z in poly]
    zs = [z for _x, z in poly]
    assert math.isclose(min(zs), 0.160, abs_tol=1e-12)
    assert math.isclose(max(zs), 0.278, abs_tol=1e-12)
    assert math.isclose(max(xs) - min(xs), 0.090, abs_tol=1e-12)

    z0 = cr.working_surface_z_m
    base_points = [(x, z) for x, z in poly if math.isclose(z, z0, abs_tol=1e-12)]
    assert len(base_points) == 2
    assert math.isclose(
        max(x for x, _z in base_points) - min(x for x, _z in base_points),
        0.090,
        abs_tol=1e-12,
    )
    top = z0 + cr.rail_overall_height_m
    top_points = [(x, z) for x, z in poly if math.isclose(z, top, abs_tol=1e-12)]
    assert len(top_points) == 2
    assert math.isclose(
        max(x for x, _z in top_points) - min(x for x, _z in top_points),
        0.080,
        abs_tol=1e-12,
    )

    core_working_z = (
        cr.working_surface_z_m
        + profile.coordinate.profile_z_to_core_z_offset_m
    )
    assert math.isclose(core_working_z, -1.510, abs_tol=1e-12)


def test_stage10_3_cover_preserves_historical_side_clearance():
    profile = load_stage10_initial_moscow_profile()
    cr = profile.contact_rail
    axis_x = contact_rail_axis_profile_x(profile)
    poly = protective_cover_profile_xz(profile)

    bottom_z = cr.working_surface_z_m + cr.cover_lower_edge_above_contact_surface_m
    assert math.isclose(bottom_z, 0.183, abs_tol=1e-12)
    assert math.isclose(
        max(z for _x, z in poly),
        bottom_z + cr.cover_height_m,
        abs_tol=1e-12,
    )

    inner_base_half = 0.5 * cr.cover_outer_base_width_m - cr.cover_side_wall_m
    rail_half = 0.5 * cr.rail_base_width_m
    assert math.isclose(
        inner_base_half - rail_half,
        0.020,
        abs_tol=1e-12,
    )
    assert cr.cover_mode == (
        "modern_silhouette_width_adjusted_to_historical_clearance"
    )
    assert cr.cover_era_mismatch is True
    assert min(x for x, _z in poly) < axis_x < max(x for x, _z in poly)


def test_stage10_3_support_schedule_snaps_independent_targets_to_sleepers():
    profile = load_stage10_initial_moscow_profile()
    length = 40.5
    supports = contact_support_chainages(length, profile)
    sleepers = sleeper_chainages(length, pitch_m=profile.sleeper.pitch_m)

    assert len(supports) == 8
    assert all(s in sleepers for s in supports)
    assert math.isclose(supports[0], 2.6785714285714284, abs_tol=2e-12)
    assert math.isclose(supports[-1], 37.79761904761903, abs_tol=2e-12)

    gaps = [b - a for a, b in zip(supports, supports[1:])]
    assert all(
        profile.contact_rail.support_normative_min_m - 1e-12
        <= gap
        <= profile.contact_rail.support_normative_max_m + 1e-12
        for gap in gaps
    )
    expected = {
        8.0 * profile.sleeper.pitch_m,
        9.0 * profile.sleeper.pitch_m,
    }
    assert all(any(math.isclose(gap, e, abs_tol=2e-12) for e in expected) for gap in gaps)


def test_stage10_3_local_support_meshes_are_complete_and_source_tagged():
    profile = load_stage10_initial_moscow_profile()
    meshes = build_stage10_3_local_support_meshes(profile)
    by_type = {m.object_type: m for m in meshes}

    assert set(by_type) == {
        "production_contact_rail_bracket",
        "production_contact_rail_insulator",
        "production_contact_rail_attachment_screws",
        "production_contact_rail_fastening_unit",
    }
    bracket = by_type["production_contact_rail_bracket"]
    assert bracket.properties["legacySleeperAttachment"] is True
    assert bracket.properties["sourceTopology"] == "Frolov_Fig1_20_curved_channel"
    assert bracket.properties["resourceEnvelopeM"] == (0.54, 0.62, 0.1)

    insulator = by_type["production_contact_rail_insulator"]
    assert insulator.properties["exactPorcelainProfileResolved"] is False
    assert math.isclose(insulator.properties["axialLengthM"], 0.150, abs_tol=1e-12)
    assert math.isclose(insulator.properties["diameterM"], 0.112, abs_tol=1e-12)

    screws = by_type["production_contact_rail_attachment_screws"]
    assert screws.properties["quantity"] == 3
    assert screws.properties["legacyAttachmentRule"] == (
        "three_track_screws_into_timber_sleeper"
    )


def test_stage10_3_production_extends_stage10_2_without_regressing_track():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=20,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(
            namespace="stage10-3-integration",
            moscow_profile=profile,
            moscow_stage="10.3",
        ),
        seed=5812,
    )

    meta = build.scene.metadata["productionGeometry"]
    assert meta["domainStage"] == "10.3"
    assert meta["permanentWayStatus"] == "implemented_stage10_2_initial_geometry"
    assert meta["contactRailStatus"] == (
        "implemented_stage10_3_initial_geometry_with_explicit_fallbacks"
    )
    assert meta["civilShellStatus"] == "deferred_to_stage10_4"

    assert len(build.scene.objects_of_type("production_track_concrete")) == 1
    assert len(build.scene.objects_of_type("production_rail")) == 2
    assert len(build.scene.objects_of_type("production_contact_rail")) == 1
    assert len(build.scene.objects_of_type("production_contact_rail_cover")) == 1
    assert len(build.scene.objects_of_type("production_sleeper")) > 0

    expected_supports = contact_support_chainages(
        build.assembly.length_by_chainage_m,
        profile,
    )
    assert meta["contactRailSupportCount"] == len(expected_supports)
    for object_type in (
        "production_contact_rail_bracket",
        "production_contact_rail_insulator",
        "production_contact_rail_attachment_screws",
        "production_contact_rail_fastening_unit",
    ):
        assert len(build.scene.objects_of_type(object_type)) == len(expected_supports)

    rail = build.scene.objects_of_type("production_contact_rail")[0]
    rp = rail.custom_properties
    assert math.isclose(rp["contactRailAxisProfileXM"], -1.450, abs_tol=1e-12)
    assert math.isclose(rp["workingSurfaceProfileZM"], 0.160, abs_tol=1e-12)
    assert rp["horizontalReference"] == "nearest_running_rail_inner_working_face"

    cover = build.scene.objects_of_type("production_contact_rail_cover")[0]
    cp = cover.custom_properties
    assert cp["eraMismatch"] is True
    assert cp["modernFallbackIsNotHistoricalClaim"] is True
    assert cp["segmentationMode"] == (
        "continuous_preview_historical_box_length_unresolved"
    )


def test_stage10_3_contact_assets_have_no_exact_duplicate_faces():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=20,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-3-topology",
            moscow_profile=profile,
            moscow_stage="10.3",
        ),
        seed=5812,
    )
    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: obj.object_type in CONTACT_TYPES,
    )
    assert audit.duplicate_group_count == 0


def test_stage10_3_periodic_support_ids_survive_exact_length_chunking():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=20,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-3-chunks",
            moscow_profile=profile,
            moscow_stage="10.3",
        ),
        seed=5812,
    )
    source = {
        obj.custom_properties["persistentKey"]: obj.instance_id
        for obj in build.scene.objects
        if obj.object_type == "production_contact_rail_bracket"
    }
    assert source

    for chunk_m in (3.7, 6.2):
        packages = build_chunk_scene_packages(
            build,
            chunk_length_m=chunk_m,
            boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        )
        found = {}
        occurrences = []
        for package in packages:
            for obj in package.objects_of_type("production_contact_rail_bracket"):
                key = obj.custom_properties["persistentKey"]
                occurrences.append(key)
                found[key] = obj.instance_id
                assert obj.custom_properties["chunkAssignmentRule"] == "event_chainage"
        assert len(occurrences) == len(set(occurrences))
        assert set(found) == set(source)
        assert found == source
