"""polyChain 4.3 CORNERS - bend vs miter, compose symmetry, offset, the
displacement policy, the fillet, and the degenerate fallbacks. No `hou`.

This is the stage 8 budgets the most time for and the spec calls "the hard
20 %". It sits BETWEEN 4.1 decompose and 4.2 plan and owns four questions the
other two deliberately do not answer:

  1. does a corner BREAK the run at all (bend) or does it get a mitered joint
     with its own slot (miter);
  2. how many corner modules go where, and which side of the vertex;
  3. how much span the corner takes away from - or lends to - the neighbouring
     default runs;
  4. what plane the geometry is cut on, in WORLD space, so `place.py` can hand
     it to the `clip` verb without knowing anything about corners.

Everything here is plain data, exactly like the rest of the kernel: a `Bevel`
is a vertex, two tangents and a plane, and the output is `plan.Placement`
objects carrying the two new fields 4.3 needed (`anchor` and `cuts`).

THE BEHAVIOURAL REFERENCE (verified against iToo's own documentation on
2026-08-22, not recalled - `railclone.md` 1 item 4 and 6.2 name the mechanism
but not its rules):

  * "When the Bevel Corner option is enabled, the segment is repeated on both
    sides of the corner, and is sliced to maintain its full length on the
    OUTSIDE of the corner. You can adjust this slice position using the BC
    Offset option."
  * "Using an even number of segments always creates an asymmetric corner
    composition. [...] when an odd number of segments is used, the middle
    segment is centred to the corner, which means that using an odd number of
    segments always creates a symmetrical corner composition." and, for the
    even case, "RailClone centres the segment immediately before the vertex,
    then places other segments on the left or right depending on order in the
    compose operator."
  * Bevel Mode, the DEFAULT segments' displacement policy: "Reset: each
    segment is placed in its default position, and simply sliced at the corner
    vertex." / "Extend: extends the geometry of the segments along the bevel,
    giving an appearance of continuity around the corner." / "Symmetric:
    creates a symmetrical composition with the segment equalised either side
    of the Corner vertex."
  (docs.itoosoft.com "How to Fine Tune Corners"; itoosoft.com "Mastering the
  Linear Generator". The pages 403 to a plain fetch, so the wording above came
  back through search extracts of those same two pages.)

THE MITER, IN ONE PARAGRAPH. At a corner the two legs meet at a turn of `t`
degrees. The miter plane passes through the vertex with normal
`n = unit(tin + tout)`, so `n.tin = n.tout = cos(t/2)` and
`n.across = sin(t/2)`: a point at across-offset `z` on the incoming leg meets
the plane at along-offset `-z * tan(t/2)` from the vertex. The OUTSIDE edge of
a piece of half-width `h` therefore reaches `e = h * tan(t/2)` PAST the
vertex, and the inside edge is cut `e` short of it. That single number `e` is
the whole of 4.3's geometry: it places the corner module (so its outside face
keeps its full length), it is how far `extend` pushes a default run, and it is
what a corner offset shifts.

DECISIONS TAKEN HERE (recorded in polychain.md 10):

  D36 BEND DOES NOT BREAK THE RUN. 4.3's own words are "the default piece
      DEFORMS ACROSS THE VERTEX", and RailClone's are "Bevel Mode should be
      set to None to prevent the Default segments from continuing through to
      the corner" - i.e. by default they DO continue through. So in `bend`
      mode the sections either side of a corner are merged and the fill is
      solved once across the vertex; `place.py`'s existing interior-vertex
      test then bends whatever piece straddles it. A `pc_section` limit is
      never merged (it is not a corner, D18), and neither is a spline end.
  D37 THE CORNER SLOT IS A MITER FEATURE. In `bend` mode no corner module is
      placed - there is no joint to fill, because the run is continuous. This
      is why a bend-mode fence uses `corner_post` only when the artist asks
      for miter, and it is why bend closes a corner with no gap at all rather
      than with a well-fitted one.
  D38 COMPOSE LAYOUT. The composed corner modules are laid along the path with
      module index `floor((N-1)/2)` STRADDLING the vertex; modules before it
      run back down the incoming leg, modules after it out along the outgoing
      leg. The straddler is the one RailClone's "repeated on both sides"
      applies to: it is duplicated, one copy per leg, each sliced at the plane
      and each keeping its OUTSIDE face at the module's full length. N = 1 is
      just this rule with an empty flank list, which is exactly 4.3's "a
      single corner module is duplicated both sides preserving the outside
      face length". The reserve each leg loses is
      `(L_c - e) + sum(flank lengths)`, so an ODD count is symmetric
      (equal flanks) and an EVEN count is not (one flank longer by L) - the
      documented rule, recovered rather than special-cased.
  D39 CORNER OFFSET is a signed distance `o = pct/100 * L_straddler`, and it
      moves the CUT PLANE, not the pieces: the incoming plane sits at
      `V - o*tin` and the outgoing at `V + o*tout`. Positive therefore parts
      the two planes by `2*o*cos(t/2)` and leaves a gap; negative crosses them
      over, so each piece is cut deeper into the corner. The corner modules
      follow their own plane (their outside face stays L), which is what makes
      the offset read as "push apart / pull in" rather than "shrink".
  D40 THE DISPLACEMENT POLICY is an EXTENSION of the default run past the
      section boundary, measured from the plane, and it applies only where the
      default run actually reaches the corner - i.e. in miter mode with NO
      corner module in the way (RailClone's own advice is to turn bevel mode
      off once a corner segment is wired). reset = 0 (the piece stops at its
      default position and is sliced), extend = `e` for the default module's
      own half-width (its outside face reaches the plane, so the two legs' geo
      is continuous around the outside of the corner), symmetric = half the
      default module's nominal length (one piece straddles the vertex and is
      cut in the middle, which is "the segment equalised either side of the
      corner vertex"). All three are then shifted by the offset.
  D41 A MITERED PIECE IS UNPACKED AND CLIPPED WHATEVER ITS `pc_deform` IS.
      Slicing in 4.2 is opt-in per module because the FILL chose to cut; the
      miter is not the fill's choice, it is the artist's corner mode, and
      RailClone's Bevel Corner likewise slices whatever segment it is given.
      `rigid_deformed` in the checks therefore exempts - and counts - pieces
      carrying `pc_corner_cut`.
  D42 THE FILLET forces a corner at the ARC MIDPOINT and suppresses every
      other arc vertex, so a rounded corner still breaks the run in exactly
      one place and can still carry a corner module. Its turn there is the
      arc's own per-vertex turn (t/segments), so the miter degenerates into a
      plain perpendicular cut - which is right: the fillet has already
      absorbed the corner, and the pieces simply follow the rounded path.
  D43 A FILLET RADIUS TOO BIG FOR ITS LEGS IS CLAMPED, never rejected: the
      tangent distance is limited to 45 % of the shorter adjacent leg (so two
      adjacent fillets can never eat each other) and the piece carries
      WARN_FILLET_CLAMPED - the NINTH warning name.
  D44 A CORNER ASSEMBLY LONGER THAN ITS SECTION is squeezed, not dropped:
      when the two reserves of one section exceed its length the corner
      modules on that section's side are scaled by `L / (reserve_in +
      reserve_out)` and carry WARN_OVERFLOW (D13's policy, applied to 4.3).
      The squeeze is per SECTION, so a corner between a long leg and a short
      one is squeezed on the short side only - which is what keeps the long
      side's joint exact.
  D45 THE LAST CORNER OF A CLOSED SPLINE IS AN ORDINARY CORNER HERE. RailClone
      documents that it cannot offset that one; polyChain can, because
      `decompose` already pairs the sections of a closed curve cyclically
      (D10) and this stage walks the same cyclic pairing. `V_rect_miter`
      measures the wrap corner alongside the other three.
"""

