from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from typing import Iterable

import numpy as np

from .config import AngleBounds, RangeDeg


class AngleMode(str, Enum):
    """Interpretations of Eqs. (1)-(4) in Yang et al. (2026).

    EQUATION_CONSISTENT:
        Enforces Eqs. (1)-(4), allows the A-block front/back spans to differ
        slightly when K_front != K_back. This is mathematically consistent with
        the published equations, but conflicts with one prose sentence saying
        A front/back spans are identical.

    LITERAL_A_EQUAL:
        Enforces A_front == A_back in addition to Eqs. (1)-(4). These conditions
        imply K_front == K_back, so this mode samples zero front/back taper.
    """

    EQUATION_CONSISTENT = "equation_consistent"
    LITERAL_A_EQUAL = "literal_a_equal"


@dataclass(frozen=True)
class SegmentAngle:
    name: str
    kind: str
    front_deg: float
    back_deg: float

    @property
    def center_deg(self) -> float:
        return 0.5 * (self.front_deg + self.back_deg)


@dataclass(frozen=True)
class RingAngles:
    """Six-segment layout in cyclic order K, B1, A1, A2, A3, B2."""

    segments: tuple[SegmentAngle, ...]
    mode: AngleMode

    def __post_init__(self) -> None:
        expected = ("K", "B1", "A1", "A2", "A3", "B2")
        got = tuple(s.name for s in self.segments)
        if got != expected:
            raise ValueError(f"expected segment order {expected}, got {got}")

    def by_name(self, name: str) -> SegmentAngle:
        return next(s for s in self.segments if s.name == name)

    @property
    def front_total_deg(self) -> float:
        return sum(s.front_deg for s in self.segments)

    @property
    def back_total_deg(self) -> float:
        return sum(s.back_deg for s in self.segments)

    @property
    def center_total_deg(self) -> float:
        return sum(s.center_deg for s in self.segments)

    def validate(self, bounds: AngleBounds | None = None, *, atol: float = 1e-8) -> None:
        bounds = bounds or AngleBounds()

        if not math.isclose(self.front_total_deg, 360.0, abs_tol=atol):
            raise ValueError(f"front face does not close: {self.front_total_deg}")
        if not math.isclose(self.back_total_deg, 360.0, abs_tol=atol):
            raise ValueError(f"back face does not close: {self.back_total_deg}")
        if not math.isclose(self.center_total_deg, 360.0, abs_tol=atol):
            raise ValueError(f"centre angles do not close: {self.center_total_deg}")

        k = self.by_name("K")
        if not bounds.k_center.contains(k.center_deg):
            raise ValueError(f"K centre angle out of bounds: {k.center_deg}")
        if not bounds.k_face.contains(k.front_deg) or not bounds.k_face.contains(k.back_deg):
            raise ValueError("K face angle out of bounds")

        for s in self.segments:
            if s.kind == "A":
                center_range, face_range = bounds.a_center, bounds.a_face
            elif s.kind == "B":
                center_range, face_range = bounds.b_center, bounds.b_face
            elif s.kind == "K":
                continue
            else:
                raise ValueError(f"unknown segment kind {s.kind}")
            if not center_range.contains(s.center_deg):
                raise ValueError(f"{s.name} centre angle out of bounds: {s.center_deg}")
            if not face_range.contains(s.front_deg) or not face_range.contains(s.back_deg):
                raise ValueError(f"{s.name} face angle out of bounds")

        # Eq. (4): K_f + B_j,f = K_b + B_j,b for the two B blocks.
        for name in ("B1", "B2"):
            b = self.by_name(name)
            lhs = k.front_deg + b.front_deg
            rhs = k.back_deg + b.back_deg
            if not math.isclose(lhs, rhs, abs_tol=atol):
                raise ValueError(f"Eq. (4) violated for {name}: {lhs} != {rhs}")

        if self.mode is AngleMode.LITERAL_A_EQUAL:
            for name in ("A1", "A2", "A3"):
                a = self.by_name(name)
                if not math.isclose(a.front_deg, a.back_deg, abs_tol=atol):
                    raise ValueError(f"literal mode requires {name} front == back")
            if not math.isclose(k.front_deg, k.back_deg, abs_tol=atol):
                raise ValueError("literal mode plus Eqs. (3)-(4) requires K front == back")


@dataclass(frozen=True)
class SegmentAngularExtent:
    name: str
    kind: str
    front_start_deg: float
    front_end_deg: float
    back_start_deg: float
    back_end_deg: float

    @property
    def front_span_deg(self) -> float:
        return self.front_end_deg - self.front_start_deg

    @property
    def back_span_deg(self) -> float:
        return self.back_end_deg - self.back_start_deg


