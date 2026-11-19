"""Create `pf_shape_generator` (pf_shape_generator.hda) - port of the Blender add-on "Shape Generator" 1.7.9 (Mark Kingsnorth).

    hython devScripts/create_pf_shape_generator_hda.py

How the Blender tool works and every mapping/decision: ideas/spacetools.md "## Shape generator".

Network (native + VEX; VEX sources devScripts/vex/pf_shapegen_*.vfl, embedded at build):

  generate (detail VEX: every shape of every level, quads, world space) -> bevel -> mirror x/y/z (clip + mirror)
  -> subdivision -> [booleans] -> normals / colour / material -> clean -> OUT

Python appears only in the Preset menu callback (UI marshalling: sets parameter values).
"""
import ast
import json
import os
import re

import hou

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
ROOT = os.path.dirname(HERE)
HDA_PATH = os.path.join(ROOT, "polyfactory", "otls", "pf_shape_generator.hda").replace("\\", "/")
NAME = "pf_shape_generator"
SLIDING = int(os.environ.get("PF_SG_SLIDING", "1"))   # polybevel: 0 auto, 1 always, 2 never
LABEL = "PF Shape Generator"
BLENDER_PRESETS = "F:/cache/shapegen/Shape Generator/sg179/shape_generator/presets"

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


def vex(name):
    return open(f"{HERE}/vex/{name}.vfl", encoding="utf-8").read()


# ---------------------------------------------------------------------------
# parameters. Names = the add-on's property names (so presets map 1:1); rotations are in DEGREES here (radians in Blender).
# ---------------------------------------------------------------------------
DEFAULTS = {
    "random_seed": 1000, "amount": 5, "min_extrude": 0.5, "max_extrude": 1.0, "min_taper": 0.5, "max_taper": 1.0,
    "min_rotation": 0.0, "max_rotation": 20.0, "min_slide": 0.0, "max_slide": 0.1, "favour": (1.0, 1.0, 1.0),
    "prevent_overlap": 1, "overlap_check_limit": 0, "subdivide_edges": 0, "flip_normals": 0,
    "location": (0.0, 0.0, 0.0), "rotation": (0.0, 0.0, 0.0), "scale": (1.0, 1.0, 1.0),
    "random_transform_seed": 12345, "randomize_location": 0, "randomize_rotation": 0, "randomize_scale": 0,
    "start_rand_location": (0.0, 0.0, 0.0), "end_rand_location": (0.0, 0.0, 0.0),
    "start_rand_rotation": (0.0, 0.0, 0.0), "end_rand_rotation": (0.0, 0.0, 0.0),
    "start_rand_scale": (1.0, 1.0, 1.0), "end_rand_scale": (1.0, 1.0, 1.0),
    "mirror_x": 1, "mirror_y": 0, "mirror_z": 0,
    "is_bevel": 0, "bevel_width": 0.1, "bevel_profile": 0.5, "bevel_method": "offset", "bevel_segments": 1,
    "bevel_angle": 30.0,
    "is_subsurf": 0, "subsurf_type": "catmull_clark", "subsurf_subdivisions": 2,
    "shade_smooth": 0, "auto_smooth": 0, "auto_smooth_angle": 30.0,
    "number_to_create": 1,
    "big_shape_num": 1, "medium_shape_num": 0, "small_shape_num": 0,
    "big_random_seed": 0, "medium_random_seed": 1, "small_random_seed": 2,
    "big_random_scatter_seed": 0, "medium_random_scatter_seed": 0, "small_random_scatter_seed": 0,
    "big_shape_scale": 1.0, "medium_shape_scale": 0.5, "small_shape_scale": 0.25,
    "is_boolean": 0, "boolean_main_obj_index": 0, "main_obj_bool_operation": "difference",
    "use_medium_shape_bool": 0, "medium_shape_bool_operation": "difference",
    "use_small_shape_bool": 0, "small_shape_bool_operation": "difference",
    "show_cutters": 0,
    "use_colors": 0, "big_shape_color": (0.0, 0.0, 1.0), "medium_shape_color": (1.0, 1.0, 0.0), "small_shape_color": (1.0, 0.0, 0.0),
    "material_to_use": "", "bms_use_materials": 0, "bms_medium_shape_material": "", "bms_small_shape_material": "",
}
BOOL_OPS = (("intersect", "Intersect"), ("union", "Union"), ("difference", "Difference"))
BEVEL_METHODS = (("offset", "Offset"), ("width", "Width"), ("depth", "Depth"), ("percent", "Percent"))
SUBSURF = (("catmull_clark", "Catmull-Clark"), ("simple", "Simple"))
ROT_KEYS = ("rotation", "start_rand_rotation", "end_rand_rotation")


