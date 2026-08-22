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
        self.params = params
        self.flat = False
        # D48: the 3D tangents and how much longer a metre of ARC is than a
        # metre of the yaw-flattened leg the flattened bevel measures in. Both
        # are identities until `flatten` runs.
        self.tin3 = self.tin
        self.tout3 = self.tout
        self.arc_in = 1.0
        self.arc_out = 1.0
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
        # ⚠️ THIS TEST IS NOT DEAD, AND THE ONE THING THAT REACHES IT IS
        # `flatten` (D68, measured). Cycle 3v instrumented `__init__` over the
        # whole suite - 40 bevels built, 0 degenerate - and concluded these
        # three lines were unreachable decoration on top of `_joinable`. They
        # are unreachable AT FIRST CONSTRUCTION, and for the reason that pass
        # gives: `merge_bend_sections` welds every corner `decompose` already
        # scored degenerate before `solve_corners` looks at a boundary.
        # `flatten` then RE-RUNS this constructor on the yaw-flattened
        # tangents, and yaw-flattening changes the turn: a path that climbs
        # while doubling back in plan turns 104.8 degrees in 3D and 178.5
        # degrees flat. `decompose` never saw that hairpin - it reads the 3D
        # tangents - so this is the only place it can be caught, and D48 made
        # the catching necessary the moment it made plumb pieces cut on a
        # flattened plane. `test_polychain_corner.TestFlattenDegenerate` pins
        # the route; 3v's M4/M6 mutations die on it.
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

    def plane_origin(self):
        """D39, REVISED: there is exactly ONE cut plane and it NEVER MOVES.

        The first version gave each copy its own plane - `V - o*tin` and
        `V + o*tout` - which parted them by `2*o*cos(t/2)`: measured, a 5.7 cm
        hole at +25 % on the starter fence and, at -25 %, 5.7 cm of DOUBLY
        SOLID interpenetrating geometry where the two planes crossed over.

        Moving ONE shared plane along the bisector instead does not fix it,
        and this was measured too before it was believed: the two legs'
        centrelines meet ONLY at the vertex, so a plane anywhere else cuts the
        two boxes at different lateral positions and the two cut faces come
        out coplanar but slid apart along the cut line by `2*o*cos(t/2)` -
        `corner_face_mate_m` read 0.056569 m, the same hole in a new shape.

        The plane through the vertex is the only one that mates, so the OFFSET
        MOVES THE PIECES ALONG THEIR OWN LEGS instead (`build_assembly`), which
        is what iToo's "adjust this slice position" describes from the
        module's point of view: the two copies stay MIRROR IMAGES about this
        plane at every offset, so the joint never opens and never doubles, and
        what the artist is dialling is how much of the corner module the miter
        eats - 4.3's own "pull-in and slice".
        """
        return self.v

    def plane_in(self):
        """(origin, normal, keep_sign) for the piece arriving at the vertex."""
        return (self.plane_origin(), self.n, -1.0)

    def plane_out(self):
        """...and for the piece leaving it. Same plane, opposite keep side."""
        return (self.plane_origin(), self.n, 1.0)

    def flatten(self):
        """D48 - re-solve this corner on YAW-FLATTENED tangents.

        A `vertical` or `stepped` piece is built PLUMB, on the horizontal
        projection of its span (`place._frame`), so a bevel taken from the 3D
        tangents cuts it on a tilted plane that has nothing to do with how it
        was laid out. Measured, both halves of that: a 40 degree pitch kink at
        a hill crest anchored its two copies 0.055 m apart in Y and mated the
        cut faces to only 0.055 m (a flat L mates to 8e-7 m), and a 90
        degree-in-plan corner on a 25 % grade sliced the plumb 1.30 m corner
        post horizontally-obliquely, leaving a 0.345 m stump against a
        full-height mate. Flattening makes the plane VERTICAL, measures the
        overhang horizontally, and puts both anchors at the vertex elevation -
        which is the same projection the pieces themselves are built in.
        """
        fin = (self.tin[0], 0.0, self.tin[2])
        fout = (self.tout[0], 0.0, self.tout[2])
        if _len(fin) < 1e-6 or _len(fout) < 1e-6:
            return self               # a plumb leg has no yaw to flatten to
        offset = self.offset
        tin3, tout3 = self.tin, self.tout
        lin, lout = _len(fin), _len(fout)
        self.__init__(self.corner, self.v, fin, fout, self.params,
                      self.section_in, self.section_out, self.s_vertex)
        self.offset = offset
        self.flat = True
        # The assembly is laid out in FLATTENED leg metres (that is the space
        # the piece is built in), but a section's `s` is ARC length and so is
        # the reserve the default fill is trimmed by. One metre of flat leg is
        # `1/cos(pitch)` metres of arc, and forgetting it left the corner post
        # reaching 0.16 m horizontally where the run had given up 0.16 m of
        # arc - a 0.010 m hole in plan at a 20 degree pitch.
        self.tin3, self.tout3 = tin3, tout3
        self.arc_in = 1.0 / lin
        self.arc_out = 1.0 / lout
        return self

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
                 warns=(), near_in=0.0, near_out=0.0, slot="corner"):
        self.bevel = bevel
        self.pieces = list(pieces)
        self.reserve_in = float(reserve_in)
        self.reserve_out = float(reserve_out)
        self.warns = tuple(warns)
        # Where each leg's straddling copy REACHES PAST the vertex (negative).
        # D44's squeeze scales the assembly about this contact and not about
        # the vertex, so a squeezed module still reaches the cut plane.
        self.near_in = float(near_in)
        self.near_out = float(near_out)
        # "corner" for a real corner module; "default" for the synthetic
        # assembly D40's extend/symmetric policies build out of the DEFAULT
        # module (it is a default piece - it just does not ride the path).
        self.slot = slot

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


