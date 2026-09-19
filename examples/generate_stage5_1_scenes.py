from __future__ import annotations

import json
from pathlib import Path

from tunnel_scanner_core import (
    RingConfig,
    SurfaceMeshingConfig,
    build_curved_ring_mesh,
    build_deformed_ring_mesh,
    build_prescribed_joint_set,
    build_ring_mesh,
    sample_closed_deformation,
    sample_joint_config,
    sample_six_segment_angles,
    sagitta_m,
)
from tunnel_scanner_core.scene import (
    ScenePackage,
    build_deformed_scene_package,
    build_nominal_scene_package,
)
from tunnel_scanner_core.scene_io import write_scene_package_json


HERE = Path(__file__).resolve().parent
SEED = 5812
RING_ID = 12
TOLERANCE_M = 0.002


def write_scene_obj(package: ScenePackage, path: Path) -> None:
    lines = [
        "# Tunnel Scanner Stage 5.1 scene preview",
        f"# package {package.name}",
        "# units: metres",
    ]
    offset = 1
    for obj in package.objects:
        lines.append(f"o {obj.name}")
        for x, y, z in obj.vertices:
            lines.append(f"v {x:.12g} {y:.12g} {z:.12g}")
        for face in obj.faces:
            indices = " ".join(str(offset + i) for i in face)
            lines.append(f"f {indices}")
        offset += len(obj.vertices)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    cfg = RingConfig()
    meshing = SurfaceMeshingConfig(max_sagitta_m=TOLERANCE_M)
    angles = sample_six_segment_angles(seed=SEED)
    ring = build_ring_mesh(cfg, angles)
    curved = build_curved_ring_mesh(ring, meshing=meshing)

    joint_cfg = sample_joint_config(seed=SEED)
    prescribed = build_prescribed_joint_set(ring, joint_cfg)
    nominal = build_nominal_scene_package(
        ring,
        prescribed,
        ring_id=RING_ID,
        include_radial_joints=True,
        include_circumferential_front=False,
        include_circumferential_back=True,
        surface_meshing=meshing,
    )
    write_scene_package_json(nominal, HERE / "stage5_1_nominal_scene.json")
    write_scene_obj(nominal, HERE / "stage5_1_nominal_scene.obj")

    deformation = sample_closed_deformation(cfg, angles, seed=SEED)
    deformed_ring = build_deformed_ring_mesh(ring, deformation)
    deformed = build_deformed_scene_package(
        deformed_ring,
        ring_id=RING_ID,
        include_displacement_joints=True,
        surface_meshing=meshing,
    )
    write_scene_package_json(deformed, HERE / "stage5_1_deformed_scene.json")
    write_scene_obj(deformed, HERE / "stage5_1_deformed_scene.obj")

    metrics = {
        "stage": "5.1",
        "seed": SEED,
        "ringId": RING_ID,
        "requestedMaxSagittaM": TOLERANCE_M,
        "analyticalSegmentRepresentation": "8-corner hexahedron retained for constraints/kinematics",
        "exportSegmentRepresentation": "adaptive cylindrical surface grid",
        "segments": [],
    }
    for coarse, surface in zip(ring.segments, curved.segments):
        coarse_span = max(
            abs(coarse.angular_extent.front_span_deg),
            abs(coarse.angular_extent.back_span_deg),
        )
        metrics["segments"].append(
            {
                "name": surface.name,
                "frontSpanDeg": surface.angular_extent.front_span_deg,
                "backSpanDeg": surface.angular_extent.back_span_deg,
                "circumferentialSubdivisions": surface.circumferential_subdivisions,
                "longitudinalSubdivisions": surface.longitudinal_subdivisions,
                "vertices": len(surface.vertices),
                "faces": len(surface.faces),
                "coarseOneChordSagittaM": sagitta_m(cfg.outer_radius_m, coarse_span),
                "curvedConservativeSagittaM": surface.achieved_max_sagitta_m,
                "improvementFactor": (
                    sagitta_m(cfg.outer_radius_m, coarse_span)
                    / surface.achieved_max_sagitta_m
                ),
            }
        )
    metrics["totalCurvedSegmentVertices"] = sum(len(s.vertices) for s in curved.segments)
    metrics["totalCurvedSegmentFaces"] = sum(len(s.faces) for s in curved.segments)
    metrics["maxAchievedSagittaM"] = max(s.achieved_max_sagitta_m for s in curved.segments)
    (HERE / "stage5_1_geometry_metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )

    print(f"nominal objects: {len(nominal.objects)}")
    print(f"deformed objects: {len(deformed.objects)}")
    print(f"curved segment vertices: {metrics['totalCurvedSegmentVertices']}")
    print(f"curved segment faces: {metrics['totalCurvedSegmentFaces']}")
    print(f"max conservative sagitta: {metrics['maxAchievedSagittaM']*1000:.6f} mm")
    print("wrote Stage-5.1 JSON/OBJ/metrics examples")


if __name__ == "__main__":
    main()
