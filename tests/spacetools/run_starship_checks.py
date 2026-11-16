"""`pf::starship_generator` checks against the SHIPPED asset, in a throwaway session.

    hython tests/spacetools/run_starship_checks.py [nseeds]

c1 cooks clean (no error/warning on ANY node inside) for N seeds at defaults
c2 output non-empty, finite, Length along Z is exact, no zero-area prims
c3 deterministic: a second fresh instance gives the same fingerprint
c4 different seeds give different ships
c5 no `_*` attribute in any class, no group at all, exact attribute whitelist + storage
c6 every parm branch exercised, each with the effect it must have:
   panels off -> pf_panel all 0, on -> layers 1..3 present; boosters off -> no pf_part 3;
   flip -> booster on -ve Z; density 0 -> only hull(0)+booster(3); mirror on -> symmetric in X;
   subdiv 0 / variants 1 / panel_subdiv 0 / jiggle 0 / ext_amount 0 / detail 3 / mirror off cook clean.

CANNOT SEE: whether it looks like a starship (look at the renders in
F:/cache/spacetools/starship_work); self-intersections (parts overlap by design);
the Blender original's exact distributions (only mapped, see ideas/spacetools.md);
mirror-seam watertightness (hull+parts are not closed solids by design).
Mutation record: see ideas/spacetools.md "Starship generator" -> Verification.
"""
import hashlib
import math
import os
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__))
HDA = os.path.join(os.path.dirname(os.path.dirname(HERE)), "polyfactory", "otls",
                   "pf_starship_generator.hda").replace("\\", "/")
hou.hda.installFile(HDA)
GEO = hou.node("/obj").createNode("geo")
FAILS = []


def check(ok, msg):
    print(("ok   " if ok else "FAIL ") + msg)
    if not ok:
        FAILS.append(msg)


def cook(**p):
    n = GEO.createNode("pf::starship_generator")
    for k, v in p.items():
        t = n.parmTuple(k)
        t.set(v if isinstance(v, (tuple, list)) else (v,))
    mut = os.environ.get("PF_MUTATE")
    if mut:   # mutation proof: each edit must turn some check red
        n.allowEditingOfContents()
        if mut.startswith("bypass:"):   # audit: PF_MUTATE=bypass:node1,node2
            for nm in mut[7:].split(","):
                n.node(nm).bypass(True)
        elif mut.startswith("snip:"):   # audit: PF_MUTATE=snip:node  (empty the wrangle snippet)
            n.node(mut[5:]).parm("snippet").set("")
        elif mut == "boost_off":
            n.node("boost_sw").parm("input").setExpression("0")
        elif mut == "panels_off":
            n.node("panel_sw").parm("input").setExpression("0")
        elif mut == "mirror_off":
            n.node("ship_mirsw").parm("input").setExpression("0")
        elif mut == "no_cleanup":
            n.node("cleanup").bypass(True)
        elif mut == "no_zero_removal":
            n.node("material").parm("snippet").set('s@pf_material = i@pf_part == 3 ? "booster" : "hull";')
    n.cook(force=True)
    bad = []
    stack = [n]
    while stack:
        c = stack.pop()
        stack += list(c.children())
        if c.errors() or c.warnings():
            bad.append((c.path(), c.errors(), c.warnings()))
    return n, bad


def prim_attr(geo, name):
    return [pr.attribValue(name) for pr in geo.prims()]


def fingerprint(geo):
    h = hashlib.md5()
    h.update(("%d %d" % (len(geo.prims()), len(geo.points()))).encode())
    pts = geo.pointFloatAttribValues("P")
    h.update(("%.4f" % sum(pts[0::3])).encode())
    h.update(("%.4f" % sum(abs(v) for v in pts)).encode())
    return h.hexdigest()


