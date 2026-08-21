# RailClone in Houdini — feature-parity evaluation

**Status:** research + evaluation, 2026-08-21. No build decision taken here.
**The question (Hannes):** RailClone is procedural at its finest; Houdini can do everything it can
but would need a lot of systems built from scratch to match the workflow. What would feature parity
mean, and how much sense does it make?
**This file owns:** the *engine/parity* evaluation — RailClone's technical generation engine, its
Houdini-native coverage, prior art, and the suite-wide demand audit.
**Not this file:** the UX/parameter-exposure dissection — that is [`artist_ui.md`](artist_ui.md) §1
(three tiers, promotion discipline, preset-library-as-front-door), already adopted as project law.
**Implementation spec:** [`polychain.md`](polychain.md) — the polyChain design spec v0
(2026-08-21), written from this study for later agent pickup. That file owns the tool design;
this one stays the research.

Research fanned out 2026-08-21 across three agents (RailClone engine inventory from iToo docs;
Houdini coverage + prior art; suite demand audit across all ideas/ studies). Sources inline;
claims read directly from cited pages unless flagged. RailClone state verified: **7.2**
(Feb 2026), 3ds Max-only, Pro €250 perpetual.

---

## 0. Verdict up front

**Reframe (Hannes, same day):** the intent is not a citygen component — it is a **general
procedural modeling tool, as RailClone is in 3ds Max**, which citygen then conveniently consumes.
That flips the placement conclusion (§0.1) but not the findings below.

**Revised verdict: full parity — engine plus iToo-scale content library — still does not make
sense. A general-purpose assembly tool as a polyfactory member in its own right is legitimate:
V1 scoped to the 1D (L1S) kernel + HDA face + starter kits, built general-first with citygen
streets as its first production consumer — and parked behind streets V1 like every other specced
system.**

Four findings carry the verdict:

1. **Houdini covers every RailClone *primitive* at or above parity, but four *engine behaviours*
   have no prebuilt equivalent** — automatic corner mitering, exact-fill slicing, slot-based rules
   (start/end/corner/evenly), marker-driven sub-splines — and in ~15 years nobody has shipped a
   Houdini equivalent (§3). "Houdini can do it" is true of the atoms, false of the machine.
2. **Only two suite systems consume the assembly half**: buildings (near-complete match — the B4/B6
   spec is functionally an A2S requirement list) and streets (three named places, one of them the
   already-decided Wang-tile catalogue). Everything else wants only the *preset/library* half,
   which is a separate, already-adopted obligation (§4).
3. **RailClone's moat is not the engine.** ~500 presets plus the 2025 "Systems" line is where the
   product value sits; our own buildings study already concluded *"the real deliverable may be the
   style library, not the generator"* ([`citygen_buildings.md`](citygen_buildings.md) §, echoing
   CityEngine's 20-year lesson). Engine parity alone is parity with the cheap part.
4. **RailClone and citygen are complements, not duplicates.** RailClone explicitly and permanently
   refuses spline junctions/intersections (§2.4) — the exact problem citygen streets exists to
   solve. Conversely RailClone's segment-catalogue machinery is exactly what streets deferred
   (Wang tiles) and buildings hasn't started. The two systems meet at a clean seam: *graph
   topology is ours; segment population along the resolved splines is the RailClone-shaped hole.*

---

## 1. What RailClone's engine actually is

