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
- selectable Moscow 6.1/5.6 m precast-RC family using the literal Stage-9
  segment/joint/fastener pipeline, with either source-backed `ten_equal` or
  user/photo-reference `kba` topology;
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

The RC envelope is:

    civil family              RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000
    intrados diameter         5.600 m
    extrados diameter         6.100 m
    structural depth          0.250 m
    ring pitch                1.000 m

The civil topology is selected independently:

    --civil-topology auto
        resolves to ten_equal

    --civil-topology ten_equal
        10 equal analytical segments, RC01..RC10
        S026 source-backed topology

    --civil-topology kba
        K, B1, A1, A2, A3, B2
        old Stage-9 K/B/A topology
        user/photo-reference Moscow alternative pending a pinned source

The earlier purpose-built ten-sector sweep has been removed. Both topology
modes now use the original Stage-9 civil architecture directly:

    SegmentAngularExtent
        -> build_hexahedral_segment
        -> RingMesh
        -> build_curved_segment_mesh / build_curved_ring_mesh
        -> prescribed radial joints
        -> prescribed circumferential joints
        -> Stage-6 bolt pockets
        -> 5 mm-overlap Boolean cutters
        -> visible bolt heads

Legacy object types are retained intentionally:

    lining_segment
    prescribed_radial_joint
    prescribed_circumferential_joint
    bolt_pocket_cutter
    bolt_head

This allows the existing Blender Stage-9 interface-strip and Boolean pipeline
to run unchanged. Moscow-specific 1.0 m ring-width/start/centre/end datums are
provided as per-object overrides so the legacy cleanup is not tied to the
original production ring pitch.

For `ten_equal`, S026 additionally supports:

    blocks per ring                10 identical
    block volume                   0.46 m3
    block mass                     1.15 t
    historical concrete            grade 400
    working reinforcement          16 mm
    erection steel pins            22 mm
    permanent bolted block joints  none

That last line is important: the Stage-9 pocket/head hardware is generated in
both topology modes because it is an explicitly requested visual transfer of
the old architecture. It is **not** presented as evidence that the documented
S026 ten-block Moscow family used permanent bolts.

For `kba`, the segment geometry itself is the old Stage-9 implementation:
front/back angular extents, adaptive curved tessellation and the cyclic
`K -> B1 -> A1 -> A2 -> A3 -> B2` topology. The repository currently tags its
Moscow applicability as user/photo-reference constrained until a concrete
historical/project source is added to the research register.

Exact RC end-face chamfers, Ø22 pin-hole/seating geometry and reinforcement
cage CAD remain unresolved.

## Ring construction and axial stagger

Moscow civil rings are a separate periodic system from the historical
Stage-9 1.35 m source-ring scaffold.

Each Moscow ring covers up to 1.000 m of chainage. A final partial ring is
permitted when the generated tunnel length is not an integer number of metres.
Internal ring boundaries have no duplicate longitudinal end caps. Only the
global tunnel start/end may be capped.

For the RC Stage-9 architecture transfer, stable keys include topology, civil
ring index and legacy object name:

    <namespace>/civil-stage9-transfer/<topology>/ring/<ring-index>/<object>

The old Stage-7 axial ring-stagger mechanism is also preserved, but it is
resampled on the independent 1.0 m Moscow civil rhythm rather than indexing the
source 1.35 m assembly poses. The existing `--rotation-strategy` controls it.

With the Stage-10 CLI default `ringwise_gaussian`, every complete civil-ring
assembly receives one seeded local +Y roll before alignment:

    phi_nominal_i ~ truncated Gaussian within +/-6*theta_K
    delta_i ~ N(0, (0.1*|phi_nominal_i|)^2)
    phi_i = phi_nominal_i + delta_i

Segments, prescribed joints, bolt cutters and heads in one civil ring share the
same `phi_i`. Track, walkway, contact rail and service infrastructure are not
rolled. Consequently the narrow K segment in the K/B/A topology changes
circumferential position from ring to ring, matching the old Stage-9 assembly
behaviour.

`continuous` remains available for zero roll; `paper_constant_nominal`
retains the old common-nominal interpretation. This is a transferred Stage-7/9
reconstruction policy, not a Moscow project-specific statistical claim.

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

## Stage-9 civil architecture reuse

For the RC family, Stage 10.4 intentionally preserves the legacy Stage-9 civil
object types so the same Blender Boolean and interface-cleanup path is reused:

    lining_segment
    prescribed_radial_joint
    prescribed_circumferential_joint
    bolt_pocket_cutter
    bolt_head

These objects are rebuilt on the Moscow radii/ring pitch/topology and receive
Moscow-specific identity, chainage, ring-width and rotation metadata. They are
not the unrelated source Stage-9 6.7/6.0 m scene objects.

For the unresolved cast-iron family, the legacy RC/KBA detail pipeline is not
used; only the source-sized smooth envelope is kept.

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
