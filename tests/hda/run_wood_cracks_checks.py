"""`pf_wood_cracks` checks, against the SHIPPED asset, in a throwaway session.

    hython tests/hda/run_wood_cracks_checks.py

Fixture: a closed 2 x 0.3 x 1 board (grain along X by the longest axis).
Eight checks, eight mutations, each seen red. What they CANNOT see: how a
crack LOOKS (lens vs slot), the log and plank props that motivated the
tool (rendered by a human, ideas/wood_cracks.md), and the boolean's own
robustness on a mesh that is not a closed solid - that is the input
contract, the same as pf_edge_damage's.
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HDA = os.path.join(REPO, "polyfactory", "otls", "pf_wood_cracks.hda").replace("\\", "/")
BOARD = (2.0, 0.3, 1.0)
VOL = BOARD[0] * BOARD[1] * BOARD[2]


def open_edges(geo):
    seen = {}
    for pr in geo.prims():
        ids = [v.point().number() for v in pr.vertices()]
        for i in range(len(ids)):
            e = (min(ids[i], ids[i - 1]), max(ids[i], ids[i - 1]))
            seen[e] = seen.get(e, 0) + 1
    return sum(1 for c in seen.values() if c == 1)


def volume(geo):
    t = 0.0
    for pr in geo.prims():
        vs = [v.point().position() for v in pr.vertices()]
        for i in range(1, len(vs) - 1):
            t += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
    return abs(t)


def cracks(geo):
    g = geo.findPrimGroup("pf_crack")
    return list(g.prims()) if g else []


def crack_pieces(geo):
    """Connected clusters of crack faces = individual cracks, by shared points."""
    import hou
    faces = {p.number(): set(pt.number() for pt in p.points()) for p in cracks(geo)}
    seen, pieces = set(), []
    for f in faces:
        if f in seen:
            continue
        stack, piece = [f], set()
        while stack:
            x = stack.pop()
            if x in piece:
                continue
            piece.add(x)
            stack += [y for y in faces if y not in piece and faces[y] & faces[x]]
        seen |= piece
        pieces.append(piece)
    return pieces


def extent(geo, prims):
    """Bounding box of a set of prims. Seeded from the first point: a bare
    hou.BoundingBox() is a zero box AT THE ORIGIN and enlargeToContain
    keeps it, so every footprint silently included (0,0,0) - measured."""
    import hou
    pts = [pt.position() for n in prims for pt in geo.prim(n).points()]
    bb = hou.BoundingBox(pts[0][0], pts[0][1], pts[0][2], pts[0][0], pts[0][1], pts[0][2])
    for p in pts[1:]:
        bb.enlargeToContain(p)
    return bb


def c1_cracks_remove_material_and_stay_closed(cook):
    g = cook()
    v, oe, n = volume(g), open_edges(g), len(cracks(g))
    ok = oe == 0 and 0.5 * VOL < v < VOL - 1e-4 and n > 0
    return ok, "volume %.4f of %.4f (want less, > half), open edges %d, crack faces %d" % (v, VOL, oe, n)


def c2_count_is_the_number_of_cracks(cook):
    """Small cracks, so none touch and merge into one piece."""
    small = dict(endbias=0.0, length=0.08, lengthvar=0.0, width=0.01, widthvar=0.0)
    a, b = len(crack_pieces(cook(count=3, **small))), len(crack_pieces(cook(count=9, **small)))
    return a == 3 and b == 9, "pieces at count 3: %d, at 9: %d (want 3, 9)" % (a, b)


def c3_cracks_run_along_the_grain(cook):
    """Every crack's footprint is longer along the grain than across it, on
    BOTH the longest-axis default (X here) and an explicit Z."""
    bad = []
    # small, so touching cracks do not merge into one piece; SHALLOW, so
    # on a side face the crack's depth (which runs across the board) cannot
    # rival its length
    # ...and kept OFF the end faces, whose normal IS the grain: there the
    # tool runs the crack across the end grain by design, so it would
    # (rightly) fail an along-the-grain test
    small = dict(endbias=0.0, anglejitter=0.0, length=0.08, lengthvar=0.0,
                 width=0.01, widthvar=0.0, depth=0.02)
    for axis, along, side_mask in (("longest", 0, "pf_side_x"), ("z", 2, "pf_side_z")):
        g = cook(grainaxis={"longest": 3, "z": 2}[axis], maskattrib=side_mask, **small)
        for piece in crack_pieces(g):
            bb = extent(g, piece)
            half = BOARD[along] / 2.0
            if bb.minvec()[along] < -half + 1e-3 or bb.maxvec()[along] > half - 1e-3:
                continue          # runs off the end and is truncated by it - legitimate
            s = bb.sizevec()
            others = [s[i] for i in range(3) if i != along]
            if not s[along] > 2.0 * max(others):
                bad.append("%s: %s (want the %s axis longest by 2x)" % (
                    axis, [round(v, 3) for v in s], "xyz"[along]))
    return not bad, "%d cracks off-grain%s" % (len(bad), (": " + bad[0]) if bad else "")


def c4_end_bias_puts_cracks_on_the_ends(cook):
    """At End Bias 1 EVERY crack reaches an end face (|x| = 1); at 0 fewer
    do (a middle crack can still reach an end by chance, so "none" is not
    the claim)."""
    def on_end(g):
        return sum(1 for piece in crack_pieces(g) if max(abs(extent(g, piece).minvec()[0]), abs(extent(g, piece).maxvec()[0])) > 0.999)
    small = dict(length=0.08, lengthvar=0.0, width=0.01, widthvar=0.0)
    g1, g0 = cook(endbias=1.0, **small), cook(endbias=0.0, **small)
    n1, t1, n0, t0 = on_end(g1), len(crack_pieces(g1)), on_end(g0), len(crack_pieces(g0))
    return n1 == t1 and t1 > 0 and n0 < t0, "on an end: %d of %d at bias 1 (want all), %d of %d at bias 0 (want fewer)" % (n1, t1, n0, t0)


def c5_groups_partition_and_nothing_internal_leaks(cook):
    g = cook()
    o = set(p.number() for p in g.findPrimGroup("pf_original").prims()) if g.findPrimGroup("pf_original") else set()
    c = set(p.number() for p in cracks(g))
    seam = g.findEdgeGroup("pf_seam")
    # Nothing of the tool's own rides out: the fixture box has only P on its
    # points, so that is all the output may have (orient / scale / the
    # scatter's source prim all live on the cutter side).
    leaks = [a.name() for cls in (g.pointAttribs(), g.primAttribs(), g.vertexAttribs(), g.globalAttribs()) for a in cls if a.name().startswith("_")]
    extra = sorted(a.name() for a in g.pointAttribs() if a.name() != "P")
    ok = (o and c and not (o & c) and (o | c) == set(range(len(g.prims()))) and seam
          and len(seam.edges()) > 0 and not leaks and not extra)
    return ok, "original %d + crack %d of %d, seam edges %d, leaks %s, extra point attribs %s" % (
        len(o), len(c), len(g.prims()), len(seam.edges()) if seam else 0, leaks, extra)


def c6_a_density_attribute_gates_where_cracks_land(cook):
    """`pf_where` = 1 on the +X half only: every crack's CENTRE sits at
    x > 0 (a crack centred just past the gate may still reach back over
    it; a gate that is ignored puts centres at x = -1)."""
    g = cook(maskattrib="pf_where", endbias=0.0, length=0.08, lengthvar=0.0)
    pieces = crack_pieces(g)
    centres = sorted(round(extent(g, piece).center()[0], 3) for piece in pieces)
    wrong = sum(1 for c in centres if c < -0.01)
    return len(pieces) > 0 and wrong == 0, "%d cracks, %d on the ungated side (want > 0, 0); centres x %s" % (
        len(pieces), wrong, centres)


def c7_zero_cracks_hands_the_board_back(cook):
    g = cook(count=0)
    return abs(volume(g) - VOL) < 1e-6 and open_edges(g) == 0 and not cracks(g), "volume %.6f, open %d, crack faces %d" % (
        volume(g), open_edges(g), len(cracks(g)))


def c8_a_cut_that_would_destroy_the_mesh_is_refused(cook):
    """On 8-bitBot's self-intersecting log one wedge collapsed the whole
    boolean. The tool cuts one crack at a time and refuses any cut that
    halves the volume. Deterministic stand-in for a failing boolean: an
    INSIDE-OUT board - every subtract goes wrong, so every cut must be
    refused, the board must come back whole, and the count must say so."""
    g = cook(_inverted=True)
    skipped = g.attribValue("pf_cracks_skipped") if g.findGlobalAttrib("pf_cracks_skipped") else None
    ok = abs(volume(g) - VOL) < 1e-4 and open_edges(g) == 0 and skipped == 12 and not cracks(g)
    return ok, "volume %.4f of %.4f, open %d, skipped %s of 12, crack faces %d" % (
        volume(g), VOL, open_edges(g), skipped, len(cracks(g)))


def m_guard_always_cuts(net):
    net.node("guard").parm("input").setExpression("1")


def m_union(net):
    net.node("cut").parm("booleanop").set(0)


def m_count_unwired(net):
    net.node("scatter").parm("npts").setExpression("6")


def m_grain_pinned(net):
    _patch(net, "grain", "vector g = 0; g[axis] = 1.0;", "vector g = {1, 0, 0};")


def m_end_bias_ignored(net):
    _patch(net, "place", 'if (r1 < chf("../endbias")) {', "if (0) {")


def m_no_cleanup(net):
    net.node("cleanup").bypass(True)


def m_density_ignored(net):
    net.node("scatter").parm("usedensityattrib").setExpression("0")


def m_zero_cuts_anyway(net):
    net.node("scatter").parm("npts").setExpression('max(ch("../count"), 1)')


def _patch(net, node, old, new):
    p = net.node(node).parm("snippet")
    src = p.eval()
    assert old in src, "mutation target not in %s's VEX: %r" % (node, old)
    p.set(src.replace(old, new))


REGISTRY = [
    (c1_cracks_remove_material_and_stay_closed, m_union),
    (c2_count_is_the_number_of_cracks, m_count_unwired),
    (c3_cracks_run_along_the_grain, m_grain_pinned),
    (c4_end_bias_puts_cracks_on_the_ends, m_end_bias_ignored),
    (c5_groups_partition_and_nothing_internal_leaks, m_no_cleanup),
    (c6_a_density_attribute_gates_where_cracks_land, m_density_ignored),
    (c7_zero_cracks_hands_the_board_back, m_zero_cuts_anyway),
    (c8_a_cut_that_would_destroy_the_mesh_is_refused, m_guard_always_cuts),
]

DEFAULTS = {"count": 12, "seed": 0.0, "grainaxis": 3, "endbias": 0.5, "length": 0.35, "lengthvar": 0.4,
            "width": 0.03, "widthvar": 0.4, "depth": 0.06, "anglejitter": 6.0, "maskattrib": "", "segments": 8}


def main():
    import hou
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(HDA)
    geo = hou.node("/obj").createNode("geo", "wood_cracks_checks")
    box = geo.createNode("box")
    box.parmTuple("size").set(BOARD)
    box.parm("type").set(1)                    # polymesh with divisions, so a
    box.parm("dodivs").set(1)                  # point mask is sharp, not one
    for ax, d in zip("xyz", (8, 2, 4)):        # ramp across a whole face
        box.parm("divs" + ax).set(d)
    mark = geo.createNode("attribwrangle")
    mark.setInput(0, box)
    mark.parm("class").set("primitive")        # a PRIM mask is sharp per cell;
    mark.parm("snippet").set(                  # a point mask ramps across each cell
        "f@pf_where = @P.x > 0.1;\n"
        "vector n = prim_normal(0, @primnum, 0.5, 0.5);\n"
        "f@pf_side_x = abs(n.x) < 0.5;          // faces that are not end grain for grain X\n"
        "f@pf_side_z = abs(n.z) < 0.5;          // ...and for grain Z\n")
    flip = geo.createNode("reverse")           # an inside-out board: every boolean goes wrong
    flip.setInput(0, mark)
    node = geo.createNode("pf_wood_cracks")
    node.setInput(0, mark)

    def cook(_inverted=False, **parms):
        node.setInput(0, flip if _inverted else mark)
        node.setParms(DEFAULTS)
        node.setParms(parms)
        frozen = hou.Geometry()
        g = node.geometry()
        if g is not None:
            frozen.merge(g)
        return frozen

    failures = 0
    t0 = time.time()
    print("pf_wood_cracks - %s\n" % HDA)
    for check, mutate in REGISTRY:
        ok, detail = check(cook)
        if not ok:
            failures += 1
        print("  %s  %-52s %s" % ("ok  " if ok else "FAIL", check.__name__, detail))
        node.allowEditingOfContents()
        try:
            mutate(node)
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
    sys.exit(main())
