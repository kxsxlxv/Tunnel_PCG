# Moscow Metro era / section / construction-archetype map

Research snapshot: 2026-09-19.

Purpose: prevent historically impossible combinations in procedural generation.

This is an evidence map, not a complete kilometre-by-kilometre tunnel inventory. A section is assigned an exact archetype only when a source supports that assignment.

## 1. 1930s: first-stage construction was not one tunnel type

Official Moscow Metro history:
- first stage opened 15 May 1935;
- Sokolniki–Park Kultury with the Okhotny Ryad–Smolenskaya branch;
- total first-stage length 11.2 km.

Source ID: S029.

Engineering literature describes **wide use of monolithic concrete lining** on first-stage Moscow tunnels constructed mainly by mining methods.

Source ID: S026.

At the same time, a dedicated early precast-RC system was used in Moscow in 1932–1937:
- documented length: about 3750 running metres;
- D_out = 6.5 m;
- D_in = 5.5 m;
- 12 identical rectangular RC blocks;
- block/ring width along tunnel = 0.75 m;
- block thickness = 0.50 m;
- no tensile ties in block/ring joints in the described system;
- adjacent rings were laid with a half-block stagger;
- internal glued waterproofing plus supporting RC shell.

Archetype:
`RC_BLOCK_EARLY_6500_5500_12SEG_R075`.

Source IDs: S024, S026.

**Generator rule:** `ERA_1930S_FIRST_STAGE` must allow both monolithic/mined and early precast-RC families. Opening year alone cannot select the physical lining.

---

## 2. Second construction stage: exact early cast-iron family

A 1938 Moscow construction publication gives an unusually complete running-tunnel ring:

- D_out = **6000 mm**;
- ring width = **750 mm**;
- **12 segments**:
  - 9 normal;
  - 2 adjacent to key;
  - 1 key;
- **67 bolts** joining one ring to the next;
- **5 bolts Ø30 mm** at each described segment connection;
- flange/rib height = **200 mm**;
- back-plate thickness = **35 mm**.

Later technical literature also gives approximately 130 mm bolt length for the 6 m cast-iron family.

Archetype:
`CAST_IRON_6000_R075_12SEG_EARLY`.

Source IDs: S025, S007.

This family creates a very distinctive LiDAR signature:
- 0.75 m circumferential seam cadence;
- dense radial ribs;
- repeated bolt heads/nuts;
- N/C/K asymmetry at the crown.

---

## 3. Mature classic cast-iron family

Standard technical family:
- D_out = 5.5 m;
- D_in = 5.1 m;
- ring width = 1.0 m;
- traditional flange/rib height = 0.20 m;
- later lightweight flange/rib height = 0.15 m;
- Ø27 x ~120 mm fastening family.

Archetypes:
- `CAST_IRON_5500_R1000`;
- `CAST_IRON_5500_LIGHT`.

Source ID: S007.

A current/recent national construction-cost reference also retains a close deep-tunnel cast-iron family:
- D_out about 5.49 m;
- ring width 1.0 m;
- ring mass 5.443 t;
- caulked joints and grout injection behind lining.

This is evidence that “5.5 m cast iron” must still be treated as a real dimensional family, not only a historical visual style.

---

## 4. Moscow precast RC: 6.1 / 5.6 m, ten-block family

A 1975 engineering text explicitly describes a Moscow Metro precast RC running-tunnel lining:

- D_out = **6.1 m**;
- D_in = **5.6 m**;
- ring width = **1.0 m**;
- **10 blocks**, identical in form/size;
- block volume = **0.46 m³**;
- block mass = **1.15 t**;
- historical concrete grade 400;
- working reinforcement Ø16 mm;
- no permanent bolted connection between individual blocks;
- during erection blocks are held by steel pins Ø22 mm placed in radial-end holes.

Archetype:
`RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000`.

Source ID: S026.

This is geometrically very different from both cast-iron tubing and modern high-precision TBM segments.

---

## 5. 1950s–1970s: industrialized RC transition

Historical technical literature records broad development/adoption of precast RC metro linings in Moscow from the 1950s.

Named development areas include:
- Kaluzhsky radius;
- Frunzensky radius;
- Zhdanovsky radius.

Multiple series existed; some shallow/open-cut work also used prefabricated roofs/walls/full-section experiments.

Do **not** map one generic RC ring to an entire named radius.

Applicable families include:
- 6.1/5.6 m ten-block Moscow family;
- unified compressed/flexible RC blocks;
- ribbed RC tubing;
- solid RC blocks;
- rectangular precast/open-cut structures.

---

## 6. Unified compressed RC-block family

Historical technical description:
- ring begins with invert block plus normal blocks;
- one documented system uses six normal blocks + one invert block + expanding/fixing inserts;
- compressed against surrounding ground;
- exact diameter/topology depends on series.

