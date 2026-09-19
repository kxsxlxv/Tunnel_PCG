# Blender diagnostic importer for a RESOLVED Koltsevaya 3D alignment.
#
# It refuses unresolved z_ugr_m values and requires a closed route. It does not
# generate final tunnel lining; it visualizes the engineering alignment and
# transported frames that the lining/track generators should consume.

import bpy
import json
import sys
from pathlib import Path
from mathutils import Matrix

BASE = Path(__file__).resolve().parent if "__file__" in globals() else Path(bpy.path.abspath("//"))
ALIGN = BASE / "alignment_3d.json"

REFERENCE_IMPL = BASE.parent.parent / "reference_impl"
if str(REFERENCE_IMPL) not in sys.path:
    sys.path.insert(0, str(REFERENCE_IMPL))

from tunnel_pcg_ref.alignment3d import Vec3, closed_parallel_transport_frames

COLLECTION_NAME = "KOLTSEVAYA_3D_ALIGNMENT"
FRAME_STEP_M = 100.0
CLOSURE_TOLERANCE_M = 0.25


def get_collection(name):
    coll = bpy.data.collections.get(name)
    if coll is None:
        coll = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(coll)
    return coll


def clear_collection(coll):
    for obj in list(coll.objects):
        bpy.data.objects.remove(obj, do_unlink=True)


def load_alignment(path):
    data = json.loads(path.read_text(encoding="utf-8"))
    samples = data.get("samples")
    if not isinstance(samples, list) or len(samples) < 4:
        raise RuntimeError("alignment_3d.json needs at least 4 samples")

    unresolved = [
        i for i, p in enumerate(samples)
        if p.get("z_ugr_m") is None
    ]
    if unresolved:
        head = ", ".join(map(str, unresolved[:10]))
        raise RuntimeError(
            "Refusing to create 3D route: unresolved z_ugr_m at sample "
            f"indices {head}" + ("..." if len(unresolved) > 10 else "")
        )

    points = [
        Vec3(float(p["x_m"]), float(p["y_m"]), float(p["z_ugr_m"]))
        for p in samples
    ]

    if (points[-1] - points[0]).norm() > CLOSURE_TOLERANCE_M:
        raise RuntimeError(
            "Koltsevaya alignment is not geometrically closed: "
            f"seam distance={(points[-1] - points[0]).norm():.3f} m"
        )

    points[-1] = points[0]
    return data, samples, points


def create_poly_curve(coll, points):
    curve = bpy.data.curves.new("Koltsevaya_UGR_alignment_curve", "CURVE")
    curve.dimensions = "3D"
    curve.resolution_u = 1

    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for dst, p in zip(spline.points, points):
        dst.co = (p.x, p.y, p.z, 1.0)

    obj = bpy.data.objects.new("Koltsevaya_UGR_alignment", curve)
    coll.objects.link(obj)
    return obj


def frame_matrix(frame):
    t, l, u, p = frame.tangent, frame.left, frame.up, frame.p
    return Matrix((
        (t.x, l.x, u.x, p.x),
        (t.y, l.y, u.y, p.y),
        (t.z, l.z, u.z, p.z),
        (0.0, 0.0, 0.0, 1.0),
    ))


def create_frame_diagnostics(coll, frames, samples):
    last_s = -1e30
    created = 0
    for frame, sample in zip(frames, samples):
        s = float(sample["s_m"])
        if s - last_s < FRAME_STEP_M and created:
            continue
        empty = bpy.data.objects.new(f"FRAME_{s:09.1f}m", None)
        empty.empty_display_type = "ARROWS"
        empty.empty_display_size = 2.0
        empty.matrix_world = frame_matrix(frame)
        empty["chainage_m"] = s
        empty["source_class"] = sample.get("source_class", "")
        empty["sigma_xy_m"] = sample.get("sigma_xy_m")
        empty["sigma_z_m"] = sample.get("sigma_z_m")
        coll.objects.link(empty)
        last_s = s
        created += 1
    return created


def main():
    if not ALIGN.exists():
        raise RuntimeError(
            f"{ALIGN.name} not found. Generate a resolved 3D alignment first."
        )

    data, samples, points = load_alignment(ALIGN)
    frames, raw_holonomy_rad = closed_parallel_transport_frames(points)

    coll = get_collection(COLLECTION_NAME)
    clear_collection(coll)

    route_obj = create_poly_curve(coll, points)
    route_obj["route_id"] = data.get("route_id", "unknown")
    route_obj["geo_quality"] = data.get("geo_quality", "unknown")
    route_obj["raw_frame_holonomy_rad"] = raw_holonomy_rad
    route_obj["frame_solver"] = "closed_parallel_transport_frames"
    route_obj["warning"] = (
        "Alignment visualization only. Lining generation must use the same "
        "engineering frames and source provenance."
    )

    frame_count = create_frame_diagnostics(coll, frames, samples)
    print(
        f"Loaded {len(points)} 3D samples; "
        f"created {frame_count} frame diagnostics; "
        f"raw holonomy={raw_holonomy_rad:.9g} rad"
    )


main()
