# Stage 10.2 Report — Moscow permanent way / track concrete / drainage

## Scope

Stage 10.2 extends the Stage-10 Moscow production mode from the Stage-10.1
R65/UGR/gauge contract to the first source-backed permanent-way assembly.

Implemented geometry:

- metro timber sleepers for the selected legacy preset;
- KD-65 support stack for both running rails;
- under-baseplate pads;
- KD-65 baseplates;
- R65 rail-foot pads;
- 24 x 150 mm metro track screws;
- M22 x 75 clamp bolts, nuts and an explicitly simplified spring-clamp
  silhouette;
- continuous track-concrete cross-section;
- 0.900 m central drainage trough;
- 0.530 m drain depth below UGR;
- 3% transverse fall toward the drain;
- 50 x 25 mm longitudinal water-release groove;
- deterministic sleeper periodicity independent of lining-ring pitch.

Stage 10.2 deliberately does **not** implement the contact rail or the Moscow
5.5/5.1 civil shell/walkway. Those remain Stage 10.3 and Stage 10.4.

## Production selection

`ProductionConfig` now accepts:

    moscow_stage="10.1"
    moscow_stage="10.2"

Stage 10.1 remains a compatibility mode. The Stage-10 command-line generator
defaults to Stage 10.2.

In Stage 10.2 the old Stage-8/9 pavement asset is removed and replaced with one
continuous `production_track_concrete` asset. The Stage-8/9 walkway and service
tubes remain transitional until their later Moscow stages.

## Machine profile

The deterministic profile remains:

    research/moscow_metro_tunnels/data/stage10_initial_profile.json

Schema version 1.3 adds explicit Stage-10.2 procedural fallbacks rather than
burying missing dimensions in production code.

Source-backed/derived data includes:

    sleeper top profile z            -0.220 m
    sleeper bottom profile z         -0.385 m
    sleeper length                    2.650 m
    sleeper thickness                 0.165 m
    sleeper upper face width          0.165 m
    sleeper lower face width          0.250 m
    sawn side height                  0.135 m

    sleeper density                   1680 / km
    deterministic pitch               0.5952380952380952 m

    KD-65 plate plan                  0.370 x 0.165 m
    KD-65 hole centres                0.310 x 0.100 m
    KD-65 hole diameter               0.026 m
    KD-65 maximum envelope            0.0556 m

    under-baseplate pad               0.370 x 0.165 x 0.006 m
    R65 rail pad                      0.190 x 0.148 m
    rail-pad base thickness           0.007 m
    rail-pad total thickness          0.014 m

    metro track screw                 0.024 x 0.150 m
    clamp bolt                        M22 x 0.075 m

    concrete top datum at rail        -0.230 m profile z
    transverse fall                   0.03
    drain clear width                 0.900 m
    drain bottom                      -0.530 m profile z
    water groove                      0.050 x 0.025 m

## Permanent-way vertical stack

Stage 10.1 fixes the R65 base at profile z=-0.180 m. The source/interpreted
sleeper top is profile z=-0.220 m, leaving a 40 mm support-stack gap.

The deterministic initial stack is:

    sleeper top                        -0.220 m profile
    under-baseplate pad                 0.006 m
    KD-65 rail-seat contribution        0.020 m
    R65 rail pad total                  0.014 m
                                        -------
    total support stack                 0.040 m
    R65 base                           -0.180 m profile

The 20 mm KD-65 rail-seat contribution is an explicit C-confidence
`derived_stack_fit_fallback`. It reconciles the independent source datums and
pad dimensions; it is not presented as a separately dimensioned Moscow factory
height.

With the Stage-10 coordinate translation:

    core_z = profile_z - 1.670 m

the same stack is:

    sleeper top core z                -1.890 m
    under-pad top                     -1.884 m
    baseplate rail seat top           -1.864 m
    rail-pad / R65 base               -1.850 m
    R65 head / UGR                    -1.670 m

The R65 foot-bottom consists of two collinear analytic profile edges split at
the rail symmetry axis. Because the KD-65 supports are discrete, Stage 10.2
keeps the continuous R65 underside intact and visible between sleepers.

Coplanar contact is removed locally from each rail pad instead: the pad
cross-section is split at the 150 mm R65 foot width and only the hidden central
rail-contact span is omitted. The visible pad overhang remains meshed. The pad
bottom is likewise split so only the true KD-65 rail-seat contact span is
omitted.

## Sleeper geometry and periodicity

The GOST sleeper is modeled as a full embedded timber solid:

- X/transverse length = 2.650 m;
- bottom longitudinal width = 0.250 m;
- top longitudinal width = 0.165 m;
- total thickness = 0.165 m;
- vertical sawn-side portion = 0.135 m.

For the straight deterministic fixture:

    density = 1680 / km
    pitch   = 1000 / 1680
            = 0.5952380952380952 m

The phase is fixed to half a sleeper pitch from tunnel start. This is deliberate:
the sleeper system is not synchronized to the Stage-9 1.35 m ring rhythm.

Every sleeper event has stable semantic parent keys under:

    <namespace>/permanent-way/sleeper-event/<event-index>/<category>

The periodic parent IDs are deterministic and remain invariant when export
chunk size changes. Periodic assets are assigned to chunks by their own
`eventChainageM`, not by lining-ring ID; regression coverage includes
`exact_length` chunks so sleeper events cannot disappear at metric chunk
boundaries.

