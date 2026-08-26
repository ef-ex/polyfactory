"""B2 mass checks - the assertions gate G1 is decided on.

SEPARATE MODULE ON PURPOSE.  `checks.py` / `cases.py` / `baseline.json` belong
to the streets work and are being edited on another branch; a shared baseline
regenerated from two branches silently blesses one of them
(`citygen_buildings.md` §0.0c rule 2).  Nothing here imports those.

Run by `run_building_checks.py`, which also owns the fixture, the baseline and
the mutation registry.  Every check below is paired there with the exact edit
that reddens it - a check whose mutation has not been seen red is not written
(dev-loop Rule 0; `testing` skill).

TOLERANCES.  `P` is float32 whatever the compute precision, so at the ~100 m
domain of these fixtures one ulp is already ~7.6e-6 m.  Every distance
comparison here uses 1e-3 m, which is three orders above the storage floor and
three below anything architectural.
"""

import collections
import math

TOL = 1e-3


class Result(object):
    """`ok` is a bool, or a DICT of clause name -> bool.

    The dict form exists because a four-clause check can ship three clauses
    nobody ever proved, and the runner could not see it: its sweep demanded
    one mutation per check NAME.  `party_walls_are_real`'s elevation clause
    was the live example - real teeth, no mutation of its own.  Naming the
    clauses is what lets the runner demand a mutation for each of them.
    """
    __slots__ = ("name", "ok", "value", "detail", "skipped", "clauses")

    def __init__(self, name, ok, value=None, detail="", skipped=False):
        self.name = name
        self.clauses = dict(ok) if isinstance(ok, dict) else {name: bool(ok)}
        self.ok = all(self.clauses.values())
        self.value = value
        self.detail = detail
        self.skipped = skipped

    def __repr__(self):
        state = "SKIP" if self.skipped else ("PASS" if self.ok else "FAIL")
        return "[%s] %-32s %s  %s" % (state, self.name, self.value,
                                      self.detail)


def faces(geo, site=None):
    """Every output prim as a plain record, so no check re-derives the read.

    Filtering is by SITE, never by style: the fixture deliberately builds one
    template twice, once on a lot it cannot fit on, and a style filter would
    hand the Einhof checks a fourth volume belonging to a different building.
    """
    out = []
    for prim in geo.prims():
        rec = {"prim": prim.number()}
        for name in ("pf_elem_id", "pf_volume_id", "pf_volume_role",
                     "pf_wall_role", "pf_shared_with", "pf_style_id"):
            rec[name] = prim.attribValue(name)
        for name in ("pf_site_id", "pf_volume_index", "pf_seed",
                     "pf_cap_group", "pf_warn_cap_group_split",
                     "pf_warn_footprint_collapsed", "pf_warn_unknown_rule",
                     "pf_warn_topology_arity"):
            rec[name] = prim.attribValue(name)
        rec["pf_plinth_top"] = prim.attribValue("pf_plinth_top")
        pts = [p.point().position() for p in prim.vertices()]
        rec["pts"] = [(round(p[0], 6), round(p[1], 6), round(p[2], 6))
                      for p in pts]
        rec["ymin"] = min(p[1] for p in pts)
        rec["ymax"] = max(p[1] for p in pts)
        rec["normal"] = prim.normal()
        rec["centre"] = tuple(sum(c[i] for c in pts) / float(len(pts))
                              for i in range(3))
        out.append(rec)
    if site is not None:
        out = [r for r in out if r["pf_site_id"] == site]
    return out


def volumes(geo, site=None):
    """volume id -> its faces, in one pass."""
    by = collections.OrderedDict()
    for rec in faces(geo, site):
        by.setdefault(rec["pf_volume_id"], []).append(rec)
    return by


def _plan_key(face):
    """A face's footprint in (x,z), ignoring Y.  The ONE identity, used by
    both checks that match a face to its neighbour - it was written twice,
    once here and once inside `party_walls_are_real`, which is two ways to
    disagree about what "the same wall" means.

    Two volumes of one building meet in PLAN but not in elevation: their
    skirts reach different depths because the ground under each is different,
    so the shared face is only shared over the overlapping height.  Comparing
    the full 3D face would report a continuous farmhouse as three detached
    buildings - measured, it did."""
    return tuple(sorted(set((round(p[0], 3), round(p[2], 3))
                            for p in face["pts"])))


def _area2d(pts):
    """Shoelace in (x,z), unsigned."""
    n = len(pts)
    return abs(sum(pts[i][0] * pts[(i + 1) % n][2]
                   - pts[(i + 1) % n][0] * pts[i][2]
                   for i in range(n))) * 0.5


def plan_box(fs):
    """(xmin, zmin, xmax, zmax) of a set of faces."""
    pts = [p for f in fs for p in f["pts"]]
    return (min(p[0] for p in pts), min(p[2] for p in pts),
            max(p[0] for p in pts), max(p[2] for p in pts))


def plan_areas(geo, site):
    """Each volume's CAP area in plan, ordered by `pf_volume_index`.

    ⚠️ THE QUANTITY THE FIRST BUILD RECORDED NOWHERE.  A round-2 audit cut the
    bar at half the fraction asked - `append(ts, cuts[c] * 0.5)` in shipped
    VEX - which moved the Einhof dwelling from 20 m to 10 m and the barn from
    12.5 m to 28.8 m, and all sixteen checks AND the baseline stayed green,
    because between them they recorded volumes, faces, roles, cap groups, wall
    roles and cap heights and not one plan dimension."""
    out = []
    for vfs in volumes(geo, site).values():
        cap = [f for f in vfs if f["pf_wall_role"] == "cap"]
        out.append((vfs[0]["pf_volume_index"],
                    _area2d(cap[0]["pts"]) if cap else 0.0))
    return [a for _i, a in sorted(out)]


# --- the gate criteria ------------------------------------------------------

