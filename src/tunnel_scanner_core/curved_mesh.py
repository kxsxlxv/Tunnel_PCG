from __future__ import annotations

from dataclasses import dataclass
import math

from .angles import SegmentAngularExtent
from .deformed_mesh import SegmentRigidTransform
from .mesh import Face, RingMesh, SegmentMesh, Vec3
from .joints import CircumferentialJointMesh


@dataclass(frozen=True)
class SurfaceMeshingConfig:
    """Adaptive tessellation policy for LiDAR/render-facing lining surfaces.

    The Stage-1 eight-corner hexahedron remains the analytical/control mesh.
    This configuration controls only a derived cylindrical surface mesh.

    `max_sagitta_m` is treated conservatively: the largest angular separation
    across a tessellated cell diagonal is constrained so its circular sagitta on
    the segment outer radius does not exceed the requested value. This covers
    both circumferential discretization and front/back segment taper.
    """

    max_sagitta_m: float = 0.002
    min_subdivisions: int = 1
    max_subdivisions: int = 4096

    def __post_init__(self) -> None:
        if not math.isfinite(self.max_sagitta_m) or self.max_sagitta_m <= 0.0:
            raise ValueError("max_sagitta_m must be finite and positive")
        if self.min_subdivisions < 1:
            raise ValueError("min_subdivisions must be >= 1")
        if self.max_subdivisions < self.min_subdivisions:
            raise ValueError("max_subdivisions must be >= min_subdivisions")


@dataclass(frozen=True)
class CurvedSegmentMesh:
    """Tessellated cylindrical-prism representation of one lining segment."""

    name: str
    kind: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    angular_extent: SegmentAngularExtent
    circumferential_subdivisions: int
    longitudinal_subdivisions: int
    requested_max_sagitta_m: float
    achieved_max_sagitta_m: float

    @property
    def subdivisions(self) -> int:
        return self.circumferential_subdivisions

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def face_count(self) -> int:
        return len(self.faces)


@dataclass(frozen=True)
class CurvedRingMesh:
    """Derived render/sensor mesh for a Stage-1 analytical RingMesh."""

    analytical_ring: RingMesh
    meshing: SurfaceMeshingConfig
    segments: tuple[CurvedSegmentMesh, ...]

    def segment_by_name(self, name: str) -> CurvedSegmentMesh:
        for segment in self.segments:
            if segment.name == name:
                return segment
        raise KeyError(name)


@dataclass(frozen=True)
class CurvedCollarMesh:
    """Curved render representation of a Stage-4 circumferential collar piece."""

    name: str
    segment_name: str
    side: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    circumferential_subdivisions: int
    requested_max_sagitta_m: float
    achieved_max_sagitta_m: float


def _point(radius: float, alpha_deg: float, y: float) -> Vec3:
    a = math.radians(alpha_deg)
    return (radius * math.sin(a), y, radius * math.cos(a))


def max_angular_step_deg(radius_m: float, max_sagitta_m: float) -> float:
    """Largest circular chord angle whose sagitta does not exceed tolerance."""
    if not math.isfinite(radius_m) or radius_m <= 0.0:
        raise ValueError("radius_m must be finite and positive")
    if not math.isfinite(max_sagitta_m) or max_sagitta_m <= 0.0:
        raise ValueError("max_sagitta_m must be finite and positive")
    c = 1.0 - max_sagitta_m / radius_m
    c = min(1.0, max(-1.0, c))
    return math.degrees(2.0 * math.acos(c))


def required_circle_subdivisions(
    radius_m: float,
    max_sagitta_m: float,
    *,
    min_subdivisions: int = 3,
    max_subdivisions: int = 4096,
) -> int:
    """Minimum full-circle chord count satisfying a radial sagitta bound."""
    if min_subdivisions < 3:
        raise ValueError("min_subdivisions must be >=3")
    if max_subdivisions < min_subdivisions:
        raise ValueError("max_subdivisions must be >= min_subdivisions")
    step_limit_deg = max_angular_step_deg(radius_m, max_sagitta_m)
    if step_limit_deg <= 0.0:
        raise ValueError("computed angular step is non-positive")
    required = max(
        min_subdivisions,
        int(math.ceil(360.0 / step_limit_deg)),
    )
    if required > max_subdivisions:
        raise ValueError(
            f"circle cannot meet sagitta tolerance {max_sagitta_m:g} m "
            f"within max_subdivisions={max_subdivisions}"
        )
    if sagitta_m(radius_m, 360.0 / required) > max_sagitta_m + 1e-12:
        raise AssertionError("computed circle subdivision exceeds sagitta tolerance")
    return required


