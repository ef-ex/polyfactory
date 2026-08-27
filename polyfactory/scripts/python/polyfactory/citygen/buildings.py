"""CityGen B1/B2 skeleton - the generator that does not know which style it is
making.  Owning spec: `ideas/citygen_buildings.md` §12; gate: §12.10 G1.

WHAT IS AND IS NOT PYTHON HERE, because the project's language hierarchy is
law (CLAUDE.md rule 2: native nodes -> VEX -> OpenCL; Python only for UI and
parameter marshalling).  Every point, polygon and metre in B1/B2 is made by
`polyfactory/vex/citygen/*.vfl`, each one execution over the WHOLE stream, so
ten buildings cost the same number of wrangle runs as one.  This module does
three things and none of them touches geometry:

  1. reads a style template - a Houdini geometry file carrying one detail
     DICTIONARY attribute, per §12.5 and the attributes-not-JSON decision;
  2. resolves it through the override cascade (`citygen.md` §2.1) against the
     defaults in this file, which are cascade level 1;
  3. flattens the resolved nested dict onto per-prim array attributes, which
     is the form VEX can read.  VEX's dict support cannot walk a nested
     template cleanly, and this runs once per BUILDING, not per element.

That third job is the whole of `stamp()` and it is the named, justified Python
case §12 asks for.  It is not a cook-path loop over geometry.

§12.12 asked "style template storage format detail: first template authored
decides".  It is decided here: a `.geo` carrying `pf_style_template` as a
detail dict.  Reasons - it needs no parser at cook time, it is a few KB of
diffable ASCII, and unlike a JSON file it can carry §12.9's packed module
prims in the same file when kits arrive.

⚠️ **It does NOT round-trip losslessly**, and an earlier version of this
docstring claimed it did.  Measured on 22.0.398: a numeric list of length 2,
3 or 4 returns as a `hou.Vector2/3/4` and every other length returns as a
tuple.  `_plain()` restores the SHAPE, so nothing may read the raw attribute
and `load()` is the only door - but it does not restore element STORAGE, and
a nested list never survives authoring at all.
⚠️ **Neither loss is detectable at LOAD time** - a dropped key is simply
absent and `resolve()` substitutes the DEFAULTS value - so the repair is a
guard at the only place the loss is still visible: `assert_storable()`, which
the authoring script calls before it writes.  Neither shape occurs in the four
shipped templates; §12.12's per-storey height tables are the shape that will.
"""

import io
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.normpath(os.path.join(HERE, "..", "..", "..", ".."))
VEX_DIR = os.path.join(_ROOT, "vex", "citygen").replace("\\", "/")
STYLE_DIR = os.path.join(_ROOT, "library", "citygen",
                         "styles").replace("\\", "/")

# Cascade level 1: system defaults.  "No constants" (citygen.md §2.1) means
# every one of these is a default a template or an override may replace, and a
# template may therefore be sparse (§12.5).
DEFAULTS = {
    "styleId": "",
    "version": 0,
    "sources": [],
    "storeyHeightM": 3.0,
    # §12.6 B1 / §7: lot -> footprint is ONE pluggable stage and `identity` is
    # a legal choice, not a separate architecture.  `offsetM` is the uniform
    # inset `offset` applies to every edge regardless of role; `shape` is the
    # notch `shapeL`/`shapeU` cut out of the plan bounds (`pf_shape.vfl`).
    "lotToFootprint": {"op": "setback", "setbackM": {},
                       "defaultSetbackM": 0.0, "offsetM": 0.0,
                       "shape": {"widthM": 0.0, "depthM": 0.0, "at": 0}},
    "volumeTopology": {
        "rails": "bar",
        "cutsAt": [],
        "courtyardDepthM": 0.0,
        "volumes": [{"role": "volume", "storeys": 1, "capGroup": 0}],
        "plinth": {"mode": "none", "minM": 0.0},
    },
    "capFamily": {"family": "flat", "pitchDeg": 0.0, "eaveDepthM": 0.0},
    # §12.6 B6: the seam strategy is "selectable through the cascade", so it is
    # a template field like any other.  `bend` is the default because it is
    # also polyChain's, and because `miter` costs 2.7x (see §12.10b).
    "junctions": {"cornerMode": "bend"},
}

