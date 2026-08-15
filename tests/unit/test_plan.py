"""The S5 planner, calibrated against the builder's own plates. No Houdini.

    python tests/unit/test_plan.py

⚠️ **CALIBRATE, DO NOT INVENT** (§11.4). `plan.crossing_trims` predicts what
`s5j_solve` cuts off each arm, as a function of arms, widths, classes and
angles, so `standing` is checkable before any geometry exists. The measured
plates it is checked against live in `trim_calibration.json`, written by
`hython tests/citygen/dump_trims.py` on all eleven cases — 524 arms.

MUTATION-TESTED across four audit rounds (10, then 16, then 1 real survivor).
The tables, the tolerances, the `_straightest` key and its returned order, and
the dust epsilon are all two-sided-pinned. What survives is recorded below so the
next round does not re-derive it — ⚠️ **and a short list is worse than none, so
add to it rather than trusting it blind** (round 4 found this list three
entries short).

EQUIVALENT, PROVEN:

  * `i >= nseg` -> `i > nseg` and dropping `clear_of_vertex`'s final push
    refusal each survive ALONE and are killed TOGETHER — verified. They mask
    each other: allowing the far-end vertex through the first guard produces a
    push the second one refuses. Asserted jointly.
  * `resample_segments`' `length <= 0` -> `< 0`: `max(1, ceil(-1e-9))` is 1
    either way. `clear_of_vertex`'s `minseg <= 0` -> `< 0`: every downstream
    branch returns `cut` unchanged at 0.
  * `_corner`'s `max(raw + run, ka)` floor: subsumed by `crossing_trims`' own
    `max(ahead, behind, 0.0)`.
  * `_straightest`'s `key < best` -> `<=`: equivalent ONLY because `edge_id` is
    unique per node — it stops being equivalent on a self-loop (below).
  * `EPS` 1e-6 -> 1e-3. Two of its three uses (`max_half < EPS`, `k_len > EPS`)
    need a sub-millimetre carriageway. The third, `tan(half) < EPS`, is
    discriminated by an ANGLE and is dead only because `sin(half) <
    COLLINEAR_SIN` sits in front of it and `tan >= sin` on [0, pi/2). ⚠️ So it
    is unreachable *for any EPS <= COLLINEAR_SIN*: raise `COLLINEAR_SIN` and
    this needs revisiting. (`EPS = 1e-1` IS killed, by the miter test.)

⚠️ **UNREACHABLE FROM TODAY'S DATA, REACHABLE THROUGH M3's ADAPTER.** The first
three are guarantees `dump_trims.py` supplies rather than `plan.py`, so the
adapter that replaces it must re-establish them; the last three are simply
things no consumer exists to hit yet. One list, because they are one obligation:

  * `graph_trims`' `max()` guards the same END written twice. `dump_trims.py`
    derives `at_start` from `pts[0].number() == pt.number()`, so two distinct
    nodes cannot both claim one end.
  * `crossing_trims`' `hypot(direction) > 1e-9` arm filter: guaranteed by
    `dump_trims.py`'s own `if n < 1e-9: continue`.
  * A SELF-LOOP (one `edge_id` on both arms of a pair) makes `default_principal`
    return a "pair" naming one street twice. Zero closed edges today and
    `dump_trims` structurally cannot emit one — but `closeloop` exists in the
    trace wrangle, so a closed street is a real object in this pipeline.
  * `junction_trims`' `if edge_id in trims` guard: without it an authored
    `principal_edges` naming a non-incident edge is INVENTED into the result at
    0.0 m. Now pinned by keyset — it was not, which is why it is here.
  * That the stranger is silently ignored at all is pinned behaviour, NOT an
    endorsement: warn / raise / fall back is an M4 decision (11.12).
  * `plan.py` has no consumer at all, which §11.2 forbids: M3 owes it one.

Two things this file is deliberately NOT:

  * it is not a green light. The residual is PINNED per case, at the value
    measured on 2026-08-15, so the model getting worse goes red — the baseline
    discipline, applied to a function instead of a scene.
  * it is not idempotence. The model is exact on straight arms and it is not
    exact on curved ones, and the difference is named and bounded rather than
    tolerated by a loose global epsilon.
"""

import json
import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "polyfactory", "scripts", "python",
                                "polyfactory"))

from citygen import plan  # noqa: E402

CALIBRATION = os.path.join(HERE, "trim_calibration.json")

# ⚠️ Measured 2026-08-15, and the split down the middle of this table IS the
# finding. Every case whose arms are STRAIGHT is reproduced exactly; every case
# with traced, curved arms is not, because `s5j_solve` re-solves each corner in
# the frame at its own cut and the planner has no arm shape to do that with.
# The bound is the worst |predicted - measured| over the case's arms, plus a
# hair. Move one of these only with the measurement that justifies it.
RESIDUAL_M = {
    "E_short_t":       0.001,   # measured 0.000000
    "F_bend":          0.001,   # measured 0.000001
    "G_tongue":        0.001,   # measured 0.000000
    "J_five_star":     0.001,   # measured 0.000034
    "K_stub_triangle": 0.001,   # measured 0.000007
    "A_drawn":         2.03,    # measured 2.024024
    "D_offset":        2.03,    # measured 2.024024
    "H_offset_strict": 2.03,    # measured 2.024024
    "B_grid":          4.00,    # measured 3.994844
    "C_radial":        4.58,    # measured 4.575012
    "I_offset_radial": 4.58,    # measured 4.575012
}

# ...and the bulk, because a max can stand still while the middle of the
# distribution rots. Arms further than 0.5 m from the builder, per case.
OVER_HALF_METRE = {
    "A_drawn": 2, "B_grid": 24, "C_radial": 97, "D_offset": 2,
    "E_short_t": 0, "F_bend": 0, "G_tongue": 0, "H_offset_strict": 2,
    "I_offset_radial": 97, "J_five_star": 0, "K_stub_triangle": 0,
}

# ⚠️ The residual on an ARM is not the number a consumer needs, and reporting it
# as though it were is how the first version of this file recorded a 2.02 m
# safety margin for a 5.88 m error. `crossing_trims` feeds `standing`, the two
# ends compound, and only one direction is dangerous: the planner claiming more
# street stands than the builder leaves. Both tails are pinned, per case,
# signed — (worst optimistic, worst pessimistic) on `standing`.
STANDING_ERROR_M = {
    "A_drawn":        (0.35, -2.03),
    "D_offset":       (0.35, -2.03),
    "H_offset_strict": (0.35, -2.03),
    "B_grid":         (4.00, -2.41),
    "C_radial":       (5.88, -8.42),
    "I_offset_radial": (5.88, -8.42),
    "E_short_t":      (0.001, -0.001),
    "F_bend":         (0.001, -0.001),
    "G_tongue":       (0.001, -0.001),
    "J_five_star":    (0.001, -0.001),
    "K_stub_triangle": (0.001, -0.001),
}

