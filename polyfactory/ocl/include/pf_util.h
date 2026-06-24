/*
 * pf_util.h — Polyfactory utility functions for Copernicus OpenCL kernels.
 *
 * Include:  #include "pf_util.h"
 * Requires: Nothing (standalone).
 */
#ifndef __PF_UTIL_H__
#define __PF_UTIL_H__

// ─── Fract ─────────────────────────────────────────────────────────────────
#ifndef pf_fract
#define pf_fract(x) ((x) - floor(x))
#endif

// ─── Smoothstep (Hermite) ──────────────────────────────────────────────────
inline float pf_smoothstep(float edge0, float edge1, float x)
{
    float t = clamp((x - edge0) / (edge1 - edge0 + 1e-6f), 0.0f, 1.0f);
    return t * t * (3.0f - 2.0f * t);
}

// ─── Quintic interpolation (Perlin 2002) ───────────────────────────────────
inline float pf_qerp(float t)    { return t*t*t * (t*(t*6.0f - 15.0f) + 10.0f); }
inline float pf_qerp_d(float t)  { return 30.0f * t*t * (t*(t - 2.0f) + 1.0f); }
inline float pf_qerp_td(float t) { return t*t*t * (t*(t*36.0f - 75.0f) + 40.0f); }

// ─── Gradient direction (8 evenly spaced unit vectors) ─────────────────────
inline float2 pf_grad(uint h) {
    float angle = (float)(h & 7U) * 0.78539816f;   // h * PI/4
    return (float2)(cos(angle), sin(angle));
}

// ─── Interpolation dispatch (Block / Linear / Hermite / Spline) ────────────
inline float pf_interp(float t, int mode) {
    if (mode == 0) return (t < 0.5f) ? 0.0f : 1.0f;
    if (mode == 1) return t;
    t = t * t * (3.0f - 2.0f * t);                  // Hermite (Soft Linear)
    if (mode == 3) t = t * t * (3.0f - 2.0f * t);   // Quintic (Spline)
    return t;
}

#endif
