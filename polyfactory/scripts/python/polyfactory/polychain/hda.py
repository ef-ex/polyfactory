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
  D88 A MARKER SLOT IS *NOT* PAYLOAD-ONLY. D85's sibling question, answered
      the other way: `marker:<id>` is a slot whose name carries a number, and
      PC-G1's own bullet is "a gate placed by a marker" - so an int and a
      module field put it on the page, inside the SAME `SLOT_PARMS` loop. And
      markers that arrive with no rule to read them now WARN, in either face:
      a silent no-op was the part that could not survive.
  D89 THE RANDOMNESS SCOPE IS PAYLOAD-ONLY. `style_from_parms` used to read a
      `scope` parm that the page never had, so every parm-face rule was
      `segment` with a dead read dressing it up as a choice. `segment` is
      passed literally now; per-section/per-spline randomness is a payload
      feature, like the conditional.
  D90 THE DRAG-TIME LOD SWITCH IS MANUAL, AND THE NODE SAYS SO. 5 asked for a
      plan preview while dragging and a full recook on release; a Python SOP
      cannot see a drag (there is no begin/end notification in a cook), so
      D81/D82 answered with a menu instead. What was missing was the pointer
      to it: a `full` cook over `SLOW_COOK_S` now warns, naming the proxy.
  D91 PADDING IS A PARM-FACE CONTROL (amends D84, and D77 is why). `_padded`
      used to run unconditionally, so a wired payload still felt the `padding`
      parm - measured, the same payload built 6 prims at 0.0 and 5 at 0.8, and
      D77's whole rationale is that one payload must build one fence on any
      node. The kit's own `pc_pad` is the pipeline face's padding.
