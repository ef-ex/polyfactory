"""GUI checks of the modelUI feedback round 1 (2026-11-10), run INSIDE a throwaway Houdini like gui_f2d.py: the desk
has no network / tree / material pane, Alt+A / Alt+N start Align over the viewer only and revert exactly, the
Explorer's Align buttons (no kitbash button), and an asset dropped from the Asset Browser over the viewer becomes one
kitbash piece standing on the ground at the cursor.

Start: PF_GUI_SCRIPT=gui_fb1.py PF_F1_SCRATCH=F:/cache/modelui/fb1/gui python tests/modelui/run_gui_f1.py
(through bash F:/cache/modelui/gui_lock.sh). Cannot see: a real OS drag (handle_dropped_at is called with the
point), Houdini's own key dispatcher beyond QTest key events with the cursor over the viewer, a network editor
context (its Alt+A binding is checked as assignments in the contexts h / h.pane / h.pane.wsheet / h.pane.textport).
"""
import glob
import json
import os
import traceback

import hdefereval
import hou
from hutil.Qt import QtCore, QtWidgets
from PySide6.QtTest import QTest

from polyfactory.asset_library import browser_ui
from polyfactory.modelui import align, containers, explorer, input_layer, keys, kitbash, pieces_ui, scene, switch

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


def picking():
    return align._state["pick"] is not None


OLD_DESK = os.path.join(os.environ["POLYFACTORY"], "desktop", "ModelUI_fb1old.desk")
BAD = ("NetworkEditor", "TreeView", "MaterialPalette")
CTX_OTHER = ("h", "h.pane", "h.pane.wsheet", "h.pane.textport")
SYMS = ("h.pf_modelui_align", "h.pf_modelui_normal_align")


def other_alt():
    """Where Alt+A / Alt+N are bound to our actions outside the viewer context (must be nowhere)."""
    return [(ctx, s) for ctx in CTX_OTHER for s in SYMS for k in hou.hotkeys.assignments(ctx, s) if k in ("Alt+A", "Alt+N")]


