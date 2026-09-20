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
)


def _source_ids(packages):
    return {
        obj.custom_properties["sourcePersistentKey"]:
        obj.custom_properties["sourceInstanceID"]
        for package in packages
        for obj in package.objects
        if obj.object_type == "production_rail"
    }


def main() -> None:
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=75,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(
            namespace="stage10-1-stress",
            moscow_profile=profile,
        ),
        seed=5812,
    )

    rails = build.scene.objects_of_type("production_rail")
    assert len(rails) == 2
    faces = sorted(
        float(r.custom_properties["railInnerWorkingFaceX"])
        for r in rails
    )
    assert math.isclose(
        faces[1] - faces[0],
        1.520,
        abs_tol=2e-12,
    )
    for rail in rails:
        n = rail.custom_properties["productionCrossSectionVertices"]
        assert (
            rail.custom_properties["productionStationCount"]
            == len(build.alignment_stations)
        )
        for station_index, station in enumerate(build.alignment_stations):
            section = rail.vertices[
                station_index * n:(station_index + 1) * n
            ]
            assert math.isclose(
                max(v[2] - station.offset_z_m for v in section),
                0.0,
                abs_tol=2e-12,
            )

    audit = audit_exact_coincident_faces(
        build.scene,
        object_filter=lambda obj: (
            obj.object_type == "production_rail"
        ),
    )
    assert audit.duplicate_group_count == 0

    chunks_a = build_chunk_scene_packages(
        build,
        chunk_length_m=16.2,
    )
    chunks_b = build_chunk_scene_packages(
        build,
        chunk_length_m=27.0,
    )
    assert _source_ids(chunks_a) == _source_ids(chunks_b)
    assert len(_source_ids(chunks_a)) == 2

    print(
        json.dumps(
            {
                "stage": "10.1",
                "profile_id": profile.profile_id,
                "rings": build.assembly.config.n_rings,
                "length_m": build.assembly.length_by_chainage_m,
                "rail_profile_vertices": (
                    rails[0].custom_properties["railProfileVertices"]
                ),
                "working_face_gauge_m": faces[1] - faces[0],
                "rail_center_offsets_m": [
                    rail.custom_properties["railCenterX"]
                    for rail in rails
                ],
                "rail_top_local_z_m": (
                    rails[0].custom_properties["railTopZLocalM"]
                ),
                "duplicate_rail_face_groups": (
                    audit.duplicate_group_count
                ),
                "stable_parent_ids_across_chunk_sizes": True,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
