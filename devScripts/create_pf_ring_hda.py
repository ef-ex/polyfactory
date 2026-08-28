"""Create `pf_ring` - a flat-sided ring (annular prism) generator, as a SOP HDA.

    hython devScripts/create_pf_ring_hda.py

Not a torus. A ring whose outer wall, inner wall, top and bottom are all FLAT
polygons: a solid 3D band, the thing you reach for when a torus is too round.

    pf_ring                            11 nodes, no inputs:
      profile   [attribwrangle/detail]   the cross-section in the XY plane,
                                         x = radius, y = height. The four
                                         corner offsets land here.
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
      capuv     [attribwrangle/prim]     UVs for those caps. `polycap` emits
                                         none, so every cap vertex arrived at
                                         uv (0,0,0) - a solid black patch on
                                         any textured arc. Each cap is fitted
                                         to its OWN extents, so it stays a
                                         full square whatever the corner
                                         offsets and the bevel do to it.
      uvlayout  [uvlayout]               packs every island into the 1001
                                         tile. Without it the wall island ran
                                         v 0..5 at the default radius and
                                         0..11 at radius 5, and the caps sat
                                         on top of the walls.
      cleanup   [attribdelete]           `_wall` off the output (conventions
                                         §2; `tests/hda/run_attrib_checks.py`
                                         fails the build if it survives)
      norm      [normal]                 vertex normals + cusp angle, so the
                                         flat sides SHADE flat as well
      OUT       [null]

Every face is planar by construction: each quad spans one angular step, so its
two radial edges are parallel chords - and that holds however the corners are
offset, because moving a corner keeps those two chords parallel. Measured on
the built asset, worst-case out-of-plane error is float32 noise (~3e-08 at
radius 1).

THE SHAPE CONTROLS: one global radius pair and height, then a radius and a
height offset on each of the four corners, ADDED on top. Nothing is a
percentage of anything, so the same offset means the same distance whatever
else is set, and a corner only ever moves when its own two parms move. That
replaced an amount/bias taper pair per side, which produced the same shapes
and was much harder to aim.

Reference-checked on 22.0.398 rather than recalled - the corrections that came
out of probing:
  * there is no `bevel` SOP; it is `polybevel::3.0`
  * `revolve`'s `cap` toggle does NOT cap an open arc (192 prims either way);
    `polycap` does, and shares the boundary points instead of adding new ones
  * `revolve` ships `normalizev 0`, so v is length-weighted and UNBOUNDED -
    it is set to 1 here so the wall island reaches `uvlayout` proportioned
    like a square rather than 11 times too tall
  * `revolve` runs u ACROSS the cross-section and v AROUND the arc, which is
    the opposite of the obvious guess
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

# The four corners of the cross-section: (suffix, label, radius parm base,
# height parm base). Order is the order they are emitted in, which is also
# the order they appear on the parameter page.
CORNERS = (("to", "Top Outer"), ("ti", "Top Inner"),
           ("bo", "Bottom Outer"), ("bi", "Bottom Inner"))

# --------------------------------------------------------------------------
# The cross-section. One detail run, four points (three when two corners land
# on the same spot) - explicit construction, so the profile is exactly what
# it says it is.
#
# x is RADIUS and y is HEIGHT, centred on the origin like the Tube SOP, so the
# revolve about +Y lands the ring in the canonical place with no transform.
#
# Each corner is the global radius/height PLUS its own two offsets. Height is
# a world +Y offset on all four, so a positive number always moves that corner
# up, whichever face it belongs to, and nothing is relative to anything else.
# --------------------------------------------------------------------------
PROFILE_VEX = r'''// pf_ring - cross-section in the XY plane (x = radius, y = height).
float ro = chf("../outer"), ri = chf("../inner"), h = chf("../height");

// Radii are unordered on purpose: swapping the two parms must not invert a ring.
float lo = min(ri, ro), hi = max(ri, ro);
ri = lo; ro = hi;
float y0 = -h * 0.5, y1 = h * 0.5;

// Per-corner offsets, ADDED to the global radius and height above. A radius
// is clamped at the axis; nothing else is clamped, so a corner goes exactly
// where it is sent - including past its neighbour, which is the artist's call.
float rot = max(ro + chf("../rad_to"), 0.0), y1o = y1 + chf("../hgt_to");
float rit = max(ri + chf("../rad_ti"), 0.0), y1i = y1 + chf("../hgt_ti");
float rob = max(ro + chf("../rad_bo"), 0.0), y0o = y0 + chf("../hgt_bo");
float rib = max(ri + chf("../rad_bi"), 0.0), y0i = y0 + chf("../hgt_bi");

// Two corners landing on the SAME point are one point, not two coincident
// ones - that is what keeps a knife edge a row of triangles instead of a row
// of zero-area quads. Both pairs collapsing would leave a profile with no
// area at all, so the bottom keeps its two.
int ct = (abs(rot - rit) <= 1e-6 && abs(y1o - y1i) <= 1e-6);
int cb = (abs(rob - rib) <= 1e-6 && abs(y0o - y0i) <= 1e-6);
if (ct && cb) cb = 0;

// ⚠️ ORDER IS THE OUTSIDE OF THE RING. Houdini winds a front face CLOCKWISE
// seen from outside - MEASURED, not recalled: a `box` and a poly `sphere`
// both enclose a NEGATIVE volume under the standard CCW divergence formula,
// and their `normal` SOP N is minus their CCW face normal. Emit this profile
// the other way round and every ring ships inside out - correct silhouette,
// correct volume, normals pointing into the solid.
int pts[];
if (!ct) append(pts, addpoint(0, set(rit, y1i, 0)));   // top inner
append(pts, addpoint(0, set(rot, y1o, 0)));            // top outer
if (!cb) append(pts, addpoint(0, set(rob, y0o, 0)));   // bottom outer
append(pts, addpoint(0, set(rib, y0i, 0)));            // bottom inner
addprim(0, "poly", pts);
'''

# `polycap` emits no UVs at all, so an arc's two end faces arrived at uv
# (0,0,0) - one solid black patch under any texture. Each cap is fitted to
# its OWN radius/height extents rather than to the parameters, so a bevel or
# an offset corner cannot shrink the square it gets. `uvlayout` downstream
# then packs this island alongside the walls.
CAPUV_VEX = r'''// pf_ring - UVs for the arc's end caps. Walls already have revolve's.
int wall = prim(0, "_wall", @primnum);
if (wall == 0) {
    int pts[] = primpoints(0, @primnum);
    float rmin = 1e18, rmax = -1e18, ymin = 1e18, ymax = -1e18;
    foreach (int pt; pts) {
        vector p = point(0, "P", pt);
        float r = length(set(p.x, 0.0, p.z));
        rmin = min(rmin, r); rmax = max(rmax, r);
        ymin = min(ymin, p.y); ymax = max(ymax, p.y);
    }
    float dr = max(rmax - rmin, 1e-9), dy = max(ymax - ymin, 1e-9);
    for (int i = 0; i < len(pts); i++) {
        vector p = point(0, "P", pts[i]);
        float r = length(set(p.x, 0.0, p.z));
        setvertexattrib(0, "uv", @primnum, i,
                        set((r - rmin) / dr, (p.y - ymin) / dy, 0.0));
    }
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


profile = _place(net.createNode("attribwrangle", "profile"), 0, 8,
                 "The cross-section: x = radius, y = height.\n"
                 "Global radius/height plus each corner's own offsets.")
profile.parm("class").set("detail")
profile.parm("snippet").set(PROFILE_VEX)

bevel = _place(net.createNode("polybevel::3.0", "bevel"), 2, 7,
               "Corner bevel, in the profile plane - so it costs the\n"
               "same whatever the ring's side count is.")
bevel.setInput(0, profile)
bevel.parm("grouptype").set(1)          # points
bevel.parm("group").set("*")
bevel.parm("offset").setExpression('ch("../bevel")')
bevel.parm("divisions").setExpression('ch("../bevelsegs")')
bevel.parm("filletshape").setExpression('ch("../bevelshape")')

swbevel = _place(net.createNode("switch", "swbevel"), 0, 6,
                 "PROBED: polybevel at offset 0 still splits every corner\n"
                 "into two coincident points, so zero width takes the\n"
                 "unbevelled profile instead of a degenerate one.")
swbevel.setInput(0, profile)
swbevel.setInput(1, bevel)
swbevel.parm("input").setExpression('ch("../bevel") > 0')

rev = _place(net.createNode("revolve", "rev"), 0, 5,
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
# Ships as 0, which leaves v length-weighted and unbounded (0..11 at radius 5).
rev.parm("normalizev").set(1)

markwall = _place(net.createNode("attribwrangle", "markwall"), 0, 4,
                  "Everything the revolve made is wall. Whatever polycap\n"
                  "adds next is therefore a cap, and can be UV'd alone.")
markwall.setInput(0, rev)
markwall.parm("class").set("primitive")
markwall.parm("snippet").set("i@_wall = 1;")

cap = _place(net.createNode("polycap", "cap"), 0, 3,
             "Fills the two arc ends. PROBED as a no-op on a closed\n"
             "ring, so it stays in the chain unconditionally.")
cap.setInput(0, markwall)

capuv = _place(net.createNode("attribwrangle", "capuv"), 0, 2,
               "polycap emits NO UVs - every cap vertex arrives at\n"
               "uv (0,0,0), one black patch under any texture.")
capuv.setInput(0, cap)
capuv.parm("class").set("primitive")
capuv.parm("snippet").set(CAPUV_VEX)

uvlayout = _place(net.createNode("uvlayout", "uvlayout"), 0, 1,
                  "Everything packed into the 1001 tile, caps beside the\n"
                  "walls rather than on top of them.")
uvlayout.setInput(0, capuv)

cleanup = _place(net.createNode("attribdelete", "cleanup"), 0, 0,
                 "`_wall` is internal (conventions.md 2) and does not\n"
                 "leave the node.")
cleanup.setInput(0, uvlayout)
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
                  "closer in. Both outer corners start here."))
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

crn = hou.FolderParmTemplate("cornerfolder", "Corners",
                             folder_type=hou.folderType.Simple)
for _i, (_suf, _lab) in enumerate(CORNERS):
    if _i == 2:
        crn.addParmTemplate(hou.SeparatorParmTemplate("cornersep"))
    crn.addParmTemplate(_float(
        "rad_" + _suf, _lab + " Radius", 0.0, -1.0, 1.0,
        "Moves the %s corner in or out, on top of the %s radius. Negative "
        "goes towards the axis." % (_lab.lower(),
                                    "outer" if "o" in _suf[1] else "inner"),
        minlock=False))
    crn.addParmTemplate(_float(
        "hgt_" + _suf, _lab + " Height", 0.0, -1.0, 1.0,
        "Moves the %s corner along +Y, on top of the height. Positive is "
        "always UP, on the bottom corners too." % _lab.lower(),
        minlock=False))
ptg.append(crn)

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
_want = ["bevelshape"]
for _suf, _lab in CORNERS:
    _want += ["rad_" + _suf, "hgt_" + _suf]
for _p in _want:
    assert re.search(r'name\s+"%s"' % _p, saved), \
        "parm %s missing from the saved asset" % _p
for _gone in ("taper_top", "bias_top", "htaper_top", "hbias_top",
              "cornerlabel"):
    assert not re.search(r'name\s+"%s"' % _gone, saved), \
        "%s is still on the asset" % _gone
print("wrote " + HDA_PATH)
