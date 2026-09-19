from pathlib import Path

from tunnel_scanner_core import (
    RingConfig,
    sample_closed_deformation,
    sample_six_segment_angles,
    write_deformation_json,
)


HERE = Path(__file__).resolve().parent

config = RingConfig(outer_radius_m=3.35, thickness_m=0.35, width_m=1.35)
angles = sample_six_segment_angles(seed=5812)
deformation = sample_closed_deformation(config, angles, seed=5812)

out = write_deformation_json(deformation, HERE / "sample_deformation.json")
print(out)
print(f"attempts={deformation.attempts}")
print(f"translation closure error={deformation.translation_closure_error_m:.3e} m")
print(f"angular closure error={deformation.angular_closure_error_deg:.3e} deg")
