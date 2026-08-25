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
import shutil
import sys
import tempfile

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
_SCRATCH = []


def scratch(name):
    """A geometry file NOBODY ELSE CAN WRITE.

    ⚠️ THIS WAS `$TEMP/pc_slice_<tag>.bgeo`, AND THE SWEEP CAUGHT IT. Under
    the parallel runner fifteen mutation items run at once, every one of them
    exporting `pc_slice_sliced.bgeo` to the SAME shared `$TEMP` - so a
    mutated item's kit was overwritten by a clean one before it could be
    loaded, and `sliced_kit_builds_the_same_fence` reported IDENTICAL on two
    mutations that had genuinely broken it. Two SURVIVED verdicts, both
    false, both from one shared filename. "Namespace scratchpad files per
    agent" is a standing project rule; it applies to processes too.
    """
    if not _SCRATCH:
        _SCRATCH.append(tempfile.mkdtemp(
            prefix="pc_slice_%d_" % os.getpid()).replace("\\", "/"))
    return "%s/%s.bgeo" % (_SCRATCH[0], name)


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
        # D20 SAYS A MODULE IS CENTRED ACROSS Z, and this fixture was not -
        # wall plane at 0, relief to +0.2, so its Z centre was 0.075. That is
        # what D272 now normalises, and a fixture that disagrees with the
        # frame it is testing is not a reference. Centred here, ONCE, off its
        # own bounds: the offset is not a magic number.
        zc = 0.5 * (m.boundingBox().minvec()[2] + m.boundingBox().maxvec()[2])
        m.transform(hou.hmath.buildTranslate(0.0, 0.0, -zc))
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


