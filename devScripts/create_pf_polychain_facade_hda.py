"""Create `pf_polychain_facade` - polyChain 7's 2D array, as a SOP HDA (P2-9).

    hython devScripts/create_pf_polychain_facade_hda.py

Until this existed there was no HDA on the 2D path at all (7.6 says so in its
own words), so every 2D setting was a keyword on `facade.build_many` and 7.6's
clip PORT, its cull-policy menu and D289's warning route had nowhere to live.

    pf_polychain_facade                    7 nodes:
      IN_FOOTPRINT IN_KIT IN_STYLE           5 named nulls, one per D127 port
      IN_SURFACE   IN_AUX
      fc_build   [python]  the whole build
      OUT        [null]

ONE Python SOP, and 13.6's sanctioned case is what it is: `hda.cook_facade` is
parameter marshalling plus ONE `place.build` call reached through
`facade.build_many`, which is the same kernel `pf_polychain` runs. There is no
native 2D chain to switch between, so 13.7 rule 1's "drop a display flag on
any stage" is answered by the `Stage` menu inside the cook rather than by a
branch per stage: three branches would be three builds of the same geometry.

⚠️ 5.1's TWO ACCEPTANCE CRITERIA, VERIFIED BY READING THE SAVED FILE BACK -
5.1's own finding is that the build script is what got them wrong:
  a) a `Tools.shelf` section putting the node in TAB > Poly Factory/Modeling,
     plus an icon that is not `SOP_subnet`;
  b) labelled inputs AND a labelled output.
⚠️ AND THERE IS NO HOM API FOR INPUT LABELS ON 22.0.398 (probed for
`pf_polychain_slice`, unchanged here): they live in the `DialogScript` section
as `inputlabel N "..."` lines, which `setParmTemplateGroup` regenerates, so
the section is patched afterwards and read back off the saved `.hda`.
"""

import os
import re
import sys

import hou

POLYFACTORY = os.environ.get("POLYFACTORY",
                             "F:/projects/polyfactory/polyfactory")
_PKG = os.path.join(POLYFACTORY, "scripts", "python").replace("\\", "/")
if os.path.isdir(_PKG) and _PKG not in sys.path:
    sys.path.insert(0, _PKG)
HDA_PATH = os.path.join(POLYFACTORY, "otls",
                        "pf_polychain_facade.hda").replace("\\", "/")

from polyfactory.polychain.array2d import CLIP_WORDS             # noqa: E402
from polyfactory.polychain.hda import (FACADE_DISABLE,           # noqa: E402
                                       FACADE_STAGES)

TOOLS_SHELF = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="viewer">
      <contextNetType>SOP</contextNetType>
    </toolMenuContext>
    <toolMenuContext name="network">
      <contextOpType>$HDA_TABLE_AND_NAME</contextOpType>
    </toolMenuContext>
    <toolSubmenu>Poly Factory/Modeling</toolSubmenu>
    <script scriptType="python"><![CDATA[import soptoolutils

soptoolutils.genericTool(kwargs, '$HDA_NAME')]]></script>
  </tool>
</shelfDocument>
"""

# 5.1b in artist words, and D127's port table is what they say.
INPUT_LABELS = ("Footprint / Wall", "Kit", "Style Payload (optional)",
                "Surface (optional)", "Clip / Aux Splines (optional)")
OUTPUT_LABEL = "Facade"
ICON = "SOP_copytopoints"

BODY = """import os
import sys

import hou

_root = hou.text.expandString("$POLYFACTORY")
if _root:
    _pkg = _root.replace(chr(92), "/").rstrip("/") + "/scripts/python"
    if os.path.isdir(_pkg) and _pkg not in sys.path:
        sys.path.append(_pkg)

from polyfactory.polychain import hda as _hda

