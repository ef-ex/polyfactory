"""polyChain - the contracts the 1D kernel is written against. No `hou`.

Spec: `ideas/polychain.md` (3 data contracts, 4.1 decompose, 4.2 plan).
Behavioural reference where the spec is silent: `ideas/railclone.md` 1.

This package is the `hou`-free half of polyChain, mirroring
`polyfactory/citygen/{__init__,plan}.py`: decide everything before geometry
exists, so it can be tested in milliseconds and audited without a licence.
A thin Python SOP adapter (later cycle) turns geometry into these plain
objects and writes the plan back out as inspectable points - the `graph_plan`
pattern. Nothing here imports Houdini, and nothing here reads a file.

House rules honoured here: metric metres everywhere; degrees only at the
artist boundary (`Params`, `Corner.turn_angle`); warn-never-block - every
failure path produces a warning name on the element and a usable result;
deterministic - see `seed_for`, which never touches `hash()` and never sees a
point number.

DECISIONS TAKEN IN THIS FILE (spec 9 open questions and ambiguities):

  D1  `pc_elem_id` is a STRING address "<curve>|<section>|<slot>|<index>|
      <styleId>", not a hash. 3.4 says "hash of ...", but the id is the key
      the swap/replace cascade matches on, and a 32-bit int over PC-G3's own
      10k+ element target collides with ~1% probability. `elem_key()` ships
      the crc32 alongside for cheap grouping/sorting only.
  D2  3.1's corner angle and 4.3's narrow angle are DIFFERENT angles and one
      threshold cannot be both. `corner_angle_deg` (default 30) is the TURN,
      i.e. deviation from straight; `min_included_angle_deg` (default 15) is
      the INCLUDED angle between the two legs - a hairpin. Both are recorded
      on every `Corner`, so the ambiguity cannot be reintroduced silently.
  D3  Open Q4 - `pc_cond` is a fixed {subject, op, value} dict with the 3.3
      subject list; `pc_vexpr` is accepted, ignored and warned in phase 1. No
      expression engine before a real conditional style exists (ponytail).
  D4  Open Q3 - `pc_role` is authoritative; `moduleRole` is accepted as an
      alias by the kit reader (buildings 12.9 convergence), one line, no
      meeting needed.
  D5  Padding is NOT scaled by the fill solve. `pc_pad` is a scene distance in
      metres (RailClone semantics); only module geometry stretches.
  D6  `Params.zmode` defaults to "" meaning "the module's own `pc_zmode`
      wins". 3.2 calls the module value a default and the style an override,
      which needs a third state for "style says nothing" - the empty string is
      it. A non-empty style zmode overrides every module.
  D17 Padding that cancels or reverses a unit ("one more piece costs nothing")
      is an input a solve cannot answer. It degrades - one scaled unit, or a
      count clamped to `MAX_UNITS` - and says WARN_DEGENERATE_PAD on every
      piece. Raising would break warn-never-block; negative padding is a
      documented feature, so the input cannot simply be rejected.
"""

import bisect
import math
import random
import zlib

# --- vocabularies. single owner, the JUNCTION_TYPE_VOCAB precedent ---------

SLOTS = ("default", "start", "end", "corner", "evenly")   # + "marker:<id>"

# --- 7.2: the 2D cell inventory. ONE vocabulary, used twice ------------------
#
# D116. RC Slice's 20 auto-generated pieces are not an enumeration - they are a
# 5 x 4 product table whose fifth column RailClone omitted (it has a Y Corner
# generator slot but never slices a Y-corner piece). A cell has exactly one X
# class and one Y class, both drawn from `SLOTS` above and NOT from a second
# vocabulary, so the inventory is the ordered pair `<x_slot>_<y_slot>` and the
# Y-`default` column collapses to the phase-1 name - which is why a phase-1
# kit is a valid phase-2 kit for the middle rows with no edit at all.
#
# `marker:<id>` is a slot on either axis by GRAMMAR, so `marker:7_default`
# (an authored bay) and `default_marker:2` (an authored storey) parse and work
# without being in the 25 - they are unbounded, and a vocabulary is not.


def role_2d(x_slot, y_slot="default"):
    """`<x>_<y>`, with the Y-`default` column written as the phase-1 name."""
    return x_slot if y_slot in ("", "default") else "%s_%s" % (x_slot, y_slot)


def split_role(role):
    """`<x>_<y>` -> (x slot, y slot). A phase-1 name is its own X half.

    Split on the LAST underscore, because a marker id can carry neither: the
    grammar is `<x>_<y>` where each half is a `SLOTS` member or `marker:<int>`,
    so `default_marker:7` splits cleanly and `corner` has no split at all. A
    string whose halves are not slots is NOT a role - it is a name the artist
    invented, and it is returned whole so a rule can still name it.
    """
    if "_" not in role:
        return (role, "default")
    x, _sep, y = role.rpartition("_")
    if _is_slot(x) and _is_slot(y):
        return (x, y)
    return (role, "default")


