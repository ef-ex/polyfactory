"""GENERATED SCENES THROUGH THE DIFFERENTIAL ORACLE, on the SHIPPED ASSET.

    hython tests/polychain/run_generated.py [--seeds N] [--start K] [--json F]

One work item's worth of v2: `gen_cases.make(seed)` builds a whole scene from
one integer, the `pf_polychain` NODE cooks it twice - `Stage = output` (the
guarded native chain) and `Stage = reference` (the Python kernel) - and
`diff.compare` compares EVERYTHING about the two results.

Why the node and not `native.py`'s rig: the skill's rule 7, earned here.  A
rig-based parity suite stayed green while the port was unplugged from the
asset's own Stage menu.  What ships is the .hda, so what is compared is the
.hda.

Why output-vs-reference is a well-formed question: `Stage = output` is a
GUARDED fork - for the classes the native chain cannot answer it falls back to
the same Python kernel `Stage = reference` runs, so the two must be identical
on every input, always.  That is `output_guard_parity`'s contract, run over
generated input instead of over 92 hand-written cases.

WHAT IT CANNOT SEE: whether either path is RIGHT.  Two identically wrong
answers compare clean - which is why the gate images and the human at the
milestone are not replaced by this and never will be.
"""

import json
import os
import shutil
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import gen_cases                                                  # noqa: E402
import hou                                                        # noqa: E402
from diff import compare, snapshot                                # noqa: E402
from polyfactory.polychain import style as S                      # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
HDA_PATH = os.path.join(REPO, "polyfactory", "otls",
                        "pf_polychain.hda").replace("\\", "/")

# ⚠️ THE `KNOWN DIVERGENCES` TABLE IS GONE, AND ITS ABSENCE IS THE FIX (P3,
# 2026-08-26).  Its one entry for its whole life - the native path wrote
# `pc_module` INSIDE its packed prims where the reference's contents carried
# `P` alone, 136 of 406 seeds - was a production finding parked in a test file,
# and `kit.source_for` now stamps it on both sides.  The table, its matcher and
# `known_divergences_still_occur` are DELETED rather than left empty: an empty
# escape hatch invites FILING the next divergence instead of fixing it.


# --- 13.9 N6's ONE STATED TOLERANCE -----------------------------------------
#
# ⚠️ EVERY OTHER CASE IS COMPARED AT 0.0, AND THIS ONE IS NOT, SO IT OWES AN
# EXPLANATION AND A MEASUREMENT.
#
# `conform.Surface.drop` is `hou.Geometry.intersect`; the native drop is VEX's
# `intersect()`.  They are two implementations of a ray-triangle test and they
# disagree on the hit's AXIS COMPONENT by about ONE DOUBLE ULP OF THE QUERY
# COORDINATE - probed directly, 7.105e-15 m on a query at y = 50, with x and z
# agreeing at 0.000e+00 m at 0 m, 100 m, 2 km and 20 km (the other two
# components are SELECTED from the query, not recomputed, exactly so that they
# can be exact).  Nothing on either side can remove that: it is not a spelling,
# it is two ray tests.
#
# ⚠️ AND IT REACHES THE OUTPUT ONLY THROUGH A DOUBLE.  A drop perturbed by one
# ULP of a world coordinate cannot move `P`, which is float32 - it is 4e-12 m
# at 20 km against a float32 ULP of 2e-3 m there.  What it CAN move is the
# packed prim's `transform` / `packedfulltransform` INTRINSIC, which is stored
# as a double and is a NORMALISED direction: the chord is `b - a`, so the
# relative error is the coordinate ULP divided by the PIECE LENGTH, and a short
# piece far from the origin is the worst case.  That is why the tolerance is
# absolute and small rather than relative to the value.
#
# THE NUMBER IS MEASURED, NOT CHOSEN: `conform_parity_spends_its_tolerance`
# prints the worst deviation every run and fails if it comes within 10x of this
# ceiling, so the headroom cannot be quietly eaten.  Measured worst on this
# sweep 2.498e-16 m; measured worst on a 20 km run of 0.3 m pieces - the shape
# the generator cannot reach and the one where `ULP(coordinate) / piece length`
# is largest - 2.963e-15 m.
CONFORM_TOL = 1e-12

