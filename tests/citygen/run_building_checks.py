"""Gate G1 - is `volumeTopology` DATA?  Fixture, checks, baseline, mutations,
images, in one throwaway hython session that never saves a .hip.

    hython tests/citygen/run_building_checks.py
    hython tests/citygen/run_building_checks.py --update-baseline
    hython tests/citygen/run_building_checks.py --mutations
    hython tests/citygen/run_building_checks.py --images [DIR]

⚠️ OWN BASELINE, OWN MODULES.  `baseline.json`, `cases.py`, `checks.py` and
`run_scene_checks.py` belong to the streets work on another branch; regenerating
a shared full-value snapshot from two branches silently blesses one of them
(`citygen_buildings.md` §0.0c rule 2).  This file touches none of them.

THE FIXTURE IS THE ARGUMENT, not the coverage.  G1 asks whether two very
different topologies come out of one rule library.  Two templates cannot answer
it: a rule used by exactly ONE template is that template's code wearing a rule's
name, and with two templates every rule is used once.  So the fixture holds two
MORE styles that recombine the same rules across the family line -
`at_vierkanthof` is a farm that uses the perimeter block's ring, `at_zinshaus_row`
is a Viennese apartment house that uses the farmhouse's bar - and
`checks_buildings.rules_serve_more_than_one_style` fails if any rule is lonely.
A fifth lot is a template on a lot it cannot fit on, because "advisory, never a
wall" (§2.2) is a claim about the degraded path and nothing else reaches it.

WHAT THIS RUN CANNOT SEE.  It exercises B2 only: no facade, no roof, no module.
It says nothing about cook cost at district scale (one cook of four buildings),
and nothing about whether an artist can drive any of it - there is no HDA yet.
"""

import io
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
# ⚠️ hython does not load the polyfactory Houdini package - `POLYFACTORY` is
# unset and `$POLYFACTORY/scripts/python` never reaches sys.path, so
# `polyfactory` resolves as a NAMESPACE package at the package directory and
# `polyfactory.citygen` is simply absent (dev-loop trap list, measured again
# here on 22.0.398). The python SOP inside the network runs in this same
# interpreter, so setting it once here serves the cook too.
for path in (HERE, os.path.join(REPO, "tests", "polychain"),
             os.path.join(REPO, "polyfactory", "scripts", "python")):
    if path not in sys.path:
        sys.path.insert(0, path)

import runguard                                                  # noqa: E402
runguard.begin()            # before `hou`: $TEMP resolves once, at startup

import checks_buildings as C                                     # noqa: E402
import hou                                                       # noqa: E402
from polyfactory.citygen import buildings as B                   # noqa: E402

BASELINE = os.path.join(HERE, "baseline_buildings.json")
IMAGES = os.path.join(HERE, "gate_images_buildings")

