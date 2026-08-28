"""`pf_ring` checks, against the SHIPPED asset, in a throwaway Houdini session.

    hython tests/hda/run_ring_checks.py

Fifteen checks and fifteen mutations. Every check runs twice: once on the
clean asset, where it must pass, and once against the ONE edit that is
supposed to redden it, where it must fail. A check whose mutation stays green
is reported as a failure of the CHECK - `ideas/build_retrospective.md` §2a is
a list of ~20 checks that could not fail, and this pairing is what keeps this
file off it. It has earned that repeatedly: it caught an HScript ternary that
built every ring as a seamed open arc, a ring that shipped inside out, and
three of its own checks that were decoration on their first run.

Whole run, including hython boot, is a couple of seconds. It stays there
because every case cooks a ring of a few hundred points, not a scene.

The mutations edit an unlocked INSTANCE. `updateFromNode` is never called, so
nothing is written back to `pf_ring.hda` (dev-loop's HDA trap: that call
overwrites its own library file).

What these checks CANNOT see:
  * the cusp angle. Nothing asserts where shading cusps, only that N points
    out of the solid (C9).
  * TEXEL DENSITY. C15 asserts the layout fills the tile, not that a texture
    lands at a consistent scale across walls and caps. Normalising v makes
    the wall island a square whatever the ring's real proportions are, which
    is the conventional choice for a primitive and is not area-correct.
  * WHERE uvlayout puts each island - only that they are in the tile (C14),
    that both islands have real area (C10, C11) and that the tile is used
    (C15). Islands may be rotated, so nothing here assumes an orientation.
  * the parameter dialog. Names, ranges and help text are unasserted; the TAB
    submenu, icon, output label, the presence of every parm the VEX reads and
    the ABSENCE of the removed taper parms are asserted by the build script
    against the saved file.
  * values other than the ones listed. Each corner offset is proven at one
    value, the bevel at one width.
  * bevel shapes are proven distinguishable and sound (C13), not correct -
    nothing here knows what `Crease` is supposed to look like.
"""

import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
HDA = os.path.join(REPO, "polyfactory", "otls", "pf_ring.hda").replace("\\", "/")

EPS = 1e-5          # float32 P at radius 1 floors near 1e-7; this is slack.


# --------------------------------------------------------------------------
# measurements
# --------------------------------------------------------------------------
def _verts(prim):
    return [v.point().position() for v in prim.vertices()]


def _newell(vs):
    """Area-weighted face normal. Stable where a 3-point cross product is not:
    on a 16-gon cap with a 0.015-long bevel edge, the 3-point normal reported
    2.7e-06 of out-of-plane error on faces this reads as flat to 3.6e-08."""
    import hou
    n = hou.Vector3(0, 0, 0)
    for i in range(len(vs)):
        a, b = vs[i], vs[(i + 1) % len(vs)]
        n += hou.Vector3((a[1] - b[1]) * (a[2] + b[2]),
                         (a[2] - b[2]) * (a[0] + b[0]),
                         (a[0] - b[0]) * (a[1] + b[1]))
    return n


def _centroid(vs):
    import hou
    return sum(vs, hou.Vector3(0, 0, 0)) / len(vs)


def open_edges(geo):
    """Boundary edges - 0 means the surface is closed."""
    seen = {}
    for pr in geo.prims():
        ids = [v.point().number() for v in pr.vertices()]
        for i in range(len(ids)):
            e = (min(ids[i], ids[i - 1]), max(ids[i], ids[i - 1]))
            seen[e] = seen.get(e, 0) + 1
    return sum(1 for c in seen.values() if c == 1)


def min_area(geo):
    worst = None
    for pr in geo.prims():
        vs = _verts(pr)
        a = 0.5 * sum(((vs[i] - vs[0]).cross(vs[i + 1] - vs[0])).length()
                      for i in range(1, len(vs) - 1))
        worst = a if worst is None else min(worst, a)
    return 0.0 if worst is None else worst


