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
tuple.  `_plain()` is what makes the claim true, so nothing may read the raw
attribute; `load()` is the only door.
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
    "lotToFootprint": {"op": "setback", "setbackM": {},
                       "defaultSetbackM": 0.0},
    "volumeTopology": {
        "rails": "bar",
        "cutsAt": [],
        "courtyardDepthM": 0.0,
        "volumes": [{"role": "volume", "storeys": 1, "capGroup": 0}],
        "plinth": {"mode": "none", "minM": 0.0},
    },
    "capFamily": {"family": "flat"},
}

# The rule vocabulary.  Adding a style must never add a member here; that is
# what gate G1 is testing.
RAILS = {"bar": 0, "ring": 1}
PLINTH = {"none": 0, "levelToHighest": 1}

# conventions.md §2/§5: `_*` leaves on no class, and neither does the VERTEX
# `pf_face_role` the lot arrived with - B2 re-emits it per PRIM on the walls
# that inherit it, and two classes of one contract name in one stream is
# exactly the confusion §1 exists to prevent.  Named, because the check that
# enforces the law is only worth having if its mutation can remove a sweep.
#
# `pf_style_template` goes the same way, for the same reason and one more: it
# is B0's REQUEST, `pf_style_id` is the template that answered it, and after
# the mass wrangle removes the footprint prims the request survives as an
# attribute definition with an empty value on every face - a name in the
# published-names baseline carrying nothing. B6's per-building DNA point is
# where the template id belongs (§12.6), not on every wall.
CLEAN = (("doptdel", "ptdel", "_*"),
         ("dovtxdel", "vtxdel", "_* pf_face_role"),
         ("doprimdel", "primdel", "_* pf_style_template"),
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
    iterable that is not a string or a dict is flattened here."""
    if isinstance(value, dict):
        return dict((k, _plain(v)) for k, v in value.items())
    if isinstance(value, (str, bytes)):
        return value
    try:
        return [_plain(v) for v in value]
    except TypeError:
        return value


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
            vertex `pf_face_role` (string), optional vertex `pf_setback`.
    Writes  the `_*` marshalling attributes, `pf_style_id`, `pf_seed`.

    The optional authored `pf_setback` is cascade level 5 and it WINS over the
    template's per-role number - "use the authored value if present, otherwise
    compute one", never compute alone (citygen.md §2.1).
    """
    import hou
    cache = {} if cache is None else cache

    for name, kind in (("_roles", hou.attribData.String),
                       ("_storeys", hou.attribData.Int),
                       ("_capgroups", hou.attribData.Int),
                       ("_storeyh", hou.attribData.Float),
                       ("_cuts", hou.attribData.Float)):
        if geo.findPrimAttrib(name) is None:
            geo.addArrayAttrib(hou.attribType.Prim, name, kind)
    for name, default in (("_rails", 0), ("_plinth", 0), ("pf_seed", 0),
                          ("pf_warn_unknown_rule", 0)):
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, default)
    for name, default in (("_courtyard", 0.0), ("_plinthmin", 0.0)):
        if geo.findPrimAttrib(name) is None:
            geo.addAttrib(hou.attribType.Prim, name, default)
    if geo.findPrimAttrib("pf_style_id") is None:
        geo.addAttrib(hou.attribType.Prim, "pf_style_id", "")
    if geo.findVertexAttrib("_inset") is None:
        geo.addAttrib(hou.attribType.Vertex, "_inset", 0.0)
    authored = geo.findVertexAttrib("pf_setback") is not None

    for prim in geo.prims():
        style_id = prim.attribValue("pf_style_template")
        if style_id not in cache:
            cache[style_id] = resolve(load(style_id), overrides)
        tpl = cache[style_id]
        topo = tpl["volumeTopology"]
        volumes = topo["volumes"] or DEFAULTS["volumeTopology"]["volumes"]
        unknown = int(topo["rails"] not in RAILS
                      or topo["plinth"]["mode"] not in PLINTH)

        prim.setAttribValue("pf_style_id", tpl["styleId"] or style_id)
        prim.setAttribValue("pf_seed", int(tpl.get("seed", 0)))
        prim.setAttribValue("_rails", RAILS.get(topo["rails"], 0))
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

        fp = tpl["lotToFootprint"]
        table = fp["setbackM"] if fp["op"] != "identity" else {}
        fallback = 0.0 if fp["op"] == "identity" else fp["defaultSetbackM"]
        for vtx in prim.vertices():
            if authored and vtx.attribValue("pf_setback") > 0.0:
                vtx.setAttribValue("_inset", vtx.attribValue("pf_setback"))
            else:
                role = vtx.attribValue("pf_face_role")
                vtx.setAttribValue("_inset",
                                   float(table.get(role, fallback)))


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

    area = wrangle(name + "_area", "pf_area0", 1, marshal)
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
