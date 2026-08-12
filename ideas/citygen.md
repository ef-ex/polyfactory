# CityGen — System Architecture

**Status:** design. Streets V1 implemented (see [`citygen_streets.md`](citygen_streets.md) §6b);
every other subsystem is still design only.
Branch `cityGen`. Started 2026-08-08. Revised after clarification rounds 1 and 2, and again
2026-08-09 (reference review + Subversion authoring study).

**This file owns:** the vision, the principles, and the contracts that span subsystems.
**Subsystem designs:** [`citygen_streets.md`](citygen_streets.md) — streets (first subsystem).
Terrain, vegetation, zoning, buildings — not yet written.

**Reference library:** `polyfactory/resources/citygen/README.md` — gitignored, local only.

---

## 1. The vision (Hannes, 2026-08-08)

A complete environment generation system: **terrain → vegetation → city (streets + buildings)**.
From a lone forest to a Manhattan-scale metropolis. A ~20-year ambition; first serious attempt.

> an entire environment with cities and forests, and I can click on a single window in a building
> and change its appearance — or a single tree, or a single stone on the ground.

**Instancing.** Generate a bounded asset set, instance aggressively. Every instance supports
**swap** (different variant) and **replace** (unique hand-made geometry).

### Confirmed parameters

| Question | Answer |
|---|---|
| Units | **Metric, metres** |
| Render target | **Offline film rendering.** No real-time engine target |
| Topology | **Cached.** Edits change parameters; topology change is explicit |
| Bridges / tunnels / overpasses | **Required in v1** |
| Rail | **Not v1** — roads first; rail systems are complex enough to be their own project |
| Future | Multi-level sci-fi — sky lanes, stacked streets (Coruscant). Schema must not preclude it |
| CityEngine | Inspiration and the most complete reference found. **Explicitly not a 1:1 rebuild** |

---

## 2. Art direction is the first principle

Stated plainly by Hannes and it outranks everything else in this document:

> In most cases having default values that the artist can change is better than hard-written values.
> It is very, very important that everything can be changed however the artist envisions it.

This is not a feature. It is a **rule that constrains every other decision**, so it is written once
here and referenced everywhere.

### 2.1 No constants — the override cascade

**Every generated value is a default, not a constant.** No magic numbers anywhere in the pipeline:
every threshold, width, angle, radius, spacing and cost is a named parameter with a default.

Resolution order for any value, **last wins**:

1. system default (in code)
2. global parameter on the generator
3. per-`land_use` / per-`street_class` preset
4. per-**region** override
5. per-element authored attribute
6. explicit entry in the **override layer** (Contract 2)

Every stage therefore reads *"use the authored value if present, otherwise compute one"* — never
*"compute"* alone. **Generated and authored values must stay distinguishable**, so artist values
live in the override layer keyed by element ID rather than being written into the same slot the
generator recomputes. Anything else silently eats the artist's work on the next cook.

### 2.2 Validation is advisory, never a wall

Generalised from Hannes' answer on invalid ramp grades. Every validation rule has a mode:

`block` · `warn` · `ignore`

with a sensible default and a **global "allow invalid" switch** that demotes every `block` to
`warn`. When the artist overrides, **the generator still generates** — and the warning is
**persisted** as an attribute/record on the offending element, not just printed to a console, so it
stays inspectable and can be visualised in the viewport.

The artist is allowed to build the physically wrong thing on purpose. They just get told.

### 2.3 Intervene at any stage — the authoring model

Added 2026-08-09 after studying **Introversion's Subversion** city generator, which Hannes singled
out for its user-side tooling. Catalogued in `resources/citygen/README.md` §4. The relevant sentence
from Chris Delay's dev diary, which is the whole design in one line:

> You can step in at any stage of development and add your own customisations, or you can just let
> everything generate itself randomly.

Its pipeline is height map → population density → city centres → highways → streets → blocks →
buildings → render, and **each stage is a button** with an editable input map in front of it. The
artist paints the height map (or generates it fractally), paints where the city will be dense, and
from there can either press "Generate All" and walk away, or stop after highways and hand-edit them
before the streets are grown. Nothing forces a choice between "fully procedural" and "hand-built".