def planar_error(geo):
    """Largest distance of any vertex from its own face's plane."""
    worst = 0.0
    for pr in geo.prims():
        vs = _verts(pr)
        if len(vs) < 4:
            continue
        n = _newell(vs)
        if n.length() < 1e-12:
            continue
        n = n.normalized()
        c = _centroid(vs)
        worst = max(worst, max(abs((v - c).dot(n)) for v in vs))
    return worst


def signed_volume(geo):
    """Divergence theorem over a closed mesh. NEGATIVE is correct in Houdini,
    which winds a front face clockwise seen from outside - measured against a
    `box` (-1.0000 for a unit cube) and a poly `sphere` (-4.07 for 4.19)."""
    total = 0.0
    for pr in geo.prims():
        vs = _verts(pr)
        for i in range(1, len(vs) - 1):
            total += vs[0].dot(vs[i].cross(vs[i + 1])) / 6.0
    return total


def analytic_volume(sides, outer, inner, height):
    """An independent derivation of the same solid: the area between two
    n-gons inscribed in the two circles, times the height."""
    return (0.5 * sides * math.sin(2.0 * math.pi / sides)
            * (outer ** 2 - inner ** 2) * height)


def arc_span(geo):
    """Degrees actually occupied: 360 minus the widest gap between neighbours."""
    a = sorted(math.degrees(math.atan2(p.position()[2], p.position()[0])) % 360.0
               for p in geo.points())
    gaps = [b - a2 for a2, b in zip(a, a[1:])] + [a[0] + 360.0 - a[-1]]
    return 360.0 - max(gaps)


def radius(p):
    return math.hypot(p[0], p[2])


def caps_and_walls(geo):
    """Split the two end caps off the walls GEOMETRICALLY: a cap's vertices
    all sit at ONE angle about Y, while a wall quad always spans an angular
    step. Deriving it from prim numbering instead would just restate the
    production code's own assumption about where polycap appends."""
    caps, walls = [], []
    for pr in geo.prims():
        angs = [math.atan2(v.point().position()[2], v.point().position()[0])
                for v in pr.vertices()]
        (caps if max(angs) - min(angs) < 1e-4 else walls).append(pr)
    return caps, walls


def uv_area(prims):
    """Area these faces occupy in UV. Rotation-proof, unlike counting distinct
    u or v values - uvlayout is free to turn an island any way it likes, and a
    COLLAPSED island rotated 45 degrees still has many distinct u and v."""
    total = 0.0
    for pr in prims:
        uvs = [v.attribValue("uv") for v in pr.vertices()]
        for i in range(1, len(uvs) - 1):
            ax, ay = uvs[i][0] - uvs[0][0], uvs[i][1] - uvs[0][1]
            bx, by = uvs[i + 1][0] - uvs[0][0], uvs[i + 1][1] - uvs[0][1]
            total += abs(ax * by - ay * bx) * 0.5
    return total


def uv_bounds(prims):
    uvs = [v.attribValue("uv") for pr in prims for v in pr.vertices()]
    return (min(a[0] for a in uvs), max(a[0] for a in uvs),
            min(a[1] for a in uvs), max(a[1] for a in uvs))


def corner_set(geo):
    """The cross-section, read back off the solid: every distinct
    (radius, height) a point sits at. A plain ring has exactly four."""
    return sorted(set((round(radius(p.position()), 4), round(p.position()[1], 4))
                      for p in geo.points()))


def heights_at(geo, r):
    """(min, max) height of the points sitting at radius `r`."""
    ys = [p.position()[1] for p in geo.points()
          if abs(radius(p.position()) - r) < EPS]
    return (min(ys), max(ys)) if ys else (None, None)


def y_extent(geo):
    ys = [p.position()[1] for p in geo.points()]
    return min(ys), max(ys)