## KD-65 geometry

The initial KD-65 family consumes the historical drawing dimensions retained in
the machine profile.

Plan orientation is explicit:

- 370 mm dimension: transverse X / along the timber sleeper;
- 165 mm dimension: longitudinal Y / along track;
- hole-centre spacings: 310 mm transverse, 100 mm longitudinal.

The baseplate section uses the source callouts already captured from drawing 96
for the initial simplified section. It is not a generic rectangular plate.

The following remain explicit visual fallbacks rather than historical CAD
claims:

- exact flat track-screw head solid;
- exact local clamp-bolt axis/slot placement;
- exact KDP-2 spring-clamp solid.

Their preview dimensions are stored in the machine profile with C-confidence
metadata. Production code no longer hides those dimensions as magic constants.

## Track concrete and drainage

The continuous concrete section is generated in the engineering profile frame
and then translated into the production core.

Deterministic profile values:

    concrete top at R65 symmetry axes  -0.230000000 m
    drain-edge top                     -0.240383716 m
    drain side x                       +/-0.450000000 m
    drain bottom                       -0.530000000 m
    groove sides                       +/-0.025000000 m
    groove bottom                      -0.555000000 m

The 3% surface falls toward the central drain.

The deterministic v1 groove position is an explicit fallback: the
source-dimensioned 50 x 25 mm groove is centered in the drain bottom because the
inspected source does not supply a separate numeric lateral offset.

Outside the drain/track area, the generated concrete top continues until it
meets the **physical Moscow 5.1 m intrados**, never the Cmk clearance envelope.
For the initial procedural surface rule the positive-X intersection is
approximately:

    x = 1.731575563 m
    z = -0.201936449 m profile

The lower concrete boundary follows the physical 2.550 m intrados circle down
to:

    invert = -0.880 m profile
           = -2.550 m production core

### Transitional civil-shell note

Stage 10.2 already uses the researched Moscow 5.1 m intrados as the physical
bottom boundary of track concrete. The visible lining object is still the old
Stage-9/Tunnel-Scanner shell until Stage 10.4.

Therefore the lower concrete boundary can appear separated from the currently
visible Stage-9 lining. This is an intentional bounded-stage mismatch, not a
track-datum error. Stage 10.4 will replace the civil shell and close that visual
interface.

## Surface/reference fallbacks

The source fixes the 3% transverse fall and the approximately 10 mm sleeper
exposure but does not dimension every hand-finished crossfall breakpoint. The
initial deterministic surface therefore uses the R65 symmetry axes as its
profile z=-0.230 m reference.

This is encoded as:

    rail_axis_datum_fallback

and carries C-confidence in the machine profile. It is replaceable if a more
fully dimensioned track-concrete section is found.

The timber sleeper remains a full embedded object. Its hidden volume may
overlap the concrete fill by design; the exposed/visible datum is controlled by
the concrete surface and the source sleeper-top elevation. The production
topology gate checks exact coincident faces/z-fighting surfaces rather than
forbidding physical embedment volumes.

## Alignment and coordinates

All Stage-10.2 periodic assets use the existing Stage-9 continuous alignment
sampling. Local permanent-way geometry is translated by the sampled station X/Z
offset and longitudinal world Y.

The Stage-10.1 frame contract is unchanged:

    profile +X -> core +X
    route chainage -> core +Y
    profile/core Z translation = -1.670 m

No floating-origin or mandatory chunking rule is introduced.

## Verification

Regression coverage now verifies:

- exact machine-profile sleeper/KD-65/concrete values;
- exact 40 mm rail-support stack closure;
- explicit fastening visual fallbacks;
- 0.900 m drain and -0.530 m profile bottom;
- 3% crossfall;
- 50 x 25 mm water-release groove;
- physical intrados closure;
- sleeper pitch and deterministic phase;
- Stage-10.2 removal of Stage-9 pavement;
- Stage-10.2 periodic asset counts;
- localized rail-pad contact-surface omission while preserving the R65 underside;
- zero exact duplicate faces in permanent-way geometry.

Dedicated stress gate:

    python scripts/verify_stage10_2.py

The 30-ring / 40.5 m verification fixture produces:

    sleeper count                         68
    sleeper pitch                         0.5952380952380952 m
    duplicate permanent-way face groups  0
    stable periodic parent IDs            PASS

The full CI retains every previous Stage-8, Stage-9 and Stage-10.1 gate.

## User-facing workflow

Stage 10.2 is now the default:

    python examples/generate_stage10_production_tunnel.py \
        --rings 20 \
        --namespace stage10-2-smoke

Stage 10.1 remains available explicitly:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.1 \
        --rings 20 \
        --namespace stage10-1-smoke

The Stage-10 Blender verifier reads `domainStage` from scene metadata and
validates either contract.

## Deferred by design

Still not implemented in Stage 10.2:

- contact rail / bracket / insulator / protective assembly — Stage 10.3;
- actual Moscow 5.5/5.1 civil shell and +0.200 m walkway — Stage 10.4;
- series-accurate N/C/K cast-iron ribs, bolts, grout plug and rebates;
- exact historical KDP-2 solid geometry;
- exact local hand-finished concrete fillets/corner radii;
- curve/cant variant of the deterministic straight fixture.

The next bounded implementation stage is Stage 10.3 contact rail.
