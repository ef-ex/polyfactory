"""create_pf_space_direction_hda.py - build polyfactory/otls/pf_space_direction.hda (COP).

Shared spacetools infrastructure: per-pixel unit direction vector for an equirect / cube-cross /
single-cube-face layout. Contract: ideas/spacetools.md "## Shared: space_direction / cubemap".
Run:  hython devScripts/create_pf_space_direction_hda.py
"""
import hou, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import pf_space_common as sc

_PF = os.environ.get("POLYFACTORY", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "polyfactory"))
OUT = os.path.join(_PF, "otls", "pf_space_direction.hda").replace("\\", "/")

KERNEL = """#bind layer !size_ref?
#bind layer !&dir float3
#bind layer !&mask float
#bind parm layout int val=0
#bind parm face int val=0
#bind parm convention int val=0
""" + sc.PF_SPACE_DIR_CL + """
@KERNEL
{
    float4 r = pf_space_dir(@ix, @iy, @xres, @yres, @layout, @face, @convention);
    @dir.set(r.xyz);
    @mask.set(r.w);
}
"""

HELP = """= PF Space Direction =
#type: node
#context: cop
#icon: COP_subnet

"""  + "Per-pixel unit direction for an output layout: equirect (4N x 2N), cube cross (4N x 3N) or one cube face (N x N).\n\n" + """
@outputs

dir:
    #type: RGB. Unit direction vector (x,y,z) of the pixel centre; (0,0,0) outside the cross.

mask:
    #type: Mono. 1 where the pixel belongs to the layout, 0 in the empty corners of the cross.

@parms

Layout:
    Equirect, cube cross or single face.

Face Size N:
    Cube face size; equirect is 4N x 2N, cross 4N x 3N.

Convention:
    Houdini: equirect centre looks down -Z. Godot: equirect centre looks down +Z (engine source: u = atan2(x,-z)/2pi).

@related
- Contract and baking: ideas/spacetools.md "Shared: space_direction / cubemap".
"""


def populate(hda):
    const = hda.createNode("constant", "size_const")
    rs = hda.createNode("resample", "size_resample")
    rs.setInput(0, const)
    rs.parm("basesize").set(0)           # 0 = size from parms, not from the input
    rs.parm("resolution1").setExpression('ch("../outresx")', language=hou.exprLanguage.Hscript)
    rs.parm("resolution2").setExpression('ch("../outresy")', language=hou.exprLanguage.Hscript)
    ocl = hda.createNode("opencl", "space_direction_kernel")
    sc.configure_opencl(ocl, KERNEL,
        inputs=[("size_ref", 7, 1)], outputs=[("dir", 4), ("mask", 2)],
        bindings=[("layout", "layout", 0, 0), ("face", "face", 0, 0), ("convention", "convention", 0, 0)])
    ocl.setInput(0, rs)
    return [(ocl, 0), (ocl, 1)]


def ptg():
    g = hou.ParmTemplateGroup()
    g.append(sc.layout_parm_folder("Layout"))
    return g


if __name__ == "__main__":
    # subnet output type idx: 3 = RGB, 1 = Mono
    print("built", sc.make_cop_hda("pf_space_direction", "PF Space Direction", OUT, ptg(), populate,
                                   [("dir", 3), ("mask", 1)], HELP))
