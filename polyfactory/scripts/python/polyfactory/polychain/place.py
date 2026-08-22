"""polyChain 4.4 PLACE + DEFORM - the SOP-side adapter, and the only Houdini
half of the kernel pipeline.

Geometry in, kernel objects out, plan back, geometry out. NOTHING here decides
anything the kernel already decides: `decompose.py` still owns sections and
`plan.py` still owns the fit. This file owns exactly three questions - what
frame a piece is built in, whether it can stay a packed prim, and what gets
stamped on it (3.4).

THE CHORD FRAME, AND WHY IT IS THE STREETS MECHANISM
----------------------------------------------------
`citygen_streets.md` 11.8 validated it on the street graph: capture a shape
point in its segment's own chord frame - `u` along, `v` across, both divided by
the chord length - then rebuild from the end nodes. The reconstruction is a
similarity, so the piece keeps its shape and follows its nodes. Here the
"nodes" are the placement's own two ends on the curve: A at `s0`, B at `s1`.

  * A RIGID piece is exactly that rebuild, expressed as one 4x4 on a packed
    prim: local x maps onto the chord A->B, local y onto the frame's up, local
    z onto its across. No points are touched, so there is no round trip and no
    drift.
  * A BENT piece needs more than the chord, because the chord cannot follow a
    vertex inside the span. Each of its points is re-read at ITS OWN arc
    position, so the piece follows the curve instead of cutting it.

⚠️ AND ITS MEASURED LESSON, WHICH IS THE REASON PACKED IS NOT AN OPTIMISATION.
The streets pass found that running the rebuild unconditionally moved 68
recorded values on cases where NO node had moved: `u`/`v` are float32, the
round trip drifts ~1 mm at 800 m coordinates, and the loop ran ten times. The
fix was to SKIP the rebuild when the endpoints had not moved - not to recompute
it to the same value. The analog here is exact: when a span holds no interior
curve vertex, the arc IS the chord and the per-point rebuild would only add
float noise to a piece the chord already places exactly. So a straight span is
never rebuilt; it is placed as a packed prim (which is also 4.6's instancing
segregation, arriving for free).

DECISIONS TAKEN HERE (recorded in polychain.md 10):

  D20 Module local frame: +X along, +Y up, +Z across; fit origin = bbox min X,
      fit length = `pc_size.x`. See `kit.py`. The spec says "Z" for up because
      RailClone is a Max plugin; Houdini is Y-up, so the spec's Z is Y.
  D21 A piece is built on the CHORD between its two ends, not on the tangent
      at its start. The chord makes piece k's end and piece k+1's start the
      same point by construction, so "no gaps or overlaps" is a property of
      the construction rather than a tolerance. Placing on the start tangent
      would open a gap at every bend.
  D25 The bend warning is measured, not counted: for each pair of adjacent
      local-x stations in the module, the distance between the built chord
      between them and the true curve at their midpoint. Max > `bend_tol`
      raises `pc_warn_bend_resolution` and the piece is STILL BUILT (4.4: no
      auto-subdivision). A module with two stations across a corner is the
      case this is for.
  D26 Slope fixing (Params.fix_slope) fits on the HORIZONTAL arc length: the
      kernel is handed a Y-flattened copy of the curve and a piecewise-linear
      remap carries every planned distance back onto the real one. That is
      iToo's documented behaviour - width measured on the horizontal axis when
      on, along the path's angle when off.
  D27 A RIGID module ignores `vertical` as a deformation, because vertical IS
      a deformation (the spec's own words: "vertices Z-displaced to
      elevation"). It degrades to `stepped`, which is what a rigid piece can
      express. No warning: RailClone cannot deform a non-deformable segment
      either, and a warning on every post of a hillside fence is noise.
  D28 Slice caps are tagged `pc_cap = 1` on the prim. The slice is the `clip`
      SOP verb plus the `polyfill` SOP verb - vanilla Houdini, no Labs, no
      hand-written polygon clipper - and the cap is identified by the PLANE
      TEST (every point of the prim on the cut plane), not by "whatever
      polyfill added": measured on 22.0.398, a prim polyfill creates inherits
      its neighbour's attribute values rather than the attribute default, so
      the obvious default-value trick reads 0 on the cap it just built.
  D30 An OPEN curve EXTRAPOLATES past either end (`Path.sample`, `_Remap`)
      instead of clamping, so a piece that legitimately overhangs the end is
      carried rather than crushed into the end plane.
  D31 The frame is PARALLEL-TRANSPORTED along a deformed piece (`_transport`):
      `across` is flip-corrected against the previous station's, so a tangent
      that reverses direction mid-piece cannot twist it through itself.
  D32 Two silent collapses are now measured and warned, and neither blocks:
      `_flat_ratio` (a yaw-only mode on a near-vertical span -> the piece keeps
      its 3D length so it stays visible, plus WARN_DEGENERATE_FRAME) and
      `_chord_ratio` (a rigid piece over a suppressed hairpin -> still built on
      its chord, plus WARN_CORNER_DEGENERATE).
  D34 A `None` input is an UNCONNECTED input, not an error: `read_curves` and
      `kit.read` return empty results and a warning, and the build makes a
      stand-in fence. Warn-never-block includes the wiring.
  D35 `pc_u` vs `pc_dist` is resolved PER MARKER (see `read_curves`), because
      a Houdini attribute is per-geometry and a merged marker cloud otherwise
      hands every u-authored marker a default `pc_dist` of 0.
  D102 The stamp is written through `hou.Geometry`'s BULK array setters on a
      deformed piece, not one `Prim.setAttribValue` per attribute per prim.
      Profiled on `scale_gate`'s heaviest row (9 996 deformed pieces, 359 856
      points): 4 758 096 `Prim.setAttribValue` calls, 9.0 s of a 14.1 s
      build. `_stamp_values` is the single description both writers read, so
      they cannot drift; parity is bit-identical across all 83 cases.
  D103 THE DEFORM'S INNER LOOP STAYS IN PYTHON, and it is measured rather
      than assumed - see polychain.md 10 cycle 10c.
  D29 Curve identity: `pc_curve_id`, else `edge_id` (the streets id, which
      3.1 says feeds `pc_elem_id`), else the primitive number - always
      normalised to a string, because `pc_elem_id` is a string address (D1).
"""

import bisect
import math

import hou

from . import (DEFAULTS, EPS, WARN_BEND_RESOLUTION, WARN_CORNER_DEGENERATE,
               WARN_DEGENERATE_FRAME, WARN_KIT_GAP, Curve, Marker, Z_MODES,
               elem_key, stand_in)
from . import (WARN_CONFORM_MISS, WARN_CURVE_ID_DUP, WARN_REPLACED,
               WARN_TILE_FALLBACK)
from . import conform as _conform
from . import corner as _corner
from . import decompose as _decompose
from . import kit as _kit
from . import plan as _plan

UP = (0.0, 1.0, 0.0)

# 3.4's output schema. One list, so the builder and the checks read the same
# names: (attribute, default).
ELEM_PRIM_ATTRS = (
    ("pc_elem_id", ""), ("pc_elem_key", 0), ("pc_slot", ""), ("pc_module", ""),
    ("pc_variant", ""), ("pc_section", 0), ("pc_u", 0.0), ("pc_zmode", ""),
    ("pc_generated", 0), ("pc_deformed", 0), ("pc_corner_cut", 0),
    # D60 - 3.4's stamp, completed. `pc_elem_id` is a STRUCTURAL ADDRESS whose
    # curve half is a string (D1), and until these two existed the only way to
    # ask "which curve did this come from" downstream was to parse the id -
    # which is exactly the kind of string surgery the attribute convention
    # exists to avoid. `pc_style` closes the same gap for the payload that
    # produced the element, which is what a multi-style stream needs to split
    # on and what the swap/replace cascade keys against when two styles share
    # one kit.
    ("pc_curve_id", ""), ("pc_style", ""), ("pc_replaced", 0),
)

_VERBS = {}


def _verb(name):
    if name not in _VERBS:
        _VERBS[name] = hou.sopNodeTypeCategory().nodeVerb(name)
    return _VERBS[name]


# --- small vector helpers (no hou.Vector3: this runs per point) -------------