# The rule vocabulary.  Adding a style must never add a member here; that is
# what gate G1 is testing.
RAILS = {"bar": 0, "ring": 1, "solid": 2}
PLINTH = {"none": 0, "levelToHighest": 1}
# B5's cap strategies.  `flat` is "no cap built", which is what B2 already
# leaves behind; `skeletonRoof` is `pf_cap.vfl`.  §12.5's other four families
# (`parapet`, `platform`, `spire`, `continueUp`) are named there and not built,
# so a template asking for one raises `pf_warn_unknown_rule` and gets `flat` -
# §2.2, advisory and never a refusal.
CAPS = {"flat": 0, "skeletonRoof": 1}
CORNERS = ("bend", "miter")
# §12.6 B1's lot -> footprint vocabulary, complete.  Three of the six are the
# same per-edge inset with different numbers and are `pf_inset.vfl`'s
# (`setback` per role, `offset` uniform, `identity` = `setback(0)`); two change
# the footprint's TOPOLOGY and are `pf_shape.vfl`'s; and `shapeO` is a ring,
# which `pf_mass.vfl` already builds - §12.6 B1 says so in as many words, so
# `shapeO` routes to the `ring` rails rather than cutting a second courtyard
# by a second mechanism.  A name that is not here raises `pf_warn_unknown_rule`
# (§12.8) and gets `setback`; before this table an unknown op fell silently
# through to the setback table with no warning at all.
FOOTPRINT = ("setback", "identity", "offset", "shapeL", "shapeU", "shapeO")
SHAPES = {"shapeL": 1, "shapeU": 2}

# conventions.md §2/§5: `_*` leaves on no class, and neither does the VERTEX
# `pf_face_role` the lot arrived with - B2 re-emits it per PRIM on the walls
# that inherit it, and two classes of one contract name in one stream is
# exactly the confusion §1 exists to prevent.  Named, because the check that
# enforces the law is only worth having if its mutation can remove a sweep.
#
# `pf_style_template` and `pf_setback` go the same way, for the same reason
# and one more: they are B0's REQUEST - `pf_style_id` is the template that
# answered it, and the built wall is the setback that answered it - and after
# the mass wrangle removes the footprint prims the request survives as an
# attribute definition with an empty value on every face, a name in the
# published-names baseline carrying nothing. B6's per-building DNA point is
# where the template id belongs (§12.6), not on every wall.
#
# ⚠️ `pf_setback` IS SWEPT ON BOTH CLASSES, and the prim one is `R4-3`'s leak
# half: a lot authoring a PRIM `pf_setback` - a class §12.4 declares legal -
# shipped it on every face of the building as a dead value, because the sweep
# named the vertex class only.  Its other half (the value being ignored) is
# closed in `stamp()`, which now reads both classes.
CLEAN = (("doptdel", "ptdel", "_*"),
         ("dovtxdel", "vtxdel", "_* pf_face_role pf_setback"),
         ("doprimdel", "primdel", "_* pf_style_template pf_setback"),
         ("dodtldel", "dtldel", "_*"))


def vex(name):
    """The text of one .vfl, inlined into a snippet parm at build time.

    Same reasoning as polyChain's `vexsrc`: hython does not set
    HOUDINI_VEX_PATH, so a cook-time `#include` cannot resolve (dev-loop trap
    list).  These files have no includes, so this stays four lines."""
    path = os.path.join(VEX_DIR, name if name.endswith(".vfl")
                        else name + ".vfl").replace("\\", "/")
    with io.open(path, "r", encoding="utf-8") as handle:
        return handle.read()


def style_path(style_id):
    return os.path.join(STYLE_DIR, style_id + ".geo").replace("\\", "/")


def _plain(value):
    """Normalise what a Houdini dict attribute hands back into plain Python.

    ⚠️ NOT just tuples-for-lists, and the difference is a trap an audit found:
    a numeric list of length 2, 3 or 4 comes back as a `hou.Vector2/3/4`,
    while length 1 or 5 comes back as a tuple.  So `cutsAt: [0.444, 0.722]`
    round-trips as a Vector2 and `[0.4]` does not, and code that happens to
    iterate the value works while code that compares it does not.  Anything
    iterable that is not a string or a dict is flattened here.

    ⚠️ AND IT RESTORES SHAPE, NOT STORAGE - two measured losses, neither of
    them repairable here, both named because D223 says an element's storage
    is part of the contract:
      * a MIXED numeric list `[1, 2.5, 3]` comes back all-float, so the ints
        in it are gone by the time this function sees the value;
      * a NESTED list never arrives at all.  It dies in the authoring script
        at `setGlobalAttribValue`, before the `.geo` is written, silently -
        so `load()` reads a template with the field simply absent and nothing
        raises anywhere.
    Neither shape occurs in the four shipped templates.  A template field that
    needs either one needs a different storage decision, not a fix here."""
    if isinstance(value, dict):
        return dict((k, _plain(v)) for k, v in value.items())
    if isinstance(value, (str, bytes)):
        return value
    try:
        return [_plain(v) for v in value]
    except TypeError:
        return value


