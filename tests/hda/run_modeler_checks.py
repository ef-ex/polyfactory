"""`pf_modeler` checks, against the SHIPPED asset, in a throwaway session.

    hython tests/hda/run_modeler_checks.py [seed]

Fixture: a seeded random tree of spheres (every sphere after the first
hangs off an earlier one, degrees up to six), a closed three-sphere loop,
a straight chain, and one isolated sphere - random positions and radii.
Thirteen checks, twenty-seven mutations, each seen red.

What these checks CANNOT see: whether the limbs look good (twist, pinching
at sharp bends) - that is Hannes' viewport; limbs crossing each other away
from a joint (input, not the tool); where exactly the bad-joint threshold
should sit (0.2 is a guess; c9 uses a fan far inside it).
"""

import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HDA = os.path.join(REPO, "polyfactory", "otls", "pf_modeler.hda").replace("\\", "/")


def fixture(seed):
    import hou
    rnd = random.Random(seed)
    geo = hou.Geometry()
    geo.addAttrib(hou.attribType.Point, "pscale", 0.0)
    pts = []

    def sphere(pos, r):
        p = geo.createPoint()
        p.setPosition(pos)
        p.setAttribValue("pscale", r)
        pts.append(p)
        return p

    def link(*ps, closed=False):
        pl = geo.createPolygon()
        pl.setIsClosed(closed)
        for p in ps:
            pl.addVertex(p)

    # a tree, spheres 0.3..1.2 apart so limbs are longer than the cubes
    tree = [sphere(hou.Vector3(0, 0, 0), rnd.uniform(0.05, 0.12))]
    deg = {0: 0}
    for i in range(1, 12):
        cands = [j for j in range(i) if deg[j] < 6]
        j = rnd.choice(cands)
        d = hou.Vector3(rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)).normalized()
        p = sphere(tree[j].position() + d * rnd.uniform(0.4, 0.9), rnd.uniform(0.04, 0.12))
        tree.append(p)
        deg[i] = 1
        deg[j] += 1
        link(tree[j], p)
    # a closed loop, far away
    loop = [sphere(hou.Vector3(5 + x, 0, z), 0.08) for x, z in ((0, 0), (1, 0), (0.5, 0.9))]
    link(*loop, closed=True)
    # a straight chain as ONE polyline (pass-through nodes)
    chain = [sphere(hou.Vector3(-5 + 0.6 * k, 0.1 * k, 0), 0.06 + 0.01 * k) for k in range(4)]
    link(*chain)
    # an isolated sphere
    sphere(hou.Vector3(0, 5, 0), 0.1)
    return geo


def directed_edges(geo):
    seen = {}
    for pr in geo.prims():
        ids = [v.point().number() for v in pr.vertices()]
        for i in range(len(ids)):
            e = (ids[i - 1], ids[i])
            seen[e] = seen.get(e, 0) + 1
    return seen


def components(geo):
    parent = list(range(len(geo.points())))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for pr in geo.prims():
        ids = [v.point().number() for v in pr.vertices()]
        for i in ids[1:]:
            parent[find(i)] = find(ids[0])
    return {p: find(p) for p in range(len(geo.points()))}


def c1_every_face_is_a_quad(cook):
    bad = {}
    for sub in (0, 2):
        g = cook(subdivisions=sub)
        bad[sub] = [len(p.vertices()) for p in g.prims() if len(p.vertices()) != 4]
    return all(not b for b in bad.values()) and len(cook(subdivisions=0).prims()) > 0, \
        "non-quad vertex counts by subdivision level %s (want none)" % bad


def c2_closed_and_consistently_wound(cook):
    g = cook(subdivisions=0)
    de = directed_edges(g)
    twice = [e for e, c in de.items() if c != 1]
    unmatched = [e for e in de if (e[1], e[0]) not in de]
    return not twice and not unmatched, "%d directed edges used twice, %d without their reverse (want 0, 0)" % (
        len(twice), len(unmatched))


def c3_faces_point_outward(cook):
    """Houdini's own prim normal (its winding convention, not ours) must
    point away from the sphere a cap belongs to, on every cap."""
    src, g = cook(_asis=True), cook(subdivisions=0)
    centres = {p.number(): p.position() for p in src.points()}
    inward = []
    for pr in g.prims():
        node = pr.attribValue("pf_node")
        if node < 0:
            continue
        c = sum((v.point().position() for v in pr.vertices()), hou.Vector3()) / 4
        if pr.normal().dot(c - centres[node]) <= 0:
            inward.append(pr.number())
    return not inward and len(g.prims()) > 0, "%d caps facing inward %s (want none)" % (len(inward), inward[:6])


