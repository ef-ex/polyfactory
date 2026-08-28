"""Create `pf_ring` - a flat-sided ring (annular prism) generator, as a SOP HDA.

    hython devScripts/create_pf_ring_hda.py

Not a torus. A ring whose outer wall, inner wall, top and bottom are all FLAT
polygons: a solid 3D band, the thing you reach for when a torus is too round.

    pf_ring                            7 nodes, no inputs:
      profile   [attribwrangle/detail]   the cross-section in the XY plane,
                                         x = radius, y = height. Taper is
                                         applied here, per side.
      bevel     [polybevel::3.0]         chamfers/rounds the profile CORNERS,
                                         in-plane, before anything is revolved
      swbevel   [switch]                 bypasses the bevel at width 0 -
                                         PROBED: polybevel at offset 0 still
                                         splits every corner into two
                                         coincident points, which would ship
                                         a degenerate quad per corner ring
      rev       [revolve]                around +Y. divs/type/angles are all
                                         expressions off the parms
      cap       [polycap]                fills the two arc ends. A no-op on a
                                         closed ring (PROBED: 64 prims in,
                                         64 out) so it is always in the chain
      norm      [normal]                 vertex normals + cusp angle, so the
                                         flat sides SHADE flat as well
      OUT       [null]

Every face is planar by construction: each quad spans one angular step, so its
two radial edges are parallel chords. Measured on the built asset, worst-case
out-of-plane error is float32 noise (~1e-8 at radius 1).

Reference-checked on 22.0.398 rather than recalled - the corrections that came
out of probing:
  * there is no `bevel` SOP; it is `polybevel::3.0`
  * `revolve`'s `cap` toggle does NOT cap an open arc (192 prims either way);
    `polycap` does, and shares the boundary points instead of adding new ones
  * ⚠️ HSCRIPT HAS NO TERNARY. `ch("../arcangle") >= 359.999 ? 0 : 1` does not
    error - it silently evaluates to the COMPARISON and drops the rest, so at
    360 it returned 1 and every ring shipped as a seamed open arc that
    `polycap` then closed back up. Watertight, right radii, right silhouette,
    100 points where 96 belong. Comparisons are used bare below.
  * `circle` spreads `divs` over the ARC, not the full circle. `pf_ring` does
    the opposite on purpose - `Sides` is the count for a FULL turn and the arc
    takes its share, so facet size stays put while an artist scrubs the arc.
"""

import os
import re

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
HDA_PATH = os.path.join(_POLYFACTORY, "otls", "pf_ring.hda").replace("\\", "/")

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

OUTPUT_LABEL = "Ring"

# --------------------------------------------------------------------------
# The cross-section. One detail run, four points (three where a side tapers to
# an edge) - explicit construction, so the profile is exactly what it says.
#
# x is RADIUS and y is HEIGHT, centred on the origin like the Tube SOP, so the
# revolve about +Y lands the ring in the canonical place with no transform.
#
# Taper, per side: `taper` is how much of the ring's width that side loses,
# `bias` is where the survivor sits - -1 keeps it on the inner circle, +1 on
# the outer, 0 takes the width off both edges evenly.
# --------------------------------------------------------------------------
PROFILE_VEX = r'''// pf_ring - cross-section in the XY plane (x = radius, y = height).
float ro = chf("../outer"), ri = chf("../inner"), h = chf("../height");
float tt = chf("../taper_top"), bt = chf("../bias_top");
float tb = chf("../taper_bot"), bb = chf("../bias_bot");

// Radii are unordered on purpose: swapping the two parms must not invert a ring.
float lo = min(ri, ro), hi = max(ri, ro);
ri = lo; ro = hi;
float w = ro - ri;

float wt = w * (1.0 - clamp(tt, 0.0, 1.0));      // width left at the top
float wb = w * (1.0 - clamp(tb, 0.0, 1.0));      // ... and at the bottom
float ft = (clamp(bt, -1.0, 1.0) + 1.0) * 0.5;   // 0 = hug inner, 1 = hug outer
float fb = (clamp(bb, -1.0, 1.0) + 1.0) * 0.5;

float rit = ri + (w - wt) * ft, rot = rit + wt;
float rib = ri + (w - wb) * fb, rob = rib + wb;
float y0 = -h * 0.5, y1 = h * 0.5;

// A fully tapered side is one edge, not two coincident points - that is what
// keeps the tip a row of triangles instead of a row of zero-area quads. Both
// sides collapsing would leave a profile with no area at all, so the bottom
// keeps its width.
int ct = (wt <= 1e-6), cb = (wb <= 1e-6);
if (ct && cb) cb = 0;

// ⚠️ ORDER IS THE OUTSIDE OF THE RING. Houdini winds a front face CLOCKWISE
// seen from outside - MEASURED, not recalled: a `box` and a poly `sphere`
// both enclose a NEGATIVE volume under the standard CCW divergence formula,
// and their `normal` SOP N is minus their CCW face normal. Emit this profile
// the other way round and every ring ships inside out - correct silhouette,
// correct volume, normals pointing into the solid.
int pts[];
if (!ct) append(pts, addpoint(0, set(rit, y1, 0)));   // top inner
append(pts, addpoint(0, set(rot, y1, 0)));            // top outer
if (!cb) append(pts, addpoint(0, set(rob, y0, 0)));   // bottom outer
append(pts, addpoint(0, set(rib, y0, 0)));            // bottom inner
addprim(0, "poly", pts);
'''


