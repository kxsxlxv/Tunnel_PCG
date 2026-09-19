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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--relation", type=int, default=DEFAULT_RELATION_ID)
    ap.add_argument(
        "--out",
        default="koltsevaya_relation_1462012_members.geojson",
    )
    ap.add_argument("--save-raw-xml", default=None)
    args = ap.parse_args()

    xml = fetch_relation_full(args.relation)
    if args.save_raw_xml:
        Path(args.save_raw_xml).write_bytes(xml)

    data = parse_relation_full_xml(xml, args.relation)
    Path(args.out).write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(
        f"relation={args.relation} "
        f"members={data['properties']['member_count']} "
        f"way_features={data['properties']['way_feature_count']} "
        f"missing={len(data['properties']['missing'])}"
    )


if __name__ == "__main__":
    main()