def _is_slot(name):
    return name in SLOTS or (name.startswith("marker:")
                             and name[7:].isdigit())


ROLES_2D = tuple(role_2d(x, y) for y in SLOTS for x in SLOTS)

# The words the industry writes, normalised at kit read - D4's `moduleRole`
# pattern, one table instead of a branch. The RC Slice piece names are in here
# verbatim (`start_top`, `x_corner_bottom`, `y_evenly_corner`, ...) so a kit
# authored against RailClone's own inventory reads without renaming, and
# `test_polychain_array2d` asserts that those 20 map onto exactly the 20 roles
# with `y_slot != "corner"` - bijectively, no leftovers on either side.
ROLE_ALIASES = {
    "bottom": "default_start", "top": "default_end",
    "left": "start", "right": "end",
    "lt": "start_end", "left_top": "start_end",
    "rt": "end_end", "right_top": "end_end",
    "lb": "start_start", "left_bottom": "start_start",
    "rb": "end_start", "right_bottom": "end_start",
    "x_corner": "corner", "x_evenly": "evenly",
    "y_evenly": "default_evenly", "xy_evenly": "evenly_evenly",
    "start_top": "start_end", "end_top": "end_end",
    "start_bottom": "start_start", "end_bottom": "end_start",
    "x_corner_top": "corner_end", "x_corner_bottom": "corner_start",
    "x_evenly_top": "evenly_end", "x_evenly_bottom": "evenly_start",
    "y_evenly_start": "start_evenly", "y_evenly_end": "end_evenly",
    "y_evenly_corner": "corner_evenly",
}


def canonical_role(name):
    """An authored role name -> the 7.2 vocabulary. Unknown names survive."""
    name = str(name).strip()
    if name in ROLE_ALIASES:
        return ROLE_ALIASES[name]
    x, y = split_role(name)
    return role_2d(x, y)

FILL_MODES = ("tile", "scale", "adaptive", "count")
Z_MODES = ("adaptive", "vertical", "stepped")
SCOPES = ("segment", "section", "spline", "generator")
SELECTORS = ("first", "sequence", "random", "conditional")
JUSTIFY = ("start", "center", "end")
CORNER_MODES = ("bend", "miter")
# 4.3's displacement policy for the DEFAULT pieces meeting a mitered corner.
# RailClone's own three (docs, "How to Fine Tune Corners", quoted in D40).
CORNER_DISPLACEMENTS = ("reset", "extend", "symmetric")
# 4.4's hybrid post/picket bands (D98). "" = no band; the band is measured
# from the module's own TOP or BOTTOM in metres of local height.
FLAT_BANDS = ("", "top", "bottom")

DEFORM_RIGID, DEFORM_BEND, DEFORM_SLICE = 0, 1, 2

