from __future__ import annotations

"""Stage-10.4 Moscow civil-shell and raised-walkway geometry."""

from dataclasses import dataclass
import math
from typing import Sequence

from .mesh import Face, Vec3
from .moscow import MoscowStage10Profile


@dataclass(frozen=True)
class CivilShellMesh:
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    angular_segments: int
    station_count: int


def civil_ring_ranges(
    total_length_m: float,
    *,
    ring_pitch_m: float,
) -> tuple[tuple[int, float, float], ...]:
    if not math.isfinite(total_length_m) or total_length_m <= 0.0:
        raise ValueError("total_length_m must be finite and positive")
    if not math.isfinite(ring_pitch_m) or ring_pitch_m <= 0.0:
        raise ValueError("ring_pitch_m must be finite and positive")
    result: list[tuple[int, float, float]] = []
    start = 0.0
    ring_index = 0
    while start < total_length_m - 1e-12:
        end = min(total_length_m, start + ring_pitch_m)
        result.append((ring_index, start, end))
        ring_index += 1
        start = end
    return tuple(result)


def walkway_profile_xz(
    profile: MoscowStage10Profile,
    *,
    intrados_samples: int = 20,
) -> tuple[tuple[float, float], ...]:
    if intrados_samples < 4:
        raise ValueError("walkway intrados_samples must be >=4")
    w = profile.walkway
    if w.side_profile_x_sign != 1:
        raise ValueError("initial Stage-10.4 walkway is expected on +profile-X side")

    inner_x = w.inner_edge_x_m
    top_z = w.top_z_m
    c = profile.datums.lining_axis_z_m
    r = profile.intrados_radius_m
    outer_x_exact = math.sqrt(r * r - (top_z - c) * (top_z - c))
    if not math.isclose(
        w.outer_edge_x_m,
        outer_x_exact,
        abs_tol=1e-9,
    ):
        raise ValueError(
            "documented walkway outer edge does not match physical intrados"
        )
    # Geometry uses the exact circle intersection. The machine-profile datum is
    # rounded to 9 decimal places for source readability/provenance.
    outer_x = outer_x_exact

    inner_bottom_z = c - math.sqrt(r * r - inner_x * inner_x)
    concrete_top_z = (
        profile.track_concrete.surface_reference_z_m
        + profile.track_concrete.surface_cross_slope_to_drain
        * (inner_x - profile.track_concrete.surface_reference_abs_x_m)
    )
    if not (inner_bottom_z < concrete_top_z < top_z):
        raise ValueError("walkway inner-riser contact datums are inconsistent")

    points: list[tuple[float, float]] = [
        (inner_x, inner_bottom_z),
        (inner_x, concrete_top_z),
        (inner_x, top_z),
        (outer_x, top_z),
    ]

    a0 = math.atan2(outer_x, top_z - c)
    if a0 < 0.0:
        a0 += 2.0 * math.pi
    a1 = math.atan2(inner_x, inner_bottom_z - c)
    if a1 < 0.0:
        a1 += 2.0 * math.pi
    if a1 <= a0:
        raise ValueError("walkway intrados arc orientation is invalid")

    for i in range(1, intrados_samples):
        u = i / intrados_samples
        a = a0 + u * (a1 - a0)
        points.append((r * math.sin(a), c + r * math.cos(a)))
    return tuple(points)


def walkway_core_xz(
    profile: MoscowStage10Profile,
    *,
    intrados_samples: int = 20,
) -> tuple[tuple[float, float], ...]:
    return tuple(
        profile.coordinate.research_xz_to_core_xz(x, z)
        for x, z in walkway_profile_xz(
            profile,
            intrados_samples=intrados_samples,
        )
    )


def build_annular_shell_sweep(
    profile: MoscowStage10Profile,
    stations_xyz: Sequence[Vec3],
    *,
    angular_segments: int = 96,
    cap_start: bool = False,
    cap_end: bool = False,
) -> CivilShellMesh:
    """Build smooth concentric 5.5/5.1 shell along translated X/Y/Z stations.

    The initial Stage-10.4 shell intentionally contains no fabricated N/C/K
    ribs, bolt holes or series-specific circumferential segmentation.
    """
    if angular_segments < 24:
        raise ValueError("civil shell needs at least 24 angular segments")
    if len(stations_xyz) < 2:
        raise ValueError("civil shell sweep requires at least two stations")
    rin = profile.intrados_radius_m
    rout = profile.extrados_radius_m
    if not (0.0 < rin < rout):
        raise ValueError("civil shell radii are invalid")

    n = angular_segments
    vertices: list[Vec3] = []
    for ox, oy, oz in stations_xyz:
        for radius in (rin, rout):
            for i in range(n):
                a = 2.0 * math.pi * i / n
                vertices.append(
                    (
                        ox + radius * math.sin(a),
                        oy,
                        oz + radius * math.cos(a),
                    )
                )

    faces: list[Face] = []
    stride = 2 * n
    for isec in range(len(stations_xyz) - 1):
        a0 = isec * stride
        b0 = (isec + 1) * stride
        for i in range(n):
            j = (i + 1) % n
            # Inner surface faces tunnel interior.
            faces.append((a0 + i, b0 + i, b0 + j, a0 + j))
            # Outer surface faces ground/extrados.
            faces.append(
                (
                    a0 + n + i,
                    a0 + n + j,
                    b0 + n + j,
                    b0 + n + i,
                )
            )

    if cap_start:
        base = 0
        for i in range(n):
            j = (i + 1) % n
            faces.append((base + i, base + j, base + n + j, base + n + i))
    if cap_end:
        base = (len(stations_xyz) - 1) * stride
        for i in range(n):
            j = (i + 1) % n
            faces.append((base + i, base + n + i, base + n + j, base + j))

    return CivilShellMesh(
        vertices=tuple(vertices),
        faces=tuple(faces),
        angular_segments=n,
        station_count=len(stations_xyz),
    )


