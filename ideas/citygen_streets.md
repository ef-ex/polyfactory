# CityGen — Street Generation Design

**Status:** V1 built and shipping as four HDAs (§6b); defects and the fix order are in §4d.
**Owner doc for:** street field → graph → intersections → road geometry → blocks → lots.
**System-level architecture and cross-cutting contracts:** [`citygen.md`](citygen.md) — read that first.
**Reference library:** `polyfactory/resources/citygen/README.md` (gitignored, local).

Branch `cityGen`. Written 2026-08-08.

---

## 1. Hard constraints

Set by Hannes, 2026-08-08. These are not negotiable and every decision below respects them.

1. **100% Houdini.** No third-party software as a requirement — not CityEngine, not
   `cityengine_for_houdini`, not Beyond Typicals, not an external solver.
2. **Vanilla Houdini only — this whole document is "the core".** SideFX Labs is a separate install,
   so **no stage S0–S8 may depend on a Labs node at runtime.** Labs *may* be studied, and its
   approach forked and reimplemented as our own polished HDA — Labs tools are considered good
   starting points that are too simple, too restrictive and too weak on art direction to ship as-is.
   See [`citygen.md`](citygen.md) §5. `Labs Road Generator` is not used.

3. **Art direction outranks everything** — [`citygen.md`](citygen.md) §2. Two rules bind every
   stage below: **no constants, only defaults the artist can override** (the resolution cascade),
   and **validation is advisory** (`block`/`warn`/`ignore` with a global "allow invalid" switch,
   warnings persisted on the element rather than printed). Anywhere this document names a number,
   read it as a default.
3. **Everything directable.** Procedural generation is the starting point, not the deliverable.
   Any artist edit must survive.
4. **Standard vocabulary, our own implementation.** Attribute names (`streetWidth`,
   `sidewalkWidthLeft`…), the junction classification words and the `layer`/`bridge`/`tunnel`
   convention are the ordinary terms of art in urban modelling and open map data. Using the
   industry's words makes the schema read correctly to anyone; it carries zero dependency and
   implies nothing about how any other tool is built.

   Commercial tools are studied as evidence of what the problem demands. **Nothing here is a
   rebuild of any of them**, and every stage is written from the published literature and our own
   geometry.

   ⚠️ **House rule, 2026-08-09.** Never write that our work is *taken from*, *follows*, *copies*,
   *clones* or *is similar to* a commercial product — in source comments, in these docs, anywhere.
   Recording what a tool *does* is fine and often useful evidence; phrasing our implementation as
   derived from it is not. Academic papers are the exception: cite them normally and by name.

### Confirmed parameters

| Parameter | Value |
|---|---|
| Units | **metres**, metric throughout |
| Render target | **offline film rendering.** No real-time engine constraints |
| Topology | **cached.** Edits change parameters; topology changes are explicit and destructive |
| Bridges / tunnels / overpasses | **required in v1** |
| Multi-level sci-fi (stacked streets, sky lanes, rail) | **not v1, but the schema must not preclude it** |

Because rendering is offline, there is no draw-call budget, no lightmap UVs and no game-LOD work —
and geometry can be generated **per shot, camera-frustum filtered**. That is a large simplification.

---

## 2. Diagnosis: why the previous attempts produced unsatisfying output

Hannes: *"they are kinda working but I never got them to a point where I generated satisfying
output."* Reading `polyfactory/vex/include/pf_streetgen.vfl` and `streamline.vfl`, the cause is
identifiable and it is **not** the field maths — that part is sound.

What exists today: `getTheta` → `getMajor`/`getMinor` produce the two perpendicular eigenvector
directions; `getNewDir` gathers nearby field vectors weighted by a `weight` attribute and fixes
the sign ambiguity via `dot(prevDir, newDir)`; `drawStreet` walks a polyline through the field.
That is a legitimate hyperstreamline tracer and it matches Chen 2008's core idea.

**What is missing is everything that turns traces into a network:**

| Missing | Consequence |
|---|---|
| **No snapping to existing nodes** | traces pass near each other but never connect |
| **No termination on proximity** to an existing trace | streets overshoot through other streets |
| **No intersection computation / edge splitting** | crossings are visual only, not topological |
| **No planarization** | the result is a pile of curves, not a graph |
| **No face extraction** | ⇒ **no blocks ⇒ no lots ⇒ no buildings** |
| **No seeding strategy** | density is uneven and unpredictable |
| **No degeneracy cleanup** | slivers, stubs, near-parallel duplicates survive |
| **No street hierarchy** | every street is equally important; cities are not like that |

> **The core insight: a city is defined by the *closed faces* of a planar graph, not by its
> curves.** Independent streamlines can never close a face. That is why the output never looked
> like a city — the missing 80% is the graph stage, not the tracer.

Two smaller findings in the existing VEX, for whoever touches it:

- `drawStreet` integrates with **forward Euler** (`pos = pos + newDir*stepSize`). On curved fields
  this drifts and produces the characteristic wobble. **RK2 (midpoint) minimum**, and it is a
  three-line change.
- The doc comments on `getMinor`/`getMajor` are **swapped** (`getMinor` says "get major vector"
  and vice versa). Harmless but actively misleading — fix when touched.

`resources/citygen/hip/cityGen_intersectionSolver_2025-11-06.hip` is the most recent prior art and
should be opened before Stage S5 is designed in detail.

---

## 3. Architecture: staged pipeline with schema contracts

Every stage is an HDA that consumes and produces **geometry conforming to a documented attribute
schema** (§6). The schema *is* the API. Consequences:

- any stage can be replaced without touching its neighbours
- an artist can **inject hand-drawn splines directly at S3** — "draw splines that are streets" is
  not a special case, it is just entering the pipeline one stage later
- a stage can be prototyped in Python and rewritten in VEX later with no downstream change

```
S0  Domain          terrain + masks (water, park, obstacle, density, height limit)
S1  Field           direction/tensor field            ← PLUGGABLE generators
S2  Trace           seeds → raw centrelines
S3  Graph           planarize + snap + cleanup        ← THE CONTRACT. Artist entry point.
S4  Classify        hierarchy + junction typing
S5  Intersections   node geometry
S6  Cross-section   template → profile → swept road geometry
S7  Blocks          closed faces of the graph
S8  Lots            subdivision + viability
```

S7/S8 hand off to the building subsystem; S3 and S8 emit the masks the biome subsystem needs
(see `citygen.md` for both contracts).

---

## 3b. The unanimous baseline — where all four sources agree

Added 2026-08-09. Sources: **P** = Parish & Müller 2001 · **C** = Chen et al. 2008 ·
**CE** = CityEngine docs · **S** = Subversion dev diaries. Every row below was checked against the
source itself, not from memory (ledger: `resources/citygen/README.md` §9).

Where all four independently do the same thing, **do it their way and stop designing.** Where they
disagree or stay silent, we are on our own and should expect it to be expensive.

| # | Feature | P | C | CE | S | Ours |
|---|---|:--:|:--:|:--:|:--:|---|
| 1 | Pipeline: maps → street graph → blocks → lots → buildings | ✓ | ✓ | ✓ | ✓ | ✅ |
| 2 | A block **is** a closed face of the street graph, and dies when the loop opens | ✓ | ✓ | ✓ | ✓ | ✅ |
| 3 | **Majors traced first until they enclose regions; minors subdivide those regions** | ✓ | ✓ | ✓ | ✓ | ❌ |
| 4 | Named patterns (grid + radial minimum) **blended by weighted sum** over maps | ✓ | ✓ | ✓ | ✓ | ✅ |
| 5 | Terrain / water / obstacle supplied as **maps**, streets route around them | ✓ | ✓ | ✓ | ✓ | ❌ |
| 6 | A **density map** drives both seeding and street spacing | ✓ | ✓ | ~ | ✓ | ❌ |
| 7 | Ends **connect or extend** — dangling is a failure, not an output | ✓ | ✓ | ✓ | ~ | ❌ |
| 8 | A short crossing of an illegal area is **allowed and flagged → becomes a bridge** | ✓ | ✓ | ~ | ✓ | ❌ |
| 9 | Street attributes (width, type, lanes) live **on graph edges and nodes** | ✓ | ✓ | ✓ | — | ✅ |
| 10 | Lots by **recursive splitting**, convex, discard no-frontage | ✓ | — | ✓ | (wants) | ❌ |
| 11 | Junction / intersection **surface** construction | — | — | ✓ | ✗ | ours |

`~` = consistent but not stated in those terms · `—` = source has no position · `✗` = explicitly not done.

### What this changes

**Row 3 is the single most valuable finding, and we get it wrong.** All four describe the *same*
mechanism, and it is not "trace majors, then trace minors":

- **C §6.2** — the major edges plus topography *divide the domain into regions*, and a minor field is
  traced **inside each region**.
- **CE** — *"major streets are created until they enclose an area, called a quarter. Then the quarter
  is subdivided by minor streets."*
- **P** — highways connect population peaks globally; streets *"cover the areas between highways […]
  giving all neighborhoods transportation access to the nearest highway."*
- **S** — highways first, then local roads connecting districts to the nearest highway.

We trace both families globally against two separate occupancy grids. **A minor street confined to a
region cannot dangle** — its boundary terminates it — so this one change addresses the dead-end
defect (§4d) structurally rather than by repair, *and* it produces the hierarchy for free. It also
means **S7 face extraction must run before minor tracing**, which reorders the pipeline: S3 and S7
interleave rather than running once each.

**Row 8 is a cheaper bridge rule than the one in §S5b.** P, C and S all use the same one: attempt the
crossing, allow it if it is under a length threshold, **flag the segment**, and let the geometry stage
replace it with a bridge or two tunnel mouths. P: *"Highways are allowed to cross illegal area up to
a specified length. The generated highway segment is flagged. At the geometry creation stage it can
then be replaced by e.g. a bridge, or two tunnel entrances on both sides."* C: *"we also allow the
tracing to cross relatively narrow water regions to form bridges."*
The cost-field least-cost routing in §S5b is a strictly more ambitious design that no source uses.
**Ship the flag rule in v1; keep cost routing as the upgrade** — the `is_bridge` attribute is the same
either way, so nothing is wasted.

**Row 11 has no consensus to lean on.** Chen states outright that geometry generation *"is not the
focus of our work"*; Parish only smooths curvature; Subversion does not solve intersections at all
(its roads and buildings visibly interpenetrate). CityEngine does it but documents no algorithm. This
is why S5 has been the hardest stage — there is no canonical answer to copy, and the reference base
is StreetGen 2018, A/B Street and Hannes' own solver. Expect to keep paying for it.

**⭐ The eighth check changed the conclusion.** BeyondCAD's *Civil Engine* looked like a
counter-example — it handles intersections, roundabouts and interchanges — but it
**requires a base model authored in SketchUp or InfraWorks** and only dresses it with
assets, striping and traffic. It never computes the junction surface either.

Which exposes the real gap: **we have only been reading games and VFX.** Civil engineering
CAD solves this routinely, because it is regulated work — it is filed under *corridor*,
*curb return*, *design radius*, *turning template*, *superelevation*, *intersection
wizard*. Autodesk Civil 3D's intersection wizard builds curb returns from design radii, and
Transoft's AutoTURN derives the corner radius from **swept-path analysis of the vehicle
that has to turn through it** — a principled version of the rule we just adopted above.
That literature is standardised and defensible in a way nothing in the games sources is.
**Sweep it before the next S5 change.** Links in `resources/citygen/README.md` §4.

A **sixth** data point, 2026-08-09: **Cities: Skylines 1 and 2 do not solve junction
geometry either.** A junction there is a prepared **node mesh**, subdivided ~16 times and
cut through the middle so the engine can split it around the intersection centre, deformed
along the spline by a vertex shader. Same family as Epic's kit. Its *data model* is worth
comparing against ours though — a node holds positions, a segment holds directions, and a
Bezier is derived from the pair. Details in `resources/citygen/README.md` §4.

There is one genuine solver worth acquiring: **JunctionArt** (AugmentedDesignLab) generates
intersections with **three to seven incident roads** and outputs OpenDRIVE. It is the only
reference found that addresses degree-5+ at all, which is exactly our untested case.

A fifth data point, checked 2026-08-09: **Epic's City Sample does not solve junctions either.** It
ships a modular kit indexed by width pair and quantised angle — three legal road widths (19/27/37),
a discrete signed angle set for transition pieces, five sidewalk corner angles, and a catch-all
`SM_ROAD_corner_filler`. The network is constrained to fit the kit. Correct for a real-time game with
modular Nanite meshes; unusable for us, since arbitrary angles and artist-authored cross-sections are
requirements. Evidence and file names in `resources/citygen/README.md` §1.

### Decision — 2026-08-09

**Rows 1–10 are accepted as the V1 baseline and will be implemented the way the sources describe.**
Hannes: *"everything except row 11 right now is safe to be implemented from my point of view. And for
row 11 we already work on our own solver."* Rows 3, 5, 6, 7, 8 and 10 are therefore work items, not
open questions — the design argument on each is closed.

**Row 4 is confirmation, not a change.** We already blend grid and radial descriptors by weighted
sum, which is exactly P's *"proposed parameter values are summed up and weighted according to the
value in the input image grey scale map"* and C's *"blended using decaying radial basis functions"*.
What is missing is a shipped **organic/noise** generator — P's Basic rule, C's rotation fields, CE's
Organic. Designed in §S1, not built.

---

## 4. Stage design

### S0 — Domain

Inputs the artist supplies: terrain (heightfield or mesh), plus 2D masks. Following Chen 2008 and
CityEngine's environment maps, the useful ones are:

- `water` — hard exclusion
- `park` — soft exclusion, streets route around
- `obstacle` — hard exclusion, generator must circumnavigate rather than stop
- `density` — drives seed density and street-to-crossing ratio
- `height_limit` — not used by streets, passed through for buildings

Terrain coupling is a cross-subsystem contract — see `citygen.md`. Street-side parameters:
`respect_elevation` (bool), `critical_slope` (only streets steeper than this adapt to elevation),
`max_slope` (hard cap). Standard terms of art - they are already the right abstractions.

### S1 — Field (pluggable generators)

Produces a direction field sampled on a grid or point cloud: `dir_major`, `dir_minor`, `weight`,
and a `degenerate` flag where magnitude collapses. This matches what the existing
`getNewDir`/`drawStreet` already expect, so today's VEX keeps working.

**Generators are plugins, not modes.** This is the correction to the original plan: the artist's
list of desired patterns does *not* come from one algorithm.

| Generator | Basis | Artist control |
|---|---|---|
| `grid` | constant θ | rectangle / angle |
| `radial` | field around a centre | circle, centre point |
| `organic` | noise-perturbed θ, randomised bend | amplitude, scale |
| `terrain` | contour + gradient directions from the heightfield | blend weight |
| `brush` | painted directions | direct paint |

Fields **blend by weighted sum** with per-generator falloff regions, which is exactly the
"circle → radial, rectangle → grid, mix them" behaviour requested, and exactly Chen 2008's
combinable basis fields.

⚠️ **Every generator has degenerate points and they must be declared, not discovered.** A `radial`
field is degenerate *at its own centre* — the eigenvectors are undefined there, so every streamline
converges on the singularity and folds. Chen 2008 treats degeneracies as first-class: tracing stops
on one (criterion 2), and the generator publishes their locations. Each generator therefore emits a
**`degenerate` point set** alongside the field, with a `plaza_radius` (default, artist-overridable)
that S2 treats as a hard exclusion. What fills the hole is S5's business: a **plaza or roundabout**,
which is what a real radial city has at its centre. This is the root cause of the radial case's
converging near-parallel streets and its centre fold — not a tracing bug.

