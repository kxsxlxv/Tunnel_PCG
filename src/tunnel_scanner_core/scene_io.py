from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from .scene import (
    LabelPolicy,
    SceneMode,
    SceneObject,
    ScenePackage,
    scene_object_mesh_prototype_payload,
)


SCENE_SCHEMA_VERSION = 1
PROTOTYPE_SCENE_SCHEMA_VERSION = 2
_MAX_PROTOTYPE_RECONSTRUCTION_ERROR_M = 1e-9


def scene_package_to_dict(
    package: ScenePackage,
    *,
    include_custom_properties: bool = True,
    prototype_instances: bool = False,
) -> dict[str, Any]:
    mesh_prototypes: dict[str, dict[str, Any]] = {}
    prototype_instance_count = 0
    max_reconstruction_error_m = 0.0

    def object_dict(obj: SceneObject) -> dict[str, Any]:
        nonlocal prototype_instance_count, max_reconstruction_error_m
        data = {
            "name": obj.name,
            "objectType": obj.object_type,
            "ringID": obj.ring_id,
            "labelID": obj.label_id,
            "instanceID": obj.instance_id,
            "semanticClass": obj.semantic_class,
            "segmentID": obj.segment_id,
            "segmentName": obj.segment_name,
            "segmentKind": obj.segment_kind,
            "reconstruction": obj.reconstruction,
            "collectionPath": obj.collection_path,
            "extraProperties": dict(obj.extra_properties),
        }

        prototype = (
            scene_object_mesh_prototype_payload(obj)
            if prototype_instances
            else None
        )
        if prototype is None:
            data["vertices"] = obj.vertices
            data["faces"] = obj.faces
        else:
            prototype_key, translation, local_vertices = prototype
            stored = mesh_prototypes.get(prototype_key)
            if stored is None:
                stored = {
                    "vertices": local_vertices,
                    "faces": obj.faces,
                    "vertexCount": len(local_vertices),
                    "faceCount": len(obj.faces),
                }
                mesh_prototypes[prototype_key] = stored
            else:
                if _tuplify_faces(stored["faces"]) != obj.faces:
                    raise ValueError(
                        f"{obj.name}: mesh prototype face topology changed for "
                        f"{prototype_key!r}"
                    )
                reference_vertices = _tuplify_vertices(stored["vertices"])
                if len(reference_vertices) != len(local_vertices):
                    raise ValueError(
                        f"{obj.name}: mesh prototype vertex count changed for "
                        f"{prototype_key!r}"
                    )
                local_error = max(
                    (
                        max(abs(a - b) for a, b in zip(actual, reference))
                        for actual, reference in zip(
                            local_vertices,
                            reference_vertices,
                        )
                    ),
                    default=0.0,
                )
                if local_error > _MAX_PROTOTYPE_RECONSTRUCTION_ERROR_M:
                    raise ValueError(
                        f"{obj.name}: mesh prototype local geometry drift "
                        f"{local_error:g} m exceeds "
                        f"{_MAX_PROTOTYPE_RECONSTRUCTION_ERROR_M:g} m"
                    )

            reference_vertices = _tuplify_vertices(stored["vertices"])
            reconstruction_error = max(
                (
                    max(
                        abs(
                            reference[index]
                            + translation[index]
                            - world[index]
                        )
                        for index in range(3)
                    )
                    for reference, world in zip(
                        reference_vertices,
                        obj.vertices,
                    )
                ),
                default=0.0,
            )
            if reconstruction_error > _MAX_PROTOTYPE_RECONSTRUCTION_ERROR_M:
                raise ValueError(
                    f"{obj.name}: prototype reconstruction error "
                    f"{reconstruction_error:g} m exceeds "
                    f"{_MAX_PROTOTYPE_RECONSTRUCTION_ERROR_M:g} m"
                )
            max_reconstruction_error_m = max(
                max_reconstruction_error_m,
                reconstruction_error,
            )
            prototype_instance_count += 1
            data["meshPrototypeRef"] = prototype_key
            data["meshTranslationM"] = translation

        if include_custom_properties:
            # Retained by default for schema/backward compatibility. The field
            # is derivable from canonical fields + extraProperties, so compact
            # production exports may omit it without information loss.
            data["customProperties"] = obj.custom_properties
        return data

    objects = [object_dict(obj) for obj in package.objects]
    result: dict[str, Any] = {
        "schema": "tunnel_scanner_scene",
        "schemaVersion": (
            PROTOTYPE_SCENE_SCHEMA_VERSION
            if prototype_instances
            else SCENE_SCHEMA_VERSION
        ),
        "name": package.name,
        "mode": package.mode.value,
        "labelPolicy": package.label_policy.value,
        "metadata": dict(package.metadata),
        "objects": objects,
    }
    if prototype_instances:
        result["geometryEncoding"] = {
            "mode": "translation_mesh_prototypes_v1",
            "prototypeCount": len(mesh_prototypes),
            "prototypeInstanceCount": prototype_instance_count,
            "maxReconstructionErrorM": max_reconstruction_error_m,
            "reconstructionErrorLimitM": (
                _MAX_PROTOTYPE_RECONSTRUCTION_ERROR_M
            ),
            "precision": "float64_source_coordinates",
        }
        result["meshPrototypes"] = mesh_prototypes
    return result


