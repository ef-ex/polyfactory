"""polyChain geometry checks - the assertions, in one place.

Each check returns a `Result` carrying a NUMBER, never a bare pass/fail: some
regressions are only ever visible as "this number got worse".  Nothing raises;
a check that cannot run reports `skipped`, because a crashed check hides the
others.

⚠️ v2, 2026-08-25: this file was 5 111 lines and ~130 checks.  Two thirds of
them were per-attribute comparisons of the built geometry against the plan
that built it - which is precisely what `diff.compare` does over EVERY
attribute by construction, on generated scenes, in `run_generated.py`.  A
bespoke assertion that compares a subset of what the comparator compares is
subsumed by it, and those are gone.  What is left is two kinds of check the
comparator structurally cannot make:

  * the sixteen GEOMETRIC properties with a registered mutation - the corner
    assembly, the conform, the deform gate, the warnings - which are
    statements about whether the answer is RIGHT, not about whether two paths
    agree on it;
  * the port TRIPWIRES, which are measured COST ceilings.  A ceiling is a
    contract (skill: "a cost check needs a measured ceiling, on every stage"),
    and every row below was bought by a regression that left every geometry
    check green.

WHAT THE NUMBERS MEAN
  packed_pieces      how many pieces shipped packed rather than deformed.
  warnings           the warning names a case is ALLOWED to raise, exactly.
  stamp_parity       [attribute values compared, differing] between the D102
                     BULK stamp and the per-prim writer it replaced.
  bank_deg           the tilt of an ADAPTIVE piece's up axis away from world
                     up: it must be NON-ZERO on a slope, or a builder that
                     ignored the Z-mode entirely would pass everything else.
  camber_deg         the cross-slope a conformed piece takes from the surface.
  conform_misses     pieces whose drape left the terrain (D53), warned.
  conform_parity     the built drape against `conform.Surface` itself.
  curvature_budget_m worst deviation a PACKED piece leaves against its budget.
  deform_gate_m      [worst deviation left packed, over budget, of those still
                     packed] - D100's dangerous direction, as a triple.
  packed_true_dev_m  the same deviation measured on the delivered geometry.
  corner_abut_m      the gap between a corner assembly and the run it joins.
  corner_outside_m   the outside-length of a mitered corner against the plan.
  corner_breach_m    how far a corner piece breaches its neighbour's span.
  corner_face_mate_m the mating faces of a corner, coplanar.
  double_pillar_m    the corner reads as ONE pillar - every other corner check
                     is a CLOSURE check, and a double pillar is perfectly
                     closed.
  *_per_piece / *_per_build / *_wrappers_built / wrapper_reads / *_hit_rate /
  *_peak_kb / *_scaling
                     11.9's cost tripwires: fixed cost per PIECE, per BUILD,
                     per verb EXECUTION and per `hou` wrapper OBJECT, each
                     with a measured ceiling and each bought by a regression
                     that left every geometry check green.
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


def _station_xs(rec):
    """Sorted distinct local x values of one built element."""
    out = []
    for x in sorted(set(round(v, 6) for v in rec["local"][0::3])):
        if not out or x - out[-1] > LOCAL_TOL:
            out.append(x)
    return out


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


UPRIGHT_ASPECT = 3.0    # height / widest footprint side, in the MODULE's own
                        # space. post 10.0, corner_post 8.1, panel 0.48,
                        # gate 0.66 - the two families are an order of
                        # magnitude apart, so the threshold is not tuned, it
                        # is a gulf.
TOUCH_M = 1e-3          # footprints this close are touching. Bigger than the
                        # float32 noise on P and far smaller than any gap an
                        # artist would read as deliberate spacing.
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
    """Footprints within TOUCH_M on both horizontal axes AND overlapping in Y.

    The Y clause only excludes pieces at genuinely different heights (a coping
    course over a plinth); a finial whose base sits exactly on a post's top
    still satisfies it. What makes a concentric stack score zero is the
    per-axis `span - own` form of the metric, not this term.
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
    """`double_pillar_m` - how much ground a RESERVED piece and a touching
    UPRIGHT from a different slot cover beyond the wider of the two. 0.0 means
    every reserved piece stands alone, which is what "one pillar at a corner"
    means when nobody is allowed to name the modules.

    The number is a distance in metres, so a corner doubled by half a post
    reads as half a post and not as a boolean, and (D270) it is a PAIRWISE
    quantity bounded by one module's footprint - never a cluster span.

    WHAT IT CANNOT SEE, stated because the checks it joins could not see the
    defect it was written for:
      * a SEPARATED double pillar - two uprights 50 mm apart look just as
        wrong and read here as deliberate spacing (`TOUCH_M` is 1 mm);
      * a doubling at or under the 2 mm `tol`. That tolerance is there because
        a pillar standing on a bend is measured on its AABB and reads slightly
        wide; the price is that a genuine 2 mm overshoot passes. Measured:
        0.0015 and 0.0019 pass, 0.0021 fails;
      * a MISSING pillar, an empty corner, or a corner dressed in the wrong
        module - it never asks what SHOULD be there, only that what is there
        is not doubled;
      * doubling WITHIN one slot: two corner assemblies squeezed onto a leg
        shorter than both (`AP_narrow_rect`) are all slot `corner` and pass
        here. That case is covered by `pc_warn_overflow` and
        `corner_face_mate_m`, and this check deliberately does not
        second-guess them;
      * two touching pieces that are BOTH reserved and both non-upright - a
        blocky corner return abutting a blocky end cap. The doubler side of
        the rule is the aspect test, and a plinth is not an upright;
      * duplication among non-reserved members - two coincident panels, or a
        fill post butted against another fill post, are invisible to it;
      * it FLAGS any upright from another slot touching a reserved piece,
        including compositions the tool advertises: `slot_evenly`'s own help
        names "lamps on a railing, bollards on a kerb", and a kit whose fill
        piece is a bollard and whose evenly piece is a lamp reds here
        (measured 0.08 m on a synthetic `default:post` + `evenly:lamp`
        abutment). `expected` is the escape hatch for such kits, and every
        non-zero expectation in the runner is named;
      * it is a PHASE-1 check: `run_2d_checks` does not call it, because a
        facade's mullions are uprights in different cells by design and the
        rule would need a 2D reading before it means anything there.
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

    # D270: bucket the footprints instead of sweeping every pair. The old
    # O(n^2) sweep measured 33.9 s on 16 667 uprights (2 km of `post` fill) -
    # affordable on the 270-piece hill cases it was written against and not on
    # the long-run fixtures `run_native_checks` already builds. The cell is
    # the WIDEST candidate, so a kit mixing a 20 m wall module with 0.12 m
    # posts degrades back towards the pairwise sweep - stated rather than
    # claimed away, because nothing in the suite has that shape today.
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


def path_sample_calls_per_piece(build_fn, place_mod, expect_max=4.0,
                                name=None):
    """`Path.sample` calls per placed piece - what P5R's `span_ends` is for.

    ⚠️ THIS EXISTS BECAUSE THE PORT'S LARGEST PACKED-BRANCH FIX WAS PINNED BY
    NOTHING. P5R threaded one forward/backward pair through `_flat_ratio`,
    `_chord_ratio`, `span_deviation`, `_needs_deform`, `_packed_transform` and
    `plan_pos` instead of letting each re-ask the sampler, and measured
    169 232 -> 69 232 calls on the 20 km packed row. `span_ends(..., ends)` is
    a pure cache - a miss re-samples and returns the identical value - so
    dropping the threading is invisible to every geometry assertion: with
    `ends` forced to `None` the whole scene suite, the HDA suite, the unit
    tests AND the baseline diff stay completely green while the packed
    fixture goes from **3.0 to 13.0 calls per piece (4.33x)**.

    That is exactly the shape `stamp_calls_per_piece` was written for one
    item earlier and `station_share_hit_rate` one item after it, and P5R
    added neither for its own fix. A COUNT, so it sits in the baseline
    without churning.

    Both fixtures are surface-free, so `place.Path` is the only sampler in
    play; a conformed run would need `ConformPath.sample` counted too.
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


