# PROJECT HANDOFF — Tunnel_PCG

**Snapshot:** 2026-09-20  
**Repository:** `kxsxlxv/Tunnel_PCG`  
**Branch:** `master`  
**Pre-handoff research HEAD:** `5795b81b1a2af62ae5c4b7322b15ac36e68217be`  
**CI at that HEAD:** GitHub Actions PASS  
**Production package version:** `0.9.0`

This document is the continuation contract for a new ChatGPT conversation or implementation agent. Read this file first, then the stage reports and Stage-10 research files linked below.

The project history is long. Do **not** restart the design from scratch and do not reinterpret already resolved ambiguities unless a new source or failing test justifies it.

---

## 1. User goal

The current goal is **not LiDAR synthesis**.

The user wants a **procedural tunnel geometry generator** whose output can later be loaded into **UNIGINE 2.22 SIM**.

Important target facts:

- UNIGINE-side world coordinates may use **double precision**.
- Therefore the production core may keep vertices many kilometres from world origin.
- Chunking exists for asset management, streaming, culling, export size and Blender convenience — **not because the core needs floating-origin precision**.
- Blender is currently used as a geometry/runtime verifier and convenient preview backend.
- LiDAR may be revisited later, but it is off the near-term roadmap.

The user wants careful staged development, substantial verification, and immediate GitHub pushes for completed changes.

---

## 2. Working style / continuation rules

The user repeatedly stated that time is not constrained and prefers correctness over speed.

For every substantial stage:

1. implement one bounded unit of work;
2. add deterministic unit/regression tests;
3. add stress tests where geometry/topology warrants them;
4. use independent topology checks where practical;
5. push completed changes to GitHub immediately;
6. explicitly state whether the stage is ready to proceed or needs deeper checking;
7. require a real Blender smoke test when the change depends on actual `bpy`/Boolean/runtime behaviour.

Do not silently guess missing engineering dimensions. Explicit fallbacks are allowed only when tagged with provenance/confidence and when the research profile permits them.

---

# PART I — WHAT HAS ALREADY BEEN BUILT

## 3. Stages 1–8: Tunnel Scanner reconstruction baseline

The project began as a geometry-side reimplementation of:

> Yang et al. (2026), *Tunnel scanner: Geometry-informed synthetic point cloud generation and transfer learning for tunnel segmentation*, Automation in Construction 187, 106924.

The authors' original Tunnel Scanner code does not appear to be publicly released. The project therefore reconstructs the published geometry, records ambiguities, and preserves diagnostic modes rather than hiding them.

Detailed reports are in:

- `STAGE1_REPORT.md`
- `STAGE2_REPORT.md`
- `STAGE3_REPORT.md`
- `STAGE4_REPORT.md`
- `STAGE5_REPORT.md`
- `STAGE5_1_REPORT.md`
- `STAGE6_REPORT.md`
- `STAGE7_REPORT.md`
- `STAGE7_1_REPORT.md`
- `STAGE8_REPORT.md`

### Stage 1 — analytical six-segment ring

Physical order:

    K + B1 + A1 + A2 + A3 + B2

Existing core convention:

- +Y = tunnel longitudinal direction;
- XZ = tunnel cross-section;
- alpha = 0 at +Z crown, increasing toward +X.

Base analytical segment is an 8-vertex hexahedron with inner radius `r = R - t_seg`.

Important source ambiguity:

- paper constraints require front/back angular sums to close separately;
- a literal interpretation that every A-segment has identical front/back angle forces K front/back equality;
- this conflicts with the paper's stated allowed K differences.

Two conceptual modes were retained in the reconstruction:

- equation-consistent geometry;
- literal A-equal diagnostic interpretation.

Do not collapse this ambiguity without reason.

### Stage 2 — deformation closure

The paper's printed deformation recurrence appears index-inconsistent: text says `d_i, phi_i` belong to segment `i` relative to `i-1`, but the printed recurrence references previous indices in a way that makes final closure variables ineffective.

The project reconstructs the physically consistent segment-indexed recurrence.

Closure is solved analytically, including a final exact 2x2 system. No SciPy dependency is required.

### Stage 3 — deformed ring geometry

Another likely paper sign issue was identified.

Production/default interpretation uses:

    theta_i = theta_(i-1) - alpha_i + phi_i

because the +phi sign preserves the shared pivot under pure rotation.

Diagnostic modes preserve the printed-sign and previous-index readings.

Displacement-joint meshes bridge deformed segment end/start faces. They are not the same thing as the prescribed nominal joints from Stage 4.

### Stage 4 — prescribed joints

Radial prescribed joint interpretation:

    theta_joi = w_joi / R_joi

with the published geometry reconstructed as an **extrados outer rib/cap** occupying roughly `R ... R+t_joi`.

It is deliberately **not** reinterpreted as an intrados groove.

Circumferential joint reconstruction is more weakly specified by the paper and was implemented as a provisional outer collar. This is documented as reconstruction, not claimed as author-original CAD.

### Stage 5 — engine-neutral ScenePackage

Introduced the engine-neutral scene representation and Blender adapter.

Semantic policy is explicit. The paper states six lining labels but does not publish K/B/A <-> class-index mapping. The implementation convention was recorded rather than presented as source truth.

Blender adapter uses lazy `bpy` import and custom properties such as `labelID`, `ringID`, IDs and reconstruction metadata.

### Stage 5.1 — curved lining surface

Stage 5 initially exposed the analytical 8-vertex hexahedra directly, producing visibly polygonal lining in Blender.

Stage 5.1 fixed this with adaptive cylindrical tessellation.

Sagitta rule:

    s = R * (1 - cos(delta/2))

Default lining render/LiDAR tolerance was 2 mm.

The final mesher is a 2D `(u,v)` grid, not only circumferential rails, because tapered front/back segment angles can otherwise create ruled surfaces that leave the cylinder.

Conservative angular-cell diagonal constraint uses circumferential and longitudinal subdivision counts.

This stage was heavily stress-tested and independently checked with trimesh.

### Stage 6 — bolt pockets and heads

Bolt pockets/heads were implemented as engine-neutral geometry plus Blender Boolean integration.

Keep in mind that Boolean cutters are temporary production tools. Production render finalization must happen after the Boolean bake.

### Stage 7 — multi-ring assembly

Introduced multi-ring tunnel assembly and ring-wise transforms.

### Stage 7.1 — physical wavelength centreline

The original multi-ring perturbation behaviour was corrected to a physical-wavelength centreline model.

The user's visual validation confirmed that the ring geometry and visible X/Z shifts looked correct.

### Stage 8 — Tunnel Scanner ancillary infrastructure

Implemented:

- pavement;
- walkway;
- two running rails;
- tube-like services: pipes/cables/power-track style objects.

Important Stage-8 source/reconstruction decisions:

- preserve the paper's printed walkway-depth upper bound `0.34r` literally rather than silently changing it;
- physical-clearance validation rejects impossible samples;
- the paper's prose/Table 4 disagree on rail spacing interpretation;
- both interpretations exist, production/reference default follows Table 4;
- tube radii are source-backed, but exact count/angular layout is not published, so the reference service layout is explicitly our engineering reconstruction;
- production default ancillary frame is gravity-fixed/stiched, while a literal ring-rigid interpretation remains diagnostic.

Stage 8 was the final geometry layer still closely tied to the paper.

---

# PART II — STAGE 9 PRODUCTION ARCHITECTURE

## 4. Why Stage 9 exists

Stage 9 deliberately stops treating the project as only a Tunnel Scanner reconstruction.

It converts the geometry into a **production procedural asset generator**.

Read in full:

- `STAGE9_REPORT.md`
- `STAGE9_BLENDER_SMOKE_TEST.md`