def parm_templates():
    P = hou

    def F(n, l, lo, hi, h, strict=False, ls=False):
        t = P.FloatParmTemplate(n, l, 1, (float(DEFAULTS[n]),), min=-10.0 if lo is None else lo, max=10.0 if hi is None else hi,
                                min_is_strict=strict and lo is not None, max_is_strict=False)
        t.setHelp(h)
        return t

    def I(n, l, lo, hi, h, strict=True):
        t = P.IntParmTemplate(n, l, 1, (DEFAULTS[n],), min=0 if lo is None else lo, max=10 if hi is None else hi,
                              min_is_strict=strict and lo is not None)
        t.setHelp(h)
        return t

    def T(n, l, h):
        t = P.ToggleParmTemplate(n, l, bool(DEFAULTS[n]))
        t.setHelp(h)
        return t

    def V(n, l, h, lo=None, hi=None, naming=P.parmNamingScheme.XYZW, size=3):
        t = P.FloatParmTemplate(n, l, size, tuple(float(x) for x in DEFAULTS[n]), min=lo if lo is not None else 0.0,
                                max=hi if hi is not None else 10.0, naming_scheme=naming)
        t.setHelp(h)
        return t

    def C(n, l, h):
        t = P.FloatParmTemplate(n, l, 3, tuple(DEFAULTS[n]), look=P.parmLook.ColorSquare, naming_scheme=P.parmNamingScheme.RGBA)
        t.setHelp(h)
        return t

    def M(n, l, items, h):
        t = P.MenuParmTemplate(n, l, tuple(i[0] for i in items), menu_labels=tuple(i[1] for i in items),
                               default_value=[i[0] for i in items].index(DEFAULTS[n]))
        t.setHelp(h)
        return t

    def S(n, l, h, tag=None):
        t = P.StringParmTemplate(n, l, 1, (DEFAULTS[n],))
        if tag:
            t.setTags(tag)
        t.setHelp(h)
        return t

    def when(t, cond, kind=P.parmCondType.DisableWhen):
        t.setConditional(kind, cond)
        return t

    preset = P.MenuParmTemplate("preset", "Preset", ("none",), menu_labels=("(choose a preset)",), default_value=0)
    preset.setHelp("Sets every parameter to one of the Blender add-on's presets (Blocks, Organic, Rifle, Spaceship, Transformer). "
                   "The seed and the look are the add-on's, the random numbers are not (a seed does not give Blender's mesh).")

    shape = P.FolderParmTemplate("f_shape", "Shape", folder_type=P.folderType.Simple)
    for t in (
        I("random_seed", "Seed", 0, 100000, "Changes every random choice of the shape (box size, which faces are extruded, how).", strict=False),
        I("amount", "Extrusions", 0, 100, "How many times a face is extruded. 0 leaves the plain box."),
        F("min_extrude", "Extrude Min", None, None, "Shortest extrusion (also the smallest box side). Negative values dig into the box."),
        F("max_extrude", "Extrude Max", None, None, "Longest extrusion (also the biggest box side)."),
        F("min_taper", "Taper Min", 0.0, 10.0, "Smallest scale of an extruded face (1 = same size, 0.5 = half)."),
        F("max_taper", "Taper Max", 0.0, 10.0, "Biggest scale of an extruded face."),
        F("min_rotation", "Tilt Min", -180.0, 180.0, "Smallest tilt (degrees) of an extruded face about a random axis, hinged at the base of the extrusion."),
        F("max_rotation", "Tilt Max", -180.0, 180.0, "Biggest tilt (degrees)."),
        F("min_slide", "Slide Min", None, None, "Smallest sideways slide of an extruded face."),
        F("max_slide", "Slide Max", None, None, "Biggest sideways slide of an extruded face."),
        V("favour", "Favour", "Which faces are extruded more often: faces looking along an axis with a bigger value are chosen more. "
          "1 1 1 = every face the same; 0.2 1 0.2 grows the shape along Y (spaceship, rifle).", 0.0, 1.0),
        T("prevent_overlap", "Prevent Face Overlaps", "Throw an extrusion away and try again when one of its edges pokes through a face (or the other way round)."),
        I("overlap_check_limit", "Retry Limit", 0, 1000, "How often one extrusion is retried. 0 = the maximum, 1000 (Blender loops forever when no placement exists; "
          "here nothing goes above 1000 so Houdini never hangs)."),
        I("subdivide_edges", "Cut Edges", 0, 10, "Splits every quad into (cuts+1) x (cuts+1) quads before the modifiers (the add-on's Subdivide Edges)."),
        T("flip_normals", "Flip Normals", "Reverses every face."),
    ):
        shape.addParmTemplate(t)

    xf = P.FolderParmTemplate("f_xf", "Transform", folder_type=P.folderType.Simple)
    for t in (
        V("location", "Location", "Moves the finished shape mesh (before the Mirror: the mirror plane stays at the origin).", -100.0, 100.0),
        V("rotation", "Rotation", "Rotates the shape about the origin, degrees, XYZ order.", -360.0, 360.0),
        V("scale", "Scale", "Scales the shape mesh (before bevel and mirror). Spaceship: 1 3.14 1 stretches it along Y.", -10.0, 10.0),
        I("random_transform_seed", "Transform Seed", 0, 100000, "Seed of the random transforms below.", strict=False),
        T("randomize_location", "Randomize Location", "Pick the location of every shape between Start and End."),
        T("randomize_rotation", "Randomize Rotation", "Pick the rotation of every shape between Start and End."),
        T("randomize_scale", "Randomize Scale", "Pick the scale of every shape between Start and End."),
        when(V("start_rand_location", "Start Location", "Lower limit of the random location.", -100.0, 100.0), "{ randomize_location == 0 }"),
        when(V("end_rand_location", "End Location", "Upper limit of the random location.", -100.0, 100.0), "{ randomize_location == 0 }"),
        when(V("start_rand_rotation", "Start Rotation", "Lower limit of the random rotation (degrees).", -360.0, 360.0), "{ randomize_rotation == 0 }"),
        when(V("end_rand_rotation", "End Rotation", "Upper limit of the random rotation (degrees).", -360.0, 360.0), "{ randomize_rotation == 0 }"),
        when(V("start_rand_scale", "Start Scale", "Lower limit of the random scale.", -10.0, 10.0), "{ randomize_scale == 0 }"),
        when(V("end_rand_scale", "End Scale", "Upper limit of the random scale.", -10.0, 10.0), "{ randomize_scale == 0 }"),
    ):
        xf.addParmTemplate(t)

    mods = P.FolderParmTemplate("f_mods", "Modifiers", folder_type=P.folderType.Simple)
    for t in (
        P.LabelParmTemplate("l_mirror", "Mirror", column_labels=("",)),
        T("mirror_x", "Mirror X", "Cut the shape at X = 0, keep the positive side and mirror it (Blender: Mirror modifier with Bisect). The mirror plane goes through the origin for every shape of every level."),
        T("mirror_y", "Mirror Y", "Same along Y."),
        T("mirror_z", "Mirror Z", "Same along Z."),
        P.SeparatorParmTemplate("sep1"),
        T("is_bevel", "Bevel Edges", "Rounds the sharp edges (Blender: Bevel modifier; only edges sharper than the angle below)."),
        when(M("bevel_method", "Width Method", BEVEL_METHODS, "How Width is read. Offset: distance of the new edges from the old edge along the faces. "
              "Width: width of the new face. Depth: distance from the old edge to the new face. Percent: percent of the length of the neighbouring edges."), "{ is_bevel == 0 }"),
        when(F("bevel_width", "Bevel Width", 0.0, 100.0, "Size of the bevel (see Width Method). It is measured on the shape before its set scale, as in Blender: a small shape gets a small bevel.", strict=True), "{ is_bevel == 0 }"),
        when(I("bevel_segments", "Bevel Segments", 1, 20, "Number of segments of the bevel."), "{ is_bevel == 0 }"),
        when(F("bevel_profile", "Bevel Profile", 0.0, 1.0, "0.5 = round. Below 0.5 flattens towards a straight chamfer (0.25 = chamfer and below). "
              "Above 0.5 stays round (Houdini's bevel cannot bulge past a circle)."), "{ is_bevel == 0 }"),
        when(F("bevel_angle", "Bevel Angle Limit", 0.0, 180.0, "Only edges whose faces meet at more than this angle are beveled (Blender's default limit method)."), "{ is_bevel == 0 }"),
        P.SeparatorParmTemplate("sep2"),
        T("is_subsurf", "Subdivision Surface", "Smooths the shape (Blender: Subdivision Surface modifier)."),
        when(M("subsurf_type", "Algorithm", SUBSURF, "Catmull-Clark rounds, Simple only splits the faces."), "{ is_subsurf == 0 }"),
        when(I("subsurf_subdivisions", "Levels", 1, 6, "Number of subdivision levels (4x the faces per level)."), "{ is_subsurf == 0 }"),
    ):
        mods.addParmTemplate(t)

    sets = P.FolderParmTemplate("f_sets", "Big / Medium / Small", folder_type=P.folderType.Simple)
    for t in (
        I("number_to_create", "Shapes Per Set", 1, 1000, "How many shapes one set holds. They all sit at the same place; with Transform randomization they spread out (Transformer presets)."),
        I("big_shape_num", "Big Sets", 1, 100, "Number of big sets. Set 1 is at the origin, the others sit on random surface points of set 1."),
        I("medium_shape_num", "Medium Sets", 0, 1000, "Medium sets scattered over the big shapes (each is a whole new shape, scaled by Medium Scale)."),
        I("small_shape_num", "Small Sets", 0, 1000, "Small sets scattered over the big and medium shapes."),
        F("big_shape_scale", "Big Scale", 0.0, 10.0, "Scale of the big shapes."),
        F("medium_shape_scale", "Medium Scale", 0.0, 10.0, "Scale of the medium shapes."),
        F("small_shape_scale", "Small Scale", 0.0, 10.0, "Scale of the small shapes."),
        I("big_random_seed", "Big Seed", 0, 100000, "Added to Seed for the big shapes.", strict=False),
        I("medium_random_seed", "Medium Seed", 0, 100000, "Added to Seed for the medium shapes.", strict=False),
        I("small_random_seed", "Small Seed", 0, 100000, "Added to Seed for the small shapes.", strict=False),
        I("big_random_scatter_seed", "Big Scatter Seed", 0, 100000, "Where the extra big sets sit.", strict=False),
        I("medium_random_scatter_seed", "Medium Scatter Seed", 0, 100000, "Where the medium shapes sit.", strict=False),
        I("small_random_scatter_seed", "Small Scatter Seed", 0, 100000, "Where the small shapes sit.", strict=False),
    ):
        sets.addParmTemplate(t)

    bools = P.FolderParmTemplate("f_bool", "Booleans", folder_type=P.folderType.Simple)
    for t in (
        T("is_boolean", "Boolean Within A Set", "Combine the shapes of one set: one of them is cut by (or united with, or intersected with) the others. Needs Shapes Per Set above 1."),
        when(I("boolean_main_obj_index", "Main Shape", 0, 1000, "Which shape of the set is the one the others act on."), "{ is_boolean == 0 }"),
        when(M("main_obj_bool_operation", "Operation", BOOL_OPS, "Difference cuts the others out of the main shape; Intersect keeps what all have in common; Union merges."), "{ is_boolean == 0 }"),
        P.SeparatorParmTemplate("sep3"),
        T("use_medium_shape_bool", "Medium Shapes: Apply Boolean", "Use the medium shapes as cutters on the big shapes."),
        when(M("medium_shape_bool_operation", "Medium Operation", BOOL_OPS, "What the medium shapes do to the big shapes."), "{ use_medium_shape_bool == 0 }"),
        T("use_small_shape_bool", "Small Shapes: Apply Boolean", "Use the small shapes as cutters on the big and medium shapes."),
        when(M("small_shape_bool_operation", "Small Operation", BOOL_OPS, "What the small shapes do to the big and medium shapes."), "{ use_small_shape_bool == 0 }"),
        T("show_cutters", "Keep Cutter Shapes", "Keep the shapes that are used as cutters in the output (primitive group pf_cutter); off = only the result."),
    ):
        bools.addParmTemplate(t)

    look = P.FolderParmTemplate("f_look", "Look", folder_type=P.folderType.Simple)
    for t in (
        T("shade_smooth", "Shade Smooth", "Adds smooth point normals N."),
        when(T("auto_smooth", "Auto Smooth", "Keeps edges sharper than the angle below hard."), "{ shade_smooth == 0 }"),
        when(F("auto_smooth_angle", "Auto Smooth Angle", 0.0, 180.0, "Edges sharper than this stay hard."), "{ shade_smooth == 0 } { auto_smooth == 0 }"),
        T("use_colors", "Use Coloring", "Writes Cd per level: big, medium, small."),
        when(C("big_shape_color", "Big Color", "Cd of the big shapes."), "{ use_colors == 0 }"),
        when(C("medium_shape_color", "Medium Color", "Cd of the medium shapes."), "{ use_colors == 0 }"),
        when(C("small_shape_color", "Small Color", "Cd of the small shapes."), "{ use_colors == 0 }"),
        S("material_to_use", "Material", "Material path written to every shape as shop_materialpath.", {"opfilter": "!!SHOP/MATERIAL!!", "oprelative": "/"}),
        T("bms_use_materials", "Separate Materials", "Medium and small shapes get their own materials."),
        when(S("bms_medium_shape_material", "Medium Material", "Material of the medium shapes.", {"opfilter": "!!SHOP/MATERIAL!!", "oprelative": "/"}), "{ bms_use_materials == 0 }"),
        when(S("bms_small_shape_material", "Small Material", "Material of the small shapes.", {"opfilter": "!!SHOP/MATERIAL!!", "oprelative": "/"}), "{ bms_use_materials == 0 }"),
    ):
        look.addParmTemplate(t)

    tabs = P.FolderParmTemplate("tabs", "Tabs", folder_type=P.folderType.Tabs)
    for f in (shape, xf, mods, sets, bools, look):
        tabs.addParmTemplate(f)
    ptg = P.ParmTemplateGroup()
    ptg.append(preset)
    ptg.append(tabs)
    return ptg


