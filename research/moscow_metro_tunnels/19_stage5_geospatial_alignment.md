# Stage 5 — georeferenced network alignment and 3D route pipeline

Research snapshot: 2026-09-19.

## Result

A practical public-data route pipeline is now defined:

```
OSM/subway vector XY
+ metric reprojection
+ terrain DEM
+ sparse project/depth/profile Z anchors
+ SP geometric constraints
= uncertainty-aware 3D UGR alignment
```

The output is a local-metre route file consumed by Blender.

## Concrete public sources

### Network plan
Current Moscow vector extract:
https://download.bbbike.org/osm/bbbike/Moscow/

Recommended raw file:
https://download.bbbike.org/osm/bbbike/Moscow/Moscow.osm.pbf

OSM physical track:
`railway=subway`.

OSM is not survey-grade for underground geometry. It is treated as a public XY approximation with provenance/uncertainty.

### Surface elevation
Copernicus GLO-30:
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

FABDEM:
https://research-information.bris.ac.uk/en/datasets/fabdem-v1-2/

### Project-quality terrain input
Moscow engineering-survey deliverables use LandXML terrain models and can include XYZ laser-scanning point clouds:
https://www.mos.ru/upload/documents/files/1115/06_TrebovaniyakrezyltatamII_10.pdf

The generator now has a defined upgrade path from global DEM to project survey without changing Blender logic.

## Concrete Moscow vertical-profile evidence

Public engineering literature contains an actual Moscow longitudinal profile + plan for the Kievskaya–Delovoy Tsentr mini-metro alignment (Fig. 1.7):
https://ru.djvu.online/file/pGZH0qOLpAG0I

Official Moscow construction materials provide sparse quantitative constraints such as:
- Karamyshevskaya / Narodnogo Opolcheniya tunnel: 1838 m, minimum depth about 44 m, ~13 m between tunnel crown and Moscow Canal bottom at crossing;
- Sokolniki–Rizhskaya BCL: 2.25 km tunnel, construction depth ~25–45 m;
- Rublyovo-Arkhangelskaya public materials identify the large two-track route under the Moscow River/Stroginsky backwater and provide profile schematics.

These constraints are suitable as anchors/inequalities rather than a complete as-built Z trace.

## Vertical datums

Copernicus DEM: EGM2008.

Russian state engineering heights: Baltic Height System 1977.

The pipeline must transform/calibrate vertical datums before computing tunnel depth/overburden.

## Current SP constraints encoded for reconstruction

Horizontal:
- main-track normal minimum circular radius: 600 m;
- difficult conditions: 300 m;
- main-track R<=2000 m normally uses transition curves;
- transition/cant values are radius-dependent.

Vertical:
- ordinary minimum grade: 3 per mille;
- difficult minimum: 2 per mille;
- justified horizontal elements allowed;
- underground maximum: 40 per mille;
- difficult short sections: up to 45 per mille;
- vertical curve radius:
  - 3000 m near station;
  - 5000 m interstation;
  - difficult: 2000/3000 m;
  - 1500 m connecting tracks.

## Reference implementation

Added:
- `reference_impl/tunnel_pcg_ref/alignment3d.py`;
- `reference_impl/tests/test_alignment3d.py`;
- `reference_impl/schemas/route_alignment.schema.json`.

Functions include:
- XY chainage;
- polyline resampling;
- station-to-track projection;
- grade calculation;
- explicit depth-datum conversion;
- preliminary profile interpolation;
- vertical-curve tangent geometry;
- local-origin conversion;
- parallel-transport 3D frames;
- cant rotation.

Stage-5 alignment kernel was tested independently:
- **7/7 tests passed**;
- `compileall` passed.

The piecewise-linear Z interpolator is explicitly marked preliminary; a final reconstruction must replace grade breaks with validated vertical curves.

## Blender rule

Blender receives already reconstructed:
- local XYZ in metres;
- chainage;
- UGR;
- cant;
- curvature/radius;
- uncertainty/provenance.

Blender does not perform:
- WGS84 projection;
- vertical-datum transformation;
- DEM mosaicking;
- station-depth interpretation.

This separation is necessary for deterministic and auditable synthetic LiDAR geometry.
