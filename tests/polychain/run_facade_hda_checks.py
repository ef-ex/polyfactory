"""The `pf_polychain_facade` HDA itself, cooked headlessly - P2-9's acceptance.

    hython tests/polychain/run_facade_hda_checks.py

`run_2d_checks.py` measures the 2D BUILDER by calling `facade.build*` directly.
Nothing there touches a node, a port or a parameter, so every defect that
lives in the asset - a parm read into the wrong argument, a port wired to the
wrong index, a payload that does not actually override - is invisible to it.
This is that missing half, and it is the same split `run_hda_checks.py` makes
one node over.

THE ACCEPTANCE IS A DIFFERENTIAL, not a list of assertions (v2 principle 1).
The node is cooked and the shipped entry point is called with the same
arguments, and `diff.compare` compares EVERYTHING at tolerance 0 - every
value, every attribute, every storage type, the topology, the packed
transforms. What that catches without anyone having to think of it: a swapped
argument, a port read at the wrong index, a setting the node drops, a kit it
silently replaced with the starter one.

⚠️ THE FIXTURES ARE CHOSEN SO THAT IGNORING A PORT IS VISIBLE. The kit on
input 2 is NOT the starter facade kit, the payload's style is NOT the page's
style, and the surface genuinely moves geometry - otherwise a node that
ignored the port would agree with an oracle that used it.

WHAT THIS CANNOT SEE: the two sides share `facade`'s port readers and, on the
un-payloaded cases, `hda.facade_style_from_parms`. A defect INSIDE those is
mirrored on both sides and reads as agreement; `facade_payload_beats_the_page`
and the port checks below are what cover them.
"""

import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cases2d                                                   # noqa: E402
import diff                                                      # noqa: E402
import hou                                                       # noqa: E402
from polyfactory.polychain import Params, Rule, Style             # noqa: E402
from polyfactory.polychain import facade as F                     # noqa: E402
from polyfactory.polychain import hda as H                        # noqa: E402
from polyfactory.polychain import kit as K                        # noqa: E402
from polyfactory.polychain import style as S                      # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
OTLS = os.path.join(REPO, "polyfactory", "otls").replace("\\", "/")
HDA_PATH = OTLS + "/pf_polychain_facade.hda"

RESULTS = []
FEED = {}

# The 2D settings a case may move. Every one is a parm NAME on the page and a
# keyword NAME on the entry point, and the two lists being the same list is
# what makes a swap visible: the check sets `parm[k] = v` and passes `k=v`.
SETTINGS = ("y_mode", "clip_mode", "extend", "auto_align", "expand")


def check(name, ok, value="", detail=""):
    RESULTS.append((name, bool(ok), value, detail))
    print("  [%s] %-38s %s  %s" % ("PASS" if ok else "FAIL", name, value,
                                   detail))
    return ok


def feed(geo_node, name, geometry):
    """A Python SOP that hands the node one `hou.Geometry` we already hold."""
    FEED[name] = geometry
    node = geo_node.createNode("python", name)
    node.parm("python").set(
        "import hou, sys\n"
        "hou.pwd().geometry().merge(sys.modules['__main__'].FEED[%r])\n"
        % name)
    return node


def payload_geo(style):
    geo = hou.Geometry()
    S.write(geo, style)
    return geo


def spline_geo(loops, closed=True, purpose=None):
    """Closed polygons from point lists - D127's spline ports as geometry."""
    geo = hou.Geometry()
    if purpose is not None:
        geo.addAttrib(hou.attribType.Prim, F.AUX_PURPOSE, "")
    for loop in loops:
        poly = geo.createPolygon(closed)
        for p in loop:
            pt = geo.createPoint()
            pt.setPosition(p)
            poly.addVertex(pt)
        if purpose is not None:
            poly.setAttribValue(F.AUX_PURPOSE, purpose)
    return geo


