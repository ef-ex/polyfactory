"""Create `pf_polychain` - polyChain's artist-facing SOP HDA (spec 5).

    hython devScripts/create_pf_polychain_hda.py

Inner network (deliberately three nodes - the work is in the package, not in
the asset, so a fix is a commit rather than a re-saved binary):

    input 1 spline(s) ┐
    input 2 kit       ├─> kernel (Python SOP) ─> OUT (null)
    input 3 style     │
    input 4 surface   ┘

The Python SOP does nothing but bootstrap the package and call
`polyfactory.polychain.hda.cook(node)`.

THE PARAMETER PAGE IS artist_ui.md 6 APPLIED, AND IT IS LAW HERE:
  * two disclosure levels, no more - one main page and one Advanced folder;
  * every parm carries a range, a unit in its label and a help string;
  * every parm names a DECISION an art director could say out loud;
  * the defaults build a good fence on the starter kit with nothing wired but
    a curve (6's standalone-usability floor);
  * `display` is on the MAIN page, because an interactive proxy LOD is an
    acceptance criterion and not polish (artist_ui rule 7).

Internal parm names match `polychain.Params` field names on purpose (D80) -
the label is the artist's face, the name is the kernel's.
"""

import os

import hou

POLYFACTORY = os.environ.get("POLYFACTORY",
                             "F:/projects/polyfactory/polyfactory")
HDA_PATH = os.path.join(POLYFACTORY, "otls",
                        "pf_polychain.hda").replace("\\", "/")

if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

# --- the Python SOP's whole body --------------------------------------------
# The bootstrap is warn-never-block wiring, not logic: a session that already
# has the package on its path skips it entirely.
KERNEL_CODE = '''import os
import sys

import hou

_root = hou.text.expandString("$POLYFACTORY")
if _root:
    _pkg = _root.replace(chr(92), "/").rstrip("/") + "/scripts/python"
    if os.path.isdir(_pkg) and _pkg not in sys.path:
        sys.path.append(_pkg)

from polyfactory.polychain import hda as _hda

_hda.cook(hou.pwd())
'''

# --- build context ----------------------------------------------------------

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_pf_polychain")
subnet = build_geo.createNode("subnet", "pf_polychain")

kernel = subnet.createNode("python", "kernel")
out_null = subnet.createNode("null", "OUT")
out_null.setInput(0, kernel)
out_null.setDisplayFlag(True)
out_null.setRenderFlag(True)

hda_node = subnet.createDigitalAsset(
    name="pf_polychain",
    hda_file_name=HDA_PATH,
    description="polyChain",
    min_num_inputs=0,
    max_num_inputs=4,
    version="1.0")
hda_node.allowEditingOfContents()

inner = dict((n.name(), n) for n in hda_node.children())
for i in range(4):
    inner["kernel"].setInput(i, hda_node.indirectInputs()[i])
inner["OUT"].setInput(0, inner["kernel"])
inner["kernel"].parm("python").set(KERNEL_CODE)

defn = hda_node.type().definition()
defn.setMinNumInputs(0)
defn.setMaxNumInputs(4)


# --- parameter page ---------------------------------------------------------

def _menu(name, label, items, default, help_text):
    """A STRING menu, never an ordinal one: the value the kernel reads is the
    token itself, so a menu reordered tomorrow cannot silently change what an
    existing node means."""
    tokens = [i[0] for i in items]
    labels = [i[1] for i in items]
    parm = hou.StringParmTemplate(name, label, 1,
                                  default_value=(default,),
                                  menu_items=tokens, menu_labels=labels)
    parm.setHelp(help_text)
    return parm


def _float(name, label, default, lo, hi, help_text):
    parm = hou.FloatParmTemplate(name, label, 1, default_value=(default,),
                                 min=lo, max=hi,
                                 min_is_strict=False, max_is_strict=False)
    parm.setHelp(help_text)
    return parm


def _int(name, label, default, lo, hi, help_text):
    parm = hou.IntParmTemplate(name, label, 1, default_value=(default,),
                               min=lo, max=hi,
                               min_is_strict=False, max_is_strict=False)
    parm.setHelp(help_text)
    return parm


def _toggle(name, label, default, help_text):
    parm = hou.ToggleParmTemplate(name, label, default_value=default)
    parm.setHelp(help_text)
    return parm


def _slot(name, label, default, help_text):
    """A module list with the kit's own manifest as its menu (5).

    `StringReplace` rather than a fixed menu: the value is a SPACE-SEPARATED
    list (D76), so the menu offers what the kit has and the field still
    accepts two names typed side by side.
    """
    parm = hou.StringParmTemplate(
        name, label, 1, default_value=(default,),
        menu_type=hou.menuType.StringReplace,
        item_generator_script_language=hou.scriptLanguage.Python,
        item_generator_script=(
            "from polyfactory.polychain import hda as _h\n"
            "return _h.slot_menu(kwargs['node'])\n"))
    parm.setHelp(help_text)
    return parm


ptg = hou.ParmTemplateGroup()

# ---- MAIN PAGE: the decisions, in the order they are made -------------------

