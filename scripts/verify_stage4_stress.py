from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from tunnel_scanner_core import (
    RingConfig,
    build_circumferential_outer_collar,
    build_prescribed_radial_joints,
    build_ring_mesh,
    sample_joint_config,
    sample_six_segment_angles,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "examples" / "stage4_verification.json"


def edge_counts(faces):
    counts = {}
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            e = tuple(sorted((a, b)))
            counts[e] = counts.get(e, 0) + 1
    return counts


def signed_volume(vertices, faces):
    vv = [np.asarray(v, dtype=float) for v in vertices]
    total = 0.0
    for q in faces:
        for a, b, c in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
            total += float(np.dot(vv[a], np.cross(vv[b], vv[c]))) / 6.0
    return total


def radius(v):
    return math.hypot(v[0], v[2])


def run_case(cfg: RingConfig, seed: int, metrics: dict):
    angles = sample_six_segment_angles(seed=seed)
    ring = build_ring_mesh(cfg, angles)
    jc = sample_joint_config(seed=1_000_000 + seed)
    radial = build_prescribed_radial_joints(ring, jc)
    front = build_circumferential_outer_collar(ring, jc, side="front")
    back = build_circumferential_outer_collar(ring, jc, side="back")

    centres = sorted(j.front_interface_alpha_deg % 360.0 for j in radial)
    half_width = 0.5 * max(j.base_angular_width_deg for j in radial)
    gaps = [(centres[(i + 1) % 6] - centres[i]) % 360.0 for i in range(6)]
    clearance = min(gaps) - 2.0 * half_width
    metrics["min_radial_joint_angular_clearance_deg"] = min(
        metrics["min_radial_joint_angular_clearance_deg"], clearance
    )

    for j in radial:
        metrics["max_base_arc_width_error_m"] = max(
            metrics["max_base_arc_width_error_m"], abs(j.base_arc_width_m - jc.width_m)
        )
        metrics["max_cap_arc_width_error_m"] = max(
            metrics["max_cap_arc_width_error_m"], abs(j.cap_arc_width_m - jc.width_m)
        )
        metrics["max_added_thickness_error_m"] = max(
            metrics["max_added_thickness_error_m"],
            abs((j.cap_radius_m - j.base_radius_m) - jc.added_thickness_m),
        )
        min_r = min(radius(v) for v in j.vertices)
        metrics["min_radial_clearance_from_extrados_m"] = min(
            metrics["min_radial_clearance_from_extrados_m"],
            min_r - cfg.outer_radius_m,
        )
        ec = edge_counts(j.faces)
        if len(ec) != 12 or set(ec.values()) != {2}:
            metrics["radial_nonmanifold_count"] += 1
        vol = signed_volume(j.vertices, j.faces)
        metrics["min_radial_signed_volume_m3"] = min(
            metrics["min_radial_signed_volume_m3"], vol
        )
        if vol <= 0:
            metrics["radial_nonpositive_volume_count"] += 1

    for side_pieces in (front, back):
        total_span = sum(p.alpha_end_deg - p.alpha_start_deg for p in side_pieces)
        metrics["max_circumferential_tiling_error_deg"] = max(
            metrics["max_circumferential_tiling_error_deg"], abs(total_span - 360.0)
        )
        for p in side_pieces:
            metrics["max_circumferential_axial_width_error_m"] = max(
                metrics["max_circumferential_axial_width_error_m"],
                abs(p.axial_width_m - jc.width_m),
            )
            ec = edge_counts(p.faces)
            if len(ec) != 12 or set(ec.values()) != {2}:
                metrics["circumferential_nonmanifold_count"] += 1
            vol = signed_volume(p.vertices, p.faces)
            metrics["min_circumferential_signed_volume_m3"] = min(
                metrics["min_circumferential_signed_volume_m3"], vol
            )
            if vol <= 0:
                metrics["circumferential_nonpositive_volume_count"] += 1


def main():
    metrics = {
        "max_base_arc_width_error_m": 0.0,
        "max_cap_arc_width_error_m": 0.0,
        "max_added_thickness_error_m": 0.0,
        "min_radial_clearance_from_extrados_m": float("inf"),
        "min_radial_joint_angular_clearance_deg": float("inf"),
        "min_radial_signed_volume_m3": float("inf"),
        "radial_nonmanifold_count": 0,
        "radial_nonpositive_volume_count": 0,
        "max_circumferential_tiling_error_deg": 0.0,
        "max_circumferential_axial_width_error_m": 0.0,
        "min_circumferential_signed_volume_m3": float("inf"),
        "circumferential_nonmanifold_count": 0,
        "circumferential_nonpositive_volume_count": 0,
    }

    default_n = 3_000
    cfg = RingConfig()
    for seed in range(default_n):
        run_case(cfg, seed, metrics)

    # Geometry randomization within the article's broad outer-radius range. The
    # article does not supply a universal t_seg distribution, so sample a modest
    # physically sensible band for stress-testing code rather than claiming it
    # as a paper distribution.
    randomized_n = 1_000
    rng = np.random.default_rng(240919)
    for i in range(randomized_n):
        R = float(rng.uniform(2.0, 5.0))
        t = float(rng.uniform(0.25, min(0.55, 0.25 * R)))
        cfg = RingConfig.from_outer_radius_and_thickness(R, t)
        run_case(cfg, 100_000 + i, metrics)

    result = {
        "stage": 4,
        "default_geometry_cases": default_n,
        "randomized_geometry_cases": randomized_n,
        "total_cases": default_n + randomized_n,
        "metrics": metrics,
        "interpretation": {
            "radial_joint": "paper-literal outer-rib reconstruction",
            "circumferential_joint": "provisional outer-collar reconstruction",
        },
    }
    OUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
