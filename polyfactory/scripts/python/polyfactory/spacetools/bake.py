"""Bake a COP node that follows the spacetools layout contract to EXR (equirect, 6 faces, cross).

Contract for the node (pf_space_direction and every consumer HDA): int parms `layout` (0 equirect,
1 cross, 2 face), `face` (0..5), `res` (face size N); the image to bake is output `layer_index`.
Use from hython:  bake.bake_set(node, "F:/cache/out", "nebula_a", res=1024)
"""
import os
import numpy as np
import OpenEXR

from . import sky


def layer_array(node, layer_index=0):
    """Cook and return the node's output layer as float32 (H, W, C), row 0 = top (EXR order)."""
    node.cook(force=True)
    L = node.layer(layer_index)
    w, h = L.bufferResolution()
    c = L.channelCount()
    a = np.frombuffer(L.allBufferElements(), dtype=np.float32).reshape(h, w, c)
    return np.ascontiguousarray(a[::-1])               # COP buffers start at the bottom row


def write_exr(path, arr, half=False):
    """Float EXR, ZIP compressed. 1 channel -> Y, 3 -> RGB, 4 -> RGBA."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    a = arr.astype(np.float16 if half else np.float32)
    name = {1: "Y", 3: "RGB", 4: "RGBA"}[a.shape[2]]
    if a.shape[2] == 1:
        a = a[..., 0]
    OpenEXR.File({"compression": OpenEXR.ZIP_COMPRESSION}, {name: a}).write(path)


def read_exr(path):
    ch = OpenEXR.File(path).channels()
    k = next(iter(ch))
    a = ch[k].pixels
    return (a[..., None] if a.ndim == 2 else a).astype(np.float32)


def bake_set(node, outdir, name, res, layouts=("equirect", "faces", "cross"), layer_index=0, half=False):
    """Set layout/face/res on `node`, cook and write EXRs. Returns {tag: path}. Restores the parms."""
    old = {p: node.parm(p).eval() for p in ("layout", "face", "res")}
    out = {}
    try:
        node.parm("res").set(res)
        jobs = []
        if "equirect" in layouts:
            jobs.append(("equirect", 0, 0))
        if "cross" in layouts:
            jobs.append(("cross", 1, 0))
        if "faces" in layouts:
            jobs += [(sky.FACE_NAMES[f], 2, f) for f in range(6)]
        for tag, lay, face in jobs:
            node.parm("layout").set(lay)
            node.parm("face").set(face)
            path = os.path.join(outdir, "%s_%s.exr" % (name, tag)).replace("\\", "/")
            write_exr(path, layer_array(node, layer_index), half)
            out[tag] = path
    finally:
        for p, v in old.items():
            node.parm(p).set(v)
    return out


def check_set(paths, conv=0):
    """Numeric seam check of a baked set (needs equirect + 6 faces; cross optional). Returns a dict of numbers."""
    equi = read_exr(paths["equirect"])
    faces = [read_exr(paths[n]) for n in sky.FACE_NAMES]
    r = {"finite": bool(all(np.isfinite(x).all() for x in [equi] + faces))}
    r["equirect_vs_faces_mean_p999"] = sky.equirect_vs_faces(equi, faces, conv)
    ec = sky.edge_continuity(faces)
    r["edge_ratio_max"] = max(ec.values())
    r["edge_ratio_median"] = float(np.median(list(ec.values())))
    if "cross" in paths:
        cr = read_exr(paths["cross"])
        cf = sky.cross_to_faces(cr)
        r["cross_vs_faces_maxdiff"] = float(max(np.abs(a - b).max() for a, b in zip(cf, faces)))
    return r