The user has completed the Stage-9 Blender smoke test successfully.

---

## 5. Canonical coordinate policy

The production core remains in **global coordinates**.

There is no mandatory floating origin and no mandatory chunk-local rebasing.

This is intentional because the eventual UNIGINE target can use double precision.

Chunk localization is an optional Blender/export convenience only.

---

## 6. Physical geometry versus technical chunks

Physical assets:

- lining ring;
- lining segment;
- bolt pocket/head;
- one continuous pavement;
- one continuous walkway;
- two continuous rails;
- configured continuous tube/service runs.

Technical asset:

- optional `TunnelChunk`.

A change in chunk size must not change physical geometry or stable parent identity.

---

## 7. Continuous longitudinal infrastructure

Stage 8 created one closed ancillary solid per ring.

That created coincident internal end caps.

Stage 9 production mode does **not instantiate** Stage-8 ring-local ancillary solids.

Instead, Stage-8 cross-sections are swept continuously over the production alignment.

Reference production infrastructure therefore exists as ten logical assets:

    1 pavement
    1 walkway
    2 rails
    6 tube/service runs

At an inter-ring boundary there is exactly one shared sweep station, not two overlapping caps.

---

## 8. Stage-9 centreline stitching

Production alignment stations are:

    tunnel start
    ring 0 centre
    boundary 0/1
    ring 1 centre
    boundary 1/2
    ...
    final ring centre
    tunnel end

For N rings:

    stations = 2*N + 1

Lining and bolt geometry use the same local-Y-dependent X/Z alignment map as continuous infrastructure.

This was necessary because independently translating complete rings can leave small centreline discontinuities at shared boundaries.

Diagnostic rigid-ring behaviour still exists; production default is stitched.

---

## 9. Z-fighting / hidden-surface policy

Stage 9 intentionally removes or avoids hidden coincident surfaces.

### Continuous infrastructure

Internal ancillary end caps are eliminated by construction.

### Pavement against lining

Hidden perimeter/contact faces are omitted.

### Rail foot against pavement

Hidden rail-foot bottom surface is omitted from production mesh.

### Stage-4 outer-joint reconstruction solids

Extrados-only prescribed-joint solids are omitted from production scenes by default. They remain available for diagnostics.

### Lining

Lining remains closed until Blender bolt Booleans are baked.

After Boolean processing, finalization removes:

- internal front/back lining caps;
- radial segment-to-segment coincident faces.

Canonical five-ring topology audit:

    Stage 8 duplicate groups      94
    Stage 9 source               30
    Stage 9 finalized             0

This cleanup is a production invariant. Do not regress it in Stage 10.

---

## 10. Stage-9 rail profile

Stage 8 rails were rectangular bars.

Stage 9 replaced them with a generic low-poly rail-like profile:

- foot;
- narrow web;
- head;
- shoulder transitions;
- 16 cross-section vertices.

This is deliberately **not** a Moscow/Russian standard rail. Stage 10 replaces it with R65/R50 research geometry.

---

## 11. Long-tunnel verification

Automated Stage-9 baseline includes:

### ~100 m full geometry

    75 rings
    101.25 m generated
    460 objects
    zero exact duplicate faces after finalization

### ~1 km full geometry

    741 rings
    1000.35 m
    4456 objects
    1483 alignment stations
    ~23728 vertices per generic rail
    ~22232 faces per generic rail

### ~5 km alignment stress

    3704 rings
    5000.4 m
    7409 alignment stations

The 5 km case checks global-coordinate alignment without allocating every detailed lining object.

---

## 12. Chunking

Default production chunk policy:

    ring_aligned

Requested chunk length is a target; boundaries snap to complete ring boundaries.

There is also an exact-length diagnostic/export mode.

For Blender:

    --localize-chunks-for-blender

For long export without a monolithic JSON:

    --chunks-only

Chunked infrastructure pieces carry stable parent asset IDs.

Ring IDs remain global.

---

## 13. Stable identity contract

Do not use Python runtime hash.

Stage 9 uses deterministic positive 63-bit BLAKE2b IDs from semantic persistent keys.

Typical keys:

    <namespace>/tunnel
    <namespace>/ring/<global-ring-id>/<object-name>
    <namespace>/infrastructure/rail/0
    <namespace>/infrastructure/rail/1

Physical parent identity is independent of chunk size.

Chunk-piece IDs are technical IDs and retain links to source parent identity.

---

## 14. Blender 5.2 large-integer compatibility

This was discovered in the user's actual Blender 5.2.2 LTS runtime.

Problem:

    OverflowError: Python int too large to convert to C int

Cause:

Stage-9 IDs are 63-bit integers, while Blender scalar custom-property assignment can route through signed 32-bit C int.

Resolved backend policy:

    fits signed int32    -> native Blender integer
    larger integer ID   -> exact decimal string

Engine-neutral ScenePackage/JSON remains a real 63-bit integer.

Inside Blender, consumers should use:

    int(value)

This has regression coverage, including `2^63-1`.

Do not replace stable IDs with 32-bit IDs merely for Blender.

---

## 15. Current automated quality gate

At the Stage-9K code baseline:

    150 tests passed

and:

- Stage 8 stress: PASS;
- Stage 8 independent trimesh: PASS;
- Stage 9 topology audit: PASS;
- Stage 9 long-tunnel stress: PASS;
- Stage 9 independent trimesh: PASS.

Later research-only commits also pass CI.

The user's real Blender Stage-9 smoke test succeeded after the 63-bit ID adapter fix.

**Therefore Stage 9 is closed.**

---

# PART III — STAGE 10 MOSCOW METRO

## 16. Stage-10 direction

Stage 10 is not another Tunnel Scanner reconstruction.

It introduces a **Moscow Metro domain profile** over the production architecture.

Planned Moscow-specific systems include:

- Moscow lining dimensions and archetypes;
- actual R50/R65 rails;
- Russian/Moscow track gauge rules;
- timber sleepers / modern supports;
- KD-65 fastening;
- track concrete;
- central drainage trough;
- Moscow walkway/service geometry;
- contact/third rail;
- cable/service layouts;
- later: historically/project-specific lining details and special structures.

Civil construction era and service-renewal era must remain separate.

---

## 17. Research location

Everything gathered by the external research agent is under:

    research/moscow_metro_tunnels/

Read first:

1. `research/moscow_metro_tunnels/README.md`
2. `research/moscow_metro_tunnels/21_stage10_initial_archetype.md`
3. `research/moscow_metro_tunnels/data/stage10_initial_profile.json`
4. `research/moscow_metro_tunnels/data/stage10_source_pinpoints.json`
5. `research/moscow_metro_tunnels/09_parameter_confidence_matrix.md`
6. `research/moscow_metro_tunnels/15_stage4_reference_sdk.md`

Do not begin Stage 10 from the earlier generic research summary alone. The research agent subsequently performed a focused Stage-10 pass and resolved many previously missing parameters.

---

## 18. Research evidence policy

Confidence classes:

- A — normative / primary;
- B — official project / engineering;
- C — technical secondary / historical;
- D — visual inference.

Non-negotiable rules from the research package:

1. physical geometry != clearance envelope;
2. nominal TBM diameter != finished lining;
3. unknown project dimensions stay unresolved or use explicit fallback metadata;
4. project-specific evidence overrides generic family values;
5. construction archetype belongs to an individual tunnel/track, not merely a line;
6. service systems must have independent pitches/phases;
7. photos do not create exact dimensions unless calibrated;
8. civil era, track-renewal era and services era are separate;
9. public OSM is not as-built survey;
10. published station depth is not automatically UGR elevation.

---

## 19. Selected first Stage-10 archetype

