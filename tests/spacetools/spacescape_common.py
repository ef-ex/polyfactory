"""Shared helpers for the pf_spacescape checks (run under hython, throwaway session, never saves a hip)."""
import os, sys
import numpy as np
import hou

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HDA = ROOT + "/polyfactory/otls/pf_spacescape.hda"
sys.path.insert(0, ROOT + "/devScripts")
sys.path.insert(0, ROOT + "/polyfactory/scripts/python")
import pf_spacescape_module as M  # noqa: E402
from polyfactory.spacetools import bake, sky  # noqa: E402
SCRATCH = "F:/cache/spacetools/spacescape_work"


def make_node(preset=None):
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(ROOT + "/polyfactory/otls/pf_space_direction.hda")
    hou.hda.installFile(HDA)
    net = hou.node("/img").createNode("copnet", "t")
    n = net.createNode("pf_spacescape", "ss")
    if preset is not None:
        M.apply_preset(n, preset)
    return n


def tonemap_png(a, path, exposure=1.0):
    from PIL import Image
    x = np.clip(a[..., :3] * exposure, 0, None)
    x = x / (1 + x)
    x = np.power(x, 1 / 2.2)
    Image.fromarray((np.clip(x, 0, 1) * 255).astype(np.uint8)).save(path)   # bake arrays are top-first