def single_roof(geo, site, min_roles=3, name="single_roof"):
    """The Einhof claim: several FUNCTIONS, one continuous mass, ONE roof.

    Not one of these three alone is the claim - a shared cap group with a
    height step is two roofs, and equal heights with a gap between the volumes
    is two buildings.  So: one cap group, every cap at one height, and every
    volume joined to the next by a face that is geometrically THERE.

    CANNOT SEE: whether a roof could actually be built over it (that is B5),
    or whether the functions are in a sensible order along the bar.
    """
    vols = volumes(geo, site)
    if not vols:
        return Result(name, True, None, "no site %r" % site, skipped=True)
    groups = set()
    tops = set()
    roles = set()
    for fs in vols.values():
        groups.update(f["pf_cap_group"] for f in fs)
        roles.update(f["pf_volume_role"] for f in fs)
        tops.update(round(f["ymax"], 3) for f in fs if
                    f["pf_wall_role"] == "cap")
    joined = 0
    keys = dict((vid, set(_plan_key(f) for f in fs
                          if f["pf_wall_role"] == "party"))
                for vid, fs in vols.items())
    ids = list(vols)
    for a in range(len(ids) - 1):
        if keys[ids[a]] & keys[ids[a + 1]]:
            joined += 1
    # Three conjuncts, ONE claim - a chain of N joined volumes carrying N
    # functions - so they are one clause and fail together.  The two roof
    # halves are separate claims and get separate clauses, because a shared
    # cap group with a height step and a height-matched pair in two groups
    # are different defects with different causes.
    ok = {"one_cap_group": len(groups) == 1,
          "one_eave": len(tops) == 1,
          "chain_of_functions": (len(roles) >= min_roles
                                 and len(ids) >= min_roles
                                 and joined == len(ids) - 1)}
    return Result(name, ok,
                  [len(ids), sorted(roles), sorted(groups), sorted(tops),
                   joined],
                  "%d volumes, %d roles, %d cap group(s), %d eave height(s), "
                  "%d/%d joins" % (len(ids), len(roles), len(groups),
                                   len(tops), joined, len(ids) - 1))


def _loop(fs):
    """(closed, enclosed area, ordered ring) of the base edges of a set of
    wall faces, in (x,z).

    Each wall's two lowest points are one edge of the ring; the ring is closed
    when every endpoint is used exactly twice."""
    seg = []
    for f in fs:
        low = sorted(f["pts"], key=lambda p: p[1])[:2]
        a = (round(low[0][0], 3), round(low[0][2], 3))
        b = (round(low[1][0], 3), round(low[1][2], 3))
        if a != b:
            seg.append(tuple(sorted((a, b))))
    count = collections.Counter()
    for a, b in seg:
        count[a] += 1
        count[b] += 1
    if not seg or any(v != 2 for v in count.values()):
        return False, 0.0, []
    link = collections.defaultdict(list)
    for a, b in seg:
        link[a].append(b)
        link[b].append(a)
    order, cur, prev = [], seg[0][0], None
    for _ in range(len(seg)):
        order.append(cur)
        nxt = [q for q in link[cur] if q != prev]
        prev, cur = cur, nxt[0] if nxt else cur
    area = 0.0
    for i in range(len(order)):
        p, q = order[i], order[(i + 1) % len(order)]
        area += p[0] * q[1] - q[0] * p[1]
    return True, abs(area) * 0.5, order


def _inside(ring, q):
    """Signed clearance of point `q` from a closed ring in (x,z): positive
    inside, negative outside, and its magnitude is the distance to the nearest
    edge.  Crossing count for the sign, segment distance for the magnitude -
    so "strictly inside by more than a tolerance" is one comparison."""
    n = len(ring)
    inside = False
    best = 1e18
    for i in range(n):
        ax, az = ring[i]
        bx, bz = ring[(i + 1) % n]
        if (az > q[1]) != (bz > q[1]):
            xx = ax + (q[1] - az) * (bx - ax) / ((bz - az) or 1e-18)
            if q[0] < xx:
                inside = not inside
        ex, ez = bx - ax, bz - az
        l2 = ex * ex + ez * ez
        t = 0.0 if l2 < 1e-18 else max(0.0, min(
            1.0, ((q[0] - ax) * ex + (q[1] - az) * ez) / l2))
        best = min(best, math.hypot(q[0] - (ax + ex * t),
                                    q[1] - (az + ez * t)))
    return best if inside else -best


def encloses_courtyard(geo, site, depth=None, name="encloses_courtyard"):
    """The perimeter-block claim: the volumes close a RING around a void.

    A ring is not "has a wall tagged courtyard" - that is a label, and a label
    is what this project keeps being bitten by.  It is five things together:
    every volume joined to two neighbours (no free end anywhere), a closed
    courtyard loop, a closed outer loop, a positive band between them, and
    every courtyard corner STRICTLY INSIDE the outer loop by a real margin.

    And when `depth` is given, the last clause is not "inside" but a
    DIFFERENTIAL ORACLE against the template: every courtyard corner stands
    `courtyardDepthM` from the outer wall, so the built tract depth is
    re-derived from the data file rather than compared with itself.

    ⚠️ MEASURED AT EDGE MIDPOINTS, NOT AT CORNERS, and that is a fix not a
    detail.  `_inside` returns the clearance to the NEAREST outer edge, and at
    a corner that is `min(d_prev, d_next)` - so ONE correct neighbour per
    corner was enough to pass.  A round-2 audit scaled one pair of opposite
    edges 1.6x and built a 518.4 m2 courtyard where 864 m2 was asked for; this
    check reported "12.00-12.00 m against 12.00 asked for".  An edge's
    midpoint is nearest to that edge's own outer partner, so each edge is now
    measured on its own account and the non-uniform ring reads 12 and 19.2.
    ⚠️ Still a nearest-edge measure, not an index-matched one: a courtyard
    edge that ends up nearer some OTHER outer edge than its own partner is
    measured against the wrong one.  `pf_inset` preserves index
    correspondence, so the index-matched version is available if a footprint
    ever bends far enough to need it.

    ⚠️ This took three tries and each failure is worth keeping.  Version one
    measured the courtyard's AREA, so setting the depth to 0 made the whole
    2 728 m2 footprint read as a courtyard.  Version two added the band, which
    closed that case and not the general one: an audit slid the whole
    courtyard 4 m sideways, wrecking the wings underneath, and both areas came
    back BYTE-IDENTICAL - a rigid translation preserves every area there is.
    Version three added containment, and the shifted block was STILL 8 m
    inside its outer wall, so it passed a check that could now see the defect
    and had no reason to object to it.  Only measuring the depth against the
    number that asked for it fails: 8 m and 16 m where 12 was specified.

    CANNOT SEE: a figure-of-eight, which also has no free end; whether the
    courtyard is habitable, daylit or legal; nor a courtyard correct in plan
    and wrong in elevation.
    """
    vols = volumes(geo, site)
    if not vols:
        return Result(name, True, None, "no site %r" % site, skipped=True)
    ends = sum(1 for fs in vols.values() for f in fs
               if f["pf_wall_role"] == "end")
    yard = [f for fs in vols.values() for f in fs
            if f["pf_wall_role"] == "courtyard"]
    outer = [f for fs in vols.values() for f in fs
             if f["pf_wall_role"] == "exterior"]
    closed, area, ring = _loop(yard)
    out_closed, out_area, out_ring = _loop(outer)
    band = out_area - area
    mid = [((ring[i][0] + ring[(i + 1) % len(ring)][0]) * 0.5,
            (ring[i][1] + ring[(i + 1) % len(ring)][1]) * 0.5)
           for i in range(len(ring))]
    gaps = ([_inside(out_ring, q) for q in mid]
            if closed and out_closed else [-1.0])
    lo, hi = min(gaps), max(gaps)
    ok = {"closed_ring": (ends == 0 and closed and out_closed
                          and len(vols) >= 3 and area > TOL and band > TOL),
          "tract_depth": (lo > TOL
                          and (depth is None or (abs(lo - depth) <= 0.01
                                                 and abs(hi - depth) <= 0.01)))}
    return Result(name, ok, [len(vols), ends, len(yard), round(area, 2),
                             round(band, 2), round(lo, 2), round(hi, 2)],
                  "%d volumes, %d free ends, %d courtyard faces, courtyard "
                  "%.1f m2 inside a %.1f m2 band; tract depth %.2f-%.2f m "
                  "against %s asked for"
                  % (len(vols), ends, len(yard), area, band, lo, hi,
                     "%.2f" % depth if depth is not None else "nothing"))