The research agent selected:

    CAST_IRON_5500_R1000
    +
    LEGACY_R65_TIMBER_KD65_2001_REFERENCE

This is now the preferred first implementation target.

Why:

A 2001 engineering source provides a directly applicable cross-section for a **5.1 m internal-diameter circular cast-iron running tunnel with R65 track concrete**.

The initial target is a deterministic civil/track/contact-rail geometry fixture.

The exact cast-iron tubing CAD remains intentionally less detailed until source gaps are closed.

---

## 20. Stage-10 coordinate datum

Research uses UGR (top plane through running-rail heads) as the primary vertical datum.

Initial profile 2D cross-section uses:

    origin: track centerline at UGR
    lateral axis: positive toward walkway / opposite contact rail
    z: up

Important integration warning:

The existing Tunnel_PCG core historically uses:

    +Y longitudinal
    XZ cross-section

Some research documents use an engineering route convention:

    +X chainage
    +Y left
    +Z up

Do **not** silently change the production core axes in Stage 10.

Recommended integration:

- keep the production ScenePackage/world convention stable;
- treat Moscow research cross-sections as local engineering 2D data;
- add an explicit mapping layer between research track-frame coordinates and the existing production tunnel frame.

Axis conversion must be unit-tested.

---

## 21. Initial civil shell — source-backed and ready

Initial circular shell:

    inner diameter          5.100 m
    inner radius            2.550 m
    outer diameter          5.500 m
    outer radius            2.750 m
    ring pitch              1.000 m

Relative to UGR:

    lining center z        +1.670 m
    intrados invert        -0.880 m
    intrados crown         +4.220 m
    extrados invert        -1.080 m
    extrados crown         +4.420 m

This finally resolves the previously missing vertical placement of track relative to the classic 5.1 m intrados.

Do not derive this placement from Cmk.

---

## 22. Walkway — resolved for the initial preset

For the selected legacy civil/service combination, the walkway is real geometry, not simply removed.

Source-backed values:

    top z above UGR          +0.200 m
    inner edge lateral        1.660 m from track/tunnel axis

Intersection of the physical intrados with z=+0.2 gives approximately:

    outer physical x          2.0836516 m

Therefore the implied clear top width is approximately:

    0.4236516 m

This width comes from the **physical lining circle + source dimension**, not from the Cmk clearance envelope.

This supersedes the earlier informal idea that a Moscow preset would simply have no walking pad.

---

## 23. Drainage / track concrete — initial geometry ready

Central drainage trough:

    clear width               0.900 m
    depth below UGR           0.530 m

General source range is 0.5–0.6 m, but the selected running-tunnel drawing gives 0.530 m and that exact value should be used for the deterministic initial profile.

Additional source-backed track-concrete facts:

    transverse fall toward drain   0.03
    water-release groove           25 x 50 mm
    concrete under timber sleeper
      straight                     0.160 m minimum
      curves/turnouts              0.100 m minimum
    concrete surface near sleeper  ~10 mm below sleeper top

The deterministic v1 drain may use a rectangular trough; exact local corner radii/hand finishing are not source-resolved.

---

## 24. R65 running rail — use research reference implementation, not Stage-9 generic rail

The research package contains an engineering reconstruction from GOST R 51685-2022.

Relevant files:

    research/moscow_metro_tunnels/reference_impl/tunnel_pcg_ref/rail_profiles.py
    research/moscow_metro_tunnels/reference_impl/fixtures/r65_analytic_primitives.json
    research/moscow_metro_tunnels/reference_impl/fixtures/r65_profile_0p05mm.csv

R65 principal dimensions:

    height             0.18000 m
    head width         0.07459 m
    base width         0.15000 m
    web thickness      0.01800 m

The reconstruction is source-derived tangent geometry and was validated against GOST area/centroid/template data.

It is suitable for production visual geometry.

Do not keep the Stage-9 generic 16-vertex rail for the Moscow profile.

---

## 25. Gauge rule

Current Moscow gauge depends on horizontal curve radius.

Research rule:

    straight or R >= 1200 m     1.520 m
    600 < R < 1200 m            1.524 m
    400 < R <= 600 m            1.530 m
    125 < R <= 400 m            1.535 m
    100 < R <= 125 m            1.540 m
    R <= 100 m                  1.544 m

Gauge is measured between **inner rail-head working faces**, not rail profile centrelines.

Therefore rail placement must know the reconstructed R65/R50 working-face datum.

For the first straight deterministic fixture, use 1.520 m.

---

## 26. Legacy timber sleepers

Selected first preset uses metro timber sleepers.

Source-backed geometry:

    length                2.650 m
    thickness             0.165 m
    upper face width      0.165 m
    lower face width      0.250 m
    sawn side height      0.135 m

Initial sleeper top:

    z = -0.220 m

This is based on the source drawing interpretation in the Stage-10 profile.

Sleeper density:

    straight / R >= 1200       1680 per km
    tighter curves             1840 per km

Do not blindly reuse Stage-8 rail spacing logic.

---

## 27. KD-65 fastening

The focused research pass now gives enough geometry for an initial KD-65 family.

Baseplate:

    370 x 165 mm
    4 holes
    hole diameter ~26 mm with source tolerance
    hole centres 310 x 100 mm
    max section envelope ~55.6 mm
    source-specific slopes/radii/profile callouts available

Under-baseplate pad:

    370 x 165 x 6 mm
    4 x Ø28 holes
    same 310 x 100 mm centres
    R10 max corner

Rail-foot pad:

    190 x 148 mm
    base thickness 7 mm
    total raised thickness 14 mm
    raised seat length 170 mm
    21 x Ø20 perforations

Metro-specific track screw:

    24 x 150 mm

Do not replace it with the general-railway 24 x 170 mm drawing.

Clamp bolt:

    M22 x 75

Spring clamp:

    KDP-2 / KD-family

Exact spring-clamp solid can remain simplified in the first implementation if marked as such.

---

## 28. Contact rail — initial geometry now implementable

Placement:

    horizontal offset from nearest running-rail inner working face:
        0.690 m ± 0.008 m

    contact working surface:
        +0.160 m ± 0.006 m above UGR

Published metro contact rail RK section:

    height             118 mm
    top width           80 mm
    base width          90 mm
    web width           20 mm

Support/bracket envelope:

    540 x 620 x 100 mm

Reference support pitch range:

    4.5–5.4 m

Deterministic initial fallback:

    5.0 m

Legacy support attaches to timber sleeper using three track screws according to the focused research source.

The exact historic protective-cover extrusion is still unresolved.

For v1:

- preserve historical clearances/support geometry;
- if a modern cover profile is used as silhouette fallback, tag it explicitly as era-mismatched C-confidence;
- do not present that cover as historic fact.

---

## 29. Initial cast-iron ring detail — IMPORTANT LIMIT

The classic 5.5/5.1 cast-iron family is **not yet series-accurate LOD0-ready**.

The focused research pass identifies a useful coarse candidate:

    DZMO_5500_5100_11_SEGMENT_REFERENCE

Possible coarse ring rhythm:

    total 11
    normal 8
    adjacent-to-key 2
    key 1

But the public research set still does not uniquely provide, for one named factory series:

- exact N/C/K central angles;
- exact key wedge angle/dimensions;
- exact rib positions per segment type;
- complete bolt-hole coordinates;
- grout-plug coordinate;
- exact flange/falts/rebate profile.

Therefore the first Stage-10 implementation may use:

- correct 5.5/5.1 civil shell;
- 1.0 m ring seams;
- optionally the 11-piece DZMO rhythm as an explicitly coarse reference;

but it must **not fabricate series-accurate ribs/bolts/pockets**.

