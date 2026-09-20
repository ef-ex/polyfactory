"""`pf_stylized_rock` checks, against the SHIPPED asset, in a throwaway session.

    hython tests/hda/run_stylized_rock_checks.py [seed]

Fixture: the three built-in bases and a wired pentagonal prism, over a
handful of seeds drawn from the run seed. Twelve checks, twenty mutations,
each seen red.

What these checks CANNOT see: whether a rock LOOKS like a rock (Hannes'
viewport, and ideas/rocks.md §6); that a wired OPEN mesh is garbage in
(it ships off-contract with no warning); Flat Bottom 0.5 on a rock the cuts
already thinned to ~0.09 (a 4-prim wedge, the artist's own call); `fit`'s
per-axis normalisation (the fixtures are near-uniform); the bevel's shape beyond "it
added faces" (a round fillet is not planar - c2 runs bevel 0); the cusp
angle (shading only); UVs (there are none, by design).
"""

import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HDA = os.path.join(REPO, "polyfactory", "otls", "pf_stylized_rock.hda").replace("\\", "/")


def directed_edges(geo):
    seen = {}
    for pr in geo.prims():
        ids = [v.point().number() for v in pr.vertices()]
        for i in range(len(ids)):
            e = (ids[i - 1], ids[i])
            seen[e] = seen.get(e, 0) + 1
    return seen


def face_normal(pr):
    pts = [v.point().position() for v in pr.vertices()]
    n = hou.Vector3()
    for i in range(len(pts)):  # Newell
        a, b = pts[i], pts[(i + 1) % len(pts)]
        n += hou.Vector3((a[1] - b[1]) * (a[2] + b[2]), (a[2] - b[2]) * (a[0] + b[0]), (a[0] - b[0]) * (a[1] + b[1]))
    return n.normalized() if n.length() > 0 else n


def volume(geo):
    v = 0.0
    for pr in geo.prims():
        pts = [x.point().position() for x in pr.vertices()]
        for i in range(1, len(pts) - 1):
            v += pts[0].dot(pts[i].cross(pts[i + 1]))
    return abs(v) / 6.0


def c1_closed_and_consistently_wound(cook, seeds):
    bad = []
    for shape in (0, 1, 2, 3):
        for s in seeds:
            de = directed_edges(cook(shape=shape, seed=s, flatbottom=0.1 * (s % 2)))
            twice = sum(1 for c in de.values() if c != 1)
            unmatched = sum(1 for e in de if (e[1], e[0]) not in de)
            if twice or unmatched:
                bad.append((shape, s, twice, unmatched))
    return not bad, "(shape, seed, edges used twice, edges without reverse): %s (want none)" % bad


def c2_every_face_is_flat(cook, seeds):
    worst = 0.0
    for shape in (0, 1, 2):
        g = cook(shape=shape, seed=seeds[0])
        for pr in g.prims():
            n = face_normal(pr)
            pts = [v.point().position() for v in pr.vertices()]
            d = [n.dot(p - pts[0]) for p in pts]
            worst = max(worst, max(d) - min(d))
    return worst < 1e-5, "worst out-of-plane spread %.2e (want < 1e-5 - the faces ARE the look)" % worst


def c3_cuts_remove_material_and_seed_matters(cook, seeds):
    base = volume(cook(cuts=0, chips=0))
    vols = [volume(cook(seed=s)) for s in seeds]
    outs = [tuple(round(x, 5) for p in cook(seed=s).points() for x in p.position()) for s in seeds]
    distinct = len(set(outs))
    ok = all(v < base * 0.9 for v in vols) and distinct == len(seeds)
    return ok, "base volume %.4f, cut volumes %s (want all < 90%%), %d distinct rocks from %d seeds" % (
        base, ["%.4f" % v for v in vols], distinct, len(seeds))


def c4_output_contract(cook, seeds):
    size = (1.3, 0.6, 0.9)
    g = cook(seed=seeds[0], size=size, bevel=0.02)
    bb = g.boundingBox()
    mn, mx = bb.minvec(), bb.maxvec()
    leaked = [a.name() for cls in (g.pointAttribs(), g.primAttribs(), g.vertexAttribs(), g.globalAttribs())
              for a in cls if a.name().startswith("_")]
    leaked += [x.name() for x in list(g.pointGroups()) + list(g.primGroups()) + list(g.edgeGroups())
               if x.name().startswith("_")]
    names = sorted(a.name() for cls in (g.pointAttribs(), g.primAttribs(), g.vertexAttribs(), g.globalAttribs())
                   for a in cls)
    want = [-size[0] / 2, 0.0, -size[2] / 2, size[0] / 2, size[1], size[2] / 2]
    got = [mn[0], mn[1], mn[2], mx[0], mx[1], mx[2]]
    ok = all(abs(a - b) < 1e-4 for a, b in zip(want, got)) and not leaked and names == ["N", "P"]
    return ok, "bbox %s (want %s), leaked %s, attributes %s (want N, P)" % (
        ["%.4f" % x for x in got], want, leaked, names)


