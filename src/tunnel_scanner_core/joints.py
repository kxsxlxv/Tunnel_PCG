from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable

import numpy as np

from .mesh import Face, RingMesh, Vec3


@dataclass(frozen=True)
class JointRangeM:
    low: float
    high: float

    def contains(self, value: float, *, atol: float = 1e-12) -> bool:
        return self.low - atol <= value <= self.high + atol

    @property
    def midpoint(self) -> float:
        return 0.5 * (self.low + self.high)


@dataclass(frozen=True)
class JointBounds:
    """Default prescribed-joint bounds from Table 2 of Yang et al. (2026)."""

    width_m: JointRangeM = JointRangeM(0.035, 0.060)
    added_thickness_m: JointRangeM = JointRangeM(0.045, 0.075)


@dataclass(frozen=True)
class JointConfig:
    """Dimensions of the paper's prescribed joint.

    `added_thickness_m` follows Table 2 literally: it is thickness in addition
    to t_seg. Combined with Section 2.2's two explicit R_joi values, this makes
    the prescribed radial-joint hexahedron occupy radial levels R and R+t_joi,
    where R=r+t_seg is the segment outer radius.
    """

    width_m: float = 0.0475
    added_thickness_m: float = 0.060

    def __post_init__(self) -> None:
        if self.width_m <= 0:
            raise ValueError("width_m must be positive")
        if self.added_thickness_m <= 0:
            raise ValueError("added_thickness_m must be positive")

    def validate_against_paper_bounds(
        self,
        bounds: JointBounds | None = None,
        *,
        atol: float = 1e-12,
    ) -> None:
        bounds = bounds or JointBounds()
        if not bounds.width_m.contains(self.width_m, atol=atol):
            raise ValueError(f"joint width outside Table-2 bounds: {self.width_m}")
        if not bounds.added_thickness_m.contains(self.added_thickness_m, atol=atol):
            raise ValueError(
                "joint added thickness outside Table-2 bounds: "
                f"{self.added_thickness_m}"
            )


class JointReconstruction(str, Enum):
    """Explicitly names which parts are literal vs inferred.

    PAPER_LITERAL_OUTER_RIB:
        Radial joint reconstructed directly from the two R_joi levels printed
        in Section 2.2: R and R+t_joi, with theta=w/R_joi at each level.

    CIRCUMFERENTIAL_OUTER_COLLAR:
        Minimal extension of the same 'thickness in addition to t_seg' concept
        to the circumferential joint. The paper states its orientation and that
        it links rings, but provides no corresponding vertex equations. This
        mode is therefore intentionally marked as an extrapolation.
    """

    PAPER_LITERAL_OUTER_RIB = "paper_literal_outer_rib"
    CIRCUMFERENTIAL_OUTER_COLLAR = "circumferential_outer_collar"


@dataclass(frozen=True)
class RadialJointMesh:
    name: str
    previous_segment: str
    next_segment: str
    width_m: float
    added_thickness_m: float
    base_radius_m: float
    cap_radius_m: float
    front_interface_alpha_deg: float
    back_interface_alpha_deg: float
    base_angular_width_deg: float
    cap_angular_width_deg: float
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    reconstruction: JointReconstruction = JointReconstruction.PAPER_LITERAL_OUTER_RIB

    @property
    def base_arc_width_m(self) -> float:
        return self.base_radius_m * math.radians(self.base_angular_width_deg)

    @property
    def cap_arc_width_m(self) -> float:
        return self.cap_radius_m * math.radians(self.cap_angular_width_deg)


@dataclass(frozen=True)
class CircumferentialJointMesh:
    """One segment-shaped piece of a circumferential outer collar.

    The paper does not publish a vertex construction for circumferential joints.
    This is the minimal hexahedral extrapolation consistent with:
      * the joint lies in / is normal to the XZ ring plane,
      * w_joi is its axial width,
      * t_joi is thickness in addition to t_seg.

    It intentionally sits outside the segment extrados, not on the LiDAR-facing
    intrados. A sensor-facing groove is *not* inferred here.
    """

    name: str
    segment_name: str
    side: str
    width_m: float
    added_thickness_m: float
    base_radius_m: float
    cap_radius_m: float
    y_inner_m: float
    y_outer_m: float
    alpha_start_deg: float
    alpha_end_deg: float
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    reconstruction: JointReconstruction = JointReconstruction.CIRCUMFERENTIAL_OUTER_COLLAR

    @property
    def axial_width_m(self) -> float:
        return abs(self.y_outer_m - self.y_inner_m)


