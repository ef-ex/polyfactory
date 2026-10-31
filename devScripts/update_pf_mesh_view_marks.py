"""Adds piece marking to the SHIPPED pf::mesh_view asset (edits it in place).

    hython devScripts/update_pf_mesh_view_marks.py

Click a piece in the viewport (the node's viewer state, Enter in the viewport) to put
its number in the `marked` list or take it out; the second output carries only the
marked pieces, laid out as in the view or (`original_scale`) exactly as they came in.
Run once on the asset as it was at 0a3f9b6; it refuses to run twice.
"""
import os

import hou

HDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "polyfactory", "otls", "pf_mesh_view.hda").replace("\\", "/")

# loop 1 (appended to attribwrangle2, detail class): only the piece number. The marks are read
# after the loop, so a click never re-cooks the per-piece loop. Labels get -1 (merge default).
PIECE_VEX = """// this piece's number (the loop iteration, shown on its label); the marks are read after the loop
addprimattrib(0, "_piece", -1);
int piece = detail(1, "iteration", 0);
for (int i = 0; i < nprimitives(0); i++)
    setprimattrib(0, "_piece", i, piece);
"""

# after the loop, detail class (one execution over all prims): parse the list once, flag the
# marked pieces. Same parse as the PythonModule's marked(): commas or whitespace between,
# only whole numbers count, compared as integers ("03" is 3).
MARK_VEX = """int want[];
foreach (string s; split(re_replace(",", " ", chs("../marked"))))
    if (re_match("^[0-9]+$", s))
        append(want, atoi(s, 10));
addprimattrib(0, "_mark", 0);
for (int i = 0; i < nprimitives(0); i++) {
    int piece = prim(0, "_piece", i);
    setprimattrib(0, "_mark", i, piece >= 0 && find(want, piece) >= 0);
}
"""

# output 0 only, detail class: marked pieces orange, on the class Cd already lives on so an
# existing vertex/point Cd cannot hide it; a new prim Cd starts at the detail Cd (or white)
HIGHLIGHT_VEX = """if (chi("../highlight") && findattribvalcount(0, "primitive", "_mark", 1) > 0) {
    vector orange = {1, 0.45, 0};
    int vtx = hasvertexattrib(0, "Cd");
    int pt = haspointattrib(0, "Cd");
    if (!vtx && !pt) {
        vector base = {1, 1, 1};
        if (hasdetailattrib(0, "Cd"))
            base = detail(0, "Cd");
        addprimattrib(0, "Cd", base);
    }
    for (int i = 0; i < nprimitives(0); i++) {
        int on = prim(0, "_mark", i);
        if (!on)
            continue;
        if (vtx)
            foreach (int v; primvertices(0, i))
                setvertexattrib(0, "Cd", -1, v, orange);
        else if (pt)
            foreach (int p; primpoints(0, i))
                setpointattrib(0, "Cd", p, orange);
        else
            setprimattrib(0, "Cd", i, orange);
    }
}
"""

DROP_VEX = "// labels and unmarked pieces go\nif (!i@_mark)\n    removeprim(0, @primnum, 1);\n"

# the untouched input, once over all prims: keep the pieces whose enum value survived DROP_VEX.
# The input may carry the enum on points (attribpromote6 moves it to prims for the loop), so
# read it where it is: from the prim, else from the prim's first point.
KEEP_VEX = """// keep a prim when a marked piece (input 1, enum on prims) carries its enum value
string a = chs("../enum_attr");
string cls = hasprimattrib(0, a) ? "primitive" : "point";
int e = cls == "primitive" ? @primnum : primpoint(0, @primnum, 0);
int keep;
if (attribtype(0, cls, a) == 2) {
    string v = attrib(0, cls, a, e);
    keep = findattribval(1, "primitive", a, v) >= 0;
} else {
    int v = attrib(0, cls, a, e);
    keep = findattribval(1, "primitive", a, v) >= 0;
}
if (!keep)
    removeprim(0, @primnum, 1);
"""

