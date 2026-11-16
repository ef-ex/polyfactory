"""pf_custom_planet checks. Run:  hython tests/spacetools/run_planet_checks.py   (exit 1 on any failure).

A  Billboard vs a real Blender render of the addon's own shader (Library.blend), 3 configs: mean|diff| relative to the
   mean, alpha mean, plus mutations (a changed parm must exceed the tolerance -> the check can fail).
B  Sphere maps, 3 planets (library disc, procedural terran, gas giant): 7 maps x (6 faces + cross + equirect) baked via
   the HDA's bake(): finite, ranges, cross == faces, cube-edge continuity, equirect vs faces, bit-identical re-bake,
   seed changes the planet, library orientation oracle (disc pixels vs the baked equirect, independent numpy maths).
C  Missing library -> procedural fallback cooks clean and is not black.
Cannot see: whether it is beautiful (look at the PNGs), GPU-vs-CPU OpenCL differences, the GUI panel, the Blender
view transform (compared in linear), library layers other than the ones in the configs (colour ramp is not compared to Blender).
"""
import json
import math
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(__file__))
from planet_common import *   # noqa
from PIL import Image

FAILS = []
M_PR = 0.3857


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (" :: " + info if info else ""))
    if not ok:
        FAILS.append(name)


# ---- A: Blender reference ----------------------------------------------------------------------------
LIBBLEND = "F:/cache/spacetools/planet_addon/CustomPlanetAddon/Library.blend"
CONFIGS = {
    "B_default": ({"surface": 5, "clouds": 1, "atm": 1, "ls": 3, "res": "2k"}, {}),
    "G_water_emis": ({"surface": 24, "water": 3, "water_blend": 1, "water_color": [0.02, 0.1, 0.3, 1], "emission": 3, "emit": 1.5,
                      "emit_rot": 0.3, "water_rot": 0.2, "shadow_vis": 0.4, "ls": 1, "clouds": 4, "atm": 2, "res": "2k"},
                     {"surface": 24, "water": 4, "w_blend": 1, "w_colorr": 0.02, "w_colorg": 0.1, "w_colorb": 0.3, "emission": 4,
                      "e_strength": 1.5, "e_rot": math.degrees(0.3), "w_rot": math.degrees(0.2), "e_shadowvis": 0.4,
                      "lightsetup": 2, "clouds": 5, "atmosphere": 3}),
    "H_grade": ({"surface": 28, "hue": 0.6, "sat": 1.4, "val": 1.2, "contrast": 1.0, "tint": [1, 0.8, 0.6, 1], "rot": 0.5,
                 "shadow_bright": 0.3, "ls": 2, "clouds": 0, "atm": 3, "atm_color": [1, 0.2, 0.1, 1], "atm_center": 0.3,
                 "white_rim": 2, "res": "2k"},
                {"surface": 28, "s_hue": 0.1, "s_sat": 1.4, "s_val": 1.2, "s_contrast": 1.0, "tintr": 1, "tintg": 0.8, "tintb": 0.6,
                 "s_rot": math.degrees(0.5), "shadow_bright": 0.3, "lightsetup": 3, "clouds": 0, "atmosphere": 4,
                 "a_colorr": 1, "a_colorg": 0.2, "a_colorb": 0.1, "a_center": 0.3, "a_wrim": 2}),
}


def blender_ref(tag, cfg):
    out = "%s/ref/%s.exr" % (SCRATCH, tag)
    if not os.path.isfile(out):
        os.makedirs(os.path.dirname(out), exist_ok=True)
        subprocess.run([BLENDER, "-b", LIBBLEND, "--python", os.path.join(os.path.dirname(__file__), "planet_blender_ref.py"),
                        "--", json.dumps(cfg), out], capture_output=True, check=True)
    return bake.read_exr(out)


