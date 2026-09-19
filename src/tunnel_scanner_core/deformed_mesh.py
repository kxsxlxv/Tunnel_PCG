from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .angles import SegmentAngularExtent
from .deformation import RingDeformation
from .mesh import Face, RingMesh, SegmentMesh, Vec3


Vec2 = tuple[float, float]


@dataclass(frozen=True)
class SegmentRigidTransform:
    """Rigid XZ transform applied to one Stage-1 segment mesh."""

    segment_name: str
    step_index: int
    rotation_deg: float
    center_offset_xz_m: Vec2
    entry_alpha_deg: float


@dataclass(frozen=True)
class JointGapMesh:
    """Hexahedral bridge between the deformed faces of adjacent segments.

    This is the *displacement-induced* joint mesh described in Section 2.2. It
    does not yet include the paper's prescribed 35-60 mm design joint width.
    """

    name: str
    previous_segment: str
    next_segment: str
    dislocation_m: float
    relative_rotation_deg: float
    vertices: tuple[Vec3, ...]
    faces: tuple[Face, ...]
    corner_separations_m: tuple[float, float, float, float]

    @property
    def max_corner_separation_m(self) -> float:
        return max(self.corner_separations_m)


@dataclass(frozen=True)
class DeformedRingMesh:
    base_ring: RingMesh
    deformation: RingDeformation
    segment_transforms: tuple[SegmentRigidTransform, ...]
    segments: tuple[SegmentMesh, ...]
    displacement_joints: tuple[JointGapMesh, ...]
    recurrence_to_mesh_rotation_deg: float

    def segment_by_name(self, name: str) -> SegmentMesh:
        for segment in self.segments:
            if segment.name == name:
                return segment
        raise KeyError(name)

    def transform_by_name(self, name: str) -> SegmentRigidTransform:
        for transform in self.segment_transforms:
            if transform.segment_name == name:
                return transform
        raise KeyError(name)


def _rot2_deg(angle_deg: float) -> np.ndarray:
    a = math.radians(angle_deg)
    c = math.cos(a)
    s = math.sin(a)
    return np.array(((c, -s), (s, c)), dtype=float)


def _mean_start_alpha(extent: SegmentAngularExtent) -> float:
    return 0.5 * (extent.front_start_deg + extent.back_start_deg)


def _standard_ray_angle_from_alpha(alpha_deg: float) -> float:
    """Stage-1 alpha (0 at +Z, positive toward +X) -> atan2(z,x) degrees."""
    return 90.0 - alpha_deg


def recurrence_to_mesh_rotation_deg(ring: RingMesh) -> float:
    """Constant rotation mapping the paper recurrence XZ frame to Stage-1 XZ.

    The recurrence starts theta_0=180 deg at the K->B1 interface. Stage 1 puts
    the same interface at B1's mean start alpha. Since a Stage-1 alpha ray has
    standard Cartesian angle 90-alpha, the required basis rotation is:
        delta = (90 - alpha_B1_start) - 180 = -90 - alpha_B1_start.
    """
    b1 = next(s for s in ring.segments if s.name == "B1")
    alpha = _mean_start_alpha(b1.angular_extent)
    return -90.0 - alpha


def _map_recurrence_point(point: Vec2, delta_deg: float) -> np.ndarray:
    return _rot2_deg(delta_deg) @ np.asarray(point, dtype=float)


def _wrap_deg(angle: float) -> float:
    return (angle + 180.0) % 360.0 - 180.0