**This is not a new principle — it is §2.1's override cascade expressed as *pipeline shape*, and it
is what our stage design already buys us.** Recording it because it names the acceptance criterion:

1. **Every stage is separately runnable and separately overridable.** Already true — S0…S8 are
   distinct HDAs with a documented schema between them ([`citygen_streets.md`](citygen_streets.md) §3).
2. **Every stage's *input* is a paintable map or an editable geometry**, not only a parameter set.
   Partly true — S0 masks are maps, but the tensor field is currently parameters on descriptor
   nodes. A `brush` field generator is already in the design and closes this.
3. **A hand edit at stage N survives regeneration of stages N+1…** — Contract 2.
4. **There is a one-button "generate everything" path** for when the artist does not want to author
   any of it. We do not have this yet; it is a thin wrapper over the existing chain, and worth
   shipping precisely because it makes the stage-wise path *optional* rather than mandatory.

Subversion's generator is itself an extension of **Parish & Müller 2001** — Delay names the paper as
his starting point — so it is the same lineage as ours, which is why its authoring model transfers
cleanly rather than being a different architecture's ergonomics.

---

## 3. Terminology: "biome" was overloaded — split it

Same *mechanism*, different domains.

| System | Name | Category attribute | Continuous drivers |
|---|---|---|---|
| Nature | **biome** | `biome` | temperature, precipitation, soil, slope, altitude |
| City | **zoning** | `land_use` | land value, distance to centre, accessibility, density |

- **`zoning`** — financial / commercial / industrial / residential / rural / civic. Drives street
  hierarchy, cross-section templates, lot sizes, building types, architectural style. Standard
  urban-planning vocabulary, so it reads correctly to anyone.
- **`district`** — a *named spatial region* ("Old Town"), which may contain a mix of zones.

**Shared mechanism, built once:** a *categorical region field* — continuous drivers resolve to a
category per location, each category carrying a rule set. `biome` and `zoning` are two
configurations of one system, not two systems.

---

## 4. Cross-subsystem contracts

Design these now; everything else is subsystem-local.

### Contract 1 — The **region** is the unit of identity, caching, locking and transfer

*Topology is cached* plus *I want to lock areas, and worst case copy-paste part of a city into
another city* collapse four problems into one concept.

A **region** owns: a **cached topology**, a **lock state** (`live` · `cached` · `locked`), and an
**ID prefix**.

| Requirement | Delivered by |
|---|---|
| Stable identity | topology cached ⇒ IDs stable **by construction** |
| Lock areas | a region flag; regeneration skips locked regions |
| Localised regeneration | invalidate one region, neighbours untouched |
| **Copy / paste city chunks** | the region *is* the clipboard unit |
| Geometry chunking | region = chunk (Contract 5) |

IDs are **hierarchical paths** — `city_A/region_07/block_03/lot_04/bldg/floor_02/win_11` — so paste
is a **prefix rewrite** with internal structure intact. That only works if IDs are relative from
the start. Within a region, elements are numbered by **canonical sort**, never cook order.

**How a region is defined — all of these, because art direction (§2):** `region_id` is just an
attribute, settable by any authoring path —
procedurally via expressions on IDs · painting an attribute on the street splines or points ·
viewport selection then assign · a dedicated region-selection tool (Contract 7).

**On paste, terrain behaviour is a choice, not a rule** — `paste_mode`:
- `terrain_adapts` — preserve the look 100%, terrain deforms to the pasted city
- `city_conforms` — the feel is close enough, the city re-drapes onto the new terrain

⚠️ **Boundary stitching remains the hard part.** A pasted region's streets must connect to the host
graph at the seam. v1: snap within a tolerance and **report every unstitched edge** (§2.2).

### Contract 2 — The override layer: an upstream node, committed to by a downstream write

Covers **both** instance overrides (swap/replace) and **attribute overrides** (§2.1) — one
mechanism.

An **override** is a sparse record keyed by element ID: swap variant · replace with unique
geometry · attribute value · transform delta · delete.

#### The edit-node design (Hannes' concept, adopted)

