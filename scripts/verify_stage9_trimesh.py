from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import trimesh

from tunnel_scanner_core import (
    LabelPolicy,
    ProductionConfig,
    TunnelAssemblyConfig,
    build_production_tunnel,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage9_trimesh_verification.json"


def triangulate(faces):
    out = []
    for face in faces:
        for i in range(1, len(face) - 1):
            out.append((face[0], face[i], face[i + 1]))
    return out


def main() -> None:
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=20,
            ring_width_m=1.35,
        ),
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(namespace="trimesh-stage9"),
        seed=5812,
    )
    failures = []
    checked = 0
    expected_open = 0
    expected_closed = 0

    for obj in build.scene.objects:
        if not obj.object_type.startswith("production_"):
            continue
        checked += 1
        mesh = trimesh.Trimesh(
            vertices=np.asarray(obj.vertices, dtype=float),
            faces=np.asarray(triangulate(obj.faces), dtype=np.int64),
            process=False,
        )
        if not mesh.is_winding_consistent:
            failures.append({"name": obj.name, "reason": "inconsistent_winding"})
        if np.any(~np.isfinite(mesh.vertices)):
            failures.append({"name": obj.name, "reason": "non_finite_vertices"})

        intentionally_open = (
            obj.custom_properties["omittedLongitudinalEdgeCount"] > 0
        )
        if intentionally_open:
            expected_open += 1
            if mesh.is_watertight:
                failures.append(
                    {"name": obj.name, "reason": "expected_open_contact_surface_but_watertight"}
                )
        else:
            expected_closed += 1
            if not mesh.is_watertight:
                failures.append({"name": obj.name, "reason": "expected_watertight"})

    result = {
        "stage": 9,
        "trimeshVersion": trimesh.__version__,
        "productionAssetsChecked": checked,
        "expectedOpenContactMeshes": expected_open,
        "expectedClosedMeshes": expected_closed,
        "failureCount": len(failures),
        "failures": failures,
        "result": "PASS" if not failures else "FAIL",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