def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _len(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _unit(v, fallback=(1.0, 0.0, 0.0)):
    n = _len(v)
    return fallback if n < EPS else (v[0] / n, v[1] / n, v[2] / n)


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


# --- the sampler ------------------------------------------------------------

class Path(object):
    """A fast arclength sampler over one polyline.

    ⚠️ THIS DESCRIBED A DIFFERENCE THAT NO LONGER EXISTS. It used to say
    `Curve.sample` rebuilds its segment table on every call; **11.2 P2 cached
    and bisected the kernel's sampler too** (6f1eb00), so both are now built
    once and searched with `bisect`, and a reader deciding whether a later
    item may reuse `Curve.sample` was being handed a cost model three commits
    out of date.

    What still separates them is END BEHAVIOUR, and only that: this one
    EXTRAPOLATES past an open curve's ends (D30 - there is a measured defect
    behind it, a 1.6 m gate crushed to a 1.11 m zero-thickness plane) where
    `Curve.sample` clamps. They are not interchangeable for that reason, not
    for speed. The table is built from `Curve._cumulative()` so the two cannot
    disagree about where a metre is; `sampler_matches_kernel` asserts exactly
    that, at 400 positions per case.
    """

    def __init__(self, curve):
        self.closed = bool(curve.closed)
        cum = curve._cumulative()
        pts = curve.points
        n = len(pts)
        self.total = cum[-1] if cum else 0.0
        self.vertex_s = list(cum)
        segs = []
        for i in range(len(cum) - 1):
            a = pts[i]
            d = _sub(pts[(i + 1) % n], a)
            if _len(d) >= EPS:
                segs.append((cum[i], cum[i + 1], a, d))
        self.segs = segs
        self.ends = [s[1] for s in segs]
        self.first = pts[0] if pts else (0.0, 0.0, 0.0)
        self.kink_s = self._kinks(segs, self.closed)

    @staticmethod
    def _kinks(segs, closed, tol=1e-9):
        """Arclengths where the direction ACTUALLY changes (D69).

        ⚠️ A RESAMPLED STRAIGHT LINE IS STILL A STRAIGHT LINE. This is D66's
        end-vertex lesson applied to the interior: `interior_vertices` used to
        report every vertex in the span, so a dead-straight 2000 m run
        authored at 1 m spacing - which is exactly the shape citygen streets
        hands this tool - built 1000 DEFORMED pieces where the same line as
        two points builds 1000 packed ones (measured: 1.19 s and 360k real
        points versus instant and one shared geometryid). Zero-length
        segments are already dropped above, so a duplicated point is absorbed
        here for free. The tolerance is exact-collinearity, not a curvature
        budget: a 5000 m-radius arc resampled at 1 m still turns 2e-4 rad per
        vertex and still unpacks, which is what keeps every baseline still.
        """
        out = []
        n = len(segs)
        # the seam of a CLOSED curve is a vertex like any other: segs[-1]
        # arrives at it and segs[0] leaves it.
        for i in range(n if (closed and n > 1) else max(n - 1, 0)):
            a = _unit(segs[i][3])
            b = _unit(segs[(i + 1) % n][3])
            if _len(_sub(a, b)) > tol:
                out.append(segs[i][1])
        return out

    def sample(self, s, forward=True):
        """(position, unit tangent) at `s` metres. Mirrors `Curve.sample`."""
        if not self.segs:
            return (self.first, (0.0, 0.0, 0.0))
        total = self.total
        if self.closed and total > EPS:
            asked = s
            s = math.fmod(s, total)
            if s < 0.0:
                s += total
            if not forward and s <= EPS and asked > EPS:
                s = total
            s = min(max(s, 0.0), self.ends[-1])
        # D30: an OPEN curve is EXTRAPOLATED past either end along the end
        # segment's own direction, never clamped. Clamping looks harmless until
        # a DEFORMED piece overhangs the end: a 1.6 m gate on a marker at 19.7 m
        # of a 20.006 m curve had both of its last two stations read back the
        # same end point, and the last 0.49 m of it was crushed into a
        # zero-thickness plane (built extent 1.11 m of 1.60 m) with no warning
        # naming the fault. Overhang is legal - D20 says so for the module's own
        # geometry - so the sampler carries it instead of squashing it.
        if s < 0.0:
            i = 0
        elif s > self.ends[-1]:
            i = len(self.segs) - 1
        elif forward:
            i = bisect.bisect_right(self.ends, s + EPS)
        else:
            i = bisect.bisect_left(self.ends, s - EPS)
        i = min(max(i, 0), len(self.segs) - 1)
        lo, hi, a, d = self.segs[i]
        t = 0.0 if hi - lo < EPS else (s - lo) / (hi - lo)
        if 0.0 <= s <= self.ends[-1]:
            t = min(max(t, 0.0), 1.0)
        return ((a[0] + d[0] * t, a[1] + d[1] * t, a[2] + d[2] * t), _unit(d))

    def interior_vertices(self, s0, s1, tol=1e-7):
        """Vertex arclengths strictly inside (s0, s1). Wraps on closed.

        ⚠️ AN OPEN CURVE'S TWO END VERTICES ARE NOT KINKS (D66). D30
        extrapolates past either end ALONG THE END SEGMENT'S OWN DIRECTION, so
        nothing bends there - but a piece that legitimately overhangs the end
        contains that vertex strictly inside its span, and reading it as a
        kink unpacked the piece for a deformation that does not exist. The
        gate at 19.7 m of a 20.006 m curve was real geometry whose points fit
        a rigid transform to 1e-7 m; `over_unpacked` is what found it.

        ⚠️ AND NEITHER IS A COLLINEAR ONE (D69) - the same lesson, one vertex
        further in. `kink_s` is the vertices where the direction actually
        changes, so a resampled straight run stays packed.

        ⚠️ AND IT BISECTS (D75). `kink_s` is sorted, and scanning all of it
        per piece is quadratic in the vertex count - which nobody noticed
        while a curved run unpacked (the deform cost dwarfed it) and which
        became the whole cook the moment the curvature budget kept those
        pieces packed: 10 000 pieces against a 20 001-vertex arc spent 9.4 s
        in this loop and 0.6 s everywhere else.
        """
        out = []
        total = self.total
        reps = (0.0,) if not (self.closed and total > EPS) else (0.0, total,
                                                                -total)
        for base in reps:
            lo = bisect.bisect_right(self.kink_s, s0 + tol - base)
            hi = bisect.bisect_left(self.kink_s, s1 - tol - base)
            for v in self.kink_s[lo:hi]:
                sv = v + base
                if not self.closed and (sv <= tol or sv >= total - tol):
                    continue
                out.append(sv)
        out.sort()
        return out


class _Remap(object):
    """s on the flattened curve -> s on the real one (D26, slope fixing).

    Both curves carry the same vertices, so their cumulative tables are the
    same length and the map is piecewise linear and exact between them.
    """

    def __init__(self, flat_cum, real_cum, closed=False):
        self.flat = flat_cum
        self.real = real_cum
        self.closed = bool(closed)
        self.flat_total = flat_cum[-1] if flat_cum else 0.0
        self.real_total = real_cum[-1] if real_cum else 0.0

    def __call__(self, s):
        if self.flat_total <= EPS:
            return 0.0
        # Only a CLOSED curve wraps. On an open one the clamped index plus an
        # unclamped `t` extrapolates on the end segment, which is D30's rule
        # carried through the slope-fixing remap - wrapping there would send a
        # gate that overhangs the end back to the curve's start.
        wraps = math.floor(s / self.flat_total) if self.closed else 0.0
        s -= wraps * self.flat_total
        i = min(max(bisect.bisect_right(self.flat, s) - 1, 0),
                len(self.flat) - 2)
        span = self.flat[i + 1] - self.flat[i]
        t = 0.0 if span <= EPS else (s - self.flat[i]) / span
        return (wraps * self.real_total + self.real[i]
                + t * (self.real[i + 1] - self.real[i]))


def _identity_remap():
    return lambda s: s


# --- reading the input stream (3.1) -----------------------------------------

def _pattr(pt, name, default=None):
    try:
        return pt.attribValue(name)
    except hou.OperationFailed:
        return default


def _prattr(prim, name, default=None):
    try:
        return prim.attribValue(name)
    except hou.OperationFailed:
        return default


def _blank_to_none(value):
    return None if (value is None
                    or (isinstance(value, str) and not value.strip())) else value


# 3.3's `attr:<name>` reads the spline's OWN prim attributes, so they have to
# be harvested (D94). The `pc_` ones are excluded because the kernel already
# reads each of them by name and a second copy under `attr:` would be a second
# contract for the same value - `plan` puts `pc_section`/`pc_style` back
# deliberately, which is the pair the spec names.
_ATTR_SKIP = ("P", "N", "Cd", "uv", "v")


# 7.1's per-row contract. ⚠️ 7.1 claims these "are already harvested onto
# `Section.attrs` by D94"; they are NOT - D94 skips every `pc_` name on
# purpose, because the kernel's own attributes are not the spline's. So the
# row's six are named here, and only here, which is also what makes
# `attr:pc_yclass` a usable conditional subject. Nothing moves in phase 1: a
# curve that does not carry the attribute never gains it.
ROW_ATTRS_2D = ("pc_yclass", "pc_row", "pc_row_y0", "pc_row_y1",
                "pc_row_scale", "pc_row_warns", "pc_clipped")


def _prim_attrs(geo, prim):
    """{name: value} for one prim's own attributes, for `attr:<name>` (D94)."""
    out = {}
    for attrib in geo.primAttribs():
        name = attrib.name()
        if name in _ATTR_SKIP or (name.startswith("pc_")
                                  and name not in ROW_ATTRS_2D):
            continue
        try:
            out[name] = prim.attribValue(name)
        except (hou.OperationFailed, TypeError):
            continue
    return out


def read_curves(geo):
    """([Curve], [Marker]) off input 1. Marker points never become curves."""
    markers = []
    marker_pts = set()
    if geo is None:                     # D34: an unconnected input, not a crash
        return ([], [])
    if geo.findPointAttrib("pc_marker") is not None:
        for pt in geo.points():
            try:
                if int(pt.attribValue("pc_marker")) != 1:
                    continue
            except (TypeError, ValueError):
                continue
            marker_pts.add(pt.number())
            data = _pattr(pt, "pc_marker_data", None)
            u = _pattr(pt, "pc_u", None)
            dist = _pattr(pt, "pc_dist", None)
            # D35: 3.1's "pc_u (0-1) OR pc_dist" is a choice PER MARKER, but a
            # Houdini attribute is geometry-wide - so in a merged marker cloud
            # (3.1's own "streets-shaped carrier") every u-authored point also
            # carries pc_dist = 0.0, and `Marker.distance_on` prefers dist. A
            # u-authored gate at 0.75 of a 20 m curve silently built at s = 0.
            # A zero dist beside a real u is therefore read as the DEFAULT, not
            # as an authored 0: when both are zero the two conventions agree on
            # s = 0 anyway, so only a genuine conflict (both non-zero) is left,
            # and there dist keeps precedence as before.
            if dist is not None and u is not None and abs(dist) <= 0.0:
                dist = None
            if u is None and dist is None:
                u = 0.0
            markers.append(Marker(
                str(_pattr(pt, "pc_curve", "")),
                u=None if u is None else float(u),
                dist=None if dist is None else float(dist),
                marker_id=int(_pattr(pt, "pc_marker_id", 0) or 0),
                data=dict(data) if isinstance(data, dict) else {}))

    native = _native_tables(geo)
    has_corner = geo.findPointAttrib("pc_corner") is not None
    pt_section = geo.findPointAttrib("pc_section") is not None
    prim_section = geo.findPrimAttrib("pc_section") is not None
    curves = []
    for prim in geo.prims():
        if prim.type() == hou.primType.PackedGeometry:
            continue
        pts = prim.points()
        if len(pts) < 2:
            continue
        if any(p.number() in marker_pts for p in pts):
            continue
        # D29, and its EMPTY-STRING hole (D64): a Houdini attribute is
        # geometry-wide, so the moment ANY prim upstream carries
        # `pc_curve_id`, every other prim carries it too - with the default
        # "". Reading that as an id gave every unlabelled curve in the stream
        # the SAME id "", which collapses their `pc_elem_id`s onto each other
        # and is exactly the "unrelated upstream change" 3.4's id rule
        # forbids. A blank id is an ABSENT id.
        cid = _blank_to_none(_prattr(prim, "pc_curve_id", None))
        if cid is None:
            cid = _blank_to_none(_prattr(prim, "edge_id", None))
        if cid is None:
            cid = prim.number()
        flags = [int(_pattr(p, "pc_corner", 0) or 0) for p in pts] \
            if has_corner else None
        if pt_section:
            sections = [_pattr(p, "pc_section", 0) for p in pts]
        elif prim_section:
            sections = _prattr(prim, "pc_section", 0)
        else:
            sections = None
        try:
            closed = prim.isClosed()
        except AttributeError:
            closed = False
        positions = [p.position() for p in pts]
        curve = Curve(str(cid), positions,
                      closed=closed, corner_flags=flags,
                      section_ids=sections,
                      style_key=str(_prattr(prim, "pc_style", "") or ""),
                      attrs=_prim_attrs(geo, prim))
        curve.prim_number = prim.number()
        if native is not None:
            curve.native = _native_for(native, str(cid), positions,
                                       [p.number() for p in pts])
        curves.append(curve)
    return (curves, markers)


# --- 13.10 THE UNION: 4.1's answers, read back off the geometry -------------
#
# The asset wires `kernel` BEHIND its own DECOMPOSE box, so by the time this
# module sees a spline the 64-bit wrangles have already walked it.  Without
# this the whole VEX branch was decoration: measured on the build before it,
# every one of the six new nodes had `cookCount == 0` after an Output cook,
# bypassing all six left the output hash byte-identical, and DESTROYING all
# six left it byte-identical too.  A branch nothing cooks is not a port.
#
# D166 - THE READ IS PYTHON, AND THAT IS WHAT HANNES' RULE ALLOWS.  What moved
# to VEX is the per-element geometry work: the cumulative scan, the coincident
# merge, the turn angle and the corner threshold, all of it over N points.
# What is left here is a handful of BULK attribute reads and one slice per
# curve - marshalling data between a node and a caller, which is the second
# half of the rule.  Nothing below touches a `hou.Point` for anything but its
# number, and the standing wrapper tripwires are what keep that true.

_NATIVE_POINT_ATTRS = (("s", "pc_s", "float"), ("clean", "pc_cleanidx", "int"),
                       ("corner", "pc_iscorner", "int"),
                       ("turn", "pc_turn_deg", "float"),
                       ("degen", "pc_corner_degen", "int"),
                       ("forced", "pc_corner_forced", "int"))


def _native_tables(geo):
    """4.1's per-point answers as bulk arrays, or None when they are absent.

    `pc_nclean` is the sentinel because `pc_arclength` is the only thing that
    writes it, and it writes it on every curve it accepted.  A raw spline - a
    check calling `build` directly, a node wired straight to a curve SOP - has
    none of these, and every caller then falls through to the Python.
    """
    if geo.findPrimAttrib("pc_nclean") is None:
        return None
    out = {}
    for key, name, kind in _NATIVE_POINT_ATTRS:
        if geo.findPointAttrib(name) is None:
            return None
        out[key] = (geo.pointFloatAttribValues(name) if kind == "float"
                    else geo.pointIntAttribValues(name))
    out["cfg"] = (geo.attribValue("pc_cfg")
                  if geo.findGlobalAttrib("pc_cfg") is not None else {})
    return out


def _native_for(native, curve_id, positions, pnums):
    """One curve's slice of the native tables, in `_clean`'s own shape."""
    s, clean = native["s"], native["clean"]
    corner, turn = native["corner"], native["turn"]
    degen, forced = native["degen"], native["forced"]
    idx, pts, cum, corners = [], [], [], []
    for k, num in enumerate(pnums):
        if clean[num] >= 0:
            idx.append(k)
            pts.append(positions[k])
            cum.append(s[num])
        if corner[num]:
            corners.append(_decompose.Corner(
                curve_id, k, positions[k], turn[num],
                bool(forced[num]), bool(degen[num]), s[num]))
    return {"clean": (idx, pts, cum), "corners": corners,
            "cfg": native["cfg"]}


# --- 4.6: the override cascade (swap and replace) ---------------------------
#
# 3.4, verbatim: "Swap = re-point `pc_module`/`pc_variant` via an override
# wired upstream of finalize; replace = hero geometry keyed by `pc_elem_id`
# swapped in at finalize. Both must work WITHOUT touching the style."
#
# So both are ONE geometry stream of override points, and neither is a parm:
# a style is a rule set and an override is an exception to it, and mixing the
# two is how a one-off hero prop ends up rewriting a rule that fifty other
# elements depend on. The stream is attributes, not JSON (the citygen
# contract), and one point does both jobs - what it does depends on which
# fields are filled, so there is no `kind` enum to keep in step:
#
#   MATCH   `pc_elem_id` / `pc_module` / `pc_variant` - each blank = "any"
#   SWAP    `pc_swap_module` and/or `pc_swap_variant` -> re-points the element
#   REPLACE a PACKED PRIM on the same point -> that geometry, at the element's
#           own transform
#
# DECISIONS:
#   D57 A SWAP KEEPS THE FIT. The plan solved a span for the old module and
#       the new one is scaled into that same span, which is RailClone's own
#       segment-swap behaviour and the only one that leaves the run intact -
#       re-solving would move every other piece on the section and make an
#       override a global edit. `pc_elem_id` therefore does NOT change (D1: it
#       is a structural address, and the module is not part of the address),
#       which is what lets a swap round-trip.
#   D58 A REPLACE LANDS PACKED, at the transform the piece would have had.
#       Hero geometry is authored to the module's own fit, so bending it round
#       a corner would be inventing a deformation nobody authored. On a piece
#       that WAS deformed the hero cannot follow the curve, so it says
#       `pc_warn_replace_deformed` - warn, never block, never silently
#       straighten a bent run.
#   D63 FIRST MATCH WINS, in payload order - the same rule 3.3 uses for
#       `rules_for`. Overrides are read once and applied in order, so a
#       narrow `pc_elem_id` rule placed before a broad `pc_module` one is how
#       an artist says "all of these, except that one".

OVERRIDE_ATTRS = (("pc_elem_id", ""), ("pc_module", ""), ("pc_variant", ""),
                  ("pc_swap_module", ""), ("pc_swap_variant", ""))


class Override(object):
    __slots__ = ("elem_id", "module", "variant", "to_module", "to_variant",
                 "hero")

    def __init__(self, elem_id="", module="", variant="", to_module="",
                 to_variant="", hero=None):
        self.elem_id = elem_id
        self.module = module
        self.variant = variant
        self.to_module = to_module
        self.to_variant = to_variant
        self.hero = hero

    def matches(self, placement, module_name):
        if self.elem_id and self.elem_id != placement.elem_id:
            return False
        if self.module and self.module != module_name:
            return False
        if self.variant and self.variant != placement.variant:
            return False
        return True


def write_override(geo, elem_id="", module="", variant="", to_module="",
                   to_variant="", hero=None):
    """Author one override point. The HDA's override input and the tests use
    THIS, so the format has exactly one writer and cannot drift."""
    for name, default in OVERRIDE_ATTRS:
        if geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, default)
    if hero is not None:
        prim = geo.createPackedGeometry(hero)
        pt = prim.points()[0]
    else:
        pt = geo.createPoint()
    for name, value in (("pc_elem_id", elem_id), ("pc_module", module),
                        ("pc_variant", variant),
                        ("pc_swap_module", to_module),
                        ("pc_swap_variant", to_variant)):
        pt.setAttribValue(name, str(value))
    return pt


