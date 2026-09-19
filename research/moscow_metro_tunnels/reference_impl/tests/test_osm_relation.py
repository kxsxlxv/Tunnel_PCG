import unittest

from tunnel_pcg_ref.osm_relation import parse_relation_full_xml


XML = """<osm version="0.6">
<node id="1" lat="55.0" lon="37.0"/>
<node id="2" lat="55.1" lon="37.1"/>
<node id="3" lat="55.2" lon="37.2"/>
<way id="10"><nd ref="1"/><nd ref="2"/><tag k="railway" v="subway"/><tag k="tracks" v="1"/></way>
<way id="11"><nd ref="2"/><nd ref="3"/><tag k="railway" v="subway"/></way>
<relation id="1462012">
  <member type="node" ref="1" role="stop"/>
  <member type="way" ref="10" role="forward"/>
  <member type="way" ref="11" role="forward"/>
  <tag k="type" v="route"/><tag k="route" v="subway"/><tag k="ref" v="5"/>
</relation>
</osm>"""


class OSMRelationTests(unittest.TestCase):
    def test_parse_relation_full_xml(self):
        data = parse_relation_full_xml(XML, 1462012)
        self.assertEqual(data["properties"]["relation_tags"]["ref"], "5")
        self.assertEqual(data["properties"]["member_count"], 3)
        self.assertEqual(len(data["features"]), 2)
        self.assertEqual(
            data["features"][0]["properties"]["member_index"], 1
        )
        self.assertEqual(
            data["features"][0]["properties"]["osm_way_id"], 10
        )
        self.assertEqual(
            data["features"][0]["geometry"]["coordinates"][1],
            [37.1, 55.1],
        )
        self.assertFalse(data["properties"]["missing"])


if __name__ == "__main__":
    unittest.main()
