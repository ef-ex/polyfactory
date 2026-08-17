"""CityGen test cases — builds every scene the checks run against.

Scenes are built from scratch in a fresh session and never saved. A live,
mutating .hip was a real source of false findings during the audit rounds:
stale cooks, leftover scratch nodes, display flags changed by one pass and read
by the next, HDA instances left unlocked. Deterministic setup removes all of it.
"""

import os

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OTLS = os.path.join(REPO, "polyfactory", "otls")

HDAS = ("pf_citygen_field_grid.hda", "pf_citygen_field_radial.hda",
        "pf_citygen_junction.hda", "pf_citygen_mesh.hda",
        "pf_citygen_tracer.hda", "pf_citygen_segmenter.hda", "pf_citygen_solver.hda")


def setup_env():
    """hython does not load the polyfactory package, so $POLYFACTORY is unset
    and `#include <pf_streetgraph.vfl>` cannot resolve. Point the VEX include
    search at the repo explicitly before anything cooks."""
    import sys
    import hou
    pkg = os.path.join(REPO, "polyfactory").replace("\\", "/")
    hou.putenv("POLYFACTORY", pkg)
    for var, val in (("HOUDINI_VEX_PATH", "%s/vex/include;&" % pkg),
                     ("HOUDINI_PATH", "%s;&" % pkg)):
        hou.putenv(var, val)
    # Python SOPs do `from polyfactory import citygen`; hython has not loaded
    # the package so scripts/python is not on sys.path either.
    pyp = "%s/scripts/python" % pkg
    if pyp not in sys.path:
        sys.path.insert(0, pyp)


def install_hdas():
    import hou
    setup_env()
    for f in HDAS:
        path = os.path.join(OTLS, f)
        if not os.path.exists(path):
            raise RuntimeError("missing HDA: %s" % path)
        hou.hda.installFile(path)


# --- the hand-drawn street input, as a literal so it never drifts -----------
DRAWN_STREETS = [
    [(-200, 0, 0), (-60, 0, 10), (80, 0, -10), (220, 0, 5)],
    [(-200, 0, 150), (0, 0, 140), (220, 0, 155)],
    [(-120, 0, -120), (-115, 0, 0), (-110, 0, 150), (-108, 0, 260)],
    [(60, 0, -120), (66, 0, 0), (70, 0, 150), (72, 0, 260)],
    [(-200, 0, -120), (220, 0, -110)],
]

# Case E's input: a short perpendicular T, sized from the clamp condition.
# See build_all() for why it exists and how the numbers were chosen.
SHORT_T_STREETS = [
    [(-60, 0, 0), (60, 0, 0)],                   # splits into two 60 m locals
    [(0, 0, 0), (0, 0, 20)],                     # the 20 m arm that binds
]

# Case F's input: a 90 degree bend on an ARTERIAL — S3b at its design amplitude.
# See build_all() for why it exists and how the numbers were chosen.
BEND_STREETS = [
    [(-200, 0, -140), (140, 0, -140), (140, 0, 200)],   # the L, 340 + 340 m
    [(-40, 0, -280), (-40, 0, -140)],                   # a 140 m collector T
]

# Case G's input: THE TONGUE. A four-way of arterials with one short arm on it.
# See build_all() for why it exists and how the numbers were chosen.
TONGUE_STREETS = [
    [(-250, 0, 0), (250, 0, 0)],       # splits at the origin into two arterials
    [(0, 0, 0), (0, 0, 250)],          # a third arterial arm
    [(0, 0, 0), (0, 0, -24)],          # the 24 m local arm the mouth eats
]

# Case J's input: A FIVE-WAY STAR THE REALIGN CAN REPAIR. Five arms on one node
# at bearings 0 / 32 / 100 / 180 / 255 degrees. See build_all() for how every
# number is derived from graph_realign's own feasibility condition.
STAR5_STREETS = [
    [(0, 0, 0), (200.00, 0, 0.00)],        # 0 deg,   200 m  arterial  - the host
    [(0, 0, 0), (101.77, 0, 63.59)],       # 32 deg,  120 m  collector - the minor leg
    [(0, 0, 0), (-19.10, 0, 108.33)],      # 100 deg, 110 m  collector
    [(0, 0, 0), (-200.00, 0, 0.00)],       # 180 deg, 200 m  arterial
    [(0, 0, 0), (-25.88, 0, -96.59)],      # 255 deg, 100 m  collector
]

# Case K's input: THE STUB TRIANGLE THE GATE MUST REFUSE. Three junctions inside
# min_node_dist closing a 3-cycle, and the third corner carries a 55 m arm -
# so the five-way the collapse would make cannot be repaired. See build_all().
STUB_TRIANGLE_STREETS = [
    [(0, 0, 0), (32, 0, 0)],               # A-B, 32.00 m
    [(32, 0, 0), (16, 0, 28)],             # B-C, 32.25 m
    [(16, 0, 28), (0, 0, 0)],              # C-A, 32.25 m
    [(0, 0, 0), (-200.00, 0, 0.00)],       # A, 180.0 deg, 200.00 m arterial
    [(0, 0, 0), (-51.30, 0, -140.95)],     # A, 250.0 deg, 150.00 m collector
    [(32, 0, 0), (143.20, 0, 153.60)],     # B,  54.1 deg, 189.63 m arterial
    [(32, 0, 0), (109.30, 0, -130.20)],    # B, 300.7 deg, 151.42 m collector
    [(16, 0, 28), (16.00, 0, 83.00)],      # C,  90.0 deg,  55.00 m local - SHORT
]

