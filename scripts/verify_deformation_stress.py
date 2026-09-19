from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from tunnel_scanner_core import RingConfig, sample_six_segment_angles
from tunnel_scanner_core.deformation import sample_closed_deformation


def summarize(values: list[float]) -> dict[str, float]:
    a = np.asarray(values, dtype=float)
    return {
        "min": float(np.min(a)),
        "mean": float(np.mean(a)),
        "median": float(np.median(a)),
        "p90": float(np.quantile(a, 0.90)),
        "p99": float(np.quantile(a, 0.99)),
        "max": float(np.max(a)),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--default-count", type=int, default=10_000)
    ap.add_argument("--random-config-count", type=int, default=2_000)
    ap.add_argument("--output", type=Path, default=Path("examples/stage2_verification.json"))
    args = ap.parse_args()

    cfg = RingConfig()
    attempts: list[float] = []
    trans: list[float] = []
    angular: list[float] = []
    max_d: list[float] = []
    max_phi: list[float] = []

    for seed in range(args.default_count):
        angles = sample_six_segment_angles(seed=seed)
        deformation = sample_closed_deformation(cfg, angles, seed=100_000 + seed)
        attempts.append(float(deformation.attempts))
        trans.append(deformation.translation_closure_error_m)
        angular.append(abs(deformation.angular_closure_error_deg))
        max_d.append(max(abs(v) for v in deformation.dislocations_m))
        max_phi.append(max(abs(v) for v in deformation.rotations_deg))

    rng = np.random.default_rng(909)
    random_attempts: list[float] = []
    random_trans: list[float] = []
    random_angular: list[float] = []
    for i in range(args.random_config_count):
        outer = float(rng.uniform(2.0, 5.0))
        thickness = float(rng.uniform(0.2, min(0.6, outer - 0.1)))
        rcfg = RingConfig.from_outer_radius_and_thickness(outer, thickness)
        angles = sample_six_segment_angles(seed=10_000 + i)
        deformation = sample_closed_deformation(rcfg, angles, seed=20_000 + i)
        random_attempts.append(float(deformation.attempts))
        random_trans.append(deformation.translation_closure_error_m)
        random_angular.append(abs(deformation.angular_closure_error_deg))

    result = {
        "default_geometry": {
            "count": args.default_count,
            "attempts": summarize(attempts),
            "translation_closure_error_m": summarize(trans),
            "angular_closure_error_deg": summarize(angular),
            "max_abs_dislocation_m": summarize(max_d),
            "max_abs_rotation_deg": summarize(max_phi),
        },
        "random_geometry": {
            "count": args.random_config_count,
            "outer_radius_range_m": [2.0, 5.0],
            "thickness_range_m": [0.2, 0.6],
            "attempts": summarize(random_attempts),
            "translation_closure_error_m": summarize(random_trans),
            "angular_closure_error_deg": summarize(random_angular),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
