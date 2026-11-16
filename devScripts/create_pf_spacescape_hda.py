"""create_pf_spacescape_hda.py - build polyfactory/otls/pf_spacescape.hda (Copernicus).

    hython devScripts/create_pf_spacescape_hda.py

Port of Spacescape (petrocket/spacescape): a layer stack of noise / point-star / billboard-star / sun / gradient
layers with Ogre blend factors and noise masks, evaluated per DIRECTION in one OpenCL COP, so cube faces, cross
and equirect layouts agree and have no seams. Layer parms are a multiparm; each of MAXL layers is bound to the
kernel as NSLOT float4 constants via ch() expressions (see pf_spacescape_kernel.py).
Source of truth for the kernel: pf_spacescape_kernel.py; for presets/bake: pf_spacescape_module.py.
"""
import os
import sys

import hou

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
sys.path.insert(0, HERE)
import pf_spacescape_kernel as K  # noqa: E402
import pf_spacescape_module as M  # noqa: E402
import pf_space_common as sc  # noqa: E402  shared direction / layout infra (ideas/spacetools.md)

_POLYFACTORY = os.environ.get("POLYFACTORY", os.path.join(os.path.dirname(HERE), "polyfactory"))
OUTPUT_HDA = os.path.join(_POLYFACTORY, "otls", "pf_spacescape.hda").replace("\\", "/")
NAME = "pf_spacescape"

# (parm, comp) per float4 slot component; None = constant 0. comp for tuple parms is the suffix letter.
def _slots():
    S = [None] * K.NSLOT
    S[0] = ["type", "seed", "noisetype", "enable"]
    S[1] = ["scale", "octaves", "lacunarity", "gain"]
    S[2] = ["@offset_or_spikes", "power", "shelf", "dither"]
    S[3] = ["colorin:r", "colorin:g", "colorin:b", "hdrmult"]
    S[4] = ["colorout:r", "colorout:g", "colorout:b", "hdrpower"]
    S[5] = ["count", "@size", "@sizemax", "srcblend"]
    S[6] = ["dstblend", "maskon", "mask_seed", "mask_type"]
    S[7] = ["mask_scale", "mask_oct", "mask_lac", "mask_gain"]
    S[8] = ["mask_offset", "mask_power", "mask_thresh", "midpos"]
    S[9] = ["axis:x", "axis:y", "axis:z", None]
    S[10] = ["colormid:r", "colormid:g", "colormid:b", "usemid"]
    return S


def expr(spec, i):
    """Python expression for one float4 component. Python (not hscript) so slots of layers that do not exist
    evaluate to 0 silently (hscript ch() on a missing multiparm instance raises a warning flag)."""
    if spec is None:
        return "0"
    g = lambda n: 'P.evalParm("%s%d")' % (n, i)
    if spec == "@offset_or_spikes":
        f = "%s if %s==0 else %s" % (g("offset"), g("type"), g("spikes"))
    elif spec == "@size":           # pixels for points, degrees (-> radians) for everything else
        f = "%s if %s==1 else %s*0.017453292519943295" % (g("size"), g("type"), g("size"))
    elif spec == "@sizemax":
        f = "%s*0.017453292519943295" % g("sizemax")
    elif ":" in spec:
        p, c = spec.split(":")
        f = 'P.evalParm("%s%d%s")' % (p, i, c)
    else:
        f = g(spec)
    return '(lambda P: (%s) if P.evalParm("layers")>=%d else 0)(hou.pwd().parent())' % (f, i)


