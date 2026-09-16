"""Create `pf_wood_cracks` - lens-shaped splits along the grain, cut by boolean.

    hython devScripts/create_pf_wood_cracks_hda.py

Wood splits along its fibre: thin lens-shaped slits, tapered at both ends,
closed in the middle of a board and running out through the end grain so
the tip gapes. Studied on 8-bitBot's prop-log.obj and tile-wood-panel-v.obj
(ideas/wood_cracks.md). Same family as pf_edge_damage: build a cutter,
boolean it out of the wood, ship the cut faces as a group.

    pf_wood_cracks                     1 input (a CLOSED polygon solid):
      fit       [matchsize]            into the unit cube, transform stashed
                                       - every size below is a fraction of
                                       the object
      grain     [attribwrangle/detail] `_grain`: the grain direction, from
                                       the menu or the longest bbox axis
      scatter   [scatter::2.0]         one point per crack, on the surface,
                                       with `_sourceprim` (the face it sits
                                       on); an optional density attribute
                                       gates where
      place     [attribwrangle/point]  per crack: pushed to an end (End
                                       Bias), a frame (x along the grain in
                                       the surface, y out along N, with the
                                       angle jitter), `scale` = (length,
                                       depth, width) with their variance.
                                       Reads the grain AND the face normal
                                       off input 1 (the grain node): scatter
                                       drops details, and its interpolated
                                       point N tilts near edges
      lenspts   [attribwrangle/detail] the cutter's points: an ellipse ring
                                       at y = +0.5 (pokes above the surface)
                                       and a two-point ridge at y = -1
      lens      [shrinkwrap::2.0]      ...hulled: a watertight wedge with
                                       correct winding, for free
      loop      [block_begin x2 .. block_end, feedback over the crack points]
        onecopy [copytopoints::2.0]    the wedge on THIS crack point,
                                       oriented and scaled
        cut     [boolean, subtract]    wood minus this wedge
        tag     [attribwrangle/prim]   crack walls remembered as
                                       `_crack_face` (the boolean regroups
                                       every cut, an attribute survives)
        m_before/m_after [measure]     volume before and after
        guard   [switch]               a cut that halves the volume is a
                                       boolean that FAILED, not a crack:
                                       keep the wood as it was
        tally   [attribwrangle/detail] `pf_cracks_skipped`
      groups    [attribwrangle/prim]   `pf_crack`, `pf_original`, and edge
                                       group `pf_seam` = every edge a crack
                                       face shares with an original face
      restore   [matchsize]            back to the input's transform
      cleanup   [attribdelete, groupdelete]  `_*` off every class
      OUT

    Why one cut per crack: on 8-bitBot's log (9 self-intersection points,
    out of contract but exactly what game props are) ONE wedge at count 12 /
    seed 0 made a single boolean of all the wedges collapse the log to 234
    floating faces. Per crack, the guard refuses that one cut and the log
    keeps the other eleven. `pf_cracks_skipped` says so.

Probed on 22.0.398 rather than recalled:
  * scatter::2.0: `npts` (with `forcetotal` on, default), `seed`,
    `usedensityattrib` + `densityattrib`.
  * copytopoints::2.0 orients by `orient` and scales by a vector `scale`
    point attribute on the target - no packing needed.
  * boolean::2.0 `booleanop` 2 is subtract; `aoutsideb` / `binsidea` /
    `abseamedges` name the groups.
  * shrinkwrap::2.0 at defaults is a convex hull.
"""

import os
import re

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
HDA_PATH = os.path.join(_POLYFACTORY, "otls", "pf_wood_cracks.hda").replace("\\", "/")

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

NAME = "pf_wood_cracks"
TAB_LABEL = "PF Wood Cracks"
OUTPUT_LABEL = "Cracked"
ICON = "SOP_boolean"

GRAIN_VEX = r'''// pf_wood_cracks - the grain direction: chosen axis, or the longest bbox axis.
vector bmin, bmax;
getbbox(0, bmin, bmax);
vector ext = bmax - bmin;
int axis = chi("../grainaxis");
if (axis == 3) axis = (ext.x >= ext.y && ext.x >= ext.z) ? 0 : (ext.y >= ext.z ? 1 : 2);
vector g = 0; g[axis] = 1.0;
v@_grain = g;
v@_bmin = bmin; v@_bmax = bmax;
'''

