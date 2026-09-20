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
    load_stage10_initial_moscow_profile,
)
from tunnel_scanner_core.scene_io import write_scene_package_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Generate the Stage 10 production scene using the current "
            "Stage 10.1 Moscow profile contract (R65/UGR/gauge)."
        )
    )
    size = parser.add_mutually_exclusive_group()
    size.add_argument("--rings", type=int, default=None)
    size.add_argument("--length-m", type=float, default=None)
    parser.add_argument("--seed", type=int, default=5812)
    parser.add_argument("--namespace", default="stage10")
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
        "--chunks-only",
        action="store_true",
        help=(
            "When --chunk-m is set, skip writing the monolithic full-scene JSON. "
            "The geometry is still generated in global coordinates internally; only "
            "the serialized output is partitioned."
        ),
    )
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
        default=PROJECT_ROOT / "examples" / "stage10_production_scene.json",
    )
    return parser.parse_args()


def _validate_stage10_1_build(build, profile) -> tuple[float, list[float]]:
    meta = build.scene.metadata["productionGeometry"]
    if meta.get("domainStage") != "10.1":
        raise AssertionError("generated scene is not tagged as Stage 10.1")
    if meta.get("moscowProfileID") != profile.profile_id:
        raise AssertionError("generated scene Moscow profile ID mismatch")
    if meta.get("moscowProfileSHA256") != profile.provenance.canonical_sha256:
        raise AssertionError("generated scene Moscow profile SHA mismatch")
    if meta.get("railProfile") != "stage10_1_r65_gost_r51685_2022":
        raise AssertionError("generated scene does not use the Stage 10.1 R65 profile")

    rails = build.scene.objects_of_type("production_rail")
    if len(rails) != 2:
        raise AssertionError(f"expected two production rails, got {len(rails)}")
    working_faces = sorted(
        float(rail.custom_properties["railInnerWorkingFaceX"])
        for rail in rails
    )
    gauge = working_faces[1] - working_faces[0]
    if not math.isclose(gauge, profile.track.gauge_m, abs_tol=2e-12):
        raise AssertionError(
            f"working-face gauge {gauge!r} does not match {profile.track.gauge_m!r}"
        )
    for rail in rails:
        props = rail.custom_properties
        if props.get("railProfile") != "stage10_1_r65_gost_r51685_2022":
            raise AssertionError(f"{rail.name}: unexpected rail profile")
        if not math.isclose(
            float(props["railTopProfileZLocalM"]),
            0.0,
            abs_tol=2e-12,
        ):
            raise AssertionError(f"{rail.name}: rail top is not at profile UGR")
        if not math.isclose(
            float(props["railTopCoreZLocalM"]),
            profile.coordinate.profile_z_to_core_z_offset_m,
            abs_tol=2e-12,
        ):
            raise AssertionError(f"{rail.name}: profile UGR was not translated to core Z")
        if not math.isclose(
            float(props["gaugeMeasurementBelowUGRM"]),
            0.013,
            abs_tol=2e-12,
        ):
            raise AssertionError(f"{rail.name}: unexpected gauge measurement plane")
    return gauge, working_faces


def main() -> None:
    args = parse_args()
    profile = load_stage10_initial_moscow_profile()
    ring_cfg = RingConfig()
    if args.rings is not None:
        if args.rings <= 0:
            raise ValueError("--rings must be positive")
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
        production_config=ProductionConfig(
            namespace=args.namespace,
            moscow_profile=profile,
        ),
        seed=args.seed,
    )
    working_face_gauge, working_faces = _validate_stage10_1_build(build, profile)

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if args.chunks_only and args.chunk_m is None:
        raise ValueError("--chunks-only requires --chunk-m")
    if not args.chunks_only:
        write_scene_package_json(build.scene, output)

    production_objects = [
        obj for obj in build.scene.objects if obj.object_type.startswith("production_")
    ]
    production_meta = build.scene.metadata["productionGeometry"]
    rails = build.scene.objects_of_type("production_rail")
    summary = {
        "stage": "10.1",
        "seed": args.seed,
        "namespace": args.namespace,
        "ringCount": n_rings,
        "requestedLengthM": args.length_m,
        "generatedLengthM": build.assembly.length_by_chainage_m,
        "globalCoordinates": True,
        "sourceRingWidthM": ring_cfg.width_m,
        "includeBolts": not args.no_bolts,
        "labelPolicy": args.label_policy,
        "sceneObjects": len(build.scene.objects),
        "productionInfrastructureObjects": len(production_objects),
        "productionRails": len(rails),
        "productionTubes": len(build.scene.objects_of_type("production_tube")),
        "productionWalkways": len(build.scene.objects_of_type("production_walkway")),
        "productionPavements": len(build.scene.objects_of_type("production_pavement")),
        "railProfile": production_meta["railProfile"],
        "railProfileVertices": int(rails[0].custom_properties["railProfileVertices"]),
        "workingFaceGaugeM": working_face_gauge,
        "innerWorkingFacesX": working_faces,
        "gaugeMeasurementBelowUGRM": profile.track.gauge_measurement_below_ugr_m,
        "ugrProfileZLocalM": profile.datums.ugr_z_m,
        "ugrCoreZLocalM": production_meta["ugrCoreZLocalM"],
        "profileZToCoreZOffsetM": production_meta["profileZToCoreZOffsetM"],
        "moscowProfileID": profile.profile_id,
        "moscowProfileSHA256": profile.provenance.canonical_sha256,
        "permanentWayStatus": production_meta["permanentWayStatus"],
        "contactRailStatus": production_meta["contactRailStatus"],
        "civilShellStatus": production_meta["civilShellStatus"],
        "nonRailInfrastructureStatus": production_meta["nonRailInfrastructureStatus"],
        "alignmentStations": len(build.alignment_stations),
        "sceneJson": None if args.chunks_only else output.name,
        "fullSceneSerialized": not args.chunks_only,
        "tunnelInstanceID": production_meta["tunnelInstanceID"],
        "infrastructureAssets": [
            {
                "persistentKey": spec.persistent_key,
                "instanceID": spec.instance_id,
                "objectType": spec.object_type,
                "category": spec.category,
            }
            for spec in build.asset_specs
        ],
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
                    "stage": "10.1",
                    "namespace": args.namespace,
                    "moscowProfileID": profile.profile_id,
                    "moscowProfileSHA256": profile.provenance.canonical_sha256,
                    "tunnelInstanceID": production_meta["tunnelInstanceID"],
                    "chunkLengthRequestedM": args.chunk_m,
                    "boundaryPolicy": args.chunk_policy,
                    "localizedForBlender": args.localize_chunks_for_blender,
                    "globalCoordinatesAreCanonical": True,
                    "infrastructureAssets": [
                        {
                            "persistentKey": spec.persistent_key,
                            "instanceID": spec.instance_id,
                            "objectType": spec.object_type,
                            "category": spec.category,
                        }
                        for spec in build.asset_specs
                    ],
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
