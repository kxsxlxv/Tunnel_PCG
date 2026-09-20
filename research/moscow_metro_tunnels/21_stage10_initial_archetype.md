# Stage 10 — initial implementable tunnel cross-section

## Selected archetype

**CAST_IRON_5500_R1000 + service preset LEGACY_R65_TIMBER_KD65_2001_REFERENCE**

This choice supersedes the provisional RC-first plan because the user-supplied 2001 book contains an unusually complete, directly applicable cross-section: Fig. 1.14 is explicitly a **5.1 m internal-diameter circular cast-iron running tunnel with R65 rails and track concrete**.

The first implementation target is therefore a deterministic civil/track/contact-rail XZ fixture, while the cast-iron ring itself remains deliberately below series-accurate LOD0.

## 1. Closed civil XZ section

Coordinate convention:
- x=0: track/tunnel axis;
- z=0: UGR;
- +x: walkway side;
- -x: contact-rail side.

From Fig. 1.14:
- intrados diameter = 5.100 m;
- theoretical lining center = +1.670 m above UGR.

Therefore:
- intrados radius = 2.550 m;
- intrados invert = **z=-0.880 m**;
- intrados crown = **z=+4.220 m**.

For the documented classic 5.5/5.1 family:
- extrados radius = 2.750 m;
- extrados invert = **z=-1.080 m**;
- extrados crown = **z=+4.420 m**.

The civil shell is thus a fully closed pair of concentric circles for the first cross-section fixture.

Primary source:
Frolov/Golitsynskiy/Ledyaev, *Metropoliteny* (2001), printed p.27, Fig.1.14; public mirror: https://ru.djvu.online/file/hXOquNRuMqgHC

## 2. Track concrete / invert

The same source family provides:
- central drainage clear width **0.900 m**;
- drainage depth **0.500–0.600 m below UGR**;
- drainage longitudinal grade = track grade;
- B12.5 track concrete;
- minimum concrete under timber sleeper at rail locations:
  - **0.160 m straight**;
  - **0.100 m curves/turnouts**;
- 3% transverse fall toward the central drain;
- small water-release groove **25×50 mm** in Fig.1.14.

For deterministic first geometry the drain depth is set to **0.550 m**, the midpoint of the source range. This is explicitly a fallback, not a newly discovered exact value.

Exact numerical corner radii or side batter of the central drain are not stated. Version 1 uses an open rectangular trough; this must remain replaceable.

The track-concrete surface is physical geometry and is never derived from Cmk.

## 3. Walkway resolved

For this civil/service combination the walkway is **not** treated as a modern optional retrofit.

Fig.1.14 identifies item 3 as the pedestrian/service walkway and dimensions its top at **+0.200 m above UGR**. Legacy metro design rules independently require a walkway in 5.1/5.2 m running tunnels on the side opposite the contact rail.

Fig.1.14 also gives **1660 mm from track/tunnel axis to the inner walkway edge**.

At z=+0.200, intersection with the physical 5.1 m intrados circle is:

x = sqrt(2.55² - (0.200-1.670)²) = 2.0836516 m.

Thus the top clear width implied by the physical lining + source dimension is approximately:

**2.0836516 - 1.660 = 0.4236516 m.**

This width is **not** derived from the Cmk clearance envelope.

## 4. Cast-iron ring readiness

The 2001 book, Fig.4.14/table and adjacent text provide a useful classic 5.5/5.1 variant:
- ring width 1.0 m;
- one documented table variant: 11 tubings;
- minimum N/C/K system;
- 1 key + 2 adjacent -> for an 11-element ring, 8 normal + 2 adjacent + 1 key;
- flange height 200 mm;
- flange thickness 25 mm;
- typical M27×120 bolts;
- bolt holes typically 3–4 mm larger than bolt;
- working bolts in longitudinal joints arranged in two rows;
- grout-injection opening exists;
- caulking rebate/falts exists.

However, public material inspected so far does **not** uniquely supply, for one named factory series:
- all N/C/K central angles;
- exact key wedge angle;
- exact radial-rib positions;
- exact bolt-hole coordinate pattern;
- exact grout-plug coordinate;
- exact falts/rebate profile.

There is also a documented family distinction: Lentrublit 5.49/5.1 and DZMO 5.5/5.1 variants differ, including 10 vs 11 elements in historical literature.

**Conclusion: CAST_IRON_5500_R1000 is ready for a closed civil XZ profile and coarse ring rhythm, but is NOT series-accurate LOD0-ready.**

