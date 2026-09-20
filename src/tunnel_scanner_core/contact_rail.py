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
