"""polyChain scene cases - every scene the checks run against.

No .hip and no node network (see tests/citygen/cases.py for why): a case is
three `hou.Geometry` objects and a `Style`, so the checks measure the builder
and nothing else. Every starter-kit module runs exactly local x = 0 to
`pc_size.x` with NO overhang - deliberate, the checks depend on it (a kit
with overhang is legal, D20, and would need the checks to carry it).
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
from polyfactory.polychain import Params, Rule, Style, Curve      # noqa: E402
from polyfactory.polychain import kit as K                        # noqa: E402
from polyfactory.polychain import place as P                      # noqa: E402
from polyfactory.polychain import style as S                      # noqa: E402
from polyfactory.polychain import conform as CONFORM              # noqa: E402


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


def marker(geo, position, curve_id, marker_id, dist=None, u=None, data=None):
    """One 3.1 marker point, authored through `pc_dist` OR `pc_u` - never
    both: attributes are geometry-wide, so mixing conventions in one cloud
    is `N_marker_mixed`'s case."""
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
    if data is not None:
        # 3.3's `markerData:<key>` DICT bag; an EMPTY-STRING value is the
        # fixture separating "the string \"\"" from "the number 0".
        if geo.findPointAttrib("pc_marker_data") is None:
            geo.addAttrib(hou.attribType.Point, "pc_marker_data", {})
        pt.setAttribValue("pc_marker_data", dict(data))
    return pt



# --- the hill: an arc on a constant grade -----------------------------------
# 0.5 m sampling on R = 30 m: 0.95 degrees per vertex - ONE section, and fine
# enough that a 2 m panel's 0.25 m stations resolve it inside `bend_tol`.
HILL_RADIUS = 30.0
HILL_SPACING = 0.5
HILL_SWEEP = math.pi / 3.0          # 60 degrees -> 31.4 m of horizontal arc
HILL_GRADE = 0.25                   # 25 %, 14.04 degrees of bank in adaptive
                                    # (5 % was too gentle to be diagnostic).


def arc_points(radius, spacing=1.0, length=20.0):
    """A circular arc in XZ, RESAMPLED at `spacing` - a street polyline (D75).

    Sagitta c*c/(8*radius): a 2 m panel on the four radii deviates 4.2e-05,
    2.5e-04, 6.2e-03 and 5.0e-02 m - three under the 0.01 m `bend_tol`, the
    last five times over. The budget must keep three packed AND bend the
    fourth."""
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
# All ANALYTIC, so the expected drape is trigonometry on the input rather
# than a number read off a build.

CONFORM_GRADE = 0.25            # 25 %, 14.036 degrees - PC-G2's own grade
RIDGE_AMP = 0.8
RIDGE_WAVE = 8.0                # m per wave: a 2 m panel cannot chord it


def surface(fn, x0=-4.0, x1=24.0, z0=-6.0, z1=6.0, nx=28, nz=12,
            flip=False, holes=()):
    """A quad grid over [x0,x1] x [z0,z1] with y = fn(x, z); `flip` reverses
    winding (D52), `holes` drops (i, j) cells (D53). Hand-built: the Grid SOP
    is not under test."""
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


def wall(fn, x0=-2.0, x1=22.0, n=480):
    """A near-VERTICAL sheet at z = fn(x), spanning y in [-3, 3].

    ⚠️ THE ONLY SHAPE IN THE SUITE A +-Z DROP CAN LAND ON, and it exists for
    one branch: `pc_frames_transportable` adds the piece's OWN STATIONS to its
    sample set on a conformed build (13.9 N6), and with a +-Y axis that branch
    decides NOTHING - the drop selects x and z from the QUERY, so the conformed
    horizontal tangent direction is the spline's own. The C4 audit registered
    the deletion of that loop as a mutation and it survived the entire suite.
    """
    geo = hou.Geometry()
    pts = {}
    for i in range(n + 1):
        x = x0 + (x1 - x0) * i / float(n)
        for j in range(3):
            pt = geo.createPoint()
            pt.setPosition((x, -3.0 + 3.0 * j, fn(x)))
            pts[(i, j)] = pt
    for i in range(n):
        for j in range(2):
            poly = geo.createPolygon()
            for pt in (pts[(i, j)], pts[(i, j + 1)],
                       pts[(i + 1, j + 1)], pts[(i + 1, j)]):
                poly.addVertex(pt)
    return geo


def ramp_x(x, _z):
    return CONFORM_GRADE * x


BUMP_CENTRE = 0.75              # between the five fixed probes the unpack
BUMP_WIDTH = 0.3                # gate used to take, and ON a panel station
BUMP_HEIGHT = 0.5


def bump(x, _z):
    """A ridge NARROWER THAN A QUARTER OF A PIECE on flat ground at y = -1
    (D71): invisible to a fixed five-sample gate, resolved by 0.25 m
    stations."""
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

    Peak at 10.2 m, NOT 10: at 10 m (piece boundary) or 11 m (panel station)
    the drape resolves exactly and nothing warns. 10.2 sits between two
    0.25 m stations - D25 measured against the conformed path: the piece cuts
    0.014 m off the ridge and says `pc_warn_bend_resolution`."""
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
    """A TALL bendable rail - the module the spine-only budget could not see
    (D87: `span_deviation` measured the spine, so off-spine points spent a
    budget nobody counted). Height is the whole point."""
    geo = hou.Geometry()
    rail = hou.Geometry()
    K.box_mesh(rail, 0.0, length, 0.0, height, -0.5 * depth, 0.5 * depth, 8)
    K.add_module(geo, "rail", rail, size=(length, height, depth),
                 deform=1, zmode=zmode, roles="default")
    K.write_manifest(geo, "pf_tall", 1, sources=("cases.tall_kit",),
                     human_scale_reference=1.8)
    return geo


def elevation_arc_points(radius=55.0, spacing=1.0, length=30.0):
    """An arc that climbs - curvature in ELEVATION, dead straight in plan:
    `up` swings by the full turn and a tall piece's top corner pays for it."""
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


def variant_kit():
    """The starter kit's two workhorses, each authored with a `pc_variant`.

    Standing finding (10), found by mutation: nothing in the 87-case suite
    ever authored one, so blanking the stamp in BOTH writers changed no value
    anywhere - the whole column was vacuous."""
    geo = hou.Geometry()
    post = hou.Geometry()
    K.box_mesh(post, 0.0, 0.12, 0.0, 1.20, -0.06, 0.06, 1)
    K.add_module(geo, "post", post, size=(0.12, 1.20, 0.12), deform=0,
                 zmode="stepped", roles="default start end post",
                 variant="oak")
    panel = hou.Geometry()
    K.box_mesh(panel, 0.0, 2.00, 0.10, 1.00, -0.03, 0.03, 8)
    K.add_module(geo, "panel", panel, size=(2.00, 0.90, 0.06), deform=1,
                 zmode="vertical", roles="default panel", variant="oak_long")
    K.write_manifest(geo, "pf_variant", 1, sources=("cases.variant_kit",),
                     human_scale_reference=1.8)
    return geo


