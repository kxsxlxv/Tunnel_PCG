import math

import numpy as np

from tunnel_scanner_core import (
    RingConfig,
    SurfaceMeshingConfig,
    build_prescribed_joint_set,
    build_ring_mesh,
    sample_joint_config,
    sample_six_segment_angles,
)
from tunnel_scanner_core.assembly import (
    RingRotationStrategy,
    TunnelAssemblyConfig,
    build_multi_ring_scene_package,
    sample_tunnel_assembly,
    transform_point_by_ring_pose,
)
from tunnel_scanner_core.bolts import (
    BoltConfig,
    BoltLayoutType,
    BoltPerturbationConfig,
    build_bolt_set,
)
from tunnel_scanner_core.blender_adapter import plan_bolt_boolean_operations
from tunnel_scanner_core.scene import SceneMode, build_nominal_scene_package
from tunnel_scanner_core.scene_io import scene_package_from_dict, scene_package_to_dict


def _ring_package(ring_id: int, *, bolts: bool = False):
    cfg = RingConfig()
    angles = sample_six_segment_angles(seed=10_000 + ring_id)
    ring = build_ring_mesh(cfg, angles)
    joints = build_prescribed_joint_set(ring, sample_joint_config(seed=20_000 + ring_id))
    bolt_set = None
    if bolts:
        bolt_set = build_bolt_set(
            ring,
            BoltConfig(),
            BoltLayoutType.TYPE1_CENTERED,
            seed=30_000 + ring_id,
            perturbation_config=BoltPerturbationConfig(sigma_m=0.0, sigma_fraction=0.0),
        )
    return build_nominal_scene_package(
        ring,
        joints,
        ring_id=ring_id,
        surface_meshing=SurfaceMeshingConfig(max_sagitta_m=0.002),
        bolts=bolt_set,
    )


def test_eq21_without_noise_matches_sinusoidal_offsets_exactly():
    cfg = TunnelAssemblyConfig(
        n_rings=5,
        ring_width_m=1.35,
        displacement_amplitude_m=0.1,
        omega_x_rad_per_ring=0.25,
        omega_z_rad_per_ring=0.4,
        axis_noise_sigma_m=0.0,
        recenter_lateral_offsets=False,
    )
    assembly = sample_tunnel_assembly(cfg, seed=123)
    for i, pose in enumerate(assembly.poses):
        assert math.isclose(pose.translation_m[0], 0.1 * math.sin(0.25 * i), abs_tol=1e-14)
        assert math.isclose(pose.translation_m[1], 1.35 * i, abs_tol=1e-14)
        assert math.isclose(pose.translation_m[2], 0.1 * math.cos(0.4 * i), abs_tol=1e-14)
        assert pose.rotation_y_deg == 0.0


def test_default_wavelengths_are_physical_and_independent_of_scene_length():
    short_cfg = TunnelAssemblyConfig(
        n_rings=5,
        axis_noise_sigma_m=0.0,
        recenter_lateral_offsets=False,
    )
    long_cfg = TunnelAssemblyConfig(
        n_rings=30,
        axis_noise_sigma_m=0.0,
        recenter_lateral_offsets=False,
    )
    short = sample_tunnel_assembly(short_cfg, seed=0)
    long = sample_tunnel_assembly(long_cfg, seed=0)

    assert short_cfg.lateral_wavelength_m == 50.0
    assert short_cfg.vertical_wavelength_m == 100.0
    assert math.isclose(
        short_cfg.resolved_omega_x_rad_per_m, 2.0 * math.pi / 50.0, abs_tol=1e-15
    )
    assert math.isclose(
        short_cfg.resolved_omega_z_rad_per_m, 2.0 * math.pi / 100.0, abs_tol=1e-15
    )

    # Same chainage => same deterministic curve regardless of export length.
    for a, b in zip(short.poses, long.poses[:5]):
        assert np.allclose(a.translation_m, b.translation_m, atol=1e-14, rtol=0)


