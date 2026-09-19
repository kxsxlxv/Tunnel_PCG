import math

import numpy as np

from tunnel_scanner_core import RingConfig, sample_six_segment_angles
from tunnel_scanner_core.deformation import (
    DeformationBounds,
    KinematicIndexing,
    propagate_as_printed,
    propagate_corrected,
    sample_closed_deformation,
)


def test_zero_deformation_closes_exactly():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    result = propagate_corrected(cfg, angles, [0.0] * 6, [0.0] * 6)
    assert result.translation_closure_error_m < 1e-12
    assert abs(result.angular_closure_error_deg) < 1e-12
    assert math.isclose(result.final_theta_deg, -180.0, abs_tol=1e-12)


def test_transition_order_returns_to_k():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=2)
    result = propagate_corrected(cfg, angles, [0.0] * 6, [0.0] * 6)
    assert [s.segment_name for s in result.steps] == [
        "B1", "A1", "A2", "A3", "B2", "K"
    ]


def test_corrected_sampling_is_deterministic():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=17)
    a = sample_closed_deformation(cfg, angles, seed=1234)
    b = sample_closed_deformation(cfg, angles, seed=1234)
    assert a == b


def test_closed_sampler_satisfies_eq11_and_bounds_over_1000_seeds():
    cfg = RingConfig()
    bounds = DeformationBounds()
    for seed in range(1000):
        angles = sample_six_segment_angles(seed=seed)
        result = sample_closed_deformation(cfg, angles, seed=10_000 + seed)
        result.validate(bounds)
        assert result.indexing is KinematicIndexing.CORRECTED_SEGMENT_INDEXED
        assert result.translation_closure_error_m < 1e-9
        assert abs(result.angular_closure_error_deg) < 1e-9
        assert max(abs(d) for d in result.dislocations_m) <= 0.010 + 1e-12
        assert max(abs(p) for p in result.rotations_deg) <= 0.3 + 1e-12


def test_final_rotation_is_exact_orientation_closure_solution():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=22)
    result = sample_closed_deformation(cfg, angles, seed=44)
    assert math.isclose(
        result.rotations_deg[-1],
        -sum(result.rotations_deg[:-1]),
        abs_tol=1e-12,
    )


def test_translation_is_affine_in_dislocation_when_rotations_fixed():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=13)
    phis = [0.1, -0.08, 0.03, 0.02, -0.04, -0.03]
    zero = np.asarray(
        propagate_corrected(cfg, angles, [0.0] * 6, phis).final_origin
    )
    da = np.asarray(
        propagate_corrected(cfg, angles, [0, 0, 0, 0, 1.0, 0], phis).final_origin
    ) - zero
    db = np.asarray(
        propagate_corrected(cfg, angles, [0, 0, 0, 0, 0, 1.0], phis).final_origin
    ) - zero

    x, y = 0.004, -0.003
    mixed = np.asarray(
        propagate_corrected(cfg, angles, [0, 0, 0, 0, x, y], phis).final_origin
    )
    expected = zero + x * da + y * db
    assert np.allclose(mixed, expected, atol=1e-12, rtol=0)


def test_as_printed_path_exposes_indexing_problem_in_api():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=3)
    result = propagate_as_printed(cfg, angles, [0.0] * 6, [0.0] * 6)
    assert result.indexing is KinematicIndexing.AS_PRINTED_PREVIOUS_INDEX
    # Literal equations consume only indices 0..N-1.  d_N and phi_N do not
    # exist in this API, documenting why the prose closure unknowns cannot be
    # used without an index correction.
    assert len(result.dislocations_m) == 6


def test_geometric_theta_update_uses_same_rotation_sign_as_eq9():
    from tunnel_scanner_core.deformation import propagate_index_corrected_printed_sign

    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=31)
    phis = [0.12, -0.04, 0.01, -0.02, -0.03, -0.04]
    ds = [0.0] * 6
    geometric = propagate_corrected(cfg, angles, ds, phis)
    printed_sign = propagate_index_corrected_printed_sign(cfg, angles, ds, phis)

    # Eq. (9) rotates the target centre-to-joint radius by +phi. Therefore the
    # next interface direction must accumulate +phi before subtracting the
    # segment span. The two conventions diverge immediately for nonzero phi.
    first_alpha = angles.by_name("B1").center_deg
    assert math.isclose(
        geometric.steps[0].theta_after_deg,
        180.0 - first_alpha + phis[0],
        abs_tol=1e-12,
    )
    assert math.isclose(
        printed_sign.steps[0].theta_after_deg,
        180.0 - first_alpha - phis[0],
        abs_tol=1e-12,
    )