def derive_segment_transforms(
    ring: RingMesh,
    deformation: RingDeformation,
) -> tuple[tuple[SegmentRigidTransform, ...], float]:
    """Derive a unique rigid transform for every physical segment.

    The crucial Stage-3 interpretation is that O(i) is the local ring/curvature
    centre of the transformed target segment. For each recurrence step, the
    vector from O(i) to the shared rotation centre gives the transformed entry
    radial direction. Comparing it with the target segment's undeformed entry
    radial direction yields the rigid rotation. Translation is simply O(i),
    after a constant basis rotation that aligns theta_0 with K->B1.

    The final i=N K state is diagnostic only; it must reproduce the identity K
    transform. The physical K segment itself remains fixed at step index 0.
    """
    if len(deformation.steps) != len(ring.segments):
        raise ValueError("deformation/ring segment count mismatch")

    extents = {s.name: s.angular_extent for s in ring.segments}
    delta_deg = recurrence_to_mesh_rotation_deg(ring)

    transforms: list[SegmentRigidTransform] = [
        SegmentRigidTransform(
            segment_name="K",
            step_index=0,
            rotation_deg=0.0,
            center_offset_xz_m=(0.0, 0.0),
            entry_alpha_deg=_mean_start_alpha(extents["K"]),
        )
    ]

    for step in deformation.steps[:-1]:
        extent = extents[step.segment_name]
        entry_alpha = _mean_start_alpha(extent)
        base_ray_angle = _standard_ray_angle_from_alpha(entry_alpha)

        center = _map_recurrence_point(step.origin_after, delta_deg)
        pivot = _map_recurrence_point(step.rotation_center, delta_deg)
        radial = pivot - center
        norm = float(np.linalg.norm(radial))
        if norm <= 1e-12:
            raise ValueError(f"degenerate radial direction at step {step.index}")
        current_ray_angle = math.degrees(math.atan2(radial[1], radial[0]))
        rotation_deg = _wrap_deg(current_ray_angle - base_ray_angle)

        transforms.append(
            SegmentRigidTransform(
                segment_name=step.segment_name,
                step_index=step.index,
                rotation_deg=rotation_deg,
                center_offset_xz_m=(float(center[0]), float(center[1])),
                entry_alpha_deg=entry_alpha,
            )
        )

    # Preserve the ring's canonical physical order rather than traversal order.
    by_name = {t.segment_name: t for t in transforms}
    ordered = tuple(by_name[s.name] for s in ring.segments)
    return ordered, delta_deg


def derive_closure_k_transform(
    ring: RingMesh,
    deformation: RingDeformation,
) -> SegmentRigidTransform:
    """Derive the duplicate final-K transform used only for closure validation."""
    step = deformation.steps[-1]
    if step.segment_name != "K":
        raise ValueError("final deformation step must return to K")
    k = next(s for s in ring.segments if s.name == "K")
    delta_deg = recurrence_to_mesh_rotation_deg(ring)
    entry_alpha = _mean_start_alpha(k.angular_extent)
    base_ray_angle = _standard_ray_angle_from_alpha(entry_alpha)
    center = _map_recurrence_point(step.origin_after, delta_deg)
    pivot = _map_recurrence_point(step.rotation_center, delta_deg)
    radial = pivot - center
    current_ray_angle = math.degrees(math.atan2(radial[1], radial[0]))
    rotation_deg = _wrap_deg(current_ray_angle - base_ray_angle)
    return SegmentRigidTransform(
        segment_name="K",
        step_index=step.index,
        rotation_deg=rotation_deg,
        center_offset_xz_m=(float(center[0]), float(center[1])),
        entry_alpha_deg=entry_alpha,
    )


def _transform_vertex(v: Vec3, transform: SegmentRigidTransform) -> Vec3:
    x, y, z = v
    xz = _rot2_deg(transform.rotation_deg) @ np.array((x, z), dtype=float)
    xz += np.asarray(transform.center_offset_xz_m, dtype=float)
    return (float(xz[0]), float(y), float(xz[1]))


def apply_segment_transform(
    segment: SegmentMesh,
    transform: SegmentRigidTransform,
) -> SegmentMesh:
    if segment.name != transform.segment_name:
        raise ValueError("segment/transform name mismatch")
    vertices = tuple(_transform_vertex(v, transform) for v in segment.vertices)
    return SegmentMesh(
        name=segment.name,
        kind=segment.kind,
        vertices=vertices,
        faces=segment.faces,
        angular_extent=segment.angular_extent,
    )


