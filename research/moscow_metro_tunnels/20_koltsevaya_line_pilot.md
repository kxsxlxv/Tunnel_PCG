# Koltsevaya Line pilot findings

Research date: 2026-09-19.

## Identity

Line: Moscow Metro Line 5, Koltsevaya.

Current public line facts:
- 12 stations;
- published line length: 19.4 km;
- current Wikidata OSM relation identifier: **1462012**;
- old OSM Wiki page still lists **300607**, so it must not be blindly used as the current route relation.

Sources:
- https://www.wikidata.org/wiki/Q831673
- https://wiki.openstreetmap.org/wiki/Moscow_Metro
- https://www.metro.ru/stations/koltsevaya/

## Pilot data created

Directory:
`examples/koltsevaya_line_v0/`

Files:
- `stations.csv` — 12 public station coordinate/depth anchors, projected to UTM 37N;
- `alignment_xy_station_spline_25m.csv` — closed 25 m XY fallback spline;
- `route_meta.json` — provenance and warnings;
- `blender_plan_preview.py` — plan-only Blender visualization;
- `tools_extract_relation.py` — relation-member extractor for a local Moscow PBF;
- `README.md`.

## Station anchors

The station order is:
1. Белорусская
2. Новослободская
3. Проспект Мира
4. Комсомольская
5. Курская
6. Таганская
7. Павелецкая
8. Добрынинская
9. Октябрьская
10. Парк культуры
11. Киевская
12. Краснопресненская
13. back to Белорусская.

Published depth anchors used in the pilot:

| Station | published depth, m |
|---|---:|
| Белорусская | 42.5 |
| Новослободская | 40 |
| Проспект Мира | 40 |
| Комсомольская | 37 |
| Курская | 40 |
| Таганская | 53 |
| Павелецкая | 40 |
| Добрынинская | 35.5 |
| Октябрьская | 40 |
| Парк культуры | 40 |
| Киевская | 53 |
| Краснопресненская | 35.5 |

Important:
these values are stored as `published_station_depth_m`, not as UGR elevations.

For Kievskaya a station-specific metro reference gives 53 m:
https://news.metro.ru/f512.html

An older aggregated station list can show 48 m, so the 53 m station-specific value is retained with a provenance warning rather than silently averaging the two.

Krasnopresnenskaya has a station-specific 35.5 m reference:
https://news.metro.ru/f511.html

## Horizontal pilot result

Because direct OSM relation bytes were unavailable in the current runtime, a temporary closed Catmull-Rom spline was generated through all 12 projected station anchors.

Result:
- length: ~18.908 km;
- official/public line length: 19.4 km;
- deficit: ~492 m, ~2.54%.

This is a strong empirical demonstration that station anchors alone are insufficient.

Intermediate physical track vertices are necessary.

The fallback spline has:
- approximate minimum sampled radius ~393 m;
- 13 samples at 25 m spacing below the normal current 600 m reference;
- no samples below the difficult-condition 300 m reference.

These radii describe the **fallback spline**, not the as-built Koltsevaya track.

## Exact OSM upgrade

Use current relation:
`r1462012`.

Recommended acquisition:

```bash
# Download/update current Moscow PBF
wget https://download.bbbike.org/osm/bbbike/Moscow/Moscow.osm.pbf

# If osmium CLI is installed, extract relation plus referenced objects.
osmium getid -r Moscow.osm.pbf r1462012 -o koltsevaya_relation.osm.pbf
```

The supplied `tools_extract_relation.py` can instead read relation 1462012 directly from the full Moscow PBF with pyosmium and export ordered member-way GeoJSON.

Do not automatically merge all relation member ways into one line:
- inner and outer directions/tracks may be separate ways;
- station/platform members may occur;
- way orientation may need correction;
- switches/depot/connecting structures may appear depending on relation structure.

The final alignment builder should classify and stitch **one physical track at a time**.

## Vertical pilot status

No false Z has been generated.

The 12 station depths are useful only after surface elevations are sampled.

Required next data layer:
- FABDEM/Copernicus/public terrain for research;
- preferably project LandXML/engineering surface when available.

Then:

```
surface_z(station)
+ explicit vertical datum
+ published/project depth datum
=> candidate UGR anchor
```

Only after that should a grade/vertical-curve solver generate the tunnel profile.

## Blender

`blender_plan_preview.py` creates:
- one closed XY route curve at z=0;
- 12 station empties;
- source/warning custom properties.

It deliberately does **not** generate tunnel geometry or fake vertical relief.

Once a resolved `alignment_3d.json` exists, the existing Stage-5 `parallel_transport_frames()` path is the correct input for rings/rails/third rail.
