"""Create `pf_plating_preset` (pf::plating_preset) - spacetools tool #2c.

    hython devScripts/create_pf_plating_preset_hda.py

One node = the Blender "Plating Generator and Greebles" preset menu, complete: all levels of a preset
(plating -> plating -> greeble ...) are chained inside, reusing pf_plating_generator and pf_greeble_scatter.
Fixed network of 10 level slots (switch source -> select faces -> blast -> plating/greeble -> visibility);
the Levels multiparm (count + per-level values) drives the slots, so after picking a preset every
value can be tweaked, levels added (max 10) or removed.  Mapping and decisions: ideas/spacetools.md
"## Plating + greebles".  Needs pf_plating_generator.hda and pf_greeble_scatter.hda built first.
Python only in the Preset menu callback (sets parameter values from section presets.json).
"""
import glob
import json
import os
import re

import hou

_PF = os.environ.get("POLYFACTORY", "F:/projects/polyfactory-spacetools/polyfactory")
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
HDA_PATH = os.path.join(_PF, "otls", "pf_plating_preset.hda").replace("\\", "/")
NAME = "pf_plating_preset"
LABEL = "PF Plating Preset"
BLENDER_PRESETS = "F:/cache/spacetools/plating/plating_greeble_gen/presets/panel"
MAXL = 10
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
HELP = """= PF Plating Preset =

#type: node
#context: sop
#internal: pf_plating_preset
#icon: SOP/polyextrude

\"\"\"Spaceship plating and greebles in one node: pick a Blender preset and get all its levels (big / medium / small plates, greebles on plates or plate edges).\"\"\"

Pick a *Preset*. The node fills the *Levels* list and builds the finished result from your surface.
Each level is either a plating pass (*PF Plating Generator*) or a greeble pass (*PF Greeble Scatter*) on
the surface, or on the plate tops / plate edges of an earlier level. Every value can be tweaked afterwards;
levels can be added (up to 10) or removed.

@parameters
    Preset:
        #id: preset
        A Blender preset (1-19) or a greeble-only preset. Overwrites the Levels list.
    Selection Seed:
        #id: sel_seed
        Which plates a level takes when it only uses a share of them.
    Levels:
        #id: levels
        One entry per level. *Source Level* 0 = your input surface, n = the result of level n.
        *Take From / To %* = the slice of the source plates this level works on (a level that takes the
        remaining plates starts where the previous one ended).

@inputs
    Surface:
        The surface to plate (quads work best).
"""


def jload(p):
    return json.load(open(p, encoding="utf-8"))


def sec(t):
    return json.loads(hou.nodeType(hou.sopNodeTypeCategory(), t).definition().sections()["presets.json"].contents())


PM = {"0": "crisscross", "2": "triangles", "6": "irregular", "3": "rectangles", "4": "rectangles_cuts"}
MP = [("amount", "amount"), ("triangle_percentage", "triangle_amount"), ("ruby_dragon_percentage", "irregular_amount"),
      ("groove_width", "groove_width"), ("groove_depth", "groove_depth"), ("plate_min_height", "height_min"),
      ("plate_max_height", "height_max"), ("plate_taper", "taper"), ("bevel_amount", "bevel_amount"),
      ("bevel_segments", "bevel_segments"), ("corner_width", "corner_radius"), ("corner_bevel_segments", "corner_segments"),
      ("rivet_corner_distance", "rivet_dist"), ("rivet_diameter", "rivet_size"), ("rectangle_amount", "rect_count"),
      ("rectangle_width_min", "rect_w_min"), ("rectangle_width_max", "rect_w_max"),
      ("rectangle_height_min", "rect_h_min"), ("rectangle_height_max", "rect_h_max"), ("pre_subdivisions", "subdiv")]
GM = [("greeble_amount", "amount"), ("coverage_amount", "coverage"), ("greeble_subd_levels", "subd_levels"),
      ("greeble_deviation", "deviation"), ("greeble_min_width", "width_min"), ("greeble_max_width", "width_max"),
      ("greeble_min_length", "length_min"), ("greeble_max_length", "length_max"), ("greeble_min_height", "height_min"),
      ("greeble_max_height", "height_max")]
