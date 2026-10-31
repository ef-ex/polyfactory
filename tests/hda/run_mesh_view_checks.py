"""`pf_mesh_view` layout, against the SHIPPED asset, in a throwaway hython session.

    hython tests/hda/run_mesh_view_checks.py

The `columns` parm wraps the row of pieces: piece i goes to column i % columns,
row i // columns (0 = never wrap, the original single row). Cell pitch is 2 in
X and 3 in Z (the label sits 2 in front of each piece, so rows must clear it).
Each case compares the centre of every piece with the cell it should be in; the
last run mutates the row pitch and must go red (a check that cannot fail is
decoration). Cannot see: label placement, piece scale, the `enum_attr` parm.
"""
import os
import sys

import hou

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
hou.hda.installFile(os.path.join(REPO, "polyfactory", "otls", "pf_mesh_view.hda"))
N = 7
geo = hou.node("/obj").createNode("geo")

# N unit boxes; prim attr isbox tells them from the number labels the node adds
box = geo.createNode("box")
box.parmTuple("size").set((1, 1, 1))
pts = geo.createNode("line")
pts.parm("points").set(N)
pts.parmTuple("dir").set((1, 0, 0))
pts.parm("dist").set(N - 1)
cp = geo.createNode("copytopoints::2.0")
cp.setInput(0, box)
cp.setInput(1, pts)
w = geo.createNode("attribwrangle")       # a box has 8 points: piece = ptnum / 8
w.parm("class").set(2)
w.setInput(0, cp)
w.parm("snippet").set("i@pf_enum = @ptnum / 8;")
mk = geo.createNode("attribwrangle")
mk.parm("class").set(1)
mk.setInput(0, w)
mk.parm("snippet").set("i@isbox = 1;")
view = geo.createNode("pf::mesh_view::1.0.0")
view.setInput(0, mk)


def centres():
    g = view.geometry()
    acc = {}
    for p in g.prims():
        if p.attribValue("isbox"):
            c = acc.setdefault(p.attribValue("pf_enum"), [0.0, 0.0, 0.0, 0])
            for v in p.vertices():
                q = v.point().position()
                c[0] += q[0]; c[1] += q[1]; c[2] += q[2]; c[3] += 1
    return {k: (c[0] / c[3], c[2] / c[3]) for k, c in acc.items()}


def check(columns, rowpitch=3.0):
    if columns is not None:
        view.parm("columns").set(columns)
    got = centres()
    bad = []
    if sorted(got) != list(range(N)):
        bad.append("pieces %s" % sorted(got))
    for i in range(N):
        col, row = (i % columns, i // columns) if columns else (i, 0)
        want = (2 * col + 0.5, rowpitch * row + 0.5)
        if i in got and max(abs(got[i][0] - want[0]), abs(got[i][1] - want[1])) > 1e-4:
            bad.append("piece %d at %s want %s" % (i, tuple(round(v, 3) for v in got[i]), want))
    return bad


fails = 0
for cols in (0, 1, 3, 7, 20):
    bad = check(cols)
    fails += bool(bad)
    print("columns=%-2d %s %s" % (cols, "FAIL" if bad else "ok", bad[:2]))

# mutation: the shipped Z pitch edited to 2 -> the 3-column case must go red
view.allowEditingOfContents()
t = view.node("transform1")
mut = t.parm("tz").expression()
t.parm("tz").setExpression(mut.replace("3*", "2*"))
bad = check(3)
print("mutation (row pitch 2): %s" % ("red, as it must" if bad else "STILL GREEN - the check is decoration"))
fails += not bad
sys.exit(1 if fails else 0)
