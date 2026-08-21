# CityGen — Street Generation Design

**Status:** V1 built and shipping as four HDAs (§6b); defects and the fix order are in §4d.
**Owner doc for:** street field → graph → intersections → road geometry → blocks → lots.
**System-level architecture and cross-cutting contracts:** [`citygen.md`](citygen.md) — read that first.
**Reference library:** `polyfactory/resources/citygen/README.md` (gitignored, local).
**Artist-facing UI:** [`artist_ui.md`](artist_ui.md) §6b audits this doc — the v1
everything-exposed parameter sheets are the *author* tier; a separate authored promotion pass
per stage HDA (empty-by-default artist face) and a greybox-while-dragging answer are still owed.

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
  "about 11×" until 2026-08-10. At the shipped defaults `repair_residual_m` reads
  A 1.5e-5 · B 3.4e-5 · C 4.3e-5 · D 1.5e-5 · E 0 · F **6.10e-5** · G 7.6e-6. The 9.2e-5 m figure
  reproduces only with the tolerance driven *below* the settling floor — measured **9.16e-5 m** on
  `F_bend` at a 1e-6 m tolerance, where the loop no longer converges and runs to its 12-pass cap —
  so it is the noise of a non-converging run, not of the shipped one. The conclusion is unaffected;
  the margin is larger, not smaller);
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

**And the tooth was proved to bite on the three real defects**, at the *shipped* tolerance — cap
each case at the pass the old verdict stopped at and ask the new flag:

| case | capped at | new flag | old flag | why |
|---|---|---|---|---|
| `F_bend` | 3 | **FAIL** | PASS | forced-pass residual **1.587e-3 m** |
| `C_radial` | 3 | **FAIL** | PASS | residual **1.142e-3 m** and **9** reversals |
| `B_grid` | 5 | **FAIL** | PASS | **1** reversal, structure stable |

⚠️ The first falsification written for this was *"drive `Repair Tolerance` to 1e-6 and `F_bend`
fails"* — which is **weaker than it looks and should not be used**: at 1e-6 the loop never
converges and runs to its 12-pass cap, so `repair_converged` is 0 and `graph_reaches_a_fixed_point`
fails too. It demonstrates the *old* tooth as much as the new one. The table above does not.

The other two new checks were broken on purpose the same way. `no_scratch_attribs_city` fails with
5 leaked when `out_detailclean` is bypassed and 6 when `repair_scratch` is bypassed as well.
`input0_reaches_an_output` fails on a 0.5 m perturbation of input 0, on the input being **unwired
altogether** — the change the audit recommended — and on the graph output being **re-sourced one
hop downstream**, which is the case that needed the attribute term (below).

Two smaller repairs in the same check: the `stopattrib` round-trip went through `.eval()`, which
would have flattened an expression to a literal on the way back in, and now goes through
`rawValue()`; and the `allowEditingOfContents()` it never undoes is deliberate rather than
forgotten — the runner unlocks the tracer for the whole case, so re-locking would take the network
away from the checks that run after it. It is commented as such.

#### ⚠️ AND THE FIX LEFT THE SAME PATTERN ONE LEVEL DOWNSTREAM

Found by the audit of the fix itself, 2026-08-10, and it is the finding that matters most here.
The two new terms were added on the **graph**; the half of the check that looks at the **shipped
product** was still four integers. Same forced pass, parcel areas compared **rank-sorted** so S8's
renumbering cannot fake a match:

| case | lots | city prims | city **points** | parcels moving > 1 m² | worst | total area delta |
|---|---|---|---|---|---|---|
| `A_drawn` | 83 → 83 | 4459 → 4459 | **5568 → 5569** | **78 of 83** | **40.6 m²** | 0.008 m² |
| `B_grid` | 619 → 619 | 18587 → 18587 | 24283 | **443 of 619** | **23.6 m²** | 0.0006 m² |
| `D_offset` | 61 → 61 | 4437 → 4437 | 5523 | 0 | 0.004 m² | 0.008 m² |

The check printed `'moved': None` and passed on A and B. **Total lot area is conserved to 6e-4 m²
— a textbook redistribution under a conserved aggregate**, which is the identical failure mode to
the one this whole section is about, one stage further down. `D_offset` moving 0 proves the
measurement discriminates rather than reporting noise. And A's shipped city *gains a point* across
the pass, which even the "structural" half never sampled because `state()` counted the graph and
the blocks, not the city.

So `state()` now carries `lots_moved` (parcels whose area moves more than 1 m²), `city_prims` and
`city_points`. **All of them are RECORDED, not asserted**, for exactly the reason the lot count is:
they are S8's determinism, not S3's convergence. What changes is that the redistribution is now
visible in the baseline diff instead of invisible. This is also the direct evidence for the
"S8 is chaotic on every case" correction above — it needs no injected jitter.

##### ⚠️ …AND `lots_moved` WAS LATENT HOLE 1 AGAIN — the count kept, the magnitude discarded

Corrected 2026-08-10 after an independent audit of `aa797db`, and it is the same shape as
"the per-edge match residual is computed and discarded" below, reproduced in the term that was
added to close the hole above. `lots_moved` counted the parcels and threw away **how far**:
A's worst is **40.6 m²** (sum 1230 m²), B's **23.6 m²** (sum 1348 m²), D's 0.0039 m². Three
attacks it cannot see, all measured: **619 parcels moving 0.9 m² each reads 0**; an equal-area
permutation reads 0; and area is **one scalar**, so a parcel changing SHAPE at constant area is
invisible. None of the three bites on this build — D's 0 is corroborated by an identity-matched
compare at 0 area, 0 perimeter and 0 centroid — but on A that identity-matched view shows
**75 of 83 centroids moving more than 5 cm, worst 13.58 m**, which is the shape term the area
scalar does not carry. `lots_worst_m2` is the magnitude, recorded beside the count.

⚠️ **And `C_radial` — the one case that actually moves — was the one reporting `None`.** An
index-wise pair does not exist when the lot count itself moves 774 → 770, so the term went blind
on exactly the case it was written for. Both lists are sampled at **64 fixed quantiles** when the
counts differ: C's worst is **8.21 m²**, sum 151 m², **42 of 64** quantiles over 1 m². `None` now
means only *"the question is meaningless here"* — E/F/G close no block and ship no parcels, where
a count of `0` read identically to "stable".

#### Recorded, not fixed — three latent holes in the geometry compare

All three measured **inactive on this build** (C/B/A: 0 unmatched edges, 0.0 worst match residual),
which is why they are recorded rather than repaired. ⚠️ **They are in the shipped VEX
`repair_verdict` verbatim as well as in the suite's `_graph_geometry_delta`** — which matters more
now that `forced_extra_repair_pass` asserts the solver's own numbers, because both asserted terms
are then the solver's self-report and a bug *inside* `repair_verdict` reads as 0 / 0 and passes:

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
Both checks therefore **record `tol_m` in their value dict**, so a loosening moves the baseline
instead of hiding in it. `graph_reaches_a_fixed_point` did not, and it was measured invisible:
on `C_radial` at a tolerance of 2e-3 *and* 1e-2, city 21363, lots 774, edges 86, the residual and
the pass count all come back identical — a **10× loosening of the tooth with nothing to see it**.

⚠️ **One more thing this check does not do:** if `repair_verdict` stops writing altogether,
`forced_extra_repair_pass` returns a **SKIP**, not a failure, because its `repair_iterations` guard
fires first. `graph_reaches_a_fixed_point` fails hard in that case and is why the suite is still
covered — but "a missing attribute FAILS" is true of the replay, not of the forced pass.

#### ⚠️ AND THE EXPERIMENT NEVER VERIFIED THAT IT RAN

Corrected 2026-08-10 from the same audit of `aa797db`. `forced_extra_repair_pass` sets
`cap = iters + 1` and then measured everything on the resulting geometry **without ever confirming
that `iters + 1` passes had happened** — even though the forced geometry carries its own
`repair_iterations` and the check was already reading that attribute. Simulated by leaving the cap
at `iters`: the structure is unchanged, the residual is **1.53e-5 m ≤ tol**, the reversal count is
**0**, and the check **PASSES with the experiment not having been performed**. It only runs today
because `Max Repair Passes` has **`maxIsStrict=False`** — its UI max is 12 and 13, 20 and 99 all
take — which is luck, not design: a strict max would have silently clamped the cap and the check
would have gone on reporting "nothing moved" about a pass it never ran. The forced geometry's
`repair_iterations` is now asserted to equal `iters + 1`, and the simulation above fails.

**Three of this experiment's numbers are the solver's own, including its control variable**, which
the audit asked to be named rather than fixed:

- **`iters`** — the pass count the whole experiment is defined against is `repair_iterations`, the
  loop's own counter. That is precisely what made "the forced pass never ran" possible. The failure
  direction is safe: a counter that under-reports forces *more* passes, one that over-reports trips
  the new assert.
- **`tol`** — the acceptance threshold is `graph_params_repair_tolerance`, the solver's **own stop
  threshold**, so `resid <= tol` here is the loop's stop condition re-applied one pass later. Its
  **unique** coverage is therefore the **f³ window only**: the loop already requires two consecutive
  no-op passes (above — `f(x) == x` says nothing about `f(f(x))`, and `B_grid` proves it), so this
  is the third iterate. Every constructible regression outside that window fails
  `repair_converged == 0` first, in `graph_reaches_a_fixed_point`.
- **`resid` / `rev`** — the verdict's own two numbers, already recorded above.

⚠️ **And the detail string named the asserted set wrongly.** It called it "the GRAPH structure"
while `blocks` is in it, and blocks are **S7**. Asserting `blocks` is correct and is measured —
**2 / 17 / 2 / 28 blocks held across every forced pass on every case**, so the block layer is the
one thing downstream of the graph that S8's chaos does not move — the string says "the graph
structure and the block count" now.

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
standing proof — output 3 must be input 0 **point for point and attribute for attribute**.

⚠️ **Positions alone were not enough, and the audit proved it on this check the day it was
written.** Re-sourcing `out_graph` one hop downstream, from `s5b_mark`, leaves every point exactly
where it was: the position-only version **passed**, `attribute_schema` passed, nothing in the suite
failed — while the published graph had silently gained `is_bridge`, `is_tunnel`, `is_ramp` and
`terrain_op`. **A pass-through that adds a column is not a pass-through**, so the attribute name
sets are compared too. (Unwiring input 0 outright was already caught before this commit, by
`attribute_schema` and `centreline_curvature_within_class`; what this check adds there is the
diagnosis, not the coverage.)

⚠️ **AND "ATTRIBUTE FOR ATTRIBUTE" WAS COMPARING NAMES. Corrected 2026-08-10** after an
independent audit of `aa797db`, and this paragraph and the check's docstring both claimed the
coverage they did not have. Publishing output 3 through a wrangle that sets
`street_class = "alley"`, `region_id = "region_99"` and `streetWidth = 1.0` on **every edge** adds
no attribute name and moves no point: `input0_reaches_an_output` **passed**, `attribute_schema`
passed, **nothing in the suite failed**, and the shipped graph said every street in the city was a
1 m alley. A pass-through that *rewrites* a column is not a pass-through either. The **values** of
every shared attribute are compared now — elementwise and exactly, because a pass-through is
bit-identical or it is not one — and a rewritten attribute reports as `!pr.street_class` beside
the `+`/`-` of a name that came or went. The attack above now fails the suite, and so does the
same attack aimed at a **point** attribute (`!pt.is_node`), which is the other half of the branch.

⚠️ **DETAIL attributes are still not compared — recorded, not closed.** Measured by accident while
writing that attack: with the wrangle's class left at *Detail*, `is_node = -12345` shipped as a
detail attribute on output 3 and the check **passed**. Prim and point are the two classes that
carry §6's street contract, and the graph legitimately ships detail attributes the suite itself
reads (`repair_converged`, `repair_iterations`), so closing this means first deciding which of
those the mesh may restate — a different question from the pass-through.

⚠️ **Two gaps remain, recorded rather than closed.**
- **Block identity is unguarded.** Cutting `blocks_id`'s second input — the very consumer that
  justifies keeping input 0 — collapses every block's `region_id` to `region_00` and loses
  `land_use`, and **not one check in the suite fails**. `source_node` / `region_id` survival is
  §6's Contract 2 and has no assertion behind it on the blocks branch.
- **A bridge case.** The pier branch is a live consumer of input 0 that the suite has never
  executed — `parm_liveness` reports all three `s5b_params_*` DEAD for that reason — which is the
  same "a mechanism the suite never runs is untested" pattern as `offset` lot mode (4e-6),
  `max_fillet_fraction` (4h-2) and the clamp at amplitude (`F_bend`). It also bites the detail
  check: `s5b_piers` writes `bridge_count`, `pier_count`, `piers_rejected`, `worst_span` and
  `span_violations` as **detail** attributes, and the first version of `out_detailclean` named five
  attributes, so all five bridge counters would have shipped on the city and tripped
  `no_scratch_attribs_city` for an unrelated reason on the first bridge case. It deletes `*` now:
  **the city mesh ships no detail attributes at all**, which is the rule, not a list.

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

⚠️ **CORRECTION — 2026-08-12. The first sentence is false as stated, and the reasoning that
produced it is what hid the defect for three sessions.** Tracing alone still cannot emit a 5-way
node, so no *point* in the graph reads degree 5 — and every check that asks "what is the maximum
degree" therefore reports 4 and passes. But C_radial carries a **degree-5 junction that is spelled
as three degree-3/4 nodes 20–32 m apart**: a triangle too small to be a city block, which the
solver treats as three junctions and solves into the same space. Measured live, §S5a. **A degree
histogram is not evidence that multi-leg junctions are absent** — the arm count has to be taken
after near-coincident junctions are identified, not before.

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

Known-hard cases still to prototype: degree ≥ 5 (**now a live defect, not a future one — §S5a**),
junctions between very different widths, junctions on a grade, and dual-carriageway short-road
clusters (A/B Street collapses these into a single intersection).

### S5a — Multi-leg junctions: the stub triangle and degree ≥ 5

⚠️ **This is a LIVE defect on C_radial, nothing here is fixed, and this is the section to read
before touching junctions.** It was filed under §S8 — Lots until 2026-08-12, which is why it was
twice reported as already handled.

#### The defect as it stands, measured in the live session — 2026-08-12

Read off `/obj/citygen_examples/C_segmenter/OUT_graph2` (95 edges, 2835 points) and the old
`C_city` (`pf_citygen_streets`), inspect-only, nothing saved.

| | measured |
|---|---|
| endpoint-degree histogram | **1×9 · 3×27 · 4×25** — maximum degree **4**, which is why every degree check passes |
| the tiny triangle | prims **86 (31.58 m) · 87 (25.37 m) · 88 (19.90 m)**, closing on points **2313** (deg 3, at 124.8, 290.9) · **2345** (deg 4, at 138.3, 262.3) · **2655** (deg 4, at 147.6, 279.9) |
| against the threshold | all three sides are under `graph_params_min_node_dist` = **40 m**; the longest is 79% of it |
| collapse the triangle to one node | **exactly 5 external arms** — prims **77, 78, 83, 92, 94** |
| old pipeline vs new | **bit-identical**: `pf_citygen_streets` yields the same three prim numbers, the same three lengths and the same histogram |
| repair machinery present | **none** — no `merge_*`, realign or roundabout node in `pf_citygen_segmenter` |

**It is not a regression from the Segmenter/Solver split.** The triangle is already present at
`graph_stitch`, the first stitched state, and passes unchanged through `graph_extend`,
`graph_prune`, `graph_min_angle`, `graph_kill_angle`, `graph_drop_tongue` and `graph_drop_orphans`
to `OUT_graph2` — in **both** builds. Hannes: *"this junction issue did not work in the old one as
well, so that is simply a bug we never caught."* Confirmed: nothing in either build has ever looked
for it. `graph_kill_angle` is the closest thing to a guard and it tests angles at a node, not the
distance between two nodes.

⚠️ **Do not key anything on prim 85/86/87/88.** The artist's original report named prim 85; the same
triangle is 86/87/88 today. Prim numbers move with every upstream change — the stable description is
*"a cycle of three edges, every side shorter than `min_node_dist`, every corner a junction."*

**Two open holes this exposes in the suite**, both of which would have caught it years earlier:

1. **No check for junction-to-junction edges under `min_node_dist`.** The measurement above is four
   lines of Python and is not committed. It belongs in `checks.py` before any fix is attempted, so
   the fix has something to turn green.
2. **No degree-5 case.** §S5 *"Higher-degree junctions"* asked for a hand-drawn star of five in
   `tests/citygen/cases.py`; grep finds none. A fix for a case the suite does not run cannot be
   verified, and this is the second time that gap has been recorded without being filled.

⚠️ **And the threshold itself is ambiguous.** `pf_citygen_segmenter` exposes **two** parameters:
`min_node_dist` = **50.0** and `graph_params_min_node_dist` = **40.0**. This document has only ever
discussed the 40 m one. Which governs the collapse must be settled before it is built, or the
threshold silently moves by 25%.

#### Stub-edge collapse, and the 5-arm solver defect it uncovered — 2026-08-11

The artist: *"prim 85 should actually be removed because it is a very small street creating a tiny
triangle which should be invalid size wise."* Three streets crossing within a few metres leave a
tiny triangle whose short side is not a street — it is the residue of two crossings that should have
been one junction. S5 then solves three junctions into the space of one and their patches collide.

**The threshold is not invented.** Subdivision street standards prohibit street jogs offset under
**125–150 ft (38–46 m)** and discourage offset intersections generally;
`graph_params_min_node_dist` already defaults to **40 m**, squarely inside that band. The value was
right and nothing enforced it — it is read in exactly one place, `graph_extend`, as a rejection test
when landing a *new* junction. The procedural literature resolves the same degenerate loops by
**removing an edge**, not by fusing whatever is nearby.

⚠️ **"Built" — AND THEN REVERTED THE SAME DAY. This paragraph said "Built:" with no revert
marker until 2026-08-12, and it is the single reason the fix was reported finished twice while the
defect was still on screen.** It is a *design record*, not a status: **no `merge_*` node exists in
any shipped HDA** (verified 2026-08-12 — `pf_citygen_segmenter` has 39 children, the only
degree-aware ones are `graph_degree` and `graph_degree_final`). Read it with the revert table
below, which is the authority on what ships.

**The design, as built and measured before reverting:** `merge_init` → `merge_mark` → `merge_fuse`
→ `merge_degree` → `merge_scratch`, inside the Segmenter's repair loop after `graph_width`. An edge
joining **two junctions** (both degree ≥ 3) shorter than `min_node_dist` is collapsed, higher point
number snapping onto lower so chains resolve over passes and the process terminates. Measured then:
**A_drawn and B_grid bit-unchanged** (15 and 64 edges), C_radial drops 6 stub edges, **0 stubs
remain on any case** — and the suite went **21 → 36 failing**, because the collapse is correct and
what it exposes is not.

⚠️ **Two approaches were tried and rejected first, both recorded in the wrangle.** Fusing any two
junctions within `min_node_dist` collapsed 8 junctions where 2 clusters exist and tore S7 open
(1414 m² unpaved, an open block loop). Doing it geometrically — merge when kerb corners would
overlap — **cascaded**, because merged nodes drift to their average, fall inside each other's
radius and re-merge every pass: B_grid ended at a **degree-167 node**. Only edges are collapsed now,
so a merge is bounded by the graph rather than by a radius.

⚠️ **THE COLLAPSE IS CORRECT AND IT EXPOSES A REAL SOLVER DEFECT. S5 DOES NOT HANDLE 5 ARMS.**
C_radial's two merged nodes come out at **degree 5, minimum angular gap 32.5°**, and the junction
solve fails on them: `junction_boundary_is_simple` 0 → 1, `selfx_junction_surface` 0 → 24, a corner
tangent out by **2.18 m**, and the S7/S8 damage that follows. Suite 21 → 36 failing, all on C_radial.

**Root cause, located:** `s5j_solve` clamps **each corner independently** against `miter_limit` —
`K = X + normalize(K - X) * (miter_limit * h2)` — and never checks that two *adjacent* corners around
the same node do not overlap. At degree 3 or 4 the angular gaps are wide enough that it never
happens. Tuning the limit is non-monotone and therefore not the fix: 4.0 → 1 non-simple boundary,
3.0 → 0, **2.5 → 1 again**, because the clamp moves corners without making them aware of each other.
The fix is a per-node pass that orders the corners angularly and enforces that consecutive ones do
not cross — not a different threshold.

#### ⚠️ But the corner solver is the WRONG TARGET. Researched 2026-08-11

Real practice does not mitre a five-leg junction. **Multi-leg intersections (5+ legs) are to be
avoided**, and where they occur the accepted resolutions are exactly three:

1. **Eliminate one leg.**
2. **Realign a leg** so it becomes two ordinary junctions instead of one multi-leg.
3. **Make it a roundabout.**

Channelization plus signalization is the fallback when the geometry cannot be changed — an operating
measure, not a geometric one, and therefore not available to us. AASHTO's *Green Book* carries the
realignment options.

⚠️ **CORRECTION — the claim first written here, that "our reference library has nothing on
multi-leg junctions", was FALSE.** It came from grepping for "multi-leg" and its spellings, which
none of our sources use. Two things were already recorded:

- **JunctionArt** (AugmentedDesignLab) — *"generates intersections with three to seven incident
  roads and outputs OpenDRIVE. It is the only reference found that addresses degree-5+ at all"*
  (§3b). We do not have the code. We do have its method, and it is instructive: it does **not**
  solve overlap in closed form. Its docs say *"if the connection length is too small, roads will
  overlap"* and then list **pre-tested safe parameter combinations for 8-road junctions**, backed by
  an `IntersectionValidator.py`. Conflict is prevented by **tuning plus validation**, not by
  construction — the opposite of our closed-form kerb-line fillet.
- **§S5 construction 2, adopted 2026-08-09 and never built:** *"Merge incident edges within
  `merge_angle` (default 20°) into a single direction before solving. Two nearly-parallel arms at
  one node are not two corners — treating them as two produces a corner with almost no angular room,
  **which is what inverts the boundary polygon**."* Boundary inversion is exactly what
  `junction_boundary_is_simple` reports on the degree-5 nodes. **This document diagnosed the failure
  and prescribed the cure before the external search began.**

So there are **two layers**, and they are complementary rather than alternatives:

| level | rule | status |
|---|---|---|
| **graph** | cap arms at 4; realign a leg, else roundabout | external practice, researched 2026-08-11 |
| **corner** | merge arms within `merge_angle` into one direction before solving | §S5, adopted, **never built** |

⚠️ **The measured gap decides which layer applies, and ours does not fit the corner rule.** C_radial's
crowded pair is **32.5°** apart, above the 20° `merge_angle` default. Either that default is too
tight for real traced fields, or 32.5° is genuinely two streets and the graph-level fix is the
correct one. **Settle this before building either** — it determines whether the work is a
threshold change or a realignment pass.

**What this means here.** §S5 already declares three node types — plaza, **roundabout (21–67 m
ICD)** and cul-de-sac bulb — and the roundabout is never triggered by arm count. So the correct
response to a degree-5 node is to **convert it**, not to teach the miter solver to survive it:

- degree ≤ 4 → the existing corner solve, unchanged
- **degree ≥ 5 → roundabout**, ICD sized from the incident widths within the 21–67 m band

That reuses machinery that already exists, matches published practice, and sidesteps the
adjacent-corner overlap entirely, because a roundabout has no mitred corners to overlap. The
per-node corner-ordering pass stays worth doing as a guard, but it is no longer the primary fix.

⚠️ **Correction — eliminating the triangle leg does NOT avoid the problem.** The artist:
*"the leg i asked you to eliminate is the one creating the triangle, if you do that you are still
left with 5 streets."* Right: the tiny triangle and the multi-leg junction are **two separate
defects that happen to coincide**. Removing the stub is necessary and does not reduce the arm count.
So both must be handled, in that order.

#### The three resolutions, ranked — researched across multiple sources, 2026-08-11

A **multi-leg intersection is one with more than four legs**; the extra leg *"creates a large area
of vehicular conflict and reduces intersection capacity."* Published practice offers three fixes,
and they are not equal:

| | resolution | standing |
|---|---|---|
| **1** | **REALIGN a leg** into a separate right-angled T, *"located at a sufficient distance to prevent interference with the main intersection"* | **preferred** — *"where economically feasible, the corrective measure"* |
| **2** | **Roundabout** | named alternative |
| **3** | **Eliminate a leg** | crude fallback; loses a street |

⚠️ **"Economically feasible" is the constraint on realignment in the real world, and it does not
apply to us.** Moving a road costs money on the ground and nothing here. So the option practice
prefers is the one a generator can take most freely — which inverts the usual assumption that the
roundabout is the easy answer.

**Separation distance.** No source gives a single figure for this case; two bracket it. The jog
rule already established here — **125–150 ft (38–46 m) minimum offset**, and offsets below that
prohibited — is the floor. The **split intersection** pattern, which deliberately replaces one
four-leg junction with two, separates them by **200–300 ft (61–91 m)**. So: never below ~40 m,
target ~60–90 m.

**Why this is cheap for us:** `graph_extend` already lands a new junction on a target street while
respecting `min_node_dist`. Realigning the fifth leg to form a T is that same operation run
deliberately rather than as repair, and it leaves two junctions the corner solver already handles —
no roundabout, no multi-leg miter, every street kept.

**Proposed cascade for degree ≥ 5, in the order practice ranks them:**

1. **Realign** the minor-most leg onto its neighbour at 60–90 m, if the neighbour is long enough to
   take a T that far out and still clear `min_node_dist` at both ends.
2. Else **roundabout**, ICD from the incident widths within §S5's 21–67 m band.
3. Never eliminate: §S3's *"a connection is never refused"* forbids resolution 3 outright.

⚠️ **Still a gap:** which leg is "minor-most" needs a rule. Width and class are the obvious keys —
the arterial goes straight through, the local moves — which is the same principle §S5 already uses
to decide that the lesser street sets the corner radius.

#### ⚠️ Four approaches built and reverted — 2026-08-11. Read before attempting a fifth

The rule is settled: **cap junction arms at 4**, realign a leg when feasible, roundabout otherwise.
The CityEngine cleanup order (intersect → snap → merge → resolve conflicts) is the model, run **once,
not inside the repair loop**. What is *not* settled is how to realign without wrecking the street.

Everything below was built, measured and reverted. The suite is back at **21 failing, zero baseline
movement**. Nothing in this subsection ships.

| # | approach | result |
|---|---|---|
| 1 | **Proximity fuse** — merge any two junctions within `min_node_dist` | collapsed 8 junctions where 2 clusters exist; S7 tore open (1414 m² unpaved, an open block loop) |
| 2 | **Geometric fuse** — merge when kerb corners would overlap, radius = widest incident half-width | **cascaded**: merged nodes drift to their average, fall inside each other's radius, re-merge every pass → **degree-167 node** on B_grid |
| 3 | **Stub-edge collapse** — collapse an edge joining two junctions shorter than `min_node_dist` | ✅ **graph-correct**: A and B bit-unchanged, C drops 6 edges, 0 stubs remain. ❌ produces **degree-5** nodes, and S5 inverts the boundary polygon on them → 21 → 36 failing |
| 4 | **3 + realign a leg** — move the minor leg's endpoint onto its neighbour `d` out, let `graph_stitch` form the T next pass | maxdeg back to **4 on every case, 0 roundabouts needed** — and 21 → **27 failing**: 2096 m² unpaved, 720 m² of lots on roads, and the repair loop **stopped converging** |
| 4b | 4 + a minimum-angle gate on the new T | **worse, 44 failing** — blocking the skew realignments left the degree-5 nodes unresolved instead |

⚠️ **THE ROOT CAUSE OF 4, AND IT IS NOT A THRESHOLD.** Moving the endpoint relocates *one vertex*
and leaves the rest of the leg where it was. The pair being realigned was chosen for being **nearly
parallel**, so the leg then meets its host at a shallow skew, with a kink where its old shape meets
the new endpoint. Practice calls for a **right-angled T**; FDOT is explicit — *"intersection angles
are to be as close to 90 degrees as practical… less than 75 degrees should be avoided"*. Gating on
that angle (4b) does not help, because it only converts a bad realign into no realign.

**Realignment requires RE-ROUTING the leg**, not relocating its endpoint: the last stretch has to be
rebuilt to approach the host near-perpendicular, inside S3b's curvature floor (`R > halfwidth`).
That is the missing piece, and it is real work rather than a parameter.

**Also worth keeping from these runs:**

- **A proximity merge adds nothing here.** Measured after the stub collapse: **zero** unconnected
  junction pairs within `min_node_dist` on any case. `graph_stitch` + `graph_fuse` already cover
  CityEngine's *intersect* and *snap*; the stub collapse covers *resolveConflictShapes*. Only
  *mergeNodes* was ever missing, and there is nothing for it to do.
- **The cap does work.** Approach 4 held every case at degree ≤ 4 with no roundabout needed, so the
  realign branch is sufficient in practice and the roundabout is a genuine fallback rather than the
  common path — worth knowing before building roundabout machinery.
- **`needs_roundabout` accumulated stale flags** because it is set inside the repair loop and never
  cleared: 13 nodes flagged on a graph whose maximum degree was 4. Any retry must clear per-pass
  state at the top of the pass.

#### ⚠️ The fifth approach — 2026-08-12. It settles which LAYER the fix belongs to

Built, measured, reverted. **The two checks stay; nothing else does.** The suite is back at
**25 failing with zero baseline movement** — every value bit-identical to the run before the
attempt.

**1. The checks are committed, and they were the point.** `junctions_not_too_close` and
`no_multileg_junctions` (`checks.py`, wired in `run_scene_checks.py`, thresholds read from
`graph_params_min_node_dist`). Red on **C_radial and I_offset_radial**, green on the other seven.
They are why the count went 21 → 25 and that is not a regression: the defect was always there and
nothing could see it. `no_multileg_junctions` clusters junctions within `min_node_dist` **before**
counting arms, which is the only way to see a five-way spelled as three nodes.

**2. The stub collapse works, and it is not the hard part.** `graph_stub_mark` → `graph_stub_kill`
→ `graph_stub_fuse`, after `graph_width`, higher point number snapping onto lower. Measured:

| | before | after |
|---|---|---|
| `junctions_not_too_close` | under **3**, shortest 30.65 m | under **0**, shortest **41.03 m** |
| A · B · D · E · F · G · H | — | **bit-unchanged, all seven** |
| C_radial edges | 86 | 83 |
| hidden multi-leg sites | 3 clusters | **3 explicit degree-5 nodes** |
| suite | 25 failing | **39 failing** |

**3. And the solver mostly survives five arms.** `junction_boundary_is_simple` reports **1**, not 3
— two of the three degree-5 nodes solve cleanly. The failure is **angular, not arity**:

| node | arm gaps | verdict |
|---|---|---|
| (−177.4, −254.9) | 48.5 · 90.1 · 89.7 · 90.8 · **40.8** | solves |
| (−56.3, −80.9) | **32.8** · 76.7 · 89.5 · 90.7 · 70.4 | solves |
| (−94.2, 26.5) | 92.0 · 89.5 · 67.3 · **32.5** · 78.6 | **inverts** |

**4. The root cause is confirmed and it has a closed form.** Two mouths `phi` apart, each cut `d`
from the node, clear each other exactly when **2 d sin(phi/2) ≥ hA + hB**. At the failing node a
26.8 m arterial and a 15.1 m collector sit 32.5° apart: the mouths need **d ≥ 37.4 m** and the cut
lands at ~26 m, so they overlap and the boundary folds back. That is the "adjacent corners are
never made aware of each other" defect, measured rather than argued.

**5. Enforcing it through the cut fails in both directions, and the pair of failures is the
result.**

| variant | outcome |
|---|---|
| floor from the **iterating** frame, uncapped | **fixes the inversion** — `junction_boundary_is_simple` 1 → **0**, `selfx_roads` 1 → 0, folds 1 → 0, `no_downward_faces` 1 → 0 — and **runs away**: `trim_leaves_road_standing` min_standing **−2363 m**, min_ratio −156, `every_mouth_has_a_road` 0 → 10, `selfx_junction_surface` 24 → 364 |
| floor from the **node** frame, capped at `maxfrac × shorter arm` | no runaway, and **too weak** — the inversion returns, 40 failing |

⚠️ **The runaway is positive feedback, not a bad constant.** Moving the cut out re-reads the tangent
on a curved arm, which *narrows* the gap, which raises the floor, which moves the cut further — and
`dist` is monotone from pass 3, so it latches instead of oscillating. Any retry must compute this in
the fixed node frame.

⚠️ **AND THE CAP CANNOT BE RAISED TO CLOSE THE GAP.** The mouths need 37.4 m; the fillet's own cap
allows `0.4 × 48.8 = 19.5 m` on the shorter arm. Trimming to 37.4 m would eat 77% of a 48.8 m
street. **Two streets that close cannot be separated by trimming, at any threshold.**

#### The layer question is now settled — by measurement, 2026-08-12

The table above asked *"either `merge_angle`'s 20° default is too tight for real traced fields, or
32.5° is genuinely two streets and the graph-level fix is the correct one — settle this before
building either."* It is settled: **the graph level.** A corner solver cannot fix 32.5° between a
26.8 m and a 15.1 m street, because the required cut exceeds the street. The cap-arms-at-4 rule is
not a stylistic preference borrowed from AASHTO; it is what the geometry forces.

**Two further findings from the same run, neither shipped:**

- ⚠️ **`graph_min_angle` deletes the wrong street.** On the live radial scene the collapsed
  five-way's crowded pair is **13.2°** — inside `min_junction_angle` (25°), so the existing rule
  fires and drops one. It keeps *the longer*, which is a 202.5 m **local**, and deletes a 151.8 m
  **arterial**. Width-first with length as the tie-break reverses that and leaves a clean four-way
  of 59.7 · 120.3 · 57.2 · 122.8° — the arterial goes straight through, the lesser street gives
  way, which is the principle §S5 already uses for the corner radius. Three lines, measured, and
  reverted with the rest only because it has no value without the collapse.
- **One parameter would land the whole thing today, and it is the resolution practice ranks last.**
  All three sites have crowded pairs at 32.5–40.8°; raising `min_junction_angle` to ~35° makes
  `graph_min_angle` resolve them by dropping the lesser street. That is **eliminate a leg**, which
  §S3's *"a connection is never refused"* forbids. It is recorded as a decision for the artist, not
  taken here.

**So the remaining work is exactly one thing, and it is the one practice prefers:** realign the
minor leg into a separate T. Everything under it is now measured — which leg is minor (class, then
width, then length), why a 4-arm cap is forced rather than chosen, and why the corner solver must
not be asked to absorb it.

#### ✅ The sixth approach WORKS at the junction layer — 2026-08-12. Artist's rule, artist's framing

Hannes, reading the measurement back: *"if 2 streets land in the same place is this not the answer?
those streets can probably form the T junction before it goes into the 4 way."* That is the
resolution practice ranks first, and it reframes the number that had looked like a dead end.

⚠️ **THE SAME INEQUALITY THAT SAYS THE FIVE-WAY IS UNSOLVABLE SAYS WHERE THE T GOES.** Two mouths
`phi` apart need `2 d sin(phi/2) ≥ hA + hB`. Read as a trim it is fatal — 37.4 m off a 48.8 m
street. Read as an *offset* it is the answer: at `d` the two streets have already separated by a
full street width, so a junction there fits by construction. Floored at `min_node_dist`, because a
T closer than that is the jog this section exists to remove.

**Built:** `graph_realign`, after the stub collapse. At any node with ≥ 5 arms it takes the tightest
angular pair, picks the **minor leg by width then length**, and moves its approach onto the major
arm at arc distance `d` — clamped to half of each arm — with the offset **blended to zero over
`max(3 |offset|, 2 min_node_dist)`**. That blend is the whole difference from the two attempts that
failed: they relocated one vertex and left the rest of the leg behind, so it met its host at a kink
and a shallow skew. Here the leg keeps its own shape and arrives with one gentle curve behind it,
which is what S3b's clamp is for. The far end never moves. One arm per node per pass; the repair
loop is a fixed point, so a six-way resolves over two passes.

**Measured on C_radial and I_offset_radial — every one of these was red before:**

| check | before | after |
|---|---|---|
| `junctions_not_too_close` | under 3 | **0** |
| `no_multileg_junctions` | max_arms 5, over_cap 3 | **max_arms 4, over_cap 0** |
| `junction_boundary_is_simple` | 1 | **0** |
| `selfx_junction_surface` | 24 | **0** |
| `graph_reaches_a_fixed_point` | — | **converged, 12 passes** |

**No street is deleted.** The five-way becomes a four-way plus a T, which is what §S5a has said the
answer is since 2026-08-11 and what nothing had built.

⚠️ **AND IT REGRESSES THE LAYER BELOW IT. NOT DONE.** Newly red on the same two cases:
`block_boundary_closes` · `city_is_fully_paved` · `lots_clear_of_roads` · `lots_tile_blocks` ·
`no_downward_faces` · `no_sweep_fold_after_trim` · `selfx_roads` · `trim_metric_is_consistent` ·
`lots_are_simple_polygons`. Counts moved **edges 83 → 77, blocks 28 → 23, lots 764 → 719**, and
`trim_leaves_road_standing` reports **1.523 m standing** at (−137.7, −250.22). Suite 25 → 39: the
same total as the collapse alone, with the failures moved from the junction layer to the block
layer. **Six edges vanish that the realign did not intend to remove, and which node removes them is
not yet known.** The other seven cases are untouched.

#### ⛔ AND THE AUDIT KILLED IT. `graph_realign` MOVED THE JUNCTION, NOT THE LEG — 2026-08-12

Independent audit on the build above (dev-loop Rule 0). Verdict: **do not keep it.** Reverted; the
suite is back at 25 failing with the baseline in sync.

⚠️ **ONE LINE, AND IT IS THE WHOLE DEFECT.** The blend loop starts at `k = 0`, and for the minor
prim `pv[0]` **is the shared junction point** — shared by every incident arm after
`graph_stub_fuse`. At `k = 0`, `acc = 0`, so `t = 1.0` and `setpointattrib(0, "P", …)` writes the
full offset onto **the node**. It does not move a leg onto its neighbour; it **translates the whole
junction 40 m and drags all five arms with it.** The code's own comment — *"the whole approach
blends, the far end never moves"* — is true for one arm in five. Measured, C_radial pass 0: three
junction points move 40.000 / 40.000 / 39.452 m, only 14 points move in the entire graph, and the
four non-minor arms get **no blend at all** — their second vertex stays put while their endpoint
jumps 40 m (prim 1, a 26.8 m arterial: its second vertex was 1.4 m from the node and is now 40.9 m
out; length 72.32 → 111.84).

⚠️ **SO THE T NEVER FORMS, AND THE ARM CAP IS REACHED BY DELETING STREETS.** Immediately after the
realign the three nodes are **still degree 5, just 40 m away**. They only reach degree 4 in pass 2,
when the drag has pushed arms below `min_junction_angle` (25°) and `graph_kill_angle` blasts them:
**8 deletions across passes 1 and 2, two of them arterials.** With the realign bypassed,
`graph_kill_angle` deletes **0 in every pass**. `no_multileg_junctions` went green by **eliminating
a leg** — resolution 3, the one §S3 forbids outright.

⚠️ **AND THE CHECK THAT REPORTED SUCCESS CANNOT TELL THE TWO APART.** `no_multileg_junctions`
counts arms; deleting an arm satisfies it exactly as well as realigning one. **Nothing in the suite
asserts *"a connection is never refused"*.** The missing assertion is one line and it would have
gone red on the first run: **`graph_kill_angle` deletes 0 prims after pass 0**, or the published
edge count never falls below the pre-repair count. Junction health and street preservation are
asserted separately and never together — the union check, again.

Also measured, and to be fixed with it:

- **The realign's "wins" are probably the deletions.** `junction_boundary_is_simple` 1 → 0 and
  `selfx_junction_surface` 24 → 0 are both at node 16 — the node whose 26.8 m arterial arm
  `kill_angle` deleted. *(Inferred from the deletion list plus the site coordinates, not isolated.)*
- **Convergence got worse and nothing noticed**: OFF settles at pass 2; ON churns 81 → 89 → 81 → 77
  and settles at pass 4. `graph_reaches_a_fixed_point` still passes, because it only asks whether
  it *eventually* stops.
- **`realigned`, `kill_angle` and `kill_stub` ship on `OUT_graph2`,** and `realigned` is **stale** —
  the final pass moves 0 points and flags 3 prims. The `needs_roundabout` stale-state failure this
  section already warns about, reproduced exactly.
- **The branch has one test graph, not two.** C_radial and I_offset_radial publish **identical
  point sets**; they differ only in `lots_params_subdiv_mode`. The other seven never reach degree 5,
  so the wrangle body never executes. §9 item 1(c) — the hand-drawn 5-star — is the only thing that
  would give this independent coverage.
- **Refuted, so do not chase them:** `graph_prune`, `graph_drop_orphans` and `graph_drop_tongue` are
  per-pass identical in both builds. The published graph is *clean* — 0 crossings, 0 folds, 0 prims
  under `R > halfwidth`, turn clamp converged on all 77. The damage downstream is not a malformed
  graph, it is a **smaller** one.

**THE FIX, FULLY SPECIFIED — this is now a small job, not a research problem:**

1. **Detach the minor leg's endpoint before moving it.** `addpoint` at `land`, `setvertexpoint` the
   minor prim's terminal vertex onto the new point, leave the junction point where it is, and start
   the blend at `k = 1`. `graph_stitch` then has a free endpoint lying on the host polyline and can
   split it into the T — which today it never gets the chance to do. **The blend machinery itself is
   correct and should be kept as is.**
2. **Drop or re-project the host's vertices inside `d`.** prim 50's landing point is 39.45 m out and
   its own vertex sits at 38.9 m, leaving a 1.1 m segment at `dot = −1.000`. prim 7 escaped only
   because its first segment happened to be 47.3 m long. Whether the host folds is luck of vertex
   spacing.
3. **Never realign two adjacent nodes in the same pass.** prim 10 joins two realigned nodes and is
   blended from **both ends at once**, over 105 m of its 131 m length: 131.02 → 79.07 m and a
   zigzag. "One arm per node per pass" is not a bound when the nodes share an edge.
4. **Commit the street-preservation assertion first** (above), or the next attempt can pass the
   same way this one did.

#### The seventh approach — the realign is FIXED, and C_radial cannot take it. 2026-08-12

Built on the audit's four-point specification above. **Three of the four are in; the fourth turned
out to be the wrong shape of problem.** What ships: the missing assertion, a `graph_realign` that
moves the leg instead of the junction, and a feasibility gate on the stub collapse. What does not: a
green `no_multileg_junctions` on C_radial, because at that field's density there is nowhere to put
the T.

⚠️ **§9's blocking entry is now stale** — it says *"Not built. Nothing of it ships"* and items 3 and
4 are no longer accurate. It was left untouched here only because a concurrent owner boundary ran
through it; it needs the correction below folded in.

##### 1. The assertion first, and it is a tripwire rather than a measurement

`connections_are_never_refused` (`checks.py`, wired in `run_scene_checks.py`). It asserts S3's
*"a connection is never refused"* directly: **`graph_kill_angle` may delete 0 primitives in any pass
after pass 0.** Pass 0 is exempt because `graph_min_angle` exists to remove the near-parallel
duplicates *tracing* produced; from pass 1 the graph is being repaired, not cleaned, so a kill there
is a repair destroying a street to make its own numbers work.

⚠️ **It had to be instrumented, because per-pass state is not reachable from outside the asset.**
`repair_end` is a feedback block and its **Single Pass re-runs ONE iteration from the original
input** instead of stepping the feedback — measured, `repair_iterations` came back **1** for every
requested pass 0–7. So `graph_min_angle` now counts the prims it flags and accumulates
`repair_killed_pass0` / `repair_killed_late` through the loop, and the check reads them off the
published graph. A MISSING attribute fails rather than skipping.

Committed and run before any HDA change: **green on all nine cases, zero baseline movement, 25
failing unchanged.** `graph_kill_angle` deletes 0 in every pass on every case in today's build,
which is what makes it a tripwire rather than a measurement.

##### 2. `graph_realign`, with the defect removed

Exactly as the audit specified: `addpoint` at the landing, `setvertexpoint` the minor prim's
**terminal vertex** onto it, the junction point never written, blend from `k = 1`. The blend
machinery is unchanged — it was correct. Three things around it are new:

- **The landing is a host VERTEX, not an arc position.** An interpolated landing lands wherever it
  lands — prim 50's was 39.45 m out with the host's own vertex at 38.9 m, and prim 7 escaped a fold
  only because its first segment happened to be 47.3 m. Snapping to the host's own vertex removes
  the sliver by construction instead of by luck, which does the same job as dropping or re-projecting
  the host's vertices and is five lines. It also sets the floor: the landing can only be placed on
  the vertex grid, so the floor is `min_node_dist + one resample step` = **45 m**, not 40.
- **`busy[]` refuses any node ADJACENT to one already realigned this pass**, which is the bound
  "one arm per node per pass" was not. The repair loop is a fixed point, so deferring a node costs a
  pass and nothing else.
- **Per-pass state is cleared** at the top of the block (`graph_stub_mark` zeroes `kill_stub` and
  `realigned` on every prim), and `repair_scratch` now deletes `kill_angle`, `kill_stub` and
  `realigned` so none of them ship on `OUT_graph2`. Both were audit findings; the stale `realigned`
  was the `needs_roundabout` failure reproduced exactly.

##### 3. ⚠️ AND IT DID NOTHING AT ALL FOR A WHOLE SUITE RUN, ON ONE WRONG FUNCTION

The new-junction proximity guard — the rail `graph_extend` already carries, that a new junction may
not crowd an existing one — asked *"is this point a node or just shape?"* as
`len(pointprims(0, p)) == 2`. **An interior vertex of a polyline belongs to exactly ONE prim, not
two.** So every shape point read as a node, every landing had a "node" within `min_node_dist`, and
**every realign was refused.** The wrangle compiled, cooked, errored on nothing and flagged nothing,
and the suite came back **bit-identical to the stub collapse alone** — 39 failing, every value
equal. `neighbourcount(0, p) != 2` is what `graph_extend` uses for the same question and is correct.

**A wrangle that refuses everything is indistinguishable from a wrangle that is not there**, and the
only thing that separates them is a number that should have moved and did not. Worth remembering the
next time a change lands bit-clean.

##### 4. It works, and the artist's own junction is the proof

Measured on `/obj/citygen_examples/C_segmenter` — the scene §S5a's first measurement was taken on.
Inspect-only, nothing saved.

| | before | after |
|---|---|---|
| the triangle | prims of **31.58 · 25.37 · 19.90 m** closing on three junctions | **gone** |
| the site | 3 junctions of degree 3 · 4 · 4, **5 external arms** | one **degree-4** node at (138.27, 262.31) plus a **degree-3 T** at (174.70, 331.27) |
| the four-way's angles | — | **57.24 · 122.81 · 59.67 · 120.28°** |
| the T's angles | — | 131.35 · **48.25** · 180.41°, clear of `min_junction_angle` (25°) |
| shortest junction-to-junction edge | 19.90 m | **46.26 m** |
| max node degree | 4 — the five-way spelled as three nodes, which is why every degree check passed | **4**, and now genuinely |
| edges | 95 | **93** — three stub edges collapsed, one T split added |
| streets deleted | — | **0**. `repair_killed_pass0` = `repair_killed_late` = 0 |
| repair loop | converged, 9 passes | converged, **12 passes** |

The four-way predicted in this section before anything was built was *"59.7 · 120.3 · 57.2 ·
122.8°"*. It came out at 59.67 · 120.28 · 57.24 · 122.81. **Rendered and looked at, both builds,
same crop:** the old pipeline shows three roads knotted into one blob with the junction patches
overlapping; the new one shows a clean four-way and a clean filleted T.

##### 5. ⛔ AND C_RADIAL CANNOT TAKE THE FIX. THAT FIELD IS AT THE JOG RULE'S OWN RESOLUTION LIMIT

This is the finding that matters, and it is a property of the case rather than of the code.

`graph_realign` must land its T at least **45 m** out along the host, and may not move an endpoint
further than **half its own street** — past that it is not realigning a leg, it is dragging one
across the block. So the crowded pair it separates needs **both** arms at least **90 m** long.
C_radial at domain 800, after the stub collapse, measured per site:

| node | arms (m) | crowded pair | `need` | `d` after the clamps | verdict |
|---|---|---|---|---|---|
| (−81.3, −34.5) | 169.7 · 58.7 · 66.6 · **42.5** · 69.3 | 29.53°, arterial + local | 40.4 m | **29.4 m** | refused |
| (−94.2, 26.5) | 69.3 · **81.9** · 245.6 · 97.0 · 48.8 | 32.55°, two collectors | 26.9 m | **41.0 m** | refused |
| (−177.4, −254.9) | 72.3 · 87.5 · **86.0** · 212.0 · 75.2 | 40.82°, two locals | 20.6 m | **43.0 m** | refused |

And the reason is one line of numbers: **the shortest junction-to-junction edges in that whole graph
are 41.03 · 42.53 · 44.09 · 48.85 · 49.28 · 49.84 m.** The entire network sits about one resample
step above the 40 m jog floor. There is no 90 m street anywhere near these nodes to hang a T on,
because at this field density there are almost no 90 m streets between junctions at all.

⚠️ **So the realignment resolution is unavailable here, and it is not a threshold that can be
tuned.** Lowering the landing floor under `min_node_dist` makes `junctions_not_too_close` red by
construction — it builds the jog this section exists to remove. Lifting the half-street clamp gives
the violent version, and that was measured: run ungated, the realign moved endpoints clean across
their own blocks, `trim_leaves_road_standing` reported **−98.88 m standing**,
`block_boundary_closes` 6 open loops and 12 unpaired ends, `selfx_junction_surface` 0 → 120,
`lots_tile_blocks` 3e-9 → 0.065, suite **25 → 41**.

**Re-measured, and it corrects this section's own earlier claim about roundabouts.** A roundabout
needs `R >= need`, so ICDs of **80.8 · 53.8 · 41.2 m** at the three sites. §S5's band is 21–67 m, so
**two of the three DO fit** and only (−81.3, −34.5) does not. The earlier statement that a
roundabout *"cannot deliver it either"* was generalised from the single 32.5° / 37.4 m case and is
too strong. The roundabout is a live option for two of C_radial's three sites and it is the only one
left for them.

##### 6. So the collapse is gated on repairability, and that is the shipped rule

