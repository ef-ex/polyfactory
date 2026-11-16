"""create_pf_custom_planet_hda.py - build polyfactory/otls/pf_custom_planet.hda (Copernicus).

    hython devScripts/create_pf_custom_planet_hda.py

Port of the Blender "Custom Planet 1.0" addon (billboard shader over a library of EXR disc images) plus full-sphere
maps for cubemaps/equirects. One OpenCL COP (pf_planet_kernel.py) evaluates every layer per pixel; the library
images arrive through File COPs (missing file = transparent black + a flag, the kernel then falls back to the
procedural generator). Source of truth: pf_planet_kernel.py (kernel), pf_custom_planet_module.py (library paths, bake).
"""
import os
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
sys.path.insert(0, HERE)
import pf_planet_kernel as K  # noqa: E402
import pf_custom_planet_module as M  # noqa: E402
import pf_space_common as sc  # noqa: E402

_POLYFACTORY = os.environ.get("POLYFACTORY", os.path.join(os.path.dirname(HERE), "polyfactory"))
OUTPUT_HDA = os.path.join(_POLYFACTORY, "otls", "pf_custom_planet.hda").replace("\\", "/")
NAME = "pf_custom_planet"
PYEXPR = {"water_proc": ("proc", "watr"), "emis_proc": ("proc", "emis"), "cloud_proc": ("proc", "clds"), "atm_proc": ("proc", "atmo")}
for _k in K.IMAGES:
    PYEXPR["have_" + _k] = ("have", _k)


def _configure(ocl):
    ocl.parm("kernelcode").set(K.build_kernel(sc.PF_SPACE_DIR_CL))
    ocl.parm("outputs").set(len(K.OUTPUTS))
    for i, (n, t) in enumerate(K.OUTPUTS, 1):
        ocl.parm("output%d_name" % i).set(n)
        ocl.parm("output%d_type" % i).set(t + 1)         # opencl signature index = subnet index + 1
    ocl.parm("inputs").set(1 + len(K.IMAGES))
    ocl.parm("input1_name").set("size_ref"); ocl.parm("input1_type").set(7); ocl.parm("input1_optional").set(1)
    for i, n in enumerate(K.IMAGES, 2):
        ocl.parm("input%d_name" % i).set(n); ocl.parm("input%d_type" % i).set(5); ocl.parm("input%d_optional" % i).set(1)
    ncol = len(K.COLOR_PARMS)
    ocl.parm("bindings").set(K.NPS + ncol)
    k = 0
    for s in range(K.NPS):
        k += 1
        ocl.parm("bindings%d_name" % k).set("P%d" % s)
        ocl.parm("bindings%d_type" % k).set(4)
        for c in range(4):
            idx = s * 4 + c
            if idx >= len(K.PARMS):
                e = "0"; lang = hou.exprLanguage.Hscript
            else:
                n = K.PARMS[idx][0]
                if n in PYEXPR:
                    fn, kind = PYEXPR[n]
                    e = 'hou.pwd().parent().hdaModule().%s(hou.pwd().parent(), "%s")' % (fn, kind); lang = hou.exprLanguage.Python
                else:
                    e = 'ch("../%s")' % n; lang = hou.exprLanguage.Hscript
            ocl.parm("bindings%d_v4val%d" % (k, c + 1)).setExpression(e, language=lang)
    for n, _ in K.COLOR_PARMS:
        k += 1
        ocl.parm("bindings%d_name" % k).set("C_" + n)
        ocl.parm("bindings%d_type" % k).set(4)
        for c, ch in enumerate("rgb"):
            ocl.parm("bindings%d_v4val%d" % (k, c + 1)).setExpression('ch("../%s%s")' % (n, ch), language=hou.exprLanguage.Hscript)
        ocl.parm("bindings%d_v4val4" % k).set(1.0)


def _menu(name, label, items, default=0, help=""):
    t = hou.MenuParmTemplate(name, label, [str(i) for i in range(len(items))], menu_labels=items, default_value=default)
    t.setHelp(help)
    return t


