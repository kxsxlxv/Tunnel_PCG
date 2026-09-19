import math

import numpy as np

from tunnel_scanner_core import (
    JointConfig,
    RingConfig,
    build_circumferential_outer_collar,
    build_prescribed_joint_set,
    build_prescribed_radial_joints,
    build_ring_mesh,
    sample_joint_config,
    sample_six_segment_angles,
)


def _edge_counts(faces):
    counts = {}
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            e = tuple(sorted((a, b)))
            counts[e] = counts.get(e, 0) + 1
    return counts


def _signed_volume(vertices, faces):
    vv = [np.asarray(v, dtype=float) for v in vertices]
    total = 0.0
    for q in faces:
        for a, b, c in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
            total += float(np.dot(vv[a], np.cross(vv[b], vv[c]))) / 6.0
    return total


def _radius(v):
    return math.hypot(v[0], v[2])


def _circular_delta_deg(a, b):
    return abs((a - b + 180.0) % 360.0 - 180.0)


def test_joint_sampling_is_bounded_and_deterministic():
    a = sample_joint_config(seed=5812)
    b = sample_joint_config(seed=5812)
    assert a == b

    for seed in range(1000):
        j = sample_joint_config(seed=seed)
        assert 0.035 <= j.width_m <= 0.060
        assert 0.045 <= j.added_thickness_m <= 0.075


def test_joint_config_validation_against_paper_bounds():
    JointConfig(0.035, 0.045).validate_against_paper_bounds()
    JointConfig(0.060, 0.075).validate_against_paper_bounds()

    try:
        JointConfig(0.034, 0.060).validate_against_paper_bounds()
    except ValueError:
        pass
    else:
        raise AssertionError("out-of-bounds width should fail validation")


def test_radial_joint_literal_theta_formula_and_added_thickness():
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=5))
    jcfg = JointConfig(width_m=0.0475, added_thickness_m=0.060)
    joints = build_prescribed_radial_joints(ring, jcfg)

    assert len(joints) == 6
    for joint in joints:
        assert math.isclose(joint.base_radius_m, cfg.outer_radius_m, abs_tol=1e-14)
        assert math.isclose(
            joint.cap_radius_m,
            cfg.outer_radius_m + jcfg.added_thickness_m,
            abs_tol=1e-14,
        )
        assert math.isclose(
            joint.cap_radius_m - joint.base_radius_m,
            jcfg.added_thickness_m,
            abs_tol=1e-14,
        )

        # Section 2.2 literal invariant: theta = w / R at both explicit R_joi.
        assert math.isclose(
            math.radians(joint.base_angular_width_deg),
            jcfg.width_m / joint.base_radius_m,
            rel_tol=0,
            abs_tol=1e-15,
        )
        assert math.isclose(
            math.radians(joint.cap_angular_width_deg),
            jcfg.width_m / joint.cap_radius_m,
            rel_tol=0,
            abs_tol=1e-15,
        )
        assert math.isclose(joint.base_arc_width_m, jcfg.width_m, abs_tol=1e-14)
        assert math.isclose(joint.cap_arc_width_m, jcfg.width_m, abs_tol=1e-14)


def test_radial_joint_vertices_use_only_the_two_published_radii():
    cfg = RingConfig(outer_radius_m=3.6, thickness_m=0.35, width_m=1.4)
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=11))
    jcfg = sample_joint_config(seed=9)
    joints = build_prescribed_radial_joints(ring, jcfg)

    expected = [cfg.outer_radius_m] * 4 + [cfg.outer_radius_m + jcfg.added_thickness_m] * 4
    for joint in joints:
        actual = [_radius(v) for v in joint.vertices]
        assert np.allclose(actual, expected, atol=1e-12, rtol=0)
        ys = [v[1] for v in joint.vertices]
        assert set(round(y, 12) for y in ys) == {
            round(-0.5 * cfg.width_m, 12),
            round(+0.5 * cfg.width_m, 12),
        }


def test_radial_joint_interfaces_follow_segment_boundaries_including_wrap():
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=13))
    joints = build_prescribed_radial_joints(ring, JointConfig())

    by_name = {s.name: s for s in ring.segments}
    for joint in joints:
        prev = by_name[joint.previous_segment]
        nxt = by_name[joint.next_segment]
        assert _circular_delta_deg(
            joint.front_interface_alpha_deg,
            prev.angular_extent.front_end_deg,
        ) < 1e-10
        assert _circular_delta_deg(
            joint.front_interface_alpha_deg,
            nxt.angular_extent.front_start_deg,
        ) < 1e-10
        assert _circular_delta_deg(
            joint.back_interface_alpha_deg,
            prev.angular_extent.back_end_deg,
        ) < 1e-10
        assert _circular_delta_deg(
            joint.back_interface_alpha_deg,
            nxt.angular_extent.back_start_deg,
        ) < 1e-10


