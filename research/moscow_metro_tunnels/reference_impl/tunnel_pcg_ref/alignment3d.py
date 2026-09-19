from __future__ import annotations

from dataclasses import dataclass
from math import acos, atan, atan2, cos, hypot, sin, sqrt
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Vec2:
    x: float
    y: float

    def __add__(self, o: "Vec2") -> "Vec2":
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: "Vec2") -> "Vec2":
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, k: float) -> "Vec2":
        return Vec2(self.x * k, self.y * k)

    __rmul__ = __mul__

    def norm(self) -> float:
        return hypot(self.x, self.y)


@dataclass(frozen=True)
class Vec3:
    x: float
    y: float
    z: float

    def __add__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x + o.x, self.y + o.y, self.z + o.z)

    def __sub__(self, o: "Vec3") -> "Vec3":
        return Vec3(self.x - o.x, self.y - o.y, self.z - o.z)

    def __mul__(self, k: float) -> "Vec3":
        return Vec3(self.x * k, self.y * k, self.z * k)

    __rmul__ = __mul__

    def dot(self, o: "Vec3") -> float:
        return self.x * o.x + self.y * o.y + self.z * o.z

    def cross(self, o: "Vec3") -> "Vec3":
        return Vec3(
            self.y * o.z - self.z * o.y,
            self.z * o.x - self.x * o.z,
            self.x * o.y - self.y * o.x,
        )

    def norm(self) -> float:
        return sqrt(self.dot(self))

    def normalized(self) -> "Vec3":
        n = self.norm()
        if n == 0:
            raise ValueError("zero vector")
        return self * (1.0 / n)


@dataclass(frozen=True)
class Frame3:
    p: Vec3
    tangent: Vec3
    left: Vec3
    up: Vec3


@dataclass(frozen=True)
class ProfileAnchor:
    s_m: float
    z_ugr_m: float
    sigma_z_m: float = 0.0
    source_id: str | None = None
    datum: str = "UGR_absolute"


def chainage_xy(points: Sequence[Vec2]) -> list[float]:
    if len(points) < 2:
        raise ValueError("need >=2 points")
    out = [0.0]
    for a, b in zip(points, points[1:]):
        d = (b - a).norm()
        if d <= 0:
            raise ValueError("duplicate consecutive point")
        out.append(out[-1] + d)
    return out


def interpolate_polyline_xy(points: Sequence[Vec2], s_query: float) -> Vec2:
    ss = chainage_xy(points)
    if not (0.0 <= s_query <= ss[-1]):
        raise ValueError("s outside polyline")
    for i in range(len(ss) - 1):
        if s_query <= ss[i + 1]:
            t = (s_query - ss[i]) / (ss[i + 1] - ss[i])
            return points[i] * (1 - t) + points[i + 1] * t
    return points[-1]


def resample_polyline_xy(points: Sequence[Vec2], step_m: float) -> list[Vec2]:
    if step_m <= 0:
        raise ValueError("step must be positive")
    total = chainage_xy(points)[-1]
    s = 0.0
    out = []
    while s < total:
        out.append(interpolate_polyline_xy(points, s))
        s += step_m
    out.append(points[-1])
    return out


def project_point_to_polyline_xy(
    p: Vec2, points: Sequence[Vec2]
) -> tuple[float, float, Vec2]:
    ss = chainage_xy(points)
    best = None
    for i, (a, b) in enumerate(zip(points, points[1:])):
        ab = b - a
        denom = ab.x * ab.x + ab.y * ab.y
        t = max(
            0.0,
            min(
                1.0,
                ((p.x - a.x) * ab.x + (p.y - a.y) * ab.y) / denom,
            ),
        )
        q = a + ab * t
        d = (p - q).norm()
        s = ss[i] + t * (ss[i + 1] - ss[i])
        if best is None or d < best[1]:
            best = (s, d, q)
    assert best is not None
    return best


def grade_permille(a: Vec3, b: Vec3) -> float:
    ds = hypot(b.x - a.x, b.y - a.y)
    if ds <= 0:
        raise ValueError("zero horizontal distance")
    return 1000.0 * (b.z - a.z) / ds


def vertical_curve_tangent_length_m(
    radius_m: float, grade1_permille: float, grade2_permille: float
) -> float:
    if radius_m <= 0:
        raise ValueError("radius must be positive")
    a1 = atan(grade1_permille / 1000.0)
    a2 = atan(grade2_permille / 1000.0)
    return radius_m * abs(__import__("math").tan((a2 - a1) / 2.0))


