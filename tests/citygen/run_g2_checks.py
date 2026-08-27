"""Gate G2 - CAN A CORNER BE CLOSED ON A NON-RECTANGULAR FOOTPRINT?

    hython tests/citygen/run_g2_checks.py
    hython tests/citygen/run_g2_checks.py --update-baseline
    hython tests/citygen/run_g2_checks.py --mutations
    hython tests/citygen/run_g2_checks.py --cost
    hython tests/citygen/run_g2_checks.py --images [DIR]

⚠️ SEPARATE RUNNER, SHARED CHECK LIBRARY.  `checks_buildings.py` is the one
assertion module for buildings (§0.0c rule 2) and G2 adds to it rather than
starting a third; the FIXTURE is here because G1's is a district of nine
rectangles and G2's is three L-shaped lots, and merging them would make every
G1 baseline row move for a reason that has nothing to do with G1.
⚠️ THE BUDGET IS COUNTED OVER ALL THREE TEST FILES, in `budget()` below and in
G1's - a new runner that its own ratio does not count is how a size budget
stops meaning anything.

THE FIXTURE IS THE ARGUMENT, again.  §5 Theme 4 says a corner is where every
surveyed generator fails, and §12.10 G2 makes it the acceptance test.  So:

  site 1  THE SUBJECT.  A 30 x 24 m L lot with a 14 x 12 m notch, five convex
          corners and ONE REFLEX corner, inset per role with FOUR DIFFERENT
          setbacks - so the reflex corner is where two edges with different
          insets meet, which is the case `pf_inset.vfl` solves corner by
          corner and nothing has ever measured.
  site 2  THE CONTROL.  A rectangle under the SAME template.  Without it a
          failure at site 1 cannot be attributed to the L rather than to the
          pipeline, and G1's own history is full of fixture properties that
          turned out to be load-bearing.
  site 3  THE FOLD.  The same L with an AUTHORED setback (cascade level 5)
          deep enough that the bottom leg's two edges cross - the
          self-intersection §0.0's "Next up" flags as untested, and the one
          case where `pf_collapse.vfl`'s containment test may not be able to
          see what happened.  What this site reports is a FINDING, not a
          target: see §12.10b.

WHAT THIS RUN CANNOT SEE.  One kit, one cap family (`skeletonRoof`), one
building per site and no ground sample.  Nothing about UVs, about instancing,
or about whether an artist can drive any of it - there is no citygen HDA.  It
says nothing about GABLES: a gable needs a per-edge wavefront speed (the
weighted skeleton, `polyexpand2d`'s `uselocalinsidescale`), which §12.10's
brief scopes out, so every roof here is fully hipped and the eave seam is the
seam actually under test.
"""

import ast
import io
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
for path in (HERE, os.path.join(REPO, "tests", "polychain"),
             os.path.join(REPO, "polyfactory", "scripts", "python")):
    if path not in sys.path:
        sys.path.insert(0, path)

import runguard                                                  # noqa: E402
runguard.begin()

import checks_buildings as C                                     # noqa: E402
import hou                                                       # noqa: E402
from polyfactory.citygen import buildings as B                   # noqa: E402
from polyfactory.polychain import kit as K                       # noqa: E402

BASELINE = os.path.join(HERE, "baseline_g2.json")
IMAGES = os.path.join(HERE, "gate_images_g2")
STYLE = "g2_lshape"

# The L, walked CCW in (x, z).  p3 is the REFLEX corner: the walk arrives
# along -x and leaves along +z, which is the one right turn in a loop of left
# turns.  Its two edges are `rear` (4.0 m) and `interiorSide` (1.5 m), so the
# corner `pf_inset` has to solve is the one where the insets DISAGREE.
def ell(ox, oz):
    return [(ox, oz), (ox + 30, oz), (ox + 30, oz + 12), (ox + 16, oz + 12),
            (ox + 16, oz + 24), (ox, oz + 24)]


ROLES_L = ["front", "sideStreet", "rear", "interiorSide", "rear", "alley"]
ROLES_R = ["front", "sideStreet", "rear", "alley"]

