"""Create `pf_stylized_rock` - a chip-off-the-block stylized rock, as a SOP HDA.

    hython devScripts/create_pf_stylized_rock_hda.py

The old "rocks by Clip SOP" trick (Stoyan Dimitrov 2019, Poly Doorway 2022 -
neither downloadable / licensed for commercial work, see ideas/rocks.md §6):
take a blocky base, and in a feedback loop slice a random chip off it with a
Clip whose plane sits just inside the surface. Big cuts first for the
silhouette, small chips second for the edges. Every face stays FLAT, which
is the whole look - no noise anywhere.

    pf_stylized_rock                   optional input: your own base shape
      base_box/base_sphere/base_tube   the built-in bases; `base_pick` menu
      base_sw    [switch]              the input when one is wired, else that
      fit        [matchsize]           normalise: unit cube, centred on the
                                       origin, so every depth below is a
                                       fraction of the rock's size
      cuts_*     [block_begin/end]     Big Cuts loop - see _chip_loop()
      chips_*    [block_begin/end]     Small Chips loop
      floor      [clip::2.0] + switch  Flat Bottom, keep above a plane at
                                       ymin + fraction * height
      bevel      [polybevel::3.0] + switch   softens every edge; bypassed at
                                       width 0 (PROBED on pf_ring: polybevel
                                       at offset 0 still doubles every point)
      place      [matchsize]           canonical output: Size along each axis,
                                       centred in XZ, standing on y = 0
      cleanup    [attribdelete]        `_*` off all four classes
                                       (conventions §2)
      cleanup_grp [groupdelete]        and `_*` groups (conventions §5)
      norm       [normal]              vertex normals + cusp angle - the flat
                                       faces SHADE flat
      OUT        [null]

One chip iteration is: a detail wrangle that picks a uniform random direction
`d` (sample_direction_uniform on rand(seed, iteration)), projects every point
onto it for the extent `m`, and puts the plane at `m - depth`; then a Clip
keeping BELOW that plane with Fill on, so the hole is capped. The depth is
Depth * fit01(rand, 1 - Depth Variation, 1). A cut is shortened or skipped so
the rock stays at least a quarter of its unit size thick along the cut
direction, so no setting collapses it.

Reference-checked on 22.0.442 rather than recalled:
  * `clip` is `clip::2.0`; its plane is origin + direction + `dist` along the
    normal, `clipop` below keeps the negative side, `dofill` caps the hole.
    Detail attributes are read into its parms with `detail("../plane", ..)`.
  * A wrangle inside a feedback block can take the metadata block on input 1
    and read `iteration` from it.
  * inside an HDA, `strlen(opinputpath("..", 0)) > 0` is 1 iff something is
    wired to the asset's first input (PROBED, wired and unwired).
  * 12 random clips on a box stay watertight: 0 duplicate and 0 unmatched
    directed edges (control test before this was written).
"""

import os
import re

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
HDA_PATH = os.path.join(_POLYFACTORY, "otls", "pf_stylized_rock.hda").replace("\\", "/")
NAME = "pf_stylized_rock"
TAB_LABEL = "PF Stylized Rock"
OUTPUT_LABEL = "Rock"
ICON = "SOP_clip"

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

HELP = """= PF Stylized Rock =

#icon: SOP/clip

\"\"\"A stylized, flat-faced rock: random chips sliced off a blocky base.\"\"\"

Feed it nothing and pick a base shape, or wire in your own blockout. Big Cuts
shape the silhouette, Small Chips break up the edges, every face stays flat.
Depths are fractions of the rock's size; the result is Size big, centred in
XZ and standing on y = 0.
"""

BASES = ("box", "sphere", "tube")
BASE_LABELS = ("Box", "Sphere", "Cylinder")

# One chip: pick a direction, find the rock's extent along it, put the plane
# just inside. OFFSET separates the two passes' random streams; the
# depth/variation parms are named per pass.
PLANE_VEX = r'''// pf_stylized_rock - one chip plane per iteration, read by the clip below.
int it = detail(1, "iteration", 0);
float seed = chf("../seed") * 0.7919 + it * 17.31 + %(offset)g;
vector2 u = rand(seed);   // typed: rand(float) -> vector2 is two independent numbers
vector d = sample_direction_uniform(u);
vector c = getbbox_center(0);
float m = -1e9, lo = 1e9;
for (int i = 0; i < npoints(0); i++) {
    float t = dot(vector(point(0, "P", i)) - c, d);
    m = max(m, t); lo = min(lo, t);
}
float var = clamp(chf("../%(var)s"), 0.0, 1.0);
float depth = chf("../%(depth)s") * fit01(rand(seed + 0.5), 1.0 - var, 1.0);
// a real thickness floor: after the cut the rock stays at least a quarter
// of its original (unit) size thick along this direction, or the cut is
// skipped. A fraction-of-what-is-left cap instead shrank it exponentially
// (AUDITED: 64 half-depth cuts left a 0.006-thick tetrahedron, then `place`
// stretched that back to full Size).
depth = min(depth, (m - lo) - 0.25);
v@_dir = d;
v@_origin = c;
f@_dist = depth > 0.0 ? m - depth : m + 1.0;   // depth 0: plane outside, no-op
'''