def read_overrides(geo):
    """[Override] off the override input, in payload order (D63).

    An unconnected input is an empty list, never an error (D34).
    """
    if geo is None:
        return []
    heroes = {}
    for prim in geo.prims():
        if prim.type() == hou.primType.PackedGeometry:
            heroes[prim.points()[0].number()] = prim.getEmbeddedGeometry()
    out = []
    for pt in geo.points():
        row = dict((name, str(_pattr(pt, name, default) or default))
                   for name, default in OVERRIDE_ATTRS)
        hero = heroes.get(pt.number())
        if hero is None and not row["pc_swap_module"] \
                and not row["pc_swap_variant"]:
            continue                       # an override that overrides nothing
        out.append(Override(row["pc_elem_id"], row["pc_module"],
                            row["pc_variant"], row["pc_swap_module"],
                            row["pc_swap_variant"], hero))
    return out


def _override_for(overrides, placement, module_name):
    for ov in overrides:
        if ov.matches(placement, module_name):
            return ov
    return None


# --- module geometry preparation --------------------------------------------

def _stations(geo, ax, tol=1e-6):
    """Sorted distinct local-x values in `geo`, relative to `ax`."""
    xs = geo.pointFloatAttribValues("P")[0::3]
    out = []
    for x in sorted(xs):
        v = x - ax
        if not out or v - out[-1] > tol:
            out.append(v)
    return out


class _Proto(object):
    """One module's geometry, measured once and reused by every placement."""

    def __init__(self, module, source):
        self.module = module
        self.source = source
        bb = source.boundingBox()
        self.ax = bb.minvec()[0]
        self.length = module.length if module.length > EPS \
            else max(bb.sizevec()[0], EPS)
        # D87 - HOW FAR THIS MODULE REACHES OFF THE SPINE, in metres. The
        # curvature budget is spent by the piece's POINTS, and only the
        # spine's sit at y = z = 0: every other point rides a frame that is
        # rebuilt station by station (`_deform_positions`), so a tall piece
        # deviates by its own radius times the frame's turn ON TOP OF the
        # sagitta. Measured off the SOURCE's bounding box rather than off
        # `pc_size`, because the nominal fitted size is a contract about the
        # fit while the bbox is the geometry that will actually move.
        self.rz = max(abs(bb.minvec()[2]), abs(bb.maxvec()[2]))
        self.ry = max(abs(bb.minvec()[1]), abs(bb.maxvec()[1]))
        # D99 - the module's own local-Y extent, which is what a top/bottom
        # BAND is measured from. Off the SOURCE bbox for the same reason `rz`
        # is: the band has to name the geometry that will actually move, not
        # the nominal fitted size.
        self.y0 = bb.minvec()[1]
        self.y1 = bb.maxvec()[1]
        # `adaptive` rolls y AND z with the frame; a yaw-only mode keeps y
        # world-vertical (`_frame`), so there only z rides it.
        self.radius = math.hypot(self.ry, self.rz)
        self.stations = _stations(source, self.ax)
        # the same stations as fractions of the fit length - what 4.5's two
        # probes sample on, so the conform gate and the conform deform read
        # the same places (D71).
        self.fracs = tuple(s / self.length for s in self.stations) \
            if self.length > EPS else ()
        self._sliced = {}

    def sliced(self, slice_t):
        """The module cut at local x = ax + slice_t * length, hole capped."""
        key = round(float(slice_t), 9)
        if key in self._sliced:
            return self._sliced[key]
        xcut = self.ax + key * self.length
        cut = hou.Geometry()
        clip = _verb("clip")
        clip.setParms({"origin": (xcut, 0.0, 0.0),
                       "dir": (1.0, 0.0, 0.0), "clipop": 1})
        clip.execute(cut, [self.source])
        filled = hou.Geometry()
        pfill = _verb("polyfill")
        pfill.setParms({"fillmode": 0})
        pfill.execute(filled, [cut])
        # D28: the cap is every prim that lies ENTIRELY in the cut plane.
        # Measured on 22.0.398: a new prim from `polyfill` inherits its
        # neighbour's attribute values, NOT the attribute default, so tagging
        # by "what polyfill added" reads 0 on the cap it just made. The plane
        # test is a property of the geometry instead of a property of the SOP.
        filled.addAttrib(hou.attribType.Prim, "pc_cap", 0)
        for prim in filled.prims():
            pts = prim.points()
            if pts and all(abs(p.position()[0] - xcut) <= 1e-5 for p in pts):
                prim.setAttribValue("pc_cap", 1)
        dress_caps(filled, self.module.name, _texel(self.source))
        out = (filled, _stations(filled, self.ax))
        self._sliced[key] = out
        return out


# --- 4.6: the cap, dressed --------------------------------------------------

CAP_ATTR = "pc_cap"
CAP_MATERIAL_ATTR = "pc_cap_material"


def _texel(source):
    """Metres per UV unit of a module's OWN mapping, or 1.0 when it has none.

    4.6 says the cap is box-mapped "from the module's mapping", which is a
    statement about DENSITY: a cap whose texels are twice the size of the
    walls beside it reads as a different material, and that is the defect this
    number exists to avoid. Measured off the source rather than declared -
    the ratio of its UV extent to its geometric extent - so a kit that halves
    its texel size needs no manifest edit.
    """
    if source is None:
        return 1.0
    attrib = source.findVertexAttrib("uv") or source.findPointAttrib("uv")
    if attrib is None:
        return 1.0
    try:
        uvs = (source.vertexFloatAttribValues("uv")
               if source.findVertexAttrib("uv") is not None
               else source.pointFloatAttribValues("uv"))
    except hou.OperationFailed:
        return 1.0
    if not uvs:
        return 1.0
    du = max(uvs[0::3]) - min(uvs[0::3])
    bb = source.boundingBox()
    dx = bb.sizevec()[0]
    if du <= EPS or dx <= EPS:
        return 1.0
    return dx / du


def dress_caps(geo, module_name="", texel=1.0, local_attr=None):
    """Box-UV every `pc_cap` prim and tag it with the cap material (D59).

    The cap plane is perpendicular to the module's own +X (D20), so the box
    projection for it is (local z, local y) - no axis choice to get wrong and
    no seam, because a cap is one planar polygon. `local_attr` names the point
    attribute holding module-local coordinates: `_Proto.sliced` still IS in
    local space and passes None, while a world-space miter cut carries
    `pc_local` through the clip and passes that.
    """
    if geo.findPrimAttrib(CAP_ATTR) is None:
        return geo
    # the FLAGS in bulk, then a wrapper for the handful of prims that are
    # caps - never one per prim to ask a question an array answers. On the
    # 100-building district this loop built 18 880 `hou.Prim` wrappers to find
    # 6 400 caps (11.9 rule 1, and the same P7 as `clip_plane`'s cap test).
    flags = geo.primIntAttribValues(CAP_ATTR)
    caps = [i for i, v in enumerate(flags) if v == 1]
    if not caps:
        return geo
    if geo.findPrimAttrib(CAP_MATERIAL_ATTR) is None:
        geo.addAttrib(hou.attribType.Prim, CAP_MATERIAL_ATTR, "")
    if geo.findVertexAttrib("uv") is None:
        geo.addAttrib(hou.attribType.Vertex, "uv", (0.0, 0.0, 0.0))
    inv = 1.0 / texel if texel > EPS else 1.0
    name = "%s_cap" % module_name if module_name else "pc_cap"
    col = list(geo.primStringAttribValues(CAP_MATERIAL_ATTR))
    for i in caps:
        col[i] = name
    geo.setPrimStringAttribValues(CAP_MATERIAL_ATTR, col)
    for i in caps:
        prim = geo.prim(i)
        for vtx in prim.vertices():
            pt = vtx.point()
            local = pt.position()
            if local_attr is not None:
                try:
                    local = pt.attribValue(local_attr)
                except hou.OperationFailed:
                    pass
            vtx.setAttribValue("uv", (local[2] * inv, local[1] * inv, 0.0))
    return geo


# --- the frames -------------------------------------------------------------

def _frame(tangent, zmode, up_ref=UP):
    """(dir, across, up) for one sample. `across` is +Z when dir is +X.

    `up_ref` is 4.5's CAMBER (D55): hand it the surface normal and the frame
    rolls onto the surface, because `up` is rebuilt as `cross(across, d)` and
    `across` is what `up_ref` decides. With the default it is world up and
    this is byte-for-byte the frame every earlier cycle measured. Only the
    `adaptive` branch reads it - a yaw-only mode is PLUMB BY DEFINITION and a
    picket that leans with the camber is not a picket (D55, D27's precedent).
    """
    if zmode == "adaptive":
        d = _unit(tangent)
        across = _cross(d, up_ref)
        if _len(across) < EPS:
            across = (0.0, 0.0, 1.0)
        else:
            across = _unit(across)
        return (d, across, _cross(across, d))
    d = _unit((tangent[0], 0.0, tangent[2]))
    return (d, (-d[2], 0.0, d[0]), UP)


def _transport(frame, prev_across):
    """D31 - the frame carried along the piece instead of re-derived per point.

    `_frame` builds `across` from cross(tangent, UP), which has no memory: the
    moment the tangent's HORIZONTAL direction reverses - an overhanging crest,
    a cliff lip, a loop - `across` flips 180 degrees mid-piece and the piece
    twists through itself. Measured on a panel over the crest
    (0,0,0)->(2,3,0)->(1,6,0): the built across vector between two adjacent
    stations 0.25 m apart had dot -0.0036 on two 0.06 m vectors, an exact
    reversal, and every other check stayed green.

    Flipping `across` alone would leave a left-handed frame, so `up` flips with
    it - two of three axes, which preserves the handedness.
    """
    d, across, up = frame
    if prev_across is None:
        return frame
    if (across[0] * prev_across[0] + across[1] * prev_across[1]
            + across[2] * prev_across[2]) >= 0.0:
        return frame
    return (d, (-across[0], -across[1], -across[2]),
            (-up[0], -up[1], -up[2]))


def span_ends(path, sa, sb, ends=None):
    """The two reads every span-shaped question in this file starts with.

    A span is asked about six times per piece - `_flat_ratio`, `_chord_ratio`,
    `span_deviation`, `_needs_deform`'s shear test, `_packed_transform` and
    the plan position - and each of them opened with the SAME forward hit at
    `sa` and backward hit at `sb`. Measured on the 20 km / 10 000-piece packed
    row (PC-G3's own shape and the citygen street shape): **130 000
    `Path.sample` calls, 13.00 per piece, at exactly two distinct arguments**.
    Pass A now takes the pair once and threads it, which is P3's idea applied
    to the branch P3 did not reach - bounded, no cache, nothing retained.

    `ends is None` samples, so every out-of-tree caller (the checks call four
    of these directly) keeps working and is only slower.
    """
    if ends is not None:
        return ends
    return (path.sample(sa), path.sample(sb, forward=False))


def _flat_ratio(path, sa, sb, zmode, ends=None):
    """D32 - how much of a planned span survives yaw-flattening, 0..1.

    A yaw-only z-mode measures the piece along the horizontal, so a vertical
    span leaves nothing to scale by. It used to build silently: a 3 m vertical
    curve produced 25 posts of 0.0000 m along-axis width, stacked coincident,
    with `warns=[]`. The onset is continuous (0.0852 m at 45 degrees, 0.0021 m
    at 89) so this is a RATIO, not a special case for exactly vertical.
    """
    span = abs(sb - sa)
    if zmode == "adaptive" or span <= EPS:
        return 1.0
    (a, _ta), (b, _tb) = span_ends(path, sa, sb, ends)
    return math.hypot(b[0] - a[0], b[2] - a[2]) / span


