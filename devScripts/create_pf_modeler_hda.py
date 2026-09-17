"""Create `pf_modeler` - ZSphere-style skinning: a graph of spheres in, an
all-quad mesh out.

    hython devScripts/create_pf_modeler_hda.py

Input: points are the spheres (`pscale` is the radius, or the Radius parm
when there is no pscale), polylines are the connections - every polyline
segment joins its two points. The way ZBrush's Adaptive Skin does it: each
sphere becomes a CUBE, each connection takes one face of the cube at either
end and is bridged with four quads, the faces nothing uses stay as caps,
and Catmull-Clark subdivision rounds the whole cage. Quads by construction,
no boolean, no remesh (ideas/modeler.md).

    pf_modeler                        1 input:
      cage    [attribwrangle/point]   per sphere: a local frame (z along the
                                      connection, or along the most opposed
                                      pair of them), the best of all 720
                                      face orderings for its neighbours,
                                      8 corner points tagged `_node` /
                                      `_corner`; `_nbs`, `_faces` and
                                      `_capfaces` on the sphere point (never
                                      a point NUMBER: addpoint's return
                                      value is not final in a wrangle).
      bridge  [attribwrangle/point]   per sphere: its caps, and 4 quads to
                                      each higher-numbered neighbour between
                                      the two reserved faces, corner pairing
                                      chosen by least twist. A connection
                                      one side could not take gets the
                                      other side's cap back.
      report  [error]                 artist-visible warnings: bad joints,
                                      more than six connections.
      blast   [blast]                 the input graph goes.
      subdiv  [subdivide]             Catmull-Clark, `Subdivisions` times.
      cleanup [attribdelete+groupdelete]  only pf_* leaves (conventions 1, 2, 5)
      OUT

Curves that share a value of an int prim attribute `pf_sheet` (> 0) are
not tubes: they are lofted, in prim order, into ONE closed slab whose
thickness follows their pscale - a wing between two bones. Curves sharing
a `pf_trunk` value are lofted AROUND into one tube whose cross-section is
the polygon they describe - an art-directed trunk - with zipper quad caps.
The `loft` wrangle (detail, one execution, runs first) builds both:
stations along, spans across (square-ish quads, or `Loft Spans`). A
branch curve whose first point lies on a loft curve takes the nearest
surface cell that faces it instead of a cube, and the bridge stitches the
branch to that cell: trunk, branches and sheets come out as one mesh.

Output prim attributes `pf_node` (int): the sphere a face came from, -1 on
a limb or loft; `pf_sheet` / `pf_trunk` (int): the sheet / trunk a face
belongs to, 0 otherwise.
"""

import os
import re

import hou

_POLYFACTORY = os.environ.get("POLYFACTORY", "F:/projects/polyfactory/polyfactory")
HDA_PATH = os.path.join(_POLYFACTORY, "otls", "pf_modeler.hda").replace("\\", "/")

TOOLS_SHELF = """<?xml version="1.0" encoding="UTF-8"?>
<shelfDocument>
  <tool name="$HDA_DEFAULT_TOOL" label="$HDA_LABEL" icon="$HDA_ICON">
    <toolMenuContext name="viewer">
      <contextNetType>SOP</contextNetType>
    </toolMenuContext>
    <toolMenuContext name="network">
      <contextOpType>$HDA_TABLE_AND_NAME</contextOpType>
    </toolMenuContext>
    <toolSubmenu>Poly Factory/Modeling</toolSubmenu>
    <script scriptType="python"><![CDATA[import soptoolutils

soptoolutils.genericTool(kwargs, '$HDA_NAME')]]></script>
  </tool>
</shelfDocument>
"""

NAME = "pf_modeler"
TAB_LABEL = "PF Modeler"
OUTPUT_LABEL = "Skin"
INPUT_LABEL = "Spheres and Connections"
ICON = "SOP_subdivide"

