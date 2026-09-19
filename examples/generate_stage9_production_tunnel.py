from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tunnel_scanner_core import (
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    RingConfig,
    RingRotationStrategy,
    SurfaceMeshingConfig,
    TunnelAssemblyConfig,
    build_chunk_scene_packages,
    build_production_tunnel,
)
from tunnel_scanner_core.scene_io import write_scene_package_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    size = parser.add_mutually_exclusive_group()
    size.add_argument("--rings", type=int, default=None)
    size.add_argument("--length-m", type=float, default=None)
    parser.add_argument("--seed", type=int, default=5812)
    parser.add_argument("--namespace", default="production")
    parser.add_argument("--no-bolts", action="store_true")
    parser.add_argument(
        "--label-policy",
        choices=[x.value for x in LabelPolicy],
        default=LabelPolicy.STSD_COARSE.value,
    )
    parser.add_argument(
        "--rotation-strategy",
        choices=[x.value for x in RingRotationStrategy],
        default=RingRotationStrategy.RINGWISE_GAUSSIAN.value,
    )
    parser.add_argument("--lateral-wavelength-m", type=float, default=50.0)
    parser.add_argument("--vertical-wavelength-m", type=float, default=100.0)
    parser.add_argument("--axis-noise-sigma", type=float, default=0.005)
    parser.add_argument("--sagitta-mm", type=float, default=2.0)
    parser.add_argument("--chunk-m", type=float, default=None)
    parser.add_argument(
        "--chunk-policy",
        choices=[x.value for x in ChunkBoundaryPolicy],
        default=ChunkBoundaryPolicy.RING_ALIGNED.value,
    )
    parser.add_argument(
        "--localize-chunks-for-blender",
        action="store_true",
        help="Keep full scene global, but subtract per-chunk origins in optional chunk JSONs.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / "examples" / "stage9_production_scene.json",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ring_cfg = RingConfig()
    if args.rings is not None:
        n_rings = args.rings
    elif args.length_m is not None:
        if args.length_m <= 0:
            raise ValueError("--length-m must be positive")
        n_rings = math.ceil(args.length_m / ring_cfg.width_m)
    else:
        n_rings = 20

    assembly_cfg = TunnelAssemblyConfig(
        n_rings=n_rings,
        ring_width_m=ring_cfg.width_m,
        lateral_wavelength_m=args.lateral_wavelength_m,
        vertical_wavelength_m=args.vertical_wavelength_m,
        axis_noise_sigma_m=args.axis_noise_sigma,
        ring_rotation_strategy=RingRotationStrategy(args.rotation_strategy),
    )
    build = build_production_tunnel(
        ring_config=ring_cfg,
        assembly_config=assembly_cfg,
        surface_meshing=SurfaceMeshingConfig(
            max_sagitta_m=args.sagitta_mm / 1000.0
        ),
        include_bolts=not args.no_bolts,
        label_policy=LabelPolicy(args.label_policy),
        production_config=ProductionConfig(namespace=args.namespace),
        seed=args.seed,
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    write_scene_package_json(build.scene, output)

    production_objects = [
        obj for obj in build.scene.objects if obj.object_type.startswith("production_")
    ]
    summary = {
        "stage": 9,
        "seed": args.seed,
        "namespace": args.namespace,
        "ringCount": n_rings,
        "requestedLengthM": args.length_m,
        "generatedLengthM": build.assembly.length_by_chainage_m,
        "globalCoordinates": True,
        "ringWidthM": ring_cfg.width_m,
        "includeBolts": not args.no_bolts,
        "labelPolicy": args.label_policy,
        "sceneObjects": len(build.scene.objects),
        "productionInfrastructureObjects": len(production_objects),
        "productionRails": len(build.scene.objects_of_type("production_rail")),
        "productionTubes": len(build.scene.objects_of_type("production_tube")),
        "productionWalkways": len(build.scene.objects_of_type("production_walkway")),
        "productionPavements": len(build.scene.objects_of_type("production_pavement")),
        "railProfile": "stage9_generic_lowpoly_16",
        "alignmentStations": len(build.alignment_stations),
        "sceneJson": output.name,
    }

    if args.chunk_m is not None:
        packages = build_chunk_scene_packages(
            build,
            chunk_length_m=args.chunk_m,
            boundary_policy=ChunkBoundaryPolicy(args.chunk_policy),
            localize_coordinates=args.localize_chunks_for_blender,
        )
        chunk_dir = output.with_name(output.stem + "_chunks")
        chunk_dir.mkdir(parents=True, exist_ok=True)
        manifest = []
        for package in packages:
            chunk_meta = package.metadata["productionChunk"]
            chunk_id = int(chunk_meta["chunkID"])
            chunk_path = chunk_dir / f"chunk_{chunk_id:05d}.json"
            write_scene_package_json(package, chunk_path)
            manifest.append(
                {
                    "chunkID": chunk_id,
                    "path": chunk_path.name,
                    "startChainageM": chunk_meta["startChainageM"],
                    "endChainageM": chunk_meta["endChainageM"],
                    "ringIDs": chunk_meta["ringIDs"],
                    "vertexCoordinatesLocalized": chunk_meta[
                        "vertexCoordinatesLocalized"
                    ],
                    "chunkWorldOrigin": chunk_meta["chunkWorldOrigin"],
                }
            )
        manifest_path = chunk_dir / "manifest.json"
        manifest_path.write_text(
            json.dumps(
                {
                    "stage": 9,
                    "namespace": args.namespace,
                    "chunkLengthRequestedM": args.chunk_m,
                    "boundaryPolicy": args.chunk_policy,
                    "localizedForBlender": args.localize_chunks_for_blender,
                    "chunks": manifest,
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        summary.update(
            {
                "chunkCount": len(packages),
                "chunkLengthRequestedM": args.chunk_m,
                "chunkPolicy": args.chunk_policy,
                "chunksLocalizedForBlender": args.localize_chunks_for_blender,
                "chunkManifest": str(manifest_path.relative_to(output.parent)),
            }
        )

    summary_path = output.with_name(output.stem + "_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
