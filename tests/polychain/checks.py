"""polyChain geometry checks - the assertions, in one place.

Same contract as `tests/citygen/checks.py`, and for the same reason: a
measurement written during a review belongs here afterwards, so the next
review starts where the last one finished rather than rewriting it. Each check
returns a `Result` carrying a NUMBER, never a bare pass/fail - the citygen
baseline caught several regressions that were only ever visible as "this
number got worse".

Nothing raises. A check that cannot run reports `skipped`, because a crashed
check hides the others.

WHAT THE NUMBERS MEAN
  sampler_matches_kernel  worst disagreement between `place.Path` (cached) and
                     `Curve.sample` (the kernel's own). If they drift, the
                     builder places pieces where the planner did not put them
                     and NOTHING else on this list could tell.
  section_coverage_m the plan still spans its section end to end. Without it
                     `exact_fill_m` could pass by measuring a short run
                     against its own short end.
  exact_fill_m       distance between the last piece's end AXIS POINT and the
                     section's end on the curve, worst over sections. The
                     whole pipeline measured end to end: the kernel's exact
                     fill only counts if geometry lands on it.
  max_gap_m          worst |end of piece k - start of piece k+1|. Zero BY
                     CONSTRUCTION (D21: consecutive pieces are built from the
                     same curve sample), so any drift is a real defect.
  stepped_riser_m    the vertical step between consecutive STEPPED pieces.
  stepped_float_m    the AIR under a stepped piece - 4.4's flatten-under.
  deform_gate_m      [worst deviation left packed, over budget, of those
                     still packed] - D100's dangerous direction, as a triple.
  band_hybrid_m      [level half, following half] of a D99 top/bottom band.
                     This is the mode working, not a gap - so it is recorded
                     as its own number and excluded from `max_gap_m` rather
                     than quietly tolerated inside it.
  band_datum_m       WHAT elevation that level half levelled to - D105. The
                     one question `band_hybrid_m` cannot ask.
  stamp_parity       [attribute values compared, differing] between the D102
                     BULK stamp and the per-prim writer it replaced.
  plumb_deg          worst tilt of a vertical-mode piece's up axis away from
                     world up. Must be 0.
  flat_stepped_m     worst spread of (world y - local y) inside a stepped
                     piece. 0 means the piece is a flat slab at one height.
  bank_deg           the same tilt measured on ADAPTIVE pieces, and it must be
                     NON-ZERO on a slope: without that assertion a builder
                     that ignored the Z-mode entirely would pass every other
                     check on this list.
"""

import math
import time

import hou

TOL_M = 1e-4        # P is float32; below ~1e-4 m at scene scale this measures
                    # the storage format, not the geometry.
LOCAL_TOL = 1e-5



class Result(object):
    __slots__ = ("name", "ok", "value", "detail", "skipped")

    def __init__(self, name, ok, value=None, detail="", skipped=False):
        self.name = name
        self.ok = ok
        self.value = value
        self.detail = detail
        self.skipped = skipped

    def as_dict(self):
        return {"name": self.name, "ok": self.ok, "value": self.value,
                "detail": self.detail, "skipped": self.skipped}

    def __repr__(self):
        state = "SKIP" if self.skipped else ("PASS" if self.ok else "FAIL")
        return "[%s] %-26s %s  %s" % (state, self.name, self.value, self.detail)


def _skip(name, why):
    return Result(name, True, None, why, skipped=True)


def _round(x, n=9):
    return round(float(x), n)


# --- element extraction -----------------------------------------------------

ELEM_STRINGS = ("pc_elem_id", "pc_slot", "pc_module", "pc_variant",
                "pc_zmode", "pc_curve_id", "pc_style")
ELEM_INTS = ("pc_elem_key", "pc_section", "pc_generated", "pc_deformed",
             "pc_replaced")


def _attrs(prim):
    rec = {}
    for name in ELEM_STRINGS:
        try:
            rec[name] = prim.attribValue(name)
        except hou.OperationFailed:
            rec[name] = ""
    for name in ELEM_INTS:
        try:
            rec[name] = int(prim.attribValue(name))
        except (hou.OperationFailed, TypeError, ValueError):
            rec[name] = 0
    try:
        rec["pc_u"] = float(prim.attribValue("pc_u"))
    except (hou.OperationFailed, TypeError, ValueError):
        rec["pc_u"] = 0.0
    return rec


def elements(geo):
    """[{attrs..., world: [x,y,z...], local: [...]}], one per pc_elem_id.

    Packed prims are unpacked HERE and nowhere else, so every check reads one
    shape and cannot accidentally measure only the deformed half of a build.
    """
    out, order = {}, []
    for prim in geo.prims():
        rec_attrs = _attrs(prim)
        eid = rec_attrs["pc_elem_id"]
        rec = out.get(eid)
        if rec is None:
            rec = dict(rec_attrs)
            rec.update({"world": [], "local": [], "_pts": set(), "prims": 0})
            out[eid] = rec
            order.append(eid)
        rec["prims"] += 1
        if prim.type() == hou.primType.PackedGeometry:
            src = prim.getEmbeddedGeometry()
            xform = prim.fullTransform()
            local = src.pointFloatAttribValues("P")
            for i in range(0, len(local), 3):
                v = hou.Vector3(local[i], local[i + 1], local[i + 2]) * xform
                rec["world"].extend((v[0], v[1], v[2]))
                rec["local"].extend((local[i], local[i + 1], local[i + 2]))
            continue
        for vtx in prim.vertices():
            pt = vtx.point()
            if pt.number() in rec["_pts"]:
                continue
            rec["_pts"].add(pt.number())
            pos = pt.position()
            try:
                loc = pt.attribValue("pc_local")
            except hou.OperationFailed:
                loc = (0.0, 0.0, 0.0)
            rec["world"].extend((pos[0], pos[1], pos[2]))
            rec["local"].extend((loc[0], loc[1], loc[2]))
    return [out[e] for e in order]


# --- measuring one element --------------------------------------------------

def _face(rec, target, tol=LOCAL_TOL):
    """[(local, world)] for the points at local x == target."""
    loc, wrl = rec["local"], rec["world"]
    out = []
    for i in range(0, len(loc), 3):
        if abs(loc[i] - target) <= tol:
            out.append(((loc[i], loc[i + 1], loc[i + 2]),
                        (wrl[i], wrl[i + 1], wrl[i + 2])))
    return out


def _frame_of(face):
    """(origin, up, across) of one face, read off the built geometry.

    The face map is AFFINE - every point of one face shares one arc position
    and therefore one frame - so `world = A + up*y + across*z` is recovered
    exactly from three point pairs. `_axis_of` wants only A; `frame_continuity`
    wants `across`, which is the vector that used to flip 180 degrees mid
    piece.
    """
    if not face:
        return (None, None, None)
    (l0, w0) = face[0]
    up, across = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    # ⚠ EACH PAIR MUST VARY IN ONE LOCAL AXIS ONLY. Taking the first
    # y-varying pair whatever its z does folds an `across` component into `up`,
    # and the recovered origin is then wrong by that much: on a clipped corner
    # post whose point order interleaves z across y (which `clip` + `polyfill`
    # produce), `corner_abut_m` reported a phantom 0.160 m gap on a corner that
    # point-by-point is perfectly closed, and the same fragility can MASK a
    # real gap. So: `up` off a pair sharing local z, `across` off a pair
    # sharing local y - and only then the affine map is the one the builder
    # actually used.
    fit = _affine_fit(face)
    if fit is not None:
        return fit
    got_up = got_across = False
    for (l1, w1) in face[1:]:
        if abs(l1[1] - l0[1]) > LOCAL_TOL and abs(l1[2] - l0[2]) <= LOCAL_TOL:
            d = l1[1] - l0[1]
            up = ((w1[0] - w0[0]) / d, (w1[1] - w0[1]) / d,
                  (w1[2] - w0[2]) / d)
            got_up = True
            break
    for (l2, w2) in face[1:]:
        if abs(l2[2] - l0[2]) > LOCAL_TOL and abs(l2[1] - l0[1]) <= LOCAL_TOL:
            dz = l2[2] - l0[2]
            across = ((w2[0] - w0[0]) / dz, (w2[1] - w0[1]) / dz,
                      (w2[2] - w0[2]) / dz)
            got_across = True
            break
    if not (got_up and got_across):
        # ⚠️ NOT a silent default. A clip leaves faces that vary in ONE local
        # axis - the outside edge of a mitered post is a single z column - and
        # assuming world up/across there put the recovered axis point up to
        # h*sqrt(2) away: a closed pentagon read a 0.129 m corner "gap" that
        # its own points prove is 0. No recoverable frame means no
        # measurement, and every caller already handles None.
        return (None, None, None)
    origin = tuple(w0[k] - up[k] * l0[1] - across[k] * l0[2] for k in range(3))
    return (origin, up, across)


def _affine_fit(face):
    """Least-squares (origin, up, across) over EVERY point of the face.

    The pair-picking below is only a fallback now, because picking pairs is
    what made the measurement fragile: a clipped corner post's point order
    interleaves local z across local y, so the first y-varying pair also
    varied in z and folded an `across` component into `up`. `corner_abut_m`
    then reported a 0.160 m phantom gap on a closed reflex corner and a
    0.129 m one on a closed pentagon - and the same fragility can equally MASK
    a real gap. Fitting `world = A + up*y + across*z` over all points has no
    pair to pick wrong, and on a face whose (y, z) spread is degenerate the
    normal matrix is singular and this returns None.
    """
    if len(face) < 3:
        return None
    m = [[0.0] * 3 for _ in range(3)]
    rhs = [[0.0] * 3 for _ in range(3)]
    for (loc, wrl) in face:
        basis = (1.0, loc[1], loc[2])
        for i in range(3):
            for j in range(3):
                m[i][j] += basis[i] * basis[j]
            for k in range(3):
                rhs[i][k] += basis[i] * wrl[k]
    inv = _inv3(m)
    if inv is None:
        return None
    sol = [[sum(inv[i][j] * rhs[j][k] for j in range(3)) for k in range(3)]
           for i in range(3)]
    return (tuple(sol[0]), tuple(sol[1]), tuple(sol[2]))


def _inv3(m):
    """Inverse of a 3x3, or None when it is singular for this job."""
    a, b, c = m[0]
    d, e, f = m[1]
    g, h, i = m[2]
    co = [[e * i - f * h, c * h - b * i, b * f - c * e],
          [f * g - d * i, a * i - c * g, c * d - a * f],
          [d * h - e * g, b * g - a * h, a * e - b * d]]
    det = a * co[0][0] + b * co[1][0] + c * co[2][0]
    scale = max(abs(v) for row in m for v in row)
    if scale <= 0.0 or abs(det) < 1e-12 * scale ** 3:
        return None
    return [[co[r][k] / det for k in range(3)] for r in range(3)]


def _element_frame(rec):
    """(up, across) recovered from whichever face of this element has both.

    A mitered piece loses half of its end cross-section to the clip, so the
    face at its outside tip varies in local y only and has no recoverable
    `across` of its own. The piece is rigid and anchored, so its frame is the
    same at every x - borrowing it from a face that does have one is exact,
    and it is what keeps `piece_extent` and `station_spacing` measuring corner
    pieces at all instead of skipping them.
    """
    for x in sorted(set(rec["local"][0::3])):
        _o, up, across = _frame_of(_face(rec, x))
        if up is not None and across is not None:
            return (up, across)
    return (None, None)


def _axis_of(face, frame=None):
    """The world point at the face's local (x, 0, 0).

    ⚠️ THE OBVIOUS MEASUREMENT - the centroid of the face - IS WRONG, and was
    measured to be wrong before this existed: a post's cross-section centre
    sits 0.60 m up and a panel's 0.55 m, so two pieces that met perfectly
    reported a 0.050 m gap and a run starting exactly on its section reported
    a 0.575 m error. Every point of one face shares one arc position and
    therefore one frame, so the face map is AFFINE - world = A + U*y + V*z -
    and the cross-section offsets divide out exactly from two point pairs.
    """
    origin = _frame_of(face)[0]
    if origin is not None or frame is None or not face:
        return origin
    up, across = frame
    if up is None or across is None:
        return None
    (l0, w0) = face[0]
    return tuple(w0[k] - up[k] * l0[1] - across[k] * l0[2] for k in range(3))


def axis_points(rec):
    """(start, end) world points on the piece's own chain axis."""
    xs = rec["local"][0::3]
    if not xs:
        return (None, None)
    frame = _element_frame(rec)
    return (_axis_of(_face(rec, min(xs)), frame),
            _axis_of(_face(rec, max(xs)), frame))


def up_tilt_deg(rec):
    """Worst angle between a piece's own vertical and world up, in degrees."""
    loc, wrl = rec["local"], rec["world"]
    cols = {}
    for i in range(0, len(loc), 3):
        key = (round(loc[i], 5), round(loc[i + 2], 5))
        cols.setdefault(key, []).append(
            (loc[i + 1], (wrl[i], wrl[i + 1], wrl[i + 2])))
    worst = 0.0
    for col in cols.values():
        if len(col) < 2:
            continue
        col.sort(key=lambda t: t[0])
        (ylo, plo), (yhi, phi) = col[0], col[-1]
        if yhi - ylo <= LOCAL_TOL:
            continue
        d = (phi[0] - plo[0], phi[1] - plo[1], phi[2] - plo[2])
        n = math.sqrt(d[0] * d[0] + d[1] * d[1] + d[2] * d[2])
        if n < 1e-9:
            continue
        worst = max(worst, math.degrees(math.acos(
            max(-1.0, min(1.0, d[1] / n)))))
    return worst


def flatness_m(rec):
    """Spread of (world y - local y). 0 => the piece sits at ONE height."""
    loc, wrl = rec["local"], rec["world"]
    vals = [wrl[i + 1] - loc[i + 1] for i in range(0, len(loc), 3)]
    return (max(vals) - min(vals)) if vals else 0.0


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
                     + (a[2] - b[2]) ** 2)


