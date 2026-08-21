"""polyChain 4.2 PLAN - the fitting solve. No Houdini, ~0.05s.

    python tests/unit/test_polychain_plan.py

⚠️ NO CALIBRATION FIXTURE EXISTS YET, and that is deliberate rather than
missed. `test_plan.py`'s "calibrate, do not invent" discipline needs a builder
to measure against, and 4.4 has not been built - so every number below is an
INVARIANT of the solve (what must be true of any correct fit), never a
measurement of a particular result. The moment 4.4 places real geometry, a
`tests/polychain/dump_placements.py` fixture joins this file the same way
`dump_trims.py` joined `test_plan.py`, and the exact-fill assertions here
become the thing the dump is checked against.

The invariants, and why each one is load-bearing:

  exact fill      Sum of pieces and gaps == the span, to 1e-9 m. Every mode.
                  A fill that is 3 mm short leaves a seam in every run of a
                  10k-piece fence, and nothing else in the pipeline can see it.
  never slice     `adaptive` may not produce a cut piece, ever - it is the
                  default mode precisely because architecture must not be cut
                  through a window (railclone.md 6.3).
  padding         Moves the NEIGHBOUR, never the padded piece; negative
                  overlaps. This is the RailClone semantic that a naive
                  "add the pad to the piece" implementation gets backwards,
                  and the difference only shows up as a drift down a long run.
  determinism     Same inputs + seed => byte-identical `plan_dicts()`, and the
                  plan does not move when an unrelated list is reordered.
  warn-never-block Every degenerate input produces a plan and a warning name,
                  and no exception.
"""

import math
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "polyfactory", "scripts", "python",
                                "polyfactory"))

import polychain as pc                                          # noqa: E402
from polychain import decompose as dc                           # noqa: E402
from polychain import plan                                      # noqa: E402

TOL = 1e-9


def module(name, length, pad=(0.0, 0.0), deform=0, roles="default", **kw):
    return pc.Module(name, (length, 1.0, 0.1), pad=pad, deform=deform,
                     roles=roles, **kw)


def kit(*mods):
    return pc.Kit("test_kit", modules=list(mods), human_scale_reference=1.8)


PANEL = module("panel", 2.0, deform=pc.DEFORM_BEND)          # bends, no slice
TILE = module("tile", 2.0, deform=pc.DEFORM_SLICE)           # sliceable
POST = module("post", 0.4, roles="default post")
GATE = module("gate", 3.0, roles="gate")
CAP_A = module("cap_a", 1.0, roles="start end")
CAP_B = module("cap_b", 1.0, roles="start end")

KIT = kit(PANEL, TILE, POST, GATE, CAP_A, CAP_B)


def style(rules, seed=0, style_id="s"):
    return pc.Style(style_id, seed=seed, rules=list(rules))


def default_style(modules=("panel",), select="first", **kw):
    return style([pc.Rule("default", select=select, modules=list(modules),
                          **kw)])


def section(length=10.0, index=0, curve_id="c", closed=False, markers=(),
            curve_length=None):
    return dc.Section(curve_id, index, 0.0, length,
                      curve_length if curve_length is not None else length,
                      markers=markers, closed=closed)


def spans(placements):
    return [(round(p.s0, 9), round(p.s1, 9)) for p in placements]


def covers(test, placements, a, b):
    """The exact-fill property, stated once: the run reaches both ends."""
    test.assertTrue(placements, "no placements at all")
    test.assertAlmostEqual(min(p.s0 for p in placements), a, delta=TOL)
    test.assertAlmostEqual(max(p.s1 for p in placements), b, delta=TOL)


