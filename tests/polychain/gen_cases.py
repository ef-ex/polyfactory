"""THE SEEDED SCENE GENERATOR - v2 principle 2, on the Houdini side.

    from tests.polychain import gen_cases
    case = gen_cases.make(seed)          # -> curve/kit/style/parms, per seed

Hypothesis owns the pure-Python solve (`tests/unit/test_polychain_properties`).
This is its hython half: one integer in, one whole scene out, and NOTHING is
hand-picked.  Every "the check was fine but no fixture ever reached the code"
miss in `ideas/build_retrospective.md` is a shape a hand-written case set did
not contain, and each of them is a dimension of this generator:

  * SHARED POINTS between prims - `graph_fuse`'s own output, present in
    production and in 0 of 89 v1 parity cases (T1's finding).
  * DUPLICATE points, degenerate segments and 2-point curves - what `_clean`
    exists for and what a tidy fixture never has.
  * `pc_curve_id` at a NON-STRING STORAGE (int / float) and with NON-ASCII
    text - the `edge_id` class of defect: an attribute's storage is part of
    its contract (conventions.md), and the one that crashed a whole gate
    through `.split()` was an int where a string was assumed.
  * DUPLICATE curve ids across prims, and markers on top of them.
  * kits WITHOUT a `corner` role, with variants, and with a corner module
    wider than the leg it must fit - the branches a fixed starter kit skips.
  * parm/payload combinations, including corner modes, fill modes and z-modes
    that no committed case pairs together.

The seed is the whole fixture: a failing run prints it, and the repro is
`make(<seed>)`.  A seed worth keeping goes in `PINS` below - one line, the
regression fixture in its cheapest possible form.

WHAT IT CANNOT SEE: it generates INPUT only.  Whether the two paths agree is
the differential comparator's job (`diff.compare`), and whether either path is
RIGHT is nobody's job here - that is what the gate images and the human at the
milestone are for.
"""

import math
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cases                                                      # noqa: E402
import hou                                                        # noqa: E402
from polyfactory.polychain import Params, Rule, Style             # noqa: E402
from polyfactory.polychain import kit as K                        # noqa: E402

# Seeds that once failed.  One line each, with what they caught - this is the
# only form a hand fixture still takes under v2 (skill principle 2).  They run
# FIRST on every invocation, however small `--seeds` is, which is also what
# gives `run_generated.KNOWN`'s "still occurs" assertion its input.
PINS = (
    27,     # `pc_module` inside the packed contents, native only (KNOWN #1)
    42,     # same, with an emoji curve id and fill=scale
    150,    # same, corner_mode=bend - it is not a miter-only divergence
    170,    # same, with an EMPTY-STRING curve id
    203,    # same, with no `corner` role in the kit at all
)

FILLS = ("adaptive", "tile", "scale", "count")
CORNERS = ("bend", "miter", "fillet")
ZMODES = ("", "adaptive", "vertical", "stepped")
JUSTIFY = ("start", "center", "end")
# Non-ASCII, and deliberately from three scripts plus an emoji: an id survives
# a round trip through a VEX string attribute, a Python dict key and a JSON
# payload, and cp1252 consoles have already killed one diagnostic here.
IDS = ("A", "curve_1", "rue-de-l'Église", "フェンス",
       "улица", "wall\U0001f9f1", "  padded  ", "")


def _rng(seed):
    return random.Random(seed * 2654435761 % (2 ** 61 - 1))


# ⚠️ HALF THE SEEDS ARE GENERATED IN THE **NATIVE LANE**, AND THAT IS THE
# MOST IMPORTANT LINE IN THIS FILE.
#
# `Stage = output` is a GUARDED fork: `pc_envelope` refuses a build that the
# native chain cannot answer and falls back to the same Python kernel
# `Stage = reference` runs.  A refused case therefore compares Python WITH
# PYTHON and cannot fail - and the first version of this generator produced
# almost nothing but refused cases.  MEASURED, by reading `_native_ok` off
# `pc_envelope` on 60 seeds: **the native chain answered 2 of them, 3 %.**
# The registry found it: `generated_pc_local_scaled` (a 1.5x scale on the
# native `pc_local`) SURVIVED the whole 400-seed differential and "reddened
# nothing at all".
#
# `_native_ok` requires: no corners, no duplicate curve ids, no marker inside
# a prim, no type-bad attribute, no row warnings, at least one prim, and a
# CONFIG the resolver admits (no surface, no fillet, no fix_slope, no
# flatten, no flat band).  The native lane builds exactly that; the wide lane
# keeps attacking everything else, which is what found the packed-contents
# divergence.
NATIVE_LANE = 2          # every Nth seed is built to be native-answerable
# The native lane's turn ceiling, in degrees, and the corner angle it is
# generated against.  A turn under the corner angle is not a corner, so
# `_cornerpt` stays empty and the guard admits the build - while the curve is
# still curved enough (and climbs enough) for the deform gate to unpack.
NATIVE_TURN_DEG = 22.0
NATIVE_CORNER_ANGLE = 45.0


# --- the curve --------------------------------------------------------------

