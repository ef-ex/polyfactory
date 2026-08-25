"""Create `pf_polychain_slice` - polyChain 7.7's kit on-ramp, as a SOP HDA.

    hython devScripts/create_pf_polychain_slice_hda.py

Model ONE good facade chunk (or one fence run) as plain geometry; get a valid
3.2 kit that `pf_polychain` consumes directly. That is the whole product, and
the parameter page is written so an artist gets it with nothing set but a wire
(`artist_ui.md` 6's standalone-usability floor).

    pf_polychain_slice                     6 nodes:
      IN_CHUNK  IN_GUIDES                    2 named nulls, one per input
      sl_kit      [python]  the 3.2 kit      the two answers, side by side, so
      sl_cells    [python]  where the cuts   the SWITCH cooks only the one
                            landed           being looked at
      show        [switch]
      OUT         [null]

Two Python SOPs and no more, and both are UI/parameter marshalling plus one
call - 13.6's sanctioned case, and the only geometry verb the tool reaches is
the `clip` the kernel already reaches (D131). The decisions live in
`polychain/slicer.py` (`hou`-free, unit-tested under plain python) and the
geometry in `polychain/kit.py`, which owns the 3.2 format.

⚠️ 5.1's TWO ACCEPTANCE CRITERIA ARE MET HERE AND VERIFIED BY READING THE
SAVED FILE BACK, because 5.1's own finding is that the build script is what
got them wrong:
  a) a `Tools.shelf` section putting the node in TAB > Poly Factory/Modeling,
     copied from the shape `pf::pf_kitbash` ships, plus an icon that is not
     `SOP_subnet`;
  b) labelled inputs and output.
⚠️ AND THERE IS NO HOM API FOR INPUT LABELS ON 22.0.398 - PROBED, not assumed:
`hou.HDADefinition` exposes `setIcon`/`setDescription` and nothing for input
labels, and `hou.SopNodeType` has no `inputLabels`. They live in the
`DialogScript` section as `inputlabel N "..."` lines, so the section is
patched after `setParmTemplateGroup` regenerates it. 5.1 says "not by
hand-editing the dialog script"; on this build there is no other door, and
the check reads the labels back off the saved `.hda`.
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
                        "pf_polychain_slice.hda").replace("\\", "/")

from polyfactory.polychain import Z_MODES                        # noqa: E402
from polyfactory.polychain.kit import NOTES_ATTR                 # noqa: E402

# The house TAB-menu declaration, read off the shipped `pf_kitbash.hda`
# rather than written from memory (5.1's table names the submenu).
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

INPUT_LABELS = ("Chunk", "Guides (optional)")
OUTPUT_LABEL = "Kit"

BODY = """import os
import sys

import hou

_root = hou.text.expandString("$POLYFACTORY")
if _root:
    _pkg = _root.replace(chr(92), "/").rstrip("/") + "/scripts/python"
    if os.path.isdir(_pkg) and _pkg not in sys.path:
        sys.path.append(_pkg)

from polyfactory.polychain import kit as _kit

