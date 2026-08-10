"""CityGen geometry checks — the assertions, in one place.

Every check here caught a REAL bug during the audit rounds. They were rewritten
from scratch by each audit pass because they lived nowhere; that is what this
module exists to stop. A new measurement written during a review belongs here
afterwards, so the next review starts where the last one finished.

Each check takes Houdini geometry and returns a Result. Nothing raises: a check
that cannot run reports `skipped`, because a crashed check hides the others.

Run via tests/citygen/run_scene_checks.py (hython). Pure-logic tests that need
no Houdini live in tests/unit/.
"""

import collections
import math

# Mirrors pfsj_corner_radius() in polyfactory/vex/include/pf_streetjunction.vfl.
# If that table changes, this one must follow, or the corner-radius assertion
# starts reporting the difference between two versions of the same constant.
CLASS_RADIUS = {"highway": 25.0, "arterial": 9.0, "collector": 6.0,
                "local": 4.0, "alley": 2.0}


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
        return "[%s] %-34s %s  %s" % (state, self.name, self.value, self.detail)


def _skip(name, why):
    return Result(name, True, None, why, skipped=True)


# ---------------------------------------------------------------------------
# small XZ geometry helpers, shared by several checks
#
# Everything here works in XZ and ignores Y on purpose: the city is flat in v1
# and PolyExpand2D leaves ~2e-5 of Y noise behind (see no_nonplanar_y), which a
# true-3D predicate would read as real structure.
#
# Tolerances: Houdini stores P as float32, so at the 800 m domain edge one ulp
# is already ~6e-5 m. Any distance tolerance below ~1e-4 m is measuring the
# storage format, not the geometry.
# ---------------------------------------------------------------------------

def _seg_point_dist(a, b, q):
    abx, abz = b[0] - a[0], b[2] - a[2]
    l2 = abx * abx + abz * abz
    if l2 < 1e-18:
        return math.hypot(q[0] - a[0], q[2] - a[2])
    t = ((q[0] - a[0]) * abx + (q[2] - a[2]) * abz) / l2
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    return math.hypot(q[0] - (a[0] + abx * t), q[2] - (a[2] + abz * t))


def _obb(pts):
    """Minimum-area oriented bounding box in XZ, by rotating calipers over the
    edge directions — the minimum-area rectangle always has a side flush with
    an edge. Returns (long_extent, short_extent). Mirrors pfsl_obb()."""
    n = len(pts)
    best = None
    for i in range(n):
        ex = pts[(i + 1) % n][0] - pts[i][0]
        ez = pts[(i + 1) % n][2] - pts[i][2]
        m = math.hypot(ex, ez)
        if m < 1e-9:
            continue
        ux, uz = ex / m, ez / m
        u0 = v0 = 1e30
        u1 = v1 = -1e30
        for q in pts:
            du = q[0] * ux + q[2] * uz
            dv = q[0] * -uz + q[2] * ux
            if du < u0:
                u0 = du
            if du > u1:
                u1 = du
            if dv < v0:
                v0 = dv
            if dv > v1:
                v1 = dv
        area = (u1 - u0) * (v1 - v0)
        if best is None or area < best[0]:
            best = (area, u1 - u0, v1 - v0)
    if best is None:
        return 0.0, 0.0
    return max(best[1], best[2]), min(best[1], best[2])


def _fit_circle(pts):
    """Kasa algebraic circle fit in XZ. Returns (cx, cz, r, max_residual) or
    None when the points are collinear."""
    n = len(pts)
    sx = sz = sxx = szz = sxz = sxxx = szzz = sxzz = szxx = 0.0
    for p in pts:
        x, z = p[0], p[2]
        sx += x
        sz += z
        sxx += x * x
        szz += z * z
        sxz += x * z
        sxxx += x * x * x
        szzz += z * z * z
        sxzz += x * z * z
        szxx += z * x * x
    a11 = 2 * (sxx - sx * sx / n)
    a12 = 2 * (sxz - sx * sz / n)
    a22 = 2 * (szz - sz * sz / n)
    b1 = sxxx + sxzz - (sxx + szz) * sx / n
    b2 = szzz + szxx - (sxx + szz) * sz / n
    det = a11 * a22 - a12 * a12
    if abs(det) < 1e-12:
        return None
    cx = (b1 * a22 - b2 * a12) / det
    cz = (a11 * b2 - a12 * b1) / det
    rs = [math.hypot(p[0] - cx, p[2] - cz) for p in pts]
    r = sum(rs) / n
    return cx, cz, r, max(abs(q - r) for q in rs)


def _arc_lengths(pts):
    acc = [0.0]
    for i in range(1, len(pts)):
        acc.append(acc[-1] + (pts[i] - pts[i - 1]).length())
    return acc


def _pos_at_length(pts, acc, s):
    """Position at arc length `s` along a polyline — what s5j_trim's
    pfsg_pos_at_length() computes."""
    if s <= 0:
        return pts[0]
    if s >= acc[-1]:
        return pts[-1]
    j = 0
    while j < len(acc) - 2 and acc[j + 1] < s:
        j += 1
    span = acc[j + 1] - acc[j]
    f = 0.0 if span <= 0 else (s - acc[j]) / span
    return pts[j] + (pts[j + 1] - pts[j]) * f


# ---------------------------------------------------------------------------
# mesh hygiene
# ---------------------------------------------------------------------------

def no_zero_area_prims(geo, tol=1e-9):
    """Was 1385 / 7280 / 7430 prims — 24% of everything shipped.

    build_profile_points emits two points per element, so every seam between
    two same-height elements sweeps into a zero-width strip.
    """
    n = sum(1 for p in geo.prims()
            if abs(p.intrinsicValue("measuredarea")) <= tol)
    return Result("no_zero_area_prims", n == 0, n,
                  "degenerate prims must be dropped after the sweep")


def no_loose_points(geo):
    """Points belonging to no primitive. They ship as stray dots and blow out
    every downstream bounding box — including the render framing."""
    n = sum(1 for p in geo.points() if len(p.prims()) == 0)
    return Result("no_loose_points", n == 0, n, "points with no primitive")


def no_downward_faces(geo, skip_types=("kerb",)):
    """A horizontal face pointing down renders black and vanishes under
    backface culling. Caught 414 of B's lots and 273 of C's."""
    bad = []
    for p in geo.prims():
        try:
            et = p.attribValue("elem_type") if geo.findPrimAttrib("elem_type") else ""
        except Exception:
            et = ""
        if et in skip_types:
            continue
        try:
            if p.normal()[1] < 0:
                bad.append(p.number())
        except Exception:
            pass
    return Result("no_downward_faces", not bad, len(bad),
                  "first few: %s" % bad[:5] if bad else "")


def no_scratch_groups(geo, allowed=()):
    """Working groups must not escape the asset. `flipme` leaking from blocks
    onto lots caused a winding regression via a group-NAME COLLISION."""
    groups = [g.name() for g in geo.primGroups() if g.name() not in allowed]
    groups += [g.name() for g in geo.pointGroups() if g.name() not in allowed]
    return Result("no_scratch_groups", not groups, len(groups), ", ".join(groups))


def no_nonplanar_y(geo, tol=1e-6):
    """PolyExpand2D breaks planarity by ~2e-5. Intersection Analysis is a true
    3D test, so coincident edges 20 microns out of plane read as REAL crossings
    — which is what made lots look self-intersecting when they were fine."""
    ys = [p.position()[1] for p in geo.points()]
    if not ys:
        return _skip("no_nonplanar_y", "no points")
    spread = max(ys) - min(ys)
    return Result("no_nonplanar_y", spread <= tol, round(spread, 9),
                  "y spread; flatten after PolyExpand2D")


# ---------------------------------------------------------------------------
# street graph
# ---------------------------------------------------------------------------

def graph_is_planar(geo, tol=1e-4):
    """No two segments may cross except at a shared node. Planarity is a
    PER-LAYER invariant — an overpass is two edges crossing on different
    layers and must NOT share a node (citygen_streets.md S3)."""
    has_layer = geo.findPrimAttrib("layer") is not None
    segs = collections.defaultdict(list)
    for pr in geo.prims():
        layer = int(pr.attribValue("layer")) if has_layer else 0
        vs = list(pr.vertices())
        for i in range(len(vs) - 1):
            a, b = vs[i].point(), vs[i + 1].point()
            segs[layer].append((a.number(), b.number(),
                                a.position(), b.position()))

    def crosses(p1, p2, p3, p4):
        d = ((p2[0] - p1[0]) * (p4[2] - p3[2]) - (p2[2] - p1[2]) * (p4[0] - p3[0]))
        if abs(d) < 1e-12:
            return False
        t = ((p3[0] - p1[0]) * (p4[2] - p3[2]) - (p3[2] - p1[2]) * (p4[0] - p3[0])) / d
        u = ((p3[0] - p1[0]) * (p2[2] - p1[2]) - (p3[2] - p1[2]) * (p2[0] - p1[0])) / d
        return tol < t < 1 - tol and tol < u < 1 - tol

    bad = 0
    for layer, lst in segs.items():
        for i in range(len(lst)):
            a1, b1, p1, p2 = lst[i]
            for j in range(i + 1, len(lst)):
                a2, b2, p3, p4 = lst[j]
                if {a1, b1} & {a2, b2}:
                    continue
                if crosses(p1, p2, p3, p4):
                    bad += 1
    return Result("graph_is_planar", bad == 0, bad,
                  "segment crossings with no shared node (per layer)")


def no_orphan_components(geo):
    """A component containing no junction is a street floating connected to
    nothing. A cul-de-sac hanging off the network is legitimate and must be
    kept — the test is per COMPONENT, not per edge."""
    seen, comps = set(), 0
    orphan = 0
    for pr in geo.prims():
        if pr.number() in seen:
            continue
        stack, comp = [pr], []
        while stack:
            cur = stack.pop()
            if cur.number() in seen:
                continue
            seen.add(cur.number())
            comp.append(cur)
            for v in cur.vertices():
                for nb in v.point().prims():
                    if nb.number() not in seen:
                        stack.append(nb)
        comps += 1
        has_junction = any(len(v.point().prims()) >= 3 for c in comp for v in c.vertices())
        if not has_junction:
            orphan += 1
    return Result("no_orphan_components", orphan == 0, orphan,
                  "%d components total" % comps)


# ---------------------------------------------------------------------------
# junctions — these two are the arc-fit regression detector
# ---------------------------------------------------------------------------

def no_degenerate_corner_segments(patch_geo, tol=1e-3):
    """Zero-length boundary segments mean the fillet arc collapsed.

    pfsj_arc_centre_through used `r = max(radius, halfc)`: when the class corner
    radius could not span the chord, every arc point stacked on one corner. Was
    32 / 72 / 96 segments and produced a notch in the sidewalk at every one.
    """
    if patch_geo.findPointAttrib("after_corner") is None:
        return _skip("no_degenerate_corner_segments", "no after_corner attrib")
    bad = 0
    for pr in patch_geo.prims():
        pts = list(pr.vertices())
        n = len(pts)
        for i in range(n):
            a = pts[i].point()
            b = pts[(i + 1) % n].point()
            if a.attribValue("after_corner") != 1:
                continue
            if (a.position() - b.position()).length() < tol:
                bad += 1
    return Result("no_degenerate_corner_segments", bad == 0, bad,
                  "collapsed fillet arcs")


