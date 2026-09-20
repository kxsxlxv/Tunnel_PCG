from __future__ import annotations

"""Stage-10.3 Moscow contact-rail geometry.

The module is engine-neutral. It consumes the typed Moscow profile and produces
continuous XZ sections plus periodic local support meshes. Production.py owns
alignment placement, persistent IDs, scene assembly and chunking.
"""

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

from .mesh import Face, Vec3
from .moscow import MoscowStage10Profile
from .permanent_way import sleeper_chainages


@dataclass(frozen=True)
class LocalContactRailMesh:
    name_suffix: str
    object_type: str
    category: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    properties: Mapping[str, Any] = field(default_factory=dict)


def contact_rail_axis_profile_x(profile: MoscowStage10Profile) -> float:
    """Nominal RK axis from nearest running-rail inner working face."""
    cr = profile.contact_rail
    return cr.side_profile_x_sign * (
        0.5 * profile.track.gauge_m
        + cr.horizontal_from_inner_working_face_m
    )


def rk_contact_rail_profile_xz(
    profile: MoscowStage10Profile,
) -> tuple[tuple[float, float], ...]:
    """Linearized RK profile preserving all dimensioned principal callouts.

    The DMZ catalog dimensions the 90 mm base, 80 mm top, 20 mm web, 118 mm
    overall height and the 46/40/23 mm vertical bands. Transition radii are not
    dimensioned, so v1 uses a deterministic 9 mm linear transition at the
    bottom and mirrors that transition length into the upper head.
    """
    cr = profile.contact_rail
    if len(cr.rail_vertical_callouts_m) != 3:
        raise ValueError("initial RK profile requires three vertical callouts")
    top_band, web_band, bottom_band = cr.rail_vertical_callouts_m
    residual = (
        cr.rail_overall_height_m - top_band - web_band - bottom_band
    )
    if residual <= 0.0:
        raise ValueError("RK profile callouts leave no transition residual")

    x0 = contact_rail_axis_profile_x(profile)
    z0 = cr.working_surface_z_m
    hb = 0.5 * cr.rail_base_width_m
    ht = 0.5 * cr.rail_top_width_m
    hw = 0.5 * cr.rail_web_width_m

    z_bottom_outer = z0 + bottom_band
    z_web_bottom = z_bottom_outer + residual
    z_web_top = z_web_bottom + web_band
    z_top_transition = min(
        z0 + cr.rail_overall_height_m,
        z_web_top + residual,
    )
    z_top = z0 + cr.rail_overall_height_m

    if z_top_transition >= z_top:
        z_top_transition = 0.5 * (z_web_top + z_top)

    return (
        (x0 - hb, z0),
        (x0 + hb, z0),
        (x0 + hb, z_bottom_outer),
        (x0 + hw, z_web_bottom),
        (x0 + hw, z_web_top),
        (x0 + ht, z_top_transition),
        (x0 + ht, z_top),
        (x0 - ht, z_top),
        (x0 - ht, z_top_transition),
        (x0 - hw, z_web_top),
        (x0 - hw, z_web_bottom),
        (x0 - hb, z_bottom_outer),
    )


def rk_contact_rail_core_xz(
    profile: MoscowStage10Profile,
) -> tuple[tuple[float, float], ...]:
    return tuple(
        profile.coordinate.research_xz_to_core_xz(x, z)
        for x, z in rk_contact_rail_profile_xz(profile)
    )


def protective_cover_profile_xz(
    profile: MoscowStage10Profile,
) -> tuple[tuple[float, float], ...]:
    """U-shaped protective-cover wall using the explicitly tagged fallback.

    Historical clearances control placement. The modern silhouette contributes
    only the shape proportions/wall thickness and remains an era-mismatched
    fallback by contract.
    """
    cr = profile.contact_rail
    x0 = contact_rail_axis_profile_x(profile)
    z0 = cr.working_surface_z_m + cr.cover_lower_edge_above_contact_surface_m
    z1 = z0 + cr.cover_height_m
    zi = z1 - cr.cover_top_wall_m

    outer_base = 0.5 * cr.cover_outer_base_width_m
    outer_top = 0.5 * cr.cover_outer_top_width_m
    inner_base = outer_base - cr.cover_side_wall_m
    inner_top = outer_top - cr.cover_side_wall_m
    if min(inner_base, inner_top) <= 0.0:
        raise ValueError("contact-rail cover wall thickness is invalid")

    return (
        (x0 - outer_base, z0),
        (x0 - outer_top, z1),
        (x0 + outer_top, z1),
        (x0 + outer_base, z0),
        (x0 + inner_base, z0),
        (x0 + inner_top, zi),
        (x0 - inner_top, zi),
        (x0 - inner_base, z0),
    )