def sagitta_m(radius_m: float, angular_step_deg: float) -> float:
    if radius_m <= 0.0:
        raise ValueError("radius_m must be positive")
    a = math.radians(abs(angular_step_deg))
    return radius_m * (1.0 - math.cos(0.5 * a))


def _spans(extent: SegmentAngularExtent) -> tuple[float, float]:
    circumferential = max(abs(extent.front_span_deg), abs(extent.back_span_deg))
    twist = max(
        abs(extent.back_start_deg - extent.front_start_deg),
        abs(extent.back_end_deg - extent.front_end_deg),
    )
    return circumferential, twist


def required_grid_subdivisions(
    outer_radius_m: float,
    extent: SegmentAngularExtent,
    meshing: SurfaceMeshingConfig,
) -> tuple[int, int]:
    """Choose (circumferential, longitudinal) subdivisions conservatively."""
    span_u, span_v = _spans(extent)
    if span_u <= 1e-14:
        raise ValueError(f"{extent.name}: degenerate angular span")
    limit = max_angular_step_deg(outer_radius_m, meshing.max_sagitta_m)
    if limit <= 0.0:
        raise ValueError("computed angular step is non-positive")

    min_n = meshing.min_subdivisions
    max_n = meshing.max_subdivisions

    if span_v <= 1e-15:
        nv_start = min_n
    else:
        nv_start = max(min_n, int(math.floor(span_v / limit)) + 1)

    best: tuple[int, int, int, int] | None = None
    nv = nv_start
    while nv <= max_n:
        dv = span_v / nv
        allowance = limit - dv
        if allowance > 1e-15:
            nu = max(min_n, int(math.ceil(span_u / allowance)))
            if nu <= max_n:
                cells = nu * nv
                vertices_proxy = (nu + 1) * (nv + 1)
                candidate = (cells, vertices_proxy, nu, nv)
                if best is None or candidate < best:
                    best = candidate
        if best is not None and nv >= best[0]:
            break
        nv += 1

    if best is None:
        raise ValueError(
            f"{extent.name}: cannot meet sagitta tolerance {meshing.max_sagitta_m:g} m "
            f"within max_subdivisions={max_n}"
        )
    return best[2], best[3]


def required_subdivisions(
    outer_radius_m: float,
    extent: SegmentAngularExtent,
    meshing: SurfaceMeshingConfig,
) -> int:
    return required_grid_subdivisions(outer_radius_m, extent, meshing)[0]


def _signed_volume(vertices: tuple[Vec3, ...], faces: tuple[Face, ...]) -> float:
    total = 0.0
    for face in faces:
        p0 = vertices[face[0]]
        for j in range(1, len(face) - 1):
            p1 = vertices[face[j]]
            p2 = vertices[face[j + 1]]
            cx = p1[1] * p2[2] - p1[2] * p2[1]
            cy = p1[2] * p2[0] - p1[0] * p2[2]
            cz = p1[0] * p2[1] - p1[1] * p2[0]
            total += (p0[0] * cx + p0[1] * cy + p0[2] * cz) / 6.0
    return total


def _flip_faces(faces: tuple[Face, ...]) -> tuple[Face, ...]:
    return tuple(tuple(reversed(face)) for face in faces)


