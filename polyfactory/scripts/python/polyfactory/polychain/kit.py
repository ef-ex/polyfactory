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

from . import DEFORM_RIGID, EPS, Kit, Module, Z_MODES

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

    Hand-built rather than run through the Box SOP because the Box SOP's
    division mode emits 24 two-point polygons alongside the faces (measured on
    22.0.398), which is not a solid and so can be neither sliced nor capped.

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
               variant="", weight=1.0):
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
            weight=max(_fattr(pt, "pc_weight", 1.0), 0.0)))
        sources[name] = src
    kit = Kit(str(manifest.get("kitId", "")),
              int(manifest.get("version", 1) or 1), modules,
              float(manifest.get("human_scale_reference", 0.0) or 0.0))
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


# --- the starter kit (6, "one fence/railing kit ... shipped with the HDA") ---

def starter_kit():
    """post / panel / corner_post / gate - the PC-G1 and PC-G2 fence kit.

    Metric metres, and every module obeys D20: base at y = 0, running from
    x = 0 to x = pc_size.x, centred across Z.
    """
    geo = hou.Geometry()

    post = hou.Geometry()
    box_mesh(post, 0.0, 0.12, 0.0, 1.20, -0.06, 0.06, 1)
    add_module(geo, "post", post, size=(0.12, 1.20, 0.12),
               deform=0, zmode="stepped", roles="default start end post")

    panel = hou.Geometry()
    box_mesh(panel, 0.0, 2.00, 0.10, 1.00, -0.03, 0.03, 8)
    add_module(geo, "panel", panel, size=(2.00, 0.90, 0.06),
               deform=1, zmode="vertical", roles="default panel")

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