#### Chaotic / organic patterns — clarified, not scrapped

To correct an earlier ambiguity: **the goal was never wrong, only the placement in the pipeline.**
Irregular street patterns are a real requirement — much of the world looks like that — and they
stay in the design. There are two routes, and the cheap one comes first:

1. **`organic` field (recommended, v1).** Noise-perturbed θ with randomised bend angles produces
   most of the irregular look, it *is* a field, and **the existing `pf_streetgen.vfl` already
   traces it with no changes.** This is the lazy route and it covers the common case.
2. **`voronoi` (deferred, not cancelled).** A Voronoi layout is a graph read straight off cell
   boundaries — there is no streamline to trace, so it cannot be a *mode of the field generator*.
   It must **bypass S1/S2 and emit into S3 directly.** Worth having eventually for genuinely
   cell-based layouts, but honestly it has a tell: straight cell boundaries and 120° three-way
   junctions, which reads less like a medieval town than noise-warped grids do.

This is precisely why **S3, not S1, is the pipeline's contract point.** Any producer of a valid
graph is a first-class citizen: tensor trace, Voronoi, hand-drawn splines, imported data.

### S2 — Trace

Seeds → raw centrelines. Fixes for the diagnosed problems:

- **Integration:** RK2 midpoint minimum. Evaluate direction at `pos`, step half, re-evaluate,
  full step with the corrected direction.
- **Seeding:** a **priority queue**, not a jittered grid — see below. Plus explicit artist seeds.
- **Termination**, any of: left the domain · hit a hard mask · exceeded max length ·
  field went degenerate · entered a `plaza_radius` around a declared degenerate point ·
  **came within `snap_radius` of an existing trace** · turned more than `max_curvature` ·
  looped back on itself. **But see `d_lookahead` — most of these are soft, not hard.**
- **`d_sep` is driven by the density map**, not a constant. Chen 2008 varies streamline separation
  by density, which is what makes road density fall off toward the city edge instead of tiling the
  whole domain uniformly.
- Trace bidirectionally from each seed.

Output is deliberately still *raw* — messy is fine, S3 cleans it.

#### Dead ends are the exception, not the norm — and the fix is in the papers

**This is the single largest quality defect in the current build** (measured: §4d). Both canonical
papers address it directly and neither mechanism was implemented.

**Chen 2008 §6.1 — keep tracing past the stopping criteria:**

> Additionally, we improve connectivity by continuing the tracing for a distance **`d_lookahead`** to
> search an intersection with other hyperstreamline even when stopping criteria 4 or 5 is met.

So proximity-to-an-existing-trace and max-length are **soft** stops: on hitting one, keep integrating
up to `d_lookahead` looking for a real crossing. Connect if one is found; roll back to the soft stop
if not. **Our tracer treats them as hard stops, which manufactures a dead end every time.**

**Chen 2008 Figure 9 — interleave the two families.** The caption compares a network where major and
minor hyperstreamlines are traced *independently* against theirs, and notes that with their approach
the graph has **fewer dangling edges**. We trace the two families independently, in two separate
passes. That figure is a picture of our bug.

**Chen 2008 §6.2 — trace minors inside regions bounded by the majors.** Minor streamlines are seeded
and traced *within the faces the major network already closed*, not across the whole domain. A minor
street then cannot dangle: its region boundary terminates it. This also gives the street hierarchy
for free, and it makes S7's faces available earlier than the current stage order implies.

**Seeding is a priority queue.** Chen weights candidate seeds by distance to region boundaries, to
degenerate points, and to population centres, and pushes new candidates as tracing proceeds. That is
what produces even coverage without a grid's tell.

**Parish & Müller 2001 §3.3.1 — extend, don't dangle:**

> In traffic systems **the dead end road is the exception.** Most roads end when crossing other roads
> or circling back to themselves.

Their local constraints are explicitly **extend-to-connect**: an end near an existing crossing is
*extended to reach it*; an end near an intersecting street is *extended to form the intersection*.
This is a graph operation, so it lands in **S3** (below) rather than here — but it is the same
finding, and the two together are the whole answer.

Dead ends that remain after all of this are real cul-de-sacs and should be **deliberate** — a
`dead_end_ratio` the artist dials, not a leftover.

### S3 — Graph (the contract, and the missing 80%)

**Purpose: turn curves into a graph with real topology — planar *per layer*, not globally planar.**

Representation — decided, and it matters:

- **One geometry of polylines.** Each polyline is one **edge**.
- An edge's **first and last points are nodes**; interior points are **shape only**.
  This separates topology from shape, so a street can be reshaped without any topological change.
- **Nodes are shared (fused) points.** Two edges meeting at a junction share one point. Topology
  is therefore real Houdini connectivity, so `pointprims()` gives node degree and `neighbours()`
  gives adjacency **for free** — no parallel adjacency structure to maintain.

#### Layers — the change bridges force

A globally planar graph **cannot represent an overpass**: two crossing edges would be forced to
share a node, which is exactly what an overpass is not. Since bridges, tunnels and overpasses are
required, the model generalises:

- Every edge carries an integer **`layer`** — negative underground, `0` ground, positive elevated.
- **Intersection detection runs per layer.** Two edges that cross on *different* layers produce
  **no node**. Planarity is a per-layer invariant, never a global one.
- **This is exactly how OpenStreetMap models the real world** — a `layer` tag plus `bridge` and
  `tunnel` flags. A convention proven against the entire planet, and an open one.
- Layer changes are carried by **ramp edges** (`is_ramp`), whose endpoints sit on two different
  layers. A node joining different layers is a **`PORTAL`** — added to the junction vocabulary
  alongside CityEngine's terms.
- **New validation rule that only exists because of bridges: vertical clearance.** For every pair
  of edges crossing on different layers, the vertical gap must be at least `min_clearance`
  (~5 m road-under-road). Violations are reported, not silently permitted — nothing else in the
  pipeline would ever catch a bridge deck passing through the road below it.

**Sci-fi multi-level comes almost free from this.** Coruscant is many layers, no ground conforming,
and `sky_lane` networks — not a rewrite. Which is the entire argument for putting `layer` and
`network_type` in now: two attributes today, versus rewriting S3 later.

#### Networks are typed

Every edge also carries **`network_type`**: `road · rail · pedestrian · sky_lane · canal`. One graph
machinery; what differs per type is the cross-section template set, the junction rules (rail uses
switches, not four-way crossings) and the permitted layer range. **v1 implements `road` only** — the
attribute exists so rail and sky lanes are a configuration problem later, not a refactor.

Operations, in order:

1. **Snap** endpoints to nodes within `snap_radius`, **same layer only**.
2. **Extend dangling ends** — Parish & Müller's local constraints, applied to every degree-1 node
   before intersection. In order of preference, within `d_extend` (default ≈ `d_lookahead`):
   **(a)** an existing node in range → extend the edge to it and weld;
   **(b)** an existing *edge* in range → extend to the nearest point on it, split it, weld;
   **(c)** nothing in range → leave it, and the node keeps `DEAD_END`.
   Extension respects `max_curvature` and the hard masks — it may not tunnel through water to make
   a connection. **This step, not stub-pruning, is what removes dead ends.** Deleting a dangling
   street removes the symptom and the street; extending it removes the symptom and gains a block.
   ⚠️ **A connection is never refused. Ruled 2026-08-09 by Hannes, and it overrides the
   rails.** There are exactly two things that can go wrong when a new junction is created,
   and neither is a reason to leave a street dangling:

   | failure | the answer — NOT refusal |
   |---|---|
   | the new junction is too close to an existing one | **merge the two into one junction**, or **relax the nodes apart** until they fit. Two junctions 8 m apart *are* one junction |
   | two incident arms meet at a very shallow angle | **merge the near-parallel arms into one direction** before solving — §S5, adopted and not yet built |

   Everything currently refusing connections is a **missing capability wearing a rule's
   clothing**: `min_node_dist` stands in for node merge/relax, the degree-≥3 test stands in
   for corner geometry at a bend, and the angle rails stand in for arm merging. Measured,
   they are also mostly inert — `min_node_dist` 50 → 40 produced *bit-identical* output and
   `min_join_angle` has never fired on any case. Build the three capabilities and the rails
   go to zero.

   ⚠️ **Correction to an earlier conclusion in this document.** §4h read the spacing ceiling
   as evidence that dead ends need the majors-enclose-minors restructure (§3b row 3). That
   is wrong. Row 3 is worth building for the *hierarchy*, which is visibly absent, but it is
   not the dead-end fix — the dead-end fix is the three capabilities above.

3. **Merge or relax colliding junctions.** After extension, any two nodes closer than the
   space their junction surfaces need are **fused into one node** (all arms re-sorted around
   the merged centre) or **pushed apart** along their connecting edge until they fit,
   whichever preserves the street pattern better. `min_node_dist` becomes the *trigger* for
   this step rather than a veto on connecting.
4. **Intersect** every pair of **same-layer** edges; insert a node at each crossing and
   **split both edges**. This is the step whose absence broke everything before.
   Cross-layer crossings are instead recorded and **clearance-checked**.
5. **Cleanup**, and this is where "satisfying" is won or lost:
   - fuse nodes closer than `min_node_dist`
   - delete stubs shorter than `min_edge_len`
   - collapse pairs of edges that are near-parallel and closer than `min_street_sep`
   - enforce `min_angle` between edges at a node (merge or nudge below it)
   - prune the dead ends that extension could not rescue, iteratively, down to `dead_end_ratio`
6. **Validate:** every edge has exactly two node endpoints; no duplicate edges between the same
   node pair; no zero-length edges; **each layer is planar**; **all cross-layer crossings meet
   `min_clearance`**; every ramp connects exactly two distinct layers.
7. **Extract faces per layer** → these are the blocks (consumed by S7). Only ground-layer faces
   normally become buildable blocks; elevated layers produce blocks only in the sci-fi case.

⚠️ **Needs prototyping before committing:** vanilla Houdini has no single planarize-polylines SOP.
`Intersection Analysis` yields intersection points but stitching, splitting and robust cleanup
still have to be written. Expect this in VEX or Python with a spatial grid for the pairwise tests.
**This is the highest-risk stage and the one to build first** — everything downstream is
straightforward once the graph is trustworthy.

### S3b — Turns: a bend is not a junction, and gets its own solver

Added 2026-08-09 (Hannes). A node where exactly **two** streets meet is not a junction — it
is a street turning a corner. Ours are created by extend-to-connect welding two dead ends
together, and by the `d_lookahead` hook; measured, four exist, one of them a full 90° with
a 13.4 m half-width.

⚠️ **Do not look for these as degree-2 nodes.** `graph_polypath` merges the two edges into a
single polyline, so the corner stops being a node and becomes an interior shape vertex. A
pass keyed on node degree finds nothing — the audit confirmed **zero** degree-2 nodes in all
four cases. Detect them as **sharp interior turns** instead.

**Solve it on the CENTRELINE, not the kerbs, and keep it out of S5.** A turn needs no
junction patch: the road sweeps straight through. Replace the sharp vertex with a circular
arc tangent to both segments, resample, and the sweep follows it — the outer kerb comes out
at `R + halfwidth` and the inner at `R - halfwidth` automatically, which is what a real road
does. S5 stays at degree ≥ 3, where the patch construction is actually needed.

**Radius.** Hard floor: `R > halfwidth`, or the inner kerb radius goes negative and the
ribbon inverts — that *is* the fold `no_sweep_fold_after_trim` catches
(`halfwidth × tan(turn/2) > segment length`). Legible floor is about `2 × halfwidth`
(≈27 m on a 26.8 m arterial). Above that, default to the **class minimum curve radius** from
design speed, artist-overridable like everything else.

**This is the same operation as the curvature clamp** in §4f-4: resample → discrete
curvature → smooth → clamp to `1/R_min(class)` → re-integrate. A sharp turn is just
curvature far over the clamp, so one mechanism fixes both the polyline wobble that reads as
CG and the folding corner. Build it once.

#### ⚠️ The clamp must be a SOLVE, not a fixed sweep count — measured 2026-08-09

The first build (`50e51f3`) was an explicit Jacobi diffusion at ω = 0.5 with `iters = 200`
hardcoded, whose only early exit was "nothing is over the clamp any more". **That cannot tell a
converged answer from a stalled one, so a non-converged centreline shipped silently**, and an
audit found two separate failures behind it. Both are now fixed; the numbers are kept here
because they are the reason the design says *solve*.

**It did not converge on the example this section was written for.** Control: the plain 90°
arterial bend, 80 m + 80 m, W = 26.8, resampled 4 m. κ × R_min after 10 / 50 / **200** / 1000 /
5000 sweeps was 4.366 / 3.383 / **2.169** / 1.031 / 1.000. At the shipped 200 the delivered
radius was 26.8 / 2.169 = **12.4 m against a 13.4 m half-width** — inside this section's own
inversion floor. Cause: only vertices *already* over the clamp moved, so the corrected region
grew about one vertex per sweep and equilibrated in O(k²); spreading 90° over the ≥ 11 vertices
a 26.8 m R_min needs at 4 m spacing takes thousands.

**And the inversion was not theoretical.** Measured on case `F_bend` through the whole pipeline,
before and after, by offsetting the published centreline by its own half-width and asking whether
the offset ever runs backwards:

| | centreline R_min | half-width | inner kerb R | kerb steps running backwards |
|---|---|---|---|---|
| before | 12.35 m | 13.40 | **−1.05 m** | **2** |
| after | 26.69 m | 13.40 | +13.29 m | 0 |

A negative inner radius is the ribbon turning itself inside out, and two of its steps genuinely
reversed direction. ⚠️ Note that `no_sweep_fold_after_trim` reported **0 folds and a max ratio of
0.393** on that same geometry — it tests `h·tan(turn/2) / segment` per vertex, which a turn spread
over nine vertices never trips however tight the resulting arc is. It is not an inversion test and
must not be read as one.

**On a fold-back it diverged and collapsed segments to zero.** Same rig, a 30 m square returning
to within 4 m of its own start: 4.37 → 5.22 (50) → **22.7 (200)** → 5320 (5000), ending with a
**1.0e-6 m segment in `OUT_graph2`** — which is §4e-7's defect arriving from the other
direction. Cause: `phimax = (l1+l2) / (2·rmin)` is proportional to the local segment lengths and
the correction pulls the vertex toward the chord, which **shortens those very segments**. Smaller
`phimax`, larger correction, shorter still, with no lower bound and no re-parametrisation.

**What replaced it**, in `pfsg_turn_clamp_solve` (`pf_streetgraph.vfl`) — the wrangle now only
reads geometry and writes the verdict back:

