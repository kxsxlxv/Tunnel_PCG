from __future__ import annotations

"""Modern Moscow tunnel service/cable geometry for Stage 10.5."""

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

from .curved_mesh import SurfaceMeshingConfig, required_circle_subdivisions, sagitta_m
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


def _arc_segments_for_sagitta(
    *,
    radius_m: float,
    span_rad: float,
    max_sagitta_m: float,
    min_segments: int = 1,
) -> tuple[int, float]:
    """Return the minimum chord count satisfying a radial sagitta tolerance."""
    if not math.isfinite(radius_m) or radius_m <= 0.0:
        raise ValueError("arc radius must be finite and positive")
    if not math.isfinite(span_rad) or span_rad <= 0.0:
        raise ValueError("arc span must be finite and positive")
    if not math.isfinite(max_sagitta_m) or max_sagitta_m <= 0.0:
        raise ValueError("max_sagitta_m must be finite and positive")
    if min_segments < 1:
        raise ValueError("min_segments must be >=1")

    # s = r * (1 - cos(theta/2)).  Clamp the acos input so the
    # calculation remains defined for deliberately coarse tolerances.
    cosine = 1.0 - max_sagitta_m / radius_m
    cosine = min(1.0, max(-1.0, cosine))
    max_step = 2.0 * math.acos(cosine)
    if max_step <= 1e-15:
        raise ValueError("sagitta tolerance yields a degenerate angular step")
    segments = max(min_segments, int(math.ceil(span_rad / max_step)))
    achieved = radius_m * (
        1.0 - math.cos(0.5 * span_rad / segments)
    )
    if achieved > max_sagitta_m + 1e-12:
        raise AssertionError("computed arc tessellation exceeds sagitta tolerance")
    return segments, achieved


