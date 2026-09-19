# Moscow Metro era / section / construction-archetype map

Purpose: prevent historically impossible combinations in procedural generation.

This is not yet a complete kilometer-by-kilometer inventory. It is a growing set of **confirmed anchor examples** and era constraints.

Confidence:
- B = official Moscow/project publication;
- C = engineering/history technical literature.

---

## 1. 1932–1937: early reinforced-concrete block running tunnels

A historical engineering source on precast RC tunnel linings describes approximately **3750 running metres** of Moscow running tunnels built in 1932–1937 with an early RC-block system:

- outside diameter: **6.5 m**;
- inside diameter: **5.5 m**;
- radial block thickness: **0.50 m**;
- ring width: **0.75 m**;
- **12 identical RC blocks per ring**;
- internal glued waterproofing with a supporting RC shell in the described system.

This is a major correction to any assumption that the earliest Moscow deep running tunnels were all cast iron.

Add archetype:
`RC_BLOCK_EARLY_6500_5500_12SEG_R075`.

Source:
historical tunnel-lining engineering literature, searchable archive:
https://ru.djvu.online/

The first Moscow Metro stage opened in 1935: Sokolniki–Park Kultury plus the Okhotny Ryad–Smolenskaya branch. Official historical source:
https://www.mosmetro.ru/press/history/

Applicability must still be established per exact interstation section before assigning this 6.5/5.5 family to a specific generated route.

---

## 2. Second construction stage: 6.0 m cast-iron tubing

Historical engineering literature identifies the second Moscow construction stage as the first Moscow use of cast-iron tubing for running tunnels.

Documented early family:
- outside diameter: **6.0 m**;
- ring width: **0.75 m**;
- **12 tubings per running-tunnel ring** in a 1950s engineering description;
- Ø30 mm-class ring bolts in the documented 6 m lining family.

In 1937 Moscow construction reportedly received large numbers of domestic shields:
- 6 m-class shields for running tunnels;
- 9.5 m-class shields for station tunnels.

This establishes a distinct late-1930s/1940s deep-running-tunnel morphology:
- dense 0.75 m ring rhythm;
- cast-iron ribs/bolts;
- 12-element ring topology with non-identical key/adjacent elements.

Archetype:
`CAST_IRON_6000_R075_12SEG_EARLY`.

---

## 3. Post-war / mature 5.5 m cast-iron family

The classic 5.5/5.1 m, 1.0 m ring cast-iron family became a standard metro running-tunnel solution.

Use:
`CAST_IRON_5500_R1000`.

Do not assume a single year of transition from 6.0 m to 5.5 m across all lines. Construction method depends on geology, project and build period.

---

## 4. 1950s–1960s: broad adoption of precast RC lining

Historical engineering literature reports active Moscow introduction/development of precast RC tunnel linings from the 1950s.

Examples/scope named in technical literature include many sections on:
- Kaluzhsky radius;
- Frunzensky radius;
- Zhdanovsky radius.

In 1956 precast RC roof structures were introduced over monolithic walls on some one-track tunnels and crossover chambers of the Frunzensky radius.

From 1958, serial precast RC solutions for two-track running tunnels were developed/applied, with multiple series.

Experimental full-section precast tunnel sections were used in Moscow:
- Frunzensky radius: around **1958**;
- Zhdanovsky radius: around **1964**.

These references establish era/morphology but do not prove that every tunnel on the named radius used the same series.

---

## 5. Unified RC-block circular family

A historical source describes a unified flexible/hinged RC running-tunnel lining with approximately:
- inside diameter: **5.1 m**;
- radial thickness: **0.20 m**;
- major block count described as **7** in the cited construction system;
- special insert/expansion components.

The textual source is not sufficiently unambiguous to freeze every segment class/count relation in LOD0, so exact angular topology remains unresolved.

Use a guarded archetype rather than equal wedges:
`RC_BLOCK_UNIFIED_ID5100_T200`.

---

## 6. Monolithic-pressed concrete: confirmed Moscow use

Monolithic-pressed lining is confirmed in Moscow construction literature and was used where shield tail void was filled by pressing fresh concrete directly against ground.

Historical typical geometry:
- internal running-tunnel diameter around **5.5 m**;
- lining thickness around **0.37–0.40 m**.

