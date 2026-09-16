"""Create `pf_fix_foldover` - find and repair inverted (folded-over) faces.

    hython devScripts/create_pf_fix_foldover_hda.py

A bevel or offset whose loops cross leaves a few faces whose normal points
the wrong way and a small fold in the silhouette. PolyBevel's Stop Loops
does not prevent it and PolyDoctor's majority-winding fix does not see it
(the fold makes the patch non-manifold there). Measured on a floor tile,
2026-09-16: 5 inverted faces, all repaired by this chain.

    pf_fix_foldover                    1 input:
      detect    [attribwrangle/prim]   `pf_foldover` group: a face whose
                                       normal opposes the average of every
                                       face sharing a point with it. Also
                                       `_c`, the face centre, for collapse.
      reverse   [reverse]              Fix = Reverse Winding: flips those
                                       faces. Facing only; the fold stays.
      collapse  [attribwrangle/point]  Fix = Collapse and Fuse: every point
                                       of an inverted face goes to the mean
                                       centre of the inverted faces it is
                                       on, so crossed loops meet at a point
      fuse      [fuse::2.0]            ...and the collapsed faces go. No
                                       Clean: its 0.001 degeneracy tolerance
                                       deleted GOOD bevel faces and opened
                                       24 edges on the tile.
      fix       [switch]               None / Reverse / Collapse
      cleanup   [attribdelete]         `_*` off the output (conventions 2)
      OUT

Blind spot, by construction: a face that is MEANT to oppose its neighbours
(the inside of a very sharp crease) is flagged too. Detect Only shows the
group before anything moves.
"""

import os
import re

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
HDA_PATH = os.path.join(_POLYFACTORY, "otls", "pf_fix_foldover.hda").replace("\\", "/")

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

NAME = "pf_fix_foldover"
TAB_LABEL = "PF Fix Foldover"
OUTPUT_LABEL = "Repaired"
ICON = "SOP_polydoctor"
GROUP = "pf_foldover"

DETECT_VEX = r'''// pf_fix_foldover - an inverted face: its normal opposes the average
// normal of every face sharing a point with it.
vector n = prim_normal(0, @primnum, 0.5, 0.5);
vector acc = 0;
foreach (int pt; primpoints(0, @primnum))
    foreach (int pr; pointprims(0, pt))
        if (pr != @primnum) acc += prim_normal(0, pr, 0.5, 0.5);
int folded = (length(acc) > 0 && dot(n, normalize(acc)) < 0);
setprimgroup(0, "%s", @primnum, folded);
vector c = 0;
foreach (int pt; primpoints(0, @primnum)) c += point(0, "P", pt);
v@_c = c / len(primpoints(0, @primnum));
''' % GROUP

COLLAPSE_VEX = r'''// pf_fix_foldover - every point of an inverted face goes to the mean
// centre of the inverted faces it belongs to, so crossed loops meet at
// one point. The fuse after this removes the collapsed faces.
vector t = 0; int k = 0;
foreach (int pr; pointprims(0, @ptnum))
    if (inprimgroup(0, "%s", pr)) { t += prim(0, "_c", pr); k++; }
if (k > 0) @P = t / k;
''' % GROUP


def _float(name, label, default, lo, hi, help_):
    t = hou.FloatParmTemplate(name, label, 1, (default,), min=lo, max=hi,
                              min_is_strict=True, max_is_strict=False)
    t.setHelp(help_)
    return t


if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_" + NAME)
subnet = build_geo.createNode("subnet", NAME)
subnet.createNode("null", "OUT").setDisplayFlag(True)