SKIP_P = ("preset", "group")
SKIP_G = ("preset", "group", "kit", "normal_direction")


def plating_vals(PD, pp):
    v = dict(PD["defaults"])
    for a, b in MP:
        v[b] = pp[a]
    v.update(pattern=PM.get(pp["pattern_type"], "crisscross"), floor="remove" if pp["remove_grooves"] else "keep",
             rivets=int(pp["use_rivets"]), random_color=0)
    v.pop("group", None)
    return v


def greeble_vals(GD, g):
    v = dict(GD["defaults"])
    for a, b in GM:
        v[b] = g[a]
    v.update(placement="overlapping" if g["greeble_pattern_type"] == "0" else "non_overlapping",
             keep_aspect=int(g["all_keep_aspect_ratio"]), random_color=0)
    for k in ("group", "kit"):
        v.pop(k, None)
    return v


def resolve_levels(L, key, PD, GD):
    """Blender preset levels -> flat slot list (source level resolved, selection as a [lo,hi) share)."""
    gl = [x for x in L if x["type"] == "GreebleDecorator"]
    out, used = [], {}
    for i, l in enumerate(L):
        k = int(l["selection_level"])
        st = list(l["selection_type"]) if k else []
        # a hidden zero-width Frame level has no side ring: take the sides of the level below it
        while k and not L[k - 1]["visible"] and L[k - 1]["type"] == "PlatingGeneratorDecorator" and st == ["1"] \
                and float(L[k - 1]["plating_props"]["groove_width"]) == 0.0 and int(L[k - 1]["selection_level"]):
            k = int(L[k - 1]["selection_level"])
        lo, hi = 0.0, 1.0
        if k and (l["select_remaining"] or l["selection_amount"] < 100):
            cur = used.get(k, 0.0)
            if l["select_remaining"]:
                lo = cur
                hi = cur + (1.0 - cur) * l["selection_amount"] / 100.0
                used[k] = hi
            else:
                hi = l["selection_amount"] / 100.0
                used[k] = max(cur, hi)
        plat = l["type"] == "PlatingGeneratorDecorator"
        if plat:
            if i == 0 and k == 0 and key in PD["presets"]:
                vals = dict(PD["defaults"])
                vals.update(PD["presets"][key]["values"])
                vals.pop("group", None)
            else:
                vals = plating_vals(PD, l["plating_props"])
        else:
            if len(gl) == 1 and key in GD["presets"]:
                vals = dict(GD["defaults"])
                vals.update(GD["presets"][key]["values"])
                for q in ("group", "kit"):
                    vals.pop(q, None)
            else:
                vals = greeble_vals(GD, l["greeble_props"])
        out.append({"type": 0 if plat else 1, "src": k, "tops": int("0" in st) if k else 1, "sides": int("1" in st),
                    "lo": round(lo * 100.0, 4), "hi": round(hi * 100.0, 4),
                    "on": int(bool(l["visible"] and l["is_enabled"])), "vals": vals})
    return out


def preset_data(PD, GD):
    pres = {}
    for f in sorted(glob.glob(BLENDER_PRESETS + "/*.json"), key=lambda x: int(os.path.basename(x).split(".")[0])):
        fn = os.path.basename(f)[:-5]
        d = jload(f)
        key = re.sub(r"[^A-Za-z0-9]+", "_", fn.split(". ", 1)[1]).strip("_")
        n = len(d["levels"])
        mkey = fn.split(". ", 1)[1].replace(" ", "_").replace("(", "").replace(")", "")   # key of the single-node preset menus
        pres[key] = {"label": fn + ("  (%d levels)" % n if n > 1 else ""),
                     "levels": resolve_levels(d["levels"], mkey, PD, GD)}
    for k, v in GD["presets"].items():
        vals = dict(GD["defaults"])
        vals.update(v["values"])
        for q in ("group", "kit"):
            vals.pop(q, None)
        pres["greeble_" + k] = {"label": "Greeble only: " + k.replace("_", " "),
                                "levels": [{"type": 1, "src": 0, "tops": 1, "sides": 0, "lo": 0.0, "hi": 100.0, "on": 1, "vals": vals}]}
    return pres


