import unittest

from tunnel_pcg_ref.osm_track_stitch import (
    candidate_subway_ways,
    stitch_relation_tracks,
)


def feat(idx, wid, refs, coords, role="", railway="subway"):
    return {
        "type": "Feature",
        "properties": {
            "member_index": idx,
            "member_role": role,
            "osm_way_id": wid,
            "osm_node_refs": refs,
            "osm_first_node_id": refs[0],
            "osm_last_node_id": refs[-1],
            "osm_railway": railway,
        },
        "geometry": {"type": "LineString", "coordinates": coords},
    }


class OSMTrackStitchTests(unittest.TestCase):
    def test_open_chain_orients_reversed_way(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(1, 10, [1, 2], [[37.0, 55.0], [37.1, 55.0]]),
                feat(2, 11, [3, 2], [[37.2, 55.0], [37.1, 55.0]]),
                feat(3, 12, [3, 4], [[37.2, 55.0], [37.3, 55.0]]),
            ],
        }
        tracks = stitch_relation_tracks(fc)
        self.assertEqual(len(tracks), 1)
        t = tracks[0]
        self.assertFalse(t.closed)
        self.assertEqual(t.node_ids, (1, 2, 3, 4))
        self.assertEqual(t.way_ids, (10, 11, 12))
        self.assertEqual(t.reversed_flags, (False, True, False))

    def test_closed_loop(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(2, 12, [3, 1], [[1, 1], [0, 0]]),
                feat(0, 10, [1, 2], [[0, 0], [1, 0]]),
                feat(1, 11, [2, 3], [[1, 0], [1, 1]]),
            ],
        }
        t = stitch_relation_tracks(fc)[0]
        self.assertTrue(t.closed)
        self.assertEqual(t.node_ids[0], t.node_ids[-1])
        self.assertEqual(set(t.way_ids), {10, 11, 12})

    def test_branch_is_rejected(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(0, 10, [1, 2], [[0, 0], [1, 0]]),
                feat(1, 11, [2, 3], [[1, 0], [2, 0]]),
                feat(2, 12, [2, 4], [[1, 0], [1, 1]]),
            ],
        }
        with self.assertRaises(ValueError):
            stitch_relation_tracks(fc)

    def test_non_subway_way_filtered(self):
        fc = {
            "type": "FeatureCollection",
            "features": [
                feat(0, 10, [1, 2], [[0, 0], [1, 0]]),
                feat(1, 11, [2, 3], [[1, 0], [2, 0]], railway="service"),
            ],
        }
        self.assertEqual(len(candidate_subway_ways(fc)), 1)


if __name__ == "__main__":
    unittest.main()
