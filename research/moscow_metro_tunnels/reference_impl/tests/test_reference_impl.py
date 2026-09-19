import math
import unittest

from tunnel_pcg_ref.clearances import OM_UPPER_RIGHT, cmk, lower_om_inside_curve_extra_m
from tunnel_pcg_ref.contact_rail import nominal_contact_rail, rule_side
from tunnel_pcg_ref.events import RouteEvent, deterministic_seed, filter_by_override_events, periodic_positions
from tunnel_pcg_ref.rail_profiles import R50, R65, validation_metrics
from tunnel_pcg_ref.rings import ring_sequence
from tunnel_pcg_ref.track import cant_angle, gauge_for_radius


class TrackTests(unittest.TestCase):
    def test_gauge_boundaries(self):
        self.assertEqual(gauge_for_radius(None), 1.520)
        self.assertEqual(gauge_for_radius(1200), 1.520)
        self.assertEqual(gauge_for_radius(1199.9), 1.524)
        self.assertEqual(gauge_for_radius(600), 1.530)
        self.assertEqual(gauge_for_radius(400), 1.535)
        self.assertEqual(gauge_for_radius(125), 1.540)
        self.assertEqual(gauge_for_radius(100), 1.544)

    def test_cant_and_cmk_shift(self):
        a = cant_angle(0.120, 1.520)
        env = cmk("R65", cant_angle_rad=a, curve_direction="left")
        self.assertAlmostEqual(env.center_y_m, 1.670 * math.tan(a), places=12)
        self.assertAlmostEqual(env.radius_m, 2.450)


class ContactRailTests(unittest.TestCase):
    def test_nominal(self):
        p = nominal_contact_rail(1.520, "left")
        self.assertAlmostEqual(p.axis_y_m, 1.450)
        self.assertAlmostEqual(p.working_surface_z_m, 0.160)

    def test_tight_curve_outside(self):
        self.assertEqual(rule_side(curve_direction="left", radius_m=150), "right")
        self.assertEqual(rule_side(curve_direction="right", radius_m=150), "left")
        self.assertEqual(rule_side(curve_direction="left", radius_m=250), "left")


class ClearanceTests(unittest.TestCase):
    def test_cmk_center(self):
        self.assertAlmostEqual(cmk("R50").center_z_m, 1.700)
        self.assertAlmostEqual(cmk("R65").center_z_m, 1.670)

    def test_om_upper_reference_points(self):
        expected = [(1.480, .550), (1.480, .740), (1.620, 3.280), (1.325, 3.625), (1.005, 3.745), (.355, 3.780), (0, 3.780)]
        self.assertEqual([(p.x, p.z) for p in OM_UPPER_RIGHT], expected)

    def test_lower_om_tight_curve_extra(self):
        self.assertEqual(lower_om_inside_curve_extra_m(90), .020)
        self.assertEqual(lower_om_inside_curve_extra_m(110), .016)
        self.assertEqual(lower_om_inside_curve_extra_m(140), .011)
        self.assertEqual(lower_om_inside_curve_extra_m(180), .006)
        self.assertEqual(lower_om_inside_curve_extra_m(200), 0.0)


class RailProfileTests(unittest.TestCase):
    def _check(self, spec):
        m = validation_metrics(spec)
        self.assertLess(abs(m["height_m"] - spec.H), 1e-7)
        self.assertLess(abs(m["base_width_m"] - spec.base_width), 1e-7)
        self.assertLess(abs(m["head_width_m"] - spec.nominal_head_width), 3e-5)  # 0.03 mm
        self.assertLess(abs(m["area_rel_error"]), 0.003)  # reconstruction QA, not manufacturing acceptance
        self.assertLess(abs(m["centroid_z_error_m"]), 0.00025)

    def test_r50(self): self._check(R50)
    def test_r65(self): self._check(R65)


class PlacementTests(unittest.TestCase):
    def test_determinism_and_override(self):
        seed = deterministic_seed("demo", "lights", "T1")
        a = periodic_positions(0, 100, 9, seed=seed, jitter=.05)
        b = periodic_positions(0, 100, 9, seed=seed, jitter=.05)
        self.assertEqual(a, b)
        e = RouteEvent(20, 40, "SWITCH_CHAMBER")
        self.assertTrue(all(not (20 <= s <= 40) for s in filter_by_override_events(a, [e])))

    def test_rings(self):
        r = ring_sequence(0, 10, 1.0)
        self.assertEqual([x.s_center_m for x in r], [0.5,1.5,2.5,3.5,4.5,5.5,6.5,7.5,8.5,9.5])


if __name__ == "__main__":
    unittest.main()
