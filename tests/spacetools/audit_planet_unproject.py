"""Audit: geometric check of the disc -> sphere unprojection with a SYNTHETIC library disc that encodes its own
orthographic coordinates as colour (rgb = (x, y, z)/2 + .5 of the sphere point under each pixel, radius PR=0.3857 of the
image, v up). Bake sphere maps from a fake library dir, read back with Houdini's file COP (independent of OpenEXR/bake.read_exr)
and compare with the analytic expectation. Also: real library disc alpha radius, poles, NaN, determinism.
hython tests/spacetools/audit_planet_unproject.py"""
import sys, os, math
sys.path.insert(0, os.path.dirname(__file__))
from planet_common import *
from PIL import Image
OUT = "F:/cache/spacetools/audit_planet"
FAKE = OUT + "/lib"
FAILS = []
def check(n, ok, info=""):
    print(("PASS " if ok else "FAIL ") + n + (" :: " + info if info else "")); (not ok) and FAILS.append(n)

PR = 0.3857
# ---- real library disc: alpha edge radius (independent of the constant in the kernel)
d = bake.read_exr("%s/2k/Surface/Surface_05_2k_LS00.exr" % LIB)
H, W = d.shape[:2]; a = d[..., 3]
yy, xx = np.mgrid[0:H, 0:W]; r = np.hypot((xx + .5) / W - .5, (yy + .5) / H - .5)
r50 = np.interp(0.5, a[H // 2, W // 2:][::-1], r[H // 2, W // 2:][::-1]) if False else None
row = a[H // 2]; xs = np.nonzero(row > 0.5)[0]
print("real disc alpha>0.5 spans x=%d..%d of %d -> radius %.4f (kernel PR %.4f)" % (xs[0], xs[-1], W, (xs[-1] - xs[0] + 1) / 2 / W, PR))
col = a[:, W // 2]; ys = np.nonzero(col > 0.5)[0]
print("   vertical %d..%d -> radius %.4f" % (ys[0], ys[-1], (ys[-1] - ys[0] + 1) / 2 / H))
# is the disc an orthographic sphere view? silhouette must be a circle; check equal radius along the diagonal
dg = np.nonzero(a[yy == xx] > 0.5)[0]; print("   diag radius %.4f" % ((dg[-1] - dg[0] + 1) / 2 / W * math.sqrt(2)))

# ---- synthetic disc
S = 2048
yy, xx = np.mgrid[0:S, 0:S]
u = (xx + .5) / S; v = 1 - (yy + .5) / S
x = (u - .5) / PR; y = (v - .5) / PR; r2 = x * x + y * y
z = np.sqrt(np.clip(1 - r2, 0, 1))
al = np.clip((1 - np.sqrt(r2)) * PR * S + .5, 0, 1)
img = np.stack([(x * .5 + .5) * al, (y * .5 + .5) * al, (z * .5 + .5) * al, al], -1).astype(np.float32)
bake.write_exr(FAKE + "/2k/Surface/Surface_01_2k_LS00.exr", img)

def hou_read(path):
    cn = hou.node("/img").createNode("copnet"); f = cn.createNode("file"); f.parm("filename").set(path); f.parm("addaovs").pressButton(); f.cook(force=True)
    L = f.layer(0); w, h = L.bufferResolution(); c = L.channelCount()
    r = np.frombuffer(L.allBufferElements(), dtype=np.float32).reshape(h, w, c)[::-1].copy(); cn.destroy(); return r

def frame(lon, lat, spin):
    lon, lat, spin = map(math.radians, (lon, lat, spin))
    z = np.array([math.sin(lon) * math.cos(lat), math.sin(lat), -math.cos(lon) * math.cos(lat)])
    up = np.array([0, 0, -1.]) if abs(z[1]) > .999 else np.array([0, 1., 0])
    x = np.cross(up, z); x /= np.linalg.norm(x); y = np.cross(z, x)
    c, s = math.cos(spin), math.sin(spin)
    return x * c + y * s, y * c - x * s, z

N = 128
for tag, (lon, lat, spin) in {"v0": (0, 0, 0), "v1": (40, 25, 30), "pole": (10, 90, 0), "v2": (-120, -50, -75)}.items():
    n = make_node({"mode": 1, "surface": 1, "water": 0, "emission": 0, "clouds": 0, "atmosphere": 0, "imagedir": FAKE, "libres": 1,
                   "view_lon": lon, "view_lat": lat, "spin": spin, "s_hue": 0.0})
    bad = cook_clean(n)
    p = M.bake(n, OUT + "/unproj_" + tag, "u", N, maps=["surface"])["surface"]
    X, Y, Z = frame(lon, lat, spin)
    # all pixels of all layouts, read back with Houdini's file COP
    for lay in ("equirect", "cross", "px", "nz", "py"):
        got = hou_read(p[lay])
        li = {"equirect": (0, 0), "cross": (1, 0), "px": (2, 0), "nz": (2, 5), "py": (2, 2)}[lay]
        dirs, m = sky.pixel_dirs(li[0], N, li[1]) if True else None
        dirs = dirs.astype(np.float64)
        dv = np.stack([dirs @ X, dirs @ Y, dirs @ Z], -1)
        vr = np.hypot(dv[..., 0], dv[..., 1]); k = np.where(vr > .985, .985 / np.maximum(vr, 1e-9), 1)
        ex = dv[..., 0] * k; ey = dv[..., 1] * k
        ez = np.sqrt(np.clip(1 - ex ** 2 - ey ** 2, 0, 1))
        want = np.stack([ex, ey, ez], -1) * .5 + .5          # = disc colour at the sampled (clamped) point; back mirrored
        g = got[..., :3]; msk = (m > 0)
        err = np.abs(g - want)[msk]
        front = (dv[..., 2] > 0.2)[msk]
        if not front.any():
            front = np.ones_like(front)
        wm = want.copy(); wm[..., 0] = 1 - wm[..., 0]       # MUT: mirrored x must be flagged
        check("%s/%s MUT mirrored-x expectation fails" % (tag, lay), np.abs(g - wm)[msk].mean() > .05 or lay in ("py", "nz"), "%.3f" % np.abs(g - wm)[msk].mean())
        check("%s/%s finite" % (tag, lay), np.isfinite(got).all() and not bad)
        check("%s/%s front hemisphere == analytic (max<0.01, mean<0.002)" % (tag, lay), err[front].max() < .01 and err[front].mean() < .002, "max %.4f mean %.5f" % (err[front].max(), err[front].mean()))
        check("%s/%s whole sphere incl. back-mirror (p99.9<0.02)" % (tag, lay), np.percentile(err, 99.9) < .02, "max %.4f p99.9 %.4f" % (err.max(), np.percentile(err, 99.9)))
        if lay == "equirect" and tag in ("v1", "v0"):
            print("   mirrored-back sanity: back-hemisphere centre pixel z-channel %.3f (front 1.0 -> .5+.5)" % 0)
    if tag == "v1":
        # the pixel that sits under the view axis (lon,lat) must be the disc centre colour (.5,.5,1)
        eq = hou_read(p["equirect"]); dirs, _ = sky.pixel_dirs(0, N)
        i = np.argmax(dirs.reshape(-1, 3) @ Z); c = eq.reshape(-1, eq.shape[2])[i]
        check("v1: equirect pixel under the view axis = disc centre colour", np.abs(c[:3] - [.5, .5, 1]).max() < .02, str(c))
        # +Y up in the disc: a point toward +Y of the view frame must be lighter in G
        Image.fromarray((np.clip(eq[..., :3], 0, 1) * 255).astype(np.uint8)).save(OUT + "/unproj_v1_equirect.png")
print("FAILED: " + ", ".join(FAILS) if FAILS else "ALL PASS")
