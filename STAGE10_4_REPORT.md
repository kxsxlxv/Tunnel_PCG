# Stage 10.4 Report — Moscow civil shells and raised walkway

## Scope

Stage 10.4 replaces the last major Stage-9 geometry that was still visible in
the Moscow production scene:

- the Tunnel-Scanner / Stage-9 lining shell;
- the Stage-8/9 generic walkway.

The Stage-10.1 R65/gauge/UGR contract, Stage-10.2 permanent way/drainage and
Stage-10.3 contact rail remain unchanged.

Implemented Stage-10.4 civil framework:

- source-sized Moscow 5.5/5.1 m cast-iron envelope, with exact tubing detail
  deliberately deferred;
- selectable Moscow 6.1/5.6 m precast-RC family rendered as ten actual curved
  blocks per 1.000 m ring;
- family-specific intrados/extrados radii;
- lining axis profile z=+1.670 m / production-core z=0 transfer rule;
- independent 1.000 m Moscow civil-ring rhythm;
- source-backed raised walkway at profile z=+0.200 m;
- walkway outer edge recomputed against the selected physical intrados;
- track-concrete / walkway partition at x=+1.660 m;
- hidden concrete/walkway contact surfaces against the lining removed.

Exact series-specific N/C/K cast-iron tubing geometry remains intentionally
disabled. Exact RC block-end pin-hole/chamfer CAD also remains unresolved.

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

The machine profile schema is 2.2.

Stage 10 keeps civil geometry source-sized and separates the two supported
families instead of forcing one visual language onto both.

### Classic 5.5 / 5.1 m cast iron

The default family remains:

    civil family              CAST_IRON_5500_R1000
    intrados diameter         5.100 m
    extrados diameter         5.500 m
    structural depth          0.200 m
    ring pitch                1.000 m

Its physical envelope is implemented, but detailed cast-iron tubing geometry is
now intentionally deferred. The previous provisional 11-piece rib/flange/bolt
overlay has been removed because the exact N/C/K angular arrangement, rib
layout, drilling coordinates, rebates and fastening geometry are not yet
resolved well enough to justify a visual reconstruction.

Current cast-iron contract:

    civilRenderMode = source_sized_smooth_cast_iron_envelope_detail_deferred
    coarseSegmentCountIsGeometry = false
    seriesAccurateTubingLOD0 = false

This keeps the researched 5.5/5.1 m dimensions available without presenting an
unverified tubing series as factual geometry.

### Moscow 6.1 / 5.6 m precast RC blocks

The researched RC family is now the detailed/composite civil option:

    civil family              RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000
    intrados diameter         5.600 m
    extrados diameter         6.100 m
    structural depth          0.250 m
    ring pitch                1.000 m
    blocks per ring           10
    block form                10 identical curved blocks
    block volume              0.46 m3
    block mass                1.15 t
    historical concrete       grade 400
    working reinforcement     16 mm
    erection steel pins       22 mm
    permanent block bolts     none

Source S026 fixes those principal dimensions and construction facts.

Unlike the earlier smooth-shell/detail-overlay preview, each generated RC ring
is now actually composed of ten disconnected full-depth curved annular block
meshes. The construction follows the useful visual/topological principle of
Stage 9 -- separate curved lining pieces with explicit radial end faces -- but
uses the Moscow 2.800 / 3.050 m radii, 1.000 m ring pitch and ten equal blocks.

A narrow 8 mm inter-block gap is currently used only as a visual seam so that
the separate blocks remain legible in Blender/LiDAR. That seam width is **not**
claimed as a source dimension. Exact radial-end chamfers, pin holes, pin seats
and reinforcement mesh are still unresolved and are not fabricated.

Current RC contract:

    civilGeometryMode = segmented_rc_6100_5600_10block_stage9_like_v1
    circumferentialSegmentSurfaceMode =
        source_backed_equal_10block_curved_segments_v1
    coarseSegmentCountReference = 10
    coarseSegmentCountIsGeometry = true
    stage9LikeCurvedSegmentConstruction = true
    renderedRCBlockCount = 10 per full ring
    renderedRCVisualSeamWidthM = 0.008  # visual fallback

The annulus volume implied by the researched 6.1/5.6 m radii and 1.0 m pitch is
approximately 4.60 m3 per ring, or 0.46 m3 per one of ten equal blocks, matching
the S026 block-volume datum and providing an independent geometry cross-check.

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

    civilShellStatus =
        implemented_stage10_4_cast_iron_smooth_envelope_detail_deferred
        # default family

    RC alternative:
        implemented_stage10_4_segmented_rc_10block_shell

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

Latest fully green production baseline:

    179 tests passed
    Stage 10.1 CLI compatibility smoke          PASS
    Stage 10.2 CLI permanent-way smoke          PASS
    Stage 10.3 CLI contact-rail smoke           PASS
    Stage 10.4 CLI civil-shell smoke            PASS
    Stage 8/9 stress/topology gates             PASS
    Stage 10.1/10.2/10.3/10.4 verifiers        PASS

30 source rings / 40.5 m Stage-10.4 stress:

    Moscow civil rings                          41
    duplicate production face groups            0
    stable civil parent IDs across chunks       true
    transitional civil gap closed               true

## User-facing workflow

Stage 10.4 is now a compatibility mode; Stage 10.5 modern is the current default:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.4 \
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

Stage 10.5 production integration is now implemented; see STAGE10_5_REPORT.md.
