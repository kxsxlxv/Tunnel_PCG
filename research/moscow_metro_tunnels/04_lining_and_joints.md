# Lining topology, joints and LiDAR-visible construction details

## 1. Cast-iron tubing — classic Moscow family

Technical source:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/

### 5.5 / 5.1 m standard ring
- ring pitch: 1.000 m;
- outside diameter: 5.500 m;
- inside diameter: 5.100 m;
- radial depth / flange height: 0.200 m;
- fastening bolt: nominal Ø27 mm, ~120 mm long;
- bolt holes: 4–6 mm larger than bolt diameter.

### Element anatomy

A cast-iron tubing is a ribbed box:
- curved back plate / skin;
- two radial/longitudinal flanges;
- two circumferential flanges;
- caulking rebates at inward-facing flange edges;
- one circumferential stiffening rib;
- typically 2–3 radial stiffening ribs depending on tubing type;
- grout-injection opening in the back, closed by a threaded metal plug;
- bolt holes in flanges.

The narrow key tubing has no radial stiffening ribs.

### Ring topology

Ring has:
- normal elements N;
- two elements adjacent to the key C;
- top key/closing element K.

Do not fake the ring with equal angular wedges if producing LOD0. The key and adjacent pieces are wedge-shaped and have different radial-joint geometry.

Exact central angles / element counts vary by ring type and need series-specific drawings before claiming survey-grade angular topology.

### Curves

Legacy cast-iron curved alignment was obtained using wedge-shaped cast-iron packing pieces with bolt holes, giving variable effective ring width.

Generator consequence:
- do not bend a 1 m ring mesh continuously;
- place planar rings and create small angular changes through wedge spacers / tapered ring interfaces.

This is essential because a synthetic LiDAR scan along a curve can resolve the stepped ring-joint orientation.

### Lightweight 5.5 m type
Historical source:
https://www.metro.ru/library/metropoliteny/233/

- D_out: 5.5 m;
- inward flange height reduced from 200 to **150 mm**;
- lower part may use a flat combined cast-iron / reinforced-concrete invert element.

This must be a distinct mesh archetype.

---

## 2. Early Moscow 6.0 m cast-iron tubing

Historical source:
https://www.metro.ru/library/metropoliteny/233/

First use:
- Moscow Metro second construction stage;
- D_out: **6.0 m**;
- ring pitch: **0.75 m**.

Later 6.0 m cast-iron variants also existed; do not assume every 6.0 m ring has the early 0.75 m pitch.

Technical source for fastening:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/

For 6 m lining:
- bolt Ø30 mm;
- bolt length ~130 mm.

A reference photograph of a wartime / early-style cast-iron tunnel clearly shows the dense 0.75 m ring rhythm:
https://russos.livejournal.com/1486834.html

---

## 3. Legacy precast reinforced-concrete lining

Technical sources:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/
https://www.metro.ru/library/metropoliteny/233/

Introduced in Moscow from the 1950s as a major replacement for cast iron.

### Face variants
- solid block: smooth inside face;
- ribbed block/tubing: visibly ribbed inside face;
- flat-joint reinforced-concrete tubing with bolted connections;
- flat invert block replacing the bottom tubing in some systems.

For solid-block lining the historical reference states ring dimensions analogous to the classic cast-iron ring family.

### Joint variants
Solid blocks:
- cylindrical convex/concave longitudinal mating surfaces;
- rings can be assembled without longitudinal inter-ring bolting;
- adjacent invert blocks can be tied with metal pins.

Ribbed blocks:
- circumferential flanges can carry assembly studs connecting rings.

Other variants use:
- flat joints;
- bolted ties;
- caulking grooves;
- three-slot / “трехштрабная” niches for inter-ring bolting.

### Unified compressed lining
A historical Moscow technical source describes a ring system based on:
- six normal blocks;
- one invert block;
- special expanding/fixing inserts.

Source:
https://ru.djvu.online/file/ZBmH1AcNEUBWG

This is a useful separate archetype:
`RC_BLOCK_UNIFIED_6N_1INVERT_EXPANDING`.

Do not infer this segmentation for every Moscow RC-block tunnel.

---

## 4. Monolithic concrete and monolithic-pressed lining

Source:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/

Typical metro running-tunnel internal diameter:
- **5.5 m**.

Historical monolithic-pressed lining references give approximate thickness:
- ~0.37–0.40 m.

