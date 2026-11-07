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
import os
import traceback

import hdefereval
import hou
from hutil.Qt import QtCore, QtWidgets
from PySide6.QtTest import QTest

from polyfactory.modelui import containers, input_layer, pieces_ui, scene, switch

OUT = os.environ["PF_F1_OUT"]
LOGF = open(OUT + ".log", "w", buffering=1)
Qt = QtCore.Qt
LMB, NOM, SHIFT = Qt.LeftButton, Qt.NoModifier, Qt.ShiftModifier
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


def suite(out):
    hou.hipFile.clear(suppress_save_prompt=True)
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
    yield from press_drag(screen_point(sv, gl, tr(bound0))[0], NOM)
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
    gh = screen_point(sv, gl, tr(pieces_ui._state["bound"]))[0]   # a click on the handle itself
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
    s.select([mid])
    yield 300

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
    hou.hipFile.clear(suppress_save_prompt=True)
    pieces_ui.install()
    c3 = containers.create()
    i3 = containers.add_pieces(c3, [(FILES[3], "last", None)])[0]
    s.select([("piece", c3.sessionId(), i3)])   # a live handle null when modelUI goes off
    yield 300
    s.select([])
    s.select([("piece", c3.sessionId(), i3)])   # and a deferred follow still queued at uninstall
    if "polyfactory.modelui.pieces_ui" not in switch.FEATURES:
        pieces_ui.uninstall()
    switch.uninstall()
    yield 300
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


def cleanup():
    _q(pieces_ui.uninstall)
    _q(_purge_stale)
    _q(switch.uninstall)
    _q(lambda: hou.ui.desktop(STATE["desk0"]).setAsCurrent())
    switch._state["on"] = False


MODS = {"pieces_ui": pieces_ui, "input_layer": input_layer, "containers": containers}


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