# site, style, (x, z) origin, (x, z) size, per-edge site roles walking
# (x0,z0) -> (x1,z0) -> (x1,z1) -> (x0,z1)
# The LOT sizes are fixture data, not template data - a lot comes from streets
# S8, never from a style. Each is chosen to sit inside a sourced range where
# one exists: the Anbauhof parcel 8-10 x 80-100 m; the Gruenderzeit
# Parzellenbreite 15-20 m; a Vierkanter front of 30-60 m enclosing the measured
# 54 x 30 m example. The Viennese block size is deliberately NOT taken from
# search - no metre figure could be sourced - so 60 x 48 m is stated as
# illustrative, chosen so the 12 m tracts leave a courtyard well over the 15 %
# the 1883 Bauordnung §42 required.
LOTS = [
    (1, "at_einhof", (0.0, 0.0), (10.0, 90.0),
     ["front", "interiorSide", "rear", "interiorSide"]),
    (2, "at_vienna_perimeter", (30.0, 0.0), (60.0, 48.0),
     ["front", "sideStreet", "sideStreet", "sideStreet"]),
    (3, "at_vierkanthof", (110.0, 0.0), (62.0, 38.0),
     ["front", "interiorSide", "rear", "interiorSide"]),
    (4, "at_zinshaus_row", (190.0, 0.0), (17.0, 26.0),
     ["front", "abuts", "rear", "abuts"]),
    # Site 5 is DELIBERATELY IMPOSSIBLE: the Einhof's 2 m front and 43 m rear
    # setback do not fit on a 6 x 6 m lot, so the footprint folds through
    # itself. §2.2 says advisory, never a wall - so a building must still come
    # out, carrying the warning. Nothing else in this fixture reaches the
    # degraded path, and the degraded path is a third of the rails rule.
    (5, "at_einhof", (215.0, 0.0), (6.0, 6.0),
     ["front", "interiorSide", "rear", "interiorSide"]),
    # Site 6 is the ROUND-2 BLOCKING DEFECT, kept as a fixture so it cannot
    # come back quietly. front 0 / sideStreet 25 / rear 12 / alley 0 on a
    # 20 x 10 lot INVERTS BOTH AXES: x 20..-5 and z 0..-2. The signed area
    # keeps its sign (+10 from +200) and SHRINKS, so sign, growth and
    # degeneracy are all silent, and three volumes shipped outside the lot
    # with every other check green. `pf_collapse.vfl` now measures
    # containment against `_p0`; `inside_the_lot` is what asserts it.
    (6, "at_vienna_perimeter", (250.0, 0.0), (20.0, 10.0),
     ["front", "sideStreet", "rear", "alley"]),
    # Site 7 is R2-6, the collapse warning's FALSE POSITIVE: a five-corner lot
    # under a bar template, so `pf_mass` degrades for a TOPOLOGY reason while
    # the offset - every zinshaus setback is 0, §12.6 B1's identity op - did
    # not collapse at all. It used to stamp `degraded ? 1 : collapsed` and so
    # warned about a footprint that was provably intact.
    (7, "at_zinshaus_row", (280.0, 0.0), (20.0, 10.0),
     ["front", "abuts", "abuts", "rear", "abuts"]),
]
# Authored per-vertex `pf_setback` - cascade level 5, which WINS over the
# template's per-role table. Used rather than a level-6 override because the
# numbers reaching `_inset` are identical, a level-6 override applies to
# every site in the stream, and this is the only thing in the suite that
# exercises `stamp()`'s authored-setback branch at all.
SETBACKS = {6: [0.0, 25.0, 12.0, 0.0]}
# The sites the fixture expects to degrade -> whether the OFFSET is what went
# wrong there. Stated here rather than read off the warning, so a collapse
# test that flags too much, or too little, is caught instead of believed.
DEGRADED = {5: True, 6: True, 7: False}
# {site: its lot ring in (x,z)} - what `inside_the_lot` measures against.
RINGS = dict((s, [(ox, oz), (ox + sx, oz), (ox + sx, oz + sz), (ox, oz + sz)])
             for s, _st, (ox, oz), (sx, sz), _r in LOTS)
# de-duplicated, order kept: site 5 deliberately reuses `at_einhof`.
STYLES = sorted(set(lot[1] for lot in LOTS),
                key=[lot[1] for lot in LOTS].index)

FAIL = []


def show(res):
    print("   ", res)
    if not res.ok and not res.skipped:
        FAIL.append(res.name)
    return res


# --- the fixture ------------------------------------------------------------

LOT_CODE = """
import hou
g = hou.pwd().geometry()
g.addAttrib(hou.attribType.Prim, 'pf_site_id', 0)
g.addAttrib(hou.attribType.Prim, 'pf_style_template', '')
g.addAttrib(hou.attribType.Prim, 'pf_seed', 0)
g.addAttrib(hou.attribType.Vertex, 'pf_face_role', '')
g.addAttrib(hou.attribType.Vertex, 'pf_setback', 0.0)
setbacks = %r
for site, style, (ox, oz), (sx, sz), roles in %r:
    p = g.createPolygon()
    p.setIsClosed(True)
    corner = [(ox, oz), (ox + sx, oz), (ox + sx, oz + sz), (ox, oz + sz)]
    if len(roles) == 5:
        corner.insert(2, (ox + sx, oz + sz * 0.5))
    for x, z in corner:
        pt = g.createPoint()
        pt.setPosition(hou.Vector3((x, 0.0, z)))
        p.addVertex(pt)
    p.setAttribValue('pf_site_id', site)
    p.setAttribValue('pf_style_template', style)
    p.setAttribValue('pf_seed', site * 1000)
    for i, v in enumerate(p.vertices()):
        v.setAttribValue('pf_face_role', roles[i])
        v.setAttribValue('pf_setback', setbacks.get(site, [0.0] * 8)[i])
"""


