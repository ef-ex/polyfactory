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

from . import (CLIP_PRESERVE, CLIP_REMOVE, CLIP_SLICE, DEFAULTS, EPS, POS_EPS,
               ROLES_2D, SLOTS, UP, WARN_CLIP_CONVEX, WARN_CLIP_UNSLICEABLE,
               WARN_KIT_GAP, WARN_OVERFLOW, WARN_ROW_KIT_GAP,
               WARN_ROW_OVERFLOW, Curve, Kit, Module, Style, _is_slot,
               canonical_role, role_2d, split_role)
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
                           tilt=m.tilt, extend=m.extend, clip=m.clip))
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
    collisions = []
    dropped = {}
    for m in kit.modules:
        for r in m.roles:
            role = canonical_role(r)
            if role != r and role in declared:
                # 7.2's alias-collision rule: "an alias that resolves to a
                # role another module already claims warns and loses - first
                # module in payload order wins". Only an ALIAS loses; a module
                # that authors the role literally is a legitimate pool member,
                # which is what `random`/`pc_weight` selection by role is made
                # of, and dropping those would break phase 1's own variants.
                collisions.append(
                    "pc_warn_role_collision: module %r alias %r resolves to "
                    "cell %r, already claimed by %r - claim dropped"
                    % (m.name, r, role, declared[role][0].name))
                dropped.setdefault(m.name, set()).add(role)
                continue
            declared.setdefault(role, []).append(m)
            if m.extend >= 0:
                by_slot.setdefault(split_role(role)[0],
                                   "x" if m.extend else "y")
    by_slot.update(dict(extend_by_slot or {}))
    extend_by_slot = by_slot
    add = {}
    fallbacks = {}
    wanted = list(ROLES_2D)
    for name in list(extra_roles) + list(declared):
        role = canonical_role(name)
        x, y = split_role(role)
        # ⚠️ A MODULE NAME IS NOT A CELL. `facade.build` hands the style's rule
        # slots AND its module names in as `extra_roles`, and taking a name
        # for a role wrote `cornice` onto the `bay` module - so `by_role
        # ("cornice")` returned `bay` and the manifest's fallback map was
        # wrong to inspect, which is D136's whole stated benefit.
        if not (_is_slot(x) and _is_slot(y)):
            continue
        if role not in wanted:
            wanted.append(role)
        # 7.2's marker cells are legal BY GRAMMAR and therefore unbounded, so
        # they cannot live in ROLES_2D - but `marker:7` on a module still owes
        # its five Y classes a closure, or `marker:7_start` arrives on the
        # ground row as a SILENT stand-in (PC-G5 condition 5 counts those).
        if x.startswith("marker:"):
            wanted.extend(w for w in (role_2d(x, yy) for yy in SLOTS)
                          if w not in wanted)
        if y.startswith("marker:"):
            wanted.extend(w for w in (role_2d(xx, y) for xx in SLOTS)
                          if w not in wanted)
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
    if not add and not fallbacks and not dropped:
        return (kit, {})
    mods = []
    for m in kit.modules:
        # ⚠️ THE MODULE'S OWN ROLES ARE REWRITTEN CANONICAL, not just read
        # canonical. `Kit.by_role` is a membership test on this tuple, so a
        # module authored `bottom` would normalise for the WALK and then be
        # invisible to the lookup - the alias table has to reach the data, not
        # only the decision. (D4's `moduleRole` does the same thing one level
        # up.)
        lost = dropped.get(m.name, ())
        roles = tuple(r for r in (canonical_role(r) for r in m.roles)
                      if r not in lost)
        extra = tuple(r for r in sorted(set(add.get(m.name, ())))
                      if r not in roles)
        if roles == tuple(m.roles) and not extra:
            mods.append(m)
            continue
        mods.append(Module(m.name, m.size, pad=m.pad, deform=m.deform,
                           zmode=m.zmode, roles=roles + extra,
                           variant=m.variant, weight=m.weight, tilt=m.tilt,
                           extend=m.extend, clip=m.clip))
    out = Kit(kit.kit_id, kit.version, mods, kit.human_scale_reference,
              fallbacks, collisions)
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
                # D139 - the Y solve's warnings ride the ROW CURVE into the
                # kernel and `plan.classify` puts them on every element the
                # row produced. Before this they were computed here and
                # dropped, so a building that lost a storey said nothing.
                "pc_row_warns": " ".join(self.warns),
                "pc_clipped": 0,
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