# 3.4's warning names, plus two the spec implies but does not name (recorded
# as deviations in polychain.md 10).
WARN_KIT_GAP = "pc_warn_kit_gap"
WARN_CORNER_DEGENERATE = "pc_warn_corner_degenerate"
WARN_OVERFLOW = "pc_warn_overflow"
WARN_TILE_FALLBACK = "pc_warn_tile_fallback"      # 4.2 "else adaptive + pc_warn"
WARN_VEXPR_IGNORED = "pc_warn_vexpr_ignored"      # D3
WARN_DEGENERATE_PAD = "pc_warn_degenerate_pad"    # D17 - padding eats the unit
WARN_BEND_RESOLUTION = "pc_warn_bend_resolution"  # D25 - 4.4 "no auto-subdiv"
WARN_DEGENERATE_FRAME = "pc_warn_degenerate_frame"  # D32 - yaw frame collapsed
WARN_FILLET_CLAMPED = "pc_warn_fillet_clamped"    # D43 - 4.3's fillet radius
WARN_CONFORM_MISS = "pc_warn_conform_miss"        # D53 - 4.5 ray missed
WARN_REPLACED = "pc_warn_replace_deformed"        # D58 - a hero over a bend
# D74 - TWO CURVES CARRYING ONE ID. `pc_elem_id` is "collision-free by
# construction" (D1) only while the curve half of the address is unique, and
# nothing upstream enforces that: a copy-pasted street prim hands two separate
# curves the same authored `pc_curve_id` and every element of the second one
# lands on an address the first one already owns (measured: 4 prims, 2 ids,
# each stamped twice, warn list empty). An id-keyed override then hits both
# curves and any by-id map downstream silently drops half the run. Warn, never
# block - the ids are left exactly as authored, because renaming them here
# would move addresses that a style or an override may already reference.
WARN_CURVE_ID_DUP = "pc_warn_curve_id_dup"
# D118 - 7.2.2's lattice walk took a step. The role the cell ASKED for was not
# in the kit and a more general one stood in for it (or, at the end of the
# chain, 3.4's blank box did). A silent stand-in is the defect PC-G5 condition
# 5 counts, so every degrade says so on every element that took it, and the
# pair of role names is persisted in `pc_kit_warnings`.
WARN_ROLE_FALLBACK = "pc_warn_role_fallback"
# 7.3.3 - THE Y TWIN OF D13's CASCADE. A band shorter than its mandatory
# bottom + top drops one of them (or squeezes the whole stack), and until this
# name existed the Y solve computed the warning onto `Row.warns` and then threw
# it away: a one-storey building lost its cornice with `warn_counts == {}`.
# D139 - a warning the Y solve raises is the ROW's, so it is named on the row
# axis and then carried onto every element of that row.
WARN_ROW_OVERFLOW = "pc_warn_row_overflow"
# ...and its twin for the other Y-solve failure: the module that was to give
# the row its nominal HEIGHT (D132) was not in the kit, so 3.4's 1 m stand-in
# set the storey height. Deliberately NOT `pc_warn_kit_gap`: that name means
# "this ELEMENT is a blank box", and PC-G5 condition 5 counts an unexplained
# one - a real element in a wrongly-sized band is a different defect.
WARN_ROW_KIT_GAP = "pc_warn_row_kit_gap"
# 7.6 / D126 - a piece asked to be SLICED by the clip boundary that its module
# does not allow to be cut (`pc_deform < 2`). It degrades to `remove`, not to
# `preserve`: an overhanging window is a visible defect and a missing one is a
# visible gap, and the gap is the one the artist notices and fixes.
WARN_CLIP_UNSLICEABLE = "pc_warn_clip_unsliceable"
# 7.6 / D145 - the half-space limit of `clip_plane`, said out loud. A straddling
# piece is cut by one world plane per boundary edge that crosses it, so what it
# is left with is the INTERSECTION of half-spaces - which equals the boundary
# only where the boundary is locally convex. A REFLEX vertex of the region
# inside one piece's own footprint takes more material away than the polygon
# does: a gap, never a breach, and it says so rather than being discovered.
WARN_CLIP_CONVEX = "pc_warn_clip_convex"
# 7.6 / D290 - the clip input's own contract, which said "closed PLANAR
# sub-spline" and only ever tested the closure. A self-intersecting loop is
# SKIPPED like an unclosed one (its two lobes have opposite windings, so the
# half-planes `Region.cuts` emits point OUT of one of them and the array
# breached its own region by 0.88 m with nothing said); a non-planar one is
# built and warned, because a hand-drawn spline is never exactly planar and
# refusing it would be hostile - but it is projected into one plane to be
# solved, so the boundary the array trims to is not the boundary drawn.
WARN_CLIP_SELFX = "pc_warn_clip_selfx"
WARN_CLIP_NONPLANAR = "pc_warn_clip_nonplanar"
# ⚠️ `pc_warn_clip_tilted` IS RETIRED (D296, C3) and the NAME IS DELETED WITH
# IT. It announced D292's defect - an array solved in its own plane and built
# along the world's - and the row's up reference is the array's own `ey` now,
# so a tilted plate and a floor plate build inside their region (the ladder is
# in `array2d.frame_tilt_deg`'s note). A warning kept after its defect is
# fixed is a warning that fires on correct work.
# 7.3.2 / D293 - the 2D payload's own two complaints, and they are deliberately
# two names and not one. A MALFORMED field degrades to the kernel default and
# says which key it dropped - D78's rule, on the 2D axis. A field asking for
# behaviour the 2D path does not have is REFUSED BY NAME instead, because
# ignoring it is answering wrong: a payload that says `cap_holes = 0` and gets
# capped holes back has been told nothing, and a silent wrong answer is the
# failure mode this project keeps recording.
WARN_PAYLOAD_MALFORMED = "pc_warn_payload_malformed"
WARN_PAYLOAD_REFUSED = "pc_warn_payload_refused"
# 7.4 / D122 - the row could not take the datum row's bay count (a section so
# short the count does not fit, or a section with anchors on it, where the
# default fill is several runs and one count cannot say which). Warn, never
# block: the row falls back to its own free solve and says so.
WARN_Y_ALIGN_LOST = "pc_warn_y_align_lost"
WARN_VOCAB = (WARN_KIT_GAP, WARN_CORNER_DEGENERATE, WARN_OVERFLOW,
              WARN_TILE_FALLBACK, WARN_VEXPR_IGNORED, WARN_DEGENERATE_PAD,
              WARN_BEND_RESOLUTION, WARN_DEGENERATE_FRAME, WARN_FILLET_CLAMPED,
              WARN_CONFORM_MISS, WARN_REPLACED, WARN_CURVE_ID_DUP,
              WARN_ROLE_FALLBACK, WARN_ROW_OVERFLOW, WARN_ROW_KIT_GAP,
              WARN_CLIP_UNSLICEABLE, WARN_CLIP_CONVEX, WARN_Y_ALIGN_LOST)