def _points(rng, straight=False):
    """A polyline with real corners, and sometimes a degenerate one.

    `straight` is the native lane: GENTLY curving and gently climbing, never
    turning more than `NATIVE_TURN_DEG`, so `_cornerpt` stays empty while the
    geometry is still curved enough to make the deform gate unpack pieces.

    ⚠️ THE FIRST NATIVE LANE WAS DEAD STRAIGHT AND FLAT, and that reached the
    native chain's PACKED branch and nothing else.  `pc_deform.vfl` - which
    writes `pc_local` - never ran, so `generated_pc_local_scaled` survived a
    second time with the lane already at 52 %.  Reaching a code path is not
    the same as reaching the branch inside it, and only the mutation could
    tell the two apart.
    """
    if straight:
        n = rng.randint(4, 12)
        pts, x, z, y = [], 0.0, 0.0, 0.0
        bear = 0.0
        for _ in range(n):
            pts.append((round(x, 4), round(y, 4), round(z, 4)))
            step = rng.uniform(0.8, 6.0)
            bear += math.radians(rng.uniform(-NATIVE_TURN_DEG * 0.8,
                                             NATIVE_TURN_DEG * 0.8))
            x += step * math.cos(bear)
            z += step * math.sin(bear)
            y += rng.uniform(-0.4, 0.4)
        return pts
    n = rng.randint(2, 9)
    pts, x, z = [], 0.0, 0.0
    for _ in range(n):
        pts.append((round(x, 4), 0.0, round(z, 4)))
        step = rng.choice([rng.uniform(0.05, 3.0), rng.uniform(3.0, 25.0)])
        ang = rng.choice([0.0, 0.0, rng.uniform(-math.pi, math.pi)])
        x += step * math.cos(ang)
        z += step * math.sin(ang)
    if rng.random() < 0.30:                 # DUPLICATE point - `_clean`'s job
        i = rng.randrange(len(pts))
        pts.insert(i, pts[i])
    if rng.random() < 0.15:                 # a spike: two duplicates in a row
        pts = pts[:1] + [pts[0], pts[0]] + pts[1:]
    return pts


def _curve_geo(rng, native=False):
    """One or two prims, sometimes SHARING a point, ids at a random storage."""
    geo = hou.Geometry()
    storage = "string" if native else rng.choice(
        ["string", "string", "int", "float"])
    ids = [rng.choice(IDS) for _ in range(2)]
    if native:
        ids = ["N%d" % rng.randint(0, 9999), "N%d" % rng.randint(0, 9999)]
    elif rng.random() < 0.25:                            # DUPLICATE curve ids
        ids[1] = ids[0]
    if storage == "string":
        geo.addAttrib(hou.attribType.Prim, "pc_curve_id", "")
        vals = ids
    elif storage == "int":
        geo.addAttrib(hou.attribType.Prim, "pc_curve_id", 0)
        vals = [rng.randint(-3, 3) for _ in ids]
    else:
        geo.addAttrib(hou.attribType.Prim, "pc_curve_id", 0.0)
        vals = [float(rng.randint(-3, 3)) for _ in ids]

    nprims = 1 if (native or rng.random() < 0.55) else 2
    shared = None
    for k in range(nprims):
        pts = _points(rng, straight=native)
        poly = geo.createPolygon(False if native else bool(rng.random() < 0.30))
        for j, p in enumerate(pts):
            if shared is not None and j == 0 and rng.random() < 0.7:
                poly.addVertex(shared)          # graph_fuse's junction point
                continue
            pt = geo.createPoint()
            pt.setPosition(p)
            poly.addVertex(pt)
        poly.setAttribValue("pc_curve_id", vals[k])
        if k == 0 and nprims > 1 and poly.points():
            shared = poly.points()[-1]
    return geo, storage, vals


def _markers(rng, geo, ids):
    """0-2 markers, addressed by `pc_dist` OR `pc_u` - never both (D-mixed)."""
    if rng.random() < 0.55:
        return 0
    n = rng.randint(1, 2)
    by_dist = rng.random() < 0.5
    for i in range(n):
        cid = rng.choice(ids)
        kw = {"dist": rng.uniform(0.0, 30.0)} if by_dist \
            else {"u": rng.uniform(0.0, 1.0)}
        cases.marker(geo, (rng.uniform(0, 20), 2.0, rng.uniform(-5, 5)),
                     cid, i + 1, **kw)
    return n


# --- the kit ----------------------------------------------------------------

def _box(x, y, z, divx=1):
    g = hou.Geometry()
    K.box_mesh(g, 0.0, x, 0.0, y, -z * 0.5, z * 0.5, divx)
    return g


