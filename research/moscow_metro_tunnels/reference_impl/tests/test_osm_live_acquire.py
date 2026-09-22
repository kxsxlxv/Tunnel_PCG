import base64, gzip, json, time, urllib.parse, urllib.request, warnings
import xml.etree.ElementTree as ET

REL_ID = 1462011
UA = "Tunnel_PCG research acquisition/2026-09-22 (OpenStreetMap geometry provenance)"

def fetch_bytes(url, data=None, timeout=120):
    req = urllib.request.Request(url, data=data, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()

def fetch_relation_full():
    errors=[]
    for u in [
        f"https://api.openstreetmap.org/api/0.6/relation/{REL_ID}/full",
        f"https://www.openstreetmap.org/api/0.6/relation/{REL_ID}/full",
    ]:
        try:
            return fetch_bytes(u), u
        except Exception as e:
            errors.append(f"{u}: {type(e).__name__}: {e}")
    raise RuntimeError("relation/full failed: " + " | ".join(errors))

def parse_full(xml_bytes):
    root=ET.fromstring(xml_bytes); nodes={}; ways={}; relations={}
    for e in root:
        if e.tag=="node":
            tags={t.attrib["k"]:t.attrib["v"] for t in e.findall("tag")}
            nodes[int(e.attrib["id"])]={"id":int(e.attrib["id"]),"lat":float(e.attrib["lat"]),"lon":float(e.attrib["lon"]),"version":int(e.attrib.get("version","0")),"timestamp":e.attrib.get("timestamp"),"tags":tags}
        elif e.tag=="way":
            tags={t.attrib["k"]:t.attrib["v"] for t in e.findall("tag")}
            ways[int(e.attrib["id"])]={"id":int(e.attrib["id"]),"version":int(e.attrib.get("version","0")),"timestamp":e.attrib.get("timestamp"),"nodes":[int(nd.attrib["ref"]) for nd in e.findall("nd")],"tags":tags}
        elif e.tag=="relation":
            tags={t.attrib["k"]:t.attrib["v"] for t in e.findall("tag")}
            members=[{"index":idx,"type":m.attrib["type"],"ref":int(m.attrib["ref"]),"role":m.attrib.get("role","")} for idx,m in enumerate(e.findall("member"))]
            relations[int(e.attrib["id"])]={"id":int(e.attrib["id"]),"version":int(e.attrib.get("version","0")),"timestamp":e.attrib.get("timestamp"),"changeset":int(e.attrib.get("changeset","0")),"members":members,"tags":tags}
    return nodes,ways,relations

def fetch_connected_overpass():
    q=f"""[out:json][timeout:180];
rel({REL_ID});
way(r)[railway=subway]->.main;
node(w.main)->.mn;
way(bn.mn)[railway=subway]->.connected;
(.main;.connected;);
out body;
>;
out skel qt;"""
    data=urllib.parse.urlencode({"data":q}).encode()
    errors=[]
    for ep in ["https://overpass-api.de/api/interpreter","https://overpass.kumi.systems/api/interpreter","https://overpass.nchc.org.tw/api/interpreter"]:
        try:
            return json.loads(fetch_bytes(ep,data=data,timeout=210)), ep
        except Exception as e:
            errors.append(f"{ep}: {type(e).__name__}: {e}"); time.sleep(2)
    raise RuntimeError("overpass failed: " + " | ".join(errors))

def normalize_overpass(obj):
    ns={}; ws={}
    for e in obj.get("elements",[]):
        if e.get("type")=="node":
            ns[int(e["id"])]={"id":int(e["id"]),"lat":float(e["lat"]),"lon":float(e["lon"]),"tags":e.get("tags",{})}
        elif e.get("type")=="way":
            ws[int(e["id"])]={"id":int(e["id"]),"nodes":[int(x) for x in e.get("nodes",[])],"tags":e.get("tags",{})}
    return ns,ws

def test_emit_live_osm_acquisition_payload():
    raw,full_url=fetch_relation_full()
    nodes,ways,rels=parse_full(raw); rel=rels[REL_ID]
    route_way_ids=[m["ref"] for m in rel["members"] if m["type"]=="way" and m["ref"] in ways and ways[m["ref"]]["tags"].get("railway")=="subway"]
    route_node_ids=sorted({nid for wid in route_way_ids for nid in ways[wid]["nodes"]})
    stop_members=[]
    for m in rel["members"]:
        if m["type"]=="node" and m["ref"] in nodes:
            n=nodes[m["ref"]]
            if m["role"] or n["tags"].get("public_transport") or n["tags"].get("railway") or n["tags"].get("name"):
                stop_members.append({"member":m,"node":n})
    op,op_url=fetch_connected_overpass(); op_nodes,op_ways=normalize_overpass(op); route_node_set=set(route_node_ids)
    connected={wid:w for wid,w in op_ways.items() if any(n in route_node_set for n in w["nodes"])}
    payload={"acquired_utc":time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime()),"relation_full_url":full_url,"overpass_endpoint":op_url,"relation":rel,"route_subway_way_ids":route_way_ids,"route_ways":{str(wid):ways[wid] for wid in route_way_ids},"route_nodes":{str(nid):nodes[nid] for nid in route_node_ids},"relation_node_members":stop_members,"connected_subway_ways":{str(k):v for k,v in connected.items()},"connected_nodes":{str(nid):op_nodes[nid] for w in connected.values() for nid in w["nodes"] if nid in op_nodes}}
    packed=base64.b64encode(gzip.compress(json.dumps(payload,separators=(",",":"),ensure_ascii=False).encode("utf-8"),compresslevel=9)).decode("ascii")
    chunks=[packed[i:i+6000] for i in range(0,len(packed),6000)]
    warnings.warn(f'OSM_LIVE_META chunks={len(chunks)} b64gzip_chars={len(packed)} relation_version={rel["version"]} route_ways={len(route_way_ids)} connected_ways={len(connected)}',UserWarning)
    for i,ch in enumerate(chunks,1):
        warnings.warn(f"OSM_LIVE_CHUNK {i}/{len(chunks)} {ch}",UserWarning)
    assert route_way_ids

# PR-triggered acquisition run

# synchronize-trigger