def signature(geo):
    """Enough of the shape to tell two bevel results apart."""
    return (len(geo.points()),
            round(sum(abs(c) for p in geo.points() for c in p.position()), 5))


# --------------------------------------------------------------------------
# checks. `cook(**parms)` returns a FROZEN copy - `node.geometry()` is a live
# handle, and comparing two of them across a re-cook compares one geometry
# with itself (C6 did exactly that and reported 96 points twice).
# --------------------------------------------------------------------------
def c1_closed_ring_has_no_seam(cook):
    """Watertight is not enough. An arc-at-360 that polycap closes back up is
    also watertight, which is the bug this file caught: a closed ring is
    `sides` columns of 4 quads and not one point more."""
    g = cook(sides=24)
    n, pts, prims = open_edges(g), len(g.points()), len(g.prims())
    ok = n == 0 and pts == 96 and prims == 96
    return ok, "open edges %d, %d pts, %d prims (want 0, 96, 96)" % (
        n, pts, prims)


def c2_arc_ends_are_capped(cook):
    n = open_edges(cook(arcangle=90.0))
    return n == 0, "open edges on a 90 deg arc: %d" % n


def c3_an_arc_is_actually_an_arc(cook):
    """Angle AND count: a quarter arc spans 90 degrees and takes a quarter of
    the sides, so facets stay the size they were at 360."""
    g = cook(sides=24, arcangle=90.0)
    span, prims = arc_span(g), len(g.prims())
    ok = abs(span - 90.0) < 0.5 and prims == 26      # 6 columns x 4 + 2 caps
    return ok, "quarter arc spans %.2f deg (want 90), %d prims (want 26)" % (
        span, prims)


def c4_the_solid_is_the_one_that_was_asked_for(cook):
    """Radii and height read off the points, and then the SAME solid measured
    a second, independent way - its volume against the closed-form n-gon
    annulus. The two derivations share no code."""
    g = cook(sides=24, outer=2.0, inner=1.25, height=0.4)
    rs = [radius(p.position()) for p in g.points()]
    lo, hi = min(rs), max(rs)
    y0, y1 = y_extent(g)
    vol = abs(signed_volume(g))              # sign is C9's; this is magnitude
    want = analytic_volume(24, 2.0, 1.25, 0.4)
    rel = abs(vol - want) / want
    ok = (abs(hi - 2.0) < EPS and abs(lo - 1.25) < EPS
          and abs(y0 + 0.2) < EPS and abs(y1 - 0.2) < EPS and rel < 1e-4)
    return ok, "outer %.6f inner %.6f y %.6f..%.6f | volume %.6f vs " \
               "analytic %.6f (%.2e rel)" % (hi, lo, y0, y1, vol, want, rel)


def c5_zero_bevel_leaves_no_degenerate_face(cook):
    a = min_area(cook(bevel=0.0))
    return a > 1e-9, "smallest face area at bevel 0: %.3e" % a


def c6_bevel_cuts_the_corners(cook):
    """A bevel adds a face per corner that faces neither along Y nor radially."""
    base = len(cook(bevel=0.0).points())
    g = cook(bevel=0.05)
    slanted = 0
    for pr in g.prims():
        vs = _verts(pr)
        n = _newell(vs)
        rad = _centroid(vs)
        rad = type(rad)(rad[0], 0, rad[2])
        if n.length() < 1e-12 or rad.length() < 1e-9:
            continue
        n = n.normalized()
        if abs(n[1]) > 0.05 and abs(n.dot(rad.normalized())) > 0.05:
            slanted += 1
    ok = len(g.points()) > base and slanted >= 4 and min_area(g) > 1e-9
    return ok, "bevelled pts %d vs %d, slanted faces %d (want >= 4), " \
               "min area %.3e" % (len(g.points()), base, slanted, min_area(g))


