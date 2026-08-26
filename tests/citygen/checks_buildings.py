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
                     "pf_wall_role", "pf_face_role", "pf_shared_with",
                     "pf_style_id"):
            rec[name] = prim.attribValue(name)
        for name in ("pf_site_id", "pf_volume_index", "pf_storeys",
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


def _plan_key(pts):
    """A face's footprint in (x,z), ignoring Y.

    Two volumes of one building meet in PLAN but not in elevation: their
    skirts reach different depths because the ground under each is different,
    so the shared face is only shared over the overlapping height.  Comparing
    the full 3D face would report a continuous farmhouse as three detached
    buildings - measured, it did."""
    return tuple(sorted(set((round(p[0], 3), round(p[2], 3)) for p in pts)))


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
    keys = dict((vid, set(_plan_key(f["pts"]) for f in fs
                          if f["pf_wall_role"] == "party"))
                for vid, fs in vols.items())
    ids = list(vols)
    for a in range(len(ids) - 1):
        if keys[ids[a]] & keys[ids[a + 1]]:
            joined += 1
    ok = (len(groups) == 1 and len(tops) == 1 and len(roles) >= min_roles
          and joined == len(ids) - 1 and len(ids) >= min_roles)
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
    gaps = ([_inside(out_ring, q) for q in ring]
            if closed and out_closed else [-1.0])
    lo, hi = min(gaps), max(gaps)
    ok = (ends == 0 and closed and out_closed and len(vols) >= 3
          and area > TOL and band > TOL and lo > TOL
          and (depth is None or (abs(lo - depth) <= 0.01
                                 and abs(hi - depth) <= 0.01)))
    return Result(name, ok, [len(vols), ends, len(yard), round(area, 2),
                             round(band, 2), round(lo, 2), round(hi, 2)],
                  "%d volumes, %d free ends, %d courtyard faces, courtyard "
                  "%.1f m2 inside a %.1f m2 band; tract depth %.2f-%.2f m "
                  "against %s asked for"
                  % (len(vols), ends, len(yard), area, band, lo, hi,
                     "%.2f" % depth if depth is not None else "nothing"))


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

    def base(f):
        return tuple(sorted(tuple(round(c, 3) for c in (p[0], p[2]))
                            for p in f["pts"]))
    plan = {}
    for vid, fs in vols.items():
        for f in fs:
            if f["pf_wall_role"] == "party":
                plan.setdefault((vid, base(f)), []).append(f)
    matched = overlapped = 0
    for vid, f in party:
        peers = plan.get((f["pf_shared_with"], base(f)))
        if not peers:
            continue
        matched += 1
        if any(min(f["ymax"], p["ymax"]) - max(f["ymin"], p["ymin"]) > TOL
               for p in peers):
            overlapped += 1
    ok = (bool(party) and named == len(party) and matched == len(party)
          and overlapped == len(party))
    return Result(name, ok, [len(party), named, matched, overlapped],
                  "%d party faces, %d name a neighbour, %d meet it in plan, "
                  "%d share height with it"
                  % (len(party), named, matched, overlapped))


def volume_count_matches_template(geo, templates, sites, degraded_sites=(),
                                  name="volume_count_matches"):
    """Every volume the template asks for is actually IN THE OUTPUT, and only
    the sites the FIXTURE says are impossible are allowed to degrade.

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

    CANNOT SEE: a volume that is present and in the wrong place.
    """
    bad = []
    for site, style in sorted(sites.items()):
        fs = faces(geo, site)
        if not fs:
            bad.append((site, 0, "nothing built"))
            continue
        got = len(set(f["pf_volume_id"] for f in fs))
        warned = any(f["pf_warn_footprint_collapsed"] for f in fs)
        if site in degraded_sites:
            if got != 1 or not warned:
                bad.append((site, got, "expected 1 degraded + a warning"))
        elif got != len(templates[style]["volumeTopology"]["volumes"]):
            bad.append((site, got,
                        len(templates[style]["volumeTopology"]["volumes"])))
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


def plinth_follows_ground(geo, site, name="plinth_follows_ground"):
    """`levelToHighest` on a slope: ONE floor datum for the whole building,
    and a skirt under every volume that reaches the ground it stands on - so
    the datums are identical and the SKIRT DEPTHS are not.  Both halves are
    asserted: one level alone is a building floating on a slab, varying depths
    alone is a stepped building, and neither is a plinth.

    With the rule off, datum and base are both 0 everywhere, so the varying
    depth is what goes red.

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
    ok = (len(datums) == 1 and len(depths) > 1
          and min(depths) > TOL and len(vols) > 1)
    return Result(name, ok, [sorted(datums), sorted(depths)],
                  "%d floor datum(s) over %d volumes, %d distinct skirt "
                  "depths %s" % (len(datums), len(vols), len(depths),
                                 sorted(depths)))


# --- contract and law -------------------------------------------------------

STORAGE = {"pf_elem_id": "String", "pf_volume_id": "String",
           "pf_volume_role": "String", "pf_wall_role": "String",
           "pf_face_role": "String", "pf_shared_with": "String",
           "pf_style_id": "String", "pf_site_id": "Int",
           "pf_volume_index": "Int", "pf_storeys": "Int",
           "pf_cap_group": "Int", "pf_plinth_top": "Float",
           "pf_storey_height": "Float"}


def attribute_storage(geo, name="attribute_storage"):
    """D223: an attribute's STORAGE is part of its contract.  An int id once
    shipped a different fence AND a different curve order with no coverage, so
    every id B2 mints is enrolled here from day one.

    CANNOT SEE: an attribute of the right storage carrying a wrong value.
    """
    have = dict((a.name(), str(a.dataType()).split(".")[-1])
                for a in geo.primAttribs())
    wrong = sorted("%s=%s want %s" % (k, have.get(k, "MISSING"), v)
                   for k, v in STORAGE.items() if have.get(k) != v)
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
    ok = not dupes and sorted(a) == sorted(b) and len(a) > 0
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


def degrades_never_refuses(geo, site, name="degrades_never_refuses"):
    """§2.2, asserted rather than assumed: a lot too small for its own setbacks
    still produces a BUILDING, and that building carries the warning.

    ⚠️ The second half is here because the first build failed it invisibly.
    `pf_warn_footprint_collapsed` was written on the footprint prim, and the
    mass wrangle then removed that prim - leaving the attribute DEFINITION,
    so every shipped face read 0 and the published-names baseline listed the
    warning as present. A warning that cannot be non-zero is not advisory
    validation, it is a name.

    CANNOT SEE: whether the degraded mass is a SENSIBLE building - only that
    one exists, is closed, and says so.
    """
    mine = [f for f in faces(geo) if f["pf_site_id"] == site]
    if not mine:
        return Result(name, False, 0,
                      "site %d produced NOTHING - a refusal, not a warning"
                      % site)
    vols = set(f["pf_volume_id"] for f in mine)
    warned = [f for f in mine if f["pf_warn_footprint_collapsed"]]
    ok = len(vols) == 1 and len(warned) == len(mine) and len(mine) >= 5
    return Result(name, ok, [len(vols), len(mine), len(warned)],
                  "%d volume(s), %d faces, %d carrying the collapse warning"
                  % (len(vols), len(mine), len(warned)))


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