ptg.append(hou.StringParmTemplate(
    "kitfile", "Kit File", 1, default_value=("",),
    string_type=hou.stringParmType.FileReference,
    file_type=hou.fileType.Geometry,
    help=("Kit geometry (3.2) to dress the spline with. Leave EMPTY to use "
          "input 2, and leave input 2 unwired to use the built-in starter "
          "fence - post, panel, corner post and gate. Metric metres.")))

ptg.append(_slot("slot_default", "Repeating Pieces", "post panel",
                 "The modules that fill the run, by kit module name or by "
                 "role. Two or more names make a repeating pattern - "
                 "'post panel' is a picket fence. From the kit manifest."))
ptg.append(_menu("variety", "Piece Order",
                 [("first", "Always the first"),
                  ("sequence", "In turn"),
                  ("random", "Random (uses Seed)")],
                 "sequence",
                 "How the repeating pieces are chosen. 'In turn' walks the "
                 "list in order; 'Random' picks by the kit's own weights and "
                 "is repeatable for a given Seed. Conditional rules are a "
                 "style-payload feature (input 3), not a parm."))
ptg.append(_slot("slot_start", "Piece at the Start", "post",
                 "Module reserved for the first piece of every section. "
                 "Empty means the run just starts with a repeating piece."))
ptg.append(_slot("slot_end", "Piece at the End", "post",
                 "Module reserved for the last piece of every section. "
                 "Empty means the run just ends with a repeating piece."))
ptg.append(_slot("slot_corner", "Piece at Corners", "corner_post",
                 "Module placed where the spline turns by more than the "
                 "Corner Angle. Empty means the run bends through the corner "
                 "with no special piece."))
ptg.append(_slot("slot_evenly", "Evenly Spaced Piece", "",
                 "Module placed at a fixed interval along the run (see "
                 "Evenly Spacing) regardless of the fill - lamps on a "
                 "railing, bollards on a kerb."))

ptg.append(_menu("fill", "Fit Method",
                 [("adaptive", "Adaptive - whole pieces, evenly stretched"),
                  ("tile", "Tile - whole pieces, remainder cut"),
                  ("scale", "Scale - stretch to fit exactly"),
                  ("count", "Count - a fixed number of pieces")],
                 "adaptive",
                 "How the pieces are fitted to each section. ADAPTIVE is the "
                 "default because it never cuts a piece: it uses whole "
                 "modules and stretches them all by the same small amount. "
                 "Tile cuts the leftover (only where the kit allows it)."))
ptg.append(_float("padding", "Gap Between Pieces", 0.0, -0.5, 2.0,
                  "Metres of space added between neighbouring pieces, on top "
                  "of whatever the kit's own padding says. NEGATIVE overlaps "
                  "them, which is how lapped boards are built. The gap moves "
                  "the neighbours; it never stretches the piece."))
ptg.append(_float("evenly_spacing", "Evenly Spacing", 0.0, 0.0, 50.0,
                  "Metres between 'Evenly Spaced Piece' anchors. 0 turns the "
                  "evenly pass off (or set Evenly Count in Advanced "
                  "instead)."))

ptg.append(_menu("corner_mode", "Corner Treatment",
                 [("bend", "Bend - the piece follows the corner"),
                  ("miter", "Miter - two pieces cut on the bisector")],
                 "bend",
                 "What happens where the spline turns. BEND deforms the "
                 "piece around the vertex, which suits rails and hedges; "
                 "MITER cuts a corner module on the angle bisector, which "
                 "suits kerbs, walls and anything with a hard edge."))
ptg.append(_float("fillet_radius", "Corner Rounding", 0.0, 0.0, 10.0,
                  "Metres of radius to round the PATH by before any piece is "
                  "placed. 0 leaves the corner sharp. A radius wider than "
                  "the legs allow is clamped and says so."))

ptg.append(_menu("zmode", "Upright Behaviour",
                 [("", "From the kit"),
                  ("adaptive", "Follow the slope (banks)"),
                  ("vertical", "Stay plumb (pickets)"),
                  ("stepped", "Sit flat (steps)")],
                 "",
                 "How a piece meets a slope. FROM THE KIT lets each module "
                 "decide, which is what a mixed kit wants: the starter "
                 "fence's pickets stay plumb while its posts sit flat. Set "
                 "one here to override every module at once."))
ptg.append(_int("seed", "Random Seed", 3, 0, 1000,
                "Changes every random choice. The same seed and the same "
                "inputs always build the same fence, in this session and in "
                "any other."))

ptg.append(_menu("display", "Display",
                 [("full", "Full geometry"),
                  ("proxy", "Proxy boxes (fast)"),
                  ("plan", "Plan points only")],
                 "full",
                 "PROXY BOXES swaps every module for a box at its nominal "
                 "size and keeps the whole run packed - the same plan, the "
                 "same corners, a fraction of the cost. Use it while "
                 "dragging a slider over a long run. PLAN POINTS shows the "
                 "fit solve alone: one point per piece, carrying what it was "
                 "given."))

# ---- ADVANCED: one folder, no folders inside it (artist_ui rule 4) ---------

