# Modeler — ZSphere-style skinning: spheres and connections in, quads out

**Status:** groundwork built 2026-09-17 on branch `pf-modeler`. Nine checks, eleven mutations,
all seen red, green on five seeds (`tests/hda/run_modeler_checks.py`). Two independent audit
rounds done, every finding fixed (§4).
**This file owns:** `pf_modeler` — the representation, the skinning method, the checks and
their blind spots, and what is deliberately not built yet (the interactive editor).
**Origin:** Hannes wants the ZSpheres workflow — place spheres, connect them, get a quad base
mesh — after reading the Dust3D assessment in
`D:/godotGames/docs/tech/ai_procedural_modeling_skill.md`. That note's Houdini table (Sweep +
Boolean) is **not** what this tool does: Dust3D unions its tubes with a triangle boolean and
only recovers quads where triangle pairs survive, so every joint is triangles. Verified in its
`mesh_combiner.cc` / `mesh_generator.cc` (2026-09-17). ZBrush's Adaptive Skin is a cube cage
instead, and that is the method here.

**Scope Hannes set (2026-09-17):** no importer, no rig, no UI yet — "a tool which places the
spheres with the connections and generates a quad topology", the starting point.

---

## 1. Representation

The input is ordinary Houdini geometry, so any stock tool can author it for now:

| Thing | In the input |
|---|---|
| a sphere | a point; `pscale` is its radius (the `Radius` parm when there is no `pscale`) |
| a connection | a polyline segment — every consecutive pair of points on a polyline; closed polylines close the loop |
| a sphere on a limb | a point shared by two segments (one polyline through it, or two fused) |

No `pf_` attributes are required on the input. Output prim attribute **`pf_node`** (int): the
sphere a face came from, `-1` on a limb.

## 2. Method — the Adaptive Skin cube cage, in two wrangles

Quads by construction: the cage is quads, Catmull-Clark keeps quads. No boolean, no remesh.

1. **`cage`** (point wrangle, one execution over all spheres). Each sphere becomes a cube of
   half-size `pscale` (clamped ≥ 1e-5) in a local frame: `z` along the connection, or along
   `d_i − d_j` for the **most opposed pair** of connections; `up` is world Y unless `z` is
   within ~25° of it, then world X. Neighbours (sorted by point number, first six) are
   assigned to distinct faces by the **best of all 720 face orderings** — the one with the
   largest summed dot — decoded in factorial base, cheap. A limb whose face dot is ≤ 0.2 marks
   the sphere `_bad_joint`; a seventh connection marks `_too_many`. Corners are **tagged**
   `_node`/`_corner`, never stored by number — `addpoint`'s return value is not the final point
   number in a wrangle (both spheres came back with corners 20–27; found by check c4). The
   free faces are recorded as `_capfaces`; this wrangle cannot find the points it just added,
   so the bridge emits the caps.
2. **`bridge`** (point wrangle over the graph spheres). Per sphere: its caps, then for every
   neighbour with a higher number, the two reserved faces (`_nbs`/`_faces`, corners via
   `findattribval`), the far face walked backwards, and of the four rotations the one with the
   least total corner distance — the least-twist pairing (check c7). Four quads, wound so the
   tube shares every edge with the caps in opposite directions (check c2). Bridging from the
   neighbour list, not the polylines, makes a duplicated connection **one** limb; a connection
   the other side could not take gives this side its face back as a cap (check c8).
3. **`report`** (Error SOP, on the asset's Message Nodes list — without that an inner warning
   never reaches the locked instance; probed, then found in the Error SOP help): *connections
   too close together for a cube joint* and *more than six connections*, as warnings the artist
   sees (check c9). **`blast`** removes the input graph; **`subdivide`** (OpenSubdiv
   Catmull-Clark, `Subdivisions` times, default 2); every attribute and group except `pf_*` is
   deleted — input attributes would otherwise ride out on the new points as zeros
   (`pscale = 0` on a skin mesh; audit finding).

**Parameters:** `Subdivisions` (0–4) and `Radius` (fallback when there is no `pscale`).

**Limits, by construction:** a cube has six faces 90° apart, so connections bunched tighter
than that cannot all leave through a face — the tool warns, it does not refuse (the mesh is
still closed and all-quad, it just self-intersects there); the seventh and later connections
at one sphere are dropped, with a warning. A sphere fully inside its neighbour's cube gets an
inverted sleeve, as in ZBrush.

## 3. Checks, and what they cannot see

