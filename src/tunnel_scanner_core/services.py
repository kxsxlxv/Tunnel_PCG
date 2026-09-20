from __future__ import annotations

"""Modern Moscow tunnel service/cable geometry for Stage 10.5."""

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

from .mesh import Face, Vec3
from .moscow import MoscowStage10Profile


@dataclass(frozen=True)
class LocalServiceMesh:
    name_suffix: str
    object_type: str
    category: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    properties: Mapping[str, Any] = field(default_factory=dict)


def cable_rack_chainages(
    total_length_m: float,
    profile: MoscowStage10Profile,
) -> tuple[float, ...]:
    """One cable-rack station at the midpoint of every Moscow civil ring.

    This includes a final partial civil ring. The machine-profile phase remains
    0.5 m for full 1.0 m rings, but a 0.5 m terminal ring correctly receives a
    rack at its own 0.25 m midpoint instead of being silently skipped.
    """
    rack = profile.cable_rack
    if not math.isfinite(total_length_m) or total_length_m <= 0.0:
        raise ValueError("total_length_m must be finite and positive")
    if not math.isclose(
        rack.repeat_pitch_m,
        profile.ring_pitch_m,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "modern cable-rack repeat pitch must match Moscow civil-ring pitch"
        )
    if not math.isclose(
        rack.phase_m,
        0.5 * rack.repeat_pitch_m,
        abs_tol=1e-12,
    ):
        raise ValueError(
            "modern cable-rack full-ring phase must be half the repeat pitch"
        )

    result: list[float] = []
    start = 0.0
    while start < total_length_m - 1e-12:
        end = min(total_length_m, start + rack.repeat_pitch_m)
        result.append(0.5 * (start + end))
        start = end
    return tuple(result)


def _rack_center_angle(
    profile: MoscowStage10Profile,
    side_sign: int,
) -> float:
    if side_sign not in (-1, 1):
        raise ValueError("side_sign must be +/-1")
    rack = profile.cable_rack
    core_z = (
        rack.center_profile_z_m
        + profile.coordinate.profile_z_to_core_z_offset_m
    )
    r = profile.intrados_radius_m
    if abs(core_z) >= r:
        raise ValueError("cable rack center lies outside intrados")
    x_abs = math.sqrt(r * r - core_z * core_z)
    a = math.atan2(side_sign * x_abs, core_z)
    if a < 0.0:
        a += 2.0 * math.pi
    return a


def _horn_angle(
    profile: MoscowStage10Profile,
    side_sign: int,
    level_index: int,
) -> float:
    rack = profile.cable_rack
    if not (0 <= level_index < rack.horn_count):
        raise ValueError("cable-rack level index outside range")
    centered = level_index - 0.5 * (rack.horn_count - 1)
    vertical_arc_offset = centered * rack.horn_pitch_m
    return (
        _rack_center_angle(profile, side_sign)
        - side_sign * vertical_arc_offset / profile.intrados_radius_m
    )


