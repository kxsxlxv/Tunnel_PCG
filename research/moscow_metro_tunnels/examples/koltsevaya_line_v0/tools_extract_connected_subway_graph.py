from __future__ import annotations

"""Expand from the two Line-5 route relations into nearby physical subway ways.

Requires:
    pip install osmium

Purpose:
- route relations 300607 (Inner) and 1462011 (Outer) define the two main
  passenger-route candidates;
- depot/service/crossover ways may NOT be route members;
- therefore a topology study must also preserve physical railway=subway ways
  connected to the route-member nodes.

The expansion is deliberately semantic-free. A connected off-route way is not
automatically called a depot branch or crossover. That annotation comes from
track_topology.json / junction_events.json.
"""

import argparse
import json
from collections import defaultdict
from pathlib import Path

import osmium

import sys

HERE = Path(__file__).resolve().parent
REFERENCE_IMPL = HERE.parents[1] / "reference_impl"
if str(REFERENCE_IMPL) not in sys.path:
    sys.path.insert(0, str(REFERENCE_IMPL))

from tunnel_pcg_ref.osm_track_graph import extract_physical_track_graph


INNER_RELATION_ID = 300607
OUTER_RELATION_ID = 1462011


class RouteMembersPass(osmium.SimpleHandler):
    def __init__(self, relation_ids: set[int]):
        super().__init__()
        self.relation_ids = set(relation_ids)
        self.route_way_ids: dict[int, set[int]] = {
            rid: set() for rid in relation_ids
        }

    def relation(self, r):
        rid = int(r.id)
        if rid not in self.relation_ids:
            return
        self.route_way_ids[rid] = {
            int(m.ref)
            for m in r.members
            if m.type == "w"
        }


class SubwayTopologyPass(osmium.SimpleHandler):
    def __init__(
        self,
        *,
        accepted_railway: tuple[str, ...] = ("subway",),
    ):
        super().__init__()
        self.accepted_railway = set(accepted_railway)
        self.ways: dict[int, dict] = {}

    def way(self, w):
        tags = dict(w.tags)
        if tags.get("railway") not in self.accepted_railway:
            return
        refs = tuple(int(n.ref) for n in w.nodes)
        if len(refs) < 2:
            return
        self.ways[int(w.id)] = {
            "way_id": int(w.id),
            "refs": refs,
            "tags": tags,
        }


class SelectedGeometryPass(osmium.SimpleHandler):
    def __init__(self, wanted_ids: set[int]):
        super().__init__()
        self.wanted_ids = set(wanted_ids)
        self.geometry: dict[int, list[list[float]]] = {}

    def way(self, w):
        wid = int(w.id)
        if wid not in self.wanted_ids:
            return
        try:
            coords = [
                [float(n.lon), float(n.lat)]
                for n in w.nodes
            ]
        except osmium.InvalidLocationError:
            return
        self.geometry[wid] = coords


def expand_connected_way_ids(
    all_ways: dict[int, dict],
    seed_way_ids: set[int],
    *,
    expansion_hops: int,
) -> tuple[set[int], dict[int, int]]:
    """BFS over shared OSM nodes.

    hop=0: route-member ways only.
    hop=1: plus ways that directly share a node with a route-member way.
    Larger values preserve successively farther physical branches.

    The hop count is only an acquisition boundary; it is never a branch
    classification or geometry assumption.
    """
    missing_seed = seed_way_ids - set(all_ways)
    if missing_seed:
        raise RuntimeError(
            "route relation contains way(s) that are not accepted "
            "railway=subway candidates: "
            + ", ".join(str(x) for x in sorted(missing_seed))
        )

    node_to_way_ids: dict[int, set[int]] = defaultdict(set)
    for wid, way in all_ways.items():
        for ref in set(way["refs"]):
            node_to_way_ids[ref].add(wid)

    included = set(seed_way_ids)
    distance_hops = {wid: 0 for wid in seed_way_ids}
    frontier = set(seed_way_ids)

    for hop in range(1, expansion_hops + 1):
        next_frontier: set[int] = set()
        frontier_nodes = {
            ref
            for wid in frontier
            for ref in all_ways[wid]["refs"]
        }
        for node_id in frontier_nodes:
            for wid in node_to_way_ids.get(node_id, set()):
                if wid in included:
                    continue
                included.add(wid)
                distance_hops[wid] = hop
                next_frontier.add(wid)
        frontier = next_frontier
        if not frontier:
            break

    return included, distance_hops


