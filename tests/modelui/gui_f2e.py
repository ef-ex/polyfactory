"""GUI checks of modelUI F2e copy and paste (clipboard.py: Ctrl+C / Ctrl+V / Ctrl+Shift+V over a viewer, the menu
items), run INSIDE a throwaway Houdini.

Start it with:  PF_GUI_SCRIPT=gui_f2e.py PF_F1_SCRATCH=F:/cache/modelui/f2e/gui python tests/modelui/run_gui_f1.py
(own prefs, only this repository's polyfactory package, windows off screen, exits by itself, never saves a .hip).
Keys go the real path: QtTest key clicks with the cursor (QTest mouse move) over the pane, as Houdini routes hotkeys
by cursor. Baseline, one run per mutation (a source edit exec'd into the live module), baseline again.

What it cannot see: the round trip between two scenes and the paste maths (check_clipboard.py, headless, owns them),
Houdini's own Ctrl+C in tool states that bind it (KineFX, APEX, RBD, stage manager: theirs wins there by design),
a second viewer, the menu bar itself (the check runs the shipped items' scripts).
"""
import glob
import json
import os
import traceback

import hdefereval
import hou
from hutil.Qt import QtCore, QtWidgets
from PySide6.QtTest import QTest

from polyfactory.modelui import clipboard, containers, keys, kitbash, pieces_ui, scene, switch

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


CLIP = "F:/cache/modelui/f2e_gui_clipboard"


def suite(out):
    os.environ["PF_MODELUI_CLIPBOARD"] = CLIP
    hou.hipFile.clear(suppress_save_prompt=True)
    c = containers.create()
    ids = containers.add_pieces(c, [(FILES[3], "a", hou.hmath.buildScale(10, 10, 10) * hou.hmath.buildRotate(0, 30, 0)
                                     * hou.hmath.buildTranslate((-6, 0, 2)))])
    a = ("piece", c.sessionId(), ids[0])
    box = hou.node("/obj").createNode("geo", "box")
    box.createNode("box").parm("scale").set(2)
    box.parmTuple("t").set((4, 1, -3))
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
    mw = hou.qt.mainWindow()
    win = gl.window().windowHandle()
    sc = scene.current()
    ne = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.NetworkEditor) or hou.ui.curDesktop().createFloatingPaneTab(hou.paneTabType.NetworkEditor)   # the desk has none
    out["installed"] = bool(ok)
    sv.setCurrentState("select")
    yield 300

    def over(pane):
        g = pane.qtScreenGeometry().center()
        QTest.mouseMove(win, L(win, g))
        w = mw.childAt(mw.mapFromGlobal(g))
        if w is not None:
            w.setFocus()

    def key(k, mods=Qt.ControlModifier, pane=None):
        """Houdini sends a hotkey to the pane under the cursor as it last saw it: move there, let it see it, press."""
        over(pane or sv)
        yield 150
        over(pane or sv)
        yield 150
        QTest.keyClick(win, k, mods)

    def clip_stamp():
        try:
            return os.stat(os.path.join(CLIP, "clipboard.json")).st_mtime_ns
        except OSError:
            return None

    def n_objects():   # the scene's objects, not modelUI's hidden handle null (it comes and goes with the selection)
        return len([n for n in hou.node("/obj").children() if n.userData(pieces_ui.PROXY_MARK) != "1"])

    def world(pid):
        return pieces_ui.get_xform(pid)

    # --- Ctrl+C over the viewer: the selection to the clipboard ---------------------------------------------------------
    sc.select([a, bx])
    yield 300
    if os.path.isdir(CLIP):
        for f in os.listdir(CLIP):
            os.remove(os.path.join(CLIP, f))
    yield from key(Qt.Key_C)
    yield 400
    data = clipboard.read()
    log("  Ctrl+C: clipboard", data and (len(data["pieces"]), len(data["objects"])),
        "keys", hou.hotkeys.assignments("h.pane.gview", "h.pf_modelui_copy"))
    out["ctrl_c_copies"] = bool(data) and len(data["pieces"]) == 1 and len(data["objects"]) == 1
    if not data:
        for w in QtWidgets.QApplication.topLevelWidgets():   # an error dialog Houdini opened for the menu script?
            if w.isVisible() and w is not mw:
                texts = [x.text() for x in w.findChildren(QtWidgets.QLabel) if x.text()]
                texts += [x.toPlainText()[:2000] for x in w.findChildren(QtWidgets.QTextEdit)]
                log("  open window:", type(w).__name__, w.windowTitle(), texts)
        try:
            clipboard.copy()
            log("  direct copy:", clipboard.read() is not None)
        except Exception:  # noqa: BLE001
            log("  direct copy failed:", traceback.format_exc())
        return

    # --- Ctrl+C over another pane is not ours -------------------------------------------------------------------------
    sc.select([a])
    yield 200
    t0 = clip_stamp()
    if ne is not None:
        yield from key(Qt.Key_C, pane=ne)
        yield 400
    out["ctrl_c_viewer_only"] = ne is not None and t0 is not None and clip_stamp() == t0
    sc.select([a, bx])
    yield 200

    # --- Ctrl+V: same world transforms, one undo step, the pasted items selected --------------------------------------
    u0 = len(hou.undos.undoLabels())
    n0 = len(containers.piece_rows(c)), n_objects()
    yield from key(Qt.Key_V)
    yield 600
    labels = hou.undos.undoLabels()
    new = [p for p in sc.selected() if p not in (a, bx)]
    log("  Ctrl+V: labels", labels[:2], "selected", sc.selected())
    same = len(new) == 2 and all(any(world(p).isAlmostEqual(world(q), 1e-4) for q in (a, bx)) for p in new)
    out["ctrl_v_pastes"] = (same and len(labels) == u0 + 1 and labels[0] == "modelUI: paste"
                            and len(containers.piece_rows(c)) == n0[0] + 1)
    hou.undos.performUndo()
    yield 300
    n_after = len(containers.piece_rows(c)), n_objects()
    log("  undo paste: counts before", n0, "after undo", n_after, [n.name() for n in hou.node("/obj").children()],
        "labels", hou.undos.undoLabels()[:2])
    out["paste_undone"] = n_after == n0

    # --- Ctrl+Shift+V: the copied set standing at the look-at point --------------------------------------------------
    sc.select([a, bx])
    yield 200
    at = kitbash.look_at()
    lo, hi = data["box"]
    want = hou.hmath.buildTranslate(at[0] - 0.5 * (lo[0] + hi[0]), at[1] - lo[1], at[2] - 0.5 * (lo[2] + hi[2]))
    yield from key(Qt.Key_V, Qt.ControlModifier | Qt.ShiftModifier)
    yield 600
    new = [p for p in sc.selected() if p not in (a, bx)]
    log("  Ctrl+Shift+V: look-at", at, "selected", sc.selected())
    out["ctrl_shift_v_at_look_at"] = len(new) == 2 and all(
        any(world(p).isAlmostEqual(world(q) * want, 1e-3) for q in (a, bx)) for p in new)
    if new:
        hou.undos.performUndo()
        yield 300

    # --- the menu items (the shipped MainMenuCommon.xml's scripts, as Houdini runs them) ------------------------------
    import xml.etree.ElementTree as ET
    items = {e.get("id"): e.find("scriptCode").text
             for e in ET.parse(os.path.join(os.environ["POLYFACTORY"], "MainMenuCommon.xml")).getroot().iter("scriptItem")}
    sc.select([bx])
    yield 200
    ok_m = all(k in items and k in keys.COMMANDS for k in ("h.pf_modelui_copy", "h.pf_modelui_paste", "h.pf_modelui_paste_at"))
    if ok_m:
        exec(items["h.pf_modelui_copy"], {})
        d = clipboard.read()
        ok_m = bool(d) and len(d["objects"]) == 1 and not d["pieces"]
        n1 = n_objects()
        if ok_m:
            for k in ("h.pf_modelui_paste", "h.pf_modelui_paste_at"):
                exec(items[k], {})   # the item defers the paste until after the menu action
                for _ in range(20):
                    yield 100
                    if n_objects() > n1 + ("at" in k):
                        break
            log("  menu: objects", n1, "->", n_objects(), "labels", hou.undos.undoLabels()[:3])
            ok_m = n_objects() == n1 + 2
            hou.undos.performUndo()
            hou.undos.performUndo()
            yield 300
    out["menu_items_work"] = bool(ok_m)

    # --- off: the keys are Houdini's again ----------------------------------------------------------------------------
    switch.uninstall()
    yield 600
    sv_off = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)   # Houdini's own desk again: its viewer
    sc.select([a])
    yield 200
    t0 = clip_stamp()
    yield from key(Qt.Key_C, pane=sv_off)
    log("  off: desk", hou.ui.curDesktop().name(), "viewer", sv_off and sv_off.name())
    yield 400
    out["off_ctrl_c_not_ours"] = sv_off is not None and clip_stamp() == t0


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
    leak = undo_open()
    if leak:
        log("  UNDO LEAK before cleanup:", leak)
    _q(switch.uninstall)
    _q(lambda: hou.ui.desktop(STATE["desk0"]).setAsCurrent())
    switch._state["on"] = False
    if keys.snapshot() != STATE["keys0"]:
        log("  KEYS CHANGED after the run: restoring")
        _q(keys.revert)