# site, style, ring, per-edge roles
LOTS = [
    (1, STYLE, ell(0.0, 0.0), ROLES_L),
    (2, STYLE, [(50, 0), (78, 0), (78, 18), (50, 18)], ROLES_R),
    (3, STYLE, ell(100.0, 0.0), ROLES_L),
    (4, STYLE, ell(150.0, 0.0), ROLES_L),
]
# Authored per-vertex `pf_setback`, cascade level 5, NEGATIVE = absent (§12.4).
# Site 3 asks for 9 m off the `front` edge and 4 m off the `rear` edge of a leg
# only 12 m deep: 9 + 4 > 12, so those two offset lines CROSS and the bottom
# leg of the L turns inside out while the TALL leg (24 m deep) stays perfectly
# well formed.  A SINGLE LOCAL INVERSION inside a polygon that is otherwise
# correct - and every corner still lands inside the lot (x 2.5..28, z 8..20 in
# a lot of 0..30 x 0..24) and the signed area merely SHRINKS, +552 -> +118.5,
# with its sign intact.  So containment is silent and all three area terms are
# silent: this is the case `pf_collapse.vfl` could not see until G2, and
# finding that out is what the site is for.  ⚠️ The first draft asked for 7 m
# and did not fold at all (7 + 4 < 12) - the fixture passed while proving
# nothing, which is this build's most-repeated defect and was caught here only
# because the numbers were re-derived by hand.
#
# ⭐ SITE 4 IS THE SAME FOLD AT THE ROUNDEST NUMBER IN THE FIXTURE, and it is
# the round-N audit's `G2-4` turned into a standing case.  `front` 8.0 against
# `rear` 4.0 on the same 12 m leg makes the two offset lines MEET instead of
# crossing: the ring comes out (152.5, 8) (178, 8) (178, 8) (164.5, 8)
# (164.5, 20) (152.5, 20) - two coincident points and four collinear ones.
# Site 3's proper crossing is caught by the crossing test; this one is not,
# because that test is STRICTLY proper (`< 0.0`, and it has to be - collinear
# lot points are legal) so four collinear points give d = 0 and it cannot
# fire.  Measured before the fix: all four `pf_warn_*` at 0, a 0.35 m facade
# hole, two corners with no corner module and a roof 0.55 m off the wall top -
# in production an artist got a broken building and no warning at all.
# ⚠️ The behaviour is DISCONTINUOUS in the authored number: 7.99 leaves a 1 cm
# leg and ships silently, 8.00 self-touches and shipped silently, 8.01 crosses
# and was already detected.  8.00 is the case a human authors.
SETBACKS = {3: [9.0, 2.0, 4.0, 1.5, 4.0, 2.5],
            4: [8.0, 2.0, 4.0, 1.5, 4.0, 2.5]}
RINGS = dict((s, r) for s, _st, r, _ro in LOTS)
STYLE_OF = dict((s, st) for s, st, _r, _ro in LOTS)
ROLES = dict((s, ro) for s, _st, _r, ro in LOTS)
# Which sites the FIXTURE says cannot be built as asked -> whether the OFFSET
# is what went wrong.  Stated here, never read off the warning, for the reason
# `volume_count_matches` gives: a check that takes the code's word for what was
# supposed to happen cannot catch the code being wrong about it.
# Site 3's fold is DETECTED (`pf_collapse.vfl`'s crossing test, added by G2)
# and it is the OFFSET that went wrong there, so it degrades onto its lot
# polygon carrying `pf_warn_footprint_collapsed` - §2.2, advisory and never a
# refusal: a building still comes out, on the shape the offset came from.
DEGRADED = {3: True, 4: True}

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
g.addAttrib(hou.attribType.Vertex, 'pf_setback', -1.0)
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

# ⚠️ G2 OWNS ITS KIT rather than importing `cases2d.facade_kit`, and the reason
# is a baseline one: that fixture belongs to polyChain's suite on another
# branch, and a committed baseline whose numbers move when someone else edits
# their fixture is a baseline that reports the wrong thing.  Six modules, the
# six cells the facade page's default slots name.  §12.9's kit manifest is the
# contract this satisfies; no citygen kit SHIPS yet, and that is B4's work and
# not the gate's.
BAY_X, BAY_Y = 3.0, 3.2         # the repeating bay
PIER_X = 0.6                    # the corner pier - B6's "corner module"
GROUND_Y, CORNICE_Y = 4.0, 1.0
# ⭐ HOW MANY ROWS THE FACADE MUST HAVE, STATED HERE AND NEVER READ OFF THE
# OUTPUT.  `corner_closure` used to take the row set from the geometry it was
# measuring, so a row with no modules was not a row and its absence was
# invisible (round-N `G2-1`, `build_retrospective.md` §2a shape 1).  The number
# belongs to the KIT, not to the template: the six modules below carry three
# VERTICAL families (`*_start`, plain, `*_end`) and polyChain's row solve turns
# exactly those into rows.  ⚠️ It is NOT the template's `storeys` and the two
# must not be confused - measured, the bands are 4.0 / 4.6 / 1.0 m over a 9.6 m
# wall while the template asks for 3 x 3.2, so `pc_row` is a kit row and the
# check's own docstring used to call it a storey row.
KIT_ROWS = 3


def kit_geometry(corner_modules=True, attr="PF_G2_KIT"):
    """The gate's kit.  `corner_modules=False` drops the three `corner*`
    cells and is the CONTROL the cost bench needs - see `cost()`."""
    spec = (("bay", BAY_X, BAY_Y, 1, "default"),
            ("pier", PIER_X, BAY_Y, 0, "corner"),
            ("shopfront", BAY_X, GROUND_Y, 1, "default_start"),
            ("pier_base", PIER_X, GROUND_Y, 0, "corner_start"),
            ("cornice", BAY_X, CORNICE_Y, 1, "default_end"),
            ("pier_cap", PIER_X, CORNICE_Y, 0, "corner_end"))
    geo = hou.Geometry()
    for name, x, y, deform, role in spec:
        if not corner_modules and role.startswith("corner"):
            continue
        box = hou.Geometry()
        K.box_mesh(box, 0.0, x, 0.0, y, -0.15, 0.15, 4 if deform else 1)
        K.add_module(geo, name, box, size=(x, y, 0.30), deform=deform,
                     zmode="vertical", roles=role)
    K.write_manifest(geo, "pf_citygen_g2", 1,
                     sources=("run_g2_checks.kit_geometry",),
                     human_scale_reference=1.8)
    # ⚠️ THROUGH `hou.session`, NOT `__main__`.  A python SOP reading
    # `sys.modules['__main__']` finds whichever script started the process, so
    # the fixture resolved from this runner and vanished under any other
    # harness that imported it.  A fixture whose availability depends on who
    # is `__main__` disappears exactly when someone reuses it.
    setattr(hou.session, attr, geo)
    return geo


