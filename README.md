# Tunnel_PCG — procedural tunnel geometry

> **Continuation / new-chat handoff:** read [`PROJECT_HANDOFF.md`](PROJECT_HANDOFF.md) first. It contains the full project state, resolved architecture decisions, Stage-9 production contract, Blender caveats, and the exact Stage-10 starting point.

Current milestone: **Stage 10.5 — modern Moscow service preset with preserved legacy alternative**.

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
    Stage 10.3 RK contact rail, legacy sleeper-mounted support chain,
               insulator envelope and explicitly tagged protective-cover fallback
    Stage 10.4 source-sized Moscow civil system: smooth 5.5/5.1 cast-iron
               envelope with detail deferred, plus selectable 6.1/5.6 RC
               ten_equal / KBA topology using the literal Stage-9 segment,
               joint, pocket and bolt-head pipeline
    Stage 10.5 default modern LVT-M/APC-4 permanent way, rounded segmented
               contact-rail cover, dedicated contact supports, R2K11 wall
               cable racks, representative cables, DN80 water main and
               zero-error continuous-sweep optimization; legacy timber/KD-65
               remains selectable

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

## Generate the current Stage 10.5 Moscow scene

    python examples/generate_stage10_production_tunnel.py \
        --rings 20 \
        --namespace stage10-5-modern

Stage 10.5 + `modern` is now the default.

The current preset keeps the researched R65/UGR contract and defaults to the
5.5/5.1 m civil shell; the 6.1/5.6 m RC envelope is selectable independently.
The modern service-era hardware includes:

    LVT-M independent half-sleeper blocks at 0.600 m pitch
    APC-4 fastening preview with 14 mm rail pad
    low rounded segmented contact-rail cover
    dedicated contact-rail support blocks / brackets / local support hoods
    R2K11/K1351.001-09 cable racks on both walls, one per side per 1.0 m civil ring
    K1350.002 literal double-U cradles (UU), first U directly on the upright
    16 representative service cables: 8 occupied levels per wall, one cable per level
    nominal 25 mm cable sag with deterministic per-span amplitude/peak variation
    one current tunnel water main, minimum DN80, weak-current side above UGR
    periodic water-main supports at <=4.0 m spacing

The timber/KD-65 implementation is **not removed**. Generate it explicitly with:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.5 \
        --service-preset legacy \
        --rings 20 \
        --namespace stage10-5-legacy

Stage 10.5 also enables zero-error alignment compaction for continuous sweeps.
It removes only mathematically redundant collinear ring-boundary samples; the
118-vertex R65 section and rail surface are unchanged.

Two civil envelopes are selectable from the Stage-10 generator:

    --civil-archetype cast_iron_5500_5100
        5.5 / 5.1 m cast-iron family; detailed tubing CAD remains deferred

    --civil-archetype rc_block_6100_5600
        6.1 / 5.6 m Moscow RC envelope; 1.0 m civil-ring pitch

For the RC envelope the topology is an independent CLI choice:

    --civil-topology auto        -> ten_equal
    --civil-topology ten_equal   -> ten identical blocks, source-backed by S026
    --civil-topology kba         -> K/B/A Stage-9 topology, explicit user/photo-reference alternative

Both RC topology modes now reuse the **literal old Stage-9 civil pipeline**:
analytical `SegmentMesh` -> adaptive `CurvedSegmentMesh`, prescribed radial
and circumferential joint solids, Stage-6 bolt pockets/Boolean cutters and
visible bolt heads. Legacy object types are intentionally preserved so Blender
runs the same interface cleanup and Boolean code as Stage 9.

For `ten_equal`, S026 supports 10 identical blocks, 0.46 m3/block,
1.15 t/block, historical grade-400 concrete, 16 mm working reinforcement,
22 mm erection pins and **no permanent bolted block connection**. Therefore the
transferred Stage-9 bolt/pocket hardware is a user-requested visual architecture
preset, not a historical fastening claim for that S026 family. The `kba`
topology is likewise explicitly tagged as a user/photo-reference alternative
until a specific Moscow source is registered in research.

The previous simplified ten-sector/8-mm-gap RC implementation has been removed.
Exact RC end-face chamfers, erection-pin holes/seats and reinforcement-cage CAD
remain unresolved.

