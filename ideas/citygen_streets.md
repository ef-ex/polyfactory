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
| `radial` | field around a centre | circle, centre point, **spiral angle** (0 = spokes + rings, 90 = the two swapped, between = a spiral) |
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

#### ⚠️ A CONNECTION WAS BEING REFUSED FOR BEING TOO CLOSE — fixed 2026-08-10

`graph_extend` case (b) — *extend to the nearest point on an existing edge* — gated the landing
at `clear_b = max(min_node_dist, min_edge_len)` = **40 m**, so an end that came to rest *inside*
the crowding range was not merged, it was **dropped**, and it shipped as a dead end sitting in
the target's pavement. Measured on C_radial after the tongue drop: **4 of its 8 interior dead
ends had an edge within 40 m**, and one of them was **7.3 m from a 26.8 m wide arterial** — a
stub three and a half metres inside the road it was refused a connection to.

The floor is now 1.0 m and a gap below `clear_b` is closed by **moving the end onto the
landing** rather than bridging it, exactly as case (a) has always done at its own snap range;
`graph_stitch` then splits the target at the T-touch. Everything that is about the *junction*
rather than about the *connector* still binds — `max_curvature` on our own end, the T's leg
angle, and `min_node_dist` measured **along the target** so the split cannot crowd the nodes at
either end of the edge it lands on — and the snap will not consume its own street.

**Measured, C_radial:** dead ends **17 → 14 total, 8 → 5 interior** (28 / 13 before this round's
work began). Blocks **20 → 26**, B_grid **16 → 17** — the connections close real city blocks.
`plaza_disc_is_clear` recovered on its own: **built 11310.8 → 8364.4 m², gap 37.86 → −1.14 m**,
because the arms that stopped 62–66 m from the plaza centre now reach it. `lots_clear_of_roads`
**16.4 → 12.7 m**. `city_is_fully_paved`, `lots_clear_of_junctions`, `selfx_junction_surface`,
folds, seam, `every_mouth_has_a_road`, `graph_planar_y` all still **0**.

Two numbers moved the wrong way and neither is swept up:

* `selfx_city_merged` on B **89 → 93**. B gained a junction (107 → 111 mouths); 4e-1 is
  road-and-patch interpenetration *at every junction*, so this tracks the junction count almost
  exactly and is not a new defect.
* `trim_leaves_road_standing.under_ratio_all` on C **3 → 8**, worst ratio **0.242**. A snap
  splits its target, and `clear_b` = 40 m only guarantees each piece is 40 m long — an arterial
  piece that short loses ~17 m to each of its two mouths and ships ~6 m standing at 26.8 m
  width. **This is the tongue again, in the one position `s5j_tongue_mark` may not touch**: a
  street between two junctions, where deleting it would disconnect the city. `under_ratio`, the
  asserted quantity, stays 0.

#### ⚠️ The node merge: attempted, measured, reverted — and the blocker is NOT the clamp

§S3 step 3's answer to the above is to **weld the two crowding junctions into one node**. The
recorded blocker was that the S3b clamp pins prim endpoints, so a merge performed after it
leaves a kink at the node that nothing can relax (κ × R_min 40.2, still 28.2 after spreading
into the incident arms). **That was addressed and it was not the binding constraint.** The whole
drop/merge pass was moved to sit between `graph_width` and `graph_turn_resample`, i.e. *before*
the clamp, so the clamp simply solves the graph it is handed; and the merge was restricted to
streets whose **both** ends are already degree ≥ 3, so the weld can never produce a degree-2
node — a bend at a node, which is the case the clamp genuinely cannot fix.

It still failed, and differently. On C_radial, 6 merges (plus 8 drops) produced:

| | before | after the merge |
|---|---|---|
| `every_mouth_has_a_road` | 0 | **14** |
| `selfx_junction_surface` | 0 | **349** |
| `block_boundary_closes` | 0 unpaired, 0 open | **28 unpaired, 14 open loops** |
| `lots_clear_of_junctions` | 0 m² | **9606 m²** |
| `trim_leaves_road_standing.min_standing_m` | 20.2 m | **−1952 m** |
| suite | 18 failing | **27 failing** |

A trim of −1952 m on a street a few hundred metres long is a **miter spike**: welding two
junctions 6 m apart brings their arms together at a shallow angle, `pfsj_corner_lines` finds the
kerb intersection hundreds of metres out, and the cut runs past the far end of the street. So the
real prerequisite is §S5's **construction 2 — "merge incident edges within `merge_angle`
(default 20°) into a single direction before solving"** — which is listed as adopted and is still
unbuilt. **The node merge cannot land before the shallow-arm merge does**; it is not a threshold
to tune and it is not the clamp. Reverted, and the numbers above are why.

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
   for corner geometry at a bend, and the angle rails stand in for arm merging. Build the
   three capabilities and the rails go to zero.

   ⚠️ **The "measured, they are also mostly inert" sentence that stood here was wrong on both
   halves, and it is deleted rather than softened.** Corrected 2026-08-10 by the full parameter
   sweep (§4c "Every promoted parameter, measured"). `min_node_dist` 50 → 40 *is* bit-identical
   and reproduces — but 50 → 0 and 50 → 300 move every output on both B and C, so it is
   threshold-insensitive around its default, not inert; and the two parameters spelled
   `min_node_dist` (the tracer's lookahead-crowding test, and `graph_params_min_node_dist` at
   `graph_extend`) are different parameters that this ledger had been conflating.
   `min_join_angle` **fires**: 45 → 5 moves all four outputs on B_grid, so at 45 it is rejecting
   extensions into existing junctions there.

   ⚠️ **Correction to an earlier conclusion in this document.** §4h read the spacing ceiling
   as evidence that dead ends need the majors-enclose-minors restructure (§3b row 3). That
   is wrong. Row 3 is worth building for the *hierarchy*, which is visibly absent, but it is
   not the dead-end fix — the dead-end fix is the three capabilities above.

   ##### Where the rails actually stand, measured 2026-08-10

   Every dangling end at `graph_extend` was replayed against every gate. The union of what
   refuses them, over B and C:

   | rail | interior ends it blocks |
   |---|---|
   | `max_curvature` on the connector direction (case b) | **every** interior refusal in both cases |
   | `max(min_node_dist, min_edge_len)` as a floor on the CONNECTOR LENGTH (case b) | 14 of 24 in C, 12 of 14 in B |
   | the split-crowding test, `min_node_dist` from the target edge's own ends | most of the rest |
   | `max_curvature` on the corner (case a) | 11 in C, 8 in B |

   **`max_curvature` 25 → 45 is the one that could be paid for today**, because it stands in
   for corner geometry at a bend and S3b's solver now converges 90° and 135° onto a tangent
   arc. Swept against every invariant on all six cases: **B dead ends 21 → 19 (interior 5 →
   4), C 33 → 28 (interior 18 → 13)**, and paving, junction overlap, lot-over-road, junction
   self-intersection, sweep folds and the seam all unmoved.

   ⚠️ **45 is still the right rung, but the reason recorded here was wrong and the wrong
   reason was pointing the next task at the wrong stage.** Corrected 2026-08-10 after an
   independent audit of `2fe1725`; the paragraph this replaces claimed *"at 50 C picks up
   8,984 m² of lots on the roads and 339 junction self-intersections … that ceiling is the
   S5 fillet clamp and the shallow-arm merge"*. **Not reproducible on this build.** Measured,
   whole suite, one value per column:

   | `max_curvature` | 45 | 50 | 60 | 90 |
   |---|---|---|---|---|
   | suite failing | **17** | **20** | 21 | 25 |
   | `lots_clear_of_roads` (every case) | 0.0 m² | **0.0 m²** | **0.0 m²** | C **123.8 m²** |
   | `selfx_junction_surface` (every case) | 0 | **0** | **0** | C **36** |
   | C dead ends (total / interior) | 28 / 13 | **27 / 12** | 27 / 12 | 27 / 12 |
   | C `selfx_city_merged` | 270 | **212** | 217 | 338 |
   | C `lots_are_simple_polygons` | 41 | **22** | 22 | 34 |

   **At 50, C is *better* on three metrics and the fillet failure does not occur at all.**
   The described failure first appears at **90**, and then at 123.8 m² and 36 — an order of
   magnitude below the numbers that were recorded for 50.

   **What actually stops 50 is a different seam.** The three new failures at 50 are all on C
   and all are S7/S5-trim, not S5 fillet: `block_boundary_closes` (**2 unpaired kerb ends,
   1 open loop** — S7's collect-and-close), `trim_metric_is_consistent` (**4.018 m**, one end
   over the 0.05 m tolerance — the S5 trim seam) and `lots_tile_blocks` (**0.193**, the
   downstream consequence of the open loop). 60 adds `every_corner_is_an_arc`
   (`radius_fit` 2.493). So the next task here is **S7's kerb collect-and-close and the S5
   trim metric**, *not* the shallow-arm merge, and the fillet clamp is not what is binding.

   ⚠️ **S3 step 3's node merge was built and measured and it is NET-NEGATIVE at the trigger
   this document specifies. Reverted; the measurements are the deliverable.** A detail
   wrangle after `graph_fuse` collapsed every edge shorter than `min_node_dist` whose two
   ends are both nodes, union-found the clusters and moved each to its centroid.

   - **Moving the node alone is not the merge.** A node is a prim *endpoint* and the S3b
     clamp pins endpoints, so a node dragged sideways leaves a kink one segment in that
     **nothing downstream can touch**: κ × R_min went to **40.2** and C lost 672 of its 790
     lots. Spreading the displacement into the incident arms with a hat weight (S3 step 3's
     *"arms re-sorted around the merged centre"*) recovered the lots and brought κ to 28.2 —
     still far outside the clamp, because the corner **at** the node is still between two
     different prims.
   - **At the specified trigger it eats legitimate blocks.** `min_node_dist` = 40 means every
     40 m edge between two junctions, and a radial city is full of them.
   - **Below the trigger it is inert or it breaks other cases.** At 25 with `max_curvature`
     45 it is genuinely good for the two cases it was tuned on — **C 33 → 21, B 21 → 18, all
     invariants clean** — and then A and D pick up a junction self-intersection and **E loses
     its 20 m arm to the merge outright**, taking the whole S3b verdict attribute with it.
     Suite 17 → **23**. Tuning on two of six cases is how that was missed, and it is recorded
     here because it will be tempting to retry.

   **What the merge needs before it is worth rebuilding:** a trigger decoupled from
   `min_node_dist` and sized by the junction surface rather than by an edge length, and a way
   to relax a corner **at** a node — which today no solver in the pipeline has, because the
   clamp works on prim interiors only. That gap is the single most valuable thing to build
   next for dead ends.

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

#### ⚠️ THE NETWORK WAS SOLVED ONCE, AND THAT IS A BUG. Fixed 2026-08-10

The artist: *"the street did not solve the junction or turn. It did detect it now as a dead end
and merged it to the closest street. That is fine, but the other street which should form a
junction with it did not — I think we only go over the street network once and do not check if
there are errors left after solving on the new network."*

**He is right, and it is structural rather than a threshold.** Every repair in this section
*mutates* the graph, and the consequence lands on a stage that has already run:

| repair | what it leaves behind |
|---|---|
| extend-to-connect, case (b) | a **new junction on the target street** — after S4 classified it and after S5 sized its mouths |
| the snap-and-merge at `clear_b` (§S3 above) | the same, one stage earlier |
| `min_standing_widths`'s tongue drop | the node it hung off **reopens** at a lower degree, and the arm's other end becomes a fresh dead end nothing tries to connect |
| the cul-de-sac bulb | a turning circle laid down after the graph is closed |

