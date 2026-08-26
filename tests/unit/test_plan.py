"""The S5 planner, calibrated against the builder's own plates. No Houdini.

    python tests/unit/test_plan.py

⚠️ **CALIBRATE, DO NOT INVENT** (§11.4). `plan.crossing_trims` predicts what
`s5j_solve` cuts off each arm, as a function of arms, widths, classes and
angles, so `standing` is checkable before any geometry exists. The measured
plates it is checked against live in `trim_calibration.json`, written by
`hython tests/citygen/dump_trims.py` on all sixteen cases — 551 arms.

⚠️ **THE FIXTURE WENT STALE ONCE AND HID A MILESTONE.** It was not
regenerated after M5.3's mover, so it recorded M and O with THREE edges -
the pre-mover topology where the shallow leg was DELETED - while the build
shipped five. 49 tests stayed green against a shape the builder had stopped
producing. **Regenerate this fixture in the same commit as any builder
change that moves a trim**; the scene baseline being current is not
evidence that this one is.

MUTATION-TESTED across four audit rounds (10, then 16, then 1 real survivor).
The tables, the tolerances and the dust epsilon are all two-sided-pinned.
(The `_straightest` measurement rule and its pins were deleted 2026-08-17 with
the junction build path they measured — §11.4 keeps the numbers.) What
survives is recorded below so the next round does not re-derive it — ⚠️ **and
a short list is worse than none, so add to it rather than trusting it blind**
(round 4 found this list three entries short).

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
  * A SELF-LOOP — ⚠️ **STILL OPEN, and it is a PLANNER defect rather than an
    adapter one.** `crossing_trims` returns a dict keyed by `edge_id`, so a
    loop's TWO arms collapse to ONE key (the second write wins) and an arm's
    cut is silently lost; and the adapter's `_arms` takes only `pts[1]` or
    `pts[-2]`, yielding one arm where two exist. **`edge_id` is not a valid
    arm key.** Zero closed prims on all 16 cases and `graph_mark_orphans`
    deletes any component with no point of degree >= 3 — but `closeloop`
    exists in the trace wrangle, so a closed street is a real object here.
    The boolean rework guards the PRINCIPAL symptom three ways
    (`default_principal` skips to a distinct street, `principal_of` falls back
    on an authored same-id pair, `junction_schema` reds two claims from one
    prim); M4 closed WITHOUT fixing the cause — it stands, unowned. (M4's
    `junction_trims`, which had the same keyset defect and a stranger-ignoring
    guard pinned here, was deleted with the 2026-08-17 render ruling — the
    build path it modelled no longer exists.)
  * ~~`plan.py` has no consumer~~ — **PAID by M3.** `graph_plan`, a Python SOP
    after `repair_scratch` in the segmenter, is the adapter: geometry -> plain
    data -> `plan.default_junction_type` -> `junction_type` written back on
    `is_node` points. ⚠️ **It re-established the first two guarantees above and
    NOT the self-loop** — `at_start` from `pts[0].number()` and the `n < 1e-9`
    filter are carried over verbatim; the loop is not. Do not read "paid" as
    "all three handed over".

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
    "N_shallow_y_32":  0.001,   # M2, measured 0.000000
    # ⚠️ M AND O ARE NO LONGER EXACT, and this is the first time a
    # STRAIGHT-armed case has not been. Both carry a merge landing (M5.3),
    # and `crossing_trims` solves it in the NODE frame - O's shallow pair
    # reads 13.55° there against 22.00° at the cut where `s5j_solve`
    # re-solves it. Same frame-refinement gap the curved cases always had;
    # it has simply arrived on a straight one. Two-sided-pinned like them.
    "M_shallow_y_24":  15.97,   # M5.3 merge landing, measured 15.9618
    "O_shallow_y_host_dies": 8.08,    # M5.4, measured 8.0704 (was 26.28
                                #  before the clamp came out - the honest
                                #  corner agrees with the planner 3x better)
    "P_stub_chain":    0.001,   # M2, measured 0.000000
    "Q_junction_ring": 0.001,   # M4 case; crossing build since the 2026-08-17
                                # revert, measured 0.000079
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
    "M_shallow_y_24": 2, "N_shallow_y_32": 0, "O_shallow_y_host_dies": 3,
    "P_stub_chain": 0, "Q_junction_ring": 0,
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
    "N_shallow_y_32": (0.001, -0.001),
    # ⚠️ Both merge landings are PESSIMISTIC ONLY - the optimistic tail is
    # exactly 0.0000. The planner under-claims how much street stands at a
    # merge, never over-claims, which is the safe direction and the only
    # one this table exists to police.
    "M_shallow_y_24": (0.001, -15.97),
    "O_shallow_y_host_dies": (0.001, -8.08),
    "P_stub_chain": (0.001, -0.001),
    "Q_junction_ring": (0.001, -0.001),
}

# ⚠️ M and O LEFT this list with M5.4: they are straight-armed and still
# not reproduced exactly, because a merge landing is a node whose frame
# refines between the planner and the builder. Membership is derived from
# the data by a test below, so this list cannot quietly drift from it.
STRAIGHT_CASES = ("E_short_t", "F_bend", "G_tongue", "J_five_star",
                  "K_stub_triangle", "N_shallow_y_32", "P_stub_chain",
                  "Q_junction_ring")


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
                         a["length"], a["at_start"],
                         principal=a.get("principal", 0) != 0)
                for a in nd["arms"]]
        nodes.append(plan.Node("(%.3f,%.3f)" % tuple(nd["pos"]), nd["pos"],
                               arms,
                               junction_type=nd.get("junction_type", "")))
    return nodes, params


def residuals(case):
    """[(predicted - measured, node, edge_id)] over every arm of every node."""
    nodes, params = case_nodes(case)
    out = []
    for node, nd in zip(nodes, case["nodes"]):
        # Dispatch via node_trims, the same door every planner consumer walks
        # through. Since the 2026-08-17 ruling every vocabulary type is the
        # crossing solve, so the dispatch is invariance rather than branching —
        # and the calibration would catch the day that stops being true.
        pred = plan.node_trims(node, params)
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
                # reads `> -0.019` and passes for anything, so the nine exact
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

        Measured over all 326 edges of the suite: zero false-OK (planner says
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
        self.assertEqual(edges, 326)
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
        # ⚠️ TWO CLASSES SINCE M5.4, and collapsing them would have
        # tripled a published number. The curved arms are still bounded by
        # `CURVED_ARM_RESIDUAL_M`; the merge landings are their own thing -
        # STRAIGHT arms that the planner still mis-reads, because the node
        # frame and the cut frame disagree about the shallow pair's angle.
        merges = ("M_shallow_y_24", "O_shallow_y_host_dies")
        curved = 0.0
        for name in sorted(self.data["cases"]):
            if name in merges:
                continue
            curved = max(curved, max(abs(r[0])
                                     for r in residuals(self.data["cases"][name])))
        self.assertLessEqual(curved, plan.CURVED_ARM_RESIDUAL_M)
        self.assertGreater(curved, plan.CURVED_ARM_RESIDUAL_M - 0.01)
        self.assertLessEqual(worst, plan.MERGE_LANDING_RESIDUAL_M)
        self.assertGreater(worst, plan.MERGE_LANDING_RESIDUAL_M - 0.01)
        # ...and the merge landing really is the worse of the two, which is
        # the fact the two constants exist to keep visible
        self.assertGreater(worst, curved)

    def test_graph_trims_lands_each_cut_on_the_right_END_of_the_right_street(self):
        """The assembly, not the corner — a different code path with its own way
        to be wrong.

        `crossing_trims` is per node and says nothing about which of a street's
        two ends a cut belongs to, or what happens to a street carrying a
        junction at both. Swapping `trim_start` for `trim_end` leaves every
        per-arm comparison above green and makes every `standing` on a
        two-junction street garbage. Asserted against the builder's own
        `trim_start` / `trim_end` on all 551 arms — and every street the builder
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
        self.assertEqual(seen, 326, "the planner did not see every street")


