"""The NATIVE stages, measured against the reference implementation.

    hython tests/polychain/run_native_checks.py

The reference stays live in-process; every stage cooks the real SOP nodes
`devScripts/create_pf_polychain_hda.py` installs, and the guard checks cook
the SHIPPED asset.  v2, 2026-08-25: trimmed from 9 066 lines / 144 checks to
the 19 names that have a registered mutation or state a property `compare()`
(diff.py + run_generated.py) structurally cannot.
WHAT IT CANNOT SEE: whether either path is right - it is a parity instrument.
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

    An ASSERTION, not a tolerance: `native == f32(reference)` cannot be
    satisfied by luck.
    """
    return struct.unpack("f", struct.pack("f", float(x)))[0]


def hilo(x):
    """D170's split: the float32 head and the float32 residual
    `plan_geometry` stores, which `pc_frames` adds back in 64-bit VEX."""
    head = f32(x)
    return head, f32(float(x) - head)




def ulp32(x):
    """One float32 ULP at `x` (D111: a unit, not a tolerance)."""
    if x == 0.0:
        return math.ldexp(1.0, -149)
    return math.ldexp(1.0, math.frexp(abs(x))[1] - 24)


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

        # (a) THE ID RULE AND THE CURVE SET, against `read_curves` ITSELF -
        # one rule now (D29/D64), asked prim by prim, INCLUDING the prims
        # the reference declined.
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

        # (b) MARKERS, keyed by the PRIM each one landed on.  D169: on a
        # duplicated id the first prim keeps the marker and owes a WARNING -
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

    # EXACT, no slack: 64-bit VEX doing the same additions in the same order
    # as 64-bit Python. If this needs a tolerance the accumulation order
    # differs, and that is a defect, not float noise (13.8).
    check("decompose_arclength_parity", worst_s == 0.0, "%.3e m" % worst_s,
          "worst |d pc_s| over %d curves, all cases (ceiling 0.0)"
          % n_curves)


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
        # The spans go through the real float32 transport on BOTH sides, so
        # the two checks below are ARITHMETIC-ONLY; the transport itself is
        # measured unrounded by `plan_span_transport_at_20km`.  The PAIR is
        # recorded, not just the sum: re-splitting `head + lo` gives a
        # different pair (3x3 then disagreed by 2.220e-16).
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
        # ONE polyline per recorded `Path`, in `Path` order - the Path may
        # be a FILLETED or slope-flattened polyline, so the prim number IS
        # the recorded index.
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
                    # components times a scale (D111).
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


