"""Shared helpers for tests/spacetools (hython). Throwaway sessions, never saves a .hip."""
import os
import sys

import hou

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
OTLS = os.path.join(ROOT, "polyfactory", "otls")
WORK = "F:/cache/spacetools/plating_work"


def fresh():
    hou.hipFile.clear(suppress_save_prompt=True)
    return hou.node("/obj").createNode("geo")


def install(name):
    hou.hda.installFile(os.path.join(OTLS, name + ".hda").replace("\\", "/"), force_use_assets=True)


def cook(n):
    """Cook and return geometry; any error/warning is a test failure."""
    try:
        n.cook(force=True)
    except hou.OperationFailed:
        pass
    allnodes = [n] + (list(n.allSubChildren()) if hasattr(n, "allSubChildren") else [])
    bad = [(c.path(), c.errors(), c.warnings()) for c in allnodes if c.errors() or c.warnings()]
    if bad:
        raise AssertionError("cook issues: %r" % (bad[:3],))
    return n.geometry()


# ---- fixtures ------------------------------------------------------------
def fx_grid(g, n=11, size=4.0):
    s = g.createNode("grid"); s.parmTuple("size").set((size, size)); s.parm("rows").set(n); s.parm("cols").set(n)
    return s


def fx_sphere(g):
    s = g.createNode("sphere"); s.parm("type").set(2); s.parmTuple("rad").set((1, 1, 1))
    s.parm("freq").set(8) if s.parm("freq") else None
    s.parm("rows").set(16); s.parm("cols").set(32); s.parm("orient").set(1)
    return s


def fx_box(g):
    b = g.createNode("box"); b.parmTuple("size").set((2, 1, 1.5)); return b


def fx_nonconvex(g):
    """L-shaped solid (concave 6-gon caps): ngons, concave faces, consistent outward normals."""
    py = g.createNode("python")
    py.parm("python").set("""
geo = hou.pwd().geometry()
pts = [(0,0),(3,0),(3,1),(1,1),(1,3),(0,3)]
ps = [geo.createPoint() for _ in pts]
for p, (x, z) in zip(ps, pts):
    p.setPosition((x, 0, z))
poly = geo.createPolygon()
for p in ps: poly.addVertex(p)
if poly.normal()[1] < 0:
    poly.reverse()
""")
    ex = g.createNode("polyextrude::2.0"); ex.setInput(0, py)
    ex.parm("dist").set(0.8); ex.parm("outputback").set(1)
    return ex


def fx_non_quad(g):
    """Triangulated sphere: tests the 'no quads at all' path."""
    s = fx_sphere(g)
    t = g.createNode("divide"); t.setInput(0, s); t.parm("convex").set(1); t.parm("numsides").set(3)
    return t


def dump_obj(geo, path, group=None):
    prims = geo.prims()
    with open(path, "w") as f:
        for p in geo.points():
            x, y, z = p.position(); f.write("v %f %f %f\n" % (x, y, z))
        for pr in prims:
            if group and not group.contains(pr):
                continue
            f.write("f " + " ".join(str(v.point().number() + 1) for v in pr.vertices()) + "\n")


def render_png(geo, path, size=900, view=(35, -30), color_attr=None, title=""):
    """Tiny painter's-algorithm projection with matplotlib (shaded flat polys)."""
    import numpy as np
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import PolyCollection
    pos = np.array([list(p.position()) for p in geo.points()]) if geo.points() else np.zeros((0, 3))
    ry, rx = np.radians(view[1]), np.radians(view[0])
    Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
    Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
    q = pos @ Ry.T @ Rx.T
    polys, depth, cols = [], [], []
    light = np.array([0.4, 0.8, 0.5]); light /= np.linalg.norm(light)
    hascd = geo.findPrimAttrib("Cd") is not None
    for pr in geo.prims():
        idx = [v.point().number() for v in pr.vertices()]
        if len(idx) < 3:
            continue
        pts = q[idx]
        n = np.cross(pts[1] - pts[0], pts[2] - pts[0])
        ln = np.linalg.norm(n)
        shade = 0.35 + 0.65 * abs(float(n @ light) / ln) if ln > 0 else 0.5
        base = np.array(pr.attribValue("Cd")) if hascd else np.array([0.75, 0.78, 0.85])
        polys.append(pts[:, :2]); depth.append(pts[:, 2].mean()); cols.append(np.clip(base * shade, 0, 1))
    order = np.argsort(depth)
    fig = plt.figure(figsize=(size / 100, size / 100), dpi=100)
    ax = fig.add_axes([0, 0, 1, 1]); ax.set_aspect("equal"); ax.axis("off")
    pc = PolyCollection([polys[i] for i in order], facecolors=[cols[i] for i in order], edgecolors=(0, 0, 0, 0.35), linewidths=0.3)
    ax.add_collection(pc)
    if len(pos):
        ax.set_xlim(q[:, 0].min() - 0.1, q[:, 0].max() + 0.1); ax.set_ylim(q[:, 1].min() - 0.1, q[:, 1].max() + 0.1)
    if title:
        ax.text(0.02, 0.97, title, transform=ax.transAxes, va="top", fontsize=10)
    fig.savefig(path); plt.close(fig)
    return len(polys)
