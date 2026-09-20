import math

from tunnel_scanner_core import (
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    R65ProductionProfile,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_chunk_scene_packages,
    build_modern_contact_support_meshes,
    build_modern_lvt_local_event_meshes,
    build_r2k11_local_rack_mesh,
    build_production_tunnel,
    cable_rack_chainages,
    contact_rail_axis_profile_x,
    load_stage10_initial_moscow_profile,
    modern_contact_support_chainages,
    modern_lvt_chainages,
    modern_protective_cover_profile_xz,
    r65_rail_center_offsets_for_gauge,
)


MODERN_TYPES = {
    "production_rail",
    "production_track_concrete",
    "production_lvt_block",
    "production_lvt_rubber_boot",
    "production_apc4_rail_pad",
    "production_apc4_fastening",
    "production_contact_rail",
    "production_contact_rail_cover_span",
    "production_contact_rail_support_block",
    "production_contact_rail_bracket",
    "production_contact_rail_insulator",
    "production_contact_rail_fastening_unit",
    "production_contact_rail_attachment_dowels",
    "production_contact_rail_support_hood",
}


def _rail_centers(profile):
    r65 = R65ProductionProfile()
    return r65_rail_center_offsets_for_gauge(
        profile.track.gauge_m,
        profile=r65,
        measurement_below_top_m=profile.track.gauge_measurement_below_ugr_m,
    )


def test_stage10_5_profile_contains_modern_default_and_legacy_alternative():
    profile = load_stage10_initial_moscow_profile()
    pw = profile.modern_permanent_way
    cr = profile.modern_contact_rail

    assert profile.schema_version == "1.8"
    assert profile.default_service_preset == "MODERN_MOSCOW_LVT_SERVICES_2020S"

    assert pw.preset_id == "MOSCOW_LVT_M_R65_APC4_2020S"
    assert pw.fastening_family == "APC-4"
    assert math.isclose(pw.support_pitch_m, 0.600, abs_tol=1e-12)
    assert math.isclose(pw.block_base_length_transverse_m, 0.640, abs_tol=1e-12)
    assert math.isclose(pw.block_top_width_m, 0.180, abs_tol=1e-12)
    assert math.isclose(pw.block_height_m, 0.165, abs_tol=1e-12)
    assert math.isclose(pw.block_base_width_wide_m, 0.197, abs_tol=1e-12)
    assert math.isclose(pw.block_base_width_narrow_m, 0.178, abs_tol=1e-12)
    assert math.isclose(pw.boot_inner_length_m, 0.650, abs_tol=1e-12)
    assert math.isclose(pw.boot_side_height_m, 0.153, abs_tol=1e-12)
    assert math.isclose(pw.rail_pad_thickness_m, 0.014, abs_tol=1e-12)
    assert math.isclose(pw.rail_seat_cant_ratio, 1.0 / 20.0, abs_tol=1e-12)

    assert cr.preset_id == "MODERN_MOSCOW_BOTTOM_CONTACT_RAIL_2020S"
    assert math.isclose(cr.cover_top_width_m, 0.092, abs_tol=1e-12)
    assert math.isclose(cr.cover_base_width_m, 0.114, abs_tol=1e-12)
    assert math.isclose(cr.cover_height_m, 0.111, abs_tol=1e-12)
    assert math.isclose(cr.cover_side_wall_m, 0.002, abs_tol=1e-12)
    assert math.isclose(cr.cover_top_wall_m, 0.003, abs_tol=1e-12)
    assert math.isclose(cr.support_block_height_m, 0.040, abs_tol=1e-12)
    assert math.isclose(cr.support_dowel_length_m, 0.140, abs_tol=1e-12)

    rack = profile.cable_rack
    assert rack.family == "R2K11"
    assert rack.horn_count == 11
    assert math.isclose(rack.overall_arc_length_m, 1.440, abs_tol=1e-12)
    assert math.isclose(rack.upright_width_longitudinal_m, 0.048, abs_tol=1e-12)
    assert math.isclose(rack.upright_thickness_m, 0.003, abs_tol=1e-12)
    assert math.isclose(rack.horn_thickness_m, 0.004, abs_tol=1e-12)
    assert math.isclose(rack.horn_radius_m, 0.0325, abs_tol=1e-12)
    assert math.isclose(rack.horn_pitch_m, 0.125, abs_tol=1e-12)
    assert math.isclose(rack.max_cable_diameter_m, 0.065, abs_tol=1e-12)


