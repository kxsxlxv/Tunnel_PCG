from __future__ import annotations

"""Stage-9 production geometry and long-tunnel assembly.

Stage 1-8 remain the reference/reconstruction baseline. Stage 9 converts that
geometry into an engine-oriented representation:

* longitudinal infrastructure is built once as continuous swept geometry rather
  than one closed solid per ring;
* internal coincident ancillary end caps are removed by construction;
* rail rectangles are replaced by a configurable low-poly rail cross-section;
* global coordinates remain global doubles -- chunking is optional export
  partitioning, not a precision workaround;
* persistent logical IDs are deterministic and independent of chunk size.
"""

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import math
from typing import Any, Callable, Iterator, Mapping, Sequence

import numpy as np

from .ancillary import (
    AncillaryConfig,
    AncillaryMesh,
    AncillarySamplingPolicy,
    AncillarySet,
    RailSpacingConvention,
    build_ancillary_set,
    sample_ancillary_config,
)
from .assembly import (
    RingPose,
    TunnelAssembly,
    TunnelAssemblyConfig,
    sample_tunnel_assembly,
)
from .angles import SegmentAngularExtent, sample_six_segment_angles
from .bolts import (
    BoltLayoutType,
    BoltPerturbationConfig,
    build_bolt_set,
    sample_bolt_config,
)
from .config import RingConfig
from .curved_mesh import SurfaceMeshingConfig
from .joints import build_prescribed_joint_set, sample_joint_config
from .mesh import (
    Face,
    RingMesh,
    Vec3,
    build_hexahedral_segment,
    build_ring_mesh,
)
from .moscow import (
    MoscowStage10Profile,
    R65ProductionProfile,
    r65_inner_working_face_x,
    r65_rail_center_offsets_for_gauge,
)
from .permanent_way import (
    build_stage10_2_local_event_meshes,
    build_modern_lvt_local_event_meshes,
    modern_lvt_chainages,
    sleeper_chainages,
    track_concrete_core_xz,
)
from .contact_rail import (
    build_stage10_3_local_support_meshes,
    build_modern_contact_support_meshes,
    contact_rail_axis_profile_x,
    contact_support_chainages,
    modern_contact_support_chainages,
    modern_cover_span_ranges,
    modern_protective_cover_core_xz,
    protective_cover_core_xz,
    rk_contact_rail_core_xz,
)
from .services import (
    build_r2k11_local_rack_mesh,
    build_water_main_support_local_mesh,
    cable_rack_chainages,
    modern_cable_sections_core,
    modern_water_main_section_core,
    water_main_support_chainages,
)
from .civil import (
    build_annular_shell_sweep,
    civil_ring_ranges,
    walkway_core_xz,
)
from .scene import (
    LabelPolicy,
    SceneMode,
    SceneObject,
    ScenePackage,
    build_nominal_scene_package,
)
from .tunnel import ProceduralTunnelBuild, build_procedural_nominal_tunnel


# ---------------------------------------------------------------------------
# Stable identities
# ---------------------------------------------------------------------------


def stable_instance_id(key: str) -> int:
    """Deterministic positive 63-bit ID independent of Python hash randomization."""
    if not key:
        raise ValueError("stable ID key must not be empty")
    digest = hashlib.blake2b(
        key.encode("utf-8"),
        digest_size=8,
        person=b"TPCG-v9",
    ).digest()
    value = int.from_bytes(digest, "big") & ((1 << 63) - 1)
    return value or 1


def _persistent_ring_key(namespace: str, obj: SceneObject) -> str:
    return f"{namespace}/ring/{obj.ring_id:08d}/{obj.name}"


def _copy_scene_object_with_stable_identity(
    obj: SceneObject,
    *,
    namespace: str,
) -> SceneObject:
    key = _persistent_ring_key(namespace, obj)
    props = dict(obj.extra_properties)
    props.update(
        {
            "persistentKey": key,
            "persistentInstanceID": stable_instance_id(key),
            "tunnelInstanceID": stable_instance_id(f"{namespace}/tunnel"),
            "identityScope": "physical_ring_object",
            "sourceInstanceIDStage8": int(obj.instance_id),
        }
    )
    return SceneObject(
        name=obj.name,
        vertices=obj.vertices,
        faces=obj.faces,
        object_type=obj.object_type,
        ring_id=obj.ring_id,
        label_id=obj.label_id,
        instance_id=stable_instance_id(key),
        semantic_class=obj.semantic_class,
        segment_id=obj.segment_id,
        segment_name=obj.segment_name,
        segment_kind=obj.segment_kind,
        reconstruction=obj.reconstruction,
        collection_path=(
            "Tunnel",
            namespace,
            "Rings",
            f"Ring_{obj.ring_id:08d}",
            *obj.collection_path[1:],
        )
        if obj.collection_path
        else ("Tunnel", namespace, "Rings", f"Ring_{obj.ring_id:08d}"),
        extra_properties=props,
    )


# ---------------------------------------------------------------------------
# Generic production rail profile
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RailProfile:
    """Low-poly generic rail profile, intentionally not a country-specific rail."""

    overall_height_m: float
    head_width_m: float
    head_height_m: float
    web_thickness_m: float
    foot_width_m: float
    foot_height_m: float

    def __post_init__(self) -> None:
        values = (
            self.overall_height_m,
            self.head_width_m,
            self.head_height_m,
            self.web_thickness_m,
            self.foot_width_m,
            self.foot_height_m,
        )
        if any((not math.isfinite(v) or v <= 0.0) for v in values):
            raise ValueError("rail profile dimensions must be finite and positive")
        if self.web_thickness_m >= self.head_width_m:
            raise ValueError("rail web must be narrower than head")
        if self.head_width_m > self.foot_width_m:
            raise ValueError("rail head must not exceed foot width")
        if self.foot_height_m + self.head_height_m >= self.overall_height_m:
            raise ValueError("rail head+foot heights leave no web")

    @classmethod
    def generic_from_ancillary(cls, config: AncillaryConfig) -> "RailProfile":
        return cls(
            overall_height_m=config.rail_depth_m,
            head_width_m=0.72 * config.rail_width_m,
            head_height_m=0.30 * config.rail_depth_m,
            web_thickness_m=0.28 * config.rail_width_m,
            foot_width_m=config.rail_width_m,
            foot_height_m=0.18 * config.rail_depth_m,
        )

    def points_xz(
        self,
        *,
        center_x_m: float,
        base_z_m: float,
    ) -> tuple[tuple[float, float], ...]:
        """Return a symmetric 16-vertex rail polygon."""
        fw = self.foot_width_m
        hw = self.head_width_m
        ww = self.web_thickness_m
        H = self.overall_height_m
        fh = self.foot_height_m
        hh = self.head_height_m
        head_bottom = H - hh

        local = (
            (-0.50 * fw, 0.00),
            (+0.50 * fw, 0.00),
            (+0.50 * fw, 0.55 * fh),
            (+0.32 * fw, 1.00 * fh),
            (+0.50 * ww, 1.15 * fh),
            (+0.50 * ww, head_bottom - 0.12 * hh),
            (+0.42 * hw, head_bottom),
            (+0.50 * hw, head_bottom + 0.35 * hh),
            (+0.44 * hw, H),
            (-0.44 * hw, H),
            (-0.50 * hw, head_bottom + 0.35 * hh),
            (-0.42 * hw, head_bottom),
            (-0.50 * ww, head_bottom - 0.12 * hh),
            (-0.50 * ww, 1.15 * fh),
            (-0.32 * fw, 1.00 * fh),
            (-0.50 * fw, 0.55 * fh),
        )
        return tuple((center_x_m + x, base_z_m + z) for x, z in local)


# ---------------------------------------------------------------------------
# Longitudinal alignment
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AlignmentStation:
    """Production alignment sample.

    chainage_m starts at the front face of the first ring. world_y_m keeps the
    existing Stage-7 coordinate convention, where ring-0 centre is y=0.
    """

    chainage_m: float
    world_y_m: float
    offset_x_m: float
    offset_z_m: float
    source: str


def production_alignment_stations(
    assembly: TunnelAssembly,
) -> tuple[AlignmentStation, ...]:
    poses = assembly.poses
    if not poses:
        raise ValueError("assembly has no poses")
    L = assembly.config.ring_width_m
    n = len(poses)

    def xz(i: int) -> tuple[float, float]:
        p = poses[i].translation_m
        return float(p[0]), float(p[2])

    stations: list[AlignmentStation] = []

    c0x, c0z = xz(0)
    if n > 1:
        c1x, c1z = xz(1)
        sx = c0x - 0.5 * (c1x - c0x)
        sz = c0z - 0.5 * (c1z - c0z)
    else:
        sx, sz = c0x, c0z
    stations.append(AlignmentStation(0.0, -0.5 * L, sx, sz, "tunnel_start"))

    for i in range(n):
        cx, cz = xz(i)
        center_chainage = (i + 0.5) * L
        stations.append(
            AlignmentStation(
                center_chainage,
                poses[i].chainage_m,
                cx,
                cz,
                f"ring_{i:08d}_center",
            )
        )
        if i + 1 < n:
            nx, nz = xz(i + 1)
            boundary_chainage = (i + 1) * L
            stations.append(
                AlignmentStation(
                    boundary_chainage,
                    poses[i].chainage_m + 0.5 * L,
                    0.5 * (cx + nx),
                    0.5 * (cz + nz),
                    f"ring_{i:08d}_{i+1:08d}_boundary",
                )
            )

    clx, clz = xz(n - 1)
    if n > 1:
        px, pz = xz(n - 2)
        ex = clx + 0.5 * (clx - px)
        ez = clz + 0.5 * (clz - pz)
    else:
        ex, ez = clx, clz
    stations.append(
        AlignmentStation(
            n * L,
            poses[-1].chainage_m + 0.5 * L,
            ex,
            ez,
            "tunnel_end",
        )
    )

    result = tuple(stations)
    if any(b.chainage_m <= a.chainage_m for a, b in zip(result, result[1:])):
        raise AssertionError("production alignment stations are not strictly increasing")
    return result


def sample_alignment_station(
    stations: Sequence[AlignmentStation],
    chainage_m: float,
) -> AlignmentStation:
    if not stations:
        raise ValueError("stations must not be empty")
    if not math.isfinite(chainage_m):
        raise ValueError("chainage must be finite")

    start = stations[0].chainage_m
    end = stations[-1].chainage_m

    # A fixed 1e-12 m boundary tolerance is too small once chainage reaches
    # kilometre scale.  Moscow 1.0 m civil-ring coordinates are composed from
    # a separate rhythm over the source 1.35 m alignment; after thousands of
    # rings, mathematically identical endpoints can differ by several IEEE-754
    # ulps.  Accept only that numerical fuzz -- not a real geometric overrun.
    magnitude = max(abs(start), abs(end), abs(chainage_m), 1.0)
    numerical_tol = max(1e-12, 32.0 * math.ulp(magnitude))
    if chainage_m < start - numerical_tol or chainage_m > end + numerical_tol:
        raise ValueError(
            "chainage outside station range: "
            f"{chainage_m:.17g} not in [{start:.17g}, {end:.17g}] "
            f"(numerical tolerance {numerical_tol:.3g} m)"
        )

    # Snap only values that lie outside the closed range by floating-point
    # fuzz. This keeps interpolation strictly inside the physical alignment and
    # still fails for any material overrun.
    if chainage_m < start:
        chainage_m = start
    elif chainage_m > end:
        chainage_m = end

    if math.isclose(chainage_m, start, rel_tol=0.0, abs_tol=numerical_tol):
        return stations[0]
    if math.isclose(chainage_m, end, rel_tol=0.0, abs_tol=numerical_tol):
        return stations[-1]

    # Binary search avoids an O(N) scan for every vertex on long production
    # scenes (3000 source rings -> 6001 alignment stations).
    lo = 0
    hi = len(stations) - 1
    while hi - lo > 1:
        mid = (lo + hi) // 2
        if stations[mid].chainage_m <= chainage_m:
            lo = mid
        else:
            hi = mid

    a = stations[lo]
    b = stations[hi]
    local_scale = max(
        abs(a.chainage_m),
        abs(b.chainage_m),
        abs(chainage_m),
        1.0,
    )
    local_tol = max(1e-12, 32.0 * math.ulp(local_scale))
    if math.isclose(
        chainage_m,
        a.chainage_m,
        rel_tol=0.0,
        abs_tol=local_tol,
    ):
        return a
    if math.isclose(
        chainage_m,
        b.chainage_m,
        rel_tol=0.0,
        abs_tol=local_tol,
    ):
        return b
    if not (
        a.chainage_m - local_tol
        <= chainage_m
        <= b.chainage_m + local_tol
    ):
        raise AssertionError("binary alignment bracket does not contain chainage")

    u = (chainage_m - a.chainage_m) / (b.chainage_m - a.chainage_m)
    return AlignmentStation(
        chainage_m=float(chainage_m),
        world_y_m=a.world_y_m + u * (b.world_y_m - a.world_y_m),
        offset_x_m=a.offset_x_m + u * (b.offset_x_m - a.offset_x_m),
        offset_z_m=a.offset_z_m + u * (b.offset_z_m - a.offset_z_m),
        source="interpolated",
    )


def _sample_alignment_station_with_terminal_extrapolation(
    stations: Sequence[AlignmentStation],
    chainage_m: float,
    *,
    max_extrapolation_m: float,
) -> AlignmentStation:
    """Sample alignment, allowing a tightly bounded terminal linear extension.

    This is intentionally private and used only for transferred Stage-9
    fastener meshes that physically protrude a few millimetres beyond the
    first/last Moscow civil ring. The public sampler remains strict.
    """
    if not math.isfinite(max_extrapolation_m) or max_extrapolation_m < 0.0:
        raise ValueError("max_extrapolation_m must be finite and non-negative")
    try:
        return sample_alignment_station(stations, chainage_m)
    except ValueError:
        pass

    if len(stations) < 2:
        raise ValueError("terminal alignment extrapolation needs two stations")

    start = stations[0].chainage_m
    end = stations[-1].chainage_m
    scale = max(abs(start), abs(end), abs(chainage_m), 1.0)
    tol = max(1e-12, 32.0 * math.ulp(scale))

    if chainage_m < start:
        overrun = start - chainage_m
        a, b = stations[0], stations[1]
        source = "terminal_extrapolated_before_start"
    elif chainage_m > end:
        overrun = chainage_m - end
        a, b = stations[-2], stations[-1]
        source = "terminal_extrapolated_after_end"
    else:
        # If the strict sampler failed for a value inside the closed interval,
        # that is a real interpolation bug and must not be hidden here.
        raise AssertionError("strict alignment sampler failed inside range")

    if overrun > max_extrapolation_m + tol:
        raise ValueError(
            "terminal alignment extrapolation exceeds object overhang: "
            f"{overrun:.17g} m > {max_extrapolation_m:.17g} m"
        )

    span = b.chainage_m - a.chainage_m
    if span <= 0.0:
        raise ValueError("terminal alignment stations are not increasing")
    u = (chainage_m - a.chainage_m) / span
    return AlignmentStation(
        chainage_m=float(chainage_m),
        world_y_m=a.world_y_m + u * (b.world_y_m - a.world_y_m),
        offset_x_m=a.offset_x_m + u * (b.offset_x_m - a.offset_x_m),
        offset_z_m=a.offset_z_m + u * (b.offset_z_m - a.offset_z_m),
        source=source,
    )


def _alignment_station_insertion_index(
    stations: Sequence[AlignmentStation],
    chainage_m: float,
    *,
    right: bool,
) -> int:
    """Return a binary-search insertion point for monotonic station chainage."""
    lo = 0
    hi = len(stations)
    while lo < hi:
        mid = (lo + hi) // 2
        value = stations[mid].chainage_m
        if value < chainage_m or (right and value == chainage_m):
            lo = mid + 1
        else:
            hi = mid
    return lo


def clipped_alignment_stations(
    stations: Sequence[AlignmentStation],
    *,
    start_chainage_m: float,
    end_chainage_m: float,
) -> tuple[AlignmentStation, ...]:
    if end_chainage_m <= start_chainage_m:
        raise ValueError("chunk end must be greater than start")
    first = sample_alignment_station(stations, start_chainage_m)
    last = sample_alignment_station(stations, end_chainage_m)
    tol = 1e-10
    first_middle = _alignment_station_insertion_index(
        stations,
        start_chainage_m + tol,
        right=True,
    )
    last_middle = _alignment_station_insertion_index(
        stations,
        end_chainage_m - tol,
        right=False,
    )
    middle = tuple(
        stations[index]
        for index in range(first_middle, last_middle)
    )
    result = (first, *middle, last)
    if any(
        b.chainage_m <= a.chainage_m + 1e-12
        for a, b in zip(result, result[1:])
    ):
        raise AssertionError("clipped alignment contains duplicate/non-increasing stations")
    return result


def compact_exact_collinear_alignment_stations(
    stations: Sequence[AlignmentStation],
    *,
    tolerance_m: float = 1e-12,
) -> tuple[AlignmentStation, ...]:
    """Remove mathematically redundant samples from a continuous sweep path.

    Stage-9 inserts explicit ring-boundary midpoint stations so ring-local
    geometry stitches exactly. For a continuous sweep those midpoints lie on
    the same piecewise-linear segment and can be removed with zero geometric
    change. Stage 10.5 enables this as a safe polygon-count optimization.
    """
    result = tuple(stations)
    if len(result) <= 2:
        return result
    if not math.isfinite(tolerance_m) or tolerance_m < 0.0:
        raise ValueError(
            "alignment compaction tolerance must be finite and non-negative"
        )

    kept: list[AlignmentStation] = [result[0]]
    for i in range(1, len(result) - 1):
        a = kept[-1]
        b = result[i]
        d = result[i + 1]
        span = d.chainage_m - a.chainage_m
        if span <= 0.0:
            raise ValueError("alignment stations must be strictly increasing")
        u = (b.chainage_m - a.chainage_m) / span
        expected_y = a.world_y_m + u * (d.world_y_m - a.world_y_m)
        expected_x = a.offset_x_m + u * (d.offset_x_m - a.offset_x_m)
        expected_z = a.offset_z_m + u * (d.offset_z_m - a.offset_z_m)
        if (
            abs(b.world_y_m - expected_y) <= tolerance_m
            and abs(b.offset_x_m - expected_x) <= tolerance_m
            and abs(b.offset_z_m - expected_z) <= tolerance_m
        ):
            continue
        kept.append(b)
    kept.append(result[-1])
    return tuple(kept)


def _stable_unit_fraction(*parts: object) -> float:
    payload = "|".join(str(part) for part in parts).encode("utf-8")
    digest = hashlib.blake2b(payload, digest_size=8).digest()
    return int.from_bytes(digest, "big") / float((1 << 64) - 1)


def _cable_span_sag_parameters(
    *,
    asset_key: str,
    span_index: int,
    base_sag_m: float,
    variation_fraction: float,
    peak_phase_jitter_fraction: float,
) -> tuple[float, float]:
    amp_u = _stable_unit_fraction(asset_key, span_index, "amp")
    phase_u = _stable_unit_fraction(asset_key, span_index, "phase")
    amplitude = base_sag_m * (
        1.0 + variation_fraction * (2.0 * amp_u - 1.0)
    )
    peak_fraction = 0.5 + peak_phase_jitter_fraction * (
        2.0 * phase_u - 1.0
    )
    return amplitude, peak_fraction


def _periodic_cable_sag_alignment_stations(
    stations: Sequence[AlignmentStation],
    *,
    support_pitch_m: float,
    support_phase_m: float,
    midspan_sag_m: float,
    variation_fraction: float = 0.0,
    peak_phase_jitter_fraction: float = 0.0,
    asset_key: str = "cable",
) -> tuple[AlignmentStation, ...]:
    """Add one deterministic irregular sag peak between periodic supports.

    Every cable/span receives a stable amplitude and a slightly shifted peak
    position derived from the asset key and support-span index. Supports stay
    at zero sag. Only one new interior control station is inserted per span,
    so visual irregularity does not require dense spline tessellation.
    """
    base = tuple(stations)
    if len(base) < 2:
        raise ValueError("cable sag requires at least two alignment stations")
    if (
        not math.isfinite(support_pitch_m)
        or support_pitch_m <= 0.0
        or not math.isfinite(support_phase_m)
        or not math.isfinite(midspan_sag_m)
        or midspan_sag_m < 0.0
        or not math.isfinite(variation_fraction)
        or not (0.0 <= variation_fraction <= 0.75)
        or not math.isfinite(peak_phase_jitter_fraction)
        or not (0.0 <= peak_phase_jitter_fraction <= 0.25)
    ):
        raise ValueError("invalid periodic cable-sag parameters")
    if midspan_sag_m <= 0.0:
        return base

    start = base[0].chainage_m
    end = base[-1].chainage_m
    chainages = {float(station.chainage_m) for station in base}

    k0 = int(math.floor((start - support_phase_m) / support_pitch_m)) - 1
    k1 = int(math.ceil((end - support_phase_m) / support_pitch_m)) + 1
    for k in range(k0, k1 + 1):
        support = support_phase_m + k * support_pitch_m
        _, peak_fraction = _cable_span_sag_parameters(
            asset_key=asset_key,
            span_index=k,
            base_sag_m=midspan_sag_m,
            variation_fraction=variation_fraction,
            peak_phase_jitter_fraction=peak_phase_jitter_fraction,
        )
        peak = support + peak_fraction * support_pitch_m
        if start + 1e-12 < support < end - 1e-12:
            chainages.add(float(support))
        if start + 1e-12 < peak < end - 1e-12:
            chainages.add(float(peak))

    result: list[AlignmentStation] = []
    for chainage in sorted(chainages):
        base_station = sample_alignment_station(base, chainage)
        phase = (chainage - support_phase_m) / support_pitch_m
        span_index = int(math.floor(phase))
        fraction = phase - span_index
        amplitude, peak_fraction = _cable_span_sag_parameters(
            asset_key=asset_key,
            span_index=span_index,
            base_sag_m=midspan_sag_m,
            variation_fraction=variation_fraction,
            peak_phase_jitter_fraction=peak_phase_jitter_fraction,
        )
        if fraction <= peak_fraction:
            local = fraction / peak_fraction
        else:
            local = (1.0 - fraction) / (1.0 - peak_fraction)
        local = max(0.0, min(1.0, local))
        sag_factor = math.sin(0.5 * math.pi * local)
        result.append(
            AlignmentStation(
                chainage_m=base_station.chainage_m,
                world_y_m=base_station.world_y_m,
                offset_x_m=base_station.offset_x_m,
                offset_z_m=(
                    base_station.offset_z_m
                    - amplitude * sag_factor
                ),
                source=f"{base_station.source}|cable_sag_irregular",
            )
        )
    return tuple(result)


# ---------------------------------------------------------------------------
# Continuous asset specs and sweep meshing
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ContinuousAssetSpec:
    persistent_key: str
    name: str
    object_type: str
    category: str
    cross_section_xz: tuple[tuple[float, float], ...]
    label_id: int
    semantic_class: str
    omitted_longitudinal_edges: tuple[int, ...] = ()
    properties: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if len(self.cross_section_xz) < 3:
            raise ValueError(f"{self.name}: cross-section needs >=3 vertices")
        if not self.persistent_key:
            raise ValueError("continuous asset persistent key is empty")
        n = len(self.cross_section_xz)
        if any(i < 0 or i >= n for i in self.omitted_longitudinal_edges):
            raise ValueError(f"{self.name}: omitted edge index outside cross-section")
        if len(set(self.omitted_longitudinal_edges)) != len(self.omitted_longitudinal_edges):
            raise ValueError(f"{self.name}: duplicate omitted edge index")

    @property
    def instance_id(self) -> int:
        return stable_instance_id(self.persistent_key)


@dataclass(frozen=True)
class SweepMesh:
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    cross_section_vertices: int
    station_count: int
    cap_start: bool
    cap_end: bool


def _polygon_signed_area_xz(points: Sequence[tuple[float, float]]) -> float:
    area = 0.0
    n = len(points)
    for i in range(n):
        x0, z0 = points[i]
        x1, z1 = points[(i + 1) % n]
        area += x0 * z1 - x1 * z0
    return 0.5 * area


