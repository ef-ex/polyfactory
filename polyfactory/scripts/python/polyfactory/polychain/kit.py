"""polyChain 3.2 KIT FORMAT - build, read and validate a kit as geometry.

This is the ONLY module that knows what a kit looks like on a Houdini stream.
`place.py` asks it for a `Kit` (the hou-free contract from `__init__.py`) plus
the module geometry behind each name; nothing else reads kit attributes.

THE FORMAT (3.2, verbatim where the spec is explicit):

  * one PACKED PRIM per module, and the manifest rides on THAT prim's own
    point - a packed prim already is exactly one point plus one prim, so
    "packed prim per module + one point per module" is one object, not two
    that could drift out of step (decision D22).
  * per-module point attributes `pc_name`, `pc_role`, `pc_size`, `pc_pad`,
    `pc_deform`, `pc_zmode`, `pc_variant`, `pc_weight`.
  * a detail DICT `pc_kit` with `kitId`, `version`, `sources` and
    `human_scale_reference` - the last one mandatory (buildings 12.9).

DECISIONS TAKEN HERE:

  D20 MODULE LOCAL FRAME: +X runs ALONG the chain, +Y is up, +Z is across.
      The module's fit origin is its bounding box MINIMUM X and its fit length
      is `pc_size.x` (bbox X extent when the attribute is absent or zero), so
      geometry outside [minX, minX + pc_size.x] legitimately OVERHANGS and is
      carried along - RailClone's "fitted size is not the bounding box".
      3.2/4.4 say "Z" for the up axis because RailClone is a 3ds Max plugin
      and Max is Z-up; polyfactory is Houdini, so the spec's Z is Y here.
  D22 The manifest lives on the packed prim's point (above).
  D23 A KIT IS A BUILDER, NOT A SHIPPED BINARY. `starter_kit()` constructs the
      fence kit in code. A .bgeo in the repo is a second source of truth that
      silently ages past the format it encodes, and `polyfactory/library/` and
      `polyfactory/resources/` are both gitignored, so a shipped kit file
      could not be committed anyway. `write_kit_file()` exists for artists who
      want one on disk; nothing in the build reads it.
  D24 Validation NEVER raises and never rejects: `validate()` returns a list of
      human-readable warning strings, and `read()` fills every missing field
      with a documented default. Warn-never-block is a suite constraint, and a
      kit is exactly the artist-authored input it was written for.
"""

import hou

from . import (DEFORM_BEND, DEFORM_RIGID, DEFORM_SLICE, EPS, Kit, Module,
               Z_MODES, split_role)

# The manifest, in one list so the builder, the reader and the validator can
# never disagree about it: (attribute, default, kind).
MODULE_ATTRS = (
    ("pc_name", "", "string"),
    ("pc_role", "default", "string"),
    ("pc_size", (0.0, 0.0, 0.0), "vector3"),
    ("pc_pad", (0.0, 0.0), "vector2"),
    ("pc_deform", DEFORM_RIGID, "int"),
    ("pc_zmode", "adaptive", "string"),
    ("pc_variant", "", "string"),
    ("pc_weight", 1.0, "float"),
    # 4.5 / D55: -1 means "the style's `conform_tilt` decides", which is why
    # the default is not 0 - a kit that says nothing must not silently veto a
    # style that asks for camber.
    ("pc_tilt", -1, "int"),
)

KIT_DETAIL = "pc_kit"
KIT_FIELDS = ("kitId", "version", "sources", "human_scale_reference")

# D34: the one warning `read` must recognise rather than merely report. An
# UNCONNECTED kit input hands the SOP `None`, and warn-never-block means that
# builds a stand-in fence, not an AttributeError mid-cook.
UNREADABLE = "pc_kit: unreadable geometry"


# --- construction -----------------------------------------------------------