def conform_cache_per_element(build_fn, conform_mod, expect_max=30.0,
                              name=None):
    """Entries `ConformPath._cache` holds per placed element - P5's cost.

    The memo is unbounded and keyed on `(round(s,9), forward)`: 53 861
    entries / 24 MB on one 2 km curve (11.2 P5), and a 300-street conformed
    citygen run carries several hundred MB of it.

    ⚠️ P5 DID NOT DELETE THE CACHE, WHICH THIS DOCSTRING USED TO PROMISE AND
    11.2 P5 STILL DOES. It kept it, made it the batch's destination and filled
    it EAGERLY - which took this reading UP, 17.55 -> 18.7, and took the peak
    working set of the conformed street row up with it. Dropping the gap
    midpoints from the enumeration is what brings it back down (18.7 -> 17.6
    here, and -191 MB of peak working set on 300 conformed streets); the
    ceiling stays where it was because what it guards is the memo growing
    without anyone noticing, not the exact figure.
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


def path_read_direction_m(place_mod, curve_cls, expect_max=1e-12):
    """How far apart `Path.sample(s)` and `Path.sample(s, forward=False)` land
    AT A VERTEX - the number P3's docstring used to state as zero.

    P3's one semantic change is that a station gap's END is now the next
    station's FORWARD read where it used to be a BACKWARD one, and it was
    written up as "bit-identical by construction... 0 differing, worst 0 m".
    It is not. That measurement was taken on PC-G3's arc, which is
    axis-aligned with round coordinates; in general the backward branch lands
    on the PREVIOUS segment with t clamped to 1.0 and returns `a + d*1.0`,
    which is float-exactly `pts[k]` only when the two endpoints are within a
    factor of 2 (Sterbenz).

    So the claim becomes a measurement: every vertex arclength of seven
    curves - open, closed, diagonal, hairpin, climbing, sub-millimetre, and
    one axis-aligned control - read both ways. Worst |dP| here is **4.4e-16 m**
    (2 of 166 differing); an independent sweep of seven other curves read
    7.1e-15 m. Both are double-precision ULP on a segment endpoint, seven
    orders below `bend_tol` and below `bend_deviation_m`'s own `_round(dev, 9)`.
    The ceiling is 1e-12 m: a REAL divergence - a dropped sub-EPS segment
    picked differently by the two branches, say - is metres, not ULPs.

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


