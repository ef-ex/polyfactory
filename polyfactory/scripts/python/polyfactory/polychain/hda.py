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
import struct
import time

import hou

from . import DEFAULTS, EPS, Params, Rule, SELECTORS, Style
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
    """D84 - `padding` metres added to every module's own `pc_pad`.

    ⚠️ IN BULK, not point by point. This used to iterate `out.points()` and
    call `attribValue` / `setAttribValue` on each - the exact pattern 11.9
    rule 1 forbids and the standing wrapper tripwires watch for - on every
    cook where the gap parm is non-zero. The kit is small, so it never showed
    up in a number; it was still the forbidden shape sitting in the cook path,
    and 15.6's inventory did not list it.
    """
    if abs(padding) < 1e-9:
        return kit_geo
    out = hou.Geometry()
    out.merge(kit_geo)
    if out.findPointAttrib("pc_pad") is None:
        out.addAttrib(hou.attribType.Point, "pc_pad", (0.0, 0.0))
    half = 0.5 * padding
    out.setPointFloatAttribValues(
        "pc_pad", [v + half for v in out.pointFloatAttribValues("pc_pad")])
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


# --- 13.3 THE NODE NETWORK: the two Python SOPs the graph still contains ----
#
# Hannes' rule: "everything geometry related should be either native nodes,
# vex or opencl. Python can be used for ui or processing data which is not
# possible to process with the other 3 mentioned options."
#
# `cook_config` is the FIRST of those two and it is the permanent one: it is
# parameter and payload marshalling, its N is the size of the parameter page,
# it touches no geometry, and its output is a dict VEX reads natively.
# `cook_plan_bridge` is the SECOND and it is SCAFFOLDING - 13.9 N2 deletes it
# the day the fitting solve lands in VEX.  It is labelled as such in the
# network and in its own docstring so nobody mistakes it for a fixture.

CONFIG_KEYS = ("corner_angle_deg", "min_included_angle_deg", "fillet_radius",
               "fillet_segments", "corner_mode", "corner_displacement",
               "corner_offset_pct", "fill", "adaptive_pct", "count",
               "evenly_spacing", "evenly_count", "justify", "adjust_to_end",
               "zmode", "flatten_stepped", "flat_band", "flat_band_m",
               "fix_slope", "bend_tol", "conform_tilt")


def config_dict(node):
    """13.3.0's `pc_cfg` - the resolved parameters, payload precedence applied.

    ONE function, both faces (2.1): `style.read` on input 3 wins whole (D77),
    and the parameter page answers when there is no payload.  Nothing
    downstream reads a parm, which is what keeps the graph generic and PC-G4
    passing by construction.
    """
    return config_resolved(node)[0]


