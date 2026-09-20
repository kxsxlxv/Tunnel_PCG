# Stage 10.5 Report — modern Moscow service preset

## Scope

Stage 10.5 turns the Stage-10.4 civil shell into the first current-generation
Moscow production preset.

The default Stage-10.5 service preset is:

    MODERN_MOSCOW_LVT_SERVICES_2020S

The legacy timber/KD-65 implementation is preserved and remains selectable as:

    LEGACY_R65_TIMBER_KD65_2001_REFERENCE

Nothing in Stage 10.5 deletes the legacy geometry path.

## Current default geometry

The modern preset retains:

- Moscow 5.5 / 5.1 m civil shell;
- R65 running rails and 1.520 m working-face gauge;
- Stage-10.2 track concrete and central drainage geometry;
- raised Moscow walkway.

It replaces the legacy service-era hardware with:

- LVT-M independent half-sleeper blocks;
- rubber boots / elastic isolation;
- APC-4 rail fastening preview;
- modern segmented contact-rail protective cover;
- dedicated contact-rail support blocks and brackets;
- local support hoods through cover interruption zones;
- R2K11 wall cable racks on both tunnel sides;
- representative wall-supported service cables;
- one current tunnel water main, minimum DN80, on the weak-current side.

## Modern permanent way

Preset:

    MOSCOW_LVT_M_R65_APC4_2020S

Source-backed dimensions used by the initial production mesh:

    support pitch                  0.600 m
    block transverse length        0.640 m
    block top width                0.180 m
    block height                   0.165 m
    block base width wide          0.197 m
    block base width narrow        0.178 m
    rail-seat cant                 1:20
    rubber-boot inner length       0.650 m
    rubber-boot side height        0.153 m
    APC-4 rail pad thickness       0.014 m

Each rail gets its own independent support block. The geometry does not bridge
the 0.900 m central drainage trough.

The exact solids of all APC-4 small hardware remain unresolved in public
sources; the current clamps/monoregulators are topology-preserving previews
with explicit fallback metadata.

## Legacy permanent way remains available

Stage 10.5 can still generate:

- timber sleepers;
- KD-65 baseplates;
- under-baseplate pads;
- R65 rail pads;
- 24x150 mm metro track screws;
- clamp hardware;
- legacy sleeper-mounted contact-rail supports.

Use:

    --domain-stage 10.5 --service-preset legacy

This path is regression-tested and remains part of the production API.

## Modern contact rail

The running contact-rail datum is unchanged:

    axis profile x                 -1.450 m
    working surface profile z     +0.160 m
    reference offset               0.690 m
    RK overall height              0.118 m

The Stage-10.3 continuous rectangular/tall legacy fallback cover is not used in
the modern preset.

Modern protective-cover envelope:

    top width                      0.092 m
    base width                     0.114 m
    height                         0.111 m
    side wall                      0.002 m
    top wall                       0.003 m

The generated profile is a smooth rounded wrap within that source-backed
envelope. Exact manufacturer corner radii remain unresolved and are not
invented.

The main cover is segmented and interrupted around support zones. Each support
zone receives a separate local hood.

## Modern contact support

Modern contact supports are not attached to or coincident with running-rail
support blocks.

The support schedule uses independent nominal 5.0 m targets within the
4.5-5.4 m normative family and snaps each target to a midpoint between running
supports.

The modern assembly contains:

- dedicated reinforced-concrete support block;
- curved-channel bracket;
- vertical insulator envelope;
- fastening unit;
- polymer attachment dowels;
- local protective hood.

The current support-block height is 0.040 m and the polymer-dowel length is
0.140 m.

The exact current support-hood product shape and some bracket bend radii remain
explicit visualization fallbacks.

## R2K11 cable racks

Modern Stage 10.5 removes the six Stage-8 tube previews.

The implemented wall rack family is R2K11:

    horn count                     11
    overall arc length             1.440 m
    upright longitudinal width     0.048 m
    upright thickness              0.003 m
    horn thickness                 0.004 m
    horn radius                    0.0325 m
    derived horn pitch             0.125 m
    max cable diameter             0.065 m

One rack is generated on each side of every 1.0 m Moscow civil ring.

The v1 service preview places one representative cable on each of 11 rack
levels per side, giving 22 continuous cable routes. The rack itself supports two
cable places per level; exact project cable schedules remain unresolved.

All modern cables/racks are checked to remain inside the 2.550 m physical
intrados.

## Current water main