def _float(name, label, default, lo, hi, help_, minlock=True, maxlock=False):
    t = hou.FloatParmTemplate(name, label, 1, (default,),
                              min=lo, max=hi,
                              min_is_strict=minlock, max_is_strict=maxlock)
    t.setHelp(help_)
    return t


def _int(name, label, default, lo, hi, help_):
    t = hou.IntParmTemplate(name, label, 1, (default,), min=lo, max=hi,
                            min_is_strict=True, max_is_strict=False)
    t.setHelp(help_)
    return t


if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_pf_ring")
subnet = build_geo.createNode("subnet", "pf_ring")
subnet.createNode("null", "OUT").setDisplayFlag(True)

hda_node = subnet.createDigitalAsset(
    name="pf_ring",
    hda_file_name=HDA_PATH,
    description="Ring",
    min_num_inputs=0,
    max_num_inputs=0,
    version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setMinNumInputs(0)
defn.setMaxNumInputs(0)
defn.setIcon("SOP_tube")

net = hda_node
out_null = net.node("OUT")


def _place(node, x, y, comment=None):
    node.setPosition(hou.Vector2(x, y))
    if comment:
        node.setComment(comment)
        node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return node


profile = _place(net.createNode("attribwrangle", "profile"), 0, 4,
                 "The cross-section: x = radius, y = height.\n"
                 "Taper is applied here, per side.")
profile.parm("class").set("detail")
profile.parm("snippet").set(PROFILE_VEX)

bevel = _place(net.createNode("polybevel::3.0", "bevel"), 2, 3,
               "Corner bevel, in the profile plane - so it costs the\n"
               "same whatever the ring's side count is.")
bevel.setInput(0, profile)
bevel.parm("grouptype").set(1)          # points
bevel.parm("group").set("*")
bevel.parm("offset").setExpression('ch("../bevel")')
bevel.parm("divisions").setExpression('ch("../bevelsegs")')
bevel.parm("filletshape").set(4)        # round; one division reads as a chamfer

swbevel = _place(net.createNode("switch", "swbevel"), 0, 2,
                 "PROBED: polybevel at offset 0 still splits every corner\n"
                 "into two coincident points, so zero width takes the\n"
                 "unbevelled profile instead of a degenerate one.")
swbevel.setInput(0, profile)
swbevel.setInput(1, bevel)
swbevel.parm("input").setExpression('ch("../bevel") > 0')

rev = _place(net.createNode("revolve", "rev"), 0, 1,
             "Around +Y. `Sides` is the count for a FULL turn; an arc\n"
             "takes its share, so facet size holds while the arc changes.")
rev.setInput(0, swbevel)
rev.parm("dirx").set(0)
rev.parm("diry").set(1)
rev.parm("dirz").set(0)
rev.parm("primtype").set(1)             # poly
rev.parm("surftype").set(5)             # quads
rev.parm("divs").setExpression(
    'max(1, ceil(ch("../sides") * ch("../arcangle") / 360))')
# 0 = closed, 1 = openarc. A bare comparison, never a ternary - see the
# HScript trap in this file's docstring.
rev.parm("type").setExpression('ch("../arcangle") < 359.999')
rev.parm("beginangle").setExpression('ch("../startangle")')
rev.parm("endangle").setExpression('ch("../startangle") + ch("../arcangle")')

cap = _place(net.createNode("polycap", "cap"), 0, 0,
             "Fills the two arc ends. PROBED as a no-op on a closed\n"
             "ring, so it stays in the chain unconditionally.")
cap.setInput(0, rev)

norm = _place(net.createNode("normal", "norm"), 0, -1,
              "Vertex normals, so the flat sides shade flat too.")
norm.setInput(0, cap)
norm.parm("type").set(1)                # vertex
norm.parm("cuspangle").setExpression('ch("../cuspangle")')

out_null.setInput(0, norm)
out_null.setPosition(hou.Vector2(0, -2))

# --------------------------------------------------------------------------
# Parameter interface
# --------------------------------------------------------------------------
ptg = hou.ParmTemplateGroup()

ptg.append(_int("sides", "Sides", 24, 3, 64,
                "Flat sides around a FULL turn. An arc uses its share of "
                "them, so the facets stay the same size when the arc "
                "angle changes."))
ptg.append(_float("outer", "Outer Radius", 1.0, 0.0, 10.0,
                  "Radius of the outer wall, measured at the CORNERS - the "
                  "flat sides are chords, so the mid-edge sits a little "
                  "closer in."))
ptg.append(_float("inner", "Inner Radius", 0.7, 0.0, 10.0,
                  "Radius of the hole, at the corners. Swapping it past the "
                  "outer radius is harmless - the two are sorted."))
ptg.append(_float("height", "Height", 0.25, 0.0, 10.0,
                  "Thickness along Y. The ring is centred on the origin, "
                  "like the Tube SOP."))

arc = hou.FolderParmTemplate("arcfolder", "Arc",
                             folder_type=hou.folderType.Simple)
arc.addParmTemplate(_float(
    "arcangle", "Arc Angle", 360.0, 0.0, 360.0,
    "360 is a closed ring. Anything less opens it into an arc, and the "
    "two cut ends are capped.", maxlock=True))
arc.addParmTemplate(_float(
    "startangle", "Start Angle", 0.0, -360.0, 360.0,
    "Where the arc begins, in degrees about +Y. Ignored at a full 360.",
    minlock=False))
ptg.append(arc)

bev = hou.FolderParmTemplate("bevelfolder", "Bevel",
                             folder_type=hou.folderType.Simple)
bev.addParmTemplate(_float(
    "bevel", "Bevel Width", 0.0, 0.0, 0.5,
    "Cuts all four corners of the cross-section - outer and inner, top "
    "and bottom. PolyBevel limits it for you when it would run past an "
    "edge, so a big number gives you the fattest bevel that fits."))
bev.addParmTemplate(_int(
    "bevelsegs", "Bevel Segments", 1, 1, 16,
    "1 is a chamfer. More segments round the corner off."))
ptg.append(bev)

tap = hou.FolderParmTemplate("taperfolder", "Taper",
                             folder_type=hou.folderType.Simple)
tap.addParmTemplate(_float(
    "taper_top", "Top Taper", 0.0, 0.0, 1.0,
    "How much of the ring's width the TOP face loses. 0 leaves it full "
    "width, 1 tapers it to an edge.", maxlock=True))
tap.addParmTemplate(_float(
    "bias_top", "Top Towards", 0.0, -1.0, 1.0,
    "Where the top's remaining width sits: -1 against the inner circle, "
    "+1 against the outer, 0 takes it off both edges evenly.",
    minlock=True, maxlock=True))
tap.addParmTemplate(_float(
    "taper_bot", "Bottom Taper", 0.0, 0.0, 1.0,
    "The same for the BOTTOM face, independent of the top.", maxlock=True))
tap.addParmTemplate(_float(
    "bias_bot", "Bottom Towards", 0.0, -1.0, 1.0,
    "Where the bottom's remaining width sits: -1 inner, +1 outer.",
    minlock=True, maxlock=True))
ptg.append(tap)

ptg.append(_float(
    "cuspangle", "Cusp Angle", 10.0, 0.0, 90.0,
    "Shading only. Below this angle neighbouring faces shade smooth. The "
    "default keeps the sides visibly flat; raise it to smooth a rounded "
    "bevel."))

defn.setParmTemplateGroup(ptg)
defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))

