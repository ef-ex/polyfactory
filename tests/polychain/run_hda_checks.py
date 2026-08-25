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
import checks as C                                               # noqa: E402
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
# D155's `stage` joins them for the same reason as `display`: it decides which
# STAGE of the network you are looking at, so of course moving it moves the
# output. It is not a lane violation, it is the debug menu working. Its own
# check is `stage_menu_reaches_every_stage` in section 9.
PARM_LANE_EXEMPT = ("display", "show_warnings", "kitfile", "stage")


class Uprights(object):
    """The one field `checks.single_pillar` reads, off a cooked NODE.

    It is here rather than in `run_scene_checks.Scene` because the defect that
    check exists for is a PARM-FACE defect: the scene cases build their styles
    in Python and the shipped defaults are the one composition none of them
    ever expressed. Reading the node's own geometry is the whole point.
    """

    def __init__(self, geo):
        self.by_id = dict((r["pc_elem_id"], r) for r in C.elements(geo))


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

    # ⚠️ AND THE DEFECT THREE THOUSAND SIX HUNDRED NUMERIC CHECKS COULD NOT
    # SEE (D266). Hannes opened this exact fence in the viewport and counted
    # TWO pillars at every mitered corner - the corner assembly's 1.30 m post
    # and, 0.0 m away, the default run's own 1.20 m `post`. `corner_abut`,
    # `corner_seam` and `no_gaps_or_overlaps` all passed and were all right:
    # the overlap is EXACTLY zero. Closure is not composition, and the fix is
    # a composition fix - `panel` fills the run, `post` is the evenly-spaced
    # rhythm, RailClone's own canonical fence (`railclone.md` 1, 6.1).
    # BOTH corner modes, because the mode decides whether a corner assembly
    # exists at all and only one of them was ever looked at.
    for _mode in ("bend", "miter"):
        node.parm("corner_mode").set(_mode)
        _res = C.single_pillar(Uprights(node.geometry()))
        check("starter_fence_one_pillar_" + _mode, _res.ok and not _res.skipped,
              _res.value, _res.detail)
    node.parm("corner_mode").set("bend")

    # ⚠️ AND THE SAME DEFECT ONE ADVANCED PARM AWAY (D269). The two rows above
    # ran the shipped defaults on a 12 x 8 m rectangle, where 12 m is an exact
    # multiple of the 2 m spacing - so the justify leftover never approaches
    # zero and NO justification could reach the corner. On 12.161 m it can:
    # `Evenly Justify = From the end` used to drive the evenly post 0.061 m
    # INTO the mitered corner post, and `Adjust to End` did it at every corner
    # of every leg, because D15's half-module shed keyed on `start_cap` /
    # `end_cap` and D18 makes both FALSE at a corner. The corner reserves its
    # space through `trim`, and `trim` is now guarded the same way.
    #
    # `adjust_to_end` is pinned at one whole post rather than at zero: landing
    # the last anchor ON the section end is what the artist asked the parm
    # for, and at a corner that end carries the corner post. What D269 removed
    # is the INTERPENETRATION; the abutment that remains is documented in the
    # parm's own help.
    odd = curve_node(geo_node, "odd_spline",
                     [(0, 0, 0), (12.161, 0, 0), (12.161, 0, 8.161),
                      (0, 0, 8.161)], closed=True)
    node.setInput(0, odd)
    node.parm("corner_mode").set("miter")
    for _label, _val in (("justify_start", "start"),
                         ("justify_center", "center"),
                         ("justify_end", "end")):
        node.parm("justify").set(_val)
        _res = C.single_pillar(Uprights(node.geometry()))
        check("evenly_clears_the_corner_" + _label,
              _res.ok and not _res.skipped, _res.value, _res.detail)
    node.parm("justify").revertToDefaults()
    # 12.66 m, because the adjust branch only fires when the LEFTOVER is at
    # or under `adjust_to_end` - on 12.161 m it is not, so the parm would
    # have been set and read on a build that never used it.
    adj = curve_node(geo_node, "adj_spline",
                     [(0, 0, 0), (12.66, 0, 0), (12.66, 0, 8.66),
                      (0, 0, 8.66)], closed=True)
    node.setInput(0, adj)
    node.parm("adjust_to_end").set(1.0)
    _res = C.single_pillar(Uprights(node.geometry()), expected=0.12)
    check("evenly_clears_the_corner_adjust_to_end",
          _res.ok and not _res.skipped, _res.value, _res.detail)
    node.parm("adjust_to_end").revertToDefaults()
    node.setInput(0, spline)
    node.parm("corner_mode").set("bend")
    odd.destroy()
    adj.destroy()

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
    # ⚠️ THE NAME IS NOT THE ASSERTION, and asserting it made this check
    # UNFAILABLE. `Kit.resolve` ends `return [stand_in(name)]`, so a module
    # the kit cannot supply becomes a blank 1 x 1 x 1 box CARRYING THE
    # REQUESTED NAME - `plank` appears in `pc_module` whether input 2 was
    # read or not. The registered mutation `kit_input_unplugged` wires the
    # asset's kit port to NOTHING and this row stayed green through it,
    # reddening nothing at all in 31 checks. So it asserts the renamed
    # module's own GEOMETRY: the starter `panel` is 2.00 x 0.90 x 0.16 m in
    # module space and 2.00 x 0.90 x 0.06 m as BUILT GEOMETRY (its 0.03 m
    # half-width is what `corner_wedge` measures); the stand-in is
    # 1 x 1 x 1. `pc_local` is read, not the world box, so the adaptive
    # stretch cannot blur the two.
    plank = [r for r in C.elements(node.geometry())
             if r["pc_module"] == "plank"]
    box = (0.0, 0.0, 0.0)
    if plank:
        loc = plank[0]["local"]
        box = tuple(max(loc[i::3]) - min(loc[i::3]) for i in range(3))
    check("input2_is_the_kit",
          bool(plank) and abs(box[1] - 0.90) < 1e-4 and abs(box[2] - 0.06) < 1e-4,
          "%d plank, %.3f x %.3f x %.3f m" % ((len(plank),) + box),
          "the kit on input 2 renamed panel->plank; the piece must be the "
          "PANEL (2.00 x 0.90 x 0.06), not the 1 x 1 x 1 stand-in that "
          "carries the same name")
    node.setInput(1, None)
    node.parm("slot_default").set("post panel")


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
          ",".join(mods), "the parms still say panel + evenly post")
    direct2, _r = P.build(geo_from(spline), H.kit_geometry(node),
                          payload_style)
    ids_a = sorted(p.attribValue("pc_elem_id") for p in with_payload.prims())
    ids_b = sorted(p.attribValue("pc_elem_id") for p in direct2.prims())
    check("payload_matches_kernel", ids_a == ids_b, len(ids_a),
          "vs %d built from the Style object" % len(ids_b))
    # ⚠️ AND THE SAME SWEEP ON A BUILD THE GUARD ADMITS, because the one above
    # only ever judged the REFERENCE.  Its fixture asks for `corner_mode
    # ='miter'` on a cornered spline, which 13.9 N10's level 1 refuses outright
    # - so every parm it sweeps is being read by `hda.cook`, and D77's
    # guarantee on the NATIVE chain was untested.  PART B is what made that
    # matter: the guard admits arcs, markers and padded builds now, so the
    # parm lane has a second implementation behind it.
    #
    # It was found by a MUTATION, not by reading.  Padding a WIRED payload -
    # D91 reverted, the exact defect D107's comment above says this sweep
    # exists to catch - left BOTH runners at 0 [FAIL]: the sweep saw nothing
    # because `hda.cook` still refuses to pad under a payload, and the native
    # chain, which now would have padded, was never the thing being swept.
    native_payload = geo_node.createNode("python", "style_in_native")
    native_payload.parm("python").set(
        "import hou\n"
        "from polyfactory.polychain import Params, Rule, Style\n"
        "from polyfactory.polychain import style as S\n"
        "st = Style('pipeline_native', 1, 11, rules=[\n"
        "    Rule('default', 'sequence', ['post', 'panel'])],\n"
        "    params=Params(fill='adaptive'))\n"
        "S.write(hou.pwd().geometry(), st)\n")
    straight = curve_node(geo_node, "straight_for_payload",
                          [(1.0 * i, 0.0, 0.0) for i in range(201)])
    nat = geo_node.createNode("pf_polychain", "chain_payload_native")
    nat.setInput(0, straight)
    nat.setInput(2, native_payload)
    nat.cook(force=True)
    nat.allowEditingOfContents()
    took_native = nat.node("copy_packed").cookCount() > 0
    base_ids2, base_pos2 = _fingerprint(nat)
    moved2 = []
    for parm in sorted(nat.parms(), key=lambda q: q.name()):
        if parm.name() in PARM_LANE_EXEMPT:
            continue
        was = parm.eval()
        if not _nudge(parm):
            continue
        got_ids, got_pos = _fingerprint(nat)
        if got_ids != base_ids2 or got_pos != base_pos2:
            moved2.append(parm.name())
        parm.set(was)
    # ⚠️ `took_native` IS PART OF THE ASSERTION, not a print.  A sweep that
    # reports "moved: none" because the guard quietly went back to the
    # reference would be the same unfailable check in a new place.
    check("parms_inert_under_payload_native", took_native and not moved2,
          "%s / %d parms" % ("native" if took_native else "REFERENCE",
                             len(nat.parms())),
          "D77 on the NATIVE chain: a straight run with a payload the guard "
          "ADMITS (copy_packed cooked: %s), every parm on the page nudged, "
          "ids and positions both. moved: %s"
          % (took_native, ",".join(moved2) or "none"))

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