def build_curved_segment_mesh(
    analytical_segment: SegmentMesh,
    *,
    inner_radius_m: float,
    outer_radius_m: float,
    width_m: float,
    meshing: SurfaceMeshingConfig | None = None,
) -> CurvedSegmentMesh:
    """Derive a curved cylindrical segment from an analytical Stage-1 segment."""
    meshing = meshing or SurfaceMeshingConfig()
    if inner_radius_m <= 0.0 or outer_radius_m <= inner_radius_m:
        raise ValueError("radii must satisfy 0 < inner_radius_m < outer_radius_m")
    if width_m <= 0.0:
        raise ValueError("width_m must be positive")

    e = analytical_segment.angular_extent
    nu, nv = required_grid_subdivisions(outer_radius_m, e, meshing)
    yf = -0.5 * width_m

    vertices: list[Vec3] = []
    for iv in range(nv + 1):
        v = iv / nv
        y = yf + v * width_m
        start = e.front_start_deg + v * (e.back_start_deg - e.front_start_deg)
        end = e.front_end_deg + v * (e.back_end_deg - e.front_end_deg)
        span = end - start
        for iu in range(nu + 1):
            u = iu / nu
            alpha = start + u * span
            vertices.append(_point(inner_radius_m, alpha, y))
            vertices.append(_point(outer_radius_m, alpha, y))

    def idx(iv: int, iu: int, layer: int) -> int:
        return 2 * (iv * (nu + 1) + iu) + layer

    faces: list[Face] = []
    for iv in range(nv):
        for iu in range(nu):
            jv = iv + 1
            ju = iu + 1
            faces.append(
                (idx(iv, iu, 0), idx(jv, iu, 0), idx(jv, ju, 0), idx(iv, ju, 0))
            )
            faces.append(
                (idx(iv, iu, 1), idx(iv, ju, 1), idx(jv, ju, 1), idx(jv, iu, 1))
            )

    for iu in range(nu):
        ju = iu + 1
        faces.append((idx(0, iu, 0), idx(0, ju, 0), idx(0, ju, 1), idx(0, iu, 1)))
        faces.append(
            (idx(nv, iu, 0), idx(nv, iu, 1), idx(nv, ju, 1), idx(nv, ju, 0))
        )

    for iv in range(nv):
        jv = iv + 1
        faces.append((idx(iv, 0, 0), idx(iv, 0, 1), idx(jv, 0, 1), idx(jv, 0, 0)))
        faces.append(
            (idx(iv, nu, 0), idx(jv, nu, 0), idx(jv, nu, 1), idx(iv, nu, 1))
        )

    vv = tuple(vertices)
    ff = tuple(faces)
    volume = _signed_volume(vv, ff)
    if abs(volume) <= 1e-15:
        raise ValueError(f"{analytical_segment.name}: curved segment has zero volume")
    if volume < 0.0:
        ff = _flip_faces(ff)

    span_u, span_v = _spans(e)
    du = span_u / nu
    dv = span_v / nv
    conservative_step = du + dv
    achieved = sagitta_m(outer_radius_m, conservative_step)
    if achieved > meshing.max_sagitta_m + 1e-12:
        raise AssertionError(
            f"internal error: achieved conservative sagitta {achieved} exceeds "
            f"requested {meshing.max_sagitta_m}"
        )

    return CurvedSegmentMesh(
        name=analytical_segment.name,
        kind=analytical_segment.kind,
        vertices=vv,
        faces=ff,
        angular_extent=e,
        circumferential_subdivisions=nu,
        longitudinal_subdivisions=nv,
        requested_max_sagitta_m=meshing.max_sagitta_m,
        achieved_max_sagitta_m=achieved,
    )


def build_curved_ring_mesh(
    ring: RingMesh,
    *,
    meshing: SurfaceMeshingConfig | None = None,
) -> CurvedRingMesh:
    meshing = meshing or SurfaceMeshingConfig()
    cfg = ring.config
    segments = tuple(
        build_curved_segment_mesh(
            segment,
            inner_radius_m=cfg.inner_radius_m,
            outer_radius_m=cfg.outer_radius_m,
            width_m=cfg.width_m,
            meshing=meshing,
        )
        for segment in ring.segments
    )
    return CurvedRingMesh(analytical_ring=ring, meshing=meshing, segments=segments)


