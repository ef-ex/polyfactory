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

import ast
import io
import json
import math
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
    # Site 8 is R3-2: an authored setback on a lot that FITS. Every other
    # authored site in this fixture degrades, so `plan_follows_data` skipped
    # all of them and its oracle - which read `setbackM` and never the
    # authored value - was never asked a question it could get wrong. It got
    # it wrong: 2..38 x 2..18 is correct and it reported `[0, 0, 40, 20]`.
    # A fixture property was load-bearing without saying so, twice now.
    (8, "at_zinshaus_row", (320.0, 0.0), (40.0, 20.0),
     ["front", "abuts", "rear", "abuts"]),
    # Site 9 is R3-5, the case `pf_collapse.vfl`'s three AREA terms exist for
    # and that nothing reached: a SINGLE inversion. 6 m off both 40 m edges of
    # a 10 m-wide lot puts x at 6..4 - inverted, and still inside 0..10, so
    # containment against `_p0` cannot see it and only the sign flip can. With
    # the terms deleted, all 28 clauses stayed green and the baseline did not
    # move, while two volumes shipped on a 2 m-wide inverted footprint and
    # `inside_the_lot` reported PASS.
    (9, "at_zinshaus_row", (380.0, 0.0), (10.0, 40.0),
     ["front", "abuts", "rear", "abuts"]),
    # Site 10 is R4-1: THE SENTINEL'S OWN FIXTURE. Round 4 measured that
    # reverting `stamp()`'s gate from `>= 0.0` to `> 0.0` left all 28 clauses
    # green and the baseline unmoved, because the only site authoring a zero
    # was an `at_vienna_perimeter` lot whose template setbacks are 0 on every
    # role - so an authored zero and the template's zero are the same number
    # and no check could tell the two gates apart. An `at_einhof` lot asks for
    # 2.0 / 2.5 / 43.0, and authoring 0 on all four edges is therefore a
    # different building under each gate: the lot itself, or a 5 x 45 m bar
    # inside it.
    (10, "at_einhof", (420.0, 0.0), (10.0, 90.0),
     ["front", "interiorSide", "rear", "interiorSide"]),
]
# Authored per-vertex `pf_setback` - cascade level 5, which WINS over the
# template's per-role table. Used rather than a level-6 override because the
# numbers reaching `_inset` are identical, a level-6 override applies to
# every site in the stream, and this is the only thing in the suite that
# exercises `stamp()`'s authored-setback branch at all.
# ⚠️ NEGATIVE IS ABSENT (§12.4, amended for R3-3). A float attribute has no
# "absent" value, so the fixture must spell it: the LOT_CODE default is -1.0
# and only the numbers below are authored. It used to be 0.0 on every vertex
# of every lot, which meant `authored` was true for all seven sites while the
# `> 0.0` gate threw every one of those zeros away - so the suite's one claim
# to exercise cascade level 5 rested on site 6's two NON-ZERO vertices.
# Site 6's zeros are now authored zeros, which is `setback(0)`, the identity
# op §12.6 B1 names - and at_vienna_perimeter's table is 0 on every role, so
# the built geometry is unchanged and the baseline says so.
SETBACKS = {6: [0.0, 25.0, 12.0, 0.0],
            8: [2.0, 2.0, 2.0, 2.0],
            9: [-1.0, 6.0, -1.0, 6.0],
            10: [0.0, 0.0, 0.0, 0.0]}
# The sites the fixture expects to degrade -> whether the OFFSET is what went
# wrong there. Stated here rather than read off the warning, so a collapse
# test that flags too much, or too little, is caught instead of believed.
DEGRADED = {5: True, 6: True, 7: False, 9: True}


def ring_of(ox, oz, sx, sz, roles):
    """A lot's polygon in (x, z) - THE ONE DEFINITION, and it used to be two.

    `RINGS` built a four-corner rectangle while `LOT_CODE` built the polygon
    the fixture actually cooks, which for site 7 has a FIFTH vertex.  Two
    copies of one shape is how an oracle silently stops describing its own
    fixture, and `plan_follows_data` now measures per EDGE, where a missing
    vertex is not a rounding difference but a different edge count.  The lot
    code below is handed the output of this function, so there is nowhere for
    the two to disagree.
    """
    corner = [(ox, oz), (ox + sx, oz), (ox + sx, oz + sz), (ox, oz + sz)]
    if len(roles) == 5:
        corner.insert(2, (ox + sx, oz + sz * 0.5))
    return corner


