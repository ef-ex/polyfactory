"""GUI checks of modelUI F1 (switch, keys, input layer, Scene Explorer), run INSIDE a throwaway Houdini.

Never run this in Hannes' session: start it with run_gui_f1.py (own prefs folder, only the polyfactory package, window
off screen, synthetic Qt events sent inside this process, exits by itself, never saves a .hip).

The suite runs once as a baseline, then once per mutation in MUTATIONS (a source edit of one module, exec'd into the
live module and restored afterwards), then once more as a baseline. Results go to $PF_F1_OUT (JSON), a log beside it.

What it cannot see: real OS input (synthetic events are sent to the widget, so the cursor-to-viewer mapping for keys
is replaced by the viewer point, and the fallback is only fed through the top QWindow); viewport picking (object
selection is made with setSelected, which is what a viewport pick does at object level); the menu entry (only the
hotkey symbol); floating panes; Houdini builds other than the one it runs on.
"""
import gc
import json
import os
import sys
import time
import traceback

import hdefereval
import hou
from hutil.Qt import QtCore, QtGui, QtWidgets

from polyfactory.modelui import explorer, input_layer, keys, scene, switch

OUT = os.environ["PF_F1_OUT"]
LOGF = open(OUT + ".log", "w", buffering=1)
QE, Qt = QtCore.QEvent, QtCore.Qt
APP = QtWidgets.QApplication.instance()
PREF = hou.text.expandString("$HOUDINI_USER_PREF_DIR")
STATE = {"desk0": None, "perf": False}
MOUSE_KEY = {int(QE.MouseButtonPress), int(QE.MouseButtonRelease), int(QE.MouseMove), int(QE.KeyPress),
             int(QE.KeyRelease)}


def log(*a):
    LOGF.write(" ".join(str(x) for x in a) + "\n")


def pref_listing():
    """Keymap, hotkey and desktop files only (what a mode switch could write). Houdini itself rewrites animbar.pref,
    config/Dialogs/*.ui and its help cache while panes are built; those are logged, not judged."""
    out = {}
    for root, _, files in os.walk(PREF):
        for f in files:
            p = os.path.join(root, f)
            st = os.stat(p)
            rel = os.path.relpath(p, PREF)
            if "keymap" in f.lower() or "hotkey" in f.lower() or rel.lower().startswith("desktop"):
                out[rel] = (st.st_size, st.st_mtime_ns)
    return out


class Probe(QtCore.QObject):
    """Object filter on the target widget: runs after every application filter, so it sees what was not swallowed."""

    def __init__(self):
        super().__init__()
        self.seen = []

    def eventFilter(self, obj, ev):  # noqa: N802
        if int(ev.type()) in MOUSE_KEY:
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


def mouse(target, etype, g, button, buttons, mods):
    """Real input enters through the widget's QWindow (Qt then hands it to the widget under the point)."""
    win = target.window().windowHandle()
    local = QtCore.QPointF(win.mapFromGlobal(g))
    APP.sendEvent(win, QtGui.QMouseEvent(etype, local, QtCore.QPointF(g), button, buttons, mods))


def drag(target, g0, mods=Qt.ControlModifier | Qt.ShiftModifier):
    g1 = g0 + QtCore.QPoint(30, 40)   # 50 px
    mouse(target, QE.MouseButtonPress, g0, Qt.LeftButton, Qt.LeftButton, mods)
    mouse(target, QE.MouseMove, g1, Qt.NoButton, Qt.LeftButton, mods)
    mouse(target, QE.MouseButtonRelease, g1, Qt.LeftButton, Qt.NoButton, mods)


def key(target, etype, k, rep=False):
    target.setFocus()   # the window hands keys to its focus widget
    APP.sendEvent(target.window().windowHandle(), QtGui.QKeyEvent(etype, k, Qt.NoModifier, "", rep))


def viewer_point():
    sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    r = sv.qtScreenGeometry()
    g = QtCore.QPoint(r.x() + int(r.width() * 0.3), r.y() + int(r.height() * 0.3))
    mw = hou.qt.mainWindow()
    return sv, g, mw.childAt(mw.mapFromGlobal(g)) or QtWidgets.QApplication.widgetAt(g)