STRAIGHT_CASES = ("E_short_t", "F_bend", "G_tongue", "J_five_star",
                  "K_stub_triangle")


def load():
    with open(CALIBRATION) as fh:
        return json.load(fh)


def case_nodes(case):
    """The dumped case as planner data, plus the params the builder used."""
    pp = case["params"]
    params = plan.Params(pp["miter_limit"], pp["corner_radius_scale"],
                         pp["max_fillet_fraction"], pp["min_end_segment"])
    nodes = []
    for nd in case["nodes"]:
        arms = [plan.Arm(a["edge_id"], a["dir"], a["width"], a["street_class"],
                         a["length"], a["at_start"]) for a in nd["arms"]]
        nodes.append(plan.Node("(%.3f,%.3f)" % tuple(nd["pos"]), nd["pos"], arms))
    return nodes, params


def residuals(case):
    """[(predicted - measured, node, edge_id)] over every arm of every node."""
    nodes, params = case_nodes(case)
    out = []
    for node, nd in zip(nodes, case["nodes"]):
        pred = plan.crossing_trims(node, params)
        for a in nd["arms"]:
            out.append((pred[a["edge_id"]] - a["measured_trim"],
                        node.node_id, a["edge_id"]))
    return out


class TestCalibration(unittest.TestCase):
    """The gate under §11.4: the model must reproduce the plates it replaces."""

    @classmethod
    def setUpClass(cls):
        cls.data = load()

    def test_every_case_is_present(self):
        self.assertEqual(sorted(self.data["cases"]), sorted(RESIDUAL_M))

    def test_the_fixture_does_not_contradict_itself(self):
        """Each arm carries its own copy of its edge's width, class and length,
        and NOTHING cross-checked the two — so corrupting one copy (round 2 of
        the audit added 10 m to a single arm's length) left the suite green.
        Two records of one fact need an assertion that they agree, or the
        calibration is only as good as whichever copy a given test happens to
        read."""
        for name in sorted(self.data["cases"]):
            case = self.data["cases"][name]
            edges = dict((e["edge_id"], e) for e in case["edges"])
            for nd in case["nodes"]:
                for a in nd["arms"]:
                    e = edges[a["edge_id"]]
                    with self.subTest(case=name, edge=a["edge_id"]):
                        self.assertAlmostEqual(a["length"], e["length"], places=9)
                        self.assertAlmostEqual(a["width"], e["width"], places=9)
                        self.assertEqual(a["street_class"], e["street_class"])
                        self.assertEqual(
                            a["measured_trim"],
                            e["trim_start"] if a["at_start"] else e["trim_end"])

    def test_residual_is_within_its_pinned_bound_AND_the_bound_is_tight(self):
        """⚠️ Two-sided, because a table of upper bounds certifies itself.

        Round 3 mutated every entry here to 99.0 and the suite stayed green — so
        the table asserted nothing about the model, only that the model was no
        worse than a number the table itself chose. A bound that is not also a
        floor is a comment. Tightness is 0.02 m: enough that the last digit of a
        measurement can move, not enough to hide a metre.
        """
        for name in sorted(self.data["cases"]):
            with self.subTest(case=name):
                res = residuals(self.data["cases"][name])
                worst = max(res, key=lambda r: abs(r[0]))
                bound = RESIDUAL_M[name]
                self.assertLessEqual(
                    abs(worst[0]), bound,
                    "%s: %.6f m at node %s on %s" % (name, worst[0], worst[1],
                                                     worst[2]))
                # ⚠️ `bound - 0.02` is VACUOUS where the bound is 1 mm — it
                # reads `> -0.019` and passes for anything, so the five exact
                # cases could be loosened 20x unnoticed. They get an equality
                # instead: their bound is the exactness floor, not a measurement.
                if name in STRAIGHT_CASES:
                    self.assertEqual(bound, 1e-3, name)
                else:
                    self.assertGreater(abs(worst[0]), bound - 0.02,
                                       "%s: bound %.3f is slack against %.6f"
                                       % (name, bound, abs(worst[0])))

    def test_STRAIGHT_CASES_is_derived_from_the_data_not_asserted_over_it(self):
        """The list of exactly-reproduced cases must BE the set of cases that
        reproduce exactly. Dropping K from it left the suite green, which would
        have quietly retired the strongest assertion the K verdict rests on."""
        exact = set(name for name in self.data["cases"]
                    if max(abs(r[0]) for r in residuals(self.data["cases"][name]))
                    <= 1e-3)
        self.assertEqual(exact, set(STRAIGHT_CASES))

    def test_straight_armed_cases_are_reproduced_exactly(self):
        """The strong form, and the one with teeth.

        No frame refinement can hide here, so this fails on any error in the
        kerb-line corner, the miter clamp, the fillet run, the CCW ordering, the
        `max_fillet_fraction` clamp or the vertex push. K is in this set, which
        is what makes the junction verdict below trustworthy.
        """
        for name in STRAIGHT_CASES:
            with self.subTest(case=name):
                res = residuals(self.data["cases"][name])
                self.assertLessEqual(max(abs(r[0]) for r in res), 1e-3, name)

    def test_bulk_of_the_distribution_has_not_moved(self):
        """Exact, not `<=`. This table exists because "a max can stand still
        while the middle of the distribution rots" — and as an upper bound it
        could not see the middle IMPROVING either, so it could not tell a real
        change from none. Every entry mutated to 999 used to pass."""
        for name in sorted(self.data["cases"]):
            with self.subTest(case=name):
                res = residuals(self.data["cases"][name])
                over = sum(1 for r in res if abs(r[0]) > 0.5)
                self.assertEqual(over, OVER_HALF_METRE[name], name)

    def test_the_standing_VERDICT_never_disagrees_with_the_builder(self):
        """⚠️ THE ASSERTION EVERYTHING DOWNSTREAM ACTUALLY RESTS ON.

        Every metre in `RESIDUAL_M` above is a bound on the model's ERROR. What
        M4/M5/M6 consume is not the metre, it is the ANSWER: does this street
        still stand once both its junctions have taken their bite? A planner
        that is 4 m out and still calls every street correctly is usable; one
        that is 0.1 m out and flips a verdict is not, and no residual table can
        tell the two apart.

        Measured over all 304 edges of the suite: zero false-OK (planner says
        the street stands, the builder ate it) and zero false-BAD. That result
        was found by the M1 audit and was not asserted anywhere, which is
        exactly how a good property rots.
        """
        false_ok, false_bad, edges = [], [], 0
        for name in sorted(self.data["cases"]):
            case = self.data["cases"][name]
            nodes, params = case_nodes(case)
            got = plan.graph_trims(nodes, params)
            for e in case["edges"]:
                edges += 1
                start, end = got.get(e["edge_id"], (0.0, 0.0))
                mine = plan.standing(e["length"], start, end)
                theirs = plan.standing(e["length"], e["trim_start"],
                                       e["trim_end"])
                if mine > 0 >= theirs:
                    false_ok.append((name, e["edge_id"], mine, theirs))
                elif theirs > 0 >= mine:
                    false_bad.append((name, e["edge_id"], mine, theirs))
        self.assertEqual(edges, 304)
        self.assertEqual(false_ok, [])
        self.assertEqual(false_bad, [])

    def test_standing_error_stays_inside_its_pinned_tails(self):
        """...and the size of the error, signed, because the two directions are
        not equally bad and the module advertises a bound on the dangerous one."""
        worst_optimistic = 0.0
        for name in sorted(self.data["cases"]):
            case = self.data["cases"][name]
            nodes, params = case_nodes(case)
            got = plan.graph_trims(nodes, params)
            errs = []
            for e in case["edges"]:
                start, end = got.get(e["edge_id"], (0.0, 0.0))
                errs.append(plan.standing(e["length"], start, end)
                            - plan.standing(e["length"], e["trim_start"],
                                            e["trim_end"]))
            hi, lo = STANDING_ERROR_M[name]
            with self.subTest(case=name):
                self.assertLessEqual(max(errs), hi, name)
                self.assertGreaterEqual(min(errs), lo, name)
                # ...and tight, or the table certifies itself (round 3 set every
                # entry to (99, -99) and nothing noticed). Same vacuity as
                # RESIDUAL_M on the exact cases, and the same cure.
                if name in STRAIGHT_CASES:
                    self.assertEqual((hi, lo), (0.001, -0.001), name)
                else:
                    self.assertGreater(max(errs), hi - 0.02, "%s hi slack" % name)
                    self.assertLess(min(errs), lo + 0.02, "%s lo slack" % name)
            worst_optimistic = max(worst_optimistic, max(errs))
        # the constant the module publishes must be the measurement, not a
        # leftover: mutating it to anything else has to go red here
        self.assertLessEqual(worst_optimistic, plan.STANDING_OPTIMISM_M)
        self.assertGreater(worst_optimistic, plan.STANDING_OPTIMISM_M - 0.01)

    def test_the_published_per_arm_residual_is_the_measured_one(self):
        worst = 0.0
        for name in sorted(self.data["cases"]):
            worst = max(worst, max(abs(r[0])
                                   for r in residuals(self.data["cases"][name])))
        self.assertLessEqual(worst, plan.CURVED_ARM_RESIDUAL_M)
        self.assertGreater(worst, plan.CURVED_ARM_RESIDUAL_M - 0.01)

    def test_graph_trims_lands_each_cut_on_the_right_END_of_the_right_street(self):
        """The assembly, not the corner — a different code path with its own way
        to be wrong.

        `crossing_trims` is per node and says nothing about which of a street's
        two ends a cut belongs to, or what happens to a street carrying a
        junction at both. Swapping `trim_start` for `trim_end` leaves every
        per-arm comparison above green and makes every `standing` on a
        two-junction street garbage. Asserted against the builder's own
        `trim_start` / `trim_end` on all 524 arms — and every street the builder
        cut must be a street the planner saw, which is the coverage half of the
        same claim: an arm silently dropped in node extraction would leave the
        per-arm comparison green and simply not be checked.
        """
        seen = 0
        for name in sorted(self.data["cases"]):
            case = self.data["cases"][name]
            nodes, params = case_nodes(case)
            got = plan.graph_trims(nodes, params)
            bound = RESIDUAL_M[name]
            for e in case["edges"]:
                start, end = got.get(e["edge_id"], (0.0, 0.0))
                with self.subTest(case=name, edge=e["edge_id"]):
                    self.assertLessEqual(abs(start - e["trim_start"]), bound)
                    self.assertLessEqual(abs(end - e["trim_end"]), bound)
                    # ⚠️ assert the BUILDER's number, not a default this test
                    # made up. The first version checked `start == 0.0` under a
                    # guard that made `start` the literal fallback — a check
                    # that could not fail.
                    if e["edge_id"] not in got:
                        self.assertEqual(e["trim_start"], 0.0)
                        self.assertEqual(e["trim_end"], 0.0)
                    else:
                        seen += 1
        self.assertEqual(seen, 304, "the planner did not see every street")