Because the RC source does not publish a separate UGR-to-lining-axis datum,
Stage 10 transfers the existing track/UGR datum and recomputes shell-contact
geometry from the selected radius.

See STAGE10_5_REPORT.md.

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

For Stage 10.1 through 10.5 use the stage-aware verifier:

    blender --background --python scripts/blender_verify_stage10.py -- \
        examples/stage10_production_scene.json \
        --report examples/blender_stage10_runtime_report.json \
        --save-blend examples/stage10_production_scene.blend

It validates the R65/UGR/gauge contract for all Stage-10 modes. Stage 10.2 adds
track-concrete and KD-65 checks. Stage 10.3 adds the legacy contact-rail
contract. Stage 10.4 validates the 5.5/5.1 shell and raised walkway. Stage 10.5
adds the modern LVT-M/APC-4 path, segmented rounded contact cover, dedicated
contact supports, R2K11 racks/cables, DN80 water main and continuous-sweep
optimization while retaining a selectable legacy preset.

See STAGE10_5_BLENDER_SMOKE_TEST.md.

## Tests and CI

Install:

    python -m pip install -e '.[test]'

Run:

    pytest

Current automated baseline:

    197 tests passed

CI also runs:

    scripts/verify_stage8_stress.py
    scripts/verify_stage8_trimesh.py
    scripts/audit_stage9_topology.py
    scripts/verify_stage9_stress.py
    scripts/verify_stage9_trimesh.py
    scripts/verify_stage10_1.py
    scripts/verify_stage10_2.py
    scripts/verify_stage10_3.py
    scripts/verify_stage10_4.py
    scripts/verify_stage10_5.py
    examples/generate_stage10_production_tunnel.py  (10.1 + 10.2 + 10.3 + 10.4 + 10.5 modern + RC ten_equal + RC KBA + 10.5 legacy CLI smoke)

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

Stage 10.2 is closed and preserved as the legacy permanent-way alternative:
timber sleepers at 1680/km, KD-65 support chain, continuous track concrete,
0.900 x 0.530 m central drainage trough, 3% crossfall and 50 x 25 mm
water-release groove.

Stage 10.3 is closed and preserved as the legacy contact-rail alternative:
bottom-collection RK contact rail at the researched 690 mm / +160 mm placement,
sleeper-snapped support chain and explicitly era-mismatched legacy-cover
fallback.

Stage 10.4 is closed at the current source boundary: source-sized Moscow civil
envelopes, independent 1.0 m civil-ring rhythm and source-backed +0.200 m
raised walkway. The 6.1/5.6 m RC family can be generated either as the
source-backed ten-identical-block topology or as the user/photo-reference K/B/A
alternative; both use the original Stage-9 segment/joint/bolt architecture.
Detailed 5.5/5.1 cast-iron tubing remains intentionally deferred.

Stage 10.5 is the current default production preset. It adds modern LVT-M
half-sleeper blocks, APC-4 fastening preview, a low rounded segmented
contact-rail cover, dedicated contact supports, dimensioned R2K11/K1351.001-09
racks with literal double-U K1350.002 cradles, 16 representative moderate-
density cable routes with deterministic irregular sag, one DN80-minimum tunnel
water main with periodic supports and zero-error continuous-sweep alignment
compaction.

The modern preset is default, but the complete timber/KD-65 implementation is
still selectable with `--service-preset legacy`.

Current integration baseline:

    197 tests passed
    Stage 10.1-10.5 CLI / verifier gates      PASS
    Stage 10.5 modern / RC6100 / legacy gates PASS
    duplicate modern face groups               0
    stable Stage-10.5 IDs across chunk sizes  PASS

Remaining source boundaries are explicit: exact cast-iron N/C/K
angles/rib coordinates/bolt drilling/rebates, exact APC-4 small hardware solids, exact modern contact
support-hood CAD, project-specific cable schedules/rack elevation, exact current
water-main pipe schedule/mounts and final UNIGINE instancing/export policy.

The next step is real Blender 5.2.2 visual/runtime validation of the Stage-10.5
modern preset before adding further unresolved detail.