def test_default_five_ring_adjacent_sinusoidal_steps_are_centimetre_scale():
    cfg = TunnelAssemblyConfig(
        n_rings=5,
        axis_noise_sigma_m=0.0,
        recenter_lateral_offsets=False,
    )
    assembly = sample_tunnel_assembly(cfg, seed=0)
    transverse_steps = [
        math.hypot(
            b.translation_m[0] - a.translation_m[0],
            b.translation_m[2] - a.translation_m[2],
        )
        for a, b in zip(assembly.poses, assembly.poses[1:])
    ]
    assert max(transverse_steps) < 0.020
    assert cfg.deterministic_adjacent_step_bound_x_m() < 0.0171
    assert cfg.deterministic_adjacent_step_bound_z_m() < 0.0085
    assert cfg.deterministic_adjacent_transverse_step_bound_m() < 0.0191


def test_lateral_recentering_makes_pose_means_zero():
    cfg = TunnelAssemblyConfig(
        n_rings=17,
        axis_noise_sigma_m=0.005,
        recenter_lateral_offsets=True,
    )
    assembly = sample_tunnel_assembly(cfg, seed=42)
    assert abs(np.mean([p.translation_m[0] for p in assembly.poses])) < 1e-14
    assert abs(np.mean([p.translation_m[2] for p in assembly.poses])) < 1e-14


def test_sampling_is_seed_deterministic():
    cfg = TunnelAssemblyConfig(
        n_rings=13,
        ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
    )
    assert sample_tunnel_assembly(cfg, seed=5812) == sample_tunnel_assembly(cfg, seed=5812)
    assert sample_tunnel_assembly(cfg, seed=5812) != sample_tunnel_assembly(cfg, seed=5813)


def test_continuous_joint_strategy_has_no_ring_rotation():
    cfg = TunnelAssemblyConfig(
        n_rings=30,
        ring_rotation_strategy=RingRotationStrategy.CONTINUOUS,
    )
    assembly = sample_tunnel_assembly(cfg, seed=1)
    assert all(p.rotation_y_deg == 0.0 for p in assembly.poses)
    assert all(p.nominal_rotation_deg == 0.0 for p in assembly.poses)
    assert all(p.angular_imperfection_deg == 0.0 for p in assembly.poses)


def test_paper_constant_nominal_uses_one_phi_plus_delta():
    cfg = TunnelAssemblyConfig(
        n_rings=20,
        ring_rotation_strategy=RingRotationStrategy.PAPER_CONSTANT_NOMINAL,
        nominal_stagger_deg=45.0,
        angular_imperfection_fraction=0.1,
    )
    assembly = sample_tunnel_assembly(cfg, seed=8)
    assert {p.nominal_rotation_deg for p in assembly.poses} == {45.0}
    assert any(abs(p.angular_imperfection_deg) > 1e-9 for p in assembly.poses)
    for p in assembly.poses:
        assert math.isclose(
            p.rotation_y_deg,
            p.nominal_rotation_deg + p.angular_imperfection_deg,
            abs_tol=1e-12,
        )


def test_ringwise_stagger_nominals_stay_inside_table2_bound():
    cfg = TunnelAssemblyConfig(
        n_rings=1000,
        ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        theta_k_deg=22.5,
    )
    assembly = sample_tunnel_assembly(cfg, seed=9)
    assert all(abs(p.nominal_rotation_deg) <= 135.0 + 1e-12 for p in assembly.poses)
    assert len({round(p.nominal_rotation_deg, 6) for p in assembly.poses}) > 100