def test_stage10_5_r2k11_racks_repeat_on_both_walls_and_stay_inside_shell():
    profile = load_stage10_initial_moscow_profile()
    chainages = cable_rack_chainages(5.4, profile)
    assert chainages == (0.5, 1.5, 2.5, 3.5, 4.5)

    for side in (-1, 1):
        rack = build_r2k11_local_rack_mesh(profile, side_sign=side)
        assert rack.properties["family"] == "R2K11"
        assert rack.properties["hornCount"] == 11
        assert rack.properties["cablePlacesPerHorn"] == 2
        assert rack.vertices
        max_radius = max(
            math.hypot(x, z)
            for x, _y, z in rack.vertices
        )
        assert max_radius < profile.intrados_radius_m


def test_stage10_5_modern_cover_is_low_rounded_wrap_not_legacy_tall_box():
    profile = load_stage10_initial_moscow_profile()
    cr = profile.contact_rail
    modern = profile.modern_contact_rail
    axis = contact_rail_axis_profile_x(profile)
    poly = modern_protective_cover_profile_xz(profile)

    assert len(poly) == 28
    zs = [z for _x, z in poly]
    xs = [x for x, _z in poly]
    expected_bottom = (
        cr.working_surface_z_m
        + modern.cover_lower_edge_above_contact_surface_m
    )
    assert math.isclose(min(zs), expected_bottom, abs_tol=1e-12)
    assert math.isclose(max(zs), expected_bottom + 0.111, abs_tol=1e-12)
    assert math.isclose(
        max(zs) - (cr.working_surface_z_m + cr.rail_overall_height_m),
        0.016,
        abs_tol=1e-12,
    )
    assert math.isclose(max(xs) - min(xs), 0.114, abs_tol=1e-12)
    assert min(xs) < axis < max(xs)

    # More than two side levels: the current cover is intentionally curved,
    # unlike the old four-corner box silhouette.
    outer_left = poly[:7]
    widths = [abs(x - axis) for x, _z in outer_left]
    assert len({round(v, 8) for v in widths}) > 4
    assert widths[0] > widths[-1]


def test_stage10_5_modern_contact_supports_live_between_running_supports():
    profile = load_stage10_initial_moscow_profile()
    pitch = profile.modern_permanent_way.support_pitch_m
    phase = 0.5 * pitch
    supports = modern_contact_support_chainages(
        40.5,
        profile,
        running_support_pitch_m=pitch,
        running_support_phase_m=phase,
    )
    assert supports
    modern = profile.modern_contact_rail

    for chainage in supports:
        nearest_index = round((chainage - phase) / pitch)
        nearest = phase + nearest_index * pitch
        assert abs(chainage - nearest) >= (
            modern.running_support_exclusion_half_length_m - 1e-12
        )

    gaps = [b - a for a, b in zip(supports, supports[1:])]
    assert all(
        modern.support_normative_min_m - 1e-12
        <= gap
        <= modern.support_normative_max_m + 1e-12
        for gap in gaps
    )