def test_radial_joint_meshes_are_closed_positive_manifolds():
    cfg = RingConfig()
    for seed in range(250):
        ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=seed))
        joints = build_prescribed_radial_joints(ring, sample_joint_config(seed=10_000 + seed))
        for joint in joints:
            counts = _edge_counts(joint.faces)
            assert len(counts) == 12
            assert set(counts.values()) == {2}
            assert _signed_volume(joint.vertices, joint.faces) > 1e-12


def test_radial_joint_ribs_do_not_intrude_inside_segment_outer_radius():
    cfg = RingConfig()
    for seed in range(100):
        ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=seed))
        joints = build_prescribed_radial_joints(ring, sample_joint_config(seed=1000 + seed))
        for joint in joints:
            assert min(_radius(v) for v in joint.vertices) >= cfg.outer_radius_m - 1e-12


def test_nominal_radial_joint_ribs_are_angularly_disjoint():
    cfg = RingConfig()
    for seed in range(100):
        ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=seed))
        jcfg = sample_joint_config(seed=3000 + seed)
        joints = build_prescribed_radial_joints(ring, jcfg)
        centres = [j.front_interface_alpha_deg % 360.0 for j in joints]
        half_width = 0.5 * max(j.base_angular_width_deg for j in joints)
        centres.sort()
        gaps = [
            (centres[(i + 1) % 6] - centres[i]) % 360.0
            for i in range(6)
        ]
        assert min(gaps) > 2.0 * half_width


def test_circumferential_outer_collar_has_expected_axial_width_and_radii():
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=23))
    jcfg = JointConfig(width_m=0.050, added_thickness_m=0.065)

    for side in ("front", "back"):
        pieces = build_circumferential_outer_collar(ring, jcfg, side=side)
        assert len(pieces) == 6
        for p in pieces:
            assert math.isclose(p.axial_width_m, jcfg.width_m, abs_tol=1e-14)
            radii = [_radius(v) for v in p.vertices]
            assert np.allclose(
                radii,
                [cfg.outer_radius_m] * 4
                + [cfg.outer_radius_m + jcfg.added_thickness_m] * 4,
                atol=1e-12,
                rtol=0,
            )
            counts = _edge_counts(p.faces)
            assert len(counts) == 12
            assert set(counts.values()) == {2}
            assert _signed_volume(p.vertices, p.faces) > 1e-12


def test_circumferential_pieces_tile_each_ring_face_once():
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=31))
    jcfg = JointConfig()
    front = build_circumferential_outer_collar(ring, jcfg, side="front")
    back = build_circumferential_outer_collar(ring, jcfg, side="back")

    assert math.isclose(
        sum(p.alpha_end_deg - p.alpha_start_deg for p in front),
        360.0,
        abs_tol=1e-10,
    )
    assert math.isclose(
        sum(p.alpha_end_deg - p.alpha_start_deg for p in back),
        360.0,
        abs_tol=1e-10,
    )


def test_joint_set_aggregate_counts():
    ring = build_ring_mesh(RingConfig(), sample_six_segment_angles(seed=41))
    joints = build_prescribed_joint_set(ring, JointConfig())
    assert len(joints.radial) == 6
    assert len(joints.circumferential_front) == 6
    assert len(joints.circumferential_back) == 6


def test_paper_bound_extremes_remain_non_degenerate_at_radius_extremes():
    cases = [
        (2.0, JointConfig(width_m=0.060, added_thickness_m=0.075)),
        (2.0, JointConfig(width_m=0.035, added_thickness_m=0.045)),
        (5.0, JointConfig(width_m=0.060, added_thickness_m=0.075)),
        (5.0, JointConfig(width_m=0.035, added_thickness_m=0.045)),
    ]
    for R, jcfg in cases:
        cfg = RingConfig.from_outer_radius_and_thickness(R, 0.35)
        ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=int(R * 100)))
        joints = build_prescribed_radial_joints(ring, jcfg)
        for j in joints:
            assert _signed_volume(j.vertices, j.faces) > 1e-12
            assert math.isclose(j.base_arc_width_m, jcfg.width_m, abs_tol=1e-14)
            assert math.isclose(j.cap_arc_width_m, jcfg.width_m, abs_tol=1e-14)