`hython tests/hda/run_modeler_checks.py [seed]`, against the shipped asset, throwaway session.
Fixture: a seeded random tree of 12 spheres (degrees up to six), a closed loop of three, a
four-sphere chain as one polyline, an isolated sphere. Each check has a mutation seen red:

| check | asserts | mutation |
|---|---|---|
| c1 every face is a quad | at subdivision 0 and 2, no prim has ≠ 4 vertices | bridge emits triangles |
| c2 closed and consistently wound | every directed edge once, its reverse present | bridge quads reversed |
| c3 faces point outward | Houdini's own `prim.normal()` points away from the owning sphere on every cap (Houdini front faces wind **clockwise** seen from outside; the first build wound them counter-clockwise and shipped inverted, found by Hannes in the viewport) | corner order inside out |
| c4 every connection joins its spheres | each sphere has 8 corners at r√3; every segment's two spheres in one connected piece; 4 pieces | bridge bypassed |
| c5 output contract | no `_*` attribute or group; `pf_node` int with −1 and ≥ 0 | cleanup bypassed |
| c6 Radius parm without pscale | 8 corners per sphere at Radius·√3 | radius hard-coded |
| c7 joints do not self-intersect | Intersection Analysis SOP reports 0 on a straight chain, a 90° bend, a tetrahedral hub, a six-limb hub | worst-twist rotation |
| c8 awkward connectivity stays closed | eight-limb hub, a pair linked twice, a loop written `[0, 1, 0]`: closed, all quads, 94 prims | cap restore removed; resize padding restored |
| c9 warnings reach the locked instance | five limbs within 20° warn "too close"; a seventh limb warns "more than six"; a single limb warns nothing | report node bypassed; `_too_many` group removed |

Verified by eye 2026-09-17 on a wireframe (`hython` + PIL, 94 cage quads / 1 504 subdivided
quads counted against the geometry): smooth tubes with edge loops running along each limb,
the loop and the chain closed and rounded.

**Cannot see:** how the limbs *look* — twist at a sharp bend, pinching where three limbs meet,
the boxy ends before subdivision. That is Hannes' viewport. Limbs crossing each other away
from a joint are input, not the tool. The 0.2 bad-joint threshold is a guess; c9 sits far
inside it.

## 4. Audit

**Round 1 (2026-09-17, independent agent, headless, ~30 adversarial inputs).** Verdict "not
yet": topology invariants held everywhere, but the greedy per-neighbour face assignment sent a
limb through the side of its own cube on 9 of 30 random seeds with the suite green; a seventh
connection left an open hole (the far cube's face was reserved and never capped); a pair
linked twice gave a doubled, non-manifold limb; inner VEX warnings never reached the locked
instance; input attributes left the node as zeros; the least-twist rotation was unchecked
(the worst rotation kept all six checks green). **All fixed** in the build above — global
assignment on the most-opposed-pair frame, cap restore, neighbour-list bridging, Message Node,
`pf_*`-only cleanup — and each has a check now (c5 tightened, c7–c9 new). Left as stated
limits: bunched connections (warned, not refused), negative `pscale` (clamped).

**Round 2 (2026-09-17, same agent, on the fixed build).** Verdict **yes, sound enough to
build the editor on**, with one bug: at eight or more connections `resize(faces, k)` pads
with 0, a face already taken, so the eighth limb was built onto it — doubled edges, a limb
through the cube, while the warning said "dropped". Fixed (entries past six set to −1), c8's
hub is eight limbs now and the padding has its own mutation seen red; c9 also asserts the
"more than six" warning, which no check had read. Re-measured by the auditor: warning fires
exactly when an assigned dot ≤ 0.2 on 30/30 seeds; six axis-aligned limbs score 1.0 each;
degree-7 hole, duplicate limb, coincident spheres, negative `pscale` all clean. Two things it
named as unverified and are stated limits: the most-opposed-pair frame has no check of its own
(c7's joints are symmetric, so reverting it to "first neighbour" stays green); and joints with
every dot ≥ 0.28 can still self-intersect without a warning (five limbs within 20°: 12
crossings, silent).

**Status after round 2: audited; the round-2 fix is check-covered but not itself re-audited.**

## 5. Not built yet, in the order Hannes named it

1. **Interactive placement** — a Python viewer state: click to add a sphere as child of the
   selected one, drag its radius, link two spheres. This is the ZSpheres feel and the larger
   piece of work; the skin behind it is done.
2. Joint quality — a better frame for three-plus-connection spheres (pick the most opposed pair
   for `z`), and membranes at L/T joints the way Adaptive Skin's `Mbr` does.
3. Dust3D `.ds3` import and auto-rig — explicitly not wanted now.
