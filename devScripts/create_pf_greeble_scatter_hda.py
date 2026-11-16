"""Create `pf_greeble_scatter` (pf::greeble_scatter) - spacetools tool #2b.

    hython devScripts/create_pf_greeble_scatter_hda.py

Recreates the greeble half of the Blender add-on "Plating Generator and Greebles 2.0":
scatter kit pieces (greebles) onto the quad faces of a surface - overlapping (random rectangles) or
non-overlapping (recursively split cells, one greeble per cell, coverage %).  Details and the
mapping: ideas/spacetools.md "## Plating + greebles".

Inputs: 1 surface (quads are used; use the pf_plating_generator groups pf_plate_top / pf_plate_side),
2 optional kit (pieces = islands, or prim attr pf_kit; Z up, footprint in XY).
The Blender kits (Defaults, Hull Details, Panels, Custom Greebles; 34 pieces, exported from the add-on's
libraries by devScripts/../greeble_export step) are embedded in the HDA as section kit_blender.bgeo.sc.

Network: native + VEX only. Python only in the Preset menu callback (sets parameter values).
"""
import glob
import json
import os

import hou

_PF = os.environ.get("POLYFACTORY", "F:/projects/polyfactory-spacetools/polyfactory")
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
HDA_PATH = os.path.join(_PF, "otls", "pf_greeble_scatter.hda").replace("\\", "/")
NAME = "pf_greeble_scatter"
LABEL = "PF Greeble Scatter"
KIT_OBJ = "F:/cache/spacetools/greeble_kit"
BLENDER_PRESETS = "F:/cache/spacetools/plating/plating_greeble_gen/presets/panel"
SECTION = "kit_blender.bgeo.sc"
TMP = "F:/cache/spacetools/plating_work/kit_blender.bgeo.sc"

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

DEFAULTS = {
    "group": "", "kit": "defaults", "placement": "non_overlapping", "amount": 100, "coverage": 50.0,
    "subd_levels": 1, "deviation": 0.5, "seed": 1, "rotation_seed": 1,
    "width_min": 0.2, "width_max": 0.8, "length_min": 0.2, "length_max": 0.8,
    "height_min": 0.0, "height_max": 0.1, "keep_aspect": 1, "override_height": 0, "height_override": 0.1,
    "custom_normal": 0, "normal_direction": (0.0, 0.0, 1.0), "fixed_rotation": 0, "rotation_steps": 0,
    "keep_surface": 1, "random_color": 0,
}
KITS = [("defaults", "Simple Shapes (6)"), ("hull", "Hull Details (16)"), ("panels", "Panels (6)"),
        ("custom", "Custom Greebles (6)"), ("all", "All Blender Greebles (34)"), ("input", "Input 2 (your kit)")]
PLACEMENTS = [("non_overlapping", "Non-Overlapping (grid of cells)"), ("overlapping", "Overlapping (random)")]


def vex(name):
    return open(f"{HERE}/vex/{name}.vfl", encoding="utf-8").read()


def build_kit():
    """All exported Blender greebles in one geometry: prim attrs pf_kit_set / pf_kit_name / pf_kit."""
    geo = hou.Geometry()
    geo.addAttrib(hou.attribType.Prim, "pf_kit", 0)
    geo.addAttrib(hou.attribType.Prim, "pf_kit_set", "")
    geo.addAttrib(hou.attribType.Prim, "pf_kit_name", "")
    idx = 0
    counts = {}
    for d in sorted(glob.glob(KIT_OBJ + "/*")):
        sset = {"Defaults": "defaults", "Hull_Details": "hull", "Panels": "panels", "Custom_Greebles": "custom"}[os.path.basename(d)]
        for f in sorted(glob.glob(d + "/*.obj")):
            verts, faces = [], []
            for line in open(f):
                t = line.split()
                if t and t[0] == "v":
                    verts.append(tuple(float(x) for x in t[1:4]))
                elif t and t[0] == "f":
                    faces.append([int(x.split("/")[0]) - 1 for x in t[1:]])
            pts = [geo.createPoint() for _ in verts]
            for p, v in zip(pts, verts):
                p.setPosition(v)
            for fc in faces:
                pr = geo.createPolygon()
                for i in fc:
                    pr.addVertex(pts[i])
                pr.setAttribValue("pf_kit", idx)
                pr.setAttribValue("pf_kit_set", sset)
                pr.setAttribValue("pf_kit_name", os.path.splitext(os.path.basename(f))[0])
            idx += 1
            counts[sset] = counts.get(sset, 0) + 1
    geo.saveToFile(TMP)
    return counts


