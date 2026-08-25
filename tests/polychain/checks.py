"""polyChain geometry checks - the assertions, in one place.

Each check returns a `Result` carrying a NUMBER, never a bare pass/fail;
nothing raises - a check that cannot run reports `skipped`.

v2, 2026-08-25: cut from 5 111 lines / ~130 checks. Per-attribute comparisons
of built geometry against the plan are subsumed by `diff.compare` in
`run_generated.py` and are gone. What remains: the geometric properties with a
registered mutation (is the answer RIGHT), and the port tripwires - measured
COST ceilings, each bought by a regression that left every geometry check
green.

WHAT THE NUMBERS MEAN
  packed_pieces      pieces shipped packed rather than deformed.
  warnings           the warning names a case is ALLOWED to raise, exactly.
  stamp_parity       [values compared, differing] - D102 BULK stamp vs the
                     per-prim writer it replaced.
  bank_deg           tilt of an ADAPTIVE piece's up axis off world up; must
                     be NON-ZERO on a slope.
  camber_deg         the cross-slope a conformed piece takes from the surface.
  conform_misses     pieces whose drape left the terrain (D53), warned.
  conform_parity     the built drape against `conform.Surface` itself.
  curvature_budget_m worst deviation a PACKED piece leaves against its budget.
  deform_gate_m      [worst deviation left packed, over budget, still packed]
                     - D100's dangerous direction.
  packed_true_dev_m  the same deviation measured on the delivered geometry.
  corner_abut_m      the gap between a corner assembly and the run it joins.
  corner_outside_m   the outside-length of a mitered corner against the plan.
  corner_breach_m    how far a corner piece breaches its neighbour's span.
  corner_face_mate_m the mating faces of a corner, coplanar.
  double_pillar_m    the corner reads as ONE pillar (the other corner checks
                     are closure checks; a double pillar is perfectly closed).
  *_per_piece / *_per_build / *_wrappers_built / wrapper_reads / *_hit_rate /
  *_peak_kb / *_scaling
                     11.9's cost tripwires, each with a measured ceiling.
"""

import math
import struct
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

    The face map is AFFINE (`world = A + up*y + across*z`), recovered exactly
    from point pairs.
    """
    if not face:
        return (None, None, None)
    (l0, w0) = face[0]
    up, across = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    # EACH PAIR MUST VARY IN ONE LOCAL AXIS ONLY: mixing folds `across` into
    # `up` (phantom 0.160 m corner_abut_m gap on a closed clipped post, and
    # the same fragility can MASK a real gap).
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
        # NOT a silent default: assuming world up/across on a one-axis clipped
        # face read a 0.129 m "gap" on a closed pentagon. No recoverable frame
        # means no measurement; every caller handles None.
        return (None, None, None)
    origin = tuple(w0[k] - up[k] * l0[1] - across[k] * l0[2] for k in range(3))
    return (origin, up, across)


def _affine_fit(face):
    """Least-squares (origin, up, across) over EVERY point of the face.

    No pair to pick wrong (pair-picking caused phantom 0.160/0.129 m corner
    gaps); a degenerate (y, z) spread makes the normal matrix singular and
    this returns None.
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

    A clipped end face may have no recoverable `across`; the piece is rigid,
    so borrowing the frame from a face that does is exact.
    """
    for x in sorted(set(rec["local"][0::3])):
        _o, up, across = _frame_of(_face(rec, x))
        if up is not None and across is not None:
            return (up, across)
    return (None, None)


def _axis_of(face, frame=None):
    """The world point at the face's local (x, 0, 0).

    NOT the face centroid - cross-section centres differ per module (measured
    0.050 m phantom gap, 0.575 m phantom start error); the affine face map
    divides the offsets out exactly.
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


