from __future__ import annotations

"""Route-dependent rail-vehicle obstacle relevance envelopes.

The implementation is deliberately engine-neutral. It provides a deterministic
reference for LiDAR point classification and for the later UNIGINE broad/narrow
phase implementation.

The current 81-775 volume is a conservative ABOVE-TOR rectangular screening
proxy based only on source-backed overall width/height and coupler-head length.
It is not a certified rolling-stock kinematic gauge.
"""

from dataclasses import dataclass
import math
from typing import Mapping, Sequence

from .mesh import Vec3
from .rail_vehicle import (
    EnvelopeAllowanceBudget,
    MOSKVA_2020_81_775,
    ObstacleRouteRelevance,
    RailVehicleGeometry,
    RailVehiclePose,
    RouteObstacleClassification,
    TrackFrameAt,
    _add,
    _dot,
    _length,
    _mul,
    _normalize,
    _sub,
    classify_route_hypothesis_intersections,
    rail_vehicle_pose_from_leading_bogie,
)


_EPS = 1e-12


@dataclass(frozen=True)
class AABB3:
    minimum: Vec3
    maximum: Vec3

    def __post_init__(self) -> None:
        if any(
            not math.isfinite(value)
            for value in (*self.minimum, *self.maximum)
        ):
            raise ValueError("AABB coordinates must be finite")
        if any(
            self.minimum[index] > self.maximum[index]
            for index in range(3)
        ):
            raise ValueError("AABB minimum must not exceed maximum")

    def contains_point(self, point: Vec3, *, epsilon_m: float = 0.0) -> bool:
        return all(
            self.minimum[index] - epsilon_m
            <= point[index]
            <= self.maximum[index] + epsilon_m
            for index in range(3)
        )

    @staticmethod
    def union(boxes: Sequence["AABB3"]) -> "AABB3":
        boxes = tuple(boxes)
        if not boxes:
            raise ValueError("cannot union an empty AABB sequence")
        return AABB3(
            minimum=tuple(
                min(box.minimum[index] for box in boxes)
                for index in range(3)
            ),
            maximum=tuple(
                max(box.maximum[index] for box in boxes)
                for index in range(3)
            ),
        )


@dataclass(frozen=True)
class OrientedBox3:
    """World-space OBB using local X=right, Y=forward, Z=up."""

    center: Vec3
    right: Vec3
    forward: Vec3
    up: Vec3
    half_width_m: float
    half_length_m: float
    half_height_m: float
    source_chainage_m: float
    numerical_inflation_m: float = 0.0

    def __post_init__(self) -> None:
        for name in (
            "half_width_m",
            "half_length_m",
            "half_height_m",
        ):
            value = float(getattr(self, name))
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if self.numerical_inflation_m < 0.0:
            raise ValueError("numerical inflation must be non-negative")

    @property
    def half_extents_m(self) -> tuple[float, float, float]:
        inflation = self.numerical_inflation_m
        return (
            self.half_width_m + inflation,
            self.half_length_m + inflation,
            self.half_height_m + inflation,
        )

    def contains_point(self, point: Vec3, *, epsilon_m: float = 0.0) -> bool:
        delta = _sub(point, self.center)
        axes = (
            _normalize(self.right, name="OBB right"),
            _normalize(self.forward, name="OBB forward"),
            _normalize(self.up, name="OBB up"),
        )
        for coordinate, extent in zip(
            (_dot(delta, axis) for axis in axes),
            self.half_extents_m,
        ):
            if abs(coordinate) > extent + epsilon_m:
                return False
        return True

    def corners(self) -> tuple[Vec3, ...]:
        right = _normalize(self.right, name="OBB right")
        forward = _normalize(self.forward, name="OBB forward")
        up = _normalize(self.up, name="OBB up")
        half_width, half_length, half_height = self.half_extents_m
        result = []
        for sx in (-1.0, 1.0):
            for sy in (-1.0, 1.0):
                for sz in (-1.0, 1.0):
                    point = self.center
                    point = _add(point, _mul(right, sx * half_width))
                    point = _add(point, _mul(forward, sy * half_length))
                    point = _add(point, _mul(up, sz * half_height))
                    result.append(point)
        return tuple(result)

    def world_aabb(self) -> AABB3:
        corners = self.corners()
        return AABB3(
            minimum=tuple(
                min(point[index] for point in corners)
                for index in range(3)
            ),
            maximum=tuple(
                max(point[index] for point in corners)
                for index in range(3)
            ),
        )


