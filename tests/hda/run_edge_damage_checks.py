"""`pf_edge_damage` checks, against the SHIPPED asset, in a throwaway session.

    hython tests/hda/run_edge_damage_checks.py

Eleven checks, eleven mutations, the pf_ring pattern: every check runs on the
clean asset and then against the ONE edit meant to redden it, and a mutation
that stays green is reported as a failure of the CHECK.

Strokes cannot be scripted, so the mask is driven through `masksource`:
Everywhere for the bulk checks, an upstream attribute for locality, and
Paint-with-no-strokes for the no-damage control.

What these checks CANNOT see:
  * the paint state itself - that a brush stroke lands where the cursor is.
    A human in the viewport is the only oracle for that.
  * how the chips LOOK. C1 measures removed volume, C7 that the seed moves
    them; nothing here judges a chip as stylised or as ugly.
  * the mask blur, the noise type menu and the fractal parms - they are
    passed through to native nodes and cooked at their defaults only.
  * `_*` leakage on the viz branches - `run_attrib_checks.py` sweeps every
    menu value of every asset and owns that.
  * the unit-cube fit. Every fixture is already a unit-ish box, so a
    bypassed `fit` passes (the audit's alternate mutation); C5 only proves
    the transform comes BACK.
  * `cutn` and the VDB round trip - bypassing either still cooks a
    plausible solid on a cube.
"""

import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HDA = os.path.join(REPO, "polyfactory", "otls", "pf_edge_damage.hda").replace("\\", "/")


def open_edges(geo):
    seen = {}
    for pr in geo.prims():
        ids = [v.point().number() for v in pr.vertices()]
        for i in range(len(ids)):
            e = (min(ids[i], ids[i - 1]), max(ids[i], ids[i - 1]))
            seen[e] = seen.get(e, 0) + 1
    return sum(1 for c in seen.values() if c == 1)


def volume(geo):
    """|enclosed volume| over a closed mesh, divergence theorem."""
    total = 0.0
    for pr in geo.prims():
        vs = [v.point().position() for v in pr.vertices()]
        for i in range(1, len(vs) - 1):
            total += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
    return abs(total)


def chipped(geo):
    g = geo.findPrimGroup("pf_chipped")
    return list(g.prims()) if g else None


def prim_area(pr):
    vs = [v.point().position() for v in pr.vertices()]
    return 0.5 * sum(((vs[i] - vs[0]).cross(vs[i + 1] - vs[0])).length()
                     for i in range(1, len(vs) - 1))


def real_chips(geo, eps=1e-5):
    """Chip faces that carry area. A boolean seam on a clean intersection
    leaves a few coincident zero-area faces in the group; those are not
    damage, and counting them as such made an exact-volume identity read as
    a defect."""
    return [pr for pr in (chipped(geo) or []) if prim_area(pr) > eps]


def centroid(pr):
    import hou
    vs = [v.point().position() for v in pr.vertices()]
    return sum(vs, hou.Vector3(0, 0, 0)) / len(vs)


# --------------------------------------------------------------------------
# checks. cook(**parms) -> frozen output of the asset on a unit box.
# --------------------------------------------------------------------------
def c1_damage_everywhere_removes_material(cook, box):
    """Edge wear on a cube at defaults takes ~0.8% of its volume: the edges
    and corners, not the faces. The floor is what a union (the mutation)
    cannot reach; the ceiling says the faces survived."""
    g = cook(masksource=2)
    v, v0, oe = volume(g), volume(box), open_edges(g)
    ok = oe == 0 and 0.3 * v0 < v < 0.999 * v0
    return ok, "volume %.4f of %.4f (want 30..99.9%%), open edges %d" % (v, v0, oe)