def suite(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj")
    a, b, c = [obj.createNode("geo", n) for n in "abc"]
    yield 100
    snap0, pref0, desk0 = keys.snapshot(), pref_listing(), hou.ui.curDesktop().name()
    out["toggle_key_registered"] = switch.TOGGLE_KEY in hou.hotkeys.assignments("h", switch.TOGGLE_SYMBOL)
    ok = switch.install()
    yield 1500
    desk = hou.ui.curDesktop()
    out["install_on"] = bool(ok and switch.is_on())
    out["desk_modelui_with_explorer"] = desk.name() == "ModelUI" and any(
        isinstance(t, hou.PythonPanel) and t.activeInterface() is not None
        and t.activeInterface().name() == "pf_modelui_explorer" for t in desk.paneTabs()) and getattr(
        hou.session, "_pf_modelui_explorer", None) is not None   # the panel was really built
    log("  python panels", [(t.name(), t.activeInterface() and t.activeInterface().name()) for t in desk.paneTabs()
                            if isinstance(t, hou.PythonPanel)], "panel", getattr(hou.session, "_pf_modelui_explorer", None))
    out["keys_applied"] = all(k in hou.hotkeys.assignments(cx, s) for cx, s, k in keys.KEYS)
    lay = input_layer.layer()
    out["input_cpp"] = lay is not None and lay.backend == "cpp"
    sv, g, target = viewer_point()
    log("  backend", lay and lay.backend, "viewer", sv.name(), "target", type(target).__name__, g)
    n0 = len(input_layer.DEMO.log)
    seen = with_probe(target, lambda: drag(target, g))
    out["demo_drag_owned"] = input_layer.DEMO.log[n0:] == [(50, sv.name())]
    out["demo_drag_swallowed"] = seen == []
    seen = with_probe(target, lambda: (
        mouse(target, QE.MouseButtonPress, g, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier),
        mouse(target, QE.MouseButtonRelease, g, Qt.LeftButton, Qt.NoButton, Qt.NoModifier)))
    out["plain_click_passes"] = int(QE.MouseButtonPress) in seen
    panel = getattr(hou.session, "_pf_modelui_explorer", None)
    out["outside_viewer_passes"] = False
    if panel is not None:
        gp = panel.mapToGlobal(panel.rect().center())
        n0 = len(input_layer.DEMO.log)
        mw = hou.qt.mainWindow()
        pw = mw.childAt(mw.mapFromGlobal(gp))
        seen = with_probe(pw, lambda: drag(pw, gp))
        out["outside_viewer_passes"] = len(input_layer.DEMO.log) == n0 and int(QE.MouseButtonPress) in seen

    got = []

    def tap(kind, ev, viewer):
        if viewer is not None and (kind != "key" or ev.key() != Qt.Key_F9):
            return False
        got.append(kind)
        return True
    input_layer.add_gesture("test_tap", tap)
    old_cursor, input_layer.cursor_pos = input_layer.cursor_pos, (lambda: g)
    try:
        seen = with_probe(target, lambda: (
            key(target, QE.KeyPress, Qt.Key_F9), key(target, QE.KeyRelease, Qt.Key_F9, True),
            key(target, QE.KeyPress, Qt.Key_F9, True), key(target, QE.KeyRelease, Qt.Key_F9)))
        out["key_gesture_owned"] = got == ["key", "key", "key", "keyup"] and seen == []
        log("  key gesture got", got, "probe", seen)
        seen = with_probe(target, lambda: (key(target, QE.KeyPress, Qt.Key_F8), key(target, QE.KeyRelease, Qt.Key_F8)))
        out["unowned_key_passes"] = int(QE.KeyPress) in seen
        counts = {}

        def count(kind, ev, viewer):   # declines everything, counts its calls
            counts[kind] = counts.get(kind, 0) + 1
            return False
        input_layer.add_gesture("test_count", count)
        mouse(target, QE.MouseButtonPress, g, Qt.LeftButton, Qt.LeftButton, Qt.NoModifier)
        mouse(target, QE.MouseButtonRelease, g, Qt.LeftButton, Qt.NoButton, Qt.NoModifier)
        key(target, QE.KeyPress, Qt.Key_F7)
        key(target, QE.KeyRelease, Qt.Key_F7)
        out["one_call_per_input"] = counts == {"press": 1, "key": 1}
        log("  counts", counts)
    finally:
        input_layer.remove_gesture("test_tap")
        input_layer.remove_gesture("test_count")
        input_layer.cursor_pos = old_cursor

    mods = Qt.ControlModifier | Qt.ShiftModifier
    mouse(target, QE.MouseButtonPress, g, Qt.LeftButton, Qt.LeftButton, mods)   # the demo owns it; no release follows
    owned = input_layer.layer().owner is not None
    win = target.window().windowHandle()
    seen = with_probe(win, lambda: mouse(target, QE.MouseMove, g + QtCore.QPoint(5, 5), Qt.NoButton, Qt.NoButton, mods))
    out["lost_release_cancels"] = owned and input_layer.layer().owner is None and int(QE.MouseMove) in seen

    w = explorer.Explorer()
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
        caught = []
        old_hook, sys.excepthook = sys.excepthook, (lambda *a: caught.append(a[0].__name__))
        try:
            w.list.item(1).setText("my hull")   # not a valid node name
            yield 200
        finally:
            sys.excepthook = old_hook
        out["invalid_rename_recovers"] = caught == [] and b.name() == "zz" and rows()[1:2] == ["zz"]
        log("  invalid rename: caught", caught, "rows", rows())
        w.list.item(2).setCheckState(Qt.Unchecked)
        out["row_hides"] = not c.isDisplayFlagSet()
        w.list.clearSelection()
        w.list.item(0).setSelected(True)
        w.delete_selected()
        yield 200
        out["row_deletes"] = hou.node("/obj/hull") is None and rows() == ["zz", "c"]
    finally:
        w.close_down()
        w.deleteLater()

    switch.toggle()
    yield 500
    out["toggle_off"] = not switch.is_on() and hou.ui.curDesktop().name() == desk0
    out["keys_reverted"] = keys.snapshot() == snap0
    sv2, g2, t2 = viewer_point()
    n0 = len(input_layer.DEMO.log)
    seen = with_probe(t2, lambda: drag(t2, g2))
    out["input_off"] = len(input_layer.DEMO.log) == n0 and int(QE.MouseButtonPress) in seen
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
        obj = hou.node("/obj")
        for i in range(2000):
            obj.createNode("geo", "p%d" % i)
        t0 = time.perf_counter()
        w2 = explorer.Explorer()
        t1 = time.perf_counter()
        hou.node("/obj/p0").setName("q0")
        t2 = time.perf_counter()
        w2.refresh()
        t3 = time.perf_counter()
        w2.refresh()
        t4 = time.perf_counter()
        w2.list.selectAll()
        t5 = time.perf_counter()
        w2.close_down()
        w2.deleteLater()
        ms = {"build": 1000 * (t1 - t0), "after_rename": 1000 * (t3 - t2), "idle": 1000 * (t4 - t3),
              "select_all": 1000 * (t5 - t4)}
        log("  perf 2000 objects (ms)", {k: round(v, 1) for k, v in ms.items()})
        # ceilings ~4x the measured values (2026-11-05, this PC, Hannes' Houdini running beside it: build 46,
        # after rename 50, idle refresh 104, select all 146 ms; the audit measured 44 / 41 / 19 / 324 ms)
        out["perf_explorer_2000"] = (ms["build"] < 200 and ms["after_rename"] < 200 and ms["idle"] < 400
                                     and ms["select_all"] < 1500)
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
    n0 = len(input_layer.DEMO.log)
    seen = with_probe(t3, lambda: drag(t3, g3))
    out["fallback_drag_owned"] = lay.backend == "windows" and input_layer.DEMO.log[n0:] == [(50, sv3.name())]
    out["fallback_swallowed"] = seen == []
    input_layer.uninstall()


def _q(f):
    try:
        f()
    except Exception:  # noqa: BLE001
        log("  cleanup:", traceback.format_exc().splitlines()[-1])


def cleanup():
    _q(switch.uninstall)
    _q(keys.revert)
    _q(input_layer.uninstall)
    for o in gc.get_objects():   # filters a mutated uninstall left attached
        if type(o).__name__ in ("_AppFilter", "_Windows"):
            _q(o.detach)
    _q(lambda: input_layer.remove_gesture("test_tap"))
    _q(lambda: input_layer.remove_gesture("test_count"))
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


# (mutation, the check it must redden, module, [(old, new)])
MUTATIONS = [
    ("feature_fails", "install_on", "keys", [("    if failed:\n        raise", "    if True:\n        raise")]),
    ("wrong_desk", "desk_modelui_with_explorer", "switch", [('DESK = "ModelUI"', 'DESK = "Build"')]),
    ("keys_not_applied", "keys_applied", "keys", [("in KEYS:\n        for other", "in KEYS[:0]:\n        for other")]),
    ("saves_overrides", "prefs_untouched", "keys", [("    if failed:\n        raise", "    H.saveOverrides()\n    if failed:\n        raise")]),
    ("removals_not_reverted", "keys_reverted", "keys", [('undo = H.removeAssignment if op == "add" else H.addAssignment',
                                                         'undo = H.removeAssignment if op == "add" else (lambda *a: True)')]),
    ("desk_not_restored", "toggle_off", "switch", [('_set_desk(hou.ui.desktop(_state["prev_desk"] or FALLBACK_DESK) or hou.ui.desktop(FALLBACK_DESK))', 'pass')]),
    ("toggle_only_off", "toggle_on_again", "switch", [('uninstall() if _state["on"] else install()', 'uninstall()')]),
    ("no_rollback", "rollback_off", "switch", [("        _rollback()\n        try:\n            hou.ui.setStatusMessage", "        try:\n            hou.ui.setStatusMessage")]),
    ("no_cpp_filter", "input_cpp", "input_layer", [('lay.attached, lay.backend = _AppFilter(lay), "cpp"', 'raise OSError("mutated")')]),
    ("cpp_never_swallows", "demo_drag_swallowed", "input_layer", [("return 1 if lay.handle(ev) else 0", "lay.handle(ev)\n            return 0")]),
    ("demo_wrong_length", "demo_drag_owned", "input_layer", [("self.log.append((px, self.viewer))", "self.log.append((px + 1, self.viewer))")]),
    ("demo_owns_any_button", "plain_click_passes", "input_layer", [("if ev.button() != Qt.LeftButton or mods != (Qt.ControlModifier | Qt.ShiftModifier):", "if False:")]),
    ("no_viewer_hit_test", "outside_viewer_passes", "input_layer", [("tab.isCurrentTab() and tab.qtScreenGeometry().contains(pos)", "tab.isCurrentTab()")]),
    ("autorepeat_ends_key", "key_gesture_owned", "input_layer", [("if t == QE.KeyRelease and not ev.isAutoRepeat():", "if t == QE.KeyRelease:")]),
    ("demo_owns_keys", "unowned_key_passes", "input_layer", [('        if kind == "key":\n            return False\n', "")]),
    ("uninstall_keeps_filter", "input_off", "input_layer", [('    remove_gesture("demo_drag")\n    lay = layer()\n    if lay is not None:\n        lay.attached.detach()',
                                                            '    lay = layer()\n    if lay is not None:\n        pass')]),
    ("fallback_not_attached", "fallback_drag_owned", "input_layer", [("            w.installEventFilter(self.filter)", "            pass")]),
    ("fallback_never_swallows", "fallback_swallowed", "input_layer", [("return int(ev.type()) in _TYPES and self.lay.handle(ev)", "self.lay.handle(ev)\n            return False")]),
    ("explorer_names_wrong", "explorer_lists", "explorer", [("it = QtWidgets.QListWidgetItem(name)", "it = QtWidgets.QListWidgetItem(name.upper())")]),
    ("rows_do_not_select", "panel_selects_node", "explorer", [("            self.model.select(self.selected_ids())", "            pass")]),
    ("no_watch", "node_selects_row", "explorer", [("        self.model.watch(self._timer.start)\n", "")]),
    ("rebuild_on_count_only", "rename_follows", "explorer", [("            if want != have:", "            if len(want) != len(have):")]),
    ("row_rename_ignored", "row_renames", "explorer", [("            self.model.rename(pid, it.text())", "            pass")]),
    ("row_hide_ignored", "row_hides", "explorer", [("            self.model.set_hidden([pid], hide)", "            pass")]),
    ("row_delete_ignored", "row_deletes", "explorer", [("            self.model.delete(ids)", "            pass")]),
    ("cpp_every_receiver", "one_call_per_input", "input_layer", [('LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "appfilter", "pf_appfilter.dll")',
                                                                  'LIB = "F:/cache/modelui/f1/mut/pf_appfilter_nowindow.dll"')]),
    ("lost_release_kept", "lost_release_cancels", "input_layer", [("                if not ev.buttons() & which:", "                if False:")]),
    ("explorer_keeps_watching", "no_callbacks_after_uninstall", "explorer", [("        _panel().set_watching(False)", "        pass")]),
    ("invalid_rename_raises", "invalid_rename_recovers", "explorer", [("                except hou.Error as e:", "                except KeyError as e:")]),
    ("slow_refresh", "perf_explorer_2000", "explorer", [("for pid in m.pieces()]", "for pid in m.pieces() if pid in m.pieces()]")]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
RESULTS = []


def driver():
    STATE["desk0"] = hou.ui.curDesktop().name()
    log("start desk", STATE["desk0"], "prefs", PREF)
    log("uiready files", hou.findFiles("python3.13libs/uiready.py"))
    log("toggle assignments", hou.hotkeys.assignments("h", switch.TOGGLE_SYMBOL))
    for name, check, modname, pairs in RUNS:
        cleanup()
        # warm runs only: the first baseline measured ~10x slower (Houdini's start-up background work)
        STATE["perf"] = (name is None and bool(RESULTS)) or (check or "").startswith("perf_")
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
    log("done")
    LOGF.close()
    hdefereval.executeDeferred(lambda: hou.exit(suppress_save_prompt=True))


def off_screen():
    mw = hou.qt.mainWindow()
    mw.showNormal()   # a maximized window ignores move()
    mw.setGeometry(-12000, 100, 1600, 1000)


def start():
    off_screen()
    g = hou.qt.mainWindow().geometry()
    log("main window", g)
    if g.x() > -5000:   # never run synthetic input in a window on Hannes' screen
        log("ABORT: window not off screen")
        finish()
        return
    pump(driver())


QtCore.QTimer.singleShot(300, off_screen)
QtCore.QTimer.singleShot(5000, start)
