"""Evidence probe (F2a audit 3, item 2): how does Houdini's own rotate handle move several selected objects? Plain
Houdini, no modelUI: a box object A at (6, 0, 0) and a null N at the origin, both selected (N last); "pose" with E
(rotate); small drags at growing radii from N's screen point find a ring; then logs whether A turned about N (its
position changes) or about its own origin (position stays, rotation changes).

    python tests/modelui/rotate_ring_probe.py
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
        a = hou.node("/obj").createNode("geo", "A")
        a.createNode("box").parm("scale").set(0.5)
        a.parmTuple("t").set((6, 0, 0))
        nn = hou.node("/obj").createNode("null", "N")
        a.setSelected(True, clear_all_selected=True)
        nn.setSelected(True)
        nn.setCurrent(True)
        sv.setCurrentState("pose")
        yield 400
        vp.frameAll()
        yield 300
        r = sv.qtScreenGeometry()
        gl = mw.childAt(mw.mapFromGlobal(r.center()))
        QTest.mouseMove(win, win.mapFromGlobal(r.center()))
        QTest.keyClick(win, Qt.Key_E)
        yield 600
        vp.draw()
        yield 300
        v = vp.mapToScreen(hou.Vector3(0, 0, 0))
        gc = gl.mapToGlobal(QtCore.QPoint(int(v[0]), int(vp.size()[-1] - v[1])))
        log("state", sv.currentState(), "N on screen", gc)
        for dirx, diry in ((1, 0), (0, -1), (-1, 0), (0, 1)):
            for rr in range(40, 260, 6):
                a.setSelected(True, clear_all_selected=True)
                nn.setSelected(True)
                nn.setCurrent(True)
                yield 50
                a0, n0 = a.worldTransform(), nn.worldTransform()
                p0 = win.mapFromGlobal(gc) + QtCore.QPoint(dirx * rr, diry * rr)
                QTest.mouseMove(win, p0)
                QTest.mousePress(win, Qt.LeftButton, Qt.NoModifier, p0)
                for k in range(1, 5):
                    QTest.mouseMove(win, p0 + QtCore.QPoint(-diry * 8 * k, dirx * 8 * k))
                    yield 30
                QTest.mouseRelease(win, Qt.LeftButton, Qt.NoModifier, p0 + QtCore.QPoint(-diry * 32, dirx * 32))
                yield 200
                a1, n1 = a.worldTransform(), nn.worldTransform()
                if any(abs(x - y) > 1e-4 for x, y in zip(a1.asTuple() + n1.asTuple(), a0.asTuple() + n0.asTuple())):
                    log("diff A", [round(x - y, 5) for x, y in zip(a1.asTuple(), a0.asTuple())],
                        "diff N", [round(x - y, 5) for x, y in zip(n1.asTuple(), n0.asTuple())],
                        "A explode", {k: tuple(round(c, 4) for c in v) for k, v in a1.explode().items()},
                        "N explode", {k: tuple(round(c, 4) for c in v) for k, v in n1.explode().items()})
                    log("drag at", (dirx * rr, diry * rr), "N rot", n1.extractRotates(), "N pos", n1.extractTranslates(),
                        "A pos", a0.extractTranslates(), "->", a1.extractTranslates(), "A rot", a1.extractRotates(),
                        "selected", [x.name() for x in hou.selectedNodes()])
                    return
        log("no ring found")

    def pump(gen):
        try:
            QtCore.QTimer.singleShot(next(gen), lambda: pump(gen))
            return
        except StopIteration:
            pass
        except Exception:  # noqa: BLE001
            res["error"] = traceback.format_exc()
        with open(OUT, "w") as f:
            json.dump(res, f, indent=1, default=str)
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
