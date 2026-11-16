"""Dev helper (hython): the whole sky (equirect) of a few presets with the HDA defaults, tonemapped, one sheet -> F:/cache/spacetools/nebula_work/sky_sheet.png
hython tests/spacetools/nebula_sky_sheet.py [preset ...]   (env NEB_N face size, default 256)"""
import os, sys, numpy as np, hou
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import bake, nebula
for f in ("pf_space_direction", "pf_nebula_generator"):
    hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", f + ".hda"))
n = hou.node("/img").createNode("copnet", "t").createNode("pf_nebula_generator")
names = sys.argv[1:] or ["red_lobster", "purple_haze", "blue_sulaco", "green_nemesis"]
rows = []
for name in names:
    nebula.apply_preset(n, name); n.parm("res").set(int(os.environ.get("NEB_N", 256))); n.parm("samples").set(2)
    a = bake.layer_array(n, 0)[..., :3]
    rows.append((np.clip(a / (1 + a), 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))
    print(name, "mean", a.mean(0).mean(0), "frac dark (<0.002):", float((a.mean(-1) < 0.002).mean()))
sheet = np.concatenate(rows, 0)
Image.fromarray(sheet).resize((sheet.shape[1] * 1000 // sheet.shape[1], sheet.shape[0] * 1000 // sheet.shape[1])).save("F:/cache/spacetools/nebula_work/sky_sheet.png")