The first version must not invent the missing tubing CAD.

## 5. Legacy R65 timber permanent way

Initial service preset uses R65 because Fig.1.14 is explicitly R65.

Timber sleeper standard (GOST 22830-77, clause 1.2/Table 1):
- length 2650±20 mm;
- thickness 165±5 mm;
- upper face 165 mm;
- lower face 250 -5/+20 mm;
- sawn side height 135 mm.

Frolov Fig.1.17 provides the KD-65 assembly topology and fasteners:
- 24×150 mm flat-head track screws;
- M22×75 clamp bolts;
- M22×22 nuts;
- spring clamps;
- KD-65 baseplate;
- rail pad and under-baseplate pad.

GOST 16277-2016 Fig.3 is the dimensioned KD-65 drawing:
- overall plan envelope 370×165 mm;
- four Ø26 +1.5/-0.5 mm holes;
- 55.6 mm reference maximum section height;
- the figure contains the rail-seat/local profile dimensions and radii needed for CAD reconstruction.

The first procedural version should reconstruct the baseplate directly from GOST Fig.3. Until then an envelope mesh is allowed only as an explicitly tagged fallback.

## 6. Contact rail

Frolov Fig.1.20 supplies assembly and placement, not just the two familiar placement numbers:
- 690±8 mm horizontal;
- working surface +160±6 mm above UGR;
- 223 mm overall vertical envelope shown for the rail/protective assembly;
- component topology includes bracket, timber sleeper fixing, insulators, pads, spacer/protective elements and cover.

For the rail object itself, a manufacturer drawing gives the metro RK section:
- height 118±1 mm;
- top width 80±2 mm;
- base width 90±1 mm;
- web width 20±1 mm.

For bracket silhouette the Moscow material schedule gives a tunnel bracket envelope:
**540×620×100 mm**.

Historical VNiR §V3-5-47 supplies cover installation geometry:
- 20 mm gap between adjacent covers;
- 25 mm cover-to-insulator gap;
- 20 mm side-board-to-rail-head gap;
- lower side-board edge 23 mm from the contact surface;
- support axes 300 mm from cover ends.

The exact historical cover extrusion is still missing. Version 1 may use a modern published metro cover profile only as an **era-mismatched C-confidence fallback**, never as historical fact.

## 7. Civil era and service era are separated

Civil:
- classic circular 5.5/5.1 cast-iron lining.

Initial services:
- R65 running rail;
- timber sleepers in track concrete;
- KD-65 fastening;
- legacy bottom-collection contact rail;
- raised +200 mm walkway;
- legacy open cable racks;
- legacy tunnel lighting.

This is a **preset**, not a claim that every surviving 5.5/5.1 tunnel looks this way today.

A modern-renewal preset may later replace track with LVT, cables and lighting while retaining the same civil lining.

## 8. Source pinpoints

Every critical dimension is mapped to a figure/table/clause in:
- `data/stage10_source_pinpoints.json`.

The uploaded scan is referenced by printed page and figure, and the public mirror URL is retained so another agent can reproduce the lookup.

## 9. Machine-readable profile

`data/stage10_initial_profile.json` contains the deterministic initial profile.

There are **no null values**. Unknowns are encoded as either:
- `not_required_for_initial_profile`, or
- explicit fallback values with confidence and reason.

## 10. Publicly unresolved parameters

For first-version planning:

### Exclude from LOD0 until a project/factory drawing is found
- exact N/C/K central angles for one named 5.5/5.1 factory series;
- key wedge dimensions;
- complete rib layout by segment type;
- complete bolt-hole coordinates;
- grout-plug coordinate;
- exact falts/caulking groove profile.

### Parameterize manually / replace when better source appears
- exact historical contact-rail protective-cover extrusion;
- exact porcelain insulator solid geometry;
- exact KD-65 rubber/polymer pad contour/material for a specific Moscow maintenance era;
- concrete-to-sleeper edge fillets and local hand-finished recesses;
- exact drain corner radii/batter;
- exact cable-rack/luminaire products.

### Safe simplifications for v1
- central drain = 0.9 m rectangular open trough, depth 0.55 m;
- detailed KD-65 plate may temporarily use a tagged envelope mesh;
- historical cover may use a tagged modern silhouette fallback;
- cast-iron lining may use smooth 5.5/5.1 shell + 1.0 m ring seams, but **must not fake segment ribs/bolts as series-accurate LOD0**.

This separation is intentional: synthetic LiDAR should know which returns come from source-backed geometry and which come from a visual fallback.
