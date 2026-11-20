"""Numpy reference for the pf_space_direction layouts (independent oracle for the OpenCL kernel),
plus cube/equirect samplers and the seam checks. No hou import. Images are (H, W, C) float32, row 0 = top.

Layout numbers: 0 equirect (4N x 2N), 1 cube cross (4N x 3N), 2 single face (N x N).
Faces: 0..5 = +X -X +Y -Y +Z -Z (OpenGL cube-face orientation). Convention: 0 houdini (Karma/USD lat-long), 1 godot: the same equirect mapping (centre +Z, +X at u=0.25).
"""
import numpy as np

FACE_NAMES = ("px", "nx", "py", "ny", "pz", "nz")
# cross cell (col,row) -> face, for the 4x3 horizontal cross
CROSS_CELLS = {(1, 0): 2, (0, 1): 1, (1, 1): 4, (2, 1): 0, (3, 1): 5, (1, 2): 3}


def face_dir(face, a, b):
    """a right, b down in [-1,1] (arrays ok) -> unit direction (..., 3)."""
    one = np.ones_like(a)
    d = {0: (one, -b, -a), 1: (-one, -b, a), 2: (a, one, b), 3: (a, -one, -b), 4: (a, -b, one), 5: (-a, -b, -one)}[face]
    d = np.stack(d, -1)
    return d / np.linalg.norm(d, axis=-1, keepdims=True)


def pixel_dirs(layout, N, face=0, conv=0):
    """(H, W, 3) directions and (H, W) mask for a layout, row 0 = top."""
    if layout == 0:
        W, H = 4 * N, 2 * N
        u = (np.arange(W) + 0.5) / W
        v = (np.arange(H) + 0.5) / H
        phi = u * 2 * np.pi   # conv 0 (Houdini/Karma) == conv 1 (Godot): OpenEXR/USD lat-long, centre +Z
        th = v * np.pi
        s = np.sin(th)[:, None]
        d = np.stack([s * np.sin(phi)[None], np.cos(th)[:, None] + 0 * phi[None], -s * np.cos(phi)[None]], -1)
        return d.astype(np.float32), np.ones((H, W), np.float32)
    ab = (np.arange(N) + 0.5) / N * 2 - 1
    a, b = np.meshgrid(ab, ab)
    if layout == 2:
        return face_dir(face, a, b).astype(np.float32), np.ones((N, N), np.float32)
    d = np.zeros((3 * N, 4 * N, 3), np.float32)
    m = np.zeros((3 * N, 4 * N), np.float32)
    for (cx, cy), f in CROSS_CELLS.items():
        d[cy * N:(cy + 1) * N, cx * N:(cx + 1) * N] = face_dir(f, a, b)
        m[cy * N:(cy + 1) * N, cx * N:(cx + 1) * N] = 1
    return d, m


def dir_to_face(d):
    """-> (face index array, a, b) with a,b in [-1,1]."""
    ax = np.abs(d)
    m = ax.max(-1)
    k = ax.argmax(-1)
    x, y, z = d[..., 0], d[..., 1], d[..., 2]
    sgn = np.take_along_axis(d, k[..., None], -1)[..., 0] >= 0
    face = np.where(k == 0, np.where(sgn, 0, 1), np.where(k == 1, np.where(sgn, 2, 3), np.where(sgn, 4, 5)))
    a = np.select([face == 0, face == 1, face == 2, face == 3, face == 4, face == 5], [-z, z, x, x, x, -x]) / m
    b = np.select([face == 0, face == 1, face == 2, face == 3, face == 4, face == 5], [-y, -y, z, -z, -y, -y]) / m
    return face, a, b


def _bilinear(img, fx, fy, wrapx=False):
    """img (H,W,C); fx,fy float pixel coords of the sample point (pixel centres at i+0.5)."""
    H, W = img.shape[:2]
    x = fx - 0.5; y = fy - 0.5
    x0 = np.floor(x).astype(int); y0 = np.floor(y).astype(int)
    tx = (x - x0)[..., None]; ty = (y - y0)[..., None]
    def g(xi, yi):
        xi = xi % W if wrapx else np.clip(xi, 0, W - 1)
        return img[np.clip(yi, 0, H - 1), xi]
    return (g(x0, y0) * (1 - tx) * (1 - ty) + g(x0 + 1, y0) * tx * (1 - ty) +
            g(x0, y0 + 1) * (1 - tx) * ty + g(x0 + 1, y0 + 1) * tx * ty)