def _truncated_normal(
    rng: np.random.Generator,
    nominal: float,
    bounds: RangeDeg,
    *,
    sigma: float | None = None,
    max_attempts: int = 500,
) -> float:
    if sigma is None:
        # Roughly 99.7% of an unconstrained Gaussian would lie in the range
        # when the nominal is near its centre. Rejection keeps hard bounds.
        sigma = max((bounds.high - bounds.low) / 6.0, 1e-9)
    for _ in range(max_attempts):
        x = float(rng.normal(nominal, sigma))
        if bounds.contains(x):
            return x
    # Deterministic bounded fallback for pathological custom bounds.
    return min(max(nominal, bounds.low), bounds.high)


def _all_in(values: Iterable[float], r: RangeDeg) -> bool:
    return all(r.contains(v) for v in values)


def sample_six_segment_angles(
    seed: int | None = None,
    *,
    mode: AngleMode | str = AngleMode.EQUATION_CONSISTENT,
    bounds: AngleBounds | None = None,
    max_attempts: int = 10_000,
) -> RingAngles:
    """Sample a symmetric six-segment ring satisfying the paper's angle equations.

    This baseline keeps all three A blocks mutually equal and the two B blocks
    mutually equal. It still permits front/back taper in EQUATION_CONSISTENT mode.
    The symmetry is deliberate for Stage 1; per-segment variation is deferred.
    """
    bounds = bounds or AngleBounds()
    mode = AngleMode(mode)
    rng = np.random.default_rng(seed)

    for _ in range(max_attempts):
        k_center = _truncated_normal(rng, bounds.k_nominal, bounds.k_center)

        if mode is AngleMode.LITERAL_A_EQUAL:
            delta = 0.0
        else:
            # delta = K_back - K_front. A modest Gaussian explores face taper;
            # hard bounds and downstream A/B feasibility are enforced by rejection.
            delta = float(rng.normal(0.0, 4.0))

        k_front = k_center - 0.5 * delta
        k_back = k_center + 0.5 * delta
        if not _all_in((k_front, k_back), bounds.k_face):
            continue

        a_center = _truncated_normal(rng, bounds.a_nominal, bounds.a_center)
        b_center = (360.0 - k_center - 3.0 * a_center) / 2.0
        if not bounds.b_center.contains(b_center):
            continue

        if mode is AngleMode.LITERAL_A_EQUAL:
            a_front = a_back = a_center
            b_front = b_back = b_center
        else:
            # Derived from Eqs. (3)-(4), assuming the A blocks are mutually
            # uniform and the two B blocks are mutually uniform:
            #   A_f - A_b = -delta/3
            #   B_f - B_b =  delta
            a_front = a_center - delta / 6.0
            a_back = a_center + delta / 6.0
            b_front = b_center + delta / 2.0
            b_back = b_center - delta / 2.0

        if not _all_in((a_front, a_back), bounds.a_face):
            continue
        if not _all_in((b_front, b_back), bounds.b_face):
            continue

        result = RingAngles(
            segments=(
                SegmentAngle("K", "K", k_front, k_back),
                SegmentAngle("B1", "B", b_front, b_back),
                SegmentAngle("A1", "A", a_front, a_back),
                SegmentAngle("A2", "A", a_front, a_back),
                SegmentAngle("A3", "A", a_front, a_back),
                SegmentAngle("B2", "B", b_front, b_back),
            ),
            mode=mode,
        )
        result.validate(bounds)
        return result

    raise RuntimeError(
        "could not sample a feasible six-segment ring within bounds; "
        "check custom bounds or increase max_attempts"
    )


def angular_extents(angles: RingAngles) -> tuple[SegmentAngularExtent, ...]:
    """Convert segment spans to cumulative front/back angular boundaries.

    K is centred at the crown (alpha=0) independently on both faces. The ring is
    traversed in the documented cyclic order K, B1, A1, A2, A3, B2.
    """
    k = angles.by_name("K")
    f = -0.5 * k.front_deg
    b = -0.5 * k.back_deg
    extents: list[SegmentAngularExtent] = []

    for s in angles.segments:
        item = SegmentAngularExtent(
            name=s.name,
            kind=s.kind,
            front_start_deg=f,
            front_end_deg=f + s.front_deg,
            back_start_deg=b,
            back_end_deg=b + s.back_deg,
        )
        extents.append(item)
        f = item.front_end_deg
        b = item.back_end_deg

    # Closing boundaries should be one full turn after the starts.
    if not math.isclose(f, -0.5 * k.front_deg + 360.0, abs_tol=1e-8):
        raise AssertionError("internal error: front angular extents do not close")
    if not math.isclose(b, -0.5 * k.back_deg + 360.0, abs_tol=1e-8):
        raise AssertionError("internal error: back angular extents do not close")

    return tuple(extents)
