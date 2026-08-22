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
    n_curves = n_corners = n_markers = 0
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

        # (a) the id rule, written twice - once in VEX, once in Python
        ref_index = H.curve_prim_index(case["curve"])
        for prim in out.prims():
            got = prim.attribValue("pc_curve_id_r")
            if ref_index.get(got) != prim.number():
                bad_id.append((name, prim.number(), got))
        by_id = dict((p.attribValue("pc_curve_id_r"), p) for p in out.prims())

        pc_s = out.pointFloatAttribValues("pc_s")
        turn = out.pointFloatAttribValues("pc_turn_deg")
        corner = out.pointIntAttribValues("pc_iscorner")
        degen = out.pointIntAttribValues("pc_corner_degen")
        for curve in curves:
            n_curves += 1
            prim = by_id.get(str(curve.curve_id))
            if prim is None:
                bad_id.append((name, str(curve.curve_id), "no prim"))
                continue
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

        # (b) markers
        ref_m = {}
        for curve in curves:
            for row in D.resolve_markers(curve, markers):
                ref_m.setdefault(str(curve.curve_id), []).append(row)
        if ref_m:
            got_m = {}
            has = out.findPointAttrib("pc_marker") is not None
            for point in out.points():
                if has and point.attribValue("pc_marker") == 1:
                    got_m.setdefault(str(point.attribValue("pc_curve")),
                                     []).append(point)
            for cid, rows in ref_m.items():
                mine = sorted(got_m.get(cid, []),
                              key=lambda p: p.attribValue("pc_s"))
                if len(mine) != len(rows):
                    bad_marker.append((name, cid, len(rows), len(mine)))
                    continue
                for row, point in zip(sorted(rows, key=lambda d: d["s"]),
                                      mine):
                    n_markers += 1
                    worst_marker = max(worst_marker,
                                       abs(row["s"] - point.attribValue("pc_s")))
        sub.destroy()

    check("native_id_parity", not bad_id, len(bad_id),
          "the VEX id rule vs hda.curve_prim_index over %d curves; %s"
          % (n_curves, bad_id[:2] or "identical"))
    # EXACT, no slack: 64-bit VEX doing the same additions in the same order
    # as 64-bit Python. If this needs a tolerance the accumulation order
    # differs, and that is a defect, not float noise (13.8).
    check("decompose_arclength_parity", worst_s == 0.0, "%.3e m" % worst_s,
          "worst |d pc_s| over %d curves, all 89 cases (ceiling 0.0)"
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
          "worst |d marker s| over %d markers; %s"
          % (n_markers, bad_marker[:2] or "counts identical"))


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
        # ⚠️ THE SPANS ARE ROUNDED TO FLOAT32 ON *BOTH* SIDES, deliberately.
        # The rig carries the plan to the wrangle through a .bgeo point
        # attribute, which is float32 storage; asking the reference the
        # question in float64 and the wrangle the same question in float32
        # measures the transport, not the arithmetic. Rounding both isolates
        # the arithmetic, which is what this check is for - and the transport
        # is covered separately by `native_intermediates_are_64bit`.
        sa, sb = f32(sa), f32(sb)
        matrix = real_pt(proto, path, sa, sb, zmode, up_ref, base_y, None,
                         yscale)
        calls.append({"pidx": getattr(path, "_pc_pidx", -1),
                      "conform": isinstance(path, CONFORM.ConformPath),
                      "plen": proto.length, "pax": proto.ax,
                      "sa": sa, "sb": sb, "zmode": zmode,
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
    plan.setPointFloatAttribValues("pc_s0r", [r["sa"] for r in rows])
    plan.setPointFloatAttribValues("pc_s1r", [r["sb"] for r in rows])
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
                    worst_lin = max(worst_lin,
                                    abs(xform[i * 9 + r * 3 + c]
                                        - matrix.at(r, c)))
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
    check("mutation_pc_frames", worst > 0.0, "%.3e" % worst,
          "a 1e-7 relative scale error over %d calls turns the 3x3 red"
          % total)

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
    node = native.wrangle(sub, "pc_arclength", "primitive", "pc_arclength")
    node.parm("snippet").set(broken)
    node.setInput(0, src)
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
    node = root.createNode("pf_polychain", "readable")
    node.setInput(0, spline)

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
    tokens = list(node.parm("stage").parmTemplate().menuItems())
    empty = []
    for token in tokens:
        node.parm("stage").set(token)
        node.cook(force=True)
        geo = node.geometry()
        if not (len(geo.points()) or len(geo.prims())):
            empty.append(token)
        if node.errors():
            empty.append(token + "(error)")
    node.parm("stage").set(tokens[0])
    check("stage_menu_reaches_every_stage", not empty, len(tokens),
          "stages that cook to nothing: %s" % (", ".join(empty) or "none"))

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
        from polyfactory.polychain import decompose as D
        curves, markers = P.read_curves(geo)
        ref_best = None
        for _ in range(3):
            start = time.time()
            for curve in curves:
                D._clean(curve)
                D.resolve_corners(curve, DEFAULTS)
                D.resolve_markers(curve, markers)
                curve._cum = None           # the cache would make run 2 free
            elapsed = time.time() - start
            ref_best = elapsed if ref_best is None else min(ref_best, elapsed)
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
              "%.4f s  (%.2fx)" % (best, ref_best / best if best else 0.0),
              "%d curves / %d points through %d native nodes, against the "
              "reference's %.4f s for the same three answers (ceiling 1.5x "
              "slower - no speedup is claimed yet)"
              % (len(out.prims()), len(out.points()), len(nodes), ref_best))
        sub.destroy()

    # `sop_cooks_per_build` - THE NEW TRIPWIRE (13.8). A network's failure
    # mode is cook count the way the Python's was wrapper count, and the
    # specific thing that must stay true through nine more build-order items
    # is this: AN ARTIST WHO NEVER TOUCHES THE STAGE MENU PAYS NOTHING FOR
    # THE REBUILD. A Switch SOP cooks only its selected input, so on the
    # Output stage every native node must sit at zero.
    #
    # ⚠️ MEASURED WITHOUT `force`, because `cook(force=True)` on a subnet
    # cooks the whole subnet and reports every node as busy - which is a
    # measurement of the flag, not of the graph. Reading `.geometry()` is the
    # cook an artist actually causes.
    fresh = root.createNode("pf_polychain", "cook_count")
    fresh.setInput(0, node.input(0))
    fresh.geometry()
    counts = dict((c.name(), c.cookCount()) for c in fresh.children())
    busy = sorted(n for n, c in counts.items()
                  if c and (n.startswith("pc_") or n == "config"))
    check("sop_cooks_per_build", not busy,
          "%d/%d" % (len(busy), len(counts)),
          "native nodes that cooked on the Output stage: %s (ceiling 0 - a "
          "switch cooks one branch, so the rebuild is free until you look "
          "at it)" % (", ".join(busy) or "none"))

    # ...and the other half of the same sentence: the stages DO cook when
    # they are asked for, which is what stops the check above passing on a
    # graph whose native branch is simply disconnected.
    fresh.parm("stage").set("sections")
    fresh.geometry()
    awake = sorted(n for n in counts
                   if n.startswith("pc_") and fresh.node(n).cookCount())
    check("stage_menu_actually_cooks_the_stage", len(awake) >= 5, len(awake),
          "native nodes that cooked once Stage = sections: %s"
          % (", ".join(awake) or "none"))


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
    thirty_two = [n for n, node in nodes.items()
                  if node.parm("vex_precision").eval() != "64"]
    check("native_intermediates_are_64bit",
          survived == 0.0 and crossed == 0.0 and not thirty_two,
          "%.3e / %.3e" % (survived, crossed),
          "a 20 km value written by a 64-bit wrangle and READ BY THE NEXT "
          "NODE, error on both sides; 32-bit wrangles: %s"
          % (", ".join(thirty_two) or "none"))
    sub.destroy()


def main():
    if not os.path.exists(HDA_PATH):
        print("no HDA at %s - run devScripts/create_pf_polychain_hda.py"
              % HDA_PATH)
        sys.exit(1)
    root = hou.node("/obj").createNode("geo", "polychain_native")
    built = cases.build_all()

    print("\n=== 1. 4.1 DECOMPOSE - native vs the reference, %d cases ==="
          % len(built))
    decompose_parity(root, built)

    print("\n=== 2. 4.4 pc_frames - native vs place._packed_transform ===")
    worst, bad_pos, total, zmodes = frames_parity(root, built)
    frames_ulp = FRAMES_ULP
    # EXACT. Both sides are 64-bit arithmetic over the same span, and the
    # rig rounds the span on both sides so this measures the maths alone.
    check("frames_linear_parity", worst == 0.0, "%.3e" % worst,
          "worst |d 3x3| over %d real calls, z-modes %s (ceiling 0.0)"
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
    check("frames_position_parity", frames_ulp[0] <= 1.0,
          "%d / %d, %.2f ULP" % (bad_pos, total * 3, frames_ulp[0]),
          "P components not bit-identical to f32(reference), and the worst "
          "one in float32 ULP (ceiling 1.0 ULP)")

    print("\n=== 3. D113's three trials ===")
    trial_parity(root)
    sixty_four_bit(root)

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