def scene(parent, corners="miter", lots=None):
    """Lots -> B2 mass -> B4 facade + B5 cap + B6 seam.  -> (mass, shell)."""
    src = parent.createNode("python", "lots")
    src.parm("python").set(LOT_CODE % (SETBACKS, lots or LOTS))
    kit = parent.createNode("python", "kit")
    kit.parm("python").set(
        "import hou\n"
        "hou.pwd().geometry().merge(hou.session.PF_G2_KIT)\n")
    mass = B.build(parent, src)
    return mass, B.build_shell(parent, mass, kit, corners=corners)


def cook(corners="miter", name="g2", lots=None):
    """A fresh /obj subtree per build, so no cook is served a stale cache."""
    parent = hou.node("/obj").createNode("geo", name)
    mass, shell = scene(parent, corners, lots)
    shell.cook(force=True)
    errs = [(n.name(), n.errors()) for n in (shell, shell.inputs()[0])
            if n.errors()]
    if errs:
        raise RuntimeError(str(errs)[:500])
    return parent, mass, shell


# --- mutation registry ------------------------------------------------------

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


def vx(old, new, src):
    return lambda: patch_vex([(src, old, new)])


# A cascade level that the mutation can drop, so "the corner treatment the
# TEMPLATE asked for" is a thing a registry row can take away.  ⚠️ Simulating
# it here rather than patching `B.corner_mode` because `main()` resolves the
# treatment ONCE and hands it to every cook - patching the function after that
# would change nothing and the row would "prove" the clause while doing
# nothing at all.
FORCED = {"corners": None}
# Undo hooks for a mutation that patches something other than `B.vex`, drained
# by `main()` in the same `finally` that restores it.
RESTORE = []


def bend():
    def apply():
        FORCED["corners"] = "bend"
    return apply


def drop_row(row):
    """⭐ THE AUDIT'S OWN INJECTED DEFECT, TURNED INTO A STANDING MUTATION.

    Round-N `G2-1` deleted all 98 modules of site 1's ground row and
    `corner_closure` reported `[14062, 0, 0.000, 0]` - PASS, worst gap 0.000 m
    - because the row set was derived from the surviving geometry.  So this is
    the exact input the old clause could not see, and it is a GEOMETRY
    mutation rather than a VEX one on purpose: the rows are polyChain's row
    solve, not our VEX, and the defect being guarded against is "a row came out
    of the facade asset missing", which no edit to a `.vfl` of ours produces.
    ⚠️ It moves the geometry and NOT the oracle - `KIT_ROWS` is a constant in
    this file - so it discriminates rather than dragging both sides along.
    """
    original = B.build_shell

    def patched(*args, **kw):
        out = original(*args, **kw)
        cut = out.parent().createNode("blast", "mut_drop_row")
        cut.setFirstInput(out)
        cut.parm("group").set("@pc_row=%d" % row)
        cut.parm("grouptype").set("prims")
        return cut

    def apply():
        B.build_shell = patched
        RESTORE.append(lambda: setattr(B, "build_shell", original))
    return apply


