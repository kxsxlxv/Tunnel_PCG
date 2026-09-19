from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

import numpy as np

from .angles import RingAngles
from .config import RingConfig


Vec2 = tuple[float, float]


class KinematicIndexing(str, Enum):
    """Reconstruction/diagnostic conventions for Eqs. (5)-(11).

    CORRECTED_SEGMENT_INDEXED
        Generation convention used from Stage 3 onward. Step i consumes d_i,
        phi_i, as required by the prose and by the stated closure unknowns. The
        orientation update is also made geometrically consistent with Eq. (9):
            theta_i = theta_(i-1) - alpha_i + phi_i.
        The printed paper has ``- phi_(i-1)``. The + sign is required for the
        new segment's shared-joint radius to rotate by the same R(phi) used in
        Eq. (9), and is independently supported by the ring-centre construction
        shown in Lin et al. (2023), the paper's ref. [49].

    INDEX_CORRECTED_PRINTED_SIGN
        Stage-2 diagnostic: fixes only the i-1 indexing but retains the printed
        ``- phi`` orientation update. This closes algebraically but cannot be
        mapped to rigid segment geometry while preserving the shared rotation
        pivot for pure rotation.

    AS_PRINTED_PREVIOUS_INDEX
        Literal diagnostic implementation: step i consumes d_(i-1), phi_(i-1)
        and uses the printed -phi orientation update. Under this convention the
        paper's stated d_N and phi_N closure unknowns never enter the recurrence.
    """

    CORRECTED_SEGMENT_INDEXED = "corrected_segment_indexed"
    INDEX_CORRECTED_PRINTED_SIGN = "index_corrected_printed_sign"
    AS_PRINTED_PREVIOUS_INDEX = "as_printed_previous_index"


@dataclass(frozen=True)
class DeformationBounds:
    """Table-2 bounds for ring-wise segment deformation."""

    max_abs_dislocation_m: float = 0.010
    max_abs_rotation_deg: float = 0.3

    def __post_init__(self) -> None:
        if self.max_abs_dislocation_m <= 0:
            raise ValueError("max_abs_dislocation_m must be positive")
        if self.max_abs_rotation_deg <= 0:
            raise ValueError("max_abs_rotation_deg must be positive")


@dataclass(frozen=True)
class KinematicStep:
    index: int
    segment_name: str
    segment_center_angle_deg: float
    dislocation_m: float
    rotation_deg: float
    origin_before: Vec2
    theta_before_deg: float
    temporary_origin: Vec2
    rotation_center: Vec2
    origin_after: Vec2
    theta_after_deg: float


@dataclass(frozen=True)
class RingDeformation:
    """Closed ring-wise rigid-body deformation trajectory.

    ``O(i)`` is interpreted as the local ring/curvature centre of segment i in
    the recurrence frame. This interpretation is consistent with the geometry
    shown in Lin et al. (2023), ref. [49] of Tunnel Scanner: adjacent rigid arc
    segments have individual centres O_B1, O_L1, etc. It also explains why all
    O(i) coincide at (0,0) for an undeformed ring.
    """

    steps: tuple[KinematicStep, ...]
    indexing: KinematicIndexing
    attempts: int = 1

    @property
    def dislocations_m(self) -> tuple[float, ...]:
        return tuple(s.dislocation_m for s in self.steps)

    @property
    def rotations_deg(self) -> tuple[float, ...]:
        return tuple(s.rotation_deg for s in self.steps)

    @property
    def final_origin(self) -> Vec2:
        return self.steps[-1].origin_after if self.steps else (0.0, 0.0)

    @property
    def final_theta_deg(self) -> float:
        return self.steps[-1].theta_after_deg if self.steps else 180.0

    @property
    def translation_closure_error_m(self) -> float:
        return math.hypot(*self.final_origin)

    @property
    def angular_closure_error_deg(self) -> float:
        # For both +/- phi conventions, sum(phi)=0 at closure and the centre
        # angles sum to 360 deg, so Eq. (11) remains theta_N + 180 = 0.
        return self.final_theta_deg + 180.0

    def validate(
        self,
        bounds: DeformationBounds | None = None,
        *,
        translation_atol_m: float = 1e-9,
        angle_atol_deg: float = 1e-9,
    ) -> None:
        bounds = bounds or DeformationBounds()
        if abs(self.translation_closure_error_m) > translation_atol_m:
            raise ValueError(
                f"translation closure failed: {self.translation_closure_error_m} m"
            )
        if abs(self.angular_closure_error_deg) > angle_atol_deg:
            raise ValueError(
                f"angular closure failed: {self.angular_closure_error_deg} deg"
            )
        for step in self.steps:
            if abs(step.dislocation_m) > bounds.max_abs_dislocation_m + 1e-12:
                raise ValueError(
                    f"d_{step.index} out of bounds: {step.dislocation_m} m"
                )
            if abs(step.rotation_deg) > bounds.max_abs_rotation_deg + 1e-12:
                raise ValueError(
                    f"phi_{step.index} out of bounds: {step.rotation_deg} deg"
                )


