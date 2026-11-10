"""GUI checks of modelUI F12 feedback (feedback_overlay.py, feedback.py, the F12 key in keys.py), run INSIDE a throwaway
Houdini.

Start it with:  PF_GUI_SCRIPT=gui_feedback.py PF_F1_SCRATCH=F:/cache/modelui/fb/gui python tests/modelui/run_gui_f1.py
(through bash F:/cache/modelui/gui_lock.sh). PF_FEEDBACK_ROOT points into the scratch folder. Keys go the real path (QtTest
key clicks, cursor over the pane); strokes and notes are QtTest mouse events on the overlay.

What it cannot see: a real screen grab of the GL viewport (the window is off screen: only the size of screenshot.png is
judged), pixels_per_point other than the PC's own (headless check_feedback.py owns the scaling of the files), the file
dialog of Attach, the polyfactory menu entry.
"""
import json
import os
import shutil
import traceback

import hdefereval
import hou
from hutil.Qt import QtCore, QtWidgets
from PySide6.QtTest import QTest

from polyfactory.modelui import feedback, feedback_overlay, keys, scene, switch

OUT = os.environ["PF_F1_OUT"]
ROOT = os.path.dirname(OUT).replace("\\", "/") + "/feedback"
os.environ["PF_FEEDBACK_ROOT"] = ROOT
LOGF = open(OUT + ".log", "w", buffering=1)
Qt = QtCore.Qt
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
    gl = mw.childAt(mw.mapFromGlobal(sv.qtScreenGeometry().center()))
    return sv, gl


def L(win, g):
    return win.mapFromGlobal(g)


def esc(ov):
    """Esc on the overlay. It may be deleted (WA_DeleteOnClose) before QTest sends the key release: that is the effect."""
    try:
        QTest.keyClick(ov, Qt.Key_Escape)
    except RuntimeError as e:
        if "already deleted" not in str(e):
            raise


def folders():
    return sorted(d for d, _, fs in os.walk(ROOT) if "feedback.json" in fs)


def overlay():
    return hou.session.__dict__.get(feedback_overlay.KEY)


