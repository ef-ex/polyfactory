"""Create `pf_edge_damage` - paintable, stylised chipped edges, as a SOP HDA.

    hython devScripts/create_pf_edge_damage_hda.py

Paint where a prop is worn, and the tool takes low-poly chips out of it.
Design doc: ideas/edge_damage.md. The technique is Quentin King's public
"Paintable Stylized Edge Damage" (quentinking.com/houdini/edgedamage/),
rebuilt here on native nodes to polyfactory's conventions.

    pf_edge_damage                     1 input, one chain plus a viz switch:
      contract  [attribwrangle/prim]   counts open edges and non-polygons
      warn      [error]                ...and refuses them: the boolean
                                       needs a closed polygon solid and
                                       returns NOTHING otherwise (a
                                       16-open-edge wood block cooked to 0
                                       prims). Allow Open Input downgrades
                                       the open case to a warning.
      ...
      empty     [error]                the last word: an empty result is
                                       an error with the reason in it
      fit       [matchsize]            input into the unit cube, transform
                                       stashed. Every size parm below is a
                                       fraction of the object.
      canvas    [divide, brick]        dense paint canvas at Paint Resolution
      tri       [divide]               triangulates the bricks
      maskinit  [attribwrangle/point]  `_damage` from the chosen source:
                                       0 (paint on top), an upstream
                                       attribute, or 1 everywhere
      paint     [attribpaint]          the strokes. Its stroke parms are
                                       channel-linked to this asset's, and
                                       new stroke instances are linked with
                                       `opmultiparm`, so the viewer state
                                       drives the ASSET and the inner node
                                       follows.
      rest      [attribwrangle/point]  pre-blur position, so an unpainted
                                       vertex can be put back there and
                                       pushed clear
      pull      [attribblur on P]      THE damage. Blurring positions pulls
                                       edges and corners in while flat faces
                                       stay flat; the boolean below then
                                       cuts exactly those edges off
      dmesh     [remesh]               even triangles at half the detail
                                       size, so the noise has vertices to move
      noise     [attribnoise on P]     roughens the worn edges into chips
      bias      [peak]                 lifts the cutter: higher = fewer chips
      push      [attribwrangle/point]  unpainted vertices are pushed OUT by
                                       more than the noise can dip, so the
                                       cutter never touches unpainted surface
      vdb/poly  [vdbfrompolygons, convertvdb]  a watertight cutter whatever
                                       the noise did to the topology
      lowpoly   [polyreduce]           Low-poly style: sharp irregular facets
      smooth    [remesh]               Smooth style: even small triangles
      style     [switch]
      cutn      [normal, cusp 0]       hard normals into the boolean
      cut       [boolean, intersect]   original AND cutter. B-inside-A faces
                                       are the chips: group `pf_chipped`
      restore   [matchsize]            back to the input's transform
      viz       [switch]               Output / Paint Canvas / Mask / Cutter
      clean     [attribdelete, groupdelete]  `_*` off every class
      OUT

Probed on 22.0.398 rather than recalled:
  * attribpaint's stroke multiparm is `stroke_numstrokes`, a
    TabbedMultiparmBlock; its instance parms are relayed with
    `opmultiparm node 'stroke#_x' '../stroke#_x'` - a plain `ch()` cannot
    express a per-instance link.
  * The stroke viewer state is `sidefx_stroke.StrokeState`; subclassing it and
    returning the inner paint node's geometry from `intersectGeometry` is what
    lets a LOCKED asset be painted on. That is the one Python in this tool,
    and it is UI (CLAUDE.md rule 2; decision log in the doc).
  * `boolean::2.0` `booleanop` 1 is intersect; `usebinsidea` + `binsidea`
    name the B-inside-A prim group.
  * `convertvdb` `conversion` 2 is polygons.
"""

import os
import re

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
HDA_PATH = os.path.join(_POLYFACTORY, "otls", "pf_edge_damage.hda").replace("\\", "/")

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

