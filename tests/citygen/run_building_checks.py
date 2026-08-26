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

THE FOUR FIXTURES ARE THE ARGUMENT, not the coverage.  G1 asks whether two very
different topologies come out of one rule library.  Two templates cannot answer
it: a rule used by exactly ONE template is that template's code wearing a rule's
name, and with two templates every rule is used once.  So the fixture holds two
MORE styles that recombine the same rules across the family line -
`at_vierkanthof` is a farm that uses the perimeter block's ring, `at_zinshaus_row`
is a Viennese apartment house that uses the farmhouse's bar - and
`checks_buildings.rules_serve_more_than_one_style` fails if any rule is lonely.

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
LOTS = [
    (1, "at_einhof", (0.0, 0.0), (46.0, 30.0),
     ["front", "interiorSide", "rear", "interiorSide"]),
    (2, "at_vienna_perimeter", (80.0, 0.0), (62.0, 44.0),
     ["front", "sideStreet", "sideStreet", "sideStreet"]),
    (3, "at_vierkanthof", (170.0, 0.0), (48.0, 48.0),
     ["front", "interiorSide", "rear", "interiorSide"]),
    (4, "at_zinshaus_row", (240.0, 0.0), (17.0, 36.0),
     ["front", "abuts", "rear", "abuts"]),
]
STYLES = [lot[1] for lot in LOTS]
SLOPED = "at_einhof"        # the plinth rule is judged on this one

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
    grid.parm("sizex").set(420.0)
    grid.parm("sizey").set(200.0)
    grid.parm("tx").set(130.0)
    grid.parm("tz").set(25.0)
    grid.parm("rows").set(90)
    grid.parm("cols").set(180)
    slope = parent.createNode("attribwrangle", "slope")
    slope.setFirstInput(grid)
    slope.parm("class").set(2)
    # A steady fall across the Einhof lot plus a gentle roll, so the plinth
    # rule has something to adapt to and every cell sees a different datum.
    slope.parm("snippet").set(
        "@P.y = @P.x * -0.06 + sin(@P.x * 0.11) * 0.6 + cos(@P.z * 0.09) * 0.4;")
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
]


# --- one full pass over the checks ------------------------------------------

def run_checks(out, mirror, templates, sources):
    geo = out.geometry()
    by_id = dict((t["styleId"], t) for t in templates)
    return [
        C.single_roof(geo, "at_einhof"),
        C.encloses_courtyard(geo, "at_vienna_perimeter"),
        C.rules_serve_more_than_one_style(templates),
        C.no_style_names_in_code(sources, STYLES),
        C.party_walls_are_real(geo),
        C.outward_normals(geo),
        C.heights_follow_data(geo, by_id),
        C.plinth_follows_ground(geo, SLOPED),
        C.attribute_storage(geo),
        C.elem_ids_structural(geo, mirror.geometry()),
        C.no_scratch(geo),
        C.warns_on_cap_group_split(geo),
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
    snap = {"published": C.published_names(geo), "styles": {}}
    for style in STYLES:
        vols = C.volumes(geo, style)
        snap["styles"][style] = {
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
    for style in STYLES:
        keep = hou.Geometry()
        keep.merge(geo)
        kill = [p for p in keep.prims()
                if p.attribValue("pf_style_id") != style]
        keep.deletePrims(kill, True)
        for axes, tag in (("iso", "iso"), (("x", "z"), "plan")):
            G.rasterise(os.path.join(outdir, "g1_%s_%s.png" % (style, tag)),
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
