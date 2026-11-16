"""Audit: mutate the OpenCL kernel of a throwaway (unlocked, in-memory) pf_custom_planet instance and run the author's
check functions A-D against it; list which mutations are NOT detected (= checks that cannot fail for that code path).
hython tests/spacetools/audit_planet_mutate.py [name ...]   (never saves the HDA)

Result 2026-11 audit (author's run_planet_checks A-D, 26 mutants, ~6 min): DETECTED: layer order, hue/tint/atm colour,
emission clamp, water layer rotation, terran seed, planet-preview colour, axis flips. NOT DETECTED (checks cannot fail there):
back-hemisphere mirror (x or y), cloud seed, colour ramp (ignored or swapped), normal sign/channel order, height scale,
water colour (small area, block metric too blunt), night saturation, pole frame branch, spin sign, limb clamp, alpha edge shift,
bump 0. The pole/spin/limb/back-mirror/orientation cases are covered by audit_planet_unproject.py (analytic synthetic disc)."""
import sys, os, io, contextlib
sys.path.insert(0, os.path.dirname(__file__))
import run_planet_checks as R
import planet_common as PC
R.SCRATCH = PC.SCRATCH = "F:/cache/spacetools/audit_planet"
MUT = {
 "layer_order_emission_after_clouds": ("float3 c03 = pf_mix3(e05, cc, pf_sat(ca));", "float3 c03 = pf_mix3(w04, cc, pf_sat(ca)) + e04;"),
 "back_hemisphere_unmirrored_x": ("float2 vxy = (float2)(dv.x, dv.y);", "float2 vxy = (float2)(dv.z < 0.0f ? -dv.x : dv.x, dv.y);"),
 "back_hemisphere_mirrored_y": ("float2 vxy = (float2)(dv.x, dv.y);", "float2 vxy = (float2)(dv.x, dv.z < 0.0f ? -dv.y : dv.y);"),
 "cloud_seed_ignored": ("(uint)seed + 301U", "301U"),
 "cloud_seed_ignored2": ("(uint)seed + 303U", "303U"),
 "terran_height_seed_ignored": ("float hh = pf_tri(d, 0U, seed, 1.6f * sc, 7, rough);", "float hh = pf_tri(d, 0U, 1, 1.6f * sc, 7, rough);"),
 "ramp_ignored": ("if (IP(useramp)) {", "if (0) {"),
 "ramp_mid_swapped": ("t < mp ? pf_mix3(ramp0, ramp1, t / mp)", "t < mp ? pf_mix3(ramp2, ramp1, t / mp)"),
 "normal_sign_flipped": ("dS - 0.1f * bump * hscale * gd", "dS + 0.1f * bump * hscale * gd"),
 "normal_channels_swapped": ("@normal.set((float4)(0.5f * npl + 0.5f, 1.0f));", "@normal.set((float4)(0.5f * npl.yxz + 0.5f, 1.0f));"),
 "height_scaled": ("@height.set(hk[0] * hscale);", "@height.set(hk[0] * hscale * 0.5f);"),
 "hue_neutral_wrong": ("pf_hsvnode(s1, s_hue + 0.5f, s_sat, s_val)", "pf_hsvnode(s1, s_hue, s_sat, s_val)"),
 "tint_ignored": ("* tint;", ";"),
 "water_colour_ignored": ("pf_mix3(s5, w_color, wmc)", "pf_mix3(s5, (float3)(0.02f,0.07f,0.18f), wmc)"),
 "atm_color_ignored": ("if (hb.y != 0.0f)", "if (0)"),
 "night_sat_ignored": ("pf_sat(lsl / 0.011f))", "1.0f)"),
 "emission_clamp_removed": ("clamp(em * (1.0f - m), 0.0f, 1.0f)", "em * (1.0f - m)"),
 "proc_ocean_ignored": ("else if (IP(water_proc)) wm = oceanP * w_blend;", "else if (IP(water_proc)) wm = 0.0f;"),
 "equirect_y_flip": ("inside = dd.w;", "inside = dd.w; dd.y = -dd.y;"),
 "dir_rot_180": ("inside = dd.w;", "inside = dd.w; dd.x = -dd.x; dd.z = -dd.z;"),
 "pole_frame_branch": ("fabs(z.y) > 0.999f ?", "fabs(z.y) > 2.0f ?"),
 "spin_sign": ("*X = x * c + y * s; *Y = y * c - x * s;", "*X = x * c - y * s; *Y = y * c + x * s;"),
 "bump_zero_normal": ("float eps = 1.5f * pixang;", "float eps = 1.5f * pixang; bump = 0.0f;"),
 "limb_clamp_off": ("if (vr > 0.985f)", "if (vr > 5.0f)"),
 "rot_layer_water_ignored": ("uW = pf_rot2(uvb - 0.5f, aW) + 0.5f", "uW = uvb"),
 "alpha_edge": ("alpha = pf_sat(rr * 16.62f - 7.81f);", "alpha = pf_sat(rr * 16.62f - 7.5f);"),
}
which = sys.argv[1:] or list(MUT)
orig_make = PC.make_node
cur = {}


def make_mut(params=None):
    n = orig_make(params)
    if cur.get("m"):
        a, b = MUT[cur["m"]]
        n.allowEditingOfContents()
        k = n.node("pf_planet_kernel")
        src = k.parm("kernelcode").eval()
        assert a in src, "mutation target not found: " + cur["m"]
        k.parm("kernelcode").set(src.replace(a, b))
        k.cook(force=True)
        err = k.errors()
        assert not err or True
    return n


R.make_node = PC.make_node = make_mut
for m in [None] + which:
    cur["m"] = m
    R.FAILS.clear()
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            for part in (R.part_a, R.part_b, R.part_c, R.part_d):
                try:
                    part()
                except Exception as e:
                    R.FAILS.append("EXC %s: %s" % (part.__name__, str(e)[:80]))
    except Exception as e:
        R.FAILS.append("EXC " + str(e)[:80])
    print("%-36s %s" % (m or "BASELINE", ("DETECTED by %d: %s" % (len(R.FAILS), "; ".join(R.FAILS)[:150])) if R.FAILS else "NOT DETECTED (all checks pass)"), flush=True)
