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

# ⚠️ `cases.setup_env` ITSELF - the copy here drifted the day it also began
# claiming the per-run temp dir, leaving the two facade runners on the system
# `$TEMP`.  One owner; the name is still exported (`REPO`/`os`/`sys` went with
# the copy - nothing else used them).
from cases import setup_env                                      # noqa: E402

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


def facade_kit(roles=None, kit_id="pf_facade", ground_x=BAY_X, rename=""):
    """The PC-G5 starter facade kit: 6 of the 25 cells, authored by role.

    `roles` keeps only the named roles. ⚠️ IT DEMOTES THE OTHER MODULES, IT
    DOES NOT DELETE THEM: the Y solve reads a module by NAME for its nominal
    storey height (D132), so deleting the shopfront to test a missing
    `default_start` CELL would also change the row stack, and the case would
    then be measuring two variables at once. Demoted modules keep their
    geometry and their height and lose only their claim on a cell, which is
    exactly the one variable the kit-gap cases are for.

    `rename` prefixes every module NAME and touches nothing else - same
    geometry, same sizes, same roles. It is the P2-9a F1 fixture: the audit's
    finding was that this suite's every kit is authored with the page's own
    default module names, so a page that resolved its Y slots against nothing
    agreed with an oracle doing the same thing.
    """
    spec = (
        # name          x       y           deform zmode       role
        ("bay",         BAY_X,  BAY_Y,      1, "vertical", "default"),
        ("pier",        PIER_X, BAY_Y,      0, "vertical", "corner"),
        # `ground_x` is PC-G5 condition 3's fixture knob and nothing else: a
        # ground floor whose bay is WIDER than the storeys above it is the
        # smallest thing that makes `aligned` and `free` distinguishable.
        ("shopfront",   ground_x, GROUND_Y, 1, "vertical", "default_start"),
        ("pier_base",   PIER_X, GROUND_Y,   0, "vertical", "corner_start"),
        ("cornice",     BAY_X,  CORNICE_Y,  1, "vertical", "default_end"),
        ("pier_cap",    PIER_X, CORNICE_Y,  0, "vertical", "corner_end"),
    )
    geo = hou.Geometry()
    for name, x, y, deform, zmode, role in spec:
        if roles is not None and role not in roles:
            role = "spare"          # a role no cell of the 5 x 5 table names
        K.add_module(geo, rename + name, _box(x, y, divx=4 if deform else 1),
                     size=(x, y, 0.30), deform=deform, zmode=zmode,
                     roles=role)
    K.write_manifest(geo, kit_id, 1, sources=("cases2d.facade_kit",),
                     human_scale_reference=1.8)
    return geo


def facade_style(fill="adaptive", corner_mode="miter", seed=11,
                 y_fill="adaptive", extra=(), meta=None, **params):
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
    ], params=Params(fill=fill, corner_mode=corner_mode, **params),
        meta=dict({"y_params": {"fill": y_fill}}, **(meta or {})))


# --- PC-G6: the clipped area (7.6 / P2-7) -----------------------------------
#
# The gate's own fixture, read off 7.8: "a flat plate defined by a closed
# spline with a nested exclude sub-spline (a hole) and a second, disjoint
# sub-spline beside it; extend_to_area on; a tile kit with one sliceable and
# one rigid module". The island inside the hole is the even-odd depth-2 case
# the gate's nesting condition asks for.

