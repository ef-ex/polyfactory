"""polyChain 7 FACADE - the 2D adapter. Rows in, ONE `place.build`, out.

This is the only file in phase 2 that imports `hou`, and it is deliberately
thin: `array2d.py` decides everything (the Y solve, the row list, the role
closure, the canonical footprint, the clipped area's frame and spans) and this
turns those decisions into one geometry and one kernel call.

TWO RULES FROM 11.9 ARE THE WHOLE DESIGN OF THIS FILE

  1. **Never touch a `hou.Prim`/`hou.Point` wrapper in a loop.** Row emission
     is `createPoints` + `createPolygons` + `setPrim*AttribValues` - one call
     per attribute over the whole stream, never one per row. The
     `rows_wrappers_built` tripwire counts wrapper attribute writes here and
     its ceiling is 0.
  2. **All N rows go through ONE `place.build` call** (D115). `place.build`
     already hoists the conform batch to the outermost loop over ALL curves
     (D112) and takes exactly one `ray` execution per build; feeding it N rows
     in one call inherits that for free and feeding it N times throws it away.
     `ray_executions_per_build` must read 1 on BOTH phase-2 fixtures, and the
     many-short-rows one (100 buildings x 8 storeys = 800 short rows) is the
     one that can fail.

DECISIONS TAKEN HERE (recorded in polychain.md 12):

  D136 THE ROLE CLOSURE IS WRITTEN BACK ONTO THE KIT PAYLOAD, not passed into
       the kernel as an object. `place.build` reads its own kit from input 2
       (D77's two-face rule), so a closure computed beside it would have been
       thrown away; expressed as `pc_role` on a COPY of the kit geometry plus
       a `role_fallbacks` entry in the manifest, it is data on the payload -
       inspectable by the artist, read by the kernel's existing reader, and
       needing no new argument anywhere.
"""

import hou

from . import (CLIP_POLICIES, CLIP_REMOVE, DEFAULTS, WARN_CLIP_NONPLANAR,
               WARN_CLIP_SELFX, WARN_CLIP_TILTED, Params)
from . import array2d as _array2d
from . import kit as _kit
from . import place as _place
from . import style as _style

def _ensure(geo, cls, name, default):
    found = (geo.findGlobalAttrib(name) if cls == hou.attribType.Global
             else geo.findPointAttrib(name) if cls == hou.attribType.Point
             else geo.findPrimAttrib(name))
    return found or geo.addAttrib(cls, name, default)


# D142 - a row the clip boundary leaves nothing of has no element to carry a
# warning, so it says so on the build's own detail channel instead. `cell_grid`
# reads `report["rows"]` and counts it as a HOLE, which is the number.
_ROW_CLIPPED = "pc_warn_row_clipped_out"

ROW_STR_ATTRS = ("pc_curve_id", "pc_yclass", "pc_row_warns", "pc_bays")
ROW_INT_ATTRS = ("pc_row", "pc_clipped")
ROW_FLT_ATTRS = ("pc_row_y0", "pc_row_y1", "pc_row_scale")


# --- row emission (11.9 rule 1) ---------------------------------------------