def _rack_center_angle(
    profile: MoscowStage10Profile,
    side_sign: int,
) -> float:
    if side_sign not in (-1, 1):
        raise ValueError("side_sign must be +/-1")
    rack = profile.cable_rack
    center_profile_z = (
        rack.negative_side_center_profile_z_m
        if side_sign < 0
        else rack.center_profile_z_m
    )
    core_z = (
        center_profile_z
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


def r2k11_mount_angle_rad(
    profile: MoscowStage10Profile,
    side_sign: int,
) -> float:
    """Wall-mount polar angle for the R2K11 assembly centre."""
    return _rack_center_angle(profile, side_sign)


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
    """Generic low-poly U saddle retained for non-R2K11 service supports."""
    if segments < 3:
        raise ValueError("service cup segments must be >=3")
    outer_r = radius_m + 0.5 * thickness_m
    inner_r = radius_m - 0.5 * thickness_m
    if inner_r <= 0.0:
        raise ValueError("service cup thickness exceeds radius")

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
    """Generic wall standoff used by the water-main support, not R2K11."""
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


def _u_ribbon_polygon(
    *,
    wall_x_m: float,
    wall_z_m: float,
    inward_x: float,
    inward_z: float,
    up_x: float,
    up_z: float,
    center_inward_m: float,
    inner_radius_m: float,
    thickness_m: float,
    stem_height_m: float,
    arc_segments: int = 8,
) -> tuple[tuple[float, float], ...]:
    """Build one literal U-shaped formed-steel cradle ribbon.

    The U has two straight side stems and a semicircular lower seat. The
    supplied inner radius is the cable-clear radius; strip thickness grows
    outward from it. This intentionally avoids the previous W/omega centre
    crest entirely.
    """
    if min(center_inward_m, inner_radius_m, thickness_m, stem_height_m) <= 0.0:
        raise ValueError("U-cradle dimensions must be positive")
    if arc_segments < 4:
        raise ValueError("U-cradle arc_segments must be >=4")

    inner_r = inner_radius_m
    outer_r = inner_radius_m + thickness_m
    if center_inward_m < outer_r - 1e-12:
        raise ValueError("U-cradle extends behind the rack upright")

    local: list[tuple[float, float]] = []

    # Outer boundary: left stem -> lower semicircle -> right stem.
    local.append((center_inward_m - outer_r, stem_height_m))
    local.append((center_inward_m - outer_r, 0.0))
    for i in range(arc_segments + 1):
        theta = math.pi + math.pi * i / arc_segments
        local.append(
            (
                center_inward_m + outer_r * math.cos(theta),
                outer_r * math.sin(theta),
            )
        )
    local.append((center_inward_m + outer_r, stem_height_m))

    # Inner boundary in reverse, closing the strip at the two open U tips.
    local.append((center_inward_m + inner_r, stem_height_m))
    local.append((center_inward_m + inner_r, 0.0))
    for i in range(arc_segments + 1):
        theta = 2.0 * math.pi - math.pi * i / arc_segments
        local.append(
            (
                center_inward_m + inner_r * math.cos(theta),
                inner_r * math.sin(theta),
            )
        )
    local.append((center_inward_m - inner_r, stem_height_m))

    polygon = tuple(
        (
            wall_x_m + inward_x * h + up_x * v,
            wall_z_m + inward_z * h + up_z * v,
        )
        for h, v in local
    )
    area = 0.5 * sum(
        x0 * z1 - x1 * z0
        for (x0, z0), (x1, z1) in zip(
            polygon,
            (*polygon[1:], polygon[0]),
        )
    )
    return polygon if area > 0.0 else tuple(reversed(polygon))


def _r2k11_double_u_layout(
    *,
    max_cable_diameter_m: float,
    thickness_m: float,
    pair_span_m: float = 0.154,
    radial_clearance_m: float = 0.001,
) -> tuple[float, float, tuple[float, float]]:
    """Resolve two adjacent U seats and their cable-centre offsets."""
    if min(max_cable_diameter_m, thickness_m, pair_span_m) <= 0.0:
        raise ValueError("double-U layout dimensions must be positive")
    if radial_clearance_m < 0.0:
        raise ValueError("double-U cable clearance cannot be negative")
    inner_r = 0.5 * max_cable_diameter_m + radial_clearance_m
    outer_r = inner_r + thickness_m
    gap = pair_span_m - 4.0 * outer_r
    if gap < -1e-12:
        raise ValueError("double-U pair span is too small for cable clearance")
    gap = max(0.0, gap)
    centers = (outer_r, 3.0 * outer_r + gap)
    return inner_r, gap, centers

def _double_u_horn_polygons(
    *,
    wall_x_m: float,
    wall_z_m: float,
    inward_x: float,
    inward_z: float,
    up_x: float,
    up_z: float,
    inner_radius_m: float,
    thickness_m: float,
    pair_span_m: float = 0.154,
    central_gap_m: float = 0.004,
    stem_height_m: float = 0.035,
    arc_segments: int = 8,
) -> tuple[
    tuple[tuple[float, float], ...],
    tuple[tuple[float, float], ...],
]:
    """Build the R2K11 horn as two simple adjacent U cradles: UU.

    The user-supplied drawing gives a 154 mm double-cradle span. The visual
    U-seat clear radius is made 1 mm larger than the published 65 mm maximum
    cable radius requirement, so each cradle has 67 mm internal clear diameter.
    With 4 mm strip this leaves a 4 mm gap between the two U shapes. The first
    U begins directly at the rack upright;
    there is no horizontal shelf, neck or central W/omega crest.
    """
    outer_r = inner_radius_m + thickness_m
    expected_span = 4.0 * outer_r + central_gap_m
    if not math.isclose(pair_span_m, expected_span, abs_tol=1e-12):
        raise ValueError(
            "double-U span must equal two cradle outer diameters plus gap"
        )

    first_center = outer_r
    second_center = 3.0 * outer_r + central_gap_m
    first = _u_ribbon_polygon(
        wall_x_m=wall_x_m,
        wall_z_m=wall_z_m,
        inward_x=inward_x,
        inward_z=inward_z,
        up_x=up_x,
        up_z=up_z,
        center_inward_m=first_center,
        inner_radius_m=inner_radius_m,
        thickness_m=thickness_m,
        stem_height_m=stem_height_m,
        arc_segments=arc_segments,
    )
    second = _u_ribbon_polygon(
        wall_x_m=wall_x_m,
        wall_z_m=wall_z_m,
        inward_x=inward_x,
        inward_z=inward_z,
        up_x=up_x,
        up_z=up_z,
        center_inward_m=second_center,
        inner_radius_m=inner_radius_m,
        thickness_m=thickness_m,
        stem_height_m=stem_height_m,
        arc_segments=arc_segments,
    )
    return first, second


def build_r2k11_local_rack_mesh(
    profile: MoscowStage10Profile,
    *,
    side_sign: int,
    surface_meshing: SurfaceMeshingConfig | None = None,
) -> LocalServiceMesh:
    rack = profile.cable_rack
    meshing = surface_meshing or SurfaceMeshingConfig()
    center_angle = _rack_center_angle(profile, side_sign)
    half_angle = 0.5 * rack.overall_arc_length_m / profile.intrados_radius_m
    rack_radius = profile.intrados_radius_m - rack.shell_clearance_inward_m
    upright_segments, upright_sagitta = _arc_segments_for_sagitta(
        radius_m=rack_radius,
        span_rad=2.0 * half_angle,
        max_sagitta_m=meshing.max_sagitta_m,
        min_segments=2,
    )
    # Keep point order from lower to upper end on either wall.
    angles = tuple(
        center_angle
        + side_sign * half_angle
        - side_sign * (2.0 * half_angle) * i / upright_segments
        for i in range(upright_segments + 1)
    )
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

        # User visual correction: K1350.002 reads as two simple U cradles,
        # not a rounded W/omega ribbon. The first U touches the upright
        # directly; there is no horizontal neck/shelf before it.
        u_inner_r, u_gap, u_centers = _r2k11_double_u_layout(
            max_cable_diameter_m=rack.max_cable_diameter_m,
            thickness_m=rack.horn_thickness_m,
        )
        horn_outer_r = u_inner_r + rack.horn_thickness_m
        horn_arc_segments, horn_sagitta = _arc_segments_for_sagitta(
            radius_m=horn_outer_r,
            span_rad=math.pi,
            max_sagitta_m=meshing.max_sagitta_m,
            min_segments=4,
        )
        horns = _double_u_horn_polygons(
            wall_x_m=wall_x,
            wall_z_m=wall_z,
            inward_x=inward[0],
            inward_z=inward[1],
            up_x=up[0],
            up_z=up[1],
            inner_radius_m=u_inner_r,
            thickness_m=rack.horn_thickness_m,
            central_gap_m=u_gap,
            arc_segments=horn_arc_segments,
        )
        meshes.extend(
            _extrude_y_polygon(
                horn,
                half_y_m=0.5 * rack.horn_longitudinal_width_m,
            )
            for horn in horns
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
            "assemblyDesignation": rack.assembly_designation,
            "uprightDesignation": rack.upright_designation,
            "hornDesignation": rack.horn_designation,
            "sideProfileXSign": side_sign,
            "hornCount": rack.horn_count,
            "cablePlacesPerHorn": rack.cable_places_per_horn,
            "overallArcLengthM": rack.overall_arc_length_m,
            "uprightWidthLongitudinalM": rack.upright_width_longitudinal_m,
            "uprightThicknessM": rack.upright_thickness_m,
            "hornPitchM": rack.horn_pitch_m,
            "hornRadiusM": rack.horn_radius_m,
            "hornThicknessM": rack.horn_thickness_m,
            "hornOverallLengthM": rack.horn_overall_length_m,
            "hornOverallHeightM": rack.horn_overall_height_m,
            "hornLongitudinalWidthM": rack.horn_longitudinal_width_m,
            "maxCableDiameterM": rack.max_cable_diameter_m,
            "placementMode": "intrados_following_side_specific_visual_elevation",
            "centerProfileZM": (
                rack.negative_side_center_profile_z_m
                if side_sign < 0
                else rack.center_profile_z_m
            ),
            "commonHorizontalUnderbar": False,
            "separateWallTab": False,
            "separateHorizontalNeck": False,
            "centralOmegaCrest": False,
            "hornGeometryMode": "double_u_cradle_pair_v6",
            "hornUCradleCount": 2,
            "hornUVisualPairSpanM": 0.154,
            "hornUCentralGapM": u_gap,
            "hornUInnerClearRadiusM": u_inner_r,
            "hornUInnerClearDiameterM": 2.0 * u_inner_r,
            "hornUCableCenterOffsetsM": u_centers,
            "hornUMaxCableRadialClearanceM": (
                u_inner_r - 0.5 * rack.max_cable_diameter_m
            ),
            "hornUStemHeightM": 0.035,
            "surfaceToleranceM": meshing.max_sagitta_m,
            "tessellationMode": "sagitta_bounded_adaptive_v1",
            "uprightArcSegments": upright_segments,
            "uprightAchievedMaxSagittaM": upright_sagitta,
            "hornUArcSegments": horn_arc_segments,
            "hornUAchievedMaxSagittaM": horn_sagitta,
            "shellClearanceInwardM": rack.shell_clearance_inward_m,
        },
    )


