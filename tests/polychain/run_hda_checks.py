"""The `pf_polychain` HDA itself, cooked headlessly - 5 and gate PC-G4.

    hython tests/polychain/run_hda_checks.py

`run_scene_checks.py` measures the KERNEL by calling `place.build` directly.
Nothing there touches a node, a parameter or an input wire, so every defect
that lives in the asset - a parm that reads nothing, an input wired to the
wrong index, a style payload that does not actually override - is invisible to
it. This file is that missing half, and it is deliberately small: it asserts
the WIRING, not the geometry, because the geometry already has 73 cases.

What it asserts, in order:
  1. defaults alone build a fence (6's standalone-usability floor - a curve
     into input 1 and NOTHING else, no kit, no style, no surface);
  2. the node agrees with the kernel called directly on the same style;
  3. every input is wired to the index 2.2 says it is (kit, style, surface);
  4. PC-G4 - a STYLE PAYLOAD on input 3 overrides the parms entirely, proved
     by SWEEPING every parm on the page while it is wired (ids and positions
     both), plus (4b) a payload that loses every rule degrading inside the
     pipeline face and (4c) D88 s marker slot authored on the page;
  5. the proxy LOD keeps a 10k-piece run interactive (5's own acceptance
     criterion, in seconds);
  6. the plan display draws one point per piece;
  7. a malformed kit file and an empty spline warn instead of erroring;
  8. artist_ui 6's BINDING UX LAW, on the built asset (D96).
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cases                                                     # noqa: E402
import hou                                                       # noqa: E402
from polyfactory.polychain import Params, Rule, Style             # noqa: E402
from polyfactory.polychain import hda as H                        # noqa: E402
from polyfactory.polychain import kit as K                        # noqa: E402
from polyfactory.polychain import place as P                      # noqa: E402
from polyfactory.polychain import style as S                      # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
HDA_PATH = os.path.join(REPO, "polyfactory", "otls",
                        "pf_polychain.hda").replace("\\", "/")

RESULTS = []

# The parms a style payload does NOT own, and why: `display` and
# `show_warnings` are viewing decisions (D81/D82), `kitfile` is the KIT lane -
# input 2's fallback - and a payload carries rules and params, never a kit.
PARM_LANE_EXEMPT = ("display", "show_warnings", "kitfile")


def _fingerprint(node):
    """(element ids, rounded point positions) - what may not move."""
    geo = node.geometry()
    ids = sorted(p.attribValue("pc_elem_id") for p in geo.prims())
    pos = sorted((round(v, 5) for v in geo.pointFloatAttribValues("P")))
    return (ids, pos)


def _nudge(parm):
    """Move `parm` to a DIFFERENT value. False when there is nowhere to go."""
    tpl = parm.parmTemplate()
    if isinstance(tpl, hou.ToggleParmTemplate):
        parm.set(0 if parm.eval() else 1)
        return True
    if isinstance(tpl, hou.IntParmTemplate):
        parm.set(int(parm.eval()) + 1)
        return True
    if isinstance(tpl, hou.FloatParmTemplate):
        parm.set(parm.eval() + 0.37)
        return True
    if isinstance(tpl, hou.StringParmTemplate):
        items = list(tpl.menuItems())
        if items:
            cur = parm.evalAsString()
            for item in items:
                if item != cur:
                    parm.set(item)
                    return True
            return False
        parm.set((parm.evalAsString() + " gate").strip())
        return True
    return False


def check(name, ok, value="", detail=""):
    RESULTS.append((name, bool(ok), value, detail))
    print("  [%s] %-28s %s  %s" % ("PASS" if ok else "FAIL", name, value,
                                   detail))
    return ok


def curve_node(geo_node, name, points, closed=False):
    node = geo_node.createNode("python", name)
    node.parm("python").set(
        "import hou\n"
        "geo = hou.pwd().geometry()\n"
        "poly = geo.createPolygon(%r)\n"
        "for p in %r:\n"
        "    pt = geo.createPoint()\n"
        "    pt.setPosition(p)\n"
        "    poly.addVertex(pt)\n" % (closed, [tuple(p) for p in points]))
    return node


def geo_from(node):
    return node.geometry()


def main():
    if not os.path.exists(HDA_PATH):
        print("no HDA at %s - run devScripts/create_pf_polychain_hda.py"
              % HDA_PATH)
        sys.exit(1)
    hou.hda.installFile(HDA_PATH)
    hou.putenv("POLYFACTORY", os.path.join(REPO, "polyfactory")
               .replace("\\", "/"))
    obj = hou.node("/obj")
    geo_node = obj.createNode("geo", "polychain_hda_gate")

    spline = curve_node(geo_node, "spline",
                        [(0, 0, 0), (12, 0, 0), (12, 0, 8), (0, 0, 8)],
                        closed=True)
    node = geo_node.createNode("pf_polychain", "chain")
    node.setInput(0, spline)

    # ---- 1. defaults alone build a fence ---------------------------------
    print("\n=== 1. defaults, nothing wired but a curve ===")
    t0 = time.time()
    geo = node.geometry()
    dt = time.time() - t0
    prims = len(geo.prims())
    packed = len([p for p in geo.prims()
                  if p.type() == hou.primType.PackedGeometry])
    modules = sorted(set(p.attribValue("pc_module") for p in geo.prims()))
    check("starter_fence_prims", prims > 20, prims, "%.2f s" % dt)
    check("starter_fence_packed", packed > 0, packed, "of %d" % prims)
    # ⚠️ NO `corner_post` HERE, and that is D36 rather than a gap: BEND mode
    # welds the four sections of a closed rectangle into one ring, so no
    # corner assembly is placed at all. The corner slot is asserted below,
    # under the corner mode that uses it.
    check("starter_fence_modules", set(modules) == set(["post", "panel"]),
          ",".join(modules), "from the built-in starter kit")
    node.parm("corner_mode").set("miter")
    mit = sorted(set(p.attribValue("pc_module") for p in node.geometry()
                     .prims()))
    check("starter_fence_corners", "corner_post" in mit, ",".join(mit),
          "the corner slot fires in miter mode")
    node.parm("corner_mode").set("bend")
    check("no_errors", not node.errors(), len(node.errors()),
          "; ".join(node.errors())[:120])

    # ---- 2. the node agrees with the kernel ------------------------------
    print("\n=== 2. the node agrees with place.build on the same style ===")
    style = H.style_from_parms(node)
    kit_geo = H.kit_geometry(node)
    direct, report = P.build(geo_from(spline), kit_geo, style)
    a = sorted(p.attribValue("pc_elem_id") for p in geo.prims())
    b = sorted(p.attribValue("pc_elem_id") for p in direct.prims())
    check("node_matches_kernel", a == b, len(a), "vs %d kernel elements"
          % len(b))

    # ---- 3. every input at the index 2.2 says ----------------------------
    print("\n=== 3. input wiring (2.2) ===")
    kit_node = geo_node.createNode("python", "kit_in")
    kit_node.parm("python").set(
        "import hou, sys\n"
        "from polyfactory.polychain import kit as K\n"
        "geo = hou.pwd().geometry()\n"
        "geo.merge(K.starter_kit())\n"
        "for pt in geo.points():\n"
        "    if pt.attribValue('pc_name') == 'panel':\n"
        "        pt.setAttribValue('pc_name', 'plank')\n")
    node.setInput(1, kit_node)
    node.parm("slot_default").set("post plank")
    got = sorted(set(p.attribValue("pc_module") for p in node.geometry()
                     .prims()))
    check("input2_is_the_kit", "plank" in got, ",".join(got),
          "the kit on input 2 renamed panel->plank")
    node.setInput(1, None)
    node.parm("slot_default").set("post panel")

    surf = geo_node.createNode("grid", "surface")
    surf.parmTuple("size").set((60.0, 60.0))
    surf.parmTuple("t").set((6.0, -2.5, 4.0))
    surf.parm("rows").set(20)
    surf.parm("cols").set(20)
    surf.parm("orient").set(2)                      # ZX - a ground plane
    node.setInput(3, surf)
    lows = [pt.position()[1] for pt in node.geometry().points()]
    check("input4_is_the_surface", min(lows) < -2.0, round(min(lows), 3),
          "the run dropped onto a grid at y = -2.5")
    node.setInput(3, None)

    # ---- 4. PC-G4: the payload overrides the parms ------------------------
    print("\n=== 4. PC-G4 - a style payload on input 3 overrides the parms ===")
    payload_style = Style("pipeline", 1, 11, rules=[
        Rule("default", "first", ["gate"]),
        Rule("corner", "first", ["corner_post"])],
        params=Params(fill="adaptive", corner_mode="miter"))
    payload = geo_node.createNode("python", "style_in")
    payload.parm("python").set(
        "import hou\n"
        "from polyfactory.polychain import Params, Rule, Style\n"
        "from polyfactory.polychain import style as S\n"
        "st = Style('pipeline', 1, 11, rules=[\n"
        "    Rule('default', 'first', ['gate']),\n"
        "    Rule('corner', 'first', ['corner_post'])],\n"
        "    params=Params(fill='adaptive', corner_mode='miter'))\n"
        "S.write(hou.pwd().geometry(), st)\n")
    node.setInput(2, payload)
    with_payload = node.geometry()
    mods = sorted(set(p.attribValue("pc_module") for p in with_payload.prims()))
    styles = sorted(set(p.attribValue("pc_style")
                        for p in with_payload.prims()))
    check("payload_overrides_modules", mods == ["corner_post", "gate"],
          ",".join(mods), "the parms still say post/panel")
    check("payload_overrides_styleid", styles == ["pipeline"],
          ",".join(styles), "pc_style comes from the payload")
    direct2, _r = P.build(geo_from(spline), H.kit_geometry(node),
                          payload_style)
    ids_a = sorted(p.attribValue("pc_elem_id") for p in with_payload.prims())
    ids_b = sorted(p.attribValue("pc_elem_id") for p in direct2.prims())
    check("payload_matches_kernel", ids_a == ids_b, len(ids_a),
          "vs %d built from the Style object" % len(ids_b))
    # ...and the parms are not consulted AT ALL while it is wired (D77).
    # ⚠️ EVERY PARM ON THE PAGE, and both the ids AND the POSITIONS. The first
    # version of this moved `fill` and `seed` only and compared sorted ids, so
    # it missed `padding` entirely: the gap parm was applied to the kit
    # unconditionally, and the same payload built 6 prims at 0.0 and 5 at 0.8
    # on the same node. One payload, two fences - which is the exact property
    # D77 says the pipeline face exists to guarantee (fixed by D91).
    # ⚠ D107 - AND THE FIXTURE ABOVE IS WHY THIS SWEEP CAN SEE IT. Under
    # `fill="scale"` the payload's fence does not move for ANY `pc_pad`:
    # measured on this build, `gate.pad` goes 0.0 -> 0.185 -> 0.4 while the
    # output stays 44 prims, 12 elements and an IDENTICAL point sum, so with
    # D91 reverted the sweep still reported `moved: none`. The one word
    # `adaptive` is what makes the D91 class of defect reachable: the same
    # revert then reports `moved: padding`. A fill mode that cannot express
    # a gap cannot test a gap parm.
    base_ids, base_pos = _fingerprint(node)
    moved = []
    for parm in sorted(node.parms(), key=lambda q: q.name()):
        if parm.name() in PARM_LANE_EXEMPT:
            continue
        was = parm.eval()
        if not _nudge(parm):
            continue
        got_ids, got_pos = _fingerprint(node)
        if got_ids != base_ids or got_pos != base_pos:
            moved.append(parm.name())
        parm.set(was)
    check("parms_inert_under_payload", not moved, len(base_ids),
          "swept %d parms; moved: %s" % (len(node.parms()),
                                         ",".join(moved) or "none"))
    node.setInput(2, None)

    # ---- 4b. a payload whose rules ALL drop stays in the PIPELINE face -----
    print("\n=== 4b. a payload with no usable rule degrades in place (D92) ===")
    junk = geo_node.createNode("python", "style_junk")
    junk.parm("python").set(
        "import hou\n"
        "from polyfactory.polychain import Params, Rule, Style\n"
        "from polyfactory.polychain import style as S\n"
        "st = Style('pipeline_junk', 1, 4,\n"
        "           rules=[Rule('defualt', 'first', ['gate'])])\n"
        "S.write(hou.pwd().geometry(), st)\n")
    node.setInput(2, junk)
    junk_geo = node.geometry()
    inner = node.node("kernel").warnings()
    check("junk_payload_builds_nothing", len(junk_geo.prims()) == 0,
          len(junk_geo.prims()),
          "%d warnings: %s" % (len(inner), (inner or ("",))[0][:70]))
    node.setInput(2, None)

    # ---- 4c. D88 - the marker slot is reachable from the PARM face ---------
    print("\n=== 4c. a gate on a marker, authored on the page (PC-G1) ===")
    marked = geo_node.createNode("python", "marked_spline")
    marked.parm("python").set(
        "import hou\n"
        "geo = hou.pwd().geometry()\n"
        "poly = geo.createPolygon(False)\n"
        "for p in [(0,0,0), (20,0,0)]:\n"
        "    pt = geo.createPoint()\n"
        "    pt.setPosition(p)\n"
        "    poly.addVertex(pt)\n"
        "geo.addAttrib(hou.attribType.Point, 'pc_marker', 0)\n"
        "geo.addAttrib(hou.attribType.Point, 'pc_marker_id', 0)\n"
        "geo.addAttrib(hou.attribType.Point, 'pc_u', 0.0)\n"
        "geo.addAttrib(hou.attribType.Point, 'pc_curve', '')\n"
        "geo.addAttrib(hou.attribType.Prim, 'pc_curve_id', '')\n"
        "poly.setAttribValue('pc_curve_id', 'M')\n"
        "m = geo.createPoint()\n"
        "m.setPosition((9.0, 0.0, 0.0))\n"
        "m.setAttribValue('pc_marker', 1)\n"
        "m.setAttribValue('pc_marker_id', 1)\n"
        "m.setAttribValue('pc_u', 0.45)\n"
        "m.setAttribValue('pc_curve', 'M')\n")
    mk = geo_node.createNode("pf_polychain", "chain_marker")
    mk.setInput(0, marked)
    mk.cook(force=True)
    silent = mk.node("kernel").warnings()
    check("unread_marker_warns",
          any("marker" in w for w in silent), len(silent),
          (silent or ("",))[0][:80])
    mk.parm("slot_marker").set("gate")
    mk.parm("marker_id").set(1)
    mods = sorted(set(p.attribValue("pc_module") for p in mk.geometry().prims()))
    gates = [p for p in mk.geometry().prims()
             if p.attribValue("pc_module") == "gate"]
    check("marker_slot_on_the_page", "gate" in mods, ",".join(mods),
          "%d gate element(s) at the marker" % len(gates))
    check("marker_read_is_silent",
          not any("marker" in w for w in mk.node("kernel").warnings()),
          len(mk.node("kernel").warnings()), "the warning stops once read")

    # ---- 5. the proxy LOD, at 10k pieces ---------------------------------
    print("\n=== 5. proxy LOD at scale (5's acceptance criterion) ===")
    long_curve = curve_node(geo_node, "long_spline",
                            [(0.0, 0.0, 0.0), (20000.0, 0.0, 0.0)])
    big = geo_node.createNode("pf_polychain", "chain_big")
    big.setInput(0, long_curve)
    big.parm("slot_default").set("panel")
    big.parm("slot_start").set("")
    big.parm("slot_end").set("")
    times = {}
    counts = {}
    for mode in ("full", "proxy", "plan"):
        big.parm("display").set(mode)
        # ⚠️ TIME THE FIRST COOK AFTER THE CHANGE, not the second: a repeated
        # `cook(force=True)` on an unchanged node returns in microseconds and
        # the whole measurement reads 0.000 s for every mode, which is how a
        # proxy that saved nothing would still pass.
        t0 = time.time()
        g = big.geometry()
        times[mode] = time.time() - t0
        counts[mode] = (len(g.prims()), len(g.points()))
    check("proxy_is_interactive", times["proxy"] < 1.0,
          round(times["proxy"], 3),
          "full %.3f s, plan %.3f s, %d pieces"
          % (times["full"], times["plan"], counts["full"][0]))
    check("plan_is_one_point_per_piece",
          counts["plan"][1] == counts["full"][0], counts["plan"][1],
          "vs %d pieces" % counts["full"][0])
    check("proxy_matches_piece_count",
          counts["proxy"][0] == counts["full"][0], counts["proxy"][0],
          "vs %d full" % counts["full"][0])

    # a CURVED run, where the proxy is worth having: the full build deforms
    # and the proxy must not.
    # R = 40 m at 1 m spacing: 0.0125 m of sagitta per 2 m panel, just OVER
    # the 0.01 m budget (D75), so the full build genuinely has to bend all
    # 10 000 of them. That is the run the proxy exists for.
    arc = curve_node(geo_node, "arc_spline",
                     cases.arc_points(40.0, 1.0, 20000.0))
    curved = geo_node.createNode("pf_polychain", "chain_arc")
    curved.setInput(0, arc)
    curved.parm("slot_default").set("panel")
    curved.parm("slot_start").set("")
    curved.parm("slot_end").set("")
    curved.parm("display").set("full")
    t0 = time.time()
    full_pts = len(curved.geometry().points())
    t_full = time.time() - t0
    curved.parm("display").set("proxy")
    t0 = time.time()
    proxy_pts = len(curved.geometry().points())
    t_proxy = time.time() - t0
    check("proxy_beats_full_on_a_curve", t_proxy < t_full,
          [round(t_proxy, 3), round(t_full, 3)],
          "%d proxy points vs %d full" % (proxy_pts, full_pts))

    # ---- 6/7. warn, never block ------------------------------------------
    print("\n=== 6. warn-never-block on the wiring ===")
    lonely = geo_node.createNode("pf_polychain", "chain_lonely")
    lonely.cook(force=True)
    # ⚠️ THE WARNING LIVES ON THE INNER NODE. `hou.Node.warnings()` does not
    # aggregate a child's warnings onto the asset (measured), even though the
    # viewport badge does - so a check that reads the outer node reads an
    # empty tuple and calls warn-never-block broken.
    inner_warns = lonely.node("kernel").warnings()
    check("no_spline_warns", not lonely.errors() and inner_warns,
          len(inner_warns), (inner_warns or ("",))[0][:80])

    bad_kit = geo_node.createNode("pf_polychain", "chain_badkit")
    bad_kit.setInput(0, spline)
    bad_kit.parm("kitfile").set("F:/nothing/here.bgeo")
    bad_kit.cook(force=True)
    bad_warns = bad_kit.node("kernel").warnings()
    check("bad_kit_file_warns",
          not bad_kit.errors() and len(bad_kit.geometry().prims()) > 20
          and bool(bad_warns),
          len(bad_kit.geometry().prims()),
          "fell back to the starter kit; %d warnings: %s"
          % (len(bad_warns), (bad_warns or ("",))[0][:60]))

    # ---- 7. the warning COLOUR, which nothing asserted ------------------
    # 11.2 P1 named `run_hda_checks.py`'s "warning-colour rows" as one of its
    # pins. There were none. Deleting the write in `hda.colour_warnings`
    # outright left this whole suite green, and `show_warnings` is exempt
    # from the PC-G4 parm sweep by design (D81/D82: it is a viewing decision),
    # so the parm and its writer were together unexercised. 2.2's advisory
    # validation only works if the artist can SEE what was warned about.
    print("\n=== 7. show_warnings paints the warned elements ===")
    warned = geo_node.createNode("pf_polychain", "chain_warncolour")
    warned.setInput(0, spline)
    warned.parm("slot_default").set("nosuchmodule")
    warned.parm("slot_start").set("")
    warned.parm("slot_end").set("")
    warned.parm("show_warnings").set(1)
    g_on = warned.geometry()
    warn_attrs = [a.name() for a in g_on.primAttribs()
                  if a.name().startswith("pc_warn_")]
    red = lit = 0
    for prim in g_on.prims():
        if any(prim.attribValue(a) for a in warn_attrs):
            lit += 1
            if tuple(round(v, 4) for v in prim.attribValue("Cd"))                     == tuple(round(v, 4) for v in H.WARN_COLOUR):
                red += 1
    check("warned_elements_are_coloured",
          bool(warn_attrs) and lit > 0 and red == lit, [lit, red],
          "%d warned prims, %d at %s" % (lit, red, str(H.WARN_COLOUR)))
    warned.parm("show_warnings").set(0)
    g_off = warned.geometry()
    off_red = sum(1 for prim in g_off.prims()
                  if g_off.findPrimAttrib("Cd") is not None
                  and tuple(round(v, 4) for v in prim.attribValue("Cd"))
                  == tuple(round(v, 4) for v in H.WARN_COLOUR))
    check("show_warnings_off_paints_nothing", off_red == 0, off_red,
          "the toggle is the control - without it the check above could pass "
          "on a builder that painted everything red unconditionally")

    # ---- 8. artist_ui 6's UX law, asserted (D96) --------------------------
    # ⚠️ THIS SECTION EXISTS BECAUSE IT WAS MISSING. An independent verifier
    # stripped the help text, the ranges and the unit suffixes off all nine
    # float parms, rebuilt the asset, and every one of the 22 checks above,
    # all 76 scene cases and all 279 unit tests stayed GREEN. artist_ui 6 is
    # binding on every parameter decision here, and until now nothing
    # enforced a word of it - so the sweep that proves a payload overrides
    # the parms could not tell a documented page from a bare one.
    print("\n=== 8. artist_ui 6 - the UX law, on the built asset (D96) ===")

    def _walk(group, folder=""):
        for tpl in group.parmTemplates():
            if isinstance(tpl, hou.FolderParmTemplate):
                for row in _walk(tpl, "%s/%s" % (folder, tpl.label())
                                 if folder else tpl.label()):
                    yield row
            else:
                yield (folder, tpl)

    rows = list(_walk(node.type().definition().parmTemplateGroup()))
    nohelp = [t.name() for f, t in rows if not (t.help() or "").strip()]
    check("every_parm_has_help", not nohelp, len(rows),
          "no help on: %s" % (",".join(nohelp) or "none"))
    # TWO disclosure levels maximum: the main page and ONE Advanced folder.
    depth = max([f.count("/") + 1 for f, t in rows if f] or [0])
    check("two_disclosure_levels", depth <= 1, depth,
          "folders: %s" % ",".join(sorted(set(f for f, t in rows if f))))
    # A number an artist types needs a range to drag inside. `hou`'s own
    # default is 0..10 on every numeric template, so "untouched" is the
    # failure this looks for, not "narrow".
    numeric = [(f, t) for f, t in rows
               if isinstance(t, (hou.FloatParmTemplate, hou.IntParmTemplate))]
    norange = [t.name() for f, t in numeric
               if (t.minValue(), t.maxValue()) == (0, 10)]
    check("every_number_has_a_range", not norange, len(numeric),
          "default 0..10 on: %s" % (",".join(norange) or "none"))
    # ...and a number in metres/degrees/percent says so IN THE LABEL, because
    # the label is the only thing visible without hovering.
    UNITED = {"padding": "m", "evenly_spacing": "m", "fillet_radius": "m",
              "adjust_to_end": "m", "bend_tol": "m", "flat_band_m": "m",
              "corner_angle_deg": "deg",
              "min_included_angle_deg": "deg", "adaptive_pct": "%",
              "corner_offset_pct": "%"}
    byname = dict((t.name(), t) for f, t in rows)
    nounit = [n for n, u in sorted(UNITED.items())
              if n in byname and ("(%s)" % u) not in byname[n].label()]
    check("units_in_the_label", not nounit, len(UNITED),
          "no unit on: %s" % (",".join(nounit) or "none"))

    failed = [r for r in RESULTS if not r[1]]
    print("\n%d failing checks" % len(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