**Repair, planarise, reclassify and solve now iterate to a fixed point.** The whole S3→S5 chain
sits inside a feedback loop in `pf_citygen_trace` (`repair_begin` … `repair_verdict` …
`repair_end`), and `repair_verdict` compares the pass's output against its own input and writes
these detail attributes onto the graph it ships:

- **`repair_converged`** — 1 only after **two consecutive** passes have changed nothing. It is
  the block-end's **Stop Attribute**, so the loop ends by *proving* the fixed point rather than
  by running out of budget.
- **`repair_iterations`** — passes used, against `Max Repair Passes` (default 12).
- **`repair_residual_m`** — the largest distance any point still moved on the last pass, against
  `Repair Tolerance` (default 1 mm). **The verdict is a number, not only a flag.**
- **`repair_reversed`** — how many edges the last pass turned round.
- **`repair_noop`** — whether *this* pass changed nothing, which is what the streak is counted on.
  ⚠️ **It is deleted the instant the loop ends** (`repair_scratch`, between `repair_end` and
  `OUT_graph2`) and ships on nothing. The streak is counted on it *inside* the loop; outside it
  there is no consumer and no meaning.

⚠️ **The first four are facts about the GRAPH, and that is the only place they ship.** They ride
`pf_citygen_trace` output 0, `pf_citygen_junction`'s stream and `pf_citygen_mesh` **output 3**,
which republishes the graph. They came off the **city mesh** (output 0) on 2026-08-10, with
`orphan_edges_dropped` (`out_detailclean`, between `out_groupclean` and `out_city`): a mesh of
roads, junction surface, piers and parcels is not where a street-graph solver's verdict belongs.
Found by an independent audit of `4fd44b6`, and the reason nothing had seen it is that `no_scratch_attribs` is the only check in the suite that reads detail
attributes at all and it was only ever called on the lots — `attribute_schema` checks graph *prim*
and road *point* attributes. It is now called on the city output too (detail attributes only; the
city's ~50 prim and ~18 point attributes have no agreed schema yet and freezing them would bless
on the city the same names this check fails on for the lots).

⚠️ **Non-convergence is surfaced, not shipped.** Hitting the cap ships `repair_converged = 0` and
`graph_reaches_a_fixed_point` fails. That failure mode has now cost this project four separate
defects — §S3b's `iters = 200`, the trace stall, the clamp budget, and this — and a solver that
cannot say whether it converged ships a broken answer silently every time.

**Measured, passes to convergence: A 3 · B 9 · C 8 · D 3 · E 3 · F 6 · G 3**, and the extra
passes are close to free: cold end-to-end city cook **C_radial 1.69 → 1.97 s, B_grid 1.36 →
1.64 s, A_drawn 0.59 → 0.64 s** — 2.7× the passes for 1.17× the time, because a repair pass is
cheap next to S6–S8.
**`Max Repair Passes` = 1 reproduces the old single-pass build exactly**, which is both the
A/B and the escape hatch.

⚠️ **COMPARE THE GRAPH, NOT THE POINT NUMBERING.** The first verdict compared `P` index-wise
and read `graph_fuse` / `polypath` / the blasts renumbering as **777 m of movement**: C_radial's
geometry is settled and the loop still ran to its cap at 8. Every term must therefore be
order-independent — a count, a sum, or a nearest-neighbour match.

#### ⚠️ …AND THEN IT STOPPED TOO EARLY, BECAUSE FOUR AGGREGATES CANNOT SEE A REDISTRIBUTION

Corrected 2026-08-10 after an independent audit of `ac64636` + `54bf0e3`. The paragraph above
used to end *"every term is now a count or a sum — edges, points, nodes, total centreline length,
bounding box — which is exactly the set of things a repair changes."* **That sentence was wrong,
and it is the reason the loop stopped, rather than converged, on three of the seven cases.**

Two counts, one length sum and a bounding box over six coordinates are all **global aggregates**,
and every local redistribution that conserves them is invisible to all four: a point sliding
*along* its polyline changes no length, a point moving *across* it changes a 5 m segment by a
second-order amount lost in a 9 km sum, and a bounding box only ever sees the extremes. Forced
one pass past its own verdict:

| case | old verdict stopped at | the next pass still moved a point by | edges | total length |
|---|---|---|---|---|
| `F_bend` | 3 | **56.2 mm** at (140.0, −109.84) | 3 → 3 | unchanged |
| `C_radial` | 3 | **26.0 mm** at (246.35, −101.22) | 86 → 86 | unchanged |
| `B_grid` | 5 | 0.034 mm | 64 → 64 | unchanged |

**And it is not cosmetic.** S8's recursive-OBB split is chaotic in a few centimetres, so that
"no-op" pass moves the shipped city: **C 766 → 774 lots** and every parcel *area* changes on A
and D while the street network is bit-stable.

**The second term is the one that matters for the future: primitive DIRECTION.** Reversing a
polyline changes no count, no node, no length and no bounding box — and it flips the shipped
`connectionStart` / `connectionEnd` (§6). Measured on C_radial: **14 edges reverse on the pass
the old verdict stopped at**, 9 on the next, 4 on the next, 1 on the next. It is harmless **only**
because all six shipped templates have `sidewalkWidthLeft == sidewalkWidthRight`;
`boulevard_bus_bike` is already in the library, and **the first asymmetric cross-section turns a
direction flip into the wide sidewalk swapping sides**, with all four of the old terms still
reporting "converged".

**What replaced it.** The four aggregate terms stay, and two more join them:

- a **symmetric Hausdorff** over the two point sets — a real **max**, not another sum — measured
  through `nearpoint()` so renumbering cannot move it, against the artist-facing
  **`Repair Tolerance`** (default **1 mm**, about **16×** the float32 settling noise, whose worst
  case across all seven cases is **6.10e-5 m** on `F_bend` — this paragraph said 9.2e-5 m and
  "about 11×" until 2026-08-10; that number is not reproducible on this build and the shipped
  `repair_residual_m` reads A 1.5e-5 · B 3.4e-5 · C 4.3e-5 · D 1.5e-5 · E 0 · F 6.10e-5 · G 7.6e-6.
  The conclusion is unaffected — the margin is larger, not smaller);
- a **per-edge direction match**: each edge is matched to the previous pass's edge that shares
  its endpoints — through the nodes, not through the numbering — and the loop will not stop while
  any of them comes back the other way round.

⚠️ **The stop rule needs TWO consecutive no-op passes, and `B_grid` is the case that proves it.**
The repair is a function of the graph **and of its point/prim order**, and a pass that changes no
geometry still hands the next pass a different ordering. B's pass 5 moves nothing and reverses
nothing — a clean no-op by every term above — and then pass 6 reverses an edge and pass 7
reverses another. One no-op pass proves `f(x) == x` and says nothing whatever about `f(f(x))`.
Requiring the streak proves both; on B it costs 5 passes → 9 and settles the orientation for good.
`Max Repair Passes` went 8 → 12 with it, because the real fixed points are 8 (C) and 9 (B) and
the old cap could not hold them.

**Measured against the acceptance the audit set**, whole suite, `54bf0e3` → this commit:
17 failing → **17 failing**, and `city_is_fully_paved`, `lots_clear_of_junctions`,
`selfx_junction_surface`, folds, `every_mouth_has_a_road`, `graph_planar_y` and
`block_boundary_closes` all still 0, seam still 0.0001, dead ends unmoved at
A 8 · B 17 · C 12 · D 8 · E 3 · F 3 · G 3. `selfx_city_merged` on C **131 → 127**.
`lot_aspect_ratio` over-3.0 count **B 164 → 161, C 192 → 189**.

⚠️ **One acceptance item did NOT land, and the reason is not the verdict.** "Lot counts stable
across an extra forced pass" is now true of A, B, D, E, F and G — A was 82 → 83 and B 622 → 617
before this change, and both are stable now — but **C still moves 774 → 770**. The pass that does
it moves no point further than **4.6e-5 m** and reverses no edge: that is the *last ulp* of
float32 at these coordinates, and the repair pass cannot be made bit-exact idempotent because
`resample`, `graph_polypath` and the clamp all re-accumulate arc length in float32 every pass.
Measured on `A_drawn`, a **1.5e-5 m** jitter alone flips a parcel. **So the residual instability
is S8's determinism, not S3's convergence**, and closing it means making the recursive-OBB split
insensitive to a 45-micron input change — a separate task, in S8.

⚠️ **A/B/D/E/F/G being stable across THAT pass is a property of that pass, NOT a durability
guarantee, and the paragraph above used to read as though it were.** Corrected 2026-08-10 after an
independent audit of `4fd44b6`. Under a comparable but independent **±4.5e-5 m** jitter — the same
amplitude, a different perturbation — the lot count moves on **every case measured**:
**C 774 → {770, 773, 770, 768, 764}**, **A 83 → {82, 83, 82, 85, 82}**,
**B 619 → {621, 623, 625, 626, 624}** — while the **block** count never moves on any of them.
The honest statement is therefore **"S8 is chaotic at the float32 noise floor on every case; the
graph is not"**, and C_radial is merely the case whose chaos the shipped forced pass happens to
land on. It does not mean the other six are settled and C is not.

**What the second pass actually does, on C_radial:**

| | one pass | fixed point |
|---|---|---|
| edges | 84 | **86** |
| centreline | 9206.4 m | **9300.1 m** |
| blocks | 26 | **28** |
| lots | 759 | **766** |
| dead ends (total / interior) | 14 / 5 | **12 / 3** |
| `lots_clear_of_roads` | 15.8 m of lot boundary in the road | **0.0** |

The two new junctions are at **(−94.6, −265.2)** and **(257.7, −91.2)**, and both are a dangling
end that pass 1 extended, whose *target* was never re-split. The second is the exact defect §S7
recorded the root cause of — *"two dangling ends 6.68 m apart at (251.4, −87.1) and (249.4, −93.5),
each one INSIDE the other street's pavement […] neither connected"* — so closing it takes
`lots_clear_of_roads` to zero on C for the first time.

⚠️ **One latent bug had to be fixed before the loop was safe, and it was invisible while the
pipeline ran once.** `graph_extend`'s connector prim copied `layer`, `street_class` and `src_id`
from the street it extends and **not the cross-section**, which was harmless while `streetWidth`
did not exist yet at that point in the graph. From the second pass it does, the connector carries
0, and **`graph_polypath` LENGTH-WEIGHT-AVERAGES prim attributes when it merges the connector back
in**: a 7.8 m connector diluted a 163.6 m local from 14.4 m to **13.71 m** — exactly 0.952×, with
`sidewalkWidth*` and `laneWidth` scaled with it. `graph_width` then left it alone, because its
"an authored value wins" guard is `streetWidth <= 0`. The road swept 0.7 m narrower than the kerb
its block was built from and **95.8 m² of lots came out on it, in a strip down both sides of that
one street.** The connector now inherits the cross-section too. *An extension is the street it
extends.*

**`graph_reaches_a_fixed_point` is committed with this**, and it has both teeth: the solver's own
`repair_converged`, and an independent replay — a second `pf_citygen_trace` with the same
parameters, fed the shipped splines on its drawn-spline input. At `Max Repair Passes` = 1 the
replay reports C_radial moving **84 → 86 edges, 45 → 47 nodes, +93.7 m**, which is the artist's
report reproduced as a number.

⚠️ **The replay was an independent NODE and not an independent CRITERION, and that is a
different thing.** Corrected 2026-08-10 by the same audit. `_graph_invariants` compared four
terms — edges, points, nodes, total length — which is a **strict subset** of `repair_verdict`,
dropping even its bounding-box term. A replay that runs a weaker test than the solver it is
auditing **cannot fail on anything the solver missed**, which is the only reason to run it: every
defect above was equally invisible to both. It now compares the **full geometry** — per-point
positions by symmetric Hausdorff, and per-edge direction — against the same `Repair Tolerance`.