def elements(geo, site=None):
    """B4/B5/B6's OUTPUT as plain records - packed facade modules and roof
    faces in one vocabulary, so no G2 check re-derives the read.

    ⚠️ A PACKED PRIM HAS ONE VERTEX (houdini-procedural-modeling §6).  Every
    extent below therefore comes from the `bounds` INTRINSIC and never from
    `prim.vertices()`: reading vertices would give ONE point per module and
    turn every plan measurement into a point sample of a 3 m wall.  `pts` is
    filled only for the roof, which is real polygons.

    ⚠️ THE BOX IS AXIS-ALIGNED, and on a rectilinear footprint that is exact -
    every wall runs along X or Z, so a module's box is the module.  On a
    SLANTED wall it would over-report coverage by up to the box's slack, and
    `corner_closure` would then be measuring a bound rather than the facade.
    Stated because G2's fixture is rectilinear and a later non-rectilinear one
    would silently weaken the check rather than fail it.
    """
    out = []
    have = dict((a.name(), True) for a in geo.primAttribs())
    for prim in geo.prims():
        b = prim.intrinsicValue("bounds")
        rec = {"prim": prim.number(),
               "box": (b[0], b[4], b[1], b[5]),      # xmin, zmin, xmax, zmax
               "ymin": b[2], "ymax": b[3]}
        for key, default in (("pf_site_id", -1), ("pf_volume_id", ""),
                             ("pf_wall_role", ""), ("pf_elem_id", ""),
                             ("pc_row", -1), ("pc_cell", "")):
            rec[key] = (prim.attribValue(key) if key in have else default)
        rec["kind"] = "roof" if rec["pf_wall_role"] == "roof" else "facade"
        rec["pts"] = ([(round(p.point().position()[0], 6),
                        round(p.point().position()[1], 6),
                        round(p.point().position()[2], 6))
                       for p in prim.vertices()]
                      if rec["kind"] == "roof" else [])
        out.append(rec)
    if site is not None:
        out = [r for r in out if r["pf_site_id"] == site]
    return out


def _cap_ring(fs):
    """A volume's footprint in (x, z), off its own cap face - which IS the
    plan `pfb_cell` built the volume from."""
    cap = [f for f in fs if f["pf_wall_role"] == "cap"]
    return [(p[0], p[2]) for p in cap[0]["pts"]] if cap else []


def _in_box(box, q, grow=0.0):
    return (box[0] - grow <= q[0] <= box[2] + grow
            and box[1] - grow <= q[1] <= box[3] + grow)


def corner_closure(geo, mass, name="corner_closure", step=0.05):
    """⭐ THE GATE'S OWN QUESTION: does the facade close at a corner?

    §5 Theme 4 is unusually concrete - the one failure where independent
    artists name the same node and the same parameter - and its first
    complaint is *corner HOLES*.  So this walks each building's footprint
    perimeter at 5 cm and asks, for EVERY STOREY ROW SEPARATELY, whether some
    facade module is standing there.  A gap that exists on one row only is
    still a hole, and a plan-only test would let the row below cover for it.

    ⚠️ THE PERIMETER IS B4's OWN INPUT, NOT AN ORACLE OF THE FOOTPRINT.  It
    is the mass's cap ring - the polygon `pf_facade_in.vfl` handed the facade
    - so this measures B4 against what B4 was given and CANNOT be confused by
    a wrong footprint upstream.  `plan_follows_data` is what says the footprint
    itself is the one the data asked for; running the two together is the
    claim, and neither alone is.

    `corner_module` is §12.6 B6's PRIMARY strategy stated as an assertion:
    in `miter` the corner is filled by a module from the kit, so every corner
    point must lie inside some `corner*` cell's box.  Its discriminating
    mutation is the cascade silently falling back to `bend`, which places no
    corner module at all (polyChain D37) and yet leaves NO GAP - so the two
    clauses separate the two treatments exactly.

    CANNOT SEE: a gap narrower than `step`; a module present but at the wrong
    DEPTH (see `elements`' axis-aligned note - and on this pipeline the Labs
    "different ledges shift to different depths" failure cannot arise anyway,
    because both legs of a corner belong to ONE array with ONE row solve);
    anything about the module's own geometry inside its box; and any face of
    the building that is not on the perimeter.
    """
    gaps, missing, worst, sampled = [], [], 0.0, 0
    for vid, fs in volumes(mass).items():
        ring = _cap_ring(fs)
        el = [e for e in elements(geo)
              if e["pf_volume_id"] == vid and e["kind"] == "facade"]
        if not ring or not el:
            gaps.append((vid, "nothing built"))
            continue
        n = len(ring)
        for row in sorted(set(e["pc_row"] for e in el)):
            boxes = [e["box"] for e in el if e["pc_row"] == row]
            run, run_at = 0.0, None
            for j in range(n):
                a, b = ring[j], ring[(j + 1) % n]
                length = math.hypot(b[0] - a[0], b[1] - a[1])
                for k in range(int(length / step) + 1):
                    t = min(1.0, k * step / (length or 1.0))
                    q = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                    sampled += 1
                    if any(_in_box(box, q, TOL) for box in boxes):
                        run = 0.0
                        continue
                    run += step
                    run_at = run_at or (j, round(q[0], 2), round(q[1], 2))
                    if run > worst:
                        worst = run
            if run_at:
                gaps.append((vid, row, run_at, round(worst, 3)))
        corner_boxes = [e["box"] for e in el
                        if str(e["pc_cell"]).startswith("corner")]
        for j, q in enumerate(ring):
            if not any(_in_box(box, q, TOL) for box in corner_boxes):
                missing.append((vid, j, round(q[0], 2), round(q[1], 2)))
    ok = {"no_gaps": sampled > 0 and not gaps,
          "corner_module": sampled > 0 and not missing}
    return Result(name, ok, [sampled, len(gaps), round(worst, 3),
                             len(missing)],
                  "%d perimeter samples over every row; uncovered runs %s "
                  "(worst %.3f m); corners with no corner module: %s"
                  % (sampled, gaps[:3] or "none", worst,
                     missing[:4] or "none"))


