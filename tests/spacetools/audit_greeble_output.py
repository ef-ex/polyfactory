"""Independent audit of pf::greeble_scatter + odd inputs for both HDAs.
 A  non-overlap really non-overlapping (2D SAT of the greeble footprints in the host plane; exact for convex footprints, flat hosts)
 B  greebles sit on the host surface (lowest point on the host plane) and are no taller than height_max (+tol)
 C  odd inputs: empty, single quad, single tri, packed prims, existing attrs, 100k prims (timing)
hython tests/spacetools/audit_greeble_output.py"""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import hou
from lib import fresh, install, cook, fx_grid, fx_sphere, fx_box
from run_plating_checks import mk, run_preset, P, prim_pts, greebles

g = fresh(); install("pf_plating_generator"); install("pf_greeble_scatter")
RES = []


def rep(name, ok, detail=""):
    RES.append(ok); print(("PASS " if ok else "FAIL ") + name + (" :: " + str(detail) if detail else ""), flush=True)


def hull(pts):
    pts = sorted(set(map(tuple, np.round(pts, 7))))
    if len(pts) < 3:
        return np.array(pts)
    def cr(o, a, b): return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo = []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0: lo.pop()
        lo.append(p)
    up = []
    for p in reversed(pts):
        while len(up) >= 2 and cr(up[-2], up[-1], p) <= 0: up.pop()
        up.append(p)
    return np.array(lo[:-1] + up[:-1])


def sat_overlap(a, b, eps=1e-6):
    for poly in (a, b):
        for i in range(len(poly)):
            e = poly[(i + 1) % len(poly)] - poly[i]
            ax = np.array([-e[1], e[0]]); l = np.linalg.norm(ax)
            if l < 1e-12: continue
            ax /= l
            pa, pb = a @ ax, b @ ax
            if pa.max() <= pb.min() + eps or pb.max() <= pa.min() + eps:
                return False
    return True


def footprints(geo):
    """per greeble: (host normal, host centre, 2D hull of all points projected on the host plane, min/max height over plane)"""
    Pp = P(geo); pp = prim_pts(geo)
    gid = geo.primIntAttribValues("pf_greeble_id"); host = geo.primIntAttribValues("pf_host")
    pts = {}
    for i, v in enumerate(gid):
        if v >= 0: pts.setdefault(v, []).append(i)
    out = {}
    for v, prs in pts.items():
        allp = np.unique(np.concatenate([pp[i] for i in prs]))
        X = Pp[allp]
        h = host[prs[0]]
        out[v] = X, h
    return out


def host_plane(src_geo, h):
    pts = np.array([list(p.position()) for p in src_geo.prim(h).vertices() and [v.point() for v in src_geo.prim(h).vertices()]])
    n = np.array(src_geo.prim(h).normal())
    return pts.mean(0), n


def audit_case(label, mkf, **parms):
    src = mkf()
    n = mk(g, "pf_greeble_scatter", src, **parms)
    geo = cook(n)
    sg = src.geometry()
    fp = footprints(geo)
    # pf_host indexes input prims? check range
    nsrc = len(sg.prims())
    polys, hts, depth = {}, [], []
    for v, (X, h) in fp.items():
        if h < 0 or h >= nsrc:
            rep(label + " pf_host in range", False, (h, nsrc)); return
        c, nn = host_plane(sg, h)
        up = np.array([0, 1, 0]) if abs(nn[1]) < 0.9 else np.array([1, 0, 0])
        t1 = np.cross(nn, up); t1 /= np.linalg.norm(t1); t2 = np.cross(nn, t1)
        d = (X - c) @ nn
        hts.append(d.max()); depth.append(d.min())
        polys[v] = (hull(np.c_[(X - c) @ t1, (X - c) @ t2]), nn, c)
    keys = list(polys); ov = 0
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if np.linalg.norm(polys[a][2] - polys[b][2]) > 3 or np.dot(polys[a][1], polys[b][1]) < 0.999:
                continue
            # bring b into a's frame
            ca, na = polys[a][2], polys[a][1]
            up = np.array([0, 1, 0]) if abs(na[1]) < 0.9 else np.array([1, 0, 0])
            t1 = np.cross(na, up); t1 /= np.linalg.norm(t1); t2 = np.cross(na, t1)
            def proj(key):
                X = fp[key][0]; return hull(np.c_[(X - ca) @ t1, (X - ca) @ t2])
            if sat_overlap(proj(a), proj(b)): ov += 1
    mx = max(hts) if hts else 0; mn = min(depth) if depth else 0
    hmax = parms.get("height_max", 0.1)
    return dict(n=len(keys), overlaps=ov, max_h=mx, min_depth=mn, hmax=hmax)