# ---------------------------------------------------------------------------
# presets: the add-on's python preset files ("op.name = value")
# ---------------------------------------------------------------------------
BOOL_TOKEN = {"INTERSECT": "intersect", "UNION": "union", "DIFFERENCE": "difference"}
BEVEL_TOKEN = {"OFFSET": "offset", "WIDTH": "width", "DEPTH": "depth", "PERCENT": "percent"}
SUBSURF_TOKEN = {"CATMULL_CLARK": "catmull_clark", "SIMPLE": "simple"}


def preset_data():
    out = {}
    if not os.path.isdir(BLENDER_PRESETS):
        return out
    rename = {"prevent_ovelapping_faces": "prevent_overlap", "favour_vec": "favour"}
    for fn in sorted(os.listdir(BLENDER_PRESETS)):
        if not fn.endswith(".py"):
            continue
        vals = {}
        for line in open(f"{BLENDER_PRESETS}/{fn}", encoding="utf-8"):
            m = re.match(r"op\.(\w+)\s*=\s*(.+)$", line.strip())
            if not m:
                continue
            k, v = m.group(1), ast.literal_eval(m.group(2))
            k = rename.get(k, k)
            if k not in DEFAULTS:
                continue
            if k in ROT_KEYS:
                v = tuple(round(x * 180.0 / 3.141592653589793, 4) + 0.0 for x in v)
            elif k.endswith("_color"):
                v = tuple(v[:3])
            elif k in ("bevel_method",):
                v = BEVEL_TOKEN[v]
            elif k == "subsurf_type":
                v = SUBSURF_TOKEN[v]
            elif k.endswith("bool_operation"):
                v = BOOL_TOKEN[v]
            elif isinstance(v, bool):
                v = int(v)
            elif isinstance(v, tuple):
                v = tuple(round(x, 5) for x in v)
            elif isinstance(v, float):
                v = round(v, 6)
            vals[k] = v
        key = os.path.splitext(fn)[0]
        out[key] = {"label": key.replace("_", " ").title(), "values": vals}
    return out


