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

import math
import os
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

    # 13.7 rule 5 - a group-name collision between two stages silently
    # corrupts one of them, so every working group carries the prefix.
    node.parm("stage").set("sections")
    node.cook(force=True)
    groups = [g.name() for g in node.geometry().pointGroups()]
    stray = [g for g in groups if not g.startswith("pc_")]
    check("working_groups_are_prefixed", not stray, len(groups),
          "unprefixed: %s" % (", ".join(stray) or "none"))
    node.parm("stage").set("output")
    return node


# --- 6: cook count and the two benches --------------------------------------

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
    streets = hou.Geometry()
    for i in range(300):
        x = (i % 20) * 30.0
        z = (i // 20) * 25.0
        cases.polyline(streets, [(x, 0.0, z), (x + 18.0, 0.0, z),
                                 (x + 18.0, 0.0, z + 14.0)],
                       curve_id="S%03d" % i)

    for label, geo in (("long_curve", long_curve), ("streets_300", streets)):
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
        best = None
        passes = 4
        for i in range(passes):
            dirt.parm("nudge").set(i + 2)
            start = time.time()
            last.cook()
            elapsed = time.time() - start
            best = elapsed if best is None else min(best, elapsed)
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
        from polyfactory.polychain import decompose as D
        curves, markers = P.read_curves(geo)
        ref_best = ref_full = None
        for _ in range(3):
            start = time.time()
            for curve in curves:
                D._clean(curve)
                D.resolve_corners(curve, DEFAULTS)
                D.resolve_markers(curve, markers)
                curve._cum = None           # the cache would make run 2 free
            elapsed = time.time() - start
            ref_best = elapsed if ref_best is None else min(ref_best, elapsed)
        for _ in range(3):
            start = time.time()
            fresh_curves, fresh_marks = P.read_curves(geo)
            for curve in fresh_curves:
                D._clean(curve)
                D.resolve_corners(curve, DEFAULTS)
                D.resolve_markers(curve, fresh_marks)
            elapsed = time.time() - start
            ref_full = elapsed if ref_full is None else min(ref_full, elapsed)
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
        check("decompose_%s_wall_clock" % label, best < ref_best * 1.5,
              "%.4f s (%.2f-%.2fx)" % (best, ref_best / best if best else 0.0,
                                       ref_full / best if best else 0.0),
              "%d curves / %d points through %d native nodes. The RANGE is "
              "the reference without its geometry read (%.4f s) and with it "
              "(%.4f s); the ceiling is 1.5x the lower bound, and no speedup "
              "is claimed on the lower bound"
              % (len(out.prims()), len(out.points()), len(nodes),
                 ref_best, ref_full))
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

    print("\n=== 4. the mutation test ===")
    mutation(root, built)

    print("\n=== 5. 13.7 - the graph is readable, on the built asset ===")
    node = readability(root)

    print("\n=== 6. cook count and the two benches ===")
    benches(root, node)

    native.cleanup()
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d failing checks" % len(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