import math

from . import (DEFAULTS, EPS, WARN_CORNER_DEGENERATE, WARN_FILLET_CLAMPED,
               WARN_KIT_GAP, WARN_OVERFLOW, Curve)
from . import plan as _plan
from .decompose import Section, _clean, _turn_deg, resolve_corners

UP = (0.0, 1.0, 0.0)


# --- vector helpers (kept local: this module must not import `hou`) ---------

def _add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _mul(a, k):
    return (a[0] * k, a[1] * k, a[2] * k)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _len(v):
    return math.sqrt(_dot(v, v))


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _unit(v, fallback=(1.0, 0.0, 0.0)):
    n = _len(v)
    return fallback if n < EPS else (v[0] / n, v[1] / n, v[2] / n)


def _rotate(v, axis, angle):
    """Rodrigues. Used only by the fillet, to walk the arc."""
    c, s = math.cos(angle), math.sin(angle)
    return _add(_add(_mul(v, c), _mul(_cross(axis, v), s)),
                _mul(axis, _dot(axis, v) * (1.0 - c)))


# --- the bevel --------------------------------------------------------------

# tan(t/2) explodes as the turn approaches 180 degrees, and a hairpin is
# exactly where 4.3 says to fall back. This cap is a second belt: even with
# `min_included_angle_deg` set to 0 by an artist, the miter overhang stays a
# number rather than an infinity.
MAX_TAN_HALF = 20.0          # ~ 174.3 degrees of turn


