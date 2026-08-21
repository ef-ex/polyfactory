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

import math
import random
import zlib

# --- vocabularies. single owner, the JUNCTION_TYPE_VOCAB precedent ---------

SLOTS = ("default", "start", "end", "corner", "evenly")   # + "marker:<id>"
FILL_MODES = ("tile", "scale", "adaptive", "count")
Z_MODES = ("adaptive", "vertical", "stepped")
SCOPES = ("segment", "section", "spline", "generator")
SELECTORS = ("first", "sequence", "random", "conditional")
JUSTIFY = ("start", "center", "end")
CORNER_MODES = ("bend", "miter")

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
WARN_VOCAB = (WARN_KIT_GAP, WARN_CORNER_DEGENERATE, WARN_OVERFLOW,
              WARN_TILE_FALLBACK, WARN_VEXPR_IGNORED, WARN_DEGENERATE_PAD,
              WARN_BEND_RESOLUTION)

# 3.1 / 3.4 attribute names, so the adapter and the checks read one list.
CURVE_ATTRS = ("pc_corner", "pc_section", "pc_style", "pc_marker")
ELEM_ATTRS = ("pc_elem_id", "pc_elem_key", "pc_slot", "pc_module", "pc_variant",
              "pc_section", "pc_u", "pc_generated", "pc_deformed")

EPS = 1e-9          # metres; a chord shorter than this is not a segment
POS_EPS = 1e-6      # metres; two points closer than this are one point
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
                 fillet_radius=0.0, zmode="", bend_tol=0.01,
                 fix_slope=False):
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
        self.fillet_radius = float(fillet_radius)
        self.zmode = zmode          # "" => the module's own pc_zmode wins (D6)
        self.bend_tol = float(bend_tol)
        # D26 - RailClone's Slope Fixing: "the segment width will remain the
        # same as the source geometry when measured on the HORIZONTAL axis,
        # but if switched off the width will be measured along the angle
        # defined by the path spline" (iToo, Using Deform modes in RailClone
        # Lite). Off by default, which is the plain reading of 4.2: the fit
        # runs on the path's own arc length.
        self.fix_slope = bool(fix_slope)


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
        segs = []
        for i in range(len(cum) - 1):
            a = pts[i]
            d = _sub(pts[(i + 1) % len(pts)], a)
            if _norm(d) >= EPS:             # duplicate point: not a segment
                segs.append((cum[i], cum[i + 1], a, d))
        if not segs:
            return (pts[0], (0.0, 0.0, 0.0))
        hit = segs[-1]
        for lo, hi, a, d in segs:
            if (hi > s + EPS) if forward else (hi >= s - EPS):
                hit = (lo, hi, a, d)
                break
        lo, hi, a, d = hit
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
                 missing=False):
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

    @property
    def length(self):
        return self.size[0]

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
                 human_scale_reference=0.0):
        self.kit_id = kit_id
        self.version = int(version)
        self.modules = list(modules)
        self.human_scale_reference = float(human_scale_reference)
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
            weight=r.get("pc_weight", r.get("weight", 1.0))))
    return Kit(kit_id, version, mods, human_scale_reference)


# --- style -----------------------------------------------------------------

class Rule(object):
    """One 3.3 rule point."""

    def __init__(self, slot, select="first", modules=(), cond=None,
                 scope="segment", weights=None, vexpr=""):
        self.slot = slot
        self.select = select if select in SELECTORS else "first"
        self.modules = list(modules)
        self.cond = cond
        self.scope = scope if scope in SCOPES else "segment"
        self.weights = dict(weights or {})
        self.vexpr = vexpr


class Style(object):
    def __init__(self, style_id="", version=1, seed=0, rules=(), params=None):
        self.style_id = style_id
        self.version = int(version)
        self.seed = int(seed)
        self.rules = list(rules)
        self.params = params or DEFAULTS

    def rules_for(self, slot):
        """Payload order preserved: the first rule that yields wins."""
        return [r for r in self.rules if r.slot == slot]

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
