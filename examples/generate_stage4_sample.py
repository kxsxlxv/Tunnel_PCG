from pathlib import Path

from tunnel_scanner_core import (
    RingConfig,
    build_prescribed_joint_set,
    build_ring_mesh,
    sample_joint_config,
    sample_six_segment_angles,
    write_prescribed_joints_json,
    write_prescribed_joints_obj,
)

HERE = Path(__file__).resolve().parent
SEED = 5812

cfg = RingConfig()
angles = sample_six_segment_angles(seed=SEED)
ring = build_ring_mesh(cfg, angles)
joint_cfg = sample_joint_config(seed=SEED)
joints = build_prescribed_joint_set(ring, joint_cfg)

write_prescribed_joints_json(ring, joints, HERE / "sample_prescribed_joints.json")
write_prescribed_joints_obj(
    ring,
    joints,
    HERE / "sample_prescribed_joints.obj",
    include_segments=True,
    include_radial=True,
    include_circumferential_front=False,
    include_circumferential_back=True,
)

print(joint_cfg)
print(f"radial joints: {len(joints.radial)}")
print(f"front collar pieces: {len(joints.circumferential_front)}")
print(f"back collar pieces: {len(joints.circumferential_back)}")
