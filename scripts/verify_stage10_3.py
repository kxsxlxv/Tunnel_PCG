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
    contact_support_chainages,
    load_stage10_initial_moscow_profile,
)


CONTACT_TYPES = {
    "production_contact_rail",
    "production_contact_rail_cover",
    "production_contact_rail_bracket",
    "production_contact_rail_insulator",
    "production_contact_rail_attachment_screws",
    "production_contact_rail_fastening_unit",
}


def _contact_parent_ids(packages):
    result = {}
    for package in packages:
        for obj in package.objects:
            if obj.object_type not in CONTACT_TYPES:
                continue
            key = obj.custom_properties.get(
                "sourcePersistentKey",
                obj.custom_properties.get("persistentKey"),
            )
            iid = obj.custom_properties.get(
                "sourceInstanceID",
                obj.instance_id,
            )
            if key is not None:
                result[str(key)] = int(iid)
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
            namespace="stage10-3-stress",
            moscow_profile=profile,
            moscow_stage="10.3",
        ),
        seed=5812,
    )

    meta = build.scene.metadata["productionGeometry"]
    assert meta["domainStage"] == "10.3"
    assert meta["permanentWayStatus"] == "implemented_stage10_2_initial_geometry"
    assert meta["contactRailStatus"] == (
        "implemented_stage10_3_initial_geometry_with_explicit_fallbacks"
    )
    assert meta["civilShellStatus"] == "deferred_to_stage10_4"

    contact = build.scene.objects_of_type("production_contact_rail")
    cover = build.scene.objects_of_type("production_contact_rail_cover")
    assert len(contact) == 1
    assert len(cover) == 1

    cp = contact[0].custom_properties
    assert math.isclose(
        float(cp["contactRailAxisProfileXM"]),
        -1.450,
        abs_tol=2e-12,
    )
    assert math.isclose(
        float(cp["workingSurfaceProfileZM"]),
        0.160,
        abs_tol=2e-12,
    )
    assert math.isclose(
        float(cp["workingSurfaceCoreZM"]),
        -1.510,
        abs_tol=2e-12,
    )
    assert cp["horizontalReference"] == "nearest_running_rail_inner_working_face"
    assert cp["eraMismatch"] is True

    cv = cover[0].custom_properties
    assert cv["eraMismatch"] is True
    assert cv["modernFallbackIsNotHistoricalClaim"] is True
    assert math.isclose(float(cv["historicalSideGapM"]), 0.020, abs_tol=2e-12)
    assert math.isclose(float(cv["outerBaseWidthM"]), 0.134, abs_tol=2e-12)
    assert math.isclose(float(cv["outerTopWidthM"]), 0.112, abs_tol=2e-12)

    expected = contact_support_chainages(
        build.assembly.length_by_chainage_m,
        profile,
    )
    brackets = build.scene.objects_of_type("production_contact_rail_bracket")
    insulators = build.scene.objects_of_type("production_contact_rail_insulator")
    screws = build.scene.objects_of_type(
        "production_contact_rail_attachment_screws"
    )
    fasteners = build.scene.objects_of_type(
        "production_contact_rail_fastening_unit"
    )
    assert len(expected) == 8
    assert len(brackets) == len(expected)
    assert len(insulators) == len(expected)
    assert len(screws) == len(expected)
    assert len(fasteners) == len(expected)
    assert int(meta["contactRailSupportCount"]) == len(expected)

    actual_chainages = [
        float(obj.custom_properties["eventChainageM"])
        for obj in brackets
    ]
    assert actual_chainages == list(expected)
    gaps = [
        b - a for a, b in zip(actual_chainages, actual_chainages[1:])
    ]
    assert all(
        profile.contact_rail.support_normative_min_m - 1e-12
        <= gap
        <= profile.contact_rail.support_normative_max_m + 1e-12
        for gap in gaps
    )
    assert all(
        obj.custom_properties["snappedToNearestTimberSleeper"] is True
        for obj in brackets
    )

    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: obj.object_type in CONTACT_TYPES,
    )
    assert audit.duplicate_group_count == 0

    chunks_a = build_chunk_scene_packages(
        build,
        chunk_length_m=7.3,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )
    chunks_b = build_chunk_scene_packages(
        build,
        chunk_length_m=11.2,
        boundary_policy=ChunkBoundaryPolicy.EXACT_LENGTH,
    )
    ids_a = _contact_parent_ids(chunks_a)
    ids_b = _contact_parent_ids(chunks_b)
    support_ids_a = {
        key: value
        for key, value in ids_a.items()
        if "/contact-rail/support-event/" in key
    }
    support_ids_b = {
        key: value
        for key, value in ids_b.items()
        if "/contact-rail/support-event/" in key
    }
    assert support_ids_a == support_ids_b
    assert len(support_ids_a) == len(expected) * 4

    print(
        json.dumps(
            {
                "stage": "10.3",
                "profile_id": profile.profile_id,
                "schema_version": profile.schema_version,
                "rings": build.assembly.config.n_rings,
                "length_m": build.assembly.length_by_chainage_m,
                "contact_rail_axis_profile_x_m": -1.45,
                "contact_working_surface_profile_z_m": 0.16,
                "contact_working_surface_core_z_m": -1.51,
                "support_count": len(expected),
                "target_support_pitch_m": 5.0,
                "support_spacing_min_m": min(gaps),
                "support_spacing_max_m": max(gaps),
                "cover_era_mismatch": True,
                "cover_historical_side_gap_m": 0.02,
                "duplicate_contact_face_groups": audit.duplicate_group_count,
                "stable_support_parent_ids_across_chunk_sizes": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