def build_curved_circumferential_collar_mesh(
    joint: CircumferentialJointMesh,
    *,
    meshing: SurfaceMeshingConfig | None = None,
) -> CurvedCollarMesh:
    """Curve the broad Stage-4 outer-collar piece around the tunnel axis."""
    meshing = meshing or SurfaceMeshingConfig()
    span = joint.alpha_end_deg - joint.alpha_start_deg
    extent = SegmentAngularExtent(
        name=joint.name,
        kind="collar",
        front_start_deg=joint.alpha_start_deg,
        front_end_deg=joint.alpha_end_deg,
        back_start_deg=joint.alpha_start_deg,
        back_end_deg=joint.alpha_end_deg,
    )
    nu, nv = required_grid_subdivisions(joint.cap_radius_m, extent, meshing)
    if nv != 1:
        raise AssertionError("untapered circumferential collar unexpectedly needs nv != 1")

    vertices: list[Vec3] = []
    for i in range(nu + 1):
        u = i / nu
        alpha = joint.alpha_start_deg + u * span
        vertices.extend(
            (
                _point(joint.base_radius_m, alpha, joint.y_inner_m),
                _point(joint.base_radius_m, alpha, joint.y_outer_m),
                _point(joint.cap_radius_m, alpha, joint.y_inner_m),
                _point(joint.cap_radius_m, alpha, joint.y_outer_m),
            )
        )

    def idx(i: int, lane: int) -> int:
        return 4 * i + lane

    faces: list[Face] = []
    for i in range(nu):
        j = i + 1
        faces.append((idx(i, 0), idx(i, 1), idx(j, 1), idx(j, 0)))
        faces.append((idx(i, 2), idx(j, 2), idx(j, 3), idx(i, 3)))
        faces.append((idx(i, 0), idx(j, 0), idx(j, 2), idx(i, 2)))
        faces.append((idx(i, 1), idx(i, 3), idx(j, 3), idx(j, 1)))
    faces.append((idx(0, 0), idx(0, 2), idx(0, 3), idx(0, 1)))
    faces.append((idx(nu, 0), idx(nu, 1), idx(nu, 3), idx(nu, 2)))

    vv = tuple(vertices)
    ff = tuple(faces)
    volume = _signed_volume(vv, ff)
    if abs(volume) <= 1e-15:
        raise ValueError(f"{joint.name}: curved collar has zero volume")
    if volume < 0.0:
        ff = _flip_faces(ff)

    achieved = sagitta_m(joint.cap_radius_m, abs(span) / nu)
    if achieved > meshing.max_sagitta_m + 1e-12:
        raise AssertionError("curved collar exceeds requested sagitta tolerance")
    return CurvedCollarMesh(
        name=joint.name,
        segment_name=joint.segment_name,
        side=joint.side,
        vertices=vv,
        faces=ff,
        circumferential_subdivisions=nu,
        requested_max_sagitta_m=meshing.max_sagitta_m,
        achieved_max_sagitta_m=achieved,
    )


def _rotate_translate_vertex(v: Vec3, transform: SegmentRigidTransform) -> Vec3:
    x, y, z = v
    a = math.radians(transform.rotation_deg)
    c = math.cos(a)
    s = math.sin(a)
    x2 = c * x - s * z + transform.center_offset_xz_m[0]
    z2 = s * x + c * z + transform.center_offset_xz_m[1]
    return (x2, y, z2)


def apply_rigid_transform_to_curved_segment(
    segment: CurvedSegmentMesh,
    transform: SegmentRigidTransform,
) -> CurvedSegmentMesh:
    if segment.name != transform.segment_name:
        raise ValueError("segment/transform name mismatch")
    return CurvedSegmentMesh(
        name=segment.name,
        kind=segment.kind,
        vertices=tuple(_rotate_translate_vertex(v, transform) for v in segment.vertices),
        faces=segment.faces,
        angular_extent=segment.angular_extent,
        circumferential_subdivisions=segment.circumferential_subdivisions,
        longitudinal_subdivisions=segment.longitudinal_subdivisions,
        requested_max_sagitta_m=segment.requested_max_sagitta_m,
        achieved_max_sagitta_m=segment.achieved_max_sagitta_m,
    )