def assert_storable(value, path="pf_style_template"):
    """RAISE on a template shape this .geo format cannot carry.

    ⚠️ A GUARD, NOT A CHECK, BECAUSE THE LOSS IS SILENT AT BOTH ENDS.
    Measured on 22.0.398 through the shipped authoring path
    (`addAttrib(Global, {})` -> `setGlobalAttribValue` -> `saveToFile` ->
    `loadFromFile` -> `_plain`), three list shapes misbehave and not one of
    them raises anywhere:
      * a list containing a LIST - the whole key is ABSENT from the loaded
        template, so `resolve()` quietly substitutes the DEFAULTS value;
      * a list mixing STRINGS with numbers - same, key absent;
      * a list mixing INT with FLOAT - it survives, every element float, so
        the int storage is gone before `_plain()` ever sees the value (D223:
        an element's storage is part of the contract).
    Dicts nest freely and a list of DICTS is fine - `volumes[]` is one, and
    `{"v": [{"h": [1.0, 2.0]}]}` round-trips intact.  So this raises at
    AUTHORING, the only moment the loss is still visible.  §12.12 carries
    per-storey height TABLES into B3; that is the shape that will hit it."""
    if isinstance(value, dict):
        for key, sub in value.items():
            assert_storable(sub, "%s.%s" % (path, key))
    elif isinstance(value, (list, tuple)):
        kinds = set()
        for i, sub in enumerate(value):
            assert_storable(sub, "%s[%d]" % (path, i))
            kinds.add("list" if isinstance(sub, (list, tuple)) else
                      "str" if isinstance(sub, (str, bytes)) else
                      "dict" if isinstance(sub, dict) else
                      "float" if isinstance(sub, float) else "int")
        bad = ("a nested list" if "list" in kinds else
               "+".join(sorted(kinds)) + " in one list" if len(kinds) > 1
               else "")
        if bad:
            raise ValueError("%s: %s - the .geo detail-dict format cannot "
                             "carry it and loses it SILENTLY (measured on "
                             "22.0.398)" % (path, bad))


def load(style_id_or_path):
    """One style template -> a plain dict."""
    import hou
    path = (style_id_or_path if style_id_or_path.endswith(".geo")
            else style_path(style_id_or_path))
    geo = hou.Geometry()
    geo.loadFromFile(path)
    return _plain(geo.attribValue("pf_style_template"))


def _merge(base, over):
    """Deep merge, so a dict-valued field is a NAMESPACE and not a value.

    Decided rather than stumbled into: an override that raises the front
    setback must not silently drop the other three roles from `setbackM`, so
    §2.1's "last wins" applies per LEAF. The cost is that a table can only be
    added to, never wholesale replaced - to empty one, set its keys."""
    out = dict(base)
    for key, value in over.items():
        if isinstance(value, dict) and isinstance(out.get(key), dict):
            out[key] = _merge(out[key], value)
        else:
            out[key] = value
    return out


def resolve(template, overrides=None):
    """Cascade level 1 (DEFAULTS) -> 3 (the template) -> 6 (overrides), last
    wins.  Levels 2/4/5 are parameters, region and per-element attributes and
    enter through the caller, not through this function."""
    out = _merge(DEFAULTS, template or {})
    return _merge(out, overrides or {}) if overrides else out


