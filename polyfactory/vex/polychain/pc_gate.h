// polyChain - D87's CURVATURE BUDGET, in VEX.  (spec 4.4 / 13.9 N5)
//
// `place.span_deviation` ported, together with the two `place.Path` members it
// needs and nothing else: `_kinks` and `interior_vertices`.  It answers ONE
// question - how far the DEFORMED piece would sit from the PACKED one, in
// metres, at its worst point - and `pc_deform_gate.vfl` turns that number into
// the packed/deformed segregation PC-G3's headline row rides on.
//
// ⚠️ WHAT IS PORTED AND WHAT IS DECLARED, because the difference is the whole
// safety of the node.  `span_deviation` has FOUR terms and this file has two:
//
//   ported  the SPINE term (D75) - the polyline's own departure from the chord
//           it is measured against, extremal at a kink because both are linear
//           in between, which is why the interior vertices are the exact
//           answer for the span and not a sample of it;
//   ported  the OFF-SPINE term (D87) - a point `radius` metres off the spine
//           swings by the chord of the frame's own rotation, 2 r sin(theta/2),
//           sampled at the span's start, at every kink and at its END;
//   NOT     D100's CAMBER rotation (`normal_at`) - 4.5's per-station surface
//           normal, which needs the conform this graph has not ported (N6);
//   NOT     D104's extra stations (`fracs`) - folded in only when `normal_at`
//           is given, so they are the same absence.
//
// The gate therefore DECLARES ITSELF UNANSWERABLE whenever the build has a
// surface, and `pc_proto` already refuses those pieces for the same reason.
// A budget that quietly drops two of its four terms is exactly the silent
// fallback that makes a rebuild cosmetic, so it is a declared limit with a
// check on it, not an approximation.
//
// ⚠️ THE `_len(ref) < EPS` AND `_len(t) < EPS` GUARDS IN THE REFERENCE ARE
// DEAD CODE AND ARE NOT PORTED AS BRANCHES.  `place._unit` returns the
// FALLBACK (1, 0, 0) for a degenerate vector, so both lengths are 1.0 and
// neither `return worst` nor `continue` can ever run.  `pc_unit` has the same
// fallback, so the VEX reaches the same answer by the same route - but a
// reader comparing the two files would otherwise think a branch went missing.

#ifndef __pc_gate_h__
#define __pc_gate_h__

#include "pc_path.h"

#define PC_KINK_TOL   1e-9      // `Path._kinks` - exact collinearity, D69
#define PC_VERT_TOL   1e-7      // `interior_vertices` - strictly inside

// The segment's own vector, read exactly the way `pc_sample` reads it: off
// `P`, with the same `(i + 1) % np` wrap, so a closed curve's last segment
// returns to vertex 0 and the subtraction is bit-for-bit the same one.
vector pc_seg_dir(const int inp; const int pr; const int j) {
    int i0 = vertex(inp, "_seg_i", pr, j);
    int nv = primvertexcount(inp, pr);
    int pa = vertexpoint(inp, vertexindex(inp, pr, i0));
    int pb = vertexpoint(inp, vertexindex(inp, pr, (i0 + 1) % max(nv, 1)));
    vector a = point(inp, "P", pa);
    vector b = point(inp, "P", pb);
    return b - a;
}

// `Path._kinks` - does the direction ACTUALLY change at the end of segment j?
//
// D69, and it is the difference between a packed run and a deformed one: a
// dead-straight 2 000 m line authored at 1 m spacing has 2 000 interior
// VERTICES and no kinks at all, and reading every vertex as a bend built
// 1 000 deformed pieces where the same line as two points builds 1 000 packed
// ones.  The tolerance is exact collinearity and not a curvature budget - a
// 5 000 m-radius arc resampled at 1 m still turns 2e-4 rad per vertex and
// still unpacks, which is what keeps every baseline still.
//
// ⚠️ THE SEAM OF A CLOSED CURVE IS A VERTEX LIKE ANY OTHER (`segs[-1]` arrives
// at it, `segs[0]` leaves it) and an OPEN curve's last segment end is NOT a
// kink at all - the reference loops `range(n if (closed and n > 1) else n - 1)`
// and both halves of that matter.
int pc_is_kink(const int inp; const int pr; const int n; const int closed;
               const int j) {
    int wraps = (closed && n > 1);
    if (!wraps && j >= n - 1) return 0;
    if (n < 2) return 0;
    vector a = pc_unit(pc_seg_dir(inp, pr, j));
    vector b = pc_unit(pc_seg_dir(inp, pr, (j + 1) % n));
    return (length(a - b) > PC_KINK_TOL);
}

