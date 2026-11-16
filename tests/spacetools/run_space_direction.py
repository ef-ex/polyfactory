"""pf_space_direction check (hython): kernel vs independent numpy reference, bake, seams.

    hython tests/spacetools/run_space_direction.py [--mutate]
Exits non-zero on any failure. Blind spots: checks the layout maths, not that Houdini's/Godot's
viewer orients the equirect the same way (the convention menu is documented, not viewer-verified for Houdini).
"""
import os, sys, tempfile
import numpy as np
import hou

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "polyfactory", "scripts", "python"))
from polyfactory.spacetools import sky, bake

hou.hda.installFile(os.path.join(ROOT, "polyfactory", "otls", "pf_space_direction.hda"))
cn = hou.node("/img").createNode("copnet", "t") if hou.node("/img") else hou.node("/").createNode("img", "img").createNode("copnet", "t")
n = cn.createNode("pf_space_direction")
fails = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name, info)
    if not ok:
        fails.append(name)


N = 64
for conv in (0, 1):
    n.parm("convention").set(conv)
    for layout, face in [(0, 0), (1, 0)] + [(2, f) for f in range(6)]:
        n.parm("layout").set(layout); n.parm("face").set(face); n.parm("res").set(N)
        d = bake.layer_array(n, 0)
        m = bake.layer_array(n, 1)[..., 0]
        rd, rm = sky.pixel_dirs(layout, N, face, conv)
        err = np.abs(d - rd).max()
        check("dir layout=%d face=%d conv=%d" % (layout, face, conv), err < 2e-6 and (m == rm).all(), "maxerr=%.2e" % err)
        ln = np.linalg.norm(d, axis=-1)
        check("unit/zero length l=%d f=%d" % (layout, face), np.allclose(ln[rm > 0], 1, atol=1e-5) and (ln[rm == 0] == 0).all())

n.parm("convention").set(0)
d = bake.layer_array(n, 0)  # last: face 5 -Z
# bake -> read -> seams of the direction layer itself
tmp = os.path.join(os.environ.get("TEMP", "F:/cache/spacetools/nebula_work"), "pfsd_test")
paths = bake.bake_set(n, tmp, "dir", 64)
r = bake.check_set(paths)
print(r)
check("finite", r["finite"])
check("equirect==faces (dir, mean<2e-3, p999<2e-2)", r["equirect_vs_faces_mean_p999"][0] < 2e-3 and r["equirect_vs_faces_mean_p999"][1] < 2e-2)
check("edges continuous (ratio<2)", r["edge_ratio_max"] < 2.0, "max=%.2f" % r["edge_ratio_max"])
check("cross==faces exact", r["cross_vs_faces_maxdiff"] == 0.0)
check("res parm restored", n.parm("res").eval() == N)
# direction semantics: godot centre looks +Z, houdini centre looks -Z
n.parm("layout").set(0); n.parm("res").set(16)
for conv, cz in ((0, -1), (1, 1)):
    n.parm("convention").set(conv)
    a = bake.layer_array(n, 0)
    c = a[16, 32]  # near centre (row below equator)
    check("equirect centre conv=%d z sign" % conv, np.sign(c[2]) == cz and abs(c[2]) > 0.9)
print("FAILED: %s" % fails if fails else "ALL PASS")
sys.exit(1 if fails else 0)
