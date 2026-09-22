import unittest

from tunnel_pcg_ref.osm_track_graph import extract_physical_track_graph


def feat(idx, wid, refs, coords, role="", railway="subway", **tags):
    props = {
        "member_index": idx,
        "member_role": role,
        "osm_way_id": wid,
        "osm_node_refs": refs,
        "osm_first_node_id": refs[0],
        "osm_last_node_id": refs[-1],
        "osm_railway": railway,
    }
    props.update({f"osm_{k}": v for k, v in tags.items()})
    return {
        "type": "Feature",
        "properties": props,
        "geometry": {"type": "LineString", "coordinates": coords},
    }


class OSMTrackGraphTests(unittest.TestCase):
    def test_simple_two_track_loop(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(0, 100, [1, 2, 3, 1], [[0, 0], [1, 0], [0.5, 1], [0, 0]]),
                feat(1, 200, [4, 5, 6, 4], [[0, 2], [1, 2], [0.5, 3], [0, 2]]),
            ],
        }
        g = extract_physical_track_graph(fc)
        self.assertEqual(len(g["components"]), 2)
        self.assertEqual(len(g["edges"]), 2)
        self.assertTrue(all(n["degree"] == 2 for n in g["nodes"]))
        self.assertFalse(any(n["entity_type"] == "SWITCH_NODE" for n in g["nodes"]))

    def test_single_turnout_branch(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(0, 100, [1, 2, 3], [[0, 0], [1, 0], [2, 0]]),
                feat(1, 101, [2, 4], [[1, 0], [1.8, 0.7]]),
            ],
        }
        g = extract_physical_track_graph(fc)
        sw = [n for n in g["nodes"] if n["osm_node_id"] == 2][0]
        self.assertEqual(sw["entity_type"], "SWITCH_NODE")
        self.assertEqual(sw["degree"], 3)
        # The main way is split at its internal shared OSM node.
        main_parts = [e for e in g["edges"] if e["osm_way_id"] == 100]
        self.assertEqual(len(main_parts), 2)

    def test_crossover_between_two_tracks(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(0, 100, [1, 2, 3], [[0, 0], [1, 0], [2, 0]]),
                feat(1, 200, [4, 5, 6], [[0, 1], [1, 1], [2, 1]]),
                feat(2, 300, [2, 5], [[1, 0], [1, 1]]),
            ],
        }
        g = extract_physical_track_graph(fc)
        degree3 = {n["osm_node_id"] for n in g["nodes"] if n["degree"] == 3}
        self.assertEqual(degree3, {2, 5})
        self.assertEqual(len(g["components"]), 1)

    def test_depot_branch_preserves_service_tag_and_end_node(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(0, 100, [1, 2, 3], [[0, 0], [1, 0], [2, 0]]),
                feat(
                    1,
                    400,
                    [2, 7, 8],
                    [[1, 0], [1.5, -0.5], [2.0, -0.8]],
                    service="yard",
                ),
            ],
        }
        g = extract_physical_track_graph(fc)
        branch = [e for e in g["edges"] if e["osm_way_id"] == 400][0]
        self.assertEqual(branch["osm_properties"]["osm_service"], "yard")
        end = [n for n in g["nodes"] if n["osm_node_id"] == 8][0]
        self.assertEqual(end["entity_type"], "END_NODE")
        # The extractor must not pretend to know that this is a depot branch.
        self.assertEqual(branch["classification"], "unclassified_physical_track")

    def test_non_subway_platform_way_is_excluded(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(
                    0,
                    100,
                    [1, 2, 3],
                    [[0, 0], [1, 0], [2, 0]],
                ),
                feat(
                    1,
                    900,
                    [10, 11],
                    [[0.5, 0.2], [1.5, 0.2]],
                    railway="platform",
                ),
            ],
        }
        g = extract_physical_track_graph(fc)
        self.assertEqual({e["osm_way_id"] for e in g["edges"]}, {100})
        self.assertFalse(any(e["osm_way_id"] == 900 for e in g["edges"]))


if __name__ == "__main__":
    unittest.main()