def _float(name, label, default, lo, hi, help_, minlock=True, maxlock=False):
    t = hou.FloatParmTemplate(name, label, 1, (default,), min=lo, max=hi,
                              min_is_strict=minlock, max_is_strict=maxlock)
    t.setHelp(help_)
    return t


def _int(name, label, default, lo, hi, help_):
    t = hou.IntParmTemplate(name, label, 1, (default,), min=lo, max=hi,
                            min_is_strict=True, max_is_strict=False)
    t.setHelp(help_)
    return t


def _place(node, x, y, comment=None):
    node.setPosition(hou.Vector2(x, y))
    if comment:
        node.setComment(comment)
        node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return node


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
    min_num_inputs=0, max_num_inputs=1, version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setMinNumInputs(0)
defn.setMaxNumInputs(1)
defn.setIcon(ICON)

net = hda_node
out_null = net.node("OUT")
inp = net.indirectInputs()[0]
inp.setPosition(hou.Vector2(3, 12))

# --- base -------------------------------------------------------------------
base_box = _place(net.createNode("box", "base_box"), -3, 11)
base_sphere = _place(net.createNode("sphere", "base_sphere"), -1.5, 11)
base_sphere.parm("type").set("poly")
base_sphere.parm("freq").set(2)
base_tube = _place(net.createNode("tube", "base_tube"), 0, 11)
base_tube.parm("type").set("poly")
base_tube.parm("cap").set(1)
base_tube.parm("cols").set(12)

base_pick = _place(net.createNode("switch", "base_pick"), -1.5, 10,
                   "Built-in base, from the Base Shape menu.")
for i, b in enumerate((base_box, base_sphere, base_tube)):
    base_pick.setInput(i, b)
base_pick.parm("input").setExpression('ch("../shape")')

base_sw = _place(net.createNode("switch", "base_sw"), 0, 9,
                 "Whatever is wired to the input wins over the menu.\n"
                 "PROBED: opinputpath is empty when nothing is wired.")
base_sw.setInput(0, base_pick)
base_sw.setInput(1, inp)
base_sw.parm("input").setExpression('strlen(opinputpath("..", 0)) > 0')

fit = _place(net.createNode("matchsize", "fit"), 0, 8,
             "Normalise: unit cube, centred on the origin. Every depth\n"
             "below is then a fraction of the rock's size, per axis;\n"
             "`place` stretches it to Size at the end.")
fit.setInput(0, base_sw)
fit.parm("justifytarget").set("explicit")
fit.parm("doscale").set(1)
fit.parm("uniformscale").set(0)


def _chip_loop(prefix, y, input_node, offset, depth_parm, var_parm, count_parm, comment):
    """One feedback block: N iterations of plane wrangle + clip."""
    begin = _place(net.createNode("block_begin", prefix + "_begin"), 0, y, comment)
    begin.parm("method").set("feedback")
    begin.setInput(0, input_node)
    meta = _place(net.createNode("block_begin", prefix + "_meta"), 2, y)
    meta.parm("method").set("metadata")
    end = _place(net.createNode("block_end", prefix + "_end"), 0, y - 3)
    begin.parm("blockpath").set("../" + end.name())
    meta.parm("blockpath").set("../" + end.name())
    end.parm("blockpath").set("../" + begin.name())
    end.parm("templatepath").set("../" + begin.name())
    end.parm("itermethod").set("count")
    end.parm("method").set("feedback")
    end.parm("iterations").setExpression('ch("../%s")' % count_parm)

    plane = _place(net.createNode("attribwrangle", prefix + "_plane"), 0, y - 1,
                   "Random direction, extent along it, plane just inside.")
    plane.parm("class").set("detail")
    plane.setInput(0, begin)
    plane.setInput(1, meta)
    plane.parm("snippet").set(PLANE_VEX % {"offset": offset, "depth": depth_parm,
                                           "var": var_parm})

    clip = _place(net.createNode("clip::2.0", prefix + "_clip"), 0, y - 2,
                  "Keep below the plane, fill the hole - one flat chip face.")
    clip.setInput(0, plane)
    clip.parm("clipop").set("below")
    clip.parm("dofill").set(1)
    clip.parm("usefillpolygons").set(0)   # ships ON by default: a `filled` group leaked (conventions §5)
    for i, ax in enumerate("xyz"):
        clip.parm("dir" + ax).setExpression('detail("../%s", "_dir", %d)' % (plane.name(), i))
        clip.parm("origin" + ax).setExpression('detail("../%s", "_origin", %d)' % (plane.name(), i))
    clip.parm("dist").setExpression('detail("../%s", "_dist", 0)' % plane.name())
    end.setInput(0, clip)
    return end