def _chord_ratio(path, sa, sb, ends=None):
    """How much of a planned span the straight chord across it covers.

    A rigid piece cuts every corner by design, but a SUPPRESSED HAIRPIN turns
    that into an order-of-magnitude collapse: a 2.5 m beam asked to cover 4 m
    of a there-and-back polyline materialised 0.10 m long, 2.5 % of its span,
    silently. Below `COLLAPSE_RATIO` the piece is still built (never block) and
    carries WARN_CORNER_DEGENERATE, whose own meaning - the corner degenerated
    - is exactly the cause.
    """
    span = abs(sb - sa)
    if span <= EPS:
        return 1.0
    (a, _ta), (b, _tb) = span_ends(path, sa, sb, ends)
    return _len(_sub(b, a)) / span


COLLAPSE_RATIO = 0.5        # chord vs planned span, for a RIGID piece
FLAT_RATIO = 0.01           # horizontal reach vs planned span, yaw-only modes


def _band(proto, zmode, params):
    """D99 - the module-local Y interval that is the flat-top/bottom BAND.

    None when there is no band to apply, which is every case the suite
    measured before this existed: no side chosen, a zero height, an
    `adaptive` piece (it rides the full frame, so it has no flat half to
    hold), or a band that reaches neither into the module nor across it.

    The interval is returned in the module's OWN local Y, which is also world
    metres: the fit scales a piece along x only, so a band named in metres is
    the same band before and after the solve.
    """
    side = getattr(params, "flat_band", "")
    size = float(getattr(params, "flat_band_m", 0.0) or 0.0)
    if side not in ("top", "bottom") or size <= EPS or zmode == "adaptive":
        return None
    if size >= (proto.y1 - proto.y0) + EPS:
        # the band swallows the module: the piece is simply the other mode,
        # which is what "all of it" means. Still a band, so the caller's
        # deform gate sees it.
        return (proto.y0 - 1.0, proto.y1 + 1.0)
    if side == "top":
        return (proto.y1 - size, proto.y1 + 1.0)
    return (proto.y0 - 1.0, proto.y0 + size)


def _follows(y, band, stepped):
    """Does the point at local height `y` FOLLOW the ground? (D99)

    One expression for both of iToo's hybrids, because they are the same
    rule seen from the two z-modes: the band is the exception. Outside a
    band, `vertical` follows and `stepped` does not - which is byte-for-byte
    what this file did before D99, since `band` is None on every path that
    has no band.
    """
    inside = band is not None and band[0] <= y <= band[1]
    return inside == stepped


def _stepped_base(path, sa, sb, fracs, flatten, pick=min):
    """D98 - the ONE elevation a `stepped` piece sits flat at.

    OFF (RailClone's default, and every baseline before D98) it is the
    elevation at the piece's own start, which is what "constant Z" meant in
    4.4 and what leaves the downhill end of every piece floating.

    ON it is the LOWEST ground under the piece's own span, sampled at the
    module's own stations - the places the deform already samples (D71), so
    the flatten and the deform read the same ground. That is the flatten-under
    4.4 names: the underside touches at its low point and nothing hangs in
    the air, and because a minimum does not care which end it started from,
    the same fence comes out of a reversed spline.

    D105 - `pick` is which extremum, because a D99 LEVEL BAND on a plumb
    piece is the same question asked upside down. A stepped piece is planted
    UNDER itself, so it takes the minimum; a level TOP band is a rail held
    over the piece, so it takes the maximum and never dips below the body it
    caps. Either way it is an extremum over the piece's own span, which is
    what makes it independent of the direction the spline was drawn - the
    whole reason D98 exists.
    """
    y = path.sample(sa)[0][1]
    if not flatten:
        return y
    span = sb - sa
    for f in (fracs or (0.0, 0.5, 1.0)):
        y = pick(y, path.sample(sa + f * span)[0][1])
    return pick(y, path.sample(sb, forward=False)[0][1])


def _y_varies(path, sa, sb, fracs):
    """Does the ground move under this span at all? Metres of range."""
    lo = hi = path.sample(sa)[0][1]
    span = sb - sa
    for f in (tuple(fracs or ()) + (1.0,)):
        y = path.sample(sa + f * span)[0][1]
        lo, hi = min(lo, y), max(hi, y)
    return hi - lo


def span_deviation(path, sa, sb, radius=0.0, zmode="adaptive",
                   normal_at=None, fracs=None, ends=None):
    """D75 + D87 - how far the DEFORMED piece would sit from the PACKED
    one, in metres, measured at its WORST POINT.

    THE CURVATURE BUDGET. D69 fixed the exact-collinear case and said so; what
    it left standing is that the vertex test is BINARY. A resampled GENTLE ARC
    - which is exactly the shape citygen streets hands this tool, since a
    street curve is a resampled polyline - has a real interior vertex in every
    span, so every piece unpacked for a deformation that rounds to nothing.
    Measured before this: a 1 m-resampled R = 12 000 m arc unpacked 8 of 150
    pieces for 4.2e-05 m of movement, BELOW 4.6's own `over_unpacked`
    tolerance, and that check FAILED on it; at PC-G3 scale the same shape cost
    727 packed / 9 278 deformed / 334 735 points / +130 MB / 18.9 s against a
    straight run's 10 005 packed / +12 MB / 0.55 s.

    So the question is not "is there a vertex" but "does the vertex MOVE
    anything". A packed piece is the chord A->B (`_packed_transform`); a
    deformed one puts the point at fraction `f` of its span at arc position
    `sa + f*(sb - sa)` (`_deform_positions`). The difference between those two
    positions IS the deformation the unpack would buy, and on a POLYLINE it is
    extremal at a vertex - so the interior vertices are not a sample of the
    span, they are the exact answer for it. Above `bend_tol` the piece bends;
    below it, the artist has already said that much error is acceptable
    (`bend_tol` is the same parm D25's resolution warning is measured against)
    and the piece stays packed.

    D87 - AND IT IS MEASURED AT THE PIECE'S WORST POINT, NOT ON ITS SPINE.
    D75 shipped the sagitta only, which is the exact answer for a point at
    y = z = 0 and an UNDER-COUNT for every other point in the module: the
    deformed piece rotates a frame per station, so a point `radius` metres off
    the spine also swings by the chord of that rotation. Measured on a 1.2 m
    tall bendable rail over an R = 55 m elevation arc resampled at 1 m: all 30
    of 30 pieces stayed PACKED on a 0.0091 m spine reading while their true
    worst point had moved 0.0327 m - 3.3x `bend_tol`, adjacent pieces meeting
    with a visible wedge at their top corners. `radius` is 0 by default, which
    is exactly D75's measure, and `_needs_deform` passes the module's own.

    Note this is measured on the PATH the piece is built on, conform included
    when there is one - a `ConformPath` samples the drape - so the ridge case
    that `Surface.deviates` exists for is not weakened by it.

    D100 - AND THE CAMBER'S OWN ROTATION IS IN IT NOW. `normal_at` is 4.5's
    per-station surface normal (D55), i.e. exactly what `_deform_positions`
    reads when the camber is on; the packed piece takes ONE normal, the
    span's midpoint (`_packed_transform`). Everything above measures the
    PATH's turn, so a run whose path is dead straight and dead flat while the
    cross-fall UNDER it rolls - `y = k*x*z` along z = 0 is the clean form -
    spent nothing, stayed packed, and was wrong by whatever the roll times
    the radius came to: swept, a cross-fall changing by 1 % per metre kept
    10 of 10 panels packed at 0.0109 m of true deviation, 1.1x `bend_tol`,
    and 20 % per metre kept them packed at 0.2126 m, 21x. With `normal_at`
    the term is the FULL frame rotation between the two - trace of the
    relative rotation, so the tangent turn and the camber roll are measured
    once together rather than added twice - and the tangent-only reading is
    what it degrades to when there is no camber, which is every case that
    was measured before this.

    D104 - AND IT IS SAMPLED WHERE THE DEFORM REBUILDS THE FRAME, NOT ONLY AT
    THE SPLINE'S KINKS. D100 read the camber only at [sa, interior vertices,
    sb]; `_deform_positions` rebuilds a frame at every MODULE STATION (D71,
    D31), so a cross-fall whose roll inflects BETWEEN those samples was
    invisible. Measured: a surface `y = 0.2 sin(pi x) z` - a superelevation
    transition whose roll is zero at every 2 m piece boundary and at every
    midpoint - left 10 of 10 panels PACKED at 0.197164 m of true deviation,
    19.7x `bend_tol`, and a 1 m-resampled spline was defeated identically
    because the ripple's own period put a zero-roll vertex on every kink. So
    `fracs` (the module's own stations as fractions of the fit, `_Proto.fracs`)
    are folded into BOTH walks - the spine one and the frame-rotation one.
    They are folded only when `normal_at` is given, which keeps the whole
    no-camber path, and therefore every pre-D104 baseline, byte-identical:
    on a polyline the spine term is linear between vertices, so the extra
    stations can only find what the camber roll put there.
    """
    span = sb - sa
    if abs(span) <= EPS:
        return 0.0
    verts = path.interior_vertices(sa, sb)
    if not verts and radius <= EPS:
        return 0.0                       # the chord IS the arc (D66/D69)
    if normal_at is not None and fracs and radius > EPS:
        # D104 - the deform's own stations, merged in arc order and deduped
        # against the kinks so a station landing on a vertex is not counted
        # twice (which would pair a frame with a zero-width span).
        merged = sorted(list(verts)
                        + [sa + f * span for f in fracs if f > 0.0])
        verts, last = [], sa
        for sv in merged:
            if sv - last > EPS and sb - sv > EPS:
                verts.append(sv)
                last = sv
    (a, ta), (b, _tb) = span_ends(path, sa, sb, ends)
    ab = _sub(b, a)
    # THE SPINE TERM, at every kink - extremal there because the polyline and
    # the chord it is measured against are both linear in between. The two
    # ends sit ON the chord by construction, and they are in the list because
    # the off-spine term below pairs each frame with the span it holds over.
    spine = [0.0]
    for sv in verts:
        f = (sv - sa) / span
        p = path.sample(sv)[0]
        spine.append(_len((p[0] - a[0] - ab[0] * f,
                           p[1] - a[1] - ab[1] * f,
                           p[2] - a[2] - ab[2] * f)))
    spine.append(0.0)
    worst = max(spine)
    if radius <= EPS:
        return worst
    # THE OFF-SPINE TERM (D87). `_deform_positions` builds its frame from the
    # FORWARD tangent at each station and `_packed_transform` builds one from
    # the chord, so a point `radius` metres off the spine is displaced by the
    # chord of that rotation, 2*r*sin(theta/2). Sampled at the span's start,
    # at every kink, and at its END - and the end is not decoration: at a
    # piece boundary the forward tangent is the NEXT segment's, which is
    # where the worst reading on the R = 55 m elevation arc came from
    # (0.0327 m against a 0.0091 m sagitta, three times the budget, and all
    # of it in this term).
    flat = zmode != "adaptive"
    ref = _unit((ab[0], 0.0, ab[2]) if flat else ab)
    if _len(ref) < EPS:
        return worst
    # D100 - the frame the PACKED piece is built on, camber included. `None`
    # keeps every pre-camber reading byte-identical: the loop then compares
    # tangent directions exactly as D87 did.
    packed = None
    if normal_at is not None:
        packed = _frame(ab if not flat else (ab[0], 0.0, ab[2]), zmode,
                        normal_at(0.5 * (sa + sb)))
    samples = [sa] + list(verts) + [sb]
    for k, s in enumerate(samples):
        # `samples[0]` IS `sa`, read forward - the tangent the pair above
        # already carries, so this is the same call with the same argument.
        t = ta if k == 0 else path.sample(s)[1]
        t = _unit((t[0], 0.0, t[2]) if flat else t)
        if _len(t) < EPS:
            continue
        if packed is None:
            dot = max(-1.0, min(1.0, ref[0] * t[0] + ref[1] * t[1]
                                + ref[2] * t[2]))
            ang = math.acos(dot)
        else:
            # the FULL rotation between the deformed station's frame and the
            # packed piece's one, from the trace of the relative rotation:
            # tr(R) = 1 + 2 cos(theta) for a rotation of orthonormal triads.
            here = _frame(t, zmode, normal_at(s))
            tr = sum(here[j][c] * packed[j][c]
                     for j in range(3) for c in range(3))
            ang = math.acos(max(-1.0, min(1.0, 0.5 * (tr - 1.0))))
        # this frame holds from its own sample to the next one, so the spine
        # term it rides is the larger of that interval's two ends
        near = max(spine[k], spine[k + 1]) if k + 1 < len(spine) else spine[k]
        worst = max(worst, near
                    + 2.0 * radius * math.sin(0.5 * ang))
    return worst