def box_mesh(geo, x0, x1, y0, y1, z0, z1, divx=1):
    """A CLOSED, point-shared box running along X, divided `divx` times.

    Hand-built rather than run through the Box SOP, and PART B corrected the
    reason - which matters, because the old one invites the opposite
    conclusion.

    ⚠️ THE OLD REASON IS STALE: "the Box SOP's division mode emits 24 two-point
    polygons alongside the faces (measured on 22.0.398), which is not a solid".
    Re-probed on 22.0.398 with `type = polymesh` and `divrate1 = 9`, the Box
    SOP emits **34 four-sided prims and 36 points, no degenerate primitive at
    all** - the same counts as `box_mesh(divx=8)` - and D33's centroid-dot-
    normal test scores 0 inward faces on both.  A reader checking that sentence
    finds it false and concludes the hand-build is obsolete.

    THE REAL REASON IS ORDER.  The two are not interchangeable geometry: the
    Box SOP lays its points out per FACE and this lays them out in 4-point
    RINGS along x, so the point set, the point order and the vertex order all
    differ.  Every module is packed and copied by `copytopoints`, so swapping
    the builder re-orders the points of every element the tool ships and moves
    `geometry_digest` on every case in the suite.  That is what makes 13.3.6's
    "four `box` SOPs + `pack`" the wrong native mechanism, and it is why D154
    is declined rather than merely unstarted - see `kit_starter_cooks_once`.

    D33 WINDING IS OUTWARD, AND IT IS ASSERTED AGAINST THE BOX SOP VERB. The
    first version of this wound every face the other way, which put 18 of the
    starter gate's 18 faces inside-out (measured: the box verb scores 0/6
    inward on a centroid-dot-normal test, this scored 6/6) - so every fence the
    tool built rendered interior-side-out and every normal-dependent op
    downstream (boolean, peak, displacement) ran on inverted geometry.
    `module_winding` in the scene checks is that measurement, kept.
    """
    divx = max(int(divx), 1)
    rings = []
    for i in range(divx + 1):
        x = x0 + (x1 - x0) * (float(i) / divx)
        ring = []
        for (y, z) in ((y0, z0), (y1, z0), (y1, z1), (y0, z1)):
            p = geo.createPoint()
            p.setPosition((x, y, z))
            ring.append(p)
        rings.append(ring)
    for i in range(divx):
        a, b = rings[i], rings[i + 1]
        for k in range(4):
            poly = geo.createPolygon()
            for p in (a[k], b[k], b[(k + 1) % 4], a[(k + 1) % 4]):
                poly.addVertex(p)
    cap = geo.createPolygon()
    for p in rings[0]:
        cap.addVertex(p)
    cap = geo.createPolygon()
    for p in reversed(rings[-1]):
        cap.addVertex(p)
    return geo


def _ensure(geo, cls, name, default):
    found = (geo.findGlobalAttrib(name) if cls == hou.attribType.Global
             else geo.findPointAttrib(name))
    if found is None:
        found = geo.addAttrib(cls, name, default)
    return found


def add_module(geo, name, source, size=None, pad=(0.0, 0.0),
               deform=DEFORM_RIGID, zmode="adaptive", roles="default",
               variant="", weight=1.0, tilt=-1, extend=-1, clip=-1):
    """Pack `source` into `geo` as one module and write its manifest point."""
    for attr, default, _kind in MODULE_ATTRS:
        _ensure(geo, hou.attribType.Point, attr, default)
    prim = geo.createPackedGeometry(source)
    pt = prim.points()[0]
    if size is None:
        sv = source.boundingBox().sizevec()
        size = (sv[0], sv[1], sv[2])
    pt.setAttribValue("pc_name", str(name))
    pt.setAttribValue("pc_role", roles if isinstance(roles, str)
                      else " ".join(roles))
    pt.setAttribValue("pc_size", tuple(float(v) for v in size))
    pt.setAttribValue("pc_pad", (float(pad[0]), float(pad[1])))
    pt.setAttribValue("pc_deform", int(deform))
    pt.setAttribValue("pc_zmode", zmode)
    pt.setAttribValue("pc_variant", str(variant))
    pt.setAttribValue("pc_weight", float(weight))
    pt.setAttribValue("pc_tilt", int(tilt))
    if int(extend) >= 0:            # 7.3.1, and only when it is authored: a
        _ensure(geo, hou.attribType.Point, "pc_extend", -1)   # phase-1 kit
        pt.setAttribValue("pc_extend", int(extend))           # gains nothing
    if int(clip) >= 0:              # 7.6 / D126, written the same way and for
        _ensure(geo, hou.attribType.Point, "pc_clip", -1)     # the same reason
        pt.setAttribValue("pc_clip", int(clip))
    return prim


