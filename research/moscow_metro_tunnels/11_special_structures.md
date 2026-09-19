# Special structures and transition geometry traversed by trains

Scope:
structures that interrupt the ordinary running-tunnel archetype and materially alter the train/LiDAR environment.

Sources:
- current SP 120.13330.2022 through 2026;
- historical metro construction literature:
  https://www.metro.ru/library/stroitelstvo_metropolitenov/
  https://www.metro.ru/library/metropoliteny/

---

## 1. Cross passages between paired single-track tunnels

### Current requirement
After current amendments, cross passages between single-track running tunnels are provided according to the design assignment / evacuation solution rather than by one universal fixed longitudinal spacing.

Current minimum clear dimensions:
- passage width: **>=1.5 m**;
- passage height: **>=2.0 m**;
- door clear opening width: **>=1.0 m**.

Doors in relevant fire/smoke barriers must be fire-rated/smoke-gas-tight as specified and capable of withstanding alternating piston-effect pressure loads.

### Historical spacing chronology

For era-correct generation, do not use current wording retroactively.

Earlier editions/design practice included:
- technological cross passages commonly specified every **500–700 m**;
- a later edition used a maximum spacing around **1000 m**;
- current amended wording makes location project/evacuation dependent.

Store cross-passage placement rule by `standard_era`.

### Physical intersection geometry
A cross passage should not be represented as a simple boolean cylinder through the lining.

Model:
1. local lining opening / cut ring;
2. reinforced portal/frame;
3. short transition throat;
4. passage lining;
5. door/frame;
6. threshold/drainage;
7. local cable/lighting/sign rerouting;
8. water/fire-service branches when documented.

For paired circular segmental tunnels, support a ring-specific opening family or cast-in-place reinforced collar.

---

## 2. Ventilation/circulation connections

Ventilation tunnels should normally connect to running tunnels from the side.

When one ventilation connection serves both single-track tunnels, it may connect through a cross passage only when its free section is justified by calculation.

A ventilation tunnel joining a cross passage normally approaches:
- from above;
- exceptionally from below when drainage requirements are solved.

### Anti-piston / circulation passages near shallow stations

Historical/current design generations used circulation cross passages near shallow stations to relieve piston pressure.

Documented design values include:
- first circulation opening around **70–120 m** from the platform end;
- free area around **40–50 m²**;
- second opening no more than around **250 m** from the first and at least one design train length away as required by the cited design generation;
- second free area around **20–30 m²**.

Later standards allow omission/optimization by calculation. Therefore these are historical/design-family presets, not universal present-day geometry.

---

## 3. Bellmouth / раструб

A bellmouth is a progressive enlargement of a running tunnel used at:
- bifurcations;
- transition between one two-track structure and two single-track tunnels;
- approach to crossover/switch chambers;
- branch/connection structures.

Construction literature commonly uses monolithic concrete or reinforced concrete for large-span/bellmouth sections.

### PCG representation

Do not use uniform radial scale along X.

Represent as a sequence of engineering cross-sections:
```
Bellmouth {
  entry_profile
  stations[]: [
    {s, profile_id, center_offset, invert_level}
  ]
  structural_family
}
```

Interpolate wall/lining surfaces between explicitly designed stations while preserving:
- track clearances;
- roof springing;
- invert/drain continuity;
- cable/service route continuity.

---

## 4. Crossover / switch chambers

When separate single-track tunnels require a crossover:
- a separate connecting tunnel may be needed;
- at the turnout / connecting-tunnel junction the running tunnel progressively widens;
- historical construction uses a sequence of short chambers with increasing span/length;
- the final widened section accommodates both the running route and the connecting branch.

These structures are frequently monolithic concrete/RC because ordinary circular rings cannot accommodate the required span.

### Required procedural decomposition
```
SWITCH_CHAMBER
  approach_transition
  turnout_track_geometry
  widened_structural_bays[]
  branch_portal
  connecting_tunnel
  drainage_transition
  third_rail_side/gap events
  evacuation_path transition
  cable rerouting
  lighting density change
```

Do not attempt to derive chamber span purely from track centerlines. A specific chamber family/drawing is required.

---

## 5. Pilot-tunnel construction morphology

Historical large-span chambers/bellmouths could be built using a pilot tunnel.

Technical literature describes:
- pilot tunnel convenient minimum diameter about **2.5 m**;
- metro applications often used **5.5 or 6.0 m** pilot lining with ~1 m ring width;
- pilot axis can coincide with final axis or sit around **0.5–1.0 m lower**;
- this method is practical for widened zones of order <=100–150 m length in the described construction context.

The final visible tunnel usually does not expose the entire pilot lining, but remnants/interfaces can affect:
- construction joints;
- local wall thickness;
- niches;
- geometry around widened chambers.

Use only for historical construction reconstruction.

---

## 6. Hermetic / pressure-gate zones

Civil-defense/hermetic gate zones can create distinctive tunnel geometry:
- thickened frame / bulkhead;
- door leaf recesses;
- rails/threshold structures;
- machinery cabinets;
- service doors;
- altered evacuation path;
- drainage changes;
- cable/pipe penetrations with sealed sleeves.

Current evacuation routing specifically requires safe passage around such obstacles.

Exact gate dimensions and placement are project-specific and can be security-sensitive in operational detail. For PCG, model generic visible geometry only from public engineering sources; do not infer non-public operational layouts.

---

## 7. TBM launch/reception chambers

Modern segmental tunneling requires:
- launch chamber;
- reception/dismantling chamber;
- local enlarged cut-and-cover or mined structure;
- transition rings / temporary frames;
- wall opening / seal assembly during construction.

For an operational-tunnel model, typical retained visible features may include:
- abrupt transition from segmental circle to monolithic chamber;
- ring termination;
- thick portal collar;
- rectangular chamber walls/roof;
- local equipment niches.

Store as `TBM_CHAMBER_TRANSITION`; exact dimensions are project-specific.

---

## 8. Portal / surface transition

Near surface portals:
- circular/mined structure may transition into rectangular open-cut structure;
- ballastless track may transition to another track form where project-specific;
- lighting level changes strongly over ~150 m;
- cable and drainage topology may change;
- weathering/water condition differs from deep tunnel.

This deserves a separate environmental-condition preset for LiDAR:
`PORTAL_DAYLIGHT_ADAPTATION_ZONE`.

---

## 9. Emergency exits

Current SP requires additional emergency-exit solutions for long interstation distances, including a rule around **3000 m between platform ends**, with project-specific exceptions/justification for some two-track arrangements.

Visible tunnel consequences:
- stair/shaft access portal;
- protected door;
- signs;
- brighter emergency lighting;
- local widening or side chamber;
- service cables/pipes.

Placement and exact shaft geometry must come from a named project source.

---

## 10. Special-structure event API

Recommended route schema:
```json
{
  "s_start": 1234.0,
  "s_end": 1290.0,
  "type": "BELL_MOUTH | CROSS_PASSAGE | SWITCH_CHAMBER | TBM_CHAMBER | PORTAL | HERMETIC_GATE_ZONE",
  "family_id": "...",
  "track_topology_before": "...",
  "track_topology_after": "...",
  "lining_override": "...",
  "third_rail_events": [],
  "service_reroutes": [],
  "source_id": "..."
}
```

Special structures always override ordinary periodic equipment generation inside their event range.
