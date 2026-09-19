from __future__ import annotations

"""Stage-7/7.1 multi-ring tunnel assembly.

Stage 7 implements the scene-level construction described around Eq. (21) of
Yang et al. (2026): individual ring ScenePackages are placed along +Y with
sinusoidal X/Z offsets and optional axial ring rotation.

Stage 7.1 changes only the default parameterization of the unpublished spatial
frequencies. The paper publishes omega_x and omega_z symbolically but does not
give numeric values. A frequency tied to N_ring makes physical curvature change
when the export window changes. Production defaults are therefore expressed as
physical wavelengths in metres and evaluated at chainage s=i*L_seg. Explicit
omega_*_rad_per_ring overrides are retained for exact reproduction of earlier
scenes or user-specified paper-style inputs.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

import numpy as np

from .mesh import Vec3
from .scene import SceneMode, SceneObject, ScenePackage


class RingRotationStrategy(str, Enum):
    """How Eq. (21)'s nominal stagger rotation is interpreted."""

    CONTINUOUS = "continuous"
    PAPER_CONSTANT_NOMINAL = "paper_constant_nominal"
    RINGWISE_GAUSSIAN = "ringwise_gaussian"


@dataclass(frozen=True)
class TunnelAssemblyConfig:
    n_rings: int = 13
    ring_width_m: float = 1.35
    displacement_amplitude_m: float = 0.1

    # Stage-7.1 production defaults. These are engineering defaults, not values
    # published by Yang et al. 50 m / 100 m preserve the earlier intent that Z
    # changes more slowly than X, but make smoothness independent of N_ring.
    lateral_wavelength_m: float = 50.0
    vertical_wavelength_m: float = 100.0

    # Compatibility / explicit paper-style overrides. If supplied, these take
    # precedence over wavelength_m and are converted to rad/m internally.
    omega_x_rad_per_ring: float | None = None
    omega_z_rad_per_ring: float | None = None

    axis_noise_sigma_m: float = 0.005
    ring_rotation_strategy: RingRotationStrategy = RingRotationStrategy.CONTINUOUS
    nominal_stagger_deg: float | None = None
    theta_k_deg: float = 22.5
    stagger_sigma_fraction_of_bound: float = 1.0 / 3.0
    angular_imperfection_fraction: float = 0.1
    recenter_lateral_offsets: bool = False

    def __post_init__(self) -> None:
        if not 1 <= self.n_rings <= 10_000:
            raise ValueError("n_rings must be in [1, 10000]")
        if not math.isfinite(self.ring_width_m) or self.ring_width_m <= 0.0:
            raise ValueError("ring_width_m must be finite and positive")
        if (
            not math.isfinite(self.displacement_amplitude_m)
            or self.displacement_amplitude_m < 0.0
        ):
            raise ValueError("displacement_amplitude_m must be finite and non-negative")
        for value, name in (
            (self.lateral_wavelength_m, "lateral_wavelength_m"),
            (self.vertical_wavelength_m, "vertical_wavelength_m"),
        ):
            if not math.isfinite(value) or value <= 0.0:
                raise ValueError(f"{name} must be finite and positive")
        if not math.isfinite(self.axis_noise_sigma_m) or self.axis_noise_sigma_m < 0.0:
            raise ValueError("axis_noise_sigma_m must be finite and non-negative")
        if not math.isfinite(self.theta_k_deg) or self.theta_k_deg <= 0.0:
            raise ValueError("theta_k_deg must be finite and positive")
        if self.stagger_sigma_fraction_of_bound <= 0.0:
            raise ValueError("stagger_sigma_fraction_of_bound must be positive")
        if self.angular_imperfection_fraction < 0.0:
            raise ValueError("angular_imperfection_fraction must be non-negative")
        for value, name in (
            (self.omega_x_rad_per_ring, "omega_x_rad_per_ring"),
            (self.omega_z_rad_per_ring, "omega_z_rad_per_ring"),
        ):
            if value is not None and not math.isfinite(value):
                raise ValueError(f"{name} must be finite or None")
        if self.nominal_stagger_deg is not None:
            bound = self.stagger_bound_deg
            if not -bound <= self.nominal_stagger_deg <= bound:
                raise ValueError(
                    f"nominal_stagger_deg must lie within Table-2 bound +/-{bound:g} deg"
                )

    def validate_against_paper_scene_bounds(self) -> None:
        if not 10 <= self.n_rings <= 30:
            raise ValueError("Table-1 N_ring bounds are 10..30 rings per scene")

    @property
    def stagger_bound_deg(self) -> float:
        return 6.0 * self.theta_k_deg

    @property
    def uses_legacy_omega_x_override(self) -> bool:
        return self.omega_x_rad_per_ring is not None

    @property
    def uses_legacy_omega_z_override(self) -> bool:
        return self.omega_z_rad_per_ring is not None

    @property
    def resolved_omega_x_rad_per_m(self) -> float:
        if self.omega_x_rad_per_ring is not None:
            return self.omega_x_rad_per_ring / self.ring_width_m
        return 2.0 * math.pi / self.lateral_wavelength_m

    @property
    def resolved_omega_z_rad_per_m(self) -> float:
        if self.omega_z_rad_per_ring is not None:
            return self.omega_z_rad_per_ring / self.ring_width_m
        return 2.0 * math.pi / self.vertical_wavelength_m

    @property
    def resolved_omega_x(self) -> float:
        """Compatibility property: resolved angular increment per ring."""
        return self.resolved_omega_x_rad_per_m * self.ring_width_m

    @property
    def resolved_omega_z(self) -> float:
        """Compatibility property: resolved angular increment per ring."""
        return self.resolved_omega_z_rad_per_m * self.ring_width_m

    @property
    def resolved_lateral_wavelength_m(self) -> float | None:
        if self.omega_x_rad_per_ring is not None:
            omega_m = abs(self.resolved_omega_x_rad_per_m)
            return None if omega_m == 0.0 else 2.0 * math.pi / omega_m
        return self.lateral_wavelength_m

    @property
    def resolved_vertical_wavelength_m(self) -> float | None:
        if self.omega_z_rad_per_ring is not None:
            omega_m = abs(self.resolved_omega_z_rad_per_m)
            return None if omega_m == 0.0 else 2.0 * math.pi / omega_m
        return self.vertical_wavelength_m

    def deterministic_adjacent_step_bound_x_m(self) -> float:
        phase = abs(self.resolved_omega_x)
        return 2.0 * self.displacement_amplitude_m * abs(math.sin(0.5 * phase))

    def deterministic_adjacent_step_bound_z_m(self) -> float:
        phase = abs(self.resolved_omega_z)
        return 2.0 * self.displacement_amplitude_m * abs(math.sin(0.5 * phase))

    def deterministic_adjacent_transverse_step_bound_m(self) -> float:
        return math.hypot(
            self.deterministic_adjacent_step_bound_x_m(),
            self.deterministic_adjacent_step_bound_z_m(),
        )


