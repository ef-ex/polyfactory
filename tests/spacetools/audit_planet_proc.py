"""Audit: the six procedural planet types (equirect + two sphere views, + billboard), odd parms, missing $PF_PLANET_IMAGES,
big resolution timing, NaN/inf. hython tests/spacetools/audit_planet_proc.py ; PNGs in F:/cache/spacetools/audit_planet/proc"""
import sys, os, time
sys.path.insert(0, os.path.dirname(__file__))
from planet_common import *
from PIL import Image
OUT = "F:/cache/spacetools/audit_planet/proc"; os.makedirs(OUT, exist_ok=True)
names = ["terran", "desert", "ice", "lava", "gas", "moon"]
tiles = []
for t, nm in enumerate(names):
    n = make_node({"mode": 1, "surface": 0, "ptype": t, "water": 1, "emission": 1, "clouds": 1 if t != 5 else 0, "atmosphere": 0})
    bad = cook_clean(n)
    t0 = time.time()
    p = M.bake(n, OUT + "/" + nm, nm, 256, maps=["beauty", "surface", "height"], layouts=("equirect",))
    dt = time.time() - t0
    eq = bake.read_exr(p["beauty"]["equirect"]); su = bake.read_exr(p["surface"]["equirect"])
    print("%-7s bad=%s finite=%s beauty mean %.3f max %.2f  surface std %.3f  bake %.1fs" % (nm, bool(bad), np.isfinite(eq).all() and np.isfinite(su).all(), eq[..., :3].mean(), eq.max(), su.std(), dt))
    row = [tonemap(sphere_view(eq, v, 256)) for v in ((0, 0, -1), (1, 0.3, 1))]
    tiles.append(np.concatenate(row + [np.asarray(Image.fromarray(tonemap(eq)).resize((512, 256)))[:, :, :]], 1) if False else np.concatenate(row, 1))
    Image.fromarray(tonemap(eq)).save("%s/%s_equirect.png" % (OUT, nm))
sheet = np.concatenate([np.concatenate(tiles[:3], 1), np.concatenate(tiles[3:], 1)], 0)
Image.fromarray(sheet).resize((1000, int(1000 * sheet.shape[0] / sheet.shape[1]))).save(OUT + "/sheet.png")
# billboard procedural
bb = []
for t in range(6):
    n = make_node({"mode": 0, "surface": 0, "ptype": t, "water": 1, "emission": 1, "clouds": 1 if t != 5 else 0, "atmosphere": 1, "lightsetup": 4})
    a = layer(n, 0); print("billboard", names[t], "finite", np.isfinite(a).all(), "mean %.3f" % a[..., :3].mean(), "alpha %.3f" % a[..., 3].mean())
    bb.append(np.asarray(Image.fromarray(tonemap(a)).resize((256, 256))))
sheet = np.concatenate([np.concatenate(bb[:3], 1), np.concatenate(bb[3:], 1)], 0); Image.fromarray(sheet).save(OUT + "/billboard_sheet.png")
# odd parms
odd = {"pscale0": {"pscale": 0.0}, "pscale50": {"pscale": 50}, "rough0": {"rough": 0.0}, "rough1": {"rough": 1.0}, "sea0": {"sea": 0.0}, "sea1": {"sea": 1.0},
       "polar1": {"polar": 1.0}, "seedneg": {"seed": -5}, "seedbig": {"seed": 2 ** 31 - 1}, "lat90": {"mode": 1, "view_lat": 90}, "lat-90": {"mode": 1, "view_lat": -90},
       "hue_big": {"s_hue": 7, "s_sat": 0, "s_val": 0, "s_contrast": 5}, "emis0": {"emission_overall": 0}, "sat_neg": {"s_sat": -1, "s_val": -1}, "tinthdr": {"tint": [50, 50, 50]},
       "ramp": {"useramp": 1, "whitepoint": 0, "rampmid": 0}, "ptype_oob": {"ptype": 99}, "surf_oob": {"surface": 99, "water": 99, "emission": 99, "clouds": 99, "atmosphere": 99},
       "lights_oob": {"lightsetup": 5, "mode": 0}, "hscale_neg": {"hscale": -3, "bump": 100}, "cloudcov": {"cloud_cov": 5, "water": 1, "clouds": 1}}
for k, v in odd.items():
    try:
        n = make_node(dict({"mode": 0}, **v)); bad = cook_clean(n)
        fin = all(np.isfinite(layer(n, i)).all() for i in range(8))
        print("odd %-10s bad=%s finite=%s" % (k, str(bad)[:120], fin))
    except Exception as e:
        print("odd %-10s EXC %s" % (k, str(e)[:150]))
# env var missing / env set
os.environ.pop("PF_PLANET_IMAGES", None)
n = make_node({"mode": 0, "surface": 5, "imagedir": "$PF_PLANET_IMAGES"}); print("env unset: bad", cook_clean(n), "mean %.3f" % layer(n, 0)[..., :3].mean())
os.environ["PF_PLANET_IMAGES"] = "F:/nope"; n = make_node({"mode": 0, "surface": 5, "imagedir": "$PF_PLANET_IMAGES"}); print("env bogus: bad", cook_clean(n), "mean %.3f" % layer(n, 0)[..., :3].mean())
# timing
for md, res, extra in ((0, "4k", {"libres": 2}), (0, "2k", {})):
    t0 = time.time(); n = make_node(dict({"mode": md, "surface": 5, "clouds": 1, "atmosphere": 1, "water": 2, "emission": 2}, **extra)); a = layer(n, 0); print("billboard", res, a.shape, "%.2fs" % (time.time() - t0))
for N_ in (512, 1024):
    n = make_node({"mode": 1, "surface": 5, "clouds": 1}); t0 = time.time()
    p = M.bake(n, OUT + "/big%d" % N_, "b", N_, maps=["beauty", "surface"], layouts=("equirect", "cross")); print("sphere bake N=%d beauty+surface equirect+cross %.1fs" % (N_, time.time() - t0))
