"""polyChain contracts and 4.1 DECOMPOSE. No Houdini, ~0.02s.

    python tests/unit/test_polychain.py

What this file is FOR: the section list is the input to every later stage, so
a wrong break here is a wrong plan, a wrong corner and a wrong id, and none of
those is visible in the viewport as "the section list is wrong". Each test
below pins one decision recorded in `polychain/decompose.py` (D7-D10) or one
house rule (determinism, warn-never-block), not an implementation detail.

The repo's habit, applied: a measurement made during a review belongs in a
test afterwards. Add to this file rather than re-deriving.
"""

import math
import os
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "polyfactory", "scripts", "python",
                                "polyfactory"))

import polychain as pc                                          # noqa: E402
from polychain import decompose as dc                           # noqa: E402


def line(*xs):
    """A polyline along +X at y = z = 0."""
    return [(float(x), 0.0, 0.0) for x in xs]


def square(size=10.0):
    return [(0.0, 0.0, 0.0), (size, 0.0, 0.0), (size, 0.0, size),
            (0.0, 0.0, size)]


class TestCurve(unittest.TestCase):

    def test_length_is_the_chord_sum(self):
        c = pc.Curve("c", line(0, 3, 7))
        self.assertAlmostEqual(c.length, 7.0, places=12)
        self.assertAlmostEqual(c.arclen(1), 3.0, places=12)

    def test_a_closed_curve_counts_its_closing_chord(self):
        c = pc.Curve("c", square(10.0), closed=True)
        self.assertAlmostEqual(c.length, 40.0, places=12)

    def test_sample_walks_the_polyline_and_reports_a_unit_tangent(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                           (10.0, 0.0, 10.0)])
        pos, tan = c.sample(15.0)
        self.assertAlmostEqual(pos[0], 10.0, places=9)
        self.assertAlmostEqual(pos[2], 5.0, places=9)
        self.assertAlmostEqual(tan[2], 1.0, places=9)
        self.assertAlmostEqual(math.sqrt(sum(t * t for t in tan)), 1.0, places=9)

    def test_a_closed_curve_wraps_instead_of_clamping(self):
        """D10: the wrapping section carries s1 > length, so sample() must
        wrap or every last section on a closed spline collapses onto the end."""
        c = pc.Curve("c", square(10.0), closed=True)
        a, _ = c.sample(2.0)
        b, _ = c.sample(42.0)
        self.assertAlmostEqual(a[0], b[0], places=9)
        self.assertAlmostEqual(a[2], b[2], places=9)

    def test_the_seam_of_a_closed_curve_has_two_tangents_like_any_vertex(self):
        """`forward` picks which side of a vertex is read, and the wrap threw
        that away at exactly one vertex: s == length folded to 0, so a closed
        loop's end frame reported the tangent LEAVING its first segment. 4.3
        bends corners off these frames."""
        c = pc.Curve("c", square(10.0), closed=True)
        _, leaving = c.sample(40.0, forward=True)
        _, arriving = c.sample(40.0, forward=False)
        self.assertAlmostEqual(leaving[0], 1.0, places=9)     # off along +x
        self.assertAlmostEqual(arriving[2], -1.0, places=9)   # in along -z
        self.assertAlmostEqual(c.sample(0.0, forward=True)[1][0], 1.0, places=9)

    def test_a_duplicate_point_does_not_break_sample(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (4.0, 0.0, 0.0)])
        pos, tan = c.sample(2.0)
        self.assertAlmostEqual(pos[0], 2.0, places=9)
        self.assertAlmostEqual(tan[0], 1.0, places=9)


