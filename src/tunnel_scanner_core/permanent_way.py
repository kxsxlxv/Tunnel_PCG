from __future__ import annotations

"""Stage-10.2 Moscow permanent-way geometry primitives.

This module stays engine-neutral. It constructs deterministic cross-sections and
periodic local meshes from the machine-readable Moscow profile. Production.py
owns alignment placement, persistent IDs, SceneObject assembly and chunking.
"""

from dataclasses import dataclass, field
import math
from typing import Any, Mapping, Sequence

from .mesh import Face, Vec3
from .moscow import MoscowStage10Profile, R65ProductionProfile


@dataclass(frozen=True)
class LocalPermanentWayMesh:
    name_suffix: str
    object_type: str
    category: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    properties: Mapping[str, Any] = field(default_factory=dict)


def sleeper_chainages(
    total_length_m: float,
    *,
    pitch_m: float,
    phase_m: float | None = None,
) -> tuple[float, ...]:
    if not math.isfinite(total_length_m) or total_length_m <= 0.0:
        raise ValueError("total_length_m must be finite and positive")
    if not math.isfinite(pitch_m) or pitch_m <= 0.0:
        raise ValueError("pitch_m must be finite and positive")
    phase = 0.5 * pitch_m if phase_m is None else float(phase_m)
    if not math.isfinite(phase) or not (0.0 <= phase < pitch_m):
        raise ValueError("phase_m must satisfy 0 <= phase < pitch")
    result: list[float] = []
    chainage = phase
    while chainage < total_length_m - 1e-12:
        result.append(chainage)
        chainage += pitch_m
    return tuple(result)


def _lower_intrados_z(
    profile: MoscowStage10Profile,
    x_m: float,
) -> float:
    c = profile.datums.lining_axis_z_m
    r = profile.intrados_radius_m
    q = r * r - x_m * x_m
    if q < -1e-12:
        raise ValueError("x lies outside Moscow intrados circle")
    return c - math.sqrt(max(0.0, q))


def _top_z_at_x(
    profile: MoscowStage10Profile,
    x_m: float,
    *,
    rail_axis_abs_x_m: float,
) -> float:
    tc = profile.track_concrete
    return (
        tc.concrete_top_at_rail_z_m
        + tc.surface_cross_slope_to_drain
        * (abs(float(x_m)) - rail_axis_abs_x_m)
    )


def _outer_surface_intersection_x(
    profile: MoscowStage10Profile,
    *,
    rail_axis_abs_x_m: float,
) -> float:
    # Solve top_plane(x) == lower_intrados(x) on the positive-X shoulder.
    drain_half = 0.5 * profile.track_concrete.central_drain_clear_width_m
    lo = max(drain_half, rail_axis_abs_x_m)
    hi = profile.intrados_radius_m - 1e-9

    def f(x: float) -> float:
        return (
            _top_z_at_x(
                profile,
                x,
                rail_axis_abs_x_m=rail_axis_abs_x_m,
            )
            - _lower_intrados_z(profile, x)
        )

    flo = f(lo)
    fhi = f(hi)
    if flo * fhi > 0.0:
        raise ValueError("failed to bracket concrete/intrados top intersection")
    for _ in range(100):
        mid = 0.5 * (lo + hi)
        fm = f(mid)
        if abs(fm) < 1e-14:
            return mid
        if flo * fm <= 0.0:
            hi = mid
            fhi = fm
        else:
            lo = mid
            flo = fm
    return 0.5 * (lo + hi)


