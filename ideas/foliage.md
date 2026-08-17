# Foliage — Tree Growth Solver Design

**Status:** design only. Research complete (2026-08-15/16); no build started. Build is parked
until citygen ships — this document exists so the design survives the wait.
**This file owns:** the foliage system vision and the tree growth solver spec.
**It does not own:** meshing/LOD (researched in the reference library §6b; spec written when the
solver exists), ecosystem simulation (Labs Biomes covers v1), or citygen's vegetation *placement*
subsystem — [`citygen.md`](citygen.md) owns how vegetation integrates into cities and will consume
this system.
**Reference library:** `polyfactory/resources/foliage/README.md` — gitignored, local only. All
literature, tool research, and the reconstructed Opara system live there; this file does not
restate it.

---

## 1. Vision and goals (Hannes, 2026-08-15)

> I am after a foliage generator where people can design foliage which can be saved as a template,
> and where the system can spawn the seeds on a terrain to grow them by rules (Labs Biomes should
> help there). But I would also love to be able to grow trees based on attributes.

Three goals, in priority order:

| # | Goal | This spec's answer |
|---|---|---|
| G1 | Grow trees from attributes | The solver core (§4–§6): per-seed attributes steer growth |
| G2 | Design foliage → save as template | A species = a parameter preset (§7.4); seeds reference it |
| G3 | Spawn seeds on terrain, grow by rules | Labs Biomes emits seed points + climate attributes; the solver consumes them (§8.1). No custom ecosystem sim in v1 |

**Non-goals for v1:** meshing (solver outputs a skeleton contract, §8.2 — the meshing stage is its
own future spec), LOD/impostor baking, wind/rigging (attributes reserved, not implemented),
grass/groundcover (different scale, different tool).

**Design anchor.** The solver is a reconstruction-and-modernisation of Anastasia Opara's EA
`aopara_treegenerator` (reference library §2.3–§2.4: her sources, rules, full parameter surface,
demo values, and demonstrated behaviours). Where this spec makes a choice her interface doesn't
document, the tiebreak order is: The Grove's documented mechanism → Pałubicki 2009 → botany
sources (Smith 2014, UT W227).

---

## 2. Principles

1. **Art direction is the cardinal rule** — adopted from [`citygen.md`](citygen.md) §2 verbatim,
   including the override cascade (§2.1: every generated value is a default, never a constant;
   per-species preset → per-seed attribute → override layer) and advisory validation (§2.2:
   `block`/`warn`/`ignore`, warnings persisted as attributes). Not restated here; that file owns it.
2. **This is an end-user tool**, not a helper — the art-direction bar is at maximum. The test:
   an artist who didn't build it must get the tree they want from the controls alone.
3. **Procedural-modeling constitution applies:** VEX (OpenCL escape hatch) for all per-element
   work, never Python; native nodes before custom code (VDB SDF, pcfind, Scatter); normalize in,
   canonical out.
4. **Biology is the rulebook, not the renderer.** Every mechanism must trace to a documented
   principle (her nine rules, reference library §2.3) — that traceability is what made her trees
   believable and it is the acceptance checklist (§11).
5. **Determinism.** Same seeds + same parameters = same forest, regardless of cook count or
   point order (§9).

---

## 3. Prior art in one paragraph

Her system (and therefore ours) is a **yearly-cycle bud automaton**: buds gather light, income
becomes vigor, vigor is allocated by hormone-weighted competition, winning buds extend the
skeleton, losers go dormant or die, branches that can't pay their energy cost self-prune, and
thickness follows from the surviving flow. It is The Grove's model rebuilt on botany primary
sources; Pałubicki et al. 2009 is the same mechanism formalised with equations. Everything below
is a Houdini-native expression of that loop. (Full lineage: reference library §2 and §5.)

---

## 4. Architecture

### 4.1 The node

