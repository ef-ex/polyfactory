"""polyChain 7.1 ARRAY2D - the row stack. No `hou`, and no second solve.

THE ONE SENTENCE (7): *a row is a phase-1 `Curve`, the row list is a phase-1
plan run on the Y axis, and all N rows go through ONE `place.build` call as one
curve stream.* Everything in this file is a consequence of it.

So there is no fitting maths here at all. The Y solve is `decompose.decompose`
+ `plan.plan_sections` on a vertical curve, which is why `fit`, `evenly`,
`justify`, `adjust_to_end`, D13's overflow cascade and D17's degenerate-pad
guard are already correct on Y - they are correct on any 1D length, and a
stack of storeys is a 1D length. RailClone's own documented wart, *"At present
Adaptive mode only functions on the X axis, the Y axis will be clipped as
though the mode is set to Tile"*, does not survive here for that reason
(D114).

WHAT THIS MODULE OWNS

  * the Y solve and the row list (`plan_rows`), including 7.2.1's Y-axis
    precedence (`y_class`);
  * D124's canonical footprint, so `pc_elem_id` survives re-authoring;
  * D118's role closure - the 5 x 5 lattice walk, done ONCE as data expansion
    of `Module.roles` at kit read, so the kernel never grows a branch for it;
  * 7.6's clipped area, reduced to the only part a facade panel needs: the
    array's local frame and the per-row span inside the boundary.

WHAT IT DELIBERATELY DOES NOT OWN: geometry. The adapter (`facade.py`) turns
the rows into one `hou.Geometry` with bulk array writes and makes the single
`place.build` call. This file runs with no Houdini imported, in milliseconds,
exactly like `plan.py`.

DECISIONS TAKEN HERE (recorded in polychain.md 12):

  D132 THE Y SOLVE RUNS ON A TRANSPOSED KIT. The 1D solver fits on
       `Module.length`, which is `pc_size.x`; a storey's nominal length is its
       HEIGHT, which is `pc_size.y` (7.3.1 promotes it to load-bearing). So
       the Y solve is handed the same modules with x and y swapped - DATA, not
       a fork - and `pc_row_scale` falls out of the same solve as
       band / nominal height. `pc_pad` is not swapped: 7.3.1 says the same two
       numbers are read as (left, right) on X and (bottom, top) on Y.
  D134 A Y `corner` CLASS IS A PROFILE VERTEX, and it is named on the plan
       rather than solved for. 4.3's corner machinery places a corner MODULE
       at a vertex in world space; a string course is not that - it is the
       BAND that starts at the setback, so the row whose band starts on a
       profile corner is the `corner` row. No second solve (D130), and the
       whole of 7.2.1's Y order is `y_class`, eight lines.
  D135 A ROW IS NEVER SLICED. A `tile` Y fill whose remainder would be cut
       gives a SCALED row instead: half a storey is a defect, a storey 4 %
       short is a choice - D11's own argument, on the other axis.
  D137 THE CLIP IS A SPAN, NOT A CULL. 7.6's cost discipline says the clip
       test runs on the plan before geometry exists; taken literally that is
       better than culling pieces, because the row's own span can be trimmed
       to the boundary and then the fill exactly fills what is left. A
       rectangle is the identity case; a taper narrows every row and no piece
       is ever built outside the line. `slice` (a piece cut on the boundary)
       is P2-7 and is not here.
"""

import math

from . import (DEFAULTS, EPS, POS_EPS, ROLES_2D, WARN_ROLE_FALLBACK, Curve,
               Kit, Module, Style, canonical_role, role_2d, split_role)
from . import decompose as _decompose
from . import plan as _plan


# --- the kit, on the other axis (D132) --------------------------------------

