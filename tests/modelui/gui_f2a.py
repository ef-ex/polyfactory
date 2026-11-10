"""GUI checks of modelUI F2a (pieces_ui: click pick, Houdini's handle on a proxy, Shift+drag Copy), run INSIDE a
throwaway Houdini.

Start it with:  PF_GUI_SCRIPT=gui_f2a.py python tests/modelui/run_gui_f1.py   (own prefs, only the polyfactory package,
every window off screen, exits by itself, never saves a .hip). Input goes the real path: QtTest on the viewer's
QWindow, at the pixel where the viewport shows the piece (``mapToScreen``). Baseline, one run per mutation in
MUTATIONS (a source edit exec'd into the live module), baseline again; results to $PF_F1_OUT.

What it cannot see: the look of the handle and the highlight (no image is judged), rotate/scale drags (only the
translate drag is driven; E/R are checked as modes), multi-viewport layouts (single perspective view), hip reload.
"""
import glob
import json
import math
import os
import traceback

import hdefereval
import hou
from hutil.Qt import QtCore, QtGui, QtWidgets
from PySide6.QtTest import QTest

from polyfactory.modelui import clone, containers, input_layer, kitbash, pieces_ui, scene, switch

OUT = os.environ["PF_F1_OUT"]
LOGF = open(OUT + ".log", "w", buffering=1)
Qt = QtCore.Qt
LMB, NOM, SHIFT = Qt.LeftButton, Qt.NoModifier, Qt.ShiftModifier
APP = QtWidgets.QApplication.instance()
FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))
STATE = {"desk0": None}


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
    r = sv.qtScreenGeometry()
    gl = mw.childAt(mw.mapFromGlobal(r.center()))
    return sv, gl


def screen_point(sv, gl, world):
    """Global Qt point where the viewport draws ``world`` (viewport pixels: origin bottom left, device pixels)."""
    vp = sv.curViewport()
    v = vp.mapToScreen(hou.Vector3(world))
    size = vp.size()
    h = size[-1]
    dpr = gl.devicePixelRatioF()
    return gl.mapToGlobal(QtCore.QPoint(int(round(v[0] / dpr)), int(round((h - v[1]) / dpr)))), (int(v[0]), int(v[1]))


class _Probe(QtCore.QObject):
    def __init__(self, seen):
        super().__init__()
        self.seen = seen

    def eventFilter(self, obj, ev):  # noqa: N802
        self.seen.append(int(ev.type()))
        return False


def L(win, g, dx=0, dy=0):
    return win.mapFromGlobal(g) + QtCore.QPoint(dx, dy)


def xf(t=(0, 0, 0)):
    return hou.hmath.buildTranslate(t)


def tr(pid):
    return pieces_ui.get_xform(pid).extractTranslates()


def clear_hip():
    """hipFile.clear, retried: under load Houdini runs our timers inside a long cook, and clear() then refuses ("Node
    cook is in progress", 2026-11-10)."""
    for _ in range(100):
        try:
            hou.hipFile.clear(suppress_save_prompt=True)
            return
        except hou.OperationFailed:
            yield 100
    hou.hipFile.clear(suppress_save_prompt=True)