- **Seed with the arc this section already specifies.** Each over-curved run is replaced by the
  circular arc of radius `R_min` tangent to the polyline on both sides, then the prim is
  resampled back onto its own point count. That is what removes the O(k²): **every prim in every
  shipped case is solved by the seed alone, in one sweep**, and the control rigs need 3 (90°),
  63 (135°, the worst turn 80 m legs can absorb) and 41 (a 300 m square ring).

  ⚠️ **Four details in that construction are load-bearing and the first version got all four
  wrong.** Two audits went through it and each found the frame broken a different way, both with
  the same signature — a clean arc that then jumps back the other way at one end.
  - **`T` is measured back from where the legs MEET**, not from the vertices either side of the
    run. Using `acc[a-1]` / `acc[b+1]` puts both tangent points a whole segment too far out and
    the circle is tangent to neither leg: the seeded 90° bend came out as a 7.67°/vertex arc and
    then 28.85 / 19.66 / 20.92° back the other way, κ × R_min 10.524 → 3.748 instead of → 1.
  - **The leg DIRECTIONS cannot come from the one segment either side of the run.** That is only
    right when the run is a single hard vertex — which every run in every shipped case happens
    to be. When the corner is *drawn* as an arc the run covers that arc, and those two segments
    are the arc's own first and last, tilted a whole vertex-turn off the straight leg. And
    because the circle was built *at* A it stayed tangent there whatever `d0` was, so the entry
    side could never show the error and all of it landed at B: **median 0.15 m out at B over
    8105 runs, p99 18.9 m, worst 89.8 m**, and a legal 135° arterial corner drawn at an 18 m
    radius that never converged. Each leg is now re-read from the *chord* of the polyline just
    outside where its tangent point lands, and the frame re-solved from it — the estimate and
    the tangent point converge in two rounds.
  - **The centre is on the bisector**, at `R_min / cos(φ/2)` from the corner along `d1 − d0`.
    It used to be chosen by scoring two perpendicular candidates on their distance to B, which
    assumes B is already on the circle — i.e. assumes the answer. That took the **mirrored arc
    on 99 of 8105 runs**, contained only because the solve keeps its best iterate.
  - **The arc must be polygonised finer than the spacing the prim ends up with**, because the
    whole ideal curve is resampled onto *n* points afterwards and that resample chords whatever
    polygon it is given. Sampling at the final spacing concentrates the entire turn on the arc's
    own vertices and the resample never sees a circle: at 1× a 135° bend settled at 1.0167 and
    **never converged**; at 4× it reaches 1.0008 in a single pass.

  Against the exact fillet (R = 26.8 tangent to both legs) F_bend's solved arterial is **0.0047 m
  max deviation over 520 m**, with the straight legs still straight to 0.0000 m — verified
  independently. The 1.004 residual is the chord artefact of 3.9 m sampling on R = 26.8, nothing
  else.
- **Spread each correction over the span it needs.** The excess turn needs `(φ − φmax)·R_min` of
  extra arc length, so the displacement is applied to that many vertices with a hat weight rather
  than to the single vertex.
- **Re-parametrise to uniform spacing every sweep.** *This* is the collapse guard: afterwards
  every segment is exactly `L/(n−1)`, so the feedback that drove a segment to 1e-6 m has nowhere
  to run. The explicit `length < minseg × nseg` test alongside it is a backstop and an audit
  confirmed **it has never fired** on any case or any control rig; setting `minseg = 0` changes
  no measured value. It stays because it is the one place a shrinking polyline can be caught
  before it ships, not because it is doing the work.