PYTHON_MODULE = '''"""pf::mesh_view: which piece sits where, and the Marked Pieces list."""
import math

import hou


def piece_at(node, pos):
    """Number of the piece whose cell holds layout position pos, or -1.

    Cells follow transform1: pitch 2 in X, 3 in Z; a piece fills x 0..1, z 0..1 of its cell
    and its label sits at z ~2, so X is split halfway between pieces (x + 0.5) and Z per row.
    """
    col = int(math.floor((pos[0] + 0.5) / 2.0))
    row = int(math.floor(pos[2] / 3.0))
    cols = node.evalParm("columns")
    if col < 0 or row < 0 or (cols > 0 and col >= cols) or (cols == 0 and row > 0):
        return -1
    return row * cols + col if cols > 0 else col


def marked(node):
    """The Marked Pieces list as ints, parsed like the `mark` wrangle: commas or whitespace
    between, only whole numbers ([0-9]+) count."""
    return sorted({int(s) for s in node.evalParm("marked").replace(",", " ").split()
                   if s.isascii() and s.isdigit()})


def toggle(node, piece):
    """Puts piece in the Marked Pieces list, or takes it out if it is there."""
    m = set(marked(node)) ^ {piece}
    with hou.undos.group("Mark piece %d" % piece):
        node.parm("marked").set(" ".join(str(i) for i in sorted(m)))
'''

VIEWER_STATE = '''"""Mark pieces: click a piece of the PF Mesh View to mark or unmark it."""
import hou

PROMPT = "Click a piece to mark or unmark it (its number goes into Marked Pieces) | Esc: exit"


class State(object):
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer

    def onEnter(self, kwargs):
        self.scene_viewer.setPromptMessage(PROMPT)

    def onExit(self, kwargs):
        self.scene_viewer.clearPromptMessage()

    def onMouseEvent(self, kwargs):
        ui_event = kwargs["ui_event"]
        if ui_event.reason() != hou.uiEventReason.Picked:
            return False
        node = kwargs["node"]
        origin, direction = ui_event.ray()
        obj = node.parent()
        while obj is not None and not isinstance(obj, hou.ObjNode):
            obj = obj.parent()
        if obj is not None:  # the ray is in world space, the geometry in the object's space
            inv = obj.worldTransform().inverted()
            far = (origin + direction) * inv
            origin = origin * inv
            direction = far - origin
        pos, nml, uvw = hou.Vector3(), hou.Vector3(), hou.Vector3()
        if node.geometry().intersect(origin, direction, pos, nml, uvw) < 0:
            return False
        piece = node.hm().piece_at(node, pos)
        if piece < 0:
            return False
        node.hm().toggle(node, piece)
        return True


def createViewerStateTemplate():
    name = kwargs["type"].definition().sections()["DefaultState"].contents()
    t = hou.ViewerStateTemplate(name, "Mark Pieces", hou.sopNodeTypeCategory())
    t.bindFactory(State)
    t.bindIcon(kwargs["type"].icon())
    return t
'''

HELP_PARMS = """    Marked Pieces:
        #id: marked
        Numbers of the marked pieces, as on their labels, separated by spaces. Click a piece in the viewport to add or remove it (press Enter in the viewport with this node selected to start clicking), or type the numbers.
    Clear Marks:
        #id: clear_marks
        Empties the Marked Pieces list.
    Highlight Marked:
        #id: highlight
        Colours the marked pieces orange in the view.
    Original Scale:
        #id: original_scale
        The Marked output gives the marked pieces exactly as they came in (original size and position) instead of as laid out in the view.

@outputs
    Mesh View:
        All pieces laid out in a grid with their numbers.
    Marked:
        Only the marked pieces, without labels.
"""

hou.hda.installFile(HDA)
d = hou.nodeType(hou.sopNodeTypeCategory(), "pf::mesh_view::1.0.0").definition()
assert d.libraryFilePath() == HDA, d.libraryFilePath()
assert "ViewerStateModule" not in d.sections(), "already has marking; refusing to run twice"

# --- parameters
ptg = d.parmTemplateGroup()
ptg.append(hou.StringParmTemplate(
    "marked", "Marked Pieces", 1,
    help="Numbers of the marked pieces, as on their labels. Click a piece in the viewport to add or remove it."))
ptg.append(hou.ButtonParmTemplate(
    "clear_marks", "Clear Marks", script_callback="kwargs['node'].parm('marked').set('')",
    script_callback_language=hou.scriptLanguage.Python, help="Empties the Marked Pieces list."))
ptg.append(hou.ToggleParmTemplate("highlight", "Highlight Marked", default_value=True,
                                  help="Colours the marked pieces orange in the view."))
