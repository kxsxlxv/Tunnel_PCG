# Koltsevaya Line pilot — Line 5

This directory is the first real-route pilot for the geospatial tunnel pipeline.

## What is factual

- Line 5 / Koltsevaya.
- 12 stations.
- published operating length: 19.4 km.
- current OSM route hierarchy: **1462012 route_master**, with **300607 Inner** and **1462011 Outer** child subway routes.
- station order, public station coordinates and published station depths.
- Kievskaya depth 53 m is backed here by a station-specific Moscow Metro photo/reference page; an older aggregated list can show 48 m, so the specific source wins for this pilot.

## What is reconstructed

The current runtime could not directly download the OSM relation geometry. Therefore `alignment_xy_station_spline_25m.csv` is a **fallback plan preview**, not an as-built centerline.

It is a closed Catmull-Rom spline through the 12 station coordinate anchors in UTM 37N.

Results:
- spline length: **18907.8 m**;
- published line length: **19400 m**;
- deficit: **492.2 m (2.54%)**.

This deficit is itself useful: a station-to-station smooth spline demonstrably cannot replace physical track geometry. Intermediate OSM/project vertices are required.

The inferred minimum sampled plan radius is about **393 m**. **13** 25 m samples are below the current normal 600 m reference, and **0** are below the difficult-condition 300 m reference. That does **not** prove the real line has those exact radii; it only describes this fallback spline.

## Vertical profile

No fake 3D profile is produced.

Published depths are stored in `stations.csv`, but `z_ugr_m` is deliberately blank because:
- the surface elevation varies around Moscow;
- the public station-depth datum is not consistently defined;
- absolute surface DEM and project heights can use different vertical datums.

The next valid step is DEM/LandXML sampling followed by a constrained vertical-profile solve.

## Files

- `route_meta.json`
- `stations.csv`
- `alignment_xy_station_spline_25m.csv`
- `blender_plan_preview.py`

The Blender preview only visualizes XY at z=0. It is intentionally incapable of masquerading as a finished 3D tunnel.


## Exact-XY acquisition tools

Two alternatives are now supplied:

1. `tools_extract_relation.py`
   - reads a local current Moscow PBF with pyosmium;
   - root relation: 1462012;
   - preserves the current child routes separately: 300607 Inner and 1462011 Outer.

2. `tools_fetch_relation_full.py`
   - calls the standard OpenStreetMap API endpoint `/api/0.6/relation/1462012/full`;
   - follows nested child route relations conservatively;
   - emits Inner and Outer separately while preserving member order/roles.

The core parser preserves OSM node IDs. The track stitcher then connects physical `railway=subway` ways only through shared endpoint node IDs and rejects branch/switch graphs rather than guessing.

## Local vertical evidence: future Dostoevskaya zone

Official Moscow documentation confirms that a 2024 Mosinzhproekt volume exists with:
- line plan 1:2000;
- line plan 1:500;
- longitudinal profile 1:2000 / 1:200.

It also identifies a 2022 Mosgorgeotrest engineering-geodetic survey for the same construction zone.

A 2026 Moscow Metro publication states that the existing Line-5 tunnels in the reserved station zone have:
- zero longitudinal grade;
- construction depth greater than 38 m.

These are stored in `vertical_constraints.json`. Exact chainage limits remain null until the project profile / physical track centerline is georeferenced.

## Closed-loop Blender frames

`blender_alignment3d_import.py` is the strict importer for the future resolved `alignment_3d.json`.

It refuses null Z, verifies route closure, then uses the tested `closed_parallel_transport_frames()` solver so a non-planar ring does not accumulate an orientation seam at the closure point.

See `ALIGNMENT_3D_CONTRACT.md`.

### Connected physical-network extraction

Passenger route relations alone do not necessarily contain depot/service/crossover branches. For a local Moscow PBF, `tools_extract_connected_subway_graph.py` therefore:

- seeds from the current Inner route 300607 and Outer route 1462011;
- scans physical `railway=subway` ways;
- expands by shared OSM nodes for a configurable number of graph hops;
- preserves route-member vs off-route-candidate membership;
- passes the result to the branch-preserving `osm_track_graph.py`;
- does **not** call an off-route way a depot branch/crossover merely because it is connected.

The hop limit is an acquisition scope only. Branch semantics still come from the researched topology contract.

## Physical topology and junction events

This example now has an explicit two-track/topology layer.

