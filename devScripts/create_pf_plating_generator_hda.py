"""Create `pf_plating_generator` (pf::plating_generator) - spacetools tool #2a.

    hython devScripts/create_pf_plating_generator_hda.py

Recreates the plate-splitting half of the Blender add-on "Plating Generator and Greebles 2.0"
(how that tool works + every mapping/decision: ideas/spacetools.md "## Plating + greebles").
Surface in -> raised / sunk panel plates out.

Network, all native + VEX (VEX sources: devScripts/vex/pf_plating_*.vfl, embedded at build):

  in -> mark(_in) -> [subdivide bilinear] -> cut(detail VEX: groove edges, diagonal splits,
  irregular blobs) -> plates(detail VEX: union-find over non-groove edges, ids/area/heights,
  _split edge group) -> edgecusp -> [inset+sink polyextrude] -> raise+taper polyextrude ->
  parts -> [corner bevel] -> [rim bevel] -> groups/colour -> + rivets -> clean -> OUT

Python appears only in the Preset menu callback (UI marshalling: sets parameter values).
"""
import json
import os

import hou

_PF = os.environ.get("POLYFACTORY", "F:/projects/polyfactory-spacetools/polyfactory")
HERE = os.path.dirname(os.path.abspath(__file__)).replace("\\", "/")
HDA_PATH = os.path.join(_PF, "otls", "pf_plating_generator.hda").replace("\\", "/")
NAME = "pf_plating_generator"
LABEL = "PF Plating Generator"
BLENDER_PRESETS = "F:/cache/spacetools/plating/plating_greeble_gen/presets/panel"

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


def vex(name, common=False):
    s = open(f"{HERE}/vex/{name}.vfl", encoding="utf-8").read()
    if common:
        s = open(f"{HERE}/vex/pf_plating_common.vfl", encoding="utf-8").read() + "\n" + s
    return s


# ---------------------------------------------------------------------------
# parameters: (name, label, default, kwargs)
# ---------------------------------------------------------------------------
DEFAULTS = {
    "group": "",
    "pattern": "crisscross", "seed": 1, "subdiv": 2, "amount": 12.0, "triangle_amount": 20.0,
    "irregular_amount": 75.0, "rect_count": 10, "rect_w_min": 3, "rect_w_max": 6,
    "rect_h_min": 3, "rect_h_max": 6, "edge_group": "", "cut_by_angle": 1, "angle_limit": 90.0,
    "angle_dev": 0.1, "groove_width": 0.02, "groove_depth": 0.0, "height_min": 0.01,
    "height_max": 0.04, "height_seed": 1, "taper": 0.0, "bevel_amount": 0.0, "bevel_segments": 1,
    "corner_radius": 0.0, "corner_segments": 3, "floor": "keep", "rivets": 0, "rivet_dist": 0.05,
    "rivet_size": 0.02, "rivet_detail": 4, "random_color": 0,
}

PATTERNS = [
    ("crisscross", "Criss-Cross (random edge loops)"),
    ("triangles", "Criss-Cross + Triangles"),
    ("rectangles", "Rectangles"),
    ("rectangles_cuts", "Rectangles + Criss-Cross"),
    ("irregular", "Irregular Blobs"),
    ("edges", "From Edge Group"),
]