MUTATIONS = [
    # ⚠️ EVERY ROW IS A VEX OR A CASCADE MUTATION, never a template one. Three
    # of the clauses below read the template as their oracle (the setback
    # table, the pitch, the requested height), so a template-side edit would
    # move the oracle and the geometry together and pass on a build it exists
    # to reject - the trap that let R2-1 survive a whole round.
    # ⚠️ AND NOTHING HERE WRITES A PYTHON FILE. `B.vex` is swapped in memory
    # and the .vfl is re-read per cook, so no `__pycache__` can hand the next
    # run a mutant it already restored - the (mtime, size) invalidation trap
    # that cost a sibling session four phantom reds.
    ("corner_closure", "no_gaps",
     "the footprint arrives OPEN, so the facade run does not wrap: the "
     "closing edge and the two corners it joins are never built",
     vx("s@pc_array = s@pf_volume_id;",
        "s@pc_array = s@pf_volume_id;\n"
        "setprimintrinsic(0, \"closed\", @primnum, 0);", "pf_facade_in")),
    ("corner_closure", "rows_tile",
     "the facade comes out with its GROUND ROW MISSING - the exact input the "
     "audit injected, which the old clause could not see because it took its "
     "row set from the geometry it was measuring; `no_gaps` stays GREEN under "
     "it, which is what makes this the clause's own mutation and not a "
     "borrowed one",
     drop_row(0)),
    ("corner_closure", "corner_module",
     "the cascade drops the template's `miter` and falls back to `bend`, "
     "which places NO corner module (polyChain D37) - and leaves no gap "
     "either, which is what makes this the clause's discriminating mutation",
     bend()),
    ("cap_seam", "eave_meets_wall",
     "the roof forgets that its wavefront starts OUTSIDE the wall, so the "
     "whole surface floats `eave * tan(pitch)` above the facade it caps",
     vx("setprimattrib(0, \"_roof_y0\", i, top - eave * t);",
        "setprimattrib(0, \"_roof_y0\", i, top);", "pf_seam")),
    ("cap_seam", "height_as_asked",
     "B4 is handed half the height B2 built, so the facade stops short - and "
     "the roof, which follows the FACADE, follows it down without a gap. "
     "Only an oracle reading B2's own number can see this one",
     vx("f@pc_height = ytop - base;", "f@pc_height = (ytop - base) * 0.5;",
        "pf_facade_in")),
    ("cap_seam", "pitch_as_asked",
     "the roof is built at TWICE the pitch the template asked for and the "
     "eave compensates, so the surface still contains the wall-top line - "
     "6.25 m taller at the ridge, and before this clause it was GREEN on all "
     "five checks with only a baseline tripwire to show for it",
     vx("float t = tan(radians(pitch));", "float t = 2.0 * tan(radians(pitch));",
        "pf_seam")),
    ("cap_seam", "roof_closed",
     "one roof face is dropped, which is the crack a skeleton that failed on "
     "the reflex corner would leave",
     vx("int owner;", "if (pr == 0) continue;\n    int owner;", "pf_cap")),
    ("plan_follows_data", "footprint",
     "B1 applies half the setback it was given - on an L that moves six "
     "edges by four different amounts, and the BOUNDING BOX the clause used "
     "to compare would have seen two of them",
     vx('float s1 = vertex(0, "_inset", vertexindex(0, pr, i));',
        'float s1 = vertex(0, "_inset", vertexindex(0, pr, i));\n'
        's0 *= 0.5; s1 *= 0.5;', "pf_inset")),
    # ⚠️ TWO EDITS, AND THE FIRST ONE ALONE LEAVES THIS CLAUSE GREEN - measured,
    # and the reason is the pipeline defending itself. Applying the setback
    # OUTWARD grows the footprint, `pf_collapse` sees an area that grew, and
    # `pf_mass` degrades onto the lot polygon it stashed - so the building
    # lands exactly ON its lot and containment is satisfied. Reaching the hole
    # therefore needs the warning silenced as well, and only THEN does the
    # oversized mass ship. The second edit is the enabling input, not the
    # defect (R3-4's shape); it also reddens `volume_count_matches`, which has
    # its own discriminating mutation below, and the runner credits only the
    # clause a row NAMES.
    ("inside_the_lot", "inside_the_lot",
     "the setback is applied OUTWARD and the collapse warning is nailed shut, "
     "so the degrade that would have rescued it never runs and every building "
     "grows past the lot line it was measured from",
     lambda: patch_vex([
         ("pf_inset", 'float s1 = vertex(0, "_inset", vertexindex(0, pr, i));',
          'float s1 = vertex(0, "_inset", vertexindex(0, pr, i));\n'
          's0 = -s0; s1 = -s1;'),
         ("pf_collapse", "i@pf_warn_footprint_collapsed =",
          "i@pf_warn_footprint_collapsed = 0 *")])),
    # ⭐ G2's OWN PRODUCTION FINDING, as a standing assertion. Site 3's inset
    # folds the L's short leg through itself while every corner stays inside
    # the lot and the signed area merely shrinks - so containment and all
    # three area terms are silent and the bowtie SHIPPED. Delete the crossing
    # test and it ships again.
    ("volume_count_matches", "volume_count_matches",
     "`pf_collapse` loses its self-intersection test, so site 3's folded "
     "footprint stops being flagged and one solid volume is built on a bowtie",
     vx("outside || crosses ||", "outside ||", "pf_collapse")),
    # ⭐ THE SECOND ROW ON THIS CLAUSE, AND IT IS DELIBERATE.  One mutation per
    # clause is the sweep's FLOOR, not its ceiling: the crossing test and the
    # lobe test catch two different folds, and a single row would leave
    # whichever term it did not touch unproven - which is exactly how round
    # 2's defect reached its third instance.
    ("volume_count_matches", "volume_count_matches",
     "`pf_collapse` loses its LOBE test, so site 4's TANGENTIAL fold - the one "
     "a strictly-proper crossing test can never fire on, because four "
     "collinear points give d = 0 - stops being flagged and a building ships "
     "on a self-touching ring with all four `pf_warn_*` at 0",
     vx("crosses || pinched ||", "crosses ||", "pf_collapse")),
]


# --- one full pass over the checks ------------------------------------------