def rows_geometry(loops, corner_flags=None, geo=None):
    """[(points, closed, attrs)] -> ONE `hou.Geometry` of row curves.

    Written with bulk array setters end to end: the point positions go in with
    one `createPoints`, the polylines with one `createPolygons`, and each of
    the six prim attributes with one `setPrim*AttribValues` over the whole
    stream. Nothing here is per-row except building the lists themselves.

    `corner_flags` is 7.5's "vertex type is data": a per-footprint-vertex
    `pc_corner`, repeated for every row. Left None, the auto-turn test
    (`corner_angle_deg`) decides, which is what a rectangle wants.

    ⚠️ THE FLAGS MUST ALREADY BE IN CANONICAL ORDER. `build` permutes them
    with `array2d.canonical_order` before calling this, because the loops it
    is handed have been rotated (and possibly reversed) by D124 and indexing
    an authored flag list by canonical position put every suppression on the
    wrong vertex.
    """
    geo = geo if geo is not None else hou.Geometry()
    if not loops:
        return geo
    positions, polys, base = [], [], 0
    for pts, closed, _attrs in loops:
        positions.extend(pts)
        polys.append((tuple(range(base, base + len(pts))), bool(closed)))
        base += len(pts)
    geo.createPoints(positions)
    # `createPolygons` takes ONE closed flag for the whole batch, so the two
    # kinds of row - a closed footprint and an open span across a clipped area
    # - are two calls at most, never one per row.
    for closed in (True, False):
        group = [p for p, c in polys if c == closed]
        if group:
            geo.createPolygons(tuple(group), closed)
    order = [i for i, (_p, c) in enumerate(polys) if c] + \
            [i for i, (_p, c) in enumerate(polys) if not c]
    attrs = [loops[i][2] for i in order]
    for name in ROW_STR_ATTRS:
        _ensure(geo, hou.attribType.Prim, name, "")
        geo.setPrimStringAttribValues(name, [str(a.get(name, "")) for a in attrs])
    for name in ROW_INT_ATTRS:
        _ensure(geo, hou.attribType.Prim, name, -1)
        geo.setPrimIntAttribValues(name, [int(a.get(name, -1)) for a in attrs])
    for name in ROW_FLT_ATTRS:
        _ensure(geo, hou.attribType.Prim, name, 0.0)
        geo.setPrimFloatAttribValues(name, [float(a.get(name, 0.0))
                                            for a in attrs])
    if corner_flags:
        # either ONE flag list for the whole stream, or one PER LOOP - which
        # is what a district of differently-authored footprints needs, and the
        # reason the flags are indexed by loop rather than by point: this
        # function reorders the stream (closed rows first, open spans after)
        # and a flat per-point column could not follow it.
        per_loop = isinstance(corner_flags[0], (list, tuple))
        _ensure(geo, hou.attribType.Point, "pc_corner", 0)
        col = []
        for i in order:
            pts = loops[i][0]
            fl = corner_flags[i] if per_loop else corner_flags
            col.extend([int(fl[j % len(fl)]) for j in range(len(pts))] if fl
                       else [0] * len(pts))
        geo.setPointIntAttribValues("pc_corner", col)
    return geo


def canonical_flags(footprint, corner_flags, closed=True):
    """7.5's per-vertex `pc_corner`, permuted the way D124 permuted the points.

    The row emitter walks the CANONICAL point list; the flags arrive in the
    order the artist authored them. Indexing one by the other put every
    suppression on a different physical vertex the moment the same footprint
    was re-authored from another start vertex - a hole in the miter at the
    vertex that should have had a corner column, and a corner column at the
    curved return that should not, with `structural_ids` unable to see it
    because no committed case passed flags at all.
    """
    if not corner_flags:
        return corner_flags
    return [corner_flags[i % len(corner_flags)]
            for i in _array2d.canonical_order(footprint, closed)]


# --- the kit, with 7.2.2's lattice closed onto it (D136) --------------------

def close_kit(kit_geo, extend="x", extra_roles=()):
    """(kit geometry with every 2D cell role resolved, {asked: supplied},
    [7.2's alias-collision notices]).

    A COPY: closing the roles rewrites `pc_role`, and a build must not edit the
    kit its caller handed it.
    """
    kit, _sources, _warns = _kit.read(kit_geo)
    kit2, fallbacks = _array2d.close_roles(kit, extend, extra_roles)
    geo = hou.Geometry()
    geo.merge(kit_geo)
    by_name = dict((m.name, m) for m in kit2.modules)
    if geo.findPointAttrib("pc_name") is not None:
        _ensure(geo, hou.attribType.Point, "pc_role", "default")
        names = list(geo.pointStringAttribValues("pc_name"))
        roles = list(geo.pointStringAttribValues("pc_role"))
        geo.setPointStringAttribValues("pc_role", [
            " ".join(by_name[n].roles) if n in by_name else r
            for n, r in zip(names, roles)])
    meta = {}
    if geo.findGlobalAttrib(_kit.KIT_DETAIL) is not None:
        try:
            meta = dict(geo.attribValue(_kit.KIT_DETAIL))
        except Exception:
            meta = {}
    meta["role_fallbacks"] = dict(fallbacks)
    _ensure(geo, hou.attribType.Global, _kit.KIT_DETAIL, {})
    geo.setGlobalAttribValue(_kit.KIT_DETAIL, meta)
    return (geo, fallbacks, kit2.role_collisions)


