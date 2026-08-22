"""polyChain PHASE 2 scene cases - the 2D array, built from scratch every run.

Same contract as `cases.py`, and for the same reasons: no .hip, no node
network, three `hou.Geometry` objects and a `Style` per case, so the checks
measure the builder and nothing else.

⚠️ THE FACADE KIT'S RULES NAME NO MODULES, AND THAT IS THE POINT. A rule that
names `bay` builds `bay` in every cell of every row, and the whole 25-role
lattice would then be dead code that every check passed over. With
`pc_modules` empty, `plan.candidates` resolves the CELL ROLE against the kit
(3.3's documented degrade, D78), so `default_start` picks the shopfront,
`corner_end` the pier cap, and a role the kit does not have takes D118's
lattice walk and says so. The style is four rules; the kit decides the rest.

Every module obeys D20 like the starter kit: base at y = 0, running x = 0 to
`pc_size.x`, centred across Z - so a piece's start and end faces ARE its fit
planes and "did this land where the plan said" stays a distance between two
real points.
"""

import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_env():
    pkg = os.path.join(REPO, "polyfactory").replace("\\", "/")
    pyp = "%s/scripts/python" % pkg
    if pyp not in sys.path:
        sys.path.insert(0, pyp)


setup_env()

import hou                                                       # noqa: E402
from polyfactory.polychain import Params, Rule, Style             # noqa: E402
from polyfactory.polychain import array2d as A                    # noqa: E402
from polyfactory.polychain import facade as F                     # noqa: E402
from polyfactory.polychain import kit as K                        # noqa: E402
from polyfactory.polychain import place as P                      # noqa: E402
from polyfactory.polychain import style as S                      # noqa: E402

# citygen_buildings 12.10 G2's own L footprint - 6 vertices, 5 convex and 1
# reflex - so that when buildings picks phase 2 up, its corner gate is already
# passing on our half of the seam (7.8, PC-G5).
L_FOOTPRINT = [(0, 0, 0), (24, 0, 0), (24, 0, 12), (12, 0, 12),
               (12, 0, 24), (0, 0, 24)]
RECT_FOOTPRINT = [(0, 0, 0), (18, 0, 0), (18, 0, 9), (0, 0, 9)]

BAY_X, BAY_Y = 3.00, 3.20         # the default cell
PIER_X = 0.60                     # the corner column
GROUND_Y, CORNICE_Y = 4.00, 1.00
TOWER_H = 13.0                    # shopfront + 3 scaled storeys + cornice


def _box(x, y, z=0.30, divx=1):
    g = hou.Geometry()
    K.box_mesh(g, 0.0, x, 0.0, y, -0.5 * z, 0.5 * z, divx)
    return g


def facade_kit(roles=None, kit_id="pf_facade"):
    """The PC-G5 starter facade kit: 6 of the 25 cells, authored by role.

    `roles` drops modules by role name, which is how the kit-gap cases are
    built - `facade_kit(("default", "corner"))` is a kit that knows the middle
    of the facade and nothing about its ground floor or its cornice, and every
    one of those cells then takes the lattice walk.
    """
    spec = (
        # name          x       y           deform zmode       role
        ("bay",         BAY_X,  BAY_Y,      1, "vertical", "default"),
        ("pier",        PIER_X, BAY_Y,      0, "vertical", "corner"),
        ("shopfront",   BAY_X,  GROUND_Y,   1, "vertical", "default_start"),
        ("pier_base",   PIER_X, GROUND_Y,   0, "vertical", "corner_start"),
        ("cornice",     BAY_X,  CORNICE_Y,  1, "vertical", "default_end"),
        ("pier_cap",    PIER_X, CORNICE_Y,  0, "vertical", "corner_end"),
    )
    geo = hou.Geometry()
    for name, x, y, deform, zmode, role in spec:
        if roles is not None and role not in roles:
            continue
        K.add_module(geo, name, _box(x, y, divx=4 if deform else 1),
                     size=(x, y, 0.30), deform=deform, zmode=zmode,
                     roles=role)
    K.write_manifest(geo, kit_id, 1, sources=("cases2d.facade_kit",),
                     human_scale_reference=1.8)
    return geo


def facade_style(fill="adaptive", corner_mode="miter", seed=11,
                 y_fill="adaptive", extra=()):
    """Four rules and no module names: the kit's roles decide every cell.

    The Y half is three `pc_axis = y` rules - a ground floor, a repeating
    storey and a cornice - and they DO name modules, because the Y solve reads
    a module for its nominal HEIGHT (D132) rather than for a cell role.
    """
    return Style("facade", 1, seed, rules=list(extra) + [
        Rule("default", "first", []),
        Rule("corner", "first", []),
        Rule("start", "first", ["shopfront"], axis="y"),
        Rule("default", "first", ["bay"], axis="y"),
        Rule("end", "first", ["cornice"], axis="y"),
    ], params=Params(fill=fill, corner_mode=corner_mode),
        meta={"y_params": {"fill": y_fill}})


