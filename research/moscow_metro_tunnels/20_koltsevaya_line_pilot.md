# Koltsevaya Line pilot findings

Research date: 2026-09-21.

## Identity

Line: Moscow Metro Line 5, Koltsevaya.

Current public line facts:
- 12 stations;
- published line length: 19.4 km;
- current OSM hierarchy is now resolved directly from OpenStreetMap:
  - **1462012** = Line 5 `route_master`;
  - **300607** = current child `route=subway` relation **Circle line (Inner)**;
  - **1462011** = current child `route=subway` relation **Circle line (Outer)**.
- The earlier pilot warning that 300607 was merely a legacy relation was incorrect: it is currently the Inner child route of route_master 1462012 (S099-S101).

Sources:
- https://www.wikidata.org/wiki/Q831673
- https://wiki.openstreetmap.org/wiki/Moscow_Metro
- https://www.metro.ru/stations/koltsevaya/

## Pilot data created

Directory:
`examples/koltsevaya_line_v0/`

Files:
- `stations.csv` — 12 public station coordinate/depth anchors, projected to UTM 37N;
- `alignment_xy_station_spline_25m.csv` — closed 25 m XY fallback spline;
- `route_meta.json` — provenance and warnings;
- `blender_plan_preview.py` — plan-only Blender visualization;
- `tools_extract_relation.py` — relation-member extractor for a local Moscow PBF;
- `README.md`.

## Station anchors

The station order is:
1. Белорусская
2. Новослободская
3. Проспект Мира
4. Комсомольская
5. Курская
6. Таганская
7. Павелецкая
8. Добрынинская
9. Октябрьская
10. Парк культуры
11. Киевская
12. Краснопресненская
13. back to Белорусская.

Published depth anchors used in the pilot:

| Station | published depth, m |
|---|---:|
| Белорусская | 42.5 |
| Новослободская | 40 |
| Проспект Мира | 40 |
| Комсомольская | 37 |
| Курская | 40 |
| Таганская | 53 |
| Павелецкая | 40 |
| Добрынинская | 35.5 |
| Октябрьская | 40 |
| Парк культуры | 40 |
| Киевская | 53 |
| Краснопресненская | 35.5 |

Important:
these values are stored as `published_station_depth_m`, not as UGR elevations.

For Kievskaya a station-specific metro reference gives 53 m:
https://news.metro.ru/f512.html

An older aggregated station list can show 48 m, so the 53 m station-specific value is retained with a provenance warning rather than silently averaging the two.

Krasnopresnenskaya has a station-specific 35.5 m reference:
https://news.metro.ru/f511.html

## Horizontal pilot result

Because direct OSM relation bytes were unavailable in the current runtime, a temporary closed Catmull-Rom spline was generated through all 12 projected station anchors.

Result:
- length: ~18.908 km;
- official/public line length: 19.4 km;
- deficit: ~492 m, ~2.54%.

This is a strong empirical demonstration that station anchors alone are insufficient.

Intermediate physical track vertices are necessary.

The fallback spline has:
- approximate minimum sampled radius ~393 m;
- 13 samples at 25 m spacing below the normal current 600 m reference;
- no samples below the difficult-condition 300 m reference.

These radii describe the **fallback spline**, not the as-built Koltsevaya track.

## Exact OSM upgrade

Current relation hierarchy:
- route master: `r1462012`;
- Inner route: `r300607`;
- Outer route: `r1462011`.

Recommended acquisition:

```bash
# Download/update current Moscow PBF
wget https://download.bbbike.org/osm/bbbike/Moscow/Moscow.osm.pbf

# Extract the two physical-direction route relations separately.
osmium getid -r Moscow.osm.pbf r300607 -o koltsevaya_inner_relation.osm.pbf
osmium getid -r Moscow.osm.pbf r1462011 -o koltsevaya_outer_relation.osm.pbf
```

The supplied acquisition tools are route-master aware: `tools_fetch_relation_full.py` starts from 1462012 and keeps the two child route relations separate; the PBF extractor is being kept consistent with the same rule.

Do not merge Inner and Outer into one line:
- each child route has its own physical member-way chain;
- station/platform members may occur;
- way orientation must be checked against physical node connectivity;
- switches/depot/connecting structures require explicit graph semantics.

The final alignment builder must classify and stitch **one physical track at a time**.

## Vertical pilot status

No false Z has been generated.

The 12 station depths are useful only after surface elevations are sampled.

