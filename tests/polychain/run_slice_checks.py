"""7.7's kit on-ramp - `pf_polychain_slice`, cooked headlessly.

    hython tests/polychain/run_slice_checks.py

The differential oracle here is the tool's own inverse: author a kit, TILE it
into one chunk, slice the chunk, and the modules must come back. That is
stronger than any assertion list because it compares the whole module - every
point of it - against something written independently of the slicer, and it
is the only shape in which "the pieces refit" is a fact rather than a hope.

Then the union (dev-loop check 1): the recovered kit is fed to the SHIPPED
`pf_polychain` asset beside the authored one, and the two fences must be the
same fence. A slicer that emits a valid-looking kit whose modules are placed
half a bay off passes every kit-level check and fails this one.

WHAT THIS CANNOT SEE:
  * the INTERIOR tessellation of a module. `clip` deletes polygons lying on
    the plane and `polyfill` replaces them with one n-gon, so a face divided
    into four quads comes back as one - measured, not assumed (18 prims ->
    12 on the smoke fixture). The POINTS are preserved exactly, so every
    comparison here is on point sets and never on prim counts.
  * whether a human likes the result. The images are rendered and the
    viewport pass stays OWED.
"""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import diff                                                      # noqa: E402
import gate_images as GI                                          # noqa: E402
import hou                                                        # noqa: E402
from polyfactory.polychain import Params, Rule, Style              # noqa: E402
from polyfactory.polychain import facade as F                      # noqa: E402
from polyfactory.polychain import kit as K                        # noqa: E402
from polyfactory.polychain import slicer as S                     # noqa: E402

REPO = os.path.dirname(os.path.dirname(HERE))
OTLS = os.path.join(REPO, "polyfactory", "otls").replace("\\", "/")
SLICE_HDA = OTLS + "/pf_polychain_slice.hda"
CHAIN_HDA = OTLS + "/pf_polychain.hda"
IMAGES = os.path.join(HERE, "gate_images").replace("\\", "/")

W, H, D = 2.0, 3.0, 0.4          # one bay, one storey, the wall's depth
ROLES = ("start_start", "default_start", "end_start",
         "start", "default", "end",
         "start_end", "default_end", "end_end")

RESULTS = []


def check(name, ok, value="", detail=""):
    RESULTS.append((name, bool(ok), value, detail))
    print("  [%s] %-34s %s  %s" % ("PASS" if ok else "FAIL", name, value,
                                   detail))
    return ok


# --- the fixture: nine authored modules, and the chunk they tile into -------

def authored_kit():
    """A 3 x 3 facade kit, every module a different SHAPE so a slicer that
    returns the right count of the wrong pieces cannot pass."""
    geo = hou.Geometry()
    for i, role in enumerate(ROLES):
        col, row = i % 3, i // 3
        m = hou.Geometry()
        # the wall plane, full bay, full storey - what makes the cells mate
        K.box_mesh(m, 0.0, W, 0.0, H, -0.05, 0.05, 2 + col)
        # a band of relief unique to this cell, so the nine differ
        r = hou.Geometry()
        K.box_mesh(r, 0.2 + 0.1 * col, W - 0.2, 0.3 + 0.2 * row,
                   H - 0.4 - 0.1 * row, 0.05, D / 2.0, 1)
        m.merge(r)
        # pc_size.z is the module's DEPTH and the slicer measures it off the
        # geometry, so the fixture states the geometry's own depth rather
        # than a round number - the check compares all three components.
        K.add_module(geo, role, m, size=(W, H, D / 2.0 + 0.05), deform=0,
                     zmode="adaptive", roles=role)
    K.write_manifest(geo, "hand_facade", 1, sources=("run_slice_checks",),
                     human_scale_reference=1.8)
    return geo


