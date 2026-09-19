# Normative clearance envelopes for procedural validation

Research snapshot: 2026-09-19.

Primary current standard: ГОСТ 23961-2024 «Метрополитены. Габариты приближения строений, оборудования и подвижного состава», effective 2025-06-01.

Primary source:
- Rosstandart: https://protect.gost.ru/gost/details/d9e37be2-c5e8-4727-9df3-b84536ed7609
- readable copy used to verify drawings: https://spbssk.ru/wp-content/uploads/2025/06/gost-23961-2024_metropoliteny-gabarity-priblizheniya-stroenij-oborudovaniya-i-podvizhnogo-sostava.pdf
- searchable copy: https://allgosts.ru/93/060/gost_23961-2024

## Modeling principle

The ГОСТ profiles are **clearance / exclusion envelopes**, not tunnel-lining surfaces.

Implement at least three independent cross-section layers:

1. `STRUCTURE_INNER_SURFACE` — actual lining / wall / invert geometry.
2. `C_CLEARANCE` — structure clearance envelope (`Cмк`, `Cмп`, `Cмкд`, etc.).
3. `O_CLEARANCE` — equipment envelope (`Oм`, `Oмк`, etc.).

Then validate:
- structural geometry must not intrude into C;
- ordinary equipment must not intrude into O;
- only explicitly allowed interaction devices may enter O/M-related zones (contact rail, auto-stop equipment, etc.).

Do not generate tunnel diameter from O or C directly.

---

## 1. Cмк — single-track circular running tunnel

Applicability:
- circular single-track tunnel;
- straight track and curves R >= 200 m;
- current figure assumes contact rail on the prescribed side;
- circular tunnels with diameter > 5.2 m are calculated separately but shall provide not less than Cмк.

### Basic construction

For R50 running rail:
- clearance circle radius: **2450 mm**;
- clearance-circle center: **1700 mm above UGR**.

For R65:
- same nominal radius;
- center-to-rail-tangent reference: **1670 mm**.

Thus a useful analytic representation is:

```
x^2 + (z - z_c)^2 = 2450^2  [mm]
z_c = 1700 mm for R50
z_c = 1670 mm for R65
```

where x is lateral from gauge axis and z is vertical from UGR.

This is a clearance-circle representation only. The actual lining of the classic 5.1 m-ID tunnel has radius 2550 mm, giving roughly 100 mm radial margin to the nominal Cмк circle before local invert/track conditions are considered.

### Cant / superelevation shift

In a curve the Cмк axis is shifted toward the inside of the curve:

- R50: `q = 1700 * tan(alpha)`
- R65: `q = 1670 * tan(alpha)`

where alpha is the track inclination angle to horizontal.

Implementation:
- build the local track frame first;
- rotate it by cant about the tangent;
- apply the inward lateral offset q to the clearance-envelope axis;
- do **not** simply rotate a fixed world-Z circle around the route.

### Lower-zone references visible in Fig. 1

The drawing explicitly includes separate lines for:
- personnel walkway;
- drainage channel;
- path foundation / invert portion compressed against the ground.

A dimension of **1660 mm** from gauge axis is shown to the walkway-related reference point in the figure. Treat this as a normative reference, not a universal physical walkway edge until the exact line convention is encoded.

For R50/R65, several lower vertical dimensions differ by 30 mm; do not reuse the R50 lower profile unchanged with R65.

### Drainage for modern elastic-block / half-sleeper track
Current ГОСТ text requires minimum drainage-channel widths:
- ordinary running tunnel: **400 mm**;
- within a tunnel bulkhead / pressure gate zone: **700 mm**;
- station: **900 mm**;
- longitudinal channel-bottom slope: **>= 3 per mille**.

---

## 2. Cмп — rectangular / open-cut running tunnel envelope

Use for:
- rectangular running tunnels;
- relevant surface/elevated structures.

Above UGR the profile is defined for straight track and must be widened in curves using Appendix A of ГОСТ 23961-2024.

For curves:
- inside increase: `d_in = b_R + b_h`;
- outside increase: `d_out = b_R - b_h`.

The geometric offset `b_R` is tabulated by radius. Useful values from ГОСТ Table A.1 include:

