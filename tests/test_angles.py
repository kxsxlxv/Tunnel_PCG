import math

from tunnel_scanner_core import (
    AngleMode,
    AngleBounds,
    angular_extents,
    sample_six_segment_angles,
)


def test_equation_consistent_samples_close_and_satisfy_constraints():
    bounds = AngleBounds()
    for seed in range(1000):
        ring = sample_six_segment_angles(seed=seed, mode=AngleMode.EQUATION_CONSISTENT)
        ring.validate(bounds)
        assert math.isclose(ring.front_total_deg, 360.0, abs_tol=1e-8)
        assert math.isclose(ring.back_total_deg, 360.0, abs_tol=1e-8)
        assert math.isclose(ring.center_total_deg, 360.0, abs_tol=1e-8)

        k = ring.by_name("K")
        for bname in ("B1", "B2"):
            b = ring.by_name(bname)
            assert math.isclose(
                k.front_deg + b.front_deg,
                k.back_deg + b.back_deg,
                abs_tol=1e-8,
            )


def test_literal_mode_forces_equal_front_back_faces():
    for seed in range(100):
        ring = sample_six_segment_angles(seed=seed, mode=AngleMode.LITERAL_A_EQUAL)
        for segment in ring.segments:
            assert math.isclose(segment.front_deg, segment.back_deg, abs_tol=1e-12)


def test_sampling_is_deterministic():
    a = sample_six_segment_angles(seed=5812)
    b = sample_six_segment_angles(seed=5812)
    assert a == b


def test_cyclic_extents_are_continuous_and_closed():
    ring = sample_six_segment_angles(seed=17)
    ex = angular_extents(ring)

    for left, right in zip(ex[:-1], ex[1:]):
        assert math.isclose(left.front_end_deg, right.front_start_deg, abs_tol=1e-9)
        assert math.isclose(left.back_end_deg, right.back_start_deg, abs_tol=1e-9)

    k = ring.by_name("K")
    assert math.isclose(ex[0].front_start_deg, -0.5 * k.front_deg, abs_tol=1e-9)
    assert math.isclose(ex[-1].front_end_deg, ex[0].front_start_deg + 360.0, abs_tol=1e-9)
    assert math.isclose(ex[-1].back_end_deg, ex[0].back_start_deg + 360.0, abs_tol=1e-9)


def test_equation_consistent_mode_exposes_paper_prose_ambiguity():
    # Find at least one deterministic sample with non-zero K taper. Under Eqs. (3)-(4),
    # that necessarily creates a small A front/back difference in our symmetric solution.
    ring = sample_six_segment_angles(seed=5812, mode=AngleMode.EQUATION_CONSISTENT)
    k = ring.by_name("K")
    assert not math.isclose(k.front_deg, k.back_deg, abs_tol=1e-6)
    a = ring.by_name("A1")
    assert not math.isclose(a.front_deg, a.back_deg, abs_tol=1e-6)