RINGS = dict((s, ring_of(ox, oz, sx, sz, r))
             for s, _st, (ox, oz), (sx, sz), r in LOTS)
STYLE_OF = dict((l[0], l[1]) for l in LOTS)
ROLES_OF = dict((l[0], l[4]) for l in LOTS)
# What the lot SOP cooks: site, style, ring, roles.
LOT_ROWS = [(s, st, RINGS[s], r) for s, st, _o, _z, r in LOTS]
# de-duplicated, order kept: site 5 deliberately reuses `at_einhof`.
STYLES = sorted(set(lot[1] for lot in LOTS),
                key=[lot[1] for lot in LOTS].index)

# The fixture's ground, written ONCE and read twice: the `slope` wrangle
# evaluates it as VEX, and `GROUND` evaluates the same text as Python so
# `plinth_follows_ground` has an oracle for `plinth.minM` that never passes
# through the code it judges. Sharing the text is the point - two copies of a
# formula is how an oracle silently stops describing its own fixture.
SLOPE = ("%s * -0.02 + %s * -0.022 + sin(%s * 0.11) * 0.6"
         " + cos(%s * 0.07) * 0.5")


def GROUND(x, z):
    return eval(SLOPE % ((x, z) * 2), {"sin": math.sin, "cos": math.cos})


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
for site, style, ring, roles in %r:
    p = g.createPolygon()
    p.setIsClosed(True)
    for x, z in ring:
        pt = g.createPoint()
        pt.setPosition(hou.Vector3((x, 0.0, z)))
        p.addVertex(pt)
    p.setAttribValue('pf_site_id', site)
    p.setAttribValue('pf_style_template', style)
    p.setAttribValue('pf_seed', site * 1000)
    for i, v in enumerate(p.vertices()):
        v.setAttribValue('pf_face_role', roles[i])
        v.setAttribValue('pf_setback', setbacks.get(site, [-1.0] * 8)[i])
