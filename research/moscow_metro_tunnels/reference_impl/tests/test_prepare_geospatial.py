import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import from_origin

from tools_prepare_geospatial import prepare


class GeospatialPrepareTests(unittest.TestCase):
    def test_prepare_synthetic_route_and_dem(self):
        with tempfile.TemporaryDirectory() as td_raw:
            td = Path(td_raw)
            route = {
                "type": "LineString",
                "coordinates": [[37.60, 55.75], [37.601, 55.751]],
            }
            (td / "route.geojson").write_text(
                json.dumps(route), encoding="utf-8"
            )

            arr = np.full((100, 100), 150, dtype="float32")
            transform = from_origin(37.59, 55.76, 0.0002, 0.0002)
            with rasterio.open(
                td / "dem.tif",
                "w",
                driver="GTiff",
                height=100,
                width=100,
                count=1,
                dtype="float32",
                crs="EPSG:4326",
                transform=transform,
            ) as ds:
                ds.write(arr, 1)

            result = prepare(
                str(td / "route.geojson"),
                str(td / "dem.tif"),
                str(td / "out.json"),
                step_m=20,
                surface_vertical_datum="EGM2008",
                route_id="test",
            )

            self.assertGreater(len(result["samples"]), 2)
            self.assertEqual(result["samples"][0]["x_m"], 0)
            self.assertEqual(result["samples"][0]["y_m"], 0)
            self.assertTrue(
                all(
                    abs(s["surface_z_m"] - 150) < 1e-6
                    for s in result["samples"]
                )
            )
            self.assertTrue(
                all(s["z_ugr_m"] is None for s in result["samples"])
            )


if __name__ == "__main__":
    unittest.main()
