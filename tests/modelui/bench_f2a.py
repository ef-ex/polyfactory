"""F2a viewport bench: kitbash pieces packed in one container, 0/100/500/2000 pieces from all 605 library files.

    python tests/modelui/bench_f2a.py

Plain python: launches a throwaway off-screen Houdini on this file (shortcut_probe.launch) and prints the result.
Inside: draw-only frame time like gui_bench2.py (frame fixed, the camera orbits, single-frame flipbooks 1280x720,
median of 20; the empty scene's number is flipbook overhead), build + first cook time, and at 2000 pieces the GUI cost
of moving, copying and selecting one piece (edit + recook + viewport redraw). Compare: ideas/modelui.md measurements
(2000 objects +101 ms draw, the same 2000 pieces in one object +9 ms).
"""
import json
import os
import sys

OUT = "F:/cache/modelui/probe/result.json"


def inside():
    import glob
    import random
    import time
    import traceback

    import hdefereval
    import hou
    from hutil.Qt import QtCore, QtWidgets
    sys.path.insert(0, "F:/projects/polyfactory/polyfactory/scripts/python")
    from polyfactory.modelui import containers, pieces_ui, scene
    res = {"log": []}
    files = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))
    fbdir = "F:/cache/modelui/probe/fb"
    os.makedirs(fbdir, exist_ok=True)

    def log(*a):
        res["log"].append(" ".join(str(x) for x in a))

    def build(n):
        hou.hipFile.clear(suppress_save_prompt=True)
        random.seed(7)
        c = containers.create()
        t = time.perf_counter()
        items = []
        for i in range(n):
            m = hou.hmath.buildRotate((0, random.uniform(0, 360), 0)) * hou.hmath.buildTranslate(
                (random.uniform(-50, 50), random.uniform(0, 20), random.uniform(-50, 50)))
            items.append((files[i % len(files)], "p%d" % i, m))
        ids = containers.add_pieces(c, items) if n else []
        t1 = time.perf_counter()
        prims = len(c.displayNode().geometry().prims())
        t2 = time.perf_counter()
        return c, ids, t1 - t, t2 - t1, prims

    def frame_time(sv, tag, calls=20):
        v = sv.curViewport()
        s = sv.flipbookSettings().stash()
        s.frameRange((1, 1))
        s.outputToMPlay(False)
        s.useResolution(True)
        s.resolution((1280, 720))
        v.frameAll()
        ts = []
        for k in range(calls):
            cam = v.defaultCamera()
            cam.setRotation(hou.hmath.buildRotate(-20, 9 * k, 0).extractRotationMatrix3())
            s.output(fbdir + "/%s_%02d.jpg" % (tag, k))
            t = time.perf_counter()
            sv.flipbook(v, s)
            ts.append(time.perf_counter() - t)
        ts.sort()
        return ts[len(ts) // 2]

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
        sv.curViewport().changeType(hou.geometryViewportType.Perspective)
        base = None
        for n in (0, 100, 500, 2000):
            c, ids, t_add, t_cook, prims = build(n)
            yield 500
            med = frame_time(sv, "pieces%d" % n)
            base = med if base is None else base
            log("N=%d pieces: add %.2f s, first cook %.2f s (%d prims), flipbook median %.1f ms (+%.1f ms over empty)"
                % (n, t_add, t_cook, prims, 1000 * med, 1000 * (med - base)))
            res["draw_%d" % n] = 1000 * (med - base)
            yield 200
        vp = sv.curViewport()

        def ms(fn):
            t = time.perf_counter()
            fn()
            len(c.displayNode().geometry().prims())
            vp.draw()
            return 1000 * (time.perf_counter() - t)
        pid = ("piece", c.sessionId(), ids[10])
        pieces_ui.install()
        yield 300
        res["move_one_ms"] = ms(lambda: containers.set_transforms(c, {ids[10]: hou.hmath.buildTranslate((1, 2, 3))}))
        res["copy_one_ms"] = ms(lambda: containers.copy_pieces(c, [ids[11]]))
        res["select_one_ms"] = ms(lambda: (scene.current().select([pid]), pieces_ui._follow_selection()))
        log("2000 pieces in the GUI: move one %.1f ms, copy one %.1f ms, select one (+ handle proxy) %.1f ms"
            % (res["move_one_ms"], res["copy_one_ms"], res["select_one_ms"]))
        pieces_ui.uninstall()

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