# ⚠️ NOT AXIS-ALIGNED, AND THAT IS THE FIXTURE'S WHOLE JOB. The first version
# of this was four rectangles on the module grid: the widened span and the
# trimmed span were the same interval on every row, NOTHING straddled the line,
# and the gate measured `slice` on two accidental pieces. A slanted plate
# corner and a DIAMOND hole put a boundary through the middle of a piece on
# every row, which is the only shape the slice policy can be judged on.
CLIP_PLATE = [(0, 0, 0), (12, 0, 0), (12, 7, 0), (7, 10, 0), (0, 10, 0)]
CLIP_HOLE = [(6, 1, 0), (10.5, 5, 0), (6, 9, 0), (1.5, 5, 0)]
# ⚠️ THE ISLAND HAS TO CONTAIN A WHOLE ROW BAND OR IT CONTAINS NOTHING. The
# first one was a 2.4 x 2.0 diamond centred on the 4..6 m band: the band's own
# two scanlines cut it at its top and bottom VERTICES, the intersection of
# those was a sliver, and PC-G6's nesting condition read [0, 0] - a hole with
# an empty island in it, which is exactly what the condition exists to reject.
CLIP_ISLAND = [(4.5, 3.5, 0), (7.5, 3.5, 0), (7.5, 6.5, 0), (4.5, 6.5, 0)]
CLIP_BESIDE = [(16, 0, 0), (24, 0, 0), (24, 10, 0), (16, 10, 0)]
CLIP_LOOPS = [CLIP_PLATE, CLIP_HOLE, CLIP_ISLAND, CLIP_BESIDE]

# C3a / D297 - the audit's F2: a 30 x 20 m plate holed 22 x 12, so a row is a
# 30 m band or two 4 m strips. Under `aligned` the strips took the 30 m row's
# 16 bays: a 2.0 m module at 0.125 m, 496 prims against free's 88.
HOLED_PLATE = [[(0, 0, 0), (30, 0, 0), (30, 20, 0), (0, 20, 0)],
               [(4, 4, 0), (26, 4, 0), (26, 16, 0), (4, 16, 0)]]
CLIP_X = CLIP_Y = 2.0


# ⚠️ PC-G6's FIXTURE HAD TWO ACCIDENTAL PROPERTIES AND BOTH WERE LOAD-BEARING
# (C2a's audit). Every loop above is wound COUNTER-CLOCKWISE and the whole
# plate sits ON THE ORIGIN. Reversed, the array frame's up axis flipped and
# every piece was built one module-height out of its own footprint - hole
# filled, `clip_inside_m` 2.0 m, and nothing failing because no fixture was
# ever wound the other way. Moved 500 m out, the cap guard's piece-scaled
# tolerance deleted 7 of 8 GENUINE caps and shipped closed boxes cut open.
# citygen builds districts at hundreds of metres and does not promise a
# winding, so this is the fixture the consumer actually has.
CLIP_FAR_X = 500.0


def clip_loops_hostile():
    return [[(p[0] + CLIP_FAR_X, p[1], p[2]) for p in reversed(loop)]
            for loop in CLIP_LOOPS]


# 7.6's contract is a closed PLANAR sub-spline, and D290/D292 are the four
# ways an artist breaks it in one input: an OPEN prim, a BOWTIE (skipped - its
# lobes wind opposite ways and the array breached its own region by 0.88 m),
# a loop 1 m off its own plane (built, warned) and one carrying
# `pc_clip_group` (D146, read and not honoured). The good plate is first so
# the build still produces an array.
CLIP_BAD_OPEN = [(0, 12, 0), (12, 12, 0), (12, 16, 0)]
CLIP_BAD_BOWTIE = [(30, 0, 0), (42, 12, 0), (42, 0, 0), (30, 12, 0)]
CLIP_BAD_NONPLANAR = [(50, 0, 0), (62, 0, 0), (62, 10, 1.0), (50, 10, 0)]
# ...and D292's, which is PLANAR and legal and still wrong: a plate tilted 10
# degrees out of vertical is solved in its own plane and built along the world
# up axis, so every piece leaves its band by 0.0260 m (measured) against
# PC-G6's 0.010 m. Nothing in the suite had ever tilted an area array.
CLIP_BAD_TILTED = [(70, 0, 0), (82, 0, 0), (82, 9.848, 1.736),
                   (70, 9.848, 1.736)]
CLIP_BAD_LOOPS = [CLIP_PLATE, CLIP_BAD_OPEN, CLIP_BAD_BOWTIE,
                  CLIP_BAD_NONPLANAR, CLIP_BAD_TILTED]