@dataclass(frozen=True)
class PrescribedJointSet:
    config: JointConfig
    radial: tuple[RadialJointMesh, ...]
    circumferential_front: tuple[CircumferentialJointMesh, ...]
    circumferential_back: tuple[CircumferentialJointMesh, ...]


def _truncated_normal(
    rng: np.random.Generator,
    bounds: JointRangeM,
    *,
    nominal: float | None = None,
    sigma: float | None = None,
    max_attempts: int = 500,
) -> float:
    nominal = bounds.midpoint if nominal is None else nominal
    sigma = (bounds.high - bounds.low) / 6.0 if sigma is None else sigma
    sigma = max(float(sigma), 1e-12)
    for _ in range(max_attempts):
        x = float(rng.normal(nominal, sigma))
        if bounds.contains(x):
            return x
    return min(max(float(nominal), bounds.low), bounds.high)


def sample_joint_config(
    seed: int | None = None,
    *,
    bounds: JointBounds | None = None,
) -> JointConfig:
    """Sample Table-2 dimensions with a hard-bounded Gaussian.

    The paper says the bounds use Gaussian sampling but does not publish sigma.
    As in Stage 1, sigma=(high-low)/6 is used so ~99.7% of an unconstrained
    centred Gaussian lies inside the reported interval; rejection enforces the
    hard bounds.
    """
    bounds = bounds or JointBounds()
    rng = np.random.default_rng(seed)
    cfg = JointConfig(
        width_m=_truncated_normal(rng, bounds.width_m),
        added_thickness_m=_truncated_normal(rng, bounds.added_thickness_m),
    )
    cfg.validate_against_paper_bounds(bounds)
    return cfg


def _point(radius: float, alpha_deg: float, y: float) -> Vec3:
    # Keep the same Stage-1 coordinate convention: alpha=0 at +Z crown and
    # increases toward +X.
    a = math.radians(alpha_deg)
    return (radius * math.sin(a), y, radius * math.cos(a))


def _hexa_faces() -> tuple[Face, ...]:
    return (
        (0, 2, 3, 1),
        (4, 5, 7, 6),
        (0, 4, 6, 2),
        (1, 3, 7, 5),
        (0, 1, 5, 4),
        (2, 6, 7, 3),
    )


def _signed_volume(vertices: tuple[Vec3, ...], faces: tuple[Face, ...]) -> float:
    vv = [np.asarray(v, dtype=float) for v in vertices]
    total = 0.0
    for face in faces:
        if len(face) != 4:
            raise ValueError("Stage-4 joint hexahedra require quad faces")
        for i0, i1, i2 in ((face[0], face[1], face[2]), (face[0], face[2], face[3])):
            total += float(np.dot(vv[i0], np.cross(vv[i1], vv[i2]))) / 6.0
    return total


def _normalize_winding(
    vertices: tuple[Vec3, ...],
    faces: tuple[Face, ...],
) -> tuple[Face, ...]:
    if _signed_volume(vertices, faces) < 0:
        return tuple((face[0], *reversed(face[1:])) for face in faces)
    return faces


def _nearest_equivalent_deg(angle_deg: float, reference_deg: float) -> float:
    """Return angle+k*360 closest to reference."""
    k = round((reference_deg - angle_deg) / 360.0)
    return angle_deg + 360.0 * k


def _interface_alpha(prev_end_deg: float, next_start_deg: float, *, atol: float = 1e-8) -> float:
    next_equiv = _nearest_equivalent_deg(next_start_deg, prev_end_deg)
    if not math.isclose(prev_end_deg, next_equiv, abs_tol=atol):
        raise ValueError(
            "adjacent undeformed segment boundaries do not coincide: "
            f"{prev_end_deg} vs {next_start_deg}"
        )
    return 0.5 * (prev_end_deg + next_equiv)


def _cyclic_pairs(items: tuple) -> Iterable[tuple[object, object]]:
    for i, item in enumerate(items):
        yield item, items[(i + 1) % len(items)]