class TestKVerdict(unittest.TestCase):
    """§11.4's experiment: does `junction` type rescue K's stub triangle?

    K's three 32 m sides are trimmed from BOTH ends by two crossing plates and
    end up with negative standing — the plates physically overlap. The question
    the whole spread depends on is whether a node type that leaves a principal
    pair unbroken removes the need to move any node at all.

    Answered here on K's own measured numbers, and the answer is NO for the
    computed default and YES for a straight-through principal. Both are asserted
    so neither can drift.
    """

    @classmethod
    def setUpClass(cls):
        cls.case = load()["cases"]["K_stub_triangle"]
        cls.nodes, cls.params = case_nodes(cls.case)
        cls.edges = dict((e["edge_id"], e) for e in cls.case["edges"])
        # a triangle side is an edge with a junction at both ends
        pos = [n.pos for n in cls.nodes]
        cls.sides = sorted(
            e["edge_id"] for e in cls.case["edges"]
            if sum(1 for p in pos if min(math.dist(p, e["p0"]),
                                         math.dist(p, e["p1"])) < 1e-3) == 2)

    def _standing(self, kind, principals=None):
        for node in self.nodes:
            node.junction_type = kind
            node.principal_edges = () if principals is None \
                else principals[node.node_id]
        trims = plan.graph_trims(self.nodes, self.params)
        return dict((eid, plan.standing(self.edges[eid]["length"], *trims[eid]))
                    for eid in trims)

    def test_the_three_sides_are_the_three_short_ones(self):
        self.assertEqual(len(self.sides), 3)
        for eid in self.sides:
            self.assertLess(self.edges[eid]["length"], 33.0)

    def test_crossing_overlaps_on_all_three_sides(self):
        """Today's build, and it reproduces the gate's own number.

        `trim_leaves_road_standing` reports min_standing_m -13.434 at (32.0,
        0.0) on this case. The planner reaches the same metre without cooking
        anything, which is the whole claim of §11.4.
        """
        st = self._standing("crossing")
        got = sorted(round(st[e], 3) for e in self.sides)
        self.assertEqual(got, [-13.434, -10.0, -6.651])
        self.assertAlmostEqual(min(st.values()), -13.434, places=3)

    def test_widest_pair_principal_rescues_ONE_side_of_three(self):
        """⚠️ THE VERDICT, AND IT IS NEGATIVE.

        At every corner of K the two widest arms are the EXTERNAL arterial and
        collector, so both triangle sides at that corner stay minors and keep
        their full trim. Only the third corner — degree 3, all three arms 14.4 m
        locals — has a triangle side wide enough to be principal, and it can
        only take one of the two.

        So `junction` type with the computed default does NOT dissolve K, and
        the resolution ladder still needs its next rung. The spread is not dead.
        """
        st = self._standing("junction")
        rescued = [e for e in self.sides if st[e] > 0]
        self.assertEqual(len(rescued), 1)
        self.assertAlmostEqual(min(st[e] for e in self.sides), -13.434, places=3)

    @staticmethod
    def _straightest(node, tol_rad=1e-6):
        """The pair nearest 180 degrees apart, with the SAME tie-break §11.3
        needs and for the same reason.

        ⚠️ Without a tie-break this rule is undefined on K. Node C is exactly
        symmetric — |CA| = |CB| = 32.249031 and the third arm runs along the
        axis of symmetry — so two pairs are equally straight, separated by
        **2.311e-07 rad** of float noise. `tol_rad` quantises that away, which
        is right (2.3e-7 rad is not a difference) and which is also what MAKES
        it a tie, so the rest of the key has to settle it.

        ⚠️ **AND THE FIRST VERSION OF THAT KEY READ ONLY ARM `i`, SO THE
        COIN-FLIP MOVED FROM FLOAT NOISE TO ARM ORDER.** Round 2 of the M1 audit
        enumerated all six orderings of node C's arms: five gave the pair that
        dissolves K and ordering (0, 2, 1) gave the other one, +11.000 m turning
        into −6.651 m on the sequence `pointprims()` happened to return. On a
        symmetric X, 12 of 24 permutations disagreed. The key below is built
        from BOTH arms, sorted, so it is a property of the pair and not of the
        loop — and `edge_id` is unique, so no two pairs can tie all the way
        down.

        ⚠️ **AND THE SECOND VERSION LEAKED THE SAME DEPENDENCE OUT OF ITS
        RETURN VALUE.** Round 3 found that making the winning SET
        order-independent left the returned TUPLE ordered by arm index — and the
        next test down indexed it. Both halves are now canonical: the key is
        built from the sorted pair, and so is what comes back.
        """
        best = None
        for i in range(len(node.arms)):
            for j in range(i + 1, len(node.arms)):
                a, b = node.arms[i], node.arms[j]
                gap = abs(a.bearing - b.bearing)
                gap = min(gap, 2 * math.pi - gap)
                pair = sorted((-round(x.width / plan.RANK_TOL_M),
                               -round(x.length / plan.RANK_TOL_M), x.edge_id)
                              for x in (a, b))
                key = (round(abs(math.pi - gap) / tol_rad), pair)
                if best is None or key < best[0]:
                    best = (key, tuple(sorted((a.edge_id, b.edge_id))))
        return best[1]

    def test_the_straightest_rule_does_not_depend_on_ARM_ORDER(self):
        """⚠️ THE DEFECT ROUND 2 FOUND IN ROUND 1's FIX, pinned at its root.

        A rule §11.3 recommends to the artist as a computed default may not
        depend on the order `pointprims()` hands back its arms. Asserted over
        every ordering of K's node C — the exactly-symmetric one — and over a
        symmetric X where two pairs are exactly 180 degrees apart, which is the
        case that has no float noise to hide behind at all.

        ⚠️ It asserts the returned TUPLE, not just the set it contains. The
        first version compared `frozenset(...)` — which is blind to exactly the
        half of the guarantee round 3 had to add, so reverting the `sorted()` in
        `_straightest` left all 42 tests green while the neighbouring test went
        back to being arm-order-dependent. A fix without an assertion is a fix
        with a countdown on it.
        """
        import itertools
        node = [n for n in self.nodes if abs(n.pos[0] - 16.0) < 0.01][0]
        base = list(node.arms)
        try:
            answers = set()
            for perm in itertools.permutations(range(len(base))):
                node.arms = [base[i] for i in perm]
                answers.add(self._straightest(node))
            self.assertEqual(len(answers), 1, "arm order changed the principal")
        finally:
            node.arms = base

        sq = [plan.Arm("n", (0, 1), 14.4, "local", 100.0),
              plan.Arm("e", (1, 0), 14.4, "local", 100.0),
              plan.Arm("s", (0, -1), 14.4, "local", 100.0),
              plan.Arm("w", (-1, 0), 14.4, "local", 100.0)]
        answers = set()
        for perm in itertools.permutations(range(4)):
            answers.add(self._straightest(
                plan.Node("x", (0, 0), [sq[i] for i in perm])))
        self.assertEqual(len(answers), 1, "a symmetric X is order-dependent")
        # ...and on the three crosses the key test uses, where two pairs tie at
        # every level and the natural i<j order is NOT already sorted
        for delta, wide in ((2e-7, False), (1e-5, False), (0.0, True)):
            arms = self._cross(delta, wide).arms
            got = set()
            for perm in itertools.permutations(range(4)):
                got.add(self._straightest(
                    plan.Node("x", (0, 0), [arms[i] for i in perm])))
            self.assertEqual(len(got), 1, "delta=%r wide=%r" % (delta, wide))

    def test_straight_through_principal_dissolves_K_entirely(self):
        """...and the same node type with a different principal RULE does.

        Pick the pair closest to 180 degrees apart at each corner — one street
        actually running through, which is what a principal street means — and
        every side of the triangle stands, worst +11.000 m, with no node moved.
        The rule, not the type, is what decides whether the spread is needed.
        """
        principals = dict((n.node_id, self._straightest(n)) for n in self.nodes)
        st = self._standing("junction", principals)
        for eid in self.sides:
            self.assertGreater(st[eid], 0.0, eid)
        self.assertAlmostEqual(min(st.values()), 11.0, places=3)

    def test_and_the_OTHER_resolution_of_that_tie_does_not(self):
        """⚠️ THE CAVEAT ON THE ROW ABOVE, pinned so it travels with it.

        K's third corner offers two equally-straight pairs. Take the other one
        and A–C goes back to -6.651 m: the straightest-pair rule dissolves K
        only with a tie-break, and the tie-break that happens to work is the
        lexicographic `edge_id` — which is luck, not a reason. Whoever ships a
        computed default (11.12) has to decide this on purpose.

        ⚠️ The two pairs are named outright, exactly as §11.4's table names
        them. Deriving "the other one" by position — which this test used to do
        — reads an ordering the rule does not promise, and under half of node
        C's arm orderings it built a THIRD pair that is in neither row of the
        table and dissolves K as well. A caveat that only holds for some input
        orderings is not a caveat.
        """
        pre = "region_+00_+00/"
        chosen, other = pre + "E_00001", pre + "E_00004"
        principals = dict((n.node_id, self._straightest(n)) for n in self.nodes)
        for node in self.nodes:
            if abs(node.pos[0] - 16.0) < 0.01:          # K's node C
                self.assertEqual(principals[node.node_id],
                                 tuple(sorted((chosen, pre + "E_00007"))))
                principals[node.node_id] = (pre + "E_00007", other)
        st = self._standing("junction", principals)
        self.assertEqual(sum(1 for e in self.sides if st[e] <= 0), 1)
        self.assertAlmostEqual(min(st[e] for e in self.sides), -6.651, places=3)

    @staticmethod
    def _cross(delta_rad, wide_pair=False):
        """Four arms in two opposed pairs, one pair off-axis by `delta_rad`.

        Named so that a tie falls to `a_*` and a strict angle comparison falls
        to `c_*`, which is what makes the two answers distinguishable.
        """
        w = 26.8 if wide_pair else 14.4
        d = 3 * math.pi / 2 + delta_rad
        return plan.Node("x", (0, 0), [
            plan.Arm("a_n", (0.0, 1.0), 14.4, "local", 100.0),
            plan.Arm("b_s", (math.cos(d), math.sin(d)), 14.4, "local", 100.0),
            plan.Arm("c_e", (1.0, 0.0), w, "arterial" if wide_pair else "local",
                     100.0),
            plan.Arm("d_w", (-1.0, 0.0), w, "arterial" if wide_pair else "local",
                     100.0)])

    def test_the_straightest_key_is_pinned_at_every_level(self):
        """⚠️ `tol_rad` is `RANK_TOL_M`'s twin and it was free to be anything:
        1e-12 and 1.0 both left the suite green, and so did reducing the pair
        key to `edge_id` alone. The first version of this test computed buckets
        itself — a copy of the formula, which is the exact mistake round 3 found
        in the epsilon test — so it could not see the shipped default move.

        Every assertion below goes through `_straightest` itself, on inputs
        built so each level of the key is the one that decides:

          * 2e-7 rad apart is NOISE. It must be quantised into a tie, or float
            picks the winner again — which is the whole reason `tol_rad` exists.
            A tolerance below the noise floor gets this wrong.
          * 1e-5 rad apart is a REAL difference. It must NOT be absorbed, or an
            unrelated pair joins the tie. A tolerance far above gets this wrong.
          * and when the angle genuinely ties, WIDTH decides before `edge_id` —
            §11.3's chain, which an `edge_id`-only key skips straight past.
        """
        # noise: tie detected, so the name decides and `a_*` wins
        self.assertEqual(self._straightest(self._cross(2e-7)), ("a_n", "b_s"))
        # a real angle: not absorbed, so the straighter `c_*` pair wins
        self.assertEqual(self._straightest(self._cross(1e-5)), ("c_e", "d_w"))
        # exact tie on angle -> the WIDER pair, though `a_*` sorts first
        self.assertEqual(self._straightest(self._cross(0.0, wide_pair=True)),
                         ("c_e", "d_w"))

    def test_the_two_tied_pairs_are_the_two_the_doc_table_names(self):
        """The premise under both tests above: node C really does offer exactly
        two equally-straight pairs, and they are the ones §11.4 tabulates. If a
        third ever ties, the table is incomplete and both verdicts are stale."""
        node = [n for n in self.nodes if abs(n.pos[0] - 16.0) < 0.01][0]
        gaps = []
        for i in range(len(node.arms)):
            for j in range(i + 1, len(node.arms)):
                g = abs(node.arms[i].bearing - node.arms[j].bearing)
                g = min(g, 2 * math.pi - g)
                gaps.append((round(abs(math.pi - g) / 1e-6),
                             frozenset((node.arms[i].edge_id,
                                        node.arms[j].edge_id))))
        best = min(g[0] for g in gaps)
        tied = sorted(sorted(e.split("/")[-1] for e in g[1])
                      for g in gaps if g[0] == best)
        self.assertEqual(tied, [["E_00001", "E_00007"],
                                ["E_00004", "E_00007"]])


