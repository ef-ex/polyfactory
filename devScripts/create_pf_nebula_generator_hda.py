"""create_pf_nebula_generator_hda.py - build polyfactory/otls/pf_nebula_generator.hda (COP).

Recreation of the Blender "Nebula Generator 3.0.3": raymarched scattering volume + stars, evaluated per output
direction (equirect / cube cross / cube face via the shared layout parms), float HDR output.
Kernel: polyfactory/ocl/pf_nebula_generator.cl. Doc: ideas/spacetools.md "## Nebula generator".
Run: hython devScripts/create_pf_nebula_generator_hda.py
"""
import hou, os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_space_common as sc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_PF = os.environ.get("POLYFACTORY", os.path.join(ROOT, "polyfactory"))
OUT = os.path.join(_PF, "otls", "pf_nebula_generator.hda").replace("\\", "/")
KERNEL_BODY = open(os.path.join(_PF, "ocl", "pf_nebula_generator.cl"), encoding="utf8").read()
PRESETS = json.load(open(os.path.join(_PF, "scripts", "python", "polyfactory", "spacetools", "nebula_presets.json")))

# kind: int | float | vec3 | color | ramp_f | ramp_c ; (name, kind, default, label, extra) per folder
D = PRESETS["presets"]["default"]
def rp(n):  # ramp default as (basis, pos, val)
    r = D[n]; return (r["interp"], r["pos"], r["val"])