def c4_every_connection_joins_its_spheres(cook):
    """At subdivision 0 each sphere still owns its 8 corners: a limb exists
    exactly when the two spheres' corners share a connected piece."""
    src, g = cook(_asis=True), cook(subdivisions=0)
    comp = components(g)
    outpts = list(g.points())

    def corners(sp):
        c, r = sp.position(), sp.attribValue("pscale")
        return [p.number() for p in outpts if abs((p.position() - c).length() - r * 3 ** 0.5) < 1e-4]

    owned = {sp.number(): corners(sp) for sp in src.points()}
    wrong_count = [n for n, c in owned.items() if len(c) != 8]
    broken = []
    for pl in src.prims():
        ids = [v.point().number() for v in pl.vertices()]
        pairs = list(zip(ids, ids[1:])) + ([(ids[-1], ids[0])] if pl.isClosed() else [])
        for a, b in pairs:
            if comp[owned[a][0]] != comp[owned[b][0]]:
                broken.append((a, b))
    n_pieces = len(set(comp.values()))
    want_pieces = 4   # tree, loop, chain, isolated
    return not wrong_count and not broken and n_pieces == want_pieces, \
        "spheres without 8 corners %s, unjoined connections %s, pieces %d (want [], [], %d)" % (
            wrong_count, broken, n_pieces, want_pieces)


def c5_output_contract(cook):
    g = cook(subdivisions=1)
    leaked = [a.name() for cls in (g.pointAttribs(), g.primAttribs(), g.vertexAttribs(), g.globalAttribs())
              for a in cls if a.name().startswith("_")]
    leaked += [x.name() for x in list(g.pointGroups()) + list(g.primGroups()) if x.name().startswith("_")]
    names = sorted(a.name() for cls in (g.pointAttribs(), g.primAttribs(), g.vertexAttribs(), g.globalAttribs())
                   for a in cls)
    a = g.findPrimAttrib("pf_node")
    vals = set(p.attribValue("pf_node") for p in g.prims()) if a else set()
    sh = g.findPrimAttrib("pf_sheet")
    ok = (not leaked and names == ["P", "pf_node", "pf_sheet", "pf_trunk"] and a.dataType() == hou.attribData.Int
          and sh.dataType() == hou.attribData.Int and -1 in vals and max(vals) >= 0)
    return ok, "leaked %s, attributes %s (want P, pf_node, pf_sheet, pf_trunk only), pf_node %s values %s" % (
        leaked, names, a and a.dataType(), sorted(vals)[:4])


def c6_radius_parm_used_without_pscale(cook):
    r = 0.07
    g, src = cook(subdivisions=0, radius=r, _nopscale=True), cook(_asis=True)
    outpts = list(g.points())
    short = [sp.number() for sp in src.points() if sum(
        1 for p in outpts if abs((p.position() - sp.position()).length() - r * 3 ** 0.5) < 1e-4) != 8]
    a = [((0.5 * i, 0, 0), 0.0) for i in range(4)]
    b = [((0.5 * i, 0, 1.0), 0.0) for i in range(4)]
    sheet = cook(subdivisions=0, radius=r, _nopscale=True, _graph=graph(a + b, [[0, 1, 2, 3], [4, 5, 6, 7]], (1, 1)))
    half = sorted(set(round(abs(p.position()[1]), 4) for p in sheet.points()))
    # with pscale present the same Radius multiplies it: at 2 the corners sit at 2 r sqrt3
    g2 = cook(subdivisions=0, radius=2.0)
    out2 = list(g2.points())
    unscaled = [sp.number() for sp in src.points() if sum(
        1 for p in out2 if abs((p.position() - sp.position()).length() - 2 * sp.attribValue("pscale") * 3 ** 0.5) < 1e-4) != 8]
    return not short and half == [r] and not unscaled, "spheres without 8 corners at Radius %s: %s (want none); sheet half-thickness %s (want [%s]); spheres not doubled by Radius 2: %s (want none)" % (
        r, short, half, r, unscaled)


