import json
import math

import pytest

from tunnel_scanner_core import (
    AncillaryConfig,
    LabelPolicy,
    MoscowStage10Profile,
    ProductionConfig,
    R65ProductionProfile,
    RailProfile,
    TunnelAssemblyConfig,
    audit_exact_coincident_faces,
    build_ancillary_set,
    build_chunk_scene_packages,
    build_continuous_asset_specs,
    build_production_tunnel,
    load_stage10_initial_moscow_profile,
    r65_inner_working_face_x,
    r65_rail_center_offsets_for_gauge,
)


def test_initial_moscow_profile_round_trips_machine_data_deterministically():
    profile = load_stage10_initial_moscow_profile()
    mapping = profile.to_mapping()
    rebuilt = MoscowStage10Profile.from_mapping(mapping)

    assert (
        profile.profile_id
        == "stage10_initial_profile_CAST_IRON_5500_R1000_R65_TIMBER_LEGACY"
    )
    assert json.loads(profile.canonical_json()) == mapping
    assert rebuilt.canonical_json() == profile.canonical_json()
    assert (
        rebuilt.provenance.canonical_sha256
        == profile.provenance.canonical_sha256
    )
    assert "P10-FROLOV-1.14" in profile.provenance.source_ids
    assert "P10-GOST51685-2022" in profile.provenance.source_ids
    assert "P10-METRO-GAUGE-13MM" in profile.provenance.source_ids


def test_moscow_datums_are_explicit_and_not_derived_from_clearance_geometry():
    profile = load_stage10_initial_moscow_profile()
    d = profile.datums

    assert d.ugr_z_m == 0.0
    assert d.track_axis_x_m == 0.0
    assert d.track_axis_z_m == 0.0
    assert d.lining_axis_x_m == 0.0
    assert d.lining_axis_z_m == 1.67
    assert d.intrados_invert_z_m == -0.88
    assert d.intrados_crown_z_m == 4.22
    assert d.extrados_invert_z_m == -1.08
    assert d.extrados_crown_z_m == 4.42


def test_coordinate_mapping_preserves_core_plus_y_longitudinal_contract():
    profile = load_stage10_initial_moscow_profile()
    c = profile.coordinate

    assert c.research_xz_to_core_xz(1.25, -0.4) == (1.25, -0.4)
    assert c.core_xz_to_research_xz(1.25, -0.4) == (1.25, -0.4)

    core = c.engineering_route_to_core_local(12.0, 2.0, 3.0)
    assert core == (-2.0, 12.0, 3.0)
    assert c.core_local_to_engineering_route(*core) == (12.0, 2.0, 3.0)


def test_r65_reference_profile_preserves_gost_principal_dimensions_and_qa():
    rail = R65ProductionProfile()
    m = rail.validation_metrics()

    assert math.isclose(m["height_m"], 0.180, abs_tol=1e-7)
    assert math.isclose(m["base_width_m"], 0.150, abs_tol=1e-7)
    assert abs(m["head_width_m"] - 0.07459) < 3e-5
    assert m["web_thickness_m"] == 0.018
    assert abs(m["area_rel_error"]) < 0.003
    assert abs(m["centroid_z_error_m"]) < 0.00025


def test_r65_gauge_is_placed_by_inner_working_faces_at_13mm_below_ugr():
    profile = load_stage10_initial_moscow_profile()
    rail = R65ProductionProfile()
    below = profile.track.gauge_measurement_below_ugr_m
    assert below == 0.013

    working = rail.working_face_offset_m(
        measurement_below_top_m=below
    )
    assert math.isclose(
        working,
        0.03612386585834637,
        abs_tol=2e-12,
    )

    centers = r65_rail_center_offsets_for_gauge(
        profile.track.gauge_m,
        profile=rail,
        measurement_below_top_m=below,
    )
    assert centers[0] < -profile.track.gauge_m / 2.0
    assert centers[1] > +profile.track.gauge_m / 2.0
    assert math.isclose(
        centers[0],
        -0.7961238658583464,
        abs_tol=2e-12,
    )
    assert math.isclose(
        centers[1],
        +0.7961238658583464,
        abs_tol=2e-12,
    )

    faces = tuple(
        r65_inner_working_face_x(
            i,
            centers[i],
            profile=rail,
            measurement_below_top_m=below,
        )
        for i in range(2)
    )
    assert math.isclose(faces[0], -0.760, abs_tol=2e-12)
    assert math.isclose(faces[1], +0.760, abs_tol=2e-12)
    assert math.isclose(
        faces[1] - faces[0],
        1.520,
        abs_tol=2e-12,
    )