MODS = {"clipboard": clipboard, "keys": keys, "switch": switch}


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

    def restore():
        exec(compile(src, mod.__file__, "exec"), mod.__dict__)
    return restore


CB = "clipboard"
MUTATIONS = [   # (mutation, the check it must redden, module, [(old, new)])
    ("not_a_switch", "installed", "switch", [("def install():", "def install():\n    return False\n\n\ndef _unused():")]),
    ("no_copy_key", "ctrl_c_copies", "keys", [('    ("h.pane.gview", "h.pf_modelui_copy", "Ctrl+C"),\n', "")]),
    ("copy_key_everywhere", "ctrl_c_viewer_only", "keys", [('    ("h.pane.gview", "h.pf_modelui_copy", "Ctrl+C"),', '    ("h", "h.pf_modelui_copy", "Ctrl+C"),')]),
    ("no_paste_key", "ctrl_v_pastes", "keys", [('    ("h.pane.gview", "h.pf_modelui_paste", "Ctrl+V"),\n', "")]),
    ("paste_not_grouped", "paste_undone", CB, [('    with hou.undos.group("modelUI: paste"):', "    if True:")]),
    ("no_paste_at_key", "ctrl_shift_v_at_look_at", "keys", [('    ("h.pane.gview", "h.pf_modelui_paste_at", "Ctrl+Shift+V"),\n', "")]),
    ("paste_at_does_nothing", "menu_items_work", CB, [("    return paste(at=kitbash.look_at())", "    return []")]),
    ("keys_not_reverted", "off_ctrl_c_not_ours", "keys", [("install, uninstall = apply, revert", "install, uninstall = apply, (lambda H=None: None)")]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
if os.environ.get("PF_F1_QUICK"):
    RUNS = RUNS[:1]
if os.environ.get("PF_F2E_ONLY"):
    RUNS = [RUNS[0]] + [m for m in MUTATIONS if m[0] in os.environ["PF_F2E_ONLY"].split(",")]
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