def config_resolved(node):
    """(`pc_cfg`, the resolved Style, the resolved Kit).

    13.9 N2 - the CONFIG SOP now publishes the kit and the rule table beside
    the scalars, and all three have to come from ONE resolution or the arrays
    would describe a different style than the dict does.  `config_dict` is the
    same function with two of the three thrown away.

    ⚠️ THE STYLE IS NEVER None HERE.  `config_dict` used to leave it None when
    no payload was wired and read the parameters instead; the rule TABLE has
    no such fallback available to it, so the parm page's own `Style` (2.1's
    other face) is built explicitly.  That is what makes `Stage = plan` answer
    about the same rules the artist sees on the page.
    """
    parms = parm_owner(node)
    # ⚠️ THE KIT GOES IN TOO. `cook` and `cook_plan_bridge` both hand
    # `style.read` the kit so a payload naming a module the kit does not have
    # warns; without it this node resolved the same payload against a
    # different world and its warnings disagreed with the kernel's.
    kit, _sources, kit_warns = _kit.read(kit_geometry(node, parms))
    style, style_warns = _style.read(_input_geo(node, 2), kit=kit)
    params = style.params if style is not None else params_from_parms(parms)
    from_payload = style is not None
    if style is None:
        style = style_from_parms(node)
    out = {}
    for key in CONFIG_KEYS:
        value = getattr(params, key, None)
        if value is None:
            continue
        out[key] = float(value) if isinstance(value, bool) else value
    out["style_id"] = str(getattr(style, "style_id", "")
                          or _parm_str(parms, "style_id", "pf_polychain"))
    out["seed"] = float(getattr(style, "seed", 0))
    out["from_payload"] = 1.0 if from_payload else 0.0
    # 13.9 N4 - `pc_proto` has to know whether 4.5 is going to move the piece,
    # because D55's camber up-vector and D98's flatten-under datum both come
    # from the surface and neither is derivable in the PLACE box.  A build
    # with a surface wired declares its frames unanswerable rather than
    # drawing them in the wrong place (D160's rule, in a new stage).
    # ⚠️ `is not None` IS NOT THE TEST.  Every stage wrangle is wired to the
    # IN_SURFACE *null*, which exists whether or not the HDA's own input 4 is
    # connected, so `_input_geo` hands back an EMPTY geometry rather than
    # None - measured, `has_surface` read 1.0 with nothing wired and the
    # whole native PLACE branch declared itself unanswerable and shipped
    # zero prims, silently. The question is whether there is a surface, so
    # the test is whether there are primitives.
    surface = _input_geo(node, 3)
    out["has_surface"] = 1.0 if (surface is not None
                                 and surface.intrinsicValue("primitivecount")
                                 ) else 0.0
    # 13.9 N10, LEVEL 1 OF THE GUARD SWITCH: may the NATIVE chain serve this
    # build's `Stage = output`?
    #
    # ⚠️ THE ANSWER LIVES HERE BECAUSE THIS NODE ALREADY HOLDS THE THREE
    # THINGS IT NEEDS - the resolved Params, the Style and the Kit - and none
    # of them is geometry.  That is the half of Hannes' rule Python keeps, and
    # putting the test anywhere else would mean resolving the payload twice.
    # `pc_envelope.vfl` adds what only the decomposed spline can say (a corner,
    # a duplicated curve id) and `pc_envelope2.vfl` what only the plan can.
    #
    # EVERY ROW IS AN UNPORTED STAGE, NAMED.  The list must shrink as 13.9
    # lands, and `output_guard_envelope` prints which case each row refused so
    # a row that stops mattering is visible rather than merely harmless.
    out["native_ok"] = 1.0 if _native_ok(
        parms, params, style, kit, out,
        list(kit_warns) + list(style_warns)) else 0.0
    return (out, style, kit)


def _native_ok(parms, params, style, kit, cfg, warns):
    """13.9 N10 level 1 - see `config_resolved`. True when nothing in the
    parameters, the style or the kit needs a stage that is still Python."""
    if cfg.get("has_surface"):
        return False                                  # 4.5 conform - N6
    if float(getattr(params, "fillet_radius", 0.0) or 0.0) > EPS:
        return False                                  # 4.3 fillet - N8
    if getattr(params, "fix_slope", False):
        return False                                  # D26 slope fix - N5
    if getattr(params, "flatten_stepped", False):
        return False                                  # D98 flatten-under - N5
    if (getattr(params, "flat_band", "") in ("top", "bottom")
            and float(getattr(params, "flat_band_m", 0.0) or 0.0) > EPS):
        return False                                  # D99 band - N5
    if getattr(params, "fill", "") == "tile":
        return False                                  # 4.6 slice caps - N7
    if warns or not getattr(style, "rules", ()):
        # `kit.read`'s validation is Python and stays Python (13.6), so the
        # native chain publishes an EMPTY `pc_kit_warnings`; it may only do
        # that where the reference would too. A style with no rules builds
        # nothing and warns, which is the reference's own answer.
        return False
    if _parm_str(parms, "display", "full") != "full":
        return False                                  # D81 plan, D82 proxy
    for name in ("show_warnings",):
        if parms.parm(name) is not None and parms.evalParm(name):
            return False                              # `colour_warnings`' Cd
    if parms.parm("padding") is not None \
            and abs(float(parms.evalParm("padding"))) > EPS:
        # D91's kit padding rewrites the KIT, and `cook_kit` does not do it.
        return False
    return True