def graph(spheres, links, sheets=(), trunks=()):
    """spheres: [(pos, r)], links: [[i, j, ...]] open polylines; sheets /
    trunks: pf_sheet / pf_trunk value per polyline (0 = a connection)."""
    g = hou.Geometry()
    g.addAttrib(hou.attribType.Point, "pscale", 0.0)
    if sheets:
        g.addAttrib(hou.attribType.Prim, "pf_sheet", 0)
    if trunks:
        g.addAttrib(hou.attribType.Prim, "pf_trunk", 0)
    pts = []
    for pos, r in spheres:
        p = g.createPoint()
        p.setPosition(hou.Vector3(*pos))
        p.setAttribValue("pscale", r)
        pts.append(p)
    for k, lk in enumerate(links):
        pl = g.createPolygon()
        pl.setIsClosed(False)
        for i in lk:
            pl.addVertex(pts[i])
        if sheets:
            pl.setAttribValue("pf_sheet", sheets[k])
        if trunks:
            pl.setAttribValue("pf_trunk", trunks[k])
    return g


def c11_trunk_with_a_branch_is_one_mesh(cook):
    """Four lines around a 1 x 1 square, five stations over 2 units, marked
    pf_trunk 1, one of them drawn the other way; a branch curve from a
    trunk point (its middle station) out to a sphere 1 unit away. One
    closed, consistently wound, all-quad piece of 46 faces: 4 x 8 ring
    cells minus the one the branch took, two 3-quad zipper caps, 4 limb
    quads and the branch sphere's 5 caps; every trunk face's Houdini
    normal away from the trunk's centre; pf_trunk 1 on exactly 37 faces."""
    lines = [[((x, 0.5 * i, z), 0.0) for i in range(5)] for x, z in ((0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5), (0.5, -0.5))]
    lines[2] = lines[2][::-1]
    sph = sum(lines, []) + [((1.5, 1.0, 0.5), 0.08)]
    links = [[5 * k + i for i in range(5)] for k in range(4)] + [[2, 20]]
    g = cook(subdivisions=0, _graph=graph(sph, links, trunks=(1, 1, 1, 1, 0)))
    de = directed_edges(g)
    bad = sum(1 for c in de.values() if c != 1) + sum(1 for e in de if (e[1], e[0]) not in de)
    nonquad = sum(1 for p in g.prims() if len(p.vertices()) != 4)
    pieces = len(set(components(g).values()))
    trunk = [p for p in g.prims() if p.attribValue("pf_trunk") == 1]
    inward = 0
    for p in trunk:
        c = sum((v.point().position() for v in p.vertices()), hou.Vector3()) / 4
        if p.normal().dot(c - hou.Vector3(0, 1.0, 0)) <= 0:   # the box is convex: away from its centre
            inward += 1
    # the limb must leave from the branch point's own cell, not any facing cell
    P = hou.Vector3(0.5, 1.0, 0.5)
    limbs = [p for p in g.prims() if p.attribValue("pf_node") == -1 and p.attribValue("pf_trunk") == 0]
    far = [p.number() for p in limbs if min((v.point().position() - P).length() for v in p.vertices()) > 0.6]
    ok = bad == 0 and nonquad == 0 and pieces == 1 and len(g.prims()) == 46 and len(trunk) == 37 and inward == 0 and not far
    return ok, "%d bad edges, %d non-quads, %d pieces, %d prims, %d trunk faces, %d inward, limb quads away from the branch point %s, warnings %s (want 0, 0, 1, 46, 37, 0, [])" % (
        bad, nonquad, pieces, len(g.prims()), len(trunk), inward, far, list(cook.node.warnings()))