def c7_every_face_is_flat(cook):
    """The whole point of the tool: flat sides, not a torus. Measured with a
    Newell normal - see `_newell`, the 3-point version measures its own
    conditioning. The second fixture pushes all four corners off the square
    AND bevels an arc, because a moved corner is exactly the edit that could
    bend a face."""
    e = max(planar_error(cook()),
            planar_error(cook(rad_to=0.3, hgt_to=-0.12, rad_ti=-0.15,
                              hgt_ti=0.2, rad_bo=0.1, hgt_bo=0.05,
                              rad_bi=0.25, hgt_bi=-0.3,
                              bevel=0.02, bevelsegs=3, arcangle=140.0)))
    return e < 1e-6, "worst out-of-plane error: %.3e (want < 1e-6)" % e


def c8_each_corner_offset_moves_only_its_own_corner(cook):
    """The whole point of dropping the taper for corner offsets: turning one
    knob moves one corner and nothing else. All eight are exercised, because
    an offset nothing ever sets is an untested branch."""
    base = {"sides": 24, "outer": 1.0, "inner": 0.6, "height": 0.4}
    flat = sorted([(0.6, -0.2), (0.6, 0.2), (1.0, -0.2), (1.0, 0.2)])
    got = corner_set(cook(**base))
    if got != flat:
        return False, "with no offsets the section is %s, want %s" % (got, flat)
    cases = [("rad_to", 0.3, (1.0, 0.2), (1.3, 0.2)),
             ("hgt_to", -0.15, (1.0, 0.2), (1.0, 0.05)),
             ("rad_ti", -0.2, (0.6, 0.2), (0.4, 0.2)),
             ("hgt_ti", 0.25, (0.6, 0.2), (0.6, 0.45)),
             ("rad_bo", 0.4, (1.0, -0.2), (1.4, -0.2)),
             ("hgt_bo", 0.1, (1.0, -0.2), (1.0, -0.1)),
             ("rad_bi", 0.15, (0.6, -0.2), (0.75, -0.2)),
             ("hgt_bi", -0.3, (0.6, -0.2), (0.6, -0.5))]
    bad = []
    for parm, val, was, now in cases:
        parms = dict(base)
        parms[parm] = val
        want = sorted([c for c in flat if c != was] + [now])
        got = corner_set(cook(**parms))
        if got != want:
            bad.append("%s=%g gave %s want %s" % (parm, val, got, want))
    return not bad, "8 offsets, %d wrong%s" % (
        len(bad), (": " + "; ".join(bad)) if bad else "")


def c9_the_solid_is_not_inside_out(cook):
    """Two independent readings, because this shipped wrong once: enclosed
    volume must be NEGATIVE (Houdini's clockwise front face - see
    `signed_volume`), and the N that actually leaves the node must point AWAY
    from the axis on the outer wall. Comparing N against the face's own
    winding cannot see this - that agreement holds either way round."""
    g = cook(outer=1.0, inner=0.7)
    vol = signed_volume(g)
    worst = 1.0
    for pr in g.prims():
        vs = _verts(pr)
        c = _centroid(vs)
        rad = type(c)(c[0], 0, c[2])
        ns = [v.attribValue("N") for v in pr.vertices()]
        mean = type(c)(sum(a[0] for a in ns), sum(a[1] for a in ns),
                       sum(a[2] for a in ns))
        if mean.length() < 1e-9:
            return False, "no usable N on prim %d" % pr.number()
        mean = mean.normalized()
        if rad.length() > 0.85 and abs(mean[1]) < 0.5:      # outer wall only
            worst = min(worst, mean.dot(rad.normalized()))
    ok = vol < 0 and worst > 0.9
    return ok, "enclosed volume %+.6f (want < 0), worst outer-wall " \
               "dot(N, radial) %.4f (want > 0.9)" % (vol, worst)