The existing Tunnel Scanner six-segment ring must not be cosmetically rescaled and called a Moscow cast-iron ring.

---

## 30. Stage-10 profile machine data

The focused research pass produced:

    research/moscow_metro_tunnels/data/stage10_initial_profile.json

Properties:

- deterministic first profile;
- no null values in required v1 fields;
- unresolved data is encoded as `not_required_for_initial_profile` or explicit fallback;
- source IDs are attached.

Source pinpoints:

    research/moscow_metro_tunnels/data/stage10_source_pinpoints.json

This maps critical dimensions to printed pages / PDF pages / figures / tables / clauses.

Use these files as the Stage-10 implementation input, not prose copied into code.

---

## 31. Reference engineering kernel

The research package includes an isolated reference implementation under:

    research/moscow_metro_tunnels/reference_impl/

Important modules:

- `geometry.py` — analytic 2D primitives;
- `track.py` — gauge/cant;
- `contact_rail.py` — placement logic;
- `clearances.py` — Cmk/Om logic;
- `rail_profiles.py` — R50/R65 reconstruction;
- `rings.py` — ring sequences;
- `events.py` — deterministic periodic systems;
- `alignment3d.py` — chainage/grade/parallel-transport frames;
- schemas and fixtures.

This reference package is intentionally isolated from production code.

Stage 10 should **consume/port tested engineering logic deliberately**, not duplicate constants ad hoc.

---

# PART IV — RECOMMENDED NEXT IMPLEMENTATION PLAN

## 32. Stage 10 should begin now

After the focused research commits, the initial Moscow profile is ready enough to start implementation.

No additional general research pass is required before Stage 10.1.

However, exact cast-iron tubing LOD0 remains blocked and should not block the rest of Stage 10.

---

## 33. Recommended Stage 10.1 — profile/data integration and coordinate contract

Do this first.

Goals:

1. create production-side Moscow profile dataclasses/schema;
2. load/represent the Stage-10 initial profile with provenance;
3. introduce explicit datums:
   - UGR;
   - track axis;
   - tunnel/lining axis;
4. define and unit-test conversion from research 2D frame to existing Tunnel_PCG world/local frame;
5. integrate R65 reference profile into production sweep;
6. implement gauge placement by inner working faces, not profile centres;
7. keep Stage-9 stable IDs/chunking/topology behaviour unchanged.

Do **not** start by modeling ribs/bolts of the cast-iron lining.

Acceptance:

- source/profile values round-trip deterministically;
- exact R65 principal dimensions are verified;
- straight gauge is exactly 1.520 m between working faces;
- rail top plane is UGR z=0 in the engineering track frame;
- world-coordinate mapping agrees with existing Stage-9 longitudinal convention;
- no Stage-9 test regression.

---

## 34. Recommended Stage 10.2 — track/invert/permanent way

Then implement:

- timber sleepers;
- KD-65 baseplate;
- pads;
- track screws;
- clamp bolts;
- simplified/parameterized spring clamp;
- track concrete cross-section;
- 0.9 x 0.53 m central trough;
- 3% crossfall;
- 25 x 50 mm water-release groove;
- deterministic sleeper pitch and independent phase.

Acceptance should include:

- no rail/concrete z-fighting;
- sleeper embedment matches profile data;
- rail-foot support chain is geometrically consistent;
- drain remains physically separate from clearance envelope;
- periodic systems are deterministic and not synchronized to lining rings.

---

## 35. Recommended Stage 10.3 — contact rail

Implement:

- RK rail profile;
- 690 / +160 placement;
- side logic;
- bracket/support chain;
- insulator initial geometry;
- protective cover with explicit fallback metadata;
- support pitch independent from sleepers and lining rings.

Add a strict metadata marker for the era-mismatched cover fallback.

---

## 36. Recommended Stage 10.4 — civil shell / walkway

Implement initial Moscow civil geometry:

- 5.5/5.1 concentric shell;
- center +1.67 m above UGR;
- ring seams at 1.0 m pitch;
- raised +0.2 m walkway;
- 1.660 m inner edge;
- physical intrados-clipped outer edge.

Keep the detailed cast-iron segment surface coarse/disabled unless source-backed.

---

## 37. Recommended Stage 10.5 — production integration

Combine Moscow civil + permanent way + contact rail on the existing Stage-9 production architecture.

Requirements:

- global double coordinates remain canonical;
- chunking remains optional;
- stable parent IDs survive chunking;
- no duplicate/coplanar production faces;
- Stage-9 finalization rules still work;
- Blender backend remains a verifier, not the geometry authority;
- prepare the scene model for a future UNIGINE exporter without coupling core geometry to Blender.

---

# PART V — THINGS THE NEXT AGENT MUST NOT DO

## 38. Do not regress resolved project decisions

Do not:

- make LiDAR the next milestone;
- force floating-origin rebasing into the core;
- make chunking mandatory for precision;
- put ancillary infrastructure back into one closed solid per ring;
- restore coincident internal caps;
- replace stable 63-bit IDs with 32-bit IDs;
- use Blender custom-property limits to redefine engine-neutral IDs;
- use the Stage-9 generic rail for the Moscow profile;
- place rail profile centreline at ±gauge/2;
- use Cmk as a physical tunnel wall;
- derive the tunnel vertical position from Cmk when the source gives physical placement;
- delete the selected Moscow walkway merely because the earlier informal roadmap mentioned no walking pad;
- call the modern protective-cover fallback historical;
- rescale the Tunnel Scanner six-segment lining and call it Moscow cast iron;
- invent exact N/C/K cast-iron geometry.

---

## 39. Known unresolved items that are acceptable to defer

The following do **not** block Stage 10.1–10.5 initial production geometry:

- exact cast-iron N/C/K angles;
- exact key wedge CAD;
- exact rib patterns;
- exact cast-iron bolt-hole coordinates;
- exact grout plug coordinate;
- exact falts/rebate profile;
- exact historical contact-rail protective-cover extrusion;
- exact porcelain insulator CAD;
- exact cable rack/luminaire products;
- local drainage sumps / special chambers;
- full network survey-grade XYZ.

These must remain tagged as unresolved/fallback rather than guessed.

---

# PART VI — REPOSITORY LANDMARKS

## 40. Production code

Main package:

    src/tunnel_scanner_core/

Key Stage-9 production module:

    src/tunnel_scanner_core/production.py

Blender backend:

    src/tunnel_scanner_core/blender_adapter.py

Scene model / JSON:

    src/tunnel_scanner_core/scene.py
    src/tunnel_scanner_core/scene_io.py

Curved lining mesher:

    src/tunnel_scanner_core/curved_mesh.py

---

## 41. Important scripts

Stage-9 generation:

    examples/generate_stage9_production_tunnel.py

Stage-9 Blender verifier:

    scripts/blender_verify_stage9.py

Topology audit:

    scripts/audit_stage9_topology.py

Long-tunnel stress:

    scripts/verify_stage9_stress.py

Independent topology:

    scripts/verify_stage9_trimesh.py

---

## 42. Test commands

Install:

    python -m pip install -e '.[test]'

Regression:

    pytest

The current established production baseline is **194 tests passed** plus Stage-8/9 stress/topology checks and dedicated Stage-10.1–10.5 production gates.

Research reference implementation has its own tests under:

    research/moscow_metro_tunnels/reference_impl/tests/

Do not assume production pytest automatically covers all reference_impl tests unless CI explicitly includes them.

---

## 43. Blender runtime

The user currently has:

    Blender 5.2.2 LTS

Stage-9 Blender verification is known to work after the 63-bit ID adapter fix.

Any new Stage-10 Blender smoke test should preserve that backend behaviour.

---

# PART VII — STATUS TO REPORT IN THE NEXT CHAT