- **Keep the best iterate, not the last**, so a diverging sequence cannot ship its worst state.
  Stop on the residual (1.01, tighter than the check's 1.02 slack), on a 50-sweep stall, or at a
  200-sweep cap.
- **Report the verdict.** `turn_clamp_converged`, `turn_clamp_ratio` and `turn_clamp_sweeps` ship
  on every graph prim, and `centreline_curvature_within_class` fails on a non-converged prim even
  when the geometry it kept happens to read low.

**The fold-back is an infeasible input, not a solver failure, and saying so is the deliverable.**
R = 26.8 m needs 26.8 m of tangent run either side of a right angle and the sides are 30 m, so no
polyline through those pinned endpoints satisfies the clamp and is still a street. It now comes
out **bounded at its input value with a 2.83 m minimum segment and `turn_clamp_converged = 0`**,
at any budget up to 5000.

**Closed prims are solved where they can be, and flagged where they cannot.** The first build
skipped them (`primintrinsic("closed")`) while the check measured them, so the day the ring
closure (`011fdcb`) puts one back in the graph the check would have fired with nothing able to
clear it. The relaxation wraps instead. Control-tested on all three kinds, because **no case in
the suite produces a closed prim at all**:

| ring | κ × R_min | result |
|---|---|---|
| R = 120 m, legal | 0.223 → 0.223 | **bit-identical.** 0 sweeps, 0 points moved |
| 300 m square | 10.524 → **1.008** | solved, 41 sweeps |
| R = 20 m, round | 1.342 → 1.342 | **infeasible.** Flagged, 0 points moved |

⚠️ **The round ring is not a solver failure and the square one is not proof the mechanism works.**
A closed curve's total turning is 2π whatever its shape, so κ × R_min = 2π·R_min / L and *the only
way to lower it is to make the ring longer*. Every correction here pulls a vertex toward a chord,
which shortens. The square works because rounding four concentrated corners redistributes turning
without needing length; a round ring under the clamp has nothing to redistribute, and its nodes
are pinned by the graph, so it is infeasible for exactly the reason the fold-back is.
**An audit caught the first version of this control test using only the square** — the one closed
shape the mechanism happens to fix. If the ring closure ever emits a ring tighter than
`2 × half-width`, the answer is a larger ring or a smaller `turn_radius_scale`, not this solver.

⚠️ **This was the third mechanism in this project to ship green and unexercised at its design
amplitude**, after `offset` lot mode (§4e-6) and `max_fillet_fraction` (§4h-2). All five cases
only ever asked the clamp for a few degrees, so it read exactly 1.000 on all of them. The cure is
the same one every time: **case `F_bend`** in `tests/citygen/cases.py` puts a real 90° corner on a
real arterial through the real pipeline, and `turn_clamp_control_rig` runs the shipped wrangle on
the five inputs no case can reach — 135°, the infeasible fold-back, and all three kinds of ring.

#### Still unguarded after this pass — recorded, not fixed

- **The 1.0 m segment floor is asserted, not enforced.** `no_short_graph_segments` catches a
  short segment in the published graph, but nothing upstream prevents one. An audit built the
  input: three drawn streets with two junctions **0.8 m apart** — above `graph_fuse`'s 0.5 m
  tolerance — ship a 2-point, 0.8 m prim, and the check correctly fails on it. `graph_prune`
  only kills *dead-end* stubs under 13 m, and the clamp cannot help because a 2-point prim has no
  interior vertex to move. **The cure is §4c's unbuilt node merge/relax, not the clamp.** No case
  produces one today.
- **`pfsg_clear_of_vertex`'s push is still a single jump** to `acc[i] ± minseg`. It now refuses
  to push when that would land within `minseg` of the *next* vertex, so it can no longer create a
  worse sliver than the one it is fixing — but it does not re-solve, it just declines. Reachable
  only through a sub-4 m resample segment, i.e. through the bullet above.
- **Adjacent over-curved runs starve each other.** `avail` is allocated first-come-first-served
  along the prim, so of two 90° corners 20 m apart the first takes `R = 16 m` and the second gets
  `R = 4 m` — an inner kerb radius of −9.4 m *in the seeded state*. The relaxation clears it and
  no case has more than one run per prim (every shipped run is a single vertex), but the seed on
  its own is not safe for closely-spaced corners.
- **A latent boundary inconsistency in the same function.** With the cut landing exactly on a
  vertex, the `atstart` branch selects the segment *after* it (deliberate — see the comment on
  `pfsg_tangent_at_length`) while the mirror branch selects the one *before*, so at `d = 4.00` on
  a 20 m / 4 m polyline `atstart` returns 4.000 and `atend` returns 5.000. Measure-zero in `d`,
  and **not fixed on purpose**: the seam is at 0.0001 m and `s5j_solve`'s cut is monotone by
  construction (§`50e51f3`), so changing which segment holds a cut is exactly the class of change
  that cost C 54 junction self-intersections last time. It wants its own pass with the seam
  measured either side.

### S4 — Classify

- **Hierarchy:** `highway · arterial · collector · local · alley`. Derived from the S2 major/minor
  distinction plus graph centrality, with artist override. Drives which cross-section template
  each edge gets by default.
- **Junction typing** per node, adopting CityEngine's vocabulary:
  `STREET · CROSSING · JUNCTION · JUNCTION_ENTRY · DEAD_END · FREEWAY · FREEWAY_ENTRY · ROUNDABOUT`
  Derived from degree, incident hierarchy and angles. Written to `connectionStart`/`connectionEnd`
  on each edge — the vocabulary the intersection solver switches on.

### S5 — Intersections

**Hannes' own solver (`attribwrangle62` / `attribwrangle77` in `cityGen.hip`) is the basis. It is
correct, and it predates any research.** Do not replace it — extend it.

Its method, per adjacent pair of incident streets around a node: solve where the two **kerb lines**
intersect, place a fillet centre on the bisector, find the tangent points where that circle meets
each kerb, and emit the junction polygon with arc points between them.

```c
angle = acos(dotProd) * dirSwitch;
alpha = piHalf - angle;  beta = piHalf - alpha;
sideB = (widthB/2)/cos(alpha);
sideA = (widthA/2)/sin(beta);
newPoint = center + dirB*sideA + dirA*sideB;   // exact kerb-line intersection
```

> ⚠️ **A trim-back-by-a-radius approach cannot work and should not be attempted again.** A single
> scalar pull-back per node is wrong whenever incident widths or angles differ, which is almost
> always: it gaps or overlaps by construction. Measured on the generated city it left 1,380 of
> 1,399 overlaps clustered at junctions. Solve the kerb intersection; do not approximate it.

#### What the literature adds

Neither Chen 2008 nor Parish & Müller build intersection surfaces (see the reference README). The
useful sources are StreetGen 2018 and A/B Street's design notes.

1. **The formula above is a miter join.** `(width/2)/cos(alpha)` is exactly the stroke-rendering
   miter offset, and it blows up as the angle shallows — the classic **miter spike**. The standard
   fix is a **miter limit with bevel fallback**: when miter length / width exceeds the limit,
   replace the spike with a straight bevel. SVG's default limit of 4.0 bevels below ~29°. This is
   the principled cure for the shallow-angle junctions that produced absurd corner points.
2. **Trim per pair, not per node.** A/B Street trims each road back to where a perpendicular from
   the collision point meets that road's centreline — a different distance for every road at the
   junction. Our sweep should end at the tangent points the solver already computes.
3. **Corner radius from street class, not a constant.** StreetGen derives the turning radius from
   road type → design speed → radius (empirical SETRA function). `cornerRadius = 3` becomes a
   per-class default the artist overrides — which is §1.3 applied.
4. **Angular sort needs a distance tie-breaker.** Sorting junction points purely by angle produces
   **bowtie** polygons when incident roads curve. A/B Street hit this and fixes it with distance.
5. **Robust fallback when trig degenerates.** StreetGen finds the arc centre by buffering each axis
   by `width + r` and intersecting the buffer boundaries, taking the candidate nearest the node.
   Slower, but it survives cases where the closed form does not.
6. **Do not boolean-union road polygons.** A/B Street reports it as unreliable for three-way
   intersections. Ruled out.

#### The invariant that was violated: **every corner is an arc, always**

Added 2026-08-09 after measuring the shipped build. **Roughly half of all junction corners are
straight chords rather than arcs** (§4d), which is exactly the "some do the expected round
transition but some just connect straight" complaint.

The cause is our own construction, not a class of geometry that resists filleting:

1. Each incident street is trimmed to a cap, and the corner arc is then **re-fitted through the two
   cap corners** — but those are not the fillet's tangent points, so the required arc frequently
   cannot span the chord between them.
2. `pfsj_arc_centre_through` papered over that with `r = max(radius, halfchord)`, which silently
   grew the radius (the "radius is too big" symptom).
3. Fixing *that* introduced a guard, `arad > halfchord + 1e-4`, which silently **drops to a straight
   line** whenever the class radius cannot span the chord (the "some are just straight" symptom).

Both symptoms are the same error. **A fillet tangent to both kerb lines exists for any non-collinear
corner** — the construction never fails, so no fallback is legitimate. The rule:

> **Compute the fillet first; trim each street to its own tangent point.** The cap corner *is* the
> tangent point. Never fit an arc through cap corners that were placed by some other rule, and never
> substitute a chord when the fit fails — a failed fit means the caps are in the wrong place.

Radius clamping stays, but it clamps the *radius* against the shorter incident segment (a fillet may
not eat more than `max_fillet_fraction` of a street), and the clamp changes the tangent points too.
Below the miter limit the corner becomes a **bevel** — a deliberate, straight, documented case, and
the only one.

#### Two rules the design left open, decided 2026-08-09

Both were unspecified, and the audit showed the code was silently inventing an answer.

1. **`max_fillet_fraction` = 0.4** (a default, artist-overridable). It was named here and never
   implemented: `pfsj_fillet` says *"the radius is CLAMPED to what the junction can actually hold"*
   and line 83 is `radius_used = radius;`. ✅ **Implemented §4h**, as a `max_run`
   argument bounding the tangent run. Unclamped, cuts reached 26 m, **three streets were
   consumed entirely** while their junction kept a mouth for them — a paved stub opening onto
   nothing — and thirteen more lost over half their length. Note the threshold mismatch this
   exposes: `graph_prune` deletes stubs under 8 m, but a junction needs ~22 m of clearance, so a
   street can survive pruning and still be eaten by its own corners.
2. **At a mixed-class corner, the LESSER street sets the radius.**
   ⚠️ **Reversed 2026-08-09, same day, after the civil-engineering sweep (§4f).** I first decided
   "the wider street wins", reasoning that the turning radius follows the largest vehicle. That is
   backwards and two independent sources say so. The arterial's own traffic goes *straight through*
   the junction; only the turn **onto the smaller street** sizes the corner. Published class-based
   shortcuts key off the minor road — ≥7.6 m at minor cross streets against ≥9.1 m at major ones —
   and the one published procedural implementation uses `r = min(r1, r2)` outright. "Wider wins"
   would have inflated every arterial-to-local corner in the city.

   The real chain is **design vehicle → swept path → required effective radius → minus what
   adjacent parking and bike lanes already provide = kerb radius**, where the design vehicle is
   *the least manoeuvrable vehicle that routinely uses the street*. So the correct model is a
   per-node `design_vehicle` override (`car` · `su_truck` · `bus` · `articulated`) that wins over
   class, with `min(class)` as the fallback. One comparison and one attribute.

   Our 4–9 m band is fine — it sits inside every published urban range checked.

   **And it must stay an artist-facing default, not a derived constant.** The strongest evidence:
   a random forest trained on ~14,000 kerb arcs measured off real streets still lands 1.69 m median
   error. If that cannot predict a corner radius from street attributes, neither can we.

⚠️ `every_corner_is_an_arc` currently asserts the *old* rule (the first-sorted street's class), so it
must be re-pointed at these two before it can verify them. Same for
`trim_metric_is_consistent`: once both nodes measure axially it should assert the geometric seam —
**the trimmed road end lies on the mouth's cap segment** — not the difference between two metrics.
✅ **Both re-pointed §4h.**

#### Three constructions adopted from the civil sweep — 2026-08-09

Spec, not background. All three are prerequisites of the solver working at all, and each
removes a whole failure class rather than patching an instance of one.

1. **Extrapolate both kerb lines far beyond the node before intersecting them** (~100 m, a
   default). Two kerbs at a shallow angle meet a long way out; solving on the trimmed
   segments finds no intersection and the corner silently degenerates. This is the general
   cure for the shallow-angle family, and it is almost certainly the same root cause as the
   arc-fit bug fixed in `f3878b5`.
2. **Merge incident edges within `merge_angle` (default 20°) into a single direction before
   solving.** Two nearly-parallel arms at one node are not two corners — treating them as
   two produces a corner with almost no angular room, which is what inverts the boundary
   polygon. Merge first, solve once, then attach both edges to the merged mouth.
3. **A dead-end cap is the perpendicular cross-section at the node, intersected with both
   kerb lines** — not an offset pushed past the last point. ⚠️ This is the cap that was
   attempted twice and reverted in `8c739d3`; the attempts failed because the construction
   was being guessed. It also fixes §S7's "lots cut long at dead ends", because the block
   boundary then meets the road at the same place the sweep ends.

**Keep the true tangent arc.** The reference implementation uses a cubic Bézier of varying
curvature and treats "radius" as a pushback distance; ours is tangent to both kerb lines
with an exact radius, which is the better primitive for a film target. Take the scaffolding,
not the corner.

**Curb return, validated.** Commercial corridor tools ship exactly three corner types —
chamfer, circular fillet, three-centred arcs — solved per quadrant. Ours is the circular
fillet, so the construction in this section is standard practice. Two caveats worth
recording: the published tables have **no simple-curve entry** for large articulated design
vehicles at 90°, which need arc-plus-taper or three-centred curves (a v2 concern); and a
curb return is properly the **offset of the design vehicle's inner rear-wheel path** at
~0.6 m clearance, of which our arc is a fittable approximation.

`min_junction_angle` now has published anchors: **90° preferred, avoid below 75°, 60° floor.**

#### Higher-degree junctions — untested, and structurally unreachable from the field

**Degree-5+ has never been generated once, and degree-3 exists only in the hand-drawn case** (§4d).
This is not luck: two *perpendicular* eigenvector families can only ever cross at 4-way. Tensor
tracing alone cannot produce a 3- or 5-way junction, so the solver's hardest cases are entirely
unexercised.

Consequences for the plan:

- The Parish extend-to-connect rule in S3 (b) — extend to the nearest point *on an edge* — is the
  main producer of **T-junctions (degree 3)** in a tensor-traced city. Dead-end repair and 3-way
  coverage are the same work.
- **Degree 5+ needs a deliberate test case**, hand-drawn, in the check suite — a star of five and
  six streets at uneven angles and mixed widths. Add it to `tests/citygen/cases.py`.
- Angular sort with the distance tie-breaker (item 4 above) is only actually stressed at degree ≥ 5.
  Assume it is wrong until a test says otherwise.

#### Plazas and roundabouts at degenerate points

Every declared degenerate point (S1) with streets terminating around it becomes a **plaza** node: a
disc of `plaza_radius`, with the incident streets trimmed to its edge and their kerb lines filleted
into the plaza boundary instead of into each other.

**There are three of these, not one, and they are one construction with three radius defaults** —
a disc with the incident kerbs filleted into it:

| Node | Default radius | Notes |
|---|---|---|
| **plaza** | artist-set | at a declared field degeneracy |
| **roundabout** | inscribed circle **21–67 m diameter** by type, so ~10–33 m radius | central island + one-way annular carriageway |
| **cul-de-sac bulb** | **13.7–14.6 m** radius, with 15.2 m transition fillets | terminates a dead end deliberately, instead of leaving a stub |

⚠️ **`plaza_radius` currently defaults to 60 m, which is a 120 m disc — 2–4× a real roundabout.**
Reset it against the table above. The cul-de-sac bulb also gives §S2/§S3 somewhere to put the dead
ends that extend-to-connect legitimately cannot rescue: a designed terminus rather than a stub.

Known-hard cases still to prototype: degree ≥ 5, junctions between very different widths, junctions
on a grade, and dual-carriageway short-road clusters (A/B Street collapses these into a single
intersection).

### S5b — Bridges, tunnels, ramps

A distinct construction stage, not a parameter on the road builder. The Unreal sample carrying
separate `freeway_geometry.hda`, `freeway_pointcloud.hda` and `freeway_utilities.hda` is direct
evidence that this is its own subsystem — worth opening before designing further.

Per-edge inputs: `layer`, `is_bridge`, `is_tunnel`, `is_ramp`, and `terrain_op`
(`cut_fill` · `none` · `excavate`).

#### Where bridges go — cost-driven routing (Hannes' technique, adopted)

Hannes has already prototyped this and it is the right approach: use Houdini's **Find Shortest
Path** SOP (native, no dependency) over the network with **cost attributes** carried on the
underlying field — construction cost, travel expense, and potentially traffic volume. Least-cost
routing then decides *whether a bridge is worth building at all*, which is what real road planning
actually optimises. A bridge appears where spanning is cheaper than going around.

This makes bridge placement a **consequence of the cost field** rather than a hand-placed
exception, and the cost weights become artist-facing parameters (§2 of `citygen.md`) — the artist
tunes "how much do I hate building bridges" instead of placing each one.

Cost inputs worth exposing: terrain slope and elevation delta · water and gorge crossings ·
`land_use` (demolition cost through dense zoning) · existing network reuse · detour length.
Same machinery routes **tunnels** (cost of boring vs. climbing) and **highways**.

- **Bridge** = deck (the swept cross-section, unchanged) + **piers** (the vertical columns holding
  the deck up) + parapets/railings.

  **Pier placement** — not an open question, just the work: space piers along the span at
  `pier_spacing` (a default the artist overrides), then reject any position that collides with what
  is underneath — the road being crossed, water, or any exclusion mask — and stretch the
  neighbouring spans to skip it, subject to `max_span_length`. This is why real bridges have
  irregular pier spacing.

  If no valid arrangement exists, the bridge is **invalid** and the standard validation policy
  applies (§1.3): default `block`, the artist can switch it off globally, and a warning is
  persisted on the element. No special-casing.
- **Tunnel** = portal geometry at each mouth + bore. Since rendering is offline, the interior only
  needs to exist when a camera sees it — build it on demand, not always.
- **Ramp** = a normal swept street whose `layer` changes end to end, plus retaining walls or
  embankment where it meets grade.
- `terrain_op` is what stops a bridge from flattening the valley it spans — see Contract 3 in
  [`citygen.md`](citygen.md). **Without it, every bridge destroys its own reason for existing.**

### S6 — Cross-section → road geometry

**Template** — our own format, an ordered list of typed elements across the street, kerb to kerb.
Beyond Typicals is a *look-and-feel* reference only; nothing is imported.

**Stored as Houdini geometry, not JSON.** One **point per element**, ordered along the cross-street
axis, carrying `elem_type`, `width`, `height`, material and behaviour flags as point attributes.
Reasons this beats a JSON file:

- no parser, no schema drift, no second format to maintain
- readable from VEX, Python, expressions and wrangles with zero glue
- inspectable in the geometry spreadsheet, so debugging is free
- caches as `.bgeo` like everything else; save as **`.geo`** when a text-diffable file is wanted,
  since that format is already JSON-based
- the template *is* geometry, so it can be authored, previewed and swept directly

Global/nested template settings that are not per-element live in **detail dictionary attributes**
on the same geometry.

Element types: `sidewalk · lane · bus · bike · parking · median · verge · turn · tram · shoulder`.
Per element: `type`, `width`, `height` (kerb offset), plus material/tint and behaviour flags
(`drivable`, `walkable`, `parkable`) that traffic and scatter will read later.

Construction: walk elements left→right accumulating x, emitting two profile points per element at
its height. Where consecutive heights differ, the shared x with two heights **produces the kerb
riser for free** — no special-casing. Sweep the profile along the edge; the sweep carries
`elem_type`, `elem_index` and a normalised cross-street coordinate onto the road surface, so every
downstream consumer selects by *type* instead of guessing from position.

Also write the resolved summary attributes onto the edge (`streetWidth`, `sidewalkWidthLeft`,
`sidewalkWidthRight`, `laneWidth`) **and the template reference itself**, which is what makes an
existing city re-editable rather than regenerate-only.

⚠️ **Design for variation along a street now, even though v1 won't implement it.** Real streets
gain a bus lane near a stop and lose parking at a junction. So the template is stored **per
segment, not per street**, and transitions between differing neighbours are a named future stage.
Storing it per street would be the cheap choice today and an expensive migration later.

### S7 — Blocks

Closed faces of the S3 graph, inset by the relevant cross-section widths. A block is the polygon
bounded by street kerb lines, not centrelines.

⚠️ **The block boundary is the *road* boundary, not an offset of the centreline.** Two defects in
the shipped build both come from treating the inset as a straight per-edge offset:

- **Lots stick into intersections.** At a node the boundary must follow **S5's fillet arc**, because
  that arc *is* the kerb there. A straight offset cuts the corner and the resulting lots overlap the
  junction surface. The block polygon and the junction polygon share an edge by construction —
  derive the block boundary from the same kerb polyline S5 already builds, rather than recomputing.
- **Dead ends are cut long.** The current cap runs `streetWidth × streetWidth/2` past the terminal
  node, which overshoots by half a street width and eats into the block. The cap belongs at the
  street's end plus the sidewalk width, closed with a proper end cap — and once S3 extends dangling
  ends (§S3 step 2) most of these stop existing at all. *Two fix attempts were made and reverted
  (commit `8c739d3`); do not retry the cap in isolation — do it with the fillet-derived boundary.*

Also: the inset scale must be resolved **per incident edge at each node**, not `max(streetWidth)`
over the block. Using the max opened a 5.9 m gap between roads and lots where widths differed.

### S8 — Lots

Subdivide blocks into buildable parcels, with artist control, plus **viability checks**: minimum
area, minimum street frontage, minimum width at the frontage, maximum aspect ratio, slope limit.
Non-viable parcels become courtyard, parking, planting or are merged with a neighbour.

#### ⚠️ Voronoi is wrong for lots. Rewritten 2026-08-09.

The shipped build subdivides blocks with `voronoifracture`. **No source in the reference library does
this, and three independent ones agree on rectangular recursive subdivision.** This is the cause of
"the lots look very weird".

**Parish & Müller 2001 §4.1:**

> We assume that most of these allotments are **convex and rectangularly shaped**. The system
> therefore **forbids the creation of concave allotments**. A block is divided using a simple,
> **recursive algorithm that divides the longest edges that are approximately parallel** until the
> subdivided lots are under a threshold area […] all allotments that are **too small or do not have
> direct access to a street are discarded.**

**CityEngine** ships exactly three subdivision algorithms, and they are the right three to copy as a
*vocabulary* (§1.4 — names and behaviour, no dependency).

**The Unreal sample** (`resources/citygen/unrealCitygen/otls/City_Layout.hda`, 987 nodes) does the
same family: `determinig_ideal_block_size_X/Z` → `foreach_POINT_MAKE_SPLIT_X` →
`foreach_POINT_MAKE_SPLIT_Z` → `foreach_end_ISLAND_SUBDIVISON` → `SUBDIVIDED_CITY_LAYOUT`. Axis-aligned
recursive splitting. Confirmed by inspection, not memory.

#### The three subdivision modes — both of the first two are required

| Mode | How | Produces | Status |
|---|---|---|---|
| **`recursive_obb`** | minimum-area **oriented** bounding box of the block; split at the midpoint of its largest edge; recurse until under `target_area` | rectangular, street-facing, back-to-back lots — American/suburban and most downtown blocks | **v1, default** |
| **`offset`** | inset the block by `lot_depth` to make a **street-facing ring** plus an interior remainder; subdivide the ring with lines **orthogonal to the offset**; the remainder becomes courtyard or is subdivided separately | **European perimeter blocks** — continuous street frontage, shared party walls, courtyard behind | **v1, required** |
| **`skeleton`** | straight-skeleton partition; every lot reaches a street; lot sides perpendicular to the adjacent road | irregular and organic blocks where every parcel must have frontage | v2 |

> **Both `recursive_obb` and `offset` ship in v1.** Hannes, 2026-08-09: *"it is very important that we
> are also capable of generating the european looking lots as well."* `offset` is the mode that
> produces them — the courtyard block is not a variation of OBB splitting, it is a different
> algorithm, and the interior remainder is a first-class output (courtyard / garden / parking), not
> a discard.

The mode is **per block**, resolved through the normal override cascade (`citygen.md` §2.1): a
`land_use`/`district` default that the artist overrides per region or per block. A city mixes them —
that is largely what makes a city read as a *place*.

Splitting rules shared by both, all defaults:
`target_area` · `area_variance` (identical parcels are the tell) · `min_frontage` ·
`lot_depth` · `split_jitter` on the midpoint · `snap_to_frontage` so splits run perpendicular to the
street edge rather than to the OBB when the two disagree.

**Discard/merge rules, from Parish:** below `min_area`, below `min_frontage`, or **no street access
at all** → not a lot. Convexity is enforced, not hoped for. Street access is tested against the
**block's street-facing edges**, and those must be the kerb boundary from S7 — measuring frontage
against a filled polygon returns ~0 everywhere inside it and passes everything.

⚠️ **Knowledge gap, still open:** the rigorous treatment is **Vanegas et al. 2012, "Procedural
Generation of Parcels in Urban Modeling"** (CGF), which we do not have. It is the peer-reviewed
version of the offset/skeleton pair above. **Acquire before building `skeleton`**; `recursive_obb`
and `offset` are specified well enough by Parish + CityEngine to build now.

---

## 4c. Implementation status — 2026-08-09

**Corrected 2026-08-09 after an independent audit. Two entries below were marked "done"
and were not.** The suite passing is not the same as the feature working — every defect in
§4e was invisible to it.

⚠️ **Status vocabulary, and it is enforced.** *done* = an independent agent audited it on
the current build. *implementer-verified* = measured and proven, but by whoever built it.
*not started* means what it says. Three features were reported "done" in this project that
had never worked; two of those were never audited and one was audited too late.

### Overnight run — 2026-08-09/10

| Item | State | Evidence |
|---|---|---|
| **Ring closure in the radial city** (`8a83baa`) | **implementer-verified** | The two bidirectional halves each soft-stop on the *other half's* occupancy claim, so the seam always lands on an occupancy cell boundary — proved by sweeping `min_street_sep`: 130 → gap at x −7.90, 110 → −71.46, 90 → −39.65, each the boundary that setting creates. Gap was 4.877 m at (−7.90, −99.65), far past the 0.5 m fuse tolerance. Closed on a shared point behind two gates (seam ≤ 2.5 steps **and** traced length > 10× seam; the first rejects a genuinely-ended street, the second stops a stub welding into a triangle). Verified by connectivity walk, not by eye: 5 ring edges, every ring node degree 2, one walk consumes all 5 and returns to start. Suite 23 → 18 failing. **Its audit never reported.** |
| **S7 — block boundary IS the kerb; PolyExpand2D deleted** (`4c53af5`, `0156c30`) | **done** — audited | `city_is_fully_paved` **0 m² on all five** (was A 757, D 919, C 7). `lots_clear_of_junctions` **0 on all five** (was up to 558 m²/junction on E). `lots_tile_blocks` passes everywhere. Seam 0.0071 → **0.0001 m**. `blocks_capback` and `blocks_expand` gone |
| **S3b — turns, built as the curvature clamp** (`50e51f3`, rebuilt `492fe7c`+) | **done** — rebuilt after audit, and the rebuild audited in turn. See §S3b "the clamp must be a SOLVE" | The 1.000 below was real but meaningless: no case asked the clamp for more than a few degrees. On a plain 90° arterial bend it delivered a **12.4 m radius against a 13.4 m half-width**, and on a fold-back it diverged to a **1.0e-6 m segment**. Now a seeded residual solve: F_bend 2.170/9-over → **1.004/0**, delivered R 12.4 → 26.7 m, and **every shipped prim solves in 1 sweep**. Infeasible inputs are *reported*, not shipped. A second audit found the seed's tangent points a segment out and its arc polygonised too coarsely; both fixed, both now covered by `turn_clamp_control_rig` |
| **S3b — the folds it did fix** (`50e51f3`) | **implementer-verified** | `no_sweep_fold_after_trim` **0 folds on all five** (C had 2) — that part was `pfsg_clear_of_vertex`, not the clamp, and §4c already records it |
| **Ring closure gate re-derived from cell size** (`011fdcb`) | **implementer-verified** | Defaults proven byte-identical by hashing every vertex. Audit running |
| **Sagitta gate replaced by a ceiling on the seam; the floor's closed-form bound** (2026-08-10) | **implemented, unverified** | Acting on an independent audit of `f0edcc6`. Max accepted chord 145.90 → **65.85 m**, chords > 100 m 12 → **0**, sole rejector 5 → **25**; defaults byte-identical over 26 digests; suite 17 failing with no baseline movement. The sweep that measured it is committed as `tests/citygen/closure_gate.py` — see "The sagitta gate is gone" below |
| Node merge/relax, shallow-arm merge, dead ends, majors-enclose-minors | not started | — |

**Suite 23 → 15 failing.** Verified on a clean tree, and A rendered whole-city: continuous
paving, no strip along the drawn street, lots meeting the road at every junction.

⚠️ **A brief of mine was wrong and the implementer caught it.** I attributed C's sweep folds
to sharp turns. They turn **0.3° and 4.0°** — they were §4e-7's 0.028 m and 0.22 m terminal
segments, left where `s5j_trim`'s cut lands just short of a resample vertex. Fixing that by
moving *points* re-opened the S5 seam to 0.48 m; it had to be fixed by moving the *cut*.
S3b was still worth building, but it was not what fixed the folds.

⚠️ **Known weakness in the ring gate, recorded rather than buried.** The ground truth needs
a 52 m chord welded at sagitta 3.44 while a 108 m chord is refused at 3.83 — an **11% window**
with the threshold mid-window. Cell adjacency, seam/cell ratio and gap angle were all tested
as alternative discriminators and none separates. A relative (radius-scaled) limit may be
the right answer. Two of the five gates rejected nothing across 12,417 streets and are
unproven.
**SUPERSEDED 2026-08-10 — see "The sagitta gate is gone" below.** The sagitta family was tried
and is worse, not better: as a discriminator its window is 2.7%, not 11%, and radius-scaling
is precisely what stops it being a bound (`seam²/8r` permits a chord growing as `√r`). The
deviation slot now holds a flat ceiling on the seam.

⚠️ **Known follow-up from the ring fix:** the two halves are radially offset ~1.6 m where
they meet, so the closing segment introduces a 21.3°/14.8° pair of turns against a 3.28°
median. It does not fold (ratio 0.28 against a threshold of 1.0). **§S3b's curvature clamp
is the cure** — do not patch it separately.

#### The loop-closure gate, per-gate — measured, and two entries in `80dc19c` were wrong

The commit message for `80dc19c` recorded a ledger of which closure gates actually reject
anything. Two of its entries do not survive re-measurement. Corrected here, and this table
— not the commit message — is the ledger. Measured at the tracer output over a **distinct**
518 config sweep (2 fields × a sep/step ladder, deduplicated as a set: the earlier sweep's
two blocks overlapped and double-counted 40 of its 584), **12,792 traced streets**. A gate is
*proven* when it is the **sole** rejector of at least one street, which is the same thing as
"deleting it would let a weld through".

Three columns, all on the same 518 configs: **pre-floor** is `80dc19c`, **`f0edcc6`** is the
magnitude-floor-plus-sagitta build, **now** is this pass. The whole table is reproduced by
`hython tests/citygen/closure_gate.py --full --table`, so it does not have to be re-derived
by hand a fourth time.

| Gate | pre-floor | `f0edcc6` | now | Status |
|---|---|---|---|---|
| `chord_forward \|\| seam ≤ close_road_width` | 7 | **0** | **0** | **unproven.** The 7 it rejected alone are exactly the 7 the magnitude floor recovers; the retrograde welds that carry the damage all fail a structural gate as well. Kept because it is a real failure mode, not because this field family reaches it |
| `\|net turn\| ≤ 2π` (one lap) | 2 | 1 | 1 | proven |
| neither half ended on a junction | 19 | 4 | 4 | proven |
| `close_seam_cells = 1.42` | 12 | 9 | **2** | proven, but **largely subsumed** — the invented-road ceiling below now refuses most of what it used to catch alone. Worst accepted weld sits at seam/cell **1.405** |
| `tracelen > 10 × seam` | 8 | 9 | 9 | **proven — `80dc19c` recorded it as never firing alone and that is refuted.** Worst accepted weld sits at 10.85 |
| `close_max_end_angle = 60` | **0** | **0** | **0** | **unproven — `80dc19c` recorded it as "proven reachable" and that is refuted.** At the config it cited (radial, plaza_radius 0, domain 120, res 250, step 8, `min_street_sep` 25.6, `seed_spacing` 50) `trace_1_1_1` failed **two** gates, the chord test and the end angle, read off the wrangle's own flags. `chord_forward` subsumes it: a >60° end mismatch nearly always implies a backwards chord. It does become the sole rejector at that one config *after* the floor goes in, but across 12,792 streets it still rejects nothing alone |
| `close_min_pts = 8` | 0 | 0 | 0 | unproven, kept |
| ~~`sagitta ≤ close_road_width/2`~~ → `seam ≤ 5 × close_road_width` | 0 | 5 | **25** | **proven, and the sagitta form it replaces was not what its own row claimed.** See below — `f0edcc6` recorded it as "proven by re-deriving it", and re-deriving a threshold is not proving it |

The magnitude floor under the chord test is the other half of this pass. `chord_forward` is a
sign test with nothing under it, so it refused the case it was written for: seven closures —
all radial, r ≈ 100, 0.987–1.000 of a lap — with seams of **0.19 / 1.17 / 1.17 / 1.94 / 1.94 /
7.08 / 7.52 m**. `graph_fuse` (tol3d 0.5) and `graph_stitch` (proxtol 0.75) are both below
that, so what shipped was **two dead ends 1–2 m apart**, the defect class §S2 and §4d rank as
the worst this project has. Both bounds still come off one number, `close_road_width` = 14.4 m,
so the value and its rationale cannot drift apart: a seam narrower than one full width is the
two ends of the same road overlapping, welded regardless of chord sign, and past five widths
the closure is a street in its own right (below).

⚠️ **Two things this paragraph used to say about the floor were wrong, and the floor survives
both.** Corrected 2026-08-10 after an independent audit.

1. **"A backwards chord can double no more road than its own seam" is false.** Measured: at
   seam 7.516 the doubling is **191.5 m² = 13.3 m of road, 1.77× the seam**; at 8.412 it is
   212.6 m². The bound is **2× the seam**, not 1×.
2. **"Seven closures, all radial, r ≈ 100" is an artefact of the 518-config grid.** Swept at
   1 m step resolution it is **61 floor-admitted welds on 8 distinct rings, r 76–385**, and
   the largest retrograde seam is **8.412 m** (radial, `min_street_sep` 22, `step` 30,
   `trace_1_2_1`, r 285). Both of those are now pinned as adversarial configs in
   `tests/citygen/closure_gate.py` so a coarse grid cannot hide them again.

**The floor's real justification is a closed form, and it needs no sweep at all.** Project the
end-to-start vector onto the start tangent: it splits into an `overshoot` along the road and a
`lateral` across it, with `overshoot² + lateral² = seam²`, and the chord runs back over the
overshoot before the seam closes it. So

```
doubled pavement = (overshoot + seam) * (w - lateral),   overshoot² + lateral² = seam²
```

Predicted against rasterised on the four worst welds: **213.5/212.6, 203.2/208.9, 191.8/191.5,
58.8/48.0 m²**. Maximising under the floor's own `seam ≤ w` puts the worst case at
`lateral = 0`, `overshoot = seam = w`:

> **worst case = 2·w·w = 414.7 m² at w = 14.4 = 28.8 m of doubled road** — and it is always
> one 14.4 × 28.8 m patch at the seam, never a run along the ring.

Worst actually observed over 520 configs: **213.5 m² predicted, 213.6 m² rasterised**, at the
sep 22 / step 30 adversarial config. Half the bound.

**Followed to the output, not stopped at the tracer.** A weld at the tracer is worth nothing
if the ring still ships with two loose ends, so each of the seven was walked in `OUT_graph2`
as well. Before: six of the seven shipped **two degree-1 nodes** — a dead-end pair — and the
ring walk broke after 3 to 123 of ~160 nodes. After: **all seven walk the complete cycle,
zero degree-1 nodes**, 159–163 nodes / the same number of edges each.
⚠️ One correction to my own claim while doing it: *"nothing downstream rescues it"* is true of
six of the seven, not all. The 0.193 m seam at sep 65 / step 3 is inside `graph_fuse`'s 0.5 m
tol3d and was already being welded there. The other six sit in 1.17–7.52 m, above both `fuse`
0.5 and `stitch` 0.75, and those are the ones that shipped broken.

⚠️ **"Exactly 7 recovered / 5 removed" counted parameter settings, not geometries.** Those 7
are **2 rings** seen at 7 sep/step combinations; the 5 are one ring at five more. Read as
independent evidence they are n = 12; they are n = 2. Every count in this section is a count
of *(field, sep, step, street)* rows unless it says otherwise.

#### The sagitta gate is gone. The seam is bounded instead — 2026-08-10

`f0edcc6` replaced `close_max_dev = 13.4` with `sagitta ≤ 0.5 × close_road_width` (7.2) and
this doc recorded it as **"proven by re-deriving it"**. Re-deriving a threshold is not proving
it, and an independent audit took the gate apart on its own terms:

- **Its decision boundary is 147.68 m accepted against 151.62 m refused — a 2.7% window**,
  *narrower* than the 11% window recorded two paragraphs above as a known weakness. It went
  the wrong way.
- **It is not monotone.** The same r ≈ 385 ring flips between closed and **two dead ends 155 m
  apart** as `step` walks 12 → 14, then back to closed at 18.
- **Its rationale was vacuous.** "The offset at which the chord stops overlapping the road it
  stands in for" — but neither the 147.68 m secant it accepts nor the 151.62 m one it refuses
  doubles any pavement (0.8–51.9 m² *on both sides of the line*), because there is no road on
  that arc to double. That road was never traced. The closure invents 142–162 m of straight
  road either way.
- **And a sagitta is not a bound at all.** `seam²/8r` grows the permitted chord as `√r`: at
  r = 2000 it would allow 339 m. It still shipped 12 welds with chords > 100 m and a maximum
  accepted seam of 145.90 m.

**The hole it was covering is `seam ≤ 1.42 × min_street_sep`, which at sep 180 permits 255.6 m
of invented road.** A radius-scaled limit cannot patch that — see the bullet above; the
suggestion two paragraphs up that "a relative (radius-scaled) limit may be the right answer"
is refuted.

**So bound the seam, which is the quantity that measures invented road:** a closure lays down
exactly `seam` metres the field never traced. The gate is now

```
seam <= 5.0 * close_road_width          // 72.0 m
```

Five widths because that is the tightest round multiple the committed ground truths allow and
it lands in measured empty space:

| | |
|---|---|
| largest must-weld ground truth | 62.32 m = **4.33 widths** |
| gap in the accepted-seam distribution | **(65.85, 77.52)** — a **17.7%** window |
| 5 × 14.4 | **72.0 m**, 9.3% above the gap's floor, 7.7% below its ceiling |
| the window the sagitta test lived in | 2.7% — this one is **6.6× wider** |
| next gap up | (112.42, 142.54), 26.8% — wider still, but 112 m is 7.8 widths, a street |

It is flat in `r` and flat in `min_street_sep`, which is exactly what the sagitta form was not,
and it is the **sole rejector for 25 streets of 12,792** against the sagitta bound's 5.

⚠️ **Unproven inside the gap.** The data fixes the gap's *edges*; nothing in it distinguishes
4.6 widths from 5.4. If a future field family puts a must-weld ring at 70 m the number moves,
and the honest record is that only `> 62.32` and `< 77.52` are measured.

⚠️ **The 20 refusals are a trade, not a free win, and the real cure is elsewhere.** Those welds
rasterise as a *chamfer* — a complete ring with one flat spot — not as a doubling, so refusing
them replaces a flattened ring with **two dead ends 77–146 m apart**. All 20 are `trace_1_2_0`
or `trace_1_2_1`, the r 283–389 outer rings, at 0.92–0.96 of a lap. A gap that size is a street
that genuinely ended and belongs to **§S3 extend-to-connect** and the **§S5 cul-de-sac bulb**,
not to a loop-closure gate papering over it. Neither state is good; this one at least does not
lie about what it is.

##### Before and after, per criterion

Same 518-config grid, 12,792 traced streets, plus 2 pinned adversarial configs (+89 streets).

| | `f0edcc6` (sagitta) | now (invented-road) |
|---|---|---|
| accepted welds | 325 | **305** |
| median accepted seam | 11.81 m | 11.56 m |
| **max accepted seam** | **145.90 m** | **65.85 m** |
| welds with chord > 100 m | 12 | **0** |
| welds with chord > 50 m | 27 | **7** |
| welds with chord > one road width | 127 | 107 |
| invented road permitted at sep 180 | 255.6 m | **72.0 m** |
| invented road permitted at r = 2000 | 339 m | **72.0 m** |
| retrograde welds admitted by the floor | 9 over 520 configs, **max seam 8.412 m** | unchanged — the floor is untouched |
| worst doubled pavement | 213.5 m² predicted / 213.6 m² rasterised, against a closed-form bound of 414.7 m² | unchanged |
| multi-lap welds | 0 | 0 |
| welded loops that self-intersect | 1 (sep 23 / step 20, 0.50 m² lobe) | 1 — same one, tracked, 0 new |
| ground truths 31.25 / 52.24 / 62.32 | weld | **weld** |
| defaults | B 1294/19/1294, C 1441/28/1443 | **byte-identical, 26 digests** |
| suite | 17 failing | **17 failing**, no baseline movement |

C's r ≈ 100 ring still closes at defaults, walked in `OUT_graph2`: **158 nodes / 158 edges,
every node degree 2, one walk consumes all 158 and returns to its start, 0 degree-1 nodes.**
⚠️ `OUT_graph2` carries **no closed prim** even when the ring is closed, and since `6dc1ad5`
the whole graph is one connected component — so neither `isClosed()` nor a component count
proves anything here. The ring has to be selected by proximity to the traced ring (a radius
band also catches every radial spoke crossing it) and then walked.

#### ⚠️ The road-under-chord metric was ill-posed. Use the pavement deficit

The `under` metric — count already-traced road within one road width of the closing chord,
excluding a **Euclidean ball** of the same radius around each chord end — reported **0 m under
any chord**. The same idea with an **arc-length** exclusion of the same 14.4 m reports **265 of
325 welds with road under the chord and a minimum distance of 1.00 m**. Opposite answers, same
geometry: the number was an artefact of the exclusion's *shape*, so the metric was not merely
loose, it was ill-posed. The earlier note in this section about picking the band scale
carefully was solving the wrong problem.

Use instead, for any simple closed centreline:

```
doubled pavement = w * L - area(Minkowski(closed loop, w/2))
```

The `w`-neighbourhood of a closed curve has area exactly `w·L` — the two offset curves' area
terms cancel on a closed loop — so any shortfall is pavement laid down twice. **No exclusion
parameter and no blind scale**: it sees a 0.5 m² sliver and a 414 m² doubling alike, and it
agrees with the closed form above to 0.1 m² on the worst weld in the sweep. Reference
implementation: `pavement_deficit` in `tests/citygen/closure_gate.py`, committed as a check.

| Item | State |
|---|---|
| S5 fillet-always (§S5 "every corner is an arc") | **done, verified independently** — circle fit residual ≤ 2e-5 m, radii exactly the class radii, tangency exact in the continuous sense |
| S5 winding-based inward offset | **done** — A `selfx_junction_surface` 4 → 0 |
| S1 degenerate points + plaza ring (§S1, §S5 plazas) | ⚠️ **NOT done.** The exclusion works; **the ring is deleted before it ships** (§4e-2). The C gains came from the seed/trace exclusion alone |
| S8 `recursive_obb` + `offset` lots (§S8) | ⚠️ **partial.** Voronoi is gone and the structure is right, but parcels are ribbons up to 31:1, non-convex blocks produce bowties, and `offset` fails `lots_tile_blocks` (§4e-4,5,6) |
| `land_use` written (§4d) | **done** |
| S7 dead-end cap at the node, not past it (§S7, §S5-3) | **done §4i-1** — `blocks_capback`; unpaved area B 4,265 → 0 m², C 9,143 → 18 |
| S7 block boundary from the fillet (§S7) | not started — and now blocking **two** defects, not one: the fillet overrun (~10 m² a corner) and the collinear-average strip (§4i-3, 757 m² in A) |
| S5 cul-de-sac bulb (§S5 plazas) | not started — the deliberate terminus for the dead ends the rails cannot rescue (§4i-2) |
| S3 extend-to-connect (§S3 step 2) | ⚠️ **case (a) only. Case (b), the branch that creates junctions, is DEAD CODE and has never executed once** — §4g-1 |
| S2 `d_lookahead` (§S2) | **works**, and is the sole source of every new degree-3 junction — but leaves a 0.53 m hook, §4g-3 |
| S2 `d_lookahead` (§S2) | **done** — soft stops 4 and 5 in the `trace` wrangle. Priority seeding and density `d_sep` still not started |
| Row 3 majors-enclose-minors (§3b) | not started |
| Rows 5/6 mask + density inputs (§3b) | not started |
| Row 8 bridge flag rule (§3b) | not started |
| Degree-5+ test case (§S5) | not started |

Suite: **6 failing → 2**. Nothing regressed against baseline. But see §4e — the suite is
measuring the wrong things, and both remaining failures were misdiagnosed.

---

## 4f. Civil-engineering sweep — 2026-08-09. What it changes

Full write-up and sources in `resources/citygen/README.md` §4b, organised by stage, with a
verified / computed / snippet / failed ledger. The five that change the design:

1. **There is an open-source implementation that builds a filled junction polygon** — the one
   thing eight game and VFX sources declined to do. Three constructions transfer straight into S5:
   **extrapolate both kerb lines ~100 m before intersecting them** (removes the entire
   "no intersection at a shallow angle" failure class); **merge incident edges within 20° into one
   direction before solving** (the structural cure for the inverted boundaries we hit); and for a
   dead end, take the **perpendicular cross-section at the node intersected with both kerb lines** —
   which is exactly the cap reverted twice in `8c739d3`. Where we are *ahead*: their corner is a
   cubic Bézier of varying curvature and their "radius" is only a pushback distance. **Our true
   tangent arc is the better primitive for film — keep it, take their scaffolding.**
2. **Our curb return is standard practice, for cars.** Commercial corridor tools ship exactly three
   corner types — chamfer, circular fillet, three-centred arcs — solved per quadrant. Ours is the
   middle one, so §S5 is validated. But the published tables have **no simple-curve entry at all**
   for large articulated vehicles at 90°; those need arc-plus-taper or three-centred curves. A
   curb return is properly defined as an **offset of the design vehicle's inner rear-wheel path**
   at ~0.6 m clearance; the arc is a fittable approximation of it.
3. **S6 is already a corridor, just with every setting at its trivial value** — one region, no
   targets, no daylighting. Two cheap upgrades: add **point / link / shape codes** (three string
   attributes, and the vertex code is what yields kerb, crown and frontage lines as longitudinal
   polylines — precisely what §S7's block boundary needs); and adopt the open interchange format's
   **`width(ds) = a + b·ds + c·ds² + d·ds³`**, which turns §S6's deferred "cross-section varies
   along a street" from an architecture change into a schema change. Keep deferring daylighting: it
   varies point count per station and would force sweep → loft.
4. **Clothoids barely matter — we were worrying about the wrong artefact.** The whole visible
   signature of a missing transition curve is a lateral shift of `Ls²/(24R)` ≈ **0.33 m** on a
   100 km/h, R = 400 m arterial, spread over 56 m. Urban streets use normal crown with **no
   superelevation**, so there is no runoff for a spiral to host anyway. What actually reads as CG,
   in order: **curvature noise in the traced polyline** (loudest by far), missing superelevation on
   fast curves, no vertical curves, radius below class minimum, clothoids last. And the cheap fix
   yields them free: resample → discrete curvature → **smooth κ** → clamp to `1/R_min(class)` →
   re-integrate. Any linear κ ramp that falls out *is* an Euler spiral, with no Fresnel maths.
5. **Lot subdivision has three upgrades over Parish's recursive split.** An **area-targeted slide
   line** — slide a fixed-direction line along the frontage until the enclosed area hits target,
   a ~20-iteration bisection replacing our midpoint split — attacks the 31:1 ribbons (§4e-4)
   directly. Add **vertex snapping to block corners**, which on its own removes much of the
   procedural look. And **Vanegas 2012 is no longer blocking** (§S8): the straight-skeleton method
   is documented step by step on a free page.

Smaller, all with published anchors now: `min_junction_angle` is **90° preferred, avoid below 75°,
60° absolute floor** · our 5 m vertical clearance is right for road-over-road but **7.11 m** is
required over freight rail, which also imposes a lateral exclusion — make it a per-obstacle lookup ·
bridges should adopt a **support-line abstraction** `(station, skew, role, transverse_length)`,
which subsumes `pier_spacing`, gives skew free, and fixes uniform-spacing-plus-rejection silently
doubling a span · the **open/spill-through abutment** (bank seat, 1.5:1 fill cone, wingwalls,
approach slab) is what makes an overpass read as built · there are **three node constructions, not
one** — plaza, roundabout and cul-de-sac bulb — all "disc plus fillets into it", one construction
with three radius defaults.

⚠️ **`plaza_radius = 60 m` is 2–4× too large.** Real roundabout inscribed circle diameters run
21–67 m *total*, so 60 m as a radius is a 120 m disc. Fix with the roundabout default.

---

## 4e. Independent audit findings — 2026-08-09

Found by a fresh agent, none of it visible to the committed suite. Ordered by severity.

1. **Roads and junction patches interpenetrate at every junction. SEVERE.**
   ✅ **Fixed §4h-1** — and the root cause was bigger than the units mismatch below:
   the mouth was also out of SQUARE with the road by up to 30.9 degrees.
   `s5j_solve` places the mouth at `c + d*dist` — a **straight-line axial** distance along
   the first resample segment. `s5j_trim` cuts the street at `dist` measured as **arc
   length** along the polyline. Same number, two different metrics. Because arc length ≥
   chord, the road always ends *short of* its mouth and never clears the fillet it was
   trimmed for. Mean error A 0.05 m · B 0.28 · C 0.58, max **3.34 m**; 65 of C's 119 ends
   are over 0.25 m out. `intersectionanalysis` on the **merged** city: **102 / 529 / 863**
   points. **The suite cannot see this** — `selfx_junction_surface` tests the patch alone
   and `selfx_roads` the roads alone; nothing tests the union. Fix both to one metric and
   add a merged-city self-intersection check.
   *Latent alongside it:* `swl`/`swr` are assigned from `nOut`, which flips at a street's
   **end** node, so sidewalk sides are swapped there. Hidden only because all six shipped
   templates are symmetric.
2. **The plaza ring never reaches the output.** The tracer emits it correctly (r = 60
   exactly), but the stop test `break`s *before appending* the point that entered the
   plaza, so streets end at r = 62.5–65.9 — a 2.5–6 m gap that `graph_fuse` (0.5 m) and
   `graph_stitch` (0.75 m) cannot close and S3 extend-to-connect does not yet exist. The
   ring ends up with no degree-≥3 node, so `graph_drop_orphans` **deletes it**. What ships
   is four 26.8 m arterial stubs dead-ending in mid-air and a 22,111 m² built-up disc
   inside the declared plaza radius. Append the entry point, and seed the ring into the
   graph as a real connected component.
3. **`pfsj_fillet` has no radius clamp**, despite its own comment claiming one and §S5
   specifying `max_fillet_fraction`. Line 83 is `radius_used = radius;`. Cuts reach 26 m;
   **3 streets are deleted entirely** by `s5j_trim`'s `ts+te >= L*0.98` while the junction
   still carries a mouth for them — a paved stub opening onto nothing. 13 more are over
   half consumed. Note the threshold mismatch: `graph_prune` kills stubs under 8 m but the
   junction needs ~22 m of clearance.
   *Also:* the corner radius is taken from `street_class` of whichever street sorts first
   by `atan2`. **98% of B's and 100% of C's corners join different classes**, so the same
   node gets a 9 m fillet on one side and 4 m on the other, arbitrarily.
   *Also:* `pfsj_bevel` was deleted but §S5 still specifies a bevel; the replacement clamps
   `K` **radially**, moving it off both kerb lines, so the "straight kerb run" would no
   longer be along a kerb if it ever fired.
4. **`recursive_obb` produces ribbons, not rectangles.** OBB aspect ratio: median ~4:1,
   p90 9:1, **max 31.5:1**; A's largest parcels are 6.2 × 62.1 m. The force-street-access
   swap recurses with no depth limit, driving frontage down to `min_frontage` while never
   touching depth. §S8 names *maximum aspect ratio* and *minimum width at the frontage* as
   viability tests; neither is implemented, so 10:1 ribbons ship with `lot_viable = 1`.
5. **Sutherland–Hodgman on non-convex blocks makes bowties.** `pfsl_clip`'s comment claims
   a mildly concave block degrades gracefully. **Every block is non-convex** (2/2, 9/9,
   13/13, up to 291 reflex vertices). 8 genuine two-lobe parcels in C, **7 flagged
   viable**; 62 lots carry duplicated vertices. `lots_tile_blocks` passes because the
   S-H bridge has zero area — exactly the defect class numbers hide.
6. **`offset` mode fails `lots_tile_blocks`** (0.006 / 0.003 / 0.003 against a 1e-4
   tolerance) **and the suite never runs it.** Cause: `ring[k]` uniformly resamples the
   contour by arc length, chording across every block vertex and losing 207–1071 m². The
   perimeter-block structure itself is correct. Courtyards up to 27,130 m² ship as one
   parcel because "subdivided separately" was never implemented.
7. **C `no_downward_faces` = 4 is not plaza residue.** `s5j_trim` snaps the straddling
   point onto the cut but leaves the neighbour microns away — 0.036 m and 0.022 m segments
   against a 7.2 m half-width, so the sweep frames cross and the ribbon folds. A and B are
   clean by luck. Latent everywhere.
8. **C `selfx_roads` = 12 is not plaza residue either.** 9 of the 12 are two degree-1
   streets ending 6.7 m apart at (247–255, −95…−99) and driving through each other. A
   snap/extend defect, i.e. §S3 step 2.
   ⚠️ **Re-diagnosed 2026-08-09 while building §S3 step 2; the second sentence is wrong.**
   The two ends meet at roughly **90°**, not head on: edge 19 is a 14.4 m `local` arriving
   from the south-west, edge 37 a 26.8 m `arterial` arriving from the south-east. Joining
   them yields a **degree-2 corner**, and S5 builds a junction patch only at degree ≥ 3,
   so the two swept ribbons still overlap. Extend-to-connect cannot fix this and must not
   try — an early version *extended* edge 19 straight past edge 37's dangling end to a
   target beyond and took the overlap from 9 points to 26. The corridor rail in
   `graph_extend` now refuses it and the count is back at 12. **The real fix is corner
   geometry at degree-2 nodes (S5/S6), not the graph.**
9. **Lots in intersections, quantified:** 18.8 / 23.2 / **37.9 m² per junction**, worst
   single case 126 m². Confirms §S7 is visibly wrong, as designed-not-yet-built.
10. Minor: `every_corner_is_an_arc` only checks that arc *points exist*, so it cannot
    catch a wrong radius · scratch **attributes** leak onto `OUT_lots` (`lot_reject`,
    `is_block`, `centre`, `area`, …) and `no_scratch_groups` only checks groups ·
    `s5j_surface` still starts with two `// nudge` lines · `pfsl_frontage` credits a full
    edge when only its midpoint is near the boundary · `arc_steps = 5` leaves 0.11 m of
    flat-to-arc error on a 9 m corner.

---

## 4g. Second audit — the dead-end build, 2026-08-09

**Verdict: not sound to build on.** Findings below, worst first; the junction-spacing
ceiling that follows was measured against a mechanism that turned out not to be running.

1. **Extend-to-connect case (b) is dead code.** ✅ **Fixed §4h-3** — and closing it
   exposed a second hole in the same rail. Its validator loop is not told which prim
   the landing point lies on, so the extension is rejected by the *adjacent segment of the
   very edge it is landing on* — one resample step away, inside `min_node_dist`. True for
   any `min_node_dist` ≥ ~8 m. Confirmed three ways: `graph_extend` adds 2 prims in B and 2
   in C, both case (a); ablating `d_extend` changes junction count by 0; and a faithful
   Python port finds 0 case-(b) connections, rising to B 2 / C 7 when the target edge is
   exempted. **Every new degree-3 junction came from `d_lookahead` alone.**
2. **Both surviving connections are dead-end-to-dead-end welds** — i.e. the degree-2 corner
   §4e-8 says must not be attempted. The mechanism manufactures the defect it documents.
3. ✅ **Fixed §4h-4.** **`d_lookahead` appends the crossing point after the last integration
   point instead of replacing it**, leaving a residual sub-step. Any residual in **(0.5 m, 0.75 m]** falls
   between `graph_fuse` tol3d 0.5 and `graph_stitch` proxtol 0.75: stitch splits twice,
   fuse cannot weld, and the junction node lands 0.53 m off the arterial with a 90° hook.
   One of nine new junctions hit it, at (-198.94, 90.56). One-line fix in the tracer.
4. **Most of the claimed wins are the rider domain fix, not the mechanisms.** B's
   `lot_aspect_ratio` gain is 82% domain fix, C's is 98%. The overshoot was 239 m, not
   130 — `nx = ceil(W/cell) + 1` over-allocates a whole extra cell, on +x/+z only.
5. **B `selfx_city_merged` +14 is a net figure** hiding −73 from the domain fix and +87 from
   the mechanisms — ~12 crossings per new junction in B, ~23 in C. Mostly the §4e-1 seam,
   but **11 points in B and 36 in C are mid-block**: lots overhanging the carriageway.
6. **Unreported regression: C `no_sweep_fold_after_trim` 2 → 3**, caused by the mechanisms.
7. **Degree-2 corners are not nodes at all.** `graph_polypath` merges the two edges into one
   polyline, so the corner becomes an interior shape vertex. §4e-8's amendment is still
   wrong: an S5 pass keyed on node degree would find nothing. Size it by sharp interior
   turns instead — 1 shipped → 5 now, and the graph is manufacturing them.

### The junction-spacing ceiling — measured 2026-08-09, and re-read after the audit

Found while building §S2 `d_lookahead` and §S3 step 2. **It is the thing that limits how
far dead-end elimination can go, and it is an S5 defect, not a graph one.**

Control test, smallest scene where the answer is known: one straight arterial, two
perpendicular T-junctions on it, varying the gap between them.

| junction gap | `selfx_junction_surface` | streets consumed entirely |
|---|---|---|
| 70 / 60 / 55 / 50 m | 0 | 0 |
| 45 m | 0 | **2** |
| 42 m | **10** | 2 |

A **lone** T-junction is clean at 90°, 60°, 45° and even 30°, and a 4-way crossing is
clean. Degree and angle are not the problem — **spacing is**. The cause is §4e-3: with no
radius clamp, `pfsj_fillet`'s pull-back is `r/tan(theta/2)`, unbounded, so two junctions
closer than roughly `2 × r/tan(theta/2)` trim away the street between them.

The shipped build never saw this because the tracer's `min_street_sep` of 130 m left **no
junction pair closer than 55.9 m (B) / 72.3 m (C)**. Every mechanism that adds junctions
walks straight into it, and the correlation is exact:

| B_grid config | junction pairs < 50 m | `selfx_junction_surface` |
|---|---|---|
| shipped | 0 | 0 |
| + `d_lookahead`, no spacing rail | 1 | 39 |
| + extend-to-connect, no spacing rail | 13 | 219 |
| both, with the rail | 0 | 0 |

So `min_node_dist` (already named in §S3 step 4) is enforced as a **rejection rail** in
both producers, defaulting to 50 m. **Clamp the fillet radius (§4e-3) and that 50 m comes
down, and the remaining interior dead ends can be connected.** Until then the rail is what
keeps the suite honest, and it is the single largest reason dead-end elimination stops
where it does.

⚠️ **Superseded by §4h.** The rail leaked, and the leak — not the spacing — was what
produced the 42 m table above. It is now 40 m.

---

## 4h. Third pass — the seam, the radius rule, the two dead-end mechanisms. 2026-08-09

Fixes for §4e-1, §4e-3, §4g-1 and §4g-3. Every number below is from
`tests/citygen/run_scene_checks.py` on a scene built from scratch.

**1. The seam was a ROTATION, not just an offset (§4e-1).** `s5j_solve` put the mouth at
`c + node_tangent * dist` while `s5j_trim` cut at `dist` as arc length. The position error
was up to 3.42 m, but the larger error was angular: the polyline turns up to 30.9° over the
trim distance, so the road's terminal cross-section and the mouth cap were rotated relative
to each other and a triangular hole up to 4.3 m deep opened at every **curved** arm — 184 m²
missing in B, 200 in C. Straight arms had no gap, which is why it read as random.

Moving only the mouth does not work and was tried twice: the kerb corner, the fillet
tangents and the arc are all solved from the node, so the cap moves and the corner it must
meet does not. **The whole corner solve now runs in the road's own frame** — `orig`/`fdir`
are the street's polyline point and tangent at its current cut, and `pfsj_corner_lines`
intersects the two kerb lines from those instead of from one shared node. Iterated 4×,
which converges because the frame only changes at all when the cut crosses a resample
segment. Seam error, road terminal cross-section against mouth cap corners:
**A 0.70 → 0.0004 m · B 4.15 → 0.007 · C 4.88 → 0.035 · D 0.70 → 0.0004.**

**2. The radius rule, and the clamp that was never there (§4e-3, §S5).** `min(rA, rB)` per
corner, and `pfsj_fillet` now takes `max_run` — `max_fillet_fraction` (0.4, new parameter
`s5j_params_max_fillet_fraction`) of the shorter incident street. Measured on the T-junction
at (-14.52, -35.65): back edge **39.8 → 34.80 m**, both corners at r = 4.0 instead of 9 and 4
— **that is `min(rA, rB)` alone, not the clamp.**

⚠️ **The clamp does not fire on A–D at all.** An audit disabled it and got bit-identical
output on every case; the worst tangent run reaches 51–53% of the cap. So it shipped
unexercised, which is the §4e-6 pattern again — and the §4g plan to bring `min_node_dist`
below 40 m *by* clamping the fillet is still resting on a mechanism no case had ever run.

**Case E** (`E_short_t`) exists to run it, and is sized from the clamp condition, which is
narrower than it looks. The run is `r/tan(theta/2)` and must exceed `0.4 x` the shorter
street, while the whole cut — kerb corner **plus** run — must still leave that street alive
and above `graph_prune_min_edge_len`. A shallow angle does **not** work: at 30° the miter
alone reaches 54 m of a 60 m arm and eats it before the clamp is approached. That is §S5's
bevel, a separate unbuilt thing, and it is now measured: **a 30° arm is 90% consumed by its
own corner.** A perpendicular T of local streets does work — `r` = 4 × 2.5 = 10 m wants 10 m
of run, `0.4 ×` the 20 m arm allows 8, and the 15.2 m cut leaves 4.8 m standing. E reports
`corner_r` 8.0 against a class radius of 10.0, seam 0.0, `selfx_junction_surface` 0.

**3. Extend-to-connect case (b) now runs (§4g-1)** — the validator exempts the LANDING prim,
not the extending one. But exempting the extending prim from `min_node_dist` is itself a
hole, and closing case (b) walked straight into it: the street a dead end belongs to is the
most likely thing to already cross the target near the landing, *because that is how the
dead end got over there*. C placed a junction 21.4 m from an existing one — 43 junction
self-intersections and a 21 m street trimmed to twice its own length. The extending prim is
now exempt from the corridor and crossing tests only.

**4. `d_lookahead` replaces the last integration point with the crossing (§4g-3)** instead of
appending after it, whenever the residual is under `graph_stitch`'s 0.75 m.

**5. The city output is WELDED at the seam** (`city_weld`, fuse 0.01 m). Closing the seam
*raised* `selfx_city_merged` at first — A 102 → 106 — because a road that now touches the
junction registers coincident-but-unwelded edges as crossings where a road that stopped
0.7 m short touched nothing. Junction↔road crossings drop A 92 → 8 · B 397 → 83 ·
C 615 → 142 with no other change.

⚠️ **The control test first quoted here proved nothing** and the audit caught it: two
coplanar quads *overlapping by 50%* also score 0, because **Intersection Analysis is blind
to coplanar overlap** and only sees transversal crossings. That is a standing limitation of
`selfx_city_merged`, `selfx_roads` and `selfx_junction_surface`, worth knowing before
trusting any of them — though the obvious candidate is clean: 0 of 5,148 (B) and 0 of 5,756
(C) road-corridor sample points fall inside a lot polygon.

The evidence that does settle it is a tolerance sweep: the drop **saturates at 0.5 mm**
(A 106 → 26 at 0.1 mm → 22 at 0.5 mm → 22 at 10 mm; C 646 → 240 → 206 → 187), so ~95% of
what the weld removes is sub-millimetre coincidence between surfaces that are meant to be
coincident. Welding is the completion of the seam. Its real cost, also measured: a 0.01 m
weld does erase genuine interpenetration below ~10 mm, and it removes 4 sub-0.03 m² kerb and
sidewalk slivers in C — which are the same short-segment slivers behind C's
`no_sweep_fold_after_trim`, so it tidies a symptom it does not fix. No lot point welds to a
road point: the only mixed clusters are `OUT_roads | s5j_surface_fuse`, at exactly 6 per
mouth.

**6. Rails re-defaulted, from the sweep** (all three measured, not guessed):

| parameter | was | now | why |
|---|---|---|---|
| `graph_params_min_node_dist` | 50 | **40** | keeps `selfx_junction_surface` at 0, the seam under 0.05 m and C's sweep folds at 3. 45 → C roads 30 / seam 0.92 m; 40 → 13 / 0.035; 35 → 14 / 0.060; 30 → 33 / 0.383 |
| `graph_params_max_curvature` | 45 | **25** | an extension onto a dead end makes a degree-2 corner and S5 builds no patch there, so the whole turn shows as two ribbons overlapping. At 45°, C keeps 28 road self-intersections and 5 folds; at 25°, 13 and 3 |
| `graph_prune_min_edge_len` | 8 | **13** | the §S5 threshold mismatch, closed. B's two mouths-onto-nothing were a 12.0 m and a 9.5 m dead-end stub carrying 32.5 m and 15.8 m of trim |

**Result.** `selfx_junction_surface` 0 on all four · `every_mouth_has_a_road` 0 on all four ·
`selfx_city_merged` **A 102 → 22 · B 543 → 89 · C 794 → 187 · D 86 → 12** · dead ends
**B 24 → 21 (8 → 5 interior) · C 39 → 35 (25 → 20 interior)** · suite 24 → 19 failing.

**One failure mode found and NOT fixed: the frame refinement can limit-cycle.** At C's
(58.58, −247.33) a cut straddles a polyline vertex at arc length 11.9766: reading the frame
at 11.9473 returns 11.9932, reading it there returns 11.9473, forever — a period-2 cycle of
amplitude 45.9 mm that 14 iterations does not damp. The mouth then carries one segment's
tangent while the road ends on the next one's, 0.151° away, which on a 26.8 m arterial is
the **0.0353 m** that `trim_metric_is_consistent` reports: 71% of tolerance, 1 of 135 ends,
and bounded only by (vertex turn) × (half-width) — so C passes by luck, not construction.
Clamping the cut into its frame's own segment fixes it (0.0353 → 0.0066) and was **tried and
reverted**: it leaves a 1 mm terminal segment whenever the cut lands near a vertex, which
folds the sweep — C went to 10 junction self-intersections and 6 downward faces. Any real
cure has to damp the iteration or re-seat the frame without shortening the terminal segment.

**Still open, and honestly so:** C `selfx_roads` 12 → **13**; the extra point is at the same
degree-2 corner family §4e-8 describes, which needs corner geometry at degree-2 nodes, not
another rail. C `lot_aspect_ratio` max 15.1 → 25.6 (with `over` 216 → 206) on a different
block decomposition — an §S8 defect, unchanged in kind.

**Two checks were re-pointed**, both as §S5 said they would have to be:
`trim_metric_is_consistent` now asserts the geometric seam (the road's terminal
cross-section IS the mouth cap segment, both endpoints within 0.05 m) because the units
mismatch it used to measure no longer exists; `every_corner_is_an_arc` asserts `min(rA, rB)`
clamped by `max_fillet_fraction` for the corner's own two streets, against both the fitted
circle and the solver's emitted `corner_r`. Its fitted-radius term is compared against the
conditioning bound `resid / (1 - cos(sweep/2))`, because a fillet that turns 5° has a 4 mm
sagitta and a 2e-5 fit residual moves the fitted radius by 15 mm — three of C's corners read
as wrong radii when nothing was wrong. `dead_ends` is now a recorded measurement.

**Two things the audit found in passing**, neither fixed: `elem_type` is a **point**
attribute on `OUT_roads` and only a prim attribute on `s5j_surface`, so
`no_downward_faces(skip_types=("kerb",))` skips kerbs on the junction surface and never on
the roads — conservative, so nothing is hidden, but half the skip is inert. And at the T
junction the **lot plate runs over the junction's far sidewalk band**, because the block
boundary still comes from the street corridor rather than the fillet — §S7, designed and not
yet built, and in a close-up it is the most visible remaining wrongness in the build.

---

## 4i. Fourth pass — the dead-end holes, the rail ceiling, the collinear average. 2026-08-09

**1. The holes at every dead end. FIXED.** `blocks_expand` is a `polyexpand2d` whose local
inside/outside scale is the point attribute `offsetscale`. PolyExpand2D caps a **dangling**
polyline end by that same local scale, so at every degree-1 node it pushed the block boundary
`streetWidth/2` **past** the node while the road sweep stops **at** it (`s5j_solve` skips
degree < 3, so trims stay 0). The result is a `streetWidth × streetWidth/2` rectangle that
nothing paves: **359 m² per arterial dead end, 104 per local street**, every centroid
`streetWidth/4` beyond its node.

Fixed by a new prim wrangle, **`blocks_capback`**, between `blocks_offsetscale` and
`blocks_expand`: pull each dangling end of the block-side polyline back along itself by exactly
its own `offsetscale`, so the cap PolyExpand2D then adds lands on the road's own end cap.

Two details that are not optional, both measured:

- **Trim by arc length, consuming the points passed.** `blocks_resample` has already split the
  street into ~3 m segments, so a 13.4 m pull-back crosses four of them; moving the terminal
  point alone doubles the polyline back on itself.
- **Snap the last surviving interior point onto the end tangent.** PolyExpand2D's square cap is
  perpendicular to the *final segment*, so without this the cap is rotated by the street's turn
  over the pull-back and the lot plate pokes into the carriageway. C_radial: **156 m² of
  residual gap without the snap, 18 m² with it.**

Whole-city unpaved area inside the corridor: **A 1,503 → 757 m² · B 4,265 → 0 · C 9,143 → 18 ·
D 1,651 → 919 · E 0 → 0.** A's and D's residue is item 3 below, not a dead end.

⚠️ **`omitendcaps` is not the knob** — control-tested; it splits the output into two prims and
leaves the overshoot.

**The check that would have caught it is now committed: `city_is_fully_paved`.** It rasterises
the shipped city onto a 1 m grid and asserts nothing inside the corridor's outer boundary is
left unpaved. `lots_tile_blocks` never could see this — the lots *do* tile their blocks exactly;
the broken seam was between the blocks and the roads, and no per-component check looks across it.

⚠️ **Closing the seam RAISES `selfx_city_merged`, and that is the §4h-5 phenomenon again, not a
new defect.** B 89 → 95, C 187 → 225, entirely at dead ends (C: 35 → 88 points within 20 m of a
degree-1 node, "other" 152 → 137). Lot-over-road plan overlap near dead ends is **unchanged to
0.01 m² (B 3.38 → 3.38, C 19.80 → 19.79)**, so the pull-back adds no interpenetration.
Intersection Analysis registers touching coincident edges and is blind to coplanar overlap, so
it **penalises exact abutment and rewards a small overlap** — a deliberate 5 cm overshoot scores
C 162, better than the 187 it scored with a 13.4 m hole. Exact abutment is what §S5 and §S7
specify, so the number is the wrong instrument *for the lot seam*.

> ⚠️ **CORRECTION, 2026-08-09.** This paragraph used to end "removing the lots from the merge
> drops the count to **0 on every case**, so the metric is entirely a lot↔road contact measure."
> **That is false, and it was being used to wave away C's largest regression.** Re-measured at
> the real output 0 (`out_city ← out_groupclean ← city_weld ← city_merge2`; note that §4h-5's
> "output 0 is `city_merge2`" is also wrong — the weld and the group clean sit between them, and
> reading it at `city_merge2` inflates A 6 → 63, B 93 → 381, C 326 → 727):
>
> | case | shipped | with the lots removed |
> |---|---|---|
> | A_drawn | 6 | **6** |
> | B_grid | 93 | **86** |
> | C_radial | 326 | **112** |
> | D_offset | 6 | **6** |
> | E_short_t | 0 | **0** |
> | F_bend | 2 | **2** |
>
> So **112 of C's 326 points are road↔junction and have nothing to do with lot abutment**, and
> A, D and F do not move at all. F_bend is the cleanest statement of it: that case ships **zero
> lots** and still scores 2. The lot-abutment reading explains at most the *difference* between
> the two columns (B 7, C 214) — it does not explain the residue, and it explains none of A, D
> or F. The residue is the §4e-1 road↔junction seam, which is a real defect class and is still
> open. Do not use §4h-5 to dismiss a movement in this number without splitting it this way
> first; the split takes one cook.

**2. The dead-end rails are at their useful limit, and the binding constraint is NOT junction
spacing.** Swept on B and C, all guardrails measured (`selfx_junction_surface`, the seam,
`selfx_roads`, sweep folds, unpaved area):

| change | result |
|---|---|
| `graph_params_min_node_dist` 40 → 30 / 25 / 20 / 15 | `selfx_junction_surface` **stays 0** at every value — the §4g hypothesis was right about that — but the **seam** blows from 0.035 m to **0.383 m**, 7.7× tolerance, at every value below ~32. 38 and 35 give C 33 / 32 dead ends at a seam of 0.0602, still over. |
| trace `min_node_dist` 50 → 40 | **bit-identical output.** Inert. |
| trace `min_node_dist` 50 → 30 / 20 | `selfx_junction_surface` 0 → 41, `selfx_roads` 13 → 168 |
| `graph_params_min_join_angle` 45 → 30 → 20 | **bit-identical output on every case.** A rail that has never fired. |
| `graph_prune_min_edge_len` 13 → 8 | B dead ends 21 → 23, 57 m² unpaved. Worse. |
| `graph_params_d_extend` 90 → 120 | B dead ends 21 → 22. Worse. |
| `graph_params_max_curvature` 25 → 35 | the only relaxation that pays: **B 21 → 19, C 35 → 33**, seam and `selfx_roads` unchanged. **Not shipped**: it flips `every_corner_is_an_arc` on C (`radius_fit` 0.42 → 1.02 on a near-straight corner whose *applied* radius is still exact to 2e-7) and costs C 22 merged-city points. Four dead ends is not worth a check. |

**Why the short links are refused, root-caused.** Instrumenting `graph_extend`: of C's 46 and
B's 34 unlinked ends, **25 (C) and 12 (B) have their nearest joinable edge INSIDE
`min_node_dist`** and are refused for being too *close* — 13 (C) / 10 (B) by `max_curvature`,
7 / 9 genuinely beyond `d_extend`. But the refusal is doubled, and the second one is structural:
`clear_b = max(mnd, minlen)` gates the connector's own length, **and** the validator applies
`min_node_dist` to the extending prim itself — and the dead end is `dist` from the landing point
by construction, so **a connector shorter than `min_node_dist` refuses itself.** Separating the
connector-length floor from the clearance alone therefore changes *nothing* (measured:
bit-identical). Restating the rail as a rule about **nodes** (the landing point must clear every
existing node, the dead end's own node exempt because it becomes degree-2) does let the short
links through — and C goes to **106 junction self-intersections, seam 0.816 m, 111 m² unpaved**
for a gain of one dead end. **The rail is load-bearing**; §4h-3 was right. The ceiling is S5's
inability to build junctions closer than ~40 m, and the structural answer is §3b row 3, not a
parameter.

**3. A_drawn's "gap at a junction" is NOT §S7's fillet.** Root-caused: **PolyExpand2D applies a
single offset to a whole COLLINEAR RUN — the point-count-weighted mean of `offsetscale` over
it.** Control test, a T of three arms with local scales 13.4 / 7.55 / 7.55: the bent arm keeps
its own 13.4, but two *collinear* arms both come out at **10.8 = (51 × 13.4 + 41 × 7.55) / 92**,
exact. Fusing the node point or setting it to the max changes it by 6 cm; a 20° bend removes the
effect entirely.

In A, the artist's drawn bottom street is classified **arterial** (26.8 m) in the middle and
**collector** (15.1 m) at both ends, and the three are collinear. The block boundary along all of
them therefore sits at 10.17 m from the centreline instead of 13.4 and 7.55: a **2.6 m strip of
no-man's-land down each side of both collector stretches (492 + 265 m², beginning exactly at the
T junctions — this is what the artist sees)**, and the lot plate 3.2 m inside the arterial's kerb.
Measured at x = 100 on the collector: road 15.10 m wide, corridor 20.34 m.

**There is no in-place cure**: a collinear run can hold only one offset, so no assignment of
`offsetscale` gives both arms their own width, and `min`/`max` instead of the mean makes one side
strictly worse (5.85 m of strip, or 5.85 m of lots over the arterial). The real fix is §S7's
kerb-derived block boundary, which replaces PolyExpand2D for this purpose — so §S7 *is* the cure,
but for a different reason than the fillet, and this is now a second independent argument for
building it. Separately, `blocks_offsetscale`'s `max(streetWidth)` over `pointprims` is **dead
code**: `blocks_resample` unshares points, so it only ever sees the point's own street.

A's other 68 m² — eight ~10 m² patches at the degree-3 and degree-4 nodes — **is** §S7's fillet
defect, one order of magnitude smaller than the strips.

---

## 4d. Measured state of the shipped build — 2026-08-09 (pre-fix)

Recorded so the next pass starts from numbers instead of re-deriving them. Cases are the three in
`tests/citygen/cases.py`: **A** hand-drawn streets, **B** grid field, **C** radial field.

| | dead ends | degree-3 | degree-4 | degree-5+ | corners: arc / straight |
|---|---|---|---|---|---|
| A drawn | 8 | 2 | 4 | **0** | 14 / 8 |
| B grid | **34** | **0** | 25 | **0** | 50 / 50 |
| C radial | **44** | **0** | 28 | **0** | 56 / 56 |

Reading:

- **More dead ends than junctions** in both generated cases → §S2 `d_lookahead` + interleaving,
  §S3 extend-to-connect.
- **Half of all corners are straight chords** → §S5 fillet-always.
- **No degree-3 from a field, no degree-5+ anywhere** → §S5 higher-degree; needs a test case before
  it can even be called broken.

Known-failing checks carried in `tests/citygen/baseline.json` — real, tracked, not noise:

| Case | Check | Value | Cause |
|---|---|---|---|
| A | `selfx_junction_surface` | 4 | junction artefact at (60.8, −111.3) |
| C | `no_downward_faces` | 10 | radial-centre fold — §S1 degenerate point, no plaza |
| C | `selfx_roads` | 46 | same fold + 2 corridor overlaps |
| all | `attribute_schema` | 1 | `land_use` never written to the graph |

**Fix order, highest visual payoff first** (agreed 2026-08-09):
S5 fillet-always → S8 `recursive_obb` + `offset` lots (with the S7 fillet-derived boundary) →
S2/S3 dead-end elimination → S1/S5 radial plaza → degree-5+ test case.

⚠️ **The third item is bigger than it looks.** "Dead-end elimination" is §3b row 3 — majors enclose,
minors subdivide the enclosure — which reorders S2/S3/S7 rather than patching the tracer. Doing it as
a repair pass (`d_lookahead` + extend-to-connect alone) will improve the numbers; doing it
structurally is what all four sources actually describe. Repair still has to exist for the residue,
so it is not wasted work either way — but do not mistake the repair for the fix.

---

## 5. Scale strategy

Manhattan-scale is a stated target, so this needs an answer, but a cheaper one than expected:

**Do not chunk the graph. Chunk the geometry.**

A street graph for a very large city is on the order of 10⁴–10⁵ edges — trivial for Houdini to
hold and solve globally. The expensive thing is the 10⁷ instanced elements (windows, kerbstones,
trees). So keep S0–S4 **global and monolithic**, which also keeps the graph simple, correct and
free of tile-seam artefacts; chunk and lazily evaluate only from S6 onward.

This avoids deterministic-tiled-generation complexity entirely, and tile stitching is where that
approach usually fails.

---

## 6. Attribute schema

The stage API. Names use the standard urban-modelling vocabulary — convention only, no dependency.

**Per edge (primitive attributes)**

| Attribute | Type | Meaning |
|---|---|---|
| `edge_id` | string | stable ID (see `citygen.md`) |
| `street_class` | string | highway / arterial / collector / local / alley |
| `street_template` | string | cross-section template reference |
| `streetWidth` | float | total width, kerb to kerb |
| `streetOffset` | float | lateral offset of geometry from the centreline |
| `sidewalkWidthLeft` / `sidewalkWidthRight` | float | per-side sidewalk width |
| `laneWidth` | float | nominal lane width, drives UVs |
| `precision` | float 0–1 | spline sampling density on curves |
| `connectionStart` / `connectionEnd` | string | junction class at each end, incl. `PORTAL` |
| `respect_elevation` | int | whether this street conforms to terrain |
| `layer` | int | −n underground · 0 ground · +n elevated. **Planarity is per layer** |
| `network_type` | string | road · rail · pedestrian · sky_lane · canal (v1: road only) |
| `is_bridge` / `is_tunnel` / `is_ramp` | int | construction flags for S5b |
| `terrain_op` | string | cut_fill · none (bridge) · excavate (tunnel) |
| `region_id` | string | owning region — unit of caching, locking and copy/paste |
| `land_use` | string | zoning category, drives template and hierarchy defaults |
| `source_node` | string | **which node generated this element.** Required from v1 — it is what lets a downstream edit be committed back to the right upstream owner (`citygen.md` Contract 2) |
| `turn_clamp_converged` | int | 1 = the S3b curvature clamp reached its residual on this edge, 0 = it did not. **A solver that cannot say whether it converged ships a broken answer silently, which is exactly what happened** (§S3b). Read by `centreline_curvature_within_class` |
| `turn_clamp_ratio` | float | the residual it settled at, as κ × R_min — 1.0 *is* the clamp |
| `turn_clamp_sweeps` | int | sweeps used, against a 200 cap. **Every prim in every shipped case uses 1** — the tangent-arc seed solves it outright; the control rigs need 3 (90°) to 63 (135°) |

`elem_id` and `source_node` must **survive all the way to the final geometry**, not merely exist at
generation time. Everything in the edit-and-override design depends on it.

**Per point**

| Attribute | Type | Meaning |
|---|---|---|
| `node_id` | string | stable ID; empty on interior shape points |
| `is_node` | int | 1 = topological node, 0 = shape point |
| `node_degree` | int | incident edge count, derived |

**On swept road geometry (points/prims)**

| Attribute | Type | Meaning |
|---|---|---|
| `elem_type` | string | sidewalk / lane / bus / bike / … |
| `elem_index` | int | index within the template |
| `u_cross` | float 0–1 | normalised position across the street |
| `drivable` / `walkable` | int | behaviour flags for traffic and scatter |

---

## 6b. Shipped V1 assets

Four HDAs in `polyfactory/otls/`, versioned. Examples live in `/obj/citygen_examples`.

| Asset | In → Out |
|---|---|
| `pf_citygen_field_grid` | — → a field **source descriptor** (one point: type, centre, weight, falloff, bearing). Chainable via its input |
| `pf_citygen_field_radial` | same, radial |
| `pf_citygen_trace` | field sources → street centrelines (tensor sum, RK2, occupancy spacing) |
| `pf_citygen_streets` | **any curves** → out0 city geometry · out1 blocks · out2 lots · **out3 street graph** (the data stream, Contract 8) |

Field sources are descriptors rather than baked grids, so any number merge and blend for free.
`pf_citygen_streets` accepts a hand-drawn Draw Curve and a traced field identically — that is the
whole point of S3 being the contract.

Verified end to end: drawn curves 15 streets → 2 blocks → 59 lots · grid field 64 → 9 → 520 ·
radial field 78 → 12 → 835.

⚠️ **Traps hit while building these, worth not rediscovering:**
- `createDigitalAsset` does **not** carry a subnet's parameter interface. Set it on the
  definition afterwards or the asset ships with no parameters.
- Copied foreach nodes keep **absolute** `blockpath`/`templatepath` references to where they were
  copied *from*. All three examples silently produced byte-identical output until those were made
  relative.
- `sweep`'s `crosssectionattrib` **cycles** cross-sections along a curve; it does not select one
  per curve. Per-template branches, not a loop.
- A per-piece foreach can serve **stale cache**: its output stayed bit-identical while its input
  changed. Explicit branches are worth the node count.

## 7. Where the code goes

Matching existing repo conventions:

- `polyfactory/vex/include/pf_streetgen.vfl` — extend the existing tracer (RK2, termination).
- `polyfactory/vex/include/pf_streetgraph.vfl` — **new**, S3 graph operations.
- `polyfactory/scripts/python/polyfactory/citygen/` — **new** package: ID generation, validation,
  override resolution, and the state library later.
- `polyfactory/otls/pf_street_*.hda` — one HDA per stage, following the `pf_` prefix convention.
- Cross-section templates as **geometry** (`.geo` for diffability, `.bgeo` for size) in a templates
  directory — not JSON, not Python.

---

## 8. Build order

Deliberately front-loads the risky stage rather than the satisfying one.

1. **S6 cross-section → geometry from one hand-drawn spline.** Self-contained, immediately visible,
   useful standalone, and it forces the §6 schema to be real. *(Agreed as first slice.)*
2. **S3 graph** on hand-drawn spline networks — snap, intersect, split, clean, validate, extract
   faces. Highest risk; prove it on inputs you control before generating anything.
3. **S5 intersections** using the S4 junction vocabulary; port from the 2025 solver hip.
4. **S4 classification.**
5. **S1/S2 generation** — tensor field first, then the other generators as plugins.
6. **S7/S8 blocks and lots.**

Verification at every step: cook clean, then **look at it** in a viewport render. Prim counts do
not prove geometry is right.

---

## 9. Open decisions

**Resolved in clarification round 1** — kept for the record: units are metres · target is offline
film · topology is cached so S8 determinism is not required · planar-per-layer replaces the
2D-vs-3D question · terrain uses the two-node chain with a per-segment `terrain_op`.

**Resolved in clarification round 2:**

- **Region definition** — `region_id` is just an attribute, authored by *any* of: expressions on
  IDs · painting on the street splines or points · viewport selection then assign · a dedicated
  region-selection tool. Multiple paths, because art direction.
- **Paste behaviour** — both are valid, so it is a parameter: `terrain_adapts` (preserve the look,
  terrain deforms) or `city_conforms` (city re-drapes onto the new terrain).
- **Cut-and-fill authority** — **the street owns it.** Embankment width is an attribute with a
  default that the artist changes.
- **Ramp grade limits** — the artist can always generate the invalid ramp. Default is `block`, and
  the global "allow invalid" switch demotes it to `warn`; the warning is persisted on the element.
  No auto-lengthening, no silent re-routing.
- **Bridge routing** — cost-driven least-cost path, see S5b.
- **Rail** — not v1. `network_type` reserved only.

- **Viewer states are v2.** v1 exposes everything through parameters — unwieldy but fully testable.
  The schema still carries `elem_id` and `source_node` from v1 so states can be added without
  reworking it.

- **Pier placement** — not a design question, just implementation plus the standard validation
  rule. Specified in §S5b.

Nothing currently blocking. Open items are tracked system-wide in [`citygen.md`](citygen.md) §7.

---

## 10. Explicit non-goals for v1

**Moved IN to v1 by clarification round 1:** bridges, tunnels, overpasses and ramps (§S5b).

Still out, recorded so they don't quietly creep in: traffic and pedestrian simulation (the graph is
being designed to make it possible later, that is all) · rail, metro and sky-lane networks
(`network_type` reserved, not implemented) · multi-level stacked city layouts (`layer` reserved and
proven on bridges, but Coruscant-scale stacking is not a v1 target) · underground utilities ·
procedural signage and road markings beyond material assignment · per-segment cross-section
transitions (seam left open, §S6) · Voronoi graph generator (deferred, §S1) · `skeleton` lot
subdivision (deferred to v2, needs Vanegas 2012 — §S8; `recursive_obb` and `offset` are both v1).