class Bevel(object):
    """One solved corner. Angles in DEGREES at the boundary, radians inside.

    `e_for(half_width)` is the miter overhang: how far past the vertex the
    OUTSIDE edge of a piece of that half-width must reach for the bisector cut
    to leave it at full length.
    """

    def __init__(self, corner, v, tin, tout, params=DEFAULTS,
                 section_in=None, section_out=None, s_vertex=0.0):
        self.corner = corner
        self.v = tuple(v)
        self.tin = _unit(tin)
        self.tout = _unit(tout)
        self.section_in = section_in
        self.section_out = section_out
        self.s_vertex = float(s_vertex)
        self.turn = _turn_deg(_sub(self.v, self.tin), self.v,
                              _add(self.v, self.tout))
        # `across` is the yaw frame's own across at the vertex (D20: +Z when
        # the piece runs +X), so `side` says which way the path turns and
        # therefore which face of a piece is the OUTSIDE one. A reflex corner
        # is simply `side = -1`; nothing else in this file changes.
        across = _cross(self.tin, UP)
        self.across = _unit(across, (0.0, 0.0, 1.0)) if _len(across) > EPS \
            else (0.0, 0.0, 1.0)
        self.side = 1.0 if _dot(self.tout, self.across) >= 0.0 else -1.0
        summed = _add(self.tin, self.tout)
        self.degenerate = bool(
            (corner.degenerate if corner is not None else False)
            or _len(summed) < 1e-6
            or (180.0 - self.turn) < params.min_included_angle_deg)
        # A hairpin has no usable bisector: unit(tin + tout) is noise. The
        # plane falls back to the incoming tangent, and the mode falls back to
        # bend - so nothing is ever cut on a plane derived from noise.
        self.n = _unit(summed, self.tin)
        self.mode = "bend" if self.degenerate else params.corner_mode
        self.half = math.radians(self.turn) * 0.5
        t = math.tan(self.half) if self.turn < 179.999 else MAX_TAN_HALF
        self.tan_half = max(min(t, MAX_TAN_HALF), -MAX_TAN_HALF)
        self.offset = 0.0                    # metres, set by `solve_corner`
        self.warns = (WARN_CORNER_DEGENERATE,) if self.degenerate else ()

    def e_for(self, half_width):
        return abs(float(half_width)) * self.tan_half

    def plane_in(self):
        """(origin, normal, keep_sign) for the piece arriving at the vertex."""
        return (_add(self.v, _mul(self.tin, -self.offset)), self.n, -1.0)

    def plane_out(self):
        """...and for the piece leaving it. Positive offset parts the two."""
        return (_add(self.v, _mul(self.tout, self.offset)), self.n, 1.0)

    def as_dict(self):
        return {"v": list(self.v), "turn": self.turn, "side": self.side,
                "n": list(self.n), "mode": self.mode,
                "degenerate": self.degenerate, "offset": self.offset,
                "s": self.s_vertex, "tan_half": self.tan_half}

    def __repr__(self):
        return "Bevel(%.2f deg, %s%s)" % (
            self.turn, self.mode, ", degenerate" if self.degenerate else "")


def _half_width(module):
    """The module's across half-extent (D20: +Z is across).

    A kit that leaves `pc_size.z` at 0 gets a miter overhang of 0, i.e. a plain
    perpendicular cut at the vertex. That is the honest degradation: without a
    width there is no outside face to keep at full length.
    """
    if module is None:
        return 0.0
    try:
        return abs(float(module.size[2])) * 0.5
    except (TypeError, IndexError):
        return 0.0


# --- 4.3 item E: the fillet -------------------------------------------------