def build_feature_collection(
    all_ways: dict[int, dict],
    selected_ids: set[int],
    geometry: dict[int, list[list[float]]],
    *,
    inner_ids: set[int],
    outer_ids: set[int],
    distance_hops: dict[int, int],
) -> dict:
    features = []
    missing_geometry = []

    for member_index, wid in enumerate(sorted(selected_ids)):
        way = all_ways[wid]
        coords = geometry.get(wid)
        if coords is None or len(coords) != len(way["refs"]):
            missing_geometry.append(wid)
            continue

        in_inner = wid in inner_ids
        in_outer = wid in outer_ids
        if in_inner and in_outer:
            membership = "inner_and_outer_route_member"
        elif in_inner:
            membership = "inner_route_member"
        elif in_outer:
            membership = "outer_route_member"
        else:
            membership = "connected_off_route_candidate"

        refs = list(way["refs"])
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "member_index": member_index,
                    "member_role": "",
                    "osm_way_id": wid,
                    "osm_node_refs": refs,
                    "osm_first_node_id": refs[0],
                    "osm_last_node_id": refs[-1],
                    "osm_route_membership": membership,
                    "osm_graph_expansion_hops_from_main_route": (
                        distance_hops[wid]
                    ),
                    **{
                        f"osm_{k}": v
                        for k, v in way["tags"].items()
                    },
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coords,
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "name": "koltsevaya_connected_subway_candidates",
        "properties": {
            "inner_relation_id": INNER_RELATION_ID,
            "outer_relation_id": OUTER_RELATION_ID,
            "warning": (
                "Off-route connected ways are topology candidates only. "
                "Do not label depot/crossover/service semantics from "
                "connectivity or proximity alone."
            ),
            "missing_geometry_way_ids": missing_geometry,
        },
        "features": features,
    }


def extract_connected_graph(
    pbf: str,
    *,
    candidate_geojson: str,
    graph_json: str,
    expansion_hops: int = 2,
):
    route_pass = RouteMembersPass(
        {INNER_RELATION_ID, OUTER_RELATION_ID}
    )
    route_pass.apply_file(pbf, locations=False)

    inner_ids = route_pass.route_way_ids[INNER_RELATION_ID]
    outer_ids = route_pass.route_way_ids[OUTER_RELATION_ID]
    if not inner_ids or not outer_ids:
        raise RuntimeError(
            "current Line-5 Inner/Outer route members were not found; "
            "check PBF date and relation IDs"
        )

    topo_pass = SubwayTopologyPass()
    topo_pass.apply_file(pbf, locations=False)

    seed_ids = inner_ids | outer_ids
    selected_ids, distance_hops = expand_connected_way_ids(
        topo_pass.ways,
        seed_ids,
        expansion_hops=expansion_hops,
    )

    geom_pass = SelectedGeometryPass(selected_ids)
    geom_pass.apply_file(pbf, locations=True)

    fc = build_feature_collection(
        topo_pass.ways,
        selected_ids,
        geom_pass.geometry,
        inner_ids=inner_ids,
        outer_ids=outer_ids,
        distance_hops=distance_hops,
    )
    graph = extract_physical_track_graph(fc)

    graph["source_contract"] = {
        "route_master": 1462012,
        "inner_route": INNER_RELATION_ID,
        "outer_route": OUTER_RELATION_ID,
        "source_ids": ["S099", "S100", "S101"],
        "expansion_hops": expansion_hops,
        "expansion_semantics": (
            "acquisition scope only; not depot/crossover classification"
        ),
    }

    Path(candidate_geojson).write_text(
        json.dumps(fc, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    Path(graph_json).write_text(
        json.dumps(graph, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return fc, graph


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf")
    ap.add_argument(
        "--candidate-geojson",
        default="koltsevaya_connected_subway_candidates.geojson",
    )
    ap.add_argument(
        "--graph-json",
        default="koltsevaya_physical_track_graph.json",
    )
    ap.add_argument(
        "--expansion-hops",
        type=int,
        default=2,
        help=(
            "Number of shared-node graph hops beyond Inner/Outer "
            "route-member ways. This is only an acquisition boundary."
        ),
    )
    args = ap.parse_args()

    fc, graph = extract_connected_graph(
        args.pbf,
        candidate_geojson=args.candidate_geojson,
        graph_json=args.graph_json,
        expansion_hops=args.expansion_hops,
    )
    print(
        f"candidate_ways={len(fc['features'])} "
        f"graph_edges={len(graph['edges'])} "
        f"graph_nodes={len(graph['nodes'])}"
    )


if __name__ == "__main__":
    main()
