"""create_pf_planet_preview_hda.py - build polyfactory/otls/pf_planet_preview.hda (SOP, type pf::planet_preview).

    hython devScripts/create_pf_planet_preview_hda.py

A sphere that wears the maps baked by pf_custom_planet (sphere mode): albedo, clouds, city/lava emission, height
displacement, a lambert light and a rim atmosphere, as point colour Cd (+ uv, N). Native sphere SOP + one point wrangle
(VEX); no Python at run time. The equirect convention is the Houdini one of pf_space_direction (centre = -Z).
"""
import os
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
_POLYFACTORY = os.environ.get("POLYFACTORY", os.path.join(os.path.dirname(HERE), "polyfactory"))
OUTPUT_HDA = os.path.join(_POLYFACTORY, "otls", "pf_planet_preview.hda").replace("\\", "/")

VEX = r'''
// pf::planet_preview: equirect maps -> point colour. u,v exactly as pf_space_dir (Houdini convention: centre = -Z).
vector pn = normalize(@P);
float u = atan2(pn.x, -pn.z) / (2.0 * PI) + 0.5;
float v = 1.0 - acos(clamp(pn.y, -1.0, 1.0)) / PI;        // texture() has v = 0 at the bottom row
string base = chs("folder") + "/" + chs("prefix");
vector alb = texture(base + "_surface_equirect.exr", u, v);
vector4 cl = {0, 0, 0, 0};
if (chi("use_clouds")) { vector4 ct = texture(base + "_clouds_equirect.exr", u, v); cl = ct; }
vector em = {0, 0, 0};
if (chi("use_emission")) em = texture(base + "_emission_equirect.exr", u, v) * chf("emission_gain");
float h = 0.5;
if (chf("height_scale") != 0.0) { vector hh = texture(base + "_height_equirect.exr", u, v); h = hh.x; }
vector L = normalize(chv("light_dir"));
float lam = max(dot(pn, L), 0.0);
float day = smooth(-0.05, 0.25, dot(pn, L));
vector col = lerp(alb, set(cl.x, cl.y, cl.z), clamp(cl.w * chf("cloud_amount"), 0, 1));
vector lit = col * (chf("ambient") + (1.0 - chf("ambient")) * lam * chf("light_gain"));
float rim = pow(1.0 - clamp(dot(pn, normalize(chv("view_dir"))), 0, 1), 3.0) * chf("atm_strength");
lit += chv("atm_color") * rim * (0.15 + 0.85 * day);
lit += em * (1.0 - day);
v@Cd = lit;
v@uv = set(u, v, 0);
@P = pn * (1.0 + (h - 0.5) * chf("height_scale"));
v@N = normalize(@P);
'''

HELP = '''= PF Planet Preview =

#type: node
#context: sop
#internal: pf::planet_preview
#icon: SOP/sphere

"""A sphere wearing the equirect maps baked by PF Custom Planet: colour, clouds, night lights, height, light and a rim atmosphere."""

Bake *PF Custom Planet* in *Sphere maps* mode (button *Bake EXR*), point *Map Folder* at the folder and set *Prefix*
to the Bake Name. The sphere reads `<prefix>_surface_equirect.exr`, `_clouds_`, `_emission_` and `_height_`.
The result is point colour `Cd` (shaded by the *Light Direction*), `uv` and `N`. Use *Height Scale* to displace the sphere.

@parameters
    Map Folder:
        #id: folder
        Folder with the baked EXRs.
    Prefix:
        #id: prefix
        File prefix (the Bake Name).
'''


