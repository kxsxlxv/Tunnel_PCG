import math

from tunnel_scanner_core import (
    LabelPolicy,
    ProductionConfig,
    R65ProductionProfile,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_production_tunnel,
    build_stage10_2_local_event_meshes,
    load_stage10_initial_moscow_profile,
    r65_rail_center_offsets_for_gauge,
    sleeper_chainages,
    track_concrete_profile_xz,
)


def _rail_centers(profile):
    r65 = R65ProductionProfile()
    return r65_rail_center_offsets_for_gauge(
        profile.track.gauge_m,
        profile=r65,
        measurement_below_top_m=(
            profile.track.gauge_measurement_below_ugr_m
        ),
    )


def test_stage10_2_profile_closes_sleeper_kd65_and_concrete_data():
    profile = load_stage10_initial_moscow_profile()
    s = profile.sleeper
    k = profile.fastening
    tc = profile.track_concrete

    assert math.isclose(s.top_z_m, -0.220, abs_tol=1e-12)
    assert math.isclose(s.bottom_z_m, -0.385, abs_tol=1e-12)
    assert math.isclose(s.length_m, 2.650, abs_tol=1e-12)
    assert math.isclose(s.thickness_m, 0.165, abs_tol=1e-12)
    assert math.isclose(s.upper_face_width_m, 0.165, abs_tol=1e-12)
    assert math.isclose(s.lower_face_width_m, 0.250, abs_tol=1e-12)
    assert math.isclose(s.sawn_side_height_m, 0.135, abs_tol=1e-12)
    assert math.isclose(s.density_per_km, 1680.0, abs_tol=1e-12)
    assert math.isclose(s.pitch_m, 1000.0 / 1680.0, abs_tol=1e-12)

    assert math.isclose(k.baseplate_transverse_m, 0.370, abs_tol=1e-12)
    assert math.isclose(k.baseplate_longitudinal_m, 0.165, abs_tol=1e-12)
    assert math.isclose(k.baseplate_max_height_m, 0.0556, abs_tol=1e-12)
    assert math.isclose(k.baseplate_rail_seat_height_m, 0.020, abs_tol=1e-12)
    assert math.isclose(k.under_pad_thickness_m, 0.006, abs_tol=1e-12)
    assert math.isclose(k.rail_pad_total_thickness_m, 0.014, abs_tol=1e-12)
    assert math.isclose(k.track_screw_length_m, 0.150, abs_tol=1e-12)
    assert math.isclose(k.track_screw_head_radius_m, 0.018, abs_tol=1e-12)
    assert math.isclose(k.track_screw_head_height_m, 0.008, abs_tol=1e-12)
    assert k.track_screw_head_mode == "simplified_visible_flat_head_fallback"
    assert math.isclose(k.clamp_bolt_length_m, 0.075, abs_tol=1e-12)
    assert math.isclose(k.clamp_bolt_axis_offset_m, 0.100, abs_tol=1e-12)
    assert math.isclose(k.spring_clamp_center_offset_m, 0.082, abs_tol=1e-12)
    assert math.isclose(k.spring_clamp_box_transverse_m, 0.055, abs_tol=1e-12)
    assert k.clamp_geometry_mode == "simplified_parameterized_initial_geometry"
    assert k.baseplate_mesh_mode == "source_callout_simplified_section"

    support_gap = (-profile.track.rail_height_m) - s.top_z_m
    support_stack = (
        k.under_pad_thickness_m
        + k.baseplate_rail_seat_height_m
        + k.rail_pad_total_thickness_m
    )
    assert math.isclose(support_gap, 0.040, abs_tol=1e-12)
    assert math.isclose(support_stack, support_gap, abs_tol=1e-12)

    assert math.isclose(tc.surface_cross_slope_to_drain, 0.03, abs_tol=1e-12)
    assert math.isclose(tc.central_drain_clear_width_m, 0.900, abs_tol=1e-12)
    assert math.isclose(tc.central_drain_bottom_z_m, -0.530, abs_tol=1e-12)
    assert math.isclose(tc.water_groove_width_m, 0.050, abs_tol=1e-12)
    assert math.isclose(tc.water_groove_depth_m, 0.025, abs_tol=1e-12)
    assert tc.surface_reference_mode == "rail_axis_datum_fallback"
    assert tc.groove_position_mode == "centered_in_central_drain_bottom_fallback"


def test_stage10_2_track_concrete_profile_has_source_backed_drain_slope_and_intrados():
    profile = load_stage10_initial_moscow_profile()
    centers = _rail_centers(profile)
    poly = track_concrete_profile_xz(
        profile,
        rail_centers_profile_x=centers,
    )

    drain_half = 0.45
    drain_top_expected = (
        -0.230
        + 0.03 * (drain_half - abs(centers[1]))
    )
    assert math.isclose(poly[1][0], -drain_half, abs_tol=1e-12)
    assert math.isclose(poly[1][1], drain_top_expected, abs_tol=1e-12)
    assert math.isclose(poly[2][0], -drain_half, abs_tol=1e-12)
    assert math.isclose(poly[2][1], -0.530, abs_tol=1e-12)
    assert math.isclose(poly[4][0], -0.025, abs_tol=1e-12)
    assert math.isclose(poly[4][1], -0.555, abs_tol=1e-12)
    assert math.isclose(poly[5][0], +0.025, abs_tol=1e-12)
    assert math.isclose(poly[5][1], -0.555, abs_tol=1e-12)
    assert math.isclose(poly[7][0], +drain_half, abs_tol=1e-12)
    assert math.isclose(poly[7][1], -0.530, abs_tol=1e-12)

    xout, zout = poly[9]
    assert math.isclose(xout, 1.7315755630613174, abs_tol=2e-12)
    assert math.isclose(zout, -0.20193644908391087, abs_tol=2e-12)
    circle_error = (
        xout * xout
        + (zout - profile.datums.lining_axis_z_m) ** 2
        - profile.intrados_radius_m ** 2
    )
    assert abs(circle_error) < 2e-12

    invert = min(z for _x, z in poly)
    assert math.isclose(invert, -0.880, abs_tol=2e-12)

    bottom_at_rail = (
        profile.datums.lining_axis_z_m
        - math.sqrt(
            profile.intrados_radius_m**2
            - abs(centers[1])**2
        )
    )
    assert bottom_at_rail <= profile.track_concrete.minimum_bottom_at_rail_z_m