**Checked for teeth rather than assumed to have them**, by stopping each case at the pass the old
verdict stopped at and asking what the replay says:

| case | stopped at | what the replay independently reports |
|---|---|---|
| `C_radial` | 3 | **10 edges reversed, 1.18 mm of movement** |
| `F_bend` | 3 | **1.65 mm of movement** |
| `B_grid` | 5 | **2 edges reversed** |

At the shipped defaults all seven cases replay to **0.0 m moved and 0 edges reversed** — the
replay is bit-exact, not merely within tolerance.

#### ⚠️ AND THE EXPERIMENT THAT CAUGHT THE VERDICT WAS ASSERTING THE VERDICT'S OWN BLIND SPOT

Corrected 2026-08-10 after an independent audit of `4fd44b6`. `forced_extra_repair_pass` is the
one check that can tell *"the loop stopped"* from *"the loop converged"*, and its `ok` flag tested
`edges` / `points` / `blocks` — **exactly the global aggregates the commit that added it had just
demonstrated cannot see a redistribution.** It would have passed on the defect it was written to
catch. On HEAD it passed while its own value dict recorded `'moved': {'lots': [774, 770]}` on
C_radial — a four-primitive change in the shipped city that its `state()` does not even sample.

The fix costs nothing, because the forced pass already writes the two *local* terms: it now
asserts **`repair_residual_m` ≤ `Repair Tolerance`** and **`repair_reversed` == 0** on the pass it
forced. Measured across all seven forced passes: worst **6.10e-5 m** (`F_bend`) against 1e-3 m — a
**16×** margin — and **0** reversals; `C_radial`'s is 4.55e-5 m, the pass that moves its four lots.
A *missing* attribute fails rather than being skipped: reading a verdict defensively is how
`turn_clamp_converged` once stopped shipping with nothing noticing (§6).

Two smaller repairs in the same check: the `stopattrib` round-trip went through `.eval()`, which
would have flattened an expression to a literal on the way back in, and now goes through
`rawValue()`; and the `allowEditingOfContents()` it never undoes is deliberate rather than
forgotten — the runner unlocks the tracer for the whole case, so re-locking would take the network
away from the checks that run after it. It is commented as such.

#### Recorded, not fixed — three latent holes in the replay's geometry compare

All three measured **inactive on this build** (C/B/A: 0 unmatched edges, 0.0 worst match residual),
which is why they are recorded rather than repaired. They are in `_graph_geometry_delta`:

1. **The per-edge match residual is computed and discarded.** `best` — how far the matched partner
   actually is — is used only to pick the orientation, so an edge matched to a partner **141 m
   away** contributes a direction verdict and is not itself an error.
2. **No "unmatched" counter.** If the nearest B point is an interior vertex of every B primitive
   there is no candidate at all, and that edge silently contributes **0 reversals** — the same
   value as a perfect match.
3. **The Hausdorff is over point *sets*.** A pure permutation of positions among the points is
   invisible to it.

⚠️ **And the acceptance threshold is a live artist parameter.** Both this check and the forced pass
read `graph_params_repair_tolerance` as their own tolerance, which is right in that the solver and
its auditor should agree — and means **an artist who sets 2 mm silences the replay tooth**: today's
margins are **1.18×** on `C_radial` and **1.65×** on `F_bend` (the numbers in the table above).

#### `pf_citygen_mesh` input 0 is NOT dead — it is under-observed

The same audit measured a 2.5 m jitter on `pf_citygen_mesh` input 0, saw `4459 / 2 / 83` city,
block and lot primitives come back identical, and recommended deleting the input. **The finding is
real as measured and the conclusion is wrong**: those three counts are the three things input 0
does not move. Re-measured with the same jitter:

- **output 3 is a pass-through of input 0** — `out_graph` reads `IN_graph` directly — so the
  published graph moves by the full jitter on every case;
- `blocks_id` reads the graph on its **second** input to stamp identity: on `C_radial` the jitter
  moves `block_id` on **1 of 28 blocks and 18 of 774 lots**, and `region_id` with it;
- `s5b_mark` → `s5b_ground` → `s5b_piers` builds the bridge piers from it, and **no case in the
  suite has a bridge**, which is why the merged primitive count never moves.

So input 0 stays and `cases.py` is unchanged. `input0_reaches_an_output` is committed as the
standing proof — output 3 must be input 0 point for point — so that deleting the input, or quietly
re-sourcing the graph output, fails a check instead of passing a primitive-count comparison.
**A bridge case is the gap that remains**: the pier branch is a live consumer of input 0 that the
suite has never executed, which is the same "a mechanism the suite never runs is untested" pattern
as `offset` lot mode (4e-6), `max_fillet_fraction` (4h-2) and the clamp at amplitude (F_bend).

**What this does NOT do.** The loop re-runs the repair; it does not add a repair. §S3 step 3's
node merge and §S5's shallow-arm merge (`merge_angle`) are still unbuilt, so a connection that
those two would rescue is still refused on every pass — the loop just stops refusing it *twice*
for a reason that no longer applies. `selfx_city_merged` on C moved **128 → 131**, which is 4e-1
tracking the junction count (58 → 59) as it always has.

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

#### The clamp is a radius floor and that is not the same as a smooth street — 2026-08-10

**The artist reported an unclamped kink on C's inner ring and the standing hypothesis for it
was wrong.** The hypothesis was that `graph_turn_clamp` still skipped closed prims
(`primintrinsic("closed") → continue`), the failure §4g-D6 predicted for the day the ring
closure landed. Measured on the current build, all three parts of it are refuted:

- the wrangle has **no such skip** — the wrap-around relaxation above shipped with it;
- `OUT_graph2` contains **zero closed prims** in every case, C included. `graph_polypath`
  runs with `closeloops = off` and the ring is split by the radial spokes crossing it, so it
  ships as several open prims and the seam is an interior vertex of one of them;
- `centreline_curvature_within_class` **was** measuring it, and **passed**: 0.852.

**What is actually wrong is that a radius floor cannot see a kink that clears the floor.**
Measured at the clamp's input, C's ring-closure seam is a single vertex turning **19.03°**
against a **2.04° median** on a 14.4 m local at 4 m spacing. The clamp fires once, brings it
to **13.36°**, and stops — because 13.36° over 3.9 m is R = 16.9 m and R_min is 14.4 m, so by
radius it is now legal. κ × R_min = 0.852, comfortably inside the 1.02 slack, and a visible
corner in a 100 m radius ring.

§4f-4's mechanism is **"resample → discrete curvature → smooth κ → clamp to `1/R_min(class)`
→ re-integrate"**, and it names *curvature noise in the traced polyline* as the loudest of
all the things that read as CG. **Only the clamp half was ever built.** The smooth-κ half is
now `pfsg_turn_ceilings`: the per-vertex turn ceiling is the class clamp **tightened** by a
bound relative to the vertex's own neighbourhood — no vertex may turn more than
`turn_smooth_gain` × the mean turn of the ±3 vertices around it **or the median turn of that
same window with the vertex itself included, whichever is larger**, floored at a quarter of the
class allowance so an isolated corner in a straight run asks for a bounded radius rather than
an infinite one. Four properties make it safe:

- **uniform curvature is a fixed point, at every gain > 0** — and **the median term is the only
  reason that is true.** See the correction below: without it the property holds only for
  `gain ≥ 1`, and this parameter ships on a `{0 8}` slider. Independently re-measured on
  `812d55f`: uniform arcs at κ × R_min 0.20–0.95, open and closed, move **0.000 m in 0 sweeps
  at every gain 0–8**, with real spikes still caught;
- **a vertex is never asked to turn less than its own neighbourhood's lower median**, so the
  bound can only bind on a vertex in the strict upper half of its own window. ⚠️ **That is
  not the same as "only on a spike", and this bullet used to claim it was** — see "Two safety
  claims were false" below;
- it is a `min` with the class clamp, so it can never *loosen* it;
- `turn_smooth_gain = 0` restores the previous behaviour exactly, and that is how the A/B was
  measured. The sweep's spread `m` was rewritten as `(φ/φmax − 1)`, which is algebraically the
  old expression for the class ceiling, so gain 0 is bit-identical and not merely close.

⚠️ **It is not surgical and it cannot be made so — this was measured, not assumed.** Several
(gain, floor) pairs were tried looking for one that touches C's seam and leaves A, B and D
untouched. **No such setting exists**, because the seam is not geometrically distinct from a
legitimate corner: at the clamp's input C's seam is 18.1° at **25.4×** its neighbourhood while
A's *hand-drawn* arterial corner at (−59.6, 9.9) is 11.0° at **53.9×** — the drawn corner has
the higher contrast, and both leave the clamp at 0.85–0.89 of R_min. What makes one read as a
defect is that it sits inside a ring, and no local measure sees that. The floor therefore
decides *how much* smoothing, not *where*:

| floor | C's seam | suite |
|---|---|---|
| 0.50 | 13.4° → ~11.9°, still visible | 17 → **19** failing (a flipped face in C, 2 bowtie lots in B) |
| **0.25** | 13.4° → **7.26°**, kink gone in the render | 17 → **18** failing (3 bowtie lots in B, and B alone) |

##### Before and after, per criterion

| | before | after |
|---|---|---|
| C ring seam, worst vertex turn | 13.36° (19.03° at the clamp input) | **7.26°**, spread over 5 vertices |
| C outer ring seam | 13.20° (18.10° in) | **5.63°** |
| `centreline_curvature_within_class` A / B / C / D | 0.889 / 0.841 / 0.852 / 0.889 | **0.364 / 0.252 / 0.463 / 0.364** |
| F_bend (the deliberate 90° corner) | 1.004 | **1.004, bit-identical** — and so is E |
| `no_sweep_fold_after_trim` max ratio A / B / C | 0.269 / 0.104 / 0.214 | **0.127 / 0.063 / 0.153**, 0 folds throughout |
| `city_is_fully_paved` · `lots_clear_of_junctions` · `selfx_junction_surface` · seam | 0 · 0 · 0 · 0.0001 m | **unchanged** |
| suite | 17 failing | **18 failing** |

**The one new failure is `lots_are_simple_polygons` on B — 3 self-touching parcels.** That is a
pre-existing S8 defect class that C has failed with 49–57 parcels throughout; it is exposed in
B because the centreline moved, and it is an S8 bug, not this one. Recorded here rather than
absorbed: the number went up, and a number going up is the thing this file exists to catch.

##### ⚠️ The fixed-point claim was false below gain 1, and it shipped — 2026-08-10

Corrected after an independent audit of `2aba0a9`. The first bullet above previously read
*"on a circular arc every neighbour turns the same, so the bound is `gain ×` the vertex's own
turn and never binds"*, and the same sentence stood in the code comment and in the commit
message. **It is only true for `gain ≥ 1`.** Below 1, `gain × φ < φ` at *every* vertex of a
correctly fitted arc, so the solver was asked to flatten geometry that was already right; it
burned its whole 200-sweep budget, stalled, and shipped the residual. Even at exactly 1 the
bound bit at the **ends** of a curved run, where the ±3 window pulls in the straight
neighbours and drags the mean below the vertex's own turn.

Swept through the committed suite over the whole shipped `{0 8}` range:

| gain | before | after |
|---|---|---|
| 0 | 16 failing | 16 |
| **0.5** | **25 failing** | **17** |
| **1** | **25 failing** | **17** |
| 2 (shipped default) | 17 | **17, and every value bit-identical** |
| 4 | 17 | 17 |
| 8 | 17 | 17 |