def suite(out):
    log("  suite start: overlay", overlay())
    shutil.rmtree(ROOT, ignore_errors=True)
    hou.hipFile.clear(suppress_save_prompt=True)
    box = hou.node("/obj").createNode("geo", "fb_box")
    box.createNode("box")
    yield 100
    ok = switch.install()
    yield 1200
    sv, gl = viewer()
    mw = hou.qt.mainWindow()
    win = gl.window().windowHandle()
    ne = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.NetworkEditor) or hou.ui.curDesktop().createFloatingPaneTab(hou.paneTabType.NetworkEditor)   # the desk has none
    out["installed"] = bool(ok)
    scene.current().select([box.sessionId()])
    yield 300

    def key(k, mods=Qt.NoModifier, pane=None):
        g = (pane or sv).qtScreenGeometry().center()
        for _ in range(2):   # Houdini routes a hotkey by the cursor as it last saw it
            QTest.mouseMove(win, L(win, g))
            w = mw.childAt(mw.mapFromGlobal(g))
            if w is not None:
                w.setFocus()
            yield 150
        QTest.keyClick(win, k, mods)

    def close_overlay():
        ov = overlay()
        if ov is not None:
            ov.done = True
            ov.close()

    out["f12_binding_set"] = "F12" in hou.hotkeys.assignments("h", "h.pf_modelui_feedback")
    log("  F12 bound in h:", hou.hotkeys.assignments("h", "h.pf_modelui_feedback"))

    # --- F12 over another pane (the network editor): the key is global ------------------------------------------------------
    yield from key(Qt.Key_F12, pane=ne)
    yield 900
    out["f12_anywhere"] = ne is not None and overlay() is not None
    close_overlay()
    yield 300

    # --- F12 over the viewer opens the overlay over the whole main window -------------------------------------------------
    yield from key(Qt.Key_F12)
    yield 900
    ov = overlay()
    out["f12_opens"] = ov is not None and ov.isVisible() and ov.geometry() == mw.geometry() and not ov.shot.isNull()
    if ov is None:
        return
    # --- a stroke, a note, a comment, then Ctrl+Enter writes a complete folder ----------------------------------------------
    ppp = ov.ppp
    P = QtCore.QPoint
    QTest.mousePress(ov, Qt.LeftButton, Qt.NoModifier, P(200, 300))
    QTest.mouseMove(ov, P(230, 310))
    QTest.mouseMove(ov, P(260, 330))
    QTest.mouseRelease(ov, Qt.LeftButton, Qt.NoModifier, P(260, 330))
    ov.buttons["note"].click()
    QTest.mouseClick(ov, Qt.LeftButton, Qt.NoModifier, P(500, 400))
    yield 200
    if ov.notes:
        ov.notes[0].edit.setPlainText("make this wider")
    ov.comment.setPlainText("the gizmo is in the way")
    ov.comment.setFocus()
    yield 200
    n0 = len(folders())
    QTest.keyClick(ov.comment, Qt.Key_Return, Qt.ControlModifier)
    for _ in range(40):
        if len(folders()) > n0 and overlay() is None:
            break
        yield 250
    fs = folders()
    out["ctrl_enter_closes_and_writes"] = len(fs) == n0 + 1 and overlay() is None
    if len(fs) != n0 + 1:
        log("  folders", fs, "overlay", overlay())
        close_overlay()
        return
    f = fs[-1]
    fb = json.load(open(f + "/feedback.json"))
    st = json.load(open(f + "/state.json"))
    from hutil.Qt import QtGui
    shot = QtGui.QImage(f + "/screenshot.png")
    st0 = fb["strokes"][0] if fb["strokes"] else {"points": [[0, 0], [0, 0]]}
    out["folder_complete"] = (sorted(os.listdir(f)) == ["feedback.json", "marked.png", "markings.png", "screenshot.png",
                                                       "state.json"]
                              and not shot.isNull() and [shot.width(), shot.height()] == fb["window"]["pixels"]
                              and fb["window"]["width"] == mw.width()
                              and os.path.basename(os.path.dirname(f)) == feedback.person())
    out["markings_recorded"] = (len(fb["strokes"]) == 1 and fb["comment"] == "the gizmo is in the way"
                                and len(fb["notes"]) == 1 and fb["notes"][0]["text"] == "make this wider"
                                and fb["strokes"][0]["colour"] == "#ff3b30" and fb["strokes"][0]["width"] == 6 * ppp
                                and abs(st0["points"][0][0] - 200 * ppp) < 1e-6 and abs(st0["points"][-1][1] - 330 * ppp) < 1e-6
                                and abs(fb["notes"][0]["x"] - 500 * ppp) < 1e-6 and abs(fb["notes"][0]["y"] - 400 * ppp) < 1e-6)
    out["state_in_folder"] = (st.get("modelui_on") is True and [s["name"] for s in st.get("selection", [])] == ["fb_box"]
                              and st.get("houdini") == hou.applicationVersionString())
    log("  state:", {k: v for k, v in st.items() if k != "log"})

    # --- Esc: no markings closes without asking; with markings it asks, Cancel keeps it, Discard closes; nothing written ---
    n0 = len(folders())
    yield from key(Qt.Key_F12)
    yield 900
    ov = overlay()
    if ov is None:
        out["esc_cancels_nothing_written"] = False
        return
    esc(ov)
    yield 300
    esc_plain = overlay() is None
    yield from key(Qt.Key_F12)
    yield 900
    ov = overlay()
    if ov is None:
        out["esc_cancels_nothing_written"] = False
        return
    QTest.mousePress(ov, Qt.LeftButton, Qt.NoModifier, P(100, 100))
    QTest.mouseRelease(ov, Qt.LeftButton, Qt.NoModifier, P(140, 100))
    asked = []
    log("  before esc: strokes", len(ov.strokes), "cur", ov.cur, "visible", ov.isVisible(), "active", ov.isActiveWindow(),
        "tool", ov.tool)

    def answer(button):   # a poller that never finds its dialog gives up (a stale one would steal the next run's)
        tries = [0]

        def go():
            tries[0] += 1
            if tries[0] > 30:
                return
            for w in QtWidgets.QApplication.topLevelWidgets():
                if isinstance(w, QtWidgets.QMessageBox) and w.isVisible():
                    asked.append(w.windowTitle())
                    w.button(button).click()
                    return
            QtCore.QTimer.singleShot(100, go)
        return go
    QtCore.QTimer.singleShot(300, answer(QtWidgets.QMessageBox.Cancel))
    esc(ov)
    yield 300
    kept = overlay() is ov and ov.isVisible()
    QtCore.QTimer.singleShot(300, answer(QtWidgets.QMessageBox.Discard))
    esc(ov)
    yield 500
    out["esc_asks_with_markings"] = len(asked) == 2 and kept
    log("  esc: asked", asked, "kept", kept)
    out["esc_cancels_nothing_written"] = esc_plain and overlay() is None and len(folders()) == n0
    # --- one overlay at a time ----------------------------------------------------------------------------------------------
    yield from key(Qt.Key_F12)
    yield 900
    first = overlay()
    yield from key(Qt.Key_F12)
    yield 900
    out["one_overlay_only"] = first is not None and overlay() is first
    close_overlay()
    yield 300
    # --- off: the key goes back exactly, F12 does nothing -----------------------------------------------------------------
    switch.uninstall()
    switch._state["on"] = False
    yield 600
    out["key_reverts_when_off"] = (keys.snapshot() == STATE["keys0"]
                                   and "F12" not in hou.hotkeys.assignments("h", "h.pf_modelui_feedback"))
    yield from key(Qt.Key_F12)
    yield 900
    out["f12_dead_when_off"] = overlay() is None
    close_overlay()


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
    ov = overlay()
    if ov is not None:
        ov.done = True
        _q(ov.close)
    leak = undo_open()
    if leak:
        log("  UNDO LEAK before cleanup:", leak)
    _q(switch.uninstall)
    _q(lambda: hou.ui.desktop(STATE["desk0"]).setAsCurrent())
    switch._state["on"] = False
    if keys.snapshot() != STATE["keys0"]:
        log("  KEYS CHANGED after the run: restoring")
        _q(keys.revert)