def c12_trunk_awkward_branches_warn_and_stay_closed(cook):
    """Same square trunk: a branch aimed INTO the trunk is dropped with a
    warning (no limb through the far wall); two branches from adjacent
    lines wanting one wall cell keep one, warn, and stay closed; Loft Spans 1
    on three lines gives an odd ring that is rounded up to even so the caps
    close, its lines' pscale 0.1 pushes the surface out to 0.6 from the
    axis, and Wrap 1 presses the mid-chord point onto the chord (0.25 from
    the axis, 0.35 at Wrap 0). Every case closed, consistently wound, all
    quads."""
    def trunk4():
        lines = [[((x, 0.5 * i, z), 0.0) for i in range(5)] for x, z in ((0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5), (0.5, -0.5))]
        return sum(lines, []), [[5 * k + i for i in range(5)] for k in range(4)]

    def closed_quads(g):
        de = directed_edges(g)
        return (sum(1 for c in de.values() if c != 1) + sum(1 for e in de if (e[1], e[0]) not in de) == 0
                and all(len(p.vertices()) == 4 for p in g.prims()))

    sph, links = trunk4()
    g = cook(subdivisions=0, _graph=graph(sph + [((0, 1.0, 0), 0.08)], links + [[2, 20]], trunks=(1, 1, 1, 1, 0)))
    into = (closed_quads(g), len(g.prims()), any("no cell" in w for w in cook.node.warnings()))
    sph, links = trunk4()
    # two branches from the same station on the two lines of the +x wall, both heading +x: one cell
    g = cook(subdivisions=0, sheetspans=1, _graph=graph(
        sph + [((1.5, 0.6, 0.5), 0.08), ((1.5, 0.6, -0.5), 0.08)], links + [[1, 20], [16, 21]], trunks=(1, 1, 1, 1, 0, 0)))
    clash = (closed_quads(g), len(set(components(g).values())), any("same surface cell" in w for w in cook.node.warnings()))
    # ...and the lines are sphere centres: pscale 0.1 on lines 0.5 from the axis puts the surface at 0.6
    tri = [[((0.5 * x, 0.5 * i, 0.5 * z), 0.1) for i in range(5)] for x, z in ((1, 0), (-0.5, 0.8660254), (-0.5, -0.8660254))]
    g = cook(subdivisions=0, sheetspans=1, _graph=graph(sum(tri, []), [[5 * k + i for i in range(5)] for k in range(3)], trunks=(1, 1, 1)))
    radial = lambda g: [hou.Vector3(p.position()[0], 0, p.position()[2]).length() for p in g.points()]
    reach = round(max(radial(g)), 3)
    # Wrap 1: the mid-chord point between two lines 0.866 apart at radius 0.1 is pressed
    # onto the chord itself, 0.25 from the axis; Wrap 0 keeps it at 0.35
    valley0 = round(min(radial(g)), 3)
    g = cook(subdivisions=0, sheetspans=1, wrap=1.0, _graph=graph(sum(tri, []), [[5 * k + i for i in range(5)] for k in range(3)], trunks=(1, 1, 1)))
    valley1 = round(min(radial(g)), 3)
    # Wrap -1 mirrors the dip into a hill (0.45, still under the 0.6 line points); Wrap 2 pushes
    # the mid-chord point 0.1 past the chord, to 0.15 from the axis
    g = cook(subdivisions=0, sheetspans=1, wrap=-1.0, _graph=graph(sum(tri, []), [[5 * k + i for i in range(5)] for k in range(3)], trunks=(1, 1, 1)))
    hill = round(min(radial(g)), 3)
    g = cook(subdivisions=0, sheetspans=1, wrap=2.0, _graph=graph(sum(tri, []), [[5 * k + i for i in range(5)] for k in range(3)], trunks=(1, 1, 1)))
    deep = round(min(radial(g)), 3)
    odd = (closed_quads(g), len(g.prims()), reach, valley0, valley1, hill, deep)
    ok = into == (True, 44, True) and clash == (True, 2, True) and odd == (True, 18, 0.6, 0.35, 0.25, 0.45, 0.15)
    return ok, "into-trunk (closed, prims, warned) %s want (True, 44, True); clash (closed, pieces, warned) %s want (True, 2, True); odd ring (closed, prims, reach, mid-chord at Wrap 0 / 1 / -1 / 2) %s want (True, 18, 0.6, 0.35, 0.25, 0.45, 0.15)" % (
        into, clash, odd)