# 7.6 / D126 - the cull policy, RailClone's "For No Slice" three, as decisions
# rather than as numbers. -1 on a module means "the array's own parm decides",
# which is D6's three-state pattern for the fourth time.
CLIP_REMOVE, CLIP_PRESERVE, CLIP_SLICE = 0, 1, 2
CLIP_POLICIES = {"remove": CLIP_REMOVE, "preserve": CLIP_PRESERVE,
                 "slice": CLIP_SLICE}

# 3.1 / 3.4 attribute names, so the adapter and the checks read one list.
CURVE_ATTRS = ("pc_corner", "pc_section", "pc_style", "pc_marker")
ELEM_ATTRS = ("pc_elem_id", "pc_elem_key", "pc_slot", "pc_module", "pc_variant",
              "pc_section", "pc_u", "pc_generated", "pc_deformed")

# ⚠️ THE KERNEL'S UP AXIS, AND IT IS ONE CONSTANT ON PURPOSE (D290). `place`
# grows every module along it and `array2d.area_frame` orients an array's plane
# by it; while they were two unrelated facts a clip loop authored CLOCKWISE
# gave the frame an `ey` of -Y, and every piece was built one module-height
# below its own row datum - out of its own footprint, hole filled, and every
# check green because every fixture was wound the other way.
UP = (0.0, 1.0, 0.0)

EPS = 1e-9          # metres; a chord shorter than this is not a segment
POS_EPS = 1e-6      # metres; two points closer than this are one point
# 7.4 / D299 - the smallest a module may be squeezed to in order to hold the
# ALIGNED datum's bay count, as a fraction of its own nominal size. 7.4 says a
# row that "physically cannot hold the datum's count" degrades to its own solve
# and warns, and on a kit without padding there is no physical limit at all -
# `fit`'s count mode returns the count it was asked for at whatever scale that
# takes, so a 2.0 m module shipped at 0.125 m with nothing said. Half is the
# threshold because below it the bay is not the module the artist chose any
# more; alignment is what was asked for, not a different building.
MIN_ALIGN_SCALE = 0.5

MAX_UNITS = 100000  # pieces in ONE run; a ceiling, not a target (D17). PC-G3
                    # plans 10k in one section legitimately, so this is 10x
                    # that - it exists only so degenerate padding degrades
                    # instead of exploding.