def c2_no_strokes_means_no_damage(cook, box):
    """Paint mode with nothing painted must hand the input back untouched:
    the unpainted vertices are put back on the original surface and pushed
    out along its face normal, so the cutter clears it everywhere and the
    intersection is the whole original. Checked on a cube AND on a chunky
    slab (thinnest dim 0.3, comfortably coarser than `detail`), because the
    audit found the additive push 0.09 short at a blurred corner and the
    rest-normal push cancelling to zero across a thin side - the face-normal
    push has to hold on both. A part thinner than `detail` is out of
    contract (see the doc); c10 covers the coarsest in-contract case."""
    # The guarantee is "no material removed" = volume unchanged, on both a
    # cube and a chunky slab. Zero chip faces is additionally required on the
    # cube, whose clean intersection leaves none; the slab's coplanar seam
    # leaves an occasional zero-VOLUME sliver in the group, so it is held to
    # the volume guarantee only.
    out = []
    for name, size, want_zero in ((("cube", (1.0, 1.0, 1.0), True)),
                                  (("slab", (1.0, 0.3, 1.0), False))):
        g = cook(masksource=0, _sizev=size)
        v0 = size[0] * size[1] * size[2]
        dv = abs(volume(g) - v0) / v0
        n = len(real_chips(g))
        if not (dv < 5e-3 and (n == 0 or not want_zero)):
            out.append("%s: volume moved %.2e, %d real chips" % (name, dv, n))
    return not out, "; ".join(out) if out else "cube and slab untouched"


def c3_an_upstream_attribute_localises_the_damage(cook, box):
    """`pf_wear` = 1 on the +X half only: every chip must sit at x > 0. A
    NON-default attribute name, so a hard-coded `pf_damage` would fail."""
    g = cook(masksource=1, maskattrib="pf_wear")
    ch = chipped(g) or []
    # The mask goes 0 -> 1 across one canvas cell (paintres 0.05) at x = 0,
    # so a chip may reach that far past the plane; a mode that ignores the
    # attribute puts chips at x = -0.5.
    wrong = sum(1 for pr in ch if centroid(pr)[0] < -0.06)
    ok = len(ch) > 0 and wrong == 0
    return ok, "%d chipped faces, %d further than a cell into the " \
               "unpainted side (want > 0, 0)" % (len(ch), wrong)


def c4_chips_ship_as_a_group_inside_the_solid(cook, box):
    g = cook(masksource=2)
    ch = chipped(g)
    if ch is None:
        return False, "no pf_chipped group on the output"
    """Every chip face sits inside the box or on its surface - a chip that
    lands exactly in a face plane is a legal sliver, one outside is not."""
    outside = sum(1 for pr in ch if max(abs(c) for c in centroid(pr)) > 0.5 + 1e-4)
    leak = g.findPrimAttrib("name") is not None
    ok = len(ch) > 0 and outside == 0 and not leak
    return ok, "%d chipped faces, %d outside the box (want > 0, 0), vdb " \
               "`name` on the output: %s" % (len(ch), outside, leak)


def c5_the_input_transform_comes_back(cook, box):
    """The work happens in the unit cube; the output must land where the
    input was: a box of size 3 at (5, 2, -1)."""
    g = cook(masksource=2, _size=3.0, _center=(5.0, 2.0, -1.0))
    bb = g.boundingBox()
    c, s = bb.center(), bb.sizevec()
    ok = (max(abs(c[0] - 5.0), abs(c[1] - 2.0), abs(c[2] + 1.0)) < 2e-2
          and 2.5 < max(s) <= 3.0 + 1e-4)
    return ok, "centre (%.3f %.3f %.3f) size %.3f (want 5 2 -1, ~3)" % (
        c[0], c[1], c[2], max(s))


def c6_both_chip_styles_are_wired_and_sound(cook, box):
    a, b = cook(masksource=2, style=0), cook(masksource=2, style=1)
    ok = (len(a.points()) != len(b.points()) and open_edges(a) == 0
          and open_edges(b) == 0)
    return ok, "smooth %d pts, low-poly %d pts (want different), open %d/%d" % (
        len(a.points()), len(b.points()), open_edges(a), open_edges(b))