Required next data layer:
- FABDEM/Copernicus/public terrain for research;
- preferably project LandXML/engineering surface when available.

Then:

```
surface_z(station)
+ explicit vertical datum
+ published/project depth datum
=> candidate UGR anchor
```

Only after that should a grade/vertical-curve solver generate the tunnel profile.

## Blender

`blender_plan_preview.py` creates:
- one closed XY route curve at z=0;
- 12 station empties;
- source/warning custom properties.

It deliberately does **not** generate tunnel geometry or fake vertical relief.

Once a resolved `alignment_3d.json` exists, the existing Stage-5 `parallel_transport_frames()` path is the correct input for rings/rails/third rail.


## Continuation: exact OSM and closed-loop 3D

The pilot now contains two exact-XY acquisition routes:

- full Moscow PBF -> `tools_extract_relation.py`;
- direct OSM API `relation/{id}/full` -> `tools_fetch_relation_full.py`.

The direct API fetcher is nested-relation aware. If relation 1462012 resolves to a route master / parent relation, child route relations are downloaded and emitted separately. Opposite directions or route variants are never merged automatically.

Core reference modules:
- `osm_relation.py` preserves member order, role, way ID and all node IDs;
- `osm_track_stitch.py` connects only physical `railway=subway` ways by shared OSM endpoint nodes;
- graph branches (switches/crossovers) are rejected for explicit topology resolution.

Synthetic QA:
- OSM relation parser: pass;
- OSM track stitching: 4/4 behavior tests pass.

For 3D ring closure, `closed_parallel_transport_frames()` was added to `alignment3d.py`. It measures closed-curve parallel-transport holonomy and distributes inverse roll along 3D chainage, so the final local frame closes onto the first frame. Alignment QA is now 8/8 tests.

The example also has:
- `vertical_constraints.json`;
- `VERTICAL_PROFILE_NOTES.md`;
- `ALIGNMENT_3D_CONTRACT.md`;
- `blender_alignment3d_import.py`.

The Blender importer refuses unresolved `z_ugr_m`, verifies seam closure and only then builds the diagnostic 3D alignment/frames.

## Current Line-5 vertical evidence

Official Moscow documentation confirms a 2024 Mosinzhproekt volume containing:
- plan 1:2000;
- plan 1:500;
- longitudinal profile 1:2000 / 1:200.

The same published evidence lists a 2022 Mosgorgeotrest engineering-geodetic survey for the Dostoevskaya/Suvorovskaya zone.

A 2026 construction statement confirms that the existing Line-5 tunnels in the reserved future-station zone have zero grade and lie at a construction depth greater than 38 m.

These are stronger than interpolating generic station depths, so they are encoded separately as project/local profile constraints with unresolved exact chainage limits.

## Stage 11/22 — physical two-track topology and junctions

The pilot is no longer allowed to treat Line 5 as one centerline plus an offset.

New contract:
- `KOLTSEVAYA_TRACK_A` = I main track, inner ring, clockwise;
- `KOLTSEVAYA_TRACK_B` = II main track, outer ring, counterclockwise;
- both must be reconstructed independently from physical `railway=subway` ways/project alignments;
- current direction-route IDs are resolved as Inner=300607 and Outer=1462011; exact member way/node IDs remain unresolved because relation/full bytes were not obtainable in the research runtime. No way/node IDs were guessed.

New files:
- `22_koltsevaya_track_topology_and_junctions.md`;
- `examples/koltsevaya_line_v0/track_topology.json`;
- `examples/koltsevaya_line_v0/junction_events.json`;
- `data/moscow_turnout_archetypes.json`;
- `reference_impl/tunnel_pcg_ref/osm_track_graph.py`;
- `reference_impl/tests/test_osm_track_graph.py`.

The first real junction selected for geometry hand-off is the Belorusskaya/Krasnaya-Presnya depot-side node. A Metrostroy historical photo/caption identifies II main track straight toward Krasnopresnenskaya and a left branch toward the turnback/depot system, with a cast-iron tubing chamber and monolithic-RC end wall.

The exact installed turnout project and actual chamber dimensions are not public in the inspected set. A dimensioned R65 1:9 metro turnout project 2976.00.000 is retained only as an explicit fallback. Frolov's dimensioned stepwise branch chambers are likewise retained only as a generic civil-transition reference, not as the Belorusskaya as-built shell.

See `22_koltsevaya_track_topology_and_junctions.md` for the KNOWN / CONSTRAINED / UNKNOWN boundary.