def c10_two_curves_loft_to_one_slab(cook):
    """Two parallel curves 2 long and 1.2 apart marked pf_sheet 1 - the
    first with uneven points and radius 0.1, the second drawn the OTHER
    WAY with three points and radius 0.05: one closed, consistently wound,
    all-quad shell of 28 faces (5 stations, 2 spans: square-ish quads),
    every face pf_sheet 1, Houdini's own prim normal away from the slab's
    centre on every face, 0.2 thick along the first curve and 0.1 along
    the second."""
    a = [((x, 0, 0), 0.1) for x in (0, 0.1, 0.2, 0.3, 2.0)]
    b = [((2.0 - 1.0 * i, 0, 1.2), 0.05) for i in range(3)]
    g = cook(subdivisions=0, _graph=graph(a + b, [[0, 1, 2, 3, 4], [5, 6, 7]], (1, 1)))
    ys = {z: sorted(set(round(abs(p.position()[1]), 4) for p in g.points() if abs(p.position()[2] - z) < 1e-4))
          for z in (0.0, 1.2)}
    thick = ys == {0.0: [0.1], 1.2: [0.05]}
    de = directed_edges(g)
    bad = sum(1 for c in de.values() if c != 1) + sum(1 for e in de if (e[1], e[0]) not in de)
    nonquad = sum(1 for p in g.prims() if len(p.vertices()) != 4)
    tags = set(p.attribValue("pf_sheet") for p in g.prims())
    centre = sum((p.position() for p in g.points()), hou.Vector3()) / len(g.points())
    inward = sum(1 for p in g.prims() if p.normal().dot(
        sum((v.point().position() for v in p.vertices()), hou.Vector3()) / 4 - centre) <= 0)
    pieces = len(set(components(g).values()))
    ok = bad == 0 and nonquad == 0 and tags == {1} and inward == 0 and pieces == 1 and len(g.prims()) == 28 and thick
    return ok, "%d bad edges, %d non-quads, pf_sheet %s, %d inward, %d pieces, %d prims, half-thickness by side %s (want 0, 0, {1}, 0, 1, 28, {0.0: [0.1], 1.2: [0.05]})" % (
        bad, nonquad, sorted(tags), inward, pieces, len(g.prims()), ys)


def c7_joints_do_not_self_intersect(cook):
    """Intersection Analysis (a native oracle sharing nothing with the VEX)
    over legal joints: a straight chain, a 90 degree bend, a tetrahedral
    hub, a six-limb hub. Cannot see: limbs bunched tighter than a cube's
    faces (those warn, c9), limbs crossing each other far from a joint."""
    t = 1 / 3 ** 0.5
    tet = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    axes = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    sph = [((0, 0, 0), 0.1), ((0.6, 0, 0), 0.08), ((1.2, 0, 0), 0.1),          # chain
           ((3, 0, 0), 0.1), ((3.6, 0, 0), 0.08), ((3.6, 0.6, 0), 0.1),        # bend
           ((6, 0, 0), 0.1)] + [((6 + 0.7 * t * x, 0.7 * t * y, 0.7 * t * z), 0.06) for x, y, z in tet] + \
          [((9, 0, 0), 0.1)] + [((9 + 0.7 * x, 0.7 * y, 0.7 * z), 0.06) for x, y, z in axes]
    links = [[0, 1, 2], [3, 4, 5]] + [[6, 7 + i] for i in range(4)] + [[11, 12 + i] for i in range(6)]
    g = cook(subdivisions=0, _graph=graph(sph, links))
    n = selfx(g)
    return n == 0, "%d self-intersections (want 0)" % n


def c8_awkward_connectivity_stays_closed(cook):
    """An eight-limb hub (the seventh AND eighth must be dropped - resize
    pads with 0, a taken face), the same pair linked twice, a two-sphere
    loop written as [0, 1, 0]: every one must still be a closed, all-quad,
    consistently wound mesh (extras dropped, duplicates one limb)."""
    hub = [((0, 0, 0), 0.1)] + [((0.7 * x, 0.7 * y, 0.7 * z), 0.05) for x, y, z in
                                [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                                 (0.6, 0.8, 0), (0, 0.8, 0.6)]]
    sph = hub + [((3, 0, 0), 0.1), ((3.6, 0, 0), 0.1), ((5, 0, 0), 0.1), ((5.6, 0, 0), 0.1)]
    links = [[0, 1 + i] for i in range(8)] + [[8 + 1, 9 + 1], [9, 10], [11, 12, 11]]
    g = cook(subdivisions=0, _graph=graph(sph, links))
    de = directed_edges(g)
    bad = sum(1 for c in de.values() if c != 1) + sum(1 for e in de if (e[1], e[0]) not in de)
    nonquad = sum(1 for p in g.prims() if len(p.vertices()) != 4)
    want = 13 * 6 - 2 * 8 + 8 * 4   # cubes, minus the 8 limbs' two faces each, plus 8 limbs
    return bad == 0 and nonquad == 0 and len(g.prims()) == want, "%d bad edges, %d non-quads, %d prims (want 0, 0, %d)" % (
        bad, nonquad, len(g.prims()), want)