# --- 13.9 N2: the KIT and the RULE TABLE, flattened for VEX ------------------
#
# 4.2's fitting solve reads a kit and a 3.3 rule list.  Neither is geometry
# and neither can be looked up from VEX in the shape Python holds it in - a
# `Kit` is objects with properties, a `Rule` has a nested `cond` dict whose
# `value` is any JSON type - so the CONFIG SOP publishes both as FLAT PARALLEL
# ARRAYS on the same detail the `pc_cfg` dict already rides on.
#
# This is the second half of Hannes' rule ("processing data which is not
# possible to process with the other 3"), not a loophole: N is the module
# count plus the rule count, it runs once per cook, and it touches no
# geometry.  What it must NOT do is decide anything - every ordering,
# fallback and default below is the one `polychain.Kit` / `polychain.Style`
# already made, transcribed.
#
# ⚠️ PAYLOAD ORDER IS LOAD-BEARING ON BOTH TABLES.  `Kit.by_role` is
# documented "payload order preserved - deterministic, never set iteration",
# and `Style.rules_for` is "payload order preserved: the first rule that
# yields wins".  A flattening that sorted either one would be a different
# tool.

KIT_TABLE = (
    ("pc_k_name", "name", ""), ("pc_k_variant", "variant", ""),
    ("pc_k_zmode", "zmode", "adaptive"),
    ("pc_k_len", "length", 0.0), ("pc_k_weight", "weight", 1.0),
    ("pc_k_deform", "deform", 0), ("pc_k_missing", "missing", 0),
    ("pc_k_tilt", "tilt", -1), ("pc_k_extend", "extend", -1),
)

# ⚠️ EVERY FLOAT COLUMN CROSSES AS A DECIMAL STRING, AND THAT IS R2, NOT
# FUSSINESS.  Measured this cycle on 22.0.398, writing 0.35 from Python and
# reading it back in a `vex_precision = 64` wrangle:
#
#     a FLOAT ARRAY attribute  ->  0.34999999403953552   (float32 storage)
#     a DICT attribute         ->  0.34999999999999998   (float64, exact)
#     `atof(repr(0.35))`       ->  0.34999999999999998   (float64, exact)
#
# `hou.Geometry` has no 64-bit float array (D170 found the same thing for
# scalars), so a kit whose module is 0.35 m long reached the solve at 32 bits
# and the plan came back 2.7e-9 out - which 13.8 calls a defect, not float
# noise.  The 89 scene cases could not see it: every length in the starter kit
# (0.12, 2.0, 1.6, 0.9) is exactly representable in float32, and it took the
# stress matrix's own kit to expose it.
#
# `repr` rather than `%.17g` because it round-trips exactly AND stays readable
# in the geometry spreadsheet: `0.35`, not `0.34999999999999998`.  A DICT
# would also have been exact, but a dict read copies the whole table on every
# accessor call where an array read copies one column.
KIT_FLOAT_COLUMNS = ("pc_k_len", "pc_k_pad0", "pc_k_pad1", "pc_k_weight")
RULE_FLOAT_COLUMNS = ("pc_r_cnum", "pc_r_clnum", "pc_r_wval")


def _exact(value):
    """A float as the decimal string VEX's `atof` reads back bit for bit."""
    return repr(float(value))

# 3.3's `pc_cond` value is any JSON type, and VEX has no such thing.  The KIND
# says which of the three columns beside it carries the value, and it is what
# lets `pc_plan.h` reproduce `evaluate_cond`'s "anything unreadable is False"
# without a type system: 0 = no condition, 1 = number, 2 = string,
# 3 = list (the `in` operator's right-hand side), 4 = unreadable.
COND_NONE, COND_NUM, COND_STR, COND_LIST, COND_BAD = 0, 1, 2, 3, 4