def build_segmented_rc_ring_sweep(
    profile: MoscowStage10Profile,
    stations_xyz: Sequence[Vec3],
    *,
    segment_count: int = 10,
    seam_width_m: float = 0.008,
    angular_subdivisions_per_segment: int = 8,
    cap_start: bool = False,
    cap_end: bool = False,
) -> CivilShellMesh:
    """Build Stage-9-like curved RC blocks on Moscow source dimensions.

    S026 fixes the 6.1/5.6 m radii, 1.0 m ring pitch and ten identical blocks.
    The exact radial-end hole/chamfer CAD is not published, so the visible
    inter-block seam is a narrow procedural gap while each block itself is a
    full-depth curved annular sector with explicit radial end faces.
    """
    if len(stations_xyz) < 2:
        raise ValueError("segmented RC ring sweep requires at least two stations")
    if segment_count < 3:
        raise ValueError("segmented RC ring requires at least three blocks")
    if angular_subdivisions_per_segment < 2:
        raise ValueError("RC block surface needs at least two angular subdivisions")
    rin = profile.intrados_radius_m
    rout = profile.extrados_radius_m
    if not (0.0 < rin < rout):
        raise ValueError("civil shell radii are invalid")
    if not (0.0 < seam_width_m < 0.25 * rin):
        raise ValueError("RC visual seam width is invalid")

    sector = 2.0 * math.pi / segment_count
    seam_angle = seam_width_m / rin
    if seam_angle >= 0.5 * sector:
        raise ValueError("RC visual seam consumes too much block angle")

    vertices: list[Vec3] = []
    faces: list[Face] = []
    n = angular_subdivisions_per_segment

    for segment_index in range(segment_count):
        center = segment_index * sector
        start = center - 0.5 * sector + 0.5 * seam_angle
        end = center + 0.5 * sector - 0.5 * seam_angle
        span = end - start
        base = len(vertices)

        for ox, oy, oz in stations_xyz:
            for iu in range(n + 1):
                angle = start + span * iu / n
                sa = math.sin(angle)
                ca = math.cos(angle)
                vertices.append((ox + rin * sa, oy, oz + rin * ca))
                vertices.append((ox + rout * sa, oy, oz + rout * ca))

        def idx(station_index: int, angular_index: int, layer: int) -> int:
            return base + 2 * (
                station_index * (n + 1) + angular_index
            ) + layer

        for station_index in range(len(stations_xyz) - 1):
            nxt_station = station_index + 1
            for iu in range(n):
                ju = iu + 1
                faces.append(
                    (
                        idx(station_index, iu, 0),
                        idx(nxt_station, iu, 0),
                        idx(nxt_station, ju, 0),
                        idx(station_index, ju, 0),
                    )
                )
                faces.append(
                    (
                        idx(station_index, iu, 1),
                        idx(station_index, ju, 1),
                        idx(nxt_station, ju, 1),
                        idx(nxt_station, iu, 1),
                    )
                )

            faces.append(
                (
                    idx(station_index, 0, 0),
                    idx(station_index, 0, 1),
                    idx(nxt_station, 0, 1),
                    idx(nxt_station, 0, 0),
                )
            )
            faces.append(
                (
                    idx(station_index, n, 0),
                    idx(nxt_station, n, 0),
                    idx(nxt_station, n, 1),
                    idx(station_index, n, 1),
                )
            )

        if cap_start:
            for iu in range(n):
                ju = iu + 1
                faces.append(
                    (
                        idx(0, iu, 0),
                        idx(0, ju, 0),
                        idx(0, ju, 1),
                        idx(0, iu, 1),
                    )
                )
        if cap_end:
            last = len(stations_xyz) - 1
            for iu in range(n):
                ju = iu + 1
                faces.append(
                    (
                        idx(last, iu, 0),
                        idx(last, iu, 1),
                        idx(last, ju, 1),
                        idx(last, ju, 0),
                    )
                )

    return CivilShellMesh(
        vertices=tuple(vertices),
        faces=tuple(faces),
        angular_segments=segment_count * n,
        station_count=len(stations_xyz),
    )

