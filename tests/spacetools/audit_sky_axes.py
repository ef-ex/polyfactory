"""Independent axis audit (hython): bakes pf_space_direction EXRs, reads them back with Houdini's own
file COP (not OpenEXR/sky.py) and compares with formulas written from the specs:
 - OpenGL/Vulkan cube-face table (sc,tc,ma) -> each face pixel's direction;
 - OpenEXR latlong spec (centre = +Z, longitude +pi at left, +X at u=.25) == Godot sky.glsl (atan2(x,-z)/2pi);
 - checks the EXR round trip is not flipped.  hython tests/spacetools/audit_sky_axes.py"""
import os, sys, numpy as np, hou
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import bake
hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", "pf_space_direction.hda"))
cn = hou.node("/img").createNode("copnet")
n = cn.createNode("pf_space_direction")
OUT = "F:/cache/spacetools/audit_sky/axes"
fails = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name, info)
    if not ok: fails.append(name)

def rd(path):   # independent reader: Houdini file COP; buffer is bottom-first -> flip to top-first
    f = cn.createNode("file"); f.parm("filename").set(path); f.parm("addaovs").pressButton(); f.cook(force=True)
    L = f.layer(0); w, h = L.bufferResolution(); c = L.channelCount()
    a = np.frombuffer(L.allBufferElements(), dtype=np.float32).reshape(h, w, c)[::-1].copy(); f.destroy(); return a

# OpenGL spec table 8.18 (major axis, sc, tc, ma); s=(sc/|ma|+1)/2 across, t=(tc/|ma|+1)/2 down the image
def gl_dir(face, s, t):
    sc, tc = 2*s-1, 2*t-1
    # inverse of the table
    d = {0: (1, -tc, -sc), 1: (-1, -tc, sc), 2: (sc, 1, tc), 3: (sc, -1, -tc), 4: (sc, -tc, 1), 5: (-sc, -tc, -1)}[face]
    d = np.array(d, float); return d / np.linalg.norm(d)
def gl_forward(d):   # direction -> (face, s, t) straight from the table, independent of the inverse above
    x, y, z = d; ax = np.abs(d); k = ax.argmax(); ma = ax[k]
    if k == 0: f, sc, tc = (0, -z, -y) if x > 0 else (1, z, -y)
    elif k == 1: f, sc, tc = (2, x, z) if y > 0 else (3, x, -z)
    else: f, sc, tc = (4, x, -y) if z > 0 else (5, -x, -y)
    return f, (sc/ma+1)/2, (tc/ma+1)/2
def exr_latlong_dir(u, v):   # OpenEXR doc: x=min -> lon +pi, x=max -> lon -pi; lat +pi/2 at top; lon 0 lat 0 = +Z, lon pi/2 = +X
    lon = np.pi - 2*np.pi*u; lat = np.pi/2 - np.pi*v
    return np.array([np.cos(lat)*np.sin(lon), np.sin(lat), np.cos(lat)*np.cos(lon)])

N = 32
for conv in (0, 1):
    n.parm("convention").set(conv)
    paths = bake.bake_set(n, OUT, "d%d" % conv, N)
    # faces
    worst = 0
    for fi, nm in enumerate(("px", "nx", "py", "ny", "pz", "nz")):
        a = rd(paths[nm])
        for r, c in [(0, 0), (5, 20), (16, 16), (31, 31), (12, 3)]:
            d = a[r, c]; f2, s, t = gl_forward(d)
            worst = max(worst, abs(f2 - fi) * 9 + abs(s - (c+.5)/N) + abs(t - (r+.5)/N))
    check("conv%d faces vs OpenGL table (read via Houdini file COP)" % conv, worst < 1e-4, "worst=%.1e" % worst)
    e = rd(paths["equirect"]); H, W = e.shape[:2]
    rng = np.random.default_rng(1); err_exr = err_god = 0
    for _ in range(400):
        r, c = rng.integers(0, H), rng.integers(0, W); u, v = (c+.5)/W, (r+.5)/H
        d = e[r, c]
        th = v*np.pi; ph = u*2*np.pi
        god = np.array([np.sin(th)*np.sin(ph), np.cos(th), -np.sin(th)*np.cos(ph)])   # Godot: u = atan2(x,-z)/2pi
        err_god = max(err_god, np.abs(d - god).max()); err_exr = max(err_exr, np.abs(d - exr_latlong_dir(u, v)).max())
    check("conv%d == Godot sky.glsl formula" % conv, err_god < 1e-4, "%.1e" % err_god)
    check("conv%d == OpenEXR/USD latlong spec (Karma dome light; Houdini domelight help)" % conv, err_exr < 1e-4, "%.1e" % err_exr)
print("FAILED: %s" % fails if fails else "ALL PASS"); sys.exit(1 if fails else 0)