class TestCorners(unittest.TestCase):

    def L(self, angle_deg, leg=10.0, **kw):
        a = math.radians(angle_deg)
        return pc.Curve("c", [(-leg, 0.0, 0.0), (0.0, 0.0, 0.0),
                              (leg * math.cos(a), 0.0, leg * math.sin(a))], **kw)

    def test_a_turn_over_the_threshold_is_a_corner_and_under_it_is_not(self):
        self.assertEqual(len(dc.resolve_corners(self.L(90.0))), 1)
        self.assertEqual(len(dc.resolve_corners(self.L(10.0))), 0)

    def test_the_threshold_is_the_TURN_not_the_included_angle(self):
        """D2. A 31 deg turn is a corner at the 30 deg default; its INCLUDED
        angle is 149 deg, and a threshold that read that would find nothing."""
        c = dc.resolve_corners(self.L(31.0))[0]
        self.assertAlmostEqual(c.turn_angle, 31.0, places=6)
        self.assertAlmostEqual(c.included_angle, 149.0, places=6)
        self.assertEqual(len(dc.resolve_corners(self.L(29.0))), 0)

    def test_force_and_suppress_override_the_threshold_both_ways(self):
        forced = self.L(5.0, corner_flags=[0, 1, 0])
        self.assertEqual(len(dc.resolve_corners(forced)), 1)
        self.assertTrue(dc.resolve_corners(forced)[0].forced)
        killed = self.L(90.0, corner_flags=[0, -1, 0])
        self.assertEqual(dc.resolve_corners(killed), [])

    def test_a_hairpin_is_degenerate_and_still_a_corner(self):
        """D9. 170 deg of turn leaves 10 deg between the legs - under the
        15 deg floor 4.3 falls back to bend at. It must still BREAK the
        section: hiding a hairpin inside a straight run is the worse failure."""
        c = dc.resolve_corners(self.L(170.0))[0]
        self.assertTrue(c.degenerate)
        self.assertIn(pc.WARN_CORNER_DEGENERATE, c.warns)
        self.assertEqual(len(dc.decompose(self.L(170.0))), 2)

    def test_a_non_degenerate_corner_carries_no_warning(self):
        self.assertEqual(dc.resolve_corners(self.L(90.0))[0].warns, ())

    def test_a_duplicate_vertex_is_collapsed_not_read_as_a_corner(self):
        """D8. A repeated point has no direction, so it can neither confirm
        nor deny a turn - and a naive acos on a zero vector is a crash."""
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                           (10.0, 0.0, 0.0)])
        self.assertEqual(dc.resolve_corners(c), [])
        secs = dc.decompose(c)
        self.assertEqual(len(secs), 1)
        self.assertAlmostEqual(secs[0].length, 10.0, places=9)

    def test_the_flag_is_read_at_the_ORIGINAL_point_index(self):
        """The cleaned polyline is an internal convenience; `pc_corner` is
        authored on the points the artist can see. Mapping the flag through
        the cleaned index would silently shift it past every duplicate."""
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                           (10.0, 0.0, 0.0), (15.0, 0.0, 0.0)],
                     corner_flags=[0, 0, 0, 1, 0])
        got = dc.resolve_corners(c)
        self.assertEqual([x.point_index for x in got], [3])

    def test_a_bad_flag_value_warns_by_doing_nothing_rather_than_raising(self):
        c = self.L(90.0, corner_flags=[0, "not an int", 0])
        self.assertEqual(len(dc.resolve_corners(c)), 1)      # auto still applies