def clip_kit(kit_id="pf_clip", clip=2):
    """A tile kit with one SLICEABLE and one RIGID module, both `slice`.

    Both carry `pc_clip = 2`, which is the assertion: the rigid one CANNOT be
    cut, so D126's degrade-to-remove must fire on it and say so, while the
    sliceable one is cut on the line. One policy, two outcomes, decided by the
    module rather than by the generator.
    """
    geo = hou.Geometry()
    for name, deform in (("panel", 2), ("block", 0)):
        K.add_module(geo, name, _box(CLIP_X, CLIP_Y, divx=1),
                     size=(CLIP_X, CLIP_Y, 0.30), deform=deform,
                     zmode="vertical", roles="default", clip=clip)
    K.write_manifest(geo, kit_id, 1, sources=("cases2d.clip_kit",),
                     human_scale_reference=1.8)
    return geo


def clip_style(fill="adaptive", seed=5):
    """`sequence` over both modules, so panel and block alternate along every
    row and the boundary meets one of each."""
    return Style("clip", 1, seed, rules=[
        Rule("default", "sequence", ["panel", "block"]),
        Rule("default", "first", ["panel"], axis="y"),
    ], params=Params(fill=fill),
        meta={"y_params": {"fill": "adaptive"}})


def clip_geometry(loops, modes=None, open_at=(), groups=()):
    """The clip input as GEOMETRY - one closed polygon per sub-spline, with
    7.6's `pc_clip_mode` on the prim. The shipped contract, so the gate runs
    over the door an artist will use rather than over a Python list.

    `open_at` / `groups` are loop indices: an UNCLOSED prim and one carrying
    `pc_clip_group`, i.e. the two validation channels that were declared in
    C2 and asserted nowhere."""
    geo = hou.Geometry()
    geo.addAttrib(hou.attribType.Prim, F.CLIP_MODE_ATTR, "")
    if groups:
        geo.addAttrib(hou.attribType.Prim, F.CLIP_GROUP_ATTR, 0)
    for i, loop in enumerate(loops):
        poly = geo.createPolygon(i not in open_at)
        for p in loop:
            pt = geo.createPoint()
            pt.setPosition(p)
            poly.addVertex(pt)
        if modes and i < len(modes) and modes[i]:
            poly.setAttribValue(F.CLIP_MODE_ATTR, str(modes[i]))
        if i in groups:
            poly.setAttribValue(F.CLIP_GROUP_ATTR, 1)
    return geo


def clip_case(loops=None, clip_mode="slice", modes=None, array_ids=None,
              kit_clip=2, open_at=(), groups=()):
    """One `build_clipped` over N closed sub-splines - PC-G6's whole fixture.

    `kit_clip = -1` is the OTHER half of D126's three-state pattern: the kit
    says nothing and the array's own `clip_mode` decides. Without a case that
    passes it, the `module.clip >= 0` branch and the `preserve` policy are
    both code no run executes.
    """
    loops = list(loops if loops is not None else CLIP_LOOPS)
    kit_geo, style = clip_kit(clip=kit_clip), clip_style()
    out, report = F.build_clipped(
        clip_geometry(loops, modes, open_at, groups), kit_geo, style,
        height=None, clip_mode=clip_mode, array_ids=array_ids)
    kept = [l for i, l in enumerate(loops)
            if i not in open_at and A.is_simple(l)]
    return {"curve": hou.Geometry(), "kit": report["kit_geo"],
            "kit_src": kit_geo, "style": style, "out": out, "report": report,
            "surface": None, "overrides": None, "paths": [],
            "clip_arrays": clip_arrays(kept, modes) if kept else {},
            "clip_loops": loops, "footprint": loops[0], "height": None,
            "array_id": "", "kw": {}}


# --- 2.1's PIPELINE FACE on the 2D path (P2-4 / D293) -----------------------

# ⚠️ THE PLATE IS SPUN, AND THE SWEEP IS WHY. `to_spline` and `x_xy` name
# the SAME +X on the shipped fixture, so an `auto_align` row over two
# identical frames would be decoration. Spun 30 degrees in its own plane,
# `to_spline` tilts the frame off UP while `x_xy` keeps `ey` exactly UP.
def spun_loops(deg=30.0, loops=None):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return [[(p[0] * c - p[1] * s, p[0] * s + p[1] * c, p[2]) for p in loop]
            for loop in (loops if loops is not None else CLIP_LOOPS)]


