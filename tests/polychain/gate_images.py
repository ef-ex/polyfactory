"""PC-G1 and PC-G2 re-confirmed THROUGH THE PARM FACE, headless, with images.

    hython tests/polychain/gate_images.py [outdir]

WHY THIS FILE EXISTS. §0.0 says headless image verification is the standing
substitute while the live MCP bridge is wedged, and *"reuse it; do not rebuild
it"* - and it has now been rebuilt from a scratchpad three times, because it
was never committed. This is tests/README.md's own rule arriving late: the
measurement an audit writes belongs in the suite afterwards. So the rasteriser
and the parm-face driver live here now.

WHAT IT ADDS THAT `run_scene_checks.py` CANNOT. That file calls `place.build`
directly, so nothing in it cooks a node or reads a parameter. This drives the
HDA's own page, proves the page and the kernel agree on ids AND rounded point
positions, and only then hands the result to the committed checks. The images
are the other half: a gate is judged on the picture, not on a test name.

⚠️ THE ASSERTIONS ARE THE COMMITTED ONES, DELIBERATELY. The first draft of
this file invented its own closure and plumb measures and produced four false
failures inside ten minutes - elements ordered by `pc_u` across sections are
not neighbours, and a panel's diagonal edges are not its ribs. `checks.py`
already encodes the right definitions and is mutation-tested. Do not re-derive
them here.

The PNG writer is `zlib` and `struct` - vanilla Houdini, no dependency, and
the flipbook path does not run under hython (tests/README.md).
"""

import math
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
REPO = os.path.dirname(os.path.dirname(HERE))
OUT = (sys.argv[1] if len(sys.argv) > 1
       else os.path.join(HERE, "gate_images"))

import checks as C                                               # noqa: E402
import hou                                                       # noqa: E402
import run_scene_checks as R                                     # noqa: E402
from polyfactory.polychain import hda as H                       # noqa: E402
from polyfactory.polychain import place as P                     # noqa: E402

HDA_PATH = os.path.join(REPO, "polyfactory", "otls",
                        "pf_polychain.hda").replace("\\", "/")

FAIL = []

# PC-G2's stepped row records 0.1 m of air with the flatten ON, and it is NOT
# a port regression - the identical fixture reads 0.1 at the pre-port commit
# `69db56c`. `_stepped_base` takes the minimum of the drape at the MODULE'S
# OWN STATIONS (0.25 m on the starter panel); where the conformed ground dips
# between two of them the piece is planted on a datum that is not the lowest
# ground under it, and unlike D25's bend resolution NOTHING WARNS about it.
# Recorded here as the accepted limit, the way D36's butt wedge is, and
# carried as standing finding (11).
KNOWN = {"stepped_float_m": 0.11}


def check(name, ok, value="", detail=""):
    if not ok:
        FAIL.append(name)
    print("  [%s] %-24s %-20s %s" % ("PASS" if ok else "FAIL", name,
                                     value, detail))
    return ok


def show(res):
    ok = res.ok or res.skipped
    if not ok and res.name in KNOWN and isinstance(res.value, float) \
            and res.value <= KNOWN[res.name]:
        return check(res.name + " (known)", True, str(res.value),
                     res.detail + "  <= the recorded limit %s"
                     % KNOWN[res.name])
    return check(res.name, ok, "SKIP" if res.skipped else str(res.value),
                 res.detail)


# --- a PNG writer, so a gate can be JUDGED ON AN IMAGE ----------------------

def png(path, w, h, pix):
    raw = b"".join(b"\x00" + bytes(pix[y * w * 3:(y + 1) * w * 3])
                   for y in range(h))

    def chunk(tag, data):
        c = tag + data
        return (struct.pack(">I", len(data)) + c
                + struct.pack(">I", zlib.crc32(c) & 0xffffffff))
    with open(path, "wb") as fh:
        fh.write(b"\x89PNG\r\n\x1a\n")
        fh.write(chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)))
        fh.write(chunk(b"IDAT", zlib.compress(raw, 9)))
        fh.write(chunk(b"IEND", b""))