def c5_flat_bottom_is_one_horizontal_face_on_the_ground(cook, seeds):
    bad = []
    for s in seeds:
        g = cook(shape=1, seed=s, flatbottom=0.2)   # icosphere: a vertex at the pole, no face on y=0
        floor = [pr for pr in g.prims() if all(abs(v.point().position()[1]) < 1e-5 for v in pr.vertices())]
        g0 = cook(shape=1, seed=s, flatbottom=0.0)
        floor0 = [pr for pr in g0.prims() if all(abs(v.point().position()[1]) < 1e-5 for v in pr.vertices())]
        if len(floor) != 1 or len(floor0) != 0:
            bad.append((s, len(floor), len(floor0)))
    return not bad, "(seed, faces on y=0 with Flat Bottom, without): %s (want 1 and 0)" % bad


def c6_no_setting_collapses_the_rock(cook, seeds):
    # Read before `place`, which would stretch even a sliver back to Size.
    # The floor is 0.25 along each CUT direction, so an axis-aligned side can
    # be less: AUDITED over 480 worst-case rocks on all bases, thinnest 0.091.
    bad = []
    for shape in (0, 1, 2):
        for s in seeds:
            for var in (1.0, 0.0):
                cook(shape=shape, seed=s, cuts=64, cutdepth=0.5, cutvar=var, chips=200, chipdepth=0.5, chipvar=var)
                g = cook.node.node("bevel_sw").geometry()
                side = min(g.boundingBox().sizevec()) if len(g.prims()) else 0.0
                if len(g.prims()) < 8 or side < 0.08:
                    bad.append((shape, s, var, len(g.prims()), round(side, 3)))
    return not bad, "(shape, seed, var, prims, thinnest side before Size) after 64 half-depth cuts + 200 chips: %s (want >= 8 prims and >= 0.08)" % bad


def c7_wired_input_replaces_the_base(cook, seeds):
    g = cook(shape=3, cuts=0, chips=0)
    sides = sorted(len(pr.vertices()) for pr in g.prims())
    return sides == [4, 4, 4, 4, 4, 5, 5], "wired pentagonal prism, no cuts: face sizes %s (want 5 quads + 2 pentagons)" % sides


def c8_bevel_adds_faces_only_when_asked(cook, seeds):
    n0 = len(cook(seed=seeds[0]).prims())
    n1 = len(cook(seed=seeds[0], bevel=0.02).prims())
    return n1 > n0 * 2, "prims %d without bevel, %d with (want more than double)" % (n0, n1)


def c9_chip_directions_cover_the_sphere(cook, seeds):
    # rand(seed) cast to vector2 gives (r, r), which puts every direction on
    # ONE spiral from pole to pole. Every cut-face normal would sit on it.
    # The spiral is computed by VEX itself, not guessed: 4000 points at
    # sample_direction_uniform((r, r)) in this session.
    geo = cook.node.parent()
    if geo.node("spiral") is None:
        pts = geo.createNode("line", "spiral_pts")
        pts.parm("points").set(4000)
        w = geo.createNode("attribwrangle", "spiral")
        w.setInput(0, pts)
        w.parm("snippet").set("float r = @ptnum / 4000.0; @P = sample_direction_uniform(set(r, r));")
    spiral = [p.position() for p in geo.node("spiral").geometry().points()]
    # Read the rock BEFORE `place`: that stretch depends on the post-cut bbox
    # and turns every normal by a different amount per cook. Before it, a cut
    # face's normal is exactly +-d.
    def before_place(**p):
        cook(**p)
        f = hou.Geometry()
        f.merge(cook.node.node("bevel_sw").geometry())
        return f
    base_n = [face_normal(pr) for pr in before_place(shape=1, cuts=0, chips=0).prims()]
    g = before_place(shape=1, seed=seeds[0], cuts=40, chips=0, cutdepth=0.15)
    on = 0
    # a cut face is one whose normal is not one of the icosphere's own (a
    # clipped icosphere triangle is an n-gon too, so vertex count cannot tell)
    faces = [pr for pr in g.prims() if min((face_normal(pr) - b).length() for b in base_n) > 1e-3]
    for pr in faces:
        n = face_normal(pr)
        # spiral samples are ~1.5e-3 apart; a random direction lands within
        # 5e-3 of the curve well under 1 % of the time
        if min(min((n - s).length(), (n + s).length()) for s in spiral) < 5e-3:
            on += 1
    return faces and on < len(faces) * 0.5, "%d of %d cut faces have their normal on the (r, r) spiral (want under half)" % (
        on, len(faces))


