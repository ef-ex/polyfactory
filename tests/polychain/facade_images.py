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


def coloured(geo):
    """(display geometry, colour_of) - the unpacked copy plus its cell colour.

    The colour has to survive the unpack, so it is baked onto the flattened
    polygons as a point attribute rather than looked up per prim afterwards:
    `unpack` merges embedded geometry, which does not carry `pc_cell`.
    """
    out = hou.Geometry()
    out.addAttrib(hou.attribType.Prim, "pc_rgb", (0.0, 0.0, 0.0))
    for prim in geo.prims():
        try:
            cell = prim.attribValue("pc_cell")
        except hou.OperationFailed:
            cell = ""
        try:
            gap = int(prim.attribValue("pc_warn_kit_gap"))
        except (hou.OperationFailed, TypeError, ValueError):
            gap = 0
        col = MISSING if gap else CELL_COLOUR.get(cell, (185, 195, 212))
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
    fail = []
    for name, view, axes, crop in (
            ("FA_L_facade", "iso", "iso", None),
            ("FA_L_facade", "front", ("x", "y"), None),
            ("FA_L_facade", "reflex", "iso", ((12.0, 12.0), 5.0)),
            ("FD_role_fallback", "iso", "iso", None),
            ("FE_stand_in", "front", ("x", "y"), None),
            ("FM_area_taper", "front", ("x", "y"), None)):
        geo, colour_of = coloured(built[name]["out"])
        if crop is not None:
            geo = near(geo, crop[0], crop[1])
        drawn = G.rasterise(os.path.join(OUT, "PCG5_%s_%s.png" % (name, view)),
                            geo, axes=axes, w=1400, h=900,
                            colour_of=colour_of)
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
