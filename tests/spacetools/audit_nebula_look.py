"""Audit helper (hython): our nebula seen through the sample .blend camera next to the EEVEE reference PNG, for several presets.
hython tests/spacetools/audit_nebula_look.py [preset ...] -> F:/cache/spacetools/audit_sky/look_<preset>.png (ours | reference), plus mean colour stats."""
import os, sys, numpy as np, hou
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import bake, nebula, sky
for f in ("pf_space_direction", "pf_nebula_generator"):
    hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", f + ".hda"))
n = hou.node("/img").createNode("copnet", "t").createNode("pf_nebula_generator")
names = sys.argv[1:] or ["default", "blue_sulaco", "red_lobster", "turquoise_sunrise", "purple_haze", "green_nemesis"]
rx, ry, rz = 1.6593619585037231, 1.6364525663448148e-06, -7.146590232849121
def R(x, y, z):
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    return np.array([[cz,-sz,0],[sz,cz,0],[0,0,1]]) @ np.array([[cy,0,sy],[0,1,0],[-sy,0,cy]]) @ np.array([[1,0,0],[0,cx,-sx],[0,sx,cx]])
w, h = 960, 540
u = (np.arange(w)+.5)/w*2-1; v = 1-(np.arange(h)+.5)/h*2
U, V = np.meshgrid(u, v*h/w)
d = np.stack([U, V, -np.ones_like(U)], -1) @ R(rx, ry, rz).T
d = (d/np.linalg.norm(d, axis=-1, keepdims=True)).astype(np.float32)
def tm(a): return (np.clip(a/(1+a), 0, 1)**(1/2.2)*255).astype(np.uint8)
for name in names:
    nebula.apply_preset(n, name); n.parm("res").set(int(os.environ.get("AUDIT_N", 256))); n.parm("samples").set(2)
    eq = bake.layer_array(n, 0)[..., :3]
    ours = sky.sample_equirect(eq, d, 0)
    ref = Image.open("F:/cache/spacetools/nebula_ref/%s.png" % name).convert("RGB").resize((w, h))
    sheet = Image.new("RGB", (2*w, h)); sheet.paste(Image.fromarray(tm(ours)), (0, 0)); sheet.paste(ref, (w, 0))
    sheet.resize((w, h//2)).save("F:/cache/spacetools/audit_sky/look_%s.png" % name) if False else sheet.save("F:/cache/spacetools/audit_sky/look_%s.png" % name)
    r = np.asarray(ref, float)/255
    o = tm(ours)/255.0
    print(name, "ours mean rgb", np.round(o.reshape(-1,3).mean(0),3), "ref mean rgb", np.round(r.reshape(-1,3).mean(0),3))