def _dist_xz(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


def open_edges(geo):
    """{elem_id: unshared edges} over real polygons - a sliced piece whose cap
    is missing shows up here and nowhere else."""
    per = {}
    for prim in geo.prims():
        if prim.type() == hou.primType.PackedGeometry:
            continue
        try:
            eid = prim.attribValue("pc_elem_id")
        except hou.OperationFailed:
            eid = ""
        counts = per.setdefault(eid, {})
        vtx = prim.vertices()
        n = len(vtx)
        for i in range(n):
            a = vtx[i].point().number()
            b = vtx[(i + 1) % n].point().number()
            key = (min(a, b), max(a, b))
            counts[key] = counts.get(key, 0) + 1
    return dict((eid, sum(1 for v in c.values() if v == 1))
                for eid, c in per.items())


def collect_warns(geo, names):
    """{elem_id: {warn: 1}} - read once, so `warnings` stays O(elements)."""
    out = {}
    if not names:
        return out
    for prim in geo.prims():
        try:
            eid = prim.attribValue("pc_elem_id")
        except hou.OperationFailed:
            continue
        slot = out.setdefault(eid, {})
        for name in names:
            try:
                if int(prim.attribValue(name)):
                    slot[name] = 1
            except (hou.OperationFailed, TypeError, ValueError):
                pass
    return out


def _band_case(scene):
    """D99 - this case carries a top/bottom BAND, so every yaw-only piece in
    it is a hybrid: half of it flat, half of it following the ground.

    Its end faces therefore do not sit on the curve in Y - exactly as a
    `stepped` piece's do not, and for the same reason - so the three
    along-the-chain checks compare it in XZ, which is the exemption they
    already grant stepped mode. `adaptive` is untouched: it has no flat half,
    so `_band` hands it no band and its axis must still land on the curve.
    """
    p = getattr(scene, "params", None)
    return bool(getattr(p, "flat_band", ""))         and float(getattr(p, "flat_band_m", 0.0) or 0.0) > 0.0


def _flat_in_y(scene, *zmodes):
    """Should these pieces' axes be compared in XZ only? (stepped, or D99.)"""
    if "stepped" in zmodes:
        return True
    return _band_case(scene) and any(z != "adaptive" for z in zmodes)


def _groups(scene):
    """[(track, section, [placements in build order])] - the unit every
    along-the-chain check measures over."""
    out = []
    for track in scene.tracks:
        cid = str(track["curve"].curve_id)
        for section in track["sections"]:
            group = [p for p in scene.plan
                     if str(p.curve_id) == cid
                     and p.section_index == section.index]
            if group:
                group.sort(key=lambda p: (p.s0, p.slot, p.index))
                out.append((track, section, group))
    return out


# --- the checks -------------------------------------------------------------

def element_count(scene):
    """Every planned piece became exactly one element (3.4's address is 1:1)."""
    n_geo, n_plan = len(scene.by_id), len(scene.plan)
    return Result("element_count", n_geo == n_plan, n_geo,
                  "" if n_geo == n_plan else "plan has %d" % n_plan)


def unique_elem_ids(scene):
    """`pc_elem_id` is an ADDRESS (D1). Two pieces sharing one breaks
    swap/replace silently, so it is counted rather than assumed."""
    ids = [p.elem_id for p in scene.plan]
    dupes = len(ids) - len(set(ids))
    return Result("duplicate_elem_ids", dupes == 0, dupes)


def sampler_matches_kernel(scene, samples=400):
    """The cached sampler and the kernel's own agree about where a metre is.

    ⚠️ ON THE BASE PATH, not on the conformed one. 4.5 wraps the Path in the
    drape (D54), and the drape is SUPPOSED to disagree with the spline - by
    the ridge amplitude, which read as a 0.800 m sampler defect the first time
    this ran on a conformed case. What this check owns is that `place.Path`
    has not drifted from `Curve.sample`; the drape is measured by
    `conform_contact_m`.
    """
    worst = 0.0
    for track in scene.tracks:
        curve, path = track["real"], track["path"]
        path = getattr(path, "base", path)
        total = curve.length
        if total <= 0.0:
            continue
        for i in range(samples + 1):
            s = total * i / float(samples)
            for forward in (True, False):
                pa, ta = curve.sample(s, forward)
                pb, tb = path.sample(s, forward)
                worst = max(worst, _dist(pa, pb), _dist(ta, tb))
    return Result("sampler_matches_kernel", worst <= 1e-9, _round(worst, 12))


def section_coverage(scene):
    """[shortfall, overshoot] in metres.

    The SHORTFALL is the assertion - a run that stops early would let
    `exact_fill_m` pass by measuring a short run against its own short end.
    The overshoot is recorded, not asserted, because a piece anchored on a
    MARKER near the end legitimately overhangs it (D20 allows the module's own
    geometry to overhang, D30 makes the sampler carry it): clamping it would
    move the gate off the marker it was placed on, which is PC-G1's own
    acceptance criterion.
    """
    short, over, where, empty = 0.0, 0.0, "", 0
    for _track, section, group in _groups(scene):
        a, b = _fill_span(section)
        # D40's boundary piece is a `default` piece that does NOT ride the
        # path: it is anchored on the leg and deliberately reaches past the
        # section end, so counting it here measured the displacement policy
        # as a 2.0 m coverage shortfall instead of the fill.
        run = [p for p in group
               if p.slot != "corner" and p.anchor is None]
        if not run:
            # D44 squeezed a corner assembly onto a section shorter than it,
            # so there is no default run left to cover anything. That case is
            # asserted by `pc_warn_overflow`, not by a coverage number that
            # would otherwise measure the corner against the fill span.
            empty += 1
            continue
        d = max(abs(min(p.s0 for p in run) - a),
                max(b - max(p.s1 for p in run), 0.0))
        over = max(over, max(p.s1 for p in run) - b)
        if d > short:
            short, where = d, "%s[%d]" % (group[0].curve_id, section.index)
    return Result("section_coverage_m", short <= TOL_M,
                  [_round(short), _round(max(over, 0.0))],
                  where or ("%d sections fully reserved by corners" % empty
                            if empty else ""))


WARN_DEGENERATE_FRAME = "pc_warn_degenerate_frame"       # place / __init__
WARN_CORNER_DEGENERATE = "pc_warn_corner_degenerate"     # place / __init__


def _mitered(scene, placement):
    """Was this piece cut on a corner's bisector plane (4.3)?

    A mitered piece is DELIBERATELY not the module any more: its end face is
    gone, its local x extent is short by the miter, and its axis leaves the
    curve on the leg's extension (D38). Every along-the-chain check therefore
    skips it and COUNTS the skips - and what replaces them is not nothing, it
    is the `corner_*` family, which measures the joint the miter actually
    made.
    """
    return bool(placement is not None and placement.cuts)


def _fill_span(section):
    """[a, b] section-local metres the default run was fitted into.

    4.3 hands a section less span than it has whenever a corner assembly
    reserves some (or more, when a displacement policy pushes the run through
    the vertex). Measuring exact fill against the SECTION end after that is
    measuring the corner, not the fit.
    """
    return (getattr(section, "fill_a", 0.0),
            getattr(section, "fill_b", section.length))


def _degenerate(scene, placement):
    """Did this piece's yaw frame collapse (D32)?

    A yaw-only z-mode measures along the horizontal, so on a (near-)vertical
    span there is no horizontal direction left and the piece cannot both stay
    flat AND land its ends on the curve. It keeps flat - which is what the mode
    means, and `flat_stepped_m` and `plumb_deg` still assert it - and says so
    with a warning. The along-the-chain checks skip exactly the pieces carrying
    that warning, and COUNT them, so the exemption cannot quietly widen.
    """
    return WARN_DEGENERATE_FRAME in scene.warns.get(placement.elem_id, {})


def exact_fill(scene):
    """The run ENDS where the section ends - measured on built geometry."""
    worst, where, skipped = 0.0, "", 0
    for track, section, group in _groups(scene):
        path, remap = track["path"], track["remap"]
        run = [p for p in group
               if p.slot != "corner" and not _mitered(scene, p)]
        if len(run) != len(group):
            skipped += 1
        if not run:
            continue
        first = scene.by_id.get(run[0].elem_id)
        last = scene.by_id.get(run[-1].elem_id)
        if first is None or last is None:
            continue
        if _degenerate(scene, run[0]) or _degenerate(scene, run[-1]):
            skipped += 1
            continue
        pairs = ((path.sample(remap(section.s0 + run[0].s0))[0],
                  axis_points(first)[0], run[0], "start"),
                 (path.sample(remap(section.s0 + run[-1].s1),
                              forward=False)[0],
                  axis_points(last)[1], run[-1], "end"))
        for want, got, placement, tag in pairs:
            if got is None:
                continue
            # A stepped piece is FLAT by definition, so its ends sit at its own
            # base height and not on the curve. That is the mode, not an error:
            # it is measured in XZ here and as `stepped_riser_m` below.
            d = (_dist_xz(want, got)
                 if _flat_in_y(scene, placement.zmode) else _dist(want, got))
            if d > worst:
                worst, where = d, "%s[%d] %s" % (group[0].curve_id,
                                                 section.index, tag)
    return Result("exact_fill_m", worst <= TOL_M, _round(worst),
                  where or ("%d sections skipped (miter/degenerate)" % skipped
                            if skipped else ""))


def no_gaps_or_overlaps(scene):
    """Consecutive pieces meet. D21 makes this exact, not approximate."""
    worst, where, skipped = 0.0, "", 0
    for _track, _section, group in _groups(scene):
        for a, b in zip(group, group[1:]):
            ra, rb = scene.by_id.get(a.elem_id), scene.by_id.get(b.elem_id)
            if ra is None or rb is None:
                continue
            if _degenerate(scene, a) or _degenerate(scene, b) \
                    or _mitered(scene, a) or _mitered(scene, b) \
                    or "corner" in (a.slot, b.slot):
                skipped += 1
                continue
            end_a, start_b = axis_points(ra)[1], axis_points(rb)[0]
            if end_a is None or start_b is None:
                continue
            stepped = _flat_in_y(scene, a.zmode, b.zmode)
            d = _dist_xz(end_a, start_b) if stepped else _dist(end_a, start_b)
            if d > worst:
                worst, where = d, "%s -> %s" % (a.module, b.module)
    return Result("max_gap_m", worst <= TOL_M, _round(worst),
                  where or ("%d degenerate pairs skipped" % skipped
                            if skipped else ""))


def stepped_riser(scene):
    """The vertical step between consecutive stepped pieces - the mode's own
    signature. Recorded, never asserted: on the flat it is 0, on a grade it is
    the piece length times the grade."""
    worst = 0.0
    seen = False
    for _track, _section, group in _groups(scene):
        for a, b in zip(group, group[1:]):
            if "stepped" not in (a.zmode, b.zmode):
                continue
            ra, rb = scene.by_id.get(a.elem_id), scene.by_id.get(b.elem_id)
            if ra is None or rb is None:
                continue
            end_a, start_b = axis_points(ra)[1], axis_points(rb)[0]
            if end_a is None or start_b is None:
                continue
            seen = True
            worst = max(worst, abs(end_a[1] - start_b[1]))
    if not seen:
        return _skip("stepped_riser_m", "no consecutive stepped pieces")
    return Result("stepped_riser_m", True, _round(worst, 6))


def stepped_float(scene):
    """D98 - the AIR under a stepped piece, in metres, at its worst point.

    `stepped_riser_m` measures the step BETWEEN two flat pieces, which is the
    mode's own signature and never goes away. This measures the other half of
    the same geometry - how far the piece's own underside sits ABOVE the
    ground beneath it - which is 4.4's flatten-under, and which does.

    A stepped piece is flat at ONE elevation. With the flatten off that
    elevation is its uphill end (4.4's "constant Z"), so on a descending run
    its whole underside floats and the fence hangs in the air by the drop
    across each piece; reversing the spline buries it by the same amount
    instead. With `flatten_stepped` on the elevation is the LOWEST ground
    under the piece, so this number goes to zero and stays there in both
    directions. Positive is air; a buried piece reads 0, because a fence post
    in the ground is not a defect.

    Measured on the piece's OWN bottom points against the path they sit over
    - the same path the builder placed them on, conform included - so the
    number is the builder's, not a re-derivation of the terrain.
    """
    worst, where, seen = 0.0, "", 0
    for track, section, group in _groups(scene):
        path, remap = track["path"], track["remap"]
        for p in group:
            if p.zmode != "stepped" or p.anchor is not None:
                continue
            rec = scene.by_id.get(p.elem_id)
            if rec is None:
                continue
            loc, wrl = rec["local"], rec["world"]
            xs = loc[0::3]
            if not xs:
                continue
            x0, x1 = min(xs), max(xs)
            ylo = min(loc[1::3])
            s0 = remap(section.s0 + p.s0)
            s1 = remap(section.s0 + p.s1)
            seen += 1
            for i in range(0, len(loc), 3):
                if loc[i + 1] > ylo + LOCAL_TOL:
                    continue                 # not on the underside
                f = 0.0 if x1 - x0 <= 1e-9 else (loc[i] - x0) / (x1 - x0)
                gy = path.sample(s0 + f * (s1 - s0))[0][1]
                if wrl[i + 1] - gy > worst:
                    worst = wrl[i + 1] - gy
                    where = "%s %s[%d]" % (p.module, p.slot, p.index)
    if not seen:
        return _skip("stepped_float_m", "no stepped pieces on a path")
    # ASSERTED once the flatten is on, and only then: off is RailClone's own
    # start-anchored behaviour and this number is then the recorded size of
    # the defect (D98's own "before"). It was recorded-only, and a mutation
    # proved that too weak - dropping the datum from the D58 HERO path moved
    # it 0.0 -> 0.029089 m with every check in the suite still green.
    ok = worst <= TOL_M if getattr(scene.params, "flatten_stepped",
                                   False) else True
    return Result("stepped_float_m", ok, _round(worst, 6),
                  where or ("%d stepped pieces" % seen))


def _by_zmode(scene, zmode):
    return [r for r in scene.by_id.values() if r["pc_zmode"] == zmode]


def plumb_vertical(scene):
    recs = _by_zmode(scene, "vertical")
    if not recs:
        return _skip("plumb_deg", "no vertical-mode pieces")
    worst = max(up_tilt_deg(r) for r in recs)
    return Result("plumb_deg", worst <= 1e-4, _round(worst, 7),
                  "%d pieces" % len(recs))


def flat_stepped(scene):
    recs = _by_zmode(scene, "stepped")
    if not recs:
        return _skip("flat_stepped_m", "no stepped pieces")
    if _band_case(scene):
        # D99: a banded stepped piece is flat everywhere EXCEPT its band, so
        # "all of it flat" is the wrong assertion here. `band_hybrid_m`
        # asserts both halves separately instead - and asserts that the band
        # actually moved, which this check could never see.
        return _skip("flat_stepped_m", "banded - see band_hybrid_m (D99)")
    worst = max(flatness_m(r) for r in recs)
    return Result("flat_stepped_m", worst <= TOL_M, _round(worst),
                  "%d pieces" % len(recs))


def band_hybrid(scene):
    """D99 - [flat half's spread, following half's spread], in metres.

    The band mechanism is TWO claims and one number cannot carry both: the
    half of the piece that should be level has to be level, AND the half that
    should follow the ground has to have actually moved. A band that silently
    did nothing would leave the first number at 0 and pass any check that
    only asked the first question - so the second number is the anti-vacuity
    half, and it is asserted to be non-zero on a slope.

    Both are measured as the spread of (world y - local y) within one piece,
    which is `flatness_m`'s own measure restricted to a set of points: 0 for
    a level set, the ground's own range for a following one.
    """
    if not _band_case(scene):
        return _skip("band_hybrid_m", "no band on this case")
    side = scene.params.flat_band
    size = float(scene.params.flat_band_m)
    flat_worst, follow_worst, seen = 0.0, 0.0, 0
    for eid, rec in scene.by_id.items():
        zmode = rec["pc_zmode"]
        if zmode not in ("vertical", "stepped"):
            continue
        src = scene.sources.get(rec["pc_module"])
        if src is None:
            continue
        bb = src.boundingBox()
        y0, y1 = bb.minvec()[1], bb.maxvec()[1]
        lo, hi = ((y1 - size, y1 + 1.0) if side == "top"
                  else (y0 - 1.0, y0 + size))
        loc, wrl = rec["local"], rec["world"]
        flat, follow = [], []
        for i in range(0, len(loc), 3):
            inside = lo <= loc[i + 1] <= hi
            (follow if inside == (zmode == "stepped") else flat).append(
                wrl[i + 1] - loc[i + 1])
        if not flat or not follow:
            continue
        seen += 1
        flat_worst = max(flat_worst, max(flat) - min(flat))
        follow_worst = max(follow_worst, max(follow) - min(follow))
    if not seen:
        return _skip("band_hybrid_m", "no banded piece had both halves")
    ok = flat_worst <= TOL_M and follow_worst > TOL_M
    return Result("band_hybrid_m", ok,
                  [_round(flat_worst), _round(follow_worst)],
                  "%d pieces, band %s %.3f m" % (seen, side, size))


def band_datum(scene):
    """D105 - how far a D99 LEVEL BAND sits from the extremum of the ground
    under its OWN piece, in metres.

    `band_hybrid_m` proves two things about a band and neither of them is
    this one: that the level half is level, and that the following half
    actually moved. WHAT elevation the level half levelled to was nobody's
    number, and the answer was "whatever the ground happened to be where the
    walk started" - so on the suite's own hill the same fence drawn backwards
    put every level top rail 0.490874 m elsewhere, and `flatten_stepped`, the
    parm whose whole promise is that the fence comes out the same whichever
    way the spline was drawn, did not reach the band at all.

    A datum taken as an EXTREMUM over the piece's own span cannot depend on
    which end the walk started at, which is why this number goes to 0 with
    the flatten on and stays there reversed. Which extremum is the band's own
    side: a level TOP band is a rail held over the piece, so it takes the
    highest ground and never dips into the body it caps; a level bottom band
    is D98's flatten-under and takes the lowest.

    Only asserted when `flatten_stepped` is on - off is RailClone's own
    start-anchored behaviour (D105), and the number is then the recorded
    size of the direction dependence rather than a failure.
    """
    if not _band_case(scene):
        return _skip("band_datum_m", "no band on this case")
    side = scene.params.flat_band
    size = float(scene.params.flat_band_m)
    worst, where, seen = 0.0, "", 0
    for track, section, group in _groups(scene):
        path, remap = track["path"], track["remap"]
        for p in group:
            if p.zmode not in ("vertical", "stepped") or p.anchor is not None:
                continue
            rec = scene.by_id.get(p.elem_id)
            src = None if rec is None else scene.sources.get(rec["pc_module"])
            if src is None:
                continue
            bb = src.boundingBox()
            y0, y1 = bb.minvec()[1], bb.maxvec()[1]
            lo, hi = ((y1 - size, y1 + 1.0) if side == "top"
                      else (y0 - 1.0, y0 + size))
            loc, wrl = rec["local"], rec["world"]
            xs = loc[0::3]
            if not xs:
                continue
            # the LEVEL half is the band on a plumb piece and everything but
            # the band on a flat one - `place._follows` read backwards.
            level = [wrl[i + 1] - loc[i + 1] for i in range(0, len(loc), 3)
                     if (lo <= loc[i + 1] <= hi)
                     == (p.zmode == "vertical")]
            if not level:
                continue
            # `min` for the level BOTTOM of a plumb piece and for a flat
            # piece (D98); `max` for a level top rail (D105).
            pick = max if (side == "top" and p.zmode == "vertical") else min
            x0, x1 = min(xs), max(xs)
            s0 = remap(section.s0 + p.s0)
            s1 = remap(section.s0 + p.s1)
            ground = [path.sample(s0 + f * (s1 - s0))[0][1]
                      for f in (sorted(set((x - x0) / (x1 - x0)
                                           for x in xs))
                                if x1 - x0 > 1e-9 else [0.0])]
            seen += 1
            d = abs(sum(level) / len(level) - pick(ground))
            if d > worst:
                worst, where = d, "%s %s[%d]" % (p.module, p.slot, p.index)
    if not seen:
        return _skip("band_datum_m", "no banded piece had a level half")
    ok = worst <= TOL_M if getattr(scene.params, "flatten_stepped", False)         else True
    return Result("band_datum_m", ok, _round(worst, 6),
                  where or ("%d banded pieces" % seen))


STAMP_PIECE_PRIMS = 3


def stamp_parity(scene, place):
    """The BULK stamp the build runs against the per-prim writer it replaced,
    re-proved on THIS build rather than in a scratchpad that ran once.

    The parity was measured when D102 landed - 83 cases, 163 115 prim
    attribute values, 0 differences - and then nothing in the repo re-asked
    it. Every other check reads a stamp from the FIRST prim of an element
    (`elements` takes `_attrs` from the first prim it sees), so a bulk writer
    that corrupted prims 2..n of a deformed piece would leave every case and
    the 9-row ladder green.

    ⚠️ REWRITTEN FOR 11.2 P1, AND THE SHAPE IS THE POINT. D102's writer
    stamped ONE PIECE at a time, so this used to compare one piece's
    geometry; P1's `_stamp_bulk` accumulates across the WHOLE OUTPUT and
    writes one array per attribute at the end, and its named risk is exactly
    that those arrays stop lining up with `out`'s prim numbering. So the
    whole case is stamped in ONE `_stamp_bulk` call, every element given
    `STAMP_PIECE_PRIMS` prims, and the per-prim writer fills a twin geometry
    element by element. A column shifted by one element is then a difference
    on nearly every prim; on the old per-piece shape it was invisible.

    Comparison is over 3.4's whole name set plus every warn name in the case,
    not over the names the element itself carries - an element that did NOT
    warn has to read 0 where its neighbour reads 1, which is the half a
    per-element comparison cannot ask.
    """
    plan = scene.report["plan"]
    if not plan:
        return _skip("stamp_parity", "nothing was built")
    warns = tuple(scene.report["warn_names"])
    rows, per_rows = [], []
    for p in plan:
        rec = scene.by_id.get(p.elem_id)
        if rec is None:
            continue
        zmode, deformed = rec["pc_zmode"], bool(rec["pc_deformed"])
        replaced = bool(rec.get("pc_replaced"))
        # the element's OWN warnings, read back off the build, so the warn
        # half of the stamp is compared too rather than assumed empty.
        here = tuple(w for w in warns if rec.get(w))
        values = place._stamp_values(p, here, deformed, zmode, replaced)
        rows.append((STAMP_PIECE_PRIMS, values))
        per_rows.append((p.elem_id, values))
    if not rows:
        return _skip("stamp_parity", "no element resolved")
    bulk, per = hou.Geometry(), hou.Geometry()
    for geo in (bulk, per):
        for _ in range(len(rows) * STAMP_PIECE_PRIMS):
            poly = geo.createPolygon()
            for _v in range(3):
                poly.addVertex(geo.createPoint())
        place._declare(geo, warns)
    place._stamp_bulk(bulk, rows, warns)
    prims = per.prims()
    for i, (_eid, values) in enumerate(per_rows):
        for prim in prims[i * STAMP_PIECE_PRIMS:(i + 1) * STAMP_PIECE_PRIMS]:
            for name, value in values:
                prim.setAttribValue(name, value)
    names = [n for n, _d in place.ELEM_PRIM_ATTRS] + list(warns)
    compared = diffs = 0
    where = ""
    a_prims, b_prims = bulk.prims(), per.prims()
    for name in names:
        for i, (a, b) in enumerate(zip(a_prims, b_prims)):
            compared += 1
            if a.attribValue(name) != b.attribValue(name):
                diffs += 1
                where = where or "%s/%s" % (
                    per_rows[i // STAMP_PIECE_PRIMS][0], name)
    return Result("stamp_parity", diffs == 0, [compared, diffs], where)


def bank_adaptive(scene, require_bank=False):
    recs = _by_zmode(scene, "adaptive")
    if not recs:
        return _skip("bank_deg", "no adaptive-mode pieces")
    worst = max(up_tilt_deg(r) for r in recs)
    ok = (worst > 0.5) if require_bank else True
    return Result("bank_deg", ok, _round(worst, 5),
                  "" if ok else "adaptive pieces did not bank on a slope")


def determinism(scene, rebuild):
    """Same inputs cooked twice => identical positions AND identical ids."""
    try:
        geo2, report2 = rebuild(scene.case)
    except Exception as exc:
        return Result("determinism", False, None, str(exc)[:200])
    a, b = elements(scene.geo), elements(geo2)
    if len(a) != len(b):
        return Result("determinism", False, "%d vs %d" % (len(a), len(b)),
                      "element count moved")
    moved, worst = 0, 0.0
    for ra, rb in zip(a, b):
        if ra["pc_elem_id"] != rb["pc_elem_id"] \
                or len(ra["world"]) != len(rb["world"]):
            moved += 1
            continue
        for x, y in zip(ra["world"], rb["world"]):
            if x != y:
                moved += 1
                worst = max(worst, abs(x - y))
                break
    ids_a = [p.elem_id for p in scene.plan]
    ids_b = [p.elem_id for p in report2["plan"]]
    ok = (moved == 0 and ids_a == ids_b)
    return Result("determinism", ok, moved,
                  "" if ok else "worst %.3e m, ids equal=%s"
                  % (worst, ids_a == ids_b))


def warnings(scene, expected=()):
    """3.4's warnings, persisted as attributes. On clean input the answer is
    an EMPTY list - that is the check, not a comment."""
    counts = {}
    for name in scene.report["warn_names"]:
        counts[name] = sum(1 for w in scene.warns.values() if w.get(name))
    got = sorted(k for k, v in counts.items() if v)
    ok = got == sorted(expected)
    # Lists, not tuples: the baseline is JSON, and a tuple round-trips as a
    # list, which would report every warning row as "moved" on every run.
    return Result("warnings", ok, [[k, v] for k, v in sorted(counts.items())],
                  "" if ok else "expected %s" % (sorted(expected),))


def instancing_split(scene, expect_all=False, expect_none=False):
    """4.6's segregation, measured: how many pieces stayed packed. A build
    that unpacked everything would still be geometrically correct and would
    still be a defect.

    `expect_all` is the INSTANCING FLOOR, asserted on the cases that have no
    excuse: a straight run of rigid modules must be 100 % packed. Every other
    case records the count and lets the baseline catch a drift, because what
    the right fraction IS depends on the figure - which is what
    `over_unpacked` measures instead.
    """
    packed = scene.report["packed"]
    total = packed + scene.report["deformed"]
    ok = True
    if expect_all:
        ok = packed == total
    elif expect_none:
        # D75's anti-vacuity control: a curve whose every span leaves the
        # chord by five times `bend_tol` must unpack every piece of it.
        ok = packed == 0
    return Result("packed_pieces", ok, packed,
                  "of %d" % total if ok
                  else "of %d - the instancing floor/ceiling for this case"
                  % total)


def slice_caps_closed(scene):
    """A sliced piece is capped (4.6). Open edges on any element is a hole."""
    holes = open_edges(scene.geo)
    worst = max(holes.values()) if holes else 0
    bad = sorted(k for k, v in holes.items() if v)
    return Result("open_edges", worst == 0, worst,
                  ("first: %s" % bad[0]) if bad else "")


def cap_tagged(scene, expect=0):
    """...and the cap carries `pc_cap = 1` (D28), so a downstream material
    assignment has something to select."""
    if scene.geo.findPrimAttrib("pc_cap") is None:
        n = 0
    else:
        n = sum(1 for p in scene.geo.prims()
                if p.type() != hou.primType.PackedGeometry
                and int(p.attribValue("pc_cap")) == 1)
    return Result("cap_prims", n >= expect, n,
                  "" if n >= expect else "expected at least %d" % expect)


KIT_WARN_ATTR = "pc_kit_warnings"       # place.KIT_WARN_ATTR


def kit_validation(scene, expect_min=0, expect_max=0):
    """The validator reports, never raises (D24) - and the report is PERSISTED.

    Read off the output geometry, not out of the Python report: a warning that
    lives only in a returned dict dies with the call, so a kit missing `kitId`
    or carrying a duplicate module name would cook clean forever on the HDA.
    Reading the attribute makes the check fail if the persisting is ever
    dropped, which reading the report could not.
    """
    if scene.geo.findGlobalAttrib(KIT_WARN_ATTR) is None:
        return Result("kit_warnings", False, None,
                      "%s not written on the output" % KIT_WARN_ATTR)
    warns = list(scene.geo.attribValue(KIT_WARN_ATTR))
    n = len(warns)
    ok = expect_min <= n <= expect_max
    return Result("kit_warnings", ok, n,
                  "" if ok else "expected %d..%d: %s"
                  % (expect_min, expect_max, warns[:3]))


def marker_offset(scene, marker_id, world_pos):
    """PC-G1: "gate exactly at its marker". Measured, in metres."""
    slot = "marker:%d" % marker_id
    hits = [p for p in scene.plan if p.slot == slot]
    if not hits:
        return Result("marker_offset_m", False, None, "no piece in %s" % slot)
    rec = scene.by_id.get(hits[0].elem_id)
    if rec is None:
        return Result("marker_offset_m", False, None, "no geometry")
    a, b = axis_points(rec)
    mid = tuple(0.5 * (a[k] + b[k]) for k in range(3))
    return Result("marker_offset_m", _dist(mid, world_pos) <= TOL_M,
                  _round(_dist(mid, world_pos)), hits[0].module)


def output_schema(scene):
    """3.4's stamps are all present and non-empty where they must be."""
    missing = [name for name in
               ("pc_elem_id", "pc_slot", "pc_module", "pc_section", "pc_u",
                "pc_generated", "pc_deformed", "pc_elem_key", "pc_variant",
                "pc_zmode")
               if scene.geo.findPrimAttrib(name) is None]
    blank = sum(1 for r in scene.by_id.values()
                if not r["pc_elem_id"] or not r["pc_module"]
                or r["pc_generated"] != 1)
    ok = not missing and blank == 0
    return Result("output_schema", ok, len(missing) + blank,
                  ("missing %s" % missing) if missing else
                  ("%d blank elements" % blank if blank else ""))


def axis_follows_curve(scene):
    """A BENDABLE piece's own axis lies on the curve at every one of its
    stations - not just at its two ends.

    ⚠️ This exists because of a hole found by mutation, not by reasoning:
    deleting the interior-vertex test in `_needs_deform` (so every bendable
    piece stayed a packed chord across the bend) moved NOTHING. `exact_fill_m`
    and `max_gap_m` both measure the piece's END POINTS, and a chord has the
    same end points as the arc it cuts. Only the inside of the piece knows.

    Rigid modules are excluded: cutting the corner is what rigid MEANS, and
    the sagitta they leave is measured as `bend_deg`-adjacent behaviour
    elsewhere. Stepped pieces are compared in XZ, since flat is the mode.
    """
    worst, where, seen, bad = 0.0, "", 0, []
    for eid, rec in scene.by_id.items():
        module = scene.kit.by_name(rec["pc_module"])
        placement = scene.plan_by_id.get(eid)
        if module is None or module.deform < 1 or placement is None:
            continue
        # D75: a PACKED bendable piece is allowed to cut its span by up to
        # `bend_tol` - that budget is why it stayed packed at all, and the
        # mutation this check was written against (deleting the deform gate
        # outright) still fails here because it cuts by far more than the
        # budget. A DEFORMED piece has no such excuse and is held to TOL_M.
        limit = (TOL_M if rec["pc_deformed"]
                 else max(TOL_M, scene.params.bend_tol))
        if _mitered(scene, placement) or placement.slot == "corner":
            continue        # the miter cut its faces off; corner_* measures it
        track = scene.track_of.get(str(placement.curve_id))
        section = scene.section_of.get((str(placement.curve_id),
                                        placement.section_index))
        if track is None or section is None or module.length <= 0.0:
            continue
        xs = rec["local"][0::3]
        if not xs:
            continue
        ax = min(xs)
        scale = (1.0 if placement.slice_t is not None
                 else (placement.s1 - placement.s0) / module.length)
        stations = []
        for x in sorted(set(round(v, 6) for v in xs)):
            if not stations or x - stations[-1] > LOCAL_TOL:
                stations.append(x)
        for x in stations:
            got = _axis_of(_face(rec, x))
            if got is None:
                continue
            s_flat = section.s0 + placement.s0 + (x - ax) * scale
            want = track["path"].sample(track["remap"](s_flat))[0]
            d = (_dist_xz(want, got)
                 if _flat_in_y(scene, placement.zmode) else _dist(want, got))
            seen += 1
            if d > limit:
                bad.append(eid)
            if d > worst:
                worst, where = d, "%s @ x=%.3f" % (rec["pc_module"], x)
    if not seen:
        return _skip("axis_on_curve_m", "no bendable pieces")
    return Result("axis_on_curve_m", not bad, _round(worst),
                  where if not bad else "%s - %d over budget, first %s"
                  % (where, len(bad), bad[0]))


def cross_section_width(scene):
    """The piece is as WIDE across the chain as the module it instances.

    ⚠️ ADDED AFTER A MUTATION SURVIVED. Replacing the yaw-only frame with the
    full 3D tangent leaves `across` UN-NORMALISED - it keeps only the tangent's
    horizontal part - so on a 25 % grade every piece came out 3 % narrow, and
    `plumb_deg`, `flat_stepped_m`, `exact_fill_m`, `max_gap_m` and
    `axis_on_curve_m` all stayed green: not one of them looks across the
    chain. Dropping the across term entirely (pieces collapsed to a ribbon)
    survived for the same reason.
    """
    worst, where = 0.0, ""
    for rec in scene.by_id.values():
        loc, wrl = rec["local"], rec["world"]
        rows = {}
        for i in range(0, len(loc), 3):
            key = (round(loc[i], 5), round(loc[i + 1], 5))
            rows.setdefault(key, []).append(
                (loc[i + 2], (wrl[i], wrl[i + 1], wrl[i + 2])))
        for row in rows.values():
            if len(row) < 2:
                continue
            row.sort(key=lambda t: t[0])
            want = row[-1][0] - row[0][0]
            if want <= LOCAL_TOL:
                continue
            got = _dist(row[0][1], row[-1][1])
            if abs(got - want) > worst:
                worst = abs(got - want)
                where = "%s want %.4f got %.4f" % (rec["pc_module"], want, got)
    return Result("cross_section_m", worst <= TOL_M, _round(worst), where)


def stepped_riser_is(scene, expected, tol=1e-3):
    """`stepped_riser_m` as an ASSERTION, for the one case that needs it.

    ⚠️ ADDED AFTER A MUTATION SURVIVED. D70's drop looks BOTH ways along the
    axis and the NEAREST hit wins; cutting that down to "look up-axis only
    when nothing was found down-axis" moved not one number in the suite,
    because the up-axis cast won 12 405 times and every one of those was for
    want of anything below. `BN_conform_overhead` is the case where both
    directions hit, and the riser at the deck's edge is the answer: 3.4 m if
    the middle of the run climbed onto the deck 0.4 m up, 0 if it stayed on
    the ground 3.0 m down. `stepped_riser` itself records rather than asserts
    (it is a shape report on every case), so the assertion lives here.
    """
    r = stepped_riser(scene)
    if r.skipped:
        return r
    return Result("stepped_riser_is_m", abs(r.value - expected) <= tol,
                  r.value, "expected %.4f" % expected)


def horizontal_span_is(scene, expected, tol=2e-3):
    """The widest piece reaches exactly this far horizontally.

    ⚠️ ALSO ADDED AFTER A MUTATION SURVIVED. `exact_fill_m` and friends read
    the section through the SAME remap the builder used, so replacing the
    slope-fixing remap with the identity moved none of them - the check and
    the defect agreed with each other. This number does not go through the
    remap at all: it is 1.60 m (the gate's own width) when slope fixing is on
    and 1.60*cos(atan(grade)) when it is off, and those are the two halves of
    iToo's sentence about what "width" means on a slope.
    """
    spans = []
    for rec in scene.by_id.values():
        a, b = axis_points(rec)
        if a is not None and b is not None:
            spans.append(_dist_xz(a, b))
    if not spans:
        return _skip("horizontal_span_is", "no pieces")
    got = max(spans)
    return Result("widest_horizontal_m", abs(got - expected) <= tol,
                  _round(got, 6), "expected %.6f" % expected)


def module_fidelity(scene):
    """The piece on the chain is the module its `pc_module` names.

    Measured as the piece's own local x extent against the kit's `pc_size.x`
    (times `slice_t` where the plan cut it). Without this, a proto cache that
    handed every placement the SAME geometry would satisfy every other check
    on this list - the ids, the fill, the frames would all still be right.
    """
    worst, where, unknown = 0.0, "", 0
    for eid, rec in scene.by_id.items():
        module = scene.kit.by_name(rec["pc_module"])
        if module is None:                     # a stand-in (3.4's kit gap)
            unknown += 1
            continue
        placement = scene.plan_by_id.get(eid)
        if _mitered(scene, placement):
            unknown += 1                    # 4.3: the miter took a bite (D41)
            continue
        want = module.length
        if placement is not None and placement.slice_t is not None:
            want *= placement.slice_t
        xs = rec["local"][0::3]
        if not xs:
            continue
        got = max(xs) - min(xs)
        if abs(got - want) > worst:
            worst = abs(got - want)
            where = "%s want %.4f got %.4f" % (rec["pc_module"], want, got)
    return Result("module_fidelity_m", worst <= TOL_M, _round(worst),
                  where or ("%d stand-ins or mitered" % unknown
                            if unknown else ""))


def rigid_never_deformed(scene):
    """4.4: bend only when `pc_deform >= 1`. A rigid module that came back as
    real geometry has been deformed, and the flag says so."""
    bad, mitered = [], 0
    for eid, rec in scene.by_id.items():
        module = scene.kit.by_name(rec["pc_module"])
        if module is None:
            continue
        if module.deform <= 0 and rec["pc_deformed"]:
            # D41: the FILL may only cut a module that opted in (pc_deform 2),
            # but a miter is not the fill's decision - it is the artist's
            # corner mode, and RailClone's Bevel Corner slices whatever segment
            # it is handed. The exemption is counted so it cannot widen
            # quietly: a rigid piece unpacked for any OTHER reason still fails.
            if _mitered(scene, scene.plan_by_id.get(eid)):
                mitered += 1
                continue
            bad.append(eid)
    return Result("rigid_deformed", not bad, len(bad),
                  bad[0] if bad else ("%d mitered" % mitered if mitered
                                      else ""))


def deformed_flag_matches_geometry(scene):
    """`pc_deformed` is the 4.6 segregation flag; if it disagreed with what
    the prim actually is, every downstream instancing decision would be made
    on a lie."""
    bad = 0
    for prim in scene.geo.prims():
        try:
            flag = int(prim.attribValue("pc_deformed"))
        except (hou.OperationFailed, TypeError, ValueError):
            bad += 1
            continue
        packed = prim.type() == hou.primType.PackedGeometry
        if packed == bool(flag):
            bad += 1
    return Result("deformed_flag_mismatch", bad == 0, bad)


def geometry_digest(scene):
    """A stable fingerprint of the whole build, recorded in the baseline.

    `determinism` proves two cooks agree inside ONE process. This is the other
    half: the digest is compared against the recorded one, so a change that
    only shows up in a different session (the `PYTHONHASHSEED` class of
    defect, which cycle 1 killed in the kernel and which the adapter could
    reintroduce) surfaces as a moved baseline value."""
    import hashlib
    h = hashlib.md5()
    for rec in sorted(scene.by_id.values(), key=lambda r: r["pc_elem_id"]):
        h.update(rec["pc_elem_id"].encode("utf-8"))
        h.update(("|%d|" % rec["pc_deformed"]).encode("utf-8"))
        h.update(",".join("%.6f" % v for v in rec["world"]).encode("utf-8"))
    return Result("geometry_digest", True, h.hexdigest()[:16])


def _station_xs(rec):
    """Sorted distinct local x values of one built element."""
    out = []
    for x in sorted(set(round(v, 6) for v in rec["local"][0::3])):
        if not out or x - out[-1] > LOCAL_TOL:
            out.append(x)
    return out


def _component_centres(geo):
    """({point number: the centre of ITS OWN connected shell}, {point: faces}).

    ⚠️ THE BBOX CENTRE OF THE WHOLE MODULE IS THE WRONG REFERENCE the moment a
    module is more than one box. A picket panel is two rails and four slats,
    and the slats' inward-facing sides point straight at the module centre
    while being perfectly correct - measured, 19 of 122 faces scored inward on
    geometry the box verb itself produced. The shell each face belongs to is
    the reference; a genuinely inside-out module still fails, because ALL of
    its faces point at its own shell centre.
    """
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for pt in geo.points():
        parent[pt.number()] = pt.number()
    for prim in geo.prims():
        nums = [p.number() for p in prim.points()]
        for n in nums[1:]:
            ra, rb = find(nums[0]), find(n)
            if ra != rb:
                parent[rb] = ra
    acc = {}
    for pt in geo.points():
        root = find(pt.number())
        pos = pt.position()
        cur = acc.setdefault(root, [0.0, 0.0, 0.0, 0])
        for k in range(3):
            cur[k] += pos[k]
        cur[3] += 1
    faces = {}
    for prim in geo.prims():
        pts = prim.points()
        if pts:
            root = find(pts[0].number())
            faces[root] = faces.get(root, 0) + 1
    centres = dict((pt.number(),
                    tuple(acc[find(pt.number())][k] / acc[find(pt.number())][3]
                          for k in range(3)))
                   for pt in geo.points())
    sizes = dict((pt.number(), faces.get(find(pt.number()), 0))
                 for pt in geo.points())
    return (centres, sizes)


def module_winding(scene):
    """Every face of every kit module points OUT (D33).

    ⚠️ WRITTEN DURING A REVIEW, AND IT FOUND THE WHOLE STARTER KIT INSIDE-OUT:
    `box_mesh` wound all six faces inward, so 18 of the gate's 18 faces scored
    inward on this exact test while the Box SOP verb scored 0 of 6 on the same
    one. Nothing else on this list looks at a normal, so every fence the tool
    built rendered interior-side-out and every normal-dependent op downstream
    (boolean, peak, displacement, one-sided shading) ran on inverted geometry.
    The reference is the box verb, not an opinion about handedness.
    """
    kit_geo = scene.case.get("kit")
    if kit_geo is None:
        return _skip("inward_faces", "no kit geometry")
    inward, total, unjudged = 0, 0, 0
    for prim in kit_geo.prims():
        if prim.type() != hou.primType.PackedGeometry:
            continue
        src = prim.getEmbeddedGeometry()
        centres, sizes = _component_centres(src)
        for face in src.prims():
            pts = face.points()
            if len(pts) < 3:
                continue
            total += 1
            root = pts[0].number()
            # ⚠️ AND AN UNWELDED SHELL IS NOT A PASS, IT IS AN UNKNOWN. When
            # every polygon owns its own points, each one is its own component
            # and its centre IS its centroid - the dot product is then zero for
            # every face and this check silently measures nothing. Found by
            # mutation: a flipped module went on passing because the mutation
            # harness had unwelded it. Fewer than four faces cannot enclose a
            # volume, so those faces are counted and the check fails on them.
            if sizes.get(root, 0) < 4:
                unjudged += 1
                continue
            centre = centres.get(root, src.boundingBox().center())
            cen = [sum(p.position()[k] for p in pts) / len(pts)
                   for k in range(3)]
            nrm = face.normal()
            if sum((cen[k] - centre[k]) * nrm[k] for k in range(3)) < 0.0:
                inward += 1
    if not total:
        return _skip("inward_faces", "no module faces")
    return Result("inward_faces", inward == 0 and unjudged == 0, inward,
                  "of %d, %d unjudged" % (total, unjudged))


def frame_continuity(scene):
    """A deformed piece's `across` vector never reverses between stations.

    ⚠️ ALSO FROM A REVIEW. `_frame` derived `across` from cross(tangent, up)
    with no memory, so wherever a tangent's horizontal direction reversed - an
    overhanging crest, a cliff lip - the frame flipped 180 degrees mid piece
    and the faces crossed through each other. Measured as the dot of two
    consecutive stations' unit `across`: 1 is a straight run, and the defect
    scored -1. Every other check stayed green through it, because none of them
    compares one station's frame with the next one's.

    ⚠ AND ITS THRESHOLD IS NOT "POSITIVE" ANY MORE, WHICH IS WHAT 4.3
    CORRECTED. Once bend mode stopped breaking the run at a corner (D36) a
    panel legitimately wraps a 90 degree vertex, and the two stations either
    side of it score EXACTLY 0.0 - a right angle, not a defect - while a 170
    degree degenerate-fallback corner scores -0.98. The frame is SUPPOSED to
    turn with the path; the defect was that it turned WITHOUT it. So the
    recorded number stays the minimum dot and the THRESHOLD moved to -0.866,
    i.e. a turn of more than 150 degrees between two adjacent stations. The
    crest defect scored -1.0 with the path barely turning; a right angle
    scores 0.0; and the one input that could legitimately reach -1 is a
    hairpin, which carries `pc_warn_corner_degenerate` and is skipped and
    counted rather than tolerated silently.
    """
    worst, where, seen, skipped = 1.0, "", 0, 0
    for eid, rec in scene.by_id.items():
        placement = scene.plan_by_id.get(eid)
        if WARN_CORNER_DEGENERATE in scene.warns.get(eid, {}):
            skipped += 1        # a hairpin really does turn the frame around
            continue
        if _mitered(scene, placement):
            # the bisector cut takes half of the end cross-section away, so
            # the affine frame read back off that face is fitted to whatever
            # survived - it is not the piece's frame, and reading it as one
            # scored a clean -1.0 on a corner post that had never rotated
            skipped += 1
            continue
        rows = []
        for x in _station_xs(rec):
            face = _face(rec, x)
            across, axis = _frame_of(face)[2], _axis_of(face)
            if across is None or axis is None:
                continue
            n = math.sqrt(sum(v * v for v in across))
            if n < 1e-9:
                continue
            rows.append((x, axis, tuple(v / n for v in across)))
        for i in range(len(rows) - 1):
            seen += 1
            got = sum(rows[i][2][k] * rows[i + 1][2][k] for k in range(3))
            if got < worst:
                worst, where = got, "%s @ x=%.3f" % (rec["pc_module"],
                                                     rows[i + 1][0])
    if not seen:
        return _skip("frame_dot_min", "no multi-station pieces")
    return Result("frame_dot_min", worst > -0.866, _round(worst, 6),
                  where + (" (%d pieces skipped)" % skipped
                           if skipped else ""))


def station_spacing(scene):
    """Two DISTINCT stations of a deformed piece never land on one point.

    ⚠️ THE END-CLAMP DETECTOR. `Path.sample` used to clamp arclength into
    [0, total] on an open curve, so a gate whose module legitimately overhangs
    the curve end had its last stations all read back the same end point and
    the tail of the piece was crushed into a zero-thickness plane. Every
    position-based check agreed with it, because they resolve the station
    through the same sampler: this one does not ask where the station SHOULD
    be, only whether two of them collapsed onto each other.
    """
    worst, where, seen = None, "", 0
    for rec in scene.by_id.values():
        if not rec["pc_deformed"]:
            continue
        frame = _element_frame(rec)
        pts = [_axis_of(_face(rec, x), frame) for x in _station_xs(rec)]
        pts = [p for p in pts if p is not None]
        for a, b in zip(pts, pts[1:]):
            seen += 1
            d = _dist(a, b)
            if worst is None or d < worst:
                worst, where = d, rec["pc_module"]
    if not seen:
        return _skip("station_spacing_m", "no deformed pieces")
    return Result("station_spacing_m", worst > TOL_M, _round(worst), where)


def piece_extent(scene):
    """No element is invisible ALONG THE CHAIN.

    ⚠️ THE DEGENERATE-FRAME DETECTOR (D32). A yaw-only z-mode on a vertical
    span scaled every piece by 1e-9: 25 posts of 0.0000 m along-axis width,
    stacked, and `warns=[]`. Zero-size geometry passes every other check on
    this list by having nothing left to measure.

    ⚠️ AND THE OBVIOUS MEASUREMENT - the piece's bounding-box diagonal - MISSES
    IT, which this check did until the mutation was run: the collapse is along
    the chain axis ONLY, so a post crushed to 1.2e-10 m of length still
    measures 1.2 m tall and 0.12 m wide and its diagonal never moves. The
    number has to be the piece's own axis span.
    """
    worst, where = None, ""
    for rec in scene.by_id.values():
        a, b = axis_points(rec)
        if a is None or b is None:
            continue
        d = _dist(a, b)
        if worst is None or d < worst:
            worst, where = d, rec["pc_module"]
    if worst is None:
        return _skip("min_piece_span_m", "no pieces")
    return Result("min_piece_span_m", worst > 1e-3, _round(worst), where)


def plan_geometry(scene, place):
    """4.2: "the plan is inspectable geometry" - and it is written, not just
    returned. One point per placement, at that placement's own start on the
    curve, carrying the plan payload."""
    geo = hou.Geometry()
    try:
        place.plan_points(geo, scene.report)
    except Exception as exc:
        return Result("plan_points", False, None,
                      "%s: %s" % (type(exc).__name__, str(exc)[:120]))
    n = len(geo.points())
    if n != len(scene.plan):
        return Result("plan_points", False, n,
                      "plan has %d" % len(scene.plan))
    worst = 0.0
    for pt, placement in zip(geo.points(), scene.plan):
        if pt.attribValue("pc_elem_id") != placement.elem_id:
            return Result("plan_points", False, n, "id mismatch")
        track = scene.track_of.get(str(placement.curve_id))
        section = scene.section_of.get((str(placement.curve_id),
                                        placement.section_index))
        if track is None or section is None:
            continue
        want = track["path"].sample(
            track["remap"](section.s0 + placement.s0))[0]
        worst = max(worst, _dist(want, pt.position()))
    return Result("plan_points", worst <= TOL_M, n, "worst %.3e m" % worst)


def plan_point_provenance(scene, place):
    """Every one of 4.2's FIFTEEN plan-point values, read back against the
    Placement it came from.

    ⚠️ `plan_points` asserted TWO of them - `pc_elem_id` and the position -
    and 11.2 P1 rewrites that writer into a bulk one. Found by mutation while
    P1 landed: shifting the `pc_u` column by one point left the whole suite
    green, which is standing finding (10) in a second writer. 5's
    plan-preview-while-dragging draws these, and an override stream addresses
    an element by them.

    Derived from the `Placement` objects rather than from `plan_dicts`, so
    this is a different expression reaching the same number - and note
    `pc_section` on a PLAN POINT is the section KEY (3.1's material-id limit),
    not the section index the prim stamp carries.

    [worst float delta, mismatched string/int values].
    """
    if not scene.plan:
        return _skip("plan_point_provenance", "nothing was planned")
    geo = hou.Geometry()
    try:
        place.plan_points(geo, scene.report)
    except Exception as exc:
        return Result("plan_point_provenance", False, None,
                      "%s: %s" % (type(exc).__name__, str(exc)[:120]))
    pts = geo.points()
    if len(pts) != len(scene.plan):
        return Result("plan_point_provenance", False, None,
                      "%d points, %d placements" % (len(pts), len(scene.plan)))
    elem_key = place._plan.elem_key
    worst, bad, where = 0.0, 0, ""
    for pt, p in zip(pts, scene.plan):
        want = {"pc_elem_id": p.elem_id, "pc_slot": p.slot,
                "pc_module": p.module, "pc_variant": p.variant,
                "pc_zmode": p.zmode, "pc_elem_key": elem_key(p.elem_id),
                "pc_section": int(p.section_key), "pc_index": int(p.index),
                "pc_deform": int(p.deform), "pc_plan": 1,
                "pc_s0": p.s0, "pc_s1": p.s1, "pc_u": p.u, "pc_scale": p.scale,
                "pc_slice_t": (-1.0 if p.slice_t is None
                               else float(p.slice_t))}
        for name, _default in place.PLAN_POINT_ATTRS:
            got, exp = pt.attribValue(name), want[name]
            if isinstance(exp, float):
                # P and every float attribute is stored float32, so the floor
                # scales with the coordinate - a 20 km `pc_s1` cannot be
                # compared at an absolute 1e-9.
                d = abs(float(got) - exp) / max(1.0, abs(exp))
                if d > worst:
                    worst, where = d, "%s %s" % (p.elem_id, name)
            elif got != exp:
                bad += 1
                where = where or "%s %s: %r != %r" % (p.elem_id, name,
                                                      got, exp)
    ok = worst <= 1e-6 and not bad
    return Result("plan_point_provenance", ok, [_round(worst, 9), bad], where)


def bend_deviation(scene):
    """D25's MEASUREMENT, not just its verdict - the worst distance any bent
    piece cuts its own corner by, in metres.

    ⚠️ ADDED BY MUTATION, NOT BY REASONING (11.2 P3). Moving the deviation
    probe 1 mm off its midpoint moved NOT ONE value in the whole suite: only
    the boolean `pc_warn_bend_resolution` was ever recorded, and 1 mm does not
    cross `bend_tol` on any case, so `warnings`, `warn_summary`,
    `curvature_budget_m` and `deform_gate_m` all stayed exactly where they
    were. §11.2 P3's own risk line says it - "it is a WARNING, so a silent
    change is invisible in geometry checks" - and it was right.

    Recorded, not asserted: what the number should BE is the geometry's
    business and `geometry_digest` already pins that. What this owns is that
    the number cannot change without anyone seeing it.
    """
    dev = scene.report.get("bend_deviation")
    if dev is None:
        return _skip("bend_deviation_m", "not reported")
    return Result("bend_deviation_m", True, _round(dev, 9),
                  "tol %.4f m" % scene.params.bend_tol)


def horizontal_spacing(scene):
    """D26's own number: the spread of the pieces' HORIZONTAL lengths. Slope
    fixing on a constant grade makes them equal to the source length; off,
    they are the horizontal projection of an arc allocation and are shorter by
    cos(slope)."""
    spans = []
    for rec in scene.by_id.values():
        a, b = axis_points(rec)
        if a is None or b is None:
            continue
        spans.append(_dist_xz(a, b))
    if not spans:
        return _skip("horizontal_span_m", "no pieces")
    return Result("horizontal_span_m", True,
                  [_round(min(spans), 6), _round(max(spans), 6)],
                  "%d pieces" % len(spans))


# --- 4.6 FINALIZE: instancing, overrides, ids --------------------------------

def _affine_residual(rec):
    """How far this element is from being AN AFFINE IMAGE of its own module.

    4.6's segregation rule is "a piece whose result is a transform x scale of
    its kit module stays a PACKED PRIM", so the honest test of an unpacked
    piece is whether that sentence is true of it: fit
    `world = O + M * local` over every point (centred, so `O` divides out and
    the linear part is one 3x3 solve) and take the worst residual. A bent,
    sheared or draped piece cannot be fitted; a piece that was unpacked for no
    reason fits to float noise, and that is the defect - it costs memory and
    kills instancing while looking perfect in the viewport.
    """
    loc, wrl = rec["local"], rec["world"]
    n = len(loc) // 3
    if n < 4:
        return None
    lc = [sum(loc[k::3]) / n for k in range(3)]
    wc = [sum(wrl[k::3]) / n for k in range(3)]
    m = [[0.0] * 3 for _ in range(3)]
    rhs = [[0.0] * 3 for _ in range(3)]
    for i in range(0, len(loc), 3):
        l = (loc[i] - lc[0], loc[i + 1] - lc[1], loc[i + 2] - lc[2])
        w = (wrl[i] - wc[0], wrl[i + 1] - wc[1], wrl[i + 2] - wc[2])
        for a in range(3):
            for b in range(3):
                m[a][b] += l[a] * l[b]
            for k in range(3):
                rhs[a][k] += l[a] * w[k]
    inv = _inv3(m)
    if inv is None:
        return None                     # a degenerate point cloud proves nothing
    fit = [[sum(inv[a][b] * rhs[b][k] for b in range(3)) for k in range(3)]
           for a in range(3)]
    worst = 0.0
    for i in range(0, len(loc), 3):
        l = (loc[i] - lc[0], loc[i + 1] - lc[1], loc[i + 2] - lc[2])
        for k in range(3):
            got = wc[k] + sum(l[a] * fit[a][k] for a in range(3))
            worst = max(worst, abs(got - wrl[i + k]))
    # ...and whether that affine is a TRANSFORM x AXIS SCALE, which is 4.6's
    # own wording, or a SHEAR, which is not. The three image vectors of the
    # local axes must be mutually perpendicular; a `vertical` piece on a
    # uniform slope fits an affine perfectly and is a pure shear (D65).
    skew = 0.0
    for a in range(3):
        for b in range(a + 1, 3):
            na = math.sqrt(sum(v * v for v in fit[a]))
            nb = math.sqrt(sum(v * v for v in fit[b]))
            if na < 1e-9 or nb < 1e-9:
                continue
            skew = max(skew, abs(_dot3(fit[a], fit[b])) / (na * nb))
    return (worst, skew)


def over_unpacked(scene, tol=1e-4):
    """4.6: NOTHING unpacks that did not have to.

    `instancing_split` counts what stayed packed and `deformed_flag_mismatch`
    proves the flag agrees with the prim type - but both of them are happy
    with a build that unpacks every piece and deforms none of them, which is
    geometrically perfect and is the exact defect 4.6 exists to prevent. This
    is the missing half: an unpacked piece that IS an affine image of its
    module was unpacked for nothing. Sliced and mitered pieces are exempt by
    construction (their geometry differs from the module by the CUT), and so
    is a replaced one (D58 - it is hero geometry, not the module at all).

    D65: A SHEAR IS A REAL DEFORMATION HERE, even though a packed prim's 4x4
    could carry one. `vertical` on a uniform slope is exactly a shear - the
    piece rises with the span while its verticals stay vertical - and 10 of
    10 pieces on the conformed ramp fit an affine to float noise. They are
    NOT counted as over-unpacked, because 4.6's own sentence is "transform x
    uniform-or-axis scale" and because a USD PointInstancer stores an
    orientation and a scale and cannot express a shear at all - so packing
    them would trade a memory win for a substrate that citygen 7 has not
    chosen yet. The count rides in the detail so the size of that prize stays
    visible.
    """
    bad, worst_ok, sheared = [], 0.0, 0
    for eid, rec in scene.by_id.items():
        if not rec["pc_deformed"]:
            continue
        placement = scene.plan_by_id.get(eid)
        if placement is None or placement.cuts or placement.slice_t is not None:
            continue
        fit = _affine_residual(rec)
        if fit is None:
            continue
        res, skew = fit
        if res <= tol and skew <= 1e-6:
            bad.append(eid)
        elif res > tol:
            worst_ok = max(worst_ok, res)
        else:
            sheared += 1
    return Result("over_unpacked", not bad, len(bad),
                  bad[0] if bad else
                  "worst real deform %.4f m, %d sheared (D65)"
                  % (worst_ok, sheared))


def curvature_budget(scene, place):
    """D75 - the deviation the packed pieces are SPENDING, in metres.

    `over_unpacked` is the other half of this: it catches a piece that
    unpacked for nothing. This catches the opposite mistake and records the
    number both of them are arguing about - for every bendable, uncut,
    un-anchored piece, how far its span leaves the chord it would be packed
    on. A PACKED piece may spend up to `bend_tol` (that is the budget); over
    that it is a piece the gate should have unpacked and did not.

    The value is [worst spent by a packed piece, worst over all pieces], so a
    gentle-arc case reads as a real number rather than as silence, and the
    tight-arc control reads a large second number with a small first one.
    """
    worst_packed, worst_all, over = 0.0, 0.0, []
    tol = scene.params.bend_tol
    for eid, rec in scene.by_id.items():
        placement = scene.plan_by_id.get(eid)
        module = scene.kit.by_name(rec["pc_module"])
        if placement is None or module is None or module.deform < 1:
            continue
        if placement.anchor is not None or placement.cuts                 or placement.slice_t is not None or rec.get("pc_replaced"):
            continue      # not placed on the path (4.3), cut, or hero (D58)
        track = scene.track_of.get(str(placement.curve_id))
        section = scene.section_of.get((str(placement.curve_id),
                                        placement.section_index))
        if track is None or section is None:
            continue
        s0 = track["remap"](section.s0 + placement.s0)
        s1 = track["remap"](section.s0 + placement.s1)
        d = place.span_deviation(track["path"], s0, s1)
        worst_all = max(worst_all, d)
        if not rec["pc_deformed"]:
            worst_packed = max(worst_packed, d)
            if d > tol:
                over.append(eid)
    if worst_all == 0.0 and not scene.by_id:
        return _skip("curvature_budget_m", "no pieces")
    return Result("curvature_budget_m", not over,
                  [_round(worst_packed), _round(worst_all)],
                  "" if not over else "%d packed over bend_tol %.4g, first %s"
                  % (len(over), tol, over[0]))


def modules_by_curve(scene, expected):
    """Which modules landed on which CURVE - {curve_id: [module, ...]}.

    Written for D94: a conditional keyed on `attr:road_width` is only proved
    by two curves in one stream that carry different values and get different
    modules. Asserting the pair rather than "a gate exists somewhere" is what
    keeps it from passing on a rule that ignores the attribute entirely.
    """
    got = {}
    for eid, rec in scene.by_id.items():
        placement = scene.plan_by_id.get(eid)
        if placement is None:
            continue
        got.setdefault(str(placement.curve_id), set()).add(rec["pc_module"])
    got = dict((k, sorted(v)) for k, v in got.items())
    want = dict((k, sorted(v)) for k, v in expected.items())
    return Result("modules_by_curve", got == want,
                  ["%s=%s" % (k, "+".join(got[k])) for k in sorted(got)],
                  "" if got == want else "expected %s" % want)


def deform_gate(scene, place):
    """D100 - [worst deviation left PACKED, pieces over budget, of those
    still packed]. The last number is the one that may not move off zero.

    `packed_true_dev_m` measures the same defect and goes SILENT the moment
    the gate starts working: with nothing packed there is nothing to report,
    so a case built to prove a budget term reads `skip` once the term is
    added and proves nothing ever again. This one is never silent, because
    the MIDDLE number says how many pieces the case actually put over the
    budget - a case that stopped exercising anything shows a 0 there and is
    visible as vacuous rather than as green.

    The assertion is the dangerous direction only: a piece may unpack for
    reasons the budget never measured (4.5's drape, D65's shear), and
    over-unpacking costs a deform, but a piece that stayed PACKED while its
    own geometry disagrees with its transform SHIPS. That is D87's elevation
    arc and D100's rolling cross-fall, and it is what this closes.
    """
    tol = scene.params.bend_tol
    worst, where, over, over_packed, seen = 0.0, "", 0, 0, 0
    for eid, rec in scene.by_id.items():
        placement = scene.plan_by_id.get(eid)
        module = scene.kit.by_name(rec["pc_module"])
        if placement is None or module is None or module.deform < 1:
            continue
        if placement.anchor is not None or placement.cuts                 or placement.slice_t is not None or rec.get("pc_replaced"):
            continue
        src = scene.sources.get(rec["pc_module"])
        track = scene.track_of.get(str(placement.curve_id))
        section = scene.section_of.get((str(placement.curve_id),
                                        placement.section_index))
        if src is None or track is None or section is None:
            continue
        proto = place._Proto(module, src)
        path, remap = track["path"], track["remap"]
        s0f, s1f = section.s0 + placement.s0, section.s0 + placement.s1
        s0r, s1r = remap(s0f), remap(s1f)
        scale = ((s1f - s0f) / proto.length) if proto.length > 1e-9 else 1.0
        zmode = rec["pc_zmode"] or module.zmode
        tilt = bool(module.tilts(scene.params) and zmode == "adaptive")
        normal_at = getattr(path, "normal", None) if tilt else None
        up_ref = place.UP if normal_at is None             else normal_at(0.5 * (s0r + s1r))
        xform = place._packed_transform(proto, path, s0r, s1r, zmode, up_ref)
        world, local = place._deform_positions(src, proto, path, s0f, scale,
                                               zmode, remap, tilt)
        truth = 0.0
        for i in range(0, len(local), 3):
            q = hou.Vector3(local[i], local[i + 1], local[i + 2]) * xform
            truth = max(truth, math.sqrt((q[0] - world[i]) ** 2
                                         + (q[1] - world[i + 1]) ** 2
                                         + (q[2] - world[i + 2]) ** 2))
        seen += 1
        packed = not rec["pc_deformed"]
        if truth > tol + 1e-9:
            over += 1
            if packed:
                over_packed += 1
        if packed and truth > worst:
            worst, where = truth, rec["pc_module"]
    if not seen:
        return _skip("deform_gate_m", "no bendable pieces on a path")
    return Result("deform_gate_m", over_packed == 0,
                  [_round(worst), over, over_packed],
                  "%d bendable, tol %.4f m%s"
                  % (seen, tol, (" - worst packed on %s" % where)
                     if where else ""))


def packed_true_deviation(scene, place):
    """D87 - the deviation a PACKED piece really carries, at its WORST POINT.

    `curvature_budget` asks `span_deviation` what a span is spending, which
    makes it blind to anything `span_deviation` itself cannot see - and for a
    whole cycle that was every point off the spine. This check never calls the
    budget: it BUILDS both answers for every packed piece (the packed 4x4
    applied to the module, and the positions `_deform_positions` would have
    produced for the same piece) and reports the largest distance between
    them. Over `bend_tol` means a piece stayed packed while its geometry was
    visibly wrong - the direction that ships, and the one that shipped: a
    1.2 m tall bendable rail on an R = 55 m elevation arc read 0.0091 m on the
    spine and 0.0327 m at its top corner, 30 of 30 pieces packed.

    Anchored, cut, sliced, rigid and replaced pieces are exempt for the same
    reasons `over_unpacked` exempts them - they are not the module on the
    path.
    """
    tol = scene.params.bend_tol
    worst, worst_id, over = 0.0, None, []
    for eid, rec in scene.by_id.items():
        if rec["pc_deformed"] or rec.get("pc_replaced"):
            continue
        placement = scene.plan_by_id.get(eid)
        module = scene.kit.by_name(rec["pc_module"])
        if placement is None or module is None or module.deform < 1:
            continue
        if placement.anchor is not None or placement.cuts                 or placement.slice_t is not None:
            continue
        src = scene.sources.get(rec["pc_module"])
        track = scene.track_of.get(str(placement.curve_id))
        section = scene.section_of.get((str(placement.curve_id),
                                        placement.section_index))
        if src is None or track is None or section is None:
            continue
        proto = place._Proto(module, src)
        path, remap = track["path"], track["remap"]
        s0f, s1f = section.s0 + placement.s0, section.s0 + placement.s1
        s0r, s1r = remap(s0f), remap(s1f)
        scale = ((s1f - s0f) / proto.length) if proto.length > 1e-9 else 1.0
        zmode = rec["pc_zmode"] or module.zmode
        tilt = bool(module.tilts(scene.params) and zmode == "adaptive")
        normal_at = getattr(path, "normal", None) if tilt else None
        up_ref = place.UP if normal_at is None             else normal_at(0.5 * (s0r + s1r))
        xform = place._packed_transform(proto, path, s0r, s1r, zmode, up_ref)
        world, local = place._deform_positions(src, proto, path, s0f, scale,
                                               zmode, remap, tilt)
        worst_here = 0.0
        for i in range(0, len(local), 3):
            q = hou.Vector3(local[i], local[i + 1], local[i + 2]) * xform
            worst_here = max(worst_here,
                             math.sqrt((q[0] - world[i]) ** 2
                                       + (q[1] - world[i + 1]) ** 2
                                       + (q[2] - world[i + 2]) ** 2))
        if worst_here > worst:
            worst, worst_id = worst_here, eid
        if worst_here > tol + 1e-9:
            over.append(eid)
    if worst_id is None:
        return _skip("packed_true_dev_m", "no packed bendable pieces")
    return Result("packed_true_dev_m", not over, _round(worst),
                  ("%d packed over bend_tol %.4g, first %s"
                   % (len(over), tol, over[0])) if over
                  else "worst on %s" % worst_id)


def style_round_trip(scene, via_payload, expect_warns=0):
    """PC-G4: the parm face's Style, expressed as a 3.3 payload and fed back
    through input 3, builds THE SAME GEOMETRY.

    Byte-identical is the assertion, not "similar": the payload carries the
    params too (D77), so anything the writer forgets - a fill mode, a seed, a
    corner offset - moves a position or an id and shows up here. It rides
    every case in the suite, which is what makes it an audit of the pipeline
    face rather than one demo.

    The warnings the reader produced are reported alongside: a clean style
    must round-trip SILENTLY, so a warning appearing here means the writer
    emitted something its own reader mistrusts. `expect_warns` is pinned
    exactly, never as a range, and the only cases that carry one are the two
    whose KIT is deliberately broken - the reader is right to say a module is
    missing there, and it is the kit that is malformed, not the style.
    """
    try:
        geo2, _report2, warns = via_payload(scene.case)
    except Exception as exc:
        return Result("style_round_trip", False, None,
                      "%s: %s" % (type(exc).__name__, str(exc)[:200]))
    a = dict((r["pc_elem_id"], r) for r in elements(geo2))
    moved = sorted(set(a) ^ set(scene.by_id))
    worst = 0.0
    for eid, rec in scene.by_id.items():
        other = a.get(eid)
        if other is None or len(other["world"]) != len(rec["world"]):
            continue
        for x, y in zip(rec["world"], other["world"]):
            worst = max(worst, abs(x - y))
    ok = not moved and worst == 0.0 and len(warns) == expect_warns
    return Result("style_round_trip", ok, [len(moved), _round(worst)],
                  ("%d reader warnings" % len(warns)) if ok else
                  "%d ids moved, %d reader warnings (expected %d): %s"
                  % (len(moved), len(warns), expect_warns,
                     (warns or [""])[0][:120]))


def style_payload_degrades(scene, payload_fn, build_fn):
    """3.3 + D78: a MALFORMED payload warns, degrades, and still builds.

    Six rules, one distinct fault each (`cases.MALFORMED_RULES`). The value is
    [rules kept, warnings, elements built] and every one of the three is
    asserted, because each of them alone can pass while the contract is
    broken: keeping every rule means nothing was validated, warning about
    everything while building nothing is warn-AND-block, and building
    geometry with no warnings is the silent degrade this exists to forbid.

    Two of the six are dropped (an unknown slot and a missing one, D78's only
    drop) and four survive. Fourteen warnings: four on the junk meta dict (an
    unknown key, an unreadable `count`, an unknown `fill` value and an
    unreadable `version`) and ten on the rules themselves.
    """
    try:
        geo, warns = build_fn(scene.case, payload_fn())
    except Exception as exc:
        return Result("style_payload_degrades", False, None,
                      "%s: %s" % (type(exc).__name__, str(exc)[:200]))
    if geo is None:
        return Result("style_payload_degrades", False, [0, len(warns), 0],
                      "the whole payload was rejected")
    built = len(elements(geo))
    got = [4, len(warns), built]
    ok = got[1] == 14 and built > 0
    return Result("style_payload_degrades", ok, got,
                  "" if ok else "expected 14 warnings and a non-empty build")


def override_round_trip(scene, plain_rebuild, expected=None):
    """Swap and replace both work WITHOUT touching the style (3.4), and
    neither of them moves an id.

    The control is the SAME case cooked with the override input unwired, so
    the comparison is against the run the artist would have had - not against
    a second opinion of the same override. Value is
    [swapped, replaced, ids that moved]; the third must be 0 on every case,
    which is what makes "round-trip" a measurement.
    """
    if not scene.case.get("overrides"):
        return _skip("override_round_trip", "no overrides")
    try:
        geo2, report2 = plain_rebuild(scene.case)
    except Exception as exc:
        return Result("override_round_trip", False, None,
                      "%s: %s" % (type(exc).__name__, str(exc)[:120]))
    plain = dict((r["pc_elem_id"], r) for r in elements(geo2))
    moved = sorted(set(plain) ^ set(scene.by_id))
    swapped = replaced = 0
    for eid, rec in scene.by_id.items():
        base = plain.get(eid)
        if base is None:
            continue
        if base["pc_module"] != rec["pc_module"] \
                or base["pc_variant"] != rec["pc_variant"]:
            swapped += 1
        if rec.get("pc_replaced"):
            replaced += 1
    got = [swapped, replaced, len(moved)]
    # ⚠️ THE COUNTS ARE ASSERTED, not merely recorded, and that is because a
    # mutation survived without it: making the swap a no-op left every check
    # green - `module_fidelity_m` compares the geometry against whatever
    # `pc_module` SAYS, so a swap that changes neither still agrees with
    # itself.
    ok = (not moved) and (expected is None or got == list(expected))
    return Result("override_round_trip", ok, got,
                  moved[0] if moved else
                  ("" if expected is None else "expected %s" % (expected,)))


def replaced_geometry(scene, elem_id=None, expected=None, tol=2e-3):
    """The hero actually ARRIVED: the world bbox of the replaced element.

    Read off the geometry, because `pc_replaced = 1` on a prim that still
    holds the old module would pass every other check on this list. The hero
    is a size no kit module has, so the number identifies it.
    """
    replaced = [(eid, rec) for eid, rec in scene.by_id.items()
                if rec.get("pc_replaced")]
    if not replaced:
        return _skip("replaced_bbox_m", "no replaced elements")
    if elem_id is not None:
        replaced = [(e, r) for e, r in replaced if e == elem_id] or replaced
    eid, rec = replaced[0]
    w = rec["world"]
    size = [max(w[k::3]) - min(w[k::3]) for k in range(3)]
    ok = expected is None or all(abs(size[k] - expected[k]) <= tol
                                 for k in range(3))
    return Result("replaced_bbox_m", ok, [_round(v, 5) for v in size],
                  eid if expected is None else "expected %s" % (expected,))


def elem_ids_survive_upstream(scene, rebuild_with_extra):
    """3.4: `pc_elem_id` is a STRUCTURAL ADDRESS, never cook order.

    ⚠️ `determinism` cannot see this and never could: it cooks the SAME inputs
    twice, and an id derived from cook order survives that perfectly. This
    merges an UNRELATED third curve into input 1 - the ordinary thing an
    artist does upstream - and requires every id of the original curves to be
    untouched. It is also what caught D64: one prim carrying `pc_curve_id`
    gives EVERY prim the attribute, blank, and reading a blank as an id
    collapsed two curves onto one address.
    """
    try:
        _geo2, report2 = rebuild_with_extra(scene.case)
    except Exception as exc:
        return Result("elem_ids_upstream", False, None,
                      "%s: %s" % (type(exc).__name__, str(exc)[:120]))
    before = set(p.elem_id for p in scene.plan)
    after = set(p.elem_id for p in report2["plan"])
    lost = sorted(before - after)
    return Result("elem_ids_upstream", not lost, len(lost),
                  lost[0] if lost else "%d ids, %d after the merge"
                  % (len(before), len(after)))


def cap_dressing(scene):
    """D59 - every slice cap carries box UVs and a cap material tag.

    The UV is MEASURED against the module's own local box projection (D20 puts
    the cap plane perpendicular to local +X, so the projection is local z, y),
    not merely found present: an attribute full of zeroes is present too, and
    the real failure mode for a MITER cap - which lives in world space and
    recovers its local coordinates through `pc_local` - is a uv taken off
    world P, which on a corner post at x = 12 is off by 12.

    ⚠️ AND IT IS COMPARED TO THE PROJECTION, NOT TO THE FACE'S OWN METRIC
    SIZE. A box projection of an OBLIQUE face compresses it, which is what box
    mapping is: the mitered corner post's cut face measures 0.2263 m across in
    world and 0.16 m in the projection, and demanding they agree failed 11
    cases while measuring nothing but the 45 degrees.
    """
    geo = scene.geo
    if geo.findPrimAttrib("pc_cap") is None:
        return _skip("cap_uv_m", "no caps")
    caps = [prim for prim in geo.prims()
            if prim.type() != hou.primType.PackedGeometry
            and int(prim.attribValue("pc_cap")) == 1]
    if not caps:
        return _skip("cap_uv_m", "no caps")
    if geo.findVertexAttrib("uv") is None             or geo.findPrimAttrib("pc_cap_material") is None:
        return Result("cap_uv_m", False, None, "no uv / pc_cap_material")
    worst, untagged, flat = 0.0, 0, 0
    for prim in caps:
        if not prim.attribValue("pc_cap_material"):
            untagged += 1
        spread = 0.0
        for vtx in prim.vertices():
            pt = vtx.point()
            try:
                local = pt.attribValue("pc_local")
            except hou.OperationFailed:
                local = pt.position()
            uv = vtx.attribValue("uv")
            worst = max(worst, abs(uv[0] - local[2]), abs(uv[1] - local[1]))
            spread = max(spread, abs(uv[0]) + abs(uv[1]))
        if spread <= 1e-9:
            flat += 1                      # a cap whose uv is all zeroes
    ok = untagged == 0 and flat == 0 and worst <= 1e-5
    return Result("cap_uv_m", ok, _round(worst, 8),
                  "%d caps, %d untagged, %d degenerate"
                  % (len(caps), untagged, flat))


def warning_summary(scene):
    """D61: the collated detail array agrees with the per-element attributes.

    Two records of the same fact drift; this is the assertion that they have
    not. The value is the summary itself, so the baseline carries it.
    """
    geo = scene.geo
    if geo.findGlobalAttrib("pc_warnings") is None:
        return Result("warn_summary", False, None, "pc_warnings not written")
    rows = list(geo.attribValue("pc_warnings"))
    counts = {}
    for name in scene.report["warn_names"]:
        n = sum(1 for w in scene.warns.values() if w.get(name))
        if n:
            counts[name] = n
    want = ["%s:%d" % (k, counts[k]) for k in sorted(counts)]
    return Result("warn_summary", rows == want, rows,
                  "" if rows == want else "elements say %s" % want)


# --- 4.5 SURFACE CONFORM -----------------------------------------------------
#
# Every number here is a distance to the SURFACE, cast with the same axis the
# builder used, so a conform that only moved the plan (and not the geometry)
# cannot pass. The three Z-modes are read as a triple exactly like the hill:
#
#   conform_contact_m  the piece TOUCHES the surface - worst over pieces of
#                      the smallest distance any of its own stations has to
#                      the surface. Every mode owes this one, including
#                      `stepped`, which touches at its start and rises off it
#                      by design.
#   conform_drape_m    the piece FOLLOWS the surface - worst over EVERY
#                      station of an adaptive or vertical piece. This is the
#                      half `stepped` does not owe, and the half that
#                      separates "projected the plan" from "deformed the
#                      geometry": a rigid chord across a ridge keeps its two
#                      ends on the ground and fails here by the sagitta.
#   camber_deg         the angle between the piece's own up and the surface
#                      normal under it. With `conform_tilt` on it is 0; with
#                      it off it is the surface's own cross-fall, and BOTH are
#                      asserted, because a camber that is always on is as
#                      wrong as one that never fires.

def _surface_of(scene):
    from polyfactory.polychain import conform as _conform
    geo = scene.case.get("surface")
    if geo is None:
        return None
    surf = _conform.Surface(geo, scene.params.conform_axis)
    return surf if surf.active else None


def _axis_stations(rec):
    """[(local x, world axis point)] for every station of one element."""
    frame = _element_frame(rec)
    out = []
    for x in sorted(set(round(v, 6) for v in rec["local"][0::3])):
        p = _axis_of(_face(rec, x), frame)
        if p is not None:
            out.append((x, p))
    return out


def _surface_gap(surf, p):
    """Signed distance from `p` to the surface along the conform axis.

    Negative = the point is BELOW the surface for the default -Y axis (the
    ray has to travel further than it does to reach `p`), positive = above.
    A miss returns None rather than 0: "no surface here" and "on the surface"
    are different answers and only one of them is a pass.
    """
    hit, _n, ok = surf.drop(p)
    if not ok:
        return None
    d = (hit[0] - p[0], hit[1] - p[1], hit[2] - p[2])
    a = surf.axis
    return -(d[0] * a[0] + d[1] * a[1] + d[2] * a[2])


def conform_contact(scene, tol=2e-3):
    surf = _surface_of(scene)
    if surf is None:
        return _skip("conform_contact_m", "no surface")
    worst, where, seen = 0.0, "", 0
    for eid, rec in scene.by_id.items():
        # a piece over a HOLE is meant to be off the surface, and it says so
        # on itself - D53. Scoring it here would make the warning a failure.
        if scene.warns.get(eid, {}).get("pc_warn_conform_miss"):
            continue
        gaps = [g for _x, p in _axis_stations(rec)
                for g in (_surface_gap(surf, p),) if g is not None]
        if not gaps:
            continue
        seen += 1
        # ⚠️ A PIECE THAT STRADDLES THE SURFACE IS IN CONTACT WITH IT, and
        # reading the gaps unsigned said otherwise. A rigid corner post sits
        # FLAT at its assembly's own datum (D72), so on a 25 % grade its two
        # ends are 0.02 m under and 0.02 m over the terrain and it passes
        # through the surface between them - which is contact, and is the
        # same "a stepped piece sits, it does not drape" that
        # `stepped_riser_m` measures. Unsigned, that reads as a 0.02 m float.
        best = 0.0 if (min(gaps) <= 0.0 <= max(gaps)) \
            else min(abs(g) for g in gaps)
        if best > worst:
            worst, where = best, "%s (%s)" % (rec["pc_module"],
                                              rec["pc_zmode"])
    if not seen:
        return _skip("conform_contact_m", "no pieces over the surface")
    return Result("conform_contact_m", worst <= tol, _round(worst, 6), where)


def conform_drape(scene, tol=2e-3):
    surf = _surface_of(scene)
    if surf is None:
        return _skip("conform_drape_m", "no surface")
    worst, where, seen = 0.0, "", 0
    for eid, rec in scene.by_id.items():
        if rec["pc_zmode"] == "stepped":
            continue                       # 4.5: stepped SITS, it does not drape
        if scene.warns.get(eid, {}).get("pc_warn_conform_miss"):
            continue
        placement = scene.plan_by_id.get(eid)
        if placement is not None and placement.anchor is not None:
            continue                       # a corner piece is rigid on its leg
        module = scene.kit.by_name(rec["pc_module"])
        if module is None or module.deform < 1:
            continue                       # a rigid piece cannot follow, D27
        for _x, p in _axis_stations(rec):
            g = _surface_gap(surf, p)
            if g is None:
                continue
            seen += 1
            if abs(g) > worst:
                worst, where = abs(g), "%s (%s)" % (rec["pc_module"],
                                                    rec["pc_zmode"])
    if not seen:
        return _skip("conform_drape_m", "no deformable pieces on the surface")
    return Result("conform_drape_m", worst <= tol, _round(worst, 6), where)


def corner_mate_axis(scene, tol=1e-4):
    """The two cut faces of ONE mitered corner sit at ONE elevation (D72).

    ⚠️ THIS IS THE HALF `corner_face_mate_m` CANNOT SEE, and the reason it
    cannot is written into it: a `stepped` piece at a pitched corner steps by
    design, so that check drops to a plan-only metric the moment either side
    is stepped - and a rigid corner post IS stepped (D27). So the whole
    conformed-corner failure mode was structurally invisible: 4.5 dropped each
    half of the assembly on its OWN anchor, the two anchors sit at different
    places on their legs, and on the suite's own 25 % ramp the two faces came
    out y[2.98..4.28] against y[3.00..4.30] while every corner check passed.
    With a 1.2 m corner module the same construction shelves them 0.28 m
    apart.

    A corner assembly is ONE rigid object cut on the bisector, whatever its
    Z-mode and whatever the ground does, so the two faces' extents along the
    conform axis must agree exactly. That holds off a surface too, which is
    why this rides every case rather than only the conformed ones.
    """
    groups = _corner_caps(scene)
    if not groups:
        return _skip("corner_mate_axis_m", "no mitered corners")
    axis = (0.0, 1.0, 0.0)
    surf = _surface_of(scene)
    if surf is not None:
        axis = tuple(-c for c in surf.axis)
    worst, where, seen = 0.0, "", 0
    for bevel, sides in groups:
        proj = {}
        for side in ("in", "out"):
            vals = [_dot3(pt, axis) for pt, _rec in sides[side]]
            proj[side] = (min(vals), max(vals)) if vals else None
        if proj["in"] is None or proj["out"] is None:
            continue
        seen += 1
        d = max(abs(proj["in"][0] - proj["out"][0]),
                abs(proj["in"][1] - proj["out"][1]))
        if d > worst:
            worst, where = d, "turn %.1f deg" % bevel.turn
    if not seen:
        return _skip("corner_mate_axis_m", "no paired cut faces")
    return Result("corner_mate_axis_m", worst <= tol, _round(worst, 6), where)


def duplicate_curve_id_warns(scene, dup_build):
    """D74 - two curves with one authored id COLLIDE, and say so.

    `pc_elem_id` is "collision-free by construction" (D1) only while the curve
    half of the address is unique, and nothing upstream enforces that: a
    copy-pasted street prim hands two curves the same `pc_curve_id`. Measured
    before the warning existed: 4 prims, 2 distinct ids, each stamped twice,
    `warn_counts` empty - so an id-keyed override hit both curves and any
    by-id map downstream dropped half the run, silently.

    The ids are NOT renamed (that would move an address a style or an override
    may already name), so what is asserted is that the collision is visible.
    The collision size rides along as the recorded value: a build that stopped
    colliding would move it, and that is worth seeing too.
    """
    try:
        geo, report = dup_build(scene.case)
    except Exception as exc:                                  # pragma: no cover
        return Result("duplicate_curve_id_warn", False, None,
                      "%s: %s" % (type(exc).__name__, str(exc)[:120]))
    counts = {}
    for prim in geo.prims():
        eid = prim.attribValue("pc_elem_id")
        counts[eid] = counts.get(eid, 0) + 1
    collided = sum(1 for n in counts.values() if n > 1)
    warned = int(report["warn_counts"].get("pc_warn_curve_id_dup", 0))
    ok = collided > 0 and warned >= len(geo.prims())
    return Result("duplicate_curve_id_warn", ok, [collided, warned],
                  "%d ids on 2+ prims, %d elements warned" % (collided, warned))


def zmode_stamp(scene, expected):
    """Every element carries `expected` in `pc_zmode` (3.2, D6, D73).

    A swap re-points the module, so the Z-mode the plan derived from the OLD
    module has to be re-derived too: a panel -> post swap under an empty style
    zmode used to stamp the panel's `vertical` on every post and build it that
    way, which on a hillside is a rail that banks instead of sitting flat.
    """
    got = sorted(set(rec["pc_zmode"] for rec in scene.by_id.values()))
    return Result("zmode_stamp", got == [expected], got,
                  "expected %r" % expected)


def conform_camber(scene, expected=None, tol=0.05):
    """D55 - the angle between a piece's own up and the surface normal.

    The piece's up comes from `_element_frame`, i.e. off the built geometry,
    and the normal from a fresh ray cast - so nothing here reads the builder's
    own opinion of either.
    """
    surf = _surface_of(scene)
    if surf is None:
        return _skip("camber_deg", "no surface")
    worst, seen, where = 0.0, 0, ""
    for _eid, rec in scene.by_id.items():
        up, _across = _element_frame(rec)
        stations = _axis_stations(rec)
        if up is None or not stations:
            continue
        mid = stations[len(stations) // 2][1]
        _hit, nrm, ok = surf.drop(mid)
        if not ok:
            continue
        n_up = math.sqrt(_dot3(up, up))
        if n_up < 1e-9:
            continue
        cos = max(-1.0, min(1.0, _dot3(up, nrm) / n_up))
        ang = math.degrees(math.acos(cos))
        seen += 1
        if ang > worst:
            worst, where = ang, rec["pc_module"]
    if not seen:
        return _skip("camber_deg", "no pieces on the surface")
    ok = expected is None or abs(worst - expected) <= tol
    return Result("camber_deg", ok, _round(worst, 4),
                  where if expected is None
                  else "%s, expected %.4f" % (where, expected))


def conform_misses(scene, expected=None):
    """How many elements kept the spline elevation because the ray found
    nothing (D53). Recorded on every conformed case, asserted where the case
    exists to produce them."""
    if scene.case.get("surface") is None:
        return _skip("conform_misses", "no surface")
    n = sum(1 for w in scene.warns.values() if w.get("pc_warn_conform_miss"))
    ok = expected is None or n == expected
    return Result("conform_misses", ok, n,
                  "" if expected is None else "expected %s" % expected)


# --- 4.3 CORNERS ------------------------------------------------------------
#
# PC-G1's acceptance is "no gaps/overlaps at any corner in either corner mode",
# so every number below is a distance in world space measured on built
# geometry, never a restatement of what the solver decided.
#
# In BEND mode there is nothing here to measure and that IS the result: the
# corner does not break the run (D36), so the corner's closure is `max_gap_m`
# and `axis_on_curve_m` on a chain that never stopped. In MITER mode the joint
# is two clipped faces, and these check that they are the SAME face:
#
#   corner_plane_dev_m  every point of a mitered piece's cut face lies on that
#                       piece's own bisector plane. A clip on the wrong side,
#                       or a plane built from the start tangent instead of the
#                       bisector, moves this immediately.
#   corner_seam_m       the separation between the two cut faces along the
#                       plane normal - 0 is "no hole and no overlap", and with
#                       a corner offset it is the gap the artist asked for.
#   corner_face_mate_m  the two faces, slid together along the normal, are the
#                       SAME polygon: worst nearest-point distance both ways.
#                       Coplanar faces that do not overlap would still pass the
#                       first two and still leave the corner open.
#   corner_outside_m    the mitered piece's OUTSIDE face keeps the module's
#                       full length - iToo's own wording for Bevel Corner, and
#                       the acceptance number for the single-module case.
#   corner_symmetry_m   |leg reach in - leg reach out| of the corner assembly:
#                       0 for an ODD compose count, one module length for an
#                       EVEN one (D38). The odd/even rule, as a number.

def _sub3(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _dot3(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _caps_by_element(geo):
    """{elem_id: [world points of its pc_cap prims]} - the cut faces."""
    if geo.findPrimAttrib("pc_cap") is None:
        return {}
    out = {}
    for prim in geo.prims():
        if prim.type() == hou.primType.PackedGeometry:
            continue
        try:
            if int(prim.attribValue("pc_cap")) != 1:
                continue
            eid = prim.attribValue("pc_elem_id")
        except (hou.OperationFailed, TypeError, ValueError):
            continue
        pts = out.setdefault(eid, [])
        for vtx in prim.vertices():
            p = vtx.point().position()
            pts.append((p[0], p[1], p[2]))
    return out


def _bevels(scene):
    out = []
    for track in scene.tracks:
        out.extend(track.get("bevels") or ())
    return out


def _centroid(rec):
    w = rec["world"]
    n = len(w) // 3
    if not n:
        return None
    return tuple(sum(w[k::3]) / n for k in range(3))


def _assembly_recs(scene):
    """[(eid, rec)] for every piece 4.3 ANCHORED on a leg.

    The corner slot, plus D40's displacement boundary piece - which is a
    `default` piece made of the default module but laid out by exactly the
    same assembly machinery, so the corner measurements apply to it verbatim.
    """
    out = []
    for eid, rec in scene.by_id.items():
        placement = scene.plan_by_id.get(eid)
        if rec["pc_slot"] == "corner" or (placement is not None
                                          and placement.anchor is not None):
            out.append((eid, rec))
    return out


def _corner_sides(scene):
    """[(bevel, {"in": [(eid, rec)], "out": [...]})] over every mitered corner.

    An element is assigned to the NEAREST vertex and then to a side by the sign
    of its centroid against the bisector plane - both read off geometry, so a
    corner piece built on the wrong leg cannot be quietly filed under the right
    one.
    """
    bevels = [b for b in _bevels(scene) if b.mode == "miter"]
    if not bevels:
        return []
    groups = [(b, {"in": [], "out": []}) for b in bevels]
    for eid, rec in scene.by_id.items():
        placement = scene.plan_by_id.get(eid)
        if placement is None or not placement.cuts:
            continue
        cen = _centroid(rec)
        if cen is None:
            continue
        best = min(groups, key=lambda g: _dist(cen, g[0].v))
        bevel = best[0]
        side = "out" if _dot3(_sub3(cen, bevel.v), bevel.n) > 0.0 else "in"
        best[1][side].append((eid, rec))
    return groups


def _corner_caps(scene):
    """[(bevel, {"in": [world pts], "out": [...]})] - every CUT-FACE POINT
    filed under the corner that cut it.

    Per POINT, not per element: once a default piece may be cut at BOTH of its
    ends (which is what happens as soon as a leg is shorter than twice the
    miter overhang - a 1.5 m equilateral triangle does it), filing the whole
    element under its nearest vertex measured half its cap points against the
    wrong corner's plane and scored a 0.73 m "plane deviation" on a piece that
    is exactly on both of its own planes. The SIDE still comes from the
    element's centroid, read against each bevel separately, so one piece is
    legitimately "out" of one corner and "in" of the next.
    """
    bevels = [b for b in _bevels(scene) if b.mode == "miter"]
    if not bevels:
        return []
    groups = dict((id(b), (b, {"in": [], "out": []})) for b in bevels)
    caps = _caps_by_element(scene.geo)
    for eid, pts in caps.items():
        placement = scene.plan_by_id.get(eid)
        if placement is None or not placement.cuts:
            continue
        rec = scene.by_id.get(eid)
        cen = _centroid(rec) if rec is not None else None
        # ⚠️ THE CANDIDATES ARE THE PIECE'S OWN CUT PLANES, not "the nearest
        # vertex". On a figure narrower than its own fence - 12 m by 0.12 m -
        # two vertices sit 0.12 m apart and a cap cut at one of them is nearer
        # the other, which scored a 0.028 m "plane deviation" on a face that
        # is exactly on the plane it was cut with.
        mine = [groups[id(b)] for b in bevels
                if any(cut[0] is b.plane_in()[0] or _dist(cut[0], b.v) < 1e-9
                       for cut in placement.cuts)]
        if not mine:
            mine = list(groups.values())
        for pt in pts:
            group = min(mine, key=lambda g: abs(_dot3(
                _sub3(pt, g[0].plane_in()[0]), g[0].n)))
            bevel = group[0]
            ref = cen if cen is not None else pt
            side = "out" if _dot3(_sub3(ref, bevel.v), bevel.n) > 0.0 else "in"
            group[1][side].append((pt, rec))
    return list(groups.values())


def corner_plane_dev(scene):
    groups = _corner_caps(scene)
    if not groups:
        return _skip("corner_plane_dev_m", "no mitered corners")
    worst, where, seen = 0.0, "", 0
    for bevel, sides in groups:
        for side in ("in", "out"):
            origin = (bevel.plane_in() if side == "in"
                      else bevel.plane_out())[0]
            for pt, rec in sides[side]:
                seen += 1
                d = abs(_dot3(_sub3(pt, origin), bevel.n))
                if d > worst:
                    worst, where = d, "%s %s" % (
                        (rec or {}).get("pc_module", "?"), side)
    if not seen:
        return _skip("corner_plane_dev_m", "no cut faces")
    return Result("corner_plane_dev_m", worst <= TOL_M, _round(worst), where)


def corner_seam(scene, expected=None, tol=2e-3):
    """Separation of the two cut faces along the plane normal, in metres.

    0 means the corner is closed: no hole, no overlap. `expected` is the gap
    the corner offset asked for, derived from the parm and the turn and NOT
    from the solver, so a seam that drifts with the offset shows up as a
    failure rather than as the builder agreeing with itself.
    """
    groups = _corner_caps(scene)
    if not groups:
        return _skip("corner_seam_m", "no mitered corners")
    worst, where, seen = 0.0, "", 0
    for bevel, sides in groups:
        proj = {}
        for side in ("in", "out"):
            vals = [_dot3(_sub3(pt, bevel.v), bevel.n)
                    for pt, _rec in sides[side]]
            if vals:
                proj[side] = sum(vals) / len(vals)
        if len(proj) < 2:
            continue
        seen += 1
        gap = proj["out"] - proj["in"]
        if expected is not None:
            gap -= expected
        if abs(gap) > abs(worst):
            worst, where = gap, "turn %.1f deg" % bevel.turn
    if not seen:
        return _skip("corner_seam_m", "no paired cut faces")
    return Result("corner_seam_m", abs(worst) <= tol, _round(worst, 6),
                  where + ("" if expected is None
                           else " (residual vs %.4f)" % expected))


def corner_face_mate(scene, expected=0.0, tol=TOL_M):
    """The two cut faces are the SAME polygon once slid together.

    Coplanar faces that do not overlap - two pieces mitered on one plane but
    displaced sideways - pass `corner_plane_dev_m` and `corner_seam_m` and
    still leave the corner open, so the faces are compared point for point.

    ⚠️ AND IT IS NOT ALWAYS SUPPOSED TO BE ZERO. The `reset` displacement
    policy leaves each default piece "in its default position, simply sliced
    at the corner vertex", so the two cut faces are MIRROR images rather than
    the same face and a notch of e*sqrt(2) is left on the outside of the
    corner - measured 0.0424 m for the starter panel at 90 degrees. That is
    RailClone's documented Reset, so the number is compared against the notch
    the policy asks for, and it is `extend` that has to come back 0.
    """
    groups = _corner_caps(scene)
    if not groups:
        return _skip("corner_face_mate_m", "no mitered corners")
    worst, where, seen = 0.0, "", 0
    for bevel, sides in groups:
        pts = dict((side, [pt for pt, _rec in sides[side]])
                   for side in ("in", "out"))
        # Same reason `corner_abut_m` and `max_gap_m` do it: a `stepped` piece
        # is flat at its own start elevation, so two of them meeting at a
        # PITCHED corner step vertically by design (4.4's deferred
        # flatten-under). The joint is judged in plan there.
        stepped = any(rec is not None and rec["pc_zmode"] == "stepped"
                      for side in ("in", "out") for _pt, rec in sides[side])
        metric = _dist_xz if stepped else _dist
        if not pts["in"] or not pts["out"]:
            continue
        seen += 1

        def flat(p):
            d = _dot3(_sub3(p, bevel.v), bevel.n)
            return tuple(p[k] - bevel.n[k] * d for k in range(3))

        a = [flat(p) for p in pts["in"]]
        b = [flat(p) for p in pts["out"]]
        for src, dst in ((a, b), (b, a)):
            for p in src:
                d = min(metric(p, q) for q in dst)
                if d > worst:
                    worst, where = d, "turn %.1f deg" % bevel.turn
    if not seen:
        return _skip("corner_face_mate_m", "no paired cut faces")
    return Result("corner_face_mate_m", abs(worst - expected) <= tol,
                  _round(worst), where + ("" if not expected
                                          else " (expected %.4f)" % expected))


def corner_outside_length(scene, expected=None, tol=2e-3):
    """iToo's own acceptance for Bevel Corner: the segment is "sliced to
    maintain its full length on the OUTSIDE of the corner".

    Measured on the mitered piece's own outside half in module-local x - a
    corner piece is placed at scale 1, so local x IS metres - which means the
    number never passes through the solver's idea of where the plane went.
    """
    groups = _corner_sides(scene)
    if not groups:
        return _skip("corner_outside_m", "no mitered corners")
    worst, where, got_v, seen = 0.0, "", None, 0
    for bevel, sides in groups:
        for side in ("in", "out"):
            for eid, rec in sides[side]:
                if rec["pc_slot"] != "corner":
                    continue
                module = scene.kit.by_name(rec["pc_module"])
                if module is None:
                    continue
                loc, wrl = rec["local"], rec["world"]
                axis = bevel.tin if side == "in" else bevel.tout
                # WORLD metres, not local x: D44 may have squeezed the module
                # onto a short leg, and local x is scale-invariant - it read a
                # clean 1.200 m on a corner block the builder had scaled to
                # 0.776 m, so the check agreed with a squeeze it never saw.
                outer = [_dot3(_sub3((wrl[i], wrl[i + 1], wrl[i + 2]),
                                     bevel.v), axis)
                         for i in range(0, len(loc), 3)
                         if loc[i + 2] * -bevel.side > 1e-6]
                if len(outer) < 2:
                    continue
                seen += 1
                got = max(outer) - min(outer)
                # The piece's OWN length, not the module's nominal one: D44
                # may have squeezed this copy and not its mate (a 12 m leg
                # meeting a 1.5 m one squeezes on the short side only), and
                # comparing both against the nominal length asserted that the
                # squeeze had not happened. `corner_reach_m` is what asserts
                # the squeeze factor itself.
                planned = module.length * (scene.plan_by_id[eid].scale
                                           if eid in scene.plan_by_id else 1.0)
                want = expected if expected is not None else planned
                if abs(got - want) > worst:
                    worst = abs(got - want)
                    where = "%s %s" % (rec["pc_module"], side)
                    got_v = got
                elif got_v is None:
                    got_v = got
    if not seen:
        return _skip("corner_outside_m", "no corner-slot pieces")
    return Result("corner_outside_m", worst <= tol, _round(got_v or 0.0, 6),
                  "%s, error %.2e m" % (where or "all exact", worst))


def corner_symmetry(scene, expected=None, tol=2e-3):
    """D38's odd/even rule as a distance: how far the corner assembly reaches
    down each leg, measured on the built pieces themselves."""
    bevels = [b for b in _bevels(scene) if getattr(b, "assembly", None)
              and b.assembly.pieces]
    if not bevels:
        return _skip("corner_symmetry_m", "no corner assemblies")
    worst, where = None, ""
    corner_recs = _assembly_recs(scene)
    for bevel in bevels:
        reach = {"in": 0.0, "out": 0.0}
        seen = False
        for eid, rec in corner_recs:
            cen = _centroid(rec)
            if cen is None:
                continue
            near = min(bevels, key=lambda b: _dist(cen, b.v))
            if near is not bevel:
                continue
            side = "out" if _dot3(_sub3(cen, bevel.v), bevel.n) > 0.0 else "in"
            axis = bevel.tout if side == "out" else bevel.tin
            sign = 1.0 if side == "out" else -1.0
            w = rec["world"]
            for i in range(0, len(w), 3):
                t = sign * _dot3(_sub3((w[i], w[i + 1], w[i + 2]), bevel.v),
                                 axis)
                if t > reach[side]:
                    reach[side] = t
            seen = True
        if not seen:
            continue
        d = abs(reach["in"] - reach["out"])
        if worst is None or d > worst:
            worst, where = d, "in %.4f out %.4f" % (reach["in"], reach["out"])
    if worst is None:
        return _skip("corner_symmetry_m", "no corner geometry")
    ok = True if expected is None else abs(worst - expected) <= tol
    return Result("corner_symmetry_m", ok, _round(worst, 6),
                  where + ("" if expected is None
                           else " (expected %.4f)" % expected))


def _reach_of(scene):
    """{(bevel, side): metres the assembly reaches back down that leg}.

    Read off the built points, so it is the geometry's answer and not the
    solver's: `t` measured from the vertex OUTWARD along the leg.
    """
    bevels = [b for b in _bevels(scene) if getattr(b, "assembly", None)
              and b.assembly.pieces]
    out = {}
    recs = _assembly_recs(scene)
    for bevel in bevels:
        for eid, rec in recs:
            cen = _centroid(rec)
            if cen is None:
                continue
            if min(bevels, key=lambda b: _dist(cen, b.v)) is not bevel:
                continue
            side = "out" if _dot3(_sub3(cen, bevel.v), bevel.n) > 0.0 else "in"
            axis = bevel.tout if side == "out" else bevel.tin
            sign = 1.0 if side == "out" else -1.0
            w = rec["world"]
            for i in range(0, len(w), 3):
                t = sign * _dot3(_sub3((w[i], w[i + 1], w[i + 2]), bevel.v),
                                 axis)
                # ⚠️ KEYED ON THE VERTEX, NOT ON `id(bevel)` (D67). `id()` is a
                # MEMORY ADDRESS: `corner_reach`'s no-expectation branch
                # reports `sorted(reaches.items())[0]`, so which corner of a
                # four-corner figure got recorded depended on where Python
                # happened to allocate its Bevels. AP_narrow_rect flapped
                # between 0.06 m and 0.08 m across runs of IDENTICAL code -
                # a baseline value that moves on its own is worse than no
                # baseline value.
                key = (tuple(round(c, 6) for c in bevel.v), side)
                if t > out.get(key, (0.0, bevel, side))[0]:
                    out[key] = (t, bevel, side)
    return out


def corner_reach(scene, expected=None, tol=2e-3):
    """4.3 item C and item D as ONE distance: how far the corner assembly
    reaches back down its leg, which is `L - e + o` for a corner module and
    `L - d + o` for D40's boundary piece.

    This is what the corner OFFSET actually moves now that D39 no longer moves
    the cut plane (moving it opened a hole at +25 % and doubled the geometry at
    -25 %), and it is also what makes `symmetric` symmetric: a panel centred on
    the vertex reaches exactly `L/2`, where the first implementation - which
    extended the fill SPAN instead - centred it at 12.07 m of a 12.00 m leg
    and, under `tile`, planted a whole extra sliced piece past the vertex.
    """
    reaches = _reach_of(scene)
    if not reaches:
        return _skip("corner_reach_m", "no corner assemblies")
    worst, got = 0.0, None
    for _key, (t, bevel, side) in sorted(reaches.items()):
        if got is None:
            got = t
        if expected is not None and abs(t - expected) > worst:
            worst, got = abs(t - expected), t
    ok = True if expected is None else worst <= tol
    return Result("corner_reach_m", ok, _round(got or 0.0, 6),
                  "" if expected is None
                  else "expected %.4f, error %.2e m" % (expected, worst))


def corner_breach(scene, tol=1e-4):
    """NO PIECE CROSSES A CORNER'S CUT PLANE UNCUT.

    ⚠️ THE INTERPENETRATION DETECTOR, and every corner check above it was
    blind to this. Two ways to reach it were measured on the built geometry:

      * the corner module SHORTER THAN ITS OWN MITER OVERHANG (`e >= L_c`,
        which is any turn past 126.87 degrees for the starter kit's 0.16 m
        post). The reserve went negative, the negative was handed to the fill
        as a negative trim, and the two legs' panels ran through the vertex
        UNCUT and into each other by 0.031 m - warning list empty.
      * a leg SHORTER THAN TWICE THE OVERHANG (a 1.5 m equilateral triangle:
        reserve 0.0215 m against a 0.03 m panel half-thickness), where the
        default piece stops short of the vertex and still reaches across the
        plane, so the two legs' square ends cross inside the corner post.

    IN BEND MODE THE SAME NUMBER IS NOT ZERO AND IS NOT A DEFECT (D36,
    extended). There is no cut plane there because nothing is cut: two
    square-ended pieces butt at the vertex, so each of them crosses the
    bisector by `half_width * cos(turn/2)` - 0.021213 m for the starter
    panel's 0.03 m half-width at 90 degrees. That is inherent to a butt
    joint; `corner_wedge_m2` measures the solid it leaves, `BUTT_BREACH_M` is
    the accepted limit, and miter is the fix.

    Both miter failures are invisible from outside the fence and invisible to
    `max_gap_m`, which walks one run at a time. This walks the plane instead: a piece is
    filed on the side its centroid is on, and every one of its points must
    stay there. Pieces further than a couple of module lengths from the vertex
    are out of scope - a bisector plane is infinite and a far leg may
    legitimately straddle it.
    """
    bevels = [b for b in _bevels(scene) if b.mode == "miter"]
    worst, where, seen = 0.0, "", 0
    # --- THE BEND BRANCH (cycle 3v's open finding, D36 extended). A bend
    # corner has no bevel to filter on, so this walked past every bend case
    # and reported SKIP while a butt joint was crossing the bisector by
    # 0.0212 m. The dissolved vertex carries the same plane a miter would have
    # cut on; what changes is that NOTHING cuts on it, which is exactly the
    # thing to measure. A SPANNED weld is not a joint (one bent piece) and is
    # counted, not scored.
    excess = 0.0
    for v, n, cos_half, pieces, spanned in _welds(scene):
        if spanned:
            continue
        for side, _eid, rec in pieces:
            sign = 1.0 if side == "in" else -1.0
            d = max(sign * _dot3(_sub3(q, v), n) for q in _pts_of(rec))
            seen += 1
            # ...AND WHAT IT IS ALLOWED TO BE, derived from the piece and the
            # turn rather than from the run: a square-ended piece of across
            # half-extent `h` butting at a turn `t` crosses the bisector by
            # exactly `h*sin(t/2)` - 0.021213 m for the starter panel at 90
            # degrees, 0.042426 m for the fatter post. Anything MORE is a
            # piece running past the vertex uncut, which is the defect the
            # miter branch below hunts. So the recorded number is the physical
            # breach and the assertion is the excess over the butt geometry.
            #
            # ⚠️ SIN, NOT COS, AND THE TWO AGREE ONLY AT 90 DEGREES - which is
            # the turn every asserted butt case in this suite happens to make,
            # so the first version of this line was right nowhere else. The
            # end face is perpendicular to the arriving tangent and spans
            # `+-h` ACROSS it, the bisector normal sits at `t/2` off that
            # tangent, so the corner of the face projects onto the normal at
            # `h*sin(t/2)`. Measured at four turns (30/60/90/120 deg) on a
            # bend butt joint: the breach is `h*sin(t/2)` to six decimals
            # every time, and `AB_fillet`'s own recorded 0.005853 is
            # `0.03*sin(11.25 deg)`. Under `cos` a 120 degree butt joint
            # failed by 1.10e-02 m for being a butt joint.
            sin_half = math.sqrt(max(0.0, 1.0 - cos_half * cos_half))
            excess = max(excess, d - _half_across(rec) * sin_half)
            if d > worst:
                worst, where = d, "%s butt %s at (%.2f, %.2f)" % (
                    rec["pc_module"], side, v[0], v[2])
    if not bevels:
        if not seen:
            return _skip("corner_breach_m", "no mitered or dissolved corners")
        return Result("corner_breach_m", excess <= 2e-3, _round(worst, 6),
                      "%s, %.2e m over the butt wedge" % (where, excess))
    for bevel in bevels:
        legs = set()
        for leg in (bevel.section_in, bevel.section_out):
            if leg is not None:
                legs.add((str(leg.curve_id), leg.index))
        for eid, rec in scene.by_id.items():
            placement = scene.plan_by_id.get(eid)
            # ONLY the two legs that meet here. A bisector plane is infinite,
            # and on a triangle or a rectangle the OPPOSITE side crosses it
            # perfectly legitimately - scoring it scored a 0.73 m "breach" on
            # a panel two corners away. Everything on the corner's own two
            # legs is strictly on its own side of the plane except within the
            # miter overhang of the vertex, which is the thing being measured.
            if placement is None or (str(placement.curve_id),
                                     placement.section_index) not in legs:
                continue
            w = rec["world"]
            pts = [(w[i], w[i + 1], w[i + 2]) for i in range(0, len(w), 3)]
            if not pts:
                continue
            cen = _centroid(rec)
            if cen is None:
                continue
            sign = 1.0 if _dot3(_sub3(cen, bevel.v), bevel.n) > 0.0 else -1.0
            breach = max(-sign * _dot3(_sub3(q, bevel.v), bevel.n)
                         for q in pts)
            seen += 1
            if breach > worst:
                worst, where = breach, "%s at turn %.1f deg" % (
                    rec["pc_module"], bevel.turn)
    if not seen:
        return _skip("corner_breach_m", "no pieces near a corner")
    return Result("corner_breach_m", worst <= tol, _round(worst, 6), where)


# --- 4.3 in BEND mode: the dissolved vertex, and the wedge a butt joint
# leaves inside the corner. Cycle 3v's open finding, closed here.
#
# A bend corner produces NO bevel at all (`merge_bend_sections` welds the two
# sections into one run before `solve_corners` ever looks at the boundary), so
# every `corner_*` check above reports SKIP on every bend case - which is how a
# real interpenetration sat unmeasured for two cycles. The vertex is still
# recorded: `Section.welds` carries the dissolved corners in section-local
# metres (D36), and that is what these two walk.

def _welds(scene, tol=1e-4):
    """[(v, n, section, welded pieces...)] - one entry per DISSOLVED corner.

    Returns (vertex, bisector normal, cos(turn/2), [(side, eid, rec)],
    spanned) where
    `side` is "in" for the piece ARRIVING at the vertex and "out" for the one
    leaving it, and `spanned` is True when ONE piece covers the vertex - in
    which case there is no butt joint to measure and the geometry is
    continuous by construction (4.3's "deformed across the vertex").
    """
    out = []
    for track in scene.tracks:
        cid = str(track["curve"].curve_id)
        path, remap = track["path"], track["remap"]
        for section in track["sections"]:
            welds = list(getattr(section, "welds", ()) or ())
            if not welds:
                continue
            total = section.curve_length
            for w in welds:
                s_real = remap(section.s0 + w)
                v, tout = path.sample(s_real)
                # ⚠️ THE RING'S OWN SEAM IS A WELD AT s = 0, and `Path.sample`
                # only pushes a backward read onto the closing segment when
                # the ASKED s was non-zero (it cannot know that a literal 0
                # meant "arriving"). Reading it as it stands returns the
                # FIRST segment's tangent for both sides, so `n` came out as
                # the outgoing tangent rather than the bisector and the
                # closed rectangle's seam scored 0.030 m against a plane no
                # corner has. Ask for the arriving side at `total`.
                s_in = s_real
                if path.closed and s_real <= 1e-9:
                    s_in = path.total
                _p, tin = path.sample(s_in, forward=False)
                summed = (tin[0] + tout[0], tin[1] + tout[1], tin[2] + tout[2])
                if math.sqrt(_dot3(summed, summed)) < 1e-6:
                    continue          # a hairpin has no usable bisector
                n = tuple(c / math.sqrt(_dot3(summed, summed)) for c in summed)
                cos_half = abs(_dot3(n, tout))      # = cos(turn/2)
                pieces, spanned = [], False
                for p in scene.plan:
                    if str(p.curve_id) != cid                             or p.section_index != section.index:
                        continue
                    rec = scene.by_id.get(p.elem_id)
                    if rec is None:
                        continue
                    # a closed ring's own seam sits at 0 and D19 lets a run
                    # wrap it, so the weld is looked for at both ends
                    for wv in (w, w + total, w - total):
                        if p.s0 + tol < wv < p.s1 - tol:
                            spanned = True
                        elif abs(p.s1 - wv) <= tol:
                            pieces.append(("in", p.elem_id, rec))
                        elif abs(p.s0 - wv) <= tol:
                            pieces.append(("out", p.elem_id, rec))
                out.append((v, n, cos_half, pieces, spanned))
    return out


def _half_across(rec):
    """The piece's own across half-extent, in METRES of module local space.

    D20 puts across on local +Z, and `pc_local` rides through the deform and
    the clip, so this reads the same number off a packed prim and off a bent
    one. It is what makes the butt allowance a fact about the KIT rather than
    a tolerance someone picked.
    """
    loc = rec["local"]
    zs = [abs(loc[i + 2]) for i in range(0, len(loc), 3)]
    return max(zs) if zs else 0.0


def _pts_of(rec):
    w = rec["world"]
    return [(w[i], w[i + 1], w[i + 2]) for i in range(0, len(w), 3)]


def _hull_xz(pts):
    """Monotone-chain convex hull of the XZ footprint, CCW."""
    ps = sorted(set((round(p[0], 9), round(p[2], 9)) for p in pts))
    if len(ps) < 3:
        return ps

    def half(seq):
        out = []
        for q in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0])
                                     * (q[1] - out[-2][1])
                                     - (out[-1][1] - out[-2][1])
                                     * (q[0] - out[-2][0])) <= 0.0:
                out.pop()
            out.append(q)
        return out
    lower, upper = half(ps), half(list(reversed(ps)))
    return lower[:-1] + upper[:-1]


def _clip_convex(subject, clip):
    """Sutherland-Hodgman. Both polygons CCW and convex, so the result is the
    intersection and it is convex."""
    out = list(subject)
    for i in range(len(clip)):
        a, b = clip[i], clip[(i + 1) % len(clip)]
        ex, ez = b[0] - a[0], b[1] - a[1]

        def inside(q):
            return ex * (q[1] - a[1]) - ez * (q[0] - a[0]) >= -1e-12
        src, out = out, []
        for k in range(len(src)):
            p, q = src[k - 1], src[k]
            ip, iq = inside(p), inside(q)
            if ip != iq:
                dx, dz = q[0] - p[0], q[1] - p[1]
                den = ex * dz - ez * dx
                if abs(den) > 1e-18:
                    t = (ex * (p[1] - a[1]) - ez * (p[0] - a[0])) / -den
                    out.append((p[0] + dx * t, p[1] + dz * t))
            if iq:
                out.append(q)
        if not out:
            return []
    return out


def _area(poly):
    a = 0.0
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        a += p[0] * q[1] - q[0] * p[1]
    return abs(a) * 0.5


def corner_wedge(scene, tol=1e-9):
    """THE BUTT-JOINT WEDGE, in square metres of doubly-solid footprint.

    Cycle 3v measured it on a raster and left it unbaselined: two square-ended
    0.06 m panels meeting at 90 degrees must leave a wedge of doubly-solid
    geometry inside the corner and the matching notch outside - 0.03 x 0.03 m
    on the starter panel, which is the 0.0009 m2 that pass reported. It is
    INHERENT to a butt joint, RailClone behaves the same way, and miter is the
    fix (D36, extended) - so this is baselined as the ACCEPTED LIMIT rather
    than asserted to be zero. What it protects against is the number GROWING.

    Convex hulls in XZ, not a raster: the two pieces at a butt joint are
    boxes, so the hull is exact and the intersection is a polygon clip instead
    of 10 000 point-in-solid tests. A piece that SPANS the vertex is skipped -
    it is one continuous bent piece, and there is no joint to measure.
    """
    joints = _welds(scene)
    if not joints:
        return _skip("corner_wedge_m2", "no dissolved corners")
    worst, where, seen, spanned_n = 0.0, "", 0, 0
    for v, _n, _cos_half, pieces, spanned in joints:
        if spanned:
            spanned_n += 1
            continue
        ins = [r for s, _e, r in pieces if s == "in"]
        outs = [r for s, _e, r in pieces if s == "out"]
        for a in ins:
            for b in outs:
                seen += 1
                area = _area(_clip_convex(_hull_xz(_pts_of(a)),
                                          _hull_xz(_pts_of(b))))
                if area > worst:
                    worst, where = area, "%s|%s at (%.2f, %.2f)" % (
                        a["pc_module"], b["pc_module"], v[0], v[2])
    if not seen:
        return _skip("corner_wedge_m2",
                     "%d dissolved corners, all spanned" % spanned_n)
    return Result("corner_wedge_m2", True, _round(worst, 8),
                  "%s (%d joints, %d spanned)" % (where, seen, spanned_n))


def corner_clearance(scene, vertex, expected, tol=5e-3):
    """4.3 item E: the fillet moved the PATH, so the pieces keep their distance
    from the original sharp vertex.

    `expected` is r*(1/cos(turn/2) - 1) - trigonometry on the INPUT, never a
    number the builder produced - so a fillet that silently did nothing, or
    that rounded to the wrong radius, cannot agree with the check.
    """
    best = None
    for rec in scene.by_id.values():
        # AXIS points, not every point: a panel's own 0.03 m half-width would
        # otherwise put the nearest vertex 0.03 m inside the path and make the
        # number a fact about the kit instead of about the fillet.
        frame = _element_frame(rec)
        for x in _station_xs(rec):
            p = _axis_of(_face(rec, x), frame)
            if p is None:
                continue
            d = math.hypot(p[0] - vertex[0], p[2] - vertex[2])
            if best is None or d < best:
                best = d
    if best is None:
        return _skip("corner_clearance_m", "no pieces")
    return Result("corner_clearance_m", abs(best - expected) <= tol,
                  _round(best, 6), "expected %.4f" % expected)


def corner_abut(scene):
    """The seam between the corner assembly and the fill that runs up to it.

    The mitered joint at the vertex is measured by `corner_seam_m`; this is
    the OTHER joint the corner creates, one per leg, where the corner
    assembly's outer end meets the last default piece. It is the one a
    reserve computed slightly wrong opens, and it is invisible to
    `max_gap_m`, which walks consecutive pieces of one run and stops where
    the run does.

    Both points are read off built geometry: the corner piece's own outermost
    axis point on the leg, and the nearest default-piece axis endpoint.
    """
    bevels = [b for b in _bevels(scene) if getattr(b, "assembly", None)
              and b.assembly.pieces]
    if not bevels:
        return _skip("corner_abut_m", "no corner assemblies")
    worst, where, seen = 0.0, "", 0
    anchored = set(eid for eid, _rec in _assembly_recs(scene))
    ends = {}
    for eid, rec in scene.by_id.items():
        if eid in anchored:
            continue
        placement = scene.plan_by_id.get(eid)
        if placement is None:
            continue
        # ⚠️ PER SECTION. A corner between a long leg and a SQUEEZED short one
        # leaves the short leg with no default run at all, and scanning every
        # piece in the scene then measured the 1.5 m gap to the other leg's
        # run as an abutment failure. A leg with nothing on it has no
        # abutment; it has `pc_warn_overflow`.
        key = (str(placement.curve_id), placement.section_index)
        a, b = axis_points(rec)
        for pt in (a, b):
            if pt is not None:
                ends.setdefault(key, []).append(pt)
    if not ends:
        return _skip("corner_abut_m", "no default pieces")
    for bevel in bevels:
        for side in ("in", "out"):
            axis = bevel.tin if side == "in" else bevel.tout
            sign = -1.0 if side == "in" else 1.0
            leg = bevel.section_in if side == "in" else bevel.section_out
            here = ends.get((str(leg.curve_id), leg.index)) if leg else None
            if not here:
                continue
            far, far_t, far_stepped = None, None, False
            for eid, rec in _assembly_recs(scene):
                cen = _centroid(rec)
                # ...of THIS corner. A closed rectangle has four assemblies of
                # the same module on the same legs, and scanning all of them
                # picked the post at the far end of the 8 m side: a 0.226 m
                # "abutment gap" that was really two different corners.
                if cen is None or min(bevels,
                                      key=lambda b: _dist(cen, b.v)) is not bevel:
                    continue
                frame = _element_frame(rec)
                for x in _station_xs(rec):
                    pt = _axis_of(_face(rec, x), frame)
                    if pt is None:
                        continue
                    t = sign * _dot3(_sub3(pt, bevel.v), axis)
                    if t < -1e-6 or t > 1e6:
                        continue
                    if far_t is None or t > far_t:
                        far_t, far = t, pt
                        far_stepped = (rec["pc_zmode"] == "stepped")
            if far is None:
                continue
            seen += 1
            # A `stepped` piece is FLAT at its own start elevation, so two of
            # them meeting on a PITCHED leg step vertically by design (D24's
            # riser, and 4.4's deferred flatten-under). Measured in XZ, like
            # `max_gap_m` and `exact_fill_m` already do for the same reason.
            metric = _dist_xz if far_stepped else _dist
            d = min(metric(far, e) for e in here)
            if d > worst:
                worst, where = d, "%s leg, %.3f m out" % (side, far_t)
    if not seen:
        return _skip("corner_abut_m", "no corner geometry")
    return Result("corner_abut_m", worst <= 2e-3, _round(worst, 6), where)


def corner_turns(scene):
    """Every corner this case actually produced: [turn, side, mode].

    Recorded, not asserted, and it is the anti-vacuity check for the whole
    4.3 family: `side` is -1 exactly where the path turns the OTHER way, so a
    "reflex corner" case that quietly contained none - which the first zigzag
    did, both of its vertices turning left - shows up as two +1s instead of
    reading as coverage it never had. `mode` records where 4.3's degenerate
    fallback fired.
    """
    rows = []
    for bevel in _bevels(scene):
        rows.append([_round(bevel.turn, 4), int(bevel.side), bevel.mode,
                     1 if bevel.degenerate else 0])
    if not rows:
        return _skip("corner_turns", "no corners")
    rows.sort()
    return Result("corner_turns", True, rows, "%d corners" % len(rows))


def corner_welds(scene):
    """[dissolved corners, of those spanned by one piece] - D36, as a count.

    In `bend` mode 4.3 does not break the run at a corner: the sections are
    welded and whatever piece lands on the vertex DEFORMS ACROSS IT, which is
    4.3's own wording. Nothing else on this list can see that decision - the
    fill, the gaps and the frames are all still fine if the run breaks there -
    so a revert of D36 only ever showed up as moved baseline values. This is
    the decision itself, as two numbers.

    ⚠ THE SECOND NUMBER IS NOT ALWAYS THE FIRST, AND THAT IS NOT A DEFECT.
    On the 24 m L-shape twelve 2 m panels fit exactly, so a piece BOUNDARY
    lands on the elbow and no single piece spans it: the chain is still
    continuous (`max_gap_m` = 1.8e-7) but the outside of that corner keeps the
    notch a butt joint leaves. That is what a corner module and miter mode are
    for, and it is recorded here rather than hidden behind an average.
    """
    total, spanned = 0, 0
    for track in scene.tracks:
        cid = str(track["curve"].curve_id)
        for section in track["sections"]:
            for w in getattr(section, "welds", ()):
                total += 1
                for p in scene.plan:
                    if str(p.curve_id) != cid                             or p.section_index != section.index:
                        continue
                    # a closed ring's seam sits at 0, and D19 lets a run
                    # wrap it, so the weld is looked for at both ends
                    if any(p.s0 + 1e-6 < v < p.s1 - 1e-6
                           for v in (w, w + section.curve_length)):
                        spanned += 1
                        break
    if not total:
        return _skip("corner_welds", "no dissolved corners")
    return Result("corner_welds", True, [total, spanned],
                  "%d of %d spanned by one piece" % (spanned, total))


def element_resolution(scene):
    """Every planned `pc_elem_id` resolves to a built prim. Cycle 2c's own
    finding, closed.

    ⚠️ WITHOUT THIS, THREE CHECKS FAIL OPEN. `exact_fill_m`, `max_gap_m` and
    `axis_on_curve_m` all reach the geometry through
    `scene.by_id.get(placement.elem_id)` and `continue` on a miss, so a build
    whose prim ids do not match its plan's ids measures 0.0 m and passes.
    `element_count` cannot cover for them - it compares two lengths, and a 1:1
    id scramble keeps both - and `unique_elem_ids` reads the PLAN, not the
    geometry. Cycle 2c killed that mutation with two checks in five cases; the
    number here is the miss count itself.
    """
    missing = [p.elem_id for p in scene.plan if p.elem_id not in scene.by_id]
    return Result("unresolved_elem_ids", not missing, len(missing),
                  missing[0] if missing else "")


def stamp_provenance(scene):
    """3.4's THREE UNASSERTED STAMPS, read back against the plan the piece
    came from - standing finding (10), cycle 12, closed here.

    `pc_u`, `pc_section` and `pc_variant` were asserted by NOTHING: corrupt
    any of them in BOTH writers (`pc_u` + 0.25, `pc_section` + 1, `pc_variant`
    blanked) and the suite reported 87 cases, 0 failing, 0 baseline moves.
    `stamp_parity` proves the two writers AGREE; it never asks whether either
    is right, and `output_schema` only asks whether the names exist.

    It is a prerequisite for 11.2's port, not housekeeping: P1, P3, P4 and P6
    each rewrite a stamp writer, and three of its fourteen values were
    unpinned.

    `pc_u` is re-derived rather than re-read: `_stamp_values` writes
    `placement.u`, so this recomputes `section.u_at(placement.s0)` from the
    section list the builder actually used (`scene.section_of`), which is a
    different expression reaching the same number. Reported in U UNITS, whose
    float32 storage floor at 0..1 is ~6e-08.

    [worst |du|, pc_section wrong, pc_variant wrong].
    """
    worst, bad_sec, bad_var = 0.0, 0, 0
    # THREE SLOTS, NOT ONE. `where` used to be shared, and the `pc_u` branch
    # set it unconditionally while the other two only filled it when it was
    # still empty - so the one run in which this check has ever fired (20
    # elements with a wrong `pc_variant`, reported by the third review round)
    # recorded the detail `DL|0|default|15|variant pc_u`, byte-identical to a
    # passing run's, and named none of the elements that actually failed. A
    # check's detail is the only artifact a failure leaves behind.
    at = {"u": "", "sec": "", "var": ""}
    for p in scene.plan:
        rec = scene.by_id.get(p.elem_id)
        if rec is None:
            continue
        section = scene.section_of.get((str(p.curve_id), p.section_index))
        if section is not None:
            du = abs(float(rec["pc_u"]) - section.u_at(p.s0))
            if du > worst:
                worst, at["u"] = du, "%s pc_u" % p.elem_id
        if int(rec["pc_section"]) != int(p.section_index):
            bad_sec += 1
            at["sec"] = at["sec"] or "%s pc_section %s != %s" % (
                p.elem_id, rec["pc_section"], p.section_index)
        if str(rec["pc_variant"]) != str(p.variant):
            bad_var += 1
            at["var"] = at["var"] or "%s pc_variant %r != %r" % (
                p.elem_id, str(rec["pc_variant"]), str(p.variant))
    ok = worst <= 2e-6 and not bad_sec and not bad_var
    return Result("stamp_provenance", ok,
                  [_round(worst, 9), bad_sec, bad_var],
                  " | ".join(v for v in (at["u"], at["sec"], at["var"]) if v))


# --- 11.2's own tripwires ---------------------------------------------------
#
# tests/README.md's compounding rule, applied to the port plan: each of these
# is a number an audit measured once in a scratchpad, standing up as an
# assertion so the next agent re-runs it instead of re-deriving it. They do
# not belong to a scene case, so `run_scene_checks.py` runs them once, under
# their own pseudo-case.
#
# ⚠️ EACH CARRIES ITS EXPECTATION ON THE CALL, `scale_gate.py`'s LADDER shape.
# Two of them describe a defect the port is FOR, so "green" today means "still
# the shape the audit measured"; the commit that fixes one flips its
# expectation, and that flip is the proof.


def stamp_calls_per_piece(build_fn, expect_max=1.0, name=None):
    """HOM per-element attribute writes per placed piece - what P1 is for.

    RUN IT ON BOTH BRANCHES. Until the third review round this had ONE row, on
    a 100 % packed fixture, and the deformed branch is where the per-prim
    stamp costs 14 x the piece's PRIM COUNT rather than 14: restoring the
    D102-era writer there took `scale_gate` arc_10 from 2.361 s to 19.854 s
    (8.4x) with the scene suite, the unit tests, the HDA suite and the ladder
    ALL green, because `tripwire_packed_run` reports `deformed == 0` and this
    number read 0.005 either way. `name` is what lets the two rows share one
    baseline.

    62 % of the real node cook was `hou.Prim.setAttribValue`, 14 calls per
    packed piece (11.2 P1). Deterministic - a COUNT, not a timing - so it
    sits in the baseline without churning.

    ⚠️ THE CEILING WAS 15.0 AND IS NOW 1.0. P1 landed: the stamp is
    accumulated across the whole output and written once per attribute, so
    this reads 0.005 (the one remaining call is `dress_caps` tagging a cap,
    which is not a stamp). Restoring the per-piece writer puts it back at
    14.005 and this goes red - which is what the ceiling is for.
    """
    calls = {"n": 0}
    real = hou.Prim.setAttribValue

    def counting(self, *a, **k):
        calls["n"] += 1
        return real(self, *a, **k)
    hou.Prim.setAttribValue = counting
    try:
        _out, report = build_fn()
    finally:
        hou.Prim.setAttribValue = real
    pieces = report["packed"] + report["deformed"]
    if not pieces:
        return _skip("stamp_calls_per_piece", "nothing was built")
    per = calls["n"] / float(pieces)
    return Result(name or "stamp_calls_per_piece", per <= expect_max,
                  _round(per, 3), "%d calls, %d pieces (%d deformed, "
                  "ceiling %.1f)" % (calls["n"], pieces, report["deformed"],
                                     expect_max))


def curve_sample_scaling(curve_cls, expect="O(n)", samples=200,
                         cold_expect=None):
    """Does `Curve.sample` cost depend on the curve's VERTEX COUNT - P2.

    `__init__.py`'s sampler rebuilds its whole per-segment table on every
    call, so it is O(n) per call: 3.2 us at 10 verts against 8 218 us at
    20 001 (11.2 P2), 83 % of the worst case either audit found.

    ⚠️ THE VALUE IS THE CLASS, NOT THE MICROSECONDS. A timing in
    `baseline.json` would move on every run and drown the movement list that
    every port commit has to read; a two-valued label moves exactly once, in
    the commit that earns it. The raw numbers ride in `detail`, which the
    runner records but does not diff.

    AND THE SECOND READING IS THE COLD ONE, which this check did not have.
    Warming the cache before timing measures only the path a MANY-SAMPLES
    curve takes. The shape citygen actually hands the tool is the opposite -
    hundreds of separate short polylines with `Curve.sample` called exactly
    twice per section - so what it pays is table CONSTRUCTION, once per curve,
    and P2 made that first call ~9 % SLOWER rather than faster (it now builds
    `his` alongside `segs`). Construction cannot be O(1) - an arclength table
    is linear in vertices by definition - so the cold expectation is `O(n)`
    and what it pins is that it stays LINEAR: a rebuild-per-segment regression
    reads quadratic here and goes red, where the warm reading cannot see it at
    all. `cold_expect=None` keeps the old one-value shape.
    """
    us, cold = {}, {}
    for n in (10, 20001):
        step = 20000.0 / n
        pts = [(i * step, 0.0, 0.0) for i in range(n)]
        c = curve_cls("m", pts)
        c.sample(1.0)                            # warm `_cumulative`
        t0 = time.time()
        for i in range(samples):
            c.sample(20000.0 * i / float(samples))
        us[n] = (time.time() - t0) / samples * 1e6
        reps = 40 if n > 1000 else samples
        t0 = time.time()
        for i in range(reps):
            curve_cls("m", pts).sample(20000.0 * i / float(reps))
        cold[n] = (time.time() - t0) / reps * 1e6
    ratio = us[20001] / max(us[10], 1e-9)
    got = "O(1)" if ratio <= 5.0 else "O(n)"
    # PER VERTEX, so linear construction reads flat and quadratic reads 2 000x
    per = (cold[20001] / 20001.0) / max(cold[10] / 10.0, 1e-12)
    got_cold = "O(n)" if per <= 5.0 else "O(n^2)"
    if cold_expect is None:
        return Result("curve_sample_scaling", got == expect, got,
                      "%.2f us at 10 verts, %.2f us at 20 001 (%.0fx), "
                      "expected %s" % (us[10], us[20001], ratio, expect))
    return Result("curve_sample_scaling",
                  got == expect and got_cold == cold_expect,
                  [got, got_cold],
                  "warm %.2f us at 10 verts, %.2f us at 20 001 (%.0fx, %s, "
                  "expected %s); COLD construct+1 sample %.1f us at 10, "
                  "%.1f us at 20 001 (%.1fx per vertex, %s, expected %s)"
                  % (us[10], us[20001], ratio, got, expect,
                     cold[10], cold[20001], per, got_cold, cold_expect))


def conform_cache_per_element(build_fn, conform_mod, expect_max=30.0):
    """Entries `ConformPath._cache` holds per placed element - P5's cost.

    The memo is unbounded and keyed on `(round(s,9), forward)`: 53 861
    entries / 24 MB on one 2 km curve (11.2 P5), and a 300-street conformed
    citygen run would carry several hundred MB of it. Nothing currently
    notices it growing. P5 deletes the cache, at which point this reads 0.
    """
    made = []
    real = conform_mod.ConformPath.__init__

    def spy(self, *a, **k):
        real(self, *a, **k)
        made.append(self)
    conform_mod.ConformPath.__init__ = spy
    try:
        _out, report = build_fn()
    finally:
        conform_mod.ConformPath.__init__ = real
    if not made:
        return _skip("conform_cache_per_element", "no surface")
    entries = sum(len(p._cache) for p in made)
    pieces = report["packed"] + report["deformed"]
    if not pieces:
        return _skip("conform_cache_per_element", "nothing was built")
    per = entries / float(pieces)
    return Result("conform_cache_per_element", per <= expect_max,
                  _round(per, 3), "%d entries over %d elements on %d paths "
                  "(ceiling %.0f)" % (entries, pieces, len(made), expect_max))


def station_share_hit_rate(build_fn, place_mod, conform_mod,
                           expect_max_misses=0.0):
    """Does P3's station cache actually get HIT - and would a miss be seen?

    P3's safety argument is "a miss just samples, so it is slower and never
    wrong", and the third review round instrumented it: 2 691 hits, 0 misses,
    0 wrong hits across all 88 cases. The fallback branch is therefore DEAD as
    tested, which cuts both ways - it is never wrong, and nobody would notice
    if it started being taken. A key drifting by one ULP (a different `remap`
    composition order, a resample of `proto.stations`, a float32 round trip of
    module P) sends EVERY station through a fresh sample: still correct, and
    P3's whole win silently gone.

    Counted, not timed: every `sample` call made from inside
    `_deform_positions` is a miss, because a hit reads the dict pass A filled.
    `[stations offered, misses per piece]` - the first is the liveness the
    second cannot report, so a build that stopped populating the cache at all
    fails here instead of quietly reading `0 misses` off an empty dict.
    """
    state = {"depth": 0, "offered": 0, "miss": 0, "pieces": 0}
    real_dp = place_mod._deform_positions
    reals = [(place_mod.Path, place_mod.Path.sample)]
    if conform_mod is not None:
        reals.append((conform_mod.ConformPath, conform_mod.ConformPath.sample))

    def wrapped(src, proto, path, s0_flat, scale, zmode, remap,
                tilt=False, base_y=None, band=None, samples=None):
        state["pieces"] += 1
        state["offered"] += len(samples or ())
        state["depth"] += 1
        try:
            return real_dp(src, proto, path, s0_flat, scale, zmode, remap,
                           tilt, base_y, band, samples)
        finally:
            state["depth"] -= 1

    def counted(real):
        def sample(self, s, forward=True):
            if state["depth"]:
                state["miss"] += 1
            return real(self, s, forward)
        return sample

    place_mod._deform_positions = wrapped
    for cls, real in reals:
        cls.sample = counted(real)
    try:
        _out, _report = build_fn()
    finally:
        place_mod._deform_positions = real_dp
        for cls, real in reals:
            cls.sample = real
    if not state["pieces"]:
        return _skip("station_share_hit_rate", "nothing deformed")
    per = state["miss"] / float(state["pieces"])
    return Result("station_share_hit_rate",
                  per <= expect_max_misses and state["offered"] > 0,
                  [state["offered"], _round(per, 3)],
                  "%d stations offered over %d deformed pieces, %d misses "
                  "(ceiling %.1f per piece)"
                  % (state["offered"], state["pieces"], state["miss"],
                     expect_max_misses))


_PEAK_ROW = (("pc_elem_id", ""), ("pc_module", "panel"), ("pc_variant", ""),
             ("pc_section", 0), ("pc_index", 0), ("pc_u", 0.0),
             ("pc_s0", 0.0), ("pc_s1", 0.0), ("pc_zmode", "vertical"),
             ("pc_generated", 1), ("pc_deformed", 1), ("pc_corner_cut", 0),
             ("pc_curve_id", "TW"), ("pc_style", "tripwire"))


def stamp_bulk_peak_kb(place_mod, pieces=1000, prims=34, expect_max=1200.0):
    """Python bytes `_stamp_bulk` holds live at its peak - P1's memory cost.

    P1 traded memory for the 2x: it accumulates the whole output's stamp and
    writes it at the end. Materialising ALL FIFTEEN columns before writing any
    of them cost **+97 MB of peak working set (61 %)** on the 340 000-prim
    deformed row, and nothing measured it - `scale_gate` prints a dRSS column
    but asserts only packed counts, and `baseline.json` carries no memory
    value at all, so the gate's own number moved unseen. Measured directly on
    the writer: 49.5 MB of Python peak for one `arc_10` build, against 7.6 MB
    once the columns are expanded one at a time.

    `tracemalloc` counts PYTHON allocations exactly, so this is deterministic
    for the same input - a number, not a timing, and it baselines the way
    `stamp_calls_per_piece` does. The fixture is synthetic on purpose: it is
    the writer's own shape (pieces x prims-per-piece x the 3.4 name set), so
    it cannot drift with the kit.
    """
    import tracemalloc
    n = pieces * prims
    geo = hou.Geometry()
    geo.createPoints([(float(i), 0.0, 0.0) for i in range(3 * n)])
    geo.createPolygons(tuple((3 * i, 3 * i + 1, 3 * i + 2) for i in range(n)),
                       True)
    warn = "pc_warn_bend_resolution"
    rows, names = [], list(dict(_PEAK_ROW)) + [warn]
    for i in range(pieces):
        vals = (("pc_elem_id", "E|%d" % i), ("pc_module", "panel"),
                ("pc_variant", ""), ("pc_section", i % 7), ("pc_index", i),
                ("pc_u", i / float(pieces)), ("pc_s0", i * 2.0),
                ("pc_s1", i * 2.0 + 2.0), ("pc_zmode", "vertical"),
                ("pc_generated", 1), ("pc_deformed", 1), ("pc_corner_cut", 0),
                ("pc_curve_id", "TW"), ("pc_style", "tripwire"))
        # only SOME pieces warn - the shape that makes the writer fill blanks
        rows.append((prims, vals + (((warn, 1),) if i % 3 else ())))
    for name, default in tuple(_PEAK_ROW) + ((warn, 0),):
        geo.addAttrib(hou.attribType.Prim, name, default)
    tracemalloc.start()
    tracemalloc.reset_peak()
    before, _p = tracemalloc.get_traced_memory()
    place_mod._stamp_bulk(geo, rows, [warn])
    _cur, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    kb = (peak - before) / 1024.0
    return Result("stamp_bulk_peak_kb", kb <= expect_max, _round(kb, 0),
                  "%d pieces x %d prims x %d attrs, ceiling %.0f kB"
                  % (pieces, prims, len(names), expect_max))


def build_out_keeps_upstream_stamps(build_fn, place_mod):
    """`build(out=...)`'s `base` machinery, exercised - dev-loop Rule 0.

    `_stamp_bulk`'s `base` argument and `plan_points`' twin exist so a
    CALLER-SUPPLIED `out` keeps the stamps it already carried, and no caller
    in the package or in the suite passes `out=` - so both branches were dead
    as tested and a later item could have blanked the head with the whole
    suite green. One build into a pre-populated geometry, and the upstream
    prim's own stamp read back afterwards.

    ⚠️ HOM TRAP FOUND WHILE MUTATION-TESTING THIS:
    `hou.Geometry.setPrimStringAttribValues` treats `""` as LEAVE UNCHANGED -
    writing `("", "NEW")` over `("KEEP", "ALSO")` yields `("KEEP", "NEW")`,
    not `("", "NEW")`. So a mutation that blanks the string head is invisible,
    and a string column can never clear a value a caller-supplied `out`
    already carried. Harmless here (`build`'s own `out` is fresh, so every
    default is already `""`), and it is why the mutation that proves this
    check corrupts the head rather than blanking it. Houdini catches the other
    half itself: dropping the head outright is a length mismatch and
    `setPrimStringAttribValues` raises `Incorrect attribute value sequence
    size`.

    `[upstream prims kept, new prims stamped]`.
    """
    pre = hou.Geometry()
    pre.createPoints([(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)])
    pre.createPolygons(((0, 1, 2),), True)
    for name, default in place_mod.ELEM_PRIM_ATTRS:
        pre.addAttrib(hou.attribType.Prim, name, default)
    up = pre.prims()[0]
    up.setAttribValue("pc_elem_id", "UPSTREAM")
    up.setAttribValue("pc_module", "mine")
    try:
        out, report = build_fn(pre)
    except Exception as exc:                     # nothing in here may raise
        return Result("build_out_keeps_upstream_stamps", False, [0, 0],
                      "build(out=...) raised %s: %s" % (type(exc).__name__,
                                                        exc))
    prims = out.prims()
    kept = 1 if (str(prims[0].attribValue("pc_elem_id")) == "UPSTREAM"
                 and str(prims[0].attribValue("pc_module")) == "mine") else 0
    stamped = sum(1 for pr in prims[1:]
                  if str(pr.attribValue("pc_elem_id")) not in ("", "UPSTREAM"))
    built = report["packed"] + report["deformed"]
    return Result("build_out_keeps_upstream_stamps",
                  bool(kept and built and stamped == len(prims) - 1),
                  [kept, stamped],
                  "%d prims out, %d built elements, prim 0 reads %r"
                  % (len(prims), built, str(prims[0].attribValue("pc_elem_id"))))
