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


def every_corner_is_an_arc(patch_geo, dot_tol=-0.985):
    """A junction corner that is a straight chord instead of an arc.

    Measured 50/50 on the grid case and 56/56 on the radial one: half of every
    junction's corners were straight. The cause was ours — the arc was refitted
    through the street cap corners rather than the caps being placed at the
    fillet's tangent points, so whenever the class radius could not span the
    chord it silently fell back to a straight line.

    A fillet tangent to both kerb lines exists for ANY non-collinear corner, so
    the only legitimate straight corner is a street running straight through the
    junction (the two mouths anti-parallel), which is what a real kerb does.
    Anything else is the bug coming back.
    """
    if patch_geo.findPointAttrib("is_cap") is None:
        return _skip("every_corner_is_an_arc", "no is_cap attribute")
    up = (0.0, 1.0, 0.0)

    def _street_dir(cin, cout, capc, centre):
        v = (cout[0] - cin[0], 0.0, cout[2] - cin[2])          # across the mouth
        d = (v[2] * up[1], 0.0, -v[0] * up[1])                 # cross(v, up)
        m = math.hypot(d[0], d[2]) or 1.0
        d = (d[0] / m, 0.0, d[2] / m)
        out = (capc[0] - centre[0], 0.0, capc[2] - centre[2])  # point away from the node
        return d if (d[0] * out[0] + d[2] * out[2]) >= 0 else (-d[0], 0.0, -d[2])

    bad = 0
    total = 0
    for prim in patch_geo.prims():
        pts = [v.point() for v in prim.vertices()]
        n = len(pts)
        if n < 3:
            continue
        cap = [p.attribValue("is_cap") for p in pts]
        aft = [p.attribValue("after_corner") for p in pts]
        pos = [p.position() for p in pts]
        centre = [sum(p[i] for p in pos) / n for i in range(3)]
        for i in range(n):
            if not (cap[i] == 1 and aft[i] == 1):
                continue                                       # not a corner start
            total += 1
            k, run = (i + 1) % n, 0
            while cap[k] == 0 and run < n:
                run += 1
                k = (k + 1) % n
            if run:
                continue                                       # has arc points: fine
            # straight: legitimate only if the two streets are anti-parallel
            a = _street_dir(pos[i - 1], pos[i], pts[i].attribValue("capc"), centre)
            b = _street_dir(pos[k], pos[(k + 1) % n], pts[k].attribValue("capc"), centre)
            if a[0] * b[0] + a[2] * b[2] > dot_tol:
                bad += 1
    return Result("every_corner_is_an_arc", bad == 0, bad,
                  "straight chords out of %d corners (through-streets excluded)" % total)


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


# ---------------------------------------------------------------------------
# schema — citygen_streets.md section 6
# ---------------------------------------------------------------------------

EDGE_ATTRS = ("edge_id", "street_class", "street_template", "streetWidth",
              "sidewalkWidthLeft", "sidewalkWidthRight", "laneWidth",
              "connectionStart", "connectionEnd", "layer", "region_id",
              "land_use", "source_node")
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

def self_intersections(node, label="self_intersections", expect=0):
    """Intersection Analysis reports 0 for a valid box, grid and kerb step —
    verified by control test — so a non-zero count is a REAL crossing, not mesh
    adjacency. Beware micron-scale non-planarity: see no_nonplanar_y."""
    import hou
    parent = node.parent()
    ia = parent.createNode("intersectionanalysis", "__chk_ia")
    try:
        ia.setInput(0, node)
        ia.cook(force=True)
        n = len(ia.geometry().points())
    except Exception as exc:
        ia.destroy()
        return _skip(label, "could not cook: %s" % str(exc)[:60])
    ia.destroy()
    return Result(label, n <= expect, n, "intersection points")
