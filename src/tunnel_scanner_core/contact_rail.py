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
from .moscow import (
    MoscowStage10Profile,
    R65ProductionProfile,
    r65_rail_center_offsets_for_gauge,
)
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
        scale = max(abs(a), abs(b), abs(spacing), 1.0)
        numerical_tol = max(1e-12, 64.0 * math.ulp(scale))
        if (
            spacing < modern.support_normative_min_m - numerical_tol
            or spacing > modern.support_normative_max_m + numerical_tol
        ):
            raise ValueError(
                f"modern contact-support spacing {spacing:.17g} m outside "
                f"normative range within numerical tolerance "
                f"{numerical_tol:.3g} m"
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
    """Build the dimensioned modern contact-rail support assembly.

    The 2026-09-21 user-supplied drawing contributes readable 873/683/180 mm
    horizontal and 373/155/90 mm vertical callouts. The authoritative
    690 +/- 8 mm / +160 mm contact-rail placement remains unchanged; the
    drawing dimensions constrain the hook-bracket envelope and clamp stack.
    """
    cr = profile.contact_rail
    modern = profile.modern_contact_rail
    sign = cr.side_profile_x_sign
    axis_x = contact_rail_axis_profile_x(profile)
    axis_u = abs(axis_x)

    # The drawing's 683 mm axis callout independently cross-checks the
    # authoritative 690 mm placement from the inner working face.
    reference_u = 0.5 * profile.track.gauge_m
    drawing_axis_u = reference_u + modern.drawing_reference_to_axis_m
    outer_envelope_u = (
        reference_u + modern.drawing_reference_to_outer_envelope_m
    )
    if abs(drawing_axis_u - axis_u) > cr.horizontal_tolerance_m + 1e-12:
        raise ValueError("dimensioned support drawing axis conflicts with gauge datum")

    band = modern.bracket_channel_band_thickness_m
    half_band = 0.5 * band
    outer_center_u = outer_envelope_u - half_band
    top_inner_edge_u = (
        outer_envelope_u - modern.drawing_upper_return_m
    )
    top_inner_center_u = top_inner_edge_u + half_band

    # User visual review requires the entire lower support assembly to start
    # at least 35 mm outboard of the contact-side LVT block.  Derive that
    # boundary from the exact R65 gauge placement plus the source-backed
    # 640 mm LVT-M block length instead of from the running-rail reference.
    rail_centers = r65_rail_center_offsets_for_gauge(
        profile.track.gauge_m,
        profile=R65ProductionProfile(),
        measurement_below_top_m=profile.track.gauge_measurement_below_ugr_m,
    )
    contact_side_rail_center_u = max(abs(v) for v in rail_centers)
    lvt_block_outboard_u = (
        contact_side_rail_center_u
        + 0.5 * profile.modern_permanent_way.block_base_length_transverse_m
    )
    support_inboard_clearance_u = (
        lvt_block_outboard_u + modern.minimum_clearance_to_lvt_block_m
    )

    support_block_transverse_m = modern.base_plate_transverse_m + 0.040
    support_block_center_u = (
        support_inboard_clearance_u + 0.5 * support_block_transverse_m
    )
    base_plate_center_u = (
        support_inboard_clearance_u + 0.5 * modern.base_plate_transverse_m
    )
    concrete_top_profile_z = (
        profile.track_concrete.surface_reference_z_m
        + profile.track_concrete.surface_cross_slope_to_drain
        * (
            base_plate_center_u
            - profile.track_concrete.surface_reference_abs_x_m
        )
    )
    block_top_core = profile.coordinate.research_xz_to_core_xz(
        0.0, concrete_top_profile_z
    )[1]
    block_bottom_core = block_top_core - modern.support_block_height_m
    block_center_x = sign * support_block_center_u
    base_plate_center_x = sign * base_plate_center_u

    block_mesh = _box_mesh(
        center_x_m=block_center_x,
        center_y_m=0.0,
        size_x_m=support_block_transverse_m,
        size_y_m=modern.base_plate_longitudinal_m + 0.040,
        z0_m=block_bottom_core,
        z1_m=block_top_core,
    )

    base_plate_z0 = block_top_core
    base_plate_z1 = base_plate_z0 + modern.base_plate_thickness_m
    base_plate_mesh = _box_mesh(
        center_x_m=base_plate_center_x,
        center_y_m=0.0,
        size_x_m=modern.base_plate_transverse_m,
        size_y_m=modern.base_plate_longitudinal_m,
        z0_m=base_plate_z0,
        z1_m=base_plate_z1,
    )

    # Four-anchor base pattern is visible in the dimensioned plan drawing.
    dowels = []
    for dx in (
        -0.5 * modern.base_plate_anchor_pitch_transverse_m,
        +0.5 * modern.base_plate_anchor_pitch_transverse_m,
    ):
        for dy in (
            -0.5 * modern.base_plate_anchor_pitch_longitudinal_m,
            +0.5 * modern.base_plate_anchor_pitch_longitudinal_m,
        ):
            dowels.append(
                _cylinder_z_mesh(
                    center_x_m=base_plate_center_x + sign * dx,
                    center_y_m=dy,
                    radius_m=0.5 * 0.024,
                    z0_m=block_top_core - modern.support_dowel_length_m,
                    z1_m=base_plate_z1 + 0.010,
                    sides=12,
                )
            )
    dowel_mesh = _combine_meshes(dowels)

    # Hook-channel side profile. 155 and 90 mm are used as the lower/upper
    # bend construction callouts; exact factory neutral-axis radii are still
    # marked as image-derived.
    base_center_profile_z = (
        concrete_top_profile_z
        + modern.base_plate_thickness_m
        + half_band
    )
    top_center_profile_z = modern.drawing_top_above_ugr_m - half_band
    lower_r = modern.bracket_lower_bend_radius_m
    upper_r = modern.bracket_upper_bend_radius_m

    start_center_u = support_inboard_clearance_u
    lower_arc_center_u = outer_center_u - lower_r
    lower_arc_center_z = base_center_profile_z + lower_r
    upper_arc_center_u = outer_center_u - upper_r
    upper_arc_center_z = top_center_profile_z - upper_r

    if lower_arc_center_u <= start_center_u:
        raise ValueError("dimensioned contact-support lower arm collapsed")
    if upper_arc_center_z <= lower_arc_center_z:
        raise ValueError("dimensioned contact-support vertical hook collapsed")
    if top_inner_center_u >= outer_center_u:
        raise ValueError("dimensioned contact-support upper return collapsed")

    centerline: list[tuple[float, float]] = [
        (start_center_u, base_center_profile_z),
        (lower_arc_center_u, base_center_profile_z),
    ]
    for i in range(1, 7):
        a = -0.5 * math.pi + (0.5 * math.pi) * i / 6.0
        centerline.append(
            (
                lower_arc_center_u + lower_r * math.cos(a),
                lower_arc_center_z + lower_r * math.sin(a),
            )
        )
    centerline.append((outer_center_u, upper_arc_center_z))
    for i in range(1, 7):
        a = (0.5 * math.pi) * i / 6.0
        centerline.append(
            (
                upper_arc_center_u + upper_r * math.cos(a),
                upper_arc_center_z + upper_r * math.sin(a),
            )
        )
    centerline.append((top_inner_center_u, top_center_profile_z))

    band_u_z = _ribbon_polygon(centerline, thickness_m=band)
    bracket_profile = tuple((sign * u, z) for u, z in band_u_z)
    bracket_core = _profile_xz_to_core(profile, bracket_profile)
    bracket_mesh = _extrude_y_from_xz(
        bracket_core,
        half_y_m=0.5 * modern.bracket_longitudinal_thickness_m,
    )

    # The 180 mm upper dimension is also consistent with the visible top
    # clamping plate width. The plate reinforces the hook arm directly above
    # the contact-rail axis.
    top_plate_z0_profile = (
        modern.drawing_top_above_ugr_m
        - modern.bracket_top_plate_thickness_m
    )
    top_plate_z1_profile = modern.drawing_top_above_ugr_m
    top_plate_center_core = profile.coordinate.research_xz_to_core_xz(
        axis_x,
        0.5 * (top_plate_z0_profile + top_plate_z1_profile),
    )
    top_plate_mesh = _box_mesh(
        center_x_m=top_plate_center_core[0],
        center_y_m=0.0,
        size_x_m=modern.bracket_top_plate_width_m,
        size_y_m=modern.bracket_longitudinal_thickness_m,
        z0_m=profile.coordinate.research_xz_to_core_xz(
            0.0, top_plate_z0_profile
        )[1],
        z1_m=profile.coordinate.research_xz_to_core_xz(
            0.0, top_plate_z1_profile
        )[1],
    )
    bracket_combined = _combine_meshes((bracket_mesh, top_plate_mesh))

    rail_top_profile_z = (
        cr.working_surface_z_m + cr.rail_overall_height_m
    )
    rail_top_core = profile.coordinate.research_xz_to_core_xz(
        0.0, rail_top_profile_z
    )[1]
    axis_core_x = profile.coordinate.research_xz_to_core_xz(axis_x, 0.0)[0]

    # Two side jaws flank the 80 mm upper contact-rail flange while the bridge
    # plate sits immediately above it. This makes the rail/support contact
    # legible instead of letting the rail visually float inside the support.
    rail_top_half = 0.5 * cr.rail_top_width_m
    jaw_center_offset = (
        rail_top_half
        + 0.003
        + 0.5 * modern.clamp_jaw_thickness_m
    )
    jaw_z1 = rail_top_core + 0.010
    jaw_z0 = jaw_z1 - modern.clamp_jaw_height_m
    clamp_parts = []
    for sx in (-1.0, +1.0):
        clamp_parts.append(
            _box_mesh(
                center_x_m=axis_core_x + sx * jaw_center_offset,
                center_y_m=0.0,
                size_x_m=modern.clamp_jaw_thickness_m,
                size_y_m=0.090,
                z0_m=jaw_z0,
                z1_m=jaw_z1,
            )
        )
    bridge_z0 = rail_top_core + 0.008
    bridge_z1 = bridge_z0 + modern.clamp_bridge_thickness_m
    clamp_parts.append(
        _box_mesh(
            center_x_m=axis_core_x,
            center_y_m=0.0,
            size_x_m=modern.clamp_bridge_width_m,
            size_y_m=0.090,
            z0_m=bridge_z0,
            z1_m=bridge_z1,
        )
    )
    clamp_mesh = _combine_meshes(clamp_parts)

    # Short visible vertical insulator stack between the clamp bridge and the
    # underside of the dimensioned hook arm. The old 150 mm cylinder caused
    # the support to float unrealistically above the rail.
    bracket_underside_profile_z = (
        modern.drawing_top_above_ugr_m
        - modern.bracket_channel_band_thickness_m
    )
    bracket_underside_core_z = profile.coordinate.research_xz_to_core_xz(
        0.0, bracket_underside_profile_z
    )[1]
    available_stack = bracket_underside_core_z - bridge_z1
    if available_stack <= 0.0:
        raise ValueError("dimensioned support leaves no room for insulator stack")
    visible_insulator_height = min(
        modern.insulator_height_m,
        available_stack,
    )
    insulator_z0 = bracket_underside_core_z - visible_insulator_height
    insulator_z1 = bracket_underside_core_z
    insulator_mesh = _cylinder_z_mesh(
        center_x_m=axis_core_x,
        center_y_m=0.0,
        radius_m=0.5 * modern.insulator_diameter_m,
        z0_m=insulator_z0,
        z1_m=insulator_z1,
        sides=20,
    )

    # Two through-bolts visible on the dimensioned clamp/top plate.
    bolt_meshes = []
    bolt_x_offset = min(
        0.5 * modern.bracket_top_plate_width_m - 0.025,
        0.5 * modern.clamp_bridge_width_m - 0.010,
    )
    bracket_top_core_z = profile.coordinate.research_xz_to_core_xz(
        0.0, modern.drawing_top_above_ugr_m
    )[1]
    for sx in (-1.0, +1.0):
        bx = axis_core_x + sx * bolt_x_offset
        shaft = _cylinder_z_mesh(
            center_x_m=bx,
            center_y_m=0.0,
            radius_m=0.5 * modern.clamp_bolt_diameter_m,
            z0_m=jaw_z1,
            z1_m=bracket_top_core_z,
            sides=12,
        )
        head = _cylinder_z_mesh(
            center_x_m=bx,
            center_y_m=0.0,
            radius_m=modern.clamp_bolt_head_radius_m,
            z0_m=bracket_top_core_z,
            z1_m=bracket_top_core_z + modern.clamp_bolt_head_height_m,
            sides=12,
        )
        bolt_meshes.extend((shaft, head))
    clamp_bolts_mesh = _combine_meshes(bolt_meshes)

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
                "geometryMode": "dimensioned_dedicated_block_v3",
                "heightM": modern.support_block_height_m,
                "planTransverseM": support_block_transverse_m,
                "planLongitudinalM": modern.base_plate_longitudinal_m + 0.040,
                "lvtBlockOutboardProfileAbsXM": lvt_block_outboard_u,
                "minimumClearanceToLVTBlockM": modern.minimum_clearance_to_lvt_block_m,
                "actualInboardClearanceToLVTBlockM": (
                    support_inboard_clearance_u - lvt_block_outboard_u
                ),
                "inboardProfileAbsXM": support_inboard_clearance_u,
                "polymerDowelLengthM": modern.support_dowel_length_m,
                "separateFromRunningRailSupport": True,
                "planGeometryResolved": False,
                "source": "P10-RU214055-CONTACT-SUPPORT;P10-USER-CONTACT-SUPPORT-873",
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_SUPPORT_BASE_PLATE",
            object_type="production_contact_rail_base_plate",
            category="contact_rail_base_plate",
            vertices=base_plate_mesh[0],
            faces=base_plate_mesh[1],
            properties={
                "geometryMode": "four_anchor_base_plate_v3",
                "transverseM": modern.base_plate_transverse_m,
                "longitudinalM": modern.base_plate_longitudinal_m,
                "thicknessM": modern.base_plate_thickness_m,
                "anchorCount": modern.base_plate_anchor_count,
                "anchorPitchTransverseM": modern.base_plate_anchor_pitch_transverse_m,
                "anchorPitchLongitudinalM": modern.base_plate_anchor_pitch_longitudinal_m,
                "lvtBlockOutboardProfileAbsXM": lvt_block_outboard_u,
                "minimumClearanceToLVTBlockM": modern.minimum_clearance_to_lvt_block_m,
                "actualInboardClearanceToLVTBlockM": (
                    support_inboard_clearance_u - lvt_block_outboard_u
                ),
                "inboardProfileAbsXM": support_inboard_clearance_u,
                "exactHoleSlotGeometryResolved": False,
                "source": "P10-USER-CONTACT-SUPPORT-873",
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_RAIL_BRACKET",
            object_type="production_contact_rail_bracket",
            category="contact_rail_bracket",
            vertices=bracket_combined[0],
            faces=bracket_combined[1],
            properties={
                "geometryMode": "dimensioned_hook_channel_873x373_v3",
                "resourceEnvelopeM": cr.support_resource_envelope_m,
                "legacyResourceEnvelopeNotGeometryAuthority": True,
                "drawingReferenceToAxisM": modern.drawing_reference_to_axis_m,
                "drawingReferenceToOuterEnvelopeM": modern.drawing_reference_to_outer_envelope_m,
                "drawingUpperReturnM": modern.drawing_upper_return_m,
                "drawingTopAboveUGRM": modern.drawing_top_above_ugr_m,
                "drawingLowerBendCalloutM": modern.drawing_lower_bend_callout_m,
                "drawingUpperBendCalloutM": modern.drawing_upper_bend_callout_m,
                "normativeAxisOffsetM": cr.horizontal_from_inner_working_face_m,
                "normativeWorkingSurfaceProfileZM": cr.working_surface_z_m,
                "outerEnvelopeProfileAbsXM": outer_envelope_u,
                "topInnerEdgeProfileAbsXM": top_inner_edge_u,
                "lvtBlockOutboardProfileAbsXM": lvt_block_outboard_u,
                "minimumClearanceToLVTBlockM": modern.minimum_clearance_to_lvt_block_m,
                "lowerLegInboardProfileAbsXM": support_inboard_clearance_u,
                "actualLowerLegClearanceToLVTBlockM": (
                    support_inboard_clearance_u - lvt_block_outboard_u
                ),
                "longitudinalThicknessM": modern.bracket_longitudinal_thickness_m,
                "channelBandThicknessM": modern.bracket_channel_band_thickness_m,
                "topPlateWidthM": modern.bracket_top_plate_width_m,
                "topPlateThicknessM": modern.bracket_top_plate_thickness_m,
                "legacySleeperAttachment": False,
                "dedicatedConcreteSupportBlock": True,
                "source": "P10-USER-CONTACT-SUPPORT-873",
                "dimensionConfidence": "B_readable_callouts_C_bend_interpretation",
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_RAIL_INSULATOR",
            object_type="production_contact_rail_insulator",
            category="contact_rail_insulator",
            vertices=insulator_mesh[0],
            faces=insulator_mesh[1],
            properties={
                "geometryMode": "short_vertical_stack_under_hook_arm_v3",
                "catalogEnvelopeHeightM": modern.insulator_height_m,
                "visibleHeightM": visible_insulator_height,
                "diameterM": modern.insulator_diameter_m,
                "orientation": "vertical_between_contact_clamp_and_upper_hook_arm",
                "exactPorcelainProfileResolved": False,
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_RAIL_CLAMP",
            object_type="production_contact_rail_fastening_unit",
            category="contact_rail_fastening_unit",
            vertices=clamp_mesh[0],
            faces=clamp_mesh[1],
            properties={
                "geometryMode": "upper_flange_saddle_insulated_two_bolt_v3",
                "bridgeWidthM": modern.clamp_bridge_width_m,
                "bridgeThicknessM": modern.clamp_bridge_thickness_m,
                "jawThicknessM": modern.clamp_jaw_thickness_m,
                "jawHeightM": modern.clamp_jaw_height_m,
                "boltCount": modern.clamp_bolt_count,
                "railTopProfileZM": rail_top_profile_z,
                "exactClampCastingResolved": False,
                "source": "P10-USER-CONTACT-SUPPORT-873;P10-FROLOV-CONTACT",
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_RAIL_CLAMP_BOLTS",
            object_type="production_contact_rail_clamp_bolts",
            category="contact_rail_clamp_bolts",
            vertices=clamp_bolts_mesh[0],
            faces=clamp_bolts_mesh[1],
            properties={
                "quantity": modern.clamp_bolt_count,
                "diameterM": modern.clamp_bolt_diameter_m,
                "headRadiusM": modern.clamp_bolt_head_radius_m,
                "headHeightM": modern.clamp_bolt_head_height_m,
                "geometryMode": "two_visible_through_bolts_v3",
                "source": "P10-USER-CONTACT-SUPPORT-873",
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_SUPPORT_DOWELS",
            object_type="production_contact_rail_attachment_dowels",
            category="contact_rail_attachment_dowels",
            vertices=dowel_mesh[0],
            faces=dowel_mesh[1],
            properties={
                "quantity": modern.base_plate_anchor_count,
                "dowelLengthM": modern.support_dowel_length_m,
                "source": "P10-USER-CONTACT-SUPPORT-873;P10-RU214055-CONTACT-SUPPORT",
                "countConfidence": "B_dimensioned_plan_topology",
            },
        ),
        LocalContactRailMesh(
            name_suffix="MODERN_CONTACT_SUPPORT_HOOD",
            object_type="production_contact_rail_support_hood",
            category="contact_rail_support_hood",
            vertices=hood_mesh[0],
            faces=hood_mesh[1],
            properties={
                "geometryMode": "rounded_local_fastening_hood_v2",
                "longitudinalLengthM": modern.support_hood_length_m,
                "widthExtraM": modern.support_hood_extra_width_m,
                "heightExtraM": modern.support_hood_extra_height_m,
                "dimensionedBracketTopProfileZM": modern.drawing_top_above_ugr_m,
                "confidence": "B_height_envelope_C_exact_hood_shape",
                "mainCoverInterruptedHere": True,
                "coversClampAndBoltHeads": True,
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
