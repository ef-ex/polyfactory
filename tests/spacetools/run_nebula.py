"""pf_nebula_generator checks (hython): finite/HDR sanity, determinism, seed sensitivity, all presets cook, equirect/cube seams,
pole + wrap continuity, and a differential oracle against a Blender Cycles render (skipped if the cached render is missing).

    hython tests/spacetools/run_nebula.py
Exits non-zero on any failure. Blind spots: the oracle only covers the default preset's gas density structure (noise port),
not lighting brightness (documented 2x spread between Cycles/EEVEE) or the star placement (ours, not Blender's).
"""
import os, sys, shutil
import numpy as np
import hou

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import bake, nebula, sky
for f in ("pf_space_direction", "pf_nebula_generator"):
    hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", f + ".hda"))
n = hou.node("/img").createNode("copnet", "t").createNode("pf_nebula_generator")
fails = []
WORK = "F:/cache/spacetools/nebula_work"


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name, info)
    if not ok:
        fails.append(name)


def reset():
    for t in n.parmTuples():
        if t.parmTemplate().type() != hou.parmTemplateType.Ramp and t.name() not in ("preset",):
            t.revertToDefaults()


def render(res=64, **parms):
    reset()
    nebula.apply_preset(n, parms.pop("preset", "default"))
    n.parm("res").set(res)
    for k, v in parms.items():
        n.parm(k).set(v)
    return bake.layer_array(n, 0)


# 1. sanity + determinism + seed sensitivity
a = render(64, samples=2)
b = render(64, samples=2)
check("finite", np.isfinite(a).all() and (a >= 0).all(), "min %.3g max %.3g" % (a.min(), a.max()))
check("HDR range (stars exceed 1, image not black)", a.max() > 5 and 0.001 < a.mean() < 1.0, "mean %.4f" % a.mean())
check("deterministic (bit identical)", np.array_equal(a, b))
c = render(64, samples=2, seed=1)
check("seed changes the image", np.abs(a - c).mean() > 0.2 * a.mean(), "mean|diff| %.4f vs mean %.4f" % (np.abs(a - c).mean(), a.mean()))

# 2. every preset cooks finite and not black (the Blender presets with a dark viewer spot are allowed to be dim)
for name in nebula.preset_names():
    p = render(32, preset=name)
    check("preset %s finite+nonblack" % name, np.isfinite(p).all() and p.max() > 0.5 and p.mean() > 1e-5, "mean %.4f" % p.mean())

# 3. seams: smooth content (no stars, many jitter samples) so layouts can be compared numerically
tmp = os.path.join(WORK, "nebula_test_bake")
shutil.rmtree(tmp, ignore_errors=True)
reset()
nebula.apply_preset(n, "default")
for k, v in dict(star_count=0, large_count=0, bg_stars=0, samples=8, steps=128, octaves=6).items():
    n.parm(k).set(v)
paths = bake.bake_set(n, tmp, "neb", 64)
r = bake.check_set(paths)
equi = bake.read_exr(paths["equirect"])
m = float(equi.mean())
print(r, "mean", m)
check("bake finite", r["finite"])


def ds(x, k=4):   # block mean: removes the per-pixel jitter (it is hashed on ix,iy so differs between layouts by design)
    h, w, c = x.shape
    return x.reshape(h // k, k, w // k, k, c).mean((1, 3))


faces = [bake.read_exr(paths[k]) for k in sky.FACE_NAMES]
d_mean, d_p = sky.equirect_vs_faces(ds(equi), [ds(f) for f in faces])
sw = [faces[1], faces[0]] + faces[2:]                                 # mutation: swap +X/-X
d_bad, _ = sky.equirect_vs_faces(ds(equi), [ds(f) for f in sw])
check("equirect vs faces (4x4 block means): real diff < 0.25 mean and swapped-face mutation >= 2x worse", d_mean < 0.25 * m and d_bad > 2 * d_mean, "%.5f (mutated %.5f) mean %.5f" % (d_mean, d_bad, m))
check("cube edge continuity ratio < 3 (misoriented seam would be >> 3)", r["edge_ratio_max"] < 3.0, "max %.2f median %.2f" % (r["edge_ratio_max"], r["edge_ratio_median"]))
cr = bake.read_exr(paths["cross"])
cf = sky.cross_to_faces(cr)
cdiff = max(np.abs(ds(x) - ds(y)).mean() for x, y in zip(cf, faces))
check("cross == faces (4x4 block means) within 25%", cdiff < 0.25 * m, "%.5f" % cdiff)
check("cross empty corners are black", float(cr[:64, :64].max()) == 0.0)
# wrap + poles of the equirect
col = np.abs(equi[:, 0] - equi[:, -1]).mean()
nb = np.abs(equi[:, 0] - equi[:, 1]).mean() + 1e-9
check("equirect wraps (col0 vs last <= 3x neighbour diff)", col <= 3 * nb + 0.02 * m, "%.5f vs %.5f" % (col, nb))
ps, ms = equi[0].mean(-1).std(), equi[equi.shape[0] // 3].mean(-1).std()
check("pole row nearly constant (std over longitude < 0.5x that of a mid-latitude row)", ps < 0.5 * ms, "%.5f vs %.5f" % (ps, ms))

# 4. differential oracle: structure of the gas density vs a Cycles render of the same .blend (equirect, same camera)
ref = os.path.join(WORK, "out", "blender_gas.exr")
if os.path.exists(ref):
    def blur(x, k=6):
        c = np.cumsum(np.pad(x, ((0, 0), (k, k)), mode="wrap"), 1); x = (c[:, 2 * k:] - c[:, :-2 * k]) / (2 * k)
        c = np.cumsum(np.pad(x, ((k, k), (0, 0)), mode="edge"), 0); return (c[2 * k:] - c[:-2 * k]) / (2 * k)
    def corr(ours, theirs, dx=0):
        return np.corrcoef(blur(ours.mean(-1)).ravel(), np.roll(blur(theirs.mean(-1)), dx, 1).ravel())[0, 1]
    theirs = bake.read_exr(ref)
    reset()
    nebula.apply_preset(n, "default")
    for k, v in dict(star_count=0, large_count=0, bg_stars=0, samples=2, shadow_steps=0, octaves=16, main_mult=0, sun_strength=0).items():
        n.parm(k).set(v)
    n.parm("res").set(256)
    ours = bake.layer_array(n, 0)
    r0, r200 = corr(ours, theirs), corr(ours, theirs, 200)
    check("oracle: gas density structure matches Cycles (r > 0.65, shifted 200px < 0.25)", r0 > 0.65 and r200 < 0.25, "r=%.3f shifted=%.3f" % (r0, r200))
    n.parm("map_locx").set(n.parm("map_locx").eval() + 5.0)           # mutation: the check must be able to fail
    mut = bake.layer_array(n, 0)
    rm = corr(mut, theirs)
    check("oracle can fail (shifted noise location drops r below 0.5)", rm < 0.5, "r=%.3f" % rm)
else:
    print("SKIP oracle (no %s)" % ref)

print("FAILED: %s" % fails if fails else "ALL PASS")
sys.exit(1 if fails else 0)