@dataclass(frozen=True)
class RingPose:
    ring_index: int
    translation_m: Vec3
    rotation_y_deg: float
    nominal_rotation_deg: float
    angular_imperfection_deg: float
    epsilon_x_m: float
    epsilon_z_m: float
    chainage_m: float


@dataclass(frozen=True)
class TunnelAssembly:
    config: TunnelAssemblyConfig
    poses: tuple[RingPose, ...]
    seed: int | None
    lateral_recenter_m: tuple[float, float]

    def __post_init__(self) -> None:
        if len(self.poses) != self.config.n_rings:
            raise ValueError("pose count must equal config.n_rings")
        indices = [p.ring_index for p in self.poses]
        if indices != list(range(self.config.n_rings)):
            raise ValueError("ring poses must be sequentially indexed from zero")

    @property
    def centreline_points(self) -> tuple[Vec3, ...]:
        return tuple(p.translation_m for p in self.poses)

    @property
    def length_by_chainage_m(self) -> float:
        if not self.poses:
            return 0.0
        return self.poses[-1].chainage_m + self.config.ring_width_m


def _truncated_zero_mean(
    rng: np.random.Generator,
    *,
    bound: float,
    sigma: float,
    max_attempts: int = 1000,
) -> float:
    if bound <= 0.0:
        return 0.0
    sigma = max(float(sigma), 1e-12)
    for _ in range(max_attempts):
        x = float(rng.normal(0.0, sigma))
        if -bound <= x <= bound:
            return x
    return min(max(x, -bound), bound)


