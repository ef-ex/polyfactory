"""Dev helper: perspective view of our equirect (houdini convention) with the sample .blend camera, to compare against a Blender/EEVEE render.
hython tests/spacetools/persp_from_equirect.py <equirect.exr> <out.exr> [w h]"""
import sys, numpy as np
sys.path.insert(0, "F:/projects/polyfactory-spacetools/polyfactory/scripts/python")
from polyfactory.spacetools import bake, sky
img = bake.read_exr(sys.argv[1])
w, h = (int(sys.argv[3]), int(sys.argv[4])) if len(sys.argv) > 4 else (960, 540)
rx, ry, rz = 1.6593619585037231, 1.6364525663448148e-06, -7.146590232849121
def R(x, y, z):
    cx, sx, cy, sy, cz, sz = np.cos(x), np.sin(x), np.cos(y), np.sin(y), np.cos(z), np.sin(z)
    Rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]]); Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]); Rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return Rz @ Ry @ Rx
M = R(rx, ry, rz)
t = 1.0                                              # tan(fov/2): lens 18 on 36 mm sensor
u = (np.arange(w) + 0.5) / w * 2 - 1; v = 1 - (np.arange(h) + 0.5) / h * 2
U, V = np.meshgrid(u * t, v * t * h / w)
d = np.stack([U, V, -np.ones_like(U)], -1) @ M.T
d /= np.linalg.norm(d, axis=-1, keepdims=True)
out = sky.sample_equirect(img, d.astype(np.float32), 0)
bake.write_exr(sys.argv[2], out.astype(np.float32))