## 44. Current overall status

### Closed

- Stage 1–8 Tunnel Scanner geometry reconstruction baseline;
- Stage 9 production geometry / long-tunnel assembly;
- Stage-9 Blender smoke test and 63-bit Blender-ID compatibility fix;
- focused Stage-10 research pass for the initial Moscow archetype;
- **Stage 10.1 — Moscow profile/data integration + R65/gauge/UGR contract**;
- **Stage 10.2 — legacy timber/KD-65 permanent way + track concrete/drainage**;
- **Stage 10.3 — legacy RK contact rail / sleeper-mounted support chain**;
- **Stage 10.4 — source-sized Moscow civil shell framework + raised walkway; 6.1/5.6 RC ten-block geometry implemented, cast-iron detail deferred**;
- **Stage 10.5 — modern LVT-M/APC-4 service preset, segmented contact cover,
  dedicated contact supports, R2K11 cable racks, DN80 water main and
  zero-error sweep optimization**.

The Stage-10.2/10.3 timber/KD-65 path remains a supported **legacy alternative**
inside Stage 10.5 and has not been removed.

### Ready for operator validation

- **Real Blender 5.2.2 visual/runtime review of the Stage-10.5 modern preset.**
- After that review: address only source-backed visual regressions or move to
  exporter/instancing work.

### Still intentionally blocked

- exact series-accurate classic 5.5/5.1 cast-iron tubing LOD0;
- exact APC-4 small-part CAD;
- exact factory neutral-axis bend radii, clamp casting, modern contact-support hood and cover corner radii;
- project-specific cable schedules/rack elevation;
- exact project water-main schedule/mounting brackets.

---

## 45. Suggested first message/task for the next implementation agent

Use this as the starting instruction:

> Read `PROJECT_HANDOFF.md`, `STAGE10_5_REPORT.md`, `STAGE10_5_BLENDER_SMOKE_TEST.md`, `research/moscow_metro_tunnels/21_stage10_initial_archetype.md`, `data/stage10_initial_profile.json`, and `data/stage10_source_pinpoints.json`. Stages 10.1–10.5 are implemented and CI-validated. Do not remove the legacy timber/KD-65 preset. First inspect the user's Blender 5.2.2 result for the default Stage-10.5 modern preset: LVT-M/APC-4, segmented rounded contact cover, dedicated contact supports, R2K11 racks/cables, DN80 water main, 5.5/5.1 shell and sweep compaction. Fix only demonstrated regressions or source-backed dimensional issues. Keep exact N/C/K cast-iron detail and unresolved small hardware blocked rather than inventing it.

---

## 46. Final note

The first Moscow running-tunnel archetype now has two service-era variants on
one civil/gauge contract:

```text
modern default:
  R65 + LVT-M/APC-4
  modern segmented contact cover + dedicated supports
  R2K11 racks / representative cables
  one DN80-minimum water main

legacy selectable:
  R65 + timber/KD-65
  legacy sleeper-mounted contact support
  legacy service preview
```

The selected civil shell remains the classic 5.5/5.1 family, so the Blender
internal diameter of approximately 5.10 m is intentional.

The next authoritative gate is a real Blender 5.2.2 visual/runtime review of
the modern preset. Keep unresolved factory/project-specific details explicit.


---

## Stage 10.1 implementation update (2026-09-20)

Stage 10.1 has been implemented on master. The bounded scope is:

- production-side Moscow profile/data model in \`src/tunnel_scanner_core/moscow.py\`;
- deterministic loading/round-trip/provenance SHA for \`data/stage10_initial_profile.json\`;
- explicit UGR, track-axis and lining-axis datums;
- explicit mapping between the research route frame and the existing +Y-longitudinal production core;
- production R65 tangent-chain profile ported from the isolated research reference implementation;
- 1.520 m straight-track gauge placed by the two inner rail-head working faces at UGR - 13 mm, not by rail symmetry axes;
- Stage-9 persistent IDs, continuous sweep, chunking and topology architecture retained;
- dedicated unit/regression coverage and \`scripts/verify_stage10_1.py\`;
- CI extended with the Stage-10.1 production verifier.

Key deterministic R65 placement values for the first profile:

\`\`\`text
UGR local z                         0.000000000 m
gauge measurement z               -0.013000000 m
R65 working-face offset            0.03612386585834637 m
negative-X rail symmetry axis     -0.7961238658583464 m
positive-X rail symmetry axis     +0.7961238658583464 m
inner working faces               -0.760 / +0.760 m
working-face gauge                 1.520000000 m
\`\`\`

Coordinate integration contract for the deterministic first profile:

\`\`\`text
profile +X (walkway side) -> core +X
route +X (chainage)       -> core +Y
route +Y (left)           -> profile -X -> core -X
route +Z                  -> core +Z
\`\`\`

Important: UGR z=0 is a **profile/engineering-track datum**, not the production-core Z origin. The production core is anchored at the lining axis. For the selected first profile, the lining axis is +1.670 m above UGR, so:

\`\`\`text
core_z = profile_z - 1.670 m
profile UGR z = 0.000 m   -> core UGR z = -1.670 m
R65 base      -0.180 m   -> core R65 base = -1.850 m
gauge plane   -0.013 m   -> core gauge plane = -1.683 m
lining axis   +1.670 m   -> core lining axis = 0.000 m
\`\`\`

Existing Stage-9 alignment offsets are then applied by the sweep, so world Z is \`core_local_z + station.offset_z_m\`.

A first Stage-10.1 operator smoke exposed a bug where profile Z was mapped without this translation, putting the rails through the centre of the Stage-9 ring. That bug has been corrected and regression-tested.

Stage 10.1 intentionally does **not** implement sleepers/KD-65/invert/drainage, contact rail, Moscow civil shell placement, or detailed cast-iron ribs/bolts. Those remain the next bounded stages, beginning with Stage 10.2.

Detailed implementation/verification notes are in \`STAGE10_1_REPORT.md\`.


### Stage 10.1 operator entry points

The user-facing generate -> JSON -> Blender workflow is now restored for the
Stage 10.1 mode:

\`\`\`text
python examples/generate_stage10_production_tunnel.py --domain-stage 10.1 --rings 20 --namespace stage10-1-smoke

blender --background --python scripts/blender_verify_stage10.py -- \
  examples/stage10_production_scene.json \
  --report examples/blender_stage10_runtime_report.json \
  --save-blend examples/stage10_production_scene.blend
\`\`\`

The generator explicitly loads the initial Moscow profile and enables
\`ProductionConfig.moscow_profile\`; the Stage-9 generator remains a separate
generic-rail compatibility path. The Stage-10 Blender verifier validates R65,
UGR, 13 mm gauge plane, exact 1.520 m working-face gauge, persistent IDs and the
existing Boolean/topology finalization path.

CI compiles both new entry points and runs a real Stage-10.1 CLI scene-generation
smoke in addition to the existing 75-ring Stage-10.1 production verifier.

### Next implementation boundary

Do not reopen Stage 10.1 geometry unless a regression or source correction requires it.

Historical note: at Stage-10.1 closure, the next implementation task was **Stage 10.2 only**. Stage 10.2 is now closed; the current next boundary is Stage 10.3.

- permanent-way support chain for the selected legacy R65/timber/KD-65 preset;
- sleeper/KD-65/support geometry;
- track concrete, central drain and crossfall using the already researched Stage-10 profile data;
- preserve the Stage-10.1 UGR/gauge/profile/frame contracts unchanged unless new primary evidence requires a documented revision.

Detailed cast-iron tubing remains blocked pending a defensible exact series/tubing drawing and must not be guessed.


---

## Stage 10.2 implementation update (2026-09-20)

Stage 10.2 is implemented on `master`.

### Bounded scope completed

Production Moscow mode now includes:

- timber sleeper geometry from the selected GOST 22830-77 metro sleeper;
- straight-track sleeper density 1680/km;
- deterministic pitch `0.5952380952380952 m`;
- half-pitch periodic phase independent from lining-ring rhythm;
- under-baseplate KD-65 pads;
- KD-65 baseplates;
- R65 rail-foot pads;
- metro 24x150 track screws;
- M22x75 clamp hardware;
- explicitly simplified/parameterized spring-clamp geometry;
- continuous Moscow track-concrete geometry;
- 0.900 m clear central drain;
- drain bottom at profile z=-0.530 m;
- 3% transverse fall toward the drain;
- 50x25 mm water-release groove;
- localized support-contact topology cleanup on each rail pad while preserving the continuous R65 underside;
- stable periodic parent IDs across different chunk lengths.

The old Stage-8/9 `production_pavement` is removed in Stage 10.2 and replaced
by `production_track_concrete`.

### Permanent-way datums

The Stage-10.1 frame contract remains unchanged:

```text
core_z = profile_z - 1.670 m

