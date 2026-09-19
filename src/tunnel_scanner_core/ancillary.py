from __future__ import annotations

"""Stage-8 ancillary structures from Tunnel Scanner Section 2.4 / Table 4.

The paper deliberately models ancillary components at lower geometric fidelity
than the lining. This module follows that principle: each local-ring object is
defined by a 2D XZ cross-section and extruded along +Y.

Published Table-4 parameters are preserved exactly, including the unusually
wide printed upper bound d_walk <= 0.34*r. Geometry/layout choices that are not
published (tube count/angles, rail-spacing interpretation, and exact pavement
cross-section closure) are explicit reconstruction metadata rather than hidden
Blender assumptions.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable

import numpy as np

from .mesh import Face, Vec3


class WalkwaySide(str, Enum):
    LEFT = "left"
    RIGHT = "right"

    @property
    def sign_x(self) -> float:
        return -1.0 if self is WalkwaySide.LEFT else 1.0


class TubeKind(str, Enum):
    PIPE = "pipe"
    CABLE = "cable"
    POWER_TRACK = "power_track"


class AncillarySamplingPolicy(str, Enum):
    REFERENCE = "reference"
    PUBLISHED_UNIFORM = "published_uniform"


@dataclass(frozen=True)
class TubeSpec:
    name: str
    kind: TubeKind
    alpha_deg: float
    radius_m: float

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("tube name must not be empty")
        if not math.isfinite(self.alpha_deg):
            raise ValueError("tube alpha_deg must be finite")
        if not math.isfinite(self.radius_m) or self.radius_m <= 0.0:
            raise ValueError("tube radius_m must be finite and positive")


@dataclass(frozen=True)
class AncillaryConfig:
    pavement_height_m: float
    walkway_height_m: float
    walkway_width_m: float
    walkway_depth_m: float
    walkway_side: WalkwaySide
    rail_depth_m: float
    rail_width_m: float
    rail_spacing_m: float
    tubes: tuple[TubeSpec, ...]
    tube_circle_vertices: int = 12
    pavement_arc_max_sagitta_m: float = 0.01
    longitudinal_subdivisions: int = 2

    def __post_init__(self) -> None:
        positive = (
            self.pavement_height_m,
            self.walkway_height_m,
            self.walkway_width_m,
            self.walkway_depth_m,
            self.rail_depth_m,
            self.rail_width_m,
            self.rail_spacing_m,
            self.pavement_arc_max_sagitta_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in positive):
            raise ValueError("ancillary dimensions must be finite and positive")
        if self.tube_circle_vertices < 8:
            raise ValueError("tube_circle_vertices must be >= 8")
        if self.longitudinal_subdivisions < 1:
            raise ValueError("longitudinal_subdivisions must be >= 1")
        names = [tube.name for tube in self.tubes]
        if len(names) != len(set(names)):
            raise ValueError("tube names must be unique")

    @classmethod
    def reference(cls, inner_radius_m: float) -> "AncillaryConfig":
        r = float(inner_radius_m)
        if not math.isfinite(r) or r <= 0.0:
            raise ValueError("inner_radius_m must be finite and positive")
        # Table 4 gives no tube count or angular positions. Six positions are a
        # Stage-8 engineering default chosen to occupy both sidewalls while
        # leaving crown/invert relatively clear.
        tubes = (
            TubeSpec("pipe_right_upper", TubeKind.PIPE, 60.0, 0.040 * r),
            TubeSpec("cable_right_mid", TubeKind.CABLE, 95.0, 0.010 * r),
            TubeSpec("cable_right_lower", TubeKind.CABLE, 110.0, 0.008 * r),
            TubeSpec("cable_left_lower", TubeKind.CABLE, 250.0, 0.008 * r),
            TubeSpec("cable_left_mid", TubeKind.CABLE, 265.0, 0.010 * r),
            TubeSpec("pipe_left_upper", TubeKind.PIPE, 300.0, 0.040 * r),
        )
        return cls(
            pavement_height_m=0.25 * r,
            walkway_height_m=0.60 * r,
            walkway_width_m=0.40 * r,
            walkway_depth_m=0.04 * r,
            walkway_side=WalkwaySide.RIGHT,
            rail_depth_m=0.175,
            rail_width_m=0.175,
            rail_spacing_m=1.5,
            tubes=tubes,
        )

    def validate_against_table4(self, inner_radius_m: float) -> None:
        r = float(inner_radius_m)
        checks = (
            ("pavement_height_m", self.pavement_height_m, 0.20 * r, 0.30 * r),
            ("walkway_height_m", self.walkway_height_m, 0.50 * r, 0.60 * r),
            ("walkway_width_m", self.walkway_width_m, 0.40 * r, 0.50 * r),
            # Preserve the printed 0.34*r upper bound exactly.
            ("walkway_depth_m", self.walkway_depth_m, 0.03 * r, 0.34 * r),
            ("rail_depth_m", self.rail_depth_m, 0.10, 0.50),
            ("rail_width_m", self.rail_width_m, 0.10, 0.50),
            ("rail_spacing_m", self.rail_spacing_m, 1.0, 2.0),
        )
        for name, value, low, high in checks:
            if not low - 1e-12 <= value <= high + 1e-12:
                raise ValueError(f"{name}={value:g} outside Table-4 bounds [{low:g},{high:g}]")
        low_tube = 0.005 * r
        high_tube = 0.05 * r
        for tube in self.tubes:
            if not low_tube - 1e-12 <= tube.radius_m <= high_tube + 1e-12:
                raise ValueError(
                    f"tube {tube.name} radius {tube.radius_m:g} outside "
                    f"Table-4 bounds [{low_tube:g},{high_tube:g}]"
                )

    def validate_physical_clearance(self, inner_radius_m: float) -> None:
        r = float(inner_radius_m)
        pavement_top_z = -r + self.pavement_height_m
        walkway_top_z = -r + self.walkway_height_m
        walkway_bottom_z = walkway_top_z - self.walkway_depth_m
        if walkway_bottom_z <= pavement_top_z:
            raise ValueError(
                "walkway intersects pavement under current Table-4 sample: "
                f"walkway_bottom_z={walkway_bottom_z:g}, pavement_top_z={pavement_top_z:g}"
            )
        rail_top_z = pavement_top_z + self.rail_depth_m
        half_rail_span = 0.5 * self.rail_spacing_m + 0.5 * self.rail_width_m
        if math.hypot(half_rail_span, rail_top_z) >= r:
            raise ValueError("rail prism exceeds tunnel intrados")

    @property
    def reconstruction_metadata(self) -> dict[str, object]:
        return {
            "source": "Yang et al. (2026) Section 2.4 / Table 4",
            "pavementCrossSection": (
                "Stage-8 reconstruction: circular-segment fill between intrados arc "
                "and the horizontal pavement elevation"
            ),
            "walkwayElevationConvention": (
                "h_walk interpreted as vertical height above tunnel invert; top surface "
                "is z=-r+h_walk and depth extends downward"
            ),
            "railSpacingConvention": (
                "Table 4 describes l_rail as spacing between rails; centres are placed "
                "at x=+/-l_rail/2"
            ),
            "tubePlacementStatus": (
                "paper states predefined angular positions but publishes neither count "
                "nor angles; Stage-8 reference layout is an explicit engineering default"
            ),
            "followRingAxialRotation": False,
        }


@dataclass(frozen=True)
class AncillaryMesh:
    name: str
    category: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    properties: dict[str, object]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("ancillary mesh name must not be empty")
        if not self.vertices or not self.faces:
            raise ValueError(f"{self.name}: ancillary mesh must contain geometry")


@dataclass(frozen=True)
class AncillarySet:
    config: AncillaryConfig
    inner_radius_m: float
    length_m: float
    meshes: tuple[AncillaryMesh, ...]

    def meshes_of_category(self, category: str) -> tuple[AncillaryMesh, ...]:
        return tuple(mesh for mesh in self.meshes if mesh.category == category)


def _signed_volume(vertices: tuple[Vec3, ...], faces: tuple[Face, ...]) -> float:
    total = 0.0
    vv = [np.asarray(v, dtype=float) for v in vertices]
    for face in faces:
        p0 = vv[face[0]]
        for i in range(1, len(face) - 1):
            total += float(np.dot(p0, np.cross(vv[face[i]], vv[face[i + 1]]))) / 6.0
    return total


def _positive_winding(
    vertices: tuple[Vec3, ...], faces: tuple[Face, ...]
) -> tuple[Face, ...]:
    if _signed_volume(vertices, faces) < 0.0:
        return tuple(tuple(reversed(face)) for face in faces)
    return faces


def _extrude_polygon_xz(
    points_xz: Iterable[tuple[float, float]],
    *,
    length_m: float,
    longitudinal_subdivisions: int = 2,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    points = tuple((float(x), float(z)) for x, z in points_xz)
    if len(points) < 3:
        raise ValueError("cross-section polygon must contain at least three points")
    if length_m <= 0.0:
        raise ValueError("length_m must be positive")
    if longitudinal_subdivisions < 1:
        raise ValueError("longitudinal_subdivisions must be >= 1")

    y0 = -0.5 * length_m
    vertices: list[Vec3] = []
    for iv in range(longitudinal_subdivisions + 1):
        y = y0 + length_m * iv / longitudinal_subdivisions
        vertices.extend((x, y, z) for x, z in points)

    n = len(points)
    faces: list[Face] = [
        tuple(reversed(tuple(range(n)))),
        tuple(
            longitudinal_subdivisions * n + i
            for i in range(n)
        ),
    ]
    for iv in range(longitudinal_subdivisions):
        a0 = iv * n
        b0 = (iv + 1) * n
        for i in range(n):
            j = (i + 1) % n
            faces.append((a0 + i, a0 + j, b0 + j, b0 + i))
    vv = tuple(vertices)
    ff = _positive_winding(vv, tuple(faces))
    if abs(_signed_volume(vv, ff)) <= 1e-15:
        raise ValueError("extruded polygon has zero volume")
    return vv, ff


def _required_arc_segments(radius_m: float, span_rad: float, sagitta_m: float) -> int:
    if span_rad <= 0.0:
        return 1
    c = max(-1.0, min(1.0, 1.0 - sagitta_m / radius_m))
    step = 2.0 * math.acos(c)
    if step <= 1e-12:
        return max(1, int(math.ceil(span_rad / 1e-6)))
    return max(1, int(math.ceil(span_rad / step)))


def _pavement_mesh(r: float, length_m: float, cfg: AncillaryConfig) -> AncillaryMesh:
    z_top = -r + cfg.pavement_height_m
    if not -r < z_top < r:
        raise ValueError("pavement elevation must intersect circular intrados")
    x_edge = math.sqrt(max(0.0, r * r - z_top * z_top))
    alpha_right = math.atan2(+x_edge, z_top)
    alpha_left = math.atan2(-x_edge, z_top)
    if alpha_left < alpha_right:
        alpha_left += 2.0 * math.pi
    span = alpha_left - alpha_right
    n_arc = _required_arc_segments(r, span, cfg.pavement_arc_max_sagitta_m)

    # Horizontal top chord from left to right, then the intrados arc from right
    # back to left through the invert.
    points: list[tuple[float, float]] = [(-x_edge, z_top), (+x_edge, z_top)]
    for i in range(1, n_arc):
        a = alpha_right + span * i / n_arc
        points.append((r * math.sin(a), r * math.cos(a)))
    vertices, faces = _extrude_polygon_xz(
        points,
        length_m=length_m,
        longitudinal_subdivisions=cfg.longitudinal_subdivisions,
    )
    return AncillaryMesh(
        name="pavement",
        category="pavement",
        vertices=vertices,
        faces=faces,
        properties={
            "pavementHeightM": cfg.pavement_height_m,
            "pavementTopZ": z_top,
            "pavementHalfChordM": x_edge,
            "arcSubdivisions": n_arc,
            "sourceParameter": "h_pav",
        },
    )


def _walkway_mesh(r: float, length_m: float, cfg: AncillaryConfig) -> AncillaryMesh:
    sign = cfg.walkway_side.sign_x
    z_top = -r + cfg.walkway_height_m
    z_bottom = z_top - cfg.walkway_depth_m
    if not (-r < z_bottom < r and -r < z_top < r):
        raise ValueError("walkway elevations must lie inside tunnel intrados")

    wall_top = sign * math.sqrt(max(0.0, r * r - z_top * z_top))
    wall_bottom = sign * math.sqrt(max(0.0, r * r - z_bottom * z_bottom))
    inner_top = wall_top - sign * cfg.walkway_width_m
    inner_bottom = wall_bottom - sign * cfg.walkway_width_m

    points = (
        (wall_top, z_top),
        (inner_top, z_top),
        (inner_bottom, z_bottom),
        (wall_bottom, z_bottom),
    )
    for x, z in points:
        if math.hypot(x, z) > r + 1e-10:
            raise ValueError("walkway cross-section leaves tunnel intrados")
    vertices, faces = _extrude_polygon_xz(
        points,
        length_m=length_m,
        longitudinal_subdivisions=cfg.longitudinal_subdivisions,
    )
    return AncillaryMesh(
        name=f"walkway_{cfg.walkway_side.value}",
        category="walkway",
        vertices=vertices,
        faces=faces,
        properties={
            "walkwayHeightM": cfg.walkway_height_m,
            "walkwayWidthM": cfg.walkway_width_m,
            "walkwayDepthM": cfg.walkway_depth_m,
            "walkwaySide": cfg.walkway_side.value,
            "walkwayTopZ": z_top,
            "sourceParameters": "h_walk,w_walk,d_walk,s_walk",
        },
    )


def _rail_mesh(
    r: float,
    length_m: float,
    cfg: AncillaryConfig,
    *,
    rail_index: int,
    center_x: float,
) -> AncillaryMesh:
    z0 = -r + cfg.pavement_height_m
    z1 = z0 + cfg.rail_depth_m
    half_w = 0.5 * cfg.rail_width_m
    points = (
        (center_x - half_w, z0),
        (center_x + half_w, z0),
        (center_x + half_w, z1),
        (center_x - half_w, z1),
    )
    vertices, faces = _extrude_polygon_xz(
        points,
        length_m=length_m,
        longitudinal_subdivisions=cfg.longitudinal_subdivisions,
    )
    return AncillaryMesh(
        name=f"rail_{rail_index}",
        category="rail",
        vertices=vertices,
        faces=faces,
        properties={
            "railIndex": rail_index,
            "railCenterX": center_x,
            "railWidthM": cfg.rail_width_m,
            "railDepthM": cfg.rail_depth_m,
            "railSpacingM": cfg.rail_spacing_m,
            "sourceParameters": "d_rail,w_rail,l_rail",
        },
    )


def _tube_mesh(r: float, length_m: float, cfg: AncillaryConfig, tube: TubeSpec) -> AncillaryMesh:
    n = cfg.tube_circle_vertices
    alpha = math.radians(tube.alpha_deg)
    rho = r - tube.radius_m
    center_x = rho * math.sin(alpha)
    center_z = rho * math.cos(alpha)
    points = tuple(
        (
            center_x + tube.radius_m * math.cos(2.0 * math.pi * i / n),
            center_z + tube.radius_m * math.sin(2.0 * math.pi * i / n),
        )
        for i in range(n)
    )
    for x, z in points:
        if math.hypot(x, z) > r + 1e-10:
            raise AssertionError("tube circle must remain inside intrados")
    vertices, faces = _extrude_polygon_xz(
        points,
        length_m=length_m,
        longitudinal_subdivisions=cfg.longitudinal_subdivisions,
    )
    return AncillaryMesh(
        name=tube.name,
        category="tube",
        vertices=vertices,
        faces=faces,
        properties={
            "tubeKind": tube.kind.value,
            "tubeAlphaDeg": tube.alpha_deg,
            "tubeRadiusM": tube.radius_m,
            "tubeCenterRadiusM": rho,
            "circleVertices": n,
            "sourceParameter": "r_tube",
        },
    )


def build_ancillary_set(
    *,
    inner_radius_m: float,
    length_m: float,
    config: AncillaryConfig | None = None,
) -> AncillarySet:
    r = float(inner_radius_m)
    if not math.isfinite(r) or r <= 0.0:
        raise ValueError("inner_radius_m must be finite and positive")
    if not math.isfinite(length_m) or length_m <= 0.0:
        raise ValueError("length_m must be finite and positive")
    cfg = config or AncillaryConfig.reference(r)
    cfg.validate_against_table4(r)
    cfg.validate_physical_clearance(r)

    meshes: list[AncillaryMesh] = [
        _pavement_mesh(r, length_m, cfg),
        _walkway_mesh(r, length_m, cfg),
    ]
    half_spacing = 0.5 * cfg.rail_spacing_m
    meshes.extend(
        (
            _rail_mesh(r, length_m, cfg, rail_index=0, center_x=-half_spacing),
            _rail_mesh(r, length_m, cfg, rail_index=1, center_x=+half_spacing),
        )
    )
    meshes.extend(_tube_mesh(r, length_m, cfg, tube) for tube in cfg.tubes)
    return AncillarySet(cfg, r, length_m, tuple(meshes))


def sample_ancillary_config(
    inner_radius_m: float,
    *,
    seed: int | None = None,
    policy: AncillarySamplingPolicy | str = AncillarySamplingPolicy.PUBLISHED_UNIFORM,
    max_attempts: int = 1000,
) -> AncillaryConfig:
    """Sample Table-4 bounds while retaining the unpublished default tube angles.

    REFERENCE returns the benchmark/reference values. PUBLISHED_UNIFORM samples
    numeric Table-4 bounds uniformly and rejects combinations where the walkway
    intersects the pavement or rails leave the intrados.
    """
    policy = AncillarySamplingPolicy(policy)
    r = float(inner_radius_m)
    if policy is AncillarySamplingPolicy.REFERENCE:
        return AncillaryConfig.reference(r)

    rng = np.random.default_rng(seed)
    base = AncillaryConfig.reference(r)
    for _ in range(max_attempts):
        tube_specs = tuple(
            TubeSpec(
                tube.name,
                tube.kind,
                tube.alpha_deg,
                float(rng.uniform(0.005 * r, 0.05 * r)),
            )
            for tube in base.tubes
        )
        cfg = AncillaryConfig(
            pavement_height_m=float(rng.uniform(0.20 * r, 0.30 * r)),
            walkway_height_m=float(rng.uniform(0.50 * r, 0.60 * r)),
            walkway_width_m=float(rng.uniform(0.40 * r, 0.50 * r)),
            walkway_depth_m=float(rng.uniform(0.03 * r, 0.34 * r)),
            walkway_side=(
                WalkwaySide.RIGHT if int(rng.integers(0, 2)) else WalkwaySide.LEFT
            ),
            rail_depth_m=float(rng.uniform(0.10, 0.50)),
            rail_width_m=float(rng.uniform(0.10, 0.50)),
            rail_spacing_m=float(rng.uniform(1.0, 2.0)),
            tubes=tube_specs,
        )
        try:
            cfg.validate_against_table4(r)
            cfg.validate_physical_clearance(r)
        except ValueError:
            continue
        return cfg
    raise RuntimeError(
        "could not sample a physically non-intersecting ancillary configuration "
        f"within {max_attempts} attempts"
    )


def iter_meshes(ancillary: AncillarySet) -> Iterable[AncillaryMesh]:
    yield from ancillary.meshes
