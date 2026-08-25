// polyChain 4.5 SURFACE CONFORM, in VEX.  (spec 4.5 / 13.9 N6)
//
// `conform.Surface.drop` and `conform.ConformPath` ported.  The whole stage is
// a SAMPLER (D54): nothing here knows what a module is, and every consumer
// downstream already asks the same two questions - where is metre `s`, and
// which way is the curve pointing there - so the three z-modes compose with
// the drape without a single new branch, exactly as they do in Python.
//
// ⚠️ THE CONTEXT IS TWO SCALARS AND IT IS PASSED, NOT GLOBAL.  A wrangle has
// no statics, so the surface INPUT NUMBER and the axis travel through every
// signature.  `surf < 0`, an UNWIRED input, or a surface with no primitive all
// mean "no surface", and then every function here is `pc_path.h`'s own answer -
// bit-for-bit, not to a tolerance, because it is literally the same call.  That
// is what keeps every phase-1 baseline still while this file is in the graph.
//
// ⚠️ WHAT IS PORTED AND WHAT IS REFUSED, because the difference is the safety
// of the whole stage:
//
//   ported   the DROP (D52/D70) - down-axis, then back no further than the hit
//            already found, nearest wins, a tie goes DOWN-axis;
//   ported   `ConformPath.sample`'s ONE-SIDED finite difference for the tangent
//            (`delta = 1e-3`), one-sided so a corner piece points down one leg
//            rather than averaging two;
//   ported   `missed` and `deviates`, on the piece's OWN stations (D71);
//   NOT      D55's CAMBER (`ConformPath.normal`).  A tilt request needs the
//            surface normal per station, and `span_deviation`'s two unported
//            terms (D100's camber rotation, D104's extra stations) are folded
//            in ONLY when `normal_at` is given - so refusing TILT is what keeps
//            the two ported terms EXACT rather than approximate.  Level 1
//            refuses `conform_tilt` and any kit module whose `pc_tilt` asks for
//            it; there is no normal in this file at all, on purpose, so no
//            later edit can quietly start using one.
//   NOT      a NON-AXIS-ALIGNED `conform_axis`.  D111 is the reason and it is
//            the reference's own condition: `Surface.batchable` gates the
//            batched `ray` off a tilted axis because the reconstruction below
//            cannot remove the divergence there.  Level 1 refuses it.
//
// ⚠️ AND THE READING IS THE CONDITION (D238/D247).  `intersect()` hands back a
// hit POSITION quantised at the magnitude of a WORLD COORDINATE; the drop is
// quantised at the magnitude of a DROP.  So the drop is read off the AXIS
// COMPONENT and the position rebuilt from the query, exactly as `drop_many`
// already does.  Measured against `Surface.drop` reading the DIFFERENCE rather
// than the position - 0.0 m on x and z and 7.1e-15 m on the axis component, at
// 0 m, 100 m, 2 km and 20 km.
//
// ⚠️ WHAT THIS CANNOT SEE: `hou.Geometry.intersect` is called with an explicit
// `tolerance = 1e-6` and VEX's `intersect()` takes no tolerance at all, so the
// two are matched on principle and not by a case that distinguishes them -
// which is the same blind spot `drop_many`'s `rtolerance` already records
// ("a 1 mm hole in a 1 mm grid and a query 1 mm past a sheet's edge both give
// 0 hit-flag mismatches at either setting").

#ifndef __pc_conform_h__
#define __pc_conform_h__

#include "pc_path.h"

// `ConformPath.delta` - the finite-difference step, in metres.
#define PC_CONFORM_DELTA  1e-3
// `_probe_s`' own interior guard, and `_probe_s(n)`'s default probe count.
#define PC_PROBE_INTERIOR 1e-9
#define PC_PROBE_N        5

// Is there a surface at all?  `Surface.__init__` asks `primitivecount`, not
// `geo is not None`: every stage wrangle is wired to the IN_SURFACE null, which
// exists whether or not the HDA's own input 4 is connected.
int pc_surf_active(const int surf) {
    return (surf >= 0 && nprimitives(surf) > 0);
}

// `Surface.drop`'s PER-POINT reach (D70), and it is derived rather than a magic
// number: every surface point lies within `radius` of the bbox centre, so
// `|q - centre| + radius` is exactly the distance that cannot miss one.  A
// reach that is a property of the SURFACE alone flipped the drape on standoff
// distance - a 5 x 5 m prop under a spline 30 m up reported a MISS and the same
// prop 10 m up hit.
//
// `getbbox` is a cached read: measured at 0.1 ms over 490 000 calls, i.e. free.
float pc_surf_far(const int surf; const vector q) {
    vector bmin, bmax;
    getbbox(surf, bmin, bmax);
    vector centre = 0.5 * (bmin + bmax);
    float radius = max(0.5 * length(bmax - bmin), 1e-6);
    return length(q - centre) + radius;
}

