"""Dev helper (plain python w/ OpenEXR via hython): side-by-side tonemapped PNG of ours vs the Blender Cycles equirect render.
hython tests/spacetools/nebula_compare.py <ours.exr> <blender.exr> <out.png>"""
import sys, numpy as np
from PIL import Image
sys.path.insert(0, "F:/projects/polyfactory-spacetools/polyfactory/scripts/python")
from polyfactory.spacetools import bake
a = bake.read_exr(sys.argv[1])[..., :3]; b = bake.read_exr(sys.argv[2])[..., :3]
def tm(x, k):
    x = x * k; x = x / (1 + x)
    return (np.clip(x, 0, 1) ** (1 / 2.2) * 255).astype(np.uint8)
def stats(n, x):
    l = x.mean(-1); print("%-8s mean %.4f p50 %.4f p90 %.4f p99 %.4f p99.9 %.3f max %.1f" % (n, l.mean(), *np.percentile(l, [50, 90, 99, 99.9]), l.max()))
stats("ours", a); stats("blender", b)
k = 1.0
Image.fromarray(np.concatenate([tm(a, k), tm(b, k)], 0)).save(sys.argv[3])