def module_points(kit_geo, dz=0.0):
    """{name: sorted rounded point positions} - the retessellation-proof
    fingerprint of every module in a kit. `dz` is D272's known Z offset."""
    out = {}
    for prim in kit_geo.prims():
        src = prim.getEmbeddedGeometry()
        flat = list(src.pointFloatAttribValues("P"))
        out[prim.points()[0].attribValue("pc_name")] = sorted(
            (round(flat[3 * i], 6), round(flat[3 * i + 1], 6),
             round(flat[3 * i + 2] + dz, 6))
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
    path = scratch("kit_" + tag)
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
    path = scratch("chunk_" + name)
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
            # `n = None` authors a guide with NO normal at all, which is the
            # commonest thing an artist hands this input.
            "if any(n is not None for _p, n, _s in %r):\n"
            "    geo.addAttrib(hou.attribType.Point, 'N', (0.0, 0.0, 0.0))\n"
            "geo.addAttrib(hou.attribType.Point, 'pc_slot', '')\n"
            "for p, n, s in %r:\n"
            "    pt = geo.createPoint()\n"
            "    pt.setPosition(p)\n"
            "    if n is not None:\n"
            "        pt.setAttribValue('N', n)\n"
            "    pt.setAttribValue('pc_slot', s)\n" % (guides, guides))
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
    #    D272 moves the kit to a canonical Z, and the offset is EXACT and
    #    known here, so the oracle stays exact: it is the authored module
    #    shifted by the chunk's own Z centre, not a comparison with Z dropped.
    zc = 0.5 * (chunk.boundingBox().minvec()[2]
                + chunk.boundingBox().maxvec()[2])
    want, got = module_points(hand, dz=-zc), module_points(sliced)
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
    #
    #    ⚠️ AGAINST THE NUMBER THE ARTIST TYPED, NOT AGAINST THE OTHER CELLS.
    #    This measured the SPREAD of the fill extents, and `axis_bands` sets
    #    every fill band to `a + w` by construction, so the spread is
    #    structurally zero and `0.000e+00 m` was a constant rather than
    #    evidence (worst 8.882e-16 over sixteen layouts, measured). 1.5 m is
    #    an input, not a derived quantity, and the bands it has to overrule
    #    are 1.30 / 1.80 / 1.30.
    #
    #    The CAP FLAGS come from the plan's own bands. Re-deriving them by
    #    `split_role`-ing the composed name read a cap as fill whenever a
    #    class did not parse.
    uneven = [("x", 1.3, ""), ("x", 3.1, ""), ("x", 4.4, "")]
    ucells, _p, ukit, _w = slice_of(chunk, xsize=1.5, ysize=H, guides=uneven)
    sizes = module_attr(ukit, "pc_size")
    fill = [sizes[c.name][0] for c in ucells if not c.xcap]
    dev = max(abs(v - 1.5) for v in fill) if fill else -1.0
    check("slice_jigsaw_size_m", len(fill) >= 2 and 0.0 <= dev <= 1e-6,
          "%.3e m" % dev,
          "%d fill cells of %d measured against the 1.5 m bay the artist "
          "asked for; the bands under it are 1.30 / 1.80 / 1.30"
          % (len(fill), len(sizes)))

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
    said = vnode.evalParm("notes")
    check("slice_reports_a_void",
          "does not reach" in said and "0.5000 m of void" in said,
          "%d char" % len(said),
          said[:80] if said else "the void detector said nothing")

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
    # ⚠️ `units` IS A PARMTAG. "(m)" in a LABEL is a caption an artist reads
    # and Houdini does not: no unit menu, no conversion of a typed `12in`.
    # All three lengths shipped without it while the cycle report called the
    # page "ranged/united/helped".
    ptg = defn.parmTemplateGroup()
    united = [p for p in ("bay", "storey", "humanscale")
              if ptg.find(p) is not None
              and ptg.find(p).tags().get("units") == "m"]
    ok = ("Poly Factory/Modeling" in
          defn.sections().get("Tools.shelf", _Empty()).contents()
          and defn.icon() == "SOP_clip"
          and 'inputlabel\t1\t"Chunk"' in ds
          and 'inputlabel\t2\t"Guides (optional)"' in ds
          and 'outputlabel\t1\t"Kit"' in ds
          and len(united) == 3)
    check("slice_hda_metadata", ok, defn.icon(),
          "TAB submenu, icon, every port label and %d/3 metre units, off "
          "the .hda" % len(united))

    # 10. D24's WARN-NEVER-BLOCK, on the five things an artist gets wrong.
    #     Every one of these was measured by hand while building C1; the
    #     compounding rule says a measurement made during a cycle becomes a
    #     standing check or is deliberately discarded, and a tool whose whole
    #     job is ingesting hand-modelled input cannot discard this one.
    flat = hou.Geometry()                     # a chunk with no volume at all
    poly = flat.createPolygon()
    for p in ((0, 0, 0), (3 * W, 0, 0), (3 * W, 3 * H, 0), (0, 3 * H, 0)):
        pt = flat.createPoint()
        pt.setPosition(p)
        poly.addVertex(pt)
    bad = []
    for tag, chunk_geo, guides in (
            ("unwired", None, None),
            ("empty", hou.Geometry(), None),
            ("flat", flat, None),
            ("guide_no_normal", chunk, [((2 * W, 0, 0), None, "")]),
            ("guide_flat_normal", chunk,
             [((2 * W, 0, 0), (0.0, 0.0, 1.0), "")])):
        n = (geo_node.createNode("pf_polychain_slice", "degen_" + tag)
             if chunk_geo is None
             else slice_node(geo_node, "degen_" + tag, chunk_geo,
                             guides=guides))
        g = n.geometry()
        if g is None or n.errors():
            bad.append("%s: %s" % (tag, "; ".join(n.errors())[:60] or "None"))
        elif not n.node("sl_kit").warnings() and \
                not g.intrinsicValue("primitivecount"):
            bad.append("%s: nothing built and nothing said" % tag)
    check("slice_degenerates_warn_never_block", not bad, "%d bad" % len(bad),
          "; ".join(bad)[:100] or "unwired, empty, flat, and two malformed "
          "guides - all warn, none error")

    # 11. THE FACADE - the nine cells doing the job they were sliced FOR.
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

    # 12. THE ARTIST'S OWN SURFACE, AREA IN VS AREA OUT.
    #     ⚠️ THE ORACLE ABOVE CANNOT REACH THIS AND NEITHER COULD ANY IMAGE.
    #     Its nine modules are CLOSED SOLIDS cut on planes that coincide with
    #     faces they already have, so it never runs `polyfill`'s open-boundary
    #     branch. A plain single-sided wall - the commonest facade chunk there
    #     is - came back at 108.000 m2 from 54.000 (every cell carrying a
    #     mirrored copy of itself), and a wall with a window came back with
    #     the WINDOW FILLED IN plus ten zero-area polygons. `validate()` was
    #     clean and `PC-C1_facade.png` looked right, because a wireframe
    #     cannot draw a filled hole. One number kills both.
    surf = []
    for tag, holes, want_area in (("plain", False, 54.0),
                                  ("window", True, 50.0)):
        n = slice_node(geo_node, "sheet_" + tag, sheet(holes), bay=3.0,
                       storey=2.0)
        got, degen = _kit_area(n.geometry())
        surf.append((tag, want_area, got, degen))
    worst = max(abs(a - g) for _t, a, g, _d in surf)
    degen = sum(d for _t, _a, _g, d in surf)
    check("slice_keeps_the_artists_surface",
          len(surf) == 2 and worst <= 1e-4 and degen == 0,
          "%.4f m2" % worst,
          "; ".join("%s %.3f -> %.3f m2, %d degenerate prim"
                    % (t, a, g, d) for t, a, g, d in surf))

    # 13. D24 REACHING THE ARTIST. Not one `pc_slice:` line did: a Python SOP
    #     inside an HDA cannot warn on the HDA and nothing propagates it, so
    #     the shipped node read CLEAN on an unwired input, a bay wider than
    #     the chunk and a malformed guide alike. The `Notes` parm is the
    #     surface, and this reads it off the SHIPPED node.
    unwired = geo_node.createNode("pf_polychain_slice", "notes_unwired")
    unwired.geometry()
    said, clean = unwired.evalParm("notes"), node.evalParm("notes")
    check("slice_notes_reach_the_artist",
          "nothing on input 1" in said and clean == "ok",
          "%d char" % len(said),
          "unwired says %r; a chunk it can slice says %r"
          % (said[:44], clean[:20]))

    # 14. THE CELL FRAME AGAINST THE GEOMETRY IN IT, ON BOTH CORNERS.
    #     `slice_kit` measured the LOW corner only and nothing clamps a fill
    #     band to the chunk, so a 0.4 m chunk asked for a 5 m bay emitted
    #     `pc_size = (5, 5, 0.1)` around 0.4 m of wall and validated clean.
    tiny = hou.Geometry()
    K.box_mesh(tiny, 0.0, 0.4, 0.0, 0.4, -0.05, 0.05, 1)
    short = slice_node(geo_node, "frame_short", tiny, bay=5.0, storey=5.0,
                       sides=0, capstop=0)
    flush = _frame_gap(out)
    bad = _frame_gap(short.geometry())
    check("slice_cell_frame_gap_m",
          flush[0] <= 1e-6 and abs(bad[0] - 4.6) <= 1e-4
          and "high" in short.evalParm("notes"),
          "%.3e m" % flush[0],
          "9 cells flush with their frames; the 0.4 m chunk given a 5 m bay "
          "is %.3f m short at its %s, and says so" % (bad[0], bad[1]))

    # 15. D272's CANONICAL Z, and the union that proves it matters. X and Y
    #     were normalised and Z was not, so a facade modelled IN PLACE on a
    #     building - the normal workflow - built a fence 49.90 m behind its
    #     own curve, silently.
    far = hou.Geometry()
    K.box_mesh(far, 120.0, 130.0, 8.0, 11.0, 49.9, 50.1, 1)
    fnode = slice_node(geo_node, "zfar", far)
    lo, hi = _kit_z(fnode.geometry())
    fbb = chain_node(geo_node, "chain_far", fnode.geometry(),
                     "far").geometry().boundingBox()
    check("slice_kit_z_is_canonical",
          abs(lo + hi) <= 1e-5 and abs(fbb.minvec()[2]) <= 0.11,
          "%.3e m" % (0.5 * (lo + hi)),
          "modules span z [%.3f %.3f]; the fence they build sits at z %.2f, "
          "not 49.90 m behind the curve" % (lo, hi, fbb.minvec()[2]))

    # 16. THE CUT FACES' UV. `dress_caps` was written for the miter cut and
    #     projects (local z, local y); on a Y cut plane `local y` is constant
    #     across the whole face, so HALF of every sliced module's cut faces
    #     shipped a zero-area UV island - on real, visible 0.6 m2 faces.
    span, ncap = _worst_cap_uv(fnode.geometry())
    check("slice_cap_uv_spans_two_axes", ncap >= 4 and span > 1e-6,
          "%.4f m" % span,
          "%d cut faces measured (0 would make this vacuous); the narrowest "
          "UV island is %.4f m across" % (ncap, span))

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
    if _SCRATCH:
        shutil.rmtree(_SCRATCH[0], ignore_errors=True)
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


