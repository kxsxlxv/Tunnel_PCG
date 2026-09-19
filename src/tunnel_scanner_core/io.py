from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path

from .mesh import RingMesh


def write_ring_json(ring: RingMesh, path: str | Path) -> Path:
    path = Path(path)
    data = {
        "coordinate_convention": {
            "longitudinal_axis": "+Y",
            "cross_section": "XZ",
            "alpha_zero": "+Z crown",
            "alpha_positive": "toward +X",
        },
        "config": asdict(ring.config),
        "angle_mode": ring.angles.mode.value,
        "angles": [asdict(s) | {"center_deg": s.center_deg} for s in ring.angles.segments],
        "segments": [
            {
                "name": s.name,
                "kind": s.kind,
                "angular_extent": asdict(s.angular_extent),
                "vertices": s.vertices,
                "faces": s.faces,
            }
            for s in ring.segments
        ],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_ring_obj(ring: RingMesh, path: str | Path) -> Path:
    path = Path(path)
    lines = [
        "# Tunnel Scanner ring",
        "# +Y longitudinal, alpha=0 at +Z crown, alpha positive toward +X",
    ]
    base = 1
    for segment in ring.segments:
        lines.append(f"o {segment.name}")
        for x, y, z in segment.vertices:
            lines.append(f"v {x:.9f} {y:.9f} {z:.9f}")
        for face in segment.faces:
            indices = " ".join(str(base + i) for i in face)
            lines.append(f"f {indices}")
        base += len(segment.vertices)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_deformation_json(deformation, path: str | Path) -> Path:
    path = Path(path)
    data = {
        "indexing": deformation.indexing.value,
        "attempts": deformation.attempts,
        "closure": {
            "final_origin_m": deformation.final_origin,
            "final_theta_deg": deformation.final_theta_deg,
            "translation_error_m": deformation.translation_closure_error_m,
            "angular_error_deg": deformation.angular_closure_error_deg,
        },
        "steps": [asdict(step) for step in deformation.steps],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_deformed_ring_json(deformed, path: str | Path) -> Path:
    path = Path(path)
    closure_k = None
    try:
        from .deformed_mesh import derive_closure_k_transform
        closure_k = asdict(derive_closure_k_transform(deformed.base_ring, deformed.deformation))
    except Exception as exc:  # diagnostic only; never hide main geometry export
        closure_k = {"error": str(exc)}

    data = {
        "coordinate_convention": {
            "longitudinal_axis": "+Y",
            "cross_section": "XZ",
            "alpha_zero": "+Z crown",
            "alpha_positive": "toward +X",
        },
        "recurrence_to_mesh_rotation_deg": deformed.recurrence_to_mesh_rotation_deg,
        "segment_transforms": [asdict(t) for t in deformed.segment_transforms],
        "closure_k_transform": closure_k,
        "segments": [
            {
                "name": s.name,
                "kind": s.kind,
                "vertices": s.vertices,
                "faces": s.faces,
            }
            for s in deformed.segments
        ],
        "displacement_joints": [asdict(j) for j in deformed.displacement_joints],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_deformed_ring_obj(
    deformed,
    path: str | Path,
    *,
    include_displacement_joints: bool = True,
) -> Path:
    path = Path(path)
    lines = [
        "# Tunnel Scanner Stage 3 deformed ring",
        "# segments are rigid transforms; joint_* objects bridge displacement-induced gaps",
    ]
    base = 1
    for segment in deformed.segments:
        lines.append(f"o {segment.name}")
        for x, y, z in segment.vertices:
            lines.append(f"v {x:.9f} {y:.9f} {z:.9f}")
        for face in segment.faces:
            lines.append("f " + " ".join(str(base + i) for i in face))
        base += len(segment.vertices)

    if include_displacement_joints:
        for joint in deformed.displacement_joints:
            lines.append(f"o {joint.name}")
            for x, y, z in joint.vertices:
                lines.append(f"v {x:.9f} {y:.9f} {z:.9f}")
            for face in joint.faces:
                lines.append("f " + " ".join(str(base + i) for i in face))
            base += len(joint.vertices)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def write_prescribed_joints_json(ring, joints, path: str | Path) -> Path:
    """Export Stage-4 nominal joint reconstruction and its assumptions."""
    path = Path(path)
    data = {
        "stage": 4,
        "joint_config": asdict(joints.config),
        "reconstruction_notes": {
            "radial": (
                "paper-literal outer-rib reconstruction using R_joi=R and "
                "R_joi=R+t_joi with theta_joi=w_joi/R_joi"
            ),
            "circumferential": (
                "provisional outer-collar extrapolation; the paper does not "
                "publish an equivalent vertex construction"
            ),
            "sensor_facing_intrados_groove": "not inferred / not implemented",
        },
        "ring_config": asdict(ring.config),
        "radial_joints": [asdict(j) for j in joints.radial],
        "circumferential_front": [asdict(j) for j in joints.circumferential_front],
        "circumferential_back": [asdict(j) for j in joints.circumferential_back],
    }
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


def write_prescribed_joints_obj(
    ring,
    joints,
    path: str | Path,
    *,
    include_segments: bool = True,
    include_radial: bool = True,
    include_circumferential_front: bool = False,
    include_circumferential_back: bool = True,
) -> Path:
    """Write a diagnostic OBJ for inspecting Stage-4 joint geometry."""
    path = Path(path)
    lines = [
        "# Tunnel Scanner Stage 4 prescribed-joint reconstruction",
        "# radial joints: paper-literal outer ribs at R..R+t_joi",
        "# circumferential joints: provisional outer-collar extrapolation",
    ]
    base = 1

    def emit(name, vertices, faces):
        nonlocal base
        lines.append(f"o {name}")
        for x, y, z in vertices:
            lines.append(f"v {x:.9f} {y:.9f} {z:.9f}")
        for face in faces:
            lines.append("f " + " ".join(str(base + i) for i in face))
        base += len(vertices)

    if include_segments:
        for segment in ring.segments:
            emit(segment.name, segment.vertices, segment.faces)

    if include_radial:
        for joint in joints.radial:
            emit(joint.name, joint.vertices, joint.faces)

    if include_circumferential_front:
        for joint in joints.circumferential_front:
            emit(joint.name, joint.vertices, joint.faces)

    if include_circumferential_back:
        for joint in joints.circumferential_back:
            emit(joint.name, joint.vertices, joint.faces)

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path
