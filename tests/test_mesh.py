import math

from tunnel_scanner_core import RingConfig, build_ring_mesh, sample_six_segment_angles


def _radius_xz(v):
    x, _, z = v
    return math.hypot(x, z)


def test_ring_has_six_hexahedral_segments():
    cfg = RingConfig(outer_radius_m=3.35, thickness_m=0.35, width_m=1.35)
    angles = sample_six_segment_angles(seed=42)
    ring = build_ring_mesh(cfg, angles)

    assert [s.name for s in ring.segments] == ["K", "B1", "A1", "A2", "A3", "B2"]
    for s in ring.segments:
        assert len(s.vertices) == 8
        assert len(s.faces) == 6
        assert all(len(face) == 4 for face in s.faces)


def test_segment_corner_radii_and_face_y_positions():
    cfg = RingConfig(outer_radius_m=3.35, thickness_m=0.35, width_m=1.35)
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=7))

    for s in ring.segments:
        for i in (0, 1, 2, 3):
            assert math.isclose(_radius_xz(s.vertices[i]), cfg.inner_radius_m, abs_tol=1e-9)
        for i in (4, 5, 6, 7):
            assert math.isclose(_radius_xz(s.vertices[i]), cfg.outer_radius_m, abs_tol=1e-9)
        for i in (0, 1, 4, 5):
            assert math.isclose(s.vertices[i][1], -cfg.width_m / 2, abs_tol=1e-12)
        for i in (2, 3, 6, 7):
            assert math.isclose(s.vertices[i][1], +cfg.width_m / 2, abs_tol=1e-12)


def test_adjacent_segments_share_angular_boundaries():
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=91))
    for left, right in zip(ring.segments[:-1], ring.segments[1:]):
        assert math.isclose(
            left.angular_extent.front_end_deg,
            right.angular_extent.front_start_deg,
            abs_tol=1e-9,
        )
        assert math.isclose(
            left.angular_extent.back_end_deg,
            right.angular_extent.back_start_deg,
            abs_tol=1e-9,
        )


def test_each_hexahedron_is_edge_manifold():
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=5812))
    for segment in ring.segments:
        counts = {}
        for face in segment.faces:
            for a, b in zip(face, face[1:] + face[:1]):
                edge = tuple(sorted((a, b)))
                counts[edge] = counts.get(edge, 0) + 1
        assert len(counts) == 12
        assert set(counts.values()) == {2}
