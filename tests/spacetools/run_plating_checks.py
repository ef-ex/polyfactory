"""spacetools tool #2 checks: pf::plating_generator + pf::greeble_scatter.

    hython tests/spacetools/run_plating_checks.py            # all checks, exit 1 on any failure
    hython tests/spacetools/run_plating_checks.py --mutate   # each mutation must turn its check RED

Scene checks in throwaway hython sessions (never saves a .hip).  Oracles are independent of the
implementation: closed-form areas/gaps, known plate counts (a box with no cuts has 6 plates, a grid with
no cuts has 1), cell counts (4^levels x quads), exact bounding boxes of a known kit piece.

What the checks cannot see: how the result LOOKS (renders are inspected by hand, see ideas/spacetools.md),
curved-surface footprints (overlap is measured with axis-aligned boxes: exact on grid/box, not on a
sphere), layouts of the random patterns beyond "cooks, deterministic, plates disjoint by the groove".
"""
import itertools
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import numpy as np
import hou
from lib import (cook, fresh, install, fx_grid, fx_sphere, fx_box, fx_nonconvex, fx_non_quad)

FAILS, PASSES = [], []
MUT = {}          # active mutation: {hda type name: fn(node)}


def check(name, ok, detail=""):
    (PASSES if ok else FAILS).append((name, detail))
    print(("PASS " if ok else "FAIL ") + name + ((" :: " + str(detail)) if (detail and not ok) else ""), flush=True)


def setp(n, p):
    n.allowEditingOfContents()
    for k, v in p.items():
        t = n.parmTuple(k)
        if t is not None and len(t) > 1:
            t.set(v)
        else:
            n.parm(k).set(v)


def mk(g, typ, src, kitin=None, **p):
    n = g.createNode(typ)
    n.setInput(0, src)
    if kitin is not None:
        n.setInput(1, kitin)
    setp(n, p)
    fn = MUT.get(typ)
    if fn:
        fn(n)
    return n


def P(geo):
    return np.array(geo.pointFloatAttribValues("P")).reshape(-1, 3)


def prim_pts(geo):
    return [[v.point().number() for v in pr.vertices()] for pr in geo.prims()]


def grp_idx(geo, name):
    gp = geo.findPrimGroup(name)
    return set(p.number() for p in gp.prims()) if gp else set()


def internals(geo):
    bad = []
    for kind, f in (("pt", geo.pointAttribs), ("vtx", geo.vertexAttribs), ("prim", geo.primAttribs), ("dtl", geo.globalAttribs)):
        bad += [kind + ":" + a.name() for a in f() if a.name().startswith("_")]
    for kind, f in (("pg", geo.primGroups), ("ptg", geo.pointGroups), ("eg", geo.edgeGroups)):
        bad += [kind + ":" + a.name() for a in f() if a.name().startswith("_")]
    return bad


def sig(geo):
    return (tuple(geo.pointFloatAttribValues("P")), len(geo.prims()))


# ============================ plating ======================================
PATTERNS = ["crisscross", "triangles", "rectangles", "rectangles_cuts", "irregular", "edges"]


def plating_matrix(g):
    fx = {"grid": lambda: fx_grid(g, 6, 4.0), "sphere": lambda: fx_sphere(g), "box": lambda: fx_box(g),
          "L": lambda: fx_nonconvex(g), "tri": lambda: fx_non_quad(g)}
    cfgs = [dict(pattern=p, subdiv=2, amount=20, triangle_amount=30, rect_count=15) for p in PATTERNS]
    cfgs += [
        dict(floor="remove", groove_width=0.05), dict(subdiv=0), dict(subdiv=1, cut_by_angle=0),
        dict(bevel_amount=0.01, bevel_segments=3, corner_radius=0.03, corner_segments=2, taper=0.01,
             groove_depth=0.03, groove_width=0.04, height_min=0.05, height_max=0.08, rivets=1, rivet_size=0.02, random_color=1),
        dict(height_min=-0.05, height_max=0.05), dict(groove_width=0.0, groove_depth=0.0, amount=30),
        dict(pattern="irregular", irregular_amount=95), dict(amount=100), dict(amount=0),
    ]
    bad, n_ok = [], 0
    for fxn, mkf in fx.items():
        for cfg in cfgs:
            src = mkf()
            try:
                geo = cook(mk(g, "pf_plating_generator", src, **cfg))
            except Exception as e:
                bad.append((fxn, cfg, str(e)[:200])); continue
            n_ok += 1
            b = internals(geo)
            if b:
                bad.append((fxn, cfg, "internals " + str(b)))
            for a, t in (("pf_plate_id", hou.attribData.Int), ("pf_plate_area", hou.attribData.Float), ("pf_plate_height", hou.attribData.Float)):
                at = geo.findPrimAttrib(a)
                if at is None or at.dataType() != t:
                    bad.append((fxn, cfg, "attr " + a))
            if np.isnan(P(geo)).any():
                bad.append((fxn, cfg, "NaN"))
    return bad, len(fx) * len(cfgs)