def modern_cable_sections_core(
    profile: MoscowStage10Profile,
    *,
    surface_meshing: SurfaceMeshingConfig | None = None,
) -> tuple[tuple[str, tuple[tuple[float, float], ...], Mapping[str, Any]], ...]:
    """Populate a moderate-density R2K11 cable preview.

    The hardware exposes two cable places on each of 11 levels, but the
    production visual preset deliberately occupies only eight distributed
    levels per wall and one cable place on each occupied level. Cable routes
    carry a small gravity sag between the 1 m rack supports; the longitudinal
    sweep adds only one midpoint station per support span.
    """
    rack = profile.cable_rack
    meshing = surface_meshing or SurfaceMeshingConfig()
    radius = 0.5 * rack.representative_cable_diameter_m
    circle_vertices = required_circle_subdivisions(
        radius,
        meshing.max_sagitta_m,
        min_subdivisions=6,
    )
    achieved_sagitta = sagitta_m(radius, 360.0 / circle_vertices)
    rack_radius = profile.intrados_radius_m - rack.shell_clearance_inward_m
    _u_inner_r, _u_gap, slot_offsets = _r2k11_double_u_layout(
        max_cable_diameter_m=rack.max_cable_diameter_m,
        thickness_m=rack.horn_thickness_m,
    )
    result = []
    for side_sign in (-1, 1):
        side_class = (
            "strong_current_side_contact_rail_side"
            if side_sign < 0
            else "weak_current_side_walkway_side"
        )
        for level in rack.occupied_level_indices:
            a = _horn_angle(profile, side_sign, level)
            sin_a = math.sin(a)
            cos_a = math.cos(a)
            # Alternate the two physical cradle positions so the preview does
            # not form an artificial perfectly aligned cable curtain.
            place_index = level % rack.cable_places_per_horn
            slot_offset = slot_offsets[place_index]
            cable_center_r = rack_radius - slot_offset
            cx = cable_center_r * sin_a
            cz = cable_center_r * cos_a
            points = tuple(
                (
                    cx
                    + radius
                    * math.cos(
                        2.0 * math.pi * i / circle_vertices
                    ),
                    cz
                    + radius
                    * math.sin(
                        2.0 * math.pi * i / circle_vertices
                    ),
                )
                for i in range(circle_vertices)
            )
            name = (
                f"cable_{'neg' if side_sign < 0 else 'pos'}_"
                f"{level:02d}_{place_index}"
            )
            result.append(
                (
                    name,
                    points,
                    {
                        "serviceFamily": "R2K11_supported_longitudinal_cable",
                        "sideProfileXSign": side_sign,
                        "serviceSideClass": side_class,
                        "rackLevel": level,
                        "representativeCableDiameterM": (
                            rack.representative_cable_diameter_m
                        ),
                        "sourcePreviewCircleVertices": rack.cable_circle_vertices,
                        "cableCircleVertices": circle_vertices,
                        "surfaceToleranceM": meshing.max_sagitta_m,
                        "surfaceAchievedMaxSagittaM": achieved_sagitta,
                        "tessellationMode": "sagitta_bounded_adaptive_v1",
                        "maxRackCableDiameterM": rack.max_cable_diameter_m,
                        "exactCableScheduleResolved": False,
                        "occupiedCablePlaceIndex": place_index,
                        "availableCablePlacesPerHorn": (
                            rack.cable_places_per_horn
                        ),
                        "occupiedCablePlacesPerHorn": (
                            rack.occupied_places_per_horn
                        ),
                        "occupiedRackLevelCountPerSide": len(
                            rack.occupied_level_indices
                        ),
                        "occupiedRackLevels": rack.occupied_level_indices,
                        "cablePlaceCenterInwardM": slot_offset,
                        "supportPitchM": rack.repeat_pitch_m,
                        "supportPhaseM": rack.phase_m,
                        "longitudinalSagM": rack.cable_sag_midspan_m,
                        "longitudinalSagVariationFraction": (
                            rack.cable_sag_variation_fraction
                        ),
                        "longitudinalSagPeakPhaseJitterFraction": (
                            rack.cable_sag_peak_phase_jitter_fraction
                        ),
                        "sagShape": (
                            "deterministic_asymmetric_single_peak_per_support_span"
                        ),
                        "layoutRuleSource": "P10-SP-CABLE-LAYOUT",
                        "occupancyMode": (
                            "eight_levels_one_cable_each_per_side_visual_preview"
                        ),
                    },
                )
            )
    return tuple(result)