# The SHALLOW-Y FAMILY (M2). A host street running straight through a node with
# one leg arriving at a shallow angle - the configuration §11.5's `merge` type
# exists for, and the one `graph_min_angle` resolves today by DELETING a street.
#
# Sampled either side of `street_params_min_junction_angle` (25 deg): M at 24 is
# under it, N at 32 is over. 32 is not an arbitrary control - it is
# J_five_star's crowded pair and the same order as C_radial's measured 32.5 deg
# site, so the family's upper sample is a configuration the suite already knows
# solves.
#
# ⚠️ **AND M IS ONE BIT FROM A NO-LEG CONTROL TOO — recorded, not acted on.**
# The same experiment that deleted L, run against M: `counts` identical
# (city 3380, edges 3), all 50 checks share the same verdict, and 44 of 50
# VALUES match a scene with no shallow leg drawn at all. M's defence is not
# distinct output, it is BRANCH COVERAGE of the length tie-break - M is the
# leg-dies branch, O is the host-dies branch - and deleting it would leave the
# leg-dies branch uncovered. O is genuinely distinct (9 values differ from M,
# 2730 city prims against 3380). Do not delete M on the L argument without
# replacing the coverage.
#
# ⚠️ **THE LETTER L IS MISSING ON PURPOSE.** There was an `L_shallow_y_15`, and
# an audit deleted it: it was bit-identical to M on all 50 checks and all 848
# leaf baseline values, because below the floor the published graph does not
# depend on the angle at all - the leg is deleted, the Y node falls to degree 2,
# the host re-fuses, and the shallow site leaves NO TRACE. The decisive
# measurement was a control scene with no shallow leg drawn at all, which
# reproduced 44 of L's 50 checks; the whole of L was one bit,
# `graph_min_angle: 1`, and M carries the same bit closer to the floor. A second
# case that is bit-identical to another today does not earn its place on a
# PROMISED FUTURE divergence - add the second sub-floor angle the day M5 gives
# it something to assert.
#
# ⚠️ And the bracket is looser than it looks: the samples locate the threshold
# only to (24, 32]. Swept live, the transition is at (24.998, 25.5]. A case
# authored at exactly 25.0 deg still DELETES, because the leg endpoint below is
# rounded to 2 dp and the resulting measured angle is 24.998 - the family cannot
# resolve the floor finer than its own rounding.
#
# ⚠️ **AND WHAT DECIDES THE VERDICT IS NEITHER ANGLE NOR CLASS, IT IS LENGTH.**
# Measured by audit: `graph_min_angle` reads only `min_junction_angle` and
# `pfsg_primlength`, and it runs at position 16 of the repair chain while
# `graph_classify` is at 22 and `graph_width` at 23 - so in PASS 0 class and
# width do not exist when the verdict is taken, and the tie-break is
# `kill = (lens[i] < lens[j]) ? prims[i] : prims[j]`, i.e. keep the longer. A
# case built to show class does not matter could therefore never have failed.
# The family varies the thing that decides instead: in M/N the leg is the
# shorter arm and the LEG dies; in O the leg is longer and the HOST'S east arm
# dies, which was covered by nothing. ⚠️ And class/width are not merely absent -
# from pass 1 the loop's feedback carries `street_class` and `streetWidth`
# written by the PREVIOUS pass's classify/width. They exist and are simply not
# read. Only in pass 0 are they genuinely absent.
#
# ⚠️ The leg length is bounded from BELOW by `d_extend` (90 m), and that is not
# obvious: at a shallow angle the leg's tip runs alongside the host and ends up
# NEAR THE HOST'S OWN TIP. At 15 deg a 120 m leg off a 2 x 200 m host lands
# 89.7 m from the host's east end - under the floor, so `graph_extend` would
# bridge them and the case would be measuring the extender instead of the angle.
# Measured closest arm-tip pair: 223.6 m on M/N, and 136.9 m on O, whose host is
# asymmetric - both clear of `d_extend` 90.
#
# ⚠️ **AND THE FIRST VERSION OF THIS FAMILY PUBLISHED AN EMPTY GRAPH ON THREE OF
# ITS CASES**, which the suite reported as tidy red rows while
# `counts` read city 0 / edges 0. Measured 2026-08-15, and it is §11.11's own
# warning arriving on schedule. The cause is a CHAIN of two by-design
# mechanisms: `graph_min_angle` removes the shallow leg, which leaves the Y node
# at degree 2 - so the component now contains no junction at all, and
# `graph_drop_orphans` correctly deletes the whole thing. A host with one leg is
# not a city; it is one deletion away from nothing.
#
# So the host carries a SECOND junction, a plain perpendicular T 300 m west,
# whose only job is to keep the component alive when the shallow site loses its
# leg. That is what makes the family measure the angle rather than the orphan
# filter. It also has to be far enough west that nothing interacts: 300 m clears
# `min_node_dist` (40) by an order of magnitude, and the closest pair of arm
# tips in the whole case is 224 m against `d_extend`'s 90.
#
# Host halves stay ARTERIAL either side of both junctions - 200 / 300 / 500 m
# (200 / 300 / 200 for O), all >= `arterial_len` 180 - so the through street's
# class is constant across the family and only the contested LENGTHS change.
def _shallow_y(deg, leg_len, host_east=500.0):
    import math
    a = math.radians(deg)
    return [[(-500, 0, 0), (host_east, 0, 0)],      # the host, split by both
            [(-300, 0, 0), (-300, 0, 100)],         # the anchor T, 100 m
            [(0, 0, 0), (round(leg_len * math.cos(a), 2), 0,
                         round(leg_len * math.sin(a), 2))]]


