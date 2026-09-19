from dataclasses import replace
from collections import Counter
import math

import numpy as np

from tunnel_scanner_core import (
    AncillaryConfig,
    AncillarySamplingPolicy,
    AncillaryTransformPolicy,
    LabelPolicy,
    RingConfig,
    RingRotationStrategy,
    TunnelAssemblyConfig,
    WalkwaySide,
    build_ancillary_set,
    build_prescribed_joint_set,
    build_ring_mesh,
    build_procedural_nominal_tunnel,
    sample_ancillary_config,
    sample_joint_config,
    sample_six_segment_angles,
)
from tunnel_scanner_core.assembly import (
    build_multi_ring_scene_package,
    sample_tunnel_assembly,
)
from tunnel_scanner_core.scene import build_nominal_scene_package
from tunnel_scanner_core.scene_io import scene_package_from_dict, scene_package_to_dict


def _edge_counts(faces):
    counts = Counter()
    for face in faces:
        for i, a in enumerate(face):
            b = face[(i + 1) % len(face)]
            counts[tuple(sorted((a, b)))] += 1
    return counts


def _signed_volume(vertices, faces):
    vv = [np.asarray(v, dtype=float) for v in vertices]
    total = 0.0
    for face in faces:
        p0 = vv[face[0]]
        for i in range(1, len(face) - 1):
            total += float(np.dot(p0, np.cross(vv[face[i]], vv[face[i + 1]]))) / 6.0
    return total


def _ring_fixture(seed=5812):
    cfg = RingConfig()
    ring = build_ring_mesh(cfg, sample_six_segment_angles(seed=seed))
    joints = build_prescribed_joint_set(ring, sample_joint_config(seed=seed))
    ancillary = build_ancillary_set(
        inner_radius_m=cfg.inner_radius_m,
        length_m=cfg.width_m,
        config=AncillaryConfig.reference(cfg.inner_radius_m),
    )
    return cfg, ring, joints, ancillary


def test_reference_config_matches_table4_reference_values():
    r = 3.0
    cfg = AncillaryConfig.reference(r)
    cfg.validate_against_table4(r)
    cfg.validate_physical_clearance(r)
    assert math.isclose(cfg.pavement_height_m, 0.25 * r)
    assert math.isclose(cfg.walkway_height_m, 0.60 * r)
    assert math.isclose(cfg.walkway_width_m, 0.40 * r)
    assert math.isclose(cfg.walkway_depth_m, 0.04 * r)
    assert cfg.walkway_side is WalkwaySide.RIGHT
    assert math.isclose(cfg.rail_depth_m, 0.175)
    assert math.isclose(cfg.rail_width_m, 0.175)
    assert math.isclose(cfg.rail_spacing_m, 1.5)
    assert len(cfg.tubes) == 6
    assert {tube.kind.value for tube in cfg.tubes} == {"pipe", "cable", "power_track"}
    assert all(0.005 * r <= tube.radius_m <= 0.05 * r for tube in cfg.tubes)


def test_printed_walkway_depth_upper_bound_is_preserved_not_silently_corrected():
    r = 3.0
    base = AncillaryConfig.reference(r)
    cfg = AncillaryConfig(
        pavement_height_m=0.30 * r,
        walkway_height_m=base.walkway_height_m,
        walkway_width_m=base.walkway_width_m,
        walkway_depth_m=0.34 * r,
        walkway_side=base.walkway_side,
        rail_depth_m=base.rail_depth_m,
        rail_width_m=base.rail_width_m,
        rail_spacing_m=base.rail_spacing_m,
        rail_spacing_convention=base.rail_spacing_convention,
        tubes=base.tubes,
    )
    cfg.validate_against_table4(r)
    try:
        cfg.validate_physical_clearance(r)
    except ValueError:
        pass
    else:
        raise AssertionError("0.34*r reference combination should intersect pavement")


def test_reference_ancillary_set_has_expected_categories_and_manifold_meshes():
    cfg, _, _, ancillary = _ring_fixture()
    assert len(ancillary.meshes) == 10
    assert len(ancillary.meshes_of_category("pavement")) == 1
    assert len(ancillary.meshes_of_category("walkway")) == 1
    assert len(ancillary.meshes_of_category("rail")) == 2
    assert len(ancillary.meshes_of_category("tube")) == 6

    for mesh in ancillary.meshes:
        counts = _edge_counts(mesh.faces)
        assert counts
        assert set(counts.values()) == {2}
        assert _signed_volume(mesh.vertices, mesh.faces) > 0.0