# D139 - a warning the Y solve raises is the ROW's, and it is renamed on the
# way out so an element can never be read as though its own X run overflowed
# or its own module was missing. Two entries; anything else the 1D solver can
# say on the Y axis is unambiguous on its own and rides through unchanged.
_ROW_WARN = {WARN_OVERFLOW: WARN_ROW_OVERFLOW, WARN_KIT_GAP: WARN_ROW_KIT_GAP}


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

    # 7.3.3's `pc_warn_row_overflow`, D13's cascade seen on the Y axis: a
    # mandatory cap the Y style asked for that the solve could not place is a
    # storey that is simply GONE (a one-storey building loses its cornice),
    # and it used to ship with `warn_counts == {}`. Raised on every row, not
    # on the missing one - the missing one has no geometry to carry it.
    asked = set(r.slot for r in (y_style.rules if y_style is not None else ()))
    got = set(p.slot for _a, _b, p in bands)
    dropped = sorted(s for s in ("start", "end") if s in asked and s not in got)

    rows = []
    for i, (s0, s1, p) in enumerate(bands):
        pos0 = profile.sample(s0)[0]
        pos1 = profile.sample(s1, forward=False)[0]
        mod = tkit.by_name(p.module)
        nominal = mod.length if mod is not None else (s1 - s0)
        # D135 - a sliced Y placement becomes a SCALED row. The band is the
        # truth and the module is scaled into it; nothing is ever cut on Y.
        scale = ((s1 - s0) / nominal) if nominal > EPS else 1.0
        warns = [_ROW_WARN.get(w, w) for w in p.warns]
        if dropped and WARN_ROW_OVERFLOW not in warns:
            warns.append(WARN_ROW_OVERFLOW)
        rows.append(Row(i, s0, s1, pos0[1], pos1[1], pos0[0], pos1[0],
                        y_class(p.slot, s0, corner_s), p.module, scale,
                        warns, array_id))
    return rows


# D140 - `classify` MOVED TO `plan.py`. It is kernel work (it touches
# `Placement` and `Kit.role_fallbacks` and nothing else), and while it lived
# here `place.build` had to import `array2d`, which pointed 7's dependency
# arrow the wrong way round: the kernel is not allowed to need the stage above
# it. Re-exported so the name still resolves from either side.
classify = _plan.classify


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
    return [pts[i] for i in canonical_order(points, closed, ndigits)]


