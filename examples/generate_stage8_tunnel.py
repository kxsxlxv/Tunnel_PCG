from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tunnel_scanner_core import (
    AncillarySamplingPolicy,
    AncillaryTransformPolicy,
    LabelPolicy,
    RailSpacingConvention,
    RingConfig,
    RingRotationStrategy,
    SurfaceMeshingConfig,
    TunnelAssemblyConfig,
    build_procedural_nominal_tunnel,
    sample_ancillary_config,
)
from tunnel_scanner_core.scene_io import write_scene_package_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rings", type=int, default=13)
    parser.add_argument("--seed", type=int, default=5812)
    parser.add_argument("--no-bolts", action="store_true")
    parser.add_argument(
        "--label-policy",
        choices=[x.value for x in LabelPolicy],
        default=LabelPolicy.STSD_COARSE.value,
    )
    parser.add_argument(
        "--ancillary-sampling",
        choices=[x.value for x in AncillarySamplingPolicy],
        default=AncillarySamplingPolicy.REFERENCE.value,
    )
    parser.add_argument(
        "--ancillary-transform-policy",
        choices=[x.value for x in AncillaryTransformPolicy],
        default=AncillaryTransformPolicy.GRAVITY_STITCHED.value,
    )
    parser.add_argument(
        "--rail-spacing-convention",
        choices=[x.value for x in RailSpacingConvention],
        default=RailSpacingConvention.TABLE4_CENTER_SPACING.value,
    )
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
        default=PROJECT_ROOT / "examples" / "stage8_tunnel_scene.json",
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
    ancillary_cfg = sample_ancillary_config(
        ring_cfg.inner_radius_m,
        seed=args.seed,
        policy=AncillarySamplingPolicy(args.ancillary_sampling),
        transform_policy=AncillaryTransformPolicy(args.ancillary_transform_policy),
        rail_spacing_convention=RailSpacingConvention(args.rail_spacing_convention),
    )
    build = build_procedural_nominal_tunnel(
        ring_config=ring_cfg,
        assembly_config=assembly_cfg,
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=args.sagitta_mm / 1000.0),
        include_bolts=not args.no_bolts,
        include_ancillary=True,
        ancillary_config=ancillary_cfg,
        ancillary_sampling_policy=AncillarySamplingPolicy(args.ancillary_sampling),
        label_policy=LabelPolicy(args.label_policy),
        seed=args.seed,
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_scene_package_json(build.scene, output)

    counts = {
        object_type: len(build.scene.objects_of_type(object_type))
        for object_type in (
            "lining_segment",
            "ancillary_pavement",
            "ancillary_walkway",
            "ancillary_rail",
            "ancillary_tube",
            "bolt_head",
            "bolt_pocket_cutter",
        )
    }
    summary = {
        "stage": 8,
        "seed": args.seed,
        "ringCount": args.rings,
        "ringWidthM": ring_cfg.width_m,
        "chainageLengthM": build.assembly.length_by_chainage_m,
        "labelPolicy": args.label_policy,
        "ancillarySampling": args.ancillary_sampling,
        "ancillaryTransformPolicy": args.ancillary_transform_policy,
        "railSpacingConvention": args.rail_spacing_convention,
        "includeBolts": not args.no_bolts,
        "sceneObjects": len(build.scene.objects),
        "counts": counts,
        "ancillaryObjectsPerRing": (
            counts["ancillary_pavement"]
            + counts["ancillary_walkway"]
            + counts["ancillary_rail"]
            + counts["ancillary_tube"]
        )
        // args.rings,
        "lateralWavelengthM": assembly_cfg.resolved_lateral_wavelength_m,
        "verticalWavelengthM": assembly_cfg.resolved_vertical_wavelength_m,
        "sceneJson": output.name,
    }
    summary_path = output.with_name(output.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
