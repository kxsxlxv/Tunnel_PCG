from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from typing import Sequence

from .geometry import (
    Line2, Vec2, circle_tangent_point, intersect_offset_lines,
    line_circle_intersections, mirror_closed_half_profile, polygon_area_centroid,
    sample_arc, sample_line, stitch,
)


@dataclass(frozen=True)
class RailSpec:
    name: str
    H: float
    A: float
    B: float
    head_construction_width: float
    head_side_drop: float
    head_virtual_depth: float
    nominal_head_width: float
    head_lower_outer_radius: float
    head_lower_inner_radius: float
    line_center_drop_from_top: float
    web_thickness: float
    upper_web_radius: float
    lower_web_radius: float
    foot_virtual_height: float
    foot_inner_radius: float
    base_width: float
    base_edge_height: float
    foot_outer_upper_radius: float
    foot_outer_lower_radius: float
    target_area_m2: float
    target_centroid_z_m: float


R50 = RailSpec(
    name="R50", H=0.152, A=0.0200541, B=0.0456848,
    head_construction_width=0.07024, head_side_drop=0.0154,
    head_virtual_depth=0.042, nominal_head_width=0.07159,
    head_lower_outer_radius=0.005, head_lower_inner_radius=0.010,
    line_center_drop_from_top=0.0835, web_thickness=0.016,
    upper_web_radius=0.325, lower_web_radius=0.350,
    foot_virtual_height=0.027, foot_inner_radius=0.020,
    base_width=0.132, base_edge_height=0.0105,
    foot_outer_upper_radius=0.004, foot_outer_lower_radius=0.002,
    target_area_m2=0.006599, target_centroid_z_m=0.07050,
)

R65 = RailSpec(
    name="R65", H=0.180, A=0.0200328, B=0.0490859,
    head_construction_width=0.07300, head_side_drop=0.01567,
    head_virtual_depth=0.045, nominal_head_width=0.07459,
    head_lower_outer_radius=0.005, head_lower_inner_radius=0.012,
    line_center_drop_from_top=0.0975, web_thickness=0.018,
    upper_web_radius=0.370, lower_web_radius=0.400,
    foot_virtual_height=0.030, foot_inner_radius=0.025,
    base_width=0.150, base_edge_height=0.01125,
    foot_outer_upper_radius=0.004, foot_outer_lower_radius=0.002,
    target_area_m2=0.008265, target_centroid_z_m=0.08130,
)


@dataclass(frozen=True)
class Primitive:
    kind: str
    start: Vec2
    end: Vec2
    center: Vec2 | None = None
    radius: float | None = None
    label: str = ""