def blocks(a, k=8):
    h, w = a.shape[:2]
    return a[:h // k * k, :w // k * k, :3].reshape(h // k, k, w // k, k, 3).mean((1, 3))


def reldiff(a, ref):
    """8x8-block mean |diff| / mean: thin 1-2 px lines (emission, rivers) differ by sub-pixel resampling between Blender's
    mapping and ours; block means compare energy and placement without that."""
    return float(np.abs(blocks(a) - blocks(ref)).mean() / blocks(ref).mean())


def part_a():
    if not (os.path.isfile(BLENDER) and os.path.isdir(LIB)):
        print("SKIP part A (Blender or library not installed)")
        return
    for tag, (bcfg, hcfg) in CONFIGS.items():
        ref = blender_ref(tag, bcfg)
        n = make_node(dict(hcfg, mode=0, libres=1))
        bad = cook_clean(n)
        check(tag + ": cooks without errors/warnings", not bad, str(bad)[:200])
        a = layer(n, 0)
        rel = reldiff(a, ref)
        check(tag + ": 8x8-block mean|diff| / mean < 0.05 vs Blender", rel < 0.05, "%.4f" % rel)
        check(tag + ": alpha mean equal (|d| < 0.005)", abs(float(a[..., 3].mean() - ref[..., 3].mean())) < 0.005,
              "%.4f vs %.4f" % (a[..., 3].mean(), ref[..., 3].mean()))
        m = make_node(dict(hcfg, mode=0, libres=1, **({"e_strength": 0.4} if "e_strength" in hcfg else {"s_hue": hcfg.get("s_hue", 0) + 0.2})))
        relm = reldiff(layer(m, 0), ref)
        check("MUT " + tag + ": hue shifted 0.2 (or emission strength cut) is clearly worse", relm > 2 * rel and relm > 0.05, "%.4f vs %.4f" % (relm, rel))
        Image.fromarray(np.concatenate([tonemap(ref), tonemap(a)], 1)).resize((1024, 512)).save("%s/ref/%s_side.png" % (SCRATCH, tag))


# ---- B: sphere maps -----------------------------------------------------------------------------------
N = 128
SPH = {"lib5": {"mode": 1},
       "terran": {"mode": 1, "surface": 0, "water": 1, "emission": 1, "clouds": 1},
       "gas": {"mode": 1, "surface": 0, "ptype": 4, "water": 0, "emission": 0, "clouds": 0}}
DENSE = ("surface", "height", "normal")


def bake_cfg(name, cfg, tag=None):
    n = make_node(cfg)
    bad = cook_clean(n)
    check(name + ": cooks without errors/warnings", not bad, str(bad)[:200])
    paths = M.bake(n, SCRATCH + "/checks/" + (tag or name), name, N)
    return n, paths


def part_b():
    os.makedirs(SCRATCH + "/checks", exist_ok=True)
    baked = {}
    for name, cfg in SPH.items():
        n, paths = bake_cfg(name, cfg)
        baked[name] = paths
        for m, p in paths.items():
            d = {k: bake.read_exr(v) for k, v in p.items()}
            check("%s/%s: 8 files, sizes" % (name, m), len(p) == 8 and d["equirect"].shape[:2] == (2 * N, 4 * N)
                  and d["cross"].shape[:2] == (3 * N, 4 * N) and d["px"].shape[:2] == (N, N))
            check("%s/%s: finite and >= 0" % (name, m), all(np.isfinite(v).all() and v.min() >= -1e-6 for v in d.values()),
                  "min %.3f" % min(v.min() for v in d.values()))
            c = bake.check_set(p)
            check("%s/%s: cross == faces" % (name, m), c["cross_vs_faces_maxdiff"] < 1e-5)
            if m in DENSE and d["equirect"].std() > 1e-3:
                check("%s/%s: cube edge ratio max < 2.5" % (name, m), c["edge_ratio_max"] < 2.5,
                      "max %.2f med %.2f" % (c["edge_ratio_max"], c["edge_ratio_median"]))
                fm = float(np.mean([d[k][..., :3].mean() for k in sky.FACE_NAMES]))
                rel = c["equirect_vs_faces_mean_p999"][0] / fm
                check("%s/%s: equirect vs faces / mean < 0.25" % (name, m), rel < 0.25, "%.3f" % rel)
        sf = bake.read_exr(paths["surface"]["equirect"])
        check(name + ": surface plausible (0.005 < mean < 1.5, std > 0.01)", 0.005 < sf[..., :3].mean() < 1.5 and sf.std() > 0.01,
              "mean %.3f std %.3f" % (sf[..., :3].mean(), sf.std()))
        ht = bake.read_exr(paths["height"]["equirect"])
        nm = bake.read_exr(paths["normal"]["equirect"])
        check(name + ": height <= ~1.6, normal in 0..1", ht.max() < 1.6 and nm.min() >= 0 and nm.max() <= 1.0 + 1e-5)
        nv = nm[..., :3] * 2 - 1
        check(name + ": normal map is unit length (mean |n| 0.9..1.1)", 0.9 < float(np.linalg.norm(nv, axis=-1).mean()) < 1.1)
        eq = bake.read_exr(paths["beauty"]["equirect"])
        Image.fromarray(tonemap(eq)).save("%s/checks/%s_equirect.png" % (SCRATCH, name))
        Image.fromarray(tonemap(sphere_view(eq, (0, 0, -1)))).save("%s/checks/%s_sphere.png" % (SCRATCH, name))

    _, p2 = bake_cfg("terran", SPH["terran"], "terran_b")
    same = all(np.array_equal(bake.read_exr(p2["surface"][k]), bake.read_exr(baked["terran"]["surface"][k])) for k in p2["surface"])
    check("same parms -> bit-identical bake", same)
    _, p3 = bake_cfg("terran", dict(SPH["terran"], seed=7), "terran_seed")
    a = bake.read_exr(baked["terran"]["surface"]["equirect"])
    b = bake.read_exr(p3["surface"]["equirect"])
    d = float(np.abs(a - b).mean() / a.mean())
    check("other seed -> different planet (rel diff > 0.05)", d > 0.05, "%.3f" % d)
    _, p4 = bake_cfg("terran", dict(SPH["terran"], ptype=3), "terran_lava")
    check("MUT planet type changes the surface", float(np.abs(bake.read_exr(p4["surface"]["equirect"]) - a).mean() / a.mean()) > 0.2)

    # library orientation oracle: baked equirect at front-hemisphere directions == the disc image at the unprojected uv
    res = "2k"
    disc = bake.read_exr("%s/%s/Surface/Surface_05_%s_LS00.exr" % (LIB, res, res))
    eq = bake.read_exr(baked["lib5"]["surface"]["equirect"])
    rng = np.random.default_rng(3)
    d = rng.normal(size=(4000, 3))
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    d = d[(-d[:, 2] > 0.35)]                              # facing the view axis V = -Z (lon 0, lat 0)
    X = np.array([-1.0, 0, 0])                            # viewer at -Z looking at +Z, up +Y: right = forward x up = -X
    Y = np.array([0, 1.0, 0])
    uv = 0.5 + M_PR * np.stack([d @ X, d @ Y], 1)
    H, W = disc.shape[:2]
    want = sky._bilinear(disc, uv[:, 0] * W, (1 - uv[:, 1]) * H)[..., :3]
    got = sky.sample_equirect(eq, d)[..., :3]
    rel = float(np.abs(want - got).mean() / want.mean())
    check("library orientation: baked front hemisphere == disc pixels (rel < 0.12; mirrored is 0.25)", rel < 0.12, "%.4f" % rel)
    c, s = math.cos(.35), math.sin(.35)
    for tag, g in (("mirrored x", sky.sample_equirect(eq, d * [-1, 1, 1])),
                   ("rolled 20 deg", sky.sample_equirect(eq, d @ np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])))):
        relm = float(np.abs(want - g[..., :3]).mean() / want.mean())
        check("MUT orientation oracle flags " + tag, relm > 2.5 * rel and relm > 0.15, "%.3f vs %.3f" % (relm, rel))


