from collections import Counter
import math

import numpy as np

from tunnel_scanner_core import RingConfig, build_ring_mesh, sample_six_segment_angles
from tunnel_scanner_core.bolts import (
    BoltConfig,
    BoltLayoutType,
    BoltPerturbationConfig,
    BoltPocketMode,
    build_bolt_head,
    build_bolt_placements,
    build_bolt_pocket,
    build_bolt_set,
    sample_bolt_config,
)


def _ring(seed=5812):
    cfg = RingConfig()
    return build_ring_mesh(cfg, sample_six_segment_angles(seed=seed))


def _edge_counts(faces):
    c = Counter()
    for face in faces:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            c[tuple(sorted((a, b)))] += 1
    return c


def _signed_volume(vertices, faces):
    vv = [np.asarray(v, dtype=float) for v in vertices]
    total = 0.0
    for face in faces:
        p0 = vv[face[0]]
        for i in range(1, len(face) - 1):
            total += float(np.dot(p0, np.cross(vv[face[i]], vv[face[i + 1]]))) / 6.0
    return total


def test_sampled_bolt_config_stays_inside_table3_bounds_for_1000_seeds():
    for seed in range(1000):
        sample_bolt_config(seed).validate_against_paper_bounds()


def test_type1_has_three_longitudinal_positions_per_segment():
    ring = _ring()
    cfg = BoltConfig()
    p = build_bolt_placements(ring, cfg, BoltLayoutType.TYPE1_CENTERED)
    assert len(p) == 18
    for segment in ring.segments:
        owned = [x for x in p if x.segment_name == segment.name]
        assert [x.y_m for x in owned] == [-0.4, 0.0, 0.4]


def test_type2_and_type3_positions_are_owned_by_declared_segments():
    ring = _ring()
    cfg = BoltConfig()
    for layout in (BoltLayoutType.TYPE2_LATERAL, BoltLayoutType.TYPE3_JOINT_ALIGNED):
        placements = build_bolt_placements(ring, cfg, layout)
        assert placements
        by_name = {s.name: s for s in ring.segments}
        for p in placements:
            s = by_name[p.segment_name]
            center = 0.25 * (
                s.angular_extent.front_start_deg
                + s.angular_extent.back_start_deg
                + s.angular_extent.front_end_deg
                + s.angular_extent.back_end_deg
            )
            a = p.alpha_deg + 360.0 * round((center - p.alpha_deg) / 360.0)
            lo = 0.5 * (s.angular_extent.front_start_deg + s.angular_extent.back_start_deg)
            hi = 0.5 * (s.angular_extent.front_end_deg + s.angular_extent.back_end_deg)
            assert min(lo, hi) - 1e-8 <= a <= max(lo, hi) + 1e-8


def test_nominal_pocket_frame_is_orthonormal_and_base_is_tangent_plane():
    ring = _ring()
    cfg = BoltConfig()
    placement = build_bolt_placements(ring, cfg, BoltLayoutType.TYPE1_CENTERED)[0]
    pocket = build_bolt_pocket(ring, cfg, placement)
    n = np.asarray(pocket.surface_normal)
    ex = np.asarray(pocket.tangent_x)
    ey = np.asarray(pocket.tangent_y)
    assert math.isclose(np.linalg.norm(n), 1.0, abs_tol=1e-12)
    assert math.isclose(np.linalg.norm(ex), 1.0, abs_tol=1e-12)
    assert math.isclose(np.linalg.norm(ey), 1.0, abs_tol=1e-12)
    assert abs(np.dot(n, ex)) < 1e-12
    assert abs(np.dot(n, ey)) < 1e-12
    assert abs(np.dot(ex, ey)) < 1e-12
    P = np.asarray(pocket.surface_point)
    for v in pocket.vertices[:4]:
        assert abs(float(np.dot(np.asarray(v) - P, n))) < 1e-12


def test_physical_pocket_apex_embeds_into_lining_while_printed_sign_goes_to_tunnel_void():
    ring = _ring()
    cfg = BoltConfig()
    placement = build_bolt_placements(ring, cfg, BoltLayoutType.TYPE1_CENTERED)[0]
    physical = build_bolt_pocket(ring, cfg, placement, mode=BoltPocketMode.PHYSICAL_EMBEDDED)
    printed = build_bolt_pocket(
        ring, cfg, placement, mode=BoltPocketMode.PAPER_PRINTED_INWARD_APEX
    )
    P = np.asarray(physical.surface_point)
    n = np.asarray(physical.surface_normal)
    dp = float(np.dot(np.asarray(physical.apex) - P, n))
    dq = float(np.dot(np.asarray(printed.apex) - P, n))
    assert dp > 0.10
    assert dq < -0.10
    assert dp < ring.config.thickness_m