def main():
    nseeds = int(sys.argv[1]) if len(sys.argv) > 1 else 10
    seeds = [313997] + [101 * i + 7 for i in range(1, nseeds)]
    prints = {}
    for s in seeds:
        n, bad = cook(seed=s)
        check(not bad, "c1 seed %d cooks clean %s" % (s, bad[:1]))
        g = n.geometry()
        pts = g.pointFloatAttribValues("P")
        check(len(g.prims()) > 1000 and all(math.isfinite(v) for v in pts), "c2 seed %d non-empty/finite (%d prims)" % (s, len(g.prims())))
        bb = g.boundingBox()
        check(abs(bb.sizevec()[2] - 15.0) < 1e-3, "c2 seed %d Z length 15 (%.4f)" % (s, bb.sizevec()[2]))
        check(max(bb.sizevec()) < 40 and min(bb.sizevec()) > 0.5, "c2 seed %d sane bbox %s" % (s, [round(v, 1) for v in bb.sizevec()]))
        zero = sum(1 for pr in g.prims() if pr.intrinsicValue("measuredarea") < 1e-9)
        check(zero == 0, "c2 seed %d zero-area prims = %d" % (s, zero))
        prints[s] = fingerprint(g)
        if s == seeds[0]:
            n2, _ = cook(seed=s)
            check(fingerprint(n2.geometry()) == prints[s], "c3 deterministic (fresh instance, same seed)")
            parts = set(prim_attr(g, "pf_part"))
            check(parts == {0, 1, 2, 3}, "c2 default has hull/medium/small/booster %s" % parts)
            check(set(prim_attr(g, "pf_panel")) == {0, 1, 2, 3}, "c6 default has all panel layers")
            ba = g.findPrimAttrib
            check(ba("pf_part").dataType() == hou.attribData.Int and ba("pf_panel").dataType() == hou.attribData.Int
                  and ba("pf_material").dataType() == hou.attribData.String, "c5 storage int/int/string")
            names = {cl: sorted(a.name() for a in getattr(g, cl)())
                     for cl in ("pointAttribs", "primAttribs", "vertexAttribs", "globalAttribs")}
            check(names == {"pointAttribs": ["P"], "primAttribs": ["pf_material", "pf_panel", "pf_part"],
                            "vertexAttribs": ["N"], "globalAttribs": []}, "c5 exact attribute whitelist %s" % names)
            check(not g.primGroups() and not g.pointGroups() and not g.edgeGroups(), "c5 no groups leak")
            check(all((m == "booster") == (p == 3) for m, p in zip(prim_attr(g, "pf_material"), prim_attr(g, "pf_part"))),
                  "c5 pf_material agrees with pf_part")
            # mirror on: the point set is symmetric in X
            xs = pts[0::3]
            npos, nneg = sum(1 for v in xs if v > 0.01), sum(1 for v in xs if v < -0.01)
            check(abs(npos - nneg) <= 0.001 * (npos + nneg), "c6 mirror on: points balanced in X (%d vs %d)" % (npos, nneg))
            check(abs(bb.minvec()[0] + bb.maxvec()[0]) < 0.02, "c6 mirror on: bbox symmetric in X")
    check(len(set(prints.values())) == len(seeds), "c4 %d seeds give %d different ships" % (len(seeds), len(set(prints.values()))))

    # parm branches (cheap settings where the branch allows)
    base = dict(detail=3, subdiv_hull=1, subdiv_med=0, subdiv_small=0, panel_subdiv=0, variants=2)
    n, bad = cook(**base)
    g = n.geometry()
    check(not bad, "c6 cheap base cooks clean %s" % bad[:1])
    ref_prims = len(g.prims())
    n, bad = cook(panels=0, **base)
    check(not bad and set(prim_attr(n.geometry(), "pf_panel")) == {0}, "c6 panels off -> pf_panel all 0")
    n, bad = cook(**base)
    check(len(set(prim_attr(n.geometry(), "pf_panel"))) > 1, "c6 panels on -> layers present")
    n, bad = cook(boosters=0, **base)
    check(not bad and 3 not in prim_attr(n.geometry(), "pf_part"), "c6 boosters off -> no pf_part 3")
    n, bad = cook(booster_flip=1, **base)
    g = n.geometry()
    zb = [pr.attribValue("pf_part") for pr in g.prims()]
    zs = [sum(v.point().position()[2] for v in pr.vertices()) / len(pr.vertices()) for pr in g.prims() if pr.attribValue("pf_part") == 3]
    check(not bad and zs and sum(zs) / len(zs) < 0, "c6 flip -> booster on -Z (mean z %.2f)" % (sum(zs) / max(len(zs), 1)))
    n, bad = cook(**base)
    g = n.geometry()
    zs = [sum(v.point().position()[2] for v in pr.vertices()) / len(pr.vertices()) for pr in g.prims() if pr.attribValue("pf_part") == 3]
    check(zs and sum(zs) / len(zs) > 0, "c6 default -> booster on +Z (mean z %.2f)" % (sum(zs) / max(len(zs), 1)))
    n, bad = cook(med_density=0, small_density=0, **base)
    check(not bad and set(prim_attr(n.geometry(), "pf_part")) == {0, 3}, "c6 density 0 -> only hull + booster")
    n, bad = cook(med_density=0, **base)
    check(not bad and set(prim_attr(n.geometry(), "pf_part")) >= {0, 2}, "c6 medium density 0 keeps small parts")
    for label, kw in (("mirror off", dict(mirror=0)), ("all off (audit: cleanup_grp warns)", dict(jiggle=0.0, ext_amount=0.0, med_density=0, small_density=0, panels=0, boosters=0, mirror=0)), ("subdiv 0 hull", dict(subdiv_hull=0)),
                      ("jiggle 0", dict(jiggle=0.0)), ("ext_amount 0", dict(ext_amount=0.0)),
                      ("variants 1", dict(variants=1)), ("panel_subdiv 1", dict(panel_subdiv=1)),
                      ("subdiv parts 1", dict(subdiv_med=1, subdiv_small=1)), ("detail 3 rot_step 0", dict(rot_step=(0.0, 0.0, 0.0)))):
        n, bad = cook(**dict(base, **kw))
        check(not bad and len(n.geometry().prims()) > 100, "c6 %s cooks clean, non-empty %s" % (label, bad[:1]))
    n, _ = cook(mirror=0, **base)
    bb = n.geometry().boundingBox()
    n2, _ = cook(**base)
    check(len(n.geometry().prims()) != len(n2.geometry().prims()), "c6 mirror off changes the output")
    # worst-case density cook ceiling (audit: 2.0+2.0 took >3 min); hard max must stay cheap
    import time
    mx = min(GEO.createNode("pf::starship_generator").parm(k).parmTemplate().maxValue() for k in ("med_density", "small_density"))
    n = GEO.createNode("pf::starship_generator")
    n.parm("med_density").set(mx); n.parm("small_density").set(mx)
    t0 = time.time(); n.cook(force=True); dt = time.time() - t0
    check(dt < 30, "c7 worst-case densities (%.1f each) cook %.1fs < 30s" % (mx, dt))
    print("FAILS: %d" % len(FAILS))
    sys.exit(1 if FAILS else 0)


main()
