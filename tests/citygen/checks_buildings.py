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


def plan_follows_data(geo, lots, templates, degraded=(), authored=None,
                      name="plan_follows_data"):
    """WHERE THE MASS IS AND HOW BIG IT IS IN PLAN - the dimension nothing in
    the first build could see, and the one G2's L-footprint is made of.

    Two DIFFERENTIAL ORACLES, both computed here from the fixture's own lot
    rectangle and the template's numbers, never from the geometry:
      * `footprint` - a rectangle inset per role is arithmetic, so the built
        mass's plan bounds must equal `lot inset by setbackM`. `pf_inset.vfl`
        solving corners is not consulted; the expected box is four additions.
      * `cell_split` - under `bar` the cells' plan AREAS must be in the ratio
        of the `cutsAt` intervals. Compared in `pf_volume_index` order, or its
        reverse, because the rail direction follows the longer edge.

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
    area swapped; nor a `footprint` claim on a non-rectangular lot, because it
    compares BOUNDING BOXES - exact for these four-corner lots and nearly
    vacuous for G2's L, which is why generalising it is G2's first test task.
    """
    bad = []
    for site, style, (ox, oz), (sx, sz), roles in lots:
        if site in degraded:
            continue
        tpl = templates[style]
        fp = tpl["lotToFootprint"]
        table = fp["setbackM"] if fp["op"] != "identity" else {}
        over = (authored or {}).get(site) or []
        s = [over[i] if i < len(over) and over[i] >= 0.0
             else float(table.get(r, 0.0 if fp["op"] == "identity"
                                  else fp["defaultSetbackM"]))
             for i, r in enumerate(roles)]
        want = (ox + s[3], oz + s[0], ox + sx - s[1], oz + sz - s[2])
        got = plan_box(faces(geo, site))
        if max(abs(g - w) for g, w in zip(got, want)) > TOL:
            bad.append((site, "footprint", [round(v, 2) for v in got],
                        [round(v, 2) for v in want]))
        topo = tpl["volumeTopology"]
        if topo["rails"] != "bar" or not topo["cutsAt"]:
            continue
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
    return Result(name, {"footprint": not [b for b in bad if b[1] ==
                                           "footprint"],
                         "cell_split": not [b for b in bad if b[1] ==
                                            "cell_split"]},
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
