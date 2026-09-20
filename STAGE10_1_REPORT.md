# Stage 10.1 Report — Moscow profile/data contract and R65 running rails

## Scope

Stage 10.1 introduces the first production-side Moscow Metro domain layer without changing the Stage-9 production architecture. It covers only:

- machine-readable Moscow profile loading and provenance;
- explicit UGR, track-axis and lining-axis datums;
- explicit coordinate-frame conversion into the existing +Y-longitudinal / XZ-cross-section core;
- production R65 cross-section reconstructed from the research GOST tangent-chain kernel;
- running-rail placement by the inner working faces of the heads.

It does not implement sleepers, KD-65, track concrete/drainage, contact rail, Moscow civil shell geometry, or detailed cast-iron tubing. Those remain Stage 10.2–10.4 work.


Consequently, **the only production geometry replaced by Stage 10.1 is the pair
of running rails**. Lining geometry, pavement, walkway, service tubes and the
rest of the Stage-9 scene remain transitional Stage-8/9 geometry until later
bounded stages. Stage 10.1 still changes more than rail shape internally: it
introduces the Moscow data model, profile provenance, datum contract,
coordinate-frame translation, R65 profile solver and working-face gauge
placement.

## Production profile model

New module:

    src/tunnel_scanner_core/moscow.py

The loader consumes the research machine data directly:

    research/moscow_metro_tunnels/data/stage10_initial_profile.json

No independent copy of the civil/track profile constants is used as the profile authority. The resulting MoscowStage10Profile preserves the canonical input JSON, computes a deterministic SHA-256 provenance digest, and exposes typed coordinate/datums/track records.

The initial profile keeps:

- UGR: z = 0.000 m;
- track axis: (x,z) = (0,0) in the profile frame;
- lining axis: (x,z) = (0,+1.670 m);
- intrados invert/crown: -0.880 / +4.220 m;
- extrados invert/crown: -1.080 / +4.420 m.

These are physical profile datums, not values derived from the clearance envelope.

## Coordinate contract

The production core remains unchanged:

- core +Y = longitudinal;
- core XZ = tunnel cross-section.

The Stage-10 XZ profile uses +X toward the walkway and +Z up, and maps profile X -> core X directly for the selected deterministic fixture.

The research route-frame convention is separate:

- route +X = increasing chainage;
- route +Y = left looking in increasing chainage;
- route +Z = up.

For this first fixture, route-left is assigned to the negative profile-X/contact-rail side. Therefore the explicit mapping is:

- route +X chainage -> core +Y;
- route +Y left -> core -X;
- route +Z -> core +Z.

Both forward and inverse mappings have regression tests. No core axis was silently changed.

The profile and production core do **not** share the same vertical origin. The
Stage-10 profile uses UGR as z=0, while the existing production core is anchored
at the lining/tunnel axis. For the selected first Moscow profile the lining axis
is +1.670 m above UGR, so the vertical mapping is:

    core_z = profile_z - 1.670 m

Therefore:

    profile UGR z              0.000 m
    core UGR z                -1.670 m
    profile R65 base z        -0.180 m
    core R65 base z           -1.850 m
    profile gauge plane z     -0.013 m
    core gauge plane z        -1.683 m
    profile lining axis z     +1.670 m
    core lining axis z         0.000 m

This translation is required even before the Moscow civil shell itself is
implemented. Omitting it places the R65 rails at the centre of the old Stage-9
ring. A regression caught and corrected that integration error after the first
Stage-10.1 operator smoke test.

## R65 production profile

The production implementation ports the isolated research engineering kernel rather than continuing to use the Stage-9 generic 16-vertex rail.

Principal dimensions:

- height: 0.18000 m;
- nominal head width: 0.07459 m;
- base width: 0.15000 m;
- web thickness: 0.01800 m.

The right-half profile is reconstructed as the documented tangent chain (R500/R80/R15, 1:20 head side, R5, 1:4 underside, R12, R370/R400, R25, 1:4 foot, R4/R2), mirrored, and sampled with a configurable chord-error tolerance. The default production chord error is 0.05 mm.

Independent QA uses a tighter 0.01 mm sample and reproduces the research fixture:

- reconstructed head width: 0.0745851724 m;
- area: 0.0082776991 m²;
- area relative error vs target: about 0.154%;
- centroid z: 0.0811455555 m;
- centroid z error: about -0.154 mm.

These values satisfy the reference implementation tolerances.

## Gauge placement by working faces

The 1.520 m gauge is not applied to rail symmetry axes.

The machine profile records the gauge measurement plane at 13 mm below UGR/running surface. The R65 working-face offset is solved analytically from the same tangent primitives at that plane:

    working_face_offset = 0.03612386585834637 m

For straight-track gauge 1.520 m, the rail symmetry axes are therefore:

- negative-X rail: -0.7961238658583464 m;
- positive-X rail: +0.7961238658583464 m.

Their inner working faces are exactly:

- -0.760 m;
- +0.760 m.

Thus the generated gauge between working faces is exactly 1.520 m within floating-point regression tolerance.

The rail top tangent is placed at local UGR z=0; the R65 base is at z=-0.180 m.

## Stage-9 compatibility

ProductionConfig now accepts an optional moscow_profile.

- With no Moscow profile, Stage-9 generic rail behaviour is unchanged.
- Supplying both the old custom generic rail_profile and moscow_profile is rejected as ambiguous.
- Persistent rail keys remain <namespace>/infrastructure/rail/0 and /1; stable 63-bit parent IDs and chunk identity remain independent of chunk size.
- Stage-9 sweep/chunking/global-coordinate code is reused unchanged.
- Stage 10.1 does not omit the R65 foot-bottom surface because the Stage-10.2 fastening/support stack is not yet present.

Production metadata explicitly marks Moscow Stage 10.1 and marks permanent way, contact rail and civil shell as deferred rather than presenting the mixed transitional scene as a completed Moscow tunnel.

## User-facing generation and Blender workflow

Stage 10.1 now has the same two-step operator workflow as Stage 9.

Generate:

    python examples/generate_stage10_production_tunnel.py \
        --domain-stage 10.1 \
        --rings 20 \
        --namespace stage10-1-smoke

This writes `examples/stage10_production_scene.json` by default plus a summary
JSON. The generator enables `ProductionConfig.moscow_profile` and performs
pre-serialization assertions for the Stage 10.1 metadata/profile/gauge
contract. The Stage-9 generator remains unchanged and continues to exercise the
generic 16-vertex rail compatibility mode.

Verify in Blender:

    blender --background --python scripts/blender_verify_stage10.py -- \
        examples/stage10_production_scene.json \
        --report examples/blender_stage10_runtime_report.json \
        --save-blend examples/stage10_production_scene.blend

The Stage-10 verifier reuses the existing Blender adapter and production
finalizer but validates R65, UGR and working-face gauge instead of requiring the
Stage-9 16-vertex generic rail. It also checks that deferred permanent-way,
contact-rail and civil-shell metadata remains explicit.

See `STAGE10_1_BLENDER_SMOKE_TEST.md`.

## Verification

Unit/regression coverage checks:

- deterministic machine-data round-trip and provenance SHA;
- exact UGR/track/lining datums;
- forward/inverse coordinate-frame mapping;
- R65 principal dimensions and research QA metrics;
- analytical 13 mm working-face datum;
- exact 1.520 m gauge between working faces;
- UGR rail-top placement;
- Stage-10.1 production integration;
- zero exact duplicate rail faces;
- persistent parent rail IDs invariant across chunk sizes;
- rejection of ambiguous generic+Moscow rail configuration.

scripts/verify_stage10_1.py exercises a 75-ring / 101.25 m Stage-10.1 scene and two different chunk sizes.

GitHub Actions compiles and runs this verifier in addition to the complete Stage-8/Stage-9 quality gate.

## Deferred by design

Not implemented in Stage 10.1:

- timber sleepers;
- KD-65 baseplates/pads/fasteners;
- track concrete, 0.9 x 0.53 m drain, crossfall and water-release groove;
- contact rail and supports;
- 5.5/5.1 Moscow civil shell generation and walkway;
- detailed cast-iron N/C/K tubing/ribs/bolts.

Historical Stage-10.1 boundary: the next bounded implementation stage was Stage 10.2 permanent way/invert geometry. Stage 10.2 is now implemented; see STAGE10_2_REPORT.md.