def _cond_columns(cond):
    """One 3.3 condition as (kind, number, string, [(kind, num, str)]).

    The LIST keeps a per-item kind, because `in` is type-sensitive in Python
    and flattening `[1, 3, 5]` to strings would make `segIndex in [1, 3, 5]`
    false for every piece - `1 in ["1"]` is False.
    """
    if not cond:
        return (COND_NONE, 0.0, "", [])
    value = cond.get("value")
    if isinstance(value, bool):
        return (COND_NUM, 1.0 if value else 0.0, "", [])
    if isinstance(value, (int, float)):
        return (COND_NUM, float(value), "", [])
    if isinstance(value, str):
        return (COND_STR, 0.0, value, [])
    if isinstance(value, (list, tuple)):
        items = []
        for v in value:
            if isinstance(v, bool):
                items.append((COND_NUM, 1.0 if v else 0.0, ""))
            elif isinstance(v, (int, float)):
                items.append((COND_NUM, float(v), ""))
            elif isinstance(v, str):
                items.append((COND_STR, 0.0, v))
            else:
                items.append((COND_BAD, 0.0, ""))
        return (COND_LIST, 0.0, "", items)
    return (COND_BAD, 0.0, "", [])


def kit_table(kit):
    """`Kit` -> the flat arrays `pc_plan.h` binds.  Payload order, unsorted."""
    mods = list(getattr(kit, "modules", ()) or ())
    out = dict((name, []) for name, _f, _d in KIT_TABLE)
    out["pc_k_roles"] = []
    out["pc_k_pad0"] = []
    out["pc_k_pad1"] = []
    for module in mods:
        for name, field, default in KIT_TABLE:
            value = getattr(module, field, default)
            if isinstance(default, str):
                out[name].append(str(value))
            elif isinstance(default, float):
                out[name].append(float(value))
            else:
                out[name].append(int(value))
        # `Module.roles` is already normalised to a tuple by `_roles`; the
        # space join is only a transport, and `pc_kit_role` splits it back.
        out["pc_k_roles"].append(" ".join(str(r) for r in module.roles))
        out["pc_k_pad0"].append(float(module.pad[0]))
        out["pc_k_pad1"].append(float(module.pad[1]))
    for name in KIT_FLOAT_COLUMNS:
        out[name] = [_exact(v) for v in out[name]]
    return out


