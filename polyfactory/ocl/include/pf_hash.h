/*
 * pf_hash.h — Polyfactory hash functions for Copernicus OpenCL kernels.
 *
 * Include:  #include "pf_hash.h"
 * Requires: pf_util.h (for pf_fract macro).
 */
#ifndef __PF_HASH_H__
#define __PF_HASH_H__

#include "pf_util.h"

// ═══════════════════════════════════════════════════════════════════════════
// Fract-based hashes (Dave Hoskins family)
// ═══════════════════════════════════════════════════════════════════════════

// 2D -> 1D  [0, 1]
inline float pf_hash21(float2 p)
{
    float3 p3 = pf_fract((float3)(p.x, p.y, p.x) * 0.1031f);
    p3 += dot(p3, (float3)(p3.y, p3.z, p3.x) + 33.33f);
    return pf_fract((p3.x + p3.y) * p3.z);
}

// 2D -> 2D  [0, 1]^2
inline float2 pf_hash22(float2 p)
{
    float3 p3 = pf_fract((float3)(p.x, p.y, p.x)
                          * (float3)(0.1031f, 0.1030f, 0.0973f));
    float d = dot(p3, (float3)(p3.y, p3.z, p3.x) + 33.33f);
    p3 += d;
    return pf_fract((float2)((p3.x + p3.y) * p3.z,
                              (p3.x + p3.z) * p3.y));
}

// 3D -> 4D  [-1, 1]^4  (Hoskins variant, Shadertoy 4djSRW)
inline float4 pf_hash43(float3 p)
{
    float4 p4 = pf_fract((float4)(p.x, p.y, p.z, p.x)
                          * (float4)(1031.0f, 0.1030f, 0.0973f, 0.1099f));
    float d = dot(p4, (float4)(p4.w, p4.z, p4.x, p4.y) + 19.19f);
    p4 += d;
    return -1.0f + 2.0f * pf_fract((float4)(
        (p4.x + p4.y) * p4.z,
        (p4.x + p4.z) * p4.y,
        (p4.y + p4.z) * p4.w,
        (p4.z + p4.w) * p4.x
    ));
}

// ═══════════════════════════════════════════════════════════════════════════
// Integer hashes (Murmur3 family)
// ═══════════════════════════════════════════════════════════════════════════

// Murmur3 32-bit finalizer
inline uint pf_ihash(uint n) {
    n ^= n >> 16;
    n *= 0x7feb352dU;
    n ^= n >> 15;
    n *= 0x846ca68bU;
    n ^= n >> 16;
    return n;
}

// 2D spatial hash with Teschner (2003) prime constants
inline uint pf_hash2d(int ix, int iy, int s) {
    uint h = (uint)ix * 73856093U + (uint)iy * 19349663U + (uint)s * 83492791U;
    return pf_ihash(h);
}

// Murmur3 variant
inline uint pf_hash1(uint n) {
    n = (n ^ 61u) ^ (n >> 16u);
    n += (n << 3u);
    n ^= (n >> 4u);
    n *= 0x27d4eb2du;
    n ^= (n >> 15u);
    return n;
}

// ═══════════════════════════════════════════════════════════════════════════
// 3D lattice hash
// ═══════════════════════════════════════════════════════════════════════════

// 3D cell -> [0, 1]  (primes: 1619, 31337, 6971)
inline float pf_lattice(int3 c, int sd) {
    uint h = pf_hash1((uint)(c.x * 1619 + c.y * 31337 + c.z * 6971 + sd * 1013));
    return (float)(h & 0xFFFFu) * (1.0f / 65535.0f);
}

#endif
