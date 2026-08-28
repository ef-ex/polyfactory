"""`pf_ring` checks, against the SHIPPED asset, in a throwaway Houdini session.

    hython tests/hda/run_ring_checks.py

Nine checks and nine mutations. Every check runs twice: once on the clean
asset, where it must pass, and once against the ONE edit that is supposed to
redden it, where it must fail. A check whose mutation stays green is reported
as a failure of the CHECK - `ideas/build_retrospective.md` §2a is a list of
~20 checks that could not fail, and this pairing is what keeps this file off
it. It has already earned that: the pairing caught an HScript ternary that
silently built every ring as a seamed open arc, and two of these checks were
themselves decoration on the first run (see the notes on C7 and C9).

The mutations edit an unlocked INSTANCE. `updateFromNode` is never called, so
nothing is written back to `pf_ring.hda` (dev-loop's HDA trap: that call
overwrites its own library file).

What these checks CANNOT see:
  * the cusp angle. C9 asserts N agrees with the surface, not where it cusps.
  * UVs. `revolve` computes them and nothing here reads them.
  * the parameter dialog. Names, ranges and help text are unasserted; the TAB
    submenu, icon and output label are asserted by the build script against
    the saved file.
  * values other than the ones listed. Bevel is proven at one width, taper at
    one amount per side, the arc at 90 and 140 degrees.
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


def radii_at(geo, y):
    """(min, max) radius of the points sitting at height `y`."""
    rs = [radius(p.position()) for p in geo.points()
          if abs(p.position()[1] - y) < EPS]
    return (min(rs), max(rs)) if rs else (None, None)


def y_extent(geo):
    ys = [p.position()[1] for p in geo.points()]
    return min(ys), max(ys)


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
    conditioning. Worst on a correct build is ~4e-08 at radius 1."""
    e = max(planar_error(cook()),
            planar_error(cook(taper_top=0.4, bias_top=0.6, bevel=0.04,
                              bevelsegs=3, arcangle=140.0)))
    return e < 1e-6, "worst out-of-plane error: %.3e (want < 1e-6)" % e


def c8_top_and_bottom_taper_independently(cook):
    """Top tapered hard against the outer circle; the bottom must not move.
    Then the reverse, so neither side is proven only in one direction."""
    g = cook(outer=1.0, inner=0.6, taper_top=0.5, bias_top=1.0)
    ti, to = radii_at(g, 0.125)
    bi, bo = radii_at(g, -0.125)
    h = cook(outer=1.0, inner=0.6, taper_bot=0.5, bias_bot=-1.0)
    ui, uo = radii_at(h, 0.125)
    li, lo = radii_at(h, -0.125)
    ok = (abs(to - 1.0) < EPS and abs(ti - 0.8) < EPS
          and abs(bo - 1.0) < EPS and abs(bi - 0.6) < EPS
          and abs(uo - 1.0) < EPS and abs(ui - 0.6) < EPS
          and abs(lo - 0.8) < EPS and abs(li - 0.6) < EPS)
    return ok, "top-taper: top %.4f..%.4f (want .8-1) bottom %.4f..%.4f " \
               "(want .6-1) | bottom-taper: top %.4f..%.4f (want .6-1) " \
               "bottom %.4f..%.4f (want .6-.8)" % (ti, to, bi, bo,
                                                   ui, uo, li, lo)


def c9_the_solid_is_not_inside_out(cook):
    """Two independent readings of the same property, because this shipped
    wrong once: the enclosed volume must be NEGATIVE (Houdini's clockwise
    front face - see `signed_volume`), and the N that actually leaves the node
    must point AWAY from the axis on the outer wall. Comparing N against the
    face's own winding cannot see this - that agreement holds either way."""
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
    return ok, "enclosed volume %+.6f (want < 0), worst outer-wall "                "dot(N, radial) %.4f (want > 0.9)" % (vol, worst)


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
    _patch(net, "float y0 = -h * 0.5", "float y0 = 0.0")


def m_bevel_always_on(net):
    net.node("swbevel").parm("input").setExpression("1")


def m_bevel_width_ignored(net):
    net.node("bevel").parm("offset").setExpression("0")


def m_profile_off_plane(net):
    _patch(net, "addpoint(0, set(rot, y1, 0))",
           "addpoint(0, set(rot, y1, 0.02))")


def m_top_taper_drives_bottom(net):
    # Must drive the bottom's WIDTH, not its bias: bias on an untapered side
    # moves nothing, so a bias-only mutation is invisible to every fixture.
    _patch(net, "float wb = w * (1.0 - clamp(tb, 0.0, 1.0));",
           "float wb = w * (1.0 - clamp(tt, 0.0, 1.0));")


def m_profile_reversed(net):
    """Emit the cross-section the other way round: the ring keeps its shape,
    its volume and its silhouette, and turns inside out."""
    # After the LAST append, not the first - reversing a one-element array
    # is a no-op, and a no-op mutation reads as a check that cannot fail.
    # `pts = reverse(pts)`, never bare `reverse(pts)`: retrospective #44.
    _patch(net, 'addprim(0, "poly", pts);',
           'pts = reverse(pts); addprim(0, "poly", pts);')


def _patch(net, old, new):
    p = net.node("profile").parm("snippet")
    src = p.eval()
    assert old in src, "mutation target not in the VEX: %r" % old
    p.set(src.replace(old, new))


REGISTRY = [
    (c1_closed_ring_has_no_seam, m_seam),
    (c2_arc_ends_are_capped, m_no_cap),
    (c3_an_arc_is_actually_an_arc, m_arc_forced_closed),
    (c4_the_solid_is_the_one_that_was_asked_for, m_not_centred),
    (c5_zero_bevel_leaves_no_degenerate_face, m_bevel_always_on),
    (c6_bevel_cuts_the_corners, m_bevel_width_ignored),
    (c7_every_face_is_flat, m_profile_off_plane),
    (c8_top_and_bottom_taper_independently, m_top_taper_drives_bottom),
    (c9_the_solid_is_not_inside_out, m_profile_reversed),
]

DEFAULTS = {"sides": 24, "outer": 1.0, "inner": 0.7, "height": 0.25,
            "arcangle": 360.0, "startangle": 0.0, "bevel": 0.0,
            "bevelsegs": 1, "taper_top": 0.0, "bias_top": 0.0,
            "taper_bot": 0.0, "bias_bot": 0.0}


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
    print("pf_ring - %s\n" % HDA)
    for check, mutate in REGISTRY:
        ok, detail = check(cook)
        if not ok:
            failures += 1
        print("  %s  %-44s %s" % ("ok  " if ok else "FAIL",
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

    print("\n%d failing checks" % failures)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