class TestFit(unittest.TestCase):
    """The maths on its own, before any slot or selection can confuse it."""

    def total(self, res, nominal, gap=0.0, fixed=0.0):
        n = res["count"]
        if n == 0:
            return res["remainder"]
        t = n * (nominal * res["scale"] + fixed) + max(n - 1, 0) * gap
        if res["slice"]:
            t += gap + res["remainder"]
        return t

    def test_every_mode_fills_the_span_exactly(self):
        p = pc.Params(count=4, adaptive_pct=50.0)
        for mode in pc.FILL_MODES:
            for L in (0.5, 1.0, 3.0, 7.3, 10.0, 99.7):
                res = plan.fit(L, 3.0, mode, p)
                with self.subTest(mode=mode, L=L):
                    self.assertAlmostEqual(self.total(res, 3.0), L, delta=TOL)

    def test_every_mode_fills_exactly_with_padding_too(self):
        p = pc.Params(count=3)
        for mode in pc.FILL_MODES:
            for gap in (0.0, 0.75, -0.25):
                res = plan.fit(20.0, 3.0, mode, p, gap=gap, fixed=0.5)
                with self.subTest(mode=mode, gap=gap):
                    self.assertAlmostEqual(
                        self.total(res, 3.0, gap=gap, fixed=0.5), 20.0,
                        delta=TOL)

    def test_tile_is_whole_pieces_plus_one_remainder(self):
        res = plan.fit(10.0, 3.0, "tile")
        self.assertEqual(res["count"], 3)
        self.assertEqual(res["scale"], 1.0)
        self.assertTrue(res["slice"])
        self.assertAlmostEqual(res["remainder"], 1.0, delta=TOL)

    def test_tile_with_no_remainder_does_not_invent_a_sliver(self):
        res = plan.fit(9.0, 3.0, "tile")
        self.assertEqual(res["count"], 3)
        self.assertFalse(res["slice"])
        self.assertAlmostEqual(res["remainder"], 0.0, delta=TOL)

    def test_tile_shorter_than_one_module_is_a_single_slice(self):
        res = plan.fit(1.2, 3.0, "tile")
        self.assertEqual(res["count"], 0)
        self.assertTrue(res["slice"])
        self.assertAlmostEqual(res["remainder"], 1.2, delta=TOL)

    def test_scale_stretches_ONE_piece(self):
        """D12, verified against iToo's wording rather than assumed: "Scale
        stretches one segment across the entire length of each sub-spline".
        Making it n stretched pieces would duplicate `adaptive` exactly."""
        res = plan.fit(10.0, 3.0, "scale")
        self.assertEqual(res["count"], 1)
        self.assertAlmostEqual(res["scale"], 10.0 / 3.0, delta=TOL)
        self.assertFalse(res["slice"])

    def test_adaptive_NEVER_slices_at_any_length(self):
        """The reason it is the default mode. Swept, not spot-checked."""
        for i in range(1, 2000):
            L = i * 0.05
            res = plan.fit(L, 3.0, "adaptive")
            self.assertFalse(res["slice"], L)
            self.assertEqual(res["remainder"], 0.0)
            self.assertGreaterEqual(res["count"], 1)

    def test_adaptive_pct_is_the_add_one_more_threshold(self):
        """3.5 m of a 3 m module is 16.7% of a second one: added at a 10%
        threshold, not added at 50%. 100% never adds; 0% always does."""
        self.assertEqual(plan.fit(3.5, 3.0, "adaptive",
                                  pc.Params(adaptive_pct=50.0))["count"], 1)
        self.assertEqual(plan.fit(3.5, 3.0, "adaptive",
                                  pc.Params(adaptive_pct=10.0))["count"], 2)
        self.assertEqual(plan.fit(5.9, 3.0, "adaptive",
                                  pc.Params(adaptive_pct=100.0))["count"], 1)
        self.assertEqual(plan.fit(3.1, 3.0, "adaptive",
                                  pc.Params(adaptive_pct=0.0))["count"], 2)

    def test_adaptive_at_50_pct_is_round_to_nearest(self):
        self.assertEqual(plan.fit(4.4, 3.0, "adaptive")["count"], 1)
        self.assertEqual(plan.fit(4.6, 3.0, "adaptive")["count"], 2)

    def test_count_honours_N_including_zero_and_one(self):
        self.assertEqual(plan.fit(10.0, 3.0, "count", pc.Params(count=0)),
                         {"count": 0, "scale": 1.0, "remainder": 0.0,
                          "slice": False, "warns": ()})
        one = plan.fit(10.0, 3.0, "count", pc.Params(count=1))
        self.assertEqual(one["count"], 1)
        self.assertAlmostEqual(one["scale"], 10.0 / 3.0, delta=TOL)
        five = plan.fit(10.0, 3.0, "count", pc.Params(count=5))
        self.assertEqual(five["count"], 5)
        self.assertAlmostEqual(five["scale"], 10.0 / 15.0, delta=TOL)

    def test_a_negative_count_is_read_as_zero_not_as_a_crash(self):
        self.assertEqual(plan.fit(10.0, 3.0, "count",
                                  pc.Params(count=-4))["count"], 0)

    def test_a_zero_length_span_or_module_places_nothing(self):
        for mode in pc.FILL_MODES:
            self.assertEqual(plan.fit(0.0, 3.0, mode)["count"], 0)
            self.assertEqual(plan.fit(10.0, 0.0, mode)["count"], 0)

    def test_padding_that_cancels_the_unit_never_divides_by_zero(self):
        """D17. Negative padding is a documented feature ("negative =
        overlap"), so pad = (-0.5, -0.5) on a 1 m module is legal input - and
        it makes one more piece cost NOTHING, which no fit can answer. It
        degrades to a single scaled unit and warns; it may not raise."""
        for mode in pc.FILL_MODES:
            res = plan.fit(10.0, 1.0, mode, pc.Params(count=3), gap=-1.0)
            with self.subTest(mode=mode):
                self.assertEqual(res["count"], 1)
                self.assertAlmostEqual(res["scale"], 10.0, delta=TOL)
                self.assertIn(pc.WARN_DEGENERATE_PAD, res["warns"])
        res = plan.fit(4.0, 1.0, "adaptive", gap=-2.0)      # step is NEGATIVE
        self.assertEqual(res["count"], 1)
        self.assertIn(pc.WARN_DEGENERATE_PAD, res["warns"])

    def test_a_nearly_cancelled_step_is_bounded_and_warned(self):
        """99.99% overlap plans tens of thousands of pieces on a 10 m run.
        That is what the input asks for, so it is obeyed - but it is flagged,
        and MAX_UNITS keeps a rounding error from planning a billion."""
        res = plan.fit(10.0, 1.0, "adaptive", gap=-0.9999)
        self.assertIn(pc.WARN_DEGENERATE_PAD, res["warns"])
        self.assertLessEqual(res["count"], pc.MAX_UNITS)
        huge = plan.fit(1e9, 1.0, "adaptive", gap=-0.999999)
        self.assertEqual(huge["count"], pc.MAX_UNITS)
        self.assertIn(pc.WARN_DEGENERATE_PAD, huge["warns"])

    def test_a_unit_wider_than_the_span_never_returns_a_negative_scale(self):
        """The drop loop stops at n = 1, so a UNIT whose own internal padding
        is longer than the span used to come back with scale < 0 - geometry
        built backwards, silently. It degenerates to zero length and warns."""
        res = plan.fit(1.5, 2.0, "adaptive", fixed=4.0)
        self.assertEqual(res["scale"], 0.0)
        self.assertIn(pc.WARN_DEGENERATE_PAD, res["warns"])

    def test_padding_wider_than_the_span_drops_units_instead_of_inverting(self):
        """A 2 m gap between 1 m pieces in a 3 m span cannot hold three of
        them; the solve must shed units, not return a negative scale."""
        res = plan.fit(3.0, 1.0, "count", pc.Params(count=3), gap=2.0)
        self.assertGreaterEqual(res["scale"], 0.0)
        self.assertAlmostEqual(self.total(res, 1.0, gap=2.0), 3.0, delta=TOL)


class TestEvenly(unittest.TestCase):

    def test_count_mode_divides_the_span_into_equal_parts(self):
        self.assertEqual([round(x, 9) for x in
                          plan.evenly(12.0, pc.Params(evenly_count=3))],
                         [3.0, 6.0, 9.0])

    def test_distance_mode_steps_by_the_spacing(self):
        got = plan.evenly(10.0, pc.Params(evenly_spacing=3.0,
                                          justify="start"))
        self.assertEqual([round(x, 9) for x in got], [3.0, 6.0, 9.0])

    def test_justify_moves_the_run_inside_its_leftover(self):
        """RailClone's Justify "adjusts the first and last space so the evenly
        segments fit". `center` is the DEFAULT, so it is the one an artist
        reads on a fence - and the only reading of centred that survives a
        look at the viewport is symmetric: equal space before the first anchor
        and after the last. Centring the run inside its LEFTOVER instead put
        3.5 m in front of a 10 m run and 0.5 m behind it."""
        c = plan.evenly(10.0, pc.Params(evenly_spacing=3.0, justify="center"))
        self.assertEqual([round(x, 9) for x in c], [2.0, 5.0, 8.0])
        self.assertAlmostEqual(c[0], 10.0 - c[-1], delta=TOL)      # symmetric
        e = plan.evenly(10.0, pc.Params(evenly_spacing=3.0, justify="end"))
        self.assertEqual([round(x, 9) for x in e], [1.0, 4.0, 7.0])
        s = plan.evenly(10.0, pc.Params(evenly_spacing=3.0, justify="start"))
        self.assertEqual([round(x, 9) for x in s], [3.0, 6.0, 9.0])

    def test_no_justify_puts_an_anchor_on_the_span_end(self):
        """An anchor AT the end centres half its module past the section, into
        the end cap or off the curve. `adjust_to_end` is the ONE way to ask
        for it, explicitly."""
        for j in pc.JUSTIFY:
            got = plan.evenly(10.0, pc.Params(evenly_spacing=3.0, justify=j))
            self.assertLess(got[-1], 10.0 - TOL, j)
            self.assertGreater(got[0], TOL, j)

    def test_adjust_to_end_stretches_the_spacing_onto_the_end(self):
        p = pc.Params(evenly_spacing=3.0, justify="start", adjust_to_end=1.0)
        got = plan.evenly(10.0, p)
        self.assertEqual(len(got), 3)
        self.assertAlmostEqual(got[-1], 10.0, delta=TOL)

    def test_adjust_to_end_does_nothing_when_the_leftover_is_too_big(self):
        p = pc.Params(evenly_spacing=3.0, justify="start", adjust_to_end=0.5)
        self.assertEqual([round(x, 9) for x in plan.evenly(10.0, p)],
                         [3.0, 6.0, 9.0])

    def test_a_spacing_longer_than_the_span_places_no_anchor(self):
        self.assertEqual(plan.evenly(2.0, pc.Params(evenly_spacing=3.0)), [])
        self.assertEqual(plan.evenly(0.0, pc.Params(evenly_count=3)), [])

    def test_no_spacing_and_no_count_is_the_off_switch(self):
        self.assertEqual(plan.evenly(10.0, pc.DEFAULTS), [])


