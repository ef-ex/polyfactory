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
3. **Intersect** every pair of **same-layer** edges; insert a node at each crossing and
   **split both edges**. This is the step whose absence broke everything before.
   Cross-layer crossings are instead recorded and **clearance-checked**.
4. **Cleanup**, and this is where "satisfying" is won or lost:
   - fuse nodes closer than `min_node_dist`
   - delete stubs shorter than `min_edge_len`
   - collapse pairs of edges that are near-parallel and closer than `min_street_sep`
   - enforce `min_angle` between edges at a node (merge or nudge below it)
   - prune the dead ends that extension could not rescue, iteratively, down to `dead_end_ratio`
5. **Validate:** every edge has exactly two node endpoints; no duplicate edges between the same
   node pair; no zero-length edges; **each layer is planar**; **all cross-layer crossings meet
   `min_clearance`**; every ramp connects exactly two distinct layers.
6. **Extract faces per layer** → these are the blocks (consumed by S7). Only ground-layer faces
   normally become buildable blocks; elevated layers produce blocks only in the sci-fi case.

⚠️ **Needs prototyping before committing:** vanilla Houdini has no single planarize-polylines SOP.
`Intersection Analysis` yields intersection points but stitching, splitting and robust cleanup
still have to be written. Expect this in VEX or Python with a spatial grid for the pairwise tests.
**This is the highest-risk stage and the one to build first** — everything downstream is
straightforward once the graph is trustworthy.

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
   and line 83 is `radius_used = radius;`. Unclamped, cuts reached 26 m, **three streets were
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

| Item | State |
|---|---|
| S5 fillet-always (§S5 "every corner is an arc") | **done, verified independently** — circle fit residual ≤ 2e-5 m, radii exactly the class radii, tangency exact in the continuous sense |
| S5 winding-based inward offset | **done** — A `selfx_junction_surface` 4 → 0 |
| S1 degenerate points + plaza ring (§S1, §S5 plazas) | ⚠️ **NOT done.** The exclusion works; **the ring is deleted before it ships** (§4e-2). The C gains came from the seed/trace exclusion alone |
| S8 `recursive_obb` + `offset` lots (§S8) | ⚠️ **partial.** Voronoi is gone and the structure is right, but parcels are ribbons up to 31:1, non-convex blocks produce bowties, and `offset` fails `lots_tile_blocks` (§4e-4,5,6) |
| `land_use` written (§4d) | **done** |
| S7 block boundary from the fillet (§S7) | not started |
| S3 extend-to-connect (§S3 step 2) | **done** — `graph_extend`, before `graph_stitch`. Interior dead ends B 15 → 7, C 28 → 12. Capped by S5, see §4f |
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

## 4f. The junction-spacing ceiling — measured 2026-08-09

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