def gen_footprints(seed=7, n=6):
    """Seeded footprints: a rectangle, an L, and n random convex rings.

    Generated rather than hand-written (v2 principle 2) and SEEDED, so a
    failure prints the seed and reproduces. Coordinates land on a 0.25 m grid
    only because a reader that dropped a vertex should be visible as a shape
    difference and not as a rounding argument.
    """
    import math
    import random
    rng = random.Random(seed)
    out = [cases2d.RECT_FOOTPRINT, cases2d.L_FOOTPRINT]
    for _i in range(n):
        k = rng.randint(4, 7)
        r = rng.choice((8.0, 12.0, 16.0))
        ring = []
        for j in range(k):
            a = 2.0 * math.pi * j / k
            rad = r + 0.25 * rng.randint(-8, 8)
            ring.append((round(rad * math.cos(a) * 4) / 4.0, 0.0,
                         round(rad * math.sin(a) * 4) / 4.0))
        out.append(ring)
    return out


def build_node(geo_node, name, foot, kit_geo, aux=None, payload=None,
               surface=None, **parms):
    node = geo_node.createNode("pf_polychain_facade", name)
    node.setInput(0, feed(geo_node, name + "_foot", foot))
    node.setInput(1, feed(geo_node, name + "_kit", kit_geo))
    if payload is not None:
        node.setInput(2, feed(geo_node, name + "_pay", payload))
    if surface is not None:
        node.setInput(3, feed(geo_node, name + "_surf", surface))
    if aux is not None:
        node.setInput(4, feed(geo_node, name + "_aux", aux))
    for key, value in parms.items():
        node.parm(key).set(value)
    return node


def oracle(node, foot, kit_geo, aux, payload, surface, parms):
    """The shipped entry point, called with the arguments the page carries."""
    style = (S.read(payload, kit=K.read(kit_geo)[0])[0] if payload is not None
             else H.facade_style_from_parms(node))
    kw = dict((k, parms[k]) for k in SETTINGS if k in parms)
    kw.update(kit_geo=kit_geo, style=style, surface_geo=surface,
              y_params=H.facade_y_params(node))
    foot_geo, clip_geo, _w = F.split_ports(foot, aux)
    if parms.get("shape") == "area":
        return F.build_clipped(
            clip_geo if clip_geo is not None else foot_geo, **kw)
    loops, flags, ids, closed, heights, _w = F.footprint_loops(foot_geo)
    tall = parms["height"]
    return F.build_many(loops, height=tall, array_ids=ids, corner_flags=flags,
                        closed=closed,
                        heights=([h if h > 0.0 else tall for h in heights]
                                 if heights is not None else None), **kw)


def differential(name, cases, geo_node):
    """Cook each case both ways and compare EVERYTHING at tolerance 0."""
    worst, bad = 0, []
    for i, (label, kw) in enumerate(cases):
        parms = kw["parms"]
        node = build_node(geo_node, "%s_%d" % (name, i), kw["foot"],
                          kw["kit"], aux=kw.get("aux"),
                          payload=kw.get("payload"),
                          surface=kw.get("surface"), **parms)
        got = node.geometry()
        want, _report = oracle(node, kw["foot"], kw["kit"], kw.get("aux"),
                               kw.get("payload"), kw.get("surface"), parms)
        # ⚠️ THE NOTES CHANNEL IS THE ONE THING THE NODE HAS THAT THE ENTRY
        # POINT DOES NOT, by design: `pc_facade_notes` is D289's route to the
        # page and no python caller has a page. It is dropped from the
        # comparison HERE rather than tolerated by the comparator, and it has
        # its own check (`facade_input_refusals_are_named`) - otherwise this
        # would be one attribute the differential silently stopped reading.
        want.addAttrib(hou.attribType.Global, H.FACADE_NOTES, "")
        want.setGlobalAttribValue(H.FACADE_NOTES,
                                  got.attribValue(H.FACADE_NOTES))
        rows = diff.compare(diff.snapshot(got), diff.snapshot(want))
        worst = max(worst, got.intrinsicValue("primitivecount"))
        if rows or not got.intrinsicValue("primitivecount"):
            bad.append("%s: %s" % (label, rows[0] if rows else "built 0 prims"))
    return check(name, not bad, "%d cases / %d prims worst" % (len(cases),
                                                               worst),
                 "; ".join(bad)[:400] or "byte-identical to the entry point")


