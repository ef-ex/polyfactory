"""Runnable check for the cross-section profile maths.  No Houdini needed.

    python polyfactory/scripts/python/polyfactory/citygen/test_citygen.py
"""

import os
import sys
import unittest

# tests/unit -> repo root -> the polyfactory python package
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "polyfactory", "scripts",
                                "python", "polyfactory"))

from citygen import (  # noqa: E402
    ELEMENT_DEFAULTS,
    STARTER_TEMPLATES,
    build_profile_points,
    get_template,
    resolve_elements,
    street_summary,
    total_width,
)

EPS = 1e-9


class TestResolve(unittest.TestCase):

    def test_defaults_filled_from_type(self):
        [e] = resolve_elements([{"type": "sidewalk", "width": 2.0}])
        self.assertEqual(e["height"], ELEMENT_DEFAULTS["sidewalk"][0])
        self.assertEqual(e["walkable"], 1)
        self.assertEqual(e["drivable"], 0)

    def test_authored_value_beats_default(self):
        """Art direction rule: anything authored wins over anything computed."""
        [e] = resolve_elements([{"type": "sidewalk", "width": 2.0, "height": 0.9}])
        self.assertEqual(e["height"], 0.9)

    def test_unknown_type_does_not_raise(self):
        [e] = resolve_elements([{"type": "monorail_plinth", "width": 1.0}])
        self.assertEqual(e["height"], 0.0)
        self.assertEqual(e["index"], 0)

    def test_index_is_position_in_list(self):
        res = resolve_elements(STARTER_TEMPLATES["local_residential"])
        self.assertEqual([e["index"] for e in res], list(range(len(res))))


class TestProfile(unittest.TestCase):

    def test_two_points_per_element(self):
        els = STARTER_TEMPLATES["local_residential"]
        self.assertEqual(len(build_profile_points(els)), 2 * len(els))

    def test_profile_is_centred_and_spans_total_width(self):
        els = STARTER_TEMPLATES["arterial_median"]
        pts = build_profile_points(els)
        w = total_width(els)
        self.assertAlmostEqual(pts[0]["x"], -0.5 * w)
        self.assertAlmostEqual(pts[-1]["x"], 0.5 * w)

    def test_offset_shifts_whole_profile(self):
        els = STARTER_TEMPLATES["collector"]
        a = build_profile_points(els)
        b = build_profile_points(els, offset=3.0)
        for pa, pb in zip(a, b):
            self.assertAlmostEqual(pb["x"] - pa["x"], 3.0)

    def test_x_never_goes_backwards(self):
        for name, els in STARTER_TEMPLATES.items():
            pts = build_profile_points(els)
            for prev, cur in zip(pts, pts[1:]):
                self.assertGreaterEqual(cur["x"] + EPS, prev["x"], name)

    def test_u_cross_spans_zero_to_one(self):
        for name, els in STARTER_TEMPLATES.items():
            pts = build_profile_points(els)
            self.assertAlmostEqual(pts[0]["u_cross"], 0.0, msg=name)
            self.assertAlmostEqual(pts[-1]["u_cross"], 1.0, msg=name)
            for p in pts:
                self.assertGreaterEqual(p["u_cross"], -EPS, name)
                self.assertLessEqual(p["u_cross"], 1.0 + EPS, name)

    def test_kerb_riser_is_generated_where_heights_differ(self):
        """A sidewalk beside a lane must produce a vertical segment: two
        points sharing an x with different y.  This is the whole reason kerbs
        need no special-casing."""
        els = [{"type": "sidewalk", "width": 2.0}, {"type": "lane", "width": 3.0}]
        pts = build_profile_points(els)
        risers = [(a, b) for a, b in zip(pts, pts[1:])
                  if abs(a["x"] - b["x"]) < EPS and abs(a["y"] - b["y"]) > EPS]
        self.assertEqual(len(risers), 1)
        self.assertAlmostEqual(abs(risers[0][0]["y"] - risers[0][1]["y"]),
                               ELEMENT_DEFAULTS["sidewalk"][0])

    def test_no_riser_between_equal_height_elements(self):
        els = [{"type": "lane", "width": 3.0}, {"type": "lane", "width": 3.0}]
        pts = build_profile_points(els)
        risers = [1 for a, b in zip(pts, pts[1:])
                  if abs(a["x"] - b["x"]) < EPS and abs(a["y"] - b["y"]) > EPS]
        self.assertEqual(risers, [])

    def test_element_widths_are_preserved_in_profile(self):
        els = STARTER_TEMPLATES["boulevard_bus_bike"]
        res = resolve_elements(els)
        pts = build_profile_points(els)
        for e in res:
            pair = [p for p in pts if p["elem_index"] == e["index"]]
            self.assertEqual(len(pair), 2)
            self.assertAlmostEqual(pair[1]["x"] - pair[0]["x"], e["width"])

    def test_empty_template_yields_no_points(self):
        self.assertEqual(build_profile_points([]), [])

    def test_zero_width_template_does_not_divide_by_zero(self):
        self.assertEqual(build_profile_points([{"type": "lane", "width": 0.0}]), [])


class TestStreetSummary(unittest.TestCase):

    def test_street_width_matches_sum_of_elements(self):
        for name, els in STARTER_TEMPLATES.items():
            self.assertAlmostEqual(street_summary(els)["streetWidth"],
                                   total_width(els), msg=name)

    def test_sidewalk_widths_are_per_side(self):
        s = street_summary([{"type": "sidewalk", "width": 2.0},
                            {"type": "lane", "width": 3.0},
                            {"type": "sidewalk", "width": 4.0}])
        self.assertAlmostEqual(s["sidewalkWidthLeft"], 2.0)
        self.assertAlmostEqual(s["sidewalkWidthRight"], 4.0)

    def test_lane_width_is_mean_of_lanes_only(self):
        s = street_summary([{"type": "lane", "width": 3.0},
                            {"type": "lane", "width": 4.0},
                            {"type": "bus", "width": 9.0}])
        self.assertAlmostEqual(s["laneWidth"], 3.5)

    def test_no_lanes_does_not_divide_by_zero(self):
        s = street_summary([{"type": "sidewalk", "width": 2.0}])
        self.assertEqual(s["laneWidth"], 0.0)

    def test_empty_is_all_zero(self):
        self.assertEqual(street_summary([])["streetWidth"], 0.0)


class TestTemplates(unittest.TestCase):

    def test_every_starter_template_is_usable(self):
        for name, els in STARTER_TEMPLATES.items():
            self.assertGreater(total_width(els), 0.0, name)
            self.assertGreater(len(build_profile_points(els)), 0, name)

    def test_unknown_template_lists_the_valid_names(self):
        with self.assertRaises(KeyError) as ctx:
            get_template("does_not_exist")
        self.assertIn("local_residential", str(ctx.exception))

    def test_known_template_round_trips(self):
        self.assertIs(get_template("highway"), STARTER_TEMPLATES["highway"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