def case(footprint, kit_geo, style, height=TOWER_H, array_id="A", **kw):
    out, report = F.build(footprint, kit_geo, style, height=height,
                          array_id=array_id, **kw)
    return {"curve": F.rows_geometry(_loops(footprint, kit_geo, style, height,
                                            array_id, kw)),
            "kit": kw.get("_kit_geo", kit_geo), "style": style,
            "out": out, "report": report, "surface": kw.get("surface_geo"),
            "overrides": None, "paths": [],
            "footprint": footprint, "height": height, "array_id": array_id,
            "kw": kw}


def _loops(footprint, kit_geo, style, height, array_id, kw):
    """The row curves the build made, re-derived for the checks to read.

    Cheap (it is the Y solve, pure maths) and it keeps `Scene` able to run the
    phase-1 checks against the same stream the kernel saw.
    """
    kit, _s, _w = K.read(kit_geo)
    _x, y_style = A.split_style(style, kw.get("y_params"))
    rows = A.plan_rows(kw.get("profile", height), kit, y_style,
                       kw.get("y_params"), array_id)
    if kw.get("area"):
        frame = A.area_frame(footprint, kw.get("auto_align", "to_spline"),
                             kw.get("expand", 0.0))
        return A.area_rows(frame, rows, kw.get("clip_mode", "remove"))
    return A.row_loops(footprint, rows, kw.get("closed", True))


def rebuild(c):
    """Cook the same inputs again into fresh geometry - the determinism check."""
    return F.build(c["footprint"], c["kit"], c["style"], height=c["height"],
                   array_id=c["array_id"], **c["kw"])


def build_all():
    built = {}
    kit = facade_kit()

    # FA - the acceptance shape: PC-G5's L footprint, 5 rows, miter corners,
    # a kit that has all six cells the figure demands.
    built["FA_L_facade"] = case(L_FOOTPRINT, kit, facade_style())

    # FB - the same figure in BEND mode. 4.3 welds the ring (D36), so there is
    # no corner slot at all and every cell is `default_*`: the control that
    # says the corner cells in FA are the corner mode's doing.
    built["FB_L_bend"] = case(L_FOOTPRINT, kit,
                              facade_style(corner_mode="bend"))

    # FC - a plain rectangle, the simplest 2D thing that can be measured.
    built["FC_rect"] = case(RECT_FOOTPRINT, kit, facade_style())

    # FD - THE KIT GAP. Only `default` and `corner` exist, so all four of the
    # ground-floor and cornice cells take D118's walk: `default_start` ->
    # `default`, `corner_end` -> `corner`, and every element that took one
    # says `pc_warn_role_fallback`. Nothing is missing from the picture; it is
    # merely plain, which is 7.2.2's whole argument for shedding Y first.
    built["FD_role_fallback"] = case(
        L_FOOTPRINT, facade_kit(("default", "corner")), facade_style())

    # FE - THE STAND-IN. A kit with only a corner column: `default` itself is
    # off the lattice, so the walk runs out and 3.4's blank box arrives - with
    # BOTH warnings on it, which is PC-G5 condition 5 (a stand-in that did not
    # say so is the defect).
    built["FE_stand_in"] = case(L_FOOTPRINT, facade_kit(("corner",)),
                                facade_style())

    # FF - EXTEND TO SIDE the other way (7.2.1). The same gap as FD, with the
    # corner column carrying `pc_extend = 0` - "this column STOPS at the
    # cornice" - so `corner_end` degrades toward the CORNICE (`default_end`)
    # instead of toward the column, and the two builds differ in exactly that.
    built["FG_extend_y"] = case(
        L_FOOTPRINT, facade_kit(("default", "corner", "default_end")),
        facade_style(), extend="y")
    built["FF_extend_x"] = case(
        L_FOOTPRINT, facade_kit(("default", "corner", "default_end")),
        facade_style(), extend="x")

    # FH - a Y profile with a real vertex: a SETBACK line at 7 m, which is a
    # `corner` ROW (D134) and the only way a `*_corner` cell can appear at
    # all. The profile is authored in (offset, height), so the solve runs on
    # its arc length exactly as X runs on the footprint's.
    built["FH_y_corner"] = case(
        L_FOOTPRINT, facade_kit(("default", "corner", "default_start",
                                 "default_end")),
        facade_style(),
        profile=A.Curve("prof", [(0, 0, 0), (0.0, 7.0, 0), (1.0, 13.0, 0)]))

    # FI - EVENLY on Y: a string course every 6 m. `evenly` is a row class
    # like any other, so `default_evenly` is a cell and the Y solve places it
    # with the same `evenly()` the X axis has always used.
    built["FI_y_evenly"] = case(
        L_FOOTPRINT, kit,
        facade_style(extra=[Rule("evenly", "first", ["cornice"], axis="y")]),
        y_params=Params(fill="adaptive", evenly_spacing=6.0))

    # FJ / FK - D124. The SAME footprint re-authored: reversed, and started at
    # a different vertex. Every `pc_elem_id` must be identical to FA's.
    built["FJ_reversed"] = case(list(reversed(L_FOOTPRINT)), kit,
                                facade_style())
    built["FK_rotated"] = case(L_FOOTPRINT[3:] + L_FOOTPRINT[:3], kit,
                               facade_style())

    # FL - 7.6, the clipped area, reduced to what a facade panel needs: a
    # closed planar rectangle standing in the XY plane both DEFINES the array
    # (extents from its own bounding box in its own frame) and trims it.
    built["FL_area_rect"] = case(
        [(0, 0, 0), (12, 0, 0), (12, 9, 0), (0, 9, 0)], kit, facade_style(),
        height=None, area=True)

    # FM - the same primitive on a TRIANGLE, where the boundary actually
    # bites: every row's span is the scanline through the band, so the fill
    # exactly fills what is left and no piece is ever built outside the line.
    built["FM_area_taper"] = case(
        [(0, 0, 0), (14, 0, 0), (0, 9, 0)], kit, facade_style(),
        height=None, area=True)

    return built