def fillet(curve, params=DEFAULTS):
    """Round every corner of `curve` by `params.fillet_radius`. Never raises.

    Returns (curve, warns). The returned curve REPLACES the input for every
    later stage - decompose, plan and place all run on the rounded path, so
    4.2's section lengths are recomputed from the real filleted arc rather
    than corrected afterwards.

    D42: the arc's midpoint vertex is FORCED to be a corner and every other
    arc vertex is suppressed, so a rounded corner still breaks the run exactly
    once and can still carry a corner module.
    """
    r = params.fillet_radius
    if r <= EPS:
        return (curve, ())
    idx, pts, _cum = _clean(curve)
    n = len(pts)
    if n < 3:
        return (curve, ())

    corners = resolve_corners(curve, params)
    # A DEGENERATE corner is not filleted (D43, second half). Its tangent
    # distance is r*tan(turn/2), which at 179.99 degrees is 17 km before the
    # 45 %-of-a-leg clamp catches it - so the "fillet" it would get is a
    # near-zero-radius arc, i.e. the same hairpin with five more vertices on
    # it. 4.3 already answers a narrow angle with a fallback, and this is that
    # answer applied to the rounding as well.
    want = set(c.point_index for c in corners if not c.degenerate)
    flags_in = curve.corner_flags
    sections_in = curve.section_ids
    per_point_sections = (sections_in is not None
                          and hasattr(sections_in, "__len__")
                          and not isinstance(sections_in, str))

    def flag_of(i):
        o = idx[i]
        if not flags_in or o >= len(flags_in):
            return 0
        try:
            return int(flags_in[o])
        except (TypeError, ValueError):
            return 0

    def section_of(i):
        o = idx[i]
        if not per_point_sections or o >= len(sections_in):
            return None
        return sections_in[o]

    out_pts, out_flags, out_sections = [], [], []
    warns = []
    segs = params.fillet_segments
    rng = range(n) if curve.closed else range(1, n - 1)
    fillet_at = set(i for i in rng if idx[i] in want)

    for i in range(n):
        if i not in fillet_at:
            out_pts.append(pts[i])
            out_flags.append(flag_of(i))
            out_sections.append(section_of(i))
            continue
        v = pts[i]
        a, b = pts[(i - 1) % n], pts[(i + 1) % n]
        tin, tout = _unit(_sub(v, a)), _unit(_sub(b, v))
        turn = _turn_deg(a, v, b)
        axis = _cross(tin, tout)
        if turn <= 1e-6 or turn >= 180.0 - 1e-6 or _len(axis) < 1e-9:
            # collinear or a hairpin: there is no arc to build, and forcing
            # one would be geometry invented out of a degenerate input
            out_pts.append(v)
            out_flags.append(flag_of(i))
            out_sections.append(section_of(i))
            continue
        axis = _unit(axis)
        half = math.radians(turn) * 0.5
        d = r * math.tan(half)
        # D43: two adjacent fillets may never eat each other, so the tangent
        # distance is capped at 45 % of the shorter leg and the radius follows
        # it down. The alternative - refusing the radius - is warn-never-block
        # in reverse.
        lim = 0.45 * min(_len(_sub(v, a)), _len(_sub(b, v)))
        rr = r
        if d > lim:
            d = lim
            rr = d / math.tan(half)
            warns.append(WARN_FILLET_CLAMPED)
        p0 = _add(v, _mul(tin, -d))
        p1 = _add(v, _mul(tout, d))
        centre = _add(v, _mul(_unit(_sub(tout, tin)), rr / math.cos(half)))
        radial = _sub(p0, centre)
        sweep = math.radians(turn)
        mid = segs // 2
        for j in range(segs + 1):
            if j == 0:
                p = p0
            elif j == segs:
                p = p1
            else:
                p = _add(centre, _rotate(radial, axis, sweep * j / float(segs)))
            out_pts.append(p)
            out_flags.append(1 if j == mid else -1)     # D42
            out_sections.append(section_of(i))

    sections_out = sections_in
    if per_point_sections:
        sections_out = out_sections
    return (Curve(curve.curve_id, out_pts, closed=curve.closed,
                  corner_flags=out_flags, section_ids=sections_out,
                  style_key=curve.style_key, attrs=curve.attrs),
            tuple(sorted(set(warns))))


# --- 4.3 item A / D36: bend merges the sections it does not break ----------

def _joinable(section, params=DEFAULTS):
    """Is this section's START boundary a corner the run should NOT break at?

    Two reasons, and the second is 4.3 item F. In `bend` mode every corner is
    dissolved (D36). In `miter` mode only the DEGENERATE ones are: a narrow
    angle has no usable bisector, so 4.3's fallback is bend, and bend means
    the run continues through (D46). Either way a `pc_section` limit is never
    dissolved - it is where one generator hands over to the next (D18) - and
    neither is a spline end, which carries no corner at all.
    """
    corner = section.start_corner
    if corner is None or section.start_cap:
        return False
    if params.corner_mode == "bend":
        return True
    return bool(corner.degenerate)


def merge_bend_sections(sections, closed=False, params=DEFAULTS):
    """D36 - weld the runs that a bend corner must not break.

    Returns a NEW section list. Indices come from the first section of each
    group, so `pc_elem_id` stays the structural address it was (D1): welding
    two sections cannot renumber a third.
    """
    n = len(sections)
    if n < 2:
        return list(sections)
    join = [_joinable(s, params) for s in sections]
    if not closed:
        join[0] = False
    if all(join):                        # a closed ring of nothing but corners
        starts = [0]
    else:
        starts = [i for i in range(n) if not join[i]]
    groups = []
    for k, i0 in enumerate(starts):
        stop = starts[(k + 1) % len(starts)] if len(starts) > 1 else i0
        run, j = [sections[i0]], (i0 + 1) % n
        while j != stop and len(run) < n:
            run.append(sections[j])
            j = (j + 1) % n
        groups.append(run)
    out = []
    for run in groups:
        out.append(run[0] if len(run) == 1 else _weld(run, closed))
    out.sort(key=lambda s: s.s0)
    return out