def stamp(geo, overrides=None, cache=None):
    """Flatten each lot prim's resolved template onto attributes VEX reads.

    Reads   prim `pf_style_template` (string), prim `pf_site_id` (int),
            vertex `pf_face_role` (string), optional `pf_setback` on the
            VERTEX or the PRIM class - §12.4 declares both legal (`R4-3`).
    Writes  the `_*` marshalling attributes, `pf_style_id`, `pf_seed`.

    The optional authored `pf_setback` is cascade level 5 and it WINS over the
    template's per-role number - "use the authored value if present, otherwise
    compute one", never compute alone (citygen.md §2.1).

    ⚠️ NEGATIVE MEANS ABSENT, AND THAT IS A SCHEMA DECISION, NOT A BRANCH.
    A Houdini float attribute has no "absent" value: every vertex carries one
    the moment the attribute exists.  The first build gated on `> 0.0`, so
    **`setback(0)` - the one value §12.6 B1 names as the identity op, and what
    the Viennese block's street edges ARE - could not be authored at all.**
    Measured on a 10 x 90 einhof lot: no attribute -> [2.5, 2.0, 7.5, 47.0];
    authored 0.0 -> IDENTICAL; authored 1.0 -> [1.0, 1.0, 9.0, 89.0].
    The gate is now `>= 0.0`, so a setback is authored when it is a distance
    and absent when it is not one.  ⚠️ The alternative - attribute presence
    alone, "the attribute exists so every vertex is authored" - was measured
    too and REJECTED: it collapses a per-element override into a per-STREAM
    one.  On this fixture, where only site 6 authors anything, it dragged
    sites 1 and 3 onto their lot lines (10 x 90 and 110..172 x 0..38) because
    their vertices carry the attribute's 0.0 default.  §12.4 is amended to say
    so and Hannes ratifies it (§0.0g).
    """
    import hou
    cache = {} if cache is None else cache
    # §12.4: the seed belongs to the SITE, so a lot that arrives carrying one
    # keeps it. This is read BEFORE the attribute is created below, because
    # after that the two cases are indistinguishable. An audit measured the
    # old line - `int(tpl.get("seed", 0))`, a key NO template defines -
    # overwriting a lot's own `pf_seed` of 4242 with 0 on every prim, which
    # left §12.4's per-site determinism row unimplemented rather than untested.
    seeded = geo.findPrimAttrib("pf_seed") is not None
    # `R4-6`: the un-seeded branch below used to fall back to a template key no
    # template defines, so every site in a stream that arrived without a seed
    # got the SAME seed, 0, and §12.4's per-site determinism row was silently
    # unimplemented rather than loudly missing.  The site id is deterministic,
    # distinct per site and structural (§12.7 - never generation order), which
    # is exactly what a seed has to be; B0 writes the same fallback, so the two
    # agree whether or not B0 ran.
    sited = geo.findPrimAttrib("pf_site_id") is not None

    for name, kind in (("_roles", hou.attribData.String),
                       ("_storeys", hou.attribData.Int),
                       ("_capgroups", hou.attribData.Int),
                       ("_storeyh", hou.attribData.Float),
                       ("_cuts", hou.attribData.Float)):
        if geo.findPrimAttrib(name) is None:
            geo.addArrayAttrib(hou.attribType.Prim, name, kind)
    for name, default in (("_rails", 0), ("_plinth", 0), ("pf_seed", 0),
                          ("pf_warn_unknown_rule", 0), ("_shape", 0),
                          ("_shape_at", 0)):
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, default)
    for name, default in (("_courtyard", 0.0), ("_plinthmin", 0.0),
                          ("_shape_w", 0.0), ("_shape_d", 0.0)):
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, default)
    if geo.findPrimAttrib("pf_style_id") is None:
        geo.addAttrib(hou.attribType.Prim, "pf_style_id", "")
    if geo.findVertexAttrib("_inset") is None:
        geo.addAttrib(hou.attribType.Vertex, "_inset", 0.0)
    authored = geo.findVertexAttrib("pf_setback") is not None
    authored_prim = geo.findPrimAttrib("pf_setback") is not None

    for prim in geo.prims():
        style_id = prim.attribValue("pf_style_template")
        if style_id not in cache:
            cache[style_id] = resolve(load(style_id), overrides)
        tpl = cache[style_id]
        topo = tpl["volumeTopology"]
        volumes = topo["volumes"] or DEFAULTS["volumeTopology"]["volumes"]
        fp = tpl["lotToFootprint"]
        op = (fp["op"] if fp["op"] in FOOTPRINT
              else DEFAULTS["lotToFootprint"]["op"])
        unknown = int(topo["rails"] not in RAILS
                      or topo["plinth"]["mode"] not in PLINTH
                      or fp["op"] not in FOOTPRINT)

        prim.setAttribValue("pf_style_id", tpl["styleId"] or style_id)
        if not seeded:
            prim.setAttribValue("pf_seed", int(tpl.get(
                "seed", prim.attribValue("pf_site_id") if sited else 0)))
        # `shapeO` IS the ring, and routing it here rather than cutting a
        # courtyard in B1 is §12.6 B1's own instruction ("the courtyard that
        # `shapeO` would cut is produced in B2 by insetting the footprint a
        # second time with the same rule").  Two mechanisms for one hole is how
        # a template ends up able to ask for a courtyard and not get one.
        prim.setAttribValue("_rails", RAILS.get(
            "ring" if op == "shapeO" else topo["rails"], 0))
        prim.setAttribValue("_cuts", [float(c) for c in topo["cutsAt"]])
        prim.setAttribValue("_roles", [str(v.get("role", "volume"))
                                       for v in volumes])
        prim.setAttribValue("_storeys", [int(v.get("storeys", 1))
                                         for v in volumes])
        prim.setAttribValue("_capgroups", [int(v.get("capGroup", 0))
                                           for v in volumes])
        # Per VOLUME, defaulting to the style's: a barn's single storey is as
        # tall as the dwelling's two, and without that they cannot sit under
        # the one continuous eave that makes an Einhof an Einhof.
        prim.setAttribValue("_storeyh",
                            [float(v.get("storeyHeightM",
                                         tpl["storeyHeightM"]))
                             for v in volumes])
        prim.setAttribValue("_courtyard", float(topo["courtyardDepthM"]))
        prim.setAttribValue("_plinth", PLINTH.get(topo["plinth"]["mode"], 0))
        prim.setAttribValue("_plinthmin",
                            float(topo["plinth"].get("minM", 0.0)))
        prim.setAttribValue("pf_warn_unknown_rule", unknown)
        shape = fp["shape"]
        prim.setAttribValue("_shape", SHAPES.get(op, 0))
        prim.setAttribValue("_shape_w", float(shape.get("widthM", 0.0)))
        prim.setAttribValue("_shape_d", float(shape.get("depthM", 0.0)))
        prim.setAttribValue("_shape_at", int(shape.get("at", 0)))

        # `identity` is `setback(0)` and `offset` is one uniform number on
        # every edge regardless of role - both are the per-role table emptied,
        # with a different fallback.  ⚠️ A NEGATIVE `offsetM` (CityEngine's
        # outward offset, §7) is NOT supported: `pf_collapse.vfl` flags a
        # footprint whose area GREW, so an outward offset degrades onto the lot
        # with the collapse warning.  Named rather than half-built - relaxing
        # that term is proven coverage and not this stage's to spend.
        table = {} if op in ("identity", "offset") else fp["setbackM"]
        fallback = (0.0 if op == "identity"
                    else float(fp["offsetM"]) if op == "offset"
                    else fp["defaultSetbackM"])
        # `R4-3`: §12.4 declares vertex AND prim legal for the authored
        # override, and only vertex was read - so a lot authoring a prim
        # `pf_setback` on a 10 x 90 einhof lot silently built the template's
        # numbers with all four warnings at 0.  Vertex wins where it is
        # authored, because a per-edge override must beat a per-face one or the
        # cascade stops being a cascade; a negative vertex value is ABSENT and
        # falls through to the prim class, then to the template.
        pfb = (prim.attribValue("pf_setback") if authored_prim else -1.0)
        for vtx in prim.vertices():
            sb = vtx.attribValue("pf_setback") if authored else -1.0
            if sb < 0.0:
                sb = pfb
            if sb >= 0.0:
                vtx.setAttribValue("_inset", sb)
            else:
                role = vtx.attribValue("pf_face_role")
                vtx.setAttribValue("_inset",
                                   float(table.get(role, fallback)))


