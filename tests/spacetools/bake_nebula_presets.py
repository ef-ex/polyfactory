"""Bake presets to EXR (equirect + 6 faces + cross) and print numbers + tonemapped PNG of the equirect and the cross.
hython tests/spacetools/bake_nebula_presets.py <N face size> <preset> [preset...]   -> F:/cache/spacetools/nebula_work/bake/<preset>/"""
import os, sys, time
import numpy as np
import hou
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import bake, nebula
for f in ("pf_space_direction", "pf_nebula_generator"):
    hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", f + ".hda"))
n = hou.node("/img").createNode("copnet", "t").createNode("pf_nebula_generator")
N = int(sys.argv[1])
def tm(a):
    x = a / (1 + a)
    return Image.fromarray((np.clip(x, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))
for name in sys.argv[2:]:
    nebula.apply_preset(n, name)
    n.parm("samples").set(2); n.parm("steps").set(128); n.parm("shadow_steps").set(12)
    out = "F:/cache/spacetools/nebula_work/bake/%s" % name
    t = time.time(); paths = bake.bake_set(n, out, name, N); dt = time.time() - t
    eq = bake.read_exr(paths["equirect"])
    print("%s N=%d bake of 8 images %.1fs  equirect %s min %.3g max %.4g mean %.4f nan/inf %d" % (name, N, dt, eq.shape, eq.min(), eq.max(), eq.mean(), (~np.isfinite(eq)).sum()))
    print("   ", {k: (v if not isinstance(v, float) else round(v, 4)) for k, v in bake.check_set(paths).items()})
    tm(eq[..., :3]).resize((2048, 1024)).save(out + "/equirect.png")
    tm(bake.read_exr(paths["cross"])[..., :3]).resize((2048, 1536)).save(out + "/cross.png")
    # deterministic: second bake of the equirect bit-identical
    n.parm("layout").set(0); n.parm("res").set(N)
    print("    deterministic:", np.array_equal(bake.layer_array(n, 0), eq))