def parm_templates():
    P = hou
    def F(n, l, lo, hi, h, strict=False):
        t = P.FloatParmTemplate(n, l, 1, (DEFAULTS[n],), min=lo, max=hi, min_is_strict=strict); t.setHelp(h); return t
    def I(n, l, lo, hi, h, strict=True):
        t = P.IntParmTemplate(n, l, 1, (DEFAULTS[n],), min=lo, max=hi, min_is_strict=strict); t.setHelp(h); return t
    def T(n, l, h):
        t = P.ToggleParmTemplate(n, l, bool(DEFAULTS[n])); t.setHelp(h); return t
    def M(n, l, items, h):
        t = P.MenuParmTemplate(n, l, tuple(i[0] for i in items), menu_labels=tuple(i[1] for i in items),
                               default_value=[i[0] for i in items].index(DEFAULTS[n])); t.setHelp(h); return t
    grp = P.StringParmTemplate("group", "Faces To Use", 1, ("",))
    grp.setHelp("Faces that get greebles (blank = all). Only four-sided faces are used. "
                "Try pf_plate_top for greebles on plates, pf_plate_side for greebles along the plate edges.")
    preset = P.MenuParmTemplate("preset", "Preset", ("none",), menu_labels=("(choose a preset)",))
    top = [preset, grp,
           M("kit", "Greeble Kit", KITS, "Which shapes are scattered. Input 2 uses your own geometry: each separate piece (or prim attribute pf_kit) is one greeble, Z up, footprint in XY."),
           M("placement", "Placement", PLACEMENTS, "Non-overlapping splits every face into cells and puts at most one greeble in each, so none can touch. Overlapping drops the given number of greebles at random and they may cross.")]
    place = P.FolderParmTemplate("f_place", "Placement", folder_type=P.folderType.Simple)
    for t in (
        I("amount", "Greeble Count", 0, 100000, "Overlapping: how many greebles in total."),
        F("coverage", "Coverage %", 0, 100, "Non-overlapping: chance that a cell gets a greeble."),
        I("subd_levels", "Cell Levels", 0, 3, "Non-overlapping: each level splits every cell into 4 (4^level cells per face)."),
        F("deviation", "Cell Irregularity", 0, 1, "Non-overlapping: how far from the middle the cuts may land."),
        I("seed", "Seed", 0, 100000, "Changes where greebles go and which kind.", strict=False),
        I("rotation_seed", "Rotation Seed", 0, 100000, "Changes the turn of each greeble.", strict=False),
    ):
        place.addParmTemplate(t)
    size = P.FolderParmTemplate("f_size", "Size", folder_type=P.folderType.Simple)
    for t in (
        F("width_min", "Width Min", 0, 1, "Share of the face/cell width a greeble covers."),
        F("width_max", "Width Max", 0, 1, "Share of the face/cell width a greeble covers."),
        F("length_min", "Length Min", 0, 1, "Share of the face/cell length."),
        F("length_max", "Length Max", 0, 1, "Share of the face/cell length."),
        T("keep_aspect", "Keep Shape Proportions", "On: a greeble keeps its original proportions (height follows from its footprint). Off: it is stretched to the footprint and the height range below is used."),
        F("height_min", "Height Min", 0, 10, "Used when proportions are not kept."),
        F("height_max", "Height Max", 0, 10, "Used when proportions are not kept."),
        T("override_height", "Fixed Height", "Use one height for every greeble."),
        F("height_override", "Height", 0, 10, "The fixed height."),
    ):
        size.addParmTemplate(t)
    orient = P.FolderParmTemplate("f_orient", "Orientation", folder_type=P.folderType.Simple)
    nd = P.FloatParmTemplate("normal_direction", "Up Direction", 3, (0.0, 0.0, 1.0)); nd.setHelp("Direction greebles point in when 'Use Up Direction' is on.")
    for t in (
        T("custom_normal", "Use Up Direction", "All greebles point the same way instead of along their face."),
        nd,
        T("fixed_rotation", "Fixed Rotation", "Every greeble is turned by the same number of quarter turns instead of randomly."),
        I("rotation_steps", "Quarter Turns", 0, 3, "Fixed rotation amount."),
    ):
        orient.addParmTemplate(t)
    out = P.FolderParmTemplate("f_out", "Output", folder_type=P.folderType.Simple)
    for t in (T("keep_surface", "Keep Surface", "Output the surface together with the greebles."),
              T("random_color", "Random Greeble Color", "Writes a random Cd per greeble.")):
        out.addParmTemplate(t)
    tabs = P.FolderParmTemplate("tabs", "Tabs", folder_type=P.folderType.Tabs)
    for f in (place, size, orient, out):
        tabs.addParmTemplate(f)
    ptg = P.ParmTemplateGroup()
    for t in top:
        ptg.append(t)
    ptg.append(tabs)
    return ptg


