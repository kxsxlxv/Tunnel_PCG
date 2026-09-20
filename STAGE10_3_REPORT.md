# Stage 10.3 Report — Moscow contact rail

## Scope

Stage 10.3 extends the Stage-10.2 Moscow permanent-way scene with the selected
legacy bottom-collection contact-rail family.

Implemented:

- one continuous RK contact rail on the negative-profile-X side;
- source-backed nominal placement from the nearest running-rail inner working
  face;
- source-backed contact working-surface elevation;
- deterministic contact-rail support chain;
- curved-channel legacy bracket topology;
- sleeper attachment by three 24 x 150 mm track screws;
- initial porcelain-insulator envelope;
- simplified contact-rail retaining/fastening unit;
- continuous protective-cover preview with strict historical-vs-modern fallback
  metadata.

Stage 10.3 deliberately does not replace the civil shell or Stage-8/9 walkway.
Those remain Stage 10.4.

## Placement contract

The running-track gauge is already defined by Stage 10.1 as 1.520 m between the
inner working faces.

For the initial contact-rail side:

    side profile X sign                      -1
    nearest running-rail inner working face -0.760 m
    horizontal offset                        0.690 m
    contact-rail axis                       -1.450 m profile X
    working surface                         +0.160 m profile Z
    working surface                         -1.510 m core Z

The 690 mm dimension is therefore not measured from the R65 symmetry axis.

The current nominal tolerances retained as metadata are:

    horizontal +/-0.008 m
    vertical   +/-0.006 m

## RK profile

The machine profile uses the dimensional RK contact-rail section retained from
the manufacturer catalog:

    overall height  0.118 m
    top width       0.080 m
    base width      0.090 m
    web width       0.020 m
    vertical bands  0.023 / 0.040 / 0.046 m

The remaining 9 mm between the published vertical callouts and the total height
is used as the deterministic transition allowance.

Exact undimensioned transition radii are not claimed. The production geometry
mode is:

    dmz_principal_dimensions_linearized_v1

and retains the explicit warning that the 2021 manufacturer section is a
dimensional fallback for the legacy Moscow preset rather than proof that every
historical rail used an identical rolling section.

The contact working surface is the lower face because the selected system is
bottom collection.

## Protective cover

Historical installation rules control clearances and the vertical envelope.

Retained historical constraints include:

    side-board to RK head gap                 0.020 m
    lower board edge above working surface    0.023 m
    overall rail/protective vertical envelope 0.223 m
    gap between protective boxes              0.020 m
    box-to-insulator gap                      0.025 m
    support offset from box end               0.300 m

The initial preview cover therefore preserves:

    lower edge z above contact surface  0.023 m
    effective cover height              0.200 m
    top of assembly above contact face  0.223 m

The modern product contributes only a replaceable silhouette/wall-thickness
fallback. Its width is adjusted to preserve the historical 20 mm lateral
clearance around the 90 mm RK maximum width:

    outer top width   0.112 m
    outer base width  0.134 m
    side wall         0.002 m
    top wall          0.003 m

Metadata is intentionally strict:

    eraMismatch = true
    modernFallbackIsNotHistoricalClaim = true

The preview is continuous longitudinally because the exact historical board
piece length for this preset is unresolved. Historical box gaps/end-support
offsets remain in metadata for a later piecewise cover implementation.

## Support chain

The source range for ordinary running-tunnel contact-rail bracket spacing is:

    4.5 ... 5.4 m

A raw 5.0 m support chain cannot be used directly for the selected legacy
suspension because the bracket is physically screwed to a timber sleeper.

Stage 10.3 therefore defines an independent target chain:

    target pitch  5.0 m
    target phase  2.5 m

and snaps every target to the nearest Stage-10.2 timber sleeper.

For the deterministic 1680 sleepers/km track this creates intervals of 8 or 9
sleeper pitches:

    8 x 0.595238095238... = 4.761904761905 m
    9 x 0.595238095238... = 5.357142857143 m

Both lie inside the retained 4.5-5.4 m source range.

The chain remains logically independent of both sleeper numbering and lining
ring seams: support persistent IDs are based on contact-support event index, and
exact-length chunk assignment uses each event's own chainage.