@dataclass(frozen=True)
class CarbodyScreeningProxy:
    """Source-bounded first approximation of the above-TOR vehicle volume."""

    half_length_m: float
    half_width_m: float
    bottom_above_tor_m: float
    top_above_tor_m: float
    length_is_coupler_proxy: bool = True
    profile_is_rectangular_proxy: bool = True

    def __post_init__(self) -> None:
        if self.half_length_m <= 0.0 or self.half_width_m <= 0.0:
            raise ValueError("carbody proxy length/width must be positive")
        if self.top_above_tor_m <= self.bottom_above_tor_m:
            raise ValueError("carbody proxy top must be above bottom")


def carbody_screening_proxy(
    geometry: RailVehicleGeometry = MOSKVA_2020_81_775,
) -> CarbodyScreeningProxy:
    """Build the only rectangular proxy supported by current 81-775 data.

    The source gives overall width, height above top of rail and length over
    coupler heads, but not a detailed body/underframe profile. The lower plane
    is therefore explicitly Top Of Rail, not an invented underframe height.
    """

    return CarbodyScreeningProxy(
        half_length_m=0.5 * geometry.length_over_couplers_m,
        half_width_m=0.5 * geometry.maximum_width_m,
        bottom_above_tor_m=0.0,
        top_above_tor_m=geometry.empty_height_above_top_of_rail_m,
    )


def carbody_obb_from_pose(
    pose: RailVehiclePose,
    *,
    geometry: RailVehicleGeometry = MOSKVA_2020_81_775,
    allowance: EnvelopeAllowanceBudget | None = None,
    numerical_inflation_m: float = 0.0,
) -> OrientedBox3:
    """Create the current above-TOR rectangular obstacle screening proxy."""

    allowance = allowance or EnvelopeAllowanceBudget()
    proxy = carbody_screening_proxy(geometry)
    lateral = allowance.known_lateral_allowance_m()
    vertical = allowance.known_vertical_allowance_m()
    height = proxy.top_above_tor_m - proxy.bottom_above_tor_m
    center_z = proxy.bottom_above_tor_m + 0.5 * height
    center = _add(
        pose.carbody.position,
        _mul(pose.carbody.up, center_z),
    )
    return OrientedBox3(
        center=center,
        right=pose.carbody.right,
        forward=pose.carbody.forward,
        up=pose.carbody.up,
        half_width_m=proxy.half_width_m + lateral,
        half_length_m=proxy.half_length_m,
        half_height_m=0.5 * height + vertical,
        source_chainage_m=pose.leading_bogie.chainage_m,
        numerical_inflation_m=float(numerical_inflation_m),
    )


@dataclass(frozen=True)
class SweptEnvelopeSamplingConfig:
    """Numerical resolution only; these are not railway safety allowances."""

    max_chainage_step_m: float = 1.0
    max_pose_deviation_m: float = 0.005
    maximum_refinement_depth: int = 14

    def __post_init__(self) -> None:
        if self.max_chainage_step_m <= 0.0:
            raise ValueError("max_chainage_step_m must be positive")
        if self.max_pose_deviation_m <= 0.0:
            raise ValueError("max_pose_deviation_m must be positive")
        if self.maximum_refinement_depth < 1:
            raise ValueError("maximum_refinement_depth must be >= 1")


@dataclass(frozen=True)
class RouteHypothesis:
    route_id: str
    frame_at: TrackFrameAt
    leading_chainage_m: float
    maximum_leading_chainage_m: float | None = None

    def __post_init__(self) -> None:
        if not self.route_id:
            raise ValueError("route_id must be non-empty")
        if self.leading_chainage_m < 0.0:
            raise ValueError("leading_chainage_m must be non-negative")
        if (
            self.maximum_leading_chainage_m is not None
            and self.maximum_leading_chainage_m < self.leading_chainage_m
        ):
            raise ValueError("route maximum must not precede leading chainage")


