"""The 2D array, looked at - PC-G5's images, headless.

    hython tests/polychain/facade_images.py [outdir]

WHY. Prim counts do not prove geometry is correct (dev-loop, "look at it"),
and 7.8 names the exact failure no number in `run_2d_checks.py` can catch:
*a corner that closes numerically while the cornice returns the wrong way
round it.* So the L facade is drawn three ways - the whole figure in
three-quarter view, the reflex corner from ground to cornice, and a front
elevation coloured by `pc_cell` so the 5 x 5 role table is visible as a
PATTERN - and the kit-gap build is drawn beside it, because a facade that has
degraded should look plain and not broken.

⚠️ THE RASTERISER IS `gate_images.py`'s, EXTENDED, NOT REBUILT. §7.8 says so
by name, and that file's own docstring records that it was rebuilt from a
scratchpad three times before anyone committed it. What phase 2 added to it is
two things a facade needs and a fence did not: `unpack` (a packed prim has ONE
vertex, so an instanced facade rasterises as an empty frame) and `project`,
whose "iso" mode is the three-quarter view no pair of world axes can give.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
OUT = (sys.argv[1] if len(sys.argv) > 1
       else os.path.join(HERE, "gate_images"))

import cases2d                                                   # noqa: E402
import gate_images as G                                          # noqa: E402
import hou                                                       # noqa: E402

# One colour per cell class, chosen so the three BANDS read apart at a glance
# and the corner column reads apart from the field within each band.
CELL_COLOUR = {
    "default":       (150, 160, 180),
    "corner":        (235, 170,  90),
    "default_start": (110, 190, 235),
    "corner_start":  (235, 120,  90),
    "default_end":   (150, 235, 150),
    "corner_end":    (245, 235, 110),
    "default_evenly": (200, 140, 235),
    "corner_evenly": (235, 100, 180),
}
MISSING = (255, 70, 70)          # a stand-in, so a kit gap is unmistakable


def _one_prim(geo, prim):
    """A one-primitive copy - the deformed branch's piece, in world space."""
    out = hou.Geometry()
    pts = [out.createPoint() for _v in prim.vertices()]
    for pt, v in zip(pts, prim.vertices()):
        pt.setPosition(v.point().position())
    poly = out.createPolygon(prim.isClosed())
    for pt in pts:
        poly.addVertex(pt)
    return out


# PC-G6: the same figure keyed on the CLIP POLICY instead of on the cell, so
# what the picture shows is what the boundary did to each piece. The pieces the
# boundary REMOVED are not in it - that is the point of drawing it: a removal
# is a gap, and a gap is only judgeable by eye.
CLIP_CUT = (120, 235, 140)       # cut on the line
CLIP_WHOLE = (150, 160, 180)     # inside, untouched
CLIP_RIGID = (235, 170, 90)      # a rigid module that stayed whole


def _cell_colour(prim):
    try:
        cell = prim.attribValue("pc_cell")
    except hou.OperationFailed:
        cell = ""
    try:
        gap = int(prim.attribValue("pc_warn_kit_gap"))
    except (hou.OperationFailed, TypeError, ValueError):
        gap = 0
    return MISSING if gap else CELL_COLOUR.get(cell, (185, 195, 212))


def _clip_colour(prim):
    try:
        cut = int(prim.attribValue("pc_corner_cut"))
    except (hou.OperationFailed, TypeError, ValueError):
        cut = 0
    if cut:
        return CLIP_CUT
    try:
        rigid = prim.attribValue("pc_module") == "block"
    except hou.OperationFailed:
        rigid = False
    return CLIP_RIGID if rigid else CLIP_WHOLE


def coloured(geo, colour_for=_cell_colour):
    """(display geometry, colour_of) - the unpacked copy plus its colour.

    The colour has to survive the unpack, so it is baked onto the flattened
    polygons as a point attribute rather than looked up per prim afterwards:
    `unpack` merges embedded geometry, which does not carry `pc_cell`.
    """
    out = hou.Geometry()
    out.addAttrib(hou.attribType.Prim, "pc_rgb", (0.0, 0.0, 0.0))
    for prim in geo.prims():
        col = colour_for(prim)
        piece = hou.Geometry()
        if prim.type() == hou.primType.PackedGeometry:
            piece.merge(prim.getEmbeddedGeometry())
            piece.transform(prim.fullTransform())
        else:
            # ⚠️ THE DEFORMED HALF IS NOT OPTIONAL, and skipping it is how the
            # first version of this image showed the reflex corner as an empty
            # GAP: a mitered corner column carries a world-space cut, so it can
            # never be a packed prim (4.3) and every `corner` cell in the
            # figure was silently absent from the picture that exists to judge
            # exactly that corner.
            piece.merge(_one_prim(geo, prim))
        piece.addAttrib(hou.attribType.Prim, "pc_rgb", (0.0, 0.0, 0.0))
        piece.setPrimFloatAttribValues(
            "pc_rgb", list(col) * piece.intrinsicValue("primitivecount"))
        out.merge(piece)

    def colour_of(prim):
        v = prim.attribValue("pc_rgb")
        return (int(v[0]), int(v[1]), int(v[2]))
    return (out, colour_of)