def scene(parent, lots=None):
    """Lots + a sloped, undulating ground; -> (lot node, B2 output node)."""
    src = parent.createNode("python", "lots")
    src.parm("python").set(LOT_CODE % (SETBACKS, lots or LOTS))

    grid = parent.createNode("grid", "ground")
    grid.parm("orient").set(2)              # zx: lies in the XZ plane
    grid.parm("sizex").set(300.0)
    grid.parm("sizey").set(180.0)
    grid.parm("tx").set(105.0)
    grid.parm("tz").set(45.0)
    grid.parm("rows").set(90)
    grid.parm("cols").set(150)
    slope = parent.createNode("attribwrangle", "slope")
    slope.setFirstInput(grid)
    slope.parm("class").set(2)
    # Falls in both directions plus a gentle roll: the Einhof bar runs 45 m
    # along Z, so the plinth rule needs the ground to move along Z as well or
    # every cell of it sees the same datum and the check has nothing to see.
    # ⚠️ Gentle on purpose. At 5 % along Z the level-floor rule gave the 3 m
    # Einhof a 3.8 m plinth - arithmetically right, architecturally absurd,
    # and a fixture that makes the output look wrong teaches the wrong thing.
    slope.parm("snippet").set(
        "@P.y = @P.x * -0.02 + @P.z * -0.022 + sin(@P.x * 0.11) * 0.6"
        " + cos(@P.z * 0.07) * 0.5;")
    return src, B.build(parent, src, ground=slope)


def cook(lots=None, name="g1"):
    """A fresh /obj subtree per build, so no cook is served a stale cache."""
    parent = hou.node("/obj").createNode("geo", name)
    src, out = scene(parent, lots)
    out.cook(force=True)
    errs = [n.errors() for n in (out, out.inputs()[0]) if n.errors()]
    if errs:
        raise RuntimeError(str(errs)[:400])
    return parent, src, out


# --- mutation registry ------------------------------------------------------
#
# A check is not written until its mutation has been seen RED.  Each row names
# the check it is PAIRED with; a mutation that reddens other checks too gets no
# credit for them (dev-loop §9).  The anchor assert matters: a `.replace` whose
# anchor has drifted is a silent no-op that "proves" the check.

def patch_vex(rows):
    original = B.vex

    def patched(name):
        text = original(name)
        for want, old, new in rows:
            if name.startswith(want):
                if old not in text:
                    raise AssertionError("mutation anchor gone from %s: %r"
                                         % (name, old[:60]))
                text = text.replace(old, new, 1)
        return text
    B.vex = patched
    return original


def patch_template(fn):
    original = B.load

    def patched(style):
        tpl = original(style)
        return fn(style, tpl) or tpl
    B.load = patched
    return original


def _volume(tpl, index, key, value):
    tpl["volumeTopology"]["volumes"][index][key] = value


# Three shorthands, because a registry that costs four lines a row gets
# written once and then argued about instead of extended.
def vol(style, index, key, value):
    return lambda: patch_template(lambda s, t: s == style
                                  and _volume(t, index, key, value))


def topo(style, key, value):
    return lambda: patch_template(
        lambda s, t: s == style and t["volumeTopology"].__setitem__(key, value))


def vx(old, new, src="pf_mass"):
    return lambda: patch_vex([(src, old, new)])


CELL1 = ("vector corner[]; string tag[], wall[], face[], shared[];",
         "if (i == 1) continue;\n        vector corner[]; string tag[], "
         "wall[], face[], shared[];")

