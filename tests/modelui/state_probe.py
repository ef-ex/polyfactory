"""Control probe: can a node-less Python viewer state be entered at object level? (F2a blocker, 2026-11-06)

    python tests/modelui/state_probe.py

Plain python: launches a throwaway off-screen Houdini on this file (shortcut_probe.launch) and prints the result.
Inside Houdini: registers empty node-less states for the OBJ and the SOP category that log onEnter, and tries to enter
each from a viewer whose pwd matches (and piece_state's real template), with the default and the Enter generate mode.
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
    res = {"log": []}
    entered = []

    def log(*a):
        res["log"].append(" ".join(str(x) for x in a))

    class Empty:
        def __init__(self, state_name, scene_viewer):
            self.name = state_name

        def onEnter(self, kwargs):
            entered.append(self.name)

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
        for name, cat in (("probe_obj_state", hou.objNodeTypeCategory()), ("probe_sop_state", hou.sopNodeTypeCategory())):
            t = hou.ViewerStateTemplate(name, name, cat)
            t.bindFactory(Empty)
            hou.ui.registerViewerState(t)
        sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
        geo = hou.node("/obj").createNode("geo", "g")
        geo.createNode("box")
        sys.path.insert(0, "F:/projects/polyfactory/polyfactory/scripts/python")
        from polyfactory.modelui import piece_state
        if not hou.ui.isRegisteredViewerState(piece_state.STATE):
            hou.ui.registerViewerState(piece_state.template())
        for pwd, name in (("/obj", "probe_obj_state"), ("/obj/g", "probe_sop_state"), ("/obj", piece_state.STATE)):
            for mode in (None, hou.stateGenerateMode.Enter):
                sv.setPwd(hou.node(pwd))
                sv.setCurrentState("objview" if pwd == "/obj" else "select")
                yield 300
                n0 = len(entered)
                try:
                    if mode is None:
                        sv.setCurrentState(name)
                    else:
                        sv.setCurrentState(name, generate=mode)
                    err = None
                except hou.Error as e:
                    err = e.instanceMessage().strip().splitlines()[-1]
                yield 400
                log("pwd", pwd, "state", name, "mode", mode, "-> current", sv.currentState(), "onEnter ran",
                    entered[n0:] != [], "error", err, "pwd category", sv.pwd().childTypeCategory().name())
                if mode is None:
                    from PySide6.QtTest import QTest
                    r = sv.qtScreenGeometry()
                    w = mw.windowHandle()
                    sv.curViewport().draw()
                    yield 300
                    after_draw = list(entered[n0:])
                    QTest.mouseMove(w, w.mapFromGlobal(r.center()))
                    QTest.mouseMove(w, w.mapFromGlobal(r.center()) + QtCore.QPoint(5, 5))
                    yield 500
                    log("   after draw", after_draw != [], "after mouse over viewer", entered[n0:] != [],
                        "current", sv.currentState())
        log("registered categories", [(n, hou.ui.viewerStateInfo(n) is not None) for n in ("probe_obj_state", piece_state.STATE)]
            if hasattr(hou.ui, "viewerStateInfo") else "no viewerStateInfo")

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