def c10_arc_caps_get_a_real_uv_island(cook):
    """polycap emits no UVs, so both end faces arrived at uv (0,0,0) - one
    black patch under any texture, and a zero-area island for uvlayout to
    pack. Area, not extent: uvlayout scales the island to share the tile, so
    how big it ends up is its business, but it must not be flat."""
    g = cook(arcangle=90.0, outer=1.0, inner=0.7, height=0.25, bevel=0.03)
    caps, _ = caps_and_walls(g)
    if len(caps) != 2:
        return False, "found %d end caps, want 2" % len(caps)
    area = uv_area(caps)
    u0, u1, v0, v1 = uv_bounds(caps)
    ok = area > 0.001 and (u1 - u0) > 0.03 and (v1 - v0) > 0.03
    return ok, "cap uv area %.4f (want > 0.001), bbox %.3f x %.3f " \
               "(want > 0.03 each)" % (area, u1 - u0, v1 - v0)


def c11_the_cap_uvs_do_not_flatten_the_walls(cook):
    """The cap formula maps (radius, height) to (u, v). Run it over a WALL
    face and either both its radii or both its heights are equal, so the
    face collapses to a LINE in UV. Total island area cannot see that: the
    mutation actually made the wall area BIGGER (0.248 -> 5.95) by handing
    uvlayout a mesh of degenerate islands and defeating the packer. Counting
    faces with no UV area is what sees it."""
    g = cook(sides=24, arcangle=90.0)
    _, walls = caps_and_walls(g)
    flat = sum(1 for pr in walls if uv_area([pr]) < 1e-9)
    return flat == 0, "%d of %d wall faces have no UV area (want 0)" % (
        flat, len(walls))


def c12_corner_offsets_add_to_the_globals(cook):
    """They must sit ON TOP of the global radius and height, not replace
    them - the thing that makes one global control plus four local ones
    predictable. So the same offset has to survive moving either global."""
    off = {"rad_to": 0.25, "hgt_bi": 0.1, "inner": 0.6}
    a = cook(outer=1.0, height=0.4, **off)
    b = cook(outer=2.0, height=0.4, **off)      # global radius moves
    c = cook(outer=1.0, height=1.0, **off)      # global height moves
    ra = max(radius(p.position()) for p in a.points())
    rb = max(radius(p.position()) for p in b.points())
    lo_c, _ = heights_at(c, 0.6)
    lo_a, _ = heights_at(a, 0.6)
    ok = (abs(ra - 1.25) < EPS and abs(rb - 2.25) < EPS
          and abs(lo_a + 0.1) < EPS and abs(lo_c + 0.4) < EPS)
    return ok, "top-outer r %.4f then %.4f (want 1.25, 2.25) | bottom-inner " \
               "y %.4f then %.4f (want -0.1, -0.4)" % (ra, rb, lo_a, lo_c)


def c13_every_bevel_shape_is_wired_and_sound(cook):
    """Every menu entry is a branch, and a branch the suite never runs is
    untested however green the run is. Each of the five must produce a sound
    solid, and the menu must actually REACH polybevel - if it did not, all
    five would come back byte-identical and every other check would still
    pass."""
    sigs, bad = [], []
    for i in range(5):
        g = cook(bevel=0.06, bevelsegs=4, bevelshape=i)
        sigs.append(signature(g))
        if open_edges(g) or planar_error(g) > 1e-6 or min_area(g) <= 1e-9:
            bad.append("%d(open=%d planar=%.1e area=%.1e)"
                       % (i, open_edges(g), planar_error(g), min_area(g)))
    distinct = len(set(sigs))
    ok = not bad and distinct >= 3
    return ok, "%d/5 distinct shapes (want >= 3), unsound: %s" % (
        distinct, ", ".join(bad) if bad else "none")