def broken_kit():
    """Deliberately malformed - one distinct fault per module, so the count
    is a fingerprint. Seven faults -> 9 warnings (the nameless module is not
    inspected further); `build` must still produce geometry
    (warn-never-block)."""
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
# One L, one rectangle, one zigzag - shared so only corner PARAMETERS vary.

L_SHAPE = [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 0.0, 12.0)]
RECT = [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0), (12.0, 0.0, 8.0), (0.0, 0.0, 8.0)]
# LEFT, then RIGHT - the first version turned left twice and tested nothing
# the L-shape did not; `corner_turns` records the two signs now.
ZIGZAG = [(0.0, 0.0, 0.0), (8.0, 0.0, 0.0), (12.0, 0.0, 4.0),
          (20.0, 0.0, 4.0)]
# The same rectangle with legs that are NOT a multiple of the 2 m evenly
# spacing, so the justify leftover approaches zero and an evenly anchor can
# reach the corner assembly. See the EA..EI block for why that matters.
RECT_ODD = [(0.0, 0.0, 0.0), (12.161, 0.0, 0.0), (12.161, 0.0, 8.161),
            (0.0, 0.0, 8.161)]

# A 90 degree corner post of half-width 0.08 m reaches e = 0.08*tan(45) past
# the vertex, so its outside face still measures its full 0.16 m.
CORNER_POST_LENGTH = 0.16
CORNER_BLOCK_LENGTH = 1.20


def corner_style(mode="miter", offset=0.0, fillet=0.0, fill="adaptive",
                 displacement="reset", evenly="", evenly_spacing=0.0,
                 justify="center", adjust_to_end=0.0, corner="corner_post",
                 marker=""):
    """The PC-G1 fence, with 4.3's parms exposed. Same kit, same rules.

    `evenly` is D269's fixture repair (§28.1(c)): the shipped composition
    (`panel` fill + `evenly post` @ 2 m) appeared in no corner case; these
    arguments let EA..EI run it through the corner battery."""
    rules = [
        Rule("default", "first", ["panel"]),
        Rule("start", "first", ["post"]),
        Rule("end", "first", ["post"]),
        Rule("corner", "first", [corner]),
    ]
    if evenly:
        rules.append(Rule("evenly", "first", [evenly]))
    if marker:
        rules.append(Rule("marker:7", "first", [marker]))
    return Style("corner", 1, 9, rules=rules,
                 params=Params(fill=fill, corner_mode=mode,
                               corner_offset_pct=offset, fillet_radius=fillet,
                               corner_displacement=displacement,
                               evenly_spacing=evenly_spacing,
                               justify=justify, adjust_to_end=adjust_to_end))


def compose_kit():
    """The starter fence plus a second, LONGER corner module: compose
    symmetry needs modules of differing length - `corner_block` 1.20 m vs
    `corner_post` 0.16 m, so odd/even differ by 1.20 m, not a rounding
    artefact."""
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
    # 11.2 P5: the `ConformPath`s are KEPT so `conform_parity` can ask the
    # batched `ray` and per-query `intersect` in one process (11.3 rule 4).
    made = []
    real = CONFORM.ConformPath.__init__

    def spy(self, *a, **k):
        real(self, *a, **k)
        made.append(self)
    CONFORM.ConformPath.__init__ = spy
    try:
        out, report = P.build(curve_geo, kit_geo, style,
                              surface_geo=surface_geo, overrides=overrides)
    finally:
        CONFORM.ConformPath.__init__ = real
    return {"curve": curve_geo, "kit": kit_geo, "style": style,
            "out": out, "report": report, "surface": surface_geo,
            "overrides": overrides, "paths": made}


# --- 13.10 TOPOLOGY FIXTURES - the shapes 4.1's parity rig could not see ----
# NOT in `build_all()`: they make three DECOMPOSE checks fail-able, and two
# build no geometry; `run_native_checks.py` merges them. Each was a measured
# hole:
#   * `T1_fused_junction` - shared-point junction (graph_fuse's shape): before
#     `pc_unshare` the 90 degree corner vanished and the junction metre
#     flipped 0.000 -> 10.000 with primitive order alone.
#   * `T2_marker_in_prim` - the VEX built a curve `read_curves` refuses.
#   * `T3_dup_id_marker` - duplicate id + marker: the reference fans out
#     (s = 5 and s = 20), the native stage answers the first and WARNS (D169).

def fused_pair(geo):
    """Two polylines SHARING their junction point, as `graph_fuse` emits; A
    turns 90 degrees AT the shared vertex (turn = 90.000 deg, s = 10)."""
    if geo.findPrimAttrib("pc_curve_id") is None:
        geo.addAttrib(hou.attribType.Prim, "pc_curve_id", "")
    shared = geo.createPoint()
    shared.setPosition((10.0, 0.0, 0.0))
    for cid, pts in (("FA", [(0.0, 0.0, 0.0), None, (10.0, 0.0, 10.0)]),
                     ("FB", [None, (20.0, 0.0, 0.0)])):
        poly = geo.createPolygon(False)
        for p in pts:
            if p is None:
                poly.addVertex(shared)
            else:
                pt = geo.createPoint()
                pt.setPosition(p)
                poly.addVertex(pt)
        poly.setAttribValue("pc_curve_id", cid)
    return geo