class TestCornerModel(unittest.TestCase):
    """The pieces, on numbers computed by hand rather than dumped."""

    def _arm(self, bearing_deg, width, cls, length, eid="e", at_start=True):
        a = math.radians(bearing_deg)
        return plan.Arm(eid, (math.cos(a), math.sin(a)), width, cls, length,
                        at_start)

    def test_perpendicular_T_matches_the_hand_computed_tongue(self):
        """G_tongue's own sizing note, cases.py: at the perpendicular corner the
        kerb lines meet 13.4 m out (the arterial's half-width) and the fillet
        adds r/tan(45) = 4 m, so ~17.4 m of the 24 m arm is eaten.

        This is G BEFORE the tongue drop — the configuration the case was drawn
        to produce, which no longer survives to the solve. Hand-computable, so
        it pins the corner term itself rather than a dumped number.
        """
        node = plan.Node("g", (0, 0), [
            self._arm(0, 26.8, "arterial", 250.0, "east"),
            self._arm(180, 26.8, "arterial", 250.0, "west"),
            self._arm(-90, 14.4, "local", 24.0, "arm"),
        ])
        self.assertAlmostEqual(plan.crossing_trims(node)["arm"], 17.4, places=6)
        # ...and the arterials pay the LOCAL's half-width, not their own. With
        # the vertex push disabled, because a 250 m arm's grid would carry
        # 11.2 m on to 12.905 and bury the term being asserted.
        raw = plan.crossing_trims(node, plan.Params(min_end_segment=0.0))
        self.assertAlmostEqual(raw["east"], 7.2 + 4.0, places=6)

    def test_G_tongue_as_it_actually_ships(self):
        """...and the same node once the tongue is dropped: three 26.8 m
        arterials, so the corner radius is 9 m and the run is 9 m at 90 degrees.
        13.4 + 9.0 = 22.4, which is what the builder writes on all three arms."""
        node = plan.Node("g", (0, 0), [
            self._arm(0, 26.8, "arterial", 250.0, "east"),
            self._arm(180, 26.8, "arterial", 250.0, "west"),
            self._arm(90, 26.8, "arterial", 250.0, "north"),
        ])
        trims = plan.crossing_trims(node)
        for eid in ("east", "west", "north"):
            self.assertAlmostEqual(trims[eid], 22.4, places=6)

    def test_a_street_running_straight_through_costs_its_neighbours_nothing(self):
        """The collinear branch: kerbs parallel, angle ~ pi, nothing to trim."""
        node = plan.Node("t", (0, 0), [
            self._arm(0, 14.4, "local", 200.0, "east"),
            self._arm(180, 14.4, "local", 200.0, "west"),
            self._arm(90, 26.8, "arterial", 200.0, "north"),
        ])
        trims = plan.crossing_trims(node)
        # each local's corner with the OTHER local contributes 0, so what is
        # left is the corner with the arterial: 13.4 + 4.0
        self.assertAlmostEqual(trims["east"], 17.4, places=6)

    def test_a_shallow_corner_is_clamped_by_the_miter_limit(self):
        """Without the clamp the kerb-line corner spikes to infinity as the gap
        closes, so the cut must be finite and bounded by the clamped corner plus
        the fillet run.

        ⚠️ **THE WIDTHS HERE MUST DIFFER, and the first version's did not.** The
        clamp reads `max(wA, wB)` in two places, and with three identical arms
        `max` and `min` are the same number and `hypot(raw_a, ha)` and
        `hypot(raw_a, hb)` are the same length — so two wrong clamps passed. The
        M1 audit found both by mutation. An arterial against a local at 10
        degrees separates all three: correct 98.9748, `min`-width 74.3346,
        `hb`-in-the-hypot 101.0. The window is 1e-4, not 46 m.

        `min_end_segment` is off so the vertex push cannot mask the term.
        """
        node = plan.Node("m", (0, 0), [
            self._arm(0, 26.8, "arterial", 400.0, "a"),
            self._arm(10, 14.4, "local", 400.0, "b"),
            self._arm(180, 14.4, "local", 400.0, "c"),
        ])
        trims = plan.crossing_trims(node, plan.Params(min_end_segment=0.0))
        self.assertAlmostEqual(trims["a"], 98.9748, places=4)
        self.assertAlmostEqual(trims["b"], 99.2207, places=4)

    def test_the_collinear_threshold_is_where_the_builder_puts_it(self):
        """`pfsj_corner_lines` gives up at |sin(gap)| < 0.02 — about 1.146
        degrees — and returns a fallback that pushes clear of both streets
        instead of a corner. Mutating the constant either way used to change
        nothing on any case and no test, because the only collinear test sat at
        exactly 0/180 where every threshold agrees.

        1.1 degrees (sin 0.0192) is inside the dead band, 1.2 (sin 0.0209) is
        out, and the two answers are nothing like each other.

        ⚠️ **AND THE WIDTHS MUST DIFFER HERE TOO.** The first version of this
        test used three 14.4 m locals and so reproduced, inside the test written
        to close one audit finding, the exact defect of another: the fallback is
        `max(a.width, b.width)` and with equal arms `max` and `min` are the same
        number, so a wrong one passed. **Zero of the suite's 524 corners take
        this branch** — all 49 collinear corners are the angle≈pi side — so this
        hand-built node is its only coverage anywhere in the repo.
        """
        p = plan.Params(min_end_segment=0.0)

        def cut(gap):
            node = plan.Node("s", (0, 0), [
                self._arm(0, 14.4, "local", 900.0, "a"),
                self._arm(gap, 26.8, "arterial", 900.0, "b"),
                self._arm(180, 14.4, "local", 900.0, "c"),
            ])
            return plan.crossing_trims(node, p)["a"]

        # inside: the fallback push, which is the WIDER of the two streets
        self.assertAlmostEqual(cut(1.1), 26.8, places=6)
        # outside: the real miter-clamped corner, far bigger
        self.assertGreater(cut(1.2), 40.0)

    def test_the_fillet_run_is_capped_at_max_fillet_fraction(self):
        """E_short_t's binding condition: r = 4 x 2.5 = 10 m of radius wants
        10 m of run at a right angle, and 0.4 x the 20 m arm allows 8."""
        p = plan.Params(corner_radius_scale=2.5)
        node = plan.Node("e", (0, 0), [
            self._arm(0, 14.4, "local", 60.0, "east"),
            self._arm(180, 14.4, "local", 60.0, "west"),
            self._arm(90, 14.4, "local", 20.0, "arm"),
        ])
        # 7.2 (the through street's half-width) + 8.0 (the clamped run) = 15.2,
        # which the vertex push then carries to 17.0 — E's shipped trim.
        self.assertAlmostEqual(plan.crossing_trims(node, p)["arm"], 17.0,
                               places=6)

    def test_degree_two_is_a_corner_and_gets_no_plate(self):
        node = plan.Node("c", (0, 0), [
            self._arm(0, 14.4, "local", 100.0, "a"),
            self._arm(90, 14.4, "local", 100.0, "b"),
        ])
        self.assertEqual(set(plan.crossing_trims(node).values()), {0.0})