CALLBACK = r'''
import json
node = kwargs["node"]
data = json.loads(node.type().definition().sections()["presets.json"].contents())
key = kwargs["script_value"] if "script_value" in kwargs else node.parm("preset").evalAsString()
p = data["presets"].get(key)
if p:
    L = p["levels"]
    node.parm("levels").set(len(L))
    for i, l in enumerate(L, 1):
        for k in ("type", "src", "tops", "sides", "lo", "hi", "on"):
            node.parm("%s%d" % (k, i)).set(l[k])
        pre = "p_" if l["type"] == 0 else "g_"
        for k, v in l["vals"].items():
            parm = node.parm("%s%s%d" % (pre, k, i))
            if parm is not None:
                parm.set(v)
'''


def flat(g):
    out = []

    def walk(es):
        for t in es:
            if t.type() == hou.parmTemplateType.Folder:
                walk(t.parmTemplates())
            else:
                out.append(t)
    walk(g.entries())
    return out


def level_templates():
    """Per-level parm templates (names end in # for the multiparm), plus the plating / greeble lists."""
    def ren(t, pre):
        c = t.clone()
        c.setName(pre + t.name() + "#")
        return c
    pdef = hou.nodeType(hou.sopNodeTypeCategory(), "pf_plating_generator").definition().parmTemplateGroup()
    gdef = hou.nodeType(hou.sopNodeTypeCategory(), "pf_greeble_scatter").definition().parmTemplateGroup()
    pl = [ren(t, "p_") for t in flat(pdef) if t.name() not in SKIP_P]
    gl = [ren(t, "g_") for t in flat(gdef) if t.name() not in SKIP_G]
    kit = hou.MenuParmTemplate("g_kit#", "Greeble Kit", ("defaults", "hull", "panels", "custom", "all"),
                               menu_labels=("Simple Shapes (6)", "Hull Details (16)", "Panels (6)", "Custom Greebles (6)", "All Blender Greebles (34)"))
    gl.insert(1, kit)
    typ = hou.MenuParmTemplate("type#", "Level Type", ("plating", "greeble"), menu_labels=("Plating (panels)", "Greebles"), default_value=0)
    typ.setHelp("Plating = cut the faces into plates and raise them. Greebles = scatter small kit pieces on the faces.")
    on = hou.ToggleParmTemplate("on#", "Show In Result", default_value=True)
    on.setHelp("Off = the level still builds (later levels can use it) but is not part of the output (Blender's hidden 'Frame' levels).")
    src = hou.IntParmTemplate("src#", "Source Level", 1, (0,), min=0, max=MAXL - 1, min_is_strict=True)
    src.setHelp("0 = your input surface. n = the plates of level n above (must be an earlier level).")
    tops = hou.ToggleParmTemplate("tops#", "Use Plate Tops", default_value=True)
    sides = hou.ToggleParmTemplate("sides#", "Use Plate Edges", default_value=False)
    tops.setHelp("When the source is a plating level: work on its top faces.")
    sides.setHelp("When the source is a plating level: work on its side walls (plate edges).")
    lo = hou.FloatParmTemplate("lo#", "Take From %", 1, (0.0,), min=0, max=100, min_is_strict=True)
    hi = hou.FloatParmTemplate("hi#", "Take To %", 1, (100.0,), min=0, max=100, min_is_strict=True)
    lo.setHelp("Share of the source plates (ranked by the selection seed) this level starts at. 0 to 100 = all plates. "
               "A level that takes 'the remaining' plates starts where the one before it ended.")
    hi.setHelp("Where the share ends.")
    for t in (tops, sides, lo, hi):
        t.setConditional(hou.parmCondType.HideWhen, "{ src# == 0 }")
    pf = hou.FolderParmTemplate("f_plating#", "Plating Settings", folder_type=hou.folderType.Collapsible)
    for t in pl:
        pf.addParmTemplate(t)
    gf = hou.FolderParmTemplate("f_greeble#", "Greeble Settings", folder_type=hou.folderType.Collapsible)
    for t in gl:
        gf.addParmTemplate(t)
    pf.setConditional(hou.parmCondType.HideWhen, "{ type# != 0 }")
    gf.setConditional(hou.parmCondType.HideWhen, "{ type# != 1 }")
    return [typ, on, src, tops, sides, lo, hi, pf, gf], pl, gl


