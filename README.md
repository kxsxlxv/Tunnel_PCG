# Tunnel_PCG — Tunnel Scanner reimplementation

Current milestone: **Stage 7.1 — physical-wavelength multi-ring tunnel assembly**.

The repository reconstructs and extends the geometry-generation side of Yang et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*.

## Implemented

    Stage 1    six-segment K/B/A ring and angle constraints
    Stage 2    ring-wise dislocation/rotation closure solver
    Stage 3    deformation state -> rigid segment geometry
    Stage 4    prescribed radial joints + provisional circumferential collar
    Stage 5    engine-neutral ScenePackage + semantic IDs + Blender adapter
    Stage 5.1  adaptive cylindrical render/LiDAR mesh
    Stage 6    bolt pockets, heads, Blender Boolean embedding
    Stage 7    Eq. (21) multi-ring S-curve/stagger assembly
    Stage 7.1  wavelength-by-chainage correction for physical smoothness

All reconstruction assumptions and discovered formula ambiguities are documented in STAGE*_REPORT.md.

## Stage 7.1 axis model

The paper gives the scene-level form

    x_i = A*sin(omega_x*i) + epsilon_x
    y_i = i*L_seg
    z_i = A*cos(omega_z*i) + epsilon_z

and provides A=0.1 m as an example, but it does not publish numerical values for omega_x or omega_z.

The original Stage-7 engineering default tied omega to N_ring, which meant a five-ring export was much more sharply curved than a thirty-ring export. Stage 7.1 fixes that.

Production defaults are now physical wavelengths evaluated by chainage s=i*L_seg:

    x(s) = A*sin(2*pi*s/lambda_x) + epsilon_x
    z(s) = A*cos(2*pi*s/lambda_z) + epsilon_z

Default reconstruction values:

    A        = 0.1 m
    lambda_x = 50 m
    lambda_z = 100 m
    sigma(epsilon_x,z) = 0.005 m

The wavelength values are explicit engineering defaults, not values recovered from the paper.

For the default 1.35 m ring width, the deterministic sinusoidal centre-to-centre step is bounded by:

    X:          16.944 mm
    Z:           8.480 mm
    transverse: 18.948 mm

Independent Gaussian axis noise is added on top of that bound.

Crucially, the centreline at a given chainage is now independent of how many rings are exported. Five-ring and thirty-ring scenes share exactly the same deterministic first five centre positions.

Legacy omega_x_rad_per_ring / omega_z_rad_per_ring overrides remain supported for reproducing earlier scenes or explicit user input.

## Ring rotation modes

    continuous
    paper_constant_nominal
    ringwise_gaussian

ringwise_gaussian samples nominal stagger angles inside the Table-2 +/-6*theta_K bound and is the default of the CLI generator. The low-level assembly config defaults to continuous joints.

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

Optional wavelength controls:

    --lateral-wavelength-m 50
    --vertical-wavelength-m 100

For a faster Blender check:

    PYTHONPATH=src python examples/generate_stage7_tunnel.py --rings 5

## Blender verification

    blender --background --python scripts/blender_verify_stage7.py -- \
        examples/stage7_tunnel_scene.json \
        --report examples/blender_stage7_runtime_report.json \
        --save-blend examples/stage7_tunnel_scene.blend

Stage 6 bolt Booleans and the Stage-7 multi-ring scene have already been visually confirmed in Blender. Stage 7.1 changes only ring X/Z positions, not mesh topology or Boolean identity.

## Tests

    python -m pip install -e '.[test]'
    pytest

Current regression result:

    95 tests passed

Stage-7.1 stress verification:

    2,000 pose scenes
    39,877 ring poses
    50 full 5-ring scenes
    13,200 SceneObjects
    9,000 planned Boolean operations
    10 JSON round-trips

    axis-noise empirical std                 0.0049953 m
    configured sigma                         0.0050000 m
    max Y-spacing error                      0.0 m
    max rigid transform error                1.78e-15 m
    export-length invariance error           0.0 m
    deterministic transverse step bound      0.0189477 m
    max observed deterministic step          0.0189476 m
    max nominal stagger                      134.902 deg
    Table-2 nominal bound                    135.000 deg

    PASS

An independent trimesh 4.11.1 check reports all 696 mesh objects in the canonical pre-Boolean 13-ring scene as watertight, winding-consistent, and positive-volume.

## Important multi-ring Boolean fix

Bolts are identified by

    (ringID, boltIndex)

rather than boltIndex alone, preventing collisions between rings.

## Next stage

With Stage 7.1 complete, the next stage is ancillary infrastructure driven along the longitudinal tunnel assembly: pavement/walkway, rails, and tube-like services.
