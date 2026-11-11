"""GUI checks of modelUI F2d Align (align.py: hotkeys, target and face picking in a viewer, the Align and Normal Align
dialogs, preview / Apply / Cancel, modelUI going off), run INSIDE a throwaway Houdini.

Start it with:  PF_GUI_SCRIPT=gui_f2d.py PF_F1_SCRATCH=F:/cache/modelui/f2d/gui python tests/modelui/run_gui_f1.py
(own prefs, only the polyfactory package of THIS repository, every window off screen, exits by itself, never saves a
.hip). Input goes the real path: QtTest on the viewer's QWindow at the pixel where the viewport shows the piece, keys
with the cursor over the viewer (Houdini routes hotkeys by cursor). Baseline, one run per mutation in MUTATIONS (a
source edit exec'd into the live module), baseline again; results to $PF_F1_OUT.

What it cannot see: the maths beyond the dialog's wiring (check_align.py owns it), the dialog's look, Esc or the
close box on a dialog (Qt routes both to reject(), the path Cancel takes), a second viewer, picking in an
orthographic view, the real mouse cursor (the cross is checked through align._cursor_tick with a point over the
viewer and one over the menu bar: the test windows are off screen), the menu bar itself (the check runs the shipped menu items' scripts; the hotkeys reach the same
items by their ids).
"""
import glob
import json
import logging
import os
import traceback

import hdefereval
import hou
from hutil.Qt import QtCore, QtWidgets
from PySide6.QtTest import QTest

from polyfactory.modelui import align, containers, input_layer, keys, pieces_ui, scene, switch

OUT = os.environ["PF_F1_OUT"]
LOGF = open(OUT + ".log", "w", buffering=1)
Qt = QtCore.Qt
LMB, RMB, NOM = Qt.LeftButton, Qt.RightButton, Qt.NoModifier
ALTCTRL = Qt.AltModifier | Qt.ControlModifier
FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))
STATE = {"desk0": None}
TOL = 1e-3   # world units at |values| <= 30, float32 storage and GUI-driven matrices


def log(*a):
    LOGF.write(" ".join(str(x) for x in a) + "\n")


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


def L(win, g):
    return win.mapFromGlobal(g)


def raw(pids):
    """Stored values bit for bit: container stash points, object transform parameters."""
    out = {}
    for pid in pids:
        if isinstance(pid, tuple):
            g = containers.stash(hou.nodeBySessionId(pid[1])).geometry()
            out[pid[1]] = tuple(tuple(g.pointFloatAttribValues(a)) for a in ("P", "orient", "scale"))
        else:
            n = hou.nodeBySessionId(pid)
            out[pid] = tuple(n.parmTuple(k).eval() for k in ("t", "r", "s", "p", "pr", "scale"))
    return out


class _Probe(QtCore.QObject):
    def __init__(self, seen):
        super().__init__()
        self.seen = seen

    def eventFilter(self, obj, ev):  # noqa: N802
        self.seen.append(int(ev.type()))
        return False


class _Lines(logging.Handler):
    def __init__(self, lines):
        super().__init__()
        self.lines = lines

    def emit(self, record):
        self.lines.append(record.getMessage())


def no_target():
    """Align's dialog (open during the pick) has not got its target."""
    d = align._state["dialog"]
    return d is None or d.session.target is None


def picking():
    return align._state["pick"] is not None


def pick_clean():
    """No pick running: the gesture is gone and the cross cursor too."""
    return (align._state["pick"] is None and align.GESTURE not in input_layer._gestures
            and QtWidgets.QApplication.overrideCursor() is None)


