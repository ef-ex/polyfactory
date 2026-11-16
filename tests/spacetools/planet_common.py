"""Shared helpers for the pf_custom_planet checks (hython, throwaway session, never saves a hip)."""
import os, sys
import numpy as np
import hou

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HDA = ROOT + "/polyfactory/otls/pf_custom_planet.hda"
sys.path.insert(0, ROOT + "/devScripts")
sys.path.insert(0, ROOT + "/polyfactory/scripts/python")
import pf_custom_planet_module as M  # noqa: E402
from polyfactory.spacetools import bake, sky  # noqa: E402
SCRATCH = "F:/cache/spacetools/planet_work"
LIB = M.DEFAULT_DIR
BLENDER = "F:/ai/blender/blender-4.5.16-windows-x64/blender.exe"


def make_node(params=None):
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(HDA)
    n = hou.node("/img").createNode("copnet", "t").createNode("pf_custom_planet", "p")
    for k, v in (params or {}).items():
        (n.parmTuple(k) if isinstance(v, (list, tuple)) else n.parm(k)).set(v)
    return n


def cook_clean(n):
    """Cook and return; any error/warning anywhere inside is a failure."""
    n.cook(force=True)
    bad = [(c.path(), c.errors(), c.warnings()) for c in [n] + list(n.allSubChildren()) if c.errors() or c.warnings()]
    return bad


def layer(n, i):
    return bake.layer_array(n, i)       # (H, W, C), row 0 = top


def tonemap(a):
    a = np.clip(a[..., :3], 0, None)
    a = a / (1 + 0.15 * a)
    return (np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055).clip(0, 1) * 255).astype(np.uint8)


def sphere_view(equi, V, size=256, light=(0.5, 0.4, 0.8), conv=0):
    """Orthographic render of an equirect map seen from direction V (up = +Y), lambert-lit: the independent preview."""
    V = np.asarray(V, float); V /= np.linalg.norm(V)
    right = np.cross(-V, (0, 1, 0)); right /= np.linalg.norm(right)
    up = np.cross(right, -V)
    yy, xx = np.mgrid[0:size, 0:size]
    x = (xx + 0.5) / size * 2 - 1; y = 1 - (yy + 0.5) / size * 2
    r2 = x * x + y * y; ins = r2 < 1
    z = np.sqrt(np.clip(1 - r2, 0, 1))
    d = x[..., None] * right + y[..., None] * up + z[..., None] * V
    col = sky.sample_equirect(equi, d, conv)[..., :3]
    L = np.asarray(light, float); L = L[0] * right + L[1] * up + L[2] * V; L /= np.linalg.norm(L)
    lam = np.clip((d * L).sum(-1), 0, 1) * 0.9 + 0.1
    out = col * lam[..., None] * ins[..., None]
    return out