def c_plating_matrix(g):
    bad, total = plating_matrix(g)
    check("plating: %d mesh x config cooks clean, no _* leaks, pf_ attr storage, no NaN" % total, not bad, bad[:3])


def c_plating_determinism(g):
    src = fx_grid(g, 6, 4.0)
    ok, why = True, ""
    for pat in PATTERNS[:5]:
        a = cook(mk(g, "pf_plating_generator", src, pattern=pat, seed=7, amount=20, subdiv=2))
        b = cook(mk(g, "pf_plating_generator", src, pattern=pat, seed=7, amount=20, subdiv=2))
        c = cook(mk(g, "pf_plating_generator", src, pattern=pat, seed=8, amount=20, subdiv=2))
        if sig(a) != sig(b):
            ok, why = False, pat + " not deterministic"
        if sig(a) == sig(c):
            ok, why = False, pat + " seed has no effect"
    check("plating: same seed -> identical points; other seed -> different", ok, why)


def tops_by_plate(geo):
    return grp_idx(geo, "pf_plate_top"), geo.primIntAttribValues("pf_plate_id")


def c_plating_oracles(g):
    gsz, gw = 4.0, 0.1
    geo = cook(mk(g, "pf_plating_generator", fx_grid(g, 6, gsz), amount=0, groove_width=gw, subdiv=2, height_min=0.05, height_max=0.05))
    tops, pid = tops_by_plate(geo)
    check("plating: grid with no cuts is exactly 1 plate", len(set(pid[i] for i in tops)) == 1, len(set(pid[i] for i in tops)))
    area = sum(geo.prim(i).intrinsicValue("measuredarea") for i in tops)
    want = (gsz - gw) ** 2
    check("plating: top area = (size - groove)^2 (closed form)", abs(area - want) < 1e-4, (area, want))
    ys = [geo.prim(i).positionAtInterior(.5, .5, 0)[1] for i in tops]
    check("plating: top height = plate height", max(abs(y - 0.05) for y in ys) < 1e-5, max(abs(y - 0.05) for y in ys))
    nb = cook(mk(g, "pf_plating_generator", fx_box(g), amount=0, subdiv=1, cut_by_angle=1))
    tops, pid = tops_by_plate(nb)
    check("plating: box with no cuts is exactly 6 plates (90 degree edges cut)", len(set(pid[i] for i in tops)) == 6, len(set(pid[i] for i in tops)))
    n1 = cook(mk(g, "pf_plating_generator", fx_box(g), amount=0, subdiv=1, cut_by_angle=0))
    tops, pid = tops_by_plate(n1)
    check("plating: box with angle cuts off and no cuts is 1 plate", len(set(pid[i] for i in tops)) == 1, len(set(pid[i] for i in tops)))


