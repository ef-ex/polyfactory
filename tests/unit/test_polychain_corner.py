"""polyChain 4.3 CORNERS - the hou-free half, tested in milliseconds.

Same contract as `test_polychain.py` and `test_polychain_plan.py`: nothing
here imports Houdini, every number is an INVARIANT rather than a measurement
(the measurements live in `tests/polychain/`, against built geometry), and
every assertion is one the spec or `railclone.md` can be pointed at.

The four things this file is here to pin, because the geometry checks cannot
see any of them without a licence:

  * the miter arithmetic - `e = h * tan(turn/2)` and the bisector normal -
    which is the whole of 4.3 in two lines and is where a sign error hides;
  * the compose layout's odd/even symmetry (D38), as an exact equality on the
    reserves rather than as a picture;
  * that bend WELDS and miter does not (D36), including the degenerate
    fallback that welds in miter mode too (D46);
  * that every degenerate input still returns a plan - warn-never-block, with
    the warning actually on a placement.
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "polyfactory", "scripts", "python"))

from polyfactory.polychain import (DEFAULTS, Curve, Kit, Module, Params, Rule,  # noqa: E402
                                   Style, WARN_CORNER_DEGENERATE,
                                   WARN_FILLET_CLAMPED, WARN_OVERFLOW)
from polyfactory.polychain import corner as C                       # noqa: E402
from polyfactory.polychain import decompose as D                    # noqa: E402


def fence_kit():
    return Kit("t", 1, [
        Module("panel", (2.0, 0.9, 0.06), deform=1, roles="default"),
        Module("post", (0.16, 1.3, 0.16), deform=0, roles="corner"),
        Module("block", (1.2, 1.3, 0.16), deform=0, roles="corner"),
    ], 1.8)


def style(mode="miter", offset=0.0, fillet=0.0, displacement="reset",
          corner=("post",), select="first"):
    rules = [Rule("default", "first", ["panel"])]
    if corner:
        rules.append(Rule("corner", select, list(corner)))
    return Style("t", 1, 1, rules=rules,
                 params=Params(fill="adaptive", corner_mode=mode,
                               corner_offset_pct=offset, fillet_radius=fillet,
                               corner_displacement=displacement))


L = [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 0.0, 12.0)]
RECT = [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 0.0, 8.0), (0.0, 0.0, 8.0)]


def run(points, st, closed=False, params=None):
    curve = Curve("c", points, closed=closed)
    p = params or st.params
    curve, _w = C.fillet(curve, p)
    sections = D.decompose(curve, (), p)
    return C.plan_curve(curve, sections, fence_kit(), st, p)


class TestBevel(unittest.TestCase):
    """The miter arithmetic. Two lines of trigonometry that everything else
    in 4.3 is built on."""

    def bevel(self, tin, tout, params=DEFAULTS):
        corner = D.Corner("c", 1, (0.0, 0.0, 0.0),
                          C._turn_deg((-tin[0], -tin[1], -tin[2]),
                                      (0.0, 0.0, 0.0), tout))
        return C.Bevel(corner, (0.0, 0.0, 0.0), tin, tout, params)

    def test_right_angle_normal_bisects(self):
        b = self.bevel((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        self.assertAlmostEqual(b.turn, 90.0, places=9)
        r = math.sqrt(0.5)
        for got, want in zip(b.n, (r, 0.0, r)):
            self.assertAlmostEqual(got, want, places=9)
        # n.tin == n.tout == cos(turn/2) is the property the whole cut relies
        # on: both legs meet the plane at the same angle, so the two halves
        # of the joint are congruent.
        self.assertAlmostEqual(C._dot(b.n, b.tin), math.cos(math.pi / 4),
                               places=9)
        self.assertAlmostEqual(C._dot(b.n, b.tin), C._dot(b.n, b.tout),
                               places=12)

    def test_overhang_is_half_width_times_tan_half(self):
        for turn, tout in ((90.0, (0.0, 0.0, 1.0)),
                           (45.0, (math.sqrt(0.5), 0.0, math.sqrt(0.5))),
                           (120.0, (-0.5, 0.0, math.sqrt(0.75)))):
            b = self.bevel((1.0, 0.0, 0.0), tout)
            self.assertAlmostEqual(b.turn, turn, places=6)
            self.assertAlmostEqual(
                b.e_for(0.03), 0.03 * math.tan(math.radians(turn) / 2.0),
                places=9)

    def test_reflex_only_flips_the_side(self):
        left = self.bevel((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        right = self.bevel((1.0, 0.0, 0.0), (0.0, 0.0, -1.0))
        self.assertEqual(left.side, 1.0)
        self.assertEqual(right.side, -1.0)
        # a reflex corner is the same miter, mirrored: same turn, same
        # overhang, and a normal that still bisects
        self.assertAlmostEqual(left.turn, right.turn, places=9)
        self.assertAlmostEqual(left.e_for(0.03), right.e_for(0.03), places=12)

    def test_offset_parts_the_two_planes_by_2_o_cos_half(self):
        b = self.bevel((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        b.offset = 0.04
        oin = b.plane_in()[0]
        oout = b.plane_out()[0]
        sep = C._dot(b.n, C._sub(oout, oin))
        self.assertAlmostEqual(sep, 2 * 0.04 * math.cos(math.pi / 4), places=9)
        self.assertEqual(b.plane_in()[2], -1.0)     # keep sides are opposite
        self.assertEqual(b.plane_out()[2], 1.0)

    def test_hairpin_degenerates_and_never_divides_by_zero(self):
        b = self.bevel((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0))
        self.assertTrue(b.degenerate)
        self.assertEqual(b.mode, "bend")            # 4.3's own fallback
        self.assertLessEqual(abs(b.tan_half), C.MAX_TAN_HALF)
        self.assertTrue(all(v == v for v in b.n))   # not NaN
        self.assertIn(WARN_CORNER_DEGENERATE, b.warns)

    def test_narrow_angle_threshold_is_the_included_angle(self):
        # 170 degrees of TURN is 10 degrees of included angle, under the
        # 15 degree default - D2's two-angles decision, still holding
        t = math.radians(170.0)
        b = self.bevel((1.0, 0.0, 0.0), (math.cos(t), 0.0, math.sin(t)))
        self.assertTrue(b.degenerate)
        b2 = self.bevel((1.0, 0.0, 0.0), (math.cos(t), 0.0, math.sin(t)),
                        Params(min_included_angle_deg=5.0))
        self.assertFalse(b2.degenerate)


class TestCompose(unittest.TestCase):
    """D38 - the odd/even rule, as an exact equality on the reserves."""

    def assembly(self, names, mode="miter", offset=0.0):
        kit = fence_kit()
        mods = [kit.by_name(n) for n in names]
        b = C.Bevel(D.Corner("c", 1, (0, 0, 0), 90.0), (0.0, 0.0, 0.0),
                    (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), DEFAULTS)
        b.mode = mode
        return C.build_assembly(b, mods, None,
                                Params(corner_mode=mode,
                                       corner_offset_pct=offset))

    def test_single_module_is_duplicated_both_sides(self):
        a = self.assembly(["post"])
        self.assertEqual(len(a.pieces), 2)
        self.assertEqual(sorted(p.side for p in a.pieces), ["in", "out"])
        self.assertTrue(all(p.duplicate for p in a.pieces))
        # and each copy reaches PAST the vertex by the overhang, which is what
        # leaves its outside face at the module's full length after the cut
        e = a.bevel.e_for(0.08)
        for piece in a.pieces:
            self.assertAlmostEqual(piece.t_near, -e, places=9)
            self.assertAlmostEqual(piece.t_far - piece.t_near, 0.16, places=9)

    def test_odd_is_symmetric_even_is_not(self):
        odd = self.assembly(["post", "block", "post"])
        self.assertAlmostEqual(odd.symmetry, 0.0, places=12)
        even = self.assembly(["post", "block"])
        self.assertAlmostEqual(even.symmetry, 1.2, places=9)
        five = self.assembly(["post", "post", "block", "post", "post"])
        self.assertAlmostEqual(five.symmetry, 0.0, places=12)
        four = self.assembly(["post", "block", "post", "block"])
        self.assertGreater(four.symmetry, 1e-6)

    def test_the_straddler_is_the_middle_of_an_odd_compose(self):
        a = self.assembly(["post", "block", "post"])
        straddlers = [p for p in a.pieces if p.duplicate]
        self.assertEqual(len(straddlers), 2)
        self.assertTrue(all(p.compose_index == 1 for p in straddlers))
        self.assertTrue(all(p.module.name == "block" for p in straddlers))

    def test_an_even_compose_centres_the_segment_before_the_vertex(self):
        # iToo: "If there is an even number of inputs, RailClone centres the
        # geometry to the 1st segment in the Compose node."
        a = self.assembly(["post", "block"])
        straddlers = [p for p in a.pieces if p.duplicate]
        self.assertTrue(all(p.compose_index == 0 for p in straddlers))
        self.assertTrue(all(p.module.name == "post" for p in straddlers))

    def test_bend_neither_duplicates_nor_overhangs(self):
        a = self.assembly(["post"], mode="bend")
        self.assertEqual(len(a.pieces), 1)
        self.assertFalse(a.pieces[0].duplicate)
        self.assertAlmostEqual(a.pieces[0].t_far, 0.08, places=9)
        self.assertAlmostEqual(a.pieces[0].t_near, -0.08, places=9)

    def test_offset_is_a_percentage_of_the_straddler(self):
        a = self.assembly(["post"], offset=25.0)
        self.assertAlmostEqual(a.bevel.offset, 0.25 * 0.16, places=12)
        b = self.assembly(["block"], offset=25.0)
        self.assertAlmostEqual(b.bevel.offset, 0.25 * 1.2, places=12)


class TestDisplacement(unittest.TestCase):
    """D40 - the three policies are three different numbers, and only in
    miter mode."""

    def bevel(self, mode="miter", offset=0.0):
        b = C.Bevel(D.Corner("c", 1, (0, 0, 0), 90.0), (0.0, 0.0, 0.0),
                    (1.0, 0.0, 0.0), (0.0, 0.0, 1.0), DEFAULTS)
        b.mode = mode
        b.offset = offset
        return b

    def test_three_policies_three_numbers(self):
        panel = fence_kit().by_name("panel")
        got = dict(
            (policy, C.displacement(self.bevel(), panel,
                                    Params(corner_displacement=policy)))
            for policy in ("reset", "extend", "symmetric"))
        self.assertAlmostEqual(got["reset"], 0.0, places=12)
        self.assertAlmostEqual(got["extend"], 0.03 * math.tan(math.pi / 4),
                               places=9)
        self.assertAlmostEqual(got["symmetric"], 1.0, places=12)
        self.assertEqual(len(set(round(v, 9) for v in got.values())), 3)

    def test_bend_never_displaces(self):
        panel = fence_kit().by_name("panel")
        for policy in ("reset", "extend", "symmetric"):
            self.assertEqual(
                C.displacement(self.bevel(mode="bend"), panel,
                               Params(corner_displacement=policy)), 0.0)

    def test_offset_shifts_all_three(self):
        panel = fence_kit().by_name("panel")
        for policy in ("reset", "extend", "symmetric"):
            p = Params(corner_displacement=policy)
            a = C.displacement(self.bevel(), panel, p)
            b = C.displacement(self.bevel(offset=0.05), panel, p)
            self.assertAlmostEqual(a - b, 0.05, places=12)

    def test_an_unknown_policy_degrades_to_reset(self):
        self.assertEqual(Params(corner_displacement="Extend"
                                ).corner_displacement, "reset")


class TestMerge(unittest.TestCase):
    """D36/D46 - bend welds, miter does not, and a degenerate corner welds
    whatever the mode says."""

    def sections(self, points, closed=False, params=DEFAULTS):
        return D.decompose(Curve("c", points, closed=closed), (), params)

    def test_bend_welds_an_l_into_one_run(self):
        secs = self.sections(L)
        self.assertEqual(len(secs), 2)
        merged = C.merge_bend_sections(secs, False, Params(corner_mode="bend"))
        self.assertEqual(len(merged), 1)
        self.assertAlmostEqual(merged[0].length, 24.0, places=9)

    def test_miter_leaves_them_alone(self):
        secs = self.sections(L)
        merged = C.merge_bend_sections(secs, False, Params(corner_mode="miter"))
        self.assertEqual(len(merged), 2)

    def test_a_closed_ring_welds_to_one_closed_section(self):
        secs = self.sections(RECT, closed=True)
        self.assertEqual(len(secs), 4)
        merged = C.merge_bend_sections(secs, True, Params(corner_mode="bend"))
        self.assertEqual(len(merged), 1)
        self.assertTrue(merged[0].closed)
        self.assertAlmostEqual(merged[0].length, 40.0, places=9)
        # D18 still holds through the weld: a closed spline gets no caps
        self.assertFalse(merged[0].start_cap)
        self.assertFalse(merged[0].end_cap)

    def test_a_pc_section_limit_is_never_welded(self):
        curve = Curve("c", L, section_ids=[0, 1, 1])
        secs = D.decompose(curve, (), DEFAULTS)
        merged = C.merge_bend_sections(secs, False, Params(corner_mode="bend"))
        self.assertEqual(len(merged), len(secs))

    def test_a_degenerate_corner_welds_in_miter_mode_too(self):
        hairpin = [(0.0, 0.0, 0.0), (6.0, 0.0, 0.0), (0.5, 0.0, 1.05)]
        secs = self.sections(hairpin)
        self.assertEqual(len(secs), 2)
        self.assertTrue(secs[1].start_corner.degenerate)
        merged = C.merge_bend_sections(secs, False, Params(corner_mode="miter"))
        self.assertEqual(len(merged), 1)

    def test_the_weld_keeps_the_first_index(self):
        # `pc_elem_id` is a structural address (D1): welding two sections may
        # not renumber the run, or every override keyed on it breaks
        secs = self.sections(RECT, closed=True)
        merged = C.merge_bend_sections(secs, True, Params(corner_mode="bend"))
        self.assertEqual(merged[0].index, secs[0].index)


class TestFillet(unittest.TestCase):
    """4.3 item E, and D42/D43."""

    def test_the_arc_is_tangent_and_on_the_radius(self):
        params = Params(fillet_radius=1.5, fillet_segments=8)
        out, warns = C.fillet(Curve("c", L), params)
        self.assertEqual(warns, ())
        v = (12.0, 0.0, 0.0)
        centre = (12.0 - 1.5, 0.0, 1.5)
        arc = [p for p in out.points
               if 1e-6 < math.hypot(p[0] - v[0], p[2] - v[2]) < 3.0]
        self.assertEqual(len(arc), 9)               # segments + 1
        for p in arc:
            self.assertAlmostEqual(
                math.hypot(p[0] - centre[0], p[2] - centre[2]), 1.5, places=9)

    def test_the_arc_midpoint_is_the_only_forced_corner(self):
        params = Params(fillet_radius=1.5, fillet_segments=4)
        out, _w = C.fillet(Curve("c", L), params)
        self.assertEqual(out.corner_flags.count(1), 1)
        self.assertEqual(out.corner_flags.count(-1), 4)
        # ...and decompose therefore still finds exactly one corner
        self.assertEqual(len(D.resolve_corners(out, params)), 1)

    def test_the_filleted_run_is_shorter_than_the_sharp_one(self):
        params = Params(fillet_radius=1.5)
        out, _w = C.fillet(Curve("c", L), params)
        self.assertLess(out.length, 24.0)
        self.assertGreater(out.length, 22.0)

    def test_a_radius_too_big_for_its_legs_is_clamped_and_warns(self):
        short = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 1.0)]
        out, warns = C.fillet(Curve("c", short), Params(fillet_radius=50.0))
        self.assertIn(WARN_FILLET_CLAMPED, warns)
        self.assertGreater(out.length, 0.0)
        # D43's own promise: the tangent distance never exceeds 45 % of a leg,
        # so two adjacent fillets can never eat each other
        for p in out.points:
            self.assertLessEqual(p[0], 1.0 + 1e-9)

    def test_zero_radius_is_the_identity(self):
        curve = Curve("c", L)
        out, warns = C.fillet(curve, Params(fillet_radius=0.0))
        self.assertIs(out, curve)
        self.assertEqual(warns, ())

    def test_a_hairpin_is_not_filleted(self):
        hairpin = [(0.0, 0.0, 0.0), (6.0, 0.0, 0.0), (0.0, 0.0, 0.001)]
        out, _w = C.fillet(Curve("c", hairpin), Params(fillet_radius=1.0))
        # a near-zero-radius "fillet" is the same hairpin with five more
        # vertices on it, so 4.3's narrow-angle fallback covers the rounding
        # too and the curve comes back untouched
        self.assertEqual(len(out.points), 3)

    def test_fillet_segments_is_forced_even(self):
        self.assertEqual(Params(fillet_segments=5).fillet_segments, 6)
        self.assertEqual(Params(fillet_segments=1).fillet_segments, 2)


class TestPlanCurve(unittest.TestCase):
    """The orchestrator, end to end - still no geometry."""

    def test_miter_places_two_corner_pieces_and_bend_places_none(self):
        miter, bevels, _s = run(L, style("miter"))
        self.assertEqual(len([p for p in miter if p.slot == "corner"]), 2)
        self.assertEqual(len(bevels), 1)
        bend, _b, secs = run(L, style("bend"))
        self.assertEqual(len([p for p in bend if p.slot == "corner"]), 0)
        self.assertEqual(len(secs), 1)              # D36 welded it

    def test_every_corner_placement_has_a_unique_address(self):
        # a closed rectangle gives every section a corner at BOTH ends, which
        # is where the first version collided two posts onto one elem_id
        out, _b, _s = run(RECT, style("miter"), closed=True)
        ids = [p.elem_id for p in out]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(len([p for p in out if p.slot == "corner"]), 8)

    def test_the_closed_wrap_corner_plans_on_its_own_section(self):
        # RailClone cannot offset the last corner of a closed spline; D45 says
        # we can, and this is the property that makes it true - the wrapping
        # piece lands at the START of section 0, not 40 m into it
        out, _b, secs = run(RECT, style("miter"), closed=True)
        first = [p for p in out
                 if p.slot == "corner" and p.section_index == secs[0].index]
        self.assertTrue(first)
        self.assertLess(min(p.s0 for p in first), 0.5)

    def test_the_corner_reserves_span_from_the_default_run(self):
        out, _b, secs = run(L, style("miter"))
        for sec in secs:
            # the corner sits at ONE end of each leg, so exactly one of the
            # two bounds moves - the reserve is what moved it
            self.assertGreater(sec.fill_a, -1e-9)
            self.assertLess(sec.fill_b - sec.fill_a, sec.length - 1e-9)
        runs = [p for p in out if p.slot == "default"]
        self.assertTrue(runs)
        self.assertLess(max(p.s1 for p in runs if p.section_index == 0),
                        12.0)

    def test_the_default_run_is_cut_only_when_nothing_fills_the_corner(self):
        with_corner, _b, _s = run(L, style("miter"))
        self.assertFalse([p for p in with_corner
                          if p.slot == "default" and p.cuts])
        bare, _b, _s = run(L, style("miter", corner=()))
        self.assertTrue([p for p in bare if p.cuts])

    def test_short_legs_squeeze_and_warn_instead_of_dropping(self):
        tiny = [(0.0, 0.0, 0.0), (1.5, 0.0, 0.0), (1.5, 0.0, 1.5)]
        out, _b, _s = run(tiny, style("miter", corner=("block", "block",
                                                       "block"),
                                      select="sequence"),
                          params=Params(fill="adaptive", corner_mode="miter"))
        corners = [p for p in out if p.slot == "corner"]
        self.assertEqual(len(corners), 4)
        self.assertTrue(all(WARN_OVERFLOW in p.warns for p in corners))
        self.assertTrue(all(p.length > 0.0 for p in corners))

    def test_a_degenerate_corner_still_builds_and_says_so(self):
        hairpin = [(0.0, 0.0, 0.0), (6.0, 0.0, 0.0), (0.5, 0.0, 1.05)]
        out, bevels, secs = run(hairpin, style("miter"))
        self.assertEqual(len(secs), 1)              # D46 welded it
        self.assertEqual(bevels, [])
        self.assertTrue(out)
        self.assertTrue([p for p in out
                         if WARN_CORNER_DEGENERATE in p.warns])

    def test_nothing_raises_on_any_degenerate_input(self):
        for points, closed in (([], False), ([(0, 0, 0)], False),
                               ([(0, 0, 0), (0, 0, 0)], False),
                               ([(0, 0, 0), (1, 0, 0)], True),
                               (L, True)):
            for mode in ("bend", "miter"):
                out, _b, _s = run(points, style(mode), closed=closed)
                self.assertIsInstance(out, list)

    def test_the_plan_is_deterministic(self):
        a = [p.as_dict() for p in run(RECT, style("miter"), closed=True)[0]]
        b = [p.as_dict() for p in run(RECT, style("miter"), closed=True)[0]]
        self.assertEqual(a, b)

    def test_a_corner_piece_carries_exactly_one_cut_plane(self):
        out, _b, _s = run(L, style("miter"))
        for p in out:
            if p.slot == "corner":
                self.assertEqual(len(p.cuts), 1)
                self.assertIsNotNone(p.anchor)


if __name__ == "__main__":
    unittest.main()
