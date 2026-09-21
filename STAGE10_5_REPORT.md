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

## Selectable civil envelope

Stage 10.5 exposes two researched Moscow civil families through
`--civil-archetype`:

    cast_iron_5500_5100
        D_in 5.100 m / D_out 5.500 m / ring pitch 1.000 m

    rc_block_6100_5600
        D_in 5.600 m / D_out 6.100 m / ring pitch 1.000 m
        10 identical precast RC blocks

The classic cast-iron family remains the compatibility default, but its detailed
N/C/K tubing geometry is **not** fabricated. Only the source-sized 5.5/5.1 m
envelope is rendered until the actual cast-iron segment/rib/fastening geometry
is researched to a defensible level.

The 6.1/5.6 m RC family is now the detailed composite option and is the intended
civil archetype for current visual review. Source S026 provides:

    ring pitch                     1.000 m
    block count                    10 identical blocks
    block volume                   0.46 m3
    block mass                     1.15 t
    historical concrete grade      400
    working reinforcement          16 mm
    erection pins                  22 mm
    permanent bolted block joints  no

Each RC ring is generated as **ten disconnected curved full-depth blocks**, not
as a smooth cylinder plus decorative seam overlay. The construction is
deliberately Stage-9-like at the topology level: separate curved annular
segments with explicit radial end faces, but adapted to the Moscow
2.800/3.050 m radii, 1.000 m ring pitch and ten equal blocks.

The current 8 mm inter-block seam is a visual fallback, not a source dimension.
Exact radial-end chamfers, pin holes/seats and reinforcement-mesh CAD remain
unresolved. The calculated annular volume is approximately 4.60 m3/ring, or
0.46 m3 for one of ten equal blocks, matching the documented block volume.

S026 does not publish a separate UGR-to-lining-axis placement for this family.
The existing Stage-10 track/UGR datum therefore remains an explicit transfer
rule; shell-contact geometry, walkway width and wall-following services are
recomputed from the selected 2.800 m intrados.

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

A user-supplied dimensioned support drawing reviewed on 2026-09-21 adds the
following readable callouts:

    running reference -> contact-axis region      0.683 m
    running reference -> outer bracket envelope   0.873 m
    upper return / top-plate callout               0.180 m
    top above UGR/reference line                   0.373 m
    lower hook/bend callout                        0.155 m
    upper hook/bend callout                        0.090 m

The established 690 +/- 8 mm horizontal and +160 mm vertical contact-rail
datums remain authoritative. The drawing's 683 and 155 mm callouts independently
fall inside those tolerances and are used as a geometry cross-check rather than
to move the contact rail.

The v3 support bracket is now a dimension-constrained J/C-shaped hook channel.
Its outboard envelope is fixed at:

    |x| = gauge/2 + 0.873 = 1.633 m

and its top is fixed at:

    profile z = +0.373 m

The 155 and 90 mm callouts drive the lower and upper hook-bend construction in
the initial mesh. Exact neutral-axis bend radii remain an image-derived
interpretation, not a factory-CAD claim.

The modern assembly now contains:

- dedicated reinforced-concrete support block;
- separate four-anchor steel base plate;
- dimensioned hook-channel bracket;
- explicit upper-flange clamp/saddle around the contact rail;
- short vertical insulator stack under the upper hook arm;
- two visible clamp through-bolts;
- four support-block dowels/anchors;
- local protective hood over the clamp/support zone.

The contact rail no longer visually floats inside the support: side jaws flank
the 80 mm upper flange, a bridge plate bears above the rail, and the insulator
stack closes the load path up to the bracket arm.

The current support-block height is 0.040 m and the polymer-dowel length is
0.140 m.

The support hood was raised to enclose the dimensioned +0.373 m bracket/clamp
top and bolt heads while retaining the same rounded-wrap language as the main
cover.

Still unresolved and explicitly tagged as fallback:

- exact production bend radii/neutral axis of the hook channel;
- exact base-plate slot/hole geometry;
- exact clamp casting;
- exact current insulator profile;
- exact local hood product CAD.

## R2K11 cable racks

Modern Stage 10.5 removes the six Stage-8 generic tube previews.

The wall-rack assembly is now tied to current component designations:

    assembly                       R2K11
    curved upright                 K1351.001-09
    double horn                    K1350.002
    horn count                     11
    upright arc length             1.440 m
    upright longitudinal width     0.048 m
    upright steel thickness        0.003 m
    horn overall length            0.169 m
    horn longitudinal width        0.040 m
    horn overall height            0.087 m
    horn steel thickness           0.004 m
    cable places per horn          2
    horn pitch                     0.125 m
    max cable diameter             0.065 m