class TestClearOfVertex(unittest.TestCase):
    """The closed form against a literal walk of the grid it stands in for.

    `pfsg_clear_of_vertex` is transcribed rather than approximated, so the check
    is a transcription of the VEX loop over an explicit vertex list — the one
    place a closed form could be subtly wrong in a way no case happens to hit.
    """

    @staticmethod
    def _vex(cut, length, at_start, step=4.0, minseg=1.0):
        nseg = max(1, int(math.ceil(length / step - 1e-9)))
        acc = [length * i / nseg for i in range(nseg + 1)]
        n = len(acc)
        s = cut if at_start else length - cut
        for i in range(1, n):
            if acc[i] <= s:
                continue
            if at_start:
                push = acc[i] + minseg
                if acc[i] - s < minseg and push <= length - minseg \
                   and i + 1 < n and acc[i + 1] - push >= minseg:
                    s = push
            else:
                pull = acc[i - 1] - minseg
                if s - acc[i - 1] < minseg and pull >= minseg and i - 2 >= 0 \
                   and pull - acc[i - 2] >= minseg:
                    s = pull
            break
        return s if at_start else length - s

    def test_matches_the_vex_walk_from_both_ends(self):
        p = plan.Params()
        for length in (13.0, 20.0, 32.0, 55.0, 100.5, 188.449, 3.0, 7.9):
            for k in range(0, int(length * 4)):
                cut = k * 0.25
                for at_start in (True, False):
                    got = plan.clear_of_vertex(cut, length, p, at_start)
                    want = self._vex(cut, length, at_start)
                    self.assertAlmostEqual(
                        got, want, places=9,
                        msg="L=%s cut=%s at_start=%s" % (length, cut, at_start))

    def test_it_only_ever_pushes_the_cut_forward(self):
        p = plan.Params()
        for length in (20.0, 55.0, 188.449):
            for k in range(0, int(length * 4)):
                cut = k * 0.25
                self.assertGreaterEqual(plan.clear_of_vertex(cut, length, p),
                                        cut)

    def test_the_resample_rule_the_whole_model_rests_on_holds_on_every_edge(self):
        """⚠️ `clear_of_vertex` is only allowed in the planner at all because the
        vertex grid is a function of arm LENGTH: `s5_resample` cuts each arm into
        `ceil(L / 4)` equal segments. That premise was verified once, by hand,
        and asserted nowhere — while `plan.py` carries a note that the two ways
        of counting it (chord-sum here, input arc length in the SOP) could
        disagree, and **10 of the 304 edges sit exactly on an integer L/4**,
        where one ulp flips `nseg` and shifts the whole grid.

        The fixture already records `npts`, so the premise is free to check.
        """
        data = load()
        checked = on_integer = 0
        for name in sorted(data["cases"]):
            for e in data["cases"][name]["edges"]:
                checked += 1
                q = e["length"] / 4.0
                if abs(q - round(q)) < 1e-9:
                    on_integer += 1
                # plan's OWN function, not a copy of the formula — a copy lets
                # the shipped epsilon be mutated away under a green test
                self.assertEqual(plan.resample_segments(e["length"]),
                                 e["npts"] - 1,
                                 "%s %s L=%r" % (name, e["edge_id"],
                                                 e["length"]))
        self.assertEqual(checked, 304)
        self.assertEqual(on_integer, 10)     # the ones the epsilon protects

    def test_the_dust_epsilon_is_pinned_on_BOTH_sides(self):
        """⚠️ The fixture cannot pin this and the test that claimed to did not.

        `resample_segments` subtracts 1e-9 before `ceil` so a length that is
        arithmetically `4n`, arriving a few ulps over, does not gain a segment
        and shift every vertex. Round 3 deleted the epsilon and all 38 tests
        stayed green: of the 304 edges, the 10 "on an integer L/4" sit at
        exactly 0.0 deviation, where `ceil` needs no help, and **zero** sit in
        the band where it does. So it is pinned here, directly, on both sides —
        dust is absorbed, a real overshoot is not.
        """
        p = plan.Params()
        self.assertEqual(plan.resample_segments(40.0, p), 10)          # exact
        self.assertEqual(plan.resample_segments(40.0 + 1e-12, p), 10)  # dust
        # ...and at the DOCUMENTED edge of the band, not three decades inside
        # it: pinned only at 1e-12, shrinking the epsilon to 1e-12 survived
        self.assertEqual(plan.resample_segments(40.0 + 1e-9, p), 10)
        self.assertEqual(plan.resample_segments(40.0 + 1e-6, p), 11)   # real

    def test_a_degenerate_arm_clamps_instead_of_dividing_by_zero(self):
        """`graph_prune_min_edge_len` (13 m) means no such arm reaches the solve
        today, so this is invisible to the fixture — and it is the difference
        between a clamp and a ZeroDivisionError the day one does. Round 3 found
        the first version tested neither: `clear_of_vertex` short-circuits on
        `length <= 0` before `resample_segments` is ever called, so the guards
        have to be exercised on the function that owns them."""
        p = plan.Params()
        self.assertEqual(plan.resample_segments(1e-12, p), 1)   # max(1, ...)
        self.assertEqual(plan.resample_segments(-5.0, p), 1)
        self.assertEqual(plan.resample_segments(
            40.0, plan.Params(resample_step=0.0)), 1)           # step guard
        self.assertAlmostEqual(plan.clear_of_vertex(1.0, 2.0, p), 1.0)

    def test_the_end_branch_is_reachable_through_crossing_trims(self):
        """`clear_of_vertex`'s two branches differ, and `crossing_trims` picks
        between them off `arm.at_start`. Forcing that argument to True survived
        mutation: the function was well covered, the wiring into it was not."""
        # A 24.36 m local meeting a 26.8 m arterial at a right angle cuts at
        # 13.4 + 4.0 = 17.4 m, and 24.36 resamples into 7 segments of 3.48 — so
        # the cut lands EXACTLY on vertex 5, the one place the two branches
        # disagree. Same node, same geometry, only the end differs.
        def trim(at_start):
            arms = [plan.Arm("m", (0, 1), 14.4, "local", 24.36, at_start),
                    plan.Arm("e", (1, 0), 26.8, "arterial", 400.0, True),
                    plan.Arm("w", (-1, 0), 26.8, "arterial", 400.0, False)]
            return plan.crossing_trims(plan.Node("n", (0, 0), arms))["m"]

        self.assertAlmostEqual(trim(True), 17.4, places=6)
        self.assertAlmostEqual(trim(False), 18.4, places=6)

    def test_a_grid_too_fine_to_push_into_is_left_alone(self):
        """The VEX declines when the push would land closer to the next vertex
        than it started from the last: an audit brute-forced 1778 pushes and
        found 780 leaving under a metre."""
        p = plan.Params(min_end_segment=2.5)      # 2 x minseg > the 4 m step
        self.assertAlmostEqual(plan.clear_of_vertex(3.9, 40.0, p), 3.9)