cuts = _chip_loop("cuts", 7, fit, 3.0, "cutdepth", "cutvar", "cuts",
                  "BIG CUTS - the silhouette.")
chips = _chip_loop("chips", 3, cuts, 101.0, "chipdepth", "chipvar", "chips",
                   "SMALL CHIPS - the edges.")

# --- flat bottom --------------------------------------------------------------
floor = _place(net.createNode("clip::2.0", "floor"), 2, -1,
               "Keep above a horizontal plane at ymin + fraction * height.")
floor.setInput(0, chips)
floor.parm("clipop").set("above")
floor.parm("dofill").set(1)
floor.parm("usefillpolygons").set(0)
floor.parm("dirx").set(0)
floor.parm("diry").set(1)
floor.parm("dirz").set(0)
# Deliberately NOT under the chips' thickness floor: a clamp made Flat Bottom
# 0.2 silently do nothing on a default rock that the cuts had brought to
# 0.25 tall (unit space) - c5 caught it. Flat Bottom 0.5 on an extreme rock
# is the artist's call and is recorded in rocks.md 6.
floor.parm("originy").setExpression(
    'bbox(opinputpath(".", 0), D_YMIN) + ch("../flatbottom") * '
    '(bbox(opinputpath(".", 0), D_YMAX) - bbox(opinputpath(".", 0), D_YMIN))')
floor_sw = _place(net.createNode("switch", "floor_sw"), 0, -2,
                  "Flat Bottom 0 leaves the rock alone.")
floor_sw.setInput(0, chips)
floor_sw.setInput(1, floor)
floor_sw.parm("input").setExpression('ch("../flatbottom") > 0')

# --- bevel ------------------------------------------------------------------
bevel = _place(net.createNode("polybevel::3.0", "bevel"), 2, -3,
               "Every edge. PolyBevel limits the width where edges are\n"
               "shorter than it, so a big number is safe.")
bevel.setInput(0, floor_sw)
bevel.parm("grouptype").set("edges")
bevel.parm("group").set("*")
bevel.parm("offset").setExpression('ch("../bevel")')
bevel.parm("divisions").setExpression('ch("../bevelsegs")')
bevel.parm("filletshape").set("round")
bevel_sw = _place(net.createNode("switch", "bevel_sw"), 0, -4,
                  "Width 0 bypasses the bevel - PROBED: polybevel at offset\n"
                  "0 still doubles every point.")
bevel_sw.setInput(0, floor_sw)
bevel_sw.setInput(1, bevel)
bevel_sw.parm("input").setExpression('ch("../bevel") > 0')

# --- canonical placement ----------------------------------------------------
place = _place(net.createNode("matchsize", "place"), 0, -5,
               "Size along each axis, centred in XZ, standing on y = 0.")
place.setInput(0, bevel_sw)
place.parm("justifytarget").set("explicit")
place.parm("doscale").set(1)
place.parm("uniformscale").set(0)
for ax in "xyz":
    place.parm("size" + ax).setExpression('ch("../size%s")' % ax)
place.parm("ty").setExpression('ch("../sizey") * 0.5')

cleanup = _place(net.createNode("attribdelete", "cleanup"), 0, -6,
                 "`_*` is internal (conventions.md 2) and does not leave.")
cleanup.setInput(0, place)
for k in ("ptdel", "vtxdel", "primdel", "dtldel"):
    cleanup.parm(k).set("_*")

cleanup_grp = _place(net.createNode("groupdelete", "cleanup_grp"), 0, -7,
                     "Same sweep for groups (conventions.md 5).")
cleanup_grp.setInput(0, cleanup)
cleanup_grp.parm("group1").set("_*")

norm = _place(net.createNode("normal", "norm"), 0, -8,
              "Vertex normals, so the flat faces shade flat.")
