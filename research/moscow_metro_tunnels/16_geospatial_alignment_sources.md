# Geospatial route / station / terrain sources for Moscow Metro

Research snapshot: 2026-09-19.

Goal: reconstruct a credible 3D engineering alignment for procedural tunnel generation. This requires **two independent datasets**:

1. horizontal plan XY — where the tracks run in map coordinates;
2. vertical profile Z — rail-head elevation versus chainage.

A terrain DEM alone cannot provide tunnel elevation. It only provides the surface.

---

## 1. Horizontal alignment: OpenStreetMap is the best public base

### OSM semantics

OpenStreetMap maps metro infrastructure with:

- `railway=subway` — physical track;
- `railway=station + station=subway` — station;
- `route=subway` — passenger route relation;
- `route_master=subway` — grouping of route directions/variants.

Sources:
- https://wiki.openstreetmap.org/wiki/Metro
- https://wiki.openstreetmap.org/wiki/Metro_Mapping
- https://wiki.openstreetmap.org/wiki/Tag:railway%3DSubway
- https://wiki.openstreetmap.org/wiki/Tag:route%3Dsubway

### Accuracy warning

OSM underground tracks are **not survey control**.

The OSM metro-mapping documentation explicitly allows contributors to omit exact underground tracks when they are unknown and to sketch smooth connections between stations. Therefore:

- OSM is strong for network topology and a good public approximation of XY;
- surface/elevated sections are often more geometrically reliable;
- underground curvature must be assigned an uncertainty class;
- do not claim centimetre- or metre-level engineering accuracy from OSM alone.

Use OSM geometry as:
`PUBLIC_XY_ALIGNMENT`, not `AS_BUILT_SURVEY`.

---

## 2. Ready current Moscow OSM extracts

BBBike publishes Moscow extracts updated on a continuing basis.

Index:
https://download.bbbike.org/osm/bbbike/Moscow/

Current available formats include:
- PBF: `Moscow.osm.pbf`;
- compressed OSM XML;
- Esri Shapefile;
- Osmium GeoJSON;
- GeoParquet;
- GeoPackage;
- CSV.

Recommended:
- PBF for authoritative OSM topology and relation membership;
- GeoPackage/GeoJSON for GIS inspection;
- never use rendered map pixels when vector OSM is available.

Direct PBF:
https://download.bbbike.org/osm/bbbike/Moscow/Moscow.osm.pbf

Direct GeoJSON archive:
https://download.bbbike.org/osm/bbbike/Moscow/Moscow.osm.geojson.xz

Direct GeoPackage:
https://download.bbbike.org/osm/bbbike/Moscow/Moscow.osm.geopackage.zip

BBBike/OSM licence requirements must be retained in project metadata.

### Example extraction with osmium

```bash
osmium tags-filter Moscow.osm.pbf \
  w/railway=subway \
  n/railway=station \
  n/station=subway \
  r/route=subway \
  r/route_master=subway \
  -o moscow_metro.osm.pbf
```

By default keep referenced nodes/members so physical way geometry remains complete.

For route generation, prefer physical `railway=subway` ways over a simplified line schematic.

---

## 3. Line relations

Do not hard-code the old 2018 Moscow OSM Wiki relation table for production; relation organization changes as lines grow.

A useful current cross-check is Wikidata, which stores OSM relation identifiers for many lines. Example:

- Sokolnicheskaya Line Wikidata Q729631 currently gives OSM relation ID **1475758**.

Source:
https://www.wikidata.org/wiki/Q729631

The acquisition tool should discover current relations by tags/name/ref and keep the relation ID as provenance.

---

## 4. Stations and official Moscow open data

Moscow's Open Data ecosystem contains/has contained datasets for:
- metro lines;
- station entrances/exits;
- station-related transport data.

Transport Moscow itself has documented using Moscow Open Data for station locations in public analytical products.

Relevant sources:
- https://data.mos.ru/
- historical/current dataset lineage: `Линии Московского метрополитена`, dataset 2278;
- `Входы и выходы вестибюлей станций Московского метрополитена`.

Because the portal/API changes over time, implement it as an **optional official station-anchor source**, not the sole pipeline dependency.

Use station coordinates to:
- validate OSM station ordering;
- snap route station chainage;
- detect gross OSM displacement.

Do not use vestibule/entrance coordinates as platform/tunnel centerline.

---

## 5. Geographic visual maps

Moscow Transport and public metro archives publish geographically tied metro maps and track-development diagrams. These are useful as **visual QA**, not as vector control geometry.

Use them to check:
- correct side of river/road;
- branch topology;
- line order;
- approximate station placement;
- obvious OSM errors.