def sample_tunnel_assembly(
    config: TunnelAssemblyConfig,
    *,
    seed: int | None = None,
) -> TunnelAssembly:
    """Sample ring poses from Eq. (21) plus explicit Stage-7.1 frequency policy."""
    rng = np.random.default_rng(seed)
    omega_x_m = config.resolved_omega_x_rad_per_m
    omega_z_m = config.resolved_omega_z_rad_per_m
    A = config.displacement_amplitude_m

    eps_x = rng.normal(0.0, config.axis_noise_sigma_m, config.n_rings)
    eps_z = rng.normal(0.0, config.axis_noise_sigma_m, config.n_rings)

    chainages = np.arange(config.n_rings, dtype=float) * config.ring_width_m
    raw_x = np.array(
        [A * math.sin(omega_x_m * s) + float(eps_x[i]) for i, s in enumerate(chainages)],
        dtype=float,
    )
    raw_z = np.array(
        [A * math.cos(omega_z_m * s) + float(eps_z[i]) for i, s in enumerate(chainages)],
        dtype=float,
    )

    recenter_x = float(raw_x.mean()) if config.recenter_lateral_offsets else 0.0
    recenter_z = float(raw_z.mean()) if config.recenter_lateral_offsets else 0.0
    raw_x -= recenter_x
    raw_z -= recenter_z

    bound = config.stagger_bound_deg
    constant_phi = config.nominal_stagger_deg
    if config.ring_rotation_strategy is RingRotationStrategy.PAPER_CONSTANT_NOMINAL:
        if constant_phi is None:
            constant_phi = _truncated_zero_mean(
                rng,
                bound=bound,
                sigma=bound * config.stagger_sigma_fraction_of_bound,
            )

    poses: list[RingPose] = []
    for i in range(config.n_rings):
        if config.ring_rotation_strategy is RingRotationStrategy.CONTINUOUS:
            nominal = 0.0
            delta = 0.0
        elif config.ring_rotation_strategy is RingRotationStrategy.PAPER_CONSTANT_NOMINAL:
            assert constant_phi is not None
            nominal = float(constant_phi)
            sigma_delta = config.angular_imperfection_fraction * abs(nominal)
            delta = (
                0.0 if sigma_delta == 0.0 else float(rng.normal(0.0, sigma_delta))
            )
        else:
            nominal = _truncated_zero_mean(
                rng,
                bound=bound,
                sigma=bound * config.stagger_sigma_fraction_of_bound,
            )
            sigma_delta = config.angular_imperfection_fraction * abs(nominal)
            delta = (
                0.0 if sigma_delta == 0.0 else float(rng.normal(0.0, sigma_delta))
            )

        chainage = float(chainages[i])
        poses.append(
            RingPose(
                ring_index=i,
                translation_m=(float(raw_x[i]), chainage, float(raw_z[i])),
                rotation_y_deg=float(nominal + delta),
                nominal_rotation_deg=float(nominal),
                angular_imperfection_deg=float(delta),
                epsilon_x_m=float(eps_x[i]),
                epsilon_z_m=float(eps_z[i]),
                chainage_m=chainage,
            )
        )

    return TunnelAssembly(
        config=config,
        poses=tuple(poses),
        seed=seed,
        lateral_recenter_m=(recenter_x, recenter_z),
    )


def _transform_point_with_axial_rotation(
    point: Vec3, pose: RingPose, rotation_y_deg: float
) -> Vec3:
    x, y, z = point
    a = math.radians(rotation_y_deg)
    c, s = math.cos(a), math.sin(a)
    xr = c * x + s * z
    zr = -s * x + c * z
    tx, ty, tz = pose.translation_m
    return (xr + tx, y + ty, zr + tz)


def transform_point_by_ring_pose(point: Vec3, pose: RingPose) -> Vec3:
    """Rotate lining-local geometry about +Y then translate."""
    return _transform_point_with_axial_rotation(point, pose, pose.rotation_y_deg)


def _alignment_offset_xz_for_local_y(
    assembly: TunnelAssembly,
    ring_index: int,
    local_y_m: float,
) -> tuple[float, float]:
    """Piecewise-linear X/Z alignment through ring centres.

    Adjacent per-ring ancillary slices share the midpoint of neighbouring ring
    centre offsets at their common longitudinal boundary. The local y=0 station
    passes exactly through the current ring centre offset.
    """
    poses = assembly.poses
    pose = poses[ring_index]
    L = assembly.config.ring_width_m
    u = float(local_y_m) / L
    if u < -0.500000001 or u > 0.500000001:
        raise ValueError(
            f"ancillary local y={local_y_m:g} lies outside ring half-width +/-{0.5*L:g}"
        )

    cx, _cy, cz = pose.translation_m
    if u >= 0.0:
        if ring_index + 1 < len(poses):
            nx, _ny, nz = poses[ring_index + 1].translation_m
            dx, dz = nx - cx, nz - cz
        elif ring_index > 0:
            px, _py, pz = poses[ring_index - 1].translation_m
            dx, dz = cx - px, cz - pz
        else:
            dx = dz = 0.0
    else:
        if ring_index > 0:
            px, _py, pz = poses[ring_index - 1].translation_m
            dx, dz = cx - px, cz - pz
        elif ring_index + 1 < len(poses):
            nx, _ny, nz = poses[ring_index + 1].translation_m
            dx, dz = nx - cx, nz - cz
        else:
            dx = dz = 0.0
    return (cx + u * dx, cz + u * dz)