class Params(object):
    """Every HDA parm the kernel reads. Angles in DEGREES (artist boundary).

    `fill` is `adaptive` because architecture never slices a window
    (`railclone.md` 6.3). `adaptive_pct` is the add-one-more threshold in
    percent of a whole unit: 50 is round-to-nearest, 100 never adds one.
    `justify` centres the evenly run, matching RailClone's Justify default
    (docs: "adjust the first and last space to make the evenly segments fit").
    `adjust_to_end` is a leftover threshold in METRES: when the run's trailing
    leftover is at or under it, the spacing is stretched so the last anchor
    lands exactly on the section end (RailClone's adaptive spacing, gated).
    """

    def __init__(self, corner_angle_deg=30.0, min_included_angle_deg=15.0,
                 fill="adaptive", adaptive_pct=50.0, count=1,
                 evenly_spacing=0.0, evenly_count=0, justify="center",
                 adjust_to_end=0.0, corner_mode="bend", corner_offset_pct=0.0,
                 corner_displacement="reset", fillet_radius=0.0,
                 fillet_segments=4, zmode="", bend_tol=0.01,
                 fix_slope=False, conform_axis=(0.0, -1.0, 0.0),
                 conform_tilt=False, flatten_stepped=False,
                 flat_band="", flat_band_m=0.0):
        self.corner_angle_deg = float(corner_angle_deg)
        self.min_included_angle_deg = float(min_included_angle_deg)
        self.fill = fill if fill in FILL_MODES else "adaptive"
        self.adaptive_pct = float(adaptive_pct)
        self.count = int(count)
        self.evenly_spacing = float(evenly_spacing)
        self.evenly_count = int(evenly_count)
        self.justify = justify if justify in JUSTIFY else "center"
        self.adjust_to_end = float(adjust_to_end)
        self.corner_mode = corner_mode if corner_mode in CORNER_MODES else "bend"
        self.corner_offset_pct = float(corner_offset_pct)
        # 4.3 item D. Unknown -> "reset", the do-nothing policy, so a typo in a
        # style payload cannot silently move every piece at every corner.
        self.corner_displacement = (corner_displacement
                                    if corner_displacement in CORNER_DISPLACEMENTS
                                    else "reset")
        self.fillet_radius = max(float(fillet_radius), 0.0)
        # An EVEN count, so the arc always carries a real midpoint vertex - that
        # vertex is the filleted corner's own break point (D42).
        n = max(int(fillet_segments), 2)
        self.fillet_segments = n + (n % 2)
        # D6 again, and its THIRD state is also the safe landing for junk: an
        # unknown style zmode degrades to "" (the module's own value wins), NOT
        # to "adaptive". Forcing adaptive would discard the artist's intent AND
        # the module's default at once - a case-slipped "Vertical" in a style
        # payload silently banked every picket on a hillside instead of leaving
        # it plumb. The module side of the same typo is already warned in
        # `kit.validate`; this side degrades to the documented default.
        self.zmode = zmode if zmode in Z_MODES else ""
        self.bend_tol = float(bend_tol)
        # D26 - RailClone's Slope Fixing: "the segment width will remain the
        # same as the source geometry when measured on the HORIZONTAL axis,
        # but if switched off the width will be measured along the angle
        # defined by the path spline" (iToo, Using Deform modes in RailClone
        # Lite). Off by default, which is the plain reading of 4.2: the fit
        # runs on the path's own arc length.
        self.fix_slope = bool(fix_slope)
        # 4.5 / D51. The spec's "-Z" is Houdini's -Y (D20's translation), and
        # it is a DIRECTION, not an axis menu: a wall-mounted run conforms
        # sideways with the same parm and no new mode. A zero vector degrades
        # to the default rather than casting rays into nothing.
        a = tuple(float(c) for c in conform_axis)
        if math.sqrt(sum(c * c for c in a)) < EPS:
            a = (0.0, -1.0, 0.0)
        self.conform_axis = a
        # D55 - camber. Off by default: a road wants it, a fence does not, and
        # a default that tilts every module is a default that surprises.
        self.conform_tilt = bool(conform_tilt)
        # D98 - 4.4's FLATTEN-UNDER (RailClone's generator-side "Flatten
        # Stepped", which "automatically flattens the path in positions where
        # RailClone uses segments in Stepped mode"). A `stepped` piece is flat
        # by definition, and it used to take its one elevation from its
        # UPHILL end, so on a descending run its whole underside floated over
        # the ground - 0.061 m on PC-G2's hill - and reversing the spline
        # changed the fence. ON it takes the LOWEST ground under its own span
        # instead, so nothing floats and the result no longer depends on
        # which way the curve was drawn. OFF by default: it is an option in
        # RailClone too, and every baseline in the suite was measured without
        # it.
        self.flatten_stepped = bool(flatten_stepped)
        # D99 - the flat-top / flat-bottom BANDS, iToo's two hybrid modes.
        # One rule covers both halves of their own description: the named
        # band is treated as the OPPOSITE of the piece's z-mode, so a
        # `vertical` piece holds the band level ("flatten a Z-band from top
        # or bottom") and a `stepped` piece lets the band follow the ground
        # ("enable the top or bottom of a segment to deform and follow the
        # spline, leaving the middle area stepped"). `adaptive` has no band -
        # it rides the full frame and there is no flat half to hold.
        self.flat_band = flat_band if flat_band in FLAT_BANDS else ""
        self.flat_band_m = max(float(flat_band_m), 0.0)


DEFAULTS = Params()


# --- geometry-free curve ---------------------------------------------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _norm(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _unit(v):
    n = _norm(v)
    if n < EPS:
        return (0.0, 0.0, 0.0)
    return (v[0] / n, v[1] / n, v[2] / n)