def create():
    if not hou.isUIAvailable():
        hou.hipFile.clear(suppress_save_prompt=True)
    if os.path.exists(OUTPUT_HDA):
        os.remove(OUTPUT_HDA)
    geo = hou.node("/obj").createNode("geo", "_build_ctx")
    sub = geo.createNode("subnet", "_build")
    hda = sub.createDigitalAsset(name="pf::planet_preview", hda_file_name=OUTPUT_HDA, description="PF Planet Preview",
                                 min_num_inputs=0, max_num_inputs=0, version="1.0")
    hda.allowEditingOfContents()
    for c in hda.children():
        c.destroy()
    sph = hda.createNode("sphere", "sphere")
    sph.parm("type").set(2)                       # polygon mesh (rows x cols)
    sph.parm("rows").setExpression('ch("../rows")', language=hou.exprLanguage.Hscript)
    sph.parm("cols").setExpression('ch("../cols")', language=hou.exprLanguage.Hscript)
    sph.parm("orient").set(1)                     # Y axis
    sph.parmTuple("rad").set((1, 1, 1))
    wr = hda.createNode("attribwrangle", "maps_to_color")
    wr.setInput(0, sph)
    wr.parm("class").set(2)
    wr.parm("snippet").set(VEX)
    spare = wr.parmTemplateGroup()
    wr.setDisplayFlag(True)
    wr.setRenderFlag(True)
    hda.layoutChildren()
    # wrangle parms are channel references to the asset parms: use ch() paths via spare parms on the wrangle copied from the asset
    ptg = hou.ParmTemplateGroup()

    def f(n, l, v, mn, mx, h=""):
        t = hou.FloatParmTemplate(n, l, 1, default_value=(v,), min=mn, max=mx)
        t.setHelp(h)
        return t

    def i(n, l, v, h=""):
        t = hou.ToggleParmTemplate(n, l, default_value=bool(v))
        t.setHelp(h)
        return t

    def v3(n, l, d, h=""):
        t = hou.FloatParmTemplate(n, l, 3, default_value=d)
        t.setHelp(h)
        return t

    s = hou.StringParmTemplate("folder", "Map Folder", 1, default_value=("$HIP/planet",), string_type=hou.stringParmType.FileReference)
    s.setHelp("Folder with the EXRs baked by PF Custom Planet (sphere maps).")
    ptg.append(s)
    s = hou.StringParmTemplate("prefix", "Prefix", 1, default_value=("planet",))
    s.setHelp("The Bake Name used when baking. Files read: <prefix>_surface_equirect.exr, _clouds_, _emission_, _height_.")
    ptg.append(s)
    r = hou.IntParmTemplate("rows", "Rows", 1, default_value=(128,), min=8, max=2048)
    c = hou.IntParmTemplate("cols", "Columns", 1, default_value=(256,), min=8, max=4096)
    r.setHelp("Sphere resolution: more points = sharper colour.")
    ptg.append(r)
    ptg.append(c)
    ptg.append(v3("light_dir", "Light Direction", (0.5, 0.4, 0.8), "Where the sun is (direction towards the sun)."))
    ptg.append(f("ambient", "Ambient", 0.05, 0, 1, "Brightness of the dark side."))
    ptg.append(f("light_gain", "Light Strength", 1.0, 0, 4))
    ptg.append(i("use_clouds", "Clouds", 1))
    ptg.append(f("cloud_amount", "Cloud Amount", 1.0, 0, 1))
    ptg.append(i("use_emission", "Night Lights / Lava", 1, "Show the emission map on the dark side."))
    ptg.append(f("emission_gain", "Emission Gain", 1.0, 0, 10))
    ptg.append(f("height_scale", "Height Scale", 0.0, 0, 0.5, "Displaces the sphere by the height map (0 = perfect sphere)."))
    ptg.append(f("atm_strength", "Atmosphere Strength", 1.0, 0, 4, "Rim glow at the edge, seen from View Direction."))
    ptg.append(hou.FloatParmTemplate("atm_color", "Atmosphere Colour", 3, default_value=(0.2, 0.45, 1.0), min=0, max=1,
                                     look=hou.parmLook.ColorSquare, naming_scheme=hou.parmNamingScheme.RGBA))
    ptg.append(v3("view_dir", "View Direction", (0, 0, 1), "Direction towards the camera, for the rim glow (colour is baked per point)."))
    defn = hda.type().definition()
    defn.setParmTemplateGroup(ptg)
    # the wrangle reads the asset parms
    for name in ("folder", "prefix"):
        pass
    wr.parm("snippet").set(VEX.replace('chs("', 'chs("../').replace('chi("', 'chi("../').replace('chf("', 'chf("../').replace('chv("', 'chv("../'))
    defn.addSection("Help", HELP)
    defn.setIcon("SOP_sphere")
    defn.save(OUTPUT_HDA, template_node=hda)
    hda.destroy()
    geo.destroy()
    d = hou.hda.definitionsInFile(OUTPUT_HDA)[0]
    assert d.embeddedHelp().strip()
    print("wrote", OUTPUT_HDA)


if __name__ == "__main__":
    create()
