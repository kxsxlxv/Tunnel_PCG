from __future__ import annotations

from dataclasses import dataclass
from math import tan

from .geometry import Vec2


@dataclass(frozen=True)
class CircleEnvelope:
    radius_m: float
    center_y_m: float
    center_z_m: float

    def signed_margin(self, y_m: float, z_m: float) -> float:
        """Positive outside/free of envelope; negative means penetration."""
        d = ((y_m - self.center_y_m) ** 2 + (z_m - self.center_z_m) ** 2) ** 0.5
        return d - self.radius_m

    def contains(self, y_m: float, z_m: float) -> bool:
        return self.signed_margin(y_m, z_m) <= 0.0


def cmk(rail_type: str = "R65", *, cant_angle_rad: float = 0.0, curve_direction: str | None = None) -> CircleEnvelope:
    if rail_type == "R50":
        zc = 1.700
    elif rail_type == "R65":
        zc = 1.670
    else:
        raise ValueError("rail_type must be R50 or R65")
    q = zc * tan(cant_angle_rad)
    if curve_direction is None or abs(q) < 1e-15:
        yc = 0.0
    elif curve_direction == "left":
        yc = q  # inside of left curve is +Y under repository convention
    elif curve_direction == "right":
        yc = -q
    else:
        raise ValueError("curve_direction must be left/right/None")
    return CircleEnvelope(radius_m=2.450, center_y_m=yc, center_z_m=zc)


# Exact named upper outline points from GOST 23961-2024 Fig. 6.
# Coordinates: lateral y from track axis, z above UGR. Right half from bottom -> crown.
OM_UPPER_RIGHT = (
    Vec2(1.480, 0.550),  # v
    Vec2(1.480, 0.740),  # g
    Vec2(1.620, 3.280),  # d
    Vec2(1.325, 3.625),  # e
    Vec2(1.005, 3.745),  # zh
    Vec2(0.355, 3.780),  # z
    Vec2(0.000, 3.780),
)


def om_upper_polygon() -> list[Vec2]:
    right = list(OM_UPPER_RIGHT)
    left = [Vec2(-p.x, p.z) for p in reversed(right)]
    # Open bottom: this function only represents the exact upper outline, not lower Om.
    return left[:-1] + right


BR_TABLE_MM = {
    4000.0: 5.0, 3000.0: 7.0, 2000.0: 10.0, 1500.0: 14.0, 1200.0: 18.0,
    1000.0: 21.0, 800.0: 26.0, 600.0: 35.0, 500.0: 42.0, 400.0: 52.0,
    350.0: 60.0, 300.0: 70.0, 250.0: 84.0, 200.0: 105.0, 175.0: 120.0,
    150.0: 140.0, 125.0: 168.0, 100.0: 210.0, 80.0: 262.0, 60.0: 350.0,
}


def br_geometric_offset_m(radius_m: float, *, interpolate: bool = False) -> float:
    if radius_m in BR_TABLE_MM:
        return BR_TABLE_MM[radius_m] / 1000.0
    if not interpolate:
        raise KeyError("radius not tabulated by GOST A.1; pass interpolate=True only as an explicit engineering interpolation")
    keys = sorted(BR_TABLE_MM)
    if radius_m < keys[0] or radius_m > keys[-1]:
        raise ValueError("radius outside table range")
    lo = max(k for k in keys if k < radius_m)
    hi = min(k for k in keys if k > radius_m)
    # Explicit linear interpolation in R. The normative table itself remains the source of truth.
    t = (radius_m - lo) / (hi - lo)
    mm = BR_TABLE_MM[lo] + t * (BR_TABLE_MM[hi] - BR_TABLE_MM[lo])
    return mm / 1000.0


def lower_om_inside_curve_extra_m(radius_m: float) -> float:
    if radius_m < 100.0:
        return 0.020
    if radius_m < 125.0:
        return 0.016
    if radius_m < 150.0:
        return 0.011
    if radius_m < 200.0:
        return 0.006
    return 0.0