def sheet(holes=False):
    """One single-sided wall, optionally with a 2 x 2 m window modelled as a
    hole. 9 x 6 m = 54 m2, or 50 m2 with the window. NOT a closed solid - and
    that is the whole point, because the 3 x 3 oracle fixture is."""
    geo = hou.Geometry()
    xs, ys = (0.0, 3.5, 5.5, 9.0), (0.0, 2.0, 4.0, 6.0)
    pts = {}
    for i, x in enumerate(xs):
        for j, y in enumerate(ys):
            p = geo.createPoint()
            p.setPosition((x, y, 0.0))
            pts[(i, j)] = p
    for i in range(3):
        for j in range(3):
            if holes and (i, j) == (1, 1):
                continue
            poly = geo.createPolygon()
            for k in ((i, j), (i + 1, j), (i + 1, j + 1), (i, j + 1)):
                poly.addVertex(pts[k])
    return geo


def _modules(kit_geo):
    for prim in kit_geo.prims():
        yield (prim.points()[0], prim.getEmbeddedGeometry())


def _kit_area(kit_geo):
    """(total surface area of every module, count of zero-area prims)."""
    total, degen = 0.0, 0
    for _pt, src in _modules(kit_geo):
        for prim in src.prims():
            a = prim.intrinsicValue("measuredarea")
            total += a
            degen += 1 if a < 1e-9 else 0
    return (total, degen)