PS = "pieces_ui"
MUTATIONS = [   # (mutation, the check it must redden, module, [(old, new)])
    ("no_proxy", "proxy_ready", PS, [('        _state["drawable"].enable(True)', '        _state["drawable"] = None')]),
    ("null_at_install", "no_handle_null_until_bound", PS, [("    _set_containers_selectable(False)\n    sv = hou.ui.curDesktop()", "    _set_containers_selectable(False)\n    _state['proxy'] = _new_proxy(hou.hmath.identityTransform())\n    sv = hou.ui.curDesktop()")]),
    ("houdini_sees_container_press", "container_click_taken", PS, [('        return True if _state["click"]["own"] else input_layer.OBSERVE', '        return input_layer.OBSERVE')]),
    ("proxy_reused_unfiltered", "undo_after_rebind_keeps_other", PS, [("            old.destroy()", "            pass"),
                                                                   ('    if pid is None or _state["writing"] or kw.get("node") != _state["proxy"]:   # a new wrapper each call: compare, never "is"', '    if pid is None or _state["writing"]:')]),
    ("redo_lost", "redo_restores_drag", PS, [("        set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get(\"rel\", {}).items()]))", "        with hou.undos.disabler():\n            set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get(\"rel\", {}).items()]))")]),
    ("typed_write_no_undo", "typed_value_one_undo", PS, [("        set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get(\"rel\", {}).items()]))", "        with hou.undos.disabler():\n            set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get(\"rel\", {}).items()]))")]),
    ("follow_after_uninstall", "uninstall_clean", PS, [("    if not _state[\"on\"]:   # a deferred follow that outlived uninstall", "    if False:   # a deferred follow that outlived uninstall")]),
    ("typed_ignored", "typed_values_move_piece", PS, [("        set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get(\"rel\", {}).items()]))", "        pass")]),
    ("save_keeps_null", "saved_without_handle_null", PS, [("        bind(None)   # the null never goes into a hip", "        pass")]),
    ("no_piece_pick", "pick_piece", PS, [('    return ("piece", c.sessionId(), geo.prim(prim).attribValue("pf_piece")) if prim >= 0 else None', "    return None")]),
    ("pick_not_shared", "explorer_follows_pick", PS, [("    sc.select(new)\n    return hit", "    _state['bound'] = hit\n    return hit")]),
    ("proxy_not_placed", "proxy_bound_to_pick", PS, [("            n.setWorldTransform(m)", "            pass"),
                                                      ("                    p.setWorldTransform(m)", "                    pass")]),
    ("highlight_never_shown", "highlight_shows_pick", PS, [("    d.setGeometry(g)\n    d.show(True)\n    _state[\"shown_box\"] = b", "    pass")]),
    ("highlight_never_hidden", "highlight_hidden_when_empty", PS, [("        d.show(False)\n        _state[\"shown_box\"] = None\n        return", "        return")]),
    ("no_object_pick", "pick_object", PS, [("        hit = n.sessionId()", "        hit = _state[\"bound\"]")]),
    ("empty_keeps_selection", "pick_empty_clears", PS, [("        new = [hit] if hit is not None else []", "        new = [hit] if hit is not None else cur")]),
    ("proxy_not_followed", "handle_drag_moves", PS, [("        set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get(\"rel\", {}).items()]))", "        pass")]),
    ("drag_write_no_undo", "handle_drag_one_undo", PS, [("        set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get(\"rel\", {}).items()]))", "        with hou.undos.disabler():\n            set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get(\"rel\", {}).items()]))")]),
    ("no_copy", "shift_drag_copies", PS, [('                st["moving"] = {i: copy_of(i) for i in st["items"]} if st["shift"] else {i: i for i in st["items"]}', '                st["moving"] = {i: i for i in st["items"]}'), ('        targets = {i: (copy_of(i) if st["shift"] else i) for i in st["items"]}', '        targets = {i: i for i in st["items"]}')]),
    ("original_follows", "shift_drag_original_stays", PS, [('        targets = {i: (copy_of(i) if st["shift"] else i) for i in st["items"]}', '        targets = {i: i for i in st["items"]}')]),
    ("copy_two_undo_steps", "shift_drag_one_undo", PS, [('    with hou.undos.group("modelUI: copy" if st["shift"] else "modelUI: move"):', '    if True:')]),
    ("no_threshold", "shift_click_no_copy", PS, [("COPY_PX = 4", "COPY_PX = 0")]),
    ("body_not_ours", "body_drag_moves", PS, [('        elif containers.is_container(n) and (shift or viewer.currentState() in MOVE_STATES):', '        elif containers.is_container(n) and shift:')]),
    ("body_drag_keeps_selection", "body_drag_selects", PS, [("    scene.current().select(list(targets.values()))", "    pass")]),
    ("preview_not_restored", "body_drag_one_undo", PS, [('            set_xforms(dict(st["start"]))', '            pass')]),
    ("add_replaces", "shift_click_adds", PS, [('    if mode == "add":\n        new = cur + [hit]', '    if False:\n        new = cur + [hit]')]),
    ("remove_replaces", "ctrl_click_removes", PS, [('    elif mode == "remove":\n        new = [p for p in cur if p != hit]', '    elif False:\n        new = [p for p in cur if p != hit]')]),
    ("box_no_pieces", "box_select_pieces", PS, [("    boxed = [pid for pid, (x, y) in piece_centres(vp).items() if lo_x <= x <= hi_x and lo_y <= y <= hi_y]", "    boxed = []")]),
    ("only_bound_follows", "handle_moves_all_pieces", PS, [('        set_xforms(dict([(pid, m)] + [(p, r * m) for p, r in _state.get("rel", {}).items()]))', '        set_xforms({pid: m})')]),
    ("proxy_clears_objects", "handle_moves_selected_object", PS, [("        n.setSelected(True)   # selected objects stay selected", "        n.setSelected(True, clear_all_selected=True)   # selected objects stay selected")]),
    ("body_drags_one", "body_drag_moves_all", PS, [("        items = sel if pid in sel else [pid]", "        items = [pid]")]),
    ("copies_only_grabbed", "shift_drag_copies_all", PS, [('        targets = {i: (copy_of(i) if st["shift"] else i) for i in st["items"]}', '        targets = {i: (copy_of(i) if st["shift"] and i == st["pid"] else i) for i in st["items"]}')]),
    ("copies_split_undo", "shift_drag_all_one_undo", PS, [('    with hou.undos.group("modelUI: copy" if st["shift"] else "modelUI: move"):', '    if True:')]),
    ("box_from_origin", "highlight_shows_pick", PS, [("            hi = [max(p_[i] for p_ in pts) for i in range(3)]", "            hi = [max([0.0] + [p_[i] for p_ in pts]) for i in range(3)]")]),
    ("flag_saved", "saved_containers_selectable", PS, [("        _set_containers_selectable(True)   # nor the unselectable flag", "        pass   # nor the unselectable flag")]),
    ("handle_click_replaces", "handle_click_keeps_selection", PS, [('            return _state["bound"]   # a plain click', '            pass   # a plain click')]),
    ("modifier_on_handle_ignored", "ctrl_click_removes", PS, [('        for c in containers.containers():   # with Shift/Ctrl: the piece behind the handle', '        for c in []:   # with Shift/Ctrl: the piece behind the handle')]),
    ("demo_always_on", "ctrl_shift_click_toggles", "input_layer", [('    if os.environ.get("PF_MODELUI_DEMO") == "1":\n        add_gesture("demo_drag", DEMO)', '    if True:\n        add_gesture("demo_drag", DEMO)')]),
    ("no_toggle", "ctrl_shift_click_toggles", PS, [('    elif mode == "toggle":\n        new = [p for p in cur if p != hit] if hit in cur', '    elif False:\n        new = [p for p in cur if p != hit] if hit in cur')]),
    ("proxy_kept", "uninstall_clean", PS, [("                n.destroy()", "                pass")]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
if os.environ.get("PF_F1_QUICK"):
    RUNS = RUNS[:1]
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