# Shared by both wrangles: which 4 cube corners make face f, CLOCKWISE seen
# from OUTSIDE - Houdini's front face (a Box SOP winds this way; probed).
# Corner c has bit k set when it sits on the +axis-k side. Face f: axis f/2,
# + side when f is even. u, v are the other two axes in right-handed order,
# so the +face runs (+u,+v) (+u,-v) (-u,-v) (-u,+v) and the -face the same
# corners in reverse.
FACE_VEX = r'''
function int[] face_corners(int f) {
    int n = f / 2, pos = (f % 2 == 0);
    int u = (n + 1) % 3, v = (n + 2) % 3;
    int su[] = array( 1, -1, -1,  1);
    int sv[] = array( 1,  1, -1, -1);
    int bit[] = array(1, 2, 4);
    int out[];
    for (int i = 0; i < 4; i++) {
        int k = pos ? (4 - i) % 4 : i;
        int c = (pos ? bit[n] : 0) + (su[k] > 0 ? bit[u] : 0) + (sv[k] > 0 ? bit[v] : 0);
        append(out, c);
    }
    return out;
}
'''

CAGE_VEX = FACE_VEX + r"""
// pf_modeler cage - one cube per sphere, one face reserved per neighbour.
// point(), not f@pscale: the binding would CREATE pscale = 0 on the stream
// and the sheet wrangle would then read zeros instead of Radius
if (i@_loftpt) return;                       // a point the loft made, not a sphere
float r = max(haspointattrib(0, "pscale") ? float(point(0, "pscale", @ptnum)) : chf("../radius"), 1e-5);
setpointgroup(0, "_graph", @ptnum, 1);
i@_node = -1;
// neighbours through the connections only - a curve marked pf_sheet or
// pf_trunk was lofted by the loft wrangle and makes no cubes and no limbs
int nbs[], onsheet = 0, loftid = 0;
string loftattr = "";
foreach (int pr; pointprims(0, @ptnum)) {
    int sid = prim(0, "pf_sheet", pr), tid = prim(0, "pf_trunk", pr);
    if (sid > 0 && findattribvalcount(0, "prim", "_loftsheet", sid) > 0) { onsheet = 1; loftid = sid; loftattr = "_loftsheet"; continue; }
    if (tid > 0 && findattribvalcount(0, "prim", "_lofttrunk", tid) > 0) { onsheet = 1; loftid = tid; loftattr = "_lofttrunk"; continue; }
    int pts[] = primpoints(0, pr);
    int n = len(pts), closed = primintrinsic(0, "closed", pr);
    for (int s = 0; s < n; s++) {
        if (pts[s] != @ptnum) continue;
        if (s > 0 || closed) append(nbs, pts[(s - 1 + n) % n]);
        if (s < n - 1 || closed) append(nbs, pts[(s + 1) % n]);
    }
}
nbs = sort(nbs);
int uniq[];
foreach (int nb; nbs) if (nb != @ptnum && (len(uniq) == 0 || uniq[-1] != nb)) append(uniq, nb);
nbs = uniq;
if (onsheet && len(nbs) == 0) return;
if (onsheet && len(nbs) == 1) {
    // a branch leaving the surface: it takes the nearest surface cell that
    // faces it instead of a cube (the bridge stitches the branch to it)
    i@_attach = 1;
    i[]@_nbs = nbs;
    i[]@_faces = array(-1);
    vector d = normalize(point(0, "P", nbs[0]) - @P);
    int best = -1; float bestd = 1e30;
    int cells[] = findattribval(0, "prim", loftattr, loftid);
    for (int ci = 0; ci < len(cells); ci++) {
        int pr = cells[ci];
        vector nrm = prim_normal(0, pr, 0.5, 0.5);
        if (dot(nrm, d) <= 0.2) continue;
        int cp[] = primpoints(0, pr);
        vector c = 0;
        for (int q = 0; q < len(cp); q++) { vector pp = point(0, "P", cp[q]); c += pp / len(cp); }
        float dd = distance(c, @P);
        if (dd < bestd) { bestd = dd; best = pr; }
    }
    i@_cell = best;
    if (best < 0) setpointgroup(0, "_no_cell", @ptnum, 1);
    return;
}
if (onsheet) setpointgroup(0, "_sheet_limb", @ptnum, 1);
vector d[];
foreach (int nb; nbs) {
    vector q = point(0, "P", nb) - @P;
    append(d, length(q) > 1e-8 ? normalize(q) : {0, 0, 1});
}
int k = len(nbs);

// frame: z along the connection, or along the most opposed PAIR of them
vector z = {0, 0, 1};
if (k == 1) z = d[0];
if (k >= 2) {
    float worst = 2;
    for (int i = 0; i < k; i++) for (int j = i + 1; j < k; j++) {
        float dd = dot(d[i], d[j]);
        if (dd < worst) { worst = dd; z = d[i] - d[j]; }
    }
    z = length(z) > 1e-6 ? normalize(z) : d[0];
}
vector up = abs(dot(z, {0, 1, 0})) > 0.9 ? {1, 0, 0} : {0, 1, 0};
vector x = normalize(cross(up, z));
vector y = cross(z, x);
vector axes[] = array(x, y, z);

// corners - tagged, not numbered: addpoint's return is only valid inside
// this cook of this point, so the bridge finds them by _node/_corner
for (int c = 0; c < 8; c++) {
    vector off = ((c & 1) ? 1 : -1) * x + ((c & 2) ? 1 : -1) * y + ((c & 4) ? 1 : -1) * z;
    int pt = addpoint(0, @P + r * off);
    setpointattrib(0, "_node", pt, @ptnum);
    setpointattrib(0, "_corner", pt, c);
}
i[]@_nbs = nbs;

// faces: the assignment of the first six neighbours to distinct faces
// that maximises the summed dot - all 720 orderings of the six faces,
// decoded in factorial base, the first k entries taken
float dots[];
for (int n = 0; n < k; n++) for (int f = 0; f < 6; f++)
    append(dots, dot(d[n], (f % 2 == 0 ? 1 : -1) * axes[f / 2]));
int fact[] = array(120, 24, 6, 2, 1, 1);
int kk = min(k, 6);
int faces[] = array(-1, -1, -1, -1, -1, -1, -1);
float best = -1e30;
for (int p = 0; p < 720; p++) {
    int avail[] = array(0, 1, 2, 3, 4, 5);
    int rem = p, chosen[];
    float score = 0;
    for (int n = 0; n < kk; n++) {
        int idx = rem / fact[n]; rem = rem % fact[n];
        append(chosen, avail[idx]);
        removeindex(avail, idx);
        score += dots[n * 6 + chosen[n]];
    }
    if (score > best) { best = score; for (int n = 0; n < kk; n++) faces[n] = chosen[n]; }
}
resize(faces, k);
for (int n = 6; n < k; n++) faces[n] = -1;   // resize pads with 0, a taken face
i[]@_faces = faces;

// a limb leaving through the side of its own cube is a bad joint
int used[] = array(0, 0, 0, 0, 0, 0);
for (int n = 0; n < kk; n++) {
    used[faces[n]] = 1;
    if (dots[n * 6 + faces[n]] <= 0.2) setpointgroup(0, "_bad_joint", @ptnum, 1);
}
if (k > 6) setpointgroup(0, "_too_many", @ptnum, 1);

// free faces stay as caps - emitted by the bridge, which can see the
// tagged corners; this cook cannot find the points it just added
int caps[];
for (int f = 0; f < 6; f++) if (!used[f]) append(caps, f);
i[]@_capfaces = caps;
"""