def main():
    if not os.path.exists(HDA_PATH):
        print("no HDA at %s - run "
              "devScripts/create_pf_polychain_facade_hda.py" % HDA_PATH)
        sys.exit(1)
    hou.hda.installFile(HDA_PATH)
    hou.putenv("POLYFACTORY",
               os.path.join(REPO, "polyfactory").replace("\\", "/"))
    obj = hou.node("/obj")
    geo_node = obj.createNode("geo", "facade_hda_gate")

    # ---- 1. the standalone floor: a wall quad and NOTHING else -----------
    print("\n=== 1. defaults, nothing wired but a shape (6's floor) ===")
    plain = geo_node.createNode("grid", "wall")
    plain.parm("sizex").set(18.0)
    plain.parm("sizey").set(9.0)
    plain.parm("rows").set(2)
    plain.parm("cols").set(2)
    bare = geo_node.createNode("pf_polychain_facade", "bare")
    bare.setInput(0, plain)
    bgeo = bare.geometry()
    cells = sorted(set(bgeo.primStringAttribValues("pc_cell"))) \
        if bgeo.findPrimAttrib("pc_cell") else []
    mods = sorted(set(bgeo.primStringAttribValues("pc_module"))) \
        if bgeo.findPrimAttrib("pc_module") else []
    starter = sorted(m.name for m in K.read(K.starter_facade_kit())[0].modules)
    # ⚠️ THE ASSERTION IS THE SIX CELLS AND THE SIX MODULES, not "it built
    # something". A stand-in box is geometry too, and a default page that
    # resolved every cell to the same slab would still have a prim count.
    check("facade_defaults_build_a_facade",
          len(cells) == 6 and mods == starter and not bare.warnings(),
          "%d prims, %d cells" % (bgeo.intrinsicValue("primitivecount"),
                                  len(cells)),
          "modules %s; warnings %d" % (",".join(mods), len(bare.warnings())))

    # ---- 2. the differential, three families ------------------------------
    print("\n=== 2. the node against the shipped entry point (tol 0) ===")
    kit = cases2d.facade_kit()                # NOT the starter kit
    ground = cases2d.terrain() if hasattr(cases2d, "terrain") else None
    foot_cases = []
    for i, loop in enumerate(gen_footprints()):
        parms = {"shape": "footprint",
                 "height": 9.0 + 1.25 * (i % 5),
                 "y_mode": ("free", "aligned")[i % 2],
                 "extend": ("x", "y")[i % 2],
                 "corner_mode": ("miter", "bend")[i % 2],
                 "fill": ("adaptive", "tile")[i % 2],
                 "y_fill": "adaptive", "seed": 3 + i}
        foot_cases.append(("gen%d" % i,
                           {"foot": spline_geo([loop]), "kit": kit,
                            "parms": parms}))
    # ...and one over a terrain, which is the only case that reads input 4.
    foot_cases.append(("on_terrain", {
        "foot": spline_geo([cases2d.RECT_FOOTPRINT]), "kit": kit,
        "surface": ground,
        "parms": {"shape": "footprint", "height": 10.0, "y_mode": "free"}}))
    # ...and a DISTRICT with a height per building (D317), which is the only
    # case that reads `pc_height` - three footprints, one of them silent, so
    # the parm has to answer for that one and only that one.
    district = spline_geo([cases2d.RECT_FOOTPRINT,
                           [(p[0] + 40.0, p[1], p[2])
                            for p in cases2d.RECT_FOOTPRINT],
                           [(p[0] + 80.0, p[1], p[2])
                            for p in cases2d.L_FOOTPRINT]])
    district.addAttrib(hou.attribType.Prim, F.HEIGHT_ATTR, 0.0)
    district.setPrimFloatAttribValues(F.HEIGHT_ATTR, [9.0, 0.0, 21.0])
    foot_cases.append(("per_prim_height", {
        "foot": district, "kit": kit,
        "parms": {"shape": "footprint", "height": 13.0, "y_mode": "free"}}))
    differential("facade_matches_entry_point", foot_cases, geo_node)

    area_cases = []
    for label, loops in (("plate", cases2d.CLIP_LOOPS),
                         ("hostile", cases2d.clip_loops_hostile()),
                         ("tilt30", [cases2d.tilt_plate(30.0)]),
                         ("floor", [cases2d.tilt_plate(90.0)]),
                         ("tilt_start1", [cases2d.tilt_plate(30.0, 0.0, 1)])):
        for policy in ("remove", "slice"):
            area_cases.append(("%s_%s" % (label, policy), {
                "foot": spline_geo([cases2d.RECT_FOOTPRINT]),
                "aux": spline_geo(loops, purpose="clip"),
                "kit": cases2d.clip_kit(),
                "parms": {"shape": "area", "clip_mode": policy,
                          "height": 12.0, "auto_align": "to_spline",
                          "expand": 0.0}}))
    differential("facade_matches_entry_point_area", area_cases, geo_node)

    pay_cases = []
    for i, (fill, y_mode, cm) in enumerate((("adaptive", "free", "miter"),
                                            ("tile", "aligned", "bend"))):
        style = cases2d.facade_style(fill=fill, corner_mode=cm,
                                     meta={"y_mode": y_mode})
        pay_cases.append(("pay%d" % i, {
            "foot": spline_geo([cases2d.L_FOOTPRINT]), "kit": kit,
            "payload": payload_geo(style),
            "parms": {"shape": "footprint", "height": 13.0,
                      # deliberately WRONG on the page, so a node that read
                      # the page instead of the payload cannot agree.
                      "y_mode": "aligned" if y_mode == "free" else "free",
                      "corner_mode": "bend" if cm == "miter" else "miter",
                      "seed": 99}}))
    differential("facade_matches_entry_point_payload", pay_cases, geo_node)

    # ---- 3. PC-G4 on the 2D node: the payload owns the build --------------
    #
    # ⚠️ AND THE SECOND HALF IS WHAT KEEPS IT FROM BEING VACUOUS. "No parm
    # moved the build" is also what a page of DEAD parms reads like, and on
    # this node it nearly happened for a benign reason: `y_mode` genuinely
    # cannot move a congruent L (7.4's own no-op), so a sweep that only
    # counted zero would have reported a proof it did not have. The same
    # sweep runs WITHOUT the payload and the same parms must MOVE it -
    # C3's `[0, 3, 3]` shape, on the whole page.
    print("\n=== 3. D77 - a payload on input 3 makes the page inert ===")
    # The lanes a style payload does NOT own, each for a stated reason:
    # `display` / `stage` / `show_warnings` are viewing decisions (D81/D82),
    # `kitfile` / `notes` are the KIT lane and the page's own read-out, and
    # `shape` says which PORT is read. Two had to be argued: `height` is an
    # INPUT DIMENSION and 7.3.2 gives a payload no field for one (a consumer
    # says it per footprint with `pc_height`, D317), and `extend` is the
    # array-level default for a KIT attribute (7.3.1's `pc_extend`), which is
    # where a payload-side consumer sets it.
    exempt = ("display", "stage", "show_warnings", "kitfile", "notes",
              "shape", "height", "extend")

    def sweep(node):
        def fingerprint():
            g = node.geometry()
            return (sorted(g.primStringAttribValues("pc_elem_id")),
                    sorted(round(v, 5) for v in g.pointFloatAttribValues("P")))

        base, moved, nudged = fingerprint(), [], 0
        for parm in sorted(node.parms(), key=lambda q: q.name()):
            if parm.name() in exempt:
                continue
            was = parm.eval()
            tpl = parm.parmTemplate()
            if isinstance(tpl, hou.ToggleParmTemplate):
                parm.set(0 if parm.eval() else 1)
            elif isinstance(tpl, hou.IntParmTemplate):
                parm.set(int(parm.eval()) + 1)
            elif isinstance(tpl, hou.FloatParmTemplate):
                parm.set(parm.eval() + 0.37)
            elif isinstance(tpl, hou.StringParmTemplate):
                items = [i for i in tpl.menuItems() if i != parm.evalAsString()]
                parm.set(items[0] if items else
                         (parm.evalAsString() + " pier").strip())
            else:
                continue
            nudged += 1
            if fingerprint() != base:
                moved.append("%s.%s" % (node.name(), parm.name()))
            parm.set(was)
        return (moved, nudged)

    # A payload that NAMES the 2D settings as well as carrying the style, so
    # `y_mode` and the whole `clip` block are payload-owned here rather than
    # left to the page (D293: what the payload does not name, the page keeps).
    named = cases2d.facade_style(meta={"y_mode": "aligned",
                                       "clip": {"mode": "slice",
                                                "auto_align": "x_xy",
                                                "expand": 1.0}})
    inert, live, nudged = [], [], 0
    for label, kwargs in (
            ("foot", {"foot": spline_geo([cases2d.L_FOOTPRINT]), "kit": kit,
                      "parms": {"shape": "footprint", "height": 13.0}}),
            ("area", {"foot": spline_geo([cases2d.RECT_FOOTPRINT]),
                      "aux": spline_geo(cases2d.CLIP_LOOPS, purpose="clip"),
                      "kit": cases2d.clip_kit(),
                      "parms": {"shape": "area", "clip_mode": "remove"}})):
        with_pay = build_node(geo_node, "sweep_" + label, kwargs["foot"],
                              kwargs["kit"], aux=kwargs.get("aux"),
                              payload=payload_geo(named), **kwargs["parms"])
        without = build_node(geo_node, "bare_" + label, kwargs["foot"],
                             kwargs["kit"], aux=kwargs.get("aux"),
                             **kwargs["parms"])
        got, n = sweep(with_pay)
        inert += got
        nudged += n
        live += sweep(without)[0]
    check("facade_payload_beats_the_page",
          not inert and len(live) >= 12 and nudged > 40,
          [len(inert), len(live), nudged],
          "parms that moved the build THROUGH a payload (must be 0), parms "
          "that moved it WITHOUT one (the anti-vacuity half), nudges. "
          "leaked: %s" % (",".join(inert) or "none"))

    # ---- 4. the ports that only say something when they are wrong ---------
    print("\n=== 4. D127's ports, and the two refusals ===")
    mixed = spline_geo([cases2d.RECT_FOOTPRINT])
    open_poly = mixed.createPolygon(False)
    for p in ((40, 0, 0), (48, 0, 0), (48, 0, 6)):
        pt = mixed.createPoint()
        pt.setPosition(p)
        open_poly.addVertex(pt)
    mixed.addAttrib(hou.attribType.Point, F.MARKER_ATTR, 0)
    ysp = spline_geo([[(0, 0, 0), (0, 12, 0), (2, 20, 0)]], closed=False,
                     purpose=F.AUX_YSPLINE)
    node = build_node(geo_node, "ports", mixed, kit, aux=ysp,
                      **{"shape": "footprint", "height": 12.0})
    said = node.evalParm("notes")
    # Each of the three is a REFUSAL, and a refusal that only exists in a
    # docstring is not one: the build must still happen and the line must
    # name the channel.
    ok = (F.WARN_FOOTPRINT_MIXED in said
          and F.WARN_MARKERS_IGNORED in said
          and F.WARN_YSPLINE_UNSUPPORTED in said
          and node.geometry().intrinsicValue("primitivecount") > 0)
    check("facade_input_refusals_are_named", ok, len(said),
          said[:150] if said else "the page said nothing")

    # ...and `pc_purpose = exclude` reaching D125's per-spline override, which
    # is the only conversion the port does that geometry alone cannot show.
    #
    # ⚠️ THE SECOND LOOP IS THE DISJOINT ONE, NOT THE NESTED HOLE, and the
    # first spelling of this check used the hole - which even-odd nesting
    # already empties by DEPTH, so the row passed without the conversion
    # existing at all. A disjoint loop is depth 0 and builds unless something
    # says `exclude`.
    holed = spline_geo([cases2d.CLIP_LOOPS[0]], purpose="clip")
    holed.merge(spline_geo([cases2d.CLIP_LOOPS[3]], purpose="exclude"))
    solid = spline_geo([cases2d.CLIP_LOOPS[0]], purpose="clip")
    solid.merge(spline_geo([cases2d.CLIP_LOOPS[3]], purpose="clip"))
    a = build_node(geo_node, "excl", spline_geo([cases2d.RECT_FOOTPRINT]),
                   cases2d.clip_kit(), aux=holed,
                   **{"shape": "area", "clip_mode": "remove"})
    b = build_node(geo_node, "solid", spline_geo([cases2d.RECT_FOOTPRINT]),
                   cases2d.clip_kit(), aux=solid,
                   **{"shape": "area", "clip_mode": "remove"})
    na = a.geometry().intrinsicValue("primitivecount")
    nb = b.geometry().intrinsicValue("primitivecount")
    check("facade_aux_exclude_cuts_the_hole", 0 < na < nb, [na, nb],
          "the same plate with and without an `exclude` sub-spline")

    # ---- 5. every Stage entry shows a DIFFERENT stage ---------------------
    print("\n=== 5. the Stage menu (13.7 rule 1) ===")
    node = build_node(geo_node, "stages", spline_geo([cases2d.RECT_FOOTPRINT]),
                      kit, **{"shape": "footprint", "height": 13.0})
    seen = {}
    for token, _label in H.FACADE_STAGES:
        node.parm("stage").set(token)
        g = node.geometry()
        seen[token] = (g.intrinsicValue("primitivecount"),
                       g.intrinsicValue("pointcount"))
    node.parm("stage").set("output")
    check("facade_stage_menu_reaches_every_stage",
          len(set(seen.values())) == len(H.FACADE_STAGES)
          and all(v[0] > 0 for v in seen.values()),
          sorted(seen.items()),
          "each entry must draw a different stage, and none may be empty")

    # ---- 5b. D117's `pc_extend`, which nothing else can reach -------------
    #
    # ⚠️ EVERY OTHER CASE HERE USES A KIT WITH ALL SIX CELLS, WHERE THE
    # FALLBACK NEVER RUNS - so `Corners Extend Into` would be an inert parm
    # the differential structurally could not see (dev-loop Rule 0's second
    # check: a toggle the suite never exercises is untested however green the
    # run is). With `corner_end` demoted, 7.2.2's walk has to choose, and the
    # two directions must choose DIFFERENTLY: keeping X gives the corner
    # pier, keeping Y gives the cornice.
    print("\n=== 5b. `pc_extend` as a parm (D117) ===")
    gap_kit = cases2d.facade_kit(roles=("default", "corner", "default_start",
                                        "corner_start", "default_end"))
    mods = {}
    for way in ("x", "y"):
        n = build_node(geo_node, "extend_" + way,
                       spline_geo([cases2d.L_FOOTPRINT]), gap_kit,
                       **{"shape": "footprint", "height": 13.0,
                          "corner_mode": "miter", "extend": way})
        g = n.geometry()
        tally = {}
        for m in g.primStringAttribValues("pc_module"):
            tally[m] = tally.get(m, 0) + 1
        mods[way] = sorted(tally.items())
    check("facade_extend_picks_the_fallback",
          bool(mods["x"]) and mods["x"] != mods["y"], len(mods["x"]),
          "the same kit-gap facade with Corners Extend Into on X and on Y: "
          "%s  vs  %s" % (mods["x"], mods["y"]))

    # ---- 6. 5.1's metadata and artist_ui 6's law, on the SAVED assets -----
    print("\n=== 6. 5.1 metadata + artist_ui 6, off the .hda ===")
    UNITED = {"height": "m", "expand": "m", "bend_tol": "m",
              "corner_angle_deg": "deg", "min_included_angle_deg": "deg",
              "adaptive_pct": "%", "y_adaptive_pct": "%",
              "corner_offset_pct": "%"}
    defn = hou.hda.definitionsInFile(HDA_PATH)[0]
    ds = defn.sections()["DialogScript"].contents()
    labels = ("Footprint / Wall", "Kit", "Style Payload (optional)",
              "Surface (optional)", "Clip / Aux Splines (optional)")
    ports = all('inputlabel\t%d\t"%s"' % (i + 1, s) in ds
                for i, s in enumerate(labels))
    metres = [p for p in ("height", "expand", "bend_tol")
              if defn.parmTemplateGroup().find(p) is not None
              and defn.parmTemplateGroup().find(p).tags().get("units") == "m"]
    shelf = defn.sections().get("Tools.shelf")
    check("facade_hda_metadata",
          shelf is not None and "Poly Factory/Modeling" in shelf.contents()
          and defn.icon() not in ("", "SOP_subnet") and ports
          and 'outputlabel\t1\t"Facade"' in ds and len(metres) == 3,
          defn.icon(),
          "TAB submenu, icon, 5 port labels + output, %d/3 metre unit tags"
          % len(metres))

    def walk(group, folder=""):
        for tpl in group.parmTemplates():
            if isinstance(tpl, hou.FolderParmTemplate):
                for row in walk(tpl, "%s/%s" % (folder, tpl.label())
                                if folder else tpl.label()):
                    yield row
            else:
                yield (folder, tpl)

    # artist_ui 6's RAMP: a parm that means nothing in the current mode is
    # GREYED OUT, not hidden - an artist can still read its help and see why
    # it is off. ⚠️ `hou.Parm.isDisabled()` DOES NOT ANSWER THIS in hython
    # (probed: it returned False for all five on a node where the conditions
    # are in the saved file), so the assertion is the DialogScript's own
    # `disablewhen` line, per parm and by VALUE - a count would pass with all
    # four conditions pointing at the wrong mode.
    EXPECTED_DISABLE = {"height": "{ shape != footprint }",
                        "clip_mode": "{ shape != area }",
                        "expand": "{ shape != area }",
                        "auto_align": "{ shape != area }"}
    # ⚠️ THE BLOCKS ARE SPLIT, NOT REGEXED ACROSS. `default { 13 }` puts a
    # closing brace INSIDE a parm block, so a `name "x"[^}]*disablewhen` match
    # stops at the default and reports every condition missing - which is how
    # the first spelling of this failed on a page that had all four.
    blocks = dict((b.split('"')[1], b) for b in ds.split("    parm {")[1:]
                  if b.strip().startswith("name"))
    wrong = [n for n, cond in sorted(EXPECTED_DISABLE.items())
             if 'disablewhen "%s"' % cond not in blocks.get(n, "")]
    rows = list(walk(defn.parmTemplateGroup()))
    byname = dict((t.name(), t) for _f, t in rows)
    nohelp = [t.name() for _f, t in rows if not (t.help() or "").strip()]
    depth = max([f.count("/") + 1 for f, _t in rows if f] or [0])
    numeric = [t for _f, t in rows
               if isinstance(t, (hou.FloatParmTemplate, hou.IntParmTemplate))]
    norange = [t.name() for t in numeric
               if (t.minValue(), t.maxValue()) == (0, 10)]
    nounit = [n for n, u in sorted(UNITED.items())
              if n in byname and ("(%s)" % u) not in byname[n].label()]
    check("facade_parm_page_obeys_the_ux_law",
          not nohelp and depth <= 1 and not norange and not nounit and not wrong,
          "%d parms / %d numeric" % (len(rows), len(numeric)),
          "no help: %s; depth %d; default range: %s; no unit in label: %s; "
          "wrong or missing disablewhen: %s"
          % (",".join(nohelp) or "none", depth,
             ",".join(norange) or "none", ",".join(nounit) or "none",
             ",".join(wrong) or "none"))

    # ⚠️ AND THE SAME TWO CRITERIA ON THE OTHER TWO ASSETS, because D314's
    # stated cost is that there are now three pages to keep in step and a
    # criterion checked on one of three is not a house convention. This is
    # what caught `pf_polychain` shipping with NO `Tools.shelf`, the default
    # `SOP_subnet` icon and four `Sub-Network Input #N` labels - four cycles
    # after 5.1 was written about that exact node.
    stale = []
    for name in ("pf_polychain", "pf_polychain_slice", "pf_polychain_facade"):
        d = hou.hda.definitionsInFile("%s/%s.hda" % (OTLS, name))[0]
        text = d.sections()["DialogScript"].contents()
        sh = d.sections().get("Tools.shelf")
        if sh is None or "Poly Factory/Modeling" not in sh.contents():
            stale.append(name + ":no TAB submenu")
        if d.icon() in ("", "SOP_subnet"):
            stale.append(name + ":default icon")
        # ⚠️ ONLY THE PORTS THE ASSET DECLARES. The generated DialogScript
        # always carries FOUR `inputlabel` lines whatever `setMaxNumInputs`
        # says, so the vestigial ones on a 2-input asset are not a defect -
        # and counting them made this row fail on a node whose every real
        # port is labelled.
        said = dict((int(i), s) for i, s in
                    re.findall(r'inputlabel\t(\d+)\t"([^"]*)"', text))
        for i in range(1, d.maxNumInputs() + 1):
            if "Sub-Network Input" in said.get(i, ""):
                stale.append("%s:input %d unlabelled" % (name, i))
        if "outputlabel" not in text:
            stale.append(name + ":output unlabelled")
    check("polychain_assets_carry_5_1_metadata", not stale, 3,
          "; ".join(stale) or "all three: TAB submenu, real icon, "
          "labelled ports")

    failed = [r for r in RESULTS if not r[1]]
    print("\n%d failing checks" % len(failed))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