# ---- C: missing library ---------------------------------------------------------------------------------------
def part_c():
    n = make_node({"mode": 0, "imagedir": "F:/definitely/not/here"})
    bad = cook_clean(n)
    check("missing library: cooks without errors/warnings", not bad, str(bad)[:200])
    a = layer(n, 0)
    check("missing library: procedural planet, not black (mean > 0.02, finite)", np.isfinite(a).all() and a[..., :3].mean() > 0.02,
          "%.3f" % a[..., :3].mean())
    ok = layer(make_node({"mode": 0}), 0)
    check("MUT library present looks different from the procedural fallback", float(np.abs(a - ok).mean()) > 0.05)


# ---- D: pf::planet_preview ------------------------------------------------------------------------------------
def part_d():
    folder = SCRATCH + "/checks/terran"            # baked by part B
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(ROOT + "/polyfactory/otls/pf_planet_preview.hda")
    n = hou.node("/obj").createNode("geo").createNode("pf::planet_preview")
    n.parm("folder").set(folder)
    n.parm("prefix").set("terran")
    for k, v in dict(use_clouds=0, use_emission=0, ambient=1, atm_strength=0).items():
        n.parm(k).set(v)
    n.cook(force=True)
    bad = [(c.path(), c.errors(), c.warnings()) for c in [n] + list(n.children()) if c.errors() or c.warnings()]
    check("planet_preview: cooks clean", not bad, str(bad)[:200])
    geo = n.geometry()
    P = np.array([list(p.position()) for p in geo.points()])
    Cd = np.array(geo.pointFloatAttribValues("Cd")).reshape(-1, 3)
    d = P / np.linalg.norm(P, axis=1, keepdims=True)
    eq = bake.read_exr(folder + "/terran_surface_equirect.exr")
    want = sky.sample_equirect(eq, d)[..., :3]
    rel = float(np.abs(Cd - want).mean() / want.mean())
    check("planet_preview: Cd == baked equirect at the point direction (rel < 1e-3)", len(P) > 20000 and rel < 1e-3, "%.2e, %d points" % (rel, len(P)))
    H, W = eq.shape[:2]
    for tag, dirn, u in (("+Z", [0, 0, 1], 0.5), ("+X", [1, 0, 0], 0.25)):   # cap of points vs the equirect box around the same spot
        m = d @ np.array(dirn, float) > math.cos(math.radians(4))
        px = eq[int(H * 0.46):int(H * 0.54), int((u - 0.0111) * W):int((u + 0.0111) * W), :3].reshape(-1, 3).mean(0)
        err = float(np.abs(Cd[m].mean(0) - px).max() / px.max())
        check("planet_preview: points around %s show the equirect at u=%.2f (centre +Z, +X at u .25)" % (tag, u), m.sum() > 5 and err < 0.12, "%s vs %s" % (Cd[m].mean(0).round(3), px.round(3)))
    relm = float(np.abs(Cd - sky.sample_equirect(eq, d * [-1, 1, 1])[..., :3]).mean() / want.mean())
    check("MUT planet_preview: mirrored lookup is clearly different", relm > 0.05, "%.3f" % relm)
    for k, v in dict(use_clouds=1, use_emission=1, ambient=0.05, atm_strength=1, height_scale=0.2).items():
        n.parm(k).set(v)
    n.cook(force=True)
    g2 = n.geometry()
    C2 = np.array(g2.pointFloatAttribValues("Cd"))
    r = np.linalg.norm(np.array(g2.pointFloatAttribValues("P")).reshape(-1, 3), axis=1)
    check("planet_preview: lit/cloud/emission/height pass finite, displaced radius varies", np.isfinite(C2).all() and r.std() > 1e-3,
          "radius std %.4f" % r.std())


if __name__ == "__main__":
    part_a()
    part_b()
    part_c()
    part_d()
    print("FAILED: " + ", ".join(FAILS) if FAILS else "ALL PASS")
    sys.exit(1 if FAILS else 0)