def _ensure_ccw_xz(
    points: Sequence[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    result = tuple((float(x), float(z)) for x, z in points)
    area = _polygon_signed_area_xz(result)
    if abs(area) <= 1e-15:
        raise ValueError("degenerate production cross-section")
    return result if area > 0.0 else tuple(reversed(result))


def build_sweep_mesh(
    cross_section_xz: Sequence[tuple[float, float]],
    stations: Sequence[AlignmentStation],
    *,
    cap_start: bool = True,
    cap_end: bool = True,
    omit_edge_indices: Sequence[int] = (),
) -> SweepMesh:
    points = _ensure_ccw_xz(cross_section_xz)
    if len(stations) < 2:
        raise ValueError("sweep needs at least two alignment stations")
    if any(b.chainage_m <= a.chainage_m for a, b in zip(stations, stations[1:])):
        raise ValueError("sweep stations must be strictly increasing")

    n = len(points)
    omitted = set(int(i) for i in omit_edge_indices)
    if any(i < 0 or i >= n for i in omitted):
        raise ValueError("sweep omitted edge index outside cross-section")
    vertices: list[Vec3] = []
    for station in stations:
        for x, z in points:
            vertices.append(
                (
                    x + station.offset_x_m,
                    station.world_y_m,
                    z + station.offset_z_m,
                )
            )

    faces: list[Face] = []
    for isec in range(len(stations) - 1):
        a0 = isec * n
        b0 = (isec + 1) * n
        for i in range(n):
            if i in omitted:
                continue
            j = (i + 1) % n
            faces.append((a0 + i, a0 + j, b0 + j, b0 + i))

    if cap_start:
        faces.append(tuple(reversed(tuple(range(n)))))
    if cap_end:
        base = (len(stations) - 1) * n
        faces.append(tuple(base + i for i in range(n)))

    return SweepMesh(
        vertices=tuple(vertices),
        faces=tuple(faces),
        cross_section_vertices=n,
        station_count=len(stations),
        cap_start=cap_start,
        cap_end=cap_end,
    )


def _section_from_ancillary_mesh(
    mesh: AncillaryMesh,
    ancillary: AncillarySet,
) -> tuple[tuple[float, float], ...]:
    sections = ancillary.config.longitudinal_subdivisions + 1
    if len(mesh.vertices) % sections != 0:
        raise ValueError(f"{mesh.name}: cannot infer Stage-8 cross-section size")
    n = len(mesh.vertices) // sections
    return tuple((float(v[0]), float(v[2])) for v in mesh.vertices[:n])


def _ancillary_semantics(
    label_policy: LabelPolicy,
    category: str,
) -> tuple[int, str]:
    if label_policy is LabelPolicy.SEG2TUNNEL_LIKE:
        return 0, "clutter"
    if label_policy is LabelPolicy.STSD_COARSE:
        if category == "walkway":
            return 2, "walkway"
        if category == "tube":
            return 3, "tubes"
        return 0, "clutter"
    raise NotImplementedError(label_policy)


def _civil_semantics(
    label_policy: LabelPolicy,
) -> tuple[int, str]:
    if label_policy is LabelPolicy.STSD_COARSE:
        return 1, "segments"
    if label_policy is LabelPolicy.SEG2TUNNEL_LIKE:
        return 0, "clutter"
    raise NotImplementedError(label_policy)


def _edges_on_core_intrados(
    points: Sequence[tuple[float, float]],
    *,
    radius_m: float,
    tolerance_m: float = 2e-9,
) -> tuple[int, ...]:
    result: list[int] = []
    n = len(points)
    for i in range(n):
        p0 = points[i]
        p1 = points[(i + 1) % n]
        if (
            abs(math.hypot(p0[0], p0[1]) - radius_m) <= tolerance_m
            and abs(math.hypot(p1[0], p1[1]) - radius_m) <= tolerance_m
        ):
            result.append(i)
    return tuple(result)


def _edges_on_vertical_contact(
    points: Sequence[tuple[float, float]],
    *,
    x_m: float,
    max_z_m: float,
    tolerance_m: float = 2e-9,
) -> tuple[int, ...]:
    result: list[int] = []
    n = len(points)
    for i in range(n):
        p0 = points[i]
        p1 = points[(i + 1) % n]
        if (
            abs(p0[0] - x_m) <= tolerance_m
            and abs(p1[0] - x_m) <= tolerance_m
            and max(p0[1], p1[1]) <= max_z_m + tolerance_m
        ):
            result.append(i)
    return tuple(result)


def _edges_with_both_vertices_at_z(
    points: Sequence[tuple[float, float]],
    z_m: float,
    *,
    tolerance_m: float = 1e-10,
) -> tuple[int, ...]:
    result = []
    n = len(points)
    for i in range(n):
        z0 = points[i][1]
        z1 = points[(i + 1) % n][1]
        if abs(z0 - z_m) <= tolerance_m and abs(z1 - z_m) <= tolerance_m:
            result.append(i)
    return tuple(result)


def _rail_center_offsets(config: AncillaryConfig) -> tuple[float, float]:
    offset = (
        0.5 * config.rail_spacing_m
        if config.rail_spacing_convention is RailSpacingConvention.TABLE4_CENTER_SPACING
        else config.rail_spacing_m
    )
    return (-offset, +offset)


def build_continuous_asset_specs(
    *,
    namespace: str,
    ancillary: AncillarySet,
    label_policy: LabelPolicy,
    rail_profile: RailProfile | None = None,
    moscow_profile: MoscowStage10Profile | None = None,
    moscow_stage: str = "10.1",
    moscow_service_preset: str = "legacy",
) -> tuple[ContinuousAssetSpec, ...]:
    if not namespace:
        raise ValueError("namespace must not be empty")
    if moscow_stage not in {"10.1", "10.2", "10.3", "10.4", "10.5"}:
        raise ValueError(
            "moscow_stage must be '10.1', '10.2', '10.3', '10.4' or '10.5'"
        )
    if moscow_stage != "10.1" and moscow_profile is None:
        raise ValueError("Moscow Stage 10.2-10.5 requires moscow_profile")
    if moscow_profile is None:
        if moscow_service_preset not in {"none", "legacy"}:
            raise ValueError(
                "non-Moscow production may only use the internal 'none' service preset"
            )
    elif moscow_service_preset not in {"legacy", "modern"}:
        raise ValueError("moscow_service_preset must be 'legacy' or 'modern'")
    profile = rail_profile or RailProfile.generic_from_ancillary(ancillary.config)
    specs: list[ContinuousAssetSpec] = []

    for mesh in ancillary.meshes:
        if mesh.category == "rail":
            continue
        if (
            moscow_profile is not None
            and moscow_stage in {"10.2", "10.3", "10.4", "10.5"}
            and mesh.category == "pavement"
        ):
            continue
        if (
            moscow_profile is not None
            and moscow_stage in {"10.4", "10.5"}
            and mesh.category == "walkway"
        ):
            continue
        if (
            moscow_profile is not None
            and moscow_stage == "10.5"
            and moscow_service_preset == "modern"
            and mesh.category == "tube"
        ):
            continue
        label_id, semantic = _ancillary_semantics(label_policy, mesh.category)
        key = f"{namespace}/infrastructure/{mesh.category}/{mesh.name}"
        section = _ensure_ccw_xz(_section_from_ancillary_mesh(mesh, ancillary))
        omitted_edges: tuple[int, ...] = ()
        if mesh.category == "pavement":
            # Only the horizontal top edge is visible to the tunnel interior.
            # The remaining circular-segment perimeter is a hidden contact
            # surface against the lining intrados.
            top_z = float(mesh.properties["pavementTopZ"])
            top_edges = set(_edges_with_both_vertices_at_z(section, top_z))
            if len(top_edges) != 1:
                raise AssertionError("production pavement must have one horizontal top edge")
            omitted_edges = tuple(i for i in range(len(section)) if i not in top_edges)
        specs.append(
            ContinuousAssetSpec(
                persistent_key=key,
                name=f"PROD_{mesh.name.upper()}",
                object_type=f"production_{mesh.category}",
                category=mesh.category,
                cross_section_xz=section,
                label_id=label_id,
                semantic_class=semantic,
                omitted_longitudinal_edges=omitted_edges,
                properties={
                    **mesh.properties,
                    "sourceStage8Name": mesh.name,
                    "productionContinuous": True,
                },
            )
        )

    if (
        moscow_profile is not None
        and moscow_stage == "10.5"
        and moscow_service_preset == "modern"
    ):
        cable_label, cable_semantic = _ancillary_semantics(
            label_policy,
            "tube",
        )
        for cable_name, section, cable_props in modern_cable_sections_core(
            moscow_profile
        ):
            specs.append(
                ContinuousAssetSpec(
                    persistent_key=(
                        f"{namespace}/services/cable/{cable_name}"
                    ),
                    name=f"PROD_SERVICE_{cable_name.upper()}",
                    object_type="production_service_cable",
                    category="cable",
                    cross_section_xz=_ensure_ccw_xz(section),
                    label_id=cable_label,
                    semantic_class=cable_semantic,
                    properties={
                        **dict(cable_props),
                        "productionContinuous": True,
                        "domainGeometryStage": "10.5",
                        "servicePreset": (
                            moscow_profile.default_service_preset
                        ),
                        "supportFamily": moscow_profile.cable_rack.family,
                        "insideMoscowIntrados": True,
                        "moscowProfileID": moscow_profile.profile_id,
                        "moscowProfileSHA256": (
                            moscow_profile.provenance.canonical_sha256
                        ),
                    },
                )
            )

        water_section, water_props = modern_water_main_section_core(
            moscow_profile
        )
        specs.append(
            ContinuousAssetSpec(
                persistent_key=f"{namespace}/services/water-main/0",
                name="PROD_TUNNEL_WATER_MAIN_DN80",
                object_type="production_water_main",
                category="water_main",
                cross_section_xz=_ensure_ccw_xz(water_section),
                label_id=cable_label,
                semantic_class=cable_semantic,
                properties={
                    **dict(water_props),
                    "productionContinuous": True,
                    "domainGeometryStage": "10.5",
                    "servicePreset": moscow_profile.default_service_preset,
                    "moscowProfileID": moscow_profile.profile_id,
                    "moscowProfileSHA256": (
                        moscow_profile.provenance.canonical_sha256
                    ),
                },
            )
        )

    if moscow_profile is not None and moscow_stage in {"10.2", "10.3", "10.4", "10.5"}:
        r65_for_concrete = R65ProductionProfile()
        centers_for_concrete = r65_rail_center_offsets_for_gauge(
            moscow_profile.track.gauge_m,
            profile=r65_for_concrete,
            measurement_below_top_m=(
                moscow_profile.track.gauge_measurement_below_ugr_m
            ),
        )
        concrete_section = _ensure_ccw_xz(
            track_concrete_core_xz(
                moscow_profile,
                rail_centers_profile_x=centers_for_concrete,
                walkway_inner_edge_x_m=(
                    moscow_profile.walkway.inner_edge_x_m
                    if moscow_stage in {"10.4", "10.5"}
                    else None
                ),
            )
        )
        label_id, semantic = _ancillary_semantics(
            label_policy,
            "pavement",
        )
        concrete_omitted_edges: tuple[int, ...] = ()
        if moscow_stage in {"10.4", "10.5"}:
            walkway_x_core = (
                moscow_profile.coordinate.profile_x_to_core_x_sign
                * moscow_profile.walkway.inner_edge_x_m
            )
            walkway_concrete_top_profile_z = (
                moscow_profile.track_concrete.surface_reference_z_m
                + moscow_profile.track_concrete.surface_cross_slope_to_drain
                * (
                    moscow_profile.walkway.inner_edge_x_m
                    - moscow_profile.track_concrete.surface_reference_abs_x_m
                )
            )
            walkway_concrete_top_core_z = (
                walkway_concrete_top_profile_z
                + moscow_profile.coordinate.profile_z_to_core_z_offset_m
            )
            concrete_omitted_edges = tuple(sorted(set(
                _edges_on_core_intrados(
                    concrete_section,
                    radius_m=moscow_profile.intrados_radius_m,
                )
                + _edges_on_vertical_contact(
                    concrete_section,
                    x_m=walkway_x_core,
                    max_z_m=walkway_concrete_top_core_z,
                )
            )))
        specs.append(
            ContinuousAssetSpec(
                persistent_key=(
                    f"{namespace}/infrastructure/track-concrete/0"
                ),
                name="PROD_TRACK_CONCRETE",
                object_type="production_track_concrete",
                category="track_concrete",
                cross_section_xz=concrete_section,
                label_id=label_id,
                semantic_class=semantic,
                omitted_longitudinal_edges=concrete_omitted_edges,
                properties={
                    "productionContinuous": True,
                    "domainGeometryStage": "10.2",
                    "concreteMaterial": (
                        moscow_profile.track_concrete.concrete_material
                    ),
                    "surfaceCrossSlopeToDrain": (
                        moscow_profile.track_concrete.surface_cross_slope_to_drain
                    ),
                    "concreteSurfaceReferenceAbsXM": (
                        moscow_profile.track_concrete.surface_reference_abs_x_m
                    ),
                    "concreteSurfaceReferenceProfileZM": (
                        moscow_profile.track_concrete.surface_reference_z_m
                    ),
                    "centralDrainClearWidthM": (
                        moscow_profile.track_concrete.central_drain_clear_width_m
                    ),
                    "centralDrainBottomProfileZM": (
                        moscow_profile.track_concrete.central_drain_bottom_z_m
                    ),
                    "waterReleaseGrooveWidthM": (
                        moscow_profile.track_concrete.water_groove_width_m
                    ),
                    "waterReleaseGrooveDepthM": (
                        moscow_profile.track_concrete.water_groove_depth_m
                    ),
                    "waterReleaseGroovePositionMode": (
                        moscow_profile.track_concrete.groove_position_mode
                    ),
                    "surfaceReferenceMode": (
                        moscow_profile.track_concrete.surface_reference_mode
                    ),
                    "physicalBottomSurface": (
                        f"moscow_{int(round(2000.0 * moscow_profile.intrados_radius_m))}_intrados"
                        if moscow_stage in {"10.4", "10.5"}
                        else (
                            "future_moscow_intrados_not_clearance_envelope"
                        )
                    ),
                    "walkwayShoulderPartitioned": moscow_stage in {"10.4", "10.5"},
                    "liningContactFacesOmitted": moscow_stage in {"10.4", "10.5"},
                    "moscowProfileID": moscow_profile.profile_id,
                    "moscowProfileSHA256": (
                        moscow_profile.provenance.canonical_sha256
                    ),
                },
            )
        )

    if moscow_profile is not None and moscow_stage in {"10.4", "10.5"}:
        walkway_section = _ensure_ccw_xz(walkway_core_xz(moscow_profile))
        walkway_label, walkway_semantic = _ancillary_semantics(
            label_policy,
            "walkway",
        )
        walkway_x_core = (
            moscow_profile.coordinate.profile_x_to_core_x_sign
            * moscow_profile.walkway.inner_edge_x_m
        )
        walkway_concrete_top_profile_z = (
            moscow_profile.track_concrete.surface_reference_z_m
            + moscow_profile.track_concrete.surface_cross_slope_to_drain
            * (
                moscow_profile.walkway.inner_edge_x_m
                - moscow_profile.track_concrete.surface_reference_abs_x_m
            )
        )
        walkway_concrete_top_core_z = (
            walkway_concrete_top_profile_z
            + moscow_profile.coordinate.profile_z_to_core_z_offset_m
        )
        walkway_omitted_edges = tuple(sorted(set(
            _edges_on_core_intrados(
                walkway_section,
                radius_m=moscow_profile.intrados_radius_m,
            )
            + _edges_on_vertical_contact(
                walkway_section,
                x_m=walkway_x_core,
                max_z_m=walkway_concrete_top_core_z,
            )
        )))
        specs.append(
            ContinuousAssetSpec(
                persistent_key=f"{namespace}/infrastructure/walkway/0",
                name="PROD_MOSCOW_WALKWAY",
                object_type="production_moscow_walkway",
                category="walkway",
                cross_section_xz=walkway_section,
                label_id=walkway_label,
                semantic_class=walkway_semantic,
                omitted_longitudinal_edges=walkway_omitted_edges,
                properties={
                    "productionContinuous": True,
                    "domainGeometryStage": "10.4",
                    "geometryMode": moscow_profile.walkway.geometry_mode,
                    "walkwayTopProfileZM": moscow_profile.walkway.top_z_m,
                    "walkwayTopCoreZM": (
                        moscow_profile.walkway.top_z_m
                        + moscow_profile.coordinate.profile_z_to_core_z_offset_m
                    ),
                    "walkwayInnerEdgeProfileXM": (
                        moscow_profile.walkway.inner_edge_x_m
                    ),
                    "walkwayOuterEdgeProfileXM": (
                        moscow_profile.walkway.outer_edge_x_m
                    ),
                    "walkwayTopClearWidthM": (
                        moscow_profile.walkway.top_clear_width_m
                    ),
                    "sideProfileXSign": (
                        moscow_profile.walkway.side_profile_x_sign
                    ),
                    "oppositeContactRail": True,
                    "trackConcreteContactFacesOmitted": True,
                    "liningContactFacesOmitted": True,
                    "serviceEraInterpretation": (
                        moscow_profile.walkway.service_era_interpretation
                    ),
                    "moscowProfileID": moscow_profile.profile_id,
                    "moscowProfileSHA256": (
                        moscow_profile.provenance.canonical_sha256
                    ),
                },
            )
        )

    if moscow_profile is not None and moscow_stage in {"10.3", "10.4", "10.5"}:
        cr = moscow_profile.contact_rail
        contact_axis_profile_x = contact_rail_axis_profile_x(moscow_profile)
        contact_section = _ensure_ccw_xz(
            rk_contact_rail_core_xz(moscow_profile)
        )
        label_id, semantic = _ancillary_semantics(label_policy, "rail")
        specs.append(
            ContinuousAssetSpec(
                persistent_key=(
                    f"{namespace}/infrastructure/contact-rail/0"
                ),
                name="PROD_CONTACT_RAIL",
                object_type="production_contact_rail",
                category="contact_rail",
                cross_section_xz=contact_section,
                label_id=label_id,
                semantic_class=semantic,
                properties={
                    "productionContinuous": True,
                    "domainGeometryStage": (
                        "10.5" if moscow_service_preset == "modern" else "10.3"
                    ),
                    "contactRailFamily": cr.rail_family,
                    "profileGeometryMode": cr.rail_profile_mode,
                    "profileConfidence": cr.rail_profile_confidence,
                    "profileEraWarning": cr.rail_profile_era_warning,
                    "eraMismatch": (
                        moscow_service_preset != "modern"
                    ),
                    "collection": cr.collection,
                    "sideProfileXSign": cr.side_profile_x_sign,
                    "contactRailAxisProfileXM": contact_axis_profile_x,
                    "contactRailAxisCoreXM": (
                        moscow_profile.coordinate.profile_x_to_core_x_sign
                        * contact_axis_profile_x
                    ),
                    "horizontalReference": (
                        "nearest_running_rail_inner_working_face"
                    ),
                    "horizontalOffsetFromInnerWorkingFaceM": (
                        cr.horizontal_from_inner_working_face_m
                    ),
                    "horizontalToleranceM": cr.horizontal_tolerance_m,
                    "workingSurfaceProfileZM": cr.working_surface_z_m,
                    "workingSurfaceCoreZM": (
                        cr.working_surface_z_m
                        + moscow_profile.coordinate.profile_z_to_core_z_offset_m
                    ),
                    "verticalToleranceM": cr.vertical_tolerance_m,
                    "overallHeightM": cr.rail_overall_height_m,
                    "topWidthM": cr.rail_top_width_m,
                    "baseWidthM": cr.rail_base_width_m,
                    "webWidthM": cr.rail_web_width_m,
                    "source": cr.rail_profile_source,
                    "moscowProfileID": moscow_profile.profile_id,
                    "moscowProfileSHA256": (
                        moscow_profile.provenance.canonical_sha256
                    ),
                },
            )
        )

        if moscow_service_preset == "legacy":
            cover_section = _ensure_ccw_xz(
                protective_cover_core_xz(moscow_profile)
            )
            specs.append(
                ContinuousAssetSpec(
                    persistent_key=(
                        f"{namespace}/infrastructure/contact-rail-cover/0"
                    ),
                    name="PROD_CONTACT_RAIL_COVER",
                    object_type="production_contact_rail_cover",
                    category="contact_rail_cover",
                    cross_section_xz=cover_section,
                    label_id=label_id,
                    semantic_class=semantic,
                    properties={
                        "productionContinuous": True,
                        "domainGeometryStage": "10.3",
                        "historicalCoverFamily": (
                            "legacy_wooden_board_protective_box"
                        ),
                        "geometryMode": cr.cover_mode,
                        "eraMismatch": cr.cover_era_mismatch,
                        "historicalSideGapM": cr.cover_historical_side_gap_m,
                        "historicalBoxGapM": cr.cover_box_gap_m,
                        "historicalBoxToInsulatorGapM": (
                            cr.cover_box_to_insulator_gap_m
                        ),
                        "historicalSupportOffsetFromBoxEndM": (
                            cr.cover_support_offset_from_box_end_m
                        ),
                        "outerTopWidthM": cr.cover_outer_top_width_m,
                        "outerBaseWidthM": cr.cover_outer_base_width_m,
                        "heightM": cr.cover_height_m,
                        "sideWallM": cr.cover_side_wall_m,
                        "topWallM": cr.cover_top_wall_m,
                        "lowerEdgeAboveContactSurfaceM": (
                            cr.cover_lower_edge_above_contact_surface_m
                        ),
                        "segmentationMode": (
                            "continuous_preview_historical_box_length_unresolved"
                        ),
                        "modernFallbackIsNotHistoricalClaim": True,
                        "moscowProfileID": moscow_profile.profile_id,
                        "moscowProfileSHA256": (
                            moscow_profile.provenance.canonical_sha256
                        ),
                    },
                )
            )
    

    if moscow_profile is None:
        base_z = -ancillary.inner_radius_m + ancillary.config.pavement_height_m
        for rail_index, center_x in enumerate(_rail_center_offsets(ancillary.config)):
            points = _ensure_ccw_xz(
                profile.points_xz(center_x_m=center_x, base_z_m=base_z)
            )
            bottom_edges = _edges_with_both_vertices_at_z(points, base_z)
            if len(bottom_edges) != 1:
                raise AssertionError(
                    "production rail must have one pavement-contact bottom edge"
                )
            key = f"{namespace}/infrastructure/rail/{rail_index}"
            label_id, semantic = _ancillary_semantics(label_policy, "rail")
            specs.append(
                ContinuousAssetSpec(
                    persistent_key=key,
                    name=f"PROD_RAIL_{rail_index}",
                    object_type="production_rail",
                    category="rail",
                    cross_section_xz=points,
                    label_id=label_id,
                    semantic_class=semantic,
                    omitted_longitudinal_edges=bottom_edges,
                    properties={
                        "railIndex": rail_index,
                        "railCenterX": center_x,
                        "railSpacingM": ancillary.config.rail_spacing_m,
                        "railProfile": "stage9_generic_lowpoly_16",
                        "railProfileVertices": len(points),
                        "railOverallHeightM": profile.overall_height_m,
                        "railHeadWidthM": profile.head_width_m,
                        "railHeadHeightM": profile.head_height_m,
                        "railWebThicknessM": profile.web_thickness_m,
                        "railFootWidthM": profile.foot_width_m,
                        "railFootHeightM": profile.foot_height_m,
                        "productionContinuous": True,
                    },
                )
            )
    else:
        r65 = R65ProductionProfile()
        gauge = moscow_profile.track.gauge_m
        gauge_level = moscow_profile.track.gauge_measurement_below_ugr_m
        centers_profile_x = r65_rail_center_offsets_for_gauge(
            gauge,
            profile=r65,
            measurement_below_top_m=gauge_level,
        )
        metrics = r65.validation_metrics()
        working_offset = r65.working_face_offset_m(
            measurement_below_top_m=gauge_level
        )
        top_profile_z = moscow_profile.datums.ugr_z_m
        base_profile_z = top_profile_z - r65.overall_height_m
        _, top_core_z = moscow_profile.coordinate.research_xz_to_core_xz(
            0.0,
            top_profile_z,
        )
        _, base_core_z = moscow_profile.coordinate.research_xz_to_core_xz(
            0.0,
            base_profile_z,
        )

        for rail_index, center_profile_x in enumerate(centers_profile_x):
            profile_points = r65.points_xz(
                center_x_m=center_profile_x,
                top_z_m=top_profile_z,
            )
            points = _ensure_ccw_xz(
                tuple(
                    moscow_profile.coordinate.research_xz_to_core_xz(x, z)
                    for x, z in profile_points
                )
            )
            center_core_x, _ = (
                moscow_profile.coordinate.research_xz_to_core_xz(
                    center_profile_x,
                    top_profile_z,
                )
            )
            working_face_profile_x = r65_inner_working_face_x(
                rail_index,
                center_profile_x,
                profile=r65,
                measurement_below_top_m=gauge_level,
            )
            working_face_core_x, working_face_core_z = (
                moscow_profile.coordinate.research_xz_to_core_xz(
                    working_face_profile_x,
                    top_profile_z - gauge_level,
                )
            )
            key = f"{namespace}/infrastructure/rail/{rail_index}"
            label_id, semantic = _ancillary_semantics(label_policy, "rail")
            # Stage 10.2 has discrete rail pads. Keep the continuous R65
            # underside visible between sleepers; the hidden coplanar contact
            # span is removed from each pad instead.
            rail_bottom_edges: tuple[int, ...] = ()
            specs.append(
                ContinuousAssetSpec(
                    persistent_key=key,
                    name=f"PROD_RAIL_{rail_index}",
                    object_type="production_rail",
                    category="rail",
                    cross_section_xz=points,
                    label_id=label_id,
                    semantic_class=semantic,
                    omitted_longitudinal_edges=rail_bottom_edges,
                    properties={
                        "railIndex": rail_index,
                        "railSide": (
                            "negative_profile_x_contact_rail_side"
                            if rail_index == 0
                            else "positive_profile_x_walkway_side"
                        ),
                        "railCenterProfileX": center_profile_x,
                        "railCenterX": center_core_x,
                        "railCenterSpacingM": (
                            centers_profile_x[1] - centers_profile_x[0]
                        ),
                        "railSpacingM": (
                            centers_profile_x[1] - centers_profile_x[0]
                        ),
                        "railProfile": "stage10_1_r65_gost_r51685_2022",
                        "railProfileVertices": len(points),
                        "railOverallHeightM": r65.overall_height_m,
                        "railHeadWidthM": r65.nominal_head_width_m,
                        "railNominalHeadWidthM": r65.nominal_head_width_m,
                        "railGeneratedHeadWidthM": metrics["head_width_m"],
                        "railWebThicknessM": r65.web_thickness_m,
                        "railFootWidthM": r65.base_width_m,
                        "railTopProfileZLocalM": top_profile_z,
                        "railBaseProfileZLocalM": base_profile_z,
                        "railTopCoreZLocalM": top_core_z,
                        "railBaseCoreZLocalM": base_core_z,
                        "railTopZLocalM": top_core_z,
                        "railBaseZLocalM": base_core_z,
                        "ugrProfileZLocalM": moscow_profile.datums.ugr_z_m,
                        "ugrCoreZLocalM": top_core_z,
                        "ugrZLocalM": top_core_z,
                        "gaugeM": gauge,
                        "gaugeMeasurementBelowUGRM": gauge_level,
                        "gaugeMeasurementProfileZLocalM": (
                            moscow_profile.datums.ugr_z_m - gauge_level
                        ),
                        "gaugeMeasurementCoreZLocalM": working_face_core_z,
                        "gaugeMeasurementZLocalM": working_face_core_z,
                        "railWorkingFaceOffsetM": working_offset,
                        "railInnerWorkingFaceProfileX": (
                            working_face_profile_x
                        ),
                        "railInnerWorkingFaceX": working_face_core_x,
                        "railInnerWorkingFaceZ": working_face_core_z,
                        "gaugePlacementRule": (
                            "inner_working_faces_at_ugr_minus_13mm"
                        ),
                        "r65AreaRelativeError": metrics["area_rel_error"],
                        "r65CentroidZErrorM": metrics["centroid_z_error_m"],
                        "moscowProfileID": moscow_profile.profile_id,
                        "moscowProfileSHA256": (
                            moscow_profile.provenance.canonical_sha256
                        ),
                        "railProfileSource": (
                            moscow_profile.track.rail_profile_source
                        ),
                        "productionContinuous": True,
                        "domainGeometryStage": moscow_stage,
                        "railFootBottomContactFaceOmitted": False,
                        "supportContactSurfacePolicy": (
                            "discrete_rail_pad_top_contact_span_omitted"
                            if moscow_stage in {"10.2", "10.3", "10.4", "10.5"}
                            else "stage10_1_closed_rail_profile"
                        ),
                    },
                )
            )

    return tuple(specs)


def scene_object_from_continuous_asset(
    spec: ContinuousAssetSpec,
    stations: Sequence[AlignmentStation],
    *,
    namespace: str,
    name_override: str | None = None,
    instance_id_override: int | None = None,
    ring_id_override: int | None = None,
    cap_start: bool = True,
    cap_end: bool = True,
    collection_prefix: tuple[str, ...] = (),
    extra_properties: Mapping[str, Any] | None = None,
    compact_exact_collinear_stations: bool = False,
) -> SceneObject:
    source_station_count = len(stations)
    base_sweep_stations = (
        compact_exact_collinear_alignment_stations(stations)
        if compact_exact_collinear_stations
        else tuple(stations)
    )
    sag_m = float(spec.properties.get("longitudinalSagM", 0.0))
    sag_variation = float(
        spec.properties.get("longitudinalSagVariationFraction", 0.0)
    )
    sag_peak_jitter = float(
        spec.properties.get(
            "longitudinalSagPeakPhaseJitterFraction",
            0.0,
        )
    )
    if spec.category == "cable" and sag_m > 0.0:
        sweep_stations = _periodic_cable_sag_alignment_stations(
            base_sweep_stations,
            support_pitch_m=float(spec.properties["supportPitchM"]),
            support_phase_m=float(spec.properties["supportPhaseM"]),
            midspan_sag_m=sag_m,
            variation_fraction=sag_variation,
            peak_phase_jitter_fraction=sag_peak_jitter,
            asset_key=spec.persistent_key,
        )
    else:
        sweep_stations = base_sweep_stations
    mesh = build_sweep_mesh(
        spec.cross_section_xz,
        sweep_stations,
        cap_start=cap_start,
        cap_end=cap_end,
        omit_edge_indices=spec.omitted_longitudinal_edges,
    )
    props = {
        **dict(spec.properties),
        "persistentKey": spec.persistent_key,
        "persistentInstanceID": spec.instance_id,
        "tunnelInstanceID": stable_instance_id(f"{namespace}/tunnel"),
        "infrastructureID": spec.instance_id,
        "identityScope": "continuous_infrastructure_asset",
        "sourceRingScope": "global",
        "productionCrossSectionVertices": mesh.cross_section_vertices,
        "productionStationCount": mesh.station_count,
        "sourceAlignmentStationCount": source_station_count,
        "sweepAlignmentStationCount": len(sweep_stations),
        "exactCollinearAlignmentStationsRemoved": (
            source_station_count - len(base_sweep_stations)
        ),
        "cableSagApplied": spec.category == "cable" and sag_m > 0.0,
        "cableSagMidspanM": sag_m if spec.category == "cable" else 0.0,
        "cableSagVariationFraction": (
            sag_variation if spec.category == "cable" else 0.0
        ),
        "cableSagPeakPhaseJitterFraction": (
            sag_peak_jitter if spec.category == "cable" else 0.0
        ),
        "cableSagDeterministicKey": (
            spec.persistent_key if spec.category == "cable" else ""
        ),
        "cableSagControlStationsAdded": (
            len(sweep_stations) - len(base_sweep_stations)
            if spec.category == "cable"
            else 0
        ),
        "alignmentCompactionMode": (
            "exact_zero_error_collinear"
            if compact_exact_collinear_stations
            else "disabled"
        ),
        "capStart": cap_start,
        "capEnd": cap_end,
        "omittedLongitudinalEdgeCount": len(spec.omitted_longitudinal_edges),
        "contactSurfacePolicy": (
            "hidden_coplanar_contact_faces_omitted"
            if spec.omitted_longitudinal_edges
            else "closed_longitudinal_perimeter"
        ),
        **dict(extra_properties or {}),
    }
    category_folder = {
        "rail": "Rails",
        "tube": "Tubes",
        "walkway": "Walkway",
        "pavement": "Pavement",
        "track_concrete": "TrackConcrete",
        "contact_rail": "ContactRail/Rail",
        "contact_rail_cover": "ContactRail/Cover",
    }.get(spec.category, spec.category.capitalize())
    return SceneObject(
        name=name_override or spec.name,
        vertices=mesh.vertices,
        faces=mesh.faces,
        object_type=spec.object_type,
        ring_id=0 if ring_id_override is None else ring_id_override,
        label_id=spec.label_id,
        instance_id=spec.instance_id if instance_id_override is None else instance_id_override,
        semantic_class=spec.semantic_class,
        reconstruction="stage9_continuous_alignment_sweep",
        collection_path=(
            *collection_prefix,
            "Tunnel",
            namespace,
            "Infrastructure",
            category_folder,
        ),
        extra_properties=props,
    )


# ---------------------------------------------------------------------------
# Ring-local production alignment
# ---------------------------------------------------------------------------


def stitch_ring_scene_object_to_alignment(
    obj: SceneObject,
    *,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
) -> SceneObject:
    """Warp a rigid Stage-7 ring-local object onto the continuous Stage-9 axis.

    The map is a piecewise-linear X/Z translation as a function of local Y. It
    preserves each ring's axial stagger rotation but makes the front/back centre
    offsets identical on both sides of every inter-ring boundary. Bolt cutters,
    heads and lining are transformed by the same map, so the Boolean relation is
    preserved.
    """
    ring_id = obj.ring_id
    if ring_id < 0 or ring_id >= assembly.config.n_rings:
        raise ValueError(f"{obj.name}: ring_id outside assembly")
    pose = assembly.poses[ring_id]
    L = assembly.config.ring_width_m
    center_chainage = (ring_id + 0.5) * L
    front_station = sample_alignment_station(stations, ring_id * L)
    center_station = sample_alignment_station(stations, center_chainage)
    back_station = sample_alignment_station(stations, (ring_id + 1) * L)
    center_x = float(pose.translation_m[0])
    center_z = float(pose.translation_m[2])

    vertices: list[Vec3] = []
    for x, y, z in obj.vertices:
        local_y = y - pose.chainage_m
        chainage = center_chainage + local_y
        station = sample_alignment_station(stations, chainage)
        vertices.append(
            (
                x + station.offset_x_m - center_x,
                y,
                z + station.offset_z_m - center_z,
            )
        )

    props = dict(obj.extra_properties)
    props.update(
        {
            "productionRingAlignmentStitched": True,
            "productionRingFrontOffsetX": float(front_station.offset_x_m),
            "productionRingFrontOffsetZ": float(front_station.offset_z_m),
            "productionRingCenterOffsetX": float(center_station.offset_x_m),
            "productionRingCenterOffsetZ": float(center_station.offset_z_m),
            "productionRingBackOffsetX": float(back_station.offset_x_m),
            "productionRingBackOffsetZ": float(back_station.offset_z_m),
            "productionRingAlignmentMap": "piecewise_linear_xz_by_local_y",
        }
    )
    return SceneObject(
        name=obj.name,
        vertices=tuple(vertices),
        faces=obj.faces,
        object_type=obj.object_type,
        ring_id=obj.ring_id,
        label_id=obj.label_id,
        instance_id=obj.instance_id,
        semantic_class=obj.semantic_class,
        segment_id=obj.segment_id,
        segment_name=obj.segment_name,
        segment_kind=obj.segment_kind,
        reconstruction=(
            f"{obj.reconstruction}+stage9_stitched_ring_alignment"
            if obj.reconstruction
            else "stage9_stitched_ring_alignment"
        ),
        collection_path=obj.collection_path,
        extra_properties=props,
    )


def _build_stage10_2_periodic_scene_objects(
    *,
    profile: MoscowStage10Profile,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    label_policy: LabelPolicy,
) -> tuple[SceneObject, ...]:
    r65 = R65ProductionProfile()
    rail_centers = r65_rail_center_offsets_for_gauge(
        profile.track.gauge_m,
        profile=r65,
        measurement_below_top_m=(
            profile.track.gauge_measurement_below_ugr_m
        ),
    )
    local_meshes = build_stage10_2_local_event_meshes(
        profile,
        rail_centers_profile_x=rail_centers,
    )
    pitch = profile.sleeper.pitch_m
    phase = 0.5 * pitch
    chainages = sleeper_chainages(
        assembly.length_by_chainage_m,
        pitch_m=pitch,
        phase_m=phase,
    )
    label_id, semantic = _ancillary_semantics(label_policy, "rail")
    result: list[SceneObject] = []
    L = assembly.config.ring_width_m

    folder_by_category = {
        "sleeper": "Sleepers",
        "under_baseplate_pad": "UnderBaseplatePads",
        "baseplate": "KD65Baseplates",
        "rail_pad": "RailPads",
        "track_screw": "TrackScrews",
        "clamp_hardware": "ClampHardware",
    }

    for event_index, chainage in enumerate(chainages):
        station = sample_alignment_station(stations, chainage)
        ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(chainage / L))),
        )
        for local in local_meshes:
            key = (
                f"{namespace}/permanent-way/sleeper-event/"
                f"{event_index:06d}/{local.category}"
            )
            iid = stable_instance_id(key)
            vertices = tuple(
                (
                    x + station.offset_x_m,
                    y + station.world_y_m,
                    z + station.offset_z_m,
                )
                for x, y, z in local.vertices
            )
            result.append(
                SceneObject(
                    name=(
                        f"PROD_PW_{event_index:06d}__"
                        f"{local.name_suffix}"
                    ),
                    vertices=vertices,
                    faces=local.faces,
                    object_type=local.object_type,
                    ring_id=ring_id,
                    label_id=label_id,
                    instance_id=iid,
                    semantic_class=semantic,
                    reconstruction="stage10_2_moscow_permanent_way",
                    collection_path=(
                        "Tunnel",
                        namespace,
                        "PermanentWay",
                        folder_by_category[local.category],
                    ),
                    extra_properties={
                        **dict(local.properties),
                        "persistentKey": key,
                        "persistentInstanceID": iid,
                        "tunnelInstanceID": stable_instance_id(
                            f"{namespace}/tunnel"
                        ),
                        "identityScope": "periodic_permanent_way_asset",
                        "domainGeometryStage": "10.2",
                        "periodicEventIndex": event_index,
                        "eventChainageM": chainage,
                        "sleeperPitchM": pitch,
                        "sleeperDensityPerKm": (
                            profile.sleeper.density_per_km
                        ),
                        "periodicPhaseM": phase,
                        "periodicPhaseRule": (
                            "half_pitch_from_tunnel_start"
                        ),
                        "alignmentOffsetX": station.offset_x_m,
                        "alignmentOffsetZ": station.offset_z_m,
                        "alignmentWorldY": station.world_y_m,
                        "moscowProfileID": profile.profile_id,
                        "moscowProfileSHA256": (
                            profile.provenance.canonical_sha256
                        ),
                    },
                )
            )
    return tuple(result)


