"""Create `pf::starship_generator` - a procedural starship, as a SOP HDA.

    hython devScripts/create_pf_starship_generator_hda.py

Recreation of the Blender "Starship Generator 1.1.0" geometry-node tool.
How the original works and how each stage maps to a node here:
ideas/spacetools.md, section "Starship generator". No inputs.

    PART CHAIN (built three times: hull / medium parts / small parts)
      box -> shape wrangle (jiggle + random scale) -> extsel (noise picks
      faces) -> polyextrude (random individual extrusion) -> taper wrangle ->
      vdbfrompolygons+convertvdb (= Blender's Remesh) -> [mirror, hull only]
      -> keep largest island -> centre -> crease wrangle -> subdivide ->
      tag.  Inside one For-Each block (count = number of variants).
    SHIP
      hull -> scatter+copytopoints medium parts on the hull
           -> scatter+copytopoints small parts on hull + medium parts
           -> panels (3 layers of grid-cell extrusion)
           -> booster (ray from the rear, copytopoints)
           -> clip x>=0 + mirror + weld -> resize to Length -> normals
           -> `_*` cleanup -> OUT

Python is used ONLY here, to build the network and the parameter interface.
Every per-point/per-prim operation is a native node or VEX.
"""

import os
import re

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory-spacetools/polyfactory")
HDA_PATH = os.path.join(_POLYFACTORY, "otls", "pf_starship_generator.hda").replace("\\", "/")
NAME = "pf::starship_generator"
TAB_LABEL = "PF Starship Generator"
OUTPUT_LABEL = "Starship"
ICON = "SOP_copytopoints"

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

HELP = """= PF Starship Generator =

#icon: SOP/copytopoints

\"\"\"A random, symmetric starship built from a smoothed hull, scattered armour
parts, raised hull panels and engines.\"\"\"

Press Create and you get a ship; change the Seed for another one. Nothing needs
to be wired in.

== Overview ==

The hull is a stretched box whose faces are randomly pushed out, then melted
together and smoothed (the Detail setting controls how coarse the melt is). Medium and small parts
- built the same way, just smaller - are scattered over the hull and over each other.
Panels are raised patches on a grid. A booster is shot onto the rear of the
ship from behind. The right half is mirrored to the left, and the result is
resized to Length.

== Output attributes ==
|| Name || Class || What ||
| pf_part | primitive int | 0 hull, 1 medium part, 2 small part, 3 booster |
| pf_panel | primitive int | 0 plain, 1 large, 2 small, 3 micro panel |
| pf_material | primitive string | `hull` or `booster`, for a shader switch |
| N | vertex | shading normals, split at Smooth Angle |

@parameters

    Seed:
        #id: seed
        Every random choice in the ship.
"""

# --------------------------------------------------------------------------
# VEX
# --------------------------------------------------------------------------
SEEDLINE = 'float sd = ch("../seed") + %(off)d + 13.0 * detail(1, "iteration", 0);\n'

SHAPE_VEX = SEEDLINE + r'''// jiggle: each axis coordinate is scaled by a noise of ITSELF (a lumpy profile
// along that axis - Blender: Starship: Jiggle X/Y/Z), then a random per-axis
// scale (Random Vector), as in Random Extrusion Nodes.
float j = chf("../jiggle");
vector p = @P;
vector q = p;
int ax[] = {1, 0, 2};
foreach (int k; ax) {
    float n = noise(set(p[k], sd * 0.731 + k * 5.17, 1.37));
    q[k] = p[k] * (1.0 + j * (2.0 * n - 1.0));
}
vector lo = set(chf("../width1"), chf("../height1"), chf("../hlength1"));
vector hi = set(chf("../width2"), chf("../height2"), chf("../hlength2"));
vector r = set(rand(sd + 0.11), rand(sd + 0.23), rand(sd + 0.37));
@P = q * lerp(lo, hi, r);
'''