def _rotation_2d(phi_rad: float) -> np.ndarray:
    c = math.cos(phi_rad)
    s = math.sin(phi_rad)
    return np.array(((c, -s), (s, c)), dtype=float)


def _transition_order(angles: RingAngles) -> tuple[tuple[str, float], ...]:
    """Return the reconstructed i=1..N traversal.

    K is the i=0 reference; i=N is the transformed K state used only to verify
    closure. Physical segment transforms are therefore K(identity), B1(step 1),
    A1(step 2), A2(step 3), A3(step 4), B2(step 5); step 6 must return to the
    identity K frame.
    """
    order = ("B1", "A1", "A2", "A3", "B2", "K")
    return tuple((name, angles.by_name(name).center_deg) for name in order)


def _one_step(
    origin: np.ndarray,
    theta_rad: float,
    segment_angle_rad: float,
    dislocation_m: float,
    rotation_rad: float,
    mean_radius_m: float,
    *,
    rotation_sign_in_theta: int,
) -> tuple[np.ndarray, float, np.ndarray, np.ndarray]:
    """Apply Eqs. (6)-(10) once.

    Eq. (9) is always the printed active 2D R(phi). ``rotation_sign_in_theta``
    controls only Eq. (10)'s orientation update:
      +1 -> geometrically reconstructed -alpha + phi
      -1 -> printed -alpha - phi
    """
    if rotation_sign_in_theta not in (-1, +1):
        raise ValueError("rotation_sign_in_theta must be +/-1")

    radial = np.array((math.cos(theta_rad), math.sin(theta_rad)), dtype=float)

    # Eq. (6)
    temporary = origin - dislocation_m * radial

    # Eq. (7): the shared rotation centre lies at the lining mean radius, split
    # by half the radial dislocation between the two adjacent segment frames.
    rotation_center = origin + (
        mean_radius_m - 0.5 * dislocation_m
    ) * radial

    # Eqs. (8)-(9)
    local = temporary - rotation_center
    rotated = _rotation_2d(rotation_rad) @ local

    # Eq. (10): translation back to global recurrence frame.
    origin_after = rotated + rotation_center
    theta_after = (
        theta_rad
        - segment_angle_rad
        + rotation_sign_in_theta * rotation_rad
    )

    return origin_after, theta_after, temporary, rotation_center


def _propagate_segment_indexed(
    config: RingConfig,
    angles: RingAngles,
    dislocations_m,
    rotations_deg,
    *,
    rotation_sign_in_theta: int,
    indexing: KinematicIndexing,
    attempts: int = 1,
) -> RingDeformation:
    transition = _transition_order(angles)
    n = len(transition)
    ds = np.asarray(dislocations_m, dtype=float)
    phis_deg = np.asarray(rotations_deg, dtype=float)
    if ds.shape != (n,) or phis_deg.shape != (n,):
        raise ValueError(f"expected {n} dislocations and {n} rotations")

    origin = np.zeros(2, dtype=float)
    theta = math.pi
    mean_radius = config.inner_radius_m + 0.5 * config.thickness_m
    steps: list[KinematicStep] = []

    for i, ((name, alpha_deg), d, phi_deg) in enumerate(
        zip(transition, ds, phis_deg), start=1
    ):
        before = origin.copy()
        theta_before = theta
        origin, theta, temporary, rotation_center = _one_step(
            origin,
            theta,
            math.radians(alpha_deg),
            float(d),
            math.radians(float(phi_deg)),
            mean_radius,
            rotation_sign_in_theta=rotation_sign_in_theta,
        )
        steps.append(
            KinematicStep(
                index=i,
                segment_name=name,
                segment_center_angle_deg=float(alpha_deg),
                dislocation_m=float(d),
                rotation_deg=float(phi_deg),
                origin_before=(float(before[0]), float(before[1])),
                theta_before_deg=math.degrees(theta_before),
                temporary_origin=(float(temporary[0]), float(temporary[1])),
                rotation_center=(float(rotation_center[0]), float(rotation_center[1])),
                origin_after=(float(origin[0]), float(origin[1])),
                theta_after_deg=math.degrees(theta),
            )
        )

    return RingDeformation(
        steps=tuple(steps),
        indexing=indexing,
        attempts=attempts,
    )


