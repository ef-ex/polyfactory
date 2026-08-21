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
                     This is the mode working, not a gap - so it is recorded
                     as its own number and excluded from `max_gap_m` rather
                     than quietly tolerated inside it.
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

ELEM_STRINGS = ("pc_elem_id", "pc_slot", "pc_module", "pc_variant", "pc_zmode")
ELEM_INTS = ("pc_elem_key", "pc_section", "pc_generated", "pc_deformed")


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


def _axis_of(face):
    """The world point at the face's local (x, 0, 0).

    ⚠️ THE OBVIOUS MEASUREMENT - the centroid of the face - IS WRONG, and was
    measured to be wrong before this existed: a post's cross-section centre
    sits 0.60 m up and a panel's 0.55 m, so two pieces that met perfectly
    reported a 0.050 m gap and a run starting exactly on its section reported
    a 0.575 m error. Every point of one face shares one arc position and
    therefore one frame, so the face map is AFFINE - world = A + U*y + V*z -
    and the cross-section offsets divide out exactly from two point pairs.
    """
    if not face:
        return None
    (l0, w0) = face[0]
    up, across = (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)
    for (l1, w1) in face[1:]:
        if abs(l1[1] - l0[1]) > LOCAL_TOL:
            d = l1[1] - l0[1]
            up = ((w1[0] - w0[0]) / d, (w1[1] - w0[1]) / d,
                  (w1[2] - w0[2]) / d)
            break
    for (l2, w2) in face[1:]:
        if abs(l2[2] - l0[2]) > LOCAL_TOL:
            dy, dz = l2[1] - l0[1], l2[2] - l0[2]
            across = ((w2[0] - w0[0] - up[0] * dy) / dz,
                      (w2[1] - w0[1] - up[1] * dy) / dz,
                      (w2[2] - w0[2] - up[2] * dy) / dz)
            break
    return tuple(w0[k] - up[k] * l0[1] - across[k] * l0[2] for k in range(3))


def axis_points(rec):
    """(start, end) world points on the piece's own chain axis."""
    xs = rec["local"][0::3]
    if not xs:
        return (None, None)
    return (_axis_of(_face(rec, min(xs))), _axis_of(_face(rec, max(xs))))


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
    worst = 0.0
    for track in scene.tracks:
        curve, path = track["real"], track["path"]
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
    worst, where = 0.0, ""
    for _track, section, group in _groups(scene):
        d = max(abs(min(p.s0 for p in group)),
                abs(max(p.s1 for p in group) - section.length))
        if d > worst:
            worst, where = d, "%s[%d]" % (group[0].curve_id, section.index)
    return Result("section_coverage_m", worst <= TOL_M, _round(worst), where)


def exact_fill(scene):
    """The run ENDS where the section ends - measured on built geometry."""
    worst, where = 0.0, ""
    for track, section, group in _groups(scene):
        path, remap = track["path"], track["remap"]
        first = scene.by_id.get(group[0].elem_id)
        last = scene.by_id.get(group[-1].elem_id)
        if first is None or last is None:
            continue
        pairs = ((path.sample(remap(section.s0 + group[0].s0))[0],
                  axis_points(first)[0], group[0], "start"),
                 (path.sample(remap(section.s0 + group[-1].s1),
                              forward=False)[0],
                  axis_points(last)[1], group[-1], "end"))
        for want, got, placement, tag in pairs:
            if got is None:
                continue
            # A stepped piece is FLAT by definition, so its ends sit at its own
            # base height and not on the curve. That is the mode, not an error:
            # it is measured in XZ here and as `stepped_riser_m` below.
            d = (_dist_xz(want, got) if placement.zmode == "stepped"
                 else _dist(want, got))
            if d > worst:
                worst, where = d, "%s[%d] %s" % (group[0].curve_id,
                                                 section.index, tag)
    return Result("exact_fill_m", worst <= TOL_M, _round(worst), where)


def no_gaps_or_overlaps(scene):
    """Consecutive pieces meet. D21 makes this exact, not approximate."""
    worst, where = 0.0, ""
    for _track, _section, group in _groups(scene):
        for a, b in zip(group, group[1:]):
            ra, rb = scene.by_id.get(a.elem_id), scene.by_id.get(b.elem_id)
            if ra is None or rb is None:
                continue
            end_a, start_b = axis_points(ra)[1], axis_points(rb)[0]
            if end_a is None or start_b is None:
                continue
            stepped = "stepped" in (a.zmode, b.zmode)
            d = _dist_xz(end_a, start_b) if stepped else _dist(end_a, start_b)
            if d > worst:
                worst, where = d, "%s -> %s" % (a.module, b.module)
    return Result("max_gap_m", worst <= TOL_M, _round(worst), where)


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
    worst = max(flatness_m(r) for r in recs)
    return Result("flat_stepped_m", worst <= TOL_M, _round(worst),
                  "%d pieces" % len(recs))


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


def instancing_split(scene):
    """4.6's segregation, measured: how many pieces stayed packed. A build
    that unpacked everything would still be geometrically correct and would
    still be a defect."""
    packed = scene.report["packed"]
    total = packed + scene.report["deformed"]
    return Result("packed_pieces", True, packed, "of %d" % total)


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


def kit_validation(scene, expect_min=0, expect_max=0):
    """The validator reports, never raises (D24)."""
    warns = scene.report["kit_warnings"]
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
    worst, where, seen = 0.0, "", 0
    for eid, rec in scene.by_id.items():
        module = scene.kit.by_name(rec["pc_module"])
        placement = scene.plan_by_id.get(eid)
        if module is None or module.deform < 1 or placement is None:
            continue
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
            d = (_dist_xz(want, got) if placement.zmode == "stepped"
                 else _dist(want, got))
            seen += 1
            if d > worst:
                worst, where = d, "%s @ x=%.3f" % (rec["pc_module"], x)
    if not seen:
        return _skip("axis_on_curve_m", "no bendable pieces")
    return Result("axis_on_curve_m", worst <= TOL_M, _round(worst), where)


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
                  where or ("%d stand-ins" % unknown if unknown else ""))


def rigid_never_deformed(scene):
    """4.4: bend only when `pc_deform >= 1`. A rigid module that came back as
    real geometry has been deformed, and the flag says so."""
    bad = []
    for eid, rec in scene.by_id.items():
        module = scene.kit.by_name(rec["pc_module"])
        if module is None:
            continue
        if module.deform <= 0 and rec["pc_deformed"]:
            bad.append(eid)
    return Result("rigid_deformed", not bad, len(bad),
                  bad[0] if bad else "")


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
