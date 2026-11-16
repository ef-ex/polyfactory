"""pf_custom_planet kernel source (OpenCL C for the Copernicus OpenCL COP) + the parameter packing table.

Single source of truth for the kernel; create_pf_custom_planet_hda.py imports it.
Recreates the Blender "Custom Planet 1.0" billboard shader (node group MATERIAL_PREFAB in Library.blend)
and extends it to full-sphere maps: every layer is a function of a direction on the sphere, either read from
the library disc images (orthographic views of a sphere, radius PR in uv units) or generated procedurally.
Noise comes from the spacescape kernel (COMMON) so both tools share one hash/noise.
See ideas/spacetools.md "## Custom planet".
"""
import pf_spacescape_kernel as _K

# name, default: float parms bound to the kernel, packed 4 per float4 slot. Menus/toggles are floats too (kernel casts).
# The HDA parm of the same name feeds it through ch("../name"). Colours (COLOR_PARMS) use name+"r/g/b".
PARMS = [
    ("mode", 0), ("layout", 0), ("face", 0), ("convention", 0),
    ("seed", 1), ("ptype", 0), ("pscale", 1.0), ("rough", 0.5),
    ("sea", 0.45), ("polar", 0.25), ("cloud_cov", 0.5), ("bump", 1.0),
    ("water_proc", 0), ("emis_proc", 0), ("cloud_proc", 0), ("atm_proc", 0),
    ("view_lon", 0.0), ("view_lat", 0.0), ("spin", 0.0), ("sun_az", 60.0),
    ("sun_el", 10.0), ("shadow_bright", 0.0), ("emission_overall", 2.0), ("night_sat", 0.5),
    ("s_rot", 0.0), ("s_hue", 0.0), ("s_sat", 1.0), ("s_val", 1.0),
    ("s_contrast", 0.0), ("useramp", 0), ("whitepoint", 1.0), ("rampmid", 0.5),
    ("r_hue", 0.0), ("r_sat", 1.0), ("r_val", 1.0), ("r_contrast", 0.0),
    ("w_blend", 1.0), ("w_rot", 0.0), ("e_strength", 1.0), ("e_rot", 0.0),
    ("e_shadowvis", 1.0), ("e_hue", 0.0), ("e_sat", 1.0), ("c_blend", 1.0),
    ("c_thick", 1.0), ("c_bright", 1.0), ("a_strength", 1.0), ("a_sat", 1.0),
    ("a_center", 0.7), ("a_wrim", 1.0), ("a_size", 1.0), ("hscale", 1.0),
    ("have_surf", 0), ("have_watr", 0), ("have_emis", 0), ("have_clds", 0),
    ("have_atmo", 0), ("have_wrim", 0), ("have_lset", 0), ("have_mask", 0),
]
COLOR_PARMS = [
    ("tint", (1, 1, 1)), ("ramp0", (0, 0, 0)), ("ramp1", (0.5, 0.5, 0.5)), ("ramp2", (1, 1, 1)),
    ("w_color", (0.02, 0.07, 0.18)), ("a_color", (0.0, 0.259, 1.0)),
]
NPS = (len(PARMS) + 3) // 4
PR = 0.3857          # planet radius in uv units of the library discs (measured: alpha edge 0.1143 .. 0.8857)
IMAGES = ["surf", "watr", "emis", "clds", "atmo", "wrim", "lset", "mask"]   # optional layer inputs, in order
OUTPUTS = [("beauty", 4), ("surface", 4), ("clouds", 4), ("emission", 3), ("atmosphere", 4), ("water", 1), ("height", 1), ("normal", 3)]