def track_concrete_profile_xz(
    profile: MoscowStage10Profile,
    *,
    rail_centers_profile_x: Sequence[float],
    intrados_samples: int = 40,
) -> tuple[tuple[float, float], ...]:
    """Return the Stage-10.2 track-concrete polygon in profile XZ coordinates.

    The source-backed top datum is anchored at the two R65 symmetry axes. The
    source-backed 3% fall is applied toward the 0.9 m central drain. The same
    plane continues outward until it meets the physical 5.1 m intrados. The
    deterministic v1 50x25 mm water-release groove is centered in the drain
    bottom per the explicit C-confidence machine-profile fallback.
    """
    if len(rail_centers_profile_x) != 2:
        raise ValueError("track concrete requires two running-rail centers")
    if intrados_samples < 8:
        raise ValueError("intrados_samples must be >= 8")
    rail_abs = 0.5 * (
        abs(float(rail_centers_profile_x[0]))
        + abs(float(rail_centers_profile_x[1]))
    )
    tc = profile.track_concrete
    drain_half = 0.5 * tc.central_drain_clear_width_m
    groove_half = 0.5 * tc.water_groove_width_m
    xout = _outer_surface_intersection_x(
        profile,
        rail_axis_abs_x_m=rail_abs,
    )
    zout = _top_z_at_x(profile, xout, rail_axis_abs_x_m=rail_abs)
    zdrain_top = _top_z_at_x(
        profile,
        drain_half,
        rail_axis_abs_x_m=rail_abs,
    )
    zbottom = tc.central_drain_bottom_z_m
    zgroove = zbottom - tc.water_groove_depth_m
    groove_center = tc.water_groove_center_x_m
    gx0 = groove_center - groove_half
    gx1 = groove_center + groove_half
    if not (-drain_half < gx0 < gx1 < drain_half):
        raise ValueError("water-release groove must lie inside drain bottom")

    top_and_drain = [
        (-xout, zout),
        (-drain_half, zdrain_top),
        (-drain_half, zbottom),
        (gx0, zbottom),
        (gx0, zgroove),
        (gx1, zgroove),
        (gx1, zbottom),
        (drain_half, zbottom),
        (drain_half, zdrain_top),
        (xout, zout),
    ]

    c = profile.datums.lining_axis_z_m
    r = profile.intrados_radius_m
    alpha_right = math.atan2(xout, zout - c)
    if alpha_right < 0.0:
        alpha_right += 2.0 * math.pi
    alpha_left = 2.0 * math.pi - alpha_right
    if alpha_left <= alpha_right:
        alpha_left += 2.0 * math.pi
    arc = []
    for i in range(1, intrados_samples):
        u = i / intrados_samples
        a = alpha_right + u * (alpha_left - alpha_right)
        arc.append((r * math.sin(a), c + r * math.cos(a)))

    return tuple((*top_and_drain, *arc))


def track_concrete_core_xz(
    profile: MoscowStage10Profile,
    *,
    rail_centers_profile_x: Sequence[float],
    intrados_samples: int = 40,
) -> tuple[tuple[float, float], ...]:
    return tuple(
        profile.coordinate.research_xz_to_core_xz(x, z)
        for x, z in track_concrete_profile_xz(
            profile,
            rail_centers_profile_x=rail_centers_profile_x,
            intrados_samples=intrados_samples,
        )
    )


