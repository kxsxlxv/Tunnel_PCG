# Stage 4 - executable reference SDK

Research snapshot: 2026-09-19.

The `reference_impl/` package converts the research base into executable engineering constraints and test fixtures. It intentionally does **not** depend on or modify the production generator already present in `Tunnel_PCG`.

## Delivered kernel

Pure-Python, stdlib-only modules:

- `geometry.py` - 2D vector/line/circle/tangent/area primitives;
- `track.py` - current radius-dependent gauge and cant angle;
- `contact_rail.py` - nominal 160/690 mm placement and side rules;
- `clearances.py` - analytic `C_mk`, exact upper `O_m` points, curve corrections and `b_R` table;
- `rail_profiles.py` - R50/R65 analytic tangent-chain reconstruction;
- `rings.py` - discrete lining-ring sequence;
- `events.py` - deterministic periodic systems and special-structure overrides;
- `blender_adapter.py` - optional minimal `bpy` bridge kept separate from the engineering kernel.

## R50/R65 reconstruction

The rail profile is solved as a right-half tangent chain and mirrored about the vertical rail axis.

For R65 the chain is:

`R500 -> R80 -> R15 -> 1:20 line -> R5 -> 1:4 underside -> R12 -> R370 -> R400 -> R25 -> 1:4 foot -> R4 -> vertical edge -> R2 -> bottom`.

For R50 the analogous chain is:

`R500 -> R80 -> R15 -> 1:20 line -> R5 -> 1:4 underside -> R10 -> R325 -> R350 -> R20 -> 1:4 foot -> R4 -> vertical edge -> R2 -> bottom`.

The A/B constants and dimension lines are taken from GOST R 51685-2022 Appendix G. Principal dimensions are checked against Table 2. Section area and centroid are checked against Appendix D.

### Current QA result

| profile | area reconstruction | GOST area | relative residual | centroid z | GOST centroid z | residual |
|---|---:|---:|---:|---:|---:|---:|
| R50 | 0.0066142 m2 | 0.006599 m2 | +0.231% | 70.393 mm | 70.500 mm | -0.107 mm |
| R65 | 0.0082777 m2 | 0.008265 m2 | +0.154% | 81.146 mm | 81.300 mm | -0.154 mm |

Height and base width reproduce the nominal dimensions exactly in the solver. Reconstructed maximum head widths differ from the current nominal widths by less than 0.03 mm.

### Interpretation

This is a high-fidelity engineering reconstruction suitable for synthetic LiDAR. It is **not** declared to be the manufacturer's rolling-caliber master CAD. The small area/centroid residual is deliberately exposed rather than hidden by numerical fitting, because fitting would destroy direct provenance to the published GOST construction geometry.

## GOST 23961 executable geometry

Implemented exactly:

- `C_mk` circle: radius 2.450 m;
- R50 center: z=1.700 m above UGR;
- R65 center: z=1.670 m above UGR;
- curve inward offset `q = z_c * tan(alpha)`;
- exact upper `O_m` named vertices from Fig. 6;
- lower `O_m` tight-curve additions for R<200 m;
- Table A.1 `b_R` values;
- two-track 3.400 m minimum center-spacing constraint remains a constraint, not a geometry preset.

Not converted into a guessed closed polygon:

- the complete lower `O_m` multi-line device envelope in Fig. 7. Its exact dimension callouts remain stored in the parent research JSON. Code should validate individual device families against the relevant named line until a fully audited vertex mapping is completed.

## Accuracy / LOD contract

Default rail fixture chord error: 0.05 mm.

Recommended sensor-driven threshold:

- rail profile: <=0.1 mm chord error;
- structural tunnel circle/segments: <=1 mm chord error for near-range scans;
- bolts/ribs/cable brackets: explicit mesh whenever projected LiDAR resolution can resolve them;
- textures/normal maps only below the configured sensor feature threshold.

## Tests

The package currently includes tests for:

- all current gauge radius boundaries, including R<=100 m -> 1544 mm;
- cant-driven Cmk shift;
- R50/R65 Cmk datum;
- exact upper Om vertices;
- lower Om tight-curve increments;
- contact-rail nominal position and tight-curve side rule;
- R50/R65 profile geometric QA;
- deterministic periodic equipment placement;
- special-structure range override;
- discrete ring sequence.

Run:

```bash
PYTHONPATH=. python -m unittest discover -s tests -v
```

## Blender integration rule

Production Blender code should consume the pure-Python kernel, not duplicate standard constants inside Geometry Nodes/scripts.

Recommended separation:

1. engineering model produces profile/ring/event data;
2. Blender adapter converts those data to meshes/curves/instances;
3. clearance validator runs in engineering coordinates;
4. exporter attaches semantic IDs for LiDAR ground truth.

`blender_adapter.py` is intentionally minimal and untested outside Blender. It demonstrates coordinate mapping only; it is not the final production mesher.