def _weld(run, closed):
    first, last = run[0], run[-1]
    s0 = first.s0
    s1 = last.s1
    if s1 <= s0 + EPS:                        # the group wrapped the seam
        s1 += first.curve_length
    markers = []
    for sec in run:
        base = sec.s0 - s0
        if base < -EPS:
            base += first.curve_length
        for m in sec.markers:
            markers.append(dict(m, s_local=base + m.get(
                "s_local", m["s"] - sec.s0)))
    markers.sort(key=lambda m: (m["s_local"], m["marker_id"]))
    whole = closed and abs((s1 - s0) - first.curve_length) <= 1e-6
    # Where the corners WERE. Once a run is welded the boundaries are gone,
    # and with them any record that 4.3 made a decision here at all - so the
    # dissolved vertices ride along on the section (section-local metres) for
    # the checks and for the warning stamp.
    welds = []
    if whole and first.start_corner is not None:
        welds.append(0.0)          # the ring's own seam is a corner too
    for sec in run[1:]:
        w = sec.s0 - s0
        if w < -EPS:
            w += first.curve_length
        welds.append(w)
    out = Section(
        first.curve_id, first.index, s0, s1, first.curve_length,
        section_key=first.section_key, style_key=first.style_key,
        # A welded ring has no boundary left to carry a corner, and a welded
        # open run keeps the corners at its own two ends (they are `pc_section`
        # limits or spline ends, never the dissolved ones).
        start_corner=None if whole else first.start_corner,
        end_corner=None if whole else last.end_corner,
        start_frame=first.start_frame, end_frame=last.end_frame,
        markers=markers, closed=whole,
        start_cap=False if whole else first.start_cap,
        end_cap=False if whole else last.end_cap)
    out.welds = welds
    return out


# --- the corner assembly ----------------------------------------------------

class CornerPiece(object):
    """One module of the composed corner run, already resolved onto a leg."""

    __slots__ = ("module", "rule", "t_far", "t_near", "side", "compose_index",
                 "duplicate")

    def __init__(self, module, rule, t_far, t_near, side, compose_index,
                 duplicate):
        self.module = module
        self.rule = rule
        self.t_far = float(t_far)      # metres from the vertex, back down the leg
        self.t_near = float(t_near)    # negative = past the vertex
        self.side = side               # "in" or "out"
        self.compose_index = int(compose_index)
        self.duplicate = bool(duplicate)


class Assembly(object):
    """The whole corner: its pieces, what each leg lends it, and its warnings."""

    def __init__(self, bevel, pieces=(), reserve_in=0.0, reserve_out=0.0,
                 warns=()):
        self.bevel = bevel
        self.pieces = list(pieces)
        self.reserve_in = float(reserve_in)
        self.reserve_out = float(reserve_out)
        self.warns = tuple(warns)

    @property
    def symmetry(self):
        """|reserve_in - reserve_out|: 0 for an odd compose, L for an even one
        (D38). This IS the odd/even rule, as a number."""
        return abs(self.reserve_in - self.reserve_out)


def compose_modules(rule, kit, ctx, style):
    """The composed corner module list, in payload order (3.3's `sequence`).

    A `sequence` rule composes ALL of its modules - that is what RailClone's
    Compose operator is - and every other selector contributes exactly one
    (the choice it makes), because "randomly pick a corner" is one segment,
    not a composition.
    """
    if rule is None:
        return []
    if rule.select == "sequence":
        return list(_plan.candidates(rule, kit))
    m = _plan.choose(rule, kit, ctx, style)
    return [m] if m is not None else []