def station_ugr_from_depth(
    surface_z_m: float,
    depth_m: float,
    *,
    depth_datum: str,
    platform_top_above_ugr_m: float = 1.1,
) -> float:
    """Convert a published station depth to UGR only when its datum is known.

    depth_datum:
      - "UGR": depth is surface -> rail-head plane
      - "platform_top": depth is surface -> platform top

    Ambiguous depth meanings are rejected rather than guessed.
    """
    if depth_m < 0:
        raise ValueError("depth must be nonnegative")
    if depth_datum == "UGR":
        return surface_z_m - depth_m
    if depth_datum == "platform_top":
        return surface_z_m - depth_m - platform_top_above_ugr_m
    raise ValueError("unsupported/ambiguous depth datum")


def interpolate_profile(
    anchors: Sequence[ProfileAnchor], s_samples: Iterable[float]
) -> list[float]:
    """Piecewise-linear preliminary interpolation.

    This is intentionally not a final vertical-alignment solver. Production
    reconstruction should replace breaks in grade with validated vertical
    curves and enforce SP limits.
    """
    if len(anchors) < 2:
        raise ValueError("need >=2 vertical anchors")
    aa = sorted(anchors, key=lambda a: a.s_m)
    if any(b.s_m <= a.s_m for a, b in zip(aa, aa[1:])):
        raise ValueError("duplicate/decreasing anchor chainage")
    out = []
    for s in s_samples:
        if s < aa[0].s_m or s > aa[-1].s_m:
            raise ValueError("sample outside anchors")
        for a, b in zip(aa, aa[1:]):
            if s <= b.s_m:
                t = (s - a.s_m) / (b.s_m - a.s_m)
                out.append(a.z_ugr_m * (1 - t) + b.z_ugr_m * t)
                break
    return out


def localize(points: Sequence[Vec3], origin: Vec3) -> list[Vec3]:
    return [p - origin for p in points]


def _rotate_about_axis(v: Vec3, axis: Vec3, angle: float) -> Vec3:
    # Rodrigues rotation.
    a = axis.normalized()
    c = cos(angle)
    s = sin(angle)
    return v * c + a.cross(v) * s + a * (a.dot(v) * (1 - c))



def _minimal_transport(v: Vec3, from_t: Vec3, to_t: Vec3) -> Vec3:
    """Rotate a vector by the minimum rotation carrying one tangent to another."""
    axis = from_t.cross(to_t)
    n = axis.norm()
    if n < 1e-12:
        if from_t.dot(to_t) < -0.999999999:
            raise ValueError("180-degree tangent reversal is ambiguous")
        return v
    axis = axis * (1.0 / n)
    angle = acos(max(-1.0, min(1.0, from_t.dot(to_t))))
    return _rotate_about_axis(v, axis, angle)


def parallel_transport_frames(
    points: Sequence[Vec3], *, initial_up: Vec3 = Vec3(0, 0, 1)
) -> list[Frame3]:
    """Low-twist frames for sweeping/instancing along a 3D alignment."""
    if len(points) < 2:
        raise ValueError("need >=2 3D points")

    tangents = []
    for i, p in enumerate(points):
        if i == 0:
            t = (points[1] - p).normalized()
        elif i == len(points) - 1:
            t = (p - points[i - 1]).normalized()
        else:
            t = (points[i + 1] - points[i - 1]).normalized()
        tangents.append(t)

    t0 = tangents[0]
    u = initial_up - t0 * initial_up.dot(t0)
    if u.norm() < 1e-9:
        alt = Vec3(0, 1, 0)
        u = alt - t0 * alt.dot(t0)
    u = u.normalized()
    left = u.cross(t0).normalized()
    u = t0.cross(left).normalized()

    frames = [Frame3(points[0], t0, left, u)]
    prev_t, prev_left, prev_up = t0, left, u

    for i in range(1, len(points)):
        t = tangents[i]
        axis = prev_t.cross(t)
        axis_norm = axis.norm()
        if axis_norm < 1e-12:
            left, up = prev_left, prev_up
        else:
            axis = axis * (1.0 / axis_norm)
            angle = acos(max(-1.0, min(1.0, prev_t.dot(t))))
            left = _rotate_about_axis(prev_left, axis, angle).normalized()
            up = _rotate_about_axis(prev_up, axis, angle).normalized()
            left = (left - t * left.dot(t)).normalized()
            up = t.cross(left).normalized()

        frames.append(Frame3(points[i], t, left, up))
        prev_t, prev_left, prev_up = t, left, up

    return frames