def every_corner_is_an_arc(patch_geo, solve_geo=None, radius_scale=1.0,
                           max_fillet_fraction=0.4,
                           dot_tol=-0.985, fit_tol=1e-3, radius_tol=5e-3,
                           tangent_tol=1e-3):
    """A junction corner that is not a correctly-placed fillet arc.

    Measured 50/50 on the grid case and 56/56 on the radial one: half of every
    junction's corners were straight. The cause was ours — the arc was refitted
    through the street cap corners rather than the caps being placed at the
    fillet's tangent points, so whenever the class radius could not span the
    chord it silently fell back to a straight line.

    A fillet tangent to both kerb lines exists for ANY non-collinear corner, so
    the only legitimate straight corner is a street running straight through the
    junction (the two mouths anti-parallel), which is what a real kerb does.
    Anything else is the bug coming back.

    STRENGTHENED after the 2026-08-09 audit (citygen_streets.md 4e-10): counting
    arc POINTS cannot see a wrong radius or a non-tangent arc, and both of those
    were live failure modes here — `r = max(radius, halfchord)` silently grew
    the radius, and re-fitting through cap corners produced arcs that met the
    kerb at an angle. So each corner's arc points now get a circle fitted to
    them, and the check asserts three further things:

      fit      the points really lie on a circle (a chord dressed up as an arc,
               or a radially-clamped bevel, fails here);
      radius   the fitted radius is the one §S5's rule demands for THIS corner
               (below) — this is what catches a silently grown or shrunk radius;
      tangent  the arc centre sits exactly `r` from BOTH kerb lines, i.e. the
               arc is tangent to each. A fillet that is not tangent leaves a
               kink in the kerb where the arc meets the straight run.

    RE-POINTED at the two rules §S5 decided on 2026-08-09. It used to accept any
    class radius present at the node, because the solver took the class of
    whichever street sorted first by atan2 and the doc named no tie-break. Both
    ends of that are now settled, so the check asserts them:

      * at a mixed-class corner the LESSER street sets the radius, `min(rA, rB)`
        — only the turn ONTO the smaller street sizes the corner;
      * `max_fillet_fraction` (0.4) caps the tangent run `r/tan(theta/2)` at
        that fraction of the shorter incident street, and the cap changes the
        radius, so the expected value is recomputed through it.

    Both the fitted circle AND the solver's own `corner_r` are compared against
    that expectation, so a solver that applies the right radius but draws the
    wrong arc, or vice versa, still fails. `mixed_class` stays as a reported
    count: it is no longer a defect, only a measure of how often the rule bites.
    """
    name = "every_corner_is_an_arc"
    if patch_geo.findPointAttrib("is_cap") is None:
        return _skip(name, "no is_cap attribute")
    up = (0.0, 1.0, 0.0)

    # node -> the streets meeting there, each with its class radius, its length
    # and its polyline, so a corner can be matched to the two it actually joins.
    # s5j_solve's output still carries both the patches and the street
    # polylines, so junction_pt indexes straight into it.
    node_radii = {}
    node_edges = {}
    if solve_geo is not None and solve_geo.findPrimAttrib("junction_pt") is not None:
        for pr in solve_geo.prims():
            try:
                if pr.attribValue("is_junction_patch") != 1:
                    continue
                jp = int(pr.attribValue("junction_pt"))
            except Exception:
                continue
            rs, es = set(), []
            for e in solve_geo.point(jp).prims():
                try:
                    if e.attribValue("is_junction_patch") == 1:
                        continue
                    r = CLASS_RADIUS.get(e.attribValue("street_class"), 4.0) \
                        * radius_scale
                except Exception:
                    continue
                ep = [v.point().position() for v in e.vertices()]
                rs.add(r)
                es.append((r, _arc_lengths(ep)[-1], ep))
            node_radii[jp] = rs
            node_edges[jp] = es

    def _street_at(edges, capc):
        """The incident street a mouth belongs to: the one its cap centre lies
        on. Position, not direction — a curved arm's tangent at the cut is not
        its direction at the node."""
        best = None
        for (r, ln, ep) in edges:
            d = min(_seg_point_dist(ep[i - 1], ep[i], capc)
                    for i in range(1, len(ep)))
            if best is None or d < best[0]:
                best = (d, r, ln)
        return (best[1], best[2]) if best else (None, None)

    def _street_dir(cin, cout, capc, centre):
        v = (cout[0] - cin[0], 0.0, cout[2] - cin[2])          # across the mouth
        d = (v[2] * up[1], 0.0, -v[0] * up[1])                 # cross(v, up)
        m = math.hypot(d[0], d[2]) or 1.0
        d = (d[0] / m, 0.0, d[2] / m)
        out = (capc[0] - centre[0], 0.0, capc[2] - centre[2])  # point away from the node
        return d if (d[0] * out[0] + d[2] * out[2]) >= 0 else (-d[0], 0.0, -d[2])

    bad = 0
    total = 0
    mixed = 0
    max_fit = max_rad = max_tan = max_radfit = 0.0
    fitted = unfitted = 0
    for prim in patch_geo.prims():
        pts = [v.point() for v in prim.vertices()]
        n = len(pts)
        if n < 3:
            continue
        cap = [p.attribValue("is_cap") for p in pts]
        aft = [p.attribValue("after_corner") for p in pts]
        pos = [p.position() for p in pts]
        centre = [sum(p[i] for p in pos) / n for i in range(3)]
        try:
            jp = int(prim.attribValue("junction_pt"))
        except Exception:
            jp = -1
        cand = node_radii.get(jp, set())
        edges = node_edges.get(jp, [])
        for i in range(n):
            if not (cap[i] == 1 and aft[i] == 1):
                continue                                       # not a corner start
            total += 1
            if len(cand) > 1:
                mixed += 1
            k, run = (i + 1) % n, 0
            while cap[k] == 0 and run < n:
                run += 1
                k = (k + 1) % n
            if not run:
                # straight: legitimate only if the two streets are anti-parallel
                a = _street_dir(pos[i - 1], pos[i], pts[i].attribValue("capc"), centre)
                b = _street_dir(pos[k], pos[(k + 1) % n], pts[k].attribValue("capc"),
                                centre)
                if a[0] * b[0] + a[2] * b[2] > dot_tol:
                    bad += 1
                continue

            # An arc exists. Is it the RIGHT arc? Every non-cap point in the run
            # lies on the fillet — the tangent points included, since those are
            # only emitted when they differ from the cap corner.
            arcpts = [pos[(i + 1 + t) % n] for t in range(run)]
            if len(arcpts) < 3:
                unfitted += 1          # arc_steps too low to fit; counted, not hidden
                continue
            fit = _fit_circle(arcpts)
            if fit is None:
                bad += 1                                       # collinear "arc"
                continue
            cx, cz, r, resid = fit
            fitted += 1
            max_fit = max(max_fit, resid)
            a = _street_dir(pos[i - 1], pos[i], pts[i].attribValue("capc"), centre)
            b = _street_dir(pos[k], pos[(k + 1) % n], pts[k].attribValue("capc"),
                            centre)
            # §S5's radius rule for THIS corner: the lesser of the two streets'
            # class radii, then clamped by max_fillet_fraction of the shorter of
            # the two. Both the fitted circle and the solver's own `corner_r`
            # have to land on it.
            if edges:
                ra, la = _street_at(edges, pts[i].attribValue("capc"))
                rb, lb = _street_at(edges, pts[k].attribValue("capc"))
                want = min(ra, rb)
                half = math.acos(max(-1.0, min(1.0, a[0] * b[0] + a[2] * b[2]))) * 0.5
                tn = math.tan(half)
                run_max = max_fillet_fraction * min(la, lb)
                if tn > 1e-9 and run_max > 0 and want / tn > run_max:
                    want = run_max * tn
                if patch_geo.findPointAttrib("corner_r") is not None:
                    max_rad = max(max_rad,
                                  abs(pts[(i + 1) % n].attribValue("corner_r") - want))
                # The FITTED radius is only ever as trustworthy as the arc's
                # sweep. A fillet that turns 5 degrees has a 4 mm sagitta, so a
                # 2e-5 fit residual moves the fitted radius by ~15 mm and every
                # near-straight corner reads as a wrong radius while nothing is
                # wrong. Measured on C: three corners at 172-175 degrees, fitted
                # 4.0098 against an applied and expected 4.0000. So compare it
                # against the first-order conditioning bound, resid / (1 -
                # cos(sweep/2)), with a factor of 2, rather than a flat number.
                sweep = math.pi - 2.0 * half
                allow = max(radius_tol,
                            2.0 * resid / max(1.0 - math.cos(sweep * 0.5), 1e-9))
                max_radfit = max(max_radfit, abs(r - want) / allow)
            for (base, d) in ((pos[i], a), (pos[k], b)):
                perp = abs((cx - base[0]) * d[2] - (cz - base[2]) * d[0])
                max_tan = max(max_tan, abs(perp - r))

    value = {"straight": bad,
             "fit": round(max_fit, 7),
             "radius": round(max_rad, 7) if node_edges else None,
             "radius_fit": round(max_radfit, 3) if node_edges else None,
             "tangent": round(max_tan, 7),
             "unfitted": unfitted,
             "mixed_class": mixed}
    ok = (bad == 0 and max_fit <= fit_tol and max_tan <= tangent_tol
          and (not node_edges or (max_rad <= radius_tol and max_radfit <= 1.0)))
    return Result(name, ok, value,
                  "%d corners, %d arcs fitted; %d join two street classes, "
                  "where the lesser one sets the radius (S5)"
                  % (total, fitted, mixed))


def sidewalk_bands_match_corners(patch_geo, surface_geo, tol=1e-3):
    """Every live corner segment must produce exactly one sidewalk band.

    A shortfall here IS the visible notch at a junction corner, and it is the
    cheapest possible detector for the arc-fit bug returning.
    """
    if patch_geo.findPointAttrib("after_corner") is None:
        return _skip("sidewalk_bands_match_corners", "no after_corner attrib")
    live = 0
    for pr in patch_geo.prims():
        pts = list(pr.vertices())
        n = len(pts)
        for i in range(n):
            a = pts[i].point()
            b = pts[(i + 1) % n].point()
            if a.attribValue("after_corner") != 1:
                continue
            if (a.position() - b.position()).length() >= tol:
                live += 1
    bands = sum(1 for p in surface_geo.prims()
                if p.attribValue("elem_type") == "sidewalk")
    return Result("sidewalk_bands_match_corners", bands == live,
                  "%d/%d" % (bands, live), "bands vs live corner segments")


def junction_boundary_is_simple(patch_geo):
    """The boundary must not self-cross. capIn/capOut assigned by distance to
    the previous tangent flipped whenever that tangent was degenerate, and the
    polygon then zigzagged — a chord cut straight across the junction and read
    as a long kerb wall. Assignment must be by ANGLE."""
    bad = []
    for pr in patch_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        n = len(pts)
        cx = sum(p[0] for p in pts) / n
        cz = sum(p[2] for p in pts) / n
        angs = [math.atan2(p[2] - cz, p[0] - cx) for p in pts]
        # one clean loop => the wrapped deltas sum to +/- 2pi
        total = 0.0
        for i in range(n):
            d = angs[(i + 1) % n] - angs[i]
            while d > math.pi:
                d -= 2 * math.pi
            while d < -math.pi:
                d += 2 * math.pi
            total += d
        if abs(abs(total) - 2 * math.pi) > 0.2:
            bad.append(pr.number())
    return Result("junction_boundary_is_simple", not bad, len(bad),
                  "patches whose turning != 2pi: %s" % bad[:5] if bad else "")


