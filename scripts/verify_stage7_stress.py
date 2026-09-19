from __future__ import annotations

import json
import math
from pathlib import Path
import random

import numpy as np

from tunnel_scanner_core import RingConfig
from tunnel_scanner_core.assembly import (
    RingRotationStrategy,
    TunnelAssemblyConfig,
    sample_tunnel_assembly,
    transform_point_by_ring_pose,
)
from tunnel_scanner_core.blender_adapter import plan_bolt_boolean_operations
from tunnel_scanner_core.scene_io import scene_package_from_dict, scene_package_to_dict
from tunnel_scanner_core.tunnel import build_procedural_nominal_tunnel


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage7_verification.json"
POSE_SCENES = 2000
FULL_SCENES = 50
JSON_ROUNDTRIPS = 10


def main() -> None:
    ring_cfg = RingConfig()
    rng = random.Random(5812)
    epsilon_x: list[float] = []
    epsilon_z: list[float] = []
    max_spacing_error = 0.0
    max_rigid_error = 0.0
    max_nominal_rotation = 0.0
    total_pose_rings = 0

    p = (2.3, -0.55, 0.7)
    q = (-1.1, 0.42, 2.0)
    d0 = math.dist(p, q)

    for scene_index in range(POSE_SCENES):
        n = rng.randint(10, 30)
        cfg = TunnelAssemblyConfig(
            n_rings=n,
            ring_width_m=ring_cfg.width_m,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
            recenter_lateral_offsets=True,
        )
        assembly = sample_tunnel_assembly(cfg, seed=100_000 + scene_index)
        total_pose_rings += n
        epsilon_x.extend(x.epsilon_x_m for x in assembly.poses)
        epsilon_z.extend(x.epsilon_z_m for x in assembly.poses)
        max_nominal_rotation = max(
            max_nominal_rotation,
            max(abs(x.nominal_rotation_deg) for x in assembly.poses),
        )
        assert all(
            abs(x.nominal_rotation_deg) <= cfg.stagger_bound_deg + 1e-12
            for x in assembly.poses
        )
        assert abs(np.mean([x.translation_m[0] for x in assembly.poses])) < 1e-12
        assert abs(np.mean([x.translation_m[2] for x in assembly.poses])) < 1e-12

        for i, pose in enumerate(assembly.poses):
            max_spacing_error = max(
                max_spacing_error,
                abs(pose.translation_m[1] - i * ring_cfg.width_m),
            )
            max_rigid_error = max(
                max_rigid_error,
                abs(
                    math.dist(
                        transform_point_by_ring_pose(p, pose),
                        transform_point_by_ring_pose(q, pose),
                    )
                    - d0
                ),
            )

    eps = np.asarray(epsilon_x + epsilon_z, dtype=float)
    empirical_mean = float(eps.mean())
    empirical_std = float(eps.std(ddof=0))
    assert abs(empirical_mean) < 0.0001
    assert abs(empirical_std - 0.005) < 0.0001

    total_objects = 0
    total_boolean_ops = 0
    json_roundtrips_done = 0
    for scene_index in range(FULL_SCENES):
        n = 5
        result = build_procedural_nominal_tunnel(
            assembly_config=TunnelAssemblyConfig(
                n_rings=n,
                ring_width_m=ring_cfg.width_m,
                ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
            ),
            include_bolts=True,
            seed=200_000 + scene_index,
        )
        scene = result.scene
        assert len(scene.objects_of_type("prescribed_circumferential_joint")) == (n - 1) * 6
        assert len(scene.objects_of_type("lining_segment")) == n * 6
        assert len(scene.objects_of_type("bolt_head")) == n * 18
        assert len(scene.objects_of_type("bolt_pocket_cutter")) == n * 18
        assert len({o.name for o in scene.objects}) == len(scene.objects)
        assert len({o.instance_id for o in scene.objects}) == len(scene.objects)

        plan = plan_bolt_boolean_operations(scene)
        assert len(plan) == n * 36
        assert {op.ring_id for op in plan} == set(range(n))
        names = {o.name for o in scene.objects}
        assert all(op.target_name in names and op.tool_name in names for op in plan)

        total_objects += len(scene.objects)
        total_boolean_ops += len(plan)

        if scene_index < JSON_ROUNDTRIPS:
            assert scene_package_from_dict(scene_package_to_dict(scene)) == scene
            json_roundtrips_done += 1

    result = {
        "stage": 7,
        "poseScenes": POSE_SCENES,
        "poseRings": total_pose_rings,
        "fullScenes": FULL_SCENES,
        "fullSceneRings": FULL_SCENES * 5,
        "fullSceneObjectsChecked": total_objects,
        "booleanOperationsPlanned": total_boolean_ops,
        "jsonRoundtrips": json_roundtrips_done,
        "empiricalAxisNoiseMeanM": empirical_mean,
        "empiricalAxisNoiseStdM": empirical_std,
        "configuredAxisNoiseSigmaM": 0.005,
        "maxLongitudinalSpacingErrorM": max_spacing_error,
        "maxRigidTransformDistanceErrorM": max_rigid_error,
        "maxSampledNominalStaggerDeg": max_nominal_rotation,
        "staggerBoundDeg": 135.0,
        "result": "PASS",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