class TestSections(unittest.TestCase):

    def test_an_open_polyline_with_no_corner_is_one_section(self):
        secs = dc.decompose(pc.Curve("c", line(0, 4, 9)))
        self.assertEqual(len(secs), 1)
        self.assertAlmostEqual(secs[0].s0, 0.0, places=12)
        self.assertAlmostEqual(secs[0].s1, 9.0, places=12)
        self.assertIsNone(secs[0].start_corner)
        self.assertIsNone(secs[0].end_corner)

    def test_sections_tile_the_curve_exactly(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                           (10.0, 0.0, 10.0), (20.0, 0.0, 10.0)])
        secs = dc.decompose(c)
        self.assertEqual(len(secs), 3)
        self.assertAlmostEqual(sum(s.length for s in secs), c.length, places=12)
        for a, b in zip(secs, secs[1:]):
            self.assertAlmostEqual(a.s1, b.s0, places=12)

    def test_each_boundary_carries_its_corner_angle_and_its_frames(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                           (10.0, 0.0, 10.0)])
        a, b = dc.decompose(c)
        self.assertAlmostEqual(a.as_dict()["end_angle"], 90.0, places=6)
        self.assertAlmostEqual(b.as_dict()["start_angle"], 90.0, places=6)
        self.assertAlmostEqual(a.end_frame[0][0], 10.0, places=9)
        self.assertAlmostEqual(b.start_frame[1][2], 1.0, places=9)

    def test_u_is_the_fraction_along_the_PARENT_curve(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                           (10.0, 0.0, 10.0)])
        a, b = dc.decompose(c)
        self.assertAlmostEqual(b.u0, 0.5, places=12)
        self.assertAlmostEqual(b.u_at(5.0), 0.75, places=12)

    def test_a_closed_square_breaks_at_all_four_corners(self):
        secs = dc.decompose(pc.Curve("c", square(10.0), closed=True))
        self.assertEqual(len(secs), 4)
        self.assertAlmostEqual(sum(s.length for s in secs), 40.0, places=12)
        self.assertFalse(any(s.closed for s in secs))

    def test_a_closed_curve_with_no_corners_is_ONE_closed_section(self):
        """D10, and RailClone's own documented limit about the closing vertex:
        a corner-free loop is one section, and start/end are unused on it."""
        pts = [(10.0 * math.cos(t * math.pi / 12.0), 0.0,
                10.0 * math.sin(t * math.pi / 12.0)) for t in range(24)]
        secs = dc.decompose(pc.Curve("c", pts, closed=True))
        self.assertEqual(len(secs), 1)
        self.assertTrue(secs[0].closed)
        self.assertAlmostEqual(secs[0].length, secs[0].curve_length, places=12)

    def test_the_closing_vertex_is_a_corner_candidate_like_any_other(self):
        """The square's fourth corner is AT point 0, which an open-curve
        implementation skips. Four sections, not three."""
        secs = dc.decompose(pc.Curve("c", square(10.0), closed=True))
        self.assertEqual(sorted(round(s.length, 6) for s in secs), [10.0] * 4)

    def test_a_repeated_closing_point_is_not_a_fifth_vertex(self):
        pts = square(10.0) + [(0.0, 0.0, 0.0)]
        secs = dc.decompose(pc.Curve("c", pts, closed=True))
        self.assertEqual(len(secs), 4)

    def test_pc_section_breaks_the_curve_where_the_value_changes(self):
        """D7: a per-POINT list is the only shape that can express a mid-curve
        limit, which is the entire purpose of 3.1's `pc_section`."""
        c = pc.Curve("c", line(0, 2, 4, 6, 8), section_ids=[1, 1, 1, 2, 2])
        secs = dc.decompose(c)
        self.assertEqual(len(secs), 2)
        self.assertAlmostEqual(secs[0].s1, 6.0, places=12)
        self.assertEqual([s.section_key for s in secs], [1, 2])

    def test_a_pc_section_change_at_the_LAST_point_makes_no_phantom_section(self):
        """The corner rules already exclude an open curve's endpoints; the
        section rules did not, so a trailing value change emitted a
        zero-length section past the end - and shifted every section index,
        which is half of `pc_elem_id`. The final segment keeps the earlier
        key: a break at the far end of a segment cannot split it."""
        c = pc.Curve("c", line(0, 5, 10), section_ids=[0, 0, 1])
        secs = dc.decompose(c)
        self.assertEqual(len(secs), 1)
        self.assertEqual(secs[0].section_key, 0)
        self.assertAlmostEqual(secs[0].length, 10.0, places=12)
        for s in dc.decompose(pc.Curve("c", line(0, 5, 10, 15),
                                       section_ids=[0, 1, 1, 2])):
            self.assertGreater(s.length, 0.0)

    def test_only_a_spline_end_or_a_section_limit_carries_a_cap(self):
        """D18: start/end modules cap a RUN. A corner is not the end of one -
        RailClone puts corner segments there - and a closed spline has no run
        end at all, so it gets no caps on any of its sides."""
        l_shape = dc.decompose(pc.Curve("c", [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                                              (5.0, 0.0, 5.0)]))
        self.assertEqual([(s.start_cap, s.end_cap) for s in l_shape],
                         [(True, False), (False, True)])
        for s in dc.decompose(pc.Curve("c", square(10.0), closed=True)):
            self.assertFalse(s.start_cap or s.end_cap)
        limits = dc.decompose(pc.Curve("c", line(0, 5, 10, 15),
                                       section_ids=[1, 1, 2, 2]))
        self.assertEqual([(s.start_cap, s.end_cap) for s in limits],
                         [(True, True), (True, True)])

    def test_a_scalar_pc_section_is_the_whole_curve_key_and_breaks_nothing(self):
        c = pc.Curve("c", line(0, 2, 4, 6), section_ids=7)
        secs = dc.decompose(c)
        self.assertEqual(len(secs), 1)
        self.assertEqual(secs[0].section_key, 7)

    def test_a_corner_and_a_section_break_at_the_same_vertex_break_once(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                           (10.0, 0.0, 10.0)], section_ids=[1, 2, 2])
        self.assertEqual(len(dc.decompose(c)), 2)