def parm_templates():
    P = hou
    def F(n, l, lo, hi, h, strict=False):
        t = P.FloatParmTemplate(n, l, 1, (DEFAULTS[n],), min=lo, max=hi, min_is_strict=strict)
        t.setHelp(h); return t
    def I(n, l, lo, hi, h, strict=True):
        t = P.IntParmTemplate(n, l, 1, (DEFAULTS[n],), min=lo, max=hi, min_is_strict=strict)
        t.setHelp(h); return t
    def T(n, l, h):
        t = P.ToggleParmTemplate(n, l, bool(DEFAULTS[n])); t.setHelp(h); return t
    def S(n, l, h):
        t = P.StringParmTemplate(n, l, 1, (DEFAULTS[n],)); t.setHelp(h); return t

    pat = P.MenuParmTemplate("pattern", "Panel Layout", tuple(p[0] for p in PATTERNS),
                             menu_labels=tuple(p[1] for p in PATTERNS), default_value=0)
    pat.setHelp("How the surface is cut into plates. Criss-Cross: random cuts along the face grid that "
                "stop when they meet another cut. Triangles: some cuts jump diagonally across a face, "
                "giving triangular plates. Rectangles: random W x H outlines. Irregular: wandering blobs. "
                "From Edge Group: the plates are bounded by the edges of the group named below.")
    preset = P.MenuParmTemplate("preset", "Preset", ("none",), menu_labels=("(choose a preset)",), default_value=0)
    preset.setHelp("Sets the parameters below to one of the Blender add-on's panel presets.")
    top = [
        preset,
        S("group", "Plate Only These Faces", "Faces to plate (blank = all). The rest of the surface passes through unchanged. "
          "Feed the output group pf_plate_top of one Plating Generator into the next to make Blender-style levels (big / medium / small plates)."),
    ]
    panels = P.FolderParmTemplate("f_panels", "Panels", folder_type=P.folderType.Simple)
    for t in (
        pat,
        I("subdiv", "Grid Subdivisions", 0, 5, "How many times every face is split into 4 before cutting. 0 uses your own faces as the cells; 3 gives 8 x 8 cells per face. More = smaller possible plates."),
        I("seed", "Seed", 0, 100000, "Changes the random layout.", strict=False),
        F("amount", "Cut Amount %", 0, 100, "How many random cuts are tried, as a share of all edges."),
        F("triangle_amount", "Triangle %", 0, 100, "Chance that a cut jumps diagonally across a face instead of going straight."),
        F("irregular_amount", "Blob Size Reduction %", 0, 100, "Irregular layout: higher = smaller blobs."),
        I("rect_count", "Rectangle Count", 0, 1000, "How many rectangle outlines are tried."),
        I("rect_w_min", "Rectangle Width Min", 1, 50, "In cells."), I("rect_w_max", "Rectangle Width Max", 1, 50, "In cells."),
        I("rect_h_min", "Rectangle Height Min", 1, 50, "In cells."), I("rect_h_max", "Rectangle Height Max", 1, 50, "In cells."),
        S("edge_group", "Edge Group", "Edges that bound the plates (layout: From Edge Group)."),
        T("cut_by_angle", "Cut At Sharp Edges", "Always put a groove where two faces meet at roughly the angle below (box edges)."),
        F("angle_limit", "Edge Angle", 0, 180, "Angle in degrees between face normals."),
        F("angle_dev", "Angle Tolerance", 0, 1, "Share of the angle accepted either side."),
    ):
        panels.addParmTemplate(t)
    plates = P.FolderParmTemplate("f_plates", "Plates", folder_type=P.folderType.Simple)
    for t in (
        F("groove_width", "Groove Width", 0, 1, "Gap between neighbouring plates."),
        F("groove_depth", "Groove Depth", 0, 1, "How far the groove floor sinks below the original surface."),
        F("height_min", "Plate Height Min", -1, 1, "Each plate gets a random height between min and max (negative sinks it)."),
        F("height_max", "Plate Height Max", -1, 1, "Set equal to min for flat heights."),
        I("height_seed", "Height Seed", 0, 100000, "Changes which plate gets which height.", strict=False),
        F("taper", "Plate Taper", 0, 1, "Inset of the plate top: slopes the plate sides."),
        F("bevel_amount", "Top Bevel", 0, 1, "Rounds the top edge of each plate."),
        I("bevel_segments", "Top Bevel Segments", 1, 10, "Smoothness of the top bevel."),
        F("corner_radius", "Corner Radius", 0, 1, "Rounds the vertical corners of each plate."),
        I("corner_segments", "Corner Segments", 1, 10, "Smoothness of rounded corners."),
    ):
        plates.addParmTemplate(t)
    fl = P.MenuParmTemplate("floor", "Groove Floor", ("keep", "remove"), menu_labels=("Keep (one surface)", "Remove (loose closed plates)"), default_value=0)
    fl.setHelp("Keep: the grooves stay as a surface between plates. Remove: only closed plates are output.")
    plates.addParmTemplate(fl)
    extras = P.FolderParmTemplate("f_extras", "Details", folder_type=P.folderType.Simple)
    for t in (
        T("rivets", "Rivets", "Add a rivet at every convex plate corner."),
        F("rivet_dist", "Distance From Corner", 0, 1, "How far in from the corner the rivet sits."),
        F("rivet_size", "Rivet Diameter", 0, 1, "Rivet size."),
        I("rivet_detail", "Rivet Detail", 3, 16, "Sphere rows/columns."),
        T("random_color", "Random Plate Color", "Writes a random Cd per plate."),
    ):
        extras.addParmTemplate(t)
    tabs = P.FolderParmTemplate("tabs", "Tabs", folder_type=P.folderType.Tabs)
    for f in (panels, plates, extras):
        tabs.addParmTemplate(f)
    ptg = P.ParmTemplateGroup()
    for t in top:
        ptg.append(t)
    ptg.append(tabs)
    return ptg


