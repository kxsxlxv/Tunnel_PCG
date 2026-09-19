from __future__ import annotations

from math import atan2


def gauge_for_radius(radius_m: float | None) -> float:
    """Current Moscow/SP rule. `None` means tangent/straight."""
    if radius_m is None or radius_m >= 1200.0:
        return 1.520
    if radius_m > 600.0:
        return 1.524
    if radius_m > 400.0:
        return 1.530
    if radius_m > 125.0:
        return 1.535
    if radius_m > 100.0:
        return 1.540
    if radius_m > 0.0:
        return 1.544
    raise ValueError("radius must be positive or None")


def cant_angle(cant_m: float, gauge_m: float) -> float:
    """Angle of the rail-head tangent plane from horizontal."""
    if gauge_m <= 0:
        raise ValueError("gauge must be positive")
    return atan2(cant_m, gauge_m)


def sleeper_pitch(count_per_km: int) -> float:
    if count_per_km <= 0:
        raise ValueError("count_per_km must be positive")
    return 1000.0 / count_per_km