BRIDGE_VEX = FACE_VEX + r"""
// pf_modeler bridge - runs once per sphere: its caps, and four quads to
// every neighbour with a higher number (each connection exactly once,
// whatever the polylines did). Both faces are outward counter-clockwise;
// the far one is walked backwards, from the rotation that twists least.
function int face_for(int a; int b) {
    int nbs[] = point(0, "_nbs", a);
    int faces[] = point(0, "_faces", a);
    int k = find(nbs, b);
    return k < 0 ? -1 : faces[k];
}
function int[] corners_of(int a) {
    int out[] = array(-1, -1, -1, -1, -1, -1, -1, -1);
    foreach (int pt; findattribval(0, "point", "_node", a)) {
        int c = point(0, "_corner", pt);
        out[c] = pt;
    }
    return out;
}
function void cap(int a; int f; int ca[]) {
    int fc[] = face_corners(f);
    int pr = addprim(0, "poly", ca[fc[0]], ca[fc[1]], ca[fc[2]], ca[fc[3]]);
    setprimattrib(0, "pf_node", pr, a);
    setprimattrib(0, "pf_sheet", pr, 0);
    setprimattrib(0, "pf_trunk", pr, 0);
}
// four quads between two outward-clockwise faces, the far one walked
// backwards from the rotation that twists least
function void limb(int A[]; int B[]) {
    int bestr = 0; float best = 1e30;
    for (int rr = 0; rr < 4; rr++) {
        float sum = 0;
        for (int i = 0; i < 4; i++) {
            vector pa = point(0, "P", A[i]);
            vector pb = point(0, "P", B[(rr - i + 4) % 4]);
            sum += distance(pa, pb);
        }
        if (sum < best) { best = sum; bestr = rr; }
    }
    for (int i = 0; i < 4; i++) {
        int j = (i + 1) % 4;
        int pr = addprim(0, "poly", A[i], A[j], B[(bestr - j + 4) % 4], B[(bestr - i + 4) % 4]);
        setprimattrib(0, "pf_node", pr, -1);
        setprimattrib(0, "pf_sheet", pr, 0);
        setprimattrib(0, "pf_trunk", pr, 0);
    }
}
function int[] face_of(int b; int f) {
    int cb[] = corners_of(b), fcb[] = face_corners(f), B[];
    for (int i = 0; i < 4; i++) append(B, cb[fcb[i]]);
    return B;
}
int a = @ptnum;
if (i@_attach) {
    // a branch on a loft surface: its cell stands in for a cube face
    int cell = i@_cell;
    if (cell < 0) return;
    int b = i[]@_nbs[0];
    int fb = face_for(b, a);
    if (fb < 0) return;                         // b dropped us: the cell stays
    int A[] = primpoints(0, cell);
    limb(A, face_of(b, fb));
    removeprim(0, cell, 0);
    return;
}
if (len(i[]@_capfaces) == 0 && len(i[]@_nbs) == 0) return;   // a loft-only point
int ca[] = corners_of(a);
foreach (int f; i[]@_capfaces) cap(a, f, ca);
foreach (int b; i[]@_nbs) {
    int fa = face_for(a, b), fb = face_for(b, a);
    // a branch point with a cell bridges from its own side
    if (point(0, "_attach", b) && point(0, "_cell", b) >= 0 && fa >= 0) continue;
    // a connection the other side could not take (its seventh or later,
    // or a branch that found no cell): this side gets its face back as a cap
    if (fb < 0 && fa >= 0) cap(a, fa, ca);
    if (fa < 0 || fb < 0 || b < a) continue;
    int fca[] = face_corners(fa), A[];
    for (int i = 0; i < 4; i++) append(A, ca[fca[i]]);
    limb(A, face_of(b, fb));
}
"""

