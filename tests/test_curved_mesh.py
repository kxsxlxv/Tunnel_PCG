from collections import Counter
import math

import numpy as np

from tunnel_scanner_core import (
    AngleMode,
    RingConfig,
    SurfaceMeshingConfig,
    build_curved_ring_mesh,
    build_curved_segment_mesh,
    build_deformed_ring_mesh,
    build_ring_mesh,
    sample_closed_deformation,
    sample_six_segment_angles,
)
from tunnel_scanner_core.curved_mesh import (
    max_angular_step_deg,
    required_grid_subdivisions,
    required_subdivisions,
    sagitta_m,
)
from tunnel_scanner_core.scene import build_deformed_scene_package, build_nominal_scene_package
from tunnel_scanner_core.joints import build_prescribed_joint_set, sample_joint_config


def _edge_counts(faces):
    counts = Counter()
    for face in faces:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            counts[tuple(sorted((a, b)))] += 1
    return counts


def _normal(a, b, c):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    c = np.asarray(c, dtype=float)
    return np.cross(b - a, c - a)


def test_max_angular_step_and_sagitta_are_inverse():
    r = 3.35
    for eps in (0.010, 0.005, 0.002, 0.001):
        step = max_angular_step_deg(r, eps)
        assert math.isclose(sagitta_m(r, step), eps, rel_tol=0, abs_tol=1e-12)


def test_expected_subdivision_counts_for_67_5_degree_segment():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=1, mode=AngleMode.LITERAL_A_EQUAL)
    ring = build_ring_mesh(cfg, angles)
    a = next(s for s in ring.segments if s.name == "A1")
    for eps in (0.010, 0.005, 0.002, 0.001):
        m = SurfaceMeshingConfig(max_sagitta_m=eps)
        n = required_subdivisions(cfg.outer_radius_m, a.angular_extent, m)
        step = max(
            abs(a.angular_extent.front_span_deg),
            abs(a.angular_extent.back_span_deg),
        ) / n
        assert sagitta_m(cfg.outer_radius_m, step) <= eps + 1e-12
        if n > 1:
            previous_step = max(
                abs(a.angular_extent.front_span_deg),
                abs(a.angular_extent.back_span_deg),
            ) / (n - 1)
            assert sagitta_m(cfg.outer_radius_m, previous_step) > eps - 1e-12


def test_curved_segment_end_stations_reproduce_stage1_corners():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    ring = build_ring_mesh(cfg, angles)
    for coarse in ring.segments:
        curved = build_curved_segment_mesh(
            coarse,
            inner_radius_m=cfg.inner_radius_m,
            outer_radius_m=cfg.outer_radius_m,
            width_m=cfg.width_m,
            meshing=SurfaceMeshingConfig(max_sagitta_m=0.002),
        )
        nu = curved.circumferential_subdivisions
        nv = curved.longitudinal_subdivisions

        def idx(iv, iu, layer):
            return 2 * (iv * (nu + 1) + iu) + layer

        expected_pairs = (
            (curved.vertices[idx(0, 0, 0)], coarse.vertices[0]),
            (curved.vertices[idx(0, nu, 0)], coarse.vertices[1]),
            (curved.vertices[idx(nv, 0, 0)], coarse.vertices[2]),
            (curved.vertices[idx(nv, nu, 0)], coarse.vertices[3]),
            (curved.vertices[idx(0, 0, 1)], coarse.vertices[4]),
            (curved.vertices[idx(0, nu, 1)], coarse.vertices[5]),
            (curved.vertices[idx(nv, 0, 1)], coarse.vertices[6]),
            (curved.vertices[idx(nv, nu, 1)], coarse.vertices[7]),
        )
        for got, expected in expected_pairs:
            assert np.allclose(got, expected, atol=1e-12, rtol=0)


def test_curved_mesh_is_closed_manifold_for_100_seeds():
    cfg = RingConfig()
    meshing = SurfaceMeshingConfig(max_sagitta_m=0.002)
    for seed in range(100):
        ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=seed))
        curved = build_curved_ring_mesh(ring, meshing=meshing)
        for segment in curved.segments:
            counts = _edge_counts(segment.faces)
            assert counts
            assert set(counts.values()) == {2}
            assert segment.achieved_max_sagitta_m <= meshing.max_sagitta_m + 1e-12
            nu = segment.circumferential_subdivisions
            nv = segment.longitudinal_subdivisions
            assert len(segment.vertices) == 2 * (nu + 1) * (nv + 1)
            assert len(segment.faces) == 2 * nu * nv + 2 * nu + 2 * nv