def _configure(ocl):
    ocl.parm("kernelcode").set(K.build_kernel(sc.PF_SPACE_DIR_CL))
    ocl.parm("outputs").set(1)
    ocl.parm("output1_name").set("color")
    ocl.parm("output1_type").set(5)
    ocl.parm("inputs").set(1)
    ocl.parm("input1_name").set("size_ref")
    ocl.parm("input1_type").set(7)            # metadata: the size comes from the shared size chain
    ocl.parm("input1_optional").set(1)
    binds = [("layout", 0), ("face", 0), ("convention", 0), ("refres", 1), ("nlayers", 0)]
    exprs = {n: 'ch("../%s")' % n for n in ("layout", "face", "convention", "refres")}
    exprs["nlayers"] = 'min(ch("../layers"),%d)' % K.MAXL
    nb = len(binds) + K.MAXL * K.NSLOT
    ocl.parm("bindings").set(nb)
    k = 0
    for name, t in binds:
        k += 1
        ocl.parm("bindings%d_name" % k).set(name)
        ocl.parm("bindings%d_type" % k).set(0 if t == 0 else 1)
        vp = "bindings%d_%s" % (k, "intval" if t == 0 else "fval")
        ocl.parm(vp).setExpression(exprs[name], language=hou.exprLanguage.Hscript)
    slots = _slots()
    for L in range(K.MAXL):
        for j in range(K.NSLOT):
            k += 1
            ocl.parm("bindings%d_name" % k).set("L%d_%d" % (L, j))
            ocl.parm("bindings%d_type" % k).set(4)           # float4
            for c in range(4):
                spec = slots[j][c]
                ocl.parm("bindings%d_v4val%d" % (k, c + 1)).setExpression(
                    expr(spec, L + 1), language=hou.exprLanguage.Python)