@dataclass(frozen=True)
class RouteSweptEnvelope:
    route_id: str
    boxes: tuple[OrientedBox3, ...]
    allowance: EnvelopeAllowanceBudget
    sampling: SweptEnvelopeSamplingConfig
    source_start_chainage_m: float
    source_end_chainage_m: float
    vehicle_geometry: RailVehicleGeometry
    representation: str = "sampled_inflated_obb_union_v1"

    def __post_init__(self) -> None:
        if not self.boxes:
            raise ValueError("route swept envelope requires at least one box")

    @property
    def safety_complete(self) -> bool:
        return self.allowance.safety_complete

    @property
    def broad_phase_aabb(self) -> AABB3:
        return AABB3.union(tuple(box.world_aabb() for box in self.boxes))

    def contains_point(self, point: Vec3) -> bool:
        if not self.broad_phase_aabb.contains_point(point):
            return False
        return any(box.contains_point(point) for box in self.boxes)


@dataclass(frozen=True)
class MultiRouteSweptEnvelope:
    routes: tuple[RouteSweptEnvelope, ...]

    def __post_init__(self) -> None:
        if not self.routes:
            raise ValueError("at least one route envelope is required")
        ids = tuple(route.route_id for route in self.routes)
        if len(set(ids)) != len(ids):
            raise ValueError("route envelope IDs must be unique")

    @property
    def safety_complete(self) -> bool:
        return all(route.safety_complete for route in self.routes)

    @property
    def feasible_route_ids(self) -> tuple[str, ...]:
        return tuple(sorted(route.route_id for route in self.routes))

    @property
    def broad_phase_aabb(self) -> AABB3:
        return AABB3.union(tuple(route.broad_phase_aabb for route in self.routes))

    def classify_point(
        self,
        point: Vec3,
        *,
        active_route_id: str | None = None,
    ) -> RouteObstacleClassification:
        intersections = {
            route.route_id: route.contains_point(point)
            for route in self.routes
        }
        return classify_route_hypothesis_intersections(
            intersections,
            active_route_id=active_route_id,
        )

    def classify_points(
        self,
        points: Sequence[Vec3],
        *,
        active_route_id: str | None = None,
    ) -> tuple[RouteObstacleClassification, ...]:
        return tuple(
            self.classify_point(point, active_route_id=active_route_id)
            for point in points
        )


def _angle_between(a: Vec3, b: Vec3) -> float:
    aa = _normalize(a, name="angle vector a")
    bb = _normalize(b, name="angle vector b")
    return math.acos(max(-1.0, min(1.0, _dot(aa, bb))))


def _pose_refinement_error_m(
    left: RailVehiclePose,
    middle: RailVehiclePose,
    right: RailVehiclePose,
    *,
    geometry: RailVehicleGeometry,
) -> float:
    """Estimate midpoint rigid-body deviation from endpoint interpolation."""

    expected_center = _mul(
        _add(left.carbody.position, right.carbody.position),
        0.5,
    )
    center_error = _length(_sub(middle.carbody.position, expected_center))

    expected_forward = _add(left.carbody.forward, right.carbody.forward)
    if _length(expected_forward) <= _EPS:
        expected_forward = left.carbody.forward
    angular_error = _angle_between(
        middle.carbody.forward,
        expected_forward,
    )
    half_diagonal = math.sqrt(
        (0.5 * geometry.length_over_couplers_m) ** 2
        + (0.5 * geometry.maximum_width_m) ** 2
        + (0.5 * geometry.empty_height_above_top_of_rail_m) ** 2
    )
    rotational_error = 2.0 * half_diagonal * math.sin(
        0.5 * angular_error
    )
    return center_error + rotational_error


