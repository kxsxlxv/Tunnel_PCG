from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, pi, sin, sqrt
from typing import Iterable, Sequence


@dataclass(frozen=True)
class Vec2:
    x: float
    z: float

    def __add__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x + other.x, self.z + other.z)

    def __sub__(self, other: "Vec2") -> "Vec2":
        return Vec2(self.x - other.x, self.z - other.z)

    def __mul__(self, k: float) -> "Vec2":
        return Vec2(self.x * k, self.z * k)

    __rmul__ = __mul__

    def dot(self, other: "Vec2") -> float:
        return self.x * other.x + self.z * other.z

    def norm(self) -> float:
        return sqrt(self.x * self.x + self.z * self.z)

    def normalized(self) -> "Vec2":
        n = self.norm()
        if n == 0:
            raise ValueError("zero-length vector")
        return Vec2(self.x / n, self.z / n)


@dataclass(frozen=True)
class Line2:
    # unit-normal form: n.x * x + n.z * z + c = 0
    n: Vec2
    c: float

    @classmethod
    def through(cls, p: Vec2, direction: Vec2) -> "Line2":
        d = direction.normalized()
        n = Vec2(-d.z, d.x)
        return cls(n=n, c=-(n.dot(p)))

    def signed_distance(self, p: Vec2) -> float:
        return self.n.dot(p) + self.c

    def project(self, p: Vec2) -> Vec2:
        d = self.signed_distance(p)
        return p - self.n * d


def intersect_offset_lines(a: Line2, da: float, b: Line2, db: float) -> Vec2:
    # Solve [a.n; b.n] p = [da-a.c; db-b.c]
    det = a.n.x * b.n.z - a.n.z * b.n.x
    if abs(det) < 1e-12:
        raise ValueError("parallel lines")
    rhs1 = da - a.c
    rhs2 = db - b.c
    x = (rhs1 * b.n.z - a.n.z * rhs2) / det
    z = (a.n.x * rhs2 - rhs1 * b.n.x) / det
    return Vec2(x, z)


def line_circle_intersections(line: Line2, signed_offset: float, center: Vec2, radius: float) -> list[Vec2]:
    # Point closest to origin on offset line n.p = signed_offset-c.
    d = signed_offset - line.c
    p0 = line.n * d
    tangent = Vec2(-line.n.z, line.n.x)
    rel = p0 - center
    B = 2.0 * rel.dot(tangent)
    C = rel.dot(rel) - radius * radius
    disc = B * B - 4.0 * C
    if disc < -1e-10:
        return []
    disc = max(0.0, disc)
    root = sqrt(disc)
    s1 = (-B + root) / 2.0
    s2 = (-B - root) / 2.0
    return [p0 + tangent * s1, p0 + tangent * s2]


def circle_tangent_point(big_center: Vec2, big_radius: float, small_center: Vec2) -> Vec2:
    v = small_center - big_center
    n = v.normalized()
    return big_center + n * big_radius


def sample_arc(center: Vec2, radius: float, start: Vec2, end: Vec2, chord_error: float = 1e-4) -> list[Vec2]:
    """Sample the minor circular arc from start to end.

    Units are arbitrary but consistent. chord_error is maximum radial sagitta.
    """
    a0 = atan2(start.z - center.z, start.x - center.x)
    a1 = atan2(end.z - center.z, end.x - center.x)
    da = (a1 - a0 + pi) % (2.0 * pi) - pi
    if radius <= 0:
        raise ValueError("radius must be positive")
    if chord_error <= 0:
        raise ValueError("chord_error must be positive")
    if chord_error >= radius:
        n = 1
    else:
        theta_max = 2.0 * __import__("math").acos(max(-1.0, min(1.0, 1.0 - chord_error / radius)))
        n = max(1, int(__import__("math").ceil(abs(da) / theta_max)))
    pts = []
    for i in range(n + 1):
        t = i / n
        a = a0 + da * t
        pts.append(Vec2(center.x + radius * cos(a), center.z + radius * sin(a)))
    return pts


def sample_line(start: Vec2, end: Vec2) -> list[Vec2]:
    return [start, end]


def stitch(parts: Sequence[Sequence[Vec2]], tol: float = 1e-9) -> list[Vec2]:
    out: list[Vec2] = []
    for part in parts:
        for p in part:
            if out and (p - out[-1]).norm() <= tol:
                continue
            out.append(p)
    return out


def mirror_closed_half_profile(half_top_to_bottom: Sequence[Vec2]) -> list[Vec2]:
    """Input: top-center -> right boundary -> bottom-center. Output closed polygon vertices."""
    right = list(half_top_to_bottom)
    left = [Vec2(-p.x, p.z) for p in reversed(right)]
    return right + left[1:-1]


def polygon_area_centroid(poly: Sequence[Vec2]) -> tuple[float, Vec2]:
    if len(poly) < 3:
        raise ValueError("polygon needs >=3 points")
    cross_sum = cx_sum = cz_sum = 0.0
    n = len(poly)
    for i, p in enumerate(poly):
        q = poly[(i + 1) % n]
        cr = p.x * q.z - q.x * p.z
        cross_sum += cr
        cx_sum += (p.x + q.x) * cr
        cz_sum += (p.z + q.z) * cr
    area = 0.5 * cross_sum
    if abs(area) < 1e-15:
        raise ValueError("degenerate polygon")
    centroid = Vec2(cx_sum / (6.0 * area), cz_sum / (6.0 * area))
    return area, centroid


def rotate_xz(p: Vec2, angle_rad: float) -> Vec2:
    c = cos(angle_rad)
    s = sin(angle_rad)
    return Vec2(c * p.x - s * p.z, s * p.x + c * p.z)
