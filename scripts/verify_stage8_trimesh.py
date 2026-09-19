from __future__ import annotations

import json
from pathlib import Path

import trimesh

from tunnel_scanner_core import (
    AncillarySamplingPolicy,
    LabelPolicy,
    RingConfig,
    TunnelAssemblyConfig,
    build_ancillary_set,
    build_procedural_nominal_tunnel,
    sample_ancillary_config,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage8_trimesh_verification.json"
ANCILLARY_CONFIGS = 250


def check_mesh(name, vertices, faces, failures):
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    if not mesh.is_watertight:
        failures.append({"name": name, "reason": "not_watertight"})
    if not mesh.is_winding_consistent:
        failures.append({"name": name, "reason": "inconsistent_winding"})
    if float(mesh.volume) <= 0.0:
        failures.append(
            {"name": name, "reason": "non_positive_volume", "volume": float(mesh.volume)}
        )


def main() -> None:
    ring_cfg = RingConfig()
    failures = []
    ancillary_meshes_checked = 0

    for seed in range(ANCILLARY_CONFIGS):
        cfg = sample_ancillary_config(
            ring_cfg.inner_radius_m,
            seed=seed,
            policy=AncillarySamplingPolicy.PUBLISHED_UNIFORM,
        )
        ancillary = build_ancillary_set(
            inner_radius_m=ring_cfg.inner_radius_m,
            length_m=ring_cfg.width_m,
            config=cfg,
        )
        for mesh in ancillary.meshes:
            ancillary_meshes_checked += 1
            check_mesh(
                f"sample_{seed:04d}/{mesh.name}",
                mesh.vertices,
                mesh.faces,
                failures,
            )

    canonical = build_procedural_nominal_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=5,
            ring_width_m=ring_cfg.width_m,
        ),
        include_bolts=True,
        include_ancillary=True,
        ancillary_sampling_policy=AncillarySamplingPolicy.REFERENCE,
        label_policy=LabelPolicy.STSD_COARSE,
        seed=5812,
    )
    canonical_objects_checked = 0
    for obj in canonical.scene.objects:
        canonical_objects_checked += 1
        check_mesh(obj.name, obj.vertices, obj.faces, failures)

    result = {
        "stage": 8,
        "trimeshVersion": trimesh.__version__,
        "sampledAncillaryConfigs": ANCILLARY_CONFIGS,
        "ancillaryMeshesChecked": ancillary_meshes_checked,
        "canonicalFiveRingObjectsChecked": canonical_objects_checked,
        "failureCount": len(failures),
        "failures": failures[:100],
        "result": "PASS" if not failures else "FAIL",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
