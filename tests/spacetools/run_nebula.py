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
FAST = bool(os.environ.get("NEB_FAST"))   # mutation runs of the section-5 checks: skips presets / seams / Cycles oracle / look proxy
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
check("HDR range (stars exceed 1, image not black)", a.max() > 1.5 and 0.001 < a.mean() < 1.0, "mean %.4f" % a.mean())
check("deterministic (bit identical)", np.array_equal(a, b))
c = render(64, samples=2, seed=1)
check("seed changes the image", np.abs(a - c).mean() > 0.2 * a.mean(), "mean|diff| %.4f vs mean %.4f" % (np.abs(a - c).mean(), a.mean()))

if FAST:
    print("NEB_FAST: sections 2-4 and 6 skipped")
if not FAST:
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
    check("cube edge continuity: median ratio < 1.5 and max < 20 (a misoriented seam is >> 10 everywhere)", r["edge_ratio_median"] < 1.5 and r["edge_ratio_max"] < 20.0, "max %.2f median %.2f" % (r["edge_ratio_max"], r["edge_ratio_median"]))
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

    # 4. differential oracle: structure of the gas density vs a Cycles render of the same .blend (equirect, same camera; r = 1.00 since the Empty-scale fix)
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
        n.parm("res").set(256); n.parm("view_dist").set(1.0)
        # Cycles' panorama centre is -Z (camera forward); the Houdini/Karma lat-long centre is +Z: half a turn
        ours = np.roll(bake.layer_array(n, 0), 512, 1)
        r0, r200 = corr(ours, theirs), corr(ours, theirs, 200)
        check("oracle: gas density structure matches Cycles (r > 0.9, shifted 200px < 0.4)", r0 > 0.9 and r200 < 0.4, "r=%.3f shifted=%.3f" % (r0, r200))
        n.parm("map_locx").set(n.parm("map_locx").eval() + 5.0)           # mutation: the check must be able to fail
        mut = np.roll(bake.layer_array(n, 0), 512, 1)
        rm = corr(mut, theirs)
        check("oracle can fail (shifted noise location drops r below 0.5)", rm < 0.5, "r=%.3f" % rm)
    else:
        print("SKIP oracle (no %s)" % ref)


# 5. behaviour checks, one per mutation the independent audit found surviving (tests/spacetools/audit_sky_mutate.py nb_*)
def layer(idx, res=64, **parms):
    reset()
    nebula.apply_preset(n, parms.pop("preset", "default"))
    n.parm("res").set(res)
    for k, v in parms.items():
        n.parm(k).set(v)
    return bake.layer_array(n, idx)


QUIET = dict(star_count=0, large_count=0, bg_stars=0, samples=2)
base = layer(0, 64, **QUIET)
twice = layer(0, 64, exposure=2.0, **QUIET)
check("exposure doubles the image", 1.98 < twice.mean() / base.mean() < 2.02, "%.3f" % (twice.mean() / base.mean()))
al_off = layer(1, 64, main_mult=0, gas_mult=0, **QUIET)
al_on = layer(1, 64, **QUIET)
check("alpha = 1 - transmittance: 0 with no volume, 0.05..0.99 mean with it", al_off.max() < 1e-3 and 0.05 < al_on.mean() < 0.99, "off max %.4f on mean %.3f" % (al_off.max(), al_on.mean()))
dust_only = layer(0, 64, gas_mult=0, **QUIET)
check("dust absorbs and never scatters (no gas -> < 25% of the default image; the constant ramp softens over 1/256 so not 0)", dust_only.mean() < 0.25 * base.mean(), "%.3g vs %.3g" % (dust_only.mean(), base.mean()))
sh0 = layer(0, 64, shadow_steps=0, **QUIET).mean()
sh24 = layer(0, 64, shadow_steps=24, **QUIET).mean()
check("shadow march darkens the sun-lit gas (24 steps < 0.9 x unshadowed)", sh24 < 0.9 * sh0, "%.5f vs %.5f" % (sh24, sh0))
gv = layer(0, 64, val=2.0, **QUIET)
check("global value 2 brightens the gas 1.8..2.6x", 1.8 < gv.mean() / base.mean() < 2.6, "%.2f" % (gv.mean() / base.mean()))
WHITE = dict(light_colorr=1.0, light_colorg=1.0, light_colorb=1.0)   # the preset's sun is orange: it would tint a desaturated gas
gs = layer(0, 64, sat=0.0, **WHITE, **QUIET)
gw = layer(0, 64, **WHITE, **QUIET)
chroma = lambda x: float(np.abs(x[..., 0] - x[..., 1]).mean() + np.abs(x[..., 1] - x[..., 2]).mean()) / float(x.mean())
check("global saturation 0 greys the gas under white light (chroma < 5% of the default's)", chroma(gs) < 0.05 * chroma(gw), "%.4f vs %.4f" % (chroma(gs), chroma(gw)))
NOVOL = dict(main_mult=0, gas_mult=0, large_count=0, star_count=0, samples=1)
bg1 = layer(0, 256, bg_stars=1.0, **NOVOL); bg0 = layer(0, 256, bg_stars=0.0, **NOVOL)
check("background star dust adds stars (>= 50 pixels above 0.01) and is off at 0", int(((bg1 - bg0).max(-1) > 0.01).sum()) >= 50 and bg0.max() == 0.0, "%d px" % int(((bg1 - bg0).max(-1) > 0.01).sum()))
bgm = float((bg1 - bg0).mean())
check("background star dust is faint like the EEVEE world probe (mean 5e-5..1e-3; EEVEE 3.7e-4, the raw node maths would give 1.8e-2)", 5e-5 < bgm < 1e-3, "%.2e" % bgm)