class TestFillModesInPlace(unittest.TestCase):
    """The same four modes, now through the whole section solve."""

    def plan(self, mode, length=10.0, modules=("panel",), **kw):
        p = pc.Params(fill=mode, **kw)
        return plan.plan_section(section(length), KIT,
                                 default_style(modules), p)

    def test_every_mode_covers_the_section_exactly(self):
        for mode in pc.FILL_MODES:
            with self.subTest(mode=mode):
                got = self.plan(mode, 10.0, ("tile",), count=3)
                covers(self, got, 0.0, 10.0)
                for a, b in zip(got, got[1:]):
                    self.assertAlmostEqual(a.s1, b.s0, delta=TOL)

    def test_adaptive_places_whole_pieces_only(self):
        got = self.plan("adaptive", 11.0)
        self.assertEqual(len(got), 6)                 # 11 / 2 -> 5.5 -> 6
        self.assertTrue(all(p.slice_t is None for p in got))
        self.assertTrue(all(abs(p.length - 11.0 / 6.0) < TOL for p in got))
        self.assertAlmostEqual(got[0].scale, 11.0 / 12.0, delta=TOL)

    def test_tile_slices_the_remainder_when_the_module_allows_it(self):
        got = self.plan("tile", 11.0, ("tile",))
        self.assertEqual(len(got), 6)
        self.assertEqual([p.slice_t for p in got[:5]], [None] * 5)
        self.assertAlmostEqual(got[-1].slice_t, 0.5, delta=TOL)
        self.assertAlmostEqual(got[-1].length, 1.0, delta=TOL)
        self.assertEqual(plan.warnings_of(got), {})

    def test_tile_falls_back_to_adaptive_and_WARNS_when_it_may_not_slice(self):
        """4.2's "else adaptive-fallback + pc_warn". D11: the WHOLE run falls
        back, because one adaptive piece inside a tiled run reads as a defect
        in the viewport while a uniformly rescaled run reads as a choice."""
        got = self.plan("tile", 11.0, ("panel",))     # panel is deform 1
        self.assertTrue(all(p.slice_t is None for p in got))
        self.assertEqual(plan.warnings_of(got),
                         {pc.WARN_TILE_FALLBACK: len(got)})
        covers(self, got, 0.0, 11.0)
        self.assertEqual(len(set(round(p.length, 9) for p in got)), 1)

    def test_tile_that_happens_to_fit_exactly_never_falls_back(self):
        got = self.plan("tile", 10.0, ("panel",))
        self.assertEqual(len(got), 5)
        self.assertEqual(plan.warnings_of(got), {})
        self.assertTrue(all(abs(p.length - 2.0) < TOL for p in got))

    def test_the_tile_remainder_continues_the_unit_instead_of_repeating_its_head(self):
        """A remainder longer than the unit's FIRST module cannot be supplied
        by one copy of it. post(1) + panel(3) tiled on 6 m leaves 2 m, which is
        a whole post plus 1 m of panel - not a post claiming 2 m of span with
        a 1.0 slice, which is a metre of hole in the viewport."""
        k = kit(module("post1", 1.0, deform=pc.DEFORM_SLICE),
                module("panel3", 3.0, deform=pc.DEFORM_SLICE))
        s = default_style(("post1", "panel3"), select="sequence")
        got = plan.plan_section(section(6.0), k, s, pc.Params(fill="tile"))
        self.assertEqual([p.module for p in got],
                         ["post1", "panel3", "post1", "panel3"])
        self.assertEqual([p.slice_t for p in got[:3]], [None] * 3)
        self.assertAlmostEqual(got[-1].length, 1.0, delta=TOL)
        self.assertAlmostEqual(got[-1].slice_t, 1.0 / 3.0, delta=TOL)
        covers(self, got, 0.0, 6.0)
        for a, b in zip(got, got[1:]):
            self.assertAlmostEqual(a.s1, b.s0, delta=TOL)

    def test_the_tile_remainder_never_slices_a_rigid_re_selection(self):
        """The run's UNIT decided the fallback, but a random rule re-picks per
        piece - so the module that actually lands on the boundary is the one
        whose `pc_deform` decides whether it may be cut (4.2). Seed 16 is the
        case that emitted a rigid module with slice_t = 0.5."""
        k = kit(module("a_slice", 2.0, deform=pc.DEFORM_SLICE),
                module("b_rigid", 2.0, deform=pc.DEFORM_RIGID))
        for seed in range(40):
            s = style([pc.Rule("default", select="random",
                               modules=["a_slice", "b_rigid"])], seed=seed)
            got = plan.plan_section(section(7.0), k, s, pc.Params(fill="tile"))
            with self.subTest(seed=seed):
                for p in got:
                    if p.slice_t is not None:
                        self.assertEqual(p.deform, pc.DEFORM_SLICE, p.module)
                covers(self, got, 0.0, 7.0)

    def test_a_tile_shorter_than_one_module_starts_at_the_section_start(self):
        """With no whole unit before it the remainder has no inter-unit gap to
        clear: offsetting it anyway pushed the only piece of a 5 m section to
        2..7 m - two metres off the end of the curve."""
        k = kit(module("big", 10.0, pad=(1.0, 1.0), deform=pc.DEFORM_SLICE))
        got = plan.plan_section(section(5.0), k, default_style(("big",)),
                                pc.Params(fill="tile"))
        self.assertEqual(spans(got), [(0.0, 5.0)])
        self.assertAlmostEqual(got[0].slice_t, 0.5, delta=TOL)

    def test_scale_places_one_stretched_piece(self):
        got = self.plan("scale", 7.0)
        self.assertEqual(len(got), 1)
        self.assertAlmostEqual(got[0].scale, 3.5, delta=TOL)
        self.assertIsNone(got[0].slice_t)

    def test_count_zero_places_nothing_and_count_one_spans_the_section(self):
        self.assertEqual(self.plan("count", 10.0, count=0), [])
        one = self.plan("count", 10.0, count=1)
        self.assertEqual(len(one), 1)
        self.assertEqual(spans(one), [(0.0, 10.0)])

    def test_count_places_exactly_N(self):
        for n in (1, 2, 7, 33):
            got = self.plan("count", 10.0, count=n)
            self.assertEqual(len(got), n)
            covers(self, got, 0.0, 10.0)