// `Surface.drop` - (position, hit).  A MISS KEEPS THE UNPROJECTED POSITION
// (D53): the fence carries on at spline elevation and `pc_warn_conform_miss`
// says where it stopped being draped.
//
// THE CAST LOOKS BOTH WAYS AND THE NEAREST HIT WINS (D70), because the surface
// may sit above the spline as well as below it - a fence in a valley, a road
// under a bridge deck.  A TIE GOES DOWN-AXIS, because the stage is a DROP.
void pc_drop(const int surf; const vector q; const vector axis;
             export vector pos; export int hit) {
    pos = q;
    hit = 0;
    if (!pc_surf_active(surf)) return;
    vector up = -axis;
    float far = pc_surf_far(surf, q);
    vector p0, uvw0, p1, uvw1;
    // `_cast`'s own `if far <= 0.0: return None`.
    int h0 = (far > 0.0) ? intersect(surf, q, axis * far, p0, uvw0) : -1;
    float d0 = (h0 >= 0) ? length(p0 - q) : -1.0;
    // ...then look BACK, but only as far as the hit already found: a closer one
    // up-axis is the nearer surface, anything further is not.  ⚠️ AND `far <= 0`
    // IS REACHABLE HERE - a ZERO-DISTANCE hit down-axis bounds the back cast at
    // 0.0, where the reference returns None rather than casting a null ray.
    float bfar = (h0 >= 0) ? d0 : far;
    int h1 = (bfar > 0.0) ? intersect(surf, q, up * bfar, p1, uvw1) : -1;
    float d1 = (h1 >= 0) ? length(p1 - q) : -1.0;
    vector best = q;
    if (h0 >= 0) { best = p0; hit = 1; }
    if (h1 >= 0 && (h0 < 0 || d1 < d0 - PC_EPS)) { best = p1; hit = 1; }
    // D111's reconstruction - see the header note.
    if (hit) {
        float t = dot(best - q, axis);
        pos = q + axis * t;
    }
}

// `ConformPath._at` - the spline sample, dropped.  `hit` is `missed`'s answer.
void pc_cat(const int inp; const int pr; const float s; const int forward;
            const int surf; const vector axis;
            export vector pos; export vector tang; export int hit) {
    pc_sample(inp, pr, s, forward, pos, tang);
    if (!pc_surf_active(surf)) { hit = 1; return; }
    vector dropped;
    pc_drop(surf, pos, axis, dropped, hit);
    pos = dropped;
}

// `ConformPath.sample` - position and tangent, the tangent a ONE-SIDED finite
// difference of DROPPED positions.
//
// ⚠️ ONE-SIDED, AND THAT IS THE CONTRACT, NOT AN ECONOMY.  `place.Path.sample`
// answers a vertex differently forward and backward (a section's START frame
// wants the tangent LEAVING the vertex, its END frame the one ARRIVING); a
// central difference here would average the two legs and point a corner piece
// down neither of them.  So the partner is asked in the direction the caller
// asked for, with the SAME `forward` flag - which is what the reference does.
//
// Without the difference at all, an adaptive rail over a 25 % slope stays dead
// level while its two ends sit on the hill.
void pc_csample(const int inp; const int pr; const float s; const int forward;
                const int surf; const vector axis;
                export vector pos; export vector tang) {
    int hit;
    pc_cat(inp, pr, s, forward, surf, axis, pos, tang, hit);
    if (!pc_surf_active(surf)) return;
    float s2 = forward ? (s + PC_CONFORM_DELTA) : (s - PC_CONFORM_DELTA);
    vector other, otan;
    int ohit;
    pc_cat(inp, pr, s2, forward, surf, axis, other, otan, ohit);
    vector step = forward ? (other - pos) : (pos - other);
    // `_unit(step, tan)`'s fallback IS the spline tangent: a VERTICAL drop
    // leaves no step at all and the reference keeps the spline's answer there.
    if (length(step) >= PC_EPS) tang = normalize(step);
}

// `ConformPath` position only - `span_deviation`'s spine term, `_bend_deviation`
// and `deviates` all read `path.sample(s)[0]` and never the tangent, so the
// finite-difference partner is work whose answer is thrown away.  Dropping it
// changes the COST and not one bit of the answer.
vector pc_cpos(const int inp; const int pr; const float s; const int forward;
               const int surf; const vector axis) {
    vector pos, tang;
    int hit;
    pc_cat(inp, pr, s, forward, surf, axis, pos, tang, hit);
    return pos;
}