def preset_data():
    out = {}
    if os.path.isdir(BLENDER_PRESETS):
        for fn in ("11. Greebles (Overlapping).json", "12. Greebles (Non Overlapping).json",
                   "13. Greebles on Plates.json", "14. Greebles on Plate Edges.json", "10. City Block.json"):
            d = json.load(open(f"{BLENDER_PRESETS}/{fn}"))
            lvl = d["levels"][-1]["greeble_props"]
            key = fn.split(". ", 1)[1].rsplit(".", 1)[0].replace(" ", "_").replace("(", "").replace(")", "")
            v = {
                "placement": "overlapping" if lvl["greeble_pattern_type"] == "0" else "non_overlapping",
                "amount": lvl["greeble_amount"], "coverage": lvl["coverage_amount"],
                "subd_levels": lvl["greeble_subd_levels"], "deviation": lvl["greeble_deviation"],
                "width_min": lvl["greeble_min_width"], "width_max": lvl["greeble_max_width"],
                "length_min": lvl["greeble_min_length"], "length_max": lvl["greeble_max_length"],
                "height_min": lvl["greeble_min_height"], "height_max": lvl["greeble_max_height"],
                "keep_aspect": int(lvl["all_keep_aspect_ratio"]), "random_color": int(lvl["add_vertex_colors_to_greebles"]),
            }
            note = "  (greeble level of the Blender preset)"
            if fn.startswith(("13", "14", "10")):
                note += " - set Faces To Use to pf_plate_top" if not fn.startswith("14") else " - set Faces To Use to pf_plate_side"
            out[key] = {"label": fn.split(". ", 1)[1].rsplit(".", 1)[0] + note, "values": v}
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
        if k == "group":
            continue
        parm = node.parm(k)
        if parm is not None:
            parm.set(v)
