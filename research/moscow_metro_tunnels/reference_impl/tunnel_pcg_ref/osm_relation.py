from __future__ import annotations

from dataclasses import dataclass
from xml.etree import ElementTree as ET


@dataclass(frozen=True)
class OSMNode:
    id: int
    lon: float
    lat: float


@dataclass(frozen=True)
class OSMWay:
    id: int
    node_refs: tuple[int, ...]
    tags: dict[str, str]


@dataclass(frozen=True)
class OSMRelationMember:
    index: int
    type: str
    ref: int
    role: str


def _tags(el: ET.Element) -> dict[str, str]:
    return {t.attrib["k"]: t.attrib["v"] for t in el.findall("tag")}


def parse_relation_full_xml(xml_bytes: bytes | str, relation_id: int) -> dict:
    """Convert OSM /relation/{id}/full XML into member-way GeoJSON.

    Member order, role and OSM way IDs are retained. No attempt is made to
    merge ways into one route because a subway relation may contain stops,
    platforms, direction-specific members or other non-centerline objects.
    """
    if isinstance(xml_bytes, str):
        xml_bytes = xml_bytes.encode("utf-8")
    root = ET.fromstring(xml_bytes)

    nodes: dict[int, OSMNode] = {}
    ways: dict[int, OSMWay] = {}
    target = None

    for el in root:
        if el.tag == "node":
            nid = int(el.attrib["id"])
            nodes[nid] = OSMNode(
                nid, float(el.attrib["lon"]), float(el.attrib["lat"])
            )
        elif el.tag == "way":
            wid = int(el.attrib["id"])
            refs = tuple(int(nd.attrib["ref"]) for nd in el.findall("nd"))
            ways[wid] = OSMWay(wid, refs, _tags(el))
        elif (
            el.tag == "relation"
            and int(el.attrib["id"]) == relation_id
        ):
            target = el

    if target is None:
        raise ValueError(f"relation {relation_id} not found in XML")

    members = [
        OSMRelationMember(
            index=i,
            type=m.attrib["type"],
            ref=int(m.attrib["ref"]),
            role=m.attrib.get("role", ""),
        )
        for i, m in enumerate(target.findall("member"))
    ]

    features = []
    missing = []
    for member in members:
        if member.type != "way":
            continue
        way = ways.get(member.ref)
        if way is None:
            missing.append(
                {
                    "member_index": member.index,
                    "way_id": member.ref,
                    "reason": "way_missing",
                }
            )
            continue

        coords = []
        missing_nodes = []
        for ref in way.node_refs:
            node = nodes.get(ref)
            if node is None:
                missing_nodes.append(ref)
            else:
                coords.append([node.lon, node.lat])

        if missing_nodes or len(coords) < 2:
            missing.append(
                {
                    "member_index": member.index,
                    "way_id": member.ref,
                    "reason": "node_missing_or_short_way",
                    "missing_nodes": missing_nodes,
                }
            )
            continue

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "relation_id": relation_id,
                    "member_index": member.index,
                    "member_role": member.role,
                    "osm_way_id": member.ref,
                    **{f"osm_{k}": v for k, v in way.tags.items()},
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "name": f"osm_relation_{relation_id}_way_members",
        "properties": {
            "relation_id": relation_id,
            "relation_tags": _tags(target),
            "member_count": len(members),
            "way_feature_count": len(features),
            "missing": missing,
            "warning": (
                "Relation members are preserved, not automatically merged "
                "into a physical track."
            ),
        },
        "features": features,
    }
