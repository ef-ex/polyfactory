"""`pf_mesh_view` layout and marking, against the SHIPPED asset, in a throwaway hython session.

    hython tests/hda/run_mesh_view_checks.py

Layout: the `columns` parm wraps the row of pieces: piece i goes to column i % columns,
row i // columns (0 = never wrap, the original single row). Cell pitch is 2 in
X and 3 in Z (the label sits 2 in front of each piece, so rows must clear it).
Each case compares the centre of every piece with the cell it should be in; the
row-pitch mutation must go red (a check that cannot fail is decoration).
Cannot see: label placement, piece scale.

Marking: the viewer state turns a click into a layout position; `hm().piece_at` turns
that into a piece number and `hm().toggle` edits the `marked` list. Checked: every
prim of the view (pieces AND labels, 2-digit labels included) maps to its piece; the
toggle adds and removes; the Marked output (laid out, and `original_scale`) holds
exactly the marked pieces, compared point for point against the view / the input; the
highlight colours exactly the marked pieces on the class Cd lives on (no Cd, point Cd,
vertex Cd) and leaves the others their input colour; the Marked output keeps the input's
colours (never the highlight); no `_*` attribute on any class of either output; the
`mark` wrangle and `hm().marked()` parse the same strings the same way (garbage, tabs,
newlines, leading zeros); a string enum attribute works too.
Every one of those is re-run under its own mutation (MUTATIONS) and only the check(s)
paired with it count: they must print FAIL.
Cannot see: the viewer state itself (ray from a real click, needs the GUI), the
object-transform inverse in it, the Clear button; a detail Cd on the input (the
highlight's prim-Cd default from it is unexercised); points shared between pieces
(each box here owns its points); whether a click re-cooks the per-piece loop (timed
by hand, not asserted); `_*` groups on the outputs (attributes only).
"""
import os
import shutil
import subprocess
import sys
import tempfile

import hou

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
HDA = os.path.join(REPO, "polyfactory", "otls", "pf_mesh_view.hda")
# PF_MESH_VIEW_MUTATE=<name>: one run with one deliberate break; a PythonModule break is
# made in a throwaway COPY of the asset (setContents writes the file), never the shipped one
MUT = os.environ.get("PF_MESH_VIEW_MUTATE", "")
LAID = ["Marked, laid out, columns=0", "Marked, laid out, columns=5"]
ORIG = ["Marked, original scale, columns=0", "Marked, original scale, columns=5"]
SECTION_MUTATIONS = {  # name -> (old, new, checks that must FAIL) in the PythonModule section
    "piece_at_x": ("(pos[0] + 0.5)", "(pos[0])", ["pick columns=0", "pick columns=4"]),
    "piece_at_row": ("pos[2] / 3.0", "pos[2] / 2.5", ["pick columns=4"]),
    "toggle": ("^ {piece}", "| {piece}", ["toggle 5,12,5,20 -> '12 20'"]),
    "py_parse": ('.replace(",", " ").split()', '.replace(",", " ").split(" ")', ["parse: mark == hm().marked()"]),
}
# name -> (node, parm, old, new, checks that must FAIL) on the edited instance; parm "snippet"
# replaces text in it, "input0" rewires input 0 from node old to node new, else old/new are values
NODE_MUTATIONS = {
    "piece": ("attribwrangle2", "snippet", 'detail(1, "iteration", 0);', 'detail(1, "iteration", 0) + 1;',
              LAID + ["highlight, no Cd"]),
    "token_filter": ("mark", "snippet", 'if (re_match("^[0-9]+$", s))', "if (1)",
                     ["typed 'x 4' marks only 4", "parse: mark == hm().marked()"]),
    "highlight_colour": ("highlight", "snippet", "orange = {1, 0.45, 0}", "orange = {1, 1, 1}",
                         ["highlight, no Cd", "highlight, point Cd", "highlight, vertex Cd"]),
    "highlight_class": ("highlight", "snippet", 'int vtx = hasvertexattrib(0, "Cd");\n    int pt = haspointattrib(0, "Cd");',
                        "int vtx = 0;\n    int pt = 0;", ["highlight, point Cd", "highlight, vertex Cd"]),
    "highlight_to_marked": ("drop_unmarked", "input0", "mark", "highlight", ["Marked keeps input colours"]),
    "drop": ("drop_unmarked", "snippet", "if (!i@_mark)", "if (0)", LAID),
    "keep": ("keep_marked", "snippet", "if (!keep)", "if (keep)", ORIG),
    "leak0": ("scratch_delete", "primdel", "_*", "", ["leak, output 0"]),
    "leak1": ("scratch_delete_marked", "dtldel", "_*", "", ["leak, Marked laid out"]),
}
if MUT in SECTION_MUTATIONS:
    tmp = os.path.join(os.environ["PF_MESH_VIEW_TMP"], "pf_mesh_view.hda")
    shutil.copy(HDA, tmp)
    HDA = tmp
