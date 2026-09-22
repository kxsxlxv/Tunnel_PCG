import math

import tunnel_scanner_core.production as production_module

from tunnel_scanner_core import (
    AlignmentStation,
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    R65ProductionProfile,
    RingConfig,
    RingRotationStrategy,
    SurfaceMeshingConfig,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_chunk_scene_packages,
    build_stage10_5_rc_modern_chunk_plan,
    build_stage10_5_rc_modern_chunk_scene_package,
    compact_exact_collinear_alignment_stations,
    build_modern_contact_support_meshes,
    build_modern_lvt_local_event_meshes,
    build_r2k11_local_rack_mesh,
    build_water_main_support_local_mesh,
    build_production_tunnel,
    build_procedural_nominal_tunnel,
    cable_rack_chainages,
    contact_rail_axis_profile_x,
    iter_stage10_5_rc_modern_chunk_scene_packages,
    load_stage10_initial_moscow_profile,
    modern_contact_support_chainages,
    modern_lvt_chainages,
    modern_protective_cover_profile_xz,
    modern_cable_sections_core,
    modern_water_main_section_core,
    production_alignment_stations,
    sample_tunnel_assembly,
    water_main_support_chainages,
    r65_rail_center_offsets_for_gauge,
    strip_internal_lining_cap_faces,
)

from tunnel_scanner_core.production import (
    _periodic_cable_sag_alignment_stations,
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
    "production_contact_rail_base_plate",
    "production_contact_rail_bracket",
    "production_contact_rail_insulator",
    "production_contact_rail_fastening_unit",
    "production_contact_rail_clamp_bolts",
    "production_contact_rail_attachment_dowels",
    "production_contact_rail_support_hood",
    "production_service_cable",
    "production_cable_rack_r2k11",
    "production_water_main",
    "production_water_main_support",
    "production_moscow_walkway",
    "production_moscow_civil_shell_ring",
}


def _point_segment_distance_xz(
    px: float,
    pz: float,
    ax: float,
    az: float,
    bx: float,
    bz: float,
) -> float:
    dx = bx - ax
    dz = bz - az
    denom = dx * dx + dz * dz
    if denom <= 1e-24:
        return math.hypot(px - ax, pz - az)
    t = ((px - ax) * dx + (pz - az) * dz) / denom
    t = max(0.0, min(1.0, t))
    qx = ax + t * dx
    qz = az + t * dz
    return math.hypot(px - qx, pz - qz)


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

    assert profile.schema_version == "2.2"
    assert profile.default_service_preset == "MODERN_MOSCOW_LVT_SERVICES_2020S"
    assert profile.water_main.min_nominal_dn_mm == 80
    assert profile.water_main.quantity_single_track_tunnel == 1
    assert profile.water_main.side_profile_x_sign == 1
    assert math.isclose(profile.water_main.center_profile_z_m, 0.60, abs_tol=1e-12)
    assert math.isclose(profile.water_main.support_max_pitch_m, 4.0, abs_tol=1e-12)

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
    assert math.isclose(cr.drawing_reference_to_axis_m, 0.683, abs_tol=1e-12)
    assert math.isclose(
        cr.drawing_reference_to_outer_envelope_m,
        0.873,
        abs_tol=1e-12,
    )
    assert math.isclose(cr.drawing_upper_return_m, 0.180, abs_tol=1e-12)
    assert math.isclose(cr.drawing_top_above_ugr_m, 0.373, abs_tol=1e-12)
    assert math.isclose(cr.drawing_lower_bend_callout_m, 0.155, abs_tol=1e-12)
    assert math.isclose(cr.drawing_upper_bend_callout_m, 0.090, abs_tol=1e-12)
    assert math.isclose(
        cr.minimum_clearance_to_lvt_block_m,
        0.035,
        abs_tol=1e-12,
    )
    assert cr.base_plate_anchor_count == 4
    assert cr.clamp_bolt_count == 2

    rack = profile.cable_rack
    assert rack.family == "R2K11"
    assert rack.assembly_designation == "R2K11 / K1351.001-09 + 11xK1350.002"
    assert rack.upright_designation == "K1351.001-09"
    assert rack.horn_designation == "K1350.002"
    assert rack.horn_count == 11
    assert math.isclose(rack.overall_arc_length_m, 1.440, abs_tol=1e-12)
    assert math.isclose(rack.upright_width_longitudinal_m, 0.048, abs_tol=1e-12)
    assert math.isclose(rack.upright_thickness_m, 0.003, abs_tol=1e-12)
    assert math.isclose(rack.horn_thickness_m, 0.004, abs_tol=1e-12)
    assert math.isclose(rack.horn_radius_m, 0.0325, abs_tol=1e-12)
    assert math.isclose(rack.horn_overall_length_m, 0.169, abs_tol=1e-12)
    assert math.isclose(rack.horn_overall_height_m, 0.087, abs_tol=1e-12)
    assert rack.cable_places_per_horn == 2
    assert rack.occupied_places_per_horn == 1
    assert rack.occupied_level_indices == (1, 2, 3, 4, 6, 7, 8, 9)
    assert math.isclose(rack.cable_sag_midspan_m, 0.025, abs_tol=1e-12)
    assert math.isclose(
        rack.cable_sag_variation_fraction,
        0.35,
        abs_tol=1e-12,
    )
    assert math.isclose(
        rack.cable_sag_peak_phase_jitter_fraction,
        0.12,
        abs_tol=1e-12,
    )
    assert math.isclose(
        rack.negative_side_center_profile_z_m,
        profile.datums.lining_axis_z_m,
        abs_tol=1e-12,
    )
    assert math.isclose(rack.horn_pitch_m, 0.125, abs_tol=1e-12)
    assert math.isclose(rack.first_cable_center_inward_m, 0.0375, abs_tol=1e-12)
    assert math.isclose(rack.second_cable_center_inward_m, 0.1165, abs_tol=1e-12)
    assert math.isclose(rack.max_cable_diameter_m, 0.065, abs_tol=1e-12)