def water_main_support_chainages(
    total_length_m: float,
    profile: MoscowStage10Profile,
) -> tuple[float, ...]:
    """Deterministic support chain with no unsupported interval over 4 m."""
    if not math.isfinite(total_length_m) or total_length_m <= 0.0:
        raise ValueError("total_length_m must be finite and positive")
    pitch = profile.water_main.support_max_pitch_m
    if total_length_m <= pitch:
        return (0.5 * total_length_m,)
    result: list[float] = []
    x = 0.5 * pitch
    while x < total_length_m - 1e-12:
        result.append(x)
        x += pitch
    if not result:
        result.append(0.5 * total_length_m)
    if result[0] > pitch + 1e-12:
        raise AssertionError("water-main first support exceeds maximum interval")
    if total_length_m - result[-1] > pitch + 1e-12:
        raise AssertionError("water-main final support exceeds maximum interval")
    return tuple(result)


def _water_main_center_core(
    profile: MoscowStage10Profile,
) -> tuple[float, float, float]:
    water = profile.water_main
    radius = 0.5 * water.preview_outer_diameter_m
    core_z = (
        water.center_profile_z_m
        + profile.coordinate.profile_z_to_core_z_offset_m
    )
    r = profile.intrados_radius_m
    if abs(core_z) + radius >= r:
        raise ValueError("water-main z lies outside Moscow intrados")
    shell_x_abs = math.sqrt(r * r - core_z * core_z)
    center_x_abs = (
        shell_x_abs
        - water.shell_clearance_inward_m
        - radius
    )
    if center_x_abs <= 0.0:
        raise ValueError("water-main fallback placement has no wall clearance")
    return water.side_profile_x_sign * center_x_abs, core_z, radius


