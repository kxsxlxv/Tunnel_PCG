from __future__ import annotations

import csv
import json
from pathlib import Path

from tunnel_pcg_ref.rail_profiles import R50, R65, reconstruct_half_primitives, sample_closed_profile, validation_metrics
from tunnel_pcg_ref.clearances import OM_UPPER_RIGHT

ROOT = Path(__file__).parent
FX = ROOT / "fixtures"
FX.mkdir(exist_ok=True)

for spec in (R50, R65):
    pts = sample_closed_profile(spec, chord_error_m=0.00005)
    with (FX / f"{spec.name.lower()}_profile_0p05mm.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["y_m", "z_m"])
        for p in pts:
            w.writerow([f"{p.x:.9f}", f"{p.z:.9f}"])
    primitives = []
    for p in reconstruct_half_primitives(spec):
        primitives.append({
            "kind": p.kind,
            "label": p.label,
            "start": [p.start.x, p.start.z],
            "end": [p.end.x, p.end.z],
            "center": None if p.center is None else [p.center.x, p.center.z],
            "radius": p.radius,
        })
    payload = {"rail": spec.name, "validation": validation_metrics(spec), "right_half_primitives": primitives}
    (FX / f"{spec.name.lower()}_analytic_primitives.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")

(FX / "om_upper_right_points.csv").write_text(
    "point,y_m,z_m\n" + "\n".join(f"{i},{p.x:.3f},{p.z:.3f}" for i,p in enumerate(OM_UPPER_RIGHT)),
    encoding="utf-8"
)