def suite(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    c = containers.create()
    big = hou.hmath.buildScale(10, 10, 10)
    ids = containers.add_pieces(c, [(FILES[3], "a", big * hou.hmath.buildTranslate((-15, 0, 0))),
                                    (FILES[3], "t", big * hou.hmath.buildRotate(0, 30, 0) * hou.hmath.buildTranslate((12, 2, -3)))])
    a, t = ("piece", c.sessionId(), ids[0]), ("piece", c.sessionId(), ids[1])
    box = hou.node("/obj").createNode("geo", "box")
    box.createNode("box").parm("scale").set(2)
    box.parmTuple("t").set((0, 0, 9))
    bx = box.sessionId()
    yield 100
    ok = switch.install()
    yield 1200
    sv, gl = viewer()
    sv.setViewportLayout(hou.geometryViewportLayout.Single)
    vp = sv.curViewport()
    vp.changeType(hou.geometryViewportType.Perspective)
    yield 300
    vp.frameAll()
    yield 400
    win = gl.window().windowHandle()
    sc = scene.current()
    out["installed"] = bool(ok) and "polyfactory.modelui.align" in switch._state["done"]
    sv.setCurrentState("select")
    yield 300

    def centre(pid):
        return [p for p in c.displayNode().geometry().prims() if p.attribValue("pf_piece") == pid[2]][0].boundingBox().center()

    def hover():
        g = gl.mapToGlobal(QtCore.QPoint(gl.width() // 2, gl.height() // 2))
        QTest.mouseMove(win, L(win, g))
        gl.setFocus()

    def key(k, mods=ALTCTRL):
        hover()
        QTest.keyClick(win, k, mods)

    def click(world, button=LMB, mods=NOM):
        g = screen_point(sv, gl, world)
        QTest.mouseMove(win, L(win, g))
        QTest.mouseClick(win, button, mods, L(win, g))

    def wait_dialog():
        for _ in range(20):
            d_ = align._state["dialog"]
            if d_ is not None and getattr(d_.session, "target", 1) is not None:   # Align's dialog is open before its target
                break
            yield 100

    # --- the menu entries: the shipped MainMenuCommon.xml's items run as Houdini runs them -----------------------------
    # (Houdini's main menu is not a tree of QActions; the hotkeys above reach these same items by their ids)
    sc.select([a, bx])   # Align needs a selection
    yield 300
    import xml.etree.ElementTree as ET
    root = ET.parse(os.path.join(os.environ["POLYFACTORY"], "MainMenuCommon.xml")).getroot()
    items = {e.get("id"): e for e in root.iter("scriptItem")}
    ok_m = True
    for sym, kind in (("h.pf_modelui_align", "align"), ("h.pf_modelui_quick_align", "quick"),
                      ("h.pf_modelui_normal_align", "normal")):
        e = items.get(sym)
        if e is None:
            ok_m = False
            continue
        exec(e.find("scriptCode").text, {})
        yield 100
        ok_m &= picking() and align._state["pick"]["kind"] == kind and sym in keys.COMMANDS
        align.cancel_pick()
    out["menu_starts_align"] = bool(ok_m)   # first: everything below goes through align() too

    # --- Align: hotkey, target click, preview, Apply ------------------------------------------------------------------
    sc.select([a, bx])
    yield 300
    sel0 = sc.selected()
    key(Qt.Key_A)
    yield 300
    order = list(input_layer._gestures)
    out["hotkey_starts_pick"] = picking() and order[:1] == [align.GESTURE]
    mw = hou.qt.mainWindow()
    inside, outside = sv.qtScreenGeometry().center(), mw.mapToGlobal(QtCore.QPoint(5, 5))   # a viewer / the menu bar
    align._cursor_tick(inside)
    cross_in = QtWidgets.QApplication.overrideCursor()
    cross_in = cross_in is not None and cross_in.shape() == Qt.CrossCursor
    align._cursor_tick(outside)
    out["cross_only_over_viewers"] = (cross_in and QtWidgets.QApplication.overrideCursor() is None
                                      and not any(v.qtScreenGeometry().contains(outside) for v in input_layer._viewers()))
    # an object right behind the target on the camera ray: the click must intersect only what the viewport shows there
    v = vp.mapToScreen(centre(t))
    rd, ro = vp.mapToWorld(int(v[0]), int(v[1]))
    behind = hou.node("/obj").createNode("geo", "behind")
    behind.createNode("box").parm("scale").set(4)
    behind.parmTuple("t").set(tuple(centre(t) + hou.Vector3(rd).normalized() * 40))
    yield 200
    log("  after Alt+Ctrl+A: pick", align._state["pick"] and align._state["pick"]["step"], "gestures", order,
        "keys", hou.hotkeys.assignments("h", "h.pf_modelui_align"))
    seen = []
    flt = _Probe(seen)
    win.installEventFilter(flt)
    click(centre(t))
    win.removeEventFilter(flt)
    yield from wait_dialog()
    dlg = align._state["dialog"]
    log("  target click: dialog", dlg and dlg.windowTitle(), "last hit", align._state["pick"] and align._state["pick"].get("last_hit"),
        "selected", sc.selected())
    log("  target click intersected", align._state.get("last_scan"), "geometries")
    out["pick_scans_one"] = align._state.get("last_scan") == 1
    out["target_click_opens_dialog"] = (isinstance(dlg, align.AlignDialog) and dlg.session.target is not None and dlg.session.target["pid"] == t
                                        and int(QtCore.QEvent.MouseButtonPress) not in seen and pick_clean()
                                        and sc.selected() == sel0)
    if dlg is None:
        return
    r0, u0 = raw([a, bx]), len(hou.undos.undoLabels())
    tgt = align.item(t)
    cb, cur, tg = dlg.pos[0]
    cur.setCurrentIndex(align.POINTS.index("min"))
    tg.setCurrentIndex(align.POINTS.index("max"))
    cb.setChecked(True)
    yield 200
    ia, ib = align.item(a), align.item(bx)
    out["dialog_preview_moves"] = (abs(align.value(ia, "min", 0) - align.value(tgt, "max", 0)) < TOL
                                   and abs(align.value(ib, "min", 0) - align.value(tgt, "max", 0)) < TOL
                                   and raw([a, bx]) != r0 and len(hou.undos.undoLabels()) == u0)
    want = {p: pieces_ui.get_xform(p) for p in (a, bx)}
    QTest.mouseClick(dlg.apply_button, LMB)
    yield 300
    labels = hou.undos.undoLabels()
    kept = all(pieces_ui.get_xform(p).isAlmostEqual(want[p], 1e-4) for p in (a, bx))
    log("  apply: labels", labels[:3], "kept", kept, "dialog", align._state["dialog"])
    hou.undos.performUndo()
    yield 200
    out["dialog_apply_one_undo"] = (align._state["dialog"] is None and kept and len(labels) == u0 + 1
                                    and labels[0] == "modelUI: align" and raw([a, bx]) == r0)

    # --- Align again: the dialog remembers, Cancel puts everything back exactly -----------------------------------------
    sc.select([a, bx])
    yield 200
    align.align()
    click(centre(t))
    yield from wait_dialog()
    dlg = align._state["dialog"]
    remembered = dlg is not None and dlg.options()["pos"] == {0: ("min", "max")}
    if dlg is not None:
        dlg.orient[1].setChecked(True)
        dlg.scale[2].setChecked(True)
        yield 200
        moved = raw([a, bx]) != r0
        QTest.mouseClick(dlg.cancel_button, LMB)
        yield 300
        out["dialog_cancel_exact"] = (remembered and moved and raw([a, bx]) == r0
                                      and len(hou.undos.undoLabels()) == u0 and align._state["dialog"] is None)

    # --- the pick itself: a selected target is refused, Alt passes to Houdini, Esc and right click end it -----------------
    align.align()
    yield 100
    click(centre(a))   # selected: not a target
    yield 300
    out["selected_target_refused"] = picking() and no_target()
    seen = []
    flt = _Probe(seen)
    win.installEventFilter(flt)
    click(centre(t), mods=Qt.AltModifier)   # Houdini's tumble key: never ours (a click, so the camera stays)
    win.removeEventFilter(flt)
    yield 300
    out["alt_click_passes"] = picking() and int(QtCore.QEvent.MouseButtonPress) in seen and no_target()
    g_t = screen_point(sv, gl, centre(t))   # Space held: Houdini's view state; its clicks are never ours (a click, no turn)
    QTest.mouseMove(win, L(win, g_t))
    gl.setFocus()
    QTest.keyPress(win, Qt.Key_Space)
    yield 300
    st_space = sv.currentState()
    seen = []
    flt = _Probe(seen)
    win.installEventFilter(flt)
    QTest.mouseClick(win, LMB, NOM, L(win, g_t))
    win.removeEventFilter(flt)
    yield 300
    QTest.keyRelease(win, Qt.Key_Space)
    yield 300
    log("  space click: state", st_space, "press seen", int(QtCore.QEvent.MouseButtonPress) in seen, "picking", picking())
    out["view_state_click_passes"] = (st_space in pieces_ui.VIEW_STATES and picking()
                                      and int(QtCore.QEvent.MouseButtonPress) in seen and no_target())
    key(Qt.Key_Escape, NOM)
    yield 300
    out["esc_ends_pick"] = pick_clean() and align._state["dialog"] is None
    align.align()   # Esc with the keyboard focus outside the viewer (a list in another pane) ends the pick too
    yield 100
    svr = sv.qtScreenGeometry()
    lists = [w for w in hou.qt.mainWindow().findChildren(QtWidgets.QAbstractItemView)
             if w.isVisible() and w.focusPolicy() != Qt.NoFocus
             and not svr.intersects(QtCore.QRect(w.mapToGlobal(QtCore.QPoint(0, 0)), w.size()))]
    if lists:
        lists[0].setFocus()
        yield 100
        log("  Esc with focus on", type(lists[0]).__name__, "focus now", type(QtWidgets.QApplication.focusWidget()).__name__)
        QTest.keyClick(win, Qt.Key_Escape)
        yield 300
    out["esc_outside_viewer_ends_pick"] = bool(lists) and pick_clean()
    align.cancel_pick()
    align.align()
    yield 100
    click(centre(t), button=RMB)
    yield 300
    out["right_click_ends_pick"] = pick_clean() and align._state["dialog"] is None

    # --- Quick Align by its key ------------------------------------------------------------------------------------------
    sc.select([a])
    yield 300
    u0 = len(hou.undos.undoLabels())
    key(Qt.Key_A, ALTCTRL | Qt.ShiftModifier)
    yield 200
    started = picking()
    click(centre(t))
    yield 400
    labels = hou.undos.undoLabels()
    out["quick_align_key"] = (started and pick_clean() and len(labels) == u0 + 1 and labels[0] == "modelUI: quick align"
                              and (pieces_ui.get_xform(a).extractTranslates() - pieces_ui.get_xform(t).extractTranslates()).length() < TOL)
    log("  quick: started", started, "labels", labels[:2], "a", pieces_ui.get_xform(a).extractTranslates(), "t",
        pieces_ui.get_xform(t).extractTranslates())
    hou.undos.performUndo()
    yield 200

    # --- Normal Align: a face of the box onto a face of the target piece --------------------------------------------------
    sc.select([bx])
    yield 300
    u0 = len(hou.undos.undoLabels())
    r0 = raw([bx])
    key(Qt.Key_N)
    yield 200
    started = picking() and align._state["pick"]["step"] == "normal_src"
    click(hou.Vector3(0, 1, 9))   # the box's top face (size 2 about (0, 0, 9))
    yield 300
    st = align._state["pick"]
    src = st and st.get("src")
    click(centre(t))
    yield from wait_dialog()
    dlg = align._state["dialog"]
    log("  normal: started", started, "src", src, "dialog", dlg)
    ok_n = False
    if isinstance(dlg, align.NormalDialog):
        ps, ns = dlg.session.src[1], dlg.session.src[2]
        ht = dlg.session.tgt
        m0 = dlg.session.items[0]["m"]
        QTest.mouseClick(dlg.apply_button, LMB)
        yield 300
        m1 = pieces_ui.get_xform(bx)
        p_new = ps * m0.inverted() * m1
        n_new = (hou.Vector4(ns[0], ns[1], ns[2], 0) * m0.transposed() * m1.inverted().transposed())   # face normal moved
        n_new = hou.Vector3(n_new[0], n_new[1], n_new[2]).normalized()
        labels = hou.undos.undoLabels()
        ok_n = (started and src is not None and src[0] == bx and abs(ps[1] - 1.0) < TOL and (ns - hou.Vector3(0, 1, 0)).length() < 1e-4
                and ht[0] == t and (p_new - ht[1]).length() < TOL and abs(n_new.dot(ht[2]) + 1) < 1e-4
                and len(labels) == u0 + 1 and labels[0] == "modelUI: normal align")
        log("  normal apply: p_new", p_new, "target", ht[1], "n_new", n_new, "nt", ht[2], "labels", labels[:2])
        hou.undos.performUndo()
        yield 200
    out["normal_align_clicks"] = ok_n and raw([bx]) == r0

    # --- modelUI goes off during a pick, and with a dialog open ----------------------------------------------------------
    sc.select([a, bx])
    yield 200
    r0, u0 = raw([a, bx]), len(hou.undos.undoLabels())
    align.align()
    yield 100
    pieces_ui_on = pieces_ui._state["on"]
    switch.uninstall()
    yield 300
    out["off_ends_pick"] = pieces_ui_on and pick_clean()
    switch.install()
    yield 800
    sc.select([a, bx])
    yield 200
    align.align()
    click(centre(t))
    yield from wait_dialog()
    dlg = align._state["dialog"]
    moved = dlg is not None and raw([a, bx]) != r0
    switch.uninstall()
    yield 300
    out["off_cancels_dialog"] = (moved and align._state["dialog"] is None and not dlg.isVisible()
                                 and raw([a, bx]) == r0 and len(hou.undos.undoLabels()) == u0)

    # --- Hannes' F12 scenario (feedback round 2): shelf-default box / torus / tube objects, the tube selected, state
    # "select", Alt+A over the viewer, click the box -------------------------------------------------------------------
    hou.hipFile.clear(suppress_save_prompt=True)
    objs = {}
    for nm, sop, t in (("box_object1", "box", (0, 0, 0)), ("torus_object1", "torus", (-4, 0, 2)), ("tube_object1", "tube", (4, 0, 0))):
        g = hou.node("/obj").createNode("geo", nm)
        g.createNode(sop)
        g.parmTuple("t").set(t)
        objs[nm] = g
    yield 200
    switch.install()
    yield 800
    sv, gl = viewer()
    sv.setCurrentState("select")
    sv.curViewport().frameAll()
    yield 500
    win = gl.window().windowHandle()
    tube_id, box_id = objs["tube_object1"].sessionId(), objs["box_object1"].sessionId()
    sc = scene.current()
    sc.select([tube_id])
    yield 300
    u0, r0 = len(hou.undos.undoLabels()), raw([tube_id])
    key(Qt.Key_A, Qt.AltModifier)
    yield 400
    dlg0 = align._state["dialog"]
    out["shelf_dialog_open_before_pick"] = (isinstance(dlg0, align.AlignDialog) and dlg0.isVisible() and picking()
                                            and "click an object" in dlg0.target_label.text()
                                            and not dlg0.apply_button.isEnabled() and not dlg0.isModal())
    align._cursor_tick(sv.qtScreenGeometry().center())
    cur = QtWidgets.QApplication.overrideCursor()
    out["shelf_cross_cursor_real"] = cur is not None and cur.shape() == Qt.CrossCursor
    # a miss says why: to the log (what F12's state.json shows) and to the status bar
    lines = []
    h_ = _Lines(lines)
    lg = logging.getLogger("polyfactory.modelui")
    lg.addHandler(h_)
    lg.setLevel(logging.INFO)
    gl_ = gl.mapToGlobal(QtCore.QPoint(15, 15))
    QTest.mouseMove(win, L(win, gl_))
    QTest.mouseClick(win, LMB, NOM, L(win, gl_))
    yield 400
    lg.removeHandler(h_)
    log("  miss lines", lines, "state", align._state.get("miss"))
    out["align_miss_logs_reason"] = (picking() and any("align pick missed" in x and "nothing is drawn" in x for x in lines)
                                     and align._state.get("miss") is not None)
    click(hou.Vector3(0, 0, 0))
    yield from wait_dialog()
    dlg = align._state["dialog"]
    log("  shelf: dialog", dlg, "pick", align._state["pick"], "miss", align._state.get("miss"))
    out["shelf_target_click_picks_box"] = (dlg is not None and dlg is dlg0 and getattr(dlg.session, "target", None) is not None
                                           and dlg.session.target["pid"] == box_id
                                           and dlg.target_label.text() == "Target: box_object1" and dlg.isModal())
    if out["shelf_target_click_picks_box"]:
        cb, cur_, tg = dlg.pos[0]
        cb.setChecked(True)
        cur_.setCurrentIndex(align.POINTS.index("min"))
        tg.setCurrentIndex(align.POINTS.index("max"))
        yield 200
        out["shelf_preview_moves_tube"] = raw([tube_id]) != r0 and len(hou.undos.undoLabels()) == u0
        QTest.mouseClick(dlg.cancel_button, LMB)
        yield 300
        out["shelf_cancel_restores"] = raw([tube_id]) == r0 and align._state["dialog"] is None
    # Cancel while the target is still being picked ends the pick and the dialog, nothing changed
    align.align()
    yield 200
    d_ = align._state["dialog"]
    QTest.mouseClick(d_.cancel_button, LMB)
    yield 300
    out["cancel_during_pick_ends_all"] = (pick_clean() and align._state["dialog"] is None and not d_.isVisible()
                                          and raw([tube_id]) == r0 and len(hou.undos.undoLabels()) == u0)
    # a transparent widget over the viewer (Houdini has overlays too) must not change where the click lands
    mw_ = hou.qt.mainWindow()
    ov = QtWidgets.QWidget(mw_)
    ov.setGeometry(QtCore.QRect(mw_.mapFromGlobal(sv.qtScreenGeometry().topLeft()), sv.qtScreenGeometry().size()))
    ov.show()
    ov.raise_()
    STATE["overlay"] = ov
    yield 200
    align.align()
    yield 200
    click(hou.Vector3(0, 0, 0))
    yield from wait_dialog()
    dlg = align._state["dialog"]
    out["pick_under_overlay_widget"] = (dlg is not None and getattr(dlg.session, "target", None) is not None
                                        and dlg.session.target["pid"] == box_id)
    if dlg is not None:
        QTest.mouseClick(dlg.cancel_button, LMB)
        yield 300
    ov.deleteLater()
    STATE["overlay"] = None
    align.cancel_pick()
    align.cancel_pick()


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
    if STATE.get("overlay") is not None:
        _q(STATE["overlay"].deleteLater)
        STATE["overlay"] = None
    leak = undo_open()
    if leak:
        log("  UNDO LEAK before cleanup:", leak)
    d = align._state.get("dialog")
    if d is not None:
        _q(d.reject)
    _q(align._end_pick)
    while QtWidgets.QApplication.overrideCursor() is not None:
        QtWidgets.QApplication.restoreOverrideCursor()
    _q(switch.uninstall)
    _q(lambda: hou.ui.desktop(STATE["desk0"]).setAsCurrent())
    switch._state["on"] = False
    if keys.snapshot() != STATE["keys0"]:
        log("  KEYS CHANGED after the run: restoring")
        _q(keys.revert)


MODS = {"align": align, "keys": keys, "input_layer": input_layer, "pieces_ui": pieces_ui}


def mutate(modname, pairs):
    mod = MODS[modname]
    with open(mod.__file__, encoding="utf-8") as f:
        src = f.read()
    new = src
    for old, rep in pairs:
        if new.count(old) != 1:
            raise RuntimeError("mutation snippet not found exactly once: %r" % old)
        new = new.replace(old, rep)
    if modname == "pieces_ui":   # its module state must survive: only the picking functions are swapped
        ns = {"__name__": mod.__name__, "__file__": mod.__file__}
        exec(compile(new, mod.__file__, "exec"), ns)
        names = ("_under", "_viewer_gl")
        saved = {k: getattr(mod, k) for k in names}
        for k in names:
            setattr(mod, k, ns[k])
        return lambda: [setattr(mod, k, v) for k, v in saved.items()]
    exec(compile(new, mod.__file__, "exec"), mod.__dict__)

    def restore():
        exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    return restore


AL = "align"
MUTATIONS = [   # (mutation, the check it must redden, module, [(old, new)])
    ("not_a_feature", "installed", AL, [("def install():\n    _end_pick()\n    _state[\"on\"] = True", "def install():\n    raise RuntimeError(\"mutation\")")]),
    ("no_align_key", "hotkey_starts_pick", "keys", [('    ("h", "h.pf_modelui_align", "Alt+Ctrl+A"),\n', "")]),
    ("pick_not_first", "target_click_opens_dialog", AL, [("input_layer.add_gesture(GESTURE, _gesture, first=True, keys_anywhere=True)", "input_layer.add_gesture(GESTURE, _gesture, keys_anywhere=True)")]),
    ("cursor_everywhere", "cross_only_over_viewers", AL, [('    over = (_state["pick"] is not None and any(', '    over = (_state["pick"] is not None or any(')]),
    ("hit_at_scans_all", "pick_scans_one", AL, [("    h = hit_ray(o, d, [n] if ok else None)", "    h = hit_ray(o, d)")]),
    ("keys_only_in_viewers", "esc_outside_viewer_ends_pick", "input_layer", [('            offered = [] if kind == "press" or text else [(k, f) for k, f in offered if k in _anywhere]', "            offered = []")]),
    ("dialog_not_wired", "dialog_preview_moves", AL, [("            cb.toggled.connect(self.refresh)\n            cur.currentIndexChanged", "            cur.currentIndexChanged")]),
    ("apply_cancels", "dialog_apply_one_undo", AL, [("            _state[\"opts\"] = self.options()   # the next Align starts from these (Max remembers them)\n            self.session.apply()",
                                                      "            _state[\"opts\"] = self.options()   # the next Align starts from these (Max remembers them)\n            self.session.cancel()")]),
    ("cancel_keeps", "dialog_cancel_exact", AL, [("        else:\n            self.session.cancel()\n        _finished()\n        super().done(r)\n\n\nclass NormalDialog",
                                                  "        else:\n            pass\n        _finished()\n        super().done(r)\n\n\nclass NormalDialog")]),
    ("selected_target_taken", "selected_target_refused", AL, [("    if pid in st[\"sel\"]:\n        LOG.info(\"align pick missed: the hit", "    if False:\n        LOG.info(\"align pick missed: the hit")]),
    ("alt_taken", "alt_click_passes", AL, [("        if viewer is None or mods & Qt.AltModifier or viewer.currentState()", "        if viewer is None or viewer.currentState()")]),
    ("view_state_taken", "view_state_click_passes", AL, [(" or viewer.currentState() in pieces_ui.VIEW_STATES:\n            return False   # Alt+drag", ":\n            return False   # Alt+drag")]),
    ("esc_ignored", "esc_ends_pick", AL, [("        if ev.key() == Qt.Key_Escape:", "        if False:")]),
    ("rmb_ignored", "right_click_ends_pick", AL, [("        if ev.button() == Qt.RightButton:", "        if False:")]),
    ("no_quick_key", "quick_align_key", "keys", [('    ("h", "h.pf_modelui_quick_align", "Alt+Ctrl+Shift+A"),\n', "")]),
    ("no_normal_key", "normal_align_clicks", "keys", [('    ("h", "h.pf_modelui_normal_align", "Alt+Ctrl+N"),\n', "")]),
    ("quick_not_committed", "quick_align_key", AL, [('        commit(quick([item(p) for p in st["sel"]], item(pid)), "quick align")', "        pass")]),
    ("normal_src_is_target", "normal_align_clicks", AL, [('NormalSession(st["sel"], st["src"], h)', 'NormalSession(st["sel"], h, h)')]),
    ("menu_does_nothing", "menu_starts_align", AL, [('    """Align Selection: pick the target, then the dialog."""\n    return _start("align")', '    """Align Selection: pick the target, then the dialog."""\n    return False')]),
    ("off_keeps_pick", "off_ends_pick", AL, [("    _state[\"on\"] = False\n    _end_pick()\n    d = _state", "    _state[\"on\"] = False\n    d = _state"),
                                                 ("        _end_pick()   # a dialog closed while", "        pass   # a dialog closed while")]),
    ("shelf_cross_missing", "shelf_cross_cursor_real", AL, [("        QtWidgets.QApplication.setOverrideCursor(Qt.CrossCursor)", "        QtWidgets.QApplication.setOverrideCursor(Qt.ArrowCursor)")]),
    ("no_dialog_before_pick", "shelf_dialog_open_before_pick", AL, [('        _show(AlignDialog(AlignSession(sel), "pick target", _state["opts"], hou.qt.mainWindow()))', '        _state["dialog"] = AlignDialog(AlignSession(sel), "pick target", _state["opts"], hou.qt.mainWindow())')]),
    ("miss_not_logged", "align_miss_logs_reason", AL, [('        LOG.info("align pick missed: %s", why)\n', "")]),
    ("cancel_keeps_pick", "cancel_during_pick_ends_all", AL, [("        _end_pick()   # a dialog closed while", "        pass   # a dialog closed while")]),
    ("pick_from_clicked_widget", "pick_under_overlay_widget", "pieces_ui", [("    gl = _viewer_gl(sv)\n    if gl is not None:", "    gl = hou.qt.mainWindow().childAt(hou.qt.mainWindow().mapFromGlobal(g))\n    if gl is not None:")]),
    ("target_not_set", "shelf_target_click_picks_box", AL, [("        self.session.set_target(pid)\n", "")]),
    ("no_preview_on_target", "shelf_preview_moves_tube", AL, [("        self.refresh()\n        self.setWindowModality", "        self.setWindowModality")]),
    ("shelf_cancel_keeps", "shelf_cancel_restores", AL, [("        else:\n            self.session.cancel()\n        _finished()\n        super().done(r)\n\n\nclass NormalDialog",
                                                         "        else:\n            pass\n        _finished()\n        super().done(r)\n\n\nclass NormalDialog")]),
    ("off_keeps_dialog", "off_cancels_dialog", AL, [("    if d is not None:\n        d.reject()", "    if d is not None:\n        pass")]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
if os.environ.get("PF_F1_QUICK"):
    RUNS = RUNS[:1]
if os.environ.get("PF_F2D_ONLY"):
    RUNS = [RUNS[0]] + [m for m in MUTATIONS if m[0] in os.environ["PF_F2D_ONLY"].split(",")]
RESULTS = []


def driver():
    STATE["desk0"] = hou.ui.curDesktop().name()
    STATE["keys0"] = keys.snapshot()
    for name, check, modname, pairs in RUNS:
        cleanup()
        restore, out = None, {}
        try:
            if modname:
                restore = mutate(modname, pairs)
            yield from suite(out)
        except Exception:  # noqa: BLE001
            out["_exception"] = traceback.format_exc()
        finally:
            cleanup()   # with the mutant still loaded: its own dialog and pick end first
            if restore:
                restore()
        out = {k: v if isinstance(v, str) else bool(v) for k, v in out.items()}   # numpy bools are not JSON
        RESULTS.append({"mutation": name, "check": check, "out": out})
        log(name or "baseline", check, out.get(check) if check else out)
        yield 200
    with open(OUT, "w") as f:
        json.dump(RESULTS, f, indent=1)


def pump(gen):
    try:
        delay = next(gen)
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