The artist edits from a *downstream* node, but the generator is *upstream*, and Houdini cannot feed
output backwards. Hannes' long-standing solution, adopted as the design:

1. The **edit node caches its input**. The artist edits against that cache and sees the result
   immediately — no full-city regeneration per tweak.
2. When the artist is done, the accumulated changes are **committed** into the **upstream override
   node**, which feeds the data stream (Contract 8).
3. After commit, the downstream edit node reverts to **pass-through**; its internal cache is live
   only while actually editing.

The commit is a **write** performed by Python on an explicit artist action, not a wire. The node
graph therefore stays acyclic — the feedback happens across two cooks, never inside one.

⚠️ **Five requirements this imposes. They are the "heavy lifting" Hannes anticipated:**

1. **Every element carries its ID *and* its origin all the way downstream.** Stamp a `source_node`
   attribute at generation time. This is the concrete answer to "identify in which layer or node
   the generation happened" — cheap, and everything else depends on it.
2. **Edits are expressed in schema terms, never geometry terms.** Dragging a vertex on finished road
   geometry must translate into *"move node X of the street graph"*. The edit node maps picked
   geometry → owning schema element. Possible only because of (1).
3. **Never write upstream during a cook.** Houdini will fight it — recursion and unstable cooks.
   Commit is an **explicit artist action** (button, or exiting the state), never automatic.
4. **Undo must be wrapped.** A commit changes several nodes at once; without a single undo block
   the artist gets a broken undo stack.
5. **Stale commits become orphans, not corruption.** If the generator's parameters changed since an
   edit was made, its target may no longer exist — report it (§2.2), never silently drop it.

⚠️ **Routing: not every edit belongs to the same upstream node.** Moving a *building* cannot be fed
back to the street generator — the building came from a lot, which came from a block, which came
from the graph. So each edit routes to **the nearest upstream node owning that element type**.
Hannes' own answer supplies the UI for this: the artist selects an element and is asked *what* they
want to edit — road network, street appearance, textures — and **that choice selects the commit
target.** The routing problem and the interaction design solve each other.

**Substrate: Solaris / USD**, which ships with Houdini. Given the offline-film target the mapping
is direct: prim paths **are** hierarchical stable IDs · variant sets **are** swap · layer opinions
**are** sparse non-destructive overrides · deactivate-and-author **is** replace · payloads handle
scale.

⚠️ **Not settled — prototype before committing.** `PointInstancer` is fast but **index-based**, and
indices shift when upstream counts change, reintroducing the identity problem it was meant to
solve. Instanceable prims carry stable paths but a much heavier scene graph. A third option is a
PointInstancer carrying a stable `elem_id` primvar. Test all three at realistic city scale.

### Contract 3 — Terrain ↔ city: two terrain nodes, no loop

Hannes' formulation, which is simpler than the staged-dependency framing:

```
terrain_base ──► city_graph ──► terrain_final ──► city_geometry
                    │              ▲
                    └── corridor mask + target elevation + terrain_op
```

One rule: the city **graph** reads `terrain_base`; the city **geometry** reads `terrain_final`.

- **`terrain_op` per segment**: `cut_fill` · `none` (bridge) · `excavate` (tunnel).
  Without it every bridge flattens the valley it exists to span.
- **The street owns the cut/fill**, including embankment width — an attribute with a default that
  the artist can change (§2.1).

### Contract 4 — City → vegetation masks

The city publishes named mask layers at an agreed resolution — `road`, `sidewalk`, `lot`,
`building_footprint`, `park` — consumed by vegetation/scatter to suppress or modulate.

### Contract 5 — Chunking is spatial. **Shots do not drive generation.**

**Correction — the earlier "chunk by shot" framing was wrong.** The city is an environment that
exists in its own right; you must be able to go anywhere in it. Shots come *after* the city, and
can never drive its generation.

What is actually wanted is **render-time visibility control**, not shot-scoped generation:

- Generation stays **global and monolithic** through the graph stages (a full city graph is
  ~10⁴–10⁵ edges — trivial).
- Geometry is chunked **spatially** — by block, region and assembly.
- Those chunks become **USD groups/assemblies that can be deactivated per group**, which is cheap
  and native.