NAME = "pf_edge_damage"
TAB_LABEL = "PF Edge Damage"
OUTPUT_LABEL = "Damaged"
ICON = "SOP_attribpaint"
MASK = "_damage"

# The stroke parms the viewer state reads off the node it is entered on, in
# the order they sit on attribpaint. Copied from attribpaint's own templates
# so types, menus and ranges stay identical to the native node's.
STROKE_PARMS = ("stroke_radius", "stroke_float", "stroke_opacity",
                "stroke_softedge", "stroke_projtype", "stroke_attrib",
                "stroke_attribtype", "stroke_numstrokes")
STROKE_LABELS = {"stroke_radius": "Brush Radius", "stroke_float": "Strength",
                 "stroke_opacity": "Opacity", "stroke_softedge": "Soft Edge",
                 "stroke_projtype": "Projection"}
# Per-stroke instance parms relayed to the inner node. `stroke#_color` is a
# colour-attribute thing and `_damage` is a float, so it is not relayed.
STROKE_INSTANCE = ("enable", "radius", "tool", "opacity", "projtype",
                   "projcenterx", "projcentery", "projcenterz",
                   "projdirx", "projdiry", "projdirz", "data", "metadata")

MASKINIT_VEX = r'''// pf_edge_damage - where damage is allowed, before any stroke lands.
int mode = chi("../masksource");
string a = chs("../maskattrib");
float d = 0.0;
if (mode == 1 && haspointattrib(0, a)) d = point(0, a, @ptnum);
if (mode == 2) d = 1.0;
f@%s = d;
''' % MASK

# Where the canvas was BEFORE the blur, so the push below can put an
# unpainted vertex back there and then out - whatever the blur did to it.
REST_VEX = r'''v@_rest = @P;
'''

# The push is what keeps unpainted surface untouched. An unpainted vertex is
# returned to its pre-blur position and moved OUT, along the ORIGINAL's face
# normal there (input 1 is the fitted input; xyzdist finds the face), by
# more than the bias, the voxels and the reduction can bring anything back
# IN - the noise only ever adds outward. So the cutter clears the original
# wherever nothing was painted and the intersection keeps it whole.
#   Two earlier forms failed on a thin plank and the audit caught the first:
#   adding to the blurred position was 0.09 short at a blurred corner, and
#   pushing along an interpolated rest NORMAL went nowhere across the thin
#   side, where the top and bottom normals cancel to ~0 (measured 0.14 long).
#   A face normal read off the original cannot cancel.
PUSH_VEX = r'''// pf_edge_damage - unpainted vertices clear the original surface.
float clear = chf("../chipdepth") + abs(chf("../bias")) + chf("../detail") * 0.5 + 0.05;
float d = clamp(f@%s, 0.0, 1.0);
int pr; vector uv;
xyzdist(1, v@_rest, pr, uv);
vector fn = prim_normal(1, pr, uv.x, uv.y);
vector safe = v@_rest + fn * clear;
@P = lerp(safe, @P, d);
''' % MASK

# The boolean needs a closed polygon solid and quietly returns nothing
# otherwise - a wood block with 16 open edges cooked to 0 prims. Counted on
# the input, before any of this tool's own work, and raised as a warning.
CONTRACT_VEX = r'''// pf_edge_damage - the input contract, counted for the warning below.
if (primintrinsic(0, "typename", @primnum) != "Poly")
    setdetailattrib(0, "_nonpoly", 1, "add");
int h = primhedge(0, @primnum);
for (int i = 0; i < primvertexcount(0, @primnum); i++) {
    if (hedge_equivcount(0, h) < 2) setdetailattrib(0, "_open", 1, "add");
    h = hedge_next(0, h);
}
'''

MASKVIZ_VEX = r'''@Cd = lerp({0.25, 0.25, 0.25}, {1.0, 0.35, 0.0}, clamp(f@%s, 0.0, 1.0));
''' % MASK