def test_curved_surface_normals_point_in_expected_directions():
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=7, mode=AngleMode.LITERAL_A_EQUAL))
    curved = build_curved_ring_mesh(ring, meshing=SurfaceMeshingConfig(max_sagitta_m=0.002))
    s = curved.segment_by_name("K")
    nu = s.circumferential_subdivisions
    nv = s.longitudinal_subdivisions
    intrados, extrados = s.faces[:2]
    front = s.faces[2 * nu * nv]
    back = s.faces[2 * nu * nv + 1]
    for face, expectation in (
        (intrados, "in"),
        (extrados, "out"),
        (front, "front"),
        (back, "back"),
    ):
        n = _normal(s.vertices[face[0]], s.vertices[face[1]], s.vertices[face[2]])
        centroid = np.mean([s.vertices[i] for i in face], axis=0)
        radial = np.array((centroid[0], 0.0, centroid[2]))
        if expectation == "in":
            assert float(np.dot(n, radial)) < 0
        elif expectation == "out":
            assert float(np.dot(n, radial)) > 0
        elif expectation == "front":
            assert n[1] < 0
        else:
            assert n[1] > 0


def test_default_scene_packages_use_curved_segment_geometry():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    ring = build_ring_mesh(cfg, angles)
    joints = build_prescribed_joint_set(ring, sample_joint_config(seed=5812))
    nominal = build_nominal_scene_package(ring, joints, ring_id=12)
    for obj in nominal.objects_of_type("lining_segment"):
        assert len(obj.vertices) > 8
        assert obj.reconstruction == "stage5_1_adaptive_cylindrical_surface"
        assert obj.custom_properties["surfaceToleranceM"] == 0.002
        assert obj.custom_properties["surfaceAchievedMaxSagittaM"] <= 0.002 + 1e-12
        assert obj.custom_properties["surfaceSubdivisions"] >= 1

    deformation = sample_closed_deformation(cfg, angles, seed=5812)
    deformed = build_deformed_ring_mesh(ring, deformation)
    pkg = build_deformed_scene_package(deformed, ring_id=12)
    for obj in pkg.objects_of_type("lining_segment"):
        assert len(obj.vertices) > 8
        assert obj.reconstruction == "stage5_1_curved_surface_plus_stage3_rigid_transform"
        assert obj.custom_properties["surfaceToleranceM"] == 0.002


def test_tighter_tolerance_never_reduces_subdivision_count():
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=91))
    tolerances = (0.010, 0.005, 0.002, 0.001, 0.0005)
    previous = None
    for eps in tolerances:
        curved = build_curved_ring_mesh(ring, meshing=SurfaceMeshingConfig(max_sagitta_m=eps))
        counts = tuple(s.subdivisions for s in curved.segments)
        if previous is not None:
            assert all(n >= p for n, p in zip(counts, previous))
        previous = counts


def test_default_nominal_scene_curves_broad_circumferential_collar_pieces():
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=5812)
    ring = build_ring_mesh(cfg, angles)
    joints = build_prescribed_joint_set(ring, sample_joint_config(seed=5812))
    package = build_nominal_scene_package(ring, joints, ring_id=12)
    collars = package.objects_of_type("prescribed_circumferential_joint")
    assert len(collars) == 6
    for obj in collars:
        assert len(obj.vertices) > 8
        assert "stage5_1_curved_surface" in obj.reconstruction
        assert obj.custom_properties["surfaceAchievedMaxSagittaM"] <= 0.002 + 1e-12


def test_deformed_curved_vertices_preserve_exact_local_radii_over_100_seeds():
    from tunnel_scanner_core.curved_mesh import apply_rigid_transform_to_curved_segment

    cfg = RingConfig()
    meshing = SurfaceMeshingConfig(max_sagitta_m=0.002)
    for seed in range(100):
        angles = sample_six_segment_angles(seed=seed)
        ring = build_ring_mesh(cfg, angles)
        curved = build_curved_ring_mesh(ring, meshing=meshing)
        deformation = sample_closed_deformation(cfg, angles, seed=10_000 + seed)
        deformed = build_deformed_ring_mesh(ring, deformation)
        transforms = {t.segment_name: t for t in deformed.segment_transforms}
        for base in curved.segments:
            t = transforms[base.name]
            moved = apply_rigid_transform_to_curved_segment(base, t)
            cx, cz = t.center_offset_xz_m
            for i, (x, _y, z) in enumerate(moved.vertices):
                radius = math.hypot(x - cx, z - cz)
                expected = cfg.inner_radius_m if i % 2 == 0 else cfg.outer_radius_m
                assert math.isclose(radius, expected, rel_tol=0, abs_tol=2e-12)
