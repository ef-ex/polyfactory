"""pf_space_common.py - build-time helpers shared by the spacetools COP HDAs.

Contract documented in ideas/spacetools.md "## Shared: space_direction / cubemap".
Import from a create_pf_*_hda.py script:

    sys.path.insert(0, os.path.dirname(__file__))
    import pf_space_common as sc
    sc.PF_SPACE_DIR_CL          # OpenCL source: pf_space_dir() - prepend to a kernel
    sc.layout_parm_folder()     # hou.FolderParmTemplate with layout/face/res/convention/outres
    sc.add_direction_node(subnet, opencl_node, input_index)   # inner pf_space_direction wired into an input
"""
import hou

LAYOUTS = ("Equirect (lat-long) 4N x 2N", "Cube cross 4N x 3N", "Single cube face N x N")
FACES = ("+X", "-X", "+Y", "-Y", "+Z", "-Z")
CONVENTIONS = ("Houdini (Y-up, centre = -Z)", "Godot (Y-up, centre = +Z)")

# One definition of direction-from-pixel, used by pf_space_direction itself and by any
# consumer kernel that prefers computing the direction inline (no layer read).
# float4 result: xyz = unit direction (0 if the pixel is outside the layout), w = 1 valid / 0 empty.
# layout 0 equirect, 1 cross, 2 face; face 0..5 = +X -X +Y -Y +Z -Z; conv 0 houdini, 1 godot.
PF_SPACE_DIR_CL = r"""
// ---- pf_space_dir: pixel -> unit direction (shared, see ideas/spacetools.md) ----
float3 pf_cube_face_dir(int face, float a, float b)   // a right, b DOWN, both in [-1,1]; OpenGL cube-face orientation
{
    float3 d;
    if      (face == 0) d = (float3)( 1.0f, -b, -a);
    else if (face == 1) d = (float3)(-1.0f, -b,  a);
    else if (face == 2) d = (float3)(  a, 1.0f,  b);
    else if (face == 3) d = (float3)(  a, -1.0f, -b);
    else if (face == 4) d = (float3)(  a, -b,  1.0f);
    else                d = (float3)( -a, -b, -1.0f);
    return normalize(d);
}
float4 pf_space_dir(int ix, int iy, int xres, int yres, int layout, int face, int conv)
{
    int row = yres - 1 - iy;                         // row 0 = TOP of the image (EXR order)
    if (layout == 0) {
        float u  = ((float)ix  + 0.5f) / (float)xres;
        float vt = ((float)row + 0.5f) / (float)yres;
        float phi = (conv == 1 ? u : u - 0.5f) * 6.28318530718f;
        float th  = vt * 3.14159265359f;
        float s = sin(th);
        return (float4)(s * sin(phi), cos(th), -s * cos(phi), 1.0f);
    }
    int N = (layout == 1) ? yres / 3 : xres;
    int cx = 0, cy = 0, f = face;
    if (layout == 1) {
        cx = ix / N; cy = row / N;
        if      (cx == 1 && cy == 0) f = 2;
        else if (cx == 0 && cy == 1) f = 1;
        else if (cx == 1 && cy == 1) f = 4;
        else if (cx == 2 && cy == 1) f = 0;
        else if (cx == 3 && cy == 1) f = 5;
        else if (cx == 1 && cy == 2) f = 3;
        else return (float4)(0.0f, 0.0f, 0.0f, 0.0f);
    }
    float a = ((float)(ix  - cx * N) + 0.5f) / (float)N * 2.0f - 1.0f;
    float b = ((float)(row - cy * N) + 0.5f) / (float)N * 2.0f - 1.0f;
    float3 d = pf_cube_face_dir(f, a, b);
    return (float4)(d.x, d.y, d.z, 1.0f);
}
// ---- end pf_space_dir ----
"""


def layout_parm_folder(label="Output Layout"):
    """Parms every consumer HDA exposes (names are the contract: layout, face, res, convention, outres)."""
    f = hou.FolderParmTemplate("space_layout_folder", label, folder_type=hou.folderType.Simple)
    f.addParmTemplate(hou.MenuParmTemplate("layout", "Layout", menu_items=("0", "1", "2"), menu_labels=LAYOUTS, default_value=0,
        help="Equirect: 4N x 2N. Cube cross: 4N x 3N (horizontal cross). Single face: N x N."))
    f.addParmTemplate(hou.MenuParmTemplate("face", "Face", menu_items=tuple(map(str, range(6))), menu_labels=FACES, default_value=0,
        conditionals={hou.parmCondType.DisableWhen: "{ layout != 2 }"}, help="Cube face for the single-face layout."))
    f.addParmTemplate(hou.IntParmTemplate("res", "Face Size N", 1, default_value=(512,), min=16, max=8192,
        min_is_strict=True, max_is_strict=False,
        help="Cube face size N in pixels. Equirect is 4N x 2N (N=512 -> 2048x1024, N=1024 -> 4096x2048)."))
    f.addParmTemplate(hou.MenuParmTemplate("convention", "Convention", menu_items=("0", "1"), menu_labels=CONVENTIONS, default_value=0,
        help="Engine convention for the equirect yaw. Both are Y-up with OpenGL cube-face orientation."))
    outres = hou.IntParmTemplate("outres", "Output Resolution", 2, default_value=(2048, 1024),
        conditionals={hou.parmCondType.DisableWhen: "{ layout >= 0 }"}, help="Resulting image size (read-only).")
    outres.setDefaultExpression(('ch("res")*(1+3*(ch("layout")<2))', 'ch("res")*(1+(ch("layout")==0)+2*(ch("layout")==1))'))
    outres.setDefaultExpressionLanguage((hou.scriptLanguage.Hscript,) * 2)
    f.addParmTemplate(outres)
    return f