def propagate_corrected(
    config: RingConfig,
    angles: RingAngles,
    dislocations_m: tuple[float, ...] | list[float] | np.ndarray,
    rotations_deg: tuple[float, ...] | list[float] | np.ndarray,
    *,
    attempts: int = 1,
) -> RingDeformation:
    """Propagate the geometry-consistent reconstructed recurrence.

    Step i consumes d_i, phi_i. Eq. (9) rotates the new segment centre around
    the shared joint by +phi_i; consequently the outgoing radial orientation is
    ``theta_(i-1) + phi_i - alpha_i``. This +phi sign is the Stage-3 correction
    that allows the recurrence to be mapped onto actual rigid arc meshes.
    """
    return _propagate_segment_indexed(
        config,
        angles,
        dislocations_m,
        rotations_deg,
        rotation_sign_in_theta=+1,
        indexing=KinematicIndexing.CORRECTED_SEGMENT_INDEXED,
        attempts=attempts,
    )


def propagate_index_corrected_printed_sign(
    config: RingConfig,
    angles: RingAngles,
    dislocations_m,
    rotations_deg,
) -> RingDeformation:
    """Diagnostic Stage-2 convention: corrected indices, printed -phi sign."""
    return _propagate_segment_indexed(
        config,
        angles,
        dislocations_m,
        rotations_deg,
        rotation_sign_in_theta=-1,
        indexing=KinematicIndexing.INDEX_CORRECTED_PRINTED_SIGN,
    )


def propagate_as_printed(
    config: RingConfig,
    angles: RingAngles,
    dislocations_0_to_n_minus_1_m: tuple[float, ...] | list[float] | np.ndarray,
    rotations_0_to_n_minus_1_deg: tuple[float, ...] | list[float] | np.ndarray,
) -> RingDeformation:
    """Diagnostic literal implementation of the printed i-1 subscripts/sign."""
    transition = _transition_order(angles)
    n = len(transition)
    ds = np.asarray(dislocations_0_to_n_minus_1_m, dtype=float)
    phis_deg = np.asarray(rotations_0_to_n_minus_1_deg, dtype=float)
    if ds.shape != (n,) or phis_deg.shape != (n,):
        raise ValueError(f"expected {n} values indexed 0..{n-1}")

    origin = np.zeros(2, dtype=float)
    theta = math.pi
    mean_radius = config.inner_radius_m + 0.5 * config.thickness_m
    steps: list[KinematicStep] = []

    for i, ((name, alpha_deg), d_prev, phi_prev_deg) in enumerate(
        zip(transition, ds, phis_deg), start=1
    ):
        before = origin.copy()
        theta_before = theta
        origin, theta, temporary, rotation_center = _one_step(
            origin,
            theta,
            math.radians(alpha_deg),
            float(d_prev),
            math.radians(float(phi_prev_deg)),
            mean_radius,
            rotation_sign_in_theta=-1,
        )
        steps.append(
            KinematicStep(
                index=i,
                segment_name=name,
                segment_center_angle_deg=float(alpha_deg),
                dislocation_m=float(d_prev),
                rotation_deg=float(phi_prev_deg),
                origin_before=(float(before[0]), float(before[1])),
                theta_before_deg=math.degrees(theta_before),
                temporary_origin=(float(temporary[0]), float(temporary[1])),
                rotation_center=(float(rotation_center[0]), float(rotation_center[1])),
                origin_after=(float(origin[0]), float(origin[1])),
                theta_after_deg=math.degrees(theta),
            )
        )

    return RingDeformation(
        steps=tuple(steps),
        indexing=KinematicIndexing.AS_PRINTED_PREVIOUS_INDEX,
    )


