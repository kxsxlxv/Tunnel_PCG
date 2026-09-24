from __future__ import annotations

import math

from tunnel_scanner_core.rail_obstacle import (
    RouteHypothesis,
    SweptEnvelopeSamplingConfig,
    build_multi_route_swept_envelope,
    build_route_swept_envelope,
    carbody_obb_from_pose,
)
from tunnel_scanner_core.rail_vehicle import (
    EnvelopeAllowanceBudget,
    MOSKVA_2020_81_775,
    ObstacleRouteRelevance,
    TrackFrame,
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


def _diverging_frame(chainage_m: float) -> TrackFrame:
    if chainage_m <= 20.0:
        return _straight_frame(chainage_m)

    radius = 50.0
    arc_s = chainage_m - 20.0
    angle = arc_s / radius
    return TrackFrame(
        chainage_m=chainage_m,
        position=(
            radius * (1.0 - math.cos(angle)),
            20.0 + radius * math.sin(angle),
            0.0,
        ),
        tangent=(
            math.sin(angle),
            math.cos(angle),
            0.0,
        ),
        up=(0.0, 0.0, 1.0),
    )


def test_carbody_obb_uses_documented_width_height_and_known_allowance():
    pose = rail_vehicle_pose_from_leading_bogie(
        _straight_frame,
        leading_chainage_m=30.0,
    )
    box = carbody_obb_from_pose(pose)

    assert math.isclose(box.half_length_m, 20.080 / 2.0)
    assert math.isclose(
        box.half_width_m,
        2.740 / 2.0 + 0.016,
    )
    assert math.isclose(box.half_height_m, 3.680 / 2.0)
    assert math.isclose(box.center[2], 3.680 / 2.0)

    assert box.contains_point((0.0, pose.carbody.position[1], 1.0))
    assert not box.contains_point(
        (box.half_width_m + 0.02, pose.carbody.position[1], 1.0)
    )
    # Current source-backed proxy is explicitly above top of rail only.
    assert not box.contains_point((0.0, pose.carbody.position[1], -0.01))


def test_sampled_curve_envelope_tracks_rigid_chord_centre_throw():
    vehicle = MOSKVA_2020_81_775
    radius = 300.0
    centre_chainage = 1000.0
    half_angle = math.asin(vehicle.vehicle_base_m / (2.0 * radius))

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

    leading_chainage = centre_chainage + radius * half_angle
    envelope = build_route_swept_envelope(
        RouteHypothesis(
            route_id="curve",
            frame_at=circle_frame,
            leading_chainage_m=leading_chainage,
        ),
        lookahead_m=0.0,
    )
    box = envelope.boxes[0]
    throw = screening_circular_curve_throw(radius, vehicle)

    body_axis_radius = math.hypot(box.center[0], box.center[1])
    assert math.isclose(
        radius - body_axis_radius,
        throw.centre_throw_exact_m,
        abs_tol=2e-9,
    )


def test_adaptive_envelope_refines_curved_route_more_than_straight():
    sampling = SweptEnvelopeSamplingConfig(
        max_chainage_step_m=10.0,
        max_pose_deviation_m=0.005,
    )
    straight = build_route_swept_envelope(
        RouteHypothesis(
            route_id="straight",
            frame_at=_straight_frame,
            leading_chainage_m=25.0,
        ),
        lookahead_m=20.0,
        sampling=sampling,
    )
    diverging = build_route_swept_envelope(
        RouteHypothesis(
            route_id="diverging",
            frame_at=_diverging_frame,
            leading_chainage_m=25.0,
        ),
        lookahead_m=20.0,
        sampling=sampling,
    )

    assert len(straight.boxes) == 3
    assert len(diverging.boxes) > len(straight.boxes)


def test_unresolved_turnout_uses_union_and_preserves_route_ambiguity():
    sampling = SweptEnvelopeSamplingConfig(
        max_chainage_step_m=1.0,
        max_pose_deviation_m=0.005,
    )
    envelope = build_multi_route_swept_envelope(
        (
            RouteHypothesis(
                route_id="straight",
                frame_at=_straight_frame,
                leading_chainage_m=25.0,
                maximum_leading_chainage_m=45.0,
            ),
            RouteHypothesis(
                route_id="diverging",
                frame_at=_diverging_frame,
                leading_chainage_m=25.0,
                maximum_leading_chainage_m=45.0,
            ),
        ),
        lookahead_m=20.0,
        sampling=sampling,
    )

    # This point is outside the straight 81-775 width but lies inside the
    # diverging branch's future chord-swept body proxy.
    obstacle = (2.5, 35.0, 1.5)
    classification = envelope.classify_point(obstacle)
    assert (
        classification.relevance
        is ObstacleRouteRelevance.ROUTE_AMBIGUOUS
    )
    assert classification.intersecting_route_ids == ("diverging",)

    resolved_straight = envelope.classify_point(
        obstacle,
        active_route_id="straight",
    )
    assert resolved_straight.relevance is ObstacleRouteRelevance.OUTSIDE

    resolved_diverging = envelope.classify_point(
        obstacle,
        active_route_id="diverging",
    )
    assert (
        resolved_diverging.relevance
        is ObstacleRouteRelevance.ACTIVE_ROUTE
    )


def test_envelope_reports_incomplete_safety_allowance_budget():
    envelope = build_route_swept_envelope(
        RouteHypothesis(
            route_id="straight",
            frame_at=_straight_frame,
            leading_chainage_m=25.0,
        ),
        lookahead_m=5.0,
    )
    assert envelope.safety_complete is False
    assert (
        "additional_vehicle_lateral_dynamic_m"
        in envelope.allowance.missing_safety_terms
    )

    complete = EnvelopeAllowanceBudget(
        documented_body_bogie_lateral_free_m=0.016,
        additional_vehicle_lateral_dynamic_m=0.010,
        vehicle_vertical_dynamic_m=0.010,
        wheel_bogie_lateral_play_m=0.005,
        track_lateral_tolerance_m=0.005,
        track_vertical_tolerance_m=0.005,
        path_estimation_lateral_m=0.010,
        path_estimation_vertical_m=0.010,
    )
    completed = build_route_swept_envelope(
        RouteHypothesis(
            route_id="straight",
            frame_at=_straight_frame,
            leading_chainage_m=25.0,
        ),
        lookahead_m=5.0,
        allowance=complete,
    )
    assert completed.safety_complete is True