class TestPadding(unittest.TestCase):
    """The RailClone semantic, stated three ways because it is easy to invert."""

    def _run(self, pad, length=9.0, count=2):
        k = kit(module("p", 2.0, pad=pad))
        return plan.plan_section(section(length), k, default_style(("p",)),
                                 pc.Params(fill="count", count=count))

    def test_padding_moves_the_NEIGHBOUR_not_the_padded_piece(self):
        """The first piece starts at 0 even though it has a left pad: there is
        nothing before it to be pushed. Adding the pad to the piece itself
        would open a 0.5 m hole at the head of every run."""
        got = self._run((0.5, 0.5))
        self.assertAlmostEqual(got[0].s0, 0.0, delta=TOL)
        self.assertAlmostEqual(got[-1].s1, 9.0, delta=TOL)

    def test_the_gap_between_two_pieces_is_the_sum_of_their_facing_pads(self):
        got = self._run((0.5, 0.5))
        self.assertAlmostEqual(got[1].s0 - got[0].s1, 1.0, delta=TOL)
        self.assertAlmostEqual(got[0].length, 4.0, delta=TOL)   # (9-1)/2

    def test_negative_padding_overlaps(self):
        got = self._run((-0.25, -0.25))
        self.assertLess(got[1].s0, got[0].s1)
        self.assertAlmostEqual(got[1].s0 - got[0].s1, -0.5, delta=TOL)
        covers(self, got, 0.0, 9.0)

    def test_padding_is_not_scaled_by_the_fit(self):
        """D5. `pc_pad` is a scene distance in metres; only geometry stretches.
        A scaled pad would make the gap drift with the section length."""
        for L in (9.0, 20.0, 41.7):
            got = self._run((0.5, 0.5), length=L)
            self.assertAlmostEqual(got[1].s0 - got[0].s1, 1.0, delta=TOL)

    def test_a_closed_run_carries_the_SAME_gap_across_the_seam(self):
        """D19. A ring laid out as an open run has n-1 gaps, so the wrap joint
        gets none: on a padded fence around a round plaza every joint is 1 m
        except one arbitrary pair of posts that touch."""
        n = 64
        pts = [(10.0 * math.cos(2 * math.pi * i / n), 0.0,
                10.0 * math.sin(2 * math.pi * i / n)) for i in range(n)]
        sec = dc.decompose(pc.Curve("ring", pts, closed=True))[0]
        self.assertTrue(sec.closed)
        k = kit(module("m", 2.0, pad=(0.5, 0.5), deform=pc.DEFORM_BEND))
        got = plan.plan_section(sec, k, default_style(("m",)))
        seam = got[0].s0 + (sec.length - got[-1].s1)
        self.assertAlmostEqual(seam, 1.0, delta=TOL)
        for a, b in zip(got, got[1:]):
            self.assertAlmostEqual(b.s0 - a.s1, 1.0, delta=TOL)

    def test_degenerate_padding_places_nothing_outside_the_section(self):
        """Warn-never-block, the geometric half: the pieces collapse to zero
        length rather than running backwards, and they stay inside the span
        rather than being pushed past its end by the padding that broke it."""
        k = kit(module("a", 1.0, pad=(0.0, 3.0)),
                module("b", 1.0, pad=(3.0, 0.0)))
        s = default_style(("a", "b"), select="sequence")
        got = plan.plan_section(section(4.0), k, s)
        self.assertTrue(got)
        for p in got:
            self.assertGreaterEqual(p.length, -TOL)
            self.assertGreaterEqual(p.s0, -TOL)
            self.assertLessEqual(p.s1, 4.0 + TOL)
            self.assertIn(pc.WARN_DEGENERATE_PAD, p.warns)

    def test_padding_still_fills_exactly_in_every_mode(self):
        k = kit(module("p", 2.0, pad=(0.3, -0.2), deform=pc.DEFORM_SLICE))
        for mode in pc.FILL_MODES:
            got = plan.plan_section(section(17.0), k, default_style(("p",)),
                                    pc.Params(fill=mode, count=4))
            with self.subTest(mode=mode):
                covers(self, got, 0.0, 17.0)
                for a, b in zip(got, got[1:]):
                    self.assertAlmostEqual(b.s0 - a.s1, 0.1, delta=TOL)