Two generators — **L1S** (1D array along a spline) and **A2S** (2D array / facade fill), nestable
to any depth — plus ~21 style nodes. Everything else reduces to eight kernel mechanisms
([key concepts](https://docs.itoosoft.com/railclone/getting-started-with-railclone/4-key-concepts-array-based-instancing),
[L1S](https://docs.itoosoft.com/railclone/style-editor/1d-arrays-generator-l1s),
[A2S](https://docs.itoosoft.com/railclone/style-editor/2d-arrays-generator-a2s),
[segments](https://docs.itoosoft.com/railclone/style-editor/segments)):

1. **Section decomposition of splines.** Start/End/Corner/Evenly/Default slots (A2S adds
   Left/Right/Top/Bottom sides, four array corners, X/Y Corner columns/rows, X/Y Evenly); corner
   slots filterable by vertex type; **markers** (RC Spline modifier — % or distance positions, IDs
   + 9 typed data channels, no vertices added); **material-ID limits** partition one spline among
   multiple generators (the multi-lane mechanism).
2. **Four fill algorithms** with padding-aware packing (negative padding = overlap): `Tile`
   (replicate; last tile boolean-**sliced** to exact remaining length, holes capped and box-mapped),
   `Scale` (stretch one segment per section), `Adaptive` (whole-segment count, all scaled — never
   a cut segment), `Count` (fixed N scaled).
3. **Three Z-deform modes** for slopes/terrain: `Adaptive` (bank with tangent), `Vertical`
   (verticals stay plumb — the picket mode), `Stepped` (no deform — posts), plus slope-fixing,
   flat-top/bottom bands, and generator-side `Flatten Stepped`.
4. **Miter-vs-bend corner machinery.** Default = bend geometry around the vertex; Bevel = slice
   into a miter with Reset/Extend/Symmetric displacement, fillet radius, and odd/even
   compose-symmetry rules for corner segments. Documented limits: narrow angles, curved paths,
   last corner of closed splines.
5. **Surface conform**: Z-projection of the whole array onto any mesh, per-segment Y-tilt for
   camber; RC7 adds a Conform *spline* operator (project the path itself, keep processing).
6. **2D clipping** by closed splines (include/exclude, cap+map holes, per-segment cull policy,
   fill-the-area mode with nesting rules).
7. **Deform-aware automatic instancing.** The engine segregates bent/sliced/Z-deformed segments
   (become mesh) from pure clones (become native render instances — V-Ray/Corona/Arnold/Redshift)
   with no user action; proxies always instance. Scale evidence: iToo's stadium scene ≈ 700 M
   polys from one object ([docs](https://docs.itoosoft.com/railclone/rendering-best-practices)).
8. **Correlated randomness scopes**: Randomize/Sequence/Selector/Conditional operators with
   generate-on and sync-between scopes (segment / section / sub-spline / array row / generator) —
   how mirrored guardrails randomize identically on both sides.

Conditional tests: spline/section length, % position, spline-segment line-vs-curve, material ID,
vertex type + angle, X/Y segment counters (periodic patterns); plus a full expression engine over
exported properties and marker data
([conditional](https://docs.itoosoft.com/railclone/style-editor/operators/conditional),
[arithmetic](https://docs.itoosoft.com/railclone/style-editor/operators/arithmetic)).

### 1.1 Recent state (why "parity" is a moving target)

- **RC6** (2023): RC Slice modifier — pre-slice one authored mesh into ~20 named slot pieces; the
  model-to-style conversion path.
- **RC7** (May 2025): a whole **Spline Operators** category — Boolean, Offset (multi-parallel
  lanes), Catenary, Connect, Conform-to-terrain, Fillet/Chamfer/Divide/etc.
  ([changelog](https://docs.itoosoft.com/changelog/2025/05/27/railclone-7_0_0)).
- **RailClone Systems** (2025–2026, Pro-only): ready-made parametric assets — windows, curtain
  walls, bridges, railings, cladding, interiors — customizable *without opening the graph*
  ([announcement](https://www.itoosoft.com/blog/introducing-railclone-7-smarter-modeling-in-3ds-max-starts-here)).
  Confirms the [`artist_ui.md`](artist_ui.md) §1d reading: presets-with-curated-knobs *is* the
  product; the engine is the back office.

### 1.2 What RailClone refuses — the sharpest boundary

**Junctions/intersections/forks: permanently unsupported.** iToo, on the record since 2014:
*"RailClone is designed to be a generic tool, so we cannot assume certain shortcuts that would be
used in a specialized road making tool"*
([forum](https://forum.itoosoft.com/railclone-pro-(*)/i-have-no-idea-in-making-the-crossroads-in-railclone-pro/)).
Still absent through 7.2 — RC7's spline Booleans operate on regions, not graph topology. Users
hand-place junction meshes and use material-ID limits to stop generators short of crossings.
Other hard limits: A2S Adaptive is X-only (Y clips as Tile); no auto-subdivision for Bend;
instanced segments can't bend/slice; the Material operator keeps instancing only in V-Ray.

---

## 2. Houdini-native coverage and the real gaps

Verified against Houdini 20.5/21 docs and forums (H21, Aug 2025, adds nothing aimed at
spline-assembly rules).

| RailClone capability | Houdini prebuilt coverage |
|---|---|
| Distribute along curve | Copy to Curves / Copy to Points + Resample, Path Deform — **distribution yes, slot system no** ([canonical DIY thread](https://www.sidefx.com/forum/topic/74853/), which names RailClone as the goal) |
| 1D piece chains | **Chain SOP** (native, missed in the first pass; flagged by Hannes, verified 2026-08-21 against [the docs](https://www.sidefx.com/docs/houdini/nodes/sop/chain.html)) — the closest native thing to L1S: start/end cap pieces, sequence/explicit/weighted-random patterns, fit-whole-pieces + scaled-count modes, negative-spacing overlap, per-piece rigidity zones with stretch softening, attribute per-curve overrides. **Missing:** corner slot + mitering entirely, exact-fill slicing, evenly slots, markers/sub-spline sectioning, conditional selection, surface conform, clipping, anything 2D. ≈ RailClone's Default+Start/End with patterns — maybe 40 % of L1S, 0 % of the rest |
| Bend/stretch to fit | Path Deform SOP (capture region, rigid zones, ramps) — **equal or better**; stretch-to-fit yes, **slice-to-fit no** |
| 2D facade fill | Labs Building Generator 4.0 (wall/corner/ledge modules, pattern strings) — ~70 % for building shells, corner alignment [reported broken](https://www.sidefx.com/forum/topic/74033/); ~20 % for general 2D arrays. Labs is study-only for us anyway ([`citygen.md`](citygen.md) — never a runtime dependency) |
| Conditional/sequence/random selection | Capability 100 % in VEX/attributes; **prebuilt artist-facing rule nodes 0 %** |
| Render-time instancing | Packed prims + USD PointInstancer — **architecturally ahead of RC**: instancing is data we control, renderer-agnostic, no V-Ray-only carve-outs |
| Preset library + promoted parms | Gallery/Asset-Gallery/HDA machinery ~90 %; **content 0 %** |

**The four gaps with no good prebuilt equivalent:** (1) automatic corner mitering for arbitrary
spline assemblies; (2) the exact-fill slicing engine (Tile mode's boolean-cut last segment);
(3) the slot-based rule system itself; (4) marker-driven sub-splines. Plus the fifth, biggest,
practical gap: **the ~500-preset content library.**

**Prior art: nobody has built it.** No commercial or free "RailClone for Houdini" HDA exists
(Gumroad/Orbolt/GitHub/forums searched). The one directly-inspired attempt — sebastianknoll's
"Attach to Curve" (Labs Tech Art Challenge 2022, cites RC Spline as inspiration) — stalled at WIP
([thread](https://www.sidefx.com/forum/topic/87519/?page=1)). Demand is served piecemeal by
single-purpose fence/rail/facade HDAs. Community sentiment is the reason: *"would make no sense at
all as 'plugins' for Houdini as Houdini already can do all this stuff out of the box"*
([SideFX forum](https://www.sidefx.com/forum/topic/56650/)) — true for TDs, and precisely why no
artist-grade product emerged. iToo has no Houdini port announced; RailClone remains 3ds Max-only.

~~⚠️ One claim in [`citygen_buildings.md`](citygen_buildings.md) failed verification: no public
source ties Unit Image to running RailClone alongside Houdini.~~ **Retracted by the §6 follow-up:**
[80.lv documents Unit Image's RailClone apartment-building generator](https://80.lv/articles/a-great-building-generator-created-with-railclone)
(*Free Fire: Double Trouble*, pipeline RailClone/Max + Houdini + Substance + V-Ray). The
buildings-survey line stands.

---

## 3. Suite demand audit — who would actually consume it

Full per-system audit ran across all eleven ideas/ studies. RailClone appears 24 times in the
corpus; only twice as a stated *need* (both streets). Result in tiers:

**Tier 1 — real, specified, unbuilt demand for the *assembly engine*:**

- **Buildings** ([`citygen_buildings.md`](citygen_buildings.md) §12). The strongest match in the
  suite — essentially an A2S requirement list already written: B4 scope-split → fill from module
  library; B6 corner/seam modules as a whole stage (corner closure is gate G2 and the subsystem's
  acceptance test); kit manifests with `moduleRole`/nominal bay size/cut geometry; swap/replace
  keyed on structural-address `elem_id`; warn-never-fail on kit gaps.
- **Streets** ([`citygen_streets.md`](citygen_streets.md)), three distinct places: (a) the named
  future consumer — *"RailClone-style final geometry instancing (what ships today is proxy)"*;
  (b) the deferred cross-section transition, already decided as a **Wang-tile catalogue of
  middle/end pieces picked by neighbours** — a 1D array with start/end segments in all but name;
  (c) the missing street-furniture/dressing stage (Epic's `street_furniture_processor` is the
  named precedent in [`citygen_simulation.md`](citygen_simulation.md)) — **no polyfactory doc
  currently owns this stage.** Streets also already built and measured a segment-deformation
  mechanism (chord-frame capture/rebuild).

**Tier 2 — would consume only the preset/library half:** asset library (would be the browser
front door but is currently a whole-mesh browser, not a kit/style library), terrain presets,
rocks, foliage species. All covered by the already-adopted [`artist_ui.md`](artist_ui.md) §6
rule 6 ("the preset corpus is a deliverable"), which is a *separate obligation from any engine*.

**Tier 3 — no consumption:** foliage (growth sim, geometry emergent), rocks (explicitly
anti-catalogue), hair (profile-along-curve, no library), traffic/crowds (dynamic agents).
Fabric/polyKnit is a genuine structural *rhyme* (per-face template selection + deformation;
caston/bindoff/rowend are start/end segments) but at yarn scale, executed in a C++ Hydra
procedural at render time — shared concept, not shared code.

**Conclusion from the audit:** among the *researched systems*, only streets + buildings consume
the assembly half. ⚠️ But per §0's reframe this audit answers a narrower question than the intent:
a general modeling tool's customers are artists doing everyday environment work (fences, railings,
curtain walls, cables, bridges — RailClone's actual daily use in Max), which exists with or
without citygen. The audit rules out a *pipeline-internal shared engine*; it does not rule out a
*standalone tool*. What it does establish: the tool's first two production customers are already
specified (streets Wang-tile transitions + the unowned street-furniture stage), and the
constraints it must satisfy are suite law, not citygen-specific (see §5).

---

## 4. What parity would mean — three separable layers

**Layer 1 — the engine kernel** (§1's eight mechanisms). For a senior Houdini TD: the 1D core
(section decomposition, four fill modes, Z-deform, miter/bend corners) is weeks of VEX/SOP work
per mechanism, but the *edge-case surface* is where RailClone's 15 years live — bevel on narrow
angles, closed-spline last corners, padding interaction with every fill mode, deform-aware
instance segregation. Honest estimate: **months to a polished general kernel; a subset scoped to
known consumers is much less.** (Estimate, not measured.)

**Layer 2 — the authoring/UX layer** (21-node vocabulary, promotion, macros, library browser).
Houdini HDAs + promoted parms + galleries already provide the mechanism; [`artist_ui.md`](artist_ui.md)
§6 already adopted the discipline (empty-by-default pages, macros as middle tier, presets as front
door). **This layer needs adoption, not construction.**

**Layer 3 — the content library.** ~500 styles + the Systems line. Pure authoring effort,
person-years at iToo's scale, and the actual moat. Parity here is a *product decision*, not an
engineering one — and our buildings study already flagged the style library as possibly the real
deliverable. No engine work substitutes for it.

The trap in "rebuild RailClone" is conflating the three: Layer 1 is buildable, Layer 2 is done on
paper, Layer 3 is the part that made RailClone RailClone — and the part a rebuild-for-ourselves
only needs at the scale of *our* kits.

---

## 5. Recommendation

1. **Do not chase full parity.** Not because a general tool is illegitimate (§0 reframe — it is),
   but because parity's expensive layers are the wrong targets: the 15-year edge-case surface (§4)
   is amortized by scoping V1 to the 1D kernel, and the ~500-style content library (§2, §4) only
   needs to exist at the scale of *our* kits. "RailClone workflow, polyfactory-sized content" is
   the target; "RailClone, all of it" is not.
2. **Build it as a standalone polyfactory tool — general-first, citygen as first consumer,
   parked behind streets V1.** The park is the same one foliage/fabric/rocks sit in, and here it
   is productive: streets' Wang-tile transition catalogue and the unowned street-furniture stage
   are the tool's first two production customers, so one build after streets V1 pays down both.
   V1 scope = L1S kernel (section decomposition/slots, four fill modes incl. exact-fill slicing,
   Z-deform modes, miter/bend corners, surface conform) + promoted-parameter HDA face + a small
   starter kit — already a shippable fence/railing/wall/cable tool. A2S facade fill is phase 2,
   on the buildings B4/B6 timeline — its scope is sharpened by the §6 follow-up. Both arrays are
   in scope; 1D-then-2D is build order, and mirrors RailClone's own architecture ("A2S is
   essentially a stack of L1S generators" — iToo's teaching), so the 1D kernel is the 2D
   substrate, not a detour.

### 5.1 Decisions taken (Hannes, 2026-08-21)

- **Chain SOP: seed, not dependency.** Not used directly — its feature set/parameter model is the
  starting point the kernel copies and extends. ⚠️ Whether its *internals* are literally copyable
  depends on how it ships: compiled C++ SOP (likely) ⇒ "copy" means reimplement its behavior as
  the kernel's base layer; factory HDA ⇒ fork the network. One `hou.nodeType` check once Houdini
  is up — verify before the kernel design is cut.
- **Preset ownership: domain tools own their corpora.** Street styles live with streetgen,
  building styles with buildinggen, etc. — per [`artist_ui.md`](artist_ui.md) §6 rule 6 ("preset
  corpus is a deliverable *per subsystem*"). The base tool ships only the engine + a minimal
  starter kit (fence/railing demo) so it is usable standalone.
- **Name: polyChain** (Hannes). Artist-friendly over technical: "poly" is the suite family mark
  (polyKnit), "chain" is the image — linked elements following a line. Deliberately adjacent to
  the native Chain SOP it seeds from: artists who know that node read polyChain as "Chain, grown
  up". The 2D facade side ships under the same name (phase 2), accepting the 1D-leaning imagery. "General" costs little in constraints, because the binding
   rules are suite law, not citygen-specific: promotion discipline and preset corpus
   ([`artist_ui.md`](artist_ui.md) §6), warn-never-block, swap/replace per instance, vanilla
   Houdini. The citygen-specific contracts (templates on the data stream, never in a node;
   attributes-not-JSON; `elem_id` override cascade) must hold at the citygen seam — designing the
   template/kit format to satisfy them from day one is the one place general-first must not drift.
   RailClone's kernel (§1) is the **checklist of mechanisms** to design against — especially the
   four fill modes, the miter/bend rules, and deform-aware instance segregation (which maps
   cleanly onto packed-prim vs real-geometry segregation and feeds the undecided
   instancing-substrate test in [`citygen.md`](citygen.md)).
3. **The suite-wide shared thing is Layer 2 + the preset obligation, not an engine.** That is
   already project law via [`artist_ui.md`](artist_ui.md) §6; the one unresolved piece is the
   preset storage mechanism (`hrecipes` is verified but officially Copernicus-only while citygen
   is SOP-only — see [`terrain_presets.md`](terrain_presets.md)), and the audit found the suite
   currently violating attributes-not-JSON four different ways. That reconciliation is a
   build-time decision and is worth more to the suite than any assembly engine.
4. **Steal the refusal, too.** RailClone's most instructive design act is refusing junctions for
   12+ years rather than half-shipping them ([`artist_ui.md`](artist_ui.md) — "refuse the
   unsolvable gracefully"). Citygen *is* solving junctions — that is the differentiator; the
   kernel should conversely refuse what the catalogue can't express (fall back to blank stand-ins,
   never fail), exactly as buildings §12 already specifies.

**Net answer to the question:** feature parity means three different things (§4), only one of
which is engine work. As a general polyfactory tool the idea is sound — the 1D kernel plus the
suite's own UX law plus polyfactory-sized kits *is* the RailClone workflow in Houdini, and nobody
has shipped that in 15 years. What does not make sense is chasing iToo-scale parity (content
library, full edge-case surface) or letting the build jump the queue: it is specced now, built
after streets V1, with citygen as its first production consumer.

---

## 6. Follow-up: RailClone as building generator (2026-08-21, same day)

Hannes flagged buildings as a prime use. Second research pass: how RailClone is *actually* driven
for buildings in production — iToo/Hayes Davidson tutorials read in full, iToo staff forum
answers, artist writeups. (Hayes Davidson, a major London archviz studio, authors iToo's official
building tutorial series — the canonical workflow is literally a studio pipeline written down.)

### 6.1 How production drives it

- **One closed footprint spline + one height scalar is the whole-building interface.** The entire
  building is a single A2S wrapped around the footprint (X Rotation 90°, segments authored lying
  flat); facades are *never* wired per-face
  ([building-generator tutorial](https://www.itoosoft.com/tutorials/create-a-building-generator-and-master-the-a2s-generator)).
  **Vertex type is data**: hard vertex → corner assembly; smooth/bezier vertex → curved facade
  with no corner geometry.
- **Storeys via slots, not per-floor splines**: Bottom = ground floor, Top = cornice/parapet,
  Default rows between (Sequence/Randomize), Y Evenly = floor spacing, X Evenly = pillar rhythm.
- **Deterministic exceptions are painted onto the spline**: doors/entrances via material IDs on
  footprint sub-segments + Selector in Spline-Mat-ID mode, or via markers — artist-authored
  positions, never randomized
  ([Mastering Procedural Modelling](https://www.itoosoft.com/tutorials/mastering-procedural-modelling-in-3ds-max)).
- **Adaptive fill is the architecture default** — whole modules subtly scaled to fit the run,
  *never* slice through a window; slicing stays opt-in (mouldings, clip boundaries).
- **Parallel generators over shared drivers**: facade + room-shell interiors + brace lattice +
  roof cap are separate A2S over the *same* footprint spline and one exported height — change the
  spline, everything regenerates
  ([interiors tutorial](https://www.itoosoft.com/tutorials/populate-buildings): visible full-geometry
  rooms with per-room light/material/UV randomization, plus scatter-based furnishing with vertical
  zoning — retail floors 0–3, offices 4–10, residential 11+).
- **Production proof at both tiers**: Bertrand Benoit covered ~80 % of a hero building with four
  swept profile elements ([writeup](https://bertrand-benoit.com/blog/railclone-lite-for-buildings/));
  Unit Image's apartment-building generator — footprint + height, "3–4 clicks" per building — for
  *Free Fire: Double Trouble* in a RailClone+Houdini pipeline
  ([80.lv](https://80.lv/articles/a-great-building-generator-created-with-railclone)); iToo's own
  [Background Buildings library](https://docs.itoosoft.com/parametriclibrary/background-buildings-library-vol-1)
  ships 13 footprint-spline towers plus an all-in-one district-fill preset (grid fill, office/
  residential/misc mix %, per-type height ranges, roof-prop density).

### 6.2 Its building limits (docs/forum-confirmed)

- **No massing.** Roofs are dressed plane-by-plane (per-plane boundary splines, clipped arrays,
  auto-align; ridge/hip/verge as separate L1S on hand-drawn splines,
  [roofs tutorial](https://www.itoosoft.com/tutorials/creating-roofs-with-railclone)) — RailClone
  never solves hip/gable massing from a footprint. Our B5 straight-skeleton is the gap it never
  filled.
- **Surface conform is Z-projection only** (iToo staff: "a little limited… it only works well when
  the face normal points towards the RC object"). Curved towers only as curved-footprint
  extrusions; twisted/tapered is outside the paradigm.
- **No boolean openings.** Wall-with-hole is modeled *into* the bay segment, or apertures are
  pre-cut and windows dropped in via per-aperture clipped arrays (the 67-unique-windows-from-one-
  object technique, [Parameterising Windows](https://www.itoosoft.com/tutorials/parameterise-windows)).
- **Intersection cells have no slots** (corner-top, evenly-bottom, corner×evenly…) — macro and
  expression workarounds; the RC Slice modifier's ~20 auto-generated pieces reveal the true cell
  inventory a facade grammar needs.
- **Adaptive × Bevel are mutually exclusive** (documented two-generator workaround), and
  instancing dies on slice/bend — so production pre-slices corner pieces to stay instanced.

### 6.3 What transfers to citygen buildings and to the assembly tool

1. **The slot taxonomy is validated by production — with one fix.** Bottom/Top/Start/End/Default/
   Corner/Evenly/Markers covers real buildings; phase 2 of our tool should ship the **intersection
   cells as first-class slots** (~20 roles per the RC Slice inventory), fixing RailClone's biggest
   wart instead of inheriting it.
2. **B6 is vindicated.** Corners are a miniature sub-system (bend vs miter, align-to-previous,
   odd/even compose symmetry, angle-conditional segment choice, offset tuning) — §6.2 + the corner
   docs are the design checklist for B6 and gate G2.
3. **Kit ingestion is the missing on-ramp for §12.9 kits.** The RC Slice pattern — *model one good
   facade chunk, auto-slice into the cell inventory, jigsaw-clipped to the default cell's size* —
   is how ordinary artists turn kit pieces into a generator without graph authoring. Worth
   specifying as a kit-*authoring* tool alongside the manifest contract (it complements, not
   replaces, the Lake House `*_cut_*` opening convention).
4. **Adaptive-fit default, slice opt-in** — adopt as the fill-mode default for all architectural
   consumers of the assembly tool.
5. **Deterministic exceptions as painted spline/prim data** (doors, entrances, hero bays) — the
   same authored-data-over-randomness philosophy citygen already holds; confirms markers/painted
   IDs belong in the tool's 1D kernel, not phase 2.
6. **The two-tier product shape maps 1:1 onto our tiers**: hero building = openable template/graph;
   background = preset exposing footprint, storeys, mix %, material slots. The Background Buildings
   AIO parameter set is a *proven* parameter surface for an eventual district-fill node — record
   for the B-stage parameter design, [`artist_ui.md`](artist_ui.md) §6 rules applying.
7. **The clipped-area array is the second primitive** beside the swept array — flat roofs, floor
   plates, cladding fields, per-aperture windows all fall out of it. Cheap once A2S exists;
   include in phase-2 scope.
8. **What citygen does that RailClone structurally cannot** — the differentiators to protect:
   massing from footprint (B2 + B5 skeleton), true junction solving, non-planar conform, boolean
   openings, and the override cascade down to a single window (the [`citygen.md`](citygen.md) §1
   vision sentence).
9. **Interiors, recorded not scoped**: room-shell arrays + vertical zoning + per-room
   randomization is a cheap, proven route to visible interiors. No polyfactory doc owns interiors
   today; when one does, start here.

**Net for buildings:** the follow-up *confirms* phase-2 demand and sharpens its scope — A2S with
first-class intersection cells, clipped-area arrays, adaptive-fit default, painted-ID exceptions,
and an RC-Slice-style kit ingestion tool. It also confirms the seam: the assembly tool dresses;
B2/B5/B6 massing, junction and cap logic stay citygen's own.