class Curve(object):
    """One polyline primitive as plain data.

    `corner_flags` / `section_ids` are per-POINT (3.1 says `pc_corner` is a
    point attribute; `pc_section` is documented as prim, but a prim int cannot
    express a mid-curve break, so the kernel reads a per-point list first and
    accepts a scalar as the whole-curve value - decision D7, in decompose.py).
    """

    def __init__(self, curve_id, points, closed=False, corner_flags=None,
                 section_ids=None, style_key="", attrs=None):
        self.curve_id = curve_id
        self.points = [(float(p[0]), float(p[1]), float(p[2])) for p in points]
        self.closed = bool(closed)
        self.corner_flags = list(corner_flags) if corner_flags else None
        self.section_ids = section_ids
        self.style_key = style_key
        self.attrs = dict(attrs or {})
        self._cum = None
        self._segs = None
        # D166 - 4.1's answers, WHEN THEY WERE ALREADY COMPUTED IN VEX.
        # `place.read_curves` fills this from the DECOMPOSE box's own output;
        # `decompose._clean` and `decompose.resolve_corners` then return it
        # instead of re-deriving it in Python.  A curve built by any other
        # code path (the fillet, the slope flatten, a check, a caller with a
        # list of tuples) leaves it None and the Python answers, so the
        # reference never stops being runnable on its own.
        self.native = None
        # The primitive this curve was read off, or -1.  It is the ONE place
        # the id -> prim mapping lives (D167): `hda.curve_prim_index` used to
        # be a second copy of `read_curves`' id rule that applied none of its
        # filters, so the two could agree with each other and both disagree
        # with the curve set the builder actually planned on.
        self.prim_number = -1

    def _cumulative(self):
        if self._cum is None:
            cum, total = [0.0], 0.0
            pts = self.points
            for i in range(1, len(pts)):
                total += _norm(_sub(pts[i], pts[i - 1]))
                cum.append(total)
            if self.closed and len(pts) > 1:
                total += _norm(_sub(pts[0], pts[-1]))
                cum.append(total)
            self._cum = cum
        return self._cum

    def _segments(self):
        """([(lo, hi, start, delta)], [hi...]) - the per-segment table, built
        once (11.2 P2).

        ⚠️ CACHED, so it assumes `points` is not mutated after the first
        sample - which `_cumulative` above has always assumed, so this adds
        no new constraint, but a future feature that edits a `Curve` in place
        would silently serve stale geometry from both.
        """
        if self._segs is None:
            cum, pts, segs = self._cumulative(), self.points, []
            for i in range(len(cum) - 1):
                a = pts[i]
                d = _sub(pts[(i + 1) % len(pts)], a)
                if _norm(d) >= EPS:         # duplicate point: not a segment
                    segs.append((cum[i], cum[i + 1], a, d))
            self._segs = (segs, [g[1] for g in segs])
        return self._segs

    @property
    def length(self):
        cum = self._cumulative()
        return cum[-1] if cum else 0.0

    def arclen(self, i):
        """Cumulative metres at point `i` (i == len(points) => the closing)."""
        return self._cumulative()[i]

    def sample(self, s, forward=True):
        """(position, unit tangent) at `s` metres along the curve.

        ⚠️ At a vertex the two tangents differ, and WHICH ONE is asked for is
        the caller's business, not a rounding accident: a section's START
        frame wants the tangent LEAVING the vertex (`forward`), its END frame
        the one ARRIVING at it. Reading one segment index at a corner is how a
        90 degree section starts pointing down the previous leg.

        Closed curves wrap, which is what lets a wrapping section carry an
        `s1` past the total length instead of being split in two. The wrap
        lands `s == total` back on 0, which is right for the LEAVING tangent
        and wrong for the ARRIVING one - so a backward read at the seam is
        pushed back onto the closing segment, or the one closed section on a
        loop reports the first segment's direction as its end frame.
        """
        pts = self.points
        if not pts:
            return ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))
        if len(pts) == 1:
            return (pts[0], (0.0, 0.0, 0.0))
        total = self.length
        if self.closed and total > EPS:
            asked = s
            s = math.fmod(s, total)
            if s < 0.0:
                s += total
            if not forward and s <= EPS and asked > EPS:
                s = total                   # the arriving side of the seam
        cum = self._cumulative()
        s = min(max(s, 0.0), cum[-1])
        segs, his = self._segments()
        if not segs:
            return (pts[0], (0.0, 0.0, 0.0))
        # 11.2 P2. This used to rebuild `segs` on EVERY call and then scan it
        # linearly: 3.2 us at 10 verts against 8 218 us at 20 001, which was
        # 83 % of the worst case either port audit found. The table is cached
        # exactly like `_cumulative` above, and the scan is the same predicate
        # expressed as a bisect - `his` is strictly increasing (a segment is
        # only kept when its length is >= EPS), so "the first `hi` strictly
        # past s" is `bisect_right` and "the first `hi` at or past s" is
        # `bisect_left`, which is what the two branches asked for literally.
        i = (bisect.bisect_right(his, s + EPS) if forward
             else bisect.bisect_left(his, s - EPS))
        lo, hi, a, d = segs[i if i < len(segs) else -1]
        t = 0.0 if hi - lo < EPS else min(max((s - lo) / (hi - lo), 0.0), 1.0)
        return ((a[0] + d[0] * t, a[1] + d[1] * t, a[2] + d[2] * t), _unit(d))


class Marker(object):
    """3.1's marker point. `u` (0-1) OR `dist` (m, negative = from the end)."""

    def __init__(self, curve_id, u=None, dist=None, marker_id=0, data=None):
        self.curve_id = curve_id
        self.u = None if u is None else float(u)
        self.dist = None if dist is None else float(dist)
        self.marker_id = int(marker_id)
        self.data = dict(data or {})

    def distance_on(self, curve):
        """Resolve to metres along `curve`. Out-of-range values are clamped."""
        total = curve.length
        if self.dist is not None:
            s = self.dist if self.dist >= 0.0 else total + self.dist
        elif self.u is not None:
            s = self.u * total
        else:
            return 0.0
        return min(max(s, 0.0), total)


# --- kit -------------------------------------------------------------------