PAYLOAD_2D = {"clip_mode": "slice", "expand": 0.25, "auto_align": "x_xy"}


# --- 7.6 / D296: the tilt ladder --------------------------------------------
#
# ⚠️ EVERY COMMITTED AREA CASE STANDS EXACTLY VERTICAL, which is how the whole
# area path shipped having only ever run at 0 degrees (C2a's F5), and 0 is IN
# the ladder: the row that must not move is as much of the measurement as the
# rows that must.
#
# ⚠️⚠️ AND SIX RUNGS OF ONE PARAMETER PROVED ONE PARAMETER (C3's audit, F1).
# Rotating about world X off a loop whose first edge already runs along world
# X leaves `frame.ex` at exactly +X on EVERY rung, so three more world-axis
# hard-codings in `place` cancelled and the ladder read green over a build
# 0.96 m out of its own plane. A rung is `(rx, rz, start)` now; the six
# original ones are the first six entries, unchanged.
TILT_LADDER = ((0.0, 0.0, 0), (2.0, 0.0, 0), (5.0, 0.0, 0), (10.0, 0.0, 0),
               (30.0, 0.0, 0), (90.0, 0.0, 0),
               (0.0, 0.0, 1), (5.0, 0.0, 1), (30.0, 0.0, 3),
               (30.0, 20.0, 0), (90.0, 45.0, 0), (10.0, 90.0, 0))

# ...and the same rungs on PC-G6's OWN loops, which is where the CUT pieces
# are - the packed writer and the deformed writer are two different functions
# and the plate only ever reaches the first (see `tilt_loops`).
TILT_DEFORM = ((0.0, 0.0, 0), (30.0, 0.0, 1), (30.0, 20.0, 0),
               (90.0, 45.0, 0))


def tilt_loops(rx, rz=0.0, start=0, loops=None):
    """PC-G6's OWN loops taken out of the world plane, same rung vocabulary.

    ⚠️ THE PLATE CANNOT REACH THE DEFORM WRITER, measured not assumed: an
    adaptive fill on a rectangle never straddles its own region boundary, so
    `tilt_plate` is 100 packed / 0 deformed at every tilt - which is how
    `2d_deform_grows_world_y` SURVIVED the twelve-rung ladder by reddening
    nothing at all. A CUT piece is the only thing here that reaches it."""
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    out = []
    for loop in (loops if loops is not None else CLIP_LOOPS):
        rot = []
        for (x, y, z) in loop[start:] + loop[:start]:
            y2, z2 = y * cx - z * sx, y * sx + z * cx
            rot.append((x * cz - y2 * sz, x * sz + y2 * cz, z2))
        out.append(rot)
    return out


def tilt_plate(rx, rz=0.0, start=0, size=20.0):
    """A 20 x 20 m plate rolled `rx` about world X then `rz` about world Z and
    re-authored from vertex `start`. Vertical at (0, 0, 0); a FLOOR PLATE at
    rx = 90, which is 7.6's "flat roofs, floor plates" by name."""
    q = [(0, 0), (size, 0), (size, size), (0, size)]
    cx, sx = math.cos(math.radians(rx)), math.sin(math.radians(rx))
    cz, sz = math.cos(math.radians(rz)), math.sin(math.radians(rz))
    out = []
    for (x, y) in q[start:] + q[:start]:
        y, z = y * cx, y * sx
        out.append((x * cz - y * sz, x * sz + y * cz, z))
    return out