def binds():
    out = ["#bind layer !size_ref?"]
    for n in IMAGES:
        out.append("#bind layer %s? float4 border=%s" % (n, "wrap" if n in ("clds", "atmo", "wrim", "lset") else "constant"))
    for n, _ in OUTPUTS:
        out.append("#bind layer !&%s" % n)
    for i in range(NPS):
        out.append("#bind parm P%d float4" % i)
    for n, _ in COLOR_PARMS:
        out.append("#bind parm C_%s float4" % n)
    defs = ["#define %s (@P%d.%s)" % (n, i // 4, "xyzw"[i % 4]) for i, (n, _) in enumerate(PARMS)]
    defs += ["#define %s (@C_%s.xyz)" % (n, n) for n, _ in COLOR_PARMS]
    return "\n".join(out) + "\n", "\n".join(defs) + "\n#define PR %.4ff\n" % PR


FUNCS = r"""
#define IP(x) ((int)((x) + 0.5f))
inline float pf_luma(float3 c) { return dot(c, (float3)(0.2126f, 0.7152f, 0.0722f)); }
inline float3 pf_rgb2hsv(float3 c) {
    float mx = fmax(c.x, fmax(c.y, c.z)), mn = fmin(c.x, fmin(c.y, c.z)), d = mx - mn, h = 0.0f;
    if (d > 1e-12f) {
        if (mx == c.x) h = (c.y - c.z) / d; else if (mx == c.y) h = 2.0f + (c.z - c.x) / d; else h = 4.0f + (c.x - c.y) / d;
        h /= 6.0f; if (h < 0.0f) h += 1.0f;
    }
    return (float3)(h, mx > 1e-12f ? d / mx : 0.0f, mx);
}
inline float3 pf_hsv2rgb(float3 c) {
    float h = (c.x - floor(c.x)) * 6.0f;
    float3 r = clamp((float3)(fabs(h - 3.0f) - 1.0f, 2.0f - fabs(h - 2.0f), 2.0f - fabs(h - 4.0f)), 0.0f, 1.0f);
    return ((r - 1.0f) * c.y + 1.0f) * c.z;
}
// Blender Hue/Saturation/Value node (hue 0.5 = neutral), fac 1
inline float3 pf_hsvnode(float3 c, float hue, float sat, float val) {
    float3 h = pf_rgb2hsv(c);
    h.x = h.x + hue - 0.5f; h.x -= floor(h.x);
    h.y = clamp(h.y * sat, 0.0f, 1.0f); h.z *= val;
    return fmax(pf_hsv2rgb(h), 0.0f);
}
inline float3 pf_bc(float3 c, float contrast) { return fmax((1.0f + contrast) * c - contrast * 0.5f, 0.0f); }
inline float3 pf_mix3(float3 a, float3 b, float f) { return a + (b - a) * f; }
inline float4 pf_unpre(float4 c) { if (c.w > 1e-5f) c.xyz /= c.w; return c; }   // Blender's image node returns straight colour
inline float pf_sat(float x) { return clamp(x, 0.0f, 1.0f); }
inline float3 pf_rotz(float3 v, float a) { float c = cos(a), s = sin(a); return (float3)(c * v.x - s * v.y, s * v.x + c * v.y, v.z); }
inline float2 pf_rot2(float2 p, float a) { float c = cos(a), s = sin(a); return (float2)(c * p.x - s * p.y, s * p.x + c * p.y); }
// the view frame: z = direction the disc image faces (lon/lat), x right, y up; spin about z
inline void pf_frame(float lon, float lat, float spin, float3* X, float3* Y, float3* Z) {
    float3 z = (float3)(sin(lon) * cos(lat), sin(lat), -cos(lon) * cos(lat));
    float3 up = fabs(z.y) > 0.999f ? (float3)(0, 0, -1) : (float3)(0, 1, 0);
    float3 x = normalize(cross(up, z)), y = cross(z, x);
    float c = cos(spin), s = sin(spin);
    *X = x * c + y * s; *Y = y * c - x * s; *Z = z;
}
inline float pf_tri(float3 d, uint s, int seed, float sc, int oct, float gain) {   // fbm 0..1
    return clamp(0.5f + 0.9f * pf_fbm(d * sc, oct, 2.0f, gain, 1.0f, 0, (uint)seed + s), 0.0f, 1.0f);
}
inline float pf_ridge(float3 d, int seed, float sc, int oct) {                       // 0..1, 1 on the ridge line
    float n = pf_fbm(d * sc, oct, 2.0f, 0.5f, 1.0f, 0, (uint)seed + 911U);
    return 1.0f - clamp(fabs(n) * 5.0f, 0.0f, 1.0f);
}
inline float pf_craters(float3 d, float sc, uint s) {                                // bowl + raised rim, height delta
    float3 p = d * sc, ic = floor(p);
    float h = 0.0f;
    for (int a = -1; a <= 1; a++) for (int b = -1; b <= 1; b++) for (int c = -1; c <= 1; c++) {
        int cx = (int)ic.x + a, cy = (int)ic.y + b, cz = (int)ic.z + c;
        uint hh = pf_h3(cx, cy, cz, s);
        if (pf_u01(pf_hash(hh + 7U)) > 0.55f) continue;
        float3 cen = (float3)((float)cx, (float)cy, (float)cz) + (float3)(pf_u01(hh), pf_u01(pf_hash(hh + 1U)), pf_u01(pf_hash(hh + 2U)));
        float r = 0.12f + 0.3f * pf_u01(pf_hash(hh + 3U));
        float q = length(p - cen) / r;
        if (q < 1.0f) h += -1.0f * (1.0f - q * q) * r;
        h += 0.16f * r * exp(-(q - 1.0f) * (q - 1.0f) * 25.0f);
    }
    return h;
}
inline float pf_pheight(float3 d, int seed, int ptype, float sc, float rough, float sea) {
    if (ptype == 4) return 0.5f;
    float h = pf_tri(d, 0U, seed, 1.6f * sc, 7, rough);
    if (ptype == 5) return clamp(0.5f + 0.5f * pf_craters(d, 5.0f * sc, 31U + (uint)seed) + 0.5f * pf_craters(d, 14.0f * sc, 77U + (uint)seed) + 0.25f * (h - 0.5f), 0.0f, 1.0f);
    if (ptype == 2) return clamp(0.5f + 0.3f * (h - 0.5f) - 0.12f * pf_ridge(d, seed, 3.0f * sc, 5), 0.0f, 1.0f);
    if (ptype == 0) return fmax(h, sea);
    return h;
}
// colour + ocean mask + emission of the procedural planet at planet-space direction d
inline float3 pf_psurface(float3 d, int seed, int ptype, float sc, float rough, float sea, float polar, float h,
                          float* ocean, float3* emis) {
    *ocean = 0.0f; *emis = (float3)(0.0f);
    float n2 = pf_tri(d, 5U, seed, 6.0f * sc, 5, 0.55f);
    float n3 = pf_tri(d, 9U, seed, 24.0f * sc, 4, 0.5f);
    float lat = fabs(d.y);
    float3 c;
    if (ptype == 0) {                                      // terran
        float hh = pf_tri(d, 0U, seed, 1.6f * sc, 7, rough);
        float el = clamp((hh - sea) / fmax(1.0f - sea, 1e-3f), 0.0f, 1.0f);
        float dry = smoothstep(0.35f, 0.75f, n2 + 0.25f * (1.0f - lat * 3.0f));
        float3 low = pf_mix3((float3)(0.10f, 0.24f, 0.07f), (float3)(0.42f, 0.34f, 0.18f), dry);
        c = pf_mix3(low, (float3)(0.30f, 0.24f, 0.18f), smoothstep(0.25f, 0.6f, el + 0.2f * (n3 - 0.5f)));
        c = pf_mix3(c, (float3)(0.8f, 0.8f, 0.82f), smoothstep(0.6f, 0.9f, el));
        c *= 0.85f + 0.3f * n3;
        float oc = smoothstep(sea + 0.012f, sea - 0.012f, hh);
        *ocean = oc * (0.72f + 0.28f * smoothstep(sea - 0.22f, sea, hh));
        c = pf_mix3(c, (float3)(0.04f, 0.08f, 0.14f), oc);
        float ice = smoothstep(1.0f - polar - 0.06f * n2, 1.0f - polar + 0.06f, lat + 0.07f * (n2 - 0.5f));
        c = pf_mix3(c, (float3)(0.9f, 0.93f, 0.96f), ice);
        *ocean *= 1.0f - ice;
        float city = smoothstep(0.58f, 0.78f, pf_tri(d, 13U, seed, 7.0f * sc, 4, 0.5f)) * smoothstep(0.45f, 0.7f, n3) * (1.0f - oc) * (1.0f - ice);
        *emis = (float3)(1.0f, 0.72f, 0.38f) * city * 1.5f;
    } else if (ptype == 1) {                               // desert
        float a = pf_tri(d, 0U, seed, 1.6f * sc, 7, rough);
        c = pf_mix3((float3)(0.62f, 0.36f, 0.19f), (float3)(0.80f, 0.60f, 0.40f), smoothstep(0.3f, 0.7f, n2));
        c = pf_mix3(c, (float3)(0.22f, 0.15f, 0.13f), smoothstep(0.55f, 0.75f, a) * 0.8f);
        c *= 0.85f + 0.3f * n3;
        float pe = 1.0f - polar * 0.6f;
        c = pf_mix3(c, (float3)(0.93f, 0.9f, 0.88f), smoothstep(pe, pe + 0.08f, lat + 0.06f * (n2 - 0.5f)));
    } else if (ptype == 2) {                               // ice
        float rid = pf_ridge(d, seed, 3.0f * sc, 5);
        c = pf_mix3((float3)(0.72f, 0.84f, 0.95f), (float3)(0.93f, 0.97f, 1.0f), n2);
        c = pf_mix3(c, (float3)(0.25f, 0.45f, 0.7f), smoothstep(0.55f, 0.9f, rid) * 0.7f);
        c *= 0.9f + 0.2f * n3;
    } else if (ptype == 3) {                               // lava
        float rid = pf_ridge(d, seed, 4.0f * sc, 6);
        c = pf_mix3((float3)(0.03f, 0.025f, 0.025f), (float3)(0.12f, 0.08f, 0.07f), n2) * (0.7f + 0.6f * n3);
        float cr = pow(smoothstep(0.55f, 0.95f, rid), 2.0f);
        c = pf_mix3(c, (float3)(0.4f, 0.08f, 0.02f), cr * 0.5f);
        *emis = (float3)(1.0f, 0.28f, 0.04f) * cr * 4.0f;
    } else if (ptype == 4) {                               // gas giant
        float w = pf_fbm(d * (float3)(1.5f, 6.0f, 1.5f) * sc, 5, 2.0f, 0.5f, 1.0f, 0, (uint)seed + 17U);
        float band = 0.5f + 0.5f * sin((d.y * 7.0f * sc + 2.7f * w) * 3.14159265f);
        float b2 = pf_tri(d * (float3)(1, 3, 1), 3U, seed, 5.0f * sc, 4, 0.5f);
        c = pf_mix3((float3)(0.82f, 0.68f, 0.48f), (float3)(0.93f, 0.9f, 0.82f), band);
        c = pf_mix3(c, (float3)(0.55f, 0.3f, 0.18f), smoothstep(0.55f, 0.8f, b2) * (1.0f - band) * 0.9f);
        c *= 0.9f + 0.2f * n3;
    } else {                                               // moon / barren
        c = pf_mix3((float3)(0.30f, 0.29f, 0.28f), (float3)(0.52f, 0.5f, 0.47f), n2) * (0.5f + 1.0f * h) * (0.85f + 0.3f * n3);
    }
    return c;
}
inline float4 pf_pclouds(float3 d, int seed, float sc, float cov) {
    float3 q = d * 2.2f * sc;
    float w = pf_fbm(q * 0.7f, 4, 2.0f, 0.5f, 1.0f, 0, (uint)seed + 301U);
    float n = 0.5f + 0.9f * pf_fbm(q + (float3)(w, -w, w) * 1.5f, 7, 2.0f, 0.55f, 1.0f, 0, (uint)seed + 303U);
    float a = smoothstep(1.0f - cov - 0.05f, 1.0f - cov + 0.3f, n);
    return (float4)((float3)(0.9f + 0.1f * n), a * 0.95f);
}
"""

MAIN = r"""
@KERNEL
{
    int xr = @xres, yr = @yres;
    int md = IP(mode);
    int seedi = IP(seed), pt = IP(ptype);
    float2 uv = (float2)(((float)@ix + 0.5f) / (float)xr, ((float)@iy + 0.5f) / (float)yr);
    float3 X, Y, Z;
    pf_frame(radians(view_lon), radians(view_lat), radians(spin), &X, &Y, &Z);
    float2 uvb; float3 dv; float inside; float pixang; float2 pp = (float2)(0.0f);
    if (md == 0) {                                           // billboard: the library disc frame
        pp = (uv - 0.5f) / PR;
        float r2 = dot(pp, pp);
        inside = r2 < 1.0f ? 1.0f : 0.0f;
        dv = (float3)(pp.x, pp.y, sqrt(fmax(1.0f - r2, 0.0f)));
        uvb = uv;
        pixang = 1.0f / (PR * (float)xr);
    } else {                                                 // sphere maps: direction -> disc uv (back side mirrored)
        float4 dd = pf_space_dir(@ix, @iy, xr, yr, IP(layout), IP(face), IP(convention));
        inside = dd.w;
        dv = (float3)(dot(dd.xyz, X), dot(dd.xyz, Y), dot(dd.xyz, Z));
        uvb = (float2)(0.5f + PR * dv.x, 0.5f + PR * dv.y);
        pixang = md == 1 ? (IP(layout) == 0 ? 6.2831853f / (float)xr : 1.5707963f / (float)(IP(layout) == 1 ? yr / 3 : xr)) : 0.01f;
    }
    float aS = radians(s_rot), aW = radians(w_rot), aE = radians(e_rot);
    float3 dS = pf_rotz(dv, aS);                             // view-space direction as seen by each rotated layer
    float2 uS = pf_rot2(uvb - 0.5f, aS) + 0.5f, uW = pf_rot2(uvb - 0.5f, aW) + 0.5f, uE = pf_rot2(uvb - 0.5f, aE) + 0.5f;
    float3 dW = pf_rotz(dv, aW), dE = pf_rotz(dv, aE);
    float3 pS = X * dS.x + Y * dS.y + Z * dS.z, pW = X * dW.x + Y * dW.y + Z * dW.z, pE = X * dE.x + Y * dE.y + Z * dE.z;
    int bill = md == 0;

    // ---- lighting image (billboard only)
    float3 ls = (float3)(1.0f);
    if (bill) {
        if (have_lset) ls = @lset.textureSample(uvb).xyz;
        else {
            float az = radians(sun_az), el = radians(sun_el);
            float3 sv = (float3)(sin(az) * cos(el), sin(el), cos(az) * cos(el));
            ls = (float3)(2.2f * smoothstep(-0.12f, 0.5f, dot(dv, sv)) * inside);
        }
    }
    float lsl = pf_luma(ls);

    // ---- height (3 taps for the normal) and the surface
    float3 t1 = normalize(cross(dS, fabs(dS.y) > 0.9f ? (float3)(1, 0, 0) : (float3)(0, 1, 0)));
    float3 t2 = cross(dS, t1);
    float eps = 1.5f * pixang;
    float hk[3];
    for (int k = 0; k < 3; k++) {
        float3 q = normalize(dS + (k == 1 ? t1 : (k == 2 ? t2 : (float3)(0.0f))) * eps);
        float hq;
        if (have_surf) hq = pf_luma(@surf.textureSample((float2)(q.x, q.y) * PR + 0.5f).xyz);
        else hq = pf_pheight(X * q.x + Y * q.y + Z * q.z, seedi, pt, pscale, rough, sea);
        hk[k] = hq;
    }
    float3 gd = ((hk[1] - hk[0]) * t1 + (hk[2] - hk[0]) * t2) / eps;
    float3 nv = normalize(dS - 0.1f * bump * hscale * gd);
    float3 npl = X * nv.x + Y * nv.y + Z * nv.z;

    float4 S; float oceanP = 0.0f; float3 emisP = (float3)(0.0f);
    float3 pcol = (float3)(0.0f);
    if (inside > 0.0f) pcol = pf_psurface(pS, seedi, pt, pscale, rough, sea, polar, hk[0], &oceanP, &emisP);
    if (have_surf) S = pf_unpre(@surf.textureSample(uS));
    else S = (float4)(pcol, inside);
    float3 s1 = pf_bc(S.xyz, s_contrast * 0.25f);
    float3 s2 = pf_hsvnode(s1, s_hue + 0.5f, s_sat, s_val) * tint;
    if (IP(useramp)) {
        float t = pf_sat(pf_luma(s2) / fmax(whitepoint, 1e-4f));
        float mp = clamp(rampmid, 0.001f, 0.999f);
        float3 rc = t < mp ? pf_mix3(ramp0, ramp1, t / mp) : pf_mix3(ramp1, ramp2, (t - mp) / (1.0f - mp));
        s2 = pf_bc(pf_hsvnode(rc, r_hue + 0.5f, r_sat, r_val), r_contrast * 0.25f);
    }
    float3 s5 = s2;
    if (bill) s5 = pf_mix3(pf_hsvnode(s2, 0.5f, night_sat, 1.0f), s2, pf_sat(lsl / 0.011f));

    // ---- water
    float wm = 0.0f;
    if (have_watr) wm = pf_luma(pf_unpre(@watr.textureSample(uW)).xyz) * w_blend;
    else if (IP(water_proc)) wm = oceanP * w_blend;
    float wmc = pf_sat(wm);
    float3 w01 = pf_mix3(s5, w_color, wmc);
    float3 w02 = pf_mix3(w_color, w01, pf_sat(S.w));
    float3 w03 = w02, lsx = (float3)(1.0f);
    float mimg = inside;
    if (bill) {
        lsx = fmax(ls, (float3)(1.0f) * (shadow_bright * 0.01f));
        w03 = w02 * lsx;
        if (have_mask) mimg = pf_luma(@mask.textureSample(uS).xyz);
    }
    float3 w04 = w03 * mimg;

    // ---- emission
    float3 em = (float3)(0.0f);
    if (have_emis) em = @emis.textureSample(uE).xyz;
    else if (IP(emis_proc)) em = emisP;
    float m = bill ? lsl * (1.0f - e_shadowvis) : 0.0f;
    float3 e01 = clamp(em * (1.0f - m), 0.0f, 1.0f);
    float3 e02 = pf_hsvnode(e01, e_hue + 0.5f, e_sat, fmax(e_strength, 0.0f));
    float3 e04 = e02 * (1.0f - wm);
    float3 e05 = w04 + e04;

    // ---- clouds
    float4 C = (float4)(0.0f);
    if (have_clds) C = pf_unpre(@clds.textureSample(uvb));
    else if (IP(cloud_proc) && inside > 0.0f) {
        C = pf_pclouds(pS, seedi, pscale, cloud_cov);
        if (bill) C.xyz *= pf_sat(lsl) + 0.02f;
    }
    float gam = 1.0f - shadow_bright + 0.23f;
    float3 cc = pow(fmax(C.xyz, 0.0f), gam) * c_bright;
    float ca = C.w * c_thick * c_blend;
    float3 c03 = pf_mix3(e05, cc, pf_sat(ca));

    // ---- atmosphere (billboard only) + white rim
    float3 a01 = (float3)(0.0f); float afac = 0.0f; float3 a04 = c03; float3 a06 = (float3)(0.0f);
    if (bill) {
        float4 A = (float4)(0.0f);
        if (have_atmo) A = pf_unpre(@atmo.textureSample(uvb));
        else if (IP(atm_proc)) {
            float r = length(pp);
            float prof = r < 1.0f ? pow(1.0f - dv.z, 4.0f) * 0.7f : exp(-(r - 1.0f) / (0.06f * a_size)) * 0.7f;
            prof *= pf_sat(lsl) + 0.03f;
            A = (float4)((float3)(0.25f, 0.6f, 1.0f) * prof, prof);
        }
        float3 ag = pow(fmax(A.xyz, 0.0f), gam);
        float3 ah = pf_hsvnode(ag, 0.5f, a_sat, 1.0f);
        float3 hb = pf_rgb2hsv(a_color);
        a01 = ah;
        if (hb.y != 0.0f) { float3 ha = pf_rgb2hsv(ah); ha.x = hb.x; a01 = pf_hsv2rgb(ha); }
        float d = length(uv - 0.5f);
        float g = 1.0f - 1.03f * sqrt(d * d + 0.25f); g = fmax(g, 0.0f); g *= g;
        float aa = A.w * a_strength;
        float a02 = aa * (1.0f - a_center + a_center * (1.0f - 5.14f * g));
        afac = pf_sat(a02);
        float3 a03 = c03 + afac * a01;
        float4 R = (float4)(0.0f);
        if (have_wrim) R = @wrim.textureSample(uvb);
        a06 = R.xyz * ls;
        float fr = pf_sat(pf_luma(R.xyz) * a_wrim);
        a04 = a03 + fr * a06;
    }
    float alpha = 1.0f;
    if (bill) {
        float d = length(uv - 0.5f);
        float g = 1.0f - 1.335f * sqrt(d * d + 0.25f); g = fmax(g, 0.0f); g *= g;
        float rr = pf_sat((g - 0.018f) / 0.013f);
        alpha = pf_sat(rr * 16.62f - 7.81f);
    }
    float3 fin = a04 * (bill ? emission_overall : 1.0f);

    @beauty.set((float4)(fin, alpha));
    @surface.set((float4)(w04, S.w));
    @clouds.set((float4)(cc, pf_sat(ca)));
    @emission.set((float4)(e04, 1.0f));
    @atmosphere.set((float4)(a01, afac));
    @water.set(wmc);
    @height.set(hk[0] * hscale);
    @normal.set((float4)(0.5f * npl + 0.5f, 1.0f));
}
"""


def build_kernel(space_dir_cl):
    pre = _K.COMMON
    b, d = binds()
    return b + space_dir_cl + pre + FUNCS + d + MAIN
