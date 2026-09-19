# Reconstructing Moscow Metro vertical profiles from public data

The vertical alignment is the hardest part of a public-data reconstruction.

There is no known open, current, survey-grade database containing absolute UGR elevations for every Moscow Metro track. Therefore the generator must distinguish:

- **observed/project Z**;
- **derived Z**;
- **engineering-constrained synthetic Z**.

Never label the third category as as-built.

---

## 1. Available public vertical anchors

### A. Dimensioned/public project longitudinal profiles

A concrete Moscow example exists in the engineering book “Строительство метрополитенов” (2006):

- Fig. 1.7 shows the **longitudinal profile and plan** of the first-priority mini-metro section from Kievskaya to Delovoy Tsentr;
- the text explains that the plan/profile was governed by engineering geology, the Moscow River crossing, and the already constructed Delovoy Tsentr station.

Source:
https://ru.djvu.online/file/pGZH0qOLpAG0I

This is exactly the type of source to digitize into chainage/elevation anchors.

### B. Official construction depth constraints

Official Moscow construction publications often give useful local constraints, e.g.:

- Karamyshevskaya / Narodnogo Opolcheniya running tunnel:
  - tunnel length 1838 m;
  - minimum construction depth about 44 m;
  - crown about 13 m below the bottom of the Moscow Canal at the crossing.
  Source:
  https://stroi.mos.ru/photo_lines/bkl-kak-stroiat-stantsii-mietro-ulitsa-narodnogho-opolchieniia-i-michurinskii-prospiekt

- Sokolniki–Rizhskaya BCL:
  - tunnel length 2.25 km;
  - passage depth approximately 25–45 m.
  Source:
  https://stroi.mos.ru/photo_lines/tonnieliem-bol-shie-shchit-sofiia-finishiroval-na-stantsii-bkl-mietro-rizhskaia

- large Rublyovo-Arkhangelskaya two-track tunnel:
  - official sources identify the river/zaton crossing and alignment endpoints;
  - published profile schematics show the descent and ascent shape, but should be treated as schematic unless dimensioned.

These become inequality/range constraints, not arbitrary exact vertices.

### C. Station depth values

Published station depths are useful but dangerous because “depth” may mean:
- surface to platform;
- surface to UGR;
- surface to structural crown;
- construction depth;
- nominal/rounded depth.

Every depth value needs:
```
depth_value
depth_datum
surface_reference
source_date
confidence
```

If `depth_datum` is ambiguous, do not convert it to UGR.

---

## 2. Current engineering constraints on profile

Current SP 120.13330.2022 (revision through 19.01.2026) provides hard plausibility constraints.

### Longitudinal grades

For underground/named line sections:
- ordinary minimum longitudinal grade: **3 per mille**;
- difficult conditions minimum: **2 per mille**;
- isolated horizontal sections are permitted with justification;
- drainage channel still requires its own required slope;
- maximum underground grade: **40 per mille**;
- difficult-condition limited sections may reach **45 per mille**;
- open surface sections: maximum **35 per mille**.

Source:
https://tiflocentre.ru/documents/sp_120.13330.2022_metropoliteni.php

### Vertical curves

When adjacent straight profile elements differ sufficiently in grade, current minimum vertical-curve radii include:

- main tracks near station: **3000 m**;
- main tracks on interstation: **5000 m**;
- connecting tracks: **1500 m**;
- difficult conditions:
  - near stations: **2000 m**;
  - interstation: **3000 m**.

Source:
https://e-ecolog.ru/docs/L6Ql8MkG1YjUB9L3_zuYG/full

Two profile elements sloping in opposite directions by more than the prescribed threshold must be linked through a low-grade element as required by the SP.

### Historical/plausibility prior

Classic metro design literature describes “hump” profiles:
- stations near local profile high points;
- approaches over roughly 150–200 m can descend away from the station at up to about 30 per mille;
- middle of interstation maintains drainage-compatible grade.

Source:
https://ru.djvu.online/file/hXOquNRuMqgHC

Use this as a **soft historical prior**, not as a universal current requirement.

---

## 3. Horizontal engineering constraints also matter to Z

Current SP:
- normal minimum horizontal circular radius on main track: **600 m**;
- difficult conditions: down to **300 m**;
- curves R <= 2000 m on main track are coupled to transition curves;
- transition curves are radioidal spirals;
- Table 5.5 gives radius-dependent cant and transition length.