FOLDERS = [
    ("Density", [
        ("main_ramp", "ramp_f", rp("main_ramp"), "Main Cloud Density Ramp", "Noise value -> density of the dark dust cloud (constant steps = hard-edged lanes)."),
        ("main_mult", "float", D["main_mult"], "Main Density Multiplier", dict(min=0, max=200)),
        ("gas_ramp", "ramp_f", rp("gas_ramp"), "Gas Density Ramp", "Noise value -> density of the luminous gas; its output also picks the gas colour."),
        ("gas_mult", "float", D["gas_mult"], "Gas Density Multiplier", dict(min=0, max=0.2)),
        ("volume_unit", "float", D["volume_unit"], "Volume Scale", dict(min=1, max=1000, help="Blender box scale: converts the per-unit densities to the unit-radius volume. Bigger = thicker.")),
    ]),
    ("Colours", [
        ("gas_color_ramp", "ramp_c", rp("gas_color_ramp"), "Gas Colour Ramp", "Gas density -> scattering colour."),
        ("gas_hue", "float", D["gas_hue"], "Gas Hue (0.5 = none)", dict(min=0, max=1)),
        ("gas_sat", "float", D["gas_sat"], "Gas Saturation", dict(min=0, max=2)),
        ("gas_val", "float", D["gas_val"], "Gas Value", dict(min=0, max=4)),
        ("hue", "float", D["hue"], "Overall Hue (0.5 = none)", dict(min=0, max=1)),
        ("sat", "float", D["sat"], "Overall Saturation", dict(min=0, max=2)),
        ("val", "float", D["val"], "Overall Value", dict(min=0, max=4)),
        ("albedo_floor", "float", 0.0105, "Weak-Colour Floor", dict(min=0, max=0.1, help="Blender/EEVEE drops gas colour channels below about 0.01 (a dark teal loses its weak channel, so dark gas looks more saturated). Measured and modelled as c * c^2/(c^2+floor^2); 0 = linear.")),
        ("exposure", "float", 1.0, "Exposure (x)", dict(min=0, max=100, help="Linear radiance multiplier of the whole image.")),
    ]),
    ("Noise", [
        ("coarse_scale", "float", D["coarse_scale"], "Scale Variation: Scale", dict(min=0.001, max=10)),
        ("coarse_rough", "float", D["coarse_rough"], "Scale Variation: Roughness", dict(min=0, max=1)),
        ("dist_scale", "float", D["dist_scale"], "Distortion Variation: Scale", dict(min=0.1, max=100)),
        ("dist_rough", "float", D["dist_rough"], "Distortion Variation: Roughness", dict(min=0, max=1)),
        ("dist_mult", "float", D["dist_mult"], "Distortion Multiplier", dict(min=0, max=2)),
        ("cloud_rough", "float", D["cloud_rough"], "Overall Roughness", dict(min=0, max=1)),
        ("octaves", "int", 12, "Detail (octaves)", dict(min=1, max=16, help="Blender uses 16; 10-12 is visually identical and faster.")),
        ("seed", "int", 0, "Seed", dict(min=0, max=100000, help="Shifts the noise lookup; the Transform location is the other 'seed'.")),
    ]),
    ("Falloff", [
        ("falloff_ramp", "ramp_f", rp("falloff_ramp"), "Transparency Gradient Ramp", "Distance from the volume centre / size -> volume opacity. The volume ends where this reaches 0."),
        ("falloff_size", "float", D["falloff_size"], "Transparency Sphere Size", dict(min=0.05, max=10)),
    ]),
    ("Light", [
        ("light_color", "color", D["light_color"], "Main Light Colour", None),
        ("light_strength", "float", D["light_strength"], "Main Light Strength", dict(min=0, max=1000)),
        ("light_rot", "vec3", D["light_rot"], "Main Light Rotation", dict(help="Blender XYZ Euler degrees; the sun lamp shines along -Z rotated by this.")),
        ("shadow_steps", "int", 24, "Shadow Steps", dict(min=0, max=48, help="Self-shadowing march of the main light (0 = unshadowed, flat).")),
        ("sun_color", "color", D["sun_color"], "Star Light Colour", None),
        ("sun_strength", "float", D["sun_strength"], "Star Light Power (W)", dict(min=0, max=1e8, help="Every large star carries a point lamp of this power (as in the .blend, where the large-star collection holds a mesh and a 2e6 W lamp). Unshadowed, 1/r^2.")),
    ]),
    ("Stars", [
        ("star_count", "int", 6000, "Small Stars: Count", dict(min=0, max=200000, help="Before the coverage mask.")),
        ("star_seed", "float", D["star_seed"], "Small Stars: Seed", dict(min=0, max=1000)),
        ("star_coverage", "float", D["star_coverage"], "Small Stars: Coverage", dict(min=0, max=1)),
        ("star_noise_scale", "float", D["star_noise_scale"], "Small Stars: Noise Scale", dict(min=0.1, max=100)),
        ("star_radius", "float", 1.2, "Small Stars: Cloud Radius", dict(min=0.1, max=10, help="Stars are points inside a ball of this radius (volume units) round the volume centre; seen from inside it, density grows toward the far side like a real 3D star cloud.")),
        ("star_size_min", "float", 0.01, "Small Stars: Min Size", dict(min=0, max=20, help="World size (Blender units) of the star planes: apparent size = size / distance.")),
        ("star_size_max", "float", 0.5, "Small Stars: Max Size", dict(min=0, max=20)),
        ("star_ramp", "ramp_c", rp("star_ramp"), "Star Colour Ramp", "Random value per star -> colour."),
        ("star_hue", "float", D["star_hue"], "Star Hue (0.5 = none)", dict(min=0, max=1)),
        ("star_sat", "float", D["star_sat"], "Star Saturation", dict(min=0, max=2)),
        ("star_val", "float", D["star_val"], "Star Value", dict(min=0, max=4)),
        ("star_strength", "float", D["star_strength"], "Star Emission Strength", dict(min=0, max=1000)),
        ("large_count", "int", D["large_count"], "Large Stars: Count", dict(min=0, max=16)),
        ("large_seed", "int", D["large_seed"], "Large Stars: Seed", dict(min=0, max=100000)),
        ("large_size_min", "float", D["large_size_min"], "Large Stars: Min Size", dict(min=0, max=50, help="World size, as for the small stars.")),
        ("large_size_max", "float", D["large_size_max"], "Large Stars: Max Size", dict(min=0, max=50)),
        ("large_pos0", "vec3", D["large_pos0"], "Large Star 1 Position", dict(help="Volume units. (0,0,0) = hashed from the seed. Also the position of its lamp.")),
        ("large_pos1", "vec3", D["large_pos1"], "Large Star 2 Position", dict(help="As star 1.")),
        ("large_pos2", "vec3", D["large_pos2"], "Large Star 3 Position", dict(help="As star 1.")),
        ("large_strength", "float", 19.4, "Large Stars: Strength", dict(min=0, max=10000)),
        ("large_glare", "float", 0.0, "Large Stars: Glare", dict(min=0, max=5, help="6-point streak glare (the .blend does this in the compositor).")),
        ("bg_stars", "float", 1.0, "Background Stars", dict(min=0, max=10, help="Voronoi dust of distant stars (the .blend's world shader). 0 = off.")),
    ]),
    ("Transform", [
        ("view", "vec3", D["view"], "Viewer Position", dict(help="Where the sky is seen from, in volume units (box half-size = 1). Default = the sample camera.")),
        ("view_dist", "float", 0.4, "Viewer Distance (x)", dict(min=0, max=2, help="Scales Viewer Position. 1 = the sample camera (near the edge of the volume, so only one side is filled); 0.4 keeps the viewer inside the cloud so the whole sky has content; 0 = volume centre.")),
        ("map_loc", "vec3", D["map_loc"], "Noise Location", None),
        ("map_rot", "vec3", D["map_rot"], "Noise Rotation", None),
        ("map_scale", "vec3", D["map_scale"], "Noise Scale", None),
        ("noise_unit", "float", 85.545, "Noise Unit Size", dict(min=1, max=1000, help="Size of the object the noise reads its coordinates from (the .blend's Empty, scale 85.545). Volume Scale / this = how many noise units the volume spans.")),
    ]),
    ("Quality", [
        ("samples", "int", 1, "Samples (jitter)", dict(min=1, max=16, help="Stratified ray jitters averaged per pixel: removes the grain of thin dust edges; cost x samples.")),
        ("steps", "int", 96, "Volume Steps", dict(min=8, max=160, help="Ray steps through the volume. 48 for preview, 128+ for a final bake.")),
    ]),
]
ALL = [p for _, ps in FOLDERS for p in ps]
CLNAMES = {"vec3": "xyz", "color": "rgb"}


