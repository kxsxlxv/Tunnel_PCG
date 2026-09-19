from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RingInstance:
    index: int
    s_center_m: float
    width_m: float
    roll_rad: float = 0.0


def ring_sequence(s0: float, s1: float, width_m: float, phase_m: float = 0.0) -> list[RingInstance]:
    if width_m <= 0 or s1 < s0:
        raise ValueError("invalid ring range")
    rings = []
    k = int((s0 - phase_m) // width_m) - 1
    while True:
        center = phase_m + (k + 0.5) * width_m
        if center > s1 + width_m:
            break
        if s0 <= center <= s1:
            rings.append(RingInstance(k, center, width_m))
        k += 1
    return rings