def rule_table(style):
    """`Style` -> the flat arrays `pc_plan.h` binds.  Payload order, unsorted.

    `modules`, `weights` and a list-valued `cond` are ragged, so each is a
    FLAT array plus a (start, count) pair per rule - the same shape
    `pc_arclength` already uses for its per-curve segment tables.
    """
    rules = list(getattr(style, "rules", ()) or ())
    out = {"pc_r_slot": [], "pc_r_select": [], "pc_r_scope": [],
           "pc_r_yclass": [], "pc_r_axis": [], "pc_r_vexpr": [],
           "pc_r_mod0": [], "pc_r_modn": [], "pc_r_mods": [],
           "pc_r_w0": [], "pc_r_wn": [], "pc_r_wkey": [], "pc_r_wval": [],
           "pc_r_ckind": [], "pc_r_csubj": [], "pc_r_cop": [],
           "pc_r_cnum": [], "pc_r_cstr": [],
           "pc_r_cl0": [], "pc_r_cln": [], "pc_r_clist": [],
           "pc_r_clnum": [], "pc_r_clkind": []}
    for rule in rules:
        out["pc_r_slot"].append(str(rule.slot))
        out["pc_r_select"].append(str(rule.select))
        out["pc_r_scope"].append(str(rule.scope))
        out["pc_r_yclass"].append(str(getattr(rule, "yclass", "") or ""))
        out["pc_r_axis"].append(str(getattr(rule, "axis", "x")))
        out["pc_r_vexpr"].append(str(rule.vexpr or ""))
        out["pc_r_mod0"].append(len(out["pc_r_mods"]))
        out["pc_r_modn"].append(len(rule.modules))
        out["pc_r_mods"].extend(str(m) for m in rule.modules)
        # sorted, because `choose`'s random branch sorts the POOL and reads
        # `rule.weights` by name - a dict has no order to preserve here, and
        # sorting it makes the table itself reproducible
        weights = dict(rule.weights or {})
        out["pc_r_w0"].append(len(out["pc_r_wkey"]))
        out["pc_r_wn"].append(len(weights))
        for key in sorted(weights):
            out["pc_r_wkey"].append(str(key))
            out["pc_r_wval"].append(float(weights[key]))
        cond = dict(rule.cond or {})
        kind, num, text, items = _cond_columns(cond)
        out["pc_r_ckind"].append(kind)
        out["pc_r_csubj"].append(str(cond.get("subject", "")))
        out["pc_r_cop"].append(str(cond.get("op", "eq")) if cond else "")
        out["pc_r_cnum"].append(num)
        out["pc_r_cstr"].append(text)
        out["pc_r_cl0"].append(len(out["pc_r_clist"]))
        out["pc_r_cln"].append(len(items))
        for ikind, inum, itext in items:
            out["pc_r_clkind"].append(ikind)
            out["pc_r_clnum"].append(inum)
            out["pc_r_clist"].append(itext)
    # ⚠️ WHICH SPLINE PRIM ATTRIBUTES `pc_sections` MUST HARVEST.  VEX cannot
    # enumerate attribute names - there is no `primattribs()` on 22.0.398,
    # four spellings probed - so the names have to be named.  Every `attr:`
    # subject in the payload, and nothing else: `place._prim_attrs` harvests
    # every non-`pc_` prim attribute, but the only thing that ever READS the
    # bag is an `attr:<name>` condition, so the shorter list answers exactly
    # the same questions.
    names = sorted(set(
        str(r.cond["subject"])[5:] for r in rules
        if r.cond and str(r.cond.get("subject", "")).startswith("attr:")))
    # ⚠️ AND FILTERED BY `place._prim_attrs`' OWN RULE, because `pc_sections`
    # harvests by NAME and `primattribtype` finds anything.  The reference
    # skips P/N/Cd/uv/v and every `pc_` name outside `ROW_ATTRS_2D`; without
    # the same filter here, `attr:pc_total` - the raw curve length this
    # network's own `pc_arclength` writes onto the prim - answered 20.0
    # natively and None in the reference, and a conditional on it built 12
    # gates against the reference's 10 panels.  Every internal the DECOMPOSE
    # box publishes (`pc_total`, `pc_closed`, `pc_nclean`, `pc_iscurve`,
    # `pc_curve_id_r`) was a live subject on one side and dead on the other.
    # Filtering HERE rather than in the VEX is what stops the two lists
    # drifting: this is the only place that decides what VEX may see.
    names = [n for n in names
             if n not in _place._ATTR_SKIP
             and not (n.startswith("pc_") and n not in _place.ROW_ATTRS_2D)]
    out["_attr_names"] = names
    for name in RULE_FLOAT_COLUMNS:
        out[name] = [_exact(v) for v in out[name]]
    return out


_ARRAY_DEFAULTS = dict(
    [(name, "") for name in ("_attr_names", "pc_k_name", "pc_k_variant",
                             "pc_k_zmode", "pc_k_roles", "pc_r_slot",
                             "pc_r_select", "pc_r_scope", "pc_r_yclass",
                             "pc_r_axis", "pc_r_vexpr", "pc_r_mods",
                             "pc_r_wkey", "pc_r_csubj", "pc_r_cop",
                             "pc_r_cstr", "pc_r_clist")]
    + [(name, "") for name in KIT_FLOAT_COLUMNS + RULE_FLOAT_COLUMNS])


def write_tables(geo, tables):
    """The flat arrays onto `geo` as DETAIL attributes, typed by their first
    element - or by `_ARRAY_DEFAULTS` when the table is empty, because an
    empty kit and an empty rule list are both legal and VEX still has to bind
    the name.
    """
    for name in sorted(tables):
        values = tables[name]
        if values:
            sample = values[0]
        else:
            sample = _ARRAY_DEFAULTS.get(name, 0.0)
        if isinstance(sample, str):
            kind = hou.attribData.String
        elif isinstance(sample, float):
            kind = hou.attribData.Float
        else:
            kind = hou.attribData.Int
        geo.addArrayAttrib(hou.attribType.Global, name, kind)
        geo.setGlobalAttribValue(name, list(values))