def stamp_cap(geo, overrides=None, cache=None):
    """B5/B6 marshalling: the cap family's numbers onto the footprint loops.

    The same job `stamp()` does for B1/B2 and for the same reason - once per
    BUILDING, never per element - but it runs one stage later, on B2's output,
    and so it resolves the template off `pf_style_id` rather than off B0's
    `pf_style_template`.  It has to: `CLEAN` sweeps every `_*` at B2's output
    (conventions.md §2) and B2 publishes no cap data, so the numbers cannot
    ride through on the mass.  Carrying them would mean publishing three more
    `pf_*` names on every wall of every building to serve the roof.

    ⚠️ An unknown `capFamily.family` raises `pf_warn_unknown_rule` - the
    warning §12.8 already has, on a rule name it did not previously cover -
    and builds `flat`.  No new artist-facing contract is invented here.
    """
    import hou
    cache = {} if cache is None else cache
    for name, default in (("_cap", 0),):
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, default)
    for name in ("_pitchdeg", "_eave", "_eave_y", "_roof_y0", "_tanpitch"):
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, 0.0)
    if geo.findPrimAttrib("pf_warn_unknown_rule") is None:
        geo.addAttrib(hou.attribType.Prim, "pf_warn_unknown_rule", 0)

    for prim in geo.prims():
        style_id = prim.attribValue("pf_style_id")
        if style_id not in cache:
            cache[style_id] = resolve(load(style_id), overrides)
        cap = cache[style_id]["capFamily"]
        family = cap.get("family", "flat")
        prim.setAttribValue("_cap", CAPS.get(family, 0))
        prim.setAttribValue("_pitchdeg", float(cap.get("pitchDeg", 0.0)))
        prim.setAttribValue("_eave", float(cap.get("eaveDepthM", 0.0)))
        if family not in CAPS:
            prim.setAttribValue("pf_warn_unknown_rule", 1)


