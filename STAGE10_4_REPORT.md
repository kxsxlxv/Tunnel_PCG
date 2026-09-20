# Stage 10.4 Report — Moscow 5.5/5.1 civil shell and raised walkway

## Scope

Stage 10.4 replaces the last major Stage-9 geometry that was still visible in
the Moscow production scene:

- the Tunnel-Scanner / Stage-9 lining shell;
- the Stage-8/9 generic walkway.

The Stage-10.1 R65/gauge/UGR contract, Stage-10.2 permanent way/drainage and
Stage-10.3 contact rail remain unchanged.

Implemented Stage-10.4 geometry:

- smooth concentric Moscow 5.5/5.1 m cast-iron-family shell;
- physical intrados radius 2.550 m;
- physical extrados radius 2.750 m;
- structural depth 0.200 m;
- lining axis profile z=+1.670 m / production-core z=0;
- independent 1.000 m Moscow civil-ring rhythm;
- source-backed raised walkway at profile z=+0.200 m;
- walkway inner edge x=+1.660 m;
- walkway outer edge closed exactly on the physical intrados;
- track-concrete / walkway partition at x=+1.660 m;
- hidden concrete/walkway contact surfaces against the lining removed.

Exact series-specific N/C/K tubing geometry remains intentionally disabled.

## The former ~0.4 m gap

Through Stage 10.2 and Stage 10.3, a visible gap of several decimetres between
`PROD_TRACK_CONCRETE` and the old visible tubing was intentional.

The reason was a bounded-stage mismatch:

- track concrete already closed to the researched Moscow 5.1 m intrados;
- the visible lining was still the larger/different Stage-9 Tunnel-Scanner
  reconstruction.

Moving the track concrete outward to hide that gap would have corrupted the
Moscow engineering datums.

Stage 10.4 removes that transitional mismatch. The visible shell now uses the
same physical 2.550 m intrados that already defines the track-concrete lower
boundary.

Scene metadata therefore changes to:

    transitionalCivilGapStatus = closed_by_stage10_4_moscow_shell

From Stage 10.4 onward, a comparable gap is a regression rather than expected
transitional geometry.

## Civil geometry policy

The machine profile schema is 1.6.

The initial civil geometry mode is:

    smooth_concentric_ringwise_shell_v1

The shell uses:

    intrados diameter        5.100 m
    extrados diameter        5.500 m
    structural depth         0.200 m
    ring pitch               1.000 m

The 11-piece DZMO-family rhythm remains metadata/reference only:

    coarseSegmentCountReference = 11
    coarseSegmentCountIsGeometry = false
    seriesAccurateTubingLOD0 = false

Stage 10.4 does not fabricate:

- N/C/K central angles;
- key-wedge geometry;
- rib positions;
- bolt-hole positions;
- grout-plug location;
- flange/rebate/falts profile.

Those fields remain blocked by the public-source boundary.

## Ring construction

Moscow civil rings are a separate periodic system from the historical
Stage-9 1.35 m source-ring scaffold.

Each Moscow ring covers up to 1.000 m of chainage. A final partial ring is
permitted when the generated tunnel length is not an integer number of metres.

Internal ring boundaries have no duplicate longitudinal end caps. Only the
global tunnel start/end may be capped.

Each ring gets a stable key:

    <namespace>/civil-shell/ring/<ring-index>

and its own midpoint `eventChainageM`, so export chunking is independent from
Stage-9 ring IDs.

## Walkway geometry

The selected legacy walkway is on +profile-X, opposite the contact rail.

Source/profile datums:

    top z                       +0.200 m
    inner edge x                +1.660 m
    documented outer edge x     +2.083650643 m
    documented top width         0.423650643 m

The actual mesh outer point is evaluated from the physical circle:

    x = sqrt(2.55^2 - (0.200 - 1.670)^2)
      = 2.083650642502... m

The machine-profile value is the source-readable rounded datum; geometry uses
the exact circle intersection so there is no microscopic shell/walkway gap.

## Track-concrete / walkway partition

At x=+1.660 m the Stage-10.2 crossfall gives:

    track-concrete top profile z = -0.21995 m

The Stage-10.4 track-concrete shoulder terminates at this X rather than
continuing to its former positive-side intrados intersection.

The walkway then provides:

- hidden lower contact from the physical intrados up to the concrete top;
- an exposed vertical riser from concrete top to walkway top +0.200 m;
- horizontal walkway top to the physical intrados;
- hidden lower surface following the physical intrados.

Hidden longitudinal contact faces are omitted on both the concrete/walkway
interface and the lining interface.

This avoids coplanar z-fighting while preserving a closed physical section.

## Stage-9 civil removal

In Stage 10.4 the production scene does not retain:

    lining_segment
    bolt_head
    bolt_pocket_cutter
    prescribed_radial_joint
    prescribed_circumferential_joint
    production_walkway

Stage-9 bolt Boolean geometry is not generated at all in Stage 10.4.

The old service tubes remain transitional infrastructure and are not claimed to
be the final Moscow cable/service arrangement.

## Production metadata

Stage 10.4 reports:

    civilShellStatus = implemented_stage10_4_smooth_concentric_shell
    walkwayStatus = implemented_stage10_4_source_backed_geometry
    stage9CivilGeometryRemoved = true
    moscowCivilRingPitchM = 1.0
    moscowCivilIntradosRadiusM = 2.55
    moscowCivilExtradosRadiusM = 2.75
    transitionalCivilGapStatus = closed_by_stage10_4_moscow_shell

Permanent-way and contact-rail statuses stay implemented from their earlier
stages.

## Verification

Regression coverage:

    tests/test_moscow_stage10_4.py

Dedicated stress gate:

    python scripts/verify_stage10_4.py

It verifies:

- exact 2.55 / 2.75 m shell radii;
- exact 0.20 m structural depth;
- 1.0 m civil-ring rhythm and partial final ring behavior;
- no old Stage-9 lining/bolt geometry in Stage 10.4;
- source-backed walkway position;
- exact walkway/intrados closure;
- track-concrete shoulder partition;
- retained Stage-10.1/10.2/10.3 geometry;
- zero exact duplicate production faces;
- stable Moscow civil-ring parent IDs across different exact-length chunk sizes.

## User-facing workflow

Stage 10.4 is now the default Stage-10 mode:

    python examples/generate_stage10_production_tunnel.py \
        --rings 20 \
        --namespace stage10-4-smoke

Then:

    blender --background --python scripts/blender_verify_stage10.py -- \
        examples/stage10_production_scene.json \
        --report examples/blender_stage10_runtime_report.json \
        --save-blend examples/stage10_production_scene.blend

Stage 10.3 remains available explicitly with `--domain-stage 10.3`.

## Deferred by design

Still unresolved after Stage 10.4:

- series-accurate cast-iron N/C/K segment surfaces and ribs;
- exact cast-iron bolt/plug/rebate geometry;
- final Moscow-specific cable/service rack geometry replacing Stage-8 services;
- full route curve/cant variants and special contact-rail events;
- future UNIGINE/export integration work.

The next bounded project step is Stage 10.5 production integration / final
Moscow archetype validation.
