# Track, permanent way, drainage and contact rail

Research snapshot: 2026-09-19.

Primary current source:
СП 120.13330.2022 «СНиП 32-02-2003 Метрополитены», current consolidated text including changes through 2026:
https://meganorm.ru/mega_doc/norm_update_01052026/metodika/0/sp_120_13330_2022_svod_pravil_metropoliteny_snip_32-02-2003.html

Other sources are identified per section.

---

## 1. Local coordinate convention

Use:
- +X: increasing chainage;
- +Y: left looking in +X;
- +Z: local vertical before cant;
- z = 0: UGR, the tangent plane through both running-rail heads;
- y = 0: track centerline.

Apply cant by rotating the whole track frame around +X.

Do not use the lining center as track origin.

---

## 2. Track gauge

Current SP values:

| Curve radius | Gauge |
|---|---:|
| straight and R >= 1200 m | 1520 mm |
| 600 < R < 1200 m | 1524 mm |
| 400 < R <= 600 m | 1530 mm |
| 125 < R <= 400 m | 1535 mm |
| 100 < R <= 125 m | 1540 mm |
| R <= 100 m | 1544 mm |

Current tolerance:
- nominal deviation <= 2 mm;
- absolute operating limits: 1512–1548 mm.

Important correction to Stage-1 starter data: the <=100 m class exists and is 1544 mm.

Implementation:
```
gauge = gauge_from_curve_radius(R)
rail_inner_working_faces = +/- gauge/2
```

Because gauge is measured between inner working faces of rail heads, rail-section extrusion must be offset using actual head geometry; do not place rail profile centerlines at +/- gauge/2.

For two-track sections with intertrack < 6.5 m, the SP requires both tracks in a curve to use the same gauge determined from the radius of the intertrack-setting axis.

---

## 3. Rail types

Current metro design supports R50 and R65.

ГОСТ Р 51685-2022 nominal rail-section dimensions:

| Dimension | R50 | R65 |
|---|---:|---:|
| overall height H | 152.00 mm | 180.00 mm |
| web height h | 83.00 mm | 105.00 mm |
| head width b | 71.59 mm | 74.59 mm |
| base width B | 132.00 mm | 150.00 mm |
| web thickness e | 16.00 mm | 18.00 mm |
| base-flange edge height m | 10.50 mm | 11.25 mm |

Primary standard:
https://protect.gost.ru/gost/details/8086c377-c8fe-49f0-9569-7e5c334554c3

Readable values:
https://base.garant.ru/406844406/

For LiDAR-grade geometry:
- use the full ГОСТ profile with head and fillet radii, not a rectangle/I-beam approximation;
- Stage 3 should vectorize Appendix Г, especially Fig. Г.2 for R65, to an exact profile spline.

Historical Moscow running tunnels commonly use R65 in later service, but the generator must support R50 because both the current metro standards and legacy clearances distinguish them.

---

## 4. Sleeper / support archetypes

### 4.1 Legacy wooden sleepers embedded in track concrete

Historical Moscow/USSR metro construction reference:
https://www.metro.ru/library/stroitelstvo_metropolitenov/524/

Documented geometry:
- sleeper length on straight track: **2.75 m**;
- sleeper length on curves: **2.65 m**;
- cross-section: **250 x 160 mm**;
- pine timber, impregnated with electrically nonconductive preservative;
- central drainage channel below sleepers: **0.7–0.9 m** wide;
- minimum concrete beneath sleeper historically: **0.20 m**;
- track-concrete surface historically slopes **0.03** toward the drain.

Current SP retains wooden under-rail bases as a valid construction and requires B25 or stronger track concrete.

Current main-track sleeper count on concrete from Table 5.16 is in the 1680/1840 per km classes depending on alignment; historical literature gives a broader 1680–2000 per km range.

Useful procedural pitch approximations:
- 1680/km -> 0.5952 m;
- 1840/km -> 0.5435 m;
- 2000/km -> 0.5000 m.

Do not use a perfectly constant pitch if reproducing a surveyed legacy tunnel; allow millimeter/centimeter-scale installation variation.

### 4.2 Wooden short sleepers
Current SP:
- main track within station platform limits: **0.9 m**;
- station track in inspection pits: **0.75 m**.

### 4.3 Modern LVT-style RC half-blocks / blocks in elastic boots

Official Moscow Transport description:
https://transport.mos.ru/mostrans/all_news/110412
https://transport.mos.ru/mostrans/all_news/112173

Construction:
- reinforced-concrete block / half-sleeper;
- elastic pad;
- rubber boot;
- assembly cast directly into unreinforced or structural track concrete;
- rails fixed to individual blocks.

Current SP explicitly provides for reinforced-concrete blocks with elastic elements in boots.

For the LiDAR mesh, the visible geometry should include:
- exposed upper face of each concrete block;
- rail-fastening plate/clips/bolts;
- rubber-boot rim where visible above concrete;
- recess / gap around block if construction leaves it visible;
- longitudinal drain.