def c10_chips_and_depth_parms_change_the_rock(cook, seeds):
    def key(**p):
        return tuple(round(x, 5) for pt in cook(seed=seeds[0], **p).points() for x in pt.position())
    pairs = {"chips 0 vs 30": (key(chips=0), key(chips=30)),
             "cutdepth 0.1 vs 0.3": (key(cutdepth=0.1), key(cutdepth=0.3)),
             "cutvar 0 vs 0.6": (key(cutvar=0.0), key(cutvar=0.6)),
             "chipdepth 0.02 vs 0.08": (key(chipdepth=0.02), key(chipdepth=0.08)),
             "chipvar 0 vs 0.6": (key(chipvar=0.0), key(chipvar=0.6))}
    same = [k for k, (x, y) in pairs.items() if x == y]
    return not same, "settings that made NO difference: %s (want none)" % same


def c11_same_settings_same_rock(cook, seeds):
    # two forced cooks, on two different frames (a rock must not change when
    # the artist scrubs)
    hou.setFrame(1)
    a = [tuple(p.position()) for p in cook(seed=seeds[1], _force=True).points()]
    hou.setFrame(37)
    b = [tuple(p.position()) for p in cook(seed=seeds[1], _force=True).points()]
    hou.setFrame(1)
    return a == b, "two forced cooks of the same settings on frames 1 and 37 %s" % ("are bit-identical" if a == b else "DIFFER")


def c12_wired_attributes_pass_but_scratch_groups_do_not(cook, seeds):
    g = cook(shape=4, cuts=4, chips=4)
    pt = sorted(a.name() for a in g.pointAttribs())
    grps = sorted(x.name() for x in g.pointGroups())
    ok = pt == ["Cd", "P"] and grps == ["pf_keep"]
    return ok, "point attributes %s (want Cd, P), point groups %s (want pf_keep only - `_vg` is scratch)" % (pt, grps)


def _patch(net, node, old, new):
    p = net.node(node).parm("snippet")
    src = p.eval()
    assert old in src, "mutation target not in %s's VEX: %r" % (node, old)
    p.set(src.replace(old, new))


def m_no_fill(net):
    net.node("cuts_clip").parm("dofill").set(0)


def m_snap_bends_neighbours(net):
    net.node("cuts_clip").parm("snaptol").set(0.2)


def m_zero_depth(net):
    _patch(net, "cuts_plane", "depth > 0.0 ? m - depth : m + 1.0", "m + 1.0")
    _patch(net, "chips_plane", "depth > 0.0 ? m - depth : m + 1.0", "m + 1.0")


def m_seed_ignored(net):
    _patch(net, "cuts_plane", 'chf("../seed") * 0.7919', "0.0")
    _patch(net, "chips_plane", 'chf("../seed") * 0.7919', "0.0")


def m_no_cleanup(net):
    net.node("cleanup").bypass(True)


def m_no_placement(net):
    net.node("place").parm("doscale").set(0)


def m_floor_never(net):
    net.node("floor_sw").parm("input").deleteAllKeyframes()
    net.node("floor_sw").parm("input").set(0)


def m_no_guard(net):
    for w in ("cuts_plane", "chips_plane"):
        _patch(net, w, "depth = min(depth, (m - lo) - 0.25);", "")


def m_input_ignored(net):
    net.node("base_sw").parm("input").deleteAllKeyframes()
    net.node("base_sw").parm("input").set(0)


def m_bevel_never(net):
    net.node("bevel_sw").parm("input").deleteAllKeyframes()
    net.node("bevel_sw").parm("input").set(0)


def m_chips_loop_dead(net):
    net.node("chips_end").parm("iterations").deleteAllKeyframes()
    net.node("chips_end").parm("iterations").set(0)


def m_cutdepth_hardcoded(net):
    _patch(net, "cuts_plane", 'chf("../cutdepth")', "0.3")


def m_variation_ignored(net):
    _patch(net, "cuts_plane", "fit01(rand(seed + 0.5), 1.0 - var, 1.0)", "1.0")