_kit.sop_slice(hou.pwd(), %r)
"""


def python_sop(net, name, mode, comment):
    node = net.createNode("python", name)
    node.parm("python").set(BODY % mode)
    node.setComment(comment)
    node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return node


if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_pf_polychain_slice")
subnet = build_geo.createNode("subnet", "pf_polychain_slice")
subnet.createNode("null", "OUT").setDisplayFlag(True)

hda_node = subnet.createDigitalAsset(
    name="pf_polychain_slice",
    hda_file_name=HDA_PATH,
    description="polyChain Slice",
    min_num_inputs=0,
    max_num_inputs=2,
    version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setMinNumInputs(0)
defn.setMaxNumInputs(2)
# 5.1a - anything but the default subnet icon. `SOP_clip` is what the tool
# does, and `pf::fast_clip` already uses it, so the house has the precedent.
defn.setIcon("SOP_clip")

net = hda_node
out_null = net.node("OUT")

ins = []
for i, name in enumerate(("IN_CHUNK", "IN_GUIDES")):
    node = net.createNode("null", name)
    node.setInput(0, net.indirectInputs()[i])
    node.setPosition(hou.Vector2(2.0 * i, 0.0))
    ins.append(node)

sl_kit = python_sop(
    net, "sl_kit", "kit",
    "7.7 - the deliverable. `slicer.plan` decides the bands and the cell\n"
    "roles off the chunk's bounding box; `kit.slice_cells` cuts each cell\n"
    "with the same `clip` verb 4.3 uses (D131); `kit.slice_kit` packs them\n"
    "and writes the 3.2 manifest. Wire the output straight into\n"
    "pf_polychain's Kit input.")
sl_cells = python_sop(
    net, "sl_cells", "cells",
    "The same cut, left WHERE IT LANDED and unpacked, one `pc_cell` per\n"
    "prim. This is the view that answers the question the parameters ask -\n"
    "did the bay width and the guides put the planes where I meant - and it\n"
    "is a separate branch rather than a stage so the switch cooks one of\n"
    "the two, never both.")
for i, node in enumerate((sl_kit, sl_cells)):
    node.setInput(0, ins[0])
    node.setInput(1, ins[1])
    node.setPosition(hou.Vector2(2.0 * i, -3.0))

show = net.createNode("switch", "show")
show.setInput(0, sl_kit)
show.setInput(1, sl_cells)
show.parm("input").setExpression('ch("../show")')
show.setPosition(hou.Vector2(0.0, -5.0))
show.setComment("`Show` on the parameter page. Input 0 is the kit, input 1\n"
                "is where the cuts landed.")
show.setGenericFlag(hou.nodeFlag.DisplayComment, True)

out_null.setInput(0, show)
out_null.setPosition(hou.Vector2(0.0, -7.0))
out_null.setDisplayFlag(True)
out_null.setRenderFlag(True)

box = net.createNetworkBox("slice")
box.setComment("7.7 - one chunk in, a 3.2 kit out")
for node in (ins[0], ins[1], sl_kit, sl_cells, show, out_null):
    box.addNode(node)
box.fitAroundContents()

net.layoutChildren()


# --- the parameter page (5 / artist_ui.md 6, two disclosure levels) ---------

def _float(name, label, default, lo, hi, help_text):
    """⚠️ `units` IS A PARMTAG AND NOTHING ELSE SETS IT. "(m)" in a label is a
    caption; the tag is what makes Houdini offer the unit menu and convert a
    value an artist types as `12in`. Every float here is a length in metres
    (house rule), and all three shipped without the tag."""
    t = hou.FloatParmTemplate(name, label, 1, default_value=(default,),
                              min=lo, max=hi, min_is_strict=True)
    t.setHelp(help_text)
    t.setTags({"units": "m"})
    return t


def _toggle(name, label, default, help_text):
    t = hou.ToggleParmTemplate(name, label, default_value=default)
    t.setHelp(help_text)
    return t


def _menu(name, label, items, labels, default, help_text):
    t = hou.StringParmTemplate(name, label, 1, default_value=(default,),
                               menu_items=items, menu_labels=labels)
    t.setHelp(help_text)
    return t


def _imenu(name, label, labels, default, help_text):
    """An INT menu, because `show` drives a Switch SOP and `ch()` on a string
    parm does not give the switch an index."""
    t = hou.IntParmTemplate(name, label, 1, default_value=(default,),
                            menu_items=[str(i) for i in range(len(labels))],
                            menu_labels=list(labels))
    t.setHelp(help_text)
    return t


ptg = hou.ParmTemplateGroup()

ptg.append(_imenu(
    "show", "Show", ("Kit", "Where The Cuts Land"), 0,
    "Kit: the finished modules, packed, ready for pf_polychain's Kit input. "
    "Where The Cuts Land: the same pieces left in place and unpacked, so you "
    "can see whether the bay width and the guides put the planes where you "
    "meant them."))

# ⚠️ THE ONLY SURFACE THE TOOL'S WARNINGS CAN REACH. A Python SOP inside an
# HDA cannot warn on the HDA - probed every way on 22.0.398, and `kit`'s
# `write_notes` carries the finding - so the lines ride out on the geometry as
# a detail string and this parm reads them back. Read-only by `disable_when`,
# because the node writes it and the artist does not.
_notes = hou.StringParmTemplate(
    "notes", "Notes", 1,
    default_value=('`details("./OUT", "%s")`' % NOTES_ATTR,))
_notes.setHelp(
    "What this node has to say about the chunk it was given: an input that is "
    "not wired, a bay too wide for the chunk, a guide it could not use, a "
    "cell with no geometry in it. 'ok' means it had nothing to report. This "
    "node never refuses to build - it builds and tells you here.")
_notes.setDisableWhen("{ show >= 0 }")
ptg.append(_notes)

ptg.append(_float(
    "bay", "Bay Width (m)", 0.0, 0.0, 20.0,
    "How wide one repeating piece is, in metres - the width of a bay on a "
    "facade, of a panel on a fence. Leave at 0 and the chunk is split into "
    "three equal bands, which turns any plain chunk into a start / middle / "
    "end kit with nothing else set."))

ptg.append(_float(
    "storey", "Storey Height (m)", 0.0, 0.0, 20.0,
    "How tall one repeating row is, in metres - a storey on a facade. 0 "
    "splits the chunk into three equal bands the same way Bay Width does."))

ptg.append(_toggle(
    "sides", "Cut Side Pieces", True,
    "On: the first and last bay become the start and end pieces, so a run "
    "closes properly at both ends. Off: every bay is a repeating piece and "
    "the kit has no caps."))

ptg.append(_toggle(
    "capstop", "Cut Top And Bottom Pieces", True,
    "On: the bottom and top rows become the ground-floor and cornice "
    "pieces. Off: the chunk is one row tall - which is what a fence or a "
    "wall run wants."))

ptg.append(_toggle(
    "jigsaw", "Fit Pieces To The Bay", True,
    "RailClone's Adjust To Default Segment: every repeating piece is cut to "
    "exactly one bay by one storey, so the pieces mate like a jigsaw when "
    "pf_polychain lays them out. Turn it off only to keep bands of uneven "
    "size, and expect gaps."))

adv = hou.FolderParmTemplate("adv", "Advanced",
                             folder_type=hou.folderType.Tabs)

adv.addParmTemplate(hou.StringParmTemplate(
    "kitid", "Kit Name", 1, default_value=("sliced_kit",),
    help="The kitId written into the kit's manifest, so a build can say "
         "which kit it came from."))

adv.addParmTemplate(_float(
    "humanscale", "Human Scale Reference (m)", 1.8, 0.1, 3.0,
    "The height of a person for this kit's scale, in metres - the manifest "
    "field every polyfactory kit must carry so two kits can be told apart "
    "when one was modelled in centimetres."))

adv.addParmTemplate(_menu(
    "deform", "Piece Behaviour", ("auto", "rigid", "bend", "slice"),
    ("Auto (ends rigid, middles bend)", "Rigid - never bends",
     "Bends along the run", "Bends and may be sliced"), "auto",
    "Whether a piece follows a curving run. Auto keeps the end and corner "
    "pieces rigid, so they stay instanced and mate cleanly at a joint, and "
    "lets the repeating middles bend - which is what the shipped fence kit "
    "does."))

adv.addParmTemplate(_menu(
    "zmode", "Upright Behaviour", Z_MODES,
    ("Follow the run", "Stay plumb", "Sit flat"), "adaptive",
    "What a piece does on a slope. Written onto every module; a style "
    "payload can still override it per slot."))

ptg.append(adv)
defn.setParmTemplateGroup(ptg)
defn.setExtraFileOption("polychain/source", __file__.replace("\\", "/"))

_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

# --- 5.1's two metadata criteria, written onto the SAVED definition --------
# `setParmTemplateGroup` regenerates `DialogScript`, so the labels are
# patched afterwards and the file is read back to prove it took.
defn = hou.hda.definitionsInFile(HDA_PATH)[0]
ds = defn.sections()["DialogScript"].contents()
for i, label in enumerate(INPUT_LABELS):
    ds = re.sub(r'inputlabel\t%d\t"[^"]*"' % (i + 1),
                'inputlabel\t%d\t"%s"' % (i + 1, label), ds)
if "outputlabel" in ds:
    ds = re.sub(r'outputlabel\t1\t"[^"]*"',
                'outputlabel\t1\t"%s"' % OUTPUT_LABEL, ds)
else:
    ds = ds.replace('inputlabel\t%d\t"%s"' % (len(INPUT_LABELS),
                                              INPUT_LABELS[-1]),
                    'inputlabel\t%d\t"%s"\n    outputlabel\t1\t"%s"'
                    % (len(INPUT_LABELS), INPUT_LABELS[-1], OUTPUT_LABEL))
defn.addSection("DialogScript", ds)
defn.addSection("Tools.shelf", TOOLS_SHELF)

hda_node.destroy()
build_geo.destroy()

# Read the SAVED file back - 5.1's "verify by INSPECTING THE BUILT ASSET".
back = hou.hda.definitionsInFile(HDA_PATH)[0]
saved = back.sections()["DialogScript"].contents()
assert "Poly Factory/Modeling" in \
    back.sections()["Tools.shelf"].contents(), "TAB submenu missing"
assert back.icon() == "SOP_clip", "icon is %r" % back.icon()
for i, label in enumerate(INPUT_LABELS):
    assert 'inputlabel\t%d\t"%s"' % (i + 1, label) in saved, \
        "input %d unlabelled" % (i + 1)
assert 'outputlabel\t1\t"%s"' % OUTPUT_LABEL in saved, "output unlabelled"
for _p in ("bay", "storey", "humanscale"):
    assert back.parmTemplateGroup().find(_p).tags().get("units") == "m", \
        "%s carries no units tag" % _p

print("[pf_polychain_slice] created: " + HDA_PATH)
