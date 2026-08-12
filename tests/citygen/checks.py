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
    bulbs = 0
    for prim in patch_geo.prims():
        # A CUL-DE-SAC BULB IS NOT A FILLET. Everything below sizes a corner
        # from the two street classes that meet at it; a bulb is a turning
        # circle sized from S5's own radius table and it has only one incident
        # street, so `radius` here would report 18.09 against an expected 9.0
        # on every dead end in the city. `culdesac_bulbs_are_circles` asserts
        # the bulb instead, in the terms a bulb actually has.
        try:
            if prim.attribValue("is_culdesac") == 1:
                bulbs += 1
                continue
        except Exception:
            pass
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
             "mixed_class": mixed,
             "culdesac_skipped": bulbs}
    ok = (bad == 0 and max_fit <= fit_tol and max_tan <= tangent_tol
          and (not node_edges or (max_rad <= radius_tol and max_radfit <= 1.0)))
    return Result(name, ok, value,
                  "%d corners, %d arcs fitted; %d join two street classes, "
                  "where the lesser one sets the radius (S5); %d cul-de-sac "
                  "bulbs skipped, see culdesac_bulbs_are_circles"
                  % (total, fitted, mixed, bulbs))


def culdesac_bulbs_are_circles(patch_geo, streets_geo, radius, fit_tol=1e-3,
                               floor=1.35):
    """The cul-de-sac bulb, asserted in the terms a bulb has.

    citygen_streets.md S5 "plazas and roundabouts at degenerate points": the
    plaza, the roundabout and the bulb are one construction with three radius
    defaults, and the bulb is the one that "terminates a dead end deliberately,
    instead of leaving a stub". `every_corner_is_an_arc` cannot check it — it
    sizes a corner from the two street classes meeting at it, and a bulb has one
    incident street and a radius from S5's own table — so it skips them and this
    picks them up. A construction that no check covers is the pattern this
    project has repeated four times.

    Four assertions:

    * **it is a circle** — every non-cap point fits one, to `fit_tol`;
    * **of the declared radius**, floored at `floor` x the road's half-width. A
      bulb narrower than the road it ends is not a turning circle, and at
      R <= h the mouth corners fall OUTSIDE the circle and the boundary
      inverts;
    * **the mouth corners lie on it** — this is the whole construction
      (R² = dcut² + h²) and it is what makes the block boundary meet the bulb
      instead of chording across it;
    * **the bulb is not the whole street** — every street carrying a bulb still
      has road standing between its junction mouth and its terminus.

    ⚠️ The count is recorded, not asserted, and deliberately: how many dead ends
    remain is S2/S3's business, and a build that connects them all should not
    fail a check about bulbs.
    """
    name = "culdesac_bulbs_are_circles"
    if patch_geo.findPrimAttrib("is_culdesac") is None:
        return Result(name, True, {"bulbs": 0}, "no cul-de-sac bulbs in this case")
    worst_fit = worst_rad = worst_cap = 0.0
    bulbs = bad = 0
    for pr in patch_geo.prims():
        if pr.attribValue("is_culdesac") != 1:
            continue
        bulbs += 1
        pts = [v.point() for v in pr.vertices()]
        arc = [p.position() for p in pts if p.attribValue("is_cap") != 1]
        caps = [p.position() for p in pts if p.attribValue("is_cap") == 1]
        if len(arc) < 3 or len(caps) != 2:
            bad += 1
            continue
        fit = _fit_circle(arc)
        if fit is None:
            bad += 1
            continue
        cx, cz, r, resid = fit
        worst_fit = max(worst_fit, resid)
        h = 0.5 * (caps[0] - caps[1]).length()
        want = max(radius, h * floor)
        # the cut is pushed outward by pfsg_clear_of_vertex when it lands too
        # close to a resample vertex, and the radius grows with it — so the
        # delivered radius is >= the wanted one, never below it
        worst_rad = max(worst_rad, max(want - r, 0.0))
        for q in caps:
            worst_cap = max(worst_cap, abs(math.hypot(q[0] - cx, q[2] - cz) - r))
    ok = (bad == 0 and worst_fit <= fit_tol and worst_rad <= 1e-2
          and worst_cap <= 1e-2)
    return Result(name, ok,
                  {"bulbs": bulbs, "malformed": bad,
                   "circle_fit": round(worst_fit, 7),
                   "under_radius": round(worst_rad, 5),
                   "mouth_off_circle": round(worst_cap, 5)},
                  "each bulb is a circle of at least max(%.2f m, %.2f x the "
                  "road half-width) with both mouth corners ON it"
                  % (radius, floor))


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


