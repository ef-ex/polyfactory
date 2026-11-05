"""modelUI scale check in a GUI Houdini: viewport frame time with N objects, measured with a synchronous flipbook
(an upper bound: it includes writing a small JPEG per frame). Window moved off screen."""
import glob, random, time, os, traceback
import hou, hdefereval
from hutil.Qt import QtCore
LOG = open("F:/cache/modelui/gui_bench.log", "a", buffering=1)
files = sorted(glob.glob("F:/3d/kitbashLib/*/*.usd"))
OUT = "F:/cache/modelui/fb"; os.makedirs(OUT, exist_ok=True)

def build(n):
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj"); random.seed(7)
    for i in range(n):
        g = obj.createNode("geo", "piece_%d" % i)
        u = g.createNode("usdimport"); u.parm("filepath1").set(files[i % len(files)])
        u.parm("input_unpack").set(1); u.parm("unpack_geomtype").set(1)
        g.parmTuple("t").set((random.uniform(-50, 50), random.uniform(0, 20), random.uniform(-50, 50)))
        g.displayNode().geometry()
    pivot = obj.createNode("null", "orbit")
    pivot.parm("ry").setExpression("$F * 7.5")
    cam = obj.createNode("cam", "benchcam"); cam.setFirstInput(pivot)
    cam.parmTuple("t").set((0, 40, 130)); cam.parm("rx").set(-15)
    cam.parm("resx").set(1280); cam.parm("resy").set(720)
    return cam

def flip(sv, tag, frames=48):
    s = sv.flipbookSettings().stash()
    s.frameRange((1, frames)); s.output(OUT + "/%s_$F4.jpg" % tag); s.outputToMPlay(False)
    t = time.perf_counter(); sv.flipbook(sv.curViewport(), s); return (time.perf_counter() - t) / frames

def run():
    try:
        sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        for n in [0, 100, 500, 2000]:
            t = time.perf_counter(); cam = build(n); tb = time.perf_counter() - t
            sv.curViewport().setCamera(cam)
            sec = flip(sv, "n%d" % n)
            LOG.write("N=%d built+cooked %.1fs  flipbook %.1f ms/frame (%.0f fps)\n" % (n, tb, 1000 * sec, 1 / sec))
    except Exception:
        LOG.write(traceback.format_exc())
    LOG.write("done\n"); LOG.close()
    hdefereval.executeDeferred(lambda: hou.exit(suppress_save_prompt=True))

def go():
    hou.qt.mainWindow().move(-12000, 100)
    run()
QtCore.QTimer.singleShot(3000, go)