def c9_bad_joint_warns_on_the_locked_instance(cook):
    """Five limbs within 20 degrees of each other cannot all leave through
    a cube face, and a seventh limb is dropped: the artist must see both
    warnings. A single limb must see none."""
    import math
    fan = [((0, 0, 0), 0.1)] + [((0.7 * math.cos(a), 0.7 * math.sin(a), 0), 0.05)
                                for a in (0, 0.087, 0.175, 0.262, 0.349)]
    cook(subdivisions=0, _graph=graph(fan, [[0, 1 + i] for i in range(5)]))
    warned = [w for w in cook.node.warnings() if "too close" in w]
    axes = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1), (0.6, 0.8, 0)]
    star = [((0, 0, 0), 0.1)] + [((0.7 * x, 0.7 * y, 0.7 * z), 0.05) for x, y, z in axes]
    cook(subdivisions=0, _graph=graph(star, [[0, 1 + i] for i in range(7)]))
    seven = [w for w in cook.node.warnings() if "more than six" in w]
    cook(subdivisions=0, _graph=graph(fan[:2], [[0, 1]]))
    clean = cook.node.warnings()
    return bool(warned) and bool(seven) and not clean, "fan warned %s, seven-limb warned %s, single limb warnings %s (want both, none)" % (
        bool(warned), bool(seven), list(clean))


def selfx(g):
    st = hou.node("/obj/modeler_checks").createNode("stash")
    st.parm("stash").set(g)
    ia = st.parent().createNode("intersectionanalysis")
    ia.setInput(0, st)
    n = len(ia.geometry().points())
    ia.destroy()
    st.destroy()
    return n


def c13_branch_attaches_where_it_leaves_the_shell(cook):
    """The square trunk with pscale 0.2 on its lines (shell at 0.7); a branch
    stroke from a trunk point with spheres at x 0.55 and 0.65 (inside the
    shell), then 1.0 and 1.5 outside. The two buried spheres get no cube -
    no output point within 0.1 of them - and the limb leaves the cell for
    the sphere at 1.0; one closed, consistently wound, all-quad piece."""
    lines = [[((x, 0.5 * i, z), 0.2) for i in range(5)] for x, z in ((0.5, 0.5), (-0.5, 0.5), (-0.5, -0.5), (0.5, -0.5))]
    sph = sum(lines, []) + [((0.55, 1.0, 0.5), 0.03), ((0.65, 1.0, 0.5), 0.03), ((1.0, 1.0, 0.5), 0.06), ((1.5, 1.0, 0.5), 0.06)]
    links = [[5 * k + i for i in range(5)] for k in range(4)] + [[2, 20, 21, 22, 23]]
    g = cook(subdivisions=0, _graph=graph(sph, links, trunks=(1, 1, 1, 1, 0)))
    de = directed_edges(g)
    bad = sum(1 for c in de.values() if c != 1) + sum(1 for e in de if (e[1], e[0]) not in de)
    pieces = len(set(components(g).values()))
    buried = [i for i, x in ((20, 0.55), (21, 0.65)) if any((p.position() - hou.Vector3(x, 1.0, 0.5)).length() < 0.1 for p in g.points())]
    limb = [p for p in g.prims() if p.attribValue("pf_node") == -1 and p.attribValue("pf_trunk") == 0]
    reaches = any(min((v.point().position() - hou.Vector3(1.0, 1.0, 0.5)).length() for v in p.vertices()) < 0.06 * 3 ** 0.5 + 1e-4 for p in limb)
    ok = bad == 0 and pieces == 1 and not buried and reaches and any("never leaves" not in w for w in [""]) and not cook.node.warnings()
    return ok, "%d bad edges, %d pieces, cubes on buried spheres %s, limb reaches the first clear sphere %s, warnings %s (want 0, 1, [], True, [])" % (
        bad, pieces, buried, reaches, list(cook.node.warnings()))


def _patch(net, node, old, new):
    p = net.node(node).parm("snippet")
    src = p.eval()
    assert old in src, "mutation target not in %s's VEX: %r" % (node, old)
    p.set(src.replace(old, new))


def m_bridge_emits_triangles(net):
    _patch(net, "bridge", "A[i], A[j], B[(bestr - j + 4) % 4], B[(bestr - i + 4) % 4]",
           "A[i], A[j], B[(bestr - j + 4) % 4]")


