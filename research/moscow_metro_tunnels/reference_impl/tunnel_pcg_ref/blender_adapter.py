from __future__ import annotations

"""Optional Blender bridge.

This module is deliberately tiny. The pure-Python engineering kernel remains testable without bpy.
Run/import this file only inside Blender.
"""

from .geometry import Vec2
from .rail_profiles import RailSpec, sample_closed_profile


def _bpy():
    try:
        import bpy  # type: ignore
    except ImportError as exc:
        raise RuntimeError("blender_adapter requires execution inside Blender") from exc
    return bpy


def create_profile_mesh(name: str, points: list[Vec2], x_m: float = 0.0):
    """Create a planar cross-section mesh in Blender coordinates X=chainage,Y=lateral,Z=up."""
    bpy = _bpy()
    verts = [(x_m, p.x, p.z) for p in points]
    face = list(range(len(verts)))
    mesh = bpy.data.meshes.new(name + "_mesh")
    mesh.from_pydata(verts, [], [face])
    mesh.update()
    obj = bpy.data.objects.new(name, mesh)
    bpy.context.collection.objects.link(obj)
    return obj


def create_rail_section(name: str, spec: RailSpec, chord_error_m: float = 0.00005):
    return create_profile_mesh(name, sample_closed_profile(spec, chord_error_m))


def profile_curve_object(name: str, points: list[Vec2], x_m: float = 0.0):
    """Create a closed POLY spline suitable for bevel/sweep experiments."""
    bpy = _bpy()
    curve = bpy.data.curves.new(name + "_curve", type="CURVE")
    curve.dimensions = "2D"
    curve.resolution_u = 1
    spline = curve.splines.new("POLY")
    spline.points.add(len(points) - 1)
    for dst, p in zip(spline.points, points):
        dst.co = (x_m, p.x, p.z, 1.0)
    spline.use_cyclic_u = True
    obj = bpy.data.objects.new(name, curve)
    bpy.context.collection.objects.link(obj)
    return obj