# ---------------------------------------------------------------------------
# the S5 seam — where the junction patch meets the road
#
# Both of these test something NO single-node check can see. They exist because
# the 2026-08-09 audit found the road and the patch disagreeing about where the
# junction ends, and every per-node check passed the whole time.
# ---------------------------------------------------------------------------

def trim_metric_is_consistent(solve_geo, trimmed_geo, tol=0.05):
    """THE S5 SEAM: the road's terminal cross-section IS the mouth's cap segment.

    citygen_streets.md 4e-1. This used to measure a units mismatch — `s5j_solve`
    placed the mouth at `c + d*dist`, a straight-line AXIAL distance along the
    node tangent, while `s5j_trim` cut the street at `dist` measured as ARC
    LENGTH along the polyline. Same number, two metrics; the road stopped up to
    3.34 m short of the mouth it was cut for.

    RE-POINTED, because the fix removed the thing that formulation measured.
    `s5j_solve` now places the mouth on the polyline itself and solves the whole
    corner in that frame, so there is only one metric and comparing two of them
    is meaningless. §S5 named the replacement in advance: *"once both nodes
    measure axially it should assert the geometric seam — the trimmed road end
    lies on the mouth's cap segment"*.

    So: for every junction mouth, take the street it belongs to, find that
    street's TRIMMED terminal point and terminal tangent, build the road's own
    terminal cross-section (the end ± streetWidth/2 across that tangent) and
    measure how far its two endpoints land from the mouth's two cap corners.

    That is strictly stronger than the old test, because it sees ORIENTATION as
    well as position. The mouth used to be square to the node tangent while the
    road ended square to the polyline tangent up to 30.9° away, wedging a
    triangular hole up to 4.3 m deep open at every curved arm — 184 m² missing
    in B — and the axial-vs-arc number could not see any of it.
    """
    name = "trim_metric_is_consistent"
    if solve_geo.findPrimAttrib("junction_pt") is None:
        return _skip(name, "no junction_pt attrib")
    if solve_geo.findPrimAttrib("edge_id") is None:
        return _skip(name, "no edge_id attrib")
    surviving = {}
    for pr in trimmed_geo.prims():
        try:
            surviving[pr.attribValue("edge_id")] = pr
        except Exception:
            pass

    errs = []
    worst = None
    for pr in solve_geo.prims():
        try:
            if pr.attribValue("is_junction_patch") != 1:
                continue
            jp = int(pr.attribValue("junction_pt"))
        except Exception:
            continue
        pts = [v.point() for v in pr.vertices()]
        n = len(pts)
        # a mouth is the cap-in -> cap-out pair; both carry the same `capc`
        mouths = []
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            if (a.attribValue("is_cap") == 1 and a.attribValue("after_corner") == 0
                    and b.attribValue("is_cap") == 1
                    and b.attribValue("after_corner") == 1):
                mouths.append((a.attribValue("capc"), a.position(), b.position()))
        if not mouths:
            continue
        node = solve_geo.point(jp).position()
        for e in solve_geo.point(jp).prims():
            try:
                if e.attribValue("is_junction_patch") == 1:
                    continue
                road = surviving.get(e.attribValue("edge_id"))
            except Exception:
                continue
            if road is None:
                continue          # deleted street: every_mouth_has_a_road owns that
            rp = [v.point().position() for v in road.vertices()]
            if len(rp) < 2:
                continue
            if (rp[0] - node).length() <= (rp[-1] - node).length():
                end, nb = rp[0], rp[1]
            else:
                end, nb = rp[-1], rp[-2]
            d = nb - end
            d = type(end)(d[0], 0.0, d[2])
            if d.length() < 1e-12:
                continue
            d = d.normalized()
            across = type(end)(-d[2], 0.0, d[0])
            h = e.attribValue("streetWidth") * 0.5
            p1, p2 = end - across * h, end + across * h
            capc, c1, c2 = min(mouths, key=lambda m: (type(end)(m[0]) - end).length())
            err = max(min((p1 - c1).length(), (p1 - c2).length()),
                      min((p2 - c1).length(), (p2 - c2).length()))
            errs.append(err)
            if worst is None or err > worst[0]:
                # a LIST, not a tuple: this lands in baseline.json and comes
                # back as a list, so a tuple reports as "moved" on every run
                worst = (err, [round(end[0], 2), round(end[2], 2)])
    if not errs:
        return _skip(name, "no trimmed ends")
    mx = max(errs)
    value = {"max": round(mx, 4),
             "mean": round(sum(errs) / len(errs), 4),
             "ends": len(errs),
             "over_0.05m": sum(1 for e in errs if e > 0.05),
             "worst_at": worst[1]}
    return Result(name, mx <= tol, value,
                  "road terminal cross-section vs mouth cap corners; both "
                  "endpoints must land within %.3g m" % tol)


def every_mouth_has_a_road(solve_geo, trimmed_geo):
    """A junction mouth whose street no longer exists: paved stub onto nothing.

    citygen_streets.md 4e-3. `pfsj_fillet` has no radius clamp (line 83 is
    `radius_used = radius;`) so cuts reach 26 m, and `s5j_trim` then deletes any
    street whose two trims consume it — `ts + te >= L*0.98`. The junction patch
    was already built with a mouth for that street and keeps it. What ships is a
    carriageway opening onto grass.

    Deletion happens four nodes downstream of the emission, which is exactly the
    shape of defect the audit named "a feature reported done that never reached
    the output": assert the OUTPUT, not the intent. Identity is matched by
    `edge_id`, not position, so a street that merely moved is not mistaken for
    one that vanished.
    """
    name = "every_mouth_has_a_road"
    if solve_geo.findPrimAttrib("junction_pt") is None:
        return _skip(name, "no junction_pt attrib")
    if solve_geo.findPrimAttrib("edge_id") is None:
        return _skip(name, "no edge_id attrib")
    surviving = set()
    for pr in trimmed_geo.prims():
        try:
            surviving.add(pr.attribValue("edge_id"))
        except Exception:
            pass
    missing, mouths = 0, 0
    for pr in solve_geo.prims():
        try:
            if pr.attribValue("is_junction_patch") != 1:
                continue
            jp = int(pr.attribValue("junction_pt"))
        except Exception:
            continue
        for e in solve_geo.point(jp).prims():
            try:
                if e.attribValue("is_junction_patch") == 1:
                    continue
                mouths += 1
                if e.attribValue("edge_id") not in surviving:
                    missing += 1
            except Exception:
                pass
    return Result(name, missing == 0, missing,
                  "mouths whose street s5j_trim deleted, out of %d" % mouths)


def dead_ends(graph_geo, margin=25.0):
    """Dead ends, split by whether they sit on the edge of the traced domain.

    Parish & Müller: "in traffic systems the dead end road is the exception".
    A dead end AT the domain boundary is the domain being cut off, not a defect;
    an INTERIOR one is a street that stops in the middle of the city, and that
    is what §S2 `d_lookahead` and §S3 extend-to-connect exist to remove.

    Informational, with no pass threshold: there is no correct number, only a
    direction of travel. It is recorded because a bare count is exactly what
    caught extend-to-connect case (b) never executing (§4g-1) — the mechanism
    shipped, the suite was green, and the number had not moved.
    """
    bb = graph_geo.boundingBox()
    lo, hi = bb.minvec(), bb.maxvec()
    total = interior = 0
    for p in graph_geo.points():
        deg = 0
        for pr in p.prims():
            vs = list(pr.vertices())
            for i in (0, len(vs) - 1):
                if vs[i].point().number() == p.number():
                    deg += 1
        if deg != 1:
            continue
        total += 1
        q = p.position()
        if (q[0] - lo[0] > margin and hi[0] - q[0] > margin
                and q[2] - lo[2] > margin and hi[2] - q[2] > margin):
            interior += 1
    return Result("dead_ends", True, {"total": total, "interior": interior},
                  "informational; interior ones are the ones S2/S3 must remove")


def no_sweep_fold_after_trim(trimmed_geo, tol=1.0):
    """The CAUSE behind C's `no_downward_faces` — a fold, not plaza residue.

    citygen_streets.md 4e-7. `s5j_trim` snaps the straddling point onto the cut
    and leaves its neighbour microns away: 0.036 m and 0.022 m segments against
    a 7.2 m half-width. Sweeping a 7.2 m ribbon along that folds it, and the
    folded quads are what `no_downward_faces` reports. A and B are clean by
    luck, so a check on the symptom only ever fires for C.

    The test is the standard offset-fold condition, not a magic minimum length:
    at a vertex turning by theta, the offset edge at half-width h is pushed back
    `h*tan(theta/2)` along each neighbouring segment, so the ribbon crosses
    itself once that exceeds the segment. Ratio > 1 means the sweep folds.

    Written this way it separates cause from coincidence: B has segments down to
    0.25 m and passes, because they are straight and a straight short segment
    sweeps perfectly well. Only short-AND-turning fails.
    """
    name = "no_sweep_fold_after_trim"
    worst, over, minseg = 0.0, 0, 1e30
    for pr in trimmed_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        try:
            h = pr.attribValue("streetWidth") * 0.5
        except Exception:
            h = 1.0
        for i in range(len(pts) - 1):
            minseg = min(minseg, (pts[i + 1] - pts[i]).length())
        for i in range(1, len(pts) - 1):
            e1, e2 = pts[i] - pts[i - 1], pts[i + 1] - pts[i]
            l1, l2 = e1.length(), e2.length()
            if l1 < 1e-12 or l2 < 1e-12:
                over += 1
                worst = 1e9
                continue
            d = max(-1.0, min(1.0, (e1 / l1).dot(e2 / l2)))
            ratio = h * math.tan(math.acos(d) * 0.5) / min(l1, l2)
            worst = max(worst, ratio)
            if ratio > tol:
                over += 1
    if minseg > 1e29:
        return _skip(name, "no centreline segments")
    value = {"max_ratio": round(worst, 3), "folds": over,
             "min_seg": round(minseg, 4)}
    return Result(name, over == 0, value,
                  "h*tan(turn/2) / segment; > %.2g means the swept ribbon "
                  "crosses itself" % tol)