def write_manifest(geo, kit_id, version=1, sources=(),
                   human_scale_reference=1.8):
    _ensure(geo, hou.attribType.Global, KIT_DETAIL, {})
    geo.setGlobalAttribValue(KIT_DETAIL, {
        "kitId": str(kit_id), "version": int(version),
        "sources": [str(s) for s in sources],
        "human_scale_reference": float(human_scale_reference)})


# --- attribute reads that cannot throw --------------------------------------

def _sattr(pt, name, default):
    try:
        v = pt.attribValue(name)
    except hou.OperationFailed:
        return default
    return v if isinstance(v, str) else default


def _iattr(pt, name, default):
    try:
        return int(pt.attribValue(name))
    except (hou.OperationFailed, TypeError, ValueError):
        return default


def _fattr(pt, name, default):
    try:
        return float(pt.attribValue(name))
    except (hou.OperationFailed, TypeError, ValueError):
        return default


def _vattr(pt, name, default):
    try:
        return tuple(float(x) for x in pt.attribValue(name))
    except (hou.OperationFailed, TypeError, ValueError):
        return default


# --- validation (D24: warnings, never exceptions) ---------------------------

def validate(geo):
    """[warning strings]. An empty list means the kit is well formed."""
    warns = []
    if geo is None:
        return ["%s (no kit connected)" % UNREADABLE]
    try:
        prims = [p for p in geo.prims()
                 if p.type() == hou.primType.PackedGeometry]
    except Exception as exc:                        # not geometry at all
        return ["%s (%s)" % (UNREADABLE, str(exc)[:120])]
    if not prims:
        warns.append("pc_kit: no packed prims - a kit is one packed prim per "
                     "module (3.2)")
    manifest = None
    if geo.findGlobalAttrib(KIT_DETAIL) is None:
        warns.append("pc_kit: detail dict %r missing" % KIT_DETAIL)
    else:
        try:
            manifest = dict(geo.attribValue(KIT_DETAIL))
        except Exception:
            warns.append("pc_kit: detail %r is not a dict" % KIT_DETAIL)
    if manifest is not None:
        for field in KIT_FIELDS:
            if field not in manifest:
                warns.append("pc_kit: mandatory field %r missing" % field)
        hsr = manifest.get("human_scale_reference")
        if hsr is not None:
            try:
                if float(hsr) <= 0.0:
                    warns.append("pc_kit: human_scale_reference must be > 0 m "
                                 "(got %r)" % (hsr,))
            except (TypeError, ValueError):
                warns.append("pc_kit: human_scale_reference is not a number "
                             "(%r)" % (hsr,))
    for attr, _default, _kind in MODULE_ATTRS:
        if geo.findPointAttrib(attr) is None:
            warns.append("pc_kit: module attribute %r missing on every module"
                         % attr)
    seen = {}
    for prim in prims:
        pt = prim.points()[0]
        name = _sattr(pt, "pc_name", "")
        if not name:
            warns.append("pc_kit: module at prim %d has no pc_name"
                         % prim.number())
            continue
        if name in seen:
            warns.append("pc_kit: duplicate module name %r (prims %d and %d)"
                         % (name, seen[name], prim.number()))
        seen[name] = prim.number()
        if _vattr(pt, "pc_size", (0.0, 0.0, 0.0))[0] <= EPS:
            warns.append("pc_kit: module %r has pc_size.x <= 0 - the fitted "
                         "length falls back to the packed bbox" % name)
        zmode = _sattr(pt, "pc_zmode", "adaptive")
        if zmode and zmode not in Z_MODES:
            warns.append("pc_kit: module %r has unknown pc_zmode %r (falls "
                         "back to 'adaptive')" % (name, zmode))
        deform = _iattr(pt, "pc_deform", DEFORM_RIGID)
        if deform not in (0, 1, 2):
            warns.append("pc_kit: module %r has pc_deform %r outside 0/1/2 "
                         "(clamped)" % (name, deform))
        if _fattr(pt, "pc_weight", 1.0) < 0.0:
            warns.append("pc_kit: module %r has a negative pc_weight "
                         "(clamped to 0)" % name)
    return warns


