from __future__ import annotations

from dataclasses import asdict
import json
from pathlib import Path
from typing import Any

from .scene import LabelPolicy, SceneMode, SceneObject, ScenePackage


SCENE_SCHEMA_VERSION = 1


def scene_package_to_dict(
    package: ScenePackage,
    *,
    include_custom_properties: bool = True,
) -> dict[str, Any]:
    def object_dict(obj: SceneObject) -> dict[str, Any]:
        data = {
            "name": obj.name,
            "vertices": obj.vertices,
            "faces": obj.faces,
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
        if include_custom_properties:
            # Retained by default for schema/backward compatibility. The field
            # is derivable from canonical fields + extraProperties, so compact
            # production exports may omit it without information loss.
            data["customProperties"] = obj.custom_properties
        return data

    return {
        "schema": "tunnel_scanner_scene",
        "schemaVersion": SCENE_SCHEMA_VERSION,
        "name": package.name,
        "mode": package.mode.value,
        "labelPolicy": package.label_policy.value,
        "metadata": dict(package.metadata),
        "objects": [object_dict(obj) for obj in package.objects],
    }


def write_scene_package_json(
    package: ScenePackage,
    path: str | Path,
    *,
    compact: bool = False,
) -> Path:
    """Write a scene without constructing the final JSON string in memory.

    Compact mode also omits redundant customProperties because the reader
    reconstructs them losslessly from canonical fields and extraProperties.
    """
    path = Path(path)
    data = scene_package_to_dict(
        package,
        include_custom_properties=not compact,
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
    if int(data.get("schemaVersion", -1)) != SCENE_SCHEMA_VERSION:
        raise ValueError(f"unsupported scene schema version: {data.get('schemaVersion')}")

    objects = []
    for raw in data["objects"]:
        objects.append(
            SceneObject(
                name=str(raw["name"]),
                vertices=_tuplify_vertices(raw["vertices"]),
                faces=_tuplify_faces(raw["faces"]),
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