def _roles(roles):
    if roles is None:
        return ("default",)
    if isinstance(roles, str):
        return tuple(r for r in roles.split() if r) or ("default",)
    return tuple(roles) or ("default",)


class Module(object):
    """One kit piece (3.2). `size` is the nominal FITTED size in metres."""

    def __init__(self, name, size, pad=(0.0, 0.0), deform=DEFORM_RIGID,
                 zmode="adaptive", roles=("default",), variant="", weight=1.0,
                 missing=False, tilt=-1, extend=-1, clip=-1):
        if hasattr(size, "__len__"):
            self.size = (float(size[0]), float(size[1]), float(size[2]))
        else:
            self.size = (float(size), 0.0, 0.0)
        self.name = name
        self.pad = (float(pad[0]), float(pad[1]))
        self.deform = int(deform)
        self.zmode = zmode if zmode in Z_MODES else "adaptive"
        self.roles = _roles(roles)
        self.variant = variant
        self.weight = max(float(weight), 0.0)
        self.missing = bool(missing)     # a stand-in => WARN_KIT_GAP downstream
        # D55, and D6's three-state pattern again: -1 = "the style decides",
        # 0 = never tilt this module, 1 = always. A kerb stone that must stay
        # level inside a cambered road is the case for the middle state.
        self.tilt = int(tilt)
        # 7.2.1's Extend To Side, D6's three-state pattern once more: -1 = the
        # generator decides, 1 = this class extends to the side and its
        # fallback keeps X, 0 = it stops at the other axis' band and its
        # fallback keeps Y. It is a tie-break for ABSENCE, never for presence.
        self.extend = int(extend)
        # 7.6 / D126's cull policy, PER MODULE. -1 = the array's `clip_mode`
        # decides; 0 remove, 1 preserve, 2 slice. A window that must never be
        # cut in half and a cladding panel that must always reach the line are
        # one array and two policies, which is what makes it a module property
        # rather than a generator parm.
        self.clip = int(clip)

    @property
    def length(self):
        return self.size[0]

    def tilts(self, params):
        """D55 - does THIS module take the surface camber?"""
        return bool(params.conform_tilt) if self.tilt < 0 else bool(self.tilt)

    @property
    def sliceable(self):
        return self.deform >= DEFORM_SLICE

    def __repr__(self):
        return "Module(%r, %.4g)" % (self.name, self.size[0])


def stand_in(name="", nominal=(1.0, 1.0, 1.0)):
    """The blank box a missing module becomes. Never a failure (3.4)."""
    return Module(name or "pc_stand_in", nominal, roles=("default",),
                  missing=True)


class Kit(object):
    def __init__(self, kit_id="", version=1, modules=(),
                 human_scale_reference=0.0, role_fallbacks=None,
                 role_collisions=()):
        self.kit_id = kit_id
        self.version = int(version)
        self.modules = list(modules)
        self.human_scale_reference = float(human_scale_reference)
        # D118 - {role asked: role supplied}, filled by `array2d.close_roles`
        # and EMPTY on every 1D kit. A role in here was served by a walk on
        # the 5 x 5 lattice, so every element that took it says
        # WARN_ROLE_FALLBACK; a value of "" means the walk ran out and 3.4's
        # stand-in box is what arrives.
        self.role_fallbacks = dict(role_fallbacks or {})
        # 7.2's alias-collision notice, as persistable strings - "an alias
        # that resolves to a role another module already claims warns and
        # loses". Empty on every kit that has no colliding alias.
        self.role_collisions = list(role_collisions or ())
        self._by_name = dict((m.name, m) for m in self.modules)

    def by_name(self, name):
        return self._by_name.get(name)

    def by_role(self, role):
        """Payload order preserved - deterministic, never set iteration."""
        return [m for m in self.modules if role in m.roles]

    def resolve(self, name):
        """Name first, then role, then a stand-in. Never returns None/[]."""
        m = self.by_name(name)
        if m is not None:
            return [m]
        by_role = self.by_role(name)
        if by_role:
            return list(by_role)
        return [stand_in(name)]


def kit_from_records(records, kit_id="", version=1, human_scale_reference=0.0):
    """Build a Kit from the manifest dicts the adapter reads off points.

    D4: `pc_role` wins, `moduleRole` is accepted when it is absent.
    """
    mods = []
    for r in records:
        mods.append(Module(
            r.get("pc_name", r.get("name", "")),
            r.get("pc_size", r.get("size", (1.0, 1.0, 1.0))),
            pad=r.get("pc_pad", r.get("pad", (0.0, 0.0))),
            deform=r.get("pc_deform", r.get("deform", DEFORM_RIGID)),
            zmode=r.get("pc_zmode", r.get("zmode", "adaptive")),
            roles=r.get("pc_role", r.get("moduleRole", "default")),
            variant=r.get("pc_variant", r.get("variant", "")),
            weight=r.get("pc_weight", r.get("weight", 1.0)),
            tilt=r.get("pc_tilt", r.get("tilt", -1)),
            extend=r.get("pc_extend", r.get("extend", -1))))
    return Kit(kit_id, version, mods, human_scale_reference)


