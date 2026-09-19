from __future__ import annotations

import argparse
import json
from pathlib import Path

from pyproj import CRS, Transformer
import rasterio
from shapely.geometry import LineString, MultiLineString, shape
from shapely.ops import linemerge, transform as shp_transform


def load_single_route_geojson(path: str | Path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("type") == "FeatureCollection":
        geoms = [
            shape(f["geometry"])
            for f in data["features"]
            if f.get("geometry")
        ]
        if not geoms:
            raise ValueError("GeoJSON has no geometry")
        geom = linemerge(geoms) if len(geoms) > 1 else geoms[0]
    elif data.get("type") == "Feature":
        geom = shape(data["geometry"])
    else:
        geom = shape(data)

    if isinstance(geom, MultiLineString):
        merged = linemerge(geom)
        if isinstance(merged, MultiLineString):
            raise ValueError(
                "route is disconnected; split into explicit route/track files"
            )
        geom = merged

    if not isinstance(geom, LineString):
        raise ValueError("route geometry must be LineString")
    return geom


def resample_line(line: LineString, step_m: float):
    if step_m <= 0:
        raise ValueError("step must be positive")
    s = 0.0
    out = []
    while s < line.length:
        p = line.interpolate(s)
        out.append((s, p.x, p.y))
        s += step_m
    p = line.interpolate(line.length)
    out.append((line.length, p.x, p.y))
    return out


def prepare(
    track_geojson: str,
    dem_path: str,
    out_json: str,
    *,
    target_crs: str = "EPSG:32637",
    step_m: float = 2.0,
    surface_vertical_datum: str = "UNKNOWN",
    route_id: str = "route",
):
    """Prepare local-metre XY + surface-Z samples.

    GeoJSON is treated as RFC 7946 WGS84. The tool intentionally leaves
    z_ugr_m null: tunnel elevation must be solved from explicit vertical
    anchors after vertical-datum reconciliation.
    """
    src_crs = CRS.from_epsg(4326)
    dst_crs = CRS.from_user_input(target_crs)

    route_ll = load_single_route_geojson(track_geojson)
    tx = Transformer.from_crs(src_crs, dst_crs, always_xy=True)
    route_xy = shp_transform(tx.transform, route_ll)
    samples = resample_line(route_xy, step_m)

    with rasterio.open(dem_path) as ds:
        if ds.crs is None:
            raise ValueError("DEM CRS missing")
        xy_to_dem = Transformer.from_crs(dst_crs, ds.crs, always_xy=True)
        dem_xy = [xy_to_dem.transform(x, y) for _, x, y in samples]
        values = [float(v[0]) for v in ds.sample(dem_xy)]
        nodata = ds.nodata

    x0, y0 = samples[0][1], samples[0][2]
    valid = [v for v in values if nodata is None or v != nodata]
    if not valid:
        raise ValueError("DEM sampling returned no valid elevation")
    z0 = valid[0]

    out = []
    for (s, x, y), surface_z in zip(samples, values):
        surface = None if nodata is not None and surface_z == nodata else surface_z
        out.append(
            {
                "s_m": s,
                "x_m": x - x0,
                "y_m": y - y0,
                "z_ugr_m": None,
                "surface_z_m": surface,
                "source_class": "PUBLIC_XY+SURFACE_DEM",
            }
        )

    payload = {
        "route_id": route_id,
        "geo_quality": "GEO_C",
        "source_crs": "EPSG:4326",
        "engineering_crs": dst_crs.to_string(),
        "vertical_datum": surface_vertical_datum,
        "horizontal_source": {"path": str(track_geojson), "type": "GeoJSON"},
        "vertical_sources": [
            {
                "path": str(dem_path),
                "type": "DEM",
                "vertical_datum": surface_vertical_datum,
            }
        ],
        "local_origin": {
            "x_m": x0,
            "y_m": y0,
            "z_m": z0,
            "absolute_crs": dst_crs.to_string(),
            "vertical_datum": surface_vertical_datum,
        },
        "samples": out,
        "notes": (
            "z_ugr_m intentionally null: add/solve tunnel profile only after "
            "vertical anchors and datum reconciliation."
        ),
    }
    Path(out_json).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--track-geojson", required=True)
    ap.add_argument("--dem", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--target-crs", default="EPSG:32637")
    ap.add_argument("--step-m", type=float, default=2.0)
    ap.add_argument("--surface-vertical-datum", required=True)
    ap.add_argument("--route-id", default="route")
    a = ap.parse_args()
    prepare(
        a.track_geojson,
        a.dem,
        a.out,
        target_crs=a.target_crs,
        step_m=a.step_m,
        surface_vertical_datum=a.surface_vertical_datum,
        route_id=a.route_id,
    )


if __name__ == "__main__":
    main()