- A shot then simply *deactivates what it does not need*. That is a consumer of the structure, not
  an input to it.

### Contract 6 — Networks are layered and typed

Bridges break global planarity: two edges crossing at an overpass must **not** share a node.

- Every edge carries an integer **`layer`** — negative underground, 0 ground, positive elevated.
  **Planarisation is per layer.** Cross-layer crossings produce no node.
- **This is how OpenStreetMap models the real world** (`layer` + `bridge`/`tunnel`) — a schema
  proven planet-wide, and an open convention.
- Every edge carries **`network_type`**: `road · rail · pedestrian · sky_lane · canal`.
  **v1 implements `road` only**; the attribute exists so rail and sky lanes are configuration
  later, not a refactor.

Two attributes now are the entire down-payment on the sci-fi future.

### Contract 7 — A reusable Python state library (new)

Requirement: states must **not be bound to one node**. The same street-editing state should be
available on the street-network node and, later, on a "city edit" node placed after everything is
generated. A **library of states**, loaded according to what the artist wants to do.

**Houdini supports this natively — verified:**

- **Nodeless viewer states.** States not tied to any node type, installed in a `viewer_states/`
  directory and auto-registered at startup, using HOM to inspect and edit arbitrary nodes and
  geometry. Launched with `hou.SceneViewer.setCurrentState()` from a shelf tool or menu.
- **`hou.ViewerStateTemplate(name, label, category)`** with **`bindFactory(callable)`** — the
  factory receives `(state_name, SceneViewer)`. An optional **`contexts`** parameter lets **one
  state implementation serve multiple node types**, and the state stays active as the user moves
  between compatible contexts.
- Bindings available: `bindHandle` / `bindHandleStatic`, `bindGeometrySelector`,
  `bindObjectSelector`, `bindMenu`, `bindParameter`, `bindIcon`.

**Design: states bind to the *schema*, not to a node.** State logic lives in shared library modules
operating on the documented attribute contract (street graph, blocks, lots). Thin registrations
expose each state as a nodeless tool *and* as a node-bound state on the relevant HDAs.
**This is the schema-as-API design paying off a third time** — a state that edits "the street
graph" works on anything that outputs the street-graph schema.

States are also **the UI for the override layer** (Contract 2) — which is precisely why that layer
has to be external storage.

**Target resolution — resolved.** Not a pointer parameter and not an upstream search: the artist
**selects an element**, and is offered the choice of *what* to edit — road network · street
appearance · textures. The selected element carries `elem_id` and `source_node` (Contract 2
requirement 1), so the choice plus the stamp resolve both the data source and the commit target.

**SOP versus LOP — resolved: stay in SOPs.** The whole USD stage can be authored from SOPs via
attributes, instancers included, so there is **one state family, not two**. This also favours the
primvar-keyed instancing option in Contract 2, since a stable `elem_id` authored on SOP points
travels into USD intact. ⚠️ Still prototype instancer authoring and per-instance override at real
city scale before treating it as settled.

**Scheduling — states are v2.** v1 gets the nodes working with everything exposed through
parameters. That will be unwieldy but entirely testable, and it keeps viewport interaction from
blocking the generator. **The schema must still be designed to support states now** — `elem_id` and
`source_node` are v1 requirements even though nothing interactive consumes them yet.

⚠️ **Verify:** package-local `viewer_states/` under `$POLYFACTORY`. The docs name
`$HOUDINI_USER_PREF_DIR/viewer_states/`; confirm the directory is also scanned from `HOUDINI_PATH`
entries the way `otls/` and `toolbar/` are, before relying on it for distribution.

### Contract 8 — Two wired streams; Houdini attributes are the data format

**No JSON, no external file formats anywhere in the pipeline.** Houdini's attribute system is more
efficient and every system in Houdini already reads it — no parser, no schema drift, no second
format to keep in sync, and it is inspectable in the geometry spreadsheet for free. Where a
text-diffable file is genuinely wanted, save geometry as **`.geo`**, which is already JSON-based.
Nested or non-per-element values go in **detail dictionary attributes**.

Every node in the pipeline takes and emits **two wired streams**:

| Stream | Contents | Character |
|---|---|---|
| **data** | street graph, blocks, lots, cross-section templates, zoning, parameters, IDs | small, cheap, **authoritative** |
| **geometry** | the actual city — road surfaces, buildings, instanced elements | large, expensive, **derived** |

A node passes through whatever it does not touch.

**Invariant: the data stream is authoritative; the geometry stream is always derivable from it.**
Geometry can therefore be discarded and rebuilt at will — which is exactly what makes region
caching (Contract 1) and spatial chunking (Contract 5) work at all.

**Why two wires rather than one packed stream:** the two have very different sizes and cook costs.
Reading a value out of the data stream must never force a heavy geometry re-cook. One wire carrying
packed sub-geometry is tidier on screen but couples the cook costs and imposes unpack/repack
discipline everywhere — not worth it.

#### Overrides ride *inside* the data stream

**Not a third wire, and not an `op:` reference.** An earlier draft proposed referencing a detached
node from inside the generator. That would not actually have deadlocked — the detached node has no
inputs, it is not downstream, and the edit node *writes* into it with Python rather than wiring to
it, and a write is not a cook dependency — but it is still the wrong design, because a hidden
reference makes the network impossible to reason about.

The clean answer needs nothing new: **overrides are just more data, so they travel in the data
stream.**

```
override_node ──┐
                ├──► data stream ──► S1 ─► S2 ─► S3 ─► … ─► edit node
terrain/params ─┘         (every stage passes it through and reads what is addressed to it)
```

- An **override node sits upstream** and merges its records into the data stream at the top.
- Records are keyed by `elem_id`, so **each stage picks out the ones addressed to it** and ignores
  the rest.
- Every node already forwards the data stream, so this costs **no extra input and no extra wire**.
- The dependency is a visible, ordinary Houdini wire. No hidden references, no stale cooks.

**Committing an edit is a write, not a wire.** The downstream edit node writes its accumulated
changes into the **upstream override node** (Python, on an explicit artist action). At cook time
the graph stays strictly acyclic — the feedback exists in *time*, across two cooks, never within
one. This is exactly why Contract 2 requirement 3 forbids writing upstream during a cook.

Multiple override sources — several edit sessions, or hand-authored overrides — simply merge into
the same stream.

### Deliberately NOT designed yet

Facade/building grammar internals · vegetation ecology rules · terrain authoring tools · traffic and
pedestrian simulation · LOD · shading strategy · UI beyond the state library. Each gets its own
subsystem doc when its turn comes.

---

## 4b. APEX — assessed 2026-08-08. Real fit, but not yet

APEX did not exist when this was last thought about. Verified from SideFX docs:

- **`APEX Invoke Graph` SOP is explicitly general-purpose, not animation-specific.** It executes
  arbitrary APEX graphs on geometry, binds dictionary attributes and named packed primitives as
  inputs, outputs both dictionaries and geometry, and supports **partial evaluation** for
  performance, with ignore/warn/abort error modes.
- **`APEX Script` SOP builds graphs procedurally** from code snippets, with `BindInput()` and an
  `@subgraph` decorator for reusable functions.
- **APEX graphs are data** — stored as geometry, so they can be generated, modified and fused
  procedurally. Houdini 21 added procedural graph fusion.

### Where it genuinely fits

**Buildings, as a rule-graph engine — the strong fit.** A shape grammar is a *rule program*. An
APEX graph is a program stored as geometry that can be built per element from zoning and style
parameters, then invoked. That is architecturally what CityEngine does with CGA, and what
CityGenAgent (2026) does by having an LLM emit "block programs" and "building programs". Since
`cityengine_for_houdini` is ruled out, **APEX is the closest native equivalent to CGA we have** —
and `@subgraph` gives the composable rule-fragment library that grammars need.

**Traffic and pedestrians, later.** APEX's native home is rigging and animation. When the splines
start driving traffic and crowds, APEX is the obvious vehicle.

**Per-element variation at scale.** Generating a small graph per element, with partial evaluation,
beats one enormous SOP network full of switches.

### Where it is the wrong tool