PAD = (
    'if (!hasattrib(0, "prim", "pf_host")) i@pf_host = -1; if (!hasattrib(0, "prim", "pf_greeble_id")) i@pf_greeble_id = -1; '
    'if (!hasattrib(0, "prim", "pf_kit")) i@pf_kit = -1; if (!hasattrib(0, "prim", "pf_kit_name")) s@pf_kit_name = ""; '
    'if (!hasattrib(0, "prim", "pf_plate_id")) i@pf_plate_id = -1; if (!hasattrib(0, "prim", "pf_plate_area")) f@pf_plate_area = 0; '
    'if (!hasattrib(0, "prim", "pf_plate_height")) f@pf_plate_height = 0; if (!hasattrib(0, "prim", "Cd")) v@Cd = {1, 1, 1};')


def vex(name):
    return open(f"{HERE}/vex/{name}.vfl", encoding="utf-8").read()


def build():
    if hou.isUIAvailable() is False:
        hou.hipFile.clear(suppress_save_prompt=True)
    for t in ("pf_plating_generator", "pf_greeble_scatter"):
        hou.hda.installFile(os.path.join(_PF, "otls", t + ".hda").replace("\\", "/"), force_use_assets=True)
    PD, GD = sec("pf_plating_generator"), sec("pf_greeble_scatter")
    if os.path.exists(HDA_PATH):
        os.remove(HDA_PATH)
    build_geo = hou.node("/obj").createNode("geo", "_build_" + NAME)
    subnet = build_geo.createNode("subnet", NAME)
    hda = subnet.createDigitalAsset(name=NAME, hda_file_name=HDA_PATH, description=LABEL,
                                    min_num_inputs=1, max_num_inputs=1, version="1.0")
    hda.allowEditingOfContents()
    defn = hda.type().definition()
    defn.setIcon("SOP_polyextrude")
    for c in list(hda.children()):
        c.destroy()

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

    inp0 = hda.indirectInputs()[0]
    ptemps, pl, gl = level_templates()
    empty = wr("empty", node("blast", "empty_blast", inp0, group="*", grouptype=4, negate=0), PAD, 1)
    outs, fins = [], []
    sel_vex = vex("pf_plating_preset_select")
    for s in range(1, MAXL + 1):
        ssrc = node("switch", "src%d" % s, inp0, *outs)
        ssrc.parm("input").setExpression("ch('../src%d')" % s)
        sel = wr("select%d" % s, ssrc, sel_vex.replace("SLOT", str(s)), 0)
        bl = node("blast", "take%d" % s, sel, group="_sel", grouptype=4, negate=1)
        skip = node("switch", "take_skip%d" % s, bl, ssrc)       # empty source: nothing to select
        skip.parm("input").setExpression("npoints('../src%d') == 0" % s)
        pn = hda.createNode("pf_plating_generator", "plating%d" % s)
        pn.setInput(0, skip)
        gn = hda.createNode("pf_greeble_scatter", "greebles%d" % s)
        gn.setInput(0, skip)
        for t in pl:
            nm = t.name()[2:-1]
            if pn.parm(nm) is not None:
                pn.parm(nm).setExpression("%s('../p_%s%d')" % ("chs" if t.type() == hou.parmTemplateType.String else "ch", nm, s))
        for t in gl:
            nm = t.name()[2:-1]
            if gn.parm(nm) is not None:
                gn.parm(nm).setExpression("ch('../g_%s%d')" % (nm, s))
        ty = node("switch", "level%d" % s, pn, gn)
        ty.parm("input").setExpression("ch('../type%d')" % s)
        post = node("blast", "greebles_only%d" % s, ty, group="pf_greeble", grouptype=4, negate=1)
        fin = node("switch", "result%d" % s, ty, post, empty)
        fin.parm("input").setExpression(
            "n = hou.pwd().parent()\n"
            "if %d > n.evalParm('levels') or not n.evalParm('on%d'): return 2\n"
            "return 1 if (n.evalParm('type%d') == 1 and n.evalParm('src%d') > 0) else 0" % (s, s, s, s),
            hou.exprLanguage.Python)
        pad = wr("same_attribs%d" % s, fin, PAD, 1)    # plates and greebles merge without an attribute mismatch warning
        outs.append(ty)
        fins.append(pad)
    mrg = node("merge", "merge", *fins)
    nocd = node("attribdelete", "no_colour", mrg, doprimdel=1, primdel="Cd")
    cdsw = node("switch", "colour_if_used", nocd, mrg)
    cdsw.parm("input").setExpression(
        "n = hou.pwd().parent()\n"
        "return int(any(n.evalParm('%s_random_color%d' % ('p' if n.evalParm('type%d' % i) == 0 else 'g', i)) for i in range(1, min(n.evalParm('levels'), " + str(MAXL) + ") + 1) if n.evalParm('on%d' % i)))",
        hou.exprLanguage.Python)
    gguard = wr("gguard", cdsw, 'if (nprimitives(0) > 0) setprimgroup(0, "_g", 0, 0, "set"); if (npoints(0) > 0) setpointgroup(0, "_g", 0, 0, "set");', 0)
    gclean = node("groupdelete", "clean_groups", gguard, deletions=1, group1="_*", grouptype1=0)
    out = node("null", "OUT", gclean)
    out.setDisplayFlag(True)
    out.setRenderFlag(True)
    hda.layoutChildren()

    pres = preset_data(PD, GD)
    items = ["none"] + list(pres)
    labels = ["(choose a preset)"] + [pres[k]["label"] for k in pres]
    pm = hou.MenuParmTemplate("preset", "Preset", tuple(items), menu_labels=tuple(labels), default_value=0)
    pm.setHelp("A Blender preset: fills the Levels list below (all its levels are chained inside). Entries 'Greeble only' scatter on your faces.")
    pm.setScriptCallback(CALLBACK)
    pm.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    seed = hou.IntParmTemplate("sel_seed", "Selection Seed", 1, (1,), min=0, max=100000, min_is_strict=True)
    seed.setHelp("Which plates a level takes when it uses only a share of its source plates (levels with Take From/To %).")
    ml = hou.FolderParmTemplate("levels", "Levels", folder_type=hou.folderType.MultiparmBlock, default_value=1,
                                parm_templates=ptemps)
    ml.setHelp("One entry per level, built top to bottom (max %d). The Preset fills it." % MAXL)
    defn.setParmTemplateGroup(hou.ParmTemplateGroup((pm, seed, ml)))
    defn.addSection("presets.json", json.dumps({"presets": pres}))
    defn.addSection("Help", HELP)
    hda.setUserData("nodeshape", "chevron_down")
    defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
    opts = defn.options()
    opts.setUnlockNewInstances(False)
    defn.setOptions(opts)
    defn.save(HDA_PATH, template_node=hda)
    d = hou.hda.definitionsInFile(HDA_PATH)[0]
    d.addSection("Tools.shelf", TOOLS_SHELF)
    assert d.embeddedHelp().strip()
    hda.destroy()
    build_geo.destroy()
    print("wrote " + HDA_PATH)


build()
