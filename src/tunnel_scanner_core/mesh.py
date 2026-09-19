from __future__ import annotations

from dataclasses import dataclass
import math

from .angles import RingAngles, SegmentAngularExtent, angular_extents
from .config import RingConfig


Vec3 = tuple[float, float, float]
Face = tuple[int, ...]


@dataclass(frozen=True)
class SegmentMesh:
    name: str
    kind: str
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    angular_extent: SegmentAngularExtent


@dataclass(frozen=True)
class RingMesh:
    config: RingConfig
    angles: RingAngles
    segments: tuple[SegmentMesh, ...]


def _point(radius: float, alpha_deg: float, y: float) -> Vec3:
    """alpha=0 at crown (+Z), positive toward +X."""
    a = math.radians(alpha_deg)
    return (radius * math.sin(a), y, radius * math.cos(a))


def build_hexahedral_segment(config: RingConfig, extent: SegmentAngularExtent) -> SegmentMesh:
    """Build the eight-corner segment representation described in the paper.

    This intentionally uses planar quad faces between the eight corner points.
    Curved/tessellated intrados and extrados are a later stage because the paper
    explicitly describes each base segment as a hexahedron with 8 vertices.
    """
    r = config.inner_radius_m
    R = config.outer_radius_m
    yf = -0.5 * config.width_m
    yb = +0.5 * config.width_m

    # Corner convention chosen to match the paper's face grouping:
    # front face = 0,1,4,5; back face = 2,3,6,7.
    vertices: tuple[Vec3, ...] = (
        _point(r, extent.front_start_deg, yf),  # 0 inner/front/start
        _point(r, extent.front_end_deg, yf),    # 1 inner/front/end
        _point(r, extent.back_start_deg, yb),   # 2 inner/back/start
        _point(r, extent.back_end_deg, yb),     # 3 inner/back/end
        _point(R, extent.front_start_deg, yf),  # 4 outer/front/start
        _point(R, extent.front_end_deg, yf),    # 5 outer/front/end
        _point(R, extent.back_start_deg, yb),   # 6 outer/back/start
        _point(R, extent.back_end_deg, yb),     # 7 outer/back/end
    )

    # Manifold hexahedron connectivity. Winding is documented here but will be
    # rechecked against Blender normal conventions during the Blender stage.
    faces: tuple[Face, ...] = (
        (0, 2, 3, 1),  # intrados
        (4, 5, 7, 6),  # extrados
        (0, 4, 6, 2),  # start radial joint face
        (1, 3, 7, 5),  # end radial joint face
        (0, 1, 5, 4),  # front circumferential face
        (2, 6, 7, 3),  # back circumferential face
    )
    return SegmentMesh(extent.name, extent.kind, vertices, faces, extent)


def build_ring_mesh(config: RingConfig, angles: RingAngles) -> RingMesh:
    angles.validate()
    extents = angular_extents(angles)
    segments = tuple(build_hexahedral_segment(config, e) for e in extents)
    return RingMesh(config=config, angles=angles, segments=segments)