## Bracket and insulator

The selected historical topology is represented as:

    timber sleeper
      -> three track screws
      -> curved-channel bracket
      -> porcelain-insulator envelope
      -> simplified retaining/fastening unit
      -> RK contact rail

The bracket uses the retained 540 x 620 x 100 mm resource envelope only as an
envelope reference. Exact channel bend radii, hole coordinates and clip geometry
are unresolved and are not presented as historical CAD.

The initial insulator is a horizontal cylindrical envelope:

    axial length  0.150 m
    diameter      0.112 m

This is intentionally tagged as envelope-only geometry; the exact porcelain
solid remains unresolved.

The three sleeper-attachment screws use the already typed metro fastening
values:

    shaft diameter  0.024 m
    shaft length    0.150 m
    preview head radius 0.018 m
    preview head height 0.008 m

The head is modeled separately from the 150 mm shaft.

## Transitional civil-shell gap

Stage 10.3 inherits the Stage-10.2 track-concrete geometry unchanged.

The concrete already closes against the researched physical Moscow 5.1 m
intrados. The visible lining/tubing objects are still the Stage-9
Tunnel-Scanner shell.

Therefore a large visible gap — approximately several decimetres and around
0.4 m in the current Blender preview — can exist between
`PROD_TRACK_CONCRETE` and the visible tubings.

This is expected and must not be "fixed" by moving the permanent-way datums or
extending concrete to the Stage-9 shell. Stage 10.4 replaces the civil shell
with the Moscow 5.5/5.1 geometry and closes the visual interface.

The same Stage-8/9 walkway remains transitional until Stage 10.4.

## Production objects

Stage 10.3 retains every Stage-10.2 object and adds:

    PROD_CONTACT_RAIL
    PROD_CONTACT_RAIL_COVER

plus one periodic set per support event:

    production_contact_rail_bracket
    production_contact_rail_insulator
    production_contact_rail_attachment_screws
    production_contact_rail_fastening_unit

Stable keys:

    <namespace>/infrastructure/contact-rail/0
    <namespace>/infrastructure/contact-rail-cover/0
    <namespace>/contact-rail/support-event/<index>/<category>

## Verification

Regression coverage:

    tests/test_moscow_stage10_3.py

Dedicated stress gate:

    python scripts/verify_stage10_3.py

The gate checks:

- exact -1.450 m contact-axis placement;
- +0.160 m working-surface profile datum;
- RK principal dimensions;
- protective-cover historical side and vertical clearances;
- explicit era mismatch;
- support snapping to real timber sleepers;
- support intervals inside 4.5-5.4 m;
- zero exact duplicate contact-rail faces;
- stable support parent IDs across different exact-length chunk sizes.

The Stage-10 Blender verifier is stage-aware through 10.3.

## User-facing workflow

Stage 10.3 is now an explicit compatibility mode because Stage 10.4 is the current default:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.3 \
        --rings 20 \
        --namespace stage10-3-smoke

Then:

    blender --background --python scripts/blender_verify_stage10.py -- \
        examples/stage10_production_scene.json \
        --report examples/blender_stage10_runtime_report.json \
        --save-blend examples/stage10_production_scene.blend

Stage 10.2 compatibility now requires an explicit selector:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.2 \
        --rings 20 \
        --namespace stage10-2-smoke

Stage 10.1 remains available with `--domain-stage 10.1`.

## Deferred by design

Historical Stage-10.3 deferrals:

- actual Moscow 5.5/5.1 civil shell and raised +0.200 m walkway — implemented in Stage 10.4;
- exact historical protective-board extrusion and board segmentation;
- exact porcelain insulator CAD;
- exact legacy bracket bend radii/hole/clip coordinates;
- contact-rail piece joints, end ramps and air-gap events;
- curve-specific side switching / R<200 m outside-curve rule in the straight
  deterministic fixture;
- series-accurate N/C/K cast-iron tubing ribs/bolts/rebates.

Stage 10.4 civil shell / walkway is now implemented; see STAGE10_4_REPORT.md.