**`pf_treegen`** (HDA, `polyfactory/otls/`, matching the `pf_` convention). One node, one job:
seeds in, grown skeletons out. Growth animation falls out of the solver's frame dependence.

| Input | Contents | Contract |
|---|---|---|
| 0 | **Seed points** | Any point cloud. Recognised attributes: §8.1. Missing attributes get defaults (normalize in — bare points must work) |
| 1 | **Environment** (optional) | Any geometry. It has exactly ONE role in the simulation: **light occluder** in the exposure pass (§6.2). Avoidance is *emergent* (§6.7) — there is no steering mechanism to configure. Internally an SDF is built once per cook (native `vdbfrompolygons`), used only as ray-occlusion acceleration and for the non-penetration guard |

*(Design revision 2026-08-16, after Hannes' recollection of the talk: her HDA's obstacle input and
light blocking were the same thing — avoidance came free once the survival rules were in place.
An earlier draft had separate obstacle/light-blocker inputs and an SDF deflection term; both cut.)*

Output 0: skeleton curves + attribute contract (§8.2), in **metres, +Y up, world space** (seeds
are already placed in the world; the solver grows in place — canonical space is the world the
seeds came in).

### 4.2 Internal structure

A **SOP Solver** whose substep = one growth tick. `Years` × `Substeps per Year` ticks total;
each stage inside the solver is one wrangle (or OpenCL kernel later), in the order of §6. All
tunables are parameters; nothing hardcoded. The solver is the only stateful element.

### 4.3 Species = template (G2)

A **species recipe is exactly the parameter set of §7** — nothing more. Saved/loaded as named
presets (JSON on disk, standard parm-preset machinery). Seeds select a species via `species`
attribute; per-seed attributes override individual recipe values per the cascade. This is the
whole template system: no second file format, no separate authoring tool.

---

## 5. Data model

Skeleton = polylines. **Points are nodes** (actual or potential bud sites), **prims are
internode chains** per year-shoot. All attributes prefixed `tg_` to keep the namespace clean
through downstream tools.

### 5.1 Point attributes (state)

| Attribute | Type | Meaning |
|---|---|---|
| `tg_id` | int | Stable unique id (never reused; rng key, §9) |
| `tg_parent` | int | Parent node id (−1 at root) |
| `tg_order` | int | Branch order: 0 = mainstem, +1 per lateral fork |
| `tg_age` | int | Years since this node was created |
| `tg_budtype` | int | 0 none · 1 terminal · 2 lateral · 3 dormant · 4 epicormic-candidate |
| `tg_state` | int | 0 growing · 1 dormant · 2 dead · 3 shed (stub kept) |
| `tg_dir` | vector | Current growth direction (unit) |
| `tg_light` | float | Exposure this tick, 0–1 (§6.2) |
| `tg_Q` | float | Accumulated light of the subtree above (basipetal pass, §6.3) |
| `tg_vigor` | float | Vigor allocated this tick (acropetal pass, §6.3) |
| `tg_energy` | float | Running branch energy balance (§6.6) |
| `tg_deficit` | int | Consecutive deficit years (prune trigger) |
| `tg_radius` | float | Secondary growth (pipe model, §6.8) |
| `tg_species` | int | Recipe index (copied from seed) |
| `tg_seed` | int | Originating seed point id (forest bookkeeping) |

### 5.2 Prim / detail

