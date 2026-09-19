import math
import unittest

from tunnel_pcg_ref.alignment3d import (
    ProfileAnchor,
    Vec2,
    Vec3,
    chainage_xy,
    closed_parallel_transport_frames,
    grade_permille,
    interpolate_profile,
    parallel_transport_frames,
    project_point_to_polyline_xy,
    resample_polyline_xy,
    station_ugr_from_depth,
    vertical_curve_tangent_length_m,
)


class Alignment3DTests(unittest.TestCase):
    def test_chainage_and_resample(self):
        points = [Vec2(0, 0), Vec2(3, 4), Vec2(6, 4)]
        self.assertEqual(chainage_xy(points), [0, 5, 8])
        self.assertEqual(resample_polyline_xy(points, 2)[-1], points[-1])

    def test_project_station_to_track(self):
        s, d, q = project_point_to_polyline_xy(
            Vec2(2, 1), [Vec2(0, 0), Vec2(10, 0)]
        )
        self.assertAlmostEqual(s, 2)
        self.assertAlmostEqual(d, 1)
        self.assertEqual(q, Vec2(2, 0))

    def test_grade(self):
        self.assertAlmostEqual(
            grade_permille(Vec3(0, 0, 0), Vec3(100, 0, 3)), 30
        )

    def test_depth_datum_is_explicit(self):
        self.assertAlmostEqual(
            station_ugr_from_depth(150, 30, depth_datum="UGR"), 120
        )
        self.assertAlmostEqual(
            station_ugr_from_depth(150, 30, depth_datum="platform_top"),
            118.9,
        )
        with self.assertRaises(ValueError):
            station_ugr_from_depth(150, 30, depth_datum="unknown")

    def test_vertical_curve_tangent_length(self):
        length = vertical_curve_tangent_length_m(5000, 30, -30)
        self.assertTrue(149 < length < 151)

    def test_parallel_transport_frames(self):
        points = [
            Vec3(0, 0, 0),
            Vec3(10, 0, 0),
            Vec3(20, 5, 1),
            Vec3(30, 10, 2),
        ]
        frames = parallel_transport_frames(points)
        self.assertEqual(len(frames), 4)
        for frame in frames:
            self.assertAlmostEqual(frame.tangent.norm(), 1, places=10)
            self.assertAlmostEqual(frame.left.norm(), 1, places=10)
            self.assertAlmostEqual(frame.up.norm(), 1, places=10)
            self.assertAlmostEqual(frame.tangent.dot(frame.left), 0, places=10)
            self.assertAlmostEqual(frame.tangent.dot(frame.up), 0, places=10)


    def test_closed_loop_frames_close_roll(self):
        points = []
        n = 200
        for i in range(n):
            a = 2 * math.pi * i / n
            points.append(
                Vec3(
                    100 * math.cos(a),
                    100 * math.sin(a),
                    7 * math.sin(2 * a) + 2 * math.sin(3 * a),
                )
            )
        points.append(points[0])

        frames, residual = closed_parallel_transport_frames(points)
        self.assertEqual(len(frames), len(points))
        first, last = frames[0], frames[-1]
        self.assertLess((first.p - last.p).norm(), 1e-10)
        self.assertGreater(first.tangent.dot(last.tangent), 1 - 1e-12)
        self.assertGreater(first.left.dot(last.left), 1 - 1e-12)
        self.assertGreater(first.up.dot(last.up), 1 - 1e-12)
        self.assertTrue(math.isfinite(residual))

    def test_preliminary_profile_interpolation(self):
        anchors = [ProfileAnchor(0, 100), ProfileAnchor(100, 103)]
        self.assertEqual(
            interpolate_profile(anchors, [0, 50, 100]),
            [100, 101.5, 103],
        )


if __name__ == "__main__":
    unittest.main()