class TestKVerdict(unittest.TestCase):
    """K's stub triangle, on its own measured numbers — and the type ruling.

    K's three 32 m sides are trimmed from BOTH ends by two crossing plates and
    end up with negative standing — the plates physically overlap. §11.4's M1
    experiment asked whether a `junction` type that leaves a principal pair
    uncut removes the need to move any node; the answer (NO under the computed
    widest default, YES under a straightest rule only by tie-break luck) is
    recorded with its numbers in §11.4/§11.9. On 2026-08-17 the artist ruled
    the uncut-principal render a BUG — every type builds the crossing solve —
    so the experiment's code went with the build path it measured, and what
    this class now pins is (a) the planner reproducing the gate's own numbers
    without cooking, and (b) the ruling itself: no type, no flag, moves a trim.
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
        """`principals` maps node_id -> the pair to author, realised as the
        per-arm booleans the 2026-08-16 schema actually ships — the flag an
        edge carries about itself, not a node-side list."""
        for node in self.nodes:
            node.junction_type = kind
            want = () if principals is None else principals[node.node_id]
            for arm in node.arms:
                arm.principal = arm.edge_id in want
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

    def test_no_vocabulary_type_moves_a_trim_since_the_ruling(self):
        """⚠️ THE 2026-08-17 RULING, pinned on K's own measured nodes: an uncut
        principal blocks turning traffic, so EVERY vocabulary type builds the
        crossing's carriageway solve and `junction_type` moves no geometry —
        it is markings-and-identity data. Authoring the widest pair onto the
        flags (exactly what the retired computed-default flip would have
        written) must change nothing either, so the flags are authored for
        every type here, not just `junction`.

        This is also the K-verdict's tombstone. The M1 experiment measured
        that the junction type could NOT dissolve K under the computed default
        (one side of three rescued, min standing still -13.434) and could
        under a straightest-pair rule only by tie-break luck — recorded with
        its numbers in §11.4/§11.9, code deleted with the build path it
        measured. K's rescue belongs to the resolution ladder (M5's merge,
        M6's spread), not to a node type.
        """
        base = self._standing("crossing")
        principals = dict((n.node_id, plan.default_principal(n))
                          for n in self.nodes)
        for kind in plan.JUNCTION_TYPE_VOCAB:
            st = self._standing(kind, principals)
            self.assertEqual(st, base, kind)
        self.assertAlmostEqual(min(base.values()), -13.434, places=3)


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
        number, so a wrong one passed. **Zero of the suite's 545 corners take
        this branch** — all 55 collinear corners are the angle≈pi side — so this
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
        disagree, and **24 of the 326 edges sit exactly on an integer L/4**,
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
        self.assertEqual(checked, 326)
        self.assertEqual(on_integer, 24)     # the ones the epsilon protects

    def test_the_dust_epsilon_is_pinned_on_BOTH_sides(self):
        """⚠️ The fixture cannot pin this and the test that claimed to did not.

        `resample_segments` subtracts 1e-9 before `ceil` so a length that is
        arithmetically `4n`, arriving a few ulps over, does not gain a segment
        and shift every vertex. Round 3 deleted the epsilon and all 38 tests
        stayed green: of the 326 edges, the 24 "on an integer L/4" sit at
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
            [("a", 14.4, 100.0), ("b", 26.8, 50.0), ("c", 15.1, 200.0)]))
        for arm in node.arms:
            arm.principal = arm.edge_id in ("a", "c")
        self.assertEqual(plan.principal_of(node), ("a", "c"))

    def test_a_half_authored_pair_falls_back_rather_than_shipping_one_arm(self):
        """Cardinality is the ONE failure the boolean shape still permits — one
        arm claiming, or three. Both fall back to the computed default rather
        than guessing which claim was meant; `junction_schema` reds the geometry
        so the fallback cannot pass silently."""
        node = plan.Node("n", (0, 0), self._arms(
            [("a", 14.4, 100.0), ("b", 26.8, 50.0), ("c", 15.1, 200.0)]))
        node.arms[0].principal = True                      # one claim
        self.assertEqual(plan.principal_of(node), ("b", "c"))
        for arm in node.arms:                              # three claims
            arm.principal = True
        self.assertEqual(plan.principal_of(node), ("b", "c"))

    def test_a_pair_is_two_STREETS_so_a_self_loop_cannot_be_both_of_them(self):
        """⚠️ THE STATE THE BOOLEAN REWORK'S AUDIT FOUND UNGUARDED. A self-loop
        puts one `edge_id` on two arms, and the naive top-two returned
        ('E_loop', 'E_loop') — a "pair" that is one street twice, which any
        `edge_id`-keyed trim dict (`crossing_trims` today) collapses to ONE
        key, silently dropping an arm (the recorded defect: `edge_id` is not
        a valid arm key). The
        computed default now skips to the best arm of a DIFFERENT street, and a
        node whose arms are all one street has no pair at all.

        Unreachable from today's geometry (0 closed prims on all 15 cases,
        `graph_mark_orphans` deletes loop-only components) — asserted here at
        the planner level because that is where the defect lives; the committed
        scene case arrives with M4, when loops become reachable.
        """
        loop_wide = plan.Arm("E_loop", (1.0, 0.0), 26.8, "arterial", 60.0)
        loop_back = plan.Arm("E_loop", (0.0, 1.0), 26.8, "arterial", 60.0,
                             at_start=False)
        street = plan.Arm("E_street", (-1.0, 0.0), 14.4, "local", 100.0)
        node = plan.Node("n", (0, 0), [loop_wide, loop_back, street])
        self.assertEqual(plan.default_principal(node), ("E_loop", "E_street"))
        # ...and a node that is ONLY the loop has no pair, rather than a fake one
        only_loop = plan.Node("n", (0, 0), [loop_wide, loop_back])
        self.assertEqual(plan.default_principal(only_loop), ())
        # ⚠️ The AUTHORED channel has the same trap and got its guard unasserted
        # — round 2 of the rework audit deleted `principal_of`'s
        # `flagged[0] != flagged[1]` and 45 tests stayed green while an authored
        # self-loop returned ('E_loop', 'E_loop'). Author both loop arms:
        # cardinality is 2 but the street count is 1, so the authored channel
        # must fall through to the computed default, not honour the fake pair.
        loop_wide.principal = True
        loop_back.principal = True
        self.assertEqual(plan.principal_of(node), ("E_loop", "E_street"))
        self.assertEqual(plan.principal_of(only_loop), ())

    def test_the_authored_pair_returns_in_edge_id_order_not_arm_order(self):
        """First-come-first-served on the DETERMINISTIC list (artist ruling,
        2026-08-16). Arm order is cook order, and three audit rounds measured a
        cook reorder flipping K's outcome — so the authored pair comes back
        sorted by `edge_id` whatever order the arms arrived in."""
        node = plan.Node("n", (0, 0), self._arms(
            [("z_late", 14.4, 100.0), ("a_early", 26.8, 50.0),
             ("m_mid", 15.1, 200.0)]))
        for arm in node.arms:
            arm.principal = arm.edge_id in ("z_late", "a_early")
        self.assertEqual(plan.principal_of(node), ("a_early", "z_late"))

    def test_default_principal_does_not_depend_on_arm_order(self):
        """⚠️ THE DEFECT CLASS THREE M1-AUDIT ROUNDS KEPT FINDING, pinned on
        the SHIPPED rule now that the `_straightest` measurement family is
        deleted with the junction build path: no pair rule may depend on the
        order `pointprims()` hands back its arms — a cook reorder flipped K's
        outcome three separate times. `default_principal` is immune by
        construction (one `sorted()` over a full-key rank), and this is the
        assertion that keeps a refactor from re-introducing the coin-flip.

        Asserted on a symmetric X where every rank ties and only `edge_id`
        can decide, and on K's node-C shape — two sides 1.3e-12 m apart in
        length, inside `RANK_TOL_M`, the exact float-noise tie that used to
        be settled by whoever came first.
        """
        import itertools
        sq = self._arms([("n", 14.4, 100.0), ("e", 14.4, 100.0),
                         ("s", 14.4, 100.0), ("w", 14.4, 100.0)])
        answers = set()
        for perm in itertools.permutations(range(4)):
            answers.add(plan.default_principal(
                plan.Node("x", (0, 0), [sq[i] for i in perm])))
        self.assertEqual(answers, {("e", "n")})
        kc = self._arms([("z_side", 14.400002479553223, 32.24903099319551),
                         ("a_side", 14.400002479553223, 32.24903099319423),
                         ("long", 14.400007247924805, 55.0)])
        answers = set()
        for perm in itertools.permutations(range(3)):
            answers.add(plan.default_principal(
                plan.Node("x", (0, 0), [kc[i] for i in perm])))
        self.assertEqual(answers, {("long", "a_side")})