Construction morphology for LiDAR:
- much smoother cylinder than cast iron / precast blocks;
- formwork-cycle / concreting seams;
- no repeated segment bolts;
- local injection / construction holes where project-specific;
- repair patches and seepage deposits are highly visible in real scans.

---

## 5. Modern high-precision segmental RC rings

Current SP requires high-precision RC segments to include grooves for elastic sealing gaskets.

Source:
https://rags.ru/documents/prod/metodika/0/sp_63529.html

### Standard modern 6.0 / 5.4 m family
2025 national metro construction cost norm:
- D_out: **6.0 m**;
- D_in: **5.4 m**;
- radial thickness: **0.30 m**;
- ring concrete volume: **7.615 m³**;
- high-precision precast RC segments.

Source:
https://rags.ru/documents/prod/normativy/0/ntss_91321.html

This is stronger evidence for a contemporary 6.0/5.4 family than a generic “6 m shield” label.

### Moscow 2012 Herrenknecht transition-tunnel ring
Official Moscow price publication:
- 6.0 / 5.4 m;
- ring width: **1.4 m**;
- **7 blocks/ring**;
- PHOENIX rubber sealing set: 7 pieces;
- grout/lifting threaded insert: 7;
- polyethylene dowels: 26.

Source:
https://www.mos.ru/upload/documents/oiv/inf_ceny_2012.pdf

### Moscow 2012 NFM running-tunnel ring
Same source:
- D_out: **5.6 m**;
- D_in: **5.1 m**;
- thickness: **0.25 m**;
- ring width: **1.4 m**;
- **8 blocks/ring**.

### Moscow BCL / 6 m-class infographic
Mosinzhproekt engineering publication:
- nominal shield class: 6 m;
- ring width: **1.4 m**;
- ring: **6 blocks**;
- ring mass: ~21 t.

### Moscow BCL / 10 m-class two-track infographic
Same publication:
- nominal shield class: 10 m;
- ring width: **1.8 m**;
- ring: **6 blocks**;
- ring mass: ~70 t.

Source:
https://mosinzhproekt.ru/wp-content/uploads/2023/03/is_01-full_.pdf

Conclusion:
segment count and finished diameter are project-family parameters; never derive one from TBM nominal diameter.

---

## 6. Modern segment mesh details

LOD0 segment should support:
- inner cylindrical face;
- radial joint faces;
- ring joint faces;
- gasket groove near extrados perimeter;
- bolt/dowel pockets where visible from interior;
- lifting / grout socket with plug;
- shallow casting chamfers;
- segment ID / recess as optional embossed geometry;
- joint-gap width parameter;
- ring-to-ring stagger / rotation.

Gasket itself is usually hidden in the joint; do not expose a large rubber strip on the intrados unless photograph/project drawing supports it.

### Ring sequence
Store every ring instance as:
```
RingInstance {
  s_center,
  width,
  taper_vector,
  roll_angle,
  segment_family,
  segment_index_rotation,
  build_tolerance
}
```

Modern universal-ring systems can use ring rotation to steer the tunnel. Do not model curvature by smoothly deforming each segment.

---

## 7. Open-cut rectangular linings

Historical technical source:
https://www.metro.ru/library/stroitelstvo_metropolitenov/482/

Families:
- precast wall + roof + invert blocks;
- monolithic reinforced-concrete frame;
- diaphragm-wall (“wall in ground”) side walls plus roof/floor structures;
- full prefabricated frame sections.

One documented full prefabricated section:
- longitudinal length: **1.5 m**;
- external height: **5.0 m**;
- external width: **4.4 m**;
- mass: **13.3 t**.

The same source shows one-track and two-track assemblies made from full sections. Treat 4.4 x 5.0 m as a documented product-family section, not a universal Moscow rectangular tunnel envelope.

LiDAR-visible details:
- section-to-section joints at 1.5 m pitch;
- wall/roof casting joints;
- waterproofing protection only if exposed;
- cable anchors / inserts;
- local beam seats;
- central column only for multi-span families;
- flat slab / drainage geometry.

---

## 8. Data confidence policy

For every lining family store:
- `geometry_confidence`: A/B/C/D;
- `segment_topology_confidence`;
- `project_applicability`;
- `source_year`;
- `known_moscow_use`.

Never use a generic textbook segment count as an exact Moscow ring unless a Moscow project/series source confirms it.