def test_stage10_5_modern_contact_local_assembly_uses_dedicated_block_and_hood():
    profile = load_stage10_initial_moscow_profile()
    meshes = build_modern_contact_support_meshes(profile)
    by_type = {m.object_type: m for m in meshes}

    assert set(by_type) == {
        "production_contact_rail_support_block",
        "production_contact_rail_bracket",
        "production_contact_rail_insulator",
        "production_contact_rail_fastening_unit",
        "production_contact_rail_attachment_dowels",
        "production_contact_rail_support_hood",
    }
    block = by_type["production_contact_rail_support_block"]
    assert block.properties["separateFromRunningRailSupport"] is True
    assert math.isclose(block.properties["heightM"], 0.040, abs_tol=1e-12)
    assert math.isclose(block.properties["polymerDowelLengthM"], 0.140, abs_tol=1e-12)

    bracket = by_type["production_contact_rail_bracket"]
    assert bracket.properties["legacySleeperAttachment"] is False
    assert bracket.properties["dedicatedConcreteSupportBlock"] is True

    insulator = by_type["production_contact_rail_insulator"]
    assert insulator.properties["orientation"] == "vertical_above_contact_rail"

    hood = by_type["production_contact_rail_support_hood"]
    assert hood.properties["mainCoverInterruptedHere"] is True
    assert hood.properties["geometryMode"] == "rounded_local_fastening_hood_v1"


def test_stage10_5_lvt_blocks_are_independent_and_clear_central_drain():
    profile = load_stage10_initial_moscow_profile()
    centers = _rail_centers(profile)
    meshes = build_modern_lvt_local_event_meshes(
        profile,
        rail_centers_profile_x=centers,
    )
    by_type = {m.object_type: m for m in meshes}
    assert set(by_type) == {
        "production_lvt_block",
        "production_lvt_rubber_boot",
        "production_apc4_rail_pad",
        "production_apc4_fastening",
    }

    blocks = by_type["production_lvt_block"]
    assert blocks.properties["bridgesCentralDrain"] is False
    assert len(blocks.vertices) == 16
    negative = blocks.vertices[:8]
    positive = blocks.vertices[8:16]
    assert max(x for x, _y, _z in negative) < -0.45
    assert min(x for x, _y, _z in positive) > +0.45

    pad = by_type["production_apc4_rail_pad"]
    assert math.isclose(pad.properties["padThicknessM"], 0.014, abs_tol=1e-12)
    assert math.isclose(pad.properties["railBaseProfileZM"], -0.180, abs_tol=1e-12)
    assert math.isclose(
        pad.properties["blockRailSeatProfileZM"],
        -0.194,
        abs_tol=1e-12,
    )

    fast = by_type["production_apc4_fastening"]
    assert fast.properties["fasteningFamily"] == "APC-4"
    assert fast.properties["clampsPerRailSeat"] == 2
    assert fast.properties["monoregulatorsPerRailSeat"] == 2
    assert fast.properties["exactSmallHardwareSolidsResolved"] is False


