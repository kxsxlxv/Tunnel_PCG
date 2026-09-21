from __future__ import annotations

from collections import defaultdict, deque
from typing import Iterable


def _feature_record(feature: dict) -> dict:
    """Normalize one physical OSM rail LineString without choosing a route."""
    props = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    if geom.get("type") != "LineString":
        raise ValueError("all graph candidates must be LineString features")

    refs = props.get("osm_node_refs")
    coords = geom.get("coordinates")
    if not isinstance(refs, list) or len(refs) < 2:
        raise ValueError("osm_node_refs missing; use the relation/full parser")
    if not isinstance(coords, list) or len(coords) != len(refs):
        raise ValueError("coordinate/node-ref length mismatch")

    return {
        "way_id": int(props["osm_way_id"]),
        "member_index": int(props.get("member_index", -1)),
        "member_role": props.get("member_role", ""),
        "railway": props.get("osm_railway"),
        "refs": tuple(int(x) for x in refs),
        "coords": tuple((float(p[0]), float(p[1])) for p in coords),
        "properties": dict(props),
    }


def candidate_physical_subway_ways(
    feature_collection: dict,
    *,
    accepted_railway: tuple[str, ...] = ("subway",),
) -> list[dict]:
    """Preserve every physical subway way; do not stitch or select a branch."""
    out = []
    for feature in feature_collection.get("features", []):
        rec = _feature_record(feature)
        if rec["railway"] not in accepted_railway:
            continue
        out.append(rec)
    return sorted(out, key=lambda x: (x["member_index"], x["way_id"]))


def _break_nodes(ways: Iterable[dict]) -> set[int]:
    """Nodes at which graph edges must be split.

    Endpoints always split. Any OSM node referenced by more than one distinct
    physical way also splits, even when it occurs in the middle of a way. This
    is essential for switch/crossover topology because OSM does not have to
    split every member way at a route-relation boundary.
    """
    ways = list(ways)
    owners: dict[int, set[int]] = defaultdict(set)
    breaks: set[int] = set()

    for way in ways:
        breaks.add(way["refs"][0])
        breaks.add(way["refs"][-1])
        for ref in way["refs"]:
            owners[ref].add(way["way_id"])

    for ref, way_ids in owners.items():
        if len(way_ids) > 1:
            breaks.add(ref)
    return breaks


def _split_way(way: dict, break_nodes: set[int]) -> list[dict]:
    refs = way["refs"]
    coords = way["coords"]

    indices = {0, len(refs) - 1}
    for i, ref in enumerate(refs):
        if ref in break_nodes:
            indices.add(i)
    cuts = sorted(indices)

    parts = []
    part_index = 0
    for a, b in zip(cuts, cuts[1:]):
        if b <= a:
            continue
        subrefs = refs[a : b + 1]
        subcoords = coords[a : b + 1]
        parts.append(
            {
                "edge_id": f"osm_way_{way['way_id']}_part_{part_index}",
                "entity_type": "TRACK_EDGE",
                "classification": "unclassified_physical_track",
                "osm_way_id": way["way_id"],
                "member_index": way["member_index"],
                "member_role": way["member_role"],
                "from_osm_node_id": subrefs[0],
                "to_osm_node_id": subrefs[-1],
                "osm_node_refs": list(subrefs),
                "coordinates_wgs84": [list(p) for p in subcoords],
                "osm_properties": way["properties"],
            }
        )
        part_index += 1

    # A valid closed OSM way with only its repeated endpoint as a break still
    # produces one self-loop graph edge.
    if not parts and refs[0] == refs[-1]:
        parts.append(
            {
                "edge_id": f"osm_way_{way['way_id']}_part_0",
                "entity_type": "TRACK_EDGE",
                "classification": "unclassified_physical_track",
                "osm_way_id": way["way_id"],
                "member_index": way["member_index"],
                "member_role": way["member_role"],
                "from_osm_node_id": refs[0],
                "to_osm_node_id": refs[-1],
                "osm_node_refs": list(refs),
                "coordinates_wgs84": [list(p) for p in coords],
                "osm_properties": way["properties"],
            }
        )

    return parts


def _components(edges: list[dict]) -> list[list[str]]:
    node_to_edges: dict[int, list[int]] = defaultdict(list)
    for i, edge in enumerate(edges):
        node_to_edges[edge["from_osm_node_id"]].append(i)
        node_to_edges[edge["to_osm_node_id"]].append(i)

    seen: set[int] = set()
    out: list[list[str]] = []
    for start in range(len(edges)):
        if start in seen:
            continue
        q = deque([start])
        seen.add(start)
        ids = []
        while q:
            i = q.popleft()
            edge = edges[i]
            ids.append(edge["edge_id"])
            for node in (edge["from_osm_node_id"], edge["to_osm_node_id"]):
                for j in node_to_edges[node]:
                    if j not in seen:
                        seen.add(j)
                        q.append(j)
        out.append(sorted(ids))
    return out


def extract_physical_track_graph(feature_collection: dict) -> dict:
    """Build a conservative physical OSM track graph.

    This function intentionally does *not* identify the Koltsevaya main track,
    depot branch, straight route, diverging route, handedness, or crossover.
    It only preserves physical ways and exposes graph nodes. Those semantics
    must be attached from researched topology in a separate contract.

    Unlike stitch_simple_component(), degree > 2 is retained as SWITCH_NODE.
    No branch is selected automatically.
    """
    ways = candidate_physical_subway_ways(feature_collection)
    breaks = _break_nodes(ways)

    edges: list[dict] = []
    for way in ways:
        edges.extend(_split_way(way, breaks))

    degree: dict[int, int] = defaultdict(int)
    node_coord: dict[int, tuple[float, float]] = {}

    for edge in edges:
        a = edge["from_osm_node_id"]
        b = edge["to_osm_node_id"]
        # A self-loop contributes degree two.
        if a == b:
            degree[a] += 2
        else:
            degree[a] += 1
            degree[b] += 1

        refs = edge["osm_node_refs"]
        coords = edge["coordinates_wgs84"]
        for ref, coord in zip(refs, coords):
            if ref in breaks and ref not in node_coord:
                node_coord[ref] = (float(coord[0]), float(coord[1]))

    nodes = []
    for ref in sorted(degree):
        d = degree[ref]
        if d == 1:
            cls = "END_NODE"
        elif d == 2:
            cls = "PASS_THROUGH"
        else:
            cls = "SWITCH_NODE"
        lon, lat = node_coord[ref]
        nodes.append(
            {
                "node_id": f"osm_node_{ref}",
                "osm_node_id": ref,
                "entity_type": cls,
                "degree": d,
                "coordinates_wgs84": [lon, lat],
                "z_ugr_m": None,
            }
        )

    return {
        "schema_version": "0.1",
        "crs": "EPSG:4326",
        "nodes": nodes,
        "edges": edges,
        "components": _components(edges),
        "warnings": [
            "OSM is topology/XY evidence, not an engineering survey.",
            "Z is intentionally unresolved.",
            "SWITCH_NODE means graph degree > 2 only; straight/diverging semantics are not guessed.",
            "Main-track A/B, crossover, and depot/service-branch classifications require a researched annotation contract.",
        ],
    }