def _periodic_mesh_prototype_properties(
    *,
    profile: MoscowStage10Profile,
    family: str,
    local_name: str,
    station: AlignmentStation,
    vertex_count: int,
    face_count: int,
) -> dict[str, Any]:
    """Describe a pure-translation periodic mesh for exact Blender instancing.

    SceneObject vertices remain fully materialized in world coordinates for
    backward compatibility. These properties let importers recover the shared
    local mesh exactly and place each logical instance with an object transform.
    """
    if not family or not local_name:
        raise ValueError("periodic mesh prototype family/name must not be empty")
    return {
        "meshPrototypeKey": (
            f"stage10.5/{profile.provenance.canonical_sha256}/"
            f"{family}/{local_name}"
        ),
        "meshPrototypeMode": "translation_only_shared_mesh_v1",
        "meshPrototypeTranslationM": (
            float(station.offset_x_m),
            float(station.world_y_m),
            float(station.offset_z_m),
        ),
        "meshPrototypeVertexCount": int(vertex_count),
        "meshPrototypeFaceCount": int(face_count),
        "meshPrototypeGeometryExact": True,
        "meshPrototypeLiDARSurfaceUnchanged": True,
    }


def _chainage_selected_for_window(
    chainage_m: float,
    *,
    total_length_m: float,
    start_chainage_m: float | None,
    end_chainage_m: float | None,
    tolerance_m: float = 1e-12,
) -> bool:
    """Use the same half-open event ownership rule as production chunks."""
    if start_chainage_m is None and end_chainage_m is None:
        return True
    start = 0.0 if start_chainage_m is None else float(start_chainage_m)
    end = float(total_length_m) if end_chainage_m is None else float(end_chainage_m)
    if not (0.0 <= start < end <= total_length_m + tolerance_m):
        raise ValueError("invalid production chainage window")
    if chainage_m < start - tolerance_m:
        return False
    if math.isclose(end, total_length_m, abs_tol=tolerance_m):
        return chainage_m <= end + tolerance_m
    return chainage_m < end - tolerance_m


def _build_stage10_5_modern_permanent_way_scene_objects(
    *,
    profile: MoscowStage10Profile,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    label_policy: LabelPolicy,
    start_chainage_m: float | None = None,
    end_chainage_m: float | None = None,
) -> tuple[SceneObject, ...]:
    r65 = R65ProductionProfile()
    rail_centers = r65_rail_center_offsets_for_gauge(
        profile.track.gauge_m,
        profile=r65,
        measurement_below_top_m=(
            profile.track.gauge_measurement_below_ugr_m
        ),
    )
    local_meshes = build_modern_lvt_local_event_meshes(
        profile,
        rail_centers_profile_x=rail_centers,
    )
    chainages = modern_lvt_chainages(
        assembly.length_by_chainage_m,
        profile,
    )
    label_id, semantic = _ancillary_semantics(label_policy, "rail")
    result: list[SceneObject] = []
    L = assembly.config.ring_width_m
    pw = profile.modern_permanent_way
    phase = 0.5 * pw.support_pitch_m
    folder_by_category = {
        "lvt_block": "LVTBlocks",
        "lvt_rubber_boot": "LVTRubberBoots",
        "apc4_rail_pad": "APC4RailPads",
        "apc4_fastening": "APC4Fastenings",
    }

    for event_index, chainage in enumerate(chainages):
        if not _chainage_selected_for_window(
            chainage,
            total_length_m=assembly.length_by_chainage_m,
            start_chainage_m=start_chainage_m,
            end_chainage_m=end_chainage_m,
        ):
            continue
        station = sample_alignment_station(stations, chainage)
        ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(chainage / L))),
        )
        for local in local_meshes:
            key = (
                f"{namespace}/permanent-way/lvt-event/"
                f"{event_index:06d}/{local.category}"
            )
            iid = stable_instance_id(key)
            vertices = tuple(
                (
                    x + station.offset_x_m,
                    y + station.world_y_m,
                    z + station.offset_z_m,
                )
                for x, y, z in local.vertices
            )
            result.append(
                SceneObject(
                    name=(
                        f"PROD_LVT_{event_index:06d}__"
                        f"{local.name_suffix}"
                    ),
                    vertices=vertices,
                    faces=local.faces,
                    object_type=local.object_type,
                    ring_id=ring_id,
                    label_id=label_id,
                    instance_id=iid,
                    semantic_class=semantic,
                    reconstruction="stage10_5_moscow_lvt_m_permanent_way",
                    collection_path=(
                        "Tunnel",
                        namespace,
                        "PermanentWay",
                        "Modern",
                        folder_by_category[local.category],
                    ),
                    extra_properties={
                        **dict(local.properties),
                        "persistentKey": key,
                        "persistentInstanceID": iid,
                        "tunnelInstanceID": stable_instance_id(
                            f"{namespace}/tunnel"
                        ),
                        "identityScope": "periodic_modern_permanent_way_asset",
                        "domainGeometryStage": "10.5",
                        "servicePreset": profile.default_service_preset,
                        "permanentWayPreset": pw.preset_id,
                        "periodicEventIndex": event_index,
                        "eventChainageM": chainage,
                        "runningSupportPitchM": pw.support_pitch_m,
                        "periodicPhaseM": phase,
                        "periodicPhaseRule": "half_pitch_from_tunnel_start",
                        "alignmentOffsetX": station.offset_x_m,
                        "alignmentOffsetZ": station.offset_z_m,
                        "alignmentWorldY": station.world_y_m,
                        **_periodic_mesh_prototype_properties(
                            profile=profile,
                            family="modern-permanent-way",
                            local_name=local.name_suffix,
                            station=station,
                            vertex_count=len(local.vertices),
                            face_count=len(local.faces),
                        ),
                        "moscowProfileID": profile.profile_id,
                        "moscowProfileSHA256": (
                            profile.provenance.canonical_sha256
                        ),
                    },
                )
            )
    return tuple(result)


def _build_stage10_3_contact_scene_objects(
    *,
    profile: MoscowStage10Profile,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    label_policy: LabelPolicy,
) -> tuple[SceneObject, ...]:
    local_meshes = build_stage10_3_local_support_meshes(profile)
    chainages = contact_support_chainages(
        assembly.length_by_chainage_m,
        profile,
    )
    label_id, semantic = _ancillary_semantics(label_policy, "rail")
    result: list[SceneObject] = []
    L = assembly.config.ring_width_m
    cr = profile.contact_rail
    folder_by_category = {
        "contact_rail_bracket": "Brackets",
        "contact_rail_insulator": "Insulators",
        "contact_rail_attachment_screws": "SleeperAttachmentScrews",
        "contact_rail_fastening_unit": "FasteningUnits",
    }

    for event_index, chainage in enumerate(chainages):
        station = sample_alignment_station(stations, chainage)
        ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(chainage / L))),
        )
        target_chainage = (
            cr.support_target_phase_m
            + event_index * cr.support_target_pitch_m
        )
        for local in local_meshes:
            key = (
                f"{namespace}/contact-rail/support-event/"
                f"{event_index:06d}/{local.category}"
            )
            iid = stable_instance_id(key)
            vertices = tuple(
                (
                    x + station.offset_x_m,
                    y + station.world_y_m,
                    z + station.offset_z_m,
                )
                for x, y, z in local.vertices
            )
            result.append(
                SceneObject(
                    name=(
                        f"PROD_CR_{event_index:06d}__"
                        f"{local.name_suffix}"
                    ),
                    vertices=vertices,
                    faces=local.faces,
                    object_type=local.object_type,
                    ring_id=ring_id,
                    label_id=label_id,
                    instance_id=iid,
                    semantic_class=semantic,
                    reconstruction="stage10_3_moscow_contact_rail_support",
                    collection_path=(
                        "Tunnel",
                        namespace,
                        "ContactRail",
                        folder_by_category[local.category],
                    ),
                    extra_properties={
                        **dict(local.properties),
                        "persistentKey": key,
                        "persistentInstanceID": iid,
                        "tunnelInstanceID": stable_instance_id(
                            f"{namespace}/tunnel"
                        ),
                        "identityScope": "periodic_contact_rail_asset",
                        "domainGeometryStage": "10.3",
                        "periodicEventIndex": event_index,
                        "eventChainageM": chainage,
                        "targetChainageM": target_chainage,
                        "targetPitchM": cr.support_target_pitch_m,
                        "targetPhaseM": cr.support_target_phase_m,
                        "snappedToNearestTimberSleeper": True,
                        "snapOffsetM": chainage - target_chainage,
                        "normativePitchMinM": cr.support_normative_min_m,
                        "normativePitchMaxM": cr.support_normative_max_m,
                        "alignmentOffsetX": station.offset_x_m,
                        "alignmentOffsetZ": station.offset_z_m,
                        "alignmentWorldY": station.world_y_m,
                        "moscowProfileID": profile.profile_id,
                        "moscowProfileSHA256": (
                            profile.provenance.canonical_sha256
                        ),
                    },
                )
            )
    return tuple(result)


def _build_stage10_5_modern_contact_scene_objects(
    *,
    profile: MoscowStage10Profile,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    label_policy: LabelPolicy,
    running_support_pitch_m: float,
    running_support_phase_m: float,
    start_chainage_m: float | None = None,
    end_chainage_m: float | None = None,
) -> tuple[SceneObject, ...]:
    local_meshes = build_modern_contact_support_meshes(profile)
    chainages = modern_contact_support_chainages(
        assembly.length_by_chainage_m,
        profile,
        running_support_pitch_m=running_support_pitch_m,
        running_support_phase_m=running_support_phase_m,
    )
    label_id, semantic = _ancillary_semantics(label_policy, "rail")
    result: list[SceneObject] = []
    L = assembly.config.ring_width_m
    modern = profile.modern_contact_rail
    folder_by_category = {
        "contact_rail_support_block": "SupportBlocks",
        "contact_rail_base_plate": "BasePlates",
        "contact_rail_bracket": "Brackets",
        "contact_rail_insulator": "Insulators",
        "contact_rail_fastening_unit": "FasteningUnits",
        "contact_rail_clamp_bolts": "ClampBolts",
        "contact_rail_attachment_dowels": "SupportDowels",
        "contact_rail_support_hood": "SupportHoods",
    }

    for event_index, chainage in enumerate(chainages):
        if not _chainage_selected_for_window(
            chainage,
            total_length_m=assembly.length_by_chainage_m,
            start_chainage_m=start_chainage_m,
            end_chainage_m=end_chainage_m,
        ):
            continue
        station = sample_alignment_station(stations, chainage)
        ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(chainage / L))),
        )
        target_chainage = (
            0.5 * modern.support_target_pitch_m
            + event_index * modern.support_target_pitch_m
        )
        nearest_running_index = round(
            (chainage - running_support_phase_m) / running_support_pitch_m
        )
        nearest_running = (
            running_support_phase_m
            + nearest_running_index * running_support_pitch_m
        )
        clearance = abs(chainage - nearest_running)
        for local in local_meshes:
            key = (
                f"{namespace}/contact-rail/modern-support-event/"
                f"{event_index:06d}/{local.category}"
            )
            iid = stable_instance_id(key)
            vertices = tuple(
                (
                    x + station.offset_x_m,
                    y + station.world_y_m,
                    z + station.offset_z_m,
                )
                for x, y, z in local.vertices
            )
            result.append(
                SceneObject(
                    name=(
                        f"PROD_CR_MODERN_{event_index:06d}__"
                        f"{local.name_suffix}"
                    ),
                    vertices=vertices,
                    faces=local.faces,
                    object_type=local.object_type,
                    ring_id=ring_id,
                    label_id=label_id,
                    instance_id=iid,
                    semantic_class=semantic,
                    reconstruction="stage10_5_modern_contact_rail_support",
                    collection_path=(
                        "Tunnel",
                        namespace,
                        "ContactRail",
                        "Modern",
                        folder_by_category[local.category],
                    ),
                    extra_properties={
                        **dict(local.properties),
                        "persistentKey": key,
                        "persistentInstanceID": iid,
                        "tunnelInstanceID": stable_instance_id(
                            f"{namespace}/tunnel"
                        ),
                        "identityScope": "periodic_modern_contact_rail_asset",
                        "domainGeometryStage": "10.5",
                        "servicePreset": modern.preset_id,
                        "periodicEventIndex": event_index,
                        "eventChainageM": chainage,
                        "targetChainageM": target_chainage,
                        "targetPitchM": modern.support_target_pitch_m,
                        "snapRule": "nearest_midpoint_between_running_supports",
                        "nearestRunningSupportChainageM": nearest_running,
                        "runningSupportClearanceM": clearance,
                        "runningSupportExclusionHalfLengthM": (
                            modern.running_support_exclusion_half_length_m
                        ),
                        "separateFromRunningRailSupport": True,
                        "alignmentOffsetX": station.offset_x_m,
                        "alignmentOffsetZ": station.offset_z_m,
                        "alignmentWorldY": station.world_y_m,
                        **_periodic_mesh_prototype_properties(
                            profile=profile,
                            family="modern-contact-support",
                            local_name=local.name_suffix,
                            station=station,
                            vertex_count=len(local.vertices),
                            face_count=len(local.faces),
                        ),
                        "moscowProfileID": profile.profile_id,
                        "moscowProfileSHA256": (
                            profile.provenance.canonical_sha256
                        ),
                    },
                )
            )

    cover_section = _ensure_ccw_xz(
        modern_protective_cover_core_xz(profile)
    )
    spans = modern_cover_span_ranges(
        assembly.length_by_chainage_m,
        profile,
        support_chainages=chainages,
    )
    for span_index, (start_chainage, end_chainage) in enumerate(spans):
        midpoint = 0.5 * (start_chainage + end_chainage)
        if not _chainage_selected_for_window(
            midpoint,
            total_length_m=assembly.length_by_chainage_m,
            start_chainage_m=start_chainage_m,
            end_chainage_m=end_chainage_m,
        ):
            continue
        clipped = clipped_alignment_stations(
            stations,
            start_chainage_m=start_chainage,
            end_chainage_m=end_chainage,
        )
        mesh = build_sweep_mesh(
            cover_section,
            clipped,
            cap_start=True,
            cap_end=True,
        )
        ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(midpoint / L))),
        )
        key = (
            f"{namespace}/contact-rail/modern-cover-span/"
            f"{span_index:06d}"
        )
        iid = stable_instance_id(key)
        result.append(
            SceneObject(
                name=f"PROD_CR_MODERN_COVER_SPAN_{span_index:06d}",
                vertices=mesh.vertices,
                faces=mesh.faces,
                object_type="production_contact_rail_cover_span",
                ring_id=ring_id,
                label_id=label_id,
                instance_id=iid,
                semantic_class=semantic,
                reconstruction="stage10_5_modern_contact_rail_cover_span",
                collection_path=(
                    "Tunnel",
                    namespace,
                    "ContactRail",
                    "Modern",
                    "CoverSpans",
                ),
                extra_properties={
                    "persistentKey": key,
                    "persistentInstanceID": iid,
                    "tunnelInstanceID": stable_instance_id(
                        f"{namespace}/tunnel"
                    ),
                    "identityScope": "modern_contact_cover_span",
                    "domainGeometryStage": "10.5",
                    "servicePreset": modern.preset_id,
                    "eventChainageM": midpoint,
                    "coverSpanIndex": span_index,
                    "coverSpanStartChainageM": start_chainage,
                    "coverSpanEndChainageM": end_chainage,
                    "geometryMode": "rounded_wrap_profile_from_exact_envelope",
                    "outerTopWidthM": modern.cover_top_width_m,
                    "outerBaseWidthM": modern.cover_base_width_m,
                    "heightM": modern.cover_height_m,
                    "sideWallM": modern.cover_side_wall_m,
                    "topWallM": modern.cover_top_wall_m,
                    "lowerEdgeAboveContactSurfaceM": (
                        modern.cover_lower_edge_above_contact_surface_m
                    ),
                    "supportZonesInterrupted": True,
                    "supportHoodSeparate": True,
                    "nominalSpanOverlapM": modern.cover_span_overlap_m,
                    "factoryCornerRadiiResolved": False,
                    "moscowProfileID": profile.profile_id,
                    "moscowProfileSHA256": (
                        profile.provenance.canonical_sha256
                    ),
                },
            )
        )
    return tuple(result)