def topology_cases():
    """The three fixtures above, in `_case`'s own shape."""
    kit_geo = K.starter_kit()
    out = {}

    g = hou.Geometry()
    fused_pair(g)
    out["T1_fused_junction"] = _case(g, kit_geo, fence_style())

    # A marker ON one of the curve's own vertices, which is what
    # `read_curves` refuses to build a curve behind.
    g = hou.Geometry()
    poly = polyline(g, [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (20.0, 0.0, 0.0)],
                    curve_id="T2")
    for name, default in (("pc_marker", 0), ("pc_marker_id", 0)):
        if g.findPointAttrib(name) is None:
            g.addAttrib(hou.attribType.Point, name, default)
    if g.findPointAttrib("pc_curve") is None:
        g.addAttrib(hou.attribType.Point, "pc_curve", "")
    mid = poly.points()[1]
    mid.setAttribValue("pc_marker", 1)
    mid.setAttribValue("pc_curve", "T2")
    out["T2_marker_in_prim"] = _case(g, kit_geo, fence_style())

    g = hou.Geometry()
    polyline(g, [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)], curve_id="DUP")
    polyline(g, [(0.0, 0.0, 5.0), (40.0, 0.0, 5.0)], curve_id="DUP")
    marker(g, (0.0, 3.0, 0.0), "DUP", 1, u=0.5)
    out["T3_dup_id_marker"] = _case(g, kit_geo, fence_style())

    # T4 / T5 - C3's two ROW attributes on a 1D spline, which is exactly how
    # an artist reaches D295's refusal: the 2D path has no HDA, so the only
    # way `pc_bays` or `pc_upref` arrives at `pf_polychain` is on a wired
    # curve. The native chain reads NEITHER - `pc_plan_solve` has no term for
    # a bay count and `pc_proto` writes the world up axis as a constant - so
    # the guard must send both builds to the reference.
    #
    # ⚠️ TWO CASES AND NOT ONE, AND THE SWEEP IS WHY. They were one curve
    # carrying both attributes, and BOTH registered mutations SURVIVED with
    # "reddened nothing at all": each removes one half of the refusal while
    # the other half still fires, so the build stayed on the reference and
    # `output_guard_parity` could not move. One case per refusal, one mutation
    # per case.
    g = hou.Geometry()
    poly = polyline(g, [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0)], curve_id="T4")
    g.addAttrib(hou.attribType.Prim, "pc_bays", "")
    poly.setAttribValue("pc_bays", "0:3")
    out["T4_row_bays_1d"] = _case(g, kit_geo, fence_style())

    g = hou.Geometry()
    poly = polyline(g, [(0.0, 0.0, 0.0), (12.0, 0.0, 0.0)], curve_id="T5")
    g.addAttrib(hou.attribType.Prim, "pc_upref", (0.0, 1.0, 0.0))
    poly.setAttribValue("pc_upref", (0.0, 0.70710678, 0.70710678))
    out["T5_row_upref_1d"] = _case(g, kit_geo, fence_style())
    return out


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

    # DA/DB/DC/DD/DE - 4.4's FLATTEN-UNDER and its two hybrid BANDS (D98,
    # D99), all read against G_hill_stepped (same hill/style/kit, parms off).
    # DA: flatten alone - `stepped_float_m` moves, `stepped_riser_m` must not.
    # DB: same curve REVERSED - the datum comes from the low point, so drawing
    # direction cannot matter. DD: `vertical` panel, TOP band held level.
    # DE: `stepped` panel, BOTTOM band follows ground (`panel` because a rigid
    # module cannot express a band, D27). DC: the BEFORE, reversed because the
    # defect only shows downhill - the number DA and DB take to zero.
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

    # DH/DI - D105: DD's level top rail took its datum from the piece's START
    # (`band_datum_m` 0.490874 m), so the reversed curve moved every rail.
    # This pair runs the flatten ON, forward + reversed; the datum is now an
    # extremum over the piece's span, so the number is 0 on both.
    for name, pts in (("DH_band_flat_datum", hill_points()),
                      ("DI_band_flat_datum_rev", list(reversed(hill_points())))):
        g = hou.Geometry()
        polyline(g, pts, curve_id="H")
        built[name] = _case(g, kit_geo, Style(
            "banded", 1, 4, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="vertical", flat_band="top",
                          flat_band_m=0.25, flatten_stepped=True)))

    # DJ - D98's datum on a REPLACED piece: the D58 hero transform was built
    # without the datum, so a replaced post floated 0.490874 m above its
    # planted neighbours, unwarned. Reversed (the float's direction). Hero is
    # 1.5 m tall vs 1.2 m, so it is unmistakably NOT the kit module.
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

    # DF/DG - D100's CAMBER OFF-SPINE BUDGET GAP, as a pair. Surface
    # y = k*x*z, run straight along +X at z = 0: the spine reads dead flat,
    # only the cross-fall roll atan(k*x) moves. DF k = 0.2: pre-D100 all 10
    # panels stayed packed at 0.2126 m, 21x `bend_tol`. DG k = 0.005
    # (0.0055 m, inside budget) is the anti-vacuity half.
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

    # DK - D104, DF's defect one level down: a superelevation TRANSITION,
    # `y = 0.2 sin(pi x) z` - roll is ZERO at every 2 m boundary and
    # midpoint, +/-11.3 degrees at quarter-span. Pre-D104: 10/10 panels
    # PACKED at 0.197164 m (19.7x `bend_tol`); a 1 m-resampled spline was
    # defeated identically. `deform_gate_m`'s middle number keeps it honest:
    # 10 over budget, 0 packed.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20.0, 0, 0)], curve_id="CB")
    built["DK_camber_ripple"] = _case(g, kit_geo, Style(
        "crossfall", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", zmode="adaptive", conform_tilt=True)),
        surface_geo=surface(
            lambda x, z: 0.2 * math.sin(math.pi * x) * z,
            x0=-2.0, x1=22.0, z0=-6.0, z1=6.0, nx=240, nz=48))

    # H and I - slope fixing (D26) as a PAIR, under TILE: adaptive rescales
    # every piece, so both fits give the same 16 pieces and measure nothing.
    # Tile keeps whole pieces unscaled: free gives 1.55 m of horizontal reach
    # per 1.6 m gate, fixed gives 1.60 m - iToo's sentence as two numbers.
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

    # L - a STRAIGHT ramp: the only sloped span with no interior vertex, the
    # one shape separating `vertical` from `stepped` for a bendable module -
    # otherwise the vertical branch of `_needs_deform` is never under test.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12.0, 3.0, 0)], curve_id="L")
    built["L_ramp_vertical"] = _case(g, kit_geo, panel_style(zmode="vertical"))

    # M - a RIGID 2.5 m beam over a 33.7 degree vertex, corner threshold 45
    # so the section holds. Exists because a mutation survived: packing from
    # the START TANGENT instead of the chord (D21) changed nothing elsewhere
    # - only a rigid module stays packed across a bend and can tell them apart.
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

    # N - one marker cloud, two conventions: marker 7 in metres, marker 8 in
    # u (so it also carries pc_dist = 0.0, geometry-wide). Reading dist
    # without asking if it was AUTHORED built the second gate at s = 0.
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

    # P - an OVERHANGING CREST: the tangent's horizontal direction reverses
    # mid-piece, where a per-point cross(tangent, up) frame flips 180 degrees.
    # corner_angle_deg = 60 keeps it one section, so one panel straddles it.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (2, 3, 0), (1, 6, 0)], curve_id="P")
    built["P_crest_bend"] = _case(g, kit_geo, Style(
        "crest", 1, 1, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", zmode="adaptive",
                      corner_angle_deg=60.0)))

    # Q - a PURELY VERTICAL run in a yaw-only z-mode: the flattened chord has
    # no length; the scale collapsed to 1e-9, 25 invisible prims. D32: pieces
    # keep their 3D length and say `pc_warn_degenerate_frame`.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (0, 3, 0)], curve_id="Q")
    built["Q_vertical_stepped"] = _case(g, kit_geo, Style(
        "vert", 1, 1, rules=[Rule("default", "first", ["post"])],
        params=Params(fill="adaptive")))

    # R - a SUPPRESSED HAIRPIN under a rigid module: 4 m of there-and-back
    # polyline whose ends are 0.10 m apart - a 25x collapse is a measurable
    # degeneration and warn-never-block says it must be visible.
    g = hou.Geometry()
    poly = polyline(g, [(0, 0, 0), (2, 0, 0), (0, 0, 0.1)], curve_id="R")
    g.addAttrib(hou.attribType.Point, "pc_corner", 0)
    poly.points()[1].setAttribValue("pc_corner", -1)          # -1 = suppress
    built["R_hairpin"] = _case(g, rigid_kit(), Style(
        "hair", 1, 1, rules=[Rule("default", "first", ["beam"])],
        params=Params(fill="scale", corner_angle_deg=170.0,
                      min_included_angle_deg=1.0)))

    # S - a gate at 19.7 m of a 20.006 m curve: the 1.6 m module legitimately
    # OVERHANGS the end (D20). The sampler used to clamp, crushing the last
    # 0.49 m of the gate into the end plane.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20.006, 0, 0)], curve_id="S")
    marker(g, (19.7, 0, 0), "S", 7, dist=19.7)
    built["S_overhang_gate"] = _case(g, kit_geo, Style(
        "overhang", 1, 2, rules=[Rule("default", "first", ["panel"]),
                                 Rule("marker:7", "first", ["gate"])],
        params=Params(fill="adaptive")))

    # ---- 4.3 CORNERS. Measured, never looked at: the numbers are
    # `corner_*` in checks.py.

    # T - the L-shape in BEND mode (D36: one 24 m section, a panel wraps the
    # vertex; the corner rule is deliberately present and unused, D37).
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="T")
    built["T_lshape_bend"] = _case(g, kit_geo, corner_style("bend"))

    # U - the same L in MITER mode: the post is duplicated both sides,
    # sliced on the bisector - `corner_outside_m` must read the post's own
    # 0.16 m and `corner_seam_m` 0.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="U")
    built["U_lshape_miter"] = _case(g, kit_geo, corner_style("miter"))

    # V - PC-G1's closed rectangle, mitered. The fourth corner is the wrap
    # corner RailClone documents it cannot offset (D45); nothing here
    # special-cases it.
    g = hou.Geometry()
    polyline(g, RECT, closed=True, curve_id="V")
    built["V_rect_miter"] = _case(g, kit_geo, corner_style("miter"))

    # W, X - the corner offset, +/-25 % of the module length: positive leaves
    # a gap of 2*o*cos(turn/2), negative cuts each piece deeper into the
    # corner. Both read off the built cut faces.
    for name, pct in (("W_corner_offset_pos", 25.0),
                      ("X_corner_offset_neg", -25.0)):
        g = hou.Geometry()
        polyline(g, L_SHAPE, curve_id=name[0])
        built[name] = _case(g, kit_geo, corner_style("miter", offset=pct))

    # Y, Z - COMPOSE SYMMETRY, the odd/even rule: odd reaches equally down
    # both legs, even puts one module more on one leg.
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

    # AA - a REFLEX corner: left then right, so the outside faces sit on
    # opposite sides. `Bevel.side` is a sign; this case proves it.
    g = hou.Geometry()
    polyline(g, ZIGZAG, curve_id="A")
    built["AA_reflex_miter"] = _case(g, kit_geo, corner_style("miter"))

    # AB - the FILLET (4.3 item E). `corner_clearance_m` is the acceptance:
    # at 90 degrees filleted by 1.5 m nothing may come closer to the sharp
    # vertex than 1.5*(1/cos45 - 1) = 0.6213 m.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="B")
    built["AB_fillet"] = _case(g, kit_geo, corner_style("bend", fillet=1.5))

    # AC - a DEGENERATE corner: 10 degrees included, under the 15 degree
    # threshold, so 4.3 falls back to bend and says
    # pc_warn_corner_degenerate. It must still build.
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

    # AE, AF, AG - the DISPLACEMENT POLICY with NO corner rule, read as a
    # TRIPLE: the three must not agree (item D).
    for name, policy in (("AE_displace_reset", "reset"),
                         ("AF_displace_extend", "extend"),
                         ("AG_displace_symmetric", "symmetric")):
        g = hou.Geometry()
        polyline(g, L_SHAPE, curve_id=name[:2])
        built[name] = _case(g, kit_geo, Style(
            "displace", 1, 4, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", corner_mode="miter",
                          corner_displacement=policy)))

    # ---- the cycle-3 REVIEW cases: each a measured defect before it was a
    # case (tests/README.md's rule).

    # AH - A TURN SHARPER THAN THE CORNER MODULE: at 140 degrees the 0.16 m
    # post's miter overhang is 0.2198 m, so the reserve went negative and a
    # panel interpenetrated the other leg by 0.031 m, silently. Clamped at 0
    # now; `corner_breach_m` asserts pieces stay on their own sides.
    a = math.radians(140.0)
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0),
                 (12 + 12 * math.cos(a), 0, 12 * math.sin(a))], curve_id="AH")
    built["AH_sharp_turn"] = _case(g, kit_geo, corner_style("miter"))

    # AI - A LEG SHORTER THAN TWICE THE OVERHANG: a 1.5 m equilateral
    # triangle leaves 0.0215 m of reserve against a 0.03 m panel
    # half-thickness - panel ends crossed inside the post's footprint.
    _tri = 1.5
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (_tri, 0, 0),
                 (_tri * 0.5, 0, _tri * math.sqrt(3.0) / 2.0)],
             closed=True, curve_id="AI")
    built["AI_triangle"] = _case(g, kit_geo, corner_style("miter"))

    # AJ, AK - closed figures always clean, always MISMEASURED: `_frame_of`
    # folded `across` into `up` on clipped corner posts - phantom gaps of
    # 0.160 m (reflex L) and 0.129 m (pentagon) on shut corners.
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

    # AL, AM - NON-PLANAR CORNERS met with a `stepped` (plumb) corner post.
    # A bevel from the 3D tangents cut on a tilted plane: crest copies
    # 0.055 m apart in Y, faces mated to 0.0548 m; the graded corner left a
    # 0.345 m stump. Neither warned. D48 flattens the bevel for yaw-only.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (7.52, 2.74, 0), (15.04, 0, 0)], curve_id="AL")
    built["AL_crest_corner"] = _case(g, kit_geo, corner_style("miter"))

    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (8, 2, 0), (8, 4, 8)], curve_id="AM")
    built["AM_graded_corner"] = _case(g, kit_geo, corner_style("miter"))

    # AN - THE DISPLACEMENT POLICY UNDER `tile`, sliceable default. D40's
    # first cut extended the FILL SPAN, so tile tiled into the extension (a
    # whole sliced piece past the vertex; a 0.03 m sliver under `extend`).
    # The boundary piece is one anchored module now.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="AN")
    built["AN_tile_symmetric"] = _case(g, kit_geo, Style(
        "tilesym", 1, 4, rules=[Rule("default", "first", ["gate"])],
        params=Params(fill="tile", corner_mode="miter",
                      corner_displacement="symmetric")))

    # AO - THE CORNER OFFSET WITH NO CORNER MODULE: `bevel.offset` was set
    # after the empty-mods early return, so 0/25/50 % built byte-identical
    # geometry. Moves D40's boundary piece now; differs from
    # AF_displace_extend by nothing but the parm.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="AO")
    built["AO_displace_offset"] = _case(g, kit_geo, Style(
        "dispoff", 1, 4, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", corner_mode="miter",
                      corner_displacement="extend", corner_offset_pct=-10.0)))

    # AP - A FIGURE NARROWER THAN ITS OWN FENCE (12 m x 0.12 m): D44
    # squeezes all four corners. Scaling about the VERTEX left an e*(1-f)
    # notch; it scales about the PLANE CONTACT now.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 0.12), (0, 0, 0.12)],
             closed=True, curve_id="AP")
    built["AP_narrow_rect"] = _case(g, kit_geo, corner_style("miter"))

    # AQ - AN ASYMMETRICALLY SQUEEZED CORNER (D44, one side only) - the case
    # AD_short_legs cannot see; vertex-scaling left a 1.20 m cut face mating
    # against a 0.776 m one.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 1.5)], curve_id="AQ")
    built["AQ_asym_squeeze"] = _case(g, compose_kit(), Style(
        "asym", 1, 3,
        rules=[Rule("default", "first", ["panel"]),
               Rule("corner", "sequence", ["corner_block", "corner_block",
                                           "corner_block"])],
        params=Params(fill="adaptive", corner_mode="miter")))

    # AR - THE OFFSET DIALLED PAST THE CORNER MODULE (-100 %): the negative
    # reserve opened a 23 cm hole with an empty warning list. Clamped and
    # warned now.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="AR")
    built["AR_offset_past"] = _case(g, kit_geo,
                                    corner_style("miter", offset=-100.0))

    # ---- the cycle-4 cases.

    # AS - cycle 3v's own figure: PC-G1's rectangle in BEND mode, panel-only,
    # so twenty 2 m panels fit the 40 m ring EXACTLY and every corner is a
    # butt joint - what `corner_breach_m`'s bend branch and
    # `corner_wedge_m2` were written for. B_rect_closed cannot cover it.
    g = hou.Geometry()
    polyline(g, RECT, closed=True, curve_id="AS")
    built["AS_rect_bend_butt"] = _case(g, kit_geo, corner_style("bend"))

    # ---- EA..EI - THE COMPOSITION THE ASSET ACTUALLY SHIPS, ON A CORNER.
    # D269 (§28.1(c) again): after D266 the shipped `panel` fill + `evenly
    # post` @ 2 m appeared ZERO times here, so the ~35 corner/closure checks
    # ran a composition the asset does not ship. Nine cases: four shapes, all
    # three justifications, `adjust_to_end`, a blocky corner module (EH), a
    # marker at a corner (EI). THE LEG LENGTHS ARE THE FIXTURE: on 12 x 8 m
    # every justification measures 0.0 before AND after D269 (12 m is a
    # multiple of the 2 m spacing); `RECT_ODD` (12.161 x 8.161 m) puts the
    # leftover ~0, where `From the end` drove the post 0.061 m INTO the
    # mitered corner post pre-D269.
    for name, cid, pts, closed, kw in (
            ("EA_rect_miter_evenly", "EA", RECT, True, {}),
            ("EB_rect_evenly_start", "EB", RECT_ODD, True,
             {"justify": "start"}),
            ("EC_rect_evenly_end", "EC", RECT_ODD, True, {"justify": "end"}),
            ("EE_lshape_evenly", "EE", L_SHAPE, False, {}),
            ("EF_reflex_evenly", "EF", ZIGZAG, False, {}),
    ):
        g = hou.Geometry()
        polyline(g, pts, closed=closed, curve_id=cid)
        built[name] = _case(g, kit_geo, corner_style(
            "miter", evenly="post", evenly_spacing=2.0, **kw))

    # ED - `Adjust to End` lands the last anchor against the corner assembly:
    # after D269 what is left is an exact ABUTMENT, one whole 0.12 m post -
    # the artist's instruction, not a defect (pinned in `DOUBLE_PILLAR`).
    # 12.66 m leaves a leftover under the 1 m `adjust_to_end` so the branch
    # fires; on 12 m it never does.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12.66, 0, 0), (12.66, 0, 8.66), (0, 0, 8.66)],
             closed=True, curve_id="ED")
    built["ED_rect_evenly_adjust"] = _case(g, kit_geo, corner_style(
        "miter", evenly="post", evenly_spacing=2.0, adjust_to_end=1.0))

    _pent5 = 6.0 / (2.0 * math.sin(math.pi / 5.0))
    g = hou.Geometry()
    polyline(g, [(_pent5 * math.cos(2 * math.pi * i / 5.0), 0.0,
                  _pent5 * math.sin(2 * math.pi * i / 5.0))
                 for i in range(5)], closed=True, curve_id="EG")
    built["EG_pentagon_evenly"] = _case(g, kit_geo, corner_style(
        "miter", evenly="post", evenly_spacing=2.0))

    # EH - A CORNER MODULE THAT IS NOT SLENDER: `corner_block` aspect 1.08,
    # so `single_pillar`'s first cut classified it not-upright and measured
    # 0.0 on a build that doubled every corner. D270 protects a RESERVED
    # piece whatever its aspect; this fixture keeps it protected.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="EH")
    built["EH_block_corner_evenly"] = _case(g, compose_kit(), corner_style(
        "miter", evenly="post", evenly_spacing=2.0, corner="corner_block"))

    # EI - A MARKER SLOT ON A CORNERED CURVE, which no marker case reached.
    # `marker:<id>` is a RESERVED slot, protected by `single_pillar` like
    # `corner` and `evenly`. Marker mid-leg ON PURPOSE: 0.4 m short of the
    # vertex it lands in the corner reserve (measured `pc_warn_overflow`,
    # `corner_abut_m` 0.040, `corner_face_mate_m` 0.113, `double_pillar_m`
    # 0.0767) - standing finding §28.7, not a pin.
    g = hou.Geometry()
    polyline(g, L_SHAPE, curve_id="EI")
    marker(g, (5.0, 0, 0), "EI", 7, 5.0)
    built["EI_marker_at_corner"] = _case(g, kit_geo, corner_style(
        "miter", evenly="post", evenly_spacing=2.0, marker="gate"))

    # ---- 4.5 SURFACE CONFORM (input 4). The spline is dead flat/straight
    # in all of these, so everything vertical came from the surface.

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

    # BE - A HOLE, AND AN EDGE: the run leaves the terrain twice - D53 keeps
    # spline elevation there, says `pc_warn_conform_miss`, NOTHING raises;
    # pieces over solid ground must still drape.
    built["BE_conform_holes"] = _case(
        conform_line("BE"), kit_geo, Style(
            "holed", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="vertical")),
        surface_geo=surface(ramp_x, x0=-2.0, x1=12.0, nx=14,
                            holes=set((7, j) for j in range(12))))

    # BF - A BACK-FACING SURFACE (D52): identical ramp, wound the other way.
    # The drape must come out the same; `geometry_digest` pins it against BG.
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

    # BH - A SURFACE COARSER THAN THE PIECES, hard crease (D56): the piece ON
    # the crease says `pc_warn_bend_resolution` (D25's detector measured
    # against the conformed path); every other piece is clean.
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

    # BJ - A TILTED `conform_axis` (D51, D111): the one configuration where
    # batched `ray` and per-query stop agreeing (float32 origin off the
    # double ray; divergence ALONG the ray, 1.9e-06 m at 20 m, 1.5e-05 m at
    # 20 km), so `Surface.batchable` declines and the reference serves it.
    # Asserted: the drape still happens; `conform_parity` reports the
    # declined batch as a skip.
    built["BJ_tilted_axis"] = _case(
        conform_line("BJ"), kit_geo, Style(
            "tilted", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="vertical",
                          conform_axis=(0.2, -1.0, 0.13))),
        surface_geo=surface(ramp_x, z0=-8.0, z1=8.0, nz=16))

    # ---- 4.6 FINALIZE: the override cascade, and the instancing floor.

    # CA - SWAP: an override re-points every panel to `gate` WITHOUT touching
    # the style (3.4). Ids identical to CB's; possible because the module is
    # not part of the address (D1).
    ov = hou.Geometry()
    P.write_override(ov, module="panel", to_module="gate")
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="CA")
    built["CA_swap_module"] = _case(g, kit_geo, panel_style(), overrides=ov)

    # CC - REPLACE: one element, keyed by `pc_elem_id`, becomes a
    # 2 x 2 x 0.4 m hero slab no kit contains - the built bbox answers "did
    # it arrive", not the attribute.
    hero = hou.Geometry()
    K.box_mesh(hero, 0.0, 2.0, 0.0, 2.0, -0.2, 0.2, 1)
    ov2 = hou.Geometry()
    P.write_override(ov2, elem_id="CC|0|default|3|rail", hero=hero)
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="CC")
    built["CC_replace_hero"] = _case(g, kit_geo, panel_style(), overrides=ov2)

    # CD - A REPLACE ON A DEFORMED PIECE: hero geometry cannot follow a bend
    # (D58), so this must WARN rather than silently straighten the run.
    ov3 = hou.Geometry()
    P.write_override(ov3, elem_id="CD|0|default|5|corner", hero=hero)
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 11)], curve_id="CD")
    built["CD_replace_bent"] = _case(g, kit_geo, corner_style("bend"),
                                     overrides=ov3)

    # CE - THE INSTANCING FLOOR: a straight run of RIGID modules must be
    # 100 % packed - the one number an unpack-everything builder fails.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (25, 0, 0)], curve_id="CE")
    built["CE_all_packed"] = _case(g, rigid_kit(), Style(
        "rigid", 1, 6, rules=[Rule("default", "first", ["beam"])],
        params=Params(fill="adaptive")))

    # ---- cycle 5: review measurements turned standing assertions
    # (tests/README.md's rule); each names its defect.

    # CF - A RESAMPLED STRAIGHT LINE IS STILL STRAIGHT (D69): CE's 25 m run
    # at 1 m spacing (the citygen street shape). Pre-fix: the two-point line
    # built 1000/1000 packed, this one 0/1000. In ALL_PACKED.
    g = hou.Geometry()
    polyline(g, [(float(x), 0.0, 0.0) for x in range(26)], curve_id="CF")
    built["CF_resampled_straight"] = _case(g, rigid_kit(), Style(
        "rigid", 1, 6, rules=[Rule("default", "first", ["beam"])],
        params=Params(fill="adaptive")))

    # CH - A SWAP ONTO A TILE REMAINDER (D73): the old code kept the gate's
    # slice fraction and cut the RIGID post at 0.125 of ITS 0.12 m - a
    # silent 0.185 m hole with `warn_counts` empty. The remainder now takes
    # D11's other answer (whole module scaled into the span) and warns;
    # asserts both `pc_warn_tile_fallback` and an intact run.
    ov = hou.Geometry()
    P.write_override(ov, module="gate", to_module="post")
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (5, 0, 0)], curve_id="CH")
    built["CH_swap_tile_slice"] = _case(g, kit_geo, Style(
        "tile", 1, 4, rules=[Rule("default", "first", ["gate"])],
        params=Params(fill="tile")), overrides=ov)

    # CI - A SWAP RE-DERIVES THE Z-MODE (D73): panel -> post on a slope used
    # to stamp every post `vertical` (the departed module's default).
    # `zmode_stamp` asserts it; the SLOPE makes the wrong mode geometric.
    ov = hou.Geometry()
    P.write_override(ov, module="panel", to_module="post")
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (10, 2.5, 0)], curve_id="CI")
    built["CI_swap_zmode"] = _case(g, kit_geo, Style(
        "swapz", 1, 4, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive")), overrides=ov)

    # CJ - A BEND BUTT JOINT AT 120 DEGREES: the allowance is h*sin(turn/2),
    # and at 90 degrees sin and cos agree - only this case separates them.
    # Correct allowance 0.025981 m, the old `cos` one 0.015 m: a legitimate
    # joint failed by 1.10e-02 m.
    g = hou.Geometry()
    ang = math.radians(120.0)
    polyline(g, [(0, 0, 0), (4, 0, 0),
                 (4 + 4 * math.cos(ang), 0, 4 * math.sin(ang))],
             curve_id="CJ")
    built["CJ_bend_butt_120"] = _case(g, kit_geo, corner_style("bend"))

    # ---- and 4.5's four, all of them measured on the built fence.

    # BJ - GROUND UNDER A BRIDGE DECK (D70): the drop takes the NEAREST
    # surface, ties go down-axis. The first version took the FIRST (topmost)
    # hit and put six of ten pieces on the deck with two 3.9 m cliff pieces.
    # `no_gaps_or_overlaps` and `conform_contact_m` see it.
    both = hou.Geometry()
    both.merge(surface(lambda x, z: -2.0, x0=-4.0, x1=24.0, nx=28))
    both.merge(surface(lambda x, z: 2.0, x0=4.0, x1=16.0, nx=12))
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="BJ")
    built["BJ_conform_deck"] = _case(g, kit_geo, panel_style(zmode="vertical"),
                                     surface_geo=both)

    # BK - A SMALL SURFACE FAR BELOW THE SPLINE (D70): reach came from the
    # surface bbox alone, so a 5 x 5 m prop was unreachable from 30 m up.
    # `conform_misses` pinned at 0; the run must sit on the prop.
    g = hou.Geometry()
    polyline(g, [(1.0, 30.0, 0.0), (4.0, 30.0, 0.0)], curve_id="BK")
    built["BK_conform_far"] = _case(
        g, kit_geo, panel_style(zmode="vertical"),
        surface_geo=surface(lambda x, z: 0.0, x0=0.0, x1=5.0, z0=-2.5, z1=2.5,
                            nx=5, nz=5))

    # BL - A BUMP NARROWER THAN THE OLD PROBE SPACING (D71): 0.3 m wide,
    # 0.5 m tall at x = 0.75 - between the five fixed samples, ON a 0.25 m
    # station. The panel shipped PACKED with the bump 0.400 m through its
    # bottom edge, unwarned. `conform_drape_m` scores every station.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="BL")
    built["BL_conform_bump"] = _case(g, kit_geo,
                                     panel_style(zmode="vertical"),
                                     surface_geo=surface(bump, x0=-1.0,
                                                         x1=21.0, nx=440))

    # BM - A HOLE ON A DEFORM STATION (D71): the 0.1 m hole at x = 0.70..0.80
    # missed the five fixed probes and hit the 0.75 station - a 0.1875 m
    # V-notch with `pc_warn_conform_miss` absent (D53's contract broken). The
    # warning is the assertion; the notch is D53's documented behaviour.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="BM")
    nx = 220
    cell = 22.0 / nx
    holed = set((i, j) for i in range(nx) for j in range(12)
                if (-1.0 + (i + 1) * cell) > 0.70 and (-1.0 + i * cell) < 0.80)
    built["BM_conform_station_hole"] = _case(
        g, kit_geo, panel_style(zmode="vertical"),
        surface_geo=surface(ramp_x, x0=-1.0, x1=21.0, nx=nx, holes=holed))

    # BN - A SURFACE OVERHEAD, NEARER THAN THE ONE BELOW (D70): deck 0.4 m
    # up, ground 3 m down - the NEAREST hit puts the fence ON THE DECK.
    # Written because a mutation survived: BJ_conform_deck's deck and ground
    # are EQUIDISTANT, so the tie-break decides (the up-axis cast won 12 405
    # times suite-wide, all with nothing below). STEPPED POSTS so the answer
    # is a NUMBER: `stepped_riser_m` records the 3.4 m step at the deck edge.
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

    # BO - A DEBUG CURVE MERGED INTO THE TERRAIN (the C4 audit's F1). Three
    # open POLYLINES 0.5 m over a ramp, which is what a citygen graph hands
    # polyChain when curves and terrain share a merge. The reference will not
    # hit a zero-area primitive (`tolerance = 1e-6`); VEX's `intersect()` has
    # no tolerance and hits a few mm off the line, so `Stage = output` built a
    # fence 2.5 m away (the audit's own repro: 1.7042 m on a hill) with both
    # guard levels reading 1. Level 1 refuses it
    # now (`_surface_is_droppable`) and `output_guard_parity` is the check -
    # this case is the ONLY one in the suite whose surface is not all closed
    # polygons, and `gen_cases._sheet` cannot build one.
    # ⚠️ AND THE GEOMETRY IS THE FIXTURE, not decoration - TWO placements of
    # this case reddened nothing before this one, and both failures are the
    # same question ("what can this fixture NOT reach?") asked of a drop:
    #   * the ground has to be BELOW the run and the polyline BETWEEN them, or
    #     the ground wins the nearest-hit on both sides and there is nothing to
    #     disagree about;
    #   * and the run has to pass NEAR the line rather than ALONG it. Measured
    #     on this very surface: a query EXACTLY on a polyline is hit by both
    #     implementations (and by the `ray` verb - 0 of 54 disagree in the
    #     audit's own sweep), a query 0.05 m off is hit by neither, and 0.005 m
    #     off is hit by VEX alone. So the run is 5 mm to the side of the middle
    #     line - a debug curve laid ALONGSIDE the fence, which is what a
    #     citygen graph actually contains.
    strays = hou.Geometry()
    strays.merge(surface(lambda x, _z: -2.0 - CONFORM_GRADE * x))
    for j in range(3):
        polyline(strays, [(-8.0 + 3.0 * i, 0.5, -3.0 + 3.0 * j)
                          for i in range(11)])
    g = hou.Geometry()
    polyline(g, [(0, 0, 0.005), (20, 0, 0.005)], curve_id="BO")
    built["BO_conform_strays"] = _case(
        g, kit_geo,
        Style("strays", 1, 3, rules=[Rule("default", "first", ["panel"])],
              params=Params(fill="adaptive", zmode="adaptive")),
        surface_geo=strays)

    # BP/BQ - A +-Z DROP ONTO A WALL (the C4 audit's F3), the same straight
    # 20 m run twice, one wall parm apart. The spline is DEAD STRAIGHT, so
    # `pc_frames_transportable` has no kink to sample and its conformed
    # STATIONS are the only thing that can refuse a piece:
    #   BP a gentle wall - every piece transportable, the build is NATIVE, and
    #      it is the suite's only native +-Z conform;
    #   BQ a 0.6 m bump at the CENTRE of every 2 m piece, steep enough that
    #      the conformed tangent reverses inside the piece while both of its
    #      ENDS still point down the run. That is the header's own "a dead
    #      straight span over an overhanging crest reverses with no kink", as
    #      geometry. Shipped: 10 planned, 0 built, level 2 refuses, the
    #      reference ships. With the station loop deleted: 10 built, level 2
    #      ADMITS, and `output_guard_parity` goes red.
    for name, fn in (
            ("BP_conform_wall",
             lambda x: -4.0 + 0.6 * math.sin(0.35 * x)),
            ("BQ_conform_wall_bumps",
             lambda x: -4.0 + 0.6 * math.exp(-((x % 2.0 - 1.0) ** 2)
                                             / (2 * 0.15 ** 2)))):
        g = hou.Geometry()
        polyline(g, [(float(x), 0.0, 0.0) for x in range(21)],
                 curve_id=name[:2])
        built[name] = _case(g, kit_geo, Style(
            "wall", 1, 3, rules=[Rule("default", "first", ["panel"])],
            params=Params(fill="adaptive", zmode="adaptive",
                          conform_axis=(0.0, 0.0, -1.0))),
            surface_geo=wall(fn))

    # CG - A RESAMPLED STRAIGHT LINE, BENDABLE MODULE (D69): CF's rigid beam
    # short-circuits `_needs_deform` at D27, so CF cannot see D69. Measured
    # revert: CF and the 67-case suite stayed green while PC-G3's 20 km run
    # went 10 005 packed / 0.60 s to 0 packed / 360 180 points / 21.9 s.
    # In ALL_PACKED.
    g = hou.Geometry()
    polyline(g, [(float(x), 0.0, 0.0) for x in range(21)], curve_id="CG")
    built["CG_resampled_bendable"] = _case(g, kit_geo, panel_style())

    # ---- cycle 7 / D75: THE CURVATURE BUDGET, across radii - resampled
    # ARCs, the citygen street shape. Pre-budget (measured: R = 12 000 m
    # unpacked 8/150 pieces for 4.2e-05 m and over_unpacked FAILED). One case
    # per decade of radius, plus the control that must still bend.
    for cid, radius in (("CK_arc_12000", 12000.0), ("CL_arc_2000", 2000.0),
                        ("CM_arc_80", 80.0), ("CN_arc_tight", 10.0)):
        g = hou.Geometry()
        polyline(g, arc_points(radius), curve_id=cid.split("_")[0])
        built[cid] = _case(g, kit_geo, panel_style())

    # ---- cycle 8 / D87: THE BUDGET IS SPENT BY POINTS, NOT THE SPINE. A
    # 1.2 m rail on an R = 55 m climbing arc: spine sagitta 0.0091 m (inside
    # `bend_tol`) yet top corners really moved 0.0327 m, 3.3x the budget. CP
    # reads it; CQ (plan arc) is the control allowed to stay packed.
    # ---- cycle 8 / D94: `attr:<name>` read exactly two attrs because
    # nothing harvested them. Two curves with different `road_width`s (wide
    # gets gates, narrow panels), proving the attribute is read PER PRIM.
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

    # DL - the only case in the suite whose modules carry a `pc_variant`.
    # Standing finding (10) again: `stamp_provenance` can only assert
    # `pc_variant` where one exists, and until this nothing authored one.
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="DL")
    built["DL_variant_kit"] = _case(g, variant_kit(), Style(
        "variant", 1, 7,
        rules=[Rule("default", "sequence", ["post", "panel"]),
               Rule("start", "first", ["post"]),
               Rule("end", "first", ["post"])],
        params=Params(fill="adaptive")))

    # DM - 13.9 N5's OWN COVERAGE: `place_deformed_covers_the_reference` was
    # comparing ~one element over 92 cases (every hilly fixture is out of
    # scope: corner, surface, fillet or flatten). A smooth 24 m ripple with
    # none - level 1 admits it, most of the run unpacks; same shape as
    # `gate_images` and `piece_order_key_is_total` use.
    g = hou.Geometry()
    polyline(g, [(0.5 * i, 0.45 * math.sin(i * 0.55), 0.0)
                 for i in range(49)], curve_id="DM")
    built["DM_ripple_deformed"] = _case(g, kit_geo,
                                        panel_style(zmode="adaptive"))

    return built
