MUTATIONS = [
    ("single_roof", "one_cap_group",
     "einhof volume 1 leaves the shared cap group",
     vol("at_einhof", 1, "capGroup", 9)),
    ("single_roof", "one_eave", "einhof volume 1 gets a third storey",
     vol("at_einhof", 1, "storeys", 3)),
    ("single_roof", "chain_of_functions",
     "the second cell of every building vanishes, the way a non-positive "
     "height already can", vx(*CELL1)),
    ("single_roof_ring", "one_eave", "a Vierkanthof farm wing loses its "
     "double height, so the level ridge steps",
     vol("at_vierkanthof", 1, "storeyHeightM", 4.0)),
    ("single_roof_ring", "one_cap_group",
     "a Vierkanthof wing leaves the shared cap group",
     vol("at_vierkanthof", 1, "capGroup", 9)),
    ("single_roof_ring", "chain_of_functions",
     "the second cell of every building vanishes", vx(*CELL1)),
    # ⚠️ BOTH courtyard mutations are VEX, deliberately. This check reads
    # `courtyardDepthM` as its oracle, so a template mutation would move the
    # oracle and the geometry together and pass on a build it exists to
    # reject - the trap auditor #2 walked into and reported.
    ("encloses_courtyard", "closed_ring",
     "a cell of the perimeter block vanishes, opening the ring",
     vx(*CELL1)),
    ("encloses_courtyard", "tract_depth", "the courtyard is slid 4 m off "
     "centre - areas are invariant under a rigid translation, so only a "
     "per-edge depth sees it",
     vx('railB[j] = point(1, "P", cpts[j]);',
        'railB[j] = point(1, "P", cpts[j]) + set(4.0,0.0,0.0);')),
    ("plan_follows_data", "footprint",
     "B1 applies half the setback it was given",
     vx('float s1 = vertex(0, "_inset", vertexindex(0, pr, i));',
        'float s1 = vertex(0, "_inset", vertexindex(0, pr, i));\n'
        's0 *= 0.5; s1 *= 0.5;', "pf_inset")),
    ("plan_follows_data", "cell_split",
     "the bar is cut at half the fraction asked - 20 m of Einhof dwelling "
     "becomes 10 m, and nothing in the first build could see it",
     vx("append(ts, cuts[c]);", "append(ts, cuts[c] * 0.5);")),
    ("rule_reuse", "rule_reuse",
     "the Vierkanthof stops using `ring`, leaving it to Vienna",
     topo("at_vierkanthof", "rails", "bar")),
    ("no_style_branching", "no_style_branching",
     "a style id appears in the mass rules",
     vx("// pf_mass.vfl", "// pf_mass.vfl at_einhof")),
    ("party_walls_real", "named", "party faces stop naming their neighbour",
     vx('havenext ? sprintf("%d:B2:v%d", site, next) : "",', '"",')),
    ("party_walls_real", "plan_match",
     "one corner of every cell moves 5 cm, so a party face and its partner "
     "no longer occupy the same plan",
     vx("corner = array(railA[i], railA[nx], railB[nx], railB[i]);",
        "corner = array(railA[i], railA[nx], railB[nx] + set(0.0,0.0,0.05), "
        "railB[i]);")),
    ("party_walls_real", "elevation_overlap",
     "every other cell is lifted 30 m, so a party wall names a neighbour it "
     "meets in plan and shares no height with",
     vx("ybase[i] = (plinth == 0) ? 0.0 : lo[i] - plinthmin;",
        "ybase[i] = ((plinth == 0) ? 0.0 : lo[i] - plinthmin) + "
        "(i % 2 ? 30.0 : 0.0);")),
    ("outward_normals", "outward_normals", "wall quads are wound the other way",
     vx("addvertex(0, pw, base[j]);  addvertex(0, pw, base[jn]);",
        "addvertex(0, pw, base[jn]); addvertex(0, pw, base[j]);")),
    ("heights_follow_data", "heights_follow_data",
     "half a metre added to every volume",
     vx("ytop[i] = hiall + float(st) * sh;",
        "ytop[i] = hiall + float(st) * sh + 0.5;")),
    ("plinth_follows_ground", "varying_skirts",
     "the Einhof stops adapting to the slope",
     lambda: patch_template(
         lambda s, t: s == "at_einhof"
         and t["volumeTopology"]["plinth"].__setitem__("mode", "none"))),
    ("plinth_follows_ground", "one_datum",
     "the floor datum goes back to being per CELL - the first build's "
     "stepped Einhof, three eave heights under one declared roof",
     vx("ptop[i] = hiall;", "ptop[i] = lo[i] + plinthmin;")),
    ("attribute_storage", "attribute_storage", "`pf_cap_group` ships as a float",
     vx('setprimattrib(0, "pf_cap_group", p, capgroup);',
        'setprimattrib(0, "pf_cap_group", p, float(capgroup));')),
    ("elem_ids_structural", "order_independent",
     "the element id becomes the prim number",
     vx('sprintf("%s:%s", vid, t)', 'sprintf("%s:%d", vid, p)')),
    ("elem_ids_structural", "unique",
     "the element id drops the face slot, so six faces share one address",
     vx('sprintf("%s:%s", vid, t)', 'sprintf("%s", vid)')),
    ("no_scratch", "no_scratch", "the prim-class `_*` sweep is removed",
     lambda: setattr(B, "CLEAN", tuple(r for r in B.CLEAN
                                       if r[1] != "primdel"))),
    ("cap_group_split_warns", "cap_group_split_warns",
     "one Einhof volume is given a third storey",
     vol("at_einhof", 1, "storeys", 3)),
    # Paired with the round-2 BLOCKING defect: drop the containment term and
    # site 6 stops being flagged, so its mass ships outside its own lot with
    # all three area tests silent - which is exactly what happened.
    ("inside_the_lot", "inside_the_lot",
     "the collapse test goes back to measuring area only",
     vx("(outside || a * was <= 0.0", "(a * was <= 0.0", "pf_collapse")),
    # `degrades_never_refuses` is GONE, not lost: §2.2's "advisory, never a
    # wall" is asserted by `volume_count_matches`, which requires every
    # DEGRADED site to hold exactly one volume and to carry - or NOT carry -
    # the collapse warning. Two checks for one contract was the budget's
    # first fat to cut.
    ("volume_count_matches", "volume_count_matches",
     "the collapsed footprint is skipped instead of degraded - a refusal, "
     "which §2.2 forbids",
     vx("int ncells = degraded ? 1 :",
        "if (degraded) continue;\n    int ncells = 0 ? 1 :")),
    ("volume_count_matches", "volume_count_matches",
     "the collapse warning goes back to meaning `degraded`, so site 7 - a "
     "five-corner lot whose every setback is 0 - reports a footprint that "
     "collapsed when it provably did not",
     vx("(collapsed || yardbad) ? 1 : 0,", "degraded ? 1 : collapsed,")),
    ("unknown_rule_warns", "unknown_rule_warns",
     "a template asks for a rails mode that does not exist",
     topo("at_einhof", "rails", "spiral")),
]


