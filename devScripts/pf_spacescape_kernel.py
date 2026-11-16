"""pf_spacescape kernel source (OpenCL C for the Copernicus OpenCL COP).

Single source of truth for the kernel text; create_pf_spacescape_hda.py imports it and
generates the per-layer `#bind parm` block (NSLOT float4 per layer, MAXL layers).

Port of Spacescape (petrocket/spacescape, SpacescapeNoiseMaterial.cpp GLSL) evaluated per
DIRECTION: noise = 3D gradient noise on the unit direction (so cube faces and equirect agree
and nothing seams); point/billboard stars are procedural (cube-face cell grids searched per pixel)
instead of GL point sprites; blend factors are Ogre's SBF_* factors applied to the running RGBA.
"""

MAXL = 12      # layers the multiparm can drive
NSLOT = 11     # float4 slots per layer (see SLOTS in create_pf_spacescape_hda.py)

COMMON = r"""
#define PF_PI 3.14159265358979f

inline uint pf_hash(uint x) {
    x ^= x >> 16; x *= 0x7feb352dU; x ^= x >> 15; x *= 0x846ca68bU; x ^= x >> 16; return x;
}
inline uint pf_h3(int a, int b, int c, uint s) {
    return pf_hash(pf_hash(pf_hash((uint)a + s * 0x9E3779B9U) + (uint)b * 0x85ebca6bU) + (uint)c * 0xc2b2ae35U);
}
inline float pf_u01(uint h) { return (float)(h >> 8) * (1.0f / 16777216.0f); }

// gradient noise, gradient components uniform in [-1,1]^3 like Spacescape's gradient texture
inline float pf_grad(int a, int b, int c, float3 f, uint s) {
    uint h = pf_h3(a, b, c, s);
    float3 g = (float3)(pf_u01(h), pf_u01(pf_hash(h + 1U)), pf_u01(pf_hash(h + 2U))) * 2.0f - 1.0f;
    return dot(g, f);
}
inline float pf_perlin(float3 p, uint s) {
    float3 fl = floor(p);
    float3 f = p - fl;
    int ix = (int)fl.x, iy = (int)fl.y, iz = (int)fl.z;
    float3 u = f * f * f * (f * (f * 6.0f - 15.0f) + 10.0f);
    float n000 = pf_grad(ix,   iy,   iz,   f, s);
    float n100 = pf_grad(ix+1, iy,   iz,   f - (float3)(1,0,0), s);
    float n010 = pf_grad(ix,   iy+1, iz,   f - (float3)(0,1,0), s);
    float n110 = pf_grad(ix+1, iy+1, iz,   f - (float3)(1,1,0), s);
    float n001 = pf_grad(ix,   iy,   iz+1, f - (float3)(0,0,1), s);
    float n101 = pf_grad(ix+1, iy,   iz+1, f - (float3)(1,0,1), s);
    float n011 = pf_grad(ix,   iy+1, iz+1, f - (float3)(0,1,1), s);
    float n111 = pf_grad(ix+1, iy+1, iz+1, f - (float3)(1,1,1), s);
    return mix(mix(mix(n000, n100, u.x), mix(n010, n110, u.x), u.y),
               mix(mix(n001, n101, u.x), mix(n011, n111, u.x), u.y), u.z);
}
// fbm (type 0) / ridged fbm (type 1), result in -1..1 like the source
inline float pf_fbm(float3 v, int oct, float lac, float gain, float off, int ridged, uint s) {
    float sum = 0.0f, amp = 1.0f, asum = 0.0f, prev = 1.0f;
    for (int i = 0; i < oct; i++) {
        float n = pf_perlin(v, s + (uint)i * 0x68E31DA4U);
        if (ridged) { float r = off - fabs(n); n = r * r; sum += n * amp * prev; prev = n; }
        else sum += n * amp;
        asum += amp; amp *= gain; v *= lac;
    }
    return sum / asum;
}
// the noise layer's scalar field 0..1: shelf, power, dither exactly as the Spacescape fragment shader
inline float pf_shape(float3 d, int ntype, uint seed, float scale, int oct, float lac, float gain,
                      float off, float shelf, float power, float dither) {
    float n = pf_fbm(d * scale, oct, lac, gain, off, ntype, seed);
    if (dither > 0.0f) n += pf_fbm(d * 10000.0f, ntype ? oct : 2, lac, gain, off, ntype, seed + 77U) * dither;
    n = n * 0.5f + 0.5f;
    n = fmax(0.0f, n - shelf);
    n *= 1.0f / fmax(1.0f - shelf, 1e-4f);
    return pow(fmax(n, 0.0f), 1.0f / fmax(power, 1e-4f));
}
inline float3 pf_ramp3(float t, float3 c_in, float3 c_mid, float3 c_out, int usemid, float midpos) {
    if (usemid == 0) return mix(c_out, c_in, t);
    midpos = clamp(midpos, 0.001f, 0.999f);
    return t < midpos ? mix(c_out, c_mid, t / midpos) : mix(c_mid, c_in, (t - midpos) / (1.0f - midpos));
}
// Ogre SBF_*: 0 one 1 zero 2 dest_colour 3 src_colour 4 1-dest_colour 5 1-src_colour
//             6 dest_alpha 7 src_alpha 8 1-dest_alpha 9 1-src_alpha
inline float4 pf_fac(int m, float4 s, float4 d) {
    switch (m) {
        case 1: return (float4)(0.0f);
        case 2: return d;
        case 3: return s;
        case 4: return (float4)(1.0f) - d;
        case 5: return (float4)(1.0f) - s;
        case 6: return (float4)(d.w);
        case 7: return (float4)(s.w);
        case 8: return (float4)(1.0f - d.w);
        case 9: return (float4)(1.0f - s.w);
        default: return (float4)(1.0f);
    }
}
// cube face frames for the star cell grids (internal to star placement; independent of the output layout)
inline void pf_face(int f, float3* n, float3* a, float3* b) {
    switch (f) {
        case 0: *n = (float3)( 1,0,0); *a = (float3)(0,0, 1); *b = (float3)(0,1,0); break;
        case 1: *n = (float3)(-1,0,0); *a = (float3)(0,0,-1); *b = (float3)(0,1,0); break;
        case 2: *n = (float3)(0, 1,0); *a = (float3)(1,0,0);  *b = (float3)(0,0, 1); break;
        case 3: *n = (float3)(0,-1,0); *a = (float3)(1,0,0);  *b = (float3)(0,0,-1); break;
        case 4: *n = (float3)(0,0, 1); *a = (float3)(-1,0,0); *b = (float3)(0,1,0); break;
        default:*n = (float3)(0,0,-1); *a = (float3)(1,0,0);  *b = (float3)(0,1,0); break;
    }
}
inline int pf_major(float3 d) {
    float ax = fabs(d.x), ay = fabs(d.y), az = fabs(d.z);
    if (ax >= ay && ax >= az) return d.x >= 0.0f ? 0 : 1;
    if (ay >= az) return d.y >= 0.0f ? 2 : 3;
    return d.z >= 0.0f ? 4 : 5;
}
// angular size of one output pixel (radians) for the shared layouts: 0 equirect, 1 cross, 2 single face
inline float pf_pixang(int xres, int yres, int layout) {
    if (layout == 0) return 2.0f * PF_PI / (float)xres;
    return (PF_PI * 0.5f) / (float)(layout == 1 ? yres / 3 : xres);
}
// flare profile around a star: core + glow + optional 4-spike cross. S is the angular size (radians)
inline float pf_flare(float3 d, float3 s, float S, float spikes, float pix) {
    float3 t1 = normalize(cross(s, fabs(s.y) < 0.95f ? (float3)(0,1,0) : (float3)(1,0,0)));
    float3 t2 = cross(s, t1);
    float3 p = d - s * dot(d, s);
    float x = dot(p, t1), y = dot(p, t2);
    float r2 = x * x + y * y;
    float sc = fmax(S * 0.12f, 0.6f * pix);
    float I = exp(-r2 / (2.0f * sc * sc)) * fmin(1.0f, (S * 0.12f) * (S * 0.12f) / (sc * sc));
    float sg = S * 0.3f;
    I += 0.06f * exp(-sqrt(r2) / fmax(sg, 0.5f * pix));
    if (spikes > 0.0f) {
        float w = fmax(S * 0.02f, 0.5f * pix), L = S * 0.8f;
        I += spikes * (exp(-fabs(y) / w) * exp(-fabs(x) / L) + exp(-fabs(x) / w) * exp(-fabs(y) / L)) * 0.5f;
    }
    return I;
}
"""