Prims: `tg_order`, `tg_year` (the year this shoot grew — the meshing stage's ring/UV seed),
`tg_scar` (set where a pruned branch left a scar, her "pruned branches leave scar" toggle).
Detail: `tg_year_current`, rng root, per-species recipe cache.

---

## 6. The growth loop (one tick)

Stage order matters; each stage reads the previous one's output. Formulas are normative;
implementation (wrangle vs OpenCL) is not.

### 6.0 Initialise (first tick only)

Each seed point becomes a root node: `tg_dir` = seed `N` if present, else +Y (**G1: the
attribute-steered growth she demoed with a Point SOP** — reference library §2.4, frame 4).
`tg_budtype` = terminal. Missing seed attributes → species defaults (normalize in).

### 6.1 Bud inventory

Collect live buds: terminals, laterals within their `Bud Life` window, dormant buds (age <
`Bud Life`), plus this year's `Spontaneous Bud Chance` rolls on old nodes and epicormic
candidates (§6.9). Everything downstream operates on this bud list.

### 6.2 Light exposure

Per bud: hemisphere sample around `tg_dir` — `Light Samples` rays (cost knob) against
(a) the tree's own leaf proxy (point cloud around live buds, radius = `Leaf Radius`),
(b) sibling trees' proxies within `Competition Radius` (forest-level shading — Deussen 1998
behaviour for free), (c) input-2 blocker geometry. `tg_light` = unoccluded fraction, shaped by
the `Light Response` ramp (artist shape control).
Mutual shading between neighbouring trees is the **same mechanism** — crowns competing for the
same light naturally stop where they meet, so **crown shyness and tree–tree avoidance are
emergent**, not features (test T9; PlantArchitect demonstrates crown shyness from exactly this
model class).
*Her documented iteration:* she replaced a point-cloud occlusion test with rays toward leaves
(reference library §2.3 wishlist) — we keep **both**: `pcfind` density mode as the cheap
preview path, rays as the quality path. One toggle, same attribute out.

### 6.3 Vigor: gather down, allocate up (the hormone core)

Basipetal pass: `tg_Q` = own `tg_light · LeafArea` + Σ children's `tg_Q`.
Acropetal pass, at every fork (Borchert–Honda, Pałubicki 2009; λ = **Apical Dominance**):

```
v_main    = v · λ·Q_main    / (λ·Q_main + (1−λ)·ΣQ_lateral)
v_lateral = v − v_main      (split among laterals ∝ their Q)
```

λ > 0.5 → excurrent/pyramidal (pine); λ < 0.5 → decurrent/spreading (oak) — this single knob is
her research note 5 and must reproduce it (§11 test T2). **Mainstem Growth Dominance** applies a
second λ used only at order-0 forks; **Mainstem Suppresses Lateral** toggles it.

### 6.4 Auxin suppression

Active terminals suppress lateral buds within `Suppression Distance` (along-branch metres,
decaying linearly). Suppressed buds skip §6.5 this tick but stay alive (dormancy clock running).
Terminal death → suppression vanishes next tick → nearest lateral inherits (her rule 6, the
"sudden direction change" signature — must be visible in output, test T3).

### 6.5 Bud fate

Per bud, one roll (id-keyed rng):

| Condition | Outcome |
|---|---|
| `tg_vigor` ≥ `Flush Threshold` and rng < `Bud Growth Chance` | **Flush** → §6.6 |
| below threshold, dormant time < `Bud Life` | stay dormant |
| dormant time ≥ `Bud Life` | bud dies |
| terminal flush and rng < `Codominant Bud Chance` (cap `Max Codominant Stems`) | fork into equal codominant terminals |

### 6.6 Shoot construction + energy ledger

A flushing bud appends `Node Count` internodes of `Internode Length` (both scaled by
`tg_vigor` — vigorous shoots are longer, weak ones stunted). New nodes get lateral buds by
**phyllotaxy**: `alternate` (one bud/node, golden-angle rotation) or `opposite` (two buds/node,
90° pairs) — species switch, straight from W227/her rule 9. Lateral departure = `Branch Angle`
± variance.

Ledger per branch: income Σ(`tg_light` · LeafArea) − costs (maintenance ∝ live volume ·
**Energy Consumption** + growth cost per new internode). Negative year → `tg_deficit++`, else
reset. `tg_deficit` > `Deficit Tolerance` → branch dies (her rule 1: shaded twigs shed, bare
inner branches — test T1). Dead branches: kept as stubs of `Dead Branch Leftover` length
(`tg_state` = shed), scar attribute if enabled.

