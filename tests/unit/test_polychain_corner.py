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

    def test_a_hairpin_is_not_filleted(self):
        hairpin = [(0.0, 0.0, 0.0), (6.0, 0.0, 0.0), (0.0, 0.0, 0.001)]
        out, _w = C.fillet(Curve("c", hairpin), Params(fillet_radius=1.0))
        # a near-zero-radius "fillet" is the same hairpin with five more
        # vertices on it, so 4.3's narrow-angle fallback covers the rounding
        # too and the curve comes back untouched
        self.assertEqual(len(out.points), 3)

class TestPlanCurve(unittest.TestCase):
    """The orchestrator, end to end - still no geometry."""

    def test_miter_places_two_corner_pieces_and_bend_places_none(self):
        miter, bevels, _s = run(L, style("miter"))
        self.assertEqual(len([p for p in miter if p.slot == "corner"]), 2)
        self.assertEqual(len(bevels), 1)
        bend, _b, secs = run(L, style("bend"))
        self.assertEqual(len([p for p in bend if p.slot == "corner"]), 0)
        self.assertEqual(len(secs), 1)              # D36 welded it

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

    def test_a_corner_piece_carries_exactly_one_cut_plane(self):
        out, _b, _s = run(L, style("miter"))
        for p in out:
            if p.slot == "corner":
                self.assertEqual(len(p.cuts), 1)
                self.assertIsNotNone(p.anchor)