def cook_kit(node):
    """The KIT STREAM the native PLACE branch copies from.

    ⚠️ IT ADDS NO PYTHON TO THE COOK PATH - it MOVES some.  `kit_geometry`
    already ran inside `kernel` on every cook where input 2 is unwired (6's
    standalone-usability floor: a curve and nothing else must make a fence),
    and 15.6 lists `kit.box_mesh` as unported and unscheduled.  Putting it on
    a node of its own is what lets the VEX branch reach the same kit the
    reference uses, and it makes the fallback VISIBLE in the graph instead of
    buried six thousand lines into a Python SOP.  D154 replaces the body with
    native `box` SOPs; the node is where it will happen.
    """
    geo = node.geometry()
    wired = _input_geo(node, 0)
    if wired is not None and wired.intrinsicValue("primitivecount"):
        return                                   # the artist's kit, untouched
    geo.clear()
    try:
        geo.merge(kit_geometry(node))
    except Exception as exc:                     # warn-never-block
        node.addWarning("kit: %s" % exc)


def cook_config(node):
    """The CONFIG stream: one point carrying `pc_cfg`. Never raises."""
    geo = node.geometry()
    geo.clear()
    cfg, style, kit = {}, None, None
    try:
        cfg, style, kit = config_resolved(node)
    except Exception as exc:                                # warn-never-block
        node.addWarning("config: %s" % exc)
    geo.addAttrib(hou.attribType.Global, "pc_cfg", {})
    geo.setGlobalAttribValue("pc_cfg", cfg)
    tables = kit_table(kit)
    tables.update(rule_table(style))
    write_tables(geo, tables)
    geo.createPoint()
    return cfg


# 13.3.4's frame inputs, as point attributes. The names are the ones
# `pc_frames.vfl` binds; changing one means changing both.
FRAME_POINT_ATTRS = (
    ("pc_s0r", 0.0), ("pc_s1r", 0.0),
    # D170 - THE RESIDUAL HALVES OF THE TWO SPANS. `hou.Geometry.addAttrib`
    # has no precision argument (probed), so every float attribute a Python
    # SOP creates is float32, and at 20 km that quantises an arclength to
    # 1.95 mm - measured, 9.765e-4 m worst against the reference, ten times
    # the suite's own 1e-4 m tolerance. R2 forbids this network being worse
    # at world scale than the Python it replaces, so the metre crosses the
    # boundary as a float32 head plus a float32 residual and `pc_frames`
    # adds the pair back in 64-bit VEX (~6e-11 m at 20 km). 13.9 N2 deletes
    # both the moment the span is solved inside that wrangle.
    ("pc_s0r_lo", 0.0), ("pc_s1r_lo", 0.0),
    ("pc_proto_len", 1.0),
    ("pc_proto_ax", 0.0), ("pc_basey", 0.0), ("pc_yscale", 1.0),
    ("pc_has_basey", 0), ("pc_curveprim", -1), ("pc_frame_valid", 0),
)


def _f32(x):
    """`x` as float32 storage will hold it - the head of the split above."""
    return struct.unpack("f", struct.pack("f", float(x)))[0]


def curve_prim_index(curve_geo):
    """{curve id: primitive number} - THE ids `place.read_curves` produced.

    ⚠️ IT USED TO BE A SECOND COPY OF THE RULE, and that is exactly how it
    went wrong.  This function re-implemented D29/D64's id resolution and
    applied NONE of `read_curves`' filters, so `native_id_parity` compared one
    copy of the rule against another and both could disagree with the curve
    set the builder actually planned on - measured, a 3-point line whose
    middle point carried `pc_marker` produced 0 curves in the reference and a
    full entry here.  There is one rule now and it lives in `read_curves`.
    """
    if curve_geo is None:
        return {}
    out = {}
    for curve in _place.read_curves(curve_geo)[0]:
        out.setdefault(str(curve.curve_id), curve.prim_number)
    return out