def build_assembly(bevel, mods, rule, params=DEFAULTS):
    """D38's layout. `mods` in compose order; returns an `Assembly`.

    Leg coordinate `t` runs from the vertex OUTWARD along each leg, so a
    negative `t` is past the vertex - which is exactly where a mitered piece's
    outside face has to reach.
    """
    if not mods:
        return Assembly(bevel)
    n = len(mods)
    c = (n - 1) // 2                       # the straddler (D38)
    straddler = mods[c]
    bevel.offset = (params.corner_offset_pct / 100.0) * straddler.length
    miter = bevel.mode == "miter"
    e = bevel.e_for(_half_width(straddler)) if miter else 0.0
    o = bevel.offset if miter else 0.0

    pieces = []
    if miter:
        # "repeated on both sides of the corner, and sliced to maintain its
        # full length on the outside": the outside edge reaches the plane, so
        # the piece runs from `t = L - e + o` down to `t = -e + o`.
        near = -e + o
        far = near + straddler.length
        pieces.append(CornerPiece(straddler, rule, far, near, "in", c, True))
        pieces.append(CornerPiece(straddler, rule, far, near, "out", c, True))
        base_in = base_out = far
    else:
        # bend: one piece centred on the vertex, no slice, no duplicate. It is
        # placed on the INCOMING leg and simply spans the vertex; `place.py`
        # bends it there if the module allows (D37 keeps this unreachable for
        # now - a bend corner has no joint - but the layout stays honest).
        half = straddler.length * 0.5
        pieces.append(CornerPiece(straddler, rule, half, -half, "in", c, False))
        base_in = base_out = half
    for j in range(c - 1, -1, -1):
        m = mods[j]
        pieces.append(CornerPiece(m, rule, base_in + m.length, base_in, "in",
                                  j, False))
        base_in += m.length
    for j in range(c + 1, n):
        m = mods[j]
        pieces.append(CornerPiece(m, rule, base_out + m.length, base_out,
                                  "out", j, False))
        base_out += m.length
    return Assembly(bevel, pieces, base_in, base_out, bevel.warns)


# --- 4.3 item D: the displacement policy ------------------------------------

def displacement(bevel, module, params=DEFAULTS):
    """D40 - how far the DEFAULT run runs past the section boundary, metres.

    Positive extends the run past the vertex (it is then cut by the plane);
    negative pulls it back. The offset shifts all three, because the plane it
    is cut against has moved.
    """
    if bevel.mode != "miter":
        return 0.0
    policy = params.corner_displacement
    if policy == "extend":
        base = bevel.e_for(_half_width(module))
    elif policy == "symmetric":
        base = (module.length * 0.5) if module is not None else 0.0
    else:                                        # reset
        base = 0.0
    return base - bevel.offset


# --- the orchestrator -------------------------------------------------------

def _default_module(kit, style, section, params):
    """The module a section's default run is made of - the one whose width the
    displacement policy is measured on. First rule that yields, first module."""
    ctx = {"curve_id": section.curve_id, "section_index": section.index,
           "sectionLength": section.length,
           "splineLength": section.curve_length,
           "cornerAngle": section.corner_angle, "u": section.u0, "index": 0,
           "attrs": {}, "marker_data": {}}
    _rule, mod = _plan.pick(style, "default", ctx, kit)
    return mod


def _corner_rule(style, kit, section):
    ctx = {"curve_id": section.curve_id, "section_index": section.index,
           "sectionLength": section.length,
           "splineLength": section.curve_length,
           "cornerAngle": section.corner_angle, "u": section.u0, "index": 0,
           "attrs": {}, "marker_data": {}}
    for rule in style.rules_for("corner"):
        if compose_modules(rule, kit, dict(ctx, slot="corner"), style):
            return (rule, ctx)
    return (None, ctx)


def _bevel_between(sec_in, sec_out, params):
    corner = sec_out.start_corner
    if corner is None:
        return None
    v = sec_in.end_frame[0]
    tin = sec_in.end_frame[1]
    tout = sec_out.start_frame[1]
    if _len(tin) < EPS or _len(tout) < EPS:
        return None
    return Bevel(corner, v, tin, tout, params, sec_in, sec_out, sec_in.s1)


def solve_corners(sections, kit, style, params=DEFAULTS, closed=False):
    """Every corner of one curve, solved. -> ([Assembly], {boundary: Assembly}).

    A boundary is keyed by the index of the section that STARTS at it, which
    is the same key `decompose` uses for `start_corner` - including the wrap
    boundary of a closed curve, whose key is the first section (D45).
    """
    out = {}
    n = len(sections)
    if n == 0:
        return out
    pairs = []
    for k in range(n):
        prev = k - 1
        if prev < 0:
            if not closed:
                continue
            prev = n - 1
        if n == 1 and not closed:
            continue
        pairs.append((sections[prev], sections[k], k))
    for sec_in, sec_out, key in pairs:
        if sec_out.start_cap:
            # D18 again: a boundary that earns a Start/End module is a spline
            # end or a `pc_section` limit, and RailClone puts caps there, not
            # corner segments. Building both would place two pieces on one
            # metre of curve.
            continue
        bevel = _bevel_between(sec_in, sec_out, params)
        if bevel is None:
            continue
        rule, ctx = _corner_rule(style, kit, sec_out)
        mods = []
        if bevel.mode == "miter":                        # D37
            mods = compose_modules(rule, kit, dict(ctx, slot="corner"), style)
        asm = build_assembly(bevel, mods, rule, params)
        out[key] = asm
    return out