PLACE_VEX = r'''// pf_wood_cracks - one crack per point: where, which way, how big.
// Input 1 is the grain node: scatter does NOT pass detail attributes
// through (PROBED - `_grain` read off input 0 was a zero vector, and every
// crack was placed and turned by the fallbacks).
vector grain = detail(1, "_grain"); vector bmin = detail(1, "_bmin"), bmax = detail(1, "_bmax");
float seed = chf("../seed");
float r1 = rand(@ptnum * 7.13 + seed), r2 = rand(@ptnum * 3.71 + seed + 11.0);
float r3 = rand(@ptnum * 5.29 + seed + 23.0), r4 = rand(@ptnum * 9.17 + seed + 37.0);

// End Bias: this share of the cracks sits ON an end, so the lens runs out
// through the end grain and the tip gapes. Slide the point along the grain
// to that face; it stays on the surface it was scattered on.
if (r1 < chf("../endbias")) {
    float lo = dot(bmin, grain), hi = dot(bmax, grain);
    float target = (r2 < 0.5) ? lo : hi;
    @P += grain * (target - dot(@P, grain));
}

// Frame: x along the grain projected into the surface, y out along the
// FACE normal (read off the face the point was scattered on - an
// interpolated point N tilts near edges, PROBED), with a little angle
// jitter about it. A face whose normal IS the grain (the end grain) gets
// an arbitrary in-plane x, which is what a crack in end grain looks like.
vector n = normalize(prim_normal(1, i@_sourceprim, 0.5, 0.5));
vector t = grain - n * dot(grain, n);
if (length(t) < 1e-4) t = cross(n, {0, 1, 0});
if (length(t) < 1e-4) t = cross(n, {1, 0, 0});
t = normalize(t);
float jit = radians(chf("../anglejitter")) * (r3 * 2.0 - 1.0);
matrix3 rot = ident(); rotate(rot, jit, n);
t = normalize(t * rot);
matrix3 frame = set(t, n, cross(t, n));
p@orient = quaternion(frame);

// Size, as fractions of the object, each with its variance.
float lv = chf("../lengthvar"), wv = chf("../widthvar");
float len = chf("../length") * (1.0 + lv * (r4 * 2.0 - 1.0));
float wid = chf("../width") * (1.0 + wv * (rand(@ptnum * 2.71 + seed + 41.0) * 2.0 - 1.0));
float dep = chf("../depth");
v@scale = set(len, dep, wid);
i@_crack = @ptnum;                 // the loop below cuts one crack per piece
'''

TAG_VEX = r'''// pf_wood_cracks - remember which faces are crack walls across the loop:
// the boolean regroups A's faces on every cut, so a group would forget the
// cracks of earlier iterations. An attribute does not.
if (inprimgroup(0, "_cut", @primnum)) i@_crack_face = 1;
'''

TALLY_VEX = r'''// pf_wood_cracks - count the cuts the guard refused (input 1: the mesh
// before the cut, input 2: after; each carries its volume as `_vol`).
float before = detail(1, "_vol", 0), after = detail(2, "_vol", 0);
if (after < 0.5 * before) i@pf_cracks_skipped += 1;
'''

GROUPS_VEX = r'''// pf_wood_cracks - the three groups, rebuilt exactly after the loop:
// crack walls, everything else, and the seam = every edge a crack face
// shares with an original face (the mouth of every crack).
int crack = prim(0, "_crack_face", @primnum);
setprimgroup(0, "pf_crack", @primnum, crack);
setprimgroup(0, "pf_original", @primnum, !crack);
if (crack) {
    int h = primhedge(0, @primnum);
    for (int i = 0; i < primvertexcount(0, @primnum); i++) {
        int o = hedge_nextequiv(0, h);
        if (o != h && prim(0, "_crack_face", hedge_prim(0, o)) == 0)
            setedgegroup(0, "pf_seam", hedge_srcpoint(0, h), hedge_dstpoint(0, h), 1);
        h = hedge_next(0, h);
    }
}
'''