class TestPrincipal(unittest.TestCase):

    def _arms(self, spec):
        out = []
        for eid, w, L in spec:
            out.append(plan.Arm(eid, (1.0, 0.0), w, "local", L))
        return out

    def test_the_class_radius_table_is_the_builders(self):
        """`pfsj_corner_radius`, mirrored. Both the table and its fallback were
        free to be anything: no case in the suite carries a `highway` or an
        `alley`, and nothing exercised the unknown-class default at all."""
        self.assertEqual(
            [plan.corner_radius(c) for c in
             ("highway", "arterial", "collector", "local", "alley")],
            [25.0, 9.0, 6.0, 4.0, 2.0])
        # an unrecognised class must fall back to `local`, not to the widest
        self.assertEqual(plan.corner_radius("monorail_plinth"), 4.0)
        self.assertEqual(plan.corner_radius(""), 4.0)

    def test_a_degree_two_node_still_has_a_through_pair(self):
        """Two arms ARE the principal pair — a corner is a street running
        through, whatever `crossing_trims` does about plates there. One arm
        cannot be a pair and must return nothing rather than half of one."""
        two = plan.Node("n", (0, 0), self._arms([("a", 14.4, 100.0),
                                                 ("b", 26.8, 50.0)]))
        self.assertEqual(plan.default_principal(two), ("b", "a"))
        one = plan.Node("n", (0, 0), self._arms([("a", 14.4, 100.0)]))
        self.assertEqual(plan.default_principal(one), ())

    def test_widest_wins(self):
        node = plan.Node("n", (0, 0), self._arms(
            [("a", 14.4, 100.0), ("b", 26.8, 50.0), ("c", 15.1, 200.0)]))
        self.assertEqual(plan.default_principal(node)[0], "b")

    def test_RANK_TOL_M_is_pinned_from_BOTH_sides(self):
        """⚠️ The tolerance introduced to fix a tie-break defect was itself free
        to be anything: round 2 of the audit mutated it to 1e-9, 0.01 and 1.0
        and the suite stayed green, because the only test using it compared two
        arms 1.3e-12 m apart — which any tolerance above ~1e-9 calls a tie.

        1 mm is the noise floor `graph_reaches_a_fixed_point` works to, so the
        rule is: under a millimetre is a tie, over it is a difference. Both
        halves asserted, which is what `COLLINEAR_SIN` got and this did not.
        """
        # 0.4 mm apart — a tie, so the longer-arm step cannot see it and the
        # lexicographic edge_id decides
        node = plan.Node("n", (0, 0), self._arms(
            [("z", 14.4, 100.0004), ("a", 14.4, 100.0), ("long", 14.4, 200.0)]))
        self.assertEqual(plan.default_principal(node), ("long", "a"))
        # 2 mm apart — a real difference, so length decides and z wins
        node = plan.Node("n", (0, 0), self._arms(
            [("z", 14.4, 100.002), ("a", 14.4, 100.0), ("long", 14.4, 200.0)]))
        self.assertEqual(plan.default_principal(node), ("long", "z"))

    def test_a_tie_inside_the_noise_floor_falls_through_to_the_edge_id(self):
        """K's third corner: two identical triangle sides whose lengths differ
        by 1.3e-12 m. Without quantisation that difference decided which street
        survived."""
        node = plan.Node("n", (0, 0), self._arms(
            [("z_side", 14.400002479553223, 32.24903099319551),
             ("a_side", 14.400002479553223, 32.24903099319423),
             ("long", 14.400007247924805, 55.0)]))
        self.assertEqual(plan.default_principal(node), ("long", "a_side"))

    def test_authored_beats_computed(self):
        node = plan.Node("n", (0, 0), self._arms(
            [("a", 14.4, 100.0), ("b", 26.8, 50.0), ("c", 15.1, 200.0)]),
            principal_edges=("a", "c"))
        self.assertEqual(plan.principal_of(node), ("a", "c"))

    def test_a_half_authored_pair_falls_back_rather_than_shipping_one_arm(self):
        node = plan.Node("n", (0, 0), self._arms(
            [("a", 14.4, 100.0), ("b", 26.8, 50.0), ("c", 15.1, 200.0)]),
            principal_edges=("a", ""))
        self.assertEqual(plan.principal_of(node), ("b", "c"))


