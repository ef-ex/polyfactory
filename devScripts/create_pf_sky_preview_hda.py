"""create_pf_sky_preview_hda.py - build polyfactory/otls/pf_sky_preview.hda (SOP, type pf::sky_preview).

    hython devScripts/create_pf_sky_preview_hda.py

A big inward-facing sphere that wears a live Copernicus equirect (pf_nebula_generator, pf_spacescape, ...): the sky as seen
from the sphere's centre, in the 3D viewport. Native sphere + reverse + one vertex wrangle reading the COP with
texture("op:<path>"), so it follows the COP's parms with no bake. The COP must be in Equirect layout.
Equirect convention = pf_space_dir (Karma/USD lat-long, centre +Z, +X at u = 0.25).
"""
import os

import hou

HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
_POLYFACTORY = os.environ.get("POLYFACTORY", os.path.join(os.path.dirname(HERE), "polyfactory"))
OUTPUT_HDA = os.path.join(_POLYFACTORY, "otls", "pf_sky_preview.hda").replace("\\", "/")

SHELF = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="viewer">
      <contextNetType>SOP</contextNetType>
    </toolMenuContext>
    <toolMenuContext name="network">
      <contextOpType>$HDA_TABLE_AND_NAME</contextOpType>
    </toolMenuContext>
    <toolSubmenu>Poly Factory/Space</toolSubmenu>
    <script scriptType="python"><![CDATA[import soptoolutils

soptoolutils.genericTool(kwargs, '$HDA_NAME')]]></script>
  </tool>
</shelfDocument>
"""

# vertex wrangle: direction -> equirect uv exactly as pf_space_dir; u is made continuous per primitive so the seam column is clean
VEX = r'''
vector pn = normalize(@P);
float u = atan2(pn.x, -pn.z) / (2.0 * PI);
vector pc = normalize(prim_attrib_centroid(@primnum));
float uc = atan2(pc.x, -pc.z) / (2.0 * PI);
if (u - uc > 0.5) u -= 1.0; else if (uc - u > 0.5) u += 1.0;
float v = 1.0 - acos(clamp(pn.y, -1.0, 1.0)) / PI;        // texture() has v = 0 at the bottom row
vector col = {0, 0, 0};
string cop = chs("cop");
if (cop != "") col = texture("op:" + cop, u - floor(u), v);
col *= pow(2.0, chf("exposure"));
if (chi("tonemap")) col = col / (1.0 + col);
v@Cd = col;
v@uv = set(u, v, 0);
'''.replace("prim_attrib_centroid(@primnum)", "primuv(0, 'P', @primnum, {0.5, 0.5, 0})")

HELP = '''= PF Sky Preview =

#type: node
#context: sop
#internal: pf::sky_preview
#icon: SOP/sphere

"""A large sphere that shows a live Copernicus sky (PF Nebula Generator, PF Spacescape) as seen from its centre."""

*PF Nebula Generator* and *PF Spacescape* create one of these for you in `/obj` when you make the node. Put the viewport
camera inside the sphere (or just zoom in) to look around the sky. The sphere follows the COP live, no baking.

The COP must be in *Equirect* layout (the default). Cube cross and single face layouts do not map onto the sphere.

@parameters
    COP Node:
        #id: cop
        The Copernicus node to show (needs an equirect output).
    Radius:
        #id: radius
        Sphere size. Large, so that the camera can sit inside it.
    Exposure:
        #id: exposure
        Stops, multiplies the HDR sky before display.
    Tonemap:
        #id: tonemap
        Compress HDR values (c / (1 + c)) so bright stars do not clip to white.
    Rows / Columns:
        #id: rows
        Sphere resolution. More points = sharper preview.
'''


def create():
    if not hou.isUIAvailable():
        hou.hipFile.clear(suppress_save_prompt=True)
    if os.path.exists(OUTPUT_HDA):
        os.remove(OUTPUT_HDA)
    geo = hou.node("/obj").createNode("geo", "_build_ctx")
    sub = geo.createNode("subnet", "_build")
    hda = sub.createDigitalAsset(name="pf::sky_preview", hda_file_name=OUTPUT_HDA, description="PF Sky Preview",
                                 min_num_inputs=0, max_num_inputs=0, version="1.0")
    hda.allowEditingOfContents()
    for c in hda.children():
        c.destroy()
    sph = hda.createNode("sphere", "sphere")
    sph.parm("type").set(2)                       # polygon mesh
    sph.parm("rows").setExpression('ch("../rows")', language=hou.exprLanguage.Hscript)
    sph.parm("cols").setExpression('ch("../cols")', language=hou.exprLanguage.Hscript)
    sph.parm("orient").set(1)                     # Y axis
    for a in ("radx", "rady", "radz"):
        sph.parm("rad" + a[-1]).setExpression('ch("../radius")', language=hou.exprLanguage.Hscript)
    rev = hda.createNode("reverse", "face_inward")
    rev.setInput(0, sph)
    wr = hda.createNode("attribwrangle", "cop_to_color")
    wr.setInput(0, rev)
    wr.parm("class").set(3)                       # vertices: the seam column keeps its own colour
    wr.parm("snippet").set(VEX.replace('chs("', 'chs("../').replace('chi("', 'chi("../').replace('chf("', 'chf("../'))
    wr.setDisplayFlag(True)
    wr.setRenderFlag(True)
    hda.layoutChildren()

    ptg = hou.ParmTemplateGroup()
    s = hou.StringParmTemplate("cop", "COP Node", 1, string_type=hou.stringParmType.NodeReference,
                               tags={"opfilter": "!!COP!!", "oprelative": "."})
    s.setHelp("The Copernicus node to show, in Equirect layout.")
    ptg.append(s)
    ptg.append(hou.FloatParmTemplate("radius", "Radius", 1, default_value=(100.0,), min=1, max=10000,
                                     help="Large, so the viewport camera can sit inside the sphere."))
    ptg.append(hou.FloatParmTemplate("exposure", "Exposure", 1, default_value=(0.0,), min=-6, max=6,
                                     help="Stops; multiplies the HDR sky before display."))
    ptg.append(hou.ToggleParmTemplate("tonemap", "Tonemap", default_value=True,
                                      help="c / (1 + c): bright stars do not clip to white."))
    ptg.append(hou.IntParmTemplate("rows", "Rows", 1, default_value=(128,), min=8, max=2048, help="Sphere resolution."))
    ptg.append(hou.IntParmTemplate("cols", "Columns", 1, default_value=(256,), min=8, max=4096, help="Sphere resolution."))
    defn = hda.type().definition()
    defn.setParmTemplateGroup(ptg)
    defn.addSection("Help", HELP)
    defn.setIcon("SOP_sphere")
    defn.addSection("Tools.shelf", SHELF)
    defn.save(OUTPUT_HDA, template_node=hda)
    hda.destroy()
    geo.destroy()
    d = hou.hda.definitionsInFile(OUTPUT_HDA)[0]
    assert d.embeddedHelp().strip()
    print("wrote", OUTPUT_HDA)


if __name__ == "__main__":
    create()