EXTSEL_VEX = SEEDLINE + r'''// noise mask picks the faces to extrude, a random distance and taper each
// (Blender: Starship: Random Extrude).
vector c = 0;
int pts[] = primpoints(0, @primnum);
foreach (int pt; pts) c += point(0, "P", pt);
c /= len(pts);
float n = noise(c * 0.5 + set(0.0, 0.0, sd * 0.37));
float m = clamp(fit(n, 0.382, 0.658, 0.0, 1.0), 0.0, 1.0);
i@group__sel = m < chf("../ext_amount");
f@zscale = lerp(chf("../ext1"), chf("../ext2"), rand(sd + @primnum * 0.713 + 1.0));
f@_tap = lerp(chf("../tap1"), chf("../tap2"), rand(sd + @primnum * 0.419 + 2.0));
'''

TAPER_VEX = r'''// Scale Elements: scale each extruded top face about its centre.
vector c = 0;
int pts[] = primpoints(0, @primnum);
foreach (int pt; pts) c += point(0, "P", pt);
c /= len(pts);
foreach (int pt; pts)
    setpointattrib(0, "P", pt, c + (point(0, "P", pt) - c) * f@_tap);
'''

ISLAND_VEX = r'''// Cleanup: keep only the biggest island (Blender keeps island 0; "biggest" is the
// robust version of that).
int n = nuniqueval(0, "prim", "_isl");
int cnt[];
resize(cnt, max(n, 1));
for (int i = 0; i < nprimitives(0); i++) cnt[prim(0, "_isl", i)]++;
int best = 0;
for (int i = 1; i < n; i++) if (cnt[i] > cnt[best]) best = i;
i@_best = best;
'''

ISLAND_DEL_VEX = r'''if (i@_isl != detail(0, "_best", 0)) removeprim(0, @primnum, 1);'''

CREASE_VEX = SEEDLINE + r'''// noise-driven edge crease, per vertex = the edge to the NEXT vertex of the face
// (Blender: Starship: Creased Subdivide).
int pr = vertexprim(0, @vtxnum);
int idx = vertexprimindex(0, @vtxnum);
int nv = primvertexcount(0, pr);
vector a = point(0, "P", vertexpoint(0, @vtxnum));
vector b = point(0, "P", vertexpoint(0, primvertex(0, pr, (idx + 1) %% nv)));
float n = noise((a + b) * 0.5 * chf("../crease_scale") + set(0.0, 0.0, sd * 0.53));
float r = clamp(fit(n, 0.389, 0.615, 0.0, 1.0), 0.0, 1.0);
// Blender crease 1 = sharp for ever; OpenSubdiv sharpness counts levels. x3 = LOOKED AT: matches the reference's boxy parts.
f@creaseweight = lerp(chf("../crease1"), chf("../crease2"), r) * %(levels)s * 3.0;
'''

TAG_VEX = r'''i@pf_part = %(part)d;
i@pf_panel = 0;
i@_variant = detail(1, "iteration", 0);
'''

SCATTER_XF_VEX = r'''// one transform per scattered point: which variant, scale, push along the
// normal, random rotation in steps (Blender: Starship: Shape Distribution).
float sd = ch("../seed") + %(off)d + @ptnum * 0.0001;
int nvar = max(chi("../variants"), 1);
i@_variant = min(int(rand(@ptnum * 7.31 + sd) * nvar), nvar - 1);
float s = lerp(chf("../%(pfx)s_scale1"), chf("../%(pfx)s_scale2"), rand(@ptnum * 3.17 + sd + 1.0));
float off = lerp(chf("../%(pfx)s_offset1"), chf("../%(pfx)s_offset2"), rand(@ptnum * 5.11 + sd + 2.0));
vector nn = normalize(v@N);
@P += nn * off;
vector step = set(chf("../rot_step1"), chf("../rot_step2"), chf("../rot_step3"));
vector ang = set(floor(rand(@ptnum * 1.7 + sd + 3.0) * 4.0), floor(rand(@ptnum * 2.9 + sd + 4.0) * 4.0),
                 floor(rand(@ptnum * 4.3 + sd + 5.0) * 4.0));
p@orient = eulertoquaternion(radians(ang * step), XFORM_XYZ);
f@pscale = s;
'''