LOFT_VEX = r"""
// pf_modeler loft - runs FIRST, once. Curves sharing a pf_sheet value are
// lofted in prim order into one closed slab (thickness = interpolated
// pscale, both ways along the sheet normal); curves sharing a pf_trunk
// value are lofted AROUND, in prim order, into one tube whose cross-section
// is the polygon the curves describe (their pscale is ignored: the lines
// ARE the surface), with zipper quad caps at both ends. Every face is a
// quad wound clockwise from outside (Houdini's front face), and every face
// carries _loftsheet / _lofttrunk = id so a branch can take it (cage).
// Curves are sampled by ARC LENGTH from their points, never primuv: on a
// polyline primuv is uniform per segment (uneven points slant the rungs)
// and on a closed polygon it is the polygon's surface (the slab collapsed).
function void curve_sample(int pr; float u; int flip; export vector P; export float r) {
    int pts[] = primpoints(0, pr);
    int n = len(pts);
    float cum[] = array(0.0);
    for (int i = 1; i < n; i++) {
        vector a = point(0, "P", pts[i - 1]), b = point(0, "P", pts[i]);
        append(cum, cum[-1] + distance(a, b));
    }
    float target = (flip ? 1 - u : u) * cum[-1];
    int i = 1;
    while (i < n - 1 && cum[i] < target) i++;
    float seg = cum[i] - cum[i - 1];
    float t = seg > 1e-9 ? clamp((target - cum[i - 1]) / seg, 0, 1) : 0;
    vector pa = point(0, "P", pts[i - 1]), pb = point(0, "P", pts[i]);
    P = lerp(pa, pb, t);
    float ra = point(0, "pscale", pts[i - 1]), rb = point(0, "pscale", pts[i]);
    r = lerp(ra, rb, t);
}
function float curve_length(int pr) {
    int pts[] = primpoints(0, pr);
    float L = 0;
    for (int i = 1; i < len(pts); i++) {
        vector a = point(0, "P", pts[i - 1]), b = point(0, "P", pts[i]);
        L += distance(a, b);
    }
    return L;
}
function int quad(int a; int b; int c; int d; string tag; int id) {
    int pr = addprim(0, "poly", a, b, c, d);
    setpointattrib(0, "_loftpt", a, 1); setpointattrib(0, "_loftpt", b, 1);
    setpointattrib(0, "_loftpt", c, 1); setpointattrib(0, "_loftpt", d, 1);
    setprimattrib(0, "pf_node", pr, -1);
    setprimattrib(0, "pf_sheet", pr, tag == "sheet" ? id : 0);
    setprimattrib(0, "pf_trunk", pr, tag == "trunk" ? id : 0);
    setprimattrib(0, tag == "sheet" ? "_loftsheet" : "_lofttrunk", pr, id);
    return pr;
}
function void build_loft(int curves[]; int closed; int id; string tag) {
    int nc = len(curves);
    foreach (int pr; curves) if (primintrinsic(0, "closed", pr)) setdetailattrib(0, "_sheet_closed", 1, "set");
    int n = 2;
    foreach (int pr; curves) n = max(n, len(primpoints(0, pr)));
    // direction: a curve whose chord opposes the previous one is walked backwards
    int flips[] = array(0);
    for (int c = 1; c < nc; c++) {
        vector a0, a1, b0, b1; float rr;
        curve_sample(curves[c - 1], 0, flips[c - 1], a0, rr);
        curve_sample(curves[c - 1], 1, flips[c - 1], a1, rr);
        curve_sample(curves[c], 0, 0, b0, rr);
        curve_sample(curves[c], 1, 0, b1, rr);
        append(flips, dot(a1 - a0, b1 - b0) < 0);
    }
    // spans per pair: roughly square quads unless Loft Spans says otherwise
    int npairs = closed ? nc : nc - 1;
    int spans[];
    float along = 0;
    foreach (int pr; curves) along += curve_length(pr) / nc;
    float step = along / (n - 1);
    for (int c = 0; c < npairs; c++) {
        int c2 = (c + 1) % nc;
        float across = 0;
        for (int i = 0; i < n; i++) {
            float u = float(i) / (n - 1);
            vector pa, pb; float rr;
            curve_sample(curves[c], u, flips[c], pa, rr);
            curve_sample(curves[c2], u, flips[c2], pb, rr);
            across += distance(pa, pb) / n;
        }
        int m = chi("../sheetspans") > 0 ? chi("../sheetspans") : int(rint(across / max(step, 1e-6)));
        append(spans, clamp(m, 1, 32));
    }
    int M = 0;
    foreach (int m; spans) M += m;
    if (closed && M % 2 == 1) { spans[-1] += 1; M += 1; }   // zipper caps need an even ring
    int W = closed ? M : M + 1;
    // the mid-surface grid P[i * W + j] and its radius
    vector P[]; float R[];
    for (int i = 0; i < n; i++) {
        float u = float(i) / (n - 1);
        for (int c = 0; c < npairs; c++) {
            int c2 = (c + 1) % nc;
            vector pa, pb; float ra, rb;
            curve_sample(curves[c], u, flips[c], pa, ra);
            curve_sample(curves[c2], u, flips[c2], pb, rb);
            if (!haspointattrib(0, "pscale")) { ra = chf("../radius"); rb = ra; }
            int last = (!closed && c == npairs - 1);
            for (int k = 0; k < spans[c] + last; k++) {
                float t = float(k) / spans[c];
                append(P, lerp(pa, pb, t));
                append(R, max(lerp(ra, rb, t), 1e-5));
            }
        }
    }
    if (closed) {
        int ring[];
        for (int i = 0; i < n; i++) for (int j = 0; j < W; j++) append(ring, addpoint(0, P[i * W + j]));
        // which way round: the ring's cross product against the outward
        // direction from its centre decides the vertex order
        float sign = 0;
        for (int i = 0; i < n - 1; i++) {
            vector rc = 0;
            for (int j = 0; j < W; j++) rc += P[i * W + j] / W;
            for (int j = 0; j < W; j++) {
                vector a = P[i * W + j], b = P[i * W + (j + 1) % W], d = P[(i + 1) * W + j];
                sign += dot(cross(d - a, b - a), (a + b + d) / 3 - rc);
            }
        }
        int fwd = sign < 0;   // sign chosen so the faces wind clockwise from outside (c11)
        for (int i = 0; i < n - 1; i++) for (int j = 0; j < W; j++) {
            int a = i * W + j, b = i * W + (j + 1) % W, d = a + W, c = b + W;
            if (fwd) quad(ring[a], ring[d], ring[c], ring[b], tag, id);
            else     quad(ring[a], ring[b], ring[c], ring[d], tag, id);
        }
        for (int k = 0; k < W / 2 - 1; k++) {
            int v0 = k, v1 = k + 1, v2 = W - 2 - k, v3 = W - 1 - k;
            int e = (n - 1) * W;
            if (fwd) { quad(ring[v0], ring[v1], ring[v2], ring[v3], tag, id);
                       quad(ring[e + v1], ring[e + v0], ring[e + v3], ring[e + v2], tag, id); }
            else     { quad(ring[v1], ring[v0], ring[v3], ring[v2], tag, id);
                       quad(ring[e + v0], ring[e + v1], ring[e + v2], ring[e + v3], tag, id); }
        }
        return;
    }
    int top[], bot[];
    for (int i = 0; i < n; i++) for (int j = 0; j < W; j++) {
        vector along_d = P[min(i + 1, n - 1) * W + j] - P[max(i - 1, 0) * W + j];
        vector across_d = P[i * W + min(j + 1, W - 1)] - P[i * W + max(j - 1, 0)];
        vector N = -normalize(cross(along_d, across_d));   // sign chosen so the faces wind clockwise from outside (c10)
        vector q = P[i * W + j];
        append(top, addpoint(0, q + N * R[i * W + j]));
        append(bot, addpoint(0, q - N * R[i * W + j]));
    }
    for (int i = 0; i < n - 1; i++) for (int j = 0; j < W - 1; j++) {
        int a = i * W + j, b = a + 1, c = a + W + 1, d = a + W;
        quad(top[a], top[d], top[c], top[b], tag, id);
        quad(bot[a], bot[b], bot[c], bot[d], tag, id);
    }
    for (int i = 0; i < n - 1; i++) {
        int a = i * W, d = a + W;                    // j = 0 wall
        quad(top[a], bot[a], bot[d], top[d], tag, id);
        a = i * W + W - 1; d = a + W;                // j = W-1 wall
        quad(top[a], top[d], bot[d], bot[a], tag, id);
    }
    for (int j = 0; j < W - 1; j++) {
        int a = j, b = a + 1;                        // i = 0 wall
        quad(top[a], top[b], bot[b], bot[a], tag, id);
        a = (n - 1) * W + j; b = a + 1;              // i = n-1 wall
        quad(top[a], bot[a], bot[b], top[b], tag, id);
    }
}
string loftattrs[] = array("pf_sheet", "pf_trunk");
foreach (string attr; loftattrs) {
    if (!hasprimattrib(0, attr)) continue;
    if (attribtype(0, "prim", attr) != 0) { i@_sheet_bad_type = 1; continue; }
    int ids[];
    for (int pr = 0; pr < nprimitives(0); pr++) {
        int sid = prim(0, attr, pr);
        if (sid > 0 && find(ids, sid) < 0) append(ids, sid);
    }
    ids = sort(ids);
    foreach (int sid; ids) {
        int curves[];
        for (int pr = 0; pr < nprimitives(0); pr++)
            if (prim(0, attr, pr) == sid) append(curves, pr);
        if (len(curves) < 2) { i@_sheet_alone = 1; continue; }
        if (attr == "pf_trunk" && len(curves) < 3) { i@_trunk_thin = 1; continue; }
        build_loft(curves, attr == "pf_trunk", sid, attr == "pf_trunk" ? "trunk" : "sheet");
    }
}
"""

