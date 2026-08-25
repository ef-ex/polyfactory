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
//           normal, which needs D55's TILT;
//   NOT     D104's extra stations (`fracs`) - folded in only when `normal_at`
//           is given, so they are the same absence.
//
// ⚠️ 13.9 N6 CHANGED WHICH PATH THESE TWO TERMS ARE MEASURED ON, AND NOT WHAT
// THEY ARE.  Every sample below is `pc_conform.h`'s CONFORMED sampler now, so
// with a surface wired the budget is spent against the drape - which is
// `place.span_deviation` handed a `ConformPath`, i.e. the reference exactly.
// With no surface `pc_csample` IS `pc_sample`, the same call, so no phase-1
// number can move.  The two terms above are still absent, and the refusal that
// covers them is now precisely D55's TILT rather than the whole of 4.5:
// `normal_at` is passed only under `conform_tilt`, so level 1 refusing tilt is
// what keeps the two ported terms EXACT here.  A budget that quietly drops two
// of its four terms is exactly the silent fallback that makes a rebuild
// cosmetic, so it is a declared limit with a check on it, not an approximation.
//
// ⚠️ THE `_len(ref) < EPS` AND `_len(t) < EPS` GUARDS IN THE REFERENCE ARE
// DEAD CODE AND ARE NOT PORTED AS BRANCHES.  `place._unit` returns the
// FALLBACK (1, 0, 0) for a degenerate vector, so both lengths are 1.0 and
// neither `return worst` nor `continue` can ever run.  `pc_unit` has the same
// fallback, so the VEX reaches the same answer by the same route - but a
// reader comparing the two files would otherwise think a branch went missing.

#ifndef __pc_gate_h__
#define __pc_gate_h__

