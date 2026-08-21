"""polyChain 4.1 DECOMPOSE - a polyline becomes an ordered section list.

A SECTION is the span between two consecutive breaks, where a break is a
corner or an explicit `pc_section` change (RailClone's material-ID limits).
Nothing here is geometry: a section is start/end distance, curve parameter,
length, the two end frames and the corner angle at each boundary.

DECISIONS TAKEN HERE (spec 9 / ambiguities), each pinned by a test:

  D7  `pc_section` is read at POINT class first. 3.1 types it as a prim int,
      but a prim int cannot express a mid-curve break, which is the whole
      point of "multiple polyChain instances may each claim a section range".
      A change of value between consecutive points is a break - the faithful
      analog of a material-ID limit. A scalar is accepted as the whole-curve
      key (the documented prim form), and then it never breaks anything.
  D8  Duplicate points are COLLAPSED, not corners. A repeated vertex has no
      direction, so it can neither confirm nor deny a turn; the cleaned
      polyline drives corner detection while arclen is unchanged (a zero
      chord adds zero metres). A curve that collapses to one point yields no
      sections; a curve with >= 2 distinct points but zero length yields one
      zero-length section, so the caller sees the curve rather than silence.
  D9  A degenerate (hairpin) corner is still a CORNER - it breaks the section.
      It is flagged `degenerate` and carries WARN_CORNER_DEGENERATE, which is
      what 4.3 reads to fall back from miter to bend. Suppressing the break
      instead would hide a hairpin inside a straight run.
  D10 Closed curves: breaks are cyclic and the section list starts at the
      FIRST break, wrapping the last section through point 0. With no breaks
      at all there is exactly one section, `closed = True`, starting at point
      0 - and start/end slots are unused on it (RailClone semantics). The
      wrapping section carries `s1 > curve.length`; `Curve.sample` wraps, so
      nothing downstream needs to know.
  D18 A section boundary is not automatically a place for a start/end module.
      RailClone caps a RUN, not a section: Start/End sit at spline ends (and
      at a material-ID limit, where another generator takes over), while a
      corner gets corner segments. So every section carries `start_cap` /
      `end_cap`, true only at a spline end or a `pc_section` change - which is
      why a closed spline gets no caps at all and an L-shaped fence does not
      grow a post pair at its elbow.
"""

import math

from . import (DEFAULTS, EPS, POS_EPS, WARN_CORNER_DEGENERATE, _norm, _sub,
               _unit)


class Corner(object):
    """A break candidate at one polyline vertex. Angles in DEGREES.

    `turn_angle` is the deviation from straight (0 = collinear), the angle
    3.1's `cornerAngle` parm thresholds. `included_angle` is the angle
    between the two legs (180 = collinear), the one 4.3's narrow-angle
    fallback thresholds. They sum to 180 by construction, and they are BOTH
    stored because the spec uses one name for both (decision D2).
    """

    def __init__(self, curve_id, point_index, position, turn_angle,
                 forced=False, degenerate=False, s=0.0):
        self.curve_id = curve_id
        self.point_index = int(point_index)
        self.position = tuple(position)
        self.turn_angle = float(turn_angle)
        self.included_angle = 180.0 - float(turn_angle)
        self.forced = bool(forced)
        self.degenerate = bool(degenerate)
        self.s = float(s)

    @property
    def warns(self):
        return (WARN_CORNER_DEGENERATE,) if self.degenerate else ()

    def as_dict(self):
        return {"curve_id": self.curve_id, "point_index": self.point_index,
                "position": list(self.position), "turn_angle": self.turn_angle,
                "included_angle": self.included_angle, "forced": self.forced,
                "degenerate": self.degenerate, "s": self.s}

    def __repr__(self):
        return "Corner(%s#%d, turn=%.3f deg%s)" % (
            self.curve_id, self.point_index, self.turn_angle,
            ", degenerate" if self.degenerate else "")


