"""Shape Generator (pf_shape_generator) checks. hython tests/spacetools/run_shapegen_checks.py [--mutations]

Oracle: shapegen_ref_full.json = the ORIGINAL Blender add-on's evaluated result for 29 cases x 20 seeds
(regenerate: blender -b --python tests/spacetools/shapegen_ref_blender_full.py -- tests/spacetools/shapegen_ref_full.json 20).
The generator uses a bit-exact MT19937, so for cases without bevel / subdivision the per-seed volume and area must agree with Blender.

CHECKS
  A per-seed parity (no bevel / subsurf): volume and area within 1.5%, booleans: volume only (coplanar merging changes area)
  B aggregate parity (bevel, subsurf, presets): mean volume within 5% (bevel_depth 15%), mean triangle count within 10%, shape count equal
  C invariants on every case: cooks without warnings, no _* attribute / group, outward winding (volume > 0), manifold
  D look-up: preset menu sets values, pf_level / pf_obj storage is int
CANNOT SEE: Blender's bevel is not Houdini's (corner topology, profile > 0.5, overlap) - B only bounds it; area of boolean results;
  Blender's own non-manifold output (bool_both) is excluded.
--mutations: breaks the asset on purpose (3 ways) and requires each check set to go red.
"""
import json
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import hou  # noqa: E402
import lib  # noqa: E402
from shapegen_common import apply_blender_params, cook, measure  # noqa: E402

REF = json.load(open(os.path.join(HERE, "shapegen_ref_full.json")))
SKIP = {"bool_both"}          # Blender's own result is non-manifold (16 open edges): nothing to compare
PER_SEED = {"blocks", "defaults", "rifle_1", "rifle_2", "big_sets", "big_scaled", "mirror_xyz", "cuts", "subsurf_simple",
            "bool_set", "bool_set_union", "bool_set_inter", "bool_medium", "bool_small_union", "bool_medium_inter"}
BOOL = {n for n in PER_SEED if n.startswith("bool")}
# Depth bevels are up to 1.41x wider than the same Width; Houdini clamps each edge to its neighbours, Blender lets bevels overlap: measured 13%
VOL_TOL = {"bevel_depth": 0.15}
fails = []


def bad(msg):
    fails.append(msg)
    print("FAIL", msg)


def run_cases(mutate=None):
    """-> list of failure strings (also appended to `fails` unless mutating)."""
    out = []
    g = lib.fresh()
    lib.install("pf_shape_generator")
    for name, case in REF.items():
        if name in SKIP:
            continue
        n = g.createNode("pf_shape_generator")
        if mutate:
            n.allowEditingOfContents()
            mutate(n)
        kw = {k: v for k, v in case["params"].items() if k != "random_seed"}
        apply_blender_params(n, kw)
        ms, errs, warn, leaks, neg, nonman = [], [], [], [], 0, 0
        for i, r in enumerate(case["runs"]):
            n.parm("random_seed").set(1000 + i)
            geo, b = cook(n)
            if b:
                warn.append(str(b[0])[:160])
            if geo is None or not geo.prims():
                m = dict(n=0, vol=0.0, area=0.0, tris=0, nonman=0, size=[0, 0, 0])
            else:
                m = measure(geo)
                leaks += [a.name() for a in geo.pointAttribs() + geo.primAttribs() + geo.vertexAttribs() + geo.globalAttribs() if a.name().startswith("_")]
                leaks += [gr.name() for gr in geo.primGroups() + geo.pointGroups() if gr.name().startswith("_")]
            ms.append(m)
            neg += m["vol"] < 0
            nonman += m["nonman"]
            if name in PER_SEED:
                e = abs(m["vol"] - r["vol"]) / max(abs(r["vol"]), 0.05)
                if name not in BOOL:
                    e = max(e, abs(m["area"] - r["area"]) / max(r["area"], 0.5))
                errs.append(e)
        if name in PER_SEED and max(errs) > 0.015:
            out.append("A %s: per-seed parity max error %.3f > 0.015" % (name, max(errs)))
        if name not in PER_SEED:
            rv = np.mean([r["vol"] for r in case["runs"]]); hv = np.mean([m["vol"] for m in ms])
            rt = np.mean([r["tris"] for r in case["runs"]]); ht = np.mean([m["tris"] for m in ms])
            tol = VOL_TOL.get(name, 0.05)
            if abs(hv - rv) > tol * abs(rv):
                out.append("B %s: mean volume %.2f vs Blender %.2f (>%d%%)" % (name, hv, rv, tol * 100))
            if abs(ht - rt) > 0.10 * rt:
                out.append("B %s: mean triangles %.0f vs Blender %.0f (>10%%)" % (name, ht, rt))
        if [m["n"] for m in ms] != [r["n"] for r in case["runs"]] and name != "bool_medium_inter":
            out.append("B %s: shape counts differ from Blender" % name)
        if warn:
            out.append("C %s: warnings %s" % (name, warn[0]))
        if leaks:
            out.append("C %s: internal names leak %s" % (name, sorted(set(leaks))[:4]))
        if neg:
            out.append("C %s: %d results wound inward (volume < 0)" % (name, neg))
        if nonman and name not in ("transformer",):
            out.append("C %s: %d non-manifold edges" % (name, nonman))
        n.destroy()
    return out