`graph_stub_mark` collapses a jog **only when what it leaves can be repaired**: if the merge would
leave more than four arms, every surviving arm must be at least 90 m
(`2 × (min_node_dist + resample step)`, the realign's own feasibility condition). Every *stub* is
excluded from that arm set, not just the one being collapsed — the defect is a CYCLE of three short
edges, so for any pair of corners the other two sides are incident to both, and counting them as
arms measured 19.9 and 25.4 m and refused the collapse on the artist's own scene until it was fixed.

The rule it encodes: **an unrepaired jog is a smaller defect than a five-way the corner solver
inverts on.** Ungated, the collapse alone is 25 → 39 failing and the collapse plus realign 25 → 41.
Gated: **25 failing, all nine cases bit-unchanged, zero moved values** — and the artist's scene
fixed.

##### 7. What this leaves open

1. ⛔ **`no_multileg_junctions` and `junctions_not_too_close` are still RED on C_radial and
   I_offset_radial**, and on that field they cannot be closed by realignment. The next move there is
   a **roundabout at two of the three sites** (§S5's 21–67 m ICD covers them), or the artist's call
   on `min_junction_angle`.
2. ~~⚠️ **Nothing in the suite executes `graph_realign` or the collapse.**~~ **CLOSED 2026-08-12 —
   see "the eighth pass" below.** `J_five_star` runs the realign and `K_stub_triangle` runs the
   gate's refusal; both are committed and in the baseline. The paragraph is kept because the *shape*
   of the gap is worth remembering: they fired on the artist's live scene and on no test case, and
   that was recorded three times before it was filled.
3. The T's approach angle is whatever the crowded pair's angle was, softened by the blend — 48.25°
   on the artist's scene, against FDOT's *"less than 75 degrees should be avoided"*. Enough to clear
   `min_junction_angle` by construction; not yet a right-angled T. **Re-routing the last stretch is
   still the unbuilt piece**, and it is what would let the landing floor come down and make the
   dense-field sites reachable.

#### ✅ INDEPENDENT AUDIT: SHIP IT — 2026-08-12. And the one latent defect it found

Verdict on the seventh approach: **ship**, all four claims survive measurement, one latent defect
to record. Read-only audit; `C_segmenter` never unlocked, `matchesCurrentDefinition()` still true,
the .hda mtime unchanged, the .hip never saved.

**The number this whole section exists for.** `intersectionanalysis` on the merged city, same A/B
chain:

| | whole city | within 60 m of the site |
|---|---|---|
| pre-fix | 246 | **128 — one 117-point cluster at (149.8, 272.9)** |
| shipped | **131** | **3** at the four-way + **4** at the new T |

That cluster is the tangle the artist has been looking at for weeks. It is gone.

**The T is a genuine split, not a touch.** Prim 0 (arterial 26.8 m, 78.0 m) and prim 1 (arterial
26.8 m, 73.78 m) are two distinct prims sharing point 0, 180.41° apart, with a 14.4 m local as the
third leg. Both halves clear `min_node_dist`. S5 on the live mesher: `junction_boundary_is_simple`
**0 bad of 60 patches**, `selfx_junction_surface` 0, `selfx_roads` 0, `every_mouth_has_a_road` 0,
folds 0, min standing 8.82 m, 0 graph crossings.

**The realigned street is not attempt 6's zigzag.** 202.48 → 156.76 m (it now starts at the T),
max turn 15.84° → **15.74°**, min radius 14.40 → **14.32 m**, turn-sign flips 10/50 → 5/39, uniform
3.92 m segments, no sliver at the landing. City-wide curvature worst 1.003 → **1.009** against 1.02
slack — legal, and it is now the sharpest bend in the city, 8 m from the T. Convergence 9 → 12
passes, genuinely converged (residual 5.1e-5, 0 reversals). Cook cost 0.48 → 0.55 s on B_grid; the
loop is gated behind `if (n < 5) continue` and never executes where there is no five-way.

**The tripwire proved it can fail — on the artist's own scene, without breaking anything.** Bypass
`graph_realign` alone and `connections_are_never_refused` goes **red**: `repair_killed_late` 1, the
casualty being the **151.8 m arterial** from (138.27, 262.31) to (208.95, 396.62), because
`graph_min_angle` keeps the longer 202.5 m *local*. It also fails closed when the attribute is
missing. ⚠️ **Coverage caveat:** it counts only `graph_min_angle`'s flags. Four other nodes in the
repair loop delete prims — `graph_stub_kill` (3, by design), `graph_drop_orphans`,
`graph_drop_tongue`, `graph_prune` — and **nothing asserts any of them**. `orphan_edges_dropped` is
written to the geometry and read by no check.

**The gate refuses on the suite for the right reason, and that was proven the hard way.** Removing
the gate line entirely in a throwaway session makes C_radial produce 3 explicit degree-5 nodes and
`graph_realign` *still* flags 0 prims: it genuinely cannot land a legal T there. Correction to the
seventh approach's write-up — the refusal is driven by surviving **arms** of 48.85–87.45 m against
the 90 m floor, not by the 41–50 m junction-to-junction edge lengths quoted there.

⚠️ **THE LATENT DEFECT — THE FEASIBILITY GATE IS STRUCTURALLY BLIND ON A 3-CYCLE, WHICH IS THE
EXACT TOPOLOGY THIS SECTION EXISTS FOR.** The gate builds its arm set from
`pointprims(pt) + pointprims(other)` — the two endpoints of the edge being collapsed. In a triangle
the **third corner's external arms land on the same merged node over the following passes and are
never counted.** Measured on the live pre-fix graph, replicating the predicate exactly:

| side collapsed | `narm` the gate computes | truth |
|---|---|---|
| prim 86 (31.58 m) | 3 | |
| prim 87 (25.37 m) | 3 | **5 external arms after full collapse** |
| prim 88 (19.90 m) | 4 | |

With three degree-3 corners the gate reads 4 and a genuine five-way results, every time. **Here it
is harmless — the five true arms are 127–191 m, all far above the 90 m floor, so a correctly
counting gate permits the same collapse. The right answer for the wrong reason.** A 3-cycle whose
third corner carries an arm under 90 m would be collapsed against the gate's own rule and left as
an unrepairable degree-5 node: `graph_realign` refuses it, and the result is C_radial's failure
mode — boundary inversion, +24 `selfx_junction_surface`, 39 failing. **No case in the suite would
see it, because no case runs the collapse.**

**Fix, small:** build the arm set by flood-filling the stub-connected cluster containing `pt` and
`other`, then count the external arms of the whole cluster. That also makes the gate's own comment
true. ✅ **BUILT 2026-08-12 — "the eighth pass" below**, and the coverage caveat in the paragraph
above it (the tripwire counting only `graph_min_angle`) is closed there too.

Also confirmed, severity unchanged: the T's 48.25° approach is below FDOT's 75° guidance; nothing
in the suite exercises the collapse or the realign; the 25 baseline failures are pre-existing.

#### The eighth pass — the gate can see the third corner, and the suite finally runs this. 2026-08-12

Three of the audit's items closed: the blind gate, the coverage gap §9 item 1(c) had recorded three
times, and the tripwire that watched one deleting node out of five. **The shipped junction did not
move.** Every number in the "seventh approach" table above re-measures bit-identical — 93 edges,
the degree-4 node at (138.27, 262.31) at 57.24 · 122.81 · 59.67 · 120.28°, the degree-3 T at
(174.70, 331.27), shortest junction-to-junction edge 46.26 m, `repair_killed_pass0` =
`repair_killed_late` = 0, converged in 12 passes.

##### 1. The gate now counts the cluster, and it reads 5 where it read 4 / 3 / 3

`graph_stub_mark` flood-fills the stub-connected cluster containing both ends of the candidate edge
— junctions joined by edges shorter than `min_node_dist`, the same predicate the arm count already
used to exclude stubs — and counts the external arms of the whole cluster. Measured on the live
pre-fix graph, instrumented inside the wrangle itself rather than replicated in Python:

| side collapsed | before | after | arms it now sees |
|---|---|---|---|
| 19.90 m | narm **4** | narm **5** | 127.46 · 131.89 · 156.00 · 165.60 · 193.38 m |
| 31.58 m | narm **3** | narm **5** | the same five |
| 25.37 m | narm **3** | narm **5** | the same five |

`ok` stays 1 because every one of the five is far above the 90 m floor, so all three sides are still
marked `kill_stub` and the collapse proceeds exactly as before. **The right answer, now for the
right reason.** The gate's own comment — *"EVERY stub is excluded, not just the one being
collapsed"* — is finally true of the arm set as well as of the exclusion.

##### 2. ⚠️ AND A COUNTER READ THE INPUT AND SHIPPED A CONFIDENT ZERO

Instrumenting the collapse looked like one line — sum `kill_stub` over the prims after the marking
loop. It came back **0 on a pass that collapsed four edges**. `prim(0, "kill_stub", i)` reads the
INPUT geometry, not the writes this same wrangle has just made, and the attribute does not exist on
the input in pass 0 at all. The count is now taken beside the `setprimattrib` that makes the mark,
where each edge is marked at most once because the scan only ever considers `other < pt`. Same
family as the `pointprims(0, p) == 2` defect two subsections up: **a measurement that silently reads
zero is worse than no measurement**, because it is evidence of the wrong thing.

##### 3. Two hand-drawn cases, and the suite executes the machinery for the first time

`J_five_star` and `K_stub_triangle` in `cases.py`. Until they existed `graph_stub_mark`,
`graph_stub_kill`, `graph_stub_fuse` and `graph_realign` were run by **nothing**: they fire on the
artist's radial scene and on no test case, because A/B/D/E/F/G/H never reach five arms and on
C_radial and I_offset_radial the gate declines before the wrangle bodies execute.

**J — the five-way the realign CAN repair.** Five arms on one node at 0 / 32 / 100 / 180 / 255°,
lengths 200 / 120 / 110 / 200 / 100 m. Every number falls out of `graph_realign`'s own feasibility
condition: `need = (26.8 + 15.1)/2 / (2 sin 16°) = 38.0 m`, floored at `min_node_dist + one resample
step = 45 m`, then clamped to half of each arm — so both arms of the crowded pair must be ≥ 90 m,
and the 32° pair clears `min_junction_angle` (25°) so nothing is resolved by deleting a leg.
Measured: **6 edges** (the 200 m host split), a **degree-4** centre at 105 · 100 · 80 · 75° and a
**degree-3 T at (48.00, 0.00)** at 56.70 · 123.30 · 180.00°, shortest junction-to-junction edge
**48.00 m**, `junction_boundary_is_simple` 0, `selfx_junction_surface` 0, converged in 5 passes and
**every deletion counter 0**. The cap is reached by realigning, not by refusing a connection, and
now something asserts that.

**K — the stub triangle the gate must refuse.** Three sides of 32.00 / 32.25 / 32.25 m, corners
carrying 2 + 2 + 1 external arms — the same 3 · 4 · 4 degree histogram and the same five external
arms as the artist's site — and the third corner's arm is **55 m**, under the 90 m floor. Measured:
the gate refuses, the triangle stays at degrees 4 · 4 · 3, `repair_stub_pass0` 0, **nothing
deleted**, converged in 3 passes, and **no degree-5 node ships**.

⚠️ **THE FIRST VERSION OF K PROVED NOTHING, AND THE A/B IS WHAT CAUGHT IT.** With the third
corner's arm at 80 m the pre-fix gate collapsed the triangle and `graph_realign` then succeeded
anyway — it only ever tries the **tightest** angular pair, and that pair happened to be two other,
longer arms. The case would have been committed green on both builds. The arm is now 55 m and the
four outer bearings are placed so the merge leaves arms at 47.0 / 79.1 / 180.0 / 250.0 / 310.0°,
which puts the tightest gap on the short arm. Run against the pre-fix definition:

| | pre-fix gate | shipped gate |
|---|---|---|
| edges | **5** — the triangle collapsed | **8** — it stands |
| max node degree | **5** | **4** |
| the node | one at (0, 0), gaps 60.01 · 96.99 · **32.08** · 100.91 · 70.0 | three at degrees 4 · 4 · 3 |
| arms | 200 · 150 · 210 · 170 · **84.53** m | 200 · 150 · 189.63 · 151.42 · **55.00** m |
| `graph_realign` | refuses — 84.53/2 = 42.27 m against a 45 m landing floor | never asked |

A collapse **lengthens** the third corner's arm, because its foot moves to the merged node: 55 m
becomes 84.53 m and is still under the floor. That is the failure mode this section exists for,
reproduced in a committed case for the first time rather than argued from the live scene.

⚠️ **K IS RED ON TEN CHECKS AND THAT IS THE POINT**, on the same precedent as I_offset_radial. Two
are universal (`no_scratch_attribs_lots`, `selfx_city_merged` fail on all eleven cases). Two are the
jog itself: `junctions_not_too_close` under 3, shortest 32.00 m, and `no_multileg_junctions`
max_arms 5, over_cap 1 — the cluster IS a five-way and the check is right to say so. The other six
are the damage that follows three junction patches solved into the space of one:
`selfx_junction_surface` **50**, `trim_leaves_road_standing` **−13.43 m standing**,
`every_mouth_has_a_road` 6 of 11, `lots_clear_of_junctions` 54.2 m², `lots_clear_of_roads` 54.2 m²,
`block_boundary_closes` 6 open loops. **That is the artist's original defect, in numbers, on a scene
of eight streets.** The rule S5a ships — an unrepaired jog is a smaller defect than a five-way the
corner solver inverts on — now has both of its sides on the record instead of one.

Suite **25 → 37 failing**: 25 unchanged, J adds 2, K adds 10. The only value that moved on the nine
pre-existing cases is `connections_are_never_refused`'s own, which necessarily got wider.

##### 4. The tripwire watches five nodes, and it was watching one

`connections_are_never_refused` counted only `graph_min_angle`'s flags — the same blind spot as the
gate, one level up. Four other nodes in the repair loop delete primitives and nothing asserted any
of them. All five now publish `repair_<stem>_pass0` / `repair_<stem>_late`, accumulated through the
feedback loop:

| node | what it deletes | verdict when it fires late |
|---|---|---|
| `graph_min_angle` | one of two near-parallel arms | refusal |
| `graph_prune` | short dead ends | refusal |
| `graph_drop_orphans` | components with no junction | refusal |
| `graph_drop_tongue` | arms the mouth has eaten | refusal |
| `graph_stub_kill` | the jog edge | **BY DESIGN** — reported, never counted |

The stub collapse is separated rather than ignored, because **a by-design deletion nobody counts is
indistinguishable from a refusal** — which is exactly how the sixth attempt shipped green.

**The pass-0 exemption generalises, and that is measured rather than assumed.** Across all nine
pre-existing cases every deletion happens in pass 0 — prune 0–3, orphan 0–3, tongue 0–8, `late`
zero everywhere — so a late deletion is a repair destroying a street, not tracing residue being
cleaned. **Proven able to fail, per node, on throwaway copies:** bypass `graph_realign` and
`graph_min_angle` kills the **151.78 m arterial (208.95, 396.62) → (138.27, 262.31) in pass 1**,
which is the seventh approach's proof case unchanged; forcing one late removal in `prune_mark` gives
`graph_prune` 65 late, in `graph_mark_orphans` gives `graph_drop_orphans` 11 late, and both go red.
`orphan_edges_dropped` — written to the geometry since S3 and read by no check — is now accumulated
and asserted alongside the rest.

##### 5. The cluster is not only a triangle, and a four-junction CHAIN is where the two changes meet

Branch coverage for the flood fill past the 3-cycle, measured in an isolated session on a chain
A(0,0) · B(30,0) · C(60,0) · D(90,0) — three 30 m links, six external arms hung 2 · 1 · 1 · 2. The
gate reads **cluster = 4, narm = 6**, so the fill finds every member and terminates. Then the two
variants diverge, and the A/B against the pre-fix definition is the whole argument for both tasks
at once:

| B's arm | pre-fix gate | shipped gate |
|---|---|---|
| 150 m (all six arms ≥ 90) | narm **2 / 3** → permits · **3 edges of 9** | narm **6**, ok 1 → permits · **3 edges of 9** |
| 60 m (one arm under 90) | narm **2 / 3** → permits · **3 edges of 9**, six streets lost | narm **6**, ok 0 → **REFUSES** · **9 edges of 9, nothing lost** |

**The gate's blindness was never really about triangles.** It was about counting two corners of a
cluster of any size, and on a chain of four the pre-fix gate saw at most 3 arms of the 6 that exist.
Where that cluster cannot be repaired, the corrected gate now keeps **all nine streets** instead of
publishing three.

⚠️ **And the top row is a defect this section did not know about, which the widened tripwire found
on its first outing.** Both builds lose three streets there — and the counters say who took them:
**`repair_orphan_late` = 2**, `graph_drop_orphans` deleting two components *after* pass 0, with
`repair_killed_late` 0 throughout. It is **not a regression** (bit-identical on both definitions,
and the collapse itself is by design at `repair_stub_pass0` = 3); it is a pre-existing hole in the
permissive branch — collapse a wide cluster, let the realign work on the six-way it makes, and
pieces of the city come off. Nothing could see it before, because nothing counted anything but
`graph_min_angle`.

**The next case is fully specified and deliberately not added here**, to keep this change to the two
the work was scoped for: the chain above with B's arm at 150 m, expected red on
`connections_are_never_refused` with `graph_drop_orphans` 2 late. It is the third hand-drawn case
and it is half an hour's work.

##### 6. ⚠️ AND IT WENT RED ON THE ARTIST'S OWN SCENE, ON ITS FIRST RUN

`graph_drop_tongue` deletes a **42.00 m arterial, 26.8 m wide, from (−240.37, 232.73) to
(−210.19, 203.54), in PASS 1** of `/obj/citygen_examples/C_segmenter`. It reproduces with
`graph_realign` bypassed, so it is not the realign's doing, and it is nowhere near the S5a site — it
is pre-existing behaviour that nothing has ever counted. All eleven suite cases are green on this
term, so **the suite still cannot see it**.

**Whether that is a defect is a design decision and is deliberately left open here.** The tongue
drop is a designed mechanism with its own checks, and an arm the mouth has already eaten may only
become measurable once the geometry settles, which is an argument for allowing it late. Against it:
S3 says a connection is never refused, this is a 42 m arterial, and the rule that exempts pass 0 for
every other node in the loop is that from pass 1 the graph is being repaired rather than cleaned.
**One street on one scene, now visible, with a number on it.** It needs the artist's call, not the
implementer's.

#### ✅ AUDIT OF THE HARDENING: DONE — and the tripwire was condemning a sanctioned deletion

Independent audit, 2026-08-12, read-only (both .hda md5-unchanged after every experiment,
`updateFromNode` never called, .hip never saved). Verdict: **the three tasks are done.** The
artist's junction is provably unchanged, not merely observed to be: the pre-collapse graph has
exactly **four** candidate edges — the triangle (19.90 / 25.37 / 31.58 m) plus a separate **0.67 m
jog at (−100.35, −136.33)** — the flood fill takes all three triangle sides from `narm` 4 / 3 / 3
to **5 / 5 / 5** (arms 127.46 · 131.89 · 156.00 · 165.60 · 193.38 m, all clear of the 90 m floor)
and leaves the 0.67 m jog's predicate untouched, so the shipped output *cannot* have moved.

⚠️ **CORRECTION: `repair_stub_pass0` is 4, not 3.** The earlier note missed the 0.67 m jog.

**The flood fill was proven on chains, not argued.** Two control scenes: CHAIN3 (three junctions in
a line, 55 m arm on the *middle*) and CHAIN4 (four junctions, 55 m arm on the *far end*). Both are
refused by the shipped build and collapsed by the pre-fix one. CHAIN4 is decisive — a pair-only
gate reads `narm` 4 on the A–B stub and permits, so refusal is only possible if the fill walked
three stubs to reach D. Termination is structural (each point appended at most once). One residual
**under-count**, narrow and unreproduced: a ≥ 40 m edge joining two cluster junctions becomes a
self-loop after the merge and is counted as one arm, which makes the gate slightly *permissive*.

#### ⚠️ …AND THE TRIPWIRE SHIPPED RED ON THE ARTIST'S OWN SCENE, FOR A DELETION THE DESIGN ASKS FOR

`repair_tongue_late` is **1** there: a **42.00 m arterial** at (−240.37, 232.73) → (−210.19, 203.54),
dropped by `graph_drop_tongue` in pass 1. **Pre-existing** — with all four S5a nodes bypassed the
graph is 95 prims converging in 9 passes, this section's own pre-S5a numbers, and the drop still
happens. **Root cause located:** in pass 0 that node has three arms; pass 1's extend/stitch lands a
fourth, and `s5j_tongue_mark` only considers dead-end arms off nodes of degree ≥ 4 — so the 42 m
arm became a candidate the instant the node reached degree 4. *Late* is normal for it.

**Fixed 2026-08-12: `graph_drop_tongue` is reclassified as by-design** in
`connections_are_never_refused` — reported in the value dict, not added to `refused`. The
classification is decidable from the code's own rails rather than from taste: `s5j_tongue_mark` is
guarded to LEAF arms only and must leave the node three arms, so the arm it removes already went
nowhere and no connection between two places is refused. **`G_tongue` is a committed case whose
whole purpose is to assert that this drop HAPPENS** — counting it as a refusal put two committed
checks in direct contradiction. Verified after the change: refused = 0 on the live scene, the check
passes, and `repair_tongue_late` 1 is still recorded rather than hidden. Suite unmoved at 37.

**A tripwire that is red-by-design on the primary scene is a tripwire someone mutes** — which is
precisely the failure this section exists to prevent. `graph_prune` stays in the refusal set: it is
arguably the same by-design case, but nobody has read its rails the way the tongue's were read.
Read them before reclassifying it.

#### ⚠️ AND K's OWN NUMBERS REFUTE THE RULE K WAS BUILT TO JUSTIFY

`K_stub_triangle`'s reds are **expected** and must stay recorded as such: 10 checks, of which 7 are
red *only with the fix*, because the refusing build keeps the jog while the collapsing build
removes the triangle and ships 0 blocks / 0 lots, making every lot check vacuous. But
`selfx_junction_surface` **50**, six dead mouths and **−13.43 m** of over-trim are not lot
artifacts: they are three junctions 32 m apart whose patches overlap.

⚠️ **And the load-bearing measurement: `junction_boundary_is_simple` is 0 in BOTH builds on K.** The
corner solver does **not** invert on K's five-way. So this section's stated rule — *"an unrepaired
jog is a smaller defect than a five-way the corner solver inverts on"* — is refuted by the very case
built to justify it. **It is the right call for C_radial, where it was measured. It is not a general
law, and it must stop being written as one.** Whether refusal or collapse is better on a given
site is an open question, not a settled one.

Minor, recorded: `cases.py` says J's landing is "exactly 45 m"; it measures **48.0 m**. The T's
approach is **48.25°**, below FDOT's 75° guidance. `orphan_edges_dropped` still ships on
`OUT_graph2`, is read by no check, and is now superseded by `repair_orphan_pass0/late`.

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

#### ⚠️ Where the thresholds came from — researched 2026-08-11, after they shipped

Hannes: *"did you ever check how lots are sized in real world, and also how all the other tools are
sizing them we checked out?"* **Fair challenge — only one of the four had a researched source.**
`max_aspect` 4.0 came from the Unreal sample's HDA; `min_lot_width` 6.0 was chosen to match the
existing `min_frontage`; `min_street_edge` 8.0 was chosen; `target_lot_area` 600 is an inherited
default of unknown provenance. Researched properly now.

**Real parcels, in metres:**

| typology | width × depth | area | aspect |
|---|---|---|---|
| Amsterdam canal house | **6** × ~30 | ~180 m² | ~5:1 |
| US row house (APA PAS 164) | **6.1** (20 ft) × 27–30 | 167–186 m² | **4.5–5.0:1** |
| — obsolete below | 4.9 (16 ft) | | |
| US urban lot | — | 139–465 m² | |
| US suburban, quarter acre | **22.9** × 44.2 | 1012 m² | **1.9:1** |
| US suburban, typical district | — | 697–929 m² | |

**What the other tools do:**

- **CityEngine** — `lotAreaMin` / `lotAreaMax` (an area **band**, not a target), `lotWidthMin`,
  `irregularity`, `offsetWidth` for the offset mode, plus `cornerAngleMax` / `cornerWidth` for
  **corner lots as a distinct case**. ⚠️ **No aspect-ratio constraint at all.** Minimum *width*
  carries the shape discipline.
- **The Unreal sample** — `1.3 / 4 / 10` aspect ladder with `min_size` 2000 m² and a
  `new_york_lot` band of 5699–9857 m². That is Manhattan-density downtown; its 4.0 was never
  aimed at row housing.

**Two conclusions, both against what shipped:**

1. **`min_lot_width` 6.0 m is right, and now has a source.** Amsterdam is 6, the US row minimum is
   6.1, and below 4.9 is called obsolete. Keep it.
2. ⚠️ **`max_aspect` 4.0 is too tight for the typology this project calls very important.** A
   genuine terraced/row parcel is **4.5–5.0:1** and our ladder rejects it as `elongated`. We
   imported a downtown number and applied it to row housing. And a single global ratio cannot serve
   both typologies at once — row is ~5:1, suburban is ~1.9:1 — so the threshold is either
   per-`land_use` / per-mode, or it is replaced by CityEngine's answer: **minimum width plus an
   area band, with no ratio at all.**

**And the reframe this gives §S8's open task.** The shipped median parcel is **~9 m wide × 45 m
deep**. That width is row-house; that depth is suburban; **no real typology is 9 × 45.** Real row is
6 × 30, real suburban is 23 × 44. So the subdivider's defect is not "parcels too small" — it is that
**depth is a free variable while width is being squeezed**, which is exactly what task #15 fixes.
The target is not a bigger lot, it is a *coherent* one: pick the typology, pin depth, let frontage
follow — which is what `offset` mode already does and `recursive_obb` does not.

#### Junction repair used to be recorded here — moved to §S5a, 2026-08-12

The stub-edge collapse, the 5-arm solver defect it uncovered and the four reverted approaches
were written in the middle of the lots section, which is where two later sessions failed to find
them and re-reported the defect as new. They are junction work and now live in **§S5a**.

#### The buildability ladder — a fifth source, and the first one that actually implements it

Every source above *names* viability; the Unreal sample is the only one that ships a working
rejection test, and Hannes remembered it correctly. Read out of
`resources/citygen/unrealCitygen/houdini/otls/City_Processors.hda`, node
`city::lot_processor::1.0/group_too_small_or_elongated_ones`, verbatim:

```
@maxSide = max(v@size.x, v@size.z);           // bbox of the lot
@minSide = min(v@size.x, v@size.z);
if (@minSide < minSide_actor)   → group 'nonPrefabCompliant'
if (@maxSide/@minSide > 1.3)    → group 'elongated'
if (@maxSide/@minSide > 4)      → group 'superElongated'
if (@maxSide/@minSide > 10)     → group 'not_buildable'
```

Three things transfer, and one does not.

1. **The groups are consumed, not just written.** `blast4` deletes `not_buildable` and `blast5`
   deletes `superElongated`; `elongated` routes to a different building treatment rather than
   being dropped. **Ours is advisory and deletes nothing** (`citygen.md` §2.2), which is a
   deliberate contract — but "advisory" has to mean *routed to another outcome*, the way
   `elongated` is, not *shipped as a house plot anyway*.
2. **The floor is derived from the asset library, not chosen.** `minSide_actor` is read from
   **input 1's bbox detail attributes** — the smallest building prefab they own. The minimum lot
   dimension is *whatever the smallest thing you can put on it needs*. That is a better answer
   than a magic `min_frontage` and it is the one to adopt: S8's floor should come from the
   building catalogue, so the two can never drift apart.
3. **Ratio thresholds are dimensionless and transfer directly**; their absolute areas
   (`min_size` 2000, `max_foot_print_size` 6500, `new_york_lot_min_size` 5699 →
   `new_york_lot_max_size` 9857, a size *band* selecting a building style) do not — the unit
   scale of their scene was not verified, and their target is a Manhattan-density downtown.

⚠️ **What does NOT transfer: their test is on the AXIS-ALIGNED bounding box.** That is only sound
because their city is axis-aligned — `City_Layout.hda` splits along X then Z. Measured on our
cases the two disagree badly, and in the dangerous direction:

| case | lots | AABB ladder (their test) | OBB ladder (ours) | min side, m |
|---|---|---|---|---|
| A_drawn | 83 | 93% / **49%** / 1% | 93% / 61% / 8% | 4.0 · p10 5.4 · med 9.5 |
| B_grid | 619 | 83% / **0%** / 0% | 93% / 59% / **26%** | 2.8 · p10 4.3 · med 8.7 |
| C_radial | 774 | 68% / **21%** / 1% | 90% / 47% / 16% | 2.7 · p10 5.1 · med 10.3 |
| D_offset | 61 | 3% / 0% / 0% | 15% / 0% / 0% | 13.0 · p10 14.3 · med 17.9 |

*(percentages are `>1.3` elongated / `>4` superElongated / `>10` not_buildable)*

**B_grid is the proof: 0% by their test, 59% by ours.** B's field is rotated 18°, so every parcel
is a diagonal ribbon with a near-square axis-aligned box. An arbitrary-angle city must measure the
**oriented** box, which `lot_aspect_ratio` already does — this is one place our check is stronger
than the source's, and the reason is our own requirement (arbitrary angles), not cleverness.

**And the verdict on the shipped build:** under either measure, roughly half of every case's
parcels are what this source would delete outright. `D_offset` is the exception at 0% — because
`lot_depth` pins depth and frontage follows. The European mode already has the shape discipline
`recursive_obb` lacks, which is the shape of the fix.

#### What was built — 2026-08-11

Two parms on `pf_citygen_mesh`, wired like the existing advisory pair, and two tests appended to
the `lots_viability` ladder:

| parm | default | writes |
|---|---|---|
| `lots_params_min_lot_width` | **6.0 m** — OBB short side | `lot_reject` = `"too_narrow"` |
| `lots_params_max_aspect` | **4.0** — dimensionless | `lot_reject` = `"elongated"` |

The full ladder is now `area` → `no_frontage` → `too_narrow` → `elongated`, and the evidence
ships with the verdict: `f@lot_width` and `f@lot_aspect` are published prim attributes, so an
artist can argue with a label instead of taking it on trust.

**It flags; it does not delete.** `citygen.md` §2.2 is unchanged — filter on `lot_viable`
downstream. 4.0 is the ratio at which the researched source *deletes*, so our advisory boundary
and its destructive one are the same number, deliberately.

Measured on the shipped build the moment it landed — **the parcels that would not hold a
building**:

| case | lots | rejected | median ratio | worst |
|---|---|---|---|---|
| A_drawn | 83 | **51 (61%)** | 4.57 | 14.4:1 |
| B_grid | 619 | **367 (59%)** | 5.02 | **31.3:1** |
| C_radial | 774 | **364 (47%)** | 3.78 | 30.8:1 |
| D_offset | 61 | 2 (3%) | 1.01 | 2.1:1 |

⚠️ **These distributions are worse than the ones this section previously recorded, and nothing
got worse.** The old `lot_aspect_ratio` measured `viable_only=True` — it was reporting a median
over the survivors while excluding the very parcels it existed to find. B's true worst parcel is
**31.3:1, not 12.9:1**. Correcting the population is why the numbers jumped.

⚠️ **And the check that measures this had to be rewritten in the same commit, or the feature
would have silently disabled it.** `viable_only=True` becomes a check that CANNOT FAIL the moment
anything sets `lot_viable` from shape: every ribbon is marked non-viable, filtered out of the
sample, and a clean median is reported over what remains. The fix would have read as a triumph.
It now asserts the **label** instead of the population — fail if a parcel the pipeline calls
viable is over the ratio or under the width — which has teeth because the two measurements are
independent implementations (`_obb` in Python here, `pfsl_obb` in VEX there). Currently
`mislabelled: 0` on all four cases, and the distribution over *all* lots is still recorded,
because labelling ribbons correctly is not the same as not producing them and only the baseline
diff can tell those apart.

**Suite: 17 → 14 failing.** `lot_aspect_ratio` passes on all four cases; `no_scratch_attribs_lots`
drops from 9 to 8 (and 5 to 4) because `lot_reject` was being counted as a leak while the shipped
parm help told artists to read it — one of the two was wrong, and the help was right.

#### The third rung — `min_street_edge`, 2026-08-11

Hannes, looking at the result: *"i would maybe add one more parameter which is minimum streetside
length, it is still possible to get long thin lots where no building could fit on."* He is right,
and an independent audit reached the same gap from the other side: **`min_lot_width` is not the
test this section specifies.** Line 2094 asks for *"minimum width at the frontage"*; what was built
is the minimum oriented-box dimension **in any orientation**, which on a shallow wide parcel is the
*depth*, shipped labelled `too_narrow`. At its default it rejected **17 parcels in 1537**, all on
C_radial, because the frontage rung above it already caught the rest.

Three measures, three different questions, and **none implies another**:

| measure | what it answers | blind to |
|---|---|---|
| `min_frontage` — `pfsl_frontage` | how much boundary touches a street, **summed** | three separate 2 m nibbles sum to 6 m and pass |
| `min_lot_width` — OBB short side | narrowest dimension in any orientation | a trapezoid 3 m at the street, 20 m at the back |
| **`min_street_edge`** — `pfsl_street_edge` | **longest UNBROKEN run of street frontage** | — |

`pfsl_street_edge` walks the lot ring twice so a run straddling the start vertex is measured whole,
and clamps to the summed total so a parcel entirely on the boundary cannot report twice its own
perimeter. Default **8.0 m**, `lot_reject` = `"no_street_edge"`. Measured on landing: **+5 on
B_grid, +6 on C_radial**, parcels every other rung passed — small, and exactly the wedge case that
motivated it. Raise it to bite harder; it is art direction, not a threshold with a right answer.

#### What the audit changed — the check was green by luck

An independent audit broke the pipeline eight ways and the check slept through three of them.
Root causes, not counts:

- **Nothing asserted the evidence was published.** `lot_aspect_ratio` computed its own OBB and read
  only `lot_viable`; `lot_width` and `lot_aspect` appeared in the suite exactly once, in an
  *allow-list*, and an allow-list does not require presence. Delete both attributes and the run
  stayed green — so "the evidence ships with the verdict" was prose, asserted by nothing.
- **The reject vocabulary was unasserted.** Relabelling every rejection `"area"` passed.
- **⚠️ The tolerance was 1e-4 against a measured 3.1e-2 disagreement.** The two OBBs are the same
  algorithm at two precisions, not independent implementations, and `lot_aspect` is an **argmin** —
  which is *discontinuous*. Where two candidate rectangles tie in area (C_radial prims 473 and 406
  tie to 1.4e-7 relative) float32 VEX and float64 Python pick **different rectangles** and the ratio
  differs by a finite amount, not an epsilon. C_radial already ships **4 viable parcels within
  0.0312 of the 4.0 line**. The check was one geometry nudge from a red run with no defect present.

Now: five assertions — evidence published · evidence agrees within a band **derived from that
measurement** (0.05, still ~80× tighter than the smallest real defect, since the axis-aligned break
moves aspect by whole integers) · no viable parcel over any threshold, tested on the **published**
numbers so deleting them cannot make it pass · vocabulary closed · `lot_reject` and `lot_viable`
agree parcel by parcel. All four cases clean.

Two smaller ones from the same audit, both fixed: `"worst": sorted(offenders)[:5]` sorted by
`(kind, primnum)`, so the field named *worst* reported the five **lowest-numbered** offenders — it
now sorts by distance past the line; and the threshold lookup in `run_scene_checks.py` was
`parm(x).eval() if parm(x) else <default>`, which **failed open in both directions at once** —
delete the promoted parm and VEX's `ch()` returns 0 while the check silently drops the width
assertion and loosens the ratio, so a missing parameter read green.

#### Round two — the fix for round one's finding did not fix it

A second audit broke the pipeline fifteen ways. **Eleven caught, four green** — and one of the four
was round one's own headline finding, unfixed.

- ⚠️ **Relabelling every rejection `"area"` still passed.** The round-one fix asserted the label is
  a *member of a closed vocabulary*; the property actually violated is that the label must **match
  the reason**. A set containing `"area"` cannot detect relabelling to `"area"`. Membership had been
  substituted for correctness.
- ⚠️ **Deleting `lot_street_edge` passed** — the *identical* defect round one named, repeated on the
  new attribute. It appeared in the suite exactly once, in an **allow-list**, and an allow-list does
  not require presence. The threshold test also read `if edge is not None`, failing open.
- ⚠️ **`pfsl_street_edge` had no verification at all.** Replacing it with the summed `pfsl_frontage`,
  pinning it to `1e9`, and halving it were all green.

Fixed by: `street_edge_control_rig` (fifth control rig in the suite — five hand-computed cases, and
the discriminating one is `nibbles`: three separate 2 m touches where the sum is 6.0 and the longest
run is 2.0); `lot_street_edge` added to the evidence assertion with the fail-open removed; and
`_expected_reject`, which recomputes the ladder from the **published** numbers and the node's
thresholds and asserts it equals `lot_reject`, excluding parcels within the tolerance band of any
threshold they are tested against.

#### Two defects neither round asked about

- ⚠️ **Courtyards shipped rejected.** `lots_subdiv` exempts them (`lt == "courtyard" || fr >=
  minfront`); `lots_viability` then overwrote `lot_viable` with no exemption, so D_offset's two
  courtyards carried `lot_reject` = `"no_frontage"`. The shipped help says *"filter on `lot_viable`
  downstream"* — **doing so deletes every courtyard in every European block**, against this
  section's own "a first-class output, not a discard". Fixed in `lots_viability`, and the check
  needed the same exemption: a courtyard has zero street frontage **by definition**, so the
  threshold assertions must skip it or the two disagree.
- ⚠️ **`lot_type` and `lot_viable` had diverged — 502 parcels** (A 35, B 221, C 246) carrying
  `lot_type` = `"lot"` with `lot_viable` = 0. `lot_type` was written once in `lots_subdiv` from the
  old two-rung test and never updated by the three shape rungs. This section's own principle is
  that advisory must mean **routed to another outcome**, and `lot_type` *is* the routing field. It
  now reads `"unbuildable"`.

#### ⚠️ On shipped data the new rung is decision-identical to raising `min_frontage` to 8

Honest limit, measured. `pfsl_street_edge` returns `min(best, total)` where `total` **is**
`pfsl_frontage`'s sum, so `lot_street_edge <= lot_frontage` identically — 0 of 1537 parcels
exceed it. With `min_street_edge` (8) above `min_frontage` (6), **all 292 `no_frontage` parcels are
also under the street-edge floor**, and `no_frontage` survives only by sitting earlier in the
else-if chain. All 11 parcels the rung newly catches have `lot_street_edge == lot_frontage`
exactly — zero fragmentation. The fragmented case is real (16 C_radial parcels, `frontage − run`
up to 20.78 m) but all 16 are viable, so fragmentation currently decides nothing.

So: *"none implies another"* is true of the three **measures** and false of the two **thresholds as
shipped**. The rung is right and the wedge case it guards against is real; it is simply not yet the
binding constraint on any parcel this suite builds. That changes the moment the subdivider stops
making ribbons, which is the next task.

#### Rounds three and four — the verification was wrong one level deeper each time

⚠️ **Round three.** The suite had a control rig proving the VEX *function* correct on synthetic
input, and a label assertion proving the *label* followed from the *published attribute* — and
**nothing spanning the gap between them.** Corrupt the value where it is written and both halves
agree with each other while the decision is wrong. Six of 27 breaks shipped green; four flipped real
decisions, the worst setting `lot_street_edge` 0.04 under its own threshold, which put **all 1537
parcels inside the tolerance band** and flipped every parcel in every case to unbuildable, green.
Fixed with `_street_edge_xz` — the shipped block ring and lot polygon re-measured in Python, the
treatment `_obb` had always given width and aspect. Also: the band now applies only to the rung that
**decides** a parcel, not all five up front.

⚠️ **Round four, and the sharpest finding of the four: the pipeline half of round three's courtyard
fix was a NO-OP.** `lots_viability` is an else-if chain and a courtyard's frontage is **0 by
construction**, so the chain always short-circuited at `no_frontage`; the exemption then *erased*
that label. Narrowing which labels get erased changed **which verdict was deleted, not which rungs
ran** — A/B'd over 11 threshold configurations, narrowed and blanket were **bit-identical in 9**,
including every configuration with `min_frontage > 0`, i.e. every one an artist can reach. The
exemption now **skips the two frontage rungs inside the ladder**, so a courtyard is still tested on
area, width and aspect.

> **The generalisation, and the reason it took four rounds:** every fix had been validated by
> inspection, never by an **A/B against the behaviour it replaced**. A fix that is a no-op looks
> identical to a fix that works.

Round four also found the coverage hole under the round-three fix: the recomputation sat behind
`if tol is not None and rings:`, so with the blocks withheld it silently did not run and **all six
breaks went green again** — the same defect as round one's allow-list and round two's
`if edge is not None`, three rounds running. **An assertion whose condition is not itself asserted
is not an assertion.** There is now a coverage counter (`recomputed_n` / `uncovered`), plus the two
invariants that make the courtyard exemption more than a word anyone can claim: **zero street
frontage**, and **at most one per block**.

⚠️ And one defect this work introduced and the A/B caught immediately: writing
`lot_type = "unbuildable"` on rejection **erased the only record that the frontage rungs had been
skipped**, so a rejected courtyard became unreconstructable. A rejected courtyard is still a
courtyard; `lot_viable` = 0 carries the rejection.

#### New case: `H_offset_strict`

**D_offset ships 0 rejected parcels, so it caught 0 of 5 rung drops.** The European perimeter block
is a hard requirement of this project and it had the least-asserting case in the suite — a rung that
never decides anything is untested however green the run is. Same defect class as `offset` mode
itself (§4e-6), `max_fillet_fraction` (§4h-2) and the turn clamp (§S3b), and the same cure: a case.
H is D's inputs in `offset` mode with `max_aspect` at **1.8**, chosen from D's own measured
distribution (median 1.01, max 2.10) so it rejects the tail rather than everything. It is the value
that exposed the no-op: at 1.8 the 2.096 courtyard must come back `elongated`, which it could not
while the exemption erased verdicts. Suite is **16 failing** — 14 plus this case's own instances of
the two known S8 failures, no new defect class.

#### ⚠️ Round six — the first PIPELINE defect, and `offset` mode was shipping broken parcels

Five audits found defects in the *verification*. The sixth was asked to sort every finding into
**PIPELINE** (the city Houdini builds is wrong) or **CHECK** (the suite would not notice), and to
lead with PIPELINE even if less severe. It came back with a real one.

**`offset` mode — the European perimeter block this document calls a hard requirement — shipped
6 of 61 parcels self-intersecting and mutually overlapping, at the default `lot_depth`. Five of the
six were labelled buildable.** Measured on `OUT_lots` directly, confirmed by an even-odd raster:
parcels {8,9,10} covering the same 1.94 m², and the *courtyard* eating into the ring parcels.

**Root cause.** `pfsj_inward_offset` is a per-vertex **miter displacement**, not a polygon
**offset**: it moves each vertex along its bisector and removes no self-intersections. Wherever a
concave feature of the block is narrower than 2 × `lot_depth` the inner ring folds through itself,
and because ring parcels are built from consecutive inner vertices the fold propagates into them.
Monotone in depth — 0 broken at 12 m, 6 at 18, 13 at 24, 15 at 30.

**Why six rounds missed it, and this is the half worth keeping:**

- `lots_tile_blocks` is **structurally incapable** of seeing it. A folded polygon's negative lobe
  cancels its positive lobe, so per-block area error stays at ~3e-7 across the whole sweep —
  including at 15 of 61 broken — while 4.6 m² is covered twice. **This is the same cancellation
  §4e-5 already recorded for the Sutherland–Hodgman bridge**, back from a different cause, in the
  other mode.
- `lots_are_simple_polygons` tested *"any vertex lying on a non-adjacent edge"* while its docstring
  claimed that *"covers the pinch and a true crossing alike"*. **False.** Two edges crossing X-wise
  with no vertex near the other edge are invisible to a vertex-to-edge test: the nearest such
  distance on the six offenders ran **0.029 m to 1.14 m against a 1e-3 m tolerance**. The stated
  property and the implemented predicate were different properties.

**The fix, both halves in one commit.** `lots_subdiv` now **bisects the inset down to the deepest
one each block can hold**, testing with `pfsl_ring_is_simple`. `lots_are_simple_polygons` gained an
**exact, tolerance-free edge-edge crossing test** beside the vertex-on-edge one, because the fold
and the pinch are different defects. A/B: reverting the pipeline fix in memory gives **6 caught,
6 viable**; restoring it gives 0, and it returns 0 on all 1476 `recursive_obb` parcels, so it
manufactures no failures. **The check half is sound.** The pipeline half is not, and round seven
took it apart.

#### ⚠️ Round seven — the fold fix is PARTIAL, and three claims made for it were false

**1. The depth cost was misreported here and to the artist.** This section claimed *"median 17.91 m
against a requested 18.0, minimum 17.85, zero parcels below 90%… the fold cost about a centimetre."*
**Wrong measurement.** That was the oriented box's LONG SIDE, which on a parcel wider than it is deep
is the *width*. Measured as depth — distance from the block boundary to the inner ring, two
independent ways that agree — it is **median 16.07 m, minimum 15.55 m, and 30 of 59 parcels below
90% of requested**. Block `B_00000` keeps **15.89 m** and gives up **2.11 m across 31 parcels**.

**2. Simplicity is NOT monotone in depth, so bisection is the wrong search.** 10 of 49 blocks flip
more than once: `C_radial#1` is simple, folds at 8.0 m, is simple again at 10.9 m, folds again at
15.8 m. Bisection assumes one transition and lands in the wrong bracket — it keeps **7.9 m where
15.8 m is available (44% lost)**, and 8.7 m against 21.6 m on another. The ring it returns was
always tested, so this is a depth-quality defect, not a validity one.

**3. ⚠️ A SIMPLE INNER RING DOES NOT GUARANTEE SIMPLE PARCELS.** The fix asserts a property of the
ring; the thing that ships is the parcel, built as `outer… + inner[k2] + inner[k]`. The implication
is false in three independent ways, all with `pfsl_ring_is_simple` returning 1:

- **An inside-out ring the sign guard cannot see.** Over-offsetting past the incenter maps the ring
  to an approximately **point-reflected** copy — and a 180° rotation in 2D **preserves orientation**,
  so `sign(ai) != sign(...)` can never fire, and the reflected polygon is itself simple. `C_radial`
  block 24 at depth 30: inner area +561.3 against the ring's +1034.4, every inner edge antiparallel
  to its outer edge, all 7 parcels bowties.
- **Miter-spike overshoot** crossing the parcel's own outer chain — `pfsj_inward_offset`'s
  `max(dot(bis,n1), 0.5)` permits 2× displacement in a near-arbitrary direction.
- **Duplicate vertices** from the outer-chain walk: its `PFSL_EPS` is 1e-6, a thousand times finer
  than the check's 1e-3, so a block vertex 1e-5 from a station survives and is immediately followed
  by that station.

Measured at the shipped defaults, `offset` mode: **B_grid 2 broken parcels, C_radial 1** — all
labelled buildable. At `lot_depth` 30: **C_radial 8, four buildable**, and 561.76 m² double-covered.

**4. The fix was validated on 2 of the 49 block shapes the suite builds.** D and H are both A's
geometry. Reaching the other 47 is one parm click on a mode this document calls a hard requirement —
the same defect class named three times already (§4e-6, §4h-2, §S3b) with the same cure each time.

**5. `8` bisection iterations is a load-bearing constant that nothing records.** Bisection converges
on the tangency depth by construction, so the residual clearance is set by the iteration count — and
`lots_are_simple_polygons`'s *pinch* half has a 1e-3 m tolerance. At 16 iterations the suite goes
**red with no defect present** (4 parcels at 4.6e-4 m). Raising the search resolution, the obvious
improvement, breaks it.

**Next, in the order round seven prescribes:** add a case running `offset` on a block shape other
than A's two (`C_radial` in `offset` is enough — it goes red on the committed check immediately),
*then* replace the predicate. "The inner ring is simple" must become the property that actually
matters — **each ring parcel is simple**, or equivalently no inner edge is antiparallel to its
outer edge. Case first, so the replacement is measurable instead of argued.

⚠️ **And round six's other finding: round five's pipeline fix was a NO-OP too — the second in a
row.** `lots_subdiv`'s courtyard guard is *dead code*: the courtyard polygon **is** `inner`, and it
is emitted only inside `abs(ai) >= minarea`, so `viable` is unconditionally 1 for every courtyard
that exists and the branch it guards is unreachable. Bit-identical over 48 configurations. Harmless,
kept for the invariant it states — but it is the second consecutive fix that changed nothing, from
the round *after* the one that named "validated by inspection, never A/B'd" as the meta-cause.

> **The lesson that outlived every individual finding:** across six rounds, no defect was ever found
> by reading code. Every one was found by *measuring the difference between two builds* — with the
> fix and without it, at the call site, on shipped geometry. Inspection cannot distinguish a fix
> that works from a fix that does nothing, and it cannot distinguish a check that passes from a
> check that cannot fail.

#### ⚠️ Two failed experiments, and they relocate the cause — 2026-08-11

Hannes chose the typology: *"i think the 10 x 30 sounds about right"* — a middling urban parcel,
~300 m², 3:1. Two attempts to make `recursive_obb` produce it. **Both made every metric worse, and
both are reverted.** `max_aspect` was deliberately left at 4.0 throughout so `rejected` stayed
comparable — the threshold being measured must not move with the thing being measured.

| | median W × L | median aspect | rejected |
|---|---|---|---|
| shipped | 9.5 × 45.4 | 4.57 | **61%** (A) |
| **1. infer frontage, cut across then along** | 4.6 × 73.6 | **15.65** | **73%** |
| **2. cap the OBB long side at `lot_depth`** | 4.6 × 42.1 | **9.68** | **85%** |

1. **Frontage inference is unreliable.** Early in the recursion a piece's longest boundary edge need
   not be street-facing, and an interior piece has no boundary edge at all — so "depth" was measured
   along the wrong axis and then driven harder.
2. **The long-side cap is bounded on paper and never binds in practice**, and *that* is the useful
   result. With the cap at 30 m the median long side still came out **36–42 m**, because
   `W < minfront` fires first: **pieces reach 4.6 m wide before their long side comes down.**

> ⚠️ **Splitting the long axis cannot narrow a piece.** So something else is narrowing them, and it
> is not this stop condition. It is the **force-street-access swap** further down `lots_subdiv`,
> which recurses with no depth limit and drives frontage toward `min_frontage` while never touching
> depth. `lot_aspect_ratio`'s docstring has said exactly this since it was written; both experiments
> assumed the area-only stop condition was the cause instead, and deepening the recursion merely fed
> the swap more opportunities.

**This corrects the hypothesis this section has carried all session** — *"`recursive_obb` splits to
hit `target_area` with no shape term, so it trades width for depth without limit"*. The stop
condition is not where the width is lost. **Fix the swap, not the stop condition**, and both failed
experiments are recorded in the wrangle itself so the next attempt does not start where these did.

**Still open, and the actual cure:** this makes the ribbons *visible*, it does not stop them being
made. Half of every case being unbuildable is a **subdivider** defect —
`recursive_obb` splits to hit `target_area` with no shape term at all, so it is free to trade
width for depth without limit. The fix is to give it the depth discipline `offset` already has,
and its target is now measurable: drive `rejected` towards D_offset's 3%.

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

### The old chain is being retired — status 2026-08-12

The split described further down as "planned" was built, and the original chain was kept beside it
at Hannes' instruction — *"keep the old HDAs around until I am happy with the new ones, so we have
them as reference in case something serious breaks."* **That reference period is over:** once §S5a's
junction shipped he called it, *"you can get rid of the old HDAs now, everything works with the new
ones."*

✅ **`pf_citygen_streets` is DELETED** (2026-08-12). Nothing referenced it — not `cases.py`'s
install list, not a single `createNode`, only prose. The S3–S8 monolith is now only in git history.

✅ **`pf_citygen_trace` is DELETED** (2026-08-12). Its one live consumer, `closure_gate.py`, was
ported onto `tracer → segmenter` first — see *"The retirement, finished"* below — and
`cases.py`'s `HDAS` and the stale `checks.py` docstring went with it. **Both monoliths are now only
in git history, and no new asset has ever had either as a dependency.**

⚠️ **Scene note:** any `pf_citygen_streets` instance left in a .hip — the `A_city` / `B_city` /
`C_city` examples — now has no definition and will load as an unknown node type. Delete those
example nodes; the `*_NEW` chains replace them.

| chain | assets | wiring, read off the live scene 2026-08-12 |
|---|---|---|
| **new** | `pf_citygen_tracer` · `pf_citygen_segmenter` · `pf_citygen_solver` · `pf_citygen_mesh` | `C_field_radial → C_tracer → C_segmenter → C_solver →(out0 splines, out1 junctions)→ C_mesher →` 4 outputs |
| **old, DELETED 2026-08-12** | ~~`pf_citygen_trace`~~ · ~~`pf_citygen_streets`~~ | was `C_field_radial → C_trace → C_city → OUT_C_radial` |

There is one chain now. `pf_citygen_tracer` / `_segmenter` / `_solver` are tracked in git as of
`dc22701`.

⚠️ **The two chains were never independent evidence, which is part of why keeping one cost nothing
to give up.** §S5a's junction defect was measured on both and was **bit-identical** — same prim
numbers, same lengths, same degree histogram. When the old chain agreed with the new one, that meant
the defect predated the split, **not** that the new chain was validated.

### The retirement, finished — 2026-08-12

Hannes: *"make the new nodes independent, they should never have had the old node as a dependency."*
There never was a runtime one — no new asset contains a `pf_citygen_trace` sub-node and not one
parameter expression names it — so what was left of the fork was the **parameter interface** and one
test-harness `createNode`. Both are now gone.

#### Every promoted parameter, measured by who READS it

The pruning the last round refused to do on a weak measurement (*"pruning on the weaker measurement
would delete live parameters, which is worse than a cluttered panel"*) was done on a different kind
of evidence: not "does perturbing it move the output" but **"is there a `ch()` anywhere inside this
asset that lands on it"**. Every parm expression, VEX snippet, `#include`d `.vfl` and Python SOP body
in every descendant node, resolved through the internal parameter-holder nulls to the promoted parm.
A parm nothing references cannot be read at any value, which is the property a perturbation sweep
can only ever approximate.

⚠️ **Two things had to be got right before that scan was worth anything, and the first draft got
both wrong.** `hou.Parm.unexpandedString()` **raises on non-string parms**, so a scan built on it
silently skips every float and int parm — i.e. every channel reference — and reports an asset that
reads nothing. And the trace wrangle builds its channel paths: `string C = "../"; float cell =
chf(concat(C,"min_street_sep"));`. A literal-only `ch("...")` regex misses all of it and reports the
**entire tracing stage** as dead. The scanner's control is the old monolith: on `pf_citygen_trace` it
finds **0 unreferenced of 36** — the node that reads everything it exposes, as it should.

| asset | promoted before | reads | **removed** | top-level entries | folders |
|---|---|---|---|---|---|
| `pf_citygen_tracer` | 36 | 14 | **22** | 14 → 11 | 4 → 1 |
| `pf_citygen_segmenter` | 35 | 22 | **13** | 13 → 3 | 4 → 3 |
| `pf_citygen_solver` | 35 | 7 | **28** | 13 → 1 | 4 → 1 |
| `pf_citygen_mesh` | 15 | 15 | 0 | untouched | — |

**63 decoy sliders gone**, and the evidence per group:

- **Tracer** loses all of `Graph (S3)`, `Streets (S4)` and `Junctions (S5)` — 22 parms, 3 whole
  folders. It contains five nodes (`field_grid`, `field_tensor`, `trace`, `IN_field`, `out`); there
  is no graph, street or junction node in it to read them. It keeps `domain` and `res` (read by
  `field_grid.sizex/cols`), the six S2 parms and the four `Loop Closure` ones (all read by
  `trace.snippet`), and `organic_amp` / `organic_scale` (read by `field_tensor`, and dead for the
  separate recorded reason that no `organic` field generator ships).
- **Segmenter** loses the nine S1/S2 parms and the whole `Loop Closure` folder — 13. It has no field
  generator and no trace wrangle. **This is where the duplicate distance parameter goes:**
  `min_node_dist` 50.0 was the Tracer's, unread here, and `graph_params_min_node_dist` 40.0 — read
  by `graph_extend`, `graph_realign` and `graph_stub_mark` — **exactly three readers, measured;
  an earlier draft of this line said "and two more", and there is no fourth or fifth** — is the one
  that governs.
  One distance parameter now, not two.
- **Solver** keeps `Junctions (S5)` and nothing else — 28 removed, three folders. Every one of its
  seven survivors is read by `junction_solve`. The thin solver the design predicted has a
  seven-slider panel to match.

⚠️ **And the scan was then checked against a measurement that does not share its assumptions**,
because a static scan can only ever miss a mechanism — it had already missed two. The **pre-trim**
copies of the three assets were installed from a scratch backup (never the repo files; no
`updateFromNode`, no `setParmTemplateGroup`), and each of the 63 removed parms was perturbed **on the
asset it was removed from**, hashing *that asset's own outputs* — the exact question, and cheap
enough to afford several values. **295 perturbations, up to three values per parm including both ends
of its range, on `C_radial` and `A_drawn`: not one moved anything.** Scoping the hash to the asset
rather than the whole chain is what makes this stronger than the sweep that was distrusted — a decoy
on the Solver cannot hide behind the Mesher.

**Nothing moved downstream either.** `run_scene_checks.py` before and after: **37 failing**, no *"moved since baseline"*
line in either run, `baseline.json` untouched — and the two runs *after* the change are byte-identical
to each other (against the run *before* it, the comparison is the whole of `K_stub_triangle`'s block
plus baseline agreement on every recorded value, which is the instrument that exists for this).
`parm_liveness.py`: **62 swept · 49 GEOM · 7 ATTR · 6 DEAD, exit 0** — the same 62 as before, because
the 63 removed parms are exactly the ones the sweep already knew not to sweep on that node.

⚠️ **And `parm_liveness` lost the two skip-guards that hid this defect in the first place.** They
existed to stop the sweep measuring the Tracer's copy of a Segmenter parm — which meant that if an
asset re-inherits an interface, the inherited parms are skipped, report nothing, and pass. With the
interfaces trimmed the guards are inert, so they are gone.

⚠️ **AND THE SENTENCE THAT STOOD HERE — *"everything promoted is now swept, and a re-inherited parm
moves nothing, reads DEAD and fails the run"* — WAS FALSE, measured by audit 2026-08-12.**
`parm_liveness`'s `plan` enrols `field_grid · field_radial · tracer · trace · mesh`, and `owner()`
has no solver branch either — it falls through to the mesher. **`pf_citygen_solver` is swept by
nothing.** The arithmetic proves it: 5 + 6 + 14 + 22 + 15 = **62**, the solver's 7 nowhere in it.

**The uncovered asset is the one that carried 28 of the 63 decoys** — precisely the case the alarm
is advertised to catch. A future fork that re-inherits the *solver's* interface passes this run
silently. No live defect today, because the solver's 7 `s5j_params_*` are expression-linked to the
segmenter's copies by `cases.py`'s `_chain()`, so they are exercised indirectly while the segmenter's
copies are swept directly.

**Open, and deliberately not done:** enrolling the solver is not a one-line fix — `p.set()` on a
parm carrying `ch("../…_segmenter/…")` destroys the link and trips the run's own RESTORE DRIFT
check, so the sweep has to perturb the segmenter end instead. **The fix went at the symptom (the
skip-guards) and not at the `plan` tuple, which is where an asset is actually enrolled.** That is
the general lesson: a guard that skips is visible, a plan that omits is not.

#### ✅ AUDIT OF THE TRIM — and the monolith was NOT a control, it was a divergence hazard

Independent audit 2026-08-12, by a route the implementer did not use: every `.hda` expanded with
`hotl -X` and **every** channel reference extracted from the raw contents — `.chn` expressions,
wrangle snippets, node `.parm` values, Python SOP bodies. **Each of the 63 removed names appears
nowhere in the entire contents of the asset that carried it.** That closes the question
*structurally* rather than statistically: a name absent from the network cannot be read by any mode,
toggle, branch or input path, so "live only on a path the suite never runs" is not possible.
Parameters it could not prove dead: **none.** Both indirection classes were re-verified with its own
probe — the `.chn` channel form (`ch("../s5j_params_miter_limit")`, how all 7 solver keeps arrive)
and the `concat()` form (10 sites on the tracer, 5 segmenter, 16 mesh, 8 junction) — and the control
reproduced: 36 promoted / 36 referenced / **0 unreferenced** on the retired monolith.

**Two checks nobody had written, both clean:** every surviving parameter is **template-identical**
before and after — type, default, min/max, label, help, tags, `disableWhen`, hidden, join, folder
*and interface order*, 0 differences across all 58 survivors; and the **internal networks are
byte-identical** on all four assets. The change is purely the interface, which no baseline diff
could have told us — a lost range or `disableWhen` moves no number.

⚠️ **The 6 remaining DEAD are the opposite of decoys, and they are evidence the method was right.**
`tracer/organic_amp` · `tracer/organic_scale` · `tracer/close_min_pts` · the three `mesh/s5b_*` are
all **referenced in VEX**; their branch is simply unreached by any committed case (no organic
generator, no `layer > 0`). **Perturbation evidence alone would have deleted all six.** That is why
the trim was cut on "is there a `ch()` that lands on this parm", not on "did it move a number".

⚠️ **AND THE RETIRED MONOLITH WAS STALE — deleting it was MORE right than recorded, not less.**
Node-by-node against the split assets, the segmenter has **four nodes `pf_citygen_trace` never had**
— `graph_realign`, `graph_stub_mark`, `graph_stub_fuse`, `graph_stub_kill`, i.e. the whole of §S5a —
plus five changed bodies (`graph_drop_tongue`, `graph_mark_orphans`, `graph_min_angle`,
`prune_mark`, and `repair_scratch`, whose `primdel` went `""` → `"kill_angle kill_stub realigned"`).
**The `trace` wrangle itself is byte-identical between the two**, which is exactly why the traced
streets and the weld verdicts are identical and the port is faithful. So the old asset had not been
a reference build since 2026-08-12 — it was a second, diverging graph stage kept alive beside the
real one. ⚠️ **Correction to the port's own claim:** "every bounded metric lands on the same number"
omits `retrograde_welds_bounded`, whose n moved **67 → 61**.

⚠️ **`pf_citygen_junction`'s 8 promoted parms are swept by nothing either** — same root cause as the
solver's 7: no `plan` entry, no `owner()` branch. Measured: all 8 are read by the junction's own VEX
and it holds **zero `../..` references**, so no read escapes it. Not a live defect; not covered.
Recorded in `parm_liveness.py` alongside the solver gap.

#### `closure_gate.py` ported onto `tracer → segmenter`

It builds the two-node chain, instruments the tracer's `trace` wrangle exactly as before — the
instance only, never the definition — and reads the **segmenter's** output, because that is what the
old node's output 0 was: the graph after stitch, fuse and repair.

Verified per config and per `src_id` against the old node before it was deleted: **not one traced
street is lost or gained**, the weld verdict per street is identical (radial sep22/step30 6 and 6,
sep130/step12 2 and 2, sep90/step6 2 and 2; grid 0 throughout), `ground_truth_welds` still passes,
and every bounded metric lands on the same number — max_seam 8.412, max doubled pavement 729.6 m²,
worst rasterised deficit 1325.7 m² at the same config, the same 21 self-intersecting loops with the
same worst three, the same seam distribution and gaps, the same 4 failing checks.

⚠️ **What the port did expose is a standing defect in the sweep, and it is worth more than the port
was.** The row count moves — 5910 → 5799 rows, 563 → 549 welds — **and it was never a street count.**
The graph stage splits every traced street at every crossing and each fragment inherits `src_id` and
the whole `x_*` gate-input set, so the sweep counts FRAGMENTS: at radial sep22/step30 the **42**
traced streets arrive as **408** rows in the old build and **407** in the port, and one street alone,
`trace_1_2_0`, is 24 fragments in one and 23 in the other. And the inherited values are
*interpolated* — `tracelen` reads 2369.9954 / 2369.9993 / 2370.0012 on three fragments of the street
the tracer itself reports as exactly 2370.0.

⚠️ **`gate_matches_vex` has therefore never been failing on what it says it is failing on.** Its own
docstring says *"nothing else in this file is worth reading if this fails"*, and it has been red at
4 rows (old) and 5 (port). Checked in the ported build, in all four configs it flags, against the
tracer's exact record for the same street: **the Python transcription agrees with the wrangle on
every traced street** and disagrees only on fragments, for two measured reasons —

- **one fragment per street carries blended attributes.** radial sep65 step2, `trace_1_2_2`:
  seam **250.80** against the street's 31.25, tracelen 376.2 against 590.0, and `cell` **63.20**
  where the traced value is a constant **65.0** — a number only a weighted blend can produce. It
  fails three gates at once.
- **and one is a float straddle.** radial sep150 step2, |turn| = **6.283187** against the loop gate's
  2π = **6.2831853**. It fails by 1.6e-6; the tracer's exact 6.283185 passes.

The cure is one line — read `tr.geometry()` on the **tracer**, one row per street with exact values,
which would also take this check green — but that changes what the sweep measures rather than where
it is wired, and this file's header says not to re-derive it. **Left for a decision, deliberately,
rather than done in passing.** `gate_matches_vex` now names the config as well as the `src_id`,
because a bare `src_id` is not unique across 58 configs and printed as four copies of one name.

⚠️ **Scene note for the artist:** the trimmed parameters were dead on those nodes, so no cook changes
— but a `.hip` that carries an explicit non-default value on one of them (or an expression pointing
at one) will lose it on load. Nothing in the test scene did; the live scene was not opened.

⚠️ **Verification status, stated plainly: the Rule 0 independent audit did NOT run.** Two audit
agents were spawned and neither returned or answered a message. Their four highest-value checks were
then run by the author, which is evidence but *is not independence*: every promoted name the suite
reads by name resolves to the node that reads it (`graph_*` and `s5j_*` → segmenter, `lots_*` →
mesh, `domain` → tracer, and all 7 of the solver's `s5j_params_*` still expression-linked to the
segmenter); `parm_liveness` sweeps all 62 with **zero** `generic()` fall-throughs, so nothing is
probed at a value nobody chose; the `--table` branch runs and its gate tallies are structurally
unchanged; and `polyfactory/otls/backup/` (gitignored) gained no file, so `create_backup=False`
held. **A fresh reader has still not looked at this.**

### The original V1 assets

Build examples from `tests/citygen/cases.py`.

| Asset | In → Out |
|---|---|
| `pf_citygen_field_grid` | — → a field **source descriptor** (one point: type, centre, weight, falloff, bearing). Chainable via its input |
| `pf_citygen_field_radial` | same, radial |
| `pf_citygen_junction` | graph splines → the S5 solution (junction patches + streets carrying `trim_start`/`trim_end`). A helper asset, used twice inside the tracer and testable on its own |
| ~~`pf_citygen_trace`~~ | *deleted 2026-08-12.* Was in0 field sources **or** in1 **any curves** → out0 **editable centreline splines** (§6 schema) · out1 the junction solution. S1·S2·S3·S4·S5. Replaced by `pf_citygen_tracer` → `_segmenter` → `_solver` |
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

### ✅ BUILT — the next boundary: SEGMENTER and SOLVER

⚠️ **This subsection said "🔵 PLANNED, NOT BUILT — nothing here ships" until 2026-08-12, by which
time the three HDAs had existed for a day and were wired into every case in the scene.** It was
written 2026-08-11 as a specification, from Hannes' requirements, with every stage assignment read
off the live `pf_citygen_trace` cook order. It shipped; the text below is kept as the rationale,
and the status is §6b's table at the top.

**Two things specified here were not delivered with the split. One is now done:**

- ✅ **The parameter interface is trimmed** (2026-08-12) — 63 inherited decoys removed across the
  three assets, each one measured to have no `ch()` referring to it anywhere inside. See §6b
  *"The retirement, finished"*.
- **The `out1` precondition below is unmet.** The wiring measured 2026-08-12 is still
  `C_solver:out1 → C_mesher:in1`, i.e. the mesher still consumes baked junction *geometry* on a
  second stream rather than deriving corners from graph attributes at cook time. Whether the
  byte-identical-output symptom below still reproduces was **not** re-measured.

#### Why it has to split again

The splines are not an intermediate, they are **the product**. Hannes: *"the splines do serve as the
construct how data flows and the mesher is only acting on the data it reads there."* Three consumers
need them, and only one exists yet: the cross-section template per curve; RailClone-style final
geometry instancing (what ships today is proxy); and traffic animation/simulation.

⚠️ **Measured 2026-08-11: the current `trace → mesh` split does not deliver that.** Doubling
`streetWidth` on half the streets between the two nodes changes the output **byte for byte
identically** — 4459 prims / 5568 points before and after. The mesher follows `out1`, the baked
junction *geometry*, and ignores what you wrote on `out0`. So *"editable centreline splines"* above
is true of the attributes and false of their effect. **`out1` must become attributes on the graph**
— junction data on the node point, per §S5's own quantities — and the mesher must derive corners at
cook time. That is a precondition for everything below.

#### The criterion, and why the cut is clean

**Topology versus geometry — and topology does not need widths.** Where two curves cross is
independent of how wide they are. That is the whole reason this split works rather than being an
arbitrary line through a chain.

- **SEGMENTER** — produces the final graph: which edges and which nodes exist. Contract: *nothing
  after me creates or destroys an edge or a node.*
- **artist authors** — on segments (prims) and junctions (points), both of which now exist and are
  addressable.
- **SOLVER** — produces geometry from that topology plus whatever was authored. Contract: *I never
  change topology.*

Dead-end resolution belongs to the **segmenter**, not the solver: merging a dead end into a
neighbour *creates a junction*, and a junction created after the authoring point is one the artist
never had the chance to tag.

#### ⚠️ The repair loop decides the cut, and it makes the solver thin

Everything from `graph_resample` to `graph_degree_final` runs **inside the fixed-point repair loop**
(`repair_begin … repair_verdict … repair_end`). The loop exists because topology changes feed back:
a dropped tongue changes degree, which changes the next junction measure. **So every stage that can
change topology must be inside the loop, and the loop must be inside the segmenter** — including
several stages that are geometry by nature and are there only because topology depends on them.

| stage (live cook order) | kind | goes to |
|---|---|---|
| `field_tensor` · `trace` | field → raw splines | **trace** (unchanged) |
| `input_switch` | source merge | becomes an ordinary **merge** |
| `graph_resample` | geometry prep | segmenter |
| `graph_extend` | **topology** — extend dangling ends to connect | segmenter |
| `graph_stitch` | **topology** — split curves at crossings | segmenter ← *the core* |
| `graph_fuse` · `graph_convertline` · `graph_polypath` | **topology** — weld, rebuild | segmenter |
| `graph_degree` | derived | segmenter |
| `prune_mark` · `graph_prune` | **topology** — drop short edges | segmenter |
| `graph_min_angle` · `graph_kill_angle` | **topology** — drop shallow-angle edges | segmenter |
| `graph_connectivity` · `graph_mark_orphans` · `graph_drop_orphans` | **topology** — drop orphans | segmenter |
| `graph_edge_attribs` | **identity** — `edge_id`, `region_id` | segmenter ← *authoring needs it* |
| `graph_classify` | **default** `street_class` | segmenter |
| `xsection_library` · `graph_width` | **default** `streetWidth` | segmenter |
| `graph_turn_resample` · `_fuse` · `graph_turn_clamp` | *geometry* — but it moves centrelines, and a moved street can cross something new | segmenter (inside the loop) |
| `junction_premeasure` | *geometry* — but the tongue test needs it | segmenter (inside the loop) |
| `s5j_tongue_mark` · `graph_drop_tongue` | **topology driven by geometry** | segmenter |
| `graph_degree_final` · `repair_verdict` | derived · fixed-point test | segmenter |
| `junction_solve` | corners, trims, cul-de-sac bulbs | **solver** |

**The solver is thin, and that is the correct answer rather than a disappointment.** It means the
authoring point sits exactly where topology is already final and proven stable — which is the
property the whole design rests on.

#### The residual circularity, and the rule that settles it

`graph_width` writes **default** widths *inside* the loop, and the tongue test consumes them. So an
artist who overrides a width *after* the segmenter has changed an input the topology decision was
already made on. Wider street → bigger corner → deeper trim → a short neighbour that should have
been dropped, but wasn't.

> **The solver CLAMPS and FLAGS. It never deletes.** This is §S3's *"a connection is never refused"*
> applied one stage later: a 40 m roundabout that will not fit shrinks to the largest that does,
> records what it used and why, and reports the shortfall. Shipping a short street is a visible
> defect the artist can act on; silently deleting one is not. The same rule covers the turn clamp
> moving a street into a new crossing.

Consequence for authoring, and it is a real constraint rather than a preference:

| attribute | where it must be authored | why |
|---|---|---|
| `streetWidth`, `street_class` | **before** the segmenter — on the source curves, which propagate (measured: arbitrary prim attributes survive stitch/fuse/polypath intact, 15 segments from 5 curves all correctly attributed) | they change corners, trims, and can delete edges |
| `street_template`, `land_use`, instancing tags, lane metadata | between segmenter and solver, per segment | no topological consequence — **but see the open decision** |
| `junction_template`, when size-neutral | between segmenter and solver, per point | the junction point exists by then |
| `junction_template`, when size-changing | same place, but the solver clamps it to fit | a roundabout's ICD is a trim, and a trim is structural |

#### ⚠️ The split shipped a defect: `copyToHDAFile` copies the PARAMETER INTERFACE too

Found by audit, 2026-08-11, on the version already saved into the artist's scene.

The three new assets were forked from `pf_citygen_trace` and then cut down internally — but the
fork carries the **whole promoted parameter interface**, and only the guts were trimmed. All 36
parms are promoted on all three nodes:

| asset | promoted | live on that node | **inert decoys** |
|---|---|---|---|
| Tracer | 36 | 11 | **25** |
| Segmenter | 38 | 18 | **20** |
| Solver | 36 | 6 | **30** |

**75 of 110 slider slots do nothing on the node they appear on.** Nothing was lost — every parm
lands live somewhere — but the panel is ~68% decoys.

⚠️ **The worst is `domain`, and it fails SILENTLY.** It is live only on the Tracer; on the
Segmenter its only occurrence is inside a code comment and on the Solver it does not appear at all.
It is also the decoy an artist is most likely to reach for, because this document and `cases.py`
both point at the Segmenter for graph controls. Measured: setting Domain on the Segmenter ships a
**25% larger city** — 26 706 prims / 1 165 lots against 21 363 / 774 — rather than erroring.

⚠️ **And bit-identity could never have caught it.** The split was verified by hashing all four
outputs against the old chain on all nine cases, which is structurally incapable of detecting a
*lost parameter link*: an unwired slider produces identical output for as long as nobody moves it.
A different measurement was needed and only an audit ran it.

**Fixed:** `domain` removed from the Segmenter and Solver; the two orphans the reverted arm-cap work
left behind (`graph_params_realign_dist`, `graph_params_merge_scale`, read by nothing) removed; the
Tracer and Segmenter corrected from 2 declared outputs to 1 — `tracer.geometry(1)` had been leaking
**19 321 prims** of internal field-sampling geometry through an unlabelled port. Suite unchanged at
21 failing, zero baseline movement, and the artist's scene reproduces its recorded prim counts
exactly.

✅ **The other decoys — 63 of them — were removed 2026-08-12.** This paragraph used to say the
pruning was blocked: the quick sweep run at the time disagreed with the audit's (6/6/3 against
11/18/6) because the two used different perturbation magnitudes, several of these parms only move at
extreme values, and **pruning on the weaker measurement would delete live parameters**, which is
worse than a cluttered panel. That was right, and the way past it was not a better sweep but a
different kind of evidence — *is there a `ch()` anywhere inside this asset that lands on this parm* —
which does not depend on a magnitude at all. §6b *"The retirement, finished"* has the method, the
two ways the first scan of it was wrong, and the per-asset counts.

#### ⚠️ The harness could not reach the Tracer at all

`_chain` returns the Segmenter as the `"trace"` role, so `cases.parm()` searched
`city`/`trace`/`solver` and never saw the Tracer. Every S1/S2 parameter — the entire tracing stage —
was perturbed on a node where it is dead and reported as a regression, while the node it actually
drives was swept by nothing: **12 false regressions and zero coverage of the stage that generates
the streets.** `cases.py` now exposes a `tracer` role and `parm_liveness` sweeps it, with the S1/S2
entries retargeted and the Tracer restricted to the parms it owns. Back to
**62 swept · 49 GEOM · 7 ATTR · 6 DEAD, exit 0.**

#### Naming — settled 2026-08-11

Hannes: *"just name them what they do not which elements they are for."* The `CityGen` prefix stays;
everything after it is the **job**, not the subject matter.

| type name (unchanged) | label | status |
|---|---|---|
| `pf_citygen_field_grid` | **CityGen Field: Grid** | already correct |
| `pf_citygen_field_radial` | **CityGen Field: Radial** | already correct |
| ~~`pf_citygen_trace`~~ | — | ✅ **DELETED 2026-08-12** — `pf_citygen_tracer` replaces it |
| ~~`pf_citygen_streets`~~ | — | ✅ **DELETED 2026-08-12** — the four-asset chain replaces it |
| `pf_citygen_tracer` | **CityGen Tracer** | ✅ built |
| `pf_citygen_segmenter` | **CityGen Segmenter** | ✅ built |
| `pf_citygen_solver` | **CityGen Solver** | ✅ built |
| `pf_citygen_junction` | **CityGen Junction (internal helper)** | ✅ used by the Segmenter and the Solver |
| `pf_citygen_mesh` | **CityGen Mesher** | ✅ renamed |

⚠️ **Corrected 2026-08-12, by audit.** This table said `pf_citygen_junction` was labelled *CityGen
Solver* — it is not; that label belongs to `pf_citygen_solver`, and the junction asset's own label on
disk is *CityGen Junction*. It also listed `pf_citygen_streets` as "✅ renamed", contradicting §6b's
deletion of it 340 lines earlier, and had no row at all for `pf_citygen_tracer` or
`pf_citygen_solver`. A naming table that disagrees with the labels on disk is worse than none.

⚠️ **Labels only. Type names are NOT renamed, and that is deliberate.** A type name is what a `.hip`
stores; changing `pf_citygen_trace` turns every existing instance into a missing definition. This
project lost a working session to exactly that failure, and the recovery required restoring a
deleted asset byte-identically from git. Labels are free, type names are a migration.

⚠️ **`pf_citygen_trace` kept its long label until the segmenter was cut**, because "Tracer" would
have been a lie while it owned S1–S5. The point is now moot in the cleanest way: the name went to a
**new type**, `pf_citygen_tracer`, which really does only trace, and the old type was retired rather
than renamed — so no existing instance ever lost its definition.

#### The Labs Building Generator precedent — checked, and it half-holds

Hannes offered it as guidance: *"you describe building features, connect them all into a data
stream, and have one solver node at the end."* Read rather than recalled
(<https://www.sidefx.com/docs/houdini/nodes/sop/labs--building_generator-4.0.html>):

- ✅ **One solver at the end of a chain — confirmed.** It takes low-resolution blockout meshes,
  slices them into floors, identifies walls/corners/ledges and substitutes high-resolution modules.
  That is precisely the role of the **Mesher** here.
- ✅ **A companion authoring node exists** — *Labs Building Generator Utility* prepares and
  configures the modules upstream. Direct precedent for the planned template-authoring node.
- ❌ **But modules are selected by NAME through parameters** — Facade Module Pattern, Corner Module,
  Top/Bottom Ledge Module — **not** by descriptors merged into a data stream.

⚠️ **So the precedent validates the SHAPE and not the PLUMBING**, and the difference is the thing
this section is about: name-referenced module parameters are exactly what the Mesher does today with
its six hard-coded `road_br_*` blasts, and it is what makes an artist unable to add a seventh
template. Feeding templates on the stream is a step **beyond** the precedent, not a copy of it — and
it is already the project's own pattern for field sources (§6b: *"descriptors rather than baked
grids, so any number merge and blend for free"*).

#### Open decisions, to settle before building

1. ✅ **SETTLED 2026-08-11 — the template defines the width.** Hannes: *"you do after all design the
   template so the street looks a certain way… whatever the artist designed is what the solver needs
   to account for."* So `street_template` is **structural**: assigning a different template to a
   segment changes its width, therefore its corners, therefore its trims. It must be authored
   **before the segmenter**, alongside `street_class` and `streetWidth`, and the per-segment
   template edit has to round-trip back to the source curve rather than being applied after.
   *Variable templates* — exposing segments within a template that may stretch — are a future
   feature and would make part of the width elastic without changing this rule.

   ⚠️ **And the template library is not where an artist can reach it.** Measured: `xsection_library`,
   a Python SOP **inside** `pf_citygen_trace`, emits exactly the shape Hannes expected — **6 points,
   one per template**, carrying `template_name`, `streetWidth`, `laneWidth`,
   `sidewalkWidthLeft/Right`. But it has **no promoted parameter and no input**, the node has only
   its field and drawn ports, and `pf_citygen_mesh` builds a **second copy** of the same library
   (`xsection_all`) from the same Python constant. Worse, the mesher then branches on template
   **by name, with six hard-coded blasts** — `road_br_alley`, `road_br_arterial_median`,
   `road_br_boulevard_bus_bike`, `road_br_collector`, `road_br_highway`,
   `road_br_local_residential`. **Adding a seventh template means editing the HDA.** The artist
   cannot add one at all, which contradicts §1's *"an artist-authored template geometry replaces
   [the starter presets] entirely"*.

   **A TEMPLATE MAY NOT LIVE INSIDE A NODE. It arrives on the data stream.** Hannes, 2026-08-11:
   *"the template needs to be plugged in with the datastream it cannot live inside a node."*

   ⚠️ **This is a FOUNDATION requirement, not a later feature, and the distinction matters.** The
   node that *authors* templates comes after the foundation is right — but the **input that carries
   them must exist from the start**, on the segmenter (it reads template widths to write defaults)
   and on the mesher (it builds the cross-section profile). Build the foundation without that port
   and the interfaces get re-cut later, which is precisely the rework this split exists to avoid.
   Until an authoring node exists, the current starter library feeds that port — same data, moved
   from inside the node to outside it.

   **The project already has this pattern and templates were the exception.** §6b: *"Field sources
   are descriptors rather than baked grids, so any number merge and blend for free."* A field source
   is one point emitted by an HDA, merged into the stream, read downstream. Templates are the same
   kind of thing and should work the same way — which is a consistency argument, not just a
   preference.

   Consumption must be **generic**: a loop over whatever templates arrive, never a branch per name.

   Two shapes to decide when it is built:

   - **What carries the cross-section.** The library points today hold only a **4-number digest**
     (`streetWidth` / `laneWidth` / `sidewalkWidthLeft` / `sidewalkWidthRight`); the real profile —
     per-element width, height, drivable, walkable, colour — is re-expanded from `STARTER_TEMPLATES`
     *inside* each node and never travels. RailClone-style instancing needs the **full element list
     in the stream**. Either array attributes on one point per template, or **one polyline per
     template whose points are the cross-section stations** — the second is profile geometry the
     sweep consumes natively and is the more Houdini-shaped answer; the first matches "one point per
     template" literally.
   - **Dedicated input port, or merged into the spline stream?** Merging matches the field-source
     precedent but needs a marker attribute (`field_src` is the existing one) so no stage mistakes a
     template for street geometry. A separate port cannot be contaminated but breaks the "everything
     merges" symmetry. **Decide before the segmenter is cut**, because it fixes the port count.
2. **`node_id` does not exist.** Prims carry a stable `edge_id` (verified: 15 distinct, all 15
   unchanged across an unrelated parameter change). Points carry only `P`, `is_node`, `node_class`,
   `node_degree` — **no identity**. Live editing downstream of the segmenter needs none; a *stored*
   selection in the edit node does. Add it in the segmenter beside `edge_id`.
3. **Neither id is known to survive a GEOMETRY change.** Both were only tested against a parameter
   change. If ids renumber when a drawn curve moves, every stored override points at the wrong
   element. **Measure before designing the edit node** — it decides whether overrides key on ids or
   on something spatial.
4. **The turn clamp must not move node points.** It smooths centrelines inside the segmenter; if it
   moves a junction, positions desync from the topology the solver is handed. Assert it, do not
   assume it.
5. **Provenance is not stamped.** `src_curve` propagates perfectly when an artist adds it by hand
   (verified semantically: all 15 segments land on the correct axis for their source curve), but
   nothing writes it automatically. `source_node` is *tool* provenance
   (`/obj/…/graph_classify`), not authoring provenance. The segmenter should stamp source identity.

#### What must be asserted once it is built

- Topology is **byte-identical** across the solver — same edge count, same `edge_id` set, same node
  degrees in and out. This is the contract; without a test it is a comment.
- An authored `streetWidth` **changes the mesh**. The measurement that exposed the current failure
  becomes the regression test.
- A clamped junction **reports** its clamp, and nothing is deleted.

**The junction solver is its own asset because it was already being used twice.** §S5's
`min_standing_widths` requires the solve to run once as a pre-measure (to learn each arm's trim)
and once for real, and the pre-measure nodes were *copies* of the shipped ones. They are now the
same HDA instanced twice, with `do_culdesac` off on the pre-measure — the copy cannot drift from
what ships, because there is no copy.

⚠️ **`pf_citygen_streets` is DEPRECATED, not gone — corrected 2026-08-11.** It was renamed and
gutted and the mesh node is the direct descendant, so any scene wiring
`pf_citygen_trace → pf_citygen_streets` should be rebuilt, and note that the tracer's **out0
changed meaning** — it was raw centrelines, it is now the solved graph.

But *deleting the .hda file* was the wrong way to retire it. Houdini had baked a copy of the
definition into the artist's `cityGen.hip`, so the scene still opened — on an **Embedded,
`incomplete`** definition that Houdini itself warns "will not function properly". It opened by
luck, and a clean load on any other machine would not have. The file is therefore **restored at
its last shipped revision (`ac64636^`) and frozen**: it is never edited, never fixed, and nothing
new may wire to it. It exists so old scenes load *and cook*. `tests/citygen/cases.py` pins its
five assets by name, so the deprecated file is invisible to the suite.

**Retiring a shipped asset means leaving the file on disk, not removing it.** A missing definition
is not a migration path; it is a scene that cannot be opened.

### ⚠️ Never change a shared VEX signature under existing callers — 2026-08-11

The same delete-and-move-on reflex hit `polyfactory/vex/include/`. Adding `angle_deg` to
`pfsf_gen_radial` changed its signature, and the artist's **hand-built** `/obj/pf_citygen` — not
an HDA, so not greppable and not migratable by any script — went red across 46 nodes.

Both include files now carry **backwards-compatible overloads** in a `DEPRECATED` block:
`pfsf_gen_radial` (4-arg, forwards `angle = 0`) in `pf_streetfield.vfl`, and `pfsj_fillet`
(pre-`max_run`), `pfsj_bevel` and `pfsj_arc_centre_through` in `pf_streetjunction.vfl`. VEX
overloads on arity *and type*, both resolve exactly, and it costs nothing.

⚠️ **The loud break was not the dangerous one.** `pfsj_fillet` gained `max_run` and lost `centre`,
so old and new both take **ten** arguments — the old call site did **not** go red. It bound a
`vector` into a `float` through an implicit cast and shipped quietly wrong junctions. A red node
is a bug report; that was not. When a signature must change, **change the arity or change the
name** — never silently re-order same-count parameters.

Measured on the whole branch: `pfsg_turn_clamp_solve`, `pfsg_turn_sweep`, `pfsj_inward_offset` and
`pfsl_clip` also changed or vanished, but **every** live call site already uses the new form, so
they need no shim. Verify that claim by call-site inspection before deleting a shim, not by
assuming.

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

- **THE NODE/SEGMENT MODEL — built, measured, and NOT yet shipped. 2026-08-15.** The
  Cities-Skylines model: you grab a node, you do not grab every vertex, and the road re-curves.

  ⚠️ **THE STRUCTURE ALREADY EXISTS AND NOBODY HAD USED IT.** `graph_polypath` already leaves
  every prim running node-to-node. Measured on A_drawn: all 8 prims have `is_node` = 1 at *both*
  ends and **zero** interior nodes, with 23–47 shape points between. So a prim already IS a
  segment; `is_node` (§6, "1 = topological node, 0 = shape point") already labels which points are
  structural. What was missing is only the DERIVATION — moving a node did nothing to the shape,
  so the street hinged at the junction, which is cause (2) of attempt five below.

  **The mechanism, validated:** capture each shape point in its segment's own chord frame —
  `u` along, `v` across, both divided by chord length — then rebuild from the end nodes. The
  reconstruction is a similarity (rotate, uniform scale, translate), so the segment keeps its
  shape and follows its nodes. Two traps found by measuring, both non-obvious:

  1. ⚠️ **A LOSSY IDENTITY INSIDE AN ITERATING LOOP IS A RANDOM WALK.** Running the rebuild
     unconditionally moved **68 recorded values** on cases where no node moved at all — city prim
     counts, lot counts, `selfx_city_merged` in both directions. `u`/`v` are float32, so the round
     trip drifts ~1e-6 relative — ~1 mm at 800 m coordinates — and the repair loop runs up to ten
     passes. `graph_reaches_a_fixed_point` tolerates 1 mm and never saw it. **The rebuild must
     store the endpoints with the frame and skip when they have not moved** — not "recompute to
     the same value", *skip*. With that gate all ten other cases went bit-identical.
  2. ⚠️ **IT MUST NOT WRAP A MOVER THAT DOES ITS OWN SHAPE WORK.** Wrapped around
     `graph_realign` it regressed `block_boundary_closes` (1 closed loop → 2 open, 4 unpaired
     ends) and `trim_metric_is_consistent` (0.0 → **2.66 m** at (44.0, 0.0)) on `J_five_star`, the
     one case the realign fires on. The realign lands its T deliberately and blends the approach;
     the rebuild then overwrote that interior with a similarity of the *pre-realign* shape and
     threw the blend away. **Its consumer is a mover that repositions nodes and nothing else** —
     the cluster spread — not the realign.

  Where it fires it does exactly what it is for: on `J_five_star`,
  `centreline_curvature_within_class` went 0.427 → **0.0** and `no_sweep_fold_after_trim`
  0.107 → **0.0**. The hinge is real and this removes it.

  **Status: reverted, unshipped, and the two wrangles are worth rebuilding verbatim** when the
  cluster spread exists to consume them. Suite unchanged at 20. Consumer architecture and
  integration requirements: **§11** (11.6–11.8).

- **How the deferred cross-section transition gets built — WANG TILES, not a solver.** Decided
  2026-08-15 while looking at the failure in the viewport. The v1 non-goal in §10 says the seam is
  left open; this records the *approach*, so the eventual build does not start from scratch.

  A street is currently swept as ONE ribbon from junction to junction, so its raised elements —
  a median, a kerb, a sidewalk band — arrive at the junction still at their own height and run
  straight over the junction plate, which is flat carriageway (`elem_type` = `lane`, y = 0).
  Measured on A_drawn: at every one of the six crossing sites the incident prims are a road band
  at y = 0.15 with its riser, and the 34 x 39 m junction plate at y = 0. That is the whole of
  `selfx_city_merged` — 9 points on A, 101 on B, 127 on C. **It is a missing feature, not a bug,
  and no threshold or trim fixes it.**

  The cure is to stop treating a street as one ribbon and **split it into segments, then choose
  each segment's geometry from what it connects TO** — middle pieces, end pieces, and whatever
  else the catalogue turns out to need. Wang tiles in the simple sense: the tile is picked by its
  neighbours, so an end piece that meets a junction is the piece that ramps the median down and
  brings the section to the junction's elevation. It is a lookup, not a solve.

  Two consequences worth writing down now. The segmentation is what makes it possible at all, so
  it comes first and it is not optional. And the catalogue is per TEMPLATE, so every cross-section
  an artist authors needs its end piece or it has no legal way to meet a junction — which is an
  argument for deriving the end piece from the template automatically wherever it can be, and
  authoring it only where it cannot.

### ⛔ OPEN AND BLOCKING — the multi-leg junction (§S5a). Added 2026-08-12

This entry said *"nothing currently blocking"* while the defect below was visible in the viewport,
which is the other half of why it was reported fixed twice.

⚠️ **STATUS 2026-08-12 — IT SHIPS, AND THE SUITE NOW RUNS IT.** `graph_stub_mark` →
`graph_stub_kill` → `graph_stub_fuse` → `graph_realign` are in `pf_citygen_segmenter`, gated on
repairability: the collapse fires only where a legal T fits, and declines otherwise. On the
artist's scene that is measured and rendered good — the five-way is a **degree-4 node at
(138.27, 262.31)**, angles 57.24 · 122.81 · 59.67 · 120.28°, plus a real **degree-3 T at
(174.70, 331.27)** where the 151.79 m arterial split into 78.0 + 73.8 m, **zero streets deleted**.
An independent audit measured that build and returned **ship**, with one latent defect: the
feasibility gate was structurally blind on a 3-cycle.

**Updated after the eighth pass (§S5a, 2026-08-12).** The gate now flood-fills the stub-connected
cluster and counts the whole cluster's external arms — 5 where it read 4 / 3 / 3 — and the shipped
junction is bit-unchanged. The coverage gap is closed: **`J_five_star` and `K_stub_triangle` are
committed**, the first cases in the suite that execute the realign and the gate's refusal at all.
`connections_are_never_refused` now watches **all five** deleting nodes in the repair loop, with the
stub collapse accounted separately as a by-design deletion, and is proven able to fail per node.
Suite **37 failing**: the 25 pre-existing plus J's 2 and K's 10, and K's ten are the honest form of
an unrepaired jog. On the other nine cases every deletion still happens in pass 0 and no other value
moved.

⚠️ **What that turned up, and both are open.** (1) On the artist's own live scene the widened
tripwire is **RED**: `graph_drop_tongue` deletes a 42.00 m arterial at (−240.37, 232.73) →
(−210.19, 203.54) in pass 1. Pre-existing, reproducible with the realign bypassed, unrelated to
S5a, invisible to all eleven cases — and **whether a late tongue drop is a by-design deletion or a
refused connection is the artist's call, not the implementer's** (§S5a "the eighth pass" item 6).
(2) On a four-junction stub CHAIN whose arms all clear the floor, the collapse is permitted and
`graph_drop_orphans` then removes two components after pass 0, publishing 3 edges of 9 — identical
on both definitions, so pre-existing, and newly visible (item 5, which specifies the case to add).

⚠️ **THE RULE CHANGED ON 2026-08-15, AND IT CHANGED BECAUSE THE DATA SAID THE OLD ONE WAS
MEASURING THE WRONG QUANTITY.** It used to read: *cap junction arms at 4; realign a leg where
feasible, roundabout otherwise*, with `min_node_dist` 40 m enforced as a floor. Both halves were
asserted as thresholds. Neither predicts a defect:

| case | gap | arms | geometry checks broken at that junction |
|---|---|---|---|
| C_radial | 30.65 m | 5 | **0 of 8** |
| I_offset_radial | 30.65 m | 5 | **0 of 8** |
| K_stub_triangle | 32.00 m | 5 | **5 of 8** |

30.65 m with five arms is clean — `trim_leaves_road_standing` leaves +6.49 m, no mouth lost, no
self-intersection, all 29 block loops closed. 32.00 m with five arms is a disaster: −13.43 m
standing, 6 mouths orphaned, 50 self-intersections. **Distance does not separate them and arm
count does not separate them.** What separates them is whether the junction PLATES fit: K's are
42 m across on a 32 m gap.

The rule as it now stands, from the artist:

- **`min_node_dist` (40 m) is a SEARCH RADIUS, not a minimum size.** It says how far to look for
  neighbours that might interact. A junction that solves correctly at a smaller spacing is
  correct. What must be zero is errors, not metres.
- **The cap of 4 is the AIM, not a cap.** Published practice is that an engineer designs for at
  most four arms, and that stays the default to aim for — but five-way junctions exist in the
  world, and one that solves correctly is correct.
- **Only where it does NOT solve is a resolution required, and the resolution is unchanged:**
  realign a leg into a separate T, leaving a T and a four-way (`graph_realign`, already built).
  Eliminating a leg stays forbidden by §S3.

Consequences already applied: `junctions_not_too_close` and `no_multileg_junctions` are now
**measured and recorded, not asserted** — the assertion moved to the checks that measure the
outcome (`trim_leaves_road_standing`, `every_mouth_has_a_road`, `selfx_junction_surface`,
`block_boundary_closes`, `lots_clear_of_junctions`). Suite 26 → 20 failing with **no geometry
change at all**, because four of those six rows were never defects. K still fails all five
outcome checks, which is the point.

Still to apply in CODE: `graph_stub_mark` treats *any* edge under 40 m as a jog to collapse
regardless of whether it has a problem, which is the old semantics. It should act on the
premeasured standing length instead. And the derived thresholds that quote the vertex grid —
`min_node_dist + one resample step` = 45 m, `2 x` that = 90 m — stop being about distance at all.
→ **Superseded by the §11 spec**: the distance trigger and `graph_min_angle`'s deletion both
become planner decisions (11.5, M5), and item 4's re-route ships as one mechanism with the
shallow-angle merge (11.6).

**Four attempts to enforce the OLD rule were built, measured and reverted (§S5a). Attempt five
was mine, 2026-08-15, and it failed for two causes worth recording** because both are traps for
the next attempt:

1. **A per-edge push applied to a per-cluster problem.** It separated each deficient edge by half
   its shortfall, capped per edge by half the endpoint's shortest other street — the realign's own
   rail. On a 3-cycle *every* side is deficient, so each corner is shoved two or three times per
   pass in different directions. Nothing capped the total per NODE.
2. **It moved only the two endpoints, and the interior is resampled at ~5 m.** Shifting an
   endpoint 16 m while vertex #2 stays put hinges the street at the junction. This is the deeper
   one, and it is why the node/segment model in §9 has to come first: a street whose shape is
   DERIVED from its end nodes re-curves when a node moves, and this failure mode cannot occur.

Measured outcome of attempt five: K's graph emptied over the loop's ten passes — `counts` city
1979 → 0, edges 8 → 0 — and suite 26 → 31. ⚠️ **Three checks went GREEN while it did that**
(`junctions_not_too_close` 3 → 0, `no_multileg_junctions` 5 → 0 arms, `selfx_junction_surface`
50 → 0), all of them because there was no geometry left to fail them. Reverted. The order
that follows from those failures:

1. ✅ **Commit the checks first** — DONE 2026-08-12. `junctions_not_too_close` and
   `no_multileg_junctions` are committed and in the baseline, red on C_radial and I_offset_radial.
   ✅ **(c) the hand-drawn 5-star is DONE too**, 2026-08-12, after being recorded as missing three
   times: `J_five_star` (the realign repairs it) and `K_stub_triangle` (the gate refuses it) are
   committed and in the baseline. See §S5a "the eighth pass".
2. ✅ **Which threshold governs** — `graph_params_min_node_dist` (40.0). The checks read it and the
   collapse read it. `min_node_dist` (50.0) is the Tracer's, duplicated onto the Segmenter by the
   `copyToHDAFile` interface copy (§6b) and unread there.

   ⚠️ **Steps 3 and 4 below are now BUILT and shipped — read the status note above, not the
   "reverted"/"only remaining piece" wording they still carry from before.** The coverage gap that
   replaced them is now closed as well (item 1(c)). What is left open is item 4's *quality*: the T
   forms, but its approach angle is whatever the crowded pair's was.
3. ✅ **Collapse the stub triangle** — built and measured 2026-08-12 (§S5a "the fifth approach"):
   correct, bit-clean on seven of nine cases, and it *raises* the arm count as designed. It ships,
   gated on repairability, and since the eighth pass the gate counts the whole stub-connected
   cluster instead of the two ends of one edge — on a 3-cycle that is 5 arms where it read 4 / 3 / 3.
4. ⚠️ **Realign the minor-most leg** into a separate T — **built and shipping**; minor-most is
   decided (**class, then width, then length**) and the landing is a host vertex at
   `min_node_dist + one resample step`. What is still unbuilt is **re-routing the last stretch** to
   meet the host at 75–90° inside S3b's `R > halfwidth`. Today the T's approach is whatever the
   crowded pair's angle was, softened by the blend: 48.25° on the artist's scene, 56.70° on
   `J_five_star`. Both clear `min_junction_angle` by construction; neither is a right-angled T, and
   re-routing is what would let the landing floor come down and make the dense C_radial sites
   reachable.
5. **Roundabout is NOT the fallback it was assumed to be.** At 32.5° two mouths need 37.4 m of
   separation; an ICD inside §S5's 21–67 m band gives a radius of 10.5–33.5 m and cannot deliver
   it either. It remains right for *wide-angle* five-ways; it does not rescue a crowded pair.
6. **Never eliminate a leg** — §S3's *"a connection is never refused"*. ⚠️ Note that
   `graph_min_angle` already does exactly this below `min_junction_angle` (25°), and raising that
   threshold to ~35° would resolve all three sites today. That is a real option and it is the
   artist's call, not the implementer's.

Run the cascade **once, outside the repair loop**, and clear per-pass state at the top of the pass
(`needs_roundabout` accumulated stale flags last time). Of the three sub-questions recorded here as
undecided, two are settled — "minor-most" is class, then width, then length, and the 32.5° pair is
two streets, so the fix is graph-level (§S5a, "the layer question is now settled"). **What remains
genuinely undecided is how to re-route the leg's last stretch.**

⚠️ **No part of this may be reported "done" on a green suite.** The suite has been green through
both pipelines while the defect shipped. It needs an independent audit on the current build; until
then the honest words are *"implemented, unverified"*.

Other open items are tracked system-wide in [`citygen.md`](citygen.md) §7.

---

## 10. Explicit non-goals for v1

**Moved IN to v1 by clarification round 1:** bridges, tunnels, overpasses and ramps (§S5b).

Still out, recorded so they don't quietly creep in: traffic and pedestrian simulation (the graph is
being designed to make it possible later, that is all — and
[`citygen_simulation.md`](citygen_simulation.md) §10.1 now states exactly what "possible later"
requires of this schema: lane counts and direction, cross-section role surviving onto the graph,
lane-to-lane connectivity at nodes, and two density floats) · rail, metro and sky-lane networks
(`network_type` reserved, not implemented) · multi-level stacked city layouts (`layer` reserved and
proven on bridges, but Coruscant-scale stacking is not a v1 target) · underground utilities ·
procedural signage and road markings beyond material assignment · per-segment cross-section
transitions (seam left open, §S6; the approach when it IS built is the Wang-tile segmentation in
§9, and `selfx_city_merged` is the standing measure of how open the seam is) · Voronoi graph
generator (deferred, §S1) · `skeleton` lot
subdivision (deferred to v2, needs Vanegas 2012 — §S8; `recursive_obb` and `offset` are both v1).

---

## 11. Implementation spec — the planner/builder split and junction types. 2026-08-15

**For the implementing agent.** Read, in order: this section · §S5a's ⛔ entry (including the
2026-08-15 rule change and attempt five) · the two §9 entries dated 2026-08-15 (node/segment
model, Wang tiles) · `tests/README.md`. Call `houdini_get_skill("houdini-dev-loop")` before
touching anything. Rule 0 applies to every milestone below: no "done" without an independent
audit on the current build, and the honest words before that are *implemented, unverified*.

### 11.0 Why this exists — the measured evidence

Every mechanism in the repair loop decides locally and discovers next pass what the others did.
The proof is the spread's min-angle interaction: **three guard variants** (chord prediction at
cluster nodes · tangent-via-dihedral · far-endpoint extension) each measured *zero violations at
the spread's own stage* — instrumented: `dbg_minang_deg` 25.0, scale untouched at 1.12 — while
`graph_min_angle` still deleted a street a pass later, because `graph_resample → graph_stitch →
graph_fuse → graph_polypath` reshape the graph between the decision and its consequence. That is
not a guard bug. **Decisions are being made against a representation the pipeline keeps
invalidating.** The cure is architectural: decide on the abstract graph, build geometry once.

CityEngine's node model (doc.arcgis.com, node parameters — read by the artist and me,
2026-08-15) confirms the shape of the fix: node **Type** ∈ Crossing / Junction / Roundabout /
Freeway; a **principal street** that Junction and Freeway leave unbroken; an angle threshold
that makes streets **bend to avoid each other** rather than ever deleting one; freeways that
*ignore* the angle threshold because a shallow merge is intended geometry there. We have built
exactly one of the four types (Crossing), applied it to every node in the city, and K's
−13.43 m standing is the direct cost: a 32 m street trimmed from *both* ends by two Crossing
plates that a Junction type would never have broken.