def payload_build(nudge=None, payload=False, clip=None, meta=None):
    """PC-G6's clip input with its 2D settings on ONE of 2.1's two faces.

    `payload=False` puts them in the KEYWORDS - which is the 2D path's parm
    face, 7.6's own wording. `payload=True` writes them into a 7.3.2
    `pc_style_meta` block through `facade.meta_2d`, puts THAT on geometry with
    `style.write` and reads it back with `style.read`, so the pipeline face is
    exercised as geometry and not as a `Style` object a test built by hand.
    `nudge` always goes to the keywords: under a payload it must be inert.
    `meta` adds TOP-LEVEL keys (D300); the third return value is what
    `style.read` said about them."""
    kw = dict(PAYLOAD_2D)
    style, read_warns = clip_style(), []
    if payload:
        geo = hou.Geometry()
        S.write(geo, Style(style.style_id, style.version, style.seed,
                           style.rules, style.params,
                           dict(style.meta, **dict(F.meta_2d(clip=clip, **kw),
                                                   **(meta or {})))))
        style, read_warns = S.read(geo)
        kw = {}
    kw.update(nudge or {})
    return F.build_clipped(clip_geometry(spun_loops()), clip_kit(clip=2),
                           style, height=None, **kw) + (read_warns,)


def clip_arrays(loops, modes=None):
    """{array_id: (frame, region, [member loop indices])} - the SAME nesting
    the builder used, re-derived for the checks to measure against.

    Cheap (pure maths, no geometry) and it keeps the checks from having to
    know how `facade.build_many` names an array.
    """
    depth, include, parent, _chart = A.nest(loops, modes)
    members = A.array_members(parent)
    out = {}
    for root in sorted(members):
        aid = "A" if len(loops) == 1 else "A%03d" % root
        frame = A.area_frame(loops[root])
        mem = members[root]
        out[aid] = (frame,
                    A.region_for(frame, [loops[j] for j in mem],
                                 [include[j] for j in mem],
                                 [depth[j] for j in mem]),
                    list(mem))
    return out


def case(footprint, kit_geo, style, height=TOWER_H, array_id="A", **kw):
    out, report = F.build(footprint, kit_geo, style, height=height,
                          array_id=array_id, **kw)
    return {# ⚠️ THE ROW STREAM THE KERNEL SAW, off the report - not
            # re-derived. Re-deriving it meant re-spelling `build_many`'s own
            # precedence here, and there were three copies of it by D122 (the
            # payload's settings, the closed kit, the aligned bay stamp); a
            # copy that drifts makes every phase-1 check measure the seam
            # between two builds instead of the build.
            "curve": F.rows_geometry(report["loops"], report["row_flags"]),
            # the CLOSED kit, which is what the kernel read (D136) - a check
            # that re-read the authored kit would resolve a different set of
            # roles from the builder and report the difference as a defect.
            "kit": report["kit_geo"], "kit_src": kit_geo, "style": style,
            "out": out, "report": report, "surface": kw.get("surface_geo"),
            "overrides": None, "paths": [],
            "footprint": footprint, "height": height, "array_id": array_id,
            "kw": kw}