def run_checks(mass, shell):
    geo = shell.geometry()
    mgeo = mass.geometry()
    tpl = {STYLE: B.resolve(B.load(STYLE))}
    return [
        C.plan_follows_data(mgeo, STYLE_OF, RINGS, ROLES, tpl,
                            DEGRADED, SETBACKS),
        C.masses_inside_lots(mgeo, RINGS),
        C.volume_count_matches_template(
            mgeo, tpl, dict((s, (st, len(r))) for s, st, r, _ro in LOTS),
            degraded_sites=DEGRADED),
        C.corner_closure(geo, mgeo, rows=KIT_ROWS),
        # One style in this fixture, so the pitch is one number; a second
        # style would key it by the volume's `pf_style_id`.  ⚠️ READ FROM THE
        # TEMPLATE and never from the geometry - that is what makes it an
        # oracle, and it is safe because no registry row below is a
        # template-side edit.
        C.cap_seam(geo, mgeo, pitch=tpl[STYLE]["capFamily"]["pitchDeg"]),
    ]


def record(shell, mass):
    """VALUES, not pass/fail."""
    geo, mgeo = shell.geometry(), mass.geometry()
    snap = {"published": C.published_names(geo), "sites": {}}
    for site, style, ring, _roles in LOTS:
        fs = C.faces(mgeo, site)
        el = C.elements(geo, site)
        row = {
            "mass_faces": len(fs),
            "mass_volumes": len(set(f["pf_volume_id"] for f in fs)),
            "planBox": [round(v, 3) for v in C.plan_box(fs)] if fs else [],
            "planAreas": [round(a, 3) for a in C.plan_areas(mgeo, site)],
            "facade_elements": sum(1 for e in el if e["kind"] == "facade"),
            "roof_faces": sum(1 for e in el if e["kind"] == "roof"),
            "topY": round(max([e["ymax"] for e in el] or [0.0]), 3),
        }
        for w in ("pf_warn_footprint_collapsed", "pf_warn_topology_arity",
                  "pf_warn_unknown_rule", "pf_warn_cap_group_split"):
            row[w] = sorted(set(f[w] for f in fs))
        snap["sites"]["%d_%s" % (site, style)] = row
    return snap


# --- ⭐ the measurement §0.0d asks G2 for -----------------------------------

def cost():
    """Cook time per CORNER TREATMENT, and the miter/reference split.

    ⭐ THIS IS EVIDENCE FOR A DECISION THAT IS HANNES', polyChain's §35.6.
    §0.0d states the mechanism: `pc_envelope.vfl`'s `[vex:corners]` refuses a
    NON-DEGENERATE corner in MITER mode, the refusal is per-BUILD, and one such
    corner sends the whole build to the Python reference.  A stopwatch alone
    cannot tell that apart from "miter simply does more work", so the third row
    has to DISCRIMINATE the two.

    ⛔ THE FIRST VERSION OF THAT THIRD ROW DID NOT DISCRIMINATE ANYTHING, and
    the round-N audit's `G2-3` is why this one is different.  It raised
    `min_included_angle_deg` past 90 to make the L's corners DEGENERATE, which
    D46 falls back to bend - so it removed the refusal AND the entire miter
    corner assembly in one edit and could not tell them apart.  Measured, its
    census was 6 624 prims of `default*` cells only: bend's output reached by
    another parameter name.  That is `build_retrospective.md` §2a's third shape,
    two effects in one measurement attributed to each other.

    ⭐ THE CONTROL THAT CHANGES ONE THING, and it is the audit's.
    `pc_envelope.vfl` decides the refusal from `_cornerpt` + `pc_corner_degen`
    + `corner_mode` and NEVER from the kit.  So: miter, corners left
    non-degenerate so the refusal still fires, with a kit carrying no `corner*`
    modules.  The refusal is unchanged and only the assembly is gone.  If the
    penalty survives, the penalty IS the refusal - and it does survive, while
    building MORE geometry in LESS time than full-kit miter, which is cost
    anti-correlated with output volume across the bend/miter boundary and is
    the signature of a different code path rather than of more work.

    ⚠️ QUOTE THE WALL-CLOCK RATIO, NOT THE us/prim ONE.  The two builds emit
    different prim counts (bend 26 496, miter 20 778 - "identical prims" was
    true against bend and false against miter), so the denominators differ by
    21 % and us/prim reads 3.47x where wall-clock reads 2.7x.
    """
    import cases2d
    hou.hda.installFile(os.path.join(REPO, "polyfactory", "otls",
                                     "pf_polychain_facade.hda")
                        .replace("\\", "/"))
    hou.putenv("POLYFACTORY", os.path.join(REPO, "polyfactory")
               .replace("\\", "/"))
    kit_geometry(False, "PF_G2_KIT_NOCORNER")
    parent = hou.node("/obj").createNode("geo", "g2_cost")
    src = parent.createNode("python", "loops")
    kitn = parent.createNode("python", "kit")
    kitn.parm("python").set(
        "import hou\n"
        "hou.pwd().geometry().merge(hou.session.PF_G2_KIT)\n")
    kit0 = parent.createNode("python", "kit_no_corner")
    kit0.parm("python").set(
        "import hou\n"
        "hou.pwd().geometry().merge(hou.session.PF_G2_KIT_NOCORNER)\n")

    print("\ncook time per corner treatment  (%s)" % hou.applicationVersionString())
    print("  %-7s %-12s %6s %9s %8s %9s" % ("loops", "treatment", "minang",
                                            "cook s", "prims", "us/prim"))
    rows = {}
    for n in (1, 16, 64):
        src.parm("python").set(
            "import hou\n"
            "g = hou.pwd().geometry()\n"
            "g.addAttrib(hou.attribType.Prim, 'pc_height', 9.6)\n"
            "for i in range(%d):\n"
            "    p = g.createPolygon()\n"
            "    p.setIsClosed(True)\n"
            "    for x, z in %r:\n"
            "        pt = g.createPoint()\n"
            "        pt.setPosition(hou.Vector3((x + i * 40.0, 0.0, z)))\n"
            "        p.addVertex(pt)\n" % (n, ell(0.0, 0.0)))
        for label, mode, ang, feed in (("bend", "bend", 15.0, kitn),
                                       ("miter", "miter", 15.0, kitn),
                                       ("miter/no-corner-kit", "miter", 15.0,
                                        kit0)):
            best, prims = 1e9, 0
            for rep in range(3):
                node = parent.createNode("pf_polychain_facade",
                                         "c_%d_%d" % (n, rep))
                node.setFirstInput(src)
                node.setInput(1, feed)
                node.parm("corner_mode").set(mode)
                node.parm("min_included_angle_deg").set(ang)
                t0 = time.time()
                node.cook(force=True)
                prims = len(node.geometry().prims())
                best = min(best, time.time() - t0)
                node.destroy()
            rows[(n, label)] = best
            print("  %-7d %-12s %6.0f %9.4f %8d %9.1f"
                  % (n, label, ang, best, prims, 1e6 * best / max(prims, 1)))
    print("\n  WALL-CLOCK ratio against `bend`, by district size:")
    for n in (1, 16, 64):
        print("    %3d L-shaped buildings   miter %.2fx   "
              "miter/no-corner-kit %.2fx"
              % (n, rows[(n, "miter")] / rows[(n, "bend")],
                 rows[(n, "miter/no-corner-kit")] / rows[(n, "bend")]))
    print("  -> the third column is the DISCRIMINATOR: the refusal still fires"
          "\n     (miter, non-degenerate corners) and only the corner assembly"
          "\n     is gone, so a penalty that SURVIVES it is the refusal taking"
          "\n     the Python reference and not the miter assembly.")
    parent.destroy()
    return rows


