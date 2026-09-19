import math
import pytest

from tunnel_scanner_core import RingConfig


def test_empirical_width_relation():
    cfg = RingConfig.from_outer_radius_and_thickness(3.35, 0.35)
    expected = (20.38 * math.exp(-1.88 * 3.35) + 2.94) * 0.35
    assert math.isclose(cfg.width_m, expected, rel_tol=0, abs_tol=1e-12)


def test_inner_radius():
    cfg = RingConfig(outer_radius_m=3.35, thickness_m=0.35, width_m=1.3)
    assert math.isclose(cfg.inner_radius_m, 3.0)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"outer_radius_m": 0.0, "thickness_m": 0.35, "width_m": 1.3},
        {"outer_radius_m": 3.0, "thickness_m": 0.0, "width_m": 1.3},
        {"outer_radius_m": 3.0, "thickness_m": 3.0, "width_m": 1.3},
        {"outer_radius_m": 3.0, "thickness_m": 0.35, "width_m": 0.0},
    ],
)
def test_invalid_config_rejected(kwargs):
    with pytest.raises(ValueError):
        RingConfig(**kwargs)