class Section(object):
    """One span. Metres along the parent curve are the truth; `u` is derived."""

    def __init__(self, curve_id, index, s0, s1, curve_length, section_key=0,
                 style_key="", start_corner=None, end_corner=None,
                 start_frame=None, end_frame=None, markers=(), closed=False,
                 start_cap=None, end_cap=None):
        self.curve_id = curve_id
        self.index = int(index)
        self.s0 = float(s0)
        self.s1 = float(s1)
        self.curve_length = float(curve_length)
        self.section_key = section_key
        self.style_key = style_key
        self.start_corner = start_corner
        self.end_corner = end_corner
        self.start_frame = start_frame or ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        self.end_frame = end_frame or ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        self.markers = list(markers)
        self.closed = bool(closed)
        # D18: a boundary earns a start/end module only when it is a real END
        # of the run - a spline end or a `pc_section` limit - never a corner.
        self.start_cap = (not self.closed) if start_cap is None else bool(start_cap)
        self.end_cap = (not self.closed) if end_cap is None else bool(end_cap)

    @property
    def length(self):
        return self.s1 - self.s0

    @property
    def u0(self):
        return 0.0 if self.curve_length <= EPS else self.s0 / self.curve_length

    @property
    def u1(self):
        return 0.0 if self.curve_length <= EPS else self.s1 / self.curve_length

    def u_at(self, s_local):
        """0-1 along the PARENT curve for `s_local` metres into the section."""
        if self.curve_length <= EPS:
            return 0.0
        u = (self.s0 + s_local) / self.curve_length
        return math.fmod(u, 1.0) if u > 1.0 else u

    @property
    def corner_angle(self):
        """The turn at the section's start, degrees. 0 at an open curve end."""
        return self.start_corner.turn_angle if self.start_corner else 0.0

    def as_dict(self):
        return {"curve_id": self.curve_id, "index": self.index,
                "s0": self.s0, "s1": self.s1, "length": self.length,
                "u0": self.u0, "u1": self.u1, "section_key": self.section_key,
                "style_key": self.style_key, "closed": self.closed,
                "start_cap": self.start_cap, "end_cap": self.end_cap,
                "start_frame": [list(self.start_frame[0]),
                                list(self.start_frame[1])],
                "end_frame": [list(self.end_frame[0]), list(self.end_frame[1])],
                "start_angle": (self.start_corner.turn_angle
                                if self.start_corner else 0.0),
                "end_angle": (self.end_corner.turn_angle
                              if self.end_corner else 0.0),
                "markers": [dict(m) for m in self.markers]}

    def __repr__(self):
        return "Section(%s[%d] %.4f..%.4f m%s)" % (
            self.curve_id, self.index, self.s0, self.s1,
            ", closed" if self.closed else "")


def _clean(curve):
    """(kept original indices, positions, cumulative metres) - D8.

    For a closed curve a final point coincident with the first is dropped: it
    is the closing vertex, not a second vertex at the same place.
    """
    idx, pts = [], []
    for i, p in enumerate(curve.points):
        if pts and _norm(_sub(p, pts[-1])) <= POS_EPS:
            continue
        idx.append(i)
        pts.append(p)
    if curve.closed and len(pts) > 1 and _norm(_sub(pts[0], pts[-1])) <= POS_EPS:
        idx.pop()
        pts.pop()
    cum, total = [0.0], 0.0
    for i in range(1, len(pts)):
        total += _norm(_sub(pts[i], pts[i - 1]))
        cum.append(total)
    return idx, pts, cum


def _turn_deg(a, b, c):
    """Deviation from straight at `b`, in degrees. 0 = collinear."""
    d0, d1 = _unit(_sub(b, a)), _unit(_sub(c, b))
    if _norm(d0) < EPS or _norm(d1) < EPS:
        return 0.0
    dot = max(-1.0, min(1.0, d0[0] * d1[0] + d0[1] * d1[1] + d0[2] * d1[2]))
    return math.degrees(math.acos(dot))


def _flag(curve, original_index):
    flags = curve.corner_flags
    if not flags or original_index >= len(flags):
        return 0
    try:
        return int(flags[original_index])
    except (TypeError, ValueError):
        return 0                                    # warn-never-block


def resolve_corners(curve, params=DEFAULTS):
    """Every vertex that is a corner, in point order (4.1).

    `pc_corner`: -1 suppress, 0 auto (turn > `corner_angle_deg`), 1 force.
    """
    idx, pts, cum = _clean(curve)
    n = len(pts)
    out = []
    if n < 3 and not (curve.closed and n >= 3):
        return out
    rng = range(n) if curve.closed else range(1, n - 1)
    for i in rng:
        a = pts[(i - 1) % n]
        c = pts[(i + 1) % n]
        turn = _turn_deg(a, pts[i], c)
        flag = _flag(curve, idx[i])
        if flag < 0:
            continue
        forced = flag > 0
        if not forced and turn <= params.corner_angle_deg:
            continue
        degenerate = (180.0 - turn) < params.min_included_angle_deg
        out.append(Corner(curve.curve_id, idx[i], pts[i], turn, forced,
                          degenerate, cum[i]))
    return out