# Case P's input: THE FOUR-JUNCTION STUB CHAIN. Specified in full by §S5a item 5
# ("fully specified and deliberately not added here") and measured there in an
# isolated session: A(0,0) B(30,0) C(60,0) D(90,0), three 30 m links, six
# external arms hung 2 - 1 - 1 - 2, all of them >= 90 m.
#
# It is the branch-coverage case for the flood fill PAST the 3-cycle: the gate
# reads cluster = 4, narm = 6, so the fill finds every member and terminates.
# K_stub_triangle only ever exercises a 3-cycle, where a wrong fill still
# happens to touch every node.
#
# ⚠️ AND IT IS EXPECTED RED, on a defect the widened tripwire found and nothing
# has fixed: with every arm over the floor the collapse is PERMITTED, and
# `graph_drop_orphans` then removes two components after pass 0 - publishing
# 3 edges of 9. Bit-identical on both gate definitions, so pre-existing, not a
# regression. A red row is the honest form of that (the J/K precedent).
#
# Sized so nothing else can be the cause. Links are 30 m: under
# `graph_params_min_node_dist` (40) so they are jogs, over
# `graph_prune_min_edge_len` (13) so pruning keeps them. Every angle at every
# node is at least 60 deg, well clear of `min_junction_angle` (25), so no leg is
# resolved by deletion. Every pair of arm tips is more than `d_extend` (90 m)
# apart - closest is 100.0 m (A's two arms, and D's two) - so `graph_extend`
# bridges nothing. B's arm is 150 m, which is the row §S5a measured.
STUB_CHAIN_STREETS = [
    [(0, 0, 0), (30, 0, 0)],               # A-B, 30.00 m
    [(30, 0, 0), (60, 0, 0)],              # B-C, 30.00 m
    [(60, 0, 0), (90, 0, 0)],              # C-D, 30.00 m
    [(0, 0, 0), (-86.60, 0, 50.00)],       # A, 150.0 deg, 100.00 m collector
    [(0, 0, 0), (-86.60, 0, -50.00)],      # A, 210.0 deg, 100.00 m collector
    [(30, 0, 0), (30.00, 0, 150.00)],      # B,  90.0 deg, 150.00 m collector
    [(60, 0, 0), (60.00, 0, -100.00)],     # C, 270.0 deg, 100.00 m collector
    [(90, 0, 0), (176.60, 0, 50.00)],      # D,  30.0 deg, 100.00 m collector
    [(90, 0, 0), (176.60, 0, -50.00)],     # D, 330.0 deg, 100.00 m collector
]

# Case Q's input: the S7 junction ring. See build_all()'s Q block for the
# derivation of every number.
JUNCTION_RING_STREETS = [
    [(0, 0, 0), (300, 0, 0)],              # south side - splits at T1 (150,0)
    [(300, 0, 0), (300, 0, 300)],          # east side
    [(300, 0, 300), (0, 0, 300)],          # north side - splits at T2 (150,300)
    [(0, 0, 300), (0, 0, 0)],              # west side
    [(150, 0, 0), (150, 0, -60)],          # minor at T1, outward, 60 m local
    [(150, 0, 300), (150, 0, 360)],        # minor at T2, outward, 60 m local
]

_DRAW_SNIPPET = """
import hou
g = hou.pwd().geometry(); g.clear()
g.addAttrib(hou.attribType.Prim, "layer", 0)
STREETS = %r
for pts in STREETS:
    poly = g.createPolygon(is_closed=False)
    for p in pts:
        poly.addVertex(g.createPoint()).point().setPosition(p)
    poly.setAttribValue("layer", 0)
""" % (DRAWN_STREETS,)


def _chain(parent, name, upstream, drawn):
    """The four-node pipeline: TRACER · SEGMENTER · SOLVER · MESHER.

    Split from the old two-node `trace → mesh` on 2026-08-11. The cut is
    TOPOLOGY versus GEOMETRY, and it works because topology does not need
    widths — where two curves cross is independent of how wide they are.

      * `pf_citygen_tracer`    field sources → raw splines (S1, S2)
      * `pf_citygen_segmenter` splines → final topology + default attributes
        (S3, S3b, S4). Owns the fixed-point repair loop, so nothing after it
        creates or destroys an edge or a node.
      * `pf_citygen_solver`    → out0 the splines, out1 the junction solution (S5)
      * `pf_citygen_mesh`      → city, blocks, lots, graph (S6, S7, S8)

    ⚠️ **A hand-drawn spline is no longer a special input.** It enters the
    SEGMENTER on the same port traced splines use — there is no second port and
    no switch. That was the whole point of the split: one workflow whatever the
    source. Verified bit-identical to the old chain on all four outputs, for
    both the field path and the drawn path, before this was adopted.
    """
    if drawn:
        t = None
        seg_in = upstream
    else:
        t = parent.createNode("pf_citygen_tracer", name + "_tracer")
        t.setInput(0, upstream)
        seg_in = t
    s = parent.createNode("pf_citygen_segmenter", name + "_segmenter")
    s.setInput(0, seg_in, 0 if t is not None else 0)
    v = parent.createNode("pf_citygen_solver", name + "_solver")
    v.setInput(0, s, 0)

    # ⚠️ TWO PARAMETERS EXIST ON MORE THAN ONE NODE AFTER THE SPLIT, and the
    # duplication is real, not a test artefact — §6b records it as needing
    # unification. The SEGMENTER is made the single source of truth here so a
    # case that sets one value cannot silently drive only half the pipeline.
    #
    #   `domain`     the tracer traces over it, the segmenter's turn clamp
    #                measures against it. Setting it on the segmenter alone
    #                left the tracer at its 900 default: B_grid came back with
    #                79 edges instead of 64 and 22 dead ends instead of 17.
    #   `s5j_params_*`  the segmenter's `junction_premeasure` reads them to
    #                decide the tongue drop; the SOLVER's `junction_solve` reads
    #                them to build the actual corners. E_short_t sets
    #                `corner_radius_scale` and would otherwise have steered the
    #                pre-measure while the real solve stayed at default.
    # `domain` used to be promoted on all three nodes and live on only the
    # Tracer — an audit measured Domain set on the Segmenter silently shipping a
    # 25% larger city (26706 prims / 1165 lots against 21363 / 774). It is now
    # removed from the Segmenter and Solver, so there is nothing left to link
    # and the value is set on the Tracer directly, where it is read.
    for q in v.parms():
        if q.name().startswith("s5j_params_") and s.parm(q.name()) is not None:
            q.setExpression('ch("../%s/%s")' % (s.name(), q.name()))
    m = parent.createNode("pf_citygen_mesh", name)
    m.setInput(0, v, 0)
    m.setInput(1, v, 1)
    return s, v, m