def sample_equirect(img, d, conv=0):
    H, W = img.shape[:2]
    u = np.arctan2(d[..., 0], -d[..., 2]) / (2 * np.pi) + (0.5 if conv == 2 else 0.0)   # conv 2 = the old Houdini guess (centre -Z): only used as a 'wrong yaw' mutant
    u = u % 1.0
    v = np.arccos(np.clip(d[..., 1], -1, 1)) / np.pi
    return _bilinear(img, u * W, v * H, wrapx=True)


def sample_cube(faces, d):
    """faces: list of 6 (N,N,C) arrays; d: (...,3) directions. Bilinear inside a face (clamped at its edge)."""
    N = faces[0].shape[0]
    f, a, b = dir_to_face(d)
    out = np.zeros(d.shape[:-1] + (faces[0].shape[2],), np.float32)
    for i in range(6):
        sel = f == i
        if sel.any():
            out[sel] = _bilinear(faces[i], (a[sel] + 1) / 2 * N, (b[sel] + 1) / 2 * N)
    return out


def cross_to_faces(cross):
    N = cross.shape[0] // 3
    faces = [None] * 6
    for (cx, cy), f in CROSS_CELLS.items():
        faces[f] = cross[cy * N:(cy + 1) * N, cx * N:(cx + 1) * N]
    return faces


def edge_continuity(faces):
    """For each of the 12 cube edges: mean |edge pixel of A - nearest pixel of neighbour B| divided by
    mean |edge pixel of A - its own inner neighbour|. ~1 = continuous, >>1 (or nan) = misoriented / seam."""
    N = faces[0].shape[0]
    ab = (np.arange(N) + 0.5) / N * 2 - 1
    e = 1.0 + 1.0 / N                                   # half a pixel beyond the face edge, in a/b units
    res = {}
    for fa in range(6):
        A = faces[fa]
        for side in ("L", "R", "T", "B"):
            if side == "L":   a, b, edge, inner = -e * np.ones(N), ab, A[:, 0], A[:, 1]
            elif side == "R": a, b, edge, inner = e * np.ones(N), ab, A[:, -1], A[:, -2]
            elif side == "T": a, b, edge, inner = ab, -e * np.ones(N), A[0], A[1]
            else:             a, b, edge, inner = ab, e * np.ones(N), A[-1], A[-2]
            d = face_dir(fa, a, b)                      # lies just beyond the edge -> in the neighbour face
            nb, na, nbb = dir_to_face(d)
            fb = int(nb[0])
            assert (nb == fb).all()
            B = _bilinear(faces[fb], (na + 1) / 2 * N, (nbb + 1) / 2 * N)
            own = np.abs(edge - inner).mean() + 1e-12
            res[(FACE_NAMES[fa], side, FACE_NAMES[fb])] = float(np.abs(edge - B).mean() / own)
    return res


def equirect_vs_faces(equi, faces, conv=0):
    """Resample the equirect at every cube-face pixel direction and compare to the face pixel.
    Returns (mean abs diff, 99.9th percentile abs diff) over all faces and channels."""
    N = faces[0].shape[0]
    diffs = []
    for f in range(6):
        d, _ = pixel_dirs(2, N, face=f)
        diffs.append(np.abs(sample_equirect(equi, d, conv) - faces[f]).ravel())
    diffs = np.concatenate(diffs)
    return float(diffs.mean()), float(np.percentile(diffs, 99.9))


def ensure_preview(cop):
    """GUI only (so hython tests stay clean): make /obj/<cop name>_sky_preview with a pf::sky_preview pointing at `cop`,
    unless one already points at it. Returns the SOP or None."""
    import hou
    if not hou.isUIAvailable() or cop.isInsideLockedHDA() or hou.node("/obj") is None:
        return None
    for g in hou.node("/obj").children():
        for c in g.children():
            if c.type().name().startswith("pf::sky_preview") and c.parm("cop").eval() == cop.path():
                return c
    g = hou.node("/obj").createNode("geo", cop.name() + "_sky_preview")
    for c in g.children():
        c.destroy()
    s = g.createNode("pf::sky_preview", "sky_preview")
    s.parm("cop").set(cop.path())
    s.setDisplayFlag(True)
    s.setRenderFlag(True)
    return s
