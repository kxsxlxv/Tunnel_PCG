from __future__ import annotations

from pathlib import Path

from tunnel_scanner_core import (
    JointConfig,
    RingConfig,
    build_deformed_ring_mesh,
    build_prescribed_joint_set,
    build_ring_mesh,
    sample_closed_deformation,
    sample_joint_config,
    sample_six_segment_angles,
)
from tunnel_scanner_core.scene import (
    build_deformed_scene_package,
    build_nominal_scene_package,
)
from tunnel_scanner_core.scene_io import write_scene_package_json


HERE = Path(__file__).resolve().parent
SEED = 5812
RING_ID = 12

cfg = RingConfig()
angles = sample_six_segment_angles(seed=SEED)
ring = build_ring_mesh(cfg, angles)

joint_cfg = sample_joint_config(seed=SEED)
prescribed = build_prescribed_joint_set(ring, joint_cfg)
nominal = build_nominal_scene_package(
    ring,
    prescribed,
    ring_id=RING_ID,
    include_radial_joints=True,
    include_circumferential_front=False,
    include_circumferential_back=True,
)
write_scene_package_json(nominal, HERE / "stage5_nominal_scene.json")

deformation = sample_closed_deformation(cfg, angles, seed=SEED)
deformed_ring = build_deformed_ring_mesh(ring, deformation)
deformed = build_deformed_scene_package(
    deformed_ring,
    ring_id=RING_ID,
    include_displacement_joints=True,
)
write_scene_package_json(deformed, HERE / "stage5_deformed_scene.json")

print(f"nominal objects: {len(nominal.objects)}")
print(f"deformed objects: {len(deformed.objects)}")
print("wrote stage5_nominal_scene.json and stage5_deformed_scene.json")