class TestDegenerateInput(unittest.TestCase):
    """Warn-never-block: none of these may raise, and none may hang."""

    def test_an_empty_curve_yields_nothing(self):
        self.assertEqual(dc.decompose(pc.Curve("c", [])), [])

    def test_a_single_point_yields_nothing(self):
        self.assertEqual(dc.decompose(pc.Curve("c", [(0.0, 0.0, 0.0)])), [])

    def test_a_curve_of_coincident_points_yields_nothing(self):
        c = pc.Curve("c", [(1.0, 2.0, 3.0)] * 5)
        self.assertEqual(dc.decompose(c), [])
        self.assertEqual(dc.resolve_corners(c), [])
        self.assertAlmostEqual(c.length, 0.0, places=12)

    def test_a_two_point_curve_has_no_interior_vertex_to_corner(self):
        self.assertEqual(dc.resolve_corners(pc.Curve("c", line(0, 5))), [])
        self.assertEqual(len(dc.decompose(pc.Curve("c", line(0, 5)))), 1)

    def test_a_closed_two_point_curve_does_not_explode(self):
        c = pc.Curve("c", line(0, 5), closed=True)
        self.assertEqual(len(dc.decompose(c)), 1)


class TestMarkers(unittest.TestCase):

    def test_u_and_distance_and_negative_distance_all_resolve_to_metres(self):
        c = pc.Curve("c", line(0, 20))
        self.assertAlmostEqual(pc.Marker("c", u=0.25).distance_on(c), 5.0, 9)
        self.assertAlmostEqual(pc.Marker("c", dist=7.0).distance_on(c), 7.0, 9)
        self.assertAlmostEqual(pc.Marker("c", dist=-3.0).distance_on(c), 17.0, 9)

    def test_an_out_of_range_marker_is_clamped_not_dropped(self):
        c = pc.Curve("c", line(0, 20))
        self.assertAlmostEqual(pc.Marker("c", dist=99.0).distance_on(c), 20.0, 9)
        self.assertAlmostEqual(pc.Marker("c", u=-1.0).distance_on(c), 0.0, 9)

    def test_markers_land_in_the_section_that_holds_them_exactly_once(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                           (10.0, 0.0, 10.0)])
        ms = [pc.Marker("c", dist=4.0, marker_id=1),
              pc.Marker("c", dist=14.0, marker_id=2),
              pc.Marker("other", dist=4.0, marker_id=3)]
        secs = dc.decompose(c, ms)
        self.assertEqual([[m["marker_id"] for m in s.markers] for s in secs],
                         [[1], [2]])
        self.assertAlmostEqual(secs[1].markers[0]["s_local"], 4.0, places=9)

    def test_a_marker_on_a_boundary_is_placed_once_not_twice(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                           (10.0, 0.0, 10.0)])
        secs = dc.decompose(c, [pc.Marker("c", dist=10.0, marker_id=1)])
        self.assertEqual(sum(len(s.markers) for s in secs), 1)

    def test_marker_data_rides_along(self):
        c = pc.Curve("c", line(0, 10))
        secs = dc.decompose(c, [pc.Marker("c", u=0.5, marker_id=4,
                                          data={"width": 3.0})])
        self.assertEqual(secs[0].markers[0]["data"], {"width": 3.0})