class TestJunctionType(unittest.TestCase):

    def test_node_trims_is_type_invariant_and_flag_invariant(self):
        """⚠️ THE MIRROR DUTY, post-ruling form. The M4 audit's headline was
        a 12.93 m planner/builder disagreement from fallbacks that differed
        (the cardinality-0 authored junction), and the fix was `node_trims`
        as the builder's shadow, state for state. Since 2026-08-17 the
        builder has ONE state — the crossing solve, every type, every claim
        shape (the uncut-principal render was ruled a bug and reverted) — so
        the mirror assertion collapses to invariance: every vocabulary type
        crossed with every claim cardinality (0, 1, 2, 3) returns the
        crossing trims EXACTLY, dict-equal. A value outside the vocabulary
        is a programming error and still raises; geometry-side it is
        `junction_schema`'s bad_vocab.

        ⚠️ **`merge` IS IN THIS LOOP AND M5 IS EXPECTED TO BREAK IT.** §11.5's
        merge contract consumes footprint ALONG the principal — a length, a
        real trim — so the milestone that builds it must move this assertion
        and `s5j_solve` in the same commit. That is the point, not an
        oversight: this test is what will FAIL when the merge lands, which is
        the mirror duty the M4 audit priced at 12.93 m. Do not relax it by
        skipping `merge`; change it when the builder changes, with the
        measurement that justifies the new expectation.
        """
        def t_node(jtype, flags):
            arms = [plan.Arm("a", (1, 0), 26.8, "arterial", 200.0,
                             principal="a" in flags),
                    plan.Arm("b", (-1, 0), 26.8, "arterial", 200.0,
                             principal="b" in flags),
                    plan.Arm("c", (0, 1), 14.4, "local", 100.0,
                             principal="c" in flags)]
            return plan.Node("r", (0, 0), arms, junction_type=jtype)

        crossing = plan.crossing_trims(t_node("", ()))
        for jtype in plan.JUNCTION_TYPE_VOCAB:
            for flags in ((), ("a",), ("a", "b"), ("a", "b", "c")):
                got = plan.node_trims(t_node(jtype, flags))
                self.assertEqual(got, crossing,
                                 "jtype=%r flags=%r" % (jtype, flags))
        with self.assertRaises(ValueError):
            plan.node_trims(t_node("roundybout", ()))

    def test_the_vocabulary_tuples_are_pinned_BY_VALUE(self):
        """⚠️ Three tests iterate `JUNCTION_TYPE_VOCAB` and one asserts
        membership in it — all four are VACUOUS under widening, measured by the
        revert's second audit round: adding a member survives every test. It is
        the
        `LOT_REJECT_VOCAB` lesson the checks already cite, aimed at itself — a
        closed set cannot detect being widened by the code that defines it, and
        `checks.py` DERIVES the geometry-side vocabulary from this tuple, so a
        widening moves both sides together and nothing goes red.

        It matters more since the revert than it did before: `node_trims` now
        branches on vocabulary membership and NOTHING else, so this tuple is
        the single gate on what the planner will accept. `RESERVED_JUNCTION_TYPES`
        gets the same treatment — emptying it silently retires
        `junction_schema`'s `unbuilt_type` term, which is the not-silent duty
        for a type the builder has no contract for.

        §11.10 promises the vocabulary is pinned. This is that promise, made
        true.
        """
        self.assertEqual(plan.JUNCTION_TYPE_VOCAB,
                         ("", "crossing", "junction", "merge", "roundabout"))
        self.assertEqual(plan.RESERVED_JUNCTION_TYPES, ("roundabout",))
        # "merge" left the reserved set with M5.3: the mover produces it and
        # the landing builds as the crossing solve. Roundabout stays reserved.
        # ...and the reserved set must be part of the vocabulary, or
        # `junction_schema` reds a state `node_trims` refuses to accept
        for kind in plan.RESERVED_JUNCTION_TYPES:
            self.assertIn(kind, plan.JUNCTION_TYPE_VOCAB)

    def test_the_computed_default_is_crossing_at_every_plated_node(self):
        """⚠️ THE GAP THE REVERT'S AUDIT FOUND: `default_junction_type` had NO
        unit coverage at all, and four mutants of it survived all 38 tests —
        returning `junction` (the retired flip), `""`, `roundabout`, or moving
        the degree gate to 4. The gate catches each one (`bad_principal`
        typed-no-claims, `untyped_junction`, `unbuilt_type`,
        `typed_non_junction`), so this was a coverage gap rather than a live
        defect — but the function's docstring now carries the strongest claim
        in the post-ruling planner, that `crossing` everywhere is the END
        STATE and not a staging step, and a claim nothing asserts is a comment.

        DEGREE is the discriminator: `""` means "decide for me" AND "nothing
        to decide" (§11.3), and only the arm count tells them apart — which is
        why `junction_schema` pairs type with degree rather than just checking
        the vocabulary.
        """
        def node(narms):
            arms = [plan.Arm("e%d" % i, (math.cos(i), math.sin(i)), 14.4,
                             "local", 100.0) for i in range(narms)]
            return plan.Node("d", (0, 0), arms)

        for narms in (3, 4, 5):
            self.assertEqual(plan.default_junction_type(node(narms)),
                             "crossing", narms)
        for narms in (0, 1, 2):
            self.assertEqual(plan.default_junction_type(node(narms)), "",
                             narms)
        # ...and whatever it returns must be sayable in the schema
        self.assertIn(plan.default_junction_type(node(3)),
                      plan.JUNCTION_TYPE_VOCAB)