class TestJunctionType(unittest.TestCase):

    def test_the_principal_pair_pays_nothing_and_the_minors_are_unchanged(self):
        a = math.radians
        arms = [plan.Arm("east", (1, 0), 26.8, "arterial", 200.0),
                plan.Arm("west", (-1, 0), 26.8, "arterial", 200.0),
                plan.Arm("north", (math.cos(a(90)), math.sin(a(90))), 14.4,
                         "local", 100.0)]
        node = plan.Node("j", (0, 0), arms)
        crossing = plan.crossing_trims(node)
        junction = plan.junction_trims(node, ("east", "west"))
        self.assertEqual(junction["east"], 0.0)
        self.assertEqual(junction["west"], 0.0)
        self.assertAlmostEqual(junction["north"], crossing["north"], places=9)

    def test_where_this_model_and_11_5s_PLATE_disagree(self):
        """⚠️ NOT A PROPERTY — A PINNED DISAGREEMENT, so M4 cannot ship past it.

        `junction_trims` is `crossing_trims` with the principal zeroed. That is
        exact for the model and it is NOT the same claim as "this is §11.5's
        plate". The M1 audit named three gaps; two of them are numbers, and both
        are recorded here so the builder either matches them or the divergence
        is a deliberate decision rather than a surprise.
        """
        a = plan.Params(min_end_segment=0.0)

        def arm(bd, w, cls, L, eid):
            r = math.radians(bd)
            return plan.Arm(eid, (math.cos(r), math.sin(r)), w, cls, L)

        # (1) TWO ADJACENT MINORS. This model charges their mutual kerb corner;
        # a rectangle-on-the-principal plate has no such corner in it.
        both = plan.Node("j", (0, 0), [
            arm(0, 26.8, "arterial", 400.0, "pe"),
            arm(180, 26.8, "arterial", 400.0, "pw"),
            arm(70, 14.4, "local", 400.0, "m1"),
            arm(110, 14.4, "local", 400.0, "m2")])
        alone = plan.Node("j", (0, 0), [
            arm(0, 26.8, "arterial", 400.0, "pe"),
            arm(180, 26.8, "arterial", 400.0, "pw"),
            arm(70, 14.4, "local", 400.0, "m1")])
        with_neighbour = plan.junction_trims(both, ("pe", "pw"), a)["m1"]
        flank_only = plan.junction_trims(alone, ("pe", "pw"), a)["m1"]
        self.assertAlmostEqual(with_neighbour, 30.7717, places=4)
        self.assertAlmostEqual(flank_only, 22.5932, places=4)
        # the model is the conservative one here — it over-charges the minor
        self.assertGreater(with_neighbour, flank_only)

        # (2) max_fillet_fraction caps on the principal ARM's length. As ONE
        # continuous street the cap would be the through-length, and the model
        # then UNDER-charges the minor — the unsafe direction.
        p4 = plan.Params(corner_radius_scale=4.0, min_end_segment=0.0)
        short = plan.Node("j", (0, 0), [
            arm(0, 26.8, "arterial", 30.0, "pe"),
            arm(180, 26.8, "arterial", 30.0, "pw"),
            arm(90, 14.4, "local", 300.0, "minor")])
        through = plan.Node("j", (0, 0), [
            arm(0, 26.8, "arterial", 60.0, "pe"),
            arm(180, 26.8, "arterial", 60.0, "pw"),
            arm(90, 14.4, "local", 300.0, "minor")])
        self.assertAlmostEqual(
            plan.junction_trims(short, ("pe", "pw"), p4)["minor"], 25.4,
            places=4)
        self.assertAlmostEqual(
            plan.junction_trims(through, ("pe", "pw"), p4)["minor"], 29.4,
            places=4)

    def test_an_authored_principal_naming_a_stranger_is_silently_IGNORED(self):
        """⚠️ PINS TODAY'S BEHAVIOUR, WHICH IS PROBABLY NOT THE RIGHT ONE.

        `principal_edges` is an artist attribute (§11.1 rule 4), so a typo — or
        an edge_id that stopped being incident after a repair pass — is the live
        failure, not a hypothetical. Today `junction_trims` skips the name it
        cannot find and the arm silently keeps a full crossing trim, with
        nothing said. Whether that should warn, raise, or fall back to the
        computed default is an M4 builder-contract decision (11.12); until then
        the behaviour is at least asserted rather than accidental.
        """
        node = plan.Node("j", (0, 0), [
            plan.Arm("east", (1, 0), 26.8, "arterial", 200.0),
            plan.Arm("west", (-1, 0), 26.8, "arterial", 200.0),
            plan.Arm("north", (0, 1), 14.4, "local", 100.0)])
        crossing = plan.crossing_trims(node)
        got = plan.junction_trims(node, ("east", "not_an_arm_here"))
        # ⚠️ THE KEYSET, which is the half this test was named for and did not
        # check: without `junction_trims`' `if edge_id in trims` guard the
        # stranger is INVENTED into the result at 0.0 m. No consumer today
        # iterates the dict by key — `graph_trims` reads it by arm — so it is
        # invisible until M3's adapter, which is exactly what will iterate it.
        self.assertEqual(set(got), {"east", "west", "north"})
        self.assertEqual(got["east"], 0.0)
        self.assertAlmostEqual(got["west"], crossing["west"], places=9)
        self.assertAlmostEqual(got["north"], crossing["north"], places=9)

    def test_an_unbuilt_type_raises_rather_than_silently_becoming_a_crossing(self):
        node = plan.Node("r", (0, 0), [
            plan.Arm("a", (1, 0), 14.4, "local", 100.0),
            plan.Arm("b", (-1, 0), 14.4, "local", 100.0),
            plan.Arm("c", (0, 1), 14.4, "local", 100.0)],
            junction_type="roundabout")
        with self.assertRaises(ValueError):
            plan.node_trims(node)


if __name__ == "__main__":
    unittest.main(verbosity=2)