# --- reading ----------------------------------------------------------------

def read(geo):
    """(Kit, {module name: hou.Geometry}, [validation warnings]).

    Never raises. A kit that fails validation still yields a usable Kit -
    every missing field falls back to the documented default (D24).
    """
    warns = validate(geo)
    if warns and warns[0].startswith(UNREADABLE):    # D34 - never touch `geo`
        return (Kit(), {}, warns)                    # again after this
    manifest = {}
    if geo.findGlobalAttrib(KIT_DETAIL) is not None:
        try:
            manifest = dict(geo.attribValue(KIT_DETAIL))
        except Exception:
            manifest = {}
    modules, sources = [], {}
    for prim in geo.prims():
        if prim.type() != hou.primType.PackedGeometry:
            continue
        pt = prim.points()[0]
        name = _sattr(pt, "pc_name", "") or "module_%d" % prim.number()
        src = prim.getEmbeddedGeometry()
        size = _vattr(pt, "pc_size", (0.0, 0.0, 0.0))
        if size[0] <= EPS:                          # D20: bbox fallback
            sv = src.boundingBox().sizevec()
            size = (sv[0], sv[1], sv[2])
        deform = _iattr(pt, "pc_deform", DEFORM_RIGID)
        deform = 0 if deform < 0 else (2 if deform > 2 else deform)
        modules.append(Module(
            name, size, pad=_vattr(pt, "pc_pad", (0.0, 0.0)),
            deform=deform, zmode=_sattr(pt, "pc_zmode", "adaptive"),
            roles=_sattr(pt, "pc_role", "default"),
            variant=_sattr(pt, "pc_variant", ""),
            weight=max(_fattr(pt, "pc_weight", 1.0), 0.0),
            tilt=_iattr(pt, "pc_tilt", -1),
            # 7.3.1 - Extend To Side, read OPTIONALLY (it is not in
            # MODULE_ATTRS, so a phase-1 kit neither carries it nor warns
            # about not carrying it) and D6's three-state default: -1 is
            # "the generator decides".
            extend=_iattr(pt, "pc_extend", -1),
            # 7.6 / D126 - the cull policy, read the same optional way: a kit
            # that says nothing about clipping lets the array's parm decide.
            clip=_iattr(pt, "pc_clip", -1)))
        sources[name] = src
    kit = Kit(str(manifest.get("kitId", "")),
              int(manifest.get("version", 1) or 1), modules,
              float(manifest.get("human_scale_reference", 0.0) or 0.0),
              # D118 - the role closure is DATA on the kit payload, so the
              # kernel reads it like everything else and `facade.close_kit`
              # is the only thing that has to know how it was computed. {} on
              # every phase-1 kit.
              manifest.get("role_fallbacks") or {})
    return (kit, sources, warns)


def source_for(sources, module, nominal_y=1.0):
    """The geometry behind a module name, or 3.4's blank stand-in box."""
    src = sources.get(module.name)
    if src is not None:
        return src
    box = hou.Geometry()
    box_mesh(box, 0.0, max(module.length, EPS), 0.0,
             max(module.size[1] or nominal_y, EPS), -0.05, 0.05, 1)
    return box


