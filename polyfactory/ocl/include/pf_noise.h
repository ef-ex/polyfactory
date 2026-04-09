/*
 * pf_noise.h — Polyfactory noise primitives for Copernicus OpenCL kernels.
 *
 * Include:  #include "pf_noise.h"
 * Requires: pf_hash.h (for pf_hash21, pf_hash2d, pf_lattice, etc.)
 *           pf_util.h (for pf_fract, pf_qerp*, pf_grad, pf_interp)
 */
#ifndef __PF_NOISE_H__
#define __PF_NOISE_H__

#include "pf_util.h"
#include "pf_hash.h"

// ═══════════════════════════════════════════════════════════════════════════
// 2D Value Noise (fract-based hash)
// ═══════════════════════════════════════════════════════════════════════════

// Non-tileable
inline float pf_value_noise(float2 p)
{
    float2 i = floor(p);
    float2 f = pf_fract(p);
    float2 u = f * f * (3.0f - 2.0f * f);

    float a = pf_hash21(i);
    float b = pf_hash21(i + (float2)(1.0f, 0.0f));
    float c = pf_hash21(i + (float2)(0.0f, 1.0f));
    float d = pf_hash21(i + (float2)(1.0f, 1.0f));

    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// Tileable — wraps cell indices at tile period via fmod.
// Period MUST be integer for clean wrapping.
inline float pf_value_noise_t(float2 p, float2 per)
{
    float2 i = floor(p);
    float2 f = p - i;
    float2 u = f * f * f * (f * (f * 6.0f - 15.0f) + 10.0f);

    float2 i00 = fmod(fmod(i, per) + per, per);
    float2 i10 = fmod(fmod(i + (float2)(1.0f, 0.0f), per) + per, per);
    float2 i01 = fmod(fmod(i + (float2)(0.0f, 1.0f), per) + per, per);
    float2 i11 = fmod(fmod(i + (float2)(1.0f, 1.0f), per) + per, per);

    float a = pf_hash21(i00);
    float b = pf_hash21(i10);
    float c = pf_hash21(i01);
    float d = pf_hash21(i11);

    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}

// ═══════════════════════════════════════════════════════════════════════════
// 2D FBM (fract-based value noise)
// ═══════════════════════════════════════════════════════════════════════════

// Non-tileable
inline float pf_fbm(float2 p, int oct)
{
    float sum = 0.0f;
    float amp = 1.0f;
    float freq = 1.0f;
    float max_amp = 0.0f;
    for (int i = 0; i < 8; i++) {
        if (i >= oct) break;
        sum += pf_value_noise(p * freq) * amp;
        max_amp += amp;
        amp *= 0.5f;
        freq *= 2.0f;
    }
    return sum / max_amp;
}

// Tileable — each octave doubles freq and period together
inline float pf_fbm_t(float2 p, int oct, float2 per)
{
    float sum = 0.0f;
    float amp = 1.0f;
    float freq = 1.0f;
    float max_amp = 0.0f;
    for (int i = 0; i < 8; i++) {
        if (i >= oct) break;
        sum += pf_value_noise_t(p * freq, per * freq) * amp;
        max_amp += amp;
        amp *= 0.5f;
        freq *= 2.0f;
    }
    return sum / max_amp;
}

// ═══════════════════════════════════════════════════════════════════════════
// 2D Ridged Multifractal (Musgrave 1989)
// ═══════════════════════════════════════════════════════════════════════════

// Non-tileable
inline float pf_ridged_multifractal(float2 p, int oct)
{
    float sum = 0.0f;
    float freq = 1.0f;
    float amp = 0.6f;
    float prev = 1.0f;

    for (int i = 0; i < 8; i++) {
        if (i >= oct) break;
        float n = pf_value_noise(p * freq);
        n = 1.0f - fabs(n * 2.0f - 1.0f);   // ridge: invert absolute
        n = n * n;                             // sharpen
        sum += n * amp * prev;
        prev = clamp(n * 2.0f, 0.0f, 1.0f);  // signal-dependent
        freq *= 2.0f;
        amp *= 0.5f;
    }
    return sum;
}

// Tileable — with configurable sharpness via pow()
inline float pf_ridged_t(float2 p, int oct, float sharpness, float2 per)
{
    float sum = 0.0f;
    float freq = 1.0f;
    float amp = 0.6f;
    float prev = 1.0f;
    for (int i = 0; i < 8; i++) {
        if (i >= oct) break;
        float n = pf_value_noise_t(p * freq, per * freq);
        n = 1.0f - fabs(n * 2.0f - 1.0f);
        n = pow(n, sharpness);
        sum += n * amp * prev;
        prev = clamp(n * 2.0f, 0.0f, 1.0f);
        freq *= 2.0f;
        amp *= 0.5f;
    }
    return sum;
}

// ═══════════════════════════════════════════════════════════════════════════
// 2D Tileable Domain Warp (Quilez recursive warp)
//
// Tiling is preserved because warp FBM tiles -> displacement identical at
// both tile edges -> warped coordinate differs by exactly 'period' ->
// final FBM tiles at that period -> seamless output.
// ═══════════════════════════════════════════════════════════════════════════

inline float pf_warped_fbm_t(float2 p, int warp_layers, float warp_str,
                              int warp_ratio, int oct, float sd, float2 per)
{
    float2 q = p;
    float fr = (float)max(warp_ratio, 1);

    if (warp_layers >= 1) {
        float wx = pf_fbm_t(q + sd, oct, per);
        float wy = pf_fbm_t(q + sd + (float2)(5.2f, 1.3f), oct, per);
        q = p + (float2)(wx, wy) * warp_str;
    }

    if (warp_layers >= 2) {
        float2 p2 = q * fr;
        float2 per2 = per * fr;
        float wx2 = pf_fbm_t(p2 + sd + (float2)(1.7f, 9.2f), oct, per2);
        float wy2 = pf_fbm_t(p2 + sd + (float2)(8.3f, 2.8f), oct, per2);
        q = p + (float2)(wx2, wy2) * warp_str * 0.8f;
    }

    if (warp_layers >= 3) {
        float2 p3 = q * fr * fr;
        float2 per3 = per * fr * fr;
        float wx3 = pf_fbm_t(p3 + sd + (float2)(3.1f, 7.4f), oct, per3);
        float wy3 = pf_fbm_t(p3 + sd + (float2)(6.7f, 0.9f), oct, per3);
        q = p + (float2)(wx3, wy3) * warp_str * 0.6f;
    }

    return pf_fbm_t(q + sd, oct, per);
}

// ═══════════════════════════════════════════════════════════════════════════
// 2D Perlin Noise (integer-hash based, with derivative variants)
// ═══════════════════════════════════════════════════════════════════════════

// Value only
inline float pf_perlin(float2 p, int seed) {
    float2 ip = floor(p);
    float2 f  = p - ip;
    int ix = (int)ip.x, iy = (int)ip.y;
    float wx = pf_qerp(f.x), wy = pf_qerp(f.y);

    float2 g00 = pf_grad(pf_hash2d(ix,   iy,   seed));
    float2 g10 = pf_grad(pf_hash2d(ix+1, iy,   seed));
    float2 g01 = pf_grad(pf_hash2d(ix,   iy+1, seed));
    float2 g11 = pf_grad(pf_hash2d(ix+1, iy+1, seed));

    float a = dot(g00, f);
    float b = dot(g10, f - (float2)(1.0f, 0.0f));
    float c = dot(g01, f - (float2)(0.0f, 1.0f));
    float d = dot(g11, f - (float2)(1.0f, 1.0f));

    float n = a + (b - a)*wx + (c - a)*wy + (a - b - c + d)*wx*wy;
    return n * 1.5f;
}

// + Pseudo-derivatives (IQ heterogeneous technique)
inline float3 pf_perlin_pd(float2 p, int seed) {
    float2 ip = floor(p);
    float2 f  = p - ip;
    int ix = (int)ip.x, iy = (int)ip.y;
    float wx  = pf_qerp(f.x),   wy  = pf_qerp(f.y);
    float dwx = pf_qerp_d(f.x), dwy = pf_qerp_d(f.y);

    float2 g00 = pf_grad(pf_hash2d(ix,   iy,   seed));
    float2 g10 = pf_grad(pf_hash2d(ix+1, iy,   seed));
    float2 g01 = pf_grad(pf_hash2d(ix,   iy+1, seed));
    float2 g11 = pf_grad(pf_hash2d(ix+1, iy+1, seed));

    float a = dot(g00, f);
    float b = dot(g10, f - (float2)(1.0f, 0.0f));
    float c = dot(g01, f - (float2)(0.0f, 1.0f));
    float d = dot(g11, f - (float2)(1.0f, 1.0f));

    float ba   = b - a;
    float ca   = c - a;
    float abcd = a - b - c + d;

    float n  = a + ba*wx + ca*wy + abcd*wx*wy;
    float dx = dwx * (ba + abcd*wy);
    float dy = dwy * (ca + abcd*wx);
    return (float3)(n, dx, dy) * 1.5f;
}

// + Analytic derivatives (Swiss/Jordan technique)
inline float3 pf_perlin_d(float2 p, int seed) {
    float2 ip = floor(p);
    float2 f  = p - ip;
    int ix = (int)ip.x, iy = (int)ip.y;

    float wx   = pf_qerp(f.x),    wy   = pf_qerp(f.y);
    float dwx  = pf_qerp_d(f.x),  dwy  = pf_qerp_d(f.y);
    float dwpx = pf_qerp_td(f.x), dwpy = pf_qerp_td(f.y);

    float2 g00 = pf_grad(pf_hash2d(ix,   iy,   seed));
    float2 g10 = pf_grad(pf_hash2d(ix+1, iy,   seed));
    float2 g01 = pf_grad(pf_hash2d(ix,   iy+1, seed));
    float2 g11 = pf_grad(pf_hash2d(ix+1, iy+1, seed));

    float a = dot(g00, f);
    float b = dot(g10, f - (float2)(1.0f, 0.0f));
    float c = dot(g01, f - (float2)(0.0f, 1.0f));
    float d = dot(g11, f - (float2)(1.0f, 1.0f));

    float n = a + (b - a)*wx + (c - a)*wy + (a - b - c + d)*wx*wy;

    float dx = (g00.x + (g01.x - g00.x)*wy)
        + ((g10.y - g00.y)*f.y - g10.x
           + ((g00.y - g10.y - g01.y + g11.y)*f.y
              + g10.x + g01.y - g11.x - g11.y)*wy) * dwx
        + ((g10.x - g00.x)
           + (g00.x - g10.x - g01.x + g11.x)*wy) * dwpx;

    float dy = (g00.y + (g10.y - g00.y)*wx)
        + ((g01.x - g00.x)*f.x - g01.y
           + ((g00.x - g10.x - g01.x + g11.x)*f.x
              + g10.x + g01.y - g11.x - g11.y)*wx) * dwy
        + ((g01.y - g00.y)
           + (g00.y - g10.y - g01.y + g11.y)*wx) * dwpy;

    return (float3)(n, dx, dy) * 1.5f;
}

// ═══════════════════════════════════════════════════════════════════════════
// 3D Value Noise (integer-hash based, mode-selectable interpolation)
// ═══════════════════════════════════════════════════════════════════════════

inline float pf_vnoise(float3 p, int sd, int ntype) {
    int3  pi = (int3)((int)floor(p.x), (int)floor(p.y), (int)floor(p.z));
    float3 pf = p - convert_float3(pi);
    float tx = pf_interp(pf.x, ntype);
    float ty = pf_interp(pf.y, ntype);
    float tz = pf_interp(pf.z, ntype);

    float c000 = pf_lattice(pi,                    sd);
    float c100 = pf_lattice(pi + (int3)(1, 0, 0),  sd);
    float c010 = pf_lattice(pi + (int3)(0, 1, 0),  sd);
    float c110 = pf_lattice(pi + (int3)(1, 1, 0),  sd);
    float c001 = pf_lattice(pi + (int3)(0, 0, 1),  sd);
    float c101 = pf_lattice(pi + (int3)(1, 0, 1),  sd);
    float c011 = pf_lattice(pi + (int3)(0, 1, 1),  sd);
    float c111 = pf_lattice(pi + (int3)(1, 1, 1),  sd);

    float c00 = mix(c000, c100, tx);
    float c01 = mix(c001, c101, tx);
    float c10 = mix(c010, c110, tx);
    float c11 = mix(c011, c111, tx);
    return mix(mix(c00, c10, ty), mix(c01, c11, ty), tz);
}

inline float pf_snoise(float3 p, int sd, int ntype) {
    return pf_vnoise(p, sd, ntype) * 2.0f - 1.0f;
}

#endif
