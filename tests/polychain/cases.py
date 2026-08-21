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


def marker(geo, position, curve_id, marker_id, dist):
    for name, default in (("pc_marker", 0), ("pc_marker_id", 0)):
        if geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, default)
    if geo.findPointAttrib("pc_curve") is None:
        geo.addAttrib(hou.attribType.Point, "pc_curve", "")
    if geo.findPointAttrib("pc_dist") is None:
        geo.addAttrib(hou.attribType.Point, "pc_dist", 0.0)
    pt = geo.createPoint()
    pt.setPosition(position)
    pt.setAttribValue("pc_marker", 1)
    pt.setAttribValue("pc_curve", str(curve_id))
    pt.setAttribValue("pc_marker_id", int(marker_id))
    pt.setAttribValue("pc_dist", float(dist))
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


def hill_points():
    n = int(round(HILL_RADIUS * HILL_SWEEP / HILL_SPACING))
    pts = []
    for i in range(n + 1):
        a = HILL_SWEEP * i / float(n)
        s = HILL_RADIUS * a
        pts.append((HILL_RADIUS * math.sin(a), s * HILL_GRADE,
                    HILL_RADIUS * (1.0 - math.cos(a))))
    return pts


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


# --- the cases --------------------------------------------------------------

def _case(curve_geo, kit_geo, style):
    out, report = P.build(curve_geo, kit_geo, style)
    return {"curve": curve_geo, "kit": kit_geo, "style": style,
            "out": out, "report": report}


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

    return built


def rebuild(case):
    """Cook the same inputs again into fresh geometry - the determinism check."""
    out, report = P.build(case["curve"], case["kit"], case["style"])
    return (out, report)