def suite(out):
    yield from clear_hip()
    c = containers.create()
    big = hou.hmath.buildScale(10, 10, 10)   # the library piece is 1 x 0.17 x 0.25: make it a target a click can hit
    ids = containers.add_pieces(c, [(FILES[3], "left", big * xf((-15, 0, 0))), (FILES[3], "mid", big),
                                    (FILES[3], "right", big * xf((15, 0, 0)))])
    loose = hou.node("/obj").createNode("geo", "loose")
    loose.createNode("box").parm("scale").set(2)
    loose.parmTuple("t").set((0, 0, 9))
    mid, left = ("piece", c.sessionId(), ids[1]), ("piece", c.sessionId(), ids[0])
    yield 100
    ok = switch.install()
    if "polyfactory.modelui.pieces_ui" not in switch.FEATURES:   # until it ships in the switch (then F1 reruns with it)
        pieces_ui.install()
    yield 1200
    sv, gl = viewer()
    log("  viewer at start: state", sv.currentState(), "gl", gl.width(), gl.height())
    sv.setViewportLayout(hou.geometryViewportLayout.Single)
    vp = sv.curViewport()
    vp.changeType(hou.geometryViewportType.Perspective)
    yield 300
    vp.frameAll()
    yield 400
    win = gl.window().windowHandle()
    marked = lambda: [n for n in hou.node("/obj").children() if n.userData(pieces_ui.PROXY_MARK) == "1"]   # noqa: E731
    out["proxy_ready"] = bool(ok) and pieces_ui._state["drawable"] is not None
    out["no_handle_null_until_bound"] = marked() == []
    s = scene.current()

    def click_at(world, mods=NOM):
        g, px = screen_point(sv, gl, world)
        QTest.mouseMove(win, L(win, g))
        QTest.mouseClick(win, LMB, mods, L(win, g))
        return px

    pr_mid = [p for p in c.displayNode().geometry().prims() if p.attribValue("pf_piece") == ids[1]][0]
    centre = pr_mid.boundingBox().center()
    sv.setCurrentState("select")   # in "pose" the body-drag gesture takes container presses anyway: test the click
    yield 300
    seen = []
    flt = _Probe(seen)
    win.installEventFilter(flt)   # an object filter on the window: it sees what our application filter let through
    n_undo = len(hou.undos.undoLabels())
    px = click_at(centre)
    win.removeEventFilter(flt)
    out["container_click_taken"] = int(QtCore.QEvent.MouseButtonPress) not in seen
    yield 300
    log("  pick mid at", px, "selected", s.selected(), "bound", pieces_ui._state["bound"], "last pick",
        pieces_ui._state.get("last_pick"), "ray", pieces_ui._state.get("last_ray"), "bbox", centre)
    out["pick_piece"] = s.selected() == [mid]
    panel = getattr(hou.session, "_pf_modelui_explorer", None)
    out["explorer_follows_pick"] = panel is not None and panel.selected_ids() == [mid]
    box, want_box = None, None   # (checked below on a piece far from the origin)
    _unused_hl = (box is not None and want_box is not None
                                   and (box.minvec() - want_box.minvec()).length() < 1e-4
                                   and (box.maxvec() - want_box.maxvec()).length() < 1e-4)
    pr_left = [p for p in c.displayNode().geometry().prims() if p.attribValue("pf_piece") == ids[0]][0]
    click_at(pr_left.boundingBox().center())
    yield 300
    pr_l = [p for p in c.displayNode().geometry().prims() if p.attribValue("pf_piece") == ids[0]][0]
    mw_l = pr_l.fullTransform() * c.worldTransform()   # an independent box: the piece's own points in world space
    wpts = [p.position() * mw_l for p in pr_l.getEmbeddedGeometry().points()]
    lo_w = [min(v[i] for v in wpts) for i in range(3)]
    hi_w = [max(v[i] for v in wpts) for i in range(3)]
    shown = pieces_ui._state.get("shown_box")
    out["highlight_shows_pick"] = (shown is not None and abs(lo_w[0]) > 5
                                   and all(abs(shown.minvec()[i] - lo_w[i]) < 1e-3 for i in range(3))
                                   and all(abs(shown.maxvec()[i] - hi_w[i]) < 1e-3 for i in range(3)))
    log("  highlight", shown, "points box", lo_w, hi_w)
    px_ = pieces_ui.proxy()
    out["proxy_bound_to_pick"] = (pieces_ui._state["bound"] == left and px_ is not None and px_.isSelected()
                                  and (px_.worldTransform().extractTranslates() - tr(left)).length() < 1e-4)
    s.select([mid])   # a piece selected: only our pick (not Houdini's own click) can turn it into the object
    yield 300
    click_at(loose.worldTransform().extractTranslates() + hou.Vector3(0, 0, 0))
    yield 300
    out["pick_object"] = s.selected() == [loose.sessionId()]
    s.select([mid])   # only our pick can clear a piece selection
    yield 300
    g0 = gl.mapToGlobal(QtCore.QPoint(6, 6))   # a viewport corner: nothing there
    QTest.mouseMove(win, L(win, g0))
    QTest.mouseClick(win, LMB, NOM, L(win, g0))
    yield 300
    log("  empty click: last pick", pieces_ui._state.get("last_pick"), "selected", s.selected())
    out["pick_empty_clears"] = s.selected() == []
    # A4: the select([mid]) above took the object out of Houdini's node selection; that must not be an undo entry
    # that restores only the node part (pieces cannot be undone)
    out["pick_adds_no_undo_entry"] = "modelUI: select" not in hou.undos.undoLabels()
    out["highlight_hidden_when_empty"] = pieces_ui._state.get("shown_box") is None

    # --- handle drag (W) on the selected piece, one undo step ----------------------------------------------------------
    click_at(centre)
    yield 300
    log("  before W: bound", pieces_ui._state["bound"],
        "selected", [n.path() for n in hou.node("/obj").children() if n.isSelected()], "state", sv.currentState())
    QTest.keyClick(win, Qt.Key_W)
    for _ in range(20):   # the session's first entry into "pose" builds the handle: press only once it is up
        if sv.currentState() == "pose":
            break
        yield 100
    vp.draw()
    yield 500
    t0 = tr(mid)
    c0 = c.worldTransform()
    px0 = pieces_ui.proxy()
    p0 = px0.worldTransform().extractTranslates() if px0 is not None else hou.Vector3()
    w0, u0 = pieces_ui._state.get("writes", 0), len(hou.undos.undoLabels())
    g, _ = screen_point(sv, gl, t0)
    QTest.mouseMove(win, L(win, g))
    QTest.mousePress(win, LMB, NOM, L(win, g))
    for k in range(1, 7):
        QTest.mouseMove(win, L(win, g, 10 * k, 0))
        yield 30   # real input: Houdini's event loop runs between mouse moves (timers, later())
    QTest.mouseRelease(win, LMB, NOM, L(win, g, 60, 0))
    yield 400
    t1 = tr(mid)
    log("  drag mid", tuple(t0), "->", tuple(t1), "proxy", tuple(p0), "->",
        pieces_ui.proxy() and tuple(pieces_ui.proxy().worldTransform().extractTranslates()), "proxy writes", pieces_ui._state.get("writes", 0) - w0,
        "undo entries", len(hou.undos.undoLabels()) - u0, hou.undos.undoLabels()[:3], "selected nodes",
        [n.path() for n in hou.selectedNodes()], "state", sv.currentState())
    # the PIECE moved through the proxy: the container itself stays where it was (Houdini's handle on the container
    # would also move the piece's world position)
    # the handle follows the cursor on screen: the piece moves most of the 60 px drag (world distance depends on how
    # far frameAll puts the camera, which varies between runs: 0.47 or 2.84 units for the same drag)
    q0, q1 = screen_point(sv, gl, t0)[1], screen_point(sv, gl, t1)[1]
    drag_px = ((q1[0] - q0[0]) ** 2 + (q1[1] - q0[1]) ** 2) ** 0.5
    log("  drag on screen %.1f px" % drag_px)
    out["handle_drag_moves"] = (drag_px > 30 and pieces_ui._state.get("writes", 0) > w0
                                and all(abs(a - b) < 1e-9 for a, b in zip(c.worldTransform().asTuple(), c0.asTuple())))
    tl = tr(left)
    click_at(pr_left.boundingBox().center())   # the handle goes to another piece, then undo
    yield 300
    hou.undos.performUndo()
    yield 300
    out["handle_drag_one_undo"] = (tr(mid) - t0).length() < 1e-3
    live = pieces_ui.proxy()
    out["undo_after_rebind_keeps_other"] = ((tr(left) - tl).length() < 1e-4 and pieces_ui._state["bound"] == left
                                            and live is not None
                                            and (live.worldTransform().extractTranslates() - tr(left)).length() < 1e-4)
    undone = tr(mid)
    hou.undos.performRedo()
    yield 200
    out["redo_restores_drag"] = (undone - t0).length() < 1e-3 and (tr(mid) - t1).length() < 1e-3
    hou.undos.performUndo()
    yield 200
    log("  undo after rebind: mid", tuple(tr(mid)), "left", tuple(tl), "->", tuple(tr(left)))
    click_at(centre)
    yield 300
    log("  state after W", sv.currentState())
    right = ("piece", c.sessionId(), ids[2])   # typed values on their own piece: nothing to undo for the rest
    s.select([right])
    yield 300
    px2 = pieces_ui.proxy()
    tr0 = pieces_ui.get_xform(right)
    if px2 is not None:
        px2.parmTuple("t").set((20, 1, 2))
        yield 100
        moved_typed = (tr(right) - hou.Vector3(20, 1, 2)).length() < 1e-4
        pieces_ui.bind(None)   # the null goes (as when another piece is picked): undo must restore the piece itself
        hou.undos.performUndo()
        yield 200
        out["typed_value_one_undo"] = moved_typed and all(abs(a - b) < 1e-4 for a, b in zip(
            pieces_ui.get_xform(right).asTuple(), tr0.asTuple()))
        s.select([])
        s.select([right])
        yield 300
        px2 = pieces_ui.proxy()
    if px2 is not None:
        px2.parmTuple("t").set((20, 1, 2))
        px2.parmTuple("r").set((0, 45, 0))
        px2.parmTuple("s").set((2, 2, 2))
        yield 200
    out["typed_values_move_piece"] = px2 is not None and all(
        abs(a - b) < 1e-4 for a, b in zip(pieces_ui.get_xform(right).asTuple(), px2.worldTransform().asTuple()))
    s.select([mid])
    yield 300

    # --- drag a piece's body in the move tool (Max): ours, one undo step --------------------------------------------
    tl0 = tr(left)
    gl_left, _ = screen_point(sv, gl, tl0)
    c_before = c.worldTransform()
    QTest.mouseMove(win, L(win, gl_left))
    QTest.mousePress(win, LMB, NOM, L(win, gl_left))
    for k in range(1, 7):
        QTest.mouseMove(win, L(win, gl_left, 10 * k, 0))
        yield 30
    QTest.mouseRelease(win, LMB, NOM, L(win, gl_left, 60, 0))
    yield 400
    q0, q1 = screen_point(sv, gl, tl0)[1], screen_point(sv, gl, tr(left))[1]
    body_px = ((q1[0] - q0[0]) ** 2 + (q1[1] - q0[1]) ** 2) ** 0.5
    log("  body drag on screen %.1f px" % body_px, "selected", s.selected())
    out["body_drag_moves"] = body_px > 30 and all(abs(a - b) < 1e-9 for a, b in zip(c.worldTransform().asTuple(), c_before.asTuple()))
    out["body_drag_selects"] = s.selected() == [left]
    hou.undos.performUndo()
    yield 200
    out["body_drag_one_undo"] = body_px > 30 and (tr(left) - tl0).length() < 1e-4
    s.select([mid])
    yield 300

    # --- Shift+drag on the handle = Copy; the original stays ----------------------------------------------------------
    n0 = len(containers.piece_rows(c))
    t0 = tr(mid)
    spy = []
    orig_g = input_layer._gestures.get("modelui_copy_drag")

    def spy_g(kind, ev, viewer):
        r = orig_g(kind, ev, viewer)
        spy.append((kind, int(ev.modifiers().value) if hasattr(ev.modifiers(), "value") else str(ev.modifiers()),
                    viewer is not None, pieces_ui._state["bound"], r))
        return r
    if orig_g is not None:
        input_layer._gestures["modelui_copy_drag"] = spy_g
    g, _ = screen_point(sv, gl, t0)
    QTest.mouseMove(win, L(win, g))
    log("  at shift press: selected", [n.path() for n in hou.node("/obj").children() if n.isSelected()],
        "proxy", pieces_ui.proxy() and tuple(pieces_ui.proxy().worldTransform().extractTranslates()), "piece", tuple(t0),
        "bound", pieces_ui._state["bound"], "state", sv.currentState())
    QTest.mousePress(win, LMB, SHIFT, L(win, g))
    for k in range(1, 7):
        QTest.mouseMove(win, L(win, g, 10 * k, 0))
        yield 30   # real input: Houdini's event loop runs between mouse moves (timers, later())
    QTest.mouseRelease(win, LMB, SHIFT, L(win, g, 60, 0))
    yield 400
    if orig_g is not None:
        input_layer._gestures["modelui_copy_drag"] = orig_g
    log("  copy gesture calls", spy[:8], "gestures", list(input_layer._gestures), "drag", pieces_ui._state.get("drag"))
    rows = containers.piece_rows(c)
    new = [r[0] for r in rows if r[0] not in ids]
    sel = s.selected()
    try:
        log("  shift drag: pieces", n0, "->", len(rows), "selected", sel, "orig", tuple(t0), "->", tuple(tr(mid)))
    except KeyError:
        log("  shift drag: the original piece is gone")
    try:
        out["shift_drag_copies"] = (len(rows) == n0 + 1 and len(new) == 1 and sel == [("piece", c.sessionId(), new[0])]
                                    and (tr(sel[0]) - t0).length() > 0.5)
    except KeyError:   # the selected piece is gone: no copy
        out["shift_drag_copies"] = False
    try:
        out["shift_drag_original_stays"] = (tr(mid) - t0).length() < 1e-3
    except KeyError:
        out["shift_drag_original_stays"] = False
    hou.undos.performUndo()
    yield 200
    out["shift_drag_one_undo"] = len(containers.piece_rows(c)) == n0 and (tr(mid) - t0).length() < 1e-3
    s.select([mid])
    yield 200
    if os.environ.get("PF_F2A_SKIP") == "shiftclick":   # diagnosis only
        out["shift_click_no_copy"] = True
        yield 1
    g, _ = screen_point(sv, gl, tr(mid))
    QTest.mouseMove(win, L(win, g))
    QTest.mousePress(win, LMB, SHIFT, L(win, g))
    QTest.mouseMove(win, L(win, g, 1, 0))
    yield 30
    QTest.mouseMove(win, L(win, g, 2, 1))   # a click's jitter
    yield 30
    QTest.mouseRelease(win, LMB, SHIFT, L(win, g, 2, 1))
    yield 300
    out["shift_click_no_copy"] = len(containers.piece_rows(c)) == n0
    # --- multi-selection (audit item 9b) --------------------------------------------------------------------------
    right = ("piece", c.sessionId(), ids[2])

    def at(pid):
        return screen_point(sv, gl, tr(pid))[0]

    def press_drag(g0, mods, steps=6, dx=10, dy=0):
        QTest.mouseMove(win, L(win, g0))
        QTest.mousePress(win, LMB, mods, L(win, g0))
        for k in range(1, steps + 1):
            QTest.mouseMove(win, L(win, g0, dx * k, dy * k))
            yield 30
        QTest.mouseRelease(win, LMB, mods, L(win, g0, dx * steps, dy * steps))
        yield 400

    s.select([mid])
    yield 300
    QTest.mouseMove(win, L(win, at(left)))
    QTest.mouseClick(win, LMB, SHIFT, L(win, at(left)))
    yield 300
    out["shift_click_adds"] = sorted(s.selected()) == sorted([mid, left])
    QTest.mouseMove(win, L(win, at(left)))
    QTest.mouseClick(win, LMB, Qt.ControlModifier, L(win, at(left)))
    yield 300
    out["ctrl_click_removes"] = s.selected() == [mid]
    s.select([left])   # one piece: the handle sits on it, the Ctrl-click lands on the handle's null
    yield 300
    QTest.mouseMove(win, L(win, at(left)))
    QTest.mouseClick(win, LMB, Qt.ControlModifier, L(win, at(left)))
    yield 300
    out["ctrl_click_on_handle_removes"] = s.selected() == []
    log("  ctrl click on handle: under", pieces_ui._state.get("last_pick"), "selected", s.selected())
    sv.setCurrentState("select")
    s.select([])
    yield 300
    ga = screen_point(sv, gl, tr(left) + hou.Vector3(-10, 0, 0))[0] + QtCore.QPoint(0, -40)
    gb = screen_point(sv, gl, (tr(mid) + tr(right)) * 0.5)[0] + QtCore.QPoint(0, 40)
    d = gb - ga
    yield from press_drag(ga, NOM, steps=8, dx=d.x() / 8.0, dy=d.y() / 8.0)
    log("  box from", ga, "to", gb, "selected", s.selected())
    out["box_select_pieces"] = sorted(p for p in s.selected() if isinstance(p, tuple)) == sorted([left, mid])
    s.select([])
    yield 300
    s.select([left, mid, loose.sessionId()])   # mixed: two pieces and an object (the handle null is made after it)
    yield 300
    QTest.keyClick(win, Qt.Key_W)
    for _ in range(20):
        if sv.currentState() == "pose":
            break
        yield 100
    vp.draw()   # re-entering "pose" builds the handle: press only once it is up
    yield 500
    l0, m0, o0 = tr(left), tr(mid), loose.worldTransform().extractTranslates()
    bound0 = pieces_ui._state["bound"]
    yield from press_drag(screen_point(sv, gl, pieces_ui.proxy().worldTransform().extractTranslates())[0], NOM)
    dl, dm, do = tr(left) - l0, tr(mid) - m0, loose.worldTransform().extractTranslates() - o0
    log("  handle moves all:", tuple(dl), tuple(dm), tuple(do), "bound", bound0)
    out["handle_moves_all_pieces"] = dl.length() > 0.1 and (dl - dm).length() < 1e-3
    out["handle_moves_selected_object"] = dl.length() > 0.1 and (dl - do).length() < 1e-3
    s.select([left, mid])
    yield 300
    l0, m0 = tr(left), tr(mid)
    yield from press_drag(at(mid), NOM)
    dl, dm = tr(left) - l0, tr(mid) - m0
    out["body_drag_moves_all"] = dm.length() > 0.1 and (dl - dm).length() < 1e-3
    n1 = len(containers.piece_rows(c))
    l0, m0 = tr(left), tr(mid)
    yield from press_drag(at(mid), SHIFT)
    rows1 = len(containers.piece_rows(c))
    sel1 = s.selected()
    out["shift_drag_copies_all"] = (rows1 == n1 + 2 and len(sel1) == 2 and left not in sel1 and mid not in sel1
                                    and (tr(left) - l0).length() < 1e-4 and (tr(mid) - m0).length() < 1e-4)
    hou.undos.performUndo()
    yield 200
    out["shift_drag_all_one_undo"] = len(containers.piece_rows(c)) == n1
    s.select([left, mid])
    yield 300
    for tries in range(30):   # wait until the handle is drawn there (a loaded PC drew it late: 2026-11-09 final baseline)
        gh = screen_point(sv, gl, pieces_ui.proxy().worldTransform().extractTranslates())[0]   # a click on the handle
        hn = pieces_ui._under(sv, gh)[3]
        if hn is not None and hn.userData(pieces_ui.PROXY_MARK) == "1":
            break
        vp.draw()
        yield 100
    log("  handle under the click after", tries, "waits:", hn and hn.path())
    QTest.mouseMove(win, L(win, gh))
    QTest.mouseClick(win, LMB, NOM, L(win, gh))
    yield 300
    out["handle_click_keeps_selection"] = sorted(s.selected()) == sorted([left, mid])
    CS2 = Qt.ControlModifier | Qt.ShiftModifier
    QTest.mouseMove(win, L(win, at(left)))
    QTest.mouseClick(win, LMB, CS2, L(win, at(left)))
    yield 300
    t1_ = s.selected() == [mid]
    log("  toggle 1:", s.selected(), "press under", pieces_ui._state.get("last_pick"), "bound", pieces_ui._state["bound"])
    QTest.mouseClick(win, LMB, CS2, L(win, at(left)))
    yield 300
    log("  toggle 2:", s.selected(), "press under", pieces_ui._state.get("last_pick"), "bound", pieces_ui._state["bound"])
    out["ctrl_shift_click_toggles"] = t1_ and sorted(s.selected()) == sorted([left, mid])
    gl.setFocus()
    QTest.keyClick(win, Qt.Key_W)
    yield 400
    s.select([mid])
    yield 300

    # --- audit 2 comfort items: 7 pivot, 8 body drag planes / snap / objects, 10 Q drag box ---------------------
    lid = loose.sessionId()
    sv.setCurrentState("select")
    yield 300
    s.select([])
    yield 200
    s.select([left, mid, lid])
    yield 400

    def wbox(pid):   # independent of pieces_ui: the piece's points (or the object's geometry) in world space
        if isinstance(pid, tuple):
            pr = [q for q in c.displayNode().geometry().prims() if q.attribValue("pf_piece") == pid[2]][0]
            mm = pr.fullTransform() * c.worldTransform()
            pts = [q.position() * mm for q in pr.getEmbeddedGeometry().points()]
        else:
            nn = hou.nodeBySessionId(pid)
            pts = [q.position() * nn.worldTransform() for q in nn.displayNode().geometry().points()]
        return [min(v[i] for v in pts) for i in range(3)], [max(v[i] for v in pts) for i in range(3)]
    bxs = [wbox(i) for i in (left, mid, lid)]
    cen3 = hou.Vector3([(min(b_[0][k] for b_ in bxs) + max(b_[1][k] for b_ in bxs)) / 2.0 for k in range(3)])
    s.select([left, mid])
    yield 300
    want_boxes = [wbox(i) for i in (left, mid)]
    shown = pieces_ui._state.get("shown_boxes") or []
    out["highlight_all_selected"] = len(shown) == 2 and all(
        any(all(abs(sb.minvec()[k] - w[0][k]) < 1e-3 and abs(sb.maxvec()[k] - w[1][k]) < 1e-3 for k in range(3))
            for sb in shown) for w in want_boxes)
    s.select([left, mid, lid])
    yield 400
    px3 = pieces_ui.proxy()
    out["pivot_at_selection_centre"] = (px3 is not None
                                        and (px3.worldTransform().extractTranslates() - cen3).length() < 1e-3)
    saved = {i: pieces_ui.get_xform(i) for i in (left, mid, lid)}
    p_before = {i: tr(i) for i in (left, mid, lid)}
    if px3 is not None:
        px3.parmTuple("r").set((0, 90, 0))   # the handle's rotation (what a rotate drag writes), about the pivot
        yield 300
    rot = hou.hmath.buildRotate((0, 90, 0))
    errs = [(tr(i) - (cen3 + (p0_ - cen3) * rot)).length() for i, p0_ in p_before.items()]
    out["mixed_rotate_about_pivot"] = px3 is not None and max(errs) < 1e-3
    log("  pivot", tuple(cen3), "proxy", px3 and tuple(px3.worldTransform().extractTranslates()), "rotate errors", errs)
    s.select([])
    yield 300
    with hou.undos.disabler():
        pieces_ui.set_xforms(saved)
    QTest.keyClick(win, Qt.Key_W)
    for _ in range(20):
        if sv.currentState() == "pose":
            break
        yield 100
    yield 300
    m0 = tr(mid)
    yield from press_drag(at(mid), NOM, steps=4, dx=0, dy=10)
    dmv = tr(mid) - m0
    out["body_drag_on_ground"] = dmv.length() > 0.1 and abs(dmv[1]) < 1e-4
    log("  ground drag", tuple(dmv))
    hou.undos.performUndo()
    yield 200
    s.select([])   # a long drag past the horizon with the camera looking 12 degrees down
    cam = vp.defaultCamera()
    r0 = cam.rotation()
    cam.setRotation(hou.hmath.buildRotate(12, 0, 0).extractRotationMatrix3())   # +X: looking down; horizon in view
    vp.frameAll()
    yield 500
    vx, vy, vw, vh = vp.size()
    fwd_d, cam_o = vp.mapToWorld(vw // 2, vh // 2)
    fwd, cam_o = hou.Vector3(fwd_d).normalized(), hou.Vector3(cam_o)
    m0 = tr(mid)
    g0h = at(mid)
    up = (gl.mapToGlobal(QtCore.QPoint(0, 8)).y() - g0h.y()) / 8.0   # to just inside the viewport's top edge
    yield from press_drag(g0h, NOM, steps=8, dx=0, dy=up)
    gfin = g0h + QtCore.QPoint(0, int(up * 8))
    _vp, fx, fy = pieces_ui.viewport_at(sv, gl, gfin)
    crossed = _vp is not None and hou.Vector3(vp.mapToWorld(fx, fy)[0])[1] > 0   # the cursor ended above the horizon
    rel = tr(mid) - cam_o
    out["drag_past_horizon_stays_in_front"] = (crossed and rel.dot(fwd) > 0
                                               and rel.length() < 25 * (m0 - cam_o).length())
    log("  horizon drag: crossed", crossed, "piece", tuple(tr(mid)), "camera", tuple(cam_o), "in front", rel.dot(fwd))
    hou.undos.performUndo()
    cam.setRotation(r0)
    vp.frameAll()
    yield 400
    s.select([])   # no handle on mid: the press must reach the piece's body
    yield 300
    cpl, rpl = sv.constructionPlane(), sv.referencePlane()
    cp_vis, rp_cell = cpl.isVisible(), rpl.cellSize()
    cpl.setIsVisible(False)
    rpl.setCellSize((0.5, 0.5))   # the grid the user sees: Ctrl moves by its cell
    step = 0.5
    yield 200
    m0 = tr(mid)
    yield from press_drag(at(mid), Qt.ControlModifier, steps=4, dx=13, dy=7)
    dmv = tr(mid) - m0
    cpl.setIsVisible(cp_vis)
    rpl.setCellSize(rp_cell)
    out["ctrl_drag_snaps"] = dmv.length() > 0.1 and all(abs(v / step - round(v / step)) < 1e-3 for v in dmv)
    log("  snapped drag", tuple(dmv), "step", step)
    hou.undos.performUndo()
    yield 200
    # E: a body drag turns the selection about the view axis through its pivot; R: scales it uniformly (Max)
    s.select([])
    yield 200
    s.select([left, mid])
    yield 300
    gl.setFocus()
    QTest.keyClick(win, Qt.Key_E)
    yield 600
    bxs2 = [wbox(i) for i in (left, mid)]
    piv = hou.Vector3([(min(b_[0][k] for b_ in bxs2) + max(b_[1][k] for b_ in bxs2)) / 2.0 for k in range(3)])
    _vx, _vy, vw_, vh_ = vp.size()
    axis = (piv - hou.Vector3(vp.mapToWorld(vw_ // 2, vh_ // 2)[1])).normalized()
    p_b = {i: tr(i) for i in (left, mid)}
    yield from press_drag(at(mid), NOM, steps=6, dx=10, dy=0)
    oks = []
    for i, pb in p_b.items():
        a_, b2 = pb - piv, tr(i) - piv
        a_p, b_p = a_ - axis * a_.dot(axis), b2 - axis * b2.dot(axis)
        ang = math.degrees(math.acos(max(-1.0, min(1.0, a_p.normalized().dot(b_p.normalized())))))
        oks.append(abs(a_.length() - b2.length()) < 1e-3 and abs((tr(i) - pb).dot(axis)) < 1e-3 and abs(ang - 30) < 1.5)
        log("  E drag", i, "angle %.2f" % ang, "radius", a_.length(), b2.length())
    out["e_body_drag_rotates"] = all(oks)
    hou.undos.performUndo()
    yield 200
    gl.setFocus()
    QTest.keyClick(win, Qt.Key_R)
    yield 600
    p_b = {i: tr(i) for i in (left, mid)}
    s_b = {i: pieces_ui.get_xform(i).explode()["scale"] for i in (left, mid)}
    yield from press_drag(at(mid), NOM, steps=6, dx=10, dy=0)
    ratio = (tr(left) - piv).length() / (p_b[left] - piv).length()
    uni = all(abs(pieces_ui.get_xform(i).explode()["scale"][k] / s_b[i][k] - ratio) < 1e-3 for i in (left, mid) for k in range(3))
    out["r_body_drag_scales"] = (ratio > 1.2 and abs((tr(mid) - piv).length() / (p_b[mid] - piv).length() - ratio) < 1e-3
                                 and uni)
    log("  R drag ratio %.4f" % ratio, "uniform", uni)
    hou.undos.performUndo()
    yield 200
    gl.setFocus()
    QTest.keyClick(win, Qt.Key_W)
    yield 400
    s.select([])
    yield 200
    lo0 = tr(lid)
    yield from press_drag(at(lid), NOM, steps=4, dx=10, dy=0)
    dlo = tr(lid) - lo0
    out["body_drag_moves_object"] = dlo.length() > 0.1 and s.selected() == [lid]
    hou.undos.performUndo()
    yield 200
    vp.changeType(hou.geometryViewportType.Front)
    yield 300
    vp.frameAll()
    yield 400
    l0 = tr(left)
    yield from press_drag(at(left), NOM, steps=4, dx=0, dy=-10)
    dlv = tr(left) - l0
    out["ortho_drag_view_plane"] = abs(dlv[1]) > 0.1 and abs(dlv[2]) < 1e-4
    log("  front view drag", tuple(dlv))
    hou.undos.performUndo()
    vp.changeType(hou.geometryViewportType.Perspective)
    yield 300
    vp.frameAll()
    yield 400
    QTest.keyClick(win, Qt.Key_Q)
    for _ in range(20):
        if sv.currentState() != "pose":
            break
        yield 100
    yield 300
    s.select([])
    yield 200
    m0 = tr(mid)
    ga, gl_ = at(mid), at(left)
    gb = gl_ + QtCore.QPoint(-60, 60 if gl_.y() >= ga.y() else -60)
    d = gb - ga
    yield from press_drag(ga, NOM, steps=6, dx=d.x() / 6.0, dy=d.y() / 6.0)
    out["q_drag_on_piece_boxes"] = left in s.selected() and (tr(mid) - m0).length() < 1e-6
    s.select([right])   # Shift+drag from a piece in Q: adds by box (Houdini's Shift), never copies
    yield 300
    nq = len(containers.piece_rows(c))
    yield from press_drag(ga, SHIFT, steps=6, dx=d.x() / 6.0, dy=d.y() / 6.0)
    out["q_shift_drag_adds_by_box"] = (len(containers.piece_rows(c)) == nq and right in s.selected()
                                       and left in s.selected())
    log("  Q shift drag: pieces", nq, "->", len(containers.piece_rows(c)), "selected", s.selected())
    log("  Q drag on a piece: state", sv.currentState(), "selected", s.selected())
    QTest.keyClick(win, Qt.Key_W)
    for _ in range(20):
        if sv.currentState() == "pose":
            break
        yield 100
    s.select([mid])
    yield 300

    # --- other buttons, Esc, cancel and switch-off during a body drag (F2a audit 4) ---------------------------------
    # A spy on the viewer's window sees what our layer let through (the application filter runs first) and swallows
    # it, so a let-through mutation cannot leave Houdini's undo group open for every later run (audit 4: once open it
    # stays open). Blind spot: Houdini's reaction to a button that gets through (audit 4 probe3 E4/E4b showed it: MMB
    # starts its handle drag, "Cannot undo within an undo group"); the real focus signal (lay.cancel() is what it calls;
    # F1's key_cancel_on_focus_window covers the signal).
    # PF_F2A_SPY_PASS=1 (evidence mode, run with PF_F2A_ONLY=other_button_passes): the spy lets a middle button
    # through to Houdini, so under the mutation the real failure (Houdini's undo group left open) must show in the check.
    spy_pass = os.environ.get("PF_F2A_SPY_PASS") == "1"
    seen = []
    MOUSE_T = (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease, QtCore.QEvent.MouseButtonDblClick)

    spy_all = [False]   # also the left button and moves: what modelUI declines never reaches Houdini either
    hide_left = [False]   # drag_case: a left drag modelUI did not take (a mutation) or gave up (cancel, off, lost
    # release) never reaches Houdini: a half-seen drag left Houdini's undo group open for every later run (2026-11-09,
    # proxy_reused_unfiltered: the body press landed on a kept handle null, the synthetic lost release did the rest)

    class Spy(QtCore.QObject):
        def eventFilter(self, obj, ev):  # noqa: N802
            if hide_left[0] and ev.type() in MOUSE_T + (QtCore.QEvent.MouseMove,) and (
                    ev.type() == QtCore.QEvent.MouseMove or ev.button() == LMB):
                return True
            if spy_all[0] and ev.type() in MOUSE_T + (QtCore.QEvent.MouseMove,):
                if ev.type() != QtCore.QEvent.MouseMove:
                    seen.append((str(ev.type()), str(ev.button())))
                return True
            if ev.type() in MOUSE_T and ev.button() != LMB:
                seen.append((str(ev.type()), str(ev.button())))
                return not (spy_pass and ev.button() == Qt.MiddleButton)
            return False
    spy = Spy()
    win.installEventFilter(spy)

    def drag_case(tag, acts, mods=NOM, release=True, steps=4, dx=10, after=None):
        s.select([left])   # the handle sits on left: the drag grabs mid's body
        yield 300
        m0, r0, u0 = tr(mid), len(containers.piece_rows(c)), len(hou.undos.undoLabels())
        g0 = screen_point(sv, gl, pieces_ui.bounds(mid).center() + hou.Vector3(-3, 0, 0))[0]
        del seen[:]
        QTest.mouseMove(win, L(win, g0))
        hide_left[0] = True
        QTest.mousePress(win, LMB, mods, L(win, g0))
        for k in range(1, steps + 1):
            QTest.mouseMove(win, L(win, g0, dx * k, 0))
            yield 30
            if k in acts:
                acts[k](g0)
                yield 100
        held, real_later = [], input_layer.later
        if release:
            if after is not None:   # QTest's release runs pending timers: hold the deferred commit back
                input_layer.later = held.append
            try:
                QTest.mouseRelease(win, LMB, mods, L(win, g0, dx * steps, 0))
            finally:
                input_layer.later = real_later
        if after is not None:
            after()   # between the release and the deferred commit
            for f in held:
                f()
        yield 400
        hide_left[0] = False
        labels = hou.undos.undoLabels()
        r = {"moved": (tr(mid) - m0).length(), "rows": len(containers.piece_rows(c)) - r0,
             "new": list(labels[:len(labels) - u0]), "seen": list(seen), "open": undo_open(),
             "gl": (gl.width(), gl.height(), sv.currentState())}
        if r["open"] is None and r["new"]:
            hou.undos.performUndo()
            yield 300
        r["after_undo"] = (tr(mid) - m0).length()
        r["rows_after_undo"] = len(containers.piece_rows(c)) - r0
        log("  " + tag, r)
        return r

    def committed_once(r):
        return (r["open"] is None and r["seen"] == [] and r["new"] == ["modelUI: move"] and r["moved"] > 0.1
                and r["after_undo"] < 1e-6)

    def untouched(r):
        return r["open"] is None and r["new"] == [] and r["moved"] < 1e-6 and r["rows"] == 0

    def btn(b, how):
        return lambda g0: how(win, b, NOM, L(win, g0, 20, 0))

    MMB, RMB = Qt.MiddleButton, Qt.RightButton
    r = yield from drag_case("mmb", {1: btn(MMB, QTest.mousePress), 2: btn(MMB, QTest.mouseRelease),
                                     3: btn(MMB, QTest.mouseDClick)})
    out["middle_click_mid_drag_swallowed"] = committed_once(r)
    r = yield from drag_case("rmb", {1: btn(RMB, QTest.mousePress), 3: btn(RMB, QTest.mouseRelease)})
    out["right_click_mid_drag_swallowed"] = committed_once(r)
    r = yield from drag_case("mmb_held_past_release", {2: btn(MMB, QTest.mousePress)})
    QTest.mouseRelease(win, MMB, NOM, L(win, at(right)))   # the middle button comes up after the drag ended
    yield 200
    out["middle_release_after_drag_swallowed"] = committed_once(r) and seen == []
    # No Esc case: Esc has no modelUI code path (the 2026-11-08 runs logged it: the drag commits once, no open group),
    # and under some mutations Houdini's Esc left "pose" for "objview", which changed the next run's framing (mid's
    # pixel (332, 294) -> (339, 291) / (332, 312)) and turned camera-dependent checks of every later run wrong.
    r = yield from drag_case("cancel", {4: lambda g0: input_layer.layer().cancel()})   # what a focus loss calls
    out["cancel_mid_drag_restores"] = untouched(r) and r["seen"] == []
    # --- audit 5 -----------------------------------------------------------------------------------------------------
    lay = input_layer.layer()
    # 2: a gesture that raises mid-drag gets "cancel" (its preview goes). The raise is injected into set_xforms once.
    real_set = pieces_ui.set_xforms

    def boom(*a, **k):
        pieces_ui.set_xforms = real_set
        raise RuntimeError("gui_f2a: injected gesture error")
    try:
        r = yield from drag_case("raise", {2: lambda g0: setattr(pieces_ui, "set_xforms", boom)})
    finally:
        pieces_ui.set_xforms = real_set
    out["gesture_error_reverts_preview"] = untouched(r) and lay.owners["mouse"] is None

    # 5a: with no drag, other buttons reach Houdini (the spy sees press and release of each).
    s.select([left])
    yield 300
    gmid = screen_point(sv, gl, pieces_ui.bounds(mid).center() + hou.Vector3(-3, 0, 0))[0]
    del seen[:]
    QTest.mouseMove(win, L(win, gmid))
    for b in (Qt.MiddleButton, Qt.RightButton):
        QTest.mousePress(win, b, NOM, L(win, gmid))
        yield 50
        QTest.mouseRelease(win, b, NOM, L(win, gmid))
        yield 50
    log("  no drag, MMB and RMB seen by the window:", seen)
    out["no_drag_buttons_reach_houdini"] = len(seen) == 4

    # 3: a lost release (the left button and an eaten middle button both come up unseen), then a new middle click
    # with no drag: its release must reach Houdini (not be eaten by the stale entry).
    def lost_release(g0):
        APP.sendEvent(win, QtGui.QMouseEvent(QtCore.QEvent.MouseMove, QtCore.QPointF(L(win, g0, 35, 0)),
                                             QtCore.QPointF(g0 + QtCore.QPoint(35, 0)), Qt.NoButton, Qt.NoButton, NOM))
    r = yield from drag_case("lost", {1: btn(Qt.MiddleButton, QTest.mousePress), 3: lost_release}, release=False)
    log("  after the lost release: eaten", lay.eaten["mouse"])
    # a move with the button up clears the entry (as here); the audit's case had none between: seed it (blind spot:
    # how the entry survives in the wild, audit 5 probe L_altmmb_after_lost)
    QTest.mouseRelease(win, Qt.MiddleButton, NOM, L(win, gmid))   # QTest's own button state: a press of a button it
    QTest.mouseRelease(win, LMB, NOM, L(win, gmid))                # holds sends a release first (Houdini gets strays)
    yield 300
    lay.eaten["mouse"].add(Qt.MiddleButton)
    del seen[:]
    QTest.mousePress(win, Qt.MiddleButton, NOM, L(win, gmid))
    log("  seeded, after the new middle press: eaten", lay.eaten["mouse"], "owner", lay.owners)
    yield 50
    QTest.mouseRelease(win, Qt.MiddleButton, NOM, L(win, gmid))
    yield 50
    yield 300
    log("  after a lost release, a middle click: seen", seen, "eaten", lay.eaten["mouse"])
    out["stale_eaten_cleared_by_press"] = untouched(r) and len(seen) == 2 and not lay.eaten["mouse"]

    # 4: a left press while another button is down is Houdini's: it gets past modelUI (the spy sees it, and hides the
    # whole gesture from Houdini: a half-seen chord left Houdini's drag, and its undo group, open).
    s.select([left])
    yield 300
    m0 = tr(mid)
    QTest.mouseMove(win, L(win, gmid))
    spy_all[0] = True
    del seen[:]
    QTest.mousePress(win, Qt.MiddleButton, NOM, L(win, gmid))
    yield 50
    QTest.mousePress(win, LMB, NOM, L(win, gmid))
    owned = lay.owners["mouse"] is not None
    left_seen = ("MouseButtonPress" in str(seen[-1][0]) or seen[-1][0] == str(QtCore.QEvent.MouseButtonPress)) and "Left" in seen[-1][1] if seen else False
    for k in range(1, 5):
        QTest.mouseMove(win, L(win, gmid, 10 * k, 0))
        yield 30
    QTest.mouseRelease(win, LMB, NOM, L(win, gmid, 40, 0))
    yield 50
    QTest.mouseRelease(win, Qt.MiddleButton, NOM, L(win, gmid, 40, 0))
    yield 50
    spy_all[0] = False
    yield 350
    log("  left press with the middle down: owned", owned, "left press seen", left_seen, "seen", seen,
        "mid moved", (tr(mid) - m0).length(), "undo open", undo_open())
    out["left_with_other_down_declined"] = not owned and left_seen and (tr(mid) - m0).length() < 1e-6
    if (tr(mid) - m0).length() > 1e-6:
        hou.undos.performUndo()
        yield 300

    # 1: Space+LMB on a piece turns Houdini's camera in W and in Q (Space puts the viewer in its view state).
    def space_drag(tag):
        s.select([left])   # the handle on left: the press lands on mid's body (a container)
        yield 300
        g0 = screen_point(sv, gl, pieces_ui.bounds(mid).center() + hou.Vector3(-3, 0, 0))[0]
        cam = vp.defaultCamera().stash()
        QTest.mouseMove(win, L(win, g0))
        QTest.keyPress(win, Qt.Key_Space)
        yield 300
        st_, under_ = sv.currentState(), pieces_ui._under(sv, g0)[3]
        v0, m0_, u0 = vp.viewTransform(), tr(mid), len(hou.undos.undoLabels())
        QTest.mousePress(win, LMB, NOM, L(win, g0))
        own = lay.owners["mouse"] is not None
        for k in range(1, 6):
            QTest.mouseMove(win, L(win, g0, 8 * k, 4 * k))
            yield 30
        QTest.mouseRelease(win, LMB, NOM, L(win, g0, 40, 20))
        yield 300
        QTest.keyRelease(win, Qt.Key_Space)
        yield 400
        turned = max(abs(a - b) for a, b in zip(vp.viewTransform().asTuple(), v0.asTuple()))
        log("  space+LMB", tag, "state", st_, "under", under_ and under_.path(), "owned", own, "view change", turned,
            "mid moved", (tr(mid) - m0_).length(), "undo", len(hou.undos.undoLabels()) - u0)
        vp.setDefaultCamera(cam)   # the next run frames from this camera: put it back exactly
        yield 300
        return (under_ is not None and containers.is_container(under_) and not own and turned > 1e-3 and (tr(mid) - m0_).length() < 1e-6
                and sv.currentState() == st0 and undo_open() is None)
    st0 = sv.currentState()
    ok_w = yield from space_drag("W")
    QTest.keyClick(win, Qt.Key_Q)
    for _ in range(20):
        if sv.currentState() == "select":
            break
        yield 100
    st0 = sv.currentState()
    ok_q = yield from space_drag("Q")
    QTest.keyClick(win, Qt.Key_W)
    for _ in range(20):
        if sv.currentState() == "pose":
            break
        yield 100
    vp.draw()
    yield 500
    out["space_lmb_on_piece_turns_camera"] = ok_w and ok_q

    # 5b: modelUI off between the release and the deferred commit: the preview goes, nothing is committed.
    r = yield from drag_case("off_pending", {}, after=lambda: (pieces_ui.uninstall(), lay.cancel()))
    pieces_ui.install()
    yield 300
    out["off_before_commit_restores"] = untouched(r)

    # modelUI off mid-drag as switch.uninstall() does it (pieces_ui first, then the input layer's shutdown cancels the
    # owner), without the desk switch: an extra desk switch per run drifted the viewport size over a full run
    # (2026-11-08: mid's pixel moved from (332, 294) to (265, 270) and the camera-dependent checks went wrong).
    # Blind spot: the desk switch itself (the end of this suite and F1's checks switch for real).
    r = yield from drag_case("off_shift", {4: lambda g0: (pieces_ui.uninstall(), input_layer.layer().cancel())},
                             mods=SHIFT)
    out["off_mid_drag_restores"] = untouched(r)
    win.removeEventFilter(spy)
    pieces_ui.install()
    yield 300

    # --- Add kitbash pieces: the row lands where the viewport looks (kitbash.look_at; the rest: check_kitbash.py) ---
    cam0 = vp.defaultCamera().stash()
    cam = vp.defaultCamera().stash()
    cam.setPivot((7.0, 3.0, -4.0))
    vp.setDefaultCamera(cam)
    yield 200
    u0 = len(hou.undos.undoLabels())
    kb = kitbash.add_files([FILES[3]])
    yield 200
    kbb = pieces_ui.bounds(kb[0])
    log("  kitbash at look-at: centre", tuple(kbb.center()), "min y", kbb.minvec()[1], "undo +", len(hou.undos.undoLabels()) - u0)
    out["kitbash_at_look_at"] = (abs(kbb.center()[0] - 7.0) < 1e-3 and abs(kbb.center()[2] + 4.0) < 1e-3
                                 and abs(kbb.minvec()[1]) < 1e-3 and s.selected() == kb)
    hou.undos.performUndo()
    vp.setDefaultCamera(cam0)
    yield 300

    # --- Clone dialog: its fields reach clone() (never shown here; the cloning itself: check_clone.py) -----------------
    s.select([mid])
    yield 300
    rows0, m0 = len(containers.piece_rows(c)), tr(mid)
    dlg = clone.CloneDialog()
    s.select([left])   # the dialog is not modal: it clones what was selected when it opened (mid)
    yield 200
    dlg.kind["instance"].setChecked(True)
    dlg.count.setValue(3)
    for box_, v in zip(dlg.move + dlg.rotate, (2.0, 0.0, 0.0, 0.0, 0.0, 0.0)):
        box_.setValue(v)
    dlg.scale.setValue(100.0)
    dlg.accept()
    yield 300
    sel = s.selected()
    kinds = [p_.stringAttribValue("pf_clone_kind") for p_ in containers.points(c).points()
             if ("piece", c.sessionId(), p_.intAttribValue("pf_piece")) in sel]
    log("  clone dialog: rows", rows0, "->", len(containers.piece_rows(c)), "kinds", kinds,
        "last moved", tuple(tr(sel[-1]) - m0) if sel else None)
    out["clone_dialog_ok"] = (len(containers.piece_rows(c)) == rows0 + 3 and kinds == ["instance"] * 3
                              and (tr(sel[-1]) - m0 - hou.Vector3(6, 0, 0)).length() < 1e-3)
    hou.undos.performUndo()
    dlg.deleteLater()
    yield 200

    skip_save = os.environ.get("PF_F2A_SKIP") == "save"   # diagnosis only
    path = os.path.dirname(OUT) + "/save_check.hip"   # a throwaway hip in this run's own folder
    s.select([mid])
    yield 300
    if not skip_save:
        hou.hipFile.save(path)
    yield 300
    bound_after = pieces_ui._state["bound"]
    pieces_ui.uninstall()   # read the file as it was written (our load cleanup would hide a saved null)
    if not skip_save:
        hou.hipFile.load(path, suppress_save_prompt=True)
    yield 300
    out["saved_without_handle_null"] = marked() == [] and bound_after == mid
    out["saved_containers_selectable"] = bool(containers.containers()) and all(
        cc.isSelectableInViewport() for cc in containers.containers())   # plain Houdini can click them
    yield from clear_hip()
    pieces_ui.install()
    c3 = containers.create()
    i3 = containers.add_pieces(c3, [(FILES[3], "last", None)])[0]
    s.select([("piece", c3.sessionId(), i3)])   # a live handle null when modelUI goes off
    yield 300
    s.select([])
    s.select([("piece", c3.sessionId(), i3)])   # and a deferred follow still queued at uninstall
    # Houdini refuses to delete a node while it cooks (2026-11-09 final baseline: the uninstall's delete hit a cook,
    # the null stayed and the rest of uninstall did not run). Here the first delete of a handle null fails like that.
    node_cls = type(hou.node("/obj"))
    real_destroy, failed = node_cls.destroy, []

    def busy_destroy(n, *a, **k):
        if not failed and n.userData(pieces_ui.PROXY_MARK) == "1":
            failed.append(n.path())
            raise hou.OperationFailed("gui_f2a: Cannot delete nodes while cooking")
        return real_destroy(n, *a, **k)
    node_cls.destroy = busy_destroy
    try:
        if "polyfactory.modelui.pieces_ui" not in switch.FEATURES:
            pieces_ui.uninstall()
        switch.uninstall()
    finally:
        node_cls.destroy = real_destroy
    yield 600
    log("  busy delete at uninstall:", failed, "marked after", [n.path() for n in marked()])
    out["uninstall_retries_busy_delete"] = (bool(failed) and marked() == [] and all(
        cc.isSelectableInViewport() for cc in containers.containers()))
    log("  after uninstall: marked", [n.path() for n in marked()])
    out["uninstall_clean"] = (not any(n.userData(pieces_ui.PROXY_MARK) == "1" for n in hou.node("/obj").children())
                              and "modelui_click_pick" not in input_layer._gestures)


def _q(f):
    try:
        f()
    except Exception:  # noqa: BLE001
        log("  cleanup:", traceback.format_exc().splitlines()[-1])


def _purge_stale():
    """A mutation re-executes pieces_ui's source into the live module: the functions an EARLIER version registered (scene
    watchers, hip file callbacks) stay registered and keep acting on their own state. Remove every one of them."""
    mod = "polyfactory.modelui.pieces_ui"
    sc = scene.current()
    for w in list(sc._watchers):
        if getattr(w, "__module__", "") == mod:
            sc.unwatch(w)
    for cb in list(hou.hipFile.eventCallbacks()):
        if getattr(cb, "__module__", "") == mod:
            hou.hipFile.removeEventCallback(cb)
    with hou.undos.disabler():
        for n in list(hou.node("/obj").children()):
            if n.userData(pieces_ui.PROXY_MARK) == "1":
                n.destroy()


def undo_open():
    """None when undo works; else Houdini's error (an undo group left open, e.g. by an unfinished handle drag)."""
    n = hou.node("/obj").createNode("null", "pf_undo_probe")
    try:
        hou.undos.performUndo()
    except hou.Error as e:
        if hou.node("/obj/pf_undo_probe") is not None:
            with hou.undos.disabler():
                n.destroy()
        return e.instanceMessage().strip().splitlines()[-1]
    return None if hou.node("/obj/pf_undo_probe") is None else "undo did not remove the probe"


def cleanup():
    leak = undo_open()
    if leak:
        mw = hou.qt.mainWindow()
        QTest.mouseRelease(mw.windowHandle(), LMB, NOM, QtCore.QPoint(5, 5))   # ends an unfinished drag, if any
        log("  UNDO LEAK before cleanup:", leak, "-> after a mouse release:", undo_open())
    _q(pieces_ui.uninstall)
    _q(_purge_stale)
    _q(switch.uninstall)
    _q(lambda: hou.ui.desktop(STATE["desk0"]).setAsCurrent())
    switch._state["on"] = False


MODS = {"pieces_ui": pieces_ui, "input_layer": input_layer, "containers": containers, "scene": scene,
        "kitbash": kitbash, "clone": clone}


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
    inst = getattr(hou.session, "_pf_modelui_scene", None) if modname == "scene" else None
    if inst is not None:   # the cached scene object (the Explorer holds it too) takes the mutant's class
        inst.__class__ = mod.MixedScene

    def restore():
        exec(compile(src, mod.__file__, "exec"), mod.__dict__)
        if inst is not None:
            inst.__class__ = mod.MixedScene
    return restore


PS = "pieces_ui"
MUTATIONS = [   # (mutation, the check it must redden, module, [(old, new)])
    ("no_proxy", "proxy_ready", PS, [('        _state["drawable"].enable(True)', '        _state["drawable"] = None')]),
    ("null_at_install", "no_handle_null_until_bound", PS, [("    _set_containers_selectable(False)\n    sv = hou.ui.curDesktop()", "    _set_containers_selectable(False)\n    _state['proxy'] = _new_proxy(hou.hmath.identityTransform())\n    sv = hou.ui.curDesktop()")]),
    ("houdini_sees_container_press", "container_click_taken", PS, [('        return True if _state["click"]["own"] else input_layer.OBSERVE', '        return input_layer.OBSERVE')]),
    ("proxy_reused_unfiltered", "undo_after_rebind_keeps_other", PS, [("            old.destroy()", "            pass"),
                                                                   ('    if pid is None or _state["writing"] or kw.get("node") != _state["proxy"]:   # a new wrapper each call: compare, never "is"', '    if pid is None or _state["writing"]:')]),
    ("redo_lost", "redo_restores_drag", PS, [("        set_xforms({i: r * m for i, r in _state.get(\"rel\", {}).items()})", "        with hou.undos.disabler():\n            set_xforms({i: r * m for i, r in _state.get(\"rel\", {}).items()})")]),
    ("typed_write_no_undo", "typed_value_one_undo", PS, [("        set_xforms({i: r * m for i, r in _state.get(\"rel\", {}).items()})", "        with hou.undos.disabler():\n            set_xforms({i: r * m for i, r in _state.get(\"rel\", {}).items()})")]),
    ("follow_after_uninstall", "uninstall_clean", PS, [("    if not _state[\"on\"]:   # a deferred follow that outlived uninstall", "    if False:   # a deferred follow that outlived uninstall")]),
    ("typed_ignored", "typed_values_move_piece", PS, [("        set_xforms({i: r * m for i, r in _state.get(\"rel\", {}).items()})", "        pass")]),
    ("save_keeps_null", "saved_without_handle_null", PS, [("        bind(None)   # the null never goes into a hip", "        pass")]),
    ("no_piece_pick", "pick_piece", PS, [('    return ("piece", c.sessionId(), geo.prim(prim).attribValue("pf_piece")) if prim >= 0 else None', "    return None")]),
    ("pick_not_shared", "explorer_follows_pick", PS, [("    sc.select(new)\n    return hit", "    _state['bound'] = hit\n    return hit")]),
    ("proxy_not_placed", "proxy_bound_to_pick", PS, [("            n.setWorldTransform(m)", "            pass"),
                                                      ("                    p.setWorldTransform(m)", "                    pass")]),
    ("highlight_never_shown", "highlight_shows_pick", PS, [("    d.setGeometry(g)\n    d.show(True)\n    _state[\"shown_box\"] = b", "    pass")]),
    ("highlight_never_hidden", "highlight_hidden_when_empty", PS, [("        d.show(False)\n        _state[\"shown_box\"] = None\n        return", "        return")]),
    ("no_object_pick", "pick_object", PS, [("        hit = n.sessionId()", "        hit = _state[\"bound\"]")]),
    ("empty_keeps_selection", "pick_empty_clears", PS, [("        new = [hit] if hit is not None else []", "        new = [hit] if hit is not None else cur")]),
    ("proxy_not_followed", "handle_drag_moves", PS, [("        set_xforms({i: r * m for i, r in _state.get(\"rel\", {}).items()})", "        pass")]),
    ("drag_write_no_undo", "handle_drag_one_undo", PS, [("        set_xforms({i: r * m for i, r in _state.get(\"rel\", {}).items()})", "        with hou.undos.disabler():\n            set_xforms({i: r * m for i, r in _state.get(\"rel\", {}).items()})")]),
    ("no_copy", "shift_drag_copies", PS, [('                st["moving"] = {i: copy_of(i) for i in st["items"]} if st["shift"] else {i: i for i in st["items"]}', '                st["moving"] = {i: i for i in st["items"]}'), ('        targets = {i: (copy_of(i) if st["shift"] else i) for i in st["items"]}', '        targets = {i: i for i in st["items"]}')]),
    ("original_follows", "shift_drag_original_stays", PS, [('        targets = {i: (copy_of(i) if st["shift"] else i) for i in st["items"]}', '        targets = {i: i for i in st["items"]}')]),
    ("copy_two_undo_steps", "shift_drag_one_undo", PS, [('    with hou.undos.group("modelUI: copy" if st["shift"] else "modelUI: move"):', '    if True:')]),
    ("no_threshold", "shift_click_no_copy", PS, [("COPY_PX = 4", "COPY_PX = 0")]),
    ("body_not_ours", "body_drag_moves", PS, [("        moving = viewer.currentState() in MOVE_STATES   # Q:", "        moving = False   # Q:")]),
    ("shift_copies_in_q", "q_shift_drag_adds_by_box", PS, [("        moving = viewer.currentState() in MOVE_STATES   # Q:", "        moving = shift or viewer.currentState() in MOVE_STATES   # Q:")]),
    ("behind_camera_kept", "drag_past_horizon_stays_in_front", PS, [("    if t <= 0 or t * d.length() > 20.0 * (origin - o).length():", "    if False:")]),
    ("only_bound_box", "highlight_all_selected", PS, [("        boxes = [bounds(p) for p in scene.current().selected()]", "        boxes = [b]")]),
    ("handle_on_first_item", "pivot_at_selection_centre", PS, [("    if len(items) == 1:\n        return get_xform(items[0])\n    boxes", "    if True:\n        return get_xform(items[0])\n    boxes")]),
    ("objects_not_driven", "mixed_rotate_about_pivot", PS, [("    _set_rel(items, proxy())", "    _set_rel([i for i in items if isinstance(i, tuple)], proxy())")]),
    ("offsets_wrong", "handle_moves_selected_object", PS, [("    _state[\"rel\"] = {o: get_xform(o) * inv for o in items}", "    _state[\"rel\"] = {o: get_xform(o) for o in items}")]),
    ("select_recorded", "pick_adds_no_undo_entry", "scene", [('hou.undos.disabler():   # not an undo entry: piece selection cannot be undone, so neither is this', 'hou.undos.group("modelUI: select"):')]),
    ("view_plane_in_persp", "body_drag_on_ground", PS, [("        normal = hou.Vector3(0, 1, 0) if persp and abs(view[1]) > 0.15 else view", "        normal = view")]),
    ("ground_in_ortho", "ortho_drag_view_plane", PS, [("        normal = hou.Vector3(0, 1, 0) if persp and abs(view[1]) > 0.15 else view", "        normal = hou.Vector3(0, 1, 0)")]),
    ("grid_hardcoded", "ctrl_drag_snaps", PS, [("        return float(sv.referencePlane().cellSize()[0]) or 1.0", "        return 0.1")]),
    ("e_drag_moves", "e_body_drag_rotates", PS, [('        if st["xmode"] in ("rotate", "scale"):', '        if False:')]),
    ("mode_keys_ignored", "e_body_drag_rotates", PS, [('        _state["xmode"] = XMODES[ev.text().upper()]', '        pass')]),
    ("r_not_uniform", "r_body_drag_scales", PS, [("                k = hou.hmath.buildScale(f, f, f)", "                k = hou.hmath.buildScale(f, 1, 1)")]),
    ("no_snap", "ctrl_drag_snaps", PS, [('            if st["snap"]:', '            if False:')]),
    ("objects_not_draggable", "body_drag_moves_object", PS, [('        elif n.type().name() == "geo" and n.userData(PROXY_MARK) != "1" and moving:', '        elif False:')]),
    ("q_drag_not_box", "q_drag_on_piece_boxes", PS, [('            st["box"] = st["empty"] or st["own"]', '            st["box"] = st["empty"]')]),
    ("body_drag_keeps_selection", "body_drag_selects", PS, [("    scene.current().select(list(targets.values()))", "    pass")]),
    ("preview_not_restored", "body_drag_one_undo", PS, [('            set_xforms(dict(st["start"]))', '            pass')]),
    ("add_replaces", "shift_click_adds", PS, [('    if mode == "add":\n        new = cur + [hit]', '    if False:\n        new = cur + [hit]')]),
    ("remove_replaces", "ctrl_click_removes", PS, [('    elif mode == "remove":\n        new = [p for p in cur if p != hit]', '    elif False:\n        new = [p for p in cur if p != hit]')]),
    ("box_no_pieces", "box_select_pieces", PS, [("    boxed = [pid for pid, (x, y) in piece_centres(vp).items() if lo_x <= x <= hi_x and lo_y <= y <= hi_y]", "    boxed = []")]),
    ("only_bound_follows", "handle_moves_all_pieces", PS, [('        set_xforms({i: r * m for i, r in _state.get("rel", {}).items()})', '        set_xforms({pid: m})')]),
    ("body_drags_one", "body_drag_moves_all", PS, [("        items = sel if pid in sel else [pid]", "        items = [pid]")]),
    ("copies_only_grabbed", "shift_drag_copies_all", PS, [('        targets = {i: (copy_of(i) if st["shift"] else i) for i in st["items"]}', '        targets = {i: (copy_of(i) if st["shift"] and i == st["pid"] else i) for i in st["items"]}')]),
    ("copies_split_undo", "shift_drag_all_one_undo", PS, [('    with hou.undos.group("modelUI: copy" if st["shift"] else "modelUI: move"):', '    if True:')]),
    ("box_from_origin", "highlight_shows_pick", PS, [("            hi = [max(p_[i] for p_ in pts) for i in range(3)]", "            hi = [max([0.0] + [p_[i] for p_ in pts]) for i in range(3)]")]),
    ("flag_saved", "saved_containers_selectable", PS, [("        _set_containers_selectable(True)   # nor the unselectable flag", "        pass   # nor the unselectable flag")]),
    ("handle_click_replaces", "handle_click_keeps_selection", PS, [('            return _state["bound"]   # a plain click', '            pass   # a plain click')]),
    ("modifier_on_handle_ignored", "ctrl_click_on_handle_removes", PS, [('        for c in containers.containers():   # with Shift/Ctrl: the piece behind the handle', '        for c in []:   # with Shift/Ctrl: the piece behind the handle')]),
    ("demo_always_on", "ctrl_shift_click_toggles", "input_layer", [('    if os.environ.get("PF_MODELUI_DEMO") == "1":\n        add_gesture("demo_drag", DEMO)', '    if True:\n        add_gesture("demo_drag", DEMO)')]),
    ("no_toggle", "ctrl_shift_click_toggles", PS, [('    elif mode == "toggle":\n        new = [p for p in cur if p != hit] if hit in cur', '    elif False:\n        new = [p for p in cur if p != hit] if hit in cur')]),
    ("proxy_kept", "uninstall_clean", PS, [("                n.destroy()", "                pass")]),
    ("dialog_live_selection", "clone_dialog_ok", "clone", [("        clone(self.pids, **v)", "        clone(scene.current().selected(), **v)")]),
    ("dialog_count_ignored", "clone_dialog_ok", "clone", [('"count": self.count.value()', '"count": 1')]),
    ("look_at_ignored", "kitbash_at_look_at", "kitbash", [("    p = sv.curViewport().defaultCamera().pivot()\n    return hou.Vector3(p[0], 0.0, p[2])", "    return hou.Vector3()")]),
    ("no_delete_retry", "uninstall_retries_busy_delete", PS, [("    if busy and tries:", "    if False:")]),
    ("cancel_on_error_dropped", "gesture_error_reverts_preview", "input_layer", [('            if dropped and kind != "cancel":', '            if False:')]),
    ("non_left_always_swallowed", "no_drag_buttons_reach_houdini", "input_layer", [('            if self.owners["mouse"] is not None:   # another button', '            if self.owners["mouse"] is not None or ev.button() != Qt.LeftButton:   # another button')]),
    ("eaten_kept_on_press", "stale_eaten_cleared_by_press", "input_layer", [('            self.eaten["mouse"].discard(ev.button())   # a new press', '            pass   # a new press')]),
    ("other_down_ignored", "left_with_other_down_declined", PS, [("            and ev.buttons() == Qt.LeftButton)", "            )")]),
    ("view_state_ignored", "space_lmb_on_piece_turns_camera", PS, [("viewer.currentState() not in VIEW_STATES", "True")]),
    ("off_ignores_pending", "off_before_commit_restores", PS, [('    st = _state["drag"] or _state["pending"]', '    st = _state["drag"]')]),
    ("other_button_passes", "middle_click_mid_drag_swallowed", "input_layer", [("                self.eaten[\"mouse\"].add(ev.button())   # (Houdini's", "                return False   # (Houdini's")]),
    ("other_button_passes_rmb", "right_click_mid_drag_swallowed", "input_layer", [("                self.eaten[\"mouse\"].add(ev.button())   # (Houdini's", "                return False   # (Houdini's")]),
    ("other_release_passes", "middle_click_mid_drag_swallowed", "input_layer", [("                    return True   # the rest of another button pressed during the owned drag", "                    return False   # the rest of another button pressed during the owned drag")]),
    ("eaten_lost_at_release", "middle_release_after_drag_swallowed", "input_layer", [("        if ev.button() == which:   # release\n            self._end(\"mouse\", o)", "        if ev.button() == which:   # release\n            self._end(\"mouse\", o)\n            self.eaten[\"mouse\"].clear()")]),
    ("cancel_commits", "cancel_mid_drag_restores", PS, [('        input_layer.later(lambda: _commit_drag(st, final, kind == "release"))', '        input_layer.later(lambda: _commit_drag(st, final, True))')]),
    ("off_keeps_preview", "off_mid_drag_restores", PS, [("        _revert_preview(st)\n    _state.update(bound=None", "        pass\n    _state.update(bound=None")]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
if os.environ.get("PF_F1_QUICK"):
    RUNS = RUNS[:1]
if os.environ.get("PF_F2A_ONLY"):   # diagnosis: one baseline and the named mutations
    RUNS = [RUNS[0]] + [m for m in MUTATIONS if m[0] in os.environ["PF_F2A_ONLY"].split(",")]
if os.environ.get("PF_F2A_TWICE"):   # diagnosis: two baselines in one session, no mutations
    RUNS = [RUNS[0], RUNS[-1]]
RESULTS = []


def driver():
    STATE["desk0"] = hou.ui.curDesktop().name()
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
            if restore:
                restore()
            cleanup()
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
