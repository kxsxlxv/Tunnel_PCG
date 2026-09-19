from __future__ import annotations

import json
from pathlib import Path

from tunnel_scanner_core import (
    RingConfig,
    SurfaceMeshingConfig,
    build_prescribed_joint_set,
    build_ring_mesh,
    sample_joint_config,
    sample_six_segment_angles,
)
from tunnel_scanner_core.bolts import (
    BoltLayoutType,
    BoltPerturbationConfig,
    build_bolt_set,
    sample_bolt_config,
)
from tunnel_scanner_core.scene import build_nominal_scene_package
from tunnel_scanner_core.scene_io import write_scene_package_json


HERE = Path(__file__).resolve().parent
SEED = 5812
RING_ID = 12


def main() -> None:
    ring_cfg = RingConfig()
    angles = sample_six_segment_angles(seed=SEED)
    ring = build_ring_mesh(ring_cfg, angles)
    joints = build_prescribed_joint_set(ring, sample_joint_config(seed=SEED))
    bolt_cfg = sample_bolt_config(seed=SEED)
    bolts = build_bolt_set(
        ring,
        bolt_cfg,
        BoltLayoutType.TYPE1_CENTERED,
        seed=SEED,
        perturbation_config=BoltPerturbationConfig(),
    )
    package = build_nominal_scene_package(
        ring,
        joints,
        ring_id=RING_ID,
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=0.002),
        bolts=bolts,
        bolt_boolean_overlap_m=0.005,
    )
    output = HERE / "stage6_nominal_bolts_scene.json"
    write_scene_package_json(package, output)

    summary = {
        "stage": 6,
        "seed": SEED,
        "ringId": RING_ID,
        "layout": bolts.layout.value,
        "boltAssemblies": len(bolts.assemblies),
        "sceneObjectsBeforeBlenderBoolean": len(package.objects),
        "expectedPocketCuttersRemoved": len(bolts.assemblies),
        "expectedObjectsAfterBlenderBoolean": len(package.objects) - len(bolts.assemblies),
        "boltConfig": {
            "topWidthM": bolt_cfg.top_width_m,
            "bottomWidthM": bolt_cfg.bottom_width_m,
            "pocketHeightM": bolt_cfg.pocket_height_m,
            "penetrationM": bolt_cfg.penetration_m,
            "headRadiusM": bolt_cfg.head_radius_m,
            "headThicknessM": bolt_cfg.head_thickness_m,
            "protrusionM": bolt_cfg.protrusion_m,
            "jointArcOffsetM": bolt_cfg.joint_arc_offset_m,
            "headHeightRatio": bolt_cfg.head_height_ratio,
        },
        "booleanPipeline": package.metadata["boltBooleanPipeline"],
    }
    (HERE / "stage6_scene_summary.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, indent=2))
    print(f"wrote {output}")


if __name__ == "__main__":
    main()