UGR / R65 head                 profile  0.000 -> core -1.670
R65 base                       profile -0.180 -> core -1.850
sleeper top                    profile -0.220 -> core -1.890
sleeper bottom                 profile -0.385 -> core -2.055
central drain bottom           profile -0.530 -> core -2.200
water-release groove bottom    profile -0.555 -> core -2.225
Moscow intrados invert         profile -0.880 -> core -2.550
```

The 40 mm gap between sleeper top and R65 base is closed by:

```text
under-baseplate pad        6 mm
KD-65 rail-seat part      20 mm   explicit C-confidence stack-fit fallback
R65 rail pad              14 mm
                          -----
total                     40 mm
```

The 20 mm rail-seat contribution is explicitly marked as a derived fallback;
it is not silently claimed as a separately dimensioned Moscow factory value.

### Explicit visual fallbacks

Stage 10.2 closed on profile schema 1.4; the shared profile is now schema 1.6
after Stage 10.3 contact-rail and Stage 10.4 civil/walkway additions. Production code does not hide unresolved
fastening dimensions as magic constants.

C-confidence visual fallbacks are recorded for:

- flat track-screw head preview geometry;
- exact local clamp-bolt axis/slot placement;
- exact KDP-2 spring-clamp silhouette/position;
- lateral position of the 50x25 mm groove (centered in the drain for v1).

The 3% concrete surface is no longer a free C-confidence breakpoint fallback:
its deterministic v1 anchor is now the physical sleeper end
`|x|=1.325 m, z=-0.230 m`, preserving the source-derived 10 mm sleeper
exposure there. The remaining uncertainty is the exact hand-finished local
breakpoint/fillet geometry.

These remain replaceable when better project/factory drawings are found.

### New production module

```text
src/tunnel_scanner_core/permanent_way.py
```

Important APIs:

- `sleeper_chainages`
- `track_concrete_profile_xz`
- `track_concrete_core_xz`
- `build_stage10_2_local_event_meshes`

### Operator workflow

Stage 10.2 is now an explicit compatibility mode:

```text
python examples/generate_stage10_production_tunnel.py \
  --domain-stage 10.2 \
  --rings 20 \
  --namespace stage10-2-smoke

blender --background --python scripts/blender_verify_stage10.py -- \
  examples/stage10_production_scene.json \
  --report examples/blender_stage10_runtime_report.json \
  --save-blend examples/stage10_production_scene.blend
```

To reproduce Stage 10.1 explicitly:

```text
python examples/generate_stage10_production_tunnel.py \
  --domain-stage 10.1 \
  --rings 20 \
  --namespace stage10-1-smoke
```

### Verification

New regression file:

```text
tests/test_moscow_stage10_2.py
```

New stress gate:

```text
scripts/verify_stage10_2.py
```

The established Stage-10.2 CI baseline before documentation-only commits is:

```text
165 tests passed
Stage 10.1 CLI compatibility smoke             PASS
Stage 10.2 CLI permanent-way smoke             PASS
Stage 8/9 legacy stress/topology gates         PASS
Stage 10.1 Moscow production verifier          PASS
Stage 10.2 permanent-way verifier              PASS

30-ring / 40.5 m Stage 10.2 stress:
  sleeper count                                68
  sleeper pitch                                0.5952380952380952 m
  duplicate permanent-way face groups         0
  continuous R65 bottom edges omitted          0
  rail-pad hidden contact span omitted         true
  stable periodic parent IDs across chunks    true
```

The exact final HEAD should still be checked after the final documentation
commits before reporting Stage 10.2 closed.

### Important transitional civil-shell note

Track concrete already closes down to the researched physical Moscow 5.1 m
intrados. The visible lining remains the old Stage-9/Tunnel-Scanner shell until
Stage 10.4.

Therefore the lower concrete boundary can appear separated from the current
visible lining. This is an intentional bounded-stage mismatch. Do not move the
track datums to the Stage-9 pavement/shell to hide that gap.

The Stage-8/9 walkway and service tubes also remain transitional.

### Next implementation boundary

Historical boundary: Stage 10.3 contact rail is now implemented and closed.
The current bounded next stage is Stage 10.4 civil shell / walkway.

Detailed Stage-10.2 notes:

```text
STAGE10_2_REPORT.md
STAGE10_2_BLENDER_SMOKE_TEST.md
```

Detailed cast-iron tubing remains blocked pending defensible exact
series/manufacturing drawings and must not be guessed.


---

## Stage 10.3 implementation update (2026-09-20)

Stage 10.3 is implemented on `master`.

### Bounded scope completed

Production Moscow mode now adds to Stage 10.2:

- continuous bottom-collection RK contact rail;
- contact axis at profile x=-1.450 m;
- working surface at profile z=+0.160 m / core z=-1.510 m;
- 690 mm placement from the nearest running-rail inner working face;
- RK principal section 90/80/20/118 mm with explicitly linearized unresolved
  transition radii;
- independent 5.0 m target support chain;
- deterministic snapping of supports to actual timber sleepers;
- resulting 4.761904762 / 5.357142857 m interval family within the researched
  4.5-5.4 m range;
- curved-channel bracket preview;
- three 24x150 mm sleeper-attachment screws per support;
- 150x112 mm porcelain-insulator envelope;
- simplified retaining/fastening unit;
- protective-cover preview with strict `eraMismatch=true`.

### Protective-cover contract

Historical clearances/envelope have priority over the modern silhouette
fallback:

```text
lower cover edge above contact surface   0.023 m
working-surface-to-cover-top envelope    0.223 m
effective cover height                   0.200 m
historical lateral rail/board gap        0.020 m
```

The current preview width is adjusted so the 90 mm RK section keeps 20 mm
internal lateral clearance:

```text
outer top width  0.112 m
outer base width 0.134 m
side wall        0.002 m
top wall         0.003 m
```

The modern product silhouette is explicitly **not** asserted to be historical
Moscow CAD.

### Stable identity / chunks

Continuous keys:

```text
<namespace>/infrastructure/contact-rail/0
<namespace>/infrastructure/contact-rail-cover/0
```

Support-event keys:

```text
<namespace>/contact-rail/support-event/<event-index>/<category>
```

Periodic support objects carry `eventChainageM` and therefore use the same
event-chainage exact-length chunk assignment introduced in Stage 10.2.

### Important civil-shell mismatch

The ~0.4 m visible gap between `PROD_TRACK_CONCRETE` and the current tubings is
**not a bug**. Track concrete already closes to the researched physical 5.1 m
Moscow intrados; the visible lining remains the old Stage-9 shell.

Do not alter track/contact-rail datums to hide this gap. Stage 10.4 replaces the
civil shell and closes the interface.

### Operator workflow

Stage 10.3 is now the default:

```text
python examples/generate_stage10_production_tunnel.py \
  --rings 20 \
  --namespace stage10-3-smoke