The eight extra failures at 0.5 were `centreline_curvature_within_class` on **C_radial**
(spike 1.100) and on **F_bend** (spike **1.688** — the case that exists to run this mechanism
at its design amplitude, worst hit of all), plus `turn_clamp_control_rig` on all six cases:
its `bend90` arc was flattened from R = 26.8 m to **57.8 m** and `bend135` stopped converging
at all. F_bend at gain 0.5 now reads **1.004, the same as the default**. The failing *set* is
now identical at 0.5, 1, 2, 4 and 8.

⚠️ **What hid it, and it is the more useful half of this finding.** `ring_legal` came back
bit-identical at *every* gain, and the control rig asserted exactly that — so the fixed point
looked proven. It was not: `ring_legal` clears the bound through the **floor**, not through the
fixed point. At κ × R_min = 0.223 the floor `0.25 × cls` already exceeds its own turn. The
self-excluded mean binds on a uniform arc precisely when **`gain < 1` *and* `κ × R_min > 0.25`**,
and no ring in the rig was above the floor. A fixed-point assertion satisfied by the wrong
mechanism is not an assertion.

**The cure is a `max` with the local median.** A spike is a minority of one in a window of
seven, so the median is blind to it and the `gain × mean` term still governs there; a uniform
arc, and the interior *and ends* of a run of **four or more** equally turning vertices, all
have the vertex's own turn *as* the lower median, so the ceiling cannot fall below it. The
**lower** median is taken, so a truncated window at a prim end errs toward smoothing rather
than toward letting a spike through — and that, exactly, is why a tightening spiral binds
there; see below. **At the shipped default of 2 this changes nothing** — the median can only ever raise
a ceiling, and at a real spike `2 × mean` is already above it — which the A/B confirms number
for number, C's 41 bowtie lots and 270 merged-city crossings included.

**And `turn_clamp_control_rig` now sweeps the gain over all six values**, so the range is
exercised by the suite rather than by an audit. **Fifth mechanism in this project to ship green
and unexercised at a value the suite never ran**, after `offset` lot mode (§4e-6),
`max_fillet_fraction` (§4h-2) and the clamp amplitude (§S3b). The cure is the same one every
time: adding a parameter means adding a case.

**`turn_smooth_ratio` ships on every graph prim** and
`centreline_curvature_within_class` now fails on it, so a kink that is legal by radius can no
longer pass silently — which is exactly how this one survived.

⚠️ **But the detector and the fix used to be the same code, and it carried one bit.** Until
2026-08-10 `max_turn_spike` **read the solver's own `turn_smooth_ratio` attribute** instead of
recomputing anything. Two consequences, both found by audit:

- it reported what the solver believed when it stopped, so it was **blind to everything the
  pipeline does after the clamp** — the failure mode §4e names as "assert the output, not the
  intent";
- the solver stops at `tol = 1.01` against this check's `1.02` slack, so every converged prim
  reported "≤ 1.01" by construction. **A, B, C and D all read a flat 1.010** — a single bit.

It is now recomputed from the **shipped centreline**, the same discipline `max_kappa_over_clamp`
already followed, with the solver's own verdict reported alongside as `solver_turn_spike` so the
two disagreeing is visible rather than silent. On the current build they agree to three decimals
on every case, which is itself the finding: nothing between the clamp and `OUT_graph2` moves the
centreline. At `gain = 0` the recomputed spike degenerates to exactly `max_kappa_over_clamp` —
now by construction rather than by coincidence, since the ceiling *is* the class allowance there.

##### ⚠️ Two safety claims were false, and both shipped — 2026-08-10

Acting on an independent audit of `812d55f`. **Shipping a false documented safety property on
this parameter is the exact defect the commit existed to remove**, so this pass deletes the
claims and states the measured rule instead. What the audit *confirmed* and this pass did not
disturb: the fixed point is real (uniform arcs at κ × R_min 0.20–0.95, open and closed, move
0.000 m in 0 sweeps at every gain 0–8, real spikes still caught); the default is byte-identical
and provably so, because `lower_median(window incl. self) ≤ 2 × mean(neighbours)` for *every*
window with supremum exactly 2.0, making the median term **a mathematical no-op for gain ≥ 2 on
any input**; and the recomputed `max_turn_spike` is ~5× more sensitive than the class residual.

**(a) The spiral claim was false.** `pf_streetgraph.vfl` and the bullet above said a
monotonically tightening spiral "has the vertex's own turn *as* the median, so the ceiling
cannot fall below it and the bound cannot bind." It binds. `pfsg_median_lower` takes index
`(m−1)/2`, and in a **truncated** end window every other member is smaller than φ_i, so the
lower median lands two positions below it. Re-measured on a 24-vertex spiral turning 1° → 7°
per vertex at 4 m, R_min 26.8 m (every turn inside the 8.55°/vertex class allowance, so this
is the noise bound and not the radius floor):

| gain | binds at | ratio |
|---|---|---|
| 0.25 / 0.5 / 0.75 | interior vertices 21, 22, 23 of 1..23 | 1.044 / 1.042 / **1.084** |
| 1.0 | same three | 1.026 / 1.042 / 1.084 |
| ≥ 1.25 | nowhere | — |

Mirror-symmetric at the **leading** end when it tightens the other way. **The comment's own
justification was the cause**: "lower … so a truncated window at a prim end errs toward
smoothing" is precisely what makes the spiral bind, and both sentences cannot be true.
**The lower median stays; the claim goes.** The consequence is mild and self-healing — the
audit measured 9 cm moved, converging to 1.010.

**(b) The help text on `graph_params_turn_smooth_gain` was false.** It said "…while a vertex
that is merely part of a curve is never touched". At the shipped default a short curve is
treated as a kink **by construction**. For a run of `k` equally-turning vertices between
straight legs the ratio is `6 / (gain × (k − 1))`, capped by the floor at `κ × R_min / 0.25`:

| | k=2 | k=3 | k=4 | k≥5 |
|---|---|---|---|---|
| gain 2 | 2.26 (floor-capped) | **1.50** | 1.000 | 1.000 |
| bites at gain 0.5 / 1 / 2 / 4 / 8 | k ∈ {2,3} | {2,3} | {2,3} | {2} · {} |

Measured instance: a **14.5° turn drawn over 3 vertices at 4 m spacing — R = 47.3 m against a
26.8 m R_min, κ × R_min = 0.566, legal by radius with room to spare — is bound at ratio 1.50**
and flattened. A run of **k ≥ 4** fills the lower-median slot of the 7-wide window, so its
ceiling equals its own turn *exactly* (ratio 1.000) and the bound never binds at any gain;
that threshold is the ±3 window width, not the median. The *code comment*'s wording ("strict
upper half of its own window") was correct — the help had generalised it into a promise the
mechanism does not keep. Rewritten to state the rule above.

##### The control rig was calibrated to one slider position, and now is not

`_RIG_INPUT_KAPPA = {"foldback": 10.5243, "ring_tight": 1.3423}` was a pair of constants
measured at `turn_radius_scale = 2`, while κ × R_min is **linear in the scale** and the check
reads the live parm; and the authored bend legs were sized for R_min = 26.8 m, so `bend90`'s
80 m legs cannot host a 90° turn of R = 107 m at scale 8. Full suite at scale 1/2/3/4/6/8 was
**24 / 17 / 24 / 23 / 25 / 24** failing, with the rig itself contributing six of the ~7 extra
at every non-default scale. Two cures, both landed:

- **every authored rig coordinate is scaled by `R_min / 26.8`**, so a rig authored feasible
  stays feasible and one authored infeasible stays infeasible at every scale (the resample
  step stays at the pipeline's real 4 m, and `circle()` derives its vertex count from the
  scaled radius so `ring_legal` stays a circle instead of becoming a 188-gon with a kink);
- **the infeasible pair's bound is measured off the input geometry** (`kappa_in`) instead of
  hard-coded.

**Result: `bend90`, `bend135`, `bend135_r18`, `bend90_r10`, `foldback`, `ring_legal` and
`ring_tight` are now correct at all 6 scales × 6 gains** — the worst open-bend delivery over
all 36 combinations is **1.0022 × R_min**, against a 1.25 allowance. ⚠️ **The suite counts did
not move** (24 / 17 / 24 / 23 / 25 / 24), because the rig is one boolean per case and
`ring_square` still trips it — but its failures are now *attributable*, and they are real:

**⚠️ THE NOISE BOUND BLOCKS THE CLOSED-RING SOLVE ENTIRELY AT R_min ≥ 40 m.** Measured with the
rig's **original, unscaled** 300 m ring, so it is not an artifact of the sizing above:

| `turn_radius_scale` | gain 0 (class only) | gain 2 |
|---|---|---|
| 3 | κ 15.787 → **1.008**, converged, 55 sweeps | κ **15.787 → 15.787**, moved 0, 50 sweeps (stall cap) |
| 4 | 21.049 → **1.008**, converged, 70 sweeps | **21.049 → 21.049**, moved 0 |
| 8 | 42.097 → 1.216, not converged, 200 | **42.097 → 42.097**, moved 0 |

The solver **does not move the ring at all** with the bound on. The seeded fillet is
open-prim-only, so a closed prim starts at a bound ratio of ~4 × κ × R_min (corner φ against a
`0.25 × cls` floor with zero neighbours), no sweep improves the combined score, and it stalls
out and returns the input. This is the same failure *shape* as the bug this section records —
the noise bound stopping the class clamp from being satisfied — resurfacing at a different
parameter value, and it is the same root cause as C's `not_converged` at scale 6/8 below.
Recorded, **not fixed**: it wants the seed extended to closed prims, which is its own pass.
Sizing the rig from R_min improves it (scale 3 reaches κ 1.013 rather than staying at 15.787).

##### The gain sweep asserted a verdict and recorded no numbers, and could not see over-smoothing

`value["gain_sweep"]` was the string `"all 6 gains clean"` or a dict of names, so **the five
non-default cooks were discarded** and the baseline diff could never see a non-default gain
regress — the exact failure the rig exists to prevent, one level up. It now records the full
per-gain, per-rig measurement.

And `solved()` bounded R only from **below** (`R_delivered > half_width`), so **over-smoothing
was not asserted at all**. It is now bounded on both sides. The old lower bound is gone rather
than kept: R_min is `half_width × turn_radius_scale`, so `κ ≤ slack` already implies
`R_delivered > half_width` for every scale above 1.02, and at the slider's minimum of 1
R_min *equals* half_width and the old form was unsatisfiable by construction — it asserted
nothing anywhere it could hold.

**Proved on a deliberately over-flattened build.** The median term was reverted to `level = 0`
in a scratch copy of the include, placed ahead of the repo on `HOUDINI_VEX_PATH` (the shipped
file was never touched), and the rig run at gain 0.5:

| rig | R delivered | R / R_min | old verdict | new verdict |
|---|---|---|---|---|
| `bend90` | **57.79 m** (26.55 shipped) | 2.156 | pass | **fail** |
| `bend90_r10` | **63.37 m** | 2.365 | pass | **fail** |
| `ring_square` | **82.65 m** (26.80 shipped) | 3.084 | pass | **fail** |
| `bend135` / `bend135_r18` | 23.7 m, not converged | 0.88 | fail | fail |

The old form caught **2 of 5**, and only through `bend135`'s collateral `converged == 0`; the
new form catches **5 of 5**. At gain 2 the reverted build is identical to the shipped one
number for number, which is an independent empirical confirmation that the median term is a
no-op at the default.