# --- one full pass over the checks ------------------------------------------

def run_checks(out, mirror, templates, sources):
    geo = out.geometry()
    by_id = dict((t["styleId"], t) for t in templates)
    return [
        C.single_roof(geo, 1),
        # The Vierkanthof is the harder half of the same claim, and it is a
        # SOURCED fact rather than a convenience: "Dachfirst auf allen vier
        # Seiten gleich hoch". Its dwelling is two storeys and its three farm
        # wings are one, so the ridge is only level because a volume carries
        # its OWN storey height - the mechanism nothing else here exercises.
        C.single_roof(geo, 3, 4, name="single_roof_ring"),
        C.encloses_courtyard(
            geo, 2,
            by_id["at_vienna_perimeter"]["volumeTopology"]["courtyardDepthM"]),
        C.rules_serve_more_than_one_style(templates),
        C.no_style_names_in_code(sources, STYLES),
        C.party_walls_are_real(geo),
        C.outward_normals(geo),
        C.heights_follow_data(geo, by_id),
        C.plinth_follows_ground(geo, 1),
        C.attribute_storage(geo),
        C.elem_ids_structural(geo, mirror.geometry()),
        C.no_scratch(geo),
        C.warns_on_cap_group_split(geo),
        C.volume_count_matches_template(
            geo, by_id, dict((l[0], (l[1], len(l[4]))) for l in LOTS),
            degraded_sites=DEGRADED),
        C.masses_inside_lots(geo, RINGS),
        C.plan_follows_data(geo, LOTS, by_id, DEGRADED),
        C.warns_on_unknown_rule(geo),
    ]


def sources_now():
    """What `no_style_branching` reads.  The .vfl files go through `B.vex` so a
    mutation that injects a style id into the rules is actually visible."""
    out = {}
    for name in sorted(os.listdir(B.VEX_DIR)):
        if name.endswith(".vfl"):
            out["vex/citygen/" + name] = B.vex(name)
    path = os.path.join(os.path.dirname(os.path.abspath(B.__file__)),
                        "buildings.py")
    with io.open(path, "r", encoding="utf-8") as handle:
        out["citygen/buildings.py"] = handle.read()
    return out


WARNS = ("pf_warn_cap_group_split", "pf_warn_footprint_collapsed",
         "pf_warn_topology_arity", "pf_warn_unknown_rule")


