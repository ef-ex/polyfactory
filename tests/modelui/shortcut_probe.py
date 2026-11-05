"""Shortcut-override probe (audit 4, item 5): can a key the modelUI input layer swallows still fire a Houdini hotkey
through Qt's shortcut path (QEvent::ShortcutOverride, type 51)?

    python tests/modelui/shortcut_probe.py        (builds nothing: run keyfeed/build_keyfeed.bat first)

Plain python: launches a throwaway Houdini on this file (own prefs in F:/cache/modelui/probe, only the polyfactory
package, window off screen) and prints the JSON result. Inside Houdini: feeds W through pf_keyfeed.dll, i.e. Qt's
platform entry points (handleShortcutEvent, then the key event if no shortcut took it), once without a gesture
(control: W must switch the viewer to "pose") and once with a gesture owning W. If the owned W still switches the
state, the layer must also handle type 51 for owned keys. What it cannot see: the OS layer below Qt (WM_KEYDOWN,
IME), i.e. a physical key press.
"""
import json
import os
import shutil
import subprocess
import sys

OUT_DIR = "F:/cache/modelui/probe"
DLL = "F:/cache/modelui/keyfeed/pf_keyfeed.dll"


def launch():
    here = os.path.dirname(os.path.abspath(__file__))
    repo = os.path.normpath(os.path.join(here, "..", ".."))
    shutil.rmtree(OUT_DIR, ignore_errors=True)
    pv = OUT_DIR + "/prefs/houdini22.0"
    os.makedirs(pv + "/packages")
    real = os.path.join(os.path.expanduser("~"), "Documents", "houdini22.0")
    for f in os.listdir(real):
        if f.endswith(".pref") and os.path.isfile(os.path.join(real, f)):
            shutil.copy2(os.path.join(real, f), pv)
    with open(pv + "/packages/polyfactory.json", "w") as f:
        json.dump({"env": [{"POLYFACTORY": repo.replace("\\", "/") + "/polyfactory"}], "path": "$POLYFACTORY"}, f)
    env = dict(os.environ)
    env.pop("HOUDINI_PATH", None)
    env.update(HOUDINI_USER_PREF_DIR=OUT_DIR + "/prefs/houdini__HVER__", HOUDINI_PACKAGE_DIR=pv + "/packages")
    exe = "C:/Program Files/Side Effects Software/Houdini 22.0.442/bin/houdini.exe"
    with open(OUT_DIR + "/console.txt", "w") as con:
        p = subprocess.Popen([exe, "-foreground", os.path.abspath(__file__)], env=env, stdout=con, stderr=subprocess.STDOUT)
        try:
            p.wait(timeout=240)
        except subprocess.TimeoutExpired:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)])
            print("TIMEOUT")
            return 1
    try:
        with open(OUT_DIR + "/result.json") as f:
            print(f.read())
    except OSError:
        print("no result; console:", OUT_DIR + "/console.txt")
        return 1
    return 0


def inside():
    import ctypes
    import traceback

    import hdefereval
    import hou
    import shiboken6
    from hutil.Qt import QtCore, QtWidgets

    from polyfactory.modelui import input_layer, switch
    Qt = QtCore.Qt
    res = {}

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
        lib = ctypes.CDLL(DLL)
        lib.pf_feed_key.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        res["install"] = switch.install()
        yield 900
        sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
        r = sv.qtScreenGeometry()
        target = mw.childAt(mw.mapFromGlobal(QtCore.QPoint(r.x() + r.width() // 3, r.y() + r.height() // 3)))
        wptr = shiboken6.getCppPointer(mw.windowHandle())[0]

        def feed(key):
            target.setFocus()
            consumed = lib.pf_feed_key(wptr, 1, key, 0)
            lib.pf_feed_key(wptr, 0, key, 0)
            return consumed
        seen = []

        def own_w(kind, ev, viewer):
            if kind == "press" or (kind == "key" and viewer is not None and ev.key() != Qt.Key_W):
                return False
            seen.append(kind)
            return True
        for label, gesture in (("control", None), ("owned", own_w), ("control_after", None)):
            sv.setCurrentState("objview")
            yield 250
            if gesture:
                input_layer.add_gesture("probe_w", gesture)
            res[label + "_shortcut_consumed"] = feed(Qt.Key_W)
            yield 300
            res[label + "_state"] = sv.currentState()
            input_layer.remove_gesture("probe_w")
        res["gesture_saw"] = seen
        switch.uninstall()

    def pump(gen):
        try:
            QtCore.QTimer.singleShot(next(gen), lambda: pump(gen))
            return
        except StopIteration:
            pass
        except Exception:  # noqa: BLE001
            res["error"] = traceback.format_exc()
        with open(OUT_DIR + "/result.json", "w") as f:
            json.dump(res, f, indent=1)
        hdefereval.executeDeferred(lambda: hou.exit(suppress_save_prompt=True))
    QtCore.QTimer.singleShot(4000, lambda: pump(steps()))


try:
    import hou  # noqa: F401
    inside()
except ImportError:
    if __name__ == "__main__":
        sys.exit(launch())