_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

# `setParmTemplateGroup` regenerates DialogScript, so the output label is
# patched onto the SAVED definition afterwards - there is no HOM API for it.
defn = hou.hda.definitionsInFile(HDA_PATH)[0]
ds = defn.sections()["DialogScript"].contents()
if "outputlabel" in ds:
    ds = re.sub(r'outputlabel\t1\t"[^"]*"',
                'outputlabel\t1\t"%s"' % OUTPUT_LABEL, ds)
else:
    ds = ds.replace('  parm {', '  outputlabel\t1\t"%s"\n  parm {'
                    % OUTPUT_LABEL, 1)
defn.addSection("DialogScript", ds)
defn.addSection("Tools.shelf", TOOLS_SHELF)

hda_node.destroy()
build_geo.destroy()

# --- Verify by reading the SAVED asset back, never the build state --------
back = hou.hda.definitionsInFile(HDA_PATH)[0]
saved = back.sections()["DialogScript"].contents()
assert "Poly Factory/Modeling" in back.sections()["Tools.shelf"].contents(), \
    "TAB submenu missing"
assert back.icon() == "SOP_tube", "icon is %r" % back.icon()
assert 'outputlabel\t1\t"%s"' % OUTPUT_LABEL in saved, "output label missing"
print("wrote " + HDA_PATH)