# --- style -----------------------------------------------------------------

class Rule(object):
    """One 3.3 rule point.

    D119 (E1) - `yclass` scopes the rule to ONE row class of the 2D array.
    Blank matches every row, so every phase-1 payload is a phase-2 X payload
    unchanged. It is its own field rather than a `conditional` on
    `attr:pc_yclass` because that encoding consumes `pc_select`, and a
    row-class-scoped rule that cannot also be `random` or `sequence` is half a
    rule (7.3.2).
    """

    def __init__(self, slot, select="first", modules=(), cond=None,
                 scope="segment", weights=None, vexpr="", yclass="",
                 axis="x"):
        self.yclass = str(yclass or "")
        # D120 - ONE payload, two axes. `y` rules drive the row stack, every
        # other rule drives the fill, and a payload that says nothing about an
        # axis is an X payload - which is every phase-1 payload there is.
        self.axis = "y" if str(axis).lower() == "y" else "x"
        self.slot = slot
        self.select = select if select in SELECTORS else "first"
        self.modules = list(modules)
        self.cond = cond
        self.scope = scope if scope in SCOPES else "segment"
        self.weights = dict(weights or {})
        self.vexpr = vexpr


class Style(object):
    def __init__(self, style_id="", version=1, seed=0, rules=(), params=None,
                 meta=None):
        self.style_id = style_id
        self.version = int(version)
        self.seed = int(seed)
        self.rules = list(rules)
        self.params = params or DEFAULTS
        # 7.3.2 - the payload's own `pc_style_meta`, kept whole so `y_params`,
        # `y_mode` and `clip` reach the 2D stage without a second reader. It
        # is {} on every parm-built style and on every phase-1 payload.
        self.meta = dict(meta or {})

    def rules_for(self, slot, yclass=None):
        """Payload order preserved: the first rule that yields wins.

        D119 - with a row class, the SCOPED rules come first and the blank
        ones after, so rule-level fallback (this row class -> any row) is the
        same ordered chain the kit-level role lattice is (7.2.2), and a
        payload says "random brick everywhere, but the ground floor is this
        shopfront" with two rules and no conditional. `yclass=None` is the
        1D caller and returns exactly what it always returned.
        """
        matched = [r for r in self.rules if r.slot == slot]
        if yclass is None:
            return matched
        return ([r for r in matched if r.yclass == yclass]
                + [r for r in matched if not r.yclass])

    def slots(self):
        out = []
        for r in self.rules:
            if r.slot not in out:
                out.append(r.slot)
        return out


# --- identity and seeding (3.3, 3.4) ---------------------------------------

def elem_id(curve_id, section_index, slot, index, style_id=""):
    """The structural address (D1). Collision-free by construction."""
    return "%s|%d|%s|%d|%s" % (curve_id, int(section_index), slot, int(index),
                               style_id)


def elem_key(elem_id_str):
    """A 31-bit int for grouping/sorting only - NEVER an identity."""
    return zlib.crc32(elem_id_str.encode("utf-8")) & 0x7FFFFFFF


_M64 = 0xFFFFFFFFFFFFFFFF


def _splitmix(x):
    x = (x + 0x9E3779B97F4A7C15) & _M64
    z = x
    z = ((z ^ (z >> 30)) * 0xBF58476D1CE4E5B9) & _M64
    z = ((z ^ (z >> 27)) * 0x94D049BB133111EB) & _M64
    return z ^ (z >> 31)


def scope_key(scope, ctx):
    """3.3's correlation key. A point number can never enter it."""
    if scope == "generator":
        return ()
    if scope == "spline":
        return (ctx.get("curve_id", ""),)
    if scope == "section":
        return (ctx.get("curve_id", ""), ctx.get("section_index", 0))
    return (ctx.get("curve_id", ""), ctx.get("section_index", 0),
            ctx.get("slot", ""), ctx.get("index", 0))


def seed_for(style, scope, ctx):
    """Deterministic across processes and sessions.

    NOT builtin `hash()`: `PYTHONHASHSEED` randomises string hashing per
    process, so a `hash()`-derived seed breaks "same inputs + seed => identical
    output" across recooks in different sessions - a house rule, not a taste.
    """
    key = "|".join(str(k) for k in scope_key(scope, ctx))
    text = "%d\x1f%s\x1f%s\x1f%s" % (style.seed, style.style_id, scope, key)
    return _splitmix(zlib.crc32(text.encode("utf-8")) & 0xFFFFFFFF)


def rng_for(style, scope, ctx):
    return random.Random(seed_for(style, scope, ctx))