def rebuild(c):
    """Cook the same inputs again into fresh geometry - the determinism check.

    ⚠️ FROM THE AUTHORED KIT (`kit_src`), not from the closed copy the checks
    read. Re-closing an already-closed kit finds every role declared, so the
    fallback map comes back EMPTY and the rebuild is a different build - which
    is a real property worth knowing (the closure is idempotent on geometry
    and not on warnings) and is not what determinism is asking about.
    """
    return F.build(c["footprint"], c["kit_src"], c["style"],
                   height=c["height"], array_id=c["array_id"], **c["kw"])


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
    # ⚠️ THE TURN HAS TO CLEAR `corner_angle_deg` (30 by default). The
    # profile this case shipped with turned 9.46 degrees, produced NO `corner`
    # row at all, and passed for an unrelated reason - so the whole `*_corner`
    # column of the 25-role table was untested while the case was named for
    # it. 4.0 m of offset over 6 m of rise is 33.69 degrees and gives
    # `['start', 'default', 'corner', 'default', 'end']`.
    built["FH_y_corner"] = case(
        L_FOOTPRINT, facade_kit(("default", "corner", "default_start",
                                 "default_end")),
        facade_style(),
        profile=A.Curve("prof", [(0, 0, 0), (0.0, 7.0, 0), (4.0, 13.0, 0)]))

    # FI - EVENLY on Y: a string course every 6 m. `evenly` is a row class
    # like any other, so `default_evenly` is a cell and the Y solve places it
    # with the same `evenly()` the X axis has always used.
    built["FI_y_evenly"] = case(
        L_FOOTPRINT, kit,
        facade_style(extra=[Rule("evenly", "first", ["cornice"], axis="y")],
                     meta={"y_params": {"fill": "adaptive",
                                        "evenly_spacing": 6.0}}))

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

    # FN / FO / FP - 7.5's "vertex type is data", carried THROUGH D124. The
    # same L with its REFLEX vertex suppressed, authored three ways. FJ/FK
    # pass no `corner_flags` at all, so the only committed identity check ran
    # on the one input where authored and canonical vertex order coincide -
    # and the emitter was indexing the authored flag list by CANONICAL
    # position, so re-authoring moved the suppression onto a different corner.
    # Flags are given in each build's OWN authored order and name the same
    # physical vertex (12, 0, 12) in all three.
    for nm, fp, fl in (
            ("FN_flags", L_FOOTPRINT, [0, 0, 0, -1, 0, 0]),
            ("FO_flags_reversed", list(reversed(L_FOOTPRINT)),
             [0, 0, -1, 0, 0, 0]),
            ("FP_flags_rotated", L_FOOTPRINT[3:] + L_FOOTPRINT[:3],
             [-1, 0, 0, 0, 0, 0])):
        built[nm] = case(fp, kit, facade_style(), corner_flags=fl)

    # FQ - 7.6's `preserve` on a CONCAVE boundary, which is the only shape
    # that can fail it. `preserve` used to collapse the row to (min, max) of
    # both scanlines, so a U-shaped panel came back as one span straight
    # across its 4 m notch and three whole bays were built 2 m inside the
    # hole with `clip_inside_m` at 0.3333 m. Both committed area cases use
    # the default `remove`, i.e. the mode that cannot fail this.
    built["FQ_area_preserve"] = case(
        [(0, 0, 0), (10, 0, 0), (10, 10, 0), (7, 10, 0), (7, 3, 0),
         (3, 3, 0), (3, 10, 0), (0, 10, 0)], kit, facade_style(),
        height=None, area=True, clip_mode="preserve")

    # FR - E1/D119 on BOTH slots, which is where the scoping was missing.
    # "the cornice row gets the cap, every other row gets the pier" is two
    # rules; `corner._corner_rule` asked `rules_for("corner")` with no row
    # class, so the scoped rule leaked onto every row and the 1.0 m cap became
    # the corner column of the ground floor.
    built["FR_rule_scoped"] = case(
        RECT_FOOTPRINT, kit,
        facade_style(extra=[Rule("corner", "first", ["pier_cap"],
                                 yclass="end"),
                            Rule("corner", "first", ["pier"])]))

    # FS - a `sequence` X rule that names no modules, the documented
    # role-resolution idiom. `plan._unit` asked `candidates(rule, kit)`
    # WITHOUT the cell role, so the ground floor silently resolved the bare
    # `default` slot and a 3.2 m bay was stretched into the 4.0 m band.
    built["FS_sequence_cells"] = case(
        RECT_FOOTPRINT, kit,
        facade_style(extra=[Rule("default", "sequence", [])]))

    # FT / FU - D139's TWO row-warning channels, which nothing ran. The
    # decision landed with its repros measured by hand and never committed, so
    # deleting the propagation outright (`extra = ()` in `plan.classify`) left
    # 19 cases and 346 unit tests green: `pc_warn_row_overflow` and
    # `pc_warn_row_kit_gap` appeared in no case, no `EXPECTED_WARNS` entry and
    # no unit test. A warning nothing asserts is a warning that can be
    # deleted by accident, which is the exact failure D139 exists to prevent.
    #
    # FT - 3.2 m of height cannot hold the 4.0 m ground floor AND the 1.0 m
    # cornice, so D13's cascade drops the mandatory `end` and the building
    # ships one storey short. Raised on every row, because the missing one has
    # no geometry to carry it.
    built["FT_row_overflow"] = case(RECT_FOOTPRINT, kit, facade_style(),
                                    height=BAY_Y)

    # FU - the Y style names a module the kit does not carry, so the Y solve's
    # own `pc_warn_kit_gap` is renamed on the way out. The rename is the
    # point: without it an element reads as though ITS OWN X run had no
    # module, when what is missing is the storey it stands in.
    built["FU_row_kit_gap"] = case(
        RECT_FOOTPRINT, kit,
        facade_style(extra=[Rule("end", "first", ["no_such_cornice"],
                                 axis="y")]))

    # FV - a row the clip boundary leaves NOTHING of. `area_rows` records it
    # into `rows_unbuilt` and `facade.build_many` turns that into
    # `pc_warn_row_clipped_out`, and until this case both were dead code:
    # neither string appeared anywhere in the suite and neither fired in any
    # run. FM's dropped band is caught by `cell_grid`'s own solved-vs-built
    # difference instead, so the channel D142 added was never the thing doing
    # the catching. A 13 m stack over a 9 m boundary is the plain form of it.
    built["FV_area_short"] = case(
        [(0, 0, 0), (12, 0, 0), (12, 9, 0), (0, 9, 0)], kit, facade_style(),
        height=TOWER_H, area=True)

    # FW - PC-G5 CONDITION 3's MISSING HALF. The gate asks whether the Y fit's
    # `aligned` mode makes every row share the datum row's bay boundaries; on
    # every other case here the rows share them anyway, because one kit fits
    # one set of legs the same way five times over. A 4.5 m shopfront under a
    # 3.0 m bay makes the ground row fit DIFFERENTLY, so `free` is now visibly
    # free - and when D122's `aligned` lands (C3) this is the fixture that can
    # tell the two apart. PC-G5's own L, so the condition is judged on the
    # gate's own figure.
    built["FW_y_free"] = case(L_FOOTPRINT, facade_kit(ground_x=4.5),
                              facade_style())

    # FW2 - D122's `aligned`, on FW's own fixture and DRIVEN FROM THE PAYLOAD
    # rather than from a keyword, so PC-G5 condition 3 is judged through 2.1's
    # pipeline face. Everything else is FW's: same footprint, same 4.5 m
    # shopfront under a 3.0 m bay, same style. The ONLY difference is
    # `pc_style_meta["y_mode"]`, and `bay_alignment` must go [3, 4] -> [0, 4].
    built["FW_y_aligned"] = case(L_FOOTPRINT, facade_kit(ground_x=4.5),
                                 facade_style(meta={"y_mode": "aligned"}))

    # FX - 7.4's DEGRADE, which is otherwise a branch nothing runs. An X
    # `evenly` rule puts anchors on every section, the default fill becomes
    # several runs, and one datum count cannot say which run holds how many -
    # so the row falls back to its own free solve and every piece of it says
    # `pc_warn_y_align_lost`. Warn, never block: the facade still builds.
    built["FX_y_align_lost"] = case(
        L_FOOTPRINT, facade_kit(ground_x=4.5),
        facade_style(extra=[Rule("evenly", "first", ["pier"])],
                     meta={"y_mode": "aligned"}, evenly_spacing=6.0))

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