# --- 7.6: the clip input, as geometry ---------------------------------------

CLIP_MODE_ATTR = "pc_clip_mode"      # "" (even-odd) / "include" / "exclude"
CLIP_GROUP_ATTR = "pc_clip_group"    # RC's By Material ID, renamed - NOT YET

# ⚠️ THE INPUT'S OWN COMPLAINTS, ON THEIR OWN CHANNEL. They also go onto
# `kit_warnings` where an artist reads them, but a loop the validation
# REJECTED has no element to carry an attribute and no `warn_names` entry
# either (that list is the union of warnings that fired on a BUILT piece), so
# there was no way to ask "what did the input say" that did not mean parsing
# prose and guessing which strings were element summaries. C3's node reads
# this to route them out per D289.
CLIP_INPUT_WARNINGS = "clip_input_warnings"


def clip_loops(geo):
    """A clip input -> ([closed loops], [per-loop mode], [warnings]).

    7.6's data contract, read off the geometry the artist wires in: one
    closed polygon per sub-spline, `pc_clip_mode` per PRIM overriding that
    loop's even-odd polarity. Open prims are skipped - a clip boundary that
    does not close cannot define an area, and warn-never-block means saying
    so rather than guessing where it ends.

    ⚠️ D290 - CLOSURE WAS THE ONLY THING THIS EVER TESTED, and 7.6's contract
    is a closed PLANAR sub-spline. Two more now, and they are deliberately
    treated differently: a SELF-INTERSECTING loop is skipped like an unclosed
    one, because its lobes wind opposite ways and the array breached its own
    region by 0.88 m with nothing said - a gap is a defect an artist sees and
    fixes, an overhang is one they ship (D126's own argument). A NON-PLANAR
    loop is built and warned, because a hand-drawn spline is never exactly
    planar; what the warning says is that the boundary being trimmed to is the
    loop's projection, not the loop.

    ⚠️ `pc_clip_group` IS READ AND NOT HONOURED. Merging several roots into
    ONE array needs a frame spanning all of them and a row stack over that
    frame, which is a different solve from "one array per root"; PC-G6 does
    not ask for it and C2 did not build it. It warns rather than silently
    building the arrays separately, because a silent wrong answer is the
    failure mode this project keeps recording.
    """
    loops, modes, warns = [], [], []
    if geo is None:
        return (loops, modes, warns)
    has_mode = geo.findPrimAttrib(CLIP_MODE_ATTR) is not None
    has_group = geo.findPrimAttrib(CLIP_GROUP_ATTR) is not None
    grouped = 0
    for prim in geo.prims():
        try:
            pts = [v.point().position() for v in prim.vertices()]
        except hou.OperationFailed:
            continue
        if len(pts) < 3:
            continue
        if not prim.isClosed():
            warns.append("pc_warn_clip_open: prim %d is not a closed loop - "
                         "a clip boundary must close" % prim.number())
            continue
        loop = [(p[0], p[1], p[2]) for p in pts]
        if not _array2d.is_simple(loop):
            warns.append("%s: prim %d crosses itself - a clip boundary with "
                         "no consistent inside is skipped"
                         % (WARN_CLIP_SELFX, prim.number()))
            continue
        planar, off = _array2d.is_planar(loop)
        if not planar:
            warns.append("%s: prim %d is %.4f m off its own plane - the array "
                         "is solved on the projection, not on the loop"
                         % (WARN_CLIP_NONPLANAR, prim.number(), off))
        loops.append(loop)
        modes.append(str(prim.attribValue(CLIP_MODE_ATTR)) if has_mode else "")
        if has_group and int(prim.attribValue(CLIP_GROUP_ATTR)):
            grouped += 1
    if grouped:
        warns.append("pc_warn_clip_group_ignored: %d sub-spline(s) carry "
                     "%s and it is not implemented - each root sub-spline is "
                     "still its own array" % (grouped, CLIP_GROUP_ATTR))
    return (loops, modes, warns)


