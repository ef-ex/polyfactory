"""Audit additions for pf_spacescape (hython): checks the author's runner does not make (found by mutation, see ideas/spacetools.md).
  1 every noise parameter changes the image   2 hdr power == n^p, colour ramp direction (in=white,out=black -> rgb = n)
  3 all 10x10 Ogre blend-factor pairs equal a numpy compositing oracle built from the layers rendered alone
  4 point-star count is absolute (N stars -> ~N peaks) and uniform over the sphere  5 star seed moves the stars
hython tests/spacetools/audit_spacescape_extra.py   (exit 1 on a failure). Blind spots: noise values themselves (own hash)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import spacescape_common as C
import numpy as np
M = C.M
fails = []
def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name, info)
    if not ok: fails.append(name)
n = C.make_node(None); n.parm("res").set(64)
def render(layers, layout=0, res=64):
    M.apply_layers(n, layers); n.parm("layout").set(layout); n.parm("res").set(res)
    return C.bake.layer_array(n, 0).astype(np.float64)
def noise(**kw):   # white inner / black outer, no dither: rgb == alpha == n^hdrpower
    d = dict(type=0, dither=0.0, colorin=(1, 1, 1), colorout=(0, 0, 0), srcblend=0, dstblend=1); d.update(kw); return M.L(**d)
base = render([noise()])
# 1 parameter sensitivity
for k, v in dict(seed=3, scale=2.5, octaves=3, lacunarity=3.0, gain=0.8, power=2.0, shelf=0.3, hdrpower=2.0, hdrmult=2.0, noisetype=1, dither=0.5).items():
    d = np.abs(render([noise(**{k: v})]) - base)[..., :3].mean()
    check("noise parm %s changes the image" % k, d > 2e-3, "mean|d|=%.4f" % d)
r = noise(noisetype=1); rb = render([r])
check("ridged offset changes the image", np.abs(render([noise(noisetype=1, offset=0.6)]) - rb)[..., :3].mean() > 2e-3)
# ridged formula oracle: one octave, no dither/shelf: fbm out = p/2+.5 (p = perlin), ridged out = (off-|p|)^2/2+.5 (Spacescape ridge())
f1 = render([noise(octaves=1)])[..., 0]; p = 2 * f1 - 1
for off in (1.0, 0.7):
    r1 = render([noise(octaves=1, noisetype=1, offset=off)])[..., 0]
    e = np.abs(r1 - ((off - np.abs(p)) ** 2 * 0.5 + 0.5)).max()
    check("ridged 1 octave == (offset-|p|)^2 (offset %.1f)" % off, e < 1e-5, "%.1e" % e)
# 2 hdrpower, colour direction
p2 = render([noise(hdrpower=2.0)])[..., 0]; check("hdrpower: out == n^2", np.abs(p2 - base[..., 0] ** 2).max() < 1e-5, "%.1e" % np.abs(p2 - base[..., 0] ** 2).max())
inv = render([noise(colorin=(0, 0, 0), colorout=(1, 1, 1))])[..., 0]
check("colour ramp: swapping in/out gives 1-n", np.abs(inv - (1 - base[..., 0])).max() < 1e-5)
# 3 blend oracle
A = noise(seed=1, srcblend=0, dstblend=1); Bl = noise(seed=2, scale=3.0)
a = render([A])[..., 0]; b = render([Bl])[..., 0]          # rgb == alpha == n
worst = 0; bad = []
fac = lambda m, s, d: [1, 0, d, s, 1 - d, 1 - s, d, s, 1 - d, 1 - s][m] if m not in (6, 7, 8, 9) else [None]*6 + [d, s, 1 - d, 1 - s][m - 6 : m - 5] if False else None
def F(m, s, d):    # s, d scalars (rgb == alpha == n for these layers)
    return [np.ones_like(s), np.zeros_like(s), d, s, 1 - d, 1 - s, d, s, 1 - d, 1 - s][m]
for sm in range(10):
    for dm in range(10):
        got = render([A, M.L(**dict(Bl, srcblend=sm, dstblend=dm))])[..., 0]
        exp = b * F(sm, b, a) + a * F(dm, b, a)
        e = np.abs(got - exp).max()
        if e > 1e-4: bad.append((sm, dm, round(e, 4)))
check("all 100 blend pairs == numpy compositing", not bad, str(bad[:5]))
# 4 star count / uniformity (1 px stars, 3 faces' worth of pixels)
def peaks(count, seed=0, res=256):
    img = render([M.L(type=1, seed=seed, count=count, size=1.0, colorin=(1, 1, 1), colorout=(1, 1, 1), srcblend=0, dstblend=1)], layout=1, res=res)[..., 0]
    from numpy.lib.stride_tricks import sliding_window_view as sw
    N = res; pk = np.zeros(img.shape, bool)
    c = img[1:-1, 1:-1]; w = sw(img, (3, 3)); pk[1:-1, 1:-1] = (c >= w.max((-1, -2))) & (c > 0.25)
    cells = np.array([[0, 1, 0, 0], [1, 1, 1, 1], [0, 1, 0, 0]]).repeat(N, 0).repeat(N, 1).astype(bool)
    return int((pk & cells).sum()), pk, cells
for cnt in (3000, 12000):
    k = peaks(cnt)[0]
    check("point stars: %d requested -> %d peaks (0.7..1.15)" % (cnt, k), 0.7 * cnt <= k <= 1.15 * cnt)
k, pk, cells = peaks(12000); N = 256
fc = pk[N:2*N, N:2*N]; ab = (np.arange(N) + .5) / N * 2 - 1; A_, B_ = np.meshgrid(ab, ab); W = (1 + A_**2 + B_**2) ** -1.5   # pixel solid angle ~ W
q = N // 4; reg = {"centre": (slice(3*q//2, 5*q//2), slice(3*q//2, 5*q//2)), "corner": (slice(0, q), slice(0, q))}
dens = {k: fc[v].sum() / W[v].sum() for k, v in reg.items()}
check("front face: stars per solid angle, corner vs centre within 25%", abs(dens["corner"] / dens["centre"] - 1) < 0.25, str({k: round(float(x), 4) for k, x in dens.items()}))
check("star seed moves the stars", np.abs(peaks(3000, 0)[1].astype(int) - peaks(3000, 5)[1].astype(int)).sum() > 1000)
print("FAILED: %s" % fails if fails else "ALL PASS"); sys.exit(1 if fails else 0)
