"""polyChain 4.2 PLAN - what generation cannot state. No Houdini, ~0.03 s.

    python tests/unit/test_polychain_plan.py

⚠️ v2, 2026-08-25: the exact-fill, evenly, padding, warn-never-block and
randomised-audit grids are GONE from this file - they are properties, and
`tests/unit/test_polychain_properties.py` states them over generated input
with Hypothesis instead of over a hand-written 4 x 6 grid.  That was not a
like-for-like swap: generation found two real defects the grid structurally
could not (`tile` does not fill exactly at any non-zero gap - the grid only
ever ran tile at gap 0; `evenly` has no MAX_UNITS ceiling and hangs).

What is left is the SLOT / SELECTION / Z-MODE / WHOLE-CURVE behaviour, which
is a lookup table and a set of rules rather than a numeric property: there is
nothing for a generator to sweep, and the assertion is that a named input
picks a named module.
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

    def test_a_custom_prim_attr_reaches_a_conditional(self):
        """D94 - 3.3 says `attr:<name>` reads ANY spline prim attr.

        Until this it read exactly two names, because the geometry adapter
        never harvested the prim's attributes and `plan_section` hardcoded
        `pc_section`/`pc_style`. `road_width` IS the first consumer's hook
        (streets, selecting off the stream's own edge data), and it declined
        every piece in silence.
        """
        section = dc.Section("c", 0, 0.0, 12.0, 12.0,
                             attrs={"road_width": 9.0})
        style = pc.Style("s", 1, 1, rules=[
            pc.Rule("default", "conditional", ["gate", "panel"],
                    cond={"subject": "attr:road_width", "op": "gt",
                          "value": 1.0})])
        got = plan.plan_section(section, KIT, style)
        self.assertTrue(got)
        self.assertEqual(set(p.module for p in got), {"gate"})
        # ...and the kernel's own two are still there beside it
        narrow = dc.Section("c", 0, 0.0, 12.0, 12.0,
                            attrs={"road_width": 0.5})
        self.assertEqual(
            set(p.module for p in plan.plan_section(narrow, KIT, style)),
            {"panel"})

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

    def test_an_unknown_STYLE_z_mode_degrades_to_the_module_not_to_adaptive(self):
        """D6's third state is also the landing place for junk.

        `Params.zmode` was unguarded so that "" could mean "the module wins",
        and an invalid non-empty value then overrode every module and resolved
        to `adaptive` downstream - discarding the artist's intent AND the
        module's own default at once. A case-slipped "Vertical" in a style
        payload banked every picket on a hillside instead of leaving it plumb,
        silently, while the SAME typo on the kit side is warned by
        `kit.validate`. Degrading to "" builds the fence the artist meant.
        """
        self.assertEqual(pc.Params(zmode="Vertical").zmode, "")
        k = kit(module("picket", 2.0, zmode="vertical"))
        got = plan.plan_section(section(10.0), k, default_style(("picket",)),
                                pc.Params(zmode="Vertical"))
        self.assertEqual(set(p.zmode for p in got), {"vertical"})

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




if __name__ == "__main__":
    unittest.main(verbosity=2)
