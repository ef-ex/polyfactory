"""Pitfall probe: does Shift+drag on Houdini's own object handle stop working after a session's first round, without
modelUI? (F2a, 2026-11-06)

    python tests/modelui/shift_handle_probe.py

Plain python: launches a throwaway off-screen Houdini (shortcut_probe.launch; only the polyfactory package, modelUI
never switched on). Inside: two rounds in one session, each: clear the hip, a box object, select it, "pose" state,
plain drag on the handle centre, then Shift+drag on it; logs how far the object moved each time.
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
    Qt = QtCore.Qt
    res = {"log": []}

    def log(*a):
        res["log"].append(" ".join(str(x) for x in a))

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
        sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
        sv.setViewportLayout(hou.geometryViewportLayout.Single)
        vp = sv.curViewport()
        win = mw.windowHandle()
        for rnd in (1, 2, 3):
            hou.hipFile.clear(suppress_save_prompt=True)
            g = hou.node("/obj").createNode("geo", "box")
            g.createNode("box").parm("scale").set(3)
            g.setSelected(True, clear_all_selected=True)
            sv.setCurrentState("pose")
            yield 300
            vp.frameAll()
            vp.draw()
            yield 600
            r = sv.qtScreenGeometry()
            gl = mw.childAt(mw.mapFromGlobal(r.center()))
            for mods, label in ((Qt.NoModifier, "plain"), (Qt.ShiftModifier, "shift")):
                t0 = g.worldTransform().extractTranslates()
                v = vp.mapToScreen(t0)
                gp = gl.mapToGlobal(QtCore.QPoint(int(v[0]), int(vp.size()[-1] - v[1])))
                loc = win.mapFromGlobal(gp)
                QTest.mouseMove(win, loc)
                QTest.mousePress(win, Qt.LeftButton, mods, loc)
                for k in range(1, 7):
                    QTest.mouseMove(win, loc + QtCore.QPoint(10 * k, 0))
                    yield 30
                QTest.mouseRelease(win, Qt.LeftButton, mods, loc + QtCore.QPoint(60, 0))
                yield 400
                log("round", rnd, label, "drag moved the box by %.3f" % (g.worldTransform().extractTranslates() - t0).length(),
                    "selected", [n.path() for n in hou.selectedNodes()], "state", sv.currentState())

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