def _fnum(v):
    return repr(float(v))


def bind_header():
    lines = ["#bind layer !size_ref?", "#bind layer !&color float3", "#bind layer !&alpha float",
             "#bind parm layout int val=0", "#bind parm face int val=0", "#bind parm convention int val=0"]
    for name, kind, default, label, extra in ALL:
        if kind == "int": lines.append("#bind parm %s int val=%d" % (name, default))
        elif kind == "float": lines.append("#bind parm %s float val=%s" % (name, _fnum(default)))
        elif kind in ("vec3", "color"): lines.append("#bind parm %s float3 val=%s" % (name, " ".join(_fnum(x) for x in default)))
        elif kind == "ramp_f": lines.append("#bind ramp %s float" % name)
        else: lines.append("#bind ramp %s float3" % name)
    return "\n".join(lines) + "\n"


def configure(ocl):
    ocl.parm("kernelcode").set(bind_header() + sc.PF_SPACE_DIR_CL + KERNEL_BODY)
    ocl.parm("inputs").set(1)
    ocl.parm("input1_name").set("size_ref"); ocl.parm("input1_type").set(7); ocl.parm("input1_optional").set(1)
    ocl.parm("outputs").set(2)
    ocl.parm("output1_name").set("color"); ocl.parm("output1_type").set(4)
    ocl.parm("output2_name").set("alpha"); ocl.parm("output2_type").set(2)
    binds = [("layout", "int"), ("face", "int"), ("convention", "int")] + [(n, k) for n, k, *_ in ALL]
    ocl.parm("bindings").set(len(binds))
    H = hou.exprLanguage.Hscript
    for i, (n, k) in enumerate(binds, 1):
        ocl.parm("bindings%d_name" % i).set(n)
        pre = "bindings%d_" % i
        if k == "int":
            ocl.parm(pre + "type").set(0); ocl.parm(pre + "intval").setExpression('ch("../%s")' % n, language=H)
        elif k == "float":
            ocl.parm(pre + "type").set(1); ocl.parm(pre + "fval").setExpression('ch("../%s")' % n, language=H)
        elif k in ("vec3", "color"):
            ocl.parm(pre + "type").set(3)
            for j, c in enumerate(CLNAMES[k], 1):
                ocl.parm(pre + "v3val%d" % j).setExpression('ch("../%s%s")' % (n, c), language=H)
        else:
            ocl.parm(pre + "type").set(5)
            ocl.parm(pre + "ramptype").set(0 if k == "ramp_f" else 1)
            ocl.parm(pre + "rampinputtype").set(1)
            ocl.parm(pre + "rampsize").set(256)
            ocl.parm(pre + "rampraw").setExpression('chrampraw("../%s")' % n, language=H)