Source:
https://base.garant.ru/406472751/

Example main-track table values:

| R, m | cant, mm | transition length, m |
|---:|---:|---:|
| 2000 | 10 | 20–30 |
| 1500 | 20 | 20–40 |
| 1200 | 40 | 20–50 |
| 1000 | 60 | 30–70 |
| 800 | 80 | 40–80 |
| 600 | 100 | 50–80 |
| 500 | 120 | 60–80 |
| 400 | 120 | 60–80 |
| 350 | 120 | 60–80 |
| 300 | 120 | 60–80 |

The 3D alignment solver should fit XY and Z jointly enough to avoid creating impossible combinations of:
- tight horizontal curvature;
- steep vertical curve;
- excessive cant transition;
- station throat geometry.

---

## 4. Reconstruction pipeline

### Step 1 — obtain XY track centerline

Source order:
1. survey/project alignment if available;
2. OSM `railway=subway` ways;
3. station-to-station reconstruction only as last resort.

Build one alignment per actual track when OSM provides both parallel tracks.

### Step 2 — compute chainage

Project to a metric CRS and compute cumulative horizontal arc length `s`.

Station coordinates are projected onto the track polyline, producing station chainages.

### Step 3 — sample terrain

Sample DEM/bare-earth terrain at:
- track XY;
- station XY;
- river/channel crossings;
- transition portals.

Store:
```
s
surface_z
surface_vertical_datum
source
```

### Step 4 — add tunnel Z anchors

Anchor priority:

1. absolute project UGR elevation;
2. dimensioned longitudinal-profile elevation;
3. station UGR derived from an explicitly defined depth datum;
4. known tunnel/crown depth range converted with known tunnel geometry;
5. schematic profile / general published depth as low-confidence constraint.

### Step 5 — solve piecewise grades

Unknown Z should be solved as a constrained optimization problem.

Conceptual objective:

```
minimize:
  sum_i w_i * (z(s_i) - z_anchor_i)^2
  + lambda_g * integral(curvature_vertical(s)^2 ds)
  + lambda_prior * engineering_prior
```

Subject to:
- ordinary grade <=40 per mille;
- 45 per mille only where explicitly allowed;
- lower grade/drainage rules;
- vertical-curve radius;
- station profile constraints;
- known overburden / river-bottom constraints;
- exact/high-confidence anchors.

### Step 6 — generate uncertainty

For every sample, output:
- `z_ugr`;
- `sigma_z`;
- `z_source_class`.

Example:
```
OBSERVED_PROJECT       sigma ~ project tolerance
DERIVED_DEPTH          sigma from depth + DEM + datum
PUBLIC_PROFILE_DIGITIZED sigma from drawing scale
ENGINEERING_INTERPOLATED sigma grows between anchors
```

Do not hide uncertainty from the LiDAR simulation dataset.

---

## 5. Depth conversion

If a source says depth to UGR:
```
z_UGR = z_surface - depth
```

If a source explicitly says depth to platform top:
```
z_UGR = z_surface - depth_to_platform - h_platform_above_UGR
```

Use the project/standard value for platform height appropriate to that station family. Do not assume every published station depth means platform elevation.

---

## 6. Rivers and water crossings

DEM alone does not contain river-bottom bathymetry.

For crossings of:
- Moscow River;
- Moscow Canal;
- Stroginsky backwater;

use, in descending priority:
1. project hydrographic/bathymetric survey;
2. published construction constraint relative to river bottom;
3. engineering-survey underwater terrain surface;
4. conservative schematic constraint with uncertainty.

Moscow engineering-survey requirements explicitly support a separate underwater terrain model joined at the water edge.

---

## 7. Quality classes for a reconstructed route

### GEO_A
Survey/project:
- exact XY;
- exact absolute Z;
- known vertical datum.

### GEO_B
Public engineering:
- accurate XY vector;
- several official/profile Z anchors;
- constrained interpolation.

### GEO_C
OSM + terrain + station depths:
- plausible route;
- correct broad relief;
- Z uncertain between anchors.

### GEO_D
Schematic reconstruction:
- visual/topological use only.

The procedural generator should include `geo_quality` in scene/export metadata.
