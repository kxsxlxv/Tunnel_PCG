from __future__ import annotations

import json
import math
from pathlib import Path
import time

from tunnel_scanner_core import (
    ChunkBoundaryPolicy,
    LabelPolicy,
    ProductionConfig,
    RingConfig,
    RingRotationStrategy,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_chunk_scene_packages,
    build_production_tunnel,
    build_procedural_nominal_tunnel,
    finalize_production_render_scene,
    plan_chunks,
    production_alignment_stations,
    sample_tunnel_assembly,
    stable_instance_id,
)


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "examples" / "stage9_verification.json"


def build_length(length_m: float, *, namespace: str):
    ring_cfg = RingConfig()
    n = math.ceil(length_m / ring_cfg.width_m)
    started = time.perf_counter()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=n,
            ring_width_m=ring_cfg.width_m,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(namespace=namespace),
        seed=5812,
    )
    elapsed = time.perf_counter() - started
    return build, elapsed


def main() -> None:
    ring_cfg = RingConfig()

    # Reference Stage-8 cap duplication versus production continuous assets.
    stage8 = build_procedural_nominal_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=5,
            ring_width_m=ring_cfg.width_m,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        include_ancillary=True,
        label_policy=LabelPolicy.STSD_COARSE,
        seed=99,
    )
    stage8_ancillary_audit = audit_exact_coincident_faces(
        stage8.scene,
        object_filter=lambda obj: obj.object_type.startswith("ancillary_"),
    )
    assert stage8_ancillary_audit.duplicate_group_count == 40

    hundred, time_100m = build_length(100.0, namespace="stress-100m")
    km, time_1km = build_length(1000.0, namespace="stress-1km")

    for build in (hundred, km):
        infrastructure_audit = audit_exact_coincident_faces(
            build.scene,
            object_filter=lambda obj: obj.object_type.startswith("production_"),
        )
        assert infrastructure_audit.duplicate_group_count == 0
        ids = [obj.instance_id for obj in build.scene.objects]
        assert len(ids) == len(set(ids))
        assert len(build.scene.objects_of_type("production_rail")) == 2
        assert len(build.scene.objects_of_type("production_tube")) == 6

    # Post-Boolean cap-strip equivalent on the no-bolt 100 m scene.
    before_lining_faces = sum(
        len(obj.faces) for obj in hundred.scene.objects_of_type("lining_segment")
    )
    cleaned = finalize_production_render_scene(hundred.scene)
    removed_lining_faces = cleaned.metadata["productionLiningCapStrip"]["removedFaces"]
    removed_interface_faces = cleaned.metadata[
        "productionSegmentInterfaceStrip"
    ]["facesRemoved"]
    after_lining_faces = sum(
        len(obj.faces) for obj in cleaned.objects_of_type("lining_segment")
    )
    assert removed_lining_faces > 0
    assert removed_interface_faces == 2 * 6 * hundred.assembly.config.n_rings
    assert (
        before_lining_faces - after_lining_faces
        == removed_lining_faces + removed_interface_faces
    )
    finalized_audit = audit_exact_coincident_faces(cleaned)
    assert finalized_audit.duplicate_group_count == 0

    # Chunking is optional and remains identity-preserving.
    chunks_50 = plan_chunks(km.assembly, chunk_length_m=50.0)
    assert chunks_50
    for chunk in chunks_50:
        assert math.isclose(
            chunk.start_chainage_m / ring_cfg.width_m,
            round(chunk.start_chainage_m / ring_cfg.width_m),
            abs_tol=1e-10,
        )
        assert math.isclose(
            chunk.end_chainage_m / ring_cfg.width_m,
            round(chunk.end_chainage_m / ring_cfg.width_m),
            abs_tol=1e-10,
        )

    sample_chunks = build_chunk_scene_packages(
        hundred,
        chunk_length_m=25.0,
        boundary_policy=ChunkBoundaryPolicy.RING_ALIGNED,
    )
    sample_chunks_other = build_chunk_scene_packages(
        hundred,
        chunk_length_m=40.0,
        boundary_policy=ChunkBoundaryPolicy.RING_ALIGNED,
    )
    parent_ids_a = {
        obj.custom_properties["sourcePersistentKey"]: obj.custom_properties[
            "sourceInstanceID"
        ]
        for package in sample_chunks
        for obj in package.objects
        if obj.object_type.startswith("production_")
    }
    parent_ids_b = {
        obj.custom_properties["sourcePersistentKey"]: obj.custom_properties[
            "sourceInstanceID"
        ]
        for package in sample_chunks_other
        for obj in package.objects
        if obj.object_type.startswith("production_")
    }
    assert parent_ids_a == parent_ids_b

    # Five-kilometre coordinate/alignment stress without allocating every lining mesh.
    n_5km = math.ceil(5000.0 / ring_cfg.width_m)
    assembly_5km = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=n_5km,
            ring_width_m=ring_cfg.width_m,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        seed=777,
    )
    stations_5km = production_alignment_stations(assembly_5km)
    assert assembly_5km.length_by_chainage_m >= 5000.0
    assert len(stations_5km) == 2 * n_5km + 1
    assert all(
        b.chainage_m > a.chainage_m
        for a, b in zip(stations_5km, stations_5km[1:])
    )
    assert stations_5km[-1].world_y_m > 4999.0

    # Rail complexity remains linear and modest.
    rail = km.scene.objects_of_type("production_rail")[0]
    rail_vertices = len(rail.vertices)
    rail_faces = len(rail.faces)
    expected_rail_vertices = (
        rail.custom_properties["productionCrossSectionVertices"]
        * rail.custom_properties["productionStationCount"]
    )
    assert rail_vertices == expected_rail_vertices

    result = {
        "stage": 9,
        "stage8FiveRingAncillaryDuplicateCapGroups": (
            stage8_ancillary_audit.duplicate_group_count
        ),
        "productionInfrastructureDuplicateFaceGroups": 0,
        "hundredMetre": {
            "rings": hundred.assembly.config.n_rings,
            "generatedLengthM": hundred.assembly.length_by_chainage_m,
            "sceneObjects": len(hundred.scene.objects),
            "generationSecondsCI": time_100m,
            "liningCapFacesRemovedByFinalizer": removed_lining_faces,
            "segmentInterfaceFacesRemovedByFinalizer": removed_interface_faces,
            "exactDuplicateFaceGroupsAfterFinalizer": finalized_audit.duplicate_group_count,
        },
        "oneKilometre": {
            "rings": km.assembly.config.n_rings,
            "generatedLengthM": km.assembly.length_by_chainage_m,
            "sceneObjects": len(km.scene.objects),
            "generationSecondsCI": time_1km,
            "alignmentStations": len(km.alignment_stations),
            "railVerticesPerRail": rail_vertices,
            "railFacesPerRail": rail_faces,
            "ringAligned50mChunkCount": len(chunks_50),
        },
        "fiveKilometreAlignment": {
            "rings": n_5km,
            "generatedLengthM": assembly_5km.length_by_chainage_m,
            "alignmentStations": len(stations_5km),
            "lastWorldYM": stations_5km[-1].world_y_m,
        },
        "stableParentAssetIDsAcrossChunkLengths": "PASS",
        "globalDoubleCoordinatesNoMandatoryRebase": "PASS",
        "result": "PASS",
    }
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
