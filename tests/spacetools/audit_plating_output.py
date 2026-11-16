"""Independent output audit of pf::plating_generator on all 19 presets x {box, sphere, grid}.
Measures: zero-area prims, duplicate prims, open/non-manifold edges on closed inputs, inverted normals
(closed convex inputs: every prim normal must point away from the centre), pf_ attr ranges, timing.
hython tests/spacetools/audit_plating_output.py [--json out.json]"""
import os, sys, time, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import hou
from lib import fresh, install, cook, fx_grid, fx_sphere, fx_box
from run_plating_checks import mk, run_preset, P, prim_pts

g = fresh()
install("pf_plating_generator")
OUT = {}


def stats(geo, closed_convex):
    Pp = P(geo); pp = prim_pts(geo)
    top = set(p.number() for p in geo.findPrimGroup('pf_plate_top').prims()) if geo.findPrimGroup('pf_plate_top') else set()
    zero = dup = 0; inv = 0; seen = set()
    ctr = np.zeros(3)  # fixtures are centred on the origin
    for pi_, pr in enumerate(pp):
        pts = Pp[pr]
        n = np.zeros(3)
        for i in range(len(pts)):
            n += np.cross(pts[i], pts[(i + 1) % len(pts)])
        a = np.linalg.norm(n) / 2
        if a < 1e-10:
            zero += 1
        k = tuple(sorted(pr))
        if k in seen:
            dup += 1
        seen.add(k)
        if closed_convex and pi_ in top and a > 1e-10 and np.dot(np.array(geo.prim(pi_).normal()), pts.mean(0) - ctr) < -1e-6:
            inv += 1
    key = {}
    for i, p in enumerate(Pp):
        key.setdefault(tuple(np.round(p, 5)), i)
    wid = [key[tuple(np.round(p, 5))] for p in Pp]
    e2 = {}
    for pr in pp:
        w = [wid[i] for i in pr]
        for i in range(len(w)):
            if w[i] == w[(i + 1) % len(w)]:
                continue
            e = tuple(sorted((w[i], w[(i + 1) % len(w)])))
            e2[e] = e2.get(e, 0) + 1
    open_e = sum(1 for v in e2.values() if v == 1); nonman = sum(1 for v in e2.values() if v > 2)
    return dict(prims=len(pp), zero=zero, dup=dup, open=open_e, nonman=nonman, inverted=inv,
                nan=int(np.isnan(Pp).any()))


fx = {"box": (lambda: fx_box(g), True), "sphere": (lambda: fx_sphere(g), True), "grid": (lambda: fx_grid(g, 11, 4.0), False)}
keys = [k for k in mk(g, "pf_plating_generator", fx_grid(g, 3)).parm("preset").parmTemplate().menuItems() if k != "none"]
bad = []
for fname, (mkf, closed) in fx.items():
    for k in keys:
        n = mk(g, "pf_plating_generator", mkf())
        run_preset(n, k)
        t = time.time()
        try:
            geo = cook(n)
        except Exception as e:
            bad.append((fname, k, "cook " + str(e)[:100])); continue
        s = stats(geo, closed); s["t"] = round(time.time() - t, 2)
        ids = np.array(geo.primIntAttribValues("pf_plate_id")); ar = np.array(geo.primFloatAttribValues("pf_plate_area"))
        s["maxid"] = int(ids.max()); s["neg_area"] = int((ar < 0).sum())
        OUT["%s/%s" % (fname, k)] = s
        flag = [x for x in ("zero", "dup", "inverted", "nan", "neg_area") if s[x]]
        if closed and (s["open"] or s["nonman"]):
            flag += ["open%d/nonman%d" % (s["open"], s["nonman"])]
        if flag:
            bad.append((fname, k, flag, s))
for b in bad:
    print("ISSUE", b)
print("cases:", len(OUT), "with issues:", len(bad), "max cook", max(v["t"] for v in OUT.values()))
if "--json" in sys.argv:
    json.dump(OUT, open(sys.argv[sys.argv.index("--json") + 1], "w"), indent=0)
sys.exit(1 if bad else 0)
