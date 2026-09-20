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

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import math
from typing import Any, Callable, Mapping, Sequence

from .ancillary import (
    AncillaryConfig,
    AncillaryMesh,
    AncillarySamplingPolicy,
    AncillarySet,
    RailSpacingConvention,
    build_ancillary_set,
    sample_ancillary_config,
)
from .assembly import TunnelAssembly, TunnelAssemblyConfig
from .config import RingConfig
from .curved_mesh import SurfaceMeshingConfig
from .mesh import Face, Vec3
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
from .civil import (
    build_annular_shell_sweep,
    civil_ring_ranges,
    walkway_core_xz,
)
from .scene import LabelPolicy, SceneMode, SceneObject, ScenePackage
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
    start = stations[0].chainage_m
    end = stations[-1].chainage_m
    if chainage_m < start - 1e-12 or chainage_m > end + 1e-12:
        raise ValueError("chainage outside station range")
    if math.isclose(chainage_m, start, abs_tol=1e-12):
        return stations[0]
    if math.isclose(chainage_m, end, abs_tol=1e-12):
        return stations[-1]
    for a, b in zip(stations, stations[1:]):
        if a.chainage_m - 1e-12 <= chainage_m <= b.chainage_m + 1e-12:
            if math.isclose(chainage_m, a.chainage_m, abs_tol=1e-12):
                return a
            if math.isclose(chainage_m, b.chainage_m, abs_tol=1e-12):
                return b
            u = (chainage_m - a.chainage_m) / (b.chainage_m - a.chainage_m)
            return AlignmentStation(
                chainage_m=float(chainage_m),
                world_y_m=a.world_y_m + u * (b.world_y_m - a.world_y_m),
                offset_x_m=a.offset_x_m + u * (b.offset_x_m - a.offset_x_m),
                offset_z_m=a.offset_z_m + u * (b.offset_z_m - a.offset_z_m),
                source="interpolated",
            )
    raise AssertionError("failed to sample production alignment")


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
    middle = tuple(
        station
        for station in stations
        if (
            station.chainage_m > start_chainage_m + tol
            and station.chainage_m < end_chainage_m - tol
        )
    )
    result = (first, *middle, last)
    if any(
        b.chainage_m <= a.chainage_m + 1e-12
        for a, b in zip(result, result[1:])
    ):
        raise AssertionError("clipped alignment contains duplicate/non-increasing stations")
    return result


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
                        "moscow_5100_intrados"
                        if moscow_stage in {"10.4", "10.5"}
                        else "future_moscow_5100_intrados_not_clearance_envelope"
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
) -> SceneObject:
    mesh = build_sweep_mesh(
        spec.cross_section_xz,
        stations,
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


def _build_stage10_5_modern_permanent_way_scene_objects(
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
        "contact_rail_bracket": "Brackets",
        "contact_rail_insulator": "Insulators",
        "contact_rail_fastening_unit": "FasteningUnits",
        "contact_rail_attachment_dowels": "SupportDowels",
        "contact_rail_support_hood": "SupportHoods",
    }

    for event_index, chainage in enumerate(chainages):
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
        midpoint = 0.5 * (start_chainage + end_chainage)
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
        mesh = build_annular_shell_sweep(
            profile,
            tuple(
                (
                    station.offset_x_m,
                    station.world_y_m,
                    station.offset_z_m,
                )
                for station in clipped
            ),
            angular_segments=96,
            cap_start=math.isclose(start_chainage, 0.0, abs_tol=1e-12),
            cap_end=math.isclose(end_chainage, total, abs_tol=1e-12),
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
                reconstruction="stage10_4_moscow_smooth_concentric_shell",
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
                    "circumferentialSegmentSurfaceMode": (
                        profile.civil_segment_surface_mode
                    ),
                    "coarseSegmentCountReference": 11,
                    "coarseSegmentCountIsGeometry": False,
                    "seriesAccurateTubingLOD0": False,
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
    keep_stage8_ring_ancillary: bool = False
    keep_prescribed_outer_joint_solids: bool = False
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
        if (
            self.moscow_stage != "10.5"
            and self.moscow_service_preset == "modern"
        ):
            raise ValueError(
                "modern Moscow service preset is currently bounded to Stage 10.5"
            )

    @property
    def resolved_moscow_service_preset(self) -> str:
        if self.moscow_profile is None:
            return "none"
        if self.moscow_service_preset == "auto":
            return "modern" if self.moscow_stage == "10.5" else "legacy"
        return self.moscow_service_preset


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
    config: ProductionConfig | None = None,
) -> ProductionTunnelBuild:
    config = config or ProductionConfig()
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

    stage10_4_civil_rings: tuple[SceneObject, ...] = ()
    if (
        config.moscow_profile is not None
        and config.moscow_stage in {"10.4", "10.5"}
    ):
        stage10_4_civil_rings = _build_stage10_4_civil_shell_objects(
            profile=config.moscow_profile,
            namespace=config.namespace,
            assembly=source_build.assembly,
            stations=stations,
            label_policy=source_scene.label_policy,
        )
        objects.extend(stage10_4_civil_rings)

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
                    "implemented_stage10_4_smooth_concentric_shell"
                    if config.moscow_stage in {"10.4", "10.5"}
                    else "deferred_to_stage10_4"
                ),
                "walkwayStatus": (
                    "implemented_stage10_4_source_backed_geometry"
                    if config.moscow_stage in {"10.4", "10.5"}
                    else "deferred_to_stage10_4"
                ),
                "nonRailInfrastructureStatus": (
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
                "moscowCivilRingCount": (
                    len(stage10_4_civil_rings)
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

    effective_include_bolts = include_bolts and not (
        production_config is not None
        and production_config.moscow_profile is not None
        and production_config.moscow_stage in {"10.4", "10.5"}
    )
    source = build_procedural_nominal_tunnel(
        ring_config=ring_config,
        assembly_config=assembly_config,
        surface_meshing=surface_meshing,
        include_bolts=effective_include_bolts,
        include_ancillary=False,
        include_prescribed_joint_solids=(
            production_config.keep_prescribed_outer_joint_solids
            if production_config is not None
            else False
        ),
        label_policy=label_policy,
        seed=seed,
    )
    return build_production_scene(
        source,
        ancillary=ancillary,
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
    while start_chainage < total - 1e-12:
        end_chainage = min(total, start_chainage + chunk_length_m)
        ring_ids = tuple(
            i
            for i in range(assembly.config.n_rings)
            if start_chainage <= (i + 0.5) * L < end_chainage
            or (
                math.isclose(end_chainage, total, abs_tol=1e-12)
                and math.isclose((i + 0.5) * L, end_chainage, abs_tol=1e-12)
            )
        )
        chunks.append(
            ChunkDescriptor(cid, start_chainage, end_chainage, ring_ids)
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
    return SceneObject(
        name=obj.name,
        vertices=tuple((x + dx, y + dy, z + dz) for x, y, z in obj.vertices),
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


def build_chunk_scene_packages(
    production: ProductionTunnelBuild,
    *,
    chunk_length_m: float,
    boundary_policy: ChunkBoundaryPolicy | str = ChunkBoundaryPolicy.RING_ALIGNED,
    localize_coordinates: bool = False,
) -> tuple[ScenePackage, ...]:
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

    packages: list[ScenePackage] = []
    for chunk in chunks:
        ring_id_set = set(chunk.ring_ids)
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
            for obj in ring_objects
            if obj.ring_id in ring_id_set
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
            for obj in periodic_objects
            if _event_chainage_belongs_to_chunk(
                float(obj.extra_properties["eventChainageM"]),
                chunk,
                total_length_m=total,
            )
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

        packages.append(
            ScenePackage(
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
        )
    return tuple(packages)


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
        front_y = (obj.ring_id - 0.5) * ring_width_m - origin_y
        back_y = (obj.ring_id + 0.5) * ring_width_m - origin_y
        strip_front = obj.ring_id > 0
        strip_back = obj.ring_id < global_max_ring_id

        kept: list[Face] = []
        removed = 0
        for face in obj.faces:
            ys = [obj.vertices[index][1] for index in face]
            on_front = strip_front and all(
                abs(y - front_y) <= tolerance_m for y in ys
            )
            on_back = strip_back and all(
                abs(y - back_y) <= tolerance_m for y in ys
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