def closed_parallel_transport_frames(
    points: Sequence[Vec3], *, initial_up: Vec3 = Vec3(0, 0, 1)
) -> tuple[list[Frame3], float]:
    """Return low-twist frames for a closed route and its raw holonomy roll.

    Input must contain at least three unique points and repeat the first point
    at the end. A raw parallel-transport frame can return to the seam with a
    residual roll (holonomy) on a non-planar closed curve. This function
    measures that signed roll and distributes the opposite correction by 3D
    arc length around the complete loop.

    The returned final frame is at the repeated first point and closes
    continuously with the first frame. This is the preferred frame generator
    for ring routes such as Moscow Metro Line 5.
    """
    if len(points) < 4:
        raise ValueError("closed loop needs >=3 unique points plus closure")
    if (points[-1] - points[0]).norm() > 1e-7:
        raise ValueError("closed loop input must repeat the first point at the end")

    unique = list(points[:-1])
    n = len(unique)
    tangents = [
        (unique[(i + 1) % n] - unique[(i - 1 + n) % n]).normalized()
        for i in range(n)
    ]

    t0 = tangents[0]
    up0 = initial_up - t0 * initial_up.dot(t0)
    if up0.norm() < 1e-9:
        alt = Vec3(0, 1, 0)
        up0 = alt - t0 * alt.dot(t0)
    up0 = up0.normalized()
    left0 = up0.cross(t0).normalized()
    up0 = t0.cross(left0).normalized()

    raw = [Frame3(unique[0], t0, left0, up0)]
    left, up = left0, up0
    for i in range(1, n):
        left = _minimal_transport(left, tangents[i - 1], tangents[i]).normalized()
        up = _minimal_transport(up, tangents[i - 1], tangents[i]).normalized()
        left = (left - tangents[i] * left.dot(tangents[i])).normalized()
        up = tangents[i].cross(left).normalized()
        raw.append(Frame3(unique[i], tangents[i], left, up))

    # Close the *uncorrected* frame once to measure the signed residual roll.
    closed_left = _minimal_transport(raw[-1].left, tangents[-1], t0).normalized()
    closed_left = (closed_left - t0 * closed_left.dot(t0)).normalized()
    residual = atan2(
        t0.dot(left0.cross(closed_left)),
        left0.dot(closed_left),
    )

    # 3D chainage including the final segment back to the first point.
    ss = [0.0]
    for a, b in zip(unique, unique[1:]):
        ss.append(ss[-1] + (b - a).norm())
    closing_len = (unique[0] - unique[-1]).norm()
    total = ss[-1] + closing_len
    if total <= 0:
        raise ValueError("degenerate closed loop")

    corrected: list[Frame3] = []
    for frame, s_m in zip(raw, ss):
        correction = -residual * (s_m / total)
        left = _rotate_about_axis(
            frame.left, frame.tangent, correction
        ).normalized()
        up = _rotate_about_axis(
            frame.up, frame.tangent, correction
        ).normalized()
        corrected.append(Frame3(frame.p, frame.tangent, left, up))

    # Continue both transport and the distributed correction through the seam.
    seam_left = _minimal_transport(
        corrected[-1].left, tangents[-1], t0
    ).normalized()
    seam_up = _minimal_transport(
        corrected[-1].up, tangents[-1], t0
    ).normalized()
    remaining = -residual * (closing_len / total)
    seam_left = _rotate_about_axis(seam_left, t0, remaining).normalized()
    seam_up = _rotate_about_axis(seam_up, t0, remaining).normalized()
    corrected.append(Frame3(points[-1], t0, seam_left, seam_up))

    return corrected, residual


def apply_cant(frame: Frame3, cant_angle_rad: float) -> Frame3:
    left = _rotate_about_axis(frame.left, frame.tangent, cant_angle_rad).normalized()
    up = _rotate_about_axis(frame.up, frame.tangent, cant_angle_rad).normalized()
    return Frame3(frame.p, frame.tangent, left, up)
