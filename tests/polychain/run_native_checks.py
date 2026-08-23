"""The NATIVE stages, measured against the reference implementation.

    hython tests/polychain/run_native_checks.py

13.9's parity rig.  `run_scene_checks.py` measures the kernel and
`run_hda_checks.py` measures the asset's wiring; neither can see whether a
stage that has been ported to VEX still answers the same question as the
Python it replaced.  This file is that missing third half, and it is built on
13.8's one rule:

    THE REFERENCE STAYS LIVE IN THE SAME PROCESS AND PARITY IS PROVEN BY
    ASKING BOTH, NOT BY DIFFING TWO RUNS.

Every stage below cooks as real SOP nodes - the SAME nodes
`devScripts/create_pf_polychain_hda.py` installs, built by `native.py`, which
both files call - on the SAME `hou.Geometry` the reference was handed.  A
stage that only existed in this file would be a check of nothing.

What it asserts, in order:
  1. 4.1 decompose parity on all 89 cases - arclength, the curve-id rule,
     corners, markers;
  2. 4.4 `pc_frames` parity on every real `_packed_transform` call those cases
     make - the 3x3 BIT FOR BIT, and P against float32 P storage exactly;
  3. D113's three trials on the new VEX - an irrational slope, 20 km, and an
     asymmetric case, because a parity check green on symmetric fixtures is a
     claim about the fixtures;
  4. the MUTATION test - corrupt each new wrangle and confirm something goes
     red, because a node whose removal leaves the suite green is untested;
  5. 13.7's readability rules on the built asset, which is the deliverable;
  6. `sop_cooks_per_build` and the two benches - ONE LONG CURVE and THREE
     HUNDRED SHORT ONES - because 11.9 rule 2 is reborn as a per-NODE fixed
     cost that one 20 km fence never shows and 300 streets multiply.
"""

import io
import math
import os
import re
import struct
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import cases                                                     # noqa: E402
cases.setup_env()

import hou                                                       # noqa: E402
import native                                                    # noqa: E402
from polyfactory.polychain import DEFAULTS                       # noqa: E402
from polyfactory.polychain import conform as CONFORM             # noqa: E402
from polyfactory.polychain import hda as H                       # noqa: E402
from polyfactory.polychain import place as P                     # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
HDA_PATH = os.path.join(REPO, "polyfactory", "otls",
                        "pf_polychain.hda").replace("\\", "/")

RESULTS = []

# `frames_parity` writes the worst P deviation, in float32 ULP, here. A module
# global rather than a fifth return value because the mutation test calls the
# same function and does not care.
FRAMES_ULP = [0.0]


def check(name, ok, value="", detail=""):
    RESULTS.append((name, bool(ok), value, detail))
    print("  [%s] %-32s %-24s %s"
          % ("PASS" if ok else "FAIL", name, value, detail))
    return ok


def f32(x):
    """`x` as Houdini stores it in a float32 attribute.

    Used as an ASSERTION, not as a tolerance: `native == f32(reference)` is a
    statement about storage that cannot be satisfied by luck, where
    `abs(native - reference) < 1e-6` can be satisfied by two different bugs.
    """
    return struct.unpack("f", struct.pack("f", float(x)))[0]


def _fingerprint(node):
    """(prim count, every point of the OUTPUT rounded to 1e-6 m) for one node.

    The strongest cheap statement about a cook: two builds that agree here
    built the same fence in the same place.
    """
    geo = node.geometry()
    return (len(geo.iterPrims()),
            tuple(round(v, 6) for v in geo.pointFloatAttribValues("P")))


def hilo(x):
    """D170's split: the float32 head and the float32 residual
    `plan_geometry` stores, which `pc_frames` adds back in 64-bit VEX."""
    head = f32(x)
    return head, f32(float(x) - head)


def transported(x):
    """`x` as it ARRIVES at the wrangle after crossing the point attributes."""
    head, lo = hilo(x)
    return head + lo


def ulp32(x):
    """One float32 ULP at `x` - the smallest number float32 can express there.

    D111's lesson, applied as a unit rather than as a tolerance: a distance
    rounds at the size of a drop and a position at the size of the world, so
    "1 ULP" means something at both and "1e-6 m" means something at only one.
    """
    if x == 0.0:
        return math.ldexp(1.0, -149)
    return math.ldexp(1.0, math.frexp(abs(x))[1] - 24)


# --- 1 + 2: the stages, cooked beside the reference -------------------------

def stage_rows(root, case, params):
    """Cook the native decompose chain on `case`'s own curve geometry."""
    sub = root.createNode("subnet", "case")
    src = native.feed(sub, case["curve"], "IN")
    cfg = native.config_stub(sub, params)
    last, nodes = native.stage_decompose(sub, src, cfg)
    last.cook(force=True)
    return sub, last, nodes


def decompose_parity(root, built):
    from polyfactory.polychain import decompose as D

    worst_s = worst_total = worst_turn = worst_marker = 0.0
    bad_corner = []
    bad_marker = []
    bad_id = []
    n_curves = n_corners = n_markers = n_declined = n_dup = 0
    for name in sorted(built):
        case = built[name]
        params = case["style"].params if case["style"] else DEFAULTS
        sub, last, _nodes = stage_rows(root, case, params)
        if last.errors():
            bad_corner.append((name, "ERROR", last.errors()))
            sub.destroy()
            continue
        out = last.geometry()
        curves, markers = P.read_curves(case["curve"])
        prims = out.prims()

        # (a) THE ID RULE AND THE CURVE SET, against `read_curves` ITSELF.
        # ⚠️ THIS USED TO COMPARE TWO COPIES OF THE SAME RULE. It asked
        # `hda.curve_prim_index`, which re-implemented D29/D64 and applied
        # none of `read_curves`' filters - so it could agree with the VEX
        # while both disagreed with the curve set the builder plans on.
        # There is one rule now (`curve_prim_index` reads `read_curves`) and
        # this asks the builder's own answer, prim by prim, INCLUDING the
        # prims the reference declined.
        ref_by_prim = dict((c.prim_number, str(c.curve_id)) for c in curves)
        iscurve = out.primIntAttribValues("pc_iscurve")
        got_ids = out.primStringAttribValues("pc_curve_id_r")
        for i, cid in enumerate(got_ids):
            want = ref_by_prim.get(i)
            if want is None:
                n_declined += 1
                if iscurve[i] or cid:
                    bad_id.append((name, i, "kept a prim the reference "
                                   "declined", cid))
            elif not iscurve[i] or cid != want:
                bad_id.append((name, i, cid, want))

        pc_s = out.pointFloatAttribValues("pc_s")
        turn = out.pointFloatAttribValues("pc_turn_deg")
        corner = out.pointIntAttribValues("pc_iscorner")
        degen = out.pointIntAttribValues("pc_corner_degen")
        for curve in curves:
            n_curves += 1
            # BY PRIM NUMBER, not by id: two curves may legally share an id
            # (D74) and keying by id silently compared one of them twice.
            prim = prims[curve.prim_number]
            worst_total = max(worst_total,
                              abs(prim.attribValue("pc_total") - curve.length))
            idx, _pts, cum = D._clean(curve)
            pnums = [p.number() for p in prim.points()]
            for k, i in enumerate(idx):
                worst_s = max(worst_s, abs(pc_s[pnums[i]] - cum[k]))
            ref = dict((c.point_index, c)
                       for c in D.resolve_corners(curve, params))
            got = dict((i, pn) for i, pn in enumerate(pnums) if corner[pn])
            if set(ref) != set(got):
                bad_corner.append((name, str(curve.curve_id),
                                   sorted(ref), sorted(got)))
            for i in set(ref) & set(got):
                n_corners += 1
                worst_turn = max(worst_turn,
                                 abs(turn[got[i]] - ref[i].turn_angle))
                if bool(degen[got[i]]) != ref[i].degenerate:
                    bad_corner.append((name, str(curve.curve_id), "degen", i))

        # (b) MARKERS, keyed by the PRIM each one landed on.
        # D169: where two prims claim one id the reference places the marker
        # on BOTH and one point wrangle can place it on one, so the native
        # stage owes a WARNING there rather than a second point. That is
        # asserted, not excused.
        seen = {}
        for cid in got_ids:
            if cid:
                seen[cid] = seen.get(cid, 0) + 1
        dup_ids = set(c for c, n in seen.items() if n > 1)
        ref_m = {}
        for curve in curves:
            rows = D.resolve_markers(curve, markers)
            if rows:
                ref_m[curve.prim_number] = sorted(rows, key=lambda d: d["s"])
        got_m = {}
        if out.findPointAttrib("pc_marker") is not None:
            has_dup = out.findPointAttrib("pc_warn_marker_dup") is not None
            mark = out.pointIntAttribValues("pc_marker")
            bound = out.pointIntAttribValues("pc_curveprim")
            warn_dup = (out.pointIntAttribValues("pc_warn_marker_dup")
                        if has_dup else [0] * len(mark))
            for pn, is_m in enumerate(mark):
                if is_m and bound[pn] >= 0:
                    got_m.setdefault(bound[pn], []).append(
                        (pc_s[pn], warn_dup[pn]))
        for pr in sorted(set(ref_m) | set(got_m)):
            rows = ref_m.get(pr, [])
            mine = sorted(got_m.get(pr, []))
            if got_ids[pr] in dup_ids:
                n_dup += 1
                # the FIRST prim claiming the id keeps the marker, and it must
                # say that it is answering for more than one curve
                first = min(i for i, c in enumerate(got_ids)
                            if c == got_ids[pr])
                want = len(rows) if pr == first else 0
                if len(mine) != want or (mine and not mine[0][1]):
                    bad_marker.append((name, pr, "dup", want, len(mine),
                                       mine and mine[0][1]))
                    continue
            elif len(mine) != len(rows):
                bad_marker.append((name, pr, len(rows), len(mine)))
                continue
            for row, pair in zip(rows, mine):
                n_markers += 1
                worst_marker = max(worst_marker, abs(row["s"] - pair[0]))
        sub.destroy()

    check("native_id_and_curve_set_parity", not bad_id, len(bad_id),
          "the VEX id rule AND the curve set vs place.read_curves over %d "
          "curves and %d declined prims; %s"
          % (n_curves, n_declined, bad_id[:2] or "identical"))
    # EXACT, no slack: 64-bit VEX doing the same additions in the same order
    # as 64-bit Python. If this needs a tolerance the accumulation order
    # differs, and that is a defect, not float noise (13.8).
    check("decompose_arclength_parity", worst_s == 0.0, "%.3e m" % worst_s,
          "worst |d pc_s| over %d curves, all cases (ceiling 0.0)"
          % n_curves)
    check("decompose_length_parity", worst_total == 0.0,
          "%.3e m" % worst_total, "worst |d curve length| (ceiling 0.0)")
    check("decompose_corner_parity", not bad_corner, len(bad_corner),
          "%d corners, identical sets and flags; %s"
          % (n_corners, bad_corner[:2] or "no mismatch"))
    # acos() is the one place a ULP shows: 2.8e-14 deg is 5e-16 rad.
    check("decompose_turn_parity", worst_turn < 1e-10,
          "%.3e deg" % worst_turn,
          "worst |d turn angle| over %d corners (ceiling 1e-10, it is acos "
          "ULP not zero)" % n_corners)
    check("decompose_marker_parity", not bad_marker and worst_marker == 0.0,
          "%.3e m" % worst_marker,
          "worst |d marker s| over %d markers on %d prims, %d of them under "
          "a duplicated id (D169 - warned, not silently short); %s"
          % (n_markers, n_curves, n_dup,
             bad_marker[:2] or "counts identical"))


def frame_calls(case):
    """Every `_packed_transform` the reference makes on `case`, recorded.

    The reference is re-run rather than read out of `case["report"]` because
    `up_ref` is a pass-B decision and the recorded call is the only place both
    halves of the question exist at once.
    """
    calls = []
    real_pt = P._packed_transform
    real_pi = P.Path.__init__
    registry = []

    def spy_pi(self, curve):
        real_pi(self, curve)
        self._pc_pidx = len(registry)
        registry.append(curve)

    def spy_pt(proto, path, sa, sb, zmode, up_ref=P.UP, base_y=None,
               ends=None, yscale=1.0):
        # ⚠️ THE SPANS GO THROUGH THE REAL TRANSPORT ON *BOTH* SIDES,
        # deliberately, and that makes the two checks below ARITHMETIC-ONLY.
        # The rig carries the plan to the wrangle through point attributes,
        # which are float32 storage; asking the reference in float64 and the
        # wrangle in float32 would measure the transport instead of the
        # maths. Rounding both isolates the maths - and the TRANSPORT is
        # measured on its own, unrounded, by `plan_span_transport_at_20km`,
        # which is the check that used not to exist.
        # ⚠️ THE PAIR IS RECORDED, NOT JUST THE SUM. Splitting `head + lo`
        # a SECOND time in `frames_geometry` gives a different pair - the sum
        # is not itself float32-representable - and the 3x3 then disagreed by
        # 2.220e-16 for no reason but the double transport.
        (ha, la), (hb, lb) = hilo(sa), hilo(sb)
        sa, sb = ha + la, hb + lb
        matrix = real_pt(proto, path, sa, sb, zmode, up_ref, base_y, None,
                         yscale)
        calls.append({"pidx": getattr(path, "_pc_pidx", -1),
                      "conform": isinstance(path, CONFORM.ConformPath),
                      "plen": proto.length, "pax": proto.ax,
                      "sa": sa, "sb": sb, "zmode": zmode,
                      "sa_head": ha, "sa_lo": la,
                      "sb_head": hb, "sb_lo": lb,
                      "up": tuple(up_ref), "base_y": base_y,
                      "yscale": yscale, "m": matrix})
        return matrix

    P._packed_transform = spy_pt
    P.Path.__init__ = spy_pi
    try:
        P.build(case["curve"], case["kit"], case["style"],
                surface_geo=case["surface"], overrides=case["overrides"])
    finally:
        P._packed_transform = real_pt
        P.Path.__init__ = real_pi
    return calls, registry


def frames_geometry(rows):
    """The plan points `pc_frames.vfl` binds, from recorded reference calls."""
    plan = hou.Geometry()
    for name, default in H.FRAME_POINT_ATTRS:
        plan.addAttrib(hou.attribType.Point, name, default)
    plan.addAttrib(hou.attribType.Point, "pc_zmode", "")
    plan.addAttrib(hou.attribType.Point, "pc_upref", (0.0, 1.0, 0.0))
    plan.createPoints([(0.0, 0.0, 0.0)] * len(rows))
    plan.setPointIntAttribValues("pc_curveprim", [r["pidx"] for r in rows])
    plan.setPointIntAttribValues(
        "pc_has_basey", [0 if r["base_y"] is None else 1 for r in rows])
    for name, key in (("pc_s0r", "sa"), ("pc_s1r", "sb")):
        plan.setPointFloatAttribValues(name, [r[key + "_head"] for r in rows])
        plan.setPointFloatAttribValues(name + "_lo",
                                       [r[key + "_lo"] for r in rows])
    plan.setPointFloatAttribValues("pc_proto_len", [r["plen"] for r in rows])
    plan.setPointFloatAttribValues("pc_proto_ax", [r["pax"] for r in rows])
    plan.setPointFloatAttribValues(
        "pc_basey", [0.0 if r["base_y"] is None else r["base_y"]
                     for r in rows])
    plan.setPointFloatAttribValues("pc_yscale", [r["yscale"] for r in rows])
    plan.setPointStringAttribValues("pc_zmode", [r["zmode"] for r in rows])
    up = []
    for row in rows:
        up.extend(row["up"])
    plan.setPointFloatAttribValues("pc_upref", up)
    return plan


def frames_parity(root, built, snippet=None, quiet=False):
    """(worst 3x3 error, worst P mismatch, calls compared, zmodes seen).

    `snippet` replaces `pc_frames.vfl`'s VEX - the mutation test's lever.
    """
    worst_lin = 0.0
    bad_pos = 0
    total = 0
    zmodes = set()
    worst_ulp = FRAMES_ULP
    worst_ulp[0] = 0.0
    for name in sorted(built):
        case = built[name]
        calls, registry = frame_calls(case)
        rows = [c for c in calls if not c["conform"] and c["pidx"] >= 0]
        if not rows:
            continue
        # ONE polyline per recorded `Path`, in `Path` order, so the prim
        # number IS the index the call recorded. The reference's Path may be
        # a FILLETED or slope-flattened polyline - feeding the raw input
        # spline instead would be asking about a curve that does not exist.
        curve_geo = hou.Geometry()
        for curve in registry:
            cases.polyline(curve_geo, curve.points, closed=curve.closed,
                           curve_id=str(curve.curve_id))
        sub = root.createNode("subnet", "frames")
        src = native.feed(sub, curve_geo, "IN")
        params = case["style"].params if case["style"] else DEFAULTS
        cfg = native.config_stub(sub, params)
        last, _nodes = native.stage_decompose(sub, src, cfg)
        node = native.wrangle(sub, "pc_frames", "point", "pc_frames")
        if snippet is not None:
            node.parm("snippet").set(snippet)
        node.setInput(0, native.feed(sub, frames_geometry(rows), "IN_PLAN"))
        node.setInput(1, cfg)
        node.setInput(2, last)
        node.cook(force=True)
        if node.errors():
            if not quiet:
                print("      !! %s: %s" % (name, node.errors()))
            sub.destroy()
            continue
        out = node.geometry()
        xform = out.pointFloatAttribValues("transform")
        pos = out.pointFloatAttribValues("P")
        for i, row in enumerate(rows):
            total += 1
            zmodes.add(row["zmode"])
            matrix = row["m"]
            for r in range(3):
                for c in range(3):
                    want = matrix.at(r, c)
                    got = xform[i * 9 + r * 3 + c]
                    # RELATIVE, floored at 1.0 - the entries are direction
                    # components times a scale, so 1.0 is their natural unit
                    # and a bare absolute error means two things at two
                    # magnitudes (D111's lesson).
                    worst_lin = max(worst_lin,
                                    abs(got - want) / max(abs(want), 1.0))
            for k in range(3):
                want = f32(matrix.at(3, k))
                got = pos[i * 3 + k]
                if got != want:
                    bad_pos += 1
                    worst_ulp[0] = max(worst_ulp[0], abs(got - want)
                                       / ulp32(want))
        sub.destroy()
    return worst_lin, bad_pos, total, zmodes


# --- 3: D113's three trials -------------------------------------------------

TRIALS = (
    # An IRRATIONAL SLOPE, so no arclength lands on a tidy binary fraction.
    ("irrational", [(0.0, 0.0, 0.0), (math.pi, math.sqrt(2.0), math.e),
                    (2.0 * math.pi, 0.0, 2.0 * math.e)], False),
    # TWENTY KILOMETRES - where 32-bit VEX returns 0 for the same expression.
    ("20km", [(0.0, 0.0, 0.0), (10000.0, 3.0, 0.0), (20000.0, 0.0, 7.0)],
     False),
    # ASYMMETRIC, and closed, so nothing can cancel: a green check on a
    # symmetric fixture is a claim about the fixture.
    ("asymmetric", [(0.0, 0.0, 0.0), (7.3, 0.0, 0.0), (9.1, 0.0, 4.4),
                    (1.0, 0.0, 6.2), (0.4, 0.0, 2.1)], True),
)


def trial_parity(root):
    from polyfactory.polychain import decompose as D
    worst_s = worst_total = 0.0
    worst_at = ""
    for label, points, closed in TRIALS:
        geo = hou.Geometry()
        cases.polyline(geo, points, closed=closed, curve_id=label)
        sub, last, _nodes = stage_rows(root, {"curve": geo}, DEFAULTS)
        out = last.geometry()
        curves, _m = P.read_curves(geo)
        pc_s = out.pointFloatAttribValues("pc_s")
        for curve in curves:
            prim = out.prims()[0]
            err_total = abs(prim.attribValue("pc_total") - curve.length)
            idx, _pts, cum = D._clean(curve)
            pnums = [p.number() for p in prim.points()]
            for k, i in enumerate(idx):
                err = abs(pc_s[pnums[i]] - cum[k])
                if err > worst_s:
                    worst_s, worst_at = err, label
            if err_total > worst_total:
                worst_total, worst_at = err_total, label
        sub.destroy()
    check("trials_irrational_20km_asymmetric",
          worst_s == 0.0 and worst_total == 0.0,
          "%.3e m" % max(worst_s, worst_total),
          "worst of the three D113 trials (%s); ceiling 0.0"
          % (worst_at or "all exact"))


# --- 4: the mutation test ---------------------------------------------------

def mutation(root, built):
    """Corrupt each new node and confirm the parity check goes red.

    A node whose removal leaves the suite green is untested, not correct -
    which is exactly what cycle P2-3V found six times.
    """
    from polyfactory.polychain import vexsrc
    from polyfactory.polychain import decompose as D
    small = dict((k, built[k]) for k in sorted(built)[:6])

    # (a) pc_frames: drop the module scale, which is one character.
    broken = vexsrc.source("pc_frames").replace(
        "float scale = max(clen / plen, 1e-9);",
        "float scale = max(clen / plen, 1e-9) * 1.0000001;")
    worst, _bad, total, _z = frames_parity(root, small, snippet=broken,
                                           quiet=True)
    check("mutation_pc_frames", worst > 4.5e-16, "%.3e rel" % worst,
          "a 1e-7 relative scale error over %d calls turns the 3x3 red - it "
          "must clear the FMA floor the sound build sits at" % total)

    # (b) pc_arclength: skip the coincident-vertex merge, so `_clean`'s
    # 1e-6 m rule stops being honoured. It must move a real number.
    merge = "if (nk && length(P[i] - P[keep[nk - 1]]) <= PC_POS_EPS) continue;"
    source = vexsrc.source("pc_arclength")
    assert merge in source, "the mutation no longer names a line that exists"
    broken = source.replace(merge, "// merge removed by the mutation test")
    geo = hou.Geometry()
    cases.polyline(geo, [(0, 0, 0), (3, 0, 0), (3, 0, 0), (6, 4, 0)],
                   curve_id="MUT")
    sub = root.createNode("subnet", "mut")
    src = native.feed(sub, geo, "IN")
    cfg = native.config_stub(sub, DEFAULTS)
    # ⚠️ THE WHOLE CHAIN, not `pc_arclength` alone. Since D167 the arclength
    # node writes nothing to a prim `pc_curveid` did not call a curve, so a
    # rig that skips the upstream nodes measures the gate rather than the
    # mutation - and the check then fails for a reason that is not a defect.
    node, nodes = native.stage_decompose(sub, src, cfg)
    nodes["pc_arclength"].parm("snippet").set(broken)
    node.cook(force=True)
    curve = P.read_curves(geo)[0][0]
    idx, _pts, cum = D._clean(curve)
    prim = node.geometry().prims()[0]
    pnums = [p.number() for p in prim.points()]
    pc_s = node.geometry().pointIntAttribValues("pc_cleanidx")
    moved = [pc_s[pnums[i]] for i in range(len(pnums))]
    check("mutation_pc_arclength", moved != [0, 1, -1, 2], moved,
          "without the merge the cleaned index table changes (sound: "
          "[0, 1, -1, 2])")
    sub.destroy()

    # (c) pc_unshare: BYPASS it, and the fused junction must go wrong.
    # D165's whole justification in one assertion. Without the split, curve
    # FA's real 90 degree corner disappears (`pointprims()[0]` resolves the
    # junction to whichever prim is first) and its metre at the junction is
    # whatever the other curve wrote there.
    fused = cases.topology_cases()["T1_fused_junction"]
    sub = root.createNode("subnet", "mut_unshare")
    src = native.feed(sub, fused["curve"], "IN")
    cfg = native.config_stub(sub, DEFAULTS)
    last, nodes = native.stage_decompose(sub, src, cfg)
    last.cook(force=True)
    sound_corners = sum(last.geometry().pointIntAttribValues("pc_iscorner"))
    nodes["pc_unshare"].bypass(True)
    last.cook(force=True)
    shared_corners = sum(last.geometry().pointIntAttribValues("pc_iscorner"))
    curves, _m = P.read_curves(fused["curve"])
    want = sum(len(D.resolve_corners(c, DEFAULTS)) for c in curves)
    check("mutation_pc_unshare",
          sound_corners == want and shared_corners != want,
          "%d -> %d (reference %d)" % (sound_corners, shared_corners, want),
          "bypassing the unshare on a FUSED junction loses the corner the "
          "reference finds - which is what the node is for (D165)")
    sub.destroy()


# --- 5: 13.7's readability rules, on the BUILT asset ------------------------

def readability(root):
    hou.hda.installFile(HDA_PATH)
    # ⚠️ WITH NOTHING ON INPUT 1 EVERY STAGE COOKS TO NOTHING, and the menu
    # check below then passes or fails for the wrong reason. A spline is the
    # asset's own standalone-usability floor (6): a curve and nothing else.
    spline = root.createNode("python", "readable_spline")
    spline.parm("python").set(
        "import hou\n"
        "geo = hou.pwd().geometry()\n"
        "poly = geo.createPolygon(False)\n"
        "for p in ((0, 0, 0), (12, 0, 0), (12, 0, 8)):\n"
        "    pt = geo.createPoint()\n"
        "    pt.setPosition(p)\n"
        "    poly.addVertex(pt)\n")
    # ⚠️ THE COST OF SHIPPING UNLOCKED, AS A STANDING MEASUREMENT. Until this
    # cycle the asset carried `setUnlockNewInstances(True)`, which makes every
    # instance materialise its own private copy of the whole network. Measured
    # at citygen scale, 300 chain nodes in one scene: 2.056 s to create and a
    # 20.7 MB .hip unlocked, 0.096 s and 0.72 MB locked, 6 000 child nodes
    # against 0 - and `matchesCurrentDefinition()` False on a FRESH instance,
    # so every scene saved during the rebuild would fork the half-built graph
    # and never receive the rest of it. Twenty instances is enough to catch
    # the flag coming back.
    fleet = [root.createNode("pf_polychain", "fleet%02d" % i)
             for i in range(20)]
    kids = sum(len(n.children()) for n in fleet)
    forked = [n.name() for n in fleet if not n.matchesCurrentDefinition()]
    for n in fleet:
        n.destroy()
    check("instances_do_not_fork_the_network", not kids and not forked,
          "%d children / %d forked" % (kids, len(forked)),
          "20 untouched instances materialise no children and all track the "
          "definition (unlocked: 400 children and 20 forked)")

    node = root.createNode("pf_polychain", "readable")
    node.setInput(0, spline)

    # ⚠️ TOUCH THE CONTENTS FIRST. A LOCKED HDA loads its children lazily, so
    # `children()`, `networkBoxes()` and `stickyNotes()` all read EMPTY on a
    # fresh instance until something asks for a child - which is the whole of
    # the trap that used to be written up as "network boxes do not survive the
    # save unless the asset ships unlocked". One `node("OUT")` is the fix, and
    # the asset ships locked because of it.
    node.node("OUT")
    inside = dict((b.name(), b.comment()) for b in node.networkBoxes())
    check("locked_instance_shows_its_network", len(inside) >= 5
          and len(node.stickyNotes()) >= 1 and node.matchesCurrentDefinition(),
          "%d boxes / %d notes" % (len(inside), len(node.stickyNotes())),
          "13.7 rule 2 on a LOCKED instance, after one child access; "
          "matchesCurrentDefinition = %s (an UNLOCKED instance reports False "
          "the moment it is created and never sees a later fix)"
          % node.matchesCurrentDefinition())

    boxes = dict((b.name(), b.comment()) for b in node.networkBoxes())
    check("every_stage_is_a_network_box", len(boxes) >= 5, len(boxes),
          "titled boxes: %s" % ", ".join(sorted(boxes)))

    nulls = sorted(c.name() for c in node.children()
                   if c.type().name() == "null" and c.name().startswith("OUT_"))
    check("every_stage_ends_in_a_named_null", len(nulls) >= 4,
          len(nulls), "an artist can drop a display flag on: %s"
          % ", ".join(nulls))

    wrangles = [c for c in node.children()
                if c.type().name() == "attribwrangle"]
    silent = [w.name() for w in wrangles if not (w.comment() or "").strip()]
    check("every_wrangle_says_what_it_computes", not silent, len(wrangles),
          "no comment on: %s" % (", ".join(silent) or "none"))

    # 13.7 rule 4 - copied `foreach` blocks keeping ABSOLUTE blockpath is a
    # recorded trap, and an absolute reference anywhere breaks an asset the
    # moment it is instantiated under a different parent.
    absolute = []
    for child in node.children():
        for parm in child.parms():
            try:
                expr = parm.expression()
            except hou.OperationFailed:
                continue
            if "/obj/" in expr or node.path() in expr:
                absolute.append("%s/%s" % (child.name(), parm.name()))
    check("no_absolute_node_paths", not absolute, len(absolute),
          "absolute references: %s" % (", ".join(absolute) or "none"))

    # D155 - the Stage menu and the switch's inputs are ONE list or they are
    # a lie; every entry must actually cook and produce something.
    #
    # ⚠️ AND UNDER MORE THAN ONE PARM STATE. This used to sweep the menu at
    # the DEFAULTS only, and the defaults are what hid the finding: with any
    # non-zero Corner Rounding every plan row is `pc_frame_valid = 0`, the
    # blast drops all of them, and the Frames stage cooked to 0 points with no
    # error and no warning. A stage is allowed to come back EMPTY - it is not
    # allowed to come back empty and silent (warn-never-block).
    tokens = list(node.parm("stage").parmTemplate().menuItems())
    states = (("defaults", {}),
              ("fillet_2m", {"fillet_radius": 2.0}),
              ("mitred_corners", {"corner_mode": "miter",
                                  "fillet_radius": 0.0}))
    silent = []
    for label, parms in states:
        for name, value in parms.items():
            node.parm(name).set(value)
        for token in tokens:
            node.parm("stage").set(token)
            node.cook(force=True)
            geo = node.geometry()
            if node.errors():
                silent.append("%s/%s(error)" % (label, token))
            elif not (len(geo.points()) or len(geo.prims())):
                # empty is legal; empty and wordless is not
                said = node.warnings() or any(
                    c.warnings() for c in node.children())
                if not said:
                    silent.append("%s/%s(empty+silent)" % (label, token))
        for name in parms:
            node.parm(name).revertToDefaults()
    node.parm("stage").set(tokens[0])
    check("stage_menu_reaches_every_stage", not silent,
          "%d x %d" % (len(states), len(tokens)),
          "every stage under %d parm states; empty AND wordless: %s"
          % (len(states), ", ".join(silent) or "none"))

    # ⚠️ THE RIG AND THE ASSET ARE TWO INDEPENDENT DECLARATIONS OF ONE CHAIN,
    # and until this check they were only asserted to share their .vfl bodies.
    # `native.stage_decompose` wires the rig; `create_pf_polychain_hda.py`'s
    # own `DECOMPOSE` tuple wires the asset. §15.1 claimed "the network the
    # checks measure IS the network the asset ships" - it was not true, and an
    # audit proved it by BYPASSING `pc_unshare` in the shipped asset: all four
    # suites stayed green, because `mutation_pc_unshare` bypasses the RIG's
    # copy. Bypassing the `pc_frames_valid` blast was invisible the same way.
    # So every property that decides what a stage COMPUTES is compared here,
    # and nothing in the asset is allowed to ship bypassed.
    sub = root.createNode("subnet", "rig_vs_asset")
    probe = hou.Geometry()
    cases.polyline(probe, [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], curve_id="A")
    cfg_stub = native.config_stub(sub, DEFAULTS)
    _last, rig = native.stage_decompose(
        sub, native.feed(sub, probe, "IN"), cfg_stub)
    # 13.9 N2 - and the PLAN chain, for exactly the same reason.
    _plast, plan_rig = native.stage_plan(sub, _last, cfg_stub, "_rig")
    for _n, _node in plan_rig.items():
        rig[_n] = _node
    # 13.9 N4 - and the PLACE branch. `kit_code` is the asset's own
    # `kit_starter` body, so the comparison includes that node too.
    _qlast, place_rig = native.stage_place(
        sub, _plast, cfg_stub, native.feed(sub, hou.Geometry(), "KITIN"),
        _last, "_rig", kit_code=native.sop_body("cook_kit"))
    for _n, _node in place_rig.items():
        rig[_n] = _node
    # D203 - and the WIRING, not only the parameters.  `OUT_frames` re-pointed
    # from `pc_frames_valid` to `pc_frames` was 94 [PASS] / 0 green: this
    # comparison read every parm that decides what a node COMPUTES and never
    # asked what any node was FED BY, and the comment above claims the
    # `isBypassed()` scan closed that - it does not, because an unplug is not
    # a bypass.  A NULL is walked through on the asset side: the asset taps
    # each stage with an `OUT_*` null the rig has no counterpart for, and a
    # null is a display tap, not logic.
    by_path = dict((n.path(), name) for name, n in rig.items())

    def through_nulls(n):
        for _hop in range(8):
            if n is None or n.type().name() != "null":
                return n
            ins = n.inputs()
            n = ins[0] if ins else None
        return n

    wired = [0]

    def compare(target):
        """The rig against `target`, recomputed - so the WIRING half can be
        shown to bite instead of asserted to."""
        drift = []
        wired[0] = 0
        for rig_name, rig_node in sorted(rig.items()):
            mine = target.node(rig_name)
            if mine is None:
                drift.append("%s: absent from the asset" % rig_name)
                continue
            mine_ins = mine.inputs()
            for slot, feeder in enumerate(rig_node.inputs()):
                want = by_path.get(feeder.path()) if feeder is not None \
                    else None
                if want is None:
                    continue      # the rig feeds this slot from a stub or a
                                  # `feed` node the asset has no twin for
                wired[0] += 1
                got = through_nulls(mine_ins[slot]) \
                    if slot < len(mine_ins) else None
                got = got.name() if got is not None else None
                if got != want:
                    drift.append("%s input %d <- %s (rig %s)"
                                 % (rig_name, slot, got, want))
            drift += parm_drift(rig_name, mine, rig_node)
        bypassed = sorted(c.name() for c in target.children()
                          if c.isBypassed())
        return drift + ["%s(bypassed)" % n for n in bypassed], bypassed

    def parm_drift(rig_name, mine, rig_node):
        drift = []
        if mine.type().name() != rig_node.type().name():
            drift.append("%s: %s vs rig %s"
                         % (rig_name, mine.type().name(),
                            rig_node.type().name()))
        # `nptsperpt` and `ptsperpt` are on the list because 13.2 measured
        # that the count attribute MULTIPLIES `nptsperpt` - an asset shipping
        # the default 10 would plan ten fences and nothing else would notice.
        for parm in ("class", "vex_precision", "snippet", "ptdel", "group",
                     "grouptype", "negate", "ptsperpt", "nptsperpt",
                     "doattrib", "attrib", "spointnum", "spointidx",
                     "docopyattribs", "attribstocopy",
                     # `attribcast` decides the OUTPUT's storage width, which
                     # is a parity property: 64 bits in `pc_u` is a different
                     # number from what 3.4 ships.
                     "class1", "attribs1", "precision1", "typeinfo1"):
            a, b = mine.parm(parm), rig_node.parm(parm)
            if (a is None) != (b is None):
                drift.append("%s.%s: one side has it" % (rig_name, parm))
            elif a is not None and a.eval() != b.eval():
                drift.append("%s.%s differs" % (rig_name, parm))
        return drift

    drift, bypassed = compare(node)
    # D203 - AND THE WIRING HALF IS MUTATION-PROVED HERE, not asserted.  A
    # comparison that quietly stops comparing anything is the shape this suite
    # has found six times, and `want is None` skipping every slot would do
    # exactly that in silence.  `pc_place_valid` is fed from `pc_frames_native`
    # in both declarations; feeding it from `pc_deform_gate` instead is an
    # intra-stage unplug of precisely the kind an `isBypassed()` scan cannot
    # see, and it has to be reported.
    # ON ITS OWN UNLOCKED INSTANCE: `node` is the LOCKED one, which is what
    # `locked_instance_shows_its_network` is about, and a locked asset refuses
    # `setInput` outright.
    mut = root.createNode("pf_polychain", "rigwire_mutation")
    mut.allowEditingOfContents()
    mut.node("pc_place_valid").setInput(0, mut.node("pc_deform_gate"))
    mutated, _b = compare(mut)
    mut.destroy()
    restored, _b = compare(node)
    check("asset_stages_match_the_rig", not drift and not restored,
          "%d nodes / %d wires / %d bypassed"
          % (len(rig), wired[0], len(bypassed)),
          "class, VEX precision, snippet, node type, the parameters that "
          "decide what it computes AND the input each node is fed by, for "
          "every stage the parity rig measures, read back off the SHIPPED "
          "asset, plus every bypassed node in it: %s"
          % (", ".join(drift) or "none"))
    check("asset_wiring_comparison_is_load_bearing",
          any("pc_place_valid input 0" in d for d in mutated),
          "%d complaints" % len(mutated),
          "feeding `pc_place_valid` from `pc_deform_gate` instead of "
          "`pc_frames_native` - an intra-stage UNPLUG, which is not a bypass "
          "and which the parameter-only comparison could not see - must be "
          "reported. Got: %s" % ("; ".join(mutated[:2]) or "NOTHING")) 

    # D205 - THE STICKY NOTE IS THE FIRST THING AN ARTIST READS, AND IT SAID
    # THE OPPOSITE OF THIS BUILD.  It called 13.9 N5's deform gate and N7's
    # finalize NOT STARTED while `pc_deform_gate` and `pc_finalize` were both
    # in the network and both cooking on an admitted build, and it said
    # `Stage = output` is `kernel` when `output` is the guard switch.
    # `every_wrangle_says_what_it_computes` only asserts a comment is
    # non-empty, so nothing could see it.  This reads the note back off the
    # BUILT .hda and refuses to let it call a stage unstarted whose nodes are
    # standing in the network - the shape `place_stamp_owed_is_live` uses.
    note = "\n".join(n.text() for n in node.stickyNotes())
    rotten = note_rot(node, note)
    nchildren = len(node.children())
    # AND IT IS MUTATION-PROVED, on the note this build REPLACED: the previous
    # cycle's text called N5's deform gate and N7's finalize NOT STARTED while
    # both nodes were standing in the network and cooking, and said
    # `Stage = output` is `kernel`.  Nothing could see it.  Feeding that exact
    # text back in has to produce all three complaints.
    stale = ("  4.4  the DEFORM gate      N5  NOT STARTED - so every piece\n"
             "  4.6  finalize + guards    N7  NOT STARTED - D153\n"
             "STAGE STILL DEFAULTS TO `output`, WHICH IS `kernel`.\n")
    caught = note_rot(node, stale)
    check("the_note_matches_the_build", not rotten and len(caught) >= 3,
          "%d chars / %d nodes" % (len(note), nchildren),
          "13.7's readability deliverable read back off the SHIPPED .hda: no "
          "13.9 item is called NOT STARTED while its nodes stand in the "
          "network, the note agrees with what `Stage = output` is wired to, "
          "and the build script's headline node count is this asset's - "
          "with the note this build REPLACED fed back in as the mutation "
          "(%d complaints, needs 3). Rotten: %s"
          % (len(caught), "; ".join(rotten) or "none"))

    # D203 - AND THE SWITCH'S INPUTS, AGAINST `native.STAGES` COLUMN BY
    # COLUMN.  The menu sweep above only requires an entry to COOK; it says
    # nothing about which node the entry is wired to, and three mutations of
    # the shipped asset proved that gap is not theoretical - see `STAGES`.
    wiring = stage_wiring_complaints(node)
    check("every_stage_entry_serves_the_node_it_names", not wiring,
          "%d entries" % len(native.STAGES),
          "every `Stage` menu entry is wired to the null it NAMES, and that "
          "null is fed by the node the declaration says feeds it - the two "
          "halves of D203. Wrong: %s" % ("; ".join(wiring) or "none"))

    # 13.7 rule 5 - a group-name collision between two stages silently
    # corrupts one of them, so every working group carries the prefix.
    # ⚠️ IT READS THE INNER NODE, NOT THE OUTPUT, AND IT HAS TO NOW.
    # `_scrub_groups` deletes `_*` before OUT (conventions.md 5), so asking
    # the OUTPUT what groups it carries would be asking a question whose
    # answer is "none" whatever the stages do - the unfailable shape. The
    # group is asserted where it is CREATED, and the law's other half - that
    # nothing `_*` reaches the output - is `tests/hda/run_attrib_checks.py`.
    node.parm("stage").set("sections")
    node.cook(force=True)
    groups = [g.name() for g in node.node("pc_corners").geometry().pointGroups()]
    stray = [g for g in groups if not g.startswith("_")]
    out_groups = [g.name() for g in node.geometry().pointGroups()
                  if g.name().startswith("_")]
    stray += ["%s ON THE OUTPUT" % g for g in out_groups]
    check("working_groups_are_prefixed", not stray, len(groups),
          "unprefixed: %s" % (", ".join(stray) or "none"))
    node.parm("stage").set("output")

    # D207 - and the two bodies of text that make CHECKABLE claims about this
    # graph and were only ever asserted to be non-empty.
    text_claims_are_true(node)
    return node


# --- D207: TEXT THAT MAKES A CLAIM ABOUT THE BUILD IS A CHECK, NOT A COMMENT
#           ---------------------------------------------------------------
#
# §21.4's SURVIVOR 2, reproduced at SOURCE this cycle: `native.STAGES`' two
# "via the PYTHON BRIDGE" labels re-worded back to "NATIVE", the .hda REBUILT
# (md5 37f1e344 -> 34fbd13a), and the asset ships a Stage menu offering **two
# entries labelled `2 - Plan, NATIVE` and two labelled `4 - Frames, NATIVE`**,
# one of each serving the dead Python bridge - with `run_native_checks` at
# **111 [PASS] / 0** and `run_hda_checks` at 0.  `stage_menu_reaches_every
# _stage` asserts a label is neither empty nor wordless; `every_stage_entry
# _serves_the_node_it_names` asserts wiring and never text.  D205's fix got
# `the_note_matches_the_build`; the menu labels, the other half of the same
# finding, got nothing, and neither did the eighteen wrangle comments.
#
# THE RULE ADOPTED: a claim token in artist-facing text is verified against
# the GRAPH, and the verification is independent of the declaration the text
# comes from (which is D208's lesson applied here in advance - reading
# `native.STAGES` to check a label built from `native.STAGES` would prove
# nothing).
#
# ⚠️ `config` AND `kit_starter` ARE EXCLUDED FROM "IS THERE PYTHON UPSTREAM",
# BY NAME AND WITH REASONS, because both sit upstream of nearly everything:
#   `config`      §13.6 - UI marshalling, no geometry, and it STAYS. It is
#                 wired into input 1 of most wrangles, so counting it would
#                 make every NATIVE label a lie and the check a nuisance.
#   `kit_starter` D154 - the standalone-kit fallback, and it should NOT be
#                 Python. It is named here rather than silently skipped, so
#                 when D154 lands this list gets shorter.
# Everything else that cooks Python on a branch makes a NATIVE label on that
# branch false.
STAGE_PYTHON_EXEMPT = ("config", "kit_starter")

# The class a wrangle's own header claims, and the class it is.  Every .vfl
# opens with a line naming its wrangle class; nothing read it until now.
WRANGLE_CLASS_WORD = {0: "DETAIL", 1: "PRIMITIVE", 2: "POINT", 3: "VERTEX"}


def _python_upstream(node, start):
    """Every Python SOP at or above `start` inside the asset, minus the two
    named exemptions.  Depth-first over `inputs()`, which is what an artist
    tracing a branch backwards would do."""
    # ⚠️ THE WALK STOPS AT THE ASSET BOUNDARY, and the first version did not:
    # `readability` feeds the node from a `python` SOP that builds its test
    # spline, so the walk climbed out through the indirect inputs and reported
    # four NATIVE labels as lying about `readable_spline`. A claim a label
    # makes is about the network the label is IN.
    seen, found, stack = set(), set(), [start]
    while stack:
        cur = stack.pop()
        if cur is None or cur.path() in seen or cur.parent() != node:
            continue
        seen.add(cur.path())
        if (cur.type().name() == "python"
                and cur.name() not in STAGE_PYTHON_EXEMPT):
            found.add(cur.name())
        stack.extend(cur.inputs())
    return sorted(found)


def stage_label_complaints(node, labels):
    """What each `Stage` menu label claims that this graph contradicts.

    Pure with respect to the LABELS - they are passed in - so §21.4's M8 can
    be replayed without rebuilding the .hda, the way `run_scene_checks
    .exit_code` and `wrangle_verdict` are exercised.
    """
    bad = []
    stems = {}
    for (token, _null, feeder, _decl), label in zip(native.STAGES, labels):
        stem = label.split("(")[0].strip().rstrip(",").strip()
        stems.setdefault(stem, []).append(token)
        if feeder is None:
            continue
        start = node.node(feeder)
        if start is None:
            bad.append("%s: no node named %s" % (token, feeder))
            continue
        python = _python_upstream(node, start)
        upper = label.upper()
        # ⚠️ "NO PYTHON" IS A NATIVE CLAIM, NOT A PYTHON ONE, and the first
        # version of this check did not know that: `4 - Place, NATIVE (4.4 -
        # packed pieces, no Python)` was reported as claiming PYTHON on a
        # branch that has none. A negated claim read as its opposite is a
        # false alarm, and a check that cries wolf on a correct build is the
        # same disease as one that cannot fail (D209).
        claims_native = "NATIVE" in upper or "NO PYTHON" in upper
        claims_python = re.search(r"(?<!NO )PYTHON", upper) is not None
        if claims_native and python:
            bad.append("%s claims NATIVE and its branch cooks %s"
                       % (token, ", ".join(python)))
        if claims_python and not python:
            bad.append("%s claims PYTHON and there is none on its branch"
                       % token)
    for stem, tokens in sorted(stems.items()):
        if len(tokens) > 1:
            bad.append("%d entries read %r: %s"
                       % (len(tokens), stem, ", ".join(tokens)))
    return bad


def wrangle_comment_complaints(node):
    """What each wrangle's own text claims that the built node contradicts.

    Three claims, all of them already written in the .vfl headers and none of
    them read by anything until now:

      * the CLASS - every header opens by naming it, and it must be the
        class parm.  Required, not optional: a header that names no class is
        a comment that cannot lie and cannot help either.
      * the PRECISION, where the header states one (`precision 64`,
        `VEX precision 64`, `DETAIL wrangle, 64`).
      * the INPUTS - a header line `//   input N  ...` must describe an input
        that is actually connected, which is what turns an UNPLUG into a
        contradiction instead of a silence.

    ⚠️ ONLY THE HEADER IS READ, not the whole snippet, and that is
    deliberate: the body comments discuss OTHER nodes' classes ("`pc_plan
    _emit` above HAS to be single-threaded... a DETAIL wrangle") and a
    checker that matched those would fail on correct text.  The header is the
    contiguous run of `//` lines the file opens with.
    """
    bad = []
    for child in sorted(node.children(), key=lambda c: c.name()):
        if child.type().name() != "attribwrangle":
            continue
        header = []
        for line in (child.parm("snippet").eval() or "").splitlines():
            if not line.startswith("//"):
                break
            header.append(line)
        head = "\n".join(header)
        name = child.name()
        if not head:
            bad.append("%s: the .vfl opens with no header" % name)
            continue

        want = WRANGLE_CLASS_WORD[child.parm("class").eval()]
        claimed = re.findall(r"\b(DETAIL|PRIMITIVE|POINT|VERTEX)\s+wrangle",
                             head)
        if not claimed:
            bad.append("%s: the header names no wrangle class" % name)
        elif claimed[0] != want:
            bad.append("%s: the header says %s, the node is %s"
                       % (name, claimed[0], want))

        prec = re.findall(r"precision\s+(\d+)|wrangle,\s+(\d+)\b", head)
        prec = [p or q for p, q in prec]
        real = child.parm("vex_precision").evalAsString()
        if prec and prec[0] != real:
            bad.append("%s: the header says precision %s, the node is %s"
                       % (name, prec[0], real))

        # ⚠️ THE INPUT PATTERN IS EXACT, AND IT HAS TO BE. A loose
        # `input\s+(\d)` matched `pc_envelope`'s line 44 - which QUOTES the
        # reference's warning text, "no spline on input 1" - and reported a
        # correct build as declaring an input it does not have. The two forms
        # the headers actually use are the indented block and the inline
        # parenthesis; anything else is prose.
        decls = (set(re.findall(r"^//   input (\d)  ", head, re.M))
                 | set(re.findall(r"input (\d) = ", head)))
        for idx in sorted(decls):
            wired = child.inputs()
            i = int(idx)
            if i >= len(wired) or wired[i] is None:
                bad.append("%s: the header declares input %s and nothing is "
                           "wired there" % (name, idx))
    return bad


def text_claims_are_true(node):
    """D207 - the two bodies of artist-facing text that make CHECKABLE claims.

    `the_note_matches_the_build` did this for the sticky note, on one string.
    These are the other two: ten `Stage` menu labels and eighteen wrangle
    headers, all of which said NATIVE / PYTHON / DETAIL / `input 2` and none
    of which anything read.
    """
    labels = list(node.parm("stage").parmTemplate().menuLabels())
    bad = stage_label_complaints(node, labels)
    # ...and the exemptions have to still BE Python, or they are decoration.
    # `place_stamp_owed_is_live`'s shape: when D154 turns `kit_starter` into
    # native `box` SOPs, this line fails and the exemption has to come out,
    # rather than sitting in the source forgiving a node that no longer needs
    # forgiving.
    dead = [n for n in STAGE_PYTHON_EXEMPT
            if node.node(n) is None or node.node(n).type().name() != "python"]
    check("stage_labels_are_true", not bad and not dead,
          "%d labels" % len(labels),
          "every `Stage` label's NATIVE / PYTHON claim is verified against "
          "the Python SOPs actually upstream of the node it serves (bar %s - "
          "§13.6 and D154), and no two entries read the same. Wrong: %s. "
          "Exemptions that are no longer Python SOPs and must be deleted: %s"
          % (" and ".join(STAGE_PYTHON_EXEMPT), "; ".join(bad) or "none",
             dead or "none"))

    # §21.4's M8, replayed on the labels alone - the source mutation rebuilds
    # the .hda, this reproduces the same text without one.
    m8 = [lbl.replace("via the PYTHON BRIDGE", "NATIVE") for lbl in labels]
    caught = stage_label_complaints(node, m8)
    check("mutation_stage_labels_claim_native",
          len(caught) >= 4 and m8 != labels,
          "%d complaints" % len(caught),
          "re-wording the two 'via the PYTHON BRIDGE' labels back to NATIVE - "
          "§21.4's SURVIVOR 2, which rebuilt the .hda and left the suite at "
          "111 [PASS] / 0 - must be reported, both as a false NATIVE claim "
          "and as two menu entries reading the same. Got: %s"
          % ("; ".join(caught) or "NOTHING"))

    bad = wrangle_comment_complaints(node)
    wrangles = [c for c in node.children()
                if c.type().name() == "attribwrangle"]
    check("every_wrangle_comment_is_checkable", not bad, len(wrangles),
          "every wrangle's own header names its CLASS and it is the node's "
          "class, any precision it states is the node's precision, and every "
          "`input N` it declares is wired - so a comment that lies is a "
          "failing check and not an invisible one. Wrong: %s"
          % ("; ".join(bad) or "none"))


def note_rot(node, note):
    """What the sticky note claims that this build contradicts.

    ⚠️ 13.7's READABILITY DELIVERABLE IS THE FIRST THING AN ARTIST READS ON
    OPENING THE NETWORK, AND IT ROTTED (D205).  The text shipped on the build
    before this one called 13.9 N5's deform gate and N7's finalize NOT STARTED
    while `pc_deform_gate` and `pc_finalize` were both in the network and both
    cooking on an admitted build, and said `Stage = output` is `kernel` when
    `output` is the guard switch.  `every_wrangle_says_what_it_computes` only
    asserts that a comment is non-EMPTY, so an artist toggling
    `pc_deform_gate` off to see what it does was being told by the network
    that the node does not exist yet.

    The shape is `place_stamp_owed_is_live`'s: the claim is read back off the
    BUILT .hda and checked against the graph it describes.
    """
    rotten = []
    for item, owned in (("N5", ("pc_deform_gate",)),
                        ("N6", ()),
                        ("N7", ("pc_finalize", "pc_stamp", "pc_out_cast")),
                        ("N8", ())):
        if not [ln for ln in note.splitlines()
                if item in ln and "NOT STARTED" in ln.upper()]:
            continue
        standing = [n for n in owned if node.node(n) is not None]
        if standing:
            rotten.append("%s is called NOT STARTED and %s is in the network"
                          % (item, ", ".join(standing)))
    # the other half of the same rot: what `Stage = output` IS.
    final = node.node("OUT_final")
    fed_by = final.inputs()[0].name() if final is not None and final.inputs() \
        and final.inputs()[0] is not None else "?"
    if "WHICH IS `kernel`" in note and fed_by != "kernel":
        rotten.append("the note says `Stage = output` is `kernel`, and "
                      "OUT_final is fed by %s" % fed_by)
    # and the build script's own headline node count.
    src = io.open(os.path.join(REPO, "devScripts",
                               "create_pf_polychain_hda.py"),
                  encoding="utf-8").read()
    claimed = re.search(r"pf_polychain\s+(\d+) nodes", src)
    if claimed is None or int(claimed.group(1)) != len(node.children()):
        rotten.append("the build script's docstring says %s nodes and the "
                      "asset has %d"
                      % (claimed.group(1) if claimed else "no",
                         len(node.children())))
    return rotten


def stage_wiring_complaints(node):
    """Every `Stage` entry of `node`, against `native.STAGES`, column by
    column.  Returns a list of complaints; empty is the sound build.

    ⚠️ THIS IS THE ASSERTION THE CYCLE'S HEADLINE CHECK WAS RESTING ON AND DID
    NOT HAVE.  `output_guard_parity`'s ORACLE is the `Stage = reference`
    switch input, and nothing asserted what that input was wired to: moving it
    onto `OUT_final` turned the whole parity proof into a comparison of the
    guarded native output WITH ITSELF over all 92 cases, and the suite stayed
    at 94 [PASS] / 0 while `output_guard_cost`'s spread collapsed from
    0.99-1.39x to four ratios of a node against itself.

    Two columns, because a repoint and an UNPLUG are different mutations and
    the second is the one `asset_stages_match_the_rig`'s `isBypassed()` scan
    structurally cannot see.
    """
    switch = node.node("stage_switch")
    if switch is None:
        return ["stage_switch is absent"]
    ins = switch.inputs()
    bad = []
    for i, (token, null, feeder, _label) in enumerate(native.STAGES):
        got = ins[i].name() if i < len(ins) and ins[i] is not None else None
        if got != null:
            bad.append("%s -> %s (want %s)" % (token, got, null))
        target = node.node(null)
        if target is None:
            bad.append("%s: %s is absent from the asset" % (token, null))
            continue
        if feeder is None:
            continue                      # `config` is a SOP, not a tapped null
        tins = target.inputs()
        fed = tins[0].name() if tins and tins[0] is not None else None
        if fed != feeder:
            bad.append("%s <- %s (want %s)" % (null, fed, feeder))
    return bad


def stage_wiring_mutation(root):
    """The four repoints that were all 94 [PASS] / 0 green, each proved to
    redden the check above.

    Rows 1-3 move a switch input onto another stage's null (w20, w3, w2); row
    4 leaves the switch alone and UNPLUGS a stage's own output null from the
    node that feeds it (w18) - the mutation the parameter-only rig comparison
    cannot see, because an unplug is not a bypass.
    """
    rows = []
    for tag, kind, where, target in (
            ("reference_entry_serves_the_output", "switch", 1, "OUT_final"),
            ("output_entry_serves_the_reference", "switch", 0, "OUT_reference"),
            ("frames_entry_serves_the_reference", "switch", 6, "OUT_reference"),
            ("out_frames_skips_the_blast", "feeder", "OUT_frames",
             "pc_frames")):
        node = root.createNode("pf_polychain", "wiremut_%s" % tag)
        node.allowEditingOfContents()
        if kind == "switch":
            node.node("stage_switch").setInput(where, node.node(target))
        else:
            node.node(where).setInput(0, node.node(target))
        bad = stage_wiring_complaints(node)
        rows.append((tag, bool(bad), bad[0] if bad else "STAYED GREEN"))
        node.destroy()
    check("mutation_stage_wiring", all(r[1] for r in rows),
          "%d/%d caught" % (sum(1 for r in rows if r[1]), len(rows)),
          "each of the four menu-repoint / unplug mutations that survived a "
          "94-PASS suite must be reported by "
          "`every_stage_entry_serves_the_node_it_names`. %s"
          % "; ".join("%s: %s" % (r[0], r[2]) for r in rows))


# --- 6: cook count and the two benches --------------------------------------

# D211 - the floor under both `decompose_*_wall_clock` rows.  20 ms is
# `GUARD_COST_FLOOR_S`, and it is the same number for the same reason: below
# it a ratio is measuring the scheduler.
BENCH_FLOOR_S = 0.02
# ...and the curve count that clears it on this shape.  3-point streets cost
# ~5 us each on the reference's best side, so 300 of them were 1.5 ms; 6 000
# measure 30-35 ms and the row reads 0.9-1.1x with a spread of a few percent
# instead of a few tens of percent.
BENCH_STREETS = 6000


def benches(root, node):
    """ONE LONG CURVE and THREE HUNDRED SHORT ONES.

    11.9 rule 2 said a per-CALL fixed cost is invisible on a one-call fixture.
    In a network it comes back as a per-NODE fixed cost, and 300 streets pay
    it 300 times where one 20 km fence pays it once. Benching only the fence
    is how that goes unnoticed until an artist opens a city.
    """
    # 13.2's own fixture: 20 km at 1 m spacing, 20 001 vertices. THE POINT
    # COUNT IS THE POINT - at 2 000 vertices the native chain measured only
    # 1.1x the reference, because five nodes each pay a fixed cost that one
    # Python call pays once. R7 is real and it is visible here.
    long_curve = hou.Geometry()
    cases.polyline(long_curve, cases.arc_points(20000.0, 1.0, 20000.0),
                   curve_id="LONG")
    # ⚠️ THE CURVE COUNT IS `BENCH_STREETS` AND IT USED TO BE 300, WHICH IS
    # D211 APPLIED TO A ROW D209 MISSED.  D209 fixed the ESTIMATOR on both
    # `decompose_*_wall_clock` rows - they are interleaved now - and gave
    # `output_guard_cost` a 20 ms floor, but this row was left resting on a
    # **1.3-2.6 ms** fixture.  Observed on an UNMUTATED build across four
    # consecutive runs: 0.53x, 0.92x, 0.94x, 1.12x against a ceiling that
    # needs > 0.667x, and the 0.53x run went RED.  That is D209's defect
    # exactly - the estimator was cured and the SIZE was not - and D211 is
    # the rule it broke: a timing check declares the size it rests on and
    # fails below it.  The count is raised rather than the points per curve,
    # because the whole point of this fixture is 11.9 rule 2's PER-CURVE
    # fixed cost: 3-point streets are what multiply it, and lengthening them
    # would measure something else.
    streets = hou.Geometry()
    for i in range(BENCH_STREETS):
        x = (i % 20) * 30.0
        z = (i // 20) * 25.0
        cases.polyline(streets, [(x, 0.0, z), (x + 18.0, 0.0, z),
                                 (x + 18.0, 0.0, z + 14.0)],
                       curve_id="S%04d" % i)

    for label, geo in (("long_curve", long_curve),
                       ("streets_%d" % BENCH_STREETS, streets)):
        sub = root.createNode("subnet", "bench_" + label)
        src = native.feed(sub, geo, "IN")
        # ⚠️ `cook(force=True)` IS NOT A MEASUREMENT. 13.2's OpenCL probe was
        # thrown away this cycle for exactly this: its kernel cooked ONCE
        # across six timed passes, so the number it produced was not
        # evidence. Forcing a node whose inputs have not changed can be a
        # no-op, and the first version of this bench reported 0.00002 s for a
        # 20 001-vertex chain because of it. The chain is dirtied through a
        # spare int the wrangle below actually reads, and `cookCount` is
        # asserted to have advanced once per pass - so the number IS what was
        # cooked.
        dirt = sub.createNode("attribwrangle", "bench_dirty")
        dirt.parm("class").set(0)
        group = dirt.parmTemplateGroup()
        group.append(hou.IntParmTemplate("nudge", "Nudge", 1))
        dirt.setParmTemplateGroup(group)
        dirt.parm("snippet").set('i@pc_bench = chi("nudge");')
        dirt.setInput(0, src)
        cfg = native.config_stub(sub, DEFAULTS)
        last, nodes = native.stage_decompose(sub, dirt, cfg)
        last.cook(force=True)
        before = dict((n, node.cookCount()) for n, node in nodes.items())
        passes = 4
        from polyfactory.polychain import decompose as D
        curves, markers = P.read_curves(geo)

        # ⚠️ D209 - ALL THREE VARIANTS ARE INTERLEAVED NOW, and they used to
        # be three separate blocks. `decompose_long_curve_wall_clock` went red
        # once under an unrelated mutation for exactly that reason: the
        # comparand and the measurement never saw the same machine. See
        # `interleaved_best`.
        state = {"i": 1}

        def _dirty():
            state["i"] += 1
            dirt.parm("nudge").set(state["i"])

        def _native():
            last.cook()

        def _ref_best():
            for curve in curves:
                D._clean(curve)
                D.resolve_corners(curve, DEFAULTS)
                D.resolve_markers(curve, markers)
                curve._cum = None       # the cache would make run 2 free

        def _ref_full():
            fresh_curves, fresh_marks = P.read_curves(geo)
            for curve in fresh_curves:
                D._clean(curve)
                D.resolve_corners(curve, DEFAULTS)
                D.resolve_markers(curve, fresh_marks)

        timed = interleaved_best(
            [("native", _dirty, _native),
             ("ref_best", None, _ref_best),
             ("ref_full", None, _ref_full)], reps=passes)
        best, ref_best, ref_full = (timed["native"], timed["ref_best"],
                                    timed["ref_full"])
        stale = sorted(n for n, node in nodes.items()
                       if node.cookCount() - before[n] != passes)
        check("bench_%s_really_cooked" % label, not stale, passes,
              "nodes whose cookCount did not advance once per timed pass: %s"
              % (", ".join(stale) or "none"))
        out = last.geometry()
        # THE COMPARAND, in the same process, on the same geometry: what the
        # REFERENCE spends answering the same question. Without it the wall
        # clock above is a number with nothing to be better than - and D115's
        # headline was wrong for exactly that reason, so the comparand is
        # spelled out rather than remembered.
        # ⚠️ TWO COMPARANDS, BECAUSE ONE OF THEM IS A CHOICE AND THE CHOICE
        # WAS BEING REPORTED AS THE NUMBER. `read_curves` is the geometry
        # read the reference CANNOT avoid to reach these answers, and the
        # native chain does not need it - but the reference amortises it
        # across plan, place and conform, so charging 100 % of it to stage 1
        # is not right either. Measured here: it is 48 % of the reference's
        # real cost on the 20 km curve and 79 % on 300 streets, which is the
        # difference between "0.81x" and "1.53x" on the same build. The
        # honest answer is a RANGE and both ends are printed.
        # ⚠️ THE CEILING IS 1.5x THE REFERENCE, NOT "FASTER", AND THAT IS
        # THE FINDING. Measured this cycle with `cookCount` confirming every
        # pass: 0.85x on one 20 km curve of 20 001 vertices, 1.10x on 300
        # short streets. The native decompose is NOT yet a speedup, and
        # 13.2's 0.0037 s figure is not comparable - it timed a wrangle that
        # wrote ONE point attribute, where this stage also builds the
        # 20 000-element sampler table the frames read. Breaking the 20 km
        # cook down: the four segment arrays are 0.0171 s of 0.0428 s, the
        # per-point `setpointattrib` loop 0.0156 s, the P prefetch 0.0030 s.
        # R7 is confirmed rather than refuted, so this check exists to catch
        # a REGRESSION cliff and to keep the ratio printed on every run - not
        # to certify a win nobody has measured.
        # ⚠️ AND THE FIXTURE HAS TO BE BIG ENOUGH TO CARRY THE RATIO (D211).
        # This FAILS rather than skipping, for the reason `output_guard_cost`
        # gives: a fixture that shrinks below the floor turns a tight ceiling
        # into a coin toss SILENTLY, and a coin toss teaches a reader to stop
        # believing the suite.  The absolute time is in the value on every
        # run so the next reader can see the size the ratio rests on.
        floor = ref_best >= BENCH_FLOOR_S
        check("decompose_%s_wall_clock" % label,
              floor and best < ref_best * 1.5,
              "%.4f s (%.2f-%.2fx)" % (best, ref_best / best if best else 0.0,
                                       ref_full / best if best else 0.0),
              "%d curves / %d points through %d native nodes. The RANGE is "
              "the reference without its geometry read (%.4f s) and with it "
              "(%.4f s); the ceiling is 1.5x the lower bound, and no speedup "
              "is claimed on the lower bound.%s"
              % (len(out.prims()), len(out.points()), len(nodes),
                 ref_best, ref_full,
                 "" if floor else
                 " THE FIXTURE IS TOO SMALL: the reference side cooks in "
                 "%.4f s, under the %.0f ms floor - a 1.5x ceiling on it is "
                 "noise, not a measurement (D211)."
                 % (ref_best, BENCH_FLOOR_S * 1e3)))
        sub.destroy()

    # ⚠️ THE CHECK THIS REPLACED WAS THE FINDING. It read `sop_cooks_per_build`
    # and asserted that ZERO native nodes cook on the Output stage - which was
    # true, and the reason it was true is that `kernel` took IN_SPLINE and the
    # entire DECOMPOSE box sat BESIDE the tool. Measured on that build: all six
    # nodes at `cookCount == 0` after an Output cook, bypassing all six left
    # the output hash byte-identical, and DESTROYING all six left it identical
    # too. A green suite was certifying that the port had not happened.
    #
    # So the tripwire is inverted, and it is deliberately NOT "bypassing the
    # branch changes the output": D166's fallback means a curve with no native
    # tables is answered by the Python, so a bypass is byte-identical BY
    # DESIGN. The only honest proof that the VEX answer REACHES the artist is
    # to corrupt it and watch the geometry move.
    fresh = root.createNode("pf_polychain", "load_bearing")
    fresh.setInput(0, node.input(0))
    before = _fingerprint(fresh)
    # The DECOMPOSE box plus CONFIG - the nodes that are UPSTREAM of `kernel`
    # and therefore on every artist's cook. `pc_plan_bridge`, `pc_frames` and
    # `pc_frames_valid` sit behind the Stage switch on purpose and must stay
    # at zero, which is what the second half of this line asserts.
    ON_PATH = ("config", "pc_unshare", "pc_curveid", "pc_curve_index",
               "pc_arclength", "pc_corners", "pc_markers")
    OFF_PATH = ("pc_plan_bridge", "pc_frames", "pc_frames_valid")
    counts = dict((c.name(), c.cookCount()) for c in fresh.children())
    asleep = sorted(n for n in ON_PATH if not counts.get(n))
    asleep += sorted("%s(should be idle)" % n for n in OFF_PATH
                     if counts.get(n))
    check("native_branch_cooks_on_output", not asleep,
          "%d/%d" % (len(ON_PATH) - len(asleep), len(ON_PATH)),
          "native nodes that did NOT cook on the Output stage: %s (ceiling 0 "
          "- the DECOMPOSE box is upstream of `kernel`, so an artist who "
          "never opens the Stage menu is still running the VEX)"
          % (", ".join(asleep) or "none"))

    fresh.allowEditingOfContents()
    arclength = fresh.node("pc_arclength")
    sound = arclength.parm("snippet").eval()
    arclength.parm("snippet").set(
        sound.replace('setpointattrib(0, "pc_s",        pts[i], ccum);',
                      'setpointattrib(0, "pc_s",        pts[i], ccum + 0.25);'))
    moved = _fingerprint(fresh)
    arclength.parm("snippet").set(sound)
    check("native_branch_is_load_bearing", moved != before, before[0],
          "shifting `pc_arclength`'s metre by 0.25 m moves the SHIPPED output "
          "(%d prims -> %d); before the rewiring this mutation changed nothing "
          "at all" % (before[0], moved[0]))


# --- the 64-bit design rule -------------------------------------------------

def sixty_four_bit(root):
    """13.8's design rule, as an assertion rather than an intention.

    "No intermediate is allowed to round-trip through float32."  A 64-bit
    wrangle writes a FLOAT64 attribute (measured: 20000.0 + 4.883e-4 reads
    back with error 0.0), and a 32-bit one does not - so the rule is testable,
    and this is the test.  The reason it matters is R2: every new intermediate
    must stay 64-bit or the tool becomes WORSE at world scale than the Python
    it is replacing.
    """
    # ⚠️ THIS CANNOT BE TESTED THROUGH `P`, AND THAT IS THE FIRST THING TO
    # SAY ABOUT IT. `P` is float32 storage: a vertex authored at
    # 20000.0004883 comes back as 20000.0 before any wrangle has run, so a
    # curve cannot even CARRY the number the rule is about. That floor is R2,
    # it is unchanged from today, and it is where the REFERENCE already lives
    # too - `frames_position_parity` is what measures it. What this checks is
    # the thing that IS new: an intermediate the network computes must not be
    # rounded to float32 at every node boundary on its way to the next stage.
    sub = root.createNode("subnet", "prec")
    geo = hou.Geometry()
    cases.polyline(geo, [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0)], curve_id="P")
    src = native.feed(sub, geo, "IN")
    writer = sub.createNode("attribwrangle", "probe_write")
    writer.parm("class").set(1)
    writer.parm("vex_precision").set("64")
    writer.parm("snippet").set("f@pc_probe = 20000.0 + 4.883e-4;")
    writer.setInput(0, src)
    reader = sub.createNode("attribwrangle", "probe_read")
    reader.parm("class").set(1)
    reader.parm("vex_precision").set("64")
    reader.parm("snippet").set("f@pc_probe_err = f@pc_probe - 20000.0;")
    reader.setInput(0, writer)
    reader.cook(force=True)
    prim = reader.geometry().prims()[0]
    survived = abs(prim.attribValue("pc_probe") - 20000.0004883)
    # ⚠️ COMPARE AGAINST THE SAME SUBTRACTION, not against the decimal
    # literal: (20000.0 + 4.883e-4) - 20000.0 is 4.8830000001...e-04 in
    # float64, and measuring the wrangle against `4.883e-4` reports 1.4e-13 of
    # the comparand's OWN cancellation as if it were the node's error. That is
    # the same shape of mistake D115's headline had.
    crossed = abs(prim.attribValue("pc_probe_err")
                  - ((20000.0 + 4.883e-4) - 20000.0))

    cfg = native.config_stub(sub, DEFAULTS)
    _last, nodes = native.stage_decompose(sub, src, cfg)
    # `pc_unshare` is a native `splitpoints`, not a wrangle - it has no
    # precision to set and it carries no intermediate of its own.
    thirty_two = [n for n, node in nodes.items()
                  if node.parm("vex_precision") is not None
                  and node.parm("vex_precision").eval() != "64"]
    check("native_intermediates_are_64bit",
          survived == 0.0 and crossed == 0.0 and not thirty_two,
          "%.3e / %.3e" % (survived, crossed),
          "a 20 km value written by a 64-bit wrangle and READ BY THE NEXT "
          "NODE, error on both sides; 32-bit wrangles: %s"
          % (", ".join(thirty_two) or "none"))
    sub.destroy()


def worldscale_transport(root):
    """D170 - the SPAN, across the Python SOP -> wrangle boundary, at 20 km.

    ⚠️ THE CHECK ABOVE CANNOT SEE THIS, AND SAYING SO IS THE POINT.
    `frames_linear_parity` rounds the span on BOTH sides through the same
    transport, which isolates the arithmetic and is what it is for. The thing
    the network actually does differently from the reference is CARRY the
    span through a point attribute, and `hou.Geometry` has no 64-bit float
    storage - so before D170 a 20 km arclength arrived 9.765e-4 m out, ten
    times the suite's own 1e-4 m tolerance and a 1.95 mm quantum that two
    neighbouring pieces snapped to the same station inside.

    So this reads `pc_s0r`/`pc_s1r` BACK off the built asset's Plan stage on
    the 20 km fixture and diffs them against the reference's own float64
    numbers, with no rounding on either side.
    """
    from polyfactory.polychain import kit as K

    # ⚠️ `root` IS ALREADY A `geo`, so the fixture is built inside it and the
    # nodes are destroyed by name afterwards.
    geo_node = root
    spline = geo_node.createNode("python", "long_spline")
    spline.parm("python").set(
        "import sys\n"
        "sys.path.insert(0, %r)\n"
        "sys.path.insert(0, %r)\n"
        "import cases\n"
        "cases.polyline(hou.pwd().geometry(),\n"
        "               cases.arc_points(20000.0, 1.0, 20000.0),\n"
        "               curve_id='LONG')\n" % (HERE.replace(chr(92), "/"),
              os.path.dirname(HERE).replace(chr(92), "/")))
    node = geo_node.createNode("pf_polychain", "worldscale")
    node.setInput(0, spline)
    node.parm("stage").set("plan")
    plan = node.geometry()
    head0 = plan.pointFloatAttribValues("pc_s0r")
    lo0 = plan.pointFloatAttribValues("pc_s0r_lo")
    head1 = plan.pointFloatAttribValues("pc_s1r")
    lo1 = plan.pointFloatAttribValues("pc_s1r_lo")

    style = H.style_from_parms(node)
    _out, report = P.build(spline.geometry(), H.kit_geometry(node), style,
                           params=style.params, report_frames=True)
    rows = report["frames"]
    worst_head = worst_pair = 0.0
    at = -1
    for i, row in enumerate(rows):
        worst_head = max(worst_head, abs(head0[i] - row["s0r"]),
                         abs(head1[i] - row["s1r"]))
        err = max(abs(head0[i] + lo0[i] - row["s0r"]),
                  abs(head1[i] + lo1[i] - row["s1r"]))
        if err > worst_pair:
            worst_pair, at = err, i
    # 1e-4 m is `checks.TOL_M`, the tolerance the rest of the suite asserts
    # positions at. The pair measures ~6e-11 m; the head alone measures the
    # 9.765e-4 m this check exists to keep out.
    check("plan_span_transport_at_20km", worst_pair < 1.0e-4,
          "%.3e m" % worst_pair,
          "worst |transported s - reference s| over %d pieces on a 20 km "
          "spline, read back off Stage = plan (ceiling 1e-4 m = TOL_M). The "
          "float32 HEAD alone is %.3e m out at piece %d, which is what the "
          "residual half is for" % (len(rows), worst_head, at))
    node.parm("stage").set("output")
    node.destroy()
    spline.destroy()


def config_payload_parity(root):
    """D77 through the ASSET'S OWN `config` NODE, under a wired payload.

    ⚠️ THE RIG'S `config_stub` CANNOT SEE THIS. It synthesises `pc_cfg` from
    the `Params` object, so it agrees with the parameters by construction -
    and the shipped node was reading an UNWIRED input for its payload the
    whole time. Measured before the fix: a payload asking for
    corner_angle_deg = 77 / min_included_angle_deg = 3 produced pc_cfg 30 /
    15 and `from_payload = 0`, and the sections stage then broke the run at
    two corners where the payload asks for one.
    """
    geo_node = root
    spline = geo_node.createNode("python", "cfg_spline")
    spline.parm("python").set(
        "geo = hou.pwd().geometry()\n"
        "poly = geo.createPolygon(False)\n"
        "for p in ((0,0,0), (12,0,0), (12,0,8), (20,0,14)):\n"
        "    pt = geo.createPoint()\n"
        "    pt.setPosition(p)\n"
        "    poly.addVertex(pt)\n")
    payload = geo_node.createNode("python", "style_in")
    payload.parm("python").set(
        "from polyfactory.polychain import Params, Rule, Style\n"
        "from polyfactory.polychain import style as S\n"
        "st = Style('pipeline', 1, 11,\n"
        "           rules=[Rule('default', 'first', ['panel'])],\n"
        "           params=Params(corner_angle_deg=77.0,\n"
        "                         min_included_angle_deg=3.0))\n"
        "S.write(hou.pwd().geometry(), st)\n")
    node = geo_node.createNode("pf_polychain", "cfg")
    node.setInput(0, spline)
    node.setInput(2, payload)
    node.parm("stage").set("config")
    cfg = node.geometry().attribValue("pc_cfg")

    from polyfactory.polychain import style as S
    want = S.read(payload.geometry())[0]
    bad = [k for k in ("corner_angle_deg", "min_included_angle_deg")
           if cfg.get(k) != getattr(want.params, k)]
    if cfg.get("from_payload") != 1.0:
        bad.append("from_payload")
    if cfg.get("style_id") != want.style_id:
        bad.append("style_id")
    check("config_reads_the_payload", not bad,
          "%.1f deg / %.1f deg" % (cfg.get("corner_angle_deg", -1.0),
                                   cfg.get("min_included_angle_deg", -1.0)),
          "pc_cfg vs style.read(payload).params on the BUILT asset "
          "(payload asks 77.0 / 3.0); disagreeing keys: %s"
          % (", ".join(bad) or "none"))

    # ...and the sections the payload's own thresholds produce, which is what
    # the disagreement actually cost.
    node.parm("stage").set("sections")
    corners = sum(node.geometry().pointIntAttribValues("pc_iscorner"))
    check("payload_thresholds_reach_the_corners", corners == 1, corners,
          "corner breaks at corner_angle_deg = 77 (the 90 deg elbow, not the "
          "53 deg bend); the parm page's 30 deg would give 2")
    node.parm("stage").set("output")
    node.destroy()
    spline.destroy()
    payload.destroy()


# --- R1: 3.3's seeding chain, in VEX ---------------------------------------

SEED_TEXTS = None


def _seed_texts():
    """The strings the seeding chain is asked about, ~360 of them.

    Four families on purpose: RANDOM ASCII (which is what caught the
    `split(s, "")` defect - it agreed with zlib on every 1-character string
    and on nothing else), the exact `seed_for` shape for all four 3.3 scopes,
    40 real `elem_id`s, because `pc_elem_key` and `pc_seed_for` are two
    different callers of the same crc - and NON-ASCII text.

    ⚠️ THE NON-ASCII FAMILY IS NOT DECORATION.  `pc_crc32` used to fold the
    CODE POINT masked to 8 bits where `zlib.crc32` folds UTF-8 BYTES, and this
    corpus could not see it because every one of its 358 strings was ASCII.
    Measured before the fix: a German `style_id` moved 28 of 40 `random`
    picks, because `pc_seed_for` runs through the same crc.  Two- three- and
    four-byte code points are all here, and so is a string that is nothing but
    continuation-byte territory.
    """
    global SEED_TEXTS
    if SEED_TEXTS is not None:
        return SEED_TEXTS
    import random as _r
    from polyfactory.polychain import elem_id as _eid
    rnd = _r.Random(11)
    alpha = "abcdefghijklmnopqrstuvwxyzABCZ0123456789|_:. -"
    out = ["".join(rnd.choice(alpha) for _ in range(rnd.randint(0, 24)))
           for _ in range(300)]
    for scope in ("generator", "spline", "section", "segment"):
        for key in ("A", "curve_7", "", "A|0|default|3"):
            out.append("%d\x1f%s\x1f%s\x1f%s" % (4, "fence", scope, key))
    out.append("%d\x1f%s\x1f%s\x1f%s" % (0, "", "segment", "A|0|default|3"))
    out.append("%d\x1f%s\x1f%s\x1f%s" % (2 ** 31 - 1, "sty", "spline", "X"))
    out.extend(_eid("curve%d" % i, i, "default", i * 7, "sty")
               for i in range(40))
    # non-ASCII: 2-byte (Latin-1 supplement), 3-byte (CJK, euro sign) and
    # 4-byte (astral) code points, alone and mixed with ASCII, plus the two
    # shapes that actually reach the crc - a `style_id` and a `curve_id` -
    # in `seed_for`'s own assembled text.
    nonascii = ["\u00e9", "\u00e9x", "stra\u00dfe", "Stra\u00dfe",
                "rue\u00e9", "\u00e9tage", "\u20ac", "\u4e2d\u6587",
                "\U0001F600", "a\U0001F600b", "\u00c5ngstr\u00f6m",
                "\u00e9\u20ac\U0001F600"]
    out.extend(nonascii)
    for scope in ("generator", "spline", "section", "segment"):
        out.append("%d\x1f%s\x1f%s\x1f%s"
                   % (5, "stra\u00dfe", scope, "rue\u00e91"))
    out.extend(_eid("Stra\u00dfe%d" % i, i, "default", i, "\u00e9tage")
               for i in range(6))
    SEED_TEXTS = out
    return out


def vex_string_literal(text):
    """`text` as a VEX string literal.  ONE site - the plan solve needs it too."""
    out = text.replace("\\", "\\\\").replace('"', '\\"')
    return '"' + out.replace("\x1f", "\\x1f") + '"'


def seeding_vex(root, header_src=None):
    """Cook `pc_rand.h` over `_seed_texts()`; -> {name: [values]}."""
    from polyfactory.polychain import vexsrc
    add = root.createNode("add")
    add.parm("points").set(1)
    node = native.wrangle(root, "pc_seed_probe", "detail", "pc_rand.h")
    node.setInput(0, add)
    body = vexsrc.source("pc_rand.h") if header_src is None else header_src
    node.parm("snippet").set(body + """
string PC_TXT[] = array(%s);
int crcs[], seeds[], keys[];
float rs[];
foreach (string t; PC_TXT) {
    push(crcs, pc_crc32(t));
    int sd = pc_seed_for(t);
    push(seeds, sd);
    push(keys, pc_elem_key(t));
    push(rs, pc_random01(sd));
}
i[]@crc = crcs; i[]@seed = seeds; i[]@key = keys;
f[]@r = rs;
""" % ", ".join(vex_string_literal(t) for t in _seed_texts()))
    geo = node.geometry()
    out = dict((name, list(geo.intListAttribValue(name)))
               for name in ("crc", "seed", "key"))
    out["r"] = list(geo.floatListAttribValue("r"))
    node.destroy()
    add.destroy()
    return out


def s64(value):
    """A Python uint64 as the signed int VEX stores and hou reads back."""
    return value - (1 << 64) if value >= (1 << 63) else value


def seeding_parity(root):
    """13.9 R1, CLOSED: crc32, splitmix64, elem_key and `random()` in VEX.

    R1 said `_splitmix` had no VEX expression because 13.2 probed `long` (an
    invalid type name) and `>>>` (a parse error).  Both probes were right and
    the conclusion was wrong: VEX has no shift OPERATORS at all - `1 << 4` is
    a syntax error - it has `shl` / `shr` / `shrz`, and under
    `vex_precision = 64` its `int` IS int64.  `shrz` is the unsigned shift.
    So splitmix64 is six lines and the Python fallback 13.3.2 reserved for it
    is not needed.
    """
    import random as _rand
    import zlib as _zlib
    from polyfactory.polychain import _splitmix

    texts = _seed_texts()
    got = seeding_vex(root)
    bad = dict(crc=0, elem_key=0, splitmix=0, random=0)
    for i, text in enumerate(texts):
        pcrc = _zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF
        if got["crc"][i] != pcrc:
            bad["crc"] += 1
        if got["key"][i] != (pcrc & 0x7FFFFFFF):
            bad["elem_key"] += 1
        mixed = _splitmix(pcrc)
        if got["seed"][i] != s64(mixed):
            bad["splitmix"] += 1
        if got["r"][i] != _rand.Random(mixed).random():
            bad["random"] += 1
    n = len(texts)
    check("seed_crc32_parity", bad["crc"] == 0, "%d texts" % n,
          "zlib.crc32 vs pc_crc32, bit for bit; mismatches: %d" % bad["crc"])
    check("seed_elem_key_parity", bad["elem_key"] == 0, "%d texts" % n,
          "3.4's pc_elem_key (crc32 & 0x7FFFFFFF); mismatches: %d"
          % bad["elem_key"])
    check("seed_splitmix64_parity", bad["splitmix"] == 0, "%d texts" % n,
          "R1 CLOSED - _splitmix is 6 lines of VEX, no limbs; mismatches: %d"
          % bad["splitmix"])
    check("seed_random01_parity", bad["random"] == 0, "%d texts" % n,
          "random.Random(seed).random() - MT19937 init_by_array plus "
          "genrand_res53, in VEX; mismatches: %d" % bad["random"])
    # ⚠️ THE CORPUS'S OWN NON-VACUITY, asserted rather than assumed.  The
    # four checks above were green for a whole cycle on a crc that hashed
    # CODE POINTS instead of UTF-8 BYTES, because every text was ASCII.
    multibyte = sum(1 for t in texts if len(t.encode("utf-8")) != len(t))
    check("seed_corpus_has_multibyte", multibyte >= 20,
          "%d of %d texts" % (multibyte, n),
          "texts whose UTF-8 encoding is LONGER than their code-point count. "
          "`pc_is_ascii` used to stand here and only said the crc might be "
          "wrong; these say it is right. Reverting pc_crc32's UTF-8 encode "
          "reddens seed_crc32_parity on %d texts" % multibyte)


def seeding_mutation(root):
    """Swap the LOGICAL shift for the ARITHMETIC one and confirm it reddens.

    `shr` compiles, and it is the shift 13.2 assumed was the only one there
    is.  If this mutation left the parity green, the parity would not be
    testing the shift at all.
    """
    import zlib as _zlib
    from polyfactory.polychain import _splitmix, vexsrc

    body = vexsrc.source("pc_rand.h")
    target = "z ^ shrz(z, 30)"
    check("seed_mutation_target_exists", target in body, target,
          "the logical shift the parity rests on is still in pc_rand.h, so "
          "the mutation below cannot silently become a no-op")
    texts = _seed_texts()
    got = seeding_vex(root, header_src=body.replace(target, "z ^ shr(z, 30)"))
    moved = sum(1 for i, t in enumerate(texts)
                if got["seed"][i] != s64(_splitmix(
                    _zlib.crc32(t.encode("utf-8")) & 0xFFFFFFFF)))
    check("mutation_pc_splitmix_shift", moved > len(texts) // 2,
          "%d / %d wrong" % (moved, len(texts)),
          "shrz -> shr in splitmix breaks it on most inputs")


# --- 13.9 N2: 4.2's fitting solve, in VEX -----------------------------------


def plan_chain(parent, case, params, style, kit, tag):
    """The whole native plan, cooked on ONE case.  -> (read node, config)."""
    cfg = native.config_full(parent, params, style, kit, "config_%s" % tag)
    src = native.feed(parent, case["curve"], "IN_%s" % tag)
    last, _dec = native.stage_decompose(parent, src, cfg)
    read, nodes = native.stage_plan(parent, last, cfg, "_%s" % tag)
    return (read, cfg, nodes)


def plan_rows(geo):
    """The native plan as plain dicts, in point order."""
    out = []
    for pt in geo.points():
        out.append({
            "curve_id": str(pt.attribValue("pc_curve_id")),
            "section": pt.attribValue("pc_sec_index"),
            "slot": pt.attribValue("pc_slot"),
            "index": pt.attribValue("pc_index"),
            "module": pt.attribValue("pc_module"),
            "variant": pt.attribValue("pc_variant"),
            "zmode": pt.attribValue("pc_zmode"),
            "deform": pt.attribValue("pc_deform"),
            "warns": pt.attribValue("pc_warns"),
            "elem_id": pt.attribValue("pc_elem_id"),
            "elem_key": pt.attribValue("pc_elem_key"),
            "s0": pt.attribValue("pc_s0"), "s1": pt.attribValue("pc_s1"),
            "u": pt.attribValue("pc_u"), "scale": pt.attribValue("pc_scale"),
            "slice": pt.attribValue("pc_slice_t")})
    return out


def plan_diff(got, ref):
    """[(row, what)] - the first disagreement per row, or []."""
    if len(got) != len(ref):
        return [(-1, "count %d != %d" % (len(got), len(ref)))]
    from polyfactory.polychain import elem_key as _ekey
    bad = []
    for i, (g, r) in enumerate(zip(got, ref)):
        if (g["curve_id"] != str(r.curve_id) or g["section"] != r.section_index
                or g["slot"] != r.slot or g["index"] != r.index):
            bad.append((i, "address %s|%d|%s|%d != %s|%d|%s|%d"
                        % (g["curve_id"], g["section"], g["slot"], g["index"],
                           r.curve_id, r.section_index, r.slot, r.index)))
            continue
        for key, rv in (("module", r.module), ("variant", r.variant),
                        ("zmode", r.zmode), ("elem_id", r.elem_id)):
            if g[key] != rv:
                bad.append((i, "%s %r != %r" % (key, g[key], rv)))
        if int(g["deform"]) != int(r.deform):
            bad.append((i, "deform %s != %s" % (g["deform"], r.deform)))
        if int(g["elem_key"]) != _ekey(r.elem_id):
            bad.append((i, "elem_key %s != %s"
                        % (g["elem_key"], _ekey(r.elem_id))))
        if sorted(g["warns"].split()) != sorted(r.warns):
            bad.append((i, "warns %r != %r" % (g["warns"], list(r.warns))))
        rslice = -1.0 if r.slice_t is None else r.slice_t
        for key, rv in (("s0", r.s0), ("s1", r.s1), ("u", r.u),
                        ("scale", r.scale), ("slice", rslice)):
            # EXACT, relative. 13.8: "the fitting solve must not need a
            # tolerance; if it does, the accumulation order differs and that
            # is a defect, not float noise."
            if abs(g[key] - rv) / max(abs(rv), 1.0) > 1e-12:
                bad.append((i, "%s %.17g != %.17g" % (key, g[key], rv)))
    return bad


def plan_reference(case, params, style, kit):
    from polyfactory.polychain import decompose as D
    from polyfactory.polychain import plan as PLAN
    curves, markers = P.read_curves(case["curve"])
    return PLAN.plan_sections(D.decompose_all(curves, markers, params),
                              kit, style, params)


def plan_parity(root, built):
    """4.2 in VEX against `plan.plan_sections`, every case, EXACT.

    ⚠️ WHAT THIS DOES AND DOES NOT COVER.  It is the whole fitting solve -
    the four fill modes with padding packing, evenly anchors with justify and
    adjust-to-end, markers, start/end reservation with D13's overflow policy,
    the compose rules and all four selectors - measured against the reference
    on the SAME decomposed spline, in one process (13.8 rule 1).  It is NOT
    4.3's corner reserve: `pc_trim_a`/`pc_trim_b` are 0 until 13.9 N8, and 0
    is exactly `plan_sections`' own `trim=(0, 0)`, which is the call this
    compares against.
    """
    from polyfactory.polychain import kit as KIT
    worst = 0.0
    bad = []
    ncase = npiece = nsec = 0
    for name in sorted(built):
        case = built[name]
        style = case["style"]
        params = style.params if style is not None else DEFAULTS
        kit = KIT.read(case["kit"])[0]
        ref = plan_reference(case, params, style, kit)
        sub = root.createNode("subnet", "plan_%s" % name)
        read, _cfg, nodes = plan_chain(sub, case, params, style, kit, name)
        try:
            read.cook(force=True)
        except Exception:
            pass
        errs = [(n.name(), n.errors()[0].replace("\n", " ")[:160])
                for n in nodes.values() if n.errors()]
        if errs:
            bad.append((name, "%s: %s" % errs[0]))
            sub.destroy()
            continue
        nsec += len(nodes["pc_plan_solve"].geometry().points())
        got = plan_rows(read.geometry())
        rows = plan_diff(got, ref)
        ncase += 1
        npiece += len(ref)
        if rows:
            bad.append((name, "row %d %s" % rows[0]))
        sub.destroy()
    check("plan_solve_parity", not bad, "%d cases / %d pieces" % (ncase, npiece),
          "4.2 in VEX vs plan.plan_sections - address, module, variant, "
          "zmode, deform, warnings, elem_id, elem_key, s0, s1, u, scale and "
          "slice_t, at 1e-12 RELATIVE and no absolute slack (13.8). "
          "Mismatches: %s" % ("; ".join("%s %s" % b for b in bad[:3]) or "none"))
    check("plan_sections_emitted", nsec > 0, nsec,
          "section points the solve actually ran over - a chain that emitted "
          "none would make the check above vacuously green")
    return worst


def stress_cases():
    """The branches the 89 scene cases do not reach.

    ⚠️ THIS EXISTS BECAUSE OF DEV-LOOP RULE 0's SECOND CHECK - "exercise every
    branch you add".  Measured on the shipped suite: exactly ONE of the 89
    cases carries a `random` rule, and it names a single module, so the
    weighted pick returns `pool[0]` whatever the RNG says and the whole
    MT19937 chain could have been wrong with every case green.  `sequence`
    over a mixed unit, all four correlation scopes, every conditional
    operator, `evenly` under all three justifications and `adjust_to_end`,
    negative and unit-cancelling padding, and `tile`'s rigid-piece fallback
    are all in the same position.  Each row here is (name, kit, style).
    """
    from polyfactory.polychain import Module, Params, Rule, Style
    kit = [Module("post", (0.12, 1.0, 0.12), pad=(0.0, 0.0), deform=0,
                  roles="default start end"),
           Module("panel", (2.0, 0.9, 0.05), pad=(0.0, 0.0), deform=1,
                  roles="default"),
           Module("gate", (1.6, 1.2, 0.06), pad=(0.1, 0.1), deform=2,
                  roles="default evenly", variant="wide", weight=3.0),
           Module("brick", (0.35, 0.2, 0.1), pad=(-0.02, -0.02), deform=2,
                  roles="default", variant="a", weight=0.5)]
    out = []
    for scope in ("generator", "spline", "section", "segment"):
        out.append(("random_%s" % scope, kit, Style(
            "st_%s" % scope, 1, 7,
            rules=[Rule("default", "random", ["post", "panel", "gate", "brick"],
                        scope=scope)],
            params=Params(fill="adaptive"))))
    out.append(("random_weighted", kit, Style(
        "wt", 1, 3, rules=[Rule("default", "random", ["post", "panel", "gate"],
                                weights={"panel": 9.0, "post": 0.0})],
        params=Params(fill="adaptive"))))
    out.append(("random_zero_total", kit, Style(
        "wz", 1, 3, rules=[Rule("default", "random", ["post", "panel"],
                                weights={"panel": 0.0, "post": 0.0})],
        params=Params(fill="adaptive"))))
    out.append(("sequence_mixed", kit, Style(
        "sq", 1, 1, rules=[Rule("default", "sequence", ["post", "panel", "post"])],
        params=Params(fill="adaptive"))))
    out.append(("sequence_by_role", kit, Style(
        "sqr", 1, 1, rules=[Rule("default", "sequence", [])],
        params=Params(fill="adaptive"))))
    for op, value in (("lt", 12.0), ("le", 12.0), ("gt", 12.0), ("ge", 12.0),
                      ("eq", 20.0), ("ne", 20.0), ("in", [1.0, 20.0]),
                      ("eq", "twenty"), ("nonsense", 1.0)):
        out.append(("cond_%s_%s" % (op, value), kit, Style(
            "c", 1, 2,
            rules=[Rule("default", "conditional", ["gate", "panel"],
                        cond={"subject": "sectionLength", "op": op,
                              "value": value}),
                   Rule("default", "first", ["post"])],
            params=Params(fill="adaptive"))))
    out.append(("cond_unknown_subject", kit, Style(
        "cu", 1, 2, rules=[Rule("default", "conditional", ["gate"],
                                cond={"subject": "weather", "op": "eq",
                                      "value": 1})],
        params=Params(fill="adaptive"))))
    out.append(("cond_u_declines_alone", kit, Style(
        "cd", 1, 2, rules=[Rule("default", "conditional", ["gate"],
                                cond={"subject": "u", "op": "gt",
                                      "value": 0.5})],
        params=Params(fill="adaptive"))))
    for justify in ("start", "center", "end"):
        out.append(("evenly_%s" % justify, kit, Style(
            "e", 1, 1, rules=[Rule("default", "first", ["panel"]),
                              Rule("evenly", "first", ["post"]),
                              Rule("start", "first", ["post"]),
                              Rule("end", "first", ["post"])],
            params=Params(fill="adaptive", evenly_spacing=3.7,
                          justify=justify))))
    out.append(("evenly_adjust", kit, Style(
        "ea", 1, 1, rules=[Rule("default", "first", ["panel"]),
                           Rule("evenly", "first", ["post"])],
        params=Params(fill="adaptive", evenly_spacing=3.7,
                      adjust_to_end=1.0))))
    out.append(("evenly_count", kit, Style(
        "ec", 1, 1, rules=[Rule("default", "first", ["panel"]),
                           Rule("evenly", "sequence", ["post", "gate"])],
        params=Params(fill="adaptive", evenly_count=4))))
    for mode in ("adaptive", "scale", "tile", "count"):
        out.append(("fill_%s" % mode, kit, Style(
            "f", 1, 1, rules=[Rule("default", "first", ["gate"])],
            params=Params(fill=mode, count=7, adaptive_pct=35.0))))
    out.append(("tile_rigid_fallback", kit, Style(
        "tf", 1, 1, rules=[Rule("default", "sequence", ["gate", "panel"])],
        params=Params(fill="tile"))))
    out.append(("pad_negative", kit, Style(
        "pn", 1, 1, rules=[Rule("default", "sequence", ["brick", "brick"])],
        params=Params(fill="adaptive"))))
    out.append(("pad_cancels_unit", [Module("thin", (0.2, 1.0, 0.1),
                                            pad=(-0.1, -0.1), deform=0,
                                            roles="default")], Style(
        "pc", 1, 1, rules=[Rule("default", "first", ["thin"])],
        params=Params(fill="adaptive"))))
    out.append(("kit_gap_standin", kit, Style(
        "kg", 1, 1, rules=[Rule("default", "first", ["nothing_named_this"])],
        params=Params(fill="adaptive"))))
    out.append(("vexpr_warns", kit, Style(
        "vx", 1, 1, rules=[Rule("default", "first", ["panel"],
                                vexpr="@u > 0.5")],
        params=Params(fill="adaptive"))))
    out.append(("overflow_both_caps", kit, Style(
        "of", 1, 1, rules=[Rule("start", "first", ["panel"]),
                           Rule("end", "first", ["panel"]),
                           Rule("default", "first", ["post"])],
        params=Params(fill="adaptive"))))

    # ⚠️ THE SUBJECT BAG, SUBJECT BY SUBJECT.  `plan.cond_subject` ends in
    # `ctx.get(subject)`, so every key of `plan_section`'s `ctx_base` is a
    # readable subject - not only the five `COND_SUBJECTS` documents - and the
    # two bags were simply not the same set.  `segIndex` existed on the VEX
    # side at every pick OUTSIDE the fill loop and on the reference side only
    # INSIDE it; `curve_id`, `section_index`, `slot` and `yclass` existed on
    # the reference side and nowhere in the VEX.  Each of the five below was a
    # measured divergence (0 vs 10 pieces on `segIndex`, 10 vs 11 on the rest)
    # and none of the 34 rows above nor the 89 scene cases contained one.
    #
    # Each subject is asked on the DEFAULT slot (which runs inside `_fill`,
    # where `segIndex` is defined) and on an ANCHORED slot (`start`, which
    # does not) - because that difference IS the defect.
    for subj, op, value in (("segIndex", "lt", 1),
                            ("curve_id", "eq", "S"),
                            ("section_index", "eq", 0),
                            ("slot", "eq", "default"),
                            ("yclass", "eq", ""),
                            ("attr:pc_total", "gt", 5.0),
                            ("attr:pc_closed", "eq", 0),
                            ("attr:pc_curve_id_r", "eq", "S")):
        tag = subj.replace(":", "_")
        out.append(("subject_%s_default" % tag, kit, Style(
            "sub", 1, 2,
            rules=[Rule("default", "conditional", ["gate", "panel"],
                        cond={"subject": subj, "op": op, "value": value})],
            params=Params(fill="adaptive"))))
        out.append(("subject_%s_start" % tag, kit, Style(
            "sub", 1, 2,
            rules=[Rule("start", "conditional", ["gate", "panel"],
                        cond={"subject": subj, "op": op, "value": value}),
                   Rule("evenly", "conditional", ["post", "gate"],
                        cond={"subject": subj, "op": op, "value": value}),
                   Rule("default", "first", ["post"])],
            params=Params(fill="adaptive", evenly_spacing=4.0))))
    return out


def stress_geometry(closed=False, length=20.0):
    """One straight open span, or - with `closed` - a square ring of it.

    ⚠️ `closed` USED TO BE IGNORED, which is worse than not having it: the
    signature advertised coverage that no caller could obtain, because the
    body built `cases.polyline(..., curve_id="S")` with polyline's OWN
    `closed=False` whatever it was asked for.  D19's cyclic run - a closed
    section with no anchors and no caps, which folds the wrap gap in and
    starts half a gap along - was therefore reached by the scene cases'
    default style and by nothing in the matrix that sweeps all four
    selectors, all four scopes and the padding modes.
    """
    geo = hou.Geometry()
    if closed:
        h = length * 0.25
        cases.polyline(geo, [(0.0, 0.0, 0.0), (h, 0.0, 0.0),
                             (h, 0.0, h), (0.0, 0.0, h)],
                       closed=True, curve_id="S")
    else:
        cases.polyline(geo, [(0.0, 0.0, 0.0), (length, 0.0, 0.0)],
                       curve_id="S")
    return geo


def plan_stress_parity(root):
    """The stress matrix, and the D113 trials, against the reference."""
    from polyfactory.polychain import Kit
    rows = stress_cases()
    shapes = [("plain", stress_geometry()),
              ("short", stress_geometry(length=0.9)),
              # D113's three trials: an IRRATIONAL slope, 20 km, and an
              # ASYMMETRIC shape. A parity check green at 0.0 on symmetric
              # fixtures is a claim about the fixtures.
              ("irrational", None), ("far", None), ("asymmetric", None)]
    import math
    g = hou.Geometry()
    cases.polyline(g, [(0.0, 0.0, 0.0), (10.0, 10.0 * math.sqrt(2.0), 0.0)],
                   curve_id="S")
    shapes[2] = ("irrational", g)
    g = hou.Geometry()
    cases.polyline(g, [(20000.0, 0.0, 0.0), (20017.0, 0.0, 0.0)], curve_id="S")
    shapes[3] = ("far", g)
    g = hou.Geometry()
    cases.polyline(g, [(0.0, 0.0, 0.0), (7.3, 0.0, 0.0), (7.3, 0.0, 19.1),
                       (1.05, 0.0, 19.1)], curve_id="S")
    shapes[4] = ("asymmetric", g)
    # D19's cyclic run, which the matrix advertised and did not have:
    # `stress_geometry`'s `closed` argument was ignored and no caller passed
    # it, so every one of the five shapes above is an OPEN polyline. A closed
    # ring is the branch that folds the wrap gap in and starts half a gap
    # along - reached by the scene cases' default style and by nothing that
    # sweeps all four selectors, all four scopes and the padding modes.
    # ⚠️ APPENDED, NOT INSERTED: the three trials above are assigned BY INDEX.
    shapes.append(("closed", stress_geometry(closed=True)))

    bad = []
    nrun = npiece = 0
    for shape_name, geo in shapes:
        for name, mods, style in rows:
            case = {"curve": geo, "kit": None}
            kit = Kit("stress", 1, mods)
            params = style.params
            ref = plan_reference(case, params, style, kit)
            tag = "%s_%s" % (shape_name, name.replace(".", "_")
                             .replace("[", "").replace("]", "")
                             .replace(",", "").replace(" ", "").replace("-", "_"))
            sub = root.createNode("subnet", "stress_%s" % tag)
            read, _cfg, nodes = plan_chain(sub, case, params, style, kit, tag)
            try:
                read.cook(force=True)
            except Exception:
                pass
            errs = [(n.name(), n.errors()[0].replace("\n", " ")[:200])
                    for n in nodes.values() if n.errors()]
            if errs:
                bad.append((tag, "%s: %s" % errs[0]))
                sub.destroy()
                continue
            diff = plan_diff(plan_rows(read.geometry()), ref)
            nrun += 1
            npiece += len(ref)
            if diff:
                bad.append((tag, "row %d %s" % diff[0]))
            sub.destroy()
    check("plan_stress_parity", not bad, "%d builds / %d pieces" % (nrun, npiece),
          "every branch of 4.2 the 89 scene cases do not reach - all four "
          "selectors, all four correlation SCOPES, every conditional "
          "operator, the three justifications, adjust-to-end, negative and "
          "unit-cancelling padding, the tile fallback and D13's overflow - "
          "on five shapes including D113's three trials. Mismatches: %s"
          % ("; ".join("%s %s" % b for b in bad[:3]) or "none"))


# --- the SHAPE-shaped fixtures the stress matrix cannot express -------------
#
# `stress_cases` varies the STYLE over six fixed shapes.  Five defects found
# by review live in the shape instead - a marker's DATA, a per-point section
# key's TYPE, two prims sharing an id, a non-ASCII id - so they need their own
# table.  Every row is (name, geometry, kit modules, style).


def fixture_cases():
    from polyfactory.polychain import Module, Params, Rule, Style
    kit = [Module("post", (0.12, 1.0, 0.12), pad=(0.0, 0.0), deform=0,
                  roles="default start end"),
           Module("panel", (2.0, 0.9, 0.05), pad=(0.0, 0.0), deform=1,
                  roles="default"),
           Module("gate", (1.6, 1.2, 0.06), pad=(0.0, 0.0), deform=2,
                  roles="default evenly", variant="wide", weight=3.0)]
    out = []

    # --- 3.3's `markerData:<key>`, by VALUE TYPE ---------------------------
    # ⚠️ THE EMPTY STRING IS THE WHOLE POINT.  VEX has no `dicttype`, so the
    # solve used to infer a dict slot's type by READING it, and a value that
    # is "" reads as "" through the string port AND as 0.0 through the numeric
    # one.  It was taken as numeric, so `markerData:tag eq ""` could never
    # match: measured, a 0.12 m post where the reference puts a 1.6 m gate,
    # and every downstream piece 0.21 m out.  `json_dumps(dict, 0)` names the
    # type and is what the solve reads now; the other four rows are the
    # controls that say the naming did not break the easy cases.
    for tag, data, value in (("empty", {"tag": ""}, ""),
                             ("str", {"tag": "x"}, "x"),
                             ("num", {"tag": 3.0}, 3.0),
                             ("int", {"tag": 4}, 4),
                             ("zero", {"tag": 0.0}, 0.0)):
        geo = hou.Geometry()
        cases.polyline(geo, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)], curve_id="S")
        cases.marker(geo, (8.0, 0.0, 0.0), "S", 7, dist=8.0, data=data)
        out.append(("marker_data_%s" % tag, geo, kit, Style(
            "md", 1, 3,
            rules=[Rule("marker:7", "conditional", ["gate", "post"],
                        cond={"subject": "markerData:tag", "op": "eq",
                              "value": value}),
                   Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive"))))

    # --- D7's per-POINT `pc_section`, by TYPE ------------------------------
    # A STRING per-point key was read as a float (always 0.0), so the
    # mid-curve break vanished: 1 section and 12 pieces natively against the
    # reference's 2 sections and 14, with both interior caps gone.
    # `read_curves` reads whatever type the artist authored, so both rows are
    # inside the contract.
    for tag, keys in (("string", ("a", "a", "b", "b")),
                      ("int", (0, 0, 1, 1))):
        geo = hou.Geometry()
        poly = cases.polyline(geo, [(0.0, 0.0, 0.0), (5.0, 0.0, 0.0),
                                    (12.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
                              curve_id="S")
        geo.addAttrib(hou.attribType.Point, "pc_section", keys[0])
        for pt, key in zip(poly.points(), keys):
            pt.setAttribValue("pc_section", key)
        out.append(("pt_section_%s" % tag, geo, kit, Style(
            "ps", 1, 3,
            rules=[Rule("start", "first", ["post"]),
                   Rule("end", "first", ["post"]),
                   Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive"))))

    # --- two primitives, ONE curve id --------------------------------------
    # The only topology where primitive order genuinely decides the answer:
    # `decompose_all` sorts by `(str(curve_id), index)` and Python's sort is
    # STABLE, so the two curves' sections INTERLEAVE (A0, B0, A1, B1) in prim
    # order.  `plan_is_input_order_free` builds its two orders out of three
    # DISTINCT ids, so it cannot reach this; the merge sort in `pc_sections`
    # breaks the tie on the prim number, and this row is what says the two
    # agree.
    geo = hou.Geometry()
    cases.polyline(geo, [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                         (10.0, 0.0, 8.0)], curve_id="A")
    cases.polyline(geo, [(0.0, 0.0, 20.0), (7.0, 0.0, 20.0),
                         (7.0, 0.0, 26.0)], curve_id="A")
    out.append(("shared_curve_id", geo, kit, Style(
        "sh", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive"))))

    # --- non-ASCII ids, through the RANDOM selector ------------------------
    # `pc_crc32` folded CODE POINTS where `zlib.crc32` folds UTF-8 BYTES, so a
    # German styleId or curve id moved the pick on roughly half the curves -
    # a 47-piece picket run where the reference builds a 5-piece panel run.
    # The `random` selector is what makes this visible: `pc_seed_for` runs
    # through the same crc as `pc_elem_key`.
    geo = hou.Geometry()
    for i in range(8):
        cases.polyline(geo, [(0.0, 0.0, 3.0 * i), (11.0, 0.0, 3.0 * i)],
                       curve_id=u"rue\u00e9%d" % i)
    out.append(("nonascii_ids_random", geo, kit, Style(
        u"stra\u00dfe", 1, 5,
        rules=[Rule("default", "random", ["post", "panel"], scope="spline")],
        params=Params(fill="adaptive"))))
    geo = hou.Geometry()
    for i in range(8):
        cases.polyline(geo, [(0.0, 0.0, 3.0 * i), (11.0, 0.0, 3.0 * i)],
                       curve_id=u"\u00e9tage%d" % i)
    # --- a kit in the HUNDREDS, resolved by ROLE ---------------------------
    # 7.2's 25 cell roles imply a facade kit of this size, and every other
    # fixture in the suite uses five modules - which is why nothing saw
    # `pc_choose` rebuilding and re-sorting the whole pool on every piece.
    # This row is the PARITY half (the pool's sort order and its weights have
    # to be the reference's at scale, on 220 modules);
    # `plan_cost_is_flat_in_kit_size` is the cost half, at 151.
    big = [Module("m%03d" % i, (0.5 + 0.01 * i, 1.0, 0.1), pad=(0.0, 0.0),
                  deform=1, roles="default", variant="v%d" % (i % 7),
                  weight=1.0 + (i % 5))
           for i in range(220)]
    geo = hou.Geometry()
    cases.polyline(geo, [(0.0, 0.0, 0.0), (60.0, 0.0, 0.0)], curve_id="S")
    out.append(("big_kit_random_by_role", geo, big, Style(
        "bk", 1, 9,
        rules=[Rule("default", "random", [], scope="segment")],
        params=Params(fill="adaptive"))))
    out.append(("big_kit_sequence_by_role", geo, big, Style(
        "bq", 1, 9, rules=[Rule("default", "sequence", [])],
        params=Params(fill="adaptive"))))

    out.append(("nonascii_ids_segment", geo, kit, Style(
        u"\u00c5ngstr\u00f6m", 1, 5,
        rules=[Rule("default", "random", ["post", "panel", "gate"],
                    scope="segment")],
        params=Params(fill="adaptive"))))

    # --- D202: an `attr:` SUBJECT THAT IS NOT A SCALAR ---------------------
    # `prim(0, name, pr)` READS COMPONENT 0.  `place._prim_attrs` hands the
    # reference `prim.attribValue(name)` - the WHOLE tuple - and
    # `evaluate_cond`'s TypeError guard makes every ordered comparison on it
    # False, so the two sides were answering different questions on a build
    # the guard ADMITS.  Measured on the shipped asset before the fix, a 20 m
    # line with `vecattr = (7.5, 1.0, 2.0)`: `gt 5.0` built 12 `gate` prims at
    # `Stage = output` against the reference's 10 `panel` prims, and
    # `lt 100.0` diverged the other way.  `eq`/`ne` agreed by luck (a tuple is
    # never equal to a float on either side), and they are the controls here.
    # Every operator is present because WHICH ones agreed was an accident of
    # the value, not a property of the code.
    for tag, value in (("vec3", (7.5, 1.0, 2.0)), ("vec2", (7.5, 1.0)),
                       ("ivec3", (8, 1, 2)), ("iarray", [8, 1, 2]),
                       ("sarray", ["a", "b"])):
        for op, want in (("gt", 5.0), ("ge", 5.0), ("lt", 100.0),
                         ("eq", 5.0), ("ne", 5.0), ("in", [7.5, 1.0])):
            geo = hou.Geometry()
            poly = cases.polyline(geo, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
                                  curve_id="S")
            geo.addAttrib(hou.attribType.Prim, "vecattr", value)
            poly.setAttribValue("vecattr", value)
            out.append(("attr_%s_%s" % (tag, op), geo, kit, Style(
                "av", 1, 3,
                rules=[Rule("default", "conditional", ["gate", "post"],
                            cond={"subject": "attr:vecattr", "op": op,
                                  "value": want}),
                       Rule("default", "first", ["panel"])],
                params=Params(fill="adaptive"))))

    # --- D202: `ctx_base`'s own DICT-VALUED keys ---------------------------
    # `cond_subject` ends in `ctx.get(subject)`, and `attrs` / `marker_data`
    # are real keys of `ctx_base` whose value is a DICT - not None, so Python
    # reaches the operator and answers True to `ne`.  `pc_cond_subject` had no
    # answer but "absent", which is False under every operator: measured,
    # `{"subject": "attrs", "op": "ne", "value": "zzz"}` planned 10 pieces
    # natively against `plan.plan_sections`' 12.  It could not reach
    # `Stage = output` because `style._check_cond` calls `attrs` an unknown
    # subject and `_native_ok` refuses on any style warning - protection by
    # coincidence, one keystroke from being lost, which is why the parity is
    # asserted here rather than left to the warning.
    for subj in ("attrs", "marker_data"):
        for op, want in (("ne", "zzz"), ("eq", "zzz"), ("gt", 5.0),
                         ("in", ["zzz"])):
            geo = hou.Geometry()
            cases.polyline(geo, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
                           curve_id="S")
            out.append(("subject_%s_%s" % (subj, op), geo, kit, Style(
                "sd", 1, 3,
                rules=[Rule("default", "conditional", ["gate", "post"],
                            cond={"subject": subj, "op": op, "value": want}),
                       Rule("default", "first", ["panel"])],
                params=Params(fill="adaptive"))))
    return out


def plan_fixture_parity(root):
    """The shape-shaped fixtures, against `plan.plan_sections`, EXACT."""
    from polyfactory.polychain import Kit
    bad = []
    nrun = npiece = 0
    for name, geo, mods, style in fixture_cases():
        case = {"curve": geo, "kit": None}
        kit = Kit("fixture", 1, mods)
        params = style.params
        ref = plan_reference(case, params, style, kit)
        sub = root.createNode("subnet", "fix_%s" % name)
        read, _cfg, nodes = plan_chain(sub, case, params, style, kit, name)
        try:
            read.cook(force=True)
        except Exception:
            pass
        errs = [(n.name(), n.errors()[0].replace("\n", " ")[:200])
                for n in nodes.values() if n.errors()]
        if errs:
            bad.append((name, "%s: %s" % errs[0]))
            sub.destroy()
            continue
        diff = plan_diff(plan_rows(read.geometry()), ref)
        nrun += 1
        npiece += len(ref)
        if diff:
            bad.append((name, "row %d %s" % diff[0]))
        sub.destroy()
    check("plan_fixture_parity", not bad, "%d builds / %d pieces"
          % (nrun, npiece),
          "the SHAPES the style matrix cannot express - a marker's "
          "`markerData` by value type (including the empty string), a "
          "per-point `pc_section` as a STRING and as an int, two prims "
          "sharing one curve id, and non-ASCII curve/style ids through the "
          "`random` selector. Mismatches: %s"
          % ("; ".join("%s %s" % b for b in bad[:3]) or "none"))


def declared_limit_dup_id_marker(root):
    """D169, ASSERTED rather than described: a marker on a DUPLICATED id.

    ⚠️ THIS CHECK EXPECTS A DIFFERENCE.  `resolve_markers` filters markers by
    curve id, so the reference places the gate on BOTH curves carrying the id;
    `pc_markers` is a point wrangle and one point can only bind to one prim,
    so the native chain places it on the FIRST and raises
    `pc_warn_marker_dup`.  That divergence was documented in a comment, warned
    about, and asserted NOWHERE - `place_packed_parity` skips the suite's one
    duplicated-id case and `plan_solve_parity` passes on it only because it
    carries no marker.  A limit nothing measures is a limit that can silently
    become something else, so this is the shape of the gap, in numbers.
    """
    from polyfactory.polychain import Kit, Module, Params, Rule, Style
    mods = [Module("post", (0.12, 1.0, 0.12), pad=(0.0, 0.0), deform=0,
                   roles="default"),
            Module("panel", (2.0, 0.9, 0.05), pad=(0.0, 0.0), deform=1,
                   roles="default"),
            Module("gate", (1.6, 1.2, 0.06), pad=(0.0, 0.0), deform=2,
                   roles="default")]
    geo = hou.Geometry()
    cases.polyline(geo, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)], curve_id="D")
    cases.polyline(geo, [(0.0, 0.0, 6.0), (20.0, 0.0, 6.0)], curve_id="D")
    cases.marker(geo, (8.0, 0.0, 0.0), "D", 7, dist=8.0)
    style = Style("dup", 1, 3,
                  rules=[Rule("marker:7", "first", ["gate"]),
                         Rule("default", "first", ["panel"])],
                  params=Params(fill="adaptive"))
    kit = Kit("dup", 1, mods)
    case = {"curve": geo, "kit": None}
    ref = plan_reference(case, style.params, style, kit)
    sub = root.createNode("subnet", "dupmk")
    read, _cfg, nodes = plan_chain(sub, case, style.params, style, kit, "dupmk")
    try:
        read.cook(force=True)
    except Exception:
        pass
    rows = plan_rows(read.geometry())
    got_gates = sum(1 for r in rows if r["slot"] == "marker:7")
    ref_gates = sum(1 for p in ref if p.slot == "marker:7")
    # the warning the decompose stage raises about it, on the marker point
    dec = nodes["pc_sections"].inputs()[0].geometry()
    warned = 0
    if dec.findPointAttrib("pc_warn_marker_dup") is not None:
        warned = sum(dec.pointIntAttribValues("pc_warn_marker_dup"))
    sub.destroy()
    ok = (ref_gates == 2 and got_gates == 1 and warned == 1
          and len(ref) - len(rows) == 1)
    check("declared_limit_dup_id_marker", ok,
          "ref %d gates / native %d / warned %d" % (ref_gates, got_gates,
                                                    warned),
          "D169, MEASURED: two prims share one curve id and one marker is "
          "bound to it. The reference places the gate on BOTH curves (%d "
          "pieces); the native chain places it on the FIRST and says so "
          "(%d pieces, pc_warn_marker_dup on 1 point). This FAILS if the "
          "divergence changes size in either direction - closing it needs "
          "the marker resolved per PRIM, not per marker point"
          % (len(ref), len(rows)))


def plan_determinism(root, built):
    """Same input, same answer - across cooks, and across INPUT ORDER.

    Three separate claims, because they can fail independently:
      1. a forced re-cook of the same chain is bit-identical (thread
         scheduling);
      2. the same curves fed in REVERSED PRIMITIVE ORDER give the same plan
         (the emission order is (curve_id, section, prim), not cook order);
      3. `PYTHONHASHSEED` does not reach the answer - `seed_for` never
         touches builtin `hash()`, and now neither does the VEX.
    """
    from polyfactory.polychain import Kit, Params, Rule, Style
    mods = stress_cases()[0][1]
    style = Style("det", 1, 11,
                  rules=[Rule("default", "random",
                              ["post", "panel", "gate", "brick"],
                              scope="segment"),
                         Rule("evenly", "first", ["gate"])],
                  params=Params(fill="adaptive", evenly_spacing=6.0))
    kit = Kit("det", 1, mods)

    def digest(geo):
        rows = plan_rows(geo)
        return "|".join("%s@%.17g/%.17g/%.17g" % (r["elem_id"], r["s0"],
                                                  r["s1"], r["scale"])
                        for r in rows)

    def build(order):
        geo = hou.Geometry()
        legs = [([(0.0, 0.0, 0.0), (13.0, 0.0, 0.0)], "A"),
                ([(0.0, 0.0, 5.0), (9.5, 0.0, 5.0), (9.5, 0.0, 14.0)], "B"),
                ([(0.0, 0.0, 9.0), (21.0, 0.0, 9.0)], "C")]
            # the SAME three curves, in the other primitive order
        for pts, cid in (legs if order else list(reversed(legs))):
            cases.polyline(geo, pts, curve_id=cid)
        sub = root.createNode("subnet", "det_%d" % order)
        read, _cfg, nodes = plan_chain(sub, {"curve": geo}, style.params,
                                       style, kit, "det%d" % order)
        read.cook(force=True)
        first = digest(read.geometry())
        again = []
        for _ in range(3):
            nodes["pc_plan_solve"].cook(force=True)
            read.cook(force=True)
            again.append(digest(read.geometry()))
        sub.destroy()
        return (first, again)

    fwd, fwd_again = build(1)
    rev, _rev_again = build(0)
    # the SHUFFLED payload: `choose`'s random branch sorts its pool by
    # (name, variant) precisely so the order the payload lists its modules in
    # cannot reach the answer, and that property has to be asserted where the
    # sort is - in the VEX - and not only in `plan.py`.
    import random as _rnd
    shuffled = list(mods)
    _rnd.Random(5).shuffle(shuffled)
    kit_shuffled = Kit("det", 1, shuffled)
    geo = hou.Geometry()
    for pts, cid in (([(0.0, 0.0, 0.0), (13.0, 0.0, 0.0)], "A"),
                     ([(0.0, 0.0, 5.0), (9.5, 0.0, 5.0), (9.5, 0.0, 14.0)], "B"),
                     ([(0.0, 0.0, 9.0), (21.0, 0.0, 9.0)], "C")):
        cases.polyline(geo, pts, curve_id=cid)
    sub = root.createNode("subnet", "det_shuffled")
    read, _cfg, _n = plan_chain(sub, {"curve": geo}, style.params, style,
                                kit_shuffled, "detsh")
    read.cook(force=True)
    shuf = digest(read.geometry())
    sub.destroy()
    check("plan_ignores_payload_order", shuf == fwd, "%d modules" % len(mods),
          "the SAME kit with its modules listed in a different order plans "
          "identically - `choose` sorts the random pool by (name, variant), "
          "and that is asserted here in the VEX and not only in plan.py")
    check("plan_recook_is_identical", all(d == fwd for d in fwd_again),
          "%d cooks" % (len(fwd_again) + 1),
          "three forced re-cooks of the same chain, digested on elem_id and "
          "the three float64 spans: %s"
          % ("identical" if all(d == fwd for d in fwd_again) else "MOVED"))
    check("plan_distinct_ids_are_input_order_free", fwd == rev,
          "%d chars" % len(fwd),
          "the same three curves - THREE DISTINCT IDS - fed in REVERSED "
          "primitive order plan identically. ⚠️ ITS SCOPE IS IN ITS NAME: "
          "with distinct ids the sort key (curve_id, section, prim) is "
          "already total, so this cannot see the prim tie-break at all. "
          "`plan_shared_id_is_order_sensitive` is the check that can")
    check("plan_digest_is_not_empty", len(fwd) > 200, len(fwd),
          "the determinism digest is non-trivial, so the two checks above "
          "are not comparing two empty strings")


def plan_shared_id_order(root):
    """Primitive order over TWO PRIMS SHARING ONE `pc_curve_id`.

    ⚠️ `plan_is_input_order_free` CANNOT REACH THIS AND SAYS SO NOW.  It
    builds its two orders out of three DISTINCT ids, where the sort key
    `(curve_id, section_index, prim)` is already total - so the prim term is
    dead weight there and mutating it cannot redden the check.  The one
    topology where primitive order genuinely decides the answer is two prims
    with the SAME id: `decompose_all` sorts by `(str(curve_id), index)` and
    Python's sort is STABLE, so their sections interleave in PRIM order and
    the plan is different in the two orders - on BOTH sides.

    So the claim is not "order-free"; it is "order-sensitive the same way".
    That is what this asserts: native == reference in each order, and the two
    orders differ, which is what makes the first half non-vacuous.
    """
    from polyfactory.polychain import Kit, Module, Params, Rule, Style
    mods = [Module("post", (0.12, 1.0, 0.12), pad=(0.0, 0.0), deform=0,
                   roles="default"),
            Module("panel", (2.0, 0.9, 0.05), pad=(0.0, 0.0), deform=1,
                   roles="default")]
    style = Style("shared", 1, 4,
                  rules=[Rule("default", "random", ["post", "panel"],
                              scope="section")],
                  params=Params(fill="adaptive"))
    kit = Kit("shared", 1, mods)
    legs = [([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 8.0)], "A"),
            ([(0.0, 0.0, 20.0), (7.0, 0.0, 20.0), (7.0, 0.0, 26.0)], "A")]

    def run(order):
        geo = hou.Geometry()
        for pts, cid in (legs if order else list(reversed(legs))):
            cases.polyline(geo, pts, curve_id=cid)
        case = {"curve": geo, "kit": None}
        ref = plan_reference(case, style.params, style, kit)
        sub = root.createNode("subnet", "shared_%d" % order)
        read, _cfg, _n = plan_chain(sub, case, style.params, style, kit,
                                    "shared%d" % order)
        read.cook(force=True)
        rows = plan_rows(read.geometry())
        sub.destroy()
        digest = "|".join("%s@%.17g" % (r["elem_id"], r["s0"]) for r in rows)
        return (plan_diff(rows, ref), digest, len(rows))

    d_fwd, dig_fwd, n_fwd = run(1)
    d_rev, dig_rev, n_rev = run(0)
    check("plan_shared_id_matches_reference_in_both_orders",
          not d_fwd and not d_rev, "%d / %d pieces" % (n_fwd, n_rev),
          "two prims carrying ONE curve id, fed in both primitive orders, "
          "against `plan.plan_sections` on the same input. Mismatches: %s"
          % ((d_fwd or d_rev)[:1] or "none"))
    check("plan_shared_id_is_order_sensitive", dig_fwd != dig_rev,
          "%d chars" % len(dig_fwd),
          "and the two orders genuinely DISAGREE - Python's stable sort "
          "interleaves the two curves' sections in prim order, so the check "
          "above is a claim about a tie-break and not about nothing. If this "
          "ever goes green-by-equality, the check above has stopped testing "
          "`pc_sections`' `r_prim` tie-break")


def _kit_scale_run(root, nmods, snippet=None, passes=2):
    """The plan chain on a 2 km fence with an `nmods`-module kit, timed.

    Only `pc_plan_solve` is timed, behind a nudge wrangle - D164: a forced
    cook of a node whose inputs have not changed can be a no-op, so the pass
    is dirtied and `cookCount` is returned for the caller to assert on.
    """
    from polyfactory.polychain import Kit, Module, Params, Rule, Style

    mods = [Module("m%03d" % i, (2.0, 0.9, 0.05), pad=(0.0, 0.0), deform=1,
                   roles="default", variant="v%d" % (i % 7))
            for i in range(nmods)]
    kit = Kit("scale", 1, mods)
    style = Style("scale", 1, 3,
                  rules=[Rule("default", "random", [], scope="segment")],
                  params=Params(fill="adaptive"))
    geo = hou.Geometry()
    cases.polyline(geo, [(0.0, 0.0, 0.0), (2000.0, 0.0, 0.0)], curve_id="S")

    sub = root.createNode("subnet", "kitscale_%d_%d" % (nmods, snippet is None))
    src = native.feed(sub, geo, "IN")
    cfg = native.config_full(sub, style.params, style, kit, "config")
    last, _dec = native.stage_decompose(sub, src, cfg)
    plan, pnodes = native.stage_plan(sub, last, cfg)
    solve = pnodes["pc_plan_solve"]
    if snippet is not None:
        solve.parm("snippet").set(snippet)
    dirt = sub.createNode("attribwrangle", "solve_dirty")
    dirt.parm("class").set(2)
    group = dirt.parmTemplateGroup()
    group.append(hou.IntParmTemplate("nudge", "Nudge", 1))
    dirt.setParmTemplateGroup(group)
    dirt.parm("snippet").set('i@_bench = chi("nudge");')
    dirt.setInput(0, pnodes["pc_plan_clean"])
    solve.setInput(0, dirt)
    plan.cook(force=True)
    npieces = len(plan.geometry().points())
    before = solve.cookCount()
    best = None
    for i in range(passes):
        dirt.parm("nudge").set(i + 2)
        t0 = time.time()
        solve.cook()
        dt = time.time() - t0
        best = dt if best is None else min(best, dt)
    cooked = solve.cookCount() - before
    sub.destroy()
    return (best, npieces, cooked)


def plan_kit_scale(root):
    """4.2's cost must not grow with the KIT, and it grew like a cube.

    ⚠️ EVERY FIXTURE IN THE SUITE USES A FIVE-MODULE KIT, which is why nothing
    saw this.  `pc_choose` re-resolved the candidate pool, re-sorted it and
    re-weighed it on EVERY PIECE, and each insertion-sort comparison called
    `pc_m_variant`, which copies the whole `pc_k_variant` detail array.
    Measured on the plan chain, 2 km fence, 1 000 pieces held constant, one
    `default` rule that names no modules so the kit resolves by ROLE:

        modules       1        51       151
        `first`     0.051 s  0.051 s   0.053 s     (flat - D175's hoist)
        `random`    0.283 s  2.632 s  66.493 s     <- the defect
        after       0.267 s  0.295 s   0.309 s

    An artist with a 150-module facade kit and one `random` rule waited over a
    minute per plan cook where the same style with `first` takes 0.05 s.
    """
    from polyfactory.polychain import vexsrc

    t1, n1, c1 = _kit_scale_run(root, 1)
    t61, n61, c61 = _kit_scale_run(root, 151)
    ratio = t61 / max(t1, 1e-6)
    check("plan_cost_is_flat_in_kit_size",
          c1 == 2 and c61 == 2 and n1 == n61 and ratio < 3.0,
          "%.2fx (%.0f ms -> %.0f ms, %d pieces)"
          % (ratio, t1 * 1000.0, t61 * 1000.0, n1),
          "`pc_plan_solve` alone, 1 000 pieces held constant, kit 1 -> 151 "
          "modules resolved by role under `random` (cookCount 2 and 2). "
          "Ceiling 3.0x: the pool is resolved once per RUN now, so the only "
          "growth left is the one-off sort. Before the hoist this measured "
          "~10x at 51 modules and 235x at 151")

    # THE MUTATION IS BOTH HALVES, because the shipped code had both and they
    # compound.  (a) rebuild the pool per piece - which is exactly what
    # `pc_choose` does - and (b) put the ACCESSOR back inside the comparator,
    # so each of the sort's O(n^2) comparisons copies the whole
    # `pc_k_variant` detail array again.  (a) alone measures 1.7x; (b) alone
    # is free while the sort runs once per run.  Together they are the cube
    # the suite never saw.
    body = vexsrc.source("pc_plan_solve")
    call_new = ('pc_pick_from_pool(r, cfi, cs_slot, "default", idx,\n'
                '                                      curve_id, sec_index, '
                'p_ci, p_cn, p_ord,\n'
                '                                      p_w, p_total, gi, gn, '
                'ok);')
    call_old = ('pc_choose(r, cfi, cs_slot, "default", idx, curve_id,\n'
                '                              sec_index, yclass, gi, gn, '
                'ok);')
    cmp_new = ('            if (cn[a] < cn[b] || (cn[a] == cn[b] && '
               'cv[a] <= cv[b])) break;')
    cmp_old = ('            string va = pc_m_variant(ci[a]), '
               'vb = pc_m_variant(ci[b]);\n'
               '            if (cn[a] < cn[b] || (cn[a] == cn[b] && '
               'va <= vb)) break;')
    found = body.count(call_new)
    found_cmp = body.count(cmp_new)
    mutated = body.replace(call_new, call_old).replace(cmp_new, cmp_old)
    tm, _nm, _cm = _kit_scale_run(root, 151, snippet=mutated, passes=1)
    check("mutation_plan_pool_per_piece",
          found == 2 and found_cmp == 1 and tm > t61 * 5.0,
          "%.0f ms vs %.0f ms sound (targets %d/%d)"
          % (tm * 1000.0, t61 * 1000.0, found, found_cmp),
          "restoring the code that shipped - the pool rebuilt per piece AND "
          "`pc_m_variant` called inside the sort comparator, which copies a "
          "whole detail array per comparison - takes the solve from %.0f ms "
          "to %.0f ms on the same 151-module kit. The ceiling above is a "
          "measurement, not a decoration" % (t61 * 1000.0, tm * 1000.0))


def plan_mutation(root, built):
    """Corrupt the solve and confirm the parity goes red."""
    from polyfactory.polychain import kit as KIT
    from polyfactory.polychain import vexsrc

    case = built["A_straight"]
    style = case["style"]
    params = style.params
    kit = KIT.read(case["kit"])[0]
    ref = plan_reference(case, params, style, kit)

    def run(mutate):
        sub = root.createNode("subnet", "planmut")
        read, _cfg, nodes = plan_chain(sub, case, params, style, kit, "mut")
        if mutate:
            mutate(nodes)
        try:
            read.cook(force=True)
        except Exception:
            sub.destroy()
            return None
        if any(n.errors() for n in nodes.values()):
            sub.destroy()
            return None
        rows = plan_rows(read.geometry())
        sub.destroy()
        return rows

    sound = run(None)
    check("plan_mutation_baseline", not plan_diff(sound, ref), len(sound),
          "the un-mutated chain is at parity, so a red below is the mutation")

    # (a) the ADD-ONE-MORE threshold. 4.2's `adaptivePct` is one comparison in
    # `fit`, and getting it backwards changes the piece COUNT, not a rounding.
    body = vexsrc.source("pc_plan_solve")
    target = ">= pc_cfg_f(\"adaptive_pct\", 50.0) - PC_PEPS"
    hdr = vexsrc.source("pc_plan.h")
    has_target = target in hdr
    got = run(lambda n: n["pc_plan_solve"].parm("snippet").set(
        body.replace(target, "> 200.0 +")))
    check("mutation_plan_adaptive_threshold",
          has_target and (got is None or plan_diff(got, ref)),
          "%s" % ("red" if (got is None or plan_diff(got, ref)) else "GREEN"),
          "breaking 4.2's add-one-more threshold changes the piece count and "
          "the parity must see it (target line present: %s)" % has_target)

    # (b) the EMITTER's piece count. `pc_plan_emit` reads `_npieces` and
    # loops it; miscounting is the failure mode 13.2 warned about in the
    # `pointgenerate` shape ("the attribute MULTIPLIES nptsperpt") and it
    # survives the change of mechanism.
    emit_body = vexsrc.source("pc_plan_emit")
    got = run(lambda n: n["pc_plan_emit"].parm("snippet").set(
        emit_body.replace(
            "int n = via_row ? npieces : min(npieces, len(p_slot));",
            "int n = (via_row ? npieces : min(npieces, len(p_slot))) - 1;")))
    check("mutation_plan_emit_count", got is None or plan_diff(got, ref),
          "%s" % ("red" if (got is None or plan_diff(got, ref)) else "GREEN"),
          "dropping ONE piece per section reddens the parity - the emitter's "
          "own loop bound is asserted, not assumed")

    # (c) the PRECISION rule. Every function in pc_plan.h needs int64 and
    # float64; at 32 bits they all still COMPILE.
    got = run(lambda n: n["pc_plan_solve"].parm("vex_precision").set("32"))
    check("mutation_plan_precision_32", got is None or plan_diff(got, ref),
          "%s" % ("red" if (got is None or plan_diff(got, ref)) else "GREEN"),
          "the solve at vex_precision = 32 compiles and answers differently")

    # (d) the CLEAN node, which is the float32 `pc_u` shadow.
    # ⚠️ IT HAS TO RUN ON A CASE THAT CARRIES A MARKER.  Bypassed on
    # `A_straight` this mutation is GREEN and says nothing: 3.1 puts `pc_u` on
    # the MARKER CLOUD, so a fence with no markers has no float32 `pc_u` to
    # shadow the plan's own with. Measured - the first version of this check
    # passed while proving nothing.
    mcase = built["N_marker_mixed"]
    mstyle = mcase["style"]
    mkit = KIT.read(mcase["kit"])[0]
    mref = plan_reference(mcase, mstyle.params, mstyle, mkit)

    def run_marker(mutate):
        sub = root.createNode("subnet", "planmut_mk")
        read, _cfg, nodes = plan_chain(sub, mcase, mstyle.params, mstyle,
                                       mkit, "mutmk")
        if mutate:
            mutate(nodes)
        try:
            read.cook(force=True)
        except Exception:
            sub.destroy()
            return None
        if any(n.errors() for n in nodes.values()):
            sub.destroy()
            return None
        rows = plan_rows(read.geometry())
        sub.destroy()
        return rows

    check("plan_mutation_marker_baseline", not plan_diff(run_marker(None), mref),
          len(mref), "the marker case is at parity before the mutation below")
    got = run_marker(lambda n: n["pc_plan_clean"].bypass(True))
    check("mutation_plan_clean_bypassed", got is None or plan_diff(got, mref),
          "%s" % ("red" if (got is None or plan_diff(got, mref)) else "GREEN"),
          "bypassing pc_plan_clean lets the artist's float32 pc_u shadow the "
          "plan's own, and u comes back 3e-9 off on a marker case")


# --- 13.9 N4: the packed branch, and R8 -------------------------------------


def asset_on(root, case, stage, tag):
    """The SHIPPED asset, on `case`, at `stage`.  -> (node, geometry|None)."""
    from polyfactory.polychain import style as STYLE
    node = root.createNode("pf_polychain", "asset_%s" % tag)
    node.setInput(0, native.feed(root, case["curve"], "AC_%s" % tag))
    kit_geo = case["kit"]
    if kit_geo is not None:
        node.setInput(1, native.feed(root, kit_geo, "AK_%s" % tag))
    if case["style"] is not None:
        style_geo = hou.Geometry()
        STYLE.write(style_geo, case["style"])
        node.setInput(2, native.feed(root, style_geo, "AS_%s" % tag))
    # ⚠️ AND THE SURFACE, WHICH THIS HELPER USED TO DROP ON THE FLOOR. Every
    # `B*_conform_*` case was cooked with input 4 UNWIRED, so a check asking
    # "did the guard hand this build to the native chain" was answering about
    # a build with no terrain in it - and 4.5 is the largest thing the native
    # chain cannot do. `place_packed_parity` never noticed because it skips
    # those cases by name; `output_guard_parity` would have counted eleven of
    # them as native successes.
    surface = case.get("surface")
    if surface is not None:
        node.setInput(3, native.feed(root, surface, "AF_%s" % tag))
    node.parm("stage").set(stage)
    try:
        node.cook(force=True)
    except Exception:
        return (node, None)
    if node.errors():
        return (node, None)
    return (node, node.geometry())


def _place_out_of_scope(case, params):
    """Why this case cannot be compared yet, or "" when it can.

    ⚠️ EVERY ROW HERE IS AN UNPORTED STAGE, NAMED, AND THE CHECK PRINTS THE
    LIST - a scope that quietly shrinks until the check is green is the
    "unfailable" pattern cycle P2-3V found six times.
    """
    from polyfactory.polychain import decompose as D
    if case["kit"] is None:
        return "no kit (3.4's stand-in has no geometry to measure)"
    if case.get("surface") is not None:
        return "4.5 conform - N6"
    if params.fillet_radius > 0.0:
        return "4.3 fillet - N8"
    if params.fix_slope:
        return "4.4 slope flatten - N5"
    if params.flatten_stepped:
        return "D98 flatten-under - N5"
    if case.get("overrides"):
        # 4.6's swap / replace cascade rewrites the module AFTER the plan, so
        # the same address names a different piece in the two builds.
        return "4.6 overrides - N7"
    curves, markers = P.read_curves(case["curve"])
    if any(D.resolve_corners(c, params) for c in curves):
        # 4.3 reserves span off both ends of every leg, so the SAME element
        # address names a different span in the two plans. That is N8, and it
        # is a different question from the one this check asks.
        return "4.3 corners - N8"
    ids = [str(c.curve_id) for c in curves]
    if len(set(ids)) != len(ids):
        return "D169 duplicated curve id - the marker binds to one prim"
    return ""


# 3.4 attributes the native branch CANNOT publish yet, each named with the
# 13.9 item that owes it.  This is a DECLARED list and not a tolerance: the
# stamp check fails on any name outside it, and `place_stamp_owed_is_live`
# fails on any entry here that no case exercises - so an exemption cannot be
# added for a defect and it cannot rot into decoration either.
STAMP_OWED = {
    "pc_cap": "4.6 slice caps - N7",
    "pc_cap_material": "4.6 slice caps - N7",
    "pc_warn_bend_resolution": "D25's bend deviation - N5",
}
# ⚠️ `pc_warn_degenerate_frame` AND `pc_warn_corner_degenerate` WERE ON THAT
# LIST AND ARE NOT ANY MORE - the deform gate raises both now (D32, one ratio
# each), which is what `place_stamp_owed_is_live` is for: an exemption that
# stops being needed FAILS rather than sitting there looking harmless.


def place_packed_parity(root, built):
    """13.9 N4 and R8, measured: `copytopoints(pack=1)` vs the reference.

    ⚠️ WHAT IS COMPARED, AND WHAT IS NOT.  Every packed prim the reference
    built is looked up by `pc_elem_id` and compared against the native
    branch's own prim of the same address - its float32 `P` and its WORLD
    BOUNDS, which is where a wrong pivot, a wrong module or a wrong scale
    would show.  A piece the reference did NOT keep packed is not compared,
    because 13.9 N5's deform gate is not built; a case with a surface, a
    fillet or a slope flatten is skipped whole, because `pc_proto` declares
    those unanswerable (4.5's normal is N6's) rather than guessing.

    ⚠️ AND 4.3 IS NOT BUILT (N8), so on a corner-heavy case the native plan
    has no corner assembly and no reserve.  Those pieces simply have no
    counterpart and drop out of the match; the ones that DO match still have
    to be bit-identical, which is what makes this check about the COPY.
    """
    worst_p = worst_b = 0.0
    nprim = ncase = 0
    bad = []
    per = []
    scope = {}
    skipped = 0
    stamp_bad = {}
    stamp_owed = {}
    stamp_n = [0]
    cover_bad = []
    cover_n = [0]
    cover_gap = [0]
    for name in sorted(built):
        name_ = name
        case = built[name]
        ref_packed = [p for p in case["out"].prims()
                      if p.type() == hou.primType.PackedGeometry]
        if not ref_packed:
            skipped += 1
            continue
        params = case["style"].params if case["style"] else DEFAULTS
        why = _place_out_of_scope(case, params)
        if why:
            skipped += 1
            scope.setdefault(why, []).append(name)
            continue
        node, geo = asset_on(root, case, "place_native", name)
        if geo is None:
            bad.append((name, "cook: %s"
                        % (node.errors()[0].replace("\n", " ")[:120]
                           if node.errors() else "?")))
            continue
        ref = {}
        for p in ref_packed:
            try:
                ref[p.attribValue("pc_elem_id")] = p
            except hou.OperationFailed:
                pass
        # 3.4's STAMP, which nothing compared until this cycle. The reference
        # publishes `ELEM_PRIM_ATTRS` plus one int per warning; the native
        # branch published nine of the fourteen and got one of those WRONG -
        # `pc_section` carried the section KEY as a float where 3.4 and
        # `_stamp_values` both say the section INDEX as an int.
        ref_types = dict((a.name(), a.dataType()) for a in
                         case["out"].primAttribs())
        nat_types = dict((a.name(), a.dataType()) for a in geo.primAttribs())
        # BOTH DIRECTIONS, over every prim attribute either side publishes -
        # not over 3.4's fourteen names. A branch that publishes MORE than
        # the reference is a contract nobody wrote (`COPY_ATTRIBS` had three
        # such names once), and a per-element WARNING that never reached the
        # prim would be invisible to a list of the fourteen.
        for name in sorted(set(ref_types) | set(nat_types)):
            if name in STAMP_OWED and name not in nat_types:
                stamp_owed.setdefault(name, []).append(name_)
            elif name not in nat_types:
                stamp_bad.setdefault("%s: absent" % name, []).append(name_)
            elif name not in ref_types:
                stamp_bad.setdefault("%s: extra" % name, []).append(name_)
            elif nat_types[name] != ref_types[name]:
                stamp_bad.setdefault(
                    "%s: %s not %s" % (name, nat_types[name],
                                       ref_types[name]), []).append(name_)
        matched = 0
        case_worst = 0.0
        for p in geo.prims():
            try:
                eid = p.attribValue("pc_elem_id")
            except hou.OperationFailed:
                continue
            r = ref.get(eid)
            if r is None:
                continue
            pa = p.points()[0].position()
            pb = r.points()[0].position()
            worst_p = max(worst_p, max(abs(pa[i] - pb[i]) for i in range(3)))
            ba = p.intrinsicValue("bounds")
            bb = r.intrinsicValue("bounds")
            d = max(abs(x - y) for x, y in zip(ba, bb))
            worst_b = max(worst_b, d)
            case_worst = max(case_worst, d)
            matched += 1
            for aname in sorted(ref_types):
                if aname not in nat_types or aname in STAMP_OWED:
                    continue
                want = r.attribValue(aname)
                got = p.attribValue(aname)
                if got != want:
                    stamp_bad.setdefault(
                        "%s: %r not %r" % (aname, got, want), []).append(eid)
            stamp_n[0] += 1
        nprim += matched
        # ⚠ AND THE ELEMENT SET, NOT ONLY THE ELEMENTS THAT HAPPEN TO PAIR.
        # Until 13.9 N5's gate landed, EVERY piece went to `copytopoints` and
        # a piece the reference deformed simply had no counterpart here - so
        # the loop above compared a SUBSET and called it parity. With the gate
        # the branch is supposed to build exactly the reference's packed set,
        # and that is a claim about the two SETS.
        got_ids = set()
        for p_ in geo.prims():
            try:
                got_ids.add(p_.attribValue("pc_elem_id"))
            except hou.OperationFailed:
                pass
        # 3.4's STAND-IN BOX is the one declared gap: "blank stand-in box at
        # nominal size, never a failure". `pc_proto` cannot MEASURE a module
        # that is not in the kit, so it declines the piece and D154's native
        # `box` SOPs are what will build it (N7). The element is counted and
        # printed, not skipped silently.
        gapped = set()
        for eid, r_ in ref.items():
            try:
                if int(r_.attribValue("pc_warn_kit_gap")):
                    gapped.add(eid)
            except hou.OperationFailed:
                pass
        only_ref = sorted(set(ref) - got_ids - gapped)
        only_nat = sorted(got_ids - set(ref))
        cover_gap[0] += len(gapped & (set(ref) - got_ids))
        if only_ref or only_nat:
            cover_bad.append((name_, len(only_ref), len(only_nat),
                              (only_ref or only_nat)[0]))
        cover_n[0] += len(ref)
        if matched:
            ncase += 1
            per.append((case_worst, name, matched))
    # float64 noise at fixture scale, and nothing else: the two sides run the
    # SAME arithmetic and both land in float32 storage, so this is parity and
    # not a new floor (13.8's third row).
    check("place_packed_parity", worst_p == 0.0 and worst_b < 1e-9 and not bad,
          "%d cases / %d prims" % (ncase, nprim),
          "copytopoints(pack=1) against the reference's own packed prims, "
          "matched on pc_elem_id: worst |dP| %.3e m, worst |d world bounds| "
          "%.3e m (%d cases skipped - conform, fillet or slope flatten, which "
          "pc_proto declares unanswerable). %s"
          % (worst_p, worst_b, skipped,
             "; ".join("%s %s" % b for b in bad[:2]) or ""))
    for why in sorted(scope):
        print("        out of scope  %-42s %d case(s)"
              % (why, len(scope[why])))
    check("place_packed_covers_the_reference",
          not cover_bad and cover_gap[0] > 0, cover_n[0],
          "the native branch builds EXACTLY the reference's packed element "
          "set on every in-scope case - not a subset - bar %d element(s) that "
          "are 3.4's STAND-IN BOX for a module the kit does not carry, which "
          "13.9 N7 owes and which this row fails on if it ever reads 0. "
          "Disagreeing: %s"
          % (cover_gap[0],
             "; ".join("%s (+%d ref / +%d native, e.g. %s)" % b
                       for b in cover_bad[:3]) or "none"))
    check("place_packed_is_not_empty", nprim > 400, nprim,
          "packed prims actually compared - a branch that built none would "
          "make the check above vacuously green")

    # ⚠️ THE STAMP, AND IT HAD NEVER BEEN COMPARED. `place_packed_parity`
    # above measures `P` and the world bounds; every one of 3.4's fourteen
    # prim attributes rode out of the native branch unasserted, and the
    # `copytopoints` list that carries them is nine names long. Measured
    # before the fix: `pc_deformed`, `pc_generated`, `pc_corner_cut`,
    # `pc_style` and `pc_replaced` were ABSENT, and `pc_section` disagreed on
    # every prim of a multi-section run - the artist's section KEY, as a
    # float, where `_stamp_values` writes the section INDEX as an int.
    keys = sorted(stamp_bad)
    for k in keys:
        print("        stamp complaint  %-46s %s"
              % (k, sorted(set(stamp_bad[k]))[:6]))
    for name in sorted(stamp_owed):
        print("        stamp owed       %-30s %-28s %d case(s)"
              % (name, STAMP_OWED[name], len(stamp_owed[name])))
    dead = sorted(set(STAMP_OWED) - set(stamp_owed))
    check("place_stamp_owed_is_live", not dead, len(STAMP_OWED),
          "every declared-owed attribute is exercised by at least one case, "
          "so the exemption list cannot rot into decoration. Never fired: %s"
          % (", ".join(dead) or "none"))
    check("place_stamp_parity", not stamp_bad,
          "%d prims / %d complaints" % (stamp_n[0], len(keys)),
          "3.4's fourteen prim attributes - NAME, TYPE and VALUE - on every "
          "packed prim matched by pc_elem_id: %s"
          % ("; ".join("%s (%d)" % (k, len(stamp_bad[k])) for k in keys[:4])
             or "identical"))


def gate_parity(root, built):
    """13.9 N5 - the deform gate, against `place._needs_deform` itself.

    ⚠️ THIS IS A BOOLEAN PER PIECE AND IT DECIDES THE WHOLE COST MODEL.  A
    piece the gate keeps packed is one packed prim sharing one `geometryid`; a
    piece it unpacks is ~36 real points.  D69 measured the difference on
    PC-G3's own shape: 10 005 packed at 0.42 s and +12 MB against 10 005
    deformed at 21.9 s and 360 180 points.  So a gate that is 99 % right is
    not 99 % right, it is a tool that silently costs fifty times what it
    should on the exact input citygen hands it.

    The reference's answer is read where it SHIPS - `pc_deformed` on the built
    prim - and not from calling `_needs_deform` again, because the question is
    whether the two implementations segregate the same elements, not whether
    two calls of one function agree.  A deformed element is many prims, so the
    reference's answer is the max over the element's own prims.

    Cases where the gate declares itself unanswerable (`_gate_valid = 0`) are
    counted and printed separately - that is D99's band and 4.5's drape, both
    named in `pc_deform_gate.vfl` - and a piece that is never judged is not
    quietly scored as agreeing.
    """
    agree = disagree = unjudged = 0
    per_case = {}
    bad = []
    ncase = 0
    both = [0, 0]
    for name in sorted(built):
        case = built[name]
        params = case["style"].params if case["style"] else DEFAULTS
        if _place_out_of_scope(case, params):
            continue
        node, geo = asset_on(root, case, "gate", name + "_g")
        if geo is None:
            bad.append((name, "cook"))
            continue
        ref = {}
        for prim in case["out"].prims():
            try:
                eid = prim.attribValue("pc_elem_id")
                dfm = int(prim.attribValue("pc_deformed"))
            except hou.OperationFailed:
                continue
            ref[eid] = max(ref.get(eid, 0), dfm)
        matched = 0
        wrong = 0
        for pt in geo.points():
            try:
                eid = pt.attribValue("pc_elem_id")
            except hou.OperationFailed:
                continue
            if eid not in ref:
                continue
            if not int(pt.attribValue("pc_gate_valid")):
                unjudged += 1
                continue
            got = int(pt.attribValue("pc_deformed"))
            want = ref[eid]
            both[want] += 1
            matched += 1
            if got != want:
                wrong += 1
                if len(bad) < 6:
                    bad.append((name, "%s: %d not %d" % (eid, got, want)))
        agree += matched - wrong
        disagree += wrong
        if matched:
            ncase += 1
            per_case[name] = (matched, wrong)
        node.destroy()
    check("gate_parity", not disagree and not bad, "%d cases / %d pieces"
          % (ncase, agree + disagree),
          "`pc_deformed` at the gate against the reference's own `pc_deformed`, matched "
          "on pc_elem_id: %d agree, %d disagree, %d unjudged (D99's band or "
          "4.5's drape - the gate declares those). %s"
          % (agree, disagree, unjudged,
             "; ".join("%s %s" % b for b in bad[:3]) or "identical"))
    # ⚠️ AND BOTH ANSWERS HAVE TO APPEAR.  A gate that returned 0 for
    # everything would agree with a suite whose in-scope cases happen to be
    # all-packed, which is exactly the vacuous shape P2-3V found six times.
    check("gate_parity_sees_both_answers", both[0] > 100 and both[1] > 0,
          "%d packed / %d deformed" % (both[0], both[1]),
          "the compared pieces must contain BOTH answers or the parity above "
          "is a check that the gate returns a constant")


def gate_mutation(root, built):
    """Move the curvature budget and watch `gate_parity` part company.

    The mutation is D75's own lever - the tolerance the artist sets - so it
    changes nothing but the answer, which is the property the check is about.
    """
    name = None
    for candidate in sorted(built):
        case = built[candidate]
        params = case["style"].params if case["style"] else DEFAULTS
        if _place_out_of_scope(case, params):
            continue
        name = candidate
        break
    case = built[name]
    node, geo = asset_on(root, case, "gate", name + "_gm")
    node.allowEditingOfContents()
    gate = node.node("pc_deform_gate")
    body = gate.parm("snippet").eval()
    target = "if (dev > tol) {"
    found = target in body
    gate.parm("snippet").set(body.replace(target, "if (dev >= -1.0) {"))
    node.cook(force=True)
    flipped = sum(int(p.attribValue("pc_deformed"))
                  for p in node.geometry().points())
    node.destroy()
    check("mutation_pc_deform_gate", found and flipped > 0,
          "%d pieces flipped" % flipped,
          "dropping the curvature budget to -1 m unpacks every piece of `%s` "
          "- the answer `gate_parity` compares is therefore the gate's and "
          "not a constant the check would agree with anyway" % name)


def r8_packed_transform(root):
    """R8: does the packed `transform` intrinsic carry the UNIFORM SCALE?

    13.2 wrote a 3x3 through `setprimintrinsic` and read `bounds` back, found
    no scale, and recorded R8 - "the mechanism exists; the scale semantics are
    unverified".  This asks `packedfulltransform` instead, which is what 13.9
    said to re-check against, on three scales including one at 20 km.
    """
    from polyfactory.polychain import kit as KIT
    import math
    sub = root.createNode("subnet", "r8")
    kit_src = native.feed(sub, KIT.starter_kit(), "KIT")
    kid = native.wrangle(sub, "pc_kit_id", "primitive", "pc_kit_id")
    kid.setInput(0, kit_src)
    pts = sub.createNode("add", "pts")
    pts.parm("points").set(3)
    frames = native.wrangle(sub, "frames", "point", "pc_kit_id")
    frames.parm("snippet").set("""
float S[] = array(1.0, 2.5, 0.37);
float ANG[] = array(0.0, 30.0, 137.0);
float X[] = array(0.0, 5.0, 20000.0);
string M[] = array("post", "panel", "gate");
float s = S[@ptnum], a = radians(ANG[@ptnum]);
matrix3 m = set(cos(a), 0.0, -sin(a), 0.0, 1.0, 0.0, sin(a), 0.0, cos(a)) * s;
3@transform = m;
@P = set(X[@ptnum], 0.0, 0.0);
s@pc_module = M[@ptnum];
""")
    frames.parm("class").set(2)
    frames.setInput(0, pts)
    copy = sub.createNode("copytopoints::2.0", "copy")
    copy.setInput(0, kid)
    copy.setInput(1, frames)
    copy.parm("pack").set(True)
    copy.parm("pivot").set("origin")
    copy.parm("useimplicitn").set(False)
    copy.parm("useidattrib").set(True)
    copy.parm("idattrib").set("pc_module")
    copy.cook(force=True)
    want = (1.0, 2.5, 0.37)
    got = []
    for prim in copy.geometry().prims():
        xf = prim.intrinsicValue("packedfulltransform")
        got.append(math.sqrt(xf[0] ** 2 + xf[1] ** 2 + xf[2] ** 2))
    worst = max(abs(a - b) for a, b in zip(sorted(got), sorted(want))) \
        if len(got) == 3 else 1.0
    sub.destroy()
    check("r8_packed_scale_survives", worst < 1e-9,
          "%.3e" % worst,
          "R8 CLOSED - the uniform scale in a 3x3 `transform` attribute DOES "
          "reach packedfulltransform (asked for %s, measured %s). 13.2 read "
          "`bounds` and concluded it did not."
          % (list(want), ["%.6f" % g for g in sorted(got)]))


def place_duplicate_module_name(root):
    """A kit with TWO prims called `post` - and all three resolvers agree.

    ⚠️ THREE THINGS RESOLVE A MODULE NAME AND THEY HAVE TO PICK THE SAME ONE.
    `Kit._by_name` is a dict comprehension, so a repeated `pc_name` is won by
    the LAST module carrying it; `pc_kit_by_name` walks the kit backwards for
    exactly that reason; `copytopoints`' `useidattrib` was measured to pick
    the last too.  `pc_proto` - which MEASURES the module the frame is built
    from - walked FORWARDS, so the plan fitted one module and the copy pasted
    another: measured on 0.5 / 1.0 / 2.0 m prims all named "post", the
    reference built 10 pieces 2.0000 m long and the native branch built them
    8.0000 m long (2.0 m of geometry scaled by 2.0 / 0.5), with
    `node.warnings()` empty.  Reversing the kit payload made the error vanish,
    which is what an order dependence looks like.

    `place_packed_parity` matches by `pc_elem_id`, so it would have caught
    this the moment such a fixture existed.  This is that fixture.
    """
    from polyfactory.polychain import kit as K
    from polyfactory.polychain import place as PL
    from polyfactory.polychain import Params, Rule, Style

    kit_geo = hou.Geometry()
    for length in (0.5, 1.0, 2.0):
        body = hou.Geometry()
        K.box_mesh(body, 0.0, length, 0.0, 1.0, -0.05, 0.05, 1)
        K.add_module(kit_geo, "post", body, size=(length, 1.0, 0.1),
                     deform=0, zmode="vertical", roles="default")
    K.write_manifest(kit_geo, "pf_dupname", 1,
                     sources=("run_native_checks.place_duplicate_module_name",),
                     human_scale_reference=1.8)
    spline = hou.Geometry()
    cases.polyline(spline, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)], curve_id="S")
    style = Style("dupname", 1, 1,
                  rules=[Rule("default", "first", ["post"])],
                  params=Params(fill="adaptive"))
    case = {"curve": spline, "kit": kit_geo, "style": style}

    ref_geo, _r = PL.build(spline, kit_geo, style, params=style.params)
    ref_x = sorted(round(p.intrinsicValue("bounds")[1]
                         - p.intrinsicValue("bounds")[0], 6)
                   for p in ref_geo.prims()
                   if p.type() == hou.primType.PackedGeometry)
    node, geo = asset_on(root, case, "place_native", "dupname")
    got_x = []
    if geo is not None:
        got_x = sorted(round(p.intrinsicValue("bounds")[1]
                             - p.intrinsicValue("bounds")[0], 6)
                       for p in geo.prims()
                       if p.type() == hou.primType.PackedGeometry)
    ok = bool(ref_x) and got_x == ref_x
    check("place_duplicate_module_name", ok,
          "native %s / ref %s" % (got_x[:1] or "-", ref_x[:1] or "-"),
          "%d native prims vs %d reference prims, compared on the packed X "
          "extent: LAST-wins in `Kit._by_name`, in `pc_kit_by_name`, in "
          "`pc_proto` and in `copytopoints`' own `useidattrib`. A forward "
          "walk in `pc_proto` alone reads %s here"
          % (len(got_x), len(ref_x), "8.0" if ref_x and ref_x[0] == 2.0
             else "the wrong module"))


def native_place_says_why_it_is_empty(root):
    """An unported build must WARN, not just ship nothing.

    ⚠️ D177 SAID THIS BRANCH "DECLARES WHAT IT CANNOT ANSWER" AND THE
    DECLARATION REACHED NOBODY.  `pc_proto` wrote `pc_frame_valid = 0` and
    `pc_place_valid` then blasted the very points carrying it, so with a
    surface wired the native PLACE branch cooked 0 prims with
    `node.warnings() == ()` and `node.errors() == ()` - an empty viewport and
    no explanation, which is the same silent-empty failure 16.4 point 3 had
    already fixed once for the unwired input.  `pc_proto` raises a node
    warning now, and this is what says so.
    """
    spline = hou.Geometry()
    cases.polyline(spline, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)], curve_id="S")
    surf = cases.surface(cases.ramp_x)
    rows = []
    for label, wire_surface, fillet in (("surface", True, 0.0),
                                        ("fillet", False, 1.0)):
        node = root.createNode("pf_polychain", "empty_%s" % label)
        node.setInput(0, native.feed(root, spline, "ES_%s" % label))
        if wire_surface:
            node.setInput(3, native.feed(root, surf, "ESF_%s" % label))
        if fillet > 0.0:
            node.parm("fillet_radius").set(fillet)
        node.parm("stage").set("place_native")
        try:
            node.cook(force=True)
            nprim = len(node.geometry().prims())
        except Exception:
            nprim = -1
        # ⚠️ THE WARNING LIVES ON THE INNER NODE, exactly as `run_hda_checks`
        # already records for `kernel`: `hou.Node.warnings()` does not
        # aggregate a child's warnings onto the asset (measured again here),
        # even though the viewport badge does.
        warned = [w for w in node.node("pc_proto").warnings()
                  if "4.5" in w or "Stage" in w]
        rows.append((label, nprim, len(warned)))
        node.destroy()
    ok = all(n == 0 and w >= 1 for _l, n, w in rows)
    check("native_place_says_why_it_is_empty", ok,
          "; ".join("%s %d prims / %d warnings" % r for r in rows),
          "a surface on input 4 and a fillet radius are both 4.5/4.3 work "
          "the native PLACE branch cannot answer (13.9 N5/N6). It ships no "
          "prims - which is correct - and it now says why on `pc_proto`, "
          "which is where the viewport badge comes from. The "
          "check FAILS both if the geometry comes back non-empty and if the "
          "warning is missing, so it cannot be satisfied by silence")


def place_mutation(root, built):
    """The three copytopoints parameters that are silently wrong by default.

    ⚠️ IT HAS TO BE A CASE WITH ROTATION IN IT.  `pivot` and `useimplicitn`
    both act on the ROTATION, so on a straight run along X they are no-ops
    and both mutations came back 0.0000 m and PASSING - proving nothing about
    two parameters whose defaults are wrong.  The closed rectangle turns four
    times.
    """
    case = built["B_rect_closed"]
    node, geo = asset_on(root, case, "place_native", "mut")
    if geo is None:
        check("place_mutation_baseline", False, "cook failed", "")
        return
    # ⚠️ AGAINST ITSELF, NOT AGAINST THE REFERENCE.  `B_rect_closed` turns
    # four times, which is what `pivot` and `useimplicitn` need - and a corner
    # case is OUT OF `place_packed_parity`'s scope until N8, so comparing it
    # to the reference here would be measuring the missing stage.  What these
    # three mutations have to show is that the parameter MOVES THE OUTPUT.
    sound = dict((p.attribValue("pc_elem_id"), p.intrinsicValue("bounds"))
                 for p in geo.prims())

    def spread(g):
        out = 0.0
        for p in g.prims():
            try:
                b = sound[p.attribValue("pc_elem_id")]
            except (hou.OperationFailed, KeyError):
                continue
            a = p.intrinsicValue("bounds")
            out = max(out, max(abs(x - y) for x, y in zip(a, b)))
        return out

    check("place_mutation_baseline", len(sound) > 8, len(sound),
          "the branch built something to mutate (each check below is that "
          "same build with ONE copytopoints parameter changed)")
    node.allowEditingOfContents()
    copy = node.node("copy_packed")

    def moved_by(parm, value):
        old = copy.parm(parm).eval()
        copy.parm(parm).set(value)
        try:
            node.cook(force=True)
            out = spread(node.geometry())
        except Exception:
            out = -1.0
        copy.parm(parm).set(old)
        node.cook(force=True)
        return out

    # ⚠️ THE NUMBERS HERE ARE MEASURED, AND ONE OF THEM CORRECTS AN EARLIER
    # CLAIM IN THIS FILE'S OWN HISTORY. `pivot = centroid` was first written
    # up as "1.25 m wrong"; that reading was the missing `pc_module` copying
    # the WHOLE KIT and taking the whole kit's centroid. In isolation the
    # pivot moves the world result by ~9.5e-07 m.
    pivot = moved_by("pivot", "centroid")
    check("mutation_copy_pivot", pivot > 1e-7, "%.3e m" % pivot,
          "pivot=centroid is the DEFAULT and this branch needs origin - "
          "_packed_transform maps the module's OWN local space. It is a "
          "sub-micron move, not a module length; the ceiling is 1e-7 m")
    # NOT a mutation, a MEASUREMENT: with an explicit `transform` attribute
    # present, `useimplicitn` is a no-op. Recorded as 0.0 rather than
    # asserted as a fix, so nobody removes the parm believing it does work
    # and nobody credits it with any.
    implicit = moved_by("useimplicitn", True)
    check("copy_useimplicitn_is_a_noop", implicit == 0.0, "%.3e m" % implicit,
          "with a per-point `transform` present the matrix wins outright, so "
          "toggling useimplicitn moves NOTHING. Set for determinism, not for "
          "correctness - and the 0.0 is the honest claim")
    ident = moved_by("useidattrib", False)
    check("mutation_copy_useidattrib", ident > 1e-6, "%.4f m" % ident,
          "useidattrib=0 - every target point receives the ENTIRE kit")


def finalize_mutation(root, built):
    """Bypass `pc_finalize` on the SHIPPED asset and watch the stamp go.

    Without this the stamp parity above is a check nobody has seen fail, and
    the thing it guards - 3.4's fourteen prim attributes - was wrong for two
    cycles with `place_packed_parity` reading 0.0 m the whole time.  The
    mutation is the state the branch shipped in: `copytopoints` alone, no
    finalize wrangle.
    """
    name = None
    for candidate in sorted(built):
        case = built[candidate]
        params = case["style"].params if case["style"] else DEFAULTS
        if _place_out_of_scope(case, params):
            continue
        if any(p.type() == hou.primType.PackedGeometry
               for p in case["out"].prims()):
            name = candidate
            break
    if name is None:
        check("mutation_pc_finalize", False, "no case", "no in-scope case")
        return
    case = built[name]
    node, geo = asset_on(root, case, "place_native", "finmut")
    node.allowEditingOfContents()
    fin = node.node("pc_finalize")
    sound = fin is not None
    missing = []
    if sound:
        fin.bypass(True)
        node.cook(force=True)
        got = dict((a.name(), a.dataType()) for a in node.geometry().primAttribs())
        ref = dict((a.name(), a.dataType()) for a in case["out"].primAttribs())
        missing = sorted(n for n in ref if n not in got and n not in STAMP_OWED)
        fin.bypass(False)
    node.destroy()
    check("mutation_pc_finalize", sound and len(missing) >= 4,
          "%d attributes lost" % len(missing),
          "bypassing `pc_finalize` on the built asset drops %s from the "
          "output of `%s` - the state this branch shipped in, with "
          "`place_packed_parity` reading 0.0 m throughout"
          % (", ".join(missing) or "nothing", name))


def kit_id_mutation(root, built):
    """`pc_kit_id` is what makes `useidattrib` work at all."""
    case = built["B_rect_closed"]
    node, geo = asset_on(root, case, "place_native", "kitmut")
    if geo is None:
        check("kit_id_mutation", False, "cook failed", "")
        return
    node.allowEditingOfContents()
    node.node("pc_kit_id").bypass(True)
    try:
        node.cook(force=True)
        bounds = [p.intrinsicValue("bounds") for p in node.geometry().prims()]
        width = max((b[1] - b[0]) for b in bounds) if bounds else 0.0
    except Exception:
        width = -1.0
    node.node("pc_kit_id").bypass(False)
    node.cook(force=True)
    sound = max((p.intrinsicValue("bounds")[1] - p.intrinsicValue("bounds")[0])
                for p in node.geometry().prims())
    check("mutation_pc_kit_id", abs(width - sound) > 1e-6,
          "%.4f m vs %.4f m" % (width, sound),
          "bypassing pc_kit_id leaves the kit with no prim `pc_module`. "
          "`pc_proto` then measures no module, declares every piece "
          "unanswerable and the branch ships NOTHING - which is what "
          "warn-never-block looks like when the id is missing, and it is a "
          "different answer from the sound build's widest piece")


def plan_benches(root, built):
    """What 4.2 and 4.4 COST, on the two shapes 11.9 rule 2 says decide it.

    ⚠️ D164 - A TIMING WITHOUT A COOK COUNT IS NOT A MEASUREMENT, and this
    check enforces it rather than commenting on it: the first version of this
    bench reported 0.0000 s for a 10 000-piece chain because
    `cook(force=True)` on an HDA instance is a no-op when nothing upstream
    changed.  The chain is dirtied through a spare int the CONFIG stub
    actually reads, and every timed node's `cookCount` must advance once per
    pass or the row fails.

    15.6 named the number to watch: "N2's per-section arrays will hit the same
    wall `pc_seg_*` hit - the fitting solve writes twelve arrays per section,
    and `pointgenerate`'s `docopyattribs` carries them through AGAIN."  A
    ten-thousand-piece single section is the shape that shows it; 300 short
    curves is the shape 11.9 rule 2 says an implementer's own fixture never
    does.
    """
    from polyfactory.polychain import Kit, Params, Rule, Style
    from polyfactory.polychain import kit as KIT

    kit_geo = KIT.starter_kit()
    kit = KIT.read(kit_geo)[0]
    style = Style("bench", 1, 1, rules=[Rule("default", "first", ["panel"])],
                  params=Params(fill="adaptive"))

    long_curve = hou.Geometry()
    cases.polyline(long_curve, cases.arc_points(20000.0, 1.0, 20000.0),
                   curve_id="LONG")
    streets = hou.Geometry()
    for i in range(300):
        x = (i % 20) * 30.0
        z = (i // 20) * 25.0
        cases.polyline(streets, [(x, 0.0, z), (x + 18.0, 0.0, z),
                                 (x + 18.0, 0.0, z + 14.0)],
                       curve_id="S%03d" % i)

    for label, geo in (("long_curve", long_curve), ("streets_300", streets)):
        sub = root.createNode("subnet", "planbench_" + label)
        src = native.feed(sub, geo, "IN")
        dirt = sub.createNode("attribwrangle", "bench_dirty")
        dirt.parm("class").set(0)
        group = dirt.parmTemplateGroup()
        group.append(hou.IntParmTemplate("nudge", "Nudge", 1))
        dirt.setParmTemplateGroup(group)
        dirt.parm("snippet").set('i@pc_bench = chi("nudge");')
        dirt.setInput(0, src)
        cfg = native.config_full(sub, style.params, style, kit, "config")
        last, dec = native.stage_decompose(sub, dirt, cfg)
        plan, pnodes = native.stage_plan(sub, last, cfg)
        place, qnodes = native.stage_place(
            sub, plan, cfg, native.feed(sub, kit_geo, "KIT"), last)
        timed = dict(pnodes)
        timed.update(qnodes)
        # The KIT side is not downstream of the spline, so nudging the spline
        # correctly does NOT re-cook it - asserting that it does would be
        # asserting a cache miss. It is excluded by name rather than by
        # loosening the rule, so D164 still bites on everything on the path.
        for off_path in ("kit_starter", "pc_kit_id", "kit_unpack"):
            timed.pop(off_path, None)
        place.cook(force=True)
        pieces = len(plan.geometry().points())
        prims = len(place.geometry().prims())
        before = dict((n, node.cookCount()) for n, node in timed.items())
        passes = 4
        best = None
        for i in range(passes):
            dirt.parm("nudge").set(i + 2)
            start = time.time()
            place.cook()
            elapsed = time.time() - start
            best = elapsed if best is None else min(best, elapsed)
        stale = sorted(n for n, node in timed.items()
                       if node.cookCount() - before[n] != passes)
        check("bench_plan_%s_really_cooked" % label, not stale, passes,
              "nodes whose cookCount did not advance once per timed pass: %s"
              % (", ".join(stale) or "none"))
        # ⚠️ AND THE COMPARAND, BECAUSE 15.2 HAD TO WITHDRAW A NUMBER FOR
        # NOT HAVING ONE. `place.build` on the SAME geometry with the SAME
        # style is what the native branch has to beat, and on the long curve
        # it does not: it is roughly 8x slower, and the row says so rather
        # than reporting a bare second count that reads like a win.
        ref_best = None
        for _ in range(3):
            out = hou.Geometry()
            start = time.time()
            res, _rep = P.build(geo, kit_geo, style, out=out)
            elapsed = time.time() - start
            ref_best = elapsed if ref_best is None else min(ref_best, elapsed)
        ref_prims = len(res.prims())
        check("bench_plan_%s" % label, best is not None and best < 30.0,
              "%.4f s vs %.4f s" % (best, ref_best),
              "4.1 + 4.2 + 4.4 as nodes (%d pieces, %d packed prims) against "
              "place.build on the same input (%d prims) - %.1fx. NO CEILING "
              "is asserted: this is a HALF-ported chain (no deform gate, no "
              "corners, no conform), so the ratio is a recorded before, not "
              "a verdict" % (pieces, prims, ref_prims, best / max(ref_best, 1e-9)))
        sub.destroy()


def frames_scale_in_segments(root, snippet=None, passes=3):
    """`pc_frames_native` must not pay O(segments) per piece.

    ⚠️ THIS IS THE CHECK THAT WOULD HAVE CAUGHT THE BIGGEST DEFECT OF THIS
    CYCLE, AND IT DID NOT EXIST.  `pc_sample` read four per-primitive ARRAY
    attributes, and a `prim()` read of an array COPIES THE WHOLE ARRAY - so
    every sample cost O(segments) and every piece pays two samples.  Measured
    on the shipped asset before the fix, 20 km / 20 001 vertices / 18 870
    pieces: `pc_frames_native` **4 833 ms**, against `copy_packed`'s 5.1 ms -
    while 16.5 wrote that "roughly two of those three seconds are
    `copytopoints` itself", off by a factor of ~950, which would have sent
    13.9 N5 at the wrong node.

    `bench_plan_long_curve` could not see it (it asserts no ceiling) and
    `streets_300` structurally cannot (a 3-point curve has 2 segments).

    ⚠️ AND IT IS DIRTIED, NOT FORCED.  D164 again: `cook(force=True)` on a
    node whose inputs have not changed can be a no-op, and the first version
    of this check reported 0.0 ms for 18 870 pieces because of it.  A nudge
    wrangle sits between `pc_proto` and `pc_frames_native`, so each pass
    re-cooks the frames node and nothing above it, and `cookCount` has to
    advance once per pass.

    `snippet` replaces `pc_frames.vfl`'s whole VEX - the mutation lever, so
    the ceiling can be shown to bite.  ⚠️ IT IS THE SNIPPET AND NOT THE
    HEADER: `vexsrc.source` INLINES `#include "pc_path.h"` (that is the whole
    point of it - the shipped asset must not need `HOUDINI_VEX_PATH`), so a
    mutation that patches the header text and then looks for the include line
    in the body finds nothing and measures the SOUND build.  It did, and the
    mutation reported "1.0 ms" and failed for the right reason.
    """
    from polyfactory.polychain import Params, Rule, Style
    from polyfactory.polychain import kit as KIT
    from polyfactory.polychain import vexsrc

    kit_geo = KIT.starter_kit()
    kit = KIT.read(kit_geo)[0]
    style = Style("fscale", 1, 1, rules=[Rule("default", "first", ["panel"])],
                  params=Params(fill="adaptive"))
    geo = hou.Geometry()
    cases.polyline(geo, [(1.0 * i, 0.0, 0.0) for i in range(20001)],
                   curve_id="LONG")

    sub = root.createNode("subnet", "framescale")
    src = native.feed(sub, geo, "IN")
    cfg = native.config_full(sub, style.params, style, kit, "config")
    last, _dec = native.stage_decompose(sub, src, cfg)
    plan, _pn = native.stage_plan(sub, last, cfg)
    place, qn = native.stage_place(sub, plan, cfg,
                                   native.feed(sub, kit_geo, "KIT"), last)
    frames = qn["pc_frames_native"]
    if snippet is not None:
        frames.parm("snippet").set(snippet)
    dirt = sub.createNode("attribwrangle", "frames_dirty")
    dirt.parm("class").set(2)
    group = dirt.parmTemplateGroup()
    group.append(hou.IntParmTemplate("nudge", "Nudge", 1))
    dirt.setParmTemplateGroup(group)
    dirt.parm("snippet").set('i@_bench = chi("nudge");')
    dirt.setInput(0, qn["pc_proto"])
    frames.setInput(0, dirt)
    place.cook(force=True)
    npieces = len(frames.geometry().points())
    before = frames.cookCount()
    best = None
    for i in range(passes):
        dirt.parm("nudge").set(i + 2)
        t0 = time.time()
        frames.cook()
        dt = time.time() - t0
        best = dt if best is None else min(best, dt)
    cooked = frames.cookCount() - before
    sub.destroy()
    return (best, npieces, cooked)


def frames_scale_check(root):
    best, npieces, cooked = frames_scale_in_segments(root)
    check("frames_cost_is_flat_in_segment_count",
          cooked == 3 and npieces > 8000 and best < 0.25,
          "%.1f ms / %d pieces" % (best * 1000.0, npieces),
          "`pc_frames_native` ALONE on 20 km / 20 000 segments / %d pieces, "
          "best of 3 dirtied passes (cookCount advanced %d). Ceiling 250 ms - "
          "twenty times the measured cost and twenty times under the defect. "
          "`mutation_pc_sample_array_reads` proves the ceiling bites"
          % (npieces, cooked))


def frames_scale_mutation(root):
    """Put an ARRAY-shaped read back and watch the 250 ms ceiling bite.

    Without this the ceiling is a number nobody has seen fail.  The mutation
    is the SHAPE of the code that shipped, not a slower constant: ONE of
    `pc_sample`'s reads binds the whole per-vertex column into a local array
    before indexing it.  The answer is identical; only the cost model changes,
    which is exactly the property the ceiling is about.  The shipped code had
    FOUR reads of that shape and measured 4 833 ms.
    """
    from polyfactory.polychain import vexsrc
    body = vexsrc.source("pc_frames")
    target = ('float pc_seg_hi_at(const int inp; const int pr; const int j) {\n'
              '    float v = vertex(inp, "_seg_hi", pr, j);\n'
              '    return v;\n'
              '}')
    replacement = (
        'float pc_seg_hi_at(const int inp; const int pr; const int j) {\n'
        '    int n = prim(inp, "_nseg", pr);\n'
        '    float col[];\n'
        '    resize(col, n);\n'
        '    for (int k = 0; k < n; k++) {\n'
        '        float e = vertex(inp, "_seg_hi", pr, k);\n'
        '        col[k] = e;\n'
        '    }\n'
        '    return col[j];\n'
        '}')
    found = target in body
    # ONE pass: the mutated node costs ~9 s and a `min` over three of them
    # buys nothing when the ceiling it has to clear is 0.25 s.
    best, npieces, cooked = frames_scale_in_segments(
        root, snippet=body.replace(target, replacement), passes=1)
    check("mutation_pc_sample_array_reads",
          found and best >= 0.25,
          "%.1f ms (target present: %s)" % (best * 1000.0, found),
          "binding ONE of `pc_sample`'s reads to the whole segment column - "
          "the shape the shipped code had four of - takes the node from ~1 ms "
          "to %.1f ms on the same %d pieces. The ceiling above is therefore a "
          "measurement and not a decoration" % (best * 1000.0, npieces))


# --- D193: the emit chain's batching ceiling ---------------------------------

# ⚠️ `pc_stamp` DE-BATCHED, and it is the mutation D193 exists for.  Cycle
# N-2V2 turned this POINT wrangle into a DETAIL wrangle looping over every
# piece on one thread - §17 finding 16, reverted - and the whole suite stayed
# at 77 / 0 while `bench_plan_streets_300` went 0.0395 -> 0.0800 s and PRINTED
# PASS, because both `bench_plan_*` rows say "NO CEILING is asserted".  The
# answer is identical; only the cost model changes, which is exactly the
# property a batching ceiling is about.
STAMP_BATCHED = '''string eid = sprintf("%s|%d|%s|%d|%s", s@pc_curve_id, i@pc_sec_index,
                     s@pc_slot, i@pc_index, style_id);
s@pc_elem_id  = eid;
i@pc_elem_key = pc_elem_key(eid);'''

STAMP_DEBATCHED = '''int n = npoints(0);
for (int i = 0; i < n; i++) {
    string cid = point(0, "pc_curve_id", i);
    int si = point(0, "pc_sec_index", i);
    string slot = point(0, "pc_slot", i);
    int idx = point(0, "pc_index", i);
    string eid = sprintf("%s|%d|%s|%d|%s", cid, si, slot, idx, style_id);
    setpointattrib(0, "pc_elem_id", i, eid);
    setpointattrib(0, "pc_elem_key", i, pc_elem_key(eid));
}'''


def emit_scale_in_pieces(root, npts, stamp_snippet=None, passes=3,
                        solve_snippet=None):
    """What `pc_plan_emit` and `pc_stamp` cost PER PIECE, each on its own.

    ⚠️ THE TWO NODES ARE TIMED SEPARATELY AND EACH IS DIRTIED FROM ITS OWN
    INPUT.  D164: `cook(force=True)` on a node whose inputs have not changed
    can be a no-op, and a timing without a cook count is not a measurement -
    so a nudge wrangle sits above each node and its `cookCount` has to advance
    once per pass or the row fails.

    `stamp_snippet` replaces `pc_stamp.vfl`'s VEX and `solve_snippet`
    `pc_plan_solve.vfl`'s - the mutation levers, so each ceiling can be shown
    to bite.  The stamp's class moves with its snippet, because a DETAIL
    wrangle is what de-batching MEANS.

    ⚠️ `pc_plan_solve` IS TIMED FIRST, and the order is not arbitrary: its own
    nudge dirties everything below it, so timing it after the other two would
    leave their cook counts short.  Each node still has its OWN nudge wrangle
    above it and its own `cookCount` assertion.

    Returns (npieces, emit_best, stamp_best, emit_cooks, stamp_cooks,
             solve_best, solve_cooks).
    """
    from polyfactory.polychain import Params, Rule, Style
    from polyfactory.polychain import kit as KIT

    kit_geo = KIT.starter_kit()
    kit = KIT.read(kit_geo)[0]
    style = Style("emitscale", 1, 1,
                  rules=[Rule("default", "first", ["panel"])],
                  params=Params(fill="adaptive"))
    geo = hou.Geometry()
    cases.polyline(geo, [(1.0 * i, 0.0, 0.0) for i in range(npts)],
                   curve_id="LONG")

    sub = root.createNode("subnet", "emitscale%d" % npts)
    src = native.feed(sub, geo, "IN")
    cfg = native.config_full(sub, style.params, style, kit, "config")
    last, _dec = native.stage_decompose(sub, src, cfg)
    plan, pn = native.stage_plan(sub, last, cfg)
    emit, stamp = pn["pc_plan_emit"], pn["pc_stamp"]
    solve = pn["pc_plan_solve"]
    if solve_snippet is not None:
        solve.parm("snippet").set(solve_snippet)
    if stamp_snippet is not None:
        # a DETAIL wrangle is what de-batching MEANS; the class moves with the
        # snippet or the mutation would just be a slower point wrangle
        stamp.parm("class").set(0)
        stamp.parm("snippet").set(stamp_snippet)

    def nudge(name, feeder, target):
        node = sub.createNode("attribwrangle", name)
        node.parm("class").set(2)
        group = node.parmTemplateGroup()
        group.append(hou.IntParmTemplate("nudge", "Nudge", 1))
        node.setParmTemplateGroup(group)
        node.parm("snippet").set('i@_%s = chi("nudge");' % name)
        node.setInput(0, feeder)
        target.setInput(0, node)
        return node

    dirt_solve = nudge("solvedirty", pn["pc_plan_clean"], solve)
    dirt_emit = nudge("emitdirty", solve, emit)
    dirt_stamp = nudge("stampdirty", pn["pc_plan_only"], stamp)
    plan.cook(force=True)
    npieces = len(plan.geometry().points())

    def timed(node, dirt, offset):
        before = node.cookCount()
        best = None
        for i in range(passes):
            dirt.parm("nudge").set(offset + i)
            t0 = time.time()
            node.cook()
            dt = time.time() - t0
            best = dt if best is None else min(best, dt)
        return best, node.cookCount() - before

    solve_best, solve_cooks = timed(solve, dirt_solve, 200)
    emit_best, emit_cooks = timed(emit, dirt_emit, 2)
    stamp_best, stamp_cooks = timed(stamp, dirt_stamp, 40)
    sub.destroy()
    return (npieces, emit_best, stamp_best, emit_cooks, stamp_cooks,
            solve_best, solve_cooks)


# The ceilings, in microseconds per piece, and where each number comes from.
# Measured on this build at 1 000 / 2 500 / 5 000 / 10 000 / 20 000 pieces:
#   pc_plan_emit   3.25 2.80 2.78 2.75 2.91   - flat, and DETAIL by necessity
#   pc_stamp       1.34 1.32 1.28 0.33 0.30   - flat, and POINT by choice
# The two defects each ceiling is aimed at, measured on the same fixture:
#   the `pointgenerate` expander D175 replaced: 3 860 us/piece at 10 000
#   `pc_stamp` de-batched into a detail loop:       9.4 us/piece at 20 000
EMIT_CEILING_US = 6.0
STAMP_CEILING_US = 3.0
# ⚠️ AND THE NODE THAT CARRIES THE WHOLE OF THE PORT'S COST REGRESSION, WHICH
# D193'S MANDATE NAMED AND DID NOT REACH (D204).  `pc_plan_solve` is 78 % of
# the native chain at 20 km straight, and the only thing watching it was
# `bench_plan_long_curve`, which asserts `best < 30.0` and prints "NO CEILING
# is asserted" - a thirty-second wall around a 0.6-second node, so a change
# that DOUBLED it would still print PASS.  The two ceilings D193 did land
# cover `pc_plan_emit` and `pc_stamp` at 2.8 and 0.34 us/piece: the two
# cheapest nodes in the chain.
# MEASURED LADDER on this build, `pc_plan_solve` alone, best of 2 dirtied
# passes with `cookCount` asserted, after the identity-permutation skip:
#     1 250   2 500   5 000  10 000  20 000  40 000  80 000  pieces
#     20.99   20.73   21.93   23.74   32.23   53.26   53.79  us/piece
# It is NOT quadratic - 40 000 -> 80 000 is flat - but it is not flat either:
# the step between 10 000 and 40 000 is where the per-section arrays stop
# fitting in cache.  So the solve gets its OWN growth ceiling rather than
# sharing `GROWTH_CEILING`; 1.5x would sit exactly on a measurement that reads
# 1.49-1.50x over three runs, which is a flaky check, not a strict one.  2.0x
# still blows up three orders of magnitude on a quadratic node.
# The absolute ceiling sits between the two measurements it separates, both
# taken as the MIN over three interleaved repetitions (`solve_scale_rates`
# says why): the sound node reads 26-28 us/piece and the spill mutant 41-49.
SOLVE_CEILING_US = 34.0
SOLVE_GROWTH_CEILING = 2.0

# The dedup table's own branch, and the SPILL branch beside it - which writes
# the five per-piece STRING ARRAYS the table replaced.  A VEX string array
# attribute costs ~9 us per ELEMENT to write and five of them at 20 000 pieces
# is 100 000 elements: that was the port's 20x defect, and forcing the spill
# path restores the cost model WITHOUT changing a single planned value, which
# is exactly the property a cost ceiling is for.
SOLVE_TABLED = "if (spill) {"
SOLVE_SPILLED = "if (1) {"
# a linear node's per-piece cost does not GROW with the piece count.  1.5x is
# slack for thread start-up and cache, and the quadratic expander blows it by
# three orders of magnitude between these two sizes.
GROWTH_CEILING = 1.5

def emit_scale_check(root):
    """D193 - the emit chain gets a per-piece ceiling, the way N4 gave one to
    the frames.

    ⚠️ THIS IS THE CHECK THAT WOULD HAVE FAILED MUTATION M2 AND DID NOT EXIST.
    `bench_plan_long_curve` and `bench_plan_streets_300` both MEASURED the
    de-batched stamp (+24 % and +103 %) and both printed PASS, because both
    say in as many words that no ceiling is asserted.  That is defensible for
    a RATIO against a half-ported chain and it is not a guard, so the guard is
    here: an absolute cost per piece, on the two nodes that had none.
    """
    small = emit_scale_in_pieces(root, 5001)
    big = emit_scale_in_pieces(root, 40001)
    # ⚠️ `pc_plan_solve` IS NOT IN THIS LOOP - `solve_scale_check` measures it,
    # for a reason that is a property of the node and not a preference.  The
    # emit and the stamp are 2.6 and 0.4 us/piece and read within a few per
    # cent of each other run to run; the solve is ~27 and reads 26-42 across
    # runs on the same build, because it is the one node here that is heavy
    # enough for another process on the machine to move.  A single best-of-3
    # pass is not a strong enough estimator to hang a tight ceiling on, and a
    # LOOSE ceiling is exactly the "NO CEILING is asserted" problem in a new
    # costume - measured: with the ceiling at 40 the string-array mutation
    # passed at 37.44 in a loaded run and failed at 49.45 in a quiet one.
    for label, node, index, cooki, ceiling, growth in (
            ("emit", "pc_plan_emit", 1, 3, EMIT_CEILING_US, GROWTH_CEILING),
            ("stamp", "pc_stamp", 2, 4, STAMP_CEILING_US, GROWTH_CEILING)):
        rate_small = small[index] * 1e6 / small[0]
        rate_big = big[index] * 1e6 / big[0]
        cooks = small[cooki] == 3 and big[cooki] == 3
        check("%s_cost_is_flat_in_piece_count" % label,
              cooks and rate_big <= ceiling
              and rate_big <= growth * rate_small,
              "%.2f us/piece" % rate_big,
              "`%s` ALONE on %d pieces, best of 3 dirtied passes; %.2f "
              "us/piece at %d pieces, so the growth is %.2fx (ceiling %.1fx). "
              "Absolute ceiling %.1f us/piece. Every one of the three has "
              "a mutation that proves it bites"
              % (node, big[0], rate_small, small[0], rate_big / rate_small,
                 growth, ceiling))


def emit_scale_mutation(root):
    """De-batch `pc_stamp` back into a single-threaded detail loop - cycle
    N-2V2's mutation M2, which survived a 77 / 0 suite - and watch the ceiling
    bite.  The mutated VEX writes the SAME `pc_elem_id` and `pc_elem_key`;
    only the cost model changes.
    """
    from polyfactory.polychain import vexsrc
    body = vexsrc.source("pc_stamp")
    found = STAMP_BATCHED in body
    row = emit_scale_in_pieces(
        root, 40001, stamp_snippet=body.replace(STAMP_BATCHED,
                                                STAMP_DEBATCHED), passes=1)
    npieces, stamp_best, cooks = row[0], row[2], row[4]
    rate = stamp_best * 1e6 / npieces
    check("mutation_pc_stamp_debatched",
          found and cooks == 1 and rate > STAMP_CEILING_US,
          "%.2f us/piece (target present: %s)" % (rate, found),
          "`pc_stamp` as a DETAIL wrangle looping over all %d pieces on one "
          "thread - M2, which was 77 / 0 green - costs %.2f us/piece against "
          "the batched %.1f-or-less. The ceiling above is a measurement, not "
          "a decoration" % (npieces, rate, STAMP_CEILING_US))


def solve_scale_rates(root, reps=3):
    """`pc_plan_solve` alone, at two sizes and in its two transports, as the
    MIN over `reps` INTERLEAVED repetitions of each variant.

    ⚠️ THE ESTIMATOR IS THE POINT.  A single best-of-3 pass on this node reads
    26-42 us/piece for the SAME build - measured, three interleaved
    repetitions gave sound 27.40 / 42.15 / 27.10 while the mutant gave 48.79 /
    44.19 / 41.28, so a run that catches the 42 and the 41 reports a ratio of
    1.05 and a run that catches the 27 and the 49 reports 1.78.  Any threshold
    between them is a coin toss on a shared machine.  The MIN over
    repetitions is the estimator that is not: interference can only make a
    pass slower, so the minimum is the closest thing to the node's own cost,
    and interleaving means both variants see the same machine.

    Returns ({"small", "big", "spill"} -> us/piece, every cook counted).
    """
    from polyfactory.polychain import vexsrc
    body = vexsrc.source("pc_plan_solve")
    mutant = body.replace(SOLVE_TABLED, SOLVE_SPILLED)
    best = {"small": None, "big": None, "spill": None}
    cooks = []
    for _rep in range(reps):
        for tag, npts, snippet in (("small", 5001, None),
                                   ("big", 40001, None),
                                   ("spill", 40001, mutant)):
            row = emit_scale_in_pieces(root, npts, passes=2,
                                       solve_snippet=snippet)
            cooks.append(row[6])
            rate = row[5] * 1e6 / row[0]
            best[tag] = rate if best[tag] is None else min(best[tag], rate)
    return best, all(c == 2 for c in cooks), body.count(SOLVE_TABLED) == 1


def solve_scale_check(root):
    """D204 - `pc_plan_solve` gets the per-piece ceiling D193's mandate named
    and did not reach, and the mutation that proves it bites.

    ⚠️ THE MUTATION DOES NOT CHANGE A SINGLE PLANNED VALUE.  Forcing the solve
    down its SPILL branch writes the five per-piece string ARRAYS the dedup
    table replaced - a live, supported transport (`plan_row_table_spills`
    exercises it) that ships the same plan - so every parity check in the
    suite stays green under it.  That is precisely why the 20x regression
    could ship unseen, and precisely what a cost ceiling is for.
    """
    rates, cooked, found = solve_scale_rates(root)
    growth = rates["big"] / max(rates["small"], 1e-9)
    ratio = rates["spill"] / max(rates["big"], 1e-9)
    check("solve_cost_is_flat_in_piece_count",
          cooked and rates["big"] <= SOLVE_CEILING_US
          and growth <= SOLVE_GROWTH_CEILING,
          "%.2f us/piece" % rates["big"],
          "`pc_plan_solve` ALONE on 20 000 pieces, min over 3 interleaved "
          "repetitions of best-of-2 dirtied passes; %.2f us/piece at 2 500, "
          "so the growth is %.2fx (ceiling %.1fx). Absolute ceiling %.1f "
          "us/piece"
          % (rates["small"], growth, SOLVE_GROWTH_CEILING, SOLVE_CEILING_US))
    check("mutation_pc_plan_solve_string_arrays",
          found and cooked and rates["spill"] > SOLVE_CEILING_US
          and ratio >= 1.25,
          "%.2f us/piece / %.2fx (target present: %s)"
          % (rates["spill"], ratio, found),
          "the solve writing the five per-piece string ARRAYS the dedup table "
          "replaced - the shape that measured twenty times the Python it "
          "ported - costs %.2f us/piece against the tabled %.2f, on an output "
          "that is value-for-value identical. It has to clear the %.1f "
          "ceiling AND be at least 1.25x the sound node measured in the same "
          "interleaved run"
          % (rates["spill"], rates["big"], SOLVE_CEILING_US))


def sections_mutation(root, built):
    """`pc_sections` has no parity check of its own, so it gets a MUTATION.

    4.1's section list is not compared directly anywhere: `plan_solve_parity`
    asks the reference for `plan_sections(decompose_all(...))` and the native
    side runs `pc_sections` -> solve, so a wrong section list moves the plan
    and the check sees it.  That is coverage BY CONSTRUCTION, which is the
    weakest kind of claim - it is true only if the section list can actually
    move the plan.  These two mutations prove it can.
    """
    from polyfactory.polychain import kit as KIT
    from polyfactory.polychain import vexsrc

    for case_name, target, replacement, label in (
            ("T_lshape_bend",
             "if (corner && (closed || (i > 0 && i < n - 1))) isbreak[i] = 1;",
             "if (0) isbreak[i] = 1;",
             "a CORNER stops breaking the curve"),
            ("A_straight",
             "if (!closed) {\n            // D18 - a spline END is a cap and never a corner.\n            if (i0 == 0)     { start_cap = 1; angle = 0.0; }\n            if (i1 == n - 1) { end_cap = 1; }\n        }",
             "if (0) {\n            if (i0 == 0)     { start_cap = 1; angle = 0.0; }\n            if (i1 == n - 1) { end_cap = 1; }\n        }",
             "D18's spline-end cap stops being a cap")):
        case = built[case_name]
        style = case["style"]
        params = style.params if style is not None else DEFAULTS
        kit = KIT.read(case["kit"])[0]
        ref = plan_reference(case, params, style, kit)
        body = vexsrc.source("pc_sections")
        present = target in body
        sub = root.createNode("subnet", "secmut_%s" % case_name)
        read, _cfg, nodes = plan_chain(sub, case, params, style, kit,
                                       "sm_%s" % case_name)
        nodes["pc_sections"].parm("snippet").set(
            body.replace(target, replacement))
        try:
            read.cook(force=True)
            got = None if any(n.errors() for n in nodes.values()) \
                else plan_rows(read.geometry())
        except Exception:
            got = None
        sub.destroy()
        moved = got is None or plan_diff(got, ref)
        check("mutation_pc_sections_%s" % case_name.split("_")[0].lower(),
              present and moved, "%s / %s" % ("target present" if present
                                              else "TARGET GONE",
                                              "red" if moved else "GREEN"),
              "%s, and the plan parity has to see it - `pc_sections` has no "
              "parity check of its own, so this is what makes its coverage "
              "real rather than structural" % label)


# --- D192: a native Stage must be PROVED native, not labelled native ---------

# (stage token, the null it must be served by, the nodes on the SPLINE side
#  that must cook, the Python SOPs allowed to cook).
#
# ⚠️ THE KIT-SIDE NODES ARE NOT ON THE "MUST COOK" LIST AND THAT IS NOT
# LENIENCY.  The dirtying lever is the SPLINE (see `stage_is_really_native`),
# and `kit_starter` / `pc_kit_id` / `kit_unpack` hang off input 1, so
# asserting they re-cook would be asserting a cache miss - `plan_benches`
# excludes them for the same reason and by the same name.
NATIVE_STAGES = (
    ("sections", "OUT_sections",
     ("pc_unshare", "pc_curveid", "pc_curve_index", "pc_arclength",
      "pc_corners", "pc_markers"),
     ("config",)),
    ("plan_native", "OUT_plan_native",
     ("pc_sections", "pc_sec_only", "pc_plan_clean", "pc_plan_solve",
      "pc_plan_emit", "pc_plan_only", "pc_stamp"),
     ("config",)),
    ("frames_native", "OUT_frames_native",
     ("pc_proto", "pc_deform_gate", "pc_frames_native"),
     ("config", "kit_starter")),
    ("place_native", "OUT_place_native",
     ("pc_proto", "pc_deform_gate", "pc_frames_native", "pc_place_valid",
      "pc_packed_only", "copy_packed", "pc_finalize", "pc_out_cast",
      "pc_warn_collate"),
     ("config", "kit_starter")),
)

# ⚠️ AND THE STAGE THE WHOLE CYCLE IS ABOUT, WHICH HAD NO ROW (D203).
# `NATIVE_STAGES` watched three stages and named no node this cycle added -
# not `pc_deform_gate`, `pc_packed_only`, `pc_finalize`, `pc_out_cast`,
# `pc_warn_collate` or either guard switch - and there was no row for `output`
# at all.  It gets its own tuple because it needs its own FIXTURE: the L-shape
# below has a corner, 4.3 is N8, so level 1 refuses it outright and the whole
# native branch is correctly idle on it.  A straight flat run is what the
# guard admits.
OUTPUT_STAGE = (
    ("output", "OUT_final",
     ("pc_deform_gate", "pc_packed_only", "pc_finalize", "pc_out_cast",
      "pc_warn_collate", "guard_envelope", "guard_native"),
     ("config",)),
)

# --- D208: THE SIX STAGES WITH NO INDEPENDENT EXPECTATION AT ALL ------------
#
# §21.5.  D203 made `native.STAGES` the ONE declaration the build script and
# the checks both read, which is the right shape for consistency and has a
# cost nobody wrote down: a mutation of the DECLARATION moves the asset and
# its oracle together, so `every_stage_entry_serves_the_node_it_names` can
# only ever see the asset DRIFTING from the declaration, never the
# declaration being wrong.  Reproduced at source this cycle - the `reference`
# row re-pointed at `OUT_final` / `guard_envelope`, .hda rebuilt (md5
# 37f1e344 -> 92b0d456) - and that check printed **PASS**.
#
# `NATIVE_STAGES` and `OUTPUT_STAGE` above are the second voice for five
# stages, and they work because they are BEHAVIOURAL: they name nodes that
# must cook and Python that must not, so they are an expectation about the
# GRAPH rather than a copy of the table.  The other five - `reference`,
# `config`, `plan`, `frames`, `gate` - had nothing.
#
# These are those five, in the same behavioural shape, plus a fifth column:
# the nodes that must NOT cook.  A stage on the Python side cannot be asserted
# by "no Python cooked", so it is asserted by what the OTHER branch would do
# if the entry were re-pointed at it - `copy_packed` is the native branch's
# materialiser and `kernel` is the reference, and on a straight admitted run
# exactly one of them cooks.
#
# ⚠️ THE FIXTURE IS THE STRAIGHT RUN, and it has to be: on the L-shape the
# guard REFUSES, so `Stage = output` runs the reference and `copy_packed`
# never cooks whatever the entry is wired to - the forbidden column would be
# vacuous on exactly the mutation it exists to catch.
#
# ⚠️ `config` HAS NO must-cook LIST, and that is a property of the node, not
# leniency: `config` is wired to IN_KIT / IN_STYLE / IN_SURFACE and not to the
# spline, so the dirtying lever cannot reach it.  Its row is the forbidden
# column alone, which is still enough - re-pointing the `config` entry at
# either neighbour makes something on this list cook.
BRIDGE_STAGES = (
    ("reference", "OUT_reference", ("kernel",), ("config", "kernel"),
     ("copy_packed", "pc_finalize", "pc_out_cast")),
    ("config", "config", (), ("config",),
     ("kernel", "copy_packed", "pc_plan_solve")),
    ("plan", "OUT_plan", ("pc_plan_bridge",),
     ("config", "pc_plan_bridge", "kit_starter"),
     ("kernel", "copy_packed")),
    ("frames", "OUT_frames", ("pc_plan_bridge", "pc_frames",
                              "pc_frames_valid"),
     ("config", "pc_plan_bridge", "kit_starter"),
     ("kernel", "copy_packed")),
    ("gate", "OUT_gate", ("pc_deform_gate",), ("config", "kit_starter"),
     ("kernel", "copy_packed")),
)

# The L-shape every native STAGE is dirtied on, and the straight flat run the
# guard ADMITS - which is the only shape `output` can be asserted native on.
D192_CORNER = [(0.0, 0.0, 0.0), (9.0, 0.0, 0.0), (9.0, 0.0, 7.0)]
D192_STRAIGHT = [(0.0, 0.0, 0.0), (9.0, 0.0, 0.0), (18.0, 0.0, 0.0)]


def stage_is_really_native(root, tag, rewire=None, rows=NATIVE_STAGES,
                           pts=None):
    """Cook the SHIPPED asset at each NATIVE Stage and ask the graph, not the
    label, whether that stage is native.

    ⚠️ THIS IS THE CHECK CYCLE N-2V2's MUTATION M4b SURVIVED FOR WANT OF.
    Pointing the `plan_native` entry of `STAGES` at `OUT_plan` makes the menu
    entry labelled "2 - Plan, NATIVE (4.2 - the VEX fitting solve)" serve
    `pc_plan_bridge`'s PYTHON plan, and the suite stayed at 77 / 0: every
    parity check runs on `native.py`'s RIG, `asset_stages_match_the_rig`
    compares node PARAMETERS and not WIRING, and
    `native_plan_and_place_reach_no_artist` asserts the opposite direction.
    Nothing asserted that a native stage IS native.

    Two assertions, and both are needed - the first alone would pass a stage
    whose wrangles cook into a null nobody reads, and the second alone would
    pass a stage that cooks nothing at all:

      1. every node the stage is made of advanced its `cookCount`;
      2. no Python SOP outside the named allowance advanced its `cookCount`.

    `rewire` is (stage token, null name) - the mutation lever. It moves the
    switch input that serves that stage onto another null, which is M4b
    exactly, applied to the built asset rather than to the build script.

    Returns a list of complaint strings; empty is the sound build.
    """
    node = root.createNode("pf_polychain", "d192_" + tag)
    geo = hou.Geometry()
    cases.polyline(geo, pts or D192_CORNER, curve_id="D192")
    src = native.feed(root, geo, "D192IN_" + tag)
    # ⚠️ THE DIRTYING LEVER IS THE SPLINE, NOT A PARM.  D164: a cook that is a
    # no-op measures nothing, and `corner_angle_deg` only dirties `config`, so
    # `pc_curveid` and `pc_arclength` - which do not read it - would never
    # re-cook and the check would read them as idle on a sound build.
    dirt = root.createNode("attribwrangle", "d192_dirty_" + tag)
    dirt.parm("class").set(2)
    group = dirt.parmTemplateGroup()
    group.append(hou.IntParmTemplate("nudge", "Nudge", 1))
    dirt.setParmTemplateGroup(group)
    dirt.parm("snippet").set('i@_d192 = chi("nudge");')
    dirt.setInput(0, src)
    node.setInput(0, dirt)
    node.allowEditingOfContents()

    bad = []
    if rewire is not None:
        token, target = rewire
        served = dict((r[0], r[1]) for r in rows)[token]
        switch = node.node("stage_switch")
        moved = [i for i, inp in enumerate(switch.inputs())
                 if inp is not None and inp.name() == served]
        # ⚠️ THIS USED TO BE `assert len(moved) == 1` AND IT IS D208's OTHER
        # HALF.  Under §21.4's M10 - the `reference` row of `native.STAGES`
        # re-pointed at `OUT_final` at SOURCE - no switch input serves
        # `OUT_reference` any more, the assert fired, and the run ABORTED with
        # a traceback: 94 [PASS], **0 [FAIL]**, and `every_stage_entry_serves
        # _the_node_it_names` printing PASS on the way past.  The exit code
        # was 1, so a caller that checks it was safe; every summary in this
        # build log counts [FAIL] lines, and would have read that as green.
        # A missing switch input is a COMPLAINT now, not an exception.
        if len(moved) != 1:
            bad.append("%s: %d switch inputs serve %s (want exactly 1) - the "
                       "declaration and the asset disagree about which null "
                       "this stage is" % (token, len(moved), served))
        else:
            switch.setInput(moved[0], node.node(target))

    pysops = [c for c in node.children() if c.type().name() == "python"]
    nudge = 2
    for row in rows:
        token, served, must_cook, allowed = row[:4]
        # D208 - the fifth column, and it is what makes a row about a stage
        # that is NOT native still say something. See `BRIDGE_STAGES`.
        forbidden = row[4] if len(row) > 4 else ()
        node.parm("stage").set(token)
        dirt.parm("nudge").set(nudge)
        node.cook(force=True)
        before = dict((c.name(), c.cookCount()) for c in node.children())
        nudge += 1
        dirt.parm("nudge").set(nudge)
        node.cook(force=True)
        idle = [n for n in must_cook
                if node.node(n) is None
                or node.node(n).cookCount() == before[n]]
        strangers = sorted(p.name() for p in pysops
                           if p.name() not in allowed
                           and p.cookCount() > before[p.name()])
        busy = [n for n in forbidden
                if node.node(n) is not None
                and node.node(n).cookCount() > before[n]]
        # ⚠️ AND A NAME THAT RESOLVES TO NO NODE IS A COMPLAINT, NOT A SKIP.
        # `busy` used to read `node.node(n) is not None and ...`, so a
        # RENAMED node silently turned the forbidden column off - and that
        # column is the whole of D208's fix, the only behavioural assertion
        # the `config` row has (its `must_cook` list is empty by design).
        # Demonstrated: replace the forbidden entries of `config`, `plan` and
        # `frames` with `kernelXX` / `copy_packedXX` / `pc_plan_solveXX` -
        # simulating a rename of `copy_packed` - and the suite prints
        # `every_stage_has_a_second_source` PASS 10/10, `native_stages_are_
        # really_native` PASS, all five `mutation_*_unplugged` PASS, 0
        # failing. With the column blinded, re-pointing the `config` Stage
        # entry at `OUT_final` yields NO complaint where the sound table
        # yields `config: copy_packed,pc_plan_solve cooked and must not`.
        # `must_cook` has complained about a missing name since D208; the two
        # halves of the same row disagreed about it for a cycle.
        gone = [n for n in tuple(forbidden) + tuple(allowed)
                if node.node(n) is None]
        if idle:
            bad.append("%s: idle %s" % (token, ",".join(idle)))
        if strangers:
            bad.append("%s: python %s cooked" % (token, ",".join(strangers)))
        if busy:
            bad.append("%s: %s cooked and must not" % (token, ",".join(busy)))
        if gone:
            bad.append("%s: %s is not a node in the asset - a declaration "
                       "naming a node that does not exist asserts nothing"
                       % (token, ",".join(sorted(gone))))
        nudge += 1
    node.destroy()
    dirt.destroy()
    return bad


def native_stage_check(root):
    bad = stage_is_really_native(root, "sound")
    bad += stage_is_really_native(root, "sound_out", rows=OUTPUT_STAGE,
                                  pts=D192_STRAIGHT)
    rows = NATIVE_STAGES + OUTPUT_STAGE
    watched = sum(len(r[2]) for r in rows)
    check("native_stages_are_really_native", not bad,
          "%d nodes / %d stages" % (watched, len(rows)),
          "D192, on the SHIPPED asset: every node each native Stage is made "
          "of advanced its cookCount, and no Python SOP outside its named "
          "allowance did - `output` among them, on a straight flat run the "
          "guard admits. Complaints: %s" % (", ".join(bad) or "none"))

    # D208 - and the FIVE stages that had no independent expectation at all,
    # in the same behavioural shape. See `BRIDGE_STAGES`.
    bad = stage_is_really_native(root, "bridge", rows=BRIDGE_STAGES,
                                 pts=D192_STRAIGHT)
    covered = set(r[0] for r in NATIVE_STAGES + OUTPUT_STAGE + BRIDGE_STAGES)
    declared = set(t for t, _n, _f, _l in native.STAGES)
    check("every_stage_has_a_second_source",
          not bad and covered == declared,
          "%d/%d stages" % (len(covered & declared), len(declared)),
          "D208: every one of the %d `Stage` entries has an expectation that "
          "does NOT read `native.STAGES` - the nodes that must cook, the "
          "Python allowed to, and the nodes that must not - so a mutation of "
          "the declaration itself moves the asset WITHOUT moving its oracle. "
          "Uncovered: %s. Complaints: %s"
          % (len(declared), sorted(declared - covered) or "none",
             ", ".join(bad) or "none"))


def native_stage_mutation(root):
    """M4b, applied to the built asset: point the `plan_native` menu entry at
    the PYTHON bridge and watch the check above go red.

    The mutation is invisible to everything else in the suite - the rig still
    cooks the VEX solve, the parameters still match, and the stage still
    produces a plan - which is precisely why it survived 77 / 0.
    """
    for tag, token, target, python_sop, rows, pts in (
            ("m4b", "plan_native", "OUT_plan", "pc_plan_bridge",
             NATIVE_STAGES, None),
            ("m4", "place_native", "OUT_reference", "kernel",
             NATIVE_STAGES, None),
            # D203 / w3 - THE EXACT UNDO OF THIS CYCLE: the `output` entry
            # pointed back at the Python reference.  Before `output` had a
            # `NATIVE_STAGES` row, only two of 94 checks could see it.
            ("w3", "output", "OUT_reference", "kernel",
             OUTPUT_STAGE, D192_STRAIGHT),
            # D208 / §21.4's M10 - THE MUTATION §20.1 OPENS WITH, and the one
            # that was stopped by an assertion CRASH rather than by the check
            # credited with it. The `reference` entry - `output_guard_parity`'s
            # whole oracle - pointed at the guarded native OUTPUT, so the
            # cycle's headline parity proof compares the output WITH ITSELF
            # over all 92 cases.
            ("m10", "reference", "OUT_final", "kernel",
             BRIDGE_STAGES, D192_STRAIGHT),
            # ...and the same shape on the one native stage that had no
            # independent voice either: an artist opening the Deform gate to
            # ask why a piece unpacked, shown the Python reference's fence.
            ("m10b", "gate", "OUT_reference", "kernel",
             BRIDGE_STAGES, D192_STRAIGHT)):
        bad = stage_is_really_native(root, tag, rewire=(token, target),
                                     rows=rows, pts=pts)
        mine = [b for b in bad if b.startswith(token + ":")]
        check("mutation_%s_unplugged" % token,
              len(mine) >= 2 and any(python_sop in b for b in mine),
              "%d complaints" % len(bad),
              "rewiring the `%s` switch input to %s must report BOTH "
              "halves - the stage own nodes idle AND %s cooking. Got: %s"
              % (token, target, python_sop, "; ".join(mine) or "none"))


def _snapshot(geo):
    """Everything about a polyChain output that a consumer can see.

    Not a digest: a digest tells you two builds differ and nothing else, and
    the whole point of this comparison is that a divergence has to be
    NAMEABLE - which attribute, which element, which number.
    """
    names = sorted(a.name() for a in geo.primAttribs())
    types = dict((a.name(), str(a.dataType())) for a in geo.primAttribs())
    prims = []
    for prim in geo.prims():
        row = [prim.type().name(),
               tuple(round(float(c), 9) for c in prim.points()[0].position())
               if prim.points() else ()]
        try:
            row.append(tuple(round(float(c), 9)
                             for c in prim.intrinsicValue("bounds")))
        except hou.OperationFailed:
            row.append(())
        row.extend(prim.attribValue(n) for n in names)
        prims.append(tuple(row))
    return dict(
        prim_attribs=names,
        prim_types=types,
        point_attribs=sorted(a.name() for a in geo.pointAttribs()),
        detail=sorted((a.name(), geo.attribValue(a.name()))
                      for a in geo.globalAttribs()),
        groups=sorted(g.name() for g in geo.primGroups()),
        npoints=len(geo.points()),
        P=[round(float(c), 9) for c in geo.pointFloatAttribValues("P")],
        prims=prims)


def _first_difference(a, b):
    for key in ("prim_attribs", "prim_types", "point_attribs", "detail",
                "groups", "npoints"):
        if a[key] != b[key]:
            return "%s: %r != %r" % (key, a[key], b[key])
    if len(a["prims"]) != len(b["prims"]):
        return "prim count %d != %d" % (len(a["prims"]), len(b["prims"]))
    for i, (x, y) in enumerate(zip(a["prims"], b["prims"])):
        if x != y:
            for j, (u, v) in enumerate(zip(x, y)):
                if u != v:
                    field = ("type", "P", "bounds")[j] if j < 3 \
                        else a["prim_attribs"][j - 3]
                    return "prim %d %s: %r != %r" % (i, field, u, v)
    if a["P"] != b["P"]:
        for i, (u, v) in enumerate(zip(a["P"], b["P"])):
            if u != v:
                return "P[%d]: %r != %r" % (i, u, v)
    return ""


def output_guard_parity(root, built):
    """13.9 N10 - `Stage = output` takes the NATIVE chain, and it had better
    build the same fence.

    ⚠️ THIS IS THE CHECK THE WHOLE CYCLE RESTS ON.  Until this commit
    `Stage = output` was the Python reference and nothing else, so 88-95 % of
    what an artist cooked was Python however much of the tool had been ported
    (18.2).  It is a guarded fork now, and a guard that is wrong in either
    direction is worse than no guard at all: too generous and the artist gets
    a different fence than yesterday, too mean and the rebuild still does not
    ship.

    So EVERY case is cooked twice, at `Stage = output` and at the new
    `Stage = reference`, and the two are compared on EVERYTHING a consumer can
    see - the prim attribute NAMES, their TYPES, every value on every prim in
    ORDER, every packed prim's world bounds, every point position, the detail
    warning arrays and the prim groups.  Where the guard chose the reference
    the two are the same node and agree trivially; the row that matters is the
    count of cases where it chose the NATIVE chain, and it is printed.
    """
    took_native, took_ref, bad, fallback = [], [], [], []
    for name in sorted(built):
        case = built[name]
        node, geo = asset_on(root, case, "output", name + "_gp")
        if geo is None:
            bad.append((name, "cook: output"))
            continue
        node.allowEditingOfContents()
        got = _snapshot(geo)
        # ⚠️ THE TALLY IS EVIDENCE, NOT THE ENVELOPE'S OWN CLAIM (D203).  It
        # used to be read off `pc_envelope2`'s `_native_ok2` detail int, which
        # cooks whether or not anything downstream is wired to it - so with
        # the `output` entry re-pointed at `OUT_reference` (the exact undo of
        # this cycle) this row still printed "9 native / 83 reference ...
        # identical" and PASSED.  `copy_packed` is the node that assembles the
        # native fence and it is INSIDE level 2's branch, so a switch that did
        # not select that branch leaves it at cookCount 0.  The envelope is
        # kept as a CROSS-CHECK and a disagreement fails the row.
        native_cooked = node.node("copy_packed").cookCount() > 0
        env = node.node("pc_envelope").geometry()
        level1 = int(env.attribValue("_native_ok")) if \
            env.findGlobalAttrib("_native_ok") is not None else 0
        level2 = 0
        if level1:
            env2 = node.node("pc_envelope2").geometry()
            level2 = int(env2.attribValue("_native_ok2")) if \
                env2.findGlobalAttrib("_native_ok2") is not None else 0
        if level1 and not level2:
            fallback.append(name)
        if bool(level2) != native_cooked:
            bad.append((name, "the envelope says %s and copy_packed %s"
                        % ("native" if level2 else "reference",
                           "cooked" if native_cooked else "did not cook")))
        node.parm("stage").set("reference")
        node.cook(force=True)
        want = _snapshot(node.geometry())
        diff = _first_difference(want, got)
        (took_native if native_cooked else took_ref).append(name)
        if diff:
            bad.append((name, ("NATIVE" if native_cooked else "reference")
                        + ": " + diff))
        node.destroy()
    check("output_guard_parity", not bad,
          "%d native / %d reference" % (len(took_native), len(took_ref)),
          "`Stage = output` against `Stage = reference` on %d cases - prim "
          "attribute names, types and every value in order, packed world "
          "bounds, every point position, the detail arrays and the groups. "
          "%s" % (len(built),
                  "; ".join("%s %s" % b for b in bad[:3]) or "identical"))
    # ⚠️ AND WHAT MAKES THE 1.15x REFUSED CEILING HONEST.  A build that passes
    # level 1 and is refused by level 2 cooks the native chain AND the
    # reference - measured at 1.43x (2 km) and 1.54x (20 km) by
    # `bench_guard_fallback`.
    #
    # ⚠️ THE FALLBACK PATH IS REACHABLE ON THE SHIPPED BUILD, and this comment
    # said the opposite for a cycle.  It was written when level 1 answered the
    # deform question with an UPPER bound, which refused every arc in
    # existence; PART B turned it into a LOWER bound in the same cycle that
    # added `GUARD_BEND_LADDER`, two of whose rows (`arc_R20_step0.05`,
    # `arc_R50_step0.1`) are legitimate inputs that pass level 1 and are
    # refused by level 2.  A kit whose module names no rule matches used to be
    # a third such class and cost 2.35x at 18.9 km; `_native_ok` refuses it
    # now (`guard_kit_mismatch`).
    #
    # So this row's "0 of 92" is a statement about the 92 FIXTURES' shapes and
    # kits, not about the tool - it says no case in the scene suite pays the
    # double cook, and `GUARD_BEND_LADDER` is where the shapes that do are
    # pinned.
    check("no_case_pays_the_guard_fallback", not fallback,
          "%d of %d" % (len(fallback), len(built)),
          "cases that pass level 1 and are then REFUSED by level 2, cooking "
          "both chains at the 1.5-1.6x `bench_guard_fallback` measures: %s"
          % (", ".join(fallback[:5]) or "none"))
    check("output_guard_takes_the_native_chain", len(took_native) >= 8,
          len(took_native),
          "cases whose `Stage = output` cook ADVANCED `copy_packed`'s "
          "cookCount - observed, not read off the envelope's own verdict "
          "(D203): %s%s. A guard that never fires would make the row above "
          "vacuous"
          % (", ".join(sorted(took_native)[:8]),
             " ..." if len(took_native) > 8 else ""))
    return took_native


def payload_cond_parity(root):
    """D202 - a `pc_cond` VALUE has to mean the same thing after the PAYLOAD
    round-trip, and for three list lengths it did not.

    ⚠️ NOTHING IN THE SUITE ROUND-TRIPPED A CONDITION VALUE.  `stress_cases`
    and `fixture_cases` hand `rule_table` a live `Style` object, so a `cond`
    value stays the plain Python list it was written as - but the artist face
    writes the style into a DICT POINT ATTRIBUTE and `style.read` reads it
    back, and Houdini hands a 2-, 3- or 4-number list back as a
    `hou.Vector2/3/4`.  Those are neither `list` nor `tuple`, so
    `_cond_columns` classified them COND_BAD and `pc_evaluate_cond` answered
    False to `in` where the reference answers True.  MEASURED on the shipped
    asset, a 20 m line with
    `{"subject": "sectionLength", "op": "in", "value": [20.0, 3.0]}`:
    `Stage = output` built 10 prims all `pc_module = panel`, `Stage =
    reference` built 12 all `gate` - 100 % of the run wrong, on a build the
    guard ADMITS (L1=1 L2=1), with `style._check_cond` silent because both the
    subject and the operator are known.  Lengths 1, 5 and 6 come back as
    tuples and agreed, which is exactly why 92 scene cases and a 170-build
    stress matrix could not see it.

    So the check sweeps the LENGTHS across the boundary - both sides of it -
    and compares the shipped asset's two stages on everything a consumer can
    see, not just the prim count.
    """
    from polyfactory.polychain import Params, Rule, Style
    from polyfactory.polychain import style as STY
    bad, kinds = [], []
    line = [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)]
    for n in range(1, 7):
        value = [20.0] + [3.0 + i for i in range(n - 1)]
        style = Style("cs", 1, 0, rules=[
            Rule("default", "conditional", ["gate"],
                 cond={"subject": "sectionLength", "op": "in",
                       "value": value}),
            Rule("default", "first", ["panel"])], params=Params())
        # the round trip itself, in isolation: what `style.read` hands back
        # has to still classify as a LIST.
        payload = hou.Geometry()
        STY.write(payload, style)
        back, _warns = STY.read(payload)
        got = back.rules[0].cond.get("value")
        kind = H._cond_columns(dict(back.rules[0].cond))[0]
        kinds.append("len %d -> %s kind %d" % (n, type(got).__name__, kind))
        if kind != H.COND_LIST:
            bad.append("len %d: `%s` classifies as kind %d after the round "
                       "trip" % (n, type(got).__name__, kind))
        # and the whole asset, both stages, on the same style.
        geo = hou.Geometry()
        cases.polyline(geo, line, curve_id="CS")
        case = {"curve": geo, "kit": None, "style": style}
        node, out = asset_on(root, case, "output", "pcp%d" % n)
        if out is None:
            bad.append("len %d: cook failed" % n)
            node.destroy()
            continue
        got_snap = _snapshot(out)
        node.parm("stage").set("reference")
        node.cook(force=True)
        diff = _first_difference(_snapshot(node.geometry()), got_snap)
        if diff:
            bad.append("len %d: %s" % (n, diff))
        node.destroy()
    # AND THE FAIL-SAFE, which is the other half of D202: a value the rule
    # table genuinely CANNOT carry must make level 1 refuse the build, not
    # evaluate to False in VEX and to something else in Python.  A `cond` with
    # no `value` key at all is the reachable case - `_cond_columns` answers
    # COND_BAD for it - and every other unported feature in `_native_ok`
    # already fails safe this way.
    novalue = Style("nv", 1, 0, rules=[
        Rule("default", "conditional", ["gate"],
             cond={"subject": "sectionLength", "op": "eq"}),
        Rule("default", "first", ["panel"])], params=Params())
    kind = H._cond_columns(dict(novalue.rules[0].cond))[0]
    geo = hou.Geometry()
    cases.polyline(geo, line, curve_id="CS")
    node, out = asset_on(root, {"curve": geo, "kit": None, "style": novalue},
                         "output", "pcp_novalue")
    node.allowEditingOfContents()
    env = node.node("pc_envelope").geometry()
    refused = not int(env.attribValue("_native_ok")) \
        if env.findGlobalAttrib("_native_ok") is not None else False
    node.parm("stage").set("reference")
    node.cook(force=True)
    safe_diff = _first_difference(_snapshot(node.geometry()),
                                  _snapshot(out) if out is not None else None) \
        if out is not None else "cook failed"
    node.destroy()
    check("native_ok_refuses_an_unreadable_cond",
          kind == H.COND_BAD and refused and not safe_diff,
          "kind %d / refused %s" % (kind, refused),
          "a `pc_cond` whose VALUE the rule table cannot represent (here: no "
          "`value` key, which is COND_BAD) must make level 1 refuse the build "
          "outright - COND_BAD used to mean `VEX evaluates this as False`, "
          "which is the reference's answer only by luck. Output vs "
          "reference: %s" % (safe_diff or "identical"))

    check("payload_cond_values_survive_the_round_trip", not bad,
          "%d lengths" % len(kinds),
          "a list-valued `pc_cond` written through `style.write` and read "
          "back: %s. `Stage = output` against `Stage = reference` on each. "
          "%s" % ("; ".join(kinds), "; ".join(bad[:3]) or "identical"))


def output_guard_mutation(root, built):
    """Level 2 is level 1's BACKSTOP, and this is what shows it holding.

    ⚠️ AND THE FIRST TWO VERSIONS OF THIS CHECK WERE DECORATION, WHICH IS WHY
    IT LOOKS LIKE THIS.  Level 1 grew a "no piece can deform" test and then a
    marker test and then a style-warning test, and after each one there was no
    case left in the 92 that passed level 1 and reached level 2 - so the
    second switch was a node nobody could show doing anything.  A guard whose
    second half never fires is exactly the unfailable shape P2-3V found six
    times.

    So the mutation is aimed at LEVEL 1, not at the fixture: level 1 is a
    CONSERVATIVE MODEL of what the native chain can build, and a model can be
    wrong.  Widening it - dropping its `!bendable` term, which is the whole of
    what it knows about the deform - hands a rippled run to the native chain,
    and level 2 has to be what refuses it.  Then widening level 2 as well has
    to change the shipped output, or neither of them was doing anything.
    """
    geo = hou.Geometry()
    cases.polyline(geo, [(1.0 * i, 0.6 * math.sin(i * 0.35), 0.0)
                         for i in range(201)], curve_id="GM")
    node = root.createNode("pf_polychain", "guardmut")
    node.setInput(0, native.feed(root, geo, "GM_IN"))
    node.parm("stage").set("reference")
    node.cook(force=True)
    want = _snapshot(node.geometry())
    node.parm("stage").set("output")
    node.cook(force=True)
    node.allowEditingOfContents()

    env = node.node("pc_envelope")
    body = env.parm("snippet").eval()
    # ⚠️ THE TARGET IS THE `!bendable` TERM AND IT MOVED IN PART B.  Level 1's
    # marker refusal is gone (D88's warning is raised by `pc_sections` now),
    # so the string this used to key on - "&& !bendable && !markers" - no
    # longer exists and the check reported "target missing" rather than
    # failing loudly.  It keys on the term alone now, which is what it was
    # always about.
    target = "&& !bendable"
    found = target in body
    rows = []
    if found:
        env.parm("snippet").set(body.replace(target, ""))
        node.cook(force=True)
        env2 = node.node("pc_envelope2").geometry()
        level1 = int(node.node("pc_envelope").geometry()
                     .attribValue("_native_ok"))
        level2 = int(env2.attribValue("_native_ok2"))
        planned = int(env2.attribValue("_guard_planned"))
        built_n = int(env2.attribValue("_guard_built"))
        caught = (level1 == 1 and level2 == 0
                  and not _first_difference(want, _snapshot(node.geometry())))
        rows.append(("level 2 catches it", caught,
                     "L1=%d L2=%d, %d planned / %d built"
                     % (level1, level2, planned, built_n)))
        gate = node.node("pc_envelope2")
        body2 = gate.parm("snippet").eval()
        t2 = "i@_native_ok2 = (level1 && planned > 0 && planned == built);"
        if t2 in body2:
            gate.parm("snippet").set(
                body2.replace(t2, "i@_native_ok2 = (level1 && planned > 0);"))
            node.cook(force=True)
            diff = _first_difference(want, _snapshot(node.geometry()))
            rows.append(("and it is load-bearing", bool(diff), diff[:80]))
        else:
            rows.append(("and it is load-bearing", False, "target moved"))
    node.destroy()
    check("mutation_guard_envelope", found and all(r[1] for r in rows),
          "; ".join("%s %s" % (r[0], "yes" if r[1] else "NO") for r in rows)
          or "target missing",
          "widening LEVEL 1 past what it can model hands a rippled run to the "
          "native chain: level 2 refuses it and the output is unchanged, and "
          "widening level 2 too changes the output. %s"
          % ("; ".join(r[2] for r in rows) or "target missing"))


def interleaved_best(variants, reps=3):
    """D204's estimator, generalised - the MIN over `reps` INTERLEAVED
    repetitions of each variant.

    ⚠️ D209.  `output_guard_cost` failed once in three runs of an UNMUTATED
    build (`corner: 1.31x over 1.15x, 0.0066 s vs 0.0050 s`) and
    `decompose_long_curve_wall_clock` went red once under an unrelated
    mutation.  Both were timing A against B in SEPARATE blocks - all of A,
    then all of B - so a busy moment during one block lands entirely on one
    side of the ratio.  D204 diagnosed exactly this on `pc_plan_solve` and
    applied the cure to that one node; this is the same cure, in a function,
    for everything else that hangs a tight ratio on a stopwatch.

    Two properties, and both matter:
      * INTERLEAVED - within one repetition every variant sees the same
        machine, so interference moves the ratio far less than it moves
        either number;
      * MIN - interference can only make a pass SLOWER, so the minimum is the
        closest thing to the variant's own cost.

    `variants` is [(name, setup, run)]; `setup` is untimed (dirtying a parm
    is not part of the measurement) and may be None.
    """
    best = {}
    for _ in range(reps):
        for name, setup, run in variants:
            if setup is not None:
                setup()
            start = time.time()
            run()
            elapsed = time.time() - start
            if name not in best or elapsed < best[name]:
                best[name] = elapsed
    return best


# ⚠️ THE CORNER FIXTURE IS 2 km NOW AND IT USED TO BE THREE POINTS.  D209's
# other half: an 18 m x 14 m L cooks in about 5 ms, and a 1.15x ceiling on a
# 5 ms build is a coin toss whatever the estimator - the observed spread on
# six consecutive runs of an unmutated build was 0.85x to 1.05x, a 24 % swing
# against a 15 % ceiling.  A 2 km L is the same SHAPE (one 90 degree corner,
# refused by level 1) at the same size as the other three rows, so the
# ceiling is measuring the guard rather than the scheduler.
GUARD_CORNER_PTS = ([(1.0 * i, 0.0, 0.0) for i in range(1001)]
                    + [(1000.0, 0.0, 1.0 * j) for j in range(1, 1001)])
# ...and the floor under every row of that check, as an ASSERTION rather than
# a habit: a fixture whose reference side cooks faster than this cannot carry
# a 1.15x ceiling, so it FAILS instead of quietly becoming a coin toss.
GUARD_COST_FLOOR_S = 0.02


def guard_arc_pts(radius, step, length):
    """A FLAT arc - the shape PART B's widened level-1 bound is about."""
    n = int(length / step) + 1
    return [(radius * math.sin(i * step / radius), 0.0,
             radius * (1.0 - math.cos(i * step / radius))) for i in range(n)]


def guard_curved_streets(count=300, seglen=4.0, nseg=15, radius=400.0):
    """THE CITYGEN SHAPE - many SHORT, GENTLY CURVED streets, laid out apart.

    ⚠️ THIS IS THE FIXTURE PART B WAS ORDERED BY, and it is not the same shape
    as `streets_300` two sections up.  That one bends 90 degrees at its middle
    vertex, so it is refused for a CORNER whatever the deform bound says; this
    one only curves, which is what an actual street network looks like and
    what 11.9 rule 2's "many short curves" lesson is really about.  Measured
    on the shipped asset with `hou.perfMon` before the widening: **490 ms of
    Python**, the second largest refused class in the whole mix.
    """
    geo = hou.Geometry()
    for i in range(count):
        x0, z0 = (i % 20) * 80.0, (i // 20) * 70.0
        r = radius * (1.0 + 0.3 * ((i % 7) - 3) / 3.0)
        cases.polyline(geo, [(x0 + r * math.sin(j * seglen / r), 0.0,
                              z0 + r * (1.0 - math.cos(j * seglen / r)))
                             for j in range(nseg + 1)],
                       curve_id="C%03d" % i)
    return geo


def guard_polyline_geo(pts):
    geo = hou.Geometry()
    cases.polyline(geo, pts, curve_id="GC")
    return geo


def output_guard_cost(root):
    """What the guard COSTS, on the shapes it admits and on the ones it does
    not - because a fork whose output is identical can still be a regression.

    ⚠️ THIS CHECK EXISTS BECAUSE THE FIRST VERSION OF THE GUARD WAS ONE.  With
    only the parameter and corner tests in level 1, a fence over a ripple
    passed level 1, cooked the whole native chain, was refused by level 2 for
    having pieces the deformed branch cannot make, and then cooked the
    reference as well: measured, 2 km 0.238 -> 0.361 s and 20 km 2.489 ->
    3.971 s, a 1.6x regression on a shape an artist really builds.  Level 1
    answers the deform question itself now (`pc_envelope.vfl`), and this is
    what holds that line.

    ⚠️ PART B NARROWED WHAT "ANSWERS IT" MEANS, so this check now has rows on
    BOTH sides of the widened bound.  Level 1 used to refuse every curved run
    outright; it now refuses only the ones where a piece will CERTAINLY
    unpack, and it is a LOWER bound rather than an upper one.  The rippled row
    below is still refused (elevation is an outright refusal), the tight arc
    is refused by the bound, and the gentle arc and the 300 curved streets are
    ADMITTED - which is where the 54 ms and 490 ms of Python went.
    `guard_bend_bound` is the row that pins the bound itself; this one is the
    end-to-end cost, and neither replaces the other.

    Two ceilings, and they measure different things:
      * REFUSED - the build takes the reference exactly as it did before, so
        the only extra cost is level 1's own probe.  1.15x, and it measures
        0.93-1.03x.
      * ADMITTED - the build takes the native chain.  1.6x, and it measured
        1.21-1.36x while `pc_plan_solve` was 61 us/piece against
        `plan.plan_sections`' 2.2 on the same input.  Half of that is paid
        off: the deduped row table took the solve to ~31 us/piece and D204's
        identity-permutation skip took another 13-18 % off it, so this shape
        now reads 0.92-1.05x.  `solve_cost_is_flat_in_piece_count` is the
        committed per-piece ceiling that keeps it there - this row is the
        end-to-end one, and neither replaces the other.
    """
    shapes = (
        ("straight_2km",
         lambda: guard_polyline_geo([(1.0 * i, 0.0, 0.0)
                                     for i in range(2001)]), True, True, 1.6),
        # ⚠️ PART B MOVED THIS ROW FROM `refused` TO `admitted`, AND THAT IS
        # THE FLIP THIS CYCLE SHIPS.  A 2 km R = 2 000 arc used to be refused
        # by level 1's straight-and-flat bound and cost 54 ms of Python; the
        # widened bound reads 0.00058 m against a 0.01 m tolerance, level 2
        # confirms 1 888 planned / 1 888 built, and it takes the native chain.
        ("arc_2km",
         lambda: guard_polyline_geo(cases.arc_points(2000.0, 1.0, 2000.0)),
         True, True, 1.6),
        # THE CITYGEN SHAPE, and the reason PART B ordered the way it did.
        ("curved_streets_300", guard_curved_streets, True, True, 1.6),
        # ...and the other side of the same bound: an arc tight enough that a
        # panel really does unpack is refused at LEVEL 1, so it never cooks
        # the native chain and pays only the probe.  Without this row the
        # widening would be asserted in one direction only.
        ("arc_R50_2km",
         lambda: guard_polyline_geo(guard_arc_pts(50.0, 1.0, 2000.0)),
         False, False, 1.15),
        ("bumpy_2km",
         lambda: guard_polyline_geo([(1.0 * i, 0.6 * math.sin(i * 0.35), 0.0)
                                     for i in range(2001)]),
         False, False, 1.15),
        # ⚠️ A UNIFORM RAMP, AND IT IS NOT A DUPLICATE OF THE ROW ABOVE.  The
        # ripple is refused twice over - it is elevated AND it kinks hard
        # enough for the bend bound alone to refuse it - so it cannot tell
        # which of the two refusals is doing the work.  A dead-straight slope
        # has ZERO turn, so the bound reads 0.0 m and ONLY the elevation test
        # refuses it; drop that test and this row passes level 1, cooks the
        # whole native chain, and is thrown out by level 2 for the sheared
        # span a `vertical` piece deforms on.  Measured: that mutation puts
        # `CI_swap_zmode`, `F_hill_vertical`, `G_hill_stepped` and
        # `L_ramp_vertical` on the double cook, and without this row
        # `no_case_pays_the_guard_fallback` was the ONLY check that saw it.
        ("ramp_2km",
         lambda: guard_polyline_geo([(1.0 * i, 0.04 * i, 0.0)
                                     for i in range(2001)]),
         False, False, 1.15),
        ("corner", lambda: guard_polyline_geo(GUARD_CORNER_PTS),
         False, False, 1.15),
    )
    rows = []
    bad = []
    for label, make_geo, want_level1, want_native, ceiling in shapes:
        geo = make_geo()
        node = root.createNode("pf_polychain", "cost_" + label)
        node.setInput(0, native.feed(root, geo, "GC_" + label))
        node.allowEditingOfContents()

        # D209 - INTERLEAVED, not two blocks. See `interleaved_best`.
        # `setup` dirties through a parm every stage reads, so neither side
        # measures a cache hit (D164), and it is outside the timer.
        state = {"i": 0}

        def _setup(stage):
            def go():
                state["i"] += 1
                node.parm("stage").set(stage)
                node.parm("corner_angle_deg").set(
                    30.0 + 0.01 * (state["i"] % 3 + 1))
            return go

        for stage in ("reference", "output"):
            node.parm("stage").set(stage)
            node.cook(force=True)
        best = interleaved_best(
            [(stage, _setup(stage), lambda: node.cook(force=True))
             for stage in ("reference", "output")])
        node.parm("corner_angle_deg").set(30.0)
        node.parm("stage").set("output")
        env = node.node("pc_envelope").geometry()
        level1 = int(env.attribValue("_native_ok")) \
            if env.findGlobalAttrib("_native_ok") is not None else 0
        went_native = level1 and int(
            node.node("pc_envelope2").geometry().attribValue("_native_ok2"))
        ratio = best["output"] / max(best["reference"], 1e-9)
        rows.append((label, ratio, bool(went_native), best["reference"]))
        if bool(went_native) != want_native:
            bad.append("%s: %s the native chain" % (
                label, "took" if went_native else "did not take"))
        # ⚠️ AND THE LEVEL-1 VERDICT SEPARATELY, WHICH IS NOT THE SAME
        # ASSERTION.  A row expected to be REFUSED is refused for a reason,
        # and "did not take the native chain" is satisfied just as well by
        # passing level 1 and being thrown out by level 2 - which cooks BOTH
        # chains.  Dropping the elevation refusal from `pc_envelope.vfl` does
        # exactly that to `bumpy_2km`, and with only the outcome asserted this
        # row stayed green through it: the 1.15x ceiling did not catch it
        # either, because the double cook on that shape happens to land under
        # it.  The refusal an artist pays for has to be the refusal the check
        # names, so both are asserted.
        if bool(level1) != want_level1:
            bad.append("%s: level 1 %s, wanted %s - a build refused at level "
                       "2 instead cooks the native chain first"
                       % (label, "admitted" if level1 else "refused",
                          "admit" if want_level1 else "refuse"))
        # D209 - AND THE FIXTURE HAS TO BE BIG ENOUGH TO CARRY THE RATIO.
        # This FAILS rather than skipping: a fixture that shrinks below the
        # floor turns a tight ceiling into a coin toss, and the whole finding
        # is that a coin toss teaches a reader to stop believing the suite.
        if best["reference"] < GUARD_COST_FLOOR_S:
            bad.append("%s: the reference cooks in %.4f s, under the %.0f ms "
                       "floor - a %.2fx ceiling on it is noise, not a "
                       "measurement" % (label, best["reference"],
                                        GUARD_COST_FLOOR_S * 1e3, ceiling))
        if ratio > ceiling:
            bad.append("%s: %.2fx over %.2fx (%.4f s vs %.4f s)"
                       % (label, ratio, ceiling, best["output"],
                          best["reference"]))
        node.destroy()
    check("output_guard_cost", not bad,
          "; ".join("%s %.2fx/%.0fms%s"
                    % (r[0], r[1], r[3] * 1e3, " native" if r[2] else "")
                    for r in rows),
          "`Stage = output` against `Stage = reference` on the same node, MIN "
          "over 3 INTERLEAVED repetitions (D209 - two separate blocks put a "
          "busy moment entirely on one side of the ratio, and this failed "
          "once in three runs of an unmutated build). A build the guard "
          "REFUSES may cost no more than 1.15x (level 1's own probe), one it "
          "ADMITS no more than 1.6x (the solve), and every fixture must cook "
          "in at least %.0f ms. %s"
          % (GUARD_COST_FLOOR_S * 1e3, "; ".join(bad) or "both ceilings hold"))


# PART B - THE LADDER LEVEL 1's WIDENED DEFORM BOUND IS JUDGED ON.
#
# (label, radius m, vertex spacing m, run length m, what level 1 must say,
#  what level 2 must say once level 1 has admitted).  `None` for the level-2
# column means level 1 refused and level 2 was never asked.
#
# ⚠️ THE THIRD AND FOURTH ROWS ARE THE POINT OF THE WHOLE TABLE.  Level 1's
# bound reads ONE kink - the sharpest anywhere in the build - so a FINELY
# RESAMPLED arc puts several kinks inside one module span and the bound
# UNDER-READS: R = 20 m at 0.05 m spacing bounds the deviation at 0.00142 m
# and level 2 then finds 284 pieces planned against 143 built.  That is the
# bound being wrong in the direction it is allowed to be wrong in, and
# `guard_bend_bound` asserts the OUTPUT IS STILL IDENTICAL there, which is the
# only property that actually matters.  A ladder without those rows would
# assert that the bound is never wrong, which is false, instead of asserting
# that being wrong is safe, which is the design.
GUARD_BEND_LADDER = (
    ("arc_R2000_step1",   2000.0, 1.0,  2000.0, True,  True),
    ("arc_R200_step2",     200.0, 2.0,  2000.0, True,  True),
    ("arc_R100_step2",     100.0, 2.0,  2000.0, False, None),
    ("arc_R20_step0.05",    20.0, 0.05,  300.0, True,  False),
    ("arc_R50_step0.1",     50.0, 0.1,   600.0, True,  False),
    ("arc_R20_step0.5",     20.0, 0.5,   300.0, False, None),
)
# What a level-1 pass / level-2 refusal is allowed to cost on that ladder.
# Measured 1.21x and 1.27x on the two rows that reach it; the ceiling is
# `bench_guard_fallback`'s, because it is the same double cook.
GUARD_BEND_FALLBACK_CEILING = 1.8


# PART B - the Gap values `guard_padding_parity` sweeps.  Negative is not
# decoration: 4.2 packs with `pc_pad` and RailClone's semantics allow a
# NEGATIVE overlap, which is a different branch of the solve (D17's
# "padding that cancels the unit degrades") and the one most likely to
# diverge.
GUARD_PADDING_M = (0.05, 0.4, -0.05, -0.3)


def kit_starter_cooks_once(root):
    """D154 - DECLINED, and this is the measurement that declines it.

    13.3.6 and 21.10 both list `kit_starter` as Python that must go native:
    "geometry construction in Python, on the shipped path, cold".  PART B
    measured it instead of porting it, and both halves of the case for porting
    turned out to be wrong.

    1. IT DOES NOT RE-COOK.  Measured on a warm instance: `cookCount` stays at
       1 through spline nudges, `bend_tol`, `padding`, `seed` and every `Stage`
       change - while `config` next to it goes 1 -> 4 on the same sequence.
       It is 1.50-1.83 ms, **1.4 % of ONE cold build and 0 % of every cook
       after it**.  `houdini-procedural-modeling` rule 1 forbids "per-element
       geometry in a node that RE-COOKS" and explicitly permits a Python SOP
       for a trivial one-off constructor; this is the second thing, not the
       first.

    2. THE PRESCRIBED MECHANISM DOES NOT PRESERVE THE GEOMETRY.  13.3.6 says
       "four `box` SOPs + `pack`".  Probed on 22.0.398: a Box SOP at
       `type = polymesh, divrate1 = 9` gives 34 four-sided prims and 36 points,
       exactly `box_mesh(divx=8)`'s counts, and both score 0 inward faces - but
       the point SET, the point ORDER and the vertex ORDER all differ, because
       the Box SOP lays points out per face and `box_mesh` lays them out in
       4-point rings along x.  Every module is packed and copied, so swapping
       the builder re-orders the points of every element the tool ships and
       moves `geometry_digest` on every case in the suite.  1.5 ms once per
       instance is not worth moving every baseline.

    ⚠️ SO THIS CHECK PINS THE PREMISE, NOT THE CONCLUSION.  A decision resting
    on "it only cooks once" is worth exactly as much as that sentence staying
    true, and nothing was watching it.  The day an edit puts `kit_starter` on
    a dependency that dirties per cook, this goes red and D154 is open again.
    """
    geo = guard_polyline_geo([(1.0 * i, 0.0, 0.0) for i in range(501)])
    src = native.feed(root, geo, "KS_IN")
    dirt = root.createNode("attribwrangle", "ks_dirty")
    dirt.parm("class").set(0)
    group = dirt.parmTemplateGroup()
    group.append(hou.IntParmTemplate("nudge", "Nudge", 1))
    dirt.setParmTemplateGroup(group)
    dirt.parm("snippet").set('i@_ks = chi("nudge");')
    dirt.setInput(0, src)

    node = root.createNode("pf_polychain", "kit_starter_once")
    node.setInput(0, dirt)              # NO kit wired - the fallback IS the kit
    node.allowEditingOfContents()
    node.cook(force=True)
    starter, config = node.node("kit_starter"), node.node("config")
    first = starter.cookCount()

    steps = []
    for i, (what, act) in enumerate((
            ("spline", lambda: dirt.parm("nudge").set(100 + i)),
            ("spline again", lambda: dirt.parm("nudge").set(200 + i)),
            ("bend_tol", lambda: node.parm("bend_tol").set(0.02)),
            ("padding", lambda: node.parm("padding").set(0.03)),
            ("seed", lambda: node.parm("seed").set(9)),
            ("stage=reference", lambda: node.parm("stage").set("reference")),
            ("stage=output", lambda: node.parm("stage").set("output")))):
        act()
        node.cook()
        steps.append((what, starter.cookCount(), config.cookCount()))

    # ⚠️ `config` IS THE CONTROL.  Without it "cookCount stayed at 1" is also
    # what a node that never cooked at all would report, and the whole row
    # would be satisfied by a broken fixture.  `config` is dirtied by the parm
    # changes above and has to prove it by advancing.
    starter_moved = [w for w, k, _c in steps if k != first]
    config_moved = steps[-1][2] > 1
    ok = first == 1 and not starter_moved and config_moved
    check("kit_starter_cooks_once", ok,
          "%d cook%s over %d dirtying steps"
          % (steps[-1][1], "" if steps[-1][1] == 1 else "s", len(steps)),
          "D154 is DECLINED on the measurement that `kit_starter` never "
          "re-cooks - 1.4%% of ONE cold build and 0%% of every cook after it - "
          "so this pins that premise. `config` beside it is the control and "
          "must advance (%d): %s. kit_starter advanced on: %s"
          % (steps[-1][2], "; ".join("%s=%d" % (w, k) for w, k, _c in steps),
             ", ".join(starter_moved) or "nothing"))
    node.destroy()
    dirt.destroy()


def guard_padding_parity(root):
    """PART B - D91's Gap, on the native chain, against the reference.

    ⚠️ NO CASE IN THE 92 REACHES THIS AND THAT IS WHY IT IS ITS OWN CHECK.
    `padding` is a PARM-FACE control (D91) and every scene case drives the
    kernel through a `Style` object, so `output_guard_parity`'s 92 builds
    never touch the parm - the last three criticals in this project were all
    features no case exercised, and shipping the port on the strength of a
    suite that cannot reach it would be the fourth.

    The port itself is one branch in `hda.config_resolved`: nothing in the
    native chain reads the kit geometry's `pc_pad` (grep says `pc_plan.h` and
    only `pc_plan.h`, through CONFIG's flattened `pc_k_pad0` / `pc_k_pad1`), so
    padding the kit before it is flattened is the whole of it.  What has to be
    proved is that the flattened numbers reach the solve and produce the
    reference's fence element for element - not merely that the build no
    longer refuses.
    """
    rows, bad = [], []
    for pad in GUARD_PADDING_M:
        geo = guard_polyline_geo([(1.0 * i, 0.0, 0.0) for i in range(201)])
        node = root.createNode("pf_polychain", "pad_%d" % int(pad * 1000))
        node.setInput(0, native.feed(root, geo, "PAD_%d" % int(pad * 1000)))
        node.parm("padding").set(pad)
        node.allowEditingOfContents()
        node.parm("stage").set("output")
        node.cook(force=True)
        took = node.node("copy_packed").cookCount() > 0
        got = _snapshot(node.geometry())
        node.parm("stage").set("reference")
        node.cook(force=True)
        want = _snapshot(node.geometry())
        diff = _first_difference(want, got)
        nprim = len(node.geometry().prims())
        if not took:
            bad.append("%+.2f m: took the reference - the guard still refuses "
                       "a padded build" % pad)
        if diff:
            bad.append("%+.2f m: %s" % (pad, diff))
        rows.append((pad, nprim, took))
        node.destroy()

    # ...and the sweep has to MOVE the fence, or every row above is the same
    # build four times and the parity is a comparison of nothing with nothing.
    counts = sorted(set(r[1] for r in rows))
    if len(counts) < 2:
        bad.append("every Gap value built %d prims - the parm is not reaching "
                   "the solve at all" % counts[0])
    check("guard_padding_parity", not bad,
          "; ".join("%+.2fm %d prims%s" % (r[0], r[1], "" if r[2] else " REF")
                    for r in rows),
          "D91's Gap on the NATIVE chain against `Stage = reference`, over %d "
          "values including negative overlaps, element for element. No scene "
          "case sets this parm, so nothing else in the suite can see it. %s"
          % (len(GUARD_PADDING_M), "; ".join(bad[:3]) or "identical"))


def guard_bend_bound(root):
    """PART B - level 1's deform bound, judged against level 2's exact answer.

    THE BOUND CHANGED CATEGORY THIS CYCLE AND THIS CHECK IS WHY IT IS SAFE TO.
    Level 1 used to hold an UPPER bound on `span_deviation` - "no kink and no
    elevation change" - which is exact, free, and refuses every arc in
    existence.  Measured on the shipped asset with `hou.perfMon`, that refusal
    was 490 ms of Python on 300 gently curved streets and 54 ms on a 2 km arc,
    while level 2 - which asks `pc_deform_gate` the exact question, per piece -
    admitted both.

    So level 1 now holds a LOWER bound: will a piece CERTAINLY unpack.  Both
    ways of being wrong are safe, and both are asserted here rather than
    argued:

      * REFUSE where level 2 would have admitted -> the reference cooks, the
        output is right, one native opportunity is missed.  Row `arc_R100`.
      * ADMIT where level 2 refuses -> the DOUBLE COOK, and the output must
        still be identical.  Rows `arc_R20_step0.05` and `arc_R50_step0.1`,
        which are exactly the case the bound gets wrong (many kinks inside one
        span, one kink read).

    ⚠️ AND THE LAST ASSERTION IS THE ONE THAT WOULD CATCH A REAL REGRESSION.
    `no_case_pays_the_guard_fallback` says no case in the 92 reaches the
    double cook; that is a statement about the CASES, not about the guard, and
    it would stay green if the fallback path were broken.  These two rows
    reach it deliberately and compare `Stage = output` against
    `Stage = reference` element for element on the way through.
    """
    rows, bad = [], []
    for label, radius, step, length, want1, want2 in GUARD_BEND_LADDER:
        geo = guard_polyline_geo(guard_arc_pts(radius, step, length))
        node = root.createNode("pf_polychain", "bend_" + label)
        node.setInput(0, native.feed(root, geo, "BB_" + label))
        node.allowEditingOfContents()
        node.parm("stage").set("output")
        node.cook(force=True)
        env = node.node("pc_envelope").geometry()
        level1 = int(env.attribValue("_native_ok"))
        bound = float(env.attribValue("_guard_dev_bound"))
        level2 = None
        if level1:
            level2 = bool(int(node.node("pc_envelope2").geometry()
                              .attribValue("_native_ok2")))
        if bool(level1) != want1:
            bad.append("%s: level 1 %s, wanted %s"
                       % (label, bool(level1), want1))
        if level1 and level2 != want2:
            bad.append("%s: level 2 %s, wanted %s" % (label, level2, want2))

        # THE OUTPUT, on every row and not only on the admitted ones.
        got = _snapshot(node.geometry())
        node.parm("stage").set("reference")
        node.cook(force=True)
        diff = _first_difference(_snapshot(node.geometry()), got)
        if diff:
            bad.append("%s: %s" % (label, diff))
        rows.append((label, bool(level1), level2, bound))
        node.destroy()

    admitted = [r for r in rows if r[2] is True]
    refused1 = [r for r in rows if not r[1]]
    fellback = [r for r in rows if r[2] is False]
    # A bound that admits everything, or refuses everything, is not a bound.
    if not admitted:
        bad.append("no row on this ladder reaches the native chain")
    if not refused1:
        bad.append("level 1 refuses nothing on this ladder")
    if not fellback:
        bad.append("no row exercises the level-1 pass / level-2 refusal path, "
                   "so nothing here proves it is safe")
    check("guard_bend_bound", not bad,
          "%d native / %d refused at L1 / %d fell back to L2"
          % (len(admitted), len(refused1), len(fellback)),
          "PART B - level 1's LOWER bound on `span_deviation` against level "
          "2's exact per-piece answer, over %d arcs, with `Stage = output` "
          "compared to `Stage = reference` on every one. The bound reads ONE "
          "kink, so a finely resampled arc under-reads it and level 2 has to "
          "catch that - which it must do without changing the output. %s"
          % (len(GUARD_BEND_LADDER),
             "; ".join(bad) or "; ".join("%s %.5f m %s" % (
                 r[0], r[3], "native" if r[2] else
                 ("L2 refused" if r[1] else "L1 refused")) for r in rows)))
    return rows


def guard_bend_bound_skips_rigid_modules(root):
    """PART B - D27 in `hda._bend_bound`, on a kit that can tell the difference.

    ⚠️ THIS CHECK EXISTS BECAUSE A MUTATION SURVIVED.  Deleting the
    `deform <= 0: continue` line from `_bend_bound` - so that a RIGID module
    sets the deform bound for the whole build - left the suite at 0 `[FAIL]`.
    The reason is that the starter kit's rigid modules are all `stepped`, so
    D87's yaw-only rule had already cut them down to their z half (0.06 and
    0.08 m) and they were not the widest thing in the kit any more.  Two
    correct rules, and only one of them was load-bearing on the fixtures.

    So this is the kit that separates them: `corner_post` - RIGID, and the
    widest module in the starter kit at ry = 1.3 m - re-tagged `adaptive`, so
    that D87 no longer shrinks it and only D27 can exclude it.  On a 2 km
    R = 200 m arc the bound then reads 0.0054 m with D27 and 0.018 m without,
    against a 0.01 m tolerance - and level 2's exact answer is ADMIT, 1 888
    planned and 1 888 built.  Without D27 the build takes the reference and
    the 54 ms of Python PART B removed comes straight back.

    D27 is `_needs_deform`'s own first test - `proto.module.deform <= 0`
    returns False before anything is measured - so a rigid module genuinely
    cannot unpack however sharp the turn is.  This asserts that the bound
    agrees with the gate about that rather than merely being safe.
    """
    from polyfactory.polychain import kit as K

    kit_geo = hou.Geometry()
    kit_geo.merge(K.starter_kit())
    # ⚠️ the tag lives on the packed prim's FIRST POINT, which is where
    # `kit.read` looks for it (`_sattr(pt, "pc_zmode", ...)`).
    if kit_geo.findPointAttrib("pc_zmode") is None:
        kit_geo.addAttrib(hou.attribType.Point, "pc_zmode", "adaptive")
    retagged = 0
    for prim in kit_geo.prims():
        pt = prim.points()[0]
        if pt.attribValue("pc_name") == "corner_post":
            pt.setAttribValue("pc_zmode", "adaptive")
            retagged += 1

    geo = guard_polyline_geo(guard_arc_pts(200.0, 2.0, 2000.0))
    node = root.createNode("pf_polychain", "bend_rigid")
    node.setInput(0, native.feed(root, geo, "BR_SPLINE"))
    node.setInput(1, native.feed(root, kit_geo, "BR_KIT"))
    node.allowEditingOfContents()
    node.parm("stage").set("output")
    node.cook(force=True)
    env = node.node("pc_envelope").geometry()
    level1 = int(env.attribValue("_native_ok"))
    bound = float(env.attribValue("_guard_dev_bound"))
    took = node.node("copy_packed").cookCount() > 0
    got = _snapshot(node.geometry())
    node.parm("stage").set("reference")
    node.cook(force=True)
    diff = _first_difference(_snapshot(node.geometry()), got)
    node.destroy()

    ok = retagged == 1 and level1 == 1 and took and not diff
    check("guard_bend_bound_skips_rigid_modules", ok,
          "bound %.5f m, %s" % (bound, "native" if took else "reference"),
          "a kit whose WIDEST module is RIGID and `adaptive` - so D87's "
          "yaw-only rule cannot shrink it and only D27 can exclude it - must "
          "still admit a 2 km R = 200 m arc that level 2 confirms is fully "
          "packed. Without D27 the bound reads 0.018 m against 0.01 and the "
          "build takes the reference. retagged=%d level1=%d took_native=%s%s"
          % (retagged, level1, took, "; " + diff if diff else ""))


def guard_bend_bound_needs_its_operands(root):
    """PART B - a bound that could not be DERIVED must refuse, not read zero.

    `hda._bend_bound` returns (span, radius, KNOWN) and level 1 refuses the
    build outright when the third value is 0.  Without that flag an empty or
    unreadable kit publishes span 0 / radius 0, the bound evaluates to 0.0 m,
    and 0.0 is under every tolerance there is - so the guard would ADMIT every
    curve in existence on exactly the input it understands least.

    ⚠️ THAT IS NOT A HYPOTHETICAL FAILURE MODE, IT IS THE ONE THIS PROJECT HAS
    SHIPPED TWICE.  20.1's `hou.Vector2` cond value and 20.2's `attr:` on a
    multi-component prim attribute were both a VEX expression quietly
    evaluating False on an input nobody had modelled, and each shipped 100 %
    wrong modules on the DEFAULT path.  The mutation below is the same shape:
    it removes the flag's refusal and asserts a straight run - which the guard
    would otherwise admit - is refused instead.
    """
    geo = guard_polyline_geo(guard_arc_pts(2000.0, 1.0, 2000.0))
    node = root.createNode("pf_polychain", "bend_operands")
    node.setInput(0, native.feed(root, geo, "BO"))
    node.allowEditingOfContents()
    node.parm("stage").set("output")
    node.cook(force=True)
    env = node.node("pc_envelope")
    before = int(env.geometry().attribValue("_native_ok"))

    # the mutation: the flag says the pair was never derived
    src = env.parm("snippet").eval()
    env.parm("snippet").set(src + "\nif (1) { i@_native_ok = 0; }\n")
    node.cook(force=True)
    forced = int(env.geometry().attribValue("_native_ok"))
    env.parm("snippet").set(src)

    # ...and the real one: `bound_ok` cleared where the VEX reads it
    env.parm("snippet").set(
        src.replace('int bendable = !bound_ok;',
                    'bound_ok = 0;\nint bendable = !bound_ok;'))
    node.cook(force=True)
    after = int(env.geometry().attribValue("_native_ok"))
    ok_flag = int(env.geometry().attribValue("_guard_bound_ok"))
    env.parm("snippet").set(src)
    node.destroy()

    # ⚠️ AND THE OTHER HALF, WHICH A NODE CANNOT REACH (D212).  Everything
    # above proves the VEX honours the flag; nothing above proves `_bend_bound`
    # ever RAISES it.  A mutation that made the unreadable-kit path return
    # `derived` instead of `refuse` survived the whole suite, because no
    # fixture can put an unreadable kit in front of the asset - a kit broken
    # enough to fail this way fails `kit.validate` first and `_native_ok`
    # refuses it for the warnings instead.  So the PURE VERDICT is called
    # directly, which is D212's own remedy: where a physical mutation cannot
    # be staged, mutate the function's answer and assert it.
    from polyfactory.polychain import kit as K

    class _UnreadableSources(dict):
        """`source_for` cannot get at the module's geometry at all."""

        def get(self, *args, **kwargs):
            raise RuntimeError("kit source unreadable")

    bad_kit = K.Kit("broken", 1, [K.Module("m", (1.0, 1.0, 0.1), deform=1)])
    verdict = H._bend_bound(bad_kit, _UnreadableSources(), DEFAULTS)
    # ...and the same call on a kit that IS readable, so the row above is not
    # satisfied by a function that refuses everything.
    good = K.read(K.starter_kit())
    sound = H._bend_bound(good[0], good[1], DEFAULTS)
    # ⚠️ AND THE EMPTY KIT, WHICH IS THE OTHER HALF AND WAS NEVER IMPLEMENTED.
    # This docstring says "an empty or unreadable kit publishes span 0 /
    # radius 0 ... so the guard would ADMIT every curve in existence", and
    # `pc_envelope.vfl`'s own warning block says the same in the same words -
    # but only the UNREADABLE branch (`except -> (0, 0, 0)`) existed, and only
    # that branch was asserted.  A `Kit` with no modules never entered the
    # loop, fell through to the derived return and published
    # (0.0, 0.0, 1.0) - a bound of ZERO, flagged DERIVED, which is the
    # fail-OPEN answer the flag exists to prevent.  Not reachable through the
    # node today (`kit.read` warns on an empty kit and `_native_ok` refuses on
    # any kit warning), which is why it was a documented fail-safe that was
    # not the implemented one rather than a shipped divergence - but it is
    # 20.1's and 20.2's shape exactly, and the fix is one counter.
    empty = H._bend_bound(K.Kit("empty", 1, []), {}, DEFAULTS)
    # ...and the ALL-RIGID kit, which must stay the deliberate derived zero
    # the docstring argues for: nothing in it can unpack, so the bound is
    # genuinely 0 and the flag is genuinely 1.  Without this row the fix above
    # would be satisfied by refusing every kit with no deformable module.
    rigid = K.read(cases.rigid_kit())
    rigid_v = H._bend_bound(rigid[0], rigid[1], DEFAULTS)

    ok = (before == 1 and forced == 0 and after == 0 and ok_flag == 0
          and verdict == (0.0, 0.0, 0.0) and sound[2] == 1.0
          and sound[0] > 0.0
          and empty == (0.0, 0.0, 0.0)
          and rigid_v[2] == 1.0 and rigid_v[0] == 0.0 and rigid_v[1] == 0.0)
    check("guard_bend_bound_needs_its_operands", ok,
          "admits %d, refuses %d without the flag" % (before, after),
          "a 2 km arc the widened bound ADMITS must be REFUSED the moment "
          "`bend_bound_ok` says the kit's span and radius were never derived "
          "- a bound of 0.0 m is under every tolerance there is, so an "
          "underivable kit must fail SAFE rather than read as `nothing can "
          "deform`. before=%d forced=%d cleared=%d flag=%d; "
          "`_bend_bound` on an unreadable kit -> %r and on an EMPTY one -> "
          "%r (both must be (0.0, 0.0, 0.0) - nothing was inspected, so "
          "nothing was derived); on the starter kit -> %r (must be derived, "
          "with a span); on an ALL-RIGID kit -> %r (must be a DERIVED zero - "
          "nothing in it can unpack, which is a different sentence)"
          % (before, forced, after, ok_flag, verdict, empty, sound, rigid_v))


# --- PART A2: the artist's own attribute TYPES, and the kit-name mismatch ---
#
# (name, class, the storage that DIVERGES, the value, what it breaks)
GUARD_TYPE_ROWS = (
    ("edge_id", "prim", "int",
     "D29's curve-id ladder is string-only in VEX, so an int reads \"\" and "
     "falls through to the primitive number while the reference does "
     "`str(cid)` - every `pc_elem_id` differs AND `decompose_all` sorts on "
     "the id, so the curves come out in a different ORDER"),
    ("pc_curve_id", "prim", "int",
     "the first rung of the same ladder"),
    ("pc_style", "prim", "int",
     "`skey = prim(0, \"pc_style\", pr)` reads \"\", so an `attr:pc_style` "
     "condition evaluates against the empty string natively and against "
     "`str(5)` in the reference - 100 % of the run ships the wrong module"),
    ("pc_yclass", "prim", "int",
     "`primattribtype(0, \"pc_yclass\") == 2` blanks it, so the native chain "
     "builds a 1D run where the reference builds a 2D one and the whole "
     "phase-2 stamp is missing from the output schema"),
    ("pc_marker_id", "point", "string",
     "`int mid = point(0, \"pc_marker_id\", p)` reads 0 where the reference "
     "does `int(\"3\")`, so the `marker:<id>` rule never fires natively"),
)


def _typed_spline(name, cls, storage, value, marker=False):
    """A 20 m line whose `name` is authored at a storage VEX cannot read."""
    geo = hou.Geometry()
    cases.polyline(geo, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
                   curve_id=None if name == "pc_curve_id" else "A")
    if marker:
        for attr, default in (("pc_marker", 0), ("pc_curve", ""),
                              ("pc_u", 0.0)):
            geo.addAttrib(hou.attribType.Point, attr, default)
        geo.addAttrib(hou.attribType.Point, name,
                      "" if storage == "string" else 0)
        pt = geo.createPoint()
        pt.setPosition((5.0, 0.0, 0.0))
        pt.setAttribValue("pc_marker", 1)
        pt.setAttribValue("pc_curve", "A")
        pt.setAttribValue("pc_u", 0.25)
        pt.setAttribValue(name, value)
        return geo
    kind = hou.attribType.Prim if cls == "prim" else hou.attribType.Point
    geo.addAttrib(kind, name, "" if storage == "string" else 0)
    for elem in (geo.prims() if cls == "prim" else geo.points()):
        elem.setAttribValue(name, value)
    return geo


def guard_spline_attr_types(root):
    """The artist's spline attributes have STORAGE, and four of them shipped
    a different fence when the storage was not the one VEX asks for.

    ⚠️ FOUR SHIPPED PARITY DIVERGENCES IN ONE SHAPE, ALL ON BUILDS THE GUARD
    ADMITTED WITH NO WARNING.  3.1 names the spline attributes; it does not
    name their storage.  `place.read_curves` reads whatever the artist
    authored and converts it (`str(cid)`, `int(... or 0)`, `float(u)`); VEX
    asks for a typed value and gets the TYPE'S ZERO when the storage does not
    match - "" for a string read of an int, 0 for an int read of a string -
    and zero is a legal value in every one of them, so nothing errors and
    nothing warns.  Measured on the shipped asset before the fix, each with
    level 1 admitting and `copy_packed` cooking:

      * an INT `edge_id` (7, 3) - `pc_curve_id` "0"/"1" natively against the
        reference's "7"/"3", and the curves EMITTED IN A DIFFERENT ORDER;
      * an INT `pc_style` = 5 under an `attr:pc_style` condition - 10 `panel`
        natively against the reference's 12 `gate`, 100 % of the run;
      * an INT `pc_yclass` = 2 - a 1D run natively, a 2D one in the reference,
        `pc_array`/`pc_cell`/`pc_clipped`/`pc_row`/`pc_yclass` absent;
      * a STRING `pc_marker_id` "3" under a `marker:3` rule - no gate at all.

    ⚠️ NOTHING IN THE SUITE COULD SEE ANY OF IT, and the reason is uniform:
    every case in `cases.py` authors these as the storage VEX happens to want,
    and `edge_id` - D29's second rung, added for the streets stream - had ZERO
    occurrences anywhere under `tests/`.  A parity case that cannot reach a
    code path proves nothing.

    ⚠️ THE ANSWER IS A REFUSAL, NOT A COERCION.  Reproducing Python's `str()`
    in VEX is a trap (`str(2.0)` is "2.0", `sprintf("%g")` is "2"), so a
    ported coercion would be a new divergence wearing the fix's clothes.  The
    guard's own law is that a build the native chain cannot answer takes the
    reference, and an attribute whose storage the chain cannot read is
    exactly that.  `pc_envelope.vfl` holds the table.

    The check asserts BOTH halves on every row: the guard refuses (level 1 = 0
    and `copy_packed` never cooks), AND `Stage = output` is the reference's
    own answer element for element - because a refusal that shipped a
    different fence would be no better than the admission it replaced.
    """
    from polyfactory.polychain.style import Rule, Style
    bad, rows = [], []
    for name, cls, storage, why in GUARD_TYPE_ROWS:
        marker = (name == "pc_marker_id")
        value = "3" if storage == "string" else (5 if name == "pc_style" else
                                                 (2 if name == "pc_yclass"
                                                  else 7))
        geo = _typed_spline(name, cls, storage, value, marker=marker)
        style = None
        if name == "pc_style":
            style = Style(rules=[
                Rule("default", "conditional", ["gate"],
                     cond={"subject": "attr:pc_style", "op": "eq",
                           "value": "5"}),
                Rule("default", "first", ["panel"])])
        elif marker:
            style = Style(rules=[Rule("marker:3", "first", ["gate"]),
                                 Rule("default", "first", ["panel"])])
        got = ref = None
        level1 = cooked = None
        for stage in ("output", "reference"):
            tag = "%s_%s_%s" % (name, storage, stage)
            case = {"curve": geo, "kit": None, "style": style,
                    "surface": None}
            node, out = asset_on(root, case, stage, tag)
            if out is None:
                bad.append("%s: cook failed at %s" % (name, stage))
                node.destroy()
                break
            if stage == "output":
                node.allowEditingOfContents()
                cooked = node.node("copy_packed").cookCount() > 0
                env = node.node("pc_envelope").geometry()
                level1 = int(env.attribValue("_native_ok"))
                got = _snapshot(out)
            else:
                ref = _snapshot(out)
            node.destroy()
        if got is None or ref is None:
            continue
        diff = _first_difference(ref, got)
        rows.append("%s(%s) L1=%s" % (name, storage, level1))
        if level1 or cooked:
            bad.append("%s as %s: the guard ADMITTED it (L1=%s, "
                       "copy_packed cooked=%s) - %s"
                       % (name, storage, level1, cooked, why))
        if diff:
            bad.append("%s as %s: output != reference - %s"
                       % (name, storage, diff))
    # ...and the CONTROL, so the row above is not satisfied by a guard that
    # refuses every build with any of these names on it.  Same attribute,
    # same value, authored at the storage the chain reads.
    ctrl = hou.Geometry()
    cases.polyline(ctrl, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)])
    ctrl.addAttrib(hou.attribType.Prim, "edge_id", "")
    for pr in ctrl.prims():
        pr.setAttribValue("edge_id", "7")
    ctrl_case = {"curve": ctrl, "kit": None, "style": None, "surface": None}
    node, out = asset_on(root, ctrl_case, "output", "edge_id_ctrl")
    ctrl_native = False
    if out is not None:
        node.allowEditingOfContents()
        ctrl_native = node.node("copy_packed").cookCount() > 0
        cid = sorted(set(pr.attribValue("pc_curve_id")
                         for pr in out.prims()))
        if cid != ["7"]:
            bad.append("string edge_id: pc_curve_id %r, expected ['7']" % cid)
        # ⚠️ AND AGAINST THE REFERENCE, because D29's SECOND rung had zero
        # occurrences anywhere under `tests/` before this check - `grep
        # edge_id tests/polychain` returned nothing, and every case in
        # `cases.py` authors `pc_curve_id` instead.  A rung nothing exercises
        # is a rung nobody knows the two paths agree on, whatever its storage.
        ctrl_got = _snapshot(out)
        node.destroy()
        node, ref_out = asset_on(root, ctrl_case, "reference",
                                 "edge_id_ctrl_r")
        if ref_out is None:
            bad.append("string edge_id: the reference would not cook")
        else:
            ctrl_diff = _first_difference(_snapshot(ref_out), ctrl_got)
            if ctrl_diff:
                bad.append("string edge_id: native != reference - %s"
                           % ctrl_diff)
    node.destroy()
    if not ctrl_native:
        bad.append("a STRING edge_id must still take the native chain - the "
                   "refusal is about storage, not about the name")
    check("guard_spline_attr_types", not bad,
          "%d refused, control native" % len(rows),
          "an artist attribute authored at a storage the VEX chain cannot "
          "read must be REFUSED at level 1 and must ship the reference's own "
          "fence: %s. Control (a STRING `edge_id`) took the native chain: "
          "%s. %s" % ("; ".join(rows), ctrl_native,
                      "; ".join(bad[:3]) or "all rows refused and identical"))


def mutation_spline_attr_types(root):
    """...and the table has to BITE, per row, or it is decoration.

    D206's lesson in a new place: a refusal table that is never mutated is a
    list of strings.  Each row's entry is removed from `pc_envelope.vfl`'s own
    table in turn and the fixture re-cooked; level 1 must ADMIT it again, and
    the output must go back to disagreeing with the reference.  A row that
    cannot be made to admit is a row the guard was never enforcing.
    """
    from polyfactory.polychain.style import Rule, Style
    node = None
    survivors, rows = [], []
    for name, cls, storage, _why in GUARD_TYPE_ROWS:
        marker = (name == "pc_marker_id")
        value = "3" if storage == "string" else (5 if name == "pc_style" else
                                                 (2 if name == "pc_yclass"
                                                  else 7))
        geo = _typed_spline(name, cls, storage, value, marker=marker)
        style = None
        if name == "pc_style":
            style = Style(rules=[
                Rule("default", "conditional", ["gate"],
                     cond={"subject": "attr:pc_style", "op": "eq",
                           "value": "5"}),
                Rule("default", "first", ["panel"])])
        elif marker:
            style = Style(rules=[Rule("marker:3", "first", ["gate"]),
                                 Rule("default", "first", ["panel"])])
        case = {"curve": geo, "kit": None, "style": style, "surface": None}
        node, _out = asset_on(root, case, "output", "mut_%s" % name)
        node.allowEditingOfContents()
        env = node.node("pc_envelope")
        src = env.parm("snippet").eval()
        # blank this ONE row's name out of the table, leaving the others
        env.parm("snippet").set(src.replace('"%s"' % name, '"_no_such_attr"'))
        node.cook(force=True)
        admitted = int(node.node("pc_envelope").geometry()
                       .attribValue("_native_ok"))
        env.parm("snippet").set(src)
        node.destroy()
        rows.append("%s %s" % (name, "ADMITTED" if admitted else "still refused"))
        if not admitted:
            survivors.append(name)
    check("mutation_spline_attr_types", not survivors,
          "%d/%d bite" % (len(GUARD_TYPE_ROWS) - len(survivors),
                          len(GUARD_TYPE_ROWS)),
          "each row of `pc_envelope.vfl`'s storage table, removed on its own "
          "- level 1 must go back to ADMITTING the divergent build, or the "
          "row was never the thing refusing it: %s. Survivors (rows that "
          "refuse for some OTHER reason and so assert nothing): %s"
          % ("; ".join(rows), ", ".join(survivors) or "none"))


# The 18.9 km straight the kit-mismatch fallback was measured on.  It is not
# 300 m on purpose: the cost of a level-1-pass / level-2-refuse build is the
# DISCARDED NATIVE CHAIN, which scales with the build, so a ceiling asserted
# on a small fixture is a ceiling asserted where the cost is not.
GUARD_MISMATCH_M = 18900.0
GUARD_MISMATCH_CEILING = 1.30


def _named_kit(names):
    """A kit of `names`, each a plain rigid box, with no `default` role."""
    from polyfactory.polychain import kit as K
    geo = hou.Geometry()
    for i, name in enumerate(names):
        src = hou.Geometry()
        K.box_mesh(src, 0.0, 2.0, 0.0, 1.0, -0.05, 0.05, 1)
        K.add_module(geo, name, src, size=(2.0, 1.0, 0.1),
                     deform=0, zmode="adaptive", roles=name)
    K.write_manifest(geo, "pf_mismatch", 1, sources=("run_native_checks",),
                     human_scale_reference=1.8)
    return geo


def guard_kit_mismatch(root):
    """A rule naming a module the kit does not carry - the ORDINARY artist
    kit - used to be 2.35x SLOWER than having no native chain at all.

    ⚠️ THE PARAMETER PAGE'S SLOT DEFAULTS NAME THE STARTER KIT.  `slot_default`
    is "post panel", `slot_corner` is "corner_post".  Wire your own kit into
    input 2 and leave the slots alone - which is how a kit arrives - and every
    row of `_native_ok` passed: no surface, no fillet, and NO WARNING, because
    the parm face never validates the style against the kit (only
    `style.read` does, and only for a wired payload).  So level 1 admitted,
    the native chain planned every piece and built ZERO (`pc_place_valid`
    drops a piece whose module `pc_proto` could not resolve), level 2 refused
    on `planned != built`, and the reference cooked on top of the discarded
    work.

    Measured on the shipped asset before the fix, an 18.9 km straight with a
    two-module kit named `wall_a`/`wall_b`: `Stage = output` 1.507 s against
    `Stage = reference` 0.642 s - 2.35x, over `GUARD_FALLBACK_CEILING`'s 1.8x,
    with 852 ms of discarded native work (736 ms of it `pc_plan_solve`) and
    `node.warnings()` empty.  The identical kit renamed `post`/`panel` read
    0.97x.

    ⚠️ NO COMMITTED CHECK COULD REACH IT.  The 92 scene cases all use
    compatible kits, so `no_case_pays_the_guard_fallback` reads 0 of 92; and
    `GUARD_BEND_LADDER`'s two fallback rows are 300 m and 600 m fixtures
    measuring 1.21x/1.27x, because the cost of the fallback scales with the
    native chain and it had only ever been measured on tiny ones.

    `_native_ok` refuses the build now, with `style.read`'s own test
    (`kit.by_name(name) is None and not kit.by_role(name)`) so the parm face
    refuses exactly what the payload face already warns about.  Both halves
    are asserted: the refusal, and the RATIO at 18.9 km.
    """
    spline = guard_polyline_geo([(x, 0.0, 0.0) for x in
                                 range(0, int(GUARD_MISMATCH_M) + 1, 1)])
    kit = _named_kit(("wall_a", "wall_b"))
    tag = "kitmismatch"
    node = root.createNode("pf_polychain", "asset_%s" % tag)
    node.setInput(0, native.feed(root, spline, "KM_S"))
    node.setInput(1, native.feed(root, kit, "KM_K"))
    node.parm("stage").set("output")
    node.cook(force=True)
    node.allowEditingOfContents()
    level1 = int(node.node("pc_envelope").geometry()
                 .attribValue("_native_ok"))
    cooked = node.node("pc_plan_solve").cookCount() > 0

    # ⚠️ INTERLEAVED, AND WHAT MOVES IS A PARM.  D209's estimator: one
    # repetition sets `Stage = output`, cooks it, then sets `Stage =
    # reference` and cooks that, so a busy moment lands on both sides.  The
    # setup half - dirtying the node so the next cook is a real one - is
    # outside the stopwatch.
    # `setup` dirties through a parm EVERY stage reads, so neither side times
    # a cache hit (D164) - `cook(force=True)` on an unchanged node returns in
    # microseconds, which is how this row first read 1.04x on a 3 ms cook.
    # It is `output_guard_cost`'s own lever, and it is outside the timer.
    state = {"i": 0}

    def _make(stage):
        def setup():
            state["i"] += 1
            node.parm("stage").set(stage)
            node.parm("corner_angle_deg").set(30.0 + 0.01 * (state["i"] % 3))

        return (stage, setup, lambda: node.cook(force=True))

    for stage in ("reference", "output"):
        node.parm("stage").set(stage)
        node.cook(force=True)
    best = interleaved_best((_make("output"), _make("reference")))
    node.parm("corner_angle_deg").set(30.0)
    out_s, ref_s = best["output"], best["reference"]
    ratio = out_s / ref_s if ref_s > 0 else 0.0
    node.destroy()
    ok = (level1 == 0 and not cooked and ratio <= GUARD_MISMATCH_CEILING
          and ref_s >= GUARD_COST_FLOOR_S)
    check("guard_kit_mismatch", ok,
          "L1=%d, %.2fx" % (level1, ratio),
          "an %.1f km straight with a kit named `wall_a`/`wall_b` and the "
          "slot parms left at their starter-kit defaults. Level 1 must "
          "REFUSE (it read %d) and `pc_plan_solve` must never cook (it "
          "cooked: %s), because the native chain would plan every piece and "
          "build none. `Stage = output` %.3f s against `Stage = reference` "
          "%.3f s = %.2fx, ceiling %.2fx - it measured 2.35x before the "
          "refusal existed. The reference side must clear the %.0f ms floor "
          "(it read %.3f s) or the ratio is noise"
          % (GUARD_MISMATCH_M / 1000.0, level1, cooked, out_s, ref_s, ratio,
             GUARD_MISMATCH_CEILING, GUARD_COST_FLOOR_S * 1e3, ref_s))


# ⚠️ THE PARAMETERS LEVEL 1 CAN REFUSE ON.  Read off the built asset in
# `guard_refusal_list_is_true` rather than listed here, so a NEW parm that
# `_native_ok` starts testing is covered without anyone remembering to add it.
_VEX_KEYWORDS = frozenset((
    "int", "float", "string", "vector", "if", "else", "for", "while",
    "foreach", "return", "nprimitives", "npoints", "detail", "prim", "point",
))


def guard_refusal_list_is_true(node=None):
    """`pc_envelope.vfl`'s "WHAT LEVEL 1 REFUSES" list, checked against the
    code it describes - in BOTH directions.

    ⚠️ IT WENT STALE FOR A CYCLE AND NOTHING NOTICED.  PART B ported D91's Kit
    Padding into `config_resolved` and deleted the row from `_native_ok`; the
    header went on listing "a non-zero Kit Padding" among the things level 1
    refuses.  A reader auditing the guard reads that list - it is the only
    prose statement of the envelope there is - and concludes a padded build
    takes the reference.  It does not: `padding = 0.5` admits and
    `copy_packed` cooks.  D207 closed exactly this shape for the Stage menu
    ("text that makes a claim about the build is a CHECK, not a comment") and
    the guard's own header was left out of it.

    Each row of the list now carries a tag - `[cfg:<name>]` for something
    `hda._native_ok` tests, `[vex:<name>]` for a term of this file's
    `i@_native_ok` expression - and four things are asserted:

      1. every `[cfg:...]` tag appears in `_native_ok`'s source;
      2. every `[vex:...]` tag appears in the verdict expression;
      3. every PARAMETER NAME `_native_ok` reads has a `[cfg:]` row - so a
         refusal added without prose is red (this is the direction that would
         have caught the padding row being ADDED, and it is read off the
         asset's own parm list, not off a second hand-kept table);
      4. every identifier in the verdict expression has a `[vex:]` row - so a
         VEX refusal added without prose is red (and, conversely, a row whose
         term is DELETED goes red at 2).
    """
    import inspect
    src = inspect.getsource(H._native_ok)
    vfl = io.open(os.path.join(REPO, "polyfactory", "vex", "polychain",
                               "pc_envelope.vfl"), encoding="utf-8").read()
    cfg_tags = re.findall(r"\[cfg:([A-Za-z_][A-Za-z_0-9]*)\]", vfl)
    vex_tags = re.findall(r"\[vex:([A-Za-z_][A-Za-z_0-9]*)\]", vfl)
    expr = vfl[vfl.index("i@_native_ok = (") + len("i@_native_ok = ("):]
    expr = expr[:expr.index(");")]
    bad = []
    for tag in cfg_tags:
        if not re.search(r"\b%s\b" % re.escape(tag), src):
            bad.append("[cfg:%s] is not tested by `_native_ok`" % tag)
    for tag in vex_tags:
        if not re.search(r"\b%s\b" % re.escape(tag), expr):
            bad.append("[vex:%s] is not read by the verdict expression" % tag)
    # 3 - every parm the asset exposes that `_native_ok` reads must be listed
    parms = set()
    if node is not None:
        parms = set(p.name() for p in node.parms())
    unlisted = sorted(p for p in parms
                      if re.search(r"[\"']%s[\"']" % re.escape(p), src)
                      and p not in cfg_tags)
    bad += ["`_native_ok` refuses on the %r parm and no row says so" % p
            for p in unlisted]
    # 4 - every term of the verdict expression must be listed
    terms = set(t for t in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", expr)
                if t not in _VEX_KEYWORDS and not t.startswith("_native_ok"))
    untagged = sorted(t for t in terms if t not in vex_tags)
    bad += ["the verdict reads %r and no row says so" % t for t in untagged]
    check("guard_refusal_list_is_true", not bad,
          "%d cfg / %d vex rows" % (len(cfg_tags), len(vex_tags)),
          "`pc_envelope.vfl`'s WHAT LEVEL 1 REFUSES list against "
          "`_native_ok`'s source and against this file's own verdict "
          "expression, both directions. Rows: %s | %s. Complaints: %s"
          % (", ".join(cfg_tags), ", ".join(vex_tags),
             "; ".join(bad[:4]) or "the list is true"))


# The double cook a level-1 pass / level-2 refusal costs, measured on the
# 2 km and 20 km ripples §19.4 says nearly shipped.  1.8x is the ceiling and
# it measures 1.52x / 1.57x.
GUARD_FALLBACK_CEILING = 1.8


def bench_guard_fallback(root):
    """What the guard's LEVEL-1-PASS / LEVEL-2-REFUSE path costs.

    ⚠️ THIS CHECK IS WRITTEN BECAUSE TWO SOURCE COMMENTS CITED IT BY NAME AND
    IT DID NOT EXIST.  `pc_envelope.vfl` and `create_pf_polychain_hda.py` both
    said `bench_guard_fallback` "measures that rather than assuming it away",
    and nothing in the repo did: `output_guard_cost`'s four shapes are all
    either refused at level 1 or admitted through level 2, so no committed
    check exercised the fallback at all.

    ⚠️ AND THE FALLBACK PATH IS REACHABLE, which is a correction to what this
    docstring said for a cycle.  It claimed "on the shipped build there is no
    legitimate input that passes level 1 and fails level 2 ... and it is the
    reason the guard is free today".  That was true of the UPPER-bound level 1
    it was written against and false the moment PART B made the bound a LOWER
    one: `GUARD_BEND_LADDER`'s `arc_R20_step0.05` and `arc_R50_step0.1` rows
    are exactly such inputs (want1=True, want2=False), reproduced here at
    R = 20 m / 500 m - L1=1, L2=0, 292 ms of which 224 ms is `kernel` and
    25 ms is discarded native work.  `guard_bend_bound` is the check that pins
    WHICH shapes pay; this one pins what it costs.

    The fixture still FORCES level 1 open rather than using an arc, and that
    is a choice about size rather than about reachability: the cost of the
    double cook scales with the native chain, so it is measured on a 2 km and
    a 20 km ripple - shapes big enough for the ratio to mean something -
    rather than on the ladder's 500 m arcs, which read 1.21-1.27x.
    """
    rows, bad = [], []
    for label, npts in (("ripple_2km", 2001), ("ripple_20km", 20001)):
        geo = hou.Geometry()
        cases.polyline(geo, [(1.0 * i, 0.6 * math.sin(i * 0.35), 0.0)
                             for i in range(npts)], curve_id="GF")
        node = root.createNode("pf_polychain", "fallback_" + label)
        node.setInput(0, native.feed(root, geo, "GF_" + label))
        node.parm("stage").set("output")
        node.cook(force=True)
        node.allowEditingOfContents()
        env = node.node("pc_envelope")
        env.parm("snippet").set(env.parm("snippet").eval()
                                + "\ni@_native_ok = (nprimitives(0) > 0);\n")
        best = {}
        for stage in ("reference", "output"):
            node.parm("stage").set(stage)
            node.cook(force=True)
            for i in range(3):
                # dirtied through a parm every stage reads (D164)
                node.parm("corner_angle_deg").set(30.0 + 0.01 * (i + 1))
                t0 = time.time()
                node.cook(force=True)
                dt = time.time() - t0
                best[stage] = dt if stage not in best else min(best[stage], dt)
            node.parm("corner_angle_deg").set(30.0)
        node.parm("stage").set("output")
        node.cook(force=True)
        level1 = int(node.node("pc_envelope").geometry()
                     .attribValue("_native_ok"))
        level2 = int(node.node("pc_envelope2").geometry()
                     .attribValue("_native_ok2"))
        ratio = best["output"] / max(best["reference"], 1e-9)
        rows.append((label, ratio, level1, level2))
        if not (level1 == 1 and level2 == 0):
            bad.append("%s: L1=%d L2=%d - this is not the fallback path"
                       % (label, level1, level2))
        if ratio > GUARD_FALLBACK_CEILING:
            bad.append("%s: %.2fx over %.2fx (%.4f s vs %.4f s)"
                       % (label, ratio, GUARD_FALLBACK_CEILING,
                          best["output"], best["reference"]))
        node.destroy()
    check("bench_guard_fallback", not bad,
          "; ".join("%s %.2fx" % (r[0], r[1]) for r in rows),
          "level 1 forced open on a rippled run, so the native chain cooks, "
          "level 2 refuses it and the reference cooks too - the double cook, "
          "measured rather than assumed. Ceiling %.1fx. %s"
          % (GUARD_FALLBACK_CEILING, "; ".join(bad) or "the ceiling holds"))


def native_reach(root):
    """WHO cooks on `Stage = output` now - and it is the ladder this cycle
    had to climb.

    ⚠️ THIS CHECK USED TO ASSERT THE OPPOSITE, AND ITS OWN COMMENT SAID WHEN
    TO EDIT IT: "the day 13.9 N10 retires `kernel`, this check has to be
    edited on the same commit".  Until this commit the answer was "none of
    them" - the solve and the packed branch were at parity behind a Stage menu
    nobody sets, which is why 18.2 measured the shipped default at 88-95 %
    Python.  The guard switch changes that, and what has to be asserted
    changes with it: not that the native chain is idle, but that it runs on a
    build inside the envelope AND THAT `kernel` DOES NOT.

    Both directions, because either one alone is satisfiable by an accident:
    a guard that always chose the reference would pass the second half, and a
    guard that always chose the native chain would pass the first.
    """
    watched = ("pc_sections", "pc_plan_solve", "pc_plan_emit", "pc_proto",
               "pc_deform_gate", "pc_frames_native", "copy_packed",
               "pc_warn_collate")
    shapes = (("inside", [(0.0, 0.0, 0.0), (9.0, 0.0, 0.0), (18.0, 0.0, 0.0)],
               True),
              # a 90 degree corner: 4.3 is N8, so level 1 refuses outright
              ("corner", [(0.0, 0.0, 0.0), (9.0, 0.0, 0.0), (9.0, 0.0, 7.0)],
               False))
    rows = []
    bad = []
    for label, pts, want_native in shapes:
        geo = hou.Geometry()
        cases.polyline(geo, pts, curve_id="R")
        node = root.createNode("pf_polychain", "reach_" + label)
        node.setInput(0, native.feed(root, geo, "REACH_" + label))
        node.allowEditingOfContents()
        node.parm("stage").set("output")
        node.cook(force=True)
        before = dict((c.name(), c.cookCount()) for c in node.children())
        # a real re-cook of the Output stage, forced through a parm every
        # stage reads
        node.parm("corner_angle_deg").set(31.0)
        node.cook(force=True)
        cooked = set(n for n, c in ((c.name(), c) for c in node.children())
                     if c.cookCount() > before[n])
        native_cooked = sorted(n for n in watched if n in cooked)
        kernel_cooked = "kernel" in cooked
        rows.append((label, len(native_cooked), kernel_cooked))
        if want_native:
            if len(native_cooked) != len(watched):
                bad.append("%s: only %s ran" % (label, native_cooked))
            if kernel_cooked:
                bad.append("%s: the PYTHON kernel cooked anyway" % label)
        else:
            if native_cooked:
                bad.append("%s: the native chain cooked for a build the "
                           "guard refused (%s)" % (label, native_cooked))
            if not kernel_cooked:
                bad.append("%s: nothing built it" % label)
        node.destroy()
    check("output_runs_the_native_chain_inside_the_envelope", not bad,
          "; ".join("%s %d/%d native, kernel %s"
                    % (r[0], r[1], len(watched), "yes" if r[2] else "no")
                    for r in rows),
          "13.9 N10: on a build inside the envelope `Stage = output` cooks "
          "all %d native nodes and NOT `kernel`; on one outside it cooks "
          "`kernel` and NONE of them - which is also what keeps the guard "
          "cheap, since a switch cooks only the input it selected. %s"
          % (len(watched), "; ".join(bad) or "both directions hold"))


# --- D206: EVERY WRANGLE GETS A MEASURED CEILING, NOT THE FOUR THAT HAPPENED
#           TO BE CAUGHT ------------------------------------------------------
#
# §21.4's SURVIVOR 1, reproduced at SOURCE this cycle: `pc_finalize.vfl`
# rewritten as a single-threaded detail loop over the prims, `native.py`'s
# class moved `primitive` -> `detail` with it, and the .hda REBUILT (md5
# 37f1e344 -> 6f2fec2e).  The fence is value-for-value identical and
#
#     run_native_checks   106 [PASS] / 0        exit 0
#     run_scene_checks    0 failing / 0 moved   exit 0
#     run_hda_checks      0 failing             exit 0
#
# while the node measures 2.13 -> 13.15 ms at 17 804 pieces (0.114 -> 0.738
# us/piece, 6.2x).  Nothing in the suite could see it, because the per-node
# ceilings D193 and D204 landed cover `pc_plan_emit`, `pc_stamp`,
# `pc_plan_solve` and `pc_frames_native` - FOUR of the eighteen wrangles - and
# §14's "batching beats language by ~55x" is the law all eighteen obey.
#
# THE INSTRUMENT is `hou.perfMon` per-node cook time on the SHIPPED ASSET -
# §21.2's second instrument, not a stopwatch around a rig subnet.  The column
# read is `Cook - ms`, which is INCLUSIVE of the wrangle's `attribvop` child;
# that child is where the VEX time actually lands (a probe measured a wrangle
# at 0.166 ms self against 234.7 ms in its child), so reading self time would
# measure nothing at all.
#
# ⚠️ THE TABLE IS RECORDED FROM AN UNLOCKED INSTANCE, and that was checked
# rather than assumed, because the mutation levers below need
# `allowEditingOfContents`.  Locked and unlocked measure the same node: 13.459
# / 13.490 ms on `pc_arclength`, 2.159 / 2.132 on `pc_finalize`, 497.2 / 484.0
# on `pc_plan_solve`.  What unlocking costs is scene size, which is
# `instances_do_not_fork_the_network`'s business and not this one's.
#
# THREE DIRTYING LEVERS, because no single one reaches all eighteen, and the
# per-node lever is DERIVED (the lever the node's own minimum came from)
# rather than hand-tabled:
#   spline   input 0 nudged  - the sixteen on the default output path;
#   kit      input 1 nudged  - `pc_kit_id`, which hangs off the KIT;
#   frames   Stage = frames  - `pc_frames`, the dead Python-bridge branch
#                              that `Stage = output` never cooks.
#
# MEASURED ON THIS BUILD, the minimum over five independent runs of three
# interleaved repetitions x three levers, at 4 454 and 17 804 pieces (a 4.7 km
# and an 18.9 km straight at 2 m spacing):
#
# ⚠️ RE-RECORDED, AND THE GROWTH COLUMN IS A SPREAD RATHER THAN A NUMBER.
# The table below used to be one run, and it was measured with the two sizes
# in two SEPARATE BLOCKS - the small rig built, measured and destroyed, then
# the big one built and measured - which is D209's defect inside the check
# that closed D206.  The growth ratio's two sides never saw the same machine,
# `wrangle_cost_is_flat_in_piece_count` failed on an UNMUTATED build
# (`pc_plan_solve growth 1.85x`), and six measurements of that sound build
# read 0.97 / 1.14 / 1.15 / 1.40 / 1.69 / 1.85 against a recorded "1.05x".
# `wrangle_cost_tables` interleaves the SIZES now; six independent runs of the
# interleaved estimator read pc_plan_solve growth 1.10 / 1.10 / 1.15 / 1.17 /
# 1.18 / 1.09, and its big-size cook 470-507 ms where the old estimator swung
# 482-818.  The numbers below are the range over those six runs.
#
#   node               big us/p (6 runs)      growth (6 runs)   big ms
#   pc_arclength         0.7560 - 0.7817       1.04 - 1.14      13.5-13.9
#   pc_corners           0.0215 - 0.0247       0.25 - 0.30       0.38-0.44
#   pc_curve_index       0.0080 - 0.0090       0.30 - 0.36       0.14-0.16
#   pc_curveid           0.0187 - 0.0217       0.50 - 0.60       0.33-0.39
#   pc_deform_gate       0.2355 - 0.2533       0.26 - 0.27       4.19-4.51
#   pc_envelope          0.4697 - 0.4960       0.92 - 0.96       8.36-8.83
#   pc_envelope2         0.0772 - 0.0891       0.71 - 0.87       1.37-1.59
#   pc_finalize          0.1119 - 0.1206       0.67 - 0.78       1.99-2.15
#   pc_frames            0.1970 - 0.2351       0.33 - 0.40       3.51-4.18
#   pc_frames_native     0.1486 - 0.1756       0.33 - 0.39       2.65-3.13
#   pc_kit_id            0.0091 - 0.0104       0.22 - 0.30       0.16-0.18
#   pc_markers           0.0111 - 0.0129       0.31 - 0.41       0.20-0.23
#   pc_plan_emit         2.5904 - 2.7142       0.91 - 0.96      46.1-48.3
#   pc_plan_solve       26.4171 - 28.4861      1.09 - 1.18       470-507
#   pc_proto             0.1048 - 0.1195       0.37 - 0.45       1.86-2.13
#   pc_sections          0.2506 - 0.3162       0.79 - 1.04       4.46-5.63
#   pc_stamp             0.4348 - 0.4525       0.22 - 0.24       7.74-8.06
#   pc_warn_collate      0.2358 - 0.2490       0.73 - 0.79       4.20-4.43
#
# THE CEILING IS THE BIG-SIZE RATE x 2.5 PLUS ONE MILLISECOND EXPRESSED PER
# PIECE, so a node whose whole cook is 0.16 ms is not judged on a coin toss -
# D209's lesson applied before the fact rather than after.  It is judged at
# the BIG size ONLY: five of these nodes are dominated by a FIXED cost at
# 4 454 pieces (`pc_corners` is 0.39 ms at BOTH sizes), so one per-piece
# ceiling cannot be right at both.  What the small size is for is the GROWTH
# ratio, which is scale-free and is the shape that catches the quadratic
# regressions - D175's `pointgenerate` expander read 3 860 us/piece where the
# node that replaced it reads 2.6.
#
# ⚠️ 2.5x IS DELIBERATELY TIGHT AND `wrangle_ceilings_are_tight` HOLDS IT
# THERE.  A ceiling is worth exactly what it refuses, so no row may sit more
# than 4x above what the run in front of it measures: the table cannot be
# quietly loosened into a number nothing can cross, and a real 40 % speedup
# (which is what §21.10 asks for on `pc_plan_solve`) FAILS this check until
# the table is re-recorded, which is the intended behaviour and not a bug.
WRANGLE_CEILING_US = {
    "pc_arclength":     1.95,
    "pc_corners":       0.115,
    "pc_curve_index":   0.078,
    "pc_curveid":       0.105,
    "pc_deform_gate":   0.67,
    "pc_envelope":      1.28,
    "pc_envelope2":     0.25,
    "pc_finalize":      0.35,
    "pc_frames":        0.57,
    "pc_frames_native": 0.44,
    "pc_kit_id":        0.08,
    "pc_markers":       0.085,
    "pc_plan_emit":     6.55,
    "pc_plan_solve":   66.50,
    "pc_proto":         0.32,
    "pc_sections":      0.65,
    "pc_stamp":         1.15,
    "pc_warn_collate":  0.56,
}
# The widest growth this build shows over SIX interleaved runs is
# `pc_plan_solve`'s 1.18x (see the spread above - it is a range, not a number,
# and quoting a single run's value here is what made this ceiling look tighter
# than it is).  1.6x leaves 36 % over the widest observation for cache and
# thread start-up, and a quadratic node blows it by three orders of magnitude
# across these two sizes.
WRANGLE_GROWTH_CEILING = 1.6
# The noise floor, in MILLISECONDS, expressed per piece when the ceiling is
# built.  A node whose entire cook is a fifth of a millisecond cannot carry a
# tight per-piece ratio on a shared machine.
WRANGLE_FLOOR_MS = 1.0
# ...and how far a ceiling may sit above the measurement it is recorded from
# before it stops refusing anything.  2.5x is the recipe; 4.0x is the refusal.
WRANGLE_HEADROOM = 4.0
# The two sizes.  Points at 2 m spacing; the piece counts they produce are
# 4 454 and 17 804.
WRANGLE_SMALL_PTS = 2361
WRANGLE_BIG_PTS = 9436

# §21.4's M3, verbatim: `pc_finalize` as a DETAIL wrangle looping over the
# prims on one thread, writing the SAME values element for element.  The
# output is identical - `place_stamp_parity` and every other parity check stay
# green under it, which is precisely why a COST ceiling is the only thing that
# can see it.
FINALIZE_DEBATCHED = """
dict cfg = detail(1, "pc_cfg");
string style_id = "";
if (isvalidindex(cfg, "style_id")) { string v = cfg["style_id"]; style_id = v; }
int nprim = nprimitives(0);
for (int i = 0; i < nprim; i++) {
    int sec = prim(0, "_sec_out", i);
    setprimattrib(0, "pc_section",    i, sec);
    setprimattrib(0, "pc_generated",  i, 1);
    setprimattrib(0, "pc_deformed",   i, 0);
    setprimattrib(0, "pc_corner_cut", i, 0);
    setprimattrib(0, "pc_replaced",   i, 0);
    setprimattrib(0, "pc_style",      i, style_id);
}
"""

# The regression each row of the table has to refuse, as a multiple of what
# this run measured.  It is 5x and not 2x because `wrangle_ceilings_are_tight`
# holds every ceiling at or under 4x the measurement: 5x therefore crosses
# EVERY ceiling in the table by construction, and the two checks together say
# "a five-fold regression on any one of the eighteen is caught", which is the
# sentence D206 asks for.
WRANGLE_MUTATION_SCALE = 5.0

# ⚠️ A PHYSICAL BURN WAS BUILT FIRST AND IT IS NOT HERE, WHICH IS THE POINT.
# The obvious way to "prove each of the eighteen reddens" is to append a
# workload to each wrangle in turn and watch it cross its ceiling.  That was
# written and measured, and on ONE machine, in ONE process, it read 18/18 on
# the first pass and 11/18 on the second and third - identical build,
# identical ceilings, `pc_deform_gate` swinging 6.94 -> 0.43 us/piece.  The
# cause is that a loop whose body does not depend on the element is
# loop-invariant, so VEX hoists it out and the "total" workload collapses by
# the thread count; making it element-dependent instead needs a per-node
# iteration budget, because a DETAIL wrangle and a 17 804-element POINT
# wrangle are sixteen times apart on the same count.
#
# A mutation check that reddens on a SOUND build is D209's defect wearing
# D206's hat, and shipping one while closing D209 in the same cycle would be
# absurd.  So the per-node proof is DETERMINISTIC: `wrangle_verdict` is a pure
# function of the measured rates, and the mutation scales one row at a time
# and asserts the verdict names it.  The one PHYSICAL mutation kept is
# §21.4's own M3 on `pc_finalize`, which is what the finding is about and
# which measured 0.82-1.42 us/piece against a 0.35 ceiling across five runs.
#
# ⚠️ AND ONE LEVER THAT DOES NOT WORK, recorded so it is not re-tried: setting
# `vex_threadjobsize` to 1e9 - one job, one thread, which looks like the
# perfect generic de-batching - moves these nodes by 10-25 % and NOTHING
# crosses its ceiling.  They are not thread-bound, which is itself worth
# knowing: M3's 6.2x is the cost of `prim()` / `setprimattrib` random access
# in a loop, not the cost of losing fifteen cores.


# ⚠️ AND THE ROWS THE ARITHMETIC MUTATION CANNOT SEE GET A PHYSICAL ONE.
#
# The comment above records that a physical burn was built and abandoned
# because it read 18/18 on one pass and 11/18 on the next: the burn was
# LOOP-INVARIANT, so VEX hoisted it and the workload collapsed by the thread
# count.  Making the body depend on the ELEMENT removes the hoist, and it is
# then deterministic - the auditor of §23 measured `pc_arclength` 18.8 -> 79.4
# ms, `pc_plan_solve` 818 -> 1836, `pc_frames_native` 3.8 -> 115,
# `pc_deform_gate` 5.1 -> 170, `pc_sections` 8.8 -> 86, `pc_envelope` 11.6 ->
# 53 and `pc_stamp` 8.5 -> 48 on seven of seven tries.  The accumulator is
# also loop-CARRIED, so the inner iterations cannot be hoisted either.
#
# It is used only for the rows the 5x arithmetic mutation lands under the
# noise floor on - five of eighteen on this build, all of them nodes whose
# whole cook is a fifth of a millisecond - because it is the expensive proof
# and the cheap one covers the other thirteen.  Together they say: EVERY row
# of the table refuses a regression, thirteen of them provably at 5x and five
# of them provably at all.
WRANGLE_BURN_ITERS = {"detail": 400000, "primitive": 900, "point": 900}
WRANGLE_BURN_ELEM = {"detail": "nprimitives(0)", "primitive": "@primnum",
                     "point": "@ptnum"}
WRANGLE_BURN = (
    "\n// a burn whose body depends on the ELEMENT and on its own\n"
    "// accumulator, so neither VEX's hoist nor its unroller can remove it\n"
    "if (1) {\n"
    "    float _burn = 0.0;\n"
    "    for (int _k = 0; _k < %d; _k++)\n"
    "        _burn += sin(_burn + (float)%s * 0.0013 + (float)_k);\n"
    "    if (_burn > 1e30) printf(\"never\");\n"
    "}\n")
# The `class` parm's own order, probed rather than recalled: 0 detail,
# 1 primitive, 2 point, 3 vertex.
WRANGLE_CLASS = {0: "detail", 1: "primitive", 2: "point", 3: "vertex"}


def _wrangle_rig(root, tag, npts):
    """The SHIPPED asset on a straight run, with a nudge on each input.

    Unlocked, because the mutation levers below have to reach a node inside
    it; `instances_do_not_fork_the_network` is what guards the shipped
    default, and the comment above records that locked and unlocked measure
    the same node.
    """
    from polyfactory.polychain import kit as KIT

    geo = hou.Geometry()
    cases.polyline(geo, [(2.0 * i, 0.0, 0.0) for i in range(npts)],
                   curve_id="LONG")

    def nudger(name, feeder):
        node = root.createNode("attribwrangle", "%s_%s" % (name, tag))
        node.parm("class").set(2)
        group = node.parmTemplateGroup()
        group.append(hou.IntParmTemplate("nudge", "Nudge", 1))
        node.setParmTemplateGroup(group)
        node.parm("snippet").set('i@_%s = chi("nudge");' % name)
        node.setInput(0, feeder)
        return node

    node = root.createNode("pf_polychain", "wcost_%s" % tag)
    spline = nudger("wsp", native.feed(root, geo, "WSP_%s" % tag))
    kit = nudger("wkt", native.feed(root, KIT.starter_kit(), "WKT_%s" % tag))
    node.setInput(0, spline)
    node.setInput(1, kit)
    node.allowEditingOfContents()
    node.node("OUT")
    node.parm("stage").set("output")
    node.cook(force=True)
    return node, spline, kit, len(node.geometry().prims())


def _wrangle_cook(node, dirt, nudge, stage):
    """One PROFILED cook -> {child node name: `Cook - ms`}.

    The CSV's `Cook - ms` is inclusive of the node's `attribvop` child, which
    is where a wrangle's VEX time lives; its self time is ~0.02 ms and would
    measure nothing.
    """
    csv = os.path.join(os.path.dirname(HDA_PATH), "_d206_perf.csv")
    node.parm("stage").set(stage)
    dirt.parm("nudge").set(nudge)
    profile = hou.perfMon.startProfile("d206")
    try:
        node.cook()
    finally:
        profile.stop()
    profile.exportAsCSV(csv)
    out = {}
    with io.open(csv, encoding="utf-8") as fh:
        for line in fh:
            field = [c.strip() for c in line.split(",")]
            if len(field) < 9 or "/wcost_" not in field[0]:
                continue
            try:
                out[field[0].rsplit("/", 1)[1]] = float(field[7])
            except ValueError:
                pass
    os.remove(csv)
    return out


def wrangle_cost_tables(rigs, reps=3):
    """Per-node MINIMUM cook time over `reps` x three levers, for EVERY rig,
    with the rigs INTERLEAVED.

    ⚠️ THE TWO SIZES USED TO BE MEASURED IN TWO SEPARATE BLOCKS, WHICH IS
    D209's DEFECT INSIDE THE CHECK THAT CLOSED D206.  The small rig was built,
    measured over nine cooks and DESTROYED, and only then was the big rig
    built and measured - so the two sides of the growth ratio never saw the
    same machine, and a busy moment during one block landed entirely on one
    side.  `wrangle_cost_is_flat_in_piece_count` failed on an UNMUTATED build
    because of it (`pc_plan_solve growth 1.85x` against a 1.6 ceiling, run 0
    of three in one process), and six independent measurements of the same
    sound build read growth 0.97 / 1.14 / 1.15 / 1.40 / 1.69 / 1.85 while the
    recorded table claimed "the widest growth this build shows is
    `pc_plan_solve`'s 1.05x".

    `interleaved_best`'s own two properties, applied to the SIZE axis: within
    one repetition every rig sees the same machine, and the minimum is taken
    because interference can only make a pass slower.  The rigs must therefore
    all exist before the first measurement, which is why the caller builds
    both and destroys neither until the end.

    It also DERIVES the lever - whichever one a node's minimum came from - so
    the mutation pass below needs no hand-maintained table of which input
    dirties which node.

    `rigs` is [(base, node, spline, kit)].
    -> [({name: ms}, {name: (nudge node, stage)})], one per rig, in order.
    """
    out = [({}, {}) for _r in rigs]
    for rep in range(reps):
        for index, (base, node, spline, kit) in enumerate(rigs):
            best, lever = out[index]
            for tag, dirt, stage in (("spline", spline, "output"),
                                     ("kit", kit, "output"),
                                     ("frames", spline, "frames")):
                got = _wrangle_cook(node, dirt,
                                    base + rep * 10 + len(tag), stage)
                for name, ms in got.items():
                    if name not in best or ms < best[name]:
                        best[name] = ms
                        lever[name] = (dirt, stage)
    return out


def wrangle_verdict(big, small, pieces, small_pieces):
    """Every complaint the measured rates raise, as text.  PURE - no Houdini.

    It is a separate function for the same reason `run_scene_checks.exit_code`
    is (D210): a rule that can only be exercised by cooking a 20 km fence is a
    rule nobody can mutate, and D206's own mandate is that every row of the
    table refuses something.  Here one row can be scaled and the verdict
    re-asked in microseconds.

    -> (rows, over, unmeasured, loose) where `rows` is [(name, us/piece,
    growth)] and the other three are lists of complaint strings; a sound build
    raises none.
    """
    floor_us = WRANGLE_FLOOR_MS * 1e3 / pieces
    rows, over, unmeasured, loose = [], [], [], []
    for name in sorted(WRANGLE_CEILING_US):
        if name not in big or name not in small:
            unmeasured.append(name)
            continue
        rate = big[name] * 1e3 / pieces
        rate_small = small[name] * 1e3 / small_pieces
        growth = rate / max(rate_small, 1e-12)
        ceiling = WRANGLE_CEILING_US[name]
        rows.append((name, rate, growth))
        if rate > ceiling:
            over.append("%s %.4f > %.4f us/piece" % (name, rate, ceiling))
        if growth > WRANGLE_GROWTH_CEILING:
            over.append("%s growth %.2fx" % (name, growth))
        if ceiling > WRANGLE_HEADROOM * rate + 2.0 * floor_us:
            loose.append("%s %.4f is %.1fx the measured %.4f"
                         % (name, ceiling, ceiling / max(rate, 1e-12), rate))
    return rows, over, unmeasured, loose


def wrangle_cost_check(root):
    """D206 - one generic ceiling over every wrangle in the shipped asset.

    Five assertions, and each closes a different way for the table to become
    decoration:

      * `every_wrangle_has_a_cost_ceiling` - the table's keys ARE the asset's
        attribwrangles, read off the built network. A nineteenth wrangle added
        without a ceiling fails here rather than shipping unwatched, which is
        exactly how fourteen of the eighteen got here.
      * `wrangle_cost_is_flat_in_piece_count` - every row under its ceiling at
        17 804 pieces and under the growth ceiling between the two sizes.
      * `wrangle_ceilings_are_tight` - no row more than 4x above what this run
        measures, so the table cannot be loosened into a number nothing can
        reach.
      * `mutation_every_wrangle_ceiling_bites` - each of the eighteen rows is
        scaled by 5 in turn and the verdict has to name it. With the row above
        holding every ceiling at or under 4x, the pair says: a five-fold
        regression on ANY of the eighteen is caught.
      * `mutation_pc_finalize_debatched` - and the real one, §21.4's M3, on the
        node the whole finding is about.
    """
    # ⚠️ BOTH RIGS ARE BUILT BEFORE EITHER IS MEASURED.  See
    # `wrangle_cost_tables` - measuring them in two blocks was D209's defect
    # living inside D206's own check, and it failed on a sound build.
    small_node, small_sp, small_kt, small_pieces = _wrangle_rig(
        root, "small", WRANGLE_SMALL_PTS)
    node, spline, kit, pieces = _wrangle_rig(root, "big", WRANGLE_BIG_PTS)
    (small, _lev), (big, lever) = wrangle_cost_tables(
        ((100, small_node, small_sp, small_kt),
         (300, node, spline, kit)))
    small_node.destroy()

    wrangles = sorted(n.name() for n in node.children()
                      if n.type().name() == "attribwrangle")
    missing = [n for n in wrangles if n not in WRANGLE_CEILING_US]
    stale = [n for n in WRANGLE_CEILING_US if n not in wrangles]
    check("every_wrangle_has_a_cost_ceiling",
          not missing and not stale and len(wrangles) == 18,
          "%d wrangles / %d ceilings" % (len(wrangles),
                                         len(WRANGLE_CEILING_US)),
          "every `attribwrangle` in the shipped asset has a MEASURED "
          "per-piece ceiling (D206 - four of eighteen did). No ceiling: %s. "
          "No node: %s" % (missing or "none", stale or "none"))

    floor_us = WRANGLE_FLOOR_MS * 1e3 / pieces
    rows, over, unmeasured, loose = wrangle_verdict(
        big, small, pieces, small_pieces)
    worst = max(rows or [("none", 0.0, 0.0)],
                key=lambda r: r[1] / WRANGLE_CEILING_US.get(r[0], 1.0))
    check("wrangle_cost_is_flat_in_piece_count",
          bool(rows) and not over and not unmeasured,
          "%d rows, worst %s at %.0f%% of its ceiling"
          % (len(rows), worst[0],
             100.0 * worst[1] / WRANGLE_CEILING_US.get(worst[0], 1.0)),
          "all %d wrangles of the SHIPPED asset under a per-piece ceiling at "
          "%d pieces and under %.1fx growth from %d, perfMon `Cook - ms`, min "
          "over 3 interleaved repetitions x 3 levers. Over: %s. Never cooked: "
          "%s" % (len(rows), pieces, WRANGLE_GROWTH_CEILING, small_pieces,
                  over or "none", unmeasured or "none"))
    # ⚠️ THE VALUE IS THE FLOOR-ADJUSTED FRACTION, NOT THE BARE RATIO. A bare
    # ratio reads 9.4x on `pc_kit_id` - whose whole cook is 0.16 ms, so its
    # ceiling is the 1 ms noise floor and nothing else - and a reader would
    # take that for a failure the check declined to make. What is asserted is
    # the ceiling against its ALLOWANCE, and 100 % is the refusal.
    check("wrangle_ceilings_are_tight", bool(rows) and not loose,
          "worst %.0f%% of its allowance"
          % (100.0 * max([WRANGLE_CEILING_US[n]
                          / (WRANGLE_HEADROOM * max(r, 1e-12) + 2.0 * floor_us)
                          for n, r, _g in rows] or [0.0])),
          "no ceiling sits more than %.1fx above what this run measures (plus "
          "twice the %.0f ms noise floor), so the table cannot be loosened "
          "into decoration. Loose: %s"
          % (WRANGLE_HEADROOM, WRANGLE_FLOOR_MS, loose or "none"))

    # --- the mutation pass: each of the eighteen rows, one at a time --------
    #
    # ⚠️ THE EXEMPTION IS DERIVED, NOT LISTED, and it is the honest half of the
    # noise floor.  A node whose entire cook is 0.16 ms cannot be guarded to
    # five per cent on a shared machine, so its ceiling is the 1 ms floor and
    # a 5x regression on it - 0.65 ms - is genuinely below what this
    # instrument can see.  A hand-written exemption list would rot; this one
    # is computed from the floor the ceiling was built with, so a node that
    # grows out of the floor stops being exempt by itself.  Every exempt row
    # is still required to be REACHED by the verdict at its own ceiling, which
    # is what catches a row silently skipped.
    survived, blind = [], []
    for name in sorted(WRANGLE_CEILING_US):
        if name not in big:
            survived.append("%s (never cooked)" % name)
            continue
        rate = big[name] * 1e3 / pieces
        ceiling = WRANGLE_CEILING_US[name]

        def _named(ms, small_ms=None):
            """The verdict on a table where this ONE row is `ms`.

            ⚠️ BOTH SIZES MOVE, AND THAT IS THE FIX.  The mutation used to
            scale `big[name]` alone, which multiplies that row's GROWTH by 5
            and trips `WRANGLE_GROWTH_CEILING` almost regardless of the
            per-piece ceiling - so most rows were being caught by the growth
            term rather than by the ceiling the check claims to prove.  A real
            de-batching or algorithmic regression slows BOTH sizes and leaves
            growth unchanged; measured with 5x applied to both,
            `pc_curve_index`, `pc_kit_id` and `pc_markers` survived entirely
            (their sound growth is ~0.3, so even 5x reads 1.5 < 1.6) and
            `pc_curveid` and `pc_corners` cleared their ceilings by 1.3 % and
            3.6 % - margins inside the measurement spread.  The check reported
            "15/18 at 5x, 3 under the floor" and PASSED.
            """
            worse, worse_small = dict(big), dict(small)
            worse[name] = ms
            if small_ms is not None:
                worse_small[name] = small_ms
            _r, over_m, _u, _l = wrangle_verdict(
                worse, worse_small, pieces, small_pieces)
            return any(c.startswith(name + " ") for c in over_m)

        # ...and the row has to be REACHED at all, exempt or not.
        if not _named(ceiling * pieces * 1.01e-3,
                      small_ms=small.get(name)):
            survived.append("%s (not reached even at its own ceiling)" % name)
            continue
        if _named(big[name] * WRANGLE_MUTATION_SCALE,
                  small_ms=small[name] * WRANGLE_MUTATION_SCALE):
            continue
        slip = (WRANGLE_MUTATION_SCALE - 1.0) * rate * pieces * 1e-3
        if slip >= 2.0 * WRANGLE_FLOOR_MS:
            survived.append("%s (%.4f us/piece at %.0fx, ceiling %.4f, "
                            "+%.2f ms)"
                            % (name, rate * WRANGLE_MUTATION_SCALE,
                               WRANGLE_MUTATION_SCALE, ceiling, slip))
        else:
            blind.append("%s +%.2f ms" % (name, slip))
    # ⚠️ AND `blind` USED TO LEAVE THE VERDICT ENTIRELY, which is the other
    # half of the same finding: with only `survived` asserted, this row would
    # print PASS at "0/18 at 5x, 18 under the floor" if the instrument ever
    # read low across the board.  Every blind row now has to be reddened
    # PHYSICALLY - the burn above, appended to that wrangle's own snippet -
    # so a row that the arithmetic mutation cannot see is proved by the one
    # thing that is not arithmetic.
    burned, burn_rows = [], []
    for entry in list(blind):
        name = entry.split()[0]
        target = node.node(name)
        cls = WRANGLE_CLASS.get(int(target.parm("class").eval()), "point")
        sound_src = target.parm("snippet").eval()
        target.parm("snippet").set(
            sound_src + WRANGLE_BURN % (WRANGLE_BURN_ITERS[cls],
                                        WRANGLE_BURN_ELEM[cls]))
        dirt, stage = lever[name]
        got = _wrangle_cook(node, dirt, 900 + len(burn_rows), stage)
        target.parm("snippet").set(sound_src)
        ms = got.get(name)
        # the PER-PIECE CEILING alone, deliberately - the growth term cannot
        # help here, because the burn is applied at the big size only and the
        # whole point of this pass is that the ceiling refuses on its own.
        seen = (ms is not None
                and ms * 1e3 / pieces > WRANGLE_CEILING_US[name])
        burn_rows.append("%s %s -> %.3f ms (ceiling %.3f)"
                         % (name, cls, ms if ms is not None else -1.0,
                            WRANGLE_CEILING_US[name] * pieces * 1e-3))
        if not seen:
            burned.append(name)
    check("mutation_every_wrangle_ceiling_bites", not survived and not burned,
          "%d/%d at %.0fx, %d under the floor"
          % (len(WRANGLE_CEILING_US) - len(survived) - len(blind),
             len(WRANGLE_CEILING_US), WRANGLE_MUTATION_SCALE, len(blind)),
          "every row is reached by the verdict at its own ceiling, and a "
          "%.0f-fold regression on it is NAMED unless that regression is "
          "smaller than twice the %.0f ms noise floor the ceiling was built "
          "with - so with `wrangle_ceilings_are_tight` holding every ceiling "
          "at or under %.0fx, no wrangle can %.0fx in silence and the ones "
          "this instrument cannot see are these, with their numbers: %s - "
          "and each of THOSE is reddened by a PHYSICAL element-dependent "
          "burn instead: %s. Survived the arithmetic mutation: %s. Survived "
          "the burn: %s"
          % (WRANGLE_MUTATION_SCALE, WRANGLE_FLOOR_MS, WRANGLE_HEADROOM,
             WRANGLE_MUTATION_SCALE, blind or "none",
             "; ".join(burn_rows) or "none", survived or "none",
             burned or "none"))

    # --- and the REAL survivor, M3, on the node it shipped through ----------
    fin = node.node("pc_finalize")
    sound = fin.parm("snippet").eval()
    dirt, stage = lever["pc_finalize"]
    fin.parm("class").set(0)
    fin.parm("snippet").set(FINALIZE_DEBATCHED)
    got = _wrangle_cook(node, dirt, 880, stage)
    fin.parm("class").set(1)
    fin.parm("snippet").set(sound)
    ms = got.get("pc_finalize")
    rate = None if ms is None else ms * 1e3 / pieces
    ceiling = WRANGLE_CEILING_US["pc_finalize"]
    check("mutation_pc_finalize_debatched",
          rate is not None and rate > ceiling,
          "%.4f us/piece" % (rate if rate is not None else -1.0),
          "§21.4's SURVIVOR 1 - `pc_finalize` as a DETAIL wrangle looping "
          "over the prims on one thread, which ships a value-for-value "
          "identical fence and was 106 [PASS] / 0 green with the .hda rebuilt "
          "at source - costs %.4f us/piece against the batched %.4f and the "
          "%.4f ceiling. This is the mutation D206 exists for"
          % (rate if rate is not None else -1.0,
             big["pc_finalize"] * 1e3 / pieces, ceiling))
    node.destroy()


def union_parity(root):
    """D166's safety property: the fence does not change when the VEX answers.

    ⚠️ THE ONE THING THAT COULD HAVE GONE WRONG QUIETLY. `resolve_corners` now
    returns the wrangle's `pc_turn_deg`, which is `acos` ULP away from the
    Python's (2.842e-14 deg), and `Corner.included_angle` is thresholded
    against `min_included_angle_deg` before every miter. A knife-edge case
    could flip a corner from miter to bend and move a whole leg.

    So: the BUILT ASSET (native path) against `place.build` on the raw
    geometry (pure Python path, no native tables present), on corner-heavy
    shapes in both corner modes - the elements and every point of them.
    """
    shapes = (("L", [(0, 0, 0), (12, 0, 0), (12, 0, 8)]),
              ("zigzag", [(0, 0, 0), (6, 0, 0), (9, 0, 5), (15, 0, 5),
                          (18, 0, 0), (26, 0, 0)]),
              ("slope", [(0, 0, 0), (10, 2, 0), (20, 0, 6), (30, 4, 6)]),
              ("hairpin", [(0, 0, 0), (10, 0, 0), (10.2, 0, 0.4),
                           (0.4, 0, 0.6)]))
    bad = []
    n_prims = 0
    worst = 0.0
    for label, pts in shapes:
        spline = root.createNode("python", "union_" + label)
        spline.parm("python").set(
            "geo = hou.pwd().geometry()\n"
            "poly = geo.createPolygon(False)\n"
            "for p in %r:\n"
            "    pt = geo.createPoint()\n"
            "    pt.setPosition(p)\n"
            "    poly.addVertex(pt)\n" % (pts,))
        for mode in ("bend", "miter"):
            node = root.createNode("pf_polychain", "u_%s_%s" % (label, mode))
            node.setInput(0, spline)
            node.parm("corner_mode").set(mode)
            got = node.geometry()
            style = H.style_from_parms(node)
            out, _r = P.build(spline.geometry(), H.kit_geometry(node), style,
                              params=style.params)
            ids_a = sorted(p.attribValue("pc_elem_id") for p in got.prims())
            ids_b = sorted(p.attribValue("pc_elem_id") for p in out.prims())
            pos_a = got.pointFloatAttribValues("P")
            pos_b = out.pointFloatAttribValues("P")
            n_prims += len(ids_a)
            if ids_a != ids_b or len(pos_a) != len(pos_b):
                bad.append((label, mode, len(ids_a), len(ids_b)))
            else:
                for a, b in zip(pos_a, pos_b):
                    worst = max(worst, abs(a - b))
            node.destroy()
        spline.destroy()
    check("union_matches_the_python_path", not bad and worst == 0.0,
          "%.3e m" % worst,
          "the BUILT asset (VEX decompose) vs place.build on raw geometry "
          "(pure Python), %d prims over 4 corner-heavy shapes x bend/miter; "
          "ceiling 0.0 - the acos ULP in pc_turn_deg must not reach the "
          "miter threshold. %s" % (n_prims, bad[:2] or "identical"))


class _StubResult(object):
    """The smallest thing a runner's `main` can put in `results`."""

    def __init__(self, value):
        self.ok, self.skipped, self.value = True, False, value

    def as_dict(self):
        return {"name": "reachability", "value": self.value}

    def __repr__(self):
        return "reachability=%r" % (self.value,)


def _runner_reaches_its_baseline(module, cases_module, tripwire_name, key):
    """Call `module.main()` FOR REAL and watch what it does about a moved
    baselined value.  -> (rows, note).

    ⚠️ THIS IS THE HALF THAT WAS MISSING AND IT IS THE HALF THAT MATTERS.
    D210's rule was asserted on `run_scene_checks.exit_code` as a pure
    function, and on `run_2d_checks` by grepping three literal strings out of
    `inspect.getsource(main)`.  Neither is REACHABILITY: inserting

        if not update and not json_out:
            print(...); sys.exit(1 if failures else 0)

    before the baseline block of `run_2d_checks.main` leaves every asserted
    string present but unreachable, and the row printed PASS 9/9 while the
    runner itself - with a `baseline_2d.json` value perturbed to 999999
    against a real 176 - printed NO movement line and exited 0.  That is
    D210's exact finding restored past a green check.

    So `main` is CALLED, with two things replaced and both restored: the case
    builder returns nothing and the tripwire block returns one stub value, so
    the run costs milliseconds instead of minutes and the only thing being
    exercised is the baseline-and-exit tail; and `BASELINE` points at a
    throwaway file this function writes.  Three passes: write the baseline,
    perturb it and demand exit 1 with the movement printed, then restore it
    and demand exit 0.  A `sys.exit` inserted anywhere above the baseline
    block fails the second pass, which is the whole point.
    """
    import contextlib
    import json as _json
    import tempfile

    handle, path = tempfile.mkstemp(suffix=".json")
    os.close(handle)
    # `mkstemp` leaves an EMPTY file and both runners do `if
    # os.path.exists(BASELINE): json.load(...)`, so the first pass has to find
    # nothing rather than nothing-shaped.
    os.remove(path)
    saved = (module.BASELINE, cases_module.build_all,
             getattr(module, tripwire_name), list(sys.argv))
    module.BASELINE = path
    cases_module.build_all = lambda: {}
    setattr(module, tripwire_name, lambda: [_StubResult(1.0)])

    def _run(argv):
        sys.argv = ["runner"] + argv
        out = io.StringIO()
        code = None
        try:
            with contextlib.redirect_stdout(out):
                module.main()
        except SystemExit as exc:
            code = exc.code
        return (code, out.getvalue())

    try:
        write_code, _ = _run(["--update-baseline"])
        with io.open(path, encoding="utf-8") as fh:
            written = _json.load(fh)
        clean_code, clean_text = _run([])
        written[key][0]["value"] = 999999.0
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write(_json.dumps(written, indent=2, sort_keys=True))
        moved_code, moved_text = _run([])
    finally:
        module.BASELINE = saved[0]
        cases_module.build_all = saved[1]
        setattr(module, tripwire_name, saved[2])
        sys.argv = saved[3]
        if os.path.exists(path):
            os.remove(path)

    name = module.__name__
    return ((("%s writes a baseline and exits 0" % name, write_code in (0, None)),
             ("%s exits 0 on an unmoved baseline" % name,
              clean_code in (0, None)),
             ("%s REACHES the baseline block" % name,
              "MOVED SINCE BASELINE" in moved_text),
             ("%s exits NON-ZERO on a moved value" % name, moved_code == 1)),
            "clean exit=%r, moved exit=%r, moved line: %s"
            % (clean_code, moved_code,
               "printed" if "MOVED SINCE BASELINE" in moved_text
               else "ABSENT"))



def scene_baseline_is_enforced():
    """D210 - `run_scene_checks`' baseline used to be ADVISORY.

    A moved value printed under "moved since baseline" and the run exited 0
    anyway, so every "no baselined value moved" claim in this build log was
    citing an exit code that could not carry it.  Reproduced by hand -
    perturbing two `A_straight` rows printed both and still exited 0 - and
    this is the standing form of that mutation, so the fix cannot be undone
    in silence the way D207's was.

    Both halves are asserted: that movement is DETECTED, and that detection
    reaches the EXIT CODE.  The old rule (`1 if failures and not update`)
    fails the second half; a rule that also fails `--update-baseline` fails
    the third row.
    """
    import run_scene_checks as RSC

    base = {"C": [{"name": "v", "value": 1}, {"name": "w", "value": 2}]}
    same = {"C": [{"name": "v", "value": 1}, {"name": "w", "value": 2}]}
    drift = {"C": [{"name": "v", "value": 1}, {"name": "w", "value": 3}]}
    moved = RSC.baseline_movement(drift, base)
    quiet = RSC.baseline_movement(same, base)
    rows = (
        ("a moved value is seen", len(moved) == 1 and "C/w: 2 -> 3" in moved),
        ("an unmoved run is quiet", quiet == []),
        ("movement exits non-zero", RSC.exit_code(0, moved, False) == 1),
        ("a clean run exits zero", RSC.exit_code(0, quiet, False) == 0),
        ("--update-baseline accepts it", RSC.exit_code(0, moved, True) == 0),
        ("a failing check still exits non-zero",
         RSC.exit_code(1, quiet, False) == 1),
    )
    # ...and the OTHER runner that carries a baseline. `run_2d_checks` had a
    # copy of the same advisory rule; adde049 named it and left it, because
    # the phase-2 agent owned the file. It is fixed now, and this is what
    # stops it being re-copied: the rule has to be R's, not a duplicate that
    # can drift back. `inspect.getsource` reads the SHIPPED module, so this
    # reddens on a revert rather than on a comment.
    import inspect

    import run_2d_checks as R2D

    # Comments stripped first, and not as tidiness: the third row below
    # matched this very fix's own comment, which QUOTES the rule it removed.
    # A source assertion that a comment can satisfy is D207's defect again.
    src = "\n".join(ln.split("#")[0]
                    for ln in inspect.getsource(R2D.main).splitlines())
    rows += (
        ("run_2d_checks diffs through R.baseline_movement",
         "R.baseline_movement(results, base)" in src),
        ("run_2d_checks exits through R.exit_code",
         "sys.exit(R.exit_code(failures, moved, update))" in src),
        ("run_2d_checks keeps no advisory exit of its own",
         "1 if failures and not update" not in src),
    )
    # ...and the BEHAVIOURAL half, which is what the three rows above are NOT.
    # A source grep proves a line is present, never that it runs; see
    # `_runner_reaches_its_baseline` for the mutation that leaves all three
    # strings in place and still exits 0 on a moved value.
    import cases2d

    notes = []
    for module, cases_module, tripwire, key in (
            (RSC, cases, "port_tripwires", "ZZ_port_tripwires"),
            (R2D, cases2d, "tripwires", "ZZ_2d_tripwires")):
        got, note = _runner_reaches_its_baseline(module, cases_module,
                                                 tripwire, key)
        rows += got
        notes.append("%s: %s" % (module.__name__, note))
    bad = [name for name, ok in rows if not ok]
    check("scene_baseline_movement_fails_the_run", not bad,
          "%d/%d" % (len(rows) - len(bad), len(rows)),
          "`run_scene_checks` AND `run_2d_checks` exit non-zero on a moved "
          "baselined value (D210 - both used to print and exit 0), asserted "
          "on the pure rule, on the source, AND by CALLING each runner's own "
          "`main` against a perturbed throwaway baseline. %s. Broken: %s"
          % ("; ".join(notes), ", ".join(bad) or "none"))


def main():
    if not os.path.exists(HDA_PATH):
        print("no HDA at %s - run devScripts/create_pf_polychain_hda.py"
              % HDA_PATH)
        sys.exit(1)
    # The asset is needed from section 3 on (the two boundary checks cook it),
    # not only by `readability`.
    hou.hda.installFile(HDA_PATH)
    root = hou.node("/obj").createNode("geo", "polychain_native")
    built = cases.build_all()
    # 13.10 - the three shapes the scene suite structurally cannot
    # contain: a fused junction, a marker inside a prim, and a
    # duplicated id with a marker. They live in `cases.py` beside
    # everything else and are merged HERE rather than into
    # `build_all` because two of them build no geometry at all, so
    # the scene checks would have nothing to assert about them.
    built.update(cases.topology_cases())

    print("\n=== 1. 4.1 DECOMPOSE - native vs the reference, %d cases ==="
          % len(built))
    decompose_parity(root, built)

    print("\n=== 2. 4.4 pc_frames - native vs place._packed_transform ===")
    worst, bad_pos, total, zmodes = frames_parity(root, built)
    frames_ulp = FRAMES_ULP
    # EXACT. Both sides are 64-bit arithmetic over the same span, and the
    # rig rounds the span on both sides so this measures the maths alone.
    # ⚠️ THE CEILING MOVED FROM 0.0 TO 2 float64 ULP, AND THE REASON IS THE
    # FIX, NOT A REGRESSION. Until D170 the span crossed to the wrangle as a
    # single float32, so BOTH sides sampled a span with 24 significant bits
    # and every last bit agreed by construction. The pair now carries ~48 of
    # them, which un-masks the one difference that was always there and that
    # `frames_arithmetic_position_parity` already names: VEX fuses `a + d*t`
    # into an FMA and Python does not, so the sampled position can round one
    # float64 ULP apart, and the frame built on it inherits that. Measured:
    # 2.220e-16 relative, exactly 1 ULP at 1.0. Trading 1e-16 of agreement
    # here for 9.765e-4 m of agreement at 20 km is the whole point of D170.
    check("frames_arithmetic_linear_parity", worst <= 4.5e-16,
          "%.3e rel" % worst,
          "worst relative |d 3x3| over %d real calls, z-modes %s (ceiling "
          "4.5e-16 = 2 float64 ULP; it is FMA, not a disagreement). "
          "ARITHMETIC ONLY - the span goes through D170's transport on both "
          "sides; `plan_span_transport_at_20km` measures the transport"
          % (total, "/".join(sorted(zmodes))))
    # NOT an equality, and the difference is worth naming rather than
    # papering over. 4 949 of 4 950 P components come back BIT-IDENTICAL to
    # `f32(reference)`; exactly one is a single float32 ULP away
    # (2.384e-07 m at 2.25 m, `AB_fillet`, `pax` = 0 so the offset term is
    # zero and the difference is in the sampler's own `a + d*t`). VEX fuses
    # that multiply-add and Python does not, so the two round the last bit
    # differently on one span in the whole suite. One ULP is the smallest
    # unit the storage HAS - a tighter ceiling would be a claim that float32
    # arithmetic is associative.
    check("frames_arithmetic_position_parity", frames_ulp[0] <= 1.0,
          "%d / %d, %.2f ULP" % (bad_pos, total * 3, frames_ulp[0]),
          "P components not bit-identical to f32(reference), and the worst "
          "one in float32 ULP (ceiling 1.0 ULP)")

    print("\n=== 3. D113's three trials, and the two boundaries ===")
    trial_parity(root)
    sixty_four_bit(root)
    worldscale_transport(root)
    config_payload_parity(root)
    union_parity(root)

    print("\n=== 3b. R1 - 3.3's seeding chain, in VEX ===")
    seeding_parity(root)

    print("\n=== 3c. 13.9 N2 - 4.2's fitting solve, in VEX ===")
    plan_parity(root, built)
    plan_stress_parity(root)
    plan_fixture_parity(root)
    declared_limit_dup_id_marker(root)
    plan_determinism(root, built)
    plan_shared_id_order(root)
    plan_kit_scale(root)

    print("\n=== 3d. 13.9 N4 - the packed branch, and R8 ===")
    r8_packed_transform(root)
    place_packed_parity(root, built)
    place_duplicate_module_name(root)
    native_place_says_why_it_is_empty(root)
    gate_parity(root, built)
    frames_scale_check(root)
    emit_scale_check(root)

    print("\n=== 4. the mutation test ===")
    mutation(root, built)
    seeding_mutation(root)
    plan_mutation(root, built)
    sections_mutation(root, built)
    place_mutation(root, built)
    kit_id_mutation(root, built)
    finalize_mutation(root, built)
    gate_mutation(root, built)
    frames_scale_mutation(root)
    emit_scale_mutation(root)
    solve_scale_check(root)
    wrangle_cost_check(root)
    scene_baseline_is_enforced()

    print("\n=== 5. 13.7 - the graph is readable, on the built asset ===")
    node = readability(root)
    native_reach(root)
    native_stage_check(root)
    native_stage_mutation(root)
    stage_wiring_mutation(root)

    print("\n=== 7. 13.9 N10 - the guard switch on `Stage = output` ===")
    output_guard_parity(root, built)
    payload_cond_parity(root)
    output_guard_mutation(root, built)
    output_guard_cost(root)
    kit_starter_cooks_once(root)
    guard_padding_parity(root)
    guard_bend_bound(root)
    guard_bend_bound_skips_rigid_modules(root)
    guard_bend_bound_needs_its_operands(root)
    guard_spline_attr_types(root)
    mutation_spline_attr_types(root)
    guard_kit_mismatch(root)
    guard_refusal_list_is_true(node)
    bench_guard_fallback(root)

    print("\n=== 6. cook count and the two benches ===")
    benches(root, node)
    plan_benches(root, built)

    native.cleanup()
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d failing checks" % len(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