PANEL_VEX = r'''// one panel layer: faces are binned into grid cells (Blender: Voronoi with Randomness 0
// = a plain grid); a hash per cell decides if the cell is raised.
vector c = 0;
int pts[] = primpoints(0, @primnum);
foreach (int pt; pts) c += point(0, "P", pt);
c /= len(pts);
float cs = chf("../panel_size") * %(cell)g;
vector prop = set(chf("../panel_prop1"), chf("../panel_prop2"), chf("../panel_prop3"));
vector cell = floor(c / (cs * prop));
float h = rand(cell.x * 7.13 + cell.y * 3.11 + cell.z * 5.17 + ch("../seed") * 0.37 + %(salt)g);
int sel = h < chf("../panel_amount") && primintrinsic(0, "measuredarea", @primnum) > 1e-5;
i@group__pnl = sel;
if (sel) i@pf_panel = %(layer)d;
'''

BOOST_SRC_VEX = r'''// one point behind (or in front of) the ship on the booster's line
float z = chi("../booster_flip") ? -100.0 : 100.0;
addpoint(0, set(chf("../booster_proj1"), chf("../booster_proj2"), z));
'''

BOOST_HIT_VEX = r'''// Raycast: along z onto the ship; no hit, no booster
vector org = @P;
vector dir = set(0.0, 0.0, -sign(org.z) * 500.0);
vector hit;
vector uvw;
int pr = intersect(1, org, dir, hit, uvw);
if (pr < 0) { removepoint(0, @ptnum); return; }
@P = hit + set(chf("../booster_off1"), chf("../booster_off2"), chf("../booster_off3"));
p@orient = quaternion(chi("../booster_flip") ? 3.14159265 : 0.0, set(0.0, 1.0, 0.0));
f@pscale = chf("../booster_scale");
'''

BOOST_CAP_VEX = r'''// the end cap facing +z
int ok = 1;
foreach (int pt; primpoints(0, @primnum)) { vector pp = point(0, "P", pt); if (pp.z < 1.49) ok = 0; }
i@group__cap = ok;
'''

# --------------------------------------------------------------------------
# build helpers
# --------------------------------------------------------------------------
net = None


def mk(typ, name, x, y, *ins, parms=None, expr=None, comment=None):
    n = net.createNode(typ, name)
    n.setPosition(hou.Vector2(x, y))
    for i, src in enumerate(ins):
        if src is not None:
            n.setInput(i, src)
    for k, v in (parms or {}).items():
        n.parm(k).set(v)
    for k, v in (expr or {}).items():
        n.parm(k).setExpression(v)
    if comment:
        n.setComment(comment)
        n.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return n


def wrangle(name, x, y, cls, snippet, *ins, group="", comment=None):
    return mk("attribwrangle", name, x, y, *ins,
              parms={"class": cls, "snippet": snippet, "group": group}, comment=comment)


def switch(name, x, y, a, b, cond, comment=None):
    """a when cond is 0, b otherwise."""
    return mk("switch", name, x, y, a, b, expr={"input": cond}, comment=comment)


SCAFFOLD_VEX = r'''// give every class something to delete, so the sweep below never warns "no match"
if (npoints(0) > 0) {
    setvertexattrib(0, "_s", 0, 0, 0);
    setvertexattrib(0, "creaseweight", 0, 0, 0.0);
    setprimattrib(0, "_s", 0, 0);
    setprimattrib(0, "name", 0, "");
}
setdetailattrib(0, "_s", 0);
'''


def sweep(name, x, y, src):
    """Scaffold + delete every `_*` (all four classes) and the node-required leftovers."""
    sc = wrangle(name + "_scaffold", x, y, "detail", SCAFFOLD_VEX, src)
    sc = wrangle(name + "_scaffold2", x, y - 1, "point", "i@_s = 0;", sc)
    d = mk("attribdelete", name, x, y - 2, sc, parms={"ptdel": "_*", "vtxdel": "_* creaseweight",
                                                      "primdel": "_* name", "dtldel": "_*"},
           comment="`_*` is internal (conventions 2); creaseweight/name are node leftovers.")
    return d


