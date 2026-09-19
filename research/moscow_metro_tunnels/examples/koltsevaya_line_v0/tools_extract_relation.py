from __future__ import annotations

"""Extract ordered OSM way members of the current Koltsevaya relation.

Requires:
    pip install osmium

Input should be a current Moscow .osm.pbf, e.g. BBBike.
This tool preserves relation member order/role and intentionally does not
pretend that all member ways form one physical track.
"""

import argparse
import json
from pathlib import Path

import osmium

DEFAULT_RELATION_ID = 1462012


class RelationPass(osmium.SimpleHandler):
    def __init__(self, relation_id: int):
        super().__init__()
        self.relation_id = relation_id
        self.members = []
        self.tags = {}

    def relation(self, r):
        if r.id != self.relation_id:
            return
        self.tags = dict(r.tags)
        self.members = [
            {
                "member_index": i,
                "type": m.type,
                "ref": int(m.ref),
                "role": m.role,
            }
            for i, m in enumerate(r.members)
        ]


class WayPass(osmium.SimpleHandler):
    def __init__(self, wanted_ids: set[int]):
        super().__init__()
        self.wanted_ids = wanted_ids
        self.ways = {}

    def way(self, w):
        if w.id not in self.wanted_ids:
            return
        coords = []
        try:
            for n in w.nodes:
                coords.append([float(n.lon), float(n.lat)])
        except osmium.InvalidLocationError:
            return
        self.ways[int(w.id)] = {
            "tags": dict(w.tags),
            "coordinates": coords,
        }


def extract(pbf: str, output: str, relation_id: int = DEFAULT_RELATION_ID):
    rp = RelationPass(relation_id)
    rp.apply_file(pbf, locations=False)

    if not rp.members:
        raise RuntimeError(f"relation {relation_id} not found or has no members")

    wanted = {
        m["ref"] for m in rp.members
        if m["type"] == "w"
    }

    wp = WayPass(wanted)
    wp.apply_file(pbf, locations=True)

    features = []
    missing = []

    for m in rp.members:
        if m["type"] != "w":
            continue
        w = wp.ways.get(m["ref"])
        if w is None:
            missing.append(m)
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "relation_id": relation_id,
                "member_index": m["member_index"],
                "member_role": m["role"],
                "osm_way_id": m["ref"],
                **{f"osm_{k}": v for k, v in w["tags"].items()},
            },
            "geometry": {
                "type": "LineString",
                "coordinates": w["coordinates"],
            },
        })

    payload = {
        "type": "FeatureCollection",
        "name": f"osm_relation_{relation_id}_way_members",
        "properties": {
            "relation_id": relation_id,
            "relation_tags": rp.tags,
            "warning": (
                "Ordered member ways only. Classify physical tracks and stitch "
                "by connectivity/direction before building engineering alignment."
            ),
            "missing_way_members": missing,
        },
        "features": features,
    }

    Path(output).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return payload


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pbf")
    ap.add_argument("output")
    ap.add_argument("--relation", type=int, default=DEFAULT_RELATION_ID)
    args = ap.parse_args()
    extract(args.pbf, args.output, args.relation)


if __name__ == "__main__":
    main()