### 6.7 Direction integrator

For each new internode, starting from parent `tg_dir`:

```
d ← normalize( d
    + w_grav  · (+Y)                    // Gravitropism (negative geotropism = up)
    + w_photo · brightest-sample dir    // Phototropism (from §6.2 samples)
    + w_irr   · rng unit vector         // Direction Irregularity (Grove's Random Heading/Pitch)
    + w_weight· sag(accumulated mass)   // her rule 7 — branches bend under weight, order>0
    + w_seedN · seed N steering         // decays over `Seed Steer Years`
)
```

**Obstacles are not steered around — avoidance must emerge.** The environment's only influence
is shade: an object blocks light → buds facing it starve → those paths die or stay dormant, while
phototropism (`w_photo`, above) pulls the survivors toward the light that remains. The chain
*shade → energy deficit → death + light-seeking* is the entire avoidance mechanism, exactly as
in her talk ("got this for free once the rules were in place"). The direction integrator has
**no obstacle term**.
The single geometric rule is the **non-penetration guard**: if a new internode's endpoint would
land inside environment geometry (SDF < `Margin`), the internode is not placed — the bud waits
in shade and the energy ledger decides its fate. This is a physical impossibility check (film
close-ups must not show wood inside walls), not steering; it has no strength knob.

### 6.8 Secondary growth

Leaf-bearing tips set `tg_radius = Tip Radius`; every node below:
`r = ( Σ r_child^n )^(1/n)` with `n` = **Pipe Exponent** (default 2 ≈ da Vinci area
preservation; expose 1.8–3). Radius never shrinks year-over-year. `tg_year` on prims preserves
ring history for the future meshing/bark stage.

### 6.9 Shadowed-branch shoot-out (epicormic)

Her SHADOWED BRANCH section: if a shaded branch (`tg_light` < `Shade Threshold`) is allowed
(`Allow Shoot Out` ✓, branch age ≥ `Allowed Age`), dormant/adventitious buds on old wood may
flush — the water-sprout response from Smith 2014. Off by default, as in her demo.

---

## 7. Parameter interface

Her sections, kept — they are a proven artist-facing grouping — with three additions (LIGHT,
OBSTACLES, OUTPUT). Defaults = her demo values where recovered (reference library §2.4); the
rest from The Grove's documented ranges. Every parameter is a species-recipe member unless
marked *(instance)*.

| Section | Parameters (default) |
|---|---|
| TREE CONTROLS | Years (6) · Substeps per Year (1) · Random Seed *(instance)* · Preview toggle · Human Scale Reference |
| BRANCHES | Node Count (5) · Internode Length (0.05 m) · Branch Angle (50°) · Branch Weight (0.4) · Direction Irregularity (0.5) · Dead Branch Leftover (2) · Pruned-branches-leave-scar (off) · Phyllotaxy (alternate) |
| HORMONES | Energy Consumption (1.0) · Gravitropism (0.5) · Apical Dominance (0.6) · Mainstem Growth Dominance (0.357) · Mainstem Suppresses Lateral (off) · Suppression Distance |
| BUDS | Bud Growth Chance (0.8) · Bud Life (4 y) · Spontaneous Bud Chance (0.05) · Flush Threshold |
| CODOMINANCE | Codominant Bud Chance (0.4) · Max Codominant Stems (2) |
| PRUNING | Deficit Tolerance (1 y) · Pruning Strength (0.3) — scales how aggressively §6.6 sheds |
| SHADOWED BRANCH | Allow Shoot Out (off) · Allowed Age (0) · Shade Threshold |
| LIGHT *(new)* | Mode (pcfind preview / ray quality) · Light Samples (cost) · Leaf Radius · Competition Radius · Light Response ramp (shape) |
| ENVIRONMENT *(new)* | Voxel Size (occlusion-accel cost) · Margin (non-penetration guard; no strength knob — see §6.7) |
| OUTPUT *(new)* | Tip Radius · Pipe Exponent (2.0) · emit leaf-proxy points toggle |

