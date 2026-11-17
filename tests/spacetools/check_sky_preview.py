"""pf::sky_preview vs the COP it shows, and the auto-created preview of nebula / spacescape.
hython tests/spacetools/check_sky_preview.py [--mutate]   (--mutate: flips the sky's x axis in the VEX; must FAIL)
Compares point colour (exposure 0, tonemap off) at 400 vertices with the COP's own equirect pixels sampled in numpy
(independent oracle: sky.sample_equirect). Cannot see: viewport look, GPU shading, HDR display."""
import os, sys, random
import numpy as np
import hou
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, R + "/polyfactory/scripts/python"); sys.path.insert(0, R + "/devScripts")
from polyfactory.spacetools import bake, sky, nebula
MUT = "--mutate" in sys.argv
fails = []


def check(cop, label):
    cop.cook(force=True)
    img = bake.layer_array(cop, 0)[..., :3]
    s = sky.ensure_preview(cop)
    assert s is not None, label + ": ensure_preview made nothing"
    assert sky.ensure_preview(cop).path() == s.path(), label + ": ensure_preview not idempotent"
    s.parm("tonemap").set(0)
    if MUT:
        s.allowEditingOfContents()
        w = s.node("cop_to_color"); w.parm("snippet").set(w.parm("snippet").eval().replace("atan2(pn.x,", "atan2(-pn.x,"))
    g = s.geometry()
    vs = [v for p in g.prims() for v in p.vertices()]
    random.seed(1); vs = random.sample(vs, 400)
    d = np.array([list(v.point().position()) for v in vs]); d /= np.linalg.norm(d, axis=1, keepdims=True)
    want = sky.sample_equirect(img, d, 0)[..., :3]
    got = np.array([list(v.attribValue("Cd")) for v in vs])
    lw, lg = np.log1p(want.mean(1)), np.log1p(got.mean(1))
    r = float(np.corrcoef(lw, lg)[0, 1]); rel = float(np.median(np.abs(got - want).sum(1) / (want.sum(1) + 1e-3)))
    print("%-10s corr(log lum) %.3f  median rel diff %.3f  (cook errors: %s)" % (label, r, rel, s.errors() or "none"))
    if not (r > 0.98 and rel < 0.1 and not s.errors()):
        fails.append(label)


hou.isUIAvailable = lambda: True                  # exercise the GUI-only creation path headless
hou.hipFile.clear(suppress_save_prompt=True)
for h in ("pf_sky_preview", "pf_nebula_generator", "pf_spacescape"):
    hou.hda.installFile(R + "/polyfactory/otls/%s.hda" % h)
cn = hou.node("/img").createNode("copnet", "cn")
n = cn.createNode("pf_nebula_generator", "neb"); n.parm("res").set(32); nebula.apply_preset(n, "blue_sulaco")
check(n, "nebula")
m = cn.createNode("pf_spacescape", "ss"); m.parm("outres1").set(128) if m.parm("outres1") else None
check(m, "spacescape")
print("FAIL: " + ", ".join(fails) if fails else "sky preview OK")
sys.exit(1 if fails else 0)