MODS = {"keys": keys, "switch": switch, "overlay": feedback_overlay, "feedback": feedback}


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


MUTATIONS = [   # (mutation, the check it must redden, module, [(old, new)])
    ("not_a_switch", "installed", "switch", [("def install():", "def install():\n    return False\n\n\ndef _unused():")]),
    ("no_f12_key", "f12_opens", "keys", [('    ("h", "h.pf_modelui_feedback", "F12"),\n', "")]),
    ("f12_viewer_only", "f12_anywhere", "keys", [('("h", "h.pf_modelui_feedback", "F12")', '("h.pane.gview", "h.pf_modelui_feedback", "F12")')]),
    ("keys_not_reverted", "key_reverts_when_off", "keys", [("install, uninstall = apply, revert", "install, uninstall = apply, (lambda H=None: None)")]),
    ("no_f12_key_bound", "f12_binding_set", "keys", [('    ("h", "h.pf_modelui_feedback", "F12"),\n', "")]),
    ("keys_not_reverted_f12", "f12_dead_when_off", "keys", [("install, uninstall = apply, revert", "install, uninstall = apply, (lambda H=None: None)")]),
    ("no_ctrl_enter", "ctrl_enter_closes_and_writes", "overlay", [('for seq in ("Ctrl+Return", "Ctrl+Enter"):', "for seq in ():")]),
    ("stroke_not_kept", "markings_recorded", "overlay", [("            self.strokes.append(self.cur)\n", "")]),
    ("notes_dropped", "markings_recorded", "overlay", [("        return [n for n in self.notes if n.edit.toPlainText().strip()]", "        return []")]),
    ("state_empty", "state_in_folder", "overlay", [("state = feedback.collect_state()", "state = {}")]),
    ("no_esc", "esc_cancels_nothing_written", "overlay", [('        QShortcut(QtGui.QKeySequence("Esc"), self, activated=self.cancel)\n', "")]),
    ("esc_never_asks", "esc_asks_with_markings", "overlay", [("if self.has_markings() and not self._confirm_discard():", "if False:")]),
    ("esc_writes", "esc_cancels_nothing_written", "overlay", [("        self.done = True\n        self.close()\n\n    def _confirm_discard", "        self.send()\n\n    def _confirm_discard")]),
    ("second_overlay", "one_overlay_only", "overlay", [("    if hou.session.__dict__.get(KEY) is not None:\n        return None\n", "")]),
    ("folder_incomplete", "folder_complete", "feedback", [('("screenshot.png", shot), ', "")]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
if os.environ.get("PF_F1_QUICK"):
    RUNS = RUNS[:1]
if os.environ.get("PF_FB_ONLY"):
    RUNS = [RUNS[0]] + [m for m in MUTATIONS if m[0] in os.environ["PF_FB_ONLY"].split(",")] + [RUNS[0]]
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
            cleanup()   # with the mutant still loaded: its own overlay ends first
            if restore:
                restore()
        out = {k: v if isinstance(v, str) else bool(v) for k, v in out.items()}
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