# --- 7.7: slicing one chunk into a kit (`pf_polychain_slice`) ---------------
#
# The GEOMETRY half of the on-ramp; `slicer.py` is the decision half and owns
# every number that reaches here. It lives in this file because 13.6's Python
# list says "kit AUTHORING and validation" and a sliced kit is a kit - the
# format has one owner, and a second module writing `pc_role` and `pc_size`
# would be a second declaration of 3.2.

def _clip(chunk, cell, texel=1.0):
    """One cell cut out of the chunk, still IN THE CHUNK'S OWN SPACE.

    Four half-space clips of the same `clip` verb 4.3 already uses (D131), so
    the tool reaches no verb the kernel does not already reach. Returns None
    when the cell is empty - a plane grid over a chunk with a courtyard in it
    legitimately has empty cells, and that is a warning, not a failure (D24).
    """
    # ⚠️ IMPORTED HERE, NOT AT MODULE SCOPE: `place` imports `kit`, so a
    # module-level import would be a cycle. This is the only call either way.
    from . import place as _place
    geo = hou.Geometry()
    geo.merge(chunk)
    for org, nrm, sign in (((cell.x0, 0.0, 0.0), (1.0, 0.0, 0.0), +1),
                           ((cell.x1, 0.0, 0.0), (1.0, 0.0, 0.0), -1),
                           ((0.0, cell.y0, 0.0), (0.0, 1.0, 0.0), +1),
                           ((0.0, cell.y1, 0.0), (0.0, 1.0, 0.0), -1)):
        geo = _place.clip_plane(geo, org, nrm, sign, cell.name, texel)
        if not geo.intrinsicValue("primitivecount"):
            return None
    return geo


def _deform_for(role, mode):
    """`pc_deform` per D268's cap/fill split, matching the starter kit: a
    cap or corner piece holds its shape at a joint (rigid, and so stays
    instanced), the fill panel follows the run (bendable)."""
    if mode != "auto":
        return {"rigid": DEFORM_RIGID, "bend": DEFORM_BEND,
                "slice": DEFORM_SLICE}.get(mode, DEFORM_RIGID)
    return (DEFORM_RIGID if split_role(role)[0] in ("start", "end", "corner")
            else DEFORM_BEND)


def slice_cells(chunk, cells, texel=1.0):
    """([(Cell, geometry in the chunk's space)], [warnings]).

    The one place the clipping happens; both HDA stages read this list, so
    the preview an artist judges and the kit they ship cannot disagree.
    """
    out, warns = [], []
    for cell in cells:
        geo = _clip(chunk, cell, texel)
        if geo is None:
            warns.append("pc_slice: cell %r is empty - the chunk has no "
                         "geometry in x [%.4f %.4f] y [%.4f %.4f]"
                         % (cell.name, cell.x0, cell.x1, cell.y0, cell.y1))
            continue
        out.append((cell, geo))
    if not out:
        warns.append("pc_slice: nothing was sliced - check that the chunk "
                     "runs along +X with +Y up (D20)")
    return (out, warns)


def slice_preview(pairs):
    """The cells where they were cut, one `pc_cell` per prim - the display
    that answers "where did the cuts land" before anything is packed."""
    geo = hou.Geometry()
    geo.addAttrib(hou.attribType.Prim, "pc_cell", "")
    for cell, piece in pairs:
        n0 = geo.intrinsicValue("primitivecount")
        geo.merge(piece)
        col = list(geo.primStringAttribValues("pc_cell"))
        col[n0:] = [cell.name] * (len(col) - n0)
        geo.setPrimStringAttribValues("pc_cell", col)
    return geo