def _tmpl_group():
    P = hou.ParmTemplateGroup()
    d = M.DEFAULT

    def menu(name, label, items, default=0, help="", **kw):
        t = hou.MenuParmTemplate(name, label, [str(i) for i in range(len(items))], menu_labels=items,
                                 default_value=default, **kw)
        t.setHelp(help)
        return t

    P.append(sc.layout_parm_folder("Output Layout"))
    t = hou.FloatParmTemplate("refres", "Star Size Reference", 1, default_value=(0.0,), min=0, max=8192)
    t.setHelp("0: point-star Size is in real output pixels, like Spacescape (a 1 px star stays 1 px at any resolution). "
              "Set it to a face width such as 2048 to make the look resolution independent: Size then means pixels "
              "of a cube face that wide, so a 512 px preview shows the same stars as a 4096 px bake.")
    P.append(t)

    L = hou.FolderParmTemplate("layers", "Layers", folder_type=hou.folderType.MultiparmBlock)
    L.setHelp("The layer stack, bottom to top. Each layer is blended onto the layers below with Spacescape's "
              "source/destination blend factors. Up to %d layers." % K.MAXL)

    def add(t, help=""):
        if help:
            t.setHelp(help)
        L.addParmTemplate(t)
        return t

    def F(n, label, v, mn, mx, help="", **kw):
        return add(hou.FloatParmTemplate(n + "#", label, 1, default_value=(v,), min=mn, max=mx, **kw), help)

    def I(n, label, v, mn, mx, help=""):
        return add(hou.IntParmTemplate(n + "#", label, 1, default_value=(v,), min=mn, max=mx), help)

    def C(n, label, v, help=""):
        return add(hou.FloatParmTemplate(n + "#", label, 3, default_value=v, min=0, max=1,
                                         look=hou.parmLook.ColorSquare,
                                         naming_scheme=hou.parmNamingScheme.RGBA), help)

    def hide(t, cond):
        t.setConditional(hou.parmCondType.HideWhen, cond)

    add(hou.ToggleParmTemplate("enable#", "Enable", default_value=True))
    add(hou.StringParmTemplate("name#", "Name", 1, default_value=("Layer",)))
    add(hou.MenuParmTemplate("type#", "Type", [str(i) for i in range(5)],
                             menu_labels=["Noise (nebula)", "Point Stars", "Billboard Stars", "Sun / Flare",
                                          "Gradient / Band"], default_value=0),
        "Noise = clouds (fbm or ridged 3D noise on the sphere). Point Stars = many pixel-size stars. "
        "Billboard Stars = fewer large flared stars. Sun = one big flare at a direction. "
        "Gradient = a smooth band or ramp across the sky along an axis.")
    I("seed", "Seed", 0, 0, 1000, "Different seed, different pattern. Same seed always gives the same sky.")
    nt = add(menu("noisetype#", "Noise Type", ["Fbm (billowy)", "Ridged (veins and filaments)"], 0,
                  "Fbm: smooth clouds. Ridged: sharp filaments, the Spacescape nebula look. "
                  "For a Gradient layer: Fbm = soft band, Ridged = linear ramp."))
    hide(nt, "{ type# == 1 } { type# == 2 } { type# == 3 }")
    for n, lab, v, mn, mx, h in [
            ("scale", "Scale", 1.0, 0.05, 40.0, "Size of the largest features: higher = smaller, more cloud shapes across the sky."),
            ("lacunarity", "Lacunarity", 2.0, 1.1, 4.0, "How much finer each octave gets."),
            ("gain", "Gain", 0.5, 0.05, 2.0, "How strong each finer octave is (persistence). Low = smooth, high = rough."),
            ("offset", "Ridge Offset", 1.0, 0.2, 1.5, "Ridged noise only: how wide the ridges are."),
            ("power", "Power", 1.0, 0.1, 4.0, "Contrast curve of the result. Below 1 fills the cloud, above 1 thins it out."),
            ("shelf", "Shelf (cutoff)", 0.0, 0.0, 0.95, "Cuts away everything below this level, leaving thin wisps. 0.8 is a good sparse nebula."),
            ("dither", "Dither", 0.03, 0.0, 0.3, "Very fine noise that hides banding in the gradient.")]:
        t = F(n, lab, v, mn, mx, h)
        hide(t, "{ type# != 0 }" if n != "power" else "{ type# == 1 } { type# == 2 } { type# == 3 }")
    t = I("octaves", "Octaves", 8, 1, 16, "How many noise layers are stacked: more = finer detail, slower.")
    hide(t, "{ type# != 0 }")
    t = F("count", "Count", 10000, 1, 200000, "Number of stars over the whole sky.")
    hide(t, "{ type# != 1 } { type# != 2 }")
    t = F("size", "Size", 1.0, 0.0, 60.0, "Point stars: pixels (at the Star Size Reference). Billboard stars: largest-distance size in degrees. "
          "Sun: angular radius in degrees. Gradient: band half-width in degrees.")
    hide(t, "{ type# == 0 }")
    t = F("sizemax", "Size Max", 4.0, 0.0, 60.0, "Billboard stars: size in degrees of the nearest (biggest) stars.")
    hide(t, "{ type# != 2 }")
    t = F("spikes", "Diffraction Spikes", 0.0, 0.0, 3.0, "Strength of the four-point cross on bright stars and the sun.")
    hide(t, "{ type# != 2 } { type# != 3 }")
    ax = add(hou.FloatParmTemplate("axis#", "Direction / Axis", 3, default_value=(0.0, 1.0, 0.0), min=-1, max=1,
                                   naming_scheme=hou.parmNamingScheme.XYZW),
             "Sun: the direction it sits in. Gradient: the axis the band is centred on (the band is a great circle "
             "around the sky at 90 degrees from the axis).")
    hide(ax, "{ type# != 3 } { type# != 4 }")
    ci = C("colorin", "Color (inner / near)", (1.0, 1.0, 1.0), "Noise and gradient: colour where the value is high. Stars: colour of the nearest/brightest stars. Sun: core colour.")
    cm = C("colormid", "Color (middle)", (0.5, 0.5, 0.5), "Optional third colour of the ramp (Noise and Gradient).")
    hide(cm, "{ type# != 0 } { type# != 4 }")
    um = add(hou.ToggleParmTemplate("usemid#", "Use Middle Color", default_value=False),
             "Turn the colour into a three-stop ramp: outer, middle, inner.")
    hide(um, "{ type# != 0 } { type# != 4 }")
    mp = F("midpos", "Middle Position", 0.5, 0.01, 0.99, "Where the middle colour sits on the ramp.")
    hide(mp, "{ type# != 0 } { type# != 4 }")
    C("colorout", "Color (outer / far)", (0.0, 0.0, 0.0), "Noise and gradient: colour where the value is low. Stars: colour of the farthest stars. Sun: halo colour.")
    F("hdrmult", "HDR Brightness", 1.0, 0.0, 200.0, "Multiplies the layer's brightness. Values above 1 are real HDR light: bright stars and the sun use 10-100.", min_is_strict=True)
    t = F("hdrpower", "HDR Falloff", 1.0, 0.2, 8.0, "Noise: contrast of the brightness. Stars: above 1 makes most stars dim and few bright.")
    hide(t, "{ type# == 3 }")
    add(menu("srcblend#", "Source Blend", M.BLEND, 0, "Spacescape source factor. 'one' adds the layer; 'src_alpha' with destination "
             "'one_minus_src_alpha' paints it over (use for dark dust)."))
    add(menu("dstblend#", "Dest Blend", M.BLEND, 0, "Spacescape destination factor (how much of what is below survives)."))
    mo = add(hou.ToggleParmTemplate("maskon#", "Mask", default_value=False),
             "Noise layers, gradients and the sun: multiplies the layer by a noise mask. Stars: keeps stars where the "
             "mask is bright (density follows mask squared, like Spacescape).")
    mk = []
    mk.append(add(menu("mask_type#", "Mask Noise", ["Fbm", "Ridged"], 1)))
    mk.append(I("mask_seed", "Mask Seed", 1, 0, 1000))
    mk.append(F("mask_scale", "Mask Scale", 1.0, 0.05, 40.0))
    mk.append(I("mask_oct", "Mask Octaves", 8, 1, 16))
    mk.append(F("mask_lac", "Mask Lacunarity", 2.0, 1.1, 4.0))
    mk.append(F("mask_gain", "Mask Gain", 0.7, 0.05, 2.0))
    mk.append(F("mask_offset", "Mask Ridge Offset", 1.0, 0.2, 1.5))
    mk.append(F("mask_power", "Mask Power", 1.25, 0.1, 4.0))
    mk.append(F("mask_thresh", "Mask Threshold", 0.4, 0.0, 0.95, "Cutoff of the mask: higher = more empty space between stars."))
    for t in mk:
        hide(t, "{ maskon# == 0 }")
    P.append(L)

    for n, lab, v, h in [("bake_folder", "Bake Folder", "$HIP/sky", "Folder the EXR files are written to."),
                         ("bake_name", "Bake Name", "sky", "File prefix. Faces get _px _nx _py _ny _pz _nz, plus _cross and _equirect.")]:
        t = hou.StringParmTemplate(n, lab, 1, default_value=(v,), string_type=hou.stringParmType.Regular)
        t.setHelp(h)
        P.append(t)
    b = hou.ButtonParmTemplate("bake", "Bake EXR (faces + cross + equirect)")
    b.setScriptCallback("hou.phm().bake(kwargs['node'], hou.text.expandString(kwargs['node'].evalParm('bake_folder')), "
                        "kwargs['node'].evalParm('bake_name'), kwargs['node'].evalParm('res'))")
    b.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    b.setHelp("Writes 32-bit float EXRs: six cube faces (N x N), the cross (4N x 3N) and the equirect (4N x 2N) with N = Face Size N.")
    P.append(b)
    pm = hou.MenuParmTemplate("preset", "Preset", list(M.PRESETS), menu_labels=list(M.PRESETS),
                              default_value=0)
    pm.setHelp("Replaces the whole layer stack with a starting look.")
    P.insertBefore(P.find("space_layout_folder"), pm)
    pb = hou.ButtonParmTemplate("loadpreset", "Load Preset")
    pb.setScriptCallback("hou.phm().apply_preset(kwargs['node'], kwargs['node'].parm('preset').evalAsString())")
    pb.setScriptCallbackLanguage(hou.scriptLanguage.Python)
    pb.setHelp("Replaces the layer stack with the chosen preset.")
    P.insertAfter(P.find("preset"), pb)
    return P


