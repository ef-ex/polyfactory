"""Probe: do run-time hotkeys still work after apply -> revert -> apply in one session? (open defect, 2026-11-05)

    python tests/modelui/keys_probe.py

Plain python: launches a throwaway off-screen Houdini on this file (shortcut_probe.launch) and prints the result.
Inside Houdini: tests Q and W by their effect (viewer state after a QtTest key click on the viewer) for stock keys,
plain hou.hotkeys add/remove/add (no modelUI code), modelUI keys.apply/revert/apply and the full switch on/off/on.
"""
import json
import os
import sys

OUT = "F:/cache/modelui/probe/result.json"


def inside():
    import traceback

    import hdefereval
    import hou
    from hutil.Qt import QtCore, QtWidgets
    from PySide6.QtTest import QTest

    from polyfactory.modelui import keys, switch
    Qt = QtCore.Qt
    H = hou.hotkeys
    ST = keys.STATE
    res = {"log": []}

    def log(*a):
        res["log"].append(" ".join(str(x) for x in a))

    def qw(label, hover=False, seq=None, at=0.5, wait=300):
        mw = hou.qt.mainWindow()
        sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
        r = sv.qtScreenGeometry()
        t = mw.childAt(mw.mapFromGlobal(QtCore.QPoint(r.x() + r.width() // 3, r.y() + r.height() // 3)))
        sv.setCurrentState("objview")
        others = [t for t in hou.ui.paneTabs() if isinstance(t, hou.SceneViewer) and t != sv]
        for o in others:
            o.setCurrentState("objview")
        if hover:   # the cursor over this viewer, as when a person presses the key
            QTest.mouseMove(mw.windowHandle(), mw.windowHandle().mapFromGlobal(
                QtCore.QPoint(r.x() + int(r.width() * at), r.y() + int(r.height() * at))))
        yield 250
        out = []
        for k in seq or (Qt.Key_Q, Qt.Key_W, Qt.Key_Q):
            t.setFocus()
            QTest.keyClick(mw.windowHandle(), k)
            yield wait
            out.append(sv.currentState())
        log(label, [chr(k) for k in seq or (Qt.Key_Q, Qt.Key_W, Qt.Key_Q)], "->", out, sv.currentState(), "desk", hou.ui.curDesktop().name(), sv.name(),
            "other viewers", [(o.name(), o.currentState()) for o in others])

    def steps():
        mw = hou.qt.mainWindow()
        mw.showNormal()
        mw.setGeometry(-12000, 100, 1600, 1000)
        yield 300
        for i, w in enumerate(QtWidgets.QApplication.topLevelWidgets()):
            if w.isVisible() and w is not mw and w.frameGeometry().right() > -5000:
                w.move(-9000, 100 + 60 * i)
        yield 200
        if any(w.isVisible() and w.frameGeometry().right() > -5000 for w in QtWidgets.QApplication.topLevelWidgets()):
            res["abort"] = "window on screen"
            return
        for ctx_sym, key in (((ST, ST + ".new_select"), "Q"), ((ST, ST + ".new_move"), "W")):
            log("conflicts", key, H.findConflicts(ctx_sym[0], ctx_sym[1], key))
        all_q = H.findConflicts("h", "h.redo", "Q")
        log("Q anywhere (non-SOP-tool):", [c for c in all_q if ".state.sop." not in c and "first_person" not in c])
        for nm in "abc":
            hou.node("/obj").createNode("geo", nm)
        orig = list(keys.KEYS)
        for desk_name in ("Build", "ModelUI"):
            hou.ui.desktop(desk_name).setAsCurrent()
            yield 600
            for sym in ("volatile_select", "new_select"):
                for unbind in (True, False):
                    rows = [(ST, ST + "." + sym, "Q")] + [r for r in orig[1:] if unbind or not r[1].startswith("-")]
                    keys.KEYS[:] = rows
                    keys.apply()
                    yield from qw("matrix %s %s unbind=%s" % (desk_name, sym, unbind), hover=True,
                                  seq=[Qt.Key_W, Qt.Key_Q])
                    keys.revert()
        keys.KEYS[:] = orig
        res["stop"] = True
        return
        yield from qw("stock")
        pure = [(ST, ST + ".new_select", "Q"), (ST, ST + ".new_move", "W")]
        for n in range(2):
            log("pure add", [H.addAssignment(*r) for r in pure])
            yield from qw("pure apply %d" % n)
            log("pure remove", [H.removeAssignment(*r) for r in pure])
            yield from qw("pure revert %d" % n)
        for n in range(2):
            keys.apply()
            yield from qw("keys.apply %d" % n)
            keys.revert()
            yield from qw("keys.revert %d" % n)
        for n in range(2):
            switch.install()
            yield 900
            yield from qw("switch on %d" % n)
            yield from qw("switch on %d, hover" % n, hover=True)
            if n == 0:
                for seq in ("QWERTQ", "WTQ", "RTQ"):
                    yield from qw("seq", hover=True, seq=[getattr(Qt, "Key_" + c) for c in seq])
                    log("   pose handle", hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer).currentState())
                for nm in "abc":
                    hou.node("/obj").createNode("geo", nm)
                log("selected", [n.path() for n in hou.selectedNodes()])
                yield from qw("objects, hover 0.75", hover=True, seq=[Qt.Key_W, Qt.Key_Q], at=0.75)
                yield from qw("objects, wait 1s", hover=True, seq=[Qt.Key_W, Qt.Key_Q], wait=1000)
                yield from qw("objects, hover 0.75, wait 1s", hover=True, seq=[Qt.Key_W, Qt.Key_Q], at=0.75, wait=1000)
                for seq in ("WQ",):
                    yield from qw("with objects", hover=True, seq=[getattr(Qt, "Key_" + c) for c in seq])
            switch.uninstall()
            yield 300
            yield from qw("switch off %d" % n)
            yield from qw("switch off %d, hover" % n, hover=True)

    def pump(gen):
        try:
            QtCore.QTimer.singleShot(next(gen), lambda: pump(gen))
            return
        except StopIteration:
            pass
        except Exception:  # noqa: BLE001
            res["error"] = traceback.format_exc()
        with open(OUT, "w") as f:
            json.dump(res, f, indent=1)
        hdefereval.executeDeferred(lambda: hou.exit(suppress_save_prompt=True))
    QtCore.QTimer.singleShot(4000, lambda: pump(steps()))


try:
    import hou  # noqa: F401
    inside()
except ImportError:
    if __name__ == "__main__":
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import shortcut_probe
        sys.exit(shortcut_probe.launch(os.path.abspath(__file__)))
