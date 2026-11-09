"""GUI checks of modelUI F1 (switch, keys, input layer, Scene Explorer), run INSIDE a throwaway Houdini.

Never run this in Hannes' session: start it with run_gui_f1.py (own prefs folder, only the polyfactory package, every
visible window off screen, exits by itself, never saves a .hip).

Input goes the real path: QtTest on the QWindow (Qt's system-event path: double-click detection, implicit grabs),
except where QtTest cannot make the event (auto-repeat, native scan codes, a lost release): those are sent to the
QWindow with sendEvent, which still passes the application filters at the window like real input.

The suite runs once as a baseline, then once per mutation in MUTATIONS (a source edit of one module, exec'd into the
live module and restored afterwards), then once more as a baseline. Results go to $PF_F1_OUT (JSON), a log beside it.

What it cannot see: the OS (window activation is simulated by emitting Qt's signal; focus is set with setFocus on an
inactive off-screen window); viewport picking (object selection is made with setSelected); the menu entry (only the
hotkey symbol); Houdini's own text fields if they are not Qt text widgets; Houdini builds other than this one.
"""
import gc
import json
import os
import sys
import time
import traceback

import hdefereval
import hou
import shiboken6
from hutil.Qt import QtCore, QtGui, QtWidgets
from PySide6.QtTest import QTest

from polyfactory.modelui import explorer, input_layer, keys, scene, switch

OUT = os.environ["PF_F1_OUT"]
LOGF = open(OUT + ".log", "w", buffering=1)
QE, Qt = QtCore.QEvent, QtCore.Qt
APP = QtWidgets.QApplication.instance()
PREF = hou.text.expandString("$HOUDINI_USER_PREF_DIR")
STATE = {"desk0": None, "perf": False}
INPUT = {int(QE.MouseButtonPress), int(QE.MouseButtonRelease), int(QE.MouseButtonDblClick), int(QE.MouseMove),
         int(QE.KeyPress), int(QE.KeyRelease)}
PRESS, RELEASE, DBL, MOVE = int(QE.MouseButtonPress), int(QE.MouseButtonRelease), int(QE.MouseButtonDblClick), int(QE.MouseMove)
KP, KR = int(QE.KeyPress), int(QE.KeyRelease)
CS = Qt.ControlModifier | Qt.ShiftModifier
LMB, NOB, NOM = Qt.LeftButton, Qt.NoButton, Qt.NoModifier
ID_ROLE = Qt.UserRole


def log(*a):
    LOGF.write(" ".join(str(x) for x in a) + "\n")


def pref_listing():
    """Keymap, hotkey and desktop files only (what a mode switch could write). Houdini itself rewrites animbar.pref,
    config/Dialogs/*.ui and its help cache on any desk switch; those are not judged."""
    out = {}
    for root, _, files in os.walk(PREF):
        for f in files:
            p = os.path.join(root, f)
            rel = os.path.relpath(p, PREF)
            if "keymap" in f.lower() or "hotkey" in f.lower() or rel.lower().startswith("desktop"):
                st = os.stat(p)
                out[rel] = (st.st_size, st.st_mtime_ns)
    return out


class Probe(QtCore.QObject):
    """Object filter: runs after every application filter, so it sees what was not swallowed."""

    def __init__(self):
        super().__init__()
        self.seen = []

    def eventFilter(self, obj, ev):  # noqa: N802
        if int(ev.type()) in INPUT:
            self.seen.append(int(ev.type()))
        return False


def with_probe(w, fn):
    p = Probe()
    w.installEventFilter(p)
    try:
        fn()
    finally:
        w.removeEventFilter(p)
    return p.seen


def L(win, g, dx=0, dy=0):   # window-local point
    return win.mapFromGlobal(g) + QtCore.QPoint(dx, dy)


def hover(win, g):   # the cursor first (outside a probe), so a press brings no hover move of its own
    QTest.mouseMove(win, L(win, g))


def drag(win, g, mods=CS):   # 50 px
    QTest.mousePress(win, LMB, mods, L(win, g))
    QTest.mouseMove(win, L(win, g, 30, 40))
    QTest.mouseRelease(win, LMB, mods, L(win, g, 30, 40))


def click(win, g, mods=NOM):
    QTest.mousePress(win, LMB, mods, L(win, g))
    QTest.mouseRelease(win, LMB, mods, L(win, g))


def send_mouse(win, etype, g, button, buttons, mods):
    APP.sendEvent(win, QtGui.QMouseEvent(etype, QtCore.QPointF(L(win, g)), QtCore.QPointF(g), button, buttons, mods))


def send_key(win, etype, k, rep=False, sc=0):
    APP.sendEvent(win, QtGui.QKeyEvent(etype, k, NOM, sc, 0, 0, "", rep))


def keyclick(win, k):
    QTest.keyPress(win, k)
    QTest.keyRelease(win, k)


def viewer_point():
    sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    r = sv.qtScreenGeometry()
    g = QtCore.QPoint(r.x() + int(r.width() * 0.3), r.y() + int(r.height() * 0.3))
    mw = hou.qt.mainWindow()
    return sv, g, mw.childAt(mw.mapFromGlobal(g)) or QtWidgets.QApplication.widgetAt(g)


def visible_on_screen():
    return [w for w in QtWidgets.QApplication.topLevelWidgets()
            if w.isVisible() and w.frameGeometry().right() > -5000]


def off_screen():
    """Every visible window to x < -5000 (floating panes ignore the position they are created with)."""
    mw = hou.qt.mainWindow()
    if mw is None:   # not built yet (a fresh prefs folder starts slower)
        return False
    if mw.geometry().x() > -5000:
        mw.showNormal()   # a maximized window ignores move()
        mw.setGeometry(-12000, 100, 1600, 1000)
    for i, w in enumerate(visible_on_screen()):
        w.move(-9000, 100 + 60 * i)
    return not visible_on_screen()


