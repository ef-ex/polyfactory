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
The viewer state's module runs with a stand-in viewer, drawable and template and with
made-up events (press/release/Picked, drags, Alt/Ctrl, a moved and rotated object, a node
that fails while marking); with Highlight Marked off (the default) a click must not
re-cook `mark`.
Cannot see: what a real viewport sends (event order of a real click, Space/Alt view
navigation, whether Houdini calls onNodeChangeEvent/onDraw and draws a closed polygon as an
outline: needs the GUI), whether a consumed click (return True) matters to the viewer, the
prompt after Esc, the outlines' height (only X/Z centres are compared), the Clear button; a detail Cd on the input (the highlight's prim-Cd default from it is unexercised);
points shared between pieces (each box here owns its points); `_*` groups on the outputs
(attributes only).
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
SECTION_MUTATIONS = {  # name -> (section, old, new, checks that must FAIL)
    "piece_at_x": ("PythonModule", "(pos[0] + 0.5)", "(pos[0])", ["pick columns=0", "pick columns=4"]),
    "piece_at_row": ("PythonModule", "pos[2] / 3.0", "pos[2] / 2.5", ["pick columns=4"]),
    "toggle": ("PythonModule", "^ {piece}", "| {piece}", ["toggle 5,12,5,20 -> '12 20'"]),
    "py_parse": ("PythonModule", '.replace(",", " ").split()', '.replace(",", " ").split(" ")',
                 ["parse: mark == hm().marked()"]),
    "state_release": ("ViewerStateModule", "press, self.press = self.press, None", "press = self.press",
                      ["state: press, Picked, release toggles once"]),
    "state_slop": ("ViewerStateModule", "> SLOP:", "> 10 ** 6:", ["state: a drag does not toggle"]),
    "state_stale_press": ("ViewerStateModule", "if reason == hou.uiEventReason.Changed:\n            if press is None:",
                          "if press is not None:\n            if press is None:",
                          ["state: a Picked after a stray press toggles"]),
    "state_bind": ("ViewerStateModule", 'bindNodeParmChangeEvent(["marked", "columns"])',
                   'bindNodeParmChangeEvent(["columns"])', ["state: outlines follow typed marks"]),
    "state_click_refresh": ("ViewerStateModule", "toggle(node, piece)\n        self.refresh()",
                            "toggle(node, piece)", ["state: outlines follow a click"]),
    "state_enter_refresh": ("ViewerStateModule", "        self.refresh()\n        self.scene_viewer.setPromptMessage(PROMPT)\n\n    def onExit",
                            "        self.scene_viewer.setPromptMessage(PROMPT)\n\n    def onExit", ["state: outlines of earlier marks on Enter"]),
    "state_show": ("ViewerStateModule", "self.guide.show(True)", "self.guide.show(False)", ["state: outlines on Enter"]),
    "state_miss": ("ViewerStateModule", "if hit < 0:\n            return False", "if False:\n            return False",
                   ["state: a click on empty space marks nothing"]),
    "state_ray_dir": ("ViewerStateModule", "direction = far - origin", "direction = direction",
                      ["state: five clicks mark five pieces"]),
    "state_guide_xform": ("ViewerStateModule", "self.guide.setTransform(obj.worldTransform() if",
                          "self.guide.setTransform(hou.hmath.identityTransform() if", ["state: outlines in world space"]),
    "state_draw": ("ViewerStateModule", "    def onDraw(self, kwargs):\n        self.guide.draw(",
                   "    def onDraw(self, kwargs):\n        pass  # (", ["state: onDraw draws the outlines"]),
    "state_invalid_geo": ("ViewerStateModule", "except (hou.InvalidGeometry, hou.GeometryPermissionError):",
                          "except ZeroDivisionError:", ["state: failed cook while marking, no error"]),
    "highlight_default": ("DialogScript", 'label   "Highlight Marked"\n        type    toggle\n        default { "0" }',
                          'label   "Highlight Marked"\n        type    toggle\n        default { "1" }',
                          ["Highlight Marked is off on a new node"]),
    "state_alt": ("ViewerStateModule", "if dev.isAltKey() or dev.isCtrlKey():", "if False:",
                  ["state: Alt or Ctrl click does not toggle"]),
    "state_no_geo": ("ViewerStateModule", "if self.geo is None:  # the last cook", "if False:  # the last cook",
                     ["state: no geometry, no error"]),
    "state_one_geo": ("ViewerStateModule", "if self.geo is None:\n            self.geo = node.geometry()",
                      "if True:\n            self.geo = node.geometry()", ["state: one geometry reference"]),
    "state_guide": ("ViewerStateModule", "for k in node.hm().marked(node):", "for k in node.hm().marked(node)[1:]:",
                    ["state: one outline per marked piece"]),
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
    "leak0_plain": ("scratch_delete_view", "primdel", "_*", "", ["leak, output 0, highlight off"]),
    "click_cooks": ("highlight_switch", "input", 0, 1, ["click does not re-cook the view"]),
    "leak1": ("scratch_delete_marked", "dtldel", "_*", "", ["leak, Marked laid out"]),
}
if MUT in SECTION_MUTATIONS:
    tmp = os.path.join(os.environ["PF_MESH_VIEW_TMP"], "pf_mesh_view.hda")
    shutil.copy(HDA, tmp)
    HDA = tmp