def _plane_y(face, q):
    """The y of a planar roof face at plan point `q`, or None if `q` is
    outside it in plan.  Three non-collinear points give the plane; a straight
    -skeleton face is planar by construction (constant pitch off one edge)."""
    ring = [(p[0], p[2]) for p in face["pts"]]
    if len(ring) < 3 or _inside(ring, q) < -TOL:
        return None
    o = face["pts"][0]
    for i in range(1, len(face["pts"]) - 1):
        u = tuple(face["pts"][i][k] - o[k] for k in range(3))
        v = tuple(face["pts"][i + 1][k] - o[k] for k in range(3))
        nx = u[1] * v[2] - u[2] * v[1]
        ny = u[2] * v[0] - u[0] * v[2]
        nz = u[0] * v[1] - u[1] * v[0]
        if abs(ny) > 1e-9:
            return o[1] - (nx * (q[0] - o[0]) + nz * (q[1] - o[2])) / ny
    return None


def cap_seam(geo, mass, name="cap_seam"):
    """⭐ THE OTHER SEAM G2's pass criterion names: facade -> cap.

    Three clauses, and the split between them is the point.  `pf_seam.vfl`
    takes the roof's datum from the facade that was BUILT, which is what makes
    the seam gapless - and it is exactly why a check that measured the roof
    against the built facade alone would move with the defect and pass:

      `eave_meets_wall`   the roof SURFACE passes through the wall's top edge.
                          Sampled at every footprint corner and edge midpoint,
                          so the VALLEY over the reflex corner is measured on
                          its own account and not averaged away.
      `height_as_asked`   the built facade top is `pf_plinth_top + storeys x
                          storeyHeight` - B2's number, and through it the
                          template's.  THIS is the clause that pins the seam
                          to the data instead of to itself.
      `roof_closed`       the roof surface's only boundary is its eave: one
                          boundary edge per footprint edge and every one of
                          them at the surface's lowest y.  A skeleton that
                          cracked at the reflex corner, or that was truncated
                          because the offset did not exceed the inradius,
                          leaves boundary edges that are neither.

    CANNOT SEE: a roof correct at the sampled points and wrong between them
    (it samples corners and midpoints, not the whole surface); a roof that is
    closed and inside out; gables, which this cap family does not build; and
    whether the eave OVERHANG is the depth the template asked for - only that
    the surface meets the wall.
    """
    high, floats, cracked, seen = [], [], [], 0
    for vid, fs in volumes(mass).items():
        ring = _cap_ring(fs)
        asked = max(f["ymax"] for f in fs if f["pf_wall_role"] == "cap")
        el = elements(geo)
        fac = [e for e in el if e["pf_volume_id"] == vid
               and e["kind"] == "facade"]
        roof = [e for e in el if e["pf_volume_id"] == vid
                and e["kind"] == "roof"]
        if not ring or not fac or not roof:
            cracked.append((vid, "facade %d roof %d" % (len(fac), len(roof))))
            continue
        seen += 1
        built = max(e["ymax"] for e in fac)
        if abs(built - asked) > TOL:
            high.append((vid, round(built, 4), round(asked, 4)))
        probes = list(ring) + [((ring[j][0] + ring[(j + 1) % len(ring)][0])
                                * 0.5,
                                (ring[j][1] + ring[(j + 1) % len(ring)][1])
                                * 0.5) for j in range(len(ring))]
        for q in probes:
            ys = [y for y in (_plane_y(f, q) for f in roof) if y is not None]
            if not ys or min(abs(y - built) for y in ys) > TOL:
                floats.append((vid, (round(q[0], 2), round(q[1], 2)),
                               [round(y, 3) for y in ys[:2]],
                               round(built, 3)))
        # ⚠️ A ZERO-LENGTH EDGE IS NOT AN EDGE, and skipping it is accounting
        # rather than leniency.  MEASURED on 22.0.398: `polyexpand2d`'s
        # surface output REPEATS a vertex wherever the wavefront collapses -
        # 29 such self-edges over this fixture's 10 roof faces - and folding
        # them into the multiset made every apex look like one edge shared by
        # nine faces AND put a spurious (p, p) pair in the boundary set.  The
        # first reading of this clause was "7 boundary edges for 6 footprint
        # edges" on a roof that is closed; the seventh was the apex touching
        # itself.  The repeated vertices are a stated limit of the B5
        # prototype (§12.10b), not a hole.
        edges = collections.Counter()
        for f in roof:
            pts = f["pts"]
            for j in range(len(pts)):
                a, b = pts[j], pts[(j + 1) % len(pts)]
                if a != b:
                    edges[tuple(sorted((a, b)))] += 1
        border = [e for e, c in edges.items() if c == 1]
        low = min(p[1] for f in roof for p in f["pts"])
        if (len(border) != len(ring)
                or any(abs(p[1] - low) > TOL for e in border for p in e)):
            cracked.append((vid, "%d boundary edges for %d footprint edges"
                            % (len(border), len(ring))))
    ok = {"eave_meets_wall": seen > 0 and not floats,
          "height_as_asked": seen > 0 and not high,
          "roof_closed": seen > 0 and not cracked}
    return Result(name, ok, [seen, len(floats), len(high), len(cracked)],
                  "%d buildings; roof off the wall top at: %s; built top vs "
                  "asked: %s; roof boundary: %s"
                  % (seen, floats[:2] or "nowhere", high[:2] or "ok",
                     cracked[:2] or "eave only"))


