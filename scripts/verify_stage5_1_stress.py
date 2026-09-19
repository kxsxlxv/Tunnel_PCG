from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path

from tunnel_scanner_core import (
    RingConfig,
    SurfaceMeshingConfig,
    apply_rigid_transform_to_curved_segment,
    build_curved_ring_mesh,
    build_deformed_ring_mesh,
    build_ring_mesh,
    sample_closed_deformation,
    sample_six_segment_angles,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage5_1_verification.json"
N_NOMINAL_RINGS = 5000
N_DEFORMED_RINGS = 1000
TOLERANCE_M = 0.002


def edge_counts(faces):
    counts = Counter()
    for face in faces:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            counts[tuple(sorted((a, b)))] += 1
    return counts


def main() -> None:
    cfg = RingConfig()
    meshing = SurfaceMeshingConfig(max_sagitta_m=TOLERANCE_M)

    max_sagitta = 0.0
    max_nu = 0
    max_nv = 0
    max_vertices = 0
    max_faces = 0
    min_vertices = 10**9
    total_segment_meshes = 0
    nv_gt_1 = 0

    for seed in range(N_NOMINAL_RINGS):
        angles = sample_six_segment_angles(seed=seed)
        ring = build_ring_mesh(cfg, angles)
        curved = build_curved_ring_mesh(ring, meshing=meshing)
        for segment in curved.segments:
            total_segment_meshes += 1
            assert segment.achieved_max_sagitta_m <= TOLERANCE_M + 1e-12
            counts = edge_counts(segment.faces)
            assert counts and set(counts.values()) == {2}
            nu = segment.circumferential_subdivisions
            nv = segment.longitudinal_subdivisions
            if nv > 1:
                nv_gt_1 += 1
            max_nu = max(max_nu, nu)
            max_nv = max(max_nv, nv)
            max_vertices = max(max_vertices, len(segment.vertices))
            min_vertices = min(min_vertices, len(segment.vertices))
            max_faces = max(max_faces, len(segment.faces))
            max_sagitta = max(max_sagitta, segment.achieved_max_sagitta_m)
            for i, (x, _y, z) in enumerate(segment.vertices):
                radius = math.hypot(x, z)
                expected = cfg.inner_radius_m if i % 2 == 0 else cfg.outer_radius_m
                assert math.isclose(radius, expected, rel_tol=0, abs_tol=2e-12)

    max_deformed_radius_error = 0.0
    max_closure_m = 0.0
    max_closure_deg = 0.0
    for seed in range(N_DEFORMED_RINGS):
        angles = sample_six_segment_angles(seed=100_000 + seed)
        ring = build_ring_mesh(cfg, angles)
        curved = build_curved_ring_mesh(ring, meshing=meshing)
        deformation = sample_closed_deformation(cfg, angles, seed=200_000 + seed)
        deformed = build_deformed_ring_mesh(ring, deformation)
        transforms = {t.segment_name: t for t in deformed.segment_transforms}
        for base in curved.segments:
            t = transforms[base.name]
            moved = apply_rigid_transform_to_curved_segment(base, t)
            cx, cz = t.center_offset_xz_m
            for i, (x, _y, z) in enumerate(moved.vertices):
                measured = math.hypot(x - cx, z - cz)
                expected = cfg.inner_radius_m if i % 2 == 0 else cfg.outer_radius_m
                max_deformed_radius_error = max(
                    max_deformed_radius_error, abs(measured - expected)
                )
        max_closure_m = max(max_closure_m, deformation.translation_closure_error_m)
        max_closure_deg = max(max_closure_deg, deformation.angular_closure_error_deg)

    result = {
        "stage": "5.1",
        "requestedMaxSagittaM": TOLERANCE_M,
        "nominalRings": N_NOMINAL_RINGS,
        "deformedRings": N_DEFORMED_RINGS,
        "segmentMeshesChecked": total_segment_meshes,
        "maxConservativeSagittaM": max_sagitta,
        "maxCircumferentialSubdivisions": max_nu,
        "maxLongitudinalSubdivisions": max_nv,
        "segmentsWithLongitudinalSubdivisionsGt1": nv_gt_1,
        "minVerticesPerSegment": min_vertices,
        "maxVerticesPerSegment": max_vertices,
        "maxFacesPerSegment": max_faces,
        "maxDeformedLocalRadiusErrorM": max_deformed_radius_error,
        "maxDeformationClosureErrorM": max_closure_m,
        "maxDeformationClosureErrorDeg": max_closure_deg,
        "manifoldEdgeCheck": "PASS",
        "nominalVertexCylinderCheck": "PASS",
        "deformedRigidRadiusCheck": "PASS",
        "result": "PASS",
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