hou.hda.installFile(HDA)
if MUT in SECTION_MUTATIONS:
    _name, _old, _new, _ = SECTION_MUTATIONS[MUT]
    _sec = hou.hda.definitionsInFile(HDA)[0].sections()[_name]
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
        _w.parm(_p).deleteAllKeyframes()      # an expression parm takes the value
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

# ---------------------------------------------------------------- the viewer state
# Its module runs here with a stand-in viewer and drawable (hython has no viewport); the
# events carry what Houdini sends: reason, mouse position, modifier keys, a world-space ray.
# The object is moved so the world -> object ray transform is exercised.
class _Viewer(object):
    prompt = None

    def setPromptMessage(self, msg, kind=None):
        self.prompt = msg

    def clearPromptMessage(self):
        self.prompt = None

    def curViewport(self):
        return self

    def draw(self):
        pass


class _Drawable(object):
    geo = xform = None
    draws = 0
    shown = False

    def __init__(self, *args, **kwargs):
        pass

    def draw(self, handle):
        self.draws += 1

    def show(self, on):
        self.shown = on

    def setGeometry(self, g):
        self.geo = g

    def setTransform(self, m):
        self.xform = m


class _Template(object):                  # records what the state binds (hython has no viewer)
    def __init__(self, *args):
        self.binds = {}

    def __getattr__(self, name):
        return lambda *a, **k: self.binds.setdefault(name, a)


class _Hou(object):                       # hou, with the drawable and template swapped for stand-ins
    GeometryDrawable = _Drawable
    ViewerStateTemplate = _Template

    def __getattr__(self, name):
        return getattr(hou, name)


class _Dev(object):
    def __init__(self, x, alt, ctrl=False):
        self.x, self.alt, self.ctrl = x, alt, ctrl

    def mouseX(self):
        return self.x

    def mouseY(self):
        return 100

    def isAltKey(self):
        return self.alt

    def isCtrlKey(self):
        return self.ctrl


