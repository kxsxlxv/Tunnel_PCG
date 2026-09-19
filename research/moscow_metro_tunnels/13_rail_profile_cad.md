# R50 / R65 rail-profile CAD reconstruction

Target: produce exact-enough rail cross-sections for LiDAR geometry from ГОСТ Р 51685-2022 rather than using generic railway I-beams.

Primary:
ГОСТ Р 51685-2022 «Рельсы железнодорожные. Общие технические условия»
https://protect.gost.ru/gost/details/8086c377-c8fe-49f0-9569-7e5c334554c3

Readable standard:
https://base.garant.ru/406844406/

---

## 1. Two different kinds of dimensions in the standard

Do not confuse:

1. **nominal finished-rail dimensions** from the main tables;
2. **caliber/profile-construction dimensions** in Appendix Г and template-control dimensions in Appendix Ж.

Example: the R65 finished nominal head width is 74.59 mm, while the rolling/profile drawing includes a 73.00 mm construction/template reference. Both are valid in their own context.

For Blender physical mesh, target the finished nominal profile and use Appendix Г/Ж to construct and validate the curve.

---

## 2. Nominal principal dimensions

### R50
- overall height H: **152.00 mm**
- head width b: **71.59 mm**
- base width B: **132.00 mm**
- web thickness e: **16.00 mm**
- web-region height h: **83.00 mm**
- base edge height m: **10.50 mm**

### R65
- overall height H: **180.00 mm**
- head width b: **74.59 mm**
- base width B: **150.00 mm**
- web thickness e: **18.00 mm**
- web-region height h: **105.00 mm**
- base edge height m: **11.25 mm**

---

## 3. Appendix Г construction constants

Current ГОСТ gives:

| Rail | A, mm | B, mm |
|---|---:|---:|
| R50 | 20.0541 | 45.6848 |
| R65 | 20.0328 | 49.0859 |

Preserve full precision in the CAD solver.

---

## 4. R65 construction geometry visible in Appendix Г

Key dimensions/radii/slopes shown in the current/associated ГОСТ profile drawing include:

Principal/profile references:
- rail height: 180 mm;
- base width: 150 mm;
- web thickness: 18 mm;
- construction head reference around 73 mm;
- vertical references including 15.67, 45, 97.5, 81.3 and 30 mm in the figure.

Curvature/slopes:
- R500
- R80
- R15
- R5
- R12
- R370
- R400
- R25
- R2
- R4
- slope 1:20
- slope 1:4

These describe a tangent chain of arcs/lines around the symmetric half-profile.

Do not convert this list into arbitrary fillets. Arc order and tangency must follow the Appendix Г drawing.

---

## 5. R50 construction geometry

Associated ГОСТ profile construction drawings give:

Principal/profile references:
- height: 152 mm;
- base width: 132 mm;
- web: 16 mm;
- web-region height: 83 mm;
- base edge: 10.5 mm;
- other construction references around 14, 15.4, 35, 42, 93.5 mm as shown in the profile figure.

Radii/slopes include:
- R500
- R80
- R15
- R3
- R10
- R325
- R350
- R20
- R4
- R2
- slope 1:20
- slope no steeper than / around 1:4 as specified by the figure.

---

## 6. Appendix Ж control-template dimensions

Useful validation dimensions from the current standard:

| Template dim | R50 mm | R65 mm |
|---|---:|---:|
| I | 45.68 | 49.09 |
| II | 70.24 | 73.00 |
| III | 14.01 | 13.94 |
| IV | 136.60 | 164.33 |
| V | 71.59 | 74.59 |
| VI | 27.50 | 29.79 |
| VII | 67.26 | 85.71 |
| VIII | 93.50 | 117.68 |
| IX | 104.25 | 126.88 |
| X | 1.28 | 1.81 |
| XI | 16.36 | 20.64 |
| XII | 45.00 | 45.00 |
| XIII | 2.15 | 3.08 |
| XIV | 9.66 | 12.07 |
| XV | 24.01 | 24.51 |
| XVI | 20.91 | 22.59 |
| XVII | 13.75 | 16.50 |
| XVIII | 1.39 | 1.73 |

These are excellent automated QA targets after generating the spline.

---

## 7. Recommended CAD solver

Do not hand-enter dozens of sampled points from a raster image.

Represent one half-profile as exact primitives:
```python
LineSegment(p0, p1)
CircularArc(center, radius, angle0, angle1)
```

Build from:
- symmetry about rail vertical axis;
- exact rail height/base width/web thickness/head width;
- specified slopes;
- specified tangent radii;
- A/B construction constants.

Solve tangent points analytically.

Then:
1. mirror half-profile;
2. close polygon;
3. calculate template/control dimensions;
4. reject profile if ГОСТ validation dimensions exceed target tolerance.

Suggested internal solver tolerance:
- construction math: <=1e-6 m;
- exported Blender vertices: <=0.05 mm profile deviation for LOD0;
- LiDAR mesh resampling chord error: configurable, default <=0.1 mm for rail section.

---

## 8. Blender extrusion

The rail profile is oriented:
- local cross-section Y = lateral;
- Z = vertical;
- longitudinal X = alignment tangent.

Rail profile reference frame must identify:
- inner working/gauge face;
- head top tangent/UGR point;
- profile symmetry axis.

Gauge placement:
```
inner_working_face_left.y - inner_working_face_right.y = gauge
```

Do not position profile centroids at +/-gauge/2.

On cant:
- both rails rotate with track frame;
- UGR is the plane through top reference points of running rails;
- contact-rail z offset is evaluated in the same local track frame.

---

## 9. Current data status

The repository now stores:
- exact principal dimensions;
- exact A/B constants;
- exact control-template values;
- the ГОСТ radii/slopes needed for a CAD reconstruction.

A fully solved ordered arc/line primitive sequence should be generated and numerically validated before freezing an `exact_polyline`.

Until that solver/test is complete, `exact_polyline` remains deliberately null in machine-readable data.