ptg.append(hou.ToggleParmTemplate(
    "original_scale", "Original Scale", default_value=False,
    help="The Marked output gives the marked pieces exactly as they came in instead of as laid out."))
d.setParmTemplateGroup(ptg)
d.setMaxNumOutputs(2)

# --- network
geo = hou.node("/obj").createNode("geo", "_build_mesh_view")
n = geo.createNode("pf::mesh_view::1.0.0")
n.allowEditingOfContents()
c = n.node


def wrangle(name, cls, snippet, *inputs):
    w = n.createNode("attribwrangle", name)
    w.parm("class").set(cls)
    w.parm("snippet").set(snippet)
    for i, src in enumerate(inputs):
        w.setInput(i, src)
    return w


# the piece number rides in the loop's existing per-piece wrangle: no extra per-piece cook
w2 = c("attribwrangle2")
w2.setInput(1, c("foreach_begin2_metadata1"))
w2.parm("snippet").set(w2.parm("snippet").eval().rstrip("\n") + "\n\n" + PIECE_VEX)

# after the loop: mark -> highlight -> scratch_delete -> output0, and mark -> drop -> Marked
mark = wrangle("mark", 0, MARK_VEX, c("foreach_end2"))
hl = wrangle("highlight", 0, HIGHLIGHT_VEX, mark)
c("scratch_delete").setInput(0, hl)
drop = wrangle("drop_unmarked", 1, DROP_VEX, mark)
clean2 = n.createNode("attribdelete", "scratch_delete_marked")
for p in ("ptdel", "vtxdel", "primdel", "dtldel"):
    clean2.parm(p).set("_*")
clean2.setInput(0, drop)
keep = wrangle("keep_marked", 1, KEEP_VEX, n.indirectInputs()[0], drop)

sw = n.createNode("switch", "marked_scale")
sw.setInput(0, clean2)
sw.setInput(1, keep)
sw.parm("input").setExpression('ch("../original_scale")')
out1 = n.createNode("output", "output1")
out1.parm("outputidx").set(1)
out1.setInput(0, sw)
n.layoutChildren()
d.updateFromNode(n)
geo.destroy()

# --- sections: click-to-mark state, helpers, help, output labels
d = hou.hda.definitionsInFile(HDA)[0]
name = d.nodeTypeName()
d.addSection("PythonModule", PYTHON_MODULE)
d.setExtraFileOption("PythonModule/IsPython", True)
d.setExtraFileOption("PythonModule/IsScript", True)
d.addSection("DefaultState", name)
d.addSection("ViewerStateName.orig", name)
d.addSection("ViewerStateModule", VIEWER_STATE)
d.addSection("ViewerStateInstall", "__import__('viewerstate.utils', fromlist=[None])"
                                   ".register_pystate_embedded(kwargs['type'])")
d.addSection("ViewerStateUninstall", "__import__('viewerstate.utils', fromlist=[None])"
                                     ".unregister_pystate_embedded(kwargs['type'])")
for sec in ("ViewerStateInstall", "ViewerStateUninstall", "ViewerStateModule", "ViewerStateName.orig"):
    d.setExtraFileOption(sec + "/IsPython", True)
    d.setExtraFileOption(sec + "/IsScript", True)
for sec in ("ViewerStateInstall", "ViewerStateUninstall", "ViewerStateModule"):
    d.setExtraFileOption(sec + "/IsViewerState", True)

hlp = d.sections()["Help"].contents().rstrip("\n") + "\n" + HELP_PARMS
hlp = hlp.replace("so you can look through a whole kit at once.",
                  "so you can look through a whole kit at once. Click pieces to mark them; "
                  "the second output carries only the marked ones.")
d.sections()["Help"].setContents(hlp)

ds = d.sections()["DialogScript"]
txt = ds.contents()
if "outputlabel" not in txt:
    txt = txt.replace('    inputlabel\t4\t"Sub-Network Input #4"\n',
                      '    inputlabel\t4\t"Sub-Network Input #4"\n'
                      '    outputlabel\t1\t"Mesh View"\n    outputlabel\t2\t"Marked"\n')
    ds.setContents(txt)

back = hou.hda.definitionsInFile(HDA)[0]
assert back.sections()["DefaultState"].contents() == back.nodeTypeName()
assert back.maxNumOutputs() == 2
print("wrote " + HDA)