def transpose_kit(kit):
    """The same modules, fitted on their HEIGHT. Data, not a second solver."""
    mods = []
    for m in kit.modules:
        mods.append(Module(m.name, (m.size[1], m.size[0], m.size[2]),
                           pad=m.pad, deform=m.deform, zmode=m.zmode,
                           roles=m.roles, variant=m.variant, weight=m.weight,
                           tilt=m.tilt, extend=m.extend))
    return Kit(kit.kit_id, kit.version, mods, kit.human_scale_reference,
               kit.role_fallbacks)


# --- 7.2.2: the role lattice, closed at kit read (D118 / E3) ----------------

def fallback_chain(role, extend="x"):
    """The ordered walk for a missing cell, 7.2.2.

    `<x>_<y>` -> drop the Y class -> drop the X class -> `default`.

    **Y sheds first, and that is the whole argument.** A cell's X class is what
    makes it CLOSE: a `corner` piece is authored to mate at the bisector plane,
    and dropping its corner-ness leaves a hole at the corner - a PC-G5 failure.
    A cell's Y class is what makes it READ: a `top` piece is a cornice profile,
    and dropping its top-ness leaves a facade that is merely plain. Closure
    beats cosmetics.

    `extend` is 7.2.1's Extend To Side, and it is a tie-break for ABSENCE
    only: `x` (this class extends to the side, cutting the other axis' band)
    keeps X, `y` keeps Y, which swaps steps 2 and 3.
    """
    x, y = split_role(canonical_role(role))
    exact = role_2d(x, y)
    keep_x = role_2d(x, "default")
    keep_y = role_2d("default", y)
    chain = [exact]
    for step in ((keep_x, keep_y) if extend != "y" else (keep_y, keep_x)):
        if step not in chain:
            chain.append(step)
    if "default" not in chain:
        chain.append("default")
    return chain


def close_roles(kit, extend="x", extra_roles=(), extend_by_slot=None):
    """(kit, {role asked: role supplied}) - E3, pure data expansion.

    Every cell role the 5 x 5 lattice can name is resolved ONCE here and added
    to the `roles` tuple of whichever module ends up serving it, so plain
    `Kit.by_role` finds it and `plan.candidates` is untouched. That is the
    whole of D118: a lattice walk performed as data at read time, never as a
    branch in the kernel.

    A role the walk cannot satisfy at all is still recorded - with an empty
    supplier - because 3.4's blank stand-in box is what will arrive and PC-G5
    condition 5 counts a stand-in that did not say so.

    `extend_by_slot` is the per-X-class `pc_extend` (7.3.1): a module carrying
    `pc_extend = 0` says "this column STOPS at the cornice", which reverses
    its own fallback walk and nothing else's.
    """
    declared = {}
    by_slot = {}
    for m in kit.modules:
        for r in m.roles:
            role = canonical_role(r)
            declared.setdefault(role, []).append(m)
            if m.extend >= 0:
                by_slot.setdefault(split_role(role)[0],
                                   "x" if m.extend else "y")
    by_slot.update(dict(extend_by_slot or {}))
    extend_by_slot = by_slot
    add = {}
    fallbacks = {}
    wanted = list(ROLES_2D) + [canonical_role(r) for r in extra_roles]
    for role in wanted:
        if role in declared:
            continue
        x, _y = split_role(role)
        chain = fallback_chain(role, extend_by_slot.get(x, extend))
        supplier = ""
        for step in chain[1:]:
            if step in declared:
                supplier = step
                break
        fallbacks[role] = supplier
        for m in declared.get(supplier, ()):
            add.setdefault(m.name, []).append(role)
    if not add and not fallbacks:
        return (kit, {})
    mods = []
    for m in kit.modules:
        extra = add.get(m.name)
        if not extra:
            mods.append(m)
            continue
        mods.append(Module(m.name, m.size, pad=m.pad, deform=m.deform,
                           zmode=m.zmode,
                           roles=tuple(m.roles) + tuple(sorted(set(extra))),
                           variant=m.variant, weight=m.weight, tilt=m.tilt,
                           extend=m.extend))
    out = Kit(kit.kit_id, kit.version, mods, kit.human_scale_reference,
              fallbacks)
    return (out, fallbacks)