def test_stage10_5_r2k11_racks_repeat_on_both_walls_and_stay_inside_shell():
    profile = load_stage10_initial_moscow_profile()
    chainages = cable_rack_chainages(5.4, profile)
    assert chainages == (0.5, 1.5, 2.5, 3.5, 4.5, 5.2)

    for side in (-1, 1):
        rack = build_r2k11_local_rack_mesh(profile, side_sign=side)
        assert rack.properties["family"] == "R2K11"
        assert rack.properties["hornCount"] == 11
        assert rack.properties["cablePlacesPerHorn"] == 2
        assert rack.properties["uprightDesignation"] == "K1351.001-09"
        assert rack.properties["hornDesignation"] == "K1350.002"
        assert math.isclose(rack.properties["hornOverallLengthM"], 0.169, abs_tol=1e-12)
        assert math.isclose(rack.properties["hornOverallHeightM"], 0.087, abs_tol=1e-12)
        assert math.isclose(rack.properties["hornLongitudinalWidthM"], 0.040, abs_tol=1e-12)
        assert rack.properties["commonHorizontalUnderbar"] is False
        assert rack.properties["separateWallTab"] is False
        assert rack.properties["separateHorizontalNeck"] is False
        assert rack.properties["centralOmegaCrest"] is False
        assert rack.properties["hornGeometryMode"] == "double_u_cradle_pair_v6"
        assert rack.properties["hornUCradleCount"] == 2
        assert math.isclose(
            rack.properties["hornUVisualPairSpanM"],
            0.154,
            abs_tol=1e-12,
        )
        assert math.isclose(
            rack.properties["hornUCentralGapM"],
            0.004,
            abs_tol=1e-12,
        )
        assert math.isclose(
            rack.properties["hornUInnerClearDiameterM"],
            0.067,
            abs_tol=1e-12,
        )
        horn_centers = tuple(
            float(x) for x in rack.properties["hornUCableCenterOffsetsM"]
        )
        assert len(horn_centers) == 2
        assert math.isclose(horn_centers[0], 0.0375, abs_tol=1e-12)
        assert math.isclose(horn_centers[1], 0.1165, abs_tol=1e-12)
        assert math.isclose(
            rack.properties["hornUMaxCableRadialClearanceM"],
            0.001,
            abs_tol=1e-12,
        )
        assert rack.properties["hornUArcSegments"] == 5
        assert rack.properties["tessellationMode"] == "sagitta_bounded_adaptive_v1"
        assert math.isclose(
            rack.properties["surfaceToleranceM"],
            0.002,
            abs_tol=1e-12,
        )
        assert rack.properties["hornUAchievedMaxSagittaM"] <= 0.002 + 1e-12
        assert rack.properties["uprightAchievedMaxSagittaM"] <= 0.002 + 1e-12
        if side < 0:
            assert math.isclose(
                rack.properties["centerProfileZM"],
                profile.datums.lining_axis_z_m,
                abs_tol=1e-12,
            )
        assert rack.vertices
        max_radius = max(
            math.hypot(x, z)
            for x, _y, z in rack.vertices
        )
        assert max_radius < profile.intrados_radius_m

    cables = modern_cable_sections_core(profile)
    assert len(cables) == 16
    assert {len(section) for _name, section, _props in cables} == {7}
    assert {
        int(props["sourcePreviewCircleVertices"])
        for _name, _section, props in cables
    } == {8}
    assert {
        int(props["cableCircleVertices"])
        for _name, _section, props in cables
    } == {7}
    assert all(
        float(props["surfaceAchievedMaxSagittaM"]) <= 0.002 + 1e-12
        for _name, _section, props in cables
    )
    tighter_cables = modern_cable_sections_core(
        profile,
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=0.001),
    )
    assert {len(section) for _name, section, _props in tighter_cables} == {10}
    assert all(
        float(props["surfaceAchievedMaxSagittaM"]) <= 0.001 + 1e-12
        for _name, _section, props in tighter_cables
    )
    assert {
        props["rackLevel"]
        for _name, _section, props in cables
    } == set(profile.cable_rack.occupied_level_indices)
    assert {
        props["occupiedCablePlaceIndex"]
        for _name, _section, props in cables
    } == {0, 1}
    cable_centers = {
        props["occupiedCablePlaceIndex"]: props["cablePlaceCenterInwardM"]
        for _name, _section, props in cables
    }
    assert math.isclose(cable_centers[0], 0.0375, abs_tol=1e-12)
    assert math.isclose(cable_centers[1], 0.1165, abs_tol=1e-12)
    assert all(
        props["occupiedCablePlacesPerHorn"] == 1
        for _name, _section, props in cables
    )
    assert all(
        math.isclose(props["longitudinalSagM"], 0.025, abs_tol=1e-12)
        for _name, _section, props in cables
    )
    assert all(
        math.isclose(
            props["longitudinalSagVariationFraction"],
            0.35,
            abs_tol=1e-12,
        )
        for _name, _section, props in cables
    )
    assert all(
        math.isclose(
            props["longitudinalSagPeakPhaseJitterFraction"],
            0.12,
            abs_tol=1e-12,
        )
        for _name, _section, props in cables
    )
    assert {
        props["serviceSideClass"]
        for _name, _section, props in cables
    } == {
        "strong_current_side_contact_rail_side",
        "weak_current_side_walkway_side",
    }

    # The continuous DN80 preview must not intersect the positive-X R2K11
    # rack at its periodic stations. This specifically protects the visual
    # service-layout bug where pipes/cables could overlap or escape the shell.
    water_section, _water_props = modern_water_main_section_core(profile)
    water_cx = sum(x for x, _z in water_section) / len(water_section)
    water_cz = sum(z for _x, z in water_section) / len(water_section)
    water_radius = 0.5 * profile.water_main.preview_outer_diameter_m
    positive_rack = build_r2k11_local_rack_mesh(profile, side_sign=1)
    min_rack_distance = math.inf
    for face in positive_rack.faces:
        for i, ia in enumerate(face):
            ib = face[(i + 1) % len(face)]
            ax, _ay, az = positive_rack.vertices[ia]
            bx, _by, bz = positive_rack.vertices[ib]
            min_rack_distance = min(
                min_rack_distance,
                _point_segment_distance_xz(
                    water_cx,
                    water_cz,
                    ax,
                    az,
                    bx,
                    bz,
                ),
            )
    assert min_rack_distance > water_radius + 1e-4