def suite(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    c = containers.create()
    big = hou.hmath.buildScale(10, 10, 10)
    ids = containers.add_pieces(c, [(FILES[3], "a", big * hou.hmath.buildTranslate((-15, 0, 0))),
                                    (FILES[3], "t", big * hou.hmath.buildTranslate((12, 0, -3)))])
    a = ("piece", c.sessionId(), ids[0])
    before = keys.snapshot()
    alt0 = {ctx: {s: tuple(hou.hotkeys.assignments(ctx, s)) for s in SYMS} for ctx in CTX_OTHER + ("h.pane.gview",)}
    yield 100
    out["installed"] = bool(switch.install())
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
    sv.setCurrentState("select")
    yield 300
    # fix 1: desk
    types = [t.type().name() for t in hou.ui.curDesktop().paneTabs()]
    out["desk_no_network_tree_material"] = not any(t in BAD for t in types)
    log("pane types", types)
    # fix 4a: keys
    out["alt_a_not_outside_viewer"] = not other_alt()
    sc.select([a])
    yield 200

    def hover(fx=0.5, fy=0.5):
        g = gl.mapToGlobal(QtCore.QPoint(int(gl.width() * fx), int(gl.height() * fy)))
        QTest.mouseMove(win, L(win, g))
        gl.setFocus()
        return g

    hover()
    QTest.keyClick(win, Qt.Key_A, Qt.AltModifier)
    yield 300
    out["alt_a_starts_align"] = picking()
    align._end_pick()
    yield 100
    hover()
    QTest.keyClick(win, Qt.Key_N, Qt.AltModifier)
    yield 300
    out["alt_n_starts_normal"] = picking()
    align._end_pick()
    yield 100
    # fix 2 + 4b: explorer buttons
    ex = explorer.Explorer()
    btns = {b.text(): b for b in ex.findChildren(QtWidgets.QPushButton)}
    out["explorer_buttons"] = (all(t in btns for t in ("Align", "Quick Align", "Normal Align"))
                               and not any("kitbash" in t.lower() for t in btns) and "Alt+A" in btns["Align"].toolTip())
    if "Align" in btns:
        btns["Align"].click()
        yield 200
        out["explorer_align_starts_pick"] = picking()
        align._end_pick()
    ex.close_down()
    ex.deleteLater()
    # fix 3: drop over the viewer, at a point that is not the look-at point
    sc.select([])
    n0, nc0 = len(sc.pieces()), len(containers.containers())
    g = hover(0.75, 0.8)
    px, dpr = gl.mapFromGlobal(g), gl.devicePixelRatioF()
    d, o = sv.curViewport().mapToWorld(int(px.x() * dpr), int((gl.height() - px.y()) * dpr))
    d, o = hou.Vector3(d), hou.Vector3(o)
    exp = o + d * (-o[1] / d[1])   # my own ray / ground plane (y = 0)
    browser_ui.AssetDropHandler().handle_dropped_at({"file_path": FILES[3], "name": "dropped"}, g)
    yield 300
    pcs = sc.pieces()
    out["drop_one_piece_same_container"] = len(pcs) == n0 + 1 and len(containers.containers()) == nc0
    sel = sc.selected()
    out["drop_selected"] = len(sel) == 1 and sel[0] in pcs
    out["drop_at_cursor_on_ground"] = False
    if len(sel) == 1 and isinstance(sel[0], tuple):
        cont = hou.nodeBySessionId(sel[0][1])
        bb = [p for p in cont.displayNode().geometry().prims() if p.attribValue("pf_piece") == sel[0][2]][0].boundingBox()
        ctr = bb.center() * cont.worldTransform()
        # 1e-2 world units at a ground point ~10-30 units from the camera (float32 storage, int pixel rounding)
        out["drop_at_cursor_on_ground"] = abs(bb.minvec()[1]) < 1e-3 and abs(ctr[0] - exp[0]) < 1e-2 and abs(ctr[2] - exp[2]) < 1e-2
        log("drop centre", tuple(ctr), "expected", tuple(exp), "miny", bb.minvec()[1])
    err = undo_open()
    hou.undos.performUndo()
    out["drop_one_undo"] = len(sc.pieces()) == n0 and not err
    # off: every binding back exactly
    switch.uninstall()
    yield 600
    now = {ctx: {s: tuple(hou.hotkeys.assignments(ctx, s)) for s in SYMS} for ctx in CTX_OTHER + ("h.pane.gview",)}
    out["keys_revert_exact"] = keys.snapshot() == before and now == alt0
    log("revert", keys.snapshot() == before, now == alt0)


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


MODS = {"keys": keys, "browser_ui": browser_ui, "kitbash": kitbash, "explorer": explorer, "switch": switch}


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


def old_desk():
    """The desk as it was before this round, under another name (removed again at the end)."""
    import subprocess
    t = subprocess.run(["git", "show", "8be4b10:polyfactory/desktop/ModelUI.desk"], capture_output=True, text=True,
                       cwd=os.environ["POLYFACTORY"]).stdout
    with open(OLD_DESK, "w", newline="") as f:
        f.write(t.replace("ModelUI.panetab", "ModelUI_fb1old.panetab"))


MUTATIONS = [   # (mutation, the check it must redden, module, [(old, new)])
    ("install_fails", "installed", "switch", [("            importlib.import_module(name).install()", "            raise RuntimeError('mutation')")]),
    ("explorer_button_dead", "explorer_align_starts_pick", "explorer", [("getattr(align, f)()", "None")]),
    ("drop_not_selected", "drop_selected", "kitbash", [("    return add_files([path], at=at)", "    r = add_files([path], at=at)\n    scene.current().select([])\n    return r")]),
    ("old_desk", "desk_no_network_tree_material", "switch", [('DESK = "ModelUI"', 'DESK = "ModelUI_fb1old"')]),
    ("no_alt_a_key", "alt_a_starts_align", "keys", [('    ("h.pane.gview", "h.pf_modelui_align", "Alt+A"),\n', "")]),
    ("alt_a_in_h", "alt_a_not_outside_viewer", "keys", [('    ("h.pane.gview", "h.pf_modelui_align", "Alt+A"),', '    ("h", "h.pf_modelui_align", "Alt+A"),')]),
    ("no_alt_n_key", "alt_n_starts_normal", "keys", [('    ("h.pane.gview", "h.pf_modelui_normal_align", "Alt+N"),\n', "")]),
    ("revert_noop", "keys_revert_exact", "keys", [("    changes, n, kept = _changes(), 0, []\n    while changes:", "    changes, n, kept = _changes(), 0, []\n    while False:")]),
    ("no_quick_button", "explorer_buttons", "explorer", [('("Quick Align", "quick_align", "Shift+A"), ', "")]),
    ("kitbash_button_back", "explorer_buttons", "explorer", [('("Align", "align", "A")', '("Add kitbash pieces...", "align", "A"), ("Align", "align", "A")')]),
    ("drop_ignored", "drop_one_piece_same_container", "browser_ui", [("            if not switch.is_on() or not asset_data", "            if True or not asset_data")]),
    ("drop_at_lookat", "drop_at_cursor_on_ground", "kitbash", [("    return add_files([path], at=at)", "    return add_files([path])")]),
    ("drop_two_undo_steps", "drop_one_undo", "kitbash", [("    return add_files([path], at=at)", "    r = add_files([path], at=at)\n    hou.node('/obj').createNode('null')\n    return r")]),
]
RUNS = [(None, None, None, None)] + MUTATIONS + [(None, None, None, None)]
if os.environ.get("PF_F1_QUICK"):
    RUNS = RUNS[:1]
RESULTS = []


def driver():
    old_desk()
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
    os.remove(OLD_DESK)
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