def _squeeze(sections, assemblies, closed):
    """D44 - a section too short for the corners at its two ends.

    Returns {section index: factor <= 1}. The factor scales the reserves (and
    therefore the corner modules) on THAT section's side only.
    """
    factors = {}
    n = len(sections)
    for k, sec in enumerate(sections):
        head = assemblies.get(k)
        tail_key = (k + 1) % n if (closed or k + 1 < n) else None
        tail = assemblies.get(tail_key) if tail_key is not None else None
        need = (head.reserve_out if head else 0.0) + \
               (tail.reserve_in if tail else 0.0)
        if need > sec.length - EPS and need > EPS:
            factors[k] = max(sec.length / need, 0.0)
    return factors


def _piece_span(bevel, piece, factor):
    """(t_far, t_near) after D44's squeeze. Scaling the reserve scales the
    module with it, so the joint stays a joint."""
    return (piece.t_far * factor, piece.t_near * factor)


def _wrap_local(v, total, closed):
    """Section-local metres, folded into (-total/2, +total/2] on a closed
    curve. An open curve never wraps (D30)."""
    if not closed or total <= EPS:
        return v
    half = total * 0.5
    while v > half:
        v -= total
    while v <= -half:
        v += total
    return v


def _assembly_placements(asm, sections, key, params, style, factors, closed):
    """The corner slot's own `Placement`s, anchored on their legs (D38)."""
    bevel = asm.bevel
    n = len(sections)
    sec_out = sections[key]
    sec_in = sections[(key - 1) % n] if (closed or key > 0) else sections[key]
    out = []
    order = sorted(asm.pieces,
                   key=lambda p: (0 if p.side == "in" else 1, p.compose_index))
    for piece in order:
        section = sec_in if piece.side == "in" else sec_out
        sec_index = section.index
        k_section = (key - 1) % n if piece.side == "in" else key
        factor = factors.get(k_section, 1.0)
        t_far, t_near = _piece_span(bevel, piece, factor)
        length = max(t_far - t_near, 0.0)
        if piece.side == "in":
            origin = _add(bevel.v, _mul(bevel.tin, -t_far))
            direction = bevel.tin
            s1 = bevel.s_vertex - t_near
            s0 = bevel.s_vertex - t_far
        else:
            origin = _add(bevel.v, _mul(bevel.tout, t_near))
            direction = bevel.tout
            s0 = bevel.s_vertex + t_near
            s1 = bevel.s_vertex + t_far
        # The index has to be STRUCTURAL (D1), and a section can receive the
        # "in" half of the corner at its end AND the "out" half of the corner
        # at its start - both of which used to be index 0, so their two
        # `pc_elem_id`s collided and `elements()` merged two corner posts on
        # opposite legs into one 5.7 m record. Two per compose slot, side
        # deciding the parity, and a collision is impossible by construction.
        idx = 2 * piece.compose_index + (1 if piece.side == "in" else 0)
        module = piece.module
        warns = list(bevel.warns)
        if factor < 1.0 - 1e-9:
            warns.append(WARN_OVERFLOW)                   # D44
        if module.missing:
            warns.append(WARN_KIT_GAP)
        cuts = ()
        if bevel.mode == "miter":
            cuts = (bevel.plane_in(),) if piece.side == "in" \
                else (bevel.plane_out(),)
        # A closed curve's LAST corner joins the last section to the FIRST
        # one (D45), so the "out" half sits at s ~ curve_length while its
        # section starts at 0: without the wrap it planned at s = 39.92 m of a
        # 12 m section, and every along-the-chain check sorted it to the wrong
        # end of the run.
        local0 = _wrap_local(s0 - section.s0, section.curve_length, closed)
        out.append(_plan.Placement(
            section.curve_id, sec_index, "corner", idx, module.name,
            local0, local0 + (s1 - s0),
            u=section.u_at(local0),
            scale=(length / module.length) if module.length > EPS else 1.0,
            deform=module.deform, zmode=_plan._zmode(module, params),
            variant=module.variant, section_key=section.section_key,
            style_id=style.style_id, warns=tuple(warns),
            anchor=(origin, direction), cuts=cuts))
    return out