def build_clipped(clip_geo, kit_geo, style, **kw):
    """7.6's whole primitive in one call: a clip input -> N arrays.

    The 2D path's artist face until phase 2 has an HDA of its own (C3): the
    boundary arrives as GEOMETRY carrying its own per-sub-spline attributes,
    and `clip_mode` is the decision-named cull policy for every module that
    does not carry its own `pc_clip`.
    """
    loops, modes, warns = clip_loops(clip_geo)
    kw.setdefault("clip_mode", "remove")
    geo, report = build_many(loops, kit_geo, style, area=True,
                             clip_modes=modes, **kw)
    report["kit_warnings"] = list(report.get("kit_warnings", [])) + warns
    report[CLIP_INPUT_WARNINGS] += warns
    return (geo, report)


def meta_2d(y_params=None, y_mode=None, clip_mode=None, auto_align=None,
            expand=None, clip=None):
    """The inverse of `array2d.payload_2d`: the 2D settings as a 7.3.2 meta
    block, so 2.1's *"the parm face's own Style expressed as a payload"* is one
    call on this axis too and the round trip is the TOOL's code in both
    directions rather than a dict a test happened to spell right.

    `clip` carries 7.3.2's three fixed keys through unaltered, which is what
    makes a REFUSAL reachable from a caller instead of only from hostile
    input.
    """
    meta = {}
    if y_params is not None:
        meta["y_params"] = _style.params_to_dict(y_params)
    if y_mode is not None:
        meta["y_mode"] = y_mode
    block = dict(clip or {})
    for key, value in (("mode", clip_mode), ("auto_align", auto_align),
                       ("expand", expand)):
        if value is not None:
            block[key] = value
    if block:
        meta["clip"] = block
    return meta


def _y_params(style, y_params, warns=None):
    """7.3.2's `pc_style_meta["y_params"]`, read by the SAME `params_from_dict`.

    `y_fill`, `y_count`, `y_evenly_spacing`... are not new parms: they are the
    same `Params` fields on the other axis.

    ⚠️ THE PAYLOAD WINS, AND IT DID NOT USE TO (D293). This read "an explicit
    argument wins, then the payload's own dict" - which makes 2.1's pipeline
    face impossible on the Y axis, because a node's parm arrives here AS an
    explicit argument and would beat the payload every time. It is the same
    precedence as the X axis now: the payload's own block, then the keyword,
    then the X params. A payload that says nothing about Y still leaves the
    keyword alone, so "the payload overrides the parms" and "the payload was
    silent" stay two different states.
    """
    data = (getattr(style, "meta", None) or {}).get("y_params")
    if data:
        return _style.params_from_dict(dict(data), warns)
    return y_params


# --- the build (D115: one call) ---------------------------------------------

def build(footprint, kit_geo, style, height=None, profile=None, array_id="A",
          y_params=None, extend="x", closed=True, corner_flags=None,
          area=False, clip_mode="remove", clip_modes=None,
          auto_align="to_spline", expand=0.0, y_mode="free",
          out=None, surface_geo=None, overrides=None):
    """One footprint + a height -> a facade. Returns (geometry, report).

    `footprint` is a list of world-space points (the closed plan) or, with
    `area=True`, a closed PLANAR sub-spline that both defines and trims the
    array (7.6): its own plane gives the local frame, its bounding box in that
    frame gives the extents, and every row is a straight span across it.

    The report is `place.build`'s, plus `rows` (the Y solve, as dicts),
    `role_fallbacks` (7.2.2's walk, per cell) and `array_id`.

    This is `build_many` with one footprint, and that is not a refactor for
    tidiness: D115's one-call property was only ever exercised by a bench
    fixture that hand-assembled loops and called `place.build` itself, while
    the only shipped entry point took ONE footprint and therefore ONE
    `place.build` per building - i.e. exactly the 100-call column the bench
    labelled the loser. One body, so the fixture and the API cannot diverge.
    """
    return build_many([footprint], kit_geo, style, height=height,
                      profile=profile, array_ids=[array_id],
                      y_params=y_params, extend=extend, closed=closed,
                      corner_flags=corner_flags, area=area,
                      clip_mode=clip_mode, clip_modes=clip_modes,
                      auto_align=auto_align, expand=expand, y_mode=y_mode,
                      out=out, surface_geo=surface_geo,
                      overrides=overrides)


