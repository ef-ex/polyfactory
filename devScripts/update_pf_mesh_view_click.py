"""Makes marking in the SHIPPED pf::mesh_view usable on big kits (edits it in place).

    hython devScripts/update_pf_mesh_view_click.py

Hannes, 2026-11-01, on an 8.4M-prim kit: only the first click marked, Esc raised
"'NoneType' object has no attribute 'intersect'", the view froze. Cause: every click
re-cooked `mark` + `highlight` over all prims (3.7 s) and rebuilt the ray-hit structure
(0.45 s); Esc during that cook interrupted it, so node.geometry() was None.
Now: a click does not re-cook the view (Highlight Marked off by default and switched out of
output 0 when off); the state draws the marks as orange outlines itself; the state keeps one
geometry reference; a click is press + release within a few pixels (not only Houdini's
quick "Picked"); Alt/Ctrl clicks and drags are left alone; no geometry -> a message, not an error.
Run once on the asset as it was at 11e5d5a; it refuses to run twice.
"""
import os

import hou

HDA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "polyfactory", "otls", "pf_mesh_view.hda").replace("\\", "/")

VIEWER_STATE = '''"""Mark pieces: click a piece of the PF Mesh View to mark or unmark it."""
import hou

PROMPT = ("Click a piece to mark or unmark it | Space or Alt + mouse: move the view | "
          "Esc: leave marking")
SLOP = 4  # pixels the mouse may move between press and release and still count as a click


class State(object):
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        self.node = None
        self.geo = None      # one live reference: Houdini builds its ray-hit structure once
        self.press = None    # mouse position at the left-button press
        self.guide = None

    def onEnter(self, kwargs):
        self.node = kwargs["node"]
        self.guide = hou.GeometryDrawable(self.scene_viewer, hou.drawableGeometryType.Line,
                                          "pf_mesh_view_marks", params={
                                              "color1": (1.0, 0.45, 0.0, 1.0), "line_width": 3.0})
        self.guide.show(True)
        self.refresh()
        self.scene_viewer.setPromptMessage(PROMPT)

    def onExit(self, kwargs):
        self.scene_viewer.clearPromptMessage()

    def onResume(self, kwargs):
        self.press = None
        self.scene_viewer.setPromptMessage(PROMPT)

    def onInterrupt(self, kwargs):
        self.press = None

    def onNodeChangeEvent(self, kwargs):
        self.refresh()

    def onDraw(self, kwargs):
        self.guide.draw(kwargs["draw_handle"])

    def onDrawInterrupt(self, kwargs):
        self.guide.draw(kwargs["draw_handle"])

    def refresh(self):
        """Orange outline around the cell of every marked piece, in world space."""
        node = self.node
        g = hou.Geometry()
        cols = node.evalParm("columns")
        for k in node.hm().marked(node):
            col, row = (k % cols, k // cols) if cols > 0 else (k, 0)
            x, z = 2.0 * col, 3.0 * row
            pts = g.createPoints([(x - 0.15, 0, z - 0.15), (x + 1.15, 0, z - 0.15),
                                  (x + 1.15, 0, z + 1.15), (x - 0.15, 0, z + 1.15)])
            poly = g.createPolygon()
            for p in pts:
                poly.addVertex(p)
        self.guide.setGeometry(g)
        obj = node.parent()
        while obj is not None and not isinstance(obj, hou.ObjNode):
            obj = obj.parent()
        self.guide.setTransform(obj.worldTransform() if obj is not None else hou.hmath.identityTransform())
        self.scene_viewer.curViewport().draw()

    def onMouseEvent(self, kwargs):
        ui_event = kwargs["ui_event"]
        dev = ui_event.device()
        reason = ui_event.reason()
        if reason == hou.uiEventReason.Start:
            self.press = (dev.mouseX(), dev.mouseY())
            return False
        if reason not in (hou.uiEventReason.Picked, hou.uiEventReason.Changed):
            return False
        press, self.press = self.press, None
        if reason == hou.uiEventReason.Changed:
            if press is None:
                return False     # the release of a press already handled as a Picked, or never seen
            if abs(dev.mouseX() - press[0]) + abs(dev.mouseY() - press[1]) > SLOP:
                return False     # a drag, not a click
        if dev.isAltKey() or dev.isCtrlKey():
            return False
        return self.click(ui_event)

    def click(self, ui_event):
        node = self.node
        if self.geo is None:
            self.geo = node.geometry()
        if self.geo is None:  # the last cook failed or was interrupted
            self.scene_viewer.setPromptMessage(
                "PF Mesh View has no geometry: its last cook failed or was interrupted | " + PROMPT,
                hou.promptMessageType.Warning)
            return False
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
        try:
            hit = self.geo.intersect(origin, direction, pos, nml, uvw)
        except (hou.InvalidGeometry, hou.GeometryPermissionError):
            self.geo = None      # the node's cook failed or was interrupted since: fetch again next time
            self.scene_viewer.setPromptMessage(
                "PF Mesh View has no geometry: its last cook failed or was interrupted | " + PROMPT,
                hou.promptMessageType.Warning)
            return False
        if hit < 0:
            return False
        piece = node.hm().piece_at(node, pos)
        if piece < 0:
            return False
        node.hm().toggle(node, piece)
        self.refresh()
        self.scene_viewer.setPromptMessage(PROMPT)
        return True


def createViewerStateTemplate():
    name = kwargs["type"].definition().sections()["DefaultState"].contents()
    t = hou.ViewerStateTemplate(name, "Mark Pieces", hou.sopNodeTypeCategory())
    t.bindFactory(State)
    t.bindNodeParmChangeEvent(["marked", "columns"])  # typing, Clear Marks, undo: outlines follow
    t.bindIcon(kwargs["type"].icon())
    return t
'''