The two caps are 1.25 × R_min for the four open bends and 2.0 × for the closed square, and the
difference is measured, not convenience: between two pinned endpoints there is one right answer
and the bends land on it (≤ 1.0022 everywhere); a closed ring's constraint set admits a family
from "four arcs at R_min" to "a circle", and a tighter noise bound walks toward the round end.
**Newly exposed on the shipped build and recorded:** `ring_square` delivers **1.49 × R_min at
gain 0.5** and 1.12 × at gain 1 at the default scale (3.22 × and 2.07 × at scale 1), burning
all 200 sweeps, because a nearly-uniform run's *lower* median sits a hair under the vertex's
own turn and the noise residual never quite clears `tol`. At gain ≥ 2 it is exactly 1.00 ×.

##### Two metrics that agreed by luck, and one assertion that is absent

- **`_turn_ceilings` measured the turn with `acos(dot)` — a true 3D angle — while the VEX uses
  `abs(atan2(cross(u,v).y, dot(u,v)))`, XZ-projected.** Identical while the graph is planar
  (2.6e-8 rad over 497 vertices) and silently divergent the day a centreline acquires Y, which
  §S5b's terrain will bring. Both are now `_turn_at`, a direct mirror of `pfsg_turn_at`; the
  whole default suite is byte-identical across the change. **And nothing asserted the graph was
  planar** — `graph_is_planar` tests segment crossings, not Y. `graph_planar_y` is now a
  standing check: y spread **0.0** on all six cases.
- **At `gain = 0` the spike bound collapses to the class allowance, so the smoothness assertion
  is simply absent.** "gain 0 → 16 failing, gain 2 → 17" compares two runs with *different
  assertions in force*, and the missing failure at 0 is this check no longer testing anything
  `max_kappa_over_clamp` does not already test. Recorded in `_turn_ceilings`, not fixed:
  pinning the check to a fixed gain would make it stop measuring the build's actual parameter.

##### Real at non-default scale — recorded, not fixed

Not rig artifacts; each reproduces the audit's finding on the current build.

