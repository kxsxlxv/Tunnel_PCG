# Koltsevaya Line pilot — Line 5

This directory is the first real-route pilot for the geospatial tunnel pipeline.

## What is factual

- Line 5 / Koltsevaya.
- 12 stations.
- published operating length: 19.4 km.
- current Wikidata identifier for the OSM line relation: **1462012**.
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