def build_water_main_support_local_mesh(
    profile: MoscowStage10Profile,
) -> LocalServiceMesh:
    """Initial wall standoff + lower saddle for the DN80 tunnel main.

    The <=4 m support interval is normative. Exact project bracket/strap CAD is
    unresolved, so the local solid is deliberately simple and tagged as such.
    """
    water = profile.water_main
    cx, cz, pipe_radius = _water_main_center_core(profile)
    center_r = math.hypot(cx, cz)
    if center_r <= 0.0:
        raise ValueError("water-main center cannot lie on tunnel axis")

    outward = (cx / center_r, cz / center_r)
    inward = (-outward[0], -outward[1])
    up = (-outward[1], outward[0])

    wall_r = profile.intrados_radius_m - 0.006
    wall_x = outward[0] * wall_r
    wall_z = outward[1] * wall_r
    pipe_outer_x = cx + outward[0] * pipe_radius
    pipe_outer_z = cz + outward[1] * pipe_radius
    standoff = (
        (pipe_outer_x - wall_x) * inward[0]
        + (pipe_outer_z - wall_z) * inward[1]
    )
    if standoff <= 0.0:
        raise ValueError("water-main support standoff collapsed")

    arm = _radial_arm_polygon(
        wall_x_m=wall_x,
        wall_z_m=wall_z,
        inward_x=inward[0],
        inward_z=inward[1],
        up_x=up[0],
        up_z=up[1],
        length_m=standoff,
        thickness_m=0.018,
        vertical_offset_m=-(pipe_radius + 0.012),
    )
    clamp = _ribbon_u_cup_polygon(
        center_x_m=cx,
        center_z_m=cz,
        inward_x=inward[0],
        inward_z=inward[1],
        up_x=up[0],
        up_z=up[1],
        radius_m=pipe_radius + 0.006,
        thickness_m=0.006,
        segments=8,
    )
    vertices, faces = _combine(
        (
            _extrude_y_polygon(arm, half_y_m=0.030),
            _extrude_y_polygon(clamp, half_y_m=0.030),
        )
    )
    return LocalServiceMesh(
        name_suffix="WATER_MAIN_SUPPORT",
        object_type="production_water_main_support",
        category="water_main_support",
        vertices=vertices,
        faces=faces,
        properties={
            "serviceFamily": "tunnel_water_main_support",
            "geometryMode": water.support_geometry_mode,
            "supportMaxPitchM": water.support_max_pitch_m,
            "pipePreviewOuterDiameterM": water.preview_outer_diameter_m,
            "exactProjectSupportCADResolved": False,
            "normativeSupportIntervalResolved": True,
            "insideMoscowIntrados": True,
        },
    )