class TestMerge(unittest.TestCase):
    """M5.1 — the merge's planner model, before any geometry exists.

    The M1 pattern, applied to the one type whose contract consumes carriageway:
    decide on the ABSTRACT graph whether a merge is even possible on the cases
    that need it, so the build is not the thing that finds out.
    """

    COLLECTOR = 15.10               # the shallow-Y rig's leg, as classified
    ARTERIAL = 26.8

    def test_min_turn_radius_is_S3bs_expression_not_the_corner_radius(self):
        """⚠️ TWO RADII, UNRELATED, AND MIXING THEM IS SILENT. `corner_radius`
        is the KERB fillet at a crossing (4-25 m by class); `min_turn_radius` is
        the CENTRELINE bend floor, `0.5 * width * turn_radius_scale`, which is
        what `centreline_curvature_within_class` measures against. On an
        arterial they are 9.0 and 26.8 - a factor of three - so a merge sized
        with the wrong one is feasible when it is not.
        """
        self.assertAlmostEqual(plan.min_turn_radius(self.ARTERIAL), 26.8, places=9)
        self.assertAlmostEqual(plan.min_turn_radius(self.COLLECTOR), 15.10, places=9)
        self.assertNotAlmostEqual(plan.min_turn_radius(self.ARTERIAL),
                                  plan.corner_radius("arterial"), places=1)
        # the scale is a parm, so it must actually be read
        self.assertAlmostEqual(
            plan.min_turn_radius(self.ARTERIAL, turn_radius_scale=1.0), 13.4,
            places=9)

    def test_the_swing_reproduces_11_5s_own_worked_number(self):
        """§11.5 quotes "~11.7 m of swing for an arterial at 25 deg" as the
        evidence that a merge costs real length. That sentence is the only
        number the spec gives for this mechanism, so it is the calibration."""
        self.assertAlmostEqual(
            plan.merge_swing_length(self.ARTERIAL, math.radians(25.0)),
            11.694, places=3)

    def test_the_landing_is_the_fillet_tangent_point_not_the_node(self):
        """⚠️ §11.6's "tangency at the landing" FORCES the landing off the node,
        and this is the geometry M5.3's builder rests on.

        A circle tangent to the principal AT the node has its centre on the
        normal there, so its distance to the minor's line is `R*cos(theta)` -
        equal to `R` only at `theta = 0`. No arc can be tangent to the
        principal at the node and leave the minor tangentially. What exists is
        the arc inscribed in the corner between the minor's ray and the
        principal's CONTINUING direction, tangent points `T = R*tan(theta/2)`
        either side of the node.

        Asserted as a PROPERTY rather than a table: the circle of radius R
        centred on the bisector must be exactly `R` from both lines.
        """
        for w, deg in ((self.ARTERIAL, 25.0), (self.COLLECTOR, 24.0),
                       (self.ARTERIAL, 90.0)):
            th = math.radians(deg)
            R = plan.min_turn_radius(w)
            T = plan.merge_tangent_length(w, th)
            # node at the origin, principal continuing along -x, minor ray at
            # +theta. Tangent points: A on the minor, B on the principal.
            ax, az = T * math.cos(th), T * math.sin(th)
            bx, bz = -T, 0.0
            # the centre is where the two normals meet; take it from B
            cx, cz = bx, R
            # distance from the centre to the minor's line through the origin
            # with direction (cos th, sin th)
            cross = abs(cx * math.sin(th) - cz * math.cos(th))
            self.assertAlmostEqual(cross, R, places=9, msg="%s %s" % (w, deg))
            self.assertAlmostEqual(abs(cz), R, places=9)      # ...and from the principal
            # the tangent point A really is on that circle
            self.assertAlmostEqual(math.hypot(ax - cx, az - cz), R, places=9)
            # the identity that made the WRONG scalar look plausible
            self.assertAlmostEqual(T * (1.0 + math.cos(th)), R * math.sin(th),
                                   places=9)

    def test_the_principal_pays_a_PER_ARM_length_not_a_straddling_span(self):
        """⚠️ THE QUANTITY THAT WAS WRONG UNTIL AN AUDIT CAUGHT IT, pinned so
        it cannot come back. `merge_consumed_along_principal` returned
        `R*sin(theta) + run` - the span between the fillet's two tangent points
        measured along the principal, which STRADDLES the node. `standing`
        charges per END and `crossing_trims` returns a per-ARM dict, so that
        number written into one arm over-charges it by 54% at 25 deg on an
        arterial and under-charges the other arm by all of it.

        The construction only ever reaches the DOWNSTREAM arm: `T + run`.
        """
        th = math.radians(25.0)
        T = plan.merge_tangent_length(self.ARTERIAL, th)
        self.assertAlmostEqual(T, 5.9414, places=4)
        self.assertAlmostEqual(
            plan.merge_consumed_along_principal(self.ARTERIAL, th),
            T + plan.MERGE_PARALLEL_RUN_M, places=9)
        self.assertAlmostEqual(
            plan.merge_consumed_along_principal(self.ARTERIAL, th),
            9.9414, places=4)
        # ...and it is strictly less than the straddling span it replaced
        straddle = plan.min_turn_radius(self.ARTERIAL) * math.sin(th)
        self.assertLess(T, straddle)
        self.assertAlmostEqual(straddle + plan.MERGE_PARALLEL_RUN_M, 15.3262,
                               places=4)
        # at 0 deg there is nothing to swing through: the run alone
        self.assertAlmostEqual(
            plan.merge_consumed_along_principal(self.ARTERIAL, 0.0),
            plan.MERGE_PARALLEL_RUN_M, places=9)

    def test_a_merge_LENGTHENS_the_minor(self):
        """The minor gives up its last `T` of straight and gains `R*theta` of
        arc, so it gets longer by `R*(theta - tan(theta/2))` - 5.75 m on an
        arterial at 25 deg. Worth pinning because every other footprint in this
        module SHORTENS a street, and a consumer that assumes "trim" here would
        have the sign backwards."""
        th = math.radians(25.0)
        gained = (plan.merge_arc_length(self.ARTERIAL, th)
                  - plan.merge_tangent_length(self.ARTERIAL, th))
        self.assertAlmostEqual(gained, 5.7523, places=4)
        self.assertGreater(gained, 0.0)
        # ...and the gate charges the arc, which is more than the construction
        # needs (T), so it is conservative in the safe direction
        self.assertGreater(plan.merge_arc_length(self.COLLECTOR, th),
                           plan.merge_tangent_length(self.COLLECTOR, th))

    def test_THE_M5_VERDICT_the_deleting_cases_can_be_merged_instead(self):
        """⚠️ THE MILESTONE'S GATING QUESTION, answered on the rig's real
        numbers before a line of builder VEX exists.

        `graph_min_angle` deletes a street in pass 0 on M (24 deg) and O
        (22 deg). M5 replaces that deletion with a merge - which is only
        honest if a merge is POSSIBLE there.

        ⚠️ **AND THE TWO CASES DO NOT DELETE THE SAME KIND OF STREET, which
        the first version of this test got wrong by assuming one class for the
        whole family.** The rig varies LENGTH, and length decides both the
        classification and which arm dies:

          * **M** - the leg is 120 m, under `arterial_len` (180) and over
            `collector_len` (70), so it is a **collector at 15.10 m**. It is
            also the shorter of the contested pair, so it is what
            `graph_min_angle` takes. Minor = the leg: needs 10.33 m of 120.
          * **O** - the leg is 300 m, so it is an **arterial at 26.8 m**, and
            it is LONGER than the host's 200 m east arm; `graph_min_angle`
            takes the host's own arterial instead (`cases.py` says so
            outright, and the case ships west+leg fused as one 599.77 m
            arterial). Both contesting arms are arterial, so class and width
            tie and length decides minor-most: the minor is the **200 m east
            arm**, needing 14.29 m - 46% more than the collector reading it
            replaced.

        Feasible either way, with better than eleven times the margin, so the
        deletion is replaceable and the milestone stands. The verdict survived
        the correction; the evidence for it did not.
        """
        for label, minor_len, width, deg, need in (
                ("M leg", 120.0, self.COLLECTOR, 24.0, 10.3251),
                ("O host-east arm", 200.0, self.ARTERIAL, 22.0, 14.2905)):
            th = math.radians(deg)
            self.assertAlmostEqual(
                plan.merge_swing_length(width, th) + plan.MERGE_PARALLEL_RUN_M,
                need, places=4, msg=label)
            self.assertTrue(plan.merge_feasible(minor_len, width, th), label)
            self.assertGreater(minor_len / need, 11.0, label)
        # ⚠️ AND THE MOVER CHANGED WHAT THIS GUARD SHOULD ASSERT. It used to
        # look for O's 599.77 m FUSED arterial - west host + leg welded into
        # one street because `graph_min_angle` had deleted the east arm. M5.3
        # stopped that deletion, so no fused street exists any more and both
        # legs SHIP. The guard now asserts the thing the milestone is for:
        # each leg survives as its own edge, and it is LONGER than drawn
        # because the merge swings it (M 120 -> 123.75, O 300 -> 303.79).
        for case, drawn, cls in (("M_shallow_y_24", 120.0, "collector"),
                                 ("O_shallow_y_host_dies", 300.0, "arterial")):
            legs = [e for e in load()["cases"][case]["edges"]
                    if drawn < e["length"] < drawn + 10.0
                    and e["street_class"] == cls]
            self.assertEqual(len(legs), 1, case)
            self.assertGreater(legs[0]["length"], drawn, case)
        # ...and M's leg, from N's fixture entry, which is the identically
        # drawn 120 m leg. Both halves of the paragraph go stale loudly or
        # neither does.
        m_leg = [e for e in load()["cases"]["N_shallow_y_32"]["edges"]
                 if abs(e["length"] - 120.0) < 0.01]
        self.assertEqual(len(m_leg), 1)
        self.assertEqual(m_leg[0]["street_class"], "collector")
        self.assertAlmostEqual(m_leg[0]["width"], self.COLLECTOR, places=2)

    def test_feasibility_is_a_two_sided_floor(self):
        """A gate asserted only from the passing side certifies itself (the
        RESIDUAL_M lesson). Straddle it by a millimetre."""
        th = math.radians(24.0)
        need = plan.merge_swing_length(self.COLLECTOR, th) + plan.MERGE_PARALLEL_RUN_M
        self.assertTrue(plan.merge_feasible(need + 1e-3, self.COLLECTOR, th))
        self.assertFalse(plan.merge_feasible(need - 1e-3, self.COLLECTOR, th))
        # ⚠️ EXACTLY at the floor is FEASIBLE, and asserting it is the only
        # thing that pins `>=` against `>`. Straddling by a millimetre does
        # not: the audit mutated the comparison and all 47 tests stayed green.
        # "Floor" is a claim about the boundary, so test the boundary.
        self.assertTrue(plan.merge_feasible(need, self.COLLECTOR, th))
        # ⚠️ A NEGATIVE ANGLE IS THE FALSE-OK DIRECTION, and nothing asserted
        # it: dropping `abs()` from `merge_swing_length` survived all 47 tests,
        # because every other test passes a positive angle. An approach angle
        # is naturally computed as a SIGNED bearing difference, and a negative
        # one makes `need` negative - so a zero-length minor reads feasible,
        # which is exactly the direction `plan.py`'s header calls the only
        # dangerous one.
        self.assertGreater(plan.merge_swing_length(self.COLLECTOR, -th), 0.0)
        self.assertEqual(plan.merge_swing_length(self.COLLECTOR, -th),
                         plan.merge_swing_length(self.COLLECTOR, th))
        self.assertFalse(plan.merge_feasible(0.0, self.COLLECTOR, -th))
        self.assertFalse(plan.merge_feasible(need - 1e-3, self.COLLECTOR, -th))
        # the run is part of the floor, not decoration: drop it and a leg that
        # is too short becomes "feasible"
        self.assertTrue(plan.merge_feasible(need - 1e-3, self.COLLECTOR, th,
                                            parallel_run=0.0))

    def test_HOW_CLOSE_THE_GATE_COMES_TO_BITING_measured_not_assumed(self):
        """⚠️ **THE INFEASIBLE PATH IS NEARLY UNREACHABLE IN THIS CORPUS, and
        the first version of this test said so with a number that was wrong.**

        I wrote "the shortest leg any case carries is 100 m" from the shallow-Y
        rig and the assertion failed on 20.0 m — `E_short_t`'s arm, the case
        built precisely to be the shortest thing in the suite. Measured over
        all 322 edges, at the 25 deg angle floor: the tightest margin is
        **1.945x** (`E_short_t`, 20.0 m against a 10.28 m floor), then two at
        1.95x (`C_radial` / `I_offset_radial`, 30.65 m arterials against
        15.69 m). Nothing is infeasible.

        So §11.5's ladder fallback is code no committed case reaches — but it
        is ONE case away, not an order of magnitude away, and the honest form
        of that is a case authored FOR it when the builder lands (M5.3). The
        same 20 m arm becomes infeasible at 65 deg, which is not a merge angle;
        a short arm at a shallow angle is what would do it.
        """
        floor = plan.merge_swing_length(self.COLLECTOR, math.radians(25.0))             + plan.MERGE_PARALLEL_RUN_M
        self.assertAlmostEqual(floor, 10.5886, places=4)
        # the real margin, over every edge, at the angle floor — asserted from
        # the fixture so a new short case moves it instead of hiding behind it
        tightest = min(
            e["length"] / (plan.merge_swing_length(e["width"],
                                                   math.radians(25.0))
                           + plan.MERGE_PARALLEL_RUN_M)
            for c in load()["cases"].values() for e in c["edges"])
        self.assertAlmostEqual(tightest, 1.9449, places=4)
        self.assertGreater(tightest, 1.0)      # nothing is infeasible today
        self.assertLess(tightest, 2.5)         # ...and not by much
        # a 20 m local arm IS refusable, just not at any angle a merge runs at
        self.assertFalse(plan.merge_feasible(20.0, 14.4, math.radians(65.0)))
        self.assertTrue(plan.merge_feasible(20.0, 14.4, math.radians(25.0)))

    def test_the_parallel_run_default_is_a_placeholder_not_a_measurement(self):
        """§11.5 makes the run a new artist parm and gives it no default, so
        this constant is unratified. It is pinned only so that a change to it
        is a visible edit rather than a drift - NOT because 4 m is right.
        One resample step is the shortest run the builder can express."""
        self.assertEqual(plan.MERGE_PARALLEL_RUN_M, 4.0)
        # ⚠️ NOT tied to `resample_step`. The first version asserted the two
        # were equal, which reads as a derivation and is not one: the resample
        # step is the junction HDA's Max Segment Length and the run is an
        # artist parm 11.5 leaves open. They happen to share a number today;
        # coupling them would red a merge test the day the step changes.


if __name__ == "__main__":
    unittest.main(verbosity=2)
