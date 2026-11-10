"""GUI checks of the modelUI Modify panel (F2c: stack_panel.py over stack.py), run INSIDE a throwaway Houdini.

Start it with:  PF_GUI_SCRIPT=gui_f2c.py PF_F1_SCRATCH=F:/cache/modelui/f2c/gui python tests/modelui/run_gui_f1.py
(own prefs, only this worktree's polyfactory package, every window off screen, exits by itself, never saves a .hip).
Baseline, one run per mutation in MUTATIONS (a source edit exec'd into the live module; the desk switch of each run
rebuilds the panel from the mutated module), baseline again; results to $PF_F1_OUT.

Input: panel buttons and Scene Explorer rows get real clicks (QTest on the widget), viewport picks a real click on the
viewer's window. Not the real path: the Modifier List dropdown (its ``activated`` signal is emitted: an off-screen
popup is not clickable reliably), the on/off check box (``setCheckState``: the indicator's pixel is style-dependent),
the component selection (``setCurrentGeometrySelection``, as Houdini's select state would leave it).
What it cannot see: the look of the panel, a handle DRAG in an entry's state (only that the state is entered),
Houdini's own reselect inside a node state, hip reload, floating panels.
"""
import faulthandler
import glob
import json
import logging
import os
import time
import traceback

import hdefereval
import hou
from hutil.Qt import QtCore, QtWidgets
from PySide6.QtTest import QTest
import shiboken6

from polyfactory.modelui import containers, scene, stack, stack_panel, switch

OUT = os.environ["PF_F1_OUT"]
LOGF = open(OUT + ".log", "w", buffering=1)
FAULTF = open(OUT + ".fault.txt", "w")   # a segfault's Python stack (Houdini writes none for these runs)
faulthandler.enable(FAULTF)
_TRACE = logging.StreamHandler(LOGF)   # the panel's viewer decisions, between the steps
_TRACE.setFormatter(logging.Formatter("      panel: %(message)s"))
logging.getLogger("polyfactory.modelui.stack_panel").addHandler(_TRACE)
logging.getLogger("polyfactory.modelui.stack_panel").setLevel(logging.DEBUG)
Qt = QtCore.Qt
LMB, NOM = Qt.LeftButton, Qt.NoModifier
FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))
STATE = {"desk0": None}
PR = hou.geometryType.Primitives


def log(*a):
    LOGF.write(time.strftime("%H:%M:%S ") + " ".join(str(x) for x in a) + "\n")


def visible_on_screen():
    return [w for w in QtWidgets.QApplication.topLevelWidgets() if w.isVisible() and w.frameGeometry().right() > -5000]


def off_screen():
    mw = hou.qt.mainWindow()
    if mw is None:
        return False
    if mw.geometry().x() > -5000:
        mw.showNormal()
        mw.setGeometry(-12000, 100, 1600, 1000)
    for i, w in enumerate(visible_on_screen()):
        w.move(-9000, 100 + 60 * i)
    return not visible_on_screen()


def viewer():
    sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    mw = hou.qt.mainWindow()
    gl = mw.childAt(mw.mapFromGlobal(sv.qtScreenGeometry().center()))
    return sv, gl


def screen_point(sv, gl, world):
    vp = sv.curViewport()
    v = vp.mapToScreen(hou.Vector3(world))
    h = vp.size()[-1]
    dpr = gl.devicePixelRatioF()
    return gl.mapToGlobal(QtCore.QPoint(int(round(v[0] / dpr)), int(round((h - v[1]) / dpr))))


def panel():
    return getattr(hou.session, "_pf_modelui_stack", None)


def explorer():
    return getattr(hou.session, "_pf_modelui_explorer", None)


def click(w):
    QTest.mouseClick(w, LMB)


def click_row(lst, pid):
    """A real click on the row of ``pid`` in a QListWidget (Explorer or stack)."""
    for i in range(lst.count()):
        it = lst.item(i)
        if it.data(Qt.UserRole) == pid:
            lst.scrollToItem(it)
            QTest.mouseClick(lst.viewport(), LMB, NOM, lst.visualItemRect(it).center())
            return True
    return False


def rows(p):
    return [p.list.item(i).data(Qt.UserRole) for i in range(p.list.count())]


def top_first(obj):
    return [n.sessionId() for n in stack.chain(obj)[::-1]]


def choose(p, key):
    """The Modifier List's choice (its activated signal, see the module doc)."""
    i = p.ops.findData(key)
    p.ops.setCurrentIndex(i)
    p.ops.activated.emit(i)


def labels():
    return list(hou.undos.undoLabels())


def why(tag, p, sv, hull):
    """Diagnosis line per step (the log, not a check)."""
    try:
        log("  %s: pwd %s state %s selected %s rows %s entry %s chain %s objects %s undo %s" % (
            tag, sv.pwd().path(), sv.currentState(), scene.current().selected(), rows(p), p._entry,
            [n.name() for n in stack.chain(hull)], [n.name() for n in hou.node("/obj").children()], labels()[:2]))
    except Exception as e:  # noqa: BLE001
        log("  %s: %s" % (tag, e))


