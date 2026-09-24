from __future__ import annotations

"""Rail-vehicle kinematics and swept-envelope reference geometry.

This module is intentionally engine-neutral. It provides deterministic
reference mathematics for a later UNIGINE runtime implementation and keeps
vehicle-path kinematics separate from render meshes and obstacle queries.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Callable, Mapping

from .mesh import Vec3


_EPS = 1e-12


def _add(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a: Vec3, b: Vec3) -> Vec3:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a: Vec3, scalar: float) -> Vec3:
    return (a[0] * scalar, a[1] * scalar, a[2] * scalar)


def _dot(a: Vec3, b: Vec3) -> float:
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _cross(a: Vec3, b: Vec3) -> Vec3:
    return (
        a[1] * b[2] - a[2] * b[1],
        a[2] * b[0] - a[0] * b[2],
        a[0] * b[1] - a[1] * b[0],
    )


def _length(a: Vec3) -> float:
    return math.sqrt(_dot(a, a))


def _normalize(a: Vec3, *, name: str) -> Vec3:
    norm = _length(a)
    if not math.isfinite(norm) or norm <= _EPS:
        raise ValueError(f"{name} must have non-zero finite length")
    return (a[0] / norm, a[1] / norm, a[2] / norm)


def _distance(a: Vec3, b: Vec3) -> float:
    return _length(_sub(a, b))


@dataclass(frozen=True)
class TrackFrame:
    """Track-centre frame at one chainage.

    position is the reference track centreline. tangent follows the selected
    travel direction. up is the local track-plane up vector and may include
    cant when a future engineering alignment supplies it.
    """

    chainage_m: float
    position: Vec3
    tangent: Vec3
    up: Vec3 = (0.0, 0.0, 1.0)

    def orthonormalized(self) -> "TrackFrame":
        tangent = _normalize(self.tangent, name="track tangent")
        up_seed = _normalize(self.up, name="track up")
        right = _normalize(_cross(tangent, up_seed), name="track right")
        up = _normalize(_cross(right, tangent), name="orthogonal track up")
        return TrackFrame(
            chainage_m=float(self.chainage_m),
            position=tuple(float(v) for v in self.position),
            tangent=tangent,
            up=up,
        )


TrackFrameAt = Callable[[float], TrackFrame]


@dataclass(frozen=True)
class RigidFrame:
    position: Vec3
    forward: Vec3
    right: Vec3
    up: Vec3

    def matrix4x4_row_major(self) -> tuple[float, ...]:
        """Return local X=right, Y=forward, Z=up transform."""
        return (
            self.right[0], self.forward[0], self.up[0], self.position[0],
            self.right[1], self.forward[1], self.up[1], self.position[1],
            self.right[2], self.forward[2], self.up[2], self.position[2],
            0.0, 0.0, 0.0, 1.0,
        )


@dataclass(frozen=True)
class RailVehicleGeometry:
    model_id: str
    length_over_couplers_m: float
    maximum_width_m: float
    empty_height_above_top_of_rail_m: float
    vehicle_base_m: float
    bogie_count: int = 2
    axles_per_bogie: int = 2
    bogie_wheelbase_m: float | None = None
    exact_carbody_length_m: float | None = None
    exact_bogie_pivot_to_end_m: float | None = None
    documented_lateral_stop_clearance_nominal_m: float = 0.015
    documented_lateral_stop_clearance_tolerance_m: float = 0.001

    def __post_init__(self) -> None:
        for name in (
            "length_over_couplers_m",
            "maximum_width_m",
            "empty_height_above_top_of_rail_m",
            "vehicle_base_m",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.vehicle_base_m >= self.length_over_couplers_m:
            raise ValueError("vehicle base must be shorter than total vehicle")
        if self.bogie_count != 2:
            raise ValueError("current rigid-chord reference model requires 2 bogies")
        if self.axles_per_bogie != 2:
            raise ValueError("current reference vehicle is four-axle")

    @property
    def half_width_m(self) -> float:
        return 0.5 * self.maximum_width_m

    @property
    def symmetric_overhang_proxy_m(self) -> float:
        """Screening proxy only: coupler-head length minus vehicle base / 2."""
        return 0.5 * (
            self.length_over_couplers_m - self.vehicle_base_m
        )

    @property
    def documented_lateral_stop_clearance_upper_m(self) -> float:
        return (
            self.documented_lateral_stop_clearance_nominal_m
            + self.documented_lateral_stop_clearance_tolerance_m
        )


MOSKVA_2020_81_775 = RailVehicleGeometry(
    model_id="81-775",
    length_over_couplers_m=20.080,
    maximum_width_m=2.740,
    empty_height_above_top_of_rail_m=3.680,
    vehicle_base_m=12.600,
)


@dataclass(frozen=True)
class BogiePose:
    chainage_m: float
    frame: RigidFrame


@dataclass(frozen=True)
class RailVehiclePose:
    """Nominal rigid-body pose derived from two rail-following bogie pivots."""

    leading_bogie: BogiePose
    trailing_bogie: BogiePose
    carbody: RigidFrame
    bogie_pivot_distance_m: float
    carbody_front_proxy: Vec3
    carbody_rear_proxy: Vec3

    @property
    def bogie_chainage_span_m(self) -> float:
        return self.leading_bogie.chainage_m - self.trailing_bogie.chainage_m


def _rigid_frame_from_track(track: TrackFrame) -> RigidFrame:
    frame = track.orthonormalized()
    right = _normalize(
        _cross(frame.tangent, frame.up),
        name="bogie right",
    )
    up = _normalize(_cross(right, frame.tangent), name="bogie up")
    return RigidFrame(
        position=frame.position,
        forward=frame.tangent,
        right=right,
        up=up,
    )


def solve_trailing_bogie_chainage(
    frame_at: TrackFrameAt,
    *,
    leading_chainage_m: float,
    bogie_pivot_distance_m: float,
    minimum_chainage_m: float = 0.0,
    tolerance_m: float = 1e-9,
    maximum_iterations: int = 96,
) -> float:
    """Solve the trailing pivot so the 3D chord equals the vehicle base.

    Subtracting the vehicle base from chainage is wrong on curves because arc
    length is longer than the straight distance between the two body pivots.
    """

    if bogie_pivot_distance_m <= 0.0:
        raise ValueError("bogie pivot distance must be positive")
    if leading_chainage_m <= minimum_chainage_m:
        raise ValueError("leading bogie must lie after minimum chainage")
    if tolerance_m <= 0.0:
        raise ValueError("tolerance must be positive")

    leading = frame_at(leading_chainage_m).orthonormalized().position

    def residual(chainage_m: float) -> float:
        point = frame_at(chainage_m).orthonormalized().position
        return _distance(leading, point) - bogie_pivot_distance_m

    hi = float(leading_chainage_m)
    max_delta = hi - float(minimum_chainage_m)
    delta = min(
        max_delta,
        max(bogie_pivot_distance_m * 1.02, 0.25),
    )
    lo = hi - delta
    lo_residual = residual(lo)

    while lo_residual < 0.0 and lo > minimum_chainage_m + _EPS:
        delta = min(max_delta, max(delta * 1.5, delta + 0.25))
        lo = hi - delta
        lo_residual = residual(lo)
        if delta >= max_delta - _EPS:
            break

    if lo_residual < 0.0:
        raise ValueError(
            "insufficient preceding path to place trailing bogie at the "
            "requested rigid pivot distance"
        )

    for _ in range(maximum_iterations):
        mid = 0.5 * (lo + hi)
        value = residual(mid)
        if abs(value) <= tolerance_m or hi - lo <= tolerance_m:
            return mid
        if value >= 0.0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def rail_vehicle_pose_from_leading_bogie(
    frame_at: TrackFrameAt,
    *,
    leading_chainage_m: float,
    geometry: RailVehicleGeometry = MOSKVA_2020_81_775,
    minimum_chainage_m: float = 0.0,
) -> RailVehiclePose:
    """Evaluate nominal two-bogie/chord carbody kinematics on a 3D path."""

    trailing_chainage = solve_trailing_bogie_chainage(
        frame_at,
        leading_chainage_m=leading_chainage_m,
        bogie_pivot_distance_m=geometry.vehicle_base_m,
        minimum_chainage_m=minimum_chainage_m,
    )
    leading_track = frame_at(leading_chainage_m).orthonormalized()
    trailing_track = frame_at(trailing_chainage).orthonormalized()
    leading_pose = BogiePose(
        chainage_m=float(leading_chainage_m),
        frame=_rigid_frame_from_track(leading_track),
    )
    trailing_pose = BogiePose(
        chainage_m=float(trailing_chainage),
        frame=_rigid_frame_from_track(trailing_track),
    )

    chord = _sub(leading_track.position, trailing_track.position)
    forward = _normalize(chord, name="carbody bogie-centre chord")
    midpoint = _mul(
        _add(leading_track.position, trailing_track.position),
        0.5,
    )

    up_seed = _add(leading_track.up, trailing_track.up)
    if _length(up_seed) <= _EPS:
        up_seed = leading_track.up
    up_seed = _normalize(up_seed, name="mean bogie up")
    right = _normalize(_cross(forward, up_seed), name="carbody right")
    up = _normalize(_cross(right, forward), name="carbody up")
    carbody = RigidFrame(
        position=midpoint,
        forward=forward,
        right=right,
        up=up,
    )

    half_proxy_length = 0.5 * geometry.length_over_couplers_m
    front_proxy = _add(midpoint, _mul(forward, half_proxy_length))
    rear_proxy = _add(midpoint, _mul(forward, -half_proxy_length))
    return RailVehiclePose(
        leading_bogie=leading_pose,
        trailing_bogie=trailing_pose,
        carbody=carbody,
        bogie_pivot_distance_m=_distance(
            leading_track.position,
            trailing_track.position,
        ),
        carbody_front_proxy=front_proxy,
        carbody_rear_proxy=rear_proxy,
    )


@dataclass(frozen=True)
class CurveThrowEstimate:
    radius_m: float
    centre_throw_exact_m: float
    end_throw_exact_m: float
    centre_throw_small_angle_m: float
    end_throw_small_angle_m: float
    total_length_is_coupler_proxy: bool


def screening_circular_curve_throw(
    radius_m: float,
    geometry: RailVehicleGeometry = MOSKVA_2020_81_775,
) -> CurveThrowEstimate:
    """Circular-curve sanity check, not a complete normative gauge calculation.

    The target source does not provide target-bogie wheelbase or a full
    carbody contour. length_over_couplers_m is therefore used only as a
    conservative longitudinal proxy for the outer endpoint in this screening
    calculation. Runtime motion should use the two-bogie pose solver above.
    """

    radius = float(radius_m)
    base = geometry.vehicle_base_m
    total = geometry.length_over_couplers_m
    if not math.isfinite(radius) or radius <= 0.5 * base:
        raise ValueError("curve radius is too small for vehicle-base geometry")

    centre_exact = radius - math.sqrt(radius * radius - 0.25 * base * base)
    end_exact = (
        math.sqrt(
            radius * radius
            + 0.25 * (total * total - base * base)
        )
        - radius
    )
    return CurveThrowEstimate(
        radius_m=radius,
        centre_throw_exact_m=centre_exact,
        end_throw_exact_m=end_exact,
        centre_throw_small_angle_m=(base * base) / (8.0 * radius),
        end_throw_small_angle_m=(
            (total * total - base * base) / (8.0 * radius)
        ),
        total_length_is_coupler_proxy=True,
    )


@dataclass(frozen=True)
class EnvelopeAllowanceBudget:
    """Vehicle/track allowance ledger using ГОСТ 23961 terminology.

    The user-supplied 81-775 material documents only a 15 +/- 1 mm free
    clearance between the central lateral stop and each side stop. That value
    is retained as evidence, but the complete ГОСТ quantities q and w are not
    available for the target vehicle and therefore default to None.

    q: bogie-frame lateral motion relative to the wheelset in a guiding section.
    w: carbody lateral motion relative to the bogie frame in a guiding section.
    """

    documented_body_bogie_lateral_free_m: float = 0.016
    gost_q_bogie_frame_relative_wheelset_m: float | None = None
    gost_w_carbody_relative_bogie_m: float | None = None
    additional_vehicle_lateral_dynamic_m: float | None = None
    vehicle_vertical_dynamic_m: float | None = None
    vehicle_roll_bound_rad: float | None = None
    track_lateral_tolerance_m: float | None = None
    track_vertical_tolerance_m: float | None = None

    def __post_init__(self) -> None:
        scalar_names = (
            "documented_body_bogie_lateral_free_m",
            "gost_q_bogie_frame_relative_wheelset_m",
            "gost_w_carbody_relative_bogie_m",
            "additional_vehicle_lateral_dynamic_m",
            "vehicle_vertical_dynamic_m",
            "track_lateral_tolerance_m",
            "track_vertical_tolerance_m",
        )
        for name in scalar_names:
            value = getattr(self, name)
            if value is None:
                continue
            if not math.isfinite(float(value)) or float(value) < 0.0:
                raise ValueError(f"{name} must be finite and non-negative")
        if self.vehicle_roll_bound_rad is not None:
            value = float(self.vehicle_roll_bound_rad)
            if not math.isfinite(value) or not (0.0 <= value < 0.5 * math.pi):
                raise ValueError(
                    "vehicle_roll_bound_rad must be in [0, pi/2)"
                )

    @property
    def missing_safety_terms(self) -> tuple[str, ...]:
        names = (
            "gost_q_bogie_frame_relative_wheelset_m",
            "gost_w_carbody_relative_bogie_m",
            "additional_vehicle_lateral_dynamic_m",
            "vehicle_vertical_dynamic_m",
            "vehicle_roll_bound_rad",
            "track_lateral_tolerance_m",
            "track_vertical_tolerance_m",
        )
        return tuple(name for name in names if getattr(self, name) is None)

    @property
    def safety_complete(self) -> bool:
        return not self.missing_safety_terms

    def known_body_bogie_lateral_m(self) -> float:
        """Use sourced w when available; otherwise retain the documented free gap."""
        if self.gost_w_carbody_relative_bogie_m is not None:
            return max(
                self.documented_body_bogie_lateral_free_m,
                float(self.gost_w_carbody_relative_bogie_m),
            )
        return self.documented_body_bogie_lateral_free_m

    def known_lateral_allowance_m(self) -> float:
        values = (
            self.known_body_bogie_lateral_m(),
            self.gost_q_bogie_frame_relative_wheelset_m,
            self.additional_vehicle_lateral_dynamic_m,
            self.track_lateral_tolerance_m,
        )
        return sum(float(value) for value in values if value is not None)

    def known_vertical_allowance_m(self) -> float:
        values = (
            self.vehicle_vertical_dynamic_m,
            self.track_vertical_tolerance_m,
        )
        return sum(float(value) for value in values if value is not None)

    def known_roll_bound_rad(self) -> float:
        return (
            0.0
            if self.vehicle_roll_bound_rad is None
            else float(self.vehicle_roll_bound_rad)
        )


class ObstacleRouteRelevance(str, Enum):
    OUTSIDE = "outside"
    ACTIVE_ROUTE = "active_route"
    ALL_FEASIBLE_ROUTES = "all_feasible_routes"
    ROUTE_AMBIGUOUS = "route_ambiguous"


@dataclass(frozen=True)
class RouteObstacleClassification:
    relevance: ObstacleRouteRelevance
    feasible_route_ids: tuple[str, ...]
    intersecting_route_ids: tuple[str, ...]


def classify_route_hypothesis_intersections(
    intersections_by_route: Mapping[str, bool],
    *,
    active_route_id: str | None = None,
) -> RouteObstacleClassification:
    """Classify an obstacle against a set of still-feasible turnout routes.

    With no resolved switch/route state, the safety-facing obstacle volume is
    the union of all feasible route envelopes. Obstacles intersecting only a
    subset are explicitly tagged route-ambiguous rather than silently dropped.
    """

    if not intersections_by_route:
        raise ValueError("at least one feasible route hypothesis is required")
    feasible = tuple(sorted(str(route) for route in intersections_by_route))
    hit = tuple(
        route
        for route in feasible
        if bool(intersections_by_route[route])
    )

    if active_route_id is not None:
        active = str(active_route_id)
        if active not in intersections_by_route:
            raise ValueError("active route is not in feasible route hypotheses")
        return RouteObstacleClassification(
            relevance=(
                ObstacleRouteRelevance.ACTIVE_ROUTE
                if intersections_by_route[active]
                else ObstacleRouteRelevance.OUTSIDE
            ),
            feasible_route_ids=feasible,
            intersecting_route_ids=hit,
        )

    if not hit:
        relevance = ObstacleRouteRelevance.OUTSIDE
    elif len(hit) == len(feasible):
        relevance = ObstacleRouteRelevance.ALL_FEASIBLE_ROUTES
    else:
        relevance = ObstacleRouteRelevance.ROUTE_AMBIGUOUS
    return RouteObstacleClassification(
        relevance=relevance,
        feasible_route_ids=feasible,
        intersecting_route_ids=hit,
    )
