"""Reference statistics of the ORIGINAL Shape Generator 1.7.9 operator (whole pipeline: shapes, big/medium/small, modifiers, booleans)
for tests/spacetools/run_shapegen_checks.py.

  blender -b --python tests/spacetools/shapegen_ref_blender_full.py -- out.json [nseeds]

For every preset (and the extra cases in EXTRA) and `nseeds` values of random_seed it runs bpy.ops.mesh.shape_generator and records, from the
EVALUATED objects in world space: number of objects, sum of volumes / areas, union bbox size, triangle count, non-manifold edge count.
Hidden / wire boolean operands are listed separately (`cutters`).
"""
import sys, json, os, types
import bpy, bmesh
import numpy as np
sys.path.insert(0, r"F:\cache\shapegen\Shape Generator\sg179")
from shape_generator import operators, properties

PRESETS = r"F:\cache\shapegen\Shape Generator\sg179\shape_generator\presets"
EXTRA = {   # name: operator kwargs (on top of the defaults)
    "defaults": {},
    "bool_set": dict(amount=4, number_to_create=2, is_boolean=True, main_obj_bool_operation="DIFFERENCE", min_extrude=0.6, max_extrude=1.0),
    "bool_set_union": dict(amount=3, number_to_create=2, is_boolean=True, main_obj_bool_operation="UNION"),
    "bool_set_inter": dict(amount=3, number_to_create=2, is_boolean=True, main_obj_bool_operation="INTERSECT"),
    "bool_medium": dict(amount=4, medium_shape_num=3, use_medium_shape_bool=True, medium_shape_bool_operation="DIFFERENCE", mirror_x=False),
    "bool_small_union": dict(amount=4, small_shape_num=3, use_small_shape_bool=True, small_shape_bool_operation="UNION", mirror_x=False),
    "bool_medium_inter": dict(amount=4, medium_shape_num=2, use_medium_shape_bool=True, medium_shape_bool_operation="INTERSECT", mirror_x=False),
    "bool_both": dict(amount=4, medium_shape_num=2, small_shape_num=3, use_medium_shape_bool=True, use_small_shape_bool=True, mirror_x=False),
    "big_sets": dict(amount=4, big_shape_num=3, medium_shape_num=2, small_shape_num=2),
    "big_scaled": dict(amount=4, big_shape_scale=2.0, medium_shape_num=2, small_shape_num=2, mirror_x=False),
    "mirror_xyz": dict(amount=6, mirror_x=True, mirror_y=True, mirror_z=True),
    "bevel_width": dict(amount=5, is_bevel=True, bevel_method="WIDTH", bevel_width=0.1, mirror_x=False),
    "bevel_depth": dict(amount=5, is_bevel=True, bevel_method="DEPTH", bevel_width=0.1, mirror_x=False),
    "bevel_seg": dict(amount=5, is_bevel=True, bevel_method="OFFSET", bevel_width=0.08, bevel_segments=3, mirror_x=False),
    "subsurf_simple": dict(amount=5, is_subsurf=True, subsurf_type="SIMPLE", subsurf_subdivisions=1, mirror_x=False),
    "cuts": dict(amount=5, subdivide_edges=2, mirror_x=False),
}


def preset_kwargs(fn):
    ns = types.SimpleNamespace()
    ctx = types.SimpleNamespace(active_operator=ns)
    src = open(os.path.join(PRESETS, fn)).read().replace("import bpy\nop = bpy.context.active_operator", "")
    exec(src, {"op": ns})
    kw = dict(vars(ns))
    kw["shade_smooth"] = False       # the add-on sets mesh.use_auto_smooth, removed in Blender 4.1; shading does not change the measured geometry
    for k in ("align",):
        kw.pop(k, None)
    return kw


def measure():
    dg = bpy.context.evaluated_depsgraph_get()
    n = 0; vol = 0.0; area = 0.0; tris = 0; nonman = 0; co = []; cutters = 0
    for o in bpy.data.objects:
        if o.hide_render or o.display_type == "WIRE":
            cutters += 1
            continue
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        bm = bmesh.new(); bm.from_mesh(me); bm.transform(o.matrix_world); bm.normal_update()
        if bm.faces:
            n += 1; vol += bm.calc_volume(signed=True); area += sum(f.calc_area() for f in bm.faces)
            tris += sum(len(f.verts) - 2 for f in bm.faces); nonman += sum(1 for e in bm.edges if not e.is_manifold)
            co.extend(v.co[:] for v in bm.verts)
        bm.free()
    bb = (np.max(co, 0) - np.min(co, 0)).tolist() if co else [0, 0, 0]
    return dict(n=n, vol=vol, area=area, tris=tris, nonman=nonman, size=bb, cutters=cutters)


def clear():
    for o in list(bpy.data.objects): bpy.data.objects.remove(o, do_unlink=True)
    for m in list(bpy.data.meshes): bpy.data.meshes.remove(m)
    for c in list(bpy.data.collections): bpy.data.collections.remove(c)


def run():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    operators.register(); properties.register()
    nseeds = int(sys.argv[sys.argv.index("--") + 2]) if len(sys.argv) > sys.argv.index("--") + 2 else 30
    cases = {}
    for fn in sorted(os.listdir(PRESETS)):
        if fn.endswith(".py"):
            cases[os.path.splitext(fn)[0]] = preset_kwargs(fn)
    cases.update(EXTRA)
    out = {}
    for name, kw in cases.items():
        res = []
        for i in range(nseeds):
            clear()
            k = dict(kw); k["random_seed"] = 1000 + i
            bpy.ops.mesh.shape_generator(**k)
            res.append(measure())
        out[name] = dict(params={a: (list(b) if hasattr(b, "__len__") and not isinstance(b, str) else b) for a, b in kw.items()}, runs=res)
        print(name, "done", flush=True)
    json.dump(out, open(sys.argv[sys.argv.index("--") + 1], "w"))


run()