def test_pavement_top_and_rail_geometry_follow_table4_interpretation():
    cfg, _, _, ancillary = _ring_fixture()
    r = cfg.inner_radius_m
    pavement = ancillary.meshes_of_category("pavement")[0]
    rails = ancillary.meshes_of_category("rail")
    expected_top = -r + 0.25 * r
    assert math.isclose(pavement.properties["pavementTopZ"], expected_top, abs_tol=1e-12)

    centers = sorted(float(x.properties["railCenterX"]) for x in rails)
    assert np.allclose(centers, [-0.75, 0.75], atol=1e-12, rtol=0)
    assert math.isclose(centers[1] - centers[0], 1.5, abs_tol=1e-12)
    for rail in rails:
        zs = [v[2] for v in rail.vertices]
        assert math.isclose(min(zs), expected_top, abs_tol=1e-12)
        assert math.isclose(max(zs), expected_top + 0.175, abs_tol=1e-12)


def test_walkway_is_attached_to_intrados_and_extends_toward_tunnel_centre():
    cfg, _, _, ancillary = _ring_fixture()
    r = cfg.inner_radius_m
    walkway = ancillary.meshes_of_category("walkway")[0]
    # First front four vertices reproduce the quadrilateral cross-section.
    front = walkway.vertices[:4]
    z_top = -r + 0.60 * r
    z_bottom = z_top - 0.04 * r
    wall_top, inner_top, inner_bottom, wall_bottom = front
    assert math.isclose(wall_top[2], z_top, abs_tol=1e-12)
    assert math.isclose(inner_top[2], z_top, abs_tol=1e-12)
    assert math.isclose(wall_bottom[2], z_bottom, abs_tol=1e-12)
    assert math.isclose(inner_bottom[2], z_bottom, abs_tol=1e-12)
    assert math.isclose(math.hypot(wall_top[0], wall_top[2]), r, abs_tol=1e-12)
    assert math.isclose(math.hypot(wall_bottom[0], wall_bottom[2]), r, abs_tol=1e-12)
    assert math.isclose(wall_top[0] - inner_top[0], 0.40 * r, abs_tol=1e-12)


def test_tube_polygons_remain_inside_intrados_and_follow_configured_radius():
    cfg, _, _, ancillary = _ring_fixture()
    r = cfg.inner_radius_m
    tube_by_name = {m.name: m for m in ancillary.meshes_of_category("tube")}
    ref = ancillary.config
    for tube in ref.tubes:
        mesh = tube_by_name[tube.name]
        assert mesh.properties["tubeKind"] == tube.kind.value
        assert math.isclose(mesh.properties["tubeRadiusM"], tube.radius_m, abs_tol=1e-12)
        assert math.isclose(
            mesh.properties["tubeCenterRadiusM"], r - tube.radius_m, abs_tol=1e-12
        )
        assert max(math.hypot(v[0], v[2]) for v in mesh.vertices) <= r + 1e-10


def test_uniform_sampler_stays_in_published_bounds_and_rejects_physical_overlap():
    r = 3.0
    for seed in range(300):
        cfg = sample_ancillary_config(
            r,
            seed=seed,
            policy=AncillarySamplingPolicy.PUBLISHED_UNIFORM,
        )
        cfg.validate_against_table4(r)
        cfg.validate_physical_clearance(r)


def test_scene_seg2tunnel_policy_labels_all_ancillary_as_clutter():
    _, ring, joints, ancillary = _ring_fixture()
    package = build_nominal_scene_package(
        ring,
        joints,
        ring_id=4,
        ancillary=ancillary,
        label_policy=LabelPolicy.SEG2TUNNEL_LIKE,
    )
    ancillary_objects = [o for o in package.objects if o.object_type.startswith("ancillary_")]
    assert len(ancillary_objects) == 10
    assert {o.label_id for o in ancillary_objects} == {0}
    assert {o.semantic_class for o in ancillary_objects} == {"clutter"}


def test_scene_stsd_coarse_policy_uses_four_class_reclassification():
    _, ring, joints, ancillary = _ring_fixture()
    package = build_nominal_scene_package(
        ring,
        joints,
        ring_id=4,
        ancillary=ancillary,
        label_policy=LabelPolicy.STSD_COARSE,
    )
    assert {o.label_id for o in package.objects_of_type("lining_segment")} == {1}
    assert {o.semantic_class for o in package.objects_of_type("lining_segment")} == {
        "segments"
    }
    assert {o.label_id for o in package.objects_of_type("ancillary_walkway")} == {2}
    assert {o.label_id for o in package.objects_of_type("ancillary_tube")} == {3}
    assert {o.label_id for o in package.objects_of_type("ancillary_pavement")} == {0}
    assert {o.label_id for o in package.objects_of_type("ancillary_rail")} == {0}