Notes. (1) Shape *and* cost controls per the tool-design skill: ramps for light response and
vigor→length mapping; `Light Samples`/`Voxel Size` for cost. (2) Her "(Dummy) Pruning Radius"
appears to be a demo/debug control — not carried over; interactive pruning (The Grove's
signature *Prune* tool) is deferred to the open questions. (3) Species examples ship as
presets: at minimum *pine* (λ 0.8, opposite of *oak* λ 0.35) to prove G2 on day one.

---

## 8. Attribute I/O contract

### 8.1 Seed attributes recognised (all optional — bare points must grow)

| Attribute | Effect |
|---|---|
| `N` | Initial growth direction (§6.0) — the attribute-steering demo behaviour |
| `species` | Recipe selection (§4.3) |
| `tg_age_offset` | Pre-aged trees (forest age variation without cook-count changes) |
| `tg_vigor_scale` | Site quality multiplier — **this is the Labs Biomes join**: map soil/precipitation/temperature suitability to one scalar in v1 |
| `pscale` | Overall size multiplier |
| any recipe parameter as `tg_ovr_<name>` | Per-seed override, cascade level 5 |

Labs Biomes → `pf_treegen` is therefore one small wrangle mapping biome attributes to
`tg_vigor_scale` + `species` — G3 without building an ecosystem simulator.

### 8.2 Output contract (what the future meshing spec may rely on)

Polyline skeleton, metres, +Y up, world space. Guaranteed: `tg_id`, `tg_parent`, `tg_order`,
`tg_age`, `tg_radius`, `tg_state` (incl. shed stubs), `tg_species`, `tg_seed`, `v` (growth
velocity, for motion blur — see §13.2) on points;
`tg_year`, `tg_scar` on prims; optional leaf-proxy points (position, orientation, area) on a
second output stream. Junction geometry, UVs, and quad topology are **explicitly downstream**
(reference library §6b owns that research — sweep limbs, purpose-built junctions, guided
remesh only at the root flare).

---

## 9. Determinism

Every stochastic decision keys its rng on `(tg_id, year, stage)` — never on point number, cook
count, or time. Consequences: identical re-cooks bit-match; adding a tree to a forest changes
nothing about its neighbours; scrubbing the timeline is stable. This is a hard requirement
(test T6), learned from citygen: id-keyed randomness or the forest "boils" on every edit.

## 10. Performance envelope

Targets, not promises: single hero tree (≈ 6–40 years, 10k–100k nodes) interactive per year-tick
in VEX; a 500-tree hillside overnight-cacheable. Escalation path if VEX saturates: compile
blocks → OpenCL for §6.2/§6.3 (both are parallel per-element passes). Environment SDF built once
per cook, not per tick. Light is the budget hog — that is why `Light Samples` and pcfind-preview
mode are artist-facing (§7).

### 10.1 Forest strategy — unique sim vs instancing

Growing every tree in a forest uniquely (full mutual shading) is the *most correct* mode and the
most expensive. Both must exist; instancing is the default (matching citygen's
instance-aggressively principle):

| Tier | What | When |
|---|---|---|
| A — **Variant library + instancing** (default) | Per species, grow a small set of variants under representative conditions (open-grown / edge / closed-canopy / N-suppressed), instance via the Biomes scatter, pick variant by local context attributes | Forests, backgrounds — render-cheap, memory-cheap |
| B — **Unique-forest sim** | All trees in one solver, mutual shading on (`Competition Radius`) — crown shyness, canopy gaps and edge asymmetry for free | Hero groves, close shots, when the interplay IS the shot. Overnight-cacheable |
| C — **Mix** | Tier-B hero cluster embedded in tier-A instances; hero trees see instanced neighbours as light occluders (their proxies feed input 1) | The practical film shot |

