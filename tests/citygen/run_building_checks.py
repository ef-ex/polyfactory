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
]
# The ONLY site the fixture expects to degrade. Stated here rather than read
# off the warning, so that a collapse test which flags too much is caught
# instead of believed.
DEGRADED = (5,)
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
g.addAttrib(hou.attribType.Vertex, 'pf_face_role', '')
for site, style, (ox, oz), (sx, sz), roles in %r:
    p = g.createPolygon()
    p.setIsClosed(True)
    for x, z in ((ox, oz), (ox + sx, oz), (ox + sx, oz + sz), (ox, oz + sz)):
        pt = g.createPoint()
        pt.setPosition(hou.Vector3((x, 0.0, z)))
        p.addVertex(pt)
    p.setAttribValue('pf_site_id', site)
    p.setAttribValue('pf_style_template', style)
    for i, v in enumerate(p.vertices()):
        v.setAttribValue('pf_face_role', roles[i])
"""


def scene(parent, lots=None):
    """Lots + a sloped, undulating ground; -> (lot node, B2 output node)."""
    src = parent.createNode("python", "lots")
    src.parm("python").set(LOT_CODE % (lots or LOTS,))

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


MUTATIONS = [
    ("single_roof", "einhof volume 1 leaves the shared cap group",
     lambda: patch_template(lambda s, t: s == "at_einhof"
                            and _volume(t, 1, "capGroup", 9))),
    ("single_roof_ring", "a Vierkanthof farm wing loses its double height, so "
     "the level ridge steps",
     lambda: patch_template(lambda s, t: s == "at_vierkanthof"
                            and _volume(t, 1, "storeyHeightM", 4.0))),
    ("encloses_courtyard", "the perimeter block's courtyard depth -> 0",
     lambda: patch_template(
         lambda s, t: s == "at_vienna_perimeter"
         and t["volumeTopology"].__setitem__("courtyardDepthM", 0.0))),
    ("rule_reuse", "the Vierkanthof stops using `ring`, leaving it to Vienna",
     lambda: patch_template(
         lambda s, t: s == "at_vierkanthof"
         and t["volumeTopology"].__setitem__("rails", "bar"))),
    ("no_style_branching", "a style id appears in the mass rules",
     lambda: patch_vex([("pf_mass", "// pf_mass.vfl",
                         "// pf_mass.vfl at_einhof")])),
    ("party_walls_real", "party faces stop naming their neighbour",
     lambda: patch_vex([("pf_mass",
                         'havenext ? sprintf("%d:B2:v%d", site, next) : "",',
                         '"",')])),
    ("outward_normals", "wall quads are wound the other way",
     lambda: patch_vex([("pf_mass",
                         "addvertex(0, pw, base[j]);  addvertex(0, pw, base[jn]);",
                         "addvertex(0, pw, base[jn]); addvertex(0, pw, base[j]);")])),
    ("heights_follow_data", "half a metre added to every volume",
     lambda: patch_vex([("pf_mass", "ytop[i] = hiall + float(st) * sh;",
                         "ytop[i] = hiall + float(st) * sh + 0.5;")])),
    ("plinth_follows_ground", "the Einhof stops adapting to the slope",
     lambda: patch_template(
         lambda s, t: s == "at_einhof"
         and t["volumeTopology"]["plinth"].__setitem__("mode", "none"))),
    ("attribute_storage", "`pf_cap_group` ships as a float",
     lambda: patch_vex([("pf_mass",
                         'setprimattrib(0, "pf_cap_group", p, capgroup);',
                         'setprimattrib(0, "pf_cap_group", p, float(capgroup));')])),
    ("elem_ids_structural", "the element id becomes the prim number",
     lambda: patch_vex([("pf_mass",
                         'sprintf("%s:%s", vid, t)', 'sprintf("%s:%d", vid, p)')])),
    ("no_scratch", "the prim-class `_*` sweep is removed",
     lambda: setattr(B, "CLEAN", tuple(r for r in B.CLEAN
                                       if r[1] != "primdel"))),
    ("cap_group_split_warns", "one Einhof volume is given a third storey",
     lambda: patch_template(lambda s, t: s == "at_einhof"
                            and _volume(t, 1, "storeys", 3))),
    ("degrades_never_refuses", "the collapsed footprint is skipped instead of "
     "degraded - a refusal, which §2.2 forbids",
     lambda: patch_vex([("pf_mass", "int ncells = degraded ? 1 :",
                         "if (degraded) continue;\n    int ncells = 0 ? 1 :")])),
    ("volume_count_matches", "the second cell of every building vanishes, "
     "the way a non-positive height already can",
     lambda: patch_vex([("pf_mass",
                         "vector corner[]; string tag[], wall[], face[],"
                         " shared[];",
                         "if (i == 1) continue;\n        vector corner[]; "
                         "string tag[], wall[], face[], shared[];")])),
    # A SECOND mutation on the same check, and the one that matters: an audit
    # slid the courtyard 4 m sideways, wrecking the wings underneath, and both
    # the area and the band came back byte-identical to a correct block. Areas
    # are invariant under a rigid translation; only containment sees it.
    ("encloses_courtyard", "the courtyard is slid 4 m off centre",
     lambda: patch_vex([("pf_mass", 'railB[j] = point(1, "P", cpts[j]);',
                         'railB[j] = point(1, "P", cpts[j]) + set(4.0,0.0,0.0);'
                         )])),
    ("unknown_rule_warns", "a template asks for a rails mode that does not "
     "exist",
     lambda: patch_template(
         lambda s, t: s == "at_einhof"
         and t["volumeTopology"].__setitem__("rails", "spiral"))),
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
            geo, by_id, dict((l[0], l[1]) for l in LOTS),
            degraded_sites=DEGRADED),
        C.degrades_never_refuses(geo, 5),
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


def record(out, templates):
    geo = out.geometry()
    snap = {"published": C.published_names(geo), "sites": {}}
    for site, style, _o, _s, _r in LOTS:
        vols = C.volumes(geo, site)
        snap["sites"]["%d_%s" % (site, style)] = {
            "volumes": len(vols),
            "faces": sum(len(v) for v in vols.values()),
            "roles": sorted(set(f["pf_volume_role"]
                                for v in vols.values() for f in v)),
            "capGroups": sorted(set(f["pf_cap_group"]
                                    for v in vols.values() for f in v)),
            "wallRoles": sorted(set(f["pf_wall_role"]
                                    for v in vols.values() for f in v)),
            "topY": sorted(set(round(f["ymax"], 3)
                               for v in vols.values() for f in v
                               if f["pf_wall_role"] == "cap")),
        }
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

    ⚠️ The image must contain its subject: the segment count is asserted
    against the geometry's own edge count before anything is judged."""
    import gate_images as G
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    geo = out.geometry()

    def colour_of(prim):
        return WALL_COLOUR.get(prim.attribValue("pf_wall_role"), (200, 0, 200))

    edges = sum(len(p.vertices()) for p in geo.prims())
    drawn = G.rasterise(os.path.join(outdir, "g1_all_iso.png"), geo,
                        axes="iso", w=1500, h=560, colour_of=colour_of)
    show(C.Result("image_contains_subject", drawn >= edges, [edges, drawn],
                  "%d polygon edges in the geometry, %d segments drawn"
                  % (edges, drawn)))
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

    snap = record(out, templates)
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
        print("\nmutations - each must redden the check it is paired with")
        names = [r.name for r in results]
        for paired, why, apply in MUTATIONS:
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
                _p, _s, mo = cook(name="mut_a_" + paired)
                _q, _t, mo2 = cook(list(reversed(LOTS)), "mut_b_" + paired)
                got = run_checks(mo, mo2, mtpl, sources_now())
                red = [r.name for r in got if not r.ok and not r.skipped]
                note = "  ".join(str(r) for r in got if r.name == paired)
            except Exception as exc:
                red = []
                note = "MUTATION DID NOT APPLY: %s" % str(exc)[:140]
            finally:
                B.vex, B.load, B.CLEAN = keep
            ok = paired in red
            if not ok:
                FAIL.append("mutation:" + paired)
            print("    [%s] %-24s %s" % ("RED " if ok else "GREEN", paired,
                                         why))
            if not ok:
                print("           UNFAILABLE ->", note)
            if paired not in names:
                FAIL.append("mutation:unpaired:" + paired)
        missing = sorted(set(names) - set(m[0] for m in MUTATIONS)
                         - set(["image_contains_subject"]))
        if missing:
            FAIL.append("checks with no mutation: %s" % missing)
            print("    CHECKS WITH NO MUTATION:", missing)

    print("\n%d failing" % len(FAIL), FAIL or "")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