class TestSlots(unittest.TestCase):

    def style(self, **kw):
        rules = [pc.Rule("default", modules=["panel"])]
        for slot, mods in kw.items():
            rules.append(pc.Rule(slot.replace("__", ":"), modules=list(mods)))
        return style(rules)

    def test_start_and_end_are_reserved_before_the_fill(self):
        got = plan.plan_section(section(10.0), KIT,
                                self.style(start=["cap_a"], end=["cap_b"]))
        by_slot = dict((p.slot, p) for p in got if p.slot in ("start", "end"))
        self.assertEqual(spans([by_slot["start"]]), [(0.0, 1.0)])
        self.assertEqual(spans([by_slot["end"]]), [(9.0, 10.0)])
        fill = [p for p in got if p.slot == "default"]
        covers(self, fill, 1.0, 9.0)
        self.assertEqual(len(fill), 4)

    def test_a_closed_section_uses_no_start_or_end(self):
        """RailClone semantics (D10): a loop has no ends to cap."""
        got = plan.plan_section(section(10.0, closed=True), KIT,
                                self.style(start=["cap_a"], end=["cap_b"]))
        self.assertEqual(set(p.slot for p in got), {"default"})
        covers(self, got, 0.0, 10.0)

    def test_a_CORNER_is_not_an_end_and_gets_no_caps(self):
        """D18. RailClone puts Start/End at spline ends and Corner segments at
        corners; capping every section grew a cap PAIR at every elbow - four
        pieces on an L instead of two, and the corner slot could never work."""
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0), (5.0, 0.0, 5.0)])
        secs = dc.decompose(c)
        got = plan.plan_sections(secs, KIT,
                                 self.style(start=["cap_a"], end=["cap_b"]))
        caps = [(p.slot, p.section_index) for p in got if p.slot != "default"]
        self.assertEqual(caps, [("start", 0), ("end", 1)])

    def test_a_CLOSED_spline_gets_no_caps_on_any_side(self):
        """The corner-free loop was already covered; the rectangle was not -
        it has four corner-bounded sections and used to grow eight caps."""
        c = pc.Curve("f", [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0),
                           (12.0, 0.0, 8.0), (0.0, 0.0, 8.0)], closed=True)
        got = plan.plan_sections(dc.decompose(c), KIT,
                                 self.style(start=["cap_a"], end=["cap_b"]))
        self.assertEqual(set(p.slot for p in got), {"default"})

    def test_a_pc_section_LIMIT_does_cap_like_a_spline_end(self):
        """The other half of D18: a material-ID limit is where one generator
        stops and the next starts, so both sides of it are real run ends."""
        c = pc.Curve("street", [(x, 0.0, 0.0) for x in (0.0, 5.0, 10.0, 15.0)],
                     section_ids=[1, 1, 2, 2])
        secs = dc.decompose(c)
        self.assertEqual([(s.start_cap, s.end_cap) for s in secs],
                         [(True, True), (True, True)])
        got = plan.plan_sections(secs, KIT,
                                 self.style(start=["cap_a"], end=["cap_b"]))
        self.assertEqual(sorted(p.slot for p in got if p.slot != "default"),
                         ["end", "end", "start", "start"])

    def test_an_evenly_anchor_never_grows_through_the_end_module(self):
        """D15 claimed the free span made a collision impossible; it did not -
        the anchor is the piece's CENTRE, so half a module has to come off
        each capped end or the last post interpenetrates the end cap."""
        k = kit(module("panel", 2.0, deform=pc.DEFORM_BEND),
                module("cap", 2.0, roles="start end"),
                module("post", 1.0, roles="post"))
        s = style([pc.Rule("default", modules=["panel"]),
                   pc.Rule("start", modules=["cap"]),
                   pc.Rule("end", modules=["cap"]),
                   pc.Rule("evenly", modules=["post"])])
        for justify in pc.JUSTIFY:
            p = pc.Params(evenly_spacing=2.0, justify=justify)
            got = plan.plan_section(section(12.0), k, s, p)
            head = [x for x in got if x.slot == "start"][0]
            tail = [x for x in got if x.slot == "end"][0]
            for ev in [x for x in got if x.slot == "evenly"]:
                with self.subTest(justify=justify):
                    self.assertGreaterEqual(ev.s0, head.s1 - TOL)
                    self.assertLessEqual(ev.s1, tail.s0 + TOL)

    def test_evenly_anchors_are_centred_and_the_fill_runs_between_them(self):
        p = pc.Params(evenly_count=3)
        got = plan.plan_section(section(12.0), KIT,
                                self.style(evenly=["post"]), p)
        ev = [x for x in got if x.slot == "evenly"]
        self.assertEqual(len(ev), 3)
        for x, at in zip(ev, (3.0, 6.0, 9.0)):
            self.assertAlmostEqual((x.s0 + x.s1) * 0.5, at, delta=TOL)
            self.assertAlmostEqual(x.length, 0.4, delta=TOL)
        covers(self, got, 0.0, 12.0)
        for a, b in zip(got, got[1:]):
            self.assertAlmostEqual(a.s1, b.s0, delta=TOL)

    def test_a_marker_places_its_module_EXACTLY_at_the_marker(self):
        """PC-G1's own acceptance wording: "gate exactly at its marker". The
        anchor is never nudged to make the fill tidier (D15)."""
        marks = [{"marker_id": 1, "s": 4.0, "u": 0.4, "data": {},
                  "s_local": 4.0}]
        got = plan.plan_section(section(12.0, markers=marks), KIT,
                                self.style(marker__1=["gate"]))
        gate = [x for x in got if x.slot == "marker:1"]
        self.assertEqual(len(gate), 1)
        self.assertAlmostEqual((gate[0].s0 + gate[0].s1) * 0.5, 4.0, delta=TOL)
        self.assertEqual(gate[0].module, "gate")
        covers(self, got, 0.0, 12.0)

    def test_a_marker_rule_is_evaluated_at_the_MARKER_not_at_the_section_start(self):
        """3.3 lists `u` as a per-candidate subject. Reading it at the section
        start made a conditional gate at u = 0.9 test u = 0.0 and silently
        never place - the failure mode that looks like a missing kit piece."""
        marks = [{"marker_id": 5, "s": 9.0, "u": 0.9, "data": {},
                  "s_local": 9.0}]
        s = style([pc.Rule("default", modules=["panel"]),
                   pc.Rule("marker:5", "conditional", ["gate"],
                           cond={"subject": "u", "op": "gt", "value": 0.5})])
        got = plan.plan_section(section(10.0, markers=marks), KIT, s)
        gate = [x for x in got if x.slot == "marker:5"]
        self.assertEqual(len(gate), 1)
        self.assertAlmostEqual((gate[0].s0 + gate[0].s1) * 0.5, 9.0, delta=TOL)

    def test_an_evenly_rule_is_evaluated_AT_EACH_ANCHOR(self):
        """Same defect on the evenly slot: one pick at u0 for the whole run,
        so a sequence never advanced and a conditional tested the wrong end."""
        p = pc.Params(evenly_count=3)
        s = style([pc.Rule("default", modules=["panel"]),
                   pc.Rule("evenly", select="sequence",
                           modules=["post", "gate"])])
        got = plan.plan_section(section(12.0), KIT, s, p)
        self.assertEqual([x.module for x in got if x.slot == "evenly"],
                         ["post", "gate", "post"])

    def test_a_marker_with_no_rule_places_nothing_and_does_not_disturb_the_fill(self):
        marks = [{"marker_id": 9, "s": 4.0, "u": 0.4, "data": {},
                  "s_local": 4.0}]
        got = plan.plan_section(section(12.0, markers=marks), KIT, self.style())
        self.assertEqual(set(x.slot for x in got), {"default"})
        covers(self, got, 0.0, 12.0)

    def test_the_default_index_runs_continuously_across_the_anchors(self):
        """The index is half of `pc_elem_id`; restarting it at every anchor
        would give two pieces in one section the same address."""
        p = pc.Params(evenly_count=2)
        got = plan.plan_section(section(12.0), KIT,
                                self.style(evenly=["post"]), p)
        fill = [x for x in got if x.slot == "default"]
        self.assertEqual([x.index for x in fill], list(range(len(fill))))
        self.assertEqual(len(set(x.elem_id for x in got)), len(got))