def plan_geometry(geo, report, curve_geo):
    """`plan_points` PLUS 13.3.4's frame inputs - the PLAN stage's output.

    ⚠️ SCAFFOLDING (13.9 N2).  The plan itself is still the reference's; this
    only lifts what the reference already computed onto real points so the
    NATIVE `pc_frames` downstream has something to read.  When the VEX solve
    lands, this node is deleted and `pc_plan_read` writes these same names.

    `pc_frame_valid` is the honest half: a piece whose `Path` is a filleted,
    slope-flattened or conformed polyline is NOT on the input spline, so the
    native arclength table cannot answer for it and the flag says 0 rather
    than the wrangle answering about a curve that does not exist.
    """
    _place.plan_points(geo, report)
    rows = report.get("frames") or []
    for name, default in FRAME_POINT_ATTRS:
        if geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, default)
    if geo.findPointAttrib("pc_upref") is None:
        geo.addAttrib(hou.attribType.Point, "pc_upref", (0.0, 1.0, 0.0))
    if not rows or geo.intrinsicValue("pointcount") != len(rows):
        return geo
    index = curve_prim_index(curve_geo)
    prim = [index.get(str(r["curve_id"]), -1) for r in rows]
    valid = [1 if (r["raw"] and not r["anchored"] and prim[i] >= 0) else 0
             for i, r in enumerate(rows)]
    geo.setPointIntAttribValues("pc_curveprim", prim)
    geo.setPointIntAttribValues("pc_frame_valid", valid)
    geo.setPointIntAttribValues(
        "pc_has_basey", [0 if r["base_y"] is None else 1 for r in rows])
    for name, key in (("pc_s0r", "s0r"), ("pc_s1r", "s1r")):
        head = [_f32(r[key]) for r in rows]
        geo.setPointFloatAttribValues(name, head)
        geo.setPointFloatAttribValues(
            name + "_lo", [r[key] - head[i] for i, r in enumerate(rows)])
    geo.setPointFloatAttribValues("pc_proto_len", [r["proto_len"] for r in rows])
    geo.setPointFloatAttribValues("pc_proto_ax", [r["proto_ax"] for r in rows])
    geo.setPointFloatAttribValues(
        "pc_basey", [0.0 if r["base_y"] is None else r["base_y"] for r in rows])
    geo.setPointFloatAttribValues("pc_yscale", [r["yscale"] for r in rows])
    up = []
    for r in rows:
        up.extend(r["up_ref"])
    geo.setPointFloatAttribValues("pc_upref", up)
    return geo


def cook_plan_bridge(node):
    """The PLAN stage's output, until 13.9 N2's VEX solve replaces it."""
    geo = node.geometry()
    geo.clear()
    curve_geo = _input_geo(node, 0)
    if curve_geo is None or not curve_geo.intrinsicValue("primitivecount"):
        node.addWarning("no spline on input 1 - nothing to plan")
        return
    parms = parm_owner(node)
    kit_geo = kit_geometry(node, parms)
    style, warns = _style.read(_input_geo(node, 2), kit=_kit.read(kit_geo)[0])
    for warn in warns:
        node.addWarning(warn)
    if style is None:
        style = style_from_parms(parms)
        kit_geo = _padded(kit_geo, parms.evalParm("padding")
                          if parms.parm("padding") else 0.0)
    _out, report = _place.build(curve_geo, kit_geo, style,
                                params=style.params,
                                surface_geo=_input_geo(node, 3),
                                report_frames=True)
    plan_geometry(geo, report, curve_geo)
    # D160, warn-never-block applied to a stage that used to go SILENT. The
    # blast below this node deletes every piece the native frame cannot
    # answer for, and on any non-zero Corner Rounding that is ALL of them:
    # measured, an L-spline at fillet 2.0 cooked the Frames stage to 0 points
    # with no error and no warning while the Output stage built 121 prims.
    valid = geo.pointIntAttribValues("pc_frame_valid")
    dropped = sum(1 for v in valid if not v)
    if dropped:
        node.addWarning(
            "%d of %d pieces ride a filleted, slope-flattened or conformed "
            "path, which is not the input spline - the native Frames stage "
            "cannot answer for them and drops them (D160). The Output stage "
            "is unaffected." % (dropped, len(valid)))
    return report