# small stars: total energy against the analytic value. A star of world size s at distance r (volume units) is a soft sprite of
# angular size 0.18 s / (r unit); the sprite carries pi/2.5 * size^2 * strength * colour. Viewer at the centre, no volume, coverage
# mask off (coverage 1.5): N stars uniform in the ball of radius R -> E[1/r^2] = 3 / R^2.
NS, SZ, RS = 20000, 0.25, 1.2
st = layer(0, 128, star_coverage=1.5, star_size_min=SZ, star_size_max=SZ, star_radius=RS, view_dist=0.0, **{**NOVOL, "star_count": NS})
H_, W_ = st.shape[:2]
dom = (np.sin((np.arange(H_) + 0.5) / H_ * np.pi) * (2 * np.pi / W_) * (np.pi / H_))[:, None, None]
meas = (st * dom).sum((0, 1))
ramp = nebula.load()["presets"]["default"]["star_ramp"]
cm = np.interp(0.5, ramp["pos"], np.array(ramp["val"])[:, 0]), np.interp(0.5, ramp["pos"], np.array(ramp["val"])[:, 1]), np.interp(0.5, ramp["pos"], np.array(ramp["val"])[:, 2])
unit = 122.73
exp_e = NS * (np.pi / 2.5) * 19.4 * (0.18 * SZ / unit) ** 2 * 3.0 / RS ** 2 * np.array(cm)
ratio = meas / exp_e
check("small-star energy == analytic (count, strength, size/distance law; each channel within 0.8..1.25)", bool(((ratio > 0.8) & (ratio < 1.25)).all()), "ratio %s" % np.round(ratio, 3))
pk = st.max(-1) > 0.05
share = st[pk][:, 0] / st[pk].sum(-1)
check("star colour comes from the ramp per star (R share varies, std > 0.05)", pk.sum() > 200 and share.std() > 0.05, "%d px std %.3f" % (pk.sum(), share.std()))

# 6. look proxy: same camera, same lights, linear radiance vs the Blender EEVEE renders of the sample .blend files (no compositor, Standard view;
#    made by F:/cache/spacetools/nebula_work/render_var.py / render_eevee_exr.py into nebula_work/lin). Tolerances are the measured spread
#    (luminance 0.86-1.35x, per-channel medians 0.8-1.8x) with margin; the pre-fix tool was 5-30x off or the wrong hue.
LIN = os.path.join(WORK, "lin")
LOOK = ["red_lobster", "purple_haze", "blue_sulaco", "green_nemesis"]
if not FAST and all(os.path.exists(os.path.join(LIN, "%s%s.exr" % (k, t))) for k in LOOK for t in ("", "_gas")):
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import nebula_vs_blender as nvb

    def peaks(img, thr):
        l = img.max(-1); m = np.ones_like(l, bool)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dy or dx:
                    m &= l > np.roll(np.roll(l, dy, 0), dx, 1)
        return int((m & (l > thr)).sum())

    for name, row in nvb.run(LOOK, 1024).items():
        so, sr, ours, ref = row["full"]
        _, _, ours_g, ref_g = row["_gas"]
        lr = so["mean"].mean() / sr["mean"].mean()
        check("look %s: mean luminance within 0.65..1.5x of EEVEE" % name, 0.65 < lr < 1.5, "%.2f" % lr)
        mr = so["med"] / sr["med"]
        check("look %s: per-channel median within 0.45..2.2x" % name, bool(((mr > 0.45) & (mr < 2.2)).all()), str(np.round(mr, 2)))
        sh = lambda v: v / v.sum()
        check("look %s: hue (channel shares of the median) within 0.12 of EEVEE" % name, np.abs(sh(so["med"]) - sh(sr["med"])).max() < 0.12, "%s vs %s" % (np.round(sh(so["med"]), 2), np.round(sh(sr["med"]), 2)))
        check("look %s: cloud structure correlates with EEVEE (r > 0.8)" % name, nvb.structure_corr(ours, ref) > 0.8, "r=%.3f" % nvb.structure_corr(ours, ref))
        po, pr = peaks(np.maximum(ours - ours_g, 0), 0.3), peaks(np.maximum(ref - ref_g, 0), 0.3)
        check("look %s: star count (peaks > 0.3) within 0.3..4x of EEVEE when it has >= 50 (and never > 6x: not hundreds of big white stars)" % name, (pr < 50 or 0.3 < po / pr < 4.0) and po < 6 * max(pr, 20), "ours %d ref %d" % (po, pr))
        bo, br = float((ours.max(-1) > 1.0).mean()), float((ref.max(-1) > 1.0).mean())
        check("look %s: bright (>1) pixel fraction <= 4x ref + 0.5%% (no glare blobs)" % name, bo <= 4 * br + 0.005, "ours %.4f ref %.4f" % (bo, br))
else:
    print("SKIP look proxy (no EEVEE renders in %s)" % LIN)

print("FAILED: %s" % fails if fails else "ALL PASS")
sys.exit(1 if fails else 0)
