from __future__ import annotations

from collections import Counter
import json
import math
from pathlib import Path

import numpy as np

from tunnel_scanner_core import (
    AncillarySamplingPolicy,
    LabelPolicy,
    RingConfig,
    TunnelAssemblyConfig,
    build_ancillary_set,
    build_procedural_nominal_tunnel,
    sample_ancillary_config,
)
from tunnel_scanner_core.scene_io import scene_package_from_dict, scene_package_to_dict


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage8_verification.json"
SAMPLED_CONFIGS = 1000
FULL_SCENES = 100
JSON_ROUNDTRIPS = 20


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
    r = ring_cfg.inner_radius_m
    max_walkway_depth = 0.0
    max_rail_extent_radius = 0.0
    max_tube_vertex_radius = 0.0
    walkway_sides = set()
    mesh_count = 0

    for seed in range(SAMPLED_CONFIGS):
        cfg = sample_ancillary_config(
            r,
            seed=seed,
            policy=AncillarySamplingPolicy.PUBLISHED_UNIFORM,
        )
        cfg.validate_against_table4(r)
        cfg.validate_physical_clearance(r)
        walkway_sides.add(cfg.walkway_side.value)
        max_walkway_depth = max(max_walkway_depth, cfg.walkway_depth_m)
        ancillary = build_ancillary_set(
            inner_radius_m=r,
            length_m=ring_cfg.width_m,
            config=cfg,
        )
        assert len(ancillary.meshes) == 10
        for mesh in ancillary.meshes:
            mesh_count += 1
            counts = edge_counts(mesh.faces)
            assert counts and set(counts.values()) == {2}
            assert signed_volume(mesh.vertices, mesh.faces) > 0.0
            if mesh.category == "rail":
                max_rail_extent_radius = max(
                    max_rail_extent_radius,
                    max(math.hypot(v[0], v[2]) for v in mesh.vertices),
                )
            elif mesh.category == "tube":
                max_tube_vertex_radius = max(
                    max_tube_vertex_radius,
                    max(math.hypot(v[0], v[2]) for v in mesh.vertices),
                )
        assert max(math.hypot(v[0], v[2]) for m in ancillary.meshes_of_category("tube") for v in m.vertices) <= r + 1e-10

    assert walkway_sides == {"left", "right"}
    assert max_rail_extent_radius < r
    assert max_tube_vertex_radius <= r + 1e-10

    total_scene_objects = 0
    total_ancillary = 0
    json_roundtrips = 0
    max_ancillary_seam_error_m = 0.0
    for seed in range(FULL_SCENES):
        n = 5
        result = build_procedural_nominal_tunnel(
            assembly_config=TunnelAssemblyConfig(
                n_rings=n,
                ring_width_m=ring_cfg.width_m,
            ),
            include_bolts=True,
            include_ancillary=True,
            ancillary_sampling_policy=AncillarySamplingPolicy.REFERENCE,
            label_policy=LabelPolicy.STSD_COARSE,
            seed=100_000 + seed,
        )
        scene = result.scene
        assert len(scene.objects_of_type("ancillary_pavement")) == n
        assert len(scene.objects_of_type("ancillary_walkway")) == n
        assert len(scene.objects_of_type("ancillary_rail")) == 2 * n
        assert len(scene.objects_of_type("ancillary_tube")) == 6 * n
        assert {o.label_id for o in scene.objects_of_type("lining_segment")} == {1}
        assert {o.label_id for o in scene.objects_of_type("ancillary_walkway")} == {2}
        assert {o.label_id for o in scene.objects_of_type("ancillary_tube")} == {3}

        for obj in scene.objects:
            if obj.object_type.startswith("ancillary_"):
                assert obj.custom_properties["objectAppliedAxialRotationDeg"] == 0.0
                assert obj.custom_properties["followRingAxialRotation"] is False
                assert obj.custom_properties["followSceneAlignment"] is True
                assert obj.custom_properties["objectTransformPolicy"] == "stitched_scene_alignment"

        by_ring = [
            [
                obj
                for obj in scene.objects
                if obj.ring_id == ring_id and obj.object_type.startswith("ancillary_")
            ]
            for ring_id in range(n)
        ]
        for ring_id in range(n - 1):
            for left, right in zip(by_ring[ring_id], by_ring[ring_id + 1]):
                assert left.object_type == right.object_type
                section = len(left.vertices) // 3
                assert section > 0 and len(left.vertices) == len(right.vertices)
                for a, b in zip(
                    left.vertices[-section:],
                    right.vertices[:section],
                ):
                    max_ancillary_seam_error_m = max(
                        max_ancillary_seam_error_m,
                        math.dist(a, b),
                    )
        assert max_ancillary_seam_error_m < 5e-12

        total_scene_objects += len(scene.objects)
        total_ancillary += sum(
            1 for o in scene.objects if o.object_type.startswith("ancillary_")
        )
        if seed < JSON_ROUNDTRIPS:
            assert scene_package_from_dict(scene_package_to_dict(scene)) == scene
            json_roundtrips += 1

    output = {
        "stage": 8,
        "sampledConfigs": SAMPLED_CONFIGS,
        "ancillaryMeshesChecked": mesh_count,
        "fullScenes": FULL_SCENES,
        "fullSceneRings": FULL_SCENES * 5,
        "fullSceneObjectsChecked": total_scene_objects,
        "fullSceneAncillaryObjects": total_ancillary,
        "jsonRoundtrips": json_roundtrips,
        "walkwaySidesObserved": sorted(walkway_sides),
        "maxSampledWalkwayDepthM": max_walkway_depth,
        "maxRailVertexRadiusM": max_rail_extent_radius,
        "maxTubeVertexRadiusM": max_tube_vertex_radius,
        "innerRadiusM": r,
        "maxAncillaryInterRingSeamErrorM": max_ancillary_seam_error_m,
        "manifoldPositiveVolume": "PASS",
        "stsdCoarseLabels": "PASS",
        "ancillaryAxialRotationSuppression": "PASS",
        "result": "PASS",
    }
    OUTPUT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
