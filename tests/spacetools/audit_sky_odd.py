"""Audit (hython): odd parm values, NaN/inf, timing, TAB menu/help/defaults for pf_space_direction, pf_spacescape, pf_nebula_generator."""
import os, sys, time, numpy as np, hou
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spacescape_common as C
from polyfactory.spacetools import bake, nebula
R = C.ROOT
for f in ("pf_space_direction", "pf_spacescape", "pf_nebula_generator"): hou.hda.installFile(R + "/polyfactory/otls/%s.hda" % f)
cn = hou.node("/img").createNode("copnet")
def stat(tag, n, **kw):
    t = time.time()
    try:
        a = bake.layer_array(n, 0); 
        print(tag, kw, a.shape, "finite" if np.isfinite(a).all() else "NONFINITE %d" % (~np.isfinite(a)).sum(), "max %.3g" % np.nanmax(a), "%.2fs" % (time.time() - t), n.errors() or "", n.warnings() or "")
    except Exception as e: print(tag, kw, "EXC", str(e)[:100], n.errors())
for t in ("pf_space_direction", "pf_spacescape", "pf_nebula_generator"):
    d = hou.nodeType(hou.copNodeTypeCategory(), t).definition()
    print(t, "help:", bool(d.embeddedHelp()) if False else len(d.sections().get("DialogScript", d.sections().get("TypePropertiesOptions")).contents()) > 0)
    print("  tab:", [ (k, v.contents()[:200]) for k, v in d.sections().items() if "Tools" in k or "shelf" in k.lower()][:1] or "no tool section", "| tabmenu:", d.nodeType().parmTemplateGroup().entries() and "" )
    print("  tabs/ icon/ comment:", d.icon(), "|", d.comment()[:60], "| help url/sections:", [k for k in d.sections() if "elp" in k or "tab" in k.lower()])
# spacescape odd
n = cn.createNode("pf_spacescape"); M = C.M
M.apply_preset(n, "Purple Nebula"); n.parm("res").set(16); stat("ss res16", n)
n.parm("res").set(16); n.parm("layers").set(0); stat("ss 0 layers", n)
M.apply_preset(n, "Purple Nebula")
for i in range(1, 9): n.parm("enable%d" % i).set(0)
stat("ss all off", n)
for i in range(1, 9): n.parm("enable%d" % i).set(1)
for k, v in dict(scale=0.0, octaves=0, octaves_=1, lacunarity=0.0, gain=0.0, power=0.0, shelf=1.0, hdrmult=1e30, count=0, size=0.0).items():
    if n.parm(k + "1") is None: continue
    old = n.parm(k + "1").eval(); n.parm(k + "1").set(v); stat("ss %s=%s" % (k, v), n); n.parm(k + "1").set(old)
for seed in (-1, 2**31 - 1, 10**9):
    n.parm("seed1").set(seed); stat("ss seed", n, seed=seed)
n.parm("seed1").set(0)
n.parm("layers").set(40); stat("ss layers=40 (cap 12)", n)
M.apply_preset(n, "Purple Nebula"); 
n.parm("res").set(1); stat("ss res=1", n); n.parm("res").set(16)
n.parm("res").set(2048); t = time.time(); n.parm("layout").set(0); stat("ss 4k-face equirect 8192x4096 (cook+readback)", n)
n.parm("res").set(1024); stat("ss 1k face (4096x2048)", n); n.parm("res").set(256); stat("ss equirect 1024x512 interactive", n)
# nebula odd
m = cn.createNode("pf_nebula_generator"); nebula.apply_preset(m, "default"); m.parm("res").set(256)
for k, v in dict(steps=0, steps_=1, octaves=0, octaves2=1, samples=0, falloff_size=0.0, volume_unit=0.0, main_mult=1e9, gas_mult=1e9, exposure=0.0, exposure_=1, star_count=0, star_count2=10**8, large_count=0, large_count2=100, seed=-5, seed2=1e7, shadow_steps=0, light_strength=0.0, sun_strength=0.0).items():
    kk = k.rstrip("_2") if k[-1] in "_2" and not k.endswith("steps") else k
    if m.parm(kk) is None: print("nb no parm", kk); continue
    old = m.parm(kk).eval(); m.parm(kk).set(v); stat("nb %s=%s" % (kk, v), m); m.parm(kk).set(old)
m.parm("res").set(16); stat("nb res16", m); m.parm("res").set(1); stat("nb res=1", m)
m.parm("res").set(1024); stat("nb 1k face equirect 4096x2048", m); m.parm("res").set(2048); stat("nb 8192x4096", m)
m.parm("res").set(128); stat("nb equirect 512x256", m)
m.parm("res").set(256); stat("nb 1024x512 (interactive speed)", m)
n2 = cn.createNode("pf_space_direction")
for r in (16, 1, 8192): 
    n2.parm("res").set(r)
    stat("sd res=%d" % r, n2)