def m_bridge_reversed(net):
    _patch(net, "bridge", "A[i], A[j], B[(bestr - j + 4) % 4], B[(bestr - i + 4) % 4]",
           "A[j], A[i], B[(bestr - i + 4) % 4], B[(bestr - j + 4) % 4]")


def m_faces_inside_out(net):
    _patch(net, "cage", "int k = pos ? (4 - i) % 4 : i;", "int k = pos ? i : (4 - i) % 4;")
    _patch(net, "bridge", "int k = pos ? (4 - i) % 4 : i;", "int k = pos ? i : (4 - i) % 4;")


def m_no_bridge(net):
    net.node("bridge").bypass(True)


def m_sheet_no_direction_check(net):
    _patch(net, "loft", "append(flips, dot(a1 - a0, b1 - b0) < 0);", "append(flips, 0);")


def m_sheet_radius_not_interpolated(net):
    _patch(net, "loft", "float straight = lerp(ra, rb, t);", "float straight = ra;")


def m_sheet_spans_always_one(net):
    _patch(net, "loft", "append(spans, clamp(m, 1, 32));", "append(spans, 1);")


def m_sheet_top_reversed(net):
    _patch(net, "loft", 'quad(top[a], top[d], top[c], top[b], tag, id)',
           'quad(top[a], top[b], top[c], top[d], tag, id)')


def m_trunk_caps_reversed(net):
    _patch(net, "loft", 'if (fwd) { quad(ring[v0], ring[v1], ring[v2], ring[v3], tag, id);',
           'if (fwd) { quad(ring[v3], ring[v2], ring[v1], ring[v0], tag, id);')
    _patch(net, "loft", 'else     { quad(ring[v1], ring[v0], ring[v3], ring[v2], tag, id);',
           'else     { quad(ring[v2], ring[v3], ring[v0], ring[v1], tag, id);')


def m_trunk_ring_flipped(net):
    _patch(net, "loft", "int fwd = sign < 0;", "int fwd = sign > 0;")


def m_first_facing_cell(net):
    _patch(net, "cage", "if (dd < bestd) { bestd = dd; best = pr; }", "if (best < 0) { bestd = dd; best = pr; }")


def m_no_locality(net):
    _patch(net, "cage", "if (best >= 0 && bestd > 2 * nearest + 1e-6) best = -1;", "")


def m_no_resolve(net):
    net.node("resolve").bypass(True)


def m_trunk_ignores_pscale(net):
    _patch(net, "loft", "if (length(o) > 1e-9) P[i * W + j] += normalize(o) * R[i * W + j];", "")


def m_wrap_ignored(net):
    _patch(net, "loft", "append(R, lerp(straight, max(ea, eb), wrap));", "append(R, straight);")


def m_wrap_clamped(net):
    _patch(net, "loft", 'float wrap = chf("../wrap");', 'float wrap = clamp(chf("../wrap"), 0, 1);')


def m_radius_scale_ignored(net):
    _patch(net, "cage", 'float(point(0, "pscale", @ptnum)) * chf("../radius")', 'float(point(0, "pscale", @ptnum))')


def m_no_burial(net):
    _patch(net, "resolve", "if (dot(P - cc, nrm) >= r) break;", "break;")


def m_odd_ring_allowed(net):
    _patch(net, "loft", "if (closed && M % 2 == 1) { spans[-1] += 1; M += 1; }", "")


def m_branch_gets_a_cube(net):
    _patch(net, "cage", "if (onsheet && len(nbs) == 1) {", "if (0) {")


def m_no_cleanup(net):
    net.node("cleanup").bypass(True)


def m_radius_hardcoded(net):
    _patch(net, "cage", ': chf("../radius"), 1e-5)', ": 0.1, 1e-5)")


def m_worst_twist(net):
    _patch(net, "bridge", "float best = 1e30;", "float best = -1;")
    _patch(net, "bridge", "if (sum < best)", "if (sum > best)")


def m_resize_pads_zero(net):
    _patch(net, "cage", "for (int n = 6; n < k; n++) faces[n] = -1;", "")


def m_no_cap_restored(net):
    _patch(net, "bridge", "if (fb < 0 && fa >= 0) cap(a, fa, ca);", "")


def m_report_bypassed(net):
    net.node("report").bypass(True)