A Russian utility-model description of the rubber boot confirms the LVT arrangement:
https://patents.google.com/patent/RU186427U1/ru

---

## 5. Track-concrete geometry

Current minimum track-concrete values from SP Table 5.18 for wooden under-rail bases include:
- typical minimum under the relevant rail locations: **160 mm**;
- special inner-rail/canted condition shown as **100 mm** in the table.

The procedural model should therefore not assume that the visible track slab is a constant-depth horizontal extrusion.

Generate:
- under-rail concrete;
- local crossfall toward drain;
- central drain / channel;
- localized shoulders around sleepers / LVT blocks;
- curve cant geometry.

---

## 6. Counterrails

Current SP:
- on underground main-track curves R < 300 m: provide guard/counterrail system;
- installed inside the gauge along the inner running rail;
- underground counterrail type must correspond to the running-rail type.

ГОСТ equipment clearance:
- rail-to-counterrail groove >= **42 mm**;
- transition to **90 mm** at the beginning and end.

Thus add an alignment event:
`COUNTER_RAIL_ZONE(start_s, end_s, curve_inside_side, rail_type)`.

---

## 7. Contact / third rail

### Electrical / placement rules

Current SP:
- lower current collection;
- contact rail enclosed by an electrically insulating protective cover;
- normally on the **left side in direction of train movement**;
- may be moved right at switches, crossovers and special cases;
- in two-track tunnels prolonged right-side placement is permitted;
- on underground curves R < 200 m it is placed on the **outside of the curve**;
- at island/service platforms it is placed under the platform.

### Exact operating geometry

Longstanding Russian metro operating geometry:
- working surface of contact rail: **+160 mm above UGR**;
- tolerance: +/-6 mm;
- contact-rail axis to the **inner face of the nearest running-rail head**: **690 mm**;
- tolerance: +/-8 mm.

Historical PTE source:
https://ru.djvu.online/file/cs51hfxUuUfHk

Readable secondary copy:
https://info.wikireading.ru/263327

This geometry is stable across Russian metro practice and should be the default physical placement for the Moscow archetypes unless a project drawing overrides it.

Implementation, if contact rail is on left:
```
nearest_running_rail_inner_face_y = +gauge/2
contact_rail_axis_y = nearest_running_rail_inner_face_y + 0.690
contact_working_surface_z = +0.160
```

Sign convention must follow the chosen +Y direction.

### Contact-rail supports

Current SP:
- ordinary bracket pitch: **4.5–5.4 m**;
- pitch is reduced on demanding alignment conditions;
- on switches/crossovers using elastic elements in boots: **2.2–2.75 m**.

Historical construction norms give the older practical range 4.5–5.5 m.

Do not synchronize every contact-rail bracket to lining-ring seams; treat the systems as independent periodic chains.

### Rail piece / strand behavior

Historical construction norm:
- special contact-rail profile;
- traditional piece lengths: **12.5 m** and **25 m**;
- mass: **51.79 kg/m**.

Source:
https://internet-law.ru/documents/prod/vnir_vedomstvennye-normy-i-rascenki/0/vnir_66174.html

Modern construction uses welded strands, so exposed joints depend on era.

### Air gaps and end ramps

Current SP:
- main-track accepting end ramp: **1:30**;
- main-track releasing end ramp: **1:25**;
- station/connecting tracks: **1:25**;
- metal-end gap crossed by one car's collectors: <= **10 m**;
- non-crossed insulating air gap: >= **14 m**;
- a contact-rail length including end ramps normally >= **18.7 m**;
- constrained case may be >= **12.5 m**, with anti-creep fastening at every bracket.

These end ramps are large, distinctive LiDAR objects and should be explicit event geometry rather than texture/LOD detail.

---

## 8. Fastenings and visible secondary details

Legacy wooden-base track:
- metal base plates;
- path screws;
- elastic pads on many later configurations;
- optional extended eight-hole plates on tight curves R <= 400 m.

Current SP requires electrical isolation from tunnel/track concrete.

For procedural generation split the assembly:
```
RUNNING_RAIL
  -> rail_profile
  -> base_pad
  -> baseplate
  -> clips_or_screws
  -> sleeper_or_block
  -> boot/pad (modern LVT)
  -> track_concrete
```

Use instance geometry for every fastening for close-range LiDAR. For long simulation runs provide LOD levels:
- LOD0: full clip/bolt geometry;
- LOD1: baseplate + simplified bolts;
- LOD2: sleeper/block and rail only.

---

## 9. Important stochastic parameters for synthetic LiDAR

Geometry randomization should be bounded and physically plausible:
- sleeper/block longitudinal placement jitter;
- fastener yaw / millimeter offset;
- weld seam or rail-joint presence by era;
- drain sediment depth;
- concrete repair patches as shallow geometry, not only texture;
- cable sag between supports;
- local protective-cover deformation on contact rail;
- small ring-installation offsets.

Do not randomize normative track gauge, contact-rail position, or clearance envelope beyond documented installation/operating tolerances unless simulating defects.