class TestDeterminism(unittest.TestCase):
    """The house rule: same inputs + seed => identical output, across
    processes and across recooks. Everything here is one property."""

    def test_seed_for_never_depends_on_a_point_number(self):
        style = pc.Style("s", seed=7)
        base = {"curve_id": "c", "section_index": 1, "slot": "default",
                "index": 3}
        self.assertEqual(pc.seed_for(style, "segment", base),
                         pc.seed_for(style, "segment", dict(base, ptnum=99)))

    def test_each_scope_correlates_exactly_what_it_says_it_does(self):
        style = pc.Style("s", seed=7)
        a = {"curve_id": "c", "section_index": 1, "slot": "default", "index": 3}
        b = dict(a, index=4)
        c = dict(a, section_index=2)
        d = dict(a, curve_id="d")
        self.assertNotEqual(pc.seed_for(style, "segment", a),
                            pc.seed_for(style, "segment", b))
        self.assertEqual(pc.seed_for(style, "section", a),
                         pc.seed_for(style, "section", b))
        self.assertNotEqual(pc.seed_for(style, "section", a),
                            pc.seed_for(style, "section", c))
        self.assertEqual(pc.seed_for(style, "spline", a),
                         pc.seed_for(style, "spline", c))
        self.assertNotEqual(pc.seed_for(style, "spline", a),
                            pc.seed_for(style, "spline", d))
        self.assertEqual(pc.seed_for(style, "generator", a),
                         pc.seed_for(style, "generator", d))

    def test_the_style_seed_and_the_style_id_both_move_the_seed(self):
        ctx = {"curve_id": "c", "section_index": 0, "slot": "default",
               "index": 0}
        s1 = pc.seed_for(pc.Style("s", seed=1), "segment", ctx)
        s2 = pc.seed_for(pc.Style("s", seed=2), "segment", ctx)
        s3 = pc.seed_for(pc.Style("t", seed=1), "segment", ctx)
        self.assertNotEqual(s1, s2)
        self.assertNotEqual(s1, s3)

    def test_the_seed_survives_PYTHONHASHSEED_which_builtin_hash_does_not(self):
        """The one that would have been missed. `hash("x")` differs per
        PROCESS, so a hash()-derived seed gives a different plan on every
        recook in a fresh session - green in-process, broken in production."""
        snippet = (
            "import sys; sys.path.insert(0, %r);"
            "import polychain as pc;"
            "print(pc.seed_for(pc.Style('s', seed=7), 'segment',"
            "                  {'curve_id': 'c', 'section_index': 1,"
            "                   'slot': 'default', 'index': 3}))"
            % os.path.join(REPO, "polyfactory", "scripts", "python",
                           "polyfactory"))
        got = []
        for hashseed in ("0", "1", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=hashseed)
            got.append(subprocess.check_output([sys.executable, "-c", snippet],
                                               env=env).strip())
        self.assertEqual(len(set(got)), 1, got)

    def test_elem_id_is_a_structural_address_and_never_cook_order(self):
        """D1. It must be reproducible from the structure alone, and two
        different structures must never share one."""
        a = pc.elem_id("edge_7", 2, "default", 5, "fence")
        self.assertEqual(a, "edge_7|2|default|5|fence")
        self.assertEqual(a, pc.elem_id("edge_7", 2, "default", 5, "fence"))
        self.assertNotEqual(a, pc.elem_id("edge_7", 2, "default", 6, "fence"))
        self.assertNotEqual(a, pc.elem_id("edge_7", 2, "start", 5, "fence"))
        self.assertNotEqual(a, pc.elem_id("edge_7", 2, "default", 5, "rail"))

    def test_elem_key_is_a_grouping_int_derived_from_the_address(self):
        a = pc.elem_id("edge_7", 2, "default", 5, "fence")
        self.assertEqual(pc.elem_key(a), pc.elem_key(a))
        self.assertGreaterEqual(pc.elem_key(a), 0)
        self.assertLess(pc.elem_key(a), 2 ** 31)

    def test_decompose_all_is_independent_of_the_order_the_curves_arrive_in(self):
        curves = [pc.Curve("b", line(0, 10)), pc.Curve("a", line(0, 5)),
                  pc.Curve("c", line(0, 7))]
        one = [s.as_dict() for s in dc.decompose_all(curves)]
        two = [s.as_dict() for s in dc.decompose_all(list(reversed(curves)))]
        self.assertEqual(one, two)
        self.assertEqual([s["curve_id"] for s in one], ["a", "b", "c"])