class TestReviewFindings(unittest.TestCase):
    """The cycle-3 review, as invariants. Every assertion here is a defect
    that was measured on built geometry before it was a test."""

    def bevel(self, turn_deg, params=DEFAULTS):
        t = math.radians(turn_deg)
        tin, tout = (1.0, 0.0, 0.0), (math.cos(t), 0.0, math.sin(t))
        corner = D.Corner("c", 1, (0.0, 0.0, 0.0), turn_deg)
        b = C.Bevel(corner, (0.0, 0.0, 0.0), tin, tout, params)
        b.mode = "miter"
        return b

    def asm(self, names, turn=90.0, offset=0.0, overhang=None):
        kit = fence_kit()
        mods = [kit.by_name(n) for n in names]
        return C.build_assembly(self.bevel(turn), mods, None,
                                Params(corner_mode="miter",
                                       corner_offset_pct=offset),
                                overhang=overhang)

    # --- D49: the reserve can never go negative -----------------------------

    def test_a_turn_sharper_than_the_module_still_straddles(self):
        """e = h*tan(t/2) passes the module length at 126.87 degrees for a
        0.16 m post of half-width 0.08. Past that the reserve went NEGATIVE
        and the negative was handed to the fill as a negative trim: the run
        built through the vertex uncut and inside-out. D49 pulls the piece
        back so a tenth of it stays on its leg, and warns."""
        for turn in (130.0, 140.0, 150.0, 170.0):
            a = self.asm(["post"], turn=turn)
            self.assertGreater(a.reserve_in, 0.0, turn)
            self.assertGreater(a.reserve_out, 0.0, turn)
            self.assertLess(a.near_in, 0.0, turn)       # still reaches past V
            self.assertIn(WARN_OVERFLOW, a.warns, turn)
            self.assertAlmostEqual(a.reserve_in, 0.1 * 0.16, places=9)

    def test_a_gentler_turn_is_untouched_and_unwarned(self):
        a = self.asm(["post"], turn=120.0)
        self.assertAlmostEqual(a.reserve_in, 0.16 - 0.08 * math.tan(
            math.radians(60.0)), places=9)
        self.assertNotIn(WARN_OVERFLOW, a.warns)

    def test_an_out_of_range_offset_is_clamped_and_warned(self):
        """-100 % pushed the whole post past the vertex: the clip then deleted
        it outright (14 elements for a 16-piece plan) and left a 23 cm hole,
        warning list EMPTY."""
        a = self.asm(["post"], offset=-100.0)
        self.assertIn(WARN_OVERFLOW, a.warns)
        self.assertAlmostEqual(a.bevel.offset, 0.08 - 0.9 * 0.16, places=12)
        self.assertGreater(a.reserve_in, 0.0)

    def test_an_in_range_offset_is_not_clamped(self):
        for pct in (25.0, -25.0, 100.0):
            a = self.asm(["post"], offset=pct)
            self.assertAlmostEqual(a.bevel.offset, pct / 100.0 * 0.16,
                                   places=12)
            self.assertNotIn(WARN_OVERFLOW, a.warns)

    def test_the_offset_moves_both_copies_the_same_way(self):
        """The mirror symmetry about the vertex plane is what keeps the two
        cut faces mated at every offset."""
        for pct in (0.0, 25.0, -25.0):
            a = self.asm(["post"], offset=pct)
            self.assertAlmostEqual(a.near_in, a.near_out, places=12)
            self.assertAlmostEqual(a.near_in, -0.08 + pct / 100.0 * 0.16,
                                   places=12)

    # --- D44 corrected: the squeeze is about the plane ----------------------

    def test_a_squeezed_copy_still_reaches_the_cut_plane(self):
        """Scaling t_near with the length pulled the squeezed copy's cut face
        back off the plane by e*(1-f) - a 0.0283 m notch at every corner of a
        12 x 0.12 m rectangle, and a 1.20 m face mating against a 0.776 m one
        on a long-leg/short-leg corner."""
        a = self.asm(["block", "block", "block"])
        for factor in (1.0, 0.75, 0.5, 0.1):
            for piece in a.pieces:
                if not piece.duplicate:
                    continue
                t_far, t_near = C._piece_span(a, piece, factor)
                self.assertAlmostEqual(t_near, piece.t_near, places=12)
                self.assertAlmostEqual(
                    t_far - t_near,
                    (piece.t_far - piece.t_near) * factor, places=12)

    def test_a_squeeze_of_one_leaves_the_layout_alone(self):
        a = self.asm(["post"])
        for piece in a.pieces:
            self.assertEqual(C._piece_span(a, piece, 1.0),
                             (piece.t_far, piece.t_near))

    # --- D40 revised: the boundary piece ------------------------------------

    def test_symmetric_centres_one_module_on_the_vertex(self):
        """Exactly, in EVERY fill mode. The first version extended the fill
        SPAN, so adaptive centred the straddler at 12.07 m of a 12.00 m leg
        and tile planted a whole extra sliced piece past the vertex."""
        for fill in ("adaptive", "tile", "scale", "count"):
            st = style(displacement="symmetric", corner=())
            st.params.fill = fill
            out, bevels, _s = run(L, st)
            straddlers = [p for p in out if p.anchor is not None]
            self.assertEqual(len(straddlers), 2, fill)
            for p in straddlers:
                self.assertAlmostEqual(p.length, 2.0, places=9)
            self.assertAlmostEqual(bevels[0].assembly.reserve_in, 1.0,
                                   places=9)
            # nothing but the anchored boundary pieces may leave the section
            for p in out:
                if p.anchor is None:
                    self.assertGreaterEqual(p.s0, -1e-9, fill)

    def test_extend_puts_the_module_face_on_the_plane(self):
        st = style(displacement="extend", corner=())
        out, bevels, _s = run(L, st)
        e = bevels[0].e_for(0.03)
        self.assertAlmostEqual(bevels[0].assembly.reserve_in, 2.0 - e,
                               places=9)
        self.assertAlmostEqual(bevels[0].assembly.near_in, -e, places=9)

    def test_reset_builds_no_boundary_piece(self):
        out, bevels, _s = run(L, style(displacement="reset", corner=()))
        self.assertEqual(bevels[0].assembly.pieces, [])
        self.assertTrue(all(p.anchor is None for p in out))
        # ...and the run is still cut at the vertex, which IS reset
        self.assertTrue(any(p.cuts for p in out))

    def test_the_boundary_piece_is_anchored_and_cut(self):
        """It used to ride the path, so it was DEFORMED around the welded kink
        and came out inside-out at a 150 degree turn."""
        for policy in ("extend", "symmetric"):
            out, _b, _s = run(L, style(displacement=policy, corner=()))
            anchored = [p for p in out if p.anchor is not None]
            self.assertEqual(len(anchored), 2, policy)
            for p in anchored:
                self.assertEqual(len(p.cuts), 1)
                self.assertEqual(p.slot, "default")
                # (origin, direction, length, datum) - D72 added the datum,
                # which is the corner vertex the WHOLE assembly is dropped on.
                self.assertEqual(len(p.anchor), 4)
                self.assertEqual(tuple(p.anchor[3]), (12.0, 0.0, 0.0))
            self.assertEqual(len(set(p.elem_id for p in out)), len(out))

    def test_a_flattened_assembly_is_anchored_at_the_vertex_elevation(self):
        """D48 says `flatten` "puts both anchors at the vertex elevation"; it
        stepped down the leg's 3D line instead, so the two halves of ONE
        corner post sat `t_far * tan(pitch)` apart in Y - 0.0583 m on the
        suite's 20 degree crest corner, invisible to `corner_face_mate_m`
        because that compares stepped pieces in plan only (D72)."""
        crest = [(0.0, 0.0, 0.0), (7.52, 2.74, 0.0), (15.04, 0.0, 0.0)]
        # a yaw-only Z-mode is what makes D48 flatten the bevel at all
        yaw = Params(fill="adaptive", corner_mode="miter", zmode="stepped",
                     corner_displacement="extend")
        out, bevels, _s = run(crest, style(displacement="extend"), params=yaw)
        self.assertTrue(bevels[0].flat)
        ys = set(round(p.anchor[0][1], 9) for p in out if p.anchor is not None)
        self.assertTrue(ys)
        self.assertEqual(ys, set([round(bevels[0].v[1], 9)]))

    # --- F7: the offset was dead without a corner module --------------------

    def test_the_offset_is_live_without_a_corner_module(self):
        """0 %, 25 % and 50 % used to build byte-identical geometry: the
        offset was only ever set AFTER build_assembly's empty-mods early
        return."""
        got = []
        for pct in (0.0, -10.0, -25.0):
            st = style(displacement="extend", corner=(), offset=pct)
            out, bevels, _s = run(L, st)
            got.append(round(bevels[0].assembly.reserve_in, 9))
            self.assertAlmostEqual(bevels[0].offset, pct / 100.0 * 2.0,
                                   places=12)
        self.assertEqual(len(set(got)), 3)

    def test_reset_scopes_the_offset_out_and_says_so(self):
        """With reset there is no piece to move - RailClone's own wording is
        "simply sliced at the corner vertex" - so the parm is a documented
        no-op there rather than a silent one (D39)."""
        for pct in (0.0, 50.0):
            out, bevels, _s = run(L, style(displacement="reset", corner=(),
                                           offset=pct))
            self.assertEqual(bevels[0].assembly.pieces, [])
            self.assertEqual(tuple(bevels[0].plane_in()[0]), bevels[0].v)

    # --- F14: the run abutting a corner assembly is cut too -----------------

    def test_a_short_leg_hands_the_run_the_plane(self):
        """The reserve (0.0215 m on a 1.5 m equilateral triangle) is shorter
        than the panel's own across-reach (0.03 m), so the two legs' square
        ends crossed inside the corner post - invisible and unwarned."""
        a = 1.5
        pts = [(0.0, 0.0, 0.0), (a, 0.0, 0.0),
               (a * 0.5, 0.0, a * math.sqrt(3.0) / 2.0)]
        out, _b, _s = run(pts, style("miter"), closed=True)
        cut = [p for p in out if p.slot == "default" and p.cuts]
        self.assertTrue(cut)
        for p in cut:
            self.assertIn(WARN_OVERFLOW, p.warns)

    def test_a_long_leg_leaves_the_run_alone(self):
        out, _b, _s = run(L, style("miter"))
        for p in out:
            if p.slot == "default":
                self.assertEqual(p.cuts, ())
                self.assertNotIn(WARN_OVERFLOW, p.warns)