def _F(name, label, v, mn, mx, help=""):
    t = hou.FloatParmTemplate(name, label, 1, default_value=(v,), min=mn, max=mx)
    t.setHelp(help)
    return t


def _C(name, label, v, help=""):
    t = hou.FloatParmTemplate(name, label, 3, default_value=v, min=0, max=1, look=hou.parmLook.ColorSquare,
                              naming_scheme=hou.parmNamingScheme.RGBA)
    t.setHelp(help)
    return t


def _folder(name, label, kids):
    f = hou.FolderParmTemplate(name, label, folder_type=hou.folderType.Simple)
    for k in kids:
        f.addParmTemplate(k)
    return f


def _ptg():
    P = hou.ParmTemplateGroup()
    F, C, menu, folder = _F, _C, _menu, _folder
    P.append(menu("mode", "Output", ["Billboard sprite (Blender addon look)", "Sphere maps (cubemap / equirect)"], 0,
                  "Billboard: one lit picture of the planet as a disc, exactly like the Blender addon's sprite. "
                  "Sphere maps: unlit maps for the whole sphere (colour, clouds, emission, water, height, normal) as equirect, cube faces or cross."))
    t = hou.IntParmTemplate("discres", "Billboard Size", 1, default_value=(1024,), min=64, max=8192, min_is_strict=True)
    t.setHelp("Width and height in pixels of the billboard image.")
    t.setConditional(hou.parmCondType.HideWhen, "{ mode != 0 }")
    P.append(t)

    lib = [hou.StringParmTemplate("imagedir", "Image Library", 1, default_value=("$PF_PLANET_IMAGES",),
                                  string_type=hou.stringParmType.FileReference)]
    lib[0].setHelp("Folder with the Custom Planet image library (1k/2k/4k with Surface, Water, Emission, Clouds, Atmosphere, LightSetup). "
                   "$PF_PLANET_IMAGES, or F:/cache/spacetools/planet_img/CustomPlanetImages when that is not set. "
                   "Without the images every layer falls back to the procedural generator.")
    rl = hou.MenuParmTemplate("libres", "Library Resolution", ["1k", "2k", "4k"], menu_labels=["1k", "2k", "4k"], default_value=1)
    rl.setHelp("Resolution of the library images read. Higher is sharper and slower.")
    lib.append(rl)
    for kind, label in (("surf", "Surface"), ("watr", "Water"), ("emis", "Emission"), ("clds", "Clouds"), ("atmo", "Atmosphere")):
        parm = M.KINDS[kind][0]
        dflt = {"surf": 5, "watr": 0, "emis": 0, "clds": 2, "atmo": 2}[kind]
        lib.append(menu(parm, label, M.menu_items(kind), dflt,
                        "Library image for this layer. 'Procedural' (or a missing file) uses the built-in generator."))
    lib.append(menu("lightsetup", "Light Setup", M.LIGHT_NAMES, 4,
                    "Library light shading for the billboard (terminator shape, how much is lit). Clouds, atmosphere and rim use the matching variant. "
                    "Procedural sun: analytic shading from Sun Azimuth/Elevation. Sphere maps are unlit and ignore this."))
    P.append(folder("f_lib", "Library", lib))

    seed = hou.IntParmTemplate("seed", "Seed", 1, default_value=(1,), min=0, max=10000)
    seed.setHelp("Different seed, different planet. Same seed always gives the same planet.")
    pr = [menu("ptype", "Planet Type", ["Terran", "Desert", "Ice", "Lava", "Gas Giant", "Moon / Barren"], 0,
               "Look of the procedural planet (used where a layer is 'Procedural' or its library image is missing)."),
          seed,
          F("pscale", "Feature Scale", 1.0, 0.2, 5.0, "Bigger = more, smaller continents/craters/bands."),
          F("rough", "Roughness", 0.5, 0.2, 0.9, "Terrain detail: higher = rougher coastlines and mountains."),
          F("sea", "Sea Level", 0.45, 0.0, 0.9, "Terran: fraction of the planet under water."),
          F("polar", "Polar Ice", 0.25, 0.0, 0.8, "Terran/Desert: size of the polar caps."),
          F("cloud_cov", "Cloud Coverage", 0.5, 0.0, 1.0, "Procedural clouds only."),
          F("bump", "Normal Strength", 1.0, 0.0, 5.0, "Strength of the normal map made from the height."),
          F("hscale", "Height Scale", 1.0, 0.0, 5.0, "Multiplies the height map. Library surfaces use their brightness as height.")]
    P.append(folder("f_proc", "Procedural", pr))

    P.append(folder("f_overall", "Overall", [
        F("emission_overall", "Emission Strength", 2.0, 0.0, 10.0, "Brightness of the whole billboard (the addon's Emission shader strength)."),
        F("shadow_bright", "Shadow Brightness", 0.0, 0.0, 1.0, "Lifts the dark side a little and brightens clouds/atmosphere (addon: Shadow Brightness).")]))
    P.append(folder("f_surface", "Surface", [
        F("s_rot", "Rotation", 0.0, -180, 180, "Turns the picture in its plane, in degrees."),
        F("s_hue", "Hue Shift", 0.0, -0.5, 0.5), F("s_sat", "Saturation", 1.0, 0.0, 3.0), F("s_val", "Brightness", 1.0, 0.0, 3.0),
        F("s_contrast", "Contrast", 0.0, -4.0, 8.0), C("tint", "Tint", (1.0, 1.0, 1.0), "Multiplies the surface colour."),
        F("night_sat", "Night Side Saturation", 0.5, 0.0, 1.0, "Billboard: how much colour survives in shadow (the addon halves it)."),
        hou.ToggleParmTemplate("useramp", "Use Colour Ramp", default_value=False),
        F("whitepoint", "White Point", 1.0, 0.1, 4.0, "Brightness that maps to the top of the ramp."),
        C("ramp0", "Ramp Dark", (0.0, 0.0, 0.0)), C("ramp1", "Ramp Middle", (0.5, 0.5, 0.5)), C("ramp2", "Ramp Light", (1.0, 1.0, 1.0)),
        F("rampmid", "Ramp Middle Position", 0.5, 0.02, 0.98),
        F("r_hue", "Ramp Hue Shift", 0.0, -0.5, 0.5), F("r_sat", "Ramp Saturation", 1.0, 0.0, 3.0),
        F("r_val", "Ramp Brightness", 1.0, 0.0, 3.0), F("r_contrast", "Ramp Contrast", 0.0, -4.0, 8.0)]))
    P.append(folder("f_water", "Water", [
        F("w_blend", "Water Blend", 1.0, 0.0, 2.0, "How strongly the water mask paints the water colour over the surface."),
        F("w_rot", "Rotation", 0.0, -180, 180), C("w_color", "Water Colour", (0.02, 0.07, 0.18))]))
    P.append(folder("f_emis", "Emission", [
        F("e_strength", "Strength", 1.0, 0.0, 10.0, "Brightness of city lights / lava glow."), F("e_rot", "Rotation", 0.0, -180, 180),
        F("e_shadowvis", "Shadow Visibility", 1.0, 0.0, 1.0, "1: lights show everywhere. 0: only on the dark side."),
        F("e_hue", "Hue Shift", 0.0, -0.5, 0.5), F("e_sat", "Saturation", 1.0, 0.0, 3.0)]))
    P.append(folder("f_clouds", "Clouds", [
        F("c_blend", "Blend", 1.0, 0.0, 1.0), F("c_thick", "Thickness", 1.0, 0.0, 3.0, "Cloud opacity multiplier."),
        F("c_bright", "Brightness", 1.0, 0.0, 1.0, "0..1: the addon clamps it (measured against Blender: 1.4 renders like 1.0).")]))
    P.append(folder("f_atm", "Atmosphere (billboard)", [
        F("a_strength", "Strength", 1.0, 0.0, 4.0), F("a_sat", "Saturation", 1.0, 0.0, 3.0), C("a_color", "Colour", (0.0, 0.259, 1.0), "Hue of the glow."),
        F("a_center", "Center Strength", 0.7, 0.0, 1.0, "Lower = atmosphere also covers the middle of the disc."),
        F("a_wrim", "White Rim", 1.0, 0.0, 4.0, "Thin bright ring at the lit edge."), F("a_size", "Procedural Thickness", 1.0, 0.2, 4.0)]))
    P.append(folder("f_light", "Procedural Sun", [
        F("sun_az", "Sun Azimuth", 60.0, -180, 180, "Degrees around the view axis."), F("sun_el", "Sun Elevation", 10.0, -90, 90)]))
    P.append(folder("f_view", "View", [
        F("view_lon", "Longitude", 0.0, -180, 180, "Which side of the planet the library disc images face (sphere maps) and the procedural planet is viewed from (billboard)."),
        F("view_lat", "Latitude", 0.0, -90, 90), F("spin", "Spin", 0.0, -180, 180)]))

    lf = sc.layout_parm_folder("Output Layout (sphere maps)")
    f2 = hou.FolderParmTemplate("space_layout_folder", "Output Layout (sphere maps)", folder_type=hou.folderType.Simple)
    for t in lf.parmTemplates():
        if t.name() != "outres":
            f2.addParmTemplate(t)
    o = hou.IntParmTemplate("outres", "Output Resolution", 2, default_value=(1024, 1024),
                            conditionals={hou.parmCondType.DisableWhen: "{ mode >= 0 }"}, help="Resulting image size (read-only).")
    o.setDefaultExpression(('if(ch("mode")==0, ch("discres"), ch("res")*(1+3*(ch("layout")<2)))',
                            'if(ch("mode")==0, ch("discres"), ch("res")*(1+(ch("layout")==0)+2*(ch("layout")==1)))'))
    o.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,) * 2)
    f2.addParmTemplate(o)
    f2.setConditional(hou.parmCondType.HideWhen, "{ mode != 1 }")
    P.append(f2)

    for n, lab, v, h in [("bake_folder", "Bake Folder", "$HIP/planet", "Folder the EXR files are written to."),
                         ("bake_name", "Bake Name", "planet", "File prefix. Sphere maps: <name>_<map>_equirect / _cross / _px _nx _py _ny _pz _nz. Billboard: <name>_<map>.")]:
        t = hou.StringParmTemplate(n, lab, 1, default_value=(v,))
        t.setHelp(h)
        P.append(t)
    b = hou.ButtonParmTemplate("bake", "Bake EXR (all maps)")
    b.setScriptCallback("hou.phm().bake(kwargs['node'], hou.text.expandString(kwargs['node'].evalParm('bake_folder')), "
                        "kwargs['node'].evalParm('bake_name'), kwargs['node'].evalParm('res'))")
    b.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    b.setHelp("Writes 32-bit float EXRs of every map. Sphere maps: faces (N x N), cross (4N x 3N), equirect (4N x 2N) with N = Face Size N.")
    P.append(b)
    return P


