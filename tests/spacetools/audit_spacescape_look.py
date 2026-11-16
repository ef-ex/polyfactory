"""Audit helper (hython): tonemapped equirect + cross of each pf_spacescape preset -> F:/cache/spacetools/audit_sky/ss_<preset>.png"""
import sys, os, numpy as np
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spacescape_common as C
from PIL import Image
def tm(a): return Image.fromarray((np.clip(a[..., :3]/(1+a[..., :3]), 0, 1)**(1/2.2)*255).astype(np.uint8))
for name in C.M.PRESETS:
    n = C.make_node(name); n.parm("res").set(256)
    out = {}
    for tag, lay in (("eq", 0), ("cross", 1)):
        n.parm("layout").set(lay); a = C.bake.layer_array(n, 0); out[tag] = a
        print(name, tag, a.shape, "mean", a[..., :3].mean().round(4), "max", a.max().round(1), "nan", int((~np.isfinite(a)).sum()))
    e = tm(out["eq"]); c = tm(out["cross"]).resize((1024*3//4*1, 768*3//4*1))
    s = Image.new("RGB", (1024, 512 + 576)); s.paste(e, (0, 0)); s.paste(tm(out["cross"]).resize((768, 576)), (0, 512)); s.save("F:/cache/spacetools/audit_sky/ss_%s.png" % name.replace(" ", "_"))