class _Event(object):
    """reason at screen x over piece k: the ray comes straight down (in the object's space)
    onto its cell's centre, given in world space as a viewer gives it; up=True points it away."""
    def __init__(self, reason, x, k, alt=False, ctrl=False, up=False):
        self.r, self.d = reason, _Dev(x, alt, ctrl)
        cols = mv.evalParm("columns")
        col, row = (k % cols, k // cols) if cols else (k, 0)
        w = geo.worldTransform()
        self.origin = hou.Vector3(2 * col + 0.5, 50, 3 * row + 0.5) * w
        self.dir = hou.Vector3(2 * col + 0.5, 51 if up else 49, 3 * row + 0.5) * w - self.origin

    def reason(self):
        return self.r

    def device(self):
        return self.d

    def ray(self):
        return self.origin, self.dir


class _NoGeo(object):                     # the view after an interrupted cook
    def __getattr__(self, name):
        return getattr(mv, name)

    def geometry(self):
        return None


_ns = {"kwargs": {}}
exec(compile(mv.type().definition().sections()["ViewerStateModule"].contents(), "ViewerStateModule", "exec"), _ns)
_ns["hou"] = _Hou()
R = hou.uiEventReason
geo.parmTuple("t").set((5, 0, -3))
geo.parmTuple("r").set((30, 40, 10))
mv.parm("columns").set(4)
mv.parm("marked").set("1 3")
st = _ns["State"]("pf::mesh_view::1.0.0", _Viewer())
st.onEnter({"node": mv})
run("state: outlines on Enter", [] if st.guide.shown else ["hidden"])
n_out = len(st.guide.geo.prims()) if st.guide.geo else 0
run("state: outlines of earlier marks on Enter", [] if n_out == 2 else ["%d outlines for 2 marks" % n_out])


def events(*evs):
    for e in evs:
        st.onMouseEvent({"ui_event": e})
    return mv.evalParm("marked")


def click(k, x=10, alt=False, ctrl=False):
    return events(_Event(R.Start, x, k, alt, ctrl), _Event(R.Changed, x + 1, k, alt, ctrl))


mv.parm("marked").set("")
for k in (1, 6, 9, 14, 22):
    click(k)
run("state: five clicks mark five pieces", [] if mv.evalParm("marked") == "1 6 9 14 22" else [mv.evalParm("marked")])

mv.parm("marked").set("")
bad = []
got = events(_Event(R.Start, 10, 3), _Event(R.Picked, 10, 3), _Event(R.Changed, 10, 3))
bad += [] if got == "3" else ["press, Picked, release -> %r" % got]
got = events(_Event(R.Picked, 10, 3))
bad += [] if got == "" else ["Picked alone -> %r" % got]
run("state: press, Picked, release toggles once", bad)

mv.parm("marked").set("")
got = events(_Event(R.Start, 10, 3), _Event(R.Active, 30, 3), _Event(R.Changed, 40, 3))
run("state: a drag does not toggle", [] if got == "" else [got])
got = events(_Event(R.Picked, 10, 3, up=True))
run("state: a click on empty space marks nothing", [] if got == "" else [got])
bad = [] if click(3, alt=True) == "" else ["Alt -> %r" % mv.evalParm("marked")]
bad += [] if click(3, ctrl=True) == "" else ["Ctrl -> %r" % mv.evalParm("marked")]
run("state: Alt or Ctrl click does not toggle", bad)
got = events(_Event(R.Start, 10, 3, alt=True), _Event(R.Picked, 400, 6))
run("state: a Picked after a stray press toggles", [] if got == "6" else [got])
mv.parm("marked").set("")

_ns["kwargs"] = {"type": mv.type()}
tpl = _ns["createViewerStateTemplate"]()
run("state: outlines follow typed marks", [] if "marked" in tpl.binds.get("bindNodeParmChangeEvent", [[]])[0]
    else ["binds %s" % tpl.binds])
click(8)
n_out = len(st.guide.geo.prims()) if st.guide.geo else 0
run("state: outlines follow a click", [] if n_out == 1 else ["%d outlines after one click" % n_out])
run("state: outlines in world space", [] if st.guide.xform == geo.worldTransform() else ["transform %s" % st.guide.xform])
d0 = st.guide.draws
st.onDraw({"draw_handle": None})
st.onDrawInterrupt({"draw_handle": None})
run("state: onDraw draws the outlines", [] if st.guide.draws == d0 + 2 else ["%d draws of 2" % (st.guide.draws - d0)])
mv.parm("marked").set("")

g0 = st.geo
click(4)
run("state: one geometry reference", [] if g0 is not None and st.geo is g0 else ["new reference per click"])

mv.parm("marked").set("2 5 7")
st.onNodeChangeEvent({"node": mv})
bad = []
polys = st.guide.geo.prims() if st.guide.geo else []
centres_ = sorted((round(c[0], 4), round(c[2], 4)) for c in (centroid(p) for p in polys))
want = sorted((2.0 * (k % 4) + 0.5, 3.0 * (k // 4) + 0.5) for k in (2, 5, 7))
run("state: one outline per marked piece", [] if centres_ == want else ["outlines at %s want %s" % (centres_, want)])

st2 = _ns["State"]("pf::mesh_view::1.0.0", _Viewer())
st2.onEnter({"node": _NoGeo()})
try:
    out = st2.onMouseEvent({"ui_event": _Event(R.Picked, 10, 3)})
    bad = [] if out is False and "no geometry" in st2.scene_viewer.prompt else ["returned %r, prompt %r" % (out, st2.scene_viewer.prompt)]
except Exception as e:
    bad = ["%s: %s" % (type(e).__name__, e)]
run("state: no geometry, no error", bad)

# the held reference goes bad when the node fails later (Esc during a cook, a broken input)
broken = geo.createNode("attribwrangle")
broken.parm("snippet").set("not vex;")
mv.parm("marked").set("")
click(2)
mv.setInput(0, broken)
try:
    out = st.onMouseEvent({"ui_event": _Event(R.Picked, 10, 3)})
    bad = [] if out is False and "no geometry" in st.scene_viewer.prompt else ["returned %r, prompt %r" % (out, st.scene_viewer.prompt)]
except Exception as e:
    bad = ["%s: %s" % (type(e).__name__, e)]
mv.setInput(0, mk)
bad += [] if click(5) == "2 5" else ["after the input is fixed: %r" % mv.evalParm("marked")]
run("state: failed cook while marking, no error", bad)
broken.destroy()
geo.parmTuple("r").set((0, 0, 0))
geo.parmTuple("t").set((0, 0, 0))

fresh = geo.createNode("pf::mesh_view::1.0.0")
run("Highlight Marked is off on a new node", [] if fresh.evalParm("highlight") == 0 else ["on"])
fresh.destroy()

# a click must not re-cook the view while Highlight Marked is off (its default): on a big kit
# `mark` + `highlight` took 3.7 s per click; the state shows the marks itself
mv.parm("highlight").set(0)
mv.geometry()
watch = ("mark", "foreach_end2", "scratch_delete_view", "highlight_switch")
before = [mv.node(w).cookCount() for w in watch]
mv.parm("marked").set("1 2")
mv.geometry()
run("click does not re-cook the view", ["%s re-cooked" % w for w, b in zip(watch, before) if mv.node(w).cookCount() != b])

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
run("leak, output 0, highlight off", leaks(mv.geometry()))
mv.parm("highlight").set(1)
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