def m_chip_variation_ignored(net):
    _patch(net, "chips_plane", "fit01(rand(seed + 0.5), 1.0 - var, 1.0)", "1.0")


def m_frame_dependent(net):
    _patch(net, "cuts_plane", 'float seed = chf("../seed") * 0.7919', 'float seed = @Frame * 0.01 + chf("../seed") * 0.7919')


def m_chipdepth_hardcoded(net):
    _patch(net, "chips_plane", 'chf("../chipdepth")', "0.08")


def m_nondeterministic(net):
    _patch(net, "cuts_plane", 'float seed = chf("../seed") * 0.7919', 'float seed = nrandom() + chf("../seed") * 0.7919')


def m_no_group_sweep(net):
    net.node("cleanup_grp").bypass(True)


def m_spiral_directions(net):
    _patch(net, "cuts_plane", "vector2 u = rand(seed);", "vector2 u = vector2(float(rand(seed)));")


REGISTRY = [
    (c1_closed_and_consistently_wound, m_no_fill),
    (c2_every_face_is_flat, m_snap_bends_neighbours),
    (c3_cuts_remove_material_and_seed_matters, m_zero_depth),
    (c3_cuts_remove_material_and_seed_matters, m_seed_ignored),
    (c4_output_contract, m_no_cleanup),
    (c4_output_contract, m_no_placement),
    (c5_flat_bottom_is_one_horizontal_face_on_the_ground, m_floor_never),
    (c6_no_setting_collapses_the_rock, m_no_guard),
    (c7_wired_input_replaces_the_base, m_input_ignored),
    (c8_bevel_adds_faces_only_when_asked, m_bevel_never),
    (c9_chip_directions_cover_the_sphere, m_spiral_directions),
    (c10_chips_and_depth_parms_change_the_rock, m_chips_loop_dead),
    (c10_chips_and_depth_parms_change_the_rock, m_cutdepth_hardcoded),
    (c10_chips_and_depth_parms_change_the_rock, m_variation_ignored),
    (c10_chips_and_depth_parms_change_the_rock, m_chipdepth_hardcoded),
    (c10_chips_and_depth_parms_change_the_rock, m_chip_variation_ignored),
    (c11_same_settings_same_rock, m_nondeterministic),
    (c11_same_settings_same_rock, m_frame_dependent),
    (c12_wired_attributes_pass_but_scratch_groups_do_not, m_no_group_sweep),
]


def main(seed=7):
    global hou
    import hou
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(HDA)
    geo = hou.node("/obj").createNode("geo", "stylized_rock_checks")
    prism = geo.createNode("tube")
    prism.parm("type").set("poly")
    prism.parm("cap").set(1)
    prism.parm("cols").set(5)
    tagged = geo.createNode("attribwrangle")   # a wired box carrying its own attributes and groups
    tagged.setInput(0, geo.createNode("box"))
    tagged.parm("snippet").set('@Cd = @P; setpointgroup(0, "_vg", @ptnum, 1); setpointgroup(0, "pf_keep", @ptnum, 1);')
    node = geo.createNode("pf_stylized_rock")
    rnd = random.Random(seed)
    seeds = rnd.sample(range(1000), 4)

    def cook(_force=False, **parms):
        shape = parms.pop("shape", 0)
        node.setInput(0, {3: prism, 4: tagged}.get(shape))
        node.setParms({"shape": min(shape, 2), "seed": seeds[0], "size": (1.0, 0.75, 0.85), "cuts": 12,
                       "cutdepth": 0.3, "cutvar": 0.6, "chips": 30, "chipdepth": 0.08, "chipvar": 0.6,
                       "flatbottom": 0.0, "bevel": 0.0, "bevelsegs": 1, "cuspangle": 5.0})
        node.setParms(parms)
        if _force:
            node.cook(force=True)
        frozen = hou.Geometry()
        frozen.merge(node.geometry())
        return frozen
    cook.node = node

    failures = 0
    t0 = time.time()
    print("pf_stylized_rock - %s (seed %d -> rock seeds %s)\n" % (HDA, seed, seeds))
    for check, mutate in REGISTRY:
        ok, detail = check(cook, seeds)
        if not ok:
            failures += 1
        print("  %s  %-52s %s" % ("ok  " if ok else "FAIL", check.__name__, detail))
        node.allowEditingOfContents()
        try:
            mutate(node)
        except AssertionError as exc:
            failures += 1
            print("        MUTATION %s NOT APPLIED - %s" % (mutate.__name__, exc))
            node.matchCurrentDefinition()
            continue
        try:
            red, mdetail = check(cook, seeds)
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
