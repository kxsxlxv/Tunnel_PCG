# Koltsevaya vertical-profile constraints

Research date: 2026-09-20.

This file separates **confirmed vertical facts** from values that are only station-depth references.

## Strongest public project evidence found

A Moscow Government historical-cultural expertise for the current Dostoevskaya construction explicitly lists a 2024 Mosinzhproekt design volume:

`ИМИП-МКЛ1-П-Г0201-ППО.02.01.00.ТРМ, Том 02.02.01`

The listed contents are:
- line plan 1:2000;
- line plan 1:500;
- longitudinal profile 1:2000 horizontally / 1:200 vertically.

The same published document lists a 2022 Mosgorgeotrest engineering-geodetic survey:
`50/1037-22-ИГДИ`.

This is important because it proves that an engineering-grade local line plan/profile and survey exist for the active Line-5 reconstruction zone. The public expertise PDF names the volumes, but this research pass has not located those standalone drawing/report volumes for download.

Source: Moscow Government expertise PDF, Appendix 1.

## Confirmed local profile condition

A 2026 Moscow Metro news archive, quoting the builder, states that the future Dostoevskaya station was planned during original Line-5 construction, therefore **the existing tunnels in the station zone have zero grade**. The same statement gives an existing construction depth of **more than 38 m**.

Use this as:
- a hard/strong **relative grade constraint** for the station-provision zone;
- a depth lower-bound/rough construction constraint.

Do **not** apply the zero grade to the full Novoslobodskaya–Prospekt Mira interstation. Exact station-zone extents require the 2024 project profile.

## Why this matters to the solver

The future profile solver should be able to encode constraints such as:

```json
{
  "segment": "Новослободская–Проспект Мира",
  "zone": "future_Dostoevskaya",
  "s0": null,
  "s1": null,
  "grade_permille": 0,
  "depth_min_m": 38,
  "source_confidence": "B"
}
```

The null chainages are intentional. They become numeric only after:
1. exact physical track XY is loaded;
2. the project station/profile location is georeferenced.

## Station depths remain soft constraints

The 12 published station depths are **not yet UGR elevations**. They remain useful as:
- plausibility checks;
- possible Z anchors after depth semantics and local surface elevation are established;
- evidence for relative deep/shallow character.

Kievskaya currently has a source conflict (53 m station-specific source versus 48 m in an aggregated list). Both must remain in provenance until reconciled.

## Required next profile upgrade

Priority order:
1. obtain the Mosinzhproekt profile volume named above;
2. otherwise obtain any absolute rail-level/elevation marks from project or engineering-geodetic documents;
3. sample a consistent DEM/terrain model;
4. reconcile vertical datum;
5. solve the remaining route with grade and vertical-curve constraints;
6. export uncertainty with every generated Z sample.

Machine-readable version:
`vertical_constraints.json`.
