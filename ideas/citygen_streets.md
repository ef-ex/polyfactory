# CityGen — Street Generation Design

**Status:** design, not implemented. Nothing built yet.
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
4. **Reference vocabulary is borrowed; software is not.** We reuse CityEngine's *attribute names*
   (`streetWidth`, `sidewalkWidthLeft`…), its *junction classification words*, and OpenStreetMap's
   `layer`/`bridge`/`tunnel` convention. Naming conventions carry zero dependency.
   **CityEngine is inspiration — the most complete reference found — explicitly not a 1:1 rebuild.**

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
`max_slope` (hard cap). Names taken from CityEngine because they are already the right
abstractions.

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
- **Seeding:** jittered grid scaled by `density`, plus explicit artist seed points. Major
  streamlines traced first and completely, then minor streamlines seeded in the gaps — this is
  what produces a legible hierarchy rather than uniform mush.
- **Termination**, any of: left the domain · hit a hard mask · exceeded max length ·
  field went degenerate · **came within `snap_radius` of an existing trace** ·
  turned more than `max_curvature` · looped back on itself.
- Trace bidirectionally from each seed.

Output is deliberately still *raw* — messy is fine, S3 cleans it.

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
  `tunnel` flags. A schema proven against the entire planet, borrowed as convention only.
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
2. **Intersect** every pair of **same-layer** edges; insert a node at each crossing and
   **split both edges**. This is the step whose absence broke everything before.
   Cross-layer crossings are instead recorded and **clearance-checked**.
3. **Cleanup**, and this is where "satisfying" is won or lost:
   - fuse nodes closer than `min_node_dist`
   - delete stubs shorter than `min_edge_len`
   - collapse pairs of edges that are near-parallel and closer than `min_street_sep`
   - enforce `min_angle` between edges at a node (merge or nudge below it)
   - optionally prune dead ends, iteratively
4. **Validate:** every edge has exactly two node endpoints; no duplicate edges between the same
   node pair; no zero-length edges; **each layer is planar**; **all cross-layer crossings meet
   `min_clearance`**; every ramp connects exactly two distinct layers.
5. **Extract faces per layer** → these are the blocks (consumed by S7). Only ground-layer faces
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

At a node of degree *n*: trim each incident street end back by a radius derived from the widest
incident `streetWidth`, then build the junction surface joining the trimmed ends, matching
cross-section element boundaries across the junction where the element types agree (lane meets
lane, sidewalk meets sidewalk).

Known-hard cases to prototype rather than assume: skewed 3-way, degree ≥ 5, junctions between
very different widths, junctions on a grade. Roundabouts are a distinct construction, not a
parameter tweak.

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

### S8 — Lots

Subdivide blocks into buildable parcels, with artist control, plus **viability checks**: minimum
area, minimum street frontage, minimum width at the frontage, maximum aspect ratio, slope limit.
Non-viable parcels become courtyard, parking, planting or are merged with a neighbour.

⚠️ **Knowledge gap:** the rigorous treatment is **Vanegas et al. 2012, "Procedural Generation of
Parcels in Urban Modeling"**, which we do not have — acquire before building this. Also inspect
what viability logic `resources/citygen/unrealCitygen/otls/City_Layout.hda` already implements.

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

The stage API. Names follow CityEngine where they overlap — convention only, no dependency.

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
transitions (seam left open, §S6) · Voronoi graph generator (deferred, §S1).