'''


def build():
    if hou.isUIAvailable() is False:
        hou.hipFile.clear(suppress_save_prompt=True)
    counts = build_kit()
    print("kit pieces", counts)
    if os.path.exists(HDA_PATH):
        os.remove(HDA_PATH)
    build_geo = hou.node("/obj").createNode("geo", "_build_" + NAME)
    subnet = build_geo.createNode("subnet", NAME)
    hda = subnet.createDigitalAsset(name=NAME, hda_file_name=HDA_PATH, description=LABEL,
                                    min_num_inputs=1, max_num_inputs=2, version="1.0")
    hda.allowEditingOfContents()
    defn = hda.type().definition()
    defn.setIcon("SOP_copytopoints")
    defn.setMaxNumInputs(2)
    for c in list(hda.children()):
        c.destroy()
    defn.addSection(SECTION, open(TMP, "rb").read())

    def node(t, n, *inputs, **parms):
        nd = hda.createNode(t, n)
        for i, src in enumerate(inputs):
            if src is not None:
                nd.setInput(i, src)
        for k, v in parms.items():
            nd.parm(k).set(v)
        return nd

    def wr(n, src, code, cls, group=""):
        w = node("attribwrangle", n, src)
        w.parm("class").set(cls)
        w.parm("snippet").set(code)
        w.parm("group").set(group)
        return w

    surf_in = hda.indirectInputs()[0]
    kit_in = hda.indirectInputs()[1]
    dfl = wr("defaults", surf_in, "i@_sel = 0; i@_k = -1; i@_island = 0; i@pf_kit = -1; i@pf_greeble_id = -1; i@pf_host = -1; s@pf_kit_name = \"\";", 1)
    dpt = wr("defaults_pt", dfl, 'i@pf_kit = -1; i@pf_greeble_id = -1; i@pf_host = -1; v@scale = {1,1,1}; p@orient = {0,0,0,1}; if (@ptnum == 0) setpointgroup(0, "_gpt", 0, 0, "set");', 2)
    sel = wr("mark_faces", dpt, "i@_sel = 1;", 1, group="`chs('../group')`")
    # kit: embedded library (filtered by set) or input 2
    lib = node("file", "kit_library", file="opdef:..?" + SECTION)
    filt = wr("kit_filter", lib, 'string k = chs("../kit"); if (k != "all" && s@pf_kit_set != k) removeprim(0, @primnum, 1);', 1)
    conn = node("connectivity", "kit_islands", kit_in, connecttype=0, attribname="_island")
    connp = node("attribdelete", "kit_island_pt", conn, doptdel=1, ptdel="_island")
    conn2 = wr("kit_tag", connp, 's@pf_kit_set = ""; s@pf_kit_name = "";', 1)
    swk = node("switch", "kit_source", filt, conn2)
    swk.parm("input").setExpression("strcmp(chs('../kit'), 'input') == 0")
    prep = wr("kit_normalise", swk, vex("pf_greeble_kitprep"), 0)
    place = hda.createNode("attribwrangle", "place")
    place.setInput(0, sel); place.setInput(1, prep)
    place.parm("class").set(0); place.parm("snippet").set(vex("pf_greeble_place"))
    targets = node("blast", "targets", place, group="_gpt", grouptype=3, negate=1)
    surf0 = node("blast", "surface_only", place, group="_gpt", grouptype=3, negate=0)
    surf = node("attribdelete", "surface_clean", surf0, doptdel=1, ptdel="orient scale pf_kit pf_greeble_id pf_host")
    cp = node("copytopoints::2.0", "greebles", prep, targets, useidattrib=1, idattrib="pf_kit", targetattribs=1)
    cp.parm("applyto1").set(2); cp.parm("applyattribs1").set("pf_greeble_id pf_host")
    post = hda.createNode("attribwrangle", "greeble_attrs")
    post.setInput(0, cp); post.setInput(1, surf)
    post.parm("class").set(1)
    post.parm("snippet").set(
        'int host = i@pf_host;\n'
        'if (hasattrib(1, "prim", "pf_plate_id"))     { int v = prim(1, "pf_plate_id", host);        setprimattrib(0, "pf_plate_id", @primnum, v, "set"); }\n'
        'if (hasattrib(1, "prim", "pf_plate_area"))   { float v = prim(1, "pf_plate_area", host);    setprimattrib(0, "pf_plate_area", @primnum, v, "set"); }\n'
        'if (hasattrib(1, "prim", "pf_plate_height")) { float v = prim(1, "pf_plate_height", host);  setprimattrib(0, "pf_plate_height", @primnum, v, "set"); }\n'
        'if (hasattrib(1, "prim", "Cd"))              { vector v = prim(1, "Cd", host);              setprimattrib(0, "Cd", @primnum, v, "set"); }\n'
        'i@_sel = 0; i@_island = 0;\n'
        'setprimgroup(0, "pf_greeble", @primnum, 1, "set");\n')
    col = wr("greeble_color", post, 'float k = float(i@pf_greeble_id) * 0.37 + float(chi("../seed")) * 1.7; float cr = rand(k); float cg = rand(k + 7.31); float cb = rand(k + 13.7); v@Cd = set(cr, cg, cb) * 0.8 + 0.2;', 1)
    swc = node("switch", "color_on", post, col)
    swc.parm("input").setExpression("ch('../random_color')")
    gdone0 = node("attribdelete", "greeble_drop_kit_set", swc, doprimdel=1, primdel="pf_kit_set")
    gdone = gdone0
    surfcd = wr("surface_cd", surf, 'if (!hasattrib(0, "prim", "Cd")) v@Cd = {0.7, 0.7, 0.75};', 1)
    surfcd_sw = node("switch", "surface_cd_on", surf, surfcd)
    surfcd_sw.parm("input").setExpression("ch('../random_color')")
    mrg = node("merge", "merge", surfcd_sw, gdone)
    swm = node("switch", "keep_surface", gdone, mrg)
    swm.parm("input").setExpression("ch('../keep_surface')")
    cur = swm
    for cname, cls, flag in (("pt", 2, "doptdel"), ("vtx", 3, "dovtxdel"), ("prim", 1, "doprimdel"), ("dtl", 0, "dodtldel")):
        gd = wr("guard_" + cname, cur, "i@_g = 0;", cls)
        cur = node("attribdelete", "clean_" + cname, gd, **{flag: 1, {"doptdel": "ptdel", "dovtxdel": "vtxdel", "doprimdel": "primdel", "dodtldel": "dtldel"}[flag]: "_*"})
    gguard = wr("gguard", cur, 'if (nprimitives(0) > 0) setprimgroup(0, "_g", 0, 0, "set"); if (npoints(0) > 0) setpointgroup(0, "_g", 0, 0, "set");', 0)
    gclean = node("groupdelete", "clean_groups", gguard, deletions=1, group1="_*", grouptype1=0)
    out = node("null", "OUT", gclean)
    out.setDisplayFlag(True); out.setRenderFlag(True)
    hda.layoutChildren()

    defn.setParmTemplateGroup(parm_templates())
    pd = {"defaults": {k: v for k, v in DEFAULTS.items() if k not in ("normal_direction",)}, "presets": preset_data()}
    defn.addSection("presets.json", json.dumps(pd))
    ptg = defn.parmTemplateGroup()
    pm = ptg.find("preset")
    items = ["none"] + list(pd["presets"].keys())
    labels = ["(choose a preset)"] + [pd["presets"][k]["label"] for k in pd["presets"]]
    pm2 = hou.MenuParmTemplate("preset", "Preset", tuple(items), menu_labels=tuple(labels), default_value=0)
    pm2.setHelp("Sets the parameters to one of the Blender add-on's greeble presets.")
    pm2.setScriptCallback(PRESET_CALLBACK)
    pm2.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    ptg.replace("preset", pm2)
    defn.setParmTemplateGroup(ptg)

    hda.setUserData("nodeshape", "chevron_down")
    defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
    opts = defn.options(); opts.setUnlockNewInstances(False); defn.setOptions(opts)
    defn.save(HDA_PATH, template_node=hda)
    d = hou.hda.definitionsInFile(HDA_PATH)[0]
    d.addSection("Tools.shelf", TOOLS_SHELF)
    hda.destroy(); build_geo.destroy()
    print("wrote " + HDA_PATH)


build()