def build_prescribed_radial_joints(
    ring: RingMesh,
    joint: JointConfig,
) -> tuple[RadialJointMesh, ...]:
    """Build six paper-literal prescribed radial joint hexahedra.

    Section 2.2 gives:
        theta_joi = w_joi / R_joi
        R_joi in {r+t_seg, r+t_seg+t_joi} = {R, R+t_joi}

    The implementation therefore centres a narrow outer-rib hexahedron on each
    undeformed segment interface. Both radial levels have the same *arc length*
    w_joi, so their angular widths differ slightly.

    This faithfully follows the published radii. It does NOT reinterpret the
    joint as a recessed intrados groove, because the paper does not provide a
    compatible formula for such a groove.
    """
    R = ring.config.outer_radius_m
    cap_R = R + joint.added_thickness_m
    yf = -0.5 * ring.config.width_m
    yb = +0.5 * ring.config.width_m

    base_width_deg = math.degrees(joint.width_m / R)
    cap_width_deg = math.degrees(joint.width_m / cap_R)
    base_half = 0.5 * base_width_deg
    cap_half = 0.5 * cap_width_deg

    result: list[RadialJointMesh] = []
    segments = ring.segments
    for prev, nxt in _cyclic_pairs(segments):
        front_alpha = _interface_alpha(
            prev.angular_extent.front_end_deg,
            nxt.angular_extent.front_start_deg,
        )
        back_alpha = _interface_alpha(
            prev.angular_extent.back_end_deg,
            nxt.angular_extent.back_start_deg,
        )

        vertices: tuple[Vec3, ...] = (
            _point(R, front_alpha - base_half, yf),
            _point(R, front_alpha + base_half, yf),
            _point(R, back_alpha - base_half, yb),
            _point(R, back_alpha + base_half, yb),
            _point(cap_R, front_alpha - cap_half, yf),
            _point(cap_R, front_alpha + cap_half, yf),
            _point(cap_R, back_alpha - cap_half, yb),
            _point(cap_R, back_alpha + cap_half, yb),
        )
        faces = _normalize_winding(vertices, _hexa_faces())
        result.append(
            RadialJointMesh(
                name=f"radial_joint_{prev.name}_{nxt.name}",
                previous_segment=prev.name,
                next_segment=nxt.name,
                width_m=joint.width_m,
                added_thickness_m=joint.added_thickness_m,
                base_radius_m=R,
                cap_radius_m=cap_R,
                front_interface_alpha_deg=front_alpha,
                back_interface_alpha_deg=back_alpha,
                base_angular_width_deg=base_width_deg,
                cap_angular_width_deg=cap_width_deg,
                vertices=vertices,
                faces=faces,
            )
        )

    return tuple(result)


def build_circumferential_outer_collar(
    ring: RingMesh,
    joint: JointConfig,
    *,
    side: str,
) -> tuple[CircumferentialJointMesh, ...]:
    """Build a provisional six-piece circumferential outer collar.

    This is deliberately a separate API because Section 2.2 does not publish an
    equation analogous to theta_joi for the ring-to-ring joint. We only use the
    explicit qualitative constraints: XZ-aligned ring interface, joint width,
    and thickness in addition to t_seg.

    The collar is useful for testing/export and later Blender reconstruction,
    but should not be presented as uniquely recovered author code.
    """
    side = side.lower()
    if side not in {"front", "back"}:
        raise ValueError("side must be 'front' or 'back'")

    R = ring.config.outer_radius_m
    cap_R = R + joint.added_thickness_m
    half_L = 0.5 * ring.config.width_m
    if side == "front":
        y0, y1 = -half_L - joint.width_m, -half_L
    else:
        y0, y1 = +half_L, +half_L + joint.width_m

    pieces: list[CircumferentialJointMesh] = []
    for segment in ring.segments:
        e = segment.angular_extent
        if side == "front":
            a0, a1 = e.front_start_deg, e.front_end_deg
        else:
            a0, a1 = e.back_start_deg, e.back_end_deg

        vertices: tuple[Vec3, ...] = (
            _point(R, a0, y0),
            _point(R, a1, y0),
            _point(R, a0, y1),
            _point(R, a1, y1),
            _point(cap_R, a0, y0),
            _point(cap_R, a1, y0),
            _point(cap_R, a0, y1),
            _point(cap_R, a1, y1),
        )
        faces = _normalize_winding(vertices, _hexa_faces())
        pieces.append(
            CircumferentialJointMesh(
                name=f"circumferential_{side}_{segment.name}",
                segment_name=segment.name,
                side=side,
                width_m=joint.width_m,
                added_thickness_m=joint.added_thickness_m,
                base_radius_m=R,
                cap_radius_m=cap_R,
                y_inner_m=y0,
                y_outer_m=y1,
                alpha_start_deg=a0,
                alpha_end_deg=a1,
                vertices=vertices,
                faces=faces,
            )
        )
    return tuple(pieces)


def build_prescribed_joint_set(
    ring: RingMesh,
    joint: JointConfig,
    *,
    include_circumferential: bool = True,
) -> PrescribedJointSet:
    radial = build_prescribed_radial_joints(ring, joint)
    if include_circumferential:
        front = build_circumferential_outer_collar(ring, joint, side="front")
        back = build_circumferential_outer_collar(ring, joint, side="back")
    else:
        front = ()
        back = ()
    return PrescribedJointSet(
        config=joint,
        radial=radial,
        circumferential_front=front,
        circumferential_back=back,
    )