### Krasnopresnensky radius
Technical literature describes use of monolithic-pressed concrete and RC compressed against ground in unstable sandy ground on shallow/dependent sections of the Krasnopresnensky radius.

### Serpukhovsky radius: Nakhimovsky Prospekt – Sevastopolskaya
A particularly valuable paired example:
- one running tunnel was constructed with a **TShB-7** shield using monolithic-pressed lining;
- the opposite tunnel used a different shield/construction method and assembled reinforced-concrete lining;
- construction dates in the cited history are around the early 1980s.

This means two tunnels of the **same interstation section can legitimately have different lining morphologies**.

The route generator must support per-track archetype assignment.

---

## 7. 2000s–2020s: modern high-precision segmental RC

Modern Moscow mechanized tunneling uses high-precision precast RC rings with elastic sealing gaskets.

Known project-family examples already stored:
- NFM 5.6/5.1 m, 1.4 m ring, 8 blocks;
- Herrenknecht 6.0/5.4 m, 1.4 m ring, 7 blocks, documented as a transition-tunnel family in a Moscow 2012 publication;
- BCL 6 m-class single-track family, 1.4 m ring, 6 blocks in Mosinzhproekt engineering material.

Do not map the 2012 ring families to a specific line solely from date/TBM manufacturer until a project source explicitly links them.

---

## 8. Modern ~10 m two-track TBM tunnels

Official Moscow sources confirm the modern move from traditional ~6 m single-track shields to ~10 m shields producing one two-track circular tunnel.

Confirmed use includes:
- Nekrasovskaya-line construction generation;
- Bolshaya Koltsevaya Line sections;
- later Rublyovo-Arkhangelskaya construction with the large-diameter shield “Lilia”.

For BCL engineering material:
- 10 m-class shield;
- ring width: **1.8 m**;
- **6 blocks**;
- ring mass about **70 t**.

Official Moscow construction reports large-diameter two-track tunnels including BCL underwater sections and western BCL construction.

Visual morphology:
- two tracks inside one circle;
- central/side evacuation-service surface depending on project;
- much wider equipment distribution than paired 5.1 m single-track tunnels;
- smooth high-precision RC segments.

---

## 9. Generation-era guardrails

Recommended top-level era presets:

### ERA_1930S_FIRST_STAGE
Allowed:
- early RC block 6.5/5.5 family where section-confirmed;
- open-cut monolithic/RC structures;
- period-specific rail/services.

Disallow by default:
- modern LVT;
- modern segment gasket/pocket morphology;
- modern 10 m two-track rings.

### ERA_LATE_1930S_1940S_DEEP
Allowed:
- early 6.0 m cast-iron / 0.75 m ring family;
- period cable/service morphology.

### ERA_1950S_1970S
Allowed:
- classic 5.5 m cast iron;
- legacy RC blocks;
- experimental/full-section precast;
- rectangular open-cut;
- timber-in-concrete track.

### ERA_1970S_1990S
Allowed:
- classic cast iron;
- improved RC block/tubing systems;
- monolithic-pressed sections;
- timber/concrete permanent way plus period-specific modernization.

### ERA_2000S_2020S_SINGLE_TRACK_TBM
Allowed:
- high-precision RC segmental rings;
- modern elastomer gaskets;
- modern cable systems;
- timber or modern RC/LVT track depending on project.

### ERA_2010S_2020S_LARGE_2TRACK_TBM
Allowed:
- ~10 m-class two-track segmental circles;
- modern evacuation/service geometry;
- modern LVT/ballastless systems where project-confirmed.

---

## 10. Important rule for procedural realism

A line opening year is **not sufficient** to choose tunnel geometry.

Selection hierarchy:
1. named interstation construction source;
2. exact tunnel/track direction if known;
3. construction period;
4. geology / construction method;
5. generic era fallback only if no stronger data exists.

Store:
```
LineSectionTrack {
  line,
  station_from,
  station_to,
  direction_or_track,
  opening_year,
  construction_year_range,
  lining_archetype,
  evidence_level,
  source_ids[]
}
```

Unknown exact assignment must stay `lining_archetype: null` rather than being guessed.