def slice_kit(pairs, kit_id="sliced_kit", version=1,
              human_scale_reference=1.8, deform="auto", zmode="adaptive",
              geo=None):
    """`slicer.plan`'s cells + their geometry -> a 3.2 kit. (geo, warnings).

    D270: each cell is translated by its OWN low corner, not by its
    geometry's, so the module's fit origin is the cell. When the geometry
    does not reach that corner the module is still built - `place._Proto`
    will take its fit origin from the bbox and place it shifted, so the gap
    is reported here, where the artist can still move a guide.

    D286: Z IS CANONICALISED, ONCE, FOR THE WHOLE KIT. X and Y were
    normalised and Z was "left exactly as authored", which meant a facade
    modelled in place on a building - the normal workflow - produced a kit
    every piece of which sat at its authored depth: measured, a chunk at
    z = 49.9 .. 50.1 built a fence 49.90 m off its own curve, silently.
    `houdini-tool-design` 3 asks for a canonical space; one offset for the
    whole kit gives it without touching the relative depth of one module
    against another, which is the thing the artist actually authored.
    """
    geo = geo if geo is not None else hou.Geometry()
    warns = []
    zc = _kit_z_centre(pairs)
    for cell, piece in pairs:
        src = hou.Geometry()
        src.merge(piece)
        src.transform(hou.hmath.buildTranslate(-cell.x0, -cell.y0, -zc))
        bb = src.boundingBox()
        gap, side = _cell_gap(bb, cell.x1 - cell.x0, cell.y1 - cell.y0)
        if gap > 1e-6:
            warns.append("pc_slice: cell %r does not reach its own %s edge "
                         "(%.4f m of void) - the piece will not fill its bay"
                         % (cell.name, side, gap))
        add_module(geo, cell.name, src,
                   size=(cell.x1 - cell.x0, cell.y1 - cell.y0,
                         bb.sizevec()[2]),
                   deform=_deform_for(cell.role, deform), zmode=zmode,
                   roles=cell.role, variant=cell.variant)
    write_manifest(geo, kit_id, version,
                   sources=("pf_polychain_slice",),
                   human_scale_reference=human_scale_reference)
    return (geo, warns)


def _kit_z_centre(pairs):
    """D286's single offset: the middle of the Z the kit actually occupies.

    WHAT THIS CANNOT SEE: Z in the chunk that no cell kept. Nothing clips Z,
    so the two differ only when a whole cell was dropped as empty.
    """
    lo = hi = None
    for _cell, piece in pairs:
        bb = piece.boundingBox()
        z0, z1 = bb.minvec()[2], bb.maxvec()[2]
        lo = z0 if lo is None else min(lo, z0)
        hi = z1 if hi is None else max(hi, z1)
    return 0.0 if lo is None else 0.5 * (lo + hi)


def _cell_gap(bb, sx, sy):
    """The worst of the FOUR distances between a cell's frame and the
    geometry in it, and which side it is on. (metres, side name).

    ⚠️ THIS USED TO READ `max(bb.minvec()[0], bb.minvec()[1])` - the low
    corner only. Nothing measured the high corner, and `axis_bands` anchors a
    fill cell at its own low edge with no clamp to the chunk, so a 0.4 m chunk
    asked for a 5 m bay emitted `pc_size = (5, 5, 0.1)` around 0.4 m of
    geometry, validated clean, and would have laid out 5 m bays holding
    0.4 m of wall.
    """
    lo, hi = bb.minvec(), bb.maxvec()
    return max(((lo[0], "low x"), (lo[1], "low y"),
                (sx - hi[0], "high x"), (sy - hi[1], "high y")),
               key=lambda g: g[0])


def _guides(geo):
    """Input 2, read as 7.7 guide planes. ([(axis, coord, class)], warnings).

    A guide is a POINT WITH A NORMAL and, optionally, `pc_slot` naming the
    class of the band that starts at it - the same `pc_slot` vocabulary 3.3
    already uses for rules, so the artist learns one word list, not two.
    """
    from . import slicer as _slicer
    if geo is None or not geo.intrinsicValue("pointcount"):
        return ([], [])
    n = geo.intrinsicValue("pointcount")
    flat = list(geo.pointFloatAttribValues("P"))
    pos = [flat[3 * i:3 * i + 3] for i in range(n)]
    if geo.findPointAttrib("N") is None:
        return ([], ["pc_slice: the guides carry no N - a guide is a point "
                     "plus the direction it cuts, so nothing was used"])
    fn = list(geo.pointFloatAttribValues("N"))
    nrm = [fn[3 * i:3 * i + 3] for i in range(n)]
    cls = (list(geo.pointStringAttribValues("pc_slot"))
           if geo.findPointAttrib("pc_slot") is not None else [])
    return _slicer.guides_from_points(pos, nrm, cls)