blender --background --python scripts/blender_verify_stage10.py -- \
  examples/stage10_production_scene.json \
  --report examples/blender_stage10_runtime_report.json \
  --save-blend examples/stage10_production_scene.blend
```

Stage 10.2 compatibility requires `--domain-stage 10.2`.

### Verification

Regression file:

```text
tests/test_moscow_stage10_3.py
```

Stress gate:

```text
scripts/verify_stage10_3.py
```

CI includes Stage-10.1/10.2/10.3 CLI smoke plus all prior Stage-8/9 stress and
topology gates.

Detailed notes:

```text
STAGE10_3_REPORT.md
STAGE10_3_BLENDER_SMOKE_TEST.md
```

### Next implementation boundary

**Stage 10.4 only — Moscow civil shell / walkway.**

Implement:

- 5.5/5.1 concentric physical shell;
- lining axis +1.670 m above UGR;
- intrados radius 2.550 m;
- extrados radius 2.750 m;
- 1.0 m civil ring pitch;
- raised walkway top +0.200 m;
- walkway inner edge x=+1.660 m;
- walkway outer edge clipped to physical intrados;
- preserve the existing Stage-10 track/contact-rail coordinate contracts.

Keep series-accurate N/C/K ribs, bolt-hole coordinates, grout-plug coordinates
and rebate geometry unresolved unless defensible manufacturing drawings are
found.


---

## Stage 10.4 implementation update (2026-09-20)

Stage 10.4 replaces the transitional Stage-9 civil geometry in Moscow mode.

### Civil shell

Implemented production geometry:

```text
family                    CAST_IRON_5500_R1000
intrados radius           2.550 m
extrados radius           2.750 m
structural depth          0.200 m
lining axis profile z    +1.670 m
lining axis core z        0.000 m
civil ring pitch          1.000 m
```

The geometry mode is a smooth concentric ringwise shell. It deliberately does
not fabricate unresolved N/C/K central angles, ribs, bolt-hole coordinates,
grout-plug coordinates or rebates.

The historical 11-piece family rhythm is retained as reference metadata only:

```text
coarseSegmentCountReference = 11
coarseSegmentCountIsGeometry = false
seriesAccurateTubingLOD0 = false
```

Stage-9 `lining_segment`, bolt-head/cutter and prescribed-joint geometry is
removed in Stage 10.4. Legacy Stage-9 bolt tooling is not built in this mode.

### Raised walkway

The old generic `production_walkway` is replaced by:

```text
production_moscow_walkway

top profile z             +0.200 m
inner edge profile x      +1.660 m
documented outer x         2.083650643 m
exact mesh outer x         2.083650642502... m
top clear width            ~0.423650643 m
side                        +X / opposite contact rail
```

The mesh uses the exact physical intrados intersection even though the
machine-profile source datum is stored rounded to 9 decimal places.

At x=+1.660 m the track-concrete top is profile z=-0.21995 m. The concrete is
partitioned there; the walkway provides the exposed riser up to +0.200 m and
then closes to the physical intrados.

Hidden concrete/walkway/lining contact faces are omitted.

### Resolution of the former civil gap

The approximately 0.4 m gap visible through Stage 10.2 and 10.3 was an
intentional bounded-stage mismatch: track concrete already used the Moscow
5.1 m intrados while the visible shell was still Stage-9 geometry.

Stage 10.4 closes that mismatch. Metadata now reports:

```text
transitionalCivilGapStatus = closed_by_stage10_4_moscow_shell
```

Do not move track datums. If a comparable gap appears in a freshly regenerated
Stage-10.4 scene, treat it as a bug.

### New production module

```text
src/tunnel_scanner_core/civil.py
```

Key APIs:

- `civil_ring_ranges`
- `walkway_profile_xz`
- `walkway_core_xz`
- `build_annular_shell_sweep`

### Verification

Regression file:

```text
tests/test_moscow_stage10_4.py
```

Stress gate:

```text
scripts/verify_stage10_4.py
```

CI also runs a Stage-10.4 CLI smoke. The Stage-10 Blender verifier is
stage-aware through 10.4.

Latest fully green Stage-10.4 baseline:

```text
179 tests passed
Stage 10.1 CLI compatibility smoke          PASS
Stage 10.2 CLI permanent-way smoke          PASS
Stage 10.3 CLI contact-rail smoke           PASS
Stage 10.4 CLI civil-shell smoke            PASS
Stage 8/9 stress/topology gates             PASS
Stage 10.1/10.2/10.3/10.4 verifiers        PASS

30 source rings / 40.5 m Stage 10.4 stress:
  Moscow civil rings                         41
  duplicate production face groups           0
  stable civil parent IDs across chunks      true
  transitional civil gap closed              true
```

### Operator workflow

Stage 10.4 is the default:

```text
python examples/generate_stage10_production_tunnel.py \
  --rings 20 \
  --namespace stage10-4-smoke

blender --background --python scripts/blender_verify_stage10.py -- \
  examples/stage10_production_scene.json \
  --report examples/blender_stage10_runtime_report.json \
  --save-blend examples/stage10_production_scene.blend
```

Stage 10.3 compatibility now requires `--domain-stage 10.3`.

Detailed notes:

```text
STAGE10_4_REPORT.md
STAGE10_4_BLENDER_SMOKE_TEST.md
```

### Next implementation boundary

**Stage 10.5 only — final production integration / initial-archetype validation.**

Do not open exact series-accurate tubing detail unless a defensible
manufacturing drawing resolves the remaining N/C/K geometry.


---

## Stage 10.5 modern-service implementation update (2026-09-21)

Stage 10.5 is now the current default Moscow production mode.

### Preset selection

Default:

```text
MODERN_MOSCOW_LVT_SERVICES_2020S
```

Preserved selectable legacy alternative:

```text
LEGACY_R65_TIMBER_KD65_2001_REFERENCE
```

The legacy timber/KD-65 implementation was **not removed**.

Production selection:

```text
python examples/generate_stage10_production_tunnel.py \
  --rings 20 \
  --namespace stage10-5-modern

python examples/generate_stage10_production_tunnel.py \
  --domain-stage 10.5 \
  --service-preset legacy \
  --rings 20 \
  --namespace stage10-5-legacy