def _needs_deform(placement, proto, path, sa, sb, zmode, tol=0.01,
                  band=None, normal_at=None, ends=None):
    """4.4 + the streets float32 lesson: rebuild ONLY when it changes something."""
    if placement.slice_t is not None or placement.cuts:
        return True                                     # D41 - a miter unpacks
    if placement.anchor is not None:
        return False                                    # a straight leg piece
    if proto.module.deform <= 0:
        return False                                    # D27
    # D99: a BAND is a per-point rule - half the piece flat, half of it
    # following - and a packed prim is one 4x4, so a band that has ground to
    # bite on is a deform by construction. `stepped` is the case this exists
    # for: without it a stepped piece with a deforming foot stayed packed and
    # the band did nothing. `vertical` reaches the same answer one test lower
    # (its own shear test), so this only makes the reason explicit.
    if band is not None and _y_varies(path, sa, sb, proto.fracs) > 1e-6:
        return True
    # D87: the budget is spent by the piece's WORST POINT, not by its spine.
    # `radius` is how far this module reaches off the spine onto the frame
    # that `_deform_positions` rebuilds per station; it is 0 for a module with
    # no cross-section, which is the spine-only measure D75 shipped.
    if span_deviation(path, sa, sb,
                      proto.radius if zmode == "adaptive" else proto.rz,
                      zmode, normal_at, proto.fracs, ends) > tol:
        return True                              # D75, D87, D100, D104
    # 4.5: A DEAD-STRAIGHT SPLINE OVER A RIDGE HAS NO INTERIOR VERTEX, so
    # without this the test above says "nothing to follow" and a bendable rail
    # crosses the hill as one rigid chord with its two ends on the ground.
    # `deviates` measures the drape against that chord, so a piece on a
    # UNIFORM slope - where the drape IS the chord - still stays packed, which
    # is 4.6's segregation surviving the conform rather than being defeated by
    # it. `stepped` is excluded because sitting flat is the mode (4.5's own
    # "stepped sits on it").
    if zmode != "stepped" and getattr(path, "deviates", None) is not None             and path.deviates(sa, sb, tol, fracs=proto.fracs):
        return True
    if zmode == "vertical":
        (a, _ta), (b, _tb) = span_ends(path, sa, sb, ends)
        return abs(b[1] - a[1]) > 1e-6                  # a sheared span
    return False


def _bend_deviation(proto, stations, path, s0_flat, scale, remap, at=None):
    """D25 - how far the built piece cuts the corner, in metres.

    11.2 P3. This sampled the path THREE TIMES PER GAP - 24 per piece against
    the deform's own 10 - and two of the three were the same two station
    positions read twice: gap i's end is gap i+1's start. So each station is
    sampled ONCE and the gaps share it: 2n-1 samples instead of 3n-3, and n
    `remap` calls instead of 2n-2.

    ⚠️ ONE SEMANTIC CHANGE, AND IT IS THE RISK IN THIS ITEM: the gap's END
    used to be read BACKWARD (`forward=False`) and is now the next station's
    FORWARD read. The two differ only at a vertex, and only in the TANGENT -
    which this function never asks for.

    ⚠️ AND THE POSITIONS ARE NOT BIT-IDENTICAL, WHICH THIS USED TO CLAIM. The
    measurement it claimed it from was taken on PC-G3's arc, which is
    axis-aligned with round coordinates and happens to be exact; on general
    geometry the backward branch lands on the PREVIOUS segment with t clamped
    to 1.0 and returns `a + d*1.0`, which is only float-exactly `pts[k]` when
    the two endpoints are within a factor of 2 (Sterbenz). Re-measured over
    the vertex arclengths of seven curves - open, closed, diagonal, hairpin,
    climbing, sub-millimetre: **166 arclengths, 2 differing, worst |dP|
    4.4e-16 m**; an independent sweep of seven other curves read 344 / 74 /
    7.1e-15 m. That is double-precision ULP on a segment endpoint - seven
    orders below `bend_tol` and below `bend_deviation_m`'s own `_round(dev,
    9)` - so the change is safe, but the two reads are NOT interchangeable and
    a future agent must not treat them as such. **`path_read_direction_m`**
    (checks.py) is that measurement standing up as an assertion, ceiling
    1e-12 m: ULP is fine, metres would be a dropped sub-EPS segment.

    What proves it on every case is that this is a WARNING, so `warn_summary`
    and `warnings` pin the per-case `pc_warn_bend_resolution` counts, and
    **`bend_deviation_m`** (checks.py) pins the number itself.

    `at` is an optional dict the caller passes to COLLECT the station samples
    (`{s: (pos, tan)}`) so the deform pass can read them back instead of
    re-deriving the same expression - the other half of P3.
    """
    n = len(stations)
    if n < 2:
        return 0.0
    ss = [remap(s0_flat + st * scale) for st in stations]
    ps = [None] * n
    worst = 0.0
    for i in range(n - 1):
        s_a, s_b = ss[i], ss[i + 1]
        if s_b - s_a <= EPS:
            continue
        for j in (i, i + 1):
            if ps[j] is None:
                hit = path.sample(ss[j])
                ps[j] = hit[0]
                if at is not None:
                    at[ss[j]] = hit
        pa, pb = ps[i], ps[i + 1]
        pm = path.sample(0.5 * (s_a + s_b))[0]
        mid = (0.5 * (pa[0] + pb[0]), 0.5 * (pa[1] + pb[1]),
               0.5 * (pa[2] + pb[2]))
        worst = max(worst, _len(_sub(pm, mid)))
    return worst


# --- building one piece -----------------------------------------------------

def _packed_transform(proto, path, sa, sb, zmode, up_ref=UP, base_y=None,
                      ends=None, yscale=1.0):
    """The 4x4 that maps module local space onto the chord A->B (D21).

    `base_y` is D98's flatten-under: a `stepped` piece is horizontal, so its
    whole elevation is one number and overriding it here moves the piece
    without touching the fit, the frame or the chord it was measured on.

    `yscale` is E2 / D121 - the ROW's band height over the module's nominal
    height, applied to the frame's UP axis. 4.6's instancing rule is
    "transform x uniform-or-axis scale of the kit module stays a packed prim",
    and an axis scale is on the allowed side of that sentence by its own
    wording, so **a scaled storey stays packed** and PC-G3's property survives
    into 2D. It is 1.0 on every 1D build, where this is the identity.
    """
    (a, ta), (b, _tb) = span_ends(path, sa, sb, ends)
    chord = _sub(b, a)
    clen = _len(chord)
    if zmode != "adaptive":
        flat = (chord[0], 0.0, chord[2])
        flen = _len(flat)
        # D32: when yaw-flattening leaves less than FLAT_RATIO of the 3D chord
        # there is nothing left to scale by, and scaling by it produced a
        # 1e-9 sliver - invisible geometry that no check could see. Keep the 3D
        # length so the piece stays VISIBLE; `_flat_ratio` has already stamped
        # WARN_DEGENERATE_FRAME on it, so it is visible in the warning
        # visualisation too.
        chord = flat
        clen = flen if flen >= FLAT_RATIO * clen else clen
    if clen < EPS:                       # a zero-length span still gets a frame
        d, across, up = _frame(ta, zmode, up_ref)
        clen = 0.0
    else:
        d, across, up = _frame(chord, zmode, up_ref)
    scale = max(clen / proto.length, 1e-9)
    ox = proto.ax * scale
    ay = a[1] if base_y is None else base_y
    return hou.Matrix4([
        [d[0] * scale, d[1] * scale, d[2] * scale, 0.0],
        [up[0] * yscale, up[1] * yscale, up[2] * yscale, 0.0],
        [across[0], across[1], across[2], 0.0],
        [a[0] - d[0] * ox, ay - d[1] * ox, a[2] - d[2] * ox, 1.0]])


def _anchor_transform(proto, origin, direction, length, zmode, up_ref=UP,
                      yscale=1.0):
    """4.3 - the 4x4 for a piece built on a STRAIGHT leg instead of on the path.

    A mitered corner piece does not ride the curve: it rides the leg, extended
    PAST the vertex so the bisector cut can leave its outside face at full
    length (D38). Sampling the curve out there would walk it round the corner
    and bend the very piece the miter exists to keep straight.
    """
    d, across, up = _frame(direction, zmode, up_ref)
    scale = max(length / proto.length, 1e-9) if proto.length > EPS else 1.0
    ox = proto.ax * scale
    return hou.Matrix4([
        [d[0] * scale, d[1] * scale, d[2] * scale, 0.0],
        [up[0] * yscale, up[1] * yscale, up[2] * yscale, 0.0],
        [across[0], across[1], across[2], 0.0],
        [origin[0] - d[0] * ox, origin[1] - d[1] * ox,
         origin[2] - d[2] * ox, 1.0]])


def _drop_anchor(path, anchor):
    """4.5: a 4.3 anchor is a SPLINE vertex, so it is dropped like everything
    else. Off a conformed path this is the identity.

    ⚠️ ONE DATUM PER ASSEMBLY, AND IT IS THE CORNER VERTEX (D72). Dropping
    each half's OWN anchor put the two halves of one mitered corner post on
    different elevations, because they start at different places on their
    legs - the in half `t_far` back down the arriving leg, the out half at the
    vertex. On the suite's own 25 % ramp the two cut faces came out
    y[2.98..4.28] against y[3.00..4.30], a 0.02 m step at a seam PC-G1 asks
    to be gapless; with a 1.2 m corner module the same construction shelves
    them 0.28 m apart. The assembly is ONE rigid object cut in two, so it
    gets ONE drop - which is the same thing D48's `flatten` already does in
    the other axis by putting both anchors at the vertex elevation.
    """
    surface = getattr(path, "surface", None)
    origin = anchor[0]
    if surface is None or not surface.active:
        return origin
    datum = anchor[3] if len(anchor) > 3 and anchor[3] is not None else origin
    dropped, _n, ok = surface.drop(datum)
    if not ok:
        return origin
    return (origin[0] + dropped[0] - datum[0],
            origin[1] + dropped[1] - datum[1],
            origin[2] + dropped[2] - datum[2])


def _anchor_len(placement):
    """The anchored piece's own geometric length.

    ⚠️ NOT `s1 - s0`. On a PITCHED leg 4.3 lays the corner assembly out in
    yaw-flattened metres (D48) - that is the space a `stepped` or `vertical`
    piece is built in - while `s` stays arc length, so the two differ by
    `1/cos(pitch)`. The anchor carries the geometric number; a placement from
    before the third field falls back to the span.
    """
    anchor = placement.anchor
    if anchor is not None and len(anchor) > 2 and anchor[2] is not None:
        return float(anchor[2])
    return placement.length


def clip_plane(geo, origin, normal, keep_sign, module_name="", texel=1.0):
    """Cut `geo` on a WORLD half-space and cap the hole. Returns new geometry.

    D28's machinery, lifted out of module-local space. The `clip` verb keeps
    the side OPPOSITE its `dir` (measured on 22.0.398, and `corner_plane_dev_m`
    is what asserts it: a flipped keep-side deletes the piece instead of
    mitering it). The cap is found by the plane test for the same reason it is
    in `_Proto.sliced` - a prim `polyfill` creates inherits its neighbour's
    attribute values, not the attribute default.
    """
    away = normal if keep_sign < 0 else (-normal[0], -normal[1], -normal[2])
    cut = hou.Geometry()
    clip = _verb("clip")
    clip.setParms({"origin": tuple(float(v) for v in origin),
                   "dir": tuple(float(v) for v in away), "clipop": 1})
    clip.execute(cut, [geo])
    if not cut.intrinsicValue("primitivecount"):
        return cut
    n_cut = cut.intrinsicValue("primitivecount")
    filled = hou.Geometry()
    pfill = _verb("polyfill")
    pfill.setParms({"fillmode": 0})
    pfill.execute(filled, [cut])
    if filled.findPrimAttrib("pc_cap") is None:
        filled.addAttrib(hou.attribType.Prim, "pc_cap", 0)
    # ⚠️ 11's UNATTEMPTED P7, AND AT FACADE SCALE IT IS THE BIGGEST ITEM IN
    # THE ROW. This used to be `for prim in filled.prims(): pts =
    # prim.points(); ... p.position() ...` - a plane test on every point of
    # every prim through wrappers. Phase 1 pays it 8 times per rectangle;
    # phase 2 pays it per vertex PER ROW, so a 100-building district reached
    # 156 000 `hou.Prim` wrappers and 198 408 `Point.position` calls here
    # alone - 46 % of the whole build, and invisible to
    # `points_wrappers_built`, which spies `hou.Geometry.points` and never
    # sees a read through `hou.Prim`.
    #
    # `polyfill` APPENDS its patches contiguously at the tail - PROBED, not
    # assumed (`polyfill_appends_its_patches` is the standing check, and it
    # compares the tail against this very plane test on a three-hole cut), so
    # the caps are exactly `[n_cut:]` and the tag is one bulk write of a list
    # nobody had to look at any geometry to build.
    #
    # ⚠️ AND IT IS AN **OR**, NOT AN ASSIGNMENT. A default piece is cut at
    # BOTH ends as soon as a leg is shorter than twice the miter overhang (a
    # 1.5 m equilateral triangle does it), and the first cut's `pc_cap` rides
    # through the second `clip` on the verb's own attribute promotion. The
    # old per-prim loop only ever SET the flag, so overwriting the column
    # cleared the first cap - `corner_face_mate_m` on `AI_triangle` went from
    # 1.29e-07 to 0.0352 m, which is what that check is for.
    n_all = filled.intrinsicValue("primitivecount")
    if n_all > n_cut:
        col = list(filled.primIntAttribValues("pc_cap"))
        col[n_cut:] = [1] * (n_all - n_cut)
        filled.setPrimIntAttribValues("pc_cap", col)
    # the miter cap is in WORLD space, so its box UV is read off `pc_local`,
    # which rode through the clip on the verb's own attribute promotion.
    dress_caps(filled, module_name, texel,
               local_attr="pc_local"
               if filled.findPointAttrib("pc_local") is not None else None)
    return filled