def build_assembly(bevel, mods, rule, params=DEFAULTS, overhang=None):
    """D38's layout. `mods` in compose order; returns an `Assembly`.

    Leg coordinate `t` runs from the vertex OUTWARD along each leg, so a
    negative `t` is past the vertex - which is exactly where a mitered piece's
    outside face has to reach.

    `overhang` overrides the miter overhang `e`. D40's `symmetric` policy is
    the same layout with `e = L/2`, so the piece is centred ON the vertex
    rather than reaching the plane with its outside face; passing the number
    keeps one layout instead of two.
    """
    if not mods:
        return Assembly(bevel)
    n = len(mods)
    c = (n - 1) // 2                       # the straddler (D38)
    straddler = mods[c]
    miter = bevel.mode == "miter"
    e = (bevel.e_for(_half_width(straddler)) if overhang is None
         else float(overhang)) if miter else 0.0
    # D49 - THE OFFSET IS CLAMPED FROM BELOW, and the miter overhang rides the
    # same clamp because they are the same number. The straddler's leg reserve
    # is `L - e + o`, and when that reaches zero the module sits ENTIRELY past
    # the vertex: the negative was handed to the default fill as a negative
    # trim, so the run built through the corner uncut (inside-out, -0.103 m3,
    # interpenetrating the other leg by 0.031 m at a 130 degree turn) and at
    # -100 % offset the corner post was clipped out of existence and left a
    # 23 cm hole - both with an EMPTY warning list. The module keeps at least
    # a tenth of its length on its own leg, and says so. There is deliberately
    # NO upper clamp: a positive offset that stops the piece short of the
    # plane leaves a notch, which is exactly what the knob is for.
    o_raw = (params.corner_offset_pct / 100.0) * straddler.length
    o = max(o_raw, e - 0.9 * straddler.length) if miter else o_raw
    clamped = miter and o > o_raw + 1e-12
    bevel.offset = o
    if not miter:
        o = 0.0

    pieces = []
    near_in = near_out = 0.0
    if miter:
        # "repeated on both sides of the corner, and sliced to maintain its
        # full length on the outside": the outside edge of the IN copy and the
        # inside edge of the OUT copy both land on the plane, so each runs
        # from `t = L - e` down to `t = -e`. D39 (revised) leaves that ONE
        # plane on the vertex and slides BOTH copies by `o` along their own
        # legs, which keeps them mirror images of each other about it: the
        # joint never opens, and the offset reads as how deep the miter bites
        # into the module.
        near_in = near_out = -e + o
        pieces.append(CornerPiece(straddler, rule, near_in + straddler.length,
                                  near_in, "in", c, True))
        pieces.append(CornerPiece(straddler, rule, near_out + straddler.length,
                                  near_out, "out", c, True))
        base_in = near_in + straddler.length
        base_out = near_out + straddler.length
    else:
        # bend: one piece centred on the vertex, no slice, no duplicate. It is
        # placed on the INCOMING leg and simply spans the vertex; `place.py`
        # bends it there if the module allows (D37 keeps this unreachable for
        # now - a bend corner has no joint - but the layout stays honest).
        half = straddler.length * 0.5
        pieces.append(CornerPiece(straddler, rule, half, -half, "in", c, False))
        base_in = base_out = half
        near_in = near_out = -half
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
    warns = list(bevel.warns)
    if clamped and WARN_OVERFLOW not in warns:
        warns.append(WARN_OVERFLOW)                      # D49
    return Assembly(bevel, pieces, base_in, base_out, tuple(warns),
                    near_in=near_in, near_out=near_out)