def build_all(parent=None):
    """Build every case. Returns {case_name: {role: node}}."""
    import hou
    if parent is None:
        parent = hou.node("/obj").createNode("geo", "citygen_tests")
        for c in parent.children():
            c.destroy()
    cases = {}

    # A — artist draws streets, gets roads, junctions, blocks and lots
    draw = parent.createNode("python", "A_drawn_streets")
    draw.parm("python").set(_DRAW_SNIPPET)
    at, at_solver, a = _chain(parent, "A_city", draw, True)
    cases["A_drawn"] = {"city": a, "trace": at, "solver": at_solver, "input": draw}

    # B — straight/grid tensor field
    bf = parent.createNode("pf_citygen_field_grid", "B_field_grid")
    bf.parm("angle").set(18.0)
    bf.parm("weight").set(1.0)
    bf.parm("falloff").set(3000.0)
    bt, bt_solver, b = _chain(parent, "B_city", bf, False)
    parent.node("B_city_tracer").parm("domain").set(800.0)
    cases["B_grid"] = {"city": b, "trace": bt, "solver": bt_solver, "input": bf, "field": bf}

    # C — radial tensor field
    cf = parent.createNode("pf_citygen_field_radial", "C_field_radial")
    cf.parm("weight").set(2.5)
    cf.parm("falloff").set(2000.0)
    ct, ct_solver, c = _chain(parent, "C_city", cf, False)
    parent.node("C_city_tracer").parm("domain").set(800.0)
    cases["C_radial"] = {"city": c, "trace": ct, "solver": ct_solver, "input": cf, "field": cf}

    # D — the OFFSET lot mode (European perimeter block). A fourth case rather
    # than a parameter sweep over A/B/C: the mode only changes S8, so running
    # all three twice would re-run every street, junction and block check for no
    # new information and roughly double the suite. One case is enough to
    # exercise the branch, and it is pinned to the cheapest input (A's two
    # blocks) so the cost is a rounding error.
    #
    # It exists because 4e-6 found `offset` had NEVER been executed by the
    # suite. It failed a committed check — lots_tile_blocks — the first time
    # anyone ran it, and the person who ran it was the auditor, not the author.
    # Adding a mode means adding a case.
    dt, dt_solver, d = _chain(parent, "D_city", draw, True)
    d.parm("lots_params_subdiv_mode").set(1)          # 0 recursive_obb, 1 offset
    cases["D_offset"] = {"city": d, "trace": dt, "solver": dt_solver, "input": draw}

    # H — `offset` mode with the shape rungs BITING.
    #
    # ⚠️ The reason this case earns its place is NOT the one it was added for.
    # It was added because D_offset rejects 0 parcels and so caught 0 of 5 rung
    # drops — true, but an audit then ran a 19-break x 5-case matrix and found
    # H catches only ONE rung drop, and A, B and C already catch it. C_radial
    # alone catches all five. H's marginal coverage on rung drops is zero.
    #
    # What H catches that NOTHING else does: a revert of the courtyard rung-skip
    # in `lots_viability`. Undo that fix and H goes red (label_wrong 1, prim 60)
    # while A, B, C *and D* stay green. It is the only case in the suite that
    # notices the European exemption regressing, which is precisely the thing
    # that shipped as a no-op once already.
    #
    # `max_aspect` = 1.9, not 1.8. At 1.8 the ring rejection this case exists to
    # produce sits 0.006 over the line against `agree_tol` 0.05 — so the ONE
    # verdict the case was added for is the one verdict `_expected_reject`
    # declines to assert, and it drags two more parcels into the band. 1.8 is
    # also inside the documented argmin instability (3.1e-2), so `rejected`
    # could flip 2<->1 on float noise and move the baseline with no defect. At
    # 1.9: zero parcels unassertable, the courtyard rejection kept, the revert
    # detection kept.
    ht, ht_solver, h = _chain(parent, "H_city", draw, True)
    h.parm("lots_params_subdiv_mode").set(1)
    h.parm("lots_params_max_aspect").set(1.9)
    cases["H_offset_strict"] = {"city": h, "trace": ht, "solver": ht_solver, "input": draw}

    # I — `offset` mode on a block shape that is NOT A's.
    #
    # ⚠️ THIS CASE IS EXPECTED TO FAIL `lots_are_simple_polygons`, and that is
    # why it exists. D and H are both A's geometry — 2 of the 49 block rings the
    # suite builds — so the round-six fold fix was validated on 4% of them. One
    # parm click reaches the rest, and there the fix does not hold: a simple
    # inner ring does NOT imply simple ring parcels (S8 round seven names three
    # independent mechanisms, including an inside-out ring that the sign guard
    # is structurally incapable of catching, because a 180 degree rotation in 2D
    # preserves orientation).
    #
    # A red case is the honest form of a known defect. The alternative is a
    # green suite over a mode the design calls a hard requirement, shipping
    # self-intersecting parcels labelled buildable — which is what the last six
    # audit rounds were spent discovering.
    it, it_solver, i = _chain(parent, "I_city", cf, False)
    parent.node("I_city_tracer").parm("domain").set(800.0)
    i.parm("lots_params_subdiv_mode").set(1)
    cases["I_offset_radial"] = {"city": i, "trace": it, "solver": it_solver, "input": cf, "field": cf}

    # E — the SHORT T, the one case that reaches `max_fillet_fraction`.
    #
    # An audit found the clamp had never executed on any of A-D: their tangent
    # runs peak at 53% of the cap, so disabling it left every number
    # bit-identical. Same defect class as `offset` mode in D — a mechanism the
    # suite never runs is untested however green the run is — and the same cure.
    #
    # Sized from the clamp condition, which is narrower than it looks. The run
    # is r/tan(theta/2) and it must exceed 0.4 x the shorter street, while the
    # whole cut (kerb corner + run) must still leave the street alive and the
    # street must clear graph_prune_min_edge_len. A shallow angle does NOT work:
    # at 30 degrees the miter alone reaches 54 m of a 60 m arm, so the arm is
    # eaten before the clamp is reached — the shallow-angle family is §S5's
    # bevel, a separate unbuilt thing. A perpendicular T of local streets does:
    # r = 4 x 2.5 = 10 m of radius wants 10 m of run, 0.4 x the 20 m arm allows
    # 8, and the resulting 15.2 m cut leaves 4.8 m of the arm standing.
    edraw = parent.createNode("python", "E_drawn_streets")
    edraw.parm("python").set(_DRAW_SNIPPET.replace(
        repr(DRAWN_STREETS), repr(SHORT_T_STREETS)))
    et, et_solver, e = _chain(parent, "E_short_t", edraw, True)
    et.parm("s5j_params_corner_radius_scale").set(2.5)
    cases["E_short_t"] = {"city": e, "trace": et, "solver": et_solver, "input": edraw}

    # F — the 90 DEGREE BEND ON AN ARTERIAL. S3b's own worked example, and the
    # one amplitude at which the curvature clamp is actually a solver rather
    # than a nudge.
    #
    # It exists because an audit ran the shipped clamp on exactly this and found
    # it does not converge: kappa x R_min after 10 / 50 / 200 / 1000 / 5000
    # Jacobi sweeps is 4.366 / 3.383 / 2.169 / 1.031 / 1.000, so at the shipped
    # 200 it delivered R = 26.8 / 2.169 = 12.4 m against a 13.4 m half-width —
    # inside S3b's own inversion floor, where the inner kerb turns inside out.
    # Every case A-E only ever asks the clamp for a few degrees, so all five
    # sat at exactly 1.000 and the suite was green. Third mechanism in this
    # project to ship green and unexercised at its design amplitude, after
    # `offset` lot mode (4e-6) and `max_fillet_fraction` (4h-2); the cure is the
    # same one every time, which is a case that reaches the amplitude.
    #
    # Sized so the bend really is on an arterial and really is 90 degrees. The
    # T at (-40, -140) splits the L into a 160 m collector and a 520 m arm; the
    # 520 m arm carries the corner and clears `street_params_arterial_len`
    # (180 m), so it is 26.8 m wide and R_min = 26.8 m. The fillet needs
    # R x tan(45) = 26.8 m of tangent run on each leg and the legs are 340 and
    # 340, so the turn is feasible with room to spare — a failure here is the
    # solver, not the input.
    fdraw = parent.createNode("python", "F_drawn_streets")
    fdraw.parm("python").set(_DRAW_SNIPPET.replace(
        repr(DRAWN_STREETS), repr(BEND_STREETS)))
    ft, ft_solver, f = _chain(parent, "F_arterial_bend", fdraw, True)
    cases["F_bend"] = {"city": f, "trace": ft, "solver": ft_solver, "input": fdraw}

    # G - THE TONGUE, drawn deliberately. `s5j_params_min_standing_widths` is
    # the parameter it exercises, and adding a parameter means adding a case.
    #
    # It reproduces C_radial's prim 60, which the artist circled four times: a
    # 24.00 m `local` arm off a FOUR-WAY junction whose mouth eats 17.75 m,
    # shipping 6.24 m of pavement at 14.4 m width - wider than it is long,
    # sticking out of the patch and stopping flat. Every check passed on it,
    # because `min_end_segment` is 1.0 m and 6.24 > 1.0.
    #
    # Sized from the trim, not from taste. The two 250 m arms and the 500 m
    # crossbar all clear `street_params_arterial_len` (180 m) so they are 26.8 m
    # arterials; the 24 m arm is a 14.4 m `local`, and it clears
    # `graph_prune_min_edge_len` (13 m) so pruning keeps it - which is the whole
    # point, the old thresholds all pass this. At the perpendicular corner the
    # kerb lines meet 13.4 m out (the arterial's half-width) and the fillet adds
    # r/tan(45) = 4 m, so ~17.4 m of the 24 m arm is eaten and ~6.6 m stands,
    # ratio 0.46 against a floor of 1.0.
    #
    # What it asserts, through the standard suite: the arm is gone from the
    # published graph (`counts.edges` 3, `dead_ends.total` 3), the junction
    # re-solves as a clean T rather than keeping a mouth for a street that no
    # longer exists (`every_mouth_has_a_road` 0), and nothing is left under the
    # ratio (`trim_leaves_road_standing.under_ratio` 0).
    gdraw = parent.createNode("python", "G_drawn_streets")
    gdraw.parm("python").set(_DRAW_SNIPPET.replace(
        repr(DRAWN_STREETS), repr(TONGUE_STREETS)))
    gt, gt_solver, g = _chain(parent, "G_tongue", gdraw, True)
    cases["G_tongue"] = {"city": g, "trace": gt, "solver": gt_solver, "input": gdraw}

    # J - THE FIVE-WAY STAR, and the first case in this suite that executes the
    # S5a repair at all.
    #
    # ⚠️ Until this existed, `graph_stub_mark`, `graph_stub_kill`,
    # `graph_stub_fuse` and `graph_realign` were run by NOTHING. They fire on the
    # artist's radial scene and on no test case: A/B/D/E/F/G/H never reach five
    # arms, and on C_radial and I_offset_radial the feasibility gate declines, so
    # the wrangle bodies never execute. That is the gap S5a section 7 item 2 and
    # section 9 item 1(c) have now recorded three times - a fix for a case the
    # suite does not run cannot be verified, which is precisely how the sixth
    # attempt shipped green while it was deleting streets.
    #
    # Sized from `graph_realign`'s own feasibility condition, not from taste.
    # The crowded pair is the tightest angular gap at the node, so the bearings
    # are uneven and 0 / 32 degrees is the minimum: 32 clears
    # `street_params_min_junction_angle` (25) so `graph_min_angle` does not
    # simply delete one of the pair, and it is the same order as the 32.5 degree
    # pair measured on C_radial. Then, with the arterial 26.8 m wide and the
    # collector 15.1 m:
    #
    #   need = (26.8 + 15.1)/2 / (2 sin(32/2)) = 38.0 m   - the two mouths clear
    #   lo   = min_node_dist + one resample step = 40 + 5 = 45 m
    #   d    = max(need, lo) = 45 m, then clamped to HALF of each arm
    #
    # so both arms of the crowded pair must be at least 90 m: the host is 200 m
    # (also >= `street_params_arterial_len` 180, so it is the wide one and the
    # minor leg is therefore the collector, by width) and the minor leg is 120 m
    # (>= `collector_len` 70). The landing is snapped to a host VERTEX and
    # `graph_resample` puts those 5 m apart, so it lands at exactly 45 m, leaving
    # 155 m of host beyond it - clear of the same 45 m floor at the far end. The
    # other three arms are 110 / 200 / 100 m so no arm is a tongue, none is
    # pruned (`graph_prune_min_edge_len` 13 m), and every arm tip is more than
    # `d_extend` (90 m) from anything `graph_extend` could bridge it to.
    #
    # What it asserts, through the standard suite: `no_multileg_junctions`
    # max_arms 4 / over_cap 0 reached WITHOUT a deletion
    # (`connections_are_never_refused` green, every counter 0 after pass 0), a
    # real T rather than a touch (`counts.edges` 6 for 5 drawn arms - the host
    # split in two - and `dead_ends` still 5), and the T clear of the jog rule
    # (`junctions_not_too_close` shortest 45 m against a 40 m floor).
    jdraw = parent.createNode("python", "J_drawn_streets")
    jdraw.parm("python").set(_DRAW_SNIPPET.replace(
        repr(DRAWN_STREETS), repr(STAR5_STREETS)))
    jt, jt_solver, j = _chain(parent, "J_five_star", jdraw, True)
    cases["J_five_star"] = {"city": j, "trace": jt, "solver": jt_solver, "input": jdraw}

    # K - THE STUB TRIANGLE THE GATE MUST REFUSE, which is the other half of J.
    #
    # ⚠️ THIS CASE IS EXPECTED TO BE RED ON `junctions_not_too_close` AND
    # `no_multileg_junctions`, and that is what it is for. S5a's shipped rule is
    # that a jog is collapsed ONLY when what it leaves can be repaired, because
    # an unrepaired jog is a smaller defect than a five-way the corner solver
    # inverts on. Those two checks are the honest form of the jog that stays; the
    # assertion this case adds is that the refusal is CLEAN - nothing deleted, no
    # degree-5 node shipped - rather than a collapse into a junction nothing can
    # repair.
    #
    # It is also the case that has teeth against the feasibility gate's own blind
    # spot. The gate built its arm set from `pointprims(pt) + pointprims(other)`,
    # the two ends of the edge being collapsed, so on a 3-CYCLE the third
    # corner's external arms - which land on the same merged node over the
    # following passes - were never counted. Measured on the artist's live graph
    # it read narm = 4 / 3 / 3 where the truth is 5. There it is harmless. Here
    # it is not, and the A/B is measured: run against the pre-fix definition this
    # case COLLAPSES (8 edges -> 6) and `graph_realign` then refuses the five-way
    # it made, so a degree-5 node ships - which is C_radial's failure mode,
    # boundary inversion and +24 selfx_junction_surface.
    #
    # ⚠️ AND THE FIRST VERSION OF THIS CASE DID NOT REPRODUCE THAT, which is why
    # the numbers below are what they are. With the short arm at 80 m the blind
    # gate collapsed the triangle and the realign then succeeded anyway - it only
    # ever tries the TIGHTEST angular pair, and that pair happened to be two
    # other, longer arms. A case that documents a gate has to make the gate's own
    # answer decide the outcome, so the geometry is arranged so the tightest pair
    # after the merge is the one containing the short arm.
    #
    # Sized so every threshold is cleared on purpose. The three sides are
    # 32.00 / 32.25 / 32.25 m - under `graph_params_min_node_dist` (40 m), so
    # they are jogs, and over `graph_prune_min_edge_len` (13 m), so pruning keeps
    # them. The corners carry 2 + 2 + 1 external arms, which is exactly the
    # 3 + 4 + 4 degree histogram and the five external arms measured on the
    # artist's scene. Every angle at every corner is at least 59.5 degrees, well
    # clear of `min_junction_angle` (25), so nothing here is resolved by deleting
    # a leg, and every arm tip is more than `d_extend` (90 m) from anything
    # `graph_extend` could bridge it to.
    #
    # The two numbers that decide it, both derived from `graph_realign`:
    #
    #   * the gate's floor is 2 x (min_node_dist + one resample step) = 90 m, and
    #     the third corner's arm is 55 m, so the CORRECTED gate refuses.
    #   * a collapse LENGTHENS that arm, because its foot moves to the merged
    #     node: 55 m from (16, 28) becomes 84.53 m from (0, 0), still under 90.
    #     The realign may not move an endpoint past half its own street, so
    #     d clamps to 42.27 m against a 45 m landing floor and it refuses too.
    #     The four outer bearings are placed so that after the merge the arms sit
    #     at 47.0 / 79.1 / 180.0 / 250.0 / 310.0 degrees - gaps of 32.1 / 100.9 /
    #     70.0 / 60.0 / 97.0 - so the tightest pair IS the short arm and its
    #     189.6 m arterial neighbour, and 32.1 degrees still clears
    #     `min_junction_angle`. Nothing is resolved by deletion in either build.
    kdraw = parent.createNode("python", "K_drawn_streets")
    kdraw.parm("python").set(_DRAW_SNIPPET.replace(
        repr(DRAWN_STREETS), repr(STUB_TRIANGLE_STREETS)))
    kt, kt_solver, k = _chain(parent, "K_stub_triangle", kdraw, True)
    cases["K_stub_triangle"] = {"city": k, "trace": kt, "solver": kt_solver,
                                "input": kdraw}

    # M / N / O - THE SHALLOW-Y FAMILY (M2). See _shallow_y() for the
    # sizing; the three differ ONLY in the leg's angle and its LENGTH relative
    # to the host's east arm - which is what decides the victim, not class.
    #
    # ⚠️ These are cases-first, ahead of the mechanism that resolves them
    # (§11.5's `merge`, M5). Their job today is to RECORD what the build does
    # with a shallow approach, which is `graph_min_angle` deleting a street
    # below `min_junction_angle` - the one deletion §S3 forbids and §S5a item 6
    # left as the artist's call. A family that only got added once the fix
    # existed would be a family that could never show the fix changed anything.
    for label, deg, leg, east in (("M_shallow_y_24", 24.0, 120.0, 500.0),
                                  ("N_shallow_y_32", 32.0, 120.0, 500.0),
                                  # ...and the OTHER branch of the same
                                  # deletion. The east host half is 200 m and
                                  # the leg 300 m, so the leg is the LONGER of
                                  # the offending pair and `graph_min_angle`
                                  # takes the host's own arterial instead. Same
                                  # rig, same angle as M's neighbour, opposite
                                  # victim - and nothing else in the suite
                                  # reaches it.
                                  ("O_shallow_y_host_dies", 22.0, 300.0, 200.0)):
        ydraw = parent.createNode("python", label + "_streets")
        ydraw.parm("python").set(_DRAW_SNIPPET.replace(
            repr(DRAWN_STREETS), repr(_shallow_y(deg, leg, east))))
        yt, yt_solver, y = _chain(parent, label, ydraw, True)
        cases[label] = {"city": y, "trace": yt, "solver": yt_solver,
                        "input": ydraw}

    # P - THE FOUR-JUNCTION STUB CHAIN. See STUB_CHAIN_STREETS.
    pdraw = parent.createNode("python", "P_drawn_streets")
    pdraw.parm("python").set(_DRAW_SNIPPET.replace(
        repr(DRAWN_STREETS), repr(STUB_CHAIN_STREETS)))
    pt_, pt_solver, p = _chain(parent, "P_stub_chain", pdraw, True)
    cases["P_stub_chain"] = {"city": p, "trace": pt_, "solver": pt_solver,
                             "input": pdraw}

    # Q - THE S7 T-CASE (M4): two AUTHORED `junction` nodes on a closed ring.
    #
    # ⚠️ 2026-08-17: the artist ruled the uncut-principal render a BUG
    # (section 11.5) and the build path was reverted - the type moves NO
    # geometry now. Q keeps its authoring on purpose: it is the proof the
    # schema flows downstream while the build stays the crossing's. The
    # revert A/B measured Q's city/blocks/lots outputs bit-identical to its
    # authoring-bypassed twin; only the graph output's ATTRIBUTE digest
    # differs, which is the authored schema values themselves flowing.
    #
    # As drawn (historical premise): §11.5 named S7 as the integration risk -
    # at a junction node the principal's kerb ran THROUGH while minor kerbs
    # teed into it, and blocks_kerb's collect-and-close had to survive that.
    # A lone T closes no block, so the case is a ring - and it carries TWO Ts,
    # not one, because a ring with a single junction becomes ONE CLOSED PRIM
    # from that node back to itself (graph_polypath merges the degree-2 corners
    # away), which is the self-loop the planner cannot represent (`edge_id` is
    # not a valid arm key, the recorded defect - M4 closed without fixing it
    # and it is unowned). Two Ts split the ring into two open prims
    # and the loop never forms.
    #
    # Sized so the ring halves are unambiguous principals: 150+300+150 = 600 m
    # each (arterial, 26.8 m) against 60 m local minors (14.4 m). The 90-degree
    # ring corners are interior vertices - S3b's turn clamp owns them (the
    # F_bend precedent), legs 150/300 clear the 26.8 m tangent runs. Minors
    # point OUTWARD so the interior block's kerb at each T is the pure
    # through-kerb case; their tips extend along their own direction into
    # nothing (the G_tongue precedent for `d_extend`).
    #
    # AUTHORING is two wrangles between segmenter and solver - the per-node
    # downstream path §11.3 records, on the settled graph where node identity
    # exists. The ring prims claim principal at BOTH their ends (each node
    # gets exactly 2 claims from 2 distinct prims); the T nodes are typed
    # `junction`, overwriting the adapter's `crossing` default - authored
    # beats computed, exercised for real.
    qdraw = parent.createNode("python", "Q_drawn_streets")
    qdraw.parm("python").set(_DRAW_SNIPPET.replace(
        repr(DRAWN_STREETS), repr(JUNCTION_RING_STREETS)))
    qs = parent.createNode("pf_citygen_segmenter", "Q_junction_ring_segmenter")
    qs.setInput(0, qdraw)
    qa_prim = parent.createNode("attribwrangle", "Q_author_principal")
    qa_prim.parm("class").set(1)
    qa_prim.parm("snippet").set(
        "// authored principal: the two 600 m ring halves, claiming at BOTH\n"
        "// their ends - 2 claims from 2 distinct prims at each T node\n"
        'if (f@edge_len > 500.0) {\n'
        "    i@principal_start = 1;\n"
        "    i@principal_end = 1;\n"
        "}\n")
    qa_prim.setInput(0, qs)
    qa_pt = parent.createNode("attribwrangle", "Q_author_junction")
    qa_pt.parm("class").set(2)
    qa_pt.parm("snippet").set(
        "// authored junction type at both Ts (the only degree >= 3 nodes)\n"
        'if (i@is_node == 1 && neighbourcount(0, @ptnum) >= 3)\n'
        '    s@junction_type = "junction";\n')
    qa_pt.setInput(0, qa_prim)
    qv = parent.createNode("pf_citygen_solver", "Q_junction_ring_solver")
    qv.setInput(0, qa_pt)
    for q in qv.parms():
        if q.name().startswith("s5j_params_") and qs.parm(q.name()) is not None:
            q.setExpression('ch("../%s/%s")' % (qs.name(), q.name()))
    qm = parent.createNode("pf_citygen_mesh", "Q_junction_ring")
    qm.setInput(0, qv, 0)
    qm.setInput(1, qv, 1)
    cases["Q_junction_ring"] = {"city": qm, "trace": qs, "solver": qv,
                                "input": qdraw}

    # ⚠️ The harness could not reach the TRACER at all. `_chain` returns the
    # segmenter as the "trace" role, so `cases.parm()` searched city/trace/solver
    # and never saw the Tracer — `parm_liveness` swept its eleven live
    # parameters on nodes where they are dead and reported twelve regressions,
    # while the node they actually drive was swept by nothing.
    for _c in cases.values():
        _t = parent.node(_c["city"].name() + "_tracer")
        if _t is not None:
            _c["tracer"] = _t

    parent.layoutChildren()
    return parent, cases


