"""hython tests/spacetools/nebula_vs_blender.py [preset ...]  (env NEB_N=1024, NEB_OUT=dir)
Ours (equirect -> the sample camera, 90deg, per-preset camera) vs the linear EEVEE EXR (no compositor, Standard) rendered by
F:/cache/spacetools/nebula_work/render_eevee_exr.py into nebula_work/lin/<preset>[_ns].exr. Prints mean/median colour ratios and
writes <out>/cmp_<preset>.png (ours | EEVEE, both through the same simple tonemap)."""
import os, sys, json, numpy as np, hou
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import bake, nebula, sky
for f in ("pf_space_direction", "pf_nebula_generator"):
    hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", f + ".hda"))
WORK = "F:/cache/spacetools/nebula_work"
OUT = os.environ.get("NEB_OUT", "F:/cache/spacetools/nebula_work/cmp")
os.makedirs(OUT, exist_ok=True)


def R(x, y, z):
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    return np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]) @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]) @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])


def cam_dirs(camrot, w=960, h=540):
    u = (np.arange(w) + .5) / w * 2 - 1
    v = 1 - (np.arange(h) + .5) / h * 2
    U, V = np.meshgrid(u, v * h / w)
    d = np.stack([U, V, -np.ones_like(U)], -1) @ R(*camrot).T
    return (d / np.linalg.norm(d, axis=-1, keepdims=True)).astype(np.float32)


def tm(a, ex=1.0):
    a = a * ex
    return (np.clip(a / (1 + a), 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)


def render_ours(n, name, N, stars=True):
    nebula.apply_preset(n, name)
    n.parm("res").set(N); n.parm("samples").set(2); n.parm("view_dist").set(1.0)   # the sample camera, not the sky default
    for kv in filter(None, os.environ.get("NEB_SET", "").split(",")):     # e.g. NEB_SET=light_strength=0,shadow_steps=16
        k, v = kv.split("="); n.parm(k).set(float(v))
    if not stars:        # "gas" variant: no small / background stars (the large stars stay: they are the lamps)
        n.parm("star_count").set(0); n.parm("bg_stars").set(0)
    cam = json.load(open("%s/presets/%s.json" % (WORK, name)))["scene"]["camrot"]
    eq = bake.layer_array(n, 0)[..., :3]
    return sky.sample_equirect(eq, cam_dirs(cam), 0)


def stats(a):
    f = a.reshape(-1, 3)
    return dict(mean=np.minimum(f, 0.5).mean(0), med=np.median(f, 0))   # mean of values clipped at 0.5: bright star cores do not dominate


def structure_corr(a, b, blur=6):
    """Pearson r of the box-blurred log luminance (structure match, independent of overall gain)."""
    def prep(x):
        l = np.log(np.minimum(x.mean(-1), 1.0) + 1e-3)
        k = np.ones(2 * blur + 1) / (2 * blur + 1)
        l = np.apply_along_axis(lambda r: np.convolve(r, k, "same"), 1, l)
        return np.apply_along_axis(lambda c: np.convolve(c, k, "same"), 0, l)[blur:-blur:3, blur:-blur:3].ravel()
    return float(np.corrcoef(prep(a), prep(b))[0, 1])


def run(names, N=None):
    N = N or int(os.environ.get("NEB_N", 1024))
    n = hou.node("/img").createNode("copnet", "t").createNode("pf_nebula_generator")
    res = {}
    for name in names:
        row = {}
        for tag, stars in (("_gas", False), ("", True)):
            ours = render_ours(n, name, N, stars)
            ref = bake.read_exr("%s/lin/%s%s.exr" % (WORK, name, tag))[..., :3]
            row[tag or "full"] = (stats(ours), stats(ref), ours, ref)
        s = Image.new("RGB", (1920, 540 * 2))
        for j, tag in enumerate(("_gas", "full")):
            s.paste(Image.fromarray(tm(row[tag][2])), (0, 540 * j)); s.paste(Image.fromarray(tm(row[tag][3])), (960, 540 * j))
        s.resize((1200, 675)).save("%s/cmp_%s.png" % (OUT, name))
        res[name] = row
    return res


if __name__ == "__main__":
    names = sys.argv[1:] or ["red_lobster", "purple_haze", "blue_sulaco", "green_nemesis", "turquoise_sunrise"]
    for name, row in run(names).items():
        for tag, (so, sr, _, _) in row.items():
            print("   structure r = %.3f" % structure_corr(row[tag][2], row[tag][3]))
            print("%-18s %-5s ours mean %s ref mean %s | ratio %s | med ours %s ref %s" % (
                name, tag, np.round(so["mean"], 4), np.round(sr["mean"], 4), np.round(so["mean"] / np.maximum(sr["mean"], 1e-9), 2),
                np.round(so["med"], 4), np.round(sr["med"], 4)))