def mutation(root, built):
    """Corrupt each new node and confirm the parity check goes red.

    A node whose removal leaves the suite green is untested (P2-3V, x6).
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
    # THE WHOLE CHAIN, not `pc_arclength` alone (D167: skipping the upstream
    # nodes measures the gate rather than the mutation).
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

    # (c) pc_unshare: BYPASS it, and the fused junction must go wrong -
    # D165's whole justification in one assertion.
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


def sixty_four_bit(root):
    """13.8's design rule, asserted: no intermediate may round-trip through
    float32 (measured: 20000.0 + 4.883e-4 reads back with error 0.0 from a
    64-bit wrangle).  R2: intermediates must stay 64-bit at world scale.
    """
    # Cannot be tested through `P` (float32 storage - R2's floor, measured by
    # `frames_arithmetic_position_parity`); this checks that a computed
    # intermediate is not rounded to float32 at node boundaries.
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
    # COMPARE AGAINST THE SAME SUBTRACTION, not the decimal literal - else
    # 1.4e-13 of the comparand's own cancellation reads as node error (D115).
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
    # THE EMPTY STRING IS THE POINT: "" cross-read as numeric 0.0 (measured:
    # 0.12 m post where the reference puts a 1.6 m gate, downstream 0.21 m
    # out).  `json_dumps(dict, 0)` names the type now; other rows = controls.
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

    # --- D242: a `markerData:` slot that is NOT A SCALAR, and a KEY THAT
    # --- `json_dumps` ESCAPES ----------------------------------------------
    # These rows exist because a source mutation survived the whole suite:
    # a vector/list/nested dict cross-type-read as 0.0 and published as a
    # READABLE numeric subject (measured: 1 gate + 10 panels vs the
    # reference's 10 panels; `lt`/`ge` diverged too).  The escaped-KEY half
    # cannot survive the rig's string-parm transport; `guard_marker_data_
    # types` covers it on the shipped asset (a quoted key fired a gate never
    # asked for; a non-ASCII key dropped one that was - both directions).
    for tag, data, op, value in (
            ("vector", {"v": hou.Vector3(1.0, 2.0, 3.0)}, "eq", 0.0),
            ("vector_lt", {"v": hou.Vector3(1.0, 2.0, 3.0)}, "lt", 1.0),
            ("vector_ge", {"v": hou.Vector3(1.0, 2.0, 3.0)}, "ge", 0.0),
            ("vector_ne", {"v": hou.Vector3(1.0, 2.0, 3.0)}, "ne", 0.0),
            ("list", {"v": (1.0, 2.0)}, "eq", 0.0),
            ("list_lt", {"v": (1.0, 2.0)}, "lt", 1.0),
            ("nested", {"v": {"a": 1.0}}, "eq", 0.0),
            ("nested_ge", {"v": {"a": 1.0}}, "ge", 0.0)):
        geo = hou.Geometry()
        cases.polyline(geo, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)], curve_id="S")
        cases.marker(geo, (8.0, 0.0, 0.0), "S", 7, dist=8.0, data=data)
        out.append(("marker_data_%s" % tag, geo, kit, Style(
            "md", 1, 3,
            rules=[Rule("marker:7", "conditional", ["gate", "post"],
                        cond={"subject": "markerData:v", "op": op,
                              "value": value}),
                   Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive"))))
    # --- D7's per-POINT `pc_section`, by TYPE ------------------------------
    # A STRING key read as float (always 0.0): 1 section / 12 pieces vs the
    # reference's 2 / 14.  Both types are inside the contract.
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
    # The only topology where prim order decides: sections INTERLEAVE
    # (A0, B0, A1, B1); `pc_sections`' merge sort ties on the prim number.
    geo = hou.Geometry()
    cases.polyline(geo, [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0),
                         (10.0, 0.0, 8.0)], curve_id="A")
    cases.polyline(geo, [(0.0, 0.0, 20.0), (7.0, 0.0, 20.0),
                         (7.0, 0.0, 26.0)], curve_id="A")
    out.append(("shared_curve_id", geo, kit, Style(
        "sh", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive"))))

    # --- non-ASCII ids, through the RANDOM selector ------------------------
    # `pc_crc32` folded CODE POINTS where `zlib.crc32` folds UTF-8 BYTES -
    # measured, a 47-piece picket run vs the reference's 5-piece panel run.
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
    # 7.2's 25 cell roles imply this size.  The PARITY half on 220 modules;
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
    # `prim(0, ...)` reads component 0 while the reference gets the WHOLE
    # tuple (measured: `gt 5.0` built 12 gate prims vs the reference's 10
    # panel; `lt 100.0` diverged the other way; eq/ne agreed by luck and are
    # the controls).  Every operator present - which ones agreed was an
    # accident of the value.
    # D257: `addAttrib` with a list builds a fixed-size TUPLE, not an array
    # (probed 22.0.398: isArrayType() False), so the ARRAY half was DEAD
    # CODE; float/string arrays and dicts (primattribsize == 1) fell to a
    # 0.0 float read (measured: 12 gate vs 10 panel; int array correctly
    # refused).  Array rows now use `addArrayAttrib` and ASSERT
    # isArrayType(); the operand set gains eq 0.0 / lt 1.0 / ge 0.0 because
    # the shipped set agreed with a 0.0 cross-read on four of six operators.
    ARRAY_ROWS = (("iarray", hou.attribData.Int, (8, 1, 2)),
                  ("farray", hou.attribData.Float, (7.5, 1.0)),
                  ("sarray", hou.attribData.String, ("a", "b")))
    OPS = (("gt", 5.0), ("ge", 5.0), ("lt", 100.0), ("eq", 5.0), ("ne", 5.0),
           ("in", [7.5, 1.0]), ("eq", 0.0), ("lt", 1.0), ("ge", 0.0),
           ("ne", 0.0))

    def _attr_case(tag, op, want, make):
        geo = hou.Geometry()
        poly = cases.polyline(geo, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
                              curve_id="S")
        make(geo, poly)
        # the name becomes a NODE name, so it has to survive `createNode`
        suffix = re.sub(r"[^A-Za-z0-9]", "", str(want))
        return ("attr_%s_%s%s" % (tag, op, suffix), geo,
                kit, Style(
                    "av", 1, 3,
                    rules=[Rule("default", "conditional", ["gate", "post"],
                                cond={"subject": "attr:vecattr", "op": op,
                                      "value": want}),
                           Rule("default", "first", ["panel"])],
                    params=Params(fill="adaptive")))

    for tag, value in (("vec3", (7.5, 1.0, 2.0)), ("vec2", (7.5, 1.0)),
                       ("ivec3", (8, 1, 2))):
        for op, want in OPS:
            def _tuple(geo, poly, value=value):
                geo.addAttrib(hou.attribType.Prim, "vecattr", value)
                poly.setAttribValue("vecattr", value)
            out.append(_attr_case(tag, op, want, _tuple))
    for tag, storage, value in ARRAY_ROWS:
        for op, want in OPS:
            def _array(geo, poly, storage=storage, value=value):
                geo.addArrayAttrib(hou.attribType.Prim, "vecattr", storage)
                poly.setAttribValue("vecattr", value)
                attrib = geo.findPrimAttrib("vecattr")
                if attrib is None or not attrib.isArrayType():
                    raise AssertionError(
                        "the `%s` fixture is not an ARRAY attribute - D257's "
                        "whole finding is that a tuple looks like one" % tag)
            out.append(_attr_case(tag, op, want, _array))
    for op, want in OPS:
        def _dict(geo, poly):
            geo.addAttrib(hou.attribType.Prim, "vecattr", {})
            poly.setAttribValue("vecattr", {"a": 1.0})
        out.append(_attr_case("dict", op, want, _dict))

    # --- D202: `ctx_base`'s own DICT-VALUED keys ---------------------------
    # `attrs` / `marker_data` are dict-valued ctx keys, not None (measured:
    # `ne "zzz"` planned 10 pieces vs the reference's 12).  The style
    # warning that blocks output is coincidence, so parity is asserted here.
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
    # AND THE SURFACE, which this helper used to drop on the floor: every
    # `B*_conform_*` case cooked with input 4 UNWIRED - and 4.5 is the
    # largest thing the native chain cannot do.
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

    Every row is an UNPORTED stage, named; the check prints the list
    (otherwise the "unfailable" pattern P2-3V found six times).
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
        # 4.3 reserves span off both ends of every leg: the SAME element
        # address names a different span in the two plans (N8).
        return "4.3 corners - N8"
    ids = [str(c.curve_id) for c in curves]
    if len(set(ids)) != len(ids):
        return "D169 duplicated curve id - the marker binds to one prim"
    return ""


def gate_parity(root, built):
    """13.9 N5 - the deform gate, against `place._needs_deform` itself.

    A boolean per piece that decides the whole cost model (D69: 10 005
    packed at 0.42 s / +12 MB vs 10 005 deformed at 21.9 s / 360 180
    points).  The reference's answer is read where it SHIPS (`pc_deformed`
    on the built prim, max over the element's prims).  `_gate_valid = 0`
    cases (D99's band, 4.5's drape) are counted separately, never quietly
    scored as agreeing.
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