HELP = '''= PF Spacescape =

#type: node
#context: cop
#internal: pf_spacescape
#icon: COP2/noise

"""Procedural space skybox: a stack of nebula noise, star, sun and gradient layers evaluated per direction, as HDR cubemap faces, cross or equirect."""

A port of Alex Peterson's Spacescape (MIT). Each layer is blended onto the ones below with Spacescape's
source/destination blend factors. Everything is computed from the 3D view direction, so the six cube faces and the
equirect agree exactly and there are no seams or pole pinching. Colours are real HDR values (stars and sun
go far above 1).

A new node comes with the *Purple Nebula* preset, so the first cook is already a space scene. Pick the *Output Layout* and *Face Size N* (equirect is 4N x 2N, cross 4N x 3N, a face N x N), or press *Bake*
to write 32-bit EXRs of all layouts at once. Layouts and conventions are the shared spacetools ones (pf_space_direction).

== Layer types ==
* *Noise*: fbm or ridged 3D noise, shelf/power/dither as in Spacescape, a two- or three-colour ramp.
* *Point Stars*: pixel-size stars, count/size/near-far colours, optional noise mask (density follows mask squared).
* *Billboard Stars*: fewer big flared stars sized by distance, optional diffraction spikes (replaces Spacescape's flare textures with a procedural flare).
* *Sun*: one flare at a direction with a core, halo and spikes.
* *Gradient*: a band or ramp along an axis (galactic plane).

== Blend factors ==
`one`/`one` adds. `src_alpha`/`one_minus_src_alpha` paints (use a black noise layer to carve dust lanes).

@parameters
    Output Layout:
        #id: layout
        Equirect, cube cross, or one cube face.
    Layers:
        #id: layers
        The layer stack (up to 12 layers).
    Bake EXR:
        #id: bake
        Writes faces, cross and equirect as float EXR.

'''