# Stars: one function for point stars (mode 0) and billboards (mode 1).
# LP: lp[j] is the j-th float4 slot of the layer. Stars live on cube-face cell grids; the pixel checks the faces
# it is near (major axis |d_axis| > 0.35) and the cells around it. A star is only drawn from its own major face.
STARS = r"""
inline float4 pf_stars(float3 d, int mode, float4 P[NSLOT], float pix, float refpix) {
    uint seed = (uint)P[0].y;
    float count = fmax(P[5].x, 1.0f);
    float size = P[5].y, sizemax = P[5].z;
    float3 cnear = P[3].xyz, cfar = P[4].xyz;
    float hdrm = P[3].w, hdrp = P[4].w;
    float spikes = P[2].x;
    int maskon = (int)(P[6].y + 0.5f);
    float G = fmax(ceil(sqrt(count / (6.0f * 0.5236f))), 3.0f);
    float p0 = fmin(1.0f, count / (6.0f * G * G * 0.5236f));
    float cell = 2.0f / G;
    float foot = (mode == 0) ? 4.0f * size * refpix * 0.4f : fmax(size, sizemax) * 1.6f;
    foot = fmax(foot, 2.0f * pix);
    int reach = (int)clamp(ceil(foot * 1.5f / cell), 1.0f, 2.0f);
    float3 acc = (float3)(0.0f); float amax = 0.0f;
    for (int face = 0; face < 6; face++) {
        float3 n, a, b; pf_face(face, &n, &a, &b);
        float dn = dot(d, n);
        if (dn < 0.35f) continue;
        float u = dot(d, a) / dn, v = dot(d, b) / dn;
        int cu = (int)floor((u + 1.0f) * 0.5f * G), cv = (int)floor((v + 1.0f) * 0.5f * G);
        for (int j = -reach; j <= reach; j++) for (int i = -reach; i <= reach; i++) {
            int ci = cu + i, cj = cv + j;
            if (ci < 0 || cj < 0 || ci >= (int)G || cj >= (int)G) continue;
            uint h = pf_h3(ci, cj, face, seed * 2654435761U + 12345U);
            float r1 = pf_u01(h), r2 = pf_u01(pf_hash(h + 1U)), r3 = pf_u01(pf_hash(h + 2U)), r4 = pf_u01(pf_hash(h + 3U));
            float r5 = pf_u01(pf_hash(h + 4U));
            float us = ((float)ci + r1) / G * 2.0f - 1.0f, vs = ((float)cj + r2) / G * 2.0f - 1.0f;
            float w = 1.0f + us * us + vs * vs;
            if (r3 > p0 * rsqrt(w * w * w)) continue;      // density compensation of the gnomonic grid
            float3 s = normalize(n + a * us + b * vs);
            if (pf_major(s) != face) continue;
            if (maskon) {
                float m = pf_shape(s, (int)(P[6].w + 0.5f), (uint)P[6].z, P[7].x, (int)(P[7].y + 0.5f), P[7].z, P[7].w,
                                   P[8].x, P[8].z, P[8].y, 0.0f);
                if (r5 > m * m) continue;               // source: keep star when rand < mask^2
            }
            float dist = r4;
            if (hdrp != 1.0f) dist = pow(dist, hdrp);
            float3 c = (cnear + dist * (cfar - cnear)) * hdrm;
            float I;
            if (mode == 0) {
                float sg0 = size * refpix * 0.4f;
                float sg = fmax(sg0, 0.5f * pix);
                float t2 = 2.0f * (1.0f - dot(d, s));
                I = exp(-t2 / (2.0f * sg * sg)) * fmin(1.0f, (sg0 * sg0) / (sg * sg));
            } else {
                float S = (size + (sizemax - size) * (1.0f - dist));
                I = pf_flare(d, s, S, spikes, pix);
            }
            acc += c * I; amax = fmax(amax, I);
        }
    }
    return (float4)(acc, fmin(amax, 1.0f));
}
"""