def record(out):
    """VALUES, not pass/fail, and three families of them were missing.

    ⚠️ `pf_warn_topology_arity` was asserted by no check and recorded by no
    row - nailing it to 0 in production left all sixteen checks green and the
    baseline unmoved, and it is *currently firing* on the degraded sites, so a
    name with a dead value would have looked identical. All four warnings are
    recorded now; that is the general cure and it needs no new check.
    ⚠️ No PLAN quantity was recorded either, which is half of round 2's
    blocking defect: a bar cut at half the fraction asked moved the Einhof
    dwelling 20 m -> 10 m with the whole suite and the baseline green.
    ⚠️ `pf_seed` is recorded because it is the SITE's, and `stamp()` used to
    overwrite it with a template key no template defines."""
    geo = out.geometry()
    snap = {"published": C.published_names(geo), "sites": {}}
    for site, style, _o, _s, _r in LOTS:
        vols = C.volumes(geo, site)
        fs = [f for v in vols.values() for f in v]
        row = {
            "volumes": len(vols),
            "faces": len(fs),
            "roles": sorted(set(f["pf_volume_role"] for f in fs)),
            "capGroups": sorted(set(f["pf_cap_group"] for f in fs)),
            "wallRoles": sorted(set(f["pf_wall_role"] for f in fs)),
            "topY": sorted(set(round(f["ymax"], 3) for f in fs
                               if f["pf_wall_role"] == "cap")),
            "planBox": [round(v, 3) for v in C.plan_box(fs)] if fs else [],
            "planAreas": [round(a, 3) for a in C.plan_areas(geo, site)],
            "seed": sorted(set(f["pf_seed"] for f in fs)),
        }
        for w in WARNS:
            row[w] = sorted(set(f[w] for f in fs))
        snap["sites"]["%d_%s" % (site, style)] = row
    return snap


def diff(new, old, path=""):
    moved = []
    if isinstance(new, dict) and isinstance(old, dict):
        for key in sorted(set(new) | set(old)):
            moved += diff(new.get(key), old.get(key), path + "/" + str(key))
    elif new != old:
        moved.append("%s  %r -> %r" % (path, old, new))
    return moved


# --- images -----------------------------------------------------------------

WALL_COLOUR = {"exterior": (150, 165, 190), "courtyard": (90, 190, 150),
               "party": (235, 120, 90), "end": (235, 200, 90),
               "cap": (250, 250, 250), "floor": (70, 78, 95)}


def images(out, outdir):
    """A gate is judged on the picture.  Colour by `pf_wall_role`, so the
    party walls and the courtyard - the topology itself - are what is drawn.

    ⚠️ The image must contain its subject, and the first version of that
    assertion could not fail: `rasterise` emits exactly one segment per vertex
    per prim and returns that count, so comparing it with the geometry's own
    `sum(len(p.vertices()))` compared a number with itself - measured 336 vs
    336, and an 8x8 PIXEL render passed. The degenerate render is now produced
    on every run and the real one has to be an order of magnitude more PNG,
    which is pixels: the thing the claim was always about."""
    import gate_images as G
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    geo = out.geometry()

    def colour_of(prim):
        return WALL_COLOUR.get(prim.attribValue("pf_wall_role"), (200, 0, 200))

    edges = sum(len(p.vertices()) for p in geo.prims())
    big = os.path.join(outdir, "g1_all_iso.png")
    drawn = G.rasterise(big, geo, axes="iso", w=1500, h=560,
                        colour_of=colour_of)
    tiny = os.path.join(outdir, "_g1_degenerate.png")
    G.rasterise(tiny, geo, axes="iso", w=8, h=8, colour_of=colour_of)
    ratio = os.path.getsize(big) / float(os.path.getsize(tiny))
    os.remove(tiny)
    show(C.Result("image_contains_subject", ratio > 20.0,
                  [edges, drawn, round(ratio, 1)],
                  "%d polygon edges, %d segments, %.1fx the bytes of the same "
                  "scene rendered 8x8" % (edges, drawn, ratio)))
    G.rasterise(os.path.join(outdir, "g1_all_plan.png"), geo,
                axes=("x", "z"), w=1500, h=560, colour_of=colour_of)
    # Per SITE, not per style - two lots share `at_einhof` and they are 215 m
    # apart, so a style filter framed one building inside a mostly empty
    # picture. Same bug the checks had, same cause: one-lot-per-style was
    # load-bearing and stopped being true.
    for site, style, _o, _s, _r in LOTS:
        keep = hou.Geometry()
        keep.merge(geo)
        keep.deletePrims([p for p in keep.prims()
                          if p.attribValue("pf_site_id") != site], True)
        for axes in ("iso", ("x", "z")):
            G.rasterise(os.path.join(outdir, "g1_%d_%s_%s.png"
                                     % (site, style, "iso" if axes == "iso"
                                        else "plan")),
                        keep, axes=axes, w=1000, h=700, colour_of=colour_of)


