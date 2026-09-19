# Reference implementation

Isolated engineering reference package for the Moscow Metro tunnel PCG research base.

It is intentionally independent from the project's production generator. Its jobs are:

- encode current gauge/contact-rail/clearance rules as executable functions;
- reconstruct R50/R65 rail cross-sections from the tangent-chain geometry in GOST R 51685-2022 Appendix G;
- validate rail reconstructions against principal dimensions plus Appendix D section area/centroid;
- expose deterministic placement/ring helpers for tests and fixtures;
- provide machine-readable schemas and expected fixture outputs.

## Important accuracy statement

The R50/R65 code is an **engineering reconstruction from the dimensioned GOST construction drawing**, using exact tangent arcs/lines and current A/B construction constants. It is suitable as a high-fidelity synthetic-LiDAR reference. It is not represented as a manufacturer's legal rolling-caliber CAD file.

The reconstruction is automatically checked against the standard's nominal height/base/head dimensions and against section area/centroid. Current residuals are intentionally retained in generated QA metadata rather than hidden by fitting the profile to the target area.

The lower `O_m` equipment outline remains represented as dimensioned named constraints rather than an invented polygon wherever the figure does not uniquely identify a vertex ordering in text.

## Run tests

```bash
python -m unittest discover -s tests -v
```

## Generate fixtures

```bash
python tools_export_fixtures.py
```
