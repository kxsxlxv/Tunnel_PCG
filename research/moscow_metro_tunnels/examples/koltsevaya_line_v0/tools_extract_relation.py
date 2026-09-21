from __future__ import annotations

"""Extract a route-master tree and physical OSM way members from a Moscow PBF.

Requires:
    pip install osmium

The current Koltsevaya hierarchy is:
    1462012 route_master
      -> 300607 Circle line (Inner)
      -> 1462011 Circle line (Outer)

This utility is intentionally conservative:
- child route relations are emitted separately;
- OSM way and node IDs are preserved;
- no branch is selected at a switch;
- no Inner/Outer geometry is merged;
- no Z is invented.
"""

import argparse
import json
from pathlib import Path

import osmium

DEFAULT_RELATION_ID = 1462012


class RelationsPass(osmium.SimpleHandler):
    def __init__(self, wanted_ids: set[int]):
        super().__init__()
        self.wanted_ids = set(wanted_ids)
        self.relations: dict[int, dict] = {}

    def relation(self, r):
        if int(r.id) not in self.wanted_ids:
            return
        self.relations[int(r.id)] = {
            "relation_id": int(r.id),
            "tags": dict(r.tags),
            "members": [
                {
                    "member_index": i,
                    "type": m.type,
                    "ref": int(m.ref),
                    "role": m.role,
                }
                for i, m in enumerate(r.members)
            ],
        }


class WayPass(osmium.SimpleHandler):
    def __init__(self, wanted_ids: set[int]):
        super().__init__()
        self.wanted_ids = set(wanted_ids)
        self.ways: dict[int, dict] = {}

    def way(self, w):
        if int(w.id) not in self.wanted_ids:
            return
        coords = []
        refs = []
        try:
            for n in w.nodes:
                refs.append(int(n.ref))
                coords.append([float(n.lon), float(n.lat)])
        except osmium.InvalidLocationError:
            return
        self.ways[int(w.id)] = {
            "tags": dict(w.tags),
            "osm_node_refs": refs,
            "coordinates": coords,
        }


def collect_relation_tree(
    pbf: str,
    root_relation_id: int,
    *,
    max_depth: int = 2,
) -> dict[int, dict]:
    """Read root plus nested relation members without merging them."""
    relations: dict[int, dict] = {}
    frontier = {int(root_relation_id)}

    for _depth in range(max_depth + 1):
        wanted = frontier - set(relations)
        if not wanted:
            break

        rp = RelationsPass(wanted)
        rp.apply_file(pbf, locations=False)

        missing = wanted - set(rp.relations)
        if missing:
            raise RuntimeError(
                "relation(s) not found in PBF: "
                + ", ".join(str(x) for x in sorted(missing))
            )

        relations.update(rp.relations)

        next_frontier: set[int] = set()
        for rel in rp.relations.values():
            for member in rel["members"]:
                if member["type"] == "r":
                    next_frontier.add(int(member["ref"]))
        frontier = next_frontier

    return relations


def relation_feature_collection(
    relation: dict,
    ways: dict[int, dict],
) -> dict:
    rid = int(relation["relation_id"])
    features = []
    missing = []

    for member in relation["members"]:
        if member["type"] != "w":
            continue
        way = ways.get(int(member["ref"]))
        if way is None:
            missing.append(
                {
                    "member_index": member["member_index"],
                    "way_id": member["ref"],
                    "reason": "way_missing_or_location_unavailable",
                }
            )
            continue

        refs = list(way["osm_node_refs"])
        coords = list(way["coordinates"])
        if len(refs) < 2 or len(refs) != len(coords):
            missing.append(
                {
                    "member_index": member["member_index"],
                    "way_id": member["ref"],
                    "reason": "short_or_coordinate_ref_mismatch",
                }
            )
            continue

        features.append(
            {
                "type": "Feature",
                "properties": {
                    "relation_id": rid,
                    "member_index": member["member_index"],
                    "member_role": member["role"],
                    "osm_way_id": member["ref"],
                    "osm_first_node_id": refs[0],
                    "osm_last_node_id": refs[-1],
                    "osm_node_refs": refs,
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

    nested = [
        {
            "member_index": m["member_index"],
            "relation_id": m["ref"],
            "role": m["role"],
        }
        for m in relation["members"]
        if m["type"] == "r"
    ]

    return {
        "type": "FeatureCollection",
        "name": f"osm_relation_{rid}_way_members",
        "properties": {
            "relation_id": rid,
            "relation_tags": relation["tags"],
            "way_feature_count": len(features),
            "nested_relation_members": nested,
            "missing_way_members": missing,
            "warning": (
                "Physical way members are preserved per relation. "
                "Do not merge direction routes or auto-select graph branches."
            ),
        },
        "features": features,
    }


def _write_json(path: Path, data: dict):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract(
    pbf: str,
    output: str,
    relation_id: int = DEFAULT_RELATION_ID,
    *,
    max_depth: int = 2,
):
    relations = collect_relation_tree(
        pbf,
        relation_id,
        max_depth=max_depth,
    )

    wanted_way_ids = {
        int(member["ref"])
        for relation in relations.values()
        for member in relation["members"]
        if member["type"] == "w"
    }

    wp = WayPass(wanted_way_ids)
    wp.apply_file(pbf, locations=True)

    outputs: dict[int, dict] = {}
    for rid, relation in relations.items():
        outputs[rid] = relation_feature_collection(
            relation,
            wp.ways,
        )

    root_path = Path(output)
    _write_json(root_path, outputs[relation_id])

    child_outputs = []
    for rid in sorted(outputs):
        if rid == relation_id:
            continue
        path = root_path.with_name(
            f"{root_path.stem}_child_relation_{rid}"
            f"{root_path.suffix}"
        )
        _write_json(path, outputs[rid])
        child_outputs.append(
            {
                "relation_id": rid,
                "path": str(path),
                "relation_tags": outputs[rid]["properties"][
                    "relation_tags"
                ],
                "way_feature_count": outputs[rid]["properties"][
                    "way_feature_count"
                ],
            }
        )

    manifest = {
        "requested_relation_id": relation_id,
        "root_relation_tags": outputs[relation_id][
            "properties"
        ]["relation_tags"],
        "root_nested_relation_members": outputs[relation_id][
            "properties"
        ]["nested_relation_members"],
        "child_outputs": child_outputs,
        "known_line5_contract": {
            "route_master": 1462012,
            "inner_route": 300607,
            "outer_route": 1462011,
        },
        "rule": (
            "For Koltsevaya, process Inner and Outer child relation "
            "outputs independently. Preserve all switch topology; "
            "never manufacture the second track by offset."
        ),
    }
    manifest_path = root_path.with_name(
        f"{root_path.stem}_manifest.json"
    )
    _write_json(manifest_path, manifest)

    return {
        "root": outputs[relation_id],
        "relations": outputs,
        "manifest": manifest,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf")
    ap.add_argument("output")
    ap.add_argument(
        "--relation",
        type=int,
        default=DEFAULT_RELATION_ID,
    )
    ap.add_argument(
        "--max-nested-depth",
        type=int,
        default=2,
    )
    args = ap.parse_args()

    result = extract(
        args.pbf,
        args.output,
        args.relation,
        max_depth=args.max_nested_depth,
    )
    manifest = result["manifest"]
    print(
        f"root={args.relation} "
        f"type={manifest['root_relation_tags'].get('type')} "
        f"nested={len(manifest['root_nested_relation_members'])} "
        f"fetched_relations={len(result['relations'])}"
    )


if __name__ == "__main__":
    main()