def c7_the_seed_moves_the_chips(cook, box):
    a, b = cook(masksource=2, seed=0.0), cook(masksource=2, seed=7.0)
    sa = round(sum(abs(c) for p in a.points() for c in p.position()), 4)
    sb = round(sum(abs(c) for p in b.points() for c in p.position()), 4)
    return sa != sb, "position sums %.4f vs %.4f (want different)" % (sa, sb)


def c8_bias_trades_chips_for_surface(cook, box):
    """Lower bias, more removed. Measured: -0.1 leaves ~59%, +0.1 ~99.99%."""
    lo, hi = volume(cook(masksource=2, bias=-0.1)), volume(cook(masksource=2, bias=0.1))
    return lo < hi - 1e-3, "volume at bias -0.1: %.4f, at +0.1: %.4f (want lower first)" % (lo, hi)


def c9_an_open_input_is_refused_with_the_reason(cook, box):
    """The boolean returns nothing for an open mesh. The tool must SAY so:
    a box with one face deleted is an ERROR on the asset node that names
    the open edges (a warning inside a locked asset never surfaces -
    probed), a closed box cooks clean, and Allow Open Input lets the open
    one through without the error."""
    cook(masksource=2, _open=True)
    e_open = " ".join(cook.node.errors())
    cook(masksource=2)
    e_closed = list(cook.node.errors())
    cook(masksource=2, _open=True, allowopen=1)
    e_allowed = " ".join(cook.node.errors())
    ok = ("not closed" in e_open and "4 open edges" in e_open and not e_closed
          and "not closed" not in e_allowed)
    return ok, "open: %s | closed errors %d | allowed: %s" % (
        "refused" if "not closed" in e_open else "SILENT", len(e_closed),
        "let through" if "not closed" not in e_allowed else "still refused")


def c11_edge_wear_is_a_distance_not_a_cell_count(cook, box):
    """Hannes' first real try: Paint Resolution 0.025, everything else at
    default, and NOTHING was cut - the wear was in canvas cells, so a finer
    canvas shrank it below the VDB voxel. The same Edge Wear must remove a
    comparable amount of material on a fine canvas and on the default one."""
    v_fine = 1.0 - volume(cook(masksource=2, paintres=0.025))
    v_def = 1.0 - volume(cook(masksource=2, paintres=0.05))
    ok = v_fine > 0.002 and v_def > 0.002 and 0.4 < v_fine / v_def < 2.5
    return ok, "removed %.4f at 0.025 vs %.4f at 0.05 (want both > 0.002, " \
               "ratio 0.4..2.5)" % (v_fine, v_def)


def c10_the_cutter_never_reduces_to_nothing(cook, box):
    """A percentage of a small cutter went to 0 polygons and the output was
    empty. With the coarsest canvas and the strongest reduction the output
    must still be a closed solid with chips in it."""
    # Measured: 93 chip faces with the 200-polygon floor, 23 without it.
    g = cook(masksource=2, paintres=0.2, lowpolypct=1.0)
    n, oe = len(chipped(g) or []), open_edges(g)
    ok = n >= 60 and oe == 0
    return ok, "%d chip faces, %d open edges (want >= 60, 0)" % (n, oe)


# --------------------------------------------------------------------------
# mutations: one per check, each editing production code inside the asset.
# --------------------------------------------------------------------------
def m_union_instead_of_intersect(net):
    net.node("cut").parm("booleanop").set(0)


def m_push_inverted(net):
    _patch(net, "push", "(1.0 - clamp(f@_damage, 0.0, 1.0))",
           "clamp(f@_damage, 0.0, 1.0)")


def m_attribute_mode_ignored(net):
    _patch(net, "maskinit", "if (mode == 2) d = 1.0;",
           "if (mode >= 1) d = 1.0;")


def m_group_renamed(net):
    net.node("cut").parm("binsidea").set("chipped")


def m_transform_not_restored(net):
    net.node("restore").bypass(True)


def m_style_pinned(net):
    net.node("style").parm("input").setExpression("1")


def m_seed_unwired(net):
    net.node("noise").parm("offset").setExpression("0")


def m_bias_unwired(net):
    net.node("bias").parm("dist").setExpression("0")


def m_no_contract(net):
    net.node("warn").bypass(True)


