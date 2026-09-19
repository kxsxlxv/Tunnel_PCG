from __future__ import annotations

"""Stage-7 multi-ring tunnel assembly.

This module implements the scene-level construction described around Eq. (21)
of Yang et al. (2026): individual ring ScenePackages are placed along +Y with
sinusoidal X/Z offsets and optional ring rotation about the tunnel axis.

The paper gives the form of Eq. (21), A≈0.1 m, the stagger-angle bounds and the
noise distributions, but does not publish omega_x/omega_z numerical values or
an unambiguous policy for how the nominal stagger angle phi is selected from
ring to ring. Those choices are explicit configuration here.
"""

from dataclasses import dataclass
from enum import Enum
import math
from typing import Sequence

import numpy as np

from .mesh import Vec3
from .scene import SceneMode, SceneObject, ScenePackage


class RingRotationStrategy(str, Enum):
    """How Eq. (21)'s nominal stagger rotation is interpreted.

    CONTINUOUS:
        Continuous-joint tunnel; every ring has zero axial rotation.

    PAPER_CONSTANT_NOMINAL:
        Literal/common-phi reading of phi_i = phi + delta_i. A single
        nominal phi is used for the whole scene, with independent imperfections.

    RINGWISE_GAUSSIAN:
        Engineering reconstruction consistent with Table 2 saying stagger-angle
        bounds are Gaussian sampled: each ring receives its own nominal phi_i
        from a truncated zero-mean Gaussian within +/-6*theta_K, then delta_i is
        sampled with sigma=0.1*|phi_i|. This actually creates ring-to-ring
        staggering and is therefore the production staggered mode.
    """

    CONTINUOUS = "continuous"
    PAPER_CONSTANT_NOMINAL = "paper_constant_nominal"
    RINGWISE_GAUSSIAN = "ringwise_gaussian"


@dataclass(frozen=True)
class TunnelAssemblyConfig:
    n_rings: int = 13
    ring_width_m: float = 1.35
    displacement_amplitude_m: float = 0.1
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
        # Table 1 lists 10–30 rings per synthetic scene. The core accepts a
        # wider range for unit tests and downstream applications, so source-bound
        # validation is explicit rather than silently hard-coded.
        if not 10 <= self.n_rings <= 30:
            raise ValueError("Table-1 N_ring bounds are 10..30 rings per scene")

    @property
    def stagger_bound_deg(self) -> float:
        return 6.0 * self.theta_k_deg

    @property
    def resolved_omega_x(self) -> float:
        """Default: one complete lateral sine wave over the scene."""
        if self.omega_x_rad_per_ring is not None:
            return self.omega_x_rad_per_ring
        if self.n_rings <= 1:
            return 0.0
        return 2.0 * math.pi / (self.n_rings - 1)

    @property
    def resolved_omega_z(self) -> float:
        """Default: half a cosine wave over the scene."""
        if self.omega_z_rad_per_ring is not None:
            return self.omega_z_rad_per_ring
        if self.n_rings <= 1:
            return 0.0
        return math.pi / (self.n_rings - 1)


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
    """Sample ring poses from Eq. (21) plus explicit stagger policy."""
    rng = np.random.default_rng(seed)
    omega_x = config.resolved_omega_x
    omega_z = config.resolved_omega_z
    A = config.displacement_amplitude_m

    eps_x = rng.normal(0.0, config.axis_noise_sigma_m, config.n_rings)
    eps_z = rng.normal(0.0, config.axis_noise_sigma_m, config.n_rings)

    raw_x = np.array(
        [A * math.sin(omega_x * i) + float(eps_x[i]) for i in range(config.n_rings)],
        dtype=float,
    )
    raw_z = np.array(
        [A * math.cos(omega_z * i) + float(eps_z[i]) for i in range(config.n_rings)],
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

        poses.append(
            RingPose(
                ring_index=i,
                translation_m=(
                    float(raw_x[i]),
                    float(i * config.ring_width_m),
                    float(raw_z[i]),
                ),
                rotation_y_deg=float(nominal + delta),
                nominal_rotation_deg=float(nominal),
                angular_imperfection_deg=float(delta),
                epsilon_x_m=float(eps_x[i]),
                epsilon_z_m=float(eps_z[i]),
                chainage_m=float(i * config.ring_width_m),
            )
        )

    return TunnelAssembly(
        config=config,
        poses=tuple(poses),
        seed=seed,
        lateral_recenter_m=(recenter_x, recenter_z),
    )


def transform_point_by_ring_pose(point: Vec3, pose: RingPose) -> Vec3:
    """Rotate about +Y then translate, matching Eq. (21) scene assembly."""
    x, y, z = point
    a = math.radians(pose.rotation_y_deg)
    c, s = math.cos(a), math.sin(a)
    xr = c * x + s * z
    zr = -s * x + c * z
    tx, ty, tz = pose.translation_m
    return (xr + tx, y + ty, zr + tz)


def transform_scene_object_by_ring_pose(obj: SceneObject, pose: RingPose) -> SceneObject:
    if obj.ring_id != pose.ring_index:
        raise ValueError(
            f"scene object ring_id={obj.ring_id} does not match pose index={pose.ring_index}"
        )
    extra = dict(obj.extra_properties)
    extra.update(
        {
            "ringTranslationX": float(pose.translation_m[0]),
            "ringTranslationY": float(pose.translation_m[1]),
            "ringTranslationZ": float(pose.translation_m[2]),
            "ringRotationDeg": float(pose.rotation_y_deg),
            "ringNominalRotationDeg": float(pose.nominal_rotation_deg),
            "ringAngularImperfectionDeg": float(pose.angular_imperfection_deg),
            "ringChainageM": float(pose.chainage_m),
        }
    )
    return SceneObject(
        name=obj.name,
        vertices=tuple(transform_point_by_ring_pose(v, pose) for v in obj.vertices),
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
            f"{obj.reconstruction}+stage7_ring_pose"
            if obj.reconstruction
            else "stage7_ring_pose"
        ),
        collection_path=obj.collection_path,
        extra_properties=extra,
    )


def build_multi_ring_scene_package(
    ring_packages: Sequence[ScenePackage],
    assembly: TunnelAssembly,
    *,
    name: str = "tunnel_scanner_stage7_tunnel",
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
            transform_scene_object_by_ring_pose(obj, pose) for obj in package.objects
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
    metadata = {
        "sourceStage": 7,
        "sourceEquation": "Yang et al. (2026) Eq. (21)",
        "ringCount": cfg.n_rings,
        "paperRingCountBounds": [10, 30],
        "ringWidthM": cfg.ring_width_m,
        "chainageLengthM": assembly.length_by_chainage_m,
        "axisDisplacementAmplitudeM": cfg.displacement_amplitude_m,
        "omegaXRadPerRing": cfg.resolved_omega_x,
        "omegaZRadPerRing": cfg.resolved_omega_z,
        "omegaStatus": (
            "user-specified"
            if cfg.omega_x_rad_per_ring is not None
            and cfg.omega_z_rad_per_ring is not None
            else "contains Stage-7 engineering defaults because the paper publishes symbols but no numeric frequencies"
        ),
        "axisNoiseSigmaM": cfg.axis_noise_sigma_m,
        "axisNoiseStatus": (
            "Stage-7 interprets printed N(0,0.005 m^2) as sigma=0.005 m; "
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
        "booleanPipeline": (
            "Stage-6 cutter/head metadata is preserved after Stage-7 world transform; "
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