MAIN = r"""
@KERNEL
{
    float pix = pf_pixang(@xres, @yres, @layout);
    float4 dd = pf_space_dir(@ix, @iy, @xres, @yres, @layout, @face, @convention);
    float3 d = dd.xyz;
    float refpix = @refres > 0.0f ? (PF_PI * 0.5f) / fmax((float)@refres, 16.0f) : pix;   // 0 = star size in real output pixels
    float4 acc = (float4)(0.0f);
    float4 P[NSLOT];
    int nl = clamp((int)@nlayers, 0, MAXL);
    for (int L = 0; L < MAXL; L++) {
        if (L >= nl) break;
//@FETCH
        int type = (int)(P[0].x + 0.5f);
        if ((int)(P[0].w + 0.5f) == 0) continue;
        float4 src = (float4)(0.0f);
        int maskon = (int)(P[6].y + 0.5f);
        float mval = 1.0f;
        if (maskon && type != 1 && type != 2)
            mval = pf_shape(d, (int)(P[6].w + 0.5f), (uint)P[6].z, P[7].x, (int)(P[7].y + 0.5f), P[7].z, P[7].w,
                            P[8].x, P[8].z, P[8].y, 0.0f);
        if (type == 0) {          // noise
            float n = pf_shape(d, (int)(P[0].z + 0.5f), (uint)P[0].y, P[1].x, (int)(P[1].y + 0.5f), P[1].z, P[1].w,
                               P[2].x, P[2].z, P[2].y, P[2].w);
            n = pow(n, P[4].w);
            float3 c = pf_ramp3(n, P[3].xyz, P[10].xyz, P[4].xyz, (int)(P[10].w + 0.5f), P[8].w);
            src = (float4)(c, n) * P[3].w * mval;
        } else if (type == 1) {   // point stars
            src = pf_stars(d, 0, P, pix, refpix);
        } else if (type == 2) {   // billboard stars
            src = pf_stars(d, 1, P, pix, refpix);
        } else if (type == 3) {   // sun: size = angular radius (rad), colour in = core, out = halo
            float3 s = normalize(P[9].xyz);
            float S = fmax(P[5].y, 1e-4f);
            float t2 = 2.0f * (1.0f - dot(d, s));
            float core = exp(-t2 / (2.0f * S * S * 0.0625f));
            float halo = exp(-sqrt(fmax(t2, 0.0f)) / (S * 3.0f));
            float I = pf_flare(d, s, S * 6.0f, P[2].x, pix);
            float3 c = (P[3].xyz * (core + I) + P[4].xyz * halo * 0.5f) * P[3].w;
            src = (float4)(c, fmin(1.0f, core + halo)) * mval;
        } else if (type == 4) {   // gradient / band along an axis
            float3 ax = normalize(P[9].xyz);
            float a = dot(d, ax);
            float t;
            if ((int)(P[0].z + 0.5f) == 0) { float w = fmax(P[5].y, 1e-3f); t = exp(-a * a / (2.0f * w * w)); }
            else t = a * 0.5f + 0.5f;
            t = pow(clamp(t, 0.0f, 1.0f), 1.0f / fmax(P[2].y, 1e-4f));
            float3 c = pf_ramp3(t, P[3].xyz, P[10].xyz, P[4].xyz, (int)(P[10].w + 0.5f), P[8].w);
            src = (float4)(c, t) * P[3].w * mval;
        }
        float4 sf = pf_fac((int)(P[5].w + 0.5f), src, acc), df = pf_fac((int)(P[6].x + 0.5f), src, acc);
        acc = src * sf + acc * df;
    }
    float3 rgb = acc.xyz * dd.w;
    @color.set((float4)(rgb, dd.w));
}
"""

# fetch block: P[j] = @L<L>_<j> for the runtime L. Generated as a switch so every binding stays a plain constant.
def fetch_block():
    lines = ["        switch (L) {"]
    for L in range(MAXL):
        lines.append("        case %d:" % L)
        for j in range(NSLOT):
            lines.append("            P[%d] = @L%d_%d;" % (j, L, j))
        lines.append("            break;")
    lines.append("        }")
    return "\n".join(lines)

def build_kernel(space_dir_cl):
    binds = ["#bind layer !size_ref?", "#bind layer !&color",
             "#bind parm layout int val=0", "#bind parm face int val=0", "#bind parm convention int val=0",
             "#bind parm refres float val=0", "#bind parm nlayers int val=0"]
    for L in range(MAXL):
        for j in range(NSLOT):
            binds.append("#bind parm L%d_%d float4" % (L, j))
    pre = "#define MAXL %d\n#define NSLOT %d\n" % (MAXL, NSLOT)
    return "\n".join(binds) + "\n" + pre + space_dir_cl + COMMON + STARS + MAIN.replace("//@FETCH", fetch_block())