def _adaptive_pose_samples(
    hypothesis: RouteHypothesis,
    *,
    end_chainage_m: float,
    geometry: RailVehicleGeometry,
    sampling: SweptEnvelopeSamplingConfig,
) -> tuple[RailVehiclePose, ...]:
    frame_at = hypothesis.frame_at

    def pose(chainage_m: float) -> RailVehiclePose:
        return rail_vehicle_pose_from_leading_bogie(
            frame_at,
            leading_chainage_m=chainage_m,
            geometry=geometry,
            minimum_chainage_m=0.0,
        )

    result: list[RailVehiclePose] = []
    start = hypothesis.leading_chainage_m
    coarse = [start]
    current = start
    while current < end_chainage_m - _EPS:
        current = min(
            end_chainage_m,
            current + sampling.max_chainage_step_m,
        )
        coarse.append(current)

    result.append(pose(coarse[0]))

    def append_interval(
        left: RailVehiclePose,
        right: RailVehiclePose,
        depth: int,
    ) -> None:
        middle_chainage = 0.5 * (
            left.leading_bogie.chainage_m
            + right.leading_bogie.chainage_m
        )
        middle = pose(middle_chainage)
        error = _pose_refinement_error_m(
            left,
            middle,
            right,
            geometry=geometry,
        )
        if (
            error <= sampling.max_pose_deviation_m
            or depth >= sampling.maximum_refinement_depth
        ):
            result.append(right)
            return
        append_interval(left, middle, depth + 1)
        append_interval(middle, right, depth + 1)

    left = result[0]
    for chainage in coarse[1:]:
        right = pose(chainage)
        append_interval(left, right, 0)
        left = right
    return tuple(result)


def build_route_swept_envelope(
    hypothesis: RouteHypothesis,
    *,
    lookahead_m: float,
    geometry: RailVehicleGeometry = MOSKVA_2020_81_775,
    allowance: EnvelopeAllowanceBudget | None = None,
    sampling: SweptEnvelopeSamplingConfig | None = None,
) -> RouteSweptEnvelope:
    if lookahead_m < 0.0:
        raise ValueError("lookahead_m must be non-negative")
    allowance = allowance or EnvelopeAllowanceBudget()
    sampling = sampling or SweptEnvelopeSamplingConfig()
    end = hypothesis.leading_chainage_m + float(lookahead_m)
    if hypothesis.maximum_leading_chainage_m is not None:
        end = min(end, hypothesis.maximum_leading_chainage_m)
    if end < hypothesis.leading_chainage_m:
        raise ValueError("resolved route envelope end precedes its start")

    poses = _adaptive_pose_samples(
        hypothesis,
        end_chainage_m=end,
        geometry=geometry,
        sampling=sampling,
    )
    # Refinement already bounds midpoint pose error. Keep that tolerance as an
    # explicit tiny numerical overlap margin so adjacent sampled OBBs form one
    # conservative screening volume rather than a set of mathematical slices.
    boxes = tuple(
        carbody_obb_from_pose(
            pose,
            geometry=geometry,
            allowance=allowance,
            numerical_inflation_m=sampling.max_pose_deviation_m,
        )
        for pose in poses
    )
    return RouteSweptEnvelope(
        route_id=hypothesis.route_id,
        boxes=boxes,
        allowance=allowance,
        sampling=sampling,
        source_start_chainage_m=hypothesis.leading_chainage_m,
        source_end_chainage_m=end,
        vehicle_geometry=geometry,
    )


def build_multi_route_swept_envelope(
    hypotheses: Sequence[RouteHypothesis],
    *,
    lookahead_m: float,
    geometry: RailVehicleGeometry = MOSKVA_2020_81_775,
    allowances_by_route: Mapping[str, EnvelopeAllowanceBudget] | None = None,
    sampling: SweptEnvelopeSamplingConfig | None = None,
) -> MultiRouteSweptEnvelope:
    hypotheses = tuple(hypotheses)
    if not hypotheses:
        raise ValueError("at least one route hypothesis is required")
    allowances_by_route = allowances_by_route or {}
    return MultiRouteSweptEnvelope(
        routes=tuple(
            build_route_swept_envelope(
                hypothesis,
                lookahead_m=lookahead_m,
                geometry=geometry,
                allowance=allowances_by_route.get(
                    hypothesis.route_id,
                    EnvelopeAllowanceBudget(),
                ),
                sampling=sampling,
            )
            for hypothesis in hypotheses
        )
    )
