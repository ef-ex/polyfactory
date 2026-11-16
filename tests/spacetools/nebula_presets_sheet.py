"""Dev helper: contact sheet of all presets (ours equirect, tonemapped) next to the Blender EEVEE reference (F:/cache/spacetools/nebula_ref).
hython tests/spacetools/nebula_presets_sheet.py [N=128] -> F:/cache/spacetools/nebula_work/out/presets_sheet.png"""
import os, sys
import numpy as np
import hou
from PIL import Image, ImageDraw
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import bake, nebula
for f in ("pf_space_direction", "pf_nebula_generator"):
    hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", f + ".hda"))
n = hou.node("/img").createNode("copnet", "t").createNode("pf_nebula_generator")
N = int(sys.argv[1]) if len(sys.argv) > 1 else 128
n.parm("res").set(N); n.parm("samples").set(2)
W, H = 4 * N, 2 * N
tiles = []
for name in nebula.preset_names():
    nebula.apply_preset(n, name)
    a = bake.layer_array(n, 0)[..., :3]
    x = a / (1 + a)
    img = Image.fromarray((np.clip(x, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8))
    ref = Image.open("F:/cache/spacetools/nebula_ref/%s.png" % name).convert("RGB").resize((W * 9 // 8, H * 9 // 8 * 1))
    ref = ref.resize((W, H))
    t = Image.new("RGB", (W * 2, H)); t.paste(img, (0, 0)); t.paste(ref, (W, 0))
    ImageDraw.Draw(t).text((4, 4), name, fill=(255, 255, 255))
    tiles.append(t)
cols = 2
rows = (len(tiles) + cols - 1) // cols
sheet = Image.new("RGB", (W * 2 * cols, H * rows))
for i, t in enumerate(tiles):
    sheet.paste(t, ((i % cols) * W * 2, (i // cols) * H))
out = "F:/cache/spacetools/nebula_work/out/presets_sheet.png"
sheet.save(out); print(out, sheet.size)