def sop_slice(node, mode="kit"):
    """`pf_polychain_slice`'s whole cook: parms in, a 3.2 kit out.

    13.6's sanctioned Python - parameter marshalling plus one call. Every
    number comes from `slicer.plan` and every polygon from the `clip` verb.
    """
    from . import slicer as _slicer
    # ⚠️ THE PARMS ARE ONE LEVEL UP. `hou.pwd()` inside the HDA is the Python
    # SOP, which has two parms of its own, so every read here returned None
    # and the page silently read as empty - the same trap `hda._parm_owner`
    # carries, hit again on the first cook of the new asset.
    parms = node if node.parm("bay") is not None else node.parent()
    geo = node.geometry()
    # ⚠️ A PYTHON SOP'S GEOMETRY ARRIVES AS A COPY OF INPUT 0. Without this
    # the kit shipped as nine packed prims MERGED INTO THE CHUNK, and every
    # kit-level check still passed because it reads modules by `pc_name` and
    # the chunk's prims all answer "" - one extra row, nine right answers.
    geo.clear()
    warns = []
    ins = node.inputs()
    chunk = node.inputGeometry(0) if ins and ins[0] is not None else None
    if chunk is None or not chunk.intrinsicValue("primitivecount"):
        warns.append("pc_slice: nothing on input 1 - wire the chunk to "
                     "slice. It should run along +X with +Y up (D20).")
    else:
        guides, w = _guides(node.inputGeometry(1)
                            if len(ins) > 1 and ins[1] is not None else None)
        warns += w
        bb = chunk.boundingBox()
        cells, w = _slicer.plan(
            (bb.minvec()[0], bb.maxvec()[0], bb.minvec()[1], bb.maxvec()[1]),
            parms.evalParm("bay"), parms.evalParm("storey"), guides,
            bool(parms.evalParm("sides")), bool(parms.evalParm("capstop")),
            bool(parms.evalParm("jigsaw")))
        warns += w
        pairs, w = slice_cells(chunk, cells)
        warns += w
        if mode == "cells":
            geo.merge(slice_preview(pairs))
        else:
            out, w = slice_kit(pairs, parms.evalParm("kitid"), 1,
                               parms.evalParm("humanscale"),
                               parms.parm("deform").evalAsString(),
                               parms.parm("zmode").evalAsString())
            warns += w
            geo.merge(out)
    for line in warns:
        node.addWarning(line)
    write_notes(geo, warns)


NOTES_ATTR = "pc_slice_notes"
NOTES_OK = "ok"


def write_notes(geo, warns):
    """D24's warnings, on the geometry, so the HDA's `Notes` parm can read
    them back with `details()`.

    ⚠️ A CHILD CANNOT WARN ON ITS HDA, AND NOTHING PROPAGATES IT EITHER.
    Probed on 22.0.398, every door: `parent().addWarning(...)` from inside a
    cook silently decorates the COOKING node instead of the one it was called
    on; a subnet aggregates a child's ERRORS ("Invalid source ... (Error: ...)")
    and never its warnings; `warnings()`, `errors()` and `messages()` on the
    parent are all empty, and there is no aggregating API. So every `pc_slice:`
    line the tool has ever raised was written on a Python SOP inside the asset,
    where an artist who has not dived in cannot see it - which made the whole
    warn-never-block contract decorative on the shipped node. This is the
    surface that is actually in front of them: the parameter page.

    WHAT THIS CANNOT SEE: whether the artist reads it. It is text on the page,
    not a badge - the badge stays on the inner stage, which is the most
    Houdini offers.
    """
    _ensure(geo, hou.attribType.Global, NOTES_ATTR, "")
    text = NOTES_OK if not warns else "%d note(s):  %s" % (
        len(warns), "   |   ".join(warns))
    geo.setGlobalAttribValue(NOTES_ATTR, text[:900])