def level_seeds(pp, master):
    """Blender adds the preset's master_seed to every per-feature seed of a level (decorators.py)."""
    base = {"6": pp["ruby_dragon_random_seed"], "3": pp["rectangle_random_seed"]}.get(pp["pattern_type"], pp["random_seed"])
    return {"seed": base + master, "height_seed": pp["plate_height_random_seed"] + master}


def preset_data():
    """Blender level-0 panel presets mapped onto this HDA's parameters."""
    pm = {"0": "crisscross", "2": "triangles", "6": "irregular", "3": "rectangles", "4": "rectangles_cuts"}
    out = {}
    if not os.path.isdir(BLENDER_PRESETS):
        return out
    for fn in sorted(os.listdir(BLENDER_PRESETS), key=lambda s: (int(s.split(".")[0]))):
        d = json.load(open(f"{BLENDER_PRESETS}/{fn}"))
        L = d["levels"]
        pp = L[0]["plating_props"]
        key = os.path.splitext(fn)[0].split(". ", 1)[1].replace(" ", "_").replace("(", "").replace(")", "")
        if L[0]["type"] != "PlatingGeneratorDecorator":
            # level 0 is a GreebleDecorator (no plating): its plating_props are stale Blender leftovers, so the preset only resets to defaults
            out[key] = {"label": os.path.splitext(fn)[0] + "  [greebles only - no plating, use Greeble Scatter]", "values": {}}
            continue
        v = {
            "subdiv": pp["pre_subdivisions"],
            "pattern": pm.get(pp["pattern_type"], "crisscross"),
            "amount": pp["amount"], "triangle_amount": pp["triangle_percentage"],
            "irregular_amount": pp["ruby_dragon_percentage"], "groove_width": pp["groove_width"],
            "groove_depth": pp["groove_depth"], "height_min": pp["plate_min_height"],
            "height_max": pp["plate_max_height"], "taper": pp["plate_taper"],
            "bevel_amount": pp["bevel_amount"], "bevel_segments": pp["bevel_segments"],
            "corner_radius": pp["corner_width"], "corner_segments": pp["corner_bevel_segments"],
            "floor": "remove" if pp["remove_grooves"] else "keep", "rivets": int(pp["use_rivets"]),
            "rivet_dist": pp["rivet_corner_distance"], "rivet_size": pp["rivet_diameter"],
            "random_color": int(pp["add_vertex_colors_to_plates"]),
            "rect_count": pp["rectangle_amount"], "rect_w_min": pp["rectangle_width_min"],
            "rect_w_max": pp["rectangle_width_max"], "rect_h_min": pp["rectangle_height_min"],
            "rect_h_max": pp["rectangle_height_max"],
        }
        v.update(level_seeds(pp, d["master_seed"]))
        label = os.path.splitext(fn)[0]
        if len(L) > 1:
            label += "  (level 1 of %d - chain more plating nodes on pf_plate_top; later levels: %s)" % (
                len(L), ", ".join("%s%d subdiv %d" % ("L" if l["type"].startswith("Plat") else "G", i + 2, l["plating_props"]["pre_subdivisions"]) for i, l in enumerate(L[1:])))
        if "Greebles" in fn or "City" in fn:
            label += "  [plates only - add Greeble Scatter]"
        out[key] = {"label": label, "values": v}
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
            if isinstance(v, str) and v.startswith("`"):
                nd.parm(k).set(v)
            elif isinstance(v, str) and v.startswith("ch("):
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

    inp0 = hda.indirectInputs()[0]
    # packed prims are unpacked and plated like normal geometry (the unpack only cooks when there are packed prims: no warning)
    probe = wr("pack_probe", inp0, 'int k = 0; for (int p = 0; p < nprimitives(0); p++) if (primintrinsic(0, "typename", p) == "PackedGeometry") k = 1; i@_npk = k;', 0)
    unp = node("unpack", "unpack_packed", probe)
    inp = node("switch", "unpack_input", probe, unp)
    inp.parm("input").setExpression("detail('../pack_probe', '_npk', 0)")
    dfl = wr("defaults", inp,
             'if (!hasattrib(0, "prim", "pf_plate_id")) setprimattrib(0, "pf_plate_id", @primnum, -1, "set");'+"\n"+
             'if (!hasattrib(0, "prim", "pf_plate_area")) setprimattrib(0, "pf_plate_area", @primnum, 0.0, "set");'+"\n"+
             'if (!hasattrib(0, "prim", "pf_plate_height")) setprimattrib(0, "pf_plate_height", @primnum, 0.0, "set");', 1)
    mark = wr("mark", dfl, "i@_in = 1;", 1, group="`chs('../group')`")
    # non-quad faces (tris, ngons incl. concave) are triangulated, then at least one bilinear level
    # turns everything into quads (bilinear on a concave ngon makes degenerate quads, so no ngons reach it)
    prep = wr("prep", mark, 'int nq = 0; for (int p = 0; p < nprimitives(0); p++) { int c = primvertexcount(0, p); if (c != 4) nq = 1; setprimgroup(0, "_ngon", p, c > 4, "set"); } i@_nq = nq;', 0)
    tri = node("divide", "triangulate_ngons", prep, group="_ngon", convex=1, usemaxsides=1, numsides=3)
    sub = node("subdivide", "subdivide", tri, algorithm=4)
    sub.parm("iterations").setExpression("max(ch('../subdiv'), detail('../prep', '_nq', 0))")
    sw0 = node("switch", "subdiv_on", tri, sub)
    sw0.parm("input").setExpression("max(ch('../subdiv'), detail('../prep', '_nq', 0)) > 0")
    cut = wr("cut", sw0, vex("pf_plating_cut", True), 0)
    plates = wr("plates", cut, vex("pf_plating_plates"), 0)
    cusp = node("edgecusp", "cusp", plates, group="_split", updatenorms=0)
    # ex1: groove ring (inset) + sink
    ex1 = node("polyextrude::2.0", "groove_ring", cusp, group="_plated", splittype=1,
                              outputfront=1, outputside=1, outputsidegrp=1, sidegrp="_groove", outputfrontgrp=1, frontgrp="_front1")
    ex1.parm("dist").setExpression("-ch('../groove_depth')")
    ex1.parm("inset").setExpression("ch('../groove_width')*0.5")
    nog = wr("no_groove", cusp, 'setprimgroup(0,"_groove",@primnum,0,"set"); setprimgroup(0,"_front1",@primnum,inprimgroup(0,"_plated",@primnum),"set");', 1)
    sw1 = node("switch", "ring_on", nog, ex1)
    sw1.parm("input").setExpression("ch('../groove_width') > 0 || ch('../groove_depth') > 0")
    # plates of zero height (height + groove depth = 0) get no side walls: they stay flat (zero-area sides would be non-manifold)
    flat = wr("flat_plates", sw1, 'int fl = inprimgroup(0, "_front1", @primnum) && abs(f@_zs) < 1e-6; setprimgroup(0, "_flat", @primnum, fl, "set"); if (fl) setprimgroup(0, "_front1", @primnum, 0, "set"); if (@primnum == 0) { foreach (string g; {"_top", "_side", "_bottom"}) setprimgroup(0, g, 0, 0, "set"); }', 1)
    # ex2: raise + taper
    ex2 = node("polyextrude::2.0", "raise", flat, group="_front1", splittype=1, dist=1.0,
               uselocalzscaleattrib=1, localzscaleattrib="_zs", 
               outputfront=1, outputfrontgrp=1, frontgrp="_top", outputside=1, outputsidegrp=1,
               sidegrp="_side", outputback=0, outputbackgrp=1, backgrp="_bottom")
    ex2.parm("inset").setExpression("ch('../taper')")
    ex2.parm("outputback").setExpression("strcmp(chs('../floor'),'remove')==0")
    parts = wr("parts", ex2,
               'i@_part = (inprimgroup(0,"_top",@primnum) || inprimgroup(0,"_flat",@primnum)) ? 1 : inprimgroup(0,"_side",@primnum) ? 2 : '
               'inprimgroup(0,"_groove",@primnum) ? 3 : inprimgroup(0,"_bottom",@primnum) ? 4 : 0;', 1)
    eg2 = wr("edges_rim", parts, vex("pf_plating_edgegroups"), 0)
    bev2 = node("polybevel::3.0", "rim_bevel", eg2, grouptype=2, group="_rim", filletshape=4)
    bev2.parm("divisions").setExpression("ch('../bevel_segments')")
    bev2.parm("offset").setExpression("min(ch('../bevel_amount'), 0.45 * abs(min(ch('../height_min'), ch('../height_max')) + ch('../groove_depth')))")
    sw3 = node("switch", "rim_on", eg2, bev2)
    sw3.parm("input").setExpression("ch('../bevel_amount') > 0 && detail('../edges_rim', '_nrim', 0) > 0")
    eg1 = wr("edges_corner", sw3, vex("pf_plating_edgegroups"), 0)
    bev1 = node("polybevel::3.0", "corner_bevel", eg1, grouptype=2, group="_corner", filletshape=4)
    bev1.parm("divisions").setExpression("ch('../corner_segments')")
    bev1.parm("offset").setExpression("ch('../corner_radius')")
    bev1.parm("useoffsetscale").set(1); bev1.parm("pointscaleattr").set("_bs")   # per-corner cap from the wall width (edgegroups)
    sw2 = node("switch", "corner_on", eg1, bev1)
    sw2.parm("input").setExpression("ch('../corner_radius') > 0 && detail('../edges_corner', '_ncorner', 0) > 0")
    fix = wr("corner_fillets_are_sides", sw2, 'if (i@_part == 0) i@_part = 2;', 1)
    # floor removal
    rm = node("blast", "drop_groove", fix, group="_groove", grouptype=4, negate=0, removegrp=0)
    sw4 = node("switch", "floor_remove", fix, rm)
    sw4.parm("input").setExpression("strcmp(chs('../floor'),'remove')==0")
    nanm = wr("nan_mark", sw4, 'setpointgroup(0, "_nan", @ptnum, isnan(@P.x) || isnan(@P.y) || isnan(@P.z), "set"); if (@ptnum == 0) setpointgroup(0, "_nan", 0, isnan(@P.x) || isnan(@P.y) || isnan(@P.z), "set");', 2)
    nanb = node("blast", "nan_drop", nanm, group="_nan", grouptype=3, negate=0, removegrp=0)   # degenerate bevels on pole-tight facets can yield NaN points: drop them, never ship NaN
    sw4 = nanb
    fin = wr("finalize", sw4,
             'int pt = i@_part;\n'
             'setprimgroup(0,"pf_plate_top",@primnum, pt==1,"set");\n'
             'setprimgroup(0,"pf_plate_side",@primnum, pt==2,"set");\n'
             'setprimgroup(0,"pf_plate_groove",@primnum, pt==3,"set");\n'
             'setprimgroup(0,"pf_plate_bottom",@primnum, pt==4,"set");\n'
             , 1)
    # rivets: points at convex top corners, taken before the bevels so a corner is still one top face
    riv = wr("rivet_points", parts, vex("pf_plating_rivets"), 0)
    rpts = node("blast", "only_rivet_points", riv, group="_rivpt", grouptype=3, negate=1)
    ball = node("sphere", "rivet_ball", type=1)
    ball.parm("type").set(1)  # polygon
    ball.parm("rows").setExpression("ch('../rivet_detail')")
    ball.parm("cols").setExpression("ch('../rivet_detail')*2")
    ball.parm("orient").set(2)
    cp = node("copytopoints::2.0", "rivet_copies", ball, rpts)
    cp.parm("targetattribs").set(0) if cp.parm("targetattribs") else None
    rid = wr("rivet_attrs", cp,
             'int pp = primpoint(0,@primnum,0);\n'
             'setprimgroup(0,"pf_plate_rivet",@primnum,1,"set");\n'
             'i@pf_plate_id = point(0,"_pid",pp); f@pf_plate_height = point(0,"_h",pp); f@pf_plate_area = point(0,"_a",pp);\n'
             'i@_part = 5; i@_plate = i@pf_plate_id; i@_in = 0; f@_zs = 0;', 1)
    rbs = wr("rivet_bs", rid, "f@_bs = 1.0;", 2)   # same point attributes as the plates, so the merge does not warn
    mrg = node("merge", "merge_rivets", fin, rbs)
    sw5 = node("switch", "rivets_on", fin, mrg)
    sw5.parm("input").setExpression("ch('../rivets')")
    col = wr("plate_color", sw5, 'if (i@_plate < 0 || i@_part <= 0) return; float k = float(i@pf_plate_id) * 0.37 + float(chi("../height_seed")) * 1.7; float cr = rand(k); float cg = rand(k + 7.31); float cb = rand(k + 13.7); v@Cd = set(cr, cg, cb) * 0.8 + 0.2;', 1)
    swc = node("switch", "color_on", sw5, col)
    swc.parm("input").setExpression("ch('../random_color')")
    cur = swc
    for cname, cls, flag in (("pt", 2, "doptdel"), ("vtx", 3, "dovtxdel"), ("prim", 1, "doprimdel"), ("dtl", 0, "dodtldel")):
        gd = wr("guard_" + cname, cur, "i@_g = 0;", cls)       # makes sure the delete below always has a match
        cur = node("attribdelete", "clean_" + cname, gd, **{flag: 1, {"doptdel": "ptdel", "dovtxdel": "vtxdel", "doprimdel": "primdel", "dodtldel": "dtldel"}[flag]: "_*"})
    clean = cur
    gguard = wr("gguard", clean, 'if (nprimitives(0) > 0) setprimgroup(0, "_g", 0, 0, "set"); if (npoints(0) > 0) setpointgroup(0, "_g", 0, 0, "set");', 0)
    gclean = node("groupdelete", "clean_groups", gguard)
    gclean.parm("deletions").set(1)
    gclean.parm("group1").set("_*")
    gclean.parm("grouptype1").set(0)  # guess; fixed below
    ing = wr("guard_pass", inp, "i@_g = 0;", 0)
    inpc = node("attribdelete", "clean_pass", ing, dodtldel=1, dtldel="_*")
    swe = node("switch", "empty_passthru", gclean, inpc)     # nothing to plate: pass the input through, no group warnings
    swe.parm("input").setExpression("npoints('../unpack_input') == 0")
    out = node("null", "OUT", swe)
    out.setDisplayFlag(True); out.setRenderFlag(True)
    hda.layoutChildren()

    ptg = parm_templates()
    defn.setParmTemplateGroup(ptg)

    pd = {"defaults": DEFAULTS, "presets": preset_data()}
    defn.addSection("presets.json", json.dumps(pd))
    # preset menu items + callback
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

    hda.setUserData("nodeshape", "chevron_down")
    defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
    opts = defn.options(); opts.setUnlockNewInstances(False); defn.setOptions(opts)
    defn.save(HDA_PATH, template_node=hda)
    d = hou.hda.definitionsInFile(HDA_PATH)[0]
    d.addSection("Tools.shelf", TOOLS_SHELF)
    hda.destroy(); build_geo.destroy()
    print("wrote " + HDA_PATH)


build()