def test_ancillary_does_not_follow_segment_ring_axial_stagger_rotation():
    cfg, ring, joints, ancillary = _ring_fixture()
    local = build_nominal_scene_package(
        ring,
        joints,
        ring_id=0,
        ancillary=ancillary,
    )
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=1,
            ring_width_m=cfg.width_m,
            displacement_amplitude_m=0.0,
            axis_noise_sigma_m=0.0,
            ring_rotation_strategy=RingRotationStrategy.PAPER_CONSTANT_NOMINAL,
            nominal_stagger_deg=90.0,
            angular_imperfection_fraction=0.0,
        ),
        seed=3,
    )
    world = build_multi_ring_scene_package([local], assembly)

    local_pavement = local.objects_of_type("ancillary_pavement")[0]
    world_pavement = world.objects_of_type("ancillary_pavement")[0]
    assert np.allclose(local_pavement.vertices, world_pavement.vertices, atol=1e-12, rtol=0)
    assert world_pavement.custom_properties["ringRotationDeg"] == 90.0
    assert world_pavement.custom_properties["objectAppliedAxialRotationDeg"] == 0.0

    local_segment = local.objects_of_type("lining_segment")[0]
    world_segment = world.objects_of_type("lining_segment")[0]
    assert not np.allclose(local_segment.vertices, world_segment.vertices, atol=1e-8, rtol=0)
    assert world_segment.custom_properties["objectAppliedAxialRotationDeg"] == 90.0


def test_high_level_stage8_builder_reuses_one_ancillary_cross_section_across_rings():
    n = 3
    result = build_procedural_nominal_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=n,
            ring_width_m=1.35,
            displacement_amplitude_m=0.0,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        include_ancillary=True,
        ancillary_sampling_policy=AncillarySamplingPolicy.REFERENCE,
        label_policy=LabelPolicy.STSD_COARSE,
        seed=5812,
    )
    assert len(result.scene.objects_of_type("ancillary_pavement")) == n
    assert len(result.scene.objects_of_type("ancillary_walkway")) == n
    assert len(result.scene.objects_of_type("ancillary_rail")) == 2 * n
    assert len(result.scene.objects_of_type("ancillary_tube")) == 6 * n
    assert result.scene.metadata["proceduralBuild"]["ancillaryObjectCountPerRing"] == 10

    per_ring = [
        [o for o in pkg.objects if o.object_type.startswith("ancillary_")]
        for pkg in result.ring_packages
    ]
    for ring_objects in per_ring[1:]:
        assert [o.vertices for o in ring_objects] == [o.vertices for o in per_ring[0]]


def test_stage8_stsd_scene_json_roundtrip_is_lossless():
    result = build_procedural_nominal_tunnel(
        assembly_config=TunnelAssemblyConfig(n_rings=2, ring_width_m=1.35),
        include_bolts=True,
        include_ancillary=True,
        label_policy=LabelPolicy.STSD_COARSE,
        seed=77,
    )
    encoded = scene_package_to_dict(result.scene)
    restored = scene_package_from_dict(encoded)
    assert restored == result.scene


def test_stage8_ancillary_slices_are_stitched_at_inter_ring_boundaries():
    n = 4
    result = build_procedural_nominal_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=n,
            ring_width_m=1.35,
            displacement_amplitude_m=0.1,
            axis_noise_sigma_m=0.005,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        include_bolts=False,
        include_ancillary=True,
        ancillary_sampling_policy=AncillarySamplingPolicy.REFERENCE,
        seed=913,
    )

    by_ring = []
    for ring_id in range(n):
        objs = [
            o
            for o in result.scene.objects
            if o.ring_id == ring_id and o.object_type.startswith("ancillary_")
        ]
        by_ring.append(objs)

    for ring_id in range(n - 1):
        assert len(by_ring[ring_id]) == len(by_ring[ring_id + 1]) == 10
        for left, right in zip(by_ring[ring_id], by_ring[ring_id + 1]):
            assert left.object_type == right.object_type
            # Stage-8 reference meshes use front/centre/back cross-sections.
            assert len(left.vertices) % 3 == 0
            assert len(right.vertices) == len(left.vertices)
            section = len(left.vertices) // 3
            left_back = np.asarray(left.vertices[-section:])
            right_front = np.asarray(right.vertices[:section])
            assert np.allclose(left_back, right_front, atol=2e-12, rtol=0)