LENS_VEX = r'''// pf_wood_cracks - the cutter's points, hulled by the shrinkwrap after this:
// an ellipse ring at y = +0.5 (so it pokes above a faceted surface) and a
// two-point ridge at y = -1 (the crack's floor, tapered to 70% of the length).
// Unit sizes; per-crack `scale` = (length, depth, width) does the rest.
int n = max(6, chi("../segments"));
for (int i = 0; i < n; i++) {
    float a = 2.0 * PI * i / n;
    addpoint(0, set(0.5 * cos(a), 0.5, 0.5 * sin(a)));
}
addpoint(0, set(-0.35, -1.0, 0.0));
addpoint(0, set( 0.35, -1.0, 0.0));
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


fit = _place(net.createNode("matchsize", "fit"), 0, 10,
             "Into the unit cube, transform stashed. Every size is a\n"
             "fraction of the object.")
fit.setInput(0, src)
fit.parm("doscale").set(1)
fit.parm("stashxform").set(1)

grain = _wrangle("grain", 0, 9, GRAIN_VEX, "Grain direction and bbox, as detail attributes.", cls="detail")
grain.setInput(0, fit)

scatter = _place(net.createNode("scatter::2.0", "scatter"), 0, 8,
                 "One point per crack. A density attribute gates where.\n"
                 "`_sourceprim`: the face each point sits on, for its normal.")
scatter.setInput(0, grain)
scatter.parm("useprimnumattrib").set(1)
scatter.parm("primnumattrib").set("_sourceprim")
scatter.parm("npts").setExpression('ch("../count")')
scatter.parm("seed").setExpression('ch("../seed")')
scatter.parm("usedensityattrib").setExpression('strlen(chs("../maskattrib")) > 0')
scatter.parm("densityattrib").setExpression('chs("../maskattrib")')

place = _wrangle("place", 0, 7, PLACE_VEX,
                 "Per crack: End Bias slides it onto an end; a frame along\n"
                 "the grain with angle jitter; scale = (length, depth, width).")
place.setInput(0, scatter)
place.setInput(1, grain)

lenspts = _wrangle("lenspts", 3, 8, LENS_VEX,
                   "Ellipse ring at y=+0.5, ridge at y=-1. Unit size.", cls="detail")

lens = _place(net.createNode("shrinkwrap::2.0", "lens"), 3, 7,
              "Convex hull: a watertight wedge, correct winding, for free.")
lens.setInput(0, lenspts)

# --- one crack per iteration, and a cut that would destroy the mesh is
# --- refused. PROBED on 8-bitBot's log (9 self-intersection points): a
# --- single wedge at count 12 / seed 0 made one boolean of all wedges
# --- collapse the log to 234 floating faces; counts 10, 11 and other
# --- seeds were fine. Subtracting one at a time and keeping the previous
# --- mesh when the volume would halve degrades to "one crack fewer".
fb_begin = _place(net.createNode("block_begin", "fb_begin"), 0, 6,
                  "Feedback: the wood so far. `_*` details from `grain`\n"
                  "ride along, so the cleanup at the end must earn its place.")
fb_begin.setInput(0, grain)
fb_begin.parm("method").set(0)                   # feedback
fb_begin.parm("blockpath").set("../loop_end")

pc_begin = _place(net.createNode("block_begin", "pc_begin"), 3, 6,
                  "Piece: this iteration's crack point.")
pc_begin.setInput(0, place)
pc_begin.parm("method").set(1)                   # piece
pc_begin.parm("blockpath").set("../loop_end")

onecopy = _place(net.createNode("copytopoints::2.0", "onecopy"), 3, 5,
                 "The wedge on this crack point, by `orient` and `scale`.")
onecopy.setInput(0, lens)
onecopy.setInput(1, pc_begin)

cut = _place(net.createNode("boolean::2.0", "cut"), 0, 4,
             "Wood minus this wedge. `_cut`: the wedge's faces inside the\n"
             "wood - tagged next, because the boolean regroups every time.")
cut.setInput(0, fb_begin)
cut.setInput(1, onecopy)
cut.parm("booleanop").set(2)                     # subtract
cut.parm("usebinsidea").set(1)
cut.parm("binsidea").set("_cut")

tag = _wrangle("tag", 0, 3, TAG_VEX, "Crack walls remembered as `_crack_face`.", cls="primitive")
tag.setInput(0, cut)

m_before = _place(net.createNode("measure::2.0", "m_before"), -3, 3, "Volume before the cut.")
m_before.setInput(0, fb_begin)
m_after = _place(net.createNode("measure::2.0", "m_after"), 3, 3, "Volume after the cut.")
m_after.setInput(0, tag)
for _m in (m_before, m_after):
    _m.parm("measure").set(2)                    # volume
    _m.parm("integrationdomain").set(2)          # throughout -> one total
    _m.parm("usetotalattrib").set(1)
    _m.parm("totalattribname").set("_vol")

guard = _place(net.createNode("switch", "guard"), 0, 2,
               "0: keep the wood as it was; 1: take the cut. A cut that\n"
               "halves the volume is a boolean that failed, not a crack.")
guard.setInput(0, fb_begin)
guard.setInput(1, tag)
guard.parm("input").setExpression(
    'detail("../m_after", "_vol", 0) >= 0.5 * detail("../m_before", "_vol", 0)')

tally = _wrangle("tally", 0, 1, TALLY_VEX, "`pf_cracks_skipped` counts the refused cuts.", cls="detail")
tally.setInput(0, guard)
tally.setInput(1, m_before)
tally.setInput(2, m_after)

loop_end = _place(net.createNode("block_end", "loop_end"), 0, 0,
                  "One iteration per crack point (`_crack`), feeding the\n"
                  "wood back.")
loop_end.setInput(0, tally)
loop_end.parm("itermethod").set(1)               # by pieces
loop_end.parm("method").set(0)                   # feedback
loop_end.parm("class").set(1)                    # point pieces
loop_end.parm("useattrib").set(1)
loop_end.parm("attrib").set("_crack")
loop_end.parm("blockpath").set("../fb_begin")
loop_end.parm("templatepath").set("../pc_begin")

groups = _wrangle("groups", 0, -1, GROUPS_VEX,
                  "pf_crack / pf_original from the tag; pf_seam = every\n"
                  "edge a crack face shares with an original one.", cls="primitive")
groups.setInput(0, loop_end)

restore = _place(net.createNode("matchsize", "restore"), 0, -2, "Back to the input's transform.")
restore.setInput(0, groups)
restore.parm("restorexform").set(1)

cleanup = _place(net.createNode("attribdelete", "cleanup"), 0, -3, "`_*` off every class (conventions.md 2).")
cleanup.setInput(0, restore)
for cls in ("pt", "vtx", "prim", "dtl"):
    cleanup.parm("do%sdel" % cls).set(1)
    cleanup.parm("%sdel" % cls).set("_*")

gcleanup = _place(net.createNode("groupdelete", "gcleanup"), 0, -4, "`_cut` off (conventions.md 5).")
gcleanup.setInput(0, cleanup)
gcleanup.parm("group1").set("_*")

out_null.setInput(0, gcleanup)
out_null.setPosition(hou.Vector2(0, -5))

# --------------------------------------------------------------------------
ptg = hou.ParmTemplateGroup()
ptg.append(_int("count", "Cracks", 12, 0, 500,
                "How many cracks. Each is one lens cut along the grain."))
ptg.append(_float("seed", "Seed", 0.0, 0.0, 1000.0,
                  "Another value, another set of cracks.", minlock=False))
_ga = hou.MenuParmTemplate("grainaxis", "Grain Along", ("x", "y", "z", "longest"),
                           menu_labels=("X", "Y", "Z", "Longest Axis"), default_value=3)
_ga.setHelp("The direction the wood fibres run. Cracks follow it. Longest Axis "
            "is right for a log or a single board.")
ptg.append(_ga)
ptg.append(_float("endbias", "End Bias", 0.5, 0.0, 1.0,
                  "The share of cracks that sit on an end of the wood, so the "
                  "lens runs out through the end grain and the tip gapes. 0 keeps "
                  "every crack in the middle.", maxlock=True))
ptg.append(_float("length", "Length", 0.35, 0.01, 1.0,
                  "Crack length along the grain, as a fraction of the object."))
ptg.append(_float("lengthvar", "Length Variance", 0.4, 0.0, 1.0,
                  "Random +/- share of Length per crack.", maxlock=True))
ptg.append(_float("width", "Width", 0.03, 0.001, 0.3,
                  "How wide a crack opens at the surface, as a fraction of the object."))
ptg.append(_float("widthvar", "Width Variance", 0.4, 0.0, 1.0,
                  "Random +/- share of Width per crack.", maxlock=True))
ptg.append(_float("depth", "Depth", 0.06, 0.005, 0.5,
                  "How deep the crack's floor sits below the surface, as a fraction "
                  "of the object. The walls taper to a knife edge there."))
ptg.append(_float("anglejitter", "Angle Jitter", 6.0, 0.0, 45.0,
                  "Degrees each crack may turn away from the grain."))
adv = hou.FolderParmTemplate("advfolder", "Advanced", folder_type=hou.folderType.Collapsible)
_ma = hou.StringParmTemplate("maskattrib", "Density Attribute", 1, default_value=("",))
_ma.setHelp("Optional float point attribute from upstream (0..1): cracks land "
            "where it is high, none where it is 0. Empty = everywhere. A "
            "painted mask from an Attribute Paint works.")
adv.addParmTemplate(_ma)
adv.addParmTemplate(_int("segments", "Lens Segments", 8, 6, 32,
                         "Points around the lens outline. 8 is the low-poly look; "
                         "more rounds the crack mouth."))
ptg.append(adv)
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
for _p in ("count", "seed", "grainaxis", "endbias", "length", "lengthvar", "width", "widthvar",
           "depth", "anglejitter", "maskattrib", "segments"):
    assert re.search(r'name\s+"%s"' % _p, saved), _p
print("wrote " + HDA_PATH)
