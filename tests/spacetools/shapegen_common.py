"""Shared helpers for the Shape Generator checks (hython): Blender-operator kwargs -> HDA parms, measuring a cooked result."""
import math
import numpy as np
import hou

RENAME = {"prevent_ovelapping_faces": "prevent_overlap", "favour_vec": "favour"}
TOKEN = {"INTERSECT": "intersect", "UNION": "union", "DIFFERENCE": "difference", "OFFSET": "offset", "WIDTH": "width", "DEPTH": "depth",
         "PERCENT": "percent", "CATMULL_CLARK": "catmull_clark", "SIMPLE": "simple"}
ROT = ("rotation", "start_rand_rotation", "end_rand_rotation")


def apply_blender_params(node, kw):
    """Set the HDA to what the add-on's operator would use for `kw` (Blender property names, radians)."""
    for k, v in kw.items():
        k = RENAME.get(k, k)
        t = node.parmTuple(k)
        if t is None:
            continue
        if isinstance(v, str):
            v = TOKEN.get(v, v)
            node.parm(k).set(v)
        elif isinstance(v, (list, tuple)):
            vv = [math.degrees(x) for x in v] if k in ROT else list(v)[:len(t)]
            t.set(vv)
        else:
            node.parm(k).set(int(v) if isinstance(v, bool) else v)


def cook(node):
    try:
        node.cook(force=True)
    except hou.OperationFailed:
        pass
    bad = [(c.path(), c.errors(), c.warnings()) for c in [node] + list(node.allSubChildren()) if c.errors() or c.warnings()]
    return node.geometry(), bad


def objects(geo):
    """{pf_obj: (P (n,3), faces list of point-index lists)} in world space."""
    P = np.array([p.position() for p in geo.points()]) if geo.points() else np.zeros((0, 3))
    out = {}
    for pr in geo.prims():
        out.setdefault(pr.attribValue("pf_obj"), []).append([v.point().number() for v in pr.vertices()])
    return P, out


def measure(geo):
    """Same numbers as shapegen_ref_blender_full.measure() (volume sign: Houdini winds outward faces clockwise, so the signed volume is negated): n objects, sum volume / area, union bbox, triangles, non-manifold edges."""
    P, objs = objects(geo)
    vol = area = 0.0; tris = 0; nonman = 0
    used = set()
    for faces in objs.values():
        edges = {}
        for f in faces:
            tris += len(f) - 2
            a = P[f[0]]
            for i in range(1, len(f) - 1):
                b, c = P[f[i]], P[f[i + 1]]
                vol += float(np.dot(a, np.cross(b, c))) / 6.0
                area += float(np.linalg.norm(np.cross(b - a, c - a))) / 2.0
            for i in range(len(f)):
                e = (f[i], f[(i + 1) % len(f)])
                edges[e] = edges.get(e, 0) + 1
            used.update(f)
        nonman += sum(1 for e, c in edges.items() if c != 1 or (e[1], e[0]) not in edges)
    size = (P[sorted(used)].max(0) - P[sorted(used)].min(0)).tolist() if used else [0, 0, 0]
    return dict(n=len(objs), vol=-vol, area=area, tris=tris, nonman=nonman // 2 if nonman else 0, size=size)