def tiled_chunk(kit_geo):
    """The nine modules laid out 3 x 3 - ONE chunk, exactly what an artist
    models by hand."""
    geo = hou.Geometry()
    for i, prim in enumerate(kit_geo.prims()):
        piece = hou.Geometry()
        piece.merge(prim.getEmbeddedGeometry())
        piece.transform(hou.hmath.buildTranslate((i % 3) * W, (i // 3) * H,
                                                 0.0))
        geo.merge(piece)
    return geo


def module_points(kit_geo):
    """{name: sorted rounded point positions} - the retessellation-proof
    fingerprint of every module in a kit."""
    out = {}
    for prim in kit_geo.prims():
        src = prim.getEmbeddedGeometry()
        flat = list(src.pointFloatAttribValues("P"))
        out[prim.points()[0].attribValue("pc_name")] = sorted(
            tuple(round(v, 6) for v in flat[3 * i:3 * i + 3])
            for i in range(src.intrinsicValue("pointcount")))
    return out


def module_attr(kit_geo, name):
    return dict((p.points()[0].attribValue("pc_name"),
                 p.points()[0].attribValue(name)) for p in kit_geo.prims())


def slice_of(chunk, **kw):
    cells, w1 = S.plan((chunk.boundingBox().minvec()[0],
                        chunk.boundingBox().maxvec()[0],
                        chunk.boundingBox().minvec()[1],
                        chunk.boundingBox().maxvec()[1]), **kw)
    pairs, w2 = K.slice_cells(chunk, cells)
    geo, w3 = K.slice_kit(pairs, "sliced_facade")
    return (cells, pairs, geo, w1 + w2 + w3)


# --- the fence both kits are asked to build ---------------------------------

def chain_node(geo_node, name, kit_geo, tag):
    kit = geo_node.createNode("python", "kit_" + tag)
    path = os.path.join(hou.text.expandString("$TEMP"),
                        "pc_slice_%s.bgeo" % tag).replace("\\", "/")
    kit_geo.saveToFile(path)
    kit.parm("python").set(
        "import hou\nhou.pwd().geometry().loadFromFile(%r)\n" % path)
    curve = GI.spline_node(geo_node, "curve_" + tag,
                           [(0, 0, 0), (3 * W, 0, 0)])
    node = geo_node.createNode("pf_polychain", name)
    node.setInput(0, curve)
    node.setInput(1, kit)
    for parm, value in (("slot_default", "default"), ("slot_start", "start"),
                        ("slot_end", "end"), ("slot_evenly", ""),
                        ("slot_corner", ""), ("slot_marker", "")):
        node.parm(parm).set(value)
    return node


def unpacked_points(geo):
    flat = list(GI.unpack(geo).pointFloatAttribValues("P"))
    return sorted(tuple(round(v, 5) for v in flat[3 * i:3 * i + 3])
                  for i in range(len(flat) // 3))


# --- the shipped node, driven by its own parameters -------------------------

def slice_node(geo_node, name, chunk_geo, guides=None, **parms):
    src = geo_node.createNode("python", "chunk_" + name)
    path = os.path.join(hou.text.expandString("$TEMP"),
                        "pc_chunk_%s.bgeo" % name).replace("\\", "/")
    chunk_geo.saveToFile(path)
    src.parm("python").set(
        "import hou\nhou.pwd().geometry().loadFromFile(%r)\n" % path)
    node = geo_node.createNode("pf_polychain_slice", name)
    node.setInput(0, src)
    if guides:
        g = geo_node.createNode("python", "guides_" + name)
        g.parm("python").set(
            "import hou\n"
            "geo = hou.pwd().geometry()\n"
            "geo.addAttrib(hou.attribType.Point, 'N', (0.0, 0.0, 0.0))\n"
            "geo.addAttrib(hou.attribType.Point, 'pc_slot', '')\n"
            "for p, n, s in %r:\n"
            "    pt = geo.createPoint()\n"
            "    pt.setPosition(p)\n"
            "    pt.setAttribValue('N', n)\n"
            "    pt.setAttribValue('pc_slot', s)\n" % (guides,))
        node.setInput(1, g)
    for parm, value in parms.items():
        node.parm(parm).set(value)
    return node


def main():
    for path in (SLICE_HDA, CHAIN_HDA):
        if not os.path.exists(path):
            print("no HDA at %s - run its devScripts builder" % path)
            sys.exit(1)
        hou.hda.installFile(path)
    hou.putenv("POLYFACTORY",
               os.path.join(REPO, "polyfactory").replace("\\", "/"))
    obj = hou.node("/obj")
    geo_node = obj.createNode("geo", "_slice_checks")

    hand = authored_kit()
    chunk = tiled_chunk(hand)
    cells, pairs, sliced, warns = slice_of(chunk, xsize=W, ysize=H)

    # 1. THE ORACLE - every module, every point, back out of the chunk.
    want, got = module_points(hand), module_points(sliced)
    missing = sorted(set(want) - set(got))
    dev = 0.0
    for name in sorted(set(want) & set(got)):
        a, b = want[name], got[name]
        if len(a) != len(b):
            dev = float("inf")
            continue
        dev = max([dev] + [abs(p[k] - q[k]) for p, q in zip(a, b)
                           for k in range(3)])
    check("slice_recovers_the_authored_kit", not missing and dev <= 1e-6,
          "%.3e m" % dev,
          "%d modules; missing %s" % (len(got), missing or "none"))
    check("slice_keeps_the_manifest",
          not K.validate(sliced) and not warns
          and module_attr(sliced, "pc_role") == module_attr(hand, "pc_role")
          and module_attr(sliced, "pc_size") == module_attr(hand, "pc_size"),
          "%d warn" % (len(K.validate(sliced)) + len(warns)),
          "; ".join(K.validate(sliced) + warns)[:90] or "3.2 complete")

    # 2. D131's JIGSAW, on a chunk whose bands are NOT already equal - the
    #    even fixture above cannot fail this and would be decoration.
    uneven = [("x", 1.3, ""), ("x", 3.1, ""), ("x", 4.4, "")]
    _c, _p, ukit, _w = slice_of(chunk, xsize=0.0, ysize=H, guides=uneven)
    sizes = module_attr(ukit, "pc_size")
    fill = [v for k, v in sizes.items()
            if S.split_role(k.split("_2")[0])[0] not in S.CAPS]
    spread = (max(v[0] for v in fill) - min(v[0] for v in fill)) if fill else -1
    check("slice_jigsaw_size_m", 0.0 <= spread <= 1e-6, "%.3e m" % spread,
          "%d fill cells of %d, bands 1.30 / 1.80 / 1.30 wide before the "
          "jigsaw" % (len(fill), len(sizes)))

    # 3. THE REFIT - the two sides of every cut plane, measured on geometry.
    gap, seen = 0.0, 0
    byband = dict(((round(c.x0, 6), round(c.y0, 6)), g) for c, g in pairs)
    for cell, geo in pairs:
        right = byband.get((round(cell.x1, 6), round(cell.y0, 6)))
        if right is None:
            continue
        a = _plane_points(geo, 0, cell.x1)
        b = _plane_points(right, 0, cell.x1)
        if not a or not b:
            continue
        seen += 1
        gap = max(gap, _hausdorff(a, b))
    check("slice_refit_gap_m", seen >= 6 and gap <= 1e-6, "%.3e m" % gap,
          "%d cut-plane pairs measured (0 would make this vacuous)" % seen)

    # 4. THE UNION - the same fence, from both kits, through the shipped node.
    a_node = chain_node(geo_node, "chain_hand", hand, "hand")
    b_node = chain_node(geo_node, "chain_sliced", sliced, "sliced")
    ga, gb = a_node.geometry(), b_node.geometry()
    bad = diff.compare(diff.snapshot(ga, packed_depth=0),
                       diff.snapshot(gb, packed_depth=0), tol=1e-6)
    same_pts = unpacked_points(ga) == unpacked_points(gb)
    check("sliced_kit_builds_the_same_fence",
          not bad and same_pts and ga.intrinsicValue("primitivecount") > 0,
          "%d prim" % ga.intrinsicValue("primitivecount"),
          ("points differ; " if not same_pts else "")
          + ("; ".join(bad[:2]) if bad else "identical"))

    # 5. THE SHIPPED NODE, with nothing set but a wire (6's floor).
    node = slice_node(geo_node, "defaults", chunk)
    out = node.geometry()
    if out is None:
        check("slice_defaults_build_a_kit", False, "no geometry",
              "; ".join(node.errors())[:200])
        sys.exit(1)
    roles = sorted(module_attr(out, "pc_role").values())
    check("slice_defaults_build_a_kit", roles == sorted(ROLES),
          "%d module" % len(roles), ", ".join(roles[:4]) + " ...")
    check("slice_hda_kit_is_valid", not K.validate(out),
          "%d warn" % len(K.validate(out)),
          "; ".join(K.validate(out))[:90] or "3.2 complete")

    # 6. A GUIDE NAMES A CELL - and the intersection cells come with it.
    #    This is the kit a CLOSED facade needs, and it is what the guide
    #    input is for: a closed footprint earns no run cap (D18), so the two
    #    X classes it asks for are `default` and `corner`.
    gnode = slice_node(
        geo_node, "guided", chunk,
        guides=[((2 * W, 0, 0), (1.0, 0.0, 0.0), "corner")],
        bay=W, storey=H, sides=0)
    gkit = gnode.geometry()
    groles = sorted(module_attr(gkit, "pc_role").values())
    want_g = sorted(["default", "corner", "default_start", "corner_start",
                     "default_end", "corner_end"])
    check("slice_guides_name_a_cell", groles == want_g,
          "%d module" % len(groles),
          "corner_start and corner_end are 7.2's intersection cells - the "
          "ones RailClone's generator has no slot for")

    # 7. THE VOID DETECTOR, proved non-vacuous on a chunk that HAS a void.
    holed = hou.Geometry()
    for i in range(3):
        p = hou.Geometry()
        K.box_mesh(p, 0.25, W - 0.25, 0.0, H, -0.05, 0.05, 1)
        p.transform(hou.hmath.buildTranslate(i * W, 0.0, 0.0))
        holed.merge(p)
    vnode = slice_node(geo_node, "voids", holed, bay=W, storey=0.0,
                       capstop=False)
    # ⚠️ THE WARNINGS ARE ON THE STAGE THAT RAISED THEM, and a subnet does not
    # copy a child's warnings into `warnings()` (probed) - the UI shows them
    # as the badge and the message an artist reads. Reading the stage inside
    # the SHIPPED instance is still the shipped artifact, not a rig.
    vnode.geometry()                     # warnings exist only after a cook
    said = [w for w in vnode.node("sl_kit").warnings()
            if "does not reach" in w]
    check("slice_reports_a_void",
          bool(said) and "0.5000 m of void" in said[0],
          "%d warn" % len(said),
          said[0][:80] if said else "the void detector said nothing")

    # 8. THE SECOND BRANCH - `Show = Where The Cuts Land` actually cooks.
    cnode = slice_node(geo_node, "cellview", chunk, show=1)
    cgeo = cnode.geometry()
    names = set(cgeo.primStringAttribValues("pc_cell")) \
        if cgeo.findPrimAttrib("pc_cell") else set()
    check("slice_cells_view_draws_every_cell",
          names == set(ROLES) and cgeo.intrinsicValue("primitivecount") > 0,
          "%d prim" % cgeo.intrinsicValue("primitivecount"),
          "%d cells drawn where they were cut" % len(names))

    # 9. 5.1's METADATA, read off the SAVED asset - never off this script.
    defn = hou.hda.definitionsInFile(SLICE_HDA)[0]
    ds = defn.sections()["DialogScript"].contents()
    ok = ("Poly Factory/Modeling" in
          defn.sections().get("Tools.shelf", _Empty()).contents()
          and defn.icon() == "SOP_clip"
          and 'inputlabel\t1\t"Chunk"' in ds
          and 'inputlabel\t2\t"Guides (optional)"' in ds
          and 'outputlabel\t1\t"Kit"' in ds)
    check("slice_hda_metadata", ok, defn.icon(),
          "TAB submenu, icon and every port label, off the .hda")

    # 10. THE FACADE - the nine cells doing the job they were sliced FOR.
    #     A 1D fence never asks for an intersection cell; a closed footprint
    #     four storeys tall asks for all nine, which is 7.2's whole point.
    fp = [(0, 0, 0), (3 * W, 0, 0), (3 * W, 0, 2 * W), (0, 0, 2 * W)]
    fgeo, freport = F.build(fp, gkit, _slice_style(), height=3 * H)
    cellset = set(p.cell for p in freport["plan"])
    fell = [k for k, v in (freport.get("role_fallbacks") or {}).items()
            if k != v and k in cellset]
    check("sliced_kit_fills_a_facade",
          cellset == set(want_g) and not fell,
          "%d cell" % len(freport["plan"]),
          "%d distinct roles, %d fallbacks - every cell a real module"
          % (len(cellset), len(fell)))

    # 11. THE IMAGES - and the count that proves they contain their subject.
    if not os.path.isdir(IMAGES):
        os.makedirs(IMAGES)
    drawn = GI.rasterise(IMAGES + "/PC-C1_cells.png", cgeo, ("x", "y"),
                         colour_of=_by_cell(cgeo))
    drawn2 = GI.rasterise(IMAGES + "/PC-C1_fence.png", GI.unpack(gb),
                          ("x", "y"))
    GI.rasterise(IMAGES + "/PC-C1_facade.png", GI.unpack(fgeo), "iso")
    # ⚠️ `nprim >= len(ROLES)` IS PART OF THE CHECK, NOT COLOUR. Without it a
    # preview that merged nothing scored `0 >= 4 * 0` and the image check
    # passed on a black frame - the exact failure the rule exists to stop.
    nprim = cgeo.intrinsicValue("primitivecount")
    check("slice_image_shows_the_kit",
          drawn >= 4 * nprim and nprim >= len(ROLES) and drawn2 > 0,
          "%d + %d seg" % (drawn, drawn2),
          "%d prims of %d cells drawn" % (nprim, len(names)))

    geo_node.destroy()
    bad_n = sum(1 for _n, ok, _v, _d in RESULTS if not ok)
    print("\n%d check(s), %d failure(s)" % (len(RESULTS), bad_n))
    sys.exit(1 if bad_n else 0)


class _Empty(object):
    def contents(self):
        return ""


def _slice_style():
    """The thinnest 7.3.2 payload that asks for all three row classes: no
    module NAMES anywhere, so the 25-role lattice is what picks the piece and
    a fallback would show up as one."""
    return Style("slice", 1, 7, rules=[
        Rule("default", "first", []), Rule("start", "first", []),
        Rule("end", "first", []), Rule("corner", "first", []),
        Rule("start", "first", [], axis="y"),
        Rule("default", "first", [], axis="y"),
        Rule("end", "first", [], axis="y"),
    ], params=Params(fill="adaptive", corner_mode="miter"))


def _by_cell(geo):
    names = sorted(set(geo.primStringAttribValues("pc_cell")))
    col = dict((n, (60 + (i * 97) % 190, 90 + (i * 53) % 160,
                    120 + (i * 31) % 130)) for i, n in enumerate(names))
    values = list(geo.primStringAttribValues("pc_cell"))
    return lambda prim: col.get(values[prim.number()], (200, 200, 200))


def _plane_points(geo, axis, value, tol=1e-6):
    flat = list(geo.pointFloatAttribValues("P"))
    out = []
    for i in range(len(flat) // 3):
        p = flat[3 * i:3 * i + 3]
        if abs(p[axis] - value) <= tol:
            out.append(tuple(round(v, 9) for v in p))
    return sorted(set(out))


def _hausdorff(a, b):
    """The worst distance from either point set to the nearest point of the
    other - the gap at a cut plane, in metres."""
    worst = 0.0
    for src, dst in ((a, b), (b, a)):
        for p in src:
            worst = max(worst, min(max(abs(p[k] - q[k]) for k in range(3))
                                   for q in dst))
    return worst


if __name__ == "__main__":
    main()
