# Run inside Blender Text Editor.
# Creates an XY diagnostic curve and station empties for the Koltsevaya pilot.
# It does NOT create tunnel Z; all objects stay at z=0 by design.

import bpy
import csv
from pathlib import Path

BASE = Path(__file__).resolve().parent if "__file__" in globals() else Path(bpy.path.abspath("//"))
ALIGN = BASE / "alignment_xy_station_spline_25m.csv"
STATIONS = BASE / "stations.csv"

COLL_NAME = "KOLTSEVAYA_V0_PLAN"

def collection(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c

def clear_collection(c):
    for obj in list(c.objects):
        bpy.data.objects.remove(obj, do_unlink=True)

c = collection(COLL_NAME)
clear_collection(c)

pts=[]
with ALIGN.open(encoding="utf-8") as f:
    for r in csv.DictReader(f):
        pts.append((float(r["x_m"]), float(r["y_m"]), 0.0))

curve = bpy.data.curves.new("Koltsevaya_XY_preview_curve", "CURVE")
curve.dimensions = "3D"
curve.resolution_u = 1
spl = curve.splines.new("POLY")
spl.points.add(len(pts))
for p,co in zip(spl.points, pts + [pts[0]]):
    p.co = (*co, 1.0)
obj = bpy.data.objects.new("Koltsevaya_XY_preview", curve)
c.objects.link(obj)
obj["geo_quality"] = "GEO_D"
obj["warning"] = "Station-anchor spline preview only; not OSM/as-built track geometry; z unresolved."

with STATIONS.open(encoding="utf-8") as f:
    for r in csv.DictReader(f):
        e = bpy.data.objects.new(f'ST_{r["code"]}_{r["name"]}', None)
        e.empty_display_type = "SPHERE"
        e.empty_display_size = 20.0
        e.location = (float(r["local_x_m"]), float(r["local_y_m"]), 0.0)
        e["station_code"] = r["code"]
        e["published_depth_m"] = float(r["published_depth_m"])
        e["depth_semantics"] = r["depth_semantics"]
        c.objects.link(e)

print(f"Created {len(pts)} route samples and station anchors in {COLL_NAME}.")
