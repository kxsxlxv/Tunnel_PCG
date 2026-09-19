from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class StitchedWay:
    way_ids: tuple[int, ...]
    member_indices: tuple[int, ...]
    reversed_flags: tuple[bool, ...]
    node_ids: tuple[int, ...]
    coordinates: tuple[tuple[float, float], ...]
    closed: bool


def _feature_record(feature: dict) -> dict:
    props = feature.get("properties") or {}
    geom = feature.get("geometry") or {}
    if geom.get("type") != "LineString":
        raise ValueError("all stitch candidates must be LineString features")

    refs = props.get("osm_node_refs")
    coords = geom.get("coordinates")
    if not isinstance(refs, list) or len(refs) < 2:
        raise ValueError("osm_node_refs missing; use the relation/full parser")
    if not isinstance(coords, list) or len(coords) != len(refs):
        raise ValueError("coordinate/node-ref length mismatch")

    return {
        "way_id": int(props["osm_way_id"]),
        "member_index": int(props["member_index"]),
        "role": props.get("member_role", ""),
        "railway": props.get("osm_railway"),
        "refs": tuple(int(x) for x in refs),
        "coords": tuple((float(p[0]), float(p[1])) for p in coords),
    }


def candidate_subway_ways(
    feature_collection: dict,
    *,
    accepted_railway: tuple[str, ...] = ("subway",),
    roles: set[str] | None = None,
) -> list[dict]:
    """Return physical-track candidates without merging them.

    By default only railway=subway LineStrings are accepted. A role filter may
    be supplied after inspecting the actual relation, but the default does not
    assume that OSM route roles are consistent across mapping eras.
    """
    out = []
    for feature in feature_collection.get("features", []):
        rec = _feature_record(feature)
        if rec["railway"] not in accepted_railway:
            continue
        if roles is not None and rec["role"] not in roles:
            continue
        out.append(rec)
    return sorted(out, key=lambda x: x["member_index"])


def connected_components(ways: Iterable[dict]) -> list[list[dict]]:
    ways = list(ways)
    node_to_way_indices: dict[int, list[int]] = {}
    for i, way in enumerate(ways):
        for node_id in {way["refs"][0], way["refs"][-1]}:
            node_to_way_indices.setdefault(node_id, []).append(i)

    seen: set[int] = set()
    components: list[list[dict]] = []

    for start in range(len(ways)):
        if start in seen:
            continue
        stack = [start]
        seen.add(start)
        idxs = []
        while stack:
            i = stack.pop()
            idxs.append(i)
            way = ways[i]
            for node_id in (way["refs"][0], way["refs"][-1]):
                for j in node_to_way_indices.get(node_id, []):
                    if j not in seen:
                        seen.add(j)
                        stack.append(j)
        components.append(
            sorted((ways[i] for i in idxs), key=lambda x: x["member_index"])
        )

    return components


def _endpoint_degree(component: list[dict]) -> dict[int, int]:
    degree: dict[int, int] = {}
    for way in component:
        degree[way["refs"][0]] = degree.get(way["refs"][0], 0) + 1
        degree[way["refs"][-1]] = degree.get(way["refs"][-1], 0) + 1
    return degree


def stitch_simple_component(component: list[dict]) -> StitchedWay:
    """Stitch one unbranched component using shared OSM endpoint node IDs.

    Accepts open chains and closed loops. Graph branches/switch junctions are
    rejected because choosing a branch without explicit topology would invent
    a physical train path.
    """
    if not component:
        raise ValueError("empty component")

    degree = _endpoint_degree(component)
    if any(d > 2 for d in degree.values()):
        raise ValueError(
            "branched component: resolve switch/topology before stitching"
        )

    endpoints = [node for node, d in degree.items() if d == 1]
    closed = len(endpoints) == 0
    if not closed and len(endpoints) != 2:
        raise ValueError("component is neither a simple chain nor a simple loop")

    unused = {w["way_id"]: w for w in component}
    node_to_way_ids: dict[int, list[int]] = {}
    for w in component:
        for node in {w["refs"][0], w["refs"][-1]}:
            node_to_way_ids.setdefault(node, []).append(w["way_id"])

    if closed:
        first = min(component, key=lambda w: w["member_index"])
        start_node = first["refs"][0]
    else:
        start_node = min(
            endpoints,
            key=lambda node: min(
                unused[wid]["member_index"]
                for wid in node_to_way_ids[node]
            ),
        )

    current = start_node
    ordered: list[tuple[dict, bool]] = []

    while unused:
        choices = [
            unused[wid]
            for wid in node_to_way_ids.get(current, [])
            if wid in unused
        ]
        if not choices:
            raise ValueError("component cannot be traversed continuously")
        way = min(choices, key=lambda w: w["member_index"])

        if way["refs"][0] == current:
            reversed_flag = False
            current = way["refs"][-1]
        elif way["refs"][-1] == current:
            reversed_flag = True
            current = way["refs"][0]
        else:
            raise AssertionError("endpoint index inconsistency")

        ordered.append((way, reversed_flag))
        del unused[way["way_id"]]

    if closed and current != start_node:
        raise ValueError("loop failed to close")
    if not closed and current not in endpoints:
        raise ValueError("open chain ended away from endpoint")

    out_nodes: list[int] = []
    out_coords: list[tuple[float, float]] = []
    way_ids: list[int] = []
    member_indices: list[int] = []
    reversed_flags: list[bool] = []

    for i, (way, rev) in enumerate(ordered):
        refs = list(reversed(way["refs"])) if rev else list(way["refs"])
        coords = list(reversed(way["coords"])) if rev else list(way["coords"])
        if i:
            if out_nodes[-1] != refs[0]:
                raise AssertionError("stitched endpoint mismatch")
            refs = refs[1:]
            coords = coords[1:]
        out_nodes.extend(refs)
        out_coords.extend(coords)
        way_ids.append(way["way_id"])
        member_indices.append(way["member_index"])
        reversed_flags.append(rev)

    return StitchedWay(
        way_ids=tuple(way_ids),
        member_indices=tuple(member_indices),
        reversed_flags=tuple(reversed_flags),
        node_ids=tuple(out_nodes),
        coordinates=tuple(out_coords),
        closed=closed,
    )


def stitch_relation_tracks(feature_collection: dict) -> list[StitchedWay]:
    """Conservative first-pass relation track stitching.

    Returns one result per unbranched connected railway=subway component.
    Branching components are rejected rather than guessed.
    """
    candidates = candidate_subway_ways(feature_collection)
    return [
        stitch_simple_component(component)
        for component in connected_components(candidates)
    ]
