"""polyChain scene cases - every scene the checks run against.

Built from scratch in a fresh hython session and never saved, for exactly the
reason `tests/citygen/cases.py` gives: a live, mutating .hip was a real source
of false findings (stale cooks, leftover scratch nodes, display flags one pass
changed and the next read).

There is no .hip and no node network here at all. 4.4 is a geometry-level
adapter, so a case is three `hou.Geometry` objects and a `Style` - which also
means the checks measure the builder and nothing else.

⚠️ EVERY MODULE IN THE STARTER KIT RUNS EXACTLY FROM LOCAL x = 0 TO
`pc_size.x`, WITH NO OVERHANG. That is deliberate and the checks depend on it:
it makes the piece's start and end FACES its fit planes, so "did this piece
land where the plan said" is a distance between two points of real geometry
rather than a restatement of the plan. A kit with overhang is legal (D20) and
would need the checks to carry the overhang; the starter kit does not, so they
do not.
"""

import math
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def setup_env():
    """hython has not loaded the polyfactory package, so scripts/python is not
    on sys.path. Same fix as tests/citygen/cases.py, minus the VEX include
    path - nothing here cooks VEX."""
    pkg = os.path.join(REPO, "polyfactory").replace("\\", "/")
    pyp = "%s/scripts/python" % pkg
    if pyp not in sys.path:
        sys.path.insert(0, pyp)


setup_env()

import hou                                                       # noqa: E402
from polyfactory.polychain import Params, Rule, Style             # noqa: E402
from polyfactory.polychain import kit as K                        # noqa: E402
from polyfactory.polychain import place as P                      # noqa: E402
from polyfactory.polychain import style as S                      # noqa: E402


# --- input construction -----------------------------------------------------

def polyline(geo, pts, closed=False, curve_id=None):
    poly = geo.createPolygon(closed)
    for p in pts:
        pt = geo.createPoint()
        pt.setPosition(p)
        poly.addVertex(pt)
    if curve_id is not None:
        if geo.findPrimAttrib("pc_curve_id") is None:
            geo.addAttrib(hou.attribType.Prim, "pc_curve_id", "")
        poly.setAttribValue("pc_curve_id", str(curve_id))
    return poly


def marker(geo, position, curve_id, marker_id, dist=None, u=None):
    """One 3.1 marker point, authored through `pc_dist` OR `pc_u`.

    ⚠️ AUTHORING ONLY ONE OF THE TWO IS THE POINT. A Houdini attribute is
    geometry-wide, so as soon as one marker in the cloud carries `pc_dist`
    every other marker carries it too, with the default 0.0 - which is exactly
    how a u-authored gate ended up built at the start of its curve. Mixing the
    two conventions in one cloud is what `N_marker_mixed` is for.
    """
    for name, default in (("pc_marker", 0), ("pc_marker_id", 0)):
        if geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, default)
    if geo.findPointAttrib("pc_curve") is None:
        geo.addAttrib(hou.attribType.Point, "pc_curve", "")
    for name, value in (("pc_dist", dist), ("pc_u", u)):
        if value is not None and geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, 0.0)
    pt = geo.createPoint()
    pt.setPosition(position)
    pt.setAttribValue("pc_marker", 1)
    pt.setAttribValue("pc_curve", str(curve_id))
    pt.setAttribValue("pc_marker_id", int(marker_id))
    if dist is not None:
        pt.setAttribValue("pc_dist", float(dist))
    if u is not None:
        pt.setAttribValue("pc_u", float(u))
    return pt


GATE_LENGTH = 1.60                  # the starter kit gate's pc_size.x

# --- the hill: an arc on a constant grade -----------------------------------
# Sampled at 0.5 m on R = 30 m, so each vertex turns 0.95 degrees - far below
# `corner_angle_deg`, so it is ONE section, and fine enough that a 2 m panel's
# own 0.25 m stations resolve it inside `bend_tol` (measured: no warning).
HILL_RADIUS = 30.0
HILL_SPACING = 0.5
HILL_SWEEP = math.pi / 3.0          # 60 degrees -> 31.4 m of horizontal arc
HILL_GRADE = 0.25                   # 25 %, 14.04 degrees of bank in adaptive.
                                    # ⚠️ It was 5 % and that was too gentle to
                                    # be diagnostic: a 2.86 degree bank sits
                                    # close enough to zero that a half-wired
                                    # Z-mode would still look plausible.


def arc_points(radius, spacing=1.0, length=20.0):
    """A circular arc in XZ, RESAMPLED at `spacing` - one interior vertex per
    metre, which is what a street polyline looks like (D75).

    The sagitta a span of `c` metres leaves is c*c/(8*radius), so a 2 m panel
    on these four radii deviates 4.2e-05, 2.5e-04, 6.2e-03 and 5.0e-02 m -
    three of them under the 0.01 m `bend_tol` and the last one five times over
    it. That ladder is the whole point: the budget has to keep the first three
    packed AND still bend the fourth.
    """
    n = int(round(length / spacing))
    pts = []
    for i in range(n + 1):
        a = (spacing * i) / radius
        pts.append((radius * math.sin(a), 0.0, radius * (1.0 - math.cos(a))))
    return pts


def hill_points():
    n = int(round(HILL_RADIUS * HILL_SWEEP / HILL_SPACING))
    pts = []
    for i in range(n + 1):
        a = HILL_SWEEP * i / float(n)
        s = HILL_RADIUS * a
        pts.append((HILL_RADIUS * math.sin(a), s * HILL_GRADE,
                    HILL_RADIUS * (1.0 - math.cos(a))))
    return pts


# --- 4.5's surfaces ---------------------------------------------------------
# Every one of them is ANALYTIC, so the expected drape is trigonometry on the
# input rather than a number read off a build: a ramp of grade g puts the
# fence at y = g*x, a tent's crease is at a known x, and a hole is a hole.

CONFORM_GRADE = 0.25            # 25 %, 14.036 degrees - PC-G2's own grade
RIDGE_AMP = 0.8
RIDGE_WAVE = 8.0                # metres per full wave: a 2 m panel cannot
                                # cross it as a chord, which is the point


def surface(fn, x0=-4.0, x1=24.0, z0=-6.0, z1=6.0, nx=28, nz=12,
            flip=False, holes=()):
    """A quad grid over [x0,x1] x [z0,z1] with y = fn(x, z).

    `flip` reverses the winding (D52's back-facing case) and `holes` drops
    (i, j) cells (D53's hole). Hand-built for the same reason `kit.box_mesh`
    is: the Grid SOP's own output is not the thing under test here.
    """
    geo = hou.Geometry()
    pts = {}
    for i in range(nx + 1):
        for j in range(nz + 1):
            x = x0 + (x1 - x0) * i / float(nx)
            z = z0 + (z1 - z0) * j / float(nz)
            pt = geo.createPoint()
            pt.setPosition((x, fn(x, z), z))
            pts[(i, j)] = pt
    for i in range(nx):
        for j in range(nz):
            if (i, j) in holes:
                continue
            quad = [pts[(i, j)], pts[(i, j + 1)], pts[(i + 1, j + 1)],
                    pts[(i + 1, j)]]
            if flip:
                quad = list(reversed(quad))
            poly = geo.createPolygon()
            for pt in quad:
                poly.addVertex(pt)
    return geo


def ramp_x(x, _z):
    return CONFORM_GRADE * x


BUMP_CENTRE = 0.75              # between the five fixed probes the unpack
BUMP_WIDTH = 0.3                # gate used to take, and ON a panel station
BUMP_HEIGHT = 0.5


def bump(x, _z):
    """A ridge NARROWER THAN A QUARTER OF A PIECE, on flat ground at y = -1.

    D71's case: the feature that a fixed five-sample gate cannot see and the
    module's own 0.25 m stations resolve perfectly.
    """
    d = abs(x - BUMP_CENTRE)
    if d >= BUMP_WIDTH / 2.0:
        return -1.0
    return -1.0 + BUMP_HEIGHT * (1.0 - d / (BUMP_WIDTH / 2.0))


def camber_z(_x, z):
    """Cross-fall: the surface tilts ACROSS the run, which is what camber is.
    A run along +X on this reads a roll of atan(0.25) = 14.036 degrees."""
    return CONFORM_GRADE * z


def ridge(x, _z):
    return RIDGE_AMP * math.sin(2.0 * math.pi * x / RIDGE_WAVE)


TENT_PEAK = 10.2


