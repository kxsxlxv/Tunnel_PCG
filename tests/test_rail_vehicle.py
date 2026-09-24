from __future__ import annotations

import math

from tunnel_scanner_core.rail_vehicle import (
    EnvelopeAllowanceBudget,
    MOSKVA_2020_81_775,
    ObstacleRouteRelevance,
    TrackFrame,
    classify_route_hypothesis_intersections,
    rail_vehicle_pose_from_leading_bogie,
    screening_circular_curve_throw,
)


def _straight_frame(chainage_m: float) -> TrackFrame:
    return TrackFrame(
        chainage_m=chainage_m,
        position=(0.0, chainage_m, 0.0),
        tangent=(0.0, 1.0, 0.0),
        up=(0.0, 0.0, 1.0),
    )


def test_81_775_reference_geometry_values():
    vehicle = MOSKVA_2020_81_775
    assert math.isclose(vehicle.length_over_couplers_m, 20.080)
    assert math.isclose(vehicle.maximum_width_m, 2.740)
    assert math.isclose(vehicle.empty_height_above_top_of_rail_m, 3.680)
    assert math.isclose(vehicle.vehicle_base_m, 12.600)
    assert math.isclose(vehicle.symmetric_overhang_proxy_m, 3.740)
    assert math.isclose(
        vehicle.documented_lateral_stop_clearance_upper_m,
        0.016,
    )


def test_straight_vehicle_pose_uses_exact_bogie_pivot_chord():
    vehicle = MOSKVA_2020_81_775
    pose = rail_vehicle_pose_from_leading_bogie(
        _straight_frame,
        leading_chainage_m=30.0,
        geometry=vehicle,
    )
    assert math.isclose(
        pose.trailing_bogie.chainage_m,
        30.0 - vehicle.vehicle_base_m,
        abs_tol=2e-9,
    )
    assert math.isclose(
        pose.bogie_pivot_distance_m,
        vehicle.vehicle_base_m,
        abs_tol=2e-9,
    )
    assert pose.carbody.forward == (0.0, 1.0, 0.0)
    assert pose.carbody.right == (1.0, 0.0, 0.0)
    assert pose.carbody.up == (0.0, 0.0, 1.0)


def test_circular_curve_pose_matches_exact_centre_and_end_throw():
    vehicle = MOSKVA_2020_81_775
    radius = 300.0
    centre_chainage = 1000.0
    half_bogie_angle = math.asin(
        vehicle.vehicle_base_m / (2.0 * radius)
    )

    def circle_frame(chainage_m: float) -> TrackFrame:
        angle = (chainage_m - centre_chainage) / radius
        return TrackFrame(
            chainage_m=chainage_m,
            position=(
                radius * math.cos(angle),
                radius * math.sin(angle),
                0.0,
            ),
            tangent=(-math.sin(angle), math.cos(angle), 0.0),
            up=(0.0, 0.0, 1.0),
        )

    leading_chainage = centre_chainage + radius * half_bogie_angle
    expected_trailing = centre_chainage - radius * half_bogie_angle
    pose = rail_vehicle_pose_from_leading_bogie(
        circle_frame,
        leading_chainage_m=leading_chainage,
        geometry=vehicle,
    )
    throw = screening_circular_curve_throw(radius, vehicle)

    assert math.isclose(
        pose.trailing_bogie.chainage_m,
        expected_trailing,
        abs_tol=2e-8,
    )
    body_radius = math.hypot(
        pose.carbody.position[0],
        pose.carbody.position[1],
    )
    runtime_centre_throw = radius - body_radius
    assert math.isclose(
        runtime_centre_throw,
        throw.centre_throw_exact_m,
        abs_tol=2e-9,
    )

    endpoint_radius = max(
        math.hypot(
            pose.carbody_front_proxy[0],
            pose.carbody_front_proxy[1],
        ),
        math.hypot(
            pose.carbody_rear_proxy[0],
            pose.carbody_rear_proxy[1],
        ),
    )
    runtime_end_throw = endpoint_radius - radius
    assert math.isclose(
        runtime_end_throw,
        throw.end_throw_exact_m,
        abs_tol=2e-9,
    )

    # Each bogie follows its own local tangent while the rigid body follows the
    # chord between bogie pivots.
    assert pose.leading_bogie.frame.forward != pose.carbody.forward
    assert pose.trailing_bogie.frame.forward != pose.carbody.forward


def test_small_angle_throw_screening_is_close_for_metro_curve():
    throw = screening_circular_curve_throw(300.0)
    assert throw.total_length_is_coupler_proxy is True
    assert math.isclose(
        throw.centre_throw_small_angle_m,
        throw.centre_throw_exact_m,
        rel_tol=2e-4,
    )
    assert math.isclose(
        throw.end_throw_small_angle_m,
        throw.end_throw_exact_m,
        rel_tol=2e-4,
    )


def test_allowance_budget_refuses_to_imply_unknown_dynamics_are_zero():
    budget = EnvelopeAllowanceBudget()
    assert budget.safety_complete is False
    assert math.isclose(budget.known_lateral_allowance_m(), 0.016)
    assert budget.known_vertical_allowance_m() == 0.0
    assert (
        "gost_q_bogie_frame_relative_wheelset_m"
        in budget.missing_safety_terms
    )
    assert (
        "gost_w_carbody_relative_bogie_m"
        in budget.missing_safety_terms
    )
    assert "vehicle_roll_bound_rad" in budget.missing_safety_terms


def test_gost_q_w_allowances_are_explicit_and_do_not_erase_source_gap():
    budget = EnvelopeAllowanceBudget(
        gost_q_bogie_frame_relative_wheelset_m=0.004,
        gost_w_carbody_relative_bogie_m=0.010,
        additional_vehicle_lateral_dynamic_m=0.006,
        vehicle_vertical_dynamic_m=0.008,
        vehicle_roll_bound_rad=0.01,
        track_lateral_tolerance_m=0.003,
        track_vertical_tolerance_m=0.004,
    )
    # The sourced 16 mm stop clearance remains the larger known body/bogie
    # term until a target-vehicle w >= 16 mm is documented.
    assert math.isclose(budget.known_body_bogie_lateral_m(), 0.016)
    assert math.isclose(
        budget.known_lateral_allowance_m(),
        0.016 + 0.004 + 0.006 + 0.003,
    )
    assert math.isclose(
        budget.known_vertical_allowance_m(),
        0.008 + 0.004,
    )
    assert math.isclose(budget.known_roll_bound_rad(), 0.01)
    assert budget.safety_complete is True


def test_turnout_without_resolved_route_uses_union_and_tags_ambiguity():
    ambiguous = classify_route_hypothesis_intersections(
        {
            "straight": False,
            "diverging": True,
        }
    )
    assert ambiguous.relevance is ObstacleRouteRelevance.ROUTE_AMBIGUOUS
    assert ambiguous.intersecting_route_ids == ("diverging",)

    all_routes = classify_route_hypothesis_intersections(
        {
            "straight": True,
            "diverging": True,
        }
    )
    assert (
        all_routes.relevance
        is ObstacleRouteRelevance.ALL_FEASIBLE_ROUTES
    )

    resolved = classify_route_hypothesis_intersections(
        {
            "straight": False,
            "diverging": True,
        },
        active_route_id="straight",
    )
    assert resolved.relevance is ObstacleRouteRelevance.OUTSIDE
