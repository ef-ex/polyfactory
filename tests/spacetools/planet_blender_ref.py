"""Blender side of the pf_custom_planet check: loads Library.blend (MATERIAL_PREFAB), sets the node values from a json cfg and renders the billboard plane (ortho, 1 sample, Standard view) to EXR.
   blender -b Library.blend --python planet_blender_ref.py -- <json cfg> <out.exr>"""
import bpy, sys, os, json, math
argv=sys.argv[sys.argv.index("--")+1:]
cfg=json.loads(argv[0]); out=argv[1]
IMG="F:/cache/spacetools/planet_img/CustomPlanetImages/"
res=cfg.get("res","1k"); ls=cfg.get("ls",0)
mat=bpy.data.materials["MATERIAL_PREFAB_delete_to_avoid_bugs"]
nt=mat.node_tree; N=nt.nodes
def load(node,kind,name):
    p=IMG+f"{res}/{kind}/{name}"
    if os.path.exists(p): N[node].image=bpy.data.images.load(p)
    else: print("MISSING",p)
    if N[node].image: N[node].image.colorspace_settings.name="Linear Rec.709"
s=cfg.get("surface",5); load("ImageTextureSurface","Surface",f"Surface_{s:02d}_{res}_LS00.exr")
if cfg.get("water"): load("ImageTextureWater","Water",f"water_{cfg['water']:02d}_{res}_LS00.exr")
else: N["ImageTextureWater"].image=None
if cfg.get("emission"): load("ImageTextureEmission","Emission",f"emission_{cfg['emission']:02d}_{res}_LS00.exr")
else: N["ImageTextureEmission"].image=None
load("ImageTextureLightSetup","LightSetup",f"LightSetup_{ls:02d}_{res}_LS{ls:02d}.exr")
if cfg.get("clouds"): load("ImageTextureClouds","Clouds",f"clouds_{cfg['clouds']:02d}_{res}_LS{ls:02d}.exr")
else:
    load("ImageTextureClouds","Clouds",f"clouds_01_{res}_LS{ls:02d}.exr"); cfg.setdefault("cloud_blend",0)
a=cfg.get("atm",1)
if a: load("ImageTextureAtmosphere","Atmosphere",f"Atmosphere_{a:02d}_{res}_LS{ls:02d}.exr")
else:
    load("ImageTextureAtmosphere","Atmosphere",f"Atmosphere_01_{res}_LS{ls:02d}.exr"); cfg.setdefault("atm_strength",0); cfg.setdefault("white_rim",0)
wr=IMG+f"{res}/Atmosphere/WhiteRim/atmosphere_whiteRim_{res}_LS{ls:02d}.exr"
if not os.path.exists(wr): wr=IMG+f"{res}/Atmosphere/WhiteRim/atmosphere_whiteRim_{res}_LS00.exr"
N["ImageTextureAtmosphere.001"].image=bpy.data.images.load(wr); N["ImageTextureAtmosphere.001"].image.colorspace_settings.name="Linear Rec.709"
N["ImageTextureSurfaceMask"].image=bpy.data.images.load(IMG+f"{res}/Mask/surface_Mask_4k.exr")
for k,(node,kind,i) in {"hue":("HueSaturationValue_s01","in",0),"sat":("HueSaturationValue_s01","in",1),"val":("HueSaturationValue_s01","in",2),"tint":("MixColor_s01","in",7),
   "atm_color":("MixColor_a01","in",7),"atm_center":("MixColor_a02","in",0),"white_rim":("Math","in",1),"atm_strength":("Math_a01","in",1),"atm_sat":("HueSaturationValue_a01","in",1),
   "cloud_thick":("Math_c01","in",1),"emit_strength_overall":("Emission","in",1),"emit_hue":("HueSaturationValue_e01","in",0),"emit_sat":("HueSaturationValue_e01","in",1)}.items():
    if k in cfg: N[node].inputs[i].default_value=cfg[k]
for k,node in {"contrast":"Value_s01","rot":"Value_r01","water_blend":"Value_w01","water_rot":"Value_r03","emit":"Value_e01","emit_rot":"Value_r04","shadow_vis":"Value_e03","cloud_blend":"Value_c01","cloud_bright":"Value_c02","shadow_bright":"Value_b01"}.items():
    if k in cfg: N[node].outputs[0].default_value=cfg[k]
if "water_color" in cfg: N["RGB_w01"].outputs[0].default_value=cfg["water_color"]
if "debug" in cfg:
    node,sock=cfg["debug"]
    src=N[node].outputs[sock]
    for l in list(nt.links):
        if l.to_node.name=="Emission" and l.to_socket.name=="Color": nt.links.remove(l)
    nt.links.new(src,N["Emission"].inputs["Color"]); N["Emission"].inputs[1].default_value=1.0
sc=bpy.context.scene
for o in list(bpy.data.objects): bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_plane_add(size=1); pl=bpy.context.active_object
pl.data.materials.clear(); pl.data.materials.append(mat)
cam=bpy.data.cameras.new("c"); cam.type="ORTHO"; cam.ortho_scale=1
co=bpy.data.objects.new("c",cam); sc.collection.objects.link(co); co.location=(0,0,2); sc.camera=co
sc.render.engine="CYCLES"; sc.cycles.samples=1; sc.cycles.device="CPU"
sc.render.resolution_x=sc.render.resolution_y=cfg.get("size",1024)
sc.view_settings.view_transform="Standard"; sc.view_settings.look="None"
sc.render.resolution_percentage=100
sc.render.film_transparent=True; sc.cycles.filter_width=0.01
w=bpy.data.worlds.new("w"); w.use_nodes=True; w.node_tree.nodes["Background"].inputs[0].default_value=(0,0,0,1); sc.world=w
sc.render.image_settings.file_format="OPEN_EXR"; sc.render.image_settings.color_depth="32"; sc.render.image_settings.color_mode="RGBA"
sc.render.filepath=out
bpy.ops.render.render(write_still=True)