# --- 4.3 item D: the displacement policy ------------------------------------

def displacement(bevel, module, params=DEFAULTS):
    """D40, REVISED - the OVERHANG of the default module's boundary piece.

    The first version made this an EXTENSION of the fill span, handed to
    `plan_section` as a negative trim. Three things were measured wrong with
    that, all on the 12+12 m L with a 2 m panel:

      * under `tile` the extension is TILED INTO, so `symmetric` planted a
        whole new sliced half-panel entirely past the vertex (the clip then
        annihilated it to a 3 cm wedge carrying its own `pc_elem_id`), and
        `extend` planted a 0.03 m sliver instead of extending the last panel;
      * under `adaptive` "symmetric" was only approximately symmetric - the
        straddling piece came out centred at 12.07 m, not 12.00 m, off by
        `(L_nominal - L_scaled)/2`;
      * the piece past the vertex was DEFORMED AROUND THE WELDED KINK, because
        a default piece has no anchor and therefore rides the path. At a 150
        degree turn its cut faces stopped mating (0.055 m) and the survivor
        was inside-out (volume -0.060 m3).

    So the policy is now the same machinery the corner slot already uses: the
    boundary piece is a ONE-MODULE ASSEMBLY of the default module, anchored on
    the straight leg, duplicated both sides and cut on the plane. This
    function returns only the number that assembly is laid out with -
    `extend` puts the module's outside face on the plane (`e`), `symmetric`
    centres the module on the vertex (`L/2`), `reset` builds no boundary piece
    at all and the fill is simply sliced where it stops.

    The corner OFFSET is no longer subtracted here: D39 (revised) moves the
    single cut plane, and `build_assembly` shifts the two copies with it.
    """
    if bevel.mode != "miter" or module is None:
        return 0.0
    policy = params.corner_displacement
    if policy == "extend":
        return bevel.e_for(_half_width(module))
    if policy == "symmetric":
        return module.length * 0.5
    return 0.0                                   # reset


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


def _yaw_only(mods, params):
    """D48 - will every piece cut on this bevel be built PLUMB?

    `place._frame` flattens the tangent for `vertical` and `stepped`, so those
    pieces live in the horizontal projection and the plane that cuts them has
    to live there too. `adaptive` banks with the path and wants the 3D
    bisector. A mixed answer keeps the 3D plane, which is the conservative one:
    it is the only plane that is right for at least one of them.
    """
    mods = [m for m in mods if m is not None]
    if not mods:
        return False
    return all(_plan._zmode(m, params) != "adaptive" for m in mods)