def _point_grid(geo, cell):
    """(cell -> [point index], flat P) for order-independent nearest lookup."""
    pos = geo.pointFloatAttribValues("P")
    grid = {}
    for i in range(len(pos) // 3):
        grid.setdefault((int(math.floor(pos[3 * i] / cell)),
                         int(math.floor(pos[3 * i + 1] / cell)),
                         int(math.floor(pos[3 * i + 2] / cell))), []).append(i)
    return grid, pos


def _nearest(grid, pos, cell, p):
    """Distance to, and index of, the closest point. Rings outwards so an
    isolated point is still found rather than reported as infinitely far."""
    kx, ky, kz = (int(math.floor(p[0] / cell)), int(math.floor(p[1] / cell)),
                  int(math.floor(p[2] / cell)))
    best, bi = None, -1
    for r in range(0, 6):
        for dx in range(-r, r + 1):
            for dy in range(-r, r + 1):
                for dz in range(-r, r + 1):
                    if r and max(abs(dx), abs(dy), abs(dz)) != r:
                        continue          # only the new shell
                    for i in grid.get((kx + dx, ky + dy, kz + dz), ()):
                        d = ((pos[3 * i] - p[0]) ** 2 + (pos[3 * i + 1] - p[1]) ** 2
                             + (pos[3 * i + 2] - p[2]) ** 2)
                        if best is None or d < best:
                            best, bi = d, i
        if best is not None and best <= (r * cell) ** 2:
            break
    if best is None:
        for i in range(len(pos) // 3):
            d = ((pos[3 * i] - p[0]) ** 2 + (pos[3 * i + 1] - p[1]) ** 2
                 + (pos[3 * i + 2] - p[2]) ** 2)
            if best is None or d < best:
                best, bi = d, i
    return (math.sqrt(best) if best is not None else float("inf")), bi


def _ends(geo):
    """(start P, end P) per prim, plus point -> [prim] for the endpoints."""
    out, by_pt = [], {}
    for pr in geo.prims():
        vs = list(pr.vertices())
        if len(vs) < 2:
            out.append(None)
            continue
        a, b = vs[0].point(), vs[-1].point()
        out.append((a.position(), b.position()))
        by_pt.setdefault(a.number(), []).append(len(out) - 1)
        by_pt.setdefault(b.number(), []).append(len(out) - 1)
    return out, by_pt


def _graph_geometry_delta(a, b, tol):
    """The FULL geometry of two graphs, compared order-independently.

    ⚠️ This used to be `_graph_invariants` — four counts and sums, a strict
    SUBSET of what `repair_verdict` already tested, since it dropped even the
    bbox term. So the replay was an independent NODE but not an independent
    CRITERION: it could not fail on anything the solver's own verdict could not
    fail on, which is the whole reason for running it. Every defect the verdict
    was blind to — a point sliding along its polyline, a point crossing it, an
    edge reversing — was equally invisible here.

    So it compares the geometry itself: a symmetric Hausdorff over the point
    sets (a real MAX, not a sum) and a per-edge direction match, both matched
    through position rather than through numbering, because graph_fuse,
    polypath and the blasts renumber freely and an index-wise comparison reads
    that as hundreds of metres of movement.
    """
    nodes_a = sum(1 for pt in a.points() if len(pt.prims()) != 1)
    nodes_b = sum(1 for pt in b.points() if len(pt.prims()) != 1)
    out = {"edges": [len(a.prims()), len(b.prims())],
           "points": [len(a.points()), len(b.points())],
           "nodes": [nodes_a, nodes_b],
           "length_m": [round(sum(pr.intrinsicValue("measuredperimeter")
                                  for pr in a.prims()), 2),
                        round(sum(pr.intrinsicValue("measuredperimeter")
                                  for pr in b.prims()), 2)]}
    cell = 8.0
    ga, pa = _point_grid(a, cell)
    gb, pb = _point_grid(b, cell)
    move = 0.0
    for i in range(len(pa) // 3):
        d, _ = _nearest(gb, pb, cell, (pa[3 * i], pa[3 * i + 1], pa[3 * i + 2]))
        move = max(move, d)
    for i in range(len(pb) // 3):
        d, _ = _nearest(ga, pa, cell, (pb[3 * i], pb[3 * i + 1], pb[3 * i + 2]))
        move = max(move, d)
    out["max_point_move_m"] = round(move, 6)

    ends_a, _ = _ends(a)
    ends_b, by_pt_b = _ends(b)
    reversed_edges = 0
    for ea in ends_a:
        if ea is None:
            continue
        s, e = ea
        cand = []
        for p in (s, e):
            _, j = _nearest(gb, pb, cell, p)
            if j >= 0:
                cand.extend(by_pt_b.get(j, ()))
        best, best_rev = None, 0
        for q in cand:
            eb = ends_b[q]
            if eb is None:
                continue
            s1, e1 = eb
            f = (s1 - s).length() + (e1 - e).length()
            g = (e1 - s).length() + (s1 - e).length()
            if best is None or f < best:
                best, best_rev = f, 0
            if g < best:
                best, best_rev = g, 1
        reversed_edges += best_rev
    out["reversed_edges"] = reversed_edges
    bad = {k: out[k] for k in ("edges", "points", "nodes")
           if out[k][0] != out[k][1]}
    if abs(out["length_m"][0] - out["length_m"][1]) > 0.01:
        bad["length_m"] = out["length_m"]
    if move > tol:
        bad["max_point_move_m"] = out["max_point_move_m"]
    if reversed_edges:
        bad["reversed_edges"] = reversed_edges
    out["moved"] = bad
    return out


def graph_reaches_a_fixed_point(trace_node):
    """The repair pass, re-run on the graph it shipped, must change nothing.

    citygen_streets.md S3. Every repair MUTATES the graph and the consequence
    lands on a stage that has already run: extend-to-connect welds a dead end
    onto a target street, which creates a NEW JUNCTION on that target, and S5
    has been and gone. The tongue drop and the cul-de-sac bulb do the same
    thing one stage further on. The artist's report was the visible half of it
    — "it did detect it now as a dead end and merged it to the closest street.
    That is fine, but the other street which should form a junction with it did
    not" — and re-feeding the shipped graph into the pipeline reproduced it
    exactly: C_radial came back with 86 edges instead of 84 and 94 m more
    street, two T-junctions the single pass had refused.

    Two teeth, because the solver's own verdict and an independent replay fail
    differently:

    * **The solver must say it converged.** `repair_converged` is the stop
      attribute on the loop, so a run that hits the cap ships 0 and this fails
      rather than shipping a half-repaired graph quietly. That failure mode has
      now bitten this project four times (S3b `iters = 200`, the trace stall,
      the clamp budget, and this).
    * **And an independent pass must agree.** A second `pf_citygen_trace`, same
      parameters, fed the shipped splines on its drawn-spline input. If the
      first node's idea of "converged" is wrong, this is what catches it.

    ⚠️ **The replay compares the FULL GEOMETRY, not a reduced invariant set,
    and that correction is the whole point of the second tooth.** It used to
    call `_graph_invariants` — edges, points, nodes and total length — which is
    a strict SUBSET of what `repair_verdict` itself tested (it did not even
    carry the bbox term), so the replay was an independent node running a
    weaker criterion and could not catch anything the solver had already
    missed. It now compares per-point positions and per-edge direction, which
    are exactly the two things the old verdict was blind to.
    """
    name = "graph_reaches_a_fixed_point"
    geo = trace_node.geometry(0)
    if geo.findGlobalAttrib("repair_converged") is None:
        return Result(name, False, None, "no repair loop on this tracer")
    conv = geo.attribValue("repair_converged")
    iters = geo.attribValue("repair_iterations")
    resid = (geo.attribValue("repair_residual_m")
             if geo.findGlobalAttrib("repair_residual_m") is not None else None)
    tolp = trace_node.parm("graph_params_repair_tolerance")
    tol = tolp.eval() if tolp is not None else 0.001
    parent = trace_node.parent()
    probe = parent.node("__chk_fixed_point")
    if probe is not None:
        probe.destroy()
    probe = parent.createNode(trace_node.type().name(), "__chk_fixed_point")
    try:
        for p in trace_node.parms():
            q = probe.parm(p.name())
            if q is not None:
                try:
                    q.set(p.eval())
                except Exception:
                    pass
        # ⚠️ Port 1 was the tracer's drawn-spline input. The SEGMENTER has one
        # port — that was the point of the split, one workflow whatever the
        # source — so the replay feeds port 0. Wire it to port 1 and the check
        # raises rather than failing, which is worse than either.
        probe.setInput(0, trace_node, 0)
        probe.cook(force=True)
        if probe.errors():
            return Result(name, False, {"converged": conv, "passes": iters},
                          "replay errored: %s" % probe.errors()[0][:160])
        delta = _graph_geometry_delta(geo, probe.geometry(0), tol)
    finally:
        probe.destroy()
    moved = delta["moved"]
    return Result(name, conv == 1 and not moved,
                  {"converged": conv, "passes": iters,
                   "residual_m": None if resid is None else round(resid, 6),
                   "reversed": delta["reversed_edges"],
                   "replay_move_m": delta["max_point_move_m"],
                   # RECORDED because it is the acceptance threshold and it is a
                   # live artist parameter: measured on C_radial, raising it to
                   # 2e-3 or even 1e-2 changes no other value in this dict, so a
                   # 10x loosening of this tooth was invisible to the baseline.
                   "tol_m": tol,
                   "replay_moved": moved or None},
                  "the repair pass re-run on the graph it shipped must be a "
                  "no-op — full geometry, to within Repair Tolerance (%.4g m)"
                  % tol)


def _lot_area_delta(was, now, quantiles=64):
    """(parcels over 1 m2, worst m2) between two rank-sorted parcel-area lists.

    ⚠️ **The COUNT alone was latent hole 1 — "computed and discarded" — one
    stage further down.** `lots_moved` recorded how many parcels moved and
    threw away how far: A's worst is **40.6 m2** and B's **23.6 m2**, and
    619 parcels moving 0.9 m2 each would have read as a flat 0. So the
    magnitude is returned with the count.

    ⚠️ **And a lot-count change is the one case that MOVES, so it may not go
    blind.** An index-wise pair does not exist when C_radial ships 774 parcels
    before the forced pass and 770 after, and this used to answer `None` there
    — for the only case in the suite whose parcels actually move. Both lists
    are sampled at 64 fixed quantiles instead: C's worst is **8.21 m2** over
    **42** of the 64 quantiles, 151 m2 in total. `None` is reserved for the
    case where the question is meaningless — E/F/G close no block and ship no
    parcels at all, where a count of 0 read identically to "stable".

    What this still cannot see is measured and stated: area is ONE SCALAR, so
    a parcel changing SHAPE at constant area is invisible here, and so is a
    pure permutation of areas among the parcels. Neither bites on this build —
    D_offset reads 0, and the audit of `aa797db` corroborated that with an
    identity-matched compare at 0 area, 0 perimeter and 0 centroid movement —
    but on A that same identity-matched view shows **75 of 83 centroids moving
    more than 5 cm, worst 13.58 m**, which is the shape term this does not
    carry. (The area figures above are re-measured here; the centroid ones are
    the audit's, and nothing in the suite computes them yet.)
    """
    if not was or not now:
        return None, None
    if len(was) == len(now):
        d = [abs(x - y) for x, y in zip(was, now)]
    else:
        def at(lst, q):
            return lst[int(round(q * (len(lst) - 1) / float(quantiles - 1)))]
        d = [abs(at(was, q) - at(now, q)) for q in range(quantiles)]
    return sum(1 for x in d if x > 1.0), round(max(d), 4)


def forced_extra_repair_pass(trace_node, city_node):
    """Turn OFF the loop's early exit, run one pass MORE than it asked for, and
    see what the shipped city does. **Run this last: it re-cooks the city.**

    ⚠️ This is the experiment that caught the old verdict, and it belongs here
    rather than in an auditor's scratch file — it is the only thing that can
    tell "the loop stopped" from "the loop converged". Every term the verdict
    tests is chosen by the person who wrote the verdict; this one asks the
    pipeline instead. On the four-aggregate verdict it moved **A 82 → 83 lots
    and B 622 → 617** on a pass the solver had certified as a no-op.

    ⚠️ **AND ITS OWN `ok` FLAG USED TO TEST THE AGGREGATES ITS OWN COMMIT HAD
    JUST PROVED BLIND.** Corrected 2026-08-10 after an independent audit of
    `4fd44b6`. The flag was `not structural`, over `edges` / `points` /
    `blocks` — three global aggregates, which is the exact set the commit that
    added this check demonstrated cannot see a redistribution. **It would have
    passed on the defect it was written to catch**, and it passed on HEAD while
    recording `'moved': {'lots': [774, 770]}` on C_radial: a four-prim change
    in the shipped city that its own `state()` does not even sample.

    So it now asserts what the forced pass itself measures. `repair_verdict`
    writes `repair_residual_m` (the largest distance any point moved on that
    pass, matched through position so renumbering cannot inflate it) and
    `repair_reversed` (edges that came back the other way round) — both are
    local and both are the terms the aggregates are blind to. Measured across
    all seven forced passes: worst residual **6.10e-5 m on F_bend** against a
    1e-3 m `Repair Tolerance`, a **16×** margin, and **0** reversals. It costs
    no extra cook: the numbers are already on the geometry the pass produced.
    **The tooth was proved on the three real defects**, by capping each case at
    the pass the old verdict stopped at with the tolerance left at 1e-3:
    `F_bend` fails at a 1.587e-3 m residual, `C_radial` at 1.142e-3 m and **9**
    reversals, `B_grid` on **1** reversal with its structure stable — all three
    of which the old `edges`/`points`/`blocks` flag passed.

    ⚠️ **Two things this does NOT do, measured rather than assumed.** Both
    asserted terms are the solver's own self-report, so a bug inside
    `repair_verdict` reads as 0 / 0 and passes here; the independent half of
    the check is still the blind set. And if `repair_verdict` stops writing
    altogether this returns a **SKIP**, not a failure, at the
    `repair_iterations` guard above — `graph_reaches_a_fixed_point` is what
    fails hard in that case, and it is the reason the suite is still covered.

    ⚠️ **THREE of this experiment's numbers are the solver's own, including
    its CONTROL VARIABLE, and that is worth naming.** Added 2026-08-10 after
    an independent audit of `aa797db`:

    * **`iters`** — the pass count the experiment is defined against
      (`cap = iters + 1`) is `repair_iterations`, the loop's own counter. That
      is what made "the forced pass never ran" expressible at all, and it is
      now asserted on the forced geometry rather than assumed. The failure
      direction is safe: a counter that under-reports forces MORE passes, and
      one that over-reports trips the assert.
    * **`tol`** — the acceptance threshold is `graph_params_repair_tolerance`,
      which is the solver's OWN stop threshold, so `resid <= tol` here is the
      loop's stop condition re-applied one pass later. Its unique coverage is
      therefore the **f³ window only**: the loop already requires two
      consecutive no-op passes (§S3 — `f(x) == x` says nothing about
      `f(f(x))`, and B_grid proves it), so this is the third iterate. Every
      constructible regression outside that window fails `repair_converged`
      == 0 first, in `graph_reaches_a_fixed_point`.
    * **`resid` / `rev`** — as above, the verdict's own two numbers.

    ⚠️ **LOT COUNT IS RECORDED, NOT ASSERTED, and the reason is S8 rather than
    S3.** With the displacement and direction terms in, A, B, D, E, F and G are
    stable across the forced pass and **C_radial still moves 774 → 770**. The
    pass that does it moves no point further than **4.6e-5 m** — the last ulp
    of float32 at these coordinates — and reverses no edge. The repair pass
    cannot be made bit-exact idempotent, because `resample`, `graph_polypath`
    and the S3b clamp all re-accumulate arc length in float32 every pass; and
    S8's recursive-OBB split is chaotic at that scale — measured on `A_drawn`,
    a **1.5e-5 m** jitter alone flips a parcel. Asserting the lot count here
    would therefore assert S8's determinism, which is a separate task, in S8.
    ⚠️ And "stable" was a claim about four integers. Rank-sorted parcel areas
    across the same forced pass move on **78 of A's 83 parcels** (worst 40.6 m²)
    and **443 of B's 619** (worst 23.6 m²) while total lot area is conserved to
    6e-4 m² — a textbook redistribution under a conserved aggregate, one level
    downstream of the one this check was written to catch, and it printed
    `moved: None`. `lots_moved` is that term, and `city_prims` / `city_points`
    close the other gap: A's shipped city gains a point across the pass and
    nothing sampled it. All of them are RECORDED, not asserted, for the same
    reason the lot count is — see citygen_streets.md §S3. `lots_worst_m2`
    carries the magnitude `lots_moved` used to discard, and both come from
    `_lot_area_delta`, which also stops answering `None` on the one case that
    moves; read its docstring for what the area term still cannot see.

    ⚠️ **`blocks` is asserted and `blocks` is S7, not S3** — the detail string
    called the asserted set "the GRAPH structure" and it is the graph plus the
    block count. Asserting it is right and it is measured: 2 / 17 / 2 / 28
    blocks held across every forced pass on every case, so the block layer is
    the one thing downstream of the graph that S8's chaos does not move.
    """
    name = "forced_extra_repair_pass"
    geo = trace_node.geometry(0)
    if geo.findGlobalAttrib("repair_iterations") is None:
        return _skip(name, "no repair loop on this tracer")
    iters = geo.attribValue("repair_iterations")
    tolp = trace_node.parm("graph_params_repair_tolerance")
    tol = tolp.eval() if tolp is not None else 0.001

    def state():
        """Counts, plus the parcel AREAS the counts cannot see — rank-sorted, so
        S8 renumbering cannot fake a match."""
        g = trace_node.geometry(0)
        lots = city_node.geometry(2)
        city = city_node.geometry(0)
        return ({"edges": len(g.prims()), "points": len(g.points()),
                 "blocks": len(city_node.geometry(1).prims()),
                 "lots": len(lots.prims()),
                 "city_prims": len(city.prims()),
                 "city_points": len(city.points())},
                sorted(pr.intrinsicValue("measuredarea") for pr in lots.prims()))

    was, was_areas = state()
    # left unlocked on purpose: run_scene_checks unlocks the tracer for the
    # whole case (turn_clamp_control_rig builds inside it), so re-locking here
    # would take the network away from the checks that run after this one.
    trace_node.allowEditingOfContents()
    end = trace_node.node("repair_end")
    cap = trace_node.parm("graph_params_repair_passes")
    if end is None or cap is None:
        return _skip(name, "repair_end / cap parm missing")
    stop = end.parm("stopattrib")
    # rawValue, not eval: eval would flatten an expression to a literal on the
    # way back in, and the restore is what leaves the asset as it was found.
    old_stop, old_cap = stop.rawValue(), cap.eval()
    resid = rev = None
    try:
        stop.set("")                            # no early out
        cap.set(iters + 1)
        city_node.cook(force=True)
        if trace_node.errors():
            return Result(name, False, None,
                          "forced pass errored: %s" % trace_node.errors()[0][:160])
        forced_geo = trace_node.geometry(0)
        for a in ("repair_residual_m", "repair_reversed", "repair_iterations"):
            if forced_geo.findGlobalAttrib(a) is None:
                return Result(name, False, None,
                              "the forced pass shipped no %s — the verdict "
                              "stopped being written" % a)
        # ...and that the experiment RAN. Everything below is measured on the
        # forced geometry, so if the extra pass never happened this check
        # reports "nothing moved" about the pass it did not run: simulated by
        # leaving the cap at `iters`, the structure is unchanged, the residual
        # is 1.53e-5 and the reversal count 0, and it PASSED. It only runs at
        # all because `Max Repair Passes` has maxIsStrict=False — luck, not
        # design — so the pass count is asserted instead of assumed.
        ran = forced_geo.attribValue("repair_iterations")
        if ran != iters + 1:
            return Result(name, False, {"passes": iters, "forced": iters + 1,
                                        "ran": ran},
                          "the forced pass did not run: the loop reports %d "
                          "passes where %d were forced, so nothing below is "
                          "about the extra pass" % (ran, iters + 1))
        resid = forced_geo.attribValue("repair_residual_m")
        rev = forced_geo.attribValue("repair_reversed")
        now, now_areas = state()
    finally:
        stop.set(old_stop)
        cap.set(old_cap)
        city_node.cook(force=True)             # leave the city as it shipped
    moved = {k: [was[k], now[k]] for k in was if was[k] != now[k]}
    # S3's terms are asserted; S8's are RECORDED, for the reason in the
    # docstring. `lots`, `city_prims`, `city_points` and `lots_moved` all move
    # with the recursive-OBB split, which is a separate task in S8.
    structural = {k: v for k, v in moved.items()
                  if k in ("edges", "points", "blocks")}
    lots_moved, lots_worst = _lot_area_delta(was_areas, now_areas)
    return Result(name, not structural and resid <= tol and rev == 0,
                  {"passes": iters, "forced": iters + 1,
                   "residual_m": round(resid, 7), "reversed": rev,
                   "tol_m": tol,
                   "lots": [was["lots"], now["lots"]],
                   "lots_moved": lots_moved,
                   "lots_worst_m2": lots_worst,
                   "moved": moved or None},
                  "one pass past the loop's own verdict, with the Stop "
                  "Attribute disabled: the pass must run (%d passes, not %d), "
                  "must move no point further than Repair Tolerance (%.4g m) "
                  "and reverse no edge, and the graph structure and the BLOCK "
                  "COUNT must not move; every S8 term — lot count, parcels "
                  "whose area moves > 1 m2 and the worst of those areas, city "
                  "prims and points — is recorded, because S8 is chaotic at "
                  "the float32 noise floor"
                  % (iters + 1, iters, tol))


def _attrib_values(geo, name, prim):
    """Every value of one attribute, in element order.

    Bulk-read where the type allows it: the graph carries thousands of points
    and `input0_reaches_an_output` reads every attribute on both sides of the
    pass-through, once per case. The attribute is looked up on the geometry
    being read rather than passed in, so the two sides changing TYPE under the
    same name reads as a value difference instead of raising.
    """
    import hou
    elems = geo.prims() if prim else geo.points()
    at = (geo.findPrimAttrib if prim else geo.findPointAttrib)(name)
    word = {hou.attribData.String: "String", hou.attribData.Int: "Int",
            hou.attribData.Float: "Float"}.get(at.dataType())
    if word is None or at.isArrayType():
        return [e.attribValue(name) for e in elems]
    return list(getattr(geo, ("prim" if prim else "point") + word
                        + "AttribValues")(name))


def input0_reaches_an_output(graph_geo, mesh_graph_geo):
    """`pf_citygen_mesh` input 0 must actually reach something published.

    Written 2026-08-10 after an independent audit reported input 0 **DEAD** —
    "a 2.5 m jitter on input 0 changes the shipped city by nothing
    (4459/2/83 identical); the same jitter on input 1 changes everything" — and
    recommended deleting it. The finding was real as far as it was measured and
    the conclusion was wrong, because the three numbers it sampled are the
    three input 0 does not move. Re-measured with the same 2.5 m jitter:

    * **output 3, the graph, is a pass-through of input 0** (`out_graph` reads
      `IN_graph` directly), so it moves by the full jitter on every case;
    * `blocks_id` reads the graph on its **second** input to stamp identity, so
      C_radial moves `block_id` on **1 of 28 blocks and 18 of 774 lots**, and
      `region_id` with it;
    * `s5b_mark` → `s5b_piers` builds the bridge piers off it, and **no case in
      the suite has a bridge**, which is why the merged prim count never moves.

    So input 0 stays, and this is the standing proof: the mesh's graph output
    must be its input 0 — point for point AND attribute for attribute.

    ⚠️ **Positions alone were not enough, and an audit proved it on this check
    the day it was written.** Re-sourcing `out_graph` one hop downstream, from
    `s5b_mark`, leaves every point where it was: the position-only version
    PASSED while the published graph had silently gained `is_bridge`,
    `is_tunnel`, `is_ramp` and `terrain_op`. The attribute NAME SETS are
    compared for that reason — a pass-through that adds a column is not a
    pass-through.

    ⚠️ **AND THE NAME SETS WERE NOT ENOUGH EITHER — "attribute for attribute"
    was comparing NAMES.** Corrected 2026-08-10 after an independent audit of
    `aa797db`. Publishing output 3 through a wrangle that sets
    `street_class = "alley"`, `region_id = "region_99"` and
    `streetWidth = 1.0` on every edge adds no name and moves no point: this
    check PASSED, `attribute_schema` passed, **nothing in the suite failed**,
    and the shipped graph said every street in the city was a 1 m alley. Same
    shape of hole as the one above, one level in: a pass-through that rewrites
    a column is not a pass-through either. The VALUES of every shared
    attribute are compared now, elementwise and exactly — a pass-through is
    bit-identical or it is not a pass-through — and a rewritten attribute
    reports as `!pr.name` beside the `+`/`-` of a name that came or went.
    Both classes are proved to bite: `!pr.street_class` / `!pr.region_id` /
    `!pr.streetWidth` on the prim attack above, and `!pt.is_node` on the same
    attack aimed at a point.

    ⚠️ **DETAIL attributes are still not compared — recorded, not closed.**
    Measured by accident while writing the attack above: with the wrangle's
    class left at Detail, `is_node = -12345` shipped as a **detail** attribute
    on output 3 and this check **passed**. Prim and point are the two classes
    that carry the street contract (§6), and the graph legitimately ships
    detail attributes the checks themselves read (`repair_converged`,
    `repair_iterations`), so closing this means deciding which of those the
    mesh is allowed to restate — a separate question from the pass-through.

    ⚠️ **Known gap, not covered here.** Cutting `blocks_id`'s second input —
    the identity consumer this check cites as a reason to keep input 0 —
    collapses every block's `region_id` to `region_00` and loses `land_use`,
    and **nothing in the suite fails.** Block identity has no check of its own.
    """
    name = "input0_reaches_an_output"
    if len(graph_geo.prims()) != len(mesh_graph_geo.prims()) or \
            len(graph_geo.points()) != len(mesh_graph_geo.points()):
        return Result(name, False,
                      {"in_prims": len(graph_geo.prims()),
                       "out_prims": len(mesh_graph_geo.prims()),
                       "in_points": len(graph_geo.points()),
                       "out_points": len(mesh_graph_geo.points())},
                      "the mesh's graph output is not its input 0")
    drift = []
    for kind, prim, a, b in (
            ("pr", True, graph_geo.primAttribs(), mesh_graph_geo.primAttribs()),
            ("pt", False, graph_geo.pointAttribs(), mesh_graph_geo.pointAttribs())):
        sa = set(x.name() for x in a)
        sb = set(x.name() for x in b)
        drift += ["+%s.%s" % (kind, n) for n in sorted(sb - sa)]
        drift += ["-%s.%s" % (kind, n) for n in sorted(sa - sb)]
        # ...and the VALUES, which is what "attribute for attribute" means. The
        # name sets alone passed a wrangle that rewrote street_class, region_id
        # and streetWidth on every edge — see the docstring.
        drift += ["!%s.%s" % (kind, n) for n in sorted(sa & sb)
                  if _attrib_values(graph_geo, n, prim)
                  != _attrib_values(mesh_graph_geo, n, prim)]
    worst = 0.0
    for a, b in zip(graph_geo.points(), mesh_graph_geo.points()):
        worst = max(worst, (a.position() - b.position()).length())
    return Result(name, worst == 0.0 and not drift,
                  {"prims": len(graph_geo.prims()), "max_move_m": worst,
                   "attrib_drift": drift or None},
                  "output 3 must be input 0 point for point and attribute for "
                  "attribute — the mesh republishes the graph it was given")


def every_block_is_subdivided(lot_geo, block_geo, floor=0):
    """A block with no parcels in it is a bare grey sector, and NOTHING here
    could see one.

    Written 2026-08-10 after the artist looked at a whole-city render of
    C_radial and reported that the lots had stopped existing. They had not —
    759 parcels ship, every block carries between 4 and 112 of them — but the
    only reason anyone could say so was an ad-hoc point-in-polygon count run by
    hand, and the suite genuinely had no way to tell the two apart:

    * `lots_tile_blocks` compares TOTAL lot area against TOTAL block area, so
      it is blind to which block the area came from,
    * `counts.lots` is informational and moves freely,
    * and every quality check here — simplicity, aspect, clear-of-roads — gets
      BETTER when parcels disappear, because a parcel that does not exist
      cannot be a bad one. `lots_are_simple_polygons` went 41 -> 0 and
      `lots_clear_of_roads.edge_m` 1290 -> 15.8 in one commit, and the honest
      question "is that a fix or a deletion?" had no assertion behind it.

    So: two teeth. Every block must hold at least one parcel, and the case must
    ship at least `floor` of them. The floor is per case in `cases.LOT_FLOOR`,
    set at ~90% of the shipped count — loose enough that a real improvement
    does not trip it, tight enough that a subdivision quietly failing does.

    Membership is measured by centroid-in-block, not by reading `block_id`, so
    a broken parcel->block linkage fails here instead of hiding here.
    """
    name = "every_block_is_subdivided"
    blocks = [pr for pr in block_geo.prims() if len(pr.vertices()) >= 3]
    if not blocks:
        return Result(name, len(lot_geo.prims()) >= floor,
                      {"lots": len(lot_geo.prims()), "blocks": 0, "empty": 0,
                       "floor": floor},
                      "no blocks in this case; only the floor applies")
    cents = []
    for pr in lot_geo.prims():
        vs = pr.vertices()
        n = float(len(vs))
        cents.append((sum(v.point().position()[0] for v in vs) / n,
                      sum(v.point().position()[2] for v in vs) / n))
    empty, worst = 0, None
    for pr in blocks:
        poly = [(v.point().position()[0], v.point().position()[2])
                for v in pr.vertices()]
        xs = [p[0] for p in poly]
        zs = [p[1] for p in poly]
        lo = (min(xs), min(zs))
        hi = (max(xs), max(zs))
        hit = 0
        for cx, cz in cents:
            if not (lo[0] <= cx <= hi[0] and lo[1] <= cz <= hi[1]):
                continue
            inside, j = False, len(poly) - 1
            for i in range(len(poly)):
                xi, zi = poly[i]
                xj, zj = poly[j]
                if (zi > cz) != (zj > cz) and \
                        cx < (xj - xi) * (cz - zi) / (zj - zi) + xi:
                    inside = not inside
                j = i
            if inside:
                hit += 1
                break
        if not hit:
            empty += 1
            if worst is None:
                worst = [round(sum(xs) / len(xs), 2), round(sum(zs) / len(zs), 2)]
    nlots = len(lot_geo.prims())
    return Result(name, empty == 0 and nlots >= floor,
                  {"lots": nlots, "blocks": len(blocks), "empty": empty,
                   "floor": floor, "empty_at": worst},
                  "blocks holding no parcel at all, and the per-case lot floor")


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


def _seg_dist_xz(a, b, q):
    """Point-segment distance on (x, z) tuples. Plain arithmetic on purpose:
    this is one half of a cross-check, so it may not share code with the thing
    it checks."""
    abx, abz = b[0] - a[0], b[1] - a[1]
    L2 = abx * abx + abz * abz
    if L2 < 1e-12:
        return math.hypot(q[0] - a[0], q[1] - a[1])
    t = max(0.0, min(1.0, ((q[0] - a[0]) * abx + (q[1] - a[1]) * abz) / L2))
    return math.hypot(q[0] - (a[0] + abx * t), q[1] - (a[1] + abz * t))


def _street_edge_xz(block, lot, tol):
    """`pfsl_street_edge` and `pfsl_frontage`, re-derived here in Python.

    ⚠️ This exists because of a defect three audits took to reach. The suite had
    a control rig proving the VEX FUNCTION is correct on synthetic input, and a
    label assertion proving the LABEL follows from the PUBLISHED ATTRIBUTE — and
    nothing at all spanning the gap between them. Corrupting the attribute at
    its call site left both halves agreeing with each other while the pipeline's
    decision was wrong: setting `lot_street_edge` to half its true value flipped
    218 parcels and the suite stayed green; setting it 0.04 under its own
    threshold flipped every parcel in every case to unbuildable, green.

    `lot_width` and `lot_aspect` never had that hole, because `_obb` here has
    always recomputed them from the shipped geometry. This is that same
    treatment for the other three inputs — measure the shipped rings, do not
    take the shipped numbers on trust.

    Returns (longest unbroken run, summed frontage).
    """
    nl, nb = len(lot), len(block)
    if nl < 2 or nb < 2:
        return 0.0, 0.0
    on, seg, total = [], [], 0.0
    for i in range(nl):
        a, b = lot[i], lot[(i + 1) % nl]
        mid = ((a[0] + b[0]) * 0.5, (a[1] + b[1]) * 0.5)
        d = min(_seg_dist_xz(block[k], block[(k + 1) % nb], mid)
                for k in range(nb))
        hit = d <= tol
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        on.append(hit)
        seg.append(L)
        if hit:
            total += L
    best = run = 0.0
    for _ in range(2):              # two laps: a run may straddle index 0
        for i in range(nl):
            if on[i]:
                run += seg[i]
                best = max(best, run)
            else:
                run = 0.0
    return min(best, total), total


def _area_xz(p):
    n = len(p)
    return abs(sum(p[i][0] * p[(i + 1) % n][1] - p[(i + 1) % n][0] * p[i][1]
                   for i in range(n))) * 0.5


def _expected_reject(lot_type, area, frontage, width, aspect, edge,
                     min_area, min_frontage, min_width, max_ratio, min_edge,
                     band):
    """The S8 ladder, recomputed from the evidence and the node's thresholds.

    Returns the label the pipeline should have written, or None when the parcel
    sits within `band` of the threshold of the rung that DECIDES it — a float32
    value against a float64 threshold flaps either way on the line.

    ⚠️ The first version tested every threshold up front and returned None if
    ANY was near. That silenced the other four rungs, and it was exploitable
    rather than merely loose: publishing `lot_street_edge` 0.04 below its own
    threshold put 1537 of 1537 parcels inside the band, so `label_wrong` read 0
    while every parcel in every case flipped to unbuildable. Only the deciding
    rung may unassert a parcel.

    A COURTYARD is exempt from the two FRONTAGE rungs, because being interior is
    its definition. It is NOT exempt from area, width or aspect — a courtyard
    that is a 2 m sliver is still a defect. The pipeline's exemption and this
    one both used to be blanket, which meant relabelling every rejected ribbon
    "courtyard" shipped 421 of them viable with a green suite.
    """
    court = (lot_type == "courtyard")
    for label, val, thr, over in (
            ("area", area, min_area, False),
            ("no_frontage", frontage, min_frontage, False),
            ("too_narrow", width, min_width, False),
            ("elongated", aspect, max_ratio, True),
            ("no_street_edge", edge, min_edge, False)):
        if thr is None:
            continue
        if court and label in ("no_frontage", "no_street_edge"):
            continue
        if abs(val - thr) <= band:
            return None                      # this rung decides, and it is a tie
        if (val > thr) if over else (val < thr):
            return label
    return ""


def lot_aspect_ratio(lot_geo, max_ratio=5.0, min_width=None, min_edge=None,
                     min_area=None, min_frontage=None, blocks_geo=None,
                     lot_depth=None, subdiv_mode=None, agree_tol=0.05):
    """Ribbons, not rectangles — and whether S8 both SAYS SO and SHOWS ITS WORK.

    ⚠️ Rewritten twice on 2026-08-11. First when S8 gained the shape tests: the
    old version measured `viable_only=True`, which was right while nothing set
    `lot_viable` from shape and became a check that CANNOT FAIL the moment
    something did — every ribbon marked non-viable, filtered out here, and a
    clean median reported over the survivors. Then again after an audit broke
    the pipeline eight ways and found three breaks this still slept through:
    deleting the published evidence, relabelling every rejection, and a
    tolerance that was green by luck.

    Five assertions now, none of which re-implements the ladder's ORDER (that
    would only prove the check agrees with itself):

    1. `lot_width` / `lot_aspect` are PUBLISHED. S8 promises the evidence ships
       with the verdict; nothing asserted it, and both could vanish silently.
    2. Those published values agree with an OBB measured here.
    3. No parcel the pipeline calls VIABLE is over the ratio, under the width,
       or under the street edge.
    4. Every `lot_reject` is in the known vocabulary.
    5. `lot_reject` non-empty and `lot_viable` == 0 agree, parcel by parcel.

    ⚠️ `agree_tol` is 0.05, not the 1e-4 it started at, and the reason is not
    slack. `lot_aspect` comes from an ARGMIN over candidate rectangles, and
    argmin is discontinuous: where two candidates tie in area, float32 VEX and
    float64 Python pick DIFFERENT rectangles and the ratio differs by a finite
    amount, not an epsilon. Measured on C_radial prims 473 and 406 — tied to
    1.4e-7 relative, disagreeing by 3.1e-2. At 1e-4 this check was one geometry
    nudge away from going red with no defect present. The band is set from that
    measurement, and it is still ~80x tighter than the smallest real defect it
    has to catch (the axis-aligned break moves aspect by whole integers).

    The distribution over ALL lots stays in the value, because it is the number
    that says whether the SUBDIVIDER improved. Labelling ribbons correctly is
    not the same as not producing them.
    """
    name = "lot_aspect_ratio"
    # The shipped block rings, so the ladder's frontage inputs can be
    # RE-MEASURED rather than taken on trust. Same tolerance `lots_subdiv`
    # uses, because a different one would report a disagreement that is only a
    # difference of question.
    rings, edge_bad, bad_courtyard = {}, [], []
    recomputed_n = 0
    courts = {}
    tol = None if lot_depth is None else max(lot_depth * 0.02, 0.05)
    if blocks_geo is not None:
        for bp in blocks_geo.prims():
            try:
                bid = bp.attribValue("block_id")
            except Exception:
                continue
            rings[bid] = [(v.point().position()[0], v.point().position()[2])
                          for v in bp.vertices()]
    ratios, offenders = [], []
    rejected = missing = mismatched = 0
    disagree, badvocab, label_wrong, bad_routing = [], {}, [], []
    for pr in lot_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        if len(pts) < 3:
            continue
        lng, shrt = _obb(pts)
        if shrt < 1e-9:
            continue
        ratio = lng / shrt
        ratios.append(ratio)

        # 1. the evidence must exist at all. `lot_street_edge` belongs here and
        #    was left out of the first version, which repeated the exact defect
        #    this assertion was written to fix: it appeared in the suite only in
        #    an ALLOW-LIST, and an allow-list does not require presence. Deleting
        #    it passed.
        try:
            pub_w = pr.attribValue("lot_width")
            pub_a = pr.attribValue("lot_aspect")
            pub_e = pr.attribValue("lot_street_edge")
            pub_ar = pr.attribValue("lot_area")
            pub_fr = pr.attribValue("lot_frontage")
            pub_ty = pr.attribValue("lot_type")
            pub_bid = pr.attribValue("block_id")
        except Exception:
            missing += 1
            continue
        # 2. ...and mean what it says. `lot_width` / `lot_aspect` are checked
        #    against `_obb`; `lot_street_edge`, `lot_frontage` and `lot_area`
        #    were checked against NOTHING until round three, which is how six
        #    corruptions of them shipped green — including one that flipped
        #    every parcel in the city.
        if abs(pub_a - ratio) > agree_tol or abs(pub_w - shrt) > agree_tol:
            disagree.append((pr.number(), round(pub_a, 3), round(ratio, 3),
                             round(pub_w, 3), round(shrt, 3)))
        if tol is not None and rings:
            ring = rings.get(pub_bid)
            if ring is None:
                edge_bad.append((pr.number(), "no such block", pub_bid))
            else:
                recomputed_n += 1
                xz = [(q[0], q[2]) for q in pts]
                re_edge, re_front = _street_edge_xz(ring, xz, tol)
                if abs(re_edge - pub_e) > agree_tol:
                    edge_bad.append((pr.number(), "street_edge",
                                     round(pub_e, 3), round(re_edge, 3)))
                elif abs(re_front - pub_fr) > agree_tol:
                    edge_bad.append((pr.number(), "frontage",
                                     round(pub_fr, 3), round(re_front, 3)))
                elif abs(_area_xz(xz) - pub_ar) > max(agree_tol, pub_ar * 1e-4):
                    edge_bad.append((pr.number(), "area", round(pub_ar, 2),
                                     round(_area_xz(xz), 2)))

        try:
            rej = pr.attribValue("lot_reject")
        except Exception:
            rej = ""
        # 4. the vocabulary is closed...
        if rej not in LOT_REJECT_VOCAB:
            badvocab[rej] = badvocab.get(rej, 0) + 1
        # ...and — the assertion the closed vocabulary was mistaken for — the
        # label must MATCH THE REASON. Membership in a set containing "area"
        # cannot detect relabelling everything to "area", which is exactly the
        # break that survived two rounds. Recomputing the ladder here is not
        # circular: every input is a PUBLISHED number and every threshold is
        # read off the node, so this catches a rung deleted, reordered,
        # mis-thresholded or relabelled.
        rung = _expected_reject(pub_ty, pub_ar, pub_fr, pub_w, pub_a, pub_e,
                                min_area, min_frontage, min_width, max_ratio,
                                min_edge, agree_tol)
        if rung is not None and rung != rej:
            label_wrong.append((pr.number(), rej, rung))
        try:
            viable = pr.attribValue("lot_viable") == 1
        except Exception:
            viable = True
        # 5. the two ways of saying "rejected" must agree
        if viable != (rej == ""):
            mismatched += 1
        # ⚠️ COURTYARD INVARIANTS RUN FIRST, on every parcel claiming the type,
        #    viable or not. They used to sit below `if not viable: continue`,
        #    which was written when a rejected courtyard could not exist — the
        #    pipeline retyped it `unbuildable`. Making a rejected courtyard
        #    reachable (so the exemption could skip rungs instead of erasing
        #    verdicts) created a state these assertions did not cover, and in
        #    the same commit that added them: 780 parcels could wear
        #    `lot_type` = "courtyard" in `recursive_obb`, a mode that cannot
        #    produce one, with 289 reject labels no longer matching their
        #    reason, on a fully green suite.
        #
        #    That is the fifth round of one defect: an assertion gated on a
        #    condition nobody asserts (the allow-list, the closed vocabulary,
        #    `if edge is not None`, `if tol is not None and rings`, and this).
        #    The general form is that each fix creates a new reachable state and
        #    each assertion is written for the states that existed before it.
        if pub_ty == "courtyard":
            # PROVENANCE. A courtyard is the interior remainder of an `offset`
            # perimeter block and no other mode can produce one, so a courtyard
            # anywhere else is a parcel wearing an exemption it did not earn.
            if subdiv_mode is not None and subdiv_mode != 1:
                bad_courtyard.append((pr.number(), "mode", subdiv_mode))
            # ...and the two invariants that make the exemption meaningful
            # rather than a word anyone can claim. Provenance alone is vacuous
            # IN offset mode, which is the only mode that can emit one: label
            # every ring parcel "courtyard" there and the exemption swallowed
            # all 61. A courtyard is INTERIOR (zero street frontage) and there
            # is at most ONE per block. Both are already measured above.
            if pub_fr > agree_tol or pub_e > agree_tol:
                bad_courtyard.append((pr.number(), "has frontage",
                                      round(pub_fr, 2)))
            courts[pub_bid] = courts.get(pub_bid, 0) + 1
            if courts[pub_bid] > 1:
                bad_courtyard.append((pr.number(), "second in block", pub_bid))

        if not viable:
            rejected += 1
            # `lot_type` IS the routing field, and S8 requires advisory to mean
            # ROUTED TO ANOTHER OUTCOME. 502 parcels carried lot_type "lot"
            # with lot_viable 0 because only lots_subdiv's two-rung test ever
            # wrote it; the three shape rungs never did.
            if pub_ty not in ("unbuildable", "courtyard"):
                bad_routing.append((pr.number(), pub_ty))
            continue
        # 3. nothing called viable may be over the line — measured on the
        #    PUBLISHED numbers, so deleting them cannot make this pass.
        #    A courtyard is exempt from the STREET-EDGE rung only, matching the
        #    ladder: being interior is its definition, but a courtyard that is a
        #    2 m sliver or a 30:1 ribbon is still a defect. This block used to
        #    `continue` on any courtyard, exempting it from aspect and width
        #    too — wider than the pipeline's own exemption, so the two disagreed
        #    about their own scope.
        if pub_a > max_ratio + agree_tol:
            offenders.append((round(pub_a - max_ratio, 3), "aspect",
                              pr.number(), round(pub_a, 2)))
        elif min_width is not None and pub_w < min_width - agree_tol:
            offenders.append((round(min_width - pub_w, 3), "width",
                              pr.number(), round(pub_w, 2)))
        elif (min_edge is not None and pub_ty != "courtyard"
              and pub_e < min_edge - agree_tol):
            offenders.append((round(min_edge - pub_e, 3), "street_edge",
                              pr.number(), round(pub_e, 2)))
    if not ratios:
        return _skip(name, "no lots with an OBB")
    ratios.sort()
    # worst FIRST, by how far over the line it is. This used to be
    # sorted(offenders)[:5] on a (kind, primnum) tuple, so the field named
    # `worst` reported the five lowest-numbered offenders.
    offenders.sort(reverse=True)
    # ⚠️ COVERAGE, not a truthy gate. The recomputation sits behind
    # `if tol is not None and rings:` — and with the blocks absent or their
    # block_id deleted it silently did not run, `evidence_recomputed` read 0,
    # and ALL SIX of round three's corruptions went green again. An assertion
    # whose condition is not itself asserted is the same defect three rounds
    # running: the allow-list, then `if edge is not None`, now this.
    uncovered = len(ratios) - missing - recomputed_n
    ok = (not offenders and not missing and not disagree and not badvocab
          and not mismatched and not label_wrong and not bad_routing
          and not edge_bad and not bad_courtyard and uncovered <= 0)
    value = {"max": round(ratios[-1], 2),
             "median": round(ratios[len(ratios) // 2], 2),
             "p90": round(ratios[int(len(ratios) * 0.9)], 2),
             "over": sum(1 for r in ratios if r > max_ratio),
             "lots": len(ratios), "rejected": rejected,
             "mislabelled": len(offenders), "no_evidence": missing,
             "evidence_disagrees": len(disagree), "viable_reject_mismatch":
             mismatched, "unknown_reject": badvocab,
             "label_wrong": len(label_wrong), "bad_routing":
             len(bad_routing), "evidence_recomputed": len(edge_bad),
             # every assertion that can turn this red must also be REPORTABLE.
             # `bad_courtyard` was in `ok` and in no field here, so the check
             # could go red without saying why and the baseline diff could not
             # see it move. Reported now, with the coverage counter beside it.
             "recomputed_n": recomputed_n, "uncovered": max(uncovered, 0),
             "courtyard_bad": len(bad_courtyard),
             "worst_courtyard": bad_courtyard[:3],
             "worst_recomputed": edge_bad[:3],
             "worst": [o[1:] for o in offenders[:5]],
             "worst_evidence": disagree[:3],
             "worst_label": label_wrong[:3], "worst_routing": bad_routing[:3]}
    return Result(name, ok, value,
                  "distribution over ALL lots; FAILS if the published evidence "
                  "is absent or disagrees by more than %g, if a viable lot "
                  "exceeds %.1f:1 / is under %s m wide / has under %s m of "
                  "street edge, or if a reject label is unknown or contradicts "
                  "lot_viable" % (agree_tol, max_ratio, min_width, min_edge))


# Five hand-answered cases for `pfsl_street_edge`, authored in metres and read
# as (x, z). The block is the square (0,0)-(100,100) throughout; `tol` is 0.5.
#
# `nibbles` is the whole reason the function exists and the reason this rig is
# committed: three separate 2 m touches of the same street. `pfsl_frontage`
# SUMS them to 6.0 and passes a 6 m minimum; the longest unbroken run is 2.0
# and no building fits. An audit replaced `pfsl_street_edge` with
# `pfsl_frontage`, with 1e9, and with half the true value, and every committed
# check stayed green through all three — because nothing measured it.
_EDGE_RIG_SNIPPET = """
#include <pf_streetlots.vfl>
vector B[] = { {0,0,0}, {100,0,0}, {100,0,100}, {0,0,100} };
float tol = 0.5;

vector all_on[]  = { {0,0,0}, {100,0,0}, {100,0,100}, {0,0,100} };
vector wrap[]    = { {0,0,0}, {100,0,0}, {100,0,20}, {0,0,20} };
vector onevert[] = { {0,0,0}, {20,0,10}, {10,0,20} };
vector nibbles[] = {
    {5,0,0}, {7,0,0}, {7,0,10}, {15,0,10}, {15,0,0}, {17,0,0},
    {17,0,10}, {25,0,10}, {25,0,0}, {27,0,0}, {27,0,20}, {5,0,20}
};
vector nothing[] = { {40,0,40}, {60,0,40}, {60,0,60}, {40,0,60} };

string names[] = { "all_on", "wrap", "one_vertex", "nibbles", "nothing" };
// hand-computed: the whole ring clamped to its own perimeter; the left+bottom+
// right run measured across the array start; a single shared vertex is not an
// edge; the longest of three 2 m touches; nothing at all.
float want[]  = { 400.0, 140.0, 0.0, 2.0, 0.0 };

for (int i = 0; i < 5; i++) {
    vector lot[];
    if (i == 0) lot = all_on;
    if (i == 1) lot = wrap;
    if (i == 2) lot = onevert;
    if (i == 3) lot = nibbles;
    if (i == 4) lot = nothing;
    int pt = addpoint(0, set(float(i), 0, 0));
    setpointattrib(0, "case", pt, names[i]);
    setpointattrib(0, "got",  pt, pfsl_street_edge(B, lot, tol));
    setpointattrib(0, "want", pt, want[i]);
    // the discriminator: SUM vs LONGEST RUN. Equal on four cases and 6 vs 2 on
    // `nibbles`, which is exactly the parcel the rung was added to catch.
    setpointattrib(0, "sum",  pt, pfsl_frontage(B, lot, tol));
}
"""
_EDGE_RIG_SUM = {"all_on": 400.0, "wrap": 140.0, "one_vertex": 0.0,
                 "nibbles": 6.0, "nothing": 0.0}


def street_edge_control_rig(city_node, tol=1e-3):
    """Run the SHIPPED `pfsl_street_edge` on cases whose answers are known.

    citygen_streets.md S8, "the third rung". Fifth control rig in the suite and
    here for the reason all five are: an audit broke the measurement three
    different ways — swapped it for the summed `pfsl_frontage`, pinned it to
    1e9, halved it — and the whole suite stayed green every time, because
    `lot_street_edge` was only ever named in an ALLOW-LIST and an allow-list
    does not require a value to be right, or even present.

    The assertion is `got == want` on five hand-computed cases, plus `sum`
    against `pfsl_frontage` so the two measures are pinned as DIFFERENT on the
    case that motivated the rung: 6.0 summed against a 2.0 longest run.

    ⚠️ Known and deliberately not asserted here: the per-edge test uses the edge
    MIDPOINT, so a lot edge whose midpoint lands on a reflex vertex of a
    concave block counts whole even when half of it is interior. `pfsl_frontage`
    has had the identical flaw since it was written. Measured over all 1537
    shipped parcels the worst error is 0.001 m and it flips no decision, so it
    is recorded rather than fixed — but a block with deep notches would change
    that, and this note is where to start looking.
    """
    name = "street_edge_control_rig"
    shown = next((c for c in city_node.children() if c.isDisplayFlagSet()), None)
    made = []
    try:
        city_node.allowEditingOfContents()
        w = city_node.createNode("attribwrangle", "__chk_edge_rig")
        made.append(w)
        w.parm("class").set(0)
        w.parm("snippet").set(_EDGE_RIG_SNIPPET)
        w.setInput(0, None)
        geo = w.geometry()
        rows = {}
        for pt in geo.points():
            rows[pt.attribValue("case")] = (round(pt.attribValue("got"), 4),
                                            round(pt.attribValue("want"), 4),
                                            round(pt.attribValue("sum"), 4))
    except Exception as exc:
        # FAIL, never skip: a rig that cannot run is a failure of the thing it
        # tests, not an absence of information about it.
        return Result(name, False, {"error": str(exc)[:200]},
                      "the street-edge control rig could not be run at all")
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

    wrong = {k: {"got": g, "want": wnt} for k, (g, wnt, _) in rows.items()
             if abs(g - wnt) > tol}
    badsum = {k: {"sum": sm, "want": _EDGE_RIG_SUM.get(k)}
              for k, (_, _, sm) in rows.items()
              if abs(sm - _EDGE_RIG_SUM.get(k, -1)) > tol}
    missing = sorted(set(_EDGE_RIG_SUM) - set(rows))
    value = {"cases": len(rows), "wrong": wrong, "frontage_wrong": badsum,
             "missing": missing,
             "nibbles_run_vs_sum": list(rows.get("nibbles", (None, None, None)))[::2]}
    return Result(name, not wrong and not badsum and not missing, value,
                  "pfsl_street_edge against five hand-computed answers; "
                  "`nibbles` must read 2.0 as a run and 6.0 as a sum")


def _orient_xz(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _seg_cross_xz(a, b, c, d):
    """Do two segments PROPERLY cross — strictly interior to both? Touching at
    an endpoint or lying collinear is not a crossing. Mirrors `pfsl_seg_cross`
    in VEX so the pipeline and the suite agree on what "simple" means."""
    o1, o2 = _orient_xz(a, b, c), _orient_xz(a, b, d)
    o3, o4 = _orient_xz(c, d, a), _orient_xz(c, d, b)
    return o1 * o2 < 0.0 and o3 * o4 < 0.0


def lots_are_simple_polygons(lot_geo, tol=1e-3):
    """Bowtie parcels: two lobes joined by a zero-width bridge — AND true
    crossings, which this check claimed to cover and did not.

    citygen_streets.md 4e-5 and S8. `pfsl_clip` was Sutherland-Hodgman, whose
    output is only guaranteed simple for a CONVEX subject, and every block here
    is non-convex. The clip then walks out along one lobe, back down the same
    line, and out along another.

    This needs its own check because the numeric ones cannot see it:
    `lots_tile_blocks` passes to 1e-8 because the bridge has ZERO AREA, and
    `no_duplicate_lot_footprints` compares centroids, which a bowtie shares with
    nothing.

    ⚠️ Rewritten 2026-08-11 after an audit. The predicate was "any vertex lying
    on a non-adjacent edge", and the docstring asserted that "covers the pinch
    (a repeated vertex) and a true crossing alike". **That is false**, and it
    hid a live pipeline defect for six audit rounds: two edges crossing X-wise
    with no vertex near the other edge are invisible to a vertex-to-edge
    distance test. `offset` mode was shipping 6 of 61 parcels folded through
    themselves, 5 of them labelled buildable, and the nearest vertex-to-edge
    distance on those six ran from 0.029 m to 1.14 m — up to three orders of
    magnitude outside this check's 1e-3 m tolerance. The stated property and the
    implemented predicate were different properties.

    So there are now TWO predicates, because they catch different things:

    * **proper edge-edge crossing** (`_seg_cross_xz`), exact and tolerance-free
      — the fold. Returns 0 on all 1476 `recursive_obb` parcels, so it
      manufactures no failures.
    * **vertex on a non-adjacent edge** within `tol` — the pinch, where a
      zero-width bridge has no transversal crossing to find. `tol` = 1 mm sits
      on a plateau: counts are stable from 1e-4 to 1e-2 m, above float32 P
      quantisation (~6e-5 m at the domain edge) and far below any real feature.
    """
    name = "lots_are_simple_polygons"
    bad, viable = 0, 0
    for pr in lot_geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        n = len(pts)
        if n < 4:
            continue
        hit = False
        # the FOLD: an exact, tolerance-free crossing test
        xz = [(q[0], q[2]) for q in pts]
        for i in range(n):
            for j in range(i + 2, n):
                if i == 0 and j == n - 1:
                    continue                      # adjacent across the seam
                if _seg_cross_xz(xz[i], xz[(i + 1) % n],
                                 xz[j], xz[(j + 1) % n]):
                    hit = True
                    break
            if hit:
                break
        # the PINCH: a zero-width bridge has no transversal crossing to find
        for i in range(n):
            if hit:
                break
            a, b = pts[i], pts[(i + 1) % n]
            for j in range(n):
                if j == i or j == (i + 1) % n or (j + 1) % n == i:
                    continue                      # shares a vertex with this edge
                if _seg_point_dist(a, b, pts[j]) < tol:
                    hit = True
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
                  "lot_viable", "land_use", "region_id", "source_node", "layer",
                  # the evidence behind a shape rejection, published so the
                  # label can be argued with rather than taken on trust
                  "lot_width", "lot_aspect",
                  # ...and the label itself, which was being counted as a leak
                  # while the shipped parm help told artists to read it
                  # ("a parcel under this area gets `lot_reject` = \"area\"").
                  # One of the two had to be wrong; the help is right, and
                  # citygen.md 2.2 backs it: a validation warning is "persisted
                  # as an attribute/record on the offending element".
                  "lot_reject", "lot_street_edge")

# The complete `lot_reject` vocabulary. Pinned here so a typo, a silently
# dropped rung or a relabelling is a test failure rather than a shrug: an
# auditor broke the ladder by relabelling every rejection "area" and every
# check stayed green.
LOT_REJECT_VOCAB = ("", "area", "no_frontage", "too_narrow", "elongated",
                    "no_street_edge")
LOT_POINT_ATTRS = ("P",)


# The U-shaped block from `pf_streetlots.vfl`'s comment block, run through the
# SHIPPED clipper. Authored in metres, read as (x, z).
#
#   U    = (0,0)(100,0)(100,60)(60,60)(60,20)(40,20)(40,60)(0,60)
#   notch = x in [40, 60], z in [20, 60]  -- the dead-end stub's ROAD
#
# It is the shape of every block that wraps a dead-end stub, and it is the
# worst case rather than a typical one: two of its vertices lie EXACTLY on the
# clip line, so pairing crossings in sorted order sees no crossing at the notch
# mouth at all and hands back the bridged ring again.
_CLIP_RIG_SNIPPET = """
#include <pf_streetlots.vfl>
vector U[] = {
    {0,0,0}, {100,0,0}, {100,0,60}, {60,0,60},
    {60,0,20}, {40,0,20}, {40,0,60}, {0,0,60}
};
vector R[] = { {0,0,0}, {100,0,0}, {100,0,60}, {0,0,60} };

void emit(const int geo; const vector pts[]; const int cnt[]; const string tag) {
    int off = 0;
    for (int i = 0; i < len(cnt); i++) {
        int pr = addprim(geo, "poly");
        setprimattrib(geo, "rig", pr, tag);
        for (int k = 0; k < cnt[i]; k++) {
            vector q = pts[off + k];
            addvertex(geo, pr, addpoint(geo, q));
        }
        off += cnt[i];
    }
}

vector o[];  int c[];
pfsl_clip_multi(U, set(0,0,20), set(0,0,-1), o, c);   // keep z >= 20
emit(0, o, c, "u_keep_top");
pfsl_clip_multi(U, set(0,0,20), set(0,0,1), o, c);    // keep z <= 20
emit(0, o, c, "u_keep_bottom");
pfsl_clip_multi(U, set(0,0,40), set(0,0,-1), o, c);   // keep z >= 40, MID-notch
emit(0, o, c, "u_mid");
pfsl_clip_multi(R, set(0,0,20), set(0,0,-1), o, c);   // convex control
emit(0, o, c, "convex");
"""

# What Sutherland-Hodgman returns for the convex control, in ITS order. The
# replacement has to be a drop-in on a convex subject or every lot in the city
# is re-cut for no reason, so the ORDER is asserted, not just the area.
_CLIP_RIG_CONVEX = [(100.0, 20.0), (100.0, 60.0), (0.0, 60.0), (0.0, 20.0)]


def lot_clip_control_rig(city_node, tol=1e-3):
    """Run the SHIPPED half-plane clipper on the concave case no block reaches.

    citygen_streets.md S8. `pfsl_clip` was Sutherland–Hodgman, which is only
    safe on a CONVEX subject; every block in this project is non-convex (2/2,
    9/9, 13/13, up to 291 reflex vertices). S-H on a concave subject returns ONE
    ring joining the disjoint pieces with a ZERO-WIDTH BRIDGE, and around a
    dead-end stub that bridge runs down the middle of the stub's pavement.
    Measured on C_radial: **39 lots, 1290.6 m of boundary inside the road
    surface**, with `lots_clear_of_roads.m2` reading 0.0 at cell sizes down to
    0.01 m because the bridge encloses no area.

    So this is the fourth control rig in the suite, and it is here for the
    reason all four are: **the case that breaks the mechanism is one the shipped
    cases only reach by luck.** C_radial happens to produce U-shaped blocks;
    A_drawn and D_offset do not, and both read a clean 0.0 m throughout. A fix
    verified only against C is verified against whichever concavities C happens
    to have this week.

    Three assertions, and the third is the one with teeth:

    * **areas** — the two prongs are 1600 m² each and the bar is 2000 m². S-H
      got these right too; area was never the failing quantity.
    * **simplicity** — same predicate as `lots_are_simple_polygons`, so a piece
      that self-touches fails here first and in the same units.
    * **nothing in the notch** — no emitted edge may pass through the OPEN
      rectangle x ∈ (40, 60), z ∈ (20, 60), which IS the stub's road.

    ⚠️ The doc's own control cut lands EXACTLY on the notch mouth, and there
    S-H's bridge lies along z = 20 — on the notch's boundary, not through its
    interior — so the notch test has no teeth on it and the piece count carries
    it instead (S-H: one 3200 m² ring; correct: two of 1600). `u_mid` is the
    same U cut at z = 40, which is where every real cut lands, and there the
    bridge runs from (0,40) to (100,40) straight across the open notch. Without
    that case the third assertion is decoration. Both are kept: the first is the
    degenerate one (two vertices exactly on the clip line, so there is no
    crossing at the mouth to pair), the second is the common one.

    Plus a drop-in assertion on the convex control: same ring, same vertex
    ORDER, so switching clippers cannot silently re-cut every convex block in
    the city through a different rand() sequence.
    """
    name = "lot_clip_control_rig"
    shown = next((c for c in city_node.children() if c.isDisplayFlagSet()), None)
    made = []
    try:
        city_node.allowEditingOfContents()
        w = city_node.createNode("attribwrangle", "__chk_clip_rig")
        made.append(w)
        w.parm("class").set(0)                       # detail: it builds its own
        w.parm("snippet").set(_CLIP_RIG_SNIPPET)
        w.setInput(0, None)
        geo = w.geometry()
        pieces = {}
        for pr in geo.prims():
            pts = [(round(v.point().position()[0], 6),
                    round(v.point().position()[2], 6)) for v in pr.vertices()]
            pieces.setdefault(pr.attribValue("rig"), []).append(pts)
    except Exception as exc:
        # FAIL, never skip — see turn_clamp_control_rig. A rig that cannot run
        # is a failure of the thing it tests.
        return Result(name, False, {"error": str(exc)[:200]},
                      "the clip control rig could not be run at all")
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

    def area(p):
        return abs(sum(p[i][0] * p[(i + 1) % len(p)][1]
                       - p[(i + 1) % len(p)][0] * p[i][1]
                       for i in range(len(p)))) * 0.5

    top = sorted(round(area(p), 3) for p in pieces.get("u_keep_top", []))
    bot = sorted(round(area(p), 3) for p in pieces.get("u_keep_bottom", []))
    mid = sorted(round(area(p), 3) for p in pieces.get("u_mid", []))
    conv = pieces.get("convex", [])

    # the notch IS the stub's road; sample every edge of every piece
    in_notch = 0
    for ps in pieces.values():
        for p in ps:
            for i in range(len(p)):
                a, b = p[i], p[(i + 1) % len(p)]
                for k in range(1, 8):
                    t = k / 8.0
                    x = a[0] + (b[0] - a[0]) * t
                    z = a[1] + (b[1] - a[1]) * t
                    if 40.0 + tol < x < 60.0 - tol and 20.0 + tol < z < 60.0 - tol:
                        in_notch += 1
                        break

    nonsimple = 0
    for ps in pieces.values():
        for p in ps:
            n = len(p)
            if n < 4:
                continue
            P = [hou_vec3(x, z) for (x, z) in p]
            for i in range(n):
                a, b = P[i], P[(i + 1) % n]
                if any(_seg_point_dist(a, b, P[j]) < tol
                       for j in range(n)
                       if j != i and j != (i + 1) % n and (j + 1) % n != i):
                    nonsimple += 1
                    break

    value = {"u_keep_top": top, "u_keep_bottom": bot, "u_mid": mid,
             "convex_pieces": len(conv),
             "convex_order_matches_SH":
                 bool(len(conv) == 1
                      and [(round(x, 3), round(z, 3)) for (x, z) in conv[0]]
                      == _CLIP_RIG_CONVEX),
             "edges_in_notch": in_notch, "nonsimple": nonsimple}
    ok = (top == [1600.0, 1600.0] and bot == [2000.0]
          and mid == [800.0, 800.0]
          and value["convex_order_matches_SH"]
          and in_notch == 0 and nonsimple == 0)
    return Result(name, ok, value,
                  "the shipped clipper on a U-shaped block split across the "
                  "notch mouth: two 1600 m2 prongs and a 2000 m2 bar, no piece "
                  "self-touching, and NO edge crossing the notch - the notch is "
                  "the dead-end stub's road, and a Sutherland-Hodgman bridge "
                  "runs straight down it")


def hou_vec3(x, z):
    """A 3-vector in the XZ plane, for reusing the geometric helpers above on
    plain coordinate pairs."""
    import hou
    return hou.Vector3(x, 0.0, z)


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

    ⚠️ `lot_reject` WAS counted as leakage here; that call was reversed on
    2026-08-11 and it is now allow-listed. It is a published output by design:
    `citygen.md` §2.2 says a validation warning is "persisted as an
    attribute/record on the offending element", and the shipped parm help on
    `min_lot_area` has told artists to read it since before the shape rungs
    existed. One of the two had to be wrong, and it was this list.

    ⚠️ **`None` means "do not police this class", and the city output is why it
    exists.** This is the only thing in the suite that looks at DETAIL
    attributes at all, and until 2026-08-10 it was only ever called on the lots
    — so all five `repair_*` details plus `orphan_edges_dropped` rode out on the
    city mesh with nothing to see them (`attribute_schema` checks graph prim and
    road point attributes only). The city's ~50 prim and ~18 point attributes
    are a separate, larger question that has no agreed schema yet; freezing them
    here as "allowed" would bless on the city exactly the names this check FAILS
    on for the lots. So the city call passes `None` for both and polices the
    detail attributes, which do have an agreed answer.
    """
    leaked = []
    if prim_allowed is not None:
        for a in geo.primAttribs():
            if a.name() not in prim_allowed:
                leaked.append("pr." + a.name())
    if point_allowed is not None:
        for a in geo.pointAttribs():
            if a.name() not in point_allowed:
                leaked.append("pt." + a.name())
    if detail_allowed is not None:
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


def _turn_at(a, b, c):
    """Mirror of `pfsg_turn_at`: |turn| at b and the two edge lengths.

    ⚠️ THE ANGLE IS PROJECTED INTO XZ AND THE LENGTHS ARE NOT, exactly as the
    VEX does it. This used to be `acos(dot)` — a true 3D angle — against the
    VEX's `atan2(cross(u, v).y, dot(u, v))`. The two agree to 2.6e-8 rad over
    497 vertices *while the graph is planar*, and would diverge silently the day
    a centreline acquires Y, which §S5b's terrain will bring. A check that
    mirrors the solver must mirror the metric, not a metric that happens to
    agree today. `graph_planar_y` is the standing assertion that they still do.
    """
    e1, e2 = b - a, c - b
    l1, l2 = e1.length(), e2.length()
    if l1 < 1e-9 or l2 < 1e-9:
        return 0.0, l1, l2
    u, v = e1 / l1, e2 / l2
    return (abs(math.atan2(u[2] * v[0] - u[0] * v[2],
                           u[0] * v[0] + u[2] * v[2])), l1, l2)


def _turn_ceilings(pts, rmin, gain, closed):
    """Per-vertex turn (radians) and its ceiling, from geometry alone.

    Returns (phi, ceiling); either list holds None where the vertex has no turn
    to bound.

    ⚠️ `gain <= 0` gives ceiling == the class allowance, so the spike residual
    degenerates to `max_kappa_over_clamp` exactly -- by construction, not by
    coincidence. WHICH MEANS THE SMOOTHNESS ASSERTION IS SIMPLY ABSENT AT
    gain 0: "gain 0 -> 16 failing, gain 2 -> 17" in the sweep table below
    compares two runs with different assertions in force, and the missing
    failure at 0 is this check no longer testing anything the class clamp does
    not already test. Recorded, not fixed: pinning the check to a fixed gain
    would make it stop measuring the parameter the build actually ships with.
    """
    n = len(pts)
    phi = [0.0] * n
    cls = [None] * n
    rng = list(range(n)) if closed else list(range(1, n - 1))
    for i in rng:
        t, l1, l2 = _turn_at(pts[(i - 1) % n], pts[i], pts[(i + 1) % n])
        if l1 < 1e-9 or l2 < 1e-9:
            continue
        phi[i] = t
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
            t, l1, l2 = _turn_at(pts[(i - 1) % n], pts[i], pts[(i + 1) % n])
            if l1 < 1e-9 or l2 < 1e-9:
                continue
            # discrete curvature x R_min: 1.0 IS the clamp
            ratio = t / (0.5 * (l1 + l2)) * rmin
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


def _junction_graph(graph_geo, floor):
    """Endpoint degree, edge lengths, and the clusters a multi-leg junction hides
    in.

    Returns (deg, edges, clusters) where `edges` is [(a, b, length)] over the
    polyline ENDPOINTS only - interior vertices of a polyline are shape, not
    topology, and `graph_polypath` has already merged every degree-2 node away,
    so there are none to find.
    """
    deg, edges = {}, []
    for pr in graph_geo.prims():
        vs = list(pr.vertices())
        if len(vs) < 2:
            continue
        pts = [v.point().position() for v in vs]
        L = sum((pts[i] - pts[i - 1]).length() for i in range(1, len(pts)))
        a, b = vs[0].point().number(), vs[-1].point().number()
        deg[a] = deg.get(a, 0) + 1
        deg[b] = deg.get(b, 0) + 1
        edges.append((a, b, L))

    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(x, y):
        rx, ry = find(x), find(y)
        if rx != ry:
            parent[ry] = rx

    for a, b, L in edges:
        if L < floor and deg.get(a, 0) >= 3 and deg.get(b, 0) >= 3:
            union(a, b)
    clusters = {}
    for p in deg:
        clusters.setdefault(find(p), []).append(p)
    return deg, edges, clusters


def junctions_not_too_close(graph_geo, floor):
    """No edge may join two junctions closer together than `floor` metres.

    THE JOG RULE, and it is the one threshold here taken from subdivision street
    standards rather than from measurement: street jogs offset under 125-150 ft
    (38-46 m) are prohibited, and `graph_params_min_node_dist` defaults to 40 m,
    inside that band. The value was already right and nothing enforced it - it
    was read in exactly ONE place, `graph_extend`, as a rejection test when
    landing a NEW junction. Nothing ever looked at the junctions tracing had
    already produced.

    What its absence cost: C_radial shipped three junctions closing a
    19.9 x 25.4 x 31.6 m triangle - present from the first stitched state, in
    BOTH the old `pf_citygen_streets` chain and the new Segmenter, and untouched
    by graph_extend, graph_prune, graph_min_angle, graph_kill_angle and
    graph_drop_tongue. S5 then solved three junction patches into the space of
    one and they collided. The artist found it in the viewport; not one check in
    this file could see it. See S5a.
    """
    name = "junctions_not_too_close"
    deg, edges, _ = _junction_graph(graph_geo, floor)
    worst, at, count = None, None, 0
    for a, b, L in edges:
        if deg.get(a, 0) < 3 or deg.get(b, 0) < 3:
            continue
        if worst is None or L < worst:
            p = graph_geo.point(a).position()
            worst, at = L, [round(p[0], 1), round(p[2], 1)]
        if L < floor:
            count += 1
    return Result(name, count == 0,
                  {"under": count,
                   "shortest_m": None if worst is None else round(worst, 2),
                   "worst_at": at},
                  "shortest edge joining two junctions; the floor is %.1f m"
                  % floor)


def no_multileg_junctions(graph_geo, floor, cap=4):
    """No junction may carry more than `cap` arms - counted AFTER near-coincident
    junctions are treated as one.

    ⚠️ THE ARM COUNT IS NOT THE NODE DEGREE, and reading the degree is exactly
    what hid this defect through two pipelines. C_radial's five-way is spelled as
    three nodes of degree 3, 4 and 4 standing 20-32 m apart, so a degree
    histogram reports a maximum of 4 and passes - it did, on every run, while the
    junction was visibly broken. Cluster junctions joined by an edge shorter than
    `floor` first, then count the edges LEAVING the cluster: 3 + 4 + 4 arms less
    two ends each for the 3 internal edges leaves exactly 5.

    Multi-leg intersections (5+ legs) are to be avoided in published practice,
    and the accepted resolutions are realign a leg into a separate T, make it a
    roundabout, or eliminate a leg - which S3 forbids outright. This check does
    not care which is chosen; it asserts the cap. See S5a.

    It is deliberately NOT a subset of `junctions_not_too_close`: collapsing the
    stub edges makes that one green and leaves this one red, which is the whole
    shape of the defect and the reason both are committed.
    """
    name = "no_multileg_junctions"
    deg, edges, clusters = _junction_graph(graph_geo, floor)
    site = {}
    for root, members in clusters.items():
        for m in members:
            site[m] = root
    arms = {}
    for a, b, L in edges:
        ra, rb = site[a], site[b]
        if ra == rb:
            continue                      # internal to the cluster: not an arm
        arms[ra] = arms.get(ra, 0) + 1
        arms[rb] = arms.get(rb, 0) + 1
    worst, at, over, merged = 0, None, 0, 0
    for root, members in clusters.items():
        k = arms.get(root, 0)
        if len(members) > 1:
            merged += 1
        if k < 3:
            continue                      # a dead end or a through-node, not a junction
        if k > worst:
            p = graph_geo.point(members[0]).position()
            worst, at = k, [round(p[0], 1), round(p[2], 1)]
        if k > cap:
            over += 1
    return Result(name, over == 0,
                  {"max_arms": worst, "over_cap": over,
                   "clusters_merged": merged, "worst_at": at},
                  "arms at the busiest junction, counting junctions within "
                  "%.1f m as one; the cap is %d" % (floor, cap))


def connections_are_never_refused(graph_geo):
    """No repair pass after the first may DELETE a street.

    S3: *"a connection is never refused"*. Every other check in this file
    measures junction HEALTH, and every one of them is satisfied just as well by
    removing an arm as by fixing it. That is not a hypothetical: the sixth S5a
    attempt reported `no_multileg_junctions` green while `graph_kill_angle`
    blasted **8 streets across passes 1 and 2, two of them arterials** — the
    realign had dragged the whole junction 40 m, pushed arms under
    `min_junction_angle`, and the existing cleanup rule then removed them. The
    arm cap was reached by resolution 3, the one S3 forbids outright, and the
    suite could not tell the two apart because junction health and street
    preservation were asserted separately and never together. This is the union
    term, and it would have gone red on that build's first run.

    Pass 0 is exempt and deliberately so: `graph_min_angle` exists to remove the
    near-parallel duplicates TRACING produced, and on this build it removes none
    on any of the nine cases. From pass 1 the graph is being repaired rather than
    cleaned, so a kill there is a repair destroying a street to make its own
    numbers work.

    The counts are written inside the Segmenter's repair loop
    (`repair_<node>_pass0` / `repair_<node>_late`) because the loop is a feedback
    block: Single Pass on `repair_end` re-runs one iteration from the ORIGINAL
    input rather than stepping the feedback, so the per-pass state is not
    reachable from outside — measured 2026-08-12, `repair_iterations` came back 1
    for every requested pass. A MISSING attribute fails rather than skipping; the
    same "fails open" trap already cost this suite a silently dropped width
    assertion (see `lot_aspect_ratio`).

    ⚠️ **IT COUNTED ONE NODE OUT OF FIVE, which is the same blind spot one level
    up.** The first version read only `graph_min_angle`'s flags, and an audit
    found FOUR other nodes in the same repair loop that delete primitives with
    nothing asserting any of them: `graph_prune` (short dead ends, inside its own
    6-iteration loop), `graph_drop_orphans` (whole components carrying no
    junction), `graph_drop_tongue` (arms the junction mouth has eaten) and
    `graph_stub_kill` (the jog collapse). A repair that reached its numbers
    through any of those four would have shipped green past a tripwire written
    for exactly that failure. `orphan_edges_dropped` was already on the geometry
    and read by no check at all.

    **`graph_stub_kill` is the one deletion the design ASKS for** and it is
    reported, never flagged: the jog edge goes and its two junctions become one,
    so the connection survives as the merged node. It is counted separately
    rather than ignored, because a by-design deletion nobody counts is
    indistinguishable from a refusal.

    The others are refusals when they fire late, on the same reasoning that
    exempts pass 0 for `graph_min_angle`: measured 2026-08-12 across all nine
    committed cases, every one of them deletes ONLY in pass 0 — prune 0-3, orphan
    0-3, tongue 0-8, late counts 0 everywhere — so a late deletion is a repair
    destroying a street, not tracing residue being cleaned.

    ⚠️ **`graph_drop_tongue` IS BY DESIGN TOO, and counting it as a refusal made
    this check RED ON THE ARTIST'S OWN SCENE — which is how a tripwire gets
    muted.** An audit found `repair_tongue_late` 1 there: a 42.00 m arterial at
    (−240.37, 232.73) → (−210.19, 203.54), dropped in pass 1. Pre-existing and
    nothing to do with S5a — with all four S5a nodes bypassed the graph is 95
    prims converging in 9 passes, §S5a's own pre-S5a numbers, and the drop still
    happens. Root cause: in pass 0 that node has three arms, and pass 1's
    extend/stitch lands a fourth; `s5j_tongue_mark` only considers dead-end arms
    off nodes of degree ≥ 4, so the 42 m arm became a candidate the instant the
    node reached degree 4. Late is normal for it, not suspicious.

    **The classification is decidable from the code's own rails, not from
    taste.** `s5j_tongue_mark` is guarded to LEAF arms only and must leave the
    node three arms (`if ((!leafstart && !leafend) || (leafstart && leafend) ||
    junc < 4 …) removeprim`), and `pfsg_is_short_stub` carries the same rail. A
    tongue drop therefore removes an arm that already went nowhere: no connection
    between two places is refused. `G_tongue` is a committed case whose entire
    purpose is to assert that this drop HAPPENS — counting it as a refusal put
    two committed checks in direct contradiction.

    So of the five instrumented nodes only **`graph_min_angle` and
    `graph_drop_orphans`** can refuse a connection by construction. `graph_prune`
    is left in the refusal set for now: it deletes short dead ends, which is
    arguably the same by-design case, but nobody has read its rails the way the
    tongue's were read, and it fires late on nothing today. Read them before
    reclassifying it — that is exactly the shortcut that produced the false red
    above. Every node stays in the value dict either way, so a baseline diff
    still catches movement in any of them.
    """
    name = "connections_are_never_refused"
    # (attribute stem, the node that does the deleting, is it a refusal?)
    NODES = (("killed", "graph_min_angle", True),
             ("prune", "graph_prune", True),
             ("orphan", "graph_drop_orphans", True),
             ("tongue", "graph_drop_tongue", False),
             ("stub", "graph_stub_kill", False))
    missing, pass0, late, refused = [], {}, {}, 0
    for stem, node, is_refusal in NODES:
        for when in ("pass0", "late"):
            attr = "repair_%s_%s" % (stem, when)
            if graph_geo.findGlobalAttrib(attr) is None:
                missing.append(attr)
                continue
            v = graph_geo.attribValue(attr)
            (pass0 if when == "pass0" else late)[node] = v
            if when == "late" and is_refusal:
                refused += v
    if missing:
        return Result(name, False, {"missing": missing},
                      "the segmenter is not reporting %s — the tripwire in the "
                      "repair loop is gone" % ", ".join(missing))
    return Result(name, refused == 0,
                  {"killed_after_pass0": late["graph_min_angle"],
                   "killed_in_pass0": pass0["graph_min_angle"],
                   "refused_after_pass0": refused,
                   "deleted_late": late,
                   "deleted_in_pass0": pass0,
                   "by_design_stub_collapse": [pass0["graph_stub_kill"],
                                               late["graph_stub_kill"]]},
                  "streets deleted by every node in the repair loop that can "
                  "delete one; a repair may fix a junction but may never delete "
                  "an arm to do it. The stub collapse deletes BY DESIGN and is "
                  "reported, not counted as a refusal")


def trim_leaves_road_standing(streets_geo, floor=1.0, width_floor=0.0):
    """A junction may never trim away the whole street it opens onto — and what
    it leaves must be longer than the street is WIDE.

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

    ⚠️ **A FIXED METRE IS THE WRONG QUANTITY, and 1.0 m passed the defect the
    artist circled four times.** C_radial's prim 60 was a 24.00 m `local` arm
    whose four-way mouth ate 17.75 m, shipping **6.24 m of pavement at 14.4 m
    width** — wider than it is long, sticking out of the patch and stopping
    flat. 6.24 > 1.0, so this check passed, and so did every other one.
    City-wide worst was prim 73 at (58.57, 397.41), **ratio 0.23**. What makes a
    leg legible is its length against its own WIDTH.

    So the second number is `min_ratio` = standing / streetWidth, and
    `s5j_params_min_standing_widths` is the floor under it. `s5j_tongue_mark`
    enforces it by dropping the arm before the junction is solved for real.

    ⚠️ **THE ASSERTION IS SCOPED TO WHAT THE MECHANISM CAN ACTUALLY REMOVE,
    and the two other numbers are recorded so the scope stays visible.** Only a
    DEAD-END arm off a junction of degree >= 4 may be dropped: a street between
    two junctions carries the graph and deleting it disconnects the city (the
    answer there is §S3's node merge), and taking a node below degree 3 leaves
    two streets meeting at a corner the S3b clamp has already run past. So
    `under_ratio` — droppable arms still under the floor — is what fails, and
    `under_ratio_all` counts every street under it, droppable or not. Measured
    after the fix: `under_ratio` 0 everywhere; `under_ratio_all` is 3 on
    C_radial (two-junction streets at 0.82–0.85, all arterials) and 1 on
    E_short_t, whose 20 m arm hangs off a degree-3 T at ratio 0.21 and is the
    whole reason that case exists. Widening the rails is §S3 node-merge work,
    not a threshold to turn up.
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
    # endpoint degree, counted over the street prims only — the patches are
    # already blasted out of this stream, so point.prims() IS the arm count
    deg = {}
    for pr in streets_geo.prims():
        vs = list(pr.vertices())
        if len(vs) < 2:
            continue
        for v in (vs[0], vs[-1]):
            n = v.point().number()
            deg[n] = deg.get(n, 0) + 1

    worst, count, at = None, 0, None
    wratio, rat_at, under_ratio, under_ratio_all = None, None, 0, 0
    for pr in streets_geo.prims():
        vs = list(pr.vertices())
        pts = [v.point().position() for v in vs]
        if len(pts) < 2:
            continue
        L = sum((pts[i] - pts[i - 1]).length() for i in range(1, len(pts)))
        standing = L - sum(pr.attribValue(a) for a in have)
        if worst is None or standing < worst:
            worst, at = standing, [round(pts[0][0], 2), round(pts[0][2], 2)]
        if standing < floor:
            count += 1
        try:
            w = pr.attribValue("streetWidth")
        except Exception:
            w = 0.0
        if w <= 0.0:
            continue
        # ⚠️ A CUL-DE-SAC BULB IS NOT A JUNCTION EATING THE STREET, it is the
        # street's own terminus, so it is added back before the ratio. Without
        # this every bulbed dead end reads as the tongue defect it has nothing
        # to do with — C_radial went to under_ratio = 1 on a street whose
        # junction end had not moved at all. The absolute floor above still
        # counts it, because a street with nothing left is still a hole in the
        # city however it got that way.
        try:
            standing += pr.attribValue("culdesac_trim")
        except Exception:
            pass
        ratio = standing / w
        if wratio is None or ratio < wratio:
            wratio, rat_at = ratio, [round(pts[0][0], 2), round(pts[0][2], 2)]
        if width_floor > 0.0 and ratio < width_floor:
            under_ratio_all += 1
            d0 = deg.get(vs[0].point().number(), 0)
            d1 = deg.get(vs[-1].point().number(), 0)
            leaf = (d0 == 1) != (d1 == 1)
            junc = d1 if d0 == 1 else d0
            if leaf and junc >= 4:
                under_ratio += 1
    return Result(name, count == 0 and under_ratio == 0,
                  {"min_standing_m": None if worst is None else round(worst, 3),
                   "under": count, "worst_at": at,
                   "min_ratio": None if wratio is None else round(wratio, 3),
                   "worst_ratio_at": rat_at,
                   "under_ratio": under_ratio,
                   "under_ratio_all": under_ratio_all},
                  "street length left after both junction trims; below %.2f m "
                  "s5j_trim is about to delete it under a live mouth, and "
                  "below %.2f x its own WIDTH it ships as a tongue of pavement "
                  "instead of a street (asserted on the dead-end arms off "
                  "degree >= 4 nodes, which is what s5j_tongue_mark can remove)"
                  % (floor, width_floor))


def turn_clamp_control_rig(city_node, slack=1.02, floor=1.0, flat=1.25,
                           flat_ring=2.0):
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

    **AND IT IS SIZED FROM THE LIVE `turn_radius_scale`**, because the same
    pattern caught it a fifth time. The rig legs were authored at
    R_min = 26.8 m — `turn_radius_scale` = 2 — and `_RIG_INPUT_KAPPA` was a pair
    of constants measured at that one value. κ × R_min is linear in the scale
    and the check reads the live parm, so at scale 1/3/4/6/8 the whole suite
    went 17 → 24/23/25/24 failing and **six of the ~7 extra at every scale were
    this rig, on all six cases**: `bend90`'s 80 m legs cannot host a 90° turn of
    R = 107 m at scale 8, and the infeasible pair was being compared against a
    scale-2 number. Two cures, both here: every authored coordinate is scaled by
    `R_min / 26.8` so a rig authored feasible stays feasible and one authored
    infeasible stays infeasible at every scale, and the bound on the infeasible
    pair is **measured off the input geometry** rather than hard-coded. The
    slider ships {1 8}; a rig that only works at 2 is calibration, not a check.

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
    # the rig is authored at R_min = 26.8 m, i.e. turn_radius_scale = 2
    rig_f = city_node.parm("graph_params_turn_radius_scale").eval() / 2.0
    # every value in the shipped {0 8} range that a slider makes easy to land on
    gains = (0.0, 0.5, 1.0, 2.0, 4.0, 8.0)
    try:
        src = city_node.createNode("python", "__chk_rig_src")
        made.append(src)
        src.parm("python").set("F = %.9f\n" % rig_f + _RIG_SNIPPET)
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
        why = _rig_verdict(sweep[gain], slack, floor, flat, flat_ring)
        if why:
            bad["%g" % gain] = why
    value = dict(got)
    # ⚠️ RECORD THE NUMBERS, not a verdict. This used to be the string "all 6
    # gains clean" or a dict of names, so the five non-default cooks were
    # discarded and the baseline diff could never see a NON-DEFAULT gain
    # regress — the exact failure this rig was added to prevent, one level up.
    value["gain_sweep"] = {"%g" % g: sweep[g] for g in gains}
    if bad:
        value["gain_sweep_failed"] = bad
    return Result(name,
                  not bad and not _rig_verdict(got, slack, floor, flat,
                                               flat_ring),
                  value,
                  "feasible turns (90, 135, both drawn as arcs, square ring) "
                  "must converge inside the clamp and NOT be flattened past "
                  "%.2f x R_min (%.2f for the closed square); infeasible ones "
                  "(fold-back, tight ring) must be flagged, not diverged, and "
                  "no worse than the input they were handed; a legal ring must "
                  "be untouched — and all of that at every turn_smooth_gain in "
                  "the shipped range, sized from the live turn_radius_scale"
                  % (flat, flat_ring))


def _rig_kappa(pts, rmin, closed):
    """Worst discrete curvature x R_min over one rig polyline."""
    n = len(pts)
    worst = 0.0
    for i in (range(n) if closed else range(1, n - 1)):
        t, l1, l2 = _turn_at(pts[(i - 1) % n], pts[i], pts[(i + 1) % n])
        if l1 < 1e-9 or l2 < 1e-9:
            continue
        worst = max(worst, t / (0.5 * (l1 + l2)) * rmin)
    return worst


def _rig_measure(geo, src_geo, city_node):
    """One cook of the control rig, read back per rig polyline."""
    got = {}
    for pr in geo.prims():
        pts = [v.point().position() for v in pr.vertices()]
        n = len(pts)
        closed = bool(pr.intrinsicValue("closed"))
        rmin = 0.5 * pr.attribValue("streetWidth") * \
            city_node.parm("graph_params_turn_radius_scale").eval()
        worst = _rig_kappa(pts, rmin, closed)
        was = [v.point().position() for v in src_geo.prims()[pr.number()].vertices()]
        moved = max((pts[i] - was[i]).length() for i in range(n))
        got[pr.attribValue("rig")] = {
            "kappa": round(worst, 4),
            # ⚠️ MEASURED off the input this cook was handed, not a constant.
            # It used to be `_RIG_INPUT_KAPPA`, a pair of numbers taken at
            # turn_radius_scale = 2; kappa x R_min is linear in the scale, so
            # the two infeasible rigs failed their own bound at every other
            # value of a slider that ships {1 8}.
            "kappa_in": round(_rig_kappa(was, rmin, closed), 4),
            "R_delivered": round(rmin / max(worst, 1e-9), 2),
            "R_min": round(rmin, 2),
            "half_width": round(0.5 * pr.attribValue("streetWidth"), 2),
            "min_seg": round(min((pts[i] - pts[(i - 1) % n]).length()
                                 for i in (range(n) if closed
                                           else range(1, n))), 4),
            "converged": int(pr.attribValue("turn_clamp_converged")),
            "sweeps": int(pr.attribValue("turn_clamp_sweeps")),
            "moved": round(moved, 6)}
    return got


def _rig_verdict(got, slack, floor, flat, flat_ring):
    """[] when every rig behaved; otherwise the rigs that did not, named."""
    want = ("bend90", "bend135", "bend135_r18", "bend90_r10", "foldback",
            "ring_legal", "ring_square", "ring_tight")
    missing = [k for k in want if k not in got]
    if missing:
        return ["missing:" + ",".join(missing)]

    def solved(r, cap):
        # ⚠️ BOUNDED ON BOTH SIDES. This used to bound R only from BELOW
        # (`R_delivered > half_width`), so OVER-smoothing was not asserted at
        # all — and over-smoothing is the literal symptom of the gain bug this
        # rig exists to catch. On the pre-median build at gain 0.5 `bend90`
        # delivered R = 57.79 m instead of 26.55 and `ring_square` 82.65 m
        # instead of 26.80, and the rig flagged neither; it caught the revert
        # only through `bend135`'s collateral `converged == 0`.
        #
        # The old lower bound is gone rather than kept alongside: R_min is
        # `half_width x turn_radius_scale`, so `kappa <= slack` already implies
        # `R_delivered > half_width` for every scale above 1.02, and at the
        # slider's minimum of 1 R_min EQUALS half_width and the old form was
        # unsatisfiable by construction. It asserted nothing anywhere it could
        # hold. `half_width` is still reported.
        return (r["converged"] == 1
                and r["kappa"] <= slack
                and r["R_delivered"] <= r["R_min"] * cap
                and r["min_seg"] >= floor)

    def flagged(r):
        # infeasible: bounded no worse than the input, intact, and REPORTED
        return (r["converged"] == 0 and r["min_seg"] >= floor
                and r["kappa"] <= r["kappa_in"] + 1e-3)

    # ⚠️ TWO CAPS, AND THE SECOND IS LOOSER BECAUSE IT IS MEASURED THAT WAY, not
    # because the tight one was inconvenient. On the current build over all six
    # gains the four open bends never leave 0.99–1.01 x R_min: between two
    # pinned endpoints there is one right answer and the solver lands on it. A
    # CLOSED ring has a family of them — "four arcs at R_min joined by straights"
    # and "a circle" both satisfy every constraint — and a tighter noise bound
    # walks toward the round end: ring_square delivers 1.00 x R_min at gain >= 2,
    # 1.12 at gain 1 and 1.49 at gain 0.5, where it burns all 200 sweeps because
    # a nearly-uniform run's LOWER median sits a hair under the vertex's own
    # turn and the noise residual never quite clears tol. That 1.49 is real and
    # is recorded in §S3b; it is not what this bound exists to catch. On the
    # pre-median build at the same gain the two read 2.16 and 3.08.
    bends = ("bend90", "bend135", "bend135_r18", "bend90_r10")
    bad = [k for k in bends if not solved(got[k], flat)]
    if not solved(got["ring_square"], flat_ring):
        bad.append("ring_square")
    bad += [k for k in ("foldback", "ring_tight") if not flagged(got[k])]
    # a ring already inside the clamp must come back BIT-IDENTICAL: the solver
    # may not touch geometry it has nothing to fix
    if not (got["ring_legal"]["converged"] == 1
            and got["ring_legal"]["sweeps"] == 0
            and got["ring_legal"]["moved"] == 0.0):
        bad.append("ring_legal")
    return bad

_RIG_SNIPPET = '''
"""The S3b control rigs, as geometry. See turn_clamp_control_rig().

⚠️ EVERY AUTHORED COORDINATE IS SCALED BY `F`, prepended by the caller as
`R_min / 26.8` — the ratio of the live turn_radius_scale to the 2 these numbers
were authored at. Without it the rig is calibrated to one slider position: at
scale 8 R_min is 107 m and bend90's 80 m legs cannot host the turn at all, so a
rig authored FEASIBLE fails its own "must converge" assertion for a reason that
is the rig's, not the solver's. The resample step stays at the pipeline's real
4 m, so a bigger R_min genuinely gets more vertices per arc.
"""
import hou, math
g = hou.pwd().geometry()
g.clear()
g.addAttrib(hou.attribType.Prim, "streetWidth", 0.0)
g.addAttrib(hou.attribType.Prim, "edge_len", 0.0)
g.addAttrib(hou.attribType.Prim, "rig", "")


def poly(name, ctrl, step=4.0):
    """Uniform 4 m resample of a control polygon, matching graph_turn_resample."""
    ctrl = [(F * p[0], F * p[1]) for p in ctrl]
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
    ctrl = [(F * p[0], F * p[1]) for p in ctrl]
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


def circle(r, step=4.0):
    """A control polygon whose chord IS the resample step, so the ring survives
    ring()'s resample as a circle rather than as a coarse n-gon with a spike at
    every original corner. n was a literal (188 for r=120, 31 for r=20); at
    R_min x 4 that literal would have left ring_legal a 188-gon sampled at 4 m,
    i.e. three straight vertices and a 0.033 rad kink, four times over.
    `r` is pre-scale — ring() applies F — so n is derived from r * F."""
    n = max(3, int(2.0 * math.pi * r * F / step + 0.5))
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
# seg is divided by F because poly() multiplies it back: the drawn arc must stay
# polygonised finer than the 4 m resample at every scale.
poly("bend135_r18", _rounded([(-200, 0), (0, 0), (-141.4, 141.4)], 18.0, 2.0 / F))
poly("bend90_r10", _rounded([(-200, 0), (0, 0), (0, 200)], 10.0, 2.0 / F))
# the one that made the first solver diverge: a 30 m square returning to within
# 4 m of its own start. R_min = 26.8 m needs 26.8 m of tangent run each side of
# a right angle and the sides are 30 m, so this is INFEASIBLE by construction
# and the only correct answer is to say so.
poly("foldback", [(0, 0), (30, 0), (30, 30), (0, 30), (0, 4)])

# --- closed prims. See turn_clamp_control_rig() for why all three are here. ---
# legal: R = 120 m is well inside the clamp, so it must come back untouched.
ring("ring_legal", circle(120.0))
# solvable: a 300 m square ring is four concentrated corners, and rounding them
# redistributes the turning without needing the ring to grow.
ring("ring_square", [(0, 0), (300, 0), (300, 300), (0, 300)])
# INFEASIBLE, and for a reason the square hides: a round ring of R = 20 m is
# over the clamp at every vertex at once, and the only way to lower kappa on a
# closed curve is to make it LONGER. Every correction here pulls toward a chord,
# which shortens. Its nodes are pinned by the graph, so nothing can fix it and
# the honest output is a flag, exactly as for the fold-back.
ring("ring_tight", circle(20.0))
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
                        min_area=1.0, tol_area=2.0, tol_edge=1.0):
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

    ⚠️ AREA WAS NOT ENOUGH, and this is the FIFTH time a check here has passed by
    measuring the wrong quantity. 2026-08-10 the artist marked lot geometry
    lying on the road at four dead-end stubs in C_radial while this check read
    **0.0 m² — correctly**. Re-rasterised at 0.5 / 0.2 / 0.1 / 0.05 / 0.01 m,
    whole-city and in 80 m windows around every degree-1 node, the answer stayed
    0.00: no lot INTERIOR is on the road. What is on the road is lot BOUNDARY.

    `pfsl_clip` (`pf_streetlots.vfl`) half-plane-clips the block with
    Sutherland-Hodgman, whose subject must be convex — and the block that wraps
    a dead-end stub is a U. S-H on a non-convex subject returns one ring that
    joins the disjoint pieces with a ZERO-WIDTH BRIDGE, and around a stub that
    bridge runs straight across the pavement. It encloses no area, so
    `pfsl_area` is exact, `lot_area` is exact, `lots_tile_blocks` passes, and
    every area test in this file — including this one — reads zero on geometry
    that ships two edges lying down the middle of an arterial. Measured on
    C_radial: **39 lots, 1290.6 m of boundary strictly inside the road surface**
    (an independent re-measurement with no raster at all -- exact point-in-
    polygon with a 0.5 m disc-clearance test -- got 40 / 1287.8, a 0.2% spread).
    (`lots_are_simple_polygons` sees the same lots from the other side and is
    already failing with 41; it says "self-touching", not "on the road".)

    So this check now measures both, and `edge_m` is the one with teeth. The
    road mask is eroded by one cell first, so a frontage edge lying ON the kerb
    — which is where every legitimate lot edge lies — cannot count.

    ⚠️ THE SLACK IS `cell`, NOT A STATED DISTANCE, so `edge_m` is not
    cell-independent: C_radial reads 1198.1 / 1290.6 / 1322.4 / 1348.0 at cell
    1.0 / 0.5 / 0.25 / 0.1. It is phase-independent (translating the city by
    0.25 m, or by 100 m, reproduces 1290.6 exactly) and it has teeth — pushing
    one B_grid lot 0.6 m into the road adds 8.7 m — but a finer run will read
    HIGHER and that is resolution, not a regression. Below cell ≈ 0.2 m the
    erosion stops covering the largest legitimate kerb-to-block deviation, the
    fillet arc-chord sagitta L²/8R ≈ 4²/(8·26.8) ≈ 0.075 m, which at cell 0.5
    has a ~6× margin.
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
    x0, z0, nx, nz, _ = grid
    road = np.zeros((nz, nx), dtype=bool)
    for g in geos:
        road |= _rasterise(np, g, grid)
    over = road & _rasterise(np, lot_geo, grid)
    blobs = _blobs(np, over, grid, min_area)
    total = round(float(over.sum()) * cell * cell, 1)

    # ...and the half with no area. One 4-neighbour erosion = `cell` metres of
    # slack, which is what keeps an edge lying along the kerb out of it.
    er = road.copy()
    er[1:, :] &= road[:-1, :]
    er[:-1, :] &= road[1:, :]
    er[:, 1:] &= road[:, :-1]
    er[:, :-1] &= road[:, 1:]
    step = cell * 0.5
    edge_m, worst_at = 0.0, None
    for pr in lot_geo.prims():
        vs = pr.vertices()
        if len(vs) < 3:
            continue
        P = np.array([(v.point().position()[0], v.point().position()[2])
                      for v in vs], dtype=np.float64)
        A = P
        B = np.roll(P, -1, axis=0)
        seg = B - A
        L = np.hypot(seg[:, 0], seg[:, 1])
        keep = L > 1e-9
        if not keep.any():
            continue
        A, B, seg, L = A[keep], B[keep], seg[keep], L[keep]
        n = np.maximum((L / step).astype(int), 1)
        for k in range(len(A)):
            t = (np.arange(1, n[k]) / float(n[k]))
            if not len(t):
                continue
            pts = A[k] + seg[k] * t[:, None]
            i = ((pts[:, 0] - x0) / cell).astype(int)
            j = ((pts[:, 1] - z0) / cell).astype(int)
            ok = (i >= 0) & (i < nx) & (j >= 0) & (j < nz)
            if not ok.any():
                continue
            hit = np.zeros(len(t), dtype=bool)
            hit[ok] = er[j[ok], i[ok]]
            if hit.any():
                edge_m += float(hit.sum()) * L[k] / n[k]
                if worst_at is None:
                    p = pts[np.flatnonzero(hit)[0]]
                    # a list, not a tuple: baseline.json round-trips through
                    # JSON and a tuple comes back a list, so every later run
                    # would report this row as "moved" for ever
                    worst_at = [round(float(p[0]), 2), round(float(p[1]), 2)]
    edge_m = round(float(edge_m), 1)
    return Result("lots_clear_of_roads",
                  bool(total <= tol_area and edge_m <= tol_edge),
                  {"m2": total, "patches": len(blobs), "edge_m": edge_m,
                   "edge_at": worst_at, "worst": blobs[:3]},
                  "lot area AND lot boundary lying on the road surface "
                  "anywhere, junction or not; the block boundary IS the kerb, "
                  "so both are 0 by construction (%g m2 / %g m allowed). "
                  "`edge_m` exists because a Sutherland-Hodgman zero-width "
                  "bridge across the pavement has no area at all"
                  % (tol_area, tol_edge))


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