def test_stage10_5_cable_sag_is_stable_irregular_and_low_poly():
    stations = (
        AlignmentStation(0.0, 0.0, 0.0, 0.0, "start"),
        AlignmentStation(4.0, 4.0, 0.0, 0.0, "end"),
    )
    kwargs = {
        "support_pitch_m": 1.0,
        "support_phase_m": 0.5,
        "midspan_sag_m": 0.025,
        "variation_fraction": 0.35,
        "peak_phase_jitter_fraction": 0.12,
    }
    a1 = _periodic_cable_sag_alignment_stations(
        stations,
        asset_key="cable-A",
        **kwargs,
    )
    a2 = _periodic_cable_sag_alignment_stations(
        stations,
        asset_key="cable-A",
        **kwargs,
    )
    b = _periodic_cable_sag_alignment_stations(
        stations,
        asset_key="cable-B",
        **kwargs,
    )

    assert a1 == a2
    assert a1 != b

    # Four metres with half-metre support phase yields one interior peak per
    # support span plus support stations, not a dense spline tessellation.
    assert len(a1) <= 11
    sagged = [
        -station.offset_z_m
        for station in a1
        if station.offset_z_m < -1e-9
    ]
    assert sagged
    assert max(sagged) - min(sagged) > 0.002

    support_chainages = (0.5, 1.5, 2.5, 3.5)
    by_chainage = {round(s.chainage_m, 9): s for s in a1}
    for chainage in support_chainages:
        assert math.isclose(
            by_chainage[round(chainage, 9)].offset_z_m,
            0.0,
            abs_tol=1e-12,
        )


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
        "production_contact_rail_base_plate",
        "production_contact_rail_bracket",
        "production_contact_rail_insulator",
        "production_contact_rail_fastening_unit",
        "production_contact_rail_clamp_bolts",
        "production_contact_rail_attachment_dowels",
        "production_contact_rail_support_hood",
    }
    centers = _rail_centers(profile)
    lvt_outboard = (
        max(abs(v) for v in centers)
        + 0.5 * profile.modern_permanent_way.block_base_length_transverse_m
    )

    block = by_type["production_contact_rail_support_block"]
    assert block.properties["separateFromRunningRailSupport"] is True
    assert math.isclose(block.properties["heightM"], 0.040, abs_tol=1e-12)
    assert math.isclose(block.properties["polymerDowelLengthM"], 0.140, abs_tol=1e-12)
    assert math.isclose(
        block.properties["lvtBlockOutboardProfileAbsXM"],
        lvt_outboard,
        abs_tol=1e-12,
    )
    assert math.isclose(
        block.properties["actualInboardClearanceToLVTBlockM"],
        0.035,
        abs_tol=1e-12,
    )

    base_plate = by_type["production_contact_rail_base_plate"]
    assert base_plate.properties["anchorCount"] == 4
    assert math.isclose(
        base_plate.properties["transverseM"],
        0.220,
        abs_tol=1e-12,
    )
    assert math.isclose(
        base_plate.properties["actualInboardClearanceToLVTBlockM"],
        0.035,
        abs_tol=1e-12,
    )

    bracket = by_type["production_contact_rail_bracket"]
    assert bracket.properties["legacySleeperAttachment"] is False
    assert bracket.properties["dedicatedConcreteSupportBlock"] is True
    assert bracket.properties["geometryMode"] == "dimensioned_hook_channel_873x373_v3"
    assert math.isclose(
        bracket.properties["drawingReferenceToAxisM"],
        0.683,
        abs_tol=1e-12,
    )
    assert math.isclose(
        bracket.properties["drawingReferenceToOuterEnvelopeM"],
        0.873,
        abs_tol=1e-12,
    )
    assert math.isclose(
        bracket.properties["drawingTopAboveUGRM"],
        0.373,
        abs_tol=1e-12,
    )
    assert math.isclose(
        bracket.properties["outerEnvelopeProfileAbsXM"],
        0.5 * profile.track.gauge_m + 0.873,
        abs_tol=1e-12,
    )
    assert math.isclose(
        bracket.properties["lvtBlockOutboardProfileAbsXM"],
        lvt_outboard,
        abs_tol=1e-12,
    )
    assert math.isclose(
        bracket.properties["minimumClearanceToLVTBlockM"],
        0.035,
        abs_tol=1e-12,
    )
    assert math.isclose(
        bracket.properties["actualLowerLegClearanceToLVTBlockM"],
        0.035,
        abs_tol=1e-12,
    )
    assert math.isclose(
        bracket.properties["lowerLegInboardProfileAbsXM"],
        lvt_outboard + 0.035,
        abs_tol=1e-12,
    )

    insulator = by_type["production_contact_rail_insulator"]
    assert insulator.properties["orientation"] == (
        "vertical_between_contact_clamp_and_upper_hook_arm"
    )
    assert 0.0 < insulator.properties["visibleHeightM"] <= 0.040 + 1e-12

    clamp = by_type["production_contact_rail_fastening_unit"]
    assert clamp.properties["geometryMode"] == (
        "upper_flange_saddle_insulated_two_bolt_v3"
    )
    assert clamp.properties["boltCount"] == 2

    clamp_bolts = by_type["production_contact_rail_clamp_bolts"]
    assert clamp_bolts.properties["quantity"] == 2

    dowels = by_type["production_contact_rail_attachment_dowels"]
    assert dowels.properties["quantity"] == 4

    hood = by_type["production_contact_rail_support_hood"]
    assert hood.properties["mainCoverInterruptedHere"] is True
    assert hood.properties["coversClampAndBoltHeads"] is True
    assert hood.properties["geometryMode"] == "rounded_local_fastening_hood_v2"

    # The generated hook bracket must match the readable drawing envelope in
    # profile X/Z while retaining the authoritative contact-rail datum.
    bracket_vertices = bracket.vertices
    profile_x_abs = [abs(x) for x, _y, _z in bracket_vertices]
    core_z = [z for _x, _y, z in bracket_vertices]
    assert min(profile_x_abs) >= lvt_outboard + 0.035 - 1e-9
    assert math.isclose(max(profile_x_abs), 1.633, abs_tol=1e-6)
    assert math.isclose(
        max(core_z) + profile.datums.lining_axis_z_m,
        0.373,
        abs_tol=2e-9,
    )


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
        modern.scene.objects_of_type("production_contact_rail_base_plate")
    ) == support_count
    assert len(
        modern.scene.objects_of_type("production_contact_rail_fastening_unit")
    ) == support_count
    assert len(
        modern.scene.objects_of_type("production_contact_rail_clamp_bolts")
    ) == support_count
    assert len(
        modern.scene.objects_of_type("production_contact_rail_attachment_dowels")
    ) == support_count
    assert len(
        modern.scene.objects_of_type("production_contact_rail_support_hood")
    ) == support_count
    assert mm["contactRailSupportSeparateFromRunningSupport"] is True
    assert len(modern.scene.objects_of_type("production_tube")) == 0
    assert len(modern.scene.objects_of_type("production_service_cable")) == 16
    rack_count = len(
        modern.scene.objects_of_type("production_cable_rack_r2k11")
    )
    assert rack_count == 22
    assert mm["serviceCableCount"] == 16
    assert mm["serviceCablePlacesPerHorn"] == 2
    assert mm["serviceCableOccupiedPlacesPerHorn"] == 1
    for cable in modern.scene.objects_of_type("production_service_cable"):
        assert cable.custom_properties["cableSagApplied"] is True
        assert math.isclose(
            cable.custom_properties["cableSagMidspanM"],
            0.025,
            abs_tol=1e-12,
        )
        assert math.isclose(
            cable.custom_properties["cableSagVariationFraction"],
            0.35,
            abs_tol=1e-12,
        )
        assert math.isclose(
            cable.custom_properties["cableSagPeakPhaseJitterFraction"],
            0.12,
            abs_tol=1e-12,
        )
        assert cable.custom_properties["cableSagControlStationsAdded"] > 0
    assert mm["serviceCableRackCount"] == rack_count
    assert mm["serviceCableRackFamily"] == "R2K11"
    assert mm["serviceCableRackHornCount"] == 11
    assert mm["serviceCableRacksPerCivilRing"] == 2
    assert mm["servicePipeStatus"] == (
        "implemented_normative_DN80_with_explicit_placement_fallback"
    )
    assert mm["serviceWaterMainCount"] == 1
    assert mm["serviceWaterMainMinNominalDNmm"] == 80
    assert len(modern.scene.objects_of_type("production_water_main")) == 1
    water_supports = modern.scene.objects_of_type("production_water_main_support")
    assert water_supports
    assert len(water_supports) == mm["serviceWaterMainSupportCount"]
    assert math.isclose(mm["serviceWaterMainSupportMaxPitchM"], 4.0, abs_tol=1e-12)
    assert mm["legacyStage8TubeCount"] == 0

    # Validate containment in the core-local cross-section. World X/Z include
    # the common alignment offset of both shell and cable, so measuring radius
    # from the global origin would be incorrect.
    for _name, section, _props in modern_cable_sections_core(profile):
        assert max(
            math.hypot(x, z)
            for x, z in section
        ) < profile.intrados_radius_m

    water_section, water_props = modern_water_main_section_core(profile)
    assert max(math.hypot(x, z) for x, z in water_section) < (
        profile.intrados_radius_m
    )
    assert water_props["minNominalDNmm"] == 80
    assert water_props["positionRule"] == "above_UGR_weak_current_side"
    assert water_props["exactProjectRouteResolved"] is False

    supports = water_main_support_chainages(10.0, profile)
    assert supports == (2.0, 6.0)
    assert supports[0] <= 4.0
    assert 10.0 - supports[-1] <= 4.0
    local_support = build_water_main_support_local_mesh(profile)
    assert local_support.object_type == "production_water_main_support"
    assert local_support.properties["normativeSupportIntervalResolved"] is True
    assert math.isclose(
        local_support.properties["supportMaxPitchM"],
        4.0,
        abs_tol=1e-12,
    )

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
    assert len(legacy.scene.objects_of_type("production_water_main")) == 0


