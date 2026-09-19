import math
from itertools import combinations

import numpy as np

from tunnel_scanner_core import (
    AngleMode,
    RingConfig,
    build_deformed_ring_mesh,
    build_ring_mesh,
    derive_closure_k_transform,
    derive_segment_transforms,
    propagate_corrected,
    sample_closed_deformation,
    sample_six_segment_angles,
)


def _wrap_deg(x: float) -> float:
    return (x + 180.0) % 360.0 - 180.0


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


def test_zero_deformation_maps_every_segment_to_identity():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=1)
    ring = build_ring_mesh(cfg, angles)
    deformation = propagate_corrected(cfg, angles, [0.0] * 6, [0.0] * 6)
    transforms, _ = derive_segment_transforms(ring, deformation)

    for t in transforms:
        assert abs(t.rotation_deg) < 1e-12
        assert math.hypot(*t.center_offset_xz_m) < 1e-12

    deformed = build_deformed_ring_mesh(ring, deformation)
    for base, moved in zip(ring.segments, deformed.segments):
        assert np.allclose(base.vertices, moved.vertices, atol=1e-12, rtol=0)
    for joint in deformed.displacement_joints:
        assert max(joint.corner_separations_m) < 1e-12


def test_segment_rotation_is_cumulative_relative_rotation():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    ring = build_ring_mesh(cfg, angles)
    deformation = sample_closed_deformation(cfg, angles, seed=5812)
    transforms, _ = derive_segment_transforms(ring, deformation)
    by_name = {t.segment_name: t for t in transforms}

    cumulative = 0.0
    for step in deformation.steps[:-1]:
        cumulative += step.rotation_deg
        assert math.isclose(
            _wrap_deg(by_name[step.segment_name].rotation_deg - cumulative),
            0.0,
            abs_tol=1e-10,
        )


def test_relative_transform_rotation_recovers_each_phi_including_closure():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=42)
    ring = build_ring_mesh(cfg, angles)
    deformation = sample_closed_deformation(cfg, angles, seed=99)
    transforms, _ = derive_segment_transforms(ring, deformation)
    by_name = {t.segment_name: t for t in transforms}

    prev_rotation = by_name["K"].rotation_deg
    for step in deformation.steps:
        current_rotation = (
            0.0 if step.segment_name == "K" else by_name[step.segment_name].rotation_deg
        )
        relative = _wrap_deg(current_rotation - prev_rotation)
        assert math.isclose(relative, step.rotation_deg, abs_tol=1e-10)
        prev_rotation = current_rotation


def test_final_duplicate_k_transform_is_identity_over_1000_seeds():
    cfg = RingConfig()
    for seed in range(1000):
        angles = sample_six_segment_angles(seed=seed)
        ring = build_ring_mesh(cfg, angles)
        deformation = sample_closed_deformation(cfg, angles, seed=20_000 + seed)
        k = derive_closure_k_transform(ring, deformation)
        assert abs(k.rotation_deg) < 1e-9
        assert math.hypot(*k.center_offset_xz_m) < 1e-9


def test_pure_dislocation_produces_expected_uniform_joint_offset():
    cfg = RingConfig()
    # Literal mode removes front/back taper from this diagnostic interface, but
    # the result is actually independent of taper for a pure rigid translation.
    angles = sample_six_segment_angles(seed=3, mode=AngleMode.LITERAL_A_EQUAL)
    ring = build_ring_mesh(cfg, angles)
    ds = [0.004, 0, 0, 0, 0, 0]
    deformation = propagate_corrected(cfg, angles, ds, [0.0] * 6)
    deformed = build_deformed_ring_mesh(ring, deformation)
    j = deformed.displacement_joints[0]
    for separation in j.corner_separations_m:
        assert math.isclose(separation, 0.004, abs_tol=1e-10)


def test_pure_rotation_keeps_mean_radius_shared_pivot():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=4, mode=AngleMode.LITERAL_A_EQUAL)
    ring = build_ring_mesh(cfg, angles)
    phi = 0.2
    deformation = propagate_corrected(cfg, angles, [0.0] * 6, [phi, 0, 0, 0, 0, 0])
    transforms, delta = derive_segment_transforms(ring, deformation)
    by_name = {t.segment_name: t for t in transforms}
    b1 = by_name["B1"]

    # Undeformed B1 entry ray in Stage-1 coordinates.
    a = math.radians(b1.entry_alpha_deg)
    base_u = np.array((math.sin(a), math.cos(a)))
    mean_r = cfg.inner_radius_m + 0.5 * cfg.thickness_m
    base_pivot = mean_r * base_u

    # The K reference stays fixed, so its side of the d=0 interface is base_pivot.
    rot = np.array([
        [math.cos(math.radians(b1.rotation_deg)), -math.sin(math.radians(b1.rotation_deg))],
        [math.sin(math.radians(b1.rotation_deg)),  math.cos(math.radians(b1.rotation_deg))],
    ])
    moved_pivot = rot @ base_pivot + np.asarray(b1.center_offset_xz_m)
    assert np.allclose(moved_pivot, base_pivot, atol=1e-10, rtol=0)


def test_rigid_transform_preserves_all_segment_pairwise_distances():
    cfg = RingConfig()
    for seed in range(100):
        angles = sample_six_segment_angles(seed=seed)
        ring = build_ring_mesh(cfg, angles)
        deformation = sample_closed_deformation(cfg, angles, seed=1000 + seed)
        deformed = build_deformed_ring_mesh(ring, deformation)
        for base, moved in zip(ring.segments, deformed.segments):
            for i, j in combinations(range(8), 2):
                d0 = math.dist(base.vertices[i], base.vertices[j])
                d1 = math.dist(moved.vertices[i], moved.vertices[j])
                assert math.isclose(d0, d1, rel_tol=0, abs_tol=1e-10)


def test_joint_gap_mesh_is_closed_combinatorially_and_winding_normalized():
    cfg = RingConfig()
    for seed in range(200):
        angles = sample_six_segment_angles(seed=seed)
        ring = build_ring_mesh(cfg, angles)
        deformation = sample_closed_deformation(cfg, angles, seed=3000 + seed)
        deformed = build_deformed_ring_mesh(ring, deformation)
        assert len(deformed.displacement_joints) == 6
        for joint in deformed.displacement_joints:
            counts = _edge_counts(joint.faces)
            assert len(counts) == 12
            assert set(counts.values()) == {2}
            # Non-degenerate joints are normalized to positive signed volume.
            v = _signed_volume(joint.vertices, joint.faces)
            assert v >= -1e-14