# --- budget -----------------------------------------------------------------

TEST_FILES = ("checks_buildings.py", "run_building_checks.py",
              "run_g2_checks.py")


def budget():
    """test <= production, PRINTED EVERY RUN, over ALL THREE test files.

    ⚠️ A NEW RUNNER THAT ITS OWN RATIO DOES NOT COUNT IS HOW A BUDGET STOPS
    MEANING ANYTHING, so `run_g2_checks.py` is in the numerator from its first
    line.  Denominator unchanged from G1's rule: `buildings.py` plus every
    shipped `.vfl`, non-blank, non-comment, non-docstring.
    """
    def lines(path, mark, scope=None):
        src = io.open(path, encoding="utf-8").read()
        doc, lo, hi = set(), 1, len(src.splitlines())
        for n in (ast.walk(ast.parse(src)) if mark == "#" else ()):
            b = getattr(n, "body", None)
            if (isinstance(n, (ast.Module, ast.FunctionDef, ast.ClassDef))
                    and b and isinstance(b[0], ast.Expr)
                    and isinstance(b[0].value, ast.Constant)):
                doc.update(range(b[0].lineno, b[0].end_lineno + 1))
            if scope and isinstance(n, ast.ClassDef) and n.name == scope:
                lo, hi = n.lineno, n.end_lineno
        return sum(1 for i, l in enumerate(src.splitlines(), 1)
                   if l.strip() and i not in doc and lo <= i <= hi
                   and not l.strip().startswith(mark))
    prod = lines(os.path.join(os.path.dirname(os.path.abspath(B.__file__)),
                              "buildings.py"), "#")
    prod += sum(lines(os.path.join(B.VEX_DIR, f), "//")
                for f in os.listdir(B.VEX_DIR) if f.endswith(".vfl"))
    test = sum(lines(os.path.join(HERE, f), "#") for f in TEST_FILES)
    # ⚠️ AND THE 23 LINES THAT LIVE IN ANOTHER SUITE'S FILE.  The round-N audit
    # corrected the numerator here: `TestStorableGuard` is buildings test code
    # - G2 wrote it for `R4-5` and it tests `buildings.assert_storable` - and
    # sitting under `tests/unit/` did not stop it being ours.  It is the same
    # argument the docstring above makes about a second RUNNER, applied to a
    # file, and it moves the honest ratio by ~0.03x.
    test += lines(os.path.join(REPO, "tests", "unit", "test_citygen.py"), "#",
                  "TestStorableGuard")
    print("\nsize budget: %d test / %d production code lines = %.2fx  %s"
          % (test, prod, test / float(prod),
             "OVER (target 1.00x)" if test > prod else "ok"))
    return test, prod


