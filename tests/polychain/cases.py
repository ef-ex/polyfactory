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

    return built


def rebuild(case):
    """Cook the same inputs again into fresh geometry - the determinism check."""
    out, report = P.build(case["curve"], case["kit"], case["style"])
    return (out, report)