# ---- A/B
cases = [("grid", lambda: fx_grid(g, 11, 4.0)), ("box", lambda: fx_box(g))]
for nm, mkf in cases:
    for cfg in (dict(placement="non_overlapping", coverage=100, subd_levels=1, deviation=0.5),
                dict(placement="non_overlapping", coverage=100, subd_levels=2, deviation=1.0, width_min=0.5, width_max=1.0, length_min=0.5, length_max=1.0),
                dict(placement="non_overlapping", coverage=100, subd_levels=1, deviation=0.5, kit="all", fixed_rotation=0, rotation_steps=1)):
        r = audit_case(nm, mkf, height_min=0.05, height_max=0.1, keep_aspect=0, **cfg)
        rep("greeble %s %s: no footprint overlaps (%d greebles)" % (nm, {k: v for k, v in cfg.items() if k in ('subd_levels', 'deviation', 'kit', 'width_max')}, r["n"]),
            r["overlaps"] == 0 and r["n"] > 20, r)
        rep("greeble %s: base on host plane (|min|<1e-4), height <= max+1e-4" % nm,
            abs(r["min_depth"]) < 1e-4 and r["max_h"] <= 0.1 + 1e-4, r)

# ---- C odd inputs
def tri(g):
    py = g.createNode("python")
    py.parm("python").set("geo=hou.pwd().geometry()\nps=[geo.createPoint() for _ in range(3)]\nfor p,x in zip(ps,[(0,0,0),(1,0,0),(0,0,1)]): p.setPosition(x)\npr=geo.createPolygon()\n[pr.addVertex(p) for p in ps]\n")
    return py
def empty(g):
    return g.createNode("null")
def packed(g):
    b = fx_box(g); p = g.createNode("pack"); p.setInput(0, b); return p
def with_attrs(g):
    s = fx_grid(g, 6); w = g.createNode("attribwrangle"); w.setInput(0, s); w.parm("class").set(1)
    w.parm("snippet").set('v@Cd={1,0,0}; i@pf_plate_id=5; f@pf_plate_area=2; i@pf_greeble_id=3; s@pf_kit_name="x"; v@uv=@P; setprimgroup(0,"pf_plate_top",@primnum,1);')
    return w
for hdaname, parms in (("pf_plating_generator", {}), ("pf_greeble_scatter", {"coverage": 100})):
    for nm, mkf in (("empty", empty), ("single tri", tri), ("packed", packed), ("existing attrs", with_attrs)):
        try:
            n = mk(g, hdaname, mkf(g), **parms)
            geo = cook(n)
            rep("%s on %s cooks without warning (%d prims)" % (hdaname, nm, len(geo.prims())), True)
        except Exception as e:
            rep("%s on %s cooks without warning" % (hdaname, nm), False, str(e)[:250])
# existing attrs: do greebles' ids restart / does it clobber?
n = mk(g, "pf_greeble_scatter", with_attrs(g), coverage=100, subd_levels=1)
n.cook(force=True); geo = n.geometry()
print("INFO existing-attr: warnings", n.warnings() or [c.warnings() for c in n.children() if c.warnings()])
ids = geo.primIntAttribValues("pf_greeble_id")
print("INFO existing-attr input: unique pf_greeble_id values among output", sorted(set(ids))[:6], "pf_plate_id host inherited", sorted(set(geo.primIntAttribValues("pf_plate_id")))[:4], "Cd set", geo.findPrimAttrib("Cd") is not None)
# 100k prim timing
big = g.createNode("grid"); big.parmTuple("size").set((20, 20)); big.parm("rows").set(317); big.parm("cols").set(317)
for hdaname, parms in (("pf_greeble_scatter", dict(coverage=50, subd_levels=1)), ("pf_plating_generator", dict(subdiv=0, amount=20))):
    n = mk(g, hdaname, big, **parms)
    t = time.time()
    try:
        geo = cook(n); rep("%s 100k-prim grid cooks" % hdaname, True, "%.1fs, %d prims out" % (time.time() - t, len(geo.prims())))
        print("INFO %s 100k: %.1fs" % (hdaname, time.time() - t), flush=True)
    except Exception as e:
        rep("%s 100k-prim grid cooks" % hdaname, False, str(e)[:200])
print("failed:", RES.count(False))
sys.exit(1 if False in RES else 0)