def protective_cover_core_xz(
    profile: MoscowStage10Profile,
) -> tuple[tuple[float, float], ...]:
    return tuple(
        profile.coordinate.research_xz_to_core_xz(x, z)
        for x, z in protective_cover_profile_xz(profile)
    )


def modern_protective_cover_profile_xz(
    profile: MoscowStage10Profile,
    *,
    width_extra_m: float = 0.0,
    height_extra_m: float = 0.0,
) -> tuple[tuple[float, float], ...]:
    """Rounded modern cover from exact envelope dimensions.

    The current manufacturer fixes top/base width, total height and wall
    thicknesses, but does not publish corner radii on the public product page.
    The outer/inner side curves therefore use a deterministic smoothstep
    interpolation. This is deliberately tagged as envelope-accurate rather
    than factory-CAD-accurate.
    """
    cr = profile.contact_rail
    modern = profile.modern_contact_rail
    x0 = contact_rail_axis_profile_x(profile)
    z0 = (
        cr.working_surface_z_m
        + modern.cover_lower_edge_above_contact_surface_m
    )
    h = modern.cover_height_m + float(height_extra_m)
    z1 = z0 + h

    outer_base = 0.5 * (modern.cover_base_width_m + float(width_extra_m))
    outer_top = 0.5 * (modern.cover_top_width_m + float(width_extra_m))
    side = modern.cover_side_wall_m
    top_wall = modern.cover_top_wall_m
    inner_base = outer_base - side
    inner_top = outer_top - side
    if min(inner_base, inner_top) <= 0.0:
        raise ValueError("modern contact cover wall thickness is invalid")
    if z1 - top_wall <= z0:
        raise ValueError("modern contact cover top wall consumes cover height")

    def side_curve(
        base_half: float,
        top_half: float,
        low_z: float,
        high_z: float,
        sign: float,
    ) -> list[tuple[float, float]]:
        pts: list[tuple[float, float]] = []
        for i in range(7):
            t = i / 6.0
            smooth = t * t * (3.0 - 2.0 * t)
            half = base_half + (top_half - base_half) * smooth
            # Slight crown easing near the top avoids the old boxy silhouette.
            z = low_z + (high_z - low_z) * t
            pts.append((x0 + sign * half, z))
        return pts

    outer_left = side_curve(outer_base, outer_top, z0, z1, -1.0)
    outer_right = list(reversed(side_curve(outer_base, outer_top, z0, z1, +1.0)))
    inner_z1 = z1 - top_wall
    inner_right = side_curve(inner_base, inner_top, z0, inner_z1, +1.0)
    inner_left = list(reversed(side_curve(inner_base, inner_top, z0, inner_z1, -1.0)))

    return tuple((*outer_left, *outer_right, *inner_right, *inner_left))


def modern_protective_cover_core_xz(
    profile: MoscowStage10Profile,
    *,
    width_extra_m: float = 0.0,
    height_extra_m: float = 0.0,
) -> tuple[tuple[float, float], ...]:
    return tuple(
        profile.coordinate.research_xz_to_core_xz(x, z)
        for x, z in modern_protective_cover_profile_xz(
            profile,
            width_extra_m=width_extra_m,
            height_extra_m=height_extra_m,
        )
    )