def make_ptg():
    g = hou.ParmTemplateGroup()
    names = PRESETS["order"]
    g.append(hou.MenuParmTemplate("preset", "Preset", menu_items=tuple(names), menu_labels=tuple(n.replace("_", " ").title() for n in names),
        default_value=0, script_callback="import polyfactory.spacetools.nebula as nb; nb.apply_preset(kwargs['node'], kwargs['parm'].evalAsString())",
        script_callback_language=hou.scriptLanguage.Python,
        help="Looks recreated from the Blender sample .blend files. Choosing one overwrites the parameters below."))
    g.append(sc.layout_parm_folder("Output Layout"))
    folders = []
    for fname, plist in FOLDERS:
        f = hou.FolderParmTemplate("f_" + fname.lower(), fname, folder_type=hou.folderType.Tabs)
        for name, kind, default, label, extra in plist:
            if kind == "int":
                x = extra or {}
                t = hou.IntParmTemplate(name, label, 1, default_value=(default,), min=x.get("min", 0), max=x.get("max", 100), help=x.get("help", ""))
            elif kind == "float":
                x = extra or {}
                t = hou.FloatParmTemplate(name, label, 1, default_value=(default,), min=x.get("min", 0), max=x.get("max", 1), help=x.get("help", ""))
            elif kind == "vec3":
                x = extra or {}
                t = hou.FloatParmTemplate(name, label, 3, default_value=tuple(default), help=x.get("help", "") if x else "", min=-1000, max=1000)
                t.setMinIsStrict(False); t.setMaxIsStrict(False)
            elif kind == "color":
                t = hou.FloatParmTemplate(name, label, 3, default_value=tuple(default), look=hou.parmLook.ColorSquare, naming_scheme=hou.parmNamingScheme.RGBA, min=0, max=1)
                t.setMaxIsStrict(False)
            else:
                isf = kind == "ramp_f"
                t = hou.RampParmTemplate(name, label, hou.rampParmType.Float if isf else hou.rampParmType.Color, default_value=2,
                                         default_basis=hou.rampBasis.Linear, show_controls=True, help=extra if isinstance(extra, str) else "")
            f.addParmTemplate(t)
        folders.append(f)
    for f in folders:
        g.append(f)
    return g


HELP = """= PF Nebula Generator =
#type: node
#context: cop
#icon: COP_subnet

"""  + """Procedural space nebula as an HDR image, recreated from the Blender "Nebula Generator 3.0.3". A raymarched scattering volume
(dark dust + luminous gas) lit by a sun lamp and by point lamps at the large stars, seen from inside, with small/large stars and a star background.

@outputs

color:
    #type: RGB. Linear HDR radiance (values above 1 are normal; stars reach ~15-100).

alpha:
    #type: Mono. 1 - transmittance of the volume (how much of the background is hidden by dust and gas).

@parms

Preset:
    Looks taken from the Blender sample files; overwrites the parameters.

Output Layout / Face Size N:
    Equirect (4N x 2N), cube cross (4N x 3N) or one cube face (N x N). Bake with polyfactory.spacetools.bake.

@related
- ideas/spacetools.md "Nebula generator" and "Shared: space_direction / cubemap".
"""


def populate(hda):
    const = hda.createNode("constant", "size_const")
    rs = hda.createNode("resample", "size_resample")
    rs.setInput(0, const)
    rs.parm("basesize").set(0)
    rs.parm("resolution1").setExpression('ch("../outresx")', language=hou.exprLanguage.Hscript)
    rs.parm("resolution2").setExpression('ch("../outresy")', language=hou.exprLanguage.Hscript)
    ocl = hda.createNode("opencl", "nebula_kernel")
    configure(ocl)
    ocl.setInput(0, rs)
    return [(ocl, 0), (ocl, 1)]


ON_CREATED = "import polyfactory.spacetools.nebula as nb\nnb.apply_preset(kwargs['node'], 'default')\nimport polyfactory.spacetools.sky as sk\nsk.ensure_preview(kwargs['node'])\n"

if __name__ == "__main__":
    path = sc.make_cop_hda("pf_nebula_generator", "PF Nebula Generator", OUT, make_ptg(), populate,
                           [("color", 3), ("alpha", 1)], HELP, on_created=ON_CREATED)
    print("built", path)