_hda.cook_facade(hou.pwd())
"""


if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_pf_polychain_facade")
subnet = build_geo.createNode("subnet", "pf_polychain_facade")
subnet.createNode("null", "OUT").setDisplayFlag(True)

hda_node = subnet.createDigitalAsset(
    name="pf_polychain_facade",
    hda_file_name=HDA_PATH,
    description="polyChain Facade",
    min_num_inputs=0,
    max_num_inputs=5,
    version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setMinNumInputs(0)
defn.setMaxNumInputs(5)
defn.setIcon(ICON)

net = hda_node
out_null = net.node("OUT")

PORTS = ("IN_FOOTPRINT", "IN_KIT", "IN_STYLE", "IN_SURFACE", "IN_AUX")
for i, name in enumerate(PORTS):
    node = net.createNode("null", name)
    node.setInput(0, net.indirectInputs()[i])
    node.setPosition(hou.Vector2(2.5 * i, 0.0))

# ⚠️ D316 - A PYTHON SOP HAS FOUR INPUTS ON 22.0.398 (probed: `maxNumInputs`
# is 4, the same ceiling D306 hit on a wrangle) AND D127 FROZE FIVE PORTS.
# The two that are both SPLINES share one stream, discriminated by the
# `pc_purpose` attribute D127 chose for input 5 in the first place - and this
# wrangle is what makes an UNTAGGED aux spline mean `clip`, so an artist who
# wires a boundary into input 5 and tags nothing gets the boundary they drew.
aux_tag = net.createNode("attribwrangle", "aux_tag")
aux_tag.parm("class").set(1)                    # primitive
aux_tag.parm("snippet").set(
    'if (s@pc_purpose == "") s@pc_purpose = "clip";')
aux_tag.parm("vex_precision").set("64")
aux_tag.setInput(0, net.node("IN_AUX"))
aux_tag.setPosition(hou.Vector2(10.0, -1.5))
aux_tag.setComment("D316 - input 5's discriminator, defaulted. `clip` /\n"
                   "`exclude` are the two the array reads; `yspline` is\n"
                   "refused by name (D128 is half-built and half of D128\n"
                   "is not D128).")
aux_tag.setGenericFlag(hou.nodeFlag.DisplayComment, True)

in_merge = net.createNode("merge", "in_splines")
in_merge.setInput(0, net.node("IN_FOOTPRINT"))
in_merge.setInput(1, aux_tag)
in_merge.setPosition(hou.Vector2(0.0, -2.0))

build = net.createNode("python", "fc_build")
build.parm("python").set(BODY)
build.setComment(
    "7 - the whole 2D array. `hda.cook_facade` reads the five ports\n"
    "(D127), resolves the two faces (a payload on input 3 wins WHOLE -\n"
    "2.1 / D77), and calls `facade.build_many` ONCE for every row of\n"
    "every footprint - D115's one-call rule, which is what keeps\n"
    "`ray_executions_per_build` at 1 on a district.\n"
    "\n"
    "It reads its parms off the PARENT: `hou.pwd()` here is this SOP and\n"
    "the page is one level up.")
build.setGenericFlag(hou.nodeFlag.DisplayComment, True)
build.setInput(0, in_merge)
for i in range(1, 4):
    build.setInput(i, net.node(PORTS[i]))
build.setPosition(hou.Vector2(0.0, -3.5))

out_null.setInput(0, build)
out_null.setPosition(hou.Vector2(0.0, -6.0))
out_null.setDisplayFlag(True)
out_null.setRenderFlag(True)

box = net.createNetworkBox("facade")
box.setComment("7 - a footprint and a height in, a facade out")
for node in net.children():
    box.addNode(node)
box.fitAroundContents()
net.layoutChildren()


# --- the parameter page (5 / artist_ui.md 6, two disclosure levels) ---------

def _menu(name, label, items, default, help_text):
    """A STRING menu, never an ordinal one: the value the kernel reads is the
    token itself, so a menu reordered tomorrow cannot silently change what an
    existing node means."""
    parm = hou.StringParmTemplate(name, label, 1, default_value=(default,),
                                  menu_items=[i[0] for i in items],
                                  menu_labels=[i[1] for i in items])
    parm.setHelp(help_text)
    return parm


def _float(name, label, default, lo, hi, help_text, units=None):
    """⚠️ `units` IS A PARMTAG AND NOTHING ELSE SETS IT. "(m)" in a label is a
    caption; the tag is what makes Houdini offer the unit menu and convert a
    value an artist types as `12in`."""
    parm = hou.FloatParmTemplate(name, label, 1, default_value=(default,),
                                 min=lo, max=hi,
                                 min_is_strict=False, max_is_strict=False)
    parm.setHelp(help_text)
    if units:
        parm.setTags({"units": units})
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
    """A module list with the FACADE kit's own manifest as its menu.

    `StringToggle`, not `StringReplace`: the value is a space-separated list
    (D76), so picking a second name must APPEND rather than overwrite.
    """
    parm = hou.StringParmTemplate(
        name, label, 1, default_value=(default,),
        menu_type=hou.menuType.StringToggle,
        item_generator_script_language=hou.scriptLanguage.Python,
        item_generator_script=(
            "from polyfactory.polychain import hda as _h\n"
            "return _h.slot_menu(kwargs['node'], _h.facade_kit_geometry)\n"))
    parm.setHelp(help_text)
    return parm


ptg = hou.ParmTemplateGroup()

# ---- MAIN PAGE: the decisions, in the order an artist makes them -----------

# ⚠️ THE ONLY SURFACE THIS TOOL'S WARNINGS CAN REACH, and it is D289's route.
# Re-probed for this node on 22.0.398: an open clip loop plus a bowtie raised
# THREE warnings on the inner Python SOP and `warnings()` on the HDA instance
# came back EMPTY. So the lines ride out on the geometry as a detail string
# and this parm reads them back. Read-only by `disable_when`, because the node
# writes it and the artist does not.
_notes = hou.StringParmTemplate(
    "notes", "Notes", 1,
    default_value=('`details("./OUT", "pc_facade_notes")`',))
_notes.setHelp(
    "What this node has to say about what it was given: a boundary loop that "
    "does not close or crosses itself, a cell the kit has no piece for and "
    "what it used instead, a storey that would not fit. 'ok' means it had "
    "nothing to report. This node never refuses to build - it builds and "
    "tells you here.")
ptg.append(_notes)

ptg.append(hou.StringParmTemplate(
    "kitfile", "Kit File", 1, default_value=("",),
    string_type=hou.stringParmType.FileReference,
    file_type=hou.fileType.Geometry,
    help=("Kit geometry (3.2) to dress the shape with. Leave EMPTY to use "
          "input 2, and leave input 2 unwired to use the built-in starter "
          "facade - a bay, a corner pier, a shopfront, a cornice and their "
          "pier pieces. Metric metres.")))

ptg.append(_menu(
    "shape", "What To Build",
    [("footprint", "Footprint + Height - a building"),
     ("area", "Boundary Shape - define and trim")], "footprint",
    "FOOTPRINT + HEIGHT wraps the closed shape on input 1 and stacks storeys "
    "up to Building Height - one array for the whole building, corners and "
    "all. BOUNDARY SHAPE takes the closed loops on input 5 (or on input 1 if "
    "input 5 is unwired) and both DEFINES the array from them and TRIMS it "
    "to them - flat roofs, floor plates, cladding fields, a window array in "
    "one aperture. A loop nested inside another is a hole."))

_height = _float(
    "height", "Building Height (m)", 13.0, 1.0, 200.0,
    "How tall the building is, in metres, measured from the footprint. The "
    "storeys are fitted into it: the ground floor and the cornice take their "
    "own heights and whole storeys fill the rest, stretched a little rather "
    "than cut. Ignored in Boundary Shape, where the shape gives the height.",
    units="m")
ptg.append(_height)
ptg.append(_slot(
    "slot_default", "Repeating Bay", "",
    "The module that fills each row, by kit module name. LEAVE IT EMPTY and "
    "the kit decides per cell - the ground floor gets whatever the kit tags "
    "as a ground-floor bay, the top row gets its cornice, the corners get "
    "their piers. Name a module here to use that one everywhere instead."))
ptg.append(_slot(
    "slot_corner", "Piece at Corners", "",
    "The column placed where the footprint turns by more than the Corner "
    "Angle. Empty lets the kit's own corner pieces answer per row, which is "
    "what a facade wants: a pier base on the ground floor, a pier cap under "
    "the cornice. Clear the kit's corner role instead to have no column."))

# ⚠️ THE THREE Y DEFAULTS NAME 7.2's ROLES, NOT THE BUILT-IN KIT'S MODULES
# (P2-9a F1). They used to read `shopfront` / `bay` / `cornice`, which are the
# starter kit's own module names - so the first thing an artist does, wiring
# their OWN kit into input 2, resolved all three against nothing and collapsed
# a four-storey building into thirteen 1 m stand-in bands. A role is the KIT
# CONTRACT (7.2) and every conforming kit answers it whatever it calls its
# pieces; measured on a kit renamed `mine_*`, the role defaults rebuild the
# same 264-piece facade the starter kit gives. Empty is still no special row -
# the Y solve reads a HEIGHT here (D132) and cannot invent one, which is why
# these three are not blank the way the X slots are.
ptg.append(_slot(
    "yslot_start", "Ground Floor", "default_start",
    "What sets the HEIGHT of the bottom row - a shopfront, a plinth, a "
    "podium. Leave it at the kit ROLE and any kit answers; name a module to "
    "pin it to one piece. Either way the storey stack is solved on heights "
    "and which piece fills each bay of that row is still the kit's decision. "
    "Empty means no special bottom row."))
ptg.append(_slot(
    "yslot_default", "Repeating Storey", "default",
    "What sets the height of every ordinary storey. The stack fits whole "
    "storeys into the height left over and scales them slightly to fill it "
    "exactly - a storey is never sliced."))
ptg.append(_slot(
    "yslot_end", "Cornice", "default_end",
    "What sets the height of the top row - a cornice, a parapet, an eaves "
    "band. Empty means the building just stops at the last storey."))

ptg.append(_menu(
    "fill", "Bay Fit",
    [("adaptive", "Adaptive - whole bays, evenly stretched"),
     ("tile", "Tile - whole bays, remainder cut"),
     ("scale", "Scale - stretch to fit exactly"),
     ("count", "Count - a fixed number of bays")], "adaptive",
    "How bays are fitted along each facade. ADAPTIVE is the default because "
    "architecture never slices a window: it uses whole bays and stretches "
    "them all by the same small amount."))
ptg.append(_menu(
    "y_fill", "Storey Fit",
    [("adaptive", "Adaptive - whole storeys, evenly stretched"),
     ("tile", "Tile - whole storeys, remainder scaled"),
     ("scale", "Scale - stretch to fit exactly"),
     ("count", "Count - a fixed number of storeys")], "adaptive",
    "The same choice on the vertical. A storey is never cut whichever you "
    "pick - the band is the truth and the module is scaled into it - so this "
    "decides how many storeys fit, not what happens to the leftover."))
ptg.append(_menu(
    "y_mode", "Storey Alignment",
    [("free", "Free - every storey fits its own length"),
     ("aligned", "Aligned - every storey takes the ground floor's bays")],
    "free",
    "What happens when storeys differ in length - a setback, a taper. FREE "
    "lets each storey solve its own bays. ALIGNED makes every storey take the "
    "ground floor's bay count per facade, so the bay joints line up all the "
    "way up. On a plain building the two are the same answer. A storey that "
    "physically cannot hold the count solves free and says so."))

ptg.append(_menu(
    "corner_mode", "Corner Treatment",
    [("miter", "Miter - two pieces cut on the bisector"),
     ("bend", "Bend - the piece follows the corner")], "miter",
    "What happens where the footprint turns. MITER cuts the corner module on "
    "the angle bisector, which is what a wall with a hard edge wants and is "
    "the default here for that reason. BEND deforms the bay around the "
    "vertex, which suits a curved or chamfered facade."))

# ⚠️ FOUR ENTRIES, AND IT USED TO BE THREE FOR A REASON THAT WAS FALSE
# (P2-9a F3). The comment here claimed `CLIP_POLICIES.get(clip_mode,
# CLIP_REMOVE)` resolved `none` to REMOVE, so offering it would have deleted
# every straddling piece. It does not: `array2d.row_spans` short-circuits on
# `mode == "none"` BEFORE any boundary test, and measured through this node it
# builds 284 prims straight across the hole against `remove`'s 76. So the
# payload face accepted a policy the parm face could not express - 2.1's two
# faces disagreeing - and the menu is built from `CLIP_WORDS`, the same
# vocabulary `payload_2d` validates against, so they cannot drift again.
_CLIP_LABELS = {"remove": "Remove - drop any piece it touches",
                "preserve": "Preserve - keep it whole, overhanging",
                "slice": "Slice - cut it to the boundary",
                "none": "Ignore - build the full rows, trim nothing"}
_clip = _menu(
    "clip_mode", "Boundary Treatment",
    [(k, _CLIP_LABELS[k]) for k in ("remove", "preserve", "slice", "none")
     if k in CLIP_WORDS["mode"]], "remove",
    "In Boundary Shape, what the boundary does to a piece that straddles it. "
    "REMOVE leaves a clean gap; SLICE cuts the piece and caps the hole, and "
    "falls back to Remove on a module the kit says cannot be cut; PRESERVE "
    "lets it overhang; IGNORE trims nothing at all, so the rows run the full "
    "width of the shape's extents and straight through any hole - it is the "
    "one to reach for when the boundary is only there to place and orient the "
    "array. A kit module carrying its own policy overrides this.")
ptg.append(_clip)

ptg.append(_int(
    "seed", "Random Seed", 3, 0, 1000,
    "Changes every random choice. The same seed and the same inputs always "
    "build the same facade, in this session and in any other."))

ptg.append(_menu(
    "display", "Display",
    [("full", "Full geometry"),
     ("proxy", "Proxy boxes (fast)"),
     ("plan", "Plan points only")], "full",
    "PROXY BOXES swaps every module for a box at its nominal size and keeps "
    "the whole building packed - the same rows, the same corners, a fraction "
    "of the cost. Use it while dragging a slider on a district. PLAN POINTS "
    "shows the fit solve alone: one point per piece, carrying what it was "
    "given."))

# ---- ADVANCED: one folder, no folders inside it (artist_ui rule 4) ---------

adv = hou.FolderParmTemplate("advanced", "Advanced",
                             folder_type=hou.folderType.Collapsible)

adv.addParmTemplate(_menu(
    "variety", "Bay Order",
    [("first", "Always the first"), ("sequence", "In turn"),
     ("random", "Random (uses Seed)")], "first",
    "How Repeating Bay is chosen when it names more than one module. Only "
    "reaches the field bays; the kit's own roles still decide the ground "
    "floor, the cornice and the corners."))
adv.addParmTemplate(_slot(
    "slot_start", "Piece at the Start", "",
    "Module reserved for the first bay of every facade. A closed footprint "
    "has no start - its runs end at corners - so this only reaches an OPEN "
    "wall run on input 1."))
adv.addParmTemplate(_slot(
    "slot_end", "Piece at the End", "",
    "Module reserved for the last bay of every facade. Like Piece at the "
    "Start, it only reaches an open wall run."))

# D117's own parm, and this is the item the finish queue lists beside the node.
adv.addParmTemplate(_menu(
    "extend", "Corners Extend Into",
    [("x", "The corner column runs through the band"),
     ("y", "The band runs past the corner column")], "x",
    "Which way a cell degrades when the kit has no piece for the crossing - a "
    "corner column meeting the cornice, for instance. THE COLUMN RUNS "
    "THROUGH keeps its corner-ness and drops the band, so the column cuts the "
    "cornice; THE BAND RUNS PAST keeps the band and drops the corner-ness, so "
    "the cornice returns continuous. When the kit HAS the crossing piece this "
    "changes nothing."))

adv.addParmTemplate(_float(
    "adaptive_pct", "Bay Adaptive Threshold (%)", 50.0, 0.0, 100.0,
    "When Adaptive is deciding whether one more bay fits: the percentage of a "
    "whole bay the leftover must reach before it adds one. 50 rounds to "
    "nearest, 100 never adds one, 0 always does."))
adv.addParmTemplate(_float(
    "y_adaptive_pct", "Storey Adaptive Threshold (%)", 50.0, 0.0, 100.0,
    "The same threshold on the vertical - whether a part storey of leftover "
    "height becomes one more whole storey or is absorbed by stretching the "
    "ones already there."))

_expand = _float(
    "expand", "Grow The Boundary (m)", 0.0, -5.0, 20.0,
    "Metres the Boundary Shape's extents are grown by before the rows are "
    "laid out, so the array covers the boundary instead of stopping a "
    "fraction short of it at the perimeter. It grows the AREA the rows span, "
    "not the trim - pieces are still cut or dropped at the real boundary.",
    units="m")
adv.addParmTemplate(_expand)
_align = _menu(
    "auto_align", "Array Direction",
    [("to_spline", "Along the boundary's first edge"),
     ("x_xy", "Horizontal")], "to_spline",
    "Which way the rows run inside a Boundary Shape. ALONG THE FIRST EDGE "
    "follows the shape the artist drew; HORIZONTAL keeps the rows level "
    "whatever the shape's own rotation is, which is what a tilted wall "
    "panel wants.")
adv.addParmTemplate(_align)

adv.addParmTemplate(_float(
    "corner_angle_deg", "Corner Angle (deg)", 30.0, 0.0, 180.0,
    "Degrees of TURN (deviation from straight) at which a footprint vertex "
    "counts as a corner and gets a corner column. Below it the facade just "
    "bends through."))
adv.addParmTemplate(_float(
    "min_included_angle_deg", "Narrow Corner Angle (deg)", 15.0, 0.0, 90.0,
    "Degrees of INCLUDED angle between two facades below which the corner is "
    "too sharp to miter. It falls back to a bend and says so."))
adv.addParmTemplate(_menu(
    "corner_displacement", "Corner Displacement",
    [("reset", "Reset - cut where the fit ended"),
     ("extend", "Extend - push the run to the corner"),
     ("symmetric", "Symmetric - centre the last bay")], "reset",
    "What the ordinary bays next to a MITERED corner do. Reset leaves each "
    "one where the fit put it and cuts it on the plane; Extend pushes the "
    "run out to the plane; Symmetric centres the last bay on it."))
adv.addParmTemplate(_float(
    "corner_offset_pct", "Corner Offset (%)", 0.0, -100.0, 100.0,
    "Percent of the corner module's length to slide BOTH copies along their "
    "own facades. Positive pulls them back from the vertex, negative pushes "
    "them through it. The cut plane does not move, so the seam stays shut."))

adv.addParmTemplate(hou.FloatParmTemplate(
    "conform_axis", "Conform Direction", 3, default_value=(0.0, -1.0, 0.0),
    min=-1.0, max=1.0,
    help=("The direction pieces are dropped in to find the surface on input "
          "4. Straight down by default, which is what sits a building on "
          "terrain.")))
adv.addParmTemplate(_toggle(
    "conform_tilt", "Tilt to Surface", False,
    "ON rolls each piece onto the surface's own normal. OFF keeps it "
    "upright, which is what a building wants. Individual kit modules can "
    "veto this."))

adv.addParmTemplate(_float(
    "bend_tol", "Bend Tolerance (m)", 0.01, 0.0, 1.0,
    "Metres of error allowed before a piece is unpacked and bent. This is "
    "also the instancing control: a piece stays a lightweight instance while "
    "following the shape would move it less than this, so a district of "
    "buildings stays instanced. 0 bends everything that curves at all.",
    units="m"))
adv.addParmTemplate(_toggle(
    "show_warnings", "Colour Warnings", False,
    "Turns every element that carries a warning red. Warnings never stop the "
    "build - this is how you find them."))
adv.addParmTemplate(hou.StringParmTemplate(
    "style_id", "Style Name", 1, default_value=("pf_polychain_facade",),
    help=("Stamped on every element as `pc_style` and mixed into the random "
          "seed. Give two buildings different names when they share a kit "
          "and must not repeat the same pattern.")))

# Not a second `display`: `display` is an art-direction control that changes
# what is BUILT (D81/D82), this changes which stage of the build you are
# LOOKING at, and every value but the default shows an intermediate that was
# never meant to be rendered. Same split, same words, as `pf_polychain`.
adv.addParmTemplate(_menu(
    "stage", "Stage (debug)", list(FACADE_STAGES), FACADE_STAGES[0][0],
    "Which stage of the build to output. ROWS is the one worth knowing: it "
    "shows the row curves the kernel is actually handed - one polyline per "
    "storey per footprint - which is where a wrong storey count or a "
    "footprint read the wrong way round is visible immediately. INPUT is the "
    "loops the ports yielded after validation dropped what it dropped."))

ptg.append(adv)

# artist_ui 6's RAMP, applied from `hda.FACADE_DISABLE` in ONE place (P2-9a
# F5). Scattering `setDisableWhen` across the page is how five mode-conditional
# parms - the two adaptive thresholds and the three MITER-only corner controls -
# shipped live and turnable in a mode where they mean nothing, with the runner
# checking the four it happened to name. The declaration is the tool's now and
# the gate check compares it to the SAVED asset in both directions.
for _name, _cond in sorted(FACADE_DISABLE.items()):
    _tpl = ptg.find(_name)
    assert _tpl is not None, "FACADE_DISABLE names %r, the page does not" % _name
    _tpl.setConditional(hou.parmCondType.DisableWhen, _cond)
    ptg.replace(_name, _tpl)

defn.setParmTemplateGroup(ptg)

defn.setExtraFileOption("polychain/source", __file__.replace("\\", "/"))

_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

# --- 5.1's two metadata criteria, written onto the SAVED definition --------
# ⚠️ AND THE GENERATED SCRIPT ONLY EVER CARRIES FOUR `inputlabel` LINES,
# whatever `setMaxNumInputs` says - measured on this asset, which declares
# five. So the fifth is INSERTED rather than substituted, and the output label
# after it.
defn = hou.hda.definitionsInFile(HDA_PATH)[0]
ds = defn.sections()["DialogScript"].contents()
for i, label in enumerate(INPUT_LABELS):
    line = 'inputlabel\t%d\t"%s"' % (i + 1, label)
    if re.search(r'inputlabel\t%d\t"[^"]*"' % (i + 1), ds):
        ds = re.sub(r'inputlabel\t%d\t"[^"]*"' % (i + 1), line, ds)
    else:
        prev = 'inputlabel\t%d\t"%s"' % (i, INPUT_LABELS[i - 1])
        ds = ds.replace(prev, "%s\n    %s" % (prev, line))
out_line = 'outputlabel\t1\t"%s"' % OUTPUT_LABEL
if "outputlabel" in ds:
    ds = re.sub(r'outputlabel\t1\t"[^"]*"', out_line, ds)
else:
    last = 'inputlabel\t%d\t"%s"' % (len(INPUT_LABELS), INPUT_LABELS[-1])
    ds = ds.replace(last, "%s\n    %s" % (last, out_line))
defn.addSection("DialogScript", ds)
defn.addSection("Tools.shelf", TOOLS_SHELF)

hda_node.destroy()
build_geo.destroy()

# Read the SAVED file back - 5.1's "verify by INSPECTING THE BUILT ASSET".
back = hou.hda.definitionsInFile(HDA_PATH)[0]
saved = back.sections()["DialogScript"].contents()
assert "Poly Factory/Modeling" in \
    back.sections()["Tools.shelf"].contents(), "TAB submenu missing"
assert back.icon() == ICON, "icon is %r" % back.icon()
for i, label in enumerate(INPUT_LABELS):
    assert 'inputlabel\t%d\t"%s"' % (i + 1, label) in saved, \
        "input %d unlabelled" % (i + 1)
assert 'outputlabel\t1\t"%s"' % OUTPUT_LABEL in saved, "output unlabelled"

print("[pf_polychain_facade] created: " + HDA_PATH)