def plan_curve(curve, sections, kit, style, params=None):
    """4.1 -> 4.3 -> 4.2 for ONE curve. -> (placements, [Bevel], [Section]).

    This is the only entry point `place.py` needs: hand it the sections
    `decompose` produced and it returns every placement, corners included,
    plus the solved bevels so the checks can measure against the same planes
    the builder cut on, plus the SECTION LIST IT ACTUALLY USED - which is not
    the one it was handed whenever bend mode welded two of them (D36). Every
    returned section carries `fill_a`/`fill_b`, the span the default run was
    fitted into after the corners took their reserve, so a check can measure
    exact fill against the corner-adjusted span instead of against a section
    end no piece was ever asked to reach.
    """
    params = params or (style.params if style is not None else None) or DEFAULTS
    if not sections:
        return ([], [], [])
    closed = bool(curve.closed)
    # 4.3 item F: where a corner is about to be DISSOLVED, remember it first.
    # After the weld there is no boundary left to hang the warning on, and a
    # degenerate corner that builds silently is exactly what warn-never-block
    # forbids - so the vertices are kept and stamped onto whichever pieces end
    # up spanning them (D46).
    degenerate_s = [sec.s0 for sec in sections
                    if _joinable(sec, params) and sec.start_corner is not None
                    and sec.start_corner.degenerate]
    sections = merge_bend_sections(sections, closed, params)  # D36 / D46
    assemblies = solve_corners(sections, kit, style, params, closed)
    factors = _squeeze(sections, assemblies, closed)
    n = len(sections)

    out = []
    for key in sorted(assemblies):
        asm = assemblies[key]
        asm.bevel.assembly = asm
        asm.bevel.squeeze = factors.get((key - 1) % n, 1.0)
        out.extend(_assembly_placements(asm, sections, key,
                                        params, style, factors, closed))

    for k, section in enumerate(sections):
        head = assemblies.get(k)
        tail_key = (k + 1) % n if (closed or k + 1 < n) else None
        tail = assemblies.get(tail_key) if tail_key is not None else None
        factor = factors.get(k, 1.0)
        module = _default_module(kit, style, section, params)
        trim_head = trim_tail = 0.0
        cut_head = cut_tail = None
        if head is not None:
            if head.pieces:
                trim_head = head.reserve_out * factor
            else:
                trim_head = -displacement(head.bevel, module, params)
                if head.bevel.mode == "miter":
                    cut_head = head.bevel.plane_out()
        if tail is not None:
            if tail.pieces:
                trim_tail = tail.reserve_in * factor
            else:
                trim_tail = -displacement(tail.bevel, module, params)
                if tail.bevel.mode == "miter":
                    cut_tail = tail.bevel.plane_in()
        section.fill_a = trim_head
        section.fill_b = section.length - trim_tail
        runs = _plan.plan_section(section, kit, style, params,
                                  trim=(trim_head, trim_tail))
        if cut_head is not None or cut_tail is not None:
            _apply_cuts(runs, section, module, cut_head, cut_tail,
                        head, tail)
        out.extend(runs)
    if degenerate_s:
        _stamp_degenerate(out, sections, degenerate_s, curve.length, closed)
    out.sort(key=lambda p: (p.section_index, p.s0, p.slot, p.index))
    return (out, [assemblies[k].bevel for k in sorted(assemblies)], sections)


def _stamp_degenerate(placements, sections, vertices, total, closed):
    """WARN_CORNER_DEGENERATE onto every piece that spans a dissolved corner."""
    by_index = dict((sec.index, sec) for sec in sections)
    reps = (0.0, total, -total) if closed else (0.0,)
    for p in placements:
        section = by_index.get(p.section_index)
        if section is None or WARN_CORNER_DEGENERATE in p.warns:
            continue
        a, b = section.s0 + p.s0, section.s0 + p.s1
        for sv in vertices:
            if any(a - EPS <= sv + base <= b + EPS for base in reps):
                p.warns = p.warns + (WARN_CORNER_DEGENERATE,)
                break


def _apply_cuts(runs, section, module, cut_head, cut_tail, head, tail):
    """Hand the miter plane to every default piece whose GEOMETRY can cross it.

    NOT "the last piece": a piece that stops exactly on the plane still has
    half its cross-section on the wrong side of it - that is what a miter IS -
    so the test is the piece's own across-reach `e`, not its axis. Getting
    this wrong the cheap way (cut only the piece that overshoots) leaves the
    inner half of the last piece poking through its neighbour at every
    right-angle corner, which no along-the-chain check can see.
    """
    half = _half_width(module)
    for p in runs:
        if p.slot == "corner":
            continue
        if cut_head is not None and p.s0 - head.bevel.e_for(half) < 1e-9:
            p.cuts = p.cuts + (cut_head,)
        if cut_tail is not None                 and p.s1 + tail.bevel.e_for(half) > section.length - 1e-9:
            p.cuts = p.cuts + (cut_tail,)