def test_stage10_2_local_sleeper_and_kd65_stack_closes_to_r65_base():
    profile = load_stage10_initial_moscow_profile()
    meshes = build_stage10_2_local_event_meshes(
        profile,
        rail_centers_profile_x=_rail_centers(profile),
    )
    by_type = {m.object_type: m for m in meshes}

    assert set(by_type) == {
        "production_sleeper",
        "production_under_baseplate_pad",
        "production_baseplate",
        "production_rail_pad",
        "production_track_screw",
        "production_clamp_hardware",
    }

    sleeper = by_type["production_sleeper"]
    xs = [v[0] for v in sleeper.vertices]
    zs = [v[2] for v in sleeper.vertices]
    assert math.isclose(max(xs) - min(xs), 2.650, abs_tol=2e-12)
    assert math.isclose(max(zs), -1.890, abs_tol=2e-12)
    assert math.isclose(min(zs), -2.055, abs_tol=2e-12)

    under = by_type["production_under_baseplate_pad"]
    assert math.isclose(min(v[2] for v in under.vertices), -1.890, abs_tol=2e-12)
    assert math.isclose(max(v[2] for v in under.vertices), -1.884, abs_tol=2e-12)

    railpad = by_type["production_rail_pad"]
    assert math.isclose(min(v[2] for v in railpad.vertices), -1.864, abs_tol=2e-12)
    assert math.isclose(max(v[2] for v in railpad.vertices), -1.850, abs_tol=2e-12)


def test_stage10_2_sleeper_events_are_deterministic_and_not_ring_synchronized():
    profile = load_stage10_initial_moscow_profile()
    pitch = profile.sleeper.pitch_m
    chainages = sleeper_chainages(20.0, pitch_m=pitch)

    assert chainages == sleeper_chainages(20.0, pitch_m=pitch)
    assert math.isclose(chainages[0], 0.5 * pitch, abs_tol=1e-12)
    assert all(
        math.isclose(b - a, pitch, abs_tol=2e-12)
        for a, b in zip(chainages, chainages[1:])
    )
    # Ring pitch and sleeper pitch must remain independent periodic systems.
    assert not math.isclose(
        pitch / 1.35,
        round(pitch / 1.35),
        abs_tol=1e-12,
    )


def test_stage10_2_production_replaces_stage9_pavement_and_adds_periodic_support_chain():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=4,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(
            namespace="stage10-2-integration",
            moscow_profile=profile,
            moscow_stage="10.2",
        ),
        seed=5812,
    )

    meta = build.scene.metadata["productionGeometry"]
    assert meta["domainStage"] == "10.2"
    assert meta["permanentWayStatus"] == "implemented_stage10_2_initial_geometry"
    assert meta["contactRailStatus"] == "deferred_to_stage10_3"
    assert meta["civilShellStatus"] == "deferred_to_stage10_4"
    assert len(build.scene.objects_of_type("production_pavement")) == 0
    assert len(build.scene.objects_of_type("production_track_concrete")) == 1
    assert len(build.scene.objects_of_type("production_rail")) == 2

    expected_events = sleeper_chainages(
        build.assembly.length_by_chainage_m,
        pitch_m=profile.sleeper.pitch_m,
    )
    assert len(expected_events) == 9
    assert meta["sleeperCount"] == len(expected_events)
    for object_type in (
        "production_sleeper",
        "production_under_baseplate_pad",
        "production_baseplate",
        "production_rail_pad",
        "production_track_screw",
        "production_clamp_hardware",
    ):
        assert len(build.scene.objects_of_type(object_type)) == len(expected_events)

    for rail in build.scene.objects_of_type("production_rail"):
        assert rail.custom_properties["railFootBottomContactFaceOmitted"] is True
        assert rail.custom_properties["omittedLongitudinalEdgeCount"] == 2

    first_sleeper = build.scene.objects_of_type("production_sleeper")[0]
    assert math.isclose(
        first_sleeper.custom_properties["eventChainageM"],
        0.5 * profile.sleeper.pitch_m,
        abs_tol=2e-12,
    )
    assert first_sleeper.custom_properties["periodicPhaseRule"] == (
        "half_pitch_from_tunnel_start"
    )


def test_stage10_2_permanent_way_has_no_exact_duplicate_faces():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=2,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-2-topology",
            moscow_profile=profile,
            moscow_stage="10.2",
        ),
        seed=5812,
    )
    permanent_way_types = {
        "production_track_concrete",
        "production_rail",
        "production_sleeper",
        "production_under_baseplate_pad",
        "production_baseplate",
        "production_rail_pad",
        "production_track_screw",
        "production_clamp_hardware",
    }
    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: obj.object_type in permanent_way_types,
    )
    assert audit.duplicate_group_count == 0
