"""polyChain 5 THE PARM FACE - everything `pf_polychain` does when it cooks.

The HDA is a wrapper: four inputs, one Python SOP, and this module. Keeping
the code here rather than in an HDA section is the same call the rest of the
suite makes - it is version-controlled, it is importable by the headless
checks, and a fix does not require re-saving a binary asset.

    devScripts/create_pf_polychain_hda.py    builds the asset
    polyfactory/otls/pf_polychain.hda        the asset itself

THE TWO FACES, RESOLVED IN ONE FUNCTION (2.1). `cook` asks `style.read` for a
payload on input 3 first; when there is one it is used WHOLE and the parms are
not consulted at all (D77). When there is not, `style_from_parms` builds the
same object out of the parameter page. One kernel, two authoring faces, and
the kernel cannot tell them apart - which is the property PC-G4 audits.

DECISIONS TAKEN HERE (recorded in polychain.md 10):

  D80 EVERY PARM THAT IS A KERNEL PARAMETER IS NAMED AFTER IT. `fill`,
      `bend_tol`, `conform_axis` and the rest carry the `Params` field name,
      so `params_from_parms` is a loop over `Params`' own fields and NOT a
      table that has to be edited twice. The artist never sees these names -
      the LABEL is what 6.3 asks to be nameable in a sentence ("Fit method",
      "Bend tolerance"), and labels are free to be prose.
  D81 THE PLAN IS A DISPLAY MODE, NOT A SECOND OUTPUT. 4.2 wants the plan
      inspectable and 5 wants a preview while dragging; one output plus a
      `display` menu gives both, where a second output would have to be
      cooked, wired and explained. `plan_points`' docstring said "the HDA's
      second output" as an aspiration; this is the answer it was waiting for.
  D82 THE PROXY LOD IS A PROXY KIT, NOT A SECOND CODE PATH (5's acceptance
      criterion). Every module is swapped for a rigid box at its own nominal
      size and the UNCHANGED kernel is run on it: rigid short-circuits the
      deform gate at D27, so nothing bends, nothing is sliced and the whole
      run is packed prims. The proxy is therefore positionally exact - it is
      the same plan, the same corners and the same transforms - and it costs
      one box per module instead of one deform per piece. A second draw path
      would have had to be kept in step with the first one forever.
  D83 INSTANCING OVERRIDE = `bend_tol`. 5 asks for "instancing overrides" in
      the Advanced folder, and D75 already made the packed/deformed split a
      measured budget in metres. Exposing that number IS the override - 0
      unpacks everything that curves at all, a large value keeps everything
      packed - and inventing a second toggle beside it would give the artist
      two controls for one decision.
  D84 PADDING IS A KIT EDIT, NOT A NEW KERNEL FIELD. 3.2's `pc_pad` is the
      only padding the kernel knows and 4.2 spends it correctly (padding moves
      the neighbours, never the piece). The `padding` parm adds metres to
      every module's own pad on a COPY of the kit, so one artist-facing
      "Gap between pieces" rides the mechanism that already exists.
  D85 A CONDITIONAL RULE IS PAYLOAD-ONLY. `pc_cond` is a {subject, op, value}
      dict and no sane parameter page authors one; the parm face offers
      first/in turn/random and the pipeline face carries conditionals. This is
      2.1 working as designed rather than a gap - the escape hatch is the
      other face, not a text field.
"""

import os

import hou

from . import DEFAULTS, Params, Rule, SELECTORS, Style
from . import kit as _kit
from . import place as _place
from . import style as _style

# (slot, parm) - 3.3's slots as the parameter page spells them. A LIST, so
# `style_from_parms` stays a loop and never grows a branch per slot.
SLOT_PARMS = (("default", "slot_default"), ("start", "slot_start"),
              ("end", "slot_end"), ("corner", "slot_corner"),
              ("evenly", "slot_evenly"))

DISPLAY_MODES = ("full", "proxy", "plan")

WARN_COLOUR = (1.0, 0.25, 0.1)