def near(geo, centre, radius):
    """The pieces within `radius` of a plan position - PC-G5's close-up.

    A crop, not a camera: the rasteriser fits whatever it is given, so
    selecting the geometry IS zooming in on it.
    """
    out = hou.Geometry()
    out.merge(geo)
    dead = []
    for prim in out.prims():
        pts = [v.point().position() for v in prim.vertices()]
        if not pts:
            continue
        cx = sum(p[0] for p in pts) / len(pts)
        cz = sum(p[2] for p in pts) / len(pts)
        if (cx - centre[0]) ** 2 + (cz - centre[1]) ** 2 > radius * radius:
            dead.append(prim)
    if dead:
        out.deletePrims(dead, True)
    return out


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    built = cases2d.build_all()
    # PC-G6's figure, 7.8: "top view of the plate with its hole, elements
    # coloured by clip policy". The fixture is drawn flat in the world XY
    # plane, so its plan view IS the (x, y) elevation.
    built["clip_plate"] = cases2d.clip_case()
    # ...and the SAME plate wound the other way, 500 m from the origin - the
    # two properties the shipped fixture had by accident and citygen will not
    # (C2a). Reversed, the array was built one module-height out of its own
    # footprint with the hole FILLED; a plan view is exactly the picture that
    # shows whether the two figures are the same drawing.
    built["clip_hostile"] = cases2d.clip_case(
        loops=cases2d.clip_loops_hostile())
    # D296's two, and they are drawn EDGE-ON on purpose. A tilted array's
    # failure is that its modules leave the array's own plane, and the one
    # view in which "in the plane" is a straight line and "out of it" is a
    # 2 m thick band is the one looking ALONG the plane. The floor plate is
    # the same picture at 90 degrees, where the world up axis is the plate's
    # own normal and the before-build stood every module on end.
    built["clip_tilt30"] = cases2d.clip_case(
        loops=[cases2d.tilt_plate(30.0)], clip_mode="remove")
    built["clip_floor"] = cases2d.clip_case(
        loops=[cases2d.tilt_plate(90.0)], clip_mode="remove")
    fail = []
    for name, view, axes, crop in (
            ("FA_L_facade", "iso", "iso", None),
            ("FA_L_facade", "front", ("x", "y"), None),
            ("FA_L_facade", "reflex", "iso", ((12.0, 12.0), 5.0)),
            ("FD_role_fallback", "iso", "iso", None),
            ("FE_stand_in", "front", ("x", "y"), None),
            ("FM_area_taper", "front", ("x", "y"), None),
            ("clip_plate", "plan", ("x", "y"), None),
            ("clip_hostile", "plan", ("x", "y"), None),
            ("clip_tilt30", "edge", ("z", "y"), None),
            ("clip_floor", "edge", ("z", "y"), None)):
        geo, colour_of = coloured(
            built[name]["out"],
            _clip_colour if name.startswith("clip_") else _cell_colour)
        if crop is not None:
            geo = near(geo, crop[0], crop[1])
        drawn = G.rasterise(os.path.join(
            OUT, "%s_%s_%s.png" % ("PCG6" if name.startswith("clip_")
                                   else "PCG5", name, view)),
            geo, axes=axes, w=1400, h=900, colour_of=colour_of)
        # D194's rule, `drawn_covers_packed`'s shape: the image must CONTAIN
        # its subject before anyone judges it. Every polygon of n vertices
        # contributes n segments, so drawn < prims (or an empty build) means
        # pieces the picture cannot show - the V4 audit fed every facade an
        # empty hou.Geometry() and this script wrote zero PNGs and exited 0,
        # PC-G5's only image evidence unable to fail.
        prims = geo.intrinsicValue("primitivecount")
        ok = prims > 0 and drawn >= prims
        print("  [%s] facade_image_has_geometry_%s_%s  %d prims, %d segments"
              % ("PASS" if ok else "FAIL", name, view, prims, drawn))
        if not ok:
            fail.append("%s_%s" % (name, view))
    print("\n%d failing facade images" % len(fail))
    if fail:
        print("  " + ", ".join(fail))
    sys.exit(1 if fail else 0)


if __name__ == "__main__":
    main()
