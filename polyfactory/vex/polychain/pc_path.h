// polyChain - the arclength sampler, in VEX.  (spec 13.3.1 / 13.3.4)
//
// This is `place.Path` ported one-for-one, INCLUDING its two deliberate
// oddities, because parity is asserted at 1e-12 and both of them move numbers:
//   * D30 - an OPEN curve is EXTRAPOLATED past either end along the end
//     segment's own direction, never clamped.
//   * the forward/backward tie-break at a vertex: a section's START frame
//     wants the tangent LEAVING the vertex, its END frame the one ARRIVING.
//
// It reads the sampler table `pc_arclength` wrote and the SPLINE'S OWN `P`
// through it - never `primpoints()`, never an unindexed scan.  Every read is
// a constant-cost lookup into a flat table (`vertex(prim, j)`,
// `vertexpoint`, `point(P)`), which is what 13.5's OpenCL transliterability
// constraint is actually asking for; a buffer plus an index buffer is exactly
// the shape OpenCL wants.
//
// ⚠️ AND IT READS IT ONE SCALAR AT A TIME.  The table used to be four
// per-primitive ARRAY attributes, and a `prim()` read of an array COPIES THE
// WHOLE ARRAY - so `pc_sample` copied 160 000 values per call on the 20 km
// fixture, twice per piece.  Measured on the shipped asset at 18 870 pieces:
// `pc_frames_native` 4 833 ms, `copy_packed` 5.1 ms.  The table is per-VERTEX
// storage now (segment j on vertex j of the same prim), so the bisect is ~15
// indexed reads and the sample four more.  The COMPARISONS are unchanged -
// D30's extrapolation past either end and the forward/backward tie-break at a
// vertex both round exactly as they did, which is what keeps the parity at
// 0.0 rather than at a tolerance.

#ifndef __pc_path_h__
#define __pc_path_h__

#define PC_EPS      1e-9        // metres; a chord shorter than this is no segment
#define PC_POS_EPS  1e-6        // metres; two points closer than this are one point

// 13.9 N5 - THE OUTPUT'S ORDER, AS A NUMBER.  `place.build` materialises pass
// B in job order, interleaving one packed prim per rigid piece with a whole
// polygon soup per deformed one; the native branch builds those as two
// `copytopoints` streams and sorts them back together on
// `_pkey0 * PC_PIECE_SPAN + <index within the piece>`.  The span is how many
// prims (or points) one module may contribute before two pieces' keys would
// collide - `pc_kit_rank` measures the real maximum and `pc_deform_gate`
// REFUSES the build rather than shipping a permuted fence.  One declaration,
// because a key whose two writers disagree is a silent reordering.
#define PC_PIECE_SPAN 65536

// One element of the sampler table, by segment index.  A typed local before
// every `vertex()` - the return is untyped and everything downstream of it
// would be ambiguous (recorded trap).
float pc_seg_hi_at(const int inp; const int pr; const int j) {
    float v = vertex(inp, "_seg_hi", pr, j);
    return v;
}

// bisect.bisect_right / bisect_left over the segment table, by INDEX.
int pc_bisect_right(const int inp; const int pr; const int n; const float v) {
    int lo = 0, hi = n;
    while (lo < hi) {
        int mid = (lo + hi) / 2;
        if (v < pc_seg_hi_at(inp, pr, mid)) hi = mid; else lo = mid + 1;
    }
    return lo;
}

int pc_bisect_left(const int inp; const int pr; const int n; const float v) {
    int lo = 0, hi = n;
    while (lo < hi) {
        int mid = (lo + hi) / 2;
        if (pc_seg_hi_at(inp, pr, mid) < v) lo = mid + 1; else hi = mid;
    }
    return lo;
}