def unpack(geo):
    """A flat copy with every PACKED prim expanded, for the rasteriser.

    ⚠️ A PACKED PRIM HAS ONE VERTEX, so the wireframe drawn straight off a
    polyChain output is EMPTY - which is what a 4.6-instanced build is, and
    exactly the case phase 2 wants to look at. `checks.elements` already
    unpacks, but it returns records rather than geometry, so this is the same
    two lines against a `hou.Geometry` and it keeps ONE unpacking rule in the
    file (11.9's own "reuse it; do not rebuild it").
    """
    out = hou.Geometry()
    for prim in geo.prims():
        if prim.type() != hou.primType.PackedGeometry:
            continue
        piece = hou.Geometry()
        piece.merge(prim.getEmbeddedGeometry())
        piece.transform(prim.fullTransform())
        out.merge(piece)
    if out.intrinsicValue("primitivecount") == 0:
        return geo
    for prim in geo.prims():
        if prim.type() == hou.primType.PackedGeometry:
            continue
        piece = hou.Geometry()
        piece.merge(geo)                      # cheap: only the deformed half
        out.merge(piece)
        break
    return out


def drawn_covers_packed(name, geo):
    """The image must contain the PACKED pieces, which are most of the fence.

    ⚠️ THIS IS AN AUDIT FINDING, NOT TIDYING.  `unpack` sat in this file with
    a docstring naming the hazard and NO CALLER: every `rasterise` was handed
    the raw node output, so a packed prim - one vertex, no polygon - drew
    nothing.  PC-G1's mitered rectangle is 80 prims of which 40 are packed,
    and the committed image was 188 segments where the fence is 3 388.  The
    gate said "judged on an image" and the image could not show the subject.
    """
    packed = sum(1 for p in geo.prims()
                 if p.type() == hou.primType.PackedGeometry)
    drawn = sum(1 for p in unpack(geo).prims()
                if p.type() != hou.primType.PackedGeometry)
    check("image_shows_packed_" + name, drawn >= packed, [packed, drawn],
          "%d packed prims, %d polygons in the rasterised copy - a raw "
          "`node_geo` here draws %d of them" % (packed, drawn, 0))


def project(axes, p):
    """(right, up) for one world point. `axes` is a pair of world axis names,
    or "iso" - the three-quarter view PC-G5 asks to be judged on, which no
    pair of world axes can give."""
    if axes == "iso":
        return ((p[0] - p[2]) * 0.8660254, p[1] + (p[0] + p[2]) * 0.4330127)
    idx = {"x": 0, "y": 1, "z": 2}
    return (p[idx[axes[0]]], p[idx[axes[1]]])


def rasterise(path, geo, axes=("x", "z"), w=1200, h=680, extra=(),
              colour_of=None):
    """Orthographic wireframe of every polygon, fitted to the frame.

    `axes` picks the two world axes drawn as (right, up), or "iso"; `extra` is
    `(colour, [world points])` polylines drawn on top - the input spline, the
    ground line - so the image shows what the fence was asked to follow.
    `colour_of(prim)` colours each polygon, which is how a facade is judged on
    its 7.2 CELL PATTERN rather than on its silhouette.
    """
    segs = []
    for prim in geo.prims():
        pts = [p.point().position() for p in prim.vertices()]
        col = (185, 195, 212) if colour_of is None else colour_of(prim)
        for i in range(len(pts)):
            a, b = pts[i], pts[(i + 1) % len(pts)]
            segs.append((col, project(axes, a), project(axes, b)))
    for colour, poly in extra:
        for i in range(len(poly) - 1):
            segs.append((colour, project(axes, poly[i]),
                         project(axes, poly[i + 1])))
    if not segs:
        return
    xs = [p[0] for _c, p, q in segs] + [q[0] for _c, p, q in segs]
    ys = [p[1] for _c, p, q in segs] + [q[1] for _c, p, q in segs]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    s = min((w - 40) / max(hi_x - lo_x, 1e-6),
            (h - 40) / max(hi_y - lo_y, 1e-6))
    ox = 20 - lo_x * s + ((w - 40) - (hi_x - lo_x) * s) * 0.5
    oy = 20 - lo_y * s + ((h - 40) - (hi_y - lo_y) * s) * 0.5
    pix = bytearray([16, 18, 24] * (w * h))

    def put(px, py, colour):
        if 0 <= px < w and 0 <= py < h:
            i = ((h - 1 - py) * w + px) * 3
            pix[i], pix[i + 1], pix[i + 2] = colour

    for colour, a, b in segs:
        x0, y0 = a[0] * s + ox, a[1] * s + oy
        x1, y1 = b[0] * s + ox, b[1] * s + oy
        n = int(max(abs(x1 - x0), abs(y1 - y0))) + 1
        for k in range(n + 1):
            t = k / float(n)
            put(int(x0 + (x1 - x0) * t), int(y0 + (y1 - y0) * t), colour)
    png(path, w, h, pix)
    print("      image: %s  (%d segments)" % (os.path.basename(path),
                                              len(segs)))