The street graph itself, field generation, tracing, planarisation, cross-section sweeping — all
plain SOPs and VEX. APEX adds nothing there, and a JSON list beats a graph for a cross-section
template.

### Verdict

**Not for v1 streets. Revisit at the buildings subsystem, and again at traffic.**
⚠️ Honest risk: the documented APEX ecosystem is heavily rigging-centric. Using it as a
general-purpose rule-graph engine is off the beaten path — expect thin examples and rough edges,
and prototype before committing the building subsystem to it.

---

## 5. SideFX Labs policy — revised 2026-08-08

Hannes' actual position, which is more nuanced than the earlier ruling:

> So far I did not like the Labs tools too much. They are often too simple, too cumbersome or too
> restrictive. I always look at them as a very good starting point but not the final polished thing.
> We can even copy the Labs tool to make it our own but it needs to be further polished. Art
> direction is key and for me there is a lack in the Labs tools there.

**Policy: Labs is a reference implementation and a starting point. It is never a shipped
dependency.**

| Use | Allowed |
|---|---|
| Study a Labs tool to learn the approach | ✅ always |
| Fork / reimplement its approach as our own polished HDA | ✅ — **must add art-direction controls (§2)** |
| Open a Labs node ad hoc to compare results | ✅ |
| Ship a tool that depends on a Labs node at runtime | ❌ **never** |

This supersedes the earlier "Labs permitted in vegetation" ruling. Labs biome tools
(`Labs Biome Plant Scatter` — **Alpha** — `Labs Biome Attributes to Terrain`,
`Labs Biome Attributes Evolve`, `Labs Biome Configure Multibiomes`, Houdini 20.5+) are the
**starting point** for vegetation, not the destination. The recurring complaint — too restrictive,
too little art direction — is exactly what §2 exists to fix.

⚠️ **Verify the SideFX Labs licence before copying node internals** into anything we ship or
distribute. Studying and reimplementing is unambiguous; lifting internals may not be. Unchecked.

---

## 6. Roadmap

Each subsystem must be usable on its own before the next begins.

1. **Streets** — in design, [`citygen_streets.md`](citygen_streets.md)
2. **Blocks & lots** — `recursive_obb` and `offset` (European perimeter blocks) are both v1 and
   fully specified from Parish 2001 + CityEngine; only `skeleton` still needs Vanegas et al. 2012
   (not acquired). See [`citygen_streets.md`](citygen_streets.md) §S8
3. **Zoning** — §3; shares its mechanism with vegetation biomes
4. **Buildings** — largest unknown, written from scratch
5. **Terrain integration** — Contract 3
6. **Vegetation / scatter** — Contract 4, Labs as starting point only
7. **Art-direction tooling** — Contracts 1, 2 and 7 made usable: selection, region locking,
   copy/paste, the state library, override inspection and orphan reporting

## 7. Open, system-level

**Resolved so far:** units · render target · topology caching · planar-per-layer · terrain chain ·
identity via regions · Labs policy · state target resolution · SOP-only (no LOP state family) ·
states deferred to v2 · data format is Houdini attributes, not JSON · pier placement (just work,
plus the standard validation rule).

⛔ **One item DOES block v1 streets and it is not listed here:** the multi-leg junction —
[`citygen_streets.md`](citygen_streets.md) §S5a, tracked in that document's §9. Not built, live on
C_radial, present in both the old and new HDA chains.

Still open at system level — none of these block v1 streets:

1. **Instancing substrate** — PointInstancer vs instanceable prims vs primvar-keyed `elem_id`.
   The SOP-authoring decision favours primvar-keyed, but **prototype at real city scale** before
   committing; per-instance override is the specific thing to stress.
2. **Boundary stitching on region paste** — Contract 1. The genuinely hard part of copy/paste.
3. **SideFX Labs licence** for copying node internals into anything distributed — §5. Unchecked.
4. Verify `viewer_states/` is scanned from `HOUDINI_PATH` for package-local distribution — needed
   only when states are built (v2).
5. **Check SideFX Project Vitruvius release status.** Cannot be a dependency; worth studying.
6. **APEX for the building subsystem** — prototype before committing (§4b).
