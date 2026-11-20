"""The Preset menu callback of pf_nebula_generator (the real script from the HDA) must work for every menu item. hython tests/spacetools/check_nebula_preset_menu.py"""
import os, sys, hou
R = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, R + "/polyfactory/scripts/python")
hou.hda.installFile(R + "/polyfactory/otls/pf_nebula_generator.hda")
n = hou.node("/img").createNode("copnet", "t").createNode("pf_nebula_generator", "n")
p = n.parm("preset")
for i, name in enumerate(p.parmTemplate().menuItems()):
    p.set(i)
    exec(p.parmTemplate().scriptCallback(), {"kwargs": {"node": n, "parm": p}})
print("preset menu OK:", len(p.parmTemplate().menuItems()), "items")