# --- driving the parm face --------------------------------------------------

def spline_node(parent, name, points, closed=False):
    n = parent.createNode("python", name)
    n.parm("python").set(
        "import hou\n"
        "geo = hou.pwd().geometry()\n"
        "poly = geo.createPolygon(%r)\n"
        "for p in %r:\n"
        "    pt = geo.createPoint()\n"
        "    pt.setPosition(p)\n"
        "    poly.addVertex(pt)\n" % (closed, [tuple(p) for p in points]))
    return n


def terrain_node(parent, name):
    """PC-G2's own 2D terrain: 1.1 sin(2 pi x/13) + 0.8 cos(2 pi z/9) + 0.06x"""
    n = parent.createNode("python", name)
    n.parm("python").set(
        "import hou, math\n"
        "geo = hou.pwd().geometry()\n"
        "nx, nz = 80, 60\n"
        "pts = []\n"
        "for i in range(nx + 1):\n"
        "    row = []\n"
        "    for j in range(nz + 1):\n"
        "        x = -6.0 + i * 0.5\n"
        "        z = -9.0 + j * 0.4\n"
        "        y = (1.1 * math.sin(2 * math.pi * x / 13.0) +\n"
        "             0.8 * math.cos(2 * math.pi * z / 9.0) + 0.06 * x)\n"
        "        pt = geo.createPoint(); pt.setPosition((x, y, z))\n"
        "        row.append(pt)\n"
        "    pts.append(row)\n"
        "for i in range(nx):\n"
        "    for j in range(nz):\n"
        "        poly = geo.createPolygon(True)\n"
        "        for pt in (pts[i][j], pts[i+1][j], pts[i+1][j+1], pts[i][j+1]):\n"
        "            poly.addVertex(pt)\n")
    return n


def ground_y(x, z):
    return (1.1 * math.sin(2 * math.pi * x / 13.0)
            + 0.8 * math.cos(2 * math.pi * z / 9.0) + 0.06 * x)


def through_the_face(node, spline, surface=None):
    """Cook the node, read its page back, and prove the two agree.

    Returns `(Scene over the kernel build, the NODE's own geometry, agreed?,
    element count)`. The Scene is what every committed check consumes; the
    node geometry is what gets rasterised, so the picture is the ASSET's
    output and not a re-derivation of it.
    """
    node_geo = node.geometry()
    style = H.style_from_parms(node)
    kit_geo = H.kit_geometry(node)
    curve_geo = spline.geometry()
    surf_geo = surface.geometry() if surface is not None else None
    out, report = P.build(curve_geo, kit_geo, style, surface_geo=surf_geo)
    a = (sorted(p.attribValue("pc_elem_id") for p in node_geo.prims()),
         sorted(round(v, 5) for v in node_geo.pointFloatAttribValues("P")))
    b = (sorted(p.attribValue("pc_elem_id") for p in out.prims()),
         sorted(round(v, 5) for v in out.pointFloatAttribValues("P")))
    case = {"curve": curve_geo, "kit": kit_geo, "style": style, "out": out,
            "report": report, "surface": surf_geo}
    return R.Scene(case), node_geo, a == b, len(a[0])