def corner_mode(template):
    """§12.6 B6's seam strategy for a resolved template, validated.

    ⚠️ IT IS PER BUILD, NOT PER BUILDING, and that limit is inherited rather
    than chosen: polyChain's facade carries the corner treatment as one PARM,
    and its own `[vex:corners]` refusal is likewise per-BUILD - one mitered
    corner anywhere sends the whole build to the Python reference (§0.0d).  So
    a stream mixing two templates that disagree about corners cannot be built
    in one cook today, and B6 will have to split the stream by treatment when
    that matters.  Named here because a silent "first template wins" is how a
    cascade level quietly stops working.
    """
    want = (template.get("junctions") or {}).get(
        "cornerMode", DEFAULTS["junctions"]["cornerMode"])
    return want if want in CORNERS else DEFAULTS["junctions"]["cornerMode"]


def build_shell(parent, mass, kit, overrides=None, corners="bend",
                name="b4"):
    """B4 facade + B5 cap + B6 junctions, wired downstream of B2's output.

    -> the output node.  `mass` is `build()`'s OUT; `kit` is a SOP emitting a
    polyChain module kit (§12.9's manifest is that kit's own contract, and no
    citygen kit ships yet - the gate authors one).

    THE SHAPE OF THIS STAGE IS THE FINDING, so it is stated here rather than
    in a report: **B4 is an adapter, not a builder.** `citygen_buildings.md`
    §0.0a predicted that B4 "may be largely polyChain CONFIGURATION" and it
    is - one wrangle turns B2's cap faces into the three things
    `facade.footprint_loops` asks for, and the shipped `pf_polychain_facade`
    asset does the rest, corner treatment included.  What is genuinely new
    here is B5 (`pf_cap.vfl` on a native straight skeleton) and B6's seam
    (`pf_seam.vfl`), which is ~40 lines of VEX between them.

    NOTHING in this chain branches on a style, exactly as B1/B2 do not: the
    corner treatment is read off the template through `corner_mode()` and the
    pitch and eave arrive as per-prim numbers.
    """
    import hou
    hou.hda.installFile(os.path.join(_ROOT, "otls",
                                     "pf_polychain_facade.hda")
                        .replace("\\", "/"))
    # The facade asset's VEX resolves `$POLYFACTORY` includes at cook time and
    # hython does not set it (dev-loop trap list, the same one the runner hits
    # for `sys.path`).
    hou.putenv("POLYFACTORY", _ROOT.replace("\\", "/"))

    def wrangle(nm, src, cls, src_input, extra=None):
        node = parent.createNode("attribwrangle", nm)
        node.parm("class").set(cls)
        node.parm("snippet").set(vex(src))
        node.setFirstInput(src_input)
        for idx, other in (extra or ()):
            node.setInput(idx, other)
        return node

    caps = parent.createNode("blast", name + "_caps")
    caps.setFirstInput(mass)
    caps.parm("group").set("@pf_wall_role=cap")
    caps.parm("grouptype").set("prims")
    caps.parm("negate").set(1)

    loops = wrangle(name + "_loops", "pf_facade_in", 1, caps)
    marshal = parent.createNode("python", name + "_cap_marshal")
    marshal.setFirstInput(loops)
    marshal.parm("python").set(
        "import hou\n"
        "from polyfactory.citygen import buildings\n"
        "buildings.stamp_cap(hou.pwd().geometry(), %r)\n" % (overrides,))

    facade = parent.createNode("pf_polychain_facade", name + "_facade")
    facade.setFirstInput(marshal)
    facade.setInput(1, kit)
    facade.parm("corner_mode").set(corners)

    eave = wrangle(name + "_eave", "pf_eave", 1, marshal)
    area = wrangle(name + "_eave_area", "pf_area0", 1, eave)
    ring = wrangle(name + "_eave_ring", "pf_inset", 2, area)
    seam = wrangle(name + "_seam", "pf_seam", 0, ring, extra=[(1, facade)])

    skel = parent.createNode("polyexpand2d", name + "_skeleton")
    skel.setFirstInput(seam)
    skel.parm("output").set("surfaces")
    skel.parm("outputinside").set(1)
    skel.parm("outputoutside").set(0)
    skel.parm("doedgedistattrib").set(1)
    # A straight skeleton terminates when its wavefront collapses, so the
    # offset only has to EXCEED the largest inradius in the stream; taken off
    # the input's own bounds rather than as a constant, because a constant
    # that is too small silently truncates the roof into a flat top.
    skel.parm("offset").setExpression(
        'bbox("../%s", D_XSIZE) + bbox("../%s", D_ZSIZE)'
        % (seam.name(), seam.name()))
    skel.parm("skeletonfailure").set("warn")

    roof = wrangle(name + "_cap", "pf_cap", 0, skel, extra=[(1, seam)])

    merge = parent.createNode("merge", name + "_merge")
    merge.setFirstInput(facade)
    merge.setInput(1, roof)
    final = wrangle(name + "_finalize", "pf_finalize", 1, merge)

    clean = parent.createNode("attribdelete", name + "_clean")
    clean.setFirstInput(final)
    for do, pat, value in CLEAN:
        clean.parm(do).set(1)
        clean.parm(pat).set(value)
    groups = parent.createNode("groupdelete", name + "_clean_groups")
    groups.setFirstInput(clean)
    groups.parm("group1").set("_*")

    out = parent.createNode("null", name + "_OUT")
    out.setFirstInput(groups)
    parent.layoutChildren()
    return out