def canonical_order(points, closed=True, ndigits=3):
    """THE PERMUTATION `canonical_loop` APPLIES, as authored-vertex indices.

    ⚠️ `pc_corner` IS PER-VERTEX DATA (7.5, "vertex type is data") AND IT HAS
    TO TRAVEL WITH THE VERTEX. The emitter used to index the authored flag
    list by position in the CANONICALISED point list, so re-authoring the same
    footprint from a different vertex moved every suppression onto a different
    corner - the exact failure D124 exists to prevent, invisible because no
    committed case passed `corner_flags`.

    ⚠️ THE WINDING TEST IS `> 0`, NOT `< 0`. `_signed_area_xz` is the shoelace
    in the (x, z) chart, whose right-handed normal is -Y, so a POSITIVE area
    there is clockwise about +Y. 7.3.3/D124 asks for counter-clockwise about
    +Y, which is what makes `_frame`'s `across = cross(tangent, up)` point OUT
    of the building - and therefore what makes an asymmetric bay's front face
    the outside of the facade (D141).
    """
    pts = [tuple(float(c) for c in p) for p in points]
    idx = list(range(len(pts)))
    if not closed or len(pts) < 3:
        return idx
    if _dist(pts[0], pts[-1]) <= POS_EPS:
        pts.pop()
        idx.pop()
    if _signed_area_xz(pts) > 0.0:
        pts.reverse()
        idx.reverse()
    keys = [tuple(round(c, ndigits) for c in p) for p in pts]
    n = len(pts)
    best = min(range(n), key=lambda i: keys[i:] + keys[:i])
    return idx[best:] + idx[:best]


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
    """A closed planar spline -> `AreaFrame`. Never raises.

    ⚠️ THE PLANE NORMAL'S SIGN IS THE AUTHORED WINDING AND THE KERNEL'S IS NOT
    (D147). `_newell` flips with the direction the artist drew the loop, so a
    CLOCKWISE boundary gave `ey = -Y` while `place.build` kept growing every
    module along `UP` - the geometry came out one module-height below its own
    row datum, i.e. OUT of the footprint the plan had trimmed, with the plan
    and the geometry consistent with each other and both wrong. On the clipped
    plate that filled the hole and removed nothing, and every clip check
    passed, because all four gate loops were wound the other way. The closed
    1D path normalises winding in `canonical_order`; this is the area path's
    equivalent, and it is expressed against `UP` itself so the array frame and
    the kernel's up axis cannot drift apart again. A loop drawn IN the ground
    plane has `ey` perpendicular to `UP` and is left exactly as it was.
    """
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
    if _dot(ey, UP) < -EPS:
        ez = (-ez[0], -ez[1], -ez[2])
        ey = (-ey[0], -ey[1], -ey[2])
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


# 7.6 / D149 - THE ARRAY IS SOLVED IN ITS OWN PLANE AND BUILT ALONG `UP`, and
# those two agree only when the plane contains the world up axis. Every row
# datum is a line in the frame's chart at `row.y0`, and the kernel then grows
# the module along `UP`; where the frame's own `ey` is tilted away from `UP`
# the piece leaves its band by the difference. MEASURED on a 20 x 20 m plate
# with a 2 m module: 2 deg -> 0.0052 m, 5 deg -> 0.0131 m, 10 deg -> 0.0260 m,
# 30 deg -> 0.0750 m outside the region, against PC-G6's 0.010 m. Found while
# closing D147 - a NON-PLANAR loop was breaching by 0.0112 m and the cause
# turned out not to be the non-planarity at all. Every committed area case and
# PC-G6's own fixture stand exactly vertical, so the whole area path had only
# ever run at 0 deg. The tilt-aware solve (the row's up reference is the
# array's `ey`, not the world's) is a kernel change and is C3's; this says so
# instead of shipping a silent 7.5 cm.
CLIP_TILT_DEG = 0.5


def frame_tilt_deg(frame):
    """Degrees between an array's own up axis and the kernel's (D149)."""
    return math.degrees(math.acos(max(-1.0, min(1.0, _dot(frame.ey, UP)))))


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


# --- 7.6 / P2-7: the clip REGION - sub-splines, polarity, and the cut --------
#
# D143 - A REGION IS A LIST OF LOOPS WITH A POLARITY, NOT A POLYGON. D137
# reduced 7.6 to one boundary and one span; P2-7 is the rest of it, and the
# three things that were missing all fall out of the same object: a hole is a
# loop whose polarity is `exclude`, an island in a hole is a loop at depth 2,
# and "which edges cut this piece" is a query on the same edge list the
# scanline already walks.

# A boundary that TOUCHES a piece has not cut it. Four orders of magnitude
# under `bend_tol` (0.01 m), which is what PC-G6 judges footprint containment
# on, so nothing this rejects could be a real crossing.
CLIP_TOUCH_EPS = 1e-6


def point_in_poly(poly, x, y):
    """Even-odd crossing test, in the region's own 2-D chart."""
    inside = False
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
        if (ay > y) != (by > y):
            if x < ax + (bx - ax) * (y - ay) / (by - ay):
                inside = not inside
    return inside


def _area2(poly):
    a = 0.0
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        a += x0 * y1 - x1 * y0
    return a


