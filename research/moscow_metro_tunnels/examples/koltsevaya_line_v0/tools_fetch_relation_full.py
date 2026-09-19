from __future__ import annotations

import argparse
import json
from pathlib import Path
from urllib.request import Request, urlopen

import sys

HERE = Path(__file__).resolve().parent
REFERENCE_IMPL = HERE.parents[1] / "reference_impl"
if str(REFERENCE_IMPL) not in sys.path:
    sys.path.insert(0, str(REFERENCE_IMPL))

from tunnel_pcg_ref.osm_relation import parse_relation_full_xml


DEFAULT_RELATION_ID = 1462012


def fetch_relation_full(
    relation_id: int,
    *,
    base_url: str = "https://api.openstreetmap.org/api/0.6",
    timeout_s: float = 60.0,
) -> bytes:
    url = f"{base_url}/relation/{relation_id}/full"
    request = Request(
        url,
        headers={
            "User-Agent": "Tunnel_PCG-research/0.2 OSM relation fetcher",
            "Accept": "application/xml,text/xml;q=0.9,*/*;q=0.1",
        },
    )
    with urlopen(request, timeout=timeout_s) as response:
        return response.read()


def _write_geojson(path: Path, data: dict):
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def fetch_relation_tree(
    relation_id: int,
    *,
    max_depth: int = 2,
    base_url: str = "https://api.openstreetmap.org/api/0.6",
    timeout_s: float = 60.0,
) -> dict[int, tuple[bytes, dict]]:
    """Fetch root plus nested relation members conservatively.

    This handles the case where a Wikidata OSM identifier points to a
    route_master/superrelation rather than directly to one direction's route.
    Child relations stay separate; they are never merged automatically.
    """
    result: dict[int, tuple[bytes, dict]] = {}
    queue = [(relation_id, 0)]

    while queue:
        rid, depth = queue.pop(0)
        if rid in result:
            continue

        xml = fetch_relation_full(
            rid, base_url=base_url, timeout_s=timeout_s
        )
        data = parse_relation_full_xml(xml, rid)
        result[rid] = (xml, data)

        if depth >= max_depth:
            continue

        for child in data["properties"].get(
            "nested_relation_members", []
        ):
            child_id = int(child["relation_id"])
            if child_id not in result:
                queue.append((child_id, depth + 1))

    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relation", type=int, default=DEFAULT_RELATION_ID)
    ap.add_argument(
        "--out",
        default="koltsevaya_relation_1462012_members.geojson",
    )
    ap.add_argument("--save-raw-xml", default=None)
    ap.add_argument(
        "--max-nested-depth",
        type=int,
        default=2,
        help=(
            "Fetch direct/nested relation members too. "
            "Use 0 to fetch only the requested relation."
        ),
    )
    args = ap.parse_args()

    tree = fetch_relation_tree(
        args.relation,
        max_depth=args.max_nested_depth,
    )
    root_xml, root_data = tree[args.relation]

    out = Path(args.out)
    _write_geojson(out, root_data)

    if args.save_raw_xml:
        Path(args.save_raw_xml).write_bytes(root_xml)

    child_outputs = []
    for rid, (xml, data) in tree.items():
        if rid == args.relation:
            continue
        child_path = out.with_name(
            f"{out.stem}_child_relation_{rid}{out.suffix}"
        )
        _write_geojson(child_path, data)
        child_outputs.append(
            {
                "relation_id": rid,
                "path": str(child_path),
                "relation_tags": data["properties"].get(
                    "relation_tags", {}
                ),
                "way_feature_count": data["properties"].get(
                    "way_feature_count", 0
                ),
            }
        )

    manifest = {
        "requested_relation_id": args.relation,
        "root_relation_tags": root_data["properties"].get(
            "relation_tags", {}
        ),
        "root_way_feature_count": root_data["properties"].get(
            "way_feature_count", 0
        ),
        "root_nested_relation_members": root_data["properties"].get(
            "nested_relation_members", []
        ),
        "child_outputs": child_outputs,
        "rule": (
            "If root is route_master, classify/stitch child route relations "
            "individually. Never merge direction variants into one track."
        ),
    }
    manifest_path = out.with_name(f"{out.stem}_manifest.json")
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"root={args.relation} "
        f"type={manifest['root_relation_tags'].get('type')} "
        f"route={manifest['root_relation_tags'].get('route')} "
        f"route_master={manifest['root_relation_tags'].get('route_master')} "
        f"root_ways={manifest['root_way_feature_count']} "
        f"nested_relations={len(manifest['root_nested_relation_members'])} "
        f"fetched_relations={len(tree)}"
    )


if __name__ == "__main__":
    main()