### 11.1 The constitution — every mechanism is designed against this page

Three times on 2026-08-15 a blocker turned out to be one of the artist's rules, discovered at
gate time. Design against this list, not into it:

1. **A connection is never refused.** No mechanism may delete a street — not as a repair, not as
   a cleanup, not late in the loop. The two existing by-design deletions (leaf tongues, the stub
   collapse) stay bounded and accounted in `connections_are_never_refused`; no new ones.
2. **Errors, not thresholds.** `min_node_dist` is a SEARCH RADIUS. The arm cap of 4 is the AIM.
   A configuration that solves with zero broken outcome checks is correct at any spacing, any
   arm count, any angle. Measured: 30.65 m five-arm solves clean; 32.00 m five-arm is a disaster;
   no threshold separates them — whether the plates fit does.
3. **The resolution ladder when it does NOT solve:** pick a richer node type (junction · merge ·
   T-split realign · roundabout as art option) → move nodes (cluster spread, fallback) → never
   delete.
4. **Authored beats computed.** `junction_type` and the `principal_start` / `principal_end`
   booleans (per-edge since the 2026-08-16 ruling, §11.3) are artist attributes with
   computed defaults, fill-if-empty — the `graph_classify` pattern.
5. **Nodes are the only authority on position; shape is derived.** No mechanism moves an
   endpoint without its segment (§9, the hinge). No rebuild touches a segment whose ends did not
   move (§9, the random walk).