hda_node = subnet.createDigitalAsset(
    name=NAME, hda_file_name=HDA_PATH, description=TAB_LABEL,
    min_num_inputs=1, max_num_inputs=1, version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setMinNumInputs(1)
defn.setMaxNumInputs(1)
defn.setIcon(ICON)

net = hda_node
out_null = net.node("OUT")
src = net.indirectInputs()[0]


def _place(node, x, y, comment=None):
    node.setPosition(hou.Vector2(x, y))
    if comment:
        node.setComment(comment)
        node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return node


detect = _place(net.createNode("attribwrangle", "detect"), 0, 6,
                "A face whose normal opposes its neighbours' average.")
detect.setInput(0, src)
detect.parm("class").set("primitive")
detect.parm("snippet").set(DETECT_VEX)

reverse = _place(net.createNode("reverse", "reverse"), 2, 5,
                 "Facing only: the fold stays in the silhouette.")
reverse.setInput(0, detect)
reverse.parm("group").set(GROUP)

collapse = _place(net.createNode("attribwrangle", "collapse"), 4, 5,
                  "Crossed loops meet at one point.")
collapse.setInput(0, detect)
collapse.parm("class").set("point")
collapse.parm("snippet").set(COLLAPSE_VEX)

fuse = _place(net.createNode("fuse::2.0", "fuse"), 4, 4,
              "Merges the collapsed points and drops the degenerate\n"
              "faces. NOT a Clean: its degeneracy tolerance deleted\n"
              "good bevel faces and opened the mesh.")
fuse.setInput(0, collapse)
fuse.parm("tol3d").setExpression('ch("../snapdist")')

fix = _place(net.createNode("switch", "fix"), 0, 3)
fix.setInput(0, detect)
fix.setInput(1, reverse)
fix.setInput(2, fuse)
fix.parm("input").setExpression('ch("../fix")')

cleanup = _place(net.createNode("attribdelete", "cleanup"), 0, 2,
                 "`_c` is internal (conventions.md 2).")
cleanup.setInput(0, fix)
cleanup.parm("doprimdel").set(1)
cleanup.parm("primdel").set("_*")

out_null.setInput(0, cleanup)
out_null.setPosition(hou.Vector2(0, 1))

ptg = hou.ParmTemplateGroup()
_fix = hou.MenuParmTemplate("fix", "Fix", ("none", "reverse", "collapse"),
                            menu_labels=("Detect Only", "Reverse Winding",
                                         "Collapse and Fuse"),
                            default_value=2)
_fix.setHelp("Detect Only marks the inverted faces in group pf_foldover and "
             "moves nothing. Reverse Winding flips their facing but leaves the "
             "fold in the silhouette. Collapse and Fuse pulls each inverted "
             "face to a point so the crossed loops meet there - the fold is "
             "gone and the mesh stays closed.")
ptg.append(_fix)
ptg.append(_float("snapdist", "Snap Distance", 1e-5, 0.0, 0.01,
                  "How close the collapsed points must be to merge. Keep it "
                  "tiny: it only has to catch points that were moved onto "
                  "each other."))
defn.setParmTemplateGroup(ptg)
defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

defn = hou.hda.definitionsInFile(HDA_PATH)[0]
ds = defn.sections()["DialogScript"].contents()
if "outputlabel" in ds:
    ds = re.sub(r'outputlabel\t1\t"[^"]*"', 'outputlabel\t1\t"%s"' % OUTPUT_LABEL, ds)
else:
    ds = ds.replace('  parm {', '  outputlabel\t1\t"%s"\n  parm {' % OUTPUT_LABEL, 1)
defn.addSection("DialogScript", ds)
defn.addSection("Tools.shelf", TOOLS_SHELF)

hda_node.destroy()
build_geo.destroy()

back = hou.hda.definitionsInFile(HDA_PATH)[0]
saved = back.sections()["DialogScript"].contents()
assert "Poly Factory/Modeling" in back.sections()["Tools.shelf"].contents()
assert back.icon() == ICON and back.description() == TAB_LABEL
assert 'outputlabel\t1\t"%s"' % OUTPUT_LABEL in saved
for _p in ("fix", "snapdist"):
    assert re.search(r'name\s+"%s"' % _p, saved), _p
print("wrote " + HDA_PATH)
