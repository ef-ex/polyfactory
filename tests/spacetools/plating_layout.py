"""Layout statistics of a plated plane, to compare OUR layouts with the Blender original's as DISTRIBUTIONS over seeds.

plates = [(area_in_cells, lo(2), hi(2))] of the plate tops on a 16x16-cell plane (cell 0.25).
`python tests/spacetools/plating_layout.py` builds plating_layout_ref.json from the OBJs written by plating_layout_orig.py
(Blender, 12 master seeds per preset).  run_plating_checks.py compares ours against that file."""
import json, os, sys
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
REF = os.path.join(HERE, "plating_layout_ref.json")
CELL = 0.25
PRESETS = {3: "Simple_Panels_Irregular", 1: "Simple_Panels_Plain", 18: "Rounded_Corners"}
SEEDS = range(1, 13)


def metrics(plates):
    pl = [p for p in plates if p[0] > 0.3]            # slivers (corner bits) are not panels
    A = np.array([p[0] for p in pl]); n = len(pl)
    asp, inside, fills = [], 0, []
    for i, (a, lo, hi) in enumerate(pl):
        d = np.asarray(hi) - np.asarray(lo)
        if a >= 4:
            asp.append(max(d) / max(min(d), 1e-9))
        if 0.8 <= a <= 1.0 and (abs(d - 0.23) < 0.011).all():
            fills.append(a * CELL ** 2 / float(np.prod(d)))
        for j, (a2, lo2, hi2) in enumerate(pl):
            if i != j and (np.asarray(lo2) <= np.asarray(lo)).all() and (np.asarray(hi) <= np.asarray(hi2)).all() and a2 > a:
                inside += 1
                break
    return dict(n=n, maxfrac=A.max() / A.sum(), big=A[A >= 32].sum() / A.sum(), aspect=float(np.mean(asp)) if asp else 1.0,
                nested=inside / n, small=float((A < 4).mean()), cellfill=float(np.median(fills)) if fills else 1.0)


def plates_from_obj(path):
    V, F = [], []
    for l in open(path):
        if l.startswith("v "):
            V.append([float(x) for x in l.split()[1:4]])
        elif l.startswith("f "):
            F.append([int(t.split("/")[0]) - 1 for t in l.split()[1:]])
    V = np.array(V); ax = int(np.argmin(V.max(0) - V.min(0))); ua = [i for i in range(3) if i != ax]
    z = V[:, ax] if V[:, ax].max() > -V[:, ax].min() else -V[:, ax]
    keep = []
    for f in F:
        p = V[f]; nrm = np.cross(p[1] - p[0], p[2] - p[0]); ln = np.linalg.norm(nrm)
        if ln > 1e-12 and abs(nrm[ax] / ln) > 0.999 and np.ptp(z[f]) < 1e-4 and z[f].mean() >= 0.5 * z.max():
            keep.append(f)
    par = {}
    def find(x):
        while par.setdefault(x, x) != x:
            par[x] = par[par[x]]; x = par[x]
        return x
    for f in keep:
        for v in f[1:]:
            par[find(v)] = find(f[0])
    comp = {}
    for f in keep:
        comp.setdefault(find(f[0]), []).append(f)
    out = []
    for fs in comp.values():
        a = sum(_area(V[f][:, ua]) for f in fs); P = V[sorted({v for f in fs for v in f})][:, ua]
        out.append((a / CELL ** 2, P.min(0), P.max(0)))
    return out


def _area(poly):
    x, y = poly[:, 0], poly[:, 1]
    return 0.5 * abs(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))


def plates_from_geo(geo, up=1):
    """Our plates: pf_plate_top prims grouped by pf_plate_id (x/z of the plane, y = height)."""
    ua = [i for i in range(3) if i != up]
    g = geo.findPrimGroup("pf_plate_top")
    by = {}
    for pr in (g.prims() if g else []):
        pts = np.array([list(v.point().position()) for v in pr.vertices()])
        by.setdefault(pr.attribValue("pf_plate_id"), []).append(pts)
    out = []
    for polys in by.values():
        a = sum(_area(p[:, ua]) for p in polys); P = np.concatenate(polys)[:, ua]
        out.append((a / CELL ** 2, P.min(0), P.max(0)))
    return out


def build_ref(statdir):
    ref = {}
    for n in PRESETS:
        rows = [metrics(plates_from_obj("%s/orig_%d_%d.obj" % (statdir, n, s))) for s in SEEDS]
        ref[str(n)] = {k: [r[k] for r in rows] for k in rows[0]}
    json.dump(ref, open(REF, "w"), indent=0)
    return ref


if __name__ == "__main__":
    r = build_ref(sys.argv[1] if len(sys.argv) > 1 else "F:/cache/spacetools/plating_compare/v3/stat")
    for n, m in r.items():
        print(n, {k: round(float(np.mean(v)), 3) for k, v in m.items()})