| | scale | reading |
|---|---|---|
| C `centreline_curvature_within_class` | 6 | 1.026, over 6, **not_converged 1** |
| C `centreline_curvature_within_class` | 8 | 1.093, over 20, **not_converged 2** |
| C `every_corner_is_an_arc` | 3 | `radius_fit` 1.407, mixed_class 135 |
| `lots_are_simple_polygons` newly on **A** | 1 / 3 / 4 / 6 | 1 self-touching parcel each |

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

   ⚠️ **That threshold mismatch is now the visible defect the artist circled, and it has
   coordinates. Measured 2026-08-10 on C_radial.** Ranked by what is left of a street after
   its two junction cuts (`s5j_streets` trim_start/trim_end against the centreline length):

   | left | length | trim | prim | from → to | class | width |
   |---|---|---|---|---|---|---|
   | **6.24 m** | 24.00 | 17.75 + 0 | 60 | (−289.34, 227.08) deg 4 → (−273.90, 245.45) deg 1 | local | 14.4 |
   | 6.20 m | 18.00 | 11.80 + 0 | 73 | (55.98, 379.60) deg 4 → (58.57, 397.41) deg 1 | arterial | 26.8 |
   | 13.13 m | 23.99 | 10.86 + 0 | 27 | (88.34, −372.82) deg 4 → (93.71, −396.20) deg 1 | arterial | 26.8 |
   | 15.91 m | 49.84 | 19.88 + 14.05 | 16 | (72.04, −70.82) → (29.93, −96.48) | local | 14.4 |

   Ranked by *surviving length ÷ width*, prim 60 is the worst in the −X/+Z quadrant at **0.43**
   (next: 0.80, prim 48 at (−60.42, 16.82)). ⚠️ **The worst in the whole city is prim 73 at
   (58.57, 397.41) — ratio 0.23** — but it is +X, so it is not the circled one; name it anyway,
   because it is the same defect one notch worse.

   **Prim 60 is the one in the lower-left quadrant and it is the best match for the artist's
   green circle.** What ships there is a **6.24 m tongue of a 14.4 m-wide road** — pavement
   wider than it is long — sticking out of a four-way junction's patch and stopping flat, with
   the junction boundary making a square jog where the mouth meets it. It is **not** a
   degree-2 bend (the published graph has **zero** degree-2 nodes) and **not** a failed
   degree-3 patch (all 39 of C's degree-3+ nodes have one); it is a 24 m arm that
   `graph_prune_min_edge_len` = 13 m keeps and the junction mouth then eats.

   `trim_leaves_road_standing` passes on all of these because `s5j_params_min_end_segment` is
   1.0 m and 6.24 > 1.0. **The floor is the wrong quantity**: what makes a leg legible is its
   length against its own *width*, not against a fixed metre.

   ✅ **FIXED 2026-08-10 — `s5j_params_min_standing_widths`, default 1.0.** The floor is now a
   ratio: a street must be left standing at least this many times its own **width**. It is
   enforced where the quantity exists, which is *after the trims are known*, so the junction
   solve **runs twice** — `s5j_pre_resample` → `s5j_pre_fuse` → `s5j_pre_solve` measure it,
   `s5j_tongue_mark` picks out the arms that fail, `graph_drop_tongue` removes them from the
   graph, and the shipped `s5j_solve` then runs on what is left. The premeasure nodes are
   **copies of the shipped ones**, not reimplementations, so the measurement cannot drift from
   what ships; the cost is one extra junction solve per cook.

   ⚠️ **It is upstream of `graph_degree_final` and OUT_graph2 on purpose.** Dropping the arm
   after the solve would ship a *graph* containing a street the *city* does not have. The key
   between the two streams is `edge_id`, because `s5_resample` and `s5_fuse` sit between them
   and prim numbering is not a contract.

   **Two rails, and both are load-bearing:**
   * **Only a dead-end arm goes.** A street between two junctions carries the graph and
     deleting it disconnects the city — the answer *there* is §S3's node merge.
   * **The junction keeps three arms.** At most `degree − 3` may go from any one node, worst
     ratio first, `primnum` as the tie-break. Taking a node to degree 2 leaves two streets
     meeting at a corner that the S3b clamp has already run past — it pins prim endpoints, so
     nothing downstream can relax the kink. That is the same blocker §S3's node merge hits.

   **Measured:** 11 arms dropped in C, 2 in B, 0 in A/D/E/F. Worst ratio before → after:
   C **0.231 → 0.819**, B **0.377 → 1.049**. Both named defects are the top two entries of the
   drop list — prim 73 at (58.6, 397.4) ratio 0.231 and prim 60 at (−273.9, 245.4) ratio 0.434.
   Dead ends fell with them: **C 28 → 17 total, 13 → 8 interior; B 19 → 17, 4 → 3.**
   `every_mouth_has_a_road` stayed **0** on all cases — the junctions re-solve at the lower
   degree rather than keeping a mouth for a street that no longer exists.

   `trim_leaves_road_standing` now **asserts the ratio**, scoped to what the mechanism can
   actually remove (dead-end arms off degree ≥ 4), and *records* `under_ratio_all` so the rest
   stays visible: **3 on C_radial** (streets between two junctions, 0.819–0.849, all arterials)
   and **1 on E_short_t**, whose 20 m arm hangs off a degree-3 T at ratio 0.208 and is the whole
   reason that case exists. Widening the rails is node-merge work, not a threshold to turn up.

   **`G_tongue` is committed with it** and reproduces prim 60 exactly: a 24 m `local` arm off a
   four-way of 26.8 m arterials. Proven to have teeth by sweeping the parm — at
   `min_standing_widths` = 0 the arm ships with **6.60 m standing at 14.4 m width, ratio 0.458**
   (the real prim 60 is 6.24 m at 0.434); at the default 1.0 it is gone and the node re-solves
   as a clean T. Adding a parameter means adding a case.

   ⚠️ **One number moved the wrong way and it is recorded, not swept up.**
   `plaza_disc_is_clear.gap` on C went **2.45 → 37.86 m**. Two of the dropped arms
   ((95.0, 28.5) and (−94.2, 26.5), both arterials at ratio ~0.78) were the ones pointing *at*
   the plaza and stopping 62–66 m from its centre — they are stubs precisely **because** 4e-2
   deletes the plaza ring they should have joined. The check was already failing on `built`
   (100% of the disc built over); when the ring ships, those arms become degree-2 or -3 and the
   leaf rail exempts them automatically. Nothing was special-cased to keep the number down.

   The other candidate fix — sizing `graph_prune_min_edge_len` by the junction clearance the
   arm's class needs — is **not** the one taken: pruning runs before widths and classes exist,
   and the clearance depends on the *other* arms at the node, which pruning cannot see.
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

✅ **THE BULB IS BUILT — `s5j_bulb`, `s5j_params_culdesac_radius`, default 14.0 m, 2026-08-10.**
Every dead end that survives S2/S3 now terminates in a turning circle instead of stopping flat.
It is the single most visible change of the three fixes in this round, and it is the reason
`dead_ends` is *recorded* rather than asserted: a dead end that ends in a bulb is a cul-de-sac,
which §S3 says is the exception and not a defect.

**It is emitted as an ordinary `is_junction_patch`**, through the same
`is_cap` / `after_corner` / `capc` / `sw` vocabulary every other patch uses, so `s5j_surface`
raises its sidewalk band and kerb riser and `blocks_kerb` chains its boundary into the block
loops with **no special case at either end** — the run `blocks_kerb` collects from a cap-out to
the next cap simply *is* the bulb. The only thing that knows it is a bulb is `is_culdesac`.

**Geometry.** The centre sits on the street's own axis `dcut` behind the mouth, so the two cap
corners at ±h land exactly on the circle: `R² = dcut² + h²`. Solved in the street's frame **at
the cut**, like every other mouth here — the node frame is up to 30.9° out of square on a curved
arm (4h-1). `R` is floored at **1.35 × the road's half-width**, because a bulb narrower than the
road it ends is not a turning circle and at `R ≤ h` the mouth corners fall *outside* the circle
and the boundary inverts.

**Three things it refuses to do, each one measured rather than anticipated:**

1. ⚠️ **It cannot live inside the junction loop.** Whether a dead end has room depends on what
   its *other* end already gave up to a junction mouth, and **a VEX wrangle does not see its own
   attribute writes** — `prim(0, "trim_start", …)` read back in a later pass of the same wrangle
   returns the input value. So it is a separate node downstream of `s5j_solve`. Built inside it,
   E_short_t's 20 m arm — which has 3.0 m standing after its junction — had 12 m taken off it
   and shipped `min_standing_m` **−9.0 m**, `every_mouth_has_a_road` **2** and **25** junction
   self-intersections.
2. **A bulb is a road, and a road may not be laid on another one.** It reaches `R − dcut` past
   the node into whatever is there. Without a clearance test against every other centreline (and
   against the bulbs the same pass has already accepted, which no geometry read can see) the
   bulbs put **294 m² of lots on the road and 174 m² inside junction patches** in the one corner
   of C_radial where two streets already drive through each other.
3. **A bulb is not a junction eating the street.** It writes `culdesac_trim` alongside the trim,
   and `trim_leaves_road_standing` adds it back before the width ratio — otherwise every bulbed
   dead end reads as the §S5 tongue defect it has nothing to do with (C went to `under_ratio` 1
   on a street whose junction end had not moved at all).

**Measured:** bulbs **A 8 · B 17 · C 13 · D 8 · E 2 · F 3 · G 3**. `culdesac_bulbs_are_circles`
is committed with it — circle fit ≤ 3.0e-5 m, radius never under the floor, both mouth corners on
the circle to 3e-5 m, and it fails rather than skips if the rig cannot run. `every_corner_is_an_arc`
skips `is_culdesac` patches and *reports how many it skipped*, because it sizes a corner from the
two street classes meeting at it and a turning circle has one incident street: unexempted it read
a radius error of **18.09 m** on every dead end in the city.

**Cost:** `selfx_city_merged` B 89 → 103, C 116 → 128 — that is 4e-1, road-and-patch
interpenetration *per junction*, and a bulb is a junction patch; it tracks the count. Everything
in the no-regression set held: `city_is_fully_paved` · `lots_clear_of_junctions` ·
`selfx_junction_surface` · folds · `every_mouth_has_a_road` · `graph_planar_y` · `selfx_roads` ·
`block_boundary_closes` all **0**, seam still 0.0001 m, suite still **18 failing**.

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

#### The other end of the same seam: lots ON the road at a dead end — 2026-08-10

The artist marked lot geometry overlapping the road at four dead-end stubs in C. **Nothing in
the suite could see it, and the reason is the fourth instance of a check missing by measuring
the wrong seam.** `city_is_fully_paved` looks for the corridor being *under*-covered.
`lots_clear_of_junctions` looks for over-coverage **inside a junction patch** — and a degree-1
node has no patch, so every dead end in the city was unmeasured. Both read **0 on all five
cases** while C shipped **48.3 m² of lots on a 26.8 m arterial**.

**Root cause, measured, and it is not in S7.** The two nodes at **(251.39, −87.10)** and
**(249.37, −93.47)** are **6.68 m apart** and each is *inside the other street's pavement*
(6.68 m against a 13.40 m half-width). Neither is connected. `graph_extend` found the pair —
`d_extend` is 90 m, and at 6.68 m it is inside the snap range where the code's own comment says
*"extending means snapping"* — and **refused it on `max_curvature`**: the total turn is
**88.4°** against a 25° limit. S7 then does what it is told: collect-and-close chains frontage
runs, junction corner runs and dead-end caps into loops with no test that a run lies outside
the pavement, so the wedge between two unmerged stubs closes into a block and S8 subdivides it
into parcels sitting on the arterial.

**`max_curvature` at snap range is a missing capability wearing a rule's clothing.** It bounds
*a connector being bent*, and below `min_edge_len` no connector is built at all — the two ends
are moved onto one point. What comes out is a street turning a corner, and S3b solves corners:
its control rig converges 90° and 135° onto a tangent arc. So at snap range the rail that binds
is **`min_join_angle` on the two legs** — the rail this parameter was written for (*"every pair
of legs at the new node must clear it"*). A fold-back, where the two streets double back
alongside each other, has a small leg angle and is still refused; this pair reads 91.6° against
a 45° floor and merges.
⚠️ This paragraph used to add that §4c's ledger records `min_join_angle` as **never having
fired**. That record is refuted — see §4c "Every promoted parameter, measured": 45 → 5 moves all
four outputs on B_grid, where it is rejecting extensions into existing junctions.

| | before | after |
|---|---|---|
| `lots_clear_of_roads` C | **48.2 m² in 1 patch** at (251.5, −97.8) | **0.0 m²** |
| `lots_clear_of_roads` A / B / D | 0.0 / 0.0 / 0.0 | unchanged |
| C dead ends (total / interior) | 33 / 18 | **31 / 16** |
| C `lots_are_simple_polygons` | 52 lots | **44** |
| C `selfx_city_merged` | 336 | **302** |
| C `centreline_curvature_within_class` | 0.463 | 1.009 — the new 90° corner, on the clamp and inside the 1.02 slack |
| `city_is_fully_paved` · `lots_clear_of_junctions` · `selfx_junction_surface` · folds · seam | 0 · 0 · 0 · 0 · 0.0001 m | **unchanged** |
| suite | 18 failing | **17 failing**, and that now includes the new check |

**The new check is `lots_clear_of_roads`** — lot area against the road surface *anywhere*,
junction or not, rasterised like its two neighbours because a block and a patch are both
non-convex. It fails on the pre-fix build (C 48.2 m²) and passes after. Committed with the fix
and wired into the runner beside `lots_clear_of_junctions`, which it exists to complete.

#### ⚠️ AREA WAS NOT ENOUGH EITHER. The fifth wrong seam — 2026-08-10

The artist marked lot geometry on the road at four dead-end stubs in C_radial, and
`lots_clear_of_roads` read **0.0 m² — correctly.** Re-rasterised at **0.5 / 0.2 / 0.1 / 0.05
and 0.01 m**, whole-city and in 80 m windows around every one of C's 28 degree-1 nodes, the
answer stayed 0.00. **No lot INTERIOR is on the road. What is on the road is lot BOUNDARY:
39 lots, 1,290 m of it.**

⚠️ **An exact Sutherland–Hodgman clipper was tried first as the cross-check and it lied**,
reporting 536.9 m² over 190 lots. S–H is only exact for a convex *clipper*; on the non-convex
lots here the result carries degenerate connector edges and its area is meaningless. The 0.01 m
raster refuted it on three separate lots. **Recorded because it would have been a very
convincing wrong answer** — it agreed with the artist.

**Root cause, and it is in S8, not S7.** `pfsl_clip` (`pf_streetlots.vfl`) is Sutherland–Hodgman
half-plane clipping, and its own comment claimed *"a mildly concave block degrades to a convex
lot rather than to a self-touching one"*. Measured false. A block that wraps a dead-end stub is
a **U, and the notch is the stub's road**; S–H on a concave subject returns one ring joining the
disjoint pieces with a **zero-width bridge** — two coincident edges traversed in opposite
directions along the clip line. Control case, run standalone:

```
U    = (0,0)(100,0)(100,60)(60,60)(60,20)(40,20)(40,60)(0,60)   # notch = the stub
clip = keep z >= 20                                             # split across the mouth
ring = (100,20)(100,60)(60,60)(60,20)(40,20)(40,60)(0,60)(0,20)
```

The two prongs are correct and `pfsl_area` returns **exactly 3200 = their true area**, because
the bridge encloses nothing. But the ring crosses the notch **twice** — on `(60,20)→(40,20)` and
on the closing `(0,20)→(100,20)` — so the parcel ships with two edges down the middle of the
stub's pavement. That is why `lot_area` is exact, `lots_tile_blocks` passes, `city_is_fully_paved`
passes, `lots_clear_of_junctions` reads 0 and `lots_clear_of_roads` read 0: **every one of them
integrates area, and the defect has none.** Blocks are clean — 0 m of block boundary inside the
road — so it happens during subdivision, not in S7.

**Six clusters in C, all at interior dead-end stubs** (the artist circled four of them):

| cluster | nearest degree-1 node | worst lots |
|---|---|---|
| (−90, −273), a 94 m band | 2266 (−96.98, −272.03) and 733 (−135.75, −246.53) | prim 10 · 83.3 m, prim 56 · 37.9 m, then ~14 parcels at 27.6 m each |
| (−170, −85) | 997 (−140.17, −63.61) | prim 100 · 88.5 m, prim 123 · 55.4 m, prim 99 · 54.5 m, prim 124 · 48.7 m |
| (−60, 190) / (42, 200) | 1798 (−39.59, 124.33) · 1878 (18.39, 124.36) | prim 530 · 94.1 m, prim 547 · 54.1 m, prim 536 · 50.8 m, prim 535 · 42.2 m |
| (−41, −70) | 190 (−37.64, −54.19) | prim 178 · 49.3 m |
| (0, −10) | 1378 (62.42, 18.74) · 1306 (−60.42, 16.82) | — |
| (245, 0) | 1469 (247.35, −4.95) | — |

**The check now measures both, and `edge_m` is the one with teeth**: metres of lot boundary
strictly inside the road mask, the mask eroded by one cell first so a frontage edge lying *on*
the kerb — where every legitimate lot edge lies — cannot count. A 0.5 m grid, sampled at 0.25 m.
Values: **A 0.0 · B 26.1 · C 1290.6 · D 0.0 · E/F skip (no lots)**. Suite **17 → 19 failing**;
no other value moved, and baseline.json is rebaselined with this commit.

✅ **FIXED 2026-08-10 — `pfsl_clip_multi`.** A clipper that returns **every** piece, plus a
`lots_subdiv` recursion that pushes all of them onto its queue. It is the same defect §4e already
records as *"non-convex blocks produce bowties that pass the area check because the pinch has zero
area"* — now with a named mechanism, a control case and a committed rig instead of a category.

⚠️ **Pairing crossings in sorted order is NOT sufficient, and the control case above is exactly
why.** Two of the U's vertices lie *on* the clip line, so the notch mouth produces **no crossings
to pair** and the naive pairing hands back the bridged ring unchanged. What is built instead is a
boolean: the kept region's boundary is (i) the polygon boundary that survives, cut at the
crossings, plus (ii) the stretches of the **clip line** the kept region actually borders — decided
by testing, on each span between consecutive boundary hits, whether the interior is immediately on
the keep side. Edges lying *along* the line are dropped from (i) and re-derived by (ii), which is
what separates the notch mouth (region on the far side, dropped) from the bar's own top edge
(region on the near side, kept). The directed edges are then chained by endpoint; each closed
chain is one piece. On a **convex** subject the first chain starts on the vertex S–H started on
and visits the same points in the same order, so it is a drop-in — asserted, because otherwise
every convex block in the city gets re-cut through a different `rand()` sequence for nothing.

**Measured, whole suite:**

| | before | after |
|---|---|---|
| `lots_are_simple_polygons` | B **3** · C **41** (40 shipping as buildable) | **0 · 0**, all six cases |
| `lots_clear_of_roads.edge_m` | A 0.0 · B **26.1** · C **1290.6** | A 0.0 · B **0.0** · C **15.9** |
| `selfx_city_merged` | A 9 · B 95 · C **270** · D 9 · F 2 | A 9 · B 94 · C **139** · D 9 · F 2 |
| lots | A 83 · B 618 · C 773 | A 82 · B 619 · C 782 |
| `city_is_fully_paved` · `lots_clear_of_junctions` · `selfx_junction_surface` · folds · seam · `every_mouth_has_a_road` · `graph_planar_y` | 0 · 0 · 0 · 0 · 0.0001 · 0 · 0 | **unchanged** |
| suite | 19 failing | **16 failing** |

⚠️ **C's residual 15.9 m is a different defect and is NOT this one.** It is a single 56 m²
`unbuildable` sliver at (−107.9, −268.0) whose long straight cut runs 0.06–0.4 m from a curved
kerb on a `local` street — the block boundary and the pavement effectively coincide there, so a
straight cut inside the block still lands inside the eroded road mask. The parcel is simple, and
`lots_are_simple_polygons` is 0. It belongs with `selfx_roads` / the S7 kerb seam, not with S–H.

**`lot_clip_control_rig` is committed with it** (`tests/citygen/checks.py`), and it runs the
shipped clipper on three cases: the U above (the degenerate one — the cut lands *on* the mouth),
the same U cut at z = 40 (the common one — the cut lands *through* the notch), and a convex
control for the drop-in assertion. Proven to have teeth by re-injecting the old S–H clipper:
`u_keep_top` comes back as **one 3200 m² ring** instead of two of 1600, and `u_mid` ships **2
edges through the open notch**. The notch test alone has no teeth on the doc's own control case —
S–H's bridge there lies *along* z = 20, on the notch boundary rather than through it — which is
precisely why `u_mid` is in the rig. A rig that only runs the degenerate case is decoration.

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
| **`turn_smooth_gain` fixed point below gain 1** (2026-08-10) | **audited** — the fixed point is real, re-measured independently on `812d55f` at κ × R_min 0.20–0.95, open and closed, 0.000 m in 0 sweeps at every gain 0–8 | Acting on an independent audit of `2aba0a9`/`68f6a21`/`2fe1725`. The bound is `max(gain × mean(neighbours), lower_median(window incl. self))`; the whole shipped `{0 8}` range sweeps to the same 17 failing and the same failing *set*, default bit-identical. See §S3b "The fixed-point claim was false below gain 1" |
| **Two false safety claims on the same parameter** (2026-08-10) | **implemented, unverified** | Acting on an independent audit of `812d55f`. The spiral claim and the "merely part of a curve is never touched" help text were both **measured false** and are deleted; the real rule (`6/(gain × (k−1))`, invisible for k ≥ 4) is stated instead. `turn_clamp_control_rig` is sized from the live `turn_radius_scale` and records the gain sweep's numbers; over-smoothing is now an assertion, proved to fail on a reverted build (`bend90` 57.79 m). Default byte-identical, suite 17. See §S3b "Two safety claims were false" |

#### ⚠️ `2aba0a9` raised six numbers and recorded one — 2026-08-10

Found by an independent audit; recorded here because a number going up is the thing this
file exists to catch, and this one went up invisibly. `2aba0a9` (the smooth-κ bound) reported
its cost as *"one new failure, 3 bowtie lots in B"* and *"folds unchanged"*. Both are true as
far as they go and both hid a regression. Measured across the three commits:

| | pre-work `f993cfd` | after `2aba0a9` | current |
|---|---|---|---|
| A `selfx_city_merged` | 6 | **9** | 9 |
| B `selfx_city_merged` | 93 | **95** | 95 |
| C `selfx_city_merged` | 336 | **359** | 270 |
| D `selfx_city_merged` | 6 | **9** | 9 |
| C `lots_are_simple_polygons` | 52 | **57** | 41 |
| B `no_sweep_fold_after_trim` `max_ratio` | 0.104 | 0.063 | **0.215** |
| C `no_sweep_fold_after_trim` `max_ratio` | 0.214 | 0.153 | **0.254** |

⚠️ **Provenance, because it differs by column.** The *pre-work* column is
`tests/citygen/baseline.json` as it stood at `f993cfd`, re-read before this pass rebaselined
it; the *current* column is a suite run on this build. The *after `2aba0a9`* column is the
audit's, cross-checked against `2aba0a9`'s own before/after table in §S3b — it has **not**
been re-measured by rebuilding that commit.

⚠️ **`baseline.json` had been three commits stale, and that is half the reason this was
invisible.** The runner *was* printing every one of these rows under "moved since baseline"
on every run; a diff that long is a diff nobody reads. It is rebaselined as of this pass, so
the next moved number is visible again. **Rebaseline with the commit that moves the number,
or the diff stops being a regression test and becomes wallpaper.**

Two mechanisms hid it:

1. **Commits 2 and 3 reported their gains against the pre-work 336 / 52, not against the
   actual pre-commit 359 / 57.** Measuring an improvement from the wrong baseline is how
   commit 1's regression became invisible — the ledger read "336 → 302" when it was
   "359 → 302".
2. **"Folds unchanged" was true of the fold COUNT and false of `max_ratio`**, which is the
   leading indicator that metric exists to give. It is now **above pre-work on both B and C**
   while the count is still 0. A count that is zero on both sides cannot report a trend; the
   ratio can, and it was in the value dict the whole time.

**Confirmed causal, not correlated, and measured on the current build** by switching the same
mechanism off with `turn_smooth_gain = 0`:

| `selfx_city_merged` | A | B | C | D | C `lots_are_simple_polygons` |
|---|---|---|---|---|---|
| pre-work `f993cfd` | 6 | 93 | 336 | 6 | 52 |
| current, gain **0** | **6** | **93** | 223 | **6** | 30 |
| current, gain **2** (shipped) | **9** | **95** | 270 | **9** | 41 |

Switching the bound off restores A, B and D to their pre-work values **exactly**; C differs
because commits 2 and 3 moved it as well. So the smooth-κ bound is buying C's ring seam and
A's `centreline_curvature_within_class` (0.889 → 0.364) at the price of those two, and the
trade is real rather than suspected.

⚠️ **And the suite's 17 → 17 across the three commits is a coincidence, not a wash.**
`selfx_roads` on C went **9 → 0** (fixed by `68f6a21`) while `lots_are_simple_polygons` on B
went **0 → 3** (broken by `2aba0a9`). Two different checks, opposite directions, same total.
A failing *count* is not a regression test; the per-check baseline diff is, and it was
printing all seven of these rows the whole time.

#### Two more from the same audit — recorded, one fixed

- **`max_turn_spike` was reading the solver instead of the geometry.** Fixed; see §S3b
  "the detector and the fix used to be the same code".
- **The snap-merge at `graph_extend` fires exactly once in the whole suite** — C_radial only,
  the (251.39, −87.10) / (249.37, −93.47) pair at a 6.68 m gap, and the two ends find each
  other symmetrically so it is one merge and one moved point. A, B, D, E and F produce **zero**
  candidates. Its gate is `min_join_angle = 45°` on the two legs, which admits a **135° turn**,
  and the one real instance leaves the clamp at **κ × R_min = 1.009 against a 1.02 slack**.
  ⚠️ That 1.1% is *the solver's own stopping tolerance* (`tol = 1.01`), not a geometric
  near-miss — C's `worst_at` is (250.64, −94.59), this corner, and it converged.
  **Sizing the gate by available tangent run instead of leg angle was considered and is not
  cheap**, for a reason worth recording: `streetWidth` is written in **`s5j_solve`**, deep in
  S5, so `R_min = ½·streetWidth·turn_radius_scale` does not exist at `graph_extend`; the class
  is decided from the street's **length**, which the merge itself changes; and at the one real
  instance the legs are **156 m and 330 m** against a required run of **≈26 m** — a 6× and a
  12.7× margin, so the gate would not move any shipped output. Build it when a case reaches it.

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
**CLOSED 2026-08-10, and the clamp alone was not the cure.** The clamp took the seam from
19.03° to 13.36° and stopped there, because at R = 16.9 m against R_min = 14.4 m it is legal
by radius — `centreline_curvature_within_class` read 0.852 and passed on a corner the artist
could see. §4f-4's **smooth-κ** step, named in the design and never built, is what closes it:
seam **7.26°**, and the whole-city curvature maximum 0.852 → 0.463. See §S3b "The clamp is a
radius floor and that is not the same as a smooth street".

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

#### Every promoted parameter, measured — 2026-08-10

The artist reported *"the ui of the nodes is not connected, I played around with the sliders
and I think I found only 2 or 3 that work across all nodes."* **Measured, that is wrong by an
order of magnitude — and it is still pointing at something real.** All **57** promoted
parameters on the four HDAs were swept: build fresh from `cases.py`, cook, SHA-1 all four
outputs (counts, `P`, topology and *every* point/prim/vertex/detail attribute), perturb one
parm to a sane in-range value, re-cook, re-hash. A parm counts as live only if a digest moves;
it counts as dead only if it moves nothing on **any** of the six cases.

| | count |
|---|---|
| moved an output at the first perturbation | **42 / 57** |
| moved only at a second, more extreme in-range value | 5 |
| **moved nothing at any value on any case** | **9** (+1 removed twice over, below) |

⚠️ **"Moved an output" is not the same as "changed the city", and the first version of this
audit conflated them.** Corrected after an independent audit of `7a43f69`. Splitting the digest
into a geometry half (counts + P + real vertex→point topology) and an attribute half puts the
55 surviving parms at **45 geometry · 4 attribute-only · 6 dead**. The four are
`street_params_region_size` (ids only), `street_params_zone_inner` / `zone_core` (the `land_use`
string only) and — the one that matters —

> **`lots_params_min_lot_area` deletes nothing.** At 50, 900, 5000 and **20 000 m²** C_radial
> ships the same **773 lot prims in the same places**; only `lot_reject`, `lot_viable` and `Cd`
> move. That is **correct**: §S8 viability is advisory by design (`citygen.md` §2.2 — flag and
> explain, never delete). But an artist dragging a slider called *Minimum Lot Area* over a 400×
> range and watching nothing happen has found the same complaint again, and "it is advisory"
> has to be on the parameter, not only in a design doc.

⚠️ **The topology term in the first digest was dead code.** `hou.Geometry.primIntrinsicValues`
does not exist in H22 and the call sat inside a bare `except`, so for one commit the "topology"
half of the hash was silently absent. It is a Python vertex walk now. Nothing in the recorded
verdicts changed — every parm called live still moves counts, `P` or attributes — but the
mechanism was not what the docstring said it was.

The nine, with the cause named rather than counted:

| parm | HDA | cause | disposition |
|---|---|---|---|
| `angle` | field_radial | **wiring bug.** Promoted → written onto the source descriptor → read back into `ang` by the trace node's `field_tensor` → **never passed to `pfsf_gen_radial`**, which had no angle argument at all | **fixed.** The generator takes `angle_deg` and adds it to the tensor bearing, so 0 is the pure radial field (bit-identical) and anything between 0 and 90 is a spiral |
| `s5_params_junction_scale` | streets | **referenced by nothing.** Grep of every `.parm` in the expanded HDA finds it only in the `s5_params` null that carries it. A relic of the trim-back-by-a-radius junction that §S5 rules out permanently | **removed**, with its backing spare parm. (`max_trim_fraction` on the same null is the other half of that relic — not promoted, also unreferenced, left in place) |
| `lots_params_setback` | streets | **referenced by nothing.** Same test. A building setback is not an S8 splitting rule and §S8 never lists it | **removed**, with its backing spare parm |
| `organic_amp` | trace | inert-by-design: read **only** on the `field_type == "organic"` branch of `field_tensor`, and **no organic generator ships** (§S1 designs it; it is not built) | kept, help text now says so |
| `organic_scale` | trace | same | kept, help text now says so |
| `close_min_pts` | trace | wired and in the gate chain, but **never binding**: 3 → 64 moves nothing on any case, and `closure_gate.py`'s ledger already records it as sole rejector for 0 of 12,792 traced streets | kept, help text now says so |
| `s5b_params_pier_spacing` | streets | inert-by-design: S5b runs only on edges with `is_bridge` = 1, i.e. `layer` > 0. **Measured: every case ships `layer` ∈ {0} and 0 bridge edges** | kept, help text now says so |
| `s5b_params_max_span` | streets | same | kept, help text now says so |
| `s5b_params_pier_clearance` | streets | same | kept, help text now says so |

⚠️ **The three `s5b_*` parms are an untested branch, not just a quiet one.** No case reaches
S5b at all, so pier placement has never executed. That is the same defect class as `offset` lot
mode (§4e-6), `max_fillet_fraction` (§4h-2) and the turn clamp (§S3b) — and the cure is the same
one every time: **a case in `cases.py` that carries a `layer` > 0 edge.** Not built here.

**Five parms that are live but only at a value or on a case the first sweep did not reach** —
these are what the artist actually hit, and none of them is a bug:

- **`weight` on both field HDAs is a no-op with a single source, and that is arithmetic, not
  wiring.** Sources sum as *tensors* and the direction is recovered as `½·atan2(t.y, t.x)`, which
  is invariant under a positive scale — so one grid source at weight 1 and at weight 8 is
  bit-identical. It only steers geometry where two or more sources overlap, which **no case in
  the suite does**. Proved with a two-source control rig (grid + radial into one trace): weight
  1 → 4 on *either* source moves all four outputs (Δθ up to 0.54 rad; single-source Δθ measured
  **0** at weight 0.5–100).
  ⚠️ **Two corrections from an independent audit of `7a43f69`.** The sentence that stood here —
  *"radial additionally moves at 8 and at 0 because its weight also scales the exponential decay
  against the tracer's strength floor"* — is **false**. The floor is `1e-6`; radial strength over
  C's 800 m domain is 5.4–8 at weight 8, six orders above it. The real mechanism is **float32
  rounding**: `u@tensor` is stored float32, so a *power-of-two* rescale is bit-identical
  (2.5 → 5.0, → 10.0, → 1.25 all reproduce the city exactly) and any other ratio shifts the
  recovered angle by ~3e-8 rad, which the tracer amplifies into a different city. And **weight 0
  is not "removes the source"** on the only source: `t` collapses, `field_tensor`'s
  `strength < 1e-9` guard fires, and the whole field becomes a flat 0° grid. A slider that is
  exactly inert at 2× and chaotic at 1.2× is worse for the artist than a dead one; sizing the
  tensor in float64, or normalising the summed tensor before recovering θ, is the real fix and
  is not built.
- **`min_node_dist` on the trace node is live.** §S3 records *"`min_node_dist` 50 → 40 produced
  bit-identical output"* and that reproduces exactly — but 50 → 0 and 50 → 300 both move every
  output on both B and C. It is threshold-insensitive around its default, not inert. **The two
  parameters called `min_node_dist` are different parameters** (trace's lookahead-crowding test;
  `graph_params_min_node_dist` at `graph_extend`) and the ledger has been conflating them.
- **`graph_params_min_join_angle` fires. The "never fired" record is refuted.** 45 → 5 moves all
  four outputs on **B_grid**, so at 45 it is rejecting extensions into existing junctions there.
  §S3 and §S7 both cite *"never having fired"*; that was measured before `68f6a21` and is no
  longer true.
- `street_params_arterial_len` / `collector_len` move nothing on C_radial and move everything on
  A_drawn — C's traced streets are all far from the class boundaries.
- `lots_params_lot_frontage` is read **only** by the `offset` branch of `lots_subdiv`; it is now
  `disablewhen`'d outside that mode so it stops reading as a dead slider.

**After the fixes: 55 promoted parms, 45 geometry · 4 attribute-only · 6 dead** — and the six dead are exactly the six
tabled above that were kept. `tests/citygen/parm_liveness.py` is the sweep, committed, and it
**fails on a disagreement in either direction** for *both* the dead set and the attribute-only
set: a parm going dead is a regression, and a parm recorded dead or attribute-only that starts
moving geometry means the entry is stale. Every default is byte-identical after the fixes —
independently re-verified by rebuilding the whole pre-commit tree (four HDAs plus all of
`vex/include`) at `7a43f69^` in a separate process and hashing **all four outputs of all six
cases** with topology included: every hash identical. The suite is unchanged at **17 failing**,
same failing set, no baseline movement.

⚠️ **DEAD is scoped to the shipped slider range.** `close_min_pts` at **1000** — far outside its
`{3 64}` range — does move C_radial. That confirms its recorded reason (wired, never the binding
gate) rather than contradicting it, but the distinction has to be stated or the next reader will
"disprove" the row with an illegal value.

#### ⚠️ THE SWEEP ITSELF WAS BROKEN, AND IT FAILED IN THE ONE WAY THAT LOOKS LIKE SUCCESS

Found 2026-08-10 by the audit of `ac64636` + `54bf0e3`. `parm_liveness.py` exited **1** on
`trace / graph_params_repair_passes  DEAD`, and the parm is not dead — the *perturbation* was.

With no `PERTURB` entry the parm falls through to `generic()`, which doubles the current value:
8 → 16, clamped to the range maximum of **12**, so the sweep raised a **cap** that no case comes
near. **It tested the only direction in which the parameter cannot possibly matter.** The fix is
one line — `("trace", "graph_params_repair_passes"): [1]` — and at 1 the geometry of every case
moves, because 1 is the documented single-pass build.

Two more were falling through to `generic()` and reading GEOM **only by luck of the doubling**,
which is not the same as being measured:

- `s5j_params_min_standing_widths` — a floor whose interesting direction is **off** (0), not
  doubled. Worse, it sits in `GRAPH_PARMS`, so it is swept over `STREET_CASES` — **which did not
  include `G_tongue`, the case written for it** (`cases.py`: *"adding a parameter means adding a
  case"*). The sweep was running the tongue parameter on every case except the tongue. `G_tongue`
  is now in `STREET_CASES`.
- `s5j_params_culdesac_radius` — same shape, same fix.

**The general lesson, and it is not about these three parms.** `generic()` is a *fallback*, and a
fallback that silently produces a wrong answer is worse than one that refuses: doubling is
meaningless for a cap, for a floor, and for anything whose default already sits at one end of its
useful range. The printed `(no perturbation listed for …)` line is the warning; treat it as one.

#### Recorded, not fixed — from the same audit

- **`restlength` is the last float prim attribute a connector does not inherit**, and nothing
  recomputes it. Impact today is **zero** because nothing reads it — but it is exactly the class
  of bug that §S3's connector fix above was written for (`streetWidth` diluted by a
  length-weighted average), so it should be inherited the next time that code is opened.
- **`every_block_is_subdivided` is inert on E, F and G.** They close no block, so `blocks == 0`
  and the assertion degrades to `len(lots) >= 0`. On the cases where it does run it asserts only
  **≥ 1 parcel per block**, and it locates parcels by **centroid-in-polygon** — so a neighbour's
  centroid falling inside an empty concave block masks exactly the failure the check was written
  to catch.
- **`attribute_schema` reports 0 while 8 of §6's attributes are absent** from the shipped graph.
  It is asserting *something*, but it is not asserting the §6 table, and the name says it is.
- **`streetWidth` drifts in the last ulp** — 26.8 → 26.7999 — even on `G_tongue`, where nothing
  is repaired at all. `graph_polypath` re-averages prim attributes on every pass and
  `graph_width`'s *"an authored value wins"* guard is `streetWidth <= 0`, which never refreshes
  it. Cosmetic at one part in 10⁶; it becomes real the moment anything compares two widths for
  equality.
- **A white unpaved, unparcelled wedge on C_radial near (−175, −300)** — enclosed by the outer
  ring, a radial arterial and the cul-de-sac arm below it, and it is neither a block nor a
  corridor: no lot, no pavement, nothing. **Confirmed pixel-identical before and after** this
  commit (whole-city top-down raster, 0.53 m/px, differenced). It predates all of this work, it
  is the same family as §S7's collect-and-close failures, and it is the one visible defect a
  whole-city render of C still shows.

  ⚠️ **Note for whoever renders next: the GUI flipbook path was unavailable** — the artist's
  session had a blocked main thread, so every `hou` call through the bridge timed out while a
  bare Python expression returned fine. These cities are flat, so an orthographic top-down raster
  drawn straight off outputs 0–3 (blocks, city, lots, graph) with PIL in `hython` **is** the
  whole-city view, it is deterministic, and it can be differenced pixel-for-pixel between two
  builds — which is how the "pixel-identical" claim above was made rather than eyeballed. It also
  leaves nothing behind in anyone's session. What B and C show at this commit: the street network
  is bit-stable (B 64 edges, C 86, unchanged), every block is fully parcelled, paving is
  continuous through every junction, and the only visible difference is that the parcels inside
  the blocks are **re-cut** — about 2.5% of pixels on C and 3% on B, spread evenly over the whole
  city rather than concentrated anywhere. That is the signature of S8 re-running on a settled
  graph, which is exactly what this change was supposed to produce.

#### ⚠️ C's east sector subdivides into long ribbons, and `ac64636` recorded only the improvements

`lot_aspect_ratio` **over-3.0 count 167 → 192** on C_radial and **161 → 164** on B_grid across
that commit, with C's p90 **7.29 → 7.93** — the maximum improved (14.84 → 13.97) and the
distribution behind it got worse. The commit message listed the maximum and not the count. The
repair-loop fix in this commit takes it partway back — **C 192 → 189, B 164 → 161**, with C's max
going the other way, 13.97 → 15.04 — but the sector is still visibly ribboned and this is the
open S8 defect, not a closed one.

Also moving the wrong way, and recorded because it is under its own threshold rather than fixed:
`lots_clear_of_roads` on B_grid **0.0 → 0.2 m²**, which is a **single 0.5 m raster cell** and
0 blobs — a lot boundary shifting a few centimetres, not a lot on the road.

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

Five HDAs in `polyfactory/otls/`, versioned. Build examples from `tests/citygen/cases.py`.

| Asset | In → Out |
|---|---|
| `pf_citygen_field_grid` | — → a field **source descriptor** (one point: type, centre, weight, falloff, bearing). Chainable via its input |
| `pf_citygen_field_radial` | same, radial |
| `pf_citygen_junction` | graph splines → the S5 solution (junction patches + streets carrying `trim_start`/`trim_end`). A helper asset, used twice inside the tracer and testable on its own |
| `pf_citygen_trace` | in0 field sources **or** in1 **any curves** → out0 **editable centreline splines** (§6 schema) · out1 the junction solution. S1·S2·S3·S4·S5 |
| `pf_citygen_mesh` | in0 splines · in1 junction solution → out0 city geometry · out1 blocks · out2 lots · **out3 the graph, passed through** (the data stream, Contract 8). S6·S7·S8 |

Field sources are descriptors rather than baked grids, so any number merge and blend for free.

### ⚠️ The boundary moved — 2026-08-10. It is now between DATA and GEOMETRY

The first build shipped S3–S8 inside one geometry HDA, which put the junction solve behind the
meshing wall: the artist's parameter panel carried Miter Limit, Corner Radius Scale, Fillet Arc
Steps and Max Fillet Fraction on the node that draws polygons. Those are decisions about
centrelines.

**Everything up to and including the junction is data about centrelines; everything after is
derived geometry. The assets split exactly there.** So `pf_citygen_trace` now owns S1 field,
S2 trace, S3 graph, S4 classify and S5 junctions and emits splines; `pf_citygen_mesh` owns
S6 sweep, S7 blocks and S8 lots and consumes them. The 20 S3/S4/S5 controls moved with the
stages they steer, into three folders (Graph · Streets · Junctions); the 12 S6/S7/S8 controls
stayed.

**A hand-drawn spline is not a special case — it is input 1 of the tracer**, which is §3's
*"an artist can inject hand-drawn splines directly at S3 […] entering the pipeline one stage
later"* made literal. Case A goes `draw → trace(in1) → mesh` and cases B/C go
`field → trace(in0) → mesh`; the only difference is which input is wired.

**The junction solver is its own asset because it was already being used twice.** §S5's
`min_standing_widths` requires the solve to run once as a pre-measure (to learn each arm's trim)
and once for real, and the pre-measure nodes were *copies* of the shipped ones. They are now the
same HDA instanced twice, with `do_culdesac` off on the pre-measure — the copy cannot drift from
what ships, because there is no copy.

⚠️ **`pf_citygen_streets` is gone.** It was renamed and gutted; the mesh node is the direct
descendant. Any scene wiring `pf_citygen_trace → pf_citygen_streets` must be rebuilt, and note
that the tracer's **out0 changed meaning** — it was raw centrelines, it is now the solved graph.

**The relocation was proven behaviour-preserving before anything else changed.** Both halves of
`digest()` — geometry (counts + P + vertex→point topology) and attributes — on all four outputs
of all seven cases, `4ce13a8` against the split: **28 of 28 identical**, and the check suite moved
**zero** values. `source_node` is excluded from the hash and is the one thing that legitimately
moved, because it records which node generated an element and the answer is now `…/trace/…`.

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
