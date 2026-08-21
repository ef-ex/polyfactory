# Rocks, Cliffs & Minerals — Formation-Based Generation Study

**Status:** research complete (2026-08-21), feasibility assessed, no design spec, no build.
Build is parked until citygen ships — this document exists so the findings and the argument
survive the wait.
**This file owns:** the vision, the feasibility verdict, and the terrain-integration architecture.
**It does not own:** the literature, tool audit, and geomorphology rulebook — those live in the
reference library at `polyfactory/resources/rocks/README.md` (gitignored, local only; this file
does not restate it). A solver design spec (`pf_rockgen` or similar) does not exist yet and
should be written here or in a sibling doc when design actually starts, following the
[`foliage.md`](foliage.md) pattern.

⚠️ **Parked.** Same rule as foliage/fabric/terrain-presets: research and design are a parallel
track; nothing here starts building before citygen ships.

---

## 1. Vision and question (Hannes, 2026-08-21)

> There are more rock generators out there than anything else, but most generate ok-ish results
> and none make me say "yes, that looks like the rocks in my garden." All the ones I know simply
> use noise, which can bring you pretty close but it is still a lot of work. What I am after is
> whether it is possible to simulate the formation of a rock or a mineral — they usually have
> geometric rules to my understanding, which makes me think this could be simulated. Maybe there
> is something similar to what we researched for trees, which is based on real-world growth.

## 2. The answer

**Yes — confirmed on both fronts.** Rock and mineral formation follows documented, quantified,
partly machine-readable geometric rules (full evidence in the reference library):

- **Rocks: "cut before carved."** Joint sets (2–4 planar fracture families from stress history)
  pre-cut the rock mass into polyhedral blocks; weathering only rounds the blocks the joints
  made; transport finishes the job. Noise never enters except as *measured* self-affine surface
  roughness. This is why noise generators plateau: noise cannot produce correlated planar face
  families, sharp dihedral edges, or a site where every boulder shares one fracture history.