def test_stage10_5_rc_6100_5600_civil_archetype_adapts_geometry():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    assert profile.civil_family == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
    assert math.isclose(profile.intrados_radius_m, 2.800, abs_tol=1e-12)
    assert math.isclose(profile.extrados_radius_m, 3.050, abs_tol=1e-12)
    assert math.isclose(profile.ring_pitch_m, 1.0, abs_tol=1e-12)

    expected_walkway_outer = math.sqrt(
        profile.intrados_radius_m**2
        - (
            profile.walkway.top_z_m
            - profile.datums.lining_axis_z_m
        ) ** 2
    )
    assert math.isclose(
        profile.walkway.outer_edge_x_m,
        expected_walkway_outer,
        abs_tol=1e-9,
    )

    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-rc6100",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
        seed=5812,
    )
    meta = build.scene.metadata["productionGeometry"]
    assert meta["civilArchetypeID"] == profile.civil_family
    assert meta["moscowCivilTopology"] == "ten_equal"
    assert meta["civilShellStatus"] == (
        "implemented_stage10_4_rc_stage9_architecture_ten_equal"
    )
    assert meta["moscowCivilCompositeDetailStatus"] == (
        "stage9_segment_joint_bolt_architecture_transferred"
    )
    assert meta["moscowCivilStage9ArchitectureTransferred"] is True
    assert meta["moscowCivilTopologyEvidenceStatus"] == (
        "S026_source_backed_10_identical_blocks"
    )

    ring_count = int(meta["moscowCivilRingCount"])
    segments = [
        obj
        for obj in build.scene.objects_of_type("lining_segment")
        if obj.custom_properties.get(
            "stage9SegmentJointFastenerArchitectureTransferred"
        ) is True
    ]
    radial = [
        obj
        for obj in build.scene.objects_of_type("prescribed_radial_joint")
        if obj.custom_properties.get(
            "stage9SegmentJointFastenerArchitectureTransferred"
        ) is True
    ]
    circum = [
        obj
        for obj in build.scene.objects_of_type("prescribed_circumferential_joint")
        if obj.custom_properties.get(
            "stage9SegmentJointFastenerArchitectureTransferred"
        ) is True
    ]
    assert len(segments) == 10 * ring_count
    assert radial == []
    assert circum == []
    assert meta["prescribedOuterJointSolidsRemoved"] is True
    assert meta["moscowCivilRenderedBlockCount"] == len(segments)
    assert meta["moscowCivilSegmentObjectCount"] == len(segments)
    assert meta["moscowCivilPrescribedRadialJointCount"] == len(radial)
    assert meta["moscowCivilPrescribedCircumferentialJointCount"] == len(circum)

    assert not build.scene.objects_of_type("bolt_head")
    assert not build.scene.objects_of_type("bolt_pocket_cutter")
    assert meta["moscowCivilBoltHeadCount"] == 0
    assert meta["moscowCivilBoltPocketCount"] == 0
    assert meta["moscowCivilBoltsEnabled"] is False

    by_ring = {}
    for segment in segments:
        p = segment.custom_properties
        assert p["civilFamily"] == profile.civil_family
        assert p["moscowCivilTopology"] == "ten_equal"
        assert p["stage9SegmentJointFastenerArchitectureTransferred"] is True
        assert p["stage9FastenerVisualTransferNotHistoricalMoscowClaim"] is True
        by_ring.setdefault(p["moscowCivilRingIndex"], []).append(segment)
    assert sorted(len(v) for v in by_ring.values()) == [10] * ring_count

    first_ring = sorted(
        by_ring[min(by_ring)],
        key=lambda obj: int(obj.segment_id),
    )
    assert [obj.segment_name for obj in first_ring] == [
        f"RC{i:02d}" for i in range(1, 11)
    ]
    for segment in first_ring:
        extent = segment.custom_properties
        assert extent["surfaceToleranceM"] > 0.0
        assert segment.reconstruction.startswith(
            "stage5_1_adaptive_cylindrical_surface"
        )

    assert math.isclose(
        meta["moscowCivilRCWorkingRebarDiameterM"],
        0.016,
        abs_tol=1e-12,
    )
    assert math.isclose(
        meta["moscowCivilRCAssemblyPinDiameterM"],
        0.022,
        abs_tol=1e-12,
    )
    assert meta["moscowCivilRCPermanentBoltedBlockJointsSource"] is False

    concrete = build.scene.objects_of_type("production_track_concrete")
    assert len(concrete) == 1
    assert concrete[0].custom_properties["physicalBottomSurface"] == (
        "moscow_5600_intrados"
    )
    assert len(build.scene.objects_of_type("production_service_cable")) == 16
    for side in (-1, 1):
        local_rack = build_r2k11_local_rack_mesh(profile, side_sign=side)
        assert max(
            math.hypot(x, z)
            for x, _y, z in local_rack.vertices
        ) < profile.intrados_radius_m


def test_stage10_5_rc_r2k11_tessellation_is_minimal_for_2mm_sagitta():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    meshing = SurfaceMeshingConfig(max_sagitta_m=0.002)
    rack = build_r2k11_local_rack_mesh(
        profile,
        side_sign=1,
        surface_meshing=meshing,
    )
    assert rack.properties["uprightArcSegments"] == 7
    assert rack.properties["hornUArcSegments"] == 5
    assert rack.properties["uprightAchievedMaxSagittaM"] <= 0.002 + 1e-12
    assert rack.properties["hornUAchievedMaxSagittaM"] <= 0.002 + 1e-12
    assert len(rack.faces) == 458

    tighter = build_r2k11_local_rack_mesh(
        profile,
        side_sign=1,
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=0.001),
    )
    assert tighter.properties["uprightArcSegments"] > rack.properties["uprightArcSegments"]
    assert tighter.properties["hornUArcSegments"] > rack.properties["hornUArcSegments"]
    assert tighter.properties["uprightAchievedMaxSagittaM"] <= 0.001 + 1e-12
    assert tighter.properties["hornUAchievedMaxSagittaM"] <= 0.001 + 1e-12


def test_stage10_5_replaced_stage7_source_skeleton_is_geometry_equivalent():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    ring_config = RingConfig()
    assembly_config = TunnelAssemblyConfig(
        n_rings=2,
        ring_width_m=ring_config.width_m,
        axis_noise_sigma_m=0.0,
        ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
    )
    meshing = SurfaceMeshingConfig(max_sagitta_m=0.002)
    config = ProductionConfig(
        namespace="stage10-5-source-skeleton-equivalence",
        moscow_profile=profile,
        moscow_stage="10.5",
        moscow_civil_topology="kba",
        moscow_civil_bolts_enabled=False,
    )

    fast = build_production_tunnel(
        ring_config=ring_config,
        assembly_config=assembly_config,
        surface_meshing=meshing,
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=config,
        seed=5812,
    )
    assert fast.source_build.ring_packages == ()
    assert fast.source_build.scene.objects == ()
    assert fast.scene.metadata["productionGeometry"][
        "sourceRingGeometrySkippedAsFullyReplaced"
    ] is True

    materialized_source = build_procedural_nominal_tunnel(
        ring_config=ring_config,
        assembly_config=assembly_config,
        surface_meshing=meshing,
        include_bolts=False,
        include_ancillary=False,
        include_prescribed_joint_solids=False,
        label_policy=LabelPolicy.STSD_COARSE,
        seed=5812,
    )
    legacy = production_module.build_production_scene(
        materialized_source,
        ancillary=fast.ancillary,
        surface_meshing=meshing,
        config=config,
    )

    # The skeleton must preserve every source pose/provenance datum used by
    # downstream production, while eliminating only transient source meshes.
    assert fast.source_build.assembly == materialized_source.assembly
    assert fast.source_build.scene.metadata == materialized_source.scene.metadata
    assert fast.scene.objects == legacy.scene.objects
    assert fast.asset_specs == legacy.asset_specs
    assert fast.alignment_stations == legacy.alignment_stations

    fast_meta = dict(fast.scene.metadata["productionGeometry"])
    legacy_meta = dict(legacy.scene.metadata["productionGeometry"])
    for key in (
        "sourceRingGeometryMaterialized",
        "sourceRingGeometrySkippedAsFullyReplaced",
    ):
        fast_meta.pop(key)
        legacy_meta.pop(key)
    assert fast_meta == legacy_meta


