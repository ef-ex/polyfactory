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
}
OUTPUT_INDEX = {"city": 0, "blocks": 1, "lots": 2, "graph": 3}