def plan_follows_data(geo, styles, rings, roles, templates, degraded=(),
                      authored=None, name="plan_follows_data"):
    """WHERE THE MASS IS AND HOW BIG IT IS IN PLAN - the dimension nothing in
    the first build could see, and the one G2's L-footprint is made of.

    Two DIFFERENTIAL ORACLES, both computed here from the fixture's own lot
    RING and the template's numbers, never from the geometry:
      * `footprint` - every lot EDGE is inset by its own role's setback, so
        the built mass's closest approach to edge j must be exactly `s[j]`.
        `pf_inset.vfl` solving corners is not consulted; the expected distance
        is one number per edge.
      * `cell_split` - under `bar` the cells' plan AREAS must be in the ratio
        of the `cutsAt` intervals. Compared in `pf_volume_index` order, or its
        reverse, because the rail direction follows the longer edge.

    ⭐ `footprint` WAS A BOUNDING-BOX COMPARISON UNTIL G2 AND THAT MADE IT
    VACUOUS ON THE ONLY SHAPE G2 CARES ABOUT.  Round 4 measured it: on an L
    lot the built mass's plan box IS the lot's plan box, so on a `setback(0)`
    L the clause asserted nothing at all, and on any L it could see only the
    two extremes of six edges.  The per-edge form is the generalisation: for
    a RECTANGLE it is arithmetically the same four numbers the box compared,
    and for an L it measures all six - including the two that meet at the
    reflex corner, which is the pair `pf_inset` has to solve and nothing had
    ever checked.  ⚠️ The closest approach is measured only over the points
    that project INSIDE the edge's own segment, which is what makes it work on
    a non-convex ring: the far leg of an L is nearest to an edge it does not
    face, and including it would report that leg's distance instead.

    ⚠️ IT MODELS THE WHOLE CASCADE, NOT JUST THE TEMPLATE, and the first
    version did not: `s` came only from `lotToFootprint.setbackM`, so an
    authored per-vertex `pf_setback` - cascade level 5, which WINS - was
    invisible to the oracle and CORRECT GEOMETRY FAILED.  Measured: a 40 x 20
    lot with 2.0 m authored all round builds correctly at 2..38 x 2..18 and
    was reported as `[2.0, 2.0, 38.0, 18.0]` against `[0, 0, 40, 20]`.  It was
    masked only because the one authored fixture site was degraded and
    skipped - "a fixture property was load-bearing without saying so", which
    is round-1 defect 3's shape.  `authored` is {site: [per-edge value]} with
    NEGATIVE meaning absent, the same sentinel `stamp()` reads, taken from the
    FIXTURE and never from the geometry.

    ⚠️ PAIR THIS ONLY WITH VEX MUTATIONS.  It reads the template, so a
    template-side mutation moves the oracle and the geometry together and both
    "pass" - auditor #2's first drafts of these oracles did exactly that.

    CANNOT SEE: a degraded site (skipped - its footprint is by definition not
    the one the data asked for); anything about elevation; two cells of equal
    area swapped; a footprint that is right at every edge and wrong BETWEEN
    them (a bulge in the middle of an edge is nearer, so it IS caught; a
    notch cut out of one is not); nor whether the corner where two edges meet
    was solved by the right rule - only that both edges arrived where the data
    put them.
    """
    bad = []
    seen, split_seen = 0, 0
    for site in sorted(rings):
        if site in degraded:
            continue
        seen += 1
        ring, edge_roles = rings[site], roles[site]
        tpl = templates[styles[site]]
        fp = tpl["lotToFootprint"]
        table = fp["setbackM"] if fp["op"] != "identity" else {}
        over = (authored or {}).get(site) or []
        s = [over[i] if i < len(over) and over[i] >= 0.0
             else float(table.get(r, 0.0 if fp["op"] == "identity"
                                  else fp["defaultSetbackM"]))
             for i, r in enumerate(edge_roles)]
        pts = [(p[0], p[2]) for f in faces(geo, site) for p in f["pts"]]
        got = []
        for j in range(len(ring)):
            a, b = ring[j], ring[(j + 1) % len(ring)]
            ex, ez = b[0] - a[0], b[1] - a[1]
            l2 = ex * ex + ez * ez
            # interior is to the LEFT of a CCW edge, so the inward normal is
            # the edge turned +90 degrees in (x, z) - the same convention
            # `pf_inset.vfl` takes off the signed area.
            nx, nz = -ez / math.sqrt(l2), ex / math.sqrt(l2)
            near = [(q[0] - a[0]) * nx + (q[1] - a[1]) * nz for q in pts
                    if 0.0 <= ((q[0] - a[0]) * ex
                               + (q[1] - a[1]) * ez) / l2 <= 1.0]
            got.append(round(min(near), 4) if near else None)
        if any(g is None or abs(g - w) > TOL for g, w in zip(got, s)):
            bad.append((site, "footprint", got, [round(v, 2) for v in s]))
        topo = tpl["volumeTopology"]
        if topo["rails"] != "bar" or not topo["cutsAt"]:
            continue
        split_seen += 1
        edge = [0.0] + sorted(float(c) for c in topo["cutsAt"]) + [1.0]
        wants = [round(edge[i + 1] - edge[i], 4)
                 for i in range(len(edge) - 1)]
        area = plan_areas(geo, site)
        total = sum(area) or 1.0
        gots = [round(a / total, 4) for a in area]
        if (len(gots) != len(wants)
                or (max(abs(a - b) for a, b in zip(gots, wants)) > 1e-3
                    and max(abs(a - b)
                            for a, b in zip(gots, wants[::-1])) > 1e-3)):
            bad.append((site, "cell_split", gots, wants))
    # ⚠️ `cell_split` IS ONLY REPORTED WHEN SOMETHING REACHED IT.  A clause
    # that no site exercises would otherwise ship PASS forever and, worse,
    # would be demanded by the runner's per-clause mutation sweep on a fixture
    # that cannot produce one - G2's every template is `solid`, so the clause
    # is not applicable there rather than satisfied there.  "Assert truth, not
    # presence" (dev-loop §9 rule 3) applies to a clause's own existence.
    ok = {"footprint": seen > 0 and not [b for b in bad if b[1] ==
                                         "footprint"]}
    if split_seen:
        ok["cell_split"] = not [b for b in bad if b[1] == "cell_split"]
    return Result(name, ok,
                  len(bad), "plan against the data: %s" % (bad[:2] or "ok"))


def rules_serve_more_than_one_style(templates, name="rule_reuse"):
    """G1's adversarial clause, mechanised.

    "A rule library where one rule is only ever used by one template is really
    that template's code in disguise."  So: every value the assembly rules can
    take must be reached by at least two DIFFERENT styleIds among the shipped
    templates, or this reports the rule that is a style in disguise.

    ⚠️ THIS CHECK IS WEAKER THAN IT READS, and an audit was right to say so.
    Of its four rows only TWO are independent: `lotToFootprint` is `setback`
    in every shipped template and so can never be lonely, and `cuts` is
    perfectly collinear with `rails` (`cutsAt` is non-empty exactly when the
    rails are a bar).  What actually carries the G1 argument is the 2x2
    CROSSING in the fixture - bar/ring against levelToHighest/none, with a
    farm and an urban block in each column - not this count.

    CANNOT SEE: a rule that two templates use for cosmetically different but
    architecturally identical buildings.  Reuse is necessary, not sufficient;
    the viewport pass is the other half.
    """
    used = collections.defaultdict(set)
    for tpl in templates:
        sid = tpl["styleId"]
        topo = tpl["volumeTopology"]
        used["rails:" + str(topo["rails"])].add(sid)
        used["plinth:" + str(topo["plinth"]["mode"])].add(sid)
        used["lotToFootprint:" + str(tpl["lotToFootprint"]["op"])].add(sid)
        used["cuts:" + ("fractions" if topo["cutsAt"] else "corners")].add(sid)
    lonely = sorted(k for k, v in used.items() if len(v) < 2)
    return Result(name, not lonely,
                  dict((k, sorted(v)) for k, v in sorted(used.items())),
                  "rules used by only one style: %s" % (lonely or "none"))


