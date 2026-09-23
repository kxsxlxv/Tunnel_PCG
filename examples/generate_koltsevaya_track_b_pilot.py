from __future__ import annotations

"""Generate the first real-route Stage 10.5 geometry integration pilot.

The horizontal alignment is the dated OSM-derived KOLTSEVAYA_TRACK_B snapshot
for Belorusskaya -> Krasnopresnenskaya -> Kievskaya -> Park Kultury. The Z
profile is deliberately synthetic and must never be presented as as-built.
"""

import argparse
from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace
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
    build_stage10_5_rc_modern_chunk_plan,
    build_stage10_5_rc_modern_chunk_scene_package,
    load_frame_alignment_geojson,
    load_stage10_initial_moscow_profile,
    write_scene_package_json,
)


RESEARCH_DIR = (
    PROJECT_ROOT
    / "research"
    / "moscow_metro_tunnels"
    / "examples"
    / "koltsevaya_line_v0"
)
DEFAULT_ALIGNMENT = (
    RESEARCH_DIR
    / "koltsevaya_track_b_belorusskaya_park_kultury_geometry_test_3d.geojson"
)
DEFAULT_HANDOFF = (
    RESEARCH_DIR
    / "koltsevaya_track_b_belorusskaya_park_kultury_handoff.json"
)
DEFAULT_PROFILE = (
    RESEARCH_DIR
    / "koltsevaya_track_b_belorusskaya_park_kultury_geometry_test_profile.json"
)
DEFAULT_OUTPUT = (
    PROJECT_ROOT
    / "examples"
    / "koltsevaya_track_b_belorusskaya_park_kultury_pilot.json"
)

_WORKER_PLAN = None
_WORKER_CHUNK_DIR: Path | None = None
_WORKER_LOCALIZE = True
_WORKER_COMPACT = True
_WORKER_PROTOTYPES = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--alignment", type=Path, default=DEFAULT_ALIGNMENT)
    parser.add_argument("--handoff", type=Path, default=DEFAULT_HANDOFF)
    parser.add_argument("--vertical-profile", type=Path, default=DEFAULT_PROFILE)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--chunk-m", type=float, default=20.0)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument("--seed", type=int, default=5812)
    parser.add_argument(
        "--namespace",
        default="koltsevaya-track-b-bel-krp-kiev-park-geometry-test-v1",
    )
    parser.add_argument(
        "--civil-topology",
        choices=("kba", "ten_equal"),
        default="kba",
    )
    parser.add_argument(
        "--rotation-strategy",
        choices=tuple(strategy.value for strategy in RingRotationStrategy),
        default=RingRotationStrategy.RINGWISE_GAUSSIAN.value,
    )
    parser.add_argument("--sagitta-mm", type=float, default=2.0)
    parser.add_argument("--no-bolts", action="store_true")
    parser.add_argument("--pretty-json", action="store_true")
    parser.add_argument("--prototype-json", action="store_true")
    parser.add_argument(
        "--global-chunk-coordinates",
        action="store_true",
        help=(
            "Keep chunk vertices in route-global coordinates. The default "
            "localizes every chunk for Blender float precision."
        ),
    )
    return parser.parse_args()


def _station_sections(handoff: dict) -> list[dict]:
    events = sorted(
        handoff["station_events"],
        key=lambda item: float(item["track_b_osm_plan_chainage_m"]),
    )
    sections = []
    for left, right in zip(events, events[1:]):
        sections.append(
            {
                "id": (
                    f"{left['station']}__{right['station']}"
                    .replace(" ", "_")
                    .replace("ё", "е")
                ),
                "fromStation": left["station"],
                "toStation": right["station"],
                "startChainageM": float(
                    left["track_b_osm_plan_chainage_m"]
                ),
                "endChainageM": float(
                    right["track_b_osm_plan_chainage_m"]
                ),
            }
        )
    return sections


def _section_for_chainage(sections: list[dict], chainage_m: float) -> str:
    for index, section in enumerate(sections):
        start = float(section["startChainageM"])
        end = float(section["endChainageM"])
        if start <= chainage_m < end:
            return str(section["id"])
        if index == len(sections) - 1 and math.isclose(
            chainage_m,
            end,
            abs_tol=1e-9,
        ):
            return str(section["id"])
    return "UNRESOLVED_SECTION"


