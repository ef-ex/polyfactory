// polyChain - the arclength sampler, in VEX.  (spec 13.3.1 / 13.3.4)
//
// This is `place.Path` ported one-for-one, INCLUDING its two deliberate
// oddities, because parity is asserted at 1e-12 and both of them move numbers:
//   * D30 - an OPEN curve is EXTRAPOLATED past either end along the end
//     segment's own direction, never clamped.
//   * the forward/backward tie-break at a vertex: a section's START frame
//     wants the tangent LEAVING the vertex, its END frame the one ARRIVING.
//
// It reads ONLY per-primitive arrays written by `pc_arclength`, never
// `primpoints()` or a point at a random index - which is 13.5's OpenCL
// transliterability constraint, kept for free rather than retrofitted.

#ifndef __pc_path_h__
#define __pc_path_h__

#define PC_EPS      1e-9        // metres; a chord shorter than this is no segment
#define PC_POS_EPS  1e-6        // metres; two points closer than this are one point

// bisect.bisect_right / bisect_left over a sorted float array.
int pc_bisect_right(const float a[]; const float v) {
    int lo = 0, hi = len(a);
    while (lo < hi) {
        int mid = (lo + hi) / 2;
        if (v < a[mid]) hi = mid; else lo = mid + 1;
    }
    return lo;
}

int pc_bisect_left(const float a[]; const float v) {
    int lo = 0, hi = len(a);
    while (lo < hi) {
        int mid = (lo + hi) / 2;
        if (a[mid] < v) lo = mid + 1; else hi = mid;
    }
    return lo;
}

// `Path.sample(s, forward)` - position and unit tangent at `s` metres.
void pc_sample(const int inp; const int pr; const float s_in; const int forward;
               export vector pos; export vector tang) {
    float seg_lo[] = prim(inp, "pc_seg_lo", pr);
    float seg_hi[] = prim(inp, "pc_seg_hi", pr);
    vector seg_a[] = prim(inp, "pc_seg_a", pr);
    vector seg_d[] = prim(inp, "pc_seg_d", pr);
    int n = len(seg_hi);
    if (n == 0) {                       // a curve with no segment at all
        pos = prim(inp, "pc_first", pr);
        tang = set(0.0, 0.0, 0.0);
        return;
    }
    float total  = prim(inp, "pc_total", pr);
    int   closed = prim(inp, "pc_closed", pr);
    float last   = seg_hi[n - 1];
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
    else if (forward)      i = pc_bisect_right(seg_hi, s + PC_EPS);
    else                   i = pc_bisect_left(seg_hi, s - PC_EPS);
    i = min(max(i, 0), n - 1);

    float lo = seg_lo[i], hi = seg_hi[i];
    vector a = seg_a[i], d = seg_d[i];
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
