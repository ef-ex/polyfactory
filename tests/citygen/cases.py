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
        "pf_citygen_trace.hda", "pf_citygen_streets.hda")


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
    a = parent.createNode("pf_citygen_streets", "A_city")
    a.setInput(0, draw)
    cases["A_drawn"] = {"city": a, "input": draw}

    # B — straight/grid tensor field
    bf = parent.createNode("pf_citygen_field_grid", "B_field_grid")
    bf.parm("angle").set(18.0)
    bf.parm("weight").set(1.0)
    bf.parm("falloff").set(3000.0)
    bt = parent.createNode("pf_citygen_trace", "B_trace")
    bt.setInput(0, bf)
    bt.parm("domain").set(800.0)
    b = parent.createNode("pf_citygen_streets", "B_city")
    b.setInput(0, bt)
    cases["B_grid"] = {"city": b, "input": bt, "field": bf}

    # C — radial tensor field
    cf = parent.createNode("pf_citygen_field_radial", "C_field_radial")
    cf.parm("weight").set(2.5)
    cf.parm("falloff").set(2000.0)
    ct = parent.createNode("pf_citygen_trace", "C_trace")
    ct.setInput(0, cf)
    ct.parm("domain").set(800.0)
    c = parent.createNode("pf_citygen_streets", "C_city")
    c.setInput(0, ct)
    cases["C_radial"] = {"city": c, "input": ct, "field": cf}

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
    d = parent.createNode("pf_citygen_streets", "D_city")
    d.setInput(0, draw)
    d.parm("lots_params_subdiv_mode").set(1)          # 0 recursive_obb, 1 offset
    cases["D_offset"] = {"city": d, "input": draw}

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
    e = parent.createNode("pf_citygen_streets", "E_short_t")
    e.setInput(0, edraw)
    e.parm("s5j_params_corner_radius_scale").set(2.5)
    cases["E_short_t"] = {"city": e, "input": edraw}

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
    f = parent.createNode("pf_citygen_streets", "F_arterial_bend")
    f.setInput(0, fdraw)
    cases["F_bend"] = {"city": f, "input": fdraw}

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
    g = parent.createNode("pf_citygen_streets", "G_tongue")
    g.setInput(0, gdraw)
    cases["G_tongue"] = {"city": g, "input": gdraw}

    parent.layoutChildren()
    return parent, cases


# Internal nodes the checks reach into. Named here so a rename breaks one line
# rather than every check.
INTERNAL = {
    "patches": "s5j_patches",
    "surface": "s5j_surface",
    "solve": "s5j_solve",       # patches AND street polylines, before the trim
    "streets": "s5j_streets",   # streets carrying trim_start / trim_end
    "trim": "s5j_trim",         # the same streets after the cut
    "roads": "OUT_roads",
    "graph": "OUT_graph2",
    "blocks": "OUT_BLOCKS_PLACEHOLDER",
    # the corridor's outer boundary curve, carrying is_outer. city_is_fully_paved
    # uses it as the region that must be paved.
    "corridor": "blocks_mark_outer",
    # S7's collect-and-close: the open kerb runs, and the loops they close into.
    # block_boundary_closes asserts the invariant the construction rests on.
    "kerb": "blocks_kerb_fuse",
    "loops": "blocks_loops",
}
OUTPUT_INDEX = {"city": 0, "blocks": 1, "lots": 2, "graph": 3}