def _bounded_normal(
    rng: np.random.Generator,
    bound: float,
    *,
    sigma: float | None = None,
    max_attempts: int = 1000,
) -> float:
    """Zero-mean Gaussian with hard symmetric bounds.

    Table 2 states Gaussian sampling inside the published bounds but omits sigma.
    The reimplementation keeps the documented Stage-2 assumption sigma=bound/3.
    """
    sigma = bound / 3.0 if sigma is None else sigma
    for _ in range(max_attempts):
        value = float(rng.normal(0.0, sigma))
        if abs(value) <= bound:
            return value
    return 0.0


def _solve_last_two_dislocations(
    config: RingConfig,
    angles: RingAngles,
    prefix_dislocations: np.ndarray,
    rotations_deg: np.ndarray,
) -> tuple[float, float, float]:
    """Solve d_(N-1), d_N from translational closure using an exact 2x2 solve."""
    n = len(rotations_deg)
    if prefix_dislocations.shape != (n - 2,):
        raise ValueError("prefix must contain d_1..d_(N-2)")

    base_ds = np.concatenate((prefix_dislocations, np.zeros(2)))
    base = propagate_corrected(config, angles, base_ds, rotations_deg)
    b = np.asarray(base.final_origin, dtype=float)

    probe_a = base_ds.copy()
    probe_a[-2] = 1.0
    oa = np.asarray(
        propagate_corrected(config, angles, probe_a, rotations_deg).final_origin
    )

    probe_b = base_ds.copy()
    probe_b[-1] = 1.0
    ob = np.asarray(
        propagate_corrected(config, angles, probe_b, rotations_deg).final_origin
    )

    matrix = np.column_stack((oa - b, ob - b))
    cond = float(np.linalg.cond(matrix))
    solution = np.linalg.solve(matrix, -b)
    return float(solution[0]), float(solution[1]), cond


def sample_closed_deformation(
    config: RingConfig,
    angles: RingAngles,
    seed: int | None = None,
    *,
    bounds: DeformationBounds | None = None,
    max_attempts: int = 10_000,
    max_condition_number: float = 1e8,
) -> RingDeformation:
    """Sample 2N-3 free DoFs and solve the three ring-closure DoFs."""
    bounds = bounds or DeformationBounds()
    rng = np.random.default_rng(seed)
    n = len(_transition_order(angles))

    for attempt in range(1, max_attempts + 1):
        prefix_d = np.array(
            [
                _bounded_normal(rng, bounds.max_abs_dislocation_m)
                for _ in range(n - 2)
            ],
            dtype=float,
        )
        prefix_phi = np.array(
            [
                _bounded_normal(rng, bounds.max_abs_rotation_deg)
                for _ in range(n - 1)
            ],
            dtype=float,
        )

        # With either orientation sign, centre angles sum to 360 deg and Eq. 11
        # reduces to sum(phi)=0. Under the geometric convention this also means
        # the final K rigid transform has zero net rotation.
        final_phi = -float(np.sum(prefix_phi))
        if abs(final_phi) > bounds.max_abs_rotation_deg:
            continue
        phis = np.concatenate((prefix_phi, (final_phi,)))

        try:
            d_nm1, d_n, cond = _solve_last_two_dislocations(
                config, angles, prefix_d, phis
            )
        except np.linalg.LinAlgError:
            continue
        if not math.isfinite(cond) or cond > max_condition_number:
            continue
        if abs(d_nm1) > bounds.max_abs_dislocation_m:
            continue
        if abs(d_n) > bounds.max_abs_dislocation_m:
            continue

        ds = np.concatenate((prefix_d, (d_nm1, d_n)))
        result = propagate_corrected(config, angles, ds, phis, attempts=attempt)
        result.validate(bounds)
        return result

    raise RuntimeError(
        "could not sample a bounded closed ring deformation; "
        "increase max_attempts or revise deformation bounds"
    )
