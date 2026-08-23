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
    drift = []
    for rig_name, rig_node in sorted(rig.items()):
        mine = node.node(rig_name)
        if mine is None:
            drift.append("%s: absent from the asset" % rig_name)
            continue
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
    bypassed = sorted(c.name() for c in node.children() if c.isBypassed())
    drift += ["%s(bypassed)" % n for n in bypassed]
    sub.destroy()
    check("asset_stages_match_the_rig", not drift,
          "%d nodes / %d bypassed" % (len(rig), len(bypassed)),
          "class, VEX precision, snippet, node type and the parameters that "
          "decide what it computes, for every stage the "
          "parity rig measures, read back off the SHIPPED asset, plus every "
          "bypassed node in it: %s" % (", ".join(drift) or "none"))

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
        emit_body.replace("int n = min(npieces, len(p_slot));",
                          "int n = min(npieces, len(p_slot)) - 1;")))
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
    "pc_warn_degenerate_frame": "4.4's degenerate frame - N5",
    "pc_warn_corner_degenerate": "4.3 corners - N8",
}


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


def emit_scale_in_pieces(root, npts, stamp_snippet=None, passes=3):
    """What `pc_plan_emit` and `pc_stamp` cost PER PIECE, each on its own.

    ⚠️ THE TWO NODES ARE TIMED SEPARATELY AND EACH IS DIRTIED FROM ITS OWN
    INPUT.  D164: `cook(force=True)` on a node whose inputs have not changed
    can be a no-op, and a timing without a cook count is not a measurement -
    so a nudge wrangle sits above each node and its `cookCount` has to advance
    once per pass or the row fails.

    `stamp_snippet` replaces `pc_stamp.vfl`'s VEX, and the class moves with it
    - the mutation lever, so the ceiling can be shown to bite.

    Returns (npieces, emit_best, stamp_best, emit_cooks, stamp_cooks).
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

    dirt_emit = nudge("emitdirty", pn["pc_plan_solve"], emit)
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

    emit_best, emit_cooks = timed(emit, dirt_emit, 2)
    stamp_best, stamp_cooks = timed(stamp, dirt_stamp, 40)
    sub.destroy()
    return npieces, emit_best, stamp_best, emit_cooks, stamp_cooks


# The ceilings, in microseconds per piece, and where each number comes from.
# Measured on this build at 1 000 / 2 500 / 5 000 / 10 000 / 20 000 pieces:
#   pc_plan_emit   3.25 2.80 2.78 2.75 2.91   - flat, and DETAIL by necessity
#   pc_stamp       1.34 1.32 1.28 0.33 0.30   - flat, and POINT by choice
# The two defects each ceiling is aimed at, measured on the same fixture:
#   the `pointgenerate` expander D175 replaced: 3 860 us/piece at 10 000
#   `pc_stamp` de-batched into a detail loop:       9.4 us/piece at 20 000
EMIT_CEILING_US = 6.0
STAMP_CEILING_US = 3.0
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
    for label, node, index, ceiling in (("emit", "pc_plan_emit", 1,
                                         EMIT_CEILING_US),
                                        ("stamp", "pc_stamp", 2,
                                         STAMP_CEILING_US)):
        rate_small = small[index] * 1e6 / small[0]
        rate_big = big[index] * 1e6 / big[0]
        cooks = small[2 + index] == 3 and big[2 + index] == 3
        check("%s_cost_is_flat_in_piece_count" % label,
              cooks and rate_big <= ceiling
              and rate_big <= GROWTH_CEILING * rate_small,
              "%.2f us/piece" % rate_big,
              "`%s` ALONE on %d pieces, best of 3 dirtied passes; %.2f "
              "us/piece at %d pieces, so the growth is %.2fx (ceiling %.1fx). "
              "Absolute ceiling %.1f us/piece. `mutation_pc_stamp_debatched` "
              "proves the stamp ceiling bites"
              % (node, big[0], rate_small, small[0], rate_big / rate_small,
                 GROWTH_CEILING, ceiling))


def emit_scale_mutation(root):
    """De-batch `pc_stamp` back into a single-threaded detail loop - cycle
    N-2V2's mutation M2, which survived a 77 / 0 suite - and watch the ceiling
    bite.  The mutated VEX writes the SAME `pc_elem_id` and `pc_elem_key`;
    only the cost model changes.
    """
    from polyfactory.polychain import vexsrc
    body = vexsrc.source("pc_stamp")
    found = STAMP_BATCHED in body
    npieces, _emit, stamp_best, _ec, cooks = emit_scale_in_pieces(
        root, 40001, stamp_snippet=body.replace(STAMP_BATCHED,
                                                STAMP_DEBATCHED), passes=1)
    rate = stamp_best * 1e6 / npieces
    check("mutation_pc_stamp_debatched",
          found and cooks == 1 and rate > STAMP_CEILING_US,
          "%.2f us/piece (target present: %s)" % (rate, found),
          "`pc_stamp` as a DETAIL wrangle looping over all %d pieces on one "
          "thread - M2, which was 77 / 0 green - costs %.2f us/piece against "
          "the batched %.1f-or-less. The ceiling above is a measurement, not "
          "a decoration" % (npieces, rate, STAMP_CEILING_US))


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
    ("place_native", "OUT_place_native",
     ("pc_proto", "pc_frames_native", "pc_place_valid", "copy_packed"),
     ("config", "kit_starter")),
)


def stage_is_really_native(root, tag, rewire=None):
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
    cases.polyline(geo, [(0.0, 0.0, 0.0), (9.0, 0.0, 0.0), (9.0, 0.0, 7.0)],
                   curve_id="D192")
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

    if rewire is not None:
        token, target = rewire
        served = dict((t, n) for t, n, _w, _p in NATIVE_STAGES)[token]
        switch = node.node("stage_switch")
        moved = [i for i, inp in enumerate(switch.inputs())
                 if inp is not None and inp.name() == served]
        assert len(moved) == 1, "no switch input serves %s" % served
        switch.setInput(moved[0], node.node(target))

    pysops = [c for c in node.children() if c.type().name() == "python"]
    bad = []
    nudge = 2
    for token, served, must_cook, allowed in NATIVE_STAGES:
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
        if idle:
            bad.append("%s: idle %s" % (token, ",".join(idle)))
        if strangers:
            bad.append("%s: python %s cooked" % (token, ",".join(strangers)))
        nudge += 1
    node.destroy()
    dirt.destroy()
    return bad


def native_stage_check(root):
    bad = stage_is_really_native(root, "sound")
    watched = sum(len(w) for _t, _n, w, _p in NATIVE_STAGES)
    check("native_stages_are_really_native", not bad,
          "%d nodes / %d stages" % (watched, len(NATIVE_STAGES)),
          "D192, on the SHIPPED asset: every node each native Stage is made "
          "of advanced its cookCount, and no Python SOP outside its named "
          "allowance did. Complaints: %s" % (", ".join(bad) or "none"))


def native_stage_mutation(root):
    """M4b, applied to the built asset: point the `plan_native` menu entry at
    the PYTHON bridge and watch the check above go red.

    The mutation is invisible to everything else in the suite - the rig still
    cooks the VEX solve, the parameters still match, and the stage still
    produces a plan - which is precisely why it survived 77 / 0.
    """
    for tag, token, target, python_sop in (
            ("m4b", "plan_native", "OUT_plan", "pc_plan_bridge"),
            ("m4", "place_native", "OUT_reference", "kernel")):
        bad = stage_is_really_native(root, tag, rewire=(token, target))
        mine = [b for b in bad if b.startswith(token + ":")]
        check("mutation_%s_unplugged" % token,
              len(mine) >= 2 and any(python_sop in b for b in mine),
              "%d complaints" % len(bad),
              "rewiring the `%s` switch input to %s must report BOTH "
              "halves - the stage own nodes idle AND %s cooking. Got: %s"
              % (token, target, python_sop, "; ".join(mine) or "none"))


def native_reach(root):
    """WHICH native nodes an artist who never opens the Stage menu runs.

    ⚠️ THIS IS THE CHECK THAT KEEPS §16's SCOPE HONEST.  The claim "the plan
    and the packed branch are ported" is worth exactly as much as the claim
    "and they reach no artist yet", and the second half is a MEASUREMENT here
    rather than a sentence in a build log that will age.  The day 13.9 N10
    retires `kernel`, this check has to be edited on the same commit - which
    is the ladder device §11.2 already uses.
    """
    node = root.createNode("pf_polychain", "reach")
    geo = hou.Geometry()
    cases.polyline(geo, [(0.0, 0.0, 0.0), (9.0, 0.0, 0.0), (9.0, 0.0, 7.0)],
                   curve_id="R")
    node.setInput(0, native.feed(root, geo, "REACH"))
    node.allowEditingOfContents()
    watched = ("pc_sections", "pc_plan_solve", "pc_plan_emit", "pc_proto",
               "pc_frames_native", "copy_packed", "pc_frames",
               "pc_plan_bridge")
    before = {}
    node.parm("stage").set("output")
    node.cook(force=True)
    for name in watched:
        child = node.node(name)
        before[name] = child.cookCount() if child is not None else -1
    # a real re-cook of the Output stage, forced through the input
    node.parm("corner_angle_deg").set(31.0)
    node.cook(force=True)
    node.parm("corner_angle_deg").set(30.0)
    node.cook(force=True)
    cooked = sorted(n for n in watched
                    if node.node(n) is not None
                    and node.node(n).cookCount() > before[n])
    check("native_plan_and_place_reach_no_artist", not cooked,
          "%d of %d idle" % (len(watched) - len(cooked), len(watched)),
          "nodes that cooked on `Stage = output`: %s. This is the HONEST "
          "half of 13.9 N2/N4 - the solve and the packed branch are at "
          "parity and they are behind the Stage switch, because 4.3, 4.5 and "
          "4.6 are still the reference (D180). N10 edits this check."
          % (", ".join(cooked) or "none"))
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
    frames_scale_mutation(root)
    emit_scale_mutation(root)

    print("\n=== 5. 13.7 - the graph is readable, on the built asset ===")
    node = readability(root)
    native_reach(root)
    native_stage_check(root)
    native_stage_mutation(root)

    print("\n=== 6. cook count and the two benches ===")
    benches(root, node)
    plan_benches(root, built)

    native.cleanup()
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d failing checks" % len(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