# ...and the SECOND half of the conformed contract, which is a different kind
# of number and so is a different mechanism (`ulp=True`, see `diff.compare`):
# one FLOAT32 ULP at the value's own magnitude.  The two ray tests disagree by
# about one DOUBLE ULP, which is 1e8 times under `CONFORM_TOL` and invisible -
# EXCEPT where the double lands exactly on a float32 rounding tie, and a query
# at a grid-cell midpoint does that systematically, because the hit is then the
# exact mean of two float32 vertices.  Measured on `BB_conform_vertical`: FOUR
# point coordinates of 1 302, all the same adjacent pair, and the `bounds`
# intrinsic that quotes them.
#
# ⚠️ AND THESE TWO INTRINSICS ARE DROPPED ON A CONFORMED CASE, which is a
# WEAKENING and so has to earn itself: both are pure functions of `P` and the
# topology, and this file compares BOTH exhaustively, so they carry no
# information of their own.  What they do carry is cancellation - they are
# products of coordinates - so a last-bit `P` difference comes out of them
# amplified past any ULP rule stated about `P` (measured: 1.49e-08 m on `P`
# arriving as 6.21e-09 on a `measuredvolume` of 0.00225, which is ten float32
# ULP of ITS magnitude).
CONFORM_SKIP = ("measuredarea", "measuredvolume")


def _arg(argv, flag, default, cast=int):
    return cast(argv[argv.index(flag) + 1]) if flag in argv else default


def _file_sop(parent, name):
    node = parent.createNode("file", name)
    node.parm("filemode").set(0)                 # read
    node.parm("missingframe").set(1)             # no error on an absent file
    return node


def _write(geo, path):
    geo.saveToFile(path)
    return path


def _envelope(node, attrib="_native_ok"):
    """The internal wrangle that holds the guard's verdict.

    ⚠️ `attrib` IS F6: both floors below read LEVEL 1 while the switch that
    decides what `Stage = output` returns reads `_native_ok2`, so a level-2
    refusal was invisible to the tripwire (178/178 and 70/70 agreed when it
    was measured, and "not yet" is what a tripwire is for).
    """
    for child in node.children():
        try:
            geo = child.geometry()
        except hou.OperationFailed:
            continue
        if geo is not None and geo.findGlobalAttrib(attrib) is not None:
            return child
    return None


def _cook(node, stage):
    """Cook the asset at one stage.  Node errors/warnings ARE part of the
    answer, so they travel in the snapshot rather than being swallowed."""
    node.parm("stage").set(stage)
    try:
        node.cook(force=True)
        errs = list(node.errors())
    except hou.OperationFailed as exc:
        return None, ["cook raised: %s" % str(exc)[:200]]
    return node.geometry(), errs + list(node.warnings())


