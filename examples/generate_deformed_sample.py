from pathlib import Path

from tunnel_scanner_core import (
    RingConfig,
    build_deformed_ring_mesh,
    build_ring_mesh,
    sample_closed_deformation,
    sample_six_segment_angles,
    write_deformation_json,
    write_deformed_ring_json,
    write_deformed_ring_obj,
)

HERE = Path(__file__).resolve().parent

cfg = RingConfig()
angles = sample_six_segment_angles(seed=5812)
ring = build_ring_mesh(cfg, angles)
deformation = sample_closed_deformation(cfg, angles, seed=5812)
deformed = build_deformed_ring_mesh(ring, deformation)

write_deformation_json(deformation, HERE / "sample_deformation_stage3.json")
write_deformed_ring_json(deformed, HERE / "sample_deformed_ring.json")
write_deformed_ring_obj(deformed, HERE / "sample_deformed_ring.obj")

print("wrote sample_deformation_stage3.json")
print("wrote sample_deformed_ring.json")
print("wrote sample_deformed_ring.obj")
