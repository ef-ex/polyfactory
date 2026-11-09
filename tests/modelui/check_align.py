"""Headless checks of modelUI Align (F2d): the maths of Align, Quick Align and Normal Align on real pieces and objects,
the hit test, and the preview / Apply / Cancel session. Each check has a paired source mutation that must turn it red.

Run:  hython tests/modelui/check_align.py     (exit 0 = all green AND every mutation reddened its paired check)
Throwaway session, never saves a .hip. Uses two kitbash library files (F:/3d/kitbashLib).

The oracle is independent of align.py: an item's WORLD points come from an Object Merge (into this object) of its
object, unpacked for container pieces and filtered by pf_piece; its local-to-world affine map is fitted to its local
points by least squares (numpy), and box, pivot, axes and scales are read from those. Fixture: a piece in a moved,
rotated and uniformly scaled container, a loose box object with rotation, non-uniform scale and a pivot (p and pr), a
target piece in another rotated container and a target box object with a pivot.
TOL = 1e-4 world units at |values| <= 30 (float32 P/orient/scale in the stash: about 4e-6 at that size, times a few
matrix products).

What these cannot see: the dialog and picking in a viewer (gui_f2d.py), hidden pieces (they align by their pivot),
shear (a piece cannot store it), animated or locked object parameters, objects inside subnets (only /obj children).
"""
import glob
import os
import sys

import numpy as np

import hou

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import align, containers, pieces_ui  # noqa: E402

FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))
TOL = 1e-4
POINTS = ("min", "center", "pivot", "max")
LOG = []