def test_stage10_5_rc_hidden_outer_joint_solids_are_omitted_by_default():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=2,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-no-hidden-joints",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
        ),
        seed=5812,
    )
    assert build.scene.objects_of_type("lining_segment")
    assert build.scene.objects_of_type("prescribed_radial_joint") == ()
    assert build.scene.objects_of_type("prescribed_circumferential_joint") == ()
    assert build.scene.metadata["productionGeometry"][
        "prescribedOuterJointSolidsRemoved"
    ] is True


def test_stage10_5_rc_hidden_outer_joint_solids_can_be_kept_for_debug():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=2,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-debug-hidden-joints",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
            keep_prescribed_outer_joint_solids=True,
        ),
        seed=5812,
    )
    assert build.scene.objects_of_type("prescribed_radial_joint")
    assert build.scene.objects_of_type("prescribed_circumferential_joint")
    assert build.scene.metadata["productionGeometry"][
        "prescribedOuterJointSolidsRemoved"
    ] is False


def test_stage10_5_rc_chunk_first_omits_hidden_outer_joint_solids():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    plan = build_stage10_5_rc_modern_chunk_plan(
        chunk_length_m=2.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-chunk-no-hidden-joints",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
        ),
        seed=5812,
    )
    first = next(iter_stage10_5_rc_modern_chunk_scene_packages(plan))
    assert first.objects_of_type("lining_segment")
    assert first.objects_of_type("prescribed_radial_joint") == ()
    assert first.objects_of_type("prescribed_circumferential_joint") == ()


def test_stage10_5_rc_transfer_uses_requested_surface_meshing_tolerance():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    requested = SurfaceMeshingConfig(max_sagitta_m=0.010)
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=2,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        surface_meshing=requested,
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-sagitta-contract",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
        ),
        seed=5812,
    )
    segments = build.scene.objects_of_type("lining_segment")
    assert segments
    assert all(
        math.isclose(
            float(obj.custom_properties["surfaceToleranceM"]),
            requested.max_sagitta_m,
            abs_tol=1e-12,
        )
        for obj in segments
    )


def test_stage10_5_rc_civil_ring_ranges_are_not_rebuilt_per_scene_object(monkeypatch):
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    original = production_module.civil_ring_ranges
    call_count = 0

    def counted_ranges(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        production_module,
        "civil_ring_ranges",
        counted_ranges,
    )
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=True,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-range-complexity",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
        ),
        seed=5812,
    )
    civil_count = int(
        build.scene.metadata["productionGeometry"]["moscowCivilRingCount"]
    )
    assert civil_count > 1
    assert call_count == 2

    transferred = [
        obj
        for obj in build.scene.objects
        if obj.custom_properties.get(
            "stage9SegmentJointFastenerArchitectureTransferred"
        ) is True
    ]
    assert transferred
    assert all(
        int(obj.custom_properties["liningGlobalRingCount"]) == civil_count
        for obj in transferred
    )


def test_stage10_5_rc_warp_reuses_alignment_samples_across_ring_objects(monkeypatch):
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        seed=5812,
    )
    stations = production_alignment_stations(assembly)
    original = production_module.sample_alignment_station
    sample_calls = 0

    def counted_sample(*args, **kwargs):
        nonlocal sample_calls
        sample_calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        production_module,
        "sample_alignment_station",
        counted_sample,
    )
    objects = production_module._build_stage10_4_rc_stage9_architecture_objects(
        profile=profile,
        topology="kba",
        namespace="stage10-5-rc-shared-warp-cache",
        assembly=assembly,
        stations=stations,
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=0.002),
        include_bolts=True,
        seed=5812,
    )
    civil_count = len(
        production_module.civil_ring_ranges(
            assembly.length_by_chainage_m,
            ring_pitch_m=profile.ring_pitch_m,
        )
    )
    assert objects
    assert civil_count > 1

    # The previous implementation paid three unconditional front/centre/back
    # samples per object, plus one strict sample for every unique longitudinal
    # vertex plane *inside that object*. World Y is a monotonic image of
    # chainage, so the mapped meshes let us reconstruct a conservative lower
    # bound for that legacy call count. The ring-shared cache must beat it.
    legacy_minimum_calls = 3 * len(objects) + sum(
        len({vertex[1] for vertex in obj.vertices})
        for obj in objects
    )
    assert sample_calls < legacy_minimum_calls

    # The new path should also avoid falling back to a per-vertex sampler.
    total_vertices = sum(len(obj.vertices) for obj in objects)
    assert sample_calls < total_vertices


def test_stage10_5_rc_kba_cap_strip_uses_moscow_civil_ring_datums():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-kba-cap-strip",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
        ),
        seed=5812,
    )
    civil_count = int(
        build.scene.metadata["productionGeometry"]["moscowCivilRingCount"]
    )
    assert civil_count > 1

    cleaned = strip_internal_lining_cap_faces(build.scene)
    strip_meta = cleaned.metadata["productionLiningCapStrip"]
    assert int(strip_meta["removedFaces"]) > 0

    segments = cleaned.objects_of_type("lining_segment")
    assert segments
    assert all(
        obj.custom_properties["liningCapCleanupPlaneMode"]
        == "mesh_extrema_with_metadata_guard"
        for obj in segments
    )

    # Outer tunnel ends remain capped; only interfaces between the independent
    # 1.0 m Moscow civil rings are opened. This deliberately uses the Moscow
    # civil-ring metadata rather than representative source Stage-9 ring IDs.
    first = [
        obj for obj in segments
        if int(obj.custom_properties["liningRingIndex"]) == 0
    ]
    last = [
        obj for obj in segments
        if int(obj.custom_properties["liningRingIndex"]) == civil_count - 1
    ]
    assert first and last
    front_y = float(first[0].custom_properties["liningRingFrontWorldYM"])
    back_y = float(last[0].custom_properties["liningRingBackWorldYM"])
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


