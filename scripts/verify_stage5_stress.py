from __future__ import annotations

import json
from pathlib import Path

from tunnel_scanner_core import (
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
from tunnel_scanner_core.scene_io import scene_package_from_dict, scene_package_to_dict


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage5_verification.json"
N_NOMINAL = 1000
N_DEFORMED = 1000


def validate_package(package, expected_count: int) -> int:
    assert len(package.objects) == expected_count
    assert len({o.name for o in package.objects}) == expected_count
    assert len({o.instance_id for o in package.objects}) == expected_count
    segments = package.objects_of_type("lining_segment")
    assert [o.label_id for o in segments] == [1, 2, 3, 4, 5, 6]
    for obj in package.objects:
        props = obj.custom_properties
        assert props["labelID"] == obj.label_id
        assert props["ringID"] == obj.ring_id
        assert all(isinstance(v, (str, int, float, bool)) for v in props.values())
        if obj.object_type != "lining_segment":
            assert obj.label_id == 0

    data = scene_package_to_dict(package)
    encoded = json.dumps(data, separators=(",", ":"))
    decoded = scene_package_from_dict(json.loads(encoded))
    assert decoded == package
    return len(encoded)


def main() -> None:
    max_nominal_json = 0
    max_deformed_json = 0
    max_closure_m = 0.0
    max_closure_deg = 0.0

    cfg = RingConfig()

    for seed in range(N_NOMINAL):
        angles = sample_six_segment_angles(seed=seed)
        ring = build_ring_mesh(cfg, angles)
        joints = build_prescribed_joint_set(ring, sample_joint_config(seed=100_000 + seed))
        package = build_nominal_scene_package(ring, joints, ring_id=seed)
        max_nominal_json = max(max_nominal_json, validate_package(package, 18))

    for seed in range(N_DEFORMED):
        angles = sample_six_segment_angles(seed=200_000 + seed)
        ring = build_ring_mesh(cfg, angles)
        deformation = sample_closed_deformation(cfg, angles, seed=300_000 + seed)
        deformed = build_deformed_ring_mesh(ring, deformation)
        package = build_deformed_scene_package(deformed, ring_id=seed)
        max_deformed_json = max(max_deformed_json, validate_package(package, 12))
        max_closure_m = max(max_closure_m, deformation.translation_closure_error_m)
        max_closure_deg = max(max_closure_deg, deformation.angular_closure_error_deg)

    result = {
        "stage": 5,
        "nominalPackages": N_NOMINAL,
        "deformedPackages": N_DEFORMED,
        "totalPackages": N_NOMINAL + N_DEFORMED,
        "objectsValidated": N_NOMINAL * 18 + N_DEFORMED * 12,
        "sceneJsonRoundtrips": N_NOMINAL + N_DEFORMED,
        "maxCompactNominalJsonBytes": max_nominal_json,
        "maxCompactDeformedJsonBytes": max_deformed_json,
        "maxDeformationClosureErrorM": max_closure_m,
        "maxDeformationClosureErrorDeg": max_closure_deg,
        "labelPolicy": {
            "segments": "1..6 in canonical generator order",
            "joints": 0,
        },
        "result": "PASS",
    }
    OUTPUT.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
