"""`pf_fix_foldover` checks, against the SHIPPED asset, in a throwaway session.

    hython tests/hda/run_fix_foldover_checks.py

Fixture: a 4x4x4-division box with ONE point dragged across its neighbour
so the faces around it fold over - the shape a crossed bevel loop leaves,
made deterministic. Five checks, five mutations, each seen red.

What these checks CANNOT see: a face that is MEANT to oppose its
neighbours (a very sharp crease) - the detector flags it too, and only
Detect Only lets a human decide; the tile that motivated the tool (its
repair is measured in ideas/fix_foldover.md, not here).
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HDA = os.path.join(REPO, "polyfactory", "otls", "pf_fix_foldover.hda").replace("\\", "/")


def open_edges(geo):
    seen = {}
    for pr in geo.prims():
        ids = [v.point().number() for v in pr.vertices()]
        for i in range(len(ids)):
            e = (min(ids[i], ids[i - 1]), max(ids[i], ids[i - 1]))
            seen[e] = seen.get(e, 0) + 1
    return sum(1 for c in seen.values() if c == 1)


def newell(P):
    import hou
    n = hou.Vector3()
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        n += hou.Vector3((a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]),
                         (a[0] - b[0]) * (a[1] + b[1]))
    return n


def inverted(geo):
    """An independent reading of the same property: faces whose Newell
    normal opposes the mean of their point-neighbours'. Shares no code
    with the asset's VEX."""
    import hou
    normals = {p.number(): newell([v.point().position() for v in p.vertices()]) for p in geo.prims()}
    bad = []
    for p in geo.prims():
        acc = hou.Vector3()
        for pt in p.points():
            for q in pt.prims():
                if q.number() != p.number():
                    acc += normals[q.number()].normalized() if normals[q.number()].length() > 0 else hou.Vector3()
        n = normals[p.number()]
        if n.length() > 0 and acc.length() > 0 and n.normalized().dot(acc.normalized()) < 0:
            bad.append(p.number())
    return bad


def group(geo):
    g = geo.findPrimGroup("pf_foldover")
    return sorted(p.number() for p in g.prims()) if g else None


def c1_a_clean_box_has_no_foldover(cook):
    g = cook(fix=0, _fold=False)
    return group(g) == [] and inverted(g) == [], "group %s, independent %s (want both empty)" % (
        group(g), inverted(g))


def c2_detect_finds_exactly_the_folded_faces(cook):
    g = cook(fix=0, _fold=True)
    got, want = group(g), inverted(g)
    return got == want and len(want) > 0, "group %s vs independent %s (want equal, non-empty)" % (got, want)


def c3_detect_only_moves_nothing(cook):
    a, b = cook(fix=0, _fold=True), cook(fix=0, _fold=True, _asis=True)
    same = len(a.points()) == len(b.points()) and all(
        (p.position() - q.position()).length() < 1e-9 for p, q in zip(a.points(), b.points()))
    return same, "positions identical to the input: %s" % same


def c4_reverse_fixes_facing_only(cook):
    g = cook(fix=1, _fold=True)
    n_in = len(cook(fix=0, _fold=True).points())
    return inverted(g) == [] and len(g.points()) == n_in, "inverted after %s, points %d of %d" % (
        inverted(g), len(g.points()), n_in)


def c5_collapse_removes_the_fold_and_stays_closed(cook):
    g = cook(fix=2, _fold=True)
    n_in = len(cook(fix=0, _fold=True).points())
    ok = inverted(g) == [] and open_edges(g) == 0 and len(g.points()) < n_in and g.findPrimAttrib("_c") is None
    return ok, "inverted %s, open edges %d, points %d of %d (want none, 0, fewer), _c leaked %s" % (
        inverted(g), open_edges(g), len(g.points()), n_in, g.findPrimAttrib("_c") is not None)


def m_sign_flipped(net):
    _patch(net, "detect", "dot(n, normalize(acc)) < 0", "dot(n, normalize(acc)) > 0")


def m_group_always_on(net):
    _patch(net, "detect", "setprimgroup(0, \"pf_foldover\", @primnum, folded);",
           "setprimgroup(0, \"pf_foldover\", @primnum, 1);")


def m_detect_moves_points(net):
    _patch(net, "detect", "v@_c = c / len(primpoints(0, @primnum));",
           "v@_c = c / len(primpoints(0, @primnum)); setpointattrib(0, \"P\", primpoints(0, @primnum)[0], v@_c);")


def m_reverse_unwired(net):
    net.node("reverse").parm("group").set("")


def m_no_fuse(net):
    net.node("fuse").bypass(True)


def _patch(net, node, old, new):
    p = net.node(node).parm("snippet")
    src = p.eval()
    assert old in src, "mutation target not in %s's VEX: %r" % (node, old)
    p.set(src.replace(old, new))


REGISTRY = [
    (c1_a_clean_box_has_no_foldover, m_group_always_on),
    (c2_detect_finds_exactly_the_folded_faces, m_sign_flipped),
    (c3_detect_only_moves_nothing, m_detect_moves_points),
    (c4_reverse_fixes_facing_only, m_reverse_unwired),
    (c5_collapse_removes_the_fold_and_stays_closed, m_no_fuse),
]


def main():
    import hou
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(HDA)
    geo = hou.node("/obj").createNode("geo", "foldover_checks")
    box = geo.createNode("box")
    box.parm("type").set(1)                       # polymesh (PROBED: menu poly/polymesh/...)
    box.parm("dodivs").set(1)
    for ax in "xyz":
        box.parm("divs" + ax).set(4)
    fold = geo.createNode("attribwrangle", "fold")
    fold.setInput(0, box)
    # swap the two DIAGONAL points of one top-face quad: that quad comes out
    # MIRRORED - its normal opposes every neighbour - which is what a
    # crossed bevel loop leaves (prims 321/614 on the tile). PROBED: swapping
    # two ADJACENT points only makes bowties, whose Newell normal cancels to
    # ~0 and is never "opposed"; dragging a single point does the same.
    fold.parm("snippet").set(
        'if (chi("swap")) {\n'
        '    if (@ptnum == chi("pa")) @P = point(0, "P", chi("pb"));\n'
        '    if (@ptnum == chi("pb")) @P = point(0, "P", chi("pa"));\n'
        '}')
    for name in ("pa", "pb", "swap"):
        fold.addSpareParmTuple(hou.IntParmTemplate(name, name, 1, (0,)))
    node = geo.createNode("pf_fix_foldover")
    node.setInput(0, fold)

    # two adjacent INTERIOR top-face points (PROBED: 4 divisions put the
    # grid at +-0.5 and +-1/6, so there is no point at 0)
    def at(x, z):
        return min(box.geometry().points(),
                   key=lambda p: (p.position() - hou.Vector3(x, 0.5, z)).length()).number()
    fold.parm("pa").set(at(-1.0 / 6, -1.0 / 6))
    fold.parm("pb").set(at(1.0 / 6, 1.0 / 6))
    assert fold.parm("pa").eval() != fold.parm("pb").eval()

    def cook(_fold=True, _asis=False, **parms):
        fold.parm("swap").set(1 if _fold else 0)
        node.setParms({"fix": 2, "snapdist": 1e-5})
        node.setParms(parms)
        src = fold if _asis else node
        frozen = hou.Geometry()
        frozen.merge(src.geometry())
        return frozen

    failures = 0
    t0 = time.time()
    print("pf_fix_foldover - %s\n" % HDA)
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
