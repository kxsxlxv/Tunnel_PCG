# Reference implementation

Isolated engineering reference package for the Moscow Metro tunnel PCG research base.

It is intentionally independent from the project's production generator. Its jobs are:

- encode current gauge/contact-rail/clearance rules as executable functions;
- reconstruct R50/R65 rail cross-sections from GOST R 51685-2022;
- validate rail reconstructions against principal dimensions and section properties;
- expose deterministic placement/ring helpers;
- represent georeferenced 3D route alignment in local engineering metres;
- compute chainage, grades, vertical-curve geometry and low-twist parallel-transport frames;
- provide machine-readable schemas and expected fixture outputs.

## Geospatial separation

GIS/survey preprocessing should occur outside Blender:

```
WGS84/project coordinates
 -> engineering metric CRS
 -> vertical-datum reconciliation
 -> 3D UGR alignment
 -> local origin
 -> Blender
```

`alignment3d.py` deliberately contains no network/GIS dependency. For ring routes, `closed_parallel_transport_frames()` measures the residual parallel-transport roll around a non-planar loop and distributes the inverse correction by 3D chainage so the first/last frame closes without a Blender seam. It consumes already projected metre coordinates. This keeps the Blender-side kernel deterministic and portable.

`tools_prepare_geospatial.py` is an **external preprocessing utility**. With the optional `geo` dependency group it:
- reads a single route LineString GeoJSON;
- transforms WGS84 to an engineering metric CRS (default EPSG:32637);
- resamples by chainage;
- samples a GeoTIFF DEM in its native CRS;
- subtracts a local origin;
- writes alignment JSON with surface Z;
- deliberately leaves `z_ugr_m=null` until real vertical anchors are supplied.

Published station depths are converted to UGR only when the depth datum is explicitly known; ambiguous depth definitions raise an error instead of being guessed.

## Important accuracy statement

The R50/R65 code is an **engineering reconstruction from the dimensioned GOST construction drawing**, using tangent arcs/lines and current A/B construction constants. It is suitable as a high-fidelity synthetic-LiDAR reference. It is not represented as a manufacturer's legal rolling-caliber CAD file.

The lower `O_m` equipment outline remains represented as dimensioned named constraints rather than an invented polygon wherever the figure does not uniquely identify a vertex ordering.

## Tests

Stage 4:
- 11 engineering tests passed.

Stage 5:
- 8 pure-Python alignment tests passed, including closed-loop holonomy/seam correction;
- 1 GeoJSON+GeoTIFF preprocessing test passed with `geo` dependencies;
- compileall passed.

Base tests:
```bash
python -m unittest discover -s tests -v
```

Install and run geospatial tests:
```bash
pip install -e '.[geo]'
python -m unittest discover -s tests -v
```

## Generate Stage-4 fixtures

```bash
python tools_export_fixtures.py
```


## OSM relation handling

The reference package now contains:
- `osm_relation.py` — parses standard OSM `/relation/{id}/full` XML while preserving member order, roles, way IDs and endpoint/node IDs;
- `osm_track_stitch.py` — conservatively stitches only `railway=subway` ways by shared OSM node IDs.

The stitcher:
- automatically reverses a way when needed for continuity;
- separates disconnected components;
- accepts simple open chains or simple closed loops;
- rejects any endpoint graph with degree >2.

That last behavior is deliberate: a turnout/crossover must be resolved from explicit topology/route semantics rather than by choosing a geometrically convenient branch.

Synthetic tests:
- relation/full parser: 1/1 passed;
- track stitching/filtering: 4/4 passed.

## Branch-preserving physical track graph

`osm_track_stitch.py` remains intentionally strict and rejects degree >2.

For switch/crossover research, `osm_track_graph.py` adds a separate conservative extractor that:
- preserves all physical `railway=subway` ways;
- splits ways at shared OSM nodes, including shared nodes located inside a way;
- retains degree >2 as `SWITCH_NODE`;
- exposes degree-1 `END_NODE`;
- preserves full OSM tags, node refs and coordinates;
- leaves `z_ugr_m=null`;
- never chooses straight/diverging routes or labels a branch as depot/crossover from geometry alone.

Synthetic test cases were added in `tests/test_osm_track_graph.py`:
- simple two-track loop;
- single turnout branch;
- crossover between two tracks;
- depot branch;
- PTv2 non-track/platform way exclusion.

The current execution environment could not clone/run the repository because external DNS for GitHub is unavailable, so these new tests are **committed but not claimed as executed here**.