def part_chain(p, x, seedoff, count_parm, subdiv_parm, part, is_hull):
    """One For-Each block that builds `count_parm` variants of one part class."""
    y = 30
    box = mk("box", p + "_box", x, y, parms={"type": "polymesh", "divrate1": 5, "divrate2": 5, "divrate3": 5,
                                             "sizex": 2, "sizey": 2, "sizez": 2},
             comment="Blender: a 2 m cube, subdivided twice (4 x 4 per side).")
    begin = mk("block_begin", p + "_begin", x, y - 1, box, parms={"method": "input"})
    meta = mk("block_begin", p + "_meta", x + 2.5, y - 1, parms={"method": "metadata"})
    end = mk("block_end", p + "_end", x, y - 19)
    begin.parm("blockpath").set("../" + end.name())
    meta.parm("blockpath").set("../" + end.name())
    end.parm("blockpath").set("../" + begin.name())
    end.parm("templatepath").set("../" + begin.name())
    end.parm("itermethod").set("count")
    end.parm("method").set("merge")
    end.parm("iterations").setExpression('ch("../%s")' % count_parm)
    fmt = {"off": seedoff}

    shape = wrangle(p + "_shape", x, y - 2, "point", SHAPE_VEX % fmt, begin, meta,
                    comment="Jiggle + random scale.")
    extsel = wrangle(p + "_extsel", x, y - 3, "primitive", EXTSEL_VEX % fmt, shape, meta,
                     comment="Noise picks faces; distance + taper per face.")
    ext = mk("polyextrude::2.0", p + "_extrude", x, y - 4, extsel,
             parms={"group": "_sel", "splittype": "elements", "dist": 1.0, "localattribs": 1,
                    "uselocalzscaleattrib": 1, "usethicknessattrib": 0, "outputfrontgrp": 1,
                    "frontgrp": "extrudeFront", "outputside": 1},
             comment="Individual extrude along the face normal; distance from zscale.")
    taper = wrangle(p + "_taper", x, y - 5, "primitive", TAPER_VEX, ext, group="extrudeFront",
                    comment="Scale each extruded top face (taper).")
    vdb = mk("vdbfrompolygons", p + "_vdb", x, y - 6, taper,
             parms={"builddistance": 1, "buildfog": 0, "fillinterior": 1, "exteriorbandvoxels": 3,
                    "interiorbandvoxels": 3, "useworldspaceunits": 1},
             expr={"voxelsize": 'max(max(bbox(opinputpath(".", 0), D_XSIZE), bbox(opinputpath(".", 0), D_YSIZE)), '
                                'bbox(opinputpath(".", 0), D_ZSIZE)) / (0.9 * pow(2, ch("../detail")))'},
             comment="Remesh: voxel = longest side / (0.9 * 2^Detail), as Blender's octree depth.")
    conv = mk("convertvdb", p + "_conv", x, y - 7, vdb,
              parms={"conversion": "poly", "adaptivity": 0.0},
              comment="Back to polygons (smooth remesh).")
    if is_hull:
        mir = mk("mirror", p + "_mirror", x, y - 8, conv,
                 parms={"operation": "clip", "dirx": 1, "diry": 0, "dirz": 0, "keepOriginal": 1,
                        "consolidatepts": 1, "consolidatetol": 0.001, "reversenml": 1},
                 comment="Keep one half, mirror it (Blender: Mirror modifier with bisect).")
        mirsw = switch(p + "_mirsw", x, y - 9, conv, mir, 'ch("../mirror")')
        prev = mirsw
    else:
        prev = conv
    conn = mk("connectivity", p + "_conn", x, y - 10, prev,
              parms={"connecttype": "prim", "attribname": "_isl"})
    isl = wrangle(p + "_island", x, y - 11, "detail", ISLAND_VEX, conn,
                  comment="Cleanup: biggest island only.")
    isl2 = wrangle(p + "_islanddel", x, y - 12, "primitive", ISLAND_DEL_VEX, isl)
    cen = mk("matchsize", p + "_center", x, y - 13, isl2,
             parms={"justifytarget": "origin", "doscale": 0},
             comment="Center Nodes: bounding box centre to the origin.")
    cre = wrangle(p + "_crease", x, y - 14, "vertex", CREASE_VEX % dict(fmt, levels='ch("../%s")' % subdiv_parm),
                  cen, meta, comment="Noise-driven edge crease.")
    sub = mk("subdivide", p + "_subd", x, y - 15, cre,
             parms={"algorithm": "osdcc"}, expr={"iterations": 'max(ch("../%s"), 1)' % subdiv_parm},
             comment="Catmull-Clark honouring creaseweight.")
    subsw = switch(p + "_subsw", x, y - 16, cre, sub, 'ch("../%s") > 0' % subdiv_parm,
                   "Level 0 = no subdivision.")
    tag = wrangle(p + "_tag", x, y - 17, "primitive", TAG_VEX % {"part": part}, subsw, meta)
    end.setInput(0, tag)
    return end


