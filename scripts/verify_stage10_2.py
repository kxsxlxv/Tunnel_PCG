from __future__ import annotations

import json
import math

from tunnel_scanner_core import (
    LabelPolicy,
    ProductionConfig,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_chunk_scene_packages,
    build_production_tunnel,
    load_stage10_initial_moscow_profile,
    sleeper_chainages,
)


PERMANENT_WAY_TYPES = {
    "production_track_concrete",
    "production_rail",
    "production_sleeper",
    "production_under_baseplate_pad",
    "production_baseplate",
    "production_rail_pad",
    "production_track_screw",
    "production_clamp_hardware",
}


def _parent_ids(packages):
    result = {}
    for package in packages:
        for obj in package.objects:
            if obj.object_type not in PERMANENT_WAY_TYPES:
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
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(
            namespace="stage10-2-stress",
            moscow_profile=profile,
            moscow_stage="10.2",
        ),
        seed=5812,
    )

    meta = build.scene.metadata["productionGeometry"]
    assert meta["domainStage"] == "10.2"
    assert meta["permanentWayStatus"] == "implemented_stage10_2_initial_geometry"
    assert len(build.scene.objects_of_type("production_pavement")) == 0
    assert len(build.scene.objects_of_type("production_track_concrete")) == 1

    expected_chainages = sleeper_chainages(
        build.assembly.length_by_chainage_m,
        pitch_m=profile.sleeper.pitch_m,
    )
    sleepers = build.scene.objects_of_type("production_sleeper")
    assert len(sleepers) == len(expected_chainages)
    assert int(meta["sleeperCount"]) == len(expected_chainages)

    for object_type in (
        "production_under_baseplate_pad",
        "production_baseplate",
        "production_rail_pad",
        "production_track_screw",
        "production_clamp_hardware",
    ):
        assert len(build.scene.objects_of_type(object_type)) == len(sleepers)

    rails = build.scene.objects_of_type("production_rail")
    assert len(rails) == 2
    for rail in rails:
        assert rail.custom_properties["railFootBottomContactFaceOmitted"] is True
        assert int(rail.custom_properties["omittedLongitudinalEdgeCount"]) == 2
        assert math.isclose(
            float(rail.custom_properties["railBaseCoreZLocalM"]),
            -1.85,
            abs_tol=2e-12,
        )

    railpads = build.scene.objects_of_type("production_rail_pad")
    assert railpads
    for pad in railpads:
        local_top = max(v[2] for v in pad.vertices)
        station_offset = float(pad.custom_properties["alignmentOffsetZ"])
        assert math.isclose(
            local_top - station_offset,
            -1.85,
            abs_tol=2e-12,
        )

    concrete = build.scene.objects_of_type("production_track_concrete")[0]
    assert math.isclose(
        float(concrete.custom_properties["centralDrainClearWidthM"]),
        0.9,
        abs_tol=2e-12,
    )
    assert math.isclose(
        float(concrete.custom_properties["centralDrainBottomProfileZM"]),
        -0.53,
        abs_tol=2e-12,
    )
    assert math.isclose(
        float(concrete.custom_properties["surfaceCrossSlopeToDrain"]),
        0.03,
        abs_tol=2e-12,
    )

    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: obj.object_type in PERMANENT_WAY_TYPES,
    )
    assert audit.duplicate_group_count == 0

    chunks_a = build_chunk_scene_packages(build, chunk_length_m=8.1)
    chunks_b = build_chunk_scene_packages(build, chunk_length_m=13.5)
    ids_a = _parent_ids(chunks_a)
    ids_b = _parent_ids(chunks_b)
    periodic_keys_a = {
        key: value
        for key, value in ids_a.items()
        if "/permanent-way/sleeper-event/" in key
    }
    periodic_keys_b = {
        key: value
        for key, value in ids_b.items()
        if "/permanent-way/sleeper-event/" in key
    }
    assert periodic_keys_a == periodic_keys_b
    assert len(periodic_keys_a) == len(sleepers) * 6

    print(
        json.dumps(
            {
                "stage": "10.2",
                "profile_id": profile.profile_id,
                "rings": build.assembly.config.n_rings,
                "length_m": build.assembly.length_by_chainage_m,
                "sleeper_count": len(sleepers),
                "sleeper_pitch_m": profile.sleeper.pitch_m,
                "periodic_permanent_way_parent_ids": len(periodic_keys_a),
                "track_concrete_assets": 1,
                "central_drain_clear_width_m": 0.9,
                "central_drain_bottom_profile_z_m": -0.53,
                "water_release_groove_width_m": 0.05,
                "water_release_groove_depth_m": 0.025,
                "rail_base_core_z_m": -1.85,
                "rail_foot_bottom_edges_omitted_per_rail": 2,
                "duplicate_permanent_way_face_groups": (
                    audit.duplicate_group_count
                ),
                "stable_periodic_parent_ids_across_chunk_sizes": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