def m_no_too_many_group(net):
    _patch(net, "cage", 'if (k > 6) setpointgroup(0, "_too_many", @ptnum, 1);', "")


REGISTRY = [
    (c1_every_face_is_a_quad, m_bridge_emits_triangles),
    (c2_closed_and_consistently_wound, m_bridge_reversed),
    (c3_faces_point_outward, m_faces_inside_out),
    (c4_every_connection_joins_its_spheres, m_no_bridge),
    (c5_output_contract, m_no_cleanup),
    (c6_radius_parm_used_without_pscale, m_radius_hardcoded),
    (c6_radius_parm_used_without_pscale, m_radius_scale_ignored),
    (c7_joints_do_not_self_intersect, m_worst_twist),
    (c8_awkward_connectivity_stays_closed, m_no_cap_restored),
    (c8_awkward_connectivity_stays_closed, m_resize_pads_zero),
    (c9_bad_joint_warns_on_the_locked_instance, m_report_bypassed),
    (c9_bad_joint_warns_on_the_locked_instance, m_no_too_many_group),
    (c10_two_curves_loft_to_one_slab, m_sheet_top_reversed),
    (c10_two_curves_loft_to_one_slab, m_sheet_no_direction_check),
    (c10_two_curves_loft_to_one_slab, m_sheet_radius_not_interpolated),
    (c10_two_curves_loft_to_one_slab, m_sheet_spans_always_one),
    (c11_trunk_with_a_branch_is_one_mesh, m_branch_gets_a_cube),
    (c11_trunk_with_a_branch_is_one_mesh, m_trunk_caps_reversed),
    (c11_trunk_with_a_branch_is_one_mesh, m_trunk_ring_flipped),
    (c11_trunk_with_a_branch_is_one_mesh, m_first_facing_cell),
    (c12_trunk_awkward_branches_warn_and_stay_closed, m_no_locality),
    (c12_trunk_awkward_branches_warn_and_stay_closed, m_no_resolve),
    (c12_trunk_awkward_branches_warn_and_stay_closed, m_odd_ring_allowed),
    (c12_trunk_awkward_branches_warn_and_stay_closed, m_trunk_ignores_pscale),
    (c12_trunk_awkward_branches_warn_and_stay_closed, m_wrap_ignored),
    (c12_trunk_awkward_branches_warn_and_stay_closed, m_wrap_clamped),
    (c13_branch_attaches_where_it_leaves_the_shell, m_no_burial),
]


def main(seed=7):
    global hou
    import hou
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(HDA)
    geo = hou.node("/obj").createNode("geo", "modeler_checks")
    stash = geo.createNode("stash")
    stash.parm("stash").set(fixture(seed))
    strip = geo.createNode("attribdelete", "strip")
    strip.setInput(0, stash)
    strip.parm("ptdel").set("pscale")
    node = geo.createNode("pf_modeler")

    def cook(_asis=False, _nopscale=False, _graph=None, **parms):
        stash.parm("stash").set(_graph if _graph is not None else fixture(seed))
        node.setInput(0, strip if _nopscale else stash)
        node.setParms({"subdivisions": 2, "radius": 1.0, "sheetspans": 0, "wrap": 0.0})
        node.setParms(parms)
        src = stash if _asis else node
        frozen = hou.Geometry()
        frozen.merge(src.geometry())
        return frozen
    cook.node = node

    failures = 0
    t0 = time.time()
    print("pf_modeler - %s (seed %d)\n" % (HDA, seed))
    for check, mutate in REGISTRY:
        ok, detail = check(cook)
        if not ok:
            failures += 1
        print("  %s  %-44s %s" % ("ok  " if ok else "FAIL", check.__name__, detail))
        node.allowEditingOfContents()
        try:
            mutate(node)
        except AssertionError as exc:
            failures += 1
            print("        MUTATION %s NOT APPLIED - %s" % (mutate.__name__, exc))
            node.matchCurrentDefinition()
            continue
        try:
            red, mdetail = check(cook)
        except Exception as exc:
            red, mdetail = False, "%s: %s" % (type(exc).__name__, exc)
        node.matchCurrentDefinition()
        if red:
            failures += 1
            print("        MUTATION %s STAYED GREEN - this check cannot fail: %s" % (mutate.__name__, mdetail))
    print("\n%d failing checks in %.2f s" % (failures, time.time() - t0))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7))
