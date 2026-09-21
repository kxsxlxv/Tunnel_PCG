from __future__ import annotations

import json
import math

from tunnel_scanner_core import (
    ChunkBoundaryPolicy,
    ProductionConfig,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_chunk_scene_packages,
    build_production_tunnel,
    load_stage10_initial_moscow_profile,
)


def _civil_parent_ids(packages):
    result = {}
    for package in packages:
        for obj in package.objects_of_type("production_moscow_civil_shell_ring"):
            key = obj.custom_properties.get("persistentKey")
            if key is not None:
                result[str(key)] = int(obj.instance_id)
    return result


def main() -> None:
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=30,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=True,
        production_config=ProductionConfig(
            namespace="stage10-4-stress",
            moscow_profile=profile,
            moscow_stage="10.4",
        ),
        seed=5812,
    )

    meta = build.scene.metadata["productionGeometry"]
    assert meta["domainStage"] == "10.4"
    assert meta["stage9CivilGeometryRemoved"] is True
    assert meta["civilShellStatus"] == (
        "implemented_stage10_4_cast_iron_smooth_envelope_detail_deferred"
    )
    assert meta["moscowCivilCompositeDetailStatus"] == (
        "cast_iron_detail_deferred_pending_research"
    )
    assert meta["walkwayStatus"] == "implemented_stage10_4_source_backed_geometry"
    assert meta["transitionalCivilGapStatus"] == "closed_by_stage10_4_moscow_shell"

    assert not build.scene.objects_of_type("lining_segment")
    assert not build.scene.objects_of_type("bolt_head")
    assert not build.scene.objects_of_type("bolt_pocket_cutter")
    assert not build.scene.objects_of_type("production_walkway")

    civil = build.scene.objects_of_type("production_moscow_civil_shell_ring")
    walkway = build.scene.objects_of_type("production_moscow_walkway")
    concrete = build.scene.objects_of_type("production_track_concrete")
    assert len(civil) == 41
    details = build.scene.objects_of_type(
        "production_moscow_civil_detail_ribs"
    )
    bolt_details = build.scene.objects_of_type(
        "production_moscow_civil_bolt_heads"
    )
    assert not details
    assert not bolt_details
    assert int(meta["moscowCivilDetailRibObjectCount"]) == 0
    assert int(meta["moscowCivilBoltObjectCount"]) == 0
    assert int(meta["moscowCivilBoltHeadCount"]) == 0
    assert meta["moscowCivilBoltsEnabled"] is False
    assert int(meta["moscowCivilRenderedBlockCount"]) == 0
    assert len(walkway) == 1
    assert len(concrete) == 1
    assert int(meta["moscowCivilRingCount"]) == len(civil)
    assert math.isclose(float(meta["moscowCivilRingPitchM"]), 1.0, abs_tol=2e-12)

    for ring in civil:
        p = ring.custom_properties
        assert math.isclose(float(p["intradosRadiusM"]), 2.55, abs_tol=2e-12)
        assert math.isclose(float(p["extradosRadiusM"]), 2.75, abs_tol=2e-12)
        assert math.isclose(float(p["structuralDepthM"]), 0.20, abs_tol=2e-12)
        assert p["seriesAccurateTubingLOD0"] is False
        assert p["coarseSegmentCountIsGeometry"] is False
        assert p["civilRenderMode"] == (
            "source_sized_smooth_cast_iron_envelope_detail_deferred"
        )
        assert p["stage9LikeCurvedSegmentConstruction"] is False
        assert p["internalRingEndCaps"] is False
    assert civil[-1].custom_properties["partialFinalRing"] is True

    wp = walkway[0].custom_properties
    assert math.isclose(float(wp["walkwayTopProfileZM"]), 0.2, abs_tol=2e-12)
    assert math.isclose(float(wp["walkwayInnerEdgeProfileXM"]), 1.66, abs_tol=2e-12)
    assert math.isclose(
        float(wp["walkwayOuterEdgeProfileXM"]),
        2.083650643,
        abs_tol=2e-9,
    )
    assert wp["trackConcreteContactFacesOmitted"] is True
    assert wp["liningContactFacesOmitted"] is True

    cp = concrete[0].custom_properties
    assert cp["physicalBottomSurface"] == "moscow_5100_intrados"
    assert cp["walkwayShoulderPartitioned"] is True
    assert cp["liningContactFacesOmitted"] is True

    # Contact rail and permanent way remain unchanged through civil replacement.
    assert len(build.scene.objects_of_type("production_rail")) == 2
    assert len(build.scene.objects_of_type("production_contact_rail")) == 1
    assert len(build.scene.objects_of_type("production_contact_rail_cover")) == 1
    assert meta["contactRailStatus"] == (
        "implemented_stage10_3_initial_geometry_with_explicit_fallbacks"
    )
    assert meta["permanentWayStatus"] == "implemented_stage10_2_initial_geometry"

    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: obj.object_type.startswith("production_"),
    )
    assert audit.duplicate_group_count == 0

    chunks_a = build_chunk_scene_packages(
        build,
        chunk_length_m=6.7,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )
    chunks_b = build_chunk_scene_packages(
        build,
        chunk_length_m=9.4,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )
    ids_a = _civil_parent_ids(chunks_a)
    ids_b = _civil_parent_ids(chunks_b)
    source_ids = {
        str(obj.custom_properties["persistentKey"]): int(obj.instance_id)
        for obj in civil
    }
    assert ids_a == source_ids
    assert ids_b == source_ids

    print(
        json.dumps(
            {
                "stage": "10.4",
                "profile_id": profile.profile_id,
                "schema_version": profile.schema_version,
                "source_stage9_rings": build.assembly.config.n_rings,
                "length_m": build.assembly.length_by_chainage_m,
                "moscow_civil_ring_count": len(civil),
                "moscow_civil_detail_rib_count": 0,
                "moscow_civil_bolt_object_count": 0,
                "moscow_civil_bolt_head_count": 0,
                "moscow_civil_ring_pitch_m": 1.0,
                "intrados_radius_m": 2.55,
                "extrados_radius_m": 2.75,
                "structural_depth_m": 0.20,
                "walkway_top_profile_z_m": 0.20,
                "walkway_inner_edge_profile_x_m": 1.66,
                "walkway_outer_edge_profile_x_m": 2.083650643,
                "stage9_lining_objects": 0,
                "duplicate_production_face_groups": audit.duplicate_group_count,
                "stable_civil_parent_ids_across_chunk_sizes": True,
                "transitional_civil_gap_closed": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