"""

import os
import time

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

MARKER_PARM = "slot_marker"        # D88 - `marker:<id>`, id from `marker_id`

DISPLAY_MODES = ("full", "proxy", "plan")

# D90 - seconds of FULL cook above which the node says "use the proxy". Set
# just under artist_ui 6's abandonment latency. The measurement it was chosen
# against was a 20 km R = 40 m arc of 10 000 panels at ~11 s full against
# 0.6-0.8 s proxy; D102 took the full side of that to **1.86 s**, so the same
# run now sits just UNDER this threshold and no longer warns - which is the
# threshold doing its job, not a stale number. It stays at the latency, not
# at whatever the current build happens to cost.
SLOW_COOK_S = 2.0

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
    if geo is not None and geo.intrinsicValue("primitivecount"):
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
    # D88: the marker slot joins the SAME loop rather than growing a branch.
    # `marker:<id>` is a slot whose name carries a number, so the pair (an int
    # parm and a module field) is all the page needs to reach it.
    slots = list(SLOT_PARMS)
    if node.parm(MARKER_PARM) is not None:
        slots.append(("marker:%d" % int(node.evalParm("marker_id")
                                        if node.parm("marker_id") else 1),
                      MARKER_PARM))
    for slot, parm in slots:
        modules = _parm_str(node, parm).split()
        if not modules:
            continue
        # D89: `segment` literally - the randomness SCOPE is payload-only,
        # like the conditional (D85). There is no `scope` parm on the page.
        rules.append(Rule(slot, select if slot == "default" else "first",
                          modules, None, "segment"))
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
    names = set(m.name for m in kit.modules if m.name)
    for role in roles:
        if role in names:
            continue        # one token, one row: a role named after a module
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
    # the COUNT, not the wrappers - this runs on the 340 000-prim display path
    # and `len(geo.prims())` builds a tuple of that many `hou.Prim` objects to
    # answer a question `intrinsicValue` already holds.
    n = geo.intrinsicValue("primitivecount")
    if not present or not n:
        return 0
    # 11.2 P1: read every warn column and write `Cd` once, instead of one
    # `attribValue` per warn per prim and one `setAttribValue` per hit. The
    # UNWARNED prims keep whatever `Cd` they already had - a kit module may
    # ship its own colour, so this cannot just rebuild the array from white.
    cols = [geo.primIntAttribValues(a) for a in present]
    cd = list(geo.primFloatAttribValues("Cd"))
    hit = 0
    for i in range(n):
        if any(col[i] for col in cols):
            cd[i * 3], cd[i * 3 + 1], cd[i * 3 + 2] = WARN_COLOUR
            hit += 1
    if hit:
        geo.setPrimFloatAttribValues("Cd", cd)
    return hit


def _warn_unread_markers(node, curve_geo, style, from_payload):
    """D88 - markers arrived and NOTHING reads them. Say so.

    3.1 lets a generator merge marker points into input 1, and `plan` places a
    module for them only where a `marker:<id>` rule exists. Without this the
    whole feature is a silent no-op: the points cook to nothing, no warning
    fires, and PC-G1's "gate placed by marker" looks broken rather than
    unauthored.
    """
    if curve_geo is None or curve_geo.findPointAttrib("pc_marker") is None:
        return
    ids = set()
    for pt in curve_geo.points():
        try:
            if int(pt.attribValue("pc_marker")) == 1:
                ids.add(int(pt.attribValue("pc_marker_id")
                            if curve_geo.findPointAttrib("pc_marker_id")
                            else 0))
        except (TypeError, ValueError):
            continue
    if not ids:
        return
    read = set()
    for rule in style.rules:
        if str(rule.slot).startswith("marker:"):
            try:
                read.add(int(str(rule.slot)[7:]))
            except ValueError:
                continue
    unread = sorted(ids - read)
    if unread:
        node.addWarning(
            "input 1 carries markers with id %s and no rule reads them - %s"
            % (", ".join(str(i) for i in unread),
               "add a marker:<id> rule to the style payload" if from_payload
               else "set Marker Id and Piece at Marker"))


# --- the cook ---------------------------------------------------------------

def cook(node):
    """The whole node, in one pass. Never raises (warn-never-block)."""
    geo = node.geometry()
    geo.clear()
    curve_geo = _input_geo(node, 0)
    if curve_geo is None or not curve_geo.intrinsicValue("primitivecount"):
        node.addWarning("no spline on input 1 - nothing to dress")
        return

    parms = parm_owner(node)
    kit_geo = kit_geometry(node, parms)
    style, warns = _style.read(_input_geo(node, 2),
                               kit=_kit.read(kit_geo)[0])
    for warn in warns:
        node.addWarning(warn)
    from_payload = style is not None
    if style is None:
        style = style_from_parms(parms)
        # D91, amending D84: the gap is a PARM-FACE control. Applying it
        # under a wired payload broke D77's own guarantee - measured, a 12 m
        # spline with the same payload built 6 prims at padding 0 and 5 at
        # 0.8, so one payload made two different fences on two nodes. A
        # pipeline consumer pads with the kit's own `pc_pad`, which is the
        # mechanism this parm rides anyway.
        kit_geo = _padded(kit_geo, parms.evalParm("padding")
                          if parms.parm("padding") else 0.0)
    if not style.rules:
        node.addWarning("no modules assigned - fill at least Repeating Pieces")
    _warn_unread_markers(node, curve_geo, style, from_payload)

    display = _parm_str(parms, "display", "full")
    if display not in DISPLAY_MODES:
        display = "full"
    if display != "full":
        kit_geo = proxy_kit(kit_geo)                          # D82

    t0 = time.time()
    out, report = _place.build(curve_geo, kit_geo, style,
                               params=style.params,
                               surface_geo=_input_geo(node, 3))
    cook_s = time.time() - t0
    if display == "full" and cook_s > SLOW_COOK_S:
        # D90: the LOD switch is MANUAL, so the artist has to be told the
        # menu is there. A full cook this long is one freeze per slider tick.
        node.addWarning("this build took %.1f s - set Display to 'Proxy "
                        "Boxes' while dragging (it is exact, just boxes)"
                        % cook_s)
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