HELP = '''= PF Custom Planet =

#type: node
#context: cop
#internal: pf_custom_planet
#icon: COP2/noise

"""Planet textures from the Blender Custom Planet look: a lit planet sprite, or colour / clouds / emission / water / height / normal maps for a whole sphere as cubemap or equirect EXR."""

A port of the *Custom Planet 1.0* Blender addon (Malte and Eike Ullrich). The addon is a shader that
composites ready-made EXR discs (surface, water mask, city/lava emission, clouds, atmosphere, light setup) on a
billboard. This node does the same maths, and can also turn the discs into whole-sphere maps. Layers without a
library image are generated procedurally, so the node always shows a planet.

== Outputs (8) ==
beauty (final), surface, clouds (rgb + opacity), emission, atmosphere (billboard), water (mask), height, normal (object space, 0..1).

== Output modes ==
* *Billboard*: the addon's lit sprite, N x N. Library discs are used as they are.
* *Sphere maps*: unlit maps for the whole sphere. Each library disc is an orthographic picture of one hemisphere; it is
  unprojected onto the facing hemisphere (Longitude/Latitude/Spin) and mirrored to the back. Procedural layers cover the whole sphere with no seams.

== Library ==
Set $PF_PLANET_IMAGES or the *Image Library* parm. Without it the planet is procedural.

@parameters
    Output:
        #id: mode
        Billboard sprite or sphere maps.
    Library:
        #id: f_lib
        Pick the image for each layer.
    Procedural:
        #id: f_proc
        Planet type and shape of the generated planet.
    Bake EXR:
        #id: bake
        Writes every map as float EXR.

'''