VIEWER_STATE = r'''"""pf_edge_damage - paint the damage mask on a LOCKED asset.

sidefx_stroke.StrokeState writes strokes into the node it is entered on
(this asset's `stroke_*` parms) and asks `intersectGeometry` what to paint
against: the inner paint canvas. Entering flips the viz switch to the canvas
so the brush lands on what is drawn; leaving flips it back to the output.
"""
import hou
import toolutils
from sidefx_stroke import StrokeState


class State(StrokeState):
    def __init__(self, **kwargs):
        super(State, self).__init__(**kwargs)
        self.cursor.init_brushlist([("sphere", {})])
        self.cursor.prompt = "Paint damage. MMB drag / wheel resizes the brush."
        self.root = None
        self.paint = None

    def onEnter(self, kwargs):
        super(State, self).onEnter(kwargs)
        self.root = kwargs["node"]
        self.paint = toolutils.findChildNodeOfType(self.root, "attribpaint", True)
        self.root.parm("viz").set(1)
        for v in self.scene_viewer.viewports():
            v.frameBoundingBox(self.root.geometry().boundingBox())

    def onExit(self, kwargs):
        super(State, self).onExit(kwargs)
        if self.root is not None:
            self.root.parm("viz").set(0)

    def intersectGeometry(self, node):
        if (self.intersect_geometry is None
                or self.intersect_geometry.sopNode() != self.paint):
            self.intersect_geometry = self.paint.geometry()
        return self.intersect_geometry


def createViewerStateTemplate():
    typename = kwargs["type"].definition().sections()["DefaultState"].contents()
    t = hou.ViewerStateTemplate(typename, "Edge Damage Paint",
                                hou.sopNodeTypeCategory())
    t.bindFactory(State)
    t.bindIcon(kwargs["type"].icon())
    return t
'''