Tier A trees don't react to their actual neighbours (an instance is an instance); the variant
axis (which variant, rotation, `pscale`, `tg_age_offset`) is what sells non-uniformity. Tier C
is the escape hatch when an instance visibly should have reacted.

## 11. Validation & acceptance

Per the show-don't-tell rule: every claim gets a viewport repro, not a number.

| Test | Pass condition (observable in viewport) |
|---|---|
| T1 energy | Mature tree has bare inner branches / bare trunk, foliage shell at crown (her rule 1) |
| T2 dominance | λ sweep 0.2→0.9 morphs one recipe from spreading oak to pyramidal pine (her rule 5) |
| T3 succession | Deleting/killing a terminal mid-sim → nearest lateral takes over with a visible direction jog (her rule 6) |
| T4 obstacles | Box on input 1 reproduces her frame-5 demo: growth curves around, zero penetration — **purely emergently** (there is no steering parameter that could be tuned to fake it) |
| T5 steering | Seed `N = (1,−2,1)` reproduces her frame-4 demo |
| T6 determinism | Two cooks diff-identical; neighbour edit leaves a tree unchanged |
| T7 species | Pine + oak presets side by side from the same seed points read as different species at silhouette distance |
| T8 growth anim | Year-by-year playback reads as growth, not interpolation (buds→shoots→thickening) |
| T9 crown shyness | Two trees planted 2 m apart: crowns partition the space and stop where they meet, no interpenetrating canopies — emergent from mutual shading alone |

Optional scoring: ICTree perceptual metric on outputs (reference library §5.5). Side-by-side
against her recovered demo frames is the final look benchmark.

Build discipline (when the build starts, not now): houdini-dev-loop from the first node; nothing
is "done" until independently audited on the live build; milestone artifact for each M is a
growth-animation flipbook next to the reference.

## 12. Milestones

- **M1** Skeleton loop: seeds → light (pcfind mode) → vigor → flush → yearly extension. T6, T8.
- **M2** Hormones: apical dominance, suppression, succession, codominance. T2, T3.
- **M3** Economy: energy ledger, self-pruning, stubs/scars, secondary growth. T1.
- **M4** Environment: ray-mode light, obstacles, seed steering, neighbour competition. T4, T5.
- **M5** Species & templates: preset save/load, pine+oak, Biomes join wrangle. T7. → then the
  meshing spec gets written against §8.2.

## 13. Open questions

1. **Interactive pruning** — The Grove's most-loved tool is manual *Prune*. Cascade-compatible
   (an override-layer edit replayed onto the sim)? Deferred past M5, but the id scheme (§9) must
   not preclude replay.
2. **Substeps — RESOLVED 2026-08-16.** The question was only about growth *animation*: does a
   year's shoot appear by interpolating the finished geometry over the year's frames (cheap), or
   does the solver truly tick sub-year (expensive)? Decision: **interpolated playback is the
   default**, with two safeguards for render quality: (a) the solver always emits a **velocity
   attribute `v`** from growth rate, so motion blur works even though topology changes at flush
   moments (topology-varying geometry breaks subframe-sample blur; velocity-based blur does not);
   (b) `Substeps per Year` stays in the interface as the escalation path if interpolated growth
   reads as morphing rather than growing. Judge on the M1 flipbook.
3. **Leaf/foliage authoring** — leaves are a proxy for light+meshing here; actual leaf/twig
   *design* (the other half of G2) is not specced. Likely its own small tool feeding the meshing
   stage. The Natsura attribute-schema study (reference library §3.2b) should happen first.
4. **Wind/rig attributes** — Wētā's "rig during construction" idea says reserve per-node rig
   data now. What exactly does a Houdini wind setup want from us? Research when meshing is
   specced, not before.
5. **Her "(Dummy) Pruning Radius"** — if the talk ever clarifies what it did, reconcile §7
   note 2.