6. **Decide on the plan, build once.** No decision may depend on measuring geometry that the
   pipeline will reshape before the decision's consequence lands (11.0).

### 11.2 Architecture

- **Planner** — pure Python, `hou`-free, at
  `polyfactory/scripts/python/polyfactory/citygen/plan.py`, unit-tested in
  `tests/unit/test_plan.py` at test_citygen speed. Operates on plain data (nodes: id, xz, arm
  edge-ids · edges: id, endpoints, width, class, length). Owns: node type selection, principal
  selection, footprints, standing/feasibility, cluster resolution *decisions*.
  ⚠️ This is NOT a resurrection of the deleted `citygen/graph.py` — that module solved
  weld/prune, which the segmenter now owns in VEX, and it died with a green test suite because
  nothing consumed it. `plan.py` lands **with** its adapter and consumer in the same milestone
  or not at all.
- **Adapter** — a thin Python SOP in the segmenter: geometry → plain data → `plan.py` →
  attributes written back. Small graph, cooks once per topology change; the `xsection_library`
  Python SOP is the precedent.
- **Builder** — VEX, as today. Realizes geometry from the plan. The repair loop shrinks toward
  a fallback executor of planner decisions.

### 11.3 Schema additions

On `is_node == 1` points (fill-if-empty, artist wins):