hou.hda.installFile(HDA)
d = hou.nodeType(hou.sopNodeTypeCategory(), "pf::mesh_view::1.0.0").definition()
assert d.libraryFilePath() == HDA, d.libraryFilePath()
assert "self.press" not in d.sections()["ViewerStateModule"].contents(), "already updated; refusing to run twice"

# --- Highlight Marked: off by default (the state shows the marks without a re-cook)
ptg = d.parmTemplateGroup()
hl = ptg.find("highlight")
hl.setDefaultValue(False)
hl.setHelp("Also colours the marked pieces orange in the geometry. Every click then re-cooks "
           "the whole view, which takes seconds on a big kit; while marking, the outlines show the marks.")
ptg.replace("highlight", hl)
d.setParmTemplateGroup(ptg)

# --- output 0: Highlight off takes the loop's result straight, so a click does not re-cook it
geo = hou.node("/obj").createNode("geo", "_build_mesh_view")
n = geo.createNode("pf::mesh_view::1.0.0")
n.allowEditingOfContents()
c = n.node
plain = n.createNode("attribdelete", "scratch_delete_view")
for p in ("ptdel", "vtxdel", "primdel", "dtldel"):
    plain.parm(p).set("_*")
plain.setInput(0, c("foreach_end2"))
sw = n.createNode("switch", "highlight_switch")
sw.setInput(0, plain)
sw.setInput(1, c("scratch_delete"))
sw.parm("input").setExpression('ch("../highlight")')
c("output0").setInput(0, sw)
n.layoutChildren()
d.updateFromNode(n)
geo.destroy()

# --- sections
d = hou.hda.definitionsInFile(HDA)[0]
d.sections()["ViewerStateModule"].setContents(VIEWER_STATE)
hlp = d.sections()["Help"].contents()
old_marked = ("Click a piece in the viewport to add or remove it (press Enter in the viewport with "
              "this node selected to start clicking), or type the numbers.")
old_hl = "Colours the marked pieces orange in the view."
assert old_marked in hlp and old_hl in hlp
hlp = hlp.replace(old_marked, "Click a piece in the viewport to add or remove it, or type the numbers. To start "
                  "clicking, select this node, move the mouse into the viewport and press Enter; the marked "
                  "pieces get an orange outline. Move the view with Space or Alt + mouse. Esc leaves marking. While "
                  "marking, keep the display flag on this node: a node after the Marked output re-cooks on every click.")
hlp = hlp.replace(old_hl, hl.help())
d.sections()["Help"].setContents(hlp)

back = hou.hda.definitionsInFile(HDA)[0]
assert "self.press" in back.sections()["ViewerStateModule"].contents()
assert back.parmTemplateGroup().find("highlight").defaultValue() == False
print("wrote " + HDA)