# (stage token, the null it must be served by, the nodes on the SPLINE side
#  that must cook, the Python SOPs allowed to cook).
# Kit-side nodes are NOT on the must-cook list: they hang off input 1 and the
# dirtying lever is the SPLINE, so asserting them asserts a cache miss.
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

# D203 - the `output` stage had no row.  Its own tuple because it needs its
# own FIXTURE: the L-shape has a corner (4.3 is N8) so level 1 refuses it; a
# straight flat run is what the guard admits.
OUTPUT_STAGE = (
    ("output", "OUT_final",
     ("pc_deform_gate", "pc_packed_only", "pc_finalize", "pc_out_cast",
      "pc_warn_collate", "guard_envelope", "guard_native"),
     ("config",)),
)

# D250 - same for 13.9 N5's ten DEFORMED-branch nodes, on `N5_RIPPLE` (the
# shape the branch exists for; on `D192_STRAIGHT` `pc_built` legitimately
# bypasses it).  `pc_kit_rank` / `pc_kit_meta` hang off input 1 (see above).
OUTPUT_DEFORMED_STAGE = (
    ("output", "OUT_final",
     ("pc_deform_gate", "pc_deformed_only", "pc_deform_prep", "copy_deformed",
      "pc_deform", "pc_pieces", "pc_built", "pc_piece_key", "pc_order",
      "pc_finalize", "pc_out_cast", "pc_warn_collate", "guard_envelope",
      "guard_native"),
     ("config",)),
)