PRESET_CALLBACK = r'''
import json
node = kwargs["node"]
data = json.loads(node.type().definition().sections()["presets.json"].contents())
key = kwargs["script_value"] if "script_value" in kwargs else node.parm("preset").evalAsString()
p = data["presets"].get(key)
if p:
    vals = dict(data["defaults"]); vals.update(p["values"])
    for k, v in vals.items():
        if isinstance(v, list):
            t = node.parmTuple(k)
            if t is not None:
                t.set(v)
        else:
            parm = node.parm(k)
            if parm is not None:
                parm.set(v)
'''


def build():
    if hou.isUIAvailable() is False:
        hou.hipFile.clear(suppress_save_prompt=True)
    if os.path.exists(HDA_PATH):
        os.remove(HDA_PATH)
    build_geo = hou.node("/obj").createNode("geo", "_build_" + NAME)
    subnet = build_geo.createNode("subnet", NAME)
    hda = subnet.createDigitalAsset(name=NAME, hda_file_name=HDA_PATH, description=LABEL,
                                    min_num_inputs=0, max_num_inputs=0, version="1.0")
    hda.allowEditingOfContents()
    defn = hda.type().definition()
    defn.setIcon("SOP_polyextrude")
    defn.setParmTemplateGroup(parm_templates())      # before the network: expressions need the parms
    for c in list(hda.children()):
        c.destroy()

    def node(t, n, *inputs, **parms):
        nd = hda.createNode(t, n)
        for i, src in enumerate(inputs):
            if src is not None:
                nd.setInput(i, src)
        for k, v in parms.items():
            if isinstance(v, str) and v.startswith("ch("):
                nd.parm(k).setExpression(v)
            else:
                nd.parm(k).set(v)
        return nd

    def wr(n, src, code, cls, group=""):
        w = node("attribwrangle", n, src)
        w.parm("class").set(cls)
        w.parm("snippet").set(code)
        w.parm("group").set(group)
        return w

    def sw(n, off, on, expr):
        s = node("switch", n, off, on)
        s.parm("input").setExpression(expr)
        return s

    gen = wr("generate", None, vex("pf_shapegen_generate"), 0)

    # ---- bevel ---------------------------------------------------------
    be = wr("bevel_edges", gen, vex("pf_shapegen_bevel"), 0)
    bev = node("polybevel::3.0", "bevel", be, grouptype=2, group="_bev", filletshape=4, offset=1.0, useoffsetscale=1, sliding=SLIDING,
               pointscaleattr="_bw")
    bev.parm("divisions").setExpression("ch('../bevel_segments')")
    bev.parm("convexity").setExpression("clamp((ch('../bevel_profile') - 0.25) / 0.25, 0, 1)")
    bev.parm("limit").set(1)      # individually: Blender's "Clamp Overlap" off lets bevels overlap; Houdini's "never" runs away on thin shapes (measured)
    cur = sw("bevel_on", be, bev, "ch('../is_bevel') && detail('../bevel_edges', '_nbev', 0) > 0")

    # ---- mirror: cut at the plane, keep the positive side, mirror it (Blender: Mirror with Bisect) ------
    for ax, d in (("x", (1, 0, 0)), ("y", (0, 1, 0)), ("z", (0, 0, 1))):
        clip = node("clip::2.0", "clip_" + ax, cur, clipop=0, dirx=d[0], diry=d[1], dirz=d[2], snaptol=1e-5)
        mir = node("mirror", "mirror_" + ax, clip, dirx=d[0], diry=d[1], dirz=d[2], consolidatetol=0.001)
        cur = sw("mirror_%s_on" % ax, cur, mir, "ch('../mirror_%s')" % ax)

    # ---- subdivision surface -------------------------------------------
    sub = node("subdivide", "subdivide", cur, algorithm=2, vtxboundary=2)
    sub.parm("iterations").setExpression("ch('../subsurf_subdivisions')")
    sub.parm("algorithm").setExpression("2 + 2 * ch('../subsurf_type')")      # menu: catmull_clark 0 -> osdcc (2), simple 1 -> osdbilinear (4)
    cur = sw("subsurf_on", cur, sub, "ch('../is_subsurf')")

    # ---- booleans: ONE feedback loop over an operation list (vex/pf_shapegen_ops.vfl), in the add-on's modifier order ----------
    cur = node("attribdelete", "drop_bevel_attrs", cur, doptdel=1, ptdel="_os _bw")      # the boolean has no use for them and would not carry them
    cutmark = wr("cutmark", cur,
                 'int nc = chi("../number_to_create"); int mi = chi("../boolean_main_obj_index"); if (mi >= nc) mi = 0;\n'
                 'int lv = i@pf_level; int hid = 0;\n'
                 'if (chi("../is_boolean") && nc > 1 && i@pf_shape != mi) hid = 1;      // operands of a set boolean\n'
                 'if (lv == 1 && chi("../use_medium_shape_bool")) hid = 1;\n'
                 'if (lv == 2 && chi("../use_small_shape_bool")) hid = 1;\n'
                 'i@_cut = hid;\n', 1)
    empty = node("null", "empty_geo")
    ops = wr("ops", empty, vex("pf_shapegen_ops"), 0)
    ops.setInput(1, cutmark)
    fb = node("block_begin", "bool_fb", cutmark, method=0)
    pc = node("block_begin", "bool_pc", ops, method=1)
    opinfo = wr("opinfo", pc,
                'foreach (string a; {"t", "o", "op", "tlevel", "tset", "tsetid", "tshape", "tcut"}) {\n'
                '    int v = point(0, a, 0); setdetailattrib(0, a, v, "set");\n'
                '}\n', 0)
    mark = wr("bool_mark", fb,
              'int t = detail(1, "t", 0), o = detail(1, "o", 0);\n'
              'setprimgroup(0, "_t", @primnum, i@pf_obj == t, "set");\n'
              'setprimgroup(0, "_o", @primnum, i@pf_obj == o, "set");\n', 1)
    mark.setInput(1, opinfo)
    targ = node("blast", "bool_target", mark, group="_t", grouptype=4, negate=1)
    oper = node("blast", "bool_operand", mark, group="_o", grouptype=4, negate=1)
    rest = node("blast", "bool_rest", mark, group="_t", grouptype=4, negate=0)
    boo = node("boolean::2.0", "bool_op", targ, oper)
    boo.parm("booleanop").setExpression("detail('../opinfo', 'op', 0)")
    keep = sw("bool_keep", targ, empty, "detail('../opinfo', 'op', 0) == 1")     # no operand left: intersect -> nothing, else the target as is
    res = sw("bool_have_both", keep, boo, "npoints('../bool_target') > 0 && npoints('../bool_operand') > 0")
    retag = wr("bool_retag", res,
               'i@pf_obj = detail(1, "t", 0); i@pf_level = detail(1, "tlevel", 0); i@pf_set = detail(1, "tset", 0);\n'
               'i@pf_setid = detail(1, "tsetid", 0); i@pf_shape = detail(1, "tshape", 0); i@_cut = detail(1, "tcut", 0);\n', 1)
    retag.setInput(1, opinfo)
    mrg = node("merge", "bool_merge", rest, retag)
    bend = node("block_end", "bool_end", mrg, itermethod=1, method=0, useattrib=1, attrib="_it")
    bend.parm("class").set(1)
    fb.parm("blockpath").set("../bool_end")
    pc.parm("blockpath").set("../bool_end")
    bend.parm("blockpath").set("../bool_fb")
    bend.parm("templatepath").set("../bool_pc")
    boolcur = sw("booleans_on", cutmark, bend, "detail('../ops', '_nops', 0) > 0")
    cg = wr("cutter_group", boolcur,
            'setprimgroup(0, "pf_cutter", @primnum, i@_cut, "set"); setdetailattrib(0, "_ncut", i@_cut, "add");\n', 1)
    drop = node("blast", "drop_cutters", cg, group="pf_cutter", grouptype=4, negate=0)
    cur = sw("cutters_off", cg, drop, "!ch('../show_cutters') && detail('../cutter_group', '_ncut', 0) > 0")

    # ---- groups, colour, material, normals ---------------------------------
    fin = wr("finalize", cur,
             'int lv = i@pf_level;\n'
             'setprimgroup(0, "pf_big", @primnum, lv == 0, "set");\n'
             'setprimgroup(0, "pf_medium", @primnum, lv == 1, "set");\n'
             'setprimgroup(0, "pf_small", @primnum, lv == 2, "set");\n'
             'if (chi("../use_colors")) {\n'
             '    vector c = lv == 0 ? chv("../big_shape_color") : lv == 1 ? chv("../medium_shape_color") : chv("../small_shape_color");\n'
             '    v@Cd = c;\n'
             '}\n'
             'string mat = chs("../material_to_use");\n'
             'if (chi("../bms_use_materials")) { if (lv == 1) mat = chs("../bms_medium_shape_material"); else if (lv == 2) mat = chs("../bms_small_shape_material"); }\n'
             'if (mat != "") s@shop_materialpath = mat;\n', 1)
    nrm = node("normal", "smooth_normals", fin, type=0)
    nrm.parm("cuspangle").setExpression("ch('../auto_smooth') * ch('../auto_smooth_angle') + (1 - ch('../auto_smooth')) * 180")
    cur = sw("smooth_on", fin, nrm, "ch('../shade_smooth')")

    # ---- clean: no _* attribute or group leaves ----------------------------
    for cname, cls, flag in (("pt", 2, "doptdel"), ("vtx", 3, "dovtxdel"), ("prim", 1, "doprimdel"), ("dtl", 0, "dodtldel")):
        gd = wr("guard_" + cname, cur, "i@_g = 0;", cls)
        cur = node("attribdelete", "clean_" + cname, gd,
                   **{flag: 1, {"doptdel": "ptdel", "dovtxdel": "vtxdel", "doprimdel": "primdel", "dodtldel": "dtldel"}[flag]: "_*"})
    gguard = wr("gguard", cur, 'if (nprimitives(0) > 0) setprimgroup(0, "_g", 0, 0, "set"); if (npoints(0) > 0) setpointgroup(0, "_g", 0, 0, "set");', 0)
    gclean = node("groupdelete", "clean_groups", gguard)
    gclean.parm("deletions").set(1)
    gclean.parm("group1").set("_*")
    out = node("null", "OUT", gclean)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)
    hda.layoutChildren()

    pd = {"defaults": {k: (list(v) if isinstance(v, tuple) else v) for k, v in DEFAULTS.items()},
          "presets": {k: {"label": v["label"], "values": {a: (list(b) if isinstance(b, tuple) else b) for a, b in v["values"].items()}}
                      for k, v in preset_data().items()}}
    defn.addSection("presets.json", json.dumps(pd))
    ptg = defn.parmTemplateGroup()
    pm = ptg.find("preset")
    items = ["none"] + list(pd["presets"].keys())
    labels = ["(choose a preset)"] + [pd["presets"][k]["label"] for k in pd["presets"]]
    pm2 = hou.MenuParmTemplate("preset", "Preset", tuple(items), menu_labels=tuple(labels), default_value=0)
    pm2.setHelp(pm.help())
    pm2.setScriptCallback(PRESET_CALLBACK)
    pm2.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    ptg.replace("preset", pm2)
    defn.setParmTemplateGroup(ptg)

    defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
    opts = defn.options()
    opts.setUnlockNewInstances(False)
    defn.setOptions(opts)
    defn.save(HDA_PATH, template_node=hda)
    d = hou.hda.definitionsInFile(HDA_PATH)[0]
    d.addSection("Tools.shelf", TOOLS_SHELF)
    hda.destroy()
    build_geo.destroy()
    print("wrote " + HDA_PATH)


build()