def plaza_disc_is_clear(block_geo, graph_geo, cx, cz, radius,
                        area_frac=0.01, gap_tol=0.75, samples=160):
    """A declared plaza that ships as ordinary city blocks.

    citygen_streets.md 4e-2. The tracer emits the plaza ring correctly at
    r = 60 exactly, but the stop test `break`s BEFORE appending the point that
    entered the plaza, so streets end at r = 62.5–66.0 instead. That 2.5–6 m gap
    is wider than `graph_fuse` (0.5 m) or `graph_stitch` (0.75 m) can close and
    S3 extend-to-connect does not exist yet, so the ring ends up with no
    degree->=3 node and `graph_drop_orphans` deletes it four nodes downstream.

    This is the "reported done, never reached the output" defect: the emission
    was correct and the metric that supposedly proved it had improved for an
    unrelated reason (the seed/trace exclusion). So assert the OUTPUT — that the
    declared disc is not built over — rather than that the ring was emitted.

    Two numbers, because either alone can be gamed: `built` is the block area
    inside the disc (a plaza with buildings on it is not a plaza), and `gap` is
    how far the nearest street end stops short of the boundary (streets must be
    trimmed TO the plaza edge, S5 "plazas and roundabouts").

    The area is rasterised rather than clipped: blocks are non-convex, and
    clipping a non-convex polygon is the very thing that produces the bowties in
    `lots_are_simple_polygons`.
    """
    name = "plaza_disc_is_clear"
    if radius <= 0:
        return _skip(name, "no plaza declared")
    polys = []
    for pr in block_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        if len(pts) < 3:
            continue
        xs = [p[0] for p in pts]
        zs = [p[2] for p in pts]
        polys.append((pts, min(xs), max(xs), min(zs), max(zs)))

    def inside(px, pz, pts):
        hit = False
        n = len(pts)
        j = n - 1
        for i in range(n):
            if (pts[i][2] > pz) != (pts[j][2] > pz):
                x = ((pts[j][0] - pts[i][0]) * (pz - pts[i][2])
                     / (pts[j][2] - pts[i][2]) + pts[i][0])
                if px < x:
                    hit = not hit
            j = i
        return hit

    step = 2.0 * radius / samples
    cell = step * step
    built = 0.0
    r2 = radius * radius
    for a in range(samples):
        px = cx - radius + (a + 0.5) * step
        for b in range(samples):
            pz = cz - radius + (b + 0.5) * step
            if (px - cx) ** 2 + (pz - cz) ** 2 > r2:
                continue
            for (pts, x0, x1, z0, z1) in polys:
                if px < x0 or px > x1 or pz < z0 or pz > z1:
                    continue
                if inside(px, pz, pts):
                    built += cell
                    break

    ends = []
    for pr in graph_geo.prims():
        vs = list(pr.vertices())
        if len(vs) < 2:
            continue
        for p in (vs[0].point(), vs[-1].point()):
            q = p.position()
            ends.append(math.hypot(q[0] - cx, q[2] - cz))
    gap = (min(ends) - radius) if ends else None

    disc = math.pi * radius * radius
    value = {"built": round(built, 1), "disc": round(disc, 1),
             "gap": None if gap is None else round(gap, 2)}
    ok = built <= disc * area_frac and (gap is not None and gap <= gap_tol)
    return Result(name, ok, value,
                  "block area inside the declared plaza, and how far the "
                  "nearest street end stops short of its edge")


# ---------------------------------------------------------------------------
# blocks and lots
# ---------------------------------------------------------------------------

def lots_tile_blocks(lot_geo, block_geo, rel_tol=1e-4):
    """Lot area must equal block area. A subdivision partitions its block."""
    la = sum(abs(p.intrinsicValue("measuredarea")) for p in lot_geo.prims())
    ba = sum(abs(p.intrinsicValue("measuredarea")) for p in block_geo.prims())
    if ba <= 0:
        return _skip("lots_tile_blocks", "no block area")
    err = abs(la - ba) / ba
    return Result("lots_tile_blocks", err <= rel_tol, round(err, 9),
                  "relative area error (lots %.1f vs blocks %.1f)" % (la, ba))


def no_duplicate_lot_footprints(lot_geo, tol=2):
    """VoronoiFracture 2.0 emits BOTH its `inside` and `outside` groups, so
    every duplicated parcel shipped twice with an identical footprint. That was
    the entire 'lots overlap' finding: B +18.9%, C +36.5% double coverage."""
    seen = collections.Counter()
    for p in lot_geo.prims():
        vs = list(p.vertices())
        cx = round(sum(v.point().position()[0] for v in vs) / len(vs), tol)
        cz = round(sum(v.point().position()[2] for v in vs) / len(vs), tol)
        seen[(cx, cz, len(vs))] += 1
    dupes = sum(c - 1 for c in seen.values() if c > 1)
    return Result("no_duplicate_lot_footprints", dupes == 0, dupes,
                  "%d prims, %d distinct footprints" % (len(lot_geo.prims()), len(seen)))