def conform_parity(scene, tol_m=1e-9, tol_n=1e-9):
    """11.2 P5 / 11.3 rule 1: the batched `ray` and the per-query
    `hou.Geometry.intersect` answer every drop this case made THE SAME.

    `ConformPath.prefetch` fills `_cache` from one `ray` execution and `_at`
    fills anything it missed from `Surface.drop`. Both implementations are
    therefore live in one process, and this asks BOTH: every key the build
    actually cached is re-dropped through the Python path here and the two
    answers are compared. A key the prefetch missed compares exactly 0.0 - it
    IS the Python path - so what this reports is the batch's own divergence.

    ⚠️ WHAT DIVERGES AND WHY. The verb and `intersect` are the same
    intersector - `ray_verb_semantics` asserts that on the surfaces that could
    tell them apart, at exactly 0. What differs is the WIDTH OF THE NUMBER:
    the verb's ray origins and its answer both live in a point cloud, i.e.
    float32, while `hou.Vector3` is double (probed - it round-trips
    2000.1234567890123 exactly). `drop_many` therefore reads the verb's
    DISTANCE and not its POSITION, and rebuilds the drop as `q + axis*dist`
    from the double query - one float32 rounding at the magnitude of a DROP
    instead of one at the magnitude of a WORLD COORDINATE (D111).

    ⚠️ AND THE 0.0 THIS READS IS NOW A PROPERTY OF THE CODE, WHICH IT WAS NOT
    BEFORE. P5 read the POSITION, and that is bit-identical only when the true
    answer happens to be exactly representable in float32 - which every
    committed conform case is, because their surfaces are `y = 0.25x` and
    their stations are multiples of 0.25 m. On an irrational-slope ramp the
    position route reads 2.4e-07 m at x < 24 and 6.1e-05 m at x = 20 000,
    against 0.0 for the distance route at both. So this check read 0.0 as a
    property of the SCENES; `ray_verb_semantics`' `dirty_ramp` and
    `dirty_ramp_20km` trials are what tell those two apart, and they are the
    reason the tolerance can honestly stay at 1e-09 m rather than at 11.3's
    declared 1e-06.

    ⚠️ A TILTED `conform_axis` IS NOT BATCHED AT ALL (D111) and this reports
    it as a skip: the float32 ray origin does not lie on the double ray, the
    divergence is ALONG the ray and the reconstruction cannot remove it
    (1.9e-06 m on the same ramp, 1.5e-05 m at 20 km), so `drop_many` declines
    and the per-query path - the reference - is the only implementation
    running. `BJ_tilted_axis` is the case that builds in that configuration.

    Reported as `[max |dP| m, hit-flag mismatches, max |dN| after D52's flip]`.
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
        # the points this build actually visited, re-asked of BOTH paths.
        # (`_cache` keys are `round(s, 9)`, and `_at` samples the RAW s, so
        # comparing against the stored value would measure the key's rounding
        # rather than the drop - 3.7e-09 m of it. Both are asked at the same
        # `p` here instead, which is the question worth answering.)
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
    """11.2 P5's tripwire, in BOTH directions: is the batch serving the drops,
    and is it fetching drops nobody wants?

    P5's safety argument is P3's - "a key the prefetch missed is slow, never
    wrong" - and P5V's X1 is the lesson that goes with it: a pure cache whose
    fill is silently disabled leaves every suite green and every number
    unmoved while the work goes back to where it was.

    ⚠️ AND THE FIRST VERSION OF THIS CHECK COULD ONLY SEE ONE OF THE TWO WAYS
    TO GET IT WRONG. It reported `fallback / batched`, which is 0.0 BY
    CONSTRUCTION when the batch over-fetches - so a prefetch enumerating
    thousands of keys nothing asks for read as a perfect score. It did: over
    the whole conformed ladder the gap midpoints were **0 % consumed on a 2 km
    fence and 9 % on 300 conformed streets**, 47 % of every batch and 47 % of
    the memo it fills. They are not enumerated any more (they are only ever
    read for a piece that DEFORMS, which the enumeration cannot know), and
    `used / batched` is the number that says so.

    Reported as `[used/batched, fallback/batched, batched]`, both ceilings on
    the call - `scale_gate.py`'s LADDER device - because the second one is a
    property of the FIXTURE: it is the gap midpoints of whatever fraction of
    that fixture's pieces deform, near 1.0 on a 100 %-deformed run and near
    0.1 on the packed-dominant street row.

    `used` needs the keys `_at` was actually asked for, so `_at` is wrapped -
    which is why this is a check and not something the kernel counts.
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
    """The `ray` verb IS `hou.Geometry.intersect`, on the eight surfaces that
    could tell them apart. 11.2 P5's load-bearing measurement, standing up.

    ⚠️ AND THE EIGHT WERE NOT ENOUGH, WHICH IS THE LESSON THIS CHECK CARRIES.
    Every one of them is an ANALYTIC surface with a round slope, sampled at
    round stations under 25 m, so its true answer is exactly representable in
    float32 - and a reading taken off the verb's POSITION attribute is
    bit-identical there whether or not it is bit-identical anywhere else. It
    is not: on an irrational-slope ramp the position route reads 2.4e-07 m,
    and at x = 20 000 m it reads 6.1e-05 m. Reading the verb's DISTANCE
    instead is 0.0 on both (D111). `dirty_ramp` and `dirty_ramp_20km` are
    those two trials, and they are the only rows here that can tell the two
    readings apart - restore the position route and they go red at 2.4e-07 /
    6.1e-05 while all eight originals stay at exactly 0.

    ⚠️ AND `tilted_axis_declines` IS AN ASSERTION ABOUT THE GATE, not about a
    drop. `Params.conform_axis` is a free direction vector (D51), and on a
    tilted axis the float32 ray origin no longer lies on the double ray: the
    divergence is ALONG the ray, the reconstruction cannot remove it, and it
    is 1.9e-06 m on the dirty ramp and 1.5e-05 m at 20 km - 1 000x this
    check's own tolerance and above `conform_parity`'s. `Surface.batchable`
    therefore declines it and the per-query path serves that configuration
    alone, which is what this row asserts.

    Everything P5 rests on is that the batched verb answers the same question
    the per-query HOM call does. 11.2 P5 predicted three named differences and
    two of the three are simply not there on 22.0.398 once the verb is
    configured to say what `Surface.drop` says: `reverserays=bidirectional` +
    `bidirectionalresult=closest` is D70's "look both ways, nearest wins",
    `rtolerance=1e-6` is `intersect`'s own `tolerance`, `bias=0` is its
    `min_hit`, and `maxraydistcheck=0` cannot cut a hit off because every
    surface point lies within `radius` of the centre. The third IS there and
    is re-added in `drop_many`: the verb hands back the polygon's own normal,
    so D52's flip-to-oppose-the-axis is applied on read.

    The eight, each of which a naive port gets wrong in a different way:
      * D70's bridge deck - ground at y=-2 with a deck at y=+2 over part of
        the run. A `first hit` port puts the road on the deck.
      * ...and the same deck at an UNEQUAL standoff (ground -2, deck +3),
        because the first two are equidistant and therefore cannot see
        `bidirectionalresult` at all (D113 - an audit mutation flipped it to
        `farthest` and all ten original trials stayed at exactly 0.0).
      * An EXACT TIE - two sheets at y=+/-2 with the query between them. D70
        says the tie goes DOWN-axis because the stage is a drop.
      * D52's reversed winding, and a query from BELOW the surface - facing is
        ignored for the hit itself.
      * D53's hole and its edge - a miss must keep the unprojected position.
      * Two COINCIDENT sheets - the degenerate tie.
      * The camber cross-fall and the two-facet tent - the normal, and a
        surface coarser than the pieces.

    Reported as `[max |dP| m, hit-flag mismatches, max |dN| after the flip]`,
    all three asserted at exactly 0.
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
        """The deck at a DIFFERENT standoff from the ground, which `deck()`
        is not - and that is the whole point of this trial (D113).

        `deck()` puts the ground at y = -2 and the deck at y = +2 with the
        query at y = 0, so the two hits are EQUIDISTANT: `closest` and
        `farthest` return the same point and the trial cannot see the parm
        that chooses between them. Mutation-tested: flipping
        `bidirectionalresult` to `farthest` left all ten original trials at
        exactly 0.0 and was caught only by `conform_parity` on one scene case.
        Here the deck is at +3 against ground at -2, so nearest is the ground
        and farthest is the deck, 5 m apart.
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
    """How many `hou.Prim` WRAPPERS a build materialises through `geo.prims()`.

    `geo.prims()` builds a tuple of one wrapper per primitive, so the cost is
    the geometry's size and not the call. P5R cut three `len(geo.prims())`
    sites that only wanted a NUMBER and the fourth survived because nothing
    counted them: `conform.Surface.__init__` runs once per CURVE, on the
    SURFACE, and on 300 conformed streets over a 7 712-prim terrain it built
    300 x 7 712 = 2.3 M wrappers - **0.530 s of a 3.46 s row, 15 %, the
    largest single entry in that profile** - to ask whether the geometry was
    empty. `intrinsicValue("primitivecount")` answers that for free.

    ⚠️ THE VALUE IS WRAPPERS, NOT CALLS, and that is the whole point: three
    legitimate `for prim in geo.prims()` loops remain (kit validation, kit
    read, `read_curves`) and they are bounded by the KIT and the INPUT, which
    is what a ceiling can be set against. A count of calls would read 3 on a
    one-curve fixture whether the surface was being wrapped or not.
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
    """How many `ray` verb EXECUTIONS one build takes. 11.2 P5, corrected.

    ⚠️ THE VERB'S COST IS NOT ALL MARGINAL, AND THAT IS WHAT THIS PINS. `ray`
    rebuilds its second input on every execution, so each call carries a fixed
    cost that scales with the SURFACE and not with the query count - measured
    on this build, minimum of five calls on one warm `Surface`: **0.34 ms at
    5 022 terrain prims, 0.71 ms at 20 088, 2.25 ms at 80 352**, against a
    marginal ~2 us per query. P5 paid it once per CURVE, which is free on the
    one-curve fence it was measured on and is a LOSS on the many-curve shape
    it was aimed at: 300 x 60 m conformed streets read **0.94-0.99x** with the
    batch on - slower than not batching at all - and 1.20-1.39x once the batch
    is taken once for the whole build.

    A count, not a time, and P5R's rule 3 applies: a call count is evidence of
    a call count. What makes it worth asserting is that the count is the thing
    that changed sign, and that `conform_bench.py` carries the wall clock.

    Counted through `Surface.drop_many`, which is one execution by definition.
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
    """How many COMPILED SOP EXECUTIONS one build takes, per verb name.

    `ray_executions_per_build` pins the conform batch because P5 proved a
    per-execute fixed cost can invert a batch's sign. `clip` and `polyfill`
    carry the same kind of cost - each rebuilds its own input - and nothing
    counted them, so phase 2 multiplied them by the ROW COUNT unwatched: a
    phase-1 rectangle is 4 corners x 2 halves = 8 mitered pieces, a
    100-building district is 100 x 4 x 8 rows x 2 = 6 400, i.e. 12 800
    executions against the 100 `ray` calls the cycle went to war over.

    The value is a sorted [name, count] list so a new verb appearing in the
    kernel is visible as a NAME (11.9: "the only compiled SOPs it reaches are
    three verbs"), not as a total that happens to match.
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
    """THE VERB PROPERTY `clip_plane`'s BULK CAP TAG RESTS ON.

    P7's fix replaced a per-prim, per-point plane test with "the caps are the
    tail", which is true because `polyfill` appends the primitives it creates
    contiguously after the ones it was given. That was probed on this build
    rather than recalled - and a probe that is not committed is a probe that
    silently stops being true, so this re-runs it: three disjoint boxes cut by
    one plane, the tail range compared against the ORIGINAL plane test.
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
    """The same question for `hou.Point`, because the same defect came back.

    P5b closed `len(geo.prims())`; P5 had ALREADY reopened it one object down.
    `drop_many`'s hit test read the `ray` verb's output point GROUP -
    `set(pt.number() for pt in grp.points())` - which builds one `hou.Point`
    wrapper per query. Timed on 34 002 queries against a 3 481-prim grid:
    `verb.execute` 0.0016 s, the group read **0.0081 s** - five times the work
    it was decorating - and 306 600 wrappers on the conformed street row.
    `prims_wrappers_built` could not see it: it counts prims.

    The verb answers it for free instead. `useprimnumattrib` writes `hitprim`,
    -1 on a miss and the primitive number on a hit; measured against the group
    over three surfaces including 40 ZERO-DISTANCE hits they disagree on 0
    points. (`putdist` + `dist != 0` is NOT a substitute - it calls all 40 of
    those a miss.)

    Both sources are counted, because the group read never touched
    `hou.Geometry.points` at all.
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
    """THE HOLE THE OTHER FOUR TRIPWIRES LEFT: reads through a `hou.Prim`.

    `prims_wrappers_built` and `points_wrappers_built` count wrappers
    MATERIALISED through `hou.Geometry` / `hou.PointGroup`, and
    `stamp_calls_per_piece` / `rows_wrappers_built` count wrapper WRITES.
    A read through a wrapper is neither, so `points_wrappers_built` read 0
    (PASS, ceiling 8) on a phase-2 district that materialised 159 242
    `hou.Point` objects through `hou.Prim.points` and called
    `Point.position` 220 488 times - i.e. 11.9 rule 1's instruction "if a
    phase-2 row is slow, COUNT WRAPPERS" was unanswerable with the counters
    that existed. This is that number: `Prim.points` (by length),
    `Point.position`, `Point.attribValue` and `Prim.attribValue`.

    The ceiling is a CLASS boundary, not a floor - three legitimate wrapper
    loops remain (kit validation, kit read, `read_curves`) and they are
    bounded by the kit and the input.
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