# --- D208: THE SIX STAGES WITH NO INDEPENDENT EXPECTATION AT ALL (§21.5) ----
# D203 made `native.STAGES` the one declaration both sides read, so a
# mutation of the DECLARATION moves the asset and its oracle together
# (reproduced: `reference` row re-pointed, .hda md5 37f1e344 -> 92b0d456,
# check printed PASS).  These rows give the five uncovered stages the same
# BEHAVIOURAL shape plus a fifth column: nodes that must NOT cook
# (`copy_packed` = native materialiser, `kernel` = reference; exactly one
# cooks on a straight admitted run).  The fixture must be the straight run -
# on the L-shape the guard refuses and the forbidden column is vacuous.
# `config` has no must-cook list (not wired to the spline); its forbidden
# column alone is enough.
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

    The check cycle N-2V2's mutation M4b survived for want of: nothing
    asserted that a native stage IS native.  Two assertions, both needed:
      1. every node the stage is made of advanced its `cookCount`;
      2. no Python SOP outside the named allowance advanced its `cookCount`.
    `rewire` is (stage token, null name) - the mutation lever (M4b applied
    to the built asset).  Returns complaint strings; empty is sound.
    """
    node = root.createNode("pf_polychain", "d192_" + tag)
    geo = hou.Geometry()
    cases.polyline(geo, pts or D192_CORNER, curve_id="D192")
    src = native.feed(root, geo, "D192IN_" + tag)
    # THE DIRTYING LEVER IS THE SPLINE, NOT A PARM (D164: `corner_angle_deg`
    # only dirties `config`, so non-readers would read as idle when sound).
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
        # D208's other half: this was `assert len(moved) == 1`, and under
        # §21.4's M10 the assert ABORTED the run showing 0 [FAIL].  A
        # missing switch input is a COMPLAINT now, not an exception.
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
        # A NAME THAT RESOLVES TO NO NODE IS A COMPLAINT, NOT A SKIP: a
        # renamed node silently turned the forbidden column off (demonstrated
        # - with it blinded, a re-pointed `config` entry drew NO complaint).
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
    # D250 - and the DEFORMED branch, on the shape it exists for.
    bad += stage_is_really_native(root, "sound_def",
                                  rows=OUTPUT_DEFORMED_STAGE, pts=N5_RIPPLE)
    rows = NATIVE_STAGES + OUTPUT_STAGE + OUTPUT_DEFORMED_STAGE
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


def _storage(attribs):
    """(dataType, NUMERIC STORAGE WIDTH, size, isArray) per attribute.

    D246: `dataType()` cannot see a precision change (Float for both
    fpreal32/fpreal64, probed 22.0.398); `numericDataType()` separates them
    and makes the output side of D223's storage-is-contract rule assertable.
    """
    out = {}
    for a in attribs:
        try:
            numeric = str(a.numericDataType())
        except (AttributeError, hou.OperationFailed):
            numeric = "?"
        out[a.name()] = (str(a.dataType()), numeric, a.size(),
                         bool(a.isArrayType()))
    return out


def _columns(geo, attribs, bulk):
    """{name: the whole column}, read in BULK - one call per attribute.

    D246: point attributes used to be compared by NAME alone (a 2.0 m
    `pc_local` mutation left `_first_difference` EMPTY).  Bulk reads because
    a deformed 20 km build carries ~300 000 points.
    """
    out = {}
    for a in attribs:
        name = a.name()
        try:
            if a.isArrayType():
                out[name] = "array"          # no bulk reader; storage is above
                continue
            dt = a.dataType()
            if dt == hou.attribData.String:
                out[name] = list(bulk["s"](name))
            elif dt == hou.attribData.Int:
                out[name] = list(bulk["i"](name))
            elif dt == hou.attribData.Float:
                out[name] = [round(float(v), 9) for v in bulk["f"](name)]
            else:
                out[name] = "unreadable"
        except (hou.OperationFailed, TypeError):
            out[name] = "unreadable"
    return out


def _snapshot(geo):
    """Everything about a polyChain output that a consumer can see.

    Not a digest: a divergence has to be NAMEABLE - which attribute, which
    element, which number.  D246: includes the point attributes' VALUES and
    every attribute's STORAGE WIDTH (see `_columns` / `_storage`).
    """
    names = sorted(a.name() for a in geo.primAttribs())
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
        prim_types=_storage(geo.primAttribs()),
        point_attribs=sorted(a.name() for a in geo.pointAttribs()),
        point_types=_storage(geo.pointAttribs()),
        point_values=_columns(geo, geo.pointAttribs(), {
            "s": geo.pointStringAttribValues,
            "i": geo.pointIntAttribValues,
            "f": geo.pointFloatAttribValues}),
        detail=sorted((a.name(), geo.attribValue(a.name()))
                      for a in geo.globalAttribs()),
        groups=sorted(g.name() for g in geo.primGroups()),
        npoints=len(geo.points()),
        P=[round(float(c), 9) for c in geo.pointFloatAttribValues("P")],
        prims=prims)


def _first_difference(a, b):
    for key in ("prim_attribs", "prim_types", "point_attribs", "point_types",
                "detail", "groups", "npoints"):
        if a[key] != b[key]:
            return "%s: %r != %r" % (key, a[key], b[key])
    # D246 - the point columns, NAMED: which attribute and which element.
    for name in sorted(a["point_values"]):
        u, v = a["point_values"][name], b["point_values"][name]
        if u == v:
            continue
        if not isinstance(u, list) or not isinstance(v, list)                 or len(u) != len(v):
            return "point %s: %r != %r" % (name, u, v)
        for i, (x, y) in enumerate(zip(u, v)):
            if x != y:
                return "point %s[%d]: %r != %r" % (name, i, x, y)
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

    Every case cooks at `Stage = output` and `Stage = reference`, compared
    on EVERYTHING a consumer can see; a guard wrong in either direction is
    worse than none.  The row that matters is the count of cases where the
    guard chose the NATIVE chain, and it is printed.
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
        # THE TALLY IS EVIDENCE, NOT THE ENVELOPE'S OWN CLAIM (D203):
        # `copy_packed` is INSIDE level 2's branch, so its cookCount is what
        # is observed; the envelope is kept as a cross-check.
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
    # What makes the 1.15x refused ceiling honest: a level-1-pass /
    # level-2-refuse build cooks BOTH chains (measured 1.43x at 2 km, 1.54x
    # at 20 km by `bench_guard_fallback`).  The fallback path IS reachable
    # (`GUARD_BEND_LADDER` rows `arc_R20_step0.05`, `arc_R50_step0.1`).
    # Since 13.9 N5 the set is NAMED: `P_crest_bend` (overhanging crest,
    # `pc_frames_transportable` declares it unanswerable) correctly pays the
    # double cook; comparing against a declaration rather than zero keeps
    # the set from GROWING quietly.
    check("no_case_pays_the_guard_fallback",
          sorted(fallback) == sorted(GUARD_FALLBACK_CASES),
          "%d of %d" % (len(fallback), len(built)),
          "cases that pass level 1 and are then REFUSED by level 2, cooking "
          "both chains at the 1.5-1.6x `bench_guard_fallback` measures. "
          "Expected exactly %s, got %s"
          % (list(GUARD_FALLBACK_CASES), sorted(fallback) or "none"))
    check("output_guard_takes_the_native_chain", len(took_native) >= 8,
          len(took_native),
          "cases whose `Stage = output` cook ADVANCED `copy_packed`'s "
          "cookCount - observed, not read off the envelope's own verdict "
          "(D203): %s%s. A guard that never fires would make the row above "
          "vacuous"
          % (", ".join(sorted(took_native)[:8]),
             " ..." if len(took_native) > 8 else ""))
    return took_native


# 13.9 N5's RIPPLE - the one fixture in this file on which the DEFORMED
# branch cooks end to end at `Stage = output`.  49 points, 24 m, no corner, so
# level 1 admits it and `copy_deformed` runs.
N5_RIPPLE = [(0.5 * i, 0.45 * math.sin(i * 0.55), 0.0) for i in range(49)]


def output_snapshot_sees_the_deformed_branch(root):
    """D246 - the parity ORACLE has to be able to see `pc_local`.

    `_snapshot` recorded point attributes by NAME only (a 2.0 m `pc_local`
    mutation left `_first_difference` EMPTY), and `dataType()` cannot see
    fpreal32 vs fpreal64, so `pc_out_cast` losing a cast moved nothing
    (D223's storage-is-contract rule, output side).  Nothing else in the
    tree covers it.  So this row mutates the SHIPPED asset twice and demands
    the snapshot names each one - a sound-build-only row would be satisfied
    by a snapshot that compares nothing, which is what shipped.
    """
    geo = guard_polyline_geo(N5_RIPPLE)
    node = root.createNode("pf_polychain", "snapmut")
    node.setInput(0, native.feed(root, geo, "SNAPMUT_IN"))
    node.allowEditingOfContents()

    def both():
        node.parm("stage").set("output")
        node.cook(force=True)
        took = node.node("copy_deformed").cookCount() > 0
        got = _snapshot(node.geometry())
        node.parm("stage").set("reference")
        node.cook(force=True)
        return took, _first_difference(_snapshot(node.geometry()), got)

    deformed, sound = both()
    nlocal = 0
    node.parm("stage").set("output")
    node.cook(force=True)
    if node.geometry().findPointAttrib("pc_local") is not None:
        nlocal = len(node.geometry().pointFloatAttribValues("pc_local"))

    deform = node.node("pc_deform")
    body = deform.parm("snippet").eval()
    TARGET = "v@pc_local = local;"
    rows, bad = [], []
    if TARGET not in body:
        bad.append("`%s` is not in the shipped `pc_deform`" % TARGET)
    else:
        for label, repl in (("scaled", "v@pc_local = local * 1.5;"),
                            ("zeroed", "v@pc_local = set(0.0, 0.0, 0.0);")):
            deform.parm("snippet").set(body.replace(TARGET, repl))
            _t, diff = both()
            rows.append((label, diff))
            if not diff:
                bad.append("%s: the snapshot saw NOTHING" % label)
        deform.parm("snippet").set(body)

    cast = node.node("pc_out_cast")
    ncasts = cast.parm("numcasts").eval()
    cast.parm("numcasts").set(max(ncasts - 1, 0))
    _t, diff = both()
    cast.parm("numcasts").set(ncasts)
    rows.append(("numcasts %d->%d" % (ncasts, ncasts - 1), diff))
    if not diff:
        bad.append("dropping the last `pc_out_cast` cast moved NOTHING - the "
                   "snapshot cannot see a storage width")
    if not deformed:
        bad.append("`copy_deformed` never cooked, so this fixture never "
                   "reached the branch the row is about")
    if sound:
        bad.append("the UNMUTATED build already differs: %s" % sound)
    if nlocal < 300:
        bad.append("only %d `pc_local` floats on the output - too few for "
                   "this row to mean anything" % nlocal)
    node.destroy()
    check("output_snapshot_sees_the_deformed_branch", not bad,
          "%d pc_local floats / %d mutations" % (nlocal, len(rows)),
          "`_snapshot` has to NAME a change to `pc_local`'s values and to its "
          "STORAGE WIDTH on the shipped asset - both were invisible to the "
          "whole native suite. Mutations: %s. %s"
          % ("; ".join("%s -> %s" % (r[0], (r[1] or "NOTHING")[:60])
                       for r in rows),
             "; ".join(bad[:3]) or "each one named"))


# 13.9 N5 - the scene cases that legitimately pay the level-1-pass /
# level-2-refuse double cook, declared rather than counted (`P_crest_bend`:
# overhanging crest).  A case joining this set is a widening to look at.
GUARD_FALLBACK_CASES = ("P_crest_bend",)


def guard_polyline_geo(pts):
    geo = hou.Geometry()
    cases.polyline(geo, pts, curve_id="GC")
    return geo


def piece_order_key_is_total(root):
    """13.9 N5 - the order key must be UNIQUE per prim and per point.

    Exists because two mutations dropping the within-piece term survived the
    whole suite (136 [PASS] / 0) on Houdini's sort happening to be STABLE.
    So the property (totality) is asserted directly: no two prims and no two
    points may share a key - independent of sort, stability, and shape.
    """
    geo = hou.Geometry()
    cases.polyline(geo, [(0.5 * i, 0.45 * math.sin(i * 0.55), 0.0)
                         for i in range(121)], curve_id="OK")
    node = root.createNode("pf_polychain", "orderkey")
    node.setInput(0, native.feed(root, geo, "OK_IN"))
    node.allowEditingOfContents()
    node.parm("stage").set("output")
    node.cook(force=True)
    key = node.node("pc_piece_key").geometry()
    gate = node.node("pc_deform_gate").geometry()
    ndef = sum(gate.pointIntAttribValues("pc_deformed"))
    pk = list(key.primFloatAttribValues("_pkey"))
    pp = list(key.pointFloatAttribValues("_pkeyp"))
    dup_prim = len(pk) - len(set(pk))
    dup_point = len(pp) - len(set(pp))
    # ...and the fixture has to CONTAIN a multi-prim piece, or a per-piece key
    # would be total by accident.
    biggest = 0
    if ndef:
        from collections import Counter
        biggest = max(Counter(int(v) // 65536 for v in pk).values())
    ok = (ndef > 0 and biggest > 1 and dup_prim == 0 and dup_point == 0)
    node.destroy()
    check("piece_order_key_is_total", ok,
          "%d prims / %d points, %d dup" % (len(pk), len(pp),
                                            dup_prim + dup_point),
          "no two prims share `_pkey` and no two points share `_pkeyp` on a "
          "build with %d deformed pieces whose largest contributes %d prims - "
          "the property the within-piece term exists for, asserted directly "
          "because BOTH mutations that delete it survived the whole suite on "
          "the sort's undocumented stability. Duplicate prim keys: %d; "
          "duplicate point keys: %d"
          % (ndef, biggest, dup_prim, dup_point))


# D242 - the marker-data rows that have to run on the SHIPPED ASSET.
# (label, marker data dict, subject, op, value).  Block 1: non-scalar slots
# the probe cross-type-read as 0.0; block 2: keys `json_dumps` escapes.
# Both measured diverging in BOTH directions on the shipped .hda.
GUARD_MARKER_DATA_ROWS = (
    ("vector_eq", {"v": (1.0, 2.0, 3.0)}, u"markerData:v", "eq", 0.0),
    ("vector_lt", {"v": (1.0, 2.0, 3.0)}, u"markerData:v", "lt", 1.0),
    ("vector_ge", {"v": (1.0, 2.0, 3.0)}, u"markerData:v", "ge", 0.0),
    ("vector_ne", {"v": (1.0, 2.0, 3.0)}, u"markerData:v", "ne", 0.0),
    ("list_eq", {"v": (1.0, 2.0)}, u"markerData:v", "eq", 0.0),
    ("nested_eq", {"v": {"a": 1.0}}, u"markerData:v", "eq", 0.0),
    ("int_control", {"v": 0}, u"markerData:v", "eq", 0.0),
    ("str_control", {"v": "x"}, u"markerData:v", "eq", "x"),
    ("key_quote_num", {u'a"b': u"x"}, u'markerData:a"b', "eq", 0.0),
    ("key_quote_str", {u'a"b': u"x"}, u'markerData:a"b', "eq", u"x"),
    ("key_bslash_num", {u"a\\b": u"x"}, u"markerData:a\\b", "eq", 0.0),
    ("key_bslash_str", {u"a\\b": u"x"}, u"markerData:a\\b", "eq", u"x"),
    ("key_nonascii_num", {u"k\u00e9": u"x"}, u"markerData:k\u00e9", "eq", 0.0),
    ("key_nonascii_str", {u"k\u00e9": u"x"}, u"markerData:k\u00e9", "eq", u"x"),
)


def guard_marker_data_types(root):
    """D242 - `markerData:<k>` on the SHIPPED asset, by value type and by key.

    Exists because a source mutation survived the whole suite (reverting the
    `!unreadable:` branch left 144 [PASS] / 0).  The KEY rows cannot go
    through the rig (string-parm backslash escaping); the asset reads its
    payload off GEOMETRY - the transport the divergence was measured on.
    """
    from polyfactory.polychain import Rule, Style
    from polyfactory.polychain import style as STYLE
    rows, bad = [], []
    for i, (label, data, subject, op, value) in enumerate(
            GUARD_MARKER_DATA_ROWS):
        # THE CURVE ID HAS TO MATCH THE MARKER'S `pc_curve`: with "GC" the
        # marker bound to no curve and all fourteen rows agreed on ten
        # panels - passing under the very mutation this was written to catch.
        geo = hou.Geometry()
        cases.polyline(geo, [(0.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
                       curve_id="S")
        cases.marker(geo, (10.0, 0.0, 0.0), "S", 7, dist=10.0, data=data)
        style = Style("md", 1, 3, rules=[
            Rule("marker:7", "conditional", ["gate"],
                 cond={"subject": subject, "op": op, "value": value}),
            Rule("default", "first", ["panel"])])
        node = root.createNode("pf_polychain", "mdt_%d" % i)
        node.setInput(0, native.feed(root, geo, "MDT_%d" % i))
        sgeo = hou.Geometry()
        STYLE.write(sgeo, style)
        node.setInput(2, native.feed(root, sgeo, "MDS_%d" % i))
        node.allowEditingOfContents()
        node.parm("slot_marker").set("gate")
        node.parm("marker_id").set(7)
        node.parm("stage").set("output")
        node.cook(force=True)
        level1 = int(node.node("pc_envelope").geometry()
                     .attribValue("_native_ok"))
        level2 = int(node.node("pc_envelope2").geometry()
                     .attribValue("_native_ok2")) if level1 else 0
        got = _snapshot(node.geometry())
        node.parm("stage").set("reference")
        node.cook(force=True)
        diff = _first_difference(_snapshot(node.geometry()), got)
        gated = 0
        node.parm("stage").set("output")
        node.cook(force=True)
        a = node.geometry().findPrimAttrib("pc_module")
        if a is not None:
            gated = sum(1 for pr in node.geometry().prims()
                        if pr.attribValue("pc_module") == "gate")
        rows.append((label, level1, level2, gated))
        if diff:
            bad.append("%s: %s" % (label, diff[:90]))
        node.destroy()
    native_n = sum(1 for r in rows if r[2])
    # ...and at least one row must actually PLACE the gate, or the marker
    # never bound and every row is a comparison of two identical fences.
    if not any(r[3] for r in rows):
        bad.append("no row placed a gate at all - the marker did not bind to "
                   "the curve, so nothing here reached the read")
    if native_n < len(rows):
        bad.append("only %d of %d rows took the NATIVE chain - a row the "
                   "guard refuses proves nothing about the read"
                   % (native_n, len(rows)))
    check("guard_marker_data_types", not bad,
          "%d rows, %d native" % (len(rows), native_n),
          "a `markerData:` slot that is a vector, a list or a nested dict, and "
          "a KEY carrying a quote, a backslash or a non-ASCII character, on "
          "the SHIPPED asset with a real style payload: `Stage = output` "
          "against `Stage = reference`, everything a consumer can see. Before "
          "D242 nine value rows and six key rows diverged, in BOTH directions "
          "- a gate fired that nobody asked for, and a gate dropped that was "
          "asked for. %s"
          % ("; ".join(bad[:3]) or "all identical, all native"))


def native_reach(root):
    """WHO cooks on `Stage = output` now.

    Used to assert the opposite (18.2: shipped default was 88-95 % Python).
    Now: the native chain runs on a build inside the envelope AND `kernel`
    does not - both directions, since either alone is an accident away from
    passing.
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


# 13.9 N6 - THE DECIDING EXPERIMENT FOR THE CONFORM PORT, COMMITTED.
# Guards a DECISION, not a feature: 4.5 is the largest refused class
# (perfMon: 300 conformed streets 3 645 ms Python, curved 4 225 ms, vs
# 806 ms cornered).  A native conform (VEX `intersect()`) would be a THIRD
# implementation of `conform.Surface.drop`.  As doubles the two disagree
# (3.8e-07 m fixture, 9.4e-04 m at 20 km) - entirely in x/z, because
# `hou.Geometry.intersect` returns float32 coordinates (D111 from the other
# side).  Answer: YES, on condition - read the drop off the AXIS COMPONENT,
# rebuild the position from the query, and compare in float32.
CONFORM_DROP_VEX = r'''
// `conform.Surface.drop`, in VEX. Down-axis, then back no further than the
// hit already found, nearest wins, ties go DOWN-axis (D70).
vector a = v@_axis;
vector up = -a;
vector q = v@_q;
float far = f@_far;
vector p0, uvw0, p1, uvw1;
int h0 = intersect(1, q, a * far, p0, uvw0);
float d0 = (h0 >= 0) ? length(p0 - q) : -1.0;
int h1 = intersect(1, q, up * ((d0 >= 0.0) ? d0 : far), p1, uvw1);
float d1 = (h1 >= 0) ? length(p1 - q) : -1.0;
vector best = q;
int hit = 0;
if (h0 >= 0) { best = p0; hit = 1; }
if (h1 >= 0 && (h0 < 0 || d1 < d0 - 1e-9)) { best = p1; hit = 1; }
// D111's reconstruction: the hit POSITION is quantised at the magnitude of a
// WORLD COORDINATE, the drop is quantised at the magnitude of a DROP.
if (hit) { float t = dot(best - q, a); best = q + a * t; }
v@_hitP = best;
i@_hit  = hit;
'''

# what survives float32 `P` storage.  Both sides round into the same 24 bits,
# so anything above this is a DIFFERENT number in the storage the output ships.
CONFORM_DROP_CEILING_M = 1e-12
# D247 - the RAW double difference the f32 row was hiding: `f32()` on both
# sides made the 1e-12 m ceiling really a half-float32-ULP tolerance
# (~0.98 mm at 20 km); ramp_20km printed 0.000e+00 on a genuine 9.375e-04 m
# disagreement.  Re-measured raw: flat 3.815e-07 m, irrational 4.578e-07 m,
# ramp_20km 9.375e-04 m.  Not a bug: `intersect()` is a float32 ray test;
# worst is 4.93e-08 relative = 0.83 float32 ULP, so the raw row is asserted
# RELATIVE (two ULP) and the f32 row keeps its exact ceiling.  WHAT THE RAW
# ROW CANNOT DO: it is not an independent detector (f32 rounding separates
# at 2^-25, four times tighter than the 2-ULP ceiling) - it REPORTS the real
# number and is deterministic where f32 detection is a last-bit coin toss.
# Registered mutation: `conform_drop_biased` (tests/polychain/mutations.py),
# biases the drop by 1e-5 m.
CONFORM_DROP_REL_CEILING = 1.192e-7      # 2 x 2^-24


def _conform_sheet(y, x0, x1, z0, z1, n=8, slope=0.0, reverse=False):
    geo = hou.Geometry()
    pts = {}
    for i in range(n + 1):
        for j in range(n + 1):
            x = x0 + (x1 - x0) * i / float(n)
            z = z0 + (z1 - z0) * j / float(n)
            pt = geo.createPoint()
            pt.setPosition((x, y + slope * x, z))
            pts[(i, j)] = pt
    for i in range(n):
        for j in range(n):
            poly = geo.createPolygon()
            ring = [pts[(i, j)], pts[(i, j + 1)],
                    pts[(i + 1, j + 1)], pts[(i + 1, j)]]
            for pt in (reversed(ring) if reverse else ring):
                poly.addVertex(pt)
    return geo


def conform_drop_is_portable_to_vex(root):
    """13.9 N6 - can VEX's `intersect()` reproduce `conform.Surface.drop`?

    Five surfaces, one per past drop-breaker: exact-tie flat sheet, rational
    slope, IRRATIONAL slope (D111), REVERSED winding (D52), and the same
    irrational ramp at 20 km (float32 world coordinates 2 mm apart).
    """
    surfaces = (
        ("flat", _conform_sheet(0.0, -5.0, 25.0, -5.0, 5.0),
         [(0.3 * i, 3.0, 0.0) for i in range(40)]),
        ("ramp_25pct", _conform_sheet(0.0, -5.0, 25.0, -5.0, 5.0, slope=0.25),
         [(0.3 * i, 9.0, 0.5) for i in range(40)]),
        ("irrational",
         _conform_sheet(0.0, -5.0, 25.0, -5.0, 5.0, slope=1.0 / 7.0),
         [(0.31 * i, 9.0, 0.37) for i in range(40)]),
        ("reversed",
         _conform_sheet(0.0, -5.0, 25.0, -5.0, 5.0, slope=0.25, reverse=True),
         [(0.3 * i, 9.0, 0.5) for i in range(40)]),
        ("ramp_20km",
         _conform_sheet(0.0, -5.0, 20005.0, -5.0, 5.0, slope=1.0 / 7.0, n=64),
         [(19000.0 + 0.31 * i, 4000.0, 0.37) for i in range(40)]),
    )
    rows, bad = [], []
    nq = 0
    for label, surf, qs in surfaces:
        py = CONFORM.Surface(surf, (0.0, -1.0, 0.0))
        want = [py.drop(q) for q in qs]
        cloud = hou.Geometry()
        cloud.addAttrib(hou.attribType.Point, "_q", (0.0, 0.0, 0.0))
        cloud.addAttrib(hou.attribType.Point, "_axis", (0.0, -1.0, 0.0))
        cloud.addAttrib(hou.attribType.Point, "_far", 0.0)
        for q in qs:
            pt = cloud.createPoint()
            pt.setPosition(q)
            pt.setAttribValue("_q", q)
            # `Surface.drop`'s own per-POINT reach (D70), not a magic number.
            pt.setAttribValue("_far", math.sqrt(
                sum((q[i] - py.centre[i]) ** 2 for i in range(3)))
                + py.radius)
        w = root.createNode("attribwrangle", "cdrop_" + label)
        w.parm("class").set(2)
        w.parm("vex_precision").set("64")
        w.parm("snippet").set(CONFORM_DROP_VEX)
        w.setInput(0, native.feed(root, cloud, "CDQ_" + label))
        w.setInput(1, native.feed(root, surf, "CDS_" + label))
        got = w.geometry()
        worst = 0.0
        worst_raw = 0.0
        worst_rel = 0.0
        misses = 0
        for i, pt in enumerate(got.points()):
            gp = pt.attribValue("_hitP")
            if int(pt.attribValue("_hit")) != int(want[i][2]):
                misses += 1
                continue
            worst = max(worst, max(abs(f32(gp[k]) - f32(want[i][0][k]))
                                   for k in range(3)))
            # D247 - the RAW double difference, and its size RELATIVE to the
            # coordinate it is a difference of.
            raw = max(abs(float(gp[k]) - float(want[i][0][k]))
                      for k in range(3))
            scale = max(abs(float(c)) for c in qs[i]) or 1.0
            worst_raw = max(worst_raw, raw)
            worst_rel = max(worst_rel, raw / scale)
        nq += len(qs)
        rows.append((label, worst, misses, worst_raw, worst_rel))
        if misses:
            bad.append("%s: %d hit-flag mismatches" % (label, misses))
        if worst > CONFORM_DROP_CEILING_M:
            bad.append("%s: %.3e m > %.3e m in float32 storage"
                       % (label, worst, CONFORM_DROP_CEILING_M))
        if worst_rel > CONFORM_DROP_REL_CEILING:
            bad.append("%s: raw %.3e m is %.3e RELATIVE, over the %.3e "
                       "float32-ULP ceiling - the two implementations "
                       "genuinely disagree, and the f32 row cannot see it "
                       "until it crosses a storage bucket"
                       % (label, worst_raw, worst_rel,
                          CONFORM_DROP_REL_CEILING))
        w.destroy()
    check("conform_drop_is_portable_to_vex", not bad,
          "%d queries, f32 %.3e m / raw %.3e rel"
          % (nq, max(r[1] for r in rows), max(r[4] for r in rows)),
          "13.9 N6's deciding experiment: VEX `intersect()` against "
          "`conform.Surface.drop`, read off the AXIS COMPONENT and rebuilt "
          "from the query (D111's reconstruction). TWO ceilings (D247): in "
          "float32 `P` storage %.0e m, and RAW as a fraction of the query "
          "magnitude %.3e (two float32 ULP - `intersect()` is a float32 ray "
          "test, so the raw agreement cannot be better than that and the f32 "
          "row was hiding a 9.4e-4 m disagreement at 20 km). Rows "
          "(f32 / raw m / raw rel): %s. %s"
          % (CONFORM_DROP_CEILING_M, CONFORM_DROP_REL_CEILING,
             "; ".join("%s %.3e / %.3e / %.3e" % (r[0], r[1], r[3], r[4])
                       for r in rows),
             "; ".join(bad[:3]) or "the drape is a PORT, not a rewrite - and "
             "the raw number is now on the record"))


def main():
    if not os.path.exists(HDA_PATH):
        print("no HDA at %s - run devScripts/create_pf_polychain_hda.py"
              % HDA_PATH)
        sys.exit(1)
    hou.hda.installFile(HDA_PATH)
    root = hou.node("/obj").createNode("geo", "polychain_native")
    built = cases.build_all()
    # The three shapes the scene suite structurally cannot contain: a fused
    # junction, a marker inside a prim, a duplicated id with a marker.
    built.update(cases.topology_cases())

    print("\n=== 1. decompose - native vs the reference, %d cases ==="
          % len(built))
    decompose_parity(root, built)

    print("\n=== 2. the three trials, 64-bit transport, the conform drop ===")
    trial_parity(root)
    sixty_four_bit(root)
    conform_drop_is_portable_to_vex(root)

    print("\n=== 3. the fitting solve, on the fixtures ===")
    plan_fixture_parity(root)

    print("\n=== 4. the mutation test ===")
    mutation(root, built)

    print("\n=== 5. every stage is really native, on the shipped asset ===")
    native_stage_check(root)
    native_reach(root)

    print("\n=== 6. the guard on `Stage = output` ===")
    output_guard_parity(root, built)
    output_snapshot_sees_the_deformed_branch(root)
    gate_parity(root, built)
    piece_order_key_is_total(root)
    guard_marker_data_types(root)

    native.cleanup()
    failed = [r for r in RESULTS if not r[1]]
    print("\n%d failing checks" % len(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
