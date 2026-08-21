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
  D29 Curve identity: `pc_curve_id`, else `edge_id` (the streets id, which
      3.1 says feeds `pc_elem_id`), else the primitive number - always
      normalised to a string, because `pc_elem_id` is a string address (D1).
"""

import bisect
import math

import hou

from . import (DEFAULTS, EPS, WARN_BEND_RESOLUTION, WARN_KIT_GAP, Curve,
               Marker, Z_MODES, elem_key, stand_in)
from . import decompose as _decompose
from . import kit as _kit
from . import plan as _plan

UP = (0.0, 1.0, 0.0)

# 3.4's output schema. One list, so the builder and the checks read the same
# names: (attribute, default).
ELEM_PRIM_ATTRS = (
    ("pc_elem_id", ""), ("pc_elem_key", 0), ("pc_slot", ""), ("pc_module", ""),
    ("pc_variant", ""), ("pc_section", 0), ("pc_u", 0.0), ("pc_zmode", ""),
    ("pc_generated", 0), ("pc_deformed", 0),
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

    `Curve.sample` rebuilds its segment table on EVERY call, which is fine for
    a kernel that samples twice per section and quadratic for a builder that
    samples once per point of every piece. This caches the table and bisects
    it, and it is built from `Curve._cumulative()` so the two cannot disagree
    about where a metre is. `sampler_matches_kernel` in the scene checks
    asserts exactly that, at 400 positions per case.
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
        if forward:
            i = bisect.bisect_right(self.ends, s + EPS)
        else:
            i = bisect.bisect_left(self.ends, s - EPS)
        i = min(i, len(self.segs) - 1)
        lo, hi, a, d = self.segs[i]
        t = 0.0 if hi - lo < EPS else min(max((s - lo) / (hi - lo), 0.0), 1.0)
        return ((a[0] + d[0] * t, a[1] + d[1] * t, a[2] + d[2] * t), _unit(d))

    def interior_vertices(self, s0, s1, tol=1e-7):
        """Vertex arclengths strictly inside (s0, s1). Wraps on closed."""
        out = []
        total = self.total
        reps = (0.0,) if not (self.closed and total > EPS) else (0.0, total,
                                                                -total)
        for base in reps:
            for v in self.vertex_s:
                sv = v + base
                if s0 + tol < sv < s1 - tol:
                    out.append(sv)
        out.sort()
        return out


class _Remap(object):
    """s on the flattened curve -> s on the real one (D26, slope fixing).

    Both curves carry the same vertices, so their cumulative tables are the
    same length and the map is piecewise linear and exact between them.
    """

    def __init__(self, flat_cum, real_cum):
        self.flat = flat_cum
        self.real = real_cum
        self.flat_total = flat_cum[-1] if flat_cum else 0.0
        self.real_total = real_cum[-1] if real_cum else 0.0

    def __call__(self, s):
        if self.flat_total <= EPS:
            return 0.0
        wraps = math.floor(s / self.flat_total)
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


def read_curves(geo):
    """([Curve], [Marker]) off input 1. Marker points never become curves."""
    markers = []
    marker_pts = set()
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
            if u is None and dist is None:
                u = 0.0
            markers.append(Marker(
                str(_pattr(pt, "pc_curve", "")),
                u=None if u is None else float(u),
                dist=None if dist is None else float(dist),
                marker_id=int(_pattr(pt, "pc_marker_id", 0) or 0),
                data=dict(data) if isinstance(data, dict) else {}))

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
        cid = _prattr(prim, "pc_curve_id", None)
        if cid is None:
            cid = _prattr(prim, "edge_id", None)          # D29, streets id
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
        curves.append(Curve(str(cid), [p.position() for p in pts],
                            closed=closed, corner_flags=flags,
                            section_ids=sections,
                            style_key=str(_prattr(prim, "pc_style", "") or "")))
    return (curves, markers)


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
        self.stations = _stations(source, self.ax)
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
        out = (filled, _stations(filled, self.ax))
        self._sliced[key] = out
        return out


# --- the frames -------------------------------------------------------------

def _frame(tangent, zmode):
    """(dir, across, up) for one sample. `across` is +Z when dir is +X."""
    if zmode == "adaptive":
        d = _unit(tangent)
        across = _cross(d, UP)
        if _len(across) < EPS:
            across = (0.0, 0.0, 1.0)
        else:
            across = _unit(across)
        return (d, across, _cross(across, d))
    d = _unit((tangent[0], 0.0, tangent[2]))
    return (d, (-d[2], 0.0, d[0]), UP)


def _needs_deform(placement, proto, path, sa, sb, zmode):
    """4.4 + the streets float32 lesson: rebuild ONLY when it changes something."""
    if placement.slice_t is not None:
        return True
    if proto.module.deform <= 0:
        return False                                    # D27
    if path.interior_vertices(sa, sb):
        return True
    if zmode == "vertical":
        ya = path.sample(sa)[0][1]
        yb = path.sample(sb, forward=False)[0][1]
        return abs(yb - ya) > 1e-6                      # a sheared span
    return False


def _bend_deviation(proto, stations, path, s0_flat, scale, remap):
    """D25 - how far the built piece cuts the corner, in metres."""
    worst = 0.0
    for i in range(len(stations) - 1):
        s_a = remap(s0_flat + stations[i] * scale)
        s_b = remap(s0_flat + stations[i + 1] * scale)
        if s_b - s_a <= EPS:
            continue
        pa = path.sample(s_a)[0]
        pb = path.sample(s_b, forward=False)[0]
        pm = path.sample(0.5 * (s_a + s_b))[0]
        mid = (0.5 * (pa[0] + pb[0]), 0.5 * (pa[1] + pb[1]),
               0.5 * (pa[2] + pb[2]))
        worst = max(worst, _len(_sub(pm, mid)))
    return worst


# --- building one piece -----------------------------------------------------

def _packed_transform(proto, path, sa, sb, zmode):
    """The 4x4 that maps module local space onto the chord A->B (D21)."""
    a, ta = path.sample(sa)
    b, _tb = path.sample(sb, forward=False)
    chord = _sub(b, a)
    if zmode != "adaptive":
        chord = (chord[0], 0.0, chord[2])
    clen = _len(chord)
    if clen < EPS:                       # a zero-length span still gets a frame
        d, across, up = _frame(ta, zmode)
        clen = 0.0
    else:
        d, across, up = _frame(chord, zmode)
    scale = max(clen / proto.length, 1e-9)
    ox = proto.ax * scale
    return hou.Matrix4([
        [d[0] * scale, d[1] * scale, d[2] * scale, 0.0],
        [up[0], up[1], up[2], 0.0],
        [across[0], across[1], across[2], 0.0],
        [a[0] - d[0] * ox, a[1] - d[1] * ox, a[2] - d[2] * ox, 1.0]])


def _deform_positions(src, proto, path, s0_flat, scale, zmode, remap):
    """Every point of `src` re-read at its own arc position. Returns
    (flat world positions, flat local positions)."""
    local = src.pointFloatAttribValues("P")
    out = [0.0] * len(local)
    base_y = path.sample(remap(s0_flat))[0][1]
    ax = proto.ax
    for i in range(0, len(local), 3):
        x, y, z = local[i], local[i + 1], local[i + 2]
        pos, tan = path.sample(remap(s0_flat + (x - ax) * scale))
        d, across, up = _frame(tan, zmode)
        if zmode == "adaptive":
            out[i] = pos[0] + across[0] * z + up[0] * y
            out[i + 1] = pos[1] + across[1] * z + up[1] * y
            out[i + 2] = pos[2] + across[2] * z + up[2] * y
        else:
            py = base_y if zmode == "stepped" else pos[1]
            out[i] = pos[0] + across[0] * z
            out[i + 1] = py + y
            out[i + 2] = pos[2] + across[2] * z
    return (out, local)


# --- output attributes ------------------------------------------------------

def _declare(geo, warn_names):
    for name, default in ELEM_PRIM_ATTRS:
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, default)
    for name in warn_names:
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, 0)


def _stamp(prim, placement, warns, deformed, zmode):
    eid = placement.elem_id
    prim.setAttribValue("pc_elem_id", eid)
    prim.setAttribValue("pc_elem_key", elem_key(eid))
    prim.setAttribValue("pc_slot", placement.slot)
    prim.setAttribValue("pc_module", placement.module)
    prim.setAttribValue("pc_variant", placement.variant)
    prim.setAttribValue("pc_section", int(placement.section_index))
    prim.setAttribValue("pc_u", float(placement.u))
    prim.setAttribValue("pc_zmode", zmode)
    prim.setAttribValue("pc_generated", 1)
    prim.setAttribValue("pc_deformed", 1 if deformed else 0)
    for w in warns:
        prim.setAttribValue(w, 1)


# --- the pipeline -----------------------------------------------------------

def _resolve_zmode(placement):
    """The kernel has ALREADY applied D6 (`plan._zmode`: a non-empty style
    zmode overrides every module), so this only guards the vocabulary - an
    unknown value falls back to `adaptive` instead of building nothing. Doing
    the override again here would be a second copy of a kernel decision."""
    return placement.zmode if placement.zmode in Z_MODES else "adaptive"


def _prepare(curve, params):
    """(kernel curve, Path on the REAL curve, flat->real remap). D26."""
    path = Path(curve)
    if not params.fix_slope:
        return (curve, path, _identity_remap())
    flat = Curve(curve.curve_id,
                 [(p[0], 0.0, p[2]) for p in curve.points],
                 closed=curve.closed, corner_flags=curve.corner_flags,
                 section_ids=curve.section_ids, style_key=curve.style_key,
                 attrs=curve.attrs)
    return (flat, path, _Remap(flat._cumulative(), curve._cumulative()))


def analyse(curve_geo, params=DEFAULTS):
    """[{curve, real, path, remap, sections}] - what `build` decomposes,
    exposed so the scene checks measure against the same sections the builder
    used instead of re-deriving them (and re-deriving them differently).

    `curve` is what the KERNEL planned on and `real` is what the geometry is
    built on. Under `fix_slope` they are different curves (D26) and a check
    that conflates them measures the slope instead of the builder.
    """
    curves, markers = read_curves(curve_geo)
    out = []
    for curve in sorted(curves, key=lambda c: str(c.curve_id)):
        kcurve, path, remap = _prepare(curve, params)
        out.append({"curve": kcurve, "real": curve, "path": path,
                    "remap": remap,
                    "sections": _decompose.decompose(kcurve, markers, params)})
    return out


def build(curve_geo, kit_geo, style, params=None, out=None):
    """Curves + kit -> placed geometry. Never raises (warn-never-block).

    Returns (geometry, report) where the report carries the plan, the kit
    validation warnings and the counts the scene checks record.
    """
    params = params or (style.params if style is not None else None) or DEFAULTS
    out = out if out is not None else hou.Geometry()
    kit, sources, kit_warns = _kit.read(kit_geo)
    curves, markers = read_curves(curve_geo)

    protos = {}

    def proto_for(module):
        if module.name not in protos:
            protos[module.name] = _Proto(
                module, _kit.source_for(sources, module))
        return protos[module.name]

    # --- pass A: plan, and decide deform/warnings before anything is built --
    jobs = []
    for curve in sorted(curves, key=lambda c: str(c.curve_id)):
        kcurve, path, remap = _prepare(curve, params)
        sections = _decompose.decompose(kcurve, markers, params)
        for section in sections:
            for p in _plan.plan_section(section, kit, style, params):
                module = kit.by_name(p.module) or stand_in(p.module)
                proto = proto_for(module)
                zmode = _resolve_zmode(p)
                # flat = the space the kernel planned in; real = the curve it
                # is built on. They differ only under fix_slope (D26).
                s0f, s1f = section.s0 + p.s0, section.s0 + p.s1
                s0r, s1r = remap(s0f), remap(s1f)
                warns = list(p.warns)
                if module.missing and WARN_KIT_GAP not in warns:
                    warns.append(WARN_KIT_GAP)
                deformed = _needs_deform(p, proto, path, s0r, s1r, zmode)
                scale = 1.0 if p.slice_t is not None else (
                    ((s1f - s0f) / proto.length) if proto.length > EPS else 1.0)
                if deformed and module.deform > 0:
                    stations = (proto.sliced(p.slice_t)[1]
                                if p.slice_t is not None else proto.stations)
                    if _bend_deviation(proto, stations, path, s0f, scale,
                                       remap) > params.bend_tol:
                        warns.append(WARN_BEND_RESOLUTION)
                jobs.append({"p": p, "proto": proto, "path": path,
                             "s0f": s0f, "s0r": s0r, "s1r": s1r,
                             "zmode": zmode, "scale": scale,
                             "deformed": deformed, "warns": tuple(warns),
                             "remap": remap})

    warn_names = []
    for job in jobs:
        for w in job["warns"]:
            if w not in warn_names:
                warn_names.append(w)
    warn_names.sort()
    _declare(out, warn_names)

    # --- pass B: materialise -----------------------------------------------
    n_packed = n_deformed = 0
    for job in jobs:
        p, proto, path = job["p"], job["proto"], job["path"]
        zmode, warns = job["zmode"], job["warns"]
        if not job["deformed"]:
            prim = out.createPackedGeometry(proto.source)
            prim.setTransform(_packed_transform(
                proto, path, job["s0r"], job["s1r"], zmode))
            _stamp(prim, p, warns, False, zmode)
            n_packed += 1
            continue
        src = proto.sliced(p.slice_t)[0] if p.slice_t is not None \
            else proto.source
        piece = hou.Geometry()
        piece.merge(src)
        world, local = _deform_positions(piece, proto, path, job["s0f"],
                                         job["scale"], zmode, job["remap"])
        piece.setPointFloatAttribValues("P", world)
        if piece.findPointAttrib("pc_local") is None:
            piece.addAttrib(hou.attribType.Point, "pc_local", (0.0, 0.0, 0.0))
        piece.setPointFloatAttribValues("pc_local", local)
        _declare(piece, warn_names)
        for prim in piece.prims():
            _stamp(prim, p, warns, True, zmode)
        out.merge(piece)
        n_deformed += 1

    report = {
        "plan": [j["p"] for j in jobs],
        "kit_warnings": kit_warns,
        "curves": len(curves),
        "markers": len(markers),
        "packed": n_packed,
        "deformed": n_deformed,
        "warn_names": warn_names,
    }
    return (out, report)
