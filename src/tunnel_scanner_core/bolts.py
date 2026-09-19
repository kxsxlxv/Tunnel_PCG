from __future__ import annotations

"""Stage-6 reconstruction of Tunnel Scanner bolt pocket/head geometry.

The published paper provides Eqs. (12)-(20), Table 3, and Algorithm 1, but the
printed equations contain two dimensional/physical ambiguities that are kept
explicit here rather than hidden inside Blender code:

1. Eq. (20) places the pocket apex at `C - d*n` while Eq. (16) defines `n`
   as the outward radial normal and the prose calls the apex embedded in the
   concrete. For an intrados surface, an embedded apex must move *outward* into
   the lining. `BoltPocketMode.PHYSICAL_EMBEDDED` therefore uses `+d*n`;
   the printed sign is retained as a diagnostic mode.
2. Algorithm 1 line 5 adds the unit vector `n_bolt` directly to a position,
   which is dimensionally inconsistent and conflicts with Table 3's protrusion
   parameter `s`. The physical reconstruction uses `-s*n_bolt` (towards
   the tunnel centre) for the exposed/top centre. The literal algorithm is not
   used for production geometry.

Stage 6 remains engine-neutral. Blender Boolean operations are a separate
adapter layer so all geometry can be tested before involving bpy.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable

import numpy as np

from .mesh import Face, RingMesh, SegmentMesh, Vec3


Vec = np.ndarray


@dataclass(frozen=True)
class RangeM:
    low: float
    high: float

    def __post_init__(self) -> None:
        if not (0.0 < self.low <= self.high):
            raise ValueError("range must satisfy 0 < low <= high")

    @property
    def midpoint(self) -> float:
        return 0.5 * (self.low + self.high)

    def contains(self, value: float, *, atol: float = 1e-12) -> bool:
        return self.low - atol <= value <= self.high + atol


@dataclass(frozen=True)
class BoltBounds:
    """Table-3 bolt dimension bounds converted from millimetres to metres."""

    top_width_m: RangeM = RangeM(0.070, 0.090)
    bottom_width_m: RangeM = RangeM(0.100, 0.150)
    pocket_height_m: RangeM = RangeM(0.150, 0.160)
    penetration_m: RangeM = RangeM(0.110, 0.120)
    head_radius_m: RangeM = RangeM(0.020, 0.040)
    head_thickness_m: RangeM = RangeM(0.080, 0.090)
    protrusion_m: RangeM = RangeM(0.010, 0.015)
    joint_arc_offset_m: RangeM = RangeM(0.180, 0.230)


@dataclass(frozen=True)
class BoltConfig:
    top_width_m: float = 0.080
    bottom_width_m: float = 0.125
    pocket_height_m: float = 0.155
    penetration_m: float = 0.115
    head_radius_m: float = 0.030
    head_thickness_m: float = 0.085
    protrusion_m: float = 0.0125
    joint_arc_offset_m: float = 0.205
    longitudinal_offset_m: float = 0.400
    embedded_head_radius_ratio: float = 0.7
    head_height_ratio: float = 0.35
    head_ring_vertices: int = 12

    def __post_init__(self) -> None:
        positive = (
            self.top_width_m,
            self.bottom_width_m,
            self.pocket_height_m,
            self.penetration_m,
            self.head_radius_m,
            self.head_thickness_m,
            self.protrusion_m,
            self.joint_arc_offset_m,
            self.longitudinal_offset_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in positive):
            raise ValueError("bolt dimensions must be finite and positive")
        if self.top_width_m >= self.bottom_width_m:
            raise ValueError("top_width_m must be smaller than bottom_width_m")
        if not (0.0 < self.embedded_head_radius_ratio <= 1.0):
            raise ValueError("embedded_head_radius_ratio must be in (0,1]")
        if not (0.0 <= self.head_height_ratio <= 1.0):
            raise ValueError("head_height_ratio must be in [0,1]")
        if self.head_ring_vertices < 6:
            raise ValueError("head_ring_vertices must be >= 6")

    @property
    def pocket_depth_m(self) -> float:
        # Eq. (19)
        return self.penetration_m + self.protrusion_m

    @property
    def embedded_head_radius_m(self) -> float:
        # Algorithm 1 / prose: r_bb = 0.7*r_bolt
        return self.embedded_head_radius_ratio * self.head_radius_m

    def validate_against_paper_bounds(self, bounds: BoltBounds | None = None) -> None:
        bounds = bounds or BoltBounds()
        mapping = (
            ("top_width_m", self.top_width_m, bounds.top_width_m),
            ("bottom_width_m", self.bottom_width_m, bounds.bottom_width_m),
            ("pocket_height_m", self.pocket_height_m, bounds.pocket_height_m),
            ("penetration_m", self.penetration_m, bounds.penetration_m),
            ("head_radius_m", self.head_radius_m, bounds.head_radius_m),
            ("head_thickness_m", self.head_thickness_m, bounds.head_thickness_m),
            ("protrusion_m", self.protrusion_m, bounds.protrusion_m),
            ("joint_arc_offset_m", self.joint_arc_offset_m, bounds.joint_arc_offset_m),
        )
        for name, value, interval in mapping:
            if not interval.contains(value):
                raise ValueError(f"{name} outside Table-3 bounds: {value}")
        if not math.isclose(self.longitudinal_offset_m, 0.400, abs_tol=1e-12):
            raise ValueError("Table 3 fixes longitudinal y_off at 0.400 m")


@dataclass(frozen=True)
class BoltPerturbationConfig:
    """Explicit reconstruction of the ambiguous N(0, 0.001 m^2) statement.

    The paper calls the disturbances small/bounded but prints a variance that
    would imply sigma ~= 31.6 mm. We interpret the intended scale as sigma=1 mm
    and truncate at +/-3 sigma. Set sigma_m=0 for deterministic ideal pockets.
    Dimensionless depth/lateral multipliers use the same *relative* sigma of
    0.001; their effect is therefore sub-millimetric for the Table-3 geometry.
    """

    sigma_m: float = 0.001
    sigma_fraction: float = 0.001
    truncate_sigma: float = 3.0

    def __post_init__(self) -> None:
        if self.sigma_m < 0 or self.sigma_fraction < 0:
            raise ValueError("perturbation sigmas must be non-negative")
        if self.truncate_sigma <= 0:
            raise ValueError("truncate_sigma must be positive")


class BoltLayoutType(str, Enum):
    TYPE1_CENTERED = "type1_centered"
    TYPE2_LATERAL = "type2_lateral"
    TYPE3_JOINT_ALIGNED = "type3_joint_aligned"


class BoltPocketMode(str, Enum):
    """Sign convention for Eq. (20)."""

    PHYSICAL_EMBEDDED = "physical_embedded"
    PAPER_PRINTED_INWARD_APEX = "paper_printed_inward_apex"


@dataclass(frozen=True)
class BoltPlacement:
    index: int
    layout: BoltLayoutType
    segment_name: str
    alpha_deg: float
    y_m: float
    source: str


@dataclass(frozen=True)
class PocketPerturbation:
    delta_x_m: float
    delta_z_m: float
    epsilon_depth: float
    epsilon_lateral: float


@dataclass(frozen=True)
class BoltPocketMesh:
    placement: BoltPlacement
    vertices: tuple[Vec3, ...]  # v0..v4
    faces: tuple[Face, ...]
    surface_point: Vec3
    surface_normal: Vec3
    tangent_x: Vec3
    tangent_y: Vec3
    centroid: Vec3
    perturbation: PocketPerturbation
    mode: BoltPocketMode

    @property
    def apex(self) -> Vec3:
        return self.vertices[4]


@dataclass(frozen=True)
class BoltHeadMesh:
    placement: BoltPlacement
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    top_center: Vec3
    bottom_center: Vec3
    normal: Vec3
    basis_x: Vec3
    basis_y: Vec3
    top_radius_m: float
    bottom_radius_m: float
    thickness_m: float
    reconstruction: str = "stage6_physical_dimensionally_consistent_algorithm1"


@dataclass(frozen=True)
class BoltAssembly:
    placement: BoltPlacement
    pocket: BoltPocketMesh
    head: BoltHeadMesh


@dataclass(frozen=True)
class BoltSet:
    config: BoltConfig
    layout: BoltLayoutType
    assemblies: tuple[BoltAssembly, ...]
    perturbation_config: BoltPerturbationConfig
    pocket_mode: BoltPocketMode


# ---------- sampling ----------

def _truncated_normal(
    rng: np.random.Generator,
    bounds: RangeM,
    *,
    nominal: float | None = None,
    sigma: float | None = None,
    max_attempts: int = 500,
) -> float:
    nominal = bounds.midpoint if nominal is None else nominal
    sigma = max((bounds.high - bounds.low) / 6.0 if sigma is None else sigma, 1e-12)
    for _ in range(max_attempts):
        x = float(rng.normal(nominal, sigma))
        if bounds.contains(x):
            return x
    return min(max(float(nominal), bounds.low), bounds.high)


def sample_bolt_config(seed: int | None = None, *, bounds: BoltBounds | None = None) -> BoltConfig:
    bounds = bounds or BoltBounds()
    rng = np.random.default_rng(seed)
    cfg = BoltConfig(
        top_width_m=_truncated_normal(rng, bounds.top_width_m),
        bottom_width_m=_truncated_normal(rng, bounds.bottom_width_m),
        pocket_height_m=_truncated_normal(rng, bounds.pocket_height_m),
        penetration_m=_truncated_normal(rng, bounds.penetration_m),
        head_radius_m=_truncated_normal(rng, bounds.head_radius_m),
        head_thickness_m=_truncated_normal(rng, bounds.head_thickness_m),
        protrusion_m=_truncated_normal(rng, bounds.protrusion_m),
        joint_arc_offset_m=_truncated_normal(rng, bounds.joint_arc_offset_m),
        longitudinal_offset_m=0.400,
    )
    cfg.validate_against_paper_bounds(bounds)
    return cfg


def _sample_truncated_zero_mean(
    rng: np.random.Generator,
    sigma: float,
    truncate_sigma: float,
) -> float:
    if sigma == 0.0:
        return 0.0
    limit = sigma * truncate_sigma
    for _ in range(100):
        x = float(rng.normal(0.0, sigma))
        if abs(x) <= limit:
            return x
    return min(max(x, -limit), limit)


def sample_pocket_perturbation(
    rng: np.random.Generator,
    config: BoltPerturbationConfig,
) -> PocketPerturbation:
    return PocketPerturbation(
        delta_x_m=_sample_truncated_zero_mean(rng, config.sigma_m, config.truncate_sigma),
        delta_z_m=_sample_truncated_zero_mean(rng, config.sigma_m, config.truncate_sigma),
        epsilon_depth=_sample_truncated_zero_mean(
            rng, config.sigma_fraction, config.truncate_sigma
        ),
        epsilon_lateral=_sample_truncated_zero_mean(
            rng, config.sigma_fraction, config.truncate_sigma
        ),
    )


# ---------- placement ----------

def _mid_start(segment: SegmentMesh) -> float:
    e = segment.angular_extent
    return 0.5 * (e.front_start_deg + e.back_start_deg)


def _mid_end(segment: SegmentMesh) -> float:
    e = segment.angular_extent
    return 0.5 * (e.front_end_deg + e.back_end_deg)


def _segment_center(segment: SegmentMesh) -> float:
    return 0.5 * (_mid_start(segment) + _mid_end(segment))


def _nearest_equivalent(angle_deg: float, reference_deg: float) -> float:
    return angle_deg + 360.0 * round((reference_deg - angle_deg) / 360.0)


def _interface_alpha(previous: SegmentMesh, current: SegmentMesh) -> float:
    a = _mid_end(previous)
    b = _nearest_equivalent(_mid_start(current), a)
    if not math.isclose(a, b, abs_tol=1e-8):
        raise ValueError(f"segment interface mismatch: {previous.name}/{current.name}")
    return 0.5 * (a + b)


def _wrap_near_segment(alpha_deg: float, segment: SegmentMesh) -> float:
    center = _segment_center(segment)
    return _nearest_equivalent(alpha_deg, center)


def _inside_segment(alpha_deg: float, segment: SegmentMesh, *, margin_deg: float = 0.0) -> bool:
    a = _wrap_near_segment(alpha_deg, segment)
    lo, hi = sorted((_mid_start(segment), _mid_end(segment)))
    return lo + margin_deg <= a <= hi - margin_deg


def build_bolt_placements(
    ring: RingMesh,
    config: BoltConfig,
    layout: BoltLayoutType | str,
) -> tuple[BoltPlacement, ...]:
    """Expand Table-3 positioning rules into deterministic bolt instances.

    Interpretation details:
    * Type 1: one circumferential centreline, at y=-yoff,0,+yoff.
    * Type 2: both angular signs crossed with both longitudinal signs (4/segment).
    * Type 3: each joint gets one offset on each side; each side uses y=+/-yoff
      (4/joint). The side determines which adjacent segment owns the bolt.
    """
    layout = BoltLayoutType(layout)
    yoff = config.longitudinal_offset_m
    result: list[BoltPlacement] = []

    def add(segment_name: str, alpha: float, y: float, source: str) -> None:
        result.append(
            BoltPlacement(
                index=len(result),
                layout=layout,
                segment_name=segment_name,
                alpha_deg=float(alpha),
                y_m=float(y),
                source=source,
            )
        )

    if layout is BoltLayoutType.TYPE1_CENTERED:
        for segment in ring.segments:
            alpha = _segment_center(segment)
            for y in (-yoff, 0.0, +yoff):
                add(segment.name, alpha, y, "Table3:type1")

    elif layout is BoltLayoutType.TYPE2_LATERAL:
        theta_k = ring.angles.by_name("K").center_deg
        for segment in ring.segments:
            center = _segment_center(segment)
            for sign in (-1.0, +1.0):
                alpha = center + sign * theta_k
                # K may place a candidate exactly on/just outside its boundary
                # under random taper. Keep only geometrically owned candidates.
                if not _inside_segment(alpha, segment):
                    continue
                for y in (-yoff, +yoff):
                    add(segment.name, alpha, y, "Table3:type2")

    else:
        offset_deg = math.degrees(config.joint_arc_offset_m / ring.config.outer_radius_m)
        segments = ring.segments
        for i, previous in enumerate(segments):
            current = segments[(i + 1) % len(segments)]
            interface = _interface_alpha(previous, current)
            alpha_prev = interface - offset_deg
            alpha_next = interface + offset_deg
            for y in (-yoff, +yoff):
                add(previous.name, alpha_prev, y, "Table3:type3:previous-side")
                add(current.name, alpha_next, y, "Table3:type3:next-side")

    return tuple(result)


# ---------- vector / mesh helpers ----------

def _as_np(v: Vec3) -> Vec:
    return np.asarray(v, dtype=float)


def _as_vec3(v: Vec) -> Vec3:
    return (float(v[0]), float(v[1]), float(v[2]))


def _normalize(v: Vec, *, name: str) -> Vec:
    n = float(np.linalg.norm(v))
    if n <= 1e-12:
        raise ValueError(f"degenerate vector: {name}")
    return v / n


def _point(radius: float, alpha_deg: float, y: float) -> Vec:
    # Stage-1 convention: alpha=0 at +Z, increasing toward +X.
    a = math.radians(alpha_deg)
    return np.array((radius * math.sin(a), y, radius * math.cos(a)), dtype=float)


def _signed_volume(vertices: tuple[Vec3, ...], faces: tuple[Face, ...]) -> float:
    total = 0.0
    vv = [np.asarray(v, dtype=float) for v in vertices]
    for face in faces:
        p0 = vv[face[0]]
        for j in range(1, len(face) - 1):
            p1, p2 = vv[face[j]], vv[face[j + 1]]
            total += float(np.dot(p0, np.cross(p1, p2))) / 6.0
    return total


def _positive_winding(vertices: tuple[Vec3, ...], faces: tuple[Face, ...]) -> tuple[Face, ...]:
    if _signed_volume(vertices, faces) < 0.0:
        return tuple(tuple(reversed(face)) for face in faces)
    return faces


# ---------- pocket / head geometry ----------

def build_bolt_pocket(
    ring: RingMesh,
    config: BoltConfig,
    placement: BoltPlacement,
    *,
    perturbation: PocketPerturbation | None = None,
    mode: BoltPocketMode | str = BoltPocketMode.PHYSICAL_EMBEDDED,
) -> BoltPocketMesh:
    """Build Eqs. (12)-(20) in the repository coordinate convention."""
    mode = BoltPocketMode(mode)
    perturbation = perturbation or PocketPerturbation(0.0, 0.0, 0.0, 0.0)
    segment = next((s for s in ring.segments if s.name == placement.segment_name), None)
    if segment is None:
        raise ValueError(f"unknown placement segment {placement.segment_name}")
    if not _inside_segment(placement.alpha_deg, segment, margin_deg=0.0):
        raise ValueError(
            f"bolt alpha {placement.alpha_deg} not inside segment {segment.name}"
        )
    half_width = 0.5 * ring.config.width_m
    if not (-half_width <= placement.y_m <= half_width):
        raise ValueError("bolt longitudinal position lies outside ring width")

    # Eq. (12), adapted only for the repository's alpha convention.
    P = _point(ring.config.inner_radius_m, placement.alpha_deg, placement.y_m)
    radial = np.array((P[0], 0.0, P[2]), dtype=float)
    n = _normalize(radial, name="surface normal")
    uy = np.array((0.0, 1.0, 0.0), dtype=float)

    # Eq. (13) exactly: ex=n x uy, ey=n x ex.
    ex = _normalize(np.cross(n, uy), name="pocket ex")
    ey = _normalize(np.cross(n, ex), name="pocket ey")

    wb = config.bottom_width_m
    wt = config.top_width_m
    hp = config.pocket_height_m
    q = perturbation

    # Eq. (17)
    v0 = P - 0.5 * wb * ex - 0.5 * hp * ey
    v1 = P + 0.5 * wb * ex - 0.5 * hp * ey + q.delta_z_m * ey
    v2 = P + (0.5 * wt + q.delta_x_m) * ex + 0.5 * hp * ey
    v3 = P - 0.5 * wt * ex + 0.5 * hp * ey
    C = 0.25 * (v0 + v1 + v2 + v3)  # Eq. (18)

    direction = +1.0 if mode is BoltPocketMode.PHYSICAL_EMBEDDED else -1.0
    # Eq. (20), with the sign reconstruction isolated in mode.
    v4 = (
        C
        + direction * config.pocket_depth_m * (1.0 + q.epsilon_depth) * n
        + q.epsilon_lateral * wb * ex
    )

    vertices = tuple(_as_vec3(v) for v in (v0, v1, v2, v3, v4))
    # Closed pyramid. Base is the trapezoid v0-v1-v2-v3; sides meet at v4.
    faces: tuple[Face, ...] = (
        (0, 3, 2, 1),
        (0, 1, 4),
        (1, 2, 4),
        (2, 3, 4),
        (3, 0, 4),
    )
    faces = _positive_winding(vertices, faces)
    return BoltPocketMesh(
        placement=placement,
        vertices=vertices,
        faces=faces,
        surface_point=_as_vec3(P),
        surface_normal=_as_vec3(n),
        tangent_x=_as_vec3(ex),
        tangent_y=_as_vec3(ey),
        centroid=_as_vec3(C),
        perturbation=q,
        mode=mode,
    )


def _stable_plane_basis(normal: Vec) -> tuple[Vec, Vec]:
    # Algorithm 1 projects i=[1,0,0]. At orientations nearly parallel to X that
    # is numerically unstable, so use Y then Z as deterministic fallbacks.
    refs = (
        np.array((1.0, 0.0, 0.0), dtype=float),
        np.array((0.0, 1.0, 0.0), dtype=float),
        np.array((0.0, 0.0, 1.0), dtype=float),
    )
    for ref in refs:
        projected = ref - float(np.dot(ref, normal)) * normal
        if float(np.linalg.norm(projected)) > 1e-8:
            ex = _normalize(projected, name="bolt head basis x")
            ey = _normalize(np.cross(normal, ex), name="bolt head basis y")
            return ex, ey
    raise ValueError("cannot build bolt-head basis")


def build_bolt_head(config: BoltConfig, pocket: BoltPocketMesh) -> BoltHeadMesh:
    """Reconstruct Algorithm 1 with dimensional/protrusion correction.

    The normal and circular-ring construction follow Algorithm 1. Line 5 is
    reconstructed as `c + eta*(v4-c) - s*n_bolt` because the printed
    `+ n_bolt` adds a unit vector to a metric position and because Table 3
    defines s as protrusion toward the tunnel centre (opposite outward n).
    """
    vv = [_as_np(v) for v in pocket.vertices]
    v0, v1, _v2, _v3, v4 = vv
    n_surface = _as_np(pocket.surface_normal)

    cross = np.cross(v0 - v1, v4 - v1)
    n_bolt = _normalize(cross, name="bolt face normal")
    if float(np.dot(n_bolt, n_surface)) < 0.0:
        n_bolt = -n_bolt

    c = 0.5 * (v0 + v1)
    axis = v4 - c
    axis_len = float(np.linalg.norm(axis))
    if axis_len <= 1e-12:
        raise ValueError("degenerate pocket axis")
    # Dimensionally consistent reconstruction of Algorithm 1 line 5.
    P_top = c + config.head_height_ratio * axis - config.protrusion_m * n_bolt
    ex, ey = _stable_plane_basis(n_bolt)
    P_bottom = P_top + config.head_thickness_m * n_bolt

    N = config.head_ring_vertices
    top: list[Vec] = []
    bottom: list[Vec] = []
    for i in range(N):
        theta = 2.0 * math.pi * i / N
        radial = math.cos(theta) * ex + math.sin(theta) * ey
        top.append(P_top + config.head_radius_m * radial)
        bottom.append(P_bottom + config.embedded_head_radius_m * radial)

    vertices = tuple(_as_vec3(v) for v in (*top, *bottom))
    faces: list[Face] = []
    # Caps plus N quad sides.
    faces.append(tuple(reversed(tuple(range(N)))))
    faces.append(tuple(range(N, 2 * N)))
    for i in range(N):
        j = (i + 1) % N
        faces.append((i, j, N + j, N + i))
    ff = _positive_winding(vertices, tuple(faces))
    return BoltHeadMesh(
        placement=pocket.placement,
        vertices=vertices,
        faces=ff,
        top_center=_as_vec3(P_top),
        bottom_center=_as_vec3(P_bottom),
        normal=_as_vec3(n_bolt),
        basis_x=_as_vec3(ex),
        basis_y=_as_vec3(ey),
        top_radius_m=config.head_radius_m,
        bottom_radius_m=config.embedded_head_radius_m,
        thickness_m=config.head_thickness_m,
    )


def build_bolt_set(
    ring: RingMesh,
    config: BoltConfig,
    layout: BoltLayoutType | str,
    *,
    seed: int | None = None,
    perturbation_config: BoltPerturbationConfig | None = None,
    pocket_mode: BoltPocketMode | str = BoltPocketMode.PHYSICAL_EMBEDDED,
) -> BoltSet:
    layout = BoltLayoutType(layout)
    pocket_mode = BoltPocketMode(pocket_mode)
    perturbation_config = perturbation_config or BoltPerturbationConfig()
    rng = np.random.default_rng(seed)
    placements = build_bolt_placements(ring, config, layout)
    assemblies: list[BoltAssembly] = []
    for placement in placements:
        q = sample_pocket_perturbation(rng, perturbation_config)
        pocket = build_bolt_pocket(
            ring,
            config,
            placement,
            perturbation=q,
            mode=pocket_mode,
        )
        head = build_bolt_head(config, pocket)
        assemblies.append(BoltAssembly(placement, pocket, head))
    return BoltSet(
        config=config,
        layout=layout,
        assemblies=tuple(assemblies),
        perturbation_config=perturbation_config,
        pocket_mode=pocket_mode,
    )


def iter_meshes(bolts: BoltSet) -> Iterable[tuple[str, tuple[Vec3, ...], tuple[Face, ...]]]:
    for assembly in bolts.assemblies:
        stem = f"bolt_{assembly.placement.index:03d}_{assembly.placement.segment_name}"
        yield f"{stem}_pocket", assembly.pocket.vertices, assembly.pocket.faces
        yield f"{stem}_head", assembly.head.vertices, assembly.head.faces


@dataclass(frozen=True)
class BoltBooleanCutterMesh:
    """Pocket cutter enlarged slightly into the tunnel void for robust Booleans.

    The paper places the pocket base coplanar with its planar lining surface.
    Stage 5.1 uses a curved intrados, so a tangent trapezoid touches the cylinder
    only at its centre. Shifting the four mouth vertices inward by a few mm makes
    the cutter overlap the curved lining without changing the analytical pocket.
    """

    placement: BoltPlacement
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    overlap_m: float
    reconstruction: str = "stage6_curved_intrados_boolean_overlap"


def build_pocket_boolean_cutter(
    pocket: BoltPocketMesh,
    *,
    overlap_m: float = 0.005,
) -> BoltBooleanCutterMesh:
    if not math.isfinite(overlap_m) or overlap_m <= 0.0:
        raise ValueError("overlap_m must be finite and positive")
    n = _as_np(pocket.surface_normal)
    vv = [_as_np(v).copy() for v in pocket.vertices]
    # Only the mouth is moved toward the tunnel void. The embedded apex remains
    # identical to the analytical pocket, so penetration depth is unchanged.
    for i in range(4):
        vv[i] -= overlap_m * n
    vertices = tuple(_as_vec3(v) for v in vv)
    faces = _positive_winding(vertices, pocket.faces)
    return BoltBooleanCutterMesh(
        placement=pocket.placement,
        vertices=vertices,
        faces=faces,
        overlap_m=overlap_m,
    )