def _deform_positions(src, proto, path, s0_flat, scale, zmode, remap,
                      tilt=False, base_y=None, band=None, samples=None,
                      yscale=1.0):
    """Every point of `src` re-read at its own arc position. Returns
    (flat world positions, flat local positions).

    `base_y` (D98) is the flat elevation a `stepped` point sits at, and
    `band` (D99) is the module-local Y interval that takes the OTHER mode.
    Both default to exactly what this did before they existed.

    11.2 P3's other half: `samples` is the `{s: (pos, tan)}` the WARNING pass
    already built for this piece (`_bend_deviation`, pass A). Its stations are
    the module's own, which is where this reads too, so the hits are the same
    `path.sample(s)` call with the same argument - bit-identical by
    construction, not by tolerance. A MISS just samples, so a piece whose
    warning pass did not run (a rigid module never reaches it) is slower and
    never wrong.
    """
    local = src.pointFloatAttribValues("P")
    out = [0.0] * len(local)
    hit = samples.get(remap(s0_flat)) if samples else None
    if base_y is None:
        base_y = (hit[0][1] if hit is not None
                  else path.sample(remap(s0_flat))[0][1])
    stepped = zmode == "stepped"
    ax = proto.ax
    # D31: one frame per STATION, transported along the piece in x order, then
    # looked up per point. Deriving it per point independently is what let it
    # flip mid-piece; doing it per station also drops the sampler calls from
    # one-per-point to one-per-station.
    frames, prev = {}, None
    normal_at = getattr(path, "normal", None) if tilt else None
    for x in sorted(set(local[0::3])):
        s_x = remap(s0_flat + (x - ax) * scale)
        hit = samples.get(s_x) if samples else None
        pos, tan = hit if hit is not None else path.sample(s_x)
        prev_across = None if prev is None else prev[1]
        # D55: the camber is read PER STATION, so a bent rail rolls along the
        # surface instead of taking one roll from its start.
        up_ref = normal_at(s_x) if normal_at is not None else UP
        frame = _transport(_frame(tan, zmode, up_ref), prev_across)
        frames[x] = (pos, frame)
        prev = frame
    for i in range(0, len(local), 3):
        x, y, z = local[i], local[i + 1], local[i + 2]
        pos, (d, across, up) = frames[x]
        # E2 - the band scale rides the LOCAL y only, so D99's band test still
        # asks the module's own question in the module's own metres and the
        # geometry still fills the row's band exactly.
        sy = y * yscale
        if zmode == "adaptive":
            out[i] = pos[0] + across[0] * z + up[0] * sy
            out[i + 1] = pos[1] + across[1] * z + up[1] * sy
            out[i + 2] = pos[2] + across[2] * z + up[2] * sy
        else:
            py = pos[1] if _follows(y, band, stepped) else base_y
            out[i] = pos[0] + across[0] * z
            out[i + 1] = py + sy
            out[i + 2] = pos[2] + across[2] * z
    return (out, local)


# --- output attributes ------------------------------------------------------

KIT_WARN_ATTR = "pc_kit_warnings"

# 4.2's "the plan is inspectable geometry", as a point schema. Named
# separately from ELEM_PRIM_ATTRS because a plan point is not an element: it
# carries the SOLVE (s0/s1/scale/slice) rather than the built prim's stamps.
PLAN_POINT_ATTRS = (
    ("pc_elem_id", ""), ("pc_slot", ""), ("pc_module", ""), ("pc_variant", ""),
    ("pc_zmode", ""), ("pc_elem_key", 0), ("pc_section", 0), ("pc_index", 0),
    ("pc_deform", 0), ("pc_plan", 1), ("pc_s0", 0.0), ("pc_s1", 0.0),
    ("pc_u", 0.0), ("pc_scale", 1.0), ("pc_slice_t", -1.0),
)


WARN_SUMMARY_ATTR = "pc_warnings"


def _collate_warnings(geo, jobs):
    """D61 - 4.6's "collate warnings", as a detail array of "name:count".

    The per-element attributes are the truth and stay exactly as they were;
    what they could not answer is "did this cook warn about anything, and how
    much" without walking every prim of a 10k-element run. One middle click
    now says `pc_warn_bend_resolution:3`, which is the whole point of
    persisting warnings rather than printing them.
    """
    counts = {}
    for job in jobs:
        for w in job["warns"]:
            counts[w] = counts.get(w, 0) + 1
    if geo.findGlobalAttrib(WARN_SUMMARY_ATTR) is None:
        geo.addArrayAttrib(hou.attribType.Global, WARN_SUMMARY_ATTR,
                           hou.attribData.String)
    geo.setGlobalAttribValue(WARN_SUMMARY_ATTR,
                             tuple("%s:%d" % (k, counts[k])
                                   for k in sorted(counts)))
    return counts


def _kit_warnings(geo, warns):
    """3.4 + the suite constraint: warnings are PERSISTED, not returned.

    Per-element warnings ride on their own prim; the kit-level class had
    nowhere to live and died with the Python call, so a kit missing `kitId` or
    carrying a duplicate module name cooked clean forever. This is that class,
    as a detail string array - one attribute, readable by a middle click.
    """
    if geo.findGlobalAttrib(KIT_WARN_ATTR) is None:
        geo.addArrayAttrib(hou.attribType.Global, KIT_WARN_ATTR,
                           hou.attribData.String)
    geo.setGlobalAttribValue(KIT_WARN_ATTR, tuple(str(w) for w in warns))


def plan_points(geo, report):
    """4.2's debuggability contract: one point per PLACEMENT, at its own start
    on the curve, carrying `plan_dicts()`'s payload.

    The plan is the stage between the kernel and the geometry, and until this
    existed it lived only inside one Python call - nothing to middle-click when
    a fill comes out wrong, and nothing for 5's plan-preview-while-dragging to
    draw. Written into a SEPARATE geometry, never merged with the build: a
    plan point is not an element. The HDA reaches it through its `display`
    menu rather than through a second output (D81).
    """
    rows = _plan.plan_dicts(report.get("plan") or [])
    pos = report.get("plan_pos") or [(0.0, 0.0, 0.0)] * len(rows)
    for name, default in PLAN_POINT_ATTRS:
        if geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, default)
    if not rows:
        return geo
    # 11.2 P1 again: 15 point attributes, one `setAttribValue` each, once per
    # placement. `Display = Plan` is the INTERACTIVE preview and it cooked
    # 1.55 s against the 0.93 s full build it previews, which is the whole
    # reason. Built the way `_stamp_bulk` builds the prim stamp: one column
    # per attribute, one call each.
    base = geo.intrinsicValue("pointcount")
    geo.createPoints([tuple(float(v) for v in p) for p in pos[:len(rows)]])
    for name, default in PLAN_POINT_ATTRS:
        src = {"pc_index": "index", "pc_s0": "s0", "pc_s1": "s1",
               "pc_scale": "scale", "pc_deform": "pc_deform",
               "pc_slice_t": "slice_t"}.get(name, name)
        if name == "pc_plan":
            col = [1] * len(rows)
        elif name == "pc_slice_t":
            col = [-1.0 if row["slice_t"] is None else float(row["slice_t"])
                   for row in rows]
        elif isinstance(default, str):
            col = [str(row.get(src, default)) for row in rows]
        elif isinstance(default, int):
            col = [int(row.get(src, default)) for row in rows]
        else:
            col = [float(row.get(src, default)) for row in rows]
        # The `if base` guard `_stamp_bulk` has, for its reason: with an
        # empty `geo` - which is every caller - the read pulled a whole column
        # through HOM only to slice it to `[]`, and the `+` copied the new one
        # again.
        if isinstance(default, str):
            if base:
                col = list(geo.pointStringAttribValues(name))[:base] + col
            geo.setPointStringAttribValues(name, col)
        elif isinstance(default, int):
            if base:
                col = list(geo.pointIntAttribValues(name))[:base] + col
            geo.setPointIntAttribValues(name, col)
        else:
            if base:
                col = list(geo.pointFloatAttribValues(name))[:base] + col
            geo.setPointFloatAttribValues(name, col)
    return geo


# 7.3.3's new stamps. Declared ONLY when a 2D build produced a cell, so a
# phase-1 output keeps exactly the schema `output_schema` has always pinned.
ELEM_2D_ATTRS = (("pc_cell", ""), ("pc_yclass", ""), ("pc_array", ""),
                 ("pc_row", -1), ("pc_clipped", 0))


def _declare(geo, warn_names, cells=False):
    for name, default in ELEM_PRIM_ATTRS + (ELEM_2D_ATTRS if cells else ()):
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, default)
    for name in warn_names:
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, 0)


def _stamp_values(placement, warns, deformed, zmode, replaced=False):
    """3.4's stamp as (name, value) pairs - one description, two writers.

    D102: the per-prim writer below and the BULK writer are the same list, so
    a stamp added to one cannot go missing from the other. `_stamp` is the
    REFERENCE - one prim, 14 `Prim.setAttribValue` calls - and `_stamp_bulk`
    is what the build actually runs, over the whole output at once
    (11.2 P1). `stamp_parity` compares them on all 89 cases.

    ⚠️ D102's own `_stamp_geo` - the per-PIECE bulk writer - is gone: with
    P1 accumulating across the whole output there is no piece-sized write
    left, and leaving a third writer in place would have left `stamp_parity`
    comparing two paths the build no longer takes.
    """
    eid = placement.elem_id
    return (
        ("pc_elem_id", eid),
        ("pc_elem_key", elem_key(eid)),
        ("pc_slot", placement.slot),
        ("pc_module", placement.module),
        ("pc_variant", placement.variant),
        ("pc_section", int(placement.section_index)),
        ("pc_u", float(placement.u)),
        ("pc_zmode", zmode),
        ("pc_generated", 1),
        ("pc_deformed", 1 if deformed else 0),
        ("pc_corner_cut", 1 if placement.cuts else 0),
        ("pc_curve_id", str(placement.curve_id)),
        ("pc_style", str(placement.style_id)),
        ("pc_replaced", 1 if replaced else 0),
    ) + _stamp_2d(placement) + tuple((w, 1) for w in warns)


def _stamp_2d(placement):
    """7.3.3 - volume / storey / face / bay, by ADDRESS COMPOSITION (D123).

    `pc_elem_id` does not change shape and `elem_id()` is not touched: the two
    halves of `pc_curve_id` are the volume and the storey, `pc_section` is the
    face (on a closed footprint a section IS a facade leg) and the index is
    the bay. These four are the READABLE form of that, and they are absent -
    not blank - on a 1D build.
    """
    if not placement.cell:
        return ()
    array, _sep, row = str(placement.curve_id).partition("#")
    row = row.split(".")[0]
    return (("pc_cell", placement.cell), ("pc_yclass", placement.yclass),
            ("pc_array", array), ("pc_row", int(row) if row.isdigit() else -1),
            ("pc_clipped", int(getattr(placement, "clipped", 0))))


def _stamp(prim, placement, warns, deformed, zmode, replaced=False):
    for name, value in _stamp_values(placement, warns, deformed, zmode,
                                     replaced):
        prim.setAttribValue(name, value)


_BLANK = {"s": "", "i": 0, "f": 0.0}


def _stamp_bulk(geo, rows, warn_names, base=0):
    """D102's bulk stamp, applied to the WHOLE OUTPUT - 11.2 P1.

    D102 did this for one deformed PIECE at a time; the packed branch - which
    is what PC-G3's headline row and every citygen street actually runs - kept
    the per-prim writer, and it was measured as **62 % of the real node cook**:
    14 `hou.Prim.setAttribValue` calls at 2.19 us, once per packed piece.

    Same fix, one level up. Pass B accumulates `(prim count, stamp values)`
    per piece in build order and this writes one array per attribute over the
    finished geometry.

    ⚠️ THE ARRAYS MUST LINE UP WITH `out`'s PRIM NUMBERING, which is why the
    count travels with the values rather than being assumed: a corner-cut
    piece goes through `clip` and `polyfill` and comes out with a prim count
    nothing upstream knows. `base` is the prim count `out` already carried
    when pass B started - zero for every caller in the tree, and read back
    from the geometry rather than defaulted so a caller-supplied `out` keeps
    its own stamps instead of being blanked.

    `_declare` has already run on `geo` (pass A), so every name exists,
    including the warn attributes - which is what lets an element that did
    NOT warn take a plain 0 here instead of needing its own branch.
    """
    if not rows:
        return
    names, kind = [], {}
    for _n, values in rows:
        for name, value in values:
            if name not in kind:
                names.append(name)
                kind[name] = ("s" if isinstance(value, str)
                              else "i" if isinstance(value, int) else "f")
    for name in warn_names:                     # warned on no element at all
        if name not in kind:
            names.append(name)
            kind[name] = "i"
    get = {"s": geo.primStringAttribValues, "i": geo.primIntAttribValues,
           "f": geo.primFloatAttribValues}
    put = {"s": geo.setPrimStringAttribValues,
           "i": geo.setPrimIntAttribValues,
           "f": geo.setPrimFloatAttribValues}
    # ⚠️ ONE COLUMN LIVE AT A TIME. Accumulating across the whole output is
    # what makes this 2x faster than the per-prim writer, but materialising
    # all fifteen columns at once and only then writing them cost **+97 MB of
    # peak working set (61 %)** on the 340 000-prim deformed row - a real
    # regression that nothing measured, since the ONLY consumer of a column is
    # its own `put`. `rows` is the compact form (one piece, one (name, value)
    # tuple list, ~10 000 of them), so expanding per name keeps a single
    # 339 864-entry list live instead of fifteen. `stamp_bulk_peak_kb` pins it.
    rows = [(n, dict(values)) for n, values in rows]
    for name in names:
        k = kind[name]
        blank = _BLANK[k]
        col = []
        for n, values in rows:
            col.extend([values.get(name, blank)] * n)
        # `base` is 0 for every caller in the tree, and neither the read nor
        # the concatenation is free: unguarded, the read pulled ~15 full
        # columns of 339 864 values through HOM and sliced every one to `[]`
        # (0.062 s of a 1.40 s row) and the `+` copied the column again. The
        # docstring's reason for the read is preserved exactly - when there is
        # no head there is nothing to keep.
        if base:
            col = list(get[k](name))[:base] + col
        put[k](name, col)