def centroid(poly):
    """The area centroid - 7.6's own word for what decides nesting.

    Degenerate (zero-area) loops fall back to the vertex mean, because a
    centroid divided by zero area is not a point and 'never raises' is the
    rule everywhere else in this file.
    """
    a = _area2(poly)
    if abs(a) < EPS:
        n = float(len(poly)) or 1.0
        return (sum(p[0] for p in poly) / n, sum(p[1] for p in poly) / n)
    cx = cy = 0.0
    for i in range(len(poly)):
        (x0, y0), (x1, y1) = poly[i], poly[(i + 1) % len(poly)]
        f = x0 * y1 - x1 * y0
        cx += (x0 + x1) * f
        cy += (y0 + y1) * f
    return (cx / (3.0 * a), cy / (3.0 * a))


def _ccw(poly):
    """ONE winding, so an edge's inward normal is a formula and not a case."""
    return poly if _area2(poly) >= 0.0 else poly[::-1]


def open_loop(points):
    """A closed point list with its duplicated last vertex dropped."""
    pts = [tuple(float(c) for c in p) for p in points]
    if len(pts) > 1 and _dist(pts[0], pts[-1]) <= POS_EPS:
        pts.pop()
    return pts


def _contains(polys):
    """`contains[i][j]` - is loop `i` nested inside loop `j`? One chart.

    ⚠️ THE AREA RULE IS NOT A TIE-BREAK, IT IS THE WHOLE TEST. Concentric
    loops - a window in a wall, an island in a hole - share ONE centroid, so
    the bare "centroid inside the other" relation makes each of three nested
    squares contain both others: depth came back [2, 2, 2] and the plate, its
    hole and its island were three separate arrays with the hole FILLED. A
    loop can only be nested inside a strictly LARGER one.
    """
    cents = [centroid(p) for p in polys]
    areas = [abs(_area2(p)) for p in polys]
    return [[j != i and areas[j] > areas[i] + EPS
             and point_in_poly(polys[j], cents[i][0], cents[i][1])
             for j in range(len(polys))] for i in range(len(polys))]


def is_planar(points, rel_tol=1e-3):
    """(planar?, worst metres off the loop's own best plane) - 7.6's contract.

    7.6 specifies a "closed PLANAR sub-spline" and until D147 nothing tested
    it: a 20 x 20 m plate with one corner lifted 3 m built with no word said
    and delivered points 0.0112 m outside the region against PC-G6's own
    0.010 m tolerance - a gate condition failing silently on input the spec
    already excluded. The solve projects the loop into ONE plane, so the
    boundary an array trims to is not the boundary drawn, and the deviation is
    how far apart the two are.

    The tolerance is RELATIVE (0.1 % of the loop's own bounding diagonal,
    28 mm on a 20 m plate) because an absolute one is either hostile to a
    hand-drawn spline at building scale or blind at district scale.
    """
    pts = open_loop(points)
    if len(pts) < 4:
        return (True, 0.0)          # three points are a plane by definition
    n = _newell(pts)
    if n == (0.0, 0.0, 0.0):
        return (True, 0.0)
    d0 = _dot(n, pts[0])
    worst = max(abs(_dot(n, p) - d0) for p in pts)
    diag = math.sqrt(sum((max(p[k] for p in pts) - min(p[k] for p in pts)) ** 2
                         for k in range(3)))
    return (worst <= rel_tol * max(1.0, diag), worst)