def solve_corners(sections, kit, style, params=DEFAULTS, closed=False):
    """Every corner of one curve, solved. -> {boundary index: Assembly}.

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
        module = _default_module(kit, style, sec_out, params)
        if _yaw_only(mods or [module], params):
            bevel.flatten()                              # D48
        overhang, slot = None, "corner"
        if not mods:
            # D40's boundary piece, and F7's dead parm. `build_assembly` sets
            # the offset off the STRADDLER, so with no corner module nothing
            # ever set it: `corner_offset_pct` moved nothing at all on a
            # displacement-policy fence, silently. Here the straddler is the
            # default module, so the same rule ("% of module length") applies
            # to the module that is actually being bevel-sliced.
            bevel.offset = (params.corner_offset_pct / 100.0) * (
                module.length if module is not None else 0.0)
            d = displacement(bevel, module, params)
            if d > EPS:
                mods, rule, overhang, slot = [module], rule, d, "default"
        asm = build_assembly(bevel, mods, rule, params, overhang=overhang)
        asm.slot = slot
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
        a_head = head.bevel.arc_out if head else 1.0
        a_tail = tail.bevel.arc_in if tail else 1.0
        need = ((head.reserve_out * a_head if head else 0.0)
                + (tail.reserve_in * a_tail if tail else 0.0))
        if need > sec.length - EPS and need > EPS:
            # D44, CORRECTED: the squeeze is about the CUT PLANE, not about
            # the vertex, so the fixed point is how far each copy reaches past
            # it. Scaling `t_near` too pulled the squeezed copy's cut face
            # back off the plane by `e*(1-f)` - measured as a 0.0283 m notch
            # at every corner of a 12 x 0.12 m rectangle, and as a 1.20 m face
            # mating against a 0.776 m one on a long-leg/short-leg corner.
            n0 = ((head.near_out * a_head if head else 0.0)
                  + (tail.near_in * a_tail if tail else 0.0))
            denom = need - n0
            factors[k] = (max((sec.length - n0) / denom, 0.0)
                          if denom > EPS else 0.0)
    return factors


def _piece_span(asm, piece, factor):
    """(t_far, t_near) after D44's squeeze, scaled about the PLANE CONTACT.

    The straddler keeps its `t_near` - it still reaches the cut plane, so the
    two copies still mate - and only its length shrinks; the flanks stacked
    behind it follow, because they are measured in the same coordinate.
    """
    n0 = asm.near_in if piece.side == "in" else asm.near_out
    return (n0 + (piece.t_far - n0) * factor,
            n0 + (piece.t_near - n0) * factor)


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


def _assembly_placements(asm, sections, key, params, style, factors, closed,
                         bases=None):
    """The assembly's own `Placement`s, anchored on their legs (D38).

    `bases` is {section index: first free `default` index on it}, used only by
    D40's displacement assembly - its pieces ARE default pieces, so they
    continue the run's numbering instead of colliding with it.
    """
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
        t_far, t_near = _piece_span(asm, piece, factor)
        length = max(t_far - t_near, 0.0)
        # D48: `t` is a FLATTENED leg distance when the bevel was flattened,
        # so the anchor rides the leg's real 3D line (`tin3` scaled by the arc
        # factor, which puts the piece at the elevation the run hands it) and
        # the section coordinates are the matching ARC metres. Off a flat
        # curve every factor is 1 and every `*3` tangent is the tangent.
        if piece.side == "in":
            arc = bevel.arc_in
            origin = _add(bevel.v, _mul(bevel.tin3, -t_far * arc))
            direction = bevel.tin
            s1 = bevel.s_vertex - t_near * arc
            s0 = bevel.s_vertex - t_far * arc
        else:
            arc = bevel.arc_out
            origin = _add(bevel.v, _mul(bevel.tout3, t_near * arc))
            direction = bevel.tout
            s0 = bevel.s_vertex + t_near * arc
            s1 = bevel.s_vertex + t_far * arc
        # The index has to be STRUCTURAL (D1), and a section can receive the
        # "in" half of the corner at its end AND the "out" half of the corner
        # at its start - both of which used to be index 0, so their two
        # `pc_elem_id`s collided and `elements()` merged two corner posts on
        # opposite legs into one 5.7 m record. Two per compose slot, side
        # deciding the parity, and a collision is impossible by construction.
        idx = 2 * piece.compose_index + (1 if piece.side == "in" else 0)
        if asm.slot != "corner":
            idx += (bases or {}).get(k_section, 0)
        module = piece.module
        warns = list(asm.warns)
        if factor < 1.0 - 1e-9 and WARN_OVERFLOW not in warns:
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
            section.curve_id, sec_index, asm.slot, idx, module.name,
            local0, local0 + (s1 - s0),
            u=section.u_at(local0),
            scale=(length / module.length) if module.length > EPS else 1.0,
            deform=module.deform, zmode=_plan._zmode(module, params),
            variant=module.variant, section_key=section.section_key,
            style_id=style.style_id, warns=tuple(warns),
            anchor=(origin, direction, length), cuts=cuts))
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
    bases = {}
    for k, section in enumerate(sections):
        head = assemblies.get(k)
        tail_key = (k + 1) % n if (closed or k + 1 < n) else None
        tail = assemblies.get(tail_key) if tail_key is not None else None
        factor = factors.get(k, 1.0)
        module = _default_module(kit, style, section, params)
        trim_head = _reserve(head, "out", factor)
        trim_tail = _reserve(tail, "in", factor)
        cut_head = head.bevel.plane_out() \
            if head is not None and head.bevel.mode == "miter" else None
        cut_tail = tail.bevel.plane_in() \
            if tail is not None and tail.bevel.mode == "miter" else None
        section.fill_a = trim_head
        section.fill_b = section.length - trim_tail
        runs = _plan.plan_section(section, kit, style, params,
                                  trim=(trim_head, trim_tail))
        # ALWAYS, not only where the corner slot is empty. A default piece
        # that stops at the assembly's reserve still reaches `e` across, so
        # wherever the reserve is SHORTER than `e` the two legs' square ends
        # cross inside the corner module's footprint: measured as a
        # 0.000391 m3 boolean intersection per corner on a 1.5 m equilateral
        # triangle (reserve 0.0215 m against a 0.03 m panel half-thickness),
        # invisible from outside and unwarned. `_apply_cuts`' own across-reach
        # test already expresses exactly that condition, so handing it the
        # planes unconditionally is the whole fix.
        _apply_cuts(runs, section, module, cut_head, cut_tail, head, tail)
        out.extend(runs)
        bases[k] = 1 + max([p.index for p in runs
                            if p.slot == "default"] or [-1])

    for key in sorted(assemblies):
        asm = assemblies[key]
        asm.bevel.assembly = asm
        asm.bevel.squeeze = factors.get((key - 1) % n, 1.0)
        out.extend(_assembly_placements(asm, sections, key, params, style,
                                        factors, closed, bases))
    # D68 - AND THE CORNERS THAT ONLY DEGENERATE ONCE THEY ARE FLATTENED.
    # `degenerate_s` above reads `decompose`, which works on the 3D tangents;
    # `Bevel.flatten` (D48) can turn a mild 3D corner into a plan hairpin, and
    # that bevel's own `warns` only reach an element through `build_assembly`
    # - so a style with NO corner module dropped the warning entirely and a
    # 178.5 degree flattened corner built silently. Adding the vertex here
    # stamps the pieces that meet it either way; `_stamp_degenerate`'s bounds
    # are inclusive, so a piece that merely ENDS on the vertex is stamped too.
    degenerate_s = list(degenerate_s) + [
        asm.bevel.s_vertex for asm in assemblies.values()
        if asm.bevel.degenerate]
    if degenerate_s:
        _stamp_degenerate(out, sections, degenerate_s, curve.length, closed)
    out.sort(key=lambda p: (p.section_index, p.s0, p.slot, p.index))
    return (out, [assemblies[k].bevel for k in sorted(assemblies)], sections)


def _reserve(asm, side, factor):
    """Metres one corner assembly takes off one leg's default fill.

    NEVER NEGATIVE. `L_c - e` goes negative as soon as the turn is sharp
    enough that the corner module is shorter than its own miter overhang
    (126.87 degrees for the starter kit's 0.16 m post), and the negative was
    handed straight to `plan_section` as a negative trim: the default run then
    ran through the vertex, was DEFORMED around the hard kink, and came out
    inside-out (measured volume -0.103 m3 at a 130 degree turn) and
    interpenetrating the other leg by 0.031 m, with an empty warning list.
    Clamping here is half the fix; `build_assembly` stamps WARN_OVERFLOW and
    `_apply_cuts` hands the run the plane, which is the other half.
    """
    if asm is None or not asm.pieces:
        return 0.0
    r = asm.reserve_out if side == "out" else asm.reserve_in
    n0 = asm.near_out if side == "out" else asm.near_in
    arc = asm.bevel.arc_out if side == "out" else asm.bevel.arc_in
    return max((n0 + (r - n0) * factor) * arc, 0.0)


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
            _overflow(p, head)
        if cut_tail is not None \
                and p.s1 + tail.bevel.e_for(half) > section.length - 1e-9:
            p.cuts = p.cuts + (cut_tail,)
            _overflow(p, tail)


def _overflow(placement, asm):
    """A default piece cut by a corner it was supposed to stop short of.

    With no corner module the slice at the vertex IS the `reset` policy and
    says nothing; with one, the piece reaching across the plane means the
    reserve was shorter than the piece's own across-reach - the corner module
    does not have room, and warn-never-block wants that visible.
    """
    if asm is not None and asm.pieces and WARN_OVERFLOW not in placement.warns:
        placement.warns = placement.warns + (WARN_OVERFLOW,)