def c_plating_gap_and_heights(g):
    gw = 0.1
    geo = cook(mk(g, "pf_plating_generator", fx_grid(g, 6, 4.0), amount=40, groove_width=gw, subdiv=2, height_min=0.02, height_max=0.06))
    tops, pid = tops_by_plate(geo)
    ph = geo.primFloatAttribValues("pf_plate_height")
    Pp = P(geo)
    pp = prim_pts(geo)
    boxes, ok_h = {}, True
    for i in tops:
        pts = Pp[pp[i]]
        boxes.setdefault(pid[i], []).append((pts[:, 0].min(), pts[:, 0].max(), pts[:, 2].min(), pts[:, 2].max()))
        if abs(pts[:, 1].mean() - ph[i]) > 1e-5 or not (0.02 - 1e-6 <= ph[i] <= 0.06 + 1e-6):
            ok_h = False
    check("plating: every top at its plate height, heights within [min,max]", ok_h)
    ids = list(boxes)
    mn = 1e9
    for a, b in itertools.combinations(ids, 2):
        for ra in boxes[a]:
            for rb in boxes[b]:
                dx = max(ra[0] - rb[1], rb[0] - ra[1], 0)
                dz = max(ra[2] - rb[3], rb[2] - ra[3], 0)
                mn = min(mn, float(np.hypot(dx, dz)))
    check("plating: tops of different plates are >= groove width apart (flat grid)", len(ids) > 3 and mn >= gw - 1e-4, (len(ids), mn))
    d = cook(mk(g, "pf_plating_generator", fx_grid(g, 6, 4.0), amount=40, groove_width=0.1, groove_depth=0.03, subdiv=2))
    gr = grp_idx(d, "pf_plate_groove")
    Pd, pd_ = P(d), prim_pts(d)
    ymin = min(Pd[pt][1] for i in gr for pt in pd_[i]) if gr else 9
    check("plating: groove floor sits groove_depth below the surface", abs(ymin + 0.03) < 1e-5, ymin)


def c_plating_floor_remove_closed(g):
    geo = cook(mk(g, "pf_plating_generator", fx_grid(g, 6, 4.0), amount=30, groove_width=0.05, subdiv=2, floor="remove"))
    no_groove = not grp_idx(geo, "pf_plate_groove")
    cnt = {}
    for pts in prim_pts(geo):
        for a, b in zip(pts, pts[1:] + pts[:1]):
            k = (min(a, b), max(a, b)); cnt[k] = cnt.get(k, 0) + 1
    open_edges = sum(1 for v in cnt.values() if v != 2)
    check("plating: floor=remove leaves no groove prims and closed (watertight) plates", no_groove and open_edges == 0 and len(geo.prims()) > 0, (no_groove, open_edges))


def c_plating_group_and_chain(g):
    src = fx_grid(g, 6, 4.0)
    half = g.createNode("groupcreate"); half.setInput(0, src)
    half.parm("groupname").set("half"); half.parm("groupbounding").set(1)
    half.parmTuple("size").set((2, 1, 4)); half.parmTuple("t").set((-1, 0, 0))
    gin = cook(half)
    nin = len(grp_idx(gin, "half"))
    geo = cook(mk(g, "pf_plating_generator", half, group="half", subdiv=0, amount=0, groove_width=0.05))
    pid = geo.primIntAttribValues("pf_plate_id")
    un = sum(1 for i in pid if i == -1)
    check("plating: faces outside the group pass through untouched (pf_plate_id -1)", un == 25 - nin and 0 < nin < 25, (un, nin))
    l1 = mk(g, "pf_plating_generator", fx_grid(g, 6, 4.0), amount=10, subdiv=1, groove_width=0.1, height_min=0.1, height_max=0.1)
    g1 = cook(l1)
    t1 = grp_idx(g1, "pf_plate_top")
    pid1 = g1.primIntAttribValues("pf_plate_id")
    ids1 = set(pid1[i] for i in range(len(g1.prims())) if i not in t1)
    l2 = mk(g, "pf_plating_generator", l1, group="pf_plate_top", amount=30, subdiv=1, groove_width=0.02, height_min=0.02, height_max=0.02, seed=3)
    g2 = cook(l2)
    t2, pid2 = tops_by_plate(g2)
    ids2 = set(pid2[i] for i in t2)
    ys = [g2.prim(i).positionAtInterior(.5, .5, 0)[1] for i in t2]
    check("plating: level 2 on level 1 tops: new plate ids disjoint from level-1 ids, stacked on top (y=0.12)",
          len(ids2) > 1 and not (ids1 & ids2) and max(abs(y - 0.12) for y in ys) < 1e-5, (len(ids2), ids1 & ids2, max(abs(y - 0.12) for y in ys)))