def fallback_lines(fallbacks):
    """7.2.2's "naming both roles", as persistable strings."""
    out = []
    for role in sorted(fallbacks):
        got = fallbacks[role]
        out.append("pc_warn_role_fallback: cell %r -> %s"
                   % (role, ("module role %r" % got) if got
                      else "3.4 stand-in box (no role on the lattice)"))
    return out


# --- 7.3.2: one payload, two axes (D120) ------------------------------------

def split_style(style, y_params=None):
    """(X `Style`, Y `Style`) off one payload. `Style` itself is unchanged.

    Rules with `pc_axis = y` drive the row stack, everything else drives the
    fill - so a phase-1 payload, which says nothing about an axis, is a valid
    phase-2 X payload and produces a Y style with no rules (i.e. one storey
    of `default`, which is exactly what a 1D run is).
    """
    x_rules = [r for r in style.rules if r.axis != "y"]
    y_rules = [r for r in style.rules if r.axis == "y"]
    meta = dict(getattr(style, "meta", None) or {})
    x = Style(style.style_id, style.version, style.seed, x_rules, style.params,
              meta)
    y = Style(style.style_id, style.version, style.seed, y_rules,
              y_params or style.params, meta)
    return (x, y)


# --- 7.1: the Y solve -------------------------------------------------------

def vertical_profile(height, array_id="A"):
    """The synthetic Y curve: a two-point line of the requested height."""
    return Curve("%s#Y" % array_id, [(0.0, 0.0, 0.0), (0.0, float(height), 0.0)])


class Row(object):
    """ONE row of the stack: a band, a Y class, and what fills the band.

    `s0`/`s1` are metres along the Y PROFILE (which is the height itself when
    the profile is vertical); `y0`/`y1` are heights and `off0`/`off1` the
    profile's off-axis coordinate, which is D128's outward plan offset - read
    here so P2-8 has it, applied by nothing yet.
    """

    __slots__ = ("index", "s0", "s1", "y0", "y1", "off0", "off1", "yclass",
                 "module", "scale", "warns", "array_id")

    def __init__(self, index, s0, s1, y0, y1, off0, off1, yclass, module,
                 scale=1.0, warns=(), array_id="A"):
        self.index = int(index)
        self.s0, self.s1 = float(s0), float(s1)
        self.y0, self.y1 = float(y0), float(y1)
        self.off0, self.off1 = float(off0), float(off1)
        self.yclass = yclass
        self.module = module
        self.scale = float(scale)
        self.warns = tuple(warns)
        self.array_id = array_id

    @property
    def height(self):
        return self.y1 - self.y0

    @property
    def curve_id(self):
        """7.3.3 - the row half of the 4D address: `<arrayId>#<row>`."""
        return "%s#%d" % (self.array_id, self.index)

    def as_dict(self):
        return {"pc_row": self.index, "pc_curve_id": self.curve_id,
                "pc_yclass": self.yclass, "pc_row_y0": self.y0,
                "pc_row_y1": self.y1, "pc_row_scale": self.scale,
                "module": self.module, "height": self.height,
                "warns": list(self.warns)}

    def __repr__(self):
        return "Row(%d %s %.4f..%.4f m x%.4f)" % (
            self.index, self.yclass, self.y0, self.y1, self.scale)


def y_class(slot, s0, corner_s, tol=1e-6):
    """7.2.1's Y precedence, in its documented order (D134).

    `start`/`end` (the array's bottom and top rows - these ARE the Y run's
    caps, which is why they carry the names and the `bottom`/`top` aliases)
    **>** `corner` (a profile vertex: a setback line, a string course)
    **>** `marker:<id>` **>** `evenly` **>** `default`.
    """
    if slot in ("start", "end"):
        return slot
    for c in corner_s:
        if abs(s0 - c) <= tol:
            return "corner"
    return slot