def test_moscow_asset_specs_replace_only_running_rails_in_stage10_1():
    profile = load_stage10_initial_moscow_profile()
    ancillary_cfg = AncillaryConfig.reference(3.0)
    ancillary = build_ancillary_set(
        inner_radius_m=3.0,
        length_m=1.35,
        config=ancillary_cfg,
    )
    specs = build_continuous_asset_specs(
        namespace="moscow-spec-test",
        ancillary=ancillary,
        label_policy=LabelPolicy.STSD_COARSE,
        moscow_profile=profile,
    )
    rails = [s for s in specs if s.category == "rail"]

    assert len(specs) == 10
    assert len(rails) == 2
    for rail in rails:
        p = rail.properties
        assert p["railProfile"] == "stage10_1_r65_gost_r51685_2022"
        assert p["railOverallHeightM"] == 0.180
        assert p["railNominalHeadWidthM"] == 0.07459
        assert p["railWebThicknessM"] == 0.018
        assert p["railFootWidthM"] == 0.150
        assert p["railTopZLocalM"] == 0.0
        assert p["railBaseZLocalM"] == -0.180
        assert p["gaugeM"] == 1.520
        assert p["gaugeMeasurementBelowUGRM"] == 0.013
        assert not rail.omitted_longitudinal_edges
        zs = [z for _x, z in rail.cross_section_xz]
        assert math.isclose(max(zs), 0.0, abs_tol=2e-12)
        assert math.isclose(min(zs), -0.180, abs_tol=2e-12)

    faces = [
        float(r.properties["railInnerWorkingFaceX"])
        for r in rails
    ]
    assert math.isclose(
        faces[1] - faces[0],
        1.520,
        abs_tol=2e-12,
    )


def test_stage10_1_full_production_integration_preserves_ids_chunking_and_topology():
    profile = load_stage10_initial_moscow_profile()
    build = build_production_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=8,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        label_policy=LabelPolicy.STSD_COARSE,
        production_config=ProductionConfig(
            namespace="moscow-stage10-1",
            moscow_profile=profile,
        ),
        seed=5812,
    )

    rails = build.scene.objects_of_type("production_rail")
    assert len(rails) == 2
    meta = build.scene.metadata["productionGeometry"]
    assert meta["domainStage"] == "10.1"
    assert meta["moscowProfileID"] == profile.profile_id
    assert meta["civilShellStatus"] == "deferred_to_stage10_4"
    assert meta["permanentWayStatus"] == "deferred_to_stage10_2"

    for rail in rails:
        assert (
            rail.custom_properties["railProfile"]
            == "stage10_1_r65_gost_r51685_2022"
        )
        assert math.isclose(
            max(v[2] for v in rail.vertices),
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
        chunk_length_m=4.05,
    )
    chunks_b = build_chunk_scene_packages(
        build,
        chunk_length_m=6.75,
    )
    ids_a = {
        obj.custom_properties["sourcePersistentKey"]:
        obj.custom_properties["sourceInstanceID"]
        for package in chunks_a
        for obj in package.objects
        if obj.object_type == "production_rail"
    }
    ids_b = {
        obj.custom_properties["sourcePersistentKey"]:
        obj.custom_properties["sourceInstanceID"]
        for package in chunks_b
        for obj in package.objects
        if obj.object_type == "production_rail"
    }
    assert ids_a == ids_b
    assert len(ids_a) == 2


def test_stage10_1_rejects_ambiguous_generic_and_moscow_rail_profiles():
    profile = load_stage10_initial_moscow_profile()
    generic = RailProfile(
        overall_height_m=0.18,
        head_width_m=0.075,
        head_height_m=0.05,
        web_thickness_m=0.018,
        foot_width_m=0.15,
        foot_height_m=0.03,
    )
    with pytest.raises(
        ValueError,
        match="either rail_profile or moscow_profile",
    ):
        ProductionConfig(
            rail_profile=generic,
            moscow_profile=profile,
        )
