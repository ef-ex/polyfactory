"""pf_spacescape checks. Run:  hython tests/spacetools/run_spacescape_checks.py   (exit 1 on any failure).

Bakes 3 layer stacks (presets) to EXR (6 faces + cross + equirect) through the shipped HDA's bake() and checks:
  finite/HDR range, shared seam check (polyfactory.spacetools.bake.check_set: 12 cube-edge continuity ratios,
  equirect vs faces, cross vs faces), determinism (same seed bit-identical, other seed different), and that the
  node's own parameters really drive the output (a layer disabled / count changed changes the sky).
MUT lines feed a corrupted set to the same checker: it must turn red (a check that cannot fail is not a check).
Cannot see: equirect-vs-face agreement for stars (sub-pixel), viewer-side orientation, GPU-vs-CPU OpenCL
differences (runs on the device the session picks), and whether the sky is *beautiful* (look at the PNGs)."""
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from spacescape_common import *   # noqa

N = 192
FAILS = []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name + (" :: " + info if info else ""))
    if not ok:
        FAILS.append(name)


def bake_setup(name, preset, tweak=None):
    n = make_node(preset)
    if tweak:
        tweak(n)
    folder = SCRATCH + "/checks/" + name
    paths = M.bake(n, folder, name, N)
    return n, paths


def arr(paths):
    return {k: bake.read_exr(p) for k, p in paths.items()}


def main():
    # --- checker self-tests (mutations fed to the shared checker)
    n, paths = bake_setup("purple", "Purple Nebula")
    good = bake.check_set(paths)
    shifted = dict(paths)
    a = bake.read_exr(paths["py"])
    shifted["py"] = SCRATCH + "/checks/purple_mut_py.exr"
    bake.write_exr(shifted["py"], np.roll(a, 7, axis=1))
    mut = bake.check_set(shifted)
    check("MUT seam checker flags a shifted +Y face", mut["edge_ratio_max"] > 1.5 * max(good["edge_ratio_max"], 1.0),
          "good %.2f mutated %.2f" % (good["edge_ratio_max"], mut["edge_ratio_max"]))
    nanset = dict(paths); b = bake.read_exr(paths["px"]); b[3, 3, 0] = np.nan
    nanset["px"] = SCRATCH + "/checks/purple_mut_px.exr"; bake.write_exr(nanset["px"], b)
    check("MUT finite check flags a NaN", not bake.check_set(nanset)["finite"])

    results = {}
    for name, preset in (("purple", "Purple Nebula"), ("green", "Green Nebula"), ("sun", "Sun and Starfield")):
        node, paths = (n, paths) if name == "purple" else bake_setup(name, preset)
        data = arr(paths)
        results[name] = (node, paths, data)
        check(name + ": 8 EXRs, expected sizes",
              len(paths) == 8 and data["equirect"].shape[:2] == (2 * N, 4 * N) and data["cross"].shape[:2] == (3 * N, 4 * N)
              and all(data[k].shape[:2] == (N, N) for k in sky.FACE_NAMES))
        fin = all(np.isfinite(v).all() and v.min() >= 0 for v in data.values())
        check(name + ": all outputs finite and >= 0", fin, "global max %.1f" % max(v.max() for v in data.values()))
        mx = max(v.max() for v in data.values())
        check(name + ": HDR range plausible (1 < max < 1e4)", 1.0 < mx < 1e4, "max %.1f" % mx)
        med = float(np.median(np.concatenate([data[k][..., :3].ravel() for k in sky.FACE_NAMES])))
        check(name + ": sky not blown out and not black (median 0.002..2)", 0.002 < med < 2.0, "median %.4f" % med)
        c = bake.check_set(paths)
        check(name + ": cross == faces", c["cross_vs_faces_maxdiff"] < 1e-5, "%.2e" % c["cross_vs_faces_maxdiff"])
        check(name + ": cube edge ratio max < 2.5", c["edge_ratio_max"] < 2.5,
              "max %.2f median %.2f" % (c["edge_ratio_max"], c["edge_ratio_median"]))
        fm = float(np.mean([data[k][..., :3].mean() for k in sky.FACE_NAMES]))
        rel = c["equirect_vs_faces_mean_p999"][0] / fm
        relbad = bake.check_set(paths, conv=2)["equirect_vs_faces_mean_p999"][0] / fm   # wrong yaw convention (conv 2 = half a turn off)
        check(name + ": equirect vs faces mean abs diff / mean < 0.2", rel < 0.2, "%.4f" % rel)
        check("MUT " + name + ": wrong convention is clearly worse", relbad > 2 * rel, "%.4f vs %.4f" % (relbad, rel))
        tonemap_png(data["equirect"], SCRATCH + "/checks/%s_equirect.png" % name, 0.8)
        tonemap_png(data["cross"], SCRATCH + "/checks/%s_cross.png" % name, 0.8)

    # --- determinism and parameter sensitivity
    _, p2 = bake_setup("det_b", "Purple Nebula")
    same = all(np.array_equal(bake.read_exr(p2[k]), results["purple"][2][k]) for k in p2)
    check("same seed + params -> bit-identical bake", same)

    def reseed(nd):
        for i in range(1, nd.evalParm("layers") + 1):
            nd.parm("seed%d" % i).set(nd.evalParm("seed%d" % i) + 1)
    _, p3 = bake_setup("det_seed", "Purple Nebula", reseed)
    d3 = float(np.abs(bake.read_exr(p3["px"]) - results["purple"][2]["px"]).mean() / results["purple"][2]["px"].mean())
    check("other seeds -> different sky", d3 > 0.05, "rel diff %.3f" % d3)

    def stars_off(nd):                       # disable every star layer
        for i in range(1, nd.evalParm("layers") + 1):
            if nd.evalParm("type%d" % i) in (1, 2):
                nd.parm("enable%d" % i).set(0)
    _, p4 = bake_setup("nostars", "Purple Nebula", stars_off)
    ref = results["purple"][2]
    off = bake.read_exr(p4["equirect"])
    check("disabling star layers removes the bright stars", off.max() < 0.25 * ref["equirect"].max(),
          "max %.2f -> %.2f" % (ref["equirect"].max(), off.max()))
    mo, mr = float(np.median(off[..., :3])), float(np.median(ref["equirect"][..., :3]))
    check("nebula intact without stars (not black, not brighter than with stars)", 0.05 < mo <= mr + 1e-6, "%.4f vs %.4f" % (mo, mr))

    def only_points(k):
        def f(nd):
            for i in range(1, nd.evalParm("layers") + 1):
                if nd.evalParm("type%d" % i) != 1:
                    nd.parm("enable%d" % i).set(0)
                elif nd.evalParm("maskon%d" % i) == 0:
                    nd.parm("count%d" % i).set(nd.evalParm("count%d" % i) * k)
                else:
                    nd.parm("enable%d" % i).set(0)
        return f
    _, q1 = bake_setup("pts1", "Purple Nebula", only_points(1))
    _, q4 = bake_setup("pts4", "Purple Nebula", only_points(4))
    m1, m4 = (float(bake.read_exr(q["equirect"])[..., :3].mean()) for q in (q1, q4))
    check("unmasked point stars: 4x count -> ~4x energy (3..5x)", 3.0 < m4 / m1 < 5.0, "%.3f -> %.3f (x%.2f)" % (m1, m4, m4 / m1))

    print("FAILED: " + ", ".join(FAILS) if FAILS else "ALL PASS")
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