hou.hda.installFile(HDA)
if MUT in SECTION_MUTATIONS:
    _sec = hou.hda.definitionsInFile(HDA)[0].sections()["PythonModule"]
    _old, _new, _ = SECTION_MUTATIONS[MUT]
    assert _old in _sec.contents(), MUT
    _sec.setContents(_sec.contents().replace(_old, _new))

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
if not MUT:
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

# ---------------------------------------------------------------- marking
M = 23                                    # enough for 2-digit labels
pts.parm("points").set(M)
pts.parm("dist").set(M - 1)
mk.parm("snippet").set('i@isbox = 1; int e = point(0, "pf_enum", primpoint(0, @primnum, 0));'
                       ' s@pf_name = sprintf("p%02d", 50 - e);')
BLUE, GREEN, WHITE, ORANGE = (0.0, 0.0, 1.0), (0.0, 1.0, 0.0), (1.0, 1.0, 1.0), (1.0, 0.45, 0.0)
cd_pt = geo.createNode("attribwrangle")   # point Cd fixture
cd_pt.parm("class").set(2)
cd_pt.setInput(0, mk)
cd_pt.parm("snippet").set("v@Cd = {0, 0, 1};")
cd_vtx = geo.createNode("attribwrangle")  # vertex Cd fixture
cd_vtx.parm("class").set(3)
cd_vtx.setInput(0, mk)
cd_vtx.parm("snippet").set("v@Cd = {0, 1, 0};")
mv = geo.createNode("pf::mesh_view::1.0.0")   # fresh: `view` carries the layout mutation
mv.setInput(0, mk)
if MUT in NODE_MUTATIONS:
    _n, _p, _old, _new, _ = NODE_MUTATIONS[MUT]
    mv.allowEditingOfContents()
    _w = mv.node(_n)
    if _p == "snippet":
        assert _old in _w.parm("snippet").eval(), MUT
        _w.parm("snippet").set(_w.parm("snippet").eval().replace(_old, _new))
    elif _p == "input0":
        assert _w.inputs()[0].name() == _old, MUT
        _w.setInput(0, mv.node(_new))
    else:
        assert _w.parm(_p).eval() == _old, MUT
        _w.parm(_p).set(_new)


def centroid(p):
    vs = [v.point().position() for v in p.vertices()]
    return hou.Vector3(sum(q[0] for q in vs) / len(vs), sum(q[1] for q in vs) / len(vs),
                       sum(q[2] for q in vs) / len(vs))


def boxes(g, attr):
    """attribute value -> sorted point positions of that box, from geometry g."""
    out = {}
    on_prims = g.findPrimAttrib(attr) is not None
    for p in g.prims():
        if p.attribValue("isbox"):
            val = p.attribValue(attr) if on_prims else p.vertex(0).point().attribValue(attr)
            out.setdefault(val, []).extend(
                tuple(round(c, 6) for c in v.point().position()) for v in p.vertices())
    return {k: sorted(v) for k, v in out.items()}