# --- the phase-2 tripwire fixtures (11.9 rule 2) ----------------------------
#
# ⚠️ THE MANY-SHORT-ROWS FIXTURE EXISTS FROM THIS CYCLE, NOT FROM PC-G7. A
# per-call fixed cost is invisible on a one-call fixture, and the fixture an
# implementer writes first is one tall tower - which is one long curve per row
# and hides exactly the defect 11.9 rule 2 names.

def tripwire_one_tower(storeys=40, bays=60):
    """ONE large facade: a 60-bay rectangle, 40 storeys. 2 400-ish cells."""
    w = bays * BAY_X * 0.5
    fp = [(0, 0, 0), (w, 0, 0), (w, 0, w), (0, 0, w)]
    return F.build(fp, facade_kit(), facade_style(),
                   height=GROUND_Y + CORNICE_Y + storeys * BAY_Y,
                   array_id="TOWER")


def tripwire_many_buildings(n=100, storeys=8, surface_geo=None):
    """100 buildings x 8 storeys = 800 SHORT rows, through ONE build call.

    The phase-2 twin of `cases.tripwire_streets_conformed`, and the fixture
    PC-G7 says can fail: `place.build` hoists the conform batch to the
    outermost loop over ALL curves (D112), so 800 rows in one call take one
    `ray` execution and 800 rows in 100 calls take 100.
    """
    kit_geo = facade_kit()
    style = facade_style()
    kit, _s, _w = K.read(kit_geo)
    _x, y_style = A.split_style(style, None)
    kit_geo2, _fb = F.close_kit(kit_geo, "x", ["default", "corner"])
    height = GROUND_Y + CORNICE_Y + (storeys - 2) * BAY_Y
    loops = []
    for i in range(n):
        r, c = divmod(i, 10)
        ox, oz = c * 30.0, r * 30.0
        fp = [(ox, 0, oz), (ox + 12, 0, oz), (ox + 12, 0, oz + 9),
              (ox, 0, oz + 9)]
        rows = A.plan_rows(height, kit, y_style, None, "B%03d" % i)
        loops.extend(A.row_loops(fp, rows))
    return (loops, kit_geo2, style, surface_geo)


def build_many_buildings(one_call=True, surface_geo=None):
    """The 800-row row stack, in ONE `place.build` call or in `n` of them.

    Both halves live here so PC-G7's "one call is not slower than 100 calls"
    is measured on one description of the fixture rather than on two.
    """
    loops, kit_geo2, style, surface = tripwire_many_buildings(
        surface_geo=surface_geo)
    x_style, _y = A.split_style(style, None)
    if one_call:
        return P.build(F.rows_geometry(loops), kit_geo2, x_style,
                       surface_geo=surface)
    out = hou.Geometry()
    report = None
    per = {}
    for loop in loops:
        per.setdefault(loop[2]["pc_curve_id"].split("#")[0], []).append(loop)
    for key in sorted(per):
        _g, report = P.build(F.rows_geometry(per[key]), kit_geo2, x_style,
                             out=out, surface_geo=surface)
    return (out, report)


def terrain(cell=10.0, amp=2.0, wave=120.0, x0=-10.0, x1=320.0,
            z0=-10.0, z1=320.0):
    """The district's ground - `cases.heightfield` at 2D fixture size."""
    import cases
    return cases.heightfield(cell, amp, wave, x0, x1, z0, z1)