def tent(x, _z):
    """TWO FACETS AND A CREASE - the surface coarser than the pieces (D56).

    Built with `nx = 2`, so this is literally two quads 14 m across: one 2 m
    panel spans a fourteenth of a facet, and the crease is the only feature.

    ⚠️ THE PEAK IS AT 10.2 m AND NOT AT 10 m, and that is the whole case. At
    10 m the crease lands on a PIECE BOUNDARY (ten 2 m panels on a 20 m run)
    and at 11 m on a panel's own station - and in both of those the drape is
    resolved exactly and nothing warns, which is the right answer and no test
    at all. 10.2 m puts it between two 0.25 m stations, which is D25's
    condition measured against the conformed path: the piece is built, it cuts
    0.014 m off the ridge, and it says `pc_warn_bend_resolution`.
    """
    return 0.3 * x if x <= TENT_PEAK else (
        3.06 + (0.3 * (2.0 * TENT_PEAK - 24.4) - 3.06)
        * (x - TENT_PEAK) / (24.4 - TENT_PEAK))


# --- kits -------------------------------------------------------------------

def coarse_kit():
    """A bendable rail with TWO stations - it cannot follow a curve, and 4.4
    forbids auto-subdividing it. The `pc_warn_bend_resolution` detector has to
    fire on this or it is vacuous."""
    geo = hou.Geometry()
    rail = hou.Geometry()
    K.box_mesh(rail, 0.0, 3.0, 0.8, 1.0, -0.03, 0.03, 1)
    K.add_module(geo, "rail2", rail, size=(3.0, 0.2, 0.06),
                 deform=1, zmode="adaptive", roles="default")
    K.write_manifest(geo, "pf_coarse", 1, sources=("cases.coarse_kit",),
                     human_scale_reference=1.8)
    return geo


def tall_kit(height=1.2, depth=0.06, length=2.0, zmode="adaptive"):
    """A TALL bendable rail - the module the spine-only budget could not see.

    D87: `span_deviation` measured the spine, so a module whose points sit far
    off it spent a budget nobody was counting. Height is the whole point here;
    the starter kit's panel is 0.05 m deep and rides `vertical`, which is
    exactly the shape that made the spine measure look exact for a cycle.
    """
    geo = hou.Geometry()
    rail = hou.Geometry()
    K.box_mesh(rail, 0.0, length, 0.0, height, -0.5 * depth, 0.5 * depth, 8)
    K.add_module(geo, "rail", rail, size=(length, height, depth),
                 deform=1, zmode=zmode, roles="default")
    K.write_manifest(geo, "pf_tall", 1, sources=("cases.tall_kit",),
                     human_scale_reference=1.8)
    return geo


def elevation_arc_points(radius=55.0, spacing=1.0, length=30.0):
    """An arc that climbs - curvature in ELEVATION, dead straight in plan.

    `arc_points` turns in plan, where an `adaptive` frame's `across` barely
    moves; this one turns in the vertical plane, where `up` swings by the full
    turn and a tall piece's top corner pays for it.
    """
    n = int(round(length / spacing))
    return [(radius * math.sin(spacing * i / radius),
             radius * (1.0 - math.cos(spacing * i / radius)), 0.0)
            for i in range(n + 1)]


def rail_style(zmode=""):
    return Style("tall", 1, 3, rules=[Rule("default", "first", ["rail"])],
                 params=Params(fill="adaptive", zmode=zmode))


def rigid_kit():
    """One long RIGID beam. Rigid pieces are the only ones allowed to stay
    packed across a bend, which makes them the only ones that can test what
    the packed transform is built FROM - see `M_rigid_over_bend`."""
    geo = hou.Geometry()
    beam = hou.Geometry()
    K.box_mesh(beam, 0.0, 2.5, 0.9, 1.1, -0.05, 0.05, 1)
    K.add_module(geo, "beam", beam, size=(2.5, 0.2, 0.1),
                 deform=0, zmode="adaptive", roles="default")
    K.write_manifest(geo, "pf_rigid", 1, sources=("cases.rigid_kit",),
                     human_scale_reference=1.8)
    return geo


def broken_kit():
    """Deliberately malformed - one distinct fault per module, so the
    validator's count is a fingerprint and not a lump sum. It must report all
    of them, raise none of them, and `build` must still produce geometry
    (warn-never-block).

    Seven faults: three mandatory manifest fields missing, an unknown zmode, a
    module with no name, a duplicate name, a zero pc_size, an out-of-range
    pc_deform and a negative pc_weight. That is 9 warnings; the module with no
    name is not inspected further, which is why it carries no second fault.
    """
    geo = hou.Geometry()
    slab = hou.Geometry()
    K.box_mesh(slab, 0.0, 1.0, 0.0, 0.5, -0.05, 0.05, 1)
    K.add_module(geo, "slab", slab, size=(1.0, 0.5, 0.1), deform=0,
                 zmode="sideways", roles="default")           # unknown zmode
    K.add_module(geo, "", slab, size=(1.0, 0.5, 0.1))          # no pc_name
    K.add_module(geo, "slab", slab, size=(1.0, 0.5, 0.1))      # duplicate
    K.add_module(geo, "sizeless", slab, size=(0.0, 0.0, 0.0))  # bbox fallback
    K.add_module(geo, "wild", slab, size=(1.0, 0.5, 0.1), deform=7,
                 weight=-1.0)                                  # junk numbers
    K._ensure(geo, hou.attribType.Global, K.KIT_DETAIL, {})
    geo.setGlobalAttribValue(K.KIT_DETAIL, {"kitId": "pf_broken"})
    return geo


# --- styles -----------------------------------------------------------------

def fence_style(fill="adaptive", zmode="", seed=7, fix_slope=False,
                corner_angle_deg=30.0):
    return Style("fence", 1, seed, rules=[
        Rule("default", "sequence", ["post", "panel"]),
        Rule("start", "first", ["post"]),
        Rule("end", "first", ["post"]),
        Rule("corner", "first", ["corner_post"]),
    ], params=Params(fill=fill, zmode=zmode, fix_slope=fix_slope,
                     corner_angle_deg=corner_angle_deg))


def panel_style(zmode="", seed=5, fix_slope=False):
    return Style("rail", 1, seed, rules=[Rule("default", "first", ["panel"])],
                 params=Params(fill="adaptive", zmode=zmode,
                               fix_slope=fix_slope))


# --- 4.3's own inputs -------------------------------------------------------
# One L, one rectangle and one zigzag, shared by every corner case so the only
# thing that changes between them is the corner PARAMETERS.

L_SHAPE = [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 0.0, 12.0)]
RECT = [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 0.0, 8.0), (0.0, 0.0, 8.0)]
# LEFT, then RIGHT. The first version of this turned left twice - both
# vertices scored `Bevel.side = +1` - so the case called itself "reflex" and
# tested nothing that the L-shape did not. `corner_turns` records the two
# signs now, so a reflex case that contains no reflex corner cannot pass as
# coverage again.
ZIGZAG = [(0.0, 0.0, 0.0), (8.0, 0.0, 0.0), (12.0, 0.0, 4.0),
          (20.0, 0.0, 4.0)]

# A 90 degree corner post of half-width 0.08 m reaches e = 0.08*tan(45) past
# the vertex, so its outside face still measures its full 0.16 m.
CORNER_POST_LENGTH = 0.16
CORNER_BLOCK_LENGTH = 1.20


def corner_style(mode="miter", offset=0.0, fillet=0.0, fill="adaptive",
                 displacement="reset"):
    """The PC-G1 fence, with 4.3's parms exposed. Same kit, same rules."""
    return Style("corner", 1, 9, rules=[
        Rule("default", "first", ["panel"]),
        Rule("start", "first", ["post"]),
        Rule("end", "first", ["post"]),
        Rule("corner", "first", ["corner_post"]),
    ], params=Params(fill=fill, corner_mode=mode, corner_offset_pct=offset,
                     fillet_radius=fillet, corner_displacement=displacement))


def compose_kit():
    """The starter fence plus a second, LONGER corner module.

    Compose symmetry is only visible when the composed modules differ in
    length: with three identical blocks an even count and an odd count reach
    the same distance down one leg by accident. `corner_block` is 1.20 m
    against `corner_post`'s 0.16 m, so the odd/even difference is 1.20 m and
    not a rounding artefact.
    """
    geo = K.starter_kit()
    block = hou.Geometry()
    K.box_mesh(block, 0.0, CORNER_BLOCK_LENGTH, 0.0, 1.30, -0.08, 0.08, 1)
    K.add_module(geo, "corner_block", block,
                 size=(CORNER_BLOCK_LENGTH, 1.30, 0.16),
                 deform=0, zmode="stepped", roles="corner")
    K.write_manifest(geo, "pf_fence_compose", 1,
                     sources=("cases.compose_kit",),
                     human_scale_reference=1.8)
    return geo


# --- the cases --------------------------------------------------------------

def _case(curve_geo, kit_geo, style, surface_geo=None, overrides=None):
    out, report = P.build(curve_geo, kit_geo, style, surface_geo=surface_geo,
                          overrides=overrides)
    return {"curve": curve_geo, "kit": kit_geo, "style": style,
            "out": out, "report": report, "surface": surface_geo,
            "overrides": overrides}


