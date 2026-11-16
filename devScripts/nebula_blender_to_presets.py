"""Convert the Blender Nebula Generator parameter dumps (F:/cache/spacetools/nebula_work/presets, presets_stars,
made by dump_params.py / dump_stars.py in Blender 4.5) into polyfactory/.../spacetools/nebula_presets.json,
keyed by our pf_nebula_generator parm names. Plain python (no hou)."""
import json, glob, os, math

WORK = "F:/cache/spacetools/nebula_work"
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "polyfactory/scripts/python/polyfactory/spacetools/nebula_presets.json")


def ramp(r, vec):
    els = r["els"]
    interp = {"CONSTANT": "constant", "LINEAR": "linear"}.get(r["interp"], "linear")
    if vec:
        return {"interp": interp, "pos": [e[0] for e in els], "val": [e[1][:3] for e in els]}
    return {"interp": interp, "pos": [e[0] for e in els], "val": [e[1][0] for e in els]}


def convert(name):
    j = json.load(open("%s/presets/%s.json" % (WORK, name)))
    sp = "%s/presets_stars/%s.json" % (WORK, name)
    st = json.load(open(sp)) if os.path.exists(sp) else {}
    box = j.get("Nebula Box", {})
    unit = box.get("scale", [122.73])[0]
    p = {"volume_unit": unit}
    p["main_ramp"] = ramp(j["Main Cloud Density Ramp"], False)
    p["main_mult"] = j["Math.002"]["in"][1]
    p["gas_ramp"] = ramp(j["Cloud Gas Density Ramp"], False)
    p["gas_mult"] = j["Math.004"]["in"][1]
    p["gas_color_ramp"] = ramp(j["ColorRamp.010"], True)
    h = j["Hue Saturation Value.003"]; p.update(gas_hue=h["Hue"], gas_sat=h["Saturation"], gas_val=h["Value"])
    c = j["ColorControls"]; p.update(hue=c["Hue"], sat=c["Saturation"], val=c["Value"])
    n9, n8, n4 = j["Noise Texture.009"], j["Noise Texture.008"], j["Noise Texture.004"]
    p.update(coarse_scale=n9["Scale"], coarse_rough=n9["Roughness"], dist_scale=n8["Scale"], dist_rough=n8["Roughness"],
             dist_mult=j["Math"]["in"][1], cloud_rough=n4["Roughness"], octaves=min(int(n4["Detail"]), 12))
    m = j["Mapping"]
    p.update(map_loc=m["Location"], map_rot=[math.degrees(x) for x in m["Rotation"]], map_scale=m["Scale"])
    p["falloff_ramp"] = ramp(j["Transparency Ramp"], False)
    p["falloff_size"] = j["Map Range"]["From Max"]
    ml = j.get("LIGHT Main Light")
    if ml:
        p.update(light_color=ml["color"], light_strength=ml["energy"], light_rot=[math.degrees(x) for x in ml["rot"]])
    sl = j.get("LIGHT Sun")
    if sl:
        p.update(sun_color=sl["color"], sun_strength=sl["energy"])
    # the "Sun" point lamp object is not rendered (its collection is excluded); the large-star instances each carry a copy of it,
    # so the exact instance positions (stars listed twice: mesh + lamp) are the lamp positions
    lp = [s[0] for s in st.get("Large Stars", {}).get("stars", [])[::2]][:3]
    for i in range(3):
        p["large_pos%d" % i] = [round(x, 5) for x in lp[i]] if i < len(lp) else [0.0, 0.0, 0.0]
    cam = j["scene"].get("cam")
    if cam:
        p["view"] = [x / unit for x in cam]
    ls = j.get("Large Stars", {}).get("Large Stars", {})
    ss = j.get("Small Stars", {}).get("Small Stars", {})
    deg = lambda s: s   # sizes stay in world units: the kernel divides by the star's distance
    if ls:
        p.update(large_count=int(ls["Number"]), large_seed=int(ls["Seed"]), large_size_min=deg(ls["Min Star Size"]), large_size_max=deg(ls["Max Star Size"]))
    if ss:
        p.update(star_seed=ss["Seed"], star_coverage=ss["Star Coverage"], star_noise_scale=ss["Noise Scale"],
                 star_size_min=deg(ss["Min Star Size"]), star_size_max=deg(ss["Max Star Size"]),
                 star_count=int(ss["Star Density"] * unit ** 3 * 4.19 * 2.8))   # x2.8: calibrated so the visible star peaks match the EEVEE renders (ours were 2.5-3.5x short)
    p["star_ramp"] = ramp(j["STAR:ColorRamp"], True)
    sh = j["STAR:Hue Saturation Value.001"]; p.update(star_hue=sh["Hue"], star_sat=sh["Saturation"], star_val=sh["Value"])
    p["star_strength"] = j["STAR:Emission"]["Strength"]
    return p


def main():
    out = {}
    for f in sorted(glob.glob(WORK + "/presets/*.json")):
        n = os.path.basename(f)[:-5]
        out[n] = convert(n)
    names = ["default"] + [k for k in out if k != "default"]
    json.dump({"order": names, "presets": out}, open(OUT, "w"), indent=0)
    print("wrote", OUT, len(out), "presets")


if __name__ == "__main__":
    main()