def parm_owner(node):
    """The node the PARAMETERS live on.

    ⚠️ `hou.pwd()` inside the HDA is the Python SOP, and the Python SOP has
    exactly two parms of its own - so every `node.parm("display")` read there
    returns None and the whole page silently reads as empty. Measured: the
    asset built 0 prims, raised nothing and warned nothing, because a style
    with no rules is a legal style. The parms are one level up, and asking for
    them explicitly is what keeps that from happening again.
    """
    return node if node.parm("display") is not None else node.parent()


def _parm_str(node, name, default=""):
    parm = node.parm(name)
    return default if parm is None else str(parm.evalAsString())


def _input_geo(node, index):
    """Input `index`, or None when it is unwired (D34 - not an error)."""
    inputs = node.inputs()
    if index >= len(inputs) or inputs[index] is None:
        return None
    try:
        return node.inputGeometry(index)
    except hou.OperationFailed:
        return None


# --- the kit (3.2, and 6's "shipped with the HDA") --------------------------

def kit_geometry(node, parms=None):
    """Input 2, else the kit file, else the built-in starter fence.

    6's standalone-usability floor: a curve into input 1 and NOTHING else must
    make a fence. `starter_kit()` is a builder rather than a shipped .bgeo
    (D23), so the fallback costs no file and cannot go stale.
    """
    parms = parms if parms is not None else parm_owner(node)
    geo = _input_geo(node, 1)
    if geo is not None and len(geo.prims()):
        return geo
    path = hou.text.expandString(_parm_str(parms, "kitfile")).strip()
    if path:
        try:
            loaded = hou.Geometry()
            loaded.loadFromFile(path)
            return loaded
        except hou.OperationFailed as exc:
            node.addWarning("kit file %r could not be read (%s) - using the "
                            "built-in starter kit" % (path, str(exc)[:80]))
    return _kit.starter_kit()


def _padded(kit_geo, padding):
    """D84 - `padding` metres added to every module's own `pc_pad`."""
    if abs(padding) < 1e-9:
        return kit_geo
    out = hou.Geometry()
    out.merge(kit_geo)
    if out.findPointAttrib("pc_pad") is None:
        out.addAttrib(hou.attribType.Point, "pc_pad", (0.0, 0.0))
    for pt in out.points():
        pad = pt.attribValue("pc_pad")
        pt.setAttribValue("pc_pad", (pad[0] + 0.5 * padding,
                                     pad[1] + 0.5 * padding))
    return out


def proxy_kit(kit_geo):
    """D82 - the same manifest, every module a RIGID box at its nominal size.

    Rigid is what makes this cheap: D27 short-circuits the deform gate, so
    every piece of the proxy run is a packed prim sharing one of a handful of
    box geometries. The manifest is copied field for field, so the plan, the
    corners and the transforms are the ones the full build will use.
    """
    kit, _sources, _warns = _kit.read(kit_geo)
    out = hou.Geometry()
    for module in kit.modules:
        sx = max(module.size[0], 1e-3)
        sy = max(module.size[1], 1e-3)
        sz = max(module.size[2], 1e-3)
        box = hou.Geometry()
        _kit.box_mesh(box, 0.0, sx, 0.0, sy, -0.5 * sz, 0.5 * sz, 1)
        _kit.add_module(out, module.name, box, size=module.size,
                        pad=module.pad, deform=0, zmode=module.zmode,
                        roles=" ".join(module.roles), variant=module.variant,
                        weight=module.weight, tilt=module.tilt)
    _kit.write_manifest(out, kit.kit_id + "_proxy", kit.version,
                        sources=("polychain.hda.proxy_kit",),
                        human_scale_reference=kit.human_scale_reference)
    return out


# --- the parm face (5) ------------------------------------------------------

def params_from_parms(node):
    """`Params` straight off the parameter page (D80 - names match fields)."""
    node = parm_owner(node)
    kw = {}
    for key in _style.PARAM_KEYS:
        tup = node.parmTuple(key)
        if tup is None:
            continue
        value = tup.eval()
        kw[key] = value[0] if len(value) == 1 else tuple(value)
    try:
        return Params(**kw)
    except Exception:
        return _style.params_from_dict(kw, [])       # per-key degrade (D78)