class TestOverflowAndDegenerates(unittest.TestCase):
    """Warn-never-block, one test per way a section can be too small."""

    def style(self):
        return style([pc.Rule("default", modules=["panel"]),
                      pc.Rule("start", modules=["cap_a"]),
                      pc.Rule("end", modules=["cap_b"])])

    def test_a_section_shorter_than_start_plus_end_drops_the_end_and_warns(self):
        got = plan.plan_section(section(1.5), KIT, self.style())
        self.assertEqual([p.slot for p in got if p.slot != "default"], ["start"])
        self.assertEqual(plan.warnings_of(got)[pc.WARN_OVERFLOW], 1)
        covers(self, got, 0.0, 1.5)

    def test_a_section_shorter_than_ONE_module_scales_it_and_warns(self):
        """D13: never an empty section, never an exception. The survivor is
        squeezed onto the section rather than left sticking out of it."""
        got = plan.plan_section(section(0.4), KIT, self.style())
        self.assertEqual(len(got), 1)
        self.assertEqual(got[0].slot, "start")
        self.assertEqual(spans(got), [(0.0, 0.4)])
        self.assertAlmostEqual(got[0].scale, 0.4, delta=TOL)
        self.assertIn(pc.WARN_OVERFLOW, got[0].warns)

    def test_a_zero_length_section_places_nothing_and_does_not_raise(self):
        self.assertEqual(plan.plan_section(section(0.0), KIT, self.style()), [])
        s = dc.Section("c", 0, 5.0, 5.0, 10.0)
        self.assertEqual(plan.plan_section(s, KIT, self.style()), [])

    def test_a_negative_length_section_places_nothing(self):
        self.assertEqual(plan.plan_section(dc.Section("c", 0, 5.0, 4.0, 10.0),
                                           KIT, self.style()), [])

    def test_a_missing_module_becomes_a_stand_in_and_warns_per_element(self):
        got = plan.plan_section(section(10.0), KIT,
                                default_style(("does_not_exist",)))
        self.assertTrue(got)
        self.assertEqual(plan.warnings_of(got), {pc.WARN_KIT_GAP: len(got)})
        covers(self, got, 0.0, 10.0)

    def test_an_empty_style_plans_nothing_rather_than_failing(self):
        self.assertEqual(plan.plan_section(section(10.0), KIT, style([])), [])

    def test_an_empty_kit_still_plans_with_stand_ins(self):
        got = plan.plan_section(section(10.0), pc.Kit("empty"),
                                default_style(("panel",)))
        self.assertTrue(got)
        self.assertEqual(plan.warnings_of(got), {pc.WARN_KIT_GAP: len(got)})

    def test_a_vexpr_is_ignored_and_warned_never_executed(self):
        """D3 / open Q4: data first, expression second, code never. Phase 1
        has no expression engine, so it says so on the element."""
        s = style([pc.Rule("default", modules=["panel"],
                           vexpr="if (@P.x > 0) 1;")])
        got = plan.plan_section(section(10.0), KIT, s)
        self.assertEqual(plan.warnings_of(got),
                         {pc.WARN_VEXPR_IGNORED: len(got)})

    def test_a_zero_length_module_does_not_hang_the_solve(self):
        k = kit(module("flat", 0.0))
        self.assertEqual(plan.plan_section(section(10.0), k,
                                           default_style(("flat",))), [])