#include "pc_conform.h"

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
//
// ⚠️ THE KINKS ARE THE SPLINE'S, THE POSITIONS ARE THE DRAPE'S, and that is the
// reference's own shape rather than an approximation of it:
// `ConformPath.interior_vertices` delegates STRAIGHT to the base path, so a
// conformed run's interior vertices are the spline's kinks while every
// `path.sample` around them is dropped.  A ridge under a dead-straight spline
// therefore contributes NOTHING here - `deviates` is the term that catches it,
// and `pc_deform_gate` asks it separately for exactly that reason.
float pc_span_deviation(const int inp; const int pr; const float sa;
                        const float sb; const float radius;
                        const string zmode; const int surf; const vector axis) {
    float span = sb - sa;
    if (abs(span) <= PC_EPS) return 0.0;
    float verts[];
    int nv = pc_interior_kinks(inp, pr, sa, sb, verts);
    if (!nv && radius <= PC_EPS) return 0.0;    // the chord IS the arc (D66/D69)

    vector a, ta, b, tb;
    pc_cspan_ends(inp, pr, sa, sb, surf, axis, a, ta, b, tb);
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
        vector p = pc_cpos(inp, pr, verts[k], 1, surf, axis);
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
            pc_csample(inp, pr, s, 1, surf, axis, p, t);
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

// `place._bend_deviation` (D25) - how far the DEFORMED piece cuts the corner
// between two of its own stations, in metres.  13.9 N5.
//
// It is not `span_deviation` in another costume: that one asks whether the
// piece should deform AT ALL, measured against the chord; this one measures
// what the deformed piece, built on the module's OWN stations, still misses -
// the sag of the straight run between two adjacent stations against the curve
// under it.  Over `bend_tol` it is `pc_warn_bend_resolution`, which is the one
// warning a deformed piece can raise and a packed one cannot, so without it
// the native branch ships an element the reference stamps and it does not.
//
// The stations arrive as RAW local x (13.9 N6 moved the table onto the PLAN
// POINT, so that the gate's fourth input is free for IN_SURFACE); the `- ax`
// happens here, in 64 bits, exactly as `_stations` does it.
//
// ⚠️ THE REFERENCE'S `ps[]` CACHE IS NOT PORTED AND DOES NOT NEED TO BE.  It
// saves a `path.sample` call per gap and returns the identical position for
// the identical argument - the sampler is a pure function of (prim, s) - so
// dropping it changes the cost and not one bit of the answer.  What IS ported
// is the `s_b - s_a <= EPS` skip, which changes WHICH gaps are measured.
float pc_bend_deviation(const int spline; const int pr; const float st[];
                        const float ax; const float s0f; const float scale;
                        const int surf; const vector axis) {
    int n = len(st);
    if (n < 2) return 0.0;
    float worst = 0.0;
    for (int i = 0; i + 1 < n; i++) {
        float sa = s0f + (st[i] - ax) * scale;
        float sb = s0f + (st[i + 1] - ax) * scale;
        if (sb - sa <= PC_EPS) continue;
        vector pa = pc_cpos(spline, pr, sa, 1, surf, axis);
        vector pb = pc_cpos(spline, pr, sb, 1, surf, axis);
        vector pm = pc_cpos(spline, pr, 0.5 * (sa + sb), 1, surf, axis);
        worst = max(worst, length(pm - 0.5 * (pa + pb)));
    }
    return worst;
}

// D31's FRAME TRANSPORT, ANSWERED AS A REFUSAL RATHER THAN PORTED.  13.9 N5.
//
// `place._transport` carries `across` along the piece station by station and
// FLIPS it whenever it would reverse against its predecessor - a prefix scan,
// which is the one shape a per-point wrangle cannot evaluate in O(1).  What
// makes the flip reachable at all is the piece's own plan-view direction
// REVERSING inside its span (an overhanging crest, a cliff lip, a hairpin
// shorter than one module), because `across` is the horizontal normal in both
// z-modes: `_frame`'s `adaptive` branch takes `cross(d, UP)` = (-dz, 0, dx)
// and its yaw-only branch takes (-d.z, 0, d.x) of the flattened tangent.
//
// So this asks the question the flip needs: over the piece's own span, do any
// two of the path's distinct directions OPPOSE, and is any of them without a
// horizontal direction at all (which is `_frame`'s other special case, the
// (0,0,1) fallback).  Either way the piece is declared unanswerable, the whole
// build takes the reference, and nothing wrong ships - 13.9 N10's rule, and
// the one both of 20.2's criticals broke by answering False instead.
//
// ⚠️ ON A BARE SPLINE THE SAMPLE SET IS THE PATH'S DIRECTIONS, NOT THE MODULE'S
// STATIONS, AND THAT IS WHY IT IS SOUND.  A station's tangent is the direction
// of whatever segment its arclength lands in, so the set of station tangents is
// a SUBSET of the segment directions over the span; the directions change only
// at a KINK, so sampling the span's start, every interior kink and its end
// visits every one of them.  Refusing on the superset can only refuse more,
// never less.
//
// ⚠️ AND THAT ARGUMENT DOES NOT SURVIVE A CONFORM, WHICH IS WHY THE STATIONS
// ARE ADDED BACK (13.9 N6).  A conformed tangent is a finite difference of
// DROPPED positions, so it turns with the terrain and not with the spline's
// segments: a dead-straight span over an overhanging crest has no kink at all
// and still reverses.  With a surface the set becomes the kinks PLUS the
// piece's own stations, which is exactly the frame set `_deform_positions`
// builds and `_transport` walks - so the test is not merely conservative there,
// it is the same set.  `st`/`ax`/`scale` are the piece's station table; an
// EMPTY table with a surface wired is a refusal, because a set that cannot be
// enumerated cannot be shown not to flip.
#define PC_FLAT_TANGENT 1e-6
int pc_frames_transportable(const int inp; const int pr; const float s0;
                            const float s1; const int surf; const vector axis;
                            const float st[]; const float ax;
                            const float scale) {
    if (s1 - s0 <= PC_EPS) return 1;
    int conformed = pc_surf_active(surf);
    if (conformed && len(st) < 2) return 0;
    float verts[];
    int nv = pc_interior_kinks(inp, pr, s0, s1, verts);
    float ss[];
    for (int k = 0; k < nv + 2; k++)
        push(ss, (k == 0) ? s0 : ((k <= nv) ? verts[k - 1] : s1));
    if (conformed)
        foreach (float x; st) push(ss, s0 + (x - ax) * scale);
    vector hs[];
    foreach (float s; ss) {
        vector p, t;
        pc_csample(inp, pr, s, 1, surf, axis, p, t);
        vector u = pc_unit(t);
        vector h = set(u.x, 0.0, u.z);
        float hl = length(h);
        if (hl < PC_FLAT_TANGENT) return 0;
        push(hs, h / hl);
    }
    int n = len(hs);
    for (int i = 0; i < n; i++)
        for (int j = i + 1; j < n; j++)
            if (dot(hs[i], hs[j]) < 0.0) return 0;
    return 1;
}

#endif