// `place.span_ends`, conformed.
void pc_cspan_ends(const int inp; const int pr; const float sa; const float sb;
                   const int surf; const vector axis;
                   export vector pa; export vector ta;
                   export vector pb; export vector tb) {
    pc_csample(inp, pr, sa, 1, surf, axis, pa, ta);
    pc_csample(inp, pr, sb, 0, surf, axis, pb, tb);
}

// `conform._probe_s` - where to sample [sa, sb].
//
// D71: `fracs` are the module's station positions as fractions of its span, so
// the probes sample exactly what `_deform_positions` will.  A hole that falls
// between five evenly spaced probes but ON a station dipped the built geometry
// to spline elevation with no warning at all - a 0.1 m hole punched a 0.1875 m
// V-notch into the rail while `pc_warn_conform_miss` stayed absent.  The even
// fallback is for a caller with no module; `interior` drops the two ends, which
// is what a chord-deviation measure wants and a hit test does not.
void pc_probe_s(const float sa; const float sb; const int n;
                const float fracs[]; const int interior;
                export float out[]) {
    float vals[];
    if (len(fracs)) {
        float c[];
        foreach (float f; fracs) push(c, min(max(f, 0.0), 1.0));
        c = sort(c);
        // `sorted(set(...))` - the dedupe is EXACT equality, as Python's is.
        foreach (float f; c)
            if (!len(vals) || f != vals[len(vals) - 1]) push(vals, f);
    } else {
        int m = max(n, 2);
        for (int i = 0; i < m; i++) push(vals, i / (float)(m - 1));
    }
    resize(out, 0);
    foreach (float f; vals) {
        if (interior && !(f > PC_PROBE_INTERIOR && f < 1.0 - PC_PROBE_INTERIOR))
            continue;
        push(out, sa + (sb - sa) * f);
    }
}

// `ConformPath.missed` - did any station across [sa, sb] fall off the surface?
int pc_conform_missed(const int inp; const int pr; const float sa;
                      const float sb; const int surf; const vector axis;
                      const float fracs[]) {
    if (!pc_surf_active(surf)) return 0;
    float ss[];
    pc_probe_s(sa, sb, PC_PROBE_N, fracs, 0, ss);
    foreach (float s; ss) {
        vector pos, tang;
        int hit;
        pc_cat(inp, pr, s, 1, surf, axis, pos, tang, hit);
        if (!hit) return 1;
    }
    return 0;
}

// `ConformPath.deviates` - does the drape between `sa` and `sb` leave the
// straight chord?
//
// THIS IS WHAT UNPACKS A PIECE OVER A HILL.  `_needs_deform` looks for interior
// curve vertices, and a dead-straight spline over a ridge has none - so without
// this the curvature budget says "nothing to follow" and a bendable rail
// crosses the hill as one rigid chord with its two ends on the ground.
// Measured against the chord between the two CONFORMED ends, so a piece on a
// uniform slope (whose drape IS a straight line) stays PACKED, which is 4.6's
// segregation surviving the conform rather than being defeated by it.
//
// ⚠️ AND IT IS PROBED ON THE PIECE'S OWN STATIONS (D71), because this is the
// GATE on a deform that would use exactly those.  Five fixed samples made the
// gate strictly coarser than the thing it gates: a 0.3 m wide, 0.5 m tall bump
// centred between them left a bendable panel PACKED as a straight chord with
// the bump 0.400 m through its bottom edge and no warning.
int pc_conform_deviates(const int inp; const int pr; const float sa;
                        const float sb; const float tol; const int surf;
                        const vector axis; const float fracs[]) {
    if (!pc_surf_active(surf) || abs(sb - sa) <= PC_EPS) return 0;
    vector a = pc_cpos(inp, pr, sa, 1, surf, axis);
    vector b = pc_cpos(inp, pr, sb, 0, surf, axis);
    vector ab = b - a;
    float n_ab = length(ab);
    if (n_ab < PC_EPS) return 0;
    vector u = ab / n_ab;
    float ss[];
    pc_probe_s(sa, sb, max(PC_PROBE_N, 3), fracs, 1, ss);
    foreach (float s; ss) {
        vector q = pc_cpos(inp, pr, s, 1, surf, axis) - a;
        float t = dot(q, u);
        if (length(q - u * t) > tol) return 1;
    }
    return 0;
}

#endif