def build_all():
    kit_geo = K.starter_kit()
    built = {}

    # A - the simplest thing that can be measured: a flat straight run.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="A")
    built["A_straight"] = _case(g, kit_geo, fence_style())

    # B - PC-G1's closed rectangle. D18 says a closed spline gets NO caps and
    # a corner earns no start/end post, so this is where that is measured.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 8), (0, 0, 8)], closed=True,
             curve_id="B")
    built["B_rect_closed"] = _case(g, kit_geo, fence_style())

    # C - tile mode with a sliceable module: the remainder is cut and capped.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (7, 0, 0)], curve_id="C")
    built["C_tile_slice"] = _case(g, kit_geo, Style(
        "tiled", 1, 3, rules=[Rule("default", "first", ["gate"])],
        params=Params(fill="tile")))

    # D - a gate on a marker. PC-G1's acceptance is "gate exactly at its
    # marker", so the marker distance is a recorded number.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="D")
    marker(g, (10, 0, 0), "D", 7, 10.0)
    built["D_marker_gate"] = _case(g, kit_geo, Style(
        "gated", 1, 2, rules=[Rule("default", "first", ["panel"]),
                              Rule("marker:7", "first", ["gate"])],
        params=Params(fill="adaptive")))

    # E, F, G - PC-G2's hill in each Z-mode, same input, same style, one parm
    # apart. Read as a triple: the three must NOT agree.
    for name, zmode in (("E_hill_adaptive", "adaptive"),
                        ("F_hill_vertical", "vertical"),
                        ("G_hill_stepped", "stepped")):
        g = hou.Geometry()
        polyline(g, hill_points(), curve_id="H")
        built[name] = _case(g, kit_geo, panel_style(zmode=zmode))

    # DA/DB/DC/DD/DE - 4.4's FLATTEN-UNDER and its two hybrid BANDS (D98, D99),
    # every one of them read against G_hill_stepped, which is the same hill,
    # the same style and the same kit with the new parms off.
    #
    #  * DA is the flatten alone: `stepped_float_m` is the number it moves and
    #    `stepped_riser_m` is the number it must NOT, because the step between
    #    two flat pieces IS stepped mode and removing it would remove the mode.
    #  * DB is the SAME curve drawn BACKWARDS. Taking the datum from the
    #    piece's start makes a fence that depends on which way the artist drew
    #    the spline; taking it from the low point cannot, and the pair is the
    #    only way to see that.
    #  * DD is iToo's picket hybrid - a `vertical` panel whose TOP band is
    #    held level while the rest follows the ground.
    #  * DE is the other one - a `stepped` panel whose BOTTOM band follows the
    #    ground while the rest stays flat. The module is `panel` rather than
    #    `post` because a rigid module cannot express a band at all (D27), and
    #    that is the honest limit rather than a hidden one.
    #  * DC is the BEFORE, and it is the reversed curve rather than the
    #    forward one because the defect only shows going DOWNHILL: taking the
    #    datum from the piece's start buries the run on a climb (where
    #    G_hill_stepped reads it) and floats it on a descent. DC is the
    #    number DA and DB take to zero.
    for name, pts, kw in (
            ("DA_hill_flatten", hill_points(),
             dict(flatten_stepped=True)),
            ("DB_hill_flatten_rev", list(reversed(hill_points())),
             dict(flatten_stepped=True)),
            ("DC_hill_rev_plain", list(reversed(hill_points())),
             dict(flatten_stepped=False))):
        g = hou.Geometry()
        polyline(g, pts, curve_id="H")
        built[name] = _case(g, kit_geo, Style(
            "flat_under", 1, 4, rules=[Rule("default", "first", ["post"])],
            params=Params(fill="adaptive", zmode="stepped", **kw)))
    for name, zmode, band in (("DD_band_flat_top", "vertical", "top"),
                              ("DE_band_stepped_foot", "stepped", "bottom")):
        g = hou.Geometry()
        polyline(g, hill_points(), curve_id="H")
        built[name] = _case(g, kit_geo, Style(
            "banded", 1, 4, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode=zmode, flat_band=band,
                          flat_band_m=0.25)))

    # DH/DI - D105. DD above is the band with the flatten OFF, and its level
    # top rail takes its one elevation from the piece's START: `band_datum_m`
    # reads 0.490874 m on it, the drop across a piece, so the SAME curve drawn
    # backwards puts every rail somewhere else. These two are that pair with
    # the flatten ON - the forward hill and the reversed one - and the datum
    # is an extremum over the piece's own span, so the number is 0 on both.
    # A single case cannot see this: 0.490874 m passes any check that only
    # asks whether the band is level, which is what `band_hybrid_m` asks.
    for name, pts in (("DH_band_flat_datum", hill_points()),
                      ("DI_band_flat_datum_rev", list(reversed(hill_points())))):
        g = hou.Geometry()
        polyline(g, pts, curve_id="H")
        built[name] = _case(g, kit_geo, Style(
            "banded", 1, 4, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="vertical", flat_band="top",
                          flat_band_m=0.25, flatten_stepped=True)))

    # DJ - D98's datum on a REPLACED piece. DA proves the flatten plants a
    # stepped piece; this proves the D58 hero path reads the same datum,
    # because it did not: hero geometry lands packed at "the transform this
    # element would have had", and that transform was built without the datum,
    # so a replaced post floated 0.490874 m above its planted neighbours (one
    # full piece-drop) with no warning and nothing in the suite combining the
    # two. Reversed, because that is the direction the float shows in.
    # the hero keeps the post's own 0.12 m footprint and is 1.5 m tall
    # instead of 1.2 m, so it is unmistakably NOT the kit module while
    # `module_fidelity_m` and `max_gap_m` still measure what they measure.
    hero_post = hou.Geometry()
    K.box_mesh(hero_post, 0.0, 0.12, 0.0, 1.5, -0.06, 0.06, 1)
    ov4 = hou.Geometry()
    P.write_override(ov4, elem_id="H|0|default|135|flat_under", hero=hero_post)
    g = hou.Geometry()
    polyline(g, list(reversed(hill_points())), curve_id="H")
    built["DJ_flatten_hero"] = _case(g, kit_geo, Style(
        "flat_under", 1, 4, rules=[Rule("default", "first", ["post"])],
        params=Params(fill="adaptive", zmode="stepped",
                      flatten_stepped=True)), overrides=ov4)

    # DF/DG - D100's CAMBER OFF-SPINE BUDGET GAP, as a pair.
    #
    # The surface is `y = k*x*z` and the run is straight along +X at z = 0, so
    # ALONG THE SPINE it is dead flat: `Surface.deviates` reads zero, D87's
    # spine term reads zero, and nothing in the pre-D100 budget could see
    # anything at all. What DOES move is the cross-fall, and with it the
    # surface normal the camber rolls onto - atan(k*x) - which a packed piece
    # takes ONCE at its midpoint and a deformed one takes per station.
    #
    #  * DF is the worst case, k = 0.2: before D100 all 10 panels stayed
    #    packed at 0.2126 m of true deviation, 21x `bend_tol`.
    #  * DG is k = 0.005, deliberately INSIDE the budget (0.0055 m): it is
    #    the anti-vacuity half, because a budget that simply unpacked every
    #    cambered piece would pass DF and cost PC-G3 everything.
    for name, k in (("DF_camber_crossfall", 0.2),
                    ("DG_camber_gentle", 0.005)):
        g = hou.Geometry()
        polyline(g, [(0, 0, 0), (20.0, 0, 0)], curve_id="CB")
        built[name] = _case(g, kit_geo, Style(
            "crossfall", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="adaptive",
                          conform_tilt=True)),
            surface_geo=surface(lambda x, z, _k=k: _k * x * z,
                                x0=-2.0, x1=22.0, z0=-6.0, z1=6.0,
                                nx=48, nz=24))

    # DK - D104, and it is DF's own defect one level down. DF's cross-fall
    # grows MONOTONICALLY, so reading the camber at the span's two ends and
    # its kinks catches it. This one is a superelevation TRANSITION,
    # `y = 0.2 sin(pi x) z`: the roll is exactly ZERO at every 2 m piece
    # boundary AND at every midpoint, and it reaches +/-11.3 degrees at the
    # quarter-span in between. Measured before D104: 10 of 10 panels stayed
    # PACKED at 0.197164 m of true deviation, 19.7x `bend_tol` - the same
    # magnitude D100's own mutation test treats as the gate failing - and a
    # 1 m-resampled spline was defeated identically (the ripple's period puts
    # a zero-roll vertex on every kink), so a dense street polyline is not
    # automatically safe. `deform_gate_m`'s middle number is what keeps this
    # case honest: 10 pieces over budget, 0 of them packed.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20.0, 0, 0)], curve_id="CB")
    built["DK_camber_ripple"] = _case(g, kit_geo, Style(
        "crossfall", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", zmode="adaptive", conform_tilt=True)),
        surface_geo=surface(
            lambda x, z: 0.2 * math.sin(math.pi * x) * z,
            x0=-2.0, x1=22.0, z0=-6.0, z1=6.0, nx=240, nz=48))

    # H and I - slope fixing (D26), as a PAIR, because one of them alone
    # proves nothing.
    #
    # ⚠️ THE OBVIOUS SLOPE-FIXING CASE MEASURES NOTHING, AND THIS ONE WAS IT
    # BEFORE IT WAS MEASURED. Under `adaptive` fill every piece is rescaled to
    # fill whatever length it is given, so fitting on the horizontal arc and
    # fitting on the 3D arc produce THE SAME 16 pieces at the same horizontal
    # spacing - the two differ only where a piece keeps its own length. So the
    # pair runs TILE, where whole pieces are unscaled: free gives 1.55 m of
    # horizontal reach per 1.6 m gate (the width measured along the path's
    # angle) and fixed gives 1.60 m (measured on the horizontal axis), which
    # is iToo's documented sentence turned into two numbers.
    tile_gate = Style("tiled_hill", 1, 8,
                      rules=[Rule("default", "first", ["gate"])],
                      params=Params(fill="tile"))
    tile_gate_fixed = Style("tiled_hill", 1, 8,
                            rules=[Rule("default", "first", ["gate"])],
                            params=Params(fill="tile", fix_slope=True))
    for name, style in (("H_tile_slope_free", tile_gate),
                        ("I_tile_slope_fixed", tile_gate_fixed)):
        g = hou.Geometry()
        polyline(g, hill_points(), curve_id="H")
        built[name] = _case(g, kit_geo, style)

    # L - a STRAIGHT ramp. The only case where a sloped span holds no interior
    # vertex, which is the one shape that separates `vertical` from `stepped`
    # for a bendable module: the piece has to shear to keep its verticals
    # plumb while its ends sit on the slope. Every other sloped case here
    # bends anyway, so without this the vertical branch of `_needs_deform`
    # is never the thing under test.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12.0, 3.0, 0)], curve_id="L")
    built["L_ramp_vertical"] = _case(g, kit_geo, panel_style(zmode="vertical"))

    # M - a RIGID 2.5 m beam straddling a 33.7 degree vertex, with the corner
    # threshold raised to 45 so the vertex does not break the section.
    #
    # ⚠️ THIS CASE EXISTS BECAUSE A MUTATION SURVIVED WITHOUT IT. Building a
    # packed piece from the START TANGENT instead of the chord (D21 deleted)
    # changed nothing anywhere else, because everywhere else a packed piece
    # sits on a straight span where the two are the same vector. A rigid
    # module is the ONLY thing that stays packed across a bend, so it is the
    # only input that can tell the chord from the tangent.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (3.0, 0, 0), (6.0, 0, 2.0)], curve_id="M")
    built["M_rigid_over_bend"] = _case(g, rigid_kit(), Style(
        "rigid", 1, 6, rules=[Rule("default", "first", ["beam"])],
        params=Params(fill="adaptive", corner_angle_deg=45.0)))

    # J - the bend detector's non-vacuity case: a two-station bendable module
    # dragged across a 19.6 degree vertex. It MUST warn and MUST still build.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (4.5, 0, 0), (9.0, 0, 1.6)], curve_id="J")
    built["J_coarse_bend"] = _case(g, coarse_kit(), Style(
        "coarse", 1, 1, rules=[Rule("default", "first", ["rail2"])],
        params=Params(fill="adaptive")))

    # K - a malformed kit. The validator counts the faults; the build still
    # produces geometry, because warn-never-block is a suite constraint.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (6, 0, 0)], curve_id="K")
    built["K_broken_kit"] = _case(g, broken_kit(), Style(
        "broken", 1, 4, rules=[Rule("default", "first", ["slab"]),
                               Rule("start", "first", ["nonexistent_module"])],
        params=Params(fill="adaptive")))

    # ---- the review cases. Every one of these is a defect that was measured
    # on a build before it was written down here (tests/README.md: a
    # measurement written during a review belongs in checks.py afterwards).

    # N - one marker cloud, two authoring conventions. Marker 7 is authored in
    # metres and marker 8 in u, and because a Houdini attribute is
    # geometry-wide marker 8 also carries pc_dist = 0.0. Reading dist first
    # without asking whether it was AUTHORED built the second gate at s = 0.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="N")
    marker(g, (5, 0, 0), "N", 7, dist=5.0)
    marker(g, (15, 0, 0), "N", 8, u=0.75)
    built["N_marker_mixed"] = _case(g, kit_geo, Style(
        "mixed", 1, 2, rules=[Rule("default", "first", ["panel"]),
                              Rule("marker:7", "first", ["gate"]),
                              Rule("marker:8", "first", ["gate"])],
        params=Params(fill="adaptive")))

    # O - NO KIT AT ALL, which is what an unconnected second input hands the
    # SOP. Warn-never-block means a stand-in fence and a warning, not an
    # AttributeError halfway through the cook.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (8, 0, 0)], curve_id="O")
    built["O_no_kit"] = _case(g, None, fence_style())

    # P - an OVERHANGING CREST: the path turns back on itself in the vertical
    # plane, so the tangent's horizontal direction reverses mid-piece. That is
    # where a frame derived per point from cross(tangent, up) flips 180
    # degrees and the panel twists through itself. corner_angle_deg = 60 keeps
    # it one section, so one panel really does straddle the reversal.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (2, 3, 0), (1, 6, 0)], curve_id="P")
    built["P_crest_bend"] = _case(g, kit_geo, Style(
        "crest", 1, 1, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", zmode="adaptive",
                      corner_angle_deg=60.0)))

    # Q - a PURELY VERTICAL run in a yaw-only z-mode. The flattened chord has
    # no length, so the scale used to collapse to 1e-9 and the posts became 25
    # invisible prims with no warning. D32: they keep their 3D length and say
    # `pc_warn_degenerate_frame`.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (0, 3, 0)], curve_id="Q")
    built["Q_vertical_stepped"] = _case(g, kit_geo, Style(
        "vert", 1, 1, rules=[Rule("default", "first", ["post"])],
        params=Params(fill="adaptive")))

    # R - a SUPPRESSED HAIRPIN under a rigid module: the beam is asked to
    # cover 4 m of a there-and-back polyline whose two ends are 0.10 m apart.
    # Cutting the corner is what rigid means, but a 25x collapse is a
    # measurable degeneration and warn-never-block says it must be visible.
    g = hou.Geometry()
    poly = polyline(g, [(0, 0, 0), (2, 0, 0), (0, 0, 0.1)], curve_id="R")
    g.addAttrib(hou.attribType.Point, "pc_corner", 0)
    poly.points()[1].setAttribValue("pc_corner", -1)          # -1 = suppress
    built["R_hairpin"] = _case(g, rigid_kit(), Style(
        "hair", 1, 1, rules=[Rule("default", "first", ["beam"])],
        params=Params(fill="scale", corner_angle_deg=170.0,
                      min_included_angle_deg=1.0)))

    # S - a gate marked at 19.7 m of a 20.006 m curve, so the 1.6 m module
    # legitimately OVERHANGS the end (D20 allows exactly that). The sampler
    # used to clamp, and the last 0.49 m of the gate was crushed into the end
    # plane - measured as two distinct stations landing on one point.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20.006, 0, 0)], curve_id="S")
    marker(g, (19.7, 0, 0), "S", 7, dist=19.7)
    built["S_overhang_gate"] = _case(g, kit_geo, Style(
        "overhang", 1, 2, rules=[Rule("default", "first", ["panel"]),
                                 Rule("marker:7", "first", ["gate"])],
        params=Params(fill="adaptive")))

    # ---- 4.3 CORNERS. PC-G1's own figure is the closed rectangle, so it is
    # here twice - once per corner mode - and the L-shape is here three times,
    # once per displacement policy. Every corner case is measured, never
    # looked at: the numbers are `corner_*` in checks.py.

    # T - the L-shape in BEND mode. D36: the elbow does NOT break the run, so
    # this is ONE section of 24 m and a panel wraps the 90 degree vertex. The
    # corner rule in `fence_style` is deliberately present and deliberately
    # unused (D37) - that is what bend means.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="T")
    built["T_lshape_bend"] = _case(g, kit_geo, corner_style("bend"))

    # U - the same L in MITER mode with a corner post. The post is duplicated
    # both sides of the vertex and each copy is sliced on the bisector, so
    # `corner_outside_m` must read the post's own 0.16 m and `corner_seam_m`
    # must read 0.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="U")
    built["U_lshape_miter"] = _case(g, kit_geo, corner_style("miter"))

    # V - PC-G1's closed rectangle, mitered. FOUR corners, and the fourth is
    # the one RailClone documents it cannot offset: the wrap corner where the
    # last section rejoins the first (D45). It is measured with the other
    # three and nothing about it is special-cased.
    g = hou.Geometry()
    polyline(g, RECT, closed=True, curve_id="V")
    built["V_rect_miter"] = _case(g, kit_geo, corner_style("miter"))

    # W, X - the corner offset, +25 % and -25 % of the corner module's length.
    # Positive parts the two cut planes and leaves a gap of
    # 2*o*cos(turn/2); negative crosses them over and cuts each piece deeper
    # into the corner. Both are read off the built cut faces.
    for name, pct in (("W_corner_offset_pos", 25.0),
                      ("X_corner_offset_neg", -25.0)):
        g = hou.Geometry()
        polyline(g, L_SHAPE, curve_id=name[0])
        built[name] = _case(g, kit_geo, corner_style("miter", offset=pct))

    # Y, Z - COMPOSE SYMMETRY, the odd/even rule. Y wires three corner modules
    # and Z wires two, off the same kit, so the only difference between the
    # two numbers is the count. Odd -> the assembly reaches equally down both
    # legs; even -> one leg carries one module more.
    for name, mods in (("Y_compose_odd", ["corner_post", "corner_block",
                                          "corner_post"]),
                       ("Z_compose_even", ["corner_post", "corner_block"])):
        g = hou.Geometry()
        polyline(g, L_SHAPE, curve_id=name[0])
        built[name] = _case(g, compose_kit(), Style(
            "compose", 1, 3,
            rules=[Rule("default", "first", ["panel"]),
                   Rule("corner", "sequence", mods)],
            params=Params(fill="adaptive", corner_mode="miter")))

    # AA - a REFLEX corner. The Z-bend turns left then right, so one vertex
    # has the outside face on the opposite side from the other. Nothing in
    # 4.3 special-cases it - `Bevel.side` is a sign - and this case is what
    # proves that claim rather than asserting it.
    g = hou.Geometry()
    polyline(g, ZIGZAG, curve_id="A")
    built["AA_reflex_miter"] = _case(g, kit_geo, corner_style("miter"))

    # AB - the FILLET. The path is rounded before anything is fitted, so the
    # section lengths are recomputed off the real arc (4.3 item E) and the
    # pieces follow it. `corner_clearance_m` is the acceptance: at a 90
    # degree corner filleted by 1.5 m nothing may come closer to the original
    # sharp vertex than 1.5*(1/cos45 - 1) = 0.6213 m.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="B")
    built["AB_fillet"] = _case(g, kit_geo, corner_style("bend", fillet=1.5))

    # AC - a DEGENERATE corner: a 170 degree turn leaves an included angle of
    # 10 degrees, under the 15 degree threshold, so 4.3 falls back to bend and
    # says pc_warn_corner_degenerate. It must still build a closed chain -
    # warn, never fail, always build something.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (6, 0, 0), (0.5, 0, 1.05)], curve_id="C")
    built["AC_degenerate_corner"] = _case(g, kit_geo,
                                          corner_style("miter"))

    # AD - LEGS SHORTER THAN THE CORNER ASSEMBLY. Three composed 1.2 m corner
    # blocks on a 1.5 m leg cannot fit, so D44 squeezes them onto the section
    # and stamps pc_warn_overflow. Nothing is dropped and nothing raises.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (1.5, 0, 0), (1.5, 0, 1.5)], curve_id="D")
    built["AD_short_legs"] = _case(g, compose_kit(), Style(
        "short", 1, 3,
        rules=[Rule("default", "first", ["panel"]),
               Rule("corner", "sequence", ["corner_block", "corner_block",
                                           "corner_block"])],
        params=Params(fill="adaptive", corner_mode="miter")))

    # AE, AF, AG - the DISPLACEMENT POLICY, on a style with NO corner rule so
    # the default run is what meets the bisector. Read as a TRIPLE: the three
    # must not agree, and how far each pushes its last piece past the vertex
    # is the whole of item D.
    for name, policy in (("AE_displace_reset", "reset"),
                         ("AF_displace_extend", "extend"),
                         ("AG_displace_symmetric", "symmetric")):
        g = hou.Geometry()
        polyline(g, L_SHAPE, curve_id=name[:2])
        built[name] = _case(g, kit_geo, Style(
            "displace", 1, 4, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", corner_mode="miter",
                          corner_displacement=policy)))

    # ---- the cycle-3 REVIEW cases. Every one of these was a measured defect
    # before it was a case: they are here so the measurement that found it
    # stays standing (tests/README.md's rule).

    # AH - A TURN SHARPER THAN THE CORNER MODULE. At 140 degrees the 0.16 m
    # post's own miter overhang is 0.2198 m, so `L_c - e` is NEGATIVE: the
    # reserve used to go negative, the negative trim ran the default fill
    # through the vertex, and `place` bent it around the kink into an
    # inside-out panel interpenetrating the other leg by 0.031 m - silently.
    # The reserve is clamped at 0 now, the run is cut on the plane, and
    # `corner_breach_m` is what asserts the pieces stay on their own sides.
    a = math.radians(140.0)
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0),
                 (12 + 12 * math.cos(a), 0, 12 * math.sin(a))], curve_id="AH")
    built["AH_sharp_turn"] = _case(g, kit_geo, corner_style("miter"))

    # AI - A LEG SHORTER THAN TWICE THE OVERHANG. All three turns of a 1.5 m
    # equilateral triangle are 120 degrees, so the reserve is 0.0215 m against
    # a 0.03 m panel half-thickness: the two legs' square panel ends crossed
    # inside the corner post's footprint, hidden from every outside view.
    _tri = 1.5
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (_tri, 0, 0),
                 (_tri * 0.5, 0, _tri * math.sqrt(3.0) / 2.0)],
             closed=True, curve_id="AI")
    built["AI_triangle"] = _case(g, kit_geo, corner_style("miter"))

    # AJ, AK - TWO CLOSED FIGURES THAT WERE ALWAYS CLEAN AND ALWAYS
    # MISMEASURED. `_frame_of` recovered a face's affine map from the first
    # y-varying point pair without requiring it to share local z, so on a
    # clipped corner post it folded `across` into `up`: `corner_abut_m`
    # reported a 0.160 m phantom gap on the reflex L and 0.129 m on the
    # pentagon, on corners whose own points prove they are shut.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (10, 0, 0), (10, 0, 6), (4, 0, 6),
                 (4, 0, 10), (0, 0, 10)], closed=True, curve_id="AJ")
    built["AJ_reflex_closed"] = _case(g, kit_geo, corner_style("miter"))

    _pent_r = 6.0 / (2.0 * math.sin(math.pi / 5.0))
    g = hou.Geometry()
    polyline(g, [(_pent_r * math.cos(2 * math.pi * i / 5.0), 0.0,
                  _pent_r * math.sin(2 * math.pi * i / 5.0))
                 for i in range(5)], closed=True, curve_id="AK")
    built["AK_pentagon"] = _case(g, kit_geo, corner_style("miter"))

    # AL, AM - NON-PLANAR CORNERS, which the starter kit meets with a
    # `stepped` corner post - i.e. a piece built PLUMB, on the horizontal
    # projection. A bevel taken from the 3D tangents cut it on a tilted plane:
    # the crest kink anchored its two copies 0.055 m apart in Y and mated
    # their faces to only 0.0548 m, and the graded corner sliced the 1.30 m
    # post obliquely and left a 0.345 m stump beside a full-height mate.
    # Neither warned. D48 flattens the bevel for yaw-only pieces.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (7.52, 2.74, 0), (15.04, 0, 0)], curve_id="AL")
    built["AL_crest_corner"] = _case(g, kit_geo, corner_style("miter"))

    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (8, 2, 0), (8, 4, 8)], curve_id="AM")
    built["AM_graded_corner"] = _case(g, kit_geo, corner_style("miter"))

    # AN - THE DISPLACEMENT POLICY UNDER `tile`, with a SLICEABLE default
    # module so tile really does slice. D40's first implementation extended
    # the FILL SPAN, so tile tiled INTO the extension: `symmetric` planted a
    # whole new sliced piece entirely past the vertex (the clip then
    # annihilated it to a 3 cm wedge with its own `pc_elem_id`) and `extend` a
    # 0.03 m sliver. The boundary piece is one anchored module now, so the
    # policy reads the same in every fill mode.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="AN")
    built["AN_tile_symmetric"] = _case(g, kit_geo, Style(
        "tilesym", 1, 4, rules=[Rule("default", "first", ["gate"])],
        params=Params(fill="tile", corner_mode="miter",
                      corner_displacement="symmetric")))

    # AO - THE CORNER OFFSET ON A STYLE WITH NO CORNER MODULE. It was
    # provably dead: `build_assembly` set `bevel.offset` only after the
    # empty-mods early return, so 0 %, 25 % and 50 % built byte-identical
    # geometry. It moves D40's boundary piece now, and AO differs from
    # AF_displace_extend by nothing but the parm.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="AO")
    built["AO_displace_offset"] = _case(g, kit_geo, Style(
        "dispoff", 1, 4, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", corner_mode="miter",
                      corner_displacement="extend", corner_offset_pct=-10.0)))

    # AP - A FIGURE NARROWER THAN ITS OWN FENCE: 12 m by 0.12 m, so both
    # 0.12 m sides are shorter than one corner post and D44 squeezes all four
    # corners. The squeeze used to scale about the VERTEX, which pulled the
    # squeezed copy's cut face back off the plane and left an e*(1-f) notch;
    # it scales about the PLANE CONTACT now, so what is left over is only the
    # part of the mating diagonal a shortened module cannot span.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 0.12), (0, 0, 0.12)],
             closed=True, curve_id="AP")
    built["AP_narrow_rect"] = _case(g, kit_geo, corner_style("miter"))

    # AQ - AN ASYMMETRICALLY SQUEEZED CORNER: a 12 m leg meets a 1.5 m one, so
    # D44 squeezes ONE side only. That is the case AD_short_legs cannot see,
    # because both of its legs squeeze equally - and it is where scaling about
    # the vertex left a 1.20 m cut face mating against a 0.776 m one.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 1.5)], curve_id="AQ")
    built["AQ_asym_squeeze"] = _case(g, compose_kit(), Style(
        "asym", 1, 3,
        rules=[Rule("default", "first", ["panel"]),
               Rule("corner", "sequence", ["corner_block", "corner_block",
                                           "corner_block"])],
        params=Params(fill="adaptive", corner_mode="miter")))

    # AR - THE OFFSET DIALLED PAST THE CORNER MODULE. At -100 % the whole post
    # sits past the vertex, so its reserve is negative: the run used to be
    # handed that negative as a trim and the corner opened a 23 cm hole with
    # an EMPTY warning list. Clamped and warned now.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="AR")
    built["AR_offset_past"] = _case(g, kit_geo,
                                    corner_style("miter", offset=-100.0))

    # ---- the cycle-4 cases.

    # AS - CYCLE 3v'S OWN FIGURE: PC-G1's 12 x 8 m rectangle in BEND mode with
    # a panel-only default, so twenty 2 m panels fit the 40 m ring EXACTLY and
    # ALL FOUR corners land on a piece boundary. That is the one shape where
    # no piece wraps a vertex and every corner is a butt joint - which is what
    # `corner_breach_m`'s bend branch and `corner_wedge_m2` were written for.
    # B_rect_closed cannot cover it: its post/panel sequence wraps three of
    # its four corners, so only the seam is ever a joint.
    g = hou.Geometry()
    polyline(g, RECT, closed=True, curve_id="AS")
    built["AS_rect_bend_butt"] = _case(g, kit_geo, corner_style("bend"))

    # ---- 4.5 SURFACE CONFORM (input 4). The spline is DEAD FLAT and dead
    # straight in every one of these, at y = 0 along +X, so everything
    # vertical in the result came from the surface and nothing came from the
    # curve - which is the only way to tell a conform from a hill.

    def conform_line(cid, x1=20.0):
        g = hou.Geometry()
        polyline(g, [(0, 0, 0), (x1, 0, 0)], curve_id=cid)
        return g

    # BA/BB/BC - the same ridge under the same run in the three Z-modes, read
    # as a TRIPLE exactly like E/F/G: 4.5 says adaptive and vertical DEFORM to
    # the surface and stepped SITS on it, so the three must not agree.
    for name, zmode, mod in (("BA_conform_adaptive", "adaptive", "panel"),
                             ("BB_conform_vertical", "vertical", "panel"),
                             ("BC_conform_stepped", "stepped", "post")):
        built[name] = _case(conform_line(name[:2]), kit_geo, Style(
            "conform", 1, 3, rules=[Rule("default", "first", [mod])],
            params=Params(fill="adaptive", zmode=zmode)),
            surface_geo=surface(ridge))

    # BD - CAMBER. The surface falls 25 % ACROSS the run, so a tilted piece
    # rolls by atan(0.25) = 14.036 degrees and an untilted one does not roll
    # at all. Both are built, from one surface and one style parm apart.
    for name, tilt in (("BD_camber_on", True), ("BD_camber_off", False)):
        built[name] = _case(conform_line(name[:2]), kit_geo, Style(
            "camber", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="adaptive",
                          conform_tilt=tilt)),
            surface_geo=surface(camber_z))

    # BE - A HOLE, AND AN EDGE. The surface stops at x = 12 and has a hole
    # punched at x ~ 5, so the run leaves the terrain twice: D53 keeps the
    # spline elevation there and says `pc_warn_conform_miss`, and NOTHING
    # raises. The pieces over solid ground must still be draped.
    built["BE_conform_holes"] = _case(
        conform_line("BE"), kit_geo, Style(
            "holed", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="vertical")),
        surface_geo=surface(ramp_x, x0=-2.0, x1=12.0, nx=14,
                            holes=set((7, j) for j in range(12))))

    # BF - A BACK-FACING SURFACE (D52). Identical ramp, wound the other way.
    # RailClone does not ask an artist to flip their terrain, and neither does
    # this: the drape must come out the same, which `conform_contact_m` and
    # `plumb_deg` measure and `geometry_digest` pins against BG.
    built["BF_conform_flipped"] = _case(
        conform_line("BF"), kit_geo, Style(
            "flipped", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="vertical")),
        surface_geo=surface(ramp_x, flip=True))
    built["BG_conform_facing"] = _case(
        conform_line("BF"), kit_geo, Style(
            "flipped", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="vertical")),
        surface_geo=surface(ramp_x))

    # BH - A SURFACE COARSER THAN THE PIECES, with a hard crease in the middle
    # (D56). Two facets over 20 m, so a 2 m panel straddles the ridge and its
    # own 0.25 m stations are what decide whether it follows: the piece ON the
    # crease says `pc_warn_bend_resolution` - the SAME detector D25 already
    # owns, measured against the conformed path - and every other piece is
    # clean.
    built["BH_conform_crease"] = _case(
        conform_line("BH"), kit_geo, Style(
            "crease", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="vertical")),
        surface_geo=surface(tent, x1=24.4, nx=2, nz=2))

    # BI - A CONFORMED CORNER. 4.3 anchors a corner assembly on the SPLINE's
    # own vertex, which is under the terrain here, so without the drop the
    # corner post is the one piece of a conformed fence still at y = 0.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 8)], curve_id="BI")
    built["BI_conform_corner"] = _case(g, kit_geo, corner_style("miter"),
                                       surface_geo=surface(ramp_x, z0=-2.0,
                                                           z1=12.0, nz=14))

    # ---- 4.6 FINALIZE: the override cascade, and the instancing floor.

    # CA - SWAP. The style says `panel` and never stops saying it; an override
    # point re-points every panel to `gate` WITHOUT the style being touched
    # (3.4's own requirement). The ids must be identical to CB's - that is
    # what "round-trip" means here, and D1 is why it is even possible: the
    # module is not part of the address, and `override_round_trip` cooks the
    # control itself rather than needing a twin case here.
    ov = hou.Geometry()
    P.write_override(ov, module="panel", to_module="gate")
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="CA")
    built["CA_swap_module"] = _case(g, kit_geo, panel_style(), overrides=ov)

    # CC - REPLACE. One element, keyed by its own `pc_elem_id`, becomes hero
    # geometry: a 2 m x 2 m x 0.4 m slab that no kit contains, so "did the
    # hero actually arrive" is a question the built bbox answers rather than
    # the attribute.
    hero = hou.Geometry()
    K.box_mesh(hero, 0.0, 2.0, 0.0, 2.0, -0.2, 0.2, 1)
    ov2 = hou.Geometry()
    P.write_override(ov2, elem_id="CC|0|default|3|rail", hero=hero)
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="CC")
    built["CC_replace_hero"] = _case(g, kit_geo, panel_style(), overrides=ov2)

    # CD - A REPLACE ON A DEFORMED PIECE. Hero geometry cannot follow a bend
    # (D58), so this is the case that must WARN rather than silently
    # straighten the run - the same figure as T_lshape_bend, with the piece
    # that wraps the elbow replaced.
    ov3 = hou.Geometry()
    P.write_override(ov3, elem_id="CD|0|default|5|corner", hero=hero)
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 11)], curve_id="CD")
    built["CD_replace_bent"] = _case(g, kit_geo, corner_style("bend"),
                                     overrides=ov3)

    # CE - THE INSTANCING FLOOR: a straight run of RIGID modules must be
    # 100 % packed. PC-G3's whole claim in one case, and the one number that
    # a builder which unpacked everything would fail while staying
    # geometrically perfect.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (25, 0, 0)], curve_id="CE")
    built["CE_all_packed"] = _case(g, rigid_kit(), Style(
        "rigid", 1, 6, rules=[Rule("default", "first", ["beam"])],
        params=Params(fill="adaptive")))

    # ---- cycle 5: every one of these is a review measurement turned into a
    # standing assertion (tests/README.md's rule). Each names the defect it
    # was written against, because a case whose reason is not written down is
    # a case the next cycle deletes.

    # CF - A RESAMPLED STRAIGHT LINE IS STILL A STRAIGHT LINE (D69). The same
    # 25 m run as CE, authored at 1 m spacing - which is the shape citygen
    # streets, this tool's first consumer, hands it. Every interior vertex is
    # collinear, so nothing bends and nothing may unpack: measured before the
    # fix, the identical line as two points built 1000/1000 packed and this
    # one built 0/1000 packed and 1000 deformed. It is in ALL_PACKED.
    g = hou.Geometry()
    polyline(g, [(float(x), 0.0, 0.0) for x in range(26)], curve_id="CF")
    built["CF_resampled_straight"] = _case(g, rigid_kit(), Style(
        "rigid", 1, 6, rules=[Rule("default", "first", ["beam"])],
        params=Params(fill="adaptive")))

    # CH - A SWAP ONTO A TILE REMAINDER (D73). `tile` fills the 5 m run with
    # three whole 1.6 m gates and cuts the last one at 0.125 of its length;
    # the override then re-points every gate to the RIGID post. The old code
    # kept the gate's slice fraction and cut the post at 0.125 of ITS 0.12 m,
    # filling 0.015 m of a 0.2 m span - a silent 0.185 m hole at the end of
    # the fence with `warn_counts` empty. The remainder now takes D11's other
    # answer (the whole module scaled into the span) and says so, so this case
    # asserts both `pc_warn_tile_fallback` and an intact run.
    ov = hou.Geometry()
    P.write_override(ov, module="gate", to_module="post")
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (5, 0, 0)], curve_id="CH")
    built["CH_swap_tile_slice"] = _case(g, kit_geo, Style(
        "tile", 1, 4, rules=[Rule("default", "first", ["gate"])],
        params=Params(fill="tile")), overrides=ov)

    # CI - A SWAP RE-DERIVES THE Z-MODE (D73). The style leaves `zmode` empty,
    # so 3.2's per-module default decides; the panel's is `vertical` and the
    # post's is `stepped`. Swapping panel -> post on a sloped curve used to
    # build and stamp every post `vertical` - the module that is no longer
    # there. `zmode_stamp` asserts the stamp, and the curve is on a SLOPE so
    # that the wrong mode is a geometric difference and not only a label.
    ov = hou.Geometry()
    P.write_override(ov, module="panel", to_module="post")
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (10, 2.5, 0)], curve_id="CI")
    built["CI_swap_zmode"] = _case(g, kit_geo, Style(
        "swapz", 1, 4, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive")), overrides=ov)

    # CJ - A BEND BUTT JOINT THAT IS NOT 90 DEGREES. `corner_breach_m` allows
    # a square-ended butt joint exactly `h*sin(turn/2)` of bisector crossing,
    # and every other butt case in this suite turns 90 degrees - where sin and
    # cos are equal and the wrong one of the two passes anyway. This turns
    # 120, where the correct allowance is 0.025981 m and the old `cos` one was
    # 0.015 m: a legitimate joint failed by 1.10e-02 m.
    g = hou.Geometry()
    ang = math.radians(120.0)
    polyline(g, [(0, 0, 0), (4, 0, 0),
                 (4 + 4 * math.cos(ang), 0, 4 * math.sin(ang))],
             curve_id="CJ")
    built["CJ_bend_butt_120"] = _case(g, kit_geo, corner_style("bend"))

    # ---- and 4.5's four, all of them measured on the built fence.

    # BJ - GROUND UNDER A BRIDGE DECK (D70). A ground sheet at y = -2 under
    # the whole run and a deck sheet at y = +2 over its middle. The drop takes
    # the NEAREST surface, and a tie goes down-axis, so the whole fence is on
    # the ground; the first version cast from beyond the far side and took the
    # FIRST hit, which is "topmost", and put six of ten pieces on top of the
    # deck with two 3.9 m cliff pieces at its edges. `no_gaps_or_overlaps` and
    # `conform_contact_m` are what see it.
    both = hou.Geometry()
    both.merge(surface(lambda x, z: -2.0, x0=-4.0, x1=24.0, nx=28))
    both.merge(surface(lambda x, z: 2.0, x0=4.0, x1=16.0, nx=12))
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="BJ")
    built["BJ_conform_deck"] = _case(g, kit_geo, panel_style(zmode="vertical"),
                                     surface_geo=both)

    # BK - A SMALL SURFACE FAR BELOW THE SPLINE (D70). The reach used to come
    # from the surface's own bbox alone, so a 5 x 5 m prop (diagonal 7.07 m)
    # could not be reached from 30 m up and the whole run reported
    # `pc_warn_conform_miss` with the surface directly beneath it - the drape
    # flipping on standoff distance and nothing else. `conform_misses` is
    # pinned at 0 here and the run has to sit on the prop.
    g = hou.Geometry()
    polyline(g, [(1.0, 30.0, 0.0), (4.0, 30.0, 0.0)], curve_id="BK")
    built["BK_conform_far"] = _case(
        g, kit_geo, panel_style(zmode="vertical"),
        surface_geo=surface(lambda x, z: 0.0, x0=0.0, x1=5.0, z0=-2.5, z1=2.5,
                            nx=5, nz=5))

    # BL - A BUMP NARROWER THAN THE OLD PROBE SPACING (D71). 0.3 m wide and
    # 0.5 m tall, centred at x = 0.75 - between the five fixed samples the
    # unpack gate used to take across a 2 m panel, and ON that panel's own
    # 0.25 m station. The gate said "flat" and the panel shipped PACKED as a
    # straight chord with the bump 0.400 m through its bottom edge, unwarned.
    # `conform_drape_m` is the assertion: it scores every station of every
    # deformable piece, so a panel that ignored the bump reads 0.4 m.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="BL")
    built["BL_conform_bump"] = _case(g, kit_geo,
                                     panel_style(zmode="vertical"),
                                     surface_geo=surface(bump, x0=-1.0,
                                                         x1=21.0, nx=440))

    # BM - A HOLE ON A DEFORM STATION (D71). The 0.1 m hole at x = 0.70..0.80
    # falls between the five fixed probes `missed()` used to take and squarely
    # on the panel's own station at 0.75, so the built rail dipped to spline
    # elevation - a 0.1875 m V-notch - while `pc_warn_conform_miss` stayed
    # absent, which is D53's contract broken exactly where the drape stopped.
    # The warning is the assertion; the notch itself is D53's documented
    # behaviour and is what the warning is FOR.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="BM")
    nx = 220
    cell = 22.0 / nx
    holed = set((i, j) for i in range(nx) for j in range(12)
                if (-1.0 + (i + 1) * cell) > 0.70 and (-1.0 + i * cell) < 0.80)
    built["BM_conform_station_hole"] = _case(
        g, kit_geo, panel_style(zmode="vertical"),
        surface_geo=surface(ramp_x, x0=-1.0, x1=21.0, nx=nx, holes=holed))

    # BN - A SURFACE OVERHEAD, AND NEARER THAN THE ONE BELOW (D70). Ground at
    # y = -3, a deck at y = +0.4 over the middle of the run, spline at y = 0:
    # the deck is 0.4 m up and the ground 3 m down, so "the NEAREST hit along
    # the axis" puts the middle of the fence ON THE DECK.
    #
    # ⚠️ WRITTEN BECAUSE A MUTATION SURVIVED. `BJ_conform_deck` looks like it
    # covers this and does not: its deck and its ground are EQUIDISTANT, so
    # the tie-break (down-axis) decides and the comparison never runs. Cutting
    # `drop`'s nearest test down to "use the up-axis hit only when there is no
    # down-axis hit" moved not one number in the whole suite - the up-axis
    # cast won 12 405 times across the suite and every single one of those was
    # because nothing was found below. This case is the one where both
    # directions hit and the nearer one has to win.
    # STEPPED POSTS, so the answer is a NUMBER and not a warning:
    # `stepped_riser_m` records the 3.4 m step at the deck edge, which exists
    # only if the run climbed onto the deck at all.
    both = hou.Geometry()
    both.merge(surface(lambda x, z: -3.0, x0=-4.0, x1=24.0, nx=28))
    both.merge(surface(lambda x, z: 0.4, x0=6.0, x1=14.0, nx=8))
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="BN")
    built["BN_conform_overhead"] = _case(
        g, kit_geo,
        Style("overhead", 1, 3, rules=[Rule("default", "first", ["post"])],
              params=Params(fill="adaptive", zmode="stepped")),
        surface_geo=both)

    # CG - A RESAMPLED STRAIGHT LINE, BENDABLE MODULE (D69). CF is the same
    # geometry with a RIGID beam, and rigid short-circuits `_needs_deform` at
    # D27 before the vertex test is ever consulted - so CF cannot see D69 at
    # all. Measured: putting every interior vertex back into `kink_s` left CF
    # green and the whole 67-case suite at 0 failures, while the same revert
    # took PC-G3's resampled 20 km run from 10 005 packed / 0.60 s to
    # 0 packed / 10 005 deformed / 360 180 points / 21.9 s. This case uses the
    # starter kit's BENDABLE panel, which is the path D69 actually fixed, and
    # it is in ALL_PACKED.
    g = hou.Geometry()
    polyline(g, [(float(x), 0.0, 0.0) for x in range(21)], curve_id="CG")
    built["CG_resampled_bendable"] = _case(g, kit_geo, panel_style())

    # ---- cycle 7 / D75: THE CURVATURE BUDGET, across radii.
    # CF and CG proved a resampled STRAIGHT line stays packed. These are the
    # shape citygen streets actually hands this tool - a resampled ARC - and
    # before the budget every one of them unpacked every piece for a
    # deformation smaller than 4.6's own `over_unpacked` tolerance (measured:
    # R = 12 000 m unpacked 8 of 150 pieces for 4.2e-05 m and over_unpacked
    # FAILED). One case per decade of radius, so the budget is measured on a
    # ladder rather than at one point, plus the control that must still bend.
    for cid, radius in (("CK_arc_12000", 12000.0), ("CL_arc_2000", 2000.0),
                        ("CM_arc_80", 80.0), ("CN_arc_tight", 10.0)):
        g = hou.Geometry()
        polyline(g, arc_points(radius), curve_id=cid.split("_")[0])
        built[cid] = _case(g, kit_geo, panel_style())

    # ---- cycle 8 / D87: THE BUDGET IS SPENT BY POINTS, NOT BY THE SPINE.
    # A 1.2 m tall bendable rail on an R = 55 m arc that climbs. The spine
    # sagitta is 0.0091 m - inside `bend_tol` - so the D75 measure kept all
    # 15 pieces PACKED while their top corners had really moved 0.0327 m,
    # 3.3x the budget, leaving a visible wedge between neighbours. CP is the
    # case that reads it; CQ is the same figure with the SAME rail on a plan
    # arc, where `across` barely turns and the pieces are allowed to stay
    # packed - without it a fix could simply unpack everything and pass.
    # ---- cycle 8 / D94: A CONDITIONAL KEYED ON THE SPLINE'S OWN ATTRIBUTE.
    # 3.3 says `attr:<name>` "reads any spline prim attr" and it read exactly
    # two, because nothing harvested them - so the hook the first consumer
    # (streets, selecting off edge data) reaches for declined every piece in
    # silence. Two curves in one stream carrying different `road_width`s, one
    # rule: the wide one gets gates, the narrow one panels. Two curves rather
    # than one, so the attribute is proved to be read PER PRIM.
    g = hou.Geometry()
    g.addAttrib(hou.attribType.Prim, "road_width", 0.0)
    wide = polyline(g, [(0, 0, 0), (12, 0, 0)], curve_id="CRa")
    narrow = polyline(g, [(0, 0, 6), (12, 0, 6)], curve_id="CRb")
    wide.setAttribValue("road_width", 9.0)
    narrow.setAttribValue("road_width", 0.5)
    built["CR_attr_conditional"] = _case(g, kit_geo, Style(
        "attrcond", 1, 2,
        rules=[Rule("default", "conditional", ["gate"],
                    cond={"subject": "attr:road_width", "op": "gt",
                          "value": 1.0}),
               Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive")))

    tall = tall_kit()
    g = hou.Geometry()
    polyline(g, elevation_arc_points(55.0), curve_id="CP")
    built["CP_elev_arc_tall"] = _case(g, tall, rail_style())
    g = hou.Geometry()
    polyline(g, arc_points(2000.0, 1.0, 30.0), curve_id="CQ")
    built["CQ_plan_arc_tall"] = _case(g, tall, rail_style())

    return built


def duplicate_curve_ids(case):
    """TWO CURVES AUTHORED WITH ONE `pc_curve_id` - D74's control build.

    ⚠️ NOT A SCENE CASE, ON PURPOSE. Colliding `pc_elem_id`s are the whole
    point here, and every id-keyed check in the suite (element_count,
    unique_elem_ids, exact_fill, max_gap, plan_geometry...) reads a merged
    scene and reports nonsense on it - ten red checks describing one condition
    the tool deliberately only WARNS about. So the case is cooked by the check
    that needs it, the way `with_extra_curve` and `rebuild_plain` are, and
    what is asserted is the warning plus the size of the collision.
    """
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (8, 0, 0)], curve_id="dup")
    polyline(g, [(0, 0, 10), (8, 0, 10)], curve_id="dup")
    out, report = P.build(g, case["kit"], case["style"])
    return (out, report)


def with_extra_curve(case):
    """The same case with an UNRELATED curve merged into input 1.

    3.4's id rule is that `pc_elem_id` is a structural address and not cook
    order, so adding a second spline upstream must not renumber the first
    one's elements. Nothing else in the suite can see that: `determinism`
    cooks the SAME inputs twice, which a cook-order id would also survive.
    """
    g = hou.Geometry()
    g.merge(case["curve"])
    polyline(g, [(0, -50, 40), (9, -50, 40), (9, -50, 47)],
             curve_id="ZZ_unrelated")
    out, report = P.build(g, case["kit"], case["style"],
                          surface_geo=case.get("surface"),
                          overrides=case.get("overrides"))
    return (out, report)


def via_payload(case):
    """THE SAME CASE DRIVEN BY A 3.3 STYLE PAYLOAD instead of by its `Style`.

    This is gate PC-G4 as a measurement rather than as a claim: the style is
    written to geometry (`style.write`), read back through the pipeline face
    (`style.read`) and rebuilt. 2.1 says the payload OVERRIDES the parms
    entirely, so the returned build must be byte-identical to the one the
    object produced - and `style_round_trip` compares the digests, not the
    element count.
    """
    payload = hou.Geometry()
    S.write(payload, case["style"])
    back, warns = S.read(payload, kit=K.read(case["kit"])[0])
    if back is None:
        raise ValueError("payload read back as no style: %s" % warns)
    out, report = P.build(case["curve"], case["kit"], back,
                          surface_geo=case.get("surface"),
                          overrides=case.get("overrides"))
    return (out, report, warns)


# ---- 3.3's warn-never-block half, as an input rather than as a claim -------
# One rule per documented failure mode, in payload order. The expected results
# are in `checks.style_payload_degrades`, which is where the numbers live.
MALFORMED_RULES = (
    {"pc_slot": "wobble", "pc_modules": "post"},              # unknown slot
    {"pc_slot": "", "pc_modules": "post"},                    # no slot at all
    {"pc_slot": "default", "pc_select": "shuffle",            # unknown select
     "pc_modules": "post panel"},
    {"pc_slot": "end", "pc_select": "conditional",            # cond, no dict
     "pc_modules": ""},                                       # + no modules
    {"pc_slot": "start", "pc_select": "first",                # cond ignored,
     "pc_modules": "post",                                    # unknown subject
     "pc_cond": {"subject": "weather", "op": "zz", "value": 1}},   # + op
    {"pc_slot": "marker:7", "pc_select": "random",            # weight for a
     "pc_modules": "gate", "pc_weights": {"ghost": 2.0},      # module not in
     "pc_vexpr": "@u > 0.5"},                                 # the list + D3
)


def malformed_payload():
    """A 3.3 payload with one distinct fault per rule, plus a junk meta dict.

    Cooked by the check that needs it (the `duplicate_curve_ids` pattern):
    the assertion is that NOTHING raises, that every fault is named, and that
    what survives still builds a fence.
    """
    geo = hou.Geometry()
    for name, default in S.RULE_ATTRS:
        geo.addAttrib(hou.attribType.Point, name, default)
    geo.addAttrib(hou.attribType.Global, S.STYLE_DETAIL, {})
    geo.setGlobalAttribValue(S.STYLE_DETAIL, {
        "styleId": "malformed", "version": "two", "seed": 4,
        "params": {"fill": "sideways", "count": "many", "nonsense": 1}})
    for row in MALFORMED_RULES:
        pt = geo.createPoint()
        for key, value in row.items():
            pt.setAttribValue(key, value)
    return geo


def build_with_payload(case, payload):
    """`case` built by whatever `payload` turns out to mean. Never raises."""
    style, warns = S.read(payload, kit=K.read(case["kit"])[0])
    if style is None:
        return (None, warns)
    out, _report = P.build(case["curve"], case["kit"], style)
    return (out, warns)


def rebuild_plain(case):
    """The same case with the OVERRIDE input unwired - the control the swap
    and replace round-trips are measured against."""
    out, report = P.build(case["curve"], case["kit"], case["style"],
                          surface_geo=case.get("surface"))
    return (out, report)


def rebuild(case):
    """Cook the same inputs again into fresh geometry - the determinism check."""
    out, report = P.build(case["curve"], case["kit"], case["style"],
                          surface_geo=case.get("surface"),
                          overrides=case.get("overrides"))
    return (out, report)