def run_preset(n, key):
    cb = n.parm("preset").parmTemplate().scriptCallback()
    n.parm("preset").set(key)
    exec(cb, {"kwargs": {"node": n, "script_value": key}})


def c_plating_presets(g):
    bad, cnt = [], 0
    src = fx_grid(g, 6, 4.0)
    n = mk(g, "pf_plating_generator", src)
    keys = [k for k in n.parm("preset").parmTemplate().menuItems() if k != "none"]
    for k in keys:
        n = mk(g, "pf_plating_generator", src, subdiv=2)
        run_preset(n, k)
        cnt += 1
        try:
            geo = cook(n)
            if len(geo.prims()) < 50 or internals(geo):
                bad.append((k, "empty/leak"))
        except Exception as e:
            bad.append((k, str(e)[:150]))
    n = mk(g, "pf_plating_generator", src)
    run_preset(n, "Rounded_Corners")
    check("plating: all %d presets apply and cook; Rounded_Corners sets corner_radius 0.037" % cnt,
          cnt >= 15 and not bad and abs(n.parm("corner_radius").eval() - 0.037) < 1e-6, bad[:3])


# ============================ greeble ======================================
def kit_two_boxes(g, off=(5.0, 5.0, 5.0)):
    b0 = g.createNode("box"); b0.parmTuple("size").set((2, 1, 0.5)); b0.parmTuple("t").set(off)
    b1 = g.createNode("box"); b1.parmTuple("size").set((1, 1, 1)); b1.parmTuple("t").set((off[0] + 9, off[1], off[2]))
    m = g.createNode("merge"); m.setInput(0, b0); m.setInput(1, b1)
    return m


def kit_one_box(g, off=(5.0, 5.0, 5.0)):
    b0 = g.createNode("box"); b0.parmTuple("size").set((2, 1, 0.5)); b0.parmTuple("t").set(off)
    return b0


def greebles(geo):
    ids = np.array(geo.primIntAttribValues("pf_greeble_id"))
    Pp = P(geo)
    pp = prim_pts(geo)
    out = {}
    for i, gid in enumerate(ids):
        if gid < 0:
            continue
        pts = Pp[pp[i]]
        a = out.setdefault(int(gid), [np.full(3, 1e30), np.full(3, -1e30), i])
        a[0] = np.minimum(a[0], pts.min(0)); a[1] = np.maximum(a[1], pts.max(0))
    return out


def overlaps(gb, eps=1e-7):
    keys = list(gb)
    lo = np.array([gb[k][0] for k in keys]); hi = np.array([gb[k][1] for k in keys])
    n = 0
    for a in range(len(keys)):
        d = np.minimum(hi[a], hi[a + 1:]) - np.maximum(lo[a], lo[a + 1:])
        n += int(np.sum(np.all(d > eps, axis=1)))
    return n