# --- the starter kit (6, "one fence/railing kit ... shipped with the HDA") ---

def starter_kit():
    """post / panel / picket_panel / corner_post / gate - 6's starter kit.

    The PC-G1 and PC-G2 fence, and the thing that makes the HDA usable with
    nothing wired but a curve. Metric metres, and every module obeys D20:
    base at y = 0, running from x = 0 to x = pc_size.x, centred across Z.
    """
    geo = hou.Geometry()

    post = hou.Geometry()
    box_mesh(post, 0.0, 0.12, 0.0, 1.20, -0.06, 0.06, 1)
    add_module(geo, "post", post, size=(0.12, 1.20, 0.12),
               deform=0, zmode="stepped", roles="default start end post")

    # ⚠️ THE DEFAULT PANEL IS SOLID, AND THAT IS A REQUIREMENT (D86).
    # A picket panel was built, rendered and REVERTED here: it looks better -
    # judged on the image, the slab reads as a grey wall with an occasional
    # post in it - but a module with VOIDS along its span cannot mate at a
    # mitered corner, and PC-G1's corner gate is measured on this module.
    # Measured on the picket version: `corner_face_mate_m` went 0.0424 ->
    # 0.1849 m on V_rect_miter, because the bisector plane cut through a gap
    # between two pickets and there was no face there to mate with. The
    # picket panel ships as `picket_panel` below instead, one menu pick away,
    # so the kit is a fence AND a railing kit without the default losing its
    # corners.
    panel = hou.Geometry()
    box_mesh(panel, 0.0, 2.00, 0.10, 1.00, -0.03, 0.03, 8)
    add_module(geo, "panel", panel, size=(2.00, 0.90, 0.06),
               deform=1, zmode="vertical", roles="default panel")

    # The railing half of "one fence/railing kit" (6). Two rails and four
    # pickets on the SAME 0.25 m station ladder as the solid panel, so it
    # bends, conforms and instances identically; only the look differs. It is
    # NOT tagged `default`, so nothing picks it up unless an artist asks.
    picket = hou.Geometry()
    for y0, y1 in ((0.25, 0.35), (0.72, 0.82)):
        rail = hou.Geometry()
        box_mesh(rail, 0.0, 2.00, y0, y1, -0.02, 0.02, 8)
        picket.merge(rail)
    for i in range(4):
        slat = hou.Geometry()
        box_mesh(slat, i * 0.5, i * 0.5 + 0.25, 0.10, 1.00, -0.03, 0.03, 1)
        picket.merge(slat)
    add_module(geo, "picket_panel", picket, size=(2.00, 0.90, 0.06),
               deform=1, zmode="vertical", roles="picket railing")

    corner = hou.Geometry()
    box_mesh(corner, 0.0, 0.16, 0.0, 1.30, -0.08, 0.08, 1)
    add_module(geo, "corner_post", corner, size=(0.16, 1.30, 0.16),
               deform=0, zmode="stepped", roles="corner")

    gate = hou.Geometry()
    box_mesh(gate, 0.0, 1.60, 0.05, 1.10, -0.04, 0.04, 4)
    add_module(geo, "gate", gate, size=(1.60, 1.05, 0.08),
               deform=2, zmode="vertical", roles="gate")

    write_manifest(geo, "pf_fence_starter", 1,
                   sources=("polyfactory/polychain/kit.py:starter_kit",),
                   human_scale_reference=1.8)
    return geo


def write_kit_file(path, geo=None):
    """Artist convenience only - nothing in the build reads a kit file (D23)."""
    (geo or starter_kit()).saveToFile(path)
    return path
