from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tunnel_scanner_core import RingConfig, SurfaceMeshingConfig
from tunnel_scanner_core.assembly import RingRotationStrategy, TunnelAssemblyConfig
from tunnel_scanner_core.scene_io import write_scene_package_json
from tunnel_scanner_core.tunnel import build_procedural_nominal_tunnel


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rings", type=int, default=13)
    parser.add_argument("--seed", type=int, default=5812)
    parser.add_argument("--no-bolts", action="store_true")
    parser.add_argument(
        "--rotation-strategy",
        choices=[x.value for x in RingRotationStrategy],
        default=RingRotationStrategy.RINGWISE_GAUSSIAN.value,
    )
    parser.add_argument("--axis-noise-sigma", type=float, default=0.005)
    parser.add_argument("--lateral-wavelength-m", type=float, default=50.0)
    parser.add_argument("--vertical-wavelength-m", type=float, default=100.0)
    parser.add_argument("--sagitta-mm", type=float, default=2.0)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "examples" / "stage7_tunnel_scene.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ring_cfg = RingConfig()
    assembly_cfg = TunnelAssemblyConfig(
        n_rings=args.rings,
        ring_width_m=ring_cfg.width_m,
        axis_noise_sigma_m=args.axis_noise_sigma,
        lateral_wavelength_m=args.lateral_wavelength_m,
        vertical_wavelength_m=args.vertical_wavelength_m,
        ring_rotation_strategy=RingRotationStrategy(args.rotation_strategy),
    )
    build = build_procedural_nominal_tunnel(
        ring_config=ring_cfg,
        assembly_config=assembly_cfg,
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=args.sagitta_mm / 1000.0),
        include_bolts=not args.no_bolts,
        seed=args.seed,
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_scene_package_json(build.scene, output)

    centreline = {
        "stage": "7.1",
        "seed": args.seed,
        "ringCount": args.rings,
        "ringWidthM": ring_cfg.width_m,
        "points": [
            {
                "ringID": p.ring_index,
                "chainageM": p.chainage_m,
                "translationM": list(p.translation_m),
                "rotationYDeg": p.rotation_y_deg,
                "nominalRotationDeg": p.nominal_rotation_deg,
                "angularImperfectionDeg": p.angular_imperfection_deg,
            }
            for p in build.assembly.poses
        ],
    }
    centreline_path = output.with_name(output.stem + "_centerline.json")
    centreline_path.write_text(json.dumps(centreline, indent=2) + "\n", encoding="utf-8")

    summary = {
        "stage": "7.1",
        "seed": args.seed,
        "ringCount": args.rings,
        "ringWidthM": ring_cfg.width_m,
        "chainageLengthM": build.assembly.length_by_chainage_m,
        "rotationStrategy": args.rotation_strategy,
        "includeBolts": not args.no_bolts,
        "sceneObjects": len(build.scene.objects),
        "liningSegments": len(build.scene.objects_of_type("lining_segment")),
        "radialJoints": len(build.scene.objects_of_type("prescribed_radial_joint")),
        "circumferentialJointPieces": len(
            build.scene.objects_of_type("prescribed_circumferential_joint")
        ),
        "boltHeads": len(build.scene.objects_of_type("bolt_head")),
        "boltPocketCutters": len(build.scene.objects_of_type("bolt_pocket_cutter")),
        "frequencyParameterization": "physical_wavelength_by_chainage",
        "lateralWavelengthM": assembly_cfg.resolved_lateral_wavelength_m,
        "verticalWavelengthM": assembly_cfg.resolved_vertical_wavelength_m,
        "omegaXRadPerM": assembly_cfg.resolved_omega_x_rad_per_m,
        "omegaZRadPerM": assembly_cfg.resolved_omega_z_rad_per_m,
        "omegaXRadPerRing": assembly_cfg.resolved_omega_x,
        "omegaZRadPerRing": assembly_cfg.resolved_omega_z,
        "deterministicAdjacentStepBoundXM": assembly_cfg.deterministic_adjacent_step_bound_x_m(),
        "deterministicAdjacentStepBoundZM": assembly_cfg.deterministic_adjacent_step_bound_z_m(),
        "deterministicAdjacentTransverseStepBoundM": assembly_cfg.deterministic_adjacent_transverse_step_bound_m(),
        "axisNoiseSigmaM": assembly_cfg.axis_noise_sigma_m,
        "lateralRecenterM": list(build.assembly.lateral_recenter_m),
        "sceneJson": output.name,
        "centrelineJson": centreline_path.name,
    }
    summary_path = output.with_name(output.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