class TestKit(unittest.TestCase):

    def test_a_missing_module_is_a_stand_in_and_never_a_failure(self):
        kit = pc.Kit("k", modules=[pc.Module("panel", (2.0, 1.0, 0.1))])
        got = kit.resolve("nope")
        self.assertEqual(len(got), 1)
        self.assertTrue(got[0].missing)
        self.assertAlmostEqual(got[0].length, 1.0, places=9)

    def test_a_name_wins_over_a_role_and_a_role_returns_payload_order(self):
        mods = [pc.Module("a", (1.0, 1, 1), roles="default post"),
                pc.Module("b", (2.0, 1, 1), roles="default"),
                pc.Module("post", (3.0, 1, 1), roles="post")]
        kit = pc.Kit("k", modules=mods)
        self.assertEqual([m.name for m in kit.resolve("post")], ["post"])
        self.assertEqual([m.name for m in kit.by_role("post")], ["a", "post"])
        self.assertEqual([m.name for m in kit.resolve("default")], ["a", "b"])

    def test_moduleRole_is_accepted_as_an_alias_for_pc_role(self):
        """D4, the buildings 12.9 convergence - one line, no meeting."""
        kit = pc.kit_from_records([
            {"pc_name": "bay", "pc_size": (3.0, 3.0, 0.5), "moduleRole": "start"},
            {"pc_name": "win", "pc_size": (3.0, 3.0, 0.5), "pc_role": "default",
             "moduleRole": "ignored"}])
        self.assertEqual([m.name for m in kit.by_role("start")], ["bay"])
        self.assertEqual([m.name for m in kit.by_role("default")], ["win"])

    def test_a_scalar_size_is_read_as_a_length(self):
        self.assertAlmostEqual(pc.Module("m", 2.5).length, 2.5, places=9)


class TestConformContract(unittest.TestCase):
    """4.5's hou-free half: the axis parm and the per-module camber switch.

    The drape itself needs a licence and is measured in `tests/polychain`
    (`conform_contact_m`, `conform_drape_m`, `camber_deg`); these two
    decisions are pure data and belong here, where they cost nothing.
    """

    def test_the_axis_defaults_to_houdini_down(self):
        # D51: 4.5's "-Z" is Max's up axis. Houdini is Y-up (D20's same
        # translation), so the default must be -Y or every fence conforms
        # sideways.
        self.assertEqual(pc.DEFAULTS.conform_axis, (0.0, -1.0, 0.0))

    def test_a_zero_axis_degrades_to_the_default(self):
        self.assertEqual(pc.Params(conform_axis=(0.0, 0.0, 0.0)).conform_axis,
                         (0.0, -1.0, 0.0))

    def test_the_axis_is_a_direction_not_a_menu(self):
        p = pc.Params(conform_axis=(1.0, 0.0, 0.0))
        self.assertEqual(p.conform_axis, (1.0, 0.0, 0.0))

    def test_camber_is_off_by_default(self):
        self.assertFalse(pc.DEFAULTS.conform_tilt)

    def test_a_module_defers_to_the_style_by_default(self):
        # D55 = D6's three-state pattern: -1 means "the style decides".
        m = pc.Module("m", (1.0, 1.0, 0.1))
        self.assertEqual(m.tilt, -1)
        self.assertFalse(m.tilts(pc.Params()))
        self.assertTrue(m.tilts(pc.Params(conform_tilt=True)))

    def test_a_module_can_veto_or_force_the_camber(self):
        never = pc.Module("kerb", (1.0, 1.0, 0.1), tilt=0)
        always = pc.Module("road", (1.0, 1.0, 0.1), tilt=1)
        self.assertFalse(never.tilts(pc.Params(conform_tilt=True)))
        self.assertTrue(always.tilts(pc.Params(conform_tilt=False)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