def run(seeds, verbose=True):
    hou.hda.installFile(HDA_PATH)
    hou.putenv("POLYFACTORY",
               os.path.join(REPO, "polyfactory").replace("\\", "/"))
    obj = hou.node("/obj")
    geo_node = obj.createNode("geo", "pc_generated")
    curve_in = _file_sop(geo_node, "curve_in")
    kit_in = _file_sop(geo_node, "kit_in")
    style_in = _file_sop(geo_node, "style_in")
    # 13.9 N6 - INPUT 4, and it stays WIRED for every seed.  A seed with no
    # terrain points it at a missing file, which `missingframe = 1` cooks as an
    # empty geometry - which is exactly what an artist's unwired input looks
    # like to `has_surface` (`primitivecount`, not `is not None`).  Rewiring per
    # seed would test a graph no artist has.
    surface_in = _file_sop(geo_node, "surface_in")
    node = geo_node.createNode("pf_polychain", "chain")
    for i, src in enumerate((curve_in, kit_in, style_in, surface_in)):
        node.setInput(i, src)

    tmp = tempfile.mkdtemp(prefix="pcgen_")
    rows, red = [], []
    env = None
    try:
        for seed in seeds:
            case = gen_cases.make(seed)
            base = os.path.join(tmp, "s%d" % seed).replace("\\", "/")
            style_geo = hou.Geometry()
            S.write(style_geo, case["style"])
            curve_in.parm("file").set(_write(case["curve"], base + "_c.bgeo"))
            kit_in.parm("file").set(_write(case["kit"], base + "_k.bgeo"))
            style_in.parm("file").set(_write(style_geo, base + "_s.bgeo"))
            surf = case.get("surface")
            surface_in.parm("file").set(
                _write(surf, base + "_t.bgeo") if surf is not None
                else base + "_absent.bgeo")

            t0 = time.time()
            ref_geo, ref_msg = _cook(node, "reference")
            ref = snapshot(ref_geo, warnings=ref_msg) if ref_geo else None
            out_geo, out_msg = _cook(node, "output")
            out = snapshot(out_geo, warnings=out_msg) if out_geo else None
            took = time.time() - t0
            env = env or _envelope(node)
            answered = 0
            if env is not None:
                g = env.geometry()
                if g is not None and g.findGlobalAttrib("_native_ok"):
                    answered = int(g.attribValue("_native_ok"))
            # ...and level 2, the one the switch reads (F6): a build level 1
            # admits and level 2 refuses ships the REFERENCE.
            g2 = _envelope(node, "_native_ok2")
            g2 = g2.geometry() if (answered and g2 is not None) else None
            answered = int(g2.attribValue("_native_ok2"))                 if (g2 is not None and g2.findGlobalAttrib("_native_ok2"))                 else 0

            worst = []
            if ref is None or out is None:
                bad = ["one stage produced no geometry: reference=%r "
                       "output=%r" % (ref_msg[:1], out_msg[:1])]
            else:
                conf = bool(case.get("surface"))
                bad = compare(ref, out, tol=CONFORM_TOL if conf else 0.0,
                              worst=worst, ulp=conf,
                              skip=CONFORM_SKIP if conf else ())
            rows.append({"seed": seed, "label": case["label"],
                         "native": answered, "ok": not bad,
                         "surface": case.get("surface_kind", ""),
                         "worst": (worst[0] if worst else (0.0, 0.0, "", 0)),
                         "seconds": round(took, 3), "diff": bad[:6],
                         "prims": (out or {}).get("counts", {})
                                  .get("primitivecount")})
            # ⚠️ THE PER-SEED LINES ARE DIAGNOSTICS, NOT CHECK NAMES.  The
            # mutation registry builds its inventory from `[PASS]/[FAIL]
            # <name>` lines, and a seed number is not a stable name - a sweep
            # that moves its range would silently retire and invent hundreds
            # of them.  The two names this file contributes are printed once,
            # at the end, and they are what a mutation is paired against.
            if bad:
                red.append(seed)
                print("   RED    seed %-6d %s" % (seed, case["label"]))
                for line in bad[:6]:
                    print("           %s" % line[:160])
            elif verbose:
                print("   ok     seed %-6d %4s prims  %.2fs  %s"
                      % (seed, rows[-1]["prims"], took, case["label"][:96]))
            for path in (base + "_c.bgeo", base + "_k.bgeo", base + "_s.bgeo",
                         base + "_t.bgeo"):
                if os.path.exists(path):
                    os.remove(path)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return rows, red