def _events_in_window(
    events: list[dict],
    start_m: float,
    end_m: float,
    *,
    include_end: bool,
) -> list[str]:
    result = []
    for event in events:
        chainage = float(event["track_b_osm_plan_chainage_m"])
        inside = (
            start_m <= chainage <= end_m
            if include_end
            else start_m <= chainage < end_m
        )
        if inside:
            result.append(str(event["event_id"]))
    return result


def _init_worker(
    plan,
    chunk_dir: Path,
    localize: bool,
    compact: bool,
    prototypes: bool,
) -> None:
    global _WORKER_PLAN
    global _WORKER_CHUNK_DIR
    global _WORKER_LOCALIZE
    global _WORKER_COMPACT
    global _WORKER_PROTOTYPES
    _WORKER_PLAN = plan
    _WORKER_CHUNK_DIR = chunk_dir
    _WORKER_LOCALIZE = localize
    _WORKER_COMPACT = compact
    _WORKER_PROTOTYPES = prototypes


def _write_worker(chunk_id: int) -> dict:
    if _WORKER_PLAN is None or _WORKER_CHUNK_DIR is None:
        raise RuntimeError("pilot chunk worker was not initialized")
    package = build_stage10_5_rc_modern_chunk_scene_package(
        _WORKER_PLAN,
        chunk_id,
        localize_coordinates=_WORKER_LOCALIZE,
    )
    meta = package.metadata["productionChunk"]
    path = _WORKER_CHUNK_DIR / f"chunk_{chunk_id:05d}.json"
    write_scene_package_json(
        package,
        path,
        compact=_WORKER_COMPACT,
        prototype_instances=_WORKER_PROTOTYPES,
    )
    return {
        "chunkID": int(chunk_id),
        "path": path.name,
        "startChainageM": float(meta["startChainageM"]),
        "endChainageM": float(meta["endChainageM"]),
        "ringIDs": list(meta["ringIDs"]),
        "objectCount": len(package.objects),
        "vertexCoordinatesLocalized": bool(
            meta["vertexCoordinatesLocalized"]
        ),
        "chunkWorldOrigin": list(meta["chunkWorldOrigin"]),
    }