def xf(t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
    return hou.hmath.buildScale(s) * hou.hmath.buildRotate(r) * hou.hmath.buildTranslate(t)


# --- the oracle ----------------------------------------------------------------------------------------------------------
class Oracle:
    def __init__(self):
        self.obj = hou.node("/obj").createNode("geo", "oracle")
        self.obj.setDisplayFlag(False)
        self.nodes = {}

    def _merge(self, node):
        key = node.path()
        if key not in self.nodes:
            om = self.obj.createNode("object_merge")
            om.parm("objpath1").set(key)
            om.parm("xformtype").set(1)   # into this object (at the origin): world positions
            un = self.obj.createNode("unpack")
            un.setFirstInput(om)
            un.parm("transfer_attributes").set("pf_piece")
            self.nodes[key] = un
        return self.nodes[key]

    def world(self, pid):
        """World points of the item, in the order of its local points."""
        if isinstance(pid, tuple):
            c = hou.nodeBySessionId(pid[1])
            g = self._merge(c).geometry()
            prims = [p for p in g.prims() if p.attribValue("pf_piece") == pid[2]]
            pts = []
            for pr in prims:
                for v in pr.vertices():
                    pts.append(v.point())
            seen, out = set(), []
            for p in sorted(pts, key=lambda p: p.number()):
                if p.number() not in seen:
                    seen.add(p.number())
                    out.append(tuple(p.position()))
            return np.array(out)
        n = hou.nodeBySessionId(pid)
        return np.array([tuple(p.position()) for p in self._merge(n).geometry().points()])

    @staticmethod
    def local(pid):
        """Local points straight from the source: the usdimport of the piece's file, or the object's display SOP."""
        if isinstance(pid, tuple):
            c = hou.nodeBySessionId(pid[1])
            src = [p for p in containers.stash(c).geometry().points() if p.intAttribValue("pf_piece") == pid[2]][0]
            path = src.stringAttribValue("pf_source")
            u = [n for n in c.children() if n.type().name() == "usdimport" and n.parm("filepath1").eval() == path][0]
            return np.array([tuple(p.position()) for p in u.geometry().points()])
        n = hou.nodeBySessionId(pid)
        return np.array([tuple(p.position()) for p in n.displayNode().geometry().points()])

    def affine(self, pid):
        """(L 3x3, t) with world = local @ L + t, fitted; raises when the fit is not exact (order mismatch)."""
        loc, w = self.local(pid), self.world(pid)
        a = np.hstack([loc, np.ones((len(loc), 1))])
        sol, *_ = np.linalg.lstsq(a, w, rcond=None)
        res = np.abs(a @ sol - w).max()
        if res > 1e-4:
            raise RuntimeError("oracle fit off by %g for %r" % (res, pid))
        return sol[:3], sol[3]

    def info(self, pid):
        w = self.world(pid)
        L, t = self.affine(pid)
        piv = np.zeros(3) if isinstance(pid, tuple) else np.array(hou.nodeBySessionId(pid).parmTuple("p").eval())
        return {"lo": w.min(0), "hi": w.max(0), "piv": piv @ L + t, "L": L, "t": t}


def val(info, which, k):
    return {"min": info["lo"][k], "max": info["hi"][k], "center": 0.5 * (info["lo"][k] + info["hi"][k]),
            "pivot": info["piv"][k]}[which]


def axes(info):
    return info["L"] / np.linalg.norm(info["L"], axis=1)[:, None]


def scales(info):
    return np.linalg.norm(info["L"], axis=1)


def raw(pids):
    """The stored values bit for bit: stash point attributes of the containers, object transform parameters."""
    out = {}
    for pid in pids:
        if isinstance(pid, tuple):
            g = containers.stash(hou.nodeBySessionId(pid[1])).geometry()
            out[pid[1]] = tuple(tuple(g.pointFloatAttribValues(a)) for a in ("P", "orient", "scale"))
        else:
            n = hou.nodeBySessionId(pid)
            out[pid] = tuple(n.parmTuple(k).eval() for k in ("t", "r", "s", "p", "pr", "scale"))
    return out


# --- the checks ----------------------------------------------------------------------------------------------------------
def fixture():
    hou.hipFile.clear(suppress_save_prompt=True)
    ca = containers.create("ca")
    with hou.undos.disabler():
        ca.parmTuple("t").set((3, 1, -2))
        ca.parmTuple("r").set((0, 30, 0))
        ca.parmTuple("s").set((1.5, 1.5, 1.5))
    ia = containers.add_pieces(ca, [(FILES[3], "src", xf((-4, 2, 1), (20, 35, -15), (10, 6, 8)))])[0]
    cb = containers.create("cb")
    with hou.undos.disabler():
        cb.parmTuple("t").set((-6, 0, 4))
        cb.parmTuple("r").set((10, -25, 5))
    ib = containers.add_pieces(cb, [(FILES[5], "tgt", xf((2, -1, 3), (-30, 10, 50), (7, 9, 5)))])[0]

    def box(name, size, centre, t, r, s, p, pr):
        n = hou.node("/obj").createNode("geo", name)
        b = n.createNode("box")
        b.parmTuple("size").set(size)
        b.parmTuple("t").set(centre)
        n.parmTuple("t").set(t)
        n.parmTuple("r").set(r)
        n.parmTuple("s").set(s)
        n.parmTuple("p").set(p)
        n.parmTuple("pr").set(pr)
        return n
    lo = box("loose", (2, 1, 3), (0.5, 0.2, -0.3), (5, 3, -7), (15, 40, -20), (1.2, 0.7, 1.5), (0.4, -0.3, 0.6), (0, 0, 0))
    to = box("target", (3, 2, 1), (-0.2, 0.4, 0.1), (-3, 5, 6), (-25, 60, 10), (1, 1.3, 0.8), (-0.5, 0.2, 0.3), (0, 0, 0))
    plane = hou.node("/obj").createNode("geo", "plane")
    plane.createNode("grid")
    plane.parmTuple("t").set((0, -20, 0))
    return {"pa": ("piece", ca.sessionId(), ia), "pb": ("piece", cb.sessionId(), ib), "lo": lo.sessionId(),
            "to": to.sessionId(), "plane": plane.sessionId()}


def close(a, b, tol=TOL):
    return bool(np.all(np.abs(np.asarray(a, dtype=float) - np.asarray(b, dtype=float)) <= tol))


def checks(out):
    f = fixture()
    orc = Oracle()
    src = [f["pa"], f["lo"]]

    def run(pids, target, opts):
        s = align.AlignSession(pids, target)
        s.update(opts)
        s.apply()
        return s

    # --- Align position: every Min/Center/Pivot/Max pair on every axis, two targets, two sources at once -----------
    ok_all, ok_other, bad = True, True, []
    for tg_pid in (f["pb"], f["to"]):
        tgt = orc.info(tg_pid)
        for k in range(3):
            for cur in POINTS:
                for tg in POINTS:
                    before = {p: orc.info(p) for p in src}
                    run(src, tg_pid, {"pos": {k: (cur, tg)}})
                    for p in src:
                        now = orc.info(p)
                        if abs(val(now, cur, k) - val(tgt, tg, k)) > TOL:
                            ok_all = False
                            bad.append((p, k, cur, tg, val(now, cur, k), val(tgt, tg, k)))
                        for j in range(3):
                            if j != k and abs(now["lo"][j] - before[p]["lo"][j]) > TOL:
                                ok_other = False
                    hou.undos.performUndo()
    out["pos_combos"] = ok_all
    out["pos_other_axes_unchanged"] = ok_other
    if bad:
        LOG.append("pos_combos first misses: %s" % bad[:3])
    mixed = {0: ("min", "max"), 1: ("pivot", "center"), 2: ("max", "min")}
    tgt = orc.info(f["to"])
    run(src, f["to"], {"pos": mixed})
    out["pos_mixed_axes"] = all(abs(val(orc.info(p), c, k) - val(tgt, t, k)) <= TOL
                                for p in src for k, (c, t) in mixed.items())
    hou.undos.performUndo()

    # --- orientation ---------------------------------------------------------------------------------------------------
    def orient_case(axes_on, tg_pid):
        before = {p: orc.info(p) for p in src}
        tgt = orc.info(tg_pid)
        run(src, tg_pid, {"orient": axes_on})
        now = {p: orc.info(p) for p in src}
        hou.undos.performUndo()
        return before, now, tgt

    ok_full, ok_two, ok_one, ok_keep = True, True, True, True
    for tg_pid in (f["pb"], f["to"]):
        b, n, t = orient_case((0, 1, 2), tg_pid)
        for p in src:
            ok_full &= close(np.sum(axes(n[p]) * axes(t), axis=1), 1.0, 1e-5)
            ok_keep &= close(scales(n[p]), scales(b[p])) and close(n[p]["piv"], b[p]["piv"])
        b, n, t = orient_case((0, 2), tg_pid)
        for p in src:
            ok_two &= close(np.sum(axes(n[p]) * axes(t), axis=1), 1.0, 1e-5)
        for k in range(3):
            b, n, t = orient_case((k,), tg_pid)
            for p in src:
                a0, a1, at = axes(b[p]), axes(n[p]), axes(t)
                rot = a0.T @ a1   # the turn between the two frames (row vectors)
                ang = np.degrees(np.arccos(np.clip((np.trace(rot) - 1) / 2, -1, 1)))
                want = np.degrees(np.arccos(np.clip(a0[k] @ at[k], -1, 1)))   # the shortest way
                ok_one &= abs(a1[k] @ at[k] - 1) < 1e-5 and abs(ang - want) < 1e-2
                ok_keep &= close(scales(n[p]), scales(b[p])) and close(n[p]["piv"], b[p]["piv"])
    out["orient_full"] = bool(ok_full)
    out["orient_two_axes"] = bool(ok_two)
    out["orient_one_axis"] = bool(ok_one)
    out["orient_keeps_pivot_and_scale"] = bool(ok_keep)

    # --- match scale ---------------------------------------------------------------------------------------------------
    ok_s, ok_rest = True, True
    for tg_pid in (f["pb"], f["to"]):
        t = orc.info(tg_pid)
        for on in ((0,), (1,), (2,), (0, 1, 2)):
            b = {p: orc.info(p) for p in src}
            run(src, tg_pid, {"scale": on})
            for p in src:
                n = orc.info(p)
                for k in range(3):
                    if k in on:
                        ok_s &= abs(scales(n)[k] - scales(t)[k]) <= TOL
                    else:
                        ok_rest &= abs(scales(n)[k] - scales(b[p])[k]) <= TOL
                ok_rest &= close(axes(n), axes(b[p]), 1e-5) and close(n["piv"], b[p]["piv"])
            hou.undos.performUndo()
    out["scale_match"] = bool(ok_s)
    out["scale_keeps_rest"] = bool(ok_rest)

    # --- quick align ---------------------------------------------------------------------------------------------------
    t = orc.info(f["to"])
    align.commit(align.quick([align.item(f["lo"])], align.item(f["to"])), "quick align")
    out["quick_single"] = close(orc.info(f["lo"])["piv"], t["piv"])
    hou.undos.performUndo()
    b = {p: orc.info(p) for p in src}
    align.commit(align.quick([align.item(p) for p in src], align.item(f["to"])), "quick align")
    n = {p: orc.info(p) for p in src}
    lo_ = np.min([n[p]["lo"] for p in src], 0)
    hi_ = np.max([n[p]["hi"] for p in src], 0)
    out["quick_multi"] = (close(0.5 * (lo_ + hi_), t["piv"])
                          and close(n[src[0]]["piv"] - n[src[1]]["piv"], b[src[0]]["piv"] - b[src[1]]["piv"]))
    hou.undos.performUndo()

    # --- hits: the nearest face under a world ray, its normal facing the ray ---------------------------------------------
    ok_hit = True
    for pid in (f["pa"], f["lo"], f["pb"]):
        info = orc.info(pid)
        c = 0.5 * (info["lo"] + info["hi"])
        for d in ((0.3, -1, 0.2), (-1, -0.2, 0.4), (0.1, 0.3, -1)):
            d = np.array(d) / np.linalg.norm(d)
            o = c - 40 * d
            h = align.hit_ray(o, d)
            node = hou.nodeBySessionId(pid[1] if isinstance(pid, tuple) else pid)
            og = orc._merge(node).geometry()   # world geometry: the hit there, independently
            pos, nrm, uvw = hou.Vector3(), hou.Vector3(), hou.Vector3()
            prim = og.intersect(hou.Vector3(o), hou.Vector3(d), pos, nrm, uvw)
            nrm = np.array(tuple(nrm)) * (-1 if np.dot(tuple(nrm), d) > 0 else 1)
            ok_hit &= (h is not None and prim >= 0 and h[0] == pid and close(tuple(h[1]), tuple(pos))
                       and close(tuple(h[2]), nrm / np.linalg.norm(nrm), 1e-4))
            if h is None or h[0] != pid or not close(tuple(h[1]), tuple(pos)) or not close(tuple(h[2]), nrm / np.linalg.norm(nrm), 1e-4):
                LOG.append("hit %r d %s: got %s want %s %s" % (pid, d, h, tuple(pos), nrm))
    out["hit_ray_matches"] = bool(ok_hit)
    h = align.hit_ray((0.3, -40, 0.2), (0, 1, 0))   # the grid's front (+Y) looks away from this ray
    out["hit_faces_ray"] = h is not None and h[0] == f["plane"] and close(tuple(h[2]), (0, -1, 0), 1e-6)

    # --- normal align: the loose box's top face onto the target box's +X face --------------------------------------------
    def face(pid, centre_local, n_local):
        L, t_ = orc.affine(pid)
        p = np.array(centre_local) @ L + t_
        n_ = np.array(n_local) @ np.linalg.inv(L).T   # normals: inverse transpose
        return p, n_ / np.linalg.norm(n_)

    top_l = ((0.5, 0.2 + 0.5, -0.3), (0, 1, 0))      # loose box: size (2,1,3) about (0.5,0.2,-0.3)
    side_t = ((-0.2 + 1.5, 0.4, 0.1), (1, 0, 0))     # target box: size (3,2,1) about (-0.2,0.4,0.1)

    def hit_face(pid, fc):
        p, n_ = face(pid, *fc)
        h = align.hit_ray(p + 0.3 * n_, -n_)
        return h, p, n_

    def normal_run(src_pids, src_hit, tgt_hit, offset, angle, flip):
        s = align.NormalSession(src_pids, src_hit, tgt_hit)
        s.update(offset, angle, flip)
        s.apply()

    hs, ps, ns = hit_face(f["lo"], top_l)
    ht, pt, nt = hit_face(f["to"], side_t)
    good_hits = hs is not None and ht is not None and hs[0] == f["lo"] and ht[0] == f["to"]
    off = 0.25
    normal_run([f["lo"]], hs, ht, off, 0.0, False)
    p2, n2 = face(f["lo"], *top_l)
    out["normal_align_object"] = bool(good_hits and close(p2, pt + off * nt) and abs(n2 @ nt + 1) < 1e-5)
    x0 = np.array((1.0, 0, 0)) @ orc.affine(f["lo"])[0]
    hou.undos.performUndo()
    normal_run([f["lo"]], hs, ht, off, 30.0, False)
    p3, n3 = face(f["lo"], *top_l)
    x1 = np.array((1.0, 0, 0)) @ orc.affine(f["lo"])[0]
    x0p, x1p = x0 - (x0 @ nt) * nt, x1 - (x1 @ nt) * nt
    ang = np.degrees(np.arctan2(np.cross(x0p, x1p) @ nt, x0p @ x1p))
    out["normal_spin"] = bool(close(p3, pt + off * nt) and abs(n3 @ nt + 1) < 1e-5 and abs(ang - 30.0) < 1e-3)
    hou.undos.performUndo()
    normal_run([f["lo"]], hs, ht, 0.0, 0.0, True)
    p4, n4 = face(f["lo"], *top_l)
    out["normal_flip"] = bool(close(p4, pt) and abs(n4 @ nt - 1) < 1e-5)
    hou.undos.performUndo()
    # a piece in a moved, rotated, scaled container as the source, the piece and the object moving together
    info = orc.info(f["pa"])
    c = 0.5 * (info["lo"] + info["hi"])
    hp = align.hit_ray(c + np.array((0, 40.0, 0)), (0, -1, 0))
    La, ta = orc.affine(f["pa"])
    loc_p = (np.array(tuple(hp[1])) - ta) @ np.linalg.inv(La)          # the hit in the piece's own space
    loc_n = np.array(tuple(hp[2])) @ La.T                                # its normal there (inverse of inv-transpose)
    lo_rel = orc.info(f["lo"])["piv"] - info["piv"]
    normal_run([f["pa"], f["lo"]], hp, ht, 0.1, 0.0, False)
    La2, ta2 = orc.affine(f["pa"])
    p5 = loc_p @ La2 + ta2
    n5 = loc_n @ np.linalg.inv(La2).T
    n5 /= np.linalg.norm(n5)
    rel_now = orc.info(f["lo"])["piv"] - orc.info(f["pa"])["piv"]
    out["normal_align_piece"] = bool(hp[0] == f["pa"] and close(p5, pt + 0.1 * nt) and abs(n5 @ nt + 1) < 1e-5
                                 and abs(np.linalg.norm(rel_now) - np.linalg.norm(lo_rel)) < TOL)
    hou.undos.performUndo()

    # --- preview, Apply, Cancel ----------------------------------------------------------------------------------------
    opts = {"pos": mixed, "orient": (1,), "scale": (0,)}
    r0, u0 = raw(src), len(hou.undos.undoLabels())
    w0 = {p: orc.world(p) for p in src}
    s = align.AlignSession(src, f["to"])
    s.update(opts)
    moved = all(not close(orc.world(p), w0[p]) for p in src)
    out["preview_no_undo"] = moved and len(hou.undos.undoLabels()) == u0
    s.cancel()
    out["cancel_exact"] = moved and raw(src) == r0 and len(hou.undos.undoLabels()) == u0
    s = align.AlignSession(src, f["to"])
    s.update(opts)
    want = {p: orc.world(p) for p in src}
    s.apply()
    labels = hou.undos.undoLabels()
    out["apply_one_undo"] = (len(labels) == u0 + 1 and labels[0] == "modelUI: align"
                             and all(close(orc.world(p), want[p]) for p in src))
    hou.undos.performUndo()
    out["apply_undo_exact"] = raw(src) == r0
    return out


def mutate(mod, old, new):
    path = mod.__file__
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if src.count(old) != 1:
        raise RuntimeError("mutation snippet not found exactly once: %r" % old)
    exec(compile(src.replace(old, new), path, "exec"), mod.__dict__)
    return lambda: exec(compile(src, path, "exec"), mod.__dict__)


A = align
MUTATIONS = [   # (name, check, module, old, new)
    ("min_is_max", "pos_combos", A, '{"min": lo[k], "max": hi[k]', '{"min": hi[k], "max": hi[k]'),
    ("center_is_min", "pos_combos", A, '"center": 0.5 * (lo[k] + hi[k])}', '"center": lo[k]}'),
    ("object_pivot_origin", "pos_combos", A, '    return hou.Vector3(hou.nodeBySessionId(pid).parmTuple("p").eval())', "    return hou.Vector3(0, 0, 0)"),
    ("box_from_local_corners", "pos_combos", A, '    w = _pts_world(it["pts"], m)',
     '    p_ = it["pts"]\n    w = _pts_world(np.array([[x, y, z] for x in (p_[:, 0].min(), p_[:, 0].max()) for y in (p_[:, 1].min(), p_[:, 1].max()) for z in (p_[:, 2].min(), p_[:, 2].max())]), m)'),
    ("all_like_first", "pos_combos", A, '    return {it["pid"]: aligned(it, tgt, opts) for it in items}', '    return {it["pid"]: aligned(items[0], tgt, opts) for it in items}'),
    ("pos_wrong_axis", "pos_other_axes_unchanged", A, "        d[k] = value(tgt, tg, k) - value(it, cur, k, m)", "        d[(k + 1) % 3] = value(tgt, tg, k) - value(it, cur, k, m)"),
    ("one_choice_for_all_axes", "pos_mixed_axes", A, "        d[k] = value(tgt, tg, k) - value(it, cur, k, m)",
     '        cur, tg = opts["pos"][min(opts["pos"])]\n        d[k] = value(tgt, tg, k) - value(it, cur, k, m)'),
    ("orient_ignores_target", "orient_full", A, "        rn = rt\n", "        rn = rs\n"),
    ("two_axes_as_one", "orient_two_axes", A, "    if len(axes) >= 2:\n        rn = rt", "    if len(axes) >= 3:\n        rn = rt"),
    ("one_axis_full_match", "orient_one_axis", A, "    if len(axes) >= 2:\n        rn = rt", "    if len(axes) >= 1:\n        rn = rt"),
    ("orient_pivot_moves", "orient_keeps_pivot_and_scale", A, "    return lin * hou.hmath.buildTranslate(piv * m_old - piv * lin)", "    return lin * hou.hmath.buildTranslate(m_old.extractTranslates())"),
    ("orient_drops_scale", "orient_keeps_pivot_and_scale", A, "    return _keep_pivot(_lin(m) * rs.inverted() * rn, m, piv)", "    return _keep_pivot(rn, m, piv)"),
    ("scale_wrong_axis", "scale_match", A, "        f[k] = _row(lt, k).length() / s if s > 1e-12 else 1.0", "        f[(k + 1) % 3] = _row(lt, k).length() / s if s > 1e-12 else 1.0"),
    ("scale_all_axes", "scale_keeps_rest", A, "    for k in axes:\n        s = _row(lin, k).length()", "    for k in range(3):\n        s = _row(lin, k).length()"),
    ("quick_single_by_centre", "quick_single", A, "    src = world_pivot(items[0]) if len(items) == 1 else selection_centre(items)", "    src = selection_centre(items)"),
    ("quick_multi_first_pivot", "quick_multi", A, "    src = world_pivot(items[0]) if len(items) == 1 else selection_centre(items)", "    src = world_pivot(items[0])"),
    ("hit_point_local", "hit_ray_matches", A, "        w = pos * m\n", "        w = pos\n"),
    ("hit_normal_forward", "hit_ray_matches", A, "        nw = hou.Vector4(nrm[0], nrm[1], nrm[2], 0.0) * inv.transposed()", "        nw = hou.Vector4(nrm[0], nrm[1], nrm[2], 0.0) * m"),
    ("packed_normal_used", "hit_ray_matches", A, "            if pr.getEmbeddedGeometry().intersect(o2, d2, pos, nrm, uvw) < 0:\n                continue",
     "            inv = n.worldTransform().inverted()"),
    ("hit_backface_kept", "hit_faces_ray", A, "        if nw.dot(d) > 0:   # the side", "        if False:   # the side"),
    ("normals_same_way", "normal_align_object", A, "    turn = ns.matrixToRotateTo(nt if flip else -nt)", "    turn = ns.matrixToRotateTo(-nt if flip else nt)"),
    ("offset_ignored", "normal_align_object", A, "hou.Vector3(pt) + nt * offset)", "hou.Vector3(pt) + nt * 0.0)"),
    ("spin_ignored", "normal_spin", A, "    spin = hou.hmath.buildRotateAboutAxis(nt, angle)", "    spin = hou.hmath.buildRotateAboutAxis(nt, 0.0)"),
    ("flip_ignored", "normal_flip", A, "    turn = ns.matrixToRotateTo(nt if flip else -nt)", "    turn = ns.matrixToRotateTo(-nt)"),
    ("normal_delta_first", "normal_align_piece", A, '        self.preview({it["pid"]: it["m"] * d for it in self.items})', '        self.preview({it["pid"]: d * it["m"] for it in self.items})'),
    ("preview_recorded", "preview_no_undo", A, "    def preview(self, xforms):\n        with hou.undos.disabler():", '    def preview(self, xforms):\n        with hou.undos.group("modelUI: preview"):'),
    ("cancel_no_restore", "cancel_exact", A, "        self.done = True\n        _restore(self.snap)\n\n\nclass AlignSession", "        self.done = True\n\n\nclass AlignSession"),
    ("apply_split", "apply_one_undo", A, '    with hou.undos.group("modelUI: " + label):\n        pieces_ui.set_xforms(xforms)', "    if True:\n        pieces_ui.set_xforms(xforms)"),
    ("apply_on_preview", "apply_undo_exact", A, "        self.done = True\n        _restore(self.snap)\n        if self.last:", "        self.done = True\n        if self.last:"),
]


def run():
    out = {}
    try:
        checks(out)
    except Exception as e:  # noqa: BLE001 - an exception is a red check; the checks before it keep their values
        import traceback
        out["_exception"] = "%s: %s" % (type(e).__name__, e)
        LOG.append(traceback.format_exc())
    return out


def main():
    only = os.environ.get("PF_ALIGN_ONLY")
    base = run()
    bad = [k for k, v in base.items() if v is not True]
    for k, v in base.items():
        print("%-32s %s" % (k, "ok" if v is True else "RED %s" % v))
    for line in LOG:
        print("  ", line)
    names = set(base) - {"_exception"}
    for name, check, mod, old, new in MUTATIONS:
        if only and name not in only.split(","):
            names.discard(check)
            continue
        del LOG[:]
        restore = mutate(mod, old, new)
        try:
            res = run()
        finally:
            restore()
        red = res.get(check) is False   # credited only when the paired check itself evaluated False
        print("mutation %-26s -> %-30s %s" % (name, check, "red (good)" if red else "NOT RED %s" % res.get("_exception", res.get(check))))
        if not red:
            bad.append("mutation " + name)
            for line in LOG[-3:]:
                print("    ", line[-600:])
        names.discard(check)
    if names:
        print("checks without a mutation:", sorted(names))
        bad.append("unpaired checks")
    print("FAIL" if bad else "PASS", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
