from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np

from tunnel_scanner_core import (
    RingConfig,
    build_deformed_ring_mesh,
    build_ring_mesh,
    derive_closure_k_transform,
    sample_closed_deformation,
    sample_six_segment_angles,
)


def edge_counts(faces):
    out = {}
    for face in faces:
        for a, b in zip(face, face[1:] + face[:1]):
            edge = tuple(sorted((a, b)))
            out[edge] = out.get(edge, 0) + 1
    return out


def signed_volume(vertices, faces):
    vv = [np.asarray(v, dtype=float) for v in vertices]
    total = 0.0
    for q in faces:
        for a, b, c in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
            total += float(np.dot(vv[a], np.cross(vv[b], vv[c]))) / 6.0
    return total


def run_default(n=3_000):
    cfg = RingConfig()
    stats = {
        "count": n,
        "max_translation_closure_error_m": 0.0,
        "max_angular_closure_error_deg": 0.0,
        "max_duplicate_k_translation_error_m": 0.0,
        "max_duplicate_k_rotation_error_deg": 0.0,
        "max_relative_rotation_recovery_error_deg": 0.0,
        "max_rigid_edge_length_error_m": 0.0,
        "max_joint_corner_separation_m": 0.0,
        "min_nonzero_joint_corner_separation_m": None,
        "min_joint_signed_volume_m3": None,
        "nonmanifold_joint_count": 0,
        "negative_winding_joint_count": 0,
        "attempts": [],
    }

    for seed in range(n):
        angles = sample_six_segment_angles(seed=seed)
        ring = build_ring_mesh(cfg, angles)
        deformation = sample_closed_deformation(cfg, angles, seed=100_000 + seed)
        dr = build_deformed_ring_mesh(ring, deformation)
        k = derive_closure_k_transform(ring, deformation)

        stats["attempts"].append(deformation.attempts)
        stats["max_translation_closure_error_m"] = max(
            stats["max_translation_closure_error_m"],
            deformation.translation_closure_error_m,
        )
        stats["max_angular_closure_error_deg"] = max(
            stats["max_angular_closure_error_deg"],
            abs(deformation.angular_closure_error_deg),
        )
        stats["max_duplicate_k_translation_error_m"] = max(
            stats["max_duplicate_k_translation_error_m"],
            math.hypot(*k.center_offset_xz_m),
        )
        stats["max_duplicate_k_rotation_error_deg"] = max(
            stats["max_duplicate_k_rotation_error_deg"], abs(k.rotation_deg)
        )

        t = {x.segment_name: x for x in dr.segment_transforms}
        prev_rot = 0.0
        for step in deformation.steps:
            cur_rot = 0.0 if step.segment_name == "K" else t[step.segment_name].rotation_deg
            recovered = (cur_rot - prev_rot + 180.0) % 360.0 - 180.0
            err = abs(recovered - step.rotation_deg)
            stats["max_relative_rotation_recovery_error_deg"] = max(
                stats["max_relative_rotation_recovery_error_deg"], err
            )
            prev_rot = cur_rot

        for base, moved in zip(ring.segments, dr.segments):
            for a, b in ((0,1),(0,4),(0,2),(3,7),(4,5),(6,7)):
                e0 = math.dist(base.vertices[a], base.vertices[b])
                e1 = math.dist(moved.vertices[a], moved.vertices[b])
                stats["max_rigid_edge_length_error_m"] = max(
                    stats["max_rigid_edge_length_error_m"], abs(e0-e1)
                )

        for joint in dr.displacement_joints:
            counts = edge_counts(joint.faces)
            if len(counts) != 12 or set(counts.values()) != {2}:
                stats["nonmanifold_joint_count"] += 1
            vol = signed_volume(joint.vertices, joint.faces)
            if vol < -1e-14:
                stats["negative_winding_joint_count"] += 1
            if stats["min_joint_signed_volume_m3"] is None:
                stats["min_joint_signed_volume_m3"] = vol
            else:
                stats["min_joint_signed_volume_m3"] = min(
                    stats["min_joint_signed_volume_m3"], vol
                )
            for sep in joint.corner_separations_m:
                stats["max_joint_corner_separation_m"] = max(
                    stats["max_joint_corner_separation_m"], sep
                )
                if sep > 1e-12:
                    if stats["min_nonzero_joint_corner_separation_m"] is None:
                        stats["min_nonzero_joint_corner_separation_m"] = sep
                    else:
                        stats["min_nonzero_joint_corner_separation_m"] = min(
                            stats["min_nonzero_joint_corner_separation_m"], sep
                        )

    attempts = np.asarray(stats.pop("attempts"), dtype=float)
    stats["attempts_mean"] = float(attempts.mean())
    stats["attempts_median"] = float(np.median(attempts))
    stats["attempts_p99"] = float(np.quantile(attempts, 0.99))
    stats["attempts_max"] = int(attempts.max())
    return stats


def run_random_geometry(n=1_000):
    rng = np.random.default_rng(94821)
    max_trans = 0.0
    max_k_trans = 0.0
    max_k_rot = 0.0
    max_attempts = 0
    for i in range(n):
        R = float(rng.uniform(2.0, 5.0))
        thickness = float(rng.uniform(0.2, min(0.6, R - 0.1)))
        cfg = RingConfig.from_outer_radius_and_thickness(R, thickness)
        angles = sample_six_segment_angles(seed=500_000 + i)
        ring = build_ring_mesh(cfg, angles)
        deformation = sample_closed_deformation(cfg, angles, seed=700_000 + i)
        k = derive_closure_k_transform(ring, deformation)
        max_trans = max(max_trans, deformation.translation_closure_error_m)
        max_k_trans = max(max_k_trans, math.hypot(*k.center_offset_xz_m))
        max_k_rot = max(max_k_rot, abs(k.rotation_deg))
        max_attempts = max(max_attempts, deformation.attempts)
    return {
        "count": n,
        "max_translation_closure_error_m": max_trans,
        "max_duplicate_k_translation_error_m": max_k_trans,
        "max_duplicate_k_rotation_error_deg": max_k_rot,
        "attempts_max": max_attempts,
    }


if __name__ == "__main__":
    result = {
        "default_geometry": run_default(),
        "random_geometry": run_random_geometry(),
    }
    out = Path(__file__).resolve().parents[1] / "examples" / "stage3_verification.json"
    out.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))