def _kit_geo(rng, native=False):
    """A kit whose ROLES, VARIANTS and corner width are all generated.

    The three branches a fixed starter kit cannot reach, in one place: no
    `corner` role at all (so the corner slot must degrade), a corner module
    WIDER than the shortest leg (so the reserve cannot fit), and two modules
    sharing a role with different `pc_variant` values (so variant selection
    has something to select between).
    """
    geo = hou.Geometry()
    panel_len = round(rng.uniform(0.3, 4.0), 3)
    K.add_module(geo, "panel", _box(panel_len, 1.0, 0.06, 4),
                 size=(panel_len, 0.9, 0.06), deform=rng.choice([0, 1, 2]),
                 zmode=rng.choice(ZMODES[1:]), roles="default panel",
                 pad=(round(rng.uniform(-0.2, 0.5), 3),
                      round(rng.uniform(-0.2, 0.5), 3)))
    K.add_module(geo, "post", _box(0.12, 1.2, 0.12),
                 size=(0.12, 1.2, 0.12), deform=0, zmode="stepped",
                 roles="default post start end")
    has_corner = False if native else rng.random() < 0.7
    if has_corner:
        # WIDER than a short leg, on purpose, one time in three.
        cw = round(rng.choice([0.16, 0.16, rng.uniform(2.0, 9.0)]), 3)
        K.add_module(geo, "corner_post", _box(cw, 1.3, cw),
                     size=(cw, 1.3, cw), deform=0, zmode="stepped",
                     roles="corner")
    nvar = 0 if native else rng.choice([0, 0, 2, 3])
    for i in range(nvar):
        K.add_module(geo, "panel_v%d" % i, _box(panel_len, 1.0, 0.06, 4),
                     size=(panel_len, 0.9, 0.06), deform=1, zmode="vertical",
                     roles="default panel", variant="v%d" % i,
                     weight=round(rng.uniform(0.1, 3.0), 3))
    K.write_manifest(geo, "gen_kit", 1, human_scale_reference=1.8)
    return geo, has_corner, nvar


# --- the style and the parm face --------------------------------------------

def _style(rng, has_corner, nvar, native=False):
    if native:
        return Style("gen%d" % rng.randint(0, 9999), seed=rng.randint(0, 9999),
                     rules=[Rule("default", "first", ["panel"])],
                     params=Params(fill="adaptive",
                                   corner_angle_deg=NATIVE_CORNER_ANGLE,
                                   adaptive_pct=round(rng.uniform(0.0, 100.0),
                                                      2),
                                   corner_mode="bend", fillet_radius=0.0,
                                   evenly_spacing=0.0, evenly_count=0,
                                   justify=rng.choice(JUSTIFY),
                                   zmode=rng.choice(ZMODES),
                                   fix_slope=False))
    rules = [Rule("default", rng.choice(["first", "random", "weighted"]),
                  ["panel"] + ["panel_v%d" % i for i in range(nvar)])]
    if rng.random() < 0.6:
        rules.append(Rule("evenly", "first", ["post"]))
    if has_corner and rng.random() < 0.7:
        rules.append(Rule("corner", "first", ["corner_post"]))
    p = Params(
        fill=rng.choice(FILLS), count=rng.randint(1, 6),
        adaptive_pct=round(rng.uniform(0.0, 100.0), 2),
        corner_angle_deg=round(rng.uniform(5.0, 90.0), 2),
        corner_mode=rng.choice(CORNERS),
        corner_offset_pct=round(rng.uniform(0.0, 60.0), 2),
        fillet_radius=round(rng.choice([0.0, rng.uniform(0.1, 3.0)]), 3),
        fillet_segments=rng.randint(2, 10),
        evenly_spacing=round(rng.choice([0.0, rng.uniform(0.2, 6.0)]), 3),
        evenly_count=rng.choice([0, 0, rng.randint(1, 5)]),
        justify=rng.choice(JUSTIFY),
        adjust_to_end=round(rng.choice([0.0, rng.uniform(0.0, 2.0)]), 3),
        zmode=rng.choice(ZMODES), fix_slope=bool(rng.random() < 0.3))
    return Style("gen%d" % rng.randint(0, 9999), seed=rng.randint(0, 9999),
                 rules=rules, params=p)


def make(seed):
    """One whole scene from one integer.  Deterministic, and the ONLY entry."""
    rng = _rng(seed)
    native = (seed % NATIVE_LANE) == 0
    curve, storage, ids = _curve_geo(rng, native)
    kit_geo, has_corner, nvar = _kit_geo(rng, native)
    style = _style(rng, has_corner, nvar, native)
    nmark = 0 if native else _markers(rng, curve, ids)
    return {"seed": seed, "curve": curve, "kit": kit_geo, "style": style,
            "native_lane": native,
            "label": ("[%s] " % ("native" if native else "wide "))
                     + describe(seed, storage, ids, has_corner, nvar, nmark,
                                style)}


def describe(seed, storage, ids, has_corner, nvar, nmark, style):
    """The one line a failure prints, so the repro needs no other artifact."""
    return ("seed=%d id_storage=%s ids=%r corner_role=%s variants=%d "
            "markers=%d fill=%s corner_mode=%s zmode=%r justify=%s"
            % (seed, storage, ids, has_corner, nvar, nmark, style.params.fill,
               style.params.corner_mode, style.params.zmode,
               style.params.justify))


def seeds(count, start=0):
    """The seeds a run uses: every PIN first, then `count` fresh ones."""
    return list(PINS) + [start + i for i in range(count)]
