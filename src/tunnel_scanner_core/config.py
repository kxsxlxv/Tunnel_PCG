from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class RangeDeg:
    low: float
    high: float

    def contains(self, value: float, *, atol: float = 1e-9) -> bool:
        return self.low - atol <= value <= self.high + atol

    @property
    def midpoint(self) -> float:
        return 0.5 * (self.low + self.high)


@dataclass(frozen=True)
class AngleBounds:
    """Default angle bounds reported in Table 1 of Yang et al. (2026)."""

    k_center: RangeDeg = RangeDeg(20.0, 25.0)
    k_face: RangeDeg = RangeDeg(13.0, 30.0)
    a_center: RangeDeg = RangeDeg(65.0, 75.0)
    a_face: RangeDeg = RangeDeg(65.0, 75.0)
    b_center: RangeDeg = RangeDeg(65.0, 75.0)
    b_face: RangeDeg = RangeDeg(65.0, 75.0)

    k_nominal: float = 22.5
    a_nominal: float = 67.5
    b_nominal: float = 67.5


@dataclass(frozen=True)
class RingConfig:
    """Geometry for one undeformed six-segment ring.

    Coordinate convention used by this reimplementation:
      * +Y = tunnel longitudinal direction
      * XZ = tunnel cross-section
      * alpha = 0 at crown (+Z), increasing toward +X
    """

    outer_radius_m: float = 3.35
    thickness_m: float = 0.35
    width_m: float = 1.35

    def __post_init__(self) -> None:
        if self.outer_radius_m <= 0:
            raise ValueError("outer_radius_m must be positive")
        if self.thickness_m <= 0:
            raise ValueError("thickness_m must be positive")
        if self.thickness_m >= self.outer_radius_m:
            raise ValueError("thickness_m must be smaller than outer_radius_m")
        if self.width_m <= 0:
            raise ValueError("width_m must be positive")

    @property
    def inner_radius_m(self) -> float:
        return self.outer_radius_m - self.thickness_m

    @classmethod
    def from_outer_radius_and_thickness(
        cls,
        outer_radius_m: float,
        thickness_m: float,
        *,
        width_m: float | None = None,
    ) -> "RingConfig":
        """Create config using the paper's empirical L_seg/t_seg relation if width is omitted.

        Table 1 reports:
            L_seg = (20.38 * exp(-1.88 R) + 2.94) * t_seg
        """
        if width_m is None:
            width_m = (
                20.38 * math.exp(-1.88 * outer_radius_m) + 2.94
            ) * thickness_m
        return cls(
            outer_radius_m=outer_radius_m,
            thickness_m=thickness_m,
            width_m=width_m,
        )
