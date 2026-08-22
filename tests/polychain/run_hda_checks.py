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
  4. PC-G4 - a STYLE PAYLOAD on input 3 overrides the parms entirely, and the
     parms it contradicts are the ones that move;
  5. the proxy LOD keeps a 10k-piece run interactive (5's own acceptance
     criterion, in seconds);
  6. the plan display draws one point per piece;
  7. a malformed kit file and an empty spline warn instead of erroring.
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
        params=Params(fill="scale", corner_mode="miter"))
    payload = geo_node.createNode("python", "style_in")
    payload.parm("python").set(
        "import hou\n"
        "from polyfactory.polychain import Params, Rule, Style\n"
        "from polyfactory.polychain import style as S\n"
        "st = Style('pipeline', 1, 11, rules=[\n"
        "    Rule('default', 'first', ['gate']),\n"
        "    Rule('corner', 'first', ['corner_post'])],\n"
        "    params=Params(fill='scale', corner_mode='miter'))\n"
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
    # ...and the parms are not consulted AT ALL while it is wired (D77)
    node.parm("fill").set("tile")
    node.parm("seed").set(99)
    after = sorted(p.attribValue("pc_elem_id") for p in node.geometry().prims())
    check("parms_inert_under_payload", after == ids_a, len(after),
          "fill and seed moved on the node and nothing moved in the output")
    node.parm("fill").set("adaptive")
    node.parm("seed").set(3)
    node.setInput(2, None)

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

    failed = [r for r in RESULTS if not r[1]]
    print("\n%d failing checks" % len(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