def plan_rows(profile, kit, y_style, y_params=None, array_id="A"):
    """[Row] for one array. `profile` is a height in metres or a `Curve`.

    A `Curve` is authored in the PROFILE plane - the along-axis coordinate is
    height and the off-axis one is D128's outward plan offset - and the solve
    runs on its arc length, exactly as the X solve runs on the footprint's.
    A vertical profile makes the two the same number.
    """
    if not isinstance(profile, Curve):
        profile = vertical_profile(profile, array_id)
    params = y_params or (y_style.params if y_style is not None else None) \
        or DEFAULTS
    tkit = transpose_kit(kit)
    sections = _decompose.decompose(profile, [], params)
    if not sections:
        return []
    by_index = dict((s.index, s) for s in sections)
    corner_s = [s.s0 for s in sections if s.start_corner is not None]
    placements = _plan.plan_sections(sections, tkit, y_style, params)

    bands = []
    for p in placements:
        sec = by_index.get(p.section_index)
        if sec is None:
            continue
        bands.append((sec.s0 + p.s0, sec.s0 + p.s1, p))
    bands.sort(key=lambda b: (b[0], b[1]))

    if not bands:
        # Warn-never-block, and the compatibility claim made literal: a
        # payload with NO Y rules is a phase-1 payload, and a phase-1 payload
        # is ONE row spanning the whole height with no Y class at all - i.e. a
        # 1D run. Nothing downstream branches on it: a blank `yclass` is what
        # makes `cell_role` the identity and `classify` a no-op.
        total = profile.length
        pos1 = profile.sample(total, forward=False)[0]
        return [Row(0, 0.0, total, profile.sample(0.0)[0][1], pos1[1],
                    profile.sample(0.0)[0][0], pos1[0], "", "", 1.0, (),
                    array_id)]

    rows = []
    for i, (s0, s1, p) in enumerate(bands):
        pos0 = profile.sample(s0)[0]
        pos1 = profile.sample(s1, forward=False)[0]
        mod = tkit.by_name(p.module)
        nominal = mod.length if mod is not None else (s1 - s0)
        # D135 - a sliced Y placement becomes a SCALED row. The band is the
        # truth and the module is scaled into it; nothing is ever cut on Y.
        scale = ((s1 - s0) / nominal) if nominal > EPS else 1.0
        rows.append(Row(i, s0, s1, pos0[1], pos1[1], pos0[0], pos1[0],
                        y_class(p.slot, s0, corner_s), p.module, scale,
                        p.warns, array_id))
    return rows


def classify(placements, kit, yclass):
    """Stamp the 2D half of every placement of ONE row, and warn D118's walk.

    ONE site, deliberately: `corner.plan_curve` builds the corner assembly's
    placements itself and never passes through `plan._module_warns`, so a
    fallback warning written in the fill path would have been silent on
    exactly the cell PC-G5 cares most about (a corner column meeting the
    cornice). Every placement of the row is here, whatever built it.
    """
    if not yclass:
        return placements
    for p in placements:
        p.yclass = yclass
        p.cell = role_2d(p.slot, yclass)
        if p.cell in kit.role_fallbacks and WARN_ROLE_FALLBACK not in p.warns:
            p.warns = tuple(p.warns) + (WARN_ROLE_FALLBACK,)
    return placements


# --- D124: the canonical footprint ------------------------------------------

def _signed_area_xz(points):
    """2 x the signed plan area. ONE fixed winding is all that is required."""
    a = 0.0
    n = len(points)
    for i in range(n):
        x0, _y0, z0 = points[i]
        x1, _y1, z1 = points[(i + 1) % n]
        a += x0 * z1 - x1 * z0
    return a


