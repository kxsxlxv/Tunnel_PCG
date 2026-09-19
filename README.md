# Tunnel_PCG — Tunnel Scanner reimplementation

Current milestone: **Stage 7 — multi-ring tunnel assembly**.

The repository reconstructs and extends the geometry-generation side of Yang et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*.

## Implemented

    Stage 1   six-segment K/B/A ring and angle constraints
    Stage 2   ring-wise dislocation/rotation closure solver
    Stage 3   deformation state -> rigid segment geometry
    Stage 4   prescribed radial joints + provisional circumferential collar
    Stage 5   engine-neutral ScenePackage + semantic IDs + Blender adapter
    Stage 5.1 adaptive cylindrical render/LiDAR mesh
    Stage 6   bolt pockets, heads, Blender Boolean embedding
    Stage 7   Eq. (21) multi-ring S-curve/stagger assembly

All reconstruction assumptions and discovered formula ambiguities are documented in STAGE*_REPORT.md.

## Stage 7

A tunnel is now built from independent ring ScenePackages and placed with the paper's scene-level model:

    x_i = A*sin(omega_x*i) + epsilon_x
    y_i = i*L_seg
    z_i = A*cos(omega_z*i) + epsilon_z
    phi_i = axial ring rotation

Default amplitude:

    A = 0.1 m

The paper does not publish numeric omega_x/omega_z, so the implementation exposes both and marks its defaults as engineering choices.

The printed N(0,0.005 m^2) axis-noise notation is treated explicitly as ambiguous; the working reconstruction uses sigma=0.005 m.

## Ring rotation modes

    continuous
    paper_constant_nominal
    ringwise_gaussian

ringwise_gaussian samples nominal stagger angles inside the Table-2 +/-6*theta_K bound and is the default of the Stage-7 CLI generator. The low-level assembly config defaults to continuous joints.

## Canonical 13-ring scene

Seed 5812:

    13 rings
    17.55 m chainage length
    78 lining segments
    78 radial joints
    72 circumferential collar pieces (12 interfaces)
    234 bolt heads
    234 pocket cutters
    696 pre-Boolean objects
    468 planned Boolean operations

The generated full scene JSON is about 4–5 MB and is intentionally generated locally instead of committed.

## Generate a tunnel

    PYTHONPATH=src python examples/generate_stage7_tunnel.py --rings 13

Outputs:

    examples/stage7_tunnel_scene.json
    examples/stage7_tunnel_scene_centerline.json
    examples/stage7_tunnel_scene_summary.json

For a faster Blender smoke test:

    PYTHONPATH=src python examples/generate_stage7_tunnel.py --rings 5

## Blender verification

    blender --background --python scripts/blender_verify_stage7.py -- \
        examples/stage7_tunnel_scene.json \
        --report examples/blender_stage7_runtime_report.json \
        --save-blend examples/stage7_tunnel_scene.blend

See STAGE7_BLENDER_SMOKE_TEST.md.

## Tests

    python -m pip install -e '.[test]'
    pytest

Current regression result:

    92 tests passed

Stage-7 stress verification:

    2,000 pose scenes
    39,877 ring poses
    50 full 5-ring scenes
    13,200 SceneObjects
    9,000 planned Boolean operations
    10 JSON round-trips

    axis-noise empirical std     0.0049953 m
    configured sigma             0.0050000 m
    max Y-spacing error          0.0 m
    max rigid transform error    1.78e-15 m
    max nominal stagger          134.902 deg
    Table-2 nominal bound        135.000 deg

    PASS

An independent trimesh 4.11.1 check also reports all 696 mesh objects in the canonical pre-Boolean 13-ring scene as watertight, winding-consistent, and positive-volume.

## Important Stage-7 fix

Stage 6 used bolt indices local to one ring. Multi-ring assembly revealed that Boolean planning must identify a bolt by:

    (ringID, boltIndex)

rather than boltIndex alone. This is fixed in the Blender adapter and regression-tested.

## Current validation gate

The one-ring Stage-6 Boolean geometry has already passed a real Blender visual test. Before adding track/walkway/services, run the Stage-7 five-ring verifier to confirm that multi-ring Boolean identity and scene hierarchy behave correctly in the user's Blender version.

## Next stage

After that smoke test, Stage 8 should add the ancillary infrastructure layer from the paper: pavement/walkway, rails, and tube-like services, driven by the Stage-7 longitudinal alignment rather than modeled as isolated primitives.