def diff(new, old, path=""):
    moved = []
    if isinstance(new, dict) and isinstance(old, dict):
        for key in sorted(set(new) | set(old)):
            moved += diff(new.get(key), old.get(key), path + "/" + str(key))
    elif new != old:
        moved.append("%s  %r -> %r" % (path, old, new))
    return moved


# --- images -----------------------------------------------------------------

COLOUR = {"roof": (200, 90, 70), "facade": (150, 165, 190)}


def images(shell, mass, outdir):
    """⚠️ UNPACKED FIRST.  A packed prim has ONE VERTEX
    (houdini-procedural-modeling §6), so a wireframe drawn off the facade
    stream contains the module COUNT in dots and none of the modules - the
    exact failure dev-loop §8 records ("a gate image that showed a 3 388
    -segment fence contained 188 segments").

    ⛔ AND UNTIL THE ROUND-N FIX PASS NOTHING HERE COULD FAIL.  This function
    wrote 24 PNGs and returned; G1 at least had `image_contains_subject`, and
    `R3-6` measured even that as seeing CANVAS rather than subject (it passes
    on 1 of 97 prims and on a different scene entirely).  So G2's only image
    evidence was Hannes' look, and `gate_images` is the check that now stands
    between the two.  Three clauses, each aimed at a failure this pipeline has
    actually had:

      `unpacked`      the geometry handed to the rasteriser has MORE prims
                      than the shell it came from - unpacking a packed module
                      turns one prim into its whole box - and every render
                      drew a positive number of segments.  Neither half is
                      `R2-2`'s count-against-itself: the first compares two
                      different streams and the second guards the failure
                      §6e(i) of the retrospective records, where `rasterise`
                      returns early on empty input and a 145-line emitter
                      wrote zero PNGs and exited 0.  ⚠️ A segments-per-prim
                      floor was tried first and REJECTED on measurement: the
                      `corner*` shards are raw polygons (`G2-8`), so a packed
                      draw still clears 3 per prim and the clause could not
                      have failed.
      `every_corner`  one PNG per footprint corner, counted against the
                      fixture's own rings.  The per-corner loop `continue`s on
                      an empty crop, so a corner that framed nothing used to
                      leave no file and no trace - shape 1 again, one directory
                      listing away from the gate's subject.
      `corner_is_subject`  each corner crop contains a `corner*` element AND
                      every kit row.  This is what makes it a picture OF the
                      corner rather than a picture near it.

    ⚠️ WHAT IT STILL CANNOT SEE, and the list is longer than the list above:
    framing, scale, occlusion, colour, whether the pixels form a building at
    all, and whether any of it is CORRECT.  It proves the drawn geometry is the
    subject; it proves nothing about the picture.
    ⛔ AND IT IS NOT A SUBSTITUTE FOR THE HUMAN PASS.  §12.10's criterion ends
    "viewport-verified", that is Hannes', and an agent looking is not Hannes
    looking (§0.0g row 3).
    ⚠️ Outside the per-clause mutation sweep, like G1's, and for a stated
    reason: `--mutations` re-cooks the scene per row and rasterising 24 PNGs on
    each would multiply the sweep by the slowest thing in the runner.  The
    clauses above were each seen red by hand instead, recorded in §12.10b.
    """
    import gate_images as G
    if not os.path.isdir(outdir):
        os.makedirs(outdir)
    unpack = shell.parent().createNode("unpack", "img_unpack")
    unpack.setFirstInput(shell)
    # `pc_cell` and `pc_row` ride along because `corner_is_subject` asks what
    # a crop CONTAINS, and an unpacked module that dropped its cell tag is
    # indistinguishable from a wall.
    unpack.parm("transfer_attributes").set("pf_wall_role pf_site_id "
                                           "pf_elem_id pc_array pc_cell "
                                           "pc_row")
    unpack.cook(force=True)
    geo = unpack.geometry()

    def colour_of(prim):
        try:
            role = prim.attribValue("pf_wall_role")
        except hou.OperationFailed:
            role = ""
        return COLOUR.get(role or "facade", (150, 165, 190))

    nprims = len(geo.prims())
    packed = len(shell.geometry().prims())
    edges = sum(len(p.vertices()) for p in geo.prims())
    print("    unpacked: %d prims (from %d), %d polygon edges"
          % (nprims, packed, edges))
    flat, want_corners, drew, empty, blind = [], 0, 0, [], []
    for tag, axes, w, h in (("iso", "iso", 1500, 700),
                            ("plan", ("x", "z"), 1500, 700)):
        drawn = G.rasterise(os.path.join(outdir, "g2_all_%s.png" % tag), geo,
                            axes=axes, w=w, h=h, colour_of=colour_of)
        print("    g2_all_%s.png  %d segments drawn" % (tag, drawn))
        if drawn <= 0:
            flat.append((tag, "nothing drawn"))
    for site, _style, _ring, _roles in LOTS:
        keep = hou.Geometry()
        keep.merge(geo)
        keep.deletePrims([p for p in keep.prims()
                          if p.attribValue("pf_site_id") != site], True)
        for tag, axes in (("iso", "iso"), ("plan", ("x", "z"))):
            G.rasterise(os.path.join(outdir, "g2_%d_%s.png" % (site, tag)),
                        keep, axes=axes, w=1100, h=800, colour_of=colour_of)
    # ⭐ ONE PICTURE PER CORNER, CLASSIFIED, because the corner IS the gate.
    # §12.10 G2 asks for "no holes or misalignments at any convex/reflex
    # corner, VIEWPORT-VERIFIED", and a whole-building wireframe is where a
    # 4 cm hole goes to hide: the facade band is ~1 px wide at 1500 px across
    # 500 m of fixture. `corner_closure` is the measurement; these are what a
    # human can actually check it against, and the reflex one is the corner
    # nothing in this project had ever built.
    for site, _st, ring, _ro in LOTS:
        fp = C._cap_ring(list(C.volumes(mass.geometry(), site).values())[0])
        want_corners += len(fp)
        for j, q in enumerate(fp):
            a, b = fp[j - 1], fp[(j + 1) % len(fp)]
            turn = ((q[0] - a[0]) * (b[1] - q[1])
                    - (q[1] - a[1]) * (b[0] - q[0]))
            keep = hou.Geometry()
            keep.merge(geo)
            keep.deletePrims(
                [p for p in keep.prims()
                 if p.attribValue("pf_site_id") != site
                 or max(abs(p.intrinsicValue("bounds")[0] - q[0]),
                        abs(p.intrinsicValue("bounds")[4] - q[1])) > 2.0],
                True)
            if not keep.prims():
                empty.append((site, j))
                continue
            near = C.elements(keep)
            cells = set(str(e["pc_cell"]) for e in near)
            rows = set(e["pc_row"] for e in near if e["kind"] == "facade")
            if not any(c.startswith("corner") for c in cells):
                blind.append((site, j, "no corner* element in frame"))
            elif len(rows) != KIT_ROWS:
                blind.append((site, j, "%d of %d kit rows in frame"
                              % (len(rows), KIT_ROWS)))
            drew += 1
            G.rasterise(os.path.join(
                outdir, "g2_%d_corner%d_%s.png"
                % (site, j, "convex" if turn > 0 else "reflex")),
                keep, axes="iso", w=900, h=900, colour_of=colour_of)
    unpack.destroy()
    show(C.Result("gate_images",
                  {"unpacked": nprims > packed > 0 and not flat,
                   "every_corner": drew == want_corners > 0 and not empty,
                   "corner_is_subject": drew > 0 and not blind},
                  [nprims, packed, drew, want_corners, len(blind)],
                  "%d prims drawn from a %d-prim shell, empty renders %s; "
                  "%d of %d corner images written%s; frames missing their "
                  "subject: %s"
                  % (nprims, packed, flat or "none", drew, want_corners,
                     (", framed nothing: %s" % (empty[:3],)) if empty else "",
                     blind[:3] or "none")))