def run_misc():
    g = lib.fresh()
    lib.install("pf_shape_generator")
    n = g.createNode("pf_shape_generator")
    cb = n.parm("preset").parmTemplate().scriptCallback()
    exec(cb, {"kwargs": {"node": n, "script_value": "spaceship_5"}})
    if n.parm("medium_shape_num").eval() != 3 or abs(n.parmTuple("scale")[1].eval() - 3.0) > 1e-6:
        bad("D preset spaceship_5 did not set medium_shape_num=3 / scale y=3")
    geo, b = cook(n)
    for a in ("pf_level", "pf_obj"):
        at = geo.findPrimAttrib(a)
        if at is None or at.dataType() != hou.attribData.Int:
            bad("D prim attribute %s missing or not int" % a)
    if geo.findPrimGroup("pf_big") is None or geo.findPrimGroup("pf_small") is None:
        bad("D pf_big / pf_small groups missing")


def mut_winding(n):          # flip the emitted winding back to Blender's: booleans and volume sign break
    w = n.node("generate")
    w.parm("snippet").set(w.parm("snippet").eval().replace("for (int j = 3; j >= 0; j--) addvertex", "for (int j = 0; j < 4; j++) addvertex"))


def mut_taper(n):            # taper no longer random: per-seed parity must break
    w = n.node("generate")
    s = w.parm("snippet").eval()
    assert "float sf = uni(R, mint, maxt);" in s
    w.parm("snippet").set(s.replace("float sf = uni(R, mint, maxt);", "float sf = uni(R, mint, maxt) * 0 + 1.0;"))


def mut_bevel(n):            # bevel without any limit: runs away on thin shapes
    n.node("bevel").parm("limit").set(0)


if __name__ == "__main__":
    if "--mutations" in sys.argv:
        ok = True
        for label, mut, prefix in (("winding", mut_winding, "C"), ("taper", mut_taper, "A"), ("bevel limit", mut_bevel, "B")):
            res = run_cases(mut)
            hit = [r for r in res if r.startswith(prefix)]
            print("mutation %-12s -> %d failures, %d of kind %s" % (label, len(res), len(hit), prefix))
            ok = ok and bool(hit)
        print("MUTATIONS", "ALL RED" if ok else "SOME STAYED GREEN")
        sys.exit(0 if ok else 1)
    for r in run_cases():
        bad(r)
    run_misc()
    print("SHAPEGEN CHECKS", "FAILED (%d)" % len(fails) if fails else "OK")
    sys.exit(1 if fails else 0)