def _build_stage10_5_service_rack_scene_objects(
    *,
    profile: MoscowStage10Profile,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    label_policy: LabelPolicy,
    start_chainage_m: float | None = None,
    end_chainage_m: float | None = None,
) -> tuple[SceneObject, ...]:
    local_by_side = {
        side: build_r2k11_local_rack_mesh(profile, side_sign=side)
        for side in (-1, 1)
    }
    chainages = cable_rack_chainages(
        assembly.length_by_chainage_m,
        profile,
    )
    label_id, semantic = _ancillary_semantics(label_policy, "tube")
    result: list[SceneObject] = []
    source_ring_width = assembly.config.ring_width_m
    rack = profile.cable_rack

    for event_index, chainage in enumerate(chainages):
        if not _chainage_selected_for_window(
            chainage,
            total_length_m=assembly.length_by_chainage_m,
            start_chainage_m=start_chainage_m,
            end_chainage_m=end_chainage_m,
        ):
            continue
        station = sample_alignment_station(stations, chainage)
        source_ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(chainage / source_ring_width))),
        )
        civil_ring_index = int(math.floor(chainage / profile.ring_pitch_m))
        for side_sign, local in local_by_side.items():
            side_name = "negative_x" if side_sign < 0 else "positive_x"
            key = (
                f"{namespace}/services/cable-rack/"
                f"{event_index:06d}/{side_name}"
            )
            iid = stable_instance_id(key)
            vertices = tuple(
                (
                    x + station.offset_x_m,
                    y + station.world_y_m,
                    z + station.offset_z_m,
                )
                for x, y, z in local.vertices
            )
            result.append(
                SceneObject(
                    name=(
                        f"PROD_SERVICE_R2K11_{event_index:06d}_"
                        f"{'NEG' if side_sign < 0 else 'POS'}"
                    ),
                    vertices=vertices,
                    faces=local.faces,
                    object_type=local.object_type,
                    ring_id=source_ring_id,
                    label_id=label_id,
                    instance_id=iid,
                    semantic_class=semantic,
                    reconstruction="stage10_5_r2k11_wall_cable_rack",
                    collection_path=(
                        "Tunnel",
                        namespace,
                        "Services",
                        "CableRacks",
                        side_name,
                    ),
                    extra_properties={
                        **dict(local.properties),
                        "persistentKey": key,
                        "persistentInstanceID": iid,
                        "tunnelInstanceID": stable_instance_id(
                            f"{namespace}/tunnel"
                        ),
                        "identityScope": "periodic_modern_service_asset",
                        "domainGeometryStage": "10.5",
                        "servicePreset": profile.default_service_preset,
                        "periodicEventIndex": event_index,
                        "eventChainageM": chainage,
                        "civilRingIndex": civil_ring_index,
                        "rackRepeatPitchM": rack.repeat_pitch_m,
                        "rackPhaseM": rack.phase_m,
                        "oneRackPerSidePerCivilRing": True,
                        "alignmentOffsetX": station.offset_x_m,
                        "alignmentOffsetZ": station.offset_z_m,
                        "alignmentWorldY": station.world_y_m,
                        **_periodic_mesh_prototype_properties(
                            profile=profile,
                            family="r2k11-cable-rack",
                            local_name=local.name_suffix,
                            station=station,
                            vertex_count=len(local.vertices),
                            face_count=len(local.faces),
                        ),
                        "moscowProfileID": profile.profile_id,
                        "moscowProfileSHA256": (
                            profile.provenance.canonical_sha256
                        ),
                    },
                )
            )
    return tuple(result)


def _build_stage10_5_water_main_support_scene_objects(
    *,
    profile: MoscowStage10Profile,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    label_policy: LabelPolicy,
    start_chainage_m: float | None = None,
    end_chainage_m: float | None = None,
) -> tuple[SceneObject, ...]:
    local = build_water_main_support_local_mesh(profile)
    chainages = water_main_support_chainages(
        assembly.length_by_chainage_m,
        profile,
    )
    label_id, semantic = _ancillary_semantics(label_policy, "tube")
    result: list[SceneObject] = []
    source_ring_width = assembly.config.ring_width_m

    for event_index, chainage in enumerate(chainages):
        if not _chainage_selected_for_window(
            chainage,
            total_length_m=assembly.length_by_chainage_m,
            start_chainage_m=start_chainage_m,
            end_chainage_m=end_chainage_m,
        ):
            continue
        station = sample_alignment_station(stations, chainage)
        source_ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(chainage / source_ring_width))),
        )
        key = f"{namespace}/services/water-main-support/{event_index:06d}"
        iid = stable_instance_id(key)
        vertices = tuple(
            (
                x + station.offset_x_m,
                y + station.world_y_m,
                z + station.offset_z_m,
            )
            for x, y, z in local.vertices
        )
        result.append(
            SceneObject(
                name=f"PROD_WATER_MAIN_SUPPORT_{event_index:06d}",
                vertices=vertices,
                faces=local.faces,
                object_type=local.object_type,
                ring_id=source_ring_id,
                label_id=label_id,
                instance_id=iid,
                semantic_class=semantic,
                reconstruction="stage10_5_water_main_wall_support",
                collection_path=(
                    "Tunnel",
                    namespace,
                    "Services",
                    "WaterMain",
                    "Supports",
                ),
                extra_properties={
                    **dict(local.properties),
                    "persistentKey": key,
                    "persistentInstanceID": iid,
                    "tunnelInstanceID": stable_instance_id(
                        f"{namespace}/tunnel"
                    ),
                    "identityScope": "periodic_modern_service_asset",
                    "domainGeometryStage": "10.5",
                    "servicePreset": profile.default_service_preset,
                    "periodicEventIndex": event_index,
                    "eventChainageM": chainage,
                    "alignmentOffsetX": station.offset_x_m,
                    "alignmentOffsetZ": station.offset_z_m,
                    "alignmentWorldY": station.world_y_m,
                    **_periodic_mesh_prototype_properties(
                        profile=profile,
                        family="water-main-support",
                        local_name=local.name_suffix,
                        station=station,
                        vertex_count=len(local.vertices),
                        face_count=len(local.faces),
                    ),
                    "moscowProfileID": profile.profile_id,
                    "moscowProfileSHA256": profile.provenance.canonical_sha256,
                },
            )
        )
    return tuple(result)