def main() -> None:
    args = parse_args()
    if args.chunk_m <= 0.0:
        raise ValueError("--chunk-m must be positive")
    if args.workers < 1:
        raise ValueError("--workers must be >=1")
    if args.sagitta_mm <= 0.0:
        raise ValueError("--sagitta-mm must be positive")

    handoff = json.loads(args.handoff.read_text(encoding="utf-8"))
    vertical_profile = json.loads(
        args.vertical_profile.read_text(encoding="utf-8")
    )
    scope = handoff["scope"]
    if scope["track_id"] != "KOLTSEVAYA_TRACK_B":
        raise ValueError("pilot handoff is not KOLTSEVAYA_TRACK_B")
    if scope["direction"] != "counterclockwise":
        raise ValueError("pilot handoff direction is not counterclockwise")
    if scope["engineering_z_status"] != "Z_UNRESOLVED":
        raise ValueError("unexpected source-truth vertical status")
    if (
        vertical_profile["status"]
        != "SYNTHETIC_GEOMETRY_TEST_ONLY_NOT_AS_BUILT"
    ):
        raise ValueError("pilot vertical profile lost synthetic-only status")

    alignment = load_frame_alignment_geojson(
        args.alignment,
        expected_track_id="KOLTSEVAYA_TRACK_B",
        expected_direction="counterclockwise",
    )
    route_length_m = float(alignment[-1].chainage_m)
    if not math.isclose(
        route_length_m,
        float(scope["segment_length_osm_plan_m"]),
        abs_tol=1e-3,
    ):
        raise ValueError("alignment/handoff route length mismatch")

    nominal_source_width_m = 1.35
    source_ring_count = math.ceil(route_length_m / nominal_source_width_m)
    scaffold_width_m = route_length_m / source_ring_count
    ring_config = RingConfig(width_m=scaffold_width_m)
    assembly_config = TunnelAssemblyConfig(
        n_rings=source_ring_count,
        ring_width_m=scaffold_width_m,
        displacement_amplitude_m=0.0,
        axis_noise_sigma_m=0.0,
        ring_rotation_strategy=RingRotationStrategy(
            args.rotation_strategy
        ),
    )
    surface_meshing = SurfaceMeshingConfig(
        max_sagitta_m=args.sagitta_mm / 1000.0
    )
    profile = load_stage10_initial_moscow_profile(
        civil_archetype="rc_block_6100_5600"
    )
    production_config = ProductionConfig(
        namespace=args.namespace,
        moscow_profile=profile,
        moscow_stage="10.5",
        moscow_service_preset="modern",
        moscow_civil_topology=args.civil_topology,
    )

    alignment_metadata = {
        "trackID": "KOLTSEVAYA_TRACK_B",
        "operationalTrackNumber": "II",
        "direction": "counterclockwise",
        "ringPosition": "outer",
        "routeRelationID": int(scope["osm_route_relation_id"]),
        "segmentStationSequence": list(
            scope["segment_station_sequence"]
        ),
        "routeLengthM": route_length_m,
        "horizontalStatus": (
            handoff["horizontal_provenance"][
                "geometry_authority_for_this_handoff"
            ]["status"]
        ),
        "horizontalSourceID": (
            handoff["horizontal_provenance"][
                "geometry_authority_for_this_handoff"
            ]["source_id"]
        ),
        "sourceTruthVerticalStatus": scope["engineering_z_status"],
        "runtimeVerticalStatus": vertical_profile["status"],
        "notAsBuilt": True,
        "alignmentFile": args.alignment.name,
        "handoffFile": args.handoff.name,
        "verticalProfileFile": args.vertical_profile.name,
        "sampleCount": len(alignment),
        "frameMode": "zero_roll_tangent_gravity_up_v1",
        "sourceScaffoldNominalRingWidthM": nominal_source_width_m,
        "sourceScaffoldExactRingWidthM": scaffold_width_m,
        "sourceScaffoldRingCount": source_ring_count,
        "sourceScaffoldGeometryReplaced": True,
    }

    plan = build_stage10_5_rc_modern_chunk_plan(
        chunk_length_m=args.chunk_m,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        ring_config=ring_config,
        assembly_config=assembly_config,
        surface_meshing=surface_meshing,
        include_bolts=not args.no_bolts,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=production_config,
        seed=args.seed,
        alignment_stations=alignment,
        alignment_metadata=alignment_metadata,
    )
    # Keep route identity at package top-level as well as productionGeometry.
    plan = replace(
        plan,
        metadata={
            **dict(plan.metadata),
            "routePilot": alignment_metadata,
        },
    )

    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    chunk_dir = output.with_name(output.stem + "_chunks")
    chunk_dir.mkdir(parents=True, exist_ok=True)
    localize = not args.global_chunk_coordinates
    compact = not args.pretty_json
    effective_workers = min(args.workers, max(1, len(plan.chunks)))

    if effective_workers == 1:
        entries = []
        _init_worker(
            plan,
            chunk_dir,
            localize,
            compact,
            args.prototype_json,
        )
        for chunk in plan.chunks:
            entries.append(_write_worker(chunk.chunk_id))
    else:
        with ProcessPoolExecutor(
            max_workers=effective_workers,
            initializer=_init_worker,
            initargs=(
                plan,
                chunk_dir,
                localize,
                compact,
                args.prototype_json,
            ),
        ) as executor:
            entries = list(
                executor.map(
                    _write_worker,
                    range(len(plan.chunks)),
                )
            )

    entries.sort(key=lambda item: int(item["chunkID"]))
    sections = _station_sections(handoff)
    station_events = list(handoff["station_events"])
    junction_events = [
        event
        for event in handoff["junction_events"]
        if "track_b_osm_plan_chainage_m" in event
    ]
    for index, entry in enumerate(entries):
        start = float(entry["startChainageM"])
        end = float(entry["endChainageM"])
        midpoint = 0.5 * (start + end)
        entry["interstationSection"] = _section_for_chainage(
            sections,
            midpoint,
        )
        include_end = index == len(entries) - 1
        entry["stationEvents"] = _events_in_window(
            station_events,
            start,
            end,
            include_end=include_end,
        )
        entry["junctionEvents"] = _events_in_window(
            junction_events,
            start,
            end,
            include_end=include_end,
        )

    production_meta = plan.metadata["productionGeometry"]
    manifest = {
        "stage": "10.5",
        "pilot": "KOLTSEVAYA_TRACK_B_BELORUSSKAYA_PARK_KULTURY",
        "trackID": "KOLTSEVAYA_TRACK_B",
        "direction": "counterclockwise",
        "namespace": args.namespace,
        "routeLengthM": route_length_m,
        "alignmentMode": production_meta["alignmentMode"],
        "alignmentFrameAware": production_meta["alignmentFrameAware"],
        "horizontalStatus": alignment_metadata["horizontalStatus"],
        "sourceTruthVerticalStatus": "Z_UNRESOLVED",
        "runtimeVerticalStatus": (
            "SYNTHETIC_GEOMETRY_TEST_ONLY_NOT_AS_BUILT"
        ),
        "mayClaimAsBuilt": False,
        "chunkLengthRequestedM": args.chunk_m,
        "boundaryPolicy": ChunkBoundaryPolicy.EXACT_LENGTH.value,
        "chunkFirstGeneration": True,
        "localizedForBlender": localize,
        "prototypeSceneJson": bool(args.prototype_json),
        "parallelChunkWorkers": effective_workers,
        "moscowProfileID": profile.profile_id,
        "moscowProfileSHA256": profile.provenance.canonical_sha256,
        "civilTopology": args.civil_topology,
        "surfaceToleranceM": surface_meshing.max_sagitta_m,
        "routeSections": sections,
        "stationEvents": station_events,
        "junctionEvents": handoff["junction_events"],
        "mainlineEdges": handoff["mainline_edges"],
        "alignmentInput": str(args.alignment),
        "handoffInput": str(args.handoff),
        "verticalProfileInput": str(args.vertical_profile),
        "chunks": entries,
    }
    manifest_path = chunk_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    object_total = sum(int(entry["objectCount"]) for entry in entries)
    summary = {
        "stage": "10.5",
        "pilot": manifest["pilot"],
        "trackID": manifest["trackID"],
        "direction": manifest["direction"],
        "namespace": args.namespace,
        "routeLengthM": route_length_m,
        "alignmentStations": len(alignment),
        "alignmentMode": manifest["alignmentMode"],
        "alignmentFrameAware": manifest["alignmentFrameAware"],
        "horizontalStatus": manifest["horizontalStatus"],
        "sourceTruthVerticalStatus": manifest[
            "sourceTruthVerticalStatus"
        ],
        "runtimeVerticalStatus": manifest["runtimeVerticalStatus"],
        "mayClaimAsBuilt": False,
        "sourceScaffoldRingCount": source_ring_count,
        "sourceScaffoldRingWidthM": scaffold_width_m,
        "moscowCivilRingCount": production_meta[
            "moscowCivilRingCount"
        ],
        "modernLVTSupportCount": production_meta[
            "modernLVTSupportCount"
        ],
        "contactRailSupportCount": production_meta[
            "contactRailSupportCount"
        ],
        "serviceCableRackCount": production_meta[
            "serviceCableRackCount"
        ],
        "civilBoltHeadCount": production_meta[
            "moscowCivilBoltHeadCount"
        ],
        "expectedBlenderBoltBooleanOps": production_meta[
            "moscowCivilExpectedBlenderBoltBooleanOps"
        ],
        "chunkCount": len(entries),
        "chunkLengthRequestedM": args.chunk_m,
        "serializedChunkObjectCount": object_total,
        "chunksLocalizedForBlender": localize,
        "parallelChunkWorkers": effective_workers,
        "compactSceneJson": compact,
        "prototypeSceneJson": bool(args.prototype_json),
        "chunkManifest": str(manifest_path.relative_to(output.parent)),
        "sceneJson": None,
    }
    summary_path = output.with_name(output.stem + "_summary.json")
    summary_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