def write_scene_package_json(
    package: ScenePackage,
    path: str | Path,
    *,
    compact: bool = False,
    prototype_instances: bool = False,
) -> Path:
    """Write a scene without constructing the final JSON string in memory.

    Compact mode also omits redundant customProperties because the reader
    reconstructs them losslessly from canonical fields and extraProperties.
    """
    path = Path(path)
    data = scene_package_to_dict(
        package,
        include_custom_properties=not compact,
        prototype_instances=prototype_instances,
    )
    with path.open("w", encoding="utf-8") as stream:
        json.dump(
            data,
            stream,
            indent=None if compact else 2,
            separators=(",", ":") if compact else None,
        )
    return path


def _tuplify_vertices(values) -> tuple[tuple[float, float, float], ...]:
    return tuple((float(v[0]), float(v[1]), float(v[2])) for v in values)


def _tuplify_faces(values) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(int(i) for i in face) for face in values)


def scene_package_from_dict(data: dict[str, Any]) -> ScenePackage:
    if data.get("schema") != "tunnel_scanner_scene":
        raise ValueError("unsupported scene schema")
    schema_version = int(data.get("schemaVersion", -1))
    if schema_version not in {
        SCENE_SCHEMA_VERSION,
        PROTOTYPE_SCENE_SCHEMA_VERSION,
    }:
        raise ValueError(
            f"unsupported scene schema version: {data.get('schemaVersion')}"
        )

    prototype_raw = data.get("meshPrototypes", {})
    if not isinstance(prototype_raw, dict):
        raise ValueError("meshPrototypes must be an object mapping")
    prototypes: dict[
        str,
        tuple[
            tuple[tuple[float, float, float], ...],
            tuple[tuple[int, ...], ...],
        ],
    ] = {}
    for key, raw in prototype_raw.items():
        if not isinstance(raw, dict):
            raise ValueError(f"mesh prototype {key!r} must be an object")
        prototypes[str(key)] = (
            _tuplify_vertices(raw["vertices"]),
            _tuplify_faces(raw["faces"]),
        )

    objects = []
    for raw in data["objects"]:
        prototype_ref = raw.get("meshPrototypeRef")
        if prototype_ref is None:
            vertices = _tuplify_vertices(raw["vertices"])
            faces = _tuplify_faces(raw["faces"])
        else:
            try:
                local_vertices, faces = prototypes[str(prototype_ref)]
            except KeyError as exc:
                raise ValueError(
                    f"unknown mesh prototype reference: {prototype_ref!r}"
                ) from exc
            raw_translation = raw.get("meshTranslationM")
            if (
                not isinstance(raw_translation, (list, tuple))
                or len(raw_translation) != 3
            ):
                raise ValueError(
                    f"{raw.get('name', '<unnamed>')}: prototype instance "
                    "requires meshTranslationM[3]"
                )
            tx, ty, tz = (float(value) for value in raw_translation)
            vertices = tuple(
                (x + tx, y + ty, z + tz)
                for x, y, z in local_vertices
            )

        objects.append(
            SceneObject(
                name=str(raw["name"]),
                vertices=vertices,
                faces=faces,
                object_type=str(raw["objectType"]),
                ring_id=int(raw["ringID"]),
                label_id=int(raw["labelID"]),
                instance_id=int(raw["instanceID"]),
                semantic_class=str(raw["semanticClass"]),
                segment_id=None if raw.get("segmentID") is None else int(raw["segmentID"]),
                segment_name=raw.get("segmentName"),
                segment_kind=raw.get("segmentKind"),
                reconstruction=raw.get("reconstruction"),
                collection_path=tuple(str(x) for x in raw.get("collectionPath", ())),
                extra_properties=dict(raw.get("extraProperties", {})),
            )
        )

    return ScenePackage(
        name=str(data["name"]),
        mode=SceneMode(data["mode"]),
        label_policy=LabelPolicy(data["labelPolicy"]),
        objects=tuple(objects),
        metadata=dict(data.get("metadata", {})),
    )


def read_scene_package_json(path: str | Path) -> ScenePackage:
    path = Path(path)
    return scene_package_from_dict(json.loads(path.read_text(encoding="utf-8")))
