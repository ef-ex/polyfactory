# Reference builder, step 1 (needs the unpacked Blender add-on, see ideas/spacetools.md "Plating + greebles"):
#   blender -b -P tests/spacetools/plating_layout_orig.py -- <preset n> <seed0> <nseeds>   -> OUT/orig_<n>_<seed>.obj  (plane 16x16, size 4)
# step 2: python tests/spacetools/plating_layout.py   (writes plating_layout_ref.json)
import bpy, bmesh, sys, os, json, glob
ADD = "F:/cache/spacetools/plating_compare/addons"; PRE = ADD + "/plating_greeble_gen/presets/panel"
OUT = "F:/cache/spacetools/plating_compare/v3/stat"   # scratch
sys.path.insert(0, ADD)
bpy.ops.preferences.addon_enable(module="plating_greeble_gen")
from plating_greeble_gen.encoding.encoding import decode_preset
from plating_greeble_gen.orchestration import decorators
a = sys.argv[sys.argv.index("--") + 1:]; n, s0, ns = int(a[0]), int(a[1]), int(a[2])
f = [p for p in glob.glob(PRE + "/*.json") if os.path.basename(p).startswith("%d. " % n)][0]
for seed in range(s0, s0 + ns):
    for o in list(bpy.data.objects): bpy.data.objects.remove(o)
    me = bpy.data.meshes.new("plane"); bm = bmesh.new()
    bmesh.ops.create_grid(bm, x_segments=16, y_segments=16, size=2.0)
    for fc in bm.faces: fc.select_set(True)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new("plane", me); bpy.context.scene.collection.objects.link(ob)
    bpy.context.view_layer.objects.active = ob; ob.select_set(True)
    bpy.ops.mesh.plates_generate_new()
    ob = bpy.context.active_object
    d = json.load(open(f)); d["master_seed"] = seed
    for l in d["levels"]:
        for g in l["greeble_props"]["library_greebles"]:
            g["file_path"] = ADD + "/plating_greeble_gen/Defaults/" + os.path.basename(g["file_path"].replace("\\", "/"))
    ob.plating_generator.auto_update = False
    decode_preset(d, bpy.context)
    decorators.decorate(ob, bpy.context)
    bpy.ops.wm.obj_export(filepath="%s/orig_%d_%d.obj" % (OUT, n, seed), export_selected_objects=True, export_materials=False, export_uv=False, export_normals=False, forward_axis="Y", up_axis="Z")
    print("DONE", n, seed, len(ob.data.polygons))
