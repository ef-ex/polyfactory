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

    parent.layoutChildren()
    return parent, cases


# Internal nodes the checks reach into. Named here so a rename breaks one line
# rather than every check.
INTERNAL = {
    "patches": "s5j_patches",
    "surface": "s5j_surface",
    "roads": "OUT_roads",
    "graph": "OUT_graph2",
    "blocks": "OUT_BLOCKS_PLACEHOLDER",
}
OUTPUT_INDEX = {"city": 0, "blocks": 1, "lots": 2, "graph": 3}