def test_ring_pose_transform_is_rigid_and_y_spacing_is_exact():
    cfg = TunnelAssemblyConfig(
        n_rings=3,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
        ring_rotation_strategy=RingRotationStrategy.PAPER_CONSTANT_NOMINAL,
        nominal_stagger_deg=37.0,
    )
    assembly = sample_tunnel_assembly(cfg, seed=1)
    p = (2.3, -0.5, 0.7)
    q = (-1.1, 0.4, 2.0)
    d0 = math.dist(p, q)
    for pose in assembly.poses:
        assert math.isclose(
            math.dist(
                transform_point_by_ring_pose(p, pose),
                transform_point_by_ring_pose(q, pose),
            ),
            d0,
            abs_tol=1e-12,
        )
    assert [pose.translation_m[1] for pose in assembly.poses] == [0.0, 1.35, 2.7]


def test_multi_ring_scene_merges_unique_objects_and_preserves_boolean_targets():
    n = 3
    packages = [_ring_package(i, bolts=True) for i in range(n)]
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(n_rings=n, ring_width_m=1.35, axis_noise_sigma_m=0.0),
        seed=5812,
    )
    scene = build_multi_ring_scene_package(packages, assembly)
    assert scene.mode is SceneMode.MULTI_RING_TUNNEL
    assert scene.ring_ids == (0, 1, 2)
    assert len(scene.objects) == 3 * 54
    assert len({o.name for o in scene.objects}) == len(scene.objects)
    assert len({o.instance_id for o in scene.objects}) == len(scene.objects)

    object_names = {o.name for o in scene.objects}
    plan = plan_bolt_boolean_operations(scene)
    assert len(plan) == 3 * 36
    for op in plan:
        assert op.target_name in object_names
        assert op.tool_name in object_names


def test_world_transform_metadata_is_written_to_every_object():
    packages = [_ring_package(i, bolts=False) for i in range(2)]
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(n_rings=2, ring_width_m=1.35, axis_noise_sigma_m=0.0),
        seed=1,
    )
    scene = build_multi_ring_scene_package(packages, assembly)
    for obj in scene.objects:
        props = obj.custom_properties
        pose = assembly.poses[obj.ring_id]
        assert props["ringChainageM"] == pose.chainage_m
        assert props["ringTranslationY"] == pose.translation_m[1]
        assert props["ringRotationDeg"] == pose.rotation_y_deg


def test_multi_ring_scene_json_roundtrip_is_lossless():
    packages = [_ring_package(i, bolts=True) for i in range(2)]
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=2,
            ring_rotation_strategy=RingRotationStrategy.RINGWISE_GAUSSIAN,
        ),
        seed=44,
    )
    scene = build_multi_ring_scene_package(packages, assembly)
    assert scene_package_from_dict(scene_package_to_dict(scene)) == scene


def test_transform_does_not_change_face_topology_or_object_counts():
    package = _ring_package(0, bolts=True)
    assembly = sample_tunnel_assembly(
        TunnelAssemblyConfig(
            n_rings=1,
            ring_rotation_strategy=RingRotationStrategy.PAPER_CONSTANT_NOMINAL,
            nominal_stagger_deg=90.0,
            axis_noise_sigma_m=0.0,
            recenter_lateral_offsets=False,
        ),
        seed=1,
    )
    scene = build_multi_ring_scene_package([package], assembly)
    assert len(scene.objects) == len(package.objects)
    for src, dst in zip(package.objects, scene.objects):
        assert src.faces == dst.faces
        assert len(src.vertices) == len(dst.vertices)
        if len(src.vertices) > 1:
            assert math.isclose(
                math.dist(src.vertices[0], src.vertices[-1]),
                math.dist(dst.vertices[0], dst.vertices[-1]),
                abs_tol=1e-12,
            )


def test_high_level_builder_has_n_minus_one_circumferential_interfaces():
    from tunnel_scanner_core.tunnel import build_procedural_nominal_tunnel

    n = 4
    result = build_procedural_nominal_tunnel(
        assembly_config=TunnelAssemblyConfig(
            n_rings=n,
            ring_width_m=1.35,
            axis_noise_sigma_m=0.0,
        ),
        include_bolts=False,
        seed=123,
    )
    assert (
        result.scene.metadata["proceduralBuild"]["expectedCircumferentialInterfaces"]
        == n - 1
    )
    assert (
        len(result.scene.objects_of_type("prescribed_circumferential_joint"))
        == (n - 1) * 6
    )
    assert len(result.scene.objects) == (n - 1) * 18 + 12