def _transform_point_follow_alignment(
    point: Vec3,
    pose: RingPose,
    assembly: TunnelAssembly,
) -> Vec3:
    x, local_y, z = point
    offset_x, offset_z = _alignment_offset_xz_for_local_y(
        assembly, pose.ring_index, local_y
    )
    return (
        x + offset_x,
        pose.chainage_m + local_y,
        z + offset_z,
    )


def transform_scene_object_by_ring_pose(
    obj: SceneObject,
    pose: RingPose,
    assembly: TunnelAssembly | None = None,
) -> SceneObject:
    if obj.ring_id != pose.ring_index:
        raise ValueError(
            f"scene object ring_id={obj.ring_id} does not match pose index={pose.ring_index}"
        )
    extra = dict(obj.extra_properties)
    follow_scene_alignment = bool(extra.get("followSceneAlignment", False))
    follow_ring_rotation = bool(extra.get("followRingAxialRotation", True))
    if follow_scene_alignment and assembly is None:
        raise ValueError(
            f"{obj.name}: followSceneAlignment requires the full TunnelAssembly"
        )
    applied_rotation_deg = (
        0.0
        if follow_scene_alignment
        else (pose.rotation_y_deg if follow_ring_rotation else 0.0)
    )
    extra.update(
        {
            "ringTranslationX": float(pose.translation_m[0]),
            "ringTranslationY": float(pose.translation_m[1]),
            "ringTranslationZ": float(pose.translation_m[2]),
            "ringRotationDeg": float(pose.rotation_y_deg),
            "objectAppliedAxialRotationDeg": float(applied_rotation_deg),
            "ringNominalRotationDeg": float(pose.nominal_rotation_deg),
            "ringAngularImperfectionDeg": float(pose.angular_imperfection_deg),
            "ringChainageM": float(pose.chainage_m),
            "objectTransformPolicy": (
                "stitched_scene_alignment"
                if follow_scene_alignment
                else (
                    "ring_translation_and_axial_rotation"
                    if follow_ring_rotation
                    else "ring_translation_only"
                )
            ),
        }
    )
    if follow_scene_alignment:
        assert assembly is not None
        transformed_vertices = tuple(
            _transform_point_follow_alignment(v, pose, assembly) for v in obj.vertices
        )
    else:
        transformed_vertices = tuple(
            _transform_point_with_axial_rotation(v, pose, applied_rotation_deg)
            for v in obj.vertices
        )
    return SceneObject(
        name=obj.name,
        vertices=transformed_vertices,
        faces=obj.faces,
        object_type=obj.object_type,
        ring_id=obj.ring_id,
        label_id=obj.label_id,
        instance_id=obj.instance_id,
        semantic_class=obj.semantic_class,
        segment_id=obj.segment_id,
        segment_name=obj.segment_name,
        segment_kind=obj.segment_kind,
        reconstruction=(
            f"{obj.reconstruction}+stage7_1_ring_pose"
            if obj.reconstruction
            else "stage7_1_ring_pose"
        ),
        collection_path=obj.collection_path,
        extra_properties=extra,
    )


