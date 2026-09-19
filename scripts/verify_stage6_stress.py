from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path

import numpy as np

from tunnel_scanner_core import RingConfig, build_ring_mesh, sample_six_segment_angles
from tunnel_scanner_core.bolts import (
    BoltLayoutType,
    build_bolt_placements,
    build_bolt_set,
    build_pocket_boolean_cutter,
    sample_bolt_config,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage6_verification.json"
N_RINGS = 1000
N_FULL_TOPOLOGY_RINGS = 100


def edge_counts(faces):
    counts = Counter()
    for face in faces:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            counts[tuple(sorted((a, b)))] += 1
    return counts


def signed_volume(vertices, faces):
    vv = [np.asarray(v, dtype=float) for v in vertices]
    total = 0.0
    for face in faces:
        p0 = vv[face[0]]
        for i in range(1, len(face) - 1):
            total += float(np.dot(p0, np.cross(vv[face[i]], vv[face[i + 1]]))) / 6.0
    return total


def main() -> None:
    ring_cfg = RingConfig()
    total_assemblies = 0
    max_pocket_depth_m = 0.0
    max_head_radius_m = 0.0
    max_head_outer_radius_m = 0.0
    max_mouth_radius_minus_inner_m = -1e9
    min_mouth_overlap_m = 1e9
    max_perturbation_m = 0.0
    layout_counts = {layout.value: [] for layout in BoltLayoutType}

    for seed in range(N_RINGS):
        ring = build_ring_mesh(ring_cfg, sample_six_segment_angles(seed=seed))
        bolt_cfg = sample_bolt_config(seed)

        for layout in BoltLayoutType:
            placements = build_bolt_placements(ring, bolt_cfg, layout)
            layout_counts[layout.value].append(len(placements))

        bolts = build_bolt_set(
            ring,
            bolt_cfg,
            BoltLayoutType.TYPE1_CENTERED,
            seed=100_000 + seed,
        )
        total_assemblies += len(bolts.assemblies)
        for assembly in bolts.assemblies:
            pocket = assembly.pocket
            head = assembly.head
            n = np.asarray(pocket.surface_normal)
            P = np.asarray(pocket.surface_point)
            depth = float(np.dot(np.asarray(pocket.apex) - P, n))
            assert 0.0 < depth < ring.config.thickness_m
            max_pocket_depth_m = max(max_pocket_depth_m, depth)

            q = pocket.perturbation
            max_perturbation_m = max(
                max_perturbation_m,
                abs(q.delta_x_m),
                abs(q.delta_z_m),
            )

            if seed < N_FULL_TOPOLOGY_RINGS:
                for mesh in (pocket, head):
                    counts = edge_counts(mesh.faces)
                    assert counts and set(counts.values()) == {2}
                    assert signed_volume(mesh.vertices, mesh.faces) > 0.0

            for v in head.vertices:
                radius = math.hypot(v[0], v[2])
                max_head_outer_radius_m = max(max_head_outer_radius_m, radius)
                assert radius < ring.config.outer_radius_m
            max_head_radius_m = max(max_head_radius_m, head.top_radius_m)

            cutter = build_pocket_boolean_cutter(pocket, overlap_m=0.005)
            if seed < N_FULL_TOPOLOGY_RINGS:
                assert set(edge_counts(cutter.faces).values()) == {2}
                assert signed_volume(cutter.vertices, cutter.faces) > 0.0
            for v in cutter.vertices[:4]:
                dr = math.hypot(v[0], v[2]) - ring.config.inner_radius_m
                max_mouth_radius_minus_inner_m = max(max_mouth_radius_minus_inner_m, dr)
                min_mouth_overlap_m = min(min_mouth_overlap_m, -dr)
                assert dr < 0.0

    result = {
        "stage": 6,
        "rings": N_RINGS,
        "fullTopologyRings": N_FULL_TOPOLOGY_RINGS,
        "type1AssembliesChecked": total_assemblies,
        "layoutPlacementCounts": {
            key: {
                "min": min(values),
                "max": max(values),
                "unique": sorted(set(values)),
            }
            for key, values in layout_counts.items()
        },
        "maxPocketDepthM": max_pocket_depth_m,
        "liningThicknessM": ring_cfg.thickness_m,
        "maxHeadRadiusM": max_head_radius_m,
        "maxHeadVertexRadiusFromTunnelAxisM": max_head_outer_radius_m,
        "outerLiningRadiusM": ring_cfg.outer_radius_m,
        "maxBooleanMouthRadiusMinusInnerM": max_mouth_radius_minus_inner_m,
        "minimumBooleanMouthOverlapIntoTunnelVoidM": min_mouth_overlap_m,
        "maxMetricPocketPerturbationM": max_perturbation_m,
        "manifoldAndPositiveVolume": "PASS",
        "headInsideLining": "PASS",
        "booleanMouthOverlap": "PASS",
        "result": "PASS",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