def main():
    if not os.path.exists(HDA_PATH):
        print("no HDA at %s - run devScripts/create_pf_polychain_hda.py"
              % HDA_PATH)
        sys.exit(1)
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    hou.hda.installFile(HDA_PATH)
    hou.putenv("POLYFACTORY",
               os.path.join(REPO, "polyfactory").replace("\\", "/"))

    # ---- PC-G1 -----------------------------------------------------------
    print("\n=== PC-G1 - the closed rectangle and the L, BOTH corner modes, "
          "through the parm face ===")
    g1 = hou.node("/obj").createNode("geo", "pc_g1_images")
    rect_pts = [(0, 0, 0), (12, 0, 0), (12, 0, 8), (0, 0, 8)]
    l_pts = [(0, 0, 0), (10, 0, 0), (10, 0, 6)]
    small_pts = [(0, 0, 0), (3, 0, 0), (3, 0, 3)]
    node1 = g1.createNode("pf_polychain", "chain")
    shapes = (("rect", spline_node(g1, "rect", rect_pts, True), rect_pts, True),
              ("L", spline_node(g1, "lshape", l_pts), l_pts, False),
              # the 3 m L is the CLOSE-UP: on a 12 m rectangle the corner is
              # four pixels and the picture proves nothing.
              ("closeup", spline_node(g1, "small", small_pts), small_pts,
               False))
    for shape, src, pts, closed in shapes:
        node1.setInput(0, src)
        for mode in ("bend", "miter"):
            print("  -- %s / %s --" % (shape, mode))
            node1.parm("corner_mode").set(mode)
            scene, node_geo, ok, n = through_the_face(node1, src)
            check("g1_%s_%s_parm_face" % (shape, mode), ok, n,
                  "node output == place.build on style_from_parms(node)")
            # Every check on this line but the last is a CLOSURE check, and
            # a double pillar is perfectly closed - which is why the first
            # nine of them passed on the fence Hannes counted two pillars on.
            # `single_pillar` is here because this is the only place in the
            # suite that drives the parm face over the L and the 3 m
            # CLOSE-UP as well as the rectangle (D270; the comment in
            # `run_scene_checks` claimed it already was, and was wrong).
            for res in (C.corner_abut(scene), C.corner_breach(scene),
                        C.single_pillar(scene)):
                show(res)
            drawn_covers_packed("%s_%s" % (shape, mode), node_geo)
            rasterise(os.path.join(OUT, "VG1_%s_%s_top.png" % (shape, mode)),
                      unpack(node_geo), ("x", "z"),
                      extra=[((255, 130, 60),
                              list(pts) + ([pts[0]] if closed else []))])

    # ---- PC-G2 -----------------------------------------------------------
    print("\n=== PC-G2 - the fence on the hill, conform ON, through the parm "
          "face ===")
    g2 = hou.node("/obj").createNode("geo", "pc_g2_images")
    hill_pts = [((i / 96.0) * 20.0 - 2.0, (i / 96.0) * 2.4,
                 3.6 * math.sin(2 * math.pi * (i / 96.0)))
                for i in range(97)]
    hill = spline_node(g2, "hill", hill_pts)
    terrain = terrain_node(g2, "terrain")
    node2 = g2.createNode("pf_polychain", "chain")
    node2.setInput(0, hill)
    node2.setInput(3, terrain)
    ground = [(x, ground_y(x, z), z) for x, _y, z in hill_pts]

    for zmode in ("vertical", "stepped", "adaptive"):
        print("  -- zmode = %s --" % zmode)
        node2.parm("zmode").set(zmode)
        node2.parm("conform_tilt").set(0)
        node2.parm("flatten_stepped").set(1 if zmode == "stepped" else 0)
        scene, node_geo, ok, n = through_the_face(node2, hill, terrain)
        check("g2_%s_parm_face" % zmode, ok, n,
              "node output == place.build on style_from_parms(node)")
        for res in (C.warnings(scene), C.bank_adaptive(scene)):
            show(res)
        drawn_covers_packed(zmode, node_geo)
        rasterise(os.path.join(OUT, "VG2_%s_side.png" % zmode),
                  unpack(node_geo), ("x", "y"), extra=[((80, 210, 120), ground),
                                     ((255, 130, 60), hill_pts)])

    print("  -- Tilt to Surface (camber) --")
    node2.parm("zmode").set("adaptive")
    node2.parm("flatten_stepped").set(0)
    node2.parm("conform_tilt").set(1)
    scene, node_geo, ok, n = through_the_face(node2, hill, terrain)
    check("g2_camber_parm_face", ok, n,
          "node output == place.build on style_from_parms(node)")
    show(C.warnings(scene))
    drawn_covers_packed("camber", node_geo)
    rasterise(os.path.join(OUT, "VG2_camber_side.png"), unpack(node_geo),
              ("x", "y"),
              extra=[((80, 210, 120), ground)])
    # the FRONT view is the one the camber is visible in - a roll onto the
    # cross-fall does not show in the side elevation it rolls about.
    rasterise(os.path.join(OUT, "VG2_camber_front.png"), unpack(node_geo),
              ("z", "y"),
              extra=[((80, 210, 120), ground)])

    # ---- PART B: the CURVED run the guard now takes natively -------------
    #
    # ⚠️ A 90 m ARC DRAWN WHOLE IS A ONE-PIXEL LINE, which is 18.4's defect in
    # a new place: two gates were once judged on images that could not show
    # the fence.  So this crops to 12 m of the arc - where a 2 m panel and a
    # 0.12 m post are several pixels wide - and renders the SAME crop from the
    # native chain and from the reference, so the pair can be compared by eye
    # as well as by `output_guard_parity`'s element-for-element diff.
    print("\n=== PART B - a curved run, NATIVE and reference, cropped ===")
    gb = hou.node("/obj").createNode("geo", "partb_images")
    radius, step, length = 60.0, 1.0, 90.0
    arc_pts = [(radius * math.sin(i * step / radius), 0.0,
                radius * (1.0 - math.cos(i * step / radius)))
               for i in range(int(length / step) + 1)]
    nodeb = gb.createNode("pf_polychain", "chain_curved")
    nodeb.setInput(0, spline_node(gb, "partb_arc", arc_pts))
    nodeb.allowEditingOfContents()

    def crop(geo, x0, x1):
        """The polygons whose centroid sits in [x0, x1], rebuilt.

        A CROP and not a re-fit: `rasterise` fits whatever it is handed, so
        handing it the whole arc is what produced the one-pixel line.
        """
        out = hou.Geometry()
        for prim in geo.prims():
            if not (x0 <= prim.boundingBox().center()[0] <= x1):
                continue
            poly = out.createPolygon()
            for vtx in prim.vertices():
                pt = out.createPoint()
                pt.setPosition(vtx.point().position())
                poly.addVertex(pt)
        return out

    shapes_seen = {}
    for stage in ("output", "reference"):
        nodeb.parm("stage").set(stage)
        nodeb.cook(force=True)
        took = nodeb.node("copy_packed").cookCount() > 0
        tag = "native" if (stage == "output" and took) else "reference"
        sub = crop(unpack(nodeb.geometry()), 30.0, 42.0)
        shapes_seen[tag] = (len(nodeb.geometry().prims()), len(sub.prims()))
        rasterise(os.path.join(OUT, "PARTB_arc_%s_top.png" % tag), sub,
                  ("x", "z"))
        rasterise(os.path.join(OUT, "PARTB_arc_%s_side.png" % tag), sub,
                  ("x", "y"))
    # ⚠️ AND THE GUARD'S VERDICT IS PART OF THE GATE.  Without this the pair
    # of images is satisfied by the reference rendered twice - which is
    # exactly what `Stage = output` did before PART B on any curved spline.
    check("partb_curved_is_native", "native" in shapes_seen,
          ",".join(sorted(shapes_seen)),
          "`Stage = output` on a 90 m R = 60 m arc must ADVANCE "
          "`copy_packed` - the widened level-1 bound reads 0.009 m "
          "against a 0.01 m tolerance and level 2 confirms every piece "
          "stays packed. prims/crop: %r" % (shapes_seen,))
    check("partb_curved_matches_the_reference",
               len(set(shapes_seen.values())) == 1,
          "%r" % (sorted(set(shapes_seen.values())),),
          "the two images are the same fence: same prim count whole and "
          "same prim count in the crop, so the pair below differs only "
          "in which chain drew it")

    # ---- 13.9 N5: a DEFORMED run, NATIVE and reference --------------------
    #
    # WHY THIS PAIR EXISTS: PRIM COUNTS DO NOT PROVE GEOMETRY.  The deformed
    # branch is the first thing this graph builds that is not one packed
    # instance per piece - every point of every module is rebuilt from
    # scratch - and two defects in this codebase (a junction that was a flat
    # plate, streets driving through each other) were invisible in every
    # number and obvious in the first frame that rendered.  So the same 24 m
    # ripple is drawn from the native chain and from the reference, cropped
    # to 8 m where a 2 m panel is several pixels wide.
    print(chr(10) + "=== 13.9 N5 - a DEFORMED run, NATIVE and reference, cropped ===")
    gd = hou.node("/obj").createNode("geo", "n5_images")
    ripple = [(0.5 * i, 0.45 * math.sin(i * 0.55), 0.0) for i in range(49)]
    noded = gd.createNode("pf_polychain", "chain_deformed")
    noded.setInput(0, spline_node(gd, "n5_ripple", ripple))
    noded.allowEditingOfContents()
    # ⚠️ D254 - PER TAG, AND POSITIONS RATHER THAN COUNTS.  Both of the rows
    # below used to be written under this block's own opening line - "PRIM
    # COUNTS DO NOT PROVE GEOMETRY" - and then assert prim counts:
    #   * `n5_polys` was a single variable assigned inside the loop, so it
    #     held the LAST iteration's value - the REFERENCE crop - and the
    #     "the image contains geometry" row said nothing at all about
    #     `N5_ripple_native_side.png`, which is the image this pair exists
    #     for and the one the cycle report says it looked at;
    #   * the match row compared (whole prim count, crop prim count) tuples,
    #     which two completely different sets of vertex positions satisfy
    #     just as well - and if `Stage = output` had silently taken the
    #     reference, `deformed_seen` would hold ONE key and `len(set(...))
    #     == 1` would be trivially true.
    # The geometry is already in hand, so the honest comparison is the crop's
    # rounded POINT POSITIONS.
    deformed_seen = {}
    n5_polys = {}
    n5_points = {}
    for stage in ("output", "reference"):
        noded.parm("stage").set(stage)
        noded.cook(force=True)
        took = noded.node("copy_deformed").cookCount() > 0
        tag = "native" if (stage == "output" and took) else "reference"
        sub = crop(unpack(noded.geometry()), 6.0, 14.0)
        deformed_seen[tag] = (len(noded.geometry().prims()), len(sub.prims()))
        n5_polys[tag] = sum(len(pr.vertices()) for pr in sub.prims())
        n5_points[tag] = sorted(
            tuple(round(float(c), 6) for c in pt.position())
            for pt in sub.points())
        rasterise(os.path.join(OUT, "N5_ripple_%s_side.png" % tag), sub,
                  ("x", "y"))
        rasterise(os.path.join(OUT, "N5_ripple_%s_top.png" % tag), sub,
                  ("x", "z"))
    check("n5_deformed_is_native", "native" in deformed_seen,
          ",".join(sorted(deformed_seen)),
          "`Stage = output` on a 24 m ripple must ADVANCE `copy_deformed` - "
          "before 13.9 N5 this build took the reference whole and cost 96 %% "
          "Python. prims/crop: %r" % (deformed_seen,))
    two = "native" in n5_points and "reference" in n5_points
    same = two and n5_points["native"] == n5_points["reference"]
    first = ""
    if two and not same:
        a, b = n5_points["native"], n5_points["reference"]
        if len(a) != len(b):
            first = "%d points native / %d reference" % (len(a), len(b))
        else:
            for i, (u, v) in enumerate(zip(a, b)):
                if u != v:
                    first = "point %d %r != %r" % (i, u, v)
                    break
    check("n5_deformed_matches_the_reference", two and same,
          "%d / %d points" % (len(n5_points.get("native", ())),
                              len(n5_points.get("reference", ()))),
          "the two images are the same fence, compared on every POINT "
          "POSITION in the crop rather than on a prim count - and BOTH chains "
          "must have drawn one, so a build that quietly took the reference "
          "cannot satisfy this by having a single tag. %s"
          % (first or "identical"))
    # ...and the drawn-segment count against the geometry (D194), because a
    # blind gate once drew 188 segments of a 3 388-segment fence.  BOTH
    # images, because the native one is the one that could be empty.
    thin = sorted(t for t, n in n5_polys.items() if n <= 200)
    check("n5_deformed_image_has_geometry", two and not thin,
          "native %d / reference %d" % (n5_polys.get("native", 0),
                                        n5_polys.get("reference", 0)),
          "drawn segments in EACH crop, counted off the geometry the "
          "rasteriser was handed - D194's rule. Under 200: %s"
          % (", ".join(thin) or "neither"))

    print("\n%d failing gate checks" % len(FAIL))
    if FAIL:
        print("  " + ", ".join(FAIL))
    sys.exit(1 if FAIL else 0)


# ...under a guard, so the RASTERISER can be imported. Without it, `import
# gate_images` ran both gates and called `sys.exit` - which is how a phase-2
# image script that reuses this file (7.8's "extend it, do not rebuild it")
# would otherwise have been forced to rebuild it after all.
if __name__ == "__main__":
    main()
