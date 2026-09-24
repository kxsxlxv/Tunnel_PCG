from __future__ import annotations

"""Engine-neutral robust CSG used for one-time canonical asset baking."""

from typing import Sequence

import numpy as np
from manifold3d import Error, Manifold, Mesh64

from .mesh import Face, Vec3


def triangulate_faces(
    faces: Sequence[Face],
) -> tuple[tuple[int, int, int], ...]:
    """Fan-triangulate convex production faces without moving vertices."""
    triangles: list[tuple[int, int, int]] = []
    for face in faces:
        if len(face) < 3:
            raise ValueError("mesh face must contain at least three vertices")
        anchor = int(face[0])
        for index in range(1, len(face) - 1):
            triangles.append(
                (anchor, int(face[index]), int(face[index + 1]))
            )
    return tuple(triangles)


def _as_manifold(
    vertices: Sequence[Vec3],
    faces: Sequence[Face],
    *,
    name: str,
) -> Manifold:
    if not vertices or not faces:
        raise ValueError(f"{name}: manifold input must not be empty")
    mesh = Mesh64(
        vert_properties=np.ascontiguousarray(
            np.asarray(vertices, dtype=np.float64)
        ),
        tri_verts=np.ascontiguousarray(
            np.asarray(triangulate_faces(faces), dtype=np.uint64)
        ),
    )
    solid = Manifold(mesh)
    if solid.status() != Error.NoError:
        raise ValueError(
            f"{name}: manifold import failed with status {solid.status()}"
        )
    if solid.is_empty():
        raise ValueError(f"{name}: manifold input unexpectedly empty")
    return solid


def subtract_closed_meshes(
    target_vertices: Sequence[Vec3],
    target_faces: Sequence[Face],
    cutters: Sequence[tuple[Sequence[Vec3], Sequence[Face]]],
    *,
    name: str = "mesh_difference",
) -> tuple[tuple[Vec3, ...], tuple[Face, ...]]:
    """Bake a set of closed cutters into one closed target mesh.

    Cutters are unioned once, then one robust difference is evaluated.  This is
    intended for canonical asset authoring: the resulting triangle mesh is
    shared by every engine instance, so no per-instance Boolean remains.
    """
    target = _as_manifold(
        target_vertices,
        target_faces,
        name=f"{name}:target",
    )
    if cutters:
        cutter_solids = [
            _as_manifold(vertices, faces, name=f"{name}:cutter:{index}")
            for index, (vertices, faces) in enumerate(cutters)
        ]
        cutter_union = Manifold.compose(cutter_solids)
        if cutter_union.status() != Error.NoError:
            raise ValueError(
                f"{name}: cutter union failed with status "
                f"{cutter_union.status()}"
            )
        target = target - cutter_union

    if target.status() != Error.NoError:
        raise ValueError(
            f"{name}: Boolean difference failed with status {target.status()}"
        )
    if target.is_empty():
        raise ValueError(f"{name}: Boolean result unexpectedly empty")

    mesh = target.to_mesh64()
    raw_vertices = np.asarray(mesh.vert_properties)
    raw_faces = np.asarray(mesh.tri_verts)
    vertices = tuple(
        (float(row[0]), float(row[1]), float(row[2]))
        for row in raw_vertices
    )
    faces = tuple(
        (int(row[0]), int(row[1]), int(row[2]))
        for row in raw_faces
    )
    if not vertices or not faces:
        raise ValueError(f"{name}: Boolean result unexpectedly empty")
    return vertices, faces