# --- main -------------------------------------------------------------------

def main():
    args = sys.argv[1:]
    kit_geometry()
    print("polyfactory package:", os.path.dirname(
        os.path.dirname(os.path.abspath(B.__file__))))

    tpl = B.resolve(B.load(STYLE))
    corners = B.corner_mode(tpl)
    print("corner treatment from the template: %r" % corners)
    parent, mass, shell = cook(corners)

    print("\nG2 checks")
    results = run_checks(mass, shell)
    for res in results:
        show(res)

    # ⚠️ THE DIFF IS COMPUTED BEFORE THE WRITE, ALWAYS, AND `--update-baseline`
    # DOES NOT SKIP IT.  This used to be an `if`/`elif`: blessing took the
    # write branch and `diff()` was never called, so the operator physically
    # could not see what they were absorbing at the moment they absorbed it.
    # `build_retrospective.md` §2a - "re-blessing is not maintenance, it is
    # erasure", and "verified after blessing is not verified" - was not merely
    # possible here, it was the only workflow the runner offered.
    snap = record(shell, mass)
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
        images(shell, mass, outdir)

    if "--mutations" in args:
        print("\nmutations - each must redden the CLAUSE it is paired with")
        names = [r.name for r in results]
        proven = set()
        for paired, clause, why, apply in MUTATIONS:
            keep = B.vex
            try:
                apply()
                _p, m2, s2 = cook(FORCED["corners"] or corners,
                                  "mut_%s_%s" % (paired, clause))
                got = dict((r.name, r) for r in run_checks(m2, s2))
                hit = got.get(paired)
                ok = (hit is not None and not hit.skipped
                      and not hit.clauses.get(clause, True))
                note = str(hit) if hit else "no check named %r" % paired
            except Exception as exc:
                ok, note = False, "MUTATION DID NOT APPLY: %s" % str(exc)[:200]
            finally:
                B.vex, FORCED["corners"] = keep, None
                while RESTORE:
                    RESTORE.pop()()
            if ok:
                proven.add((paired, clause))
            else:
                FAIL.append("mutation:%s/%s" % (paired, clause))
            print("    [%s] %-22s %-18s %s" % ("RED " if ok else "GREEN",
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

    if "--cost" in args:
        cost()

    budget()
    print("\n%d failing" % len(FAIL), FAIL or "")
    return 1 if FAIL else 0


if __name__ == "__main__":
    sys.exit(main())