Files:
- `track_topology.json` — two independently identified Line-5 main tracks plus source-backed junction-system annotations;
- `junction_events.json` — event contract for the first Belorusskaya/Krasnaya-Presnya depot-side divergence;
- `../../data/moscow_turnout_archetypes.json` — source-backed turnout constraints plus tagged R65 project-2976 and alternate R50 project-2891 fallbacks;
- `../../data/moscow_junction_civil_archetypes.json` — actual-site civil constraints separated from generic Frolov/ENiR chamber references.

Main-track identities:
- `KOLTSEVAYA_TRACK_A`: I main / inner / clockwise;
- `KOLTSEVAYA_TRACK_B`: II main / outer / counterclockwise.

The physical centerlines are **not** created from `alignment_xy_station_spline_25m.csv` and are **not** offsets of each other. The direction-route IDs are now resolved (300607 Inner, 1462011 Outer); exact OSM member way/node IDs remain deliberately null until relation/full or Moscow-PBF extraction is available.

Graph workflow:
1. use route_master 1462012 only to discover/validate its two current child routes;
2. fetch **300607 Inner** and **1462011 Outer** independently;
3. preserve all physical `railway=subway` ways and OSM node IDs per child route;
4. run the conservative graph extractor without choosing degree>2 branches;
5. map Inner to `KOLTSEVAYA_TRACK_A` and Outer to `KOLTSEVAYA_TRACK_B` using the independent operational direction evidence;
6. attach branch/crossover semantics from `track_topology.json`;
7. leave unresolved branches unclassified rather than selecting them automatically.

`osm_track_stitch.py` still rejects graph degree >2. The separate `osm_track_graph.py` is the branch-preserving path for turnout/crossover research.

### Depot-branch edge boundary

The Krasnaya Presnya connection contract now distinguishes:
- `BRANCH_KRP_BELORUSSKAYA_LEG` — single-track Line-5 depot-connection leg;
- `BRANCH_KRP_KRASNOPRESNENSKAYA_LEG` — separate single-track Line-5 depot-connection leg;
- a farther depot-side **local two-track section** and switch system visible in S120.

For the first geometry fixture, follow only `BRANCH_KRP_BELORUSSKAYA_LEG` and terminate at an `END_NODE` before the unresolved downstream system. Track count is source-backed; civil shell cross-section, independent-round-tunnel start and Z remain unresolved.

The Krasnopresnenskaya leg has a separate archival S121 crown-profile constraint. It is intentionally not reused for the Belorusskaya leg.

### First junction

`JUNCTION_KOL5_BELORUSSKAYA_DEPOT_WEST`:
- II main track continues straight toward Krasnopresnenskaya;
- the turnback/depot route diverges left;
- the actual chamber is source-backed as cast-iron tubing with a monolithic-RC end wall;
- switch XY/Z, installed turnout project and actual chamber dimensions remain unresolved.

The example therefore contains a strict KNOWN/CONSTRAINED/UNKNOWN boundary. Generic chamber/turnout fallback data must stay tagged as fallback in generated geometry.

## Current station-level track-development inventory

`track_topology.json` now covers all 12 current Line-5 stations. The important distinction is **station development vs nearby network junction**: Taganskaya is source-backed as having no station track development even though a separate nearby service-connection system exists in the Taganskaya area.

Stations without current station track development:
`Новослободская`, `Комсомольская`, `Таганская`, `Добрынинская`, `Октябрьская`, `Киевская`.

Stations with source-backed current development:
`Белорусская`, `Проспект Мира`, `Курская`, `Павелецкая`, `Парк культуры`, `Краснопресненская`.

The planned `Достоевская` state is stored separately. Its future 4-turnout/2-storage-track development plus the planned transfer of the current Prospekt-Mira KRL connection must not be mixed into the 2026 normal-operating topology.

## Service-era turnout alternatives

The first mesh fallback remains metro-specific R65 project 2976 because the active Stage-10 service preset is R65/KD65/2001-reference. An R50 1:9 metro-specific project-2891 fallback is also encoded, but only for an explicitly selected R50 service-era/site preset. Neither product project is asserted as the installed Belorusskaya turnout.

## Secondary actual-site validation

`junction_events.json` also contains `JUNCTION_KOL5_KURSKAYA_LDL_1990S` as a secondary visual/civil validation event. It preserves source-backed facts such as Track II/outer-ring switch numbering, a qualitatively descending service branch, and mixed monolithic/cast-iron chamber construction, while leaving all unsourced dimensions and Z null.