"""


def scene(parent, lots=None):
    """Lots + a sloped, undulating ground; -> (lot node, B2 output node)."""
    src = parent.createNode("python", "lots")
    src.parm("python").set(LOT_CODE % (SETBACKS, lots or LOT_ROWS))

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
        "@P.y = " + SLOPE % (("@P.x", "@P.z") * 2) + ";")
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


def patch_pysrc(old, new):
    """A PYTHON-SOURCE door for the registry, and `R4-1` is why it exists.

    The registry could patch `B.vex` and `B.load` and nothing else, so a
    defect in `buildings.py` itself could not be mutated at all - which is how
    the `pf_setback` sentinel came to be defended by no check: reverting
    `stamp()`'s gate left all 28 clauses green and the baseline unmoved, and
    there was no way to say so in a row.

    ⚠️ IT EXECS A MODIFIED SOURCE STRING AND NEVER WRITES A FILE.  A registry
    that edited `buildings.py` on disk and restored it would risk `__pycache__`
    handing the NEXT run the mutant: bytecode is invalidated on (mtime, size),
    and the classic mutation - `>=` to `>` - preserves size and can be undone
    inside the same second.  A sibling session lost four phantom reds to
    exactly that.  Nothing here touches the filesystem, so the trap cannot
    apply.
    """
    original = B.stamp
    path = os.path.join(os.path.dirname(os.path.abspath(B.__file__)),
                        "buildings.py")
    with io.open(path, "r", encoding="utf-8") as handle:
        src = handle.read()
    if old not in src:
        raise AssertionError("mutation anchor gone from buildings.py: %r"
                             % old[:70])
    ns = dict(vars(B))
    exec(compile(src.replace(old, new, 1), "buildings_mutated", "exec"), ns)
    B.stamp = ns["stamp"]
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
    # ⚠️ BOTH DATUMS MOVE, and that is the R3-1 fix rather than a flourish.
    # Lifting `ybase` alone left `ytop` where it was, so `pfb_cell`'s
    # `ytop - ybase < 1e-6` guard REFUSED to build those cells: 16 volumes
    # became 10, nine clauses went red, and the paired clause went red only
    # because `matched` fell 22 -> 0 - `overlapped` is counted inside
    # `if peers:`, so `plan_match` fails first and the elevation half follows
    # mechanically. The clause's own claim was never tested. Lifting both
    # builds all 16 and yields 22 party faces, 22 matched in plan, 0 sharing
    # height: `elevation_overlap` RED with `plan_match` GREEN, which is the
    # only shape that proves this clause.
    ("party_walls_real", "elevation_overlap",
     "every other cell is lifted 30 m BODILY, so a party wall names a "
     "neighbour it meets in plan and shares no height with",
     lambda: patch_vex([
         ("pf_mass", "ybase[i] = (plinth == 0) ? 0.0 : lo[i] - plinthmin;",
          "ybase[i] = ((plinth == 0) ? 0.0 : lo[i] - plinthmin) + "
          "(i % 2 ? 30.0 : 0.0);"),
         ("pf_mass", "ytop[i] = hiall + float(st) * sh;",
          "ytop[i] = hiall + float(st) * sh + (i % 2 ? 30.0 : 0.0);")])),
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
    ("plinth_follows_ground", "plinth_depth",
     "the skirt stops reaching `minM` below the ground it stands on - 0.0 "
     "and 25.0 were both green before this clause existed",
     vx("ybase[i] = (plinth == 0) ? 0.0 : lo[i] - plinthmin;",
        "ybase[i] = (plinth == 0) ? 0.0 : lo[i];")),
    ("plinth_follows_ground", "one_datum",
     "the floor datum goes back to being per CELL - the first build's "
     "stepped Einhof, three eave heights under one declared roof",
     vx("ptop[i] = hiall;", "ptop[i] = lo[i] + plinthmin;")),
    ("attribute_storage", "attribute_storage", "`pf_cap_group` ships as a float",
     vx('setprimattrib(0, "pf_cap_group", p, capgroup);',
        'setprimattrib(0, "pf_cap_group", p, float(capgroup));')),
    ("attribute_storage", "attribute_storage",
     "an undeclared `pf_*` attribute is published on every face - green on "
     "every check before R3-7, and only the baseline said so",
     vx('setprimattrib(0, "pf_cap_group", p, capgroup);',
        'setprimattrib(0, "pf_cap_group", p, capgroup);\n'
        '        setprimattrib(0, "pf_undeclared", p, 1);')),
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
     # anchor updated when G2 added the crossing term; the mutation still
     # removes ONLY containment, so what it proves is unchanged.
     vx("(outside || crosses || a * was <= 0.0", "(crosses || a * was <= 0.0",
        "pf_collapse")),
    # `degrades_never_refuses` is GONE, not lost: §2.2's "advisory, never a
    # wall" is asserted by `volume_count_matches`, which requires every
    # DEGRADED site to hold exactly one volume and to carry - or NOT carry -
    # the collapse warning. Two checks for one contract was the budget's
    # first fat to cut.
    ("volume_count_matches", "volume_count_matches",
     "the collapsed footprint is skipped instead of degraded - a refusal, "
     "which §2.2 forbids",
     # ⚠️ ANCHOR MOVED WHEN G2 ADDED THE `solid` RULE (`degraded || whole`),
     # and the registry's own anchor assert is what caught it - a `.replace`
     # whose anchor has drifted is a silent no-op that "proves" the check.
     vx("int ncells = (degraded || whole) ? 1 :",
        "if (degraded) continue;\n    int ncells = 0 ? 1 :")),
    ("volume_count_matches", "volume_count_matches",
     "the collapse warning goes back to meaning `degraded`, so site 7 - a "
     "five-corner lot whose every setback is 0 - reports a footprint that "
     "collapsed when it provably did not",
     vx("(collapsed || yardbad) ? 1 : 0,", "degraded ? 1 : collapsed,")),
    # R3-5. The three AREA terms in `pf_collapse.vfl` were deletable with all
    # 28 clauses green and the baseline unmoved; site 9 is what reaches them.
    ("volume_count_matches", "volume_count_matches",
     "the collapse test keeps containment and drops its three area terms, so "
     "site 9's SINGLE inversion - x 6..4, still inside 0..10 - ships two "
     "volumes on a 2 m footprint that `inside_the_lot` calls fine",
     # anchor updated when G2 added the crossing term; containment AND the
     # crossing test are kept, so this still isolates the three area terms.
     vx("(outside || crosses || a * was <= 0.0\n"
        "     || abs(a) > abs(was) * (1.0 + 1e-6) + 1e-6\n"
        "     || abs(a) < 1e-4) ? 1 : 0;", "(outside || crosses) ? 1 : 0;",
        "pf_collapse")),
    # R3-4, and it takes THREE edits because two of them are the legal input
    # that reaches the hole and only the third is the defect. No shipped
    # template lists exactly one volume, so the case cannot be a fixture site:
    # `at_zinshaus_row` is cut down to one volume and no cuts, which leaves
    # sites 4 and 8 correct at one cell each and site 7 - the five-corner lot
    # that degrades for a TOPOLOGY reason - with `len(roles) == 1`. The third
    # edit reverts arity to being measured against the degraded fallback's own
    # cell, and site 7 then ships one volume with all four warnings at 0 -
    # measured, and that is R3-4's exact signature.
    # ⚠️ `rule_reuse` reddens too, and it is the ENABLING INPUT that does it,
    # not the defect: emptying `cutsAt` leaves `cuts:fractions` used by one
    # style. Structural, not avoidable - reaching the hole requires a template
    # with one volume, and a `bar` template with one volume must have no cuts
    # or its own non-degraded sites break for an unrelated reason. Credit goes
    # to the named clause only (dev-loop §9), which is what the runner does.
    ("volume_count_matches", "volume_count_matches",
     "a five-corner lot under a one-volume bar template degrades in silence: "
     "arity measured against the fallback's single cell instead of against "
     "the nothing the rails produced",
     lambda: (topo("at_zinshaus_row", "volumes",
                   [{"role": "volume", "storeys": 1, "capGroup": 0}])(),
              topo("at_zinshaus_row", "cutsAt", [])(),
              patch_vex([("pf_mass", "int railcells = degraded ? 0 : ncells;",
                          "int railcells = ncells;")]))),
    ("unknown_rule_warns", "unknown_rule_warns",
     "a template asks for a rails mode that does not exist",
     topo("at_einhof", "rails", "spiral")),
    # R4-1. The `pf_setback` sentinel, defended at last. `>= 0` means AUTHORED
    # and negative means ABSENT (§12.4, amended); reverting the gate to `> 0.0`
    # makes an authored zero indistinguishable from no attribute at all, so
    # site 10 - which authors 0 on all four edges of an einhof lot - stops
    # building on its lot line and silently takes the template's 2.0 / 2.5 /
    # 43.0 instead. No new check and no new clause: it lands on the oracle
    # that already models the whole cascade.
    ("plan_follows_data", "footprint",
     "the setback sentinel reverts to `> 0.0`, so `setback(0)` - §12.6 B1's "
     "identity op - becomes unauthorable again and site 10 quietly builds "
     "the template's setbacks instead of the zero it was given",
     lambda: patch_pysrc('if authored and vtx.attribValue("pf_setback") '
                         '>= 0.0:',
                         'if authored and vtx.attribValue("pf_setback") '
                         '> 0.0:')),
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
        C.plinth_follows_ground(
            geo, 1,
            by_id["at_einhof"]["volumeTopology"]["plinth"]["minM"],
            GROUND),
        C.attribute_storage(geo),
        C.elem_ids_structural(geo, mirror.geometry()),
        C.no_scratch(geo),
        C.warns_on_cap_group_split(geo),
        C.volume_count_matches_template(
            geo, by_id, dict((l[0], (l[1], len(RINGS[l[0]]))) for l in LOTS),
            degraded_sites=DEGRADED),
        C.masses_inside_lots(geo, RINGS),
        C.plan_follows_data(geo, STYLE_OF, RINGS, ROLES_OF, by_id,
                            DEGRADED, SETBACKS),
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


# ⚠️ THE G2 RUNNER IS IN THE NUMERATOR TOO.  A second runner that the
# ratio does not count is how a size budget stops meaning anything, and
# `run_g2_checks.py` prints the identical number from the identical list.
TEST_FILES = ("checks_buildings.py", "run_building_checks.py",
              "run_g2_checks.py")


def budget():
    """test <= production, PRINTED EVERY RUN so it cannot drift unstated
    again - the first build recorded 8 % and was measured at 1.5x.

    Code lines: non-blank, non-comment, non-docstring, over the artefacts B2
    SHIPS. `devScripts/create_pf_building_styles.py` authors data and never
    cooks, so it is not in the denominator; ~70 % of it is source citations,
    and prose in a denominator is not production code. Both round-2 auditors
    rejected it independently for that reason."""
    def lines(path, mark):
        src = io.open(path, encoding="utf-8").read()
        doc = set()
        for n in (ast.walk(ast.parse(src)) if mark == "#" else ()):
            b = getattr(n, "body", None)
            if (isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                    and b and isinstance(b[0], ast.Expr)
                    and isinstance(b[0].value, ast.Constant)):
                doc.update(range(b[0].lineno, b[0].end_lineno + 1))
        return sum(1 for i, l in enumerate(src.splitlines(), 1)
                   if l.strip() and i not in doc
                   and not l.strip().startswith(mark))
    prod = lines(os.path.join(os.path.dirname(os.path.abspath(B.__file__)),
                              "buildings.py"), "#")
    prod += sum(lines(os.path.join(B.VEX_DIR, f), "//")
                for f in os.listdir(B.VEX_DIR) if f.endswith(".vfl"))
    test = sum(lines(os.path.join(HERE, f), "#") for f in TEST_FILES)
    print("\nsize budget: %d test / %d production code lines = %.2fx  %s"
          % (test, prod, test / float(prod),
             "OVER (target 1.00x)" if test > prod else "ok"))


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

    ⚠️ `image_contains_subject` IS NAMED FOR MORE THAN IT PROVES, and this is
    the honest statement of it. The first version could not fail at all:
    `rasterise` emits one segment per vertex per prim and returns that count,
    so comparing it with the geometry's own `sum(len(p.vertices()))` compared
    a number with itself - measured 336 vs 336, and an 8x8 PIXEL render
    passed. Comparing the real render's PNG bytes against the same scene at
    8x8 does close that hole, and closes only that one. Measured: a render of
    1 of the 97 prims is 40.2x and PASSES, and a completely different scene -
    a 40 x 40 grid with no building in it - is 90.7x and PASSES. So what it
    proves is THE CANVAS IS NOT DEGENERATE, and nothing whatever about what is
    drawn on it: not framing, not subject identity, not correctness. The
    `> 20x` threshold has been measured once, on one Houdini and one zlib.
    ⚠️ It is also OUTSIDE the per-clause mutation sweep - `missing` iterates
    `run_checks`'s results and this is shown from `images()` - so it is
    neither swept nor required to hold a registry row.
    ⭐ Hannes' human viewport pass is G1's only image evidence (§0.0g row 3)."""
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
    mirror, _s2, mout = cook(list(reversed(LOT_ROWS)), "g1_mirror")

    print("\nG1 checks")
    results = run_checks(out, mout, templates, sources_now())
    for res in results:
        show(res)

    # ⚠️ THE DIFF IS COMPUTED BEFORE THE WRITE, ALWAYS - see the same block in
    # `run_g2_checks.py`.  Blessing used to take an `elif` branch that never
    # called `diff()`, so what a `--update-baseline` absorbed was invisible at
    # the moment it was absorbed (`build_retrospective.md` §2a).
    snap = record(out)
    moved = None
    if os.path.exists(BASELINE):
        with io.open(BASELINE, "r", encoding="utf-8") as handle:
            moved = diff(snap, json.load(handle))
        print("\nbaseline: %d moved value(s)" % len(moved))
        for line in moved:
            print("    MOVED", line)
    else:
        print("\nbaseline: none recorded yet")
    if "--update-baseline" in args:
        with io.open(BASELINE, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(snap, indent=1, sort_keys=True))
        print("baseline written (%s moved value(s) absorbed): %s"
              % ("no" if moved is None else len(moved), BASELINE))
    elif moved:
        FAIL.append("baseline_movement")

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
            keep = (B.vex, B.load, B.CLEAN, B.stamp)
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
                _q, _t, mo2 = cook(list(reversed(LOT_ROWS)),
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
                B.vex, B.load, B.CLEAN, B.stamp = keep
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

    budget()
    print("\n%d failing" % len(FAIL), FAIL or "")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