adv = hou.FolderParmTemplate("advanced", "Advanced",
                             folder_type=hou.folderType.Collapsible)

adv.addParmTemplate(_float(
    "adaptive_pct", "Adaptive Threshold (%)", 50.0, 0.0, 100.0,
    "When Adaptive is deciding whether one more piece fits: the percentage "
    "of a whole piece the leftover must reach before it adds one. 50 rounds "
    "to nearest, 100 never adds one, 0 always does."))
adv.addParmTemplate(_int(
    "count", "Piece Count", 1, 1, 500,
    "How many pieces per section in COUNT mode. Ignored in every other fit "
    "method."))
adv.addParmTemplate(_int(
    "evenly_count", "Evenly Count", 0, 0, 200,
    "Number of evenly spaced anchors per section, as an alternative to "
    "Evenly Spacing. 0 uses the spacing instead."))
adv.addParmTemplate(_menu(
    "justify", "Evenly Justify",
    [("start", "From the start"), ("center", "Centred"),
     ("end", "From the end")], "center",
    "Where the leftover goes when the evenly anchors do not divide the "
    "section exactly."))
adv.addParmTemplate(_float(
    "adjust_to_end", "Adjust to End", 0.0, 0.0, 5.0,
    "Metres. When the trailing leftover is at or under this, the evenly "
    "spacing is stretched so the last anchor lands exactly on the section "
    "end. 0 never adjusts."))

adv.addParmTemplate(_menu(
    "corner_displacement", "Corner Displacement",
    [("reset", "Reset - cut where the fit ended"),
     ("extend", "Extend - push the run to the corner"),
     ("symmetric", "Symmetric - centre the last piece")], "reset",
    "What the ordinary pieces next to a MITERED corner do. Reset leaves each "
    "one where the fit put it and cuts it on the plane; Extend pushes the "
    "run out to the plane; Symmetric centres the last piece on it."))
adv.addParmTemplate(_float(
    "corner_offset_pct", "Corner Offset (%)", 0.0, -100.0, 100.0,
    "Percent of the corner module's length to slide BOTH copies along their "
    "own legs. Positive pulls them back from the vertex, negative pushes "
    "them through it. The cut plane does not move, so the seam stays shut."))
adv.addParmTemplate(_float(
    "corner_angle_deg", "Corner Angle", 30.0, 0.0, 180.0,
    "Degrees of TURN (deviation from straight) at which a spline vertex "
    "counts as a corner. Below it the run just bends through."))
adv.addParmTemplate(_float(
    "min_included_angle_deg", "Narrow Corner Angle", 15.0, 0.0, 90.0,
    "Degrees of INCLUDED angle between the two legs below which a corner is "
    "too sharp to miter. It falls back to a bend and says so."))
adv.addParmTemplate(_int(
    "fillet_segments", "Corner Rounding Segments", 4, 2, 64,
    "How many segments the Corner Rounding arc is built from. Rounded up to "
    "an even number so the arc always has a midpoint vertex."))

adv.addParmTemplate(_toggle(
    "fix_slope", "Measure Widths Horizontally", False,
    "ON measures every piece's width on the horizontal, so a fence keeps its "
    "post spacing seen from above as it climbs. OFF measures along the path "
    "itself, which is longer on a slope."))
adv.addParmTemplate(hou.FloatParmTemplate(
    "conform_axis", "Conform Direction", 3, default_value=(0.0, -1.0, 0.0),
    min=-1.0, max=1.0,
    help=("The direction pieces are dropped in to find the surface on input "
          "4. Straight down by default; point it sideways for a run "
          "conformed to a wall.")))
adv.addParmTemplate(_toggle(
    "conform_tilt", "Tilt to Surface", False,
    "ON rolls each piece onto the surface's own normal, so a rail follows "
    "the camber of a road. OFF keeps it upright. Individual kit modules can "
    "veto this."))

adv.addParmTemplate(_float(
    "bend_tol", "Bend Tolerance", 0.01, 0.0, 1.0,
    "Metres of error allowed before a piece is unpacked and bent. This is "
    "also the instancing control: a piece stays a lightweight instance while "
    "following the curve would move it less than this, so a gently curving "
    "road of 10 000 panels stays instanced. 0 bends everything that curves "
    "at all."))
adv.addParmTemplate(_toggle(
    "show_warnings", "Colour Warnings", False,
    "Turns every element that carries a warning red. Warnings never stop the "
    "build - this is how you find them."))
adv.addParmTemplate(hou.StringParmTemplate(
    "style_id", "Style Name", 1, default_value=("pf_polychain",),
    help=("Stamped on every element as `pc_style` and mixed into the random "
          "seed. Give two polyChains different names when they share a kit "
          "and must not repeat the same pattern.")))

ptg.append(adv)
defn.setParmTemplateGroup(ptg)

defn.setExtraFileOption("polychain/source", __file__.replace("\\", "/"))
defn.save(HDA_PATH, template_node=hda_node)

hda_node.destroy()
build_geo.destroy()

print("[pf_polychain] created: " + HDA_PATH)