Archetype:
`RC_BLOCK_UNIFIED_6N_1INVERT_EXPANDING`.

Source ID: S021/S008 technical literature set.

Keep unknown dimensions as null.

---

## 7. Monolithic-pressed concrete: confirmed Moscow examples

### Krasnopresnensky radius
An industry article from 1972 discusses an experimental/working monolithic-pressed-concrete application on the Krasnopresnensky radius, especially in sandy ground.

Source ID: S036.

### Nakhimovsky Prospekt – Sevastopolskaya
A primary industry article in “Metrostroy”, 1982, states:

- **left tunnel**: TShB-7 mechanized complex; monolithic-pressed concrete lining;
- **right tunnel**: ShNE-1 excavator-type shield as part of KM-42; assembled lining system.

A later technical source gives the TShB-7 family:
- shield diameter about **5.9 m**;
- intended monolithic-pressed lining internal diameter about **5.2 m**.

Archetype:
`MONOLITHIC_PRESSED_TSHB7_ID5200`.

Source IDs: S027, S028.

**Critical PCG consequence:** two tunnels of the same interstation section may legitimately use different lining systems. Store lining family per track/tunnel, not per station pair.

---

## 8. Modern high-precision single-track RC segment families

Do not collapse modern “6 m TBM” work into one geometry.

Documented reference families include:
- Moscow NFM: 5.6/5.1 m; 1.4 m ring; 8 blocks;
- Moscow Herrenknecht transition family: 6.0/5.4 m; 1.4 m ring; 7 blocks;
- BCL engineering family: nominal 6 m shield class; ring 1.4 m; 6 blocks; ~21 t;
- national reference family: 5.65/5.15 m; ring concrete volume 5.93 m³;
- 2026 national reference family: 6.0/5.4 m; ring concrete volume 7.615 m³.

Source IDs: S012, S013, S017, S032, S033.

These sources prove multiple contemporary geometries coexist. TBM nominal diameter is not enough to select lining ID/OD.

---

## 9. Modern large-diameter two-track shield tunnels

Official Moscow sources confirm large shields >10 m for one circular two-track tunnel.

Confirmed examples:
- shield “Lilia” on BCL;
- “Lilia” previously used on Nekrasovskaya-line construction;
- Rublyovo-Arkhangelskaya line, where official Moscow material states diameter >10 m and explicitly says this class is intended for two-track tunnels.

On western BCL:
- “Lilia” built the >2.2 km two-track Terekhovo–Kuntsevskaya tunnel;
- Terekhovo/Kuntsevskaya stage is explicitly described as using 10 m shields and two-track tunnels.

Source IDs: S030, S031, S037.

Engineering BCL family data:
- ring width 1.8 m;
- 6 blocks;
- ring mass ~70 t.

Source ID: S013.

---

## 10. Current appearance modifiers independent of lining age

Current SP changes what an old structural tunnel can look like after modernization.

Examples:
- all lining types: light-coloured waterproof noncombustible coating for **50 m from station ends**;
- current evacuation signs;
- current cable systems;
- modern lighting;
- modern track renewal / LVT may coexist with an older lining where a project has renewed permanent way.

Therefore store:
```
civil_construction_era
track_renewal_era
services_renewal_era
surface_condition_era
```
as independent attributes.

---

## 11. Era presets

### ERA_1930S_FIRST_STAGE
Possible:
- mined monolithic concrete;
- early 6.5/5.5 RC block system;
- early open-cut rectangular concrete.

### ERA_LATE_1930S_1940S_DEEP
Possible:
- 6.0 m / 0.75 m / 12-segment cast iron;
- historical service infrastructure.

### ERA_1950S_1970S
Possible:
- classic 5.5/5.1 cast iron;
- 6.1/5.6 ten-block Moscow RC;
- unified/experimental RC systems;
- open-cut rectangular structures.

### ERA_1970S_1990S
Possible:
- cast iron and RC families;
- monolithic-pressed sections;
- mature timber-in-track-concrete permanent way.

### ERA_2000S_2020S_SINGLE_TRACK_TBM
Possible:
- multiple high-precision segment families;
- modern gasketed joints;
- modern track/services according to project.

### ERA_2010S_2020S_LARGE_2TRACK_TBM
Possible:
- large circular two-track segmental lining;
- central/side evacuation geometry;
- dense modern cable/services installation.

---

## 12. Selection hierarchy

For procedural generation choose geometry in this order:

1. exact tunnel/track construction source;
2. exact interstation section source;
3. named project/TBM/lining family;
4. construction-era + engineering method evidence;
5. generic era fallback only when explicitly permitted.

Schema:
```
LineSectionTrack {
  line,
  station_from,
  station_to,
  track_or_direction,
  construction_year_range,
  opening_year,
  structural_archetype,
  track_archetype,
  services_era,
  evidence_level,
  source_ids[]
}
```

Unknown assignment remains null.