def site(parent, lots, style="", name="b0"):
    """B0 - the SITE CONTRACT (§12.4), wired under `parent` downstream of the
    raw lot SOP.  -> the output node.  `style` is the zone default template id,
    cascade level 2, used only where the lot itself names none.

    IT SHIPS AS AN ADAPTER (§0.0a) and that is a deliberate, reversible choice:
    it ingests TODAY's planar S8 lot and stamps §12.4's volume + face-role
    schema in its degenerate planar form, so streets needs no change and no
    seam mismatch can arise.  ⚠️ The schema is Hannes' to ratify (§0.0g row 1)
    and nothing here records it as ratified.

    WHAT IT INGESTS, all optional: `pf_site_id` on the prim OR the detail
    class (§12.4 says B0 owns that conversion), `pf_seed` on the prim,
    `pf_style_template` on the prim OR the detail class, `pf_face_role` on the
    vertex OR the prim class, and `pf_setback` on the vertex class.  A bare
    closed polygon with none of them is a legal input.
    ⚠️ AND THAT IS WHAT AN S8 LOT IS TODAY as far as IDENTITY goes: streets
    publishes `block_id` / `lot_id` (`tests/citygen/checks.py`'s lot
    allowlist) and nothing in this repo writes `pf_site_id`, so an unidentified
    lot is the normal path and not an edge case.  `pf_site_in.vfl` gives it an
    order-independent id derived from its own plan position; it used to give it
    the primitive number, which is generation order and which §12.7 forbids.
    Teaching B0 to read the streets lot identity by name needs that attribute's
    storage settled with the streets owner (D223) and is the named next step.

    WHAT IT STAMPS: prim `pf_site_id`, prim `pf_seed`, prim
    `pf_style_template`, vertex `pf_face_role`, vertex `pf_setback`.  §12.4's
    `pf_coverage_max` / `pf_far_max` / `pf_height_max` are deliberately NOT
    stamped: nothing consumes them yet, and a published name carrying a value
    no stage reads is the exact defect shape §12.10a defect 5 names.  They
    arrive with the caps check that raises `pf_warn_coverage_exceeded`.

    ⛔ THE ONE THING B0 EXISTS TO MAKE IMPOSSIBLE is a missing `pf_setback`
    sentinel; the reasoning and the measurement are in `pf_site.vfl`'s header.
    ⚠️ THE RESIDUAL IS NOT "a stream that skips B0", which is what this
    docstring used to say.  Measured: a lot carrying a HAND-CREATED vertex
    `pf_setback` passes THROUGH B0 and still builds on its lot line with all
    four `pf_warn_*` at 0, so the guarantee is "every stream whose lot carries
    no vertex `pf_setback`".  `pf_site.vfl`'s header carries the numbers.

    THREE NODES, and the split between the first two is NOT load-bearing -
    this docstring claimed it was, on a premise measured false.  The claim was
    that a wrangle which WRITES an attribute has already created it by the time
    `has*attrib` is asked; on 22.0.398 `hasvertexattrib` returns 0 inside a
    wrangle that writes the attribute, before the write, after it, and under
    the `@`-binding form, while a positive control returns 1.  The split is
    kept because it is harmless and because everything the read node writes
    lands on `_*` scratch - so its tests are demonstrably asked of the input -
    but the guarantee does not depend on it and no argument should rest on it.
    """
    import hou

    def wrangle(nm, src, cls, src_input):
        node = parent.createNode("attribwrangle", nm)
        node.parm("class").set(cls)
        node.parm("snippet").set(vex(src))
        node.setFirstInput(src_input)
        return node

    read = wrangle(name + "_read", "pf_site_in", 1, lots)
    group = read.parmTemplateGroup()
    group.append(hou.StringParmTemplate("style", "Default Style Template", 1))
    read.setParmTemplateGroup(group)
    read.parm("style").set(style)

    out_w = wrangle(name + "_stamp", "pf_site", 1, read)

    clean = parent.createNode("attribdelete", name + "_clean")
    clean.setFirstInput(out_w)
    # The `_*` law (conventions.md §2) on all four classes, plus the two names
    # B0 NORMALISED off the volume form: a role carried on the prim class has
    # been re-emitted per vertex, and two classes of one contract name in one
    # stream is exactly the confusion §1 exists to prevent.  ⚠️ Prim
    # `pf_setback` is NOT swept here - it is a cascade override `stamp()` still
    # has to read (`R4-3`), and `CLEAN` sweeps it at B2's output instead.
    for do, pat, value in (("doptdel", "ptdel", "_*"),
                           ("dovtxdel", "vtxdel", "_*"),
                           ("doprimdel", "primdel", "_* pf_face_role"),
                           ("dodtldel", "dtldel", "_* pf_site_id "
                            "pf_style_template")):
        clean.parm(do).set(1)
        clean.parm(pat).set(value)
    groups = parent.createNode("groupdelete", name + "_clean_groups")
    groups.setFirstInput(clean)
    # GROUPS ARE THE FOURTH CLASS conventions.md §2 names, and B0 sweeps them
    # because a LOT can arrive carrying one - B0 itself makes none, which is
    # why nothing could make this line fail until the fixture brought one in.
    groups.parm("group1").set("_*")

    out = parent.createNode("null", name + "_OUT")
    out.setFirstInput(groups)
    parent.layoutChildren()
    return out