def test_stage8_ancillary_centre_station_passes_through_ring_centre_offset():
    result = build_procedural_nominal_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=3,
            ring_width_m=1.35,
            displacement_amplitude_m=0.1,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        include_ancillary=True,
        seed=5812,
    )
    for ring_id, local_pkg in enumerate(result.ring_packages):
        pose = result.assembly.poses[ring_id]
        local = local_pkg.objects_of_type("ancillary_rail")[0]
        world = [
            o
            for o in result.scene.objects_of_type("ancillary_rail")
            if o.ring_id == ring_id
        ][0]
        section = len(local.vertices) // 3
        local_mid = np.asarray(local.vertices[section : 2 * section])
        world_mid = np.asarray(world.vertices[section : 2 * section])
        expected = local_mid.copy()
        expected[:, 0] += pose.translation_m[0]
        expected[:, 1] += pose.translation_m[1]
        expected[:, 2] += pose.translation_m[2]
        assert np.allclose(world_mid, expected, atol=2e-12, rtol=0)


def test_rail_spacing_ambiguity_modes_are_explicit():
    from tunnel_scanner_core import RailSpacingConvention

    r = 3.0
    base = AncillaryConfig.reference(r)
    assert base.rail_spacing_convention is RailSpacingConvention.TABLE4_CENTER_SPACING

    table = build_ancillary_set(
        inner_radius_m=r,
        length_m=1.35,
        config=base,
    )
    table_centers = sorted(m.properties["railCenterX"] for m in table.meshes_of_category("rail"))
    assert np.allclose(table_centers, [-0.75, 0.75], atol=1e-12, rtol=0)

    prose_cfg = AncillaryConfig(
        pavement_height_m=base.pavement_height_m,
        walkway_height_m=base.walkway_height_m,
        walkway_width_m=base.walkway_width_m,
        walkway_depth_m=base.walkway_depth_m,
        walkway_side=base.walkway_side,
        rail_depth_m=base.rail_depth_m,
        rail_width_m=base.rail_width_m,
        rail_spacing_m=base.rail_spacing_m,
        rail_spacing_convention=RailSpacingConvention.PROSE_OFFSET_FROM_MIDLINE,
        tubes=base.tubes,
    )
    prose = build_ancillary_set(
        inner_radius_m=r,
        length_m=1.35,
        config=prose_cfg,
    )
    prose_centers = sorted(m.properties["railCenterX"] for m in prose.meshes_of_category("rail"))
    assert np.allclose(prose_centers, [-1.5, 1.5], atol=1e-12, rtol=0)


def test_literal_paper_ring_rigid_policy_rotates_ancillary_with_ring():
    cfg, ring, joints, _ = _ring_fixture()
    base = AncillaryConfig.reference(cfg.inner_radius_m)
    paper_cfg = replace(
        base,
        transform_policy=AncillaryTransformPolicy.PAPER_RING_RIGID,
    )
    ancillary = build_ancillary_set(
        inner_radius_m=cfg.inner_radius_m,
        length_m=cfg.width_m,
        config=paper_cfg,
    )
    local = build_nominal_scene_package(
        ring,
        joints,
        ring_id=0,
        ancillary=ancillary,
    )
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=1,
            ring_width_m=cfg.width_m,
            displacement_amplitude_m=0.0,
            axis_noise_sigma_m=0.0,
            ring_rotation_strategy=RingRotationStrategy.PAPER_CONSTANT_NOMINAL,
            nominal_stagger_deg=90.0,
            angular_imperfection_fraction=0.0,
        ),
        seed=3,
    )
    world = build_multi_ring_scene_package([local], assembly)
    local_pavement = local.objects_of_type("ancillary_pavement")[0]
    world_pavement = world.objects_of_type("ancillary_pavement")[0]
    assert not np.allclose(
        local_pavement.vertices,
        world_pavement.vertices,
        atol=1e-8,
        rtol=0,
    )
    assert world_pavement.custom_properties["followSceneAlignment"] is False
    assert world_pavement.custom_properties["followRingAxialRotation"] is True
    assert world_pavement.custom_properties["objectAppliedAxialRotationDeg"] == 90.0