def test_stage10_5_rc_ten_equal_topology_reuses_stage9_fastener_pipeline():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=2,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=True,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-ten-equal-bolts",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="ten_equal",
        ),
        seed=5812,
    )
    meta = build.scene.metadata["productionGeometry"]
    assert meta["moscowCivilTopology"] == "ten_equal"
    assert meta["moscowCivilTopologyEvidenceStatus"] == (
        "S026_source_backed_10_identical_blocks"
    )
    assert meta["moscowCivilBoltsEnabled"] is True
    assert meta["moscowCivilLegacyBoltLayout"] == "type1_centered"
    assert math.isclose(
        meta["moscowCivilLegacyBoltBooleanOverlapM"],
        0.005,
        abs_tol=1e-12,
    )
    assert meta["moscowCivilBoltRenderMode"] == "pocket_cutter_plus_visible_head"
    assert meta["moscowCivilBoltPocketBooleansEnabled"] is True
    assert meta["moscowCivilBoltPocketRecessOmitted"] is False
    assert meta["moscowCivilHeadSeatingBooleanEnabled"] is False
    assert meta["moscowCivilHiddenBoltBodyOmitted"] is True

    segments = [
        obj
        for obj in build.scene.objects_of_type("lining_segment")
        if obj.custom_properties.get(
            "stage9SegmentJointFastenerArchitectureTransferred"
        ) is True
    ]
    heads = build.scene.objects_of_type("bolt_head")
    cutters = build.scene.objects_of_type("bolt_pocket_cutter")
    assert heads
    assert len(cutters) == len(heads)

    # 2 x 1.35 m source rings make two complete 1 m Moscow civil rings plus
    # one clipped 0.7 m ring. The exact Stage-9 TYPE1 layout contributes three
    # visible heads and one transient pocket cutter per segment. Hidden bolt
    # bodies are omitted, and the clipped final ring receives no fasteners.
    full_civil_rings = 2
    assert len(heads) == full_civil_rings * 10 * 3
    assert meta["moscowCivilBoltHeadCount"] == len(heads)
    assert meta["moscowCivilBoltPocketCount"] == len(cutters)
    assert meta["moscowCivilExpectedBlenderBoltBooleanOps"] == len(cutters)

    full_ring_segment_names = {
        obj.segment_name
        for obj in segments
        if obj.custom_properties["moscowCivilRingIndex"] < full_civil_rings
    }
    assert full_ring_segment_names == {
        f"RC{i:02d}" for i in range(1, 11)
    }

    for head in sorted(
        heads,
        key=lambda o: o.custom_properties["boltIndex"],
    ):
        hp = head.custom_properties
        assert hp["legacyBoltLayout"] == "type1_centered"
        assert hp["stage9FastenerVisualTransferNotHistoricalMoscowClaim"] is True
        assert hp["visibleHeadOnlyMode"] is True
        assert hp["hiddenBoltBodyOmitted"] is True
        assert hp["boltPocketRecessOmitted"] is False
        assert hp["hiddenEmbeddedHeadBottomCapOmitted"] is True
        assert hp["cutTargetBeforeDisplay"] is False
        assert hp["booleanParticipation"] is False
        assert hp["moscowCivilBoltBooleanParticipation"] is False
        assert "booleanTarget" not in hp
        n = int(hp["boltHeadRingVertices"])
        radius = float(hp["boltHeadRadiusM"])
        achieved = radius * (1.0 - math.cos(math.pi / n))
        assert 6 <= n <= 10
        assert len(head.vertices) == 2 * n
        assert len(head.faces) == n + 1
        assert math.isclose(
            float(hp["boltHeadSurfaceToleranceM"]),
            0.002,
            abs_tol=1e-12,
        )
        assert math.isclose(
            float(hp["boltHeadAchievedMaxSagittaM"]),
            achieved,
            abs_tol=1e-12,
        )
        assert achieved <= 0.002 + 1e-12
        if n > 6:
            previous = radius * (1.0 - math.cos(math.pi / (n - 1)))
            assert previous > 0.002 - 1e-12


def test_stage10_5_rc_legacy_bolt_boolean_mode_remains_available_for_debug():
    from tunnel_scanner_core.blender_adapter import plan_bolt_boolean_operations

    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=1,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=True,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-debug-bolt-booleans",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="ten_equal",
            keep_moscow_civil_bolt_pocket_booleans=True,
        ),
        seed=5812,
    )
    heads = build.scene.objects_of_type("bolt_head")
    cutters = build.scene.objects_of_type("bolt_pocket_cutter")
    meta = build.scene.metadata["productionGeometry"]
    assert heads
    assert len(cutters) == len(heads)
    assert meta["moscowCivilBoltRenderMode"] == "legacy_pocket_and_head_boolean"
    assert meta["moscowCivilBoltPocketBooleansEnabled"] is True
    assert meta["moscowCivilBoltPocketCount"] == len(cutters)
    assert meta["moscowCivilExpectedBlenderBoltBooleanOps"] == 2 * len(heads)
    assert math.isclose(
        meta["moscowCivilLegacyBoltBooleanOverlapM"],
        0.005,
        abs_tol=1e-12,
    )
    operations = plan_bolt_boolean_operations(build.scene)
    assert len(operations) == 2 * len(heads)


def test_stage10_5_rc_kba_preserves_boundary_fastener_mesh_at_exact_scene_end():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    # 20 * 1.35 m = exactly 27.0 m, so the final Moscow 1 m civil ring is
    # complete. This reproduces the same crop-edge condition as 3000 rings
    # (4050 m) without constructing a multi-kilometre unit-test scene.
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=20,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        include_bolts=True,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-kba-boundary-fastener",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
        ),
        seed=5812,
    )
    assert math.isclose(
        build.assembly.length_by_chainage_m,
        27.0,
        abs_tol=1e-12,
    )
    meta = build.scene.metadata["productionGeometry"]
    civil_count = int(meta["moscowCivilRingCount"])
    assert civil_count == 27

    fasteners = [
        obj
        for object_type in ("bolt_head", "bolt_pocket_cutter")
        for obj in build.scene.objects_of_type(object_type)
    ]
    assert fasteners

    boundary = [
        obj
        for obj in fasteners
        if int(obj.custom_properties["moscowCivilRingIndex"])
        in {0, civil_count - 1}
    ]
    assert boundary

    extrapolated = [
        obj
        for obj in boundary
        if obj.custom_properties[
            "moscowCivilBoundaryFastenerAlignmentExtrapolated"
        ]
        is True
    ]
    assert extrapolated
    assert any(
        "end"
        in tuple(
            obj.custom_properties[
                "moscowCivilBoundaryFastenerExtrapolatedSides"
            ]
        )
        for obj in extrapolated
    )
    assert all(
        obj.custom_properties[
            "moscowCivilBoundaryFastenerExtrapolationMode"
        ]
        == "terminal_linear_alignment_extension_preserve_stage9_mesh"
        for obj in extrapolated
    )
    assert all(
        0.0
        < float(
            obj.custom_properties[
                "moscowCivilBoundaryFastenerMaxOverhangM"
            ]
        )
        < 0.1
        for obj in extrapolated
    )

    # Interior transferred hardware must never use terminal extrapolation.
    interior = [
        obj
        for obj in fasteners
        if int(obj.custom_properties["moscowCivilRingIndex"])
        not in {0, civil_count - 1}
    ]
    assert interior
    assert all(
        obj.custom_properties[
            "moscowCivilBoundaryFastenerAlignmentExtrapolated"
        ]
        is False
        for obj in interior
    )