class TestSelection(unittest.TestCase):

    def test_first_takes_the_head_of_the_list(self):
        got = plan.plan_section(section(10.0), KIT,
                                default_style(("panel", "tile")))
        self.assertEqual(set(p.module for p in got), {"panel"})

    def test_sequence_walks_the_list_and_still_fills_exactly(self):
        """D14: a sequence is fitted as a PATTERN, so mixed sizes work. The
        unit here is post(0.4) + panel(2.0) = 2.4 m."""
        s = default_style(("post", "panel"), select="sequence")
        got = plan.plan_section(section(12.0), KIT, s,
                                pc.Params(fill="adaptive"))
        self.assertEqual([p.module for p in got],
                         ["post", "panel"] * (len(got) // 2))
        covers(self, got, 0.0, 12.0)
        self.assertAlmostEqual(got[1].length / got[0].length, 5.0, delta=1e-6)

    def test_random_is_weighted_and_reproducible(self):
        k = kit(module("a", 2.0), module("b", 2.0, weight=0.0))
        s = default_style(("a", "b"), select="random")
        got = plan.plan_section(section(40.0), k, s)
        self.assertEqual(set(p.module for p in got), {"a"})   # weight 0 never

    def test_conditional_reads_the_data_and_declines_to_the_next_rule(self):
        s = style([
            pc.Rule("default", select="conditional", modules=["gate"],
                    cond={"subject": "sectionLength", "op": "gt", "value": 20.0}),
            pc.Rule("default", modules=["panel"])])
        long_ = plan.plan_section(section(30.0), KIT, s)
        short = plan.plan_section(section(10.0), KIT, s)
        self.assertEqual(set(p.module for p in long_), {"gate"})
        self.assertEqual(set(p.module for p in short), {"panel"})

    def test_conditional_with_two_modules_is_its_own_else_branch(self):
        s = style([pc.Rule("default", select="conditional",
                           modules=["gate", "panel"],
                           cond={"subject": "u", "op": "lt", "value": 0.5})])
        got = plan.plan_section(dc.Section("c", 0, 0.0, 10.0, 100.0), KIT, s)
        self.assertEqual(set(p.module for p in got), {"gate"})
        got2 = plan.plan_section(dc.Section("c", 0, 60.0, 70.0, 100.0), KIT, s)
        self.assertEqual(set(p.module for p in got2), {"panel"})

    def test_every_named_conditional_subject_is_readable(self):
        ctx = {"sectionLength": 10.0, "splineLength": 40.0, "u": 0.25,
               "cornerAngle": 90.0, "segIndex": 3,
               "marker_data": {"w": 2.0}, "attrs": {"pc_section": 4}}
        for subject in plan.COND_SUBJECTS:
            self.assertIsNotNone(plan.cond_subject(subject, ctx), subject)
        self.assertEqual(plan.cond_subject("markerData:w", ctx), 2.0)
        self.assertEqual(plan.cond_subject("attr:pc_section", ctx), 4)

    def test_every_operator_works_and_a_bad_one_is_False_not_an_exception(self):
        ctx = {"segIndex": 3}
        c = lambda op, v: plan.evaluate_cond(
            {"subject": "segIndex", "op": op, "value": v}, ctx)
        self.assertTrue(c("lt", 4))
        self.assertTrue(c("le", 3))
        self.assertTrue(c("gt", 2))
        self.assertTrue(c("ge", 3))
        self.assertTrue(c("eq", 3))
        self.assertTrue(c("ne", 4))
        self.assertTrue(c("in", [1, 3, 5]))
        self.assertFalse(c("nonsense", 3))
        self.assertFalse(c("lt", "a string"))        # type mismatch, not a raise
        self.assertFalse(plan.evaluate_cond(
            {"subject": "nope", "op": "eq", "value": 1}, ctx))
        self.assertTrue(plan.evaluate_cond(None, ctx))

    def test_the_corner_angle_at_the_section_start_is_a_readable_subject(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                           (10.0, 0.0, 10.0)])
        secs = dc.decompose(c)
        s = style([pc.Rule("default", select="conditional", modules=["gate"],
                           cond={"subject": "cornerAngle", "op": "ge",
                                 "value": 45.0}),
                   pc.Rule("default", modules=["panel"])])
        got = plan.plan_sections(secs, KIT, s)
        first = [p.module for p in got if p.section_index == 0]
        second = [p.module for p in got if p.section_index == 1]
        self.assertEqual(set(first), {"panel"})       # open end, angle 0
        self.assertEqual(set(second), {"gate"})       # 90 deg corner


class TestDeterminism(unittest.TestCase):

    RANDOM = None

    def setUp(self):
        self.kit = kit(module("a", 2.0), module("b", 2.0), module("c", 2.0))

    def plan(self, seed, scope="segment", modules=("a", "b", "c")):
        s = style([pc.Rule("default", select="random", modules=list(modules),
                           scope=scope)], seed=seed)
        return plan.plan_dicts(plan.plan_section(section(40.0), self.kit, s))

    def test_the_same_seed_gives_a_byte_identical_plan(self):
        self.assertEqual(self.plan(11), self.plan(11))

    def test_a_different_seed_gives_a_different_plan(self):
        self.assertNotEqual(self.plan(11), self.plan(12))

    def test_the_plan_does_not_move_when_the_module_list_is_reordered(self):
        """⚠️ The one a naive weighted pick fails. Iterating the payload order
        makes the RESULT depend on the order the artist happened to author the
        rule in, so re-saving the style silently reshuffles a whole fence."""
        base = self.plan(11, modules=("a", "b", "c"))
        for order in (("c", "b", "a"), ("b", "a", "c"), ("a", "c", "b")):
            self.assertEqual(base, self.plan(11, modules=order), order)

    def test_the_plan_does_not_move_when_the_curves_are_reordered(self):
        curves = [pc.Curve("c%d" % i, [(0.0, 0.0, 0.0), (10.0 + i, 0.0, 0.0)])
                  for i in range(5)]
        s = style([pc.Rule("default", select="random", modules=["a", "b", "c"])],
                  seed=3)
        one = plan.plan_dicts(plan.plan_sections(
            dc.decompose_all(curves), self.kit, s))
        shuffled = list(curves)
        random.Random(1).shuffle(shuffled)
        two = plan.plan_dicts(plan.plan_sections(
            dc.decompose_all(shuffled), self.kit, s))
        self.assertEqual(one, two)

    def test_the_plan_does_not_move_when_the_markers_are_reordered(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (30.0, 0.0, 0.0)])
        ms = [pc.Marker("c", dist=d, marker_id=1) for d in (5.0, 12.0, 22.0)]
        s = style([pc.Rule("default", modules=["a"]),
                   pc.Rule("marker:1", modules=["b"])], seed=3)
        one = plan.plan_dicts(plan.plan_sections(dc.decompose(c, ms),
                                                 self.kit, s))
        two = plan.plan_dicts(plan.plan_sections(
            dc.decompose(c, list(reversed(ms))), self.kit, s))
        self.assertEqual(one, two)

    def test_the_scope_correlates_exactly_what_3_3_says_it_does(self):
        seg = [d["pc_module"] for d in self.plan(5, "segment")]
        sec = [d["pc_module"] for d in self.plan(5, "section")]
        spl = [d["pc_module"] for d in self.plan(5, "spline")]
        gen = [d["pc_module"] for d in self.plan(5, "generator")]
        self.assertGreater(len(set(seg)), 1)          # varies piece to piece
        self.assertEqual(len(set(sec)), 1)            # one pick per section
        self.assertEqual(len(set(spl)), 1)
        self.assertEqual(len(set(gen)), 1)

    def test_two_sections_of_one_spline_correlate_under_spline_scope(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0),
                           (20.0, 0.0, 20.0)])
        s = style([pc.Rule("default", select="random", modules=["a", "b", "c"],
                           scope="spline")], seed=4)
        got = plan.plan_section
        secs = dc.decompose(c)
        picks = set()
        for sec in secs:
            picks |= set(p.module for p in got(sec, self.kit, s))
        self.assertEqual(len(picks), 1)

    def test_section_scope_does_NOT_correlate_across_sections(self):
        c = pc.Curve("c", [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0),
                           (20.0, 0.0, 20.0)])
        s = style([pc.Rule("default", select="random", modules=["a", "b", "c"],
                           scope="section")], seed=4)
        secs = dc.decompose(c)
        picks = [set(p.module for p in plan.plan_section(sec, self.kit, s))
                 for sec in secs]
        self.assertEqual([len(x) for x in picks], [1, 1])
        self.assertNotEqual(picks[0], picks[1])

    def test_plan_dicts_carries_the_whole_3_4_element_contract(self):
        d = self.plan(11)[0]
        for key in ("pc_elem_id", "pc_elem_key", "pc_slot", "pc_module",
                    "pc_variant", "pc_section", "pc_u"):
            self.assertIn(key, d)
        self.assertEqual(d["pc_elem_id"].count("|"), 4)

    def test_pc_u_is_the_position_along_the_PARENT_curve(self):
        """D16. A section halfway down a curve must not report u from 0."""
        s = dc.Section("c", 1, 50.0, 60.0, 100.0)
        got = plan.plan_section(s, self.kit, default_style(("a",)),
                                pc.Params(fill="count", count=2))
        self.assertAlmostEqual(got[0].u, 0.50, delta=TOL)
        self.assertAlmostEqual(got[1].u, 0.55, delta=TOL)


class TestZModes(unittest.TestCase):

    def test_the_module_z_mode_is_the_default_and_the_style_overrides_it(self):
        """D6: 3.2 makes the module value a default and the style an override,
        which needs a third state for "the style said nothing"."""
        k = kit(module("picket", 2.0, zmode="vertical"))
        got = plan.plan_section(section(10.0), k, default_style(("picket",)))
        self.assertEqual(set(p.zmode for p in got), {"vertical"})
        got = plan.plan_section(section(10.0), k, default_style(("picket",)),
                                pc.Params(zmode="stepped"))
        self.assertEqual(set(p.zmode for p in got), {"stepped"})

    def test_an_unknown_z_mode_falls_back_rather_than_failing(self):
        self.assertEqual(pc.Module("m", 1.0, zmode="sideways").zmode, "adaptive")

    def test_the_deform_flag_rides_onto_every_placement(self):
        got = plan.plan_section(section(10.0), KIT, default_style(("tile",)))
        self.assertEqual(set(p.deform for p in got), {pc.DEFORM_SLICE})