def build(parent, lots, ground=None, overrides=None, name="b2"):
    """Wire B1+B2 under `parent`, downstream of the `lots` SOP.  -> the output
    node.  `lots` emits lot polygons carrying prim `pf_site_id` (int), prim
    `pf_style_template` (string), vertex `pf_face_role` (string) and
    optionally vertex `pf_setback` (float).

    NOTHING in this chain branches on a style.  Both templates walk the same
    seven nodes; only the numbers and strings on the prims differ.
    """
    def wrangle(nm, src, cls, src_input, extra=None):
        node = parent.createNode("attribwrangle", nm)
        node.parm("class").set(cls)
        node.parm("snippet").set(vex(src))
        node.setFirstInput(src_input)
        for idx, other in (extra or ()):
            node.setInput(idx, other)
        return node

    marshal = parent.createNode("python", name + "_marshal")
    marshal.setFirstInput(lots)
    marshal.parm("python").set(
        "import hou\n"
        "from polyfactory.citygen import buildings\n"
        "buildings.stamp(hou.pwd().geometry(), %r)\n" % (overrides,))

    # B1's shape ops sit between the cascade and the inset: `shapeL`/`shapeU`
    # change the footprint's TOPOLOGY, and the per-role setback is then applied
    # to the shape that came out - which is CityEngine's order too (the parcel
    # is shaped, then set back).  A template that asks for neither leaves
    # `_shape` at 0 and the node returns on its first line.
    shape = wrangle(name + "_shape", "pf_shape", 1, marshal)
    area = wrangle(name + "_area", "pf_area0", 1, shape)
    inset = wrangle(name + "_setback", "pf_inset", 2, area)
    footprint = wrangle(name + "_footprint", "pf_collapse", 1, inset)

    yard_d = wrangle(name + "_yard_depth", "pf_yard_inset", 3, footprint)
    yard_i = wrangle(name + "_yard", "pf_inset", 2, yard_d)
    yard = wrangle(name + "_courtyard", "pf_collapse", 1, yard_i)

    mass = wrangle(name + "_mass", "pf_mass", 0, footprint,
                   extra=[(1, yard)] + ([(2, ground)] if ground else []))

    clean = parent.createNode("attribdelete", name + "_clean")
    clean.setFirstInput(mass)
    for do, pat, value in CLEAN:
        clean.parm(do).set(1)
        clean.parm(pat).set(value)
    groups = parent.createNode("groupdelete", name + "_clean_groups")
    groups.setFirstInput(clean)
    groups.parm("group1").set("_*")

    out = parent.createNode("null", name + "_OUT")
    out.setFirstInput(groups)
    parent.layoutChildren()
    return out