def lot_aspect_ratio(lot_geo, max_ratio=5.0, viable_only=True):
    """Ribbons, not rectangles. Parcels 6.2 m wide and 62 m deep ship viable.

    citygen_streets.md 4e-4. OBB aspect ratio measured median ~4:1, p90 9:1,
    max 31.5:1. The force-street-access swap in `lots_subdiv` recurses with no
    depth limit, driving frontage down towards `min_frontage` while never
    touching depth, so the split that "fixes" access is the one that makes the
    ribbon.

    S8 names "maximum aspect ratio" and "minimum width at the frontage" among
    the viability tests and implements NEITHER, which is why 10:1 ribbons carry
    `lot_viable = 1`. The doc gives no number, so the suite pins one here:
    `max_ratio` is the knob, and moving it is a design decision, not a fix.

    Aspect is taken from the minimum-area oriented box, not the axis-aligned
    one — a diagonal ribbon has a perfectly square AABB.
    """
    name = "lot_aspect_ratio"
    ratios = []
    for pr in lot_geo.prims():
        if viable_only:
            try:
                if pr.attribValue("lot_viable") != 1:
                    continue
            except Exception:
                pass
        pts = [v.point().position() for v in pr.vertices()]
        if len(pts) < 3:
            continue
        lng, shrt = _obb(pts)
        if shrt < 1e-9:
            continue
        ratios.append(lng / shrt)
    if not ratios:
        return _skip(name, "no lots with an OBB")
    ratios.sort()
    over = sum(1 for r in ratios if r > max_ratio)
    value = {"max": round(ratios[-1], 2),
             "median": round(ratios[len(ratios) // 2], 2),
             "p90": round(ratios[int(len(ratios) * 0.9)], 2),
             "over": over, "lots": len(ratios)}
    return Result(name, over == 0, value,
                  "OBB long/short on %s lots; S8 viability caps it at %.1f:1"
                  % ("viable" if viable_only else "all", max_ratio))


def lots_are_simple_polygons(lot_geo, tol=1e-3):
    """Bowtie parcels: two lobes joined by a zero-width bridge.

    citygen_streets.md 4e-5. `pfsl_clip` is Sutherland-Hodgman, whose output is
    only guaranteed simple for a CONVEX subject. Its comment claims a mildly
    concave block "degrades gracefully"; in fact every block is non-convex
    (2/2, 9/9, 13/13, up to 291 reflex vertices), and the clip then walks out
    along one lobe, back down the same line, and out along another.

    This needs its own check because the numeric ones cannot see it:
    `lots_tile_blocks` passes to 1e-8 because the bridge has ZERO AREA, and
    `no_duplicate_lot_footprints` compares centroids, which a bowtie shares with
    nothing. Exactly the defect class that hides behind aggregate numbers.

    The predicate is "the boundary is not simple": any vertex lying on a
    non-adjacent edge. That covers the pinch (a repeated vertex) and a true
    crossing alike, and unlike a parametric crossing test it is stated in
    metres. `tol` = 1 mm sits on a plateau — the counts are stable from 1e-4 to
    1e-2 m — comfortably above float32 P quantisation (~6e-5 m at the domain
    edge) and far below any real parcel feature.
    """
    name = "lots_are_simple_polygons"
    bad, viable = 0, 0
    for pr in lot_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        n = len(pts)
        if n < 4:
            continue
        hit = False
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            for j in range(n):
                if j == i or j == (i + 1) % n or (j + 1) % n == i:
                    continue                      # shares a vertex with this edge
                if _seg_point_dist(a, b, pts[j]) < tol:
                    hit = True
                    break
            if hit:
                break
        if not hit:
            continue
        bad += 1
        try:
            if pr.attribValue("lot_viable") == 1:
                viable += 1
        except Exception:
            pass
    return Result(name, bad == 0, {"lots": bad, "viable": viable},
                  "self-touching parcels within %.3g m (%d of them ship as "
                  "buildable)" % (tol, viable))


# What a lot legitimately carries out of the asset: its own S8 measurements,
# plus the section-6 identity attributes that must survive to final geometry.
# Everything else on OUT_lots is inherited block/graph scratch.
LOT_PRIM_ATTRS = ("block_id", "lot_id", "lot_type", "lot_area", "lot_frontage",
                  "lot_viable", "land_use", "region_id", "source_node", "layer")
LOT_POINT_ATTRS = ("P",)


def no_scratch_attribs(geo, prim_allowed=(), point_allowed=("P",),
                       detail_allowed=(), name="no_scratch_attribs"):
    """Working ATTRIBUTES leak out of the asset; `no_scratch_groups` only ever
    checked groups.

    citygen_streets.md 4e-10. OUT_lots ships `lot_reject`, `is_block`, `centre`,
    `area`, `frontage`, `keep_component`, `restlength`, `streetWidth`,
    `street_class`, `edge_id` and more — the whole graph-edge schema, inherited
    down the blocks branch, plus the intermediate measurements of three
    different stages. A consumer cannot tell which of `area` / `lot_area` and
    `frontage` / `lot_frontage` is authoritative, and a group-name collision
    already corrupted a stage here once (see `no_scratch_groups`); the same
    hazard applies to attribute names.

    `lot_reject` is listed as leakage per the audit even though the wrangle that
    writes it treats it as an advisory explanation — the allow-list above is one
    line to change if that call goes the other way.
    """
    leaked = []
    for a in geo.primAttribs():
        if a.name() not in prim_allowed:
            leaked.append("pr." + a.name())
    for a in geo.pointAttribs():
        if a.name() not in point_allowed:
            leaked.append("pt." + a.name())
    for a in geo.globalAttribs():
        if a.name() not in detail_allowed:
            leaked.append("dt." + a.name())
    return Result(name, not leaked, len(leaked), ", ".join(sorted(leaked)))


# ---------------------------------------------------------------------------
# schema — citygen_streets.md section 6
# ---------------------------------------------------------------------------

EDGE_ATTRS = ("edge_id", "street_class", "street_template", "streetWidth",
              "sidewalkWidthLeft", "sidewalkWidthRight", "laneWidth",
              "connectionStart", "connectionEnd", "layer", "region_id",
              "land_use", "source_node",
              # the S3b solver's own verdict. In the schema table (section 6)
              # because a downstream `attribdelete` was shown to make
              # `centreline_curvature_within_class` report not_converged: 0 and
              # PASS — the check reads it defensively, so nothing else noticed
              # the attribute had stopped shipping.
              "turn_clamp_converged")
ROAD_POINT_ATTRS = ("elem_type", "elem_index", "u_cross", "drivable", "walkable")


def attribute_schema(graph_geo, road_geo):
    """Conformance with the schema table. Identity must survive to the final
    geometry, not merely exist at generation time (citygen.md Contract 2)."""
    missing = []
    for a in EDGE_ATTRS:
        if graph_geo.findPrimAttrib(a) is None:
            missing.append("edge." + a)
    for a in ROAD_POINT_ATTRS:
        if road_geo.findPointAttrib(a) is None:
            missing.append("road." + a)
    return Result("attribute_schema", not missing, len(missing),
                  ", ".join(missing))


# ---------------------------------------------------------------------------
# self-intersection, per component
# ---------------------------------------------------------------------------

def self_intersections(node, label="self_intersections", expect=0, output=0):
    """Intersection Analysis reports 0 for a valid box, grid and kerb step —
    verified by control test — so a non-zero count is a REAL crossing, not mesh
    adjacency. Beware micron-scale non-planarity: see no_nonplanar_y.

    Creating the analysis node steals the display flag from whatever held it, so
    the previous holder is recorded and restored: an audit that leaves flags off
    makes the next pass diagnose a scene it did not build."""
    parent = node.parent()
    shown = None
    for c in parent.children():
        try:
            if c.isDisplayFlagSet():
                shown = c
                break
        except Exception:
            pass
    ia = parent.createNode("intersectionanalysis", "__chk_ia")
    try:
        ia.setInput(0, node, output)
        ia.cook(force=True)
        n = len(ia.geometry().points())
    except Exception as exc:
        ia.destroy()
        return _skip(label, "could not cook: %s" % str(exc)[:60])
    finally:
        try:
            ia.destroy()
        except Exception:
            pass
        if shown is not None:
            try:
                shown.setDisplayFlag(True)
            except Exception:
                pass
    return Result(label, n <= expect, n, "intersection points")


def merged_city_self_intersections(city_node, expect=0):
    """THE gap. Roads and junction patches interpenetrate at every junction and
    the suite could not see it, because nothing tested the union.

    citygen_streets.md 4e-1, and the reason RULE 0 of the houdini-dev-loop skill
    exists. `selfx_junction_surface` cooks Intersection Analysis on the junction
    patch alone and reports 0. `selfx_roads` cooks it on the roads alone and
    reports 0. Both were green through four commits while the merged city — the
    thing that actually ships — carried 102 / 529 / 863 intersection points.
    Two green per-component checks, one broken seam, no signal.

    Output 0 of the asset is `city_merge2`: roads, junction surface, bridge
    piers and lots. Asserting on it also covers 4e-9 (lots overhanging junction
    surfaces), which is why its count is higher than roads+patches alone.
    """
    return self_intersections(city_node, "selfx_city_merged", expect, output=0)


# ---------------------------------------------------------------------------
# coverage: is there any part of the city that nothing paves?
# ---------------------------------------------------------------------------

def _raster_grid(geos, cell, pad=4.0):
    xs, zs = [], []
    for g in geos:
        b = g.boundingBox()
        xs += [b.minvec()[0], b.maxvec()[0]]
        zs += [b.minvec()[2], b.maxvec()[2]]
    x0, z0 = min(xs) - pad, min(zs) - pad
    nx = int(math.ceil((max(xs) + pad - x0) / cell)) + 1
    nz = int(math.ceil((max(zs) + pad - z0) / cell)) + 1
    return x0, z0, nx, nz, cell


def _rasterise(np, geo, grid, prim_filter=None):
    """Even-odd fill of every polygon in `geo` onto a boolean XZ grid."""
    x0, z0, nx, nz, cell = grid
    cov = np.zeros((nz, nx), dtype=bool)
    for pr in geo.prims():
        if prim_filter is not None and not prim_filter(pr):
            continue
        vs = pr.vertices()
        if len(vs) < 3:
            continue
        P = np.array([(v.point().position()[0], v.point().position()[2])
                      for v in vs], dtype=np.float64)
        i0 = max(0, int(math.floor((P[:, 0].min() - x0) / cell)))
        i1 = min(nx - 1, int(math.ceil((P[:, 0].max() - x0) / cell)))
        j0 = max(0, int(math.floor((P[:, 1].min() - z0) / cell)))
        j1 = min(nz - 1, int(math.ceil((P[:, 1].max() - z0) / cell)))
        if i1 < i0 or j1 < j0:
            continue
        X, Z = np.meshgrid(x0 + (np.arange(i0, i1 + 1) + 0.5) * cell,
                           z0 + (np.arange(j0, j1 + 1) + 0.5) * cell)
        inside = np.zeros(X.shape, dtype=bool)
        n = len(P)
        for k in range(n):
            ax, az = P[k]
            bx, bz = P[(k + 1) % n]
            if az == bz:
                continue
            inside ^= ((az > Z) != (bz > Z)) & (X < (bx - ax) * (Z - az) / (bz - az) + ax)
        cov[j0:j1 + 1, i0:i1 + 1] |= inside
    return cov


def _blobs(np, mask, grid, min_area):
    """Connected components of a boolean mask as (area, cx, cz), largest first.

    Run-length union-find rather than an iterative dilation: a 900 x 900 grid
    needs ~1000 dilation passes to propagate across the city and one pass over
    the runs to label it."""
    x0, z0, nx, nz, cell = grid
    parent = {}

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    rows, rid = [], 0
    for j in range(nz):
        d = np.diff(np.concatenate(([0], mask[j].view(np.int8), [0])))
        rr = []
        for s, e in zip(np.flatnonzero(d == 1), np.flatnonzero(d == -1)):
            parent[rid] = rid
            rr.append((s, e, rid))
            rid += 1
        if j:
            for s, e, i in rr:
                for ps, pe, pi in rows[j - 1]:
                    if ps < e and s < pe:
                        ra, rb = find(i), find(pi)
                        if ra != rb:
                            parent[rb] = ra
        rows.append(rr)
    comp = {}
    for j, rr in enumerate(rows):
        for s, e, i in rr:
            c = comp.setdefault(find(i), [0, 0.0, 0.0])
            n = e - s
            c[0] += n
            c[1] += (s + e - 1) * 0.5 * n
            c[2] += j * n
    out = []
    for n, sx, sz in comp.values():
        a = float(n) * cell * cell
        if a >= min_area:
            # plain floats in a LIST, not numpy scalars in a tuple: this lands
            # in baseline.json, and a tuple comes back as a list, so the runner
            # would report the value as "moved" on every single run
            out.append([round(a, 1), round(float(x0 + (sx / n + 0.5) * cell), 2),
                        round(float(z0 + (sz / n + 0.5) * cell), 2)])
    out.sort(reverse=True)
    return out


def block_boundary_closes(kerb_node, loops_node):
    """S7's collect-and-close invariant, which nothing else asserts.

    The block boundary is assembled from open polylines — street frontage runs,
    junction corner runs, dead-end caps — whose endpoints coincide exactly two
    at a time, so every joined point has degree 2 and PolyPath falls out into
    closed loops. PolyPath is a pure topological join: it cannot enforce that
    precondition, and if the precondition fails it silently emits an OPEN chain,
    which then ships as a block or as the outer boundary depending on the sign
    of a meaningless signed area.

    An audit broke it twice in one sitting using rail values that were shipping
    three commits earlier: `graph_params_min_node_dist` 40 → 30 puts the S5 seam
    at 0.383 m, past the 0.25 m radius `blocks_kerb` searches for a cap corner,
    and C came out with 4 open loops of which 3 shipped as blocks;
    `graph_prune_min_edge_len` 13 → 8 leaves B with two mouths that have no road,
    and a 10,477 m² block vanished. `lots_tile_blocks` and
    `lots_clear_of_junctions` stayed green through both.

    Two assertions, both cheap:
      * after the fuse, every run END coincides with exactly one other run end —
        multiplicity 2, never 1 (nothing to join to) and never 3 (a T, which
        PolyPath cannot resolve);
      * every loop out of PolyPath is closed and has at least 3 vertices.

    Counted over run ENDS, not point vertex counts: a polyline references each of
    its points from exactly one vertex, interior ones included, so a vertex count
    says nothing about whether two runs met.
    """
    name = "block_boundary_closes"
    if kerb_node is None or loops_node is None:
        return _skip(name, "S7 kerb nodes missing")
    kg, lg = kerb_node.geometry(), loops_node.geometry()
    seen = collections.Counter()
    for pr in kg.prims():
        n = pr.numVertices()
        if pr.intrinsicValue("closed"):
            continue                       # a ring street closes on itself
        for vi in (0, n - 1):
            seen[pr.vertex(vi).point().number()] += 1
    bad = collections.Counter(v for v in seen.values() if v != 2)
    open_loops = sum(1 for pr in lg.prims()
                     if not pr.intrinsicValue("closed") or pr.numVertices() < 3)
    value = {"unpaired_ends": sum(bad.values()), "multiplicity": dict(bad),
             "open_loops": open_loops, "loops": len(lg.prims())}
    return Result(name, not bad and not open_loops, value,
                  "every kerb run end must meet exactly one other and every "
                  "loop must close; an open chain still ships as a block")


# --- mirror of pfsg_turn_ceilings in pf_streetgraph.vfl ---------------------
# Kept in step with the VEX by hand, which is a real cost and is paid on
# purpose. `max_turn_spike` used to READ the solver's own `turn_smooth_ratio`
# attribute, which made the detector and the fix the same code: it reported
# whatever the solver believed when it stopped, it could not see anything the
# clamp did afterwards, and because the solver stops at tol = 1.01 against this
# check's 1.02 slack it carried exactly one bit -- A, B, C and D all read a flat
# 1.01. Recomputing it from the shipped centreline is the same discipline
# `max_kappa_over_clamp` already follows, and it is what makes a spike that
# survives to the output visible.
_SMOOTH_W = 3
_SMOOTH_FLOOR = 0.25


def _turn_ceilings(pts, rmin, gain, closed):
    """Per-vertex turn (radians) and its ceiling, from geometry alone.

    Returns (phi, ceiling); either list holds None where the vertex has no turn
    to bound. `gain <= 0` gives ceiling == the class allowance, so the spike
    residual degenerates to `max_kappa_over_clamp` exactly -- by construction,
    not by coincidence.
    """
    n = len(pts)
    phi = [0.0] * n
    cls = [None] * n
    rng = list(range(n)) if closed else list(range(1, n - 1))
    for i in rng:
        e1 = pts[i] - pts[(i - 1) % n]
        e2 = pts[(i + 1) % n] - pts[i]
        l1, l2 = e1.length(), e2.length()
        if l1 < 1e-9 or l2 < 1e-9:
            continue
        d = max(-1.0, min(1.0, (e1 / l1).dot(e2 / l2)))
        phi[i] = math.acos(d)
        cls[i] = 0.5 * (l1 + l2) / rmin
    ceil = [None] * n
    for i in rng:
        if cls[i] is None:
            continue
        if gain <= 0.0:
            ceil[i] = cls[i]
            continue
        window, s, c = [phi[i]], 0.0, 0
        for j in range(-_SMOOTH_W, _SMOOTH_W + 1):
            if j == 0:
                continue
            q = i + j
            if closed:
                q %= n
            elif q < 1 or q > n - 2:
                continue
            s += phi[q]
            c += 1
            window.append(phi[q])
        noise = gain * s / c if c else cls[i]
        level = sorted(window)[(len(window) - 1) // 2]
        ceil[i] = min(cls[i], max(noise, level, _SMOOTH_FLOOR * cls[i]))
    return phi, ceil


def centreline_curvature_within_class(graph_geo, scale_parm, slack=1.02,
                                      gain_parm=None):
    """No centreline may bend tighter than its class minimum curve radius.

    S3b. A node where two streets meet is a BEND, not a junction, and it is
    solved on the centreline — replace the sharp vertex with a tangent arc and
    the sweep follows, so the outer kerb comes out at R + halfwidth and the
    inner at R - halfwidth on their own. Built as 4f-4's curvature clamp,
    because a sharp turn is only curvature far over the clamp.

    ⚠️ Do NOT re-express this as a search for degree-2 nodes. `graph_polypath`
    merges the two edges into one polyline, so the corner is an interior shape
    vertex and an audit found zero degree-2 nodes in every case.

    R_min defaults to 2 x the street half-width (S3b's legible floor, ~27 m on a
    26.8 m arterial). Below 1 x half-width the inner kerb radius inverts and the
    ribbon folds, which is what `no_sweep_fold_after_trim` catches downstream.

    Measured on the polyline as it ships, so it is meaningless without the
    uniform resample ahead of the clamp: C's kink at (-80.56, -269.77) turns
    20.2 degrees between a 73.4 m segment and a 6 m one, and averaged over that
    arc length it reads as a gentle R = 113 m. Sampled at 4 m the same kink is
    R = 11 m.

    ⚠️ A LOW NUMBER HERE IS NOT THE SAME AS A SOLVED CENTRELINE, which is why
    `not_converged` is reported alongside it. The first clamp was a fixed
    200-sweep diffusion with no residual test, so it shipped whatever it had
    reached; on the 90 degree arterial bend that was kappa x R_min = 2.17, a
    12.4 m radius on a 13.4 m half-width. Every case in the suite only asked it
    for a few degrees, so this check read 1.000 on all five and the mechanism
    looked solved for as long as nobody drew a corner. Case F_bend does.

    Closed prims are measured all the way round, wrapping, because the clamp now
    solves them the same way — the two used to disagree, so the day the ring
    closure (011fdcb) put a closed prim back in the graph this would have fired
    with no mechanism able to clear it.
    """
    name = "centreline_curvature_within_class"
    # ⚠️ ABSENT IS NOT CONVERGED. Reading this per-prim inside a try/except made
    # the whole non-convergence half vanish silently the moment the attribute
    # stopped shipping — an audit proved it by putting an `attribdelete` between
    # the clamp and the output, and this reported not_converged: 0 and PASSED.
    if graph_geo.findPrimAttrib("turn_clamp_converged") is None:
        return Result(name, False, {"not_converged": None},
                      "the graph carries no turn_clamp_converged: the S3b "
                      "solver's verdict is not reaching the output")
    # ⚠️ ABSENT IS NOT SMOOTH either. The residual is recomputed below, but the
    # solver must still be shown to be REACHING the output — the same "follow it
    # to the output" rule the converged flag gets.
    if graph_geo.findPrimAttrib("turn_smooth_ratio") is None:
        return Result(name, False, {"max_turn_spike": None},
                      "the graph carries no turn_smooth_ratio: 4f-4's "
                      "curvature-noise residual is not reaching the output")
    scale = scale_parm.eval() if scale_parm is not None else 2.0
    gain = gain_parm.eval() if gain_parm is not None else 2.0
    worst, over, at = 0.0, 0, None
    spike, spike_at = 0.0, None
    unconverged = []
    for pr in graph_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        try:
            rmin = 0.5 * pr.attribValue("streetWidth") * scale
        except Exception:
            continue
        if rmin <= 1e-4:
            continue
        try:
            if pr.attribValue("turn_clamp_converged") == 0:
                unconverged.append(pr.number())
        except Exception:
            pass
        closed = bool(pr.intrinsicValue("closed"))
        n = len(pts)
        rng = range(n) if closed else range(1, n - 1)
        phi, ceil = _turn_ceilings(pts, rmin, gain, closed)
        for i in rng:
            e1 = pts[i] - pts[(i - 1) % n]
            e2 = pts[(i + 1) % n] - pts[i]
            l1, l2 = e1.length(), e2.length()
            if l1 < 1e-9 or l2 < 1e-9:
                continue
            d = max(-1.0, min(1.0, (e1 / l1).dot(e2 / l2)))
            # discrete curvature x R_min: 1.0 IS the clamp
            ratio = math.acos(d) / (0.5 * (l1 + l2)) * rmin
            if ratio > worst:
                worst, at = ratio, [round(pts[i][0], 2), round(pts[i][2], 2)]
            if ratio > slack:
                over += 1
            if ceil[i] is not None and ceil[i] > 1e-9:
                sr = phi[i] / ceil[i]
                if sr > spike:
                    spike = sr
                    spike_at = [round(pts[i][0], 2), round(pts[i][2], 2)]
    # ⚠️ A LOW kappa IS ALSO NOT THE SAME AS A SMOOTH CENTRELINE, and that is
    # what `max_turn_spike` is for. 4f-4's mechanism is "smooth kappa THEN clamp
    # to 1/R_min"; only the clamp was built, so C_radial's ring-closure seam came
    # out of it as a single-vertex 13.4 deg turn against a 2.5 deg median —
    # R = 16.9 m against R_min = 14.4 m. LEGAL BY RADIUS, so this check read
    # 0.852 and passed while the artist could see the corner in a 100 m radius
    # ring.
    #
    # It is recomputed above from the SHIPPED centreline rather than read off the
    # solver's `turn_smooth_ratio` attribute. Reading the attribute made this
    # blind to anything the pipeline does after the solver stops, and blind by
    # construction: the solver's own tol is 1.01 against this slack of 1.02, so
    # every converged prim reported "1.01 or less" and the check carried a single
    # bit. A, B, C and D all read a flat 1.010. The solver's own verdict is still
    # reported alongside, so the two disagreeing is visible rather than silent.
    solver = 0.0
    for pr in graph_geo.prims():
        solver = max(solver, pr.attribValue("turn_smooth_ratio"))
    return Result(name, over == 0 and not unconverged and spike <= slack,
                  {"max_kappa_over_clamp": round(worst, 3), "over": over,
                   "worst_at": at, "not_converged": len(unconverged),
                   "max_turn_spike": round(spike, 3), "spike_prim_at": spike_at,
                   "solver_turn_spike": round(solver, 3)},
                  "discrete curvature x R_min(class); > %.2f means the "
                  "centreline bends tighter than S3b allows, "
                  "not_converged means the solver said so itself, and "
                  "max_turn_spike is the same residual against 4f-4's "
                  "curvature-noise bound — a kink that is legal by radius — "
                  "recomputed from the shipped centreline, not read off the "
                  "solver" % slack)


def no_short_graph_segments(graph_geo, floor=1.0):
    """No segment of a shipped centreline may be shorter than `floor` metres.

    THE STATED FLOOR, and it is stated in three places that must agree: this
    check, `s5j_params_min_end_segment`, and `minseg` inside the S3b clamp.

    Two independent mechanisms have driven a centreline segment to nothing.
    4e-7: `s5j_trim`'s cut landing just short of a resample vertex left C a
    0.028 m and a 0.22 m terminal segment against a 7.2 m half-width, and the
    swept ribbon folded on both. And the first S3b clamp: `phimax` is
    proportional to (l1 + l2) and the correction shortens those very segments,
    so on a fold-back it drove one to 1.0e-6 m — a degenerate shipped output,
    reached by positive feedback with no lower bound.

    `no_sweep_fold_after_trim` only sees the second of those, and only after the
    trim. This looks at the graph as published, which is where the block
    boundary, the sweep and every downstream stage read it from.
    """
    name = "no_short_graph_segments"
    worst, count, at = None, 0, None
    for pr in graph_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        n = len(pts)
        if n < 2:
            continue
        rng = range(n) if pr.intrinsicValue("closed") else range(1, n)
        for i in rng:
            d = (pts[i % n] - pts[i - 1]).length()
            if worst is None or d < worst:
                worst, at = d, [round(pts[i % n][0], 2), round(pts[i % n][2], 2)]
            if d < floor:
                count += 1
    return Result(name, count == 0,
                  {"min_segment_m": None if worst is None else round(worst, 4),
                   "under": count, "worst_at": at},
                  "shortest centreline segment in the published graph; the "
                  "floor is %.2f m" % floor)


def trim_leaves_road_standing(streets_geo, floor=1.0):
    """A junction may never trim away the whole street it opens onto.

    `s5j_trim` deletes a street outright once `trim_start + trim_end >= 0.98 L`,
    and the junction patch keeps the mouth it already built — a carriageway
    opening onto grass, 4e-3. `every_mouth_has_a_road` catches that after the
    fact; this is the leading indicator, because the margin turned out to be
    thin and nothing was watching it.

    It was added when `pfsg_clear_of_vertex` was found able to consume a street
    on its own: when the cut landed within `min_end_segment` of the FAR end of
    the polyline the push evaluated to the street's whole length. Not triggered
    on any case, but B prim 29 is a 19.6 m local with 17.40 m trimmed — 2.18 m
    standing, 1.18 m from the cliff — and E_short_t's binding 20 m arm had
    already dropped from 4.80 m to 3.00 m. E exists to exercise
    `max_fillet_fraction`; it was 3 m from deleting its own reason to exist.
    """
    name = "trim_leaves_road_standing"
    # ⚠️ `trim_end` does not always EXIST. s5j_solve creates each of the two
    # attributes the first time it writes one, so a city whose every trim
    # happens to fall at a street's start ships with `trim_start` and no
    # `trim_end` at all — true of E_short_t and F_bend. Reading it as absent
    # rather than as zero silently skipped every prim in both cases, which
    # meant this check reported None for the two cases with the least road to
    # spare. Default the missing one; do not skip on it.
    have = [a for a in ("trim_start", "trim_end")
            if streets_geo.findPrimAttrib(a) is not None]
    if not have:
        return _skip(name, "no trim_start / trim_end attrib")
    worst, count, at = None, 0, None
    for pr in streets_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        if len(pts) < 2:
            continue
        L = sum((pts[i] - pts[i - 1]).length() for i in range(1, len(pts)))
        standing = L - sum(pr.attribValue(a) for a in have)
        if worst is None or standing < worst:
            worst, at = standing, [round(pts[0][0], 2), round(pts[0][2], 2)]
        if standing < floor:
            count += 1
    return Result(name, count == 0,
                  {"min_standing_m": None if worst is None else round(worst, 3),
                   "under": count, "worst_at": at},
                  "street length left after both junction trims; below %.2f m "
                  "s5j_trim is about to delete it under a live mouth" % floor)


def turn_clamp_control_rig(city_node, slack=1.02, floor=1.0):
    """Run the SHIPPED S3b clamp on the inputs that broke the first one.

    This is the only check in the suite that supplies its own geometry, and it
    exists because of a pattern this project has now repeated three times: a
    mechanism ships green because no case reaches its design amplitude. `offset`
    lot mode (4e-6) and `max_fillet_fraction` (4h-2) were the first two; the
    curvature clamp was the third, and it was delivering a 12.4 m radius on a
    13.4 m half-width while this suite reported 1.000 on all five cases.

    F_bend covers the feasible half of that through the real pipeline. Three
    things it cannot cover are here instead:

    **The infeasible half**, which cannot be a passing case by definition. A
    30 m square returning to within 4 m of its own start has no polyline through
    its pinned endpoints that satisfies R = 26.8 m and is still a street. The
    old solver's answer was to diverge — kappa x R_min 4.37 -> 22.7 (200 sweeps)
    -> 5320 (5000), ending with a 1.0e-6 m segment in the shipped graph. What is
    asserted is that it now says so: bounded, no collapsed segment, and
    `turn_clamp_converged` = 0 rather than a silent ship.

    **135 degrees**, the worst turn these legs can still absorb, because 90 was
    passing while 135 was not — the solved arc there sits hard on the clamp for
    its whole length and is much the harder solve.

    **All three kinds of closed prim**, because no case produces one at all.
    ⚠️ An audit caught the first version of this testing only the square ring —
    the one closed shape the mechanism happens to fix. A closed curve's total
    turning is 2 pi whatever its shape, so the only way to lower kappa on a
    ROUND ring is to make it longer, and every correction here pulls toward a
    chord, which shortens. `ring_tight` is therefore infeasible for a reason
    `ring_square` hides, and asserting all three is the difference between
    "closed prims are handled" and "closed prims are handled when they look
    like this one".

    **AND IT SWEEPS `turn_smooth_gain` OVER ITS WHOLE SHIPPED RANGE**, because
    the fourth instance of the same pattern was the gain itself. It shipped at
    the default 2 with a {0 8} slider and help text saying only "0 disables it";
    at 0.5 and at 1.0 — the first two values anyone reaching for "less
    smoothing" will try — the suite went 17 -> 25 failing, this rig among them.
    The cause was that the bound compared a vertex against the mean of its
    neighbours WITH ITSELF EXCLUDED, so below gain 1 every vertex of a correctly
    fitted arc was over by construction and the solver spent its whole budget
    flattening geometry that was already right. `ring_legal` came back
    bit-identical throughout and was read as proof that uniform curvature was a
    fixed point; it is not, it clears the bound through the floor. Sweeping the
    parameter is the only thing that would have caught it, so the sweep is the
    check. Adding a parameter means adding a case.

    It copies the real `graph_turn_clamp` node so it cannot drift from what
    ships, and destroys everything it made — an audit that leaves scratch nodes
    or display flags behind makes the next pass diagnose a scene it did not
    build.
    """
    name = "turn_clamp_control_rig"
    clamp = city_node.node("graph_turn_clamp")
    if clamp is None:
        return _skip(name, "graph_turn_clamp not found")
    shown = next((c for c in city_node.children() if c.isDisplayFlagSet()), None)
    made = []
    shipped_gain = city_node.parm("graph_params_turn_smooth_gain").eval()
    # every value in the shipped {0 8} range that a slider makes easy to land on
    gains = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0)
    try:
        src = city_node.createNode("python", "__chk_rig_src")
        made.append(src)
        src.parm("python").set(_RIG_SNIPPET)
        w = clamp.copyTo(city_node)
        made.append(w)
        w.setInput(0, src)
        base = w.parm("snippet").rawValue()
        # ⚠️ The gain is overridden by REWRITING THE COPY'S SNIPPET, not by
        # touching the city's parameter — setting the real parm would recook the
        # entire city twice per gain. The substitution is asserted below: if the
        # wrangle ever stops reading the gain from this channel the rig fails
        # loudly instead of silently sweeping one value six times.
        chan = 'chf("../graph_params/turn_smooth_gain")'
        if chan not in base:
            raise RuntimeError("graph_turn_clamp no longer reads %s" % chan)
        sweep = {}
        for gain in gains:
            w.parm("snippet").set(base.replace(chan, "%.6f" % gain))
            w.cook(force=True)
            sweep[gain] = _rig_measure(w.geometry(), src.geometry(), city_node)
        got = sweep[shipped_gain] if shipped_gain in sweep else None
        if got is None:
            w.parm("snippet").set(base)
            w.cook(force=True)
            got = _rig_measure(w.geometry(), src.geometry(), city_node)
    except Exception as exc:
        # ⚠️ FAIL, do not skip. This used to `_skip`, and `_skip` sets ok=True —
        # so deleting the `turn_clamp_converged` write, which makes this raise,
        # turned a hard regression into a silent pass that the runner does not
        # even count. An audit found it by doing exactly that. A rig that cannot
        # run is a failure of the thing it is testing.
        return Result(name, False, {"error": str(exc)[:160]},
                      "the control rig could not be run at all")
    finally:
        for nd in reversed(made):
            try:
                nd.destroy()
            except Exception:
                pass
        if shown is not None:
            try:
                shown.setDisplayFlag(True)
            except Exception:
                pass

    bad = {}
    for gain in gains:
        why = _rig_verdict(sweep[gain], slack, floor)
        if why:
            bad["%g" % gain] = why
    value = dict(got)
    value["gain_sweep"] = "all %d gains clean" % len(gains) if not bad else bad
    return Result(name, not bad and not _rig_verdict(got, slack, floor), value,
                  "feasible turns (90, 135, both drawn as arcs, square ring) "
                  "must converge inside the clamp with R above the half-width; "
                  "infeasible ones (fold-back, tight ring) must be flagged, not "
                  "diverged; a legal ring must be untouched — and all of that "
                  "at every turn_smooth_gain in the shipped range")


def _rig_measure(geo, src_geo, city_node):
    """One cook of the control rig, read back per rig polyline."""
    got = {}
    for pr in geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        n = len(pts)
        closed = bool(pr.intrinsicValue("closed"))
        rmin = 0.5 * pr.attribValue("streetWidth") * \
            city_node.parm("graph_params_turn_radius_scale").eval()
        worst = 0.0
        for i in (range(n) if closed else range(1, n - 1)):
            e1 = pts[i] - pts[(i - 1) % n]
            e2 = pts[(i + 1) % n] - pts[i]
            l1, l2 = e1.length(), e2.length()
            if l1 < 1e-9 or l2 < 1e-9:
                continue
            d = max(-1.0, min(1.0, (e1 / l1).dot(e2 / l2)))
            worst = max(worst, math.acos(d) / (0.5 * (l1 + l2)) * rmin)
        was = [v.point().position() for v in src_geo.prims()[pr.number()].vertices()]
        moved = max((pts[i] - was[i]).length() for i in range(n))
        got[pr.attribValue("rig")] = {
            "kappa": round(worst, 4),
            "R_delivered": round(rmin / max(worst, 1e-9), 2),
            "half_width": round(0.5 * pr.attribValue("streetWidth"), 2),
            "min_seg": round(min((pts[i] - pts[(i - 1) % n]).length()
                                 for i in (range(n) if closed
                                           else range(1, n))), 4),
            "converged": int(pr.attribValue("turn_clamp_converged")),
            "sweeps": int(pr.attribValue("turn_clamp_sweeps")),
            "moved": round(moved, 6)}
    return got


def _rig_verdict(got, slack, floor):
    """[] when every rig behaved; otherwise the rigs that did not, named."""
    want = ("bend90", "bend135", "bend135_r18", "bend90_r10", "foldback",
            "ring_legal", "ring_square", "ring_tight")
    missing = [k for k in want if k not in got]
    if missing:
        return ["missing:" + ",".join(missing)]

    def solved(r):
        return (r["converged"] == 1 and r["kappa"] <= slack
                and r["R_delivered"] > r["half_width"] and r["min_seg"] >= floor)

    def flagged(r, which):
        # infeasible: bounded no worse than the input, intact, and REPORTED
        return (r["converged"] == 0 and r["min_seg"] >= floor
                and r["kappa"] <= _RIG_INPUT_KAPPA[which] + 1e-3)

    bad = [k for k in ("bend90", "bend135", "bend135_r18", "bend90_r10",
                       "ring_square") if not solved(got[k])]
    bad += [k for k in ("foldback", "ring_tight")
            if not flagged(got[k], k)]
    # a ring already inside the clamp must come back BIT-IDENTICAL: the solver
    # may not touch geometry it has nothing to fix
    if not (got["ring_legal"]["converged"] == 1
            and got["ring_legal"]["sweeps"] == 0
            and got["ring_legal"]["moved"] == 0.0):
        bad.append("ring_legal")
    return bad


# kappa x R_min of the two infeasible rigs as authored. The solver may never
# ship a state WORSE than the input it was handed — that is what divergence
# looks like, and the first one went to 5320 on the fold-back.
_RIG_INPUT_KAPPA = {"foldback": 10.5243, "ring_tight": 1.3423}

_RIG_SNIPPET = '''
"""The two S3b control rigs, as geometry. See turn_clamp_control_rig()."""
import hou, math
g = hou.pwd().geometry()
g.clear()
g.addAttrib(hou.attribType.Prim, "streetWidth", 0.0)
g.addAttrib(hou.attribType.Prim, "edge_len", 0.0)
g.addAttrib(hou.attribType.Prim, "rig", "")


def poly(name, ctrl, step=4.0):
    """Uniform 4 m resample of a control polygon, matching graph_turn_resample."""
    acc = [0.0]
    for i in range(1, len(ctrl)):
        acc.append(acc[-1] + math.dist(ctrl[i - 1], ctrl[i]))
    L = acc[-1]
    n = max(1, int(L / step + 0.5))
    pr = g.createPolygon(is_closed=False)
    for k in range(n + 1):
        s = L * k / n
        j = 1
        while j < len(acc) - 1 and acc[j] < s:
            j += 1
        t = 0.0 if acc[j] == acc[j - 1] else (s - acc[j - 1]) / (acc[j] - acc[j - 1])
        pr.addVertex(g.createPoint()).point().setPosition(
            (ctrl[j - 1][0] + t * (ctrl[j][0] - ctrl[j - 1][0]), 0.0,
             ctrl[j - 1][1] + t * (ctrl[j][1] - ctrl[j - 1][1])))
    pr.setAttribValue("streetWidth", 26.8)      # arterial_median, half-width 13.4
    pr.setAttribValue("rig", name)


def _rounded(ctrl, radius, seg=2.0):
    """Replace each interior corner of `ctrl` with a tangent arc of `radius`,
    so the turn arrives as a RUN of vertices rather than one hard one."""
    out = [ctrl[0]]
    for i in range(1, len(ctrl) - 1):
        p, c, q = ctrl[i - 1], ctrl[i], ctrl[i + 1]
        d0 = (c[0] - p[0], c[1] - p[1])
        d1 = (q[0] - c[0], q[1] - c[1])
        n0, n1 = math.hypot(*d0), math.hypot(*d1)
        d0 = (d0[0] / n0, d0[1] / n0)
        d1 = (d1[0] / n1, d1[1] / n1)
        phi = math.atan2(d0[0] * d1[1] - d0[1] * d1[0], d0[0] * d1[0] + d0[1] * d1[1])
        t = radius * abs(math.tan(phi / 2.0))
        a = (c[0] - d0[0] * t, c[1] - d0[1] * t)
        bis = (d1[0] - d0[0], d1[1] - d0[1])
        nb = math.hypot(*bis)
        cen = (c[0] + bis[0] / nb * (radius / math.cos(abs(phi) / 2.0)),
               c[1] + bis[1] / nb * (radius / math.cos(abs(phi) / 2.0)))
        a0 = math.atan2(a[1] - cen[1], a[0] - cen[0])
        steps = max(2, int(abs(phi) * radius / seg))
        out.append(a)
        for k in range(1, steps + 1):
            ang = a0 + phi * k / float(steps)
            out.append((cen[0] + radius * math.cos(ang),
                        cen[1] + radius * math.sin(ang)))
    out.append(ctrl[-1])
    return out


def ring(name, ctrl, step=4.0):
    """`ctrl` is a closed control polygon, resampled at `step` like the poly()
    above; the first point is not repeated."""
    loop = list(ctrl) + [ctrl[0]]
    acc = [0.0]
    for i in range(1, len(loop)):
        acc.append(acc[-1] + math.dist(loop[i - 1], loop[i]))
    L = acc[-1]
    n = max(3, int(L / step + 0.5))
    pr = g.createPolygon(is_closed=True)
    for k in range(n):
        s = L * k / n
        j = 1
        while j < len(acc) - 1 and acc[j] < s:
            j += 1
        t = 0.0 if acc[j] == acc[j - 1] else (s - acc[j - 1]) / (acc[j] - acc[j - 1])
        pr.addVertex(g.createPoint()).point().setPosition(
            (loop[j - 1][0] + t * (loop[j][0] - loop[j - 1][0]), 0.0,
             loop[j - 1][1] + t * (loop[j][1] - loop[j - 1][1])))
    pr.setAttribValue("streetWidth", 26.8)
    pr.setAttribValue("rig", name)


def circle(r, n):
    return [(r * math.cos(k * 2 * math.pi / n), r * math.sin(k * 2 * math.pi / n))
            for k in range(n)]


# S3b's own worked example: a plain 90 degree bend on an arterial.
poly("bend90", [(-80, 0), (0, 0), (0, 80)])
# 135 degrees is the worst FEASIBLE turn on these legs: it wants
# R x tan(67.5) = 64.7 m of tangent run and the legs are 80 m, so it only just
# fits and the solved arc sits hard on the clamp the whole way round.
poly("bend135", [(-80, 0), (0, 0), (-56.6, 56.6)])
# ⚠️ MULTI-VERTEX RUNS. Every over-curved run in every shipped case is a single
# hard vertex, where locating the corner is trivial (it IS that vertex) and the
# leg directions are exactly the segments either side. An audit found that the
# whole rest of the corner construction — the leg intersection, the refined leg
# frame — was therefore executed by no test at all, and was wrong: a 135 degree
# corner DRAWN as an 18 m arc spreads over ten over-curved vertices, whose first
# and last segments are the arc's own, tilted a full vertex-turn off the
# straight legs. That case did not converge. These two draw the corner rather
# than break it, which is the only way to reach that branch.
poly("bend135_r18", _rounded([(-200, 0), (0, 0), (-141.4, 141.4)], 18.0))
poly("bend90_r10", _rounded([(-200, 0), (0, 0), (0, 200)], 10.0))
# the one that made the first solver diverge: a 30 m square returning to within
# 4 m of its own start. R_min = 26.8 m needs 26.8 m of tangent run each side of
# a right angle and the sides are 30 m, so this is INFEASIBLE by construction
# and the only correct answer is to say so.
poly("foldback", [(0, 0), (30, 0), (30, 30), (0, 30), (0, 4)])

# --- closed prims. See turn_clamp_control_rig() for why all three are here. ---
# legal: R = 120 m is well inside the clamp, so it must come back untouched.
ring("ring_legal", circle(120.0, 188))
# solvable: a 300 m square ring is four concentrated corners, and rounding them
# redistributes the turning without needing the ring to grow.
ring("ring_square", [(0, 0), (300, 0), (300, 300), (0, 300)])
# INFEASIBLE, and for a reason the square hides: a round ring of R = 20 m is
# over the clamp at every vertex at once, and the only way to lower kappa on a
# closed curve is to make it LONGER. Every correction here pulls toward a chord,
# which shortens. Its nodes are pinned by the graph, so nothing can fix it and
# the honest output is a flag, exactly as for the fold-back.
ring("ring_tight", circle(20.0, 31))
'''


def lots_clear_of_junctions(lot_geo, patch_node, cell=0.5, tol_per_junction=0.5):
    """No lot may lie inside a junction. The other half of city_is_fully_paved.

    `city_is_fully_paved` catches the corridor being UNDER-covered; this catches
    it being over-covered at the one place that has always been wrong. S7
    specifies that at a node the block boundary follows S5's fillet arc, because
    that arc IS the kerb there. The shipped build offset the centreline graph
    with PolyExpand2D instead, whose straight skeleton mitres the corner, so
    every lot cut the corner and sat on the junction surface — 11.7 (A) / 7.5
    (B) / 9.7 (C) / 3.1 (D) m2 per junction, and 558 in E where the corridor's
    own outer ring was being subdivided into lots.

    Rasterised rather than clipped: a junction patch is non-convex once the
    fillets are in, so Sutherland-Hodgman would lie about it — which is exactly
    the defect 4e-5 records in the lot subdivider.
    """
    try:
        import numpy as np
    except ImportError:
        return _skip("lots_clear_of_junctions", "numpy unavailable")
    if patch_node is None or patch_node.errors():
        return _skip("lots_clear_of_junctions", "junction patch node missing")
    g_p = patch_node.geometry()
    njunc = len(g_p.prims())
    if njunc == 0:
        return _skip("lots_clear_of_junctions", "no junctions in this case")
    grid = _raster_grid([g_p], cell)
    over = _rasterise(np, lot_geo, grid) & _rasterise(np, g_p, grid)
    area = float(over.sum()) * cell * cell
    per = area / njunc
    return Result("lots_clear_of_junctions", per <= tol_per_junction,
                  {"m2": round(area, 1), "junctions": njunc,
                   "per_junction": round(per, 2)},
                  "lot area lying inside a junction patch; the block boundary "
                  "must BE S5's kerb, so this is 0 by construction")


def lots_clear_of_roads(lot_geo, roads_node, surface_node, cell=0.5,
                        min_area=1.0, tol_area=2.0):
    """No lot may lie on the road, ANYWHERE — not just inside a junction patch.

    THE GAP `lots_clear_of_junctions` leaves, and the fourth time in this
    project that a check has missed by measuring the wrong seam. It measures
    lots against the JUNCTION PATCH, and a degree-1 node has no patch, so every
    dead end in the city is unmeasured by it. `city_is_fully_paved` is the other
    half and looks for the corridor being UNDER-covered; nothing looked for a
    lot sitting ON the pavement away from a junction. Both read 0 on all five
    cases while C_radial shipped 48.3 m2 of lots on an arterial.

    MEASURED root cause of that 48.3 m2, so this check is aimed at something
    real rather than at a category: two dangling ends 6.68 m apart at
    (251.4, -87.1) and (249.4, -93.5), each one INSIDE the other street's
    pavement (6.68 m against a 13.40 m half-width), neither connected. S7's
    collect-and-close chains frontage runs, junction corner runs and dead-end
    caps into loops with no test that a run lies outside the pavement, so the
    wedge between two unmerged stubs closes into a block, and S8 subdivides it
    into parcels that sit on the arterial.

    Rasterised, like its two neighbours, because a junction patch and a block
    are both non-convex and a clip would lie about them. A lot edge lying
    exactly along a kerb costs nothing: `_rasterise` tests cell CENTRES, so an
    abutting pair claims disjoint cells. Measured — B_grid reads exactly 0.0.
    """
    try:
        import numpy as np
    except ImportError:
        return _skip("lots_clear_of_roads", "numpy unavailable")
    geos = [n.geometry() for n in (roads_node, surface_node)
            if n is not None and not n.errors()]
    if not geos:
        return _skip("lots_clear_of_roads", "no road geometry")
    if len(lot_geo.prims()) == 0:
        return _skip("lots_clear_of_roads", "no lots in this case")
    grid = _raster_grid(geos + [lot_geo], cell)
    road = np.zeros((grid[3], grid[2]), dtype=bool)
    for g in geos:
        road |= _rasterise(np, g, grid)
    over = road & _rasterise(np, lot_geo, grid)
    blobs = _blobs(np, over, grid, min_area)
    total = round(float(over.sum()) * cell * cell, 1)
    return Result("lots_clear_of_roads", bool(total <= tol_area),
                  {"m2": total, "patches": len(blobs), "worst": blobs[:3]},
                  "lot area lying on the road surface anywhere, junction or "
                  "not; the block boundary IS the kerb, so this is 0 by "
                  "construction (%g m2 allowed)" % tol_area)


def city_is_fully_paved(city_node, outer_node, cell=1.0, min_area=4.0,
                        tol_area=40.0):
    """Nothing inside the street corridor may be left unpaved.

    THE check that would have caught the dead-end holes, and the suite had
    nothing of its shape. `lots_tile_blocks` cannot see them: the lots DO tile
    their blocks exactly. The broken seam is between the blocks and the roads,
    and no per-component check looks across it.

    PolyExpand2D caps a dangling polyline end by the same local scale it uses
    sideways, so at every degree-1 node the block boundary was pushed
    streetWidth/2 PAST the node while the road sweep stopped AT it. That left a
    streetWidth x streetWidth/2 rectangle paved by nothing — 359 m2 per arterial
    dead end, 9,143 m2 across C_radial, and invisible to all 30 other checks.

    Method: rasterise the shipped city (roads + junction surface + lots +
    piers) onto a 1 m XZ grid, and rasterise the corridor's outer boundary
    curve as the region that MUST be covered. Anything inside the region that
    nothing covers is reported, largest first. The region is eroded by one cell
    so the half-covered fringe along its own boundary does not read as a defect.

    A whole-city measure on purpose. A 360 m2 hole is invisible in a 40 m crop
    and obvious in a top-down of the city, and this build has been reported
    "fixed" three times off a crop of the thing just changed.
    """
    try:
        import numpy as np
    except ImportError:
        return _skip("city_is_fully_paved", "numpy unavailable")
    if outer_node is None or outer_node.errors():
        return _skip("city_is_fully_paved", "corridor boundary node missing")
    try:
        g_city = city_node.geometry(0)
        g_outer = outer_node.geometry()
    except Exception as exc:
        return _skip("city_is_fully_paved", "no geometry: %s" % str(exc)[:60])
    if g_outer.findPrimAttrib("is_outer") is None:
        return _skip("city_is_fully_paved", "no is_outer attribute")

    grid = _raster_grid([g_city, g_outer], cell)
    region = _rasterise(np, g_outer, grid, lambda pr: pr.attribValue("is_outer"))
    # erode by one cell: the region boundary IS the geometry boundary, so cells
    # straddling it are half-covered by construction and are not holes
    e = region.copy()
    e[1:, :] &= region[:-1, :]
    e[:-1, :] &= region[1:, :]
    e[:, 1:] &= region[:, :-1]
    e[:, :-1] &= region[:, 1:]
    e[0, :] = e[-1, :] = False
    e[:, 0] = e[:, -1] = False

    gaps = _blobs(np, e & ~_rasterise(np, g_city, grid), grid, min_area)
    total = round(float(sum(g[0] for g in gaps)), 1)
    return Result("city_is_fully_paved", bool(total <= tol_area),
                  {"unpaved_m2": total, "regions": len(gaps),
                   "worst": gaps[:3]},
                  "area inside the corridor that no road, junction or lot "
                  "covers (>= %g m2 each, %g m2 allowed in total)"
                  % (min_area, tol_area))