def reconstruct_half_primitives(spec: RailSpec) -> list[Primitive]:
    """Engineering reconstruction of GOST Appendix G tangent chain."""
    H = spec.H
    c500 = Vec2(0.0, H - 0.500)
    top = Vec2(0.0, H)
    xA = spec.A / 2.0
    p1 = Vec2(xA, c500.z + sqrt(0.500**2 - xA**2))
    c80 = p1 + (c500 - p1) * (0.080 / 0.500)
    xB = spec.B / 2.0
    p2 = Vec2(xB, c80.z + sqrt(0.080**2 - (xB - c80.x)**2))
    c15 = p2 + (c80 - p2) * (0.015 / 0.080)
    p3 = Vec2(spec.head_construction_width / 2.0, H - spec.head_side_drop)

    side = Line2.through(p3, Vec2(1.0, -20.0))
    underside = Line2.through(Vec2(0.0, H - spec.head_virtual_depth), Vec2(-4.0, -1.0))
    r5 = spec.head_lower_outer_radius
    c5 = intersect_offset_lines(side, -r5, underside, -r5)
    p4 = side.project(c5)
    p5 = underside.project(c5)

    zc = H - spec.line_center_drop_from_top
    xw = spec.web_thickness / 2.0
    c_up = Vec2(xw + spec.upper_web_radius, zc)
    r12 = spec.head_lower_inner_radius
    c12_candidates = line_circle_intersections(underside, +r12, c_up, spec.upper_web_radius - r12)
    c12 = min((p for p in c12_candidates if 0.0 < p.x < 0.060), key=lambda p: abs(p.z - (H - spec.head_virtual_depth - 0.006)))
    p6 = underside.project(c12)
    p7 = circle_tangent_point(c_up, spec.upper_web_radius, c12)
    pmid = Vec2(xw, zc)

    c_low = Vec2(xw + spec.lower_web_radius, zc)
    base = Line2.through(Vec2(0.0, spec.foot_virtual_height), Vec2(4.0, -1.0))
    rf = spec.foot_inner_radius
    cf_candidates = line_circle_intersections(base, +rf, c_low, spec.lower_web_radius - rf)
    cf = min((p for p in cf_candidates if 0.0 < p.x < 0.080), key=lambda p: abs(p.z - (spec.foot_virtual_height + 0.017)))
    p8 = circle_tangent_point(c_low, spec.lower_web_radius, cf)
    p9 = base.project(cf)

    halfbase = spec.base_width / 2.0
    side_base = Line2.through(Vec2(halfbase, 0.0), Vec2(0.0, -1.0))
    r4 = spec.foot_outer_upper_radius
    c4 = intersect_offset_lines(base, +r4, side_base, -r4)
    p10 = base.project(c4)
    p11 = side_base.project(c4)

    r2 = spec.foot_outer_lower_radius
    c2 = Vec2(halfbase - r2, r2)
    p12 = Vec2(halfbase, r2)
    p13 = Vec2(halfbase - r2, 0.0)
    bottom = Vec2(0.0, 0.0)

    return [
        Primitive("arc", top, p1, c500, 0.500, "head_R500"),
        Primitive("arc", p1, p2, c80, 0.080, "head_R80"),
        Primitive("arc", p2, p3, c15, 0.015, "head_R15"),
        Primitive("line", p3, p4, label="head_side_1_20"),
        Primitive("arc", p4, p5, c5, r5, "head_lower_outer"),
        Primitive("line", p5, p6, label="head_underside_1_4"),
        Primitive("arc", p6, p7, c12, r12, "head_web_fillet"),
        Primitive("arc", p7, pmid, c_up, spec.upper_web_radius, "upper_web"),
        Primitive("arc", pmid, p8, c_low, spec.lower_web_radius, "lower_web"),
        Primitive("arc", p8, p9, cf, rf, "web_foot_fillet"),
        Primitive("line", p9, p10, label="foot_top_1_4"),
        Primitive("arc", p10, p11, c4, r4, "foot_outer_R4"),
        Primitive("line", p11, p12, label="foot_outer_side"),
        Primitive("arc", p12, p13, c2, r2, "foot_outer_R2"),
        Primitive("line", p13, bottom, label="foot_bottom"),
    ]


def sample_half_profile(spec: RailSpec, chord_error_m: float = 0.00005) -> list[Vec2]:
    parts = []
    for p in reconstruct_half_primitives(spec):
        if p.kind == "line":
            parts.append(sample_line(p.start, p.end))
        else:
            assert p.center is not None and p.radius is not None
            parts.append(sample_arc(p.center, p.radius, p.start, p.end, chord_error_m))
    return stitch(parts)


def sample_closed_profile(spec: RailSpec, chord_error_m: float = 0.00005) -> list[Vec2]:
    return mirror_closed_half_profile(sample_half_profile(spec, chord_error_m))


def validation_metrics(spec: RailSpec, chord_error_m: float = 0.00001) -> dict[str, float]:
    poly = sample_closed_profile(spec, chord_error_m)
    area_signed, centroid = polygon_area_centroid(poly)
    area = abs(area_signed)
    max_x = max(abs(p.x) for p in poly)
    max_head_x = max(abs(p.x) for p in poly if p.z > spec.H - spec.head_virtual_depth)
    return {
        "height_m": max(p.z for p in poly) - min(p.z for p in poly),
        "base_width_m": 2.0 * max_x,
        "head_width_m": 2.0 * max_head_x,
        "area_m2": area,
        "area_rel_error": (area - spec.target_area_m2) / spec.target_area_m2,
        "centroid_z_m": centroid.z,
        "centroid_z_error_m": centroid.z - spec.target_centroid_z_m,
    }