def scatter_parts(p, x, y, src, variants, density_parm, off, comment):
    """Scatter points on `src`, copy random variants onto them, merge with `src`."""
    sc = mk("scatter::2.0", p + "_scatter", x, y, src,
            parms={"generateby": "bydensity", "forcetotal": 0, "relaxpoints": 0},
            expr={"densityscale": 'ch("../%s")' % density_parm, "seed": 'ch("../seed") + %d' % off},
            comment=comment)
    xf = wrangle(p + "_xf", x, y - 1, "point", SCATTER_XF_VEX % {"off": off, "pfx": p}, sc)
    cp = mk("copytopoints::2.0", p + "_copy", x + 2.5, y - 2, variants, xf,
            parms={"useidattrib": 1, "idattrib": "_variant", "pack": 0})
    mg = mk("merge", p + "_merge", x, y - 3, src, cp)
    return mg


def build():
    global net
    out = net.node("OUT")

    # ---- part chains ---------------------------------------------------
    hull_end = part_chain("hull", -14, 1, "one", "subdiv_hull", 0, True)
    med_end = part_chain("med", 0, 100, "variants", "subdiv_med", 1, False)
    small_end = part_chain("small", 14, 200, "variants", "subdiv_small", 2, False)
    # the hull block runs once
    hull_end.parm("iterations").deleteAllKeyframes()
    hull_end.parm("iterations").set(1)

    # ---- scatter -------------------------------------------------------
    s1 = scatter_parts("med", -6, 4, hull_end, med_end, "med_density", 7,
                       "Medium parts on the hull.")
    s2 = scatter_parts("small", -6, -2, s1, small_end, "small_density", 8,
                       "Small parts on hull + medium parts (Blender's second Scatter Object modifier).")

    # ---- panels --------------------------------------------------------
    y = -9
    psub = mk("subdivide", "panel_subd", -6, y, s2,
              parms={"algorithm": "osdbilinear"}, expr={"iterations": 'ch("../panel_subdiv")'},
              comment="Linear split so panels have enough faces (Blender: Subdivide Mesh).")
    psw = switch("panel_subsw", -6, y - 1, s2, psub, 'ch("../panel_subdiv") > 0')
    prev = psw
    for k, (cell, h) in enumerate(((1.0, "panel_h1"), (0.5, "panel_h2"), (0.25, "panel_h3"))):
        w = wrangle("panel_sel%d" % (k + 1), -6, y - 2 - 2 * k, "primitive",
                    PANEL_VEX % {"cell": cell, "salt": 11.0 * (k + 1), "layer": k + 1}, prev)
        pe = mk("polyextrude::2.0", "panel_ext%d" % (k + 1), -6, y - 3 - 2 * k, w,
                parms={"group": "_pnl", "splittype": "components", "extrusionmode": "pointnormal", "usethicknessattrib": 0},
                expr={"dist": 'ch("../%s")' % h})
        prev = pe
    pan_sw = switch("panel_sw", -6, y - 8, s2, prev, 'ch("../panels")',
                    "Panels: three layers of raised grid cells.")

    # ---- booster -------------------------------------------------------
    bx, by = 6, -9
    tube = mk("tube", "boost_tube", bx, by, parms={"type": "poly", "orient": "z", "cap": 1, "rows": 1,
                                                    "radscale": 1, "height": 3},
              expr={"cols": 'ch("../booster_sides")'},
              comment="Blender: Variable Booster Nodes - a cylinder with a hollow nozzle.")
    tube.parm("rad1").set(1.0)
    tube.parm("rad2").set(1.0)
    cap = wrangle("boost_cap", bx, by - 1, "primitive", BOOST_CAP_VEX, tube)
    pe1 = mk("polyextrude::2.0", "boost_pe1", bx, by - 2, cap,
             parms={"group": "_cap", "splittype": "elements", "inset": 0.2, "dist": -0.5,
                    "outputfrontgrp": 1, "frontgrp": "extrudeFront"},
             comment="Nozzle: shrink the end, push it in.")
    pe2 = mk("polyextrude::2.0", "boost_pe2", bx, by - 3, pe1,
             parms={"group": "extrudeFront", "splittype": "elements", "inset": 0.15, "dist": 0.1})
    btag = wrangle("boost_tag", bx, by - 4, "primitive", "i@pf_part = 3; i@pf_panel = 0;", pe2)
    src = wrangle("boost_src", bx + 3, by - 4, "detail", BOOST_SRC_VEX,
                  comment="One ray origin behind the ship.")
    hit = wrangle("boost_hit", bx + 3, by - 5, "point", BOOST_HIT_VEX, src, pan_sw,
                  comment="Raycast onto the ship; the booster goes where it lands.")
    bcp = mk("copytopoints::2.0", "boost_copy", bx, by - 6, btag, hit, )
    pan_clean = sweep("boost_clean", -12, by - 5, pan_sw)
    bmerge = mk("merge", "boost_merge", -6, by - 7, pan_clean, bcp)
    bsw = switch("boost_sw", -6, by - 8, pan_sw, bmerge, 'ch("../boosters")')

    # ---- mirror, resize, output ----------------------------------------
    y = -19
    clip = mk("mirror", "ship_mirror", -6, y, bsw,
              parms={"operation": "clip", "dirx": 1, "diry": 0, "dirz": 0, "keepOriginal": 1,
                     "consolidatepts": 1, "consolidatetol": 0.001, "reversenml": 1},
              comment="Blender: the Starship's Mirror modifier (bisect, merge).")
    msw = switch("ship_mirsw", -6, y - 1, bsw, clip, 'ch("../mirror")')
    size = mk("matchsize", "resize", -6, y - 2, msw,
              parms={"justifytarget": "explicit", "doscale": 1, "uniformscale": 1, "scale_axis": "z",
                     "dotranslate": 1},
              expr={"sizez": 'ch("../length")'},
              comment="Resize Nodes: uniform scale so the ship is Length long (z), centred.")
    mat = wrangle("material", -6, y - 3, "primitive",
                  'if (primintrinsic(0, "measuredarea", @primnum) < 1e-9) { removeprim(0, @primnum, 1); return; }\n'
                  's@pf_material = i@pf_part == 3 ? "booster" : "hull";', size,
                  comment="Drops the few zero-area faces the mirror seam / panel extrusion leave.")
    nrm = mk("normal", "shade", -6, y - 4, mat, parms={"type": 1},
             expr={"cuspangle": 'ch("../smooth_angle")'}, comment="Auto Smooth.")
    cl2 = sweep("cleanup", -6, y - 5, nrm)
    clg = mk("groupdelete", "cleanup_grp", -6, y - 9, cl2, parms={"group1": "*"},
             comment="Working groups (extrudeFront, extrudeSide, _sel ...) must not leave.")
    out.setInput(0, clg)
    out.setPosition(hou.Vector2(-6, y - 10))