```

### Modern permanent way

Current default:

```text
family                       LVT-M
running rail                 R65
fastening                    APC-4
support pitch                0.600 m
block transverse length      0.640 m
block top width              0.180 m
block height                 0.165 m
block base widths            0.197 / 0.178 m
rail seat cant               1:20
rail pad thickness           0.014 m
```

Each running rail has an independent half-sleeper block. No block bridges the
0.900 m central drainage trough.

Exact APC-4 small hardware solids remain fallback previews and are explicitly
tagged as such.

### Modern contact rail

The running contact rail retains the established engineering datum:

```text
axis profile x               -1.450 m
working surface profile z    +0.160 m
reference offset              0.690 m
RK height                     0.118 m
```

The modern protective cover is no longer the Stage-10.3 tall rectangular
continuous fallback.

Modern cover envelope:

```text
top width                     0.092 m
base width                    0.114 m
height                        0.111 m
side wall                     0.002 m
top wall                      0.003 m
```

Geometry mode:

```text
rounded_wrap_profile_from_exact_envelope
```

The main cover is segmented. It is interrupted around support zones and each
support zone has a separate local protective hood.

Modern contact support events use dedicated concrete support blocks rather than
sharing or intersecting running-rail LVT supports.

A 2026-09-21 user-supplied dimensioned support drawing is now part of the
machine profile (schema 2.0). Readable callouts:

```text
running reference -> contact-axis region      0.683 m
running reference -> outer bracket envelope   0.873 m
upper return / top plate                       0.180 m
bracket top above UGR/reference                0.373 m
lower/upper bend callouts                      0.155 / 0.090 m
```

The 683/155 mm values are independent drawing cross-checks of the authoritative
690 +/- 8 mm / +160 mm contact-rail placement and do not move the rail.

The modern bracket is now `dimensioned_hook_channel_873x373_v3`, with a
separate four-anchor base plate, explicit upper-flange saddle/bridge clamp,
short vertical insulator stack, two visible through-bolts and a taller rounded
local hood that encloses the +0.373 m bracket/clamp top.

The target support chain remains 5.0 m inside the researched 4.5-5.4 m interval
family, but the event phase is snapped to midpoints between running-support
events rather than to timber sleepers.

### R2K11 cable infrastructure

The modern preset removes the old six Stage-8 generic tube/service previews.

Implemented R2K11 principal dimensions:

```text
horn count                    11
overall arc length            1.440 m
upright longitudinal width    0.048 m
upright thickness             0.003 m
horn thickness                0.004 m
horn radius                   0.0325 m
derived horn pitch            0.125 m
max cable diameter            0.065 m
```

Placement:

```text
one rack per side per 1.0 m Moscow civil ring
```

The current v5 preview follows the supplied R2K11/K1350.002 drawing, 3D
reference and Blender feedback. Each horn is one continuous rounded-W /
omega-like formed ribbon that starts directly on the upright, passes through
both cable cradles and the central crest, then turns up at the free end. There
is no separate horizontal shelf, neck or wall-side tab. The v5 mesh uses four
sparse interpolation samples per anchor span instead of two, making the bends
visibly rounder while preserving a modest polygon count.

The preset occupies eight distributed levels per wall with one cable per
occupied level, for 16 representative service cables total. Cable sag is
nominally 25 mm but is deterministic and irregular per cable/span: amplitude
varies by +/-35% and the low point shifts by up to +/-0.12 of the 1.0 m span.
Only one interior sag control point is added per span.

The negative-X/contact-rail-side rack midpoint is placed at the lining-axis
height to match the supplied visual reference. This remains a visual placement
rule rather than a manufacturer mounting datum.

Exact project cable occupancy, cable types/diameters and route schedules remain
unresolved.

### Current water main

Stage 10.5 now includes the current tunnel water-main rule:

```text
minimum nominal size          DN80
quantity                      1 per single-track tunnel
position rule                 above UGR
normal side                   weak-current side
```

Preview-only placement values:

```text
visual OD proxy               0.089 m
profile center z              +0.600 m
shell clearance inward        0.040 m
support maximum pitch          4.000 m
```

The exact project pipe schedule, wall thickness and mounting coordinates remain
unresolved and are tagged as fallbacks.

### Polygon-count optimization

Stage 10.5 enables exact collinear alignment compaction for continuous sweeps:

```text
continuousSweepAlignmentCompaction = exact_zero_error_collinear
```

It removes only mathematically redundant Stage-9 ring-boundary midpoint
stations. It does not approximate the alignment.

The R65 profile remains 118 vertices.

Four-ring CI smoke:

```text
rail source stations          9
rail sweep stations           4
```

This directly targets the user's 2.7 km observation where each R65 rail was
approaching one million polygons. The longitudinal rail sweep section count is
substantially reduced without changing the rail surface.

### Selectable Stage-10 civil envelope

The generator accepts:

```text
--civil-archetype cast_iron_5500_5100
--civil-archetype rc_block_6100_5600
```

The 5.5/5.1 m cast-iron family remains the compatibility default. Its principal
diameters and 1.0 m ring rhythm are retained, but detailed N/C/K tubing geometry
is deliberately **deferred**. Do not restore the previous provisional
11-division rib/flange/M27 visual overlay: the exact cast-iron segment angles,
ribs, drilling, rebates and fastening geometry are not sufficiently resolved.

The implementation focus is now the researched Moscow precast-RC archetype
`RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000`:

```text
outer / inner diameter         6.100 / 5.600 m
structural depth               0.250 m
ring pitch                     1.000 m
blocks                         10 identical curved RC blocks
block volume                   0.46 m3
block mass                     1.15 t
historical concrete grade      400
working reinforcement          16 mm
erection pins                  22 mm
permanent bolted block joints  false
```

Each generated RC ring now consists of ten **disconnected full-depth curved
annular block meshes**, following the useful Stage-9 segment topology but using
the Moscow dimensions/topology above. Radial block end faces are explicit.
The current 8 mm inter-block gap is only a visibility fallback; it is not a
source-backed joint width.

Exact radial-end chamfers, pin holes/seats and reinforcement-mesh CAD remain
unresolved and must not be invented. The generated annulus gives about
4.60 m3/ring, or 0.46 m3 per ten equal blocks, independently matching the S026
block-volume datum.

S026 does not provide a separate UGR-to-lining-axis placement for this family,
so the larger RC archetype explicitly inherits the Stage-10 track/UGR datum and
all radius-dependent geometry is recomputed from the selected intrados.

### Verification

Current exact CI baseline:

```text
194 tests passed
Stage 10.1 CLI compatibility smoke          PASS
Stage 10.2 CLI compatibility smoke          PASS
Stage 10.3 CLI compatibility smoke          PASS
Stage 10.4 CLI compatibility smoke          PASS
Stage 10.5 modern CLI smoke                 PASS
Stage 10.5 6.1/5.6 RC CLI smoke             PASS
Stage 10.5 legacy CLI smoke                 PASS
Stage 8/9 stress/topology gates             PASS
Stage 10.1-10.5 verifiers                   PASS
```

40.5 m Stage-10.5 integration stress:

```text
modern LVT support events                   67
contact supports                             8
contact cover spans                          9
service cables                              16
R2K11 rack objects                          82
water mains                                  1
duplicate modern face groups                 0
stable parent IDs across chunk sizes         true
legacy timber variant selectable             true
```

Regression:

```text
tests/test_moscow_stage10_5.py
```

Stress/integration gate:

```text
scripts/verify_stage10_5.py
```

Operator docs:

```text
STAGE10_5_REPORT.md
STAGE10_5_BLENDER_SMOKE_TEST.md
```

### Current source-boundary list

Still intentionally unresolved rather than fabricated:

- exact cast-iron N/C/K angles, rib coordinates, bolt drilling, rebates and grout plugs;
- exact LVT rubber-boot outer section;
- exact APC-4 small hardware CAD;
- exact current contact-cover corner radii;
- exact factory neutral-axis bend radii for the now dimension-constrained bracket;
- exact clamp casting/base-plate slot geometry and support-hood product CAD;
- exact project-specific R2K11 elevation;
- exact project cable occupancy and cable diameters;
- exact current water-main pipe schedule and mounting brackets;
- route-specific curve/cant/special-track variants;
- final UNIGINE exporter/instancing implementation.

### Next action

Do not add another geometry stage before a real Blender 5.2.2 visual/runtime
review of the Stage-10.5 modern preset.

Use:

```text
python examples/generate_stage10_production_tunnel.py \
  --rings 2000 \
  --namespace stage10-5-modern

blender --background --python scripts/blender_verify_stage10.py -- \
  examples/stage10_production_scene.json \
  --report examples/blender_stage10_runtime_report.json \
  --save-blend examples/stage10_production_scene.blend
```

For faster visual iteration use 20-100 rings first.