def is_simple(points):
    """Does the loop avoid crossing itself? 7.6's other unstated contract.

    A self-intersecting boundary has no consistent winding - its two lobes
    wind opposite ways, `_area2` of a symmetric one is exactly 0.0 so `_ccw`
    is a no-op, and the half-planes `Region.cuts` emits then point OUT of one
    lobe: a bowtie plate breached its own region by 0.8839 m with nothing
    warned and `clip_inside_m` measuring the breach against the very region
    the builder used. D145's reflex channel cannot see it either, because a
    self-intersection is never a VERTEX. So it is rejected at the door like an
    unclosed loop rather than half-built (D147).

    O(n^2) on a sub-spline's own vertices, and it runs once per loop at read
    time - not in any per-piece path.
    """
    pts = open_loop(points)
    n = len(pts)
    if n < 4:
        return True
    flat = [(p[0], p[1], p[2]) for p in pts]
    for i in range(n):
        a, b = flat[i], flat[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or (j + 1) % n == i or j == (i + 1) % n:
                continue
            if _segments_cross(a, b, flat[j], flat[(j + 1) % n]):
                return False
    return True


def _segments_cross(a, b, c, d):
    """Do two 3-D segments properly cross, seen in the plane they best share?

    Projected onto the two axes with the largest spread, which is the same
    chart `area_frame` will flatten the loop into - so this answers the
    question the SOLVE will face rather than a 3-D one the solve never asks.
    """
    pts = (a, b, c, d)
    spread = sorted(range(3),
                    key=lambda k: -(max(p[k] for p in pts)
                                    - min(p[k] for p in pts)))
    u, v = spread[0], spread[1]

    def side(p, q, r):
        return ((q[u] - p[u]) * (r[v] - p[v])
                - (q[v] - p[v]) * (r[u] - p[u]))
    d1, d2 = side(a, b, c), side(a, b, d)
    d3, d4 = side(c, d, a), side(c, d, b)
    return ((d1 > EPS and d2 < -EPS) or (d1 < -EPS and d2 > EPS)) and \
           ((d3 > EPS and d4 < -EPS) or (d3 < -EPS and d4 > EPS))


def nest(loops, modes=None, chart=None):
    """D125's even-odd nesting: ([depth], [include?], [parent], chart).

    Containment is decided in ONE chart - the first loop's plane - because a
    hole and its boundary are the same drawing and must be compared in the
    same coordinates; each ARRAY then gets its own frame afterwards, which is
    the independence half of D125.

    `modes[i]` in ("include", "exclude") is 7.6's per-sub-spline override: it
    replaces that loop's depth parity and NOTHING else's, which is RC's `None`
    hierarchy mode expressed per spline instead of globally.
    """
    chart = chart if chart is not None else area_frame(loops[0])
    polys = [[chart.local(p) for p in open_loop(l)] for l in loops]
    contains = _contains(polys)
    depth = [sum(1 for c in row if c) for row in contains]
    parent = []
    for i, row in enumerate(contains):
        inside_of = [j for j, c in enumerate(row) if c]
        parent.append(max(inside_of, key=lambda j: depth[j])
                      if inside_of else -1)
    include = []
    for i, d in enumerate(depth):
        m = (modes[i] if modes and i < len(modes) else "") or ""
        include.append(True if m == "include" else
                       False if m == "exclude" else (d % 2 == 0))
    return (depth, include, parent, chart)


def array_members(parent):
    """{root loop index: [every loop in that root's tree]} - D125's "each
    closed sub-spline is its own array"."""
    root = []
    for i in range(len(parent)):
        r, seen = i, set()
        while parent[r] >= 0 and r not in seen:
            seen.add(r)
            r = parent[r]
        root.append(r)
    out = {}
    for i, r in enumerate(root):
        out.setdefault(r, []).append(i)
    return out


class Region(object):
    """The clip boundary of ONE array, in that array's own frame.

    `polys` are the member loops, normalised to one winding; `include` is
    their polarity. A point is inside the region when the DEEPEST loop
    containing it is an include loop - which reduces to even-odd when nothing
    is overridden, and stays right when something is.
    """

    __slots__ = ("polys", "include", "depth")

    def __init__(self, polys, include=None, depth=None):
        self.polys = [_ccw([(float(a), float(b)) for a, b in p])
                      for p in polys]
        self.include = list(include if include is not None
                            else [True] * len(self.polys))
        # ⚠️ THE DEFAULT USED TO BE `range(len(polys))` - the loop's INDEX read
        # as its nesting depth, so a caller that omitted `depth` got the
        # polarity of every multi-loop region decided by authoring order. Every
        # shipped caller passes real depths; the default is now derived from
        # the loops themselves, so there is no wrong answer left to inherit.
        self.depth = list(depth if depth is not None
                          else [sum(1 for c in row if c)
                                for row in _contains(self.polys)])

    def inside(self, x, y):
        best, hit = -1, False
        for i, poly in enumerate(self.polys):
            if point_in_poly(poly, x, y) and self.depth[i] > best:
                best, hit = self.depth[i], self.include[i]
        return hit

    def spans(self, y):
        """[(x0, x1)] of the horizontal line `y` INSIDE the region.

        Every loop's crossings, sorted, and the midpoint of each resulting
        interval tested - so a hole subtracts and an island inside it adds
        back with no special case for either.
        """
        xs = []
        for poly in self.polys:
            n = len(poly)
            for i in range(n):
                (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
                if (ay <= y < by) or (by <= y < ay):
                    xs.append(ax + (bx - ax) * (y - ay) / (by - ay))
        xs.sort()
        out = []
        for i in range(len(xs) - 1):
            if xs[i + 1] - xs[i] > EPS and \
                    self.inside(0.5 * (xs[i] + xs[i + 1]), y):
                out.append((xs[i], xs[i + 1]))
        return _merge(out)

    def cuts(self, x0, y0, x1, y1):
        """([(px, py, nx, ny)], reflex?) - the boundary edges that cross the
        rect, each as a half-plane whose normal points INTO the region.

        The second value is D145's honesty: two crossing edges that meet at a
        REFLEX vertex inside the rect cannot be expressed as an intersection
        of half-spaces, so the cut takes more than the polygon would.
        """
        out, corners = [], []
        for pi, poly in enumerate(self.polys):
            n = len(poly)
            sign = 1.0 if self.include[pi] else -1.0
            for i in range(n):
                (ax, ay), (bx, by) = poly[i], poly[(i + 1) % n]
                if not _seg_hits_rect(ax, ay, bx, by, x0, y0, x1, y1):
                    continue
                dx, dy = bx - ax, by - ay
                m = math.sqrt(dx * dx + dy * dy)
                if m < EPS:
                    continue
                out.append((ax, ay, -dy / m * sign, dx / m * sign))
                if x0 <= bx <= x1 and y0 <= by <= y1:
                    corners.append((pi, i))
        reflex = False
        for pi, i in corners:
            poly = self.polys[pi]
            n = len(poly)
            (ax, ay) = poly[i]
            (bx, by) = poly[(i + 1) % n]
            (cx, cy) = poly[(i + 2) % n]
            cross = (bx - ax) * (cy - by) - (by - ay) * (cx - bx)
            if (cross < -EPS) if self.include[pi] else (cross > EPS):
                reflex = True
        return (out, reflex)


def _seg_hits_rect(ax, ay, bx, by, x0, y0, x1, y1):
    """Liang-Barsky: does segment a->b meet the axis-aligned rect at all?"""
    t0, t1 = 0.0, 1.0
    dx, dy = bx - ax, by - ay
    for p, q in ((-dx, ax - x0), (dx, x1 - ax), (-dy, ay - y0), (dy, y1 - ay)):
        if abs(p) < EPS:
            if q < 0.0:
                return False
            continue
        r = q / p
        if p < 0.0:
            t0 = max(t0, r)
        else:
            t1 = min(t1, r)
        if t0 > t1:
            return False
    return True


def region_for(frame, loops, include=None, depth=None):
    """A `Region` in `frame`'s 2-D chart, from world-space member loops."""
    return Region([[frame.local(p) for p in open_loop(l)] for l in loops],
                  include, depth)


def _intersect(a, b):
    out = []
    for (a0, a1) in a:
        for (b0, b1) in b:
            lo, hi = max(a0, b0), min(a1, b1)
            if hi - lo > EPS:
                out.append((lo, hi))
    return out


def row_spans(frame, row, mode="remove", region=None):
    """The x intervals row `row` may occupy inside the boundary (D137).

    7.6's cost discipline, taken literally: the boundary test runs on the PLAN
    before geometry exists, and the cheapest place to apply it is the row's own
    span - so `remove` (nothing crosses the line) is the INTERSECTION of the
    scanlines at the band's bottom and top, `preserve` (a piece may overhang)
    widens each of those intervals to the union of the scanline intervals it
    OVERLAPS, and nothing is ever built outside the line by either. On a
    rectangle both are the full width, which is why a rectangular facade panel
    needs none of this and still gets it for free.

    ⚠️ `preserve` USED TO COLLAPSE THE WHOLE ROW TO `(min, max)`. On any
    concave or holed boundary that bridged the excluded region: a 4 m notch in
    a U-shaped panel came back as one span straight across it, and three
    whole bays were built 2.0 m INSIDE the hole with `clip_inside_m` reading
    0.3333 m against a 0.01 m tolerance. Per-interval is what "kept whole and
    may overhang" actually means - overhang the edge of your own interval,
    never bridge a gap between two.

    P2-7: `slice` widens the same way `preserve` does, and for the opposite
    reason - a piece that is to be CUT ON the line has to be able to reach it,
    and the `remove` intersection stops it a bay short. The cut itself is
    per-piece and lives in `place.build` (D144).
    """
    if mode == "none" or not frame.poly:
        return [(0.0, frame.width)]
    region = region if region is not None else Region([frame.poly])
    lo = region.spans(row.y0 + EPS)
    hi = region.spans(row.y1 - EPS)
    if not lo or not hi:
        mid = region.spans(0.5 * (row.y0 + row.y1))
        return mid or []
    keep = _intersect(lo, hi)
    if mode == "remove":
        return keep
    out = []
    for (a0, a1) in keep:
        x0, x1 = a0, a1
        for (b0, b1) in lo + hi:
            if min(a1, b1) - max(a0, b0) > EPS:
                x0, x1 = min(x0, b0), max(x1, b1)
        out.append((x0, x1))
    return _merge(sorted(out))


def _merge(spans):
    """Overlapping intervals folded together, so `preserve` cannot emit two
    row curves for one physical span."""
    out = []
    for (a, b) in spans:
        if out and a - out[-1][1] <= EPS:
            out[-1] = (out[-1][0], max(out[-1][1], b))
        else:
            out.append((a, b))
    return [tuple(s) for s in out]


def area_rows(frame, rows, mode="remove", unbuilt=None, region=None,
              hook=None):
    """[(points, closed, attrs)] - the row curves of a clipped area.

    Each row is a straight OPEN polyline across the boundary at its own band
    datum, in world space. A row the boundary leaves nothing of is dropped,
    which is `remove` doing its job rather than an error - but it is RECORDED
    into `unbuilt` when one is passed, because a whole storey vanishing
    silently is how `FM_area_taper` lost the top band of its roof panel with
    `cell_grid` reporting "0 empty": that check derived its row list from the
    OUTPUT, so a row that was never built could not read as a hole (D142).
    """
    out = []
    for row in rows:
        spans = [s for s in row_spans(frame, row, mode, region)
                 if s[1] - s[0] > EPS]
        if not spans and unbuilt is not None:
            unbuilt.append(row.index)
        full = abs(sum(s[1] - s[0] for s in spans) - frame.width) > EPS
        for k, (x0, x1) in enumerate(spans):
            pts = [frame.world(x0, row.y0), frame.world(x1, row.y0)]
            attrs = row.as_dict()
            # 7.3.3's `pc_clipped`, under D137's reading of it: this row's own
            # span was trimmed by the boundary, so every piece on it is a
            # piece the clip decided about.
            attrs["pc_clipped"] = 1 if full else 0
            if k:
                attrs["pc_curve_id"] = "%s.%d" % (attrs["pc_curve_id"], k)
            # D144 - the per-piece half of 7.6, handed to the kernel by
            # `pc_curve_id` alone. The kernel knows an arc length along a row
            # curve; this is the only place that knows what that arc length is
            # in the ARRAY's chart, so the translation is recorded here and
            # `ClipHook` does nothing but apply it.
            if hook is not None:
                hook.add(attrs["pc_curve_id"], frame, region, x0,
                         row.y0, row.y1)
            out.append((pts, False, attrs))
    return out


# --- D144: the per-piece cull, 7.6's own cost discipline --------------------

class ClipHook(object):
    """`place.build`'s clip callable: (curve_id, s0, s1, module) -> verdict.

    7.6 states the cost rule and this is it, literally: the test is a 2-D
    point-in-polygon on the piece's four footprint CORNERS, run on the plan
    before any geometry exists, so `remove` never builds anything and
    `preserve` never runs a boolean. Only a piece the plan says STRADDLES
    reaches `clip_plane`, and that is the `clip` verb 4.3 already uses - no
    fourth verb and no boolean SOP.

    ⚠️ THE CORNER TEST ALONE IS NOT ENOUGH AND THE EDGE WALK IS NOT AN EXTRA
    COST. A hole smaller than one bay sits entirely inside a piece with all
    four corners inside the region, so the corner test says "whole" and the
    window is filled in - the same class of defect as C1's polyfill trap, and
    invisible for the same reason. The edge walk that finds the CUTS is what
    detects it, and it has to run for `slice` anyway.
    """

    __slots__ = ("by_id", "policy", "removed", "sliced", "kept")

    def __init__(self, policy=CLIP_REMOVE):
        self.by_id = {}
        self.policy = int(policy)
        self.removed = self.sliced = self.kept = 0

    def add(self, curve_id, frame, region, x0, y0, y1):
        self.by_id[str(curve_id)] = (frame, region, float(x0), float(y0),
                                     float(y1))

    def __call__(self, curve_id, s0, s1, module):
        """(keep?, ((origin, normal, keep_sign), ...), (warning, ...))."""
        ent = self.by_id.get(str(curve_id))
        if ent is None or ent[1] is None:
            return (True, (), ())
        frame, region, ox, y0, y1 = ent
        ax, bx = ox + float(s0), ox + float(s1)
        lo, hi = min(ax, bx), max(ax, bx)
        # ⚠️ THE INSET IS LOAD-BEARING, AND IT IS THE FIRST THING THIS GOT
        # WRONG. `remove` means "a piece INTERSECTING the boundary is dropped";
        # without the inset a piece that merely TOUCHES it counts, and every
        # boundary of a rectangle touches the two end bays of every row - a
        # plain 12 x 9 panel went 12 packed pieces to 2, and the taper to
        # zero, with nothing failing. A cut is a crossing of the piece's
        # INTERIOR; the two are one epsilon apart and 1e-6 m is four orders
        # under `bend_tol`, which is the tolerance PC-G6 judges on.
        e = CLIP_TOUCH_EPS * max(1.0, hi - lo, y1 - y0)
        corners = [region.inside(x, y)
                   for x in (lo + e, hi - e) for y in (y0 + e, y1 - e)]
        edges, reflex = region.cuts(lo + e, y0 + e, hi - e, y1 - e)
        if not edges and all(corners):
            self.kept += 1
            return (True, (), ())
        if not edges and not any(corners):
            self.removed += 1
            return (False, (), ())
        policy = module.clip if module.clip >= 0 else self.policy
        if policy == CLIP_PRESERVE:
            self.kept += 1
            return (True, (), ())
        if policy != CLIP_SLICE:
            self.removed += 1
            return (False, (), ())
        if not module.sliceable:
            # D126 - degrade to REMOVE, never to preserve: an overhanging
            # window is a visible defect and a missing one is a visible gap,
            # and the gap is the one an artist notices and fixes.
            self.removed += 1
            return (False, (), (WARN_CLIP_UNSLICEABLE,))
        cuts = []
        for (px, py, nx, ny) in edges:
            cuts.append((frame.world(px, py),
                         (frame.ex[0] * nx + frame.ey[0] * ny,
                          frame.ex[1] * nx + frame.ey[1] * ny,
                          frame.ex[2] * nx + frame.ey[2] * ny),
                         1.0))
        self.sliced += 1
        return (True, tuple(cuts),
                (WARN_CLIP_CONVEX,) if reflex else ())