# Internal nodes the checks reach into, as (owning role, path below it). Named
# here so a rename breaks one line rather than every check. The owner matters
# now that the pipeline is two nodes: everything about CENTRELINES is on the
# tracer, everything about GEOMETRY is on the mesh node.
INTERNAL = {
    "patches": ("city", "s5j_patches"),
    "surface": ("city", "s5j_surface"),
    # patches AND street polylines, before the trim — and before the bulbs, so
    # it stays the pre-cul-de-sac solve it has always been.
    # ⚠️ `junction_solve` moved OUT of the tracer when the pipeline split on
    # 2026-08-11. It now lives in the SOLVER, which is the only node that owns
    # S5. Leaving this pointing at "trace" would have silently returned None and
    # skipped four checks — `inner()` returns None for a missing node.
    "solve": ("solver", "junction_solve/s5j_solve"),
    "streets": ("city", "s5j_streets"),   # streets carrying trim_start / trim_end
    "trim": ("city", "s5j_trim"),         # the same streets after the cut
    "roads": ("city", "OUT_roads"),
    "graph": ("trace", "OUT_graph2"),
    "clamp": ("trace", "graph_turn_clamp"),
    # the corridor's outer boundary curve, carrying is_outer. city_is_fully_paved
    # uses it as the region that must be paved.
    "corridor": ("city", "blocks_mark_outer"),
    # S7's collect-and-close: the open kerb runs, and the loops they close into.
    # block_boundary_closes asserts the invariant the construction rests on.
    "kerb": ("city", "blocks_kerb_fuse"),
    "loops": ("city", "blocks_loops"),
}
OUTPUT_INDEX = {"city": 0, "blocks": 1, "lots": 2, "graph": 3}