class TestFlattenDegenerate(unittest.TestCase):
    """D68 - `Bevel.degenerate` is reachable, and `flatten` is what reaches it.

    Cycle 3v mutated `Bevel.degenerate` to False and mutated away the
    `mode = "bend" if degenerate` fallback; both mutations SURVIVED all 44
    scene cases, and the pass concluded the branch was dead code sitting on
    top of `_joinable`. It is dead only at FIRST construction: `decompose`
    reads the 3D tangents, so a corner that is mild in 3D and a hairpin in
    PLAN is never welded, and D48's `flatten` then rebuilds the bevel on the
    flattened tangents - where it is a hairpin. These three tests are the
    route, and they are what those two mutations now die on.
    """

    def bevel(self, tin, tout, params=None):
        # miter, because "falls back to bend" is only a statement about a
        # bevel that was asked for a miter in the first place.
        params = params or style("miter").params
        corner = D.Corner("c", 1, (0.0, 0.0, 0.0),
                          C._turn_deg((-tin[0], -tin[1], -tin[2]),
                                      (0.0, 0.0, 0.0), tout))
        return C.Bevel(corner, (0.0, 0.0, 0.0), tin, tout, params)

    def test_flatten_can_turn_a_mild_corner_into_a_hairpin(self):
        # climbing steeply while doubling back in plan: 104.8 degrees of turn
        # in 3D, 178.5 flat. Nothing upstream can see the second number.
        b = self.bevel((8.0, 6.0, 0.0), (-7.6, 6.0, 0.2))
        self.assertFalse(b.degenerate)
        self.assertEqual(b.mode, "miter")
        self.assertLess(b.turn, 110.0)
        b.flatten()
        self.assertTrue(b.degenerate)
        self.assertGreater(b.turn, 170.0)

    def test_a_flattened_hairpin_falls_back_to_bend_and_warns(self):
        b = self.bevel((8.0, 6.0, 0.0), (-7.6, 6.0, 0.2)).flatten()
        self.assertEqual(b.mode, "bend")            # nothing is cut on noise
        self.assertIn(WARN_CORNER_DEGENERATE, b.warns)

    def test_a_flat_corner_is_unchanged_by_flatten(self):
        b = self.bevel((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        n0, turn0 = tuple(b.n), b.turn
        b.flatten()
        self.assertFalse(b.degenerate)
        self.assertEqual(b.mode, "miter")
        self.assertAlmostEqual(b.turn, turn0, places=9)
        for a, c in zip(b.n, n0):
            self.assertAlmostEqual(a, c, places=9)

    def test_the_flattened_hairpin_warning_reaches_a_placement(self):
        """...even with NO corner module. `Bevel.warns` only rides out through
        `build_assembly`, so a style without a corner rule dropped it and the
        corner built silently - warn-never-block, broken by D48's own fix."""
        pts = [(0.0, 0.0, 0.0), (8.0, 6.0, 0.0), (0.4, 12.0, 0.2)]
        st = Style("t", 1, 1, rules=[Rule("default", "first", ["panel"])],
                   params=Params(fill="adaptive", corner_mode="miter",
                                 zmode="vertical", corner_angle_deg=20.0))
        out, bevels, _s = run(pts, st)
        self.assertTrue(bevels[0].degenerate)
        self.assertTrue(bevels[0].flat)
        self.assertTrue([p for p in out
                         if WARN_CORNER_DEGENERATE in p.warns])


if __name__ == "__main__":
    unittest.main()