| attr | class | type | values |
|---|---|---|---|
| `junction_type` | point | string | `""` (decide for me) · `crossing` · `junction` · `merge` · `roundabout` (reserved, unimplemented) |
| `principal_start` / `principal_end` | **prim, on the edge** | int | 1 = this street is the principal at its start / end node. Planner-computed, fill-if-empty |

⚠️ **THE PRINCIPAL MOVED FROM A NODE STRING TO PER-EDGE BOOLEANS — artist ruling, 2026-08-16.**
The first shipped shape was `principal_edges`, a node-side string of two space-separated
`edge_id`s. Three audit rounds found four defects that are all properties of that SHAPE, not of
any implementation: a pair naming a stranger, the same edge twice, only one edge, and an
int-typed value that crashed the whole gate through `.split()`. The booleans erase the class —
an edge cannot name a stranger about itself — and replace it with one small check, cardinality:
**at each node, the arms claiming principal must number exactly 0 or 2.** This is CityEngine's
own shape (its docs: *"The principal street is specified … by setting the object attribute
`principleStreetStart` or `principleStreetEnd` on adjacent streets"*), and it mirrors
`trim_start` / `trim_end`, which already proved the per-edge-end pattern here. It is also what
makes an authoring surface POSSIBLE: a prim attribute exists on a drawn curve before the
segmenter runs — the prim-attribute half of the `graph_classify` precedent, the half that DOES
transfer — where a node-side string could not be authored at all because nodes do not exist
until the segmenter creates them (M3's measured gap).

**THE RULE IS DECIDED (artist, 2026-08-16): widest pair, ratified.** CityEngine's automatic is
the same (*"the two segments with the maximal street widths are automatically treated as a
major street"*), and the artist's definition of continuity is IDENTITY, not bearing — the
biggest street through the node stays the same street even where it turns, so a principal pair
sitting 70° apart is legal geometry, and 11.5's plate must survive a bent principal. The
straightest-pair alternative recorded in 11.4 stays as measurement history: it is what showed
the RULE decides K's outcome, which is why the decision was put to the artist before M4 built
anything. Consequence, kept visible: **widest pair does not dissolve K** — two of three sides
still overlap — so the ladder's next rungs stay live and M6 stays open.

**THE TIE-BREAK IS DECIDED (artist, 2026-08-16): first in the list — and ⚠️ "the list" is the
DETERMINISTIC one.** Width and length compare quantised to 1 mm (measured: a 1.3e-12 m length
difference once decided K's third corner), then the tie falls to **lexicographic `edge_id`
order** — first-come-first-served on the stable list, the tongue-rank precedent, and exactly
what `default_principal` already ships. It must NEVER mean arm order: `pointprims()` order is
cook-dependent, and three audit rounds measured that reordering K's node-C arms flips a
standing side from +12.9 m to −6.65 m with no geometry change. First by `edge_id`, never by
cook order.

Pin the vocabulary in `checks.py` as `JUNCTION_TYPE_VOCAB` — the `LOT_REJECT_VOCAB` precedent:
an auditor once relabelled every rejection and stayed green.

**M4's authoring surface, designed here so it stops being a gap:** the artist marks the DRAWN
CURVE (a prim attribute, e.g. `principal_priority`), which survives the split onto every child
edge; the planner turns that into `principal_start` / `principal_end` at each node the street
passes through, computed default = widest pair where nothing is authored. Per-node authoring
downstream stays possible by editing the booleans directly.

**STREET IDENTITY — data model decided 2026-08-17, derivation deferred to the markings/decals
milestone.** The artist's question ("should we already start to think street identity? it
would drive the middle stripe") is answered YES at the data level, and the schema above
already contains its local half: a valid principal pair at a node IS street identity through
that node — "straight means you stay on the street" was the ruling that ratified the widest
pair, and CityEngine's booleans encode the same statement. The global form is derived, not
authored:

* **`street_id`** (prim, on the edge, planner-written): chain the pairings. At every node
  whose claims form a valid pair, the two claimed edge-ends are one street; at every plain
  degree-2 point the two incident edges continue one street by default (a degree-2 node has
  exactly one through pair — authorable apart later if a boundary is ever wanted there).
  Union-find over those links; each component is a street, id'd deterministically (lowest
  member `edge_id` — the tongue-rank precedent, never cook order). Pure Python in `plan.py`,
  no HDA edits, testable on all 16 cases; the self-loop keyset defect recorded in
  `test_plan.py`'s docstring is in scope for whoever builds this, because a loop is one
  street whose two ends meet at one node.
* **Per-street flags ride the edges of the street** (fill-if-empty, artist wins), e.g.
  `median_continuous` — the busy-main-street condition the artist named: "you are not
  allowed to cross the other side of the road". One flag on the street, and every junction
  along it keeps its median decal running through and places its zebras accordingly. A flag
  that differs across one street's edges is a schema red, same discipline as cardinality.
* **Consumers, in order of arrival:** the median-continuation condition and zebra placement
  (markings are DECALS — artist ruling 2026-08-17, instancing first, geometry generation
  deferred wholesale); later naming, class/width consistency along a street, and decal runs
  that span a whole street. None of them move carriageway geometry: identity is
  markings-and-priority data, exactly like the type vocabulary since the §11.5 ruling.

### 11.4 The footprint function, and M1 — the experiment that gates everything

`plan.py` gets `crossing_trims(node) → {edge_id: consumed_m}` and
`junction_trims(node, principal) → …`: what each node type consumes from each arm, as a
FUNCTION of arms + widths + classes + corner radii — not a measurement of built plates.
(`junction_trims` was deleted 2026-08-17 with the render ruling — §11.5 ⛔ — after serving
as this section's measurement instrument; `crossing_trims` is the only trim model, every
vocabulary type builds it, and `node_trims` asserts that invariance.)
`standing(edge) = length − consumed(end A) − consumed(end B)`, checkable before any geometry
exists. This eventually retires the premeasure double-solve and its float32 drift.

⚠️ **CALIBRATE, DO NOT INVENT.** Dump measured `trim_start`/`trim_end` + node data from all 11
cases (hython script), and assert the crossing model predicts every measured trim within
0.5 m before trusting anything downstream of it.

**M1 deliverable:** with `junction` type and widest-pair principal at K's three corners, is
`standing > 0` on all three triangle sides? Committed as `test_plan.py`'s first fixture using
K's real numbers. **The verdict decides whether the spread is ever needed** — the principal
pair takes zero trim from its own node, so K's negative standing may simply not occur.

#### M1 BUILT AND MEASURED — 2026-08-15. The verdict, and what the calibration refused

Built: `polyfactory/scripts/python/polyfactory/citygen/plan.py` (pure Python, `hou`-free) ·
`tests/citygen/dump_trims.py` (hython, all 11 cases → `tests/unit/trim_calibration.json`,
524 arms) · `tests/unit/test_plan.py` (43 tests, 0.03 s). No HDA touched, no parm added; the
gate is unmoved at **20 failing, and an independent value-by-value diff against
`baseline.json` over all 11 cases moved zero entries**.

⚠️ **INDEPENDENTLY AUDITED FOUR TIMES — every round came back NO.** Round 1 came back NO on the
numbers rather than the code. The
auditor re-extracted the HDA, wrote its own transcription of `s5j_solve` from the VEX, and
found it agrees with `crossing_trims` to **1.1e-13 m over 40 000 random nodes** — including
**60 066 miter-clamp firings and 27 816 reflex (>180°) gaps**, configurations the 524-arm
fixture never produces. The construction is right. What was wrong was every number written
*about* it, and four mutations of `plan.py` that the suite could not see. Those four are fixed
and killed — ⚠️ but **"zero survivors" was never true of the whole suite and this section used
to say it was**: `test_plan.py`'s docstring records twelve, seven proven equivalent and five
reachable only through M3's adapter. Rounds 2–4 then found more, each in the *previous round's
fix* (§11.9 has the shape of it). The corrections are folded into the text below rather than
appended, and the ones worth carrying forward are:

- ⚠️ **THE RESIDUAL IS TWO-SIGNED, and the first version of this section claimed it was not.**
  `s5j_solve` latches monotone only from its third pass (`dist[i] = (iter < 3) ? dd :
  max(dist[i], dd)`), so passes 1 and 2 may RETREAT below the node-frame value. "The builder
  always cuts more" was a guess dressed as a measurement.
- ⚠️ **A 5.88 m optimistic error was recorded as a 2.02 m safety margin.** The published
  constant had been written from A/D/H before B and C were measured, and nothing asserted it —
  mutating it to 99.0 left the suite green. The quantity that matters is not the per-arm
  residual at all but the error on `standing`, where both ends compound: worst **+5.876 m**
  optimistic, **−8.418 m** pessimistic (C_radial / I_offset_radial).
- ✅ **AND THE PROPERTY THAT ACTUALLY MATTERS WAS TRUE AND UNASSERTED.** Over all **304 edges**
  of the suite the planner's `standing > 0` **verdict** never disagrees with the builder's —
  **0 false-OK, 0 false-BAD**. A planner 4 m out that calls every street correctly is usable; no
  residual table can distinguish that from one 0.1 m out that flips a verdict. It is now the
  suite's headline assertion, and it is the one to defend in M4–M6.
- ⚠️ **The miter clamp fires on 0 of 524 calibration corners**, and its one test used three
  arms of equal width — so `max(wA,wB)` and `min(wA,wB)` were the same number and two wrong
  clamps passed. Same shape as `max_fillet_fraction` (E), the S3b clamp (F) and the tongue (G):
  a mechanism the suite never runs at its design amplitude. Now pinned to 1e-4 on an
  arterial-against-local corner, and `COLLINEAR_SIN` is pinned either side of 1.146° — it too
  was free to take any value.

⚠️ **THE 0.5 m CALIBRATION IS MET ON FIVE CASES AND CANNOT BE MET ON THE OTHER SIX, and the
line between them is not arbitrary.** `crossing_trims` is a closed-form transcription of
`s5j_solve`'s corner construction in the NODE frame. What `s5j_solve` does that no function of
the plan can do is **re-read each arm's frame at its own current cut and re-solve the corner
there, eight times** — a fixed point on a straight arm, a moving target on a curved one:

| case | arms | worst \|predicted − measured\| | arms over 0.5 m |
|---|---|---|---|
| E_short_t · F_bend · G_tongue · **J_five_star** · **K_stub_triangle** | 27 | **≤ 0.000034 m** | **0** |
| A_drawn · D_offset · H_offset_strict | 66 | 2.024 m | 2 of 22 each |
| B_grid | 111 | 3.995 m | 24 |
| C_radial · I_offset_radial | 320 | 4.575 m | 97 of 160 each |

Two things came out of getting there, and both are load-bearing:

1. **`pfsg_clear_of_vertex` belongs to the PLAN, not the builder.** It moves 184 of the 524
   arms by up to `2 × min_end_segment` (worst +1.971 m), one-signed, and without it a
   `standing` is optimistic on a third of the city. It looked like geometry and is not: `s5_resample` cuts each arm
   into `ceil(L / 4 m)` EQUAL segments — verified on all 304 prims, spread 8e-5 m within one,
   and now asserted in `test_plan.py` against the fixture's own `npts`, which matters because
   10 of the 304 sit exactly on an integer `L / 4` where one ulp shifts the whole grid — so
   the vertex grid is a function of the arm's **length**, which is plain edge data. Modelling
   it is what took E/F/G/J/K from ~1.8 m of error to exact. ⚠️ Its two branches are NOT mirror
   images: the start branch takes the first vertex *strictly* beyond the cut, the end branch
   the first *at or* beyond, so a cut landing exactly on a vertex pushes from one end and not
   the other. Transcribed, and pinned by a control test against a literal walk of the grid.
2. **Closing the curved-arm residual needs the arm's SHAPE, and that is the §9 segment model,
   not a curvature fudge.** A segment's captured `(u, v)` frame is invariant under node moves
   by construction, so a planner carrying it could evaluate position and tangent at any arc
   length and iterate the builder's own fixed point exactly. That is the honest route and it
   is not M1's. Until it exists, `crossing_trims` is out by up to **4.58 m per arm either
   way**, and on `standing` — the quantity anything downstream reads — by **+5.88 m
   optimistic / −8.42 m pessimistic**, recorded in `plan.py` as `STANDING_OPTIMISM_M` and
   `CURVED_ARM_RESIDUAL_M`, pinned per case and signed in `test_plan.py`. ⚠️ These are bounds
   on the ERROR, not on the verdict, and they are not a safety margin to guard with — the
   verdict agreement above is the property to rely on.

**THE K VERDICT — and the answer to the question as posed is NO.** All numbers from K's own
measured node data; the crossing row reproduces the gate's `min_standing_m` −13.434 to the
millimetre without cooking anything, which is the claim of this section discharged.

| K, node type / principal rule | A–B (32.00 m) | A–C (32.25 m) | B–C (32.25 m) | worst over all 8 edges |
|---|---|---|---|---|
| **crossing** (today) | **−10.000** | **−6.651** | **−13.434** | −13.434 |
| **junction**, widest-pair principal (the computed default) | **−10.000** | +12.949 | **−13.434** | −13.434 |
| **junction**, principal = the pair nearest 180° apart | +11.000 | +12.949 | +12.649 | **+11.000** |

Why the computed default fails: at A and at B the two widest arms are the **external** arterial
and collector, so both triangle sides at that corner stay minors and keep their full trim. Only
C — degree 3, all three arms 14.4 m locals — has a triangle side wide enough to be principal,
and it can only take one of the two. **So junction type alone does not dissolve K, the
resolution ladder still needs its next rung, and the spread is not dead** (M6 stays open).

**But the type is not what decides it — the principal RULE is.** Choose the pair nearest to
running straight through, which is what a principal street *means*, and every side of K stands
with no node moved and nothing deleted. That is a candidate change to §11.3's computed default
and it is **the artist's call** (§11.12): the widest pair and the straightest pair are different
rules, and on K they differ by the whole outcome.

⚠️ **AND THAT THIRD ROW IS A COIN-FLIP UNTIL SOMEBODY BREAKS THE TIE ON PURPOSE.** Found by the
M1 audit. K's node C is *exactly* symmetric — |CA| = |CB| = 32.249031 and the third arm runs
along the axis of symmetry — so **two pairs are equally straight**, differing by 2.311e-07 rad
of float noise, and the rule as stated does not say which wins:

| principal at C | A–B | A–C | B–C | |
|---|---|---|---|---|
| E_00007 + E_00001 | +11.000 | +12.949 | +12.649 | K dissolves |
| E_00007 + E_00004 | +11.000 | **−6.651** | +32.249 | **K does not** |

This is §11.3's float-tie defect restated in ANGLE instead of length, and it is the second time
the same class has decided K. `test_plan.py` quantises the angle and falls through to the same
width → length → `edge_id` chain, which lands on the row that dissolves K — but that is luck,
not a reason, and **whichever rule ships must break this tie deliberately** (11.12).

⚠️ **AND THE FIRST TIE-BREAK WRITTEN FOR IT MOVED THE COIN-FLIP RATHER THAN REMOVING IT** — found
by audit round 2, on the fix rather than on the build. The key read only the first arm of the
pair, so the winner depended on the order `pointprims()` returned the arms in: of node C's six
orderings, **five gave +11.000 and one gave −6.651**, and on a symmetric X 12 of 24 permutations
disagreed. The key is now built from BOTH arms, sorted, so it is a property of the pair. **Any
computed default that ranks PAIRS has this failure mode**, and the same reading applies to
§11.3's widest-pair rule the day two arms tie on width and length.

⚠️ **AND THE FIX FOR *THAT* LEAKED THE SAME DEPENDENCE OUT OF ITS RETURN VALUE** — round 3. The
winning *set* became order-independent while the returned *tuple* stayed ordered by arm index,
and the neighbouring test read it positionally: three of six orderings failed, and in the failing
half the test constructed a **third** pair that is in neither row of the table above and dissolves
K as well. Round 4 then found the corrected order guaranteed but **unasserted** — reverting it
left the whole suite green. Three rounds, one defect, each fix landing one level further out:
the lesson is that **a rule which ranks pairs must be canonical in what it compares AND in what
it returns, and both halves need an assertion**, or the next reader inherits a guarantee with a
countdown on it.

✅ **RESOLVED BY THE ARTIST, 2026-08-16 — widest pair ratified, tie broken first-by-`edge_id`.**
The artist's definition settles what "straight" was standing in for: street continuity is
IDENTITY, not bearing — the biggest street through the node stays the same street even where it
bends — and CityEngine's automatic is the same rule. Checked against the sources rather than
asserted: no system in the reference set derives the principal from geometry or identity;
CityEngine uses maximal width with a per-street override, and OpenDRIVE's road identity is a
label, not a selector. The straightest-pair rows above stay as the measurement that forced the
decision. The tie falls to lexicographic `edge_id` — the deterministic list — never arm order,
which is the coin-flip documented above. Schema consequence in §11.3: the principal became
per-edge booleans, CityEngine's own shape.

⚠️ **AND THE DOCUMENTED TIE-BREAK WAS UNREACHABLE.** §11.3 says *maximal `streetWidth`; tie →
longer, then lexicographic `edge_id`*. On K's third corner the three arms are all 14.4 m wide
and two of them are the same 32.249 m long — and in float the widths differ by 5e-6 m and the
lengths by **1.3e-12 m**, so `-width` alone settled it and the lexicographic step was dead code.
Which of two identical triangle sides survived turned on 1.3e-12 m. `default_principal` now
quantises to **1 mm** — the noise floor `graph_reaches_a_fixed_point` already works to — before
ranking, so the rule that runs is the rule the doc describes. Same defect class as S8's argmin
instability at `max_aspect` 1.8.

### 11.5 Node types — builder contracts

- **crossing** — `s5j_solve`, unchanged. Since the 2026-08-17 ruling below it is not merely
  the default the planner writes: it is what EVERY vocabulary type builds today, and
  `plan.node_trims` asserts that invariance. ⚠️ The invariance is a statement about what is
  BUILT, not a law about types: the ruling is that a type may not change how a junction is
  DRIVEN (open mouth, kerb into the fillets, median interrupted), and priority-through-a-node
  therefore lives in markings. The **merge** below is the one type whose contract genuinely
  consumes carriageway — a length along the principal, not a plate — so M5 breaks this
  invariance deliberately, and `node_trims` and the builder move together when it does.
- **junction** — ⛔ **SCHEMA ONLY.** The paragraph below is the contract as DESIGNED and BUILT
  in M4, and it was reverted on 2026-08-17 (ruling immediately after it): the principal pair
  WAS to be one continuous street through the node — no break, no mouth, no trim contribution
  from this node; minors trimming to the principal's flank (halfwidth + corner arc); plate a
  rectangle on the principal spanning the minor mouths (CityEngine's blue). None of that is
  built. What the type means today: this node's principal pair is the street that has
  PRIORITY through it — data for the zebra and median decals, and the local half of street
  identity (§11.3).

  ⛔ **ARTIST RULING 2026-08-17 — the as-built junction render is a BUG, not a decision.** The
  uncut principal carries its kerb/sidewalk band and its median stripe straight across the
  minor's mouth, and a street you cannot turn into is not a junction. The crossing's carriageway
  solve — open mouth, kerb breaking into the fillets, median interrupted — is the ONLY correct
  geometry, for every type. What "the principal runs through" buys is NOT geometry, it is
  markings and priority: the through-footway reading becomes a **zebra crossing** over the
  minor's mouth, and the median continues ONLY as an authored special condition (the busy main
  street you may not cross) — a per-STREET property, which is exactly what street identity is
  for. Markings are a **decal workflow** (artist's call, same day — instancing is the point),
  so their generation is deferred wholesale; the junction type keeps its schema and principal
  pair as the DATA that will drive those decals. The jtrim/is_plate/through-extension build
  path above is overruled as a shipped look; whether it is gated off now or at the markings
  milestone is M4-close-out sequencing, not an open design question.

  ⚠️ **HISTORICAL — THE THREE GAPS between the plate paragraph and M1's model, measured
  2026-08-15 by the M1 audit; M4 closed them by DECIDING rather than by matching, and the
  2026-08-17 revert deleted both sides.** `plan.junction_trims` WAS `crossing_trims` with the
  principal zeroed — exact for the model, and not the same claim as "this is the plate above".
  Kept because these are now the ONLY surviving record of the measurements (the tests that
  carried them went with the function), and because a merge (M5) consuming footprint along a
  principal will meet gaps 1 and 2 again:
  1. **Two adjacent minors with no principal between them.** The model charges their
     minor-to-minor kerb corner; a rectangle-on-the-principal has no such corner in it.
     Measured, 14.4 m minors at 70° and 110° off an arterial principal: **30.77 m against
     22.59 m**. The model is the conservative one.
  2. **`max_fillet_fraction` caps on the principal ARM's length, not the through-length** it
     would have as one continuous street. Measured on 30 m arms: a minor trims **25.40 m under
     the arm cap, 29.40 m under the 60 m through cap** — and this one goes the UNSAFE way, the
     plan under-charging the minor by 4 m.
  3. **The computed principal need not run through at all** — at K's node A the widest pair sits
     **70.0°** apart (node B's is 113.4°), and the model then returns zero trim on both arms of
     it. A pair that bends 110° through its own junction is not "one continuous street"; nothing
     signals it today.

  ⚠️ **S7 WAS the named integration risk**: the block boundary IS the kerb, and at a junction
  node the principal's kerb ran *through* while minor kerbs teed into it — `blocks_kerb`'s
  collect-and-close had to survive that. It did (Q: 0 unpaired ends), the risk is moot while
  no type cuts differently, and the S7 T-case (11.10) and its render requirement both DID
  their job: the render is what killed the feature. **The rule generalises — any future typed
  build (M5's merge first) re-opens S7 and gets LOOKED at before it is called done.**
- **merge** — chosen where the approach angle is under `min_junction_angle` (reuse the parm,
  do not duplicate it): the minor is re-routed (11.6) toward the principal. ⚠️ "Arrive
  parallel and fuse tangentially" was the contract as written; §11.6's weld law (measured
  2026-08-17) makes a tangent arrival unreachable in this pipeline, and the SHIPPED landing
  arrives at θ/2 ≈ 10.5–14°, one resample step out.
  Feasibility: minor length ≥ `R_min(class) × θ` + a parallel run (new parm, artist default —
  ~11.7 m of swing for an arterial at 25°, so this is real length). Its footprint is consumed
  ALONG the principal — a length, not a radius — and `standing` on the principal must account
  it. Infeasible → planner falls back down the ladder (T realign, then spread). Never delete.
- **roundabout** — vocabulary reserved, nothing built. §S5a already measured it cannot rescue a
  crowded pair; it returns later as an art option, not a repair.

### 11.6 The re-route — one mechanism, two targets

Replace the minor's last stretch with a curve through pinned endpoints, tangency at the landing,
`R ≥ R_min(class)`: target **0°** = the merge; target **75–90°** = the T landing that closes
⛔ §S5a item 4. Investigate reusing the S3b clamp machinery (`pfsg_turn_clamp_solve` family)
before writing a new solver — same constraint family, one extra tangency pin. Verification is a
control rig in the `turn_clamp_control_rig` mould: authored-feasible and authored-infeasible
pairs, swept across street classes and `turn_radius_scale` — the gain-sweep lesson says sweep
every new parameter across its shipped range.

#### The construction, SOLVED 2026-08-17 (M5.3's planner half)

⚠️ **THE LANDING IS NOT THE NODE, and that is forced by geometry rather than chosen.** A
circle tangent to the principal AT the node has its centre on the normal there, so its distance
to the minor's line is `R·cos θ` — equal to `R` only at `θ = 0`. **No arc can be tangent to
the principal at the node and also leave the minor tangentially.** What exists is the arc
inscribed in the corner between the minor's ray and the principal's CONTINUING direction (an
angle of `π − θ`), and its two tangent points sit

> **`T = R·tan(θ/2)`**

either side of the node — one back along the minor, one forward along the principal. So:

* the **minor** gives up its last `T` of straight and gains an arc of `R·θ`, i.e. a merge
  **LENGTHENS** the minor by `R(θ − tan(θ/2))` = 5.75 m on an arterial at 25°. Every other
  footprint in `plan.py` shortens a street; a consumer that assumes "trim" here has the sign
  backwards.
* the **principal** pays `T + parallel_run` on its **DOWNSTREAM arm only** — 9.94 m at 25° on
  an arterial. The upstream arm pays nothing; the construction never reaches it.
* the **minor's endpoint MOVES** from the node to the landing, and the principal splits there.
  That is a topology change, so §11.7's rest/rebuild pair is mandatory and the re-route is one
  of its two legal consumers — exactly as §11.7 already says.

⚠️ **`plan.merge_consumed_along_principal` returned `R·sin θ + run` until this was worked
out**, which is a different quantity and not a per-arm one: `R·sin θ` is the span between the
two tangent points measured along the principal, so it STRADDLES the node. Written into one
arm's trim it over-charges that arm by 54% at 25° and under-charges the other by all of it.
The identity that made the wrong one look plausible — and that now pins the right one — is
**`T(1 + cos θ) = R·sin θ`**, asserted exactly in `test_plan.py`.

⚠️ **The feasibility gate is CONSERVATIVE against this construction, deliberately.** §11.5
charges `R·θ + run` (10.59 m for a collector at 25°) where the construction only needs `T`
(3.35 m). Conservative is the safe direction for a feasibility test, and the gap is the room
the parallel run will need once the artist pins it — do not tighten the gate to `T` first.

#### The mover SHIPPED 2026-08-17 — and the pipeline overruled the tangent

`graph_merge_route` (detail wrangle after `graph_width`, where street widths first exist;
`graph_min_angle` keeps its detection as the tripwire's skeleton and deletes NOTHING). The
mover moves ONE point — the swing street's node-end vertex is rewired onto an EXISTING vertex
of the continuing arm — plus a same-pass `polypath` (`merge_split_switch` gates it behind the
mover having fired, because an unconditional rebuild moved every case at the float noise
floor: Q gained a lot). The swing arm is the pair member that is LESS anti-parallel to the
third arm — the naive minor-most rule picks O's host-east arm, which is collinear with the
through street and has no construction at all.

⚠️ **THE TANGENT CONSTRUCTION DOES NOT SURVIVE THIS PIPELINE, and that is a LAW, not a
bug to fix later — three shapes were built and each was measured off:**
1. endpoint moved only → `graph_turn_clamp` pins prim ENDPOINTS and cannot round a bend that
   sits at one: arrival 25°, an arterial pair at a forbidden angle, 98.5 m miter trims, 2
   self-intersections.
2. the exact tangent arc written by the mover → a tangential arc runs nearly parallel to the
   host, its first sample sat 0.12 m from a host sample, and `graph_fuse`'s **0.5 m point
   weld** dragged the junction onto the arc: the landing migrated −8 → (−4.004, 0.098).
3. arc samples kept 0.6 m clear of both tangent lines → the clamp and resample REBUILD
   near-host points every pass; the weld found those instead.

An approach at angle α keeps points within weld radius `c` for `~c/sin α` of length, so
tangency at 4–5 m sampling with a 0.5 m weld is unreachable by geometry. **The shipped
landing is therefore ONE RESAMPLE STEP out** — arrival 10.5–14° for every committed
configuration, every sample clear of the weld under resample jitter — and the landing is an
existing vertex, so nothing ever dangles for `graph_extend` to retarget. The tangent ideal
returns the day the fuse can exempt a merge mouth or the local sampling gets finer.

**Result on the deleting cases:** M and O ship ALL their streets —
`deleted_in_pass0.graph_min_angle` 1 → **0** on both, `repair_merged` 1, landings exactly one
vertex out, stable across every pass. `merge_route_control_rig` (16 rows, the
`turn_clamp_control_rig` mould) pins the contract on eight stations: fires / infeasible /
above-floor / degree-4 / sub-band / through-host / perpendicular-partner, the re-fire OUTCOME
through a polypath split (landing coordinates, not counts), the EVALUATED
`merge_parallel_run` default (the parm was once missing entirely and literal substitution made
the sweep blind to it — the audit's blocker), and both new parameters swept to an IN-RANGE
feasibility flip.

⚠️ **Three envelope guards ship with the mover, all audit-drawn:** an ARRIVAL FLOOR —
`θ < 2·asin(0.6/4)` ≈ 17.25° parks the pair (counted, `repair_merge_subband`), because below
it the weld owns the landing again (10° and 6° pairs were drawn and their junctions migrated);
an ENDPOINT guard — the node must be a prim endpoint of all three arms, or dirs read off the
wrong end and the mover rewired a leg 40 m up a side street; and a PARTNER guard — the pair
partner must continue the third arm within 150°, or there is no through street to merge into
(both counted, `repair_merge_shape`). ⚠️ Sub-17° pairs now SURVIVE as shallow crossings that
the weld drags 0.35–0.41 m off-axis (measured at 10°/6°) — pre-existing weld behaviour newly
EXPOSED because nothing deletes those pairs any more; the ladder's next rung owns them. ⚠️
And the re-fire guard's redundancy is PARAMETER-DEPENDENT, the audit's refutation of my first
record: the floor dominates it only while `min_junction_angle` ≤ ~31° (chord geometry; 34.5°
by the θ/2 model) — raise that artist parm past it and the `merged_end` guard alone stops the
landing walking, measured at minang 45° / θ 36°: (−5,0) → (−10,0) guard-less.
⚠️ **The open half is the MOUTH: the landing builds as a crossing at ~12°, below the 25°
floor the corner solve was designed against.** Collector widths (M) build it green; arterial
widths (O) ship a ~100 m gore wedge with 2 surface self-intersections and a 3.17 corner-arc
tangent error — O's two rows in the known-failing table. The merge mouth in `s5j_solve` (and
its `node_trims` mirror, same commit) is the remaining M5 work, and the artist has not yet
ruled on the gore look at all.

**STILL OPEN after the mover shipped:** the merge MOUTH contract in `s5j_solve` and its
`plan.node_trims` mirror, in one commit — the landing builds as a crossing at ~12°, below the
25° floor the corner solve was designed against, and O's two known-failing rows are its
recorded price · ⛔ §S5a item 4, the 75–90° T-landing — the mover's second target, not built ·
the tangent ideal, which returns only with a fuse exemption or finer local sampling · the
artist's ruling on the gore look. ⚠️ The mover cannot fire in pass 0 (its chain position sees
endpoint-only prims there); the earliest fire is pass 1, measured — irrelevant at the default
12 passes, fatal to anyone lowering `repair_passes` to 1.

### 11.7 Segment-model integration requirements

The §9 rest/rebuild pair is correct and reverted; rebuild it verbatim, subject to: (a) the
rebuild stores the endpoints with the frame and **skips bit-exact** when they have not moved
(float32 u/v drifted ~1 mm/pass and moved 68 recorded values inside the loop's tolerance);
(b) it lives ONLY inside a mover that repositions nodes and does nothing else — wrapped around
`graph_realign` it overwrote the realign's deliberate approach blend (`trim_metric` 0 → 2.66 m,
1 closed loop → 2 open). The re-route (11.6) and the spread (11.8) are its only legal consumers.

### 11.8 The cluster spread — fallback, reference implementation

Status at revert: **20 → 15 failing.** K: gap 32.0 → 40.61 m, arms 5 → 4, standing −13.43 → ✅,
`selfx_junction_surface` 50 → 0, `selfx_city_merged` 87 → 4, city prims intact (1979 → 2017) —
and ONE regression: `graph_min_angle` deleted 1 street in a late pass (`edges` 8 → 6, the
triangle's interior block lost). Do not attempt guard #4 — 11.0 explains why the guard cannot
be written from where the spread runs. Under the planner the interaction is decided before
geometry exists, or the shallow leg is a merge and `graph_min_angle`'s deletion is retired
(M5) — which is the artist's ruling.

Ship checklist if re-integrated (M6): planner chooses it, not a threshold · strip `dbg_*`
details · clean `repair_spread_nodes` / `repair_spread_m` before the city output
(`no_scratch_attribs_city` polices details) · tripwire accounting stays honest.

Wiring: `s5j_spread_mark` (attribwrangle, run over prims, input 0 = `junction_premeasure`) and
`graph_cluster_spread` (attribwrangle, run over detail, input 0 = `graph_drop_tongue`,
input 1 = `s5j_spread_mark`, output → `graph_degree_final` input 0).

`s5j_spread_mark`:

```
#include <pf_streetgraph.vfl>

// S3 - the two-junction streets that cannot host both their junctions.
// The complement of `s5j_tongue_mark`: that one keeps LEAF arms and deletes
// them; this keeps streets with a junction at BOTH ends - the case its rails
// refuse, because deleting one disconnects the city. Separating is the third
// option beside delete and merge. Runs on the premeasure copy of the junction
// solve, so the number cannot drift from what ships.
float ratio = chf("../s5j_params_min_standing_widths");
int   pts[] = primpoints(0, @primnum);

if (ratio <= 0.0 || prim(0, "is_junction_patch", @primnum) == 1 || len(pts) < 2) {
    removeprim(0, @primnum, 0);
    return;
}
int d0 = neighbourcount(0, pts[0]);
int d1 = neighbourcount(0, pts[-1]);
if (d0 < 3 || d1 < 3) { removeprim(0, @primnum, 0); return; }

float w = prim(0, "streetWidth", @primnum);
if (w <= 0.0) { removeprim(0, @primnum, 0); return; }

float L  = pfsg_primlength(0, @primnum);
float ts = prim(0, "trim_start", @primnum);
float te = prim(0, "trim_end", @primnum);
float standing = L - ts - te;
float need     = ratio * w;

// ⚠️ THE TRIGGER IS AN ERROR, NOT A THRESHOLD, and getting that wrong cost a
// whole build. Firing on `standing < need` fixed K and REGRESSED 14 checks on
// C_radial and I_offset_radial - three two-junction streets at ratio 0.82-0.85,
// under the floor, tolerated by design, measurably clean. `standing <= 0` is
// the error: the plates have consumed more street than exists, so they
// physically overlap (K: -13.43 m). A short street that still fits is a short
// street.
if (standing > 0.0) { removeprim(0, @primnum, 0); return; }

setprimattrib(0, "spread_deficit", @primnum, need - standing);
setprimattrib(0, "spread_standing", @primnum, standing);
```

`graph_cluster_spread` (the damped, guard-free build — the 15-failing state):

```
#include <pf_streetgraph.vfl>

// S3 - SEPARATE A CLUSTER OF JUNCTIONS THAT CANNOT FIT, AND CARRY THE STREETS.
//
// ⚠️ THE CLUSTER SCALES UNIFORMLY ABOUT ITS OWN CENTROID; IT IS NOT A SUM OF
// PER-EDGE PUSHES. Attempt five pushed each deficient edge apart on its own;
// on a 3-cycle every corner is an endpoint of two or three deficient edges and
// got shoved that many times per pass - the triangle tumbled and K's graph
// emptied, 1979 prims -> 0. One scale factor per cluster is one target per
// node. Uniform scale also preserves every angle, so the plates keep their
// size and the requirement does not move while we satisfy it; the factor
// solves in closed form, s >= (L + deficit) / L per edge, largest wins.
//
// ⚠️ THE REBUILD IS THE SECOND HALF OF THIS NODE, NOT A NODE OF ITS OWN.
// Moving an end node while the ~5 m resampled interior stays put hinges the
// street at the junction. As a separate wrangle around `graph_realign` it
// overwrote the realign's own approach blend: trim_metric 0.0 -> 2.66 m.
//
// ⚠️ SEGMENTS WHOSE ENDS DID NOT MOVE ARE NOT TOUCHED - not "recomputed to
// the same value", untouched. float32 (u,v) is ~1 mm lossy at 800 m and this
// sits in a ten-pass loop: unconditional, it moved 68 recorded values under
// graph_reaches_a_fixed_point's 1 mm tolerance.
//
// `edge_id` is the key, never the prim number: `s5_resample` and `s5_fuse`
// sit between the streams (the graph_drop_tongue precedent).
int nmark = nprimitives(1);
if (nmark == 0) return;
int n0 = nprimitives(0);
int np = npoints(0);

// --- the deficient edges, resolved into this stream -----------------------
int defprim[] = {};
float defneed[] = {};
for (int q = 0; q < nmark; q++) {
    string eid = prim(1, "edge_id", q);
    float def = prim(1, "spread_deficit", q);
    if (def <= 0.0) continue;
    for (int p = 0; p < n0; p++) {
        string e = prim(0, "edge_id", p);
        if (e == eid) { append(defprim, p); append(defneed, def); break; }
    }
}
if (len(defprim) == 0) return;

// --- flood-fill the clusters they join ------------------------------------
int lab[]; resize(lab, np);
for (int i = 0; i < np; i++) lab[i] = -1;
int ncl = 0;
foreach (int idx; int pr; defprim) {
    int pp[] = primpoints(0, pr);
    int a = pp[0], b = pp[-1];
    int la = lab[a], lb = lab[b];
    if (la < 0 && lb < 0) { lab[a] = ncl; lab[b] = ncl; ncl++; }
    else if (la < 0) lab[a] = lb;
    else if (lb < 0) lab[b] = la;
    else if (la != lb) { for (int i = 0; i < np; i++) if (lab[i] == lb) lab[i] = la; }
}

vector cen[]; resize(cen, ncl);
float cnt[]; resize(cnt, ncl);
float scl[]; resize(scl, ncl);
float rad[]; resize(rad, ncl);
float cap[]; resize(cap, ncl);
for (int c = 0; c < ncl; c++) {
    cen[c] = {0, 0, 0}; cnt[c] = 0.0; scl[c] = 1.0; rad[c] = 0.0; cap[c] = 1e9;
}
for (int i = 0; i < np; i++) {
    int c = lab[i];
    if (c < 0) continue;
    cen[c] += vector(point(0, "P", i));
    cnt[c] += 1.0;
}
for (int c = 0; c < ncl; c++) if (cnt[c] > 0.0) cen[c] /= cnt[c];

// --- the factor each cluster needs ----------------------------------------
foreach (int idx; int pr; defprim) {
    int pp[] = primpoints(0, pr);
    int c = lab[pp[0]];
    if (c < 0) continue;
    float L = pfsg_primlength(0, pr);
    if (L < 1e-4) continue;
    scl[c] = max(scl[c], (L + defneed[idx]) / L);
}

// --- and what the arms LEAVING the cluster will allow ----------------------
// The realign's own rail: no endpoint moves further than half its own street.
for (int i = 0; i < np; i++) {
    int c = lab[i];
    if (c < 0) continue;
    rad[c] = max(rad[c], distance(vector(point(0, "P", i)), cen[c]));
    foreach (int pr; pointprims(0, i)) {
        int pp[] = primpoints(0, pr);
        int o = (pp[0] == i) ? pp[-1] : pp[0];
        if (lab[o] == c) continue;          // internal to the cluster
        cap[c] = min(cap[c], pfsg_primlength(0, pr) * 0.5);
    }
}
for (int c = 0; c < ncl; c++)
    if (rad[c] > 1e-4) scl[c] = min(scl[c], 1.0 + cap[c] / rad[c]);

// ⚠️ AND DAMPED, BECAUSE THE LOOP IS THE SOLVER. K needs s = 2.26 in one step,
// which yanks each corner ~23 m and lets the cleanup downstream delete the
// wreckage - measured, K emptied to 0 prims. The loop runs up to ten passes
// and re-measures every one; 1.12^10 is over 3x, more than any real input
// needs. (1.12 is a magic number - derive from remaining passes or expose as
// a parm if this ships.)
for (int c = 0; c < ncl; c++) scl[c] = min(scl[c], 1.12);

// --- capture every touched segment in its own chord frame ------------------
int touched[] = {};
float ru[]; resize(ru, np);
float rv[]; resize(rv, np);
vector pa[]; resize(pa, n0);
vector pb[]; resize(pb, n0);
for (int p = 0; p < n0; p++) {
    int pp[] = primpoints(0, p);
    if (len(pp) < 2) continue;
    if (lab[pp[0]] < 0 && lab[pp[-1]] < 0) continue;
    append(touched, p);
    vector A = point(0, "P", pp[0]);
    vector B = point(0, "P", pp[-1]);
    pa[p] = A; pb[p] = B;
    vector ch = B - A; ch.y = 0;
    float L = length(ch);
    if (L < 1e-5 || len(pp) < 3) continue;
    vector dir  = ch / L;
    vector perp = normalize(cross(dir, set(0, 1, 0)));
    for (int k = 1; k < len(pp) - 1; k++) {
        vector d = vector(point(0, "P", pp[k])) - A; d.y = 0;
        ru[pp[k]] = dot(d, dir) / L;
        rv[pp[k]] = dot(d, perp) / L;
    }
}

// --- move the nodes -------------------------------------------------------
int nmoved = 0;
float total = 0.0;
for (int i = 0; i < np; i++) {
    int c = lab[i];
    if (c < 0 || scl[c] <= 1.0 + 1e-9) continue;
    vector Pp = point(0, "P", i);
    vector Q = cen[c] + (Pp - cen[c]) * scl[c];
    Q.y = Pp.y;                              // planar per layer
    setpointattrib(0, "P", i, Q);
    total += distance(Pp, Q);
    nmoved++;
}

// --- and carry the streets with them --------------------------------------
foreach (int p; touched) {
    int pp[] = primpoints(0, p);
    if (len(pp) < 3) continue;
    vector A = point(0, "P", pp[0]);
    vector B = point(0, "P", pp[-1]);
    if (distance(A, pa[p]) < 1e-6 && distance(B, pb[p]) < 1e-6) continue;
    vector ch = B - A; ch.y = 0;
    float L = length(ch);
    if (L < 1e-5) continue;
    vector dir  = ch / L;
    vector perp = normalize(cross(dir, set(0, 1, 0)));
    for (int k = 1; k < len(pp) - 1; k++) {
        vector q = A + dir * (ru[pp[k]] * L) + perp * (rv[pp[k]] * L);
        q.y = 0;
        setpointattrib(0, "P", pp[k], q);
    }
}
setdetailattrib(0, "repair_spread_nodes", nmoved, "set");
setdetailattrib(0, "repair_spread_m", total, "set");
```

### 11.9 Milestones — each ends with the full gate, a baseline compare, and an audit

- **M0 — this commit.** Spec + constitution recorded; spread preserved above; working tree
  reverted to the committed 20-failing state.
- **M1 — the planner core and the K verdict.** **BUILT 2026-08-15, AUDITED FOUR TIMES.**
  `plan.py` + `test_plan.py` (43 tests) + `dump_trims.py`. Gate unmoved: 20 failing, zero moved
  entries on a value-by-value baseline diff, re-verified independently in three separate rounds.
  Exit as written was *calibrated within 0.5 m on all 11 cases*: **met exactly (≤ 3.4e-5 m) on
  the five straight-arm cases including K, and refused on the six with curved arms** — the
  residual is `s5j_solve`'s own frame refinement and closing it needs the §9 segment shape, not
  a fudge. K's verdict (11.4) is **negative for the widest-pair principal**: two of three sides
  still overlap, so the spread is not dead and M6 stays open.

  ⚠️ **NO ✅ HERE, AND THE AUDIT HISTORY IS THE REASON.** Rounds 1–4 all returned NO, and the
  shape of them is the record worth keeping: round 1 found the construction correct to 1.1e-13 m
  over 40 000 random nodes and **every number written about it wrong**; rounds 2 and 3 each found
  that *the fix for the previous round* was itself behaviourally wrong (a coin-flip moved from
  float noise to arm order, then the same dependence leaking out of a return value); round 4
  found **no behavioural defect and no moved answer** — one unasserted guarantee and three doc
  errors. That is convergence, and it is also four rounds of evidence for §11.0's thesis: the
  defects were never in the geometry, they were in decisions made against a representation
  nobody was asserting. Surviving mutants and the guarantees `dump_trims.py` supplies that
  **M3's adapter must re-establish** are listed in `test_plan.py`'s module docstring.
- **M2 — cases first.** **BUILT 2026-08-15, AUDITED TWICE.** Four cases, 11 → 15; gate 20 →
  **26 failing**, and the baseline diff is **4635 insertions and ZERO deletions** — verified
  against `HEAD` rather than trusting the diff shape: **0 pre-existing values moved**. Three of
  the six new rows are the declared v1 non-goal already recorded on ten other cases; the other
  three are defects the build had and nothing could see.

  **The shallow-Y family** (M 24° · N 32° · O 22°) samples either side of `min_junction_angle`.
  `graph_min_angle` deletes one street in pass 0 on M and O; N keeps its leg.

  ⚠️ **There was a fourth, L at 15°, and an audit deleted it.** It was bit-identical to M on
  all 50 checks and all 848 leaf baseline values — because below the floor the published graph
  does not depend on the angle at all: the leg goes, the Y node falls to degree 2, the host
  re-fuses, and the shallow site leaves NO trace. The decisive measurement was a control scene
  with no shallow leg drawn at all, which reproduced **44 of L's 50 checks**. The whole of L was
  one bit, and M carries the same bit closer to the floor. **A case that is bit-identical to
  another today does not earn its place on a promised future divergence** — add the second
  sub-floor angle the day M5 gives it something to assert. And the bracket is looser than ±1°:
  the samples locate the floor only to (24, 32]; swept live the transition is at (24.998, 25.5],
  and a case authored at exactly 25.0° still deletes, because the leg endpoint is rounded to
  2 dp and measures 24.998°.

  ⚠️ **AND WHAT DECIDES WHICH STREET DIES IS LENGTH, NOT ANGLE OR CLASS** — found by audit,
  and it killed the family's first fourth case. `graph_min_angle` reads only
  `min_junction_angle` and `pfsg_primlength`, and it runs at **position 16** of the repair chain
  while `graph_classify` is at 22 and `graph_width` at **23**: in **pass 0** class and width do
  not exist when the verdict is taken, and the tie-break is
  `kill = (lens[i] < lens[j]) ? prims[i] : prims[j]` — keep the longer. ⚠️ From pass 1 the
  loop's feedback carries `street_class` and `streetWidth` written by the previous pass, so they
  exist and are simply **not read**; do not reorder the chain expecting that to change anything. A case built to show "class
  does not change the verdict" could therefore never have failed — it was true by construction.
  O now varies the thing that actually decides: its leg is LONGER than the host's east half, so
  `graph_min_angle` takes **the host's own arterial**, and the city ships the west host fused to
  the leg as a single **599.77 m** street — verified by geometry: no edge terminates at (200,0).
  Nothing else in the suite reaches that branch. (It truncates the host rather than severing a
  connection: the deleted edge's far end is degree 1, so `connections_are_never_refused` stays
  green, and O earns its slot on its published GEOMETRY — 2730 city prims against M's 3380,
  `centreline_curvature_within_class` 0.648/1.01 against 0/0 — not on the deletion alone.)

  ⚠️ M and O stay GREEN on `connections_are_never_refused` while each deletes a street, because
  pass 0 is exempt by design. The deletion is **recorded** in `deleted_in_pass0.graph_min_angle`
  = 1 rather than asserted, so the baseline pins it and M5 turning it to 0 is visible.

  ⚠️ **N's TWO RED ROWS ARE ONE DEFECT, IT IS NEW, AND TWO ROOT CAUSES WERE WRONG BEFORE THIS
  ONE.** First the absent `merge` type was blamed; then a zero trim. The second matters, because
  the fix it implied would not have worked. Measured: `s5j_trim` deletes a junction's shared
  point unconditionally — *"a shared junction point belongs to several edges; only ever delete
  it"* — and the surviving last point is moved to the cut only by `if (de < te)`. **The
  predicate is that line and it is not a constant**: `de` is the arm's own TERMINAL SEGMENT,
  `L / ceil(L / step)` — bounded by `(step/2, step]`, so a 2.00 m floor in principle, and
  measured **3.5832 .. 4.0000 m** over the suite's 545 junction-side ends, equal to 4.00 only on
  the 22 whose length is an exact multiple of the step. So the
  endpoint is re-created only when **`trim > de`** and the hole is **`de − trim`**. ⚠️ Two
  earlier versions of this entry said "non-zero" and then "`> 4.00 m`" — 4.00 is the resample
  CAP, and writing the fix as `if (te < 4.0)` detaches it from the geometry it was measured on. Swept on the
  shallow-Y rig: a 25.5–45° leg leaves trim 0.0000 and a **4.000 m** gap; 50° leaves trim 1.4107
  and **2.589 m**; 55° leaves 2.9575 and **1.043 m**; from 60° the trim clears 4 m and the gap
  is 0. **A non-zero trim of 1.41 m still leaves a 2.59 m hole**, so "snap when the trim is
  zero" ships a green gate over a live defect — the corpus has no arm strictly between 0 and 4,
  and four arms sit at 4.35–5.00 m, 0.35 m from the trigger.

  ⚠️ **And the trigger was over-generalised twice.** It is not "every junction with one wide
  arm pair" — of **545 arms** exactly **one** has a junction-side trim ≤ 4 m (N's, measured
  0.0000; the count read five while M4's four deliberately-uncut Q arms existed, and the
  2026-08-17 revert gave them real crossing trims again), and **89 of the 90
  junctions with two or more arterial arms do not exhibit it** (`G_tongue` is two collinear
  arterials plus a third and trims 22.4 all round). ⚠️ That second figure read `87 of the 88`
  and BOTH halves were wrong — the denominator was the pre-Q count, stale since M4 added a
  sixteenth case, and the numerator moved with this revert. The audit caught it three words
  from the clause I had just recomputed: **re-derive the whole sentence, not the number you
  came for.** Nor is it "the arm opposite a near-floor pair
  at a 3-arm node", which generalised one rig. **The hole condition is just `trim < de`**: an
  arm's trim is `max(reach_ahead, reach_behind, 0)` in the planner and in the builder alike, so
  any arm whose larger corner reach falls short of its own terminal segment gaps. ⚠️ "Both
  corner reaches ≤ 0" is a SUB-condition — it yields `trim == 0` and so the MAXIMAL hole, the
  full `de`; both `_corner` implementations floor at ≥ 0, so it can only mean "== 0", and the
  precise form is `raw + run ≤ 0` (the fillet run counts, so "kerb lines cross behind the node"
  alone is not it). Degree-independent either way: over legal degree-4 nodes (every gap ≥ 25°,
  nothing deleted) **964 bearing sets** produce an arm at trim ≤ 4 m — e.g. bearings
  (0, 25, 150, 275) at widths (26.8, 15.1, 26.8, 15.1) → **2.957 m, with BOTH reaches at
  +2.957**, a real gap with neither reach at zero. The angle floor is not part of it at all: on the 3-arm rig
  the opposite arterial is at trim 0.000 for **every** gap from 5° to 45°, and symmetrically at
  135–175°. On N the hole is **107.20 m² = 4.00 × 26.80 exactly** (not the 104.53 first
  recorded), a clean rectangle — which is what the root cause predicts.
  **Recorded, not fixed: M2 is cases-first.**

  ⚠️ **And `city_is_fully_paved` cannot see it**, because it builds the must-be-paved region
  from the corridor's own outer boundary — which the same defect breaks. On N those prims span
  x −518.09..−4.00 and 0.00..518.09, so the hole falls outside the region by construction and
  the check passes at `unpaved_m2 0.0`. The one check written to find holes is blind to a hole
  that also opens the block boundary: the `selfx_*` lesson again, a check whose input is
  produced by the thing it is checking.

  **The stub chain** (P) reproduces ⛔ item 5 exactly, from a spec written before the case
  existed — and by the specified MECHANISM, not merely to the same counts: live instrumentation
  inside the repair loop reads `cluster 4, narm 6, ok 1` → permits, then `graph_stub_kill` **3**
  in pass 0 by design and **`graph_drop_orphans` 2 LATE**, red on the tripwire, **3 edges of 9
  published**. The flood fill past a 3-cycle now has coverage; K only ever exercised the
  triangle.

  ⚠️ **AND THE FIRST VERSION OF THE FAMILY PUBLISHED AN EMPTY GRAPH ON THREE OF FOUR CASES**
  — city 0, edges 0, reported as three tidy red rows. §11.11's own warning arriving on schedule.
  Not a bug: `graph_min_angle` removes the shallow leg, the Y node falls to degree 2, the
  component holds no junction, and `graph_drop_orphans` correctly deletes all of it. **A host
  with one leg is one deletion away from nothing.** Each Y now carries a second plain T 300 m
  west so the case measures the angle rather than the orphan filter — and that is a rule for
  every case added from here: a case whose graph can empty asserts nothing.
- **M3 — schema + adapter.** ✅ **BUILT 2026-08-15.** `junction_type` / the principal (as
  `principal_edges`, reworked to the per-edge booleans 2026-08-16 — see the addendum) +
  `junction_schema` in `checks.py`; the planner writes `crossing` everywhere unless authored.

  **EXIT MET, and it was established by comparing GEOMETRY, not by trusting the baseline diff.**
  The baseline records what the checks look at, and a check that looks at nothing sees nothing.
  The audit digested every output of every case — point / prim / vertex counts, a hash of the
  full vertex→point topology, and every value of every point, vertex, prim and detail attribute
  with floats packed as doubles — against the HDAs checked out from HEAD. **30 differences over
  15 cases × 4 outputs, and all 30 are the two new string attributes appearing on the GRAPH
  output.** `P` is bit-identical on city, blocks, lots and graph everywhere. The baseline agrees:
  gate 26 failing before and after, and the diff is insertions only — new check rows, no moved
  value.

  ⚠️ **AND THE FIRST ATTEMPT AT THAT A/B PRODUCED A FALSE GREEN** — worth knowing before
  anyone repeats it. With `HOUDINI_PATH` set as the gate command sets it, Houdini auto-scans
  `polyfactory/otls` at startup and those definitions WIN over an explicit
  `hou.hda.installFile` of a HEAD copy, so both halves of the A/B cooked the working-tree HDA
  and came back byte-identical, md5 and all. Any before/after here needs a guard that prints
  and asserts the library file path and the node's presence before cooking.

  **The adapter is `graph_plan`**, a Python SOP after `repair_scratch` in the segmenter — the
  `xsection_library` precedent, and §11.2's shape exactly: geometry → plain data →
  `plan.default_junction_type` → attributes written back on `is_node` points. It sits AFTER the
  repair loop, so it decides once on the settled graph rather than against a representation the
  loop keeps invalidating (rule 6). **This also pays §11.2's other debt** — for two milestones
  `plan.py` was imported by nothing but its own test, which is the state that killed the deleted
  `graph.py`; it now has a real consumer.

  ⚠️ **The principal attributes are created and deliberately LEFT EMPTY** (originally the
  `principal_edges` string; the per-edge booleans since the 2026-08-16 rework). §11.3 called it fill-if-empty
  with a computed default, but 11.4's audit found the two candidate rules — widest pair vs
  straightest pair — disagree on K by the whole outcome, with the tie between them decided by
  float noise. Freezing either into geometry now would ship a decision 11.12 reserves for the
  artist, and M4's rollout is authored-only first for exactly that reason.

  ⚠️ **The attributes leaked onto every city point and no check could see it.** They belong on
  graph nodes; the city mesh has no use for a `junction_type` string per point. Caught by
  probing the outputs directly rather than by the gate — `no_scratch_attribs_city` polices
  DETAIL attributes only, so a point-attribute leak was invisible to it. Cleaned at
  `out_detailclean`, the city branch's existing attribdelete (the `lots_publish` precedent), so
  the graph output — a pass-through of the mesh's input 0 — keeps them.

  ⚠️ **ADDENDUM 2026-08-16 — THE PRINCIPAL SCHEMA WAS REWORKED TO THE BOOLEAN SHAPE** on the
  artist's ruling (§11.3): `principal_edges`, the node-side string, is RETIRED; the principal is
  `principal_start` / `principal_end`, int booleans on the edge prim. The rework was proven the
  same way the original was: gate 26 failing; the only baseline movement is **15 `junction_schema` values gaining the
  deliberate `claims` key** (the principal's pin — without it, turning the computed default on
  would move ZERO baseline values; written for M4's flip, which the 2026-08-17 ruling blocked,
  and the pin outlives it because the booleans still ship as data), geometry unmoved — and
  eight fresh injections on the boolean shape all
  fail as red rows with clean restores, including the one the string shape could not survive: a
  wrong-TYPE value authored upstream, which now produces red rows instead of killing all 15
  cases. A well-formed authored pair stays green. One trap found installing it: **a string parm
  evaluates backtick pairs as HSCRIPT** — identifier-like contents happen to be benign, which is
  why every earlier snippet cooked, and a pair containing dots is a syntax error that kills the
  whole cook. The new leak channel that comes with prim-class attributes — the booleans riding
  the sweep onto the published city's ROAD PRIMS — is cleaned at `out_detailclean` (`primdel`,
  previously empty) and detected by the leak check's home-map scan.

  **`junction_schema` is proven able to fail**, and it took two rounds to make it so. ⚠️ The
  injection list below is the STRING ERA's, kept as history — the boolean shape makes the three
  principal injections inexpressible, and its own eight injections are recorded in the
  2026-08-16 addendum above and `tests/README.md`. The audit
  found three states it passed that it should not: `principal_edges` naming the SAME edge twice
  (a pair that is one street), a principal on a dead end (only `junction_type` was degree-paired),
  and — the vacuity this project keeps rediscovering — `is_node` destroyed, where every term
  reads 0 because the loop never runs. All three now fail, alongside the original five: adapter
  bypassed → *attribute missing*; outside the vocabulary → `bad_vocab` 6; a type on a degree-1
  node → `typed_non_junction` 8; a principal naming a stranger, only one edge_id, or the same
  edge twice → `bad_principal` 6 / 6 / 6; a principal on a dead end → `bad_principal` 8.

  ⚠️ It deliberately does NOT assert WHICH type a node carries: `junction_type` is
  artist-authorable, so "junction everywhere" is a legal state and a check forbidding it would be
  asserting taste. What pins today's choice is the recorded `types` histogram — any change to
  what the planner computes moves it visibly. (Written for M4's flip; that flip is blocked
  since the 2026-08-17 ruling, and the pin is what makes ANY future default change visible.)

  ⚠️ **AND THE LEAK FIX SHIPPED WITHOUT A DETECTOR, WHICH IS THE COMPOUNDING RULE BROKEN ON THE
  ONE CHANGE M3 MADE THAT WAS NOT A NO-OP.** Measured on frozen copies with the leak put back:
  `no_scratch_attribs_city` returns PASS 0 (it is called with `None, None`, so city POINT
  attributes are deliberately unpoliced) and `attribute_schema` returns PASS 0 (it counts only
  MISSING attributes). Clearing `out_detailclean`'s `ptdel` left the whole suite green. And
  `crossing` written on 497 non-node graph points left `junction_schema` green with all four of
  its terms at zero, because it only ever reads nodes. **`node_schema_stays_on_the_graph`** is the
  detector, and it took three rounds to finish: `leaked` (city / blocks / lots AND the graph, on
  points, VERTICES, prims and detail — `out_detailclean` had the same vertex hole), `off_node`
  (in the string era it read BOTH attributes — `principal_edges` on 497 shape points had left
  both checks green; since the boolean rework it reads point-class `junction_type` only, the
  booleans being prim-class with their own claim accounting),
  `untyped_plated` (any point the builder would plate that is not a typed node — both checks
  select by `is_node`, the attribute the adapter also selects by, while `s5j_solve` never reads
  it), and `schema_source` (the shared name-set constant was INERT for a round because the
  import path was wrong, and a value-identical fallback hid it). Nine injections proven to fail.

  ⚠️ **FILL-IF-EMPTY WORKS AND THERE IS NOWHERE TO AUTHOR — M4 INHERITS THIS.** An authored
  `junction_type` set upstream of the segmenter survives the entire repair loop and `graph_plan`
  correctly declines to overwrite it, measured end to end. But **node identity does not exist
  upstream**, so authoring there is necessarily blanket, and blanket authoring is exactly what
  the schema check rejects (`typed_non_junction` 8, `bad_principal` 14 → red). Downstream, where
  `is_node` exists, `graph_plan` has already written `crossing`, so the artist would be
  overwriting rather than filling. **The §11.3 `graph_classify` precedent does not transfer**:
  `street_class` is a PRIM attribute on a drawn curve that has identity before the segmenter
  runs, while `junction_type` is a POINT attribute on a node the segmenter CREATES. **BLANKET
  authoring upstream needs no HDA unlock** — a plain attribwrangle in the artist's own scene
  reaches it, and all 14 nodes shipped the authored value with `graph_plan` declining every one.
  What has no surface is PER-NODE authoring, and blanket authoring fails three terms, not two:
  `typed_non_junction` 8, `bad_principal` 14 **and `off_node` 497**. M4's authoring surface has
  to clear all three.

  Recorded and not fixed: the SOLVER's output 1 (the junction solution) also carries both
  attributes — 822 empty and 6 on the real junction nodes, so tidiness rather than wrong data,
  and one node upstream of where the city branch is cleaned — and **no check is passed the
  solver's outputs at all**. Also open, all unreachable today and recorded so the next round does
  not re-derive them: `node_schema_stays_on_the_graph` receives city / blocks / lots
  POSITIONALLY, so swapping two of them is undetectable (only a graph-vs-other swap is caught);
  an EMPTY graph still passes `junction_schema` vacuously, where only `counts` would show it; a
  differently-CASED attribute name (`Junction_Type`) and a GROUP named for a schema attribute are
  both outside the leak scan; and `untyped_plated` inherits the builder's self-loop blind spot by
  construction — a closed street contributes one prim, so a 3-arm junction made of a loop plus
  one street reads degree 2 to the check and to `s5j_solve` alike.

  ⚠️ **AND THE SELF-LOOP IS A PLANNER DEFECT, NOT A CHECK QUIRK — AND IT IS UNOWNED.** It was
  assigned to M4, and **M4 closed on 2026-08-17 without fixing it**; the next milestone to
  touch this ground owns it, and street identity (§11.3) meets it first, because a loop is one
  street whose two ends meet at one node. `test_plan.py`'s docstring lists it among the
  guarantees "M3's adapter must re-establish", and **M3 did not**: nothing in `graph_plan` or
  either check prevents, detects or asserts a closed edge. The audit found the mechanism
  underneath it: any `edge_id`-keyed trim dict (`junction_trims` then, `crossing_trims` now)
  collapses a loop's TWO arms to ONE key and an arm is silently lost — and `_arms`
  in the adapter takes only `pts[1]` or `pts[-2]`, yielding one arm where two exist. **`edge_id`
  is not a valid arm key.** Unreachable today (0 closed prims on all 15 cases, and
  `graph_mark_orphans` deletes any component with no point of degree >= 3), which is why
  a principal pair that is one street twice is RED — since the boolean rework via THREE guards:
  `junction_schema`'s same-prim claim test, `default_principal`'s distinct-street skip, and
  `principal_of`'s distinct-id fallback on the authored channel (the third found unasserted by
  the rework audit's own mutation pass, and now pinned). The symptom is guarded; the cause
  (`edge_id` is not a valid arm key) stays M4's.
- **M4 — junction type in the builder** — ⛔ **CLOSED 2026-08-17 WITH THE BUILD REVERTED.** Its
  plan was: authored-only first; S7 T-case green and its render LOOKED at; then flip the
  computed default in its own commit; re-measure K. The render step did its job and killed the
  feature — the type ships as SCHEMA ONLY (markings + identity data, §11.3/§11.5), the flip is
  blocked, and K's rescue reverts to the resolution ladder (M5/M6). See the close-out below.

  ⛔ **EVERYTHING FROM HERE TO THE CLOSE-OUT IS A HISTORICAL RECORD OF A BUILD THAT WAS
  REVERTED.** The artist looked at the render on 2026-08-17 and ruled it a bug (§11.5 ⛔): the
  build below is not in the repo. Kept because its measurements are the evidence — the S7
  finding, the three audit blockers, the injection proofs — and because the schema half of it
  survives. Read it in the past tense; the close-out at the end of this milestone says what
  stands today.

  **AUTHORED-ONLY HALF BUILT 2026-08-16.** `s5j_solve` validated an authored junction (type +
  exactly two principal claims from two distinct prims — the planner's cardinality rule,
  mirrored) and built THE CROSSING CONSTRUCTION with two differences: principals took no
  street trim (they wrote `jtrim_*`, the KERB-only trim) and their caps were marked `is_plate`.
  Anything invalid builds as a crossing, and `junction_schema` reds the geometry so the
  fallback cannot pass silently — proven by injection (cardinality 1 → crossing trims on every
  arm, `bad_principal` 2, kerb still closed).

  ⚠️ **THE S7 RISK WAS REAL AND IT LIVED IN `s5j_trim`, NOT `blocks_kerb`.** The first build
  left a **7.96 m hole in the through carriageway over every junction node**: `s5j_trim`
  deletes the shared node point unconditionally, and with trim = 0 nothing re-created the
  endpoint — M2's measured `de − trim` gap arriving exactly where its record predicted, and it
  also shifted every arc `blocks_kerb` measures from the prim start (the kerb landed one
  resample segment off, 16 unpaired ends). Fix: the deleted point's neighbour re-extends to the
  node when its end carries `jtrim > 0`, so the carriageway is continuous and arc zero IS the
  node. `blocks_kerb` then treats a through end like a trimmed end for the KERB — frontage
  truncated at the plate corners, no false dead-end cap — and the collect-and-close closes:
  **Q_junction_ring, 0 unpaired ends, 1 interior block, 155 lots.**

  **The Q case** (two authored `junction` Ts on a ring) is the S7 T-case: gate 16 cases,
  **27 failing = 26 + Q's `selfx_city_merged` (122, the declared v1 non-goal — the plate spans
  the principal, whose ribbon runs beneath it: coplanar overlap, recorded not fought)**. All
  15 pre-existing cases bit-identical at GEOMETRY level (audited digest, 0 differences); the
  only baseline movement is the deliberate `unbuilt_type: 0` key on 15 `junction_schema` rows — because every new
  code path is behind attributes that only exist once a junction is authored. The calibration
  closed the geometry→planner round trip at last: `dump_trims` exports the type and the claims,
  `test_plan` dispatches `node_trims`, and Q reproduced to **1e-5 m** — `junction_trims` with
  authored booleans WAS the builder's plate, principals at zero included. (Post-revert the same
  round trip runs against the crossing solve and Q reproduces to **7.9e-5 m**; the export and
  the dispatch are what survived, the model they agreed on is `crossing_trims`.)

  ⚠️ **AUDIT ROUND 1 (NO) found the guarantees around the geometry, not the geometry.** Three
  blockers, all fixed and re-injected: (F1) a `junction` node with ZERO claims was schema-legal
  while planner and builder fell back DIFFERENTLY — a green gate over a 12.93 m disagreement in
  the state an artist reaches by typing the node and stopping. `node_trims` now mirrors the
  builder's fallback exactly (invalid pair → crossing) and `junction_schema` reds
  typed-no-claims (`bad_principal`). (F2) a vocabulary-RESERVED type (`merge`) was schema-legal
  and CRASHED the calibration, since M4 put `node_trims` on that path — reserved types now build
  as crossing on both sides and `junction_schema` reds them (`unbuilt_type`), the not-silent
  duty moved to geometry. (F3) the through seam was measured by NOTHING — pulling a through end
  7.96 m back along the street, reopening the exact hole the fix closes, left every check
  bit-identically green. `trim_metric_is_consistent` now asserts terminal == node per through
  end (Q: 6 ends measured, was 2).

  **§11.5's model-vs-plate gaps: TWO of three are DECIDED, in the model's favour** the builder keeps the
  crossing's minor-minor corners (two adjacent minors' kerbs really do collide before the
  principal's flank) and the per-arm `max_fillet_fraction` cap — so builder and planner agree
  by construction instead of by tolerance. The plate is the crossing boundary with the
  principals uncut, which over the principal's span IS "a rectangle on the principal spanning
  the minor mouths". **The THIRD gap stays OPEN, on the authored channel**: nothing tests the
  angle of an authored principal pair — the audit built a ring with junctions AT the corners and
  two "through" ribbons leaving each node at 90.0°, all green including kerb closure. Partly
  freedom (authored beats computed; a bent principal is legal geometry), partly unmeasured: on a
  principal CURVING at the node the re-extension chords across one resample sample — ~0.30 m of
  centreline error and ~8.5° of ribbon rotation at the tightest legal arterial radius, by the
  closed form; no committed case reaches it. Also recorded from the audit: **Q's blocks and lots
  are bit-identical to the crossing build** — on straight collinear principals the kerb lands on
  the same points either way, so Q asserts the through-kerb only in the collinear/one-minor
  configuration (the audit measured bent-pair, two-minors-same-side and minors-both-sides
  variants all closing, uncommitted); and the solver's graph pass-through is no longer spanned
  by `input0_reaches_an_output` since it reads the mesh's actual input.

  **`input0_reaches_an_output` now reads the mesh's ACTUAL input 0** rather than the
  segmenter's output as a proxy for it — §11.3's downstream authoring path legitimately writes
  between the two, and the proxy reported Q's authored attributes as drift on a faithful
  pass-through. Value-identical on unauthored cases.

  **The render review happened 2026-08-17 and the verdict is REJECTED** (⛔ ruling in §11.5):
  the uncut principal's through-kerb and through-median block turning traffic — a bug, not a
  decision. The "sidewalk band sweeps THROUGH" item this list used to carry as a cosmetic is
  the disqualifying defect. Consequences: the **computed-default FLIP is BLOCKED**, no longer
  merely the artist's timing call — flipping it would put ruled-wrong geometry on every
  degree-≥3 node; it stays off until the junction builds the crossing's carriageway solve and
  the through-ness lives in markings (zebra decal + conditional median, deferred with the decal
  workflow). Quarantine fact: the wrong look only exists where `junction` is AUTHORED, i.e. in
  the Q case — no computed default ever writes it. Still recorded: differing principal widths
  abut without a taper (K's arterial + collector pair will show a step; CityEngine tapers,
  v1 abuts) — moot while the junction renders as a crossing, alive again when markings land.

  **M4 CLOSE-OUT — the revert, 2026-08-17 (the ruling made mechanical).** The three M4 build
  wrangles went back to their 763ca6c text byte-exactly — `s5j_solve` (jt/isP gate, `jtrim_*`
  writes, `is_plate` caps), `s5j_trim` (the through-end re-extension), `blocks_kerb` (jtrim
  truncation + dead-end-cap guards) — verified by extracting all three from the written
  libraries and diffing against both git states: reverted wrangles == pre-M4, everything else
  == HEAD, node inventories unchanged, `out_detailclean`'s schema masking untouched (it
  pre-dates M4). Planner: `junction_trims` DELETED, `node_trims` collapses to
  crossing-for-every-vocab-type (out-of-vocab still raises), and the K-verdict measurement
  family (`_straightest` + its pins) went with the model it measured — the arm-order lesson
  re-pinned on `default_principal` (permutation test), the ruling pinned twice
  (`test_no_vocabulary_type_moves_a_trim_since_the_ruling` on K's real nodes,
  `test_node_trims_is_type_invariant_and_flag_invariant` on synthetic ones). Calibration
  regenerated: Q's worst residual 0.000079 m (straight-exact again), 545 arms / 322 edges
  unchanged, 38 unit tests green. `trim_metric_is_consistent`'s `is_plate` skip and `jtrim_*`
  through-end term removed — the attributes they read can no longer exist. Gate: **moved
  values are Q-ONLY and every one improves or re-reports** — `selfx_city_merged` 122 → 4 (the
  coplanar plate WAS most of Q's self-intersection count — the z-fight the artist saw), city
  prims 4137 → 4033 (equal to the crossing twin), `trim_metric` still 6 ends at 0.0 max; 27
  failing before and after, no regressions. Q's lot floor pinned at 139 (155 shipped, the A–D
  precedent — the render has now been looked at). What SURVIVES of M4: the schema, the
  adapter, the principal booleans and their planner rules, `junction_schema` /
  `node_schema_stays_on_the_graph`, and Q as the proof that authored schema flows while the
  build stays the crossing's. What DIED: every geometric consequence of the type.

  **REVERT AUDIT, round 1 — seven findings, and the worst one was mine.** It verified the
  claims independently (`hotl -X` per-node diffs proving the three wrangles byte-identical to
  763ca6c and every other `.parm` identical to 86f61b1; **`junction_type` proven inert on three
  topologies it had never seen** — all four vocabulary values × principal flags on/off authored
  onto A, J and K, 24 variants, city/blocks/lots digests bit-identical to unauthored in all 24,
  with the harness proven non-blind because the graph attribute digest DOES move; gate 27
  failing matching the working-tree baseline on all 832 rows). Then: **(F1, mine, the reason
  the verdict was NO) the §11.9 rewrite welded M5's bullet onto the end of this close-out** —
  deleting M5 from the milestone list while three cross-references still pointed at it, and
  making this paragraph claim the revert had turned the shallow-Y family green. A text merge,
  invisible to every test in the repo. (F2) §11.5's live half still specified the reverted
  build in the present tense — *after* the ⛔ ruling, and disagreeing with `cases.py`, which
  had been past-tensed. (F3) **a stale plan inside an HDA**, `graph_plan`'s comment still
  sequencing the flip, invisible to `git diff`. (F4) `tests/README.md` contradicted itself 60
  lines apart. (F5) `default_junction_type` had NO unit coverage: four mutants of it survived
  all 38 tests — a coverage gap, not a live defect (the gate's four schema terms catch each),
  but its docstring now carries the post-ruling planner's strongest claim. (F6) **the junction
  HDA's `hdaroot` came back `display on render on` where both git states have off** — the
  flag ride-along, through a guard that watched children and not the root. (F7) two stale
  rationales in `checks.py`. All seven fixed, and the F3 fix cost two further HDA-write traps
  of my own (eval/backticks, `.OPfallbacks`/CWD) — recorded with F6's in §11.11, where
  `hotl -X` is now the standing discipline.

  **Round 2 ran as TWO independent verification passes, confirmed every fix, and found
  fourteen more between them — all mine.** (Recorded because the two passes could not see
  each other: the second one later reported that the first two items below were self-found
  and asked me to strike the audit's credit for them. They were the FIRST pass's N1 and N2.
  Provenance across concurrent auditors is exactly as easy to get wrong as the counts
  below.) The material ones: a number
  I had just recomputed was wrong again three words later (`87 of the 88` → **89 of the 90**,
  where the denominator had been stale since M4 added Q and the numerator moved with this
  revert — *re-derive the sentence, not the number you came for*); `JUNCTION_TYPE_VOCAB` and
  `RESERVED_JUNCTION_TYPES` were **never pinned by value**, so widening either survived every
  test — which this change made load-bearing, since `node_trims` now branches on vocabulary
  membership and nothing else; §11.5's rewritten `crossing` bullet claimed a type changes the
  carriageway "never", contradicting the merge contract twelve lines below it; M6's new
  rationale credited the revert with closing an exit that M1's measurement had closed two days
  earlier; §11.11's own whitelist was FILE-scoped, so as first written it could not have
  caught the trap it was written for; `plan.py`'s `default_principal` still named
  `junction_trims` in the present tense; and the README's test count was corrected 45 → 38 in
  the same round a 39th test was added. Every one fixed, the vocabulary pins mutation-checked.
- **M5 — merge type + re-route** (11.6 control rig included). Shallow-Y family goes green;
  `graph_min_angle` stops deleting — a shallow angle becomes a planner signal (the artist's
  ruling); tripwire accounting updated; ⛔ §S5a item 4 closed by the same mechanism at 75–90°.

  **M5.1 BUILT 2026-08-17 — the planner's merge model, and the milestone's gating verdict.**
  Pure Python, no HDA touched, the M1 pattern: decide on the abstract graph whether a merge is
  POSSIBLE on the cases that need one before building anything. `min_turn_radius` (S3b's
  `0.5 × width × turn_radius_scale`, ⚠️ **not** `corner_radius` — 26.8 m against 9.0 m on an
  arterial, and mixing them silently triples the answer), `merge_swing_length` = `R·θ`,
  `merge_feasible`, and `merge_consumed_along_principal`. Calibrated against §11.5's own worked
  number: 26.8 × radians(25°) = **11.694 m**, the "~11.7 m of swing" the contract quotes.
  ⚠️ **The principal pays the PROJECTION, not the arc** — `R·sin θ` + the run, not `R·θ`: 3% of the arc
  at 25° and 36% at 90°, an over-charge that grows with the angle and would have ridden
  into `standing` unnoticed. **THE VERDICT: both deleting cases can be merged instead** — M's
  120 m collector leg at 24° needs 10.33 m; O's minor is NOT its leg but the host's **200 m
  arterial east arm** (the leg is 300 m, over `arterial_len` 180, so it is a 26.8 m arterial
  and the longer of the contested pair — `graph_min_angle` takes the host's own arm and the
  case ships west+leg fused as one 599.77 m arterial), needing **14.29 m**. Feasible either
  way with better than eleven times the margin. ⚠️ The first record of this verdict read
  "O's 300 m leg needs 9.80 m", assuming one class for the whole family when the family varies
  LENGTH and length decides both the class and which arm dies — 46% low, on the paragraph M5.3
  builds on. The verdict survived the correction; its evidence did not. So `graph_min_angle`'s deletion is replaceable and the
  milestone stands. ⚠️ **And the infeasible path is one short case away from unreachable, which
  I first wrote down as a wrong number**: "the shortest leg any case carries is 100 m" failed
  on 20.0 m — `E_short_t`'s arm, the case built to be the shortest thing in the suite.
  Measured over all 322 edges at the 25° floor the tightest margin is **1.945×**; nothing is
  infeasible, so §11.5's ladder fallback is code no committed case reaches and M5.3 owes it an
  authored case rather than a green suite that reads as coverage. `MERGE_PARALLEL_RUN_M` = 4.0
  is a PLACEHOLDER pinned so a change is visible, not a measurement — §11.5 leaves it to the
  artist.

  ⚠️ **AND THE FEASIBILITY FLOOR IS A LOWER BOUND, NOT THE ANSWER — M5.3 inherits this.**
  `merge_feasible` charges the swing that turns the minor PARALLEL; it does not charge getting
  it ALONGSIDE. At `R_min` the whole swing displaces `R(1 - cos θ)` = 2.51 m at 25°, well
  inside a 26.8 m arterial's own carriageway, so the model does not yet express §11.5's "arrive
  parallel and fuse tangentially". If the artist pins the lateral target at centreline
  separation (26.8 m for two arterials) the cost is 63.4 m of minor at 25° — **four times**
  what the gate charges. The M/O verdict survives that (margins 11.6× → 2.9× and 14.0× →
  3.5×, both still feasible) but the corpus-wide 1.945× does NOT: `E_short_t`'s 20 m arm would
  need 48.8 m and become infeasible, which turns "the ladder fallback is unreachable" into "it
  is reached today". So the lateral target is an M5.3 decision that can move the gate, and
  nothing may treat this floor as settled until it lands.

  **M5.2 BUILT 2026-08-17 — the shallow-Y family goes green: gate 27 → 25 failing.** N's two
  red rows were one defect with **two causes in two different wrangles**, and fixing only the
  first made the second worse — worth recording, because the first fix alone looked like
  progress on one row while `block_boundary_closes` went from 1 open loop to 3.
  (a) `s5j_trim` deletes a junction's shared point unconditionally and only ever moves a point
  that is INSIDE the trim, so a cut falling within the first resample segment had nothing land
  on it and the street started a step short — the `de − trim` hole, 107.20 m² on N. The
  neighbour of the deleted point now takes the cut, which is the same move the existing
  branches make one point further along, and is reachable only where the node point really is
  shared (a dead end keeps its length). (b) That put the road ON the node with `trim_end = 0`,
  and `blocks_kerb` read `trim <= 0` as "dead end" and laid a cap **across a live junction** —
  three kerb runs at each flank point. ⚠️ **The snippet's own warning had predicted this shape
  and mis-attributed the trigger**: it said the proxy holds "because the graph has NO degree-2
  nodes", when a degree-THREE node whose corner reaches are both ≤ 0 writes trim 0 just as
  well. The test is now cap PRESENCE — asked of the patch, whose corners sit 0.000 m from the
  frontage endpoints — and the snap and the dead-end test read the same predicate, so they
  cannot disagree. Result: `trim_metric_is_consistent` max **4.00 → 0.00 m**,
  `block_boundary_closes` **1 open loop / 2 unpaired ends → 0 / 0, one closed loop** (the
  corridor's outer boundary; N is acyclic so `blocks 0` is correct), and **no other value in
  the suite moved.**

  ⚠️ **M5 is the first milestone that has to build a typed node's GEOMETRY under the 2026-08-17
  ruling**, and the only type whose contract legitimately consumes carriageway: the merge's
  footprint is a LENGTH along the principal (§11.5), so the trim half lands in the solver and
  in `plan.node_trims` together — never one without the other, which is the mirror duty the M4
  audit priced at 12.93 m. Its other half is the re-route, and that is NOT a solver change:
  §11.6 points it at the S3b clamp machinery and §11.7 confines it to a mover that repositions
  nodes and does nothing else. Whatever it builds gets LOOKED at before it is called done —
  every check was green on M4's render, and the artist's eye is what caught it.
- **M6 — the spread**, only if M5 leaves it a consumer. ⚠️ Its old exit condition — "if K
  dissolves under junction type, delete the spread as dead" — is retired, but ⚠️ **not by the
  revert**: M1 measured on 2026-08-15 that the widest-pair principal does NOT dissolve K
  (§11.4's table, two of three sides still overlapping), and the artist ratified widest pair on
  08-16, so the exit was already closed before the junction type was built. The revert only
  removed the geometry that the retired reading still referred to. K's six red rows are M5's
  and M6's to answer.

### 11.10 Test plan

New: `test_plan.py` (M1) · stub-chain case · shallow-Y family (M2) · S7 T-case (M4) · re-route
control rig (M5) · `JUNCTION_TYPE_VOCAB` pinned. **Quiet-case A/B hash** for every new
mechanism: on cases where its trigger is absent, output hashes must equal a build with the
mechanism bypassed — bit-exact, not within tolerance. ⚠️ Do NOT assert bit-exact idempotence on
the *whole* repair loop: `forced_extra_repair_pass` already measures a 2.16e-05 m residual from
float32 re-accumulation; the loop is not bit-stable today and that is a separate, older debt.
`parm_liveness.py` runs for every added parm. Baseline updates only with every moved value
justified in the commit.

### 11.11 Environment and traps

Gate: `POLYFACTORY="F:/projects/polyfactory/polyfactory"
HOUDINI_PATH="F:/projects/polyfactory/polyfactory;&" hython
tests/citygen/run_scene_checks.py [--json out.json]` (Houdini 22.0.398). Compare
fixed/regressed/moved against `tests/citygen/baseline.json` — and ⚠️ **read `counts` before
believing any green**: three checks went green on 2026-08-15 while K's graph was EMPTY. HDA
edits via hython + `definition().updateFromNode(node)` — it writes the library file
immediately. Editing a `#include`d .vfl does not recompile dependent wrangles (nudge the
snippet). `edge_id`, never prim numbers, across streams. `resample` unshares points and
interpolates attributes. Type `point()` returns into locals. Never save a .hip in tests. Named
git paths only — no tree-wide add/checkout/stash, another agent may share the repo.

⚠️ **`graph_fuse`'s 0.5 m POINT WELD OWNS ALL NEAR-PARALLEL GEOMETRY.** Any two graph
points within 0.5 m become one, every pass, forever — and a curve arriving at angle α keeps
points within 0.5 m of its target line for ~0.5/sin α of approach. Below ~13° (at 4–5 m
sampling) the weld starts eating the approach: measured on the merge, where it dragged a
junction 4 m along the host and 0.098 m off it, twice, through two different "fixes". Design
shallow approaches around the weld — land steeper, or on an existing vertex — rather than
fighting it; the drawn corpus never trips this because `min_join_angle` (45°) keeps drawn
curves apart.

⚠️ **MUTATION TESTING CAN TEST THE MUTANT INSTEAD OF THE RESTORE.** Python invalidates a
`__pycache__/*.pyc` on (mtime, size), and any mutation that PRESERVES THE BYTE COUNT —
flipping a constant (`2.0` → `1.0`), an operator (`<=` → `>=`), a digit — leaves (mtime, size)
unchanged if the restore lands inside the same mtime second, so the cache still looks valid
and the next run imports the MUTANT. ⚠️ A length-CHANGING edit (`>=` → `>`, one byte shorter)
is safe by accident, which is worth knowing precisely so the rule is not over-applied. Measured 2026-08-17: four `TestMerge` tests failed against a restored
tree because `min_turn_radius` was still returning 13.4. It cost ten minutes and it reads
exactly like a real regression — and the dangerous direction is the other one, a stale cache
reporting SURVIVED for a mutant the tests would have killed. **Delete the `__pycache__`
directories between every mutation AND after the restore**, and re-run the suite once at the
end to prove the tree is clean.

⚠️ **THREE WAYS AN HDA WRITE CHANGES MORE THAN YOU EDITED, none of them visible in
`git diff` on a binary — all three hit the 2026-08-17 revert: trap 2 was found by its audit,
traps 1 and 3 by me while fixing what that audit found.** Verify every HDA write by expanding
both versions with
`hotl -X <dir> <file>` and diffing the trees. ⚠️ **The whitelist is LINE-scoped, not
file-scoped, and that distinction is the whole point** — `hdaroot.def` differs on EVERY write
because its `stat` block carries `create`/`modify`, and the `flags =` line that trap 2
corrupts lives in that same file, so a rule that waves the FILE through cannot catch trap 2.
It has to be read. Besides the sections you deliberately edited (`<node>.parm`, plus
`hdaroot.order` / `hdaroot.net` / `Contents.contents` if you added a node — which trap 2's own
remedy tells you to do), the only differences that may pass are:
`INDEX__SECTION`; the `create`/`modify` lines inside a `*.def` `stat` block **and nothing else
in that file**; and `.OPdummydefs` — ⚠️ **only after you have looked inside it**, because it
is not a timestamp file: it caches whole nested HDA definitions (the segmenter's copy embeds
the entire `Sop/pf_citygen_junction` type, DialogScript included), so a real interface change
next door moves it materially. `cat -v` it and confirm only the embedded epochs moved. ⚠️ Do
not confuse it with `.OPfallbacks` — three letters apart, a different file, and the subject of
trap 3, which is the OTHER way nested-asset bookkeeping goes wrong:
1. **`parm.eval()` on a string parm evaluates its backtick pairs as HSCRIPT.** Reading a
   4 KB Python-SOP comment block with `eval()` and writing it back stripped EVERY backtick
   pair in it (4170 → 4146 chars) while the intended edit landed perfectly. Read
   **`parm.unexpandedString()`**, write that, and assert the backtick count moved by exactly
   what your edits account for. (The older half of this trap — a backtick pair *containing
   dots* killing a cook outright — is why the rule was written; this is the silent half.)
2. **The instance's own display/render flags become the stored `hdaroot` flags.** A geo whose
   ONLY SOP is the instance forces them ON, so `updateFromNode` writes `display on render on`
   into the definition. Guarding `allSubChildren()` flags does not catch it — the root is not
   its own child. Match what git has: add a second SOP to hold the flag when the definition
   stores `off`, add nothing when it stores `on`.
3. **`.OPfallbacks` records a nested HDA's library path RELATIVE TO THE PROCESS CWD.** Editing
   the segmenter from the repo root rewrote its record of the junction HDA from
   `otls/…` to `polyfactory/otls/…`. Run the edit from the directory that reproduces the
   committed spelling (here `<repo>/polyfactory`).

### 11.12 Reserved for the artist

Type vocabulary naming · the merge's parallel-run default · whether roundabout enters v1 at
all · the median-continuation condition's authoring shape (per-street flag, §11.5 ruling) ·
the zebra decal's look and placement rules.

**Decided 2026-08-16, no longer open:** the principal rule (widest pair, ratified — continuity
is street identity, not bearing) and its tie-break (first by `edge_id`, the deterministic list,
never cook order). Recorded with the CityEngine and OpenDRIVE evidence in §11.3 and §11.4.

**Decided 2026-08-17, no longer open:** the S7/T-case render review — verdict REJECTED, the
uncut-principal junction render is a bug (⛔ §11.5); the computed-default flip is BLOCKED on
that rework, no longer a timing call; street markings are a **decal workflow** (instancing
first, generation deferred). For the third time the artist's viewport reading overturned what
the numbers said: every check was green on geometry a driver could not use.