# --- the pipeline -----------------------------------------------------------

def _resolve_zmode(placement):
    """The kernel has ALREADY applied D6 (`plan._zmode`: a non-empty style
    zmode overrides every module), so this only guards the vocabulary - an
    unknown value falls back to `adaptive` instead of building nothing. Doing
    the override again here would be a second copy of a kernel decision."""
    return placement.zmode if placement.zmode in Z_MODES else "adaptive"


def _prepare(curve, params, surface_geo=None, surface=None):
    """(kernel curve, Path on the REAL curve, flat->real remap, fillet warns).

    4.5 wraps the Path and nothing else (D54): every stage below this one asks
    the same two questions of the same object, so the drape reaches the
    frames, the deform, the plan positions and the checks at once.

    4.3's FILLET runs FIRST and replaces the curve outright (D42): decompose,
    plan and place then all run on the rounded path, so 4.2's section lengths
    are recomputed from the real filleted arc instead of being corrected after
    the fact. Slope fixing (D26) composes on top of the rounded curve, not
    under it - the flattened copy is taken from whatever path the pieces will
    actually sit on.
    """
    curve, fillet_warns = _corner.fillet(curve, params)
    path, _surface = _conform.wrap(Path(curve), surface_geo, params, surface)
    if not params.fix_slope:
        return (curve, curve, path, _identity_remap(), fillet_warns)
    flat = Curve(curve.curve_id,
                 [(p[0], 0.0, p[2]) for p in curve.points],
                 closed=curve.closed, corner_flags=curve.corner_flags,
                 section_ids=curve.section_ids, style_key=curve.style_key,
                 attrs=curve.attrs)
    return (flat, curve, path, _Remap(flat._cumulative(), curve._cumulative(),
                                      curve.closed), fillet_warns)


def analyse(curve_geo, params=DEFAULTS, kit=None, style=None,
            surface_geo=None):
    """[{curve, real, path, remap, sections}] - what `build` decomposes,
    exposed so the scene checks measure against the same sections the builder
    used instead of re-deriving them (and re-deriving them differently).

    `curve` is what the KERNEL planned on and `real` is what the geometry is
    built on - both AFTER the fillet, which replaces the curve outright. Under `fix_slope` they are different curves (D26) and a check
    that conflates them measures the slope instead of the builder.

    Pass `kit` and `style` to get the 4.3 stage too: the sections come back
    WELDED where bend mode welded them (D36), carrying `fill_a`/`fill_b`, and
    each track carries the solved `bevels`. Without them the sections are the
    raw 4.1 output, which is a different list the moment a corner exists.
    """
    curves, markers = read_curves(curve_geo)
    out = []
    for curve in sorted(curves, key=lambda c: str(c.curve_id)):
        kcurve, real, path, remap, fillet_warns = _prepare(curve, params,
                                                           surface_geo)
        sections = _decompose.decompose(kcurve, markers, params)
        bevels = []
        if style is not None:
            _p, bevels, sections = _corner.plan_curve(kcurve, sections, kit,
                                                      style, params)
        out.append({"curve": kcurve, "real": real, "path": path,
                    "remap": remap, "sections": sections, "bevels": bevels,
                    "fillet_warns": fillet_warns})
    return out