# The floor under `every_block_is_subdivided`, ~90% of the shipped count on
# 2026-08-10 (A 82 - B 623 - C 759 - D 61). Every lot-quality check in the suite
# improves when parcels vanish, so without a floor "fewer lots" reads as "better
# lots" — which is exactly what was suspected of the new half-plane clipper and
# had to be disproved by hand. E/F/G close no block and legitimately ship none.
LOT_FLOOR = {"A_drawn": 74, "B_grid": 560, "C_radial": 683, "D_offset": 55,
             "E_short_t": 0, "F_bend": 0, "G_tongue": 0,
             # J is a star of dead ends and closes no block at all. K closes
             # exactly one - the ~450 m2 triangle interior, which is smaller than
             # the kerbs around it; both are pinned at 0 for the same reason I is,
             # because a parcel count is only worth defending once the geometry
             # under it is not a documented defect.
             "J_five_star": 0, "K_stub_triangle": 0,
             # H is D's geometry, so it ships D's parcel count; only the
             # LABELS differ. If this floor ever drops, the shape rungs have
             # started deleting rather than flagging.
             "H_offset_strict": 55,
             # I is deliberately unpinned at 0. It is a case that documents a
             # LIVE defect, so its parcel count is not yet a number worth
             # defending — pin it the day `offset` stops folding on non-A
             # blocks, and not before, or this floor freezes broken output in.
             "I_offset_radial": 0,
             # M2's cases close no block between them: the shallow-Y family is a
             # host and one leg, and the stub chain is a chain — neither has a
             # cycle, so there is no ring for S7 to close and no parcel to pin.
             "M_shallow_y_24": 0, "N_shallow_y_32": 0,
             "O_shallow_y_host_dies": 0, "P_stub_chain": 0,
             # Q closes ONE block - the ring interior. The render was looked
             # at 2026-08-17 (verdict: the junction type builds as a crossing,
             # section 11.5's ruling), so the count is pinned from measurement
             # per the A-D precedent: 155 lots shipped, floor ~90%.
             "Q_junction_ring": 139}