// `Path.interior_vertices` - the kink arclengths strictly inside (s0, s1).
//
// The reference bisects a COMPACTED list of kinks; this bisects the segment
// table and applies the kink test as it walks, which is the same set and the
// same order.  It is O(segments in the span) and a span is one module long,
// so the walk is two or three segments - D75's own reason for bisecting (a
// linear scan of 20 001 vertices per piece cost 9.4 s at 10 000 pieces) is
// honoured by the bisect that opens it, not by the compaction.
int pc_interior_kinks(const int inp; const int pr; const float s0;
                      const float s1; export float out[]) {
    int n = prim(inp, "_nseg", pr);
    int closed = prim(inp, "pc_closed", pr);
    float total = prim(inp, "pc_total", pr);
    resize(out, 0);
    float bases[] = array(0.0);
    if (closed && total > PC_EPS) bases = array(0.0, total, -total);
    foreach (float base; bases) {
        float lo = s0 + PC_VERT_TOL - base;
        float hi = s1 - PC_VERT_TOL - base;
        int j = pc_bisect_right(inp, pr, n, lo);
        for (; j < n; j++) {
            float v = pc_seg_hi_at(inp, pr, j);
            if (v >= hi) break;
            if (!pc_is_kink(inp, pr, n, closed, j)) continue;
            float sv = v + base;
            // D66: an OPEN curve's two END vertices are not kinks. D30
            // extrapolates past either end along the end segment's own
            // direction, so nothing bends there - and a piece that legally
            // overhangs the end contains that vertex strictly inside its span.
            if (!closed && (sv <= PC_VERT_TOL || sv >= total - PC_VERT_TOL))
                continue;
            push(out, sv);
        }
    }
    out = sort(out);
    return len(out);
}

// `place.span_deviation` with `normal_at = None` - see the header note.
float pc_span_deviation(const int inp; const int pr; const float sa;
                        const float sb; const float radius;
                        const string zmode) {
    float span = sb - sa;
    if (abs(span) <= PC_EPS) return 0.0;
    float verts[];
    int nv = pc_interior_kinks(inp, pr, sa, sb, verts);
    if (!nv && radius <= PC_EPS) return 0.0;    // the chord IS the arc (D66/D69)

    vector a, ta, b, tb;
    pc_span_ends(inp, pr, sa, sb, a, ta, b, tb);
    vector ab = b - a;

    // THE SPINE TERM, at every kink. The two ends sit ON the chord by
    // construction and are in the list because the off-spine term below pairs
    // each frame with the span it holds over.
    float spine[];
    resize(spine, nv + 2);
    spine[0] = 0.0;
    spine[nv + 1] = 0.0;
    for (int k = 0; k < nv; k++) {
        float f = (verts[k] - sa) / span;
        vector p, t;
        pc_sample(inp, pr, verts[k], 1, p, t);
        spine[k + 1] = length(p - a - ab * f);
    }
    float worst = 0.0;
    for (int k = 0; k < nv + 2; k++) worst = max(worst, spine[k]);
    if (radius <= PC_EPS) return worst;

    // THE OFF-SPINE TERM (D87). `_deform_positions` builds its frame from the
    // FORWARD tangent at each station and `_packed_transform` builds one from
    // the chord, so a point `radius` metres off the spine is displaced by the
    // chord of that rotation. The END sample is not decoration: at a piece
    // boundary the forward tangent is the NEXT segment's, which is where the
    // worst reading on the R = 55 m elevation arc came from - 0.0327 m against
    // a 0.0091 m sagitta, three times the budget, all of it in this term.
    int flat = (zmode != "adaptive");
    vector ref = pc_unit(flat ? set(ab.x, 0.0, ab.z) : ab);
    for (int k = 0; k < nv + 2; k++) {
        float s = (k == 0) ? sa : ((k <= nv) ? verts[k - 1] : sb);
        vector t;
        if (k == 0) {
            t = ta;                     // the pair above already carries it
        } else {
            vector p;
            pc_sample(inp, pr, s, 1, p, t);
        }
        t = pc_unit(flat ? set(t.x, 0.0, t.z) : t);
        float ang = acos(clamp(dot(ref, t), -1.0, 1.0));
        // this frame holds from its own sample to the next one, so the spine
        // term it rides is the larger of that interval's two ends
        float near = (k + 1 < nv + 2) ? max(spine[k], spine[k + 1]) : spine[k];
        worst = max(worst, near + 2.0 * radius * sin(0.5 * ang));
    }
    return worst;
}

#endif