def geos():
    """The geometry objects (not the handle's proxy null, which comes and goes with the piece selection)."""
    return sorted(n.name() for n in hou.node("/obj").children() if n.type().name() == "geo")


def suite(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    # every run starts with an empty undo history: after the enter_recorded mutation run (its viewer moves recorded as
    # "Change Selection") the next run segfaulted twice at the same step
    hou.undos.clear()
    hull = hou.node("/obj").createNode("geo", "hull")
    b = hull.createNode("box", "base")
    ex = hull.createNode("polyextrude::2.0", "ex")
    ex.setFirstInput(b)
    ex.parm("group").set("0")
    ex.parm("dist").set(0.5)
    sd = hull.createNode("subdivide", "sd")
    sd.setFirstInput(ex)
    sd.setDisplayFlag(True)
    sd.setRenderFlag(True)
    other = hou.node("/obj").createNode("geo", "other")
    other.createNode("box").parm("scale").set(2)
    other.parmTuple("t").set((0, 0, 8))
    spine = hou.node("/obj").createNode("geo", "spine")
    spine.createNode("line")
    spine.parmTuple("t").set((0, 0, -8))
    c = containers.create()
    pids = containers.add_pieces(c, [(FILES[3], "wing", hou.hmath.buildTranslate(-8, 0, 0))])
    piece = ("piece", c.sessionId(), pids[0])
    start_geos = geos()
    yield 100
    ok = switch.install()
    yield 1500
    sv, gl = viewer()
    # every state the code asks the viewer for: "geo" would make the next click create an object (mutation
    # wrong_object_state); the objects alone were not reliably there to see when the run ended
    asked = STATE["asked"] = []
    orig_scs = hou.SceneViewer.setCurrentState
    STATE["orig_scs"] = orig_scs

    def recording(self, name, *a, **kw):
        asked.append(name)
        return orig_scs(self, name, *a, **kw)
    hou.SceneViewer.setCurrentState = recording
    sv.setViewportLayout(hou.geometryViewportLayout.Single)
    sv.curViewport().changeType(hou.geometryViewportType.Perspective)
    yield 300
    sv.curViewport().frameAll()
    yield 300
    win = gl.window().windowHandle()
    s = scene.current()
    desk = hou.ui.curDesktop()
    hb, e = panel(), explorer()   # the panel Houdini built in the desk (it keeps it across desk switches)
    STATE["hb"] = hb
    out["panel_in_desk"] = bool(ok) and hb is not None and hb.isVisible() and hb._watching and any(
        isinstance(t, hou.PythonPanel) and t.activeInterface() is not None
        and t.activeInterface().name() == "pf_modelui_stack" for t in desk.paneTabs()) and any(
        getattr(cb, "__self__", None) is hb for cb in sv.eventCallbacks())   # it hears this desk's viewer
    log("  desk panel watching", hb is not None and hb._watching, "on the desk's viewer", hb is not None and hb._sv == sv)
    if hb is None or e is None:
        raise RuntimeError("no Modify panel or Scene Explorer")
    # The checks drive a fresh panel from the live (maybe mutated) module, in a window of its own (kept off screen by
    # the guard): Houdini's panel keeps the class it was built with, and replacing a widget Houdini owns crashed
    # Houdini (two runs, segfault after the swap). The switch hooks reach the fresh one through hou.session.
    hb.close_down()
    p = stack_panel.ModifyPanel()
    hou.session._pf_modelui_stack = p
    STATE["fresh"] = p
    p.resize(420, 900)
    p.move(-9000, 100)   # never on screen, not even until the guard runs
    p.show()
    yield 300
    log("  panel", p, type(p) is stack_panel.ModifyPanel, "visible", p.isVisible(), "desk panel", hb)
    log("  start: pwd", sv.pwd().path(), "state", sv.currentState(), "camera", sv.curViewport().viewTransform().extractTranslates(),
        "selected", s.selected(), "undo", labels()[:3])   # what the previous run left (camera, state)

    # --- follows the selection: Scene Explorer and viewport ---------------------------------------------------------
    click_row(e.list, hull.sessionId())
    yield 300
    out["follows_explorer"] = s.selected() == [hull.sessionId()] and rows(p) == top_first(hull) and len(rows(p)) == 3
    sv.setCurrentState("select")
    yield 200
    g = screen_point(sv, gl, other.worldTransform().extractTranslates())
    QTest.mouseMove(win, win.mapFromGlobal(g))
    QTest.mouseClick(win, LMB, NOM, win.mapFromGlobal(g))
    yield 400
    log("  viewport pick: selected", s.selected(), "rows", rows(p))
    out["follows_viewport_pick"] = s.selected() == [other.sessionId()] and rows(p) == top_first(other)
    log("  step: explorer click hull")
    click_row(e.list, hull.sessionId())
    yield 300
    # an edit in the network editor (by hand there): a node inserted into the chain
    log("  step: network edit")
    n_ = hull.createNode("null", "by_hand")
    n_.setFirstInput(ex)
    sd.setInput(0, n_)
    yield 300
    out["follows_network_edit"] = rows(p) == top_first(hull) and n_.sessionId() in rows(p)
    sd.setInput(0, ex)
    log("  step: network delete")
    n_.destroy()
    yield 300
    out["follows_network_delete"] = rows(p) == top_first(hull) and len(rows(p)) == 3

    # --- a refresh Houdini runs inside our viewer change must not rebuild the list under the row being chosen ----------
    # (2026-11-10: SceneViewer.setPwd ran the panel's timer, list.clear() deleted the clicked item, Houdini segfaulted).
    # setPwd here also runs Qt's events, as Houdini's did; a pending refresh changes a row (a rename). The row is chosen
    # with setSelected, not a click: without the guard a real click kills this Houdini and every later run.
    rows_ = [p.list.item(i) for i in range(p.list.count()) if p.list.item(i).data(Qt.UserRole) == ex.sessionId()]
    if not rows_:   # a broken build (mutation wrong_object_state) lost the row already: judge the stray-object check now,
        out["no_stray_objects"] = geos() == start_geos and "geo" not in asked   # by assertion, instead of dying on the missing row
        log("  row of the entry missing; objects", geos(), "at the start", start_geos)
        return
    row = rows_[0]
    own = "setPwd" in hou.SceneViewer.__dict__
    orig = hou.SceneViewer.setPwd

    def pumping(self, *a, **kw):
        r = orig(self, *a, **kw)
        QtWidgets.QApplication.processEvents()
        return r
    with hou.undos.disabler():
        sd.setName("sd_renamed")
    hou.SceneViewer.setPwd = pumping
    try:
        row.setSelected(True)
        out["no_rebuild_inside_click"] = shiboken6.isValid(row) and sv.pwd() == hull
    finally:
        if own:
            hou.SceneViewer.setPwd = orig
        else:
            del hou.SceneViewer.setPwd
        with hou.undos.disabler():
            sd.setName("sd")
    yield 400
    p.list.clearSelection()
    yield 400

    # --- an entry: its own viewer state inside the object, its parameters, no undo entry ------------------------------
    u0 = labels()
    click_row(p.list, ex.sessionId())
    yield 600
    log("  entry ex: pwd", sv.pwd().path(), "state", sv.currentState(), "selected", s.selected(),
        "parms", p.parms and p.parms.node())
    out["entry_shows_state"] = sv.pwd() == hull and sv.currentState() == "polyextrude::2.0"
    out["entry_shows_parms"] = (p.parms is not None and p.parms.node() == ex and p.parms.isVisible()
                                and p.parms.height() >= 200)   # room to work in, not a sliver under the stack
    log("  parameter editor height", p.parms and p.parms.height(), "panel", p.height())
    out["entry_select_no_undo"] = labels() == u0
    p.grab().save(os.path.join(os.path.dirname(OUT), "panel_%d.png" % len(RESULTS)))   # for a person to look at
    out["inside_keeps_object_shown"] = (rows(p) == top_first(hull) and p.title.text() == "hull" and sv.pwd() == hull
                                        and p._entry == ex.sessionId())   # still inside, with the entry chosen
    p.list.clearSelection()
    yield 400
    out["no_entry_back_to_objects"] = sv.pwd() == hou.node("/obj") and p.parms is None
    click_row(p.list, ex.sessionId())
    yield 400
    own = "setPwd" in hou.SceneViewer.__dict__
    orig = hou.SceneViewer.setPwd

    def dropping(self, *a, **kw):   # Houdini dropped the object selection on the way out in some runs, not all: here
        r = orig(self, *a, **kw)    # every time, so the choice must survive it
        hou.clearAllSelected()
        return r
    hou.SceneViewer.setPwd = dropping
    to_obj = p._to_object_level   # full3 (2026-11-10): Houdini had already taken the viewer out, so setPwd never ran,

    def dropping_out(sv_):        # nothing was dropped and mutation leave_reselects_old stayed green: drop it here too,
        before = (sv_.pwd(), sv_.currentState())   # but only when the viewer really moved (_settle calls this every
        to_obj(sv_)                                # refresh and a no-op does not touch Houdini's selection)
        if (sv_.pwd(), sv_.currentState()) != before:
            hou.clearAllSelected()
    p._to_object_level = dropping_out
    try:
        click_row(e.list, other.sessionId())
        yield 400
    finally:
        del p._to_object_level
        if own:
            hou.SceneViewer.setPwd = orig
        else:
            del hou.SceneViewer.setPwd
    log("  other object: pwd", sv.pwd().path(), "state", sv.currentState(), "rows", rows(p))
    shown = (sv.pwd() == hou.node("/obj") and rows(p) == top_first(other) and sv.currentState() in stack_panel.OBJ_STATES
             and s.selected() == [other.sessionId()])   # the choice stays (setPwd drops the selection on the way out)
    # Houdini takes the viewer out too, sometimes before the panel and sometimes into the object's "geo" tool state
    # after it (GUI runs 2026-11-10, most runs; a click in "geo" CREATES an object). A late state change is made here
    # every time, with "showhandle": setCurrentState("geo") itself created an object and dropped the selection (Houdini's
    # own late "geo" did neither), so the rows are judged before it
    sv.setCurrentState("showhandle")
    yield 300
    log("  other object, late state: pwd", sv.pwd().path(), "state", sv.currentState(), "objects", geos())
    out["other_object_back_to_objects"] = shown and sv.currentState() in stack_panel.OBJ_STATES
    click_row(e.list, hull.sessionId())
    yield 300

    # --- add from the Modifier List: on top, one undo step, undo follows -----------------------------------------
    u0 = labels()
    choose(p, "subdivide")
    yield 500
    top = hull.displayNode()
    log("  add: top", top and top.path(), "undo", labels()[:3], "rows", rows(p), "entry", p._entry)
    out["add_from_list"] = (top.type().name() == "subdivide" and top.input(0) == sd and rows(p) == top_first(hull)
                            and p._entry == top.sessionId() and sv.currentState() == "subdivide")
    out["add_one_undo_gui"] = len(labels()) == len(u0) + 1 and labels()[0].startswith("modelUI: add")
    hou.undos.performUndo()
    yield 400
    why('undo_follows', p, sv, hull)
    out["undo_follows"] = rows(p) == top_first(hull) and len(rows(p)) == 3 and hull.displayNode() == sd and p.parms is None

    # --- the component selection becomes the new entry's group ---------------------------------------------------------
    p.list.clearSelection()
    yield 300
    with hou.undos.disabler():
        sv.setPwd(hull)
    sv.setCurrentState("select")
    yield 300
    sv.setCurrentGeometrySelection(PR, (sd,), (hou.Selection(sd.geometry(), PR, "0 1"),))
    yield 300
    choose(p, "extrude")
    yield 500
    top = hull.displayNode()
    log("  selection add: top", top.path(), "group", top.parm("group").eval())
    out["selection_to_group_gui"] = (top.type().name() == "polyextrude::2.0" and top.input(0) == sd
                                     and sorted(pr.number() for pr in sd.geometry().globPrims(top.parm("group").eval())) == [0, 1])
    hou.undos.performUndo()
    yield 400

    # --- buttons: up, on/off, delete, collapse, open as nodes ---------------------------------------------------------
    click_row(p.list, ex.sessionId())
    yield 400
    click(p.buttons["up"])
    yield 400
    why('up_button_reorders', p, sv, hull)
    out["up_button_reorders"] = ([n.name() for n in stack.chain(hull)] == ["base", "sd", "ex"] and rows(p) == top_first(hull)
                                 and hull.displayNode() == ex)
    hou.undos.performUndo()
    yield 300
    why('reorder_undo_follows', p, sv, hull)
    out["reorder_undo_follows"] = [n.name() for n in stack.chain(hull)] == ["base", "ex", "sd"] and rows(p) == top_first(hull)
    click_row(p.list, sd.sessionId())
    yield 400
    click(p.buttons["down"])
    yield 400
    out["down_button_reorders"] = ([n.name() for n in stack.chain(hull)] == ["base", "sd", "ex"] and rows(p) == top_first(hull)
                                   and hull.displayNode() == ex)
    hou.undos.performUndo()
    yield 300
    u0 = labels()
    for i in range(p.list.count()):
        if p.list.item(i).data(Qt.UserRole) == ex.sessionId():
            p.list.item(i).setCheckState(Qt.Unchecked)
    yield 300
    why('off_box_bypasses', p, sv, hull)
    out["off_box_bypasses"] = ex.isBypassed() and len(labels()) == len(u0) + 1
    hou.undos.performUndo()
    yield 300
    item = [p.list.item(i) for i in range(p.list.count()) if p.list.item(i).data(Qt.UserRole) == ex.sessionId()]
    out["undo_shows_on"] = not ex.isBypassed() and bool(item) and item[0].checkState() == Qt.Checked
    click_row(p.list, ex.sessionId())
    yield 400
    click(p.buttons["delete"])
    yield 400
    why('delete_button', p, sv, hull)
    out["delete_button"] = ([n.name() for n in stack.chain(hull)] == ["base", "sd"] and rows(p) == top_first(hull)
                            and p.parms is None and hull.node("ex") is None)
    hou.undos.performUndo()
    yield 400
    ex = hull.node("ex")
    out["delete_undo_follows"] = ex is not None and rows(p) == top_first(hull) and len(rows(p)) == 3
    want = [tuple(pt.position()) for pt in hull.displayNode().geometry().points()]
    p.list.clearSelection()
    yield 300
    click(p.buttons["collapse"])
    yield 400
    disp = hull.displayNode()
    why('collapse_button', p, sv, hull)
    out["collapse_button"] = ([n.type().name() for n in stack.chain(hull)] == ["stash"] and rows(p) == top_first(hull)
                              and [tuple(pt.position()) for pt in disp.geometry().points()] == want)
    hou.undos.performUndo()
    yield 400
    ex, sd = hull.node("ex"), hull.node("sd")
    # no entry chosen (the viewer at object level): the network editor is elsewhere until the button takes it in. With
    # an entry the viewer is inside and a linked network editor is there already, so it could not tell
    ne = next((t for t in hou.ui.paneTabs() if t.type() == hou.paneTabType.NetworkEditor), None) or hou.ui.curDesktop().createFloatingPaneTab(hou.paneTabType.NetworkEditor)   # the desk has none
    with hou.undos.disabler():
        ne.setPwd(hou.node("/obj"))
    yield 300
    log("  network editor before open as nodes:", ne.pwd().path(), ne.currentNode())
    click(p.buttons["nodes"])
    yield 400
    log("  network editors:", [(t.name(), t.pwd().path()) for t in hou.ui.paneTabs() if t.type() == hou.paneTabType.NetworkEditor])
    log("  open as nodes:", ne and ne.pwd().path(), ne and ne.currentNode(), "objects", [n.name() for n in hou.node("/obj").children()])
    out["open_as_nodes"] = ne is not None and ne.pwd() == hull and ne.currentNode() == sd
    click_row(p.list, ex.sessionId())
    yield 400

    # --- pick an object into an input ---------------------------------------------------------------------------------
    pb = getattr(p, "pick_buttons", {}).get(1)
    if pb is not None:
        click(pb)
        yield 300
        click_row(e.list, spine.sessionId())
        yield 500
    log("  pick: input 1", ex.input(1), "selected", s.selected(), "entry", p._entry)
    om = ex.input(1)
    out["pick_button_wires"] = (pb is not None and om is not None and om.type().name() == "object_merge"
                                and om.parm("objpath1").eval() == spine.path())
    out["pick_returns_to_object"] = s.selected() == [hull.sessionId()] and rows(p) == top_first(hull) and p._entry == ex.sessionId()
    p.list.clearSelection()
    yield 300

    # --- a container piece: its first modifier promotes it, one undo step -------------------------------------------
    click_row(e.list, piece)
    yield 400
    why('piece_shows_one_row', p, sv, hull)
    out["piece_shows_one_row"] = s.selected() == [piece] and rows(p) == [None]
    objs0 = {n.sessionId() for n in hou.node("/obj").children()}
    geos0 = geos()
    u0 = labels()
    choose(p, "subdivide")
    yield 600
    made = [n for n in hou.node("/obj").children() if n.sessionId() not in objs0 and n.type().name() == "geo"]
    new = made[0] if len(made) == 1 else None
    why("promote", p, sv, hull)
    log("  promote: new", new and new.path(), "made", [n.name() for n in made])
    out["promote_from_panel"] = (new is not None and [n.type().name() for n in stack.chain(new)] == ["usdimport", "subdivide"]
                                 and rows(p) == top_first(new) and pids[0] not in [r[0] for r in containers.piece_rows(c)])
    out["promote_one_undo_gui"] = len(labels()) == len(u0) + 1
    hou.undos.performUndo()
    yield 400
    why("promote undone", p, sv, hull)
    out["undo_back_to_object_state"] = sv.pwd() == hou.node("/obj") and sv.currentState() in ("select", "pose")
    out["promote_undo_gui"] = (geos() == geos0
                               and pids[0] in [r[0] for r in containers.piece_rows(c)])

    # a panel deleted without close_down (Houdini destroying a pane's panel) takes its callbacks with it
    q = stack_panel.ModifyPanel()
    yield 300
    armed = bool(q._armed) and q._sv is not None and q._watching
    q.deleteLater()
    yield 300
    left = [1 for cb in sv.eventCallbacks() if getattr(cb, "__self__", None) is q] + [
        n.path() for n in [hull] + list(hull.children()) for cb in n.eventCallbacks() if getattr(cb[1], "__self__", None) is q]
    out["deleted_panel_lets_go"] = armed and not left and q._timer.start not in s._watchers
    log("  deleted panel: armed", armed, "callbacks left", left)

    # no object made on the way: the viewer was never left in a state where a click or entering it creates one ("geo")
    out["no_stray_objects"] = geos() == start_geos and "geo" not in asked
    log("  objects at the end", geos(), "at the start", start_geos)

    # --- modelUI off: nothing of ours left on the nodes --------------------------------------------------------------
    click_row(e.list, hull.sessionId())
    yield 300
    switch.uninstall()
    yield 300
    left = [n.path() for n in [hull] + list(hull.children()) for cb in n.eventCallbacks()
            if getattr(cb[1], "__self__", None) is p]
    left += ["viewer" for cb in sv.eventCallbacks() if getattr(cb, "__self__", None) is p]
    out["uninstall_clean"] = not left and not p._armed
    log("  after uninstall: callbacks left", left)


def undo_open():
    n = hou.node("/obj").createNode("null", "pf_undo_probe")
    try:
        hou.undos.performUndo()
    except hou.Error as e:
        if hou.node("/obj/pf_undo_probe") is not None:
            with hou.undos.disabler():
                n.destroy()
        return e.instanceMessage().strip().splitlines()[-1]
    return None if hou.node("/obj/pf_undo_probe") is None else "undo did not remove the probe"


def _q(f):
    try:
        f()
    except Exception:  # noqa: BLE001
        log("  cleanup:", traceback.format_exc().splitlines()[-1])


def cleanup():
    if "orig_scs" in STATE:
        hou.SceneViewer.setCurrentState = STATE.pop("orig_scs")
    leak = undo_open()
    if leak:
        log("  UNDO LEAK before cleanup:", leak)
    sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    if sv is not None:
        _q(lambda: sv.setPwd(hou.node("/obj")))
        _q(lambda: sv.setCurrentState("select"))   # a run must not leave its state to the next (seen: "showhandle")
    md = hou.ui.desktop(switch.DESK)   # a panel left on modelUI's viewer by a mutation run (viewer_callback_left) would
    msv = md.paneTabOfType(hou.paneTabType.SceneViewer) if md is not None else None   # act in every later run
    for v in {x.name(): x for x in (sv, msv) if x is not None}.values():
        for cb in v.eventCallbacks():
            if type(getattr(cb, "__self__", None)).__name__ == "ModifyPanel" and cb.__self__ is not STATE.get("hb"):
                _q(lambda: v.removeEventCallback(cb))
                if cb.__self__ is not STATE.get("fresh"):
                    log("  cleanup: removed a stray panel's viewer callback (panel %x)" % id(cb.__self__))
    _q(switch.uninstall)
    fresh = STATE.pop("fresh", None)
    if fresh is not None:   # ours: closed and deleted; Houdini's own panel is the switch's again
        _q(fresh.close_down)
        _q(fresh.close)
        _q(fresh.deleteLater)
        hou.session._pf_modelui_stack = STATE.get("hb")
    _q(lambda: hou.ui.desktop(STATE["desk0"]).setAsCurrent())
    switch._state["on"] = False


MODS = {"stack_panel": stack_panel, "stack": stack}


def mutate(modname, pairs):
    mod = MODS[modname]
    with open(mod.__file__, encoding="utf-8") as f:
        src = f.read()
    new = src
    for old, rep in pairs:
        if new.count(old) != 1:
            raise RuntimeError("mutation snippet not found exactly once: %r" % old)
        new = new.replace(old, rep)
    exec(compile(new, mod.__file__, "exec"), mod.__dict__)
    return lambda: exec(compile(src, mod.__file__, "exec"), mod.__dict__)


SP = "stack_panel"
MUTATIONS = [   # (mutation, the check it must redden, module, [(old, new)])
    ("install_skipped", "panel_in_desk", SP, [("        p.set_watching(False)\n        p.set_watching(True)", "        pass")]),
    ("refresh_inside_action", "no_rebuild_inside_click", SP, [("        if self._busy:\n            LOG.debug(\"refresh deferred (busy)\")", "        if False:\n            LOG.debug(\"refresh deferred (busy)\")")]),
    ("not_watching_scene", "follows_explorer", SP, [("            self.model.watch(self._timer.start)", "            pass")]),
    ("target_ignores_pick", "follows_viewport_pick", SP, [("        return sel[0] if len(sel) == 1 else None", "        return self._pid if self._pid is not None else (sel[0] if len(sel) == 1 else None)")]),
    ("nodes_not_watched", "follows_network_edit", SP, [("                node.addEventCallback(events, self._node_event)", "                pass")]),
    ("deletes_not_watched", "follows_network_delete", SP, [("_OBJ_EVENTS = (hou.nodeEventType.ChildCreated, hou.nodeEventType.ChildDeleted)", "_OBJ_EVENTS = (hou.nodeEventType.ChildCreated,)"),
                                                           ("_NODE_EVENTS = (hou.nodeEventType.InputRewired, hou.nodeEventType.FlagChanged, hou.nodeEventType.NameChanged)", "_NODE_EVENTS = (hou.nodeEventType.FlagChanged, hou.nodeEventType.NameChanged)")]),
    ("no_state", "entry_shows_state", SP, [("                sv.enterCurrentNodeState()", "                sv.setCurrentState('select')")]),
    ("parms_of_object", "entry_shows_parms", SP, [("            self.parms = hou.qt.ParmDialog(node)", "            self.parms = hou.qt.ParmDialog(node.parent())"),
                                                  ("            self.parms.setNode(node)", "            self.parms.setNode(node.parent())")]),
    ("parms_sliver", "entry_shows_parms", SP, [("        split.setSizes([350, 650])", "        pass")]),
    ("state_left_to_houdini", "undo_back_to_object_state", SP, [("            if sv.currentState() not in OBJ_STATES:   # also when", "            if False:   # also when"),
                                                                 ("            if sv.pwd() != hou.node(\"/obj\"):   # ours", "            if ins is not None:   # ours")]),
    ("enter_recorded", "entry_select_no_undo", SP, [("        with hou.undos.disabler():\n            if sv.pwd() != obj:", "        if True:\n            if sv.pwd() != obj:")]),
    ("object_dropped", "inside_keeps_object_shown", SP, [("        if ins is not None and (not sel or sel == [ins.sessionId()]):", "        if False:")]),
    ("stays_inside", "no_entry_back_to_objects", SP, [("        else:\n            self._leave_object()\n        self._update()", "        else:\n            pass\n        self._update()")]),
    ("stays_inside_other", "other_object_back_to_objects", SP, [("            if self._picking is None and (ins is None and self._went_in or ins is not None and pid != ins.sessionId()):", "            if False:")]),
    ("list_ignored", "add_from_list", SP, [("        if key:\n            self.add(key)", "        if False:\n            self.add(key)")]),
    ("add_entry_recorded", "add_one_undo_gui", SP, [("        with hou.undos.disabler():\n            if sv.pwd() != obj:", "        if True:\n            if sv.pwd() != obj:")]),
    ("undo_not_followed", "undo_follows", SP, [("                node.addEventCallback(events, self._node_event)", "                pass"),
                                               ("            self._timer.start()   # never work inside Houdini's callback", "            pass")]),
    ("selection_unused", "selection_to_group_gui", SP, [("        if gs is None or not gs.nodes() or not gs.mergedSelectionString():", "        if True:")]),
    ("up_moves_down", "up_button_reorders", SP, [('(("up", "Up", lambda: self.move_entry(+1))', '(("up", "Up", lambda: self.move_entry(-1))')]),
    ("down_moves_up", "down_button_reorders", SP, [('("down", "Down", lambda: self.move_entry(-1))', '("down", "Down", lambda: self.move_entry(+1))')]),
    ("reorder_undo_unseen", "reorder_undo_follows", SP, [("_NODE_EVENTS = (hou.nodeEventType.InputRewired, hou.nodeEventType.FlagChanged, hou.nodeEventType.NameChanged)", "_NODE_EVENTS = (hou.nodeEventType.NameChanged,)")]),
    ("box_ignored", "off_box_bypasses", SP, [("        if node is not None and (it.checkState() == Qt.Checked) == node.isBypassed():", "        if False:")]),
    ("flag_unseen", "undo_shows_on", SP, [("_NODE_EVENTS = (hou.nodeEventType.InputRewired, hou.nodeEventType.FlagChanged, hou.nodeEventType.NameChanged)", "_NODE_EVENTS = (hou.nodeEventType.InputRewired, hou.nodeEventType.NameChanged)")]),
    ("delete_dead", "delete_button", SP, [('("delete", "Delete", self.delete_entry)', '("delete", "Delete", lambda: None)')]),
    ("delete_undo_unseen", "delete_undo_follows", SP, [("_OBJ_EVENTS = (hou.nodeEventType.ChildCreated, hou.nodeEventType.ChildDeleted)", "_OBJ_EVENTS = (hou.nodeEventType.ChildDeleted,)"),
                                                       ("_NODE_EVENTS = (hou.nodeEventType.InputRewired, hou.nodeEventType.FlagChanged, hou.nodeEventType.NameChanged)", "_NODE_EVENTS = (hou.nodeEventType.NameChanged,)")]),
    ("collapse_one_entry", "collapse_button", SP, [("            st = stack.collapse(node, obj=obj)", "            st = stack.collapse(node or stack.chain(obj)[1], obj=obj)")]),
    ("settle_ignored", "other_object_back_to_objects", SP, [("            self._settle()", "            pass")]),
    ("viewer_callback_left", "uninstall_clean", SP, [("                    self._sv.removeEventCallback(self._viewer_event)", "                    pass")]),
    ("leave_reselects_old", "other_object_back_to_objects", SP, [("            want = sel or ([ins.sessionId()] if ins is not None else [])", "            want = [ins.sessionId()] if ins is not None else sel")]),
    ("nodes_elsewhere", "open_as_nodes", SP, [("            ne.setPwd(obj)", "            pass"),
                                              ("                node.setCurrent(True, clear_all_selected=False)", "                pass")]),
    ("pick_not_taken", "pick_button_wires", SP, [("                stack.pick_input(node, index, sel[0], self.mode)", "                pass")]),
    ("pick_keeps_source", "pick_returns_to_object", SP, [("        self.model.select([owner])\n        self._entry = entry_sid", "        self._entry = entry_sid")]),
    ("piece_hidden", "piece_shows_one_row", SP, [('                rows = [(None, "%s (piece)" % self.model.name(pid), False)]', "                rows = []")]),
    ("add_to_object_only", "promote_from_panel", SP, [("            n = stack.add(self._pid, key, above=above,", "            n = stack.add(self.obj().sessionId(), key, above=above,")]),
    ("promote_outside_group", "promote_one_undo_gui", "stack", [('    with hou.undos.group("modelUI: add " + op["label"]):\n        obj = _own_object(pid)\n', '    obj = _own_object(pid)\n    with hou.undos.group("modelUI: add " + op["label"]):\n')]),
    ("promote_undo_partial", "promote_undo_gui", "stack", [("    obj = containers.promote(c, piece)", "    with hou.undos.disabler():\n        obj = containers.promote(c, piece)")]),
    ("callbacks_left", "uninstall_clean", SP, [("            self._arm(None)\n            self._picking = None", "            self._picking = None")]),
    ("no_destroy_hook", "deleted_panel_lets_go", SP, [("        self.destroyed.connect(functools.partial(_forget,", "        (functools.partial(_forget,")]),
    ("wrong_object_state", "no_stray_objects", SP, [('                    sv.setCurrentState(self._obj_state or "select")', '                    sv.setCurrentState("geo")')]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
if os.environ.get("PF_F1_QUICK"):
    RUNS = RUNS[:1]
if os.environ.get("PF_F2C_ONLY"):   # diagnosis: one baseline and the named mutations
    RUNS = [RUNS[0]] + [m for m in MUTATIONS if m[0] in os.environ["PF_F2C_ONLY"].split(",")]
    if os.environ.get("PF_F2C_ISOLATE"):   # diagnosis: a baseline after every mutation run (what does a run leave?)
        RUNS = [RUNS[0]] + [r for m in RUNS[1:] for r in (m, RUNS[0])]
RESULTS = []


def driver():
    STATE["desk0"] = hou.ui.curDesktop().name()
    import polyfactory
    log("polyfactory from", polyfactory.__file__)
    for name, check, modname, pairs in RUNS:
        cleanup()
        restore, out = None, {}
        try:
            if modname:
                restore = mutate(modname, pairs)
            gen = STATE["gen"] = suite(out)
            for delay in gen:
                yield delay
                if check and check in out:   # a mutation run ends at its paired check: shorter, and what a broken
                    gen.close()              # build does after it cannot spill into later runs
                    break
        except Exception:  # noqa: BLE001
            out["_exception"] = traceback.format_exc()
        finally:
            if restore:
                restore()
            cleanup()
        RESULTS.append({"mutation": name, "check": check, "out": out})
        log(name or "baseline", check, out.get(check) if check else out)
        yield 200
    with open(OUT, "w") as f:
        json.dump(RESULTS, f, indent=1)


def _line(g):
    """The suite line a generator chain paused at (the step trace: the last one logged is where a crash happened)."""
    while getattr(g, "gi_yieldfrom", None) is not None:
        g = g.gi_yieldfrom
    return g.gi_frame.f_lineno if getattr(g, "gi_frame", None) is not None else None


def pump(gen, waited=0):
    p = STATE.get("fresh")
    if p is not None and (p._busy or p._pending) and waited < 10000:
        # the panel is inside a HOM call that runs Houdini's nested event loop (setPwd / setCurrentState took up to
        # ~2 s in GUI runs, with this timer firing inside): the next step waits until it has finished
        QtCore.QTimer.singleShot(50, lambda: pump(gen, waited + 50))
        return
    if waited:
        LOGF.write("    waited %d ms for the panel\n" % waited)
    try:
        delay = next(gen)
        LOGF.write("    @%s\n" % _line(STATE.get("gen")))
    except StopIteration:
        finish()
        return
    except Exception:  # noqa: BLE001
        log(traceback.format_exc())
        finish()
        return
    QtCore.QTimer.singleShot(delay, lambda: pump(gen))


def finish():
    if LOGF.closed:
        return
    GUARD.stop()
    log("done")
    LOGF.close()
    hdefereval.executeDeferred(lambda: hou.exit(suppress_save_prompt=True))


def guard():
    if hou.qt.mainWindow() is not None and not off_screen():
        log("ABORT: windows on screen", [(type(w).__name__, w.frameGeometry()) for w in visible_on_screen()])
        finish()


GUARD = QtCore.QTimer(interval=200, timeout=guard)


def start(tries=[0]):  # noqa: B006
    try:
        if hou.qt.mainWindow() is None:
            tries[0] += 1
            if tries[0] > 60:
                raise RuntimeError("no main window after 65 s")
            QtCore.QTimer.singleShot(1000, start)
            return
        off_screen()
        GUARD.start()
        pump(driver())
    except Exception:  # noqa: BLE001
        log(traceback.format_exc())
        finish()


QtCore.QTimer.singleShot(300, off_screen)
QtCore.QTimer.singleShot(5000, start)