K1350.002 keeps the current 169 x 40 x 87 mm component envelope, but the
visual horn topology is now the literal `UU` requested from Blender review:
two adjacent U-shaped cradles, with no central omega/W crest and no horizontal
shelf/neck before the first cradle. The first U begins directly at the upright.

The visible double-cradle span is 154 mm. Each U has 67 mm internal clear
diameter, giving 1 mm radial clearance over the 65 mm maximum cable diameter.
With 4 mm strip thickness the two U shapes are separated by a 4 mm visual gap.
Cable-route centres use the same geometry at 37.5 mm and 116.5 mm inward from
the upright. Each lower semicircle uses eight arc subdivisions, so the result is
round enough in Blender without a dense spline mesh. Exact factory bend radii
remain unresolved.

One R2K11 rack is generated on each wall at the midpoint of every 1.0 m Moscow
civil ring.

The visual cable preset occupies eight distributed levels per wall and one
cable place on each occupied level:

    8 levels x 1 cable x 2 sides = 16 representative cable routes

The routes use a restrained nominal 0.025 m sag between the 1.0 m rack
supports. The sag is no longer repeated identically: each cable/span gets a
stable hashed amplitude variation of +/-35% and its lowest point moves by up to
+/-0.12 of a span. Only one interior control station is added per span, so the
irregularity does not create a dense spline mesh.

The negative-X/contact-rail wall is tagged as the strong-current side and its
rack midpoint is raised to the lining-axis height to match the supplied visual
reference. The positive-X/walkway wall remains the weak-current side.

This remains a visual-density preset, not a claim about the exact cable schedule
of one named tunnel. Project-specific cable types, diameters and occupancy
remain unresolved.

All modern racks and representative cables are checked to remain inside the
selected physical intrados.

## Current water main

The current service preset generates one tunnel water main:

    minimum nominal diameter       DN80
    quantity                       1 per single-track tunnel
    side                           weak-current side
    vertical rule                  above UGR
    maximum support interval       4.000 m

The exact project pipe schedule, wall thickness and factory support hardware are
not universal and remain unresolved for the selected archetype.

The preview uses:

    outer-diameter visual proxy    0.089 m
    profile center z               +0.600 m
    shell clearance inward         0.040 m

The center was moved from the former +0.700 m fallback to +0.600 m, the lower
bound of the already recorded 0.6-0.8 m historical placement range. This keeps
the water main below the lowest R2K11 cable/horn layer while retaining the
current normative rule that the pipe remains above UGR on the weak-current
side.

The water main now also has periodic wall supports. Their spacing never exceeds
4.0 m. The initial support is a simple wall standoff plus lower pipe saddle;
support interval is source-backed, while the exact project bracket/strap CAD is
explicitly marked unresolved.

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
- R2K11/K1351.001-09 upright dimensions and K1350.002 horn envelope;
- two cable places per R2K11 horn and current strong/weak-current side ordering;
- one DN80 minimum tunnel water main on the weak-current side above UGR;
- tunnel water-main support spacing no greater than 4 m.

Still explicit fallbacks:

- which 197/178 mm LVT block base end points inboard;
- outer rubber-boot wall thickness;
- exact APC-4 small-part solids;
- modern cover corner radii;
- exact support-hood product shape;
- some support-bracket bend radii;
- exact project cable occupancy/schedule (the current 16-cable layout is a visual-density preset);
- exact current pipe OD/wall thickness and project support/bracket CAD.

## Verification

Regression:

    tests/test_moscow_stage10_5.py

Stress/integration gate:

    python scripts/verify_stage10_5.py

Profile schema is now **2.2** because the dimensioned support drawing is part of the typed machine contract.

Current fully green v6 code baseline:

    195 tests passed
    Stage 10.1 CLI compatibility smoke       PASS
    Stage 10.2 CLI compatibility smoke       PASS
    Stage 10.3 CLI compatibility smoke       PASS
    Stage 10.4 CLI compatibility smoke       PASS
    Stage 10.5 modern CLI smoke              PASS
    Stage 10.5 6.1/5.6 RC CLI smoke          PASS
    Stage 10.5 legacy CLI smoke              PASS
    Stage 8/9 stress/topology gates          PASS
    Stage 10.1-10.5 verifiers                PASS

40.5 m Stage-10.5 integration stress:

    modern LVT support events                67
    contact supports                          8
    contact cover spans                       9
    service cables                           16
    R2K11 rack objects                       82
    water mains                               1
    periodic water-main supports              source-length dependent, <=4 m pitch
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

Larger 6.1/5.6 m RC-envelope alternative:

    python examples/generate_stage10_production_tunnel.py \
        --rings 20 \
        --namespace stage10-5-rc6100 \
        --civil-archetype rc_block_6100_5600

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

- exact series-specific cast-iron N/C/K angles, rib coordinates, bolt drilling, rebates and grout plugs;
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