def test_stage10_5_rc_kba_topology_reuses_stage9_fastener_pipeline():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        include_bolts=True,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-kba",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
        ),
        seed=5812,
    )
    meta = build.scene.metadata["productionGeometry"]
    assert meta["moscowCivilTopology"] == "kba"
    assert meta["moscowCivilTopologyEvidenceStatus"] == (
        "user_reported_Moscow_photo_reference_pending_research_pinpoint"
    )
    assert meta["civilShellStatus"] == (
        "implemented_stage10_4_rc_stage9_architecture_kba"
    )
    ring_count = int(meta["moscowCivilRingCount"])

    segments = [
        obj
        for obj in build.scene.objects_of_type("lining_segment")
        if obj.custom_properties.get(
            "stage9SegmentJointFastenerArchitectureTransferred"
        ) is True
    ]
    assert len(segments) == 6 * ring_count
    first_ring = [
        obj
        for obj in segments
        if obj.custom_properties["moscowCivilRingIndex"] == 0
    ]
    assert {obj.segment_kind for obj in first_ring} == {"K", "B", "A"}
    assert [obj.segment_name for obj in sorted(first_ring, key=lambda o: o.segment_id)] == [
        "K",
        "B1",
        "A1",
        "A2",
        "A3",
        "B2",
    ]

    assert meta["moscowCivilRotationStrategy"] == "ringwise_gaussian"
    assert meta["moscowCivilRotationModel"] == (
        "stage7_ring_pose_on_independent_moscow_civil_rhythm"
    )
    assert meta["moscowCivilRotationAppliedOnlyToLining"] is True

    rotation_by_ring = {}
    for segment in segments:
        p = segment.custom_properties
        ring_index = int(p["moscowCivilRingIndex"])
        rotation = float(p["ringRotationDeg"])
        rotation_by_ring.setdefault(ring_index, set()).add(round(rotation, 12))
        assert p["moscowCivilRotationStrategy"] == "ringwise_gaussian"
        assert p["moscowCivilIndependentRingPoseStream"] is True
        assert p["stage7RingAxialStaggerTransferred"] is True
        assert math.isclose(
            rotation,
            float(p["ringNominalRotationDeg"])
            + float(p["ringAngularImperfectionDeg"]),
            abs_tol=1e-12,
        )
        assert p["moscowCivilRotationFrame"] == (
            "local_cross_section_before_stage10_alignment"
        )

    assert all(len(values) == 1 for values in rotation_by_ring.values())
    ring_rotations = [
        next(iter(rotation_by_ring[index]))
        for index in sorted(rotation_by_ring)
    ]
    assert any(abs(value) > 1e-9 for value in ring_rotations)
    assert len(set(ring_rotations)) > 1

    # K must move around the lining with its complete ring, rather than staying
    # pinned to the crown. Compare its world XZ direction to the alignment
    # centre for multiple rings.
    k_angles = []
    for ring_index in sorted(rotation_by_ring):
        k = next(
            obj
            for obj in segments
            if int(obj.custom_properties["moscowCivilRingIndex"]) == ring_index
            and obj.segment_name == "K"
        )
        p = k.custom_properties
        cx = float(p["productionRingCenterOffsetX"])
        cz = float(p["productionRingCenterOffsetZ"])
        mean_x = sum(v[0] for v in k.vertices) / len(k.vertices)
        mean_z = sum(v[2] for v in k.vertices) / len(k.vertices)
        k_angles.append(math.degrees(math.atan2(mean_x - cx, mean_z - cz)))
    assert max(k_angles) - min(k_angles) > 10.0

    radial = [
        obj
        for obj in build.scene.objects_of_type("prescribed_radial_joint")
        if obj.custom_properties.get(
            "stage9SegmentJointFastenerArchitectureTransferred"
        ) is True
    ]
    assert radial == []
    assert meta["prescribedOuterJointSolidsRemoved"] is True
    assert all(
        obj.custom_properties["legacyPrescribedJointGeometry"] is True
        for obj in radial
    )

    heads = build.scene.objects_of_type("bolt_head")
    cutters = build.scene.objects_of_type("bolt_pocket_cutter")
    assert heads
    assert len(cutters) == len(heads)
    assert meta["moscowCivilBoltHeadCount"] == len(heads)
    assert meta["moscowCivilBoltPocketCount"] == len(cutters)
    assert meta["moscowCivilBoltsEnabled"] is True
    assert meta["moscowCivilLegacyBoltLayout"] == "type1_centered"
    assert meta["moscowCivilBoltRenderMode"] == "pocket_cutter_plus_visible_head"
    assert meta["moscowCivilExpectedBlenderBoltBooleanOps"] == len(cutters)
    assert meta["moscowCivilBoltPocketBooleansEnabled"] is True
    assert meta["moscowCivilHeadSeatingBooleanEnabled"] is False
    assert math.isclose(
        meta["moscowCivilLegacyBoltBooleanOverlapM"],
        0.005,
        abs_tol=1e-12,
    )
    for head in sorted(
        heads,
        key=lambda o: o.custom_properties["boltIndex"],
    ):
        hp = head.custom_properties
        assert hp["legacyBoltLayout"] == "type1_centered"
        assert hp["stage9FastenerVisualTransferNotHistoricalMoscowClaim"] is True
        assert hp["visibleHeadOnlyMode"] is True
        assert hp["hiddenBoltBodyOmitted"] is True
        assert hp["boltPocketRecessOmitted"] is False
        assert hp["moscowCivilBoltBooleanParticipation"] is False
        assert "booleanTarget" not in hp


def test_stage10_5_periodic_assets_declare_exact_reusable_mesh_prototypes():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-periodic-prototypes",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
        seed=5812,
    )

    reusable_types = {
        "production_lvt_block",
        "production_lvt_rubber_boot",
        "production_apc4_rail_pad",
        "production_apc4_fastening",
        "production_contact_rail_support_block",
        "production_contact_rail_base_plate",
        "production_contact_rail_bracket",
        "production_contact_rail_insulator",
        "production_contact_rail_fastening_unit",
        "production_contact_rail_clamp_bolts",
        "production_contact_rail_attachment_dowels",
        "production_contact_rail_support_hood",
        "production_cable_rack_r2k11",
        "production_water_main_support",
    }
    objects = [
        obj for obj in build.scene.objects
        if obj.object_type in reusable_types
    ]
    assert objects
    assert {obj.object_type for obj in objects} == reusable_types

    local_by_key = {}
    instances_by_key = {}
    for obj in objects:
        props = obj.custom_properties
        assert props["meshPrototypeMode"] == "translation_only_shared_mesh_v1"
        assert props["meshPrototypeGeometryExact"] is True
        assert props["meshPrototypeLiDARSurfaceUnchanged"] is True
        assert int(props["meshPrototypeVertexCount"]) == len(obj.vertices)
        assert int(props["meshPrototypeFaceCount"]) == len(obj.faces)

        translation = tuple(float(v) for v in props["meshPrototypeTranslationM"])
        assert translation == (
            float(props["alignmentOffsetX"]),
            float(props["alignmentWorldY"]),
            float(props["alignmentOffsetZ"]),
        )
        local = tuple(
            (
                vertex[0] - translation[0],
                vertex[1] - translation[1],
                vertex[2] - translation[2],
            )
            for vertex in obj.vertices
        )
        key = str(props["meshPrototypeKey"])
        if key in local_by_key:
            reference_vertices, reference_faces = local_by_key[key]
            assert len(reference_vertices) == len(local)
            assert reference_faces == obj.faces
            for actual, expected in zip(local, reference_vertices):
                assert all(
                    math.isclose(a, b, abs_tol=2e-12)
                    for a, b in zip(actual, expected)
                )
        else:
            local_by_key[key] = (local, obj.faces)
        instances_by_key[key] = instances_by_key.get(key, 0) + 1

    # At least the 600 mm permanent-way chain must create many logical
    # instances from a small fixed prototype set.
    assert any(count >= 5 for count in instances_by_key.values())
    assert len(local_by_key) < len(objects)


