"""Draw-only frame time: frame stays fixed (nothing cooks), the viewport camera moves between single-frame
flipbooks. Compares one object per piece against all pieces in one object."""
import glob, random, time, os, traceback
import hou, hdefereval
from hutil.Qt import QtCore
LOG = open("F:/cache/modelui/gui_bench2.log", "a", buffering=1)
files = sorted(glob.glob("F:/3d/kitbashLib/*/*.usd"))
OUT = "F:/cache/modelui/fb2"; os.makedirs(OUT, exist_ok=True)

def pieces(n):
    random.seed(7)
    return [(files[i % len(files)], (random.uniform(-50, 50), random.uniform(0, 20), random.uniform(-50, 50))) for i in range(n)]

def build_objects(n):
    hou.hipFile.clear(suppress_save_prompt=True); obj = hou.node("/obj")
    for i, (f, t) in enumerate(pieces(n)):
        g = obj.createNode("geo", "piece_%d" % i); u = g.createNode("usdimport")
        u.parm("filepath1").set(f); u.parm("input_unpack").set(1); u.parm("unpack_geomtype").set(1)
        g.parmTuple("t").set(t); g.displayNode().geometry()

def build_one(n):
    hou.hipFile.clear(suppress_save_prompt=True); g = hou.node("/obj").createNode("geo", "all")
    m = g.createNode("merge")
    for i, (f, t) in enumerate(pieces(n)):
        u = g.createNode("usdimport"); u.parm("filepath1").set(f); u.parm("input_unpack").set(1); u.parm("unpack_geomtype").set(1)
        x = g.createNode("xform"); x.setFirstInput(u); x.parmTuple("t").set(t); m.setInput(i, x)
    m.setDisplayFlag(True); m.geometry()

def frame_time(sv, tag, calls=20):
    v = sv.curViewport(); v.changeType(hou.geometryViewportType.Perspective)
    s = sv.flipbookSettings().stash(); s.frameRange((1, 1)); s.outputToMPlay(False)
    s.useResolution(True); s.resolution((1280, 720))
    v.frameAll(); ts = []
    for k in range(calls):
        cam = v.defaultCamera(); cam.setRotation(hou.hmath.buildRotate(-20, 9 * k, 0).extractRotationMatrix3())
        s.output(OUT + "/%s_%02d.jpg" % (tag, k))
        t = time.perf_counter(); sv.flipbook(v, s); ts.append(time.perf_counter() - t)
    ts.sort(); return ts[len(ts) // 2]

def run():
    try:
        sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        for label, fn, n in [("empty", build_objects, 0), ("objects", build_objects, 500), ("objects", build_objects, 2000),
                             ("one-object", build_one, 2000)]:
            fn(n); med = frame_time(sv, "%s%d" % (label, n))
            LOG.write("%-10s N=%d  single-frame flipbook median %.1f ms\n" % (label, n, 1000 * med))
    except Exception:
        LOG.write(traceback.format_exc())
    LOG.write("done\n"); LOG.close()
    hdefereval.executeDeferred(lambda: hou.exit(suppress_save_prompt=True))

QtCore.QTimer.singleShot(3000, lambda: (hou.qt.mainWindow().move(-12000, 100), run()))
