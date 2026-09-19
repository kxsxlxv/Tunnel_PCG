from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ContactRailPlacement:
    side: str
    axis_y_m: float
    working_surface_z_m: float


def nominal_contact_rail(gauge_m: float, side: str) -> ContactRailPlacement:
    """Nominal physical placement in local track coordinates.

    +Y is left looking in increasing chainage. Gauge is between inner working faces.
    """
    if side not in {"left", "right"}:
        raise ValueError("side must be 'left' or 'right'")
    sign = 1.0 if side == "left" else -1.0
    y = sign * (gauge_m / 2.0 + 0.690)
    return ContactRailPlacement(side=side, axis_y_m=y, working_surface_z_m=0.160)


def rule_side(default_side: str = "left", *, curve_direction: str | None = None, radius_m: float | None = None, override: str | None = None) -> str:
    if override is not None:
        if override not in {"left", "right"}:
            raise ValueError("override must be left/right")
        return override
    if default_side not in {"left", "right"}:
        raise ValueError("default_side must be left/right")
    # Current SP: underground R<200 m -> contact rail on outside of curve.
    if radius_m is not None and radius_m < 200.0:
        if curve_direction == "left":
            return "right"  # outside
        if curve_direction == "right":
            return "left"
    return default_side