class TestWholeCurves(unittest.TestCase):
    """End to end: geometry-shaped input, a plan out, nothing in between."""

    def test_a_closed_fence_covers_every_section_of_the_rectangle(self):
        c = pc.Curve("fence", [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0),
                               (12.0, 0.0, 8.0), (0.0, 0.0, 8.0)], closed=True)
        secs = dc.decompose(c)
        s = style([pc.Rule("default", modules=["panel"]),
                   pc.Rule("evenly", modules=["post"])])
        got = plan.plan_sections(secs, KIT, s, pc.Params(evenly_spacing=3.0))
        self.assertEqual(len(secs), 4)
        for sec in secs:
            mine = [p for p in got if p.section_index == sec.index]
            covers(self, mine, 0.0, sec.length)
        self.assertEqual(len(set(p.elem_id for p in got)), len(got))
        self.assertEqual(plan.warnings_of(got), {})

    def test_a_painted_pc_section_swap_mid_run_changes_style_key_not_coverage(self):
        c = pc.Curve("street", [(x, 0.0, 0.0) for x in (0.0, 5.0, 10.0, 15.0)],
                     section_ids=[1, 1, 2, 2])
        secs = dc.decompose(c)
        self.assertEqual([s.section_key for s in secs], [1, 2])
        got = plan.plan_sections(secs, KIT, default_style(("panel",)))
        self.assertEqual(sorted(set(p.section_key for p in got)), [1, 2])
        for sec in secs:
            covers(self, [p for p in got if p.section_index == sec.index],
                   0.0, sec.length)

    def test_the_STYLE_carries_its_own_params_when_none_are_passed(self):
        """2.1's two-face principle: a style payload wired into input 3
        "overrides the parms entirely". A caller holding only the style must
        therefore get the style's fill mode, not the HDA defaults - silently
        planning `adaptive` for a payload that says `tile` drops the whole
        pipeline face with no error anywhere."""
        s = style([pc.Rule("default", modules=["tile"])])
        s.params = pc.Params(fill="tile")
        got = plan.plan_section(section(11.0), KIT, s)
        self.assertEqual(len(got), 6)
        self.assertAlmostEqual(got[-1].slice_t, 0.5, delta=TOL)
        # an explicit argument is still the artist face, and still wins
        forced = plan.plan_section(section(11.0), KIT, s,
                                   pc.Params(fill="adaptive"))
        self.assertTrue(all(p.slice_t is None for p in forced))
        self.assertEqual(plan.plan_sections([section(11.0)], KIT, s)[-1].slice_t,
                         got[-1].slice_t)

    def test_ten_thousand_pieces_stay_addressable_and_unique(self):
        """PC-G3's own scale target, on the plan side: `pc_elem_id` is the key
        the swap/replace cascade matches on, so a collision there is a wrong
        module in the viewport. The string address cannot collide (D1); this
        is the assertion that says so out loud."""
        got = plan.plan_section(section(20000.0), KIT,
                                default_style(("panel",)))
        self.assertEqual(len(got), 10000)
        ids = set(p.elem_id for p in got)
        self.assertEqual(len(ids), 10000)
        covers(self, got, 0.0, 20000.0)


class TestRandomisedAudit(unittest.TestCase):
    """The review pass's own sweep, kept as a standing assertion.

    Hand-written cases pin the bugs that were found; this one is what found
    the shape of them. Over 1500 seeded kit/style/section combinations -
    including negative padding, padding wider than the section, closed
    sections and every fill mode - the solve may not raise, may not build a
    piece backwards, may not slice a module that forbids it, and must plan the
    same thing twice. (Pre-fix this sweep reported 526 reversed placements and
    22 rigid slices; the point of keeping it is that the number stays 0.)
    """

    def _case(self, rnd):
        mods = []
        for i in range(rnd.randint(1, 3)):
            mods.append(module(
                "m%d" % i, rnd.choice([0.4, 1.0, 2.0, 3.3, 7.0]),
                pad=(rnd.choice([0.0, 0.5, -0.3, 2.0]),
                     rnd.choice([0.0, 0.5, -0.3, 2.0])),
                deform=rnd.choice([0, 1, 2]), roles="default start end evenly"))
        names = [m.name for m in mods]
        rules = [pc.Rule("default", select=rnd.choice(list(pc.SELECTORS)),
                         modules=names,
                         cond={"subject": "u", "op": "lt", "value": 0.5})]
        if rnd.random() < 0.4:
            rules += [pc.Rule("start", modules=names[:1]),
                      pc.Rule("end", modules=names[-1:])]
        if rnd.random() < 0.3:
            rules.append(pc.Rule("evenly", modules=names[:1]))
        params = pc.Params(fill=rnd.choice(list(pc.FILL_MODES)),
                           count=rnd.randint(0, 5),
                           evenly_spacing=rnd.choice([0.0, 2.0, 5.0]),
                           justify=rnd.choice(list(pc.JUSTIFY)),
                           adjust_to_end=rnd.choice([0.0, 1.0]))
        L = rnd.choice([0.3, 1.0, 4.0, 12.7, 40.0])
        marks = ([{"marker_id": 1, "s": L * 0.5, "u": 0.5, "data": {},
                   "s_local": L * 0.5}] if rnd.random() < 0.2 else [])
        sec = section(L, markers=marks, closed=rnd.random() < 0.3)
        return (sec, kit(*mods),
                style(rules, seed=rnd.randint(0, 99)), params)

    def test_no_input_makes_the_solve_raise_reverse_or_cut_a_rigid_module(self):
        rnd = random.Random(7)
        for trial in range(1500):
            sec, k, s, params = self._case(rnd)
            got = plan.plan_section(sec, k, s, params)      # must not raise
            for p in got:
                with self.subTest(trial=trial, piece=repr(p)):
                    self.assertGreaterEqual(p.length, -TOL)
                    if p.slice_t is not None:
                        self.assertGreaterEqual(p.deform, pc.DEFORM_SLICE)
                    if p.warns:
                        self.assertTrue(set(p.warns) <= set(pc.WARN_VOCAB))
            self.assertEqual(plan.plan_dicts(got),
                             plan.plan_dicts(plan.plan_section(sec, k, s,
                                                               params)),
                             trial)


if __name__ == "__main__":
    unittest.main(verbosity=2)