def district(n=100, storeys=8):
    """100 building footprints on a 10 x 10 grid, plus their kit and style.

    ⚠️ ONE DESCRIPTION OF THE FIXTURE, USED BY BOTH HALVES OF THE BENCH. It
    used to hand-assemble the loops and call `place.build` directly, so the
    "ONE call" row measured a code path the shipped adapter could not reach:
    `facade.build` took one footprint and made one `place.build`, i.e. the
    100-call column. `facade.build_many` is the entry point now and this
    returns its arguments.
    """
    fps = []
    for i in range(n):
        r, c = divmod(i, 10)
        ox, oz = c * 30.0, r * 30.0
        fps.append([(ox, 0, oz), (ox + 12, 0, oz), (ox + 12, 0, oz + 9),
                    (ox, 0, oz + 9)])
    return (fps, facade_kit(), facade_style(),
            GROUND_Y + CORNICE_Y + (storeys - 2) * BAY_Y,
            ["B%03d" % i for i in range(n)])


def tripwire_many_buildings(n=100, storeys=8, surface_geo=None):
    """100 buildings x 8 storeys = 800 SHORT rows, through ONE build call.

    The phase-2 twin of `cases.tripwire_streets_conformed`, and the fixture
    PC-G7 says can fail: `place.build` hoists the conform batch to the
    outermost loop over ALL curves (D112), so 800 rows in one call take one
    `ray` execution and 800 rows in 100 calls take 100.
    """
    fps, kit_geo, style, height, ids = district(n, storeys)
    kit, _s, _w = K.read(kit_geo)
    _x, y_style = A.split_style(style, None)
    kit_geo2, _fb, _col = F.close_kit(kit_geo, "x", ["default", "corner"])
    loops = []
    for fp, aid in zip(fps, ids):
        rows = A.plan_rows(height, kit, y_style, None, aid)
        loops.extend(A.row_loops(fp, rows))
    return (loops, kit_geo2, style, surface_geo)