def c14_uvs_stay_inside_the_1001_tile(cook):
    """Before uvlayout the wall island ran v 0..5 at the default radius and
    0..11 at radius 5 - four and ten tiles of overspill that only showed on a
    CLOSED ring, because an arc happened to land inside 0-1."""
    out = []
    for name, parms in (("defaults", {}),
                        ("big radius", {"outer": 5.0, "inner": 4.0}),
                        ("tall", {"height": 4.0}),
                        ("64 sides", {"sides": 64}),
                        ("arc + bevel", {"arcangle": 200.0, "bevel": 0.05,
                                         "bevelsegs": 3})):
        g = cook(**parms)
        u0, u1, v0, v1 = uv_bounds(g.prims())
        if min(u0, v0) < -1e-3 or max(u1, v1) > 1.0 + 1e-3:
            out.append("%s u %.3f..%.3f v %.3f..%.3f" % (name, u0, u1, v0, v1))
    return not out, "outside the tile: %s" % ("; ".join(out) if out else "none")


def c15_the_layout_fills_the_tile(cook):
    """Fitting inside 1001 is half of it - a sliver in the corner also fits.
    `revolve` ships v un-normalised and length-weighted, and uvlayout keeps an
    island's aspect, so leaving it that way packed the ring into 20% of the
    tile at the default radius and 9% at radius 5."""
    worst, worstname = 1.0, ""
    for name, parms in (("defaults", {}),
                        ("big radius", {"outer": 5.0, "inner": 4.0})):
        u0, u1, v0, v1 = uv_bounds(cook(**parms).prims())
        used = min(u1 - u0, v1 - v0)
        if used < worst:
            worst, worstname = used, name
    return worst > 0.9, "smallest tile extent used: %.3f on %s (want > 0.9)" \
                        % (worst, worstname)


# --------------------------------------------------------------------------
# mutations: one per check, each editing production code inside the asset.
# --------------------------------------------------------------------------
def m_seam(net):
    """Revolve stops closing the loop - the 360 seam is left open (and then
    capped, which is why C1 counts points rather than boundary edges)."""
    net.node("rev").parm("type").deleteAllKeyframes()
    net.node("rev").parm("type").set(1)


def m_no_cap(net):
    net.node("cap").bypass(True)


def m_arc_forced_closed(net):
    """The shipped bug: an HScript ternary that silently kept `type` at 0."""
    net.node("rev").parm("type").deleteAllKeyframes()
    net.node("rev").parm("type").set(0)


def m_not_centred(net):
    _patch(net, "profile", "float y0 = -h * 0.5", "float y0 = 0.0")


def m_bevel_always_on(net):
    net.node("swbevel").parm("input").setExpression("1")


def m_bevel_width_ignored(net):
    net.node("bevel").parm("offset").setExpression("0")


def m_profile_off_plane(net):
    _patch(net, "profile", "append(pts, addpoint(0, set(rot, y1o, 0)));",
           "append(pts, addpoint(0, set(rot, y1o, 0.02)));")


def m_corners_share_a_height(net):
    """The top inner corner follows the top OUTER one, so two corners move
    when one knob turns - the exact failure the taper had by design."""
    _patch(net, "profile", 'y1i = y1 + chf("../hgt_ti")',
           'y1i = y1 + chf("../hgt_to")')


def m_profile_reversed(net):
    """Emit the cross-section the other way round: the ring keeps its shape,
    its volume and its silhouette, and turns inside out. After the LAST
    append, not the first - reversing a one-element array is a no-op, and a
    no-op mutation reads as a check that cannot fail. `pts = reverse(pts)`,
    never bare `reverse(pts)`: retrospective #44."""
    _patch(net, "profile", 'addprim(0, "poly", pts);',
           'pts = reverse(pts); addprim(0, "poly", pts);')


def m_no_cap_uv(net):
    net.node("capuv").bypass(True)


def m_capuv_unguarded(net):
    """Drop the wall guard so the cap UVs are written over the whole mesh."""
    _patch(net, "capuv", "if (wall == 0) {", "if (wall == 0 || wall == 1) {")


def m_offset_replaces_the_global(net):
    _patch(net, "profile", 'float rot = max(ro + chf("../rad_to"), 0.0)',
           'float rot = max(chf("../rad_to"), 0.0)')