The current service preset generates one tunnel water main:

    minimum nominal diameter       DN80
    quantity                       1 per single-track tunnel
    side                           weak-current side
    vertical rule                  above UGR

The exact project pipe schedule and wall thickness are unresolved for the
selected archetype.

The preview uses:

    outer-diameter visual proxy    0.089 m
    profile center z               +0.700 m
    shell clearance inward         0.040 m

Those exact placement/OD values are explicitly tagged as fallbacks; the
normative DN80/quantity/side/above-UGR rules are source-backed.

## Polygon-count optimization

Stage 10.5 introduces a zero-error continuous-sweep optimization.

The Stage-9 alignment contains explicit midpoint samples at ring boundaries.
For a continuous sweep those boundary samples lie mathematically on the same
piecewise-linear segment between neighbouring ring centers.

Stage 10.5 removes only those exactly collinear samples before sweeping:

    continuousSweepAlignmentCompaction = exact_zero_error_collinear

No geometry is approximated and no tolerance-based curve simplification is
performed.

For the four-ring CI smoke:

    source rail alignment stations        9
    compacted rail sweep stations         4

The R65 cross-section remains the full 118-vertex reconstructed profile.

For long tunnels this removes roughly half of the longitudinal rail sweep
sections that previously caused nearly one million polygons per rail in a
2.7 km scene, without changing the rail surface.

The optimization can be disabled through ProductionConfig for regression and
comparison work.

## Source-backed versus fallback boundaries

Source-backed/current:

- LVT-M main block dimensions;
- 600 mm support pitch;
- rubber-boot internal dimensions;
- APC-4 family and 14 mm rail pad;
- contact-cover principal envelope;
- contact support separation from running supports;
- R2K11 principal rack dimensions;
- one DN80 minimum tunnel water main on the weak-current side above UGR.

Still explicit fallbacks:

- which 197/178 mm LVT block base end points inboard;
- outer rubber-boot wall thickness;
- exact APC-4 small-part solids;
- modern cover corner radii;
- exact support-hood product shape;
- some support-bracket bend radii;
- exact project cable occupancy/schedule;
- exact current pipe OD/wall thickness and project mounting coordinates.

## Verification

Regression:

    tests/test_moscow_stage10_5.py

Stress/integration gate:

    python scripts/verify_stage10_5.py

Latest fully green baseline:

    192 tests passed
    Stage 10.1 CLI compatibility smoke       PASS
    Stage 10.2 CLI compatibility smoke       PASS
    Stage 10.3 CLI compatibility smoke       PASS
    Stage 10.4 CLI compatibility smoke       PASS
    Stage 10.5 modern CLI smoke              PASS
    Stage 10.5 legacy CLI smoke              PASS
    Stage 8/9 stress/topology gates          PASS
    Stage 10.1-10.5 verifiers                PASS

40.5 m Stage-10.5 integration stress:

    modern LVT support events                67
    contact supports                          8
    contact cover spans                       9
    service cables                           22
    R2K11 rack objects                       82
    water mains                               1
    duplicate modern face groups              0
    stable parent IDs across chunk sizes      true
    legacy timber variant selectable          true

## User-facing workflow

Current default:

    python examples/generate_stage10_production_tunnel.py \
        --rings 20 \
        --namespace stage10-5-modern

Equivalent explicit form:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.5 \
        --service-preset modern \
        --rings 20 \
        --namespace stage10-5-modern

Legacy timber/KD-65 alternative:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.5 \
        --service-preset legacy \
        --rings 20 \
        --namespace stage10-5-legacy

Blender verification:

    blender --background --python scripts/blender_verify_stage10.py -- \
        examples/stage10_production_scene.json \
        --report examples/blender_stage10_runtime_report.json \
        --save-blend examples/stage10_production_scene.blend

## Remaining open questions

The selected archetype is now suitable for another visual/runtime review, but
these questions remain intentionally open:

- exact series-specific cast-iron N/C/K ribs, bolts, rebates and grout plugs;
- project-specific modern cable route occupancy and cable diameters;
- exact R2K11 elevation/offset for a named tunnel project;
- exact current contact-support hood CAD;
- exact modern contact-cover corner radii;
- exact LVT boot outer wall and all APC-4 small-part solids;
- exact current water-main pipe schedule and mounting brackets;
- route-specific curve/cant/special-track variants;
- final UNIGINE exporter/instancing strategy.

The next validation step should be a real Blender 5.2.2 scene review of the
modern Stage-10.5 preset before adding more unresolved visual detail.