norm.setInput(0, cleanup_grp)
norm.parm("type").set(1)  # vertex
norm.parm("cuspangle").setExpression('ch("../cuspangle")')

out_null.setInput(0, norm)
out_null.setPosition(hou.Vector2(0, -9))

# --------------------------------------------------------------------------
# Parameter interface
# --------------------------------------------------------------------------
ptg = hou.ParmTemplateGroup()

_shape = hou.MenuParmTemplate("shape", "Base Shape", BASES, menu_labels=BASE_LABELS,
                              default_value=0)
_shape.setHelp("Used when nothing is wired to the input. Box gives the blockiest "
               "rock, Cylinder the flattest top and bottom, Sphere the roundest. "
               "Wire your own blockout in and this is ignored.")
ptg.append(_shape)
ptg.append(_int("seed", "Seed", 0, 0, 1000,
                "Every chip's direction and depth. Change it for a different rock "
                "with the same settings."))
_size = hou.FloatParmTemplate("size", "Size", 3, (1.0, 0.75, 0.85), min=0.0, max=5.0,
                              min_is_strict=True)
_size.setHelp("Final extent along X, Y and Z. The rock is centred in XZ and stands "
              "on y = 0, so this is its footprint and its height.")
ptg.append(_size)

cutf = hou.FolderParmTemplate("cutsfolder", "Big Cuts", folder_type=hou.folderType.Simple)
cutf.addParmTemplate(_int("cuts", "Cuts", 12, 0, 64,
                          "How many big slices come off. These make the silhouette; "
                          "0 keeps the base shape."))
cutf.addParmTemplate(_float("cutdepth", "Depth", 0.3, 0.0, 0.5,
                            "How deep each cut goes, as a fraction of the rock's size. "
                            "0.5 can take half the rock."))
cutf.addParmTemplate(_float("cutvar", "Depth Variation", 0.6, 0.0, 1.0,
                            "0 makes every cut the same depth; 1 lets a cut be anything "
                            "from a graze to the full depth.", maxlock=True))
ptg.append(cutf)

chipf = hou.FolderParmTemplate("chipsfolder", "Small Chips", folder_type=hou.folderType.Simple)
chipf.addParmTemplate(_int("chips", "Chips", 30, 0, 200,
                           "How many small chips come off after the big cuts. These "
                           "break up the edges and corners."))
chipf.addParmTemplate(_float("chipdepth", "Depth", 0.08, 0.0, 0.5,
                             "How deep each chip goes, as a fraction of the rock's size."))
chipf.addParmTemplate(_float("chipvar", "Depth Variation", 0.6, 0.0, 1.0,
                             "0 makes every chip the same depth; 1 lets a chip be anything "
                             "from a graze to the full depth.", maxlock=True))
ptg.append(chipf)

ptg.append(_float("flatbottom", "Flat Bottom", 0.0, 0.0, 0.5,
                  "Slices the underside off flat, this fraction of the height up "
                  "from the lowest point, so the rock sits on the ground. 0 is off."))
ptg.append(_float("bevel", "Bevel Width", 0.0, 0.0, 0.2,
                  "Rounds every edge by this much (in the rock's own units before "
                  "Size). 0 keeps the edges knife sharp."))
ptg.append(_int("bevelsegs", "Bevel Segments", 1, 1, 8,
                "1 is a single flat chamfer. More segments round the edge off."))
ptg.append(_float("cuspangle", "Cusp Angle", 5.0, 0.0, 90.0,
                  "Shading only. Faces meeting below this angle shade smooth across "
                  "the edge. The default keeps every chip visibly flat (LOOKED AT: "
                  "20 hid the facets); raise it to smooth a rounded bevel."))

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
defn.addSection("Help", HELP)

hda_node.destroy()
build_geo.destroy()

# --- Verify by reading the SAVED asset back ---------------------------------
back = hou.hda.definitionsInFile(HDA_PATH)[0]
saved = back.sections()["DialogScript"].contents()
assert "Poly Factory/Modeling" in back.sections()["Tools.shelf"].contents(), "TAB submenu missing"
assert back.icon() == ICON and back.description() == TAB_LABEL
assert 'outputlabel\t1\t"%s"' % OUTPUT_LABEL in saved, "output label missing"
assert back.maxNumInputs() == 1 and back.minNumInputs() == 0
for _p in ("shape", "seed", "size", "cuts", "cutdepth", "cutvar", "chips", "chipdepth",
           "chipvar", "flatbottom", "bevel", "bevelsegs", "cuspangle"):
    assert re.search(r'name\s+"%s"' % _p, saved), "parm %s missing from the saved asset" % _p
print("wrote " + HDA_PATH)