# --- main -------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    print("polyfactory package:", os.path.dirname(
        os.path.dirname(os.path.abspath(B.__file__))))
    templates = [B.resolve(B.load(s)) for s in STYLES]

    parent, _src, out = cook()
    mirror, _s2, mout = cook(list(reversed(LOTS)), "g1_mirror")

    print("\nG1 checks")
    results = run_checks(out, mout, templates, sources_now())
    for res in results:
        show(res)

    snap = record(out)
    if "--update-baseline" in args:
        with io.open(BASELINE, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(snap, indent=1, sort_keys=True))
        print("\nbaseline written:", BASELINE)
    elif os.path.exists(BASELINE):
        with io.open(BASELINE, "r", encoding="utf-8") as handle:
            moved = diff(snap, json.load(handle))
        print("\nbaseline: %d moved value(s)" % len(moved))
        for line in moved:
            print("    MOVED", line)
        if moved:
            FAIL.append("baseline_movement")
    else:
        print("\nbaseline: none recorded yet")

    if "--images" in args:
        idx = args.index("--images")
        outdir = (args[idx + 1] if len(args) > idx + 1
                  and not args[idx + 1].startswith("-") else IMAGES)
        print("\nimages ->", outdir)
        images(out, outdir)

    if "--mutations" in args:
        # ⚠️ PER CLAUSE, NOT PER CHECK NAME, and that is the systemic fix of
        # round 2. The old sweep asked only that each check NAME appear in the
        # registry, so a four-clause check could ship with three clauses
        # nobody had ever seen fail - `party_walls_are_real`'s elevation half
        # had real teeth and no mutation of its own, and the sweep was
        # structurally unable to say so. A mutation is credited ONLY to the
        # clause it names, never to its blast radius (dev-loop §9): crediting
        # the whole radius once marked 57 unexamined checks proven.
        print("\nmutations - each must redden the CLAUSE it is paired with")
        names = [r.name for r in results]
        proven = set()
        for paired, clause, why, apply in MUTATIONS:
            keep = (B.vex, B.load, B.CLEAN)
            note = ""
            try:
                apply()
                # ⚠️ EVERYTHING the check reads must come from the MUTATED
                # build: the templates re-resolved through the patched
                # `B.load`, and BOTH lot orders re-cooked. The first version
                # of this loop reused the clean templates and passed one
                # geometry as its own mirror, which made two checks
                # structurally unable to notice their own mutation.
                mtpl = [B.resolve(B.load(s)) for s in STYLES]
                _p, _s, mo = cook(name="mut_a_%s_%s" % (paired, clause))
                _q, _t, mo2 = cook(list(reversed(LOTS)),
                                   "mut_b_%s_%s" % (paired, clause))
                got = dict((r.name, r)
                           for r in run_checks(mo, mo2, mtpl, sources_now()))
                hit = got.get(paired)
                ok = (hit is not None and not hit.skipped
                      and not hit.clauses.get(clause, True))
                note = str(hit) if hit else "no check named %r" % paired
            except Exception as exc:
                ok = False
                note = "MUTATION DID NOT APPLY: %s" % str(exc)[:140]
            finally:
                B.vex, B.load, B.CLEAN = keep
            if ok:
                proven.add((paired, clause))
            else:
                FAIL.append("mutation:%s/%s" % (paired, clause))
            print("    [%s] %-22s %-19s %s" % ("RED " if ok else "GREEN",
                                               paired, clause, why))
            if not ok:
                print("           UNFAILABLE ->", note)
            if paired not in names:
                FAIL.append("mutation:unpaired:" + paired)
        missing = sorted("%s/%s" % (r.name, k) for r in results
                         if not r.skipped for k in r.clauses
                         if (r.name, k) not in proven)
        if missing:
            FAIL.append("clauses with no mutation: %s" % missing)
            print("    CLAUSES WITH NO MUTATION:", missing)

    print("\n%d failing" % len(FAIL), FAIL or "")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