# --------------------------------------------------------------------------
# parameter interface
# --------------------------------------------------------------------------
def _f(name, label, default, lo, hi, help_, n=1, strict=True, ls=False):
    t = hou.FloatParmTemplate(name, label, n, default if n > 1 else (default,), min=lo, max=hi,
                              min_is_strict=strict, max_is_strict=False)
    t.setHelp(help_)
    t.setNamingScheme(hou.parmNamingScheme.Base1)
    return t


def _i(name, label, default, lo, hi, help_):
    t = hou.IntParmTemplate(name, label, 1, (default,), min=lo, max=hi,
                            min_is_strict=True, max_is_strict=False)
    t.setHelp(help_)
    return t


def _b(name, label, default, help_):
    t = hou.ToggleParmTemplate(name, label, default_value=default)
    t.setHelp(help_)
    return t


def _folder(name, label, items):
    f = hou.FolderParmTemplate(name, label, folder_type=hou.folderType.Collapsible)
    for t in items:
        f.addParmTemplate(t)
    return f


def interface():
    g = hou.ParmTemplateGroup()
    g.append(_i("seed", "Seed", 313997, 0, 1000000, "Every random choice in the ship. A new seed is a new ship."))
    g.append(_f("length", "Length", 15.0, 0.1, 100.0,
                "Final length of the ship along Z, in scene units. The nose points to -Z, the engine to +Z."))
    g.append(_b("mirror", "Mirror (Left = Right)", True,
                "Keeps the +X half and mirrors it, so the ship is symmetric. Off keeps the raw random shape."))
    g.append(_folder("f_hull", "Hull", [
        _f("width", "Width", (0.5, 1.2), 0.01, 5.0,
           "Random range of the hull's half-width, before the remesh. The hull is a 2 unit box scaled by this.", 2),
        _f("height", "Height", (0.5, 0.5), 0.01, 5.0,
           "Random range of the hull's half-height. Small values give a flat ship.", 2),
        _f("hlength", "Body Length", (4.0, 8.0), 0.1, 20.0,
           "Random range of the hull's half-length. Large values give a long, thin ship (the final size is set "
           "by Length).", 2),
        _f("jiggle", "Jiggle", 1.0, 0.0, 2.0,
           "Makes the hull lumpy along each axis. 0 keeps the box straight."),
        _f("ext_amount", "Extrusion Amount", 0.5, 0.0, 1.0,
           "Fraction of faces that get pushed out (or in). 0 gives a smooth blob."),
        _f("ext", "Extrusion Distance", (0.0, 1.0), 0.0, 5.0,
           "Random range of how far an extruded face goes.", 2),
        _f("tap", "Taper", (0.8, 1.2), 0.1, 3.0,
           "Random range of the scale of an extruded face's top. Below 1 narrows it, above 1 flares it.", 2),
        _i("detail", "Detail", 4, 2, 7,
           "How coarse the melt is. Each step doubles the resolution (and roughly 4x the faces). 4 is the "
           "original's default; lower is chunkier."),
        _i("subdiv_hull", "Hull Subdivision", 2, 0, 4, "Smoothing levels on the hull. 0 keeps the melted facets."),
        _f("crease", "Crease", (0.2, 0.8), 0.0, 1.0,
           "Random range of how sharp the edges stay while smoothing. 1 is fully sharp, 0 fully soft.", 2),
        _f("crease_scale", "Crease Noise Scale", 1.0, 0.01, 10.0,
           "Size of the patches that are sharp or soft. Larger numbers make smaller patches."),
    ]))
    g.append(_folder("f_parts", "Parts", [
        _i("variants", "Variants", 5, 1, 12,
           "How many different shapes are built for medium parts and, separately, for small parts. "
           "More variants look less repetitive and cook longer."),
        _f("med_density", "Medium Density", 0.15, 0.0, 2.0, "Medium parts per unit of surface area. 0 turns them off."),
        _f("med_scale", "Medium Scale", (0.4, 0.6), 0.01, 3.0, "Random size range, as a fraction of the hull's own size.", 2),
        _f("med_offset", "Medium Offset", (0.1, 0.4), -2.0, 5.0, "How far a medium part is lifted off the surface.", 2),
        _f("small_density", "Small Density", 0.15, 0.0, 2.0, "Small parts per unit of surface area. 0 turns them off."),
        _f("small_scale", "Small Scale", (0.1, 0.2), 0.01, 3.0, "Random size range, as a fraction of the hull's own size.", 2),
        _f("small_offset", "Small Offset", (0.0, 0.2), -2.0, 5.0, "How far a small part is lifted off the surface.", 2),
        _f("rot_step", "Rotation Step", (0.0, 90.0, 0.0), 0.0, 360.0,
           "Parts are turned in whole steps of this many degrees around X, Y, Z. The default turns them in "
           "quarter turns about the vertical axis.", 3),
        _i("subdiv_med", "Medium Subdivision", 1, 0, 3, "Smoothing levels on medium parts."),
        _i("subdiv_small", "Small Subdivision", 1, 0, 3, "Smoothing levels on small parts."),
    ]))
    g.append(_folder("f_panels", "Panels", [
        _b("panels", "Panels", True, "Raised panels on every surface."),
        _f("panel_size", "Panel Size", 1.0, 0.05, 20.0, "Size of the largest panels, in scene units before Length."),
        _f("panel_h", "Panel Heights", (0.03, 0.01, 0.003), 0.0, 1.0,
           "How far large, small and micro panels stand out.", 3),
        _f("panel_prop", "Panel Proportions", (1.0, 1.0, 1.0), 0.05, 20.0,
           "Stretches the panel grid along X, Y and Z. 1, 0.5, 1 gives panels twice as tall as wide.", 3),
        _f("panel_amount", "Panel Amount", 0.5, 0.0, 1.0, "Fraction of grid cells that get a panel, in every layer."),
        _i("panel_subdiv", "Panel Subdivision", 0, 0, 3, "Splits the faces before panelling so panels have faces to use."),
    ]))
    g.append(_folder("f_boost", "Booster", [
        _b("boosters", "Booster", True, "One engine, shot onto the ship from behind."),
        _f("booster_scale", "Booster Scale", 0.5, 0.01, 10.0, "Size of the engine."),
        _b("booster_flip", "Flip", False, "Put the engine on the front (-Z) instead of the rear (+Z)."),
        _f("booster_proj", "Projection X, Y", (0.0, 0.0), -50.0, 50.0,
           "Where the ray that places the engine is shot from. X 0 is the centre line; any other value gives "
           "a pair after mirroring.", 2),
        _f("booster_off", "Offset", (0.0, 0.0, 0.0), -10.0, 10.0, "Nudge the engine after it landed.", 3),
        _i("booster_sides", "Sides", 16, 3, 64, "Number of sides of the engine."),
    ]))
    g.append(_f("smooth_angle", "Smooth Angle", 30.0, 0.0, 180.0,
                "Shading only. Edges sharper than this angle shade as a hard edge."))
    # the hull block runs once: a hidden constant the part chain reads
    one = hou.IntParmTemplate("one", "One", 1, (1,), is_hidden=True)
    g.append(one)
    return g


