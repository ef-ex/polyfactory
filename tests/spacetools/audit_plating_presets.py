"""Independent audit: HDA preset tables vs the Blender json files (re-derived here, not imported from the build script).
hython tests/spacetools/audit_plating_presets.py"""
import os, sys, json, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hou
from lib import fresh, install
SRC = "F:/cache/spacetools/plating/plating_greeble_gen/presets/panel"
install("pf_plating_generator"); install("pf_greeble_scatter")


def sec(t):
    return json.loads(hou.nodeType(hou.sopNodeTypeCategory(), t).definition().sections()["presets.json"].contents())


pl, gr = sec("pf_plating_generator"), sec("pf_greeble_scatter")
if "--selftest" in sys.argv:   # in-memory perturbation (never touch the .hda): the audit must go red
    pl["presets"]["Tapered"]["values"]["groove_width"] *= 3
    gr["presets"]["City_Block"]["values"]["coverage"] += 1
files = sorted(glob.glob(SRC + "/*.json"), key=lambda s: int(os.path.basename(s).split(".")[0]))
fails = []
PAT = {"0": "crisscross", "2": "triangles", "6": "irregular", "3": "rectangles", "4": "rectangles_cuts", "1": "edges", "5": "?uv"}
mp = [("amount", "amount"), ("triangle_percentage", "triangle_amount"), ("ruby_dragon_percentage", "irregular_amount"),
      ("groove_width", "groove_width"), ("groove_depth", "groove_depth"), ("plate_min_height", "height_min"),
      ("plate_max_height", "height_max"), ("plate_taper", "taper"), ("bevel_amount", "bevel_amount"),
      ("bevel_segments", "bevel_segments"), ("corner_width", "corner_radius"), ("corner_bevel_segments", "corner_segments"),
      ("rivet_corner_distance", "rivet_dist"), ("rivet_diameter", "rivet_size"), ("rectangle_amount", "rect_count"),
      ("rectangle_width_min", "rect_w_min"), ("rectangle_width_max", "rect_w_max"),
      ("rectangle_height_min", "rect_h_min"), ("rectangle_height_max", "rect_h_max")]
print("plating presets in HDA:", len(pl["presets"]), "json files:", len(files))
for f in files:
    d = json.load(open(f)); L = d["levels"]; name = os.path.basename(f)[:-5]
    key = name.split(". ", 1)[1].replace(" ", "_").replace("(", "").replace(")", "")
    v = pl["presets"].get(key, {}).get("values")
    if v is None:
        fails.append((name, "missing")); continue
    pp = L[0]["plating_props"]
    notes = []
    if L[0]["type"] != "PlatingGeneratorDecorator":
        notes.append("level0 is %s: no plating; the preset must only reset to defaults (no stale props)" % L[0]["type"])
        if v:
            fails.append((name, "stale plating props applied", v))
        print(name, "|", "; ".join(notes))
        continue
    if v.get("subdiv") != pp["pre_subdivisions"]:
        fails.append((name, "pre_subdivisions", pp["pre_subdivisions"], v.get("subdiv")))
    for a, b in mp:
        if abs(float(pp[a]) - float(v[b])) > 1e-6:
            fails.append((name, a, pp[a], v[b]))
    if PAT[pp["pattern_type"]] != v["pattern"]:
        fails.append((name, "pattern", pp["pattern_type"], v["pattern"]))
    if v["floor"] != ("remove" if pp["remove_grooves"] else "keep"):
        fails.append((name, "floor"))
    if bool(v["rivets"]) != pp["use_rivets"]:
        fails.append((name, "rivets"))
    if len(L) > 1:
        notes.append("levels=%d types=%s" % (len(L), [l["type"][:4] for l in L]))
    if "subdiv" not in v:
        notes.append("subdiv not set by preset (HDA default %s; Blender pre_subdivisions=%d)" % (pl["defaults"]["subdiv"], pp["pre_subdivisions"]))
    print(name, "|", "; ".join(notes))
gp = gr["presets"]
gm = [("greeble_amount", "amount"), ("coverage_amount", "coverage"), ("greeble_subd_levels", "subd_levels"),
      ("greeble_deviation", "deviation"), ("greeble_min_width", "width_min"), ("greeble_max_width", "width_max"),
      ("greeble_min_length", "length_min"), ("greeble_max_length", "length_max"), ("greeble_min_height", "height_min"),
      ("greeble_max_height", "height_max")]
print("greeble presets in HDA:", list(gp))
for f in files:
    d = json.load(open(f)); name = os.path.basename(f)[:-5]
    key = name.split(". ", 1)[1].replace(" ", "_").replace("(", "").replace(")", "")
    gl = [l for l in d["levels"] if l["type"].startswith("Greeble")]
    if key in gp:
        g = gl[-1]["greeble_props"]; v = gp[key]["values"]
        for a, b in gm:
            if abs(float(g[a]) - float(v[b])) > 1e-6:
                fails.append((name, "G", a, g[a], v[b]))
        if v["placement"] != {"0": "overlapping", "1": "non_overlapping"}[g["greeble_pattern_type"]]:
            fails.append((name, "placement"))
        if bool(v["keep_aspect"]) != g["all_keep_aspect_ratio"]:
            fails.append((name, "aspect"))
        print("greeble preset", name, "ok; greeble levels in json:", len(gl))
    elif gl:
        print("greeble levels in", name, "NOT offered as a greeble preset:", len(gl))
print("MISMATCHES:", fails)
sys.exit(1 if fails else 0)