| R, m | b_R, mm |
|---:|---:|
| 4000 | 5 |
| 3000 | 7 |
| 2000 | 10 |
| 1500 | 14 |
| 1200 | 18 |
| 1000 | 21 |
| 800 | 26 |
| 600 | 35 |
| 500 | 42 |
| 400 | 52 |
| 350 | 60 |
| 300 | 70 |
| 250 | 84 |
| 200 | 105 |
| 175 | 120 |
| 150 | 140 |
| 125 | 168 |
| 100 | 210 |
| 80 | 262 |
| 60 | 350 |

`b_h` depends on cant and height above UGR and must be calculated / table-looked-up from Appendix A.

For PCG this means a rectangular tunnel must **not** be swept with constant lateral wall offsets through a tight curve; its normative lateral clearance is asymmetric.

---

## 3. Cмкд — two-track circular tunnel

Use for modern large-diameter two-track circular tunnels.

Important current constraints:
- minimum track-center spacing on main tracks in circular or rectangular two-track tunnels without intermediate supports, for straight track and curves R >= 500 m: **3400 mm**;
- for R < 500 m increase spacing using the Appendix A.3 curve method;
- the distance from tunnel axis to UGR shown in Fig. 5 is a design parameter; for tunnel diameters **> 9400 mm it must be determined by calculation**;
- service bridge / service platform height >= **1100 mm above UGR**;
- clear platform passage width >= **700 mm**.

Therefore the ~10 m Moscow TBM archetype needs:
- configurable track-center spacing;
- calculated vertical track placement inside the circular lining;
- independent side service/evacuation geometry;
- no assumption that the two tracks are simply at +/-1.7 m in a centered circle.

---

## 4. Oм — equipment envelope

### Upper envelope coordinates for straight track

The upper Oм profile in ГОСТ Fig. 6 gives the following exact straight-track reference coordinates relative to track axis and UGR.

Symmetric points:

| x from axis, mm | z above UGR, mm | note |
|---:|---:|---|
| 1480 | 550 | lower shoulder reference |
| 1480 | 740 | adjacent lower point shown in drawing |
| 1620 | 3280 | outer upper-side point |
| 1325 | 3625 | shoulder |
| 1005 | 3745 | roof shoulder |
| 355 | 3780 | near-center roof |
| 0 | approximately 3780 | top center between symmetric 355 points |

The drawing also marks inner roof widths of 355 / 1005 / 1325 / 1620 mm from the axis.

Do not approximate this with a single rectangle. Encode as a polyline and mirror around x=0.

For circular tunnels using R65, the standard permits vertical dimensions to points д, е, ж, з to be reduced by 30 mm as specified in the text.

### Lower Oм profile

Fig. 7 separately defines:
- contact-rail approach line;
- thresholds / deckings;
- raised auto-stop rail;
- picket-marker bracket;
- automatic-driving sensors;
- cable connection point to the contact rail;
- lower bed of sleeper in circular tunnel concrete track.

This profile is deliberately asymmetric because of the contact rail.

Important horizontal references visible in Fig. 7 include, on the contact-rail side:
- 1660 mm;
- 1480 mm;
- 1560 mm;
and on the opposite / internal-device side:
- 1625, 1600, 1570, 1480, 1365, 1250 mm depending on device line.

These are exclusion-line coordinates, **not object centerlines**. For an actual third-rail centerline use the operating-rule dimensions in `05_track_and_contact_rail.md`.

The standard requires:
- minimum groove between running-rail working face and devices inside gauge: **90 mm**;
- minimum rail/counterrail groove: **42 mm**, transitioning smoothly to 90 mm at ends.

For R < 200 m, horizontal distances to lower-envelope points on the inside rail are additionally enlarged:
- R < 100 m: +20 mm;
- 100–124 m: +16 mm;
- 125–149 m: +11 mm;
- 150–199 m: +6 mm.

Also:
- in curves R <= 350 m, cables may not cross over the crown from one side of a circular tunnel to the other within the Cмк–Oм space.

---

## 5. Automated validation recommended

For every generated cross-section sample at chainage s:

```python
assert no_intersection(structural_mesh, C_clearance(s))

for object in ordinary_equipment:
    assert no_intersection(object, O_clearance(s))

for object in interaction_equipment:
    assert object.type in allowed_intrusions
```

Run clearance checks:
- at every lining ring;
- at every contact-rail bracket;
- at cable-rack elevation changes;
- at curve/cant transition samples;
- around cross passages / chambers / tunnel-diameter transitions.

For LiDAR simulation, retain the true object mesh even when a simplified collision proxy is used for validation.
