from __future__ import annotations

"""High-level Stage-7 tunnel scene builder.

This module intentionally composes the already-tested ring, joint, bolt, scene,
and assembly layers. It does not introduce new geometry equations.
"""

from dataclasses import dataclass

import numpy as np

from .angles import sample_six_segment_angles
from .ancillary import (
    AncillaryConfig,
    AncillarySamplingPolicy,
    build_ancillary_set,
    sample_ancillary_config,
)
from .assembly import (
    TunnelAssembly,
    TunnelAssemblyConfig,
    build_multi_ring_scene_package,
    sample_tunnel_assembly,
)
from .bolts import (
    BoltLayoutType,
    BoltPerturbationConfig,
    build_bolt_set,
    sample_bolt_config,
)
from .config import RingConfig
from .curved_mesh import SurfaceMeshingConfig
from .joints import build_prescribed_joint_set, sample_joint_config
from .mesh import build_ring_mesh
from .scene import LabelPolicy, ScenePackage, build_nominal_scene_package


@dataclass(frozen=True)
class ProceduralTunnelBuild:
    scene: ScenePackage
    assembly: TunnelAssembly
    ring_packages: tuple[ScenePackage, ...]


def _child_seed(master_seed: int, ring_id: int, stream: int) -> int:
    state = np.random.SeedSequence(
        [int(master_seed), int(ring_id), int(stream)]
    ).generate_state(1)
    return int(state[0])


def build_procedural_nominal_tunnel(
    *,
    ring_config: RingConfig | None = None,
    assembly_config: TunnelAssemblyConfig | None = None,
    surface_meshing: SurfaceMeshingConfig | None = None,
    include_bolts: bool = True,
    bolt_layout: BoltLayoutType | str = BoltLayoutType.TYPE1_CENTERED,
    bolt_perturbation: BoltPerturbationConfig | None = None,
    include_ancillary: bool = False,
    ancillary_config: AncillaryConfig | None = None,
    ancillary_sampling_policy: AncillarySamplingPolicy | str = AncillarySamplingPolicy.REFERENCE,
    label_policy: LabelPolicy = LabelPolicy.SEG2TUNNEL_LIKE,
    include_terminal_circumferential_joint: bool = False,
    include_prescribed_joint_solids: bool = True,
    bolt_boolean_overlap_m: float = 0.005,
    seed: int = 5812,
) -> ProceduralTunnelBuild:
    """Build a complete nominal multi-ring scene ready for Blender import.

    Geometry is independently sampled for each ring while retaining a single
    global seed. The final ring omits its back circumferential joint by default,
    so a tunnel of N rings contains exactly N-1 inter-ring joint interfaces.
    """
    ring_config = ring_config or RingConfig()
    surface_meshing = surface_meshing or SurfaceMeshingConfig()
    bolt_layout = BoltLayoutType(bolt_layout)
    bolt_perturbation = bolt_perturbation or BoltPerturbationConfig()
    ancillary_sampling_policy = AncillarySamplingPolicy(ancillary_sampling_policy)

    if assembly_config is None:
        assembly_config = TunnelAssemblyConfig(ring_width_m=ring_config.width_m)
    if abs(assembly_config.ring_width_m - ring_config.width_m) > 1e-12:
        raise ValueError(
            "assembly_config.ring_width_m must equal ring_config.width_m so adjacent "
            "ring chainage is coherent"
        )

    ancillary_set = None
    if include_ancillary:
        if ancillary_config is None:
            ancillary_config = sample_ancillary_config(
                ring_config.inner_radius_m,
                seed=_child_seed(seed, 0, 5_000),
                policy=ancillary_sampling_policy,
            )
        ancillary_set = build_ancillary_set(
            inner_radius_m=ring_config.inner_radius_m,
            length_m=ring_config.width_m,
            config=ancillary_config,
        )

    ring_packages: list[ScenePackage] = []
    for ring_id in range(assembly_config.n_rings):
        angles = sample_six_segment_angles(
            seed=_child_seed(seed, ring_id, 1)
        )
        ring = build_ring_mesh(ring_config, angles)
        joints = build_prescribed_joint_set(
            ring,
            sample_joint_config(seed=_child_seed(seed, ring_id, 2)),
        )

        bolts = None
        if include_bolts:
            bolt_cfg = sample_bolt_config(seed=_child_seed(seed, ring_id, 3))
            bolts = build_bolt_set(
                ring,
                bolt_cfg,
                bolt_layout,
                seed=_child_seed(seed, ring_id, 4),
                perturbation_config=bolt_perturbation,
            )

        ring_packages.append(
            build_nominal_scene_package(
                ring,
                joints,
                ring_id=ring_id,
                include_radial_joints=include_prescribed_joint_solids,
                include_circumferential_front=False,
                include_circumferential_back=(
                    include_prescribed_joint_solids
                    and (
                        ring_id < assembly_config.n_rings - 1
                        or include_terminal_circumferential_joint
                    )
                ),
                label_policy=label_policy,
                surface_meshing=surface_meshing,
                bolts=bolts,
                bolt_boolean_overlap_m=bolt_boolean_overlap_m,
                ancillary=ancillary_set,
            )
        )

    assembly = sample_tunnel_assembly(
        assembly_config,
        seed=_child_seed(seed, 0, 10_000),
    )
    scene = build_multi_ring_scene_package(
        tuple(ring_packages),
        assembly,
        name=(
            f"tunnel_scanner_stage8_{assembly_config.n_rings:02d}_rings"
            if include_ancillary
            else f"tunnel_scanner_stage7_1_{assembly_config.n_rings:02d}_rings"
        ),
    )
    metadata = dict(scene.metadata)
    metadata.update(
        {
            "proceduralBuild": {
                "masterSeed": int(seed),
                "ringGeometryRandomizedIndependently": True,
                "includeBolts": bool(include_bolts),
                "boltLayout": bolt_layout.value if include_bolts else None,
                "includeAncillary": bool(include_ancillary),
                "ancillarySamplingPolicy": (
                    ancillary_sampling_policy.value if include_ancillary else None
                ),
                "ancillarySceneGlobalCrossSection": bool(include_ancillary),
                "ancillaryObjectCountPerRing": (
                    len(ancillary_set.meshes) if ancillary_set is not None else 0
                ),
                "labelPolicy": label_policy.value,
                "includePrescribedJointSolids": bool(
                    include_prescribed_joint_solids
                ),
                "terminalCircumferentialJoint": bool(
                    include_terminal_circumferential_joint
                ),
                "expectedCircumferentialInterfaces": (
                    assembly_config.n_rings
                    if include_terminal_circumferential_joint
                    else max(0, assembly_config.n_rings - 1)
                ),
            }
        }
    )
    scene = ScenePackage(
        name=scene.name,
        mode=scene.mode,
        label_policy=scene.label_policy,
        objects=scene.objects,
        metadata=metadata,
    )
    return ProceduralTunnelBuild(
        scene=scene,
        assembly=assembly,
        ring_packages=tuple(ring_packages),
    )