def create():
    if not hou.isUIAvailable():
        hou.hipFile.clear(suppress_save_prompt=True)
    if os.path.exists(OUTPUT_HDA):
        os.remove(OUTPUT_HDA)
    img = hou.node("/img") or hou.node("/").createNode("img", "img")
    copnet = img.createNode("copnet", "_build_ctx")
    subnet = copnet.createNode("subnet", "_build")
    subnet.parm("outputs").set(len(K.OUTPUTS))
    for i, (n, t) in enumerate(K.OUTPUTS, 1):
        subnet.parm("outputlabel%d" % i).set(n)
        subnet.parm("outputtype%d" % i).set(t)
    ocl = subnet.createNode("opencl", "pf_planet_kernel")
    hda = subnet.createDigitalAsset(name=NAME, hda_file_name=OUTPUT_HDA, description="PF Custom Planet",
                                    min_num_inputs=0, max_num_inputs=0, version="1")
    hda.allowEditingOfContents()
    kids = {n.name(): n for n in hda.children()}
    inner_ocl = kids["pf_planet_kernel"]
    out = [n for n in hda.children() if n.type().name() in ("output", "output0", "outputs")][0]
    for slot in range(20):
        try:
            out.setInput(slot, None)
        except Exception:
            break
    _configure(inner_ocl)
    for i in range(len(K.OUTPUTS)):
        out.setInput(i, inner_ocl, i)
    const = hda.createNode("constant", "size_const")
    rs = hda.createNode("resample", "size_resample")
    rs.setInput(0, const)
    rs.parm("basesize").set(0)
    rs.parm("resolution1").setExpression('ch("../outresx")', language=hou.exprLanguage.Hscript)
    rs.parm("resolution2").setExpression('ch("../outresy")', language=hou.exprLanguage.Hscript)
    inner_ocl.setInput(0, rs)
    for i, kind in enumerate(K.IMAGES, 1):
        f = hda.createNode("file", "f_" + kind)
        f.parm("filename").setExpression('hou.pwd().parent().hdaModule().filepath(hou.pwd().parent(), "%s")' % kind,
                                         language=hou.exprLanguage.Python)
        f.parm("missingdata").set(1)
        f.parm("aovs").set(1)
        f.parm("aov1").set("C")
        inner_ocl.setInput(i, f, 0)
    hda.layoutChildren()
    defn = hda.type().definition()
    defn.setParmTemplateGroup(_ptg())
    defn.addSection("Help", HELP)
    with open(os.path.join(HERE, "pf_custom_planet_module.py"), "r", encoding="utf-8") as fh:
        defn.addSection("PythonModule", fh.read())
    defn.setExtraFileOption("PythonModule/IsPython", True)
    defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
    defn.setIcon("COP2_noise")
    sc.add_tab_submenu(defn)
    defn.save(OUTPUT_HDA, template_node=hda)
    hda.destroy()
    copnet.destroy()
    d = hou.hda.definitionsInFile(OUTPUT_HDA)[0]
    assert d.embeddedHelp().strip()
    print("wrote", OUTPUT_HDA)


if __name__ == "__main__":
    create()