def c_greeble_matrix(g):
    bad, total = [], 0
    fx = {"grid": lambda: fx_grid(g, 6, 4.0), "box": lambda: fx_box(g), "sphere": lambda: fx_sphere(g)}
    cfgs = [
        dict(kit="defaults"), dict(kit="hull", placement="overlapping", amount=60), dict(kit="panels", subd_levels=2),
        dict(kit="custom", coverage=15, subd_levels=0), dict(kit="all", coverage=30),
        dict(kit="defaults", keep_aspect=0, height_max=0.2),
        dict(kit="defaults", override_height=1, height_override=0.07),
        dict(kit="defaults", custom_normal=1, normal_direction=(0.0, 1.0, 0.0)),
        dict(kit="defaults", fixed_rotation=1, rotation_steps=3), dict(kit="defaults", random_color=1, keep_surface=0),
        dict(kit="defaults", coverage=0), dict(kit="defaults", amount=0, placement="overlapping"),
    ]
    for fxn, mkf in fx.items():
        for cfg in cfgs:
            total += 1
            try:
                geo = cook(mk(g, "pf_greeble_scatter", mkf(), **cfg))
            except Exception as e:
                bad.append((fxn, cfg, str(e)[:200])); continue
            b = internals(geo)
            if b:
                bad.append((fxn, cfg, b))
            for a, t in (("pf_greeble_id", hou.attribData.Int), ("pf_kit", hou.attribData.Int), ("pf_host", hou.attribData.Int)):
                at = geo.findPrimAttrib(a)
                if at is None or at.dataType() != t:
                    bad.append((fxn, cfg, "attr " + a))
    pl = mk(g, "pf_plating_generator", fx_grid(g, 6, 4.0), amount=20, subdiv=2, height_min=0.03, height_max=0.05)
    for grp in ("pf_plate_top", "pf_plate_side", ""):
        total += 1
        try:
            geo = cook(mk(g, "pf_greeble_scatter", pl, kit_two_boxes(g), kit="input", group=grp, coverage=40))
            if internals(geo):
                bad.append(("chain", grp, internals(geo)))
        except Exception as e:
            bad.append((("chain", grp), str(e)[:200]))
    check("greeble: %d mesh x config (+3 input-kit chains on plating groups) cook clean, no _* leaks, pf_ attrs" % total, not bad, bad[:3])


def c_greeble_determinism(g):
    src = fx_grid(g, 6, 4.0)
    ok, why = True, ""
    for pl in ("overlapping", "non_overlapping"):
        a = cook(mk(g, "pf_greeble_scatter", src, placement=pl, seed=3, kit="hull"))
        b = cook(mk(g, "pf_greeble_scatter", src, placement=pl, seed=3, kit="hull"))
        c = cook(mk(g, "pf_greeble_scatter", src, placement=pl, seed=4, kit="hull"))
        if sig(a) != sig(b):
            ok, why = False, pl + " not deterministic"
        if sig(a) == sig(c):
            ok, why = False, pl + " seed no effect"
    check("greeble: same seed -> identical points; other seed -> different", ok, why)


def c_greeble_counts(g):
    src = fx_grid(g, 6, 4.0)   # 25 quads
    ok, why = True, ""
    for lv in (0, 1, 2):
        geo = cook(mk(g, "pf_greeble_scatter", src, coverage=100, subd_levels=lv, kit="defaults", keep_surface=0))
        n = len(greebles(geo))
        if n != 25 * 4 ** lv:
            ok, why = False, (lv, n)
    geo = cook(mk(g, "pf_greeble_scatter", src, coverage=0, kit="defaults", keep_surface=1))
    if len(greebles(geo)) != 0:
        ok, why = False, "coverage 0"
    geo = cook(mk(g, "pf_greeble_scatter", src, placement="overlapping", amount=77, kit="defaults", keep_surface=0))
    if len(greebles(geo)) != 77:
        ok, why = False, ("overlapping", len(greebles(geo)))
    check("greeble: cell count = 4^levels x quads at 100% coverage; 0 at 0%; overlapping = amount", ok, why)


def c_greeble_nonoverlap(g):
    src = fx_grid(g, 6, 4.0)
    geo = cook(mk(g, "pf_greeble_scatter", src, coverage=100, subd_levels=2, kit="defaults", width_min=0.5, width_max=1.0,
                  length_min=0.5, length_max=1.0, keep_surface=0))
    gb = greebles(geo)
    check("greeble: non-overlapping on grid: no two greeble boxes intersect (400 greebles)", len(gb) == 400 and overlaps(gb) == 0, (len(gb), overlaps(gb)))
    ov = cook(mk(g, "pf_greeble_scatter", fx_grid(g, 3, 1.0), placement="overlapping", amount=60, kit="defaults", width_min=0.5,
                 width_max=1.0, length_min=0.5, length_max=1.0, keep_surface=0))
    check("greeble: the overlap checker finds overlaps in overlapping mode (positive control)", overlaps(greebles(ov)) > 0, overlaps(greebles(ov)))
    bx = cook(mk(g, "pf_greeble_scatter", fx_box(g), coverage=100, subd_levels=1, kit="hull", keep_surface=0))
    gbx = greebles(bx)
    check("greeble: non-overlapping on a box: no two greeble boxes intersect", len(gbx) == 6 * 4 and overlaps(gbx) == 0, (len(gbx), overlaps(gbx)))