// `Path.sample(s, forward)` - position and unit tangent at `s` metres.
void pc_sample(const int inp; const int pr; const float s_in; const int forward;
               export vector pos; export vector tang) {
    int n = prim(inp, "_nseg", pr);
    if (n <= 0) {                       // a curve with no segment at all
        vector first = prim(inp, "_first", pr);
        pos = first;
        tang = set(0.0, 0.0, 0.0);
        return;
    }
    float total  = prim(inp, "pc_total", pr);
    int   closed = prim(inp, "pc_closed", pr);
    float last   = pc_seg_hi_at(inp, pr, n - 1);
    float s      = s_in;

    if (closed && total > PC_EPS) {
        float asked = s;
        s = s - total * trunc(s / total);           // math.fmod
        if (s < 0.0) s += total;
        if (!forward && s <= PC_EPS && asked > PC_EPS) s = total;
        s = min(max(s, 0.0), last);
    }

    int i;
    if (s < 0.0)           i = 0;
    else if (s > last)     i = n - 1;
    else if (forward)      i = pc_bisect_right(inp, pr, n, s + PC_EPS);
    else                   i = pc_bisect_left(inp, pr, n, s - PC_EPS);
    i = min(max(i, 0), n - 1);

    // `seg_lo[i]` IS `seg_hi[i - 1]` - a dropped segment has zero length, so
    // the kept segments are contiguous in arclength and the table stores one
    // column instead of two.
    float hi = pc_seg_hi_at(inp, pr, i);
    float lo = (i > 0) ? pc_seg_hi_at(inp, pr, i - 1) : 0.0;
    // and the segment's two VECTORS are read off `P`, not stored: `_seg_i` is
    // the vertex the segment starts at, and the wrap is the same
    // `(i + 1) % np` `pc_arclength` used, so a closed curve's last segment
    // returns to vertex 0.  Same float32 positions, same subtraction, same
    // bits.
    int i0 = vertex(inp, "_seg_i", pr, i);
    int nv = primvertexcount(inp, pr);
    int pa = vertexpoint(inp, vertexindex(inp, pr, i0));
    int pb = vertexpoint(inp, vertexindex(inp, pr, (i0 + 1) % max(nv, 1)));
    vector a = point(inp, "P", pa);
    vector bpos = point(inp, "P", pb);
    vector d = bpos - a;
    float t = (hi - lo < PC_EPS) ? 0.0 : (s - lo) / (hi - lo);
    if (s >= 0.0 && s <= last) t = min(max(t, 0.0), 1.0);
    pos  = a + d * t;
    tang = normalize(d);
}

// `place.span_ends` - the two reads every span-shaped question starts with.
void pc_span_ends(const int inp; const int pr; const float sa; const float sb;
                  export vector pa; export vector ta;
                  export vector pb; export vector tb) {
    pc_sample(inp, pr, sa, 1, pa, ta);
    pc_sample(inp, pr, sb, 0, pb, tb);
}

// `place._unit` - and its FALLBACK, which is not decoration: a yaw-only frame
// on a vertical tangent flattens to (0,0,0), and the reference answers +X
// there.  VEX's own `normalize()` answers 0, which silently collapses the
// piece instead of laying it along X.
vector pc_unit(const vector v) {
    float n = length(v);
    return (n < PC_EPS) ? set(1.0, 0.0, 0.0) : v / n;
}

// `place._frame` - (dir, across, up) for one sample.
//   `up_ref` is 4.5's CAMBER (D55): hand it the surface normal and the frame
//   rolls onto the surface.  Only the `adaptive` branch reads it - a yaw-only
//   mode is PLUMB BY DEFINITION.
void pc_frame(const vector tangent; const string zmode; const vector up_ref;
              export vector dir; export vector across; export vector up) {
    if (zmode == "adaptive") {
        dir = pc_unit(tangent);
        vector ac = cross(dir, up_ref);
        across = (length(ac) < PC_EPS) ? set(0.0, 0.0, 1.0) : pc_unit(ac);
        up = cross(across, dir);
        return;
    }
    dir = pc_unit(set(tangent.x, 0.0, tangent.z));
    across = set(-dir.z, 0.0, dir.x);
    up = set(0.0, 1.0, 0.0);
}

#endif