def test_pocket_and_head_are_closed_positive_volume_manifolds():
    ring = _ring()
    cfg = BoltConfig()
    placement = build_bolt_placements(ring, cfg, BoltLayoutType.TYPE1_CENTERED)[0]
    pocket = build_bolt_pocket(ring, cfg, placement)
    head = build_bolt_head(cfg, pocket)
    for mesh in (pocket, head):
        counts = _edge_counts(mesh.faces)
        assert counts and set(counts.values()) == {2}
        assert _signed_volume(mesh.vertices, mesh.faces) > 0.0


def test_head_geometry_matches_algorithm_dimensions_and_basis():
    ring = _ring()
    cfg = BoltConfig()
    placement = build_bolt_placements(ring, cfg, BoltLayoutType.TYPE1_CENTERED)[0]
    pocket = build_bolt_pocket(ring, cfg, placement)
    head = build_bolt_head(cfg, pocket)
    n = np.asarray(head.normal)
    ex = np.asarray(head.basis_x)
    ey = np.asarray(head.basis_y)
    top_c = np.asarray(head.top_center)
    bot_c = np.asarray(head.bottom_center)
    assert math.isclose(np.linalg.norm(n), 1.0, abs_tol=1e-12)
    assert abs(np.dot(n, ex)) < 1e-12
    assert abs(np.dot(n, ey)) < 1e-12
    assert abs(np.dot(ex, ey)) < 1e-12
    assert math.isclose(np.linalg.norm(bot_c - top_c), cfg.head_thickness_m, abs_tol=1e-12)
    N = cfg.head_ring_vertices
    for v in head.vertices[:N]:
        dv = np.asarray(v) - top_c
        assert abs(np.dot(dv, n)) < 1e-12
        assert math.isclose(np.linalg.norm(dv), cfg.head_radius_m, abs_tol=1e-12)
    for v in head.vertices[N:]:
        dv = np.asarray(v) - bot_c
        assert abs(np.dot(dv, n)) < 1e-12
        assert math.isclose(np.linalg.norm(dv), cfg.embedded_head_radius_m, abs_tol=1e-12)


def test_zero_perturbation_bolt_set_is_deterministic():
    ring = _ring()
    cfg = BoltConfig()
    q = BoltPerturbationConfig(sigma_m=0.0, sigma_fraction=0.0)
    a = build_bolt_set(ring, cfg, BoltLayoutType.TYPE1_CENTERED, seed=1, perturbation_config=q)
    b = build_bolt_set(ring, cfg, BoltLayoutType.TYPE1_CENTERED, seed=999, perturbation_config=q)
    assert a == b


def test_perturbed_bolt_set_is_seed_deterministic_and_bounded():
    ring = _ring()
    cfg = BoltConfig()
    q = BoltPerturbationConfig()
    a = build_bolt_set(ring, cfg, BoltLayoutType.TYPE1_CENTERED, seed=42, perturbation_config=q)
    b = build_bolt_set(ring, cfg, BoltLayoutType.TYPE1_CENTERED, seed=42, perturbation_config=q)
    assert a == b
    for assembly in a.assemblies:
        p = assembly.pocket.perturbation
        assert abs(p.delta_x_m) <= 0.003 + 1e-15
        assert abs(p.delta_z_m) <= 0.003 + 1e-15
        assert abs(p.epsilon_depth) <= 0.003 + 1e-15
        assert abs(p.epsilon_lateral) <= 0.003 + 1e-15


def test_100_seed_bolt_geometry_stays_inside_lining_depth_and_is_manifold():
    ring = _ring()
    for seed in range(100):
        cfg = sample_bolt_config(seed)
        bolts = build_bolt_set(ring, cfg, BoltLayoutType.TYPE1_CENTERED, seed=seed)
        for assembly in bolts.assemblies:
            pocket = assembly.pocket
            P = np.asarray(pocket.surface_point)
            n = np.asarray(pocket.surface_normal)
            depth = float(np.dot(np.asarray(pocket.apex) - P, n))
            assert 0.0 < depth < ring.config.thickness_m
            for mesh in (pocket, assembly.head):
                counts = _edge_counts(mesh.faces)
                assert set(counts.values()) == {2}
                assert _signed_volume(mesh.vertices, mesh.faces) > 0.0



def test_boolean_cutter_moves_only_mouth_inward_and_remains_manifold():
    from tunnel_scanner_core.bolts import build_pocket_boolean_cutter

    ring = _ring()
    cfg = BoltConfig()
    placement = build_bolt_placements(ring, cfg, BoltLayoutType.TYPE1_CENTERED)[0]
    pocket = build_bolt_pocket(ring, cfg, placement)
    cutter = build_pocket_boolean_cutter(pocket, overlap_m=0.005)
    n = np.asarray(pocket.surface_normal)
    for i in range(4):
        dv = np.asarray(cutter.vertices[i]) - np.asarray(pocket.vertices[i])
        assert math.isclose(float(np.dot(dv, n)), -0.005, abs_tol=1e-12)
    assert np.allclose(cutter.vertices[4], pocket.vertices[4], atol=1e-12, rtol=0)
    assert set(_edge_counts(cutter.faces).values()) == {2}
    assert _signed_volume(cutter.vertices, cutter.faces) > 0.0