def main():
    argv = sys.argv[1:]
    if not os.path.exists(HDA_PATH):
        print("no HDA at %s - run devScripts/create_pf_polychain_hda.py"
              % HDA_PATH)
        return 1
    seeds = gen_cases.seeds(_arg(argv, "--seeds", 12),
                            _arg(argv, "--start", 0))
    t0 = time.time()
    rows, red = run(seeds, verbose="--quiet" not in argv)

    answered = len([r for r in rows if r.get("native")])
    print("")
    # ⚠️ THE FLOOR IS THE POINT, NOT THE PERCENTAGE.  A run in which the guard
    # refuses everything is a run that compared the Python kernel with itself
    # on every case and printed a green.  Measured: 3 % before the native lane
    # existed, 52 % after.  40 % is a floor with room under it for a build
    # that legitimately narrows the envelope, and a failure here says "the
    # oracle stopped being an oracle", not "the tool regressed".
    floor = 0.40
    share = float(answered) / max(len(rows), 1)
    if share < floor:
        red = list(red) + ["only %.0f%% of cases reached the native chain"
                           % (100 * share)]
    print("  [%s] generated_cases_reach_the_native_chain    %d of %d "
          "(%.0f%%, floor %.0f%%)"
          % ("FAIL" if share < floor else "PASS", answered, len(rows),
             100 * share, 100 * floor))
    # ⚠️ 13.9 N6 NEEDS ITS OWN FLOOR, AND FOR THE SAME REASON THE ROW ABOVE
    # DOES.  `Stage = output` is a guarded fork, so a conformed case the guard
    # REFUSES compares the Python kernel with itself and passes by
    # construction - which is what every conformed case did before N6 and what
    # they would all silently go back to doing the day level 1 stopped
    # admitting a surface.  This row is the tripwire on that: it counts only
    # the seeds that carry a terrain, and only the ones the native chain
    # actually answered.  `tilt` and a tilted `conform_axis` are DELIBERATE
    # refusals (D55, D111), so they are excluded from the denominator by name
    # rather than by lowering the floor to hide them.
    # `wiggle` joins `tilt` for the same reason: the +-Z wall lane (F3) exists
    # to reach a LEVEL-2 REFUSAL. The gentle half of the lane stays counted.
    surf_rows = [r for r in rows if r.get("surface")
                 and "tilt" not in r["surface"]
                 and "wiggle" not in r["surface"]]
    surf_ok = len([r for r in surf_rows if r.get("native")])
    sfloor = 0.90
    sshare = float(surf_ok) / max(len(surf_rows), 1)
    if surf_rows and sshare < sfloor:
        red = list(red) + ["only %.0f%% of CONFORMED cases reached the native "
                           "chain" % (100 * sshare)]
    print("  [%s] generated_output_matches_the_reference   %d clean, %d red"
          % ("FAIL" if red else "PASS", len(rows) - len(red), len(red)))
    print("  [%s] conformed_cases_reach_the_native_chain   %d of %d "
          "(%.0f%%, floor %.0f%%)"
          % ("FAIL" if (surf_rows and sshare < sfloor) else "PASS",
             surf_ok, len(surf_rows), 100 * sshare, 100 * sfloor))
    # ⚠️ A STATED TOLERANCE THAT NOTHING MEASURES IS A NUMBER ANY LATER CYCLE
    # CAN WIDEN FOR FREE.  This is the row that reads it back: the worst
    # deviation actually spent on a conformed case, against a TENTH of the
    # ceiling, so the headroom has to stay an order of magnitude.  It also
    # counts the ULP-tie differences, which must stay a handful - a systematic
    # port error moves thousands of values, not four.
    spent = max([r["worst"][0] for r in rows if r.get("surface")] or [0.0])
    ties = sum(r["worst"][3] for r in rows if r.get("surface"))
    over = spent > CONFORM_TOL / 10.0
    if over:
        red = list(red) + ["the conformed tolerance is being spent: %.3e m"
                           % spent]
    print("  [%s] conform_parity_spends_its_tolerance      %.3e m of %.0e "
          "(guard %.0e), %d float32 tie(s)"
          % ("FAIL" if over else "PASS", spent, CONFORM_TOL,
             CONFORM_TOL / 10.0, ties))
    out = _arg(argv, "--json", None, str)
    if out:
        with open(out, "w") as fh:
            json.dump({"rows": rows, "red": red}, fh, indent=1)
    print("\n%d generated case(s), %d RED, %.1f s (%d pinned)"
          % (len(rows), len(red), time.time() - t0, len(gen_cases.PINS)))
    if red:
        print("repro: gen_cases.make(%r)   # then pin it in gen_cases.PINS "
              "with one line saying what it caught" % red[0])
    return 1 if red else 0


if __name__ == "__main__":
    sys.exit(main())
