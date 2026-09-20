# Tunnel_PCG — procedural tunnel geometry

Current milestone: **Stage 9 — production geometry / long-tunnel assembly**.

The project began as a geometry-side reconstruction of Yang et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*. Stages 1–8 preserve that reference baseline. Stage 9 turns it into an independent production-oriented procedural asset generator intended for later real-time-engine use, including UNIGINE.

LiDAR synthesis is intentionally not the current priority.

## Implemented

    Stage 1    six-segment K/B/A lining ring and angular constraints
    Stage 2    deformation closure solver
    Stage 3    deformed ring rigid geometry
    Stage 4    prescribed joint reconstruction
    Stage 5    engine-neutral ScenePackage + Blender adapter
    Stage 5.1  curved lining tessellation
    Stage 6    bolt pockets, heads and Blender Booleans
    Stage 7    multi-ring tunnel assembly
    Stage 7.1  physical-wavelength centreline
    Stage 8    pavement, walkway, rails and tube-like services
    Stage 9    continuous production geometry, topology cleanup,
               long tunnels, optional chunking, stable IDs,
               low-poly rail profile

Detailed reconstruction/production assumptions are documented in STAGE*_REPORT.md.

## Stage 9 production model

The canonical geometry stays in **global double coordinates**. There is no mandatory floating origin or coordinate rebasing.

Ring-local physical geometry remains discrete:

    lining rings
    lining segments
    bolt pockets / heads

Longitudinal infrastructure is continuous:

    1 pavement asset
    1 walkway asset
    2 rail assets
    6 reference tube/service assets

The Stage-8 per-ring ancillary solids are not instantiated in production scenes, so their coincident internal end caps no longer exist.

## Continuous centreline

Lining, bolt tools and infrastructure use the same Stage-9 piecewise-linear X/Z alignment through:

    tunnel start
    ring centres
    inter-ring boundaries
    tunnel end

Neighbouring rings therefore share one physical boundary cross-section instead of independently translated centres.

## Production topology cleanup

Before Boolean bake, lining remains closed because Blender Boolean operations need solid geometry.

After the bolt tools are baked, production render finalization removes:

    hidden internal ring end caps
    hidden radial segment-to-segment faces

The topology audit additionally omits hidden coplanar contact surfaces such as:

    rail-foot bottom against pavement
    hidden pavement perimeter against lining

Default production scenes also omit the Stage-4 extrados-only reconstructed joint solids.

Latest five-ring topology audit:

    Stage-8 exact duplicate groups       94
    Stage-9 source exact duplicates      30
    Stage-9 finalized exact duplicates    0

See STAGE9_REPORT.md.

## Rail geometry

Rails are no longer rectangular bars.

Stage 9 uses a generic configurable low-poly rail profile with:

    foot
    narrow web
    head
    shoulder transitions

Default cross-section:

    16 vertices

This is intentionally generic. A specific Moscow/Russian rail section belongs to Stage 10.

## Stable identity

Production IDs are deterministic 63-bit BLAKE2b values derived from semantic persistent keys.

Examples:

    <namespace>/tunnel
    <namespace>/ring/<ring-id>/<object-name>
    <namespace>/infrastructure/rail/0
    <namespace>/infrastructure/rail/1

Physical parent IDs are independent of chunk size.

Chunk-piece IDs are technical export IDs and point back to stable parent IDs through metadata.

## Long tunnels

Latest automated baseline:

### 100 m full geometry

    75 rings
    101.25 m generated
    460 scene objects
    zero exact duplicate faces after finalization

### 1 km full geometry

    741 rings
    1000.35 m generated
    4456 scene objects
    1483 alignment stations
    23728 vertices per rail
    22232 faces per rail

### 5 km alignment stress

    3704 rings
    5000.4 m generated
    7409 alignment stations

No coordinate rebasing is required by the core.

## Optional chunking

Chunking is an export/streaming/tooling feature, not a precision requirement.

Default:

    ring_aligned

A physical lining ring never straddles two default chunks.

Optional exact metric cutting is available as:

    exact_length

For Blender or other tools that benefit from local coordinates:

    --localize-chunks-for-blender

For long scenes where a monolithic JSON is unwanted:

    --chunks-only

Example:

    PYTHONPATH=src python examples/generate_stage9_production_tunnel.py \
        --length-m 1000 \
        --chunk-m 50 \
        --chunks-only \
        --localize-chunks-for-blender \
        --namespace production-1km

This writes chunk JSON files plus a manifest containing global ring IDs, world origins and stable parent asset IDs.

## Generate a short production scene

    PYTHONPATH=src python examples/generate_stage9_production_tunnel.py \
        --rings 20 \
        --namespace stage9-smoke

## Blender 5.2 ID-property note

Stage-9 persistent IDs are engine-neutral positive 63-bit integers. Blender 5.2.x scalar custom-property assignment can overflow when a Python integer exceeds the signed 32-bit C-int range.

The Blender adapter therefore uses a lossless backend-only encoding:

    signed 32-bit values     native Blender integer
    larger integer IDs      decimal string

The ScenePackage/JSON representation is unchanged and keeps the original 63-bit integer. Blender verification reads ID fields through `int(...)`, so the exact identity is preserved.

## Blender verification

    blender --background --python scripts/blender_verify_stage9.py -- \
        examples/stage9_production_scene.json \
        --report examples/blender_stage9_runtime_report.json \
        --save-blend examples/stage9_production_scene.blend

The Stage-9 verifier applies bolt Booleans, removes temporary cutters, strips hidden lining interface surfaces, checks persistent IDs and validates the 16-vertex rail profile.

See STAGE9_BLENDER_SMOKE_TEST.md.

## Tests and CI

Install:

    python -m pip install -e '.[test]'

Run:

    pytest

Current automated baseline:

    150 tests passed

CI also runs:

    scripts/verify_stage8_stress.py
    scripts/verify_stage8_trimesh.py
    scripts/audit_stage9_topology.py
    scripts/verify_stage9_stress.py
    scripts/verify_stage9_trimesh.py

Latest Stage-9 production verification:

    topology finalizer duplicate groups       0
    stable parent IDs across chunk lengths    PASS
    global double coordinates                 PASS
    independent production mesh failures      0

## Stage 10

Stage 10 is intentionally a domain-profile change rather than another Tunnel Scanner reconstruction step.

Planned Moscow Metro work includes:

    tunnel/lining dimensions
    actual rail standard
    track gauge
    sleepers and fasteners
    central trough / drainage geometry
    removal/replacement of the current walkway
    Moscow-specific cable/service arrangement
    other line/type/era-specific infrastructure

Stage 9 should be visually approved in Blender before those geometry rules are introduced.