def suite(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj")
    a, b, c = [obj.createNode("geo", n) for n in "abc"]
    yield 100
    snap0, pref0, desk0 = keys.snapshot(), pref_listing(), hou.ui.curDesktop().name()
    out["toggle_key_registered"] = switch.TOGGLE_KEY in hou.hotkeys.assignments("h", switch.TOGGLE_SYMBOL)
    ok = switch.install()
    yield 900
    desk = hou.ui.curDesktop()
    out["install_on"] = bool(ok and switch.is_on())
    out["desk_modelui_with_explorer"] = desk.name() == "ModelUI" and any(
        isinstance(t, hou.PythonPanel) and t.activeInterface() is not None
        and t.activeInterface().name() == "pf_modelui_explorer" for t in desk.paneTabs()) and getattr(
        hou.session, "_pf_modelui_explorer", None) is not None
    out["keys_applied"] = all((k not in hou.hotkeys.assignments(cx, s[1:])) if s.startswith("-")
                              else (k in hou.hotkeys.assignments(cx, s)) for cx, s, k in keys.KEYS)
    lay = input_layer.layer()
    sv0, g0, t0 = viewer_point()
    states = []
    sv0.setCurrentState("objview")
    hover(hou.qt.mainWindow().windowHandle(), g0)   # Houdini sends a hotkey to the viewer under the cursor
    yield 200
    for k in (Qt.Key_Q, Qt.Key_W, Qt.Key_E, Qt.Key_R, Qt.Key_T, Qt.Key_Q):   # stock: none changes "objview"
        t0.setFocus()
        keyclick(hou.qt.mainWindow().windowHandle(), k)
        yield 250
        states.append(sv0.currentState())
    out["max_keys_work"] = states[:2] == ["select", "pose"]
    out["w_then_q_selects"] = states[1] == "pose" and states[-1] == "select"   # Max: W, E, R, then Q back to select
    log("  Q/W states", states)
    out["input_cpp"] = lay is not None and lay.backend == "cpp"
    sv, g, target = viewer_point()
    mw = hou.qt.mainWindow()
    win = mw.windowHandle()
    log("  backend", lay and lay.backend, "viewer", sv.name(), "target", type(target).__name__, g)
    DEMO = lambda: input_layer.DEMO.log   # noqa: E731 - the module object may be re-exec'd by a mutation

    # --- mouse on the real path ------------------------------------------------------------------------------------
    n0 = len(DEMO())
    hover(win, g)
    seen = with_probe(target, lambda: drag(win, g))
    log("  demo drag probe", seen)
    out["demo_drag_owned"] = DEMO()[n0:] == [(50, sv.name())]
    out["demo_drag_swallowed"] = not set(seen) & {PRESS, MOVE, RELEASE}
    seen = with_probe(target, lambda: click(win, g))
    out["plain_click_passes"] = PRESS in seen
    seen = with_probe(target, lambda: QTest.mouseDClick(win, LMB, CS, L(win, g)))
    out["dblclick_swallowed"] = not set(seen) & {PRESS, DBL, RELEASE}
    log("  dblclick probe", seen)
    panel = getattr(hou.session, "_pf_modelui_explorer", None)
    out["outside_viewer_passes"] = False
    if panel is not None:
        gp = panel.mapToGlobal(panel.rect().center())
        pw = mw.childAt(mw.mapFromGlobal(gp))
        n0 = len(DEMO())
        seen = with_probe(pw, lambda: drag(win, gp))
        out["outside_viewer_passes"] = len(DEMO()) == n0 and PRESS in seen
    ov = QtWidgets.QWidget(None, Qt.Tool | Qt.FramelessWindowHint)   # a small window over the viewer
    ov.setGeometry(g.x() - 20, g.y() - 20, 120, 80)
    ov.show()
    yield 100
    n0 = len(DEMO())
    seen = with_probe(ov, lambda: click(ov.windowHandle(), g, CS))
    out["window_over_viewer_passes"] = len(DEMO()) == n0 and PRESS in seen
    ov.setGeometry(g.x() - 800, g.y() - 500, 1600, 1000)   # covers the viewer: only the receiving-window test is left
    n0 = len(DEMO())
    click(ov.windowHandle(), g, CS)
    out["other_window_receiver_passes"] = len(DEMO()) == n0
    ov.close()
    ov.deleteLater()
    out["hidden_viewer_tab_ignored"] = False
    ptabs = [t for t in desk.paneTabs() if isinstance(t, hou.PythonPanel) and t.activeInterface() is not None
             and t.activeInterface().name() == "pf_modelui_explorer"]
    if panel is not None and ptabs:
        hv = ptabs[0].pane().createTab(hou.paneTabType.SceneViewer)   # a Scene View tab behind the Explorer
        ptabs[0].setIsCurrentTab()
        yield 300
        gp = panel.mapToGlobal(panel.rect().center())
        n0 = len(DEMO())
        hover(win, gp)
        drag(win, gp)
        out["hidden_viewer_tab_ignored"] = len(DEMO()) == n0 and not hv.isCurrentTab()
        log("  hidden tab", hv.qtScreenGeometry(), "explorer", panel.geometry(), "current", hv.isCurrentTab())
        _q(hv.close)
        ptabs[0].setIsCurrentTab()
        yield 100

    # --- keys ------------------------------------------------------------------------------------------------------
    got = []

    def tap(kind, ev, viewer):
        if kind == "press":
            return False
        if kind == "key" and viewer is not None and ev.key() not in (Qt.Key_F9, Qt.Key_2):
            return False
        got.append(kind)
        if kind == "other":   # while F9 is held: swallow F7 and Alt+clicks in a viewer, let everything else through
            if ev.type() == QE.KeyPress:
                return ev.key() == Qt.Key_F7
            return bool(ev.modifiers() & Qt.AltModifier) and viewer is not None
        return True
    input_layer.add_gesture("test_tap", tap)
    target.setFocus()
    try:
        seen = with_probe(target, lambda: keyclick(win, Qt.Key_F9))
        out["key_gesture_owned"] = got == ["key", "keyup"] and not set(seen) & {KP, KR}
        del got[:]
        seen = with_probe(target, lambda: (send_key(win, QE.KeyPress, Qt.Key_F9), send_key(win, QE.KeyRelease, Qt.Key_F9, True),
                                           send_key(win, QE.KeyPress, Qt.Key_F9, True), send_key(win, QE.KeyRelease, Qt.Key_F9)))
        out["key_autorepeat_owned"] = got == ["key", "key", "key", "keyup"] and seen == []
        del got[:]
        send_key(win, QE.KeyPress, Qt.Key_2, sc=3)       # Shift went down while held: "2" pressed, "@" released
        send_key(win, QE.KeyRelease, Qt.Key_At, sc=3)
        out["key_pairs_by_scancode"] = got == ["key", "keyup"] and input_layer.layer().owner is None
        input_layer.layer().owners.update(mouse=None, key=None)
        seen = with_probe(target, lambda: keyclick(win, Qt.Key_F8))
        out["unowned_key_passes"] = KP in seen
        le = QtWidgets.QLineEdit(mw)   # a text field inside the viewer's rectangle
        le.setGeometry(QtCore.QRect(mw.mapFromGlobal(g), QtCore.QSize(120, 24)))
        le.show()
        le.setFocus()
        del got[:]
        seen = with_probe(le, lambda: keyclick(win, Qt.Key_F9))
        out["text_field_keeps_keys"] = got == [] and KP in seen
        le.deleteLater()
        target.setFocus()
        del got[:]
        QTest.keyPress(win, Qt.Key_F9)   # owned; then the application loses activation (Alt+Tab while holding)
        QtGui.QGuiApplication.instance().applicationStateChanged.emit(Qt.ApplicationInactive)
        QtGui.QGuiApplication.instance().applicationStateChanged.emit(Qt.ApplicationActive)   # Houdini listens too
        out["key_cancel_on_deactivate"] = got == ["key", "cancel"] and input_layer.layer().owner is None
        QTest.keyRelease(win, Qt.Key_F9)
        app = QtGui.QGuiApplication.instance()
        owners = input_layer.layer().owners
        target.setFocus()   # cancel also forgets what the holder swallowed: a fresh F7 then reaches Houdini whole
        QTest.keyPress(win, Qt.Key_F9)
        QTest.keyPress(win, Qt.Key_F7)   # swallowed via "other"; its release never comes
        app.applicationStateChanged.emit(Qt.ApplicationInactive)
        app.applicationStateChanged.emit(Qt.ApplicationActive)
        eaten_empty = not input_layer.layer().eaten["key"]
        seen = with_probe(win, lambda: keyclick(win, Qt.Key_F7))
        out["cancel_clears_eaten"] = eaten_empty and seen.count(KP) == 1 and seen.count(KR) == 1
        QTest.keyRelease(win, Qt.Key_F9)
        del got[:]
        QTest.keyPress(win, Qt.Key_F9)   # held; a menu pops up (TAB menu, RMB menu), then focus goes to another window
        menu = QtWidgets.QMenu()
        menu.addAction("x")
        menu.popup(QtCore.QPoint(-9500, 300))
        app.focusWindowChanged.emit(menu.windowHandle())
        out["popup_keeps_held_key"] = owners["key"] is not None and "cancel" not in got
        menu.close()
        menu.deleteLater()
        other = QtWidgets.QWidget(None, Qt.Tool)
        other.setGeometry(-9500, 600, 100, 100)
        other.show()
        app.focusWindowChanged.emit(other.windowHandle())
        out["key_cancel_on_focus_window"] = got[-1:] == ["cancel"] and owners["key"] is None
        other.close()
        other.deleteLater()
        app.focusWindowChanged.emit(win)
        QTest.keyRelease(win, Qt.Key_F9)
        target.setFocus()
        del got[:]
        QTest.keyPress(win, Qt.Key_F9)   # held by tap
        # leaks are seen on the window: Houdini may take a hotkey or Alt+LMB before the widget's own filters
        seen = with_probe(win, lambda: (keyclick(win, Qt.Key_F8), QTest.keyPress(win, Qt.Key_F7),
                                        send_key(win, QE.KeyPress, Qt.Key_F7, True)))
        out["second_key_notifies_hold_owner"] = got.count("other") == 2 and seen == [KP, KR]   # F8 only, all of it
        log("  hold: got", got, "probe", seen)
        n0 = len(DEMO())
        hover(win, g)
        drag(win, g)
        out["hold_then_click_reaches_mouse_gesture"] = DEMO()[n0:] == [(50, sv.name())] and owners["key"] is not None
        del got[:]   # Alt+click during the hold: the holder may swallow it in a viewer, never on the Explorer
        seen = with_probe(win, lambda: click(win, g, Qt.AltModifier))
        out["other_click_in_viewer_swallowable"] = got == ["other"] and not set(seen) & {PRESS, RELEASE}
        out["other_click_on_explorer_passes"] = False
        if panel is not None:
            gp = panel.mapToGlobal(panel.rect().center())
            pw = mw.childAt(mw.mapFromGlobal(gp))
            seen = with_probe(pw, lambda: click(win, gp, Qt.AltModifier))
            out["other_click_on_explorer_passes"] = PRESS in seen and RELEASE in seen
        n0 = len(DEMO())   # a drag started during the hold survives the holder's key-up
        hover(win, g)
        QTest.mousePress(win, LMB, CS, L(win, g))
        seen = with_probe(win, lambda: (QTest.keyRelease(win, Qt.Key_F9), QTest.keyRelease(win, Qt.Key_F7)))
        out["swallowed_key_fully_hidden"] = seen == [] and not input_layer.layer().eaten["key"]
        QTest.mouseMove(win, L(win, g, 30, 40))
        QTest.mouseRelease(win, LMB, CS, L(win, g, 30, 40))
        out["keyup_keeps_drag"] = DEMO()[n0:] == [(50, sv.name())]
        hover(win, g)   # keys are offered during a drag; a deactivation ends the drag too
        QTest.mousePress(win, LMB, CS, L(win, g))
        del got[:]
        target.setFocus()   # the Alt+click on the Explorer took the focus
        QTest.keyPress(win, Qt.Key_F9)
        out["key_offered_during_drag"] = got == ["key"] and owners["mouse"] is not None
        QTest.keyRelease(win, Qt.Key_F9)
        app.applicationStateChanged.emit(Qt.ApplicationInactive)
        app.applicationStateChanged.emit(Qt.ApplicationActive)   # Houdini listens too
        out["cancel_ends_drag"] = owners["mouse"] is None
        QTest.mouseRelease(win, LMB, NOM, L(win, g))
        if panel is not None:
            panel.list.setFocus()   # focus in the Explorer (outside the viewer)
            del got[:]
            seen = with_probe(panel.list, lambda: keyclick(win, Qt.Key_F9))
            out["key_outside_viewer_passes"] = got == [] and KP in seen
            target.setFocus()
    finally:
        input_layer.remove_gesture("test_tap")
        if input_layer.layer() is not None:
            input_layer.layer().owners.update(mouse=None, key=None)

    counts = {}

    def count(kind, ev, viewer):   # observes Alt+LMB and F7 (their events go on to Houdini), counts every call
        if viewer is not None and not ((kind == "press" and ev.modifiers() & Qt.AltModifier)
                                       or (kind == "key" and ev.key() == Qt.Key_F7)):
            return False
        counts[kind] = counts.get(kind, 0) + 1
        return input_layer.OBSERVE
    input_layer.add_gesture("test_count", count)
    try:
        QTest.mousePress(win, LMB, Qt.AltModifier, L(win, g))
        QTest.mouseMove(win, L(win, g, 5, 5))
        QTest.mouseRelease(win, LMB, Qt.AltModifier, L(win, g, 5, 5))
        target.setFocus()   # Houdini's Alt+LMB tumble moved the focus
        keyclick(win, Qt.Key_F7)
        out["one_call_per_input"] = counts == {"press": 1, "move": 1, "release": 1, "key": 1, "keyup": 1}
        log("  counts", counts)
    finally:
        input_layer.remove_gesture("test_count")

    QTest.mousePress(win, LMB, CS, L(win, g))   # the demo owns it; the release is lost
    owned = input_layer.layer().owner is not None
    seen = with_probe(win, lambda: send_mouse(win, QE.MouseMove, g + QtCore.QPoint(5, 5), NOB, NOB, CS))
    out["lost_release_cancels"] = owned and input_layer.layer().owner is None and MOVE in seen
    QTest.mouseRelease(win, LMB, NOM, L(win, g, 5, 5))   # QtTest's own button state

    kinds = []

    def nested(kind, ev, viewer):   # its press runs a nested delivery that brings the release
        if kind == "press":
            if not ev.modifiers() & Qt.MetaModifier:
                return False
            send_mouse(win, QE.MouseButtonRelease, g, LMB, NOB, Qt.MetaModifier)
            return True
        kinds.append(kind)
        return True
    input_layer.add_gesture("test_nested", nested)
    try:
        QTest.mousePress(win, LMB, Qt.MetaModifier, L(win, g))
        out["nested_release_not_stuck"] = input_layer.layer().owner is None and kinds == ["release"]
        input_layer.layer().owners.update(mouse=None, key=None)
        QTest.mouseRelease(win, LMB, Qt.MetaModifier, L(win, g))
    finally:
        input_layer.remove_gesture("test_nested")

    copies, st = [0], {}

    def clone(kind, ev, viewer):   # Shift+drag clone in miniature: observe, copy once past 6 px, deferred
        if kind == "press":
            mods = ev.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier)
            if ev.button() != LMB or mods != Qt.ShiftModifier:
                return False
            st.update(start=ev.globalPosition(), done=False)
            return input_layer.OBSERVE
        if kind == "move" and not st["done"]:
            d = ev.globalPosition() - st["start"]
            if abs(d.x()) + abs(d.y()) > 6:
                st["done"] = True
                input_layer.later(lambda: copies.__setitem__(0, copies[0] + 1))
                st["inside"] = copies[0]   # still 0 if the copy waits for the event loop
        st.setdefault("kinds", []).append(kind)
        return False
    input_layer.add_gesture("test_clone", clone)
    try:
        hover(win, g)

        def shift_drag():
            QTest.mousePress(win, LMB, Qt.ShiftModifier, L(win, g))
            for d in (2, 6, 12, 20):
                QTest.mouseMove(win, L(win, g, d, d))
            QTest.mouseRelease(win, LMB, Qt.ShiftModifier, L(win, g, 20, 20))
        wseen = []
        seen = with_probe(target, lambda: wseen.extend(with_probe(win, shift_drag)))
        yield 50
        # "not swallowed by us" is seen on the window (our filter acts there; Houdini's own filter may then take
        # a Shift+LMB drag before the viewer widget, which is Houdini's business)
        out["observe_drag_passes_through"] = (wseen.count(PRESS) == 1 and wseen.count(MOVE) >= 4 and RELEASE in wseen
                                              and st.get("kinds", [])[-1:] == ["release"])
        out["later_defers"] = st.get("inside") == 0 and copies[0] == 1
        log("  observe probe", seen, "window", wseen, "kinds", st.get("kinds"), "copies inside/after", st.get("inside"), copies[0])
        copies[0] = 0
        QTest.mouseClick(win, LMB, Qt.ShiftModifier, L(win, g, 40, 0))
        yield 50
        out["observe_click_no_copy_and_ends"] = (copies[0] == 0 and input_layer.layer().owner is None
                                                 and not input_layer.layer().watchers["mouse"])
    finally:
        input_layer.remove_gesture("test_clone")
        input_layer.layer().owners.update(mouse=None, key=None)

    obs = {"a": [], "b": []}   # two observing gestures share one Shift press

    def observer(k):
        def g(kind, ev, viewer):
            if kind == "press":
                mods = ev.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier)
                if ev.button() != LMB or mods != Qt.ShiftModifier:
                    return False
            obs[k].append(kind)
            return input_layer.OBSERVE
        return g
    input_layer.add_gesture("test_obs_a", observer("a"))
    input_layer.add_gesture("test_obs_b", observer("b"))
    try:
        hover(win, g)

        def shift_drag2():
            QTest.mousePress(win, LMB, Qt.ShiftModifier, L(win, g))
            for d in (4, 10, 16):
                QTest.mouseMove(win, L(win, g, d, d))
            QTest.mouseRelease(win, LMB, Qt.ShiftModifier, L(win, g, 16, 16))
        wseen2 = with_probe(win, shift_drag2)
        out["two_observers_share_press"] = (obs["a"][:1] == ["press"] and obs["a"] == obs["b"]
                                            and obs["a"][-1:] == ["release"] and PRESS in wseen2)
        log("  two observers", obs, "window", wseen2)
    finally:
        input_layer.remove_gesture("test_obs_a")
        input_layer.remove_gesture("test_obs_b")
    got_c = []
    AS = Qt.AltModifier | Qt.ShiftModifier

    def obs_c(kind, ev, viewer):   # observes Alt+Shift presses; a gesture after it takes them
        if kind == "press" and (ev.modifiers() & (Qt.ControlModifier | AS)) != AS:
            return False
        got_c.append(kind)
        return input_layer.OBSERVE

    def taker(kind, ev, viewer):
        if kind == "press" and (ev.modifiers() & (Qt.ControlModifier | AS)) != AS:
            return False
        return True
    input_layer.add_gesture("test_obs_c", obs_c)
    input_layer.add_gesture("test_taker", taker)
    try:
        QTest.mousePress(win, LMB, AS, L(win, g))
        QTest.mouseRelease(win, LMB, AS, L(win, g))
        out["observer_cancelled_by_taker"] = got_c == ["press", "cancel"]
        log("  observer before a taker", got_c)
    finally:
        input_layer.remove_gesture("test_obs_c")
        input_layer.remove_gesture("test_taker")

    fp = desk.createFloatingPaneTab(hou.paneTabType.SceneViewer, position=(-11000, 300), size=(600, 450))
    yield 300
    if not off_screen():
        raise RuntimeError("ABORT: a window stayed on screen")
    yield 300
    try:
        fc = fp.qtScreenGeometry().center()
        ft = [t for t in QtWidgets.QApplication.topLevelWidgets()
              if t.isVisible() and t is not mw and t.frameGeometry().contains(fc)]
        n0 = len(DEMO())
        drag(ft[0].windowHandle(), fc)
        out["floating_viewer_gesture"] = DEMO()[n0:] == [(50, fp.name())]
        log("  floating viewer", fp.qtScreenGeometry(), [type(t).__name__ for t in ft], DEMO()[n0:])
    finally:
        for p in hou.ui.floatingPanels():
            if fp in p.paneTabs():
                _q(p.close)

    # --- Scene Explorer -------------------------------------------------------------------------------------------
    w = explorer.Explorer()
    caught = []
    old_hook, sys.excepthook = sys.excepthook, (lambda *a: caught.append(a[0].__name__))
    try:
        def rows():
            return [w.list.item(i).text() for i in range(w.list.count())]
        out["explorer_lists"] = rows() == ["a", "b", "c"]
        w.list.clearSelection()
        w.list.item(1).setSelected(True)
        out["panel_selects_node"] = b.isSelected() and not a.isSelected() and not c.isSelected()
        c.setSelected(True, clear_all_selected=True)
        yield 200
        out["node_selects_row"] = w.selected_ids() == [c.sessionId()]
        w.list.item(0).setText("hull")
        yield 200
        out["row_renames"] = a.name() == "hull" and rows()[0] == "hull"
        b.setName("zz")
        yield 200
        out["rename_follows"] = rows()[1:2] == ["zz"]
        n0 = len(caught)
        w.list.item(1).setText("my hull")   # not a valid node name
        yield 200
        out["invalid_rename_recovers"] = caught[n0:] == [] and b.name() == "zz" and rows()[1:2] == ["zz"]
        w.list.item(2).setCheckState(Qt.Unchecked)
        out["row_hides"] = not c.isDisplayFlagSet()
        w.list.clearSelection()
        w.list.item(0).setSelected(True)
        w.delete_selected()
        yield 200
        out["row_deletes"] = hou.node("/obj/hull") is None and rows() == ["zz", "c"]
        n0 = len(caught)
        c.destroy()   # its row is still there until the queued refresh runs
        w.list.clearSelection()
        w.list.item(1).setSelected(True)
        out["deleted_row_click_recovers"] = caught[n0:] == [] and rows() == ["zz"]
        log("  explorer exceptions", caught)
    finally:
        sys.excepthook = old_hook
        w.close_down()
        w.deleteLater()

    # --- switch back, prefs, callbacks, cost -----------------------------------------------------------------------
    switch.toggle()
    yield 500
    out["toggle_off"] = not switch.is_on() and hou.ui.curDesktop().name() == desk0
    out["keys_reverted"] = keys.snapshot() == snap0
    sv2, g2, t2 = viewer_point()
    n0 = len(DEMO())
    seen = with_probe(t2, lambda: drag(t2.window().windowHandle(), g2))
    out["input_off"] = len(DEMO()) == n0 and PRESS in seen
    switch.toggle()
    yield 800
    out["toggle_on_again"] = switch.is_on() and hou.ui.curDesktop().name() == "ModelUI"
    switch.uninstall()
    yield 300
    s = scene.current()
    nodes = [hou.node("/obj")] + list(hou.node("/obj").children())
    out["no_callbacks_after_uninstall"] = (
        not s._watchers and not any(cb[1] == s._event for n in nodes for cb in n.eventCallbacks())
        and not any(cb == s._hip_event for cb in hou.hipFile.eventCallbacks()))
    if STATE["perf"]:
        for i in range(2000):
            obj.createNode("geo", "p%d" % i)

        def ms(fn):
            t = time.perf_counter()
            fn()
            return 1000 * (time.perf_counter() - t)

        def med(v):
            return sorted(v)[len(v) // 2]
        def ref_list():   # fixed reference workload: a plain list of the same 2000 names, filled and selected, x10
            for _ in range(10):
                w = QtWidgets.QListWidget()
                w.addItems([n.name() for n in hou.node("/obj").children()])
                w.selectAll()
                w.deleteLater()
        refs = [ms(ref_list) for _ in range(3)]   # right before and right after the Explorer timings
        builds, made = [], []
        for _ in range(3):
            builds.append(ms(lambda: made.append(explorer.Explorer())))
        for x in made[:-1]:
            x.close_down()
            x.deleteLater()
        w2 = made[-1]
        renames = []
        for k in range(5):
            hou.node("/obj/p%d" % k).setName("q%d" % k)
            renames.append(ms(w2.refresh))
        ptrs = [shiboken6.getCppPointer(w2.list.item(i))[0] for i in range(w2.list.count())]
        idles = [ms(w2.refresh) for _ in range(5)]
        out["explorer_no_rebuild_when_unchanged"] = ptrs == [
            shiboken6.getCppPointer(w2.list.item(i))[0] for i in range(w2.list.count())]
        sel = ms(w2.list.selectAll)
        refs += [ms(ref_list) for _ in range(3)]
        w2.close_down()
        w2.deleteLater()
        m = {"build": med(builds), "after_rename": med(renames), "idle": med(idles), "select_all": sel}
        ref = med(refs)
        log("  perf 2000 objects, medians (ms)", {k: round(v, 1) for k, v in m.items()}, "reference", round(ref, 1),
            "ratios", {k: round(v / ref, 2) for k, v in m.items()})
        # judged against the reference measured right beside it, so another job loading the PC does not decide it
        # (absolute ceilings failed at 100 % CPU, 2026-11-09). Ceilings: 3x the highest ratio of the 2026-11-09 warm
        # runs at 62-100 % CPU (build 2.2, after rename 2.5, idle 2.9, select all 7.4; one reference = 10 lists).
        # Blind spot: a load that slows the Explorer's HOM calls much more than plain Qt lists.
        ceil = {"build": 7.0, "after_rename": 8.0, "idle": 9.0, "select_all": 22.0}
        out["perf_explorer_2000"] = all(m[k] / ref < ceil[k] for k in ceil)
    pref1 = pref_listing()
    out["prefs_untouched"] = pref1 == pref0
    if pref1 != pref0:
        log("  prefs moved:", sorted(k for k in set(pref0) | set(pref1) if pref0.get(k) != pref1.get(k)))

    switch.FEATURES.append("polyfactory.modelui._no_such_feature")
    try:
        ok = switch.install()
    finally:
        switch.FEATURES.remove("polyfactory.modelui._no_such_feature")
    yield 300
    out["rollback_off"] = (not ok and not switch.is_on() and hou.ui.curDesktop().name() == desk0
                           and keys.snapshot() == snap0 and input_layer.layer() is None)

    input_layer.install(fallback=True)
    yield 100
    lay = input_layer.layer()
    sv3, g3, t3 = viewer_point()
    n0 = len(DEMO())
    hover(t3.window().windowHandle(), g3)
    seen = with_probe(t3, lambda: drag(t3.window().windowHandle(), g3))
    out["fallback_drag_owned"] = lay.backend == "windows" and DEMO()[n0:] == [(50, sv3.name())]
    out["fallback_swallowed"] = not set(seen) & {PRESS, MOVE, RELEASE}
    input_layer.uninstall()


def _q(f):
    try:
        f()
    except Exception:  # noqa: BLE001
        log("  cleanup:", traceback.format_exc().splitlines()[-1])


def restore_keys():
    """Back to the hotkeys of the session start: a mutation run may leave them changed (removals_not_reverted once
    deleted Houdini's own Q for the rest of the session and hid repeat_current_kept)."""
    now, snap = keys.snapshot(), STATE["keys0"]
    for name in set(snap) | set(now):
        ctx, _, sym = name.partition("?")
        want, have = set(snap.get(name, ())), set(now.get(name, ()))
        for k in have - want:
            hou.hotkeys.removeAssignment(ctx, sym, k)
        for k in want - have:
            hou.hotkeys.addAssignment(ctx, sym, k)
        if want != have:
            log("  restored hotkey", name, sorted(have), "->", sorted(want))


def cleanup():
    _q(switch.uninstall)
    _q(keys.revert)
    _q(restore_keys)
    _q(input_layer.uninstall)
    for o in gc.get_objects():   # filters a mutated uninstall left attached
        if type(o).__name__ in ("_AppFilter", "_Windows"):
            _q(o.detach)
    for name in ("test_tap", "test_count", "test_nested", "test_clone", "test_obs_a", "test_obs_b", "test_obs_c", "test_taker"):
        _q(lambda: input_layer.remove_gesture(name))
    for p in hou.ui.floatingPanels():
        if any(isinstance(t, hou.SceneViewer) for t in p.paneTabs()):
            _q(p.close)
    _q(lambda: hou.ui.desktop(STATE["desk0"]).setAsCurrent())
    switch._state["on"] = False


MODS = {"switch": switch, "keys": keys, "input_layer": input_layer, "explorer": explorer}


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


IL = "input_layer"
# (mutation, the check it must redden, module, [(old, new)])
MUTATIONS = [
    ("feature_fails", "install_on", "keys", [("    if failed:\n        raise", "    if True:\n        raise")]),
    ("wrong_desk", "desk_modelui_with_explorer", "switch", [('DESK = "ModelUI"', 'DESK = "Build"')]),
    ("keys_not_applied", "keys_applied", "keys", [('    for ctx, sym, key in KEYS:\n        if sym.startswith("-"):', '    for ctx, sym, key in KEYS[:0]:\n        if sym.startswith("-"):')]),
    ("saves_overrides", "prefs_untouched", "keys", [("    if failed:\n        raise", "    H.saveOverrides()\n    if failed:\n        raise")]),
    ("removals_not_reverted", "keys_reverted", "keys", [('undo = H.removeAssignment if op == "add" else H.addAssignment',
                                                         'undo = H.removeAssignment if op == "add" else (lambda *a: True)')]),
    ("desk_not_restored", "toggle_off", "switch", [('_set_desk(hou.ui.desktop(_state["prev_desk"] or FALLBACK_DESK) or hou.ui.desktop(FALLBACK_DESK))', 'pass')]),
    ("toggle_only_off", "toggle_on_again", "switch", [('uninstall() if _state["on"] else install()', 'uninstall()')]),
    ("no_rollback", "rollback_off", "switch", [("        _rollback()\n        try:\n            hou.ui.setStatusMessage", "        try:\n            hou.ui.setStatusMessage")]),
    ("no_cpp_filter", "input_cpp", IL, [('lay.attached, lay.backend = _AppFilter(lay), "cpp"', 'raise OSError("mutated")')]),
    ("cpp_never_swallows", "demo_drag_swallowed", IL, [("return 1 if lay.handle(ev, receiver) else 0", "lay.handle(ev, receiver)\n            return 0")]),
    ("demo_wrong_length", "demo_drag_owned", IL, [("self.log.append((px, self.viewer))", "self.log.append((px + 1, self.viewer))")]),
    ("demo_owns_any_button", "plain_click_passes", IL, [("if ev.button() != Qt.LeftButton or mods != (Qt.ControlModifier | Qt.ShiftModifier):", "if False:")]),
    ("dblclick_leaks", "dblclick_swallowed", IL, [("            return ev.button() == which and swallow   # Qt sends it", "            return False   # Qt sends it")]),
    ("no_viewer_rect_test", "outside_viewer_passes", IL, [("        if g.contains(r) and tg.contains(g):", "        if True:")]),
    ("no_window_cover_test", "window_over_viewer_passes", IL, [("        if g.contains(r) and tg.contains(g):", "        if g.contains(r):")]),
    ("receiver_ignored", "other_window_receiver_passes", IL, [("        top = receiving_top(receiver)   # widgetAt()", "        top = hou.qt.mainWindow()   # widgetAt()")]),
    ("keys_never_offered", "key_gesture_owned", IL, [("        elif t == QE.KeyPress:", "        elif False:")]),
    ("autorepeat_ends_key", "key_autorepeat_owned", IL, [('        if t == QE.KeyRelease and not ev.isAutoRepeat():\n            self._end("key", o)', '        if t == QE.KeyRelease:\n            self._end("key", o)')]),
    ("keys_paired_by_key", "key_pairs_by_scancode", IL, [("    return ev.nativeScanCode() or ev.key()", "    return ev.key()")]),
    ("demo_owns_keys", "unowned_key_passes", IL, [('        if kind == "key":\n            return False\n', "")]),
    ("text_fields_not_skipped", "text_field_keeps_keys", IL, [("viewer = None if isinstance(focus, _TEXT) else viewer_of(focus)", "viewer = viewer_of(focus)")]),
    ("no_deactivate_cancel", "key_cancel_on_deactivate", IL, [("        app.applicationStateChanged.connect(self._state_changed)\n", "")]),
    ("cpp_every_receiver", "one_call_per_input", IL, [('LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "appfilter", "pf_appfilter.dll")',
                                                       'LIB = os.environ["PF_F1_MUT_DLL"]')]),
    ("lost_release_kept", "lost_release_cancels", IL, [("            if not ev.buttons() & which:", "            if False:")]),
    ("owner_after_call", "nested_release_not_stuck", IL, [("            self.owners[slot] = owner          # before the call: a nested event loop inside fn must see it\n            res = self._call(fn, kind, ev, viewer)",
                                                           "            res = self._call(fn, kind, ev, viewer)\n            self.owners[slot] = owner")]),
    ("observe_swallows", "observe_drag_passes_through", IL, [("                watchers.append([fn, which, False])   # observers share", "                return True   # observers share")]),
    ("later_runs_now", "later_defers", IL, [("    QtCore.QTimer.singleShot(0, run)", "    run()")]),
    ("observe_release_kept", "observe_click_no_copy_and_ends", IL, [('        if ev.button() == which:   # release\n            self._end("mouse", o)', '        if ev.button() == which:   # release\n            pass')]),
    ("docked_viewers_only", "floating_viewer_gesture", IL, [("[t for t in hou.ui.paneTabs() if", "[t for t in hou.ui.curDesktop().paneTabs() if")]),
    ("no_focus_cancel", "key_cancel_on_focus_window", IL, [("        app.focusWindowChanged.connect(self._focus_changed)\n", "")]),
    ("popup_cancels", "popup_keeps_held_key", IL, [("        if w is not None and w.type() in (Qt.Popup, Qt.ToolTip):", "        if False:")]),
    ("keys_any_focus", "key_outside_viewer_passes", IL, [("else viewer_of(focus)", "else (viewer_of(focus) or _viewers()[0])")]),
    ("hidden_tabs_count", "hidden_viewer_tab_ignored", IL, [("isinstance(t, hou.SceneViewer) and t.isCurrentTab()", "isinstance(t, hou.SceneViewer)")]),
    ("one_owner", "hold_then_click_reaches_mouse_gesture", IL, [('SLOT = {"press": "mouse", "key": "key"}', 'SLOT = {"press": "mouse", "key": "mouse"}')]),
    ("no_other_notice", "second_key_notifies_hold_owner", IL, [('        if held is not None and self._call(held[0], "other", ev, viewer) is True:', "        if False:")]),
    ("keys_not_applied_state", "max_keys_work", "keys", [('    for ctx, sym, key in KEYS:\n        if sym.startswith("-"):', '    for ctx, sym, key in KEYS[:0]:\n        if sym.startswith("-"):')]),
    ("no_q_binding", "w_then_q_selects", "keys", [('    (STATE, STATE + ".new_select", "Q"),', "")]),
    ("repeat_current_kept", "w_then_q_selects", "keys", [('    ("h.pane.gview", "-h.pane.gview.repeat_current", "Q"),', "")]),
    ("cancel_keeps_eaten", "cancel_clears_eaten", IL, [('        self.eaten["mouse"].clear()\n        self.eaten["key"].clear()\n', "")]),
    ("drop_eaten", "swallowed_key_fully_hidden", IL, [('            self.eaten["mouse" if kind == "press" else "key"].add(which)', "            pass")]),
    ("eaten_cleared_on_keyup", "swallowed_key_fully_hidden", IL, [('            self._end("key", o)\n            self._call(fn, "keyup", ev, None)', '            self._end("key", o)\n            self.eaten["key"].clear()\n            self._call(fn, "keyup", ev, None)')]),
    ("other_without_viewer", "other_click_in_viewer_swallowable", IL, [('self._call(held[0], "other", ev, viewer)', 'self._call(held[0], "other", ev, None)')]),
    ("no_other_for_clicks", "other_click_in_viewer_swallowable", IL, [('        if held is not None and self._call(held[0], "other", ev, viewer)', '        if held is not None and kind == "key" and self._call(held[0], "other", ev, viewer)')]),
    ("other_always_viewer", "other_click_on_explorer_passes", IL, [('self._call(held[0], "other", ev, viewer)', 'self._call(held[0], "other", ev, viewer or _viewers()[0])')]),
    ("cancel_keeps_mouse", "cancel_ends_drag", IL, [('        for slot in ("mouse", "key"):\n            o = self.owners[slot]', '        for slot in ("key",):\n            o = self.owners[slot]')]),
    ("drag_blocks_keys", "key_offered_during_drag", IL, [('        elif t == QE.KeyPress:\n            kind, which = "key", _key_id(ev)', '        elif t == QE.KeyPress:\n            if self.owners["mouse"] is not None:\n                return False\n            kind, which = "key", _key_id(ev)')]),
    ("keyup_ends_drag", "keyup_keeps_drag", IL, [('            self._end("key", o)\n            self._call(fn, "keyup", ev, None)', '            self._end("key", o)\n            self.owners["mouse"] = None\n            self._call(fn, "keyup", ev, None)')]),
    ("taker_drops_silently", "observer_cancelled_by_taker", IL, [("                for w in watchers + self.watchers[slot]:   # a gesture that takes the press wins: observers get cancel", "                for w in []:   # a gesture that takes the press wins: observers get cancel")]),
    ("first_observer_only", "two_observers_share_press", IL, [("                watchers.append([fn, which, False])   # observers share the press; every later gesture is still asked", "                watchers.append([fn, which, False])\n                break")]),
    ("uninstall_keeps_filter", "input_off", IL, [('    remove_gesture("demo_drag")\n    lay = layer()\n    if lay is not None:\n        lay.attached.detach()\n        lay.shutdown()\n        setattr(hou.session, SESSION_ATTR, None)', "    pass")]),
    ("fallback_not_attached", "fallback_drag_owned", IL, [("            w.installEventFilter(self.filter)", "            pass")]),
    ("fallback_never_swallows", "fallback_swallowed", IL, [("return int(ev.type()) in _TYPES and self.lay.handle(ev, _ptr(obj))", "self.lay.handle(ev, _ptr(obj))\n            return False")]),
    ("explorer_names_wrong", "explorer_lists", "explorer", [("it = QtWidgets.QListWidgetItem(name)", "it = QtWidgets.QListWidgetItem(name.upper())")]),
    ("rows_do_not_select", "panel_selects_node", "explorer", [("                self.model.select(self.selected_ids())", "                pass")]),
    ("no_watch", "node_selects_row", "explorer", [("            self.model.watch(self._timer.start)\n", "")]),
    ("rebuild_on_count_only", "rename_follows", "explorer", [("            if want != have:", "            if len(want) != len(have):")]),
    ("row_rename_ignored", "row_renames", "explorer", [("                    self.model.rename(pid, it.text())", "                    pass")]),
    ("row_hide_ignored", "row_hides", "explorer", [("                self.model.set_hidden([pid], hide)", "                pass")]),
    ("row_delete_ignored", "row_deletes", "explorer", [("            self.model.delete(ids)", "            pass")]),
    ("explorer_keeps_watching", "no_callbacks_after_uninstall", "explorer", [("        _panel().set_watching(False)", "        pass")]),
    ("invalid_rename_raises", "invalid_rename_recovers", "explorer", [("                except hou.Error as e:", "                except KeyError as e:")]),
    ("deleted_row_raises", "deleted_row_click_recovers", "explorer", [("            except KeyError:   # a row of a piece deleted", "            except IndexError:   # a row of a piece deleted")]),
    ("rebuild_every_refresh", "explorer_no_rebuild_when_unchanged", "explorer", [("            if want != have:", "            if True:")]),
    ("slow_refresh", "perf_explorer_2000", "explorer", [("for pid in m.pieces()]", "for pid in m.pieces() if pid in m.pieces()]")]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
if os.environ.get("PF_F1_QUICK"):   # diagnosis: one baseline only (the runner then reports missing pairs)
    RUNS = RUNS[:1]
RESULTS = []


def driver():
    STATE["desk0"] = hou.ui.curDesktop().name()
    STATE["keys0"] = keys.snapshot()
    log("start desk", STATE["desk0"], "prefs", PREF)
    log("toggle assignments", hou.hotkeys.assignments("h", switch.TOGGLE_SYMBOL))
    for name, check, modname, pairs in RUNS:
        cleanup()
        # warm runs only: the first baseline measured ~10x slower (Houdini's start-up background work)
        STATE["perf"] = (name is None and bool(RESULTS)) or check in ("perf_explorer_2000", "explorer_no_rebuild_when_unchanged")
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
    if not off_screen():   # never leave synthetic input running with a window on Hannes' screen
        log("ABORT: windows on screen", [(type(w).__name__, w.frameGeometry()) for w in visible_on_screen()])
        finish()
        return
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
    """Every 200 ms: every visible window off screen, else stop the run (never input on Hannes' screen)."""
    if hou.qt.mainWindow() is not None and not off_screen():
        log("ABORT: windows on screen", [(type(w).__name__, w.frameGeometry()) for w in visible_on_screen()])
        finish()


GUARD = QtCore.QTimer(interval=200, timeout=guard)


def start(tries=[0]):  # noqa: B006 - a counter across retries
    try:
        if hou.qt.mainWindow() is None:   # a fresh prefs folder: the main window may come later than 5 s
            tries[0] += 1
            if tries[0] > 60:
                raise RuntimeError("no main window after 65 s")
            QtCore.QTimer.singleShot(1000, start)
            return
        off_screen()
        GUARD.start()
        log("main window", hou.qt.mainWindow().geometry())
        pump(driver())
    except Exception:  # noqa: BLE001 - never hang with a window on screen
        log(traceback.format_exc())
        finish()


QtCore.QTimer.singleShot(300, off_screen)
QtCore.QTimer.singleShot(5000, start)