def modern_water_main_section_core(
    profile: MoscowStage10Profile,
    *,
    circle_vertices: int = 16,
) -> tuple[tuple[tuple[float, float], ...], Mapping[str, Any]]:
    """Build one current tunnel water-main preview inside the physical intrados.

    The current metro code fixes one main per single-track tunnel, minimum DN80,
    above UGR and normally on the weak-current side. Exact project coordinates
    and pipe OD/wall thickness are not universal, so those remain explicit
    preview fallbacks in the machine profile.
    """
    if circle_vertices < 8:
        raise ValueError("water-main circle requires at least 8 vertices")
    water = profile.water_main
    center_x, core_z, radius = _water_main_center_core(profile)
    r = profile.intrados_radius_m
    points = tuple(
        (
            center_x + radius * math.cos(2.0 * math.pi * i / circle_vertices),
            core_z + radius * math.sin(2.0 * math.pi * i / circle_vertices),
        )
        for i in range(circle_vertices)
    )
    if max(math.hypot(x, z) for x, z in points) >= r - 1e-9:
        raise AssertionError("water-main preview escapes physical intrados")
    return points, {
        "serviceFamily": "tunnel_water_main",
        "minNominalDNmm": water.min_nominal_dn_mm,
        "quantitySingleTrackTunnel": water.quantity_single_track_tunnel,
        "sideProfileXSign": water.side_profile_x_sign,
        "positionRule": "above_UGR_weak_current_side",
        "centerProfileZM": water.center_profile_z_m,
        "previewOuterDiameterM": water.preview_outer_diameter_m,
        "outerDiameterMode": water.outer_diameter_mode,
        "shellClearanceInwardM": water.shell_clearance_inward_m,
        "supportMaxPitchM": water.support_max_pitch_m,
        "supportGeometryMode": water.support_geometry_mode,
        "placementMode": water.placement_mode,
        "materialFamily": water.material_family,
        "normativeSource": water.normative_source,
        "confidence": water.confidence,
        "exactProjectRouteResolved": False,
        "insideMoscowIntrados": True,
    }