def modern_contact_support_chainages(
    total_length_m: float,
    profile: MoscowStage10Profile,
    *,
    running_support_pitch_m: float,
    running_support_phase_m: float,
) -> tuple[float, ...]:
    """Place modern contact supports in gaps between running-rail supports.

    RU214055U1 explicitly separates the contact-rail bracket block from the
    under-rail support block. The deterministic schedule therefore snaps each
    5 m target to the nearest midpoint between adjacent running-rail supports,
    rather than to the support itself.
    """
    if not math.isfinite(total_length_m) or total_length_m <= 0.0:
        raise ValueError("total_length_m must be finite and positive")
    if not math.isfinite(running_support_pitch_m) or running_support_pitch_m <= 0.0:
        raise ValueError("running_support_pitch_m must be positive")
    modern = profile.modern_contact_rail

    midpoint_phase = (
        float(running_support_phase_m) + 0.5 * running_support_pitch_m
    ) % running_support_pitch_m
    midpoints = sleeper_chainages(
        total_length_m,
        pitch_m=running_support_pitch_m,
        phase_m=midpoint_phase,
    )
    if not midpoints:
        return ()

    targets: list[float] = []
    t = 0.5 * modern.support_target_pitch_m
    while t < total_length_m - 1e-12:
        targets.append(t)
        t += modern.support_target_pitch_m

    result: list[float] = []
    used: set[float] = set()
    for target in targets:
        candidate = min(midpoints, key=lambda s: (abs(s - target), s))
        if candidate in used:
            raise ValueError("modern contact support targets collapsed to one gap")
        used.add(candidate)
        result.append(candidate)

    for chainage in result:
        nearest_index = round(
            (chainage - running_support_phase_m) / running_support_pitch_m
        )
        nearest_support = (
            running_support_phase_m
            + nearest_index * running_support_pitch_m
        )
        clearance = abs(chainage - nearest_support)
        if (
            clearance
            < modern.running_support_exclusion_half_length_m - 1e-12
        ):
            raise ValueError("modern contact support conflicts with running support")

    for a, b in zip(result, result[1:]):
        spacing = b - a
        if (
            spacing < modern.support_normative_min_m - 1e-12
            or spacing > modern.support_normative_max_m + 1e-12
        ):
            raise ValueError(
                f"modern contact-support spacing {spacing:.9f} m outside "
                "normative range"
            )
    return tuple(result)


def modern_cover_span_ranges(
    total_length_m: float,
    profile: MoscowStage10Profile,
    *,
    support_chainages: Sequence[float],
) -> tuple[tuple[float, float], ...]:
    """Return main-cover spans separated around each support hood."""
    modern = profile.modern_contact_rail
    gap = profile.contact_rail.cover_box_to_insulator_gap_m
    half_exclusion = 0.5 * modern.support_hood_length_m + gap
    cursor = 0.0
    spans: list[tuple[float, float]] = []
    for chainage in support_chainages:
        start = max(0.0, chainage - half_exclusion)
        end = min(total_length_m, chainage + half_exclusion)
        if start > cursor + 1e-9:
            spans.append((cursor, start))
        cursor = max(cursor, end)
    if cursor < total_length_m - 1e-9:
        spans.append((cursor, total_length_m))
    return tuple(spans)


def contact_support_chainages(
    total_length_m: float,
    profile: MoscowStage10Profile,
) -> tuple[float, ...]:
    """Build an independent target chain then snap supports to timber sleepers.

    The legacy bracket is physically screwed to a sleeper. A pure 5.0 m chain
    would miss the Stage-10.2 1680/km sleepers, so each independent target is
    snapped to its nearest sleeper. For the deterministic straight preset this
    yields the 8/9-sleeper interval family 4.7619/5.3571 m, both inside the
    researched 4.5-5.4 m bracket-spacing range.
    """
    if not math.isfinite(total_length_m) or total_length_m <= 0.0:
        raise ValueError("total_length_m must be finite and positive")
    cr = profile.contact_rail
    sleepers = sleeper_chainages(
        total_length_m,
        pitch_m=profile.sleeper.pitch_m,
    )
    if not sleepers:
        return ()

    targets: list[float] = []
    t = cr.support_target_phase_m
    while t < total_length_m - 1e-12:
        targets.append(t)
        t += cr.support_target_pitch_m

    result: list[float] = []
    used: set[float] = set()
    for target in targets:
        candidate = min(
            sleepers,
            key=lambda s: (abs(s - target), s),
        )
        if candidate in used:
            raise ValueError("contact support target chain snapped to duplicate sleeper")
        used.add(candidate)
        result.append(candidate)

    for a, b in zip(result, result[1:]):
        spacing = b - a
        if (
            spacing < cr.support_normative_min_m - 1e-12
            or spacing > cr.support_normative_max_m + 1e-12
        ):
            raise ValueError(
                f"snapped contact-support spacing {spacing:.9f} m "
                "falls outside normative range"
            )
    return tuple(result)