def _dist(a: Vec3, b: Vec3) -> float:
    return math.dist(a, b)


def _build_gap(
    previous: SegmentMesh,
    current: SegmentMesh,
    *,
    step_dislocation_m: float,
    step_rotation_deg: float,
) -> JointGapMesh:
    # Corresponding corners of previous end face and current start face:
    # inner/front, inner/back, outer/front, outer/back.
    p_if, p_ib, p_of, p_ob = (
        previous.vertices[1],
        previous.vertices[3],
        previous.vertices[5],
        previous.vertices[7],
    )
    c_if, c_ib, c_of, c_ob = (
        current.vertices[0],
        current.vertices[2],
        current.vertices[4],
        current.vertices[6],
    )

    # Eight-vertex bridge. The topology mirrors the Stage-1 hexahedron, but its
    # start/end faces are the actual neighbouring segment boundary surfaces.
    vertices: tuple[Vec3, ...] = (
        p_if, c_if,
        p_ib, c_ib,
        p_of, c_of,
        p_ob, c_ob,
    )
    faces: tuple[Face, ...] = (
        (0, 2, 3, 1),  # intrados bridge
        (4, 5, 7, 6),  # extrados bridge
        (0, 4, 6, 2),  # previous segment boundary
        (1, 3, 7, 5),  # current segment boundary
        (0, 1, 5, 4),  # front
        (2, 6, 7, 3),  # back
    )

    # Depending on the sign of relative displacement, the same correspondence
    # topology can initially wind inward. Normalize non-degenerate joint meshes
    # to positive signed volume so Blender/OBJ face normals are deterministic.
    def signed_volume() -> float:
        total = 0.0
        vv = [np.asarray(v, dtype=float) for v in vertices]
        for q in faces:
            for i0, i1, i2 in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
                total += float(np.dot(vv[i0], np.cross(vv[i1], vv[i2]))) / 6.0
        return total

    if signed_volume() < -1e-15:
        faces = tuple((face[0], *reversed(face[1:])) for face in faces)

    separations = (
        _dist(p_if, c_if),
        _dist(p_ib, c_ib),
        _dist(p_of, c_of),
        _dist(p_ob, c_ob),
    )
    return JointGapMesh(
        name=f"joint_{previous.name}_{current.name}",
        previous_segment=previous.name,
        next_segment=current.name,
        dislocation_m=step_dislocation_m,
        relative_rotation_deg=step_rotation_deg,
        vertices=vertices,
        faces=faces,
        corner_separations_m=separations,
    )


def build_deformed_ring_mesh(
    ring: RingMesh,
    deformation: RingDeformation,
) -> DeformedRingMesh:
    """Apply the recurrence states to Stage-1 meshes and build joint-gap meshes."""
    transforms, delta_deg = derive_segment_transforms(ring, deformation)
    t_by_name = {t.segment_name: t for t in transforms}
    deformed = tuple(
        apply_segment_transform(segment, t_by_name[segment.name])
        for segment in ring.segments
    )
    s_by_name = {s.name: s for s in deformed}

    # Recurrence traversal defines each interface from previous -> target.
    previous_name = "K"
    gaps: list[JointGapMesh] = []
    for step in deformation.steps:
        current_name = step.segment_name
        gaps.append(
            _build_gap(
                s_by_name[previous_name],
                s_by_name[current_name],
                step_dislocation_m=step.dislocation_m,
                step_rotation_deg=step.rotation_deg,
            )
        )
        previous_name = current_name

    return DeformedRingMesh(
        base_ring=ring,
        deformation=deformation,
        segment_transforms=transforms,
        segments=deformed,
        displacement_joints=tuple(gaps),
        recurrence_to_mesh_rotation_deg=delta_deg,
    )