def build_multi_ring_scene_package(
    ring_packages: Sequence[ScenePackage],
    assembly: TunnelAssembly,
    *,
    name: str = "tunnel_scanner_stage7_1_tunnel",
) -> ScenePackage:
    """Merge ring-local packages into one world-space multi-ring scene."""
    if len(ring_packages) != assembly.config.n_rings:
        raise ValueError("ring package count must equal assembly.config.n_rings")
    if not ring_packages:
        raise ValueError("at least one ring package is required")

    label_policy = ring_packages[0].label_policy
    objects: list[SceneObject] = []
    ring_metadata: list[dict] = []
    for i, (package, pose) in enumerate(zip(ring_packages, assembly.poses)):
        if package.label_policy is not label_policy:
            raise ValueError("all ring packages must use the same label policy")
        if package.ring_ids != (i,):
            raise ValueError(
                f"ring package {i} must contain exactly ringID={i}; got {package.ring_ids}"
            )
        objects.extend(
            transform_scene_object_by_ring_pose(obj, pose, assembly)
            for obj in package.objects
        )
        ring_metadata.append(
            {
                "ringID": i,
                "chainageM": pose.chainage_m,
                "translationM": list(pose.translation_m),
                "rotationYDeg": pose.rotation_y_deg,
                "nominalRotationDeg": pose.nominal_rotation_deg,
                "angularImperfectionDeg": pose.angular_imperfection_deg,
                "sourcePackage": package.name,
            }
        )

    cfg = assembly.config
    legacy_override = (
        cfg.uses_legacy_omega_x_override or cfg.uses_legacy_omega_z_override
    )
    metadata = {
        "sourceStage": "7.1",
        "sourceEquation": "Yang et al. (2026) Eq. (21)",
        "ringCount": cfg.n_rings,
        "paperRingCountBounds": [10, 30],
        "ringWidthM": cfg.ring_width_m,
        "chainageLengthM": assembly.length_by_chainage_m,
        "axisDisplacementAmplitudeM": cfg.displacement_amplitude_m,
        "frequencyParameterization": (
            "explicit_rad_per_ring_override"
            if legacy_override
            else "physical_wavelength_by_chainage"
        ),
        "lateralWavelengthM": cfg.resolved_lateral_wavelength_m,
        "verticalWavelengthM": cfg.resolved_vertical_wavelength_m,
        "omegaXRadPerM": cfg.resolved_omega_x_rad_per_m,
        "omegaZRadPerM": cfg.resolved_omega_z_rad_per_m,
        "omegaXRadPerRing": cfg.resolved_omega_x,
        "omegaZRadPerRing": cfg.resolved_omega_z,
        "frequencyStatus": (
            "explicit omega override supplied by caller"
            if legacy_override
            else (
                "Stage-7.1 engineering defaults: 50 m lateral wavelength and "
                "100 m vertical wavelength; paper publishes omega symbols but no values"
            )
        ),
        "deterministicAdjacentStepBoundXM": cfg.deterministic_adjacent_step_bound_x_m(),
        "deterministicAdjacentStepBoundZM": cfg.deterministic_adjacent_step_bound_z_m(),
        "deterministicAdjacentTransverseStepBoundM": (
            cfg.deterministic_adjacent_transverse_step_bound_m()
        ),
        "axisNoiseSigmaM": cfg.axis_noise_sigma_m,
        "axisNoiseStatus": (
            "Stage-7.1 interprets printed N(0,0.005 m^2) as sigma=0.005 m; "
            "literal variance would imply ~70.7 mm sigma"
        ),
        "rotationStrategy": cfg.ring_rotation_strategy.value,
        "staggerBoundDeg": cfg.stagger_bound_deg,
        "angularImperfectionFraction": cfg.angular_imperfection_fraction,
        "lateralOffsetsRecentered": cfg.recenter_lateral_offsets,
        "lateralRecenterM": list(assembly.lateral_recenter_m),
        "seed": assembly.seed,
        "coordinateConvention": {
            "longitudinalAxis": "+Y",
            "crossSection": "XZ",
            "ringRotationAxis": "+Y",
            "units": "metres",
        },
        "ringPoses": ring_metadata,
        "ancillaryTransformPolicy": {
            "objectsWithStitchedAlignment": sum(
                1
                for obj in objects
                if obj.extra_properties.get("followSceneAlignment") is True
            ),
            "policy": (
                "Stage-8 ancillary infrastructure uses a piecewise-linear X/Z sweep "
                "through ring centres with shared inter-ring boundary cross-sections; "
                "it does not follow segment-ring axial staggering and remains fixed "
                "relative to the tunnel gravity frame"
            ),
        },
        "booleanPipeline": (
            "Stage-6 cutter/head metadata is preserved after Stage-7.1 world transform; "
            "Blender Boolean targets remain ring-local stable names"
        ),
    }
    return ScenePackage(
        name=name,
        mode=SceneMode.MULTI_RING_TUNNEL,
        label_policy=label_policy,
        objects=tuple(objects),
        metadata=metadata,
    )