def c_greeble_transform_oracle(g):
    src = fx_grid(g, 6, 4.0)        # quads 0.8 x 0.8 in the xz plane, normal +y
    kw = dict(kit="input", subd_levels=0, coverage=100, width_min=0.5, width_max=0.5, length_min=0.5, length_max=0.5,
              fixed_rotation=1, keep_surface=0)
    ok, why = True, ""
    for steps, want in ((0, (0.4, 0.2)), (1, (0.2, 0.4)), (2, (0.4, 0.2))):
        geo = cook(mk(g, "pf_greeble_scatter", src, kit_one_box(g), rotation_steps=steps, keep_aspect=1, **kw))
        gb = greebles(geo)
        sizes = [(b[1] - b[0]) for b in gb.values()]
        if len(gb) != 25 or any(abs(s[0] - want[0]) > 1e-5 or abs(s[2] - want[1]) > 1e-5 or abs(s[1] - 0.1) > 1e-5 for s in sizes):
            ok, why = False, (steps, sizes[:1], want)
    check("greeble: keep-aspect box (2x1x0.5) in footprint 0.4x0.4 -> 0.4x0.2x0.1; quarter turns swap x/z", ok, why)
    geo = cook(mk(g, "pf_greeble_scatter", src, kit_one_box(g), keep_aspect=0, height_min=0.07, height_max=0.07, **{**kw, "fixed_rotation": 0}))
    gb = greebles(geo)
    sizes = [(b[1] - b[0]) for b in gb.values()]
    check("greeble: stretched to footprint 0.4x0.4, height 0.07 (kit far from origin is re-centred)",
          len(gb) == 25 and all(abs(s[0] - 0.4) < 1e-5 and abs(s[2] - 0.4) < 1e-5 and abs(s[1] - 0.07) < 1e-5 for s in sizes), sizes[:1])
    gi = cook(fx_grid(g, 6, 4.0))
    Pi, pi = P(gi), prim_pts(gi)
    hosts = geo.primIntAttribValues("pf_host")
    ok = True
    for gid, (lo, hi, i0) in gb.items():
        q = Pi[pi[hosts[i0]]]
        c = (lo + hi) / 2
        if abs(lo[1]) > 1e-6 or abs(c[0] - q[:, 0].mean()) > 1e-5 or abs(c[2] - q[:, 2].mean()) > 1e-5:
            ok = False
    check("greeble: base on the surface (y=0) and centred on its host face (pf_host)", ok)


def c_greeble_chain_on_plates(g):
    pl = mk(g, "pf_plating_generator", fx_grid(g, 6, 4.0), amount=25, subdiv=2, groove_width=0.06, height_min=0.05, height_max=0.05)
    geo = cook(mk(g, "pf_greeble_scatter", pl, kit_one_box(g), kit="input", group="pf_plate_top", subd_levels=1, coverage=100,
                  keep_surface=1, keep_aspect=0, height_min=0.02, height_max=0.02))
    gb = greebles(geo)
    pid = geo.primIntAttribValues("pf_plate_id")
    ok_base = all(abs(b[0][1] - 0.05) < 1e-5 for b in gb.values())
    host_id = all(pid[b[2]] >= 0 for b in gb.values())
    check("greeble: on pf_plate_top the greebles stand on the plates (y=0.05) and inherit pf_plate_id",
          len(gb) > 20 and ok_base and host_id, (len(gb), ok_base, host_id))


def c_greeble_presets(g):
    bad = []
    src = fx_grid(g, 6, 4.0)
    keys = [k for k in mk(g, "pf_greeble_scatter", src).parm("preset").parmTemplate().menuItems() if k != "none"]
    for k in keys:
        n = mk(g, "pf_greeble_scatter", src)
        run_preset(n, k)
        try:
            geo = cook(n)
            if not greebles(geo):
                bad.append((k, "no greebles"))
        except Exception as e:
            bad.append((k, str(e)[:150]))
    check("greeble: all %d presets apply and cook with greebles" % len(keys), len(keys) >= 4 and not bad, bad)