def test_stage10_5_rc_chunk_first_3000_ring_first_chunk_is_local(monkeypatch):
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    assembly = TunnelAssemblyConfig(
        n_rings=3000,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
        ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
    )
    config = ProductionConfig(
        namespace="stage10-5-rc-chunk-first-3000",
        moscow_profile=profile,
        moscow_stage="10.5",
        moscow_civil_topology="kba",
    )
    original = production_module._moscow_rc_legacy_ring_mesh
    built_civil_rings = 0

    def counted_ring(*args, **kwargs):
        nonlocal built_civil_rings
        built_civil_rings += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        production_module,
        "_moscow_rc_legacy_ring_mesh",
        counted_ring,
    )
    plan = build_stage10_5_rc_modern_chunk_plan(
        chunk_length_m=10.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        assembly_config=assembly,
        include_bolts=False,
        production_config=config,
        seed=5812,
    )
    assert math.isclose(
        plan.assembly.length_by_chainage_m,
        4050.0,
        abs_tol=1e-12,
    )
    assert int(
        plan.metadata["productionGeometry"]["moscowCivilRingCount"]
    ) == 4050
    assert built_civil_rings == 0

    first = next(
        iter_stage10_5_rc_modern_chunk_scene_packages(plan)
    )
    # A 10 m chunk owns only the ten 1 m Moscow civil rings whose midpoints
    # lie inside it. Most importantly, consuming the first lazy chunk must not
    # materialize the remaining 4040 civil rings.
    assert built_civil_rings == 10
    assert first.metadata["productionChunk"]["startChainageM"] == 0.0
    assert first.metadata["productionChunk"]["endChainageM"] == 10.0
    assert all(
        float(obj.extra_properties.get("eventChainageM", 0.0)) < 10.0
        for obj in first.objects
        if "eventChainageM" in obj.extra_properties
    )


def test_stage10_5_rc_single_chunk_builder_matches_lazy_iterator():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    plan = build_stage10_5_rc_modern_chunk_plan(
        chunk_length_m=2.35,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        assembly_config=TunnelAssemblyConfig(
            n_rings=6,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=0.002),
        include_bolts=True,
        production_config=ProductionConfig(
            namespace="stage10-5-rc-single-chunk-equivalence",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_civil_topology="kba",
        ),
        seed=5812,
    )
    lazy = tuple(iter_stage10_5_rc_modern_chunk_scene_packages(plan))
    direct = tuple(
        build_stage10_5_rc_modern_chunk_scene_package(
            plan,
            chunk.chunk_id,
        )
        for chunk in plan.chunks
    )
    assert direct == lazy


def test_stage10_5_rc_chunk_first_matches_materialized_chunk_geometry():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    assembly = TunnelAssemblyConfig(
        n_rings=6,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
        ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
    )
    config = ProductionConfig(
        namespace="stage10-5-rc-chunk-first-equivalence",
        moscow_profile=profile,
        moscow_stage="10.5",
        moscow_civil_topology="kba",
    )
    meshing = SurfaceMeshingConfig(max_sagitta_m=0.002)
    full = build_production_tunnel(
        assembly_config=assembly,
        surface_meshing=meshing,
        include_bolts=True,
        production_config=config,
        seed=5812,
    )
    plan = build_stage10_5_rc_modern_chunk_plan(
        chunk_length_m=2.35,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        assembly_config=assembly,
        surface_meshing=meshing,
        include_bolts=True,
        production_config=config,
        seed=5812,
    )
    assert plan.source_build.scene.objects == ()
    assert plan.source_build.ring_packages == ()
    assert plan.metadata["productionGeometry"]["chunkFirstGeneration"] is True

    expected = tuple(
        production_module.iter_chunk_scene_packages(
            full,
            chunk_length_m=2.35,
            boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        )
    )
    actual = tuple(
        iter_stage10_5_rc_modern_chunk_scene_packages(plan)
    )
    assert len(actual) == len(expected) == len(plan.chunks)

    for got, want in zip(actual, expected):
        assert got.name == want.name
        assert got.label_policy == want.label_policy
        assert got.metadata["productionChunk"] == {
            **want.metadata["productionChunk"],
            "chunkFirstGeneration": True,
        }
        assert [obj.name for obj in got.objects] == [
            obj.name for obj in want.objects
        ]
        assert [obj.instance_id for obj in got.objects] == [
            obj.instance_id for obj in want.objects
        ]
        for got_obj, want_obj in zip(got.objects, want.objects):
            assert got_obj.object_type == want_obj.object_type
            assert got_obj.ring_id == want_obj.ring_id
            assert got_obj.faces == want_obj.faces
            assert got_obj.collection_path == want_obj.collection_path
            assert got_obj.extra_properties == want_obj.extra_properties
            assert got_obj.vertices == want_obj.vertices


def test_stage10_5_rc_chunk_first_localized_geometry_matches_materialized_chunks():
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    assembly = TunnelAssemblyConfig(
        n_rings=4,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
        ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
    )
    config = ProductionConfig(
        namespace="stage10-5-rc-chunk-first-localized",
        moscow_profile=profile,
        moscow_stage="10.5",
        moscow_civil_topology="kba",
    )
    full = build_production_tunnel(
        assembly_config=assembly,
        include_bolts=False,
        production_config=config,
        seed=5812,
    )
    plan = build_stage10_5_rc_modern_chunk_plan(
        chunk_length_m=2.0,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        assembly_config=assembly,
        include_bolts=False,
        production_config=config,
        seed=5812,
    )
    expected = tuple(
        production_module.iter_chunk_scene_packages(
            full,
            chunk_length_m=2.0,
            boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
            localize_coordinates=True,
        )
    )
    actual = tuple(
        iter_stage10_5_rc_modern_chunk_scene_packages(
            plan,
            localize_coordinates=True,
        )
    )
    assert len(actual) == len(expected)
    for got, want in zip(actual, expected):
        assert got.metadata["productionChunk"]["chunkWorldOrigin"] == (
            want.metadata["productionChunk"]["chunkWorldOrigin"]
        )
        assert [obj.name for obj in got.objects] == [
            obj.name for obj in want.objects
        ]
        for got_obj, want_obj in zip(got.objects, want.objects):
            assert got_obj.faces == want_obj.faces
            assert got_obj.vertices == want_obj.vertices
            assert got_obj.extra_properties == want_obj.extra_properties


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


def test_stage10_5_exact_alignment_compaction_removes_only_collinear_samples():
    stations = (
        AlignmentStation(0.0, 0.0, 0.0, 0.0, "start"),
        AlignmentStation(0.5, 0.5, 0.5, -0.25, "mid_exact"),
        AlignmentStation(1.0, 1.0, 1.0, -0.5, "end_segment"),
        AlignmentStation(1.5, 1.5, 1.2, -0.1, "bend"),
    )
    compact = compact_exact_collinear_alignment_stations(stations)
    assert [s.source for s in compact] == ["start", "end_segment", "bend"]


def test_stage10_5_continuous_sweeps_use_zero_error_station_compaction_by_default():
    profile = load_stage10_initial_moscow_profile()
    assembly = TunnelAssemblyConfig(
        n_rings=20,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
    )
    compact = build_production_tunnel(
        assembly_config=assembly,
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-compact",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
        seed=5812,
    )
    dense = build_production_tunnel(
        assembly_config=assembly,
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-dense",
            moscow_profile=profile,
            moscow_stage="10.5",
            compact_exact_collinear_continuous_stations=False,
        ),
        seed=5812,
    )

    c_rail = compact.scene.objects_of_type("production_rail")[0]
    d_rail = dense.scene.objects_of_type("production_rail")[0]
    cp = c_rail.custom_properties
    dp = d_rail.custom_properties
    assert cp["alignmentCompactionMode"] == "exact_zero_error_collinear"
    assert dp["alignmentCompactionMode"] == "disabled"
    assert cp["sourceAlignmentStationCount"] == dp["sourceAlignmentStationCount"]
    assert cp["sweepAlignmentStationCount"] < cp["sourceAlignmentStationCount"]
    assert cp["exactCollinearAlignmentStationsRemoved"] > 0
    assert len(c_rail.faces) < len(d_rail.faces)

    # The optimization is topology-only along mathematically collinear spans:
    # tunnel endpoints and rail cross-section are unchanged.
    assert c_rail.vertices[:118] == d_rail.vertices[:118]
    assert c_rail.vertices[-118:] == d_rail.vertices[-118:]
