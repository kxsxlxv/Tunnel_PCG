from pathlib import Path

from tunnel_scanner_core import (
    AngleMode,
    RingConfig,
    build_ring_mesh,
    sample_six_segment_angles,
    write_ring_json,
    write_ring_obj,
)


HERE = Path(__file__).resolve().parent

config = RingConfig.from_outer_radius_and_thickness(
    outer_radius_m=3.35,
    thickness_m=0.35,
)
angles = sample_six_segment_angles(
    seed=5812,
    mode=AngleMode.EQUATION_CONSISTENT,
)
ring = build_ring_mesh(config, angles)

write_ring_json(ring, HERE / "sample_ring.json")
write_ring_obj(ring, HERE / "sample_ring.obj")

print("Generated:")
print(HERE / "sample_ring.json")
print(HERE / "sample_ring.obj")
for s in angles.segments:
    print(
        f"{s.name:>2}: front={s.front_deg:9.6f}°, "
        f"back={s.back_deg:9.6f}°, center={s.center_deg:9.6f}°"
    )