_ROWS_CACHE = {}


def tripwire_row_emission():
    """JUST the emitter, over 800 rows - `rows_wrappers_built`'s subject.

    The loops are prepared ONCE and cached, because the fixture also builds a
    kit and `K.add_module` legitimately writes attributes through wrappers -
    counting those would make the tripwire read 54 on a perfect emitter and
    measure nothing at all.
    """
    if "loops" not in _ROWS_CACHE:
        _ROWS_CACHE["loops"] = tripwire_many_buildings()[0]
    return F.rows_geometry(_ROWS_CACHE["loops"])


def build_many_buildings(one_call=True, surface_geo=None, accumulate=False):
    """The 800-row row stack, in ONE `facade.build_many` or in 100 `build`s.

    Both halves live here so PC-G7's "one call is not slower than 100 calls"
    is measured on one description of the fixture rather than on two.

    ⚠️ THE TWO HALVES MUST DO IDENTICAL WORK OR THE RATIO IS AN ARTEFACT, and
    it was: the many-call half passed one shared `out` through all 100 calls,
    so `place._stamp_bulk` re-read and re-wrote the whole prim attribute
    column on every call - O(n^2), 51 % of that half's own runtime - and the
    one-call half paid it once. Measured fairly (fresh geometry per call, the
    merge into one geometry added back so both produce the same prim count)
    the one-call win is much smaller than the 2.95x/3.98x that was recorded,
    which is D115 restated from what it actually measures. `accumulate=True`
    keeps the old `out=` shape so the O(n^2) fix has a fixture too.
    """
    fps, kit_geo, style, height, ids = district()
    if one_call:
        return F.build_many(fps, kit_geo, style, height=height,
                            array_ids=ids, surface_geo=surface_geo)
    out = hou.Geometry()
    total = {"curves": 0, "packed": 0, "deformed": 0, "plan": [],
             "warn_counts": {}, "kit_warnings": []}
    for fp, aid in zip(fps, ids):
        g, report = F.build(fp, kit_geo, style, height=height, array_id=aid,
                            out=out if accumulate else None,
                            surface_geo=surface_geo)
        if not accumulate:
            out.merge(g)
        for field in ("curves", "packed", "deformed"):
            total[field] += report[field]
        total["plan"].extend(report["plan"])
    return (out, total)


def terrain(cell=2.34, amp=2.0, wave=120.0, x0=-10.0, x1=320.0,
            z0=-10.0, z1=320.0):
    """The district's ground - `cases.heightfield` at 2D fixture size.

    ⚠️ THE CELL SIZE IS THE MEASUREMENT. `ray` rebuilds its surface input on
    every execution and that fixed cost scales with the SURFACE: 11.8 P5c
    measured 0.34 ms at 5 022 terrain prims, 0.71 ms at 20 088 and 2.25 ms at
    80 352. At the 10 m cell this fixture shipped with, the ground is 1 089
    prims - 4.6x SMALLER than the cheapest surface that number was ever
    measured on - so 99 saved `ray` executions were worth about 34 ms against
    a 4 s row and the batch could not possibly show its value. 2.34 m gives
    19 881 prims, i.e. P5c's middle rung, which is the size the one-call rule
    should be argued from.
    """
    import cases
    return cases.heightfield(cell, amp, wave, x0, x1, z0, z1)
