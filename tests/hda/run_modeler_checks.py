"""`pf_modeler` checks, against the SHIPPED asset, in a throwaway session.

    hython tests/hda/run_modeler_checks.py [seed]

Fixture: a seeded random tree of spheres (every sphere after the first
hangs off an earlier one, degrees up to six), a closed three-sphere loop,
a straight chain, and one isolated sphere - random positions and radii.
Ten checks, twelve mutations, each seen red.

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
    ok = not leaked and names == ["P", "pf_node", "pf_sheet"] and a.dataType() == hou.attribData.Int and -1 in vals and max(vals) >= 0
    return ok, "leaked %s, attributes %s (want P, pf_node, pf_sheet only), pf_node %s values %s" % (
        leaked, names, a and a.dataType(), sorted(vals)[:4])


def c6_radius_parm_used_without_pscale(cook):
    r = 0.07
    g, src = cook(subdivisions=0, radius=r, _nopscale=True), cook(_asis=True)
    outpts = list(g.points())
    short = [sp.number() for sp in src.points() if sum(
        1 for p in outpts if abs((p.position() - sp.position()).length() - r * 3 ** 0.5) < 1e-4) != 8]
    return not short, "spheres without 8 corners at Radius %s: %s (want none)" % (r, short)


def graph(spheres, links, sheets=()):
    """spheres: [(pos, r)], links: [[i, j, ...]] open polylines; sheets:
    pf_sheet value per polyline (0 = a connection)."""
    g = hou.Geometry()
    g.addAttrib(hou.attribType.Point, "pscale", 0.0)
    if sheets:
        g.addAttrib(hou.attribType.Prim, "pf_sheet", 0)
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
    return g


def c10_two_curves_loft_to_one_slab(cook):
    """Two parallel five-point curves marked pf_sheet 1 (radius 0.1 on one,
    0.05 on the other): one closed, consistently wound, all-quad shell,
    every face pf_sheet 1, no cubes for the curve points, Houdini's own
    prim normal pointing away from the slab's centre on every face."""
    a = [((0.5 * i, 0, 0), 0.1) for i in range(5)]
    b = [((0.5 * i, 0, 1.2), 0.05) for i in range(5)]
    g = cook(subdivisions=0, _graph=graph(a + b, [[0, 1, 2, 3, 4], [5, 6, 7, 8, 9]], (1, 1)))
    de = directed_edges(g)
    bad = sum(1 for c in de.values() if c != 1) + sum(1 for e in de if (e[1], e[0]) not in de)
    nonquad = sum(1 for p in g.prims() if len(p.vertices()) != 4)
    tags = set(p.attribValue("pf_sheet") for p in g.prims())
    centre = sum((p.position() for p in g.points()), hou.Vector3()) / len(g.points())
    inward = sum(1 for p in g.prims() if p.normal().dot(
        sum((v.point().position() for v in p.vertices()), hou.Vector3()) / 4 - centre) <= 0)
    pieces = len(set(components(g).values()))
    ok = bad == 0 and nonquad == 0 and tags == {1} and inward == 0 and pieces == 1 and len(g.prims()) > 0
    return ok, "%d bad edges, %d non-quads, pf_sheet %s, %d inward, %d pieces (want 0, 0, {1}, 0, 1)" % (
        bad, nonquad, sorted(tags), inward, pieces)


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


def m_sheet_top_reversed(net):
    _patch(net, "sheet", 'addprim(0, "poly", top[a], top[d], top[c], top[b])',
           'addprim(0, "poly", top[a], top[b], top[c], top[d])')


def m_no_cleanup(net):
    net.node("cleanup").bypass(True)


def m_radius_hardcoded(net):
    _patch(net, "cage", 'chf("../radius")', "0.1")


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
    (c7_joints_do_not_self_intersect, m_worst_twist),
    (c8_awkward_connectivity_stays_closed, m_no_cap_restored),
    (c8_awkward_connectivity_stays_closed, m_resize_pads_zero),
    (c9_bad_joint_warns_on_the_locked_instance, m_report_bypassed),
    (c9_bad_joint_warns_on_the_locked_instance, m_no_too_many_group),
    (c10_two_curves_loft_to_one_slab, m_sheet_top_reversed),
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
        node.setParms({"subdivisions": 2, "radius": 0.1})
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