def _combine_geometry_parts(
    parts: Sequence[tuple[Sequence[Vec3], Sequence[Face]]],
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    vertices: list[Vec3] = []
    faces: list[Face] = []
    for part_vertices, part_faces in parts:
        base = len(vertices)
        vertices.extend(tuple(map(float, vertex)) for vertex in part_vertices)
        faces.extend(
            tuple(base + index for index in face)
            for face in part_faces
        )
    return tuple(vertices), tuple(faces)


def _civil_visual_segment_count(profile: MoscowStage10Profile) -> int:
    return (
        10
        if profile.civil_family
        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
        else 11
    )


def _civil_segment_boundary_angles(segment_count: int) -> tuple[float, ...]:
    if segment_count < 3:
        raise ValueError("civil visual segmentation requires >=3 pieces")
    # Keep a segment centred at crown instead of putting a joint on crown.
    return tuple(
        (2 * index + 1) * math.pi / segment_count
        for index in range(segment_count)
    )


def _build_civil_angular_rib_mesh(
    profile: MoscowStage10Profile,
    stations_xyz: Sequence[Vec3],
    *,
    segment_count: int,
    flange_arc_width_m: float,
    inward_relief_m: float,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    """Build open-backed longitudinal joint flanges on the intrados."""
    if len(stations_xyz) < 2:
        raise ValueError("civil angular ribs require at least two stations")
    rin = profile.intrados_radius_m
    if not (0.0 < inward_relief_m < rin):
        raise ValueError("invalid civil rib inward relief")
    half_angle = 0.5 * flange_arc_width_m / rin
    parts: list[tuple[tuple[Vec3, ...], tuple[Face, ...]]] = []
    for angle in _civil_segment_boundary_angles(segment_count):
        sections: list[tuple[Vec3, Vec3, Vec3, Vec3]] = []
        for ox, oy, oz in stations_xyz:
            a0 = angle - half_angle
            a1 = angle + half_angle
            ro = rin
            ri = rin - inward_relief_m
            sections.append(
                (
                    (ox + ro * math.sin(a0), oy, oz + ro * math.cos(a0)),
                    (ox + ro * math.sin(a1), oy, oz + ro * math.cos(a1)),
                    (ox + ri * math.sin(a1), oy, oz + ri * math.cos(a1)),
                    (ox + ri * math.sin(a0), oy, oz + ri * math.cos(a0)),
                )
            )
        vv = tuple(vertex for section in sections for vertex in section)
        ff: list[Face] = []
        for section_index in range(len(sections) - 1):
            a = 4 * section_index
            b = 4 * (section_index + 1)
            # Omit edge 0 (the face lying on the smooth intrados).
            for edge_index in (1, 2, 3):
                nxt = (edge_index + 1) % 4
                ff.append(
                    (
                        a + edge_index,
                        a + nxt,
                        b + nxt,
                        b + edge_index,
                    )
                )
        parts.append((vv, tuple(ff)))
    return _combine_geometry_parts(parts)


def _build_civil_circumferential_band_mesh(
    profile: MoscowStage10Profile,
    stations_xyz: Sequence[Vec3],
    *,
    inward_relief_m: float,
    angular_segments: int = 64,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    """Build one open-backed intrados flange/stiffener band."""
    if len(stations_xyz) < 2:
        raise ValueError("civil band requires at least two stations")
    if angular_segments < 24:
        raise ValueError("civil detail band needs >=24 angular segments")
    rin = profile.intrados_radius_m
    ri = rin - inward_relief_m
    n = angular_segments
    vertices: list[Vec3] = []
    for ox, oy, oz in stations_xyz:
        for radius in (rin, ri):
            for index in range(n):
                angle = 2.0 * math.pi * index / n
                vertices.append(
                    (
                        ox + radius * math.sin(angle),
                        oy,
                        oz + radius * math.cos(angle),
                    )
                )
    faces: list[Face] = []
    stride = 2 * n
    for station_index in range(len(stations_xyz) - 1):
        a = station_index * stride
        b = (station_index + 1) * stride
        # Only the inward-facing cylindrical surface is longitudinal.
        for index in range(n):
            nxt = (index + 1) % n
            faces.append(
                (
                    a + n + index,
                    b + n + index,
                    b + n + nxt,
                    a + n + nxt,
                )
            )
    # Exposed annular faces at both axial edges. The outer cylindrical face is
    # omitted because it lies directly on the base Stage-10 shell intrados.
    for base, reverse in (
        (0, True),
        ((len(stations_xyz) - 1) * stride, False),
    ):
        for index in range(n):
            nxt = (index + 1) % n
            face = (
                base + index,
                base + nxt,
                base + n + nxt,
                base + n + index,
            )
            faces.append(tuple(reversed(face)) if reverse else face)
    return tuple(vertices), tuple(faces)


def _build_civil_bolt_head_mesh(
    profile: MoscowStage10Profile,
    placements: Sequence[tuple[float, float, float, float]],
    *,
    seat_relief_m: float,
    head_radius_m: float = 0.023,
    head_protrusion_m: float = 0.014,
    sides: int = 6,
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    """Build low-poly visible bolt heads on the visual joint flanges."""
    if sides < 6:
        raise ValueError("civil bolt head requires at least six sides")
    rin = profile.intrados_radius_m
    parts: list[tuple[tuple[Vec3, ...], tuple[Face, ...]]] = []
    for ox, oy, oz, angle in placements:
        radial = (math.sin(angle), 0.0, math.cos(angle))
        tangent = (math.cos(angle), 0.0, -math.sin(angle))
        base_radius = rin - seat_relief_m
        top_radius = base_radius - head_protrusion_m
        vv: list[Vec3] = []
        for axis_radius in (base_radius, top_radius):
            cx = ox + axis_radius * radial[0]
            cy = oy
            cz = oz + axis_radius * radial[2]
            for index in range(sides):
                theta = 2.0 * math.pi * index / sides
                ct = math.cos(theta)
                sy = math.sin(theta)
                vv.append(
                    (
                        cx + head_radius_m * ct * tangent[0],
                        cy + head_radius_m * sy,
                        cz + head_radius_m * ct * tangent[2],
                    )
                )
        ff: list[Face] = []
        for index in range(sides):
            nxt = (index + 1) % sides
            ff.append((index, nxt, sides + nxt, sides + index))
        # The seating face is intentionally omitted where it touches the rib.
        ff.append(tuple(reversed(tuple(range(sides, 2 * sides)))))
        parts.append((tuple(vv), tuple(ff)))
    return _combine_geometry_parts(parts)


def _build_stage10_4_civil_detail_objects(
    *,
    profile: MoscowStage10Profile,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    label_policy: LabelPolicy,
    include_bolts: bool,
) -> tuple[SceneObject, ...]:
    """Restore Stage-9-like visible composition on the source-sized shell.

    The smooth Stage-10 physical envelope remains authoritative. This overlay
    restores visible joint/flange rhythm and bolt clutter without reverting to
    the wrong 6.7/6.0 m Stage-9 research ring dimensions.
    """
    total = assembly.length_by_chainage_m
    label_id, semantic = _civil_semantics(label_policy)
    source_ring_width = assembly.config.ring_width_m
    is_cast_iron = profile.civil_family == "CAST_IRON_5500_R1000"
    segment_count = _civil_visual_segment_count(profile)
    flange_width = 0.025 if is_cast_iron else 0.018
    longitudinal_relief = 0.035 if is_cast_iron else 0.012
    boundary_band_width = 0.025 if is_cast_iron else 0.018
    boundary_band_relief = 0.035 if is_cast_iron else 0.010
    center_band_width = 0.020
    center_band_relief = 0.025
    result: list[SceneObject] = []

    for ring_index, start_chainage, end_chainage in civil_ring_ranges(
        total,
        ring_pitch_m=profile.ring_pitch_m,
    ):
        midpoint = 0.5 * (start_chainage + end_chainage)
        representative_ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(midpoint / source_ring_width))),
        )
        clipped = clipped_alignment_stations(
            stations,
            start_chainage_m=start_chainage,
            end_chainage_m=end_chainage,
        )
        xyz = tuple(
            (station.offset_x_m, station.world_y_m, station.offset_z_m)
            for station in clipped
        )
        rib_parts: list[tuple[Sequence[Vec3], Sequence[Face]]] = []
        rib_parts.append(
            _build_civil_angular_rib_mesh(
                profile,
                xyz,
                segment_count=segment_count,
                flange_arc_width_m=flange_width,
                inward_relief_m=longitudinal_relief,
            )
        )

        start_band_end = min(
            end_chainage,
            start_chainage + boundary_band_width,
        )
        if start_band_end > start_chainage + 1e-9:
            band = clipped_alignment_stations(
                stations,
                start_chainage_m=start_chainage,
                end_chainage_m=start_band_end,
            )
            rib_parts.append(
                _build_civil_circumferential_band_mesh(
                    profile,
                    tuple(
                        (s.offset_x_m, s.world_y_m, s.offset_z_m)
                        for s in band
                    ),
                    inward_relief_m=boundary_band_relief,
                )
            )

        if is_cast_iron and end_chainage - start_chainage > center_band_width:
            half = 0.5 * center_band_width
            band = clipped_alignment_stations(
                stations,
                start_chainage_m=midpoint - half,
                end_chainage_m=midpoint + half,
            )
            rib_parts.append(
                _build_civil_circumferential_band_mesh(
                    profile,
                    tuple(
                        (s.offset_x_m, s.world_y_m, s.offset_z_m)
                        for s in band
                    ),
                    inward_relief_m=center_band_relief,
                )
            )

        rib_vertices, rib_faces = _combine_geometry_parts(rib_parts)
        rib_key = f"{namespace}/civil-detail/ribs/{ring_index:06d}"
        rib_iid = stable_instance_id(rib_key)
        result.append(
            SceneObject(
                name=f"PROD_MOSCOW_CIVIL_RIBS_{ring_index:06d}",
                vertices=rib_vertices,
                faces=rib_faces,
                object_type="production_moscow_civil_detail_ribs",
                ring_id=representative_ring_id,
                label_id=label_id,
                instance_id=rib_iid,
                semantic_class=semantic,
                reconstruction="stage10_4_moscow_civil_composite_visual_detail_v1",
                collection_path=(
                    "Tunnel", namespace, "CivilShell", "Details", "Ribs"
                ),
                extra_properties={
                    "persistentKey": rib_key,
                    "persistentInstanceID": rib_iid,
                    "tunnelInstanceID": stable_instance_id(
                        f"{namespace}/tunnel"
                    ),
                    "identityScope": "periodic_moscow_civil_detail",
                    "domainGeometryStage": "10.4",
                    "eventChainageM": midpoint,
                    "moscowCivilRingIndex": ring_index,
                    "civilFamily": profile.civil_family,
                    "visualSegmentCount": segment_count,
                    "visualSegmentCountIsLOD0": False,
                    "detailMode": (
                        "cast_iron_flange_and_stiffener_overlay"
                        if is_cast_iron
                        else "rc_block_joint_relief_overlay"
                    ),
                    "flangeWidthM": flange_width,
                    "longitudinalJointReliefM": longitudinal_relief,
                    "ringBoundaryBandWidthM": boundary_band_width,
                    "ringBoundaryBandReliefM": boundary_band_relief,
                    "circumferentialStiffenerIncluded": is_cast_iron,
                    "source": (
                        "P10-FROLOV-RING"
                        if is_cast_iron
                        else "S026"
                    ),
                    "accuracyBoundary": (
                        "source_backed_anatomy_and_principal_dimensions_"
                        "visual_rib_positions_not_series_CAD"
                    ),
                },
            )
        )

        if is_cast_iron and include_bolts:
            placements: list[tuple[float, float, float, float]] = []
            row_fractions = (0.28, 0.72)
            for angle in _civil_segment_boundary_angles(segment_count):
                for fraction in row_fractions:
                    chainage = start_chainage + fraction * (
                        end_chainage - start_chainage
                    )
                    station = sample_alignment_station(stations, chainage)
                    placements.append(
                        (
                            station.offset_x_m,
                            station.world_y_m,
                            station.offset_z_m,
                            angle,
                        )
                    )
            bolt_vertices, bolt_faces = _build_civil_bolt_head_mesh(
                profile,
                placements,
                seat_relief_m=longitudinal_relief,
            )
            bolt_key = f"{namespace}/civil-detail/bolts/{ring_index:06d}"
            bolt_iid = stable_instance_id(bolt_key)
            result.append(
                SceneObject(
                    name=f"PROD_MOSCOW_CIVIL_BOLTS_{ring_index:06d}",
                    vertices=bolt_vertices,
                    faces=bolt_faces,
                    object_type="production_moscow_civil_bolt_heads",
                    ring_id=representative_ring_id,
                    label_id=0,
                    instance_id=bolt_iid,
                    semantic_class="clutter",
                    reconstruction="stage10_4_cast_iron_M27_bolt_visual_v1",
                    collection_path=(
                        "Tunnel", namespace, "CivilShell", "Details", "Bolts"
                    ),
                    extra_properties={
                        "persistentKey": bolt_key,
                        "persistentInstanceID": bolt_iid,
                        "tunnelInstanceID": stable_instance_id(
                            f"{namespace}/tunnel"
                        ),
                        "identityScope": "periodic_moscow_civil_detail",
                        "domainGeometryStage": "10.5",
                        "eventChainageM": midpoint,
                        "moscowCivilRingIndex": ring_index,
                        "civilFamily": profile.civil_family,
                        "boltHeadCount": len(placements),
                        "boltRowsPerLongitudinalJoint": 2,
                        "nominalBoltDiameterM": 0.027,
                        "nominalBoltLengthM": 0.120,
                        "visualHeadRadiusM": 0.023,
                        "visualHeadProtrusionM": 0.014,
                        "exactBoltHeadCADResolved": False,
                        "source": "P10-FROLOV-RING",
                    },
                )
            )
    return tuple(result)


def _stage9_child_seed(master_seed: int, ring_id: int, stream: int) -> int:
    """Reproduce the old Stage-9 per-ring RNG stream split exactly."""
    state = np.random.SeedSequence(
        [int(master_seed), int(ring_id), int(stream)]
    ).generate_state(1)
    return int(state[0])


def _sample_moscow_civil_roll_assembly(
    *,
    source_assembly: TunnelAssembly,
    profile: MoscowStage10Profile,
    civil_ring_count: int,
    master_seed: int,
) -> TunnelAssembly:
    """Reproduce Stage-7/9 ring roll on the independent Moscow civil rhythm.

    Stage 10 infrastructure follows the gravity/alignment frame, while the
    lining itself retains the old per-ring axial stagger.  Moscow civil rings
    use a 1.0 m pitch, so they need their own pose stream rather than indexing
    the source 1.35 m Stage-9 assembly poses.
    """
    if civil_ring_count <= 0:
        raise ValueError("Moscow civil roll stream requires at least one ring")
    src = source_assembly.config
    cfg = TunnelAssemblyConfig(
        n_rings=civil_ring_count,
        ring_width_m=profile.ring_pitch_m,
        displacement_amplitude_m=0.0,
        lateral_wavelength_m=src.lateral_wavelength_m,
        vertical_wavelength_m=src.vertical_wavelength_m,
        omega_x_rad_per_ring=src.omega_x_rad_per_ring,
        omega_z_rad_per_ring=src.omega_z_rad_per_ring,
        axis_noise_sigma_m=0.0,
        ring_rotation_strategy=src.ring_rotation_strategy,
        nominal_stagger_deg=src.nominal_stagger_deg,
        theta_k_deg=src.theta_k_deg,
        stagger_sigma_fraction_of_bound=src.stagger_sigma_fraction_of_bound,
        angular_imperfection_fraction=src.angular_imperfection_fraction,
        recenter_lateral_offsets=False,
    )
    # Stage 7/9 sampled the complete assembly from the master stream 10000.
    # Reusing that stream on the civil-ring count preserves the historical
    # rotation algorithm while decoupling it from the source-ring pitch.
    return sample_tunnel_assembly(
        cfg,
        seed=_stage9_child_seed(master_seed, 0, 10_000),
    )


def _moscow_rc_legacy_ring_mesh(
    profile: MoscowStage10Profile,
    *,
    topology: str,
    ring_index: int,
    width_m: float,
    seed: int,
) -> RingMesh:
    cfg = RingConfig(
        outer_radius_m=profile.extrados_radius_m,
        thickness_m=(
            profile.extrados_radius_m - profile.intrados_radius_m
        ),
        width_m=width_m,
    )
    sampled_angles = sample_six_segment_angles(
        seed=_stage9_child_seed(seed, ring_index, 1)
    )
    if topology == "kba":
        return build_ring_mesh(cfg, sampled_angles)
    if topology != "ten_equal":
        raise ValueError(f"unsupported Moscow RC topology {topology!r}")

    # The old RingMesh container carries RingAngles because Stage 1 was a
    # six-segment reconstruction. For ten-equal Moscow RC the angle object is
    # intentionally unused by curved-mesh, joint and TYPE1 bolt construction;
    # the actual geometry is defined by these ten analytical extents.
    step = 360.0 / 10.0
    extents = tuple(
        SegmentAngularExtent(
            name=f"RC{i + 1:02d}",
            kind="RC",
            front_start_deg=-0.5 * step + i * step,
            front_end_deg=-0.5 * step + (i + 1) * step,
            back_start_deg=-0.5 * step + i * step,
            back_end_deg=-0.5 * step + (i + 1) * step,
        )
        for i in range(10)
    )
    segments = tuple(build_hexahedral_segment(cfg, extent) for extent in extents)
    return RingMesh(
        config=cfg,
        angles=sampled_angles,
        segments=segments,
    )


@dataclass
class _CivilRingWarpContext:
    ring_index: int
    start_chainage_m: float
    end_chainage_m: float
    midpoint_m: float
    representative_ring_id: int
    civil_pose: RingPose
    civil_rotation_seed: int | None
    civil_ring_count: int
    rotation_cos: float
    rotation_sin: float
    front_station: AlignmentStation
    center_station: AlignmentStation
    back_station: AlignmentStation
    tunnel_instance_id: int
    station_cache: dict[float, AlignmentStation]


def _build_civil_ring_warp_context(
    *,
    ring_index: int,
    start_chainage_m: float,
    end_chainage_m: float,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    civil_pose: RingPose,
    civil_rotation_seed: int | None,
    civil_ring_count: int,
    tunnel_instance_id: int,
) -> _CivilRingWarpContext:
    if civil_ring_count <= 0 or not (0 <= ring_index < civil_ring_count):
        raise ValueError("invalid Moscow civil ring index/count")

    midpoint = 0.5 * (start_chainage_m + end_chainage_m)
    source_ring_width = assembly.config.ring_width_m
    representative_ring_id = min(
        assembly.config.n_rings - 1,
        max(0, int(math.floor(midpoint / source_ring_width))),
    )
    rotation_rad = math.radians(civil_pose.rotation_y_deg)
    front_station = sample_alignment_station(stations, start_chainage_m)
    center_station = sample_alignment_station(stations, midpoint)
    back_station = sample_alignment_station(stations, end_chainage_m)
    return _CivilRingWarpContext(
        ring_index=ring_index,
        start_chainage_m=start_chainage_m,
        end_chainage_m=end_chainage_m,
        midpoint_m=midpoint,
        representative_ring_id=representative_ring_id,
        civil_pose=civil_pose,
        civil_rotation_seed=civil_rotation_seed,
        civil_ring_count=civil_ring_count,
        rotation_cos=math.cos(rotation_rad),
        rotation_sin=math.sin(rotation_rad),
        front_station=front_station,
        center_station=center_station,
        back_station=back_station,
        tunnel_instance_id=tunnel_instance_id,
        station_cache={
            float(start_chainage_m): front_station,
            float(midpoint): center_station,
            float(end_chainage_m): back_station,
        },
    )


def _warp_civil_local_object_to_alignment(
    obj: SceneObject,
    *,
    context: _CivilRingWarpContext,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    namespace: str,
    profile: MoscowStage10Profile,
    topology: str,
) -> SceneObject:
    ring_index = context.ring_index
    start_chainage_m = context.start_chainage_m
    end_chainage_m = context.end_chainage_m
    midpoint = context.midpoint_m
    representative_ring_id = context.representative_ring_id
    civil_pose = context.civil_pose
    civil_rotation_seed = context.civil_rotation_seed
    civil_ring_count = context.civil_ring_count
    rotation_cos = context.rotation_cos
    rotation_sin = context.rotation_sin

    local_ys = tuple(float(v[1]) for v in obj.vertices)
    object_min_chainage = midpoint + min(local_ys)
    object_max_chainage = midpoint + max(local_ys)
    alignment_start = stations[0].chainage_m
    alignment_end = stations[-1].chainage_m
    start_overhang_m = max(0.0, alignment_start - object_min_chainage)
    end_overhang_m = max(0.0, object_max_chainage - alignment_end)
    is_boundary_fastener = obj.object_type in {
        "bolt_pocket_cutter",
        "bolt_head",
    }
    allow_start_extrapolation = (
        is_boundary_fastener
        and ring_index == 0
        and start_overhang_m > 0.0
    )
    allow_end_extrapolation = (
        is_boundary_fastener
        and ring_index == civil_ring_count - 1
        and end_overhang_m > 0.0
    )

    # The copied Stage-9 hardware is small relative to a 1 m civil ring.
    # A larger excursion would indicate malformed geometry, not a crop-edge
    # fastener overhang, so keep a hard safety guard.
    max_boundary_fastener_overhang_m = 0.25 * profile.ring_pitch_m
    if (
        start_overhang_m > max_boundary_fastener_overhang_m
        or end_overhang_m > max_boundary_fastener_overhang_m
    ):
        raise ValueError(
            f"{obj.name}: transferred fastener/civil object overhang exceeds "
            f"{max_boundary_fastener_overhang_m:g} m safety bound"
        )

    extrapolated_vertex_count = 0
    extrapolated_max_overhang_m = 0.0
    extrapolated_sides: set[str] = set()

    # One strict alignment cache is shared by every object in the civil ring.
    # Terminal extrapolation remains object-specific because its admissible
    # overhang depends on the individual fastener mesh.
    vertices: list[Vec3] = []
    for x, local_y, z in obj.vertices:
        # Literal Stage-7/9 axial ring rotation is applied to the complete
        # lining object in its local XZ frame before Stage-10 alignment warp.
        xr = rotation_cos * x + rotation_sin * z
        zr = -rotation_sin * x + rotation_cos * z
        chainage = midpoint + local_y
        extrapolated_side: str | None = None
        overrun = 0.0
        station = context.station_cache.get(float(chainage))
        if station is None:
            try:
                station = sample_alignment_station(stations, chainage)
                context.station_cache[float(chainage)] = station
            except ValueError as exc:
                before_start = chainage < alignment_start
                after_end = chainage > alignment_end
                if before_start and allow_start_extrapolation:
                    max_extra = start_overhang_m
                    extrapolated_side = "start"
                    overrun = alignment_start - chainage
                elif after_end and allow_end_extrapolation:
                    max_extra = end_overhang_m
                    extrapolated_side = "end"
                    overrun = chainage - alignment_end
                else:
                    raise ValueError(
                        f"{obj.name}: Moscow civil warp chainage "
                        f"{chainage:.17g} m outside alignment while mapping ring "
                        f"{ring_index} [{start_chainage_m:.17g}, "
                        f"{end_chainage_m:.17g}] m, local_y={local_y:.17g} m, "
                        f"object_type={obj.object_type}"
                    ) from exc
                try:
                    station = _sample_alignment_station_with_terminal_extrapolation(
                        stations,
                        chainage,
                        max_extrapolation_m=max_extra,
                    )
                except ValueError as extrapolation_exc:
                    raise ValueError(
                        f"{obj.name}: failed bounded terminal fastener alignment "
                        f"extrapolation at chainage {chainage:.17g} m"
                    ) from extrapolation_exc

        if extrapolated_side is not None:
            extrapolated_vertex_count += 1
            extrapolated_max_overhang_m = max(
                extrapolated_max_overhang_m,
                overrun,
            )
            extrapolated_sides.add(extrapolated_side)
        vertices.append(
            (
                xr + station.offset_x_m,
                station.world_y_m,
                zr + station.offset_z_m,
            )
        )

    # Preserve the legacy Stage-9 object types literally so the Blender
    # adapter applies the same lining-interface cleanup and bolt Boolean plan.
    object_type = obj.object_type
    key = (
        f"{namespace}/civil-stage9-transfer/{topology}/"
        f"ring/{ring_index:06d}/{obj.name}"
    )
    iid = stable_instance_id(key)
    front_station = context.front_station
    center_station = context.center_station
    back_station = context.back_station
    props = dict(obj.extra_properties)
    props.update(
        {
            "persistentKey": key,
            "persistentInstanceID": iid,
            "tunnelInstanceID": context.tunnel_instance_id,
            "identityScope": "moscow_civil_stage9_architecture_transfer",
            "domainGeometryStage": "10.4",
            "moscowCivilRingIndex": ring_index,
            "moscowCivilRingStartChainageM": start_chainage_m,
            "moscowCivilRingEndChainageM": end_chainage_m,
            "eventChainageM": midpoint,
            "liningRingIndex": ring_index,
            "liningRingWidthM": end_chainage_m - start_chainage_m,
            "liningRingCenterWorldYM": center_station.world_y_m,
            "liningRingFrontWorldYM": front_station.world_y_m,
            "liningRingBackWorldYM": back_station.world_y_m,
            "ringTranslationX": center_station.offset_x_m,
            "ringTranslationY": center_station.world_y_m,
            "ringTranslationZ": center_station.offset_z_m,
            "ringRotationDeg": float(civil_pose.rotation_y_deg),
            "objectAppliedAxialRotationDeg": float(civil_pose.rotation_y_deg),
            "ringNominalRotationDeg": float(civil_pose.nominal_rotation_deg),
            "ringAngularImperfectionDeg": float(
                civil_pose.angular_imperfection_deg
            ),
            "moscowCivilRotationStrategy": (
                assembly.config.ring_rotation_strategy.value
            ),
            "moscowCivilRotationSeed": civil_rotation_seed,
            "moscowCivilRotationFrame": (
                "local_cross_section_before_stage10_alignment"
            ),
            "moscowCivilIndependentRingPoseStream": True,
            "stage7RingAxialStaggerTransferred": True,
            "productionRingAlignmentStitched": True,
            "moscowCivilBoundaryFastenerAlignmentExtrapolated": (
                extrapolated_vertex_count > 0
            ),
            "moscowCivilBoundaryFastenerExtrapolatedVertexCount": (
                extrapolated_vertex_count
            ),
            "moscowCivilBoundaryFastenerMaxOverhangM": (
                extrapolated_max_overhang_m
            ),
            "moscowCivilBoundaryFastenerExtrapolatedSides": tuple(
                sorted(extrapolated_sides)
            ),
            "moscowCivilBoundaryFastenerExtrapolationMode": (
                "terminal_linear_alignment_extension_preserve_stage9_mesh"
                if extrapolated_vertex_count > 0
                else "none"
            ),
            "productionRingFrontOffsetX": front_station.offset_x_m,
            "productionRingFrontOffsetZ": front_station.offset_z_m,
            "productionRingCenterOffsetX": center_station.offset_x_m,
            "productionRingCenterOffsetZ": center_station.offset_z_m,
            "productionRingBackOffsetX": back_station.offset_x_m,
            "productionRingBackOffsetZ": back_station.offset_z_m,
            "chunkAssignmentDatum": "moscow_ring_midpoint_chainage",
            "civilFamily": profile.civil_family,
            "moscowCivilTopology": topology,
            "stage9SegmentJointFastenerArchitectureTransferred": True,
            "stage9FastenerVisualTransferNotHistoricalMoscowClaim": True,
            "liningGlobalRingCount": civil_ring_count,
            "moscowProfileID": profile.profile_id,
            "moscowProfileSHA256": profile.provenance.canonical_sha256,
        }
    )
    if obj.object_type in {"bolt_pocket_cutter", "bolt_head"}:
        local_bolt_index = int(props.get("boltIndex", 0))
        props["stage9LocalBoltIndex"] = local_bolt_index
        props["boltIndex"] = ring_index * 1000 + local_bolt_index
        props["legacyBoltLayout"] = BoltLayoutType.TYPE1_CENTERED.value
        props["legacyBoltBooleanOverlapM"] = 0.005
    if obj.object_type.startswith("prescribed_"):
        props["legacyPrescribedJointGeometry"] = True

    return SceneObject(
        name=obj.name,
        vertices=tuple(vertices),
        faces=obj.faces,
        object_type=object_type,
        ring_id=representative_ring_id,
        label_id=obj.label_id,
        instance_id=iid,
        semantic_class=obj.semantic_class,
        segment_id=obj.segment_id,
        segment_name=obj.segment_name,
        segment_kind=obj.segment_kind,
        reconstruction=(
            f"{obj.reconstruction}+moscow_stage9_architecture_transfer"
            if obj.reconstruction
            else "moscow_stage9_architecture_transfer"
        ),
        collection_path=(
            "Tunnel",
            namespace,
            "CivilShell",
            "Stage9ArchitectureTransfer",
            topology,
            f"Ring_{ring_index:06d}",
            *obj.collection_path[1:],
        )
        if obj.collection_path
        else (
            "Tunnel",
            namespace,
            "CivilShell",
            "Stage9ArchitectureTransfer",
            topology,
            f"Ring_{ring_index:06d}",
        ),
        extra_properties=props,
    )


def _build_stage10_4_rc_stage9_architecture_objects(
    *,
    profile: MoscowStage10Profile,
    topology: str,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    surface_meshing: SurfaceMeshingConfig,
    include_bolts: bool,
    include_prescribed_outer_joint_solids: bool = False,
    seed: int,
    start_chainage_m: float | None = None,
    end_chainage_m: float | None = None,
    civil_roll_assembly: TunnelAssembly | None = None,
) -> tuple[SceneObject, ...]:
    """Parameterize the old Stage-9 segment/joint/bolt pipeline for Moscow RC."""
    if profile.civil_family != "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000":
        raise ValueError("Stage-9 civil transfer currently targets Moscow RC only")
    if topology not in {"ten_equal", "kba"}:
        raise ValueError("Moscow RC topology must be ten_equal or kba")

    ranges = civil_ring_ranges(
        assembly.length_by_chainage_m,
        ring_pitch_m=profile.ring_pitch_m,
    )
    civil_ring_count = len(ranges)
    if civil_roll_assembly is None:
        civil_roll_assembly = _sample_moscow_civil_roll_assembly(
            source_assembly=assembly,
            profile=profile,
            civil_ring_count=civil_ring_count,
            master_seed=seed,
        )
    elif civil_roll_assembly.config.n_rings != civil_ring_count:
        raise ValueError("civil_roll_assembly ring count mismatch")
    result: list[SceneObject] = []
    tunnel_instance_id = stable_instance_id(f"{namespace}/tunnel")
    for range_index, (
        ring_index,
        start_chainage,
        end_chainage,
    ) in enumerate(ranges):
        midpoint = 0.5 * (start_chainage + end_chainage)
        if not _chainage_selected_for_window(
            midpoint,
            total_length_m=assembly.length_by_chainage_m,
            start_chainage_m=start_chainage_m,
            end_chainage_m=end_chainage_m,
        ):
            continue
        width = end_chainage - start_chainage
        ring = _moscow_rc_legacy_ring_mesh(
            profile,
            topology=topology,
            ring_index=ring_index,
            width_m=width,
            seed=seed,
        )
        joints = build_prescribed_joint_set(
            ring,
            sample_joint_config(
                seed=_stage9_child_seed(seed, ring_index, 2)
            ),
        )

        # Stage 9 uses TYPE1_CENTERED by default: three pockets/heads per
        # segment at y=-0.4, 0, +0.4 m. The complete pocket/head geometry,
        # not only its centre, assumes a full nominal ring. Therefore a clipped
        # final civil ring gets no transferred fasteners rather than moving or
        # rescaling the old Stage-9 hardware.
        bolts = None
        full_longitudinal_bolt_layout_fits = (
            width >= profile.ring_pitch_m - 1e-9
        )
        if include_bolts and full_longitudinal_bolt_layout_fits:
            bolt_cfg = sample_bolt_config(
                seed=_stage9_child_seed(seed, ring_index, 3)
            )
            bolts = build_bolt_set(
                ring,
                bolt_cfg,
                BoltLayoutType.TYPE1_CENTERED,
                seed=_stage9_child_seed(seed, ring_index, 4),
                perturbation_config=BoltPerturbationConfig(),
            )

        warp_context = _build_civil_ring_warp_context(
            ring_index=ring_index,
            start_chainage_m=start_chainage,
            end_chainage_m=end_chainage,
            assembly=assembly,
            stations=stations,
            civil_pose=civil_roll_assembly.poses[ring_index],
            civil_rotation_seed=civil_roll_assembly.seed,
            civil_ring_count=civil_ring_count,
            tunnel_instance_id=tunnel_instance_id,
        )

        package = build_nominal_scene_package(
            ring,
            joints,
            ring_id=ring_index,
            include_radial_joints=include_prescribed_outer_joint_solids,
            include_circumferential_front=False,
            include_circumferential_back=(
                include_prescribed_outer_joint_solids
                and range_index < civil_ring_count - 1
            ),
            label_policy=LabelPolicy.STSD_COARSE,
            surface_meshing=surface_meshing,
            bolts=bolts,
            bolt_boolean_overlap_m=0.005,
        )
        for obj in package.objects:
            mapped = _warp_civil_local_object_to_alignment(
                obj,
                context=warp_context,
                assembly=assembly,
                stations=stations,
                namespace=namespace,
                profile=profile,
                topology=topology,
            )
            if (
                obj.object_type in {"bolt_pocket_cutter", "bolt_head"}
                and not full_longitudinal_bolt_layout_fits
            ):
                raise AssertionError("partial-ring bolt object unexpectedly built")
            result.append(mapped)
    return tuple(result)


def _build_stage10_4_civil_shell_objects(
    *,
    profile: MoscowStage10Profile,
    namespace: str,
    assembly: TunnelAssembly,
    stations: Sequence[AlignmentStation],
    label_policy: LabelPolicy,
) -> tuple[SceneObject, ...]:
    total = assembly.length_by_chainage_m
    label_id, semantic = _civil_semantics(label_policy)
    result: list[SceneObject] = []
    source_ring_width = assembly.config.ring_width_m
    ranges = civil_ring_ranges(
        total,
        ring_pitch_m=profile.ring_pitch_m,
    )
    for ring_index, start_chainage, end_chainage in ranges:
        clipped = clipped_alignment_stations(
            stations,
            start_chainage_m=start_chainage,
            end_chainage_m=end_chainage,
        )
        station_xyz = tuple(
            (
                station.offset_x_m,
                station.world_y_m,
                station.offset_z_m,
            )
            for station in clipped
        )
        cap_start = math.isclose(start_chainage, 0.0, abs_tol=1e-12)
        cap_end = math.isclose(end_chainage, total, abs_tol=1e-12)

        mesh = build_annular_shell_sweep(
            profile,
            station_xyz,
            angular_segments=96,
            cap_start=cap_start,
            cap_end=cap_end,
        )
        reconstruction = (
            "stage10_4_moscow_cast_iron_smooth_envelope_detail_deferred"
        )
        coarse_count_is_geometry = False
        civil_render_mode = (
            "source_sized_smooth_cast_iron_envelope_detail_deferred"
        )

        midpoint = 0.5 * (start_chainage + end_chainage)
        representative_ring_id = min(
            assembly.config.n_rings - 1,
            max(0, int(math.floor(midpoint / source_ring_width))),
        )
        key = f"{namespace}/civil-shell/ring/{ring_index:06d}"
        iid = stable_instance_id(key)
        result.append(
            SceneObject(
                name=f"PROD_MOSCOW_CIVIL_RING_{ring_index:06d}",
                vertices=mesh.vertices,
                faces=mesh.faces,
                object_type="production_moscow_civil_shell_ring",
                ring_id=representative_ring_id,
                label_id=label_id,
                instance_id=iid,
                semantic_class=semantic,
                reconstruction=reconstruction,
                collection_path=(
                    "Tunnel",
                    namespace,
                    "CivilShell",
                    "Rings",
                ),
                extra_properties={
                    "persistentKey": key,
                    "persistentInstanceID": iid,
                    "tunnelInstanceID": stable_instance_id(
                        f"{namespace}/tunnel"
                    ),
                    "identityScope": "periodic_moscow_civil_ring",
                    "domainGeometryStage": "10.4",
                    "eventChainageM": midpoint,
                    "chunkAssignmentDatum": "moscow_ring_midpoint_chainage",
                    "moscowCivilRingIndex": ring_index,
                    "moscowCivilRingStartChainageM": start_chainage,
                    "moscowCivilRingEndChainageM": end_chainage,
                    "moscowCivilRingPitchM": profile.ring_pitch_m,
                    "partialFinalRing": (
                        end_chainage - start_chainage
                        < profile.ring_pitch_m - 1e-12
                    ),
                    "civilFamily": profile.civil_family,
                    "civilGeometryMode": profile.civil_geometry_mode,
                    "civilRenderMode": civil_render_mode,
                    "circumferentialSegmentSurfaceMode": (
                        profile.civil_segment_surface_mode
                    ),
                    "coarseSegmentCountReference": 11,
                    "coarseSegmentCountIsGeometry": coarse_count_is_geometry,
                    "seriesAccurateTubingLOD0": False,
                    "seriesAccurateCivilLOD0": False,
                    "stage9LikeCurvedSegmentConstruction": False,
                    "renderedRCBlockCount": 0,
                    "intradosRadiusM": profile.intrados_radius_m,
                    "intradosDiameterM": 2.0 * profile.intrados_radius_m,
                    "extradosRadiusM": profile.extrados_radius_m,
                    "extradosDiameterM": 2.0 * profile.extrados_radius_m,
                    "structuralDepthM": (
                        profile.extrados_radius_m
                        - profile.intrados_radius_m
                    ),
                    "liningAxisProfileZM": profile.datums.lining_axis_z_m,
                    "liningAxisCoreZM": 0.0,
                    "angularSegments": mesh.angular_segments,
                    "internalRingEndCaps": False,
                    "moscowProfileID": profile.profile_id,
                    "moscowProfileSHA256": (
                        profile.provenance.canonical_sha256
                    ),
                },
            )
        )
    return tuple(result)


# ---------------------------------------------------------------------------
# Production scene
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ProductionConfig:
    namespace: str = "default"
    rail_profile: RailProfile | None = None
    moscow_profile: MoscowStage10Profile | None = None
    moscow_stage: str = "10.1"
    moscow_service_preset: str = "auto"
    moscow_civil_topology: str = "auto"
    compact_exact_collinear_continuous_stations: bool | None = None
    keep_stage8_ring_ancillary: bool = False
    keep_prescribed_outer_joint_solids: bool = False
    moscow_civil_bolts_enabled: bool = True
    stitch_ring_geometry: bool = True
    stable_reidentify_ring_objects: bool = True

    def __post_init__(self) -> None:
        if not self.namespace:
            raise ValueError("production namespace must not be empty")
        if self.rail_profile is not None and self.moscow_profile is not None:
            raise ValueError(
                "specify either rail_profile or moscow_profile, not both"
            )
        if self.moscow_stage not in {"10.1", "10.2", "10.3", "10.4", "10.5"}:
            raise ValueError(
                "moscow_stage must be '10.1', '10.2', '10.3', '10.4' or '10.5'"
            )
        if self.moscow_stage != "10.1" and self.moscow_profile is None:
            raise ValueError("Moscow Stage 10.2-10.5 requires moscow_profile")
        if self.moscow_service_preset not in {"auto", "legacy", "modern"}:
            raise ValueError(
                "moscow_service_preset must be 'auto', 'legacy' or 'modern'"
            )
        if self.moscow_civil_topology not in {"auto", "ten_equal", "kba"}:
            raise ValueError(
                "moscow_civil_topology must be 'auto', 'ten_equal' or 'kba'"
            )
        if (
            self.moscow_civil_topology in {"ten_equal", "kba"}
            and (
                self.moscow_profile is None
                or self.moscow_profile.civil_family
                != "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
            )
        ):
            raise ValueError(
                "ten_equal/kba Moscow civil topology currently requires "
                "rc_block_6100_5600 civil archetype"
            )
        if (
            self.moscow_stage != "10.5"
            and self.moscow_service_preset == "modern"
        ):
            raise ValueError(
                "modern Moscow service preset is currently bounded to Stage 10.5"
            )

    @property
    def resolved_moscow_civil_topology(self) -> str:
        if self.moscow_profile is None:
            return "none"
        if (
            self.moscow_profile.civil_family
            != "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
        ):
            return "cast_iron_detail_deferred"
        if self.moscow_civil_topology == "auto":
            return "ten_equal"
        return self.moscow_civil_topology

    @property
    def resolved_moscow_service_preset(self) -> str:
        if self.moscow_profile is None:
            return "none"
        if self.moscow_service_preset == "auto":
            return "modern" if self.moscow_stage == "10.5" else "legacy"
        return self.moscow_service_preset

    @property
    def resolved_compact_exact_collinear_continuous_stations(self) -> bool:
        if self.compact_exact_collinear_continuous_stations is None:
            return (
                self.moscow_profile is not None
                and self.moscow_stage == "10.5"
            )
        return bool(self.compact_exact_collinear_continuous_stations)


@dataclass(frozen=True)
class ProductionTunnelBuild:
    scene: ScenePackage
    source_build: ProceduralTunnelBuild
    ancillary: AncillarySet
    asset_specs: tuple[ContinuousAssetSpec, ...]
    alignment_stations: tuple[AlignmentStation, ...]
    config: ProductionConfig

    @property
    def assembly(self) -> TunnelAssembly:
        return self.source_build.assembly


def build_production_scene(
    source_build: ProceduralTunnelBuild,
    *,
    ancillary: AncillarySet,
    surface_meshing: SurfaceMeshingConfig | None = None,
    config: ProductionConfig | None = None,
) -> ProductionTunnelBuild:
    config = config or ProductionConfig()
    surface_meshing = surface_meshing or SurfaceMeshingConfig()
    source_scene = source_build.scene
    stations = production_alignment_stations(source_build.assembly)
    specs = build_continuous_asset_specs(
        namespace=config.namespace,
        ancillary=ancillary,
        label_policy=source_scene.label_policy,
        rail_profile=config.rail_profile,
        moscow_profile=config.moscow_profile,
        moscow_stage=config.moscow_stage,
        moscow_service_preset=config.resolved_moscow_service_preset,
    )

    objects: list[SceneObject] = []
    for obj in source_scene.objects:
        if (
            config.moscow_profile is not None
            and config.moscow_stage in {"10.4", "10.5"}
            and obj.object_type
            in {
                "lining_segment",
                "bolt_pocket_cutter",
                "bolt_head",
                "prescribed_radial_joint",
                "prescribed_circumferential_joint",
            }
        ):
            continue
        if (
            not config.keep_stage8_ring_ancillary
            and obj.object_type.startswith("ancillary_")
        ):
            continue
        if (
            not config.keep_prescribed_outer_joint_solids
            and obj.object_type
            in {
                "prescribed_radial_joint",
                "prescribed_circumferential_joint",
            }
        ):
            continue
        source_obj = (
            stitch_ring_scene_object_to_alignment(
                obj,
                assembly=source_build.assembly,
                stations=stations,
            )
            if config.stitch_ring_geometry
            else obj
        )
        objects.append(
            _copy_scene_object_with_stable_identity(
                source_obj, namespace=config.namespace
            )
            if config.stable_reidentify_ring_objects
            else source_obj
        )

    objects.extend(
        scene_object_from_continuous_asset(
            spec,
            stations,
            namespace=config.namespace,
            compact_exact_collinear_stations=(
                config.resolved_compact_exact_collinear_continuous_stations
            ),
        )
        for spec in specs
    )

    stage10_2_periodic: tuple[SceneObject, ...] = ()
    if (
        config.moscow_profile is not None
        and config.moscow_stage in {"10.2", "10.3", "10.4", "10.5"}
        and config.resolved_moscow_service_preset == "legacy"
    ):
        stage10_2_periodic = _build_stage10_2_periodic_scene_objects(
            profile=config.moscow_profile,
            namespace=config.namespace,
            assembly=source_build.assembly,
            stations=stations,
            label_policy=source_scene.label_policy,
        )
        objects.extend(stage10_2_periodic)

    stage10_5_modern_permanent_way: tuple[SceneObject, ...] = ()
    if (
        config.moscow_profile is not None
        and config.moscow_stage == "10.5"
        and config.resolved_moscow_service_preset == "modern"
    ):
        stage10_5_modern_permanent_way = (
            _build_stage10_5_modern_permanent_way_scene_objects(
                profile=config.moscow_profile,
                namespace=config.namespace,
                assembly=source_build.assembly,
                stations=stations,
                label_policy=source_scene.label_policy,
            )
        )
        objects.extend(stage10_5_modern_permanent_way)

    stage10_3_contact_periodic: tuple[SceneObject, ...] = ()
    if (
        config.moscow_profile is not None
        and (
            config.moscow_stage in {"10.3", "10.4"}
            or (
                config.moscow_stage == "10.5"
                and config.resolved_moscow_service_preset == "legacy"
            )
        )
    ):
        stage10_3_contact_periodic = _build_stage10_3_contact_scene_objects(
            profile=config.moscow_profile,
            namespace=config.namespace,
            assembly=source_build.assembly,
            stations=stations,
            label_policy=source_scene.label_policy,
        )
        objects.extend(stage10_3_contact_periodic)

    stage10_5_modern_contact: tuple[SceneObject, ...] = ()
    if (
        config.moscow_profile is not None
        and config.moscow_stage == "10.5"
        and config.resolved_moscow_service_preset == "modern"
    ):
        modern_pw = config.moscow_profile.modern_permanent_way
        stage10_5_modern_contact = _build_stage10_5_modern_contact_scene_objects(
            profile=config.moscow_profile,
            namespace=config.namespace,
            assembly=source_build.assembly,
            stations=stations,
            label_policy=source_scene.label_policy,
            running_support_pitch_m=modern_pw.support_pitch_m,
            running_support_phase_m=0.5 * modern_pw.support_pitch_m,
        )
        objects.extend(stage10_5_modern_contact)

    stage10_5_service_racks: tuple[SceneObject, ...] = ()
    if (
        config.moscow_profile is not None
        and config.moscow_stage == "10.5"
        and config.resolved_moscow_service_preset == "modern"
    ):
        stage10_5_service_racks = _build_stage10_5_service_rack_scene_objects(
            profile=config.moscow_profile,
            namespace=config.namespace,
            assembly=source_build.assembly,
            stations=stations,
            label_policy=source_scene.label_policy,
        )
        objects.extend(stage10_5_service_racks)

    stage10_5_water_supports: tuple[SceneObject, ...] = ()
    if (
        config.moscow_profile is not None
        and config.moscow_stage == "10.5"
        and config.resolved_moscow_service_preset == "modern"
    ):
        stage10_5_water_supports = (
            _build_stage10_5_water_main_support_scene_objects(
                profile=config.moscow_profile,
                namespace=config.namespace,
                assembly=source_build.assembly,
                stations=stations,
                label_policy=source_scene.label_policy,
            )
        )
        objects.extend(stage10_5_water_supports)

    stage10_4_civil_objects: tuple[SceneObject, ...] = ()
    stage10_4_civil_ring_count = 0
    if (
        config.moscow_profile is not None
        and config.moscow_stage in {"10.4", "10.5"}
    ):
        civil_ranges = civil_ring_ranges(
            source_build.assembly.length_by_chainage_m,
            ring_pitch_m=config.moscow_profile.ring_pitch_m,
        )
        stage10_4_civil_ring_count = len(civil_ranges)
        if (
            config.moscow_profile.civil_family
            == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
        ):
            master_seed = int(
                source_scene.metadata.get("proceduralBuild", {}).get(
                    "masterSeed",
                    5812,
                )
            )
            stage10_4_civil_objects = (
                _build_stage10_4_rc_stage9_architecture_objects(
                    profile=config.moscow_profile,
                    topology=config.resolved_moscow_civil_topology,
                    namespace=config.namespace,
                    assembly=source_build.assembly,
                    stations=stations,
                    surface_meshing=surface_meshing,
                    include_bolts=config.moscow_civil_bolts_enabled,
                    include_prescribed_outer_joint_solids=(
                        config.keep_prescribed_outer_joint_solids
                    ),
                    seed=master_seed,
                )
            )
        else:
            stage10_4_civil_objects = _build_stage10_4_civil_shell_objects(
                profile=config.moscow_profile,
                namespace=config.namespace,
                assembly=source_build.assembly,
                stations=stations,
                label_policy=source_scene.label_policy,
            )
        objects.extend(stage10_4_civil_objects)

    metadata = dict(source_scene.metadata)
    metadata.update(
        {
            "sourceStage": 9,
            "productionGeometry": {
                "namespace": config.namespace,
                "tunnelInstanceID": stable_instance_id(f"{config.namespace}/tunnel"),
                "globalCoordinates": True,
                "coordinatePrecisionIntent": "double/global; no mandatory rebasing",
                "ringAncillaryRemoved": not config.keep_stage8_ring_ancillary,
                "prescribedOuterJointSolidsRemoved": (
                    not config.keep_prescribed_outer_joint_solids
                ),
                "prescribedOuterJointReason": (
                    "Stage-4 literal joint ribs/collars are extrados-only reconstruction "
                    "solids; production interior geometry keeps segment boundaries but "
                    "omits hidden outer solids by default"
                ),
                "continuousInfrastructureAssets": len(specs),
                "sourceRingGeometryMaterialized": bool(
                    source_build.ring_packages
                ),
                "sourceRingGeometrySkippedAsFullyReplaced": (
                    config.moscow_profile is not None
                    and config.moscow_stage in {"10.4", "10.5"}
                    and not source_build.ring_packages
                ),
                "ringGeometryStitchedToAlignment": config.stitch_ring_geometry,
                "ringGeometryAlignmentMap": (
                    "piecewise_linear_xz_by_local_y"
                    if config.stitch_ring_geometry
                    else "stage7_rigid_ring_translation"
                ),
                "internalAncillaryCaps": 0,
                "railProfile": (
                    "stage10_1_r65_gost_r51685_2022"
                    if config.moscow_profile is not None
                    else (
                        "stage9_generic_lowpoly_16"
                        if config.rail_profile is None
                        else "custom"
                    )
                ),
                "identity": (
                    "stable 63-bit BLAKE2b IDs from persistent semantic keys; "
                    "independent of chunk length"
                ),
                "chunking": "optional export partitioning, not a precision requirement",
                "continuousSweepAlignmentCompaction": (
                    "exact_zero_error_collinear"
                    if config.resolved_compact_exact_collinear_continuous_stations
                    else "disabled"
                ),
            },
            "productionAlignmentStations": len(stations),
        }
    )
    if config.moscow_profile is not None:
        production_meta = metadata["productionGeometry"]
        production_meta.update(
            {
                "domainStage": config.moscow_stage,
                "moscowProfileID": config.moscow_profile.profile_id,
                "moscowProfileSHA256": (
                    config.moscow_profile.provenance.canonical_sha256
                ),
                "ugrProfileZLocalM": config.moscow_profile.datums.ugr_z_m,
                "ugrCoreZLocalM": (
                    config.moscow_profile.coordinate.profile_z_to_core_z_offset_m
                    + config.moscow_profile.datums.ugr_z_m
                ),
                "ugrZLocalM": (
                    config.moscow_profile.coordinate.profile_z_to_core_z_offset_m
                    + config.moscow_profile.datums.ugr_z_m
                ),
                "trackAxisXProfileLocalM": (
                    config.moscow_profile.datums.track_axis_x_m
                ),
                "trackAxisZProfileLocalM": (
                    config.moscow_profile.datums.track_axis_z_m
                ),
                "trackAxisXLocalM": config.moscow_profile.datums.track_axis_x_m,
                "trackAxisZLocalM": (
                    config.moscow_profile.coordinate.profile_z_to_core_z_offset_m
                    + config.moscow_profile.datums.track_axis_z_m
                ),
                "liningAxisXProfileLocalM": (
                    config.moscow_profile.datums.lining_axis_x_m
                ),
                "liningAxisZProfileLocalM": (
                    config.moscow_profile.datums.lining_axis_z_m
                ),
                "liningAxisXLocalM": (
                    config.moscow_profile.datums.lining_axis_x_m
                ),
                "liningAxisZLocalM": (
                    config.moscow_profile.coordinate.profile_z_to_core_z_offset_m
                    + config.moscow_profile.datums.lining_axis_z_m
                ),
                "profileZToCoreZOffsetM": (
                    config.moscow_profile.coordinate.profile_z_to_core_z_offset_m
                ),
                "coordinateMapping": (
                    "profile +X -> core +X; profile Z -> core Z by subtracting "
                    "the +1.670m profile lining-axis datum; route chainage +X -> "
                    "core +Y; route left +Y -> core -X; route +Z -> translated core +Z"
                ),
                "gaugePlacement": (
                    "R65 inner working faces at UGR-0.013m"
                ),
                "servicePreset": (
                    config.resolved_moscow_service_preset
                ),
                "servicePresetID": (
                    config.moscow_profile.default_service_preset
                    if config.resolved_moscow_service_preset == "modern"
                    else "LEGACY_R65_TIMBER_KD65_2001_REFERENCE"
                ),
                "permanentWayStatus": (
                    "implemented_stage10_5_modern_LVT_M_APC4"
                    if (
                        config.moscow_stage == "10.5"
                        and config.resolved_moscow_service_preset == "modern"
                    )
                    else (
                        "implemented_stage10_2_initial_geometry"
                        if config.moscow_stage in {"10.2", "10.3", "10.4", "10.5"}
                        else "deferred_to_stage10_2"
                    )
                ),
                "permanentWayPresetID": (
                    config.moscow_profile.modern_permanent_way.preset_id
                    if (
                        config.moscow_stage == "10.5"
                        and config.resolved_moscow_service_preset == "modern"
                    )
                    else (
                        "LEGACY_R65_TIMBER_KD65_2001_REFERENCE"
                        if config.moscow_stage in {"10.2", "10.3", "10.4", "10.5"}
                        else None
                    )
                ),
                "trackConcreteStatus": (
                    "implemented_stage10_2_source_backed_with_explicit_fallbacks"
                    if config.moscow_stage in {"10.2", "10.3", "10.4", "10.5"}
                    else "deferred_to_stage10_2"
                ),
                "contactRailStatus": (
                    "implemented_stage10_5_modern_segmented_cover_and_dedicated_support"
                    if (
                        config.moscow_stage == "10.5"
                        and config.resolved_moscow_service_preset == "modern"
                    )
                    else (
                        "implemented_stage10_3_initial_geometry_with_explicit_fallbacks"
                        if config.moscow_stage in {"10.3", "10.4", "10.5"}
                        else "deferred_to_stage10_3"
                    )
                ),
                "contactRailPresetID": (
                    config.moscow_profile.modern_contact_rail.preset_id
                    if (
                        config.moscow_stage == "10.5"
                        and config.resolved_moscow_service_preset == "modern"
                    )
                    else (
                        "LEGACY_FROLOV_VNIR_CONTACT_2001_REFERENCE"
                        if config.moscow_stage in {"10.3", "10.4", "10.5"}
                        else None
                    )
                ),
                "civilShellStatus": (
                    (
                        (
                            "implemented_stage10_4_rc_stage9_architecture_"
                            f"{config.resolved_moscow_civil_topology}"
                        )
                        if config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                        else (
                            "implemented_stage10_4_cast_iron_smooth_envelope_"
                            "detail_deferred"
                        )
                    )
                    if config.moscow_stage in {"10.4", "10.5"}
                    else "deferred_to_stage10_4"
                ),
                "civilArchetypeID": config.moscow_profile.civil_family,
                "walkwayStatus": (
                    "implemented_stage10_4_source_backed_geometry"
                    if config.moscow_stage in {"10.4", "10.5"}
                    else "deferred_to_stage10_4"
                ),
                "nonRailInfrastructureStatus": (
                    "r2k11_cable_racks_and_dn80_water_main_with_supports_implemented"
                    if (
                        config.moscow_stage == "10.5"
                        and config.resolved_moscow_service_preset == "modern"
                    )
                    else (
                        "moscow_walkway_stage10_4_stage8_services_transitional"
                        if config.moscow_stage in {"10.4", "10.5"}
                        else (
                            "stage8_walkway_and_services_until_stage10_4"
                            if config.moscow_stage == "10.3"
                            else (
                                "stage8_walkway_and_services_until_stage10_3_to_10_4"
                                if config.moscow_stage == "10.2"
                                else "stage8_baseline_until_stage10_2_to_10_4"
                            )
                        )
                    )
                ),
                "serviceCableCount": sum(
                    1
                    for obj in objects
                    if obj.object_type == "production_service_cable"
                ),
                "serviceCableRackCount": len(stage10_5_service_racks),
                "serviceCableRackFamily": (
                    config.moscow_profile.cable_rack.family
                    if stage10_5_service_racks
                    else None
                ),
                "serviceCableRackHornCount": (
                    config.moscow_profile.cable_rack.horn_count
                    if stage10_5_service_racks
                    else 0
                ),
                "serviceCableRackAssemblyDesignation": (
                    config.moscow_profile.cable_rack.assembly_designation
                    if stage10_5_service_racks
                    else None
                ),
                "serviceCableRackUprightDesignation": (
                    config.moscow_profile.cable_rack.upright_designation
                    if stage10_5_service_racks
                    else None
                ),
                "serviceCableRackHornDesignation": (
                    config.moscow_profile.cable_rack.horn_designation
                    if stage10_5_service_racks
                    else None
                ),
                "serviceCablePlacesPerHorn": (
                    config.moscow_profile.cable_rack.cable_places_per_horn
                    if stage10_5_service_racks
                    else 0
                ),
                "serviceCableOccupiedPlacesPerHorn": (
                    config.moscow_profile.cable_rack.occupied_places_per_horn
                    if stage10_5_service_racks
                    else 0
                ),
                "serviceCableRacksPerCivilRing": (
                    2 if stage10_5_service_racks else 0
                ),
                "serviceCableExactRouteScheduleResolved": (
                    False if stage10_5_service_racks else None
                ),
                "servicePipeStatus": (
                    "implemented_normative_DN80_with_explicit_placement_fallback"
                    if (
                        config.moscow_stage == "10.5"
                        and config.resolved_moscow_service_preset == "modern"
                    )
                    else "legacy_stage8_preview"
                ),
                "serviceWaterMainCount": sum(
                    1
                    for obj in objects
                    if obj.object_type == "production_water_main"
                ),
                "serviceWaterMainSupportCount": len(
                    stage10_5_water_supports
                ),
                "serviceWaterMainSupportMaxPitchM": (
                    config.moscow_profile.water_main.support_max_pitch_m
                    if stage10_5_water_supports
                    else None
                ),
                "serviceWaterMainMinNominalDNmm": (
                    config.moscow_profile.water_main.min_nominal_dn_mm
                    if (
                        config.moscow_stage == "10.5"
                        and config.resolved_moscow_service_preset == "modern"
                    )
                    else None
                ),
                "legacyStage8TubeCount": sum(
                    1
                    for obj in objects
                    if obj.object_type == "production_tube"
                ),
                "sleeperCount": sum(
                    1
                    for obj in stage10_2_periodic
                    if obj.object_type == "production_sleeper"
                ),
                "sleeperPitchM": (
                    config.moscow_profile.sleeper.pitch_m
                    if stage10_2_periodic
                    else None
                ),
                "sleeperPhaseRule": (
                    "half_pitch_from_tunnel_start"
                    if stage10_2_periodic
                    else None
                ),
                "modernLVTSupportCount": sum(
                    1
                    for obj in stage10_5_modern_permanent_way
                    if obj.object_type == "production_lvt_block"
                ),
                "modernLVTSupportPitchM": (
                    config.moscow_profile.modern_permanent_way.support_pitch_m
                    if stage10_5_modern_permanent_way
                    else None
                ),
                "modernLVTBlocksPerEvent": (
                    2 if stage10_5_modern_permanent_way else 0
                ),
                "modernLVTBridgesCentralDrain": (
                    False if stage10_5_modern_permanent_way else None
                ),
                "contactRailSupportCount": (
                    sum(
                        1
                        for obj in (
                            stage10_5_modern_contact
                            if stage10_5_modern_contact
                            else stage10_3_contact_periodic
                        )
                        if obj.object_type == "production_contact_rail_bracket"
                    )
                ),
                "contactRailCoverSpanCount": sum(
                    1
                    for obj in stage10_5_modern_contact
                    if obj.object_type == "production_contact_rail_cover_span"
                ),
                "contactRailSupportHoodCount": sum(
                    1
                    for obj in stage10_5_modern_contact
                    if obj.object_type == "production_contact_rail_support_hood"
                ),
                "contactRailTargetPitchM": (
                    config.moscow_profile.modern_contact_rail.support_target_pitch_m
                    if stage10_5_modern_contact
                    else (
                        config.moscow_profile.contact_rail.support_target_pitch_m
                        if stage10_3_contact_periodic
                        else None
                    )
                ),
                "contactRailSupportSchedule": (
                    "5m_targets_snapped_to_midpoints_between_running_supports"
                    if stage10_5_modern_contact
                    else (
                        "independent_5m_targets_snapped_to_nearest_timber_sleeper"
                        if stage10_3_contact_periodic
                        else None
                    )
                ),
                "contactRailSupportSeparateFromRunningSupport": (
                    True if stage10_5_modern_contact else False
                ),
                "contactRailAxisProfileXM": (
                    contact_rail_axis_profile_x(config.moscow_profile)
                    if config.moscow_stage in {"10.3", "10.4", "10.5"}
                    else None
                ),
                "contactRailWorkingSurfaceProfileZM": (
                    config.moscow_profile.contact_rail.working_surface_z_m
                    if config.moscow_stage in {"10.3", "10.4", "10.5"}
                    else None
                ),
                "contactRailCoverEraMismatch": (
                    False
                    if stage10_5_modern_contact
                    else (
                        config.moscow_profile.contact_rail.cover_era_mismatch
                        if stage10_3_contact_periodic
                        else None
                    )
                ),
                "stage9CivilGeometryRemoved": (
                    config.moscow_stage in {"10.4", "10.5"}
                ),
                "moscowCivilTopology": (
                    config.resolved_moscow_civil_topology
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowCivilTopologyEvidenceStatus": (
                    (
                        "S026_source_backed_10_identical_blocks"
                        if config.resolved_moscow_civil_topology == "ten_equal"
                        else (
                            "user_reported_Moscow_photo_reference_"
                            "pending_research_pinpoint"
                            if config.resolved_moscow_civil_topology == "kba"
                            else "cast_iron_detail_deferred"
                        )
                    )
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowCivilCompositeDetailStatus": (
                    (
                        "stage9_segment_joint_bolt_architecture_transferred"
                        if config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                        else "cast_iron_detail_deferred_pending_research"
                    )
                    if config.moscow_stage in {"10.4", "10.5"}
                    else "deferred_to_stage10_4"
                ),
                "moscowCivilStage9ArchitectureTransferred": (
                    config.moscow_stage in {"10.4", "10.5"}
                    and config.moscow_profile.civil_family
                    == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                ),
                "moscowCivilRotationStrategy": (
                    source_build.assembly.config.ring_rotation_strategy.value
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else None
                ),
                "moscowCivilRotationModel": (
                    "stage7_ring_pose_on_independent_moscow_civil_rhythm"
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else None
                ),
                "moscowCivilRotationSeed": (
                    _stage9_child_seed(
                        int(
                            source_scene.metadata.get(
                                "proceduralBuild", {}
                            ).get("masterSeed", 5812)
                        ),
                        0,
                        10_000,
                    )
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else None
                ),
                "moscowCivilRotationAppliedOnlyToLining": (
                    config.moscow_stage in {"10.4", "10.5"}
                    and config.moscow_profile.civil_family
                    == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                ),
                "moscowCivilSegmentObjectCount": sum(
                    1
                    for obj in stage10_4_civil_objects
                    if obj.object_type == "lining_segment"
                ),
                "moscowCivilPrescribedRadialJointCount": sum(
                    1
                    for obj in stage10_4_civil_objects
                    if obj.object_type
                    == "prescribed_radial_joint"
                ),
                "moscowCivilPrescribedCircumferentialJointCount": sum(
                    1
                    for obj in stage10_4_civil_objects
                    if obj.object_type
                    == "prescribed_circumferential_joint"
                ),
                "moscowCivilBoltPocketCount": sum(
                    1
                    for obj in stage10_4_civil_objects
                    if obj.object_type == "bolt_pocket_cutter"
                ),
                "moscowCivilBoltHeadCount": sum(
                    1
                    for obj in stage10_4_civil_objects
                    if obj.object_type == "bolt_head"
                ),
                "moscowCivilBoltsEnabled": (
                    config.moscow_civil_bolts_enabled
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else False
                ),
                "moscowCivilLegacyBoltLayout": (
                    BoltLayoutType.TYPE1_CENTERED.value
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else None
                ),
                "moscowCivilLegacyBoltBooleanOverlapM": (
                    0.005
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else 0.0
                ),
                "moscowCivilLegacyFastenerVisualTransfer": (
                    config.moscow_stage in {"10.4", "10.5"}
                    and config.moscow_profile.civil_family
                    == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                ),
                "moscowCivilLegacyObjectTypesPreserved": (
                    config.moscow_stage in {"10.4", "10.5"}
                    and config.moscow_profile.civil_family
                    == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                ),
                "moscowCivilLegacyPrescribedJointSolidsIncluded": (
                    config.moscow_stage in {"10.4", "10.5"}
                    and config.moscow_profile.civil_family
                    == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                ),
                "moscowCivilRCPermanentBoltedBlockJointsSource": (
                    False
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else None
                ),
                "moscowCivilRenderedBlockCount": sum(
                    1
                    for obj in stage10_4_civil_objects
                    if obj.object_type == "lining_segment"
                ),
                "moscowCivilRCVisualSeamWidthM": 0.0,
                "moscowCivilRCWorkingRebarDiameterM": (
                    0.016
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else 0.0
                ),
                "moscowCivilRCBlockVolumeSourceM3": (
                    0.46
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else 0.0
                ),
                "moscowCivilRCBlockMassSourceT": (
                    1.15
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else 0.0
                ),
                "moscowCivilRCConcreteGradeHistorical": (
                    "400"
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else ""
                ),
                "moscowCivilRCAssemblyPinDiameterM": (
                    0.022
                    if (
                        config.moscow_stage in {"10.4", "10.5"}
                        and config.moscow_profile.civil_family
                        == "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
                    )
                    else 0.0
                ),
                "moscowCivilDetailAccuracyBoundary": (
                    (
                        "Moscow RC principal radii and ten-equal topology are "
                        "source-backed by S026. K/B/A topology is an explicit "
                        "user-selected photo-reference alternative pending a "
                        "registered source. Segment/joint/bolt pocket/head "
                        "geometry is transferred from the old Stage-9 "
                        "architecture and is not claimed as Moscow historical "
                        "fastener geometry."
                    )
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowCivilRingCount": (
                    stage10_4_civil_ring_count
                    if config.moscow_stage in {"10.4", "10.5"}
                    else 0
                ),
                "moscowCivilRingPitchM": (
                    config.moscow_profile.ring_pitch_m
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowCivilIntradosRadiusM": (
                    config.moscow_profile.intrados_radius_m
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowCivilExtradosRadiusM": (
                    config.moscow_profile.extrados_radius_m
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowCivilGeometryMode": (
                    config.moscow_profile.civil_geometry_mode
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowCivilSegmentSurfaceMode": (
                    config.moscow_profile.civil_segment_surface_mode
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowWalkwayTopProfileZM": (
                    config.moscow_profile.walkway.top_z_m
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowWalkwayInnerEdgeProfileXM": (
                    config.moscow_profile.walkway.inner_edge_x_m
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "moscowWalkwayOuterEdgeProfileXM": (
                    config.moscow_profile.walkway.outer_edge_x_m
                    if config.moscow_stage in {"10.4", "10.5"}
                    else None
                ),
                "transitionalCivilGapStatus": (
                    "closed_by_stage10_4_moscow_shell"
                    if config.moscow_stage in {"10.4", "10.5"}
                    else "open_until_stage10_4"
                ),
            }
        )

    scene = ScenePackage(
        name=f"tunnel_production_{config.namespace}",
        mode=SceneMode.MULTI_RING_TUNNEL,
        label_policy=source_scene.label_policy,
        objects=tuple(objects),
        metadata=metadata,
    )
    return ProductionTunnelBuild(
        scene=scene,
        source_build=source_build,
        ancillary=ancillary,
        asset_specs=specs,
        alignment_stations=stations,
        config=config,
    )


def _build_stage10_replaced_source_skeleton(
    *,
    ring_config: RingConfig,
    assembly_config: TunnelAssemblyConfig,
    label_policy: LabelPolicy,
    include_prescribed_joint_solids: bool,
    seed: int,
) -> ProceduralTunnelBuild:
    """Build Stage-7 provenance/poses without meshes that Stage 10.4+ discards.

    Moscow Stage 10.4/10.5 replaces every source lining/joint/bolt object before
    the production scene is emitted. Materializing those Stage-7 meshes first is
    pure transient work. This skeleton reproduces the source assembly and scene
    metadata exactly while intentionally carrying no ring packages or objects.
    """
    if abs(assembly_config.ring_width_m - ring_config.width_m) > 1e-12:
        raise ValueError(
            "assembly_config.ring_width_m must equal ring_config.width_m so adjacent "
            "ring chainage is coherent"
        )

    assembly = sample_tunnel_assembly(
        assembly_config,
        seed=_stage9_child_seed(seed, 0, 10_000),
    )
    cfg = assembly.config
    legacy_override = (
        cfg.uses_legacy_omega_x_override or cfg.uses_legacy_omega_z_override
    )
    ring_metadata = [
        {
            "ringID": index,
            "chainageM": pose.chainage_m,
            "translationM": list(pose.translation_m),
            "rotationYDeg": pose.rotation_y_deg,
            "nominalRotationDeg": pose.nominal_rotation_deg,
            "angularImperfectionDeg": pose.angular_imperfection_deg,
            "sourcePackage": f"tunnel_scanner_nominal_ring_{index:04d}",
        }
        for index, pose in enumerate(assembly.poses)
    ]
    metadata = {
        "sourceStage": "7.1",
        "sourceEquation": "Yang et al. (2026) Eq. (21)",
        "ringCount": cfg.n_rings,
        "paperRingCountBounds": [10, 30],
        "ringWidthM": cfg.ring_width_m,
        "chainageLengthM": assembly.length_by_chainage_m,
        "axisDisplacementAmplitudeM": cfg.displacement_amplitude_m,
        "frequencyParameterization": (
            "explicit_rad_per_ring_override"
            if legacy_override
            else "physical_wavelength_by_chainage"
        ),
        "lateralWavelengthM": cfg.resolved_lateral_wavelength_m,
        "verticalWavelengthM": cfg.resolved_vertical_wavelength_m,
        "omegaXRadPerM": cfg.resolved_omega_x_rad_per_m,
        "omegaZRadPerM": cfg.resolved_omega_z_rad_per_m,
        "omegaXRadPerRing": cfg.resolved_omega_x,
        "omegaZRadPerRing": cfg.resolved_omega_z,
        "frequencyStatus": (
            "explicit omega override supplied by caller"
            if legacy_override
            else (
                "Stage-7.1 engineering defaults: 50 m lateral wavelength and "
                "100 m vertical wavelength; paper publishes omega symbols but no values"
            )
        ),
        "deterministicAdjacentStepBoundXM": (
            cfg.deterministic_adjacent_step_bound_x_m()
        ),
        "deterministicAdjacentStepBoundZM": (
            cfg.deterministic_adjacent_step_bound_z_m()
        ),
        "deterministicAdjacentTransverseStepBoundM": (
            cfg.deterministic_adjacent_transverse_step_bound_m()
        ),
        "axisNoiseSigmaM": cfg.axis_noise_sigma_m,
        "axisNoiseStatus": (
            "Stage-7.1 interprets printed N(0,0.005 m^2) as sigma=0.005 m; "
            "literal variance would imply ~70.7 mm sigma"
        ),
        "rotationStrategy": cfg.ring_rotation_strategy.value,
        "staggerBoundDeg": cfg.stagger_bound_deg,
        "angularImperfectionFraction": cfg.angular_imperfection_fraction,
        "lateralOffsetsRecentered": cfg.recenter_lateral_offsets,
        "lateralRecenterM": list(assembly.lateral_recenter_m),
        "seed": assembly.seed,
        "coordinateConvention": {
            "longitudinalAxis": "+Y",
            "crossSection": "XZ",
            "ringRotationAxis": "+Y",
            "units": "metres",
        },
        "ringPoses": ring_metadata,
        "ancillaryTransformPolicy": {
            "objectsWithStitchedAlignment": 0,
            "policy": (
                "Stage-8 ancillary infrastructure uses a piecewise-linear X/Z sweep "
                "through ring centres with shared inter-ring boundary cross-sections; "
                "it does not follow segment-ring axial staggering and remains fixed "
                "relative to the tunnel gravity frame"
            ),
        },
        "booleanPipeline": (
            "Stage-6 cutter/head metadata is preserved after Stage-7.1 world transform; "
            "Blender Boolean targets remain ring-local stable names"
        ),
        "proceduralBuild": {
            "masterSeed": int(seed),
            "ringGeometryRandomizedIndependently": True,
            "includeBolts": False,
            "boltLayout": None,
            "includeAncillary": False,
            "ancillarySamplingPolicy": None,
            "ancillarySceneGlobalCrossSection": False,
            "ancillaryObjectCountPerRing": 0,
            "labelPolicy": label_policy.value,
            "includePrescribedJointSolids": bool(
                include_prescribed_joint_solids
            ),
            "terminalCircumferentialJoint": False,
            "expectedCircumferentialInterfaces": max(
                0,
                assembly_config.n_rings - 1,
            ),
        },
    }
    scene = ScenePackage(
        name=f"tunnel_scanner_stage7_1_{assembly_config.n_rings:02d}_rings",
        mode=SceneMode.MULTI_RING_TUNNEL,
        label_policy=label_policy,
        objects=(),
        metadata=metadata,
    )
    return ProceduralTunnelBuild(
        scene=scene,
        assembly=assembly,
        ring_packages=(),
    )


def build_production_tunnel(
    *,
    ring_config: RingConfig | None = None,
    assembly_config: TunnelAssemblyConfig | None = None,
    surface_meshing: SurfaceMeshingConfig | None = None,
    include_bolts: bool = True,
    label_policy: LabelPolicy = LabelPolicy.STSD_COARSE,
    ancillary_config: AncillaryConfig | None = None,
    ancillary_sampling_policy: AncillarySamplingPolicy | str = AncillarySamplingPolicy.REFERENCE,
    production_config: ProductionConfig | None = None,
    seed: int = 5812,
) -> ProductionTunnelBuild:
    ring_config = ring_config or RingConfig()
    surface_meshing = surface_meshing or SurfaceMeshingConfig()
    if (
        production_config is not None
        and production_config.moscow_profile is not None
        and production_config.moscow_stage in {"10.4", "10.5"}
    ):
        production_config = replace(
            production_config,
            moscow_civil_bolts_enabled=bool(include_bolts),
        )
    if assembly_config is None:
        assembly_config = TunnelAssemblyConfig(ring_width_m=ring_config.width_m)
    if ancillary_config is None:
        ancillary_config = sample_ancillary_config(
            ring_config.inner_radius_m,
            seed=seed,
            policy=ancillary_sampling_policy,
        )
    ancillary = build_ancillary_set(
        inner_radius_m=ring_config.inner_radius_m,
        length_m=ring_config.width_m,
        config=ancillary_config,
    )

    source_geometry_fully_replaced = (
        production_config is not None
        and production_config.moscow_profile is not None
        and production_config.moscow_stage in {"10.4", "10.5"}
    )
    include_prescribed_joint_solids = (
        production_config.keep_prescribed_outer_joint_solids
        if production_config is not None
        else False
    )
    if source_geometry_fully_replaced:
        source = _build_stage10_replaced_source_skeleton(
            ring_config=ring_config,
            assembly_config=assembly_config,
            label_policy=label_policy,
            include_prescribed_joint_solids=include_prescribed_joint_solids,
            seed=seed,
        )
    else:
        source = build_procedural_nominal_tunnel(
            ring_config=ring_config,
            assembly_config=assembly_config,
            surface_meshing=surface_meshing,
            include_bolts=include_bolts,
            include_ancillary=False,
            include_prescribed_joint_solids=include_prescribed_joint_solids,
            label_policy=label_policy,
            seed=seed,
        )
    return build_production_scene(
        source,
        ancillary=ancillary,
        surface_meshing=surface_meshing,
        config=production_config,
    )


# ---------------------------------------------------------------------------
# Optional chunking
# ---------------------------------------------------------------------------


class ChunkBoundaryPolicy(str, Enum):
    """Export partition policy; unrelated to coordinate precision."""

    RING_ALIGNED = "ring_aligned"
    EXACT_LENGTH = "exact_length"


@dataclass(frozen=True)
class ChunkDescriptor:
    chunk_id: int
    start_chainage_m: float
    end_chainage_m: float
    ring_ids: tuple[int, ...]

    @property
    def length_m(self) -> float:
        return self.end_chainage_m - self.start_chainage_m


def plan_chunks(
    assembly: TunnelAssembly,
    *,
    chunk_length_m: float,
    boundary_policy: ChunkBoundaryPolicy | str = ChunkBoundaryPolicy.RING_ALIGNED,
) -> tuple[ChunkDescriptor, ...]:
    if not math.isfinite(chunk_length_m) or chunk_length_m <= 0.0:
        raise ValueError("chunk_length_m must be finite and positive")
    policy = ChunkBoundaryPolicy(boundary_policy)
    total = assembly.length_by_chainage_m
    L = assembly.config.ring_width_m

    if policy is ChunkBoundaryPolicy.RING_ALIGNED:
        rings_per_chunk = max(
            1,
            int(math.floor(chunk_length_m / L + 0.5)),
        )
        chunks: list[ChunkDescriptor] = []
        first_ring = 0
        cid = 0
        while first_ring < assembly.config.n_rings:
            last_ring_exclusive = min(
                assembly.config.n_rings,
                first_ring + rings_per_chunk,
            )
            chunks.append(
                ChunkDescriptor(
                    chunk_id=cid,
                    start_chainage_m=first_ring * L,
                    end_chainage_m=last_ring_exclusive * L,
                    ring_ids=tuple(range(first_ring, last_ring_exclusive)),
                )
            )
            cid += 1
            first_ring = last_ring_exclusive
        return tuple(chunks)

    chunks = []
    start_chainage = 0.0
    cid = 0
    next_ring_id = 0
    n_rings = assembly.config.n_rings
    while start_chainage < total - 1e-12:
        end_chainage = min(total, start_chainage + chunk_length_m)
        final_chunk = math.isclose(end_chainage, total, abs_tol=1e-12)
        assigned: list[int] = []

        # Ring centres are monotonic, so EXACT_LENGTH chunk planning can walk
        # them once instead of rescanning all N rings for every metric chunk.
        while next_ring_id < n_rings:
            center = (next_ring_id + 0.5) * L
            if center < start_chainage:
                next_ring_id += 1
                continue
            belongs = center < end_chainage or (
                final_chunk
                and math.isclose(center, end_chainage, abs_tol=1e-12)
            )
            if not belongs:
                break
            assigned.append(next_ring_id)
            next_ring_id += 1

        chunks.append(
            ChunkDescriptor(
                cid,
                start_chainage,
                end_chainage,
                tuple(assigned),
            )
        )
        cid += 1
        start_chainage = end_chainage
    return tuple(chunks)

def _chunk_piece_key(spec: ContinuousAssetSpec, chunk: ChunkDescriptor) -> str:
    start_um = round(chunk.start_chainage_m * 1_000_000)
    end_um = round(chunk.end_chainage_m * 1_000_000)
    return f"{spec.persistent_key}/chunk-piece/{start_um}-{end_um}"


def _translate_scene_object(
    obj: SceneObject,
    *,
    dx: float,
    dy: float,
    dz: float,
    extra_properties: Mapping[str, Any] | None = None,
    collection_prefix: tuple[str, ...] = (),
) -> SceneObject:
    props = {**dict(obj.extra_properties), **dict(extra_properties or {})}
    vertices = (
        obj.vertices
        if dx == 0.0 and dy == 0.0 and dz == 0.0
        else tuple((x + dx, y + dy, z + dz) for x, y, z in obj.vertices)
    )
    return SceneObject(
        name=obj.name,
        vertices=vertices,
        faces=obj.faces,
        object_type=obj.object_type,
        ring_id=obj.ring_id,
        label_id=obj.label_id,
        instance_id=obj.instance_id,
        semantic_class=obj.semantic_class,
        segment_id=obj.segment_id,
        segment_name=obj.segment_name,
        segment_kind=obj.segment_kind,
        reconstruction=obj.reconstruction,
        collection_path=(*collection_prefix, *obj.collection_path),
        extra_properties=props,
    )


def _event_chainage_belongs_to_chunk(
    chainage_m: float,
    chunk: ChunkDescriptor,
    *,
    total_length_m: float,
    tolerance_m: float = 1e-12,
) -> bool:
    """Assign one periodic event to exactly one metric chunk.

    Chunk starts are inclusive. Chunk ends are exclusive except for the final
    tunnel end. This keeps periodic assets independent from lining-ring IDs,
    which is required for EXACT_LENGTH chunking.
    """
    c = float(chainage_m)
    if c < chunk.start_chainage_m - tolerance_m:
        return False
    final_chunk = math.isclose(
        chunk.end_chainage_m,
        total_length_m,
        abs_tol=tolerance_m,
    )
    if final_chunk:
        return c <= chunk.end_chainage_m + tolerance_m
    return c < chunk.end_chainage_m - tolerance_m


def _event_chainage_chunk_index(
    chainage_m: float,
    chunks: Sequence[ChunkDescriptor],
    *,
    total_length_m: float,
) -> int | None:
    """Locate one event chunk in O(log chunk_count), preserving boundary rules."""
    lo = 0
    hi = len(chunks)
    while lo < hi:
        mid = (lo + hi) // 2
        chunk = chunks[mid]
        if _event_chainage_belongs_to_chunk(
            chainage_m,
            chunk,
            total_length_m=total_length_m,
        ):
            return mid
        if chainage_m < chunk.start_chainage_m:
            hi = mid
        else:
            lo = mid + 1
    return None


@dataclass(frozen=True)
class Stage105RCModernChunkPlan:
    """Lightweight global state for chunk-first Stage-10.5 RC generation."""

    source_build: ProceduralTunnelBuild
    ancillary: AncillarySet
    asset_specs: tuple[ContinuousAssetSpec, ...]
    alignment_stations: tuple[AlignmentStation, ...]
    config: ProductionConfig
    surface_meshing: SurfaceMeshingConfig
    chunks: tuple[ChunkDescriptor, ...]
    boundary_policy: ChunkBoundaryPolicy
    civil_roll_assembly: TunnelAssembly
    seed: int
    metadata: Mapping[str, Any]

    @property
    def assembly(self) -> TunnelAssembly:
        return self.source_build.assembly

    @property
    def scene_name(self) -> str:
        return f"tunnel_production_{self.config.namespace}"


def build_stage10_5_rc_modern_chunk_plan(
    *,
    chunk_length_m: float,
    boundary_policy: ChunkBoundaryPolicy | str = ChunkBoundaryPolicy.RING_ALIGNED,
    ring_config: RingConfig | None = None,
    assembly_config: TunnelAssemblyConfig | None = None,
    surface_meshing: SurfaceMeshingConfig | None = None,
    include_bolts: bool = True,
    label_policy: LabelPolicy = LabelPolicy.STSD_COARSE,
    ancillary_config: AncillaryConfig | None = None,
    ancillary_sampling_policy: AncillarySamplingPolicy | str = AncillarySamplingPolicy.REFERENCE,
    production_config: ProductionConfig,
    seed: int = 5812,
) -> Stage105RCModernChunkPlan:
    """Plan long RC Stage-10.5 export without materializing the full scene."""
    ring_config = ring_config or RingConfig()
    surface_meshing = surface_meshing or SurfaceMeshingConfig()
    profile = production_config.moscow_profile
    if (
        profile is None
        or production_config.moscow_stage != "10.5"
        or production_config.resolved_moscow_service_preset != "modern"
        or profile.civil_family
        != "RC_BLOCK_MOSCOW_6100_5600_10SEG_R1000"
    ):
        raise ValueError(
            "chunk-first planner currently requires Stage 10.5 modern "
            "rc_block_6100_5600"
        )
    production_config = replace(
        production_config,
        moscow_civil_bolts_enabled=bool(include_bolts),
    )
    if assembly_config is None:
        assembly_config = TunnelAssemblyConfig(
            ring_width_m=ring_config.width_m
        )
    if ancillary_config is None:
        ancillary_config = sample_ancillary_config(
            ring_config.inner_radius_m,
            seed=seed,
            policy=ancillary_sampling_policy,
        )
    ancillary = build_ancillary_set(
        inner_radius_m=ring_config.inner_radius_m,
        length_m=ring_config.width_m,
        config=ancillary_config,
    )
    source = _build_stage10_replaced_source_skeleton(
        ring_config=ring_config,
        assembly_config=assembly_config,
        label_policy=label_policy,
        include_prescribed_joint_solids=(
            production_config.keep_prescribed_outer_joint_solids
        ),
        seed=seed,
    )
    stations = production_alignment_stations(source.assembly)
    specs = build_continuous_asset_specs(
        namespace=production_config.namespace,
        ancillary=ancillary,
        label_policy=label_policy,
        rail_profile=production_config.rail_profile,
        moscow_profile=profile,
        moscow_stage=production_config.moscow_stage,
        moscow_service_preset=(
            production_config.resolved_moscow_service_preset
        ),
    )
    resolved_boundary_policy = ChunkBoundaryPolicy(boundary_policy)
    chunks = plan_chunks(
        source.assembly,
        chunk_length_m=chunk_length_m,
        boundary_policy=resolved_boundary_policy,
    )
    civil_ranges = civil_ring_ranges(
        source.assembly.length_by_chainage_m,
        ring_pitch_m=profile.ring_pitch_m,
    )
    civil_roll_assembly = _sample_moscow_civil_roll_assembly(
        source_assembly=source.assembly,
        profile=profile,
        civil_ring_count=len(civil_ranges),
        master_seed=seed,
    )

    modern_pw = profile.modern_permanent_way
    rail_centers = r65_rail_center_offsets_for_gauge(
        profile.track.gauge_m,
        profile=R65ProductionProfile(),
        measurement_below_top_m=(
            profile.track.gauge_measurement_below_ugr_m
        ),
    )
    lvt_local = build_modern_lvt_local_event_meshes(
        profile,
        rail_centers_profile_x=rail_centers,
    )
    lvt_events = modern_lvt_chainages(
        source.assembly.length_by_chainage_m,
        profile,
    )
    lvt_block_count = len(lvt_events) * sum(
        1 for mesh in lvt_local
        if mesh.object_type == "production_lvt_block"
    )
    support_chainages = modern_contact_support_chainages(
        source.assembly.length_by_chainage_m,
        profile,
        running_support_pitch_m=modern_pw.support_pitch_m,
        running_support_phase_m=0.5 * modern_pw.support_pitch_m,
    )
    cover_spans = modern_cover_span_ranges(
        source.assembly.length_by_chainage_m,
        profile,
        support_chainages=support_chainages,
    )
    rack_chainages = cable_rack_chainages(
        source.assembly.length_by_chainage_m,
        profile,
    )
    water_supports = water_main_support_chainages(
        source.assembly.length_by_chainage_m,
        profile,
    )

    civil_segment_count = (
        6
        if production_config.resolved_moscow_civil_topology == "kba"
        else 10
    )
    full_bolt_rings = sum(
        1
        for _ring_index, start, end in civil_ranges
        if end - start >= profile.ring_pitch_m - 1e-9
    )
    bolt_count = (
        full_bolt_rings * civil_segment_count * 3
        if include_bolts
        else 0
    )
    production_meta = {
        "namespace": production_config.namespace,
        "tunnelInstanceID": stable_instance_id(
            f"{production_config.namespace}/tunnel"
        ),
        "globalCoordinates": True,
        "coordinatePrecisionIntent": (
            "double/global; no mandatory rebasing"
        ),
        "domainStage": "10.5",
        "moscowProfileID": profile.profile_id,
        "moscowProfileSHA256": profile.provenance.canonical_sha256,
        "servicePreset": "modern",
        "servicePresetID": profile.default_service_preset,
        "railProfile": "stage10_1_r65_gost_r51685_2022",
        "sourceRingGeometryMaterialized": False,
        "sourceRingGeometrySkippedAsFullyReplaced": True,
        "chunking": "chunk_first_generation_without_full_scene",
        "chunkFirstGeneration": True,
        "continuousSweepAlignmentCompaction": (
            "exact_zero_error_collinear"
            if production_config.resolved_compact_exact_collinear_continuous_stations
            else "disabled"
        ),
        "permanentWayStatus": "implemented_stage10_5_modern_LVT_M_APC4",
        "permanentWayPresetID": modern_pw.preset_id,
        "modernLVTSupportCount": lvt_block_count,
        "modernLVTSupportPitchM": modern_pw.support_pitch_m,
        "modernLVTBlocksPerEvent": 2,
        "modernLVTBridgesCentralDrain": False,
        "contactRailStatus": (
            "implemented_stage10_5_modern_segmented_cover_and_dedicated_support"
        ),
        "contactRailPresetID": profile.modern_contact_rail.preset_id,
        "contactRailSupportCount": len(support_chainages),
        "contactRailCoverSpanCount": len(cover_spans),
        "contactRailSupportHoodCount": len(support_chainages),
        "contactRailTargetPitchM": (
            profile.modern_contact_rail.support_target_pitch_m
        ),
        "contactRailSupportSeparateFromRunningSupport": True,
        "civilShellStatus": (
            "implemented_stage10_4_rc_stage9_architecture_"
            f"{production_config.resolved_moscow_civil_topology}"
        ),
        "civilArchetypeID": profile.civil_family,
        "walkwayStatus": "implemented_stage10_4_source_backed_geometry",
        "moscowCivilTopology": (
            production_config.resolved_moscow_civil_topology
        ),
        "moscowCivilRingCount": len(civil_ranges),
        "moscowCivilRingPitchM": profile.ring_pitch_m,
        "moscowCivilRenderedBlockCount": (
            civil_segment_count * len(civil_ranges)
        ),
        "moscowCivilSegmentObjectCount": (
            civil_segment_count * len(civil_ranges)
        ),
        "moscowCivilPrescribedRadialJointCount": (
            civil_segment_count * len(civil_ranges)
        ),
        "moscowCivilPrescribedCircumferentialJointCount": (
            civil_segment_count * max(0, len(civil_ranges) - 1)
        ),
        "moscowCivilBoltPocketCount": bolt_count,
        "moscowCivilBoltHeadCount": bolt_count,
        "moscowCivilBoltsEnabled": bool(include_bolts),
        "moscowCivilLegacyBoltLayout": (
            BoltLayoutType.TYPE1_CENTERED.value if include_bolts else None
        ),
        "moscowCivilLegacyBoltBooleanOverlapM": (
            0.005 if include_bolts else 0.0
        ),
        "moscowCivilStage9ArchitectureTransferred": True,
        "moscowCivilRotationStrategy": (
            source.assembly.config.ring_rotation_strategy.value
        ),
        "moscowCivilRotationModel": (
            "stage7_ring_pose_on_independent_moscow_civil_rhythm"
        ),
        "serviceCableCount": sum(
            1
            for spec in specs
            if spec.object_type == "production_service_cable"
        ),
        "serviceCableRackCount": 2 * len(rack_chainages),
        "serviceCableRackFamily": profile.cable_rack.family,
        "serviceCableRackHornCount": profile.cable_rack.horn_count,
        "serviceWaterMainCount": sum(
            1
            for spec in specs
            if spec.object_type == "production_water_main"
        ),
        "serviceWaterMainSupportCount": len(water_supports),
        "serviceWaterMainSupportMaxPitchM": (
            profile.water_main.support_max_pitch_m
        ),
        "serviceWaterMainMinNominalDNmm": (
            profile.water_main.min_nominal_dn_mm
        ),
        "continuousInfrastructureAssets": len(specs),
    }
    metadata = {
        **dict(source.scene.metadata),
        "sourceStage": 9,
        "productionGeometry": production_meta,
        "productionAlignmentStations": len(stations),
    }
    return Stage105RCModernChunkPlan(
        source_build=source,
        ancillary=ancillary,
        asset_specs=specs,
        alignment_stations=stations,
        config=production_config,
        surface_meshing=surface_meshing,
        chunks=chunks,
        boundary_policy=resolved_boundary_policy,
        civil_roll_assembly=civil_roll_assembly,
        seed=int(seed),
        metadata=metadata,
    )


def build_stage10_5_rc_modern_chunk_scene_package(
    plan: Stage105RCModernChunkPlan,
    chunk_id: int,
    *,
    localize_coordinates: bool = False,
) -> ScenePackage:
    """Build one deterministic Stage-10.5 RC chunk from lightweight global state."""
    if not (0 <= int(chunk_id) < len(plan.chunks)):
        raise IndexError("Stage-10.5 RC chunk_id outside planned range")
    chunk = plan.chunks[int(chunk_id)]
    if chunk.chunk_id != int(chunk_id):
        raise AssertionError("Stage-10.5 RC chunk IDs must remain contiguous")

    profile = plan.config.moscow_profile
    if profile is None:
        raise AssertionError("Stage-10.5 RC chunk plan lost Moscow profile")
    assembly = plan.assembly
    total = assembly.length_by_chainage_m
    modern_pw = profile.modern_permanent_way
    start = chunk.start_chainage_m
    end = chunk.end_chainage_m

    periodic: list[SceneObject] = []
    periodic.extend(
        _build_stage10_5_modern_permanent_way_scene_objects(
            profile=profile,
            namespace=plan.config.namespace,
            assembly=assembly,
            stations=plan.alignment_stations,
            label_policy=plan.source_build.scene.label_policy,
            start_chainage_m=start,
            end_chainage_m=end,
        )
    )
    periodic.extend(
        _build_stage10_5_modern_contact_scene_objects(
            profile=profile,
            namespace=plan.config.namespace,
            assembly=assembly,
            stations=plan.alignment_stations,
            label_policy=plan.source_build.scene.label_policy,
            running_support_pitch_m=modern_pw.support_pitch_m,
            running_support_phase_m=0.5 * modern_pw.support_pitch_m,
            start_chainage_m=start,
            end_chainage_m=end,
        )
    )
    periodic.extend(
        _build_stage10_5_service_rack_scene_objects(
            profile=profile,
            namespace=plan.config.namespace,
            assembly=assembly,
            stations=plan.alignment_stations,
            label_policy=plan.source_build.scene.label_policy,
            start_chainage_m=start,
            end_chainage_m=end,
        )
    )
    periodic.extend(
        _build_stage10_5_water_main_support_scene_objects(
            profile=profile,
            namespace=plan.config.namespace,
            assembly=assembly,
            stations=plan.alignment_stations,
            label_policy=plan.source_build.scene.label_policy,
            start_chainage_m=start,
            end_chainage_m=end,
        )
    )
    periodic.extend(
        _build_stage10_4_rc_stage9_architecture_objects(
            profile=profile,
            topology=plan.config.resolved_moscow_civil_topology,
            namespace=plan.config.namespace,
            assembly=assembly,
            stations=plan.alignment_stations,
            surface_meshing=plan.surface_meshing,
            include_bolts=plan.config.moscow_civil_bolts_enabled,
            include_prescribed_outer_joint_solids=(
                plan.config.keep_prescribed_outer_joint_solids
            ),
            seed=plan.seed,
            start_chainage_m=start,
            end_chainage_m=end,
            civil_roll_assembly=plan.civil_roll_assembly,
        )
    )

    chunk_prefix = ("Chunks", f"Chunk_{chunk.chunk_id:05d}")
    objects: list[SceneObject] = [
        _translate_scene_object(
            obj,
            dx=0.0,
            dy=0.0,
            dz=0.0,
            collection_prefix=chunk_prefix,
            extra_properties={
                "chunkID": chunk.chunk_id,
                "chunkStartChainageM": start,
                "chunkEndChainageM": end,
                "chunkAssignmentRule": "event_chainage",
            },
        )
        for obj in periodic
    ]

    clipped = clipped_alignment_stations(
        plan.alignment_stations,
        start_chainage_m=start,
        end_chainage_m=end,
    )
    representative_ring_id = (
        chunk.ring_ids[0]
        if chunk.ring_ids
        else min(
            assembly.config.n_rings - 1,
            max(
                0,
                int(
                    math.floor(
                        0.5 * (start + end)
                        / assembly.config.ring_width_m
                    )
                ),
            ),
        )
    )
    for spec in plan.asset_specs:
        piece_key = _chunk_piece_key(spec, chunk)
        objects.append(
            scene_object_from_continuous_asset(
                spec,
                clipped,
                namespace=plan.config.namespace,
                name_override=f"CH{chunk.chunk_id:05d}__{spec.name}",
                instance_id_override=stable_instance_id(piece_key),
                ring_id_override=representative_ring_id,
                cap_start=math.isclose(start, 0.0, abs_tol=1e-12),
                cap_end=math.isclose(end, total, abs_tol=1e-12),
                collection_prefix=chunk_prefix,
                compact_exact_collinear_stations=(
                    plan.config.resolved_compact_exact_collinear_continuous_stations
                ),
                extra_properties={
                    "chunkID": chunk.chunk_id,
                    "chunkStartChainageM": start,
                    "chunkEndChainageM": end,
                    "chunkPieceKey": piece_key,
                    "sourceInstanceID": spec.instance_id,
                    "sourceInfrastructureID": spec.instance_id,
                    "sourcePersistentKey": spec.persistent_key,
                    "representativeRingID": representative_ring_id,
                    "identityScope": "technical_chunk_piece",
                },
            )
        )

    chunk_world_origin = (0.0, 0.0, 0.0)
    if localize_coordinates:
        midpoint = 0.5 * (start + end)
        origin_station = sample_alignment_station(
            plan.alignment_stations,
            midpoint,
        )
        chunk_world_origin = (
            origin_station.offset_x_m,
            origin_station.world_y_m,
            origin_station.offset_z_m,
        )
        ox, oy, oz = chunk_world_origin
        objects = [
            _translate_scene_object(
                obj,
                dx=-ox,
                dy=-oy,
                dz=-oz,
                extra_properties={
                    "coordinatesLocalizedToChunk": True,
                    "chunkWorldOriginX": ox,
                    "chunkWorldOriginY": oy,
                    "chunkWorldOriginZ": oz,
                },
            )
            for obj in objects
        ]

    return ScenePackage(
        name=f"{plan.scene_name}_chunk_{chunk.chunk_id:05d}",
        mode=SceneMode.MULTI_RING_TUNNEL,
        label_policy=plan.source_build.scene.label_policy,
        objects=tuple(objects),
        metadata={
            **dict(plan.metadata),
            "productionChunk": {
                "chunkID": chunk.chunk_id,
                "startChainageM": start,
                "endChainageM": end,
                "lengthM": chunk.length_m,
                "ringIDs": list(chunk.ring_ids),
                "boundaryPolicy": plan.boundary_policy.value,
                "vertexCoordinatesLocalized": bool(localize_coordinates),
                "globalCoordinatesPreserved": not localize_coordinates,
                "chunkWorldOrigin": list(chunk_world_origin),
                "worldTransformRestoresGlobalCoordinates": True,
                "internalLongitudinalCaps": False,
                "sourceContinuousAssetIDsStableAcrossChunking": True,
                "periodicAssetsAssignedByEventChainage": True,
                "chunkFirstGeneration": True,
            },
        },
    )


def iter_stage10_5_rc_modern_chunk_scene_packages(
    plan: Stage105RCModernChunkPlan,
    *,
    localize_coordinates: bool = False,
) -> Iterator[ScenePackage]:
    """Generate one Stage-10.5 RC chunk at a time from lightweight global state."""
    for chunk in plan.chunks:
        yield build_stage10_5_rc_modern_chunk_scene_package(
            plan,
            chunk.chunk_id,
            localize_coordinates=localize_coordinates,
        )


def iter_chunk_scene_packages(
    production: ProductionTunnelBuild,
    *,
    chunk_length_m: float,
    boundary_policy: ChunkBoundaryPolicy | str = ChunkBoundaryPolicy.RING_ALIGNED,
    localize_coordinates: bool = False,
) -> Iterator[ScenePackage]:
    policy = ChunkBoundaryPolicy(boundary_policy)
    chunks = plan_chunks(
        production.assembly,
        chunk_length_m=chunk_length_m,
        boundary_policy=policy,
    )
    total = production.assembly.length_by_chainage_m
    source_continuous_ids = {spec.instance_id for spec in production.asset_specs}
    non_continuous_objects = tuple(
        obj
        for obj in production.scene.objects
        if obj.instance_id not in source_continuous_ids
    )
    periodic_objects = tuple(
        obj
        for obj in non_continuous_objects
        if "eventChainageM" in obj.extra_properties
    )
    ring_objects = tuple(
        obj
        for obj in non_continuous_objects
        if "eventChainageM" not in obj.extra_properties
    )

    ring_chunk_by_id: dict[int, int] = {}
    for chunk in chunks:
        for ring_id in chunk.ring_ids:
            if ring_id in ring_chunk_by_id:
                raise AssertionError("ring assigned to multiple production chunks")
            ring_chunk_by_id[ring_id] = chunk.chunk_id

    ring_objects_by_chunk: list[list[SceneObject]] = [
        [] for _ in chunks
    ]
    for obj in ring_objects:
        chunk_id = ring_chunk_by_id.get(obj.ring_id)
        if chunk_id is not None:
            ring_objects_by_chunk[chunk_id].append(obj)

    periodic_objects_by_chunk: list[list[SceneObject]] = [
        [] for _ in chunks
    ]
    for obj in periodic_objects:
        chunk_id = _event_chainage_chunk_index(
            float(obj.extra_properties["eventChainageM"]),
            chunks,
            total_length_m=total,
        )
        if chunk_id is not None:
            periodic_objects_by_chunk[chunk_id].append(obj)

    for chunk in chunks:
        chunk_prefix = ("Chunks", f"Chunk_{chunk.chunk_id:05d}")
        objects: list[SceneObject] = [
            _translate_scene_object(
                obj,
                dx=0.0,
                dy=0.0,
                dz=0.0,
                collection_prefix=chunk_prefix,
                extra_properties={
                    "chunkID": chunk.chunk_id,
                    "chunkStartChainageM": chunk.start_chainage_m,
                    "chunkEndChainageM": chunk.end_chainage_m,
                },
            )
            for obj in ring_objects_by_chunk[chunk.chunk_id]
        ]
        objects.extend(
            _translate_scene_object(
                obj,
                dx=0.0,
                dy=0.0,
                dz=0.0,
                collection_prefix=chunk_prefix,
                extra_properties={
                    "chunkID": chunk.chunk_id,
                    "chunkStartChainageM": chunk.start_chainage_m,
                    "chunkEndChainageM": chunk.end_chainage_m,
                    "chunkAssignmentRule": "event_chainage",
                },
            )
            for obj in periodic_objects_by_chunk[chunk.chunk_id]
        )
        clipped = clipped_alignment_stations(
            production.alignment_stations,
            start_chainage_m=chunk.start_chainage_m,
            end_chainage_m=chunk.end_chainage_m,
        )
        representative_ring_id = (
            chunk.ring_ids[0]
            if chunk.ring_ids
            else min(
                production.assembly.config.n_rings - 1,
                max(
                    0,
                    int(
                        math.floor(
                            0.5
                            * (chunk.start_chainage_m + chunk.end_chainage_m)
                            / production.assembly.config.ring_width_m
                        )
                    ),
                ),
            )
        )
        for spec in production.asset_specs:
            piece_key = _chunk_piece_key(spec, chunk)
            objects.append(
                scene_object_from_continuous_asset(
                    spec,
                    clipped,
                    namespace=production.config.namespace,
                    name_override=f"CH{chunk.chunk_id:05d}__{spec.name}",
                    instance_id_override=stable_instance_id(piece_key),
                    ring_id_override=representative_ring_id,
                    cap_start=math.isclose(
                        chunk.start_chainage_m, 0.0, abs_tol=1e-12
                    ),
                    cap_end=math.isclose(
                        chunk.end_chainage_m, total, abs_tol=1e-12
                    ),
                    collection_prefix=chunk_prefix,
                    compact_exact_collinear_stations=(
                        production.config.resolved_compact_exact_collinear_continuous_stations
                    ),
                    extra_properties={
                        "chunkID": chunk.chunk_id,
                        "chunkStartChainageM": chunk.start_chainage_m,
                        "chunkEndChainageM": chunk.end_chainage_m,
                        "chunkPieceKey": piece_key,
                        "sourceInstanceID": spec.instance_id,
                        "sourceInfrastructureID": spec.instance_id,
                        "sourcePersistentKey": spec.persistent_key,
                        "representativeRingID": representative_ring_id,
                        "identityScope": "technical_chunk_piece",
                    },
                )
            )

        chunk_world_origin = (0.0, 0.0, 0.0)
        if localize_coordinates:
            midpoint = 0.5 * (
                chunk.start_chainage_m + chunk.end_chainage_m
            )
            origin_station = sample_alignment_station(
                production.alignment_stations, midpoint
            )
            chunk_world_origin = (
                origin_station.offset_x_m,
                origin_station.world_y_m,
                origin_station.offset_z_m,
            )
            ox, oy, oz = chunk_world_origin
            objects = [
                _translate_scene_object(
                    obj,
                    dx=-ox,
                    dy=-oy,
                    dz=-oz,
                    extra_properties={
                        "coordinatesLocalizedToChunk": True,
                        "chunkWorldOriginX": ox,
                        "chunkWorldOriginY": oy,
                        "chunkWorldOriginZ": oz,
                    },
                )
                for obj in objects
            ]

        yield ScenePackage(
            name=f"{production.scene.name}_chunk_{chunk.chunk_id:05d}",
            mode=SceneMode.MULTI_RING_TUNNEL,
            label_policy=production.scene.label_policy,
            objects=tuple(objects),
            metadata={
                **dict(production.scene.metadata),
                "productionChunk": {
                    "chunkID": chunk.chunk_id,
                    "startChainageM": chunk.start_chainage_m,
                    "endChainageM": chunk.end_chainage_m,
                    "lengthM": chunk.length_m,
                    "ringIDs": list(chunk.ring_ids),
                    "boundaryPolicy": policy.value,
                    "vertexCoordinatesLocalized": bool(localize_coordinates),
                    "globalCoordinatesPreserved": not localize_coordinates,
                    "chunkWorldOrigin": list(chunk_world_origin),
                    "worldTransformRestoresGlobalCoordinates": True,
                    "internalLongitudinalCaps": False,
                    "sourceContinuousAssetIDsStableAcrossChunking": True,
                    "periodicAssetsAssignedByEventChainage": True,
                },
            },
        )


def build_chunk_scene_packages(
    production: ProductionTunnelBuild,
    *,
    chunk_length_m: float,
    boundary_policy: ChunkBoundaryPolicy | str = ChunkBoundaryPolicy.RING_ALIGNED,
    localize_coordinates: bool = False,
) -> tuple[ScenePackage, ...]:
    """Compatibility wrapper that materializes the lazy chunk iterator."""
    return tuple(
        iter_chunk_scene_packages(
            production,
            chunk_length_m=chunk_length_m,
            boundary_policy=boundary_policy,
            localize_coordinates=localize_coordinates,
        )
    )


# ---------------------------------------------------------------------------
# Render-surface cleanup
# ---------------------------------------------------------------------------


def strip_internal_lining_cap_faces(
    scene: ScenePackage,
    *,
    ring_width_m: float | None = None,
    tolerance_m: float = 1e-9,
    require_boolean_tools_absent: bool = True,
) -> ScenePackage:
    """Remove hidden longitudinal end faces between neighbouring lining rings.

    The closed Stage-5/6 solids are useful to Blender Boolean operations. For a
    final realtime render mesh, however, the two end-cap layers at an internal
    ring boundary are unnecessary and can overlap. This function is therefore a
    post-Boolean/render finalization step.

    It intentionally strips only lining_segment faces. Circumferential joint
    solids and other reconstruction objects are left untouched.
    """
    if require_boolean_tools_absent and scene.objects_of_type("bolt_pocket_cutter"):
        raise ValueError(
            "strip_internal_lining_cap_faces must run after bolt cutters are baked/removed"
        )
    if not math.isfinite(tolerance_m) or tolerance_m <= 0.0:
        raise ValueError("tolerance_m must be finite and positive")
    if ring_width_m is None:
        try:
            ring_width_m = float(scene.metadata["ringWidthM"])
        except Exception as exc:
            raise ValueError("ring_width_m is required when scene metadata lacks ringWidthM") from exc
    if not math.isfinite(ring_width_m) or ring_width_m <= 0.0:
        raise ValueError("ring_width_m must be finite and positive")

    lining = scene.objects_of_type("lining_segment")
    if not lining:
        return scene
    global_ring_count = int(
        scene.metadata.get(
            "ringCount",
            max(obj.ring_id for obj in lining) + 1,
        )
    )
    global_max_ring_id = global_ring_count - 1
    removed_total = 0
    objects: list[SceneObject] = []

    for obj in scene.objects:
        if obj.object_type != "lining_segment":
            objects.append(obj)
            continue

        origin_y = (
            float(obj.extra_properties.get("chunkWorldOriginY", 0.0))
            if obj.extra_properties.get("coordinatesLocalizedToChunk", False)
            else 0.0
        )
        props_in = obj.extra_properties
        if (
            "liningRingFrontWorldYM" in props_in
            and "liningRingBackWorldYM" in props_in
        ):
            front_y = float(props_in["liningRingFrontWorldYM"]) - origin_y
            back_y = float(props_in["liningRingBackWorldYM"]) - origin_y
            lining_ring_index = int(
                props_in.get("liningRingIndex", obj.ring_id)
            )
            lining_ring_count = int(
                props_in.get("liningGlobalRingCount", global_ring_count)
            )
            strip_front = lining_ring_index > 0
            strip_back = lining_ring_index < lining_ring_count - 1
        else:
            front_y = (obj.ring_id - 0.5) * ring_width_m - origin_y
            back_y = (obj.ring_id + 0.5) * ring_width_m - origin_y
            strip_front = obj.ring_id > 0
            strip_back = obj.ring_id < global_max_ring_id

        transferred_moscow = bool(
            props_in.get(
                "stage9SegmentJointFastenerArchitectureTransferred",
                False,
            )
        )
        cap_tolerance_m = tolerance_m
        target_front_y = front_y
        target_back_y = back_y
        if transferred_moscow and obj.vertices:
            actual_front_y = min(vertex[1] for vertex in obj.vertices)
            actual_back_y = max(vertex[1] for vertex in obj.vertices)
            metadata_tolerance_m = 1e-8
            if abs(actual_front_y - front_y) > metadata_tolerance_m:
                raise ValueError(
                    f"{obj.name}: Moscow lining front plane metadata mismatch"
                )
            if abs(actual_back_y - back_y) > metadata_tolerance_m:
                raise ValueError(
                    f"{obj.name}: Moscow lining back plane metadata mismatch"
                )
            target_front_y = actual_front_y
            target_back_y = actual_back_y

        kept: list[Face] = []
        removed = 0
        for face in obj.faces:
            ys = [obj.vertices[index][1] for index in face]
            on_front = strip_front and all(
                abs(y - target_front_y) <= cap_tolerance_m for y in ys
            )
            on_back = strip_back and all(
                abs(y - target_back_y) <= cap_tolerance_m for y in ys
            )
            if on_front or on_back:
                removed += 1
            else:
                kept.append(face)

        props = dict(obj.extra_properties)
        props.update(
            {
                "internalLongitudinalCapsStripped": True,
                "longitudinalCapFacesRemoved": removed,
                "renderSurfaceOpenAtInternalRingBoundaries": True,
                "liningCapCleanupPlaneMode": (
                    "mesh_extrema_with_metadata_guard"
                    if transferred_moscow
                    else "legacy_ring_id_plane"
                ),
            }
        )
        removed_total += removed
        objects.append(
            SceneObject(
                name=obj.name,
                vertices=obj.vertices,
                faces=tuple(kept),
                object_type=obj.object_type,
                ring_id=obj.ring_id,
                label_id=obj.label_id,
                instance_id=obj.instance_id,
                semantic_class=obj.semantic_class,
                segment_id=obj.segment_id,
                segment_name=obj.segment_name,
                segment_kind=obj.segment_kind,
                reconstruction=(
                    f"{obj.reconstruction}+stage9_internal_cap_strip"
                    if obj.reconstruction
                    else "stage9_internal_cap_strip"
                ),
                collection_path=obj.collection_path,
                extra_properties=props,
            )
        )

    metadata = dict(scene.metadata)
    metadata["productionLiningCapStrip"] = {
        "removedFaces": removed_total,
        "internalBoundariesOnly": True,
        "outerTunnelEndCapsPreserved": True,
        "requiresBooleanBakeFirst": True,
    }
    return ScenePackage(
        name=scene.name,
        mode=scene.mode,
        label_policy=scene.label_policy,
        objects=tuple(objects),
        metadata=metadata,
    )


def _angle_delta_deg(a_deg: float, b_deg: float) -> float:
    return (a_deg - b_deg + 180.0) % 360.0 - 180.0


def _face_follows_segment_boundary(
    obj: SceneObject,
    face: Face,
    *,
    ring_width_m: float,
    angle_tolerance_deg: float,
    radial_span_tolerance_m: float,
    y_span_tolerance_m: float,
) -> bool:
    props = obj.custom_properties
    required = (
        "segmentFrontStartDeg",
        "segmentFrontEndDeg",
        "segmentBackStartDeg",
        "segmentBackEndDeg",
        "ringTranslationX",
        "ringTranslationY",
        "ringTranslationZ",
        "ringRotationDeg",
    )
    if any(key not in props for key in required):
        return False

    tx = float(props["ringTranslationX"])
    ty = float(props["ringTranslationY"])
    tz = float(props["ringTranslationZ"])
    localized = bool(props.get("coordinatesLocalizedToChunk", False))
    origin_x = float(props.get("chunkWorldOriginX", 0.0)) if localized else 0.0
    origin_y = float(props.get("chunkWorldOriginY", 0.0)) if localized else 0.0
    origin_z = float(props.get("chunkWorldOriginZ", 0.0)) if localized else 0.0
    tx -= origin_x
    ty -= origin_y
    tz -= origin_z
    stitched = bool(props.get("productionRingAlignmentStitched", False))
    rotation_deg = float(props["ringRotationDeg"])
    a = math.radians(rotation_deg)
    c = math.cos(a)
    sr = math.sin(a)

    local_samples: list[tuple[float, float, float]] = []
    for index in face:
        x, y, z = obj.vertices[index]
        local_y = y - ty
        center_x = tx
        center_z = tz
        if stitched:
            front_x = float(props["productionRingFrontOffsetX"]) - origin_x
            front_z = float(props["productionRingFrontOffsetZ"]) - origin_z
            center_x_stitched = float(props["productionRingCenterOffsetX"]) - origin_x
            center_z_stitched = float(props["productionRingCenterOffsetZ"]) - origin_z
            back_x = float(props["productionRingBackOffsetX"]) - origin_x
            back_z = float(props["productionRingBackOffsetZ"]) - origin_z
            if local_y <= 0.0:
                u = min(1.0, max(0.0, (local_y + 0.5 * ring_width_m) / (0.5 * ring_width_m)))
                center_x = front_x + u * (center_x_stitched - front_x)
                center_z = front_z + u * (center_z_stitched - front_z)
            else:
                u = min(1.0, max(0.0, local_y / (0.5 * ring_width_m)))
                center_x = center_x_stitched + u * (back_x - center_x_stitched)
                center_z = center_z_stitched + u * (back_z - center_z_stitched)

        dx = x - center_x
        dz = z - center_z
        # Inverse of Stage-7 axial rotation:
        # world_x = c*x + s*z ; world_z = -s*x + c*z.
        local_x = c * dx - sr * dz
        local_z = sr * dx + c * dz
        radius = math.hypot(local_x, local_z)
        alpha = math.degrees(math.atan2(local_x, local_z))
        local_samples.append((local_y, radius, alpha))

    ys = [sample[0] for sample in local_samples]
    radii = [sample[1] for sample in local_samples]
    if max(ys) - min(ys) <= y_span_tolerance_m:
        return False
    if max(radii) - min(radii) <= radial_span_tolerance_m:
        return False

    fs = float(props["segmentFrontStartDeg"])
    fe = float(props["segmentFrontEndDeg"])
    bs = float(props["segmentBackStartDeg"])
    be = float(props["segmentBackEndDeg"])

    start_matches = True
    end_matches = True
    for local_y, _radius, alpha in local_samples:
        v = (local_y + 0.5 * ring_width_m) / ring_width_m
        # Boolean operations can create vertices microscopically outside a source
        # face. Clamp only for boundary classification.
        v = min(1.0, max(0.0, v))
        expected_start = fs + v * (bs - fs)
        expected_end = fe + v * (be - fe)
        start_matches = start_matches and (
            abs(_angle_delta_deg(alpha, expected_start)) <= angle_tolerance_deg
        )
        end_matches = end_matches and (
            abs(_angle_delta_deg(alpha, expected_end)) <= angle_tolerance_deg
        )
    return start_matches or end_matches


def strip_lining_segment_boundary_faces(
    scene: ScenePackage,
    *,
    ring_width_m: float | None = None,
    angle_tolerance_deg: float = 1e-4,
    radial_span_tolerance_m: float = 1e-5,
    y_span_tolerance_m: float = 1e-8,
    require_boolean_tools_absent: bool = True,
) -> ScenePackage:
    """Remove hidden radial boundary surfaces from every lining segment.

    Unlike exact polygon-signature matching, this classifier is independent of
    neighbouring tessellation density. A boundary face is identified against the
    segment's front/back angular extent as a function of longitudinal position.
    """
    if require_boolean_tools_absent and scene.objects_of_type("bolt_pocket_cutter"):
        raise ValueError(
            "segment boundary cleanup must run after bolt cutters are baked/removed"
        )
    if ring_width_m is None:
        try:
            ring_width_m = float(scene.metadata["ringWidthM"])
        except Exception as exc:
            raise ValueError(
                "ring_width_m is required when scene metadata lacks ringWidthM"
            ) from exc
    if not math.isfinite(ring_width_m) or ring_width_m <= 0.0:
        raise ValueError("ring_width_m must be finite and positive")

    objects: list[SceneObject] = []
    removed_total = 0
    affected_objects = 0
    for obj in scene.objects:
        if obj.object_type != "lining_segment":
            objects.append(obj)
            continue
        remove = {
            face_index
            for face_index, face in enumerate(obj.faces)
            if _face_follows_segment_boundary(
                obj,
                face,
                ring_width_m=ring_width_m,
                angle_tolerance_deg=angle_tolerance_deg,
                radial_span_tolerance_m=radial_span_tolerance_m,
                y_span_tolerance_m=y_span_tolerance_m,
            )
        }
        if not remove:
            objects.append(obj)
            continue

        affected_objects += 1
        removed_total += len(remove)
        props = dict(obj.extra_properties)
        props.update(
            {
                "segmentBoundaryFacesStripped": True,
                "segmentBoundaryFacesRemoved": len(remove),
                "renderSurfaceOpenAtSegmentInterfaces": True,
            }
        )
        objects.append(
            SceneObject(
                name=obj.name,
                vertices=obj.vertices,
                faces=tuple(
                    face
                    for face_index, face in enumerate(obj.faces)
                    if face_index not in remove
                ),
                object_type=obj.object_type,
                ring_id=obj.ring_id,
                label_id=obj.label_id,
                instance_id=obj.instance_id,
                semantic_class=obj.semantic_class,
                segment_id=obj.segment_id,
                segment_name=obj.segment_name,
                segment_kind=obj.segment_kind,
                reconstruction=(
                    f"{obj.reconstruction}+stage9_segment_boundary_strip"
                    if obj.reconstruction
                    else "stage9_segment_boundary_strip"
                ),
                collection_path=obj.collection_path,
                extra_properties=props,
            )
        )

    metadata = dict(scene.metadata)
    metadata["productionSegmentBoundaryStrip"] = {
        "facesRemoved": removed_total,
        "objectsAffected": affected_objects,
        "angleToleranceDeg": angle_tolerance_deg,
        "radialSpanToleranceM": radial_span_tolerance_m,
        "requiresBooleanBakeFirst": True,
        "tessellationIndependent": True,
    }
    return ScenePackage(
        name=scene.name,
        mode=scene.mode,
        label_policy=scene.label_policy,
        objects=tuple(objects),
        metadata=metadata,
    )


def strip_exact_coincident_lining_interface_faces(
    scene: ScenePackage,
    *,
    tolerance_m: float = 1e-9,
    require_boolean_tools_absent: bool = True,
) -> ScenePackage:
    """Remove exact duplicate faces shared by separate lining segment objects.

    In the nominal ring representation neighbouring segment solids each own the
    same radial interface face. Closed solids are useful during Boolean authoring,
    but both copies are unnecessary in the final realtime render surface.
    """
    if require_boolean_tools_absent and scene.objects_of_type("bolt_pocket_cutter"):
        raise ValueError(
            "coincident lining interface cleanup must run after bolt cutters are baked/removed"
        )
    if not math.isfinite(tolerance_m) or tolerance_m <= 0.0:
        raise ValueError("tolerance_m must be finite and positive")

    lining = scene.objects_of_type("lining_segment")
    if not lining:
        return scene

    occurrences: dict[
        tuple[tuple[int, int, int], ...],
        list[tuple[str, int]],
    ] = {}
    for obj in lining:
        for face_index, face in enumerate(obj.faces):
            signature = tuple(
                sorted(
                    _quantized_vertex(obj.vertices[index], tolerance_m)
                    for index in face
                )
            )
            occurrences.setdefault(signature, []).append((obj.name, face_index))

    remove_by_object: dict[str, set[int]] = {}
    duplicate_groups = 0
    for items in occurrences.values():
        object_names = {name for name, _ in items}
        if len(items) > 1 and len(object_names) > 1:
            duplicate_groups += 1
            for name, face_index in items:
                remove_by_object.setdefault(name, set()).add(face_index)

    removed_total = sum(len(indices) for indices in remove_by_object.values())
    objects: list[SceneObject] = []
    for obj in scene.objects:
        remove = remove_by_object.get(obj.name)
        if not remove:
            objects.append(obj)
            continue
        props = dict(obj.extra_properties)
        props.update(
            {
                "coincidentSegmentInterfaceFacesStripped": True,
                "coincidentSegmentInterfaceFacesRemoved": len(remove),
                "renderSurfaceOpenAtSegmentInterfaces": True,
            }
        )
        objects.append(
            SceneObject(
                name=obj.name,
                vertices=obj.vertices,
                faces=tuple(
                    face
                    for face_index, face in enumerate(obj.faces)
                    if face_index not in remove
                ),
                object_type=obj.object_type,
                ring_id=obj.ring_id,
                label_id=obj.label_id,
                instance_id=obj.instance_id,
                semantic_class=obj.semantic_class,
                segment_id=obj.segment_id,
                segment_name=obj.segment_name,
                segment_kind=obj.segment_kind,
                reconstruction=(
                    f"{obj.reconstruction}+stage9_segment_interface_strip"
                    if obj.reconstruction
                    else "stage9_segment_interface_strip"
                ),
                collection_path=obj.collection_path,
                extra_properties=props,
            )
        )

    metadata = dict(scene.metadata)
    metadata["productionSegmentInterfaceStrip"] = {
        "duplicateGroupsRemoved": duplicate_groups,
        "facesRemoved": removed_total,
        "exactCoincidenceToleranceM": tolerance_m,
        "requiresBooleanBakeFirst": True,
    }
    return ScenePackage(
        name=scene.name,
        mode=scene.mode,
        label_policy=scene.label_policy,
        objects=tuple(objects),
        metadata=metadata,
    )


def finalize_production_render_scene(
    scene: ScenePackage,
    *,
    ring_width_m: float | None = None,
    tolerance_m: float = 1e-9,
) -> ScenePackage:
    """Apply post-Boolean lining cleanup for realtime rendering."""
    no_caps = strip_internal_lining_cap_faces(
        scene,
        ring_width_m=ring_width_m,
        tolerance_m=tolerance_m,
    )
    return strip_lining_segment_boundary_faces(
        no_caps,
        ring_width_m=ring_width_m,
    )


# ---------------------------------------------------------------------------
# Topology audit
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateFaceGroup:
    signature: tuple[tuple[int, int, int], ...]
    occurrences: tuple[tuple[str, int], ...]


@dataclass(frozen=True)
class TopologyAudit:
    tolerance_m: float
    duplicate_face_groups: tuple[DuplicateFaceGroup, ...]

    @property
    def duplicate_group_count(self) -> int:
        return len(self.duplicate_face_groups)

    @property
    def duplicate_face_occurrence_count(self) -> int:
        return sum(len(group.occurrences) for group in self.duplicate_face_groups)


def _quantized_vertex(v: Vec3, tolerance_m: float) -> tuple[int, int, int]:
    return (
        round(float(v[0]) / tolerance_m),
        round(float(v[1]) / tolerance_m),
        round(float(v[2]) / tolerance_m),
    )


def audit_exact_coincident_faces(
    scene: ScenePackage,
    *,
    tolerance_m: float = 1e-9,
    object_filter: Callable[[SceneObject], bool] | None = None,
) -> TopologyAudit:
    if not math.isfinite(tolerance_m) or tolerance_m <= 0.0:
        raise ValueError("tolerance_m must be finite and positive")
    occurrences: dict[
        tuple[tuple[int, int, int], ...],
        list[tuple[str, int]],
    ] = {}
    for obj in scene.objects:
        if object_filter is not None and not object_filter(obj):
            continue
        for face_index, face in enumerate(obj.faces):
            signature = tuple(
                sorted(_quantized_vertex(obj.vertices[i], tolerance_m) for i in face)
            )
            occurrences.setdefault(signature, []).append((obj.name, face_index))

    groups = tuple(
        DuplicateFaceGroup(signature, tuple(items))
        for signature, items in occurrences.items()
        if len(items) > 1
    )
    return TopologyAudit(tolerance_m, groups)