def no_style_names_in_code(sources, style_ids, name="no_style_branching"):
    """G1's PASS criterion as an assertion: `if style == "einhof"` anywhere is
    an automatic fail, so no production source may contain a style id at all.

    CANNOT SEE: a branch on something that CORRELATES with one style - a test
    on `courtyardDepthM > 0` would pass this and be a style branch in fact.
    That one is answered by `rule_reuse` above, not here.
    """
    hits = []
    for path, text in sources.items():
        for sid in style_ids:
            if sid in text:
                hits.append("%s:%s" % (path, sid))
    return Result(name, not hits, len(hits),
                  "style ids found in production source: %s" % (hits or "none"))


# --- the correctness the gate rests on --------------------------------------

def party_walls_are_real(geo, name="party_walls_real"):
    """Every face tagged party names a neighbour, and the neighbour has a face
    in the SAME PLACE.  The union, not the parts: each volume alone can be
    perfectly tagged while the two never touch.

    Matched in PLAN and then in ELEVATION, separately.  Plan alone was all
    this had, and an audit was right to call that out: two volumes whose
    skirts reach different depths cannot be compared as identical 3D
    polygons, but they must still SHARE HEIGHT - a party wall whose neighbour
    sits entirely above or below it is a party wall to nothing.  So the
    elevation half asserts the two faces' Y ranges overlap by more than a
    tolerance, which is the weakest true statement about them.

    CANNOT SEE: how MUCH of the face is genuinely shared. An unequal-height
    pair (Vorderhaus vs Hoftrakt) is tagged party over its whole area
    including the part standing proud above the shorter neighbour; splitting
    that is B6's.
    """
    vols = volumes(geo)
    party = [(vid, f) for vid, fs in vols.items() for f in fs
             if f["pf_wall_role"] == "party"]
    named = sum(1 for _v, f in party if f["pf_shared_with"])
    plan = {}
    for vid, fs in vols.items():
        for f in fs:
            if f["pf_wall_role"] == "party":
                plan.setdefault((vid, _plan_key(f)), []).append(f)
    matched = overlapped = 0
    for vid, f in party:
        peers = plan.get((f["pf_shared_with"], _plan_key(f)))
        if not peers:
            continue
        matched += 1
        if any(min(f["ymax"], p["ymax"]) - max(f["ymin"], p["ymin"]) > TOL
               for p in peers):
            overlapped += 1
    ok = {"named": bool(party) and named == len(party),
          "plan_match": bool(party) and matched == len(party),
          "elevation_overlap": bool(party) and overlapped == len(party)}
    return Result(name, ok, [len(party), named, matched, overlapped],
                  "%d party faces, %d name a neighbour, %d meet it in plan, "
                  "%d share height with it"
                  % (len(party), named, matched, overlapped))


def _wanted(tpl, corners):
    """How many volumes a template asks for ON THIS FOOTPRINT.

    Under `ring` the cell count is the FOOTPRINT's edge count and `volumes` is
    indexed cyclically, so a SHORTER list is legal - that is exactly what
    `pf_warn_topology_arity` exists to say - and comparing against its length
    would fail correct geometry.  Latent rather than live today: every fixture
    lot is a 4-gon and every ring template happens to list four volumes."""
    vols = len(tpl["volumeTopology"]["volumes"])
    return corners if tpl["volumeTopology"]["rails"] == "ring" else vols


def volume_count_matches_template(geo, templates, sites, degraded_sites=(),
                                  name="volume_count_matches"):
    """Every volume the template asks for is actually IN THE OUTPUT, and only
    the sites the FIXTURE says are impossible are allowed to degrade.

    `sites` is {site: (styleId, corner count of the lot)}.

    ⚠️ A cell can vanish without a sound: `pfb_cell` refuses a non-positive
    height and returns, and nothing downstream counts.  An audit measured 7
    volumes built where 13 were expected and every other check stayed green,
    because all of them reason about the volumes that exist.  This is the one
    that reasons about the ones that do not.

    ⚠️ `degraded_sites` is passed IN rather than read off the warning, and
    that too is measured: the first version trusted the warning, so when a
    tightened collapse test wrongly flagged every `setback(0)` footprint, two
    perimeter blocks quietly became one solid mass each and this check called
    it correct degradation.  A check that takes the code's word for what was
    supposed to happen cannot catch the code being wrong about it.

    ⚠️ AND A DEGRADED SITE MUST SAY SO.  §2.2 is "advisory, never a wall", and
    the advice is the whole of it - a degradation nobody is told about is just
    a wrong building.  Measured: a five-corner lot under a bar template whose
    `volumes` list has length 1 shipped one volume with ALL FOUR `pf_warn_*`
    at 0, and this check reported PASS because `_wanted` was 1 and 1 was
    built.  Fixture site 7 was visible only because `len(roles) != ncells`
    happens to hold there, which is a property of the template it was given.
    So every degraded site must carry `pf_warn_topology_arity`: it never
    honoured its volume list, and §12.8 already defines that warning as the
    list not matching the cells the rails produced.

    CANNOT SEE: a volume that is present and in the wrong place; nor WHY a
    site degraded, beyond whether the offset was what folded.
    """
    bad = []
    for site, (style, corners) in sorted(sites.items()):
        fs = faces(geo, site)
        if not fs:
            bad.append((site, 0, "nothing built"))
            continue
        got = len(set(f["pf_volume_id"] for f in fs))
        warned = any(f["pf_warn_footprint_collapsed"] for f in fs)
        if site in degraded_sites:
            # ⚠️ `degraded_sites` maps site -> whether the OFFSET is what went
            # wrong there, and BOTH directions are asserted. §12.8 defines
            # `pf_warn_footprint_collapsed` as "offset degenerate", so a site
            # that degrades for a topology reason must NOT carry it - nothing
            # else in the suite can see a warning that fires too often, and
            # this one did, on a footprint that was provably the identity.
            arity = all(f["pf_warn_topology_arity"] for f in fs)
            if (got != 1 or bool(warned) != bool(degraded_sites[site])
                    or not arity):
                bad.append((site, got, "expected 1 volume, collapse warning "
                            "%s, arity warning True; got warnings %s/%s"
                            % (bool(degraded_sites[site]), bool(warned),
                               arity)))
        elif got != _wanted(templates[style], corners):
            bad.append((site, got, _wanted(templates[style], corners)))
        elif warned:
            bad.append((site, got, "degraded when it should not have"))
    return Result(name, not bad, len(bad),
                  "sites whose volume count is not what the template asked "
                  "for: %s" % (bad[:4] or "none"))