def canonical_loop(points, closed=True, ndigits=3):
    """D124 - a closed footprint, emitted so its ids survive re-authoring.

    Phase 1 numbers sections from point 0 in the authored direction, so on a
    closed footprint rotating the start vertex or reversing the spline
    renumbers every face and moves every `pc_elem_id` - exactly what
    citygen_buildings 12.7 forbids, and something phase 1 never had to face
    because its closed cases are authored once.

    So the row emitter emits canonical: ONE winding (fixed by the sign of the
    plan area) and a start vertex fixed by the geometry (the smallest
    mm-rounded position, ties broken by the whole rotated sequence, so two
    coincident-rounded vertices cannot make the answer depend on input order).
    Done at emission, OUTSIDE the kernel, so not one phase-1 baseline moves.
    """
    pts = [tuple(float(c) for c in p) for p in points]
    if not closed or len(pts) < 3:
        return pts
    if _dist(pts[0], pts[-1]) <= POS_EPS:
        pts.pop()
    if _signed_area_xz(pts) < 0.0:
        pts.reverse()
    keys = [tuple(round(c, ndigits) for c in p) for p in pts]
    n = len(pts)
    best = min(range(n), key=lambda i: keys[i:] + keys[:i])
    return pts[best:] + pts[:best]


def _dist(a, b):
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(3)))


def row_loops(footprint, rows, closed=True, canonical=True):
    """[(points, closed, attrs)] - one entry per row, ready for the adapter.

    The whole 7.1 per-row contract in one place: the polyline, translated to
    the band's datum, plus the six prim attributes the kernel is handed. Five
    of the six are already harvested onto `Section.attrs` by D94, so they
    reach the fill rules as `attr:<name>` subjects with no adapter change.
    """
    base = canonical_loop(footprint, closed) if canonical else \
        [tuple(float(c) for c in p) for p in footprint]
    out = []
    for row in rows:
        pts = [(p[0], p[1] + row.y0, p[2]) for p in base]
        out.append((pts, closed, row.as_dict()))
    return out


# --- 7.6: the clipped area, reduced to what a facade panel needs (D137) -----

def _cross3(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit3(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])
    return (0.0, 0.0, 0.0) if n < EPS else (v[0] / n, v[1] / n, v[2] / n)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class AreaFrame(object):
    """A closed sub-spline's own plane, as a frame plus 2-D extents.

    7.6's "Extend X/Y Size to Area": the array's extents come from the closed
    spline instead of from a footprint and a height. `auto_align` is RC's own
    parm with D20's axis translation applied - RC is Z-up, we are Y-up, so its
    "keep +X parallel to the world XY plane" is *keep +X horizontal* here, and
    both spellings are accepted.
    """

    __slots__ = ("origin", "ex", "ey", "ez", "width", "height", "poly")

    def __init__(self, origin, ex, ey, ez, width, height, poly):
        self.origin = origin
        self.ex, self.ey, self.ez = ex, ey, ez
        self.width, self.height = width, height
        self.poly = poly            # the boundary, in frame 2-D coordinates

    def world(self, x, y):
        o, ex, ey = self.origin, self.ex, self.ey
        return (o[0] + ex[0] * x + ey[0] * y,
                o[1] + ex[1] * x + ey[1] * y,
                o[2] + ex[2] * x + ey[2] * y)

    def local(self, p):
        d = (p[0] - self.origin[0], p[1] - self.origin[1],
             p[2] - self.origin[2])
        return (_dot(d, self.ex), _dot(d, self.ey))


def _newell(points):
    n = [0.0, 0.0, 0.0]
    m = len(points)
    for i in range(m):
        a, b = points[i], points[(i + 1) % m]
        n[0] += (a[1] - b[1]) * (a[2] + b[2])
        n[1] += (a[2] - b[2]) * (a[0] + b[0])
        n[2] += (a[0] - b[0]) * (a[1] + b[1])
    return _unit3(tuple(n))