def _extrude_y_from_xz(
    points_xz: Sequence[tuple[float, float]],
    *,
    half_y_m: float,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    if len(points_xz) < 3:
        raise ValueError("XZ prism cross-section needs >=3 points")
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


def _combine_meshes(
    meshes: Sequence[tuple[Sequence[Vec3], Sequence[Face]]],
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    vertices: list[Vec3] = []
    faces: list[Face] = []
    for mesh_vertices, mesh_faces in meshes:
        base = len(vertices)
        vertices.extend(tuple(map(float, v)) for v in mesh_vertices)
        faces.extend(tuple(base + i for i in face) for face in mesh_faces)
    return tuple(vertices), tuple(faces)


def _cylinder_z_mesh(
    *,
    center_x_m: float,
    center_y_m: float,
    radius_m: float,
    z0_m: float,
    z1_m: float,
    sides: int = 12,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    if sides < 6:
        raise ValueError("cylinder sides must be >=6")
    vertices: list[Vec3] = []
    for z in (z0_m, z1_m):
        for i in range(sides):
            a = 2.0 * math.pi * i / sides
            vertices.append(
                (
                    center_x_m + radius_m * math.cos(a),
                    center_y_m + radius_m * math.sin(a),
                    z,
                )
            )
    faces: list[Face] = [
        tuple(reversed(tuple(range(sides)))),
        tuple(sides + i for i in range(sides)),
    ]
    for i in range(sides):
        j = (i + 1) % sides
        faces.append((i, j, sides + j, sides + i))
    return tuple(vertices), tuple(faces)


def _cylinder_x_mesh(
    *,
    x0_m: float,
    x1_m: float,
    center_y_m: float,
    center_z_m: float,
    radius_m: float,
    sides: int = 16,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    if sides < 6:
        raise ValueError("cylinder sides must be >=6")
    vertices: list[Vec3] = []
    for x in (x0_m, x1_m):
        for i in range(sides):
            a = 2.0 * math.pi * i / sides
            vertices.append(
                (
                    x,
                    center_y_m + radius_m * math.cos(a),
                    center_z_m + radius_m * math.sin(a),
                )
            )
    faces: list[Face] = [
        tuple(reversed(tuple(range(sides)))),
        tuple(sides + i for i in range(sides)),
    ]
    for i in range(sides):
        j = (i + 1) % sides
        faces.append((i, j, sides + j, sides + i))
    return tuple(vertices), tuple(faces)


def _box_mesh(
    *,
    center_x_m: float,
    center_y_m: float,
    size_x_m: float,
    size_y_m: float,
    z0_m: float,
    z1_m: float,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    hx = 0.5 * size_x_m
    hy = 0.5 * size_y_m
    x0, x1 = center_x_m - hx, center_x_m + hx
    y0, y1 = center_y_m - hy, center_y_m + hy
    v = (
        (x0, y0, z0_m), (x1, y0, z0_m), (x1, y1, z0_m), (x0, y1, z0_m),
        (x0, y0, z1_m), (x1, y0, z1_m), (x1, y1, z1_m), (x0, y1, z1_m),
    )
    f = (
        (0, 3, 2, 1), (4, 5, 6, 7),
        (0, 1, 5, 4), (1, 2, 6, 5),
        (2, 3, 7, 6), (3, 0, 4, 7),
    )
    return v, f


def _bezier_point(
    p0: tuple[float, float],
    p1: tuple[float, float],
    p2: tuple[float, float],
    p3: tuple[float, float],
    t: float,
) -> tuple[float, float]:
    u = 1.0 - t
    return (
        u**3 * p0[0]
        + 3.0 * u * u * t * p1[0]
        + 3.0 * u * t * t * p2[0]
        + t**3 * p3[0],
        u**3 * p0[1]
        + 3.0 * u * u * t * p1[1]
        + 3.0 * u * t * t * p2[1]
        + t**3 * p3[1],
    )


def _ribbon_polygon(
    centerline: Sequence[tuple[float, float]],
    *,
    thickness_m: float,
) -> tuple[tuple[float, float], ...]:
    if len(centerline) < 2:
        raise ValueError("ribbon centerline needs >=2 points")
    half = 0.5 * thickness_m
    left: list[tuple[float, float]] = []
    right: list[tuple[float, float]] = []
    for i, p in enumerate(centerline):
        if i == 0:
            q0, q1 = centerline[0], centerline[1]
        elif i == len(centerline) - 1:
            q0, q1 = centerline[-2], centerline[-1]
        else:
            q0, q1 = centerline[i - 1], centerline[i + 1]
        dx = q1[0] - q0[0]
        dz = q1[1] - q0[1]
        norm = math.hypot(dx, dz)
        if norm <= 1e-12:
            raise ValueError("degenerate bracket centerline")
        nx = -dz / norm
        nz = dx / norm
        left.append((p[0] + half * nx, p[1] + half * nz))
        right.append((p[0] - half * nx, p[1] - half * nz))
    return tuple((*left, *reversed(right)))


def _profile_xz_to_core(
    profile: MoscowStage10Profile,
    points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    return tuple(
        profile.coordinate.research_xz_to_core_xz(x, z)
        for x, z in points
    )


def build_modern_contact_support_meshes(
    profile: MoscowStage10Profile,
) -> tuple[LocalContactRailMesh, ...]:
    """Build the modern dedicated-block contact-rail support assembly."""
    cr = profile.contact_rail
    modern = profile.modern_contact_rail
    sign = cr.side_profile_x_sign
    axis_x = contact_rail_axis_profile_x(profile)
    axis_u = abs(axis_x)

    rail_top_profile_z = (
        cr.working_surface_z_m + cr.rail_overall_height_m
    )
    plate_under_profile_z = (
        rail_top_profile_z + modern.insulator_height_m
    )
    plate_top_profile_z = (
        plate_under_profile_z + modern.bracket_top_plate_thickness_m
    )

    # Dedicated support block sits in track concrete, between running supports.
    block_center_u = max(1.08, axis_u - 0.26)
    concrete_top_profile_z = (
        profile.track_concrete.surface_reference_z_m
        + profile.track_concrete.surface_cross_slope_to_drain
        * (
            block_center_u
            - profile.track_concrete.surface_reference_abs_x_m
        )
    )
    block_top_core = profile.coordinate.research_xz_to_core_xz(
        0.0, concrete_top_profile_z
    )[1]
    block_bottom_core = block_top_core - modern.support_block_height_m
    block_center_x = sign * block_center_u

    # Plan dimensions are not published in RU214055U1; keep a compact,
    # explicitly tagged preview footprint under the 100 mm bracket thickness.
    block_mesh = _box_mesh(
        center_x_m=block_center_x,
        center_y_m=0.0,
        size_x_m=0.24,
        size_y_m=0.18,
        z0_m=block_bottom_core,
        z1_m=block_top_core,
    )

    base_u = block_center_u
    base_z = concrete_top_profile_z + 0.015
    end_u = axis_u
    end_z = plate_under_profile_z
    p0 = (base_u, base_z)
    p1 = (base_u + 0.20, base_z + 0.06)
    p2 = (axis_u + 0.20, end_z + 0.04)
    p3 = (end_u, end_z)
    centerline = tuple(
        _bezier_point(p0, p1, p2, p3, i / 18.0)
        for i in range(19)
    )
    band_u_z = _ribbon_polygon(
        centerline,
        thickness_m=modern.bracket_channel_band_thickness_m,
    )
    bracket_profile = tuple((sign * u, z) for u, z in band_u_z)
    bracket_core = _profile_xz_to_core(profile, bracket_profile)
    bracket_mesh = _extrude_y_from_xz(
        bracket_core,
        half_y_m=0.5 * modern.bracket_longitudinal_thickness_m,
    )

    plate_center_core = profile.coordinate.research_xz_to_core_xz(
        axis_x,
        0.5 * (plate_under_profile_z + plate_top_profile_z),
    )
    top_plate_mesh = _box_mesh(
        center_x_m=plate_center_core[0],
        center_y_m=0.0,
        size_x_m=modern.bracket_top_plate_width_m,
        size_y_m=modern.bracket_longitudinal_thickness_m,
        z0_m=profile.coordinate.research_xz_to_core_xz(
            0.0, plate_under_profile_z
        )[1],
        z1_m=profile.coordinate.research_xz_to_core_xz(
            0.0, plate_top_profile_z
        )[1],
    )
    bracket_combined = _combine_meshes((bracket_mesh, top_plate_mesh))

    # The modern/photographic topology has the insulator above the contact rail,
    # hanging the rail from the over-rail bracket plate.
    insulator_z0 = profile.coordinate.research_xz_to_core_xz(
        0.0, rail_top_profile_z
    )[1]
    insulator_z1 = profile.coordinate.research_xz_to_core_xz(
        0.0, plate_under_profile_z
    )[1]
    insulator_mesh = _cylinder_z_mesh(
        center_x_m=profile.coordinate.research_xz_to_core_xz(axis_x, 0.0)[0],
        center_y_m=0.0,
        radius_m=0.5 * modern.insulator_diameter_m,
        z0_m=insulator_z0,
        z1_m=insulator_z1,
        sides=16,
    )

    # Rail-retaining saddle around the upper head, still explicitly topology
    # only until a current factory assembly drawing resolves the clamp.
    rail_half = 0.5 * cr.rail_top_width_m
    saddle_center_x = profile.coordinate.research_xz_to_core_xz(axis_x, 0.0)[0]
    rail_top_core = insulator_z0
    saddle_parts = (
        _box_mesh(
            center_x_m=saddle_center_x - rail_half - 0.010,
            center_y_m=0.0,
            size_x_m=0.012,
            size_y_m=0.085,
            z0_m=rail_top_core - 0.030,
            z1_m=rail_top_core + 0.014,
        ),
        _box_mesh(
            center_x_m=saddle_center_x + rail_half + 0.010,
            center_y_m=0.0,
            size_x_m=0.012,
            size_y_m=0.085,
            z0_m=rail_top_core - 0.030,
            z1_m=rail_top_core + 0.014,
        ),
        _box_mesh(
            center_x_m=saddle_center_x,
            center_y_m=0.0,
            size_x_m=cr.rail_top_width_m + 0.032,
            size_y_m=0.085,
            z0_m=rail_top_core + 0.006,
            z1_m=rail_top_core + 0.018,
        ),
    )
    saddle_mesh = _combine_meshes(saddle_parts)

    # Two 140 mm polymer-dowel/track-screw axes in the dedicated support block.
    dowels = []
    for dy in (-0.045, +0.045):
        dowels.append(
            _cylinder_z_mesh(
                center_x_m=block_center_x,
                center_y_m=dy,
                radius_m=0.012,
                z0_m=block_top_core - modern.support_dowel_length_m,
                z1_m=block_top_core + 0.010,
                sides=10,
            )
        )
    dowel_mesh = _combine_meshes(dowels)

    hood_profile = modern_protective_cover_core_xz(
        profile,
        width_extra_m=modern.support_hood_extra_width_m,
        height_extra_m=modern.support_hood_extra_height_m,
    )
    hood_mesh = _extrude_y_from_xz(
        hood_profile,
        half_y_m=0.5 * modern.support_hood_length_m,
    )

    return (
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_SUPPORT_BLOCK",
            object_type="production_contact_rail_support_block",
            category="contact_rail_support_block",
            vertices=block_mesh[0],
            faces=block_mesh[1],
            properties={
                "geometryMode": "RU214055_dedicated_block_preview",
                "heightM": modern.support_block_height_m,
                "polymerDowelLengthM": modern.support_dowel_length_m,
                "separateFromRunningRailSupport": True,
                "planGeometryResolved": False,
                "source": "P10-RU214055-CONTACT-SUPPORT",
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_RAIL_BRACKET",
            object_type="production_contact_rail_bracket",
            category="contact_rail_bracket",
            vertices=bracket_combined[0],
            faces=bracket_combined[1],
            properties={
                "geometryMode": "curved_channel_overrail_top_plate_v2",
                "resourceEnvelopeM": cr.support_resource_envelope_m,
                "longitudinalThicknessM": modern.bracket_longitudinal_thickness_m,
                "channelBandThicknessM": modern.bracket_channel_band_thickness_m,
                "topPlateWidthM": modern.bracket_top_plate_width_m,
                "topPlateThicknessM": modern.bracket_top_plate_thickness_m,
                "legacySleeperAttachment": False,
                "dedicatedConcreteSupportBlock": True,
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_RAIL_INSULATOR",
            object_type="production_contact_rail_insulator",
            category="contact_rail_insulator",
            vertices=insulator_mesh[0],
            faces=insulator_mesh[1],
            properties={
                "geometryMode": "vertical_cylindrical_envelope_v2",
                "heightM": modern.insulator_height_m,
                "diameterM": modern.insulator_diameter_m,
                "orientation": "vertical_above_contact_rail",
                "exactPorcelainProfileResolved": False,
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_RAIL_FASTENING",
            object_type="production_contact_rail_fastening_unit",
            category="contact_rail_fastening_unit",
            vertices=saddle_mesh[0],
            faces=saddle_mesh[1],
            properties={
                "geometryMode": "upper_head_saddle_v2",
                "confidence": "C_topology_only",
                "exactBoltClipGeometryResolved": False,
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_SUPPORT_DOWELS",
            object_type="production_contact_rail_attachment_dowels",
            category="contact_rail_attachment_dowels",
            vertices=dowel_mesh[0],
            faces=dowel_mesh[1],
            properties={
                "quantity": 2,
                "dowelLengthM": modern.support_dowel_length_m,
                "source": "P10-RU214055-CONTACT-SUPPORT",
                "countConfidence": "C_figure_interpretation",
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_SUPPORT_HOOD",
            object_type="production_contact_rail_support_hood",
            category="contact_rail_support_hood",
            vertices=hood_mesh[0],
            faces=hood_mesh[1],
            properties={
                "geometryMode": "rounded_local_fastening_hood_v1",
                "longitudinalLengthM": modern.support_hood_length_m,
                "widthExtraM": modern.support_hood_extra_width_m,
                "heightExtraM": modern.support_hood_extra_height_m,
                "confidence": "C_photo_topology_only",
                "mainCoverInterruptedHere": True,
            },
        ),
    )


def build_stage10_3_local_support_meshes(
    profile: MoscowStage10Profile,
) -> tuple[LocalContactRailMesh, ...]:
    cr = profile.contact_rail
    sign = cr.side_profile_x_sign
    axis_x = contact_rail_axis_profile_x(profile)
    axis_u = abs(axis_x)
    sleeper_half = 0.5 * profile.sleeper.length_m
    attach_u = sleeper_half - cr.support_sleeper_end_attachment_inset_m
    rail_outer_u = axis_u + 0.5 * cr.rail_base_width_m
    insulator_outboard_u = rail_outer_u + cr.insulator_axial_length_m
    z_attach = profile.sleeper.top_z_m + 0.012
    z_support = cr.working_surface_z_m + 0.5 * cr.rail_overall_height_m

    p0 = (attach_u, z_attach)
    p1 = (sleeper_half + 0.10, z_attach)
    p2 = (
        max(insulator_outboard_u + 0.045, sleeper_half + 0.30),
        z_attach + 0.18,
    )
    p3 = (
        insulator_outboard_u + cr.support_upper_outboard_clearance_from_rail_m,
        z_support,
    )
    centerline = tuple(
        _bezier_point(p0, p1, p2, p3, i / 12.0)
        for i in range(13)
    )
    band_u_z = _ribbon_polygon(
        centerline,
        thickness_m=cr.support_channel_band_thickness_m,
    )
    bracket_profile = tuple((sign * u, z) for u, z in band_u_z)
    bracket_core = _profile_xz_to_core(profile, bracket_profile)
    bracket_mesh = _extrude_y_from_xz(
        bracket_core,
        half_y_m=0.5 * cr.support_longitudinal_thickness_m,
    )

    insulator_x_in = sign * rail_outer_u
    insulator_x_out = sign * insulator_outboard_u
    z_support_core = profile.coordinate.research_xz_to_core_xz(
        0.0,
        z_support,
    )[1]
    insulator_mesh = _cylinder_x_mesh(
        x0_m=min(insulator_x_in, insulator_x_out),
        x1_m=max(insulator_x_in, insulator_x_out),
        center_y_m=0.0,
        center_z_m=z_support_core,
        radius_m=0.5 * cr.insulator_diameter_m,
    )

    screw_x = sign * attach_u
    sleeper_top_core = profile.coordinate.research_xz_to_core_xz(
        0.0,
        profile.sleeper.top_z_m,
    )[1]
    screw_meshes = []
    for dy in (-0.032, 0.0, 0.032):
        shaft = _cylinder_z_mesh(
            center_x_m=screw_x,
            center_y_m=dy,
            radius_m=0.5 * profile.fastening.track_screw_diameter_m,
            z0_m=sleeper_top_core - profile.fastening.track_screw_length_m,
            z1_m=sleeper_top_core,
            sides=12,
        )
        head = _cylinder_z_mesh(
            center_x_m=screw_x,
            center_y_m=dy,
            radius_m=profile.fastening.track_screw_head_radius_m,
            z0_m=sleeper_top_core,
            z1_m=(
                sleeper_top_core
                + profile.fastening.track_screw_head_height_m
            ),
            sides=12,
        )
        screw_meshes.extend((shaft, head))
    screws = _combine_meshes(tuple(screw_meshes))

    clip_center_x = sign * (rail_outer_u - 0.010)
    clip_z0 = z_support_core - 0.030
    clip_z1 = z_support_core + 0.030
    clip_profile = (
        (clip_center_x - 0.018, clip_z0),
        (clip_center_x + 0.018, clip_z0),
        (clip_center_x + 0.018, clip_z1),
        (clip_center_x - 0.018, clip_z1),
    )
    clip_mesh = _extrude_y_from_xz(
        clip_profile,
        half_y_m=0.040,
    )

    return (
        LocalContactRailMesh(
            name_suffix="CONTACT_RAIL_BRACKET",
            object_type="production_contact_rail_bracket",
            category="contact_rail_bracket",
            vertices=bracket_mesh[0],
            faces=bracket_mesh[1],
            properties={
                "geometryMode": cr.support_geometry_mode,
                "resourceEnvelopeM": cr.support_resource_envelope_m,
                "longitudinalThicknessM": cr.support_longitudinal_thickness_m,
                "channelBandThicknessM": cr.support_channel_band_thickness_m,
                "legacySleeperAttachment": True,
                "sourceTopology": "Frolov_Fig1_20_curved_channel",
            },
        ),
        LocalContactRailMesh(
            name_suffix="CONTACT_RAIL_INSULATOR",
            object_type="production_contact_rail_insulator",
            category="contact_rail_insulator",
            vertices=insulator_mesh[0],
            faces=insulator_mesh[1],
            properties={
                "geometryMode": cr.insulator_mode,
                "axialLengthM": cr.insulator_axial_length_m,
                "diameterM": cr.insulator_diameter_m,
                "exactPorcelainProfileResolved": False,
            },
        ),
        LocalContactRailMesh(
            name_suffix="CONTACT_RAIL_ATTACHMENT_SCREWS",
            object_type="production_contact_rail_attachment_screws",
            category="contact_rail_attachment_screws",
            vertices=screws[0],
            faces=screws[1],
            properties={
                "quantity": 3,
                "diameterM": profile.fastening.track_screw_diameter_m,
                "shaftLengthM": profile.fastening.track_screw_length_m,
                "headRadiusM": profile.fastening.track_screw_head_radius_m,
                "headHeightM": profile.fastening.track_screw_head_height_m,
                "headGeometry": profile.fastening.track_screw_head_mode,
                "embeddedFastenerVolumeOverlap": True,
                "legacyAttachmentRule": "three_track_screws_into_timber_sleeper",
            },
        ),
        LocalContactRailMesh(
            name_suffix="CONTACT_RAIL_FASTENING_UNIT",
            object_type="production_contact_rail_fastening_unit",
            category="contact_rail_fastening_unit",
            vertices=clip_mesh[0],
            faces=clip_mesh[1],
            properties={
                "geometryMode": "simplified_retaining_clip_v1",
                "confidence": "C_topology_only",
                "exactBoltClipGeometryResolved": False,
            },
        ),
    )