def build(curve_geo, kit_geo, style, params=None, out=None,
          surface_geo=None, overrides=None, report_frames=False):
    """Curves + kit -> placed geometry. Never raises (warn-never-block).

    Returns (geometry, report) where the report carries the plan, the kit
    validation warnings and the counts the scene checks record.
    """
    params = params or (style.params if style is not None else None) or DEFAULTS
    out = out if out is not None else hou.Geometry()
    kit, sources, kit_warns = _kit.read(kit_geo)
    curves, markers = read_curves(curve_geo)
    overrides = read_overrides(overrides)

    protos = {}

    def proto_for(module):
        if module.name not in protos:
            protos[module.name] = _Proto(
                module, _kit.source_for(sources, module))
        return protos[module.name]

    # --- pass A: plan, and decide deform/warnings before anything is built --
    jobs = []
    bevels = []
    all_sections = []
    bend_worst = 0.0
    # D74: two curves with one id share every `pc_elem_id` they produce. The
    # ids are left alone (renaming would move an address an override may
    # already name); what changes is that it is no longer silent.
    id_count = {}
    for c in curves:
        id_count[str(c.curve_id)] = id_count.get(str(c.curve_id), 0) + 1
    # ONE `Surface` for the whole build, not one per curve: its constructor
    # reads the terrain's bounding box, and 300 conformed streets read the
    # same 80 352-prim box 300 times. `wrap` takes it or makes its own.
    shared_surface = _conform.Surface(
        surface_geo, getattr(params, "conform_axis", (0.0, -1.0, 0.0)))
    # 11.2 P5, corrected: pass A is split in two so the conform batch can be
    # taken ONCE FOR THE BUILD instead of once per curve. `ray` rebuilds its
    # surface input on every execution (0.34 ms at 5 022 prims, 2.25 ms at
    # 80 352), so per-curve batching made the citygen row SLOWER than not
    # batching at all - see `conform.prefetch_all`.
    plans = []
    for curve in sorted(curves, key=lambda c: str(c.curve_id)):
        kcurve, _real, path, remap, fillet_warns = _prepare(curve, params,
                                                            surface_geo,
                                                            shared_surface)
        # 13.8 rule 1 - the NATIVE stage and the reference must be asked the
        # same question in the SAME process, so the report has to say which
        # curve each `Path` is on and whether that curve is still the one the
        # artist wired in. A filleted, slope-flattened or conformed path is a
        # DIFFERENT polyline, and a native wrangle reading the input spline's
        # arclength table would be answering about a curve that does not
        # exist. `pc_raw` is that flag; `frames_parity` refuses to compare
        # where it is False rather than comparing something else.
        path.pc_curve_id = str(curve.curve_id)
        path.pc_raw = bool(
            not isinstance(path, _conform.ConformPath)
            and _real.closed == curve.closed
            and _real.points == curve.points)
        if id_count.get(str(curve.curve_id), 0) > 1:
            fillet_warns = tuple(fillet_warns) + (WARN_CURVE_ID_DUP,)
        sections = _decompose.decompose(kcurve, markers, params)
        # 4.3 owns everything between the section list and the fill: it welds
        # what bend must not break (D36), places the corner slot, and hands
        # each section the span the corners left it.
        placements, curve_bevels, sections = _corner.plan_curve(
            kcurve, sections, kit, style, params)
        # 7.1 - the ROW's own two numbers, off the row prim. `yclass` has
        # already reached the fitting solve through `Section.attrs` (D94); this
        # is where every placement of the row - the corner assembly's included,
        # which never passes through `plan._module_warns` - gets its `pc_cell`
        # and D118's fallback warning. Blank on every 1D curve.
        yclass = str(curve.attrs.get("pc_yclass", "") or "")
        # D138 - the row carries its BAND and the piece scales its own nominal
        # height into it. `pc_row_scale` is the ROW's number (band / the height
        # of the module the Y solve chose) and it is right only while the cell
        # is filled by that same module - which stops being true the moment
        # D118's lattice walk puts a 3.2 m bay in a 1.0 m cornice band, and
        # then the cornice row overshoots the roof by 2.2 m with every other
        # number in the suite still green (measured, `row_fill_y_m`). The band
        # is the truth; `pc_row_scale` is the fallback for a module that
        # declares no height at all.
        row_band = (float(curve.attrs.get("pc_row_y1", 0.0) or 0.0)
                - float(curve.attrs.get("pc_row_y0", 0.0) or 0.0)) \
            if "pc_row_y1" in curve.attrs else 0.0
        row_scale = float(curve.attrs.get("pc_row_scale", 1.0) or 1.0)
        _plan.classify(placements, kit, yclass,
                       str(curve.attrs.get("pc_row_warns", "") or "").split(),
                       int(curve.attrs.get("pc_clipped", 0) or 0))
        bevels.extend(curve_bevels)
        all_sections.extend(sections)
        by_section = dict((sec.index, sec) for sec in sections)
        spans = []
        if getattr(path, "plan_keys", None) is not None:
            for p in placements:
                section = by_section.get(p.section_index)
                if section is None:
                    continue
                ov = _override_for(overrides, p, p.module)
                mname = (ov.to_module if (ov is not None and ov.to_module)
                         else p.module)
                module = kit.by_name(mname) or stand_in(mname)
                spans.append((remap(section.s0 + p.s0),
                              remap(section.s0 + p.s1),
                              proto_for(module).fracs))
        plans.append((path, remap, placements, by_section, fillet_warns,
                      spans, row_band, row_scale))

    # ...and the batch, once, before ANY placement asks anything. It is a
    # cache fill and nothing else - every key it misses is served by the
    # per-query Python path exactly as before, so this is additive.
    _conform.prefetch_all([(pl[0], pl[5]) for pl in plans if pl[5]])

    for (path, remap, placements, by_section, fillet_warns, _spans,
         row_band, row_scale) in plans:
        for p in placements:
            section = by_section.get(p.section_index)
            if section is None:
                continue
            # D57: the SWAP happens here, before anything is measured or
            # built, so the new module's own deform class, length and zmode
            # are what the rest of the pass reasons about - and `pc_module`
            # stamps the module that is actually in the output.
            ov = _override_for(overrides, p, p.module)
            swapped = ov is not None and bool(ov.to_module)
            if swapped:
                p.module = ov.to_module
            if ov is not None and ov.to_variant:
                p.variant = ov.to_variant
            module = kit.by_name(p.module) or stand_in(p.module)
            swap_warns = []
            if swapped:
                # ...WHICH MEANS RE-DERIVING WHAT THE PLAN DERIVED FROM THE
                # OLD MODULE (D73), because two of those survived the
                # re-pointing and described a module that is no longer there:
                #
                #  * the Z-MODE. `plan._zmode` is D6's cascade - the style
                #    wins, else the module's own manifest default - and it ran
                #    against the OLD module, so a panel->post swap under an
                #    empty style zmode built and stamped every post
                #    `vertical`, the panel's mode. Re-run the same cascade, so
                #    an UNSWAPPED placement is byte-identical and a swapped
                #    one obeys 3.2's "per-module default, style-overridable".
                #  * the SLICE. 4.2 cuts a tile remainder only when the module
                #    allows it (`pc_deform == 2`); the fraction is a fraction
                #    of THAT module's length. Swapping a 1.6 m sliceable gate
                #    to a rigid 0.12 m post kept `slice_t = 0.125` and cut the
                #    post at 0.125 of 0.12 m, filling 0.015 m of a 0.2 m span
                #    and leaving a silent 0.185 m hole at the end of the run.
                #    The run cannot be re-solved (D57 - a swap is an exception
                #    to a rule, not a global edit), so the placement takes
                #    D11's OTHER answer instead: the whole module is scaled
                #    into the span it was given, and it says WARN_TILE_FALLBACK.
                p.zmode = _plan._zmode(module, params)
                if p.slice_t is not None and module.deform < 2:
                    p.slice_t = None
                    swap_warns.append(WARN_TILE_FALLBACK)
            proto = proto_for(module)
            yscale = (row_band / module.size[1]
                      if row_band > EPS and module.size[1] > EPS
                      else row_scale)
            zmode = _resolve_zmode(p)
            # flat = the space the kernel planned in; real = the curve it
            # is built on. They differ only under fix_slope (D26).
            s0f, s1f = section.s0 + p.s0, section.s0 + p.s1
            s0r, s1r = remap(s0f), remap(s1f)
            # `span_ends`, taken ONCE for this piece. Anchored pieces are
            # excluded because not one consumer of the pair runs for them
            # (D72 lays a corner assembly out on its own vertex), and asking
            # a `ConformPath` for a drop nothing needed would grow the memo
            # `conform_cache_per_element` pins.
            ends = None if p.anchor is not None else (
                path.sample(s0r), path.sample(s1r, forward=False))
            warns = list(p.warns)
            for w in swap_warns:
                if w not in warns:
                    warns.append(w)
            for w in fillet_warns:
                if w not in warns:
                    warns.append(w)
            if module.missing and WARN_KIT_GAP not in warns:
                warns.append(WARN_KIT_GAP)
            band = _band(proto, zmode, params)
            # D100: the camber's own rotation is part of the budget, so the
            # per-station normal has to reach `_needs_deform` - which means
            # deciding the tilt BEFORE the deform gate rather than after it.
            tilt = bool(module.tilts(params) and zmode == "adaptive")
            deformed = _needs_deform(p, proto, path, s0r, s1r, zmode,
                                     params.bend_tol, band,
                                     getattr(path, "normal", None)
                                     if tilt else None, ends)
            # 4.5 / D53: a ray that finds nothing keeps the spline elevation
            # and SAYS SO. Probed on the piece's own span rather than on the
            # whole run, so a fence that leaves the terrain at one end reports
            # exactly the pieces that hang in the air.
            if getattr(path, "missed", None) is not None \
                    and path.missed(s0r, s1r, fracs=proto.fracs) \
                    and WARN_CONFORM_MISS not in warns:
                warns.append(WARN_CONFORM_MISS)
            scale = 1.0 if p.slice_t is not None else (
                ((s1f - s0f) / proto.length) if proto.length > EPS else 1.0)
            if p.anchor is None and _flat_ratio(path, s0r, s1r, zmode,
                                                ends) < FLAT_RATIO:
                warns.append(WARN_DEGENERATE_FRAME)          # D32
            if p.anchor is None and not deformed \
                    and _chord_ratio(path, s0r, s1r, ends) < COLLAPSE_RATIO \
                    and WARN_CORNER_DEGENERATE not in warns:
                warns.append(WARN_CORNER_DEGENERATE)         # D32, rigid
            # 11.2 P3: the warning pass's station samples are kept for the
            # DEFORM pass, which asks the same sampler the same question at
            # the same arclengths. Only for a piece that will actually be
            # deformed and unanchored - i.e. only where pass B has a consumer.
            station_hits = None
            if p.anchor is None and deformed and module.deform > 0:
                stations = (proto.sliced(p.slice_t)[1]
                            if p.slice_t is not None else proto.stations)
                station_hits = {}
                dev = _bend_deviation(proto, stations, path, s0f, scale,
                                      remap, station_hits)
                # D25's number, not just its verdict. Found by mutation while
                # 11.2 P3 landed: moving the deviation probe 1 mm changed NOT
                # ONE value in the whole suite - `curvature_budget_m` and
                # `deform_gate_m` record the BOOLEAN's consequences, not this -
                # because only the boolean it feeds was ever recorded and 1 mm
                # does not cross `bend_tol`.
                # A warning whose measurement nothing pins is a warning any
                # refactor can quietly re-aim. `bend_deviation_m` reads it.
                bend_worst = max(bend_worst, dev)
                if dev > params.bend_tol:
                    warns.append(WARN_BEND_RESOLUTION)
            hero = ov.hero if (ov is not None and ov.hero is not None) else None
            if hero is not None and deformed and WARN_REPLACED not in warns:
                warns.append(WARN_REPLACED)             # D58
            # D98 - the flatten-under datum, decided once per piece and used
            # by ALL THREE materialisation paths - packed, deformed, and the
            # D58 HERO REPLACEMENT, which was reading the spline's own
            # elevation and floating a replaced piece one full piece-drop
            # above its planted neighbours (0.490874 m on the suite's hill).
            # Anchored pieces are excluded on purpose: 4.3 gives ONE datum to
            # a whole corner assembly (D72), and a per-half minimum would
            # reopen the 0.02 m step at the seam PC-G1 asks to be gapless.
            # D105 - and it reaches the D99 LEVEL BAND of a PLUMB piece too.
            # Without this the band took its one elevation from the piece's
            # START (`_deform_positions`' own default), so a "level top rail"
            # moved by the drop across a piece when the spline was drawn the
            # other way - 0.490874 m on the suite's own hill - and the parm
            # that promises direction independence did not reach it.
            # `packed_y` is the datum a RIGID piece takes: `stepped` only,
            # because a banded piece has no one elevation to place by.
            base_y = packed_y = None
            if p.anchor is None                     and getattr(params, "flatten_stepped", False):
                if zmode == "stepped":
                    base_y = packed_y = _stepped_base(
                        path, s0r, s1r, proto.fracs, True)
                elif band is not None:
                    base_y = _stepped_base(
                        path, s0r, s1r, proto.fracs, True,
                        max if getattr(params, "flat_band", "") == "top"
                        else min)
            jobs.append({"p": p, "proto": proto, "path": path, "hero": hero,
                         "yscale": yscale,
                         "s0f": s0f, "s0r": s0r, "s1r": s1r,
                         "zmode": zmode, "scale": scale, "band": band,
                         "base_y": base_y, "packed_y": packed_y,
                         "deformed": deformed, "warns": tuple(warns),
                         "remap": remap, "tilt": tilt, "ends": ends,
                         # the plan position, taken off the pair now so pass B
                         # can drop the pair itself the moment it is consumed
                         # - `stamp_rows` is already the build's memory high
                         # water mark and `ends` would sit beside it.
                         "pos0": (ends[0][0] if ends is not None
                                  else path.sample(s0r)[0]),
                         "stations": station_hits})

    warn_names = []
    for job in jobs:
        for w in job["warns"]:
            if w not in warn_names:
                warn_names.append(w)
    warn_names.sort()
    # ⚠️ WHEN THE CALLER ACCUMULATES, DO NOT BUILD ON TOP OF ITS HEAD.
    # `_stamp_bulk` has to hand `setPrim*AttribValues` the WHOLE column, so
    # `build(out=...)` made every call re-read and re-write every prim every
    # earlier call had written - O(n^2) on the documented accumulation path,
    # and 51 % of a 100-building district (5.20 s against 1.81 s for the same
    # work). This call's pieces go into a staging geometry, are stamped once
    # at base 0, and are merged into the caller's geometry as one block.
    # An EMPTY `out` - every caller in the tree and every committed case -
    # takes the identical path it always took, so no baseline value can move.
    target = out
    if out.intrinsicValue("primitivecount"):
        out = hou.Geometry()
    _declare(out, warn_names, cells=any(j["p"].cell for j in jobs))

    # --- pass B: materialise -----------------------------------------------
    # 11.2 P1: the stamp is ACCUMULATED here and written once at the end -
    # `(prim count, values)` per piece, in build order, so the arrays line up
    # with `out`'s own prim numbering after every merge.
    n_packed = n_deformed = n_cut = n_replaced = 0
    stamp_rows = []
    # the COUNT, not the wrappers: `len(geo.prims())` materialises a tuple of
    # `hou.Prim` objects, and on the deformed branch it ran once per piece -
    # 0.090 s of a 1.40 s row, 6.4 %, the 3rd-largest built-in in the profile,
    # for a number `intrinsicValue` hands over for free (measured 24x cheaper
    # on the real 34-prim piece). `stamp_parity` and `output_schema` pin that
    # the two agree.
    stamp_base = out.intrinsicValue("primitivecount")
    for job in jobs:
        p, proto, path = job["p"], job["proto"], job["path"]
        zmode, warns = job["zmode"], job["warns"]
        ends = job.pop("ends", None)            # consumed here, not retained
        up_ref = UP
        normal_at = getattr(path, "normal", None) if job["tilt"] else None
        if normal_at is not None:
            # the MIDPOINT normal for a rigid piece: its two ends can sit on
            # different facets, and rolling to one end's facet tips the far
            # end into the ground.
            up_ref = normal_at(0.5 * (job["s0r"] + job["s1r"]))
        job["up_ref"] = up_ref          # 13.8 - pass B's own answer, recorded
        if job["hero"] is not None:
            # D58: hero geometry lands PACKED at the transform this element
            # would have had - the same 4x4 a rigid piece gets, so a replaced
            # gate sits exactly where the gate sat. A piece that WAS deformed
            # has no single transform, so it takes the chord's and says so.
            xform = (_anchor_transform(proto, _drop_anchor(path, p.anchor),
                                       p.anchor[1], _anchor_len(p), zmode,
                                       up_ref, job["yscale"])
                     if p.anchor is not None
                     else _packed_transform(proto, path, job["s0r"],
                                            job["s1r"], zmode, up_ref,
                                            job["packed_y"], ends,
                                            job["yscale"]))
            prim = out.createPackedGeometry(job["hero"])
            prim.setTransform(xform)
            stamp_rows.append(
                (1, _stamp_values(p, warns, False, zmode, replaced=True)))
            n_packed += 1
            n_replaced += 1
            continue
        if not job["deformed"]:
            if p.anchor is not None:
                # 4.3 lays a corner assembly out on the SPLINE's own vertex, so
                # without this the corner post of a conformed fence hangs at
                # spline elevation while every piece beside it sits on the
                # terrain. The anchor is dropped; its direction is left alone,
                # because an anchored piece is rigid on its leg by definition.
                xform = _anchor_transform(proto, _drop_anchor(path, p.anchor),
                                          p.anchor[1], _anchor_len(p), zmode,
                                          up_ref, job["yscale"])
            else:
                xform = _packed_transform(proto, path, job["s0r"],
                                          job["s1r"], zmode, up_ref,
                                          job["packed_y"], ends,
                                          job["yscale"])
            prim = out.createPackedGeometry(proto.source)
            prim.setTransform(xform)
            stamp_rows.append((1, _stamp_values(p, warns, False, zmode)))
            n_packed += 1
            continue
        src = proto.sliced(p.slice_t)[0] if p.slice_t is not None \
            else proto.source
        piece = hou.Geometry()
        piece.merge(src)
        if piece.findPointAttrib("pc_local") is None:
            piece.addAttrib(hou.attribType.Point, "pc_local", (0.0, 0.0, 0.0))
        if p.anchor is not None:
            # 4.3: a corner piece is rigid on its leg, so its local frame is
            # the module's own and the transform is baked rather than sampled.
            local = list(src.pointFloatAttribValues("P"))
            piece.transform(_anchor_transform(
                proto, _drop_anchor(path, p.anchor), p.anchor[1],
                _anchor_len(p), zmode, up_ref, job["yscale"]))
            # AFTER the transform, never before: `hou.Geometry.transform`
            # carries any attribute Houdini reads as a vector along with P, and
            # a rotated `pc_local` would make every local-frame check measure
            # the world instead of the module.
            piece.setPointFloatAttribValues("pc_local", local)
        else:
            world, local = _deform_positions(piece, proto, path, job["s0f"],
                                             job["scale"], zmode,
                                             job["remap"], job["tilt"],
                                             job["base_y"], job["band"],
                                             job.pop("stations", None),
                                             job["yscale"])
            piece.setPointFloatAttribValues("P", world)
            piece.setPointFloatAttribValues("pc_local", local)
        if p.cuts:
            # the bisector cut, in WORLD space. `pc_local` rides through the
            # clip on the verb's own attribute promotion, so the checks can
            # still recover the piece's frame from the mitered half.
            for (origin, normal, keep) in p.cuts:
                piece = clip_plane(piece, origin, normal, keep,
                                   proto.module.name, _texel(proto.source))
            n_cut += 1
        stamp_rows.append((piece.intrinsicValue("primitivecount"),
                           _stamp_values(p, warns, True, zmode)))
        out.merge(piece)
        n_deformed += 1

    _stamp_bulk(out, stamp_rows, warn_names, stamp_base)
    if out is not target:
        target.merge(out)
        out = target
    _kit_warnings(out, kit_warns)
    counts = _collate_warnings(out, jobs)
    report = {
        "warn_counts": counts,
        "replaced": n_replaced,
        "overrides": len(overrides),
        "plan": [j["p"] for j in jobs],
        "plan_pos": [j["pos0"] for j in jobs],
        # 13.3.4's frame inputs, as the reference actually computed them.
        # ⚠️ OFF BY DEFAULT (D171). It is instrumentation, its only consumers
        # are `cook_plan_bridge` and the parity rig, and it is not free:
        # measured on the packed 10k fixture it is 10 000 dicts of 11 keys,
        # 4.96 MB by recursive `getsizeof` and 0.0031 s of a 0.2239 s build,
        # allocated and thrown away on every cook of a node nobody has put on
        # the Plan stage. It grows with N4/N5, so it asks before it rides.
        "frames": ([{"s0r": j["s0r"], "s1r": j["s1r"], "zmode": j["zmode"],
                     "proto_len": j["proto"].length, "proto_ax": j["proto"].ax,
                     "base_y": j["packed_y"], "yscale": j["yscale"],
                     "up_ref": tuple(j.get("up_ref", UP)),
                     "curve_id": getattr(j["path"], "pc_curve_id", None),
                     "raw": bool(getattr(j["path"], "pc_raw", False)),
                     "anchored": j["p"].anchor is not None}
                    for j in jobs] if report_frames else []),
        "kit_warnings": kit_warns,
        "curves": len(curves),
        "markers": len(markers),
        "packed": n_packed,
        "deformed": n_deformed,
        "corner_cuts": n_cut,
        "bevels": bevels,
        "sections": all_sections,
        "warn_names": warn_names,
        "bend_deviation": bend_worst,
    }
    return (out, report)