def outward_normals(geo, name="outward_normals"):
    """Caps up, floors down, walls away from their own volume.  A reversed
    quad renders and measures identically and shades as a backface.

    CANNOT SEE: a wall correct in orientation but at the wrong place.
    """
    bad = []
    for vid, fs in volumes(geo).items():
        pts = [p for f in fs for p in f["pts"]]
        cx = sum(p[0] for p in pts) / float(len(pts))
        cz = sum(p[2] for p in pts) / float(len(pts))
        cy = sum(p[1] for p in pts) / float(len(pts))
        for f in fs:
            n, c = f["normal"], f["centre"]
            if f["pf_wall_role"] == "cap":
                good = n[1] > 0.9
            elif f["pf_wall_role"] == "floor":
                good = n[1] < -0.9
            else:
                out = (c[0] - cx, c[1] - cy, c[2] - cz)
                good = (n[0] * out[0] + n[1] * out[1] + n[2] * out[2]) > 0.0
            if not good:
                bad.append(f["pf_elem_id"])
    return Result(name, not bad, len(bad),
                  "faces pointing the wrong way: %s" % (bad[:4] or "none"))


def heights_follow_data(geo, templates, name="heights_follow_data"):
    """A DIFFERENTIAL ORACLE, not a snapshot: every volume's wall height is
    re-derived from the TEMPLATE FILE - `volumes[i].storeys` times that
    volume's own storey height - and compared with the built geometry.  A
    snapshot of the geometry against itself would pass whatever the data said.

    `templates` is {styleId: resolved template}.  CANNOT SEE: a storey height
    that is wrong in the template file itself; the viewport pass answers that.
    """
    bad = []
    seen = 0
    for vid, fs in volumes(geo).items():
        tpl = templates.get(fs[0]["pf_style_id"])
        if tpl is None:
            continue
        spec = tpl["volumeTopology"]["volumes"]
        vol = spec[fs[0]["pf_volume_index"] % len(spec)]
        cap = [f for f in fs if f["pf_wall_role"] == "cap"]
        if not cap:
            bad.append((vid, "no cap"))
            continue
        seen += 1
        want = (int(vol.get("storeys", 1))
                * float(vol.get("storeyHeightM", tpl["storeyHeightM"])))
        got = cap[0]["ymax"] - fs[0]["pf_plinth_top"]
        if abs(got - want) > TOL:
            bad.append((vid, round(got, 4), round(want, 4)))
    return Result(name, not bad and seen > 0, [seen, len(bad)],
                  "%d volumes measured against their template; wrong: %s"
                  % (seen, bad[:3] or "none"))


def plinth_follows_ground(geo, site, minm=None, ground=None,
                          name="plinth_follows_ground"):
    """`levelToHighest` on a slope: ONE floor datum for the whole building,
    and a skirt under every volume that reaches the ground it stands on - so
    the datums are identical and the SKIRT DEPTHS are not.  Both halves are
    asserted: one level alone is a building floating on a slab, varying depths
    alone is a stepped building, and neither is a plinth.

    With the rule off, datum and base are both 0 everywhere, so the varying
    depth is what goes red.

    ⚠️ AND `plinth.minM` IS MEASURED, because it was not: an audit set it to
    0.0 and to 25.0 - buildings sunk twenty-five metres - and both left every
    check green and the baseline unmoved.  The identity that pins it: the
    floor datum is the HIGHEST ground under the building and each cell's
    skirt reaches its OWN lowest corner minus `minM`, so the DEEPEST skirt is
    exactly `(ground span over the base corners) + minM`.  `ground(x, z)` is
    the fixture's slope in closed form, evaluated here, so the expected value
    never passes through the code being judged.
    ⚠️ Tolerance 0.05 m, not TOL: `ground` is the analytic surface while the
    wrangle raycasts it SAMPLED on a 2 m grid, and the chord of that sampling
    is ~5 mm at this curvature.  The number under test is 0.4 m.

    CANNOT SEE: whether the datum is the true maximum of the ground over the
    cells' whole AREA - it samples the plan CORNERS only, so a hump between
    two corners is missed (polyChain's stepped-base finding, same shape).
    """
    vols = volumes(geo, site)
    if not vols:
        return Result(name, True, None, "no site %r" % site, skipped=True)
    datums, depths = set(), set()
    for vid, fs in vols.items():
        walls = [f for f in fs if f["pf_wall_role"] not in ("cap", "floor")]
        if not walls:
            continue
        datum = fs[0]["pf_plinth_top"]
        datums.add(round(datum, 3))
        depths.add(round(datum - min(w["ymin"] for w in walls), 3))
    base = [(p[0], p[2]) for fs in vols.values() for f in fs
            if f["pf_wall_role"] == "floor" for p in f["pts"]]
    span = ([ground(x, z) for x, z in base] if ground and base else [0.0])
    want = max(span) - min(span) + (minm or 0.0)
    ok = {"one_datum": len(datums) == 1 and len(vols) > 1,
          "varying_skirts": (len(depths) > 1 and min(depths) > TOL),
          "plinth_depth": (minm is None or ground is None
                           or abs(max(depths) - want) <= 0.05)}
    return Result(name, ok, [sorted(datums), sorted(depths), round(want, 3)],
                  "%d floor datum(s) over %d volumes, %d distinct skirt "
                  "depths %s; deepest %.3f against %.3f = ground span + minM"
                  % (len(datums), len(vols), len(depths), sorted(depths),
                     max(depths), want))


# --- contract and law -------------------------------------------------------

STORAGE = {"pf_elem_id": "String", "pf_volume_id": "String",
           "pf_volume_role": "String", "pf_wall_role": "String",
           "pf_face_role": "String", "pf_shared_with": "String",
           "pf_style_id": "String", "pf_site_id": "Int",
           "pf_volume_index": "Int", "pf_storeys": "Int",
           "pf_cap_group": "Int", "pf_plinth_top": "Float",
           "pf_storey_height": "Float", "pf_seed": "Int",
           "pf_warn_cap_group_split": "Int", "pf_warn_topology_arity": "Int",
           "pf_warn_footprint_collapsed": "Int", "pf_warn_unknown_rule": "Int"}