def _frame_gap(kit_geo):
    """The worst of the four distances between a module's own frame
    (0 .. `pc_size`) and the geometry in it. (metres, "<name> <side>")."""
    worst = (0.0, "none")
    for pt, src in _modules(kit_geo):
        size, bb = pt.attribValue("pc_size"), src.boundingBox()
        lo, hi = bb.minvec(), bb.maxvec()
        for gap, side in ((lo[0], "low x"), (lo[1], "low y"),
                          (size[0] - hi[0], "high x"),
                          (size[1] - hi[1], "high y")):
            if gap > worst[0]:
                worst = (gap, "%s %s" % (pt.attribValue("pc_name"), side))
    return worst


def _kit_z(kit_geo):
    """(lowest, highest) module-local Z across the whole kit."""
    lo, hi = 1e30, -1e30
    for _pt, src in _modules(kit_geo):
        bb = src.boundingBox()
        lo, hi = min(lo, bb.minvec()[2]), max(hi, bb.maxvec()[2])
    return (lo, hi)


def _worst_cap_uv(kit_geo):
    """(narrowest UV span over every `pc_cap` face, number of faces seen)."""
    worst, seen = 1e30, 0
    for _pt, src in _modules(kit_geo):
        if src.findPrimAttrib("pc_cap") is None:
            continue
        for i, flag in enumerate(src.primIntAttribValues("pc_cap")):
            if not flag:
                continue
            uv = [vtx.attribValue("uv") for vtx in src.prim(i).vertices()]
            seen += 1
            worst = min(worst, min(max(v[k] for v in uv)
                                   - min(v[k] for v in uv) for k in (0, 1)))
    return (0.0 if not seen else worst, seen)


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
