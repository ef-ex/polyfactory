"""Create `pf_ring` - a flat-sided ring (annular prism) generator, as a SOP HDA.

    hython devScripts/create_pf_ring_hda.py

Not a torus. A ring whose outer wall, inner wall, top and bottom are all FLAT
polygons: a solid 3D band, the thing you reach for when a torus is too round.

    pf_ring                            10 nodes, no inputs:
      profile   [attribwrangle/detail]   the cross-section in the XY plane,
                                         x = radius, y = height. Both tapers
                                         are applied here, per side.
      bevel     [polybevel::3.0]         cuts the profile CORNERS in-plane,
                                         so bevel cost does not scale with
                                         the ring's side count
      swbevel   [switch]                 bypasses the bevel at width 0 -
                                         PROBED: polybevel at offset 0 still
                                         splits every corner into two
                                         coincident points, which would ship
                                         a degenerate quad per corner ring
      rev       [revolve]                around +Y. divs/type/angles are all
                                         expressions off the parms
      markwall  [attribwrangle/prim]     `_wall` on everything the revolve
                                         made, so the caps can be told apart
                                         from it afterwards
      cap       [polycap]                fills the two arc ends. A no-op on a
                                         closed ring (PROBED: 64 prims in,
                                         64 out) so it is always in the chain
      capuv     [attribwrangle/vertex]   UVs for those caps. `polycap` emits
                                         none, so every cap vertex arrived at
                                         uv (0,0,0) - a solid black patch on
                                         any textured arc
      cleanup   [attribdelete]           `_wall` off the output (conventions
                                         §2; `tests/hda/run_attrib_checks.py`
                                         fails the build if it survives)
      norm      [normal]                 vertex normals + cusp angle, so the
                                         flat sides SHADE flat as well
      OUT       [null]

Every face is planar by construction: each quad spans one angular step, so its
two radial edges are parallel chords - and that holds under either taper,
because dropping an edge's height keeps those two chords parallel. Measured on
the built asset, worst-case out-of-plane error is float32 noise (~4e-08 at
radius 1).

Reference-checked on 22.0.398 rather than recalled - the corrections that came
out of probing:
  * there is no `bevel` SOP; it is `polybevel::3.0`
  * `revolve`'s `cap` toggle does NOT cap an open arc (192 prims either way);
    `polycap` does, and shares the boundary points instead of adding new ones
  * ⚠️ HSCRIPT HAS NO TERNARY. `ch("../arcangle") >= 359.999 ? 0 : 1` does not
    error - it silently evaluates to the COMPARISON and drops the rest, so at
    360 it returned 1 and every ring shipped as a seamed open arc that
    `polycap` then closed back up. Watertight, right radii, right silhouette,
    100 points where 96 belong. Comparisons are used bare below. (VEX is a
    different language and its `?:` is fine - the profile snippet uses it.)
  * ⚠️ HOUDINI WINDS A FRONT FACE CLOCKWISE seen from outside. Measured: a
    `box` encloses -1.0000 and a poly `sphere` -4.07 under the standard CCW
    divergence formula, and `normal`'s N is minus their CCW face normal. Emit
    the profile the other way round and the ring ships inside out.
  * all five `filletshape` entries are safe here - each stays watertight and
    planar on this profile - but `None` ignores the division count.
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

# polybevel::3.0's own `filletshape` menu, in its own order, so the parm below
# feeds it straight through with no remapping to get out of step.
BEVEL_SHAPES = ("none", "solid", "crease", "chamfer", "round")
BEVEL_LABELS = ("None", "Solid", "Crease", "Chamfer", "Round")

# --------------------------------------------------------------------------
# The cross-section. One detail run, four points (three where a side tapers to
# an edge) - explicit construction, so the profile is exactly what it says.
#
# x is RADIUS and y is HEIGHT, centred on the origin like the Tube SOP, so the
# revolve about +Y lands the ring in the canonical place with no transform.
#
# Two tapers per side, each an amount plus a bias saying where it is spent:
#   WIDTH  taper moves that face's radii   - the face gets narrower
#   HEIGHT taper drops that face's corners - the face slopes
# A bias of -1 spends it at the inner circle, +1 at the outer, 0 at both.
# --------------------------------------------------------------------------
PROFILE_VEX = r'''// pf_ring - cross-section in the XY plane (x = radius, y = height).
float ro = chf("../outer"), ri = chf("../inner"), h = chf("../height");
float tt = chf("../taper_top"),  bt  = chf("../bias_top");
float tb = chf("../taper_bot"),  bb  = chf("../bias_bot");
float ht = chf("../htaper_top"), hbt = chf("../hbias_top");
float hb = chf("../htaper_bot"), hbb = chf("../hbias_bot");

// Radii are unordered on purpose: swapping the two parms must not invert a ring.
float lo = min(ri, ro), hi = max(ri, ro);
ri = lo; ro = hi;
float w = ro - ri;

// --- width taper: move the radii ---
float wt = w * (1.0 - clamp(tt, 0.0, 1.0));      // width left at the top
float wb = w * (1.0 - clamp(tb, 0.0, 1.0));      // ... and at the bottom
float ft = (clamp(bt, -1.0, 1.0) + 1.0) * 0.5;   // 0 = hug inner, 1 = hug outer
float fb = (clamp(bb, -1.0, 1.0) + 1.0) * 0.5;

float rit = ri + (w - wt) * ft, rot = rit + wt;
float rib = ri + (w - wb) * fb, rob = rib + wb;
float y0 = -h * 0.5, y1 = h * 0.5;

// --- height taper: drop the corners, same amount/bias grammar ---
float gt = (clamp(hbt, -1.0, 1.0) + 1.0) * 0.5;  // 0 = drop inner, 1 = outer
float gb = (clamp(hbb, -1.0, 1.0) + 1.0) * 0.5;
float dt = h * clamp(ht, 0.0, 1.0);
float db = h * clamp(hb, 0.0, 1.0);
float y1i = y1 - dt * (1.0 - gt), y1o = y1 - dt * gt;
float y0i = y0 + db * (1.0 - gb), y0o = y0 + db * gb;
y1i = max(y1i, y0i);                             // the faces may meet,
y1o = max(y1o, y0o);                             // they may not cross

// A fully width-tapered side is one edge, not two coincident points - that is
// what keeps the tip a row of triangles instead of zero-area quads. Both sides
// collapsing would leave a profile with no area, so the bottom keeps its width.
int ct = (wt <= 1e-6), cb = (wb <= 1e-6);
if (ct && cb) cb = 0;

// ⚠️ ORDER IS THE OUTSIDE OF THE RING. Houdini winds a front face CLOCKWISE
// seen from outside - MEASURED, not recalled: a `box` and a poly `sphere`
// both enclose a NEGATIVE volume under the standard CCW divergence formula,
// and their `normal` SOP N is minus their CCW face normal. Emit this profile
// the other way round and every ring ships inside out - correct silhouette,
// correct volume, normals pointing into the solid.
int pts[];
if (!ct) append(pts, addpoint(0, set(rit, y1i, 0)));                  // top in
append(pts, addpoint(0, set(rot, ct ? (y1i + y1o) * 0.5 : y1o, 0)));  // top out
if (!cb) append(pts, addpoint(0, set(rob, y0o, 0)));                  // bot out
append(pts, addpoint(0, set(rib, cb ? (y0i + y0o) * 0.5 : y0i, 0)));  // bot in
addprim(0, "poly", pts);
'''

# `polycap` emits no UVs at all, so an arc's two end faces arrived at uv
# (0,0,0) - one solid black patch under any texture. They get the profile's
# own parametrisation: u across the ring's width, v up its height, which is
# the same 0-1 square `revolve` gives the walls.
CAPUV_VEX = r'''// pf_ring - UVs for the arc's end caps. Walls already have revolve's.
int wall = prim(0, "_wall", @primnum);
if (wall == 0) {
    float ri = min(chf("../inner"), chf("../outer"));
    float ro = max(chf("../inner"), chf("../outer"));
    float h  = chf("../height");
    float r  = length(set(@P.x, 0.0, @P.z));
    float u  = (ro - ri) > 1e-9 ? (r - ri) / (ro - ri) : 0.0;
    float v  = h > 1e-9 ? (@P.y + h * 0.5) / h : 0.0;
    v@uv = set(clamp(u, 0.0, 1.0), clamp(v, 0.0, 1.0), 0.0);
}
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


def _taper_pair(prefix, side, kind, what):
    """The four (amount, bias) pairs share one grammar; write it once."""
    amount = _float(
        "%staper_%s" % (prefix, side), "%s %s Taper" % (side.capitalize(), kind),
        0.0, 0.0, 1.0,
        "How much %s the %s face loses. 0 leaves it alone, 1 spends all "
        "of it." % (what, side), maxlock=True)
    bias = _float(
        "%sbias_%s" % (prefix, side), "%s %s Towards" % (side.capitalize(), kind),
        0.0, -1.0, 1.0,
        "Where that is spent: -1 at the inner circle, +1 at the outer, 0 at "
        "both evenly.", minlock=True, maxlock=True)
    return amount, bias


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


profile = _place(net.createNode("attribwrangle", "profile"), 0, 7,
                 "The cross-section: x = radius, y = height.\n"
                 "Width and height taper are both applied here, per side.")
profile.parm("class").set("detail")
profile.parm("snippet").set(PROFILE_VEX)

bevel = _place(net.createNode("polybevel::3.0", "bevel"), 2, 6,
               "Corner bevel, in the profile plane - so it costs the\n"
               "same whatever the ring's side count is.")
bevel.setInput(0, profile)
bevel.parm("grouptype").set(1)          # points
bevel.parm("group").set("*")
bevel.parm("offset").setExpression('ch("../bevel")')
bevel.parm("divisions").setExpression('ch("../bevelsegs")')
bevel.parm("filletshape").setExpression('ch("../bevelshape")')

swbevel = _place(net.createNode("switch", "swbevel"), 0, 5,
                 "PROBED: polybevel at offset 0 still splits every corner\n"
                 "into two coincident points, so zero width takes the\n"
                 "unbevelled profile instead of a degenerate one.")
swbevel.setInput(0, profile)
swbevel.setInput(1, bevel)
swbevel.parm("input").setExpression('ch("../bevel") > 0')

rev = _place(net.createNode("revolve", "rev"), 0, 4,
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

markwall = _place(net.createNode("attribwrangle", "markwall"), 0, 3,
                  "Everything the revolve made is wall. Whatever polycap\n"
                  "adds next is therefore a cap, and can be UV'd alone.")
markwall.setInput(0, rev)
markwall.parm("class").set("primitive")
markwall.parm("snippet").set("i@_wall = 1;")

cap = _place(net.createNode("polycap", "cap"), 0, 2,
             "Fills the two arc ends. PROBED as a no-op on a closed\n"
             "ring, so it stays in the chain unconditionally.")
cap.setInput(0, markwall)

capuv = _place(net.createNode("attribwrangle", "capuv"), 0, 1,
               "polycap emits NO UVs - every cap vertex arrives at\n"
               "uv (0,0,0), one black patch under any texture.")
capuv.setInput(0, cap)
capuv.parm("class").set("vertex")
capuv.parm("snippet").set(CAPUV_VEX)

cleanup = _place(net.createNode("attribdelete", "cleanup"), 0, 0,
                 "`_wall` is internal (conventions.md 2) and does not\n"
                 "leave the node.")
cleanup.setInput(0, capuv)
cleanup.parm("doprimdel").set(1)
cleanup.parm("primdel").set("_wall")

norm = _place(net.createNode("normal", "norm"), 0, -1,
              "Vertex normals, so the flat sides shade flat too.")
norm.setInput(0, cleanup)
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
    "two cut ends are capped and UV'd.", maxlock=True))
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
_shape = hou.MenuParmTemplate("bevelshape", "Bevel Shape", BEVEL_SHAPES,
                              menu_labels=BEVEL_LABELS, default_value=4)
_shape.setHelp("PolyBevel's own fillet shapes, passed straight through. "
               "Round is the default and Chamfer is its flat equivalent; "
               "Solid and Crease fill the corner instead of rounding it. "
               "None ignores the segment count below.")
bev.addParmTemplate(_shape)
bev.addParmTemplate(_int(
    "bevelsegs", "Bevel Segments", 1, 1, 16,
    "1 is a single flat cut whatever the shape. More segments round the "
    "corner off - except under None, which ignores this."))
ptg.append(bev)

tap = hou.FolderParmTemplate("taperfolder", "Taper",
                             folder_type=hou.folderType.Simple)
for _a, _b in (_taper_pair("", "top", "Width", "of the ring's width"),
               _taper_pair("h", "top", "Height", "of the ring's height")):
    tap.addParmTemplate(_a)
    tap.addParmTemplate(_b)
tap.addParmTemplate(hou.SeparatorParmTemplate("tapersep"))
for _a, _b in (_taper_pair("", "bot", "Width", "of the ring's width"),
               _taper_pair("h", "bot", "Height", "of the ring's height")):
    tap.addParmTemplate(_a)
    tap.addParmTemplate(_b)
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
for _p in ("htaper_top", "hbias_top", "htaper_bot", "hbias_bot", "bevelshape"):
    assert re.search(r'name\s+"%s"' % _p, saved),         "parm %s missing from the saved asset" % _p
print("wrote " + HDA_PATH)
