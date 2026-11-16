"""Dev helper: hython tests/spacetools/nebula_look.py <preset> <res N> [steps] [layout] -> PNGs of tonemapped equirect under F:/cache/spacetools/nebula_work/out"""
import os, sys, time
import numpy as np
import hou
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import bake, nebula
for f in ("pf_space_direction", "pf_nebula_generator"):
    hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", f + ".hda"))
cn = hou.node("/img").createNode("copnet", "t")
n = cn.createNode("pf_nebula_generator")
preset = sys.argv[1] if len(sys.argv) > 1 else "default"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 256
if len(sys.argv) > 3: n.parm("steps").set(int(sys.argv[3]))
nebula.apply_preset(n, preset)
n.parm("res").set(N)
if os.environ.get("NOSTARS"):
    for k in ("star_count", "large_count"): n.parm(k).set(0)
    n.parm("bg_stars").set(0)
if os.environ.get("ONLY") == "main": n.parm("sun_strength").set(0)
if os.environ.get("ONLY") == "point": n.parm("light_strength").set(0)
for kv in filter(None, os.environ.get("PARMS", "").split(",")):
    k, v = kv.split("="); n.parm(k).set(float(v))
if len(sys.argv) > 4: n.parm("layout").set(int(sys.argv[4]))
t = time.time(); a = bake.layer_array(n, 0); dt = time.time() - t
print("cook+read %.2fs shape %s min %.4g max %.4g mean %.4g nan %d" % (dt, a.shape, a.min(), a.max(), a.mean(), np.isnan(a).sum()))
def tonemap(x, k=1.0):
    x = x * k
    x = x / (1 + x)            # simple Reinhard-ish, then gamma
    return (np.clip(x, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)
out = "F:/cache/spacetools/nebula_work/out/%s_%d%s.png" % (preset, N, os.environ.get("TAG", ""))
Image.fromarray(tonemap(a[..., :3])).save(out); print(out)
if os.environ.get("SAVE_EXR"): bake.write_exr(os.environ["SAVE_EXR"], a)