def style_from_parms(node):
    """The parameter page as a `Style` - the standalone artist face (2.1)."""
    node = parm_owner(node)
    select = _parm_str(node, "variety", "first")
    if select not in SELECTORS:
        select = "first"
    rules = []
    for slot, parm in SLOT_PARMS:
        modules = _parm_str(node, parm).split()
        if not modules:
            continue
        rules.append(Rule(slot, select if slot == "default" else "first",
                          modules, None, _parm_str(node, "scope", "segment")))
    return Style(_parm_str(node, "style_id", "pf_polychain"), 1,
                 int(node.evalParm("seed") if node.parm("seed") else 0),
                 rules, params_from_parms(node))


def slot_menu(node):
    """The kit manifest as a menu (5's "per-slot module menus").

    Names first, then the roles they answer to, so an artist can point a slot
    at `panel` (one module) or at `default` (whatever the kit tags that way).
    """
    try:
        kit, _sources, _warns = _kit.read(kit_geometry(node))
    except Exception:
        return []
    items = []
    for module in kit.modules:
        if module.name:
            items.extend([module.name, module.name])
    roles = []
    for module in kit.modules:
        for role in module.roles:
            if role not in roles:
                roles.append(role)
    for role in roles:
        items.extend([role, "%s  (role)" % role])
    return items


# --- warnings (5's visualisation toggle) ------------------------------------

def colour_warnings(geo, warn_names):
    """Every element carrying a warning turned red, and how many there were.

    2.2's advisory validation made visible: warn-never-block only works if the
    artist can SEE what was warned about, and a warning that only exists as an
    attribute is one nobody reads.
    """
    if not warn_names:
        return 0
    if geo.findPrimAttrib("Cd") is None:
        geo.addAttrib(hou.attribType.Prim, "Cd", (1.0, 1.0, 1.0))
    present = [n for n in warn_names if geo.findPrimAttrib(n) is not None]
    hit = 0
    for prim in geo.prims():
        if any(prim.attribValue(n) for n in present):
            prim.setAttribValue("Cd", WARN_COLOUR)
            hit += 1
    return hit


# --- the cook ---------------------------------------------------------------

def cook(node):
    """The whole node, in one pass. Never raises (warn-never-block)."""
    geo = node.geometry()
    geo.clear()
    curve_geo = _input_geo(node, 0)
    if curve_geo is None or not len(curve_geo.prims()):
        node.addWarning("no spline on input 1 - nothing to dress")
        return

    parms = parm_owner(node)
    kit_geo = kit_geometry(node, parms)
    style, warns = _style.read(_input_geo(node, 2),
                               kit=_kit.read(kit_geo)[0])
    for warn in warns:
        node.addWarning(warn)
    if style is None:
        style = style_from_parms(parms)
    if not style.rules:
        node.addWarning("no modules assigned - fill at least Repeating Pieces")

    kit_geo = _padded(kit_geo, parms.evalParm("padding")
                      if parms.parm("padding") else 0.0)
    display = _parm_str(parms, "display", "full")
    if display not in DISPLAY_MODES:
        display = "full"
    if display != "full":
        kit_geo = proxy_kit(kit_geo)                          # D82

    out, report = _place.build(curve_geo, kit_geo, style,
                               params=style.params,
                               surface_geo=_input_geo(node, 3))
    if display == "plan":                                     # D81
        _place.plan_points(geo, report)
    else:
        geo.merge(out)
        if parms.parm("show_warnings") and parms.evalParm("show_warnings"):
            colour_warnings(geo, report["warn_names"])
    for name in report["kit_warnings"]:
        node.addWarning(str(name))
    for name, count in sorted(report["warn_counts"].items()):
        if count:
            node.addWarning("%s on %d elements" % (name, count))
    return report


def build_starter_kit_file(path=None):
    """6's starter-kit deliverable, on disk for an artist who wants one.

    Nothing in the build reads it (D23) - `kit_geometry` falls back to the
    builder - so this is a convenience, not a dependency.
    """
    path = path or os.path.join(
        hou.text.expandString("$POLYFACTORY") or ".",
        "library", "polychain", "pf_fence_starter.bgeo").replace("\\", "/")
    folder = os.path.dirname(path)
    if folder and not os.path.isdir(folder):
        os.makedirs(folder)
    return _kit.write_kit_file(path)