def build_many(footprints, kit_geo, style, height=None, heights=None,
               profile=None, array_ids=None, y_params=None, extend="x",
               closed=True, corner_flags=None, area=False,
               clip_mode="remove", clip_modes=None, auto_align="to_spline",
               expand=0.0, y_mode="free", out=None, surface_geo=None,
               overrides=None):
    """N footprints -> ONE `place.build`. D115 / PC-G7's one-call rule, shipped.

    ⚠️ THIS IS THE ENTRY POINT THE ONE-CALL RULE IS ABOUT, and until it
    existed there was no caller that could reach it. `place.build` hoists the
    conform batch to the outermost loop over ALL curves (D112) and takes one
    `ray` execution per build, so a district of 100 buildings driven one
    `facade.build` at a time took 100 `ray` executions and 300 `kit.read`
    calls - the shape 11.9 rule 2 exists to warn about - while
    `ray_executions_per_build == 1` was asserted on a fixture with no caller.

    `heights` / `array_ids` are optional parallel sequences; `corner_flags` is
    either one flag list shared by every footprint or one per footprint. The
    kit is read and closed ONCE for the whole district, which is the other
    per-call cost a per-building loop paid.

    Returns (geometry, report). The report is `place.build`'s plus `arrays` -
    one entry per footprint carrying its rows, frame and unbuilt rows - and,
    when there is exactly one footprint, that entry's fields hoisted to the
    top level so `build`'s report shape is unchanged.
    """
    kit, _sources, _kw = _kit.read(kit_geo)
    # 2.1 / D293 - THE PAYLOAD FACE, ON BOTH AXES. Every keyword below this
    # line is the 2D path's parm face (7.6: "there is no HDA on the 2D path at
    # all, so a parm here means an argument on the shipped entry point"), and
    # a payload that names a setting overrides it entirely. What the payload
    # does NOT name is left to the keyword, which is what keeps "overridden"
    # and "not mentioned" two distinguishable states.
    pay_warns = []
    settings = _array2d.payload_2d(style, pay_warns)
    clip_mode = settings.get("clip_mode", clip_mode)
    auto_align = settings.get("auto_align", auto_align)
    expand = settings.get("expand", expand)
    y_mode = settings.get("y_mode", y_mode)
    x_style, y_style = _array2d.split_style(
        style, _y_params(style, y_params, pay_warns))
    named = [m for r in style.rules for m in r.modules] + \
            [r.slot for r in style.rules]
    kit_geo2, fallbacks, collisions = close_kit(kit_geo, extend, named)
    # D122's datum solve needs the CLOSED kit - the one the kernel reads - or
    # it resolves a different set of cells from the builder and counts bays
    # nobody will build. Only `aligned` pays for it.
    kit_closed = (_array2d.close_roles(kit, extend, named)[0]
                  if y_mode == "aligned" else kit)

    per_flags = bool(corner_flags) and isinstance(corner_flags[0],
                                                  (list, tuple))
    # 7.6 / D125 - EVERY CLOSED SUB-SPLINE AT ONCE, then even-odd nesting, and
    # only then one array per ROOT. A loop inside another is a hole in that
    # array and builds nothing of its own; a loop inside the hole is an island
    # and builds again (depth 2). That is what makes editing sub-spline B move
    # zero of sub-spline A's `pc_elem_id`s: they were never one array.
    depth = include = parent = members = hook = None
    # ...and `footprints` CAN be empty now: D290 rejects a self-intersecting
    # sub-spline at the door, so a clip input made only of bad loops arrives
    # here as no loops at all. Warn-never-block means an empty build, not a
    # traceback.
    if area and footprints:
        depth, include, parent, _chart = _array2d.nest(footprints, clip_modes)
        members = _array2d.array_members(parent)
        hook = _array2d.ClipHook(CLIP_POLICIES.get(clip_mode, CLIP_REMOVE))
    loops, arrays, flag_col, frame_warns = [], [], [], list(pay_warns)
    for i, footprint in enumerate(footprints):
        array_id = (array_ids[i] if array_ids is not None
                    else ("A" if len(footprints) == 1 else "A%03d" % i))
        h = heights[i] if heights is not None else height
        flags = corner_flags[i] if per_flags else corner_flags
        frame, unbuilt = None, []
        if area:
            if i not in members:
                continue                     # a hole, or an island in one
            frame = _array2d.area_frame(footprint, auto_align, expand)
            tilt = _array2d.frame_tilt_deg(frame)
            if tilt > _array2d.CLIP_TILT_DEG:
                frame_warns.append(
                    "%s: array %s is solved in a plane tilted %.2f deg from "
                    "the axis modules are built along - every piece leaves "
                    "its own band by that much" % (WARN_CLIP_TILTED,
                                                   array_id, tilt))
            mine_loops = members[i]
            region = _array2d.region_for(
                frame, [footprints[j] for j in mine_loops],
                [include[j] for j in mine_loops],
                [depth[j] for j in mine_loops])
            rows = _array2d.plan_rows(
                profile if profile is not None
                else (h if h is not None else frame.height),
                kit, y_style, y_params, array_id)
            mine = _array2d.area_rows(frame, rows, clip_mode, unbuilt,
                                      region, hook)
        else:
            rows = _array2d.plan_rows(profile if profile is not None else h,
                                      kit, y_style, y_params, array_id)
            mine = _array2d.row_loops(footprint, rows, closed)
            flags = canonical_flags(footprint, flags, closed)
        # 7.4 / D122 - ALIGNED, per array, because bay boundaries are a
        # property of ONE footprint's rows and two arrays share nothing.
        if y_mode == "aligned":
            _array2d.align_rows(mine, kit_closed, x_style, x_style.params)
        loops.extend(mine)
        # one flag list PER LOOP, because `rows_geometry` reorders the stream
        # (closed rows first) and a flat column could not follow it.
        flag_col.extend([flags] * len(mine))
        arrays.append({"array_id": array_id, "frame": frame,
                       "rows_unbuilt": list(unbuilt),
                       "rows": [dict(r.as_dict(),
                                     built=0 if r.index in unbuilt else 1)
                                for r in rows]})

    geo, report = _place.build(
        rows_geometry(loops, flag_col if any(flag_col) else None), kit_geo2,
        x_style, params=x_style.params, out=out, surface_geo=surface_geo,
        overrides=overrides, clip=hook)
    report["arrays"] = arrays
    # ⚠️ THE ROW STREAM THE KERNEL ACTUALLY SAW, published. Every consumer that
    # wanted it - the check harness, a debug view - was re-deriving it by
    # re-spelling this function's own precedence, and D122 made that a third
    # copy (the payload's `y_mode`, the closed kit, the aligned stamp). A
    # re-derivation that drifts is a harness measuring the seam between two
    # builds instead of the build.
    report["loops"] = loops
    report["row_flags"] = flag_col if any(flag_col) else None
    one = arrays[0] if len(arrays) == 1 else None
    report["rows"] = one["rows"] if one else [r for a in arrays
                                              for r in a["rows"]]
    report["rows_unbuilt"] = one["rows_unbuilt"] if one else []
    report["array_id"] = one["array_id"] if one else ""
    report["frame"] = one["frame"] if one else None
    unbuilt = [(a["array_id"], i) for a in arrays for i in a["rows_unbuilt"]]
    report["role_fallbacks"] = fallbacks
    # the kit the KERNEL actually read (D136's closed copy), so a check
    # resolves the same roles the builder did instead of the ones the caller
    # authored.
    report["kit_geo"] = kit_geo2
    # 7.2.2's "naming both roles" - the per-element attribute says a fallback
    # happened, and this says which one, once per (role, kit).
    report[CLIP_INPUT_WARNINGS] = list(frame_warns)
    report["kit_warnings"] = list(report.get("kit_warnings", [])) + \
        list(collisions) + frame_warns + \
        ["%s: array %s row %d has no span left inside the clip boundary - "
         "not built" % (_ROW_CLIPPED, a, i) for a, i in unbuilt] + \
        ["%s: %d piece(s) removed by the clip boundary" % (w, n)
         for w, n in sorted(report.get("clip_warns", {}).items())] + \
        _array2d.fallback_lines(dict((k, v) for k, v in fallbacks.items()
                                     if _used(k, report)))
    return (geo, report)


def _used(role, report):
    """Only name a fallback a CELL ACTUALLY ASKED FOR. The lattice has 25
    entries and a facade uses a handful; listing the rest would bury the one
    that matters."""
    for p in report.get("plan", ()):
        if p.cell == role:
            return True
    return False