PYTHON_MODULE = r'''def reset(node):
    """The Reset button: drop every stroke. The strokes live on this node's
    own multiparm; the inner paint node is locked and holds nothing."""
    node.parm("stroke_numstrokes").set(0)
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


def _menu(name, label, items, labels, default, help_):
    t = hou.MenuParmTemplate(name, label, items, menu_labels=labels,
                             default_value=default)
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


def _wrangle(name, x, y, vex, comment, cls="point"):
    w = _place(net.createNode("attribwrangle", name), x, y, comment)
    w.parm("class").set(cls)
    w.parm("snippet").set(vex)
    return w


contract = _wrangle("contract", 0, 16, CONTRACT_VEX,
                    "Counts open edges and non-polygons on the INPUT.",
                    cls="primitive")
contract.setInput(0, src)

warn = _place(net.createNode("error", "warn"), 0, 15,
              "The boolean needs a closed polygon solid and returns\n"
              "nothing otherwise. Said here, not discovered later.\n"
              "PROBED: a warning inside a locked asset never reaches\n"
              "the asset node; an error does, text and all.")
warn.setInput(0, contract)
warn.parm("numerror").set(2)
warn.parm("enable1").setExpression('detail("../contract", "_open", 0) > 0')
# 2 = error, 1 = warning (which only a diver into the asset would see).
warn.parm("severity1").setExpression('if(ch("../allowopen"), 1, 2)')
warn.parm("errormsg1").set(
    "Input is not closed: `detail(\"../contract\", \"_open\", 0)` open "
    "edges. Edge damage needs a watertight solid - Fuse or PolyFill it "
    "first, or turn on Allow Open Input to cut anyway.")
warn.parm("enable2").setExpression('detail("../contract", "_nonpoly", 0) > 0')
warn.parm("severity2").set(2)
warn.parm("errormsg2").set(
    "Input has `detail(\"../contract\", \"_nonpoly\", 0)` non-polygon "
    "primitives. Convert to polygons first.")

fit = _place(net.createNode("matchsize", "fit"), 0, 14,
             "Into the unit cube, transform stashed. Every size below\n"
             "is a fraction of the object.")
fit.setInput(0, warn)
fit.parm("doscale").set(1)
fit.parm("stashxform").set(1)

canvas = _place(net.createNode("divide", "canvas"), 0, 13,
                "Dense paint canvas. Brick divide keeps flat faces flat.")
canvas.setInput(0, fit)
canvas.parm("brick").set(1)
canvas.parm("convex").set(0)
canvas.parm("usemaxsides").set(0)
for ax in "xyz":
    canvas.parm("size" + ax).setExpression('ch("../paintres")')

tri = _place(net.createNode("divide", "tri"), 0, 12)
tri.setInput(0, canvas)

maskinit = _wrangle("maskinit", 0, 11, MASKINIT_VEX,
                    "`_damage`: 0 for painting, an upstream attribute,\n"
                    "or 1 everywhere.")
maskinit.setInput(0, tri)

paint = _place(net.createNode("attribpaint", "paint"), 0, 10,
               "Stroke parms are channel-linked to the asset's; new\n"
               "stroke instances are linked with opmultiparm.")
paint.setInput(0, maskinit)
paint.parm("attribname1").set(MASK)
paint.parm("attribtype1").set(1)                 # float
for p in STROKE_PARMS[:-1]:
    if p == "stroke_attrib":
        paint.parm(p).set(MASK)
    else:
        paint.parm(p).setExpression('ch("../%s")' % p)
paint.parm("stroke_numstrokes").setExpression('ch("../stroke_numstrokes")')
_links = " ".join("'stroke#_%s' '../stroke#_%s'" % (p, p) for p in STROKE_INSTANCE)
_err = hou.hscript("opmultiparm %s %s" % (paint.path(), _links))[1]
assert not _err, "opmultiparm: " + _err

rest = _wrangle("rest", 0, 9.3, REST_VEX,
                "Pre-blur position, for the push below.")
rest.setInput(0, paint)

pull = _place(net.createNode("attribblur", "pull"), 0, 9,
              "THE damage: blurring P pulls edges and corners in while\n"
              "flat faces stay flat. Everything after this only\n"
              "roughens the result. Distance scales with Paint\n"
              "Resolution x Edge Wear.")
pull.setInput(0, rest)
pull.parm("attributes").set("P")
pull.parm("iterations").setExpression('ch("../edgewear")')

dmesh = _place(net.createNode("remesh::2.0", "dmesh"), 0, 8,
               "Even triangles at half the detail size - vertices\n"
               "for the noise to move.")
dmesh.setInput(0, pull)
dmesh.parm("targetsize").setExpression('ch("../detail") * 0.5')

noise = _place(net.createNode("attribnoise::2.0", "noise"), 0, 7,
               "The chip shapes.")
noise.setInput(0, dmesh)
noise.parm("attribs").set("P")
noise.parm("displace").set(1)
for p in ("amplitude", "elementsize", "basis", "fractal", "oct", "lac",
          "rough", "offset"):
    noise.parm(p).setExpression('ch("../%s")' % {
        "amplitude": "chipdepth", "elementsize": "chipsize",
        "offset": "seed"}.get(p, p))

bias = _place(net.createNode("peak", "bias"), 0, 6,
              "Lifts the whole cutter: higher = fewer chips.")
bias.setInput(0, noise)
bias.parm("dist").setExpression('ch("../bias")')

push = _wrangle("push", 0, 5, PUSH_VEX,
                "Unpainted vertices go back to where they were and OUT\n"
                "along the original's face normal (input 1), further\n"
                "than anything can pull them IN.")
push.setInput(0, bias)
push.setInput(1, fit)

vdb = _place(net.createNode("vdbfrompolygons", "vdb"), 0, 4,
             "A watertight cutter whatever the noise did.")
vdb.setInput(0, push)
vdb.parm("voxelsize").setExpression('ch("../detail") * 0.25')
vdb.parm("exteriorbandvoxels").set(1)
vdb.parm("interiorbandvoxels").set(5)

poly = _place(net.createNode("convertvdb", "poly"), 0, 3)
poly.setInput(0, vdb)
poly.parm("conversion").set(2)                   # polygons

noname = _place(net.createNode("attribdelete", "noname"), 0, 2.5,
                "vdbfrompolygons names its grid `surface`, and that prim\n"
                "`name` would ride the chip faces out through the boolean.")
noname.setInput(0, poly)
noname.parm("doprimdel").set(1)
noname.parm("primdel").set("name")

lowpoly = _place(net.createNode("polyreduce::2.0", "lowpoly"), 2, 2,
                 "Low-poly: sharp, irregular facets. A floor of 200\n"
                 "polygons, because a percentage of a small cutter\n"
                 "reduced to nothing and the output was empty.")
lowpoly.setInput(0, noname)
lowpoly.parm("target").set(2)                    # polygon count
lowpoly.parm("finalcount").setExpression(
    'max(nprims("../noname") * ch("../lowpolypct") / 100, 200)')

smooth = _place(net.createNode("remesh::2.0", "smooth"), -2, 2,
                "Smooth: even small triangles.")
smooth.setInput(0, noname)
smooth.parm("targetsize").setExpression('ch("../smoothsize")')

style = _place(net.createNode("switch", "style"), 0, 1)
style.setInput(0, smooth)
style.setInput(1, lowpoly)
style.parm("input").setExpression('ch("../style")')

cutn = _place(net.createNode("normal", "cutn"), 0, 0,
              "Hard normals into the boolean.")
cutn.setInput(0, style)
cutn.parm("cuspangle").set(0)

cut = _place(net.createNode("boolean::2.0", "cut"), 0, -1,
             "Original AND cutter. The cutter's faces inside the\n"
             "original are the chips: `pf_chipped`.")
cut.setInput(0, fit)
cut.setInput(1, cutn)
cut.parm("booleanop").set(1)                     # intersect
cut.parm("usebinsidea").set(1)
cut.parm("binsidea").set("pf_chipped")

restore = _place(net.createNode("matchsize", "restore"), 0, -2,
                 "Back to the input's transform.")
restore.setInput(0, cut)
restore.parm("restorexform").set(1)

maskviz = _wrangle("maskviz", 4, -2, MASKVIZ_VEX, "Mask as colour.")
maskviz.setInput(0, pull)

viz = _place(net.createNode("switch", "viz"), 0, -3,
             "Output / Paint Canvas / Mask / Cutter. The paint state\n"
             "flips this to the canvas while painting.")
viz.setInput(0, restore)
viz.setInput(1, tri)
viz.setInput(2, maskviz)
viz.setInput(3, cutn)
viz.parm("input").setExpression('ch("../viz")')

clean = _place(net.createNode("attribdelete", "clean"), 0, -4,
               "`_*` off every class (conventions.md 2).")
clean.setInput(0, viz)
for cls in ("pt", "vtx", "prim", "dtl"):
    clean.parm("do%sdel" % cls).set(1)
    clean.parm("%sdel" % cls).set("_*")

gclean = _place(net.createNode("groupdelete", "gclean"), 0, -5)
gclean.setInput(0, clean)
gclean.parm("group1").set("_*")

empty = _place(net.createNode("error", "empty"), 0, -6,
               "An open input let through can still cut to nothing.\n"
               "Nothing is never silent.")
empty.setInput(0, gclean)
empty.parm("enable1").setExpression(
    'nprims("../restore") == 0 && nprims("../contract") > 0')
empty.parm("severity1").set(2)
empty.parm("errormsg1").set(
    "Edge damage produced nothing. The input is not a watertight solid "
    "(`detail(\"../contract\", \"_open\", 0)` open edges) - Fuse or "
    "PolyFill it first.")

out_null.setInput(0, empty)
out_null.setPosition(hou.Vector2(0, -7))

# --------------------------------------------------------------------------
# Parameter interface
# --------------------------------------------------------------------------
ptg = hou.ParmTemplateGroup()

ptg.append(_menu("viz", "Show", ("output", "canvas", "mask", "cutter"),
                 ("Output", "Paint Canvas", "Mask", "Cutter"), 0,
                 "What the node draws. The paint state switches to the "
                 "canvas by itself; Mask and Cutter are for checking."))
ptg.append(_menu("masksource", "Damage Where", ("paint", "attrib", "all"),
                 ("I Paint It", "An Attribute Says", "Everywhere"), 0,
                 "Paint: only where strokes land. Attribute: a float "
                 "point attribute from upstream, 0..1, strokes add on "
                 "top. Everywhere: the whole surface."))
_ma = hou.StringParmTemplate("maskattrib", "Mask Attribute", 1,
                             default_value=("pf_damage",))
_ma.setHelp("The upstream point attribute read when Damage Where is "
            "An Attribute Says.")
ptg.append(_ma)
_ao = hou.ToggleParmTemplate("allowopen", "Allow Open Input", False)
_ao.setHelp("The cut needs a watertight polygon solid and an open mesh "
            "is refused with an error. Turn this on to cut anyway - the "
            "result may be open, wrong, or empty (which is still an "
            "error).")
ptg.append(_ao)

ptg.append(_float("chipdepth", "Chip Depth", 0.07, 0.0, 0.5,
                  "How deep a chip cuts, as a fraction of the object."))
ptg.append(_float("chipsize", "Chip Size", 0.1, 0.01, 1.0,
                  "How big the chips are, as a fraction of the object."))
ptg.append(_float("bias", "Damage Bias", 0.04, -0.1, 0.1,
                  "How much of the painted area actually chips. Lower is "
                  "more, higher is less; 0 chips about half.",
                  minlock=False))
ptg.append(_float("detail", "Detail", 0.2, 0.02, 1.0,
                  "Size of the smallest feature, as a fraction of the "
                  "object. Smaller is finer and slower."))
ptg.append(_int("edgewear", "Edge Wear", 13, 0, 50,
                "How far edges and corners get eaten, in canvas cells - "
                "so it scales with Paint Resolution. At the defaults a cube "
                "loses about 1% of its volume; 0 leaves only the noise "
                "chips. Thin parts wear through first."))
ptg.append(_float("paintres", "Paint Resolution", 0.05, 0.01, 0.2,
                  "Canvas cell size, as a fraction of the object. Sets "
                  "how fine you can paint AND how far one step of Edge "
                  "Wear reaches: doubling it doubles the wear. Above ~0.1 "
                  "the flat faces start to go too.", maxlock=True))
ptg.append(_menu("style", "Chip Style", ("smooth", "lowpoly"),
                 ("Smooth", "Low-poly"), 1,
                 "Low-poly gives sharp irregular facets; Smooth gives an "
                 "even small-triangle surface."))
ptg.append(_float("lowpolypct", "Low-poly Amount", 10.0, 1.0, 100.0,
                  "Percentage of the cutter's polygons kept. Lower is "
                  "chunkier.", maxlock=True))
ptg.append(_float("smoothsize", "Smooth Triangle Size", 0.25, 0.01, 1.0,
                  "Triangle size of the Smooth style, as a fraction of "
                  "the object."))
ptg.append(_float("seed", "Seed", 0.0, 0.0, 100.0,
                  "Another value, another set of chips.", minlock=False))

adv = hou.FolderParmTemplate("advfolder", "Advanced Noise",
                             folder_type=hou.folderType.Collapsible)
_ap = hou.node("/obj").createNode("geo", "_tmpl").createNode("attribnoise::2.0")
NOISE_HELP = {
    "basis": "Attribute Noise's own noise types. Simplex is the default; "
             "Worley types give cellular, crystal-like chips.",
    "fractal": "Layers of finer noise on top. None is the plain noise.",
    "oct": "How many finer layers, when Fractal is on.",
    "lac": "How much finer each layer is than the last.",
    "rough": "How strong each finer layer is relative to the last."}
for p in ("basis", "fractal", "oct", "lac", "rough"):
    t = _ap.parmTemplateGroup().find(p)
    t.setHelp(NOISE_HELP[p])
    adv.addParmTemplate(t)
_ap.parent().destroy()
ptg.append(adv)

pnt = hou.FolderParmTemplate("paintfolder", "Paint",
                             folder_type=hou.folderType.Collapsible)
_tp = hou.node("/obj").createNode("geo", "_tmpl2").createNode("attribpaint")
_tpg = _tp.parmTemplateGroup()
STROKE_HELP = {
    "stroke_radius": "Brush size in the viewport. MMB-drag or the mouse "
                     "wheel changes it while painting.",
    "stroke_float": "How much damage one stroke paints: 1 is full, less "
                    "fades, negative erases.",
    "stroke_opacity": "Stroke opacity, like a paint program.",
    "stroke_softedge": "How soft the brush edge is.",
    "stroke_projtype": "How the brush projects onto the surface.",
    "stroke_numstrokes": "The strokes themselves, one entry each. Reset "
                         "Strokes clears them."}
STROKE_DEFAULTS = {"stroke_attrib": (MASK,), "stroke_radius": (0.1,),
                   "stroke_float": (1.0,), "stroke_projtype": 4}
for p in STROKE_PARMS:
    t = _tpg.find(p)
    if p in STROKE_LABELS:
        t.setLabel(STROKE_LABELS[p])
    if p in STROKE_HELP:
        t.setHelp(STROKE_HELP[p])
    if p in STROKE_DEFAULTS:
        t.setDefaultValue(STROKE_DEFAULTS[p])
    if p in ("stroke_attrib", "stroke_attribtype"):
        t.hide(True)
    pnt.addParmTemplate(t)
_tp.parent().destroy()
_reset = hou.ButtonParmTemplate("reset", "Reset Strokes")
_reset.setHelp("Drops every stroke.")
_reset.setScriptCallback("hou.phm().reset(kwargs['node'])")
_reset.setScriptCallbackLanguage(hou.scriptLanguage.Python)
pnt.addParmTemplate(_reset)
ptg.append(pnt)

defn.setParmTemplateGroup(ptg)

defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

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
defn.addSection("PythonModule", PYTHON_MODULE)
# The embedded viewer state, exactly as the Type Properties editor installs it.
typename = defn.nodeTypeName()
defn.addSection("DefaultState", typename)
defn.addSection("ViewerStateName.orig", typename)
defn.addSection("ViewerStateModule", VIEWER_STATE)
defn.addSection("ViewerStateInstall",
                "__import__('viewerstate.utils', fromlist=[None])"
                ".register_pystate_embedded(kwargs['type'])")
defn.addSection("ViewerStateUninstall",
                "__import__('viewerstate.utils', fromlist=[None])"
                ".unregister_pystate_embedded(kwargs['type'])")
# Without these flags Houdini runs the install/uninstall sections as
# HSCRIPT ("Unknown command: __import__") and the state never registers.
# Mirrors the options on attribpaint's own definition.
for _sec in ("ViewerStateInstall", "ViewerStateUninstall", "ViewerStateModule",
             "PythonModule", "ViewerStateName.orig"):
    defn.setExtraFileOption(_sec + "/IsPython", True)
    defn.setExtraFileOption(_sec + "/IsScript", True)
for _sec in ("ViewerStateInstall", "ViewerStateUninstall", "ViewerStateModule"):
    defn.setExtraFileOption(_sec + "/IsViewerState", True)

hda_node.destroy()
build_geo.destroy()

# --- Verify by reading the SAVED asset back, never the build state --------
back = hou.hda.definitionsInFile(HDA_PATH)[0]
saved = back.sections()["DialogScript"].contents()
assert "Poly Factory/Modeling" in back.sections()["Tools.shelf"].contents()
assert back.icon() == ICON, "icon is %r" % back.icon()
assert back.description() == TAB_LABEL
assert 'outputlabel\t1\t"%s"' % OUTPUT_LABEL in saved
assert back.sections()["DefaultState"].contents() == back.nodeTypeName()
for _p in ("viz", "masksource", "maskattrib", "allowopen", "chipdepth", "chipsize", "bias",
           "detail", "edgewear", "style", "lowpolypct", "smoothsize", "seed",
           "paintres", "basis", "stroke_radius", "stroke_numstrokes", "reset"):
    assert re.search(r'name\s+"%s"' % _p, saved), "parm %s missing" % _p
print("wrote " + HDA_PATH)