- **Voronoi shatter is the wrong prior.** Natural 3D fragmentation statistically converges to
  cuboids (~orthogonal cuts), not Voronoi cells (Plato's Cube, PNAS 2020).
- **Minerals are the most rule-governed shapes in nature.** A crystal habit is a convex clip of
  half-spaces from symmetry-expanded Miller indices; the per-mineral face data is free for
  commercial use (Smorf), and habit prediction from raw crystallographic files is a ~50-line
  algorithm (BFDH). A believable quartz cluster/geode is a weekend, not a research project.
- **The tool audit confirmed the frustration:** every shipping rock generator is a noise stack
  (there is no SideFX Labs rock node at all); the realism ceiling is photogrammetry scans; the
  one direct academic prior art (Paris et al. 2020, implicit jointed blocks, code public) was
  never productized. The two strong CG lineages — statistical jointing and time-stepped
  weathering — were **never combined**. That gap is the tool.

## 3. Feasibility — is the simulation too heavy for an artist tool? No.

The formation processes converge to **geometric operators**, and the literature hands us those
operators directly; the physics-faithful codes are where the *rules* come from, not what runs
when an artist drags a slider.

| Stage | What actually executes | Cost |
|---|---|---|
| Joint set generation | Sample planes from Fisher + lognormal distributions | Milliseconds |
| Block extraction | Cut an SDF by dozens of planes | Seconds (native VDB/boolean) |
| Cliff assembly | Per-layer retreat + remove unsupported blocks | Cheap geometry logic |
| Weathering | Level-set erosion weighted by curvature/exposure + shell offsets | The "sim" — VDB offset + curvature flow, GPU-friendly; near-interactive on 2007 hardware (Beardall) |
| Rounding | Corner-chip boolean loop; VDB Smooth SDF mean-curvature mode | Seconds |
| Talus | Bullet RBD settling of the generator's own blocks | Standard RBD wait times |
| Surface detail | fBm displacement with measured spectra (H≈0.8, JRC-calibrated) | Same cost as today's noise |
| Age dressing | Attribute bookkeeping (every face has a birthday) | Free |

Estimate: single boulder in seconds, cliff section in minutes — comparable to a Gaea erosion
pass or an RBD fracture cook, both of which artists already accept. Blocks are independent, so
it parallelizes and LODs naturally. The genuinely heavy methods (phase field, kinetic Monte
Carlo, DEM, reaction–diffusion) appear only as offline rule-mining references or optional
upgrade passes (e.g. a CA pass for hopper crystals/frost), never as the core runtime.
**Caveat:** these are engineering estimates from what the papers report, not profiled numbers.

**The real risk is control, not compute** — same lesson as trees. Three mitigations, all with
precedent:
1. Most stages have a **one-shot form** ("rounding 0–1" = a curvature-flow amount; "age" = an
   erosion distance) — scrub a value, don't babysit a timeline. The published durability-graph
   interface (Jones 2010) is the artist-parameterization blueprint.
2. **Stage-modular with geometry at every seam** — artists can replace the block lattice,
   hand-place hero blocks, or paint the strata field; downstream stages don't care. This is the
   citygen override-cascade philosophy ([`citygen.md`](citygen.md) §2) applying cleanly.
3. Deterministic geometry ops → caching and per-stage freezing work.

**De-risk step when this unparks** (show-don't-tell, per standing practice): a 1–2 day Houdini
prototype — joint-cut a block, run VDB curvature weathering, drop the talus — and judge
"garden-rock" quality in the viewport before any tool-building.

## 4. Terrain integration — the natural habitat, not an add-on

The strongest research lineage was built for exactly this (Paris 2019 amplifies imported
heightfields with volumetric cliffs/hoodoos/arches; Paris 2020 replicates jointed blocks over
the vertical parts of a terrain). Division of labor:

- **Heightfield owns the macro landform** — Houdini terrain tools / the Gaea-style preset layer
  ([`terrain_presets.md`](terrain_presets.md)) decide relief, ridges, drainage. Unchanged.
- **The rock system amplifies masked zones.** Slope/curvature masks select steep and rocky
  regions; only those convert to SDF and run the formation chain, then merge back. Overhangs,
  ledge-and-slope profiles, undercuts, hoodoos become possible exactly where heightfields fail.
  Only masked zones go volumetric, so the §3 performance story holds at landscape scale.
- **World-space fields are the glue and the payoff.** One stratigraphy field + one joint-set
  field over the whole landscape → the cliff face, the hilltop tor, and the valley boulders all
  share lithology and fracture orientation (**site coherence** — impossible with scans or
  i.i.d. noise rocks). Downstream for free: boulder-field density = inverse joint density;
  talus below a cliff = that cliff's own blocks, fractally broken and RBD-settled; the river
  gets the same clast population with rounding driven by transport distance.
- **Two-way erosion coupling:** HF-erode flow/wear masks drive which cliff faces retreat;
  the rock system's grus/talus feeds back as heightfield sediment. Gaea's Stratify/Outcrops
  nodes are the 2.5D *painting* of this; the formation approach computes it for real, and a
  preset ("granite tor field", "sandstone mesa") is just a rock-type enum + a terrain mask.
- **Industry precedent for the pipeline shape:** SideFX's Pegasus/Elderwood cliff recipes are
  already heightfield → split steep sections → detail → merge; the upgrade is what happens
  inside the "detail" box.
- **CityGen link:** [`citygen.md`](citygen.md) §1 reserves terrain as an unwritten subsystem
  (`terrain → vegetation → city`); this system is a consumer of that future terrain layer, same
  as foliage.

## 5. What makes this approach different (the differentiators to protect)

1. **Joint-first block statistics** (cuboid attractor, shared per-site fracture families) — the
   thing no noise or Voronoi tool can produce.
2. **Site coherence** from world-space geology fields — the thing no scan library can produce.
3. **Every face has a birthday** — formation events date every surface, and exposure age drives
   case-hardening/varnish/lichen masks for free. No other architecture gets this.
4. Competitor is the Fab scan library: win on **art direction and coherence** ("same lithology,
   different block"), not raw surface fidelity — and embrace scan/detail projection as the last
   mile rather than fighting it.