def m_bevel_shape_pinned(net):
    net.node("bevel").parm("filletshape").setExpression("4")


def m_no_tile_containment(net):
    """Two things keep the UVs in 1001 and EITHER alone is enough, so both
    have to go for C14 to be able to fail: the packer, and normalising v
    (which revolve ships OFF, leaving v length-weighted and unbounded)."""
    net.node("uvlayout").bypass(True)
    net.node("rev").parm("normalizev").set(0)


def m_v_not_normalised(net):
    net.node("rev").parm("normalizev").set(0)


def _patch(net, node, old, new):
    p = net.node(node).parm("snippet")
    src = p.eval()
    assert old in src, "mutation target not in %s's VEX: %r" % (node, old)
    p.set(src.replace(old, new))


REGISTRY = [
    (c1_closed_ring_has_no_seam, m_seam),
    (c2_arc_ends_are_capped, m_no_cap),
    (c3_an_arc_is_actually_an_arc, m_arc_forced_closed),
    (c4_the_solid_is_the_one_that_was_asked_for, m_not_centred),
    (c5_zero_bevel_leaves_no_degenerate_face, m_bevel_always_on),
    (c6_bevel_cuts_the_corners, m_bevel_width_ignored),
    (c7_every_face_is_flat, m_profile_off_plane),
    (c8_each_corner_offset_moves_only_its_own_corner, m_corners_share_a_height),
    (c9_the_solid_is_not_inside_out, m_profile_reversed),
    (c10_arc_caps_get_a_real_uv_island, m_no_cap_uv),
    (c11_the_cap_uvs_do_not_flatten_the_walls, m_capuv_unguarded),
    (c12_corner_offsets_add_to_the_globals, m_offset_replaces_the_global),
    (c13_every_bevel_shape_is_wired_and_sound, m_bevel_shape_pinned),
    (c14_uvs_stay_inside_the_1001_tile, m_no_tile_containment),
    (c15_the_layout_fills_the_tile, m_v_not_normalised),
]

DEFAULTS = {"sides": 24, "outer": 1.0, "inner": 0.7, "height": 0.25,
            "arcangle": 360.0, "startangle": 0.0,
            "bevel": 0.0, "bevelshape": 4, "bevelsegs": 1,
            "rad_to": 0.0, "hgt_to": 0.0, "rad_ti": 0.0, "hgt_ti": 0.0,
            "rad_bo": 0.0, "hgt_bo": 0.0, "rad_bi": 0.0, "hgt_bi": 0.0}


def main():
    import hou
    hou.hipFile.clear(suppress_save_prompt=True)
    hou.hda.installFile(HDA)
    geo = hou.node("/obj").createNode("geo", "ring_checks")
    ring = geo.createNode("pf_ring")

    def cook(**parms):
        ring.setParms(DEFAULTS)
        ring.setParms(parms)
        frozen = hou.Geometry()
        frozen.merge(ring.geometry())
        return frozen

    failures = 0
    t0 = time.time()
    print("pf_ring - %s\n" % HDA)
    for check, mutate in REGISTRY:
        ok, detail = check(cook)
        if not ok:
            failures += 1
        print("  %s  %-48s %s" % ("ok  " if ok else "FAIL",
                                  check.__name__, detail))

        ring.allowEditingOfContents()
        try:
            mutate(ring)
            red, mdetail = check(cook)
        except Exception as exc:                    # a crash IS a red check
            red, mdetail = False, "%s: %s" % (type(exc).__name__, exc)
        ring.matchCurrentDefinition()
        if red:
            failures += 1
            print("        MUTATION %s STAYED GREEN - this check cannot "
                  "fail: %s" % (mutate.__name__, mdetail))

    print("\n%d failing checks in %.2f s (checks only; hython boot is on top)"
          % (failures, time.time() - t0))
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