def attribute_storage(geo, name="attribute_storage"):
    """D223: an attribute's STORAGE is part of its contract.  An int id once
    shipped a different fence AND a different curve order with no coverage, so
    every id B2 mints is enrolled here from day one.  ⚠️ "Every" was a claim
    and not a fact until round 2: `pf_seed` and all four `pf_warn_*` were
    missing from the table under a docstring that said they were in it.

    ⚠️ BOTH DIRECTIONS.  The table said what must ship; nothing said what must
    NOT.  Measured: adding `pf_undeclared` to every face left this check
    green ("all 18 ok"), `no_scratch` green and all 28 clauses green - only
    the baseline's `published/prim` row moved.  That row does fail the run, so
    the gap was never silent; the risk is `--update-baseline` blessing a new
    published name unread, and this build regenerated the baseline in the same
    pass that added attributes.  A published `pf_*` prim attribute that is in
    neither this table nor the table's reason for existing is now a failure
    here, where a human has to add a row for it deliberately.

    CANNOT SEE: an attribute of the right storage carrying a wrong value; nor
    an undeclared name on the point, vertex or detail classes, where B2
    publishes nothing and the baseline is the only guard.
    """
    have = dict((a.name(), str(a.dataType()).split(".")[-1])
                for a in geo.primAttribs())
    wrong = sorted(["%s=%s want %s" % (k, have.get(k, "MISSING"), v)
                    for k, v in STORAGE.items() if have.get(k) != v]
                   + ["%s=%s UNDECLARED" % (k, v) for k, v in have.items()
                      if k.startswith("pf_") and k not in STORAGE])
    return Result(name, not wrong, len(wrong),
                  "; ".join(wrong) or "all %d ok" % len(STORAGE))


def elem_ids_structural(geo, other, name="elem_ids_structural"):
    """§12.7: the id is site + stage + structural address, NEVER generation
    order.  `other` is the same two buildings cooked with the lots in the
    OPPOSITE order - the id sets must be identical, and unique.

    CANNOT SEE: an id stable under reordering but unstable under a geometry
    change upstream (the open S8 question §0.0a insulates against).
    """
    a = [f["pf_elem_id"] for f in faces(geo)]
    b = [f["pf_elem_id"] for f in faces(other)]
    dupes = [k for k, v in collections.Counter(a).items() if v > 1]
    ok = {"unique": not dupes and len(a) > 0,
          "order_independent": sorted(a) == sorted(b) and len(a) > 0}
    return Result(name, ok, [len(a), len(set(a)), len(set(b))],
                  "%d ids, %d duplicates, %d differ under reordered input"
                  % (len(a), len(dupes), len(set(a) ^ set(b))))


def no_scratch(geo, name="no_scratch"):
    """conventions.md §2/§5 - nothing beginning with `_` leaves the node, on
    any of the four attribute classes or the groups.

    ⚠️ All four attribute classes AND all four group types.  This read only
    prim and point groups until an audit measured that the sweep itself
    covers vertex and edge groups too - the check was narrower than the law
    it enforces, which is how a rule ends up worth nothing.

    CANNOT SEE: a leaked name that does NOT begin with `_`; that is what the
    baseline snapshot beside this check is for (conventions.md §7's reason).
    """
    names = ([a.name() for a in geo.pointAttribs()]
             + [a.name() for a in geo.primAttribs()]
             + [a.name() for a in geo.vertexAttribs()]
             + [a.name() for a in geo.globalAttribs()]
             + [g.name() for g in geo.primGroups()]
             + [g.name() for g in geo.pointGroups()]
             + [g.name() for g in geo.vertexGroups()]
             + [g.name() for g in geo.edgeGroups()])
    leaked = sorted(n for n in names if n.startswith("_"))
    return Result(name, not leaked, len(leaked),
                  "leaked scaffolding: %s" % (leaked or "none"))


def published_names(geo):
    """The baseline snapshot: every published name and its storage.  Records
    VALUES, not pass/fail - a new attribute on the output is a diff a human
    has to look at (conventions.md §7 check 2)."""
    def part(attrs):
        return sorted("%s:%s" % (a.name(), str(a.dataType()).split(".")[-1])
                      for a in attrs)
    return {"point": part(geo.pointAttribs()), "prim": part(geo.primAttribs()),
            "vertex": part(geo.vertexAttribs()),
            "detail": part(geo.globalAttribs()),
            "groups": sorted(g.name() for g in geo.primGroups())}


def masses_inside_lots(geo, lots, name="inside_the_lot"):
    """THE ROUND-2 BLOCKING DEFECT, as a standing assertion: a building stands
    on the lot it belongs to.

    Nothing else here could see it.  A legal cascade override inverted BOTH
    axes of a 20 x 10 lot; the signed area kept its sign and shrank, so all
    three collapse tests were silent, and `volume_count_matches`,
    `outward_normals` and `party_walls_real` stayed green over a mass built
    entirely outside its own lot with `pf_warn_footprint_collapsed` = 0 on
    every face.  Fixture site 6 IS that override.

    `lots` is {site: [(x, z), ...]} - the ring the FIXTURE built, never
    anything the generator derived, so this is a differential oracle against
    the input and not the output compared with itself.

    ⚠️ Inside OR ON.  `setback(0)` puts a wall exactly on the lot line and is
    what both Viennese templates ask for on every edge, and the degraded path
    deliberately rebuilds on the lot polygon itself.

    CANNOT SEE: a mass in the right lot in plan and at the wrong height; a
    mass inside a lot that is not its own but overlaps it; nor anything about
    lots this fixture does not build (every one is a rectangle).
    """
    bad, seen = [], 0
    for site, ring in sorted(lots.items()):
        for f in faces(geo, site):
            seen += 1
            gap = min(_inside(ring, (p[0], p[2])) for p in f["pts"])
            if gap < -TOL:
                bad.append((f["pf_elem_id"], round(gap, 2)))
    return Result(name, seen > 0 and not bad, [seen, len(bad)],
                  "%d faces measured against their own lot; outside it: %s"
                  % (seen, bad[:3] or "none"))


def warns_on_unknown_rule(geo, name="unknown_rule_warns"):
    """A template naming a rule the library does not have still BUILDS, on the
    default rule, and says so. Clean fixtures carry none; the mutation that
    misspells a rails mode is what proves the flag can rise.

    CANNOT SEE: a rule name that is spelled correctly and means the wrong
    thing.
    """
    hot = sorted(set(f["pf_style_id"] for f in faces(geo)
                     if f["pf_warn_unknown_rule"]))
    return Result(name, not hot, len(hot),
                  "styles naming a rule that does not exist: %s"
                  % (hot or "none"))


def warns_on_cap_group_split(geo, name="cap_group_split_warns"):
    """§2.2: advisory, never a wall.  Two volumes told to share a roof but
    given different heights still BUILD; they carry the warning.  This asserts
    the clean fixtures carry none - the mutation asserts the dirty one does.

    CANNOT SEE: whether the warning is visible to an artist, which is
    §12.8/§2.2's other half and is a B-stage HDA question.
    """
    hot = [f["pf_volume_id"] for f in faces(geo)
           if f["pf_warn_cap_group_split"]]
    return Result(name, not hot, len(set(hot)),
                  "volumes warned for a split cap group: %s"
                  % (sorted(set(hot))[:4] or "none"))
