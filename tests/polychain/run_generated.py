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

# --- KNOWN DIVERGENCES ------------------------------------------------------
#
# A real, dated, tracked difference between the two paths, matched on the DIFF
# TEXT rather than on a seed number: keying it to a seed would go stale the
# moment the sweep moves its range, and would say nothing about what the
# divergence IS.  A case whose EVERY difference matches one of these is
# reported `[KNOWN]` and does not fail the run.
#
# ⚠️ AND ITS DISAPPEARANCE FAILS THE RUN TOO (`still_occurs`).  A known
# divergence that stops occurring has either been fixed - in which case the
# entry must be deleted deliberately - or has stopped being REACHED, which is
# the fixture-blindness class this whole file exists to attack.
KNOWN = (
    ("packed[", ".prim: 'pc_module' only on the RIGHT",
     "2026-08-25, FOUND BY THIS FILE ON ITS FIRST 120-SEED RUN. The guarded "
     "native output packs its pieces with `pc_module` written INSIDE the "
     "packed geometry; the Python reference's packed contents carry `P` and "
     "nothing else. Same outer attributes on both, so no v1 check could see "
     "it: `_snapshot` never descended into a packed prim. What a consumer "
     "sees differs after an `unpack`. ⚠️ IT READ '5 of 400 seeds' UNTIL THE "
     "NATIVE LANE LANDED, AND THAT NUMBER WAS AN ARTEFACT OF THE GENERATOR, "
     "NOT OF THE TOOL: the guard was refusing 97 % of cases, so 97 % of the "
     "differential was Python against Python. With the lane it is 207 of the "
     "208 cases the native chain actually answers - i.e. it is what the "
     "native path DOES, not an edge case. Not diagnosed here - this is the "
     "test cycle; it is a production finding for polyChain's owner."),
)


def _known(diff):
    """-> the KNOWN entry every line of `diff` matches, or None.

    `compare` ends its report with two META lines - the elision count and the
    worst float deviation - which describe the report rather than name a
    difference, so they are dropped before matching.  The elision one matters:
    a case with 30 identical known differences was reported RED purely because
    "... and 5 more difference(s)" did not look like the pattern.
    """
    real = [d for d in diff
            if not d.startswith("... and ") and not d.startswith("worst float")]
    for head, tail, _why in KNOWN:
        if real and all(head in line and tail in line for line in real):
            return head + tail
    return None


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


def _envelope(node):
    """The internal wrangle that holds the guard's verdict.

    ⚠️ WITHOUT THIS THE WHOLE FILE CAN BE A CHECK THAT CANNOT FAIL.
    `Stage = output` is a GUARDED fork - a refused build falls back to the
    same Python kernel `Stage = reference` runs, so a refused case compares
    Python WITH PYTHON and is identical by construction.  The first version of
    this suite ran 400 seeds of which the native chain answered 3 %, and the
    registry proved it: `generated_pc_local_scaled` scaled the native
    `pc_local` by 1.5x and "reddened nothing at all".
    `_native_ok` is `_`-prefixed and deleted before the output, so it has to
    be read off `pc_envelope` inside the instance.
    """
    for child in node.children():
        try:
            geo = child.geometry()
        except hou.OperationFailed:
            continue
        if geo is not None and geo.findGlobalAttrib("_native_ok") is not None:
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
    node = geo_node.createNode("pf_polychain", "chain")
    for i, src in enumerate((curve_in, kit_in, style_in)):
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

            if ref is None or out is None:
                bad = ["one stage produced no geometry: reference=%r "
                       "output=%r" % (ref_msg[:1], out_msg[:1])]
            else:
                bad = compare(ref, out)
            known = _known(bad)
            rows.append({"seed": seed, "label": case["label"],
                         "native": answered, "ok": not bad, "known": known,
                         "seconds": round(took, 3), "diff": bad[:6],
                         "prims": (out or {}).get("counts", {})
                                  .get("primitivecount")})
            # ⚠️ THE PER-SEED LINES ARE DIAGNOSTICS, NOT CHECK NAMES.  The
            # mutation registry builds its inventory from `[PASS]/[FAIL]
            # <name>` lines, and a seed number is not a stable name - a sweep
            # that moves its range would silently retire and invent hundreds
            # of them.  The two names this file contributes are printed once,
            # at the end, and they are what a mutation is paired against.
            if bad and known:
                print("   known  seed %-6d %s" % (seed, known))
            elif bad:
                red.append(seed)
                print("   RED    seed %-6d %s" % (seed, case["label"]))
                for line in bad[:6]:
                    print("           %s" % line[:160])
            elif verbose:
                print("   ok     seed %-6d %4s prims  %.2fs  %s"
                      % (seed, rows[-1]["prims"], took, case["label"][:96]))
            for path in (base + "_c.bgeo", base + "_k.bgeo", base + "_s.bgeo"):
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

    # ⚠️ A KNOWN DIVERGENCE THAT STOPS OCCURRING FAILS THE RUN TOO.  Either it
    # was fixed - delete the entry, deliberately - or the generator stopped
    # REACHING it, which is the fixture-blindness class this file attacks.
    # `gen_cases.PINS` is what guarantees it has an input on any `--seeds`.
    seen = set(r["known"] for r in rows if r["known"])
    missing = [h + t for h, t, _w in KNOWN if h + t not in seen]
    nknown = len([r for r in rows if r["known"]])
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
    print("  [%s] generated_output_matches_the_reference   %d clean, %d known,"
          " %d red" % ("FAIL" if red else "PASS",
                       len(rows) - len(red) - nknown, nknown, len(red)))
    print("  [%s] known_divergences_still_occur            %d of %d reached%s"
          % ("FAIL" if missing else "PASS", len(KNOWN) - len(missing),
             len(KNOWN), "; MISSING " + ", ".join(missing) if missing else ""))
    out = _arg(argv, "--json", None, str)
    if out:
        with open(out, "w") as fh:
            json.dump({"rows": rows, "red": red, "missing": missing}, fh,
                      indent=1)
    print("\n%d generated case(s), %d RED, %d KNOWN, %.1f s (%d pinned)"
          % (len(rows), len(red), nknown, time.time() - t0,
             len(gen_cases.PINS)))
    if red:
        print("repro: gen_cases.make(%r)   # then pin it in gen_cases.PINS "
              "with one line saying what it caught" % red[0])
    return 1 if (red or missing) else 0


if __name__ == "__main__":
    sys.exit(main())