RESOLVE_VEX = r"""
// pf_modeler resolve - two branches that chose the same surface cell:
// the lower-numbered keeps it, the other is dropped with a warning.
int taken[];
foreach (int pt; findattribval(0, "point", "_attach", 1)) {
    int c = point(0, "_cell", pt);
    if (c < 0) continue;
    if (find(taken, c) >= 0) { setpointattrib(0, "_cell", pt, -1); setpointgroup(0, "_cell_clash", pt, 1); }
    else append(taken, c);
}
"""


if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_" + NAME)
subnet = build_geo.createNode("subnet", NAME)
subnet.createNode("null", "OUT").setDisplayFlag(True)

hda_node = subnet.createDigitalAsset(
    name=NAME, hda_file_name=HDA_PATH, description=TAB_LABEL,
    min_num_inputs=1, max_num_inputs=1, version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setMinNumInputs(1)
defn.setMaxNumInputs(1)
defn.setIcon(ICON)

net = hda_node
out_null = net.node("OUT")
src = net.indirectInputs()[0]


def _place(node, x, y, comment=None):
    node.setPosition(hou.Vector2(x, y))
    if comment:
        node.setComment(comment)
        node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return node


loft = _place(net.createNode("attribwrangle", "loft"), 0, 8,
              "Sheets (pf_sheet) and trunks (pf_trunk) lofted first,\n"
              "so a branch can take one of their cells.")
loft.setInput(0, src)
loft.parm("class").set("detail")
loft.parm("snippet").set(LOFT_VEX)

cage = _place(net.createNode("attribwrangle", "cage"), 0, 7,
              "One cube per sphere; a face per connection.")
cage.setInput(0, loft)
cage.parm("class").set("point")
cage.parm("snippet").set(CAGE_VEX)

resolve = _place(net.createNode("attribwrangle", "resolve"), 0, 6.5,
                 "Two branches wanting one cell: the later one loses it.")
resolve.setInput(0, cage)
resolve.parm("class").set("detail")
resolve.parm("snippet").set(RESOLVE_VEX)

bridge = _place(net.createNode("attribwrangle", "bridge"), 0, 6,
                "Four quads per connection, least twist.")
bridge.setInput(0, resolve)
bridge.parm("class").set("point")
bridge.parm("group").set("_graph")
bridge.parm("grouptype").set("points")
bridge.parm("snippet").set(BRIDGE_VEX)

report = _place(net.createNode("error", "report"), 0, 5,
                "Warnings the artist can see (a locked asset hides VEX warnings).")
report.setInput(0, bridge)
report.parm("numerror").set(9)
report.parm("severity1").set("warn")
report.parm("enable1").setExpression('npointsgroup(opinputpath(".", 0), "_bad_joint")')
report.parm("errormsg1").set("Some spheres have connections too close together for a cube "
                             "joint (a limb leaves through the side of its own cube). Spread "
                             "them out or add a sphere between.")
report.parm("severity2").set("warn")
report.parm("enable2").setExpression('npointsgroup(opinputpath(".", 0), "_too_many")')
report.parm("errormsg2").set("A sphere has more than six connections; the seventh and later "
                             "are dropped (a cube has six faces).")
report.parm("severity3").set("warn")
report.parm("enable3").setExpression('npointsgroup(opinputpath(".", 0), "_sheet_limb")')
report.parm("errormsg3").set("A sheet or trunk point has two or more connections: it gets a "
                             "cube that overlaps the surface. Only a single branch joins a "
                             "surface.")
report.parm("severity4").set("warn")
report.parm("enable4").setExpression('detail(opinputpath(".", 0), "_sheet_alone", 0)')
report.parm("errormsg4").set("A pf_sheet value is on only one curve; a sheet needs two or more.")
report.parm("severity5").set("warn")
report.parm("enable5").setExpression('detail(opinputpath(".", 0), "_sheet_bad_type", 0)')
report.parm("errormsg5").set("pf_sheet must be an integer primitive attribute.")
report.parm("severity6").set("warn")
report.parm("enable6").setExpression('detail(opinputpath(".", 0), "_sheet_closed", 0)')
report.parm("errormsg6").set("A sheet curve is a closed polyline; it is lofted as if open, "
                             "without its closing segment.")
report.parm("severity7").set("warn")
report.parm("enable7").setExpression('detail(opinputpath(".", 0), "_trunk_thin", 0)')
report.parm("errormsg7").set("A pf_trunk value is on fewer than three curves; a trunk needs "
                             "three or more lines around it.")
report.parm("severity8").set("warn")
report.parm("enable8").setExpression('npointsgroup(opinputpath(".", 0), "_no_cell")')
report.parm("errormsg8").set("A branch on a sheet or trunk points into the surface, so no "
                             "cell faces it; the branch is dropped. Aim it outward.")
report.parm("severity9").set("warn")
report.parm("enable9").setExpression('npointsgroup(opinputpath(".", 0), "_cell_clash")')
report.parm("errormsg9").set("Two branches want the same surface cell; the later one is "
                             "dropped. Move it along, or raise Loft Spans.")

blast = _place(net.createNode("blast", "blast"), 0, 4.5, "The input graph goes.")
blast.setInput(0, report)
blast.parm("group").set("_graph")
blast.parm("grouptype").set("points")

subdiv = _place(net.createNode("subdivide", "subdiv"), 0, 4,
                "Catmull-Clark: quads in, quads out, rounded.")
subdiv.setInput(0, blast)
subdiv.parm("iterations").setExpression('ch("../subdivisions")')

cleanup = _place(net.createNode("attribdelete", "cleanup"), 0, 3,
                 "Only pf_* leaves (conventions.md 1, 2): input attributes\n"
                 "would otherwise ride out on the new points as zeros.")
cleanup.setInput(0, subdiv)
for cls in ("pt", "vtx", "prim", "dtl"):
    cleanup.parm("do%sdel" % cls).set(1)
    cleanup.parm("%sdel" % cls).set("* ^pf_*")

cleangrp = _place(net.createNode("groupdelete", "cleanup_groups"), 0, 2,
                  "`_*` groups too (conventions.md 5).")
cleangrp.setInput(0, cleanup)
cleangrp.parm("group1").set("_*")

out_null.setInput(0, cleangrp)
out_null.setPosition(hou.Vector2(0, 1))

ptg = hou.ParmTemplateGroup()
_sub = hou.IntParmTemplate("subdivisions", "Subdivisions", 1, (2,), min=0, max=4,
                           min_is_strict=True, max_is_strict=False)
_sub.setHelp("How many times the cube cage is subdivided. 0 shows the raw cage "
             "of cubes and bridges; 2 is a smooth base mesh; every step "
             "quadruples the face count.")
ptg.append(_sub)
_spans = hou.IntParmTemplate("sheetspans", "Loft Spans", 1, (0,), min=0, max=32,
                             min_is_strict=True, max_is_strict=False)
_spans.setHelp("Quads across a sheet or around a trunk, between each pair of its curves. 0 "
               "picks as many as make the quads roughly square; set it to trade smoothness "
               "for face count, or to give branches smaller cells to attach to.")
ptg.append(_spans)
_rad = hou.FloatParmTemplate("radius", "Radius", 1, (0.1,), min=0.001, max=1.0,
                             min_is_strict=True, max_is_strict=False)
_rad.setHelp("Sphere radius used when the input points carry no pscale. A "
             "pscale attribute on the points always wins.")
ptg.append(_rad)
defn.setParmTemplateGroup(ptg)
defn.setExtraFileOption("pf/source", __file__.replace("\\", "/"))
_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

defn = hou.hda.definitionsInFile(HDA_PATH)[0]
ds = defn.sections()["DialogScript"].contents()
if "outputlabel" in ds:
    ds = re.sub(r'outputlabel\t1\t"[^"]*"', 'outputlabel\t1\t"%s"' % OUTPUT_LABEL, ds)
else:
    ds = ds.replace('  parm {', '  outputlabel\t1\t"%s"\n  parm {' % OUTPUT_LABEL, 1)
if "inputlabel" in ds:
    ds = re.sub(r'inputlabel\t1\t"[^"]*"', 'inputlabel\t1\t"%s"' % INPUT_LABEL, ds)
else:
    ds = ds.replace('  parm {', '  inputlabel\t1\t"%s"\n  parm {' % INPUT_LABEL, 1)
defn.addSection("DialogScript", ds)
defn.addSection("Tools.shelf", TOOLS_SHELF)
# an Error SOP's warnings reach the asset's user only from a Message Node
defn.addSection("MessageNodes", "report")
hda_node.destroy()
build_geo.destroy()

back = hou.hda.definitionsInFile(HDA_PATH)[0]
saved = back.sections()["DialogScript"].contents()
assert "Poly Factory/Modeling" in back.sections()["Tools.shelf"].contents()
assert back.icon() == ICON and back.description() == TAB_LABEL
assert back.sections()["MessageNodes"].contents().strip() == "report"
assert 'outputlabel\t1\t"%s"' % OUTPUT_LABEL in saved
for _p in ("subdivisions", "sheetspans", "radius"):
    assert re.search(r'name\s+"%s"' % _p, saved), _p
print("wrote " + HDA_PATH)