def rebuild(case):
    """Cook the same inputs again into fresh geometry - the determinism check."""
    out, report = P.build(case["curve"], case["kit"], case["style"],
                          surface_geo=case.get("surface"),
                          overrides=case.get("overrides"))
    return (out, report)


# --- 11.2's tripwire fixtures ----------------------------------------------
# Not scene cases: no geometry assertion, only the port plan's measurements
# (checks.py, "11.2's own tripwires").

def tripwire_packed_run():
    """200 x 2 m panels on a 400 m straight - PC-G3's shape, small enough to
    run inside the scene suite. 100 % packed, so the stamp is the packed
    writer's 14 `Prim.setAttribValue` calls per piece and nothing else."""
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (400, 0, 0)], curve_id="TW")
    return P.build(g, K.starter_kit(), Style(
        "tripwire", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive")))


def tripwire_deformed_run():
    """The same panels on a 10 m arc - 100 % DEFORMED (`arc_10` in miniature:
    5.0e-02 m sagitta per span, 5x `bend_tol`). The deformed branch is where
    a per-prim stamp costs 14 x the PRIM COUNT: restoring the D102-era writer
    was 8.4x wall-clock (2.361 -> 19.854 s) with the packed tripwire unmoved.
    """
    g = hou.Geometry()
    r, n = 10.0, 60
    polyline(g, [(r * math.sin(i / r), 0.0, r * (1.0 - math.cos(i / r)))
                 for i in range(n + 1)], curve_id="TWD")
    return P.build(g, K.starter_kit(), Style(
        "tripwire", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", zmode="adaptive")))


def tripwire_out_build(out):
    """`tripwire_packed_run`'s fence, built INTO a caller-supplied geometry -
    `build`'s `out=` parameter, which nothing else in the tree passes."""
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="TW")
    return P.build(g, K.starter_kit(), Style(
        "tripwire", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive")), out=out)


def tripwire_mitered_run():
    """A closed rectangle in MITER mode - the only branch reaching
    `clip_plane`, so `prims_wrappers_built` can see `len(cut.prims())`
    (unreachable from the corner-less packed/deformed/conformed fixtures)."""
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (12, 0, 0), (12, 0, 8), (0, 0, 8)],
             closed=True, curve_id="TWM")
    return P.build(g, K.starter_kit(), Style(
        "tripwire", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", corner_mode="miter")))


def tripwire_conformed_run():
    """The same run draped over a surface - one `ConformPath`, so its memo
    cache is measurable per placed element."""
    g = hou.Geometry()
    polyline(g, [(0, 0, 0), (20, 0, 0)], curve_id="TW")
    return P.build(g, K.starter_kit(), fence_style(),
                   surface_geo=surface(ramp_x))


def heightfield(cell, amp, wave, x0, x1, z0, z1):
    """A quad heightfield, `cell` m per quad, `y = amp*sin(kx)*sin(kz)`. The
    conformed terrain at fixture size."""
    geo = hou.Geometry()
    nx = int(round((x1 - x0) / cell))
    nz = int(round((z1 - z0) / cell))
    k = 2.0 * math.pi / wave
    pts = {}
    for i in range(nx + 1):
        x = x0 + cell * i
        for j in range(nz + 1):
            z = z0 + cell * j
            pt = geo.createPoint()
            pt.setPosition((x, amp * math.sin(k * x) * math.sin(k * z), z))
            pts[(i, j)] = pt
    for i in range(nx):
        for j in range(nz):
            poly = geo.createPolygon()
            for pt in (pts[(i, j)], pts[(i, j + 1)],
                       pts[(i + 1, j + 1)], pts[(i + 1, j)]):
                poly.addVertex(pt)
    return geo


def tripwire_streets_conformed():
    """40 x 20 m conformed runs - MANY SHORT CURVES over gentle terrain, the
    citygen shape a single long curve cannot stand in for.

    `ray` rebuilds its surface input per execution: per-curve batching was
    0.94x (SLOWER than none) on 300 x 60 m streets, per-build 1.20-1.39x.
    This run is 87 % PACKED, so deformed-piece gap midpoints are dead weight
    on it."""
    g = hou.Geometry()
    for i in range(40):
        r, c = divmod(i, 8)
        polyline(g, [(c * 22.0, 40.0, r * 6.0), (c * 22.0 + 20.0, 40.0, r * 6.0)],
                 curve_id="TWS%02d" % i)
    return P.build(g, K.starter_kit(), Style(
        "tripwire", 1, 3, rules=[Rule("default", "first", ["panel"])],
        params=Params(fill="adaptive", zmode="adaptive")),
        surface_geo=heightfield(10.0, 2.0, 120.0, -10.0, 190.0, -10.0, 40.0))