def _dist(a, b):
    return math.sqrt((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
                     + (a[2] - b[2]) ** 2)


def _dist_xz(a, b):
    return math.hypot(a[0] - b[0], a[2] - b[2])


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


def _by_zmode(scene, zmode):
    return [r for r in scene.by_id.values() if r["pc_zmode"] == zmode]


STAMP_PIECE_PRIMS = 3


def stamp_parity(scene, place):
    """The BULK stamp vs the per-prim writer it replaced (D102, 11.2 P1),
    re-proved on THIS build.

    The whole case goes through ONE `_stamp_bulk` call so a column shifted by
    one element differs on nearly every prim. Comparison is over 3.4's whole
    name set plus every warn name in the case - a non-warning element must
    read 0 where its neighbour reads 1.
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
    """4.6's segregation: how many pieces stayed packed.

    `expect_all` is the INSTANCING FLOOR (a straight rigid run must be 100 %
    packed); other cases record the count and let the baseline catch drift.
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


def _station_xs(rec):
    """Sorted distinct local x values of one built element."""
    out = []
    for x in sorted(set(round(v, 6) for v in rec["local"][0::3])):
        if not out or x - out[-1] > LOCAL_TOL:
            out.append(x)
    return out


def curvature_budget(scene, place):
    """D75 - the deviation the packed pieces are SPENDING, in metres.

    A PACKED piece may spend up to `bend_tol`; over that, the gate should have
    unpacked it. Value: [worst spent by a packed piece, worst over all].
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


def deform_gate(scene, place):
    """D100 - [worst deviation left PACKED, pieces over budget, of those
    still packed]. The last number may not move off zero.

    Never silent (unlike `packed_true_dev_m`): the middle number shows a case
    that stopped exercising anything as vacuous. Asserts the dangerous
    direction only - a piece that stays PACKED while its geometry disagrees
    with its transform SHIPS (D87, D100).
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

    Builds both answers (packed 4x4 vs `_deform_positions`) and never calls
    the budget; over `bend_tol` means packed-but-wrong, the direction that
    shipped (R = 55 m arc: 0.0091 m on the spine, 0.0327 m at the top corner,
    30/30 packed). Anchored/cut/sliced/rigid/replaced pieces are exempt.
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


def conform_camber(scene, expected=None, tol=0.05):
    """D55 - the angle between a piece's own up and the surface normal.
    Both read independently of the builder (built geometry + fresh ray cast).
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
    """[(eid, rec)] for every piece 4.3 ANCHORED on a leg - the corner slot,
    plus D40's displacement boundary piece (same assembly machinery).
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
    Assignment (nearest vertex, centroid sign vs bisector) is read off
    geometry, so a piece on the wrong leg cannot be filed under the right one.
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

    Per POINT, not per element: a piece cut at BOTH ends filed per element
    scored a 0.73 m phantom plane deviation. The SIDE comes from the centroid
    read against each bevel separately.
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
        # The candidates are the piece's OWN cut planes, not the nearest
        # vertex (0.028 m phantom deviation on a 12 m x 0.12 m figure).
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


def corner_face_mate(scene, expected=0.0, tol=TOL_M):
    """The two cut faces are the SAME polygon once slid together, compared
    point for point (coplanar-but-displaced passes the other corner checks).

    NOT always zero: the `reset` displacement policy leaves an e*sqrt(2) notch
    by design - measured 0.0424 m for the starter panel at 90 degrees - so the
    number is compared against `expected`; `extend` has to come back 0.
    """
    groups = _corner_caps(scene)
    if not groups:
        return _skip("corner_face_mate_m", "no mitered corners")
    worst, where, seen = 0.0, "", 0
    for bevel, sides in groups:
        pts = dict((side, [pt for pt, _rec in sides[side]])
                   for side in ("in", "out"))
        # `stepped` pieces step vertically by design at a pitched corner
        # (4.4's deferred flatten-under) - judged in plan, like corner_abut_m.
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
    """iToo's acceptance for Bevel Corner: the segment is "sliced to
    maintain its full length on the OUTSIDE of the corner". Measured off the
    built geometry, never through the solver's idea of where the plane went.
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
                # WORLD metres, not scale-invariant local x: D44's squeeze
                # read a clean 1.200 m on a block scaled to 0.776 m.
                outer = [_dot3(_sub3((wrl[i], wrl[i + 1], wrl[i + 2]),
                                     bevel.v), axis)
                         for i in range(0, len(loc), 3)
                         if loc[i + 2] * -bevel.side > 1e-6]
                if len(outer) < 2:
                    continue
                seen += 1
                got = max(outer) - min(outer)
                # The piece's OWN (possibly D44-squeezed) length, not the
                # nominal one; `corner_reach_m` asserts the squeeze itself.
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


def corner_breach(scene, tol=1e-4):
    """NO PIECE CROSSES A CORNER'S CUT PLANE UNCUT - the interpenetration
    detector, invisible to every other corner check and to `max_gap_m`.

    Two measured miter routes: corner module shorter than its own miter
    overhang (`e >= L_c`, any turn past 126.87 deg for the 0.16 m post; 0.031 m
    interpenetration, warning list empty), and a leg shorter than twice the
    overhang (1.5 m equilateral triangle). In BEND mode a butt joint crosses
    the bisector by design (D36 extended); `BUTT_BREACH_M` is the limit.
    Pieces far from the vertex are out of scope - a bisector is infinite.
    """
    bevels = [b for b in _bevels(scene) if b.mode == "miter"]
    worst, where, seen = 0.0, "", 0
    # THE BEND BRANCH (D36 extended): a dissolved vertex carries the same
    # plane a miter would cut on - NOTHING cuts on it, so measure it. A
    # SPANNED weld (one bent piece) is counted, not scored.
    excess = 0.0
    for v, n, cos_half, pieces, spanned in _welds(scene):
        if spanned:
            continue
        for side, _eid, rec in pieces:
            sign = 1.0 if side == "in" else -1.0
            d = max(sign * _dot3(_sub3(q, v), n) for q in _pts_of(rec))
            seen += 1
            # The allowed butt breach is `h*sin(t/2)` - SIN, not cos; the two
            # agree only at 90 deg. Verified at 30/60/90/120 deg to six
            # decimals (`AB_fillet`'s 0.005853 is `0.03*sin(11.25 deg)`).
            # Recorded number = physical breach; assertion = excess over it.
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
            # ONLY the two legs that meet here - scoring the whole scene read
            # a 0.73 m "breach" on a panel two corners away.
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


def _welds(scene, tol=1e-4):
    """One entry per DISSOLVED corner: (vertex, bisector normal, cos(turn/2),
    [(side, eid, rec)], spanned). `side` is "in"/"out" by arrival; `spanned`
    means ONE piece covers the vertex - no butt joint to measure (4.3).
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
                # A closed ring's seam is a weld at s = 0: read the arriving
                # side at `total`, or `n` is the outgoing tangent instead of
                # the bisector (seam scored 0.030 m against a phantom plane).
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
    """The piece's own across half-extent, in METRES of module local space
    (D20: across is local +Z; `pc_local` survives deform and clip).
    """
    loc = rec["local"]
    zs = [abs(loc[i + 2]) for i in range(0, len(loc), 3)]
    return max(zs) if zs else 0.0


def _pts_of(rec):
    w = rec["world"]
    return [(w[i], w[i + 1], w[i + 2]) for i in range(0, len(w), 3)]


UPRIGHT_ASPECT = 3.0    # height / widest footprint side in MODULE space.
                        # post 10.0, corner_post 8.1, panel 0.48, gate 0.66 -
                        # a gulf, not a tuned threshold.
TOUCH_M = 1e-3          # footprints this close are touching: above float32
                        # noise on P, far under deliberate spacing.
RESERVED_SLOTS = ("corner", "start", "end", "evenly")


def _reserved_slot(slot):
    """Slots that exist to put ONE piece at ONE place (D267)."""
    return slot in RESERVED_SLOTS or slot.startswith("marker:")


def _world_bbox(rec):
    w = rec.get("world") or []
    if len(w) < 3:
        return None
    xs, ys, zs = w[0::3], w[1::3], w[2::3]
    return (min(xs), max(xs), min(ys), max(ys), min(zs), max(zs))


def _is_upright(rec):
    """Aspect off `pc_local` - the MODULE's own space, so the fitting solve
    cannot reclassify a piece by scaling it (D270)."""
    loc = rec.get("local") or []
    if len(loc) < 3:
        return False
    xs, ys, zs = loc[0::3], loc[1::3], loc[2::3]
    foot = max(max(xs) - min(xs), max(zs) - min(zs))
    return foot > TOL_M and (max(ys) - min(ys)) >= UPRIGHT_ASPECT * foot


def _touching(a, b):
    """Footprints within TOUCH_M on both horizontal axes AND overlapping in Y
    (the Y clause only excludes genuinely different heights; concentric
    stacks score zero via `_pair_excess`, not this term).
    """
    return (a[0] - TOUCH_M <= b[1] and b[0] - TOUCH_M <= a[1]
            and a[4] - TOUCH_M <= b[5] and b[4] - TOUCH_M <= a[5]
            and a[2] - TOUCH_M <= b[3] and b[2] - TOUCH_M <= a[3])


def _pair_excess(a, b):
    """How much more ground the PAIR covers than the bigger of the two, per
    horizontal axis. Bounded by the smaller footprint, so it is a pillar
    width and never a run length."""
    return max(max(a[1], b[1]) - min(a[0], b[0]) - max(a[1] - a[0], b[1] - b[0]),
               max(a[5], b[5]) - min(a[4], b[4]) - max(a[5] - a[4], b[5] - b[4]))


def single_pillar(scene, expected=0.0, tol=2e-3):
    """`double_pillar_m` - ground a RESERVED piece and a touching UPRIGHT from
    a different slot cover beyond the wider of the two; 0.0 means every
    reserved piece stands alone. A distance in metres, PAIRWISE and bounded by
    one module's footprint (D270), never a cluster span.

    WHAT IT CANNOT SEE: a SEPARATED double pillar (reads as spacing); a
    doubling at or under the 2 mm `tol` (AABB-on-a-bend allowance; measured
    0.0015/0.0019 pass, 0.0021 fails); a MISSING/wrong-module pillar;
    doubling WITHIN one slot (`pc_warn_overflow` + `corner_face_mate_m` own
    that); two touching reserved non-uprights; duplication among non-reserved
    members. It FLAGS advertised compositions like `evenly:lamp` on a post
    (0.08 m measured) - `expected` is the escape hatch, every non-zero
    expectation named. PHASE-1 only: `run_2d_checks` does not call it.
    """
    boxes = []
    for eid, rec in scene.by_id.items():
        bb = _world_bbox(rec)
        if bb is None:
            continue
        slot = rec.get("pc_slot", "")
        res, up = _reserved_slot(slot), _is_upright(rec)
        if res or up:                    # anything else can never form a pair
            boxes.append((eid, rec, bb, res, up))
    if len(boxes) < 2:
        return _skip("double_pillar_m", "%d candidate members" % len(boxes))

    # D270: bucket the footprints - the O(n^2) sweep measured 33.9 s on
    # 16 667 uprights. Cell = WIDEST candidate, so a kit mixing 20 m walls
    # with 0.12 m posts degrades back towards the sweep (stated, not claimed
    # away).
    cell = max(max(b[1] - b[0], b[5] - b[4]) for _e, _r, b, _s, _u in boxes)
    cell = max(cell, TOL_M) + TOUCH_M
    grid = {}
    for k, (_e, _r, bb, _s, _u) in enumerate(boxes):
        for ix in range(int(math.floor((bb[0] - TOUCH_M) / cell)),
                        int(math.floor((bb[1] + TOUCH_M) / cell)) + 1):
            for iz in range(int(math.floor((bb[4] - TOUCH_M) / cell)),
                            int(math.floor((bb[5] + TOUCH_M) / cell)) + 1):
                grid.setdefault((ix, iz), []).append(k)

    worst, where, pairs, seen = 0.0, "", 0, set()
    for bucket in grid.values():
        for a in range(len(bucket)):
            for b in range(a + 1, len(bucket)):
                i, j = bucket[a], bucket[b]
                if i > j:
                    i, j = j, i
                if (i, j) in seen:
                    continue
                seen.add((i, j))
                _ei, ri, bi, si, ui = boxes[i]
                _ej, rj, bj, sj, uj = boxes[j]
                if ri.get("pc_slot", "") == rj.get("pc_slot", ""):
                    continue             # one slot is one deliberate rhythm
                if not ((si and uj) or (sj and ui)):
                    continue             # protected piece + upright doubler
                if not _touching(bi, bj):
                    continue
                pairs += 1
                excess = _pair_excess(bi, bj)
                if excess > worst or not where:
                    worst = excess
                    where = "%s+%s at (%.2f, %.2f)" % (
                        "%s:%s" % (ri.get("pc_slot", "?"),
                                   ri.get("pc_module", "?")),
                        "%s:%s" % (rj.get("pc_slot", "?"),
                                   rj.get("pc_module", "?")),
                        0.25 * (bi[0] + bi[1] + bj[0] + bj[1]),
                        0.25 * (bi[4] + bi[5] + bj[4] + bj[5]))
    return Result("double_pillar_m", abs(worst - expected) <= tol,
                  _round(worst, 6),
                  "%d candidates, %d doubled pairs, worst %s (expected %.4f)"
                  % (len(boxes), pairs, where or "none", expected))


def corner_abut(scene):
    """The seam between the corner assembly and the fill that runs up to it -
    the joint a slightly-wrong reserve opens, invisible to `max_gap_m`.
    Both points are read off built geometry.
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
        # PER SECTION: a leg with no default run has no abutment, it has
        # `pc_warn_overflow` (scene-wide scan misread a 1.5 m cross-leg gap).
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
                # ...of THIS corner only (far-corner scan misread 0.226 m).
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
            # `stepped` pieces step vertically by design on a pitched leg
            # (D24, 4.4) - measured in XZ like `max_gap_m`.
            metric = _dist_xz if far_stepped else _dist
            d = min(metric(far, e) for e in here)
            if d > worst:
                worst, where = d, "%s leg, %.3f m out" % (side, far_t)
    if not seen:
        return _skip("corner_abut_m", "no corner geometry")
    return Result("corner_abut_m", worst <= 2e-3, _round(worst, 6), where)


def stamp_calls_per_piece(build_fn, expect_max=1.0, name=None):
    """HOM per-element attribute writes per placed piece (11.2 P1). A COUNT,
    not a timing. RUN IT ON BOTH BRANCHES - restoring the per-prim writer on
    the deformed branch took arc_10 from 2.361 s to 19.854 s (8.4x) with all
    suites green. Ceiling 1.0 (was 15.0): P1 reads 0.005, the per-piece
    writer reads 14.005 and goes red.
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


def path_sample_calls_per_piece(build_fn, place_mod, expect_max=4.0,
                                name=None):
    """`Path.sample` calls per placed piece - pins P5R's `span_ends`
    threading (169 232 -> 69 232 calls on the 20 km packed row; dropping it
    is green everywhere while the fixture goes 3.0 -> 13.0 calls/piece).
    A COUNT, not a timing. Fixtures are surface-free, so `place.Path` is the
    only sampler; a conformed run would need `ConformPath.sample` counted too.
    """
    real = place_mod.Path.sample
    calls = {"n": 0}

    def counting(self, *a, **k):
        calls["n"] += 1
        return real(self, *a, **k)
    place_mod.Path.sample = counting
    try:
        _out, report = build_fn()
    finally:
        place_mod.Path.sample = real
    pieces = report["packed"] + report["deformed"]
    if not pieces:
        return _skip(name or "path_sample_calls_per_piece", "nothing was built")
    per = calls["n"] / float(pieces)
    return Result(name or "path_sample_calls_per_piece", per <= expect_max,
                  _round(per, 3), "%d calls, %d pieces (%d deformed, "
                  "ceiling %.1f)" % (calls["n"], pieces, report["deformed"],
                                     expect_max))


def curve_sample_scaling(curve_cls, expect="O(n)", samples=200,
                         cold_expect=None):
    """Does `Curve.sample` cost depend on VERTEX COUNT - 11.2 P2 (pre-fix:
    3.2 us at 10 verts vs 8 218 us at 20 001). The VALUE is the complexity
    class, not microseconds - a label moves once, a timing churns the
    baseline; raw numbers ride in `detail`. The COLD reading pins table
    construction staying LINEAR (a rebuild-per-segment regression reads
    quadratic, invisible to the warm reading). `cold_expect=None` keeps the
    old one-value shape.
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


def conform_cache_per_element(build_fn, conform_mod, expect_max=30.0,
                              name=None):
    """Entries `ConformPath._cache` holds per placed element - P5's cost
    (unbounded memo: 53 861 entries / 24 MB on one 2 km curve). Dropping gap
    midpoints from the enumeration read 18.7 -> 17.6 here and -191 MB on 300
    conformed streets; the ceiling guards the memo growing unnoticed, not the
    exact figure.
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
    nm = name or "conform_cache_per_element"
    if not made:
        return _skip(nm, "no surface")
    entries = sum(len(p._cache) for p in made)
    pieces = report["packed"] + report["deformed"]
    if not pieces:
        return _skip(nm, "nothing was built")
    per = entries / float(pieces)
    return Result(nm, per <= expect_max,
                  _round(per, 3), "%d entries over %d elements on %d paths "
                  "(ceiling %.0f)" % (entries, pieces, len(made), expect_max))


def station_share_hit_rate(build_fn, place_mod, conform_mod,
                           expect_max_misses=0.0):
    """Does P3's station cache actually get HIT (measured 2 691 hits, 0
    misses over 88 cases) - a key drifting one ULP is still correct with the
    whole win silently gone. Counted, not timed: every `sample` inside
    `_deform_positions` is a miss. `[stations offered, misses per piece]` -
    the first is the liveness the second cannot report.
    """
    state = {"depth": 0, "offered": 0, "miss": 0, "pieces": 0}
    real_dp = place_mod._deform_positions
    reals = [(place_mod.Path, place_mod.Path.sample)]
    if conform_mod is not None:
        reals.append((conform_mod.ConformPath, conform_mod.ConformPath.sample))

    def wrapped(src, proto, path, s0_flat, scale, zmode, remap,
                tilt=False, base_y=None, band=None, samples=None,
                yscale=1.0):
        state["pieces"] += 1
        state["offered"] += len(samples or ())
        state["depth"] += 1
        try:
            return real_dp(src, proto, path, s0_flat, scale, zmode, remap,
                           tilt, base_y, band, samples, yscale)
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
    Materialising all fifteen columns at once cost +97 MB (61 %) on the
    340 000-prim deformed row; measured 49.5 MB vs 7.6 MB expanded one at a
    time. `tracemalloc` is deterministic, and the fixture is synthetic (the
    writer's own shape) so it cannot drift with the kit.
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


def path_read_direction_m(place_mod, curve_cls, expect_max=1e-12):
    """How far apart `Path.sample(s)` and `Path.sample(s, forward=False)`
    land AT A VERTEX - P3's "bit-identical" claim, made a measurement over
    seven curve shapes. Worst measured |dP|: 4.4e-16 m here, 7.1e-15 m on an
    independent sweep - double-precision ULP, seven orders below `bend_tol`.
    Ceiling 1e-12 m: a REAL divergence is metres, not ULPs.
    `[vertex arclengths read, how many differ]`, worst in `detail`.
    """
    made = {
        "axis": [(2.0 * i, 0.0, 0.0) for i in range(40)],
        "irregular": [(i * 3.1 + 0.37 * math.sin(i), 0.13 * i * i % 7.3 - 3.1,
                       -1.7 * i + 0.9 * math.cos(i * 1.7)) for i in range(60)],
        "diagonal": [(i * 1.7320508, i * 0.5772, i * 2.71828)
                     for i in range(30)],
        "sub_mm": [(0.0, 0.0, 0.0), (1e-3, 2e-3, 3e-3), (0.5, -0.25, 0.125)],
        "hairpin": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (0.0, 0.0, 1e-6)],
        "climb": [(i * 2.0, i * 0.37, i * 0.11) for i in range(25)],
        "closed": [(0.0, 0.0, 0.0), (10.0, 0.0, 0.0), (10.0, 0.0, 10.0),
                   (0.0, 0.0, 10.0)],
    }
    total = differ = 0
    worst, where = 0.0, ""
    for name, pts in sorted(made.items()):
        curve = curve_cls(name, pts)
        curve.closed = name == "closed"
        path = place_mod.Path(curve)
        for sv in path.vertex_s:
            f = path.sample(sv)[0]
            b = path.sample(sv, forward=False)[0]
            d = math.sqrt(sum((f[i] - b[i]) ** 2 for i in range(3)))
            total += 1
            differ += 1 if d else 0
            if d > worst:
                worst, where = d, "%s at s=%.6f" % (name, sv)
    return Result("path_read_direction_m", worst <= expect_max,
                  [total, differ],
                  "worst |dP| %.3e m %s (ceiling %.0e - it is ULP, not zero)"
                  % (worst, where and "on " + where, expect_max))


def build_out_keeps_upstream_stamps(build_fn, place_mod):
    """`build(out=...)`'s `base` machinery, exercised - both branches were
    dead as tested (no caller passes `out=`).

    HOM trap found mutation-testing this: `setPrimStringAttribValues` treats
    `""` as LEAVE UNCHANGED, so a blanked string head is invisible - the
    proving mutation corrupts the head instead. `[kept, stamped]`.
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


def conform_parity(scene, tol_m=1e-9, tol_n=1e-9):
    """11.2 P5 / 11.3 rule 1: the batched `ray` and per-query
    `hou.Geometry.intersect` answer every drop this case made THE SAME -
    every key the build cached is re-dropped through the Python path.

    `drop_many` reads the verb's DISTANCE, not its float32 POSITION, and
    rebuilds the drop from the double query (D111) - which is why the
    tolerance can honestly stay at 1e-09 m (position route: 2.4e-07 m near
    origin, 6.1e-05 m at 20 km; `ray_verb_semantics`' dirty_ramp trials tell
    the routes apart). A tilted `conform_axis` is not batched at all (D111)
    and reports as a skip. `[max |dP| m, hit mismatches, max |dN|]`.
    """
    paths = scene.case.get("paths") or []
    live = [p for p in paths if getattr(p, "_cache", None)]
    if not live:
        return _skip("conform_parity", "no conformed path")
    worst_p = worst_n = 0.0
    mism = 0
    where = ""
    total = 0
    for path in live:
        surf = path.surface
        # BOTH paths asked at the same `p` - comparing against the stored
        # value would measure the key's rounding (3.7e-09 m), not the drop.
        qs = [path.base.sample(s, forward)[0]
              for (s, forward) in sorted(path._cache)]
        batched = surf.drop_many(qs)
        if batched is None:
            if not surf.batchable:
                return _skip("conform_parity", "a tilted `conform_axis` is "
                             "not batched (D111) - the per-query path is the "
                             "only implementation here")
            return Result("conform_parity", False, None,
                          "the `ray` verb declined on this case")
        total += len(qs)
        for q, got in zip(qs, batched):
            ref = surf.drop(q)
            dp = max(abs(got[0][k] - ref[0][k]) for k in range(3))
            dn = max(abs(got[1][k] - ref[1][k]) for k in range(3))
            if got[2] != ref[2]:
                mism += 1
                if not where:
                    where = "hit flag %r != %r at %r" % (got[2], ref[2], q)
            if dp > worst_p and mism == 0:
                where = "worst |dP| %.3e m at %r: %r vs %r" % (dp, q, got[0],
                                                               ref[0])
            worst_p, worst_n = max(worst_p, dp), max(worst_n, dn)
    return Result("conform_parity",
                  worst_p <= tol_m and worst_n <= tol_n and mism == 0,
                  [_round(worst_p, 9), mism, _round(worst_n, 9)],
                  where or "%d drops over %d paths, bit-identical"
                  % (total, len(live)))


def conform_prefetch_hit_rate(build_fn, conform_mod, expect_max_fallback=0.2,
                              expect_min_used=1.0, name=None):
    """11.2 P5's tripwire, in BOTH directions: is the batch serving the
    drops, and is it fetching drops nobody wants? `fallback/batched` alone is
    0.0 by construction when the batch over-fetches (gap midpoints measured
    0 % consumed on a 2 km fence, 9 % on 300 streets, 47 % of every batch);
    `used/batched` is the number that says so. `[used/batched,
    fallback/batched, batched]`, both ceilings per call - the second is a
    property of the FIXTURE.
    """
    made = []
    asked = set()
    real = conform_mod.ConformPath.__init__
    real_at = conform_mod.ConformPath._at

    def spy(self, *a, **k):
        real(self, *a, **k)
        made.append(self)

    def spy_at(self, s, forward=True):
        asked.add((id(self), round(float(s), 9), bool(forward)))
        return real_at(self, s, forward)
    conform_mod.ConformPath.__init__ = spy
    conform_mod.ConformPath._at = spy_at
    try:
        build_fn()
    finally:
        conform_mod.ConformPath.__init__ = real
        conform_mod.ConformPath._at = real_at
    nm = name or "conform_prefetch_hit_rate"
    if not made:
        return _skip(nm, "no surface")
    batched = sum(p.batched for p in made)
    fell = sum(p.fallback for p in made)
    if not batched:
        return Result(nm, False, [-1.0, -1.0, 0],
                      "the prefetch filled NOTHING; %d keys went to the "
                      "per-query path" % fell)
    # a batched key is USED when `_at` was asked for it; `fallback` counts the
    # keys `_at` had to drop itself, so `asked - fallback` is what the batch
    # actually served.
    used = len(asked) - fell
    ratio_used = used / float(batched)
    ratio_fell = fell / float(batched)
    return Result(nm, ratio_used >= expect_min_used
                  and ratio_fell <= expect_max_fallback,
                  [_round(ratio_used, 4), _round(ratio_fell, 4), batched],
                  "%d of %d batched keys used (floor %.2f), %d fallback keys "
                  "(ceiling %.2f)"
                  % (used, batched, expect_min_used, fell,
                     expect_max_fallback))


def ray_verb_semantics(conform_mod, cases_mod):
    """The `ray` verb IS `hou.Geometry.intersect`, on the surfaces that could
    tell them apart - 11.2 P5's load-bearing measurement, standing up.

    The eight analytic trials are float32-exact by construction; only
    `dirty_ramp` / `dirty_ramp_20km` can tell the DISTANCE reading from the
    POSITION one (restore the position route: 2.4e-07 / 6.1e-05 m red, D111).
    `tilted_axis_declines` asserts the GATE: on a tilted axis the divergence
    is along the ray (1.9e-06 m / 1.5e-05 m), so `Surface.batchable` declines
    and the per-query path serves it alone. The verb's one real difference -
    it hands back the polygon's own normal - is re-added in `drop_many` as
    D52's flip. Trials cover: D70 bridge deck, unequal-standoff deck (D113 -
    equidistant hits cannot see `bidirectionalresult`), exact tie, D52
    reversed winding + from-below, D53 hole/edge, coincident sheets, camber,
    tent. `[max |dP| m, hit-flag mismatches, max |dN|]`, all asserted at
    exactly 0.
    """
    axis = (0.0, -1.0, 0.0)
    S = cases_mod.surface

    def deck():
        g = S(lambda x, z: -2.0, x0=-2.0, x1=24.0, z0=-4.0, z1=4.0,
              nx=26, nz=4)
        g.merge(S(lambda x, z: 2.0, x0=4.0, x1=12.0, z0=-4.0, z1=4.0,
                  nx=8, nz=4))
        return g

    def deck_offcentre():
        """Deck at an UNEQUAL standoff (D113): `deck()`'s hits are
        equidistant, so it cannot see `bidirectionalresult` - here nearest is
        the ground and farthest the deck, 5 m apart.
        """
        g = S(lambda x, z: -2.0, x0=-2.0, x1=24.0, z0=-4.0, z1=4.0,
              nx=26, nz=4)
        g.merge(S(lambda x, z: 3.0, x0=4.0, x1=12.0, z0=-4.0, z1=4.0,
                  nx=8, nz=4))
        return g

    def tie():
        g = S(lambda x, z: 2.0, x0=-2.0, x1=24.0, z0=-4.0, z1=4.0,
              nx=26, nz=4)
        g.merge(S(lambda x, z: -2.0, x0=-2.0, x1=24.0, z0=-4.0, z1=4.0,
                  nx=26, nz=4))
        return g

    def coincident():
        g = S(cases_mod.ramp_x)
        g.merge(S(cases_mod.ramp_x))
        return g

    def dirty_h(x, z):
        """An IRRATIONAL slope, so the drop is not a float32 number."""
        return 0.2718281828 * x + 0.0314159 * z

    def dirty(at=0.0):
        g = S(lambda x, z, _a=at: dirty_h(x - _a, z),
              x0=at - 3.1, x1=at + 23.7, z0=-5.3, z1=6.1, nx=27, nz=11)
        return g

    def dirty_q(at=0.0, y=7.0):
        """...and DIRTY stations, so the query is not one either."""
        return [(at + 0.1234567 + k * 0.3719, y, 0.0517 * math.sin(k))
                for k in range(60)]

    row = lambda y, n=48, step=0.5: [(k * step, y, 0.0) for k in range(n)]
    trials = (
        ("dirty_ramp", dirty(), dirty_q()),
        ("dirty_ramp_20km", dirty(20000.0), dirty_q(20000.0, 5100.0)),
        ("bridge_deck", deck(), row(0.0, 49)),
        ("deck_offcentre", deck_offcentre(), row(0.0, 49)),
        ("exact_tie", tie(), [(1.0, 0.0, 0.0), (5.5, 0.0, 0.0),
                              (11.25, 0.0, 0.0), (20.0, 0.0, 0.0)]),
        ("flipped_winding", S(cases_mod.ramp_x, flip=True), row(3.0, 20, 1.0)),
        ("hole_and_edge", S(cases_mod.ramp_x, x0=-2.0, x1=12.0, nx=14,
                            holes=((8, 5), (8, 6), (9, 5), (9, 6))), row(3.0)),
        ("coincident_sheets", coincident(), row(3.0)),
        ("from_below", S(cases_mod.ridge), row(-5.0)),
        ("camber", S(cases_mod.camber_z),
         [(k * 0.5, 3.0, z) for k in range(24) for z in (-2.0, 0.0, 2.0)]),
        ("tent", S(cases_mod.tent, nx=2, nz=1), row(4.0, 96, 0.25)),
    )
    worst_p = worst_n = 0.0
    mism = 0
    where = ""
    for label, geo, pts in trials:
        surf = conform_mod.Surface(geo, axis)
        batched = surf.drop_many(pts)
        if batched is None:
            return Result("ray_verb_semantics", False, None,
                          "the `ray` verb declined on %s" % label)
        for p, got in zip(pts, batched):
            ref = surf.drop(p)
            dp = max(abs(got[0][k] - ref[0][k]) for k in range(3))
            dn = max(abs(got[1][k] - ref[1][k]) for k in range(3))
            if got[2] != ref[2]:
                mism += 1
                if not where:
                    where = "%s: hit %r != %r at %r" % (label, got[2],
                                                        ref[2], p)
            if dp > worst_p or dn > worst_n:
                if not where:
                    where = "%s: |dP| %.3e |dN| %.3e at %r" % (label, dp,
                                                               dn, p)
            worst_p, worst_n = max(worst_p, dp), max(worst_n, dn)
    # ...and the gate itself: a tilted axis must DECLINE rather than answer.
    tilted = conform_mod.Surface(dirty(), (0.2, -1.0, 0.13))
    declined = (not tilted.batchable) and tilted.drop_many(dirty_q()) is None
    if not declined and not where:
        where = ("a tilted `conform_axis` was BATCHED - D111 says it cannot "
                 "be, at 1.9e-06 m on this very surface")
    return Result("ray_verb_semantics",
                  worst_p == 0.0 and worst_n == 0.0 and mism == 0 and declined,
                  [_round(worst_p, 12), mism, _round(worst_n, 12)],
                  where or "%d points over %d surfaces, bit-identical; a "
                  "tilted axis declines"
                  % (sum(len(t[2]) for t in trials), len(trials)))


def prims_wrappers_built(build_fn, hou_mod, expect_max=64, name=None):
    """How many `hou.Prim` WRAPPERS a build materialises through
    `geo.prims()` (the surviving `len(geo.prims())` in `Surface.__init__`
    built 2.3 M wrappers on 300 streets - 0.530 s of a 3.46 s row, 15 %).
    The value is WRAPPERS, not calls: the three legitimate loops are bounded
    by the kit and the input, which a ceiling can be set against.
    """
    real = hou_mod.Geometry.prims
    built = [0]

    def spy(self, *a, **k):
        got = real(self, *a, **k)
        built[0] += len(got)
        return got
    hou_mod.Geometry.prims = spy
    try:
        build_fn()
    finally:
        hou_mod.Geometry.prims = real
    return Result(name or "prims_wrappers_built", built[0] <= expect_max,
                  built[0], "%d `hou.Prim` wrappers materialised in one build "
                  "(ceiling %d)" % (built[0], expect_max))


def ray_executions_per_build(build_fn, hou_mod, expect_max=1, name=None):
    """How many `ray` verb EXECUTIONS one build takes (11.2 P5, corrected).
    Each execution carries a fixed cost scaling with the SURFACE (0.34 ms at
    5 022 prims, 2.25 ms at 80 352, vs ~2 us marginal per query): per-curve
    batching read 0.94-0.99x on 300 streets, once-per-build 1.20-1.39x.
    A count, not a time; counted through `Surface.drop_many`.
    """
    from polyfactory.polychain import conform as _conform
    real = _conform.Surface.drop_many
    calls = [0]

    def spy(self, pts):
        calls[0] += 1
        return real(self, pts)
    _conform.Surface.drop_many = spy
    try:
        build_fn()
    finally:
        _conform.Surface.drop_many = real
    return Result(name or "ray_executions_per_build", calls[0] <= expect_max,
                  calls[0], "%d `ray` executions in one build (ceiling %d)"
                  % (calls[0], expect_max))


def verb_executions_per_build(build_fn, place_mod, expect_max, name=None):
    """COMPILED SOP EXECUTIONS per build, per verb name - `clip`/`polyfill`
    carry the same per-execute fixed cost as `ray`, and phase 2 multiplies
    them by ROW COUNT (a 100-building district: 12 800 executions vs the 100
    `ray` calls). Sorted [name, count] so a new verb is visible as a NAME.
    """
    import hou as _hou
    real = _hou.SopVerb.execute
    counts = {}
    live = {}

    def spy(self, *a, **k):
        key = live.get(id(self))
        counts[key or "?"] = counts.get(key or "?", 0) + 1
        return real(self, *a, **k)
    for vname, verb in getattr(place_mod, "_VERBS", {}).items():
        live[id(verb)] = vname
    _hou.SopVerb.execute = spy
    try:
        build_fn()
        # verbs are cached lazily, so a name first reached during the build
        # would otherwise be counted as "?" - relabel and re-key once.
        for vname, verb in getattr(place_mod, "_VERBS", {}).items():
            live.setdefault(id(verb), vname)
    finally:
        _hou.SopVerb.execute = real
    got = [[k, counts[k]] for k in sorted(counts)]
    total = sum(counts.values())
    return Result(name or "verb_executions_per_build", total <= expect_max,
                  got, "%d compiled SOP executions in one build (ceiling %d)"
                  % (total, expect_max))


def polyfill_appends_its_patches(place_mod, hou_mod):
    """The verb property `clip_plane`'s bulk cap tag rests on (P7): polyfill
    appends its created prims contiguously at the tail. Re-probed here -
    three disjoint boxes cut by one plane, tail range vs the plane test.
    """
    from polyfactory.polychain import kit as _kit
    cat = hou_mod.sopNodeTypeCategory()
    src = hou_mod.Geometry()
    for z in (0.0, 5.0, 10.0):
        box = hou_mod.Geometry()
        _kit.box_mesh(box, 0.0, 3.0, z, z + 3.2, -0.15, 0.15, 2)
        src.merge(box)
    cut = hou_mod.Geometry()
    clip = cat.nodeVerb("clip")
    clip.setParms({"origin": (1.7, 0.0, 0.0), "dir": (1.0, 0.0, 0.0),
                   "clipop": 1})
    clip.execute(cut, [src])
    n_cut = cut.intrinsicValue("primitivecount")
    filled = hou_mod.Geometry()
    pfill = cat.nodeVerb("polyfill")
    pfill.setParms({"fillmode": 0})
    pfill.execute(filled, [cut])
    n_all = filled.intrinsicValue("primitivecount")
    tail = list(range(n_cut, n_all))
    plane = [prim.number() for prim in filled.prims()
             if prim.points() and all(abs(p.position()[0] - 1.7) <= 1e-5
                                      for p in prim.points())]
    ok = bool(tail) and sorted(plane) == tail
    return Result("polyfill_appends_its_patches", ok, [len(tail), len(plane)],
                  "%d patches at the tail, %d found by the plane test%s"
                  % (len(tail), len(plane),
                     "" if ok else " - THE BULK CAP TAG IS NOW WRONG"))


def points_wrappers_built(build_fn, hou_mod, expect_max=8, name=None):
    """The same question for `hou.Point` wrappers (the group read in
    `drop_many` cost 5x the verb it decorated: 0.0081 s vs 0.0016 s, 306 600
    wrappers on the street row; `hitprim` via `useprimnumattrib` answers it
    for free - `putdist` + `dist != 0` is NOT a substitute, it calls the 40
    zero-distance hits misses). Both wrapper sources are counted.
    """
    real_g = hou_mod.Geometry.points
    real_p = hou_mod.PointGroup.points
    built = [0]

    def spy_g(self, *a, **k):
        got = real_g(self, *a, **k)
        built[0] += len(got)
        return got

    def spy_p(self, *a, **k):
        got = real_p(self, *a, **k)
        built[0] += len(got)
        return got
    hou_mod.Geometry.points = spy_g
    hou_mod.PointGroup.points = spy_p
    try:
        build_fn()
    finally:
        hou_mod.Geometry.points = real_g
        hou_mod.PointGroup.points = real_p
    return Result(name or "points_wrappers_built", built[0] <= expect_max,
                  built[0], "%d `hou.Point` wrappers materialised in one "
                  "build (ceiling %d)" % (built[0], expect_max))


def wrapper_reads(build_fn, hou_mod, expect_max, name=None):
    """The hole the other four tripwires left: READS through a wrapper
    (`Prim.points` by length, `Point.position`, `*.attribValue`) - a phase-2
    district read 0 on `points_wrappers_built` while materialising 159 242
    points via `Prim.points` and calling `Point.position` 220 488 times.
    The ceiling is a CLASS boundary, not a floor.
    """
    real_pp = hou_mod.Prim.points
    real_pos = hou_mod.Point.position
    real_pav = hou_mod.Point.attribValue
    real_rav = hou_mod.Prim.attribValue
    got = [0]

    def spy_pp(self, *a, **k):
        out = real_pp(self, *a, **k)
        got[0] += len(out)
        return out

    def spy_pos(self, *a, **k):
        got[0] += 1
        return real_pos(self, *a, **k)

    def spy_pav(self, *a, **k):
        got[0] += 1
        return real_pav(self, *a, **k)

    def spy_rav(self, *a, **k):
        got[0] += 1
        return real_rav(self, *a, **k)
    hou_mod.Prim.points = spy_pp
    hou_mod.Point.position = spy_pos
    hou_mod.Point.attribValue = spy_pav
    hou_mod.Prim.attribValue = spy_rav
    try:
        build_fn()
    finally:
        hou_mod.Prim.points = real_pp
        hou_mod.Point.position = real_pos
        hou_mod.Point.attribValue = real_pav
        hou_mod.Prim.attribValue = real_rav
    return Result(name or "wrapper_reads", got[0] <= expect_max, got[0],
                  "%d wrapper reads (`Prim.points` + `Point.position` + "
                  "`*.attribValue`) in one build (ceiling %d)"
                  % (got[0], expect_max))
def rows_wrappers_built(build_fn, hou_mod, expect_max=0, name=None):
    """11.9 rule 1 on the row emitter: wrapper attribute WRITES during row
    emission. Ceiling 0, meant to stay 0 - every row attribute goes in as one
    `setPrim*AttribValues` over the whole stream.
    """
    real_p = hou_mod.Prim.setAttribValue
    real_pt = hou_mod.Point.setAttribValue
    calls = [0]

    def spy_p(self, *a, **k):
        calls[0] += 1
        return real_p(self, *a, **k)

    def spy_pt(self, *a, **k):
        calls[0] += 1
        return real_pt(self, *a, **k)
    hou_mod.Prim.setAttribValue = spy_p
    hou_mod.Point.setAttribValue = spy_pt
    try:
        build_fn()
    finally:
        hou_mod.Prim.setAttribValue = real_p
        hou_mod.Point.setAttribValue = real_pt
    return Result(name or "rows_wrappers_built", calls[0] <= expect_max,
                  calls[0], "%d wrapper attribute writes during row emission "
                  "(ceiling %d)" % (calls[0], expect_max))


# --- phase 2 (the 2D array) -------------------------------------------------

CELL_STRINGS = ("pc_cell", "pc_yclass", "pc_array")


def _cells(geo):
    """[{pc_cell, pc_yclass, pc_array, pc_row, pc_elem_id, ...}] per element."""
    out, order = {}, []
    if geo.findPrimAttrib("pc_cell") is None:
        return []
    for prim in geo.prims():
        try:
            eid = prim.attribValue("pc_elem_id")
        except hou.OperationFailed:
            continue
        if eid in out:
            continue
        rec = {"pc_elem_id": eid}
        for name in CELL_STRINGS:
            try:
                rec[name] = prim.attribValue(name)
            except hou.OperationFailed:
                rec[name] = ""
        for name in ("pc_row", "pc_section", "pc_corner_cut", "pc_deformed",
                     "pc_clipped"):
            try:
                rec[name] = int(prim.attribValue(name))
            except (hou.OperationFailed, TypeError, ValueError):
                rec[name] = -1
        try:
            rec["pc_module"] = prim.attribValue("pc_module")
        except hou.OperationFailed:
            rec["pc_module"] = ""
        out[eid] = rec
        order.append(eid)
    return [out[e] for e in order]




def clip_stamp(scene):
    """7.3.3's `pc_clipped` (0/1): [elements on a clipped row, total]. Under
    D137 the clip is a SPAN, not a cull; NOT 7.3.1's per-module `pc_clip`
    policy (arrives with P2-7). The assertion is the TRANSFER - every element
    must match its row curve's `pc_clipped` - because `ok = area or n == 0`
    was vacuously True on the only builds where the stamp can be 1.
    """
    recs = _cells(scene.geo)
    if not recs:
        return _skip("clip_stamp", "no pc_cell - a 1D build")
    n = sum(1 for r in recs if r.get("pc_clipped") == 1)
    curve = scene.case.get("curve")
    want = {}
    if curve is not None and curve.findPrimAttrib("pc_clipped") is not None:
        rows = list(curve.primIntAttribValues("pc_row"))
        clip = list(curve.primIntAttribValues("pc_clipped"))
        for y, c in zip(rows, clip):
            want[y] = max(want.get(y, 0), int(c))
    bad = sum(1 for r in recs
              if r["pc_row"] in want
              and int(r.get("pc_clipped") or 0) != want[r["pc_row"]])
    ok = bad == 0 and (scene.frame is not None or n == 0)
    return Result("clip_stamp", ok, [n, len(recs)],
                  "%d of %d elements on a clipped row%s"
                  % (n, len(recs),
                     "" if ok else
                     " - %d disagree with their row curve" % bad if bad
                     else " - but this is not an area build"))


# --- PC-G6: the clipped area (7.6 / P2-7) -----------------------------------

def _pip(poly, x, y):
    """Even-odd point-in-polygon, WRITTEN HERE ON PURPOSE. `clip_nesting`
    judges the artist's four drawings directly, so it must not borrow the
    builder's own containment test - a `nest` that mislabels a hole would
    otherwise agree with itself."""
    inside = False
    n = len(poly)
    for i in range(n):
        (ax, ay), (bx, by) = poly[i][:2], poly[(i + 1) % n][:2]
        if (ay > y) != (by > y) and \
                x < ax + (bx - ax) * (y - ay) / (by - ay):
            inside = not inside
    return inside


def _seg_dist(px, py, ax, ay, bx, by):
    dx, dy = bx - ax, by - ay
    d2 = dx * dx + dy * dy
    t = 0.0 if d2 <= 0.0 else max(
        0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / d2))
    return math.hypot(px - ax - dx * t, py - ay - dy * t)


def _by_array(scene):
    """[(element, frame, region)] - each element beside the clip data of its
    OWN array, matched on the `<arrayId>` half of `pc_curve_id`."""
    arrays = scene.case.get("clip_arrays") or {}
    out = []
    for rec in elements(scene.geo):
        ent = arrays.get(str(rec.get("pc_curve_id", "")).split("#")[0])
        if ent is not None:
            out.append((rec, ent[0], ent[1]))
    return out


def _centre(rec):
    w = rec.get("world") or [0.0, 0.0, 0.0]
    n = max(len(w) // 3, 1)
    return (sum(w[0::3]) / n, sum(w[1::3]) / n, sum(w[2::3]) / n)


def clip_inside_m(scene, tol=1e-2):
    """PC-G6 condition 1: [worst metres a delivered point lies OUTSIDE the
    clip region, points measured]. `bend_tol` is 0.01 m.

    Every point of every delivered element - not a bbox, and not the plan -
    projected into its own array's chart and asked whether it is inside the
    include region and outside every exclude region. A piece that overhangs
    the line, a bay built inside a hole and a slice that did not actually cut
    all read as the same number, which is the distance it pokes out.

    WHAT IT CANNOT SEE: (a) a hole that is EMPTY when it should be filled -
    that is `clip_nesting`, and it is the failure this one is blind to by
    construction, because nothing missing has a point to measure; (b) whether
    the region itself is right: the region here is the one the builder used,
    so this proves agreement between plan and geometry, not that the plan read
    the artist's drawing correctly. `clip_nesting` judges the drawing.
    """
    pairs = _by_array(scene)
    if not pairs:
        return _skip("clip_inside_m", "no clip_arrays - not a clipped build")
    worst, n = 0.0, 0
    for rec, frame, region in pairs:
        w = rec["world"]
        for i in range(0, len(w), 3):
            x, y = frame.local((w[i], w[i + 1], w[i + 2]))
            n += 1
            if region.inside(x, y):
                continue
            d = min(_seg_dist(x, y, p[i2][0], p[i2][1],
                              p[(i2 + 1) % len(p)][0],
                              p[(i2 + 1) % len(p)][1])
                    for p in region.polys for i2 in range(len(p)))
            worst = max(worst, d)
    return Result("clip_inside_m", worst <= tol and n > 0, _round(worst),
                  "%d points, worst %.4f m outside the region (tol %.3f)"
                  % (n, worst, tol))


def clip_nesting(scene, hole=1, island=2):
    """PC-G6 condition 5: [elements centred in the HOLE, elements centred on
    the ISLAND inside it]. 0 and non-zero is the pass.

    Judged on the artist's own sub-splines by index - loop `hole` must contain
    nothing, loop `island` (nested inside it, even-odd depth 2) must contain
    something - with this file's own point-in-polygon, so a `nest` that gave a
    loop the wrong polarity cannot pass by agreeing with itself.

    ⚠️ MEASURED IN THE WORLD (x, y) CHART, which is the plan chart only
    because PC-G6's fixture is drawn flat in the world XY plane. A clipped
    array authored on a tilted plane would need the frame; the gate figure
    does not, and the simpler measurement is the one that cannot be wrong
    about the frame.
    """
    loops = scene.case.get("clip_loops") or []
    if len(loops) <= max(hole, island):
        return _skip("clip_nesting", "no nested clip loops in this case")
    n_hole = n_island = 0
    for rec in elements(scene.geo):
        cx, cy, _cz = _centre(rec)
        if _pip(loops[island], cx, cy):
            n_island += 1
        elif _pip(loops[hole], cx, cy):
            n_hole += 1
    return Result("clip_nesting", n_hole == 0 and n_island > 0,
                  [n_hole, n_island],
                  "%d element(s) inside the hole, %d on the island inside it"
                  % (n_hole, n_island))


def clip_mode_override(default_case, override_case, loop=1, island=2):
    """7.6's per-sub-spline `pc_clip_mode`: [elements in the hole by even-odd,
    elements in it once it is marked `include`]. 0 then non-zero is the pass.

    RC's `None` hierarchy mode, per spline instead of globally, and the only
    check that runs the whole `pc_clip_mode` prim attribute from the artist's
    geometry through `nest` to the built pieces. Without it the override is a
    branch nothing executes.

    ⚠️ THE ISLAND IS SUBTRACTED, and leaving it in made the check read
    [2, 10] and fail: the two pieces on the depth-2 island are geometrically
    inside the hole, so "elements in loop 1" counts them whatever the
    override does. The question is what lies in the hole and NOT on the
    island.

    WHAT IT CANNOT SEE: `exclude` on a loop even-odd already excludes - the
    override and the default agree there, so only the polarity that FLIPS is
    evidence.
    """
    loops = default_case.get("clip_loops") or []
    if len(loops) <= max(loop, island):
        return _skip("clip_mode_override", "no nested clip loop to override")

    def inside(case):
        return sum(1 for rec in elements(case["out"])
                   if _pip(loops[loop], *_centre(rec)[:2])
                   and not _pip(loops[island], *_centre(rec)[:2]))
    a, b = inside(default_case), inside(override_case)
    return Result("clip_mode_override", a == 0 and b > 0, [a, b],
                  "%d element(s) in loop %d by even-odd, %d once it says "
                  "include" % (a, loop, b))


def clip_preserve(scene):
    """D126's `preserve`, and the array-decides half of its three-state
    pattern: [worst metres a piece overhangs the boundary, pieces removed].
    Non-zero and zero is the pass.

    `preserve` is "kept whole and may overhang", so the number `clip_inside_m`
    requires to be ZERO under `remove`/`slice` must be POSITIVE here - the
    same measurement read the other way round, which is the only way to tell
    "preserve works" from "nothing straddled". And nothing may be removed: a
    removal under `preserve` is `remove` leaking through.

    ⚠️ THE KIT SAYS NOTHING ABOUT CLIPPING IN THIS CASE (`pc_clip = -1`), so
    this is also the only run that takes `module.clip >= 0`'s false branch.
    PC-G6's own fixture pins every module at `slice`, which left both the
    array-decides path and the whole `preserve` policy as code nothing
    executed.

    WHAT IT CANNOT SEE: how far an overhang is ALLOWED to go. `preserve` has
    no bound by definition; what bounds it is the row span, and that is
    `row_spans`' own per-interval rule (FQ_area_preserve).
    """
    pairs = _by_array(scene)
    if not pairs:
        return _skip("clip_preserve", "no clip_arrays - not a clipped build")
    worst = 0.0
    for rec, frame, region in pairs:
        w = rec["world"]
        for i in range(0, len(w), 3):
            x, y = frame.local((w[i], w[i + 1], w[i + 2]))
            if region.inside(x, y):
                continue
            worst = max(worst, min(
                _seg_dist(x, y, p[k][0], p[k][1],
                          p[(k + 1) % len(p)][0], p[(k + 1) % len(p)][1])
                for p in region.polys for k in range(len(p))))
    out = int((scene.case.get("report") or {}).get("clipped_out", 0))
    return Result("clip_preserve", worst > 1e-3 and out == 0,
                  [_round(worst), out],
                  "worst overhang %.4f m, %d piece(s) removed" % (worst, out))


def clip_caps_closed(scene):
    """PC-G6 condition 2: [open boundary edges on clip-cut elements, cut
    elements, cut prims tagged as a cap without a cap material].

    A kit module here is a CLOSED box, so a cut that capped only the hole it
    opened leaves a closed solid: zero edges used by exactly one polygon. That
    is the same measurement C1's `polyfill` trap failed in the other
    direction - it closed boundaries the cut never opened - so the two halves
    of "cap only what the cut opened" are both numbers now.

    ⚠️ `pc_corner_cut` IS THE CLIP CUT HERE. It stamps `1` for any placement
    carrying world-space cuts, and an area row is an OPEN straight polyline
    with no vertices for 4.3 to miter, so on a clipped area the only thing
    that can set it is the boundary.

    WHAT IT CANNOT SEE: a cap in the wrong PLACE. A closed solid capped on the
    wrong plane is still closed; `clip_inside_m` is what says where the cut
    landed.
    """
    geo = scene.geo
    if geo.findPrimAttrib("pc_corner_cut") is None:
        return _skip("clip_caps_closed", "no pc_corner_cut - not a cut build")
    edges, cut, untagged, caps = {}, set(), 0, 0
    for prim in geo.prims():
        try:
            if int(prim.attribValue("pc_corner_cut")) != 1:
                continue
            eid = prim.attribValue("pc_elem_id")
        except (hou.OperationFailed, TypeError, ValueError):
            continue
        cut.add(eid)
        try:
            if int(prim.attribValue("pc_cap")) == 1:
                caps += 1
                if not str(prim.attribValue("pc_cap_material")):
                    untagged += 1
        except (hou.OperationFailed, TypeError, ValueError):
            pass
        nums = [v.point().number() for v in prim.vertices()]
        for i in range(len(nums)):
            a, b = nums[i], nums[(i + 1) % len(nums)]
            key = (eid, min(a, b), max(a, b))
            edges[key] = edges.get(key, 0) + 1
    open_edges = sum(1 for v in edges.values() if v == 1)
    ok = open_edges == 0 and len(cut) > 0 and caps > 0 and untagged == 0
    return Result("clip_caps_closed", ok, [open_edges, len(cut), untagged],
                  "%d open boundary edge(s) on %d clip-cut element(s), "
                  "%d cap prim(s), %d untagged"
                  % (open_edges, len(cut), caps, untagged))


def clip_policy(scene):
    """PC-G6 condition 3: [pieces removed saying `pc_warn_clip_unsliceable`,
    pieces sliced, pieces removed in total]. All three must be non-zero and
    the removals must cover the warnings.

    D126's degrade, measured rather than argued: one `slice` policy over a kit
    with one sliceable and one rigid module must CUT the first and REMOVE the
    second - and the second must say so, because a silent gap is the failure
    that policy exists to make visible.

    WHAT IT CANNOT SEE: which pieces. It is a count off the build report; the
    geometry-side statement that nothing crosses the line is
    `clip_inside_m`'s.
    """
    rep = scene.case.get("report") or {}
    if "clipped_out" not in rep:
        return _skip("clip_policy", "no clip report - not a clipped build")
    warns = rep.get("clip_warns") or {}
    unsliceable = int(warns.get("pc_warn_clip_unsliceable", 0))
    sliced, out = int(rep.get("clip_sliced", 0)), int(rep.get("clipped_out", 0))
    return Result("clip_policy",
                  unsliceable > 0 and sliced > 0 and out >= unsliceable,
                  [unsliceable, sliced, out],
                  "%d rigid piece(s) removed and warned, %d sliced, "
                  "%d removed in total" % (unsliceable, sliced, out))


def clip_independence(a_case, b_case, moved_array):
    """PC-G6 condition 4: [elem_ids that moved in the UNTOUCHED array,
    elem_ids that moved in the edited one].

    Two builds of the same clip input with ONE sub-spline edited. The array
    that sub-spline belongs to must change; every other array must not move a
    single `pc_elem_id` - which is what "each closed sub-spline is its own
    array" means operationally (D125), and the only way to say it that a
    shared row stack could fail.

    WHAT IT CANNOT SEE: positions. Two builds could keep every id and move
    every piece; `geometry_digest` and `determinism` are what pin the values.
    """
    def by_array(case):
        out = {}
        for rec in elements(case["out"]):
            aid = str(rec.get("pc_curve_id", "")).split("#")[0]
            out.setdefault(aid, set()).add(rec["pc_elem_id"])
        return out
    a, b = by_array(a_case), by_array(b_case)
    still = [k for k in sorted(set(a) | set(b)) if k != moved_array]
    untouched = sum(len(a.get(k, set()) ^ b.get(k, set())) for k in still)
    # ...and how many ids the untouched arrays HAVE, because "0 moved" is
    # free when there is nothing there to move.
    held = sum(len(a.get(k, set())) for k in still)
    edited = len(a.get(moved_array, set()) ^ b.get(moved_array, set()))
    return Result("clip_independence",
                  untouched == 0 and edited > 0 and held > 0,
                  [untouched, edited, held],
                  "%d of %d id(s) moved in the untouched arrays, %d in %s"
                  % (untouched, held, edited, moved_array))


def _elem_cols(geo, names):
    """{name: [value per ELEMENT]} - bulk reads, deduped by `pc_elem_id`.

    One `prim*AttribValues` per column and no `hou.Prim` in the loop (11.9
    rule 1), which is why this exists rather than another `_cells` pass.
    """
    if geo.findPrimAttrib("pc_elem_id") is None:
        return {}
    eid = list(geo.primStringAttribValues("pc_elem_id"))
    cols = {}
    for name in names:
        a = geo.findPrimAttrib(name)
        if a is None:
            return {}
        cols[name] = (list(geo.primIntAttribValues(name))
                      if a.dataType() == hou.attribData.Int
                      else list(geo.primFloatAttribValues(name)))
    keep, seen = [], set()
    for i, e in enumerate(eid):
        if e not in seen:
            seen.add(e)
            keep.append(i)
    return dict((n, [c[i] for i in keep]) for n, c in cols.items())


def no_sliced_cells(scene):
    """PC-G5 condition 4: [placements cut as a tile remainder, placements].
    0 is the pass.

    Adaptive on both axes fits WHOLE modules by construction, so a facade that
    ships a half window is a fitting-solve defect - and until this check the
    condition was true and unasserted (the gate's own words: "the cheapest
    untested truth in the tool").

    ⚠️ IT READS THE PLAN, and that is a stated compromise rather than an
    oversight: `pc_slice_t` is a PLAN-POINT attribute (`PLAN_POINT_ATTRS`) and
    is deliberately not on the shipped element, so the only place a slice is
    named is `Placement.slice_t` - which is also exactly what 7.8 condition 4
    is written about ("`slice_t is None` on 100 % of non-clip placements").

    WHAT IT CANNOT SEE: (a) a slice the plan asked for and the BUILDER then
    ignored, or the reverse - the delivered span is `exact_fill_m`'s subject,
    not this one; (b) a piece cut by a miter or by the clip boundary, which is
    `Placement.cuts` / `pc_corner_cut`, a different mechanism with its own
    gates (PC-G1, PC-G6).
    """
    plan = list(scene.case.get("report", {}).get("plan", ()))
    if not plan:
        return _skip("no_sliced_cells", "no plan in the report")
    n = sum(1 for p in plan if getattr(p, "slice_t", None) is not None)
    return Result("no_sliced_cells", n == 0, [n, len(plan)],
                  "%d of %d placements carry a slice_t" % (n, len(plan)))


def bay_alignment(scene, aligned=False):
    """PC-G5 condition 3: [rows whose bay boundaries differ from the datum's,
    rows]. Under `free` at least one must differ; under `aligned`, none may.

    A row's bay-boundary set is `(pc_section, pc_u)` per cell - the section it
    is in and its parametric start inside that section - both stamped, so two
    rows over the SAME footprint are directly comparable and a row that fits
    its bays differently says so.

    ⚠️ THE FIXTURE IS THE HALF THAT WAS MISSING. Every row of PC-G5's L used
    one kit over one set of legs, so `aligned` and `free` were indistinguishable
    on it however `aligned` were implemented - the check would have passed on
    both and measured nothing. `FW_y_free` gives the ground floor a WIDER
    module, which is the smallest thing that makes the two modes different.

    WHAT IT CANNOT SEE: whether the boundaries are in the right PLACE. It
    compares rows to each other; `exact_fill_m` and `max_gap_m` are what say
    the fill is correct in the first place.
    """
    cols = _elem_cols(scene.geo, ("pc_row", "pc_section", "pc_u"))
    if not cols:
        return _skip("bay_alignment", "no pc_row - a 1D build")
    rows = {}
    for r, s, u in zip(cols["pc_row"], cols["pc_section"], cols["pc_u"]):
        rows.setdefault(int(r), set()).add((int(s), round(float(u), 6)))
    if len(rows) < 2:
        return _skip("bay_alignment", "one row - nothing to align against")
    datum = rows[min(rows)]
    differ = sorted(r for r in rows if rows[r] != datum)
    ok = (not differ) if aligned else bool(differ)
    return Result("bay_alignment", ok, [len(differ), len(rows)],
                  "%d of %d rows differ from row %d%s"
                  % (len(differ), len(rows), min(rows),
                     "" if ok else
                     " - `aligned` must make every row share the datum's bays"
                     if aligned else
                     " - the fixture does not distinguish aligned from free"))
