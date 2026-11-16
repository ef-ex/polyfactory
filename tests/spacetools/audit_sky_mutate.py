"""Mutation driver: python mutate.py <id>... ; copies the repo subset, applies one source edit, rebuilds the HDAs, runs the tool's checks."""
import os, shutil, subprocess, sys, re
SRC = "F:/projects/polyfactory-spacetools"; BASE = "F:/cache/spacetools/audit_sky/mut"
H = "C:/Program Files/Side Effects Software/Houdini 22.0.442/bin/hython.exe"
BUILD = {"sd": ["create_pf_space_direction_hda.py"], "ss": ["create_pf_space_direction_hda.py", "create_pf_spacescape_hda.py"],
         "nb": ["create_pf_space_direction_hda.py", "create_pf_nebula_generator_hda.py"]}
RUN = {"sd": "run_space_direction.py", "ss": "run_spacescape_checks.py", "nb": "run_nebula.py"}
CL = "polyfactory/ocl/pf_nebula_generator.cl"; SK = "devScripts/pf_spacescape_kernel.py"; SC = "devScripts/pf_space_common.py"
SKY = "polyfactory/scripts/python/polyfactory/spacetools/bake.py"
M = {
 # shared direction layer
 "sd_negY": ("sd", SC, "d = (float3)(  a, -1.0f, -b);", "d = (float3)(  a, -1.0f,  b);"),
 "sd_vflip": ("sd", SC, "float th  = vt * 3.14159265359f;", "float th  = (1.0f - vt) * 3.14159265359f;"),
 "sd_yaw": ("sd", SC, "float phi = u * 6.28318530718f;", "float phi = (u - 0.25f) * 6.28318530718f;"),
 "sd_bakeflip": ("sd", SKY, "return np.ascontiguousarray(a[::-1])", "return np.ascontiguousarray(a)"),
 "sd_crosscell": ("sd", SC, "else if (cx == 3 && cy == 1) f = 5;", "else if (cx == 3 && cy == 1) f = 4;"),
 # spacescape
 "ss_seed": ("ss", SK, "pf_perlin(v, s + (uint)i * 0x68E31DA4U)", "pf_perlin(v, (uint)i * 0x68E31DA4U)"),
 "ss_blend": ("ss", SK, "case 6: return (float4)(d.w);", "case 6: return (float4)(s.w);"),
 "ss_hdrpow": ("ss", SK, "n = pow(n, P[4].w);", ""),
 "ss_rampswap": ("ss", SK, "if (usemid == 0) return mix(c_out, c_in, t);", "if (usemid == 0) return mix(c_in, c_out, t);"),
 "ss_count": ("ss", SK, "float p0 = fmin(1.0f, count / (6.0f * G * G * 0.5236f));", "float p0 = 0.5f * fmin(1.0f, count / (6.0f * G * G * 0.5236f));"),
 "ss_maskpow": ("ss", SK, "if (r5 > m * m) continue;", "if (r5 > m) continue;"),
 "ss_shelf": ("ss", SK, "n = fmax(0.0f, n - shelf);", ""),
 "ss_ridgeoff": ("ss", SK, "float r = off - fabs(n); n = r * r;", "float r = off - fabs(n); n = r;"),
 "ss_gain": ("ss", SK, "asum += amp; amp *= gain; v *= lac;", "asum += amp; amp *= 0.5f; v *= lac;"),
 "ss_starseed": ("ss", SK, "uint seed = (uint)P[0].y;", "uint seed = 7u;"),
 "ss_sundir": ("ss", SK, "float3 s = normalize(P[9].xyz);\n            float S = fmax(P[5].y", "float3 s = normalize(P[9].xzy);\n            float S = fmax(P[5].y"),
 "ss_stardens": ("ss", SK, "if (r3 > p0 * rsqrt(w * w * w)) continue;", "if (r3 > p0) continue;"),
 # nebula
 "nb_gasramp": ("nb", CL, "@gas_color_ramp(gval)", "@gas_color_ramp(1.0f - gval)"),
 "nb_dustmix": ("nb", CL, "float mixf = clamp(dmain * @main_mult, 0.0f, 1.0f);", "float mixf = 0.0f;"),
 "nb_seed": ("nb", CL, "(float3)(@seed * 17.31f, @seed * -9.77f, @seed * 5.13f)", "(float3)(0.0f)"),
 "nb_starcount": ("nb", CL, "float rho = (float)@star_count / (4.0f * PF_PI);", "float rho = 0.5f * (float)@star_count / (4.0f * PF_PI);"),
 "nb_starramp": ("nb", CL, "pf_hsv_adjust(@star_ramp(st.cu)", "pf_hsv_adjust(@star_ramp(0.5f)"),
 "nb_pointlamp": ("nb", CL, "Lin += @sun_color * (sun_i / (rw * rw));", "Lin += (float3)(0.0f);"),
 "nb_exposure": ("nb", CL, "float3 outc = (L + S + bg * T) * @exposure;", "float3 outc = (L + S + bg * T);"),
 "nb_alpha": ("nb", CL, "@alpha.set(1.0f - T);", "@alpha.set(T);"),
 "nb_bg": ("nb", CL, "if (@bg_stars > 0.0f) {", "if (0) {"),
 "nb_shadow": ("nb", CL, "int ns = clamp(@shadow_steps, 0, 48);", "int ns = 0;"),
 "nb_hue": ("nb", CL, "gc = pf_hsv_adjust(gc, @hue, @sat, @val);", ""),
 "nb_starstrength": ("nb", CL, "S += sc * @star_strength * exp", "S += sc * 2.0f * @star_strength * exp"),
 "nb_largecount": ("nb", CL, "if (k >= @large_count) break;", "if (k >= 1) break;"),
 # added with the look fix (NEB_FAST=1 runs only the section-5 checks; the look-proxy mutants need the full run)
 "nb_noiseunit": ("nb", CL, "(@volume_unit / @noise_unit)", "1.0f"),
 "nb_weak": ("nb", CL, "gc = pf_weak_colour(gc, @albedo_floor);", ""),
 "nb_sungain": ("nb", CL, "#define PF_LIGHT_GAIN 1.0f", "#define PF_LIGHT_GAIN 2.0f"),
 "nb_lampgain": ("nb", CL, "#define PF_STAR_LIGHT_GAIN 3.14159265f", "#define PF_STAR_LIGHT_GAIN 1.0f"),
 "nb_stardepth": ("nb", CL, "s.size = PF_STAR_CORE * mix(smin, smax, pf_u01(pf_h(h + 3u))) / (s.dist * unit);", "s.size = PF_STAR_CORE * mix(smin, smax, pf_u01(pf_h(h + 3u))) / (0.9f * unit);"),
 "nb_bgsize": ("nb", CL, "#define PF_BG_R 0.25f", "#define PF_BG_R 1.0f"),
 "nb_octmod": ("nb", CL, "fmin((float)(OCT), PF_N9_CAP)", "fmin((float)(OCT), 2.0f)"),
}
def run(mid):
    tool, rel, old, new = M[mid]
    d = "%s/%s" % (BASE, mid)
    shutil.rmtree(d, ignore_errors=True)
    for sub in ("devScripts", "tests/spacetools", "polyfactory/ocl", "polyfactory/scripts", "polyfactory/otls"):
        shutil.copytree("%s/%s" % (SRC, sub), "%s/%s" % (d, sub), ignore=shutil.ignore_patterns("__pycache__", "*.hda" if sub == "polyfactory/otls" else "zzz"))
    p = "%s/%s" % (d, rel); s = open(p, encoding="utf8", newline="").read()
    if old not in s: return mid, "PATTERN NOT FOUND"
    open(p, "w", encoding="utf8", newline="").write(s.replace(old, new, 1))
    for f in ("polyfactory/otls/x",):
        pass
    for f in ("tests/spacetools/run_nebula.py", "tests/spacetools/spacescape_common.py"):
        q = "%s/%s" % (d, f); t = open(q, encoding="utf8").read()
        t = t.replace('tmp = os.path.join(WORK, "nebula_test_bake")', 'tmp = "%s/nb_bake"' % d).replace('SCRATCH = "F:/cache/spacetools/spacescape_work"', 'SCRATCH = "%s/scratch"' % d)
        open(q, "w", encoding="utf8").write(t)
    env = dict(os.environ, POLYFACTORY="%s/polyfactory" % d, TEMP=d, TMP=d)
    for b in BUILD[tool]:
        r = subprocess.run([H, "%s/devScripts/%s" % (d, b)], env=env, capture_output=True, text=True)
        if not os.path.exists("%s/polyfactory/otls/%s" % (d, b.replace("create_", "").replace("_hda.py", ".hda"))): return mid, "BUILD FAILED " + r.stdout[-300:] + r.stderr[-300:]
    r = subprocess.run([H, "%s/tests/spacetools/%s" % (d, RUN[tool])], env=env, capture_output=True, text=True, timeout=1500)
    out = r.stdout + r.stderr
    fails = [l for l in out.splitlines() if l.startswith("FAIL")]
    ok = "ALL PASS" in out and r.returncode == 0
    return mid, ("SURVIVED (all green)" if ok else "RED rc=%d: %s" % (r.returncode, " | ".join(x[:90] for x in fails[:4]) or out[-200:].replace("\n", " ")))
if __name__ == "__main__":
    from concurrent.futures import ThreadPoolExecutor
    ids = sys.argv[1:] or list(M)
    with ThreadPoolExecutor(3) as ex:
        for mid, res in ex.map(run, ids):
            print(mid, "=>", res, flush=True)