def picking(cols):
    """Every prim of the view, label prims too, must map to the piece it belongs to.
    Oracle: a box maps to its own piece number (its rank in the layout = the label);
    a label prim belongs to the nearest box centre that is not in front of it in Z."""
    mv.parm("columns").set(cols)
    g = mv.geometry()
    num = {}                              # box centre -> piece number, from the cell formula
    for k in range(M):
        col, row = (k % cols, k // cols) if cols else (k, 0)
        num[(2 * col + 0.5, 3 * row + 0.5)] = k
    bad = []
    for p in g.prims():
        c = centroid(p)
        if p.attribValue("isbox"):
            want = p.attribValue("pf_enum")
        else:
            cands = [(abs(x - c[0]), k) for (x, z), k in num.items() if z <= c[2] + 1e-6 and c[2] - z < 3]
            want = min(cands)[1]
        # a click can land anywhere on the prim: its centre and its outline pulled 1 % inwards
        for q in [c] + [c + (v.point().position() - c) * 0.99 for v in p.vertices()]:
            got = mv.hm().piece_at(mv, q)
            if got != want:
                bad.append("prim %d %s at %s -> %d want %d" % (p.number(), "box" if p.attribValue("isbox") else "label",
                                                              tuple(round(v, 2) for v in q), got, want))
                break
    return bad


def run(name, bad):
    global fails
    fails += bool(bad)
    print("%-34s %s %s" % (name, "FAIL" if bad else "ok", bad[:3]))


def same(a, b):                           # float32 colours: 1e-6 at magnitude <= 1
    return max(abs(x - y) for x, y in zip(a, b)) <= 1e-6


def colours(g, p, cls):
    if cls == "prim":
        return [p.attribValue("Cd")]
    if cls == "vertex":
        return [v.attribValue("Cd") for v in p.vertices()]
    return [v.point().attribValue("Cd") for v in p.vertices()]


def leaks(g):
    return ["%s %s" % (cls, a.name()) for cls, f in (("point", g.pointAttribs), ("prim", g.primAttribs),
                                                     ("vertex", g.vertexAttribs), ("detail", g.globalAttribs))
            for a in f() if a.name().startswith("_")]


run("pick columns=0", picking(0))
run("pick columns=4", picking(4))

mv.parm("marked").set("")
for k in (5, 12, 5, 20):
    mv.hm().toggle(mv, k)
run("toggle 5,12,5,20 -> '12 20'", [] if mv.evalParm("marked") == "12 20" else [mv.evalParm("marked")])

mv.parm("marked").set("3, 11 17")         # typed by hand, comma and space
MARKED = {3, 11, 17}
src = mk.geometry()
for cols in (0, 5):
    mv.parm("columns").set(cols)
    mv.parm("original_scale").set(0)
    view_boxes = boxes(mv.geometry(), "pf_enum")
    out = mv.geometry(1)
    bad = []
    if any(not p.attribValue("isbox") for p in out.prims()):
        bad.append("labels in the Marked output")
    got = boxes(out, "pf_enum")
    if sorted(got) != sorted(MARKED):
        bad.append("pieces %s" % sorted(got))
    bad += ["piece %d moved" % k for k in got if got[k] != view_boxes.get(k)]
    run("Marked, laid out, columns=%d" % cols, bad)

    mv.parm("original_scale").set(1)
    out = mv.geometry(1)
    got, want = boxes(out, "pf_enum"), boxes(src, "pf_enum")
    bad = [] if sorted(got) == sorted(MARKED) else ["pieces %s" % sorted(got)]
    bad += ["piece %d differs from the input" % k for k in got if got[k] != want[k]]
    if out.intrinsicValue("pointcount") != sum(len(set(want[k])) for k in MARKED):
        bad.append("points %d" % out.intrinsicValue("pointcount"))
    layout = lambda g: [sorted(a.name() for a in f()) for f in (g.pointAttribs, g.primAttribs, g.vertexAttribs, g.globalAttribs)]
    if layout(out) != layout(src):
        bad.append("attributes %s, input has %s" % (layout(out), layout(src)))
    run("Marked, original scale, columns=%d" % cols, bad)

# highlight: on the class Cd lives on; unmarked pieces keep their input colour
mv.parm("original_scale").set(0)
for label, node, cls, base in (("no Cd", mk, "prim", WHITE), ("point Cd", cd_pt, "point", BLUE),
                               ("vertex Cd", cd_vtx, "vertex", GREEN)):
    mv.setInput(0, node)
    g = mv.geometry()
    bad = []
    for p in g.prims():
        if p.attribValue("isbox"):
            k = p.attribValue("pf_enum")
            want = ORANGE if k in MARKED else base
            if not all(same(c, want) for c in colours(g, p, cls)):
                bad.append("piece %d %s %s want %s" % (k, cls, colours(g, p, cls)[0], want))
    run("highlight, " + label, sorted(set(bad)))

    if node is cd_pt:                     # the Marked output carries the input's colours
        out = mv.geometry(1)
        bad = ["piece %d %s" % (p.attribValue("pf_enum"), c) for p in out.prims()
               for c in colours(out, p, "point") if not same(c, BLUE)]
        bad += ["prim/vertex Cd added"] if out.findPrimAttrib("Cd") or out.findVertexAttrib("Cd") else []
        run("Marked keeps input colours", bad)

        run("leak, output 0", leaks(mv.geometry()))
        run("leak, Marked laid out", leaks(mv.geometry(1)))
        mv.parm("original_scale").set(1)
        run("leak, Marked original scale", leaks(mv.geometry(1)))
        mv.parm("original_scale").set(0)
mv.setInput(0, mk)

# parsing: the `mark` wrangle (what the Marked output holds) against hm().marked()
mv.parm("marked").set("x 4")
got = sorted(boxes(mv.geometry(1), "pf_enum"))
run("typed 'x 4' marks only 4", [] if got == [4] else ["pieces %s" % got])
bad = []
for s in ("3, 11 17", "x 4", "1\t2\n3", "03,,5", "-1 2.5 7", " 9 ,\t10 "):
    mv.parm("marked").set(s)
    got, py = sorted(boxes(mv.geometry(1), "pf_enum")), mv.hm().marked(mv)
    if got != py:
        bad.append("%r: wrangle %s, python %s" % (s, got, py))
run("parse: mark == hm().marked()", bad)
mv.parm("marked").set("3, 11 17")

# string enum: piece order now follows pf_name; oracle = the name of the box in each cell
mv.parm("enum_attr").set("pf_name")
mv.parm("columns").set(0)
mv.parm("original_scale").set(1)
in_cell = {}
for p in mv.geometry().prims():
    if p.attribValue("isbox"):
        in_cell[mv.hm().piece_at(mv, centroid(p))] = p.attribValue("pf_name")
got = boxes(mv.geometry(1), "pf_name")
want = sorted(in_cell[k] for k in MARKED)
run("string enum, original scale", [] if sorted(got) == want else ["got %s want %s" % (sorted(got), want)])

geo.destroy()

if MUT:
    sys.exit(1 if fails else 0)

# every mutation must turn exactly its paired check(s) red; a FAIL elsewhere does not count
os.makedirs("F:/cache/pf_mesh_view_checks", exist_ok=True)
for name, spec in list(SECTION_MUTATIONS.items()) + list(NODE_MUTATIONS.items()):
    tmpdir = tempfile.mkdtemp(dir="F:/cache/pf_mesh_view_checks")
    try:
        r = subprocess.run([sys.executable, os.path.abspath(__file__)], capture_output=True, text=True,
                           env=dict(os.environ, PF_MESH_VIEW_MUTATE=name, PF_MESH_VIEW_TMP=tmpdir))
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)
    hit = [l.split(" FAIL")[0].strip() for l in r.stdout.splitlines() if " FAIL" in l]
    missed = [c for c in spec[-1] if c not in hit]
    red = r.returncode != 0 and not missed
    fails += not red
    print("mutation %-19s %s paired %s; failed %s%s" % (
        name, "red, as it must:" if red else "NOT RED on its pair:", spec[-1], hit,
        "" if red else " " + r.stderr[-300:]))
sys.exit(1 if fails else 0)