def area_frame(points, auto_align="to_spline", expand=0.0):
    """A closed planar spline -> `AreaFrame`. Never raises."""
    pts = [tuple(float(c) for c in p) for p in points]
    if len(pts) > 1 and _dist(pts[0], pts[-1]) <= POS_EPS:
        pts.pop()
    ez = _newell(pts) if len(pts) >= 3 else (0.0, 0.0, 1.0)
    if ez == (0.0, 0.0, 0.0):
        ez = (0.0, 0.0, 1.0)
    ex = None
    if auto_align in ("x_xy", "x_horizontal"):
        ex = _unit3(_cross3((0.0, 1.0, 0.0), ez))
    if not ex or ex == (0.0, 0.0, 0.0):     # `to_spline`, and the degenerate
        ex = _unit3((pts[1][0] - pts[0][0], pts[1][1] - pts[0][1],
                     pts[1][2] - pts[0][2])) if len(pts) > 1 else (1.0, 0.0, 0.0)
    ey = _unit3(_cross3(ez, ex))
    o = pts[0]
    flat = [(_dot((p[0] - o[0], p[1] - o[1], p[2] - o[2]), ex),
             _dot((p[0] - o[0], p[1] - o[1], p[2] - o[2]), ey)) for p in pts]
    x0 = min(f[0] for f in flat) - expand
    y0 = min(f[1] for f in flat) - expand
    x1 = max(f[0] for f in flat) + expand
    y1 = max(f[1] for f in flat) + expand
    origin = (o[0] + ex[0] * x0 + ey[0] * y0,
              o[1] + ex[1] * x0 + ey[1] * y0,
              o[2] + ex[2] * x0 + ey[2] * y0)
    poly = [(f[0] - x0, f[1] - y0) for f in flat]
    return AreaFrame(origin, ex, ey, ez, x1 - x0, y1 - y0, poly)


def scanline(poly, y):
    """[(x0, x1)] where the horizontal line `y` is inside `poly`."""
    xs = []
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        if (ay <= y < by) or (by <= y < ay):
            xs.append(ax + (bx - ax) * (y - ay) / (by - ay))
    xs.sort()
    return [(xs[i], xs[i + 1]) for i in range(0, len(xs) - 1, 2)]


def _intersect(a, b):
    out = []
    for (a0, a1) in a:
        for (b0, b1) in b:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo > EPS:
                out.append((lo, hi))
    return out


def row_spans(frame, row, mode="remove"):
    """The x intervals row `row` may occupy inside the boundary (D137).

    7.6's cost discipline, taken literally: the boundary test runs on the PLAN
    before geometry exists, and the cheapest place to apply it is the row's own
    span - so `remove` (nothing crosses the line) is the INTERSECTION of the
    scanlines at the band's bottom and top, `preserve` (a piece may overhang)
    is their union bounds, and nothing is ever built outside the line by
    either. On a rectangle both are the full width, which is why a rectangular
    facade panel needs none of this and still gets it for free.
    """
    if mode == "none" or not frame.poly:
        return [(0.0, frame.width)]
    lo = scanline(frame.poly, row.y0 + EPS)
    hi = scanline(frame.poly, row.y1 - EPS)
    if not lo or not hi:
        mid = scanline(frame.poly, 0.5 * (row.y0 + row.y1))
        return mid or []
    if mode == "preserve":
        return [(min(s[0] for s in lo + hi), max(s[1] for s in lo + hi))]
    return _intersect(lo, hi)


def area_rows(frame, rows, mode="remove"):
    """[(points, closed, attrs)] - the row curves of a clipped area.

    Each row is a straight OPEN polyline across the boundary at its own band
    datum, in world space. A row the boundary leaves nothing of is dropped,
    which is `remove` doing its job rather than an error.
    """
    out = []
    for row in rows:
        for k, (x0, x1) in enumerate(row_spans(frame, row, mode)):
            if x1 - x0 <= EPS:
                continue
            pts = [frame.world(x0, row.y0), frame.world(x1, row.y0)]
            attrs = row.as_dict()
            if k:
                attrs["pc_curve_id"] = "%s.%d" % (attrs["pc_curve_id"], k)
            out.append((pts, False, attrs))
    return out