def create():
    if not hou.isUIAvailable():
        hou.hipFile.clear(suppress_save_prompt=True)
    if os.path.exists(OUTPUT_HDA):
        os.remove(OUTPUT_HDA)
    img = hou.node("/img") or hou.node("/").createNode("img", "img")
    copnet = img.createNode("copnet", "_build_ctx")
    subnet = copnet.createNode("subnet", "_build")
    ocl = subnet.createNode("opencl", "pf_spacescape_kernel")
    _configure(ocl)
    subnet.parm("outputs").set(1)
    subnet.parm("outputlabel1").set("color")
    subnet.parm("outputtype1").set(4)
    hda = subnet.createDigitalAsset(name=NAME, hda_file_name=OUTPUT_HDA, description="PF Spacescape",
                                    min_num_inputs=0, max_num_inputs=0, version="1")
    hda.allowEditingOfContents()
    kids = {n.name(): n for n in hda.children()}
    inner_ocl = kids["pf_spacescape_kernel"]
    inner_out = [n for n in hda.children() if n.type().name() in ("output", "output0", "outputs")][0]
    for slot in range(20):
        try:
            inner_out.setInput(slot, None)
        except Exception:
            break
    inner_out.setInput(0, inner_ocl, 0)
    const = hda.createNode("constant", "size_const")     # same size chain as pf_space_direction
    rs = hda.createNode("resample", "size_resample")
    rs.setInput(0, const)
    rs.parm("basesize").set(0)
    rs.parm("resolution1").setExpression('ch("../outresx")', language=hou.exprLanguage.Hscript)
    rs.parm("resolution2").setExpression('ch("../outresy")', language=hou.exprLanguage.Hscript)
    inner_ocl.setInput(0, rs)
    defn = hda.type().definition()
    defn.setParmTemplateGroup(_tmpl_group())
    defn.addSection("Help", HELP)
    sc.add_tab_submenu(defn)
    with open(os.path.join(HERE, "pf_spacescape_module.py"), "r", encoding="utf-8") as f:
        defn.addSection("PythonModule", f.read())
    defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
    defn.addSection("OnCreated", "kwargs['type'].hdaModule().on_created(kwargs['node'])")
    defn.setExtraFileOption("OnCreated/IsPython", True)
    defn.setExtraFileOption("PythonModule/IsPython", True)
    defn.setIcon("COP2_noise")
    defn.save(OUTPUT_HDA, template_node=hda)
    hda.destroy()
    copnet.destroy()
    d = hou.hda.definitionsInFile(OUTPUT_HDA)[0]
    assert d.embeddedHelp().strip()
    print("wrote", OUTPUT_HDA)


if __name__ == "__main__":
    create()
