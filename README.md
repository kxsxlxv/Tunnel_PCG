# Tunnel_PCG — procedural tunnel geometry

> **Continuation / new-chat handoff:** read [`PROJECT_HANDOFF.md`](PROJECT_HANDOFF.md) first. It contains the full project state, resolved architecture decisions, Stage-9 production contract, Blender caveats, and the exact Stage-10 starting point.

Current milestone: **Stage 10.2 — Moscow timber/KD-65 permanent way, track concrete and drainage**.

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
    Stage 10.1 Moscow profile/data model, explicit UGR/frame mapping,
               production R65 and working-face gauge placement
    Stage 10.2 timber sleepers, KD-65 support chain, track concrete,
               central drain, crossfall and water-release groove

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

This remains the compatibility path for Stage 9. Stage 10.1 adds a separate Moscow mode using the reconstructed GOST R65 profile, local UGR z=0, and 1.520 m gauge measured between the inner working faces 13 mm below UGR.

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

## Generate the current Stage 10.2 Moscow scene

    python examples/generate_stage10_production_tunnel.py \
        --rings 20 \
        --namespace stage10-2-smoke

Stage 10.2 is the default. It keeps the Stage-10.1 R65/gauge/UGR contract and
adds timber sleepers, KD-65 support geometry and the Moscow track-concrete /
drainage section. The old Stage-8/9 pavement is removed.

To reproduce the Stage-10.1 rails-only compatibility scene:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.1 \
        --rings 20 \
        --namespace stage10-1-smoke

See STAGE10_2_REPORT.md.

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

For Stage 10.1 or Stage 10.2 use the stage-aware verifier:

    blender --background --python scripts/blender_verify_stage10.py -- \
        examples/stage10_production_scene.json \
        --report examples/blender_stage10_runtime_report.json \
        --save-blend examples/stage10_production_scene.blend

It validates the R65/UGR/gauge contract for both stages. For Stage 10.2 it additionally validates track-concrete/drainage metadata, sleeper/KD-65 asset counts and dimensions, support-contact policy, persistent IDs, and the existing Blender Boolean/topology finalization path.

See STAGE10_2_BLENDER_SMOKE_TEST.md. Stage-10.1 compatibility instructions remain in STAGE10_1_BLENDER_SMOKE_TEST.md.

## Tests and CI

Install:

    python -m pip install -e '.[test]'

Run:

    pytest

Current automated baseline:

    164 tests passed

CI also runs:

    scripts/verify_stage8_stress.py
    scripts/verify_stage8_trimesh.py
    scripts/audit_stage9_topology.py
    scripts/verify_stage9_stress.py
    scripts/verify_stage9_trimesh.py
    scripts/verify_stage10_1.py
    scripts/verify_stage10_2.py
    examples/generate_stage10_production_tunnel.py  (10.1 + 10.2 CLI smoke)

Latest Stage-9 production verification:

    topology finalizer duplicate groups       0
    stable parent IDs across chunk lengths    PASS
    global double coordinates                 PASS
    independent production mesh failures      0

## Stage 10

Stage 10 is a domain-profile change rather than another Tunnel Scanner
reconstruction step.

Stage 10.1 is closed: source-backed Moscow profile data, explicit UGR/frame
mapping, R65 and working-face gauge placement.

Stage 10.2 is implemented: timber sleepers at 1680/km, KD-65 support chain,
continuous track concrete, 0.900 x 0.530 m central drainage trough, 3% crossfall
and 50 x 25 mm water-release groove. Missing visual fastening details are
explicit machine-profile fallbacks rather than hidden guesses.

The next bounded implementation stage is **Stage 10.3 — contact rail**.
The actual Moscow 5.5/5.1 civil shell and raised walkway remain Stage 10.4.
Exact series-specific cast-iron N/C/K ribs/bolts remain intentionally unresolved
rather than fabricated.