def inner(case, role):
    """The internal node for `role`, or None if it is missing or in error.

    Unlocks every HDA on the way down — `junction_solve/s5j_solve` is two
    assets deep now that the junction solver is its own reusable HDA.
    """
    owner, path = INTERNAL[role]
    n = case.get(owner)
    for part in path.split("/"):
        if n is None:
            return None
        n.allowEditingOfContents()
        n = n.node(part)
    return None if (n is None or n.errors()) else n


def parm(case, name):
    """A promoted parameter, wherever it now lives.

    Since the interfaces were trimmed to what each asset READS (2026-08-12):
    S1/S2 and Loop Closure on the tracer, S3/S3b/S4 on the segmenter, S5 on the
    segmenter AND the solver (the pre-measure and the solve must agree, and
    `_chain` links them), S6/S7/S8 on the mesh.

    ⚠️ **THIS DOCSTRING CLAIMED "exactly one asset carries any given name and
    this search cannot pick the wrong copy". IT IS FALSE, and it contradicted
    itself two lines later.** Measured by audit 2026-08-12: **eight names live
    on two roles** — the seven `s5j_params_*` plus `junctions_folder`, on the
    segmenter *and* the solver. The trim removed the decoys; it did not and
    could not make names unique, because S5 is genuinely shared.

    The search is still correct, but by ORDER and not by uniqueness: `solver`
    comes after `trace`, so a shared name returns the SEGMENTER's copy, which is
    the one `_chain()` drives and the solver's copy is expression-linked to.
    Verified: 7 of 7 links bind and track on all 15 cases. Change that role
    order and S5 parameters silently start steering the linked end instead of
    the driving one.

    A stated-but-untrue invariant in the helper every case uses to find a
    parameter is exactly the class of thing that produced the `domain` incident
    (promoted on three assets, read by one, 25% larger city). Do not restore the
    claim; if uniqueness is ever wanted, make it true and assert it.
    """
    for role in ("city", "trace", "solver", "tracer"):
        n = case.get(role)
        p = None if n is None else n.parm(name)
        if p is not None:
            return p
    return None