Never digitize a raster transit schematic when vector OSM is available.

---

## 6. Terrain / surface elevation

### Copernicus DEM GLO-30

Official Copernicus product:
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

Properties:
- global 30 m grid for GLO-30;
- DSM, therefore includes buildings, infrastructure and vegetation;
- WGS84 horizontal coordinates;
- EGM2008 vertical reference;
- absolute vertical accuracy stated as <4 m at 90% linear error;
- relative vertical accuracy <2 m on slopes <=20%.

For Moscow tunnel reconstruction it is suitable for:
- broad terrain shape;
- river-valley relief;
- station-to-station surface profile;
- approximate overburden.

It is **not** suitable as a final engineering terrain model around streets/buildings.

### FABDEM V1-2

University of Bristol:
https://research-information.bris.ac.uk/en/datasets/fabdem-v1-2/

FABDEM removes modeled building and forest-height bias from Copernicus GLO-30 and remains approximately 30 m resolution.

This is usually more useful for a synthetic **bare-earth** surface profile through urban Moscow than raw Copernicus DSM.

Important licence:
FABDEM V1-2 is CC BY-NC-SA 4.0; commercial use requires separate attention. Do not silently include it in a commercial asset pipeline.

### Recommended priority

1. project engineering LandXML / surveyed points if legally available;
2. Moscow engineering survey terrain model if supplied with the project;
3. FABDEM for research/non-commercial bare-earth reconstruction;
4. Copernicus GLO-30 when an openly usable DSM is acceptable;
5. SRTM/NASADEM only as fallback.

---

## 7. What Moscow engineering survey data should look like

Official Moscow requirements for engineering-geodetic deliverables specify:

- digital terrain model in **LandXML**;
- surface elevation points in SHAPE;
- optionally laser-scanning point clouds in XYZ;
- water-body underwater surfaces as separate terrain models when surveyed.

Source:
https://www.mos.ru/upload/documents/files/1115/06_TrebovaniyakrezyltatamII_10.pdf

This is the **gold-standard input format** to support later, even if public download is unavailable.

If the user later obtains:
- `*.xml` LandXML;
- DWG/DGN topography;
- CSV survey points;
- XYZ point cloud;

the same alignment pipeline should accept those and supersede global DEM data.

---

## 8. Horizontal CRS

Raw OSM:
- WGS84 longitude/latitude (EPSG:4326).

Recommended preprocessing:
- transform Moscow data into UTM zone 37N, EPSG:32637, or a project-defined engineering CRS;
- then subtract a local origin before exporting to Blender.

Do not feed WGS84 degrees directly to Blender.

Do not keep UTM easting/northing values of hundreds of kilometres as scene coordinates for long LiDAR simulation runs; use a floating local origin.

Suggested structure:

```
source_crs = EPSG:4326
engineering_crs = EPSG:32637
local_origin = [E0, N0, H0]
blender_xyz = engineering_xyz - local_origin
```

For official Moscow engineering data, preserve its original local coordinate-system metadata instead of forcing it through OSM/UTM.

---

## 9. Vertical datum — critical warning

Copernicus DEM uses **EGM2008** orthometric heights.

Russian engineering/project documentation can use the **Baltic Height System 1977 (БСВ-77)**. The Russian state height system is BSV-77, referenced to the Kronstadt datum.

Sources:
- https://base.garant.ru/71549536/
- Moscow information-model requirements: https://www.mos.ru/upload/documents/files/1672/Prilojenie2_TrebovaniyakIMlineinogoobekta-Injenernieseti.pdf

Therefore:

**never subtract a BSV-77 rail elevation directly from an EGM2008 DEM elevation without a vertical-datum transformation/calibration.**

Recommended hierarchy:
1. transform with an authoritative vertical grid if available;
2. otherwise calibrate a local vertical offset against surveyed/common control points;
3. if neither exists, flag absolute Z as uncertain and use only relative profile shape.

Store:
`vertical_datum` on every surface/profile source.

---

## 10. Public source confidence for 3D route generation

| Data | Typical role | Confidence |
|---|---|---|
| project survey / LandXML | XY+surface Z | A/project |
| project longitudinal profile | tunnel Z and grades | A/project |
| OSM physical subway ways | public XY | B/C |
| official station coordinate | station XY anchor | B |
| official published station/tunnel depth | sparse Z constraint | B |
| engineering book profile drawing | plan/profile reconstruction | C |
| Copernicus/FABDEM | surface Z | B/C for broad terrain |
| depth infographic / enthusiast map | visual Z cross-check | D |

A high-fidelity synthetic route should expose this provenance per chainage interval.