def test_stage10_5_modern_is_default_and_legacy_remains_selectable():
    profile = load_stage10_initial_moscow_profile()
    base = dict(
        assembly_config=TunnelAssemblyConfig(
            n_rings=8,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        seed=5812,
    )
    modern = build_production_tunnel(
        **base,
        production_config=ProductionConfig(
            namespace="stage10-5-modern",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
    )
    legacy = build_production_tunnel(
        **base,
        production_config=ProductionConfig(
            namespace="stage10-5-legacy",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_service_preset="legacy",
        ),
    )

    mm = modern.scene.metadata["productionGeometry"]
    assert modern.config.resolved_moscow_service_preset == "modern"
    assert mm["servicePreset"] == "modern"
    assert mm["permanentWayStatus"] == "implemented_stage10_5_modern_LVT_M_APC4"
    assert mm["contactRailStatus"] == (
        "implemented_stage10_5_modern_segmented_cover_and_dedicated_support"
    )
    assert len(modern.scene.objects_of_type("production_sleeper")) == 0
    assert len(modern.scene.objects_of_type("production_baseplate")) == 0
    assert len(modern.scene.objects_of_type("production_lvt_block")) > 0
    assert len(modern.scene.objects_of_type("production_apc4_fastening")) > 0
    assert len(modern.scene.objects_of_type("production_contact_rail_cover")) == 0
    assert len(modern.scene.objects_of_type("production_contact_rail_cover_span")) > 0
    support_count = len(
        modern.scene.objects_of_type("production_contact_rail_bracket")
    )
    assert support_count > 0
    assert len(
        modern.scene.objects_of_type("production_contact_rail_support_block")
    ) == support_count
    assert len(
        modern.scene.objects_of_type("production_contact_rail_support_hood")
    ) == support_count
    assert mm["contactRailSupportSeparateFromRunningSupport"] is True
    assert len(modern.scene.objects_of_type("production_tube")) == 0
    assert len(modern.scene.objects_of_type("production_service_cable")) == 22
    rack_count = len(
        modern.scene.objects_of_type("production_cable_rack_r2k11")
    )
    assert rack_count == 22
    assert mm["serviceCableCount"] == 22
    assert mm["serviceCableRackCount"] == rack_count
    assert mm["serviceCableRackFamily"] == "R2K11"
    assert mm["serviceCableRackHornCount"] == 11
    assert mm["serviceCableRacksPerCivilRing"] == 2
    assert mm["servicePipeStatus"] == "unresolved_not_generated"
    assert mm["legacyStage8TubeCount"] == 0

    for cable in modern.scene.objects_of_type("production_service_cable"):
        # Straight zero-noise fixture: all cable-section vertices remain inside
        # the physical Moscow 2.55 m intrados.
        assert max(
            math.hypot(x, z)
            for x, _y, z in cable.vertices
        ) < profile.intrados_radius_m

    lm = legacy.scene.metadata["productionGeometry"]
    assert legacy.config.resolved_moscow_service_preset == "legacy"
    assert lm["servicePreset"] == "legacy"
    assert len(legacy.scene.objects_of_type("production_sleeper")) > 0
    assert len(legacy.scene.objects_of_type("production_baseplate")) > 0
    assert len(legacy.scene.objects_of_type("production_lvt_block")) == 0
    assert len(legacy.scene.objects_of_type("production_contact_rail_cover")) == 1
    assert len(legacy.scene.objects_of_type("production_contact_rail_cover_span")) == 0
    assert len(legacy.scene.objects_of_type("production_tube")) == 6
    assert len(legacy.scene.objects_of_type("production_service_cable")) == 0


def test_stage10_5_modern_objects_have_no_exact_duplicate_faces_and_stable_ids():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=12,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-topology",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
        seed=5812,
    )
    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: obj.object_type in MODERN_TYPES,
    )
    assert audit.duplicate_group_count == 0

    source = {
        obj.custom_properties["persistentKey"]: obj.instance_id
        for obj in build.scene.objects
        if (
            obj.object_type.startswith("production_lvt_")
            or obj.object_type.startswith("production_apc4_")
            or obj.object_type.startswith("production_contact_rail_")
        )
        and "persistentKey" in obj.custom_properties
    }
    assert source

    for chunk_m in (3.7, 6.2):
        packages = build_chunk_scene_packages(
            build,
            chunk_length_m=chunk_m,
            boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        )
        found = {}
        for package in packages:
            for obj in package.objects:
                key = obj.custom_properties.get("persistentKey")
                if key in source:
                    found[key] = obj.instance_id
        assert found == source


def test_stage10_5_lvt_support_chain_is_600mm_half_phase():
    profile = load_stage10_initial_moscow_profile()
    chainages = modern_lvt_chainages(10.0, profile)
    assert chainages
    assert math.isclose(chainages[0], 0.300, abs_tol=1e-12)
    assert all(
        math.isclose(b - a, 0.600, abs_tol=2e-12)
        for a, b in zip(chainages, chainages[1:])
    )