def _extrude_y_from_xz(
    points_xz: Sequence[tuple[float, float]],
    *,
    half_y_m: float,
    omit_longitudinal_edge_indices: Sequence[int] = (),
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    if len(points_xz) < 3:
        raise ValueError("XZ prism cross-section needs >=3 points")
    n = len(points_xz)
    vertices = tuple(
        [(x, -half_y_m, z) for x, z in points_xz]
        + [(x, +half_y_m, z) for x, z in points_xz]
    )
    omit = {int(i) for i in omit_longitudinal_edge_indices}
    faces: list[Face] = []
    faces.append(tuple(reversed(tuple(range(n)))))
    faces.append(tuple(n + i for i in range(n)))
    for i in range(n):
        if i in omit:
            continue
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


def _box_mesh(
    *,
    center_x_m: float,
    center_y_m: float,
    size_x_m: float,
    size_y_m: float,
    z0_m: float,
    z1_m: float,
    omit_bottom: bool = False,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    hx = 0.5 * size_x_m
    hy = 0.5 * size_y_m
    x0, x1 = center_x_m - hx, center_x_m + hx
    y0, y1 = center_y_m - hy, center_y_m + hy
    v = (
        (x0, y0, z0_m),
        (x1, y0, z0_m),
        (x1, y1, z0_m),
        (x0, y1, z0_m),
        (x0, y0, z1_m),
        (x1, y0, z1_m),
        (x1, y1, z1_m),
        (x0, y1, z1_m),
    )
    f: list[Face] = []
    if not omit_bottom:
        f.append((0, 3, 2, 1))
    f.extend(
        (
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (1, 2, 6, 5),
            (2, 3, 7, 6),
            (3, 0, 4, 7),
        )
    )
    return v, tuple(f)


def _cylinder_z_mesh(
    *,
    center_x_m: float,
    center_y_m: float,
    radius_m: float,
    z0_m: float,
    z1_m: float,
    segments: int = 10,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    if segments < 6:
        raise ValueError("cylinder needs >=6 segments")
    v: list[Vec3] = []
    for z in (z0_m, z1_m):
        for i in range(segments):
            a = 2.0 * math.pi * i / segments
            v.append(
                (
                    center_x_m + radius_m * math.cos(a),
                    center_y_m + radius_m * math.sin(a),
                    z,
                )
            )
    f: list[Face] = []
    f.append(tuple(reversed(tuple(range(segments)))))
    f.append(tuple(segments + i for i in range(segments)))
    for i in range(segments):
        j = (i + 1) % segments
        f.append((i, j, segments + j, segments + i))
    return tuple(v), tuple(f)


def _profile_z_to_core(
    profile: MoscowStage10Profile,
    z_m: float,
) -> float:
    return profile.coordinate.research_xz_to_core_xz(0.0, z_m)[1]


def build_stage10_2_local_event_meshes(
    profile: MoscowStage10Profile,
    *,
    rail_centers_profile_x: Sequence[float],
) -> tuple[LocalPermanentWayMesh, ...]:
    """Build one sleeper + two-rail KD-65 support event at local Y=0."""
    if len(rail_centers_profile_x) != 2:
        raise ValueError("KD-65 event requires two running-rail centers")
    s = profile.sleeper
    k = profile.fastening

    sleeper_top = _profile_z_to_core(profile, s.top_z_m)
    sleeper_bottom = _profile_z_to_core(profile, s.bottom_z_m)
    vertical_side_top = sleeper_bottom + s.sawn_side_height_m
    half_lower_y = 0.5 * s.lower_face_width_m
    half_upper_y = 0.5 * s.upper_face_width_m
    yz = (
        (-half_lower_y, sleeper_bottom),
        (+half_lower_y, sleeper_bottom),
        (+half_lower_y, vertical_side_top),
        (+half_upper_y, sleeper_top),
        (-half_upper_y, sleeper_top),
        (-half_lower_y, vertical_side_top),
    )
    # Extrude the sleeper YZ profile along X.
    x0 = -0.5 * s.length_m
    x1 = +0.5 * s.length_m
    n = len(yz)
    sleeper_vertices = tuple(
        [(x0, y, z) for y, z in yz]
        + [(x1, y, z) for y, z in yz]
    )
    sleeper_faces: list[Face] = [
        tuple(reversed(tuple(range(n)))),
        tuple(n + i for i in range(n)),
    ]
    for i in range(n):
        j = (i + 1) % n
        sleeper_faces.append((i, j, n + j, n + i))

    result: list[LocalPermanentWayMesh] = [
        LocalPermanentWayMesh(
            name_suffix="SLEEPER",
            object_type="production_sleeper",
            category="sleeper",
            vertices=sleeper_vertices,
            faces=tuple(sleeper_faces),
            properties={
                "sleeperStandard": "GOST_22830_77",
                "sleeperLengthM": s.length_m,
                "sleeperThicknessM": s.thickness_m,
                "sleeperUpperFaceWidthM": s.upper_face_width_m,
                "sleeperLowerFaceWidthM": s.lower_face_width_m,
                "sleeperSawnSideHeightM": s.sawn_side_height_m,
                "sleeperTopProfileZM": s.top_z_m,
                "sleeperBottomProfileZM": s.bottom_z_m,
                "sleeperTopCoreZM": sleeper_top,
                "sleeperBottomCoreZM": sleeper_bottom,
                "source": s.source,
            },
        )
    ]

    underpad_z0 = sleeper_top
    underpad_z1 = underpad_z0 + k.under_pad_thickness_m
    baseplate_z0 = underpad_z1
    baseplate_seat_z = baseplate_z0 + k.baseplate_rail_seat_height_m
    railpad_z0 = baseplate_seat_z
    railpad_z1 = railpad_z0 + k.rail_pad_total_thickness_m
    expected_rail_base = _profile_z_to_core(
        profile,
        profile.datums.ugr_z_m - profile.track.rail_height_m,
    )
    if not math.isclose(railpad_z1, expected_rail_base, abs_tol=2e-12):
        raise AssertionError("KD-65 support stack does not close to R65 base")

    underpads = []
    baseplates = []
    railpads = []
    screws = []
    clamp_hardware = []

    # Baseplate cross-section uses the source plan dimensions and maximum
    # shoulder envelope. The rail-seat height is the explicit machine-profile
    # assembly-fit fallback needed to reconcile the independent Moscow datums.
    bp_half = 0.5 * k.baseplate_transverse_m
    seat_half = k.baseplate_rail_seat_half_width_m
    shoulder_inner = k.baseplate_shoulder_inner_x_m
    shoulder_outer = k.baseplate_shoulder_outer_x_m
    bp_outer_top = baseplate_z0 + k.baseplate_outer_wing_top_height_m
    bp_max = baseplate_z0 + k.baseplate_max_height_m
    bp_profile = (
        (-bp_half, baseplate_z0),
        (+bp_half, baseplate_z0),
        (+bp_half, bp_outer_top),
        (+shoulder_outer, bp_outer_top),
        (+shoulder_inner, bp_max),
        (+seat_half, bp_max),
        (+seat_half, baseplate_seat_z),
        (-seat_half, baseplate_seat_z),
        (-seat_half, bp_max),
        (-shoulder_inner, bp_max),
        (-shoulder_outer, bp_outer_top),
        (-bp_half, bp_outer_top),
    )

    rp_half = 0.5 * k.rail_pad_transverse_m
    rp_raised_half = 0.5 * k.rail_pad_raised_seat_transverse_m
    rail_foot_half = 0.5 * R65ProductionProfile().base_width_m
    if rail_foot_half >= rp_raised_half:
        raise AssertionError("R65 foot must fit inside raised rail-pad seat")
    rp_base_top = railpad_z0 + k.rail_pad_base_thickness_m
    # Split both bottom and raised top so only the true hidden contact spans
    # are omitted. The pad overhang and the R65 underside between sleepers
    # remain visible.
    rp_profile = (
        (-rp_half, railpad_z0),
        (-seat_half, railpad_z0),
        (+seat_half, railpad_z0),
        (+rp_half, railpad_z0),
        (+rp_half, rp_base_top),
        (+rp_raised_half, rp_base_top),
        (+rp_raised_half, railpad_z1),
        (+rail_foot_half, railpad_z1),
        (-rail_foot_half, railpad_z1),
        (-rp_raised_half, railpad_z1),
        (-rp_raised_half, rp_base_top),
        (-rp_half, rp_base_top),
    )

    for center_profile_x in rail_centers_profile_x:
        center_x = profile.coordinate.research_xz_to_core_xz(
            float(center_profile_x), 0.0
        )[0]
        underpads.append(
            _box_mesh(
                center_x_m=center_x,
                center_y_m=0.0,
                size_x_m=k.under_pad_transverse_m,
                size_y_m=k.under_pad_longitudinal_m,
                z0_m=underpad_z0,
                z1_m=underpad_z1,
                omit_bottom=True,
            )
        )

        bp_shifted = tuple((center_x + x, z) for x, z in bp_profile)
        baseplates.append(
            _extrude_y_from_xz(
                bp_shifted,
                half_y_m=0.5 * k.baseplate_longitudinal_m,
                omit_longitudinal_edge_indices=(0,),
            )
        )

        rp_shifted = tuple((center_x + x, z) for x, z in rp_profile)
        railpads.append(
            _extrude_y_from_xz(
                rp_shifted,
                half_y_m=0.5 * k.rail_pad_longitudinal_m,
                # Edge 1: baseplate-seat contact.
                # Edge 7: R65 foot contact.
                omit_longitudinal_edge_indices=(1, 7),
            )
        )

        hx = 0.5 * k.baseplate_hole_spacing_transverse_m
        hy = 0.5 * k.baseplate_hole_spacing_longitudinal_m
        screw_head_z0 = bp_outer_top
        screw_head_z1 = screw_head_z0 + k.track_screw_head_height_m
        for sx in (-hx, +hx):
            for sy in (-hy, +hy):
                screws.append(
                    _cylinder_z_mesh(
                        center_x_m=center_x + sx,
                        center_y_m=sy,
                        radius_m=0.5 * k.track_screw_diameter_m,
                        z0_m=sleeper_top - k.track_screw_length_m,
                        z1_m=screw_head_z0,
                    )
                )
                screws.append(
                    _cylinder_z_mesh(
                        center_x_m=center_x + sx,
                        center_y_m=sy,
                        radius_m=k.track_screw_head_radius_m,
                        z0_m=screw_head_z0,
                        z1_m=screw_head_z1,
                        segments=8,
                    )
                )

        bolt_x = k.clamp_bolt_axis_offset_m
        bolt_z0 = baseplate_seat_z
        bolt_z1 = bolt_z0 + k.clamp_bolt_length_m
        nut_z0 = bolt_z1 - k.nut_height_m
        for sx in (-bolt_x, +bolt_x):
            clamp_hardware.append(
                _cylinder_z_mesh(
                    center_x_m=center_x + sx,
                    center_y_m=0.0,
                    radius_m=0.5 * k.clamp_bolt_diameter_m,
                    z0_m=bolt_z0,
                    z1_m=bolt_z1,
                )
            )
            clamp_hardware.append(
                _cylinder_z_mesh(
                    center_x_m=center_x + sx,
                    center_y_m=0.0,
                    radius_m=k.nut_circumradius_m,
                    z0_m=nut_z0,
                    z1_m=bolt_z1,
                    segments=6,
                )
            )
            # Simplified KDP-2/PK clamp silhouette. Exact spring-clamp CAD is
            # explicitly outside the initial-profile source boundary.
            clamp_center_x = (
                center_x
                + math.copysign(k.spring_clamp_center_offset_m, sx)
            )
            clamp_z0 = (
                baseplate_seat_z
                + k.spring_clamp_base_above_rail_seat_m
            )
            clamp_hardware.append(
                _box_mesh(
                    center_x_m=clamp_center_x,
                    center_y_m=0.0,
                    size_x_m=k.spring_clamp_box_transverse_m,
                    size_y_m=k.spring_clamp_box_longitudinal_m,
                    z0_m=clamp_z0,
                    z1_m=clamp_z0 + k.spring_clamp_box_height_m,
                )
            )

    for suffix, obj_type, category, meshes, props in (
        (
            "UNDER_BASEPLATE_PADS",
            "production_under_baseplate_pad",
            "under_baseplate_pad",
            underpads,
            {
                "padPlanTransverseM": k.under_pad_transverse_m,
                "padPlanLongitudinalM": k.under_pad_longitudinal_m,
                "padThicknessM": k.under_pad_thickness_m,
                "holeDiameterM": k.under_pad_hole_diameter_m,
                "holeGeometryMode": "metadata_only_no_boolean_cut_v1",
                "contactBottomFacesOmitted": True,
            },
        ),
        (
            "KD65_BASEPLATES",
            "production_baseplate",
            "baseplate",
            baseplates,
            {
                "fasteningFamily": k.family,
                "baseplatePlanTransverseM": k.baseplate_transverse_m,
                "baseplatePlanLongitudinalM": k.baseplate_longitudinal_m,
                "baseplateMaximumEnvelopeHeightM": k.baseplate_max_height_m,
                "baseplateRailSeatHeightM": k.baseplate_rail_seat_height_m,
                "holeSpacingTransverseM": k.baseplate_hole_spacing_transverse_m,
                "holeSpacingLongitudinalM": k.baseplate_hole_spacing_longitudinal_m,
                "holeDiameterM": k.baseplate_hole_diameter_m,
                "holeGeometryMode": "metadata_only_no_boolean_cut_v1",
                "railSeatHeightMode": "derived_stack_fit_fallback",
                "baseplateMeshMode": k.baseplate_mesh_mode,
                "contactBottomFacesOmitted": True,
            },
        ),
        (
            "R65_RAIL_PADS",
            "production_rail_pad",
            "rail_pad",
            railpads,
            {
                "railPadPlanTransverseM": k.rail_pad_transverse_m,
                "railPadPlanLongitudinalM": k.rail_pad_longitudinal_m,
                "railPadBaseThicknessM": k.rail_pad_base_thickness_m,
                "railPadTotalThicknessM": k.rail_pad_total_thickness_m,
                "railPadRaisedSeatTransverseM": k.rail_pad_raised_seat_transverse_m,
                "baseplateContactFaceOmitted": True,
                "railFootContactFaceOmitted": True,
                "railFootContactWidthM": 2.0 * rail_foot_half,
                "padOverhangSurfacesPreserved": True,
                "perforationGeometryMode": "metadata_only_no_boolean_cut_v1",
            },
        ),
        (
            "TRACK_SCREWS",
            "production_track_screw",
            "track_screw",
            screws,
            {
                "trackScrewDiameterM": k.track_screw_diameter_m,
                "trackScrewLengthM": k.track_screw_length_m,
                "quantityPerBaseplate": k.track_screws_per_baseplate,
                "metroFastener": "24x150_flat_head",
                "headGeometry": k.track_screw_head_mode,
                "headRadiusM": k.track_screw_head_radius_m,
                "headHeightM": k.track_screw_head_height_m,
                "embeddedFastenerVolumeOverlap": True,
            },
        ),
        (
            "CLAMP_HARDWARE",
            "production_clamp_hardware",
            "clamp_hardware",
            clamp_hardware,
            {
                "clampBoltThread": "M22",
                "clampBoltLengthM": k.clamp_bolt_length_m,
                "clampBoltsPerBaseplate": k.clamp_bolts_per_baseplate,
                "nutHeightM": k.nut_height_m,
                "nutsPerBaseplate": k.nuts_per_baseplate,
                "springClampsPerBaseplate": k.spring_clamps_per_baseplate,
                "springClampGeometry": k.clamp_geometry_mode,
                "clampBoltAxisOffsetM": k.clamp_bolt_axis_offset_m,
                "nutCircumradiusM": k.nut_circumradius_m,
                "springClampCenterOffsetM": k.spring_clamp_center_offset_m,
                "springClampBoxTransverseM": k.spring_clamp_box_transverse_m,
                "springClampBoxLongitudinalM": k.spring_clamp_box_longitudinal_m,
                "springClampBoxHeightM": k.spring_clamp_box_height_m,
            },
        ),
    ):
        vertices, faces = _combine_meshes(meshes)
        result.append(
            LocalPermanentWayMesh(
                name_suffix=suffix,
                object_type=obj_type,
                category=category,
                vertices=vertices,
                faces=faces,
                properties=props,
            )
        )

    return tuple(result)
