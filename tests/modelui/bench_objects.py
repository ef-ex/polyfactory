"""modelUI scale check: one geometry object per kitbash mesh, headless (no viewport draw)."""
import glob, random, sys, time, os, ctypes, ctypes.wintypes as w
import hou

class PMC(ctypes.Structure):
    _fields_ = [("cb", w.DWORD), ("PageFaultCount", w.DWORD), ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t), ("a", ctypes.c_size_t), ("b", ctypes.c_size_t),
                ("c", ctypes.c_size_t), ("d", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t), ("e", ctypes.c_size_t)]
def mem_mb():
    c = PMC(); c.cb = ctypes.sizeof(c)
    k = ctypes.windll.kernel32
    k.GetCurrentProcess.restype = w.HANDLE
    k.K32GetProcessMemoryInfo.argtypes = [w.HANDLE, ctypes.POINTER(PMC), w.DWORD]
    assert k.K32GetProcessMemoryInfo(k.GetCurrentProcess(), ctypes.byref(c), c.cb)
    return c.WorkingSetSize / 2**20

files = sorted(glob.glob("F:/3d/kitbashLib/*/*.usd"))
random.seed(7)
obj = hou.node("/obj")

def build(n):
    t = time.perf_counter()
    nodes = []
    for i in range(n):
        f = files[i % len(files)]
        g = obj.createNode("geo", "piece_%d" % i)
        u = g.createNode("usdimport")
        u.parm("filepath1").set(f)
        u.parm("input_unpack").set(1)
        u.parm("unpack_geomtype").set(1)       # polygons: editable mesh
        g.parmTuple("t").set((random.uniform(-50, 50), random.uniform(0, 20), random.uniform(-50, 50)))
        nodes.append(g)
    t_create = time.perf_counter() - t
    t = time.perf_counter(); pts = 0
    for g in nodes:
        pts += g.displayNode().geometry().intrinsicValue("pointcount")
    t_cook = time.perf_counter() - t
    return nodes, t_create, t_cook, pts

for n in [int(a) for a in sys.argv[1:]] or [100, 500, 2000]:
    hou.hipFile.clear(suppress_save_prompt=True)
    m0 = mem_mb()
    nodes, tc, tk, pts = build(n)
    t = time.perf_counter(); names = [c.name() for c in obj.children()]; t_list = time.perf_counter() - t
    t = time.perf_counter(); bb = [g.displayNode().geometry().boundingBox() for g in nodes]; t_bbox = time.perf_counter() - t
    t = time.perf_counter(); cp = hou.copyNodesTo([nodes[n // 2]], obj); cp[0].displayNode().geometry(); t_copy = time.perf_counter() - t
    t = time.perf_counter(); nodes[n // 2].setSelected(True, clear_all_selected=True); t_sel = time.perf_counter() - t
    t = time.perf_counter(); cp[0].destroy(); t_del = time.perf_counter() - t
    print("N=%5d create %.2fs (%.2f ms/obj) cook %.2fs  points %d  mem +%.0f MB  list %.1f ms  bbox-all %.0f ms  copy-one %.1f ms  select %.2f ms  delete %.1f ms"
          % (n, tc, 1000 * tc / n, tk, pts, mem_mb() - m0, 1000 * t_list, 1000 * t_bbox, 1000 * t_copy, 1000 * t_sel, 1000 * t_del), flush=True)
