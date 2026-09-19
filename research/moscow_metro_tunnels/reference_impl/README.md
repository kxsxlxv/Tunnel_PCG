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

`alignment3d.py` deliberately contains no network/GIS dependency. It consumes already projected metre coordinates. This keeps the Blender-side kernel deterministic and portable.

Published station depths are converted to UGR only when the depth datum is explicitly known; ambiguous depth definitions raise an error instead of being guessed.

## Important accuracy statement

The R50/R65 code is an **engineering reconstruction from the dimensioned GOST construction drawing**, using tangent arcs/lines and current A/B construction constants. It is suitable as a high-fidelity synthetic-LiDAR reference. It is not represented as a manufacturer's legal rolling-caliber CAD file.

The lower `O_m` equipment outline remains represented as dimensioned named constraints rather than an invented polygon wherever the figure does not uniquely identify a vertex ordering.

## Tests

Stage 4:
- 11 engineering tests passed.

Stage 5 alignment kernel:
- 7 independent tests passed;
- compileall passed.

Run all tests in the package:

```bash
python -m unittest discover -s tests -v
```

## Generate Stage-4 fixtures

```bash
python tools_export_fixtures.py
```
