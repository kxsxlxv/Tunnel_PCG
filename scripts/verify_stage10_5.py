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


MODERN_TYPES = {
    "production_rail",
    "production_track_concrete",
    "production_lvt_block",
    "production_lvt_rubber_boot",
    "production_apc4_rail_pad",
    "production_apc4_fastening",
    "production_contact_rail",
    "production_contact_rail_cover_span",
    "production_contact_rail_support_block",
    "production_contact_rail_bracket",
    "production_contact_rail_insulator",
    "production_contact_rail_fastening_unit",
    "production_contact_rail_attachment_dowels",
    "production_contact_rail_support_hood",
    "production_service_cable",
    "production_cable_rack_r2k11",
    "production_water_main",
    "production_moscow_walkway",
    "production_moscow_civil_shell_ring",
}


def _periodic_ids(packages, wanted):
    result = {}
    for package in packages:
        for obj in package.objects:
            key = obj.custom_properties.get("persistentKey")
            if key in wanted:
                result[key] = obj.instance_id
    return result


def _continuous_parent_ids(packages, wanted):
    result = {}
    for package in packages:
        for obj in package.objects:
            key = obj.custom_properties.get("sourcePersistentKey")
            if key not in wanted:
                continue
            iid = int(obj.custom_properties["sourceInstanceID"])
            if key in result:
                assert result[key] == iid
            result[key] = iid
    return result


def main() -> None:
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=30,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-stress",
            moscow_profile=profile,
            moscow_stage="10.5",
        ),
        seed=5812,
    )

    meta = build.scene.metadata["productionGeometry"]
    assert meta["domainStage"] == "10.5"
    assert meta["servicePreset"] == "modern"
    assert meta["permanentWayStatus"] == "implemented_stage10_5_modern_LVT_M_APC4"
    assert meta["contactRailStatus"] == (
        "implemented_stage10_5_modern_segmented_cover_and_dedicated_support"
    )
    assert meta["civilShellStatus"] == "implemented_stage10_4_smooth_concentric_shell"
    assert meta["transitionalCivilGapStatus"] == "closed_by_stage10_4_moscow_shell"

    assert not build.scene.objects_of_type("production_sleeper")
    assert not build.scene.objects_of_type("production_baseplate")
    assert not build.scene.objects_of_type("production_contact_rail_cover")
    assert not build.scene.objects_of_type("production_tube")

    lvt_count = len(build.scene.objects_of_type("production_lvt_block"))
    assert lvt_count > 0
    assert lvt_count == int(meta["modernLVTSupportCount"])
    for obj_type in (
        "production_lvt_rubber_boot",
        "production_apc4_rail_pad",
        "production_apc4_fastening",
    ):
        assert len(build.scene.objects_of_type(obj_type)) == lvt_count

    support_count = int(meta["contactRailSupportCount"])
    assert support_count > 0
    for obj_type in (
        "production_contact_rail_support_block",
        "production_contact_rail_bracket",
        "production_contact_rail_insulator",
        "production_contact_rail_fastening_unit",
        "production_contact_rail_attachment_dowels",
        "production_contact_rail_support_hood",
    ):
        assert len(build.scene.objects_of_type(obj_type)) == support_count
    assert len(build.scene.objects_of_type("production_contact_rail_cover_span")) > 0
    assert meta["contactRailSupportSeparateFromRunningSupport"] is True
    assert meta["contactRailCoverEraMismatch"] is False

    civil_count = int(meta["moscowCivilRingCount"])
    assert civil_count > 0
    assert len(build.scene.objects_of_type("production_moscow_civil_shell_ring")) == civil_count
    assert len(build.scene.objects_of_type("production_moscow_walkway")) == 1

    assert len(build.scene.objects_of_type("production_service_cable")) == 22
    assert len(build.scene.objects_of_type("production_cable_rack_r2k11")) == 2 * civil_count
    assert meta["serviceCableRackFamily"] == "R2K11"
    assert int(meta["serviceCableRackHornCount"]) == 11
    assert meta["servicePipeStatus"] == (
        "implemented_normative_DN80_with_explicit_placement_fallback"
    )
    assert int(meta["serviceWaterMainCount"]) == 1
    assert int(meta["serviceWaterMainMinNominalDNmm"]) == 80
    water = build.scene.objects_of_type("production_water_main")
    assert len(water) == 1
    wp = water[0].custom_properties
    assert wp["positionRule"] == "above_UGR_weak_current_side"
    assert wp["exactProjectRouteResolved"] is False

    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: obj.object_type in MODERN_TYPES,
    )
    assert audit.duplicate_group_count == 0

    continuous_source = {
        spec.persistent_key: spec.instance_id
        for spec in build.asset_specs
    }
    periodic_source = {
        obj.custom_properties["persistentKey"]: obj.instance_id
        for obj in build.scene.objects
        if (
            obj.object_type in MODERN_TYPES
            and "eventChainageM" in obj.custom_properties
            and "persistentKey" in obj.custom_properties
        )
    }
    assert continuous_source
    assert periodic_source
    for chunk_m in (6.7, 9.4):
        packages = build_chunk_scene_packages(
            build,
            chunk_length_m=chunk_m,
            boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
        )
        assert _continuous_parent_ids(
            packages,
            continuous_source,
        ) == continuous_source
        assert _periodic_ids(
            packages,
            periodic_source,
        ) == periodic_source

    legacy = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=8,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        production_config=ProductionConfig(
            namespace="stage10-5-legacy-check",
            moscow_profile=profile,
            moscow_stage="10.5",
            moscow_service_preset="legacy",
        ),
        seed=5812,
    )
    lm = legacy.scene.metadata["productionGeometry"]
    assert lm["servicePreset"] == "legacy"
    assert len(legacy.scene.objects_of_type("production_sleeper")) > 0
    assert len(legacy.scene.objects_of_type("production_baseplate")) > 0
    assert len(legacy.scene.objects_of_type("production_lvt_block")) == 0
    assert len(legacy.scene.objects_of_type("production_contact_rail_cover")) == 1

    print(
        json.dumps(
            {
                "stage": "10.5",
                "schema_version": profile.schema_version,
                "service_preset": meta["servicePreset"],
                "length_m": build.assembly.length_by_chainage_m,
                "modern_lvt_support_count": lvt_count,
                "contact_support_count": support_count,
                "contact_cover_span_count": meta["contactRailCoverSpanCount"],
                "civil_ring_count": civil_count,
                "service_cable_count": meta["serviceCableCount"],
                "service_rack_count": meta["serviceCableRackCount"],
                "water_main_count": meta["serviceWaterMainCount"],
                "water_main_min_nominal_dn_mm": meta[
                    "serviceWaterMainMinNominalDNmm"
                ],
                "duplicate_modern_face_groups": audit.duplicate_group_count,
                "stable_continuous_parent_ids_across_chunk_sizes": True,
                "stable_periodic_ids_across_chunk_sizes": True,
                "continuous_sweep_alignment_compaction": meta.get(
                    "continuousSweepAlignmentCompaction"
                ),
                "rail_source_alignment_stations": int(
                    build.scene.objects_of_type("production_rail")[0]
                    .custom_properties["sourceAlignmentStationCount"]
                ),
                "rail_sweep_alignment_stations": int(
                    build.scene.objects_of_type("production_rail")[0]
                    .custom_properties["sweepAlignmentStationCount"]
                ),
                "legacy_timber_variant_selectable": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