CHECKS = [c_plating_matrix, c_plating_determinism, c_plating_oracles, c_plating_gap_and_heights, c_plating_floor_remove_closed,
          c_plating_group_and_chain, c_plating_presets, c_greeble_matrix, c_greeble_determinism, c_greeble_counts,
          c_greeble_nonoverlap, c_greeble_transform_oracle, c_greeble_chain_on_plates, c_greeble_presets]


def run_all(only=None):
    FAILS.clear(); PASSES.clear()
    g = fresh()
    install("pf_plating_generator"); install("pf_greeble_scatter")
    for c in CHECKS:
        if only and c.__name__ not in only:
            continue
        t = time.time()
        try:
            c(g)
        except Exception as e:
            check(c.__name__ + " (raised)", False, repr(e)[:300])
        print("   %s %.1fs" % (c.__name__, time.time() - t), flush=True)
    return len(FAILS)


# ============================ mutations =====================================
def sub(node, child, old, new):
    c = node.node(child)
    s = c.parm("snippet").unexpandedString()
    assert old in s, (child, old)
    c.parm("snippet").set(s.replace(old, new))


MUTATIONS = [
    ("groove inset ignored", "pf_plating_generator", lambda n: n.node("groove_ring").parm("inset").setExpression("0"), ["c_plating_oracles", "c_plating_gap_and_heights"]),
    ("plates never merge (union skipped)", "pf_plating_generator", lambda n: sub(n, "plates", "if (groove) continue;", "if (groove || p1 < 1000000) continue;"), ["c_plating_oracles"]),
    ("_* scaffolding leaks (all clean_* bypassed)", "pf_plating_generator", lambda n: [n.node(c).bypass(True) for c in ("clean_pt", "clean_vtx", "clean_prim", "clean_dtl")], ["c_plating_matrix"]),
    ("seed ignored in cuts", "pf_plating_generator", lambda n: sub(n, "cut", 'int    seed = chi("../seed");', "int    seed = 1;"), ["c_plating_determinism"]),
    ("plate height ignored", "pf_plating_generator", lambda n: sub(n, "plates", '"_zs", p, hts[plate[p]] + depth', '"_zs", p, 0.01'), ["c_plating_gap_and_heights"]),
    ("greeble footprint 1.8x too big", "pf_greeble_scatter", lambda n: sub(n, "place", "* width * 0.5, hl", "* width * 0.9, hl"), ["c_greeble_nonoverlap"]),
    ("kit not lifted onto z=0", "pf_greeble_scatter", lambda n: sub(n, "kit_normalise", "(P0.z - lo[k].z) / kz[k]", "(P0.z - c.z) / kz[k]"), ["c_greeble_transform_oracle"]),
    ("coverage test inverted", "pf_greeble_scatter", lambda n: sub(n, "place", "if (chk > cov) continue;", "if (chk <= cov) continue;"), ["c_greeble_counts"]),
    ("quarter turns ignored", "pf_greeble_scatter", lambda n: sub(n, "place", "for (int r = 0; r < rot; r++)", "for (int r = 0; r < 0; r++)"), ["c_greeble_transform_oracle"]),
    ("greeble seed ignored", "pf_greeble_scatter", lambda n: sub(n, "place", 'int    seed = chi("../seed");', "int    seed = 1;"), ["c_greeble_determinism"]),
]


def run_mutations():
    bad = 0
    for name, typ, fn, expect in MUTATIONS:
        MUT.clear(); MUT[typ] = fn
        n = run_all(only=set(expect))
        print("MUTATION %-45s -> %s" % (name, "RED (good)" if n > 0 else "STILL GREEN (BAD)"), flush=True)
        bad += (n == 0)
    MUT.clear()
    return bad


if __name__ == "__main__":
    if "--mutate" in sys.argv:
        sys.exit(1 if run_mutations() else 0)
    n = run_all()
    print("\n%d passed, %d failed" % (len(PASSES), len(FAILS)))
    sys.exit(1 if n else 0)