def m_wear_in_cells(net):
    """The shipped bug: iterations = a constant, so the distance shrinks
    with the cell size."""
    net.node("pull").parm("iterations").setExpression("13")


def m_no_polygon_floor(net):
    net.node("lowpoly").parm("finalcount").setExpression(
        'nprims("../noname") * ch("../lowpolypct") / 100')


def _patch(net, node, old, new):
    p = net.node(node).parm("snippet")
    src = p.eval()
    assert old in src, "mutation target not in %s's VEX: %r" % (node, old)
    p.set(src.replace(old, new))


REGISTRY = [
    (c1_damage_everywhere_removes_material, m_union_instead_of_intersect),
    (c2_no_strokes_means_no_damage, m_push_inverted),
    (c3_an_upstream_attribute_localises_the_damage, m_attribute_mode_ignored),
    (c4_chips_ship_as_a_group_inside_the_solid, m_group_renamed),
    (c5_the_input_transform_comes_back, m_transform_not_restored),
    (c6_both_chip_styles_are_wired_and_sound, m_style_pinned),
    (c7_the_seed_moves_the_chips, m_seed_unwired),
    (c8_bias_trades_chips_for_surface, m_bias_unwired),
    (c9_an_open_input_is_refused_with_the_reason, m_no_contract),
    (c10_the_cutter_never_reduces_to_nothing, m_no_polygon_floor),
    (c11_edge_wear_is_a_distance_not_a_cell_count, m_wear_in_cells),
]

DEFAULTS = {"masksource": 0, "maskattrib": "pf_damage", "chipdepth": 0.07,
            "chipsize": 0.1, "bias": 0.04, "detail": 0.2, "edgewear": 0.1,
            "style": 1, "lowpolypct": 10.0, "smoothsize": 0.25, "seed": 0.0,
            "paintres": 0.05, "viz": 0, "allowopen": 0}


def main():
    import hou
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(HDA)
    geo = hou.node("/obj").createNode("geo", "edge_damage_checks")
    box = geo.createNode("box")
    mark = geo.createNode("attribwrangle")
    mark.parm("snippet").set("f@pf_wear = @P.x > 0;")
    mark.setInput(0, box)
    hole = geo.createNode("blast")           # one face off = an open mesh
    hole.setInput(0, mark)
    hole.parm("group").set("0")
    hole.parm("grouptype").set(4)            # primitives
    node = geo.createNode("pf_edge_damage")

    def cook(_size=1.0, _center=(0.0, 0.0, 0.0), _sizev=(1.0, 1.0, 1.0),
             _open=False, **parms):
        box.parm("scale").set(_size)
        box.parmTuple("t").set(_center)
        box.parmTuple("size").set(_sizev)
        node.setInput(0, hole if _open else mark)
        node.setParms(DEFAULTS)
        node.setParms(parms)
        frozen = hou.Geometry()
        geo = node.geometry()            # None when the asset errors
        if geo is not None:
            frozen.merge(geo)
        return frozen
    cook.node = node

    unit = hou.Geometry()
    box.parm("scale").set(1.0)
    box.parmTuple("t").set((0, 0, 0))
    unit.merge(box.geometry())

    failures = 0
    t0 = time.time()
    print("pf_edge_damage - %s\n" % HDA)
    for check, mutate in REGISTRY:
        ok, detail = check(cook, unit)
        if not ok:
            failures += 1
        print("  %s  %-52s %s" % ("ok  " if ok else "FAIL", check.__name__, detail))

        node.allowEditingOfContents()
        try:
            mutate(node)
            red, mdetail = check(cook, unit)
        except Exception as exc:
            red, mdetail = False, "%s: %s" % (type(exc).__name__, exc)
        node.matchCurrentDefinition()
        if red:
            failures += 1
            print("        MUTATION %s STAYED GREEN - this check cannot "
                  "fail: %s" % (mutate.__name__, mdetail))

    print("\n%d failing checks in %.2f s (checks only; hython boot is on top)"
          % (failures, time.time() - t0))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