def test_high_level_builder_with_bolts_preserves_multiring_boolean_plan():
    from tunnel_scanner_core.tunnel import build_procedural_nominal_tunnel

    n = 3
    result = build_procedural_nominal_tunnel(
        assembly_config=TunnelAssemblyConfig(n_rings=n, ring_width_m=1.35),
        include_bolts=True,
        seed=5812,
    )
    plan = plan_bolt_boolean_operations(result.scene)
    assert len(result.scene.objects_of_type("bolt_head")) == n * 18
    assert len(result.scene.objects_of_type("bolt_pocket_cutter")) == n * 18
    assert len(plan) == n * 36
    assert {op.ring_id for op in plan} == set(range(n))


def test_high_level_builder_is_fully_seed_deterministic():
    from tunnel_scanner_core.tunnel import build_procedural_nominal_tunnel

    cfg = TunnelAssemblyConfig(n_rings=2, ring_width_m=1.35)
    a = build_procedural_nominal_tunnel(
        assembly_config=cfg,
        include_bolts=True,
        seed=77,
    )
    b = build_procedural_nominal_tunnel(
        assembly_config=cfg,
        include_bolts=True,
        seed=77,
    )
    assert a.scene == b.scene
    assert a.assembly == b.assembly


def test_paper_scene_ring_count_bounds_are_explicit():
    TunnelAssemblyConfig(n_rings=10).validate_against_paper_scene_bounds()
    TunnelAssemblyConfig(n_rings=30).validate_against_paper_scene_bounds()
    for n in (1, 9, 31):
        try:
            TunnelAssemblyConfig(n_rings=n).validate_against_paper_scene_bounds()
        except ValueError:
            pass
        else:
            raise AssertionError("out-of-bound paper scene ring count must be rejected")


def test_eq21_is_unrecentered_by_default():
    cfg = TunnelAssemblyConfig(n_rings=5, axis_noise_sigma_m=0.0)
    assembly = sample_tunnel_assembly(cfg, seed=0)
    assert assembly.lateral_recenter_m == (0.0, 0.0)
    assert math.isclose(assembly.poses[0].translation_m[2], 0.1, abs_tol=1e-14)


def test_scene_metadata_records_physical_wavelength_policy():
    packages = [_ring_package(i, bolts=False) for i in range(2)]
    cfg = TunnelAssemblyConfig(
        n_rings=2,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
    )
    assembly = sample_tunnel_assembly(cfg, seed=1)
    scene = build_multi_ring_scene_package(packages, assembly)
    assert scene.metadata["sourceStage"] == "7.1"
    assert scene.metadata["frequencyParameterization"] == "physical_wavelength_by_chainage"
    assert scene.metadata["lateralWavelengthM"] == 50.0
    assert scene.metadata["verticalWavelengthM"] == 100.0
    assert scene.metadata["deterministicAdjacentTransverseStepBoundM"] < 0.0191


def test_explicit_per_ring_omega_override_preserves_legacy_equation():
    cfg = TunnelAssemblyConfig(
        n_rings=7,
        ring_width_m=1.35,
        axis_noise_sigma_m=0.0,
        omega_x_rad_per_ring=0.25,
        omega_z_rad_per_ring=0.4,
    )
    assembly = sample_tunnel_assembly(cfg, seed=3)
    assert cfg.uses_legacy_omega_x_override
    assert cfg.uses_legacy_omega_z_override
    for i, pose in enumerate(assembly.poses):
        assert math.isclose(pose.translation_m[0], 0.1 * math.sin(0.25 * i), abs_tol=1e-14)
        assert math.isclose(pose.translation_m[2], 0.1 * math.cos(0.4 * i), abs_tol=1e-14)