def _section_breaks(curve, idx, n):
    """Cleaned indices where `pc_section` changes value, and the key per index.

    D7: a per-point list breaks the curve; a scalar is the whole-curve key.
    """
    ids = curve.section_ids
    if ids is None:
        return set(), [0] * n
    if not hasattr(ids, "__len__") or isinstance(ids, str):
        return set(), [ids] * n
    keys = [ids[idx[i]] if idx[i] < len(ids) else None for i in range(n)]
    breaks = set()
    # An open curve cannot break at its own last point: the break would open a
    # zero-length section past the end. A value change on the final point
    # belongs to the segment before it, so the last span keeps the earlier key
    # (the endpoint rule the corner breaks already follow).
    span = range(n) if curve.closed else range(1, n - 1)
    for i in span:
        if keys[i] != keys[(i - 1) % n]:
            breaks.add(i)
    return breaks, keys


def resolve_markers(curve, markers):
    """[{u, s, marker_id, data}] for the markers that belong to `curve`."""
    out = []
    for m in markers or ():
        if m.curve_id != curve.curve_id:
            continue
        s = m.distance_on(curve)
        total = curve.length
        out.append({"marker_id": m.marker_id, "s": s,
                    "u": 0.0 if total <= EPS else s / total,
                    "data": dict(m.data)})
    out.sort(key=lambda d: (d["s"], d["marker_id"]))
    return out


def decompose(curve, markers=(), params=DEFAULTS):
    """The ordered section list for one curve. Never raises (warn-never-block)."""
    idx, pts, cum = _clean(curve)
    n = len(pts)
    total = curve.length
    if n < 2:
        return []                                   # D8: nothing to place on

    corners = resolve_corners(curve, params)
    corner_at = dict((c.point_index, c) for c in corners)
    orig_to_clean = dict((o, i) for i, o in enumerate(idx))

    sec_breaks, sec_keys = _section_breaks(curve, idx, n)
    breaks = set(sec_breaks)
    for c in corners:
        i = orig_to_clean.get(c.point_index)
        if i is not None and (curve.closed or 0 < i < n - 1):
            breaks.add(i)

    if curve.closed:
        ends = sorted(breaks)
        if not ends:                                # D10: one wrapping section
            spans = [(0, n)]
        else:
            spans = [(ends[k], ends[(k + 1) % len(ends)]
                      + (n if k == len(ends) - 1 else 0))
                     for k in range(len(ends))]
    else:
        ends = sorted(breaks)
        cuts = [0] + ends + [n - 1]
        spans = [(cuts[k], cuts[k + 1]) for k in range(len(cuts) - 1)]

    marks = resolve_markers(curve, markers)
    taken = set()
    out = []
    for k, (i0, i1) in enumerate(spans):
        s0 = cum[i0]
        s1 = cum[i1] if i1 < n else total + cum[i1 - n]
        start_c = corner_at.get(idx[i0 % n])
        end_c = corner_at.get(idx[i1 % n])
        # D18: start/end modules cap a RUN, and a corner is not the end of one
        # (RailClone puts Corner segments there, never Start/End). Only a
        # spline end or a `pc_section` limit - the material-ID analog, where
        # another generator takes over - earns a cap.
        start_cap = (i0 % n) in sec_breaks
        end_cap = (i1 % n) in sec_breaks
        if not curve.closed:
            if i0 == 0:
                start_c = None
                start_cap = True
            if i1 == n - 1:
                end_c = None
                end_cap = True
        # A marker on a boundary belongs to exactly one section - the first
        # that can hold it - so a gate is never placed twice.
        sec_markers = []
        for j, m in enumerate(marks):
            if j in taken:
                continue
            s = m["s"]
            if not (s0 - EPS <= s <= s1 + EPS) and curve.closed:
                s += total
            if s0 - EPS <= s <= s1 + EPS:
                taken.add(j)
                sec_markers.append(dict(m, s_local=s - s0))
        out.append(Section(
            curve.curve_id, k, s0, s1, total,
            section_key=sec_keys[i0] if sec_keys else 0,
            style_key=curve.style_key,
            start_corner=start_c, end_corner=end_c,
            start_frame=curve.sample(s0, forward=True),
            end_frame=curve.sample(s1, forward=False),
            markers=sec_markers,
            closed=curve.closed and not breaks,
            start_cap=start_cap, end_cap=end_cap))
    return out


def decompose_all(curves, markers=(), params=DEFAULTS):
    """Every curve's sections, sorted by (curve_id, index) - order-independent."""
    out = []
    for c in sorted(curves, key=lambda c: str(c.curve_id)):
        out.extend(decompose(c, markers, params))
    out.sort(key=lambda s: (str(s.curve_id), s.index))
    return out