def add_direction_node(subnet, ocl, input_index=0, name="space_direction"):
    """Create the inner pf_space_direction in `subnet`, link its layout parms to the same-named parms of
    the subnet (the HDA) and wire its `dir` output (index 0) into input `input_index` of `ocl`."""
    n = subnet.createNode("pf_space_direction", name)
    for p in ("layout", "face", "res", "convention"):
        n.parm(p).setExpression('ch("../%s")' % p, language=hou.exprLanguage.Hscript)
    ocl.setInput(input_index, n, 0)
    return n


# parm bindings for the opencl node of space_direction-like kernels: (kernel name, type 0 int/1 float)
def configure_opencl(ocl, kernel, inputs, outputs, bindings, expr_prefix="../"):
    """inputs: [(name, type_idx, optional)], outputs: [(name, opencl_type_idx)],
    bindings: [(kernel_name, hda_parm, 0|1, default)] -> int/float constants linked with ch()."""
    ocl.parm("kernelcode").set(kernel)
    ocl.parm("inputs").set(len(inputs))
    for i, (n, t, opt) in enumerate(inputs, 1):
        ocl.parm("input%d_name" % i).set(n); ocl.parm("input%d_type" % i).set(t); ocl.parm("input%d_optional" % i).set(int(opt))
    ocl.parm("outputs").set(len(outputs))
    for i, (n, t) in enumerate(outputs, 1):
        ocl.parm("output%d_name" % i).set(n); ocl.parm("output%d_type" % i).set(t)
    ocl.parm("bindings").set(len(bindings))
    for i, (k, h, bt, d) in enumerate(bindings, 1):
        ocl.parm("bindings%d_name" % i).set(k); ocl.parm("bindings%d_type" % i).set(bt)
        vp = ocl.parm("bindings%d_%s" % (i, "intval" if bt == 0 else "fval"))
        vp.set(int(d) if bt == 0 else float(d))
        vp.setExpression('ch("%s%s")' % (expr_prefix, h), language=hou.exprLanguage.Hscript)


def make_cop_hda(type_name, description, out_path, ptg, populate, outputs, help_text="", icon="COP_subnet", inputs=0, on_created=""):
    """Build a COP subnet HDA headless. populate(hda) creates the inner nodes and returns [(node, output_port)]
    feeding HDA output i. outputs: [(label, subnet_output_type_idx)] (0 ID,1 Mono,2 UV,3 RGB,4 RGBA)."""
    import os
    if os.path.exists(out_path):
        os.remove(out_path)
    if not hou.isUIAvailable():
        hou.hipFile.clear(suppress_save_prompt=True)
    img = hou.node("/img") or hou.node("/").createNode("img", "img")
    copnet = img.createNode("copnet", "_build_ctx")
    subnet = copnet.createNode("subnet", "_build")
    subnet.parm("outputs").set(len(outputs))      # output multiparm lives on the plain subnet, not on the asset
    for i, (label, t) in enumerate(outputs, 1):
        subnet.parm("outputlabel%d" % i).set(label)
        subnet.parm("outputtype%d" % i).set(t)
    hda = subnet.createDigitalAsset(name=type_name, hda_file_name=out_path, description=description,
                                    min_num_inputs=0, max_num_inputs=inputs, version="1")
    hda.allowEditingOfContents()
    for c in hda.children():
        c.destroy()
    out = hda.createNode("output", "OUT")
    for i, (node, port) in enumerate(populate(hda)):
        out.setInput(i, node, port)
    out.setDisplayFlag(True)
    hda.layoutChildren()
    defn = hda.type().definition()
    defn.setParmTemplateGroup(ptg)
    defn.setIcon(icon)
    if help_text:
        defn.addSection("Help", help_text)
    if on_created:
        defn.addSection("OnCreated", on_created)
        defn.setExtraFileOption("OnCreated/IsPython", True)
    defn.save(out_path, template_node=hda)
    hda.destroy(); copnet.destroy()
    return out_path