if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_pf_starship_generator")
subnet = build_geo.createNode("subnet", "pf_starship_generator")
subnet.createNode("null", "OUT").setDisplayFlag(True)

hda_node = subnet.createDigitalAsset(name=NAME, hda_file_name=HDA_PATH, description=TAB_LABEL,
                                     min_num_inputs=0, max_num_inputs=0, version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setIcon(ICON)
defn.setParmTemplateGroup(interface())   # before the network: expressions need the parms
net = hda_node
build()
defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

defn = hou.hda.definitionsInFile(HDA_PATH)[0]
ds = defn.sections()["DialogScript"].contents()
if "outputlabel" in ds:
    ds = re.sub(r'outputlabel\t1\t"[^"]*"', 'outputlabel\t1\t"%s"' % OUTPUT_LABEL, ds)
else:
    ds = ds.replace('  parm {', '  outputlabel\t1\t"%s"\n  parm {' % OUTPUT_LABEL, 1)
defn.addSection("DialogScript", ds)
defn.addSection("Tools.shelf", TOOLS_SHELF)
defn.addSection("Help", HELP)

hda_node.destroy()
build_geo.destroy()

back = hou.hda.definitionsInFile(HDA_PATH)[0]
saved = back.sections()["DialogScript"].contents()
assert "Poly Factory/Modeling" in back.sections()["Tools.shelf"].contents(), "TAB submenu missing"
assert back.icon() == ICON and back.description() == TAB_LABEL
assert 'outputlabel\t1\t"%s"' % OUTPUT_LABEL in saved, "output label missing"
assert back.maxNumInputs() == 0
print("wrote " + HDA_PATH)