def _extrude_y_polygon(
    points_xz: Sequence[tuple[float, float]],
    *,
    half_y_m: float,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    if len(points_xz) < 3:
        raise ValueError("service polygon needs >=3 points")
    n = len(points_xz)
    vertices = tuple(
        [(x, -half_y_m, z) for x, z in points_xz]
        + [(x, +half_y_m, z) for x, z in points_xz]
    )
    faces: list[Face] = [
        tuple(reversed(tuple(range(n)))),
        tuple(n + i for i in range(n)),
    ]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return vertices, tuple(faces)


def _combine(
    meshes: Sequence[tuple[Sequence[Vec3], Sequence[Face]]],
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    vertices: list[Vec3] = []
    faces: list[Face] = []
    for mv, mf in meshes:
        base = len(vertices)
        vertices.extend(tuple(map(float, v)) for v in mv)
        faces.extend(tuple(base + i for i in face) for face in mf)
    return tuple(vertices), tuple(faces)


def _annular_strip_mesh(
    *,
    radius_outer_m: float,
    radial_thickness_m: float,
    angles: Sequence[float],
    half_y_m: float,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    if len(angles) < 2:
        raise ValueError("annular strip requires >=2 angular samples")
    ro = radius_outer_m
    ri = ro - radial_thickness_m
    if ri <= 0.0:
        raise ValueError("annular strip inner radius must be positive")
    sections: list[tuple[float, float]] = []
    # Closed XZ polygon: outer arc bottom->top, inner arc top->bottom.
    for a in angles:
        sections.append((ro * math.sin(a), ro * math.cos(a)))
    for a in reversed(angles):
        sections.append((ri * math.sin(a), ri * math.cos(a)))
    return _extrude_y_polygon(sections, half_y_m=half_y_m)


def _ribbon_u_cup_polygon(
    *,
    center_x_m: float,
    center_z_m: float,
    inward_x: float,
    inward_z: float,
    up_x: float,
    up_z: float,
    radius_m: float,
    thickness_m: float,
    segments: int = 5,
) -> tuple[tuple[float, float], ...]:
    if segments < 3:
        raise ValueError("horn cup segments must be >=3")
    outer_r = radius_m + 0.5 * thickness_m
    inner_r = radius_m - 0.5 * thickness_m
    if inner_r <= 0.0:
        raise ValueError("horn thickness exceeds cup radius")

    def point(r: float, theta: float) -> tuple[float, float]:
        h = r * math.cos(theta)
        v = r * math.sin(theta)
        return (
            center_x_m + inward_x * h + up_x * v,
            center_z_m + inward_z * h + up_z * v,
        )

    outer = [
        point(outer_r, math.pi + math.pi * i / segments)
        for i in range(segments + 1)
    ]
    inner = [
        point(inner_r, 2.0 * math.pi - math.pi * i / segments)
        for i in range(segments + 1)
    ]
    return tuple((*outer, *inner))


def _radial_arm_polygon(
    *,
    wall_x_m: float,
    wall_z_m: float,
    inward_x: float,
    inward_z: float,
    up_x: float,
    up_z: float,
    length_m: float,
    thickness_m: float,
    vertical_offset_m: float,
) -> tuple[tuple[float, float], ...]:
    sx = wall_x_m + up_x * vertical_offset_m
    sz = wall_z_m + up_z * vertical_offset_m
    ex = sx + inward_x * length_m
    ez = sz + inward_z * length_m
    h = 0.5 * thickness_m
    return (
        (sx - up_x * h, sz - up_z * h),
        (ex - up_x * h, ez - up_z * h),
        (ex + up_x * h, ez + up_z * h),
        (sx + up_x * h, sz + up_z * h),
    )


def build_r2k11_local_rack_mesh(
    profile: MoscowStage10Profile,
    *,
    side_sign: int,
) -> LocalServiceMesh:
    rack = profile.cable_rack
    center_angle = _rack_center_angle(profile, side_sign)
    half_angle = 0.5 * rack.overall_arc_length_m / profile.intrados_radius_m
    # Keep point order from lower to upper end on either wall.
    angles = tuple(
        center_angle
        + side_sign * half_angle
        - side_sign * (2.0 * half_angle) * i / 16.0
        for i in range(17)
    )
    rack_radius = profile.intrados_radius_m - rack.shell_clearance_inward_m
    meshes = [
        _annular_strip_mesh(
            radius_outer_m=rack_radius,
            radial_thickness_m=rack.upright_thickness_m,
            angles=angles,
            half_y_m=0.5 * rack.upright_width_longitudinal_m,
        )
    ]

    for level in range(rack.horn_count):
        a = _horn_angle(profile, side_sign, level)
        sin_a = math.sin(a)
        cos_a = math.cos(a)
        wall_x = rack_radius * sin_a
        wall_z = rack_radius * cos_a
        inward = (-sin_a, -cos_a)
        up = (-side_sign * cos_a, side_sign * sin_a)

        # One continuous radial seat under both cable places.
        arm_length = (
            rack.second_cable_center_inward_m + rack.horn_radius_m
        )
        arm_poly = _radial_arm_polygon(
            wall_x_m=wall_x,
            wall_z_m=wall_z,
            inward_x=inward[0],
            inward_z=inward[1],
            up_x=up[0],
            up_z=up[1],
            length_m=arm_length,
            thickness_m=rack.horn_thickness_m,
            vertical_offset_m=-rack.horn_radius_m,
        )
        meshes.append(
            _extrude_y_polygon(
                arm_poly,
                half_y_m=0.5 * rack.horn_longitudinal_width_m,
            )
        )

        for slot_offset in (
            rack.first_cable_center_inward_m,
            rack.second_cable_center_inward_m,
        ):
            cx = wall_x + inward[0] * slot_offset
            cz = wall_z + inward[1] * slot_offset
            cup = _ribbon_u_cup_polygon(
                center_x_m=cx,
                center_z_m=cz,
                inward_x=inward[0],
                inward_z=inward[1],
                up_x=up[0],
                up_z=up[1],
                radius_m=rack.horn_radius_m,
                thickness_m=rack.horn_thickness_m,
            )
            meshes.append(
                _extrude_y_polygon(
                    cup,
                    half_y_m=0.5 * rack.horn_longitudinal_width_m,
                )
            )

    vertices, faces = _combine(meshes)
    return LocalServiceMesh(
        name_suffix=f"R2K11_{'POS' if side_sign > 0 else 'NEG'}",
        object_type="production_cable_rack_r2k11",
        category="cable_rack",
        vertices=vertices,
        faces=faces,
        properties={
            "family": rack.family,
            "sideProfileXSign": side_sign,
            "hornCount": rack.horn_count,
            "cablePlacesPerHorn": 2,
            "overallArcLengthM": rack.overall_arc_length_m,
            "uprightWidthLongitudinalM": rack.upright_width_longitudinal_m,
            "uprightThicknessM": rack.upright_thickness_m,
            "hornPitchM": rack.horn_pitch_m,
            "hornRadiusM": rack.horn_radius_m,
            "hornThicknessM": rack.horn_thickness_m,
            "maxCableDiameterM": rack.max_cable_diameter_m,
            "placementMode": "intrados_following_photo_constrained_elevation",
            "centerProfileZM": rack.center_profile_z_m,
            "shellClearanceInwardM": rack.shell_clearance_inward_m,
        },
    )


def modern_cable_sections_core(
    profile: MoscowStage10Profile,
) -> tuple[tuple[str, tuple[tuple[float, float], ...], Mapping[str, Any]], ...]:
    """One representative longitudinal cable per R2K11 horn level per side."""
    rack = profile.cable_rack
    radius = 0.5 * rack.representative_cable_diameter_m
    rack_radius = profile.intrados_radius_m - rack.shell_clearance_inward_m
    result = []
    for side_sign in (-1, 1):
        for level in range(rack.horn_count):
            a = _horn_angle(profile, side_sign, level)
            sin_a = math.sin(a)
            cos_a = math.cos(a)
            cable_center_r = rack_radius - rack.first_cable_center_inward_m
            cx = cable_center_r * sin_a
            cz = cable_center_r * cos_a
            points = tuple(
                (
                    cx + radius * math.cos(2.0 * math.pi * i / rack.cable_circle_vertices),
                    cz + radius * math.sin(2.0 * math.pi * i / rack.cable_circle_vertices),
                )
                for i in range(rack.cable_circle_vertices)
            )
            name = (
                f"cable_{'neg' if side_sign < 0 else 'pos'}_"
                f"{level:02d}"
            )
            result.append(
                (
                    name,
                    points,
                    {
                        "serviceFamily": "R2K11_supported_longitudinal_cable",
                        "sideProfileXSign": side_sign,
                        "rackLevel": level,
                        "representativeCableDiameterM": (
                            rack.representative_cable_diameter_m
                        ),
                        "maxRackCableDiameterM": rack.max_cable_diameter_m,
                        "exactCableScheduleResolved": False,
                        "occupiedCablePlaceIndex": 0,
                        "availableCablePlacesPerHorn": 2,
                    },
                )
            )
    return tuple(result)
