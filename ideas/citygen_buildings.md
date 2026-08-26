# CityGen — Building Generation Research & Design Spec

**Status:** research complete (§§1–11); **design spec v0 in §12**, written 2026-08-17.
**Gate G1 passed 2026-08-26 and skeleton B2 + B1 `setback` are built** (§12.10a) — §0.0 is the
resume pointer and supersedes this line. G2 and G3 (§12.10) are still ahead of the remaining
B-stages.
**Owner doc for:** the building subsystem — [`citygen.md`](citygen.md) §6 roadmap item 4,
*"largest unknown, written from scratch"*.
**System-level architecture and cross-cutting contracts:** [`citygen.md`](citygen.md) — read first.
**Streets / blocks / lots (the upstream producer of footprints):** [`citygen_streets.md`](citygen_streets.md).
**Reference library:** `polyfactory/resources/citygen/README.md` (gitignored, local). It owns
*inventory and literature*; this file owns *the survey*. What it already holds for buildings — and
the acquisition list it flags — is in §10a.
**Artist-facing UI:** [`artist_ui.md`](artist_ui.md) — the parameter surface study; its §6b audits
this doc (style = data + openable presets, never a second grammar; text rules must never be the
only path to an art-directable outcome). Binding on the eventual B-stage parameter design.
**RailClone building workflows:** [`railclone.md`](railclone.md) §6 — how production drives
RailClone for whole buildings (footprint-spline interface, slot taxonomy, corner machinery,
RC-Slice kit ingestion) and what transfers to B4/B6, §12.9 kits, and phase 2 of the planned
**polyChain** assembly tool. Also retracts one flag: the Unit Image RailClone+Houdini claim (§ tool table) is verified.

Written 2026-08-17. Branch `cityGen`.

---

## 0.0 BUILD STATE — resume pointer (read this first, keep it current)

⚠️ **If you are a fresh agent, or this session resumed after a usage-limit reset or a crash:
start here.** This block is the single source of truth for where the build stands. §12 is the spec;
this is the bookmark. **Every cycle must update this block and commit it** — it is cheap, and it is
the only thing that survives a context loss.

**Overnight autonomous build authorized by Hannes 2026-08-26.** This supersedes the
"Nothing built / gates before stages" framing in the Status line above for the duration of the run.
Opus 5 implements, an independent agent audits, headless `hython` verifies, **commit per cycle**,
branch `worldengine`, **never push**, never rewrite history, stage named paths only.

| Field | Value |
|---|---|
| Branch | `worldengine`. ⚠️ **Hannes 2026-08-26: EVERY agent works on `worldengine` from now on** — this supersedes any per-tool branch (`cityGen`, `polychain`) named in a sibling doc's resume pointer. ⚠️ **Mechanical constraint that follows:** git refuses to check out one branch in two worktrees at once. This shared checkout `F:/projects/polyfactory` holds `worldengine`; polyfactory-f2's worktree `F:/projects/polyfactory-citygen` cannot also check it out. Whoever moves second must merge/rebase their branch into `worldengine` from here, or take the checkout over — **not** `--ignore-other-worktrees`. Raised with f2 and Hannes 2026-08-26. |
| hython | `"C:/Program Files/Side Effects Software/Houdini 22.0.398/bin/hython.exe"` (verified headless by the polyChain build) |
| Owning spec | §12 of this file. Build order is §12.10, **gates G1/G2 before any B-stage** |
| Last completed | **G1 — question answered, GATE WITHHELD**, 2026-08-26. Skeleton B2 + B1 `setback` built; four style templates with per-field provenance; 16 checks, 17 mutations all seen RED (re-verified in round 2). **TWO independent round-2 audits ran on the current build and agree**: the gate's own question — is `volumeTopology` data? — is **confirmed and not disputed**, but G1 may not be recorded as done. Blocking reason in **§0.0f defect 1** (a legal override ships a building outside its own lot, unwarned — independently reproduced by both auditors). Second auditor's findings in **§12.10a "Round 2"** (R2-1…R2-7). ⚠️ **R2-1 is §0.0f defect 1's other half**: nothing in the suite measures the mass's plan position or size, so halving the bar's cut fractions in shipped VEX leaves all 16 checks and the baseline green. Fix both, re-run, then round 3. §12's attribute tables were corrected to the `pf_` law in the same pass (§12.4/§12.6/§12.7/§12.8). ⚠️ Test code is **1.53× production**, not the 8 % previously recorded — both auditors recounted independently and got the same number; budget now stated with its denominator in §12.10a, deletion list in §0.0f. |
| Next up | ⚠️ **CHECK AGAINST `git log --oneline -25` BEFORE STARTING.** **G2 — corner closure on an L** (§12.10), which is the acceptance test the whole survey points at (§5 Theme 4). Read §0.0d FIRST: polyChain's miter refusal is per-BUILD and B6's primary strategy walks into it, and ⭐ G2 must **record cook time per corner treatment** — those numbers are evidence for Hannes' pending §35.6 miter decision. ⚠️ G2 needs a **non-convex footprint**, which G1 never produced: `pf_inset.vfl` solves each corner independently and can fold a non-convex polygon through itself. That is the first thing to go and look at. |
| Gates | ⛔ **G1 IS NOT DECIDED. ROUND-2 AUDIT REPORTED 2026-08-26 AND WITHHELD IT.** The gate's *own question* — "is `volumeTopology` data?" — was re-verified and **is not disputed**: the rule library is genuinely shared and no style is named in production code. What blocks "decided" is a **production defect**: `pf_collapse.vfl` ships a building **massed entirely outside its own lot with no warning** (§0.0f defect 1). Fix, re-run, then round 3. Do **not** start G2 on an undecided G1. G1 topology-as-data ⏳ **question answered, gate withheld** · G2 ⬜ · G3 ⬜ · G2 corner closure on an L ⬜ · G3 APEX-vs-VEX ⬜ (only after G1+G2). Every gate owes a HUMAN viewport pass by Hannes — an agent looking at an image is not that, and it is never silently skipped. ⚠️ **G1's human pass is OWED**: two agents have now looked at `tests/citygen/gate_images_buildings/` and judged the four masses correct (round 2 viewed the Einhof plan, the Vienna plan, the Vierkanthof iso and the Zinshaus iso); **Hannes has not, and no agent may record that pass as satisfied.** Regenerate with `hython tests/citygen/run_building_checks.py --images`. ⚠️ **And the check that guards those images cannot fail** (§12.10a R2-2): `image_contains_subject` compares the rasteriser's own return value against the count that produced it, so an 8 × 8 px render of the same geometry still reports PASS. Until it asserts on the written PNG, **the human pass is the only image evidence G1 has.** |
| Run it | `hython tests/citygen/run_building_checks.py [--mutations] [--images] [--update-baseline]`. ⚠️ **hython does not load the polyfactory package** — `POLYFACTORY` is unset and `polyfactory` resolves as a namespace package with no `citygen` in it; the runner puts `polyfactory/scripts/python` on `sys.path` itself. |

### 0.0a Dependencies — check before picking a stage

| Dependency | State (2026-08-26) | Blocks |
|---|---|---|
| **polyChain** | ✅ **DONE.** `polychain.md` §0.0: *"THE BUILD IS FINISHED AND THE RULE-0 QUEUE IS EMPTY."* A 2D facade node exists (`pf_polychain`, `facade.build_many`, gates PC-G5/PC-G6). ⚠️ That file's *top* Status line still says "Nothing built / parked" and is **stale** — §0.0 there supersedes it. | Unblocks **B4**, **B6**. Read `polychain.md` §0.0 + `railclone.md` §6 before writing either — B4 may be largely polyChain *configuration*, not new code. |
| **Streets S8 determinism** | ⚠️ **ANSWERED, AND IT IS "UNTOUCHED"** (polyfactory-b1, 2026-08-26). Streets paused 2026-08-21 when polyChain took over; nobody has been near S8 since. Documented truth: `elem_id` survival is proven against **parameter** changes only, **unproven under geometry change**; `node_id` does not exist; provenance is not auto-stamped. | **DO NOT BLOCK — INSULATE.** §12.7's structural-address `elem_id` (`siteId` + stage + volume/face/bay/storey, **never generation order**) is the defence, and it is now load-bearing rather than a nicety. Source `siteId` from the lot **at B0 ingestion only**, and record the **lot→siteId mapping as the single seam** to revisit when streets resumes. Note it in every cycle's report. |
| **B0 schema** (`citygen.md` §7 item 0) | ⚠️ **RESOLVED FOR THE BUILD, NOT RATIFIED.** polyfactory-b1: proceed with §12.4's **volume + face-roles**, planar lot as the degenerate case. | Build **B0 as an ADAPTER**: ingest today's planar S8 lot, stamp the volume-form schema. Streets needs no change, so **no seam mismatch can arise** and the work stays reversible. ⚠️ **Hannes ratifies, not an agent** — this goes in the morning report. |
| **Streets tonight** | ✅ **S8 IS STABLE TONIGHT.** polyfactory-f2 is working upstream at S5 (junction merge mouth), in an **isolated worktree** `F:/projects/polyfactory-citygen`, branch `cityGen`. | Input contract is stable. ⛔ **Never `git worktree remove` `F:/projects/polyfactory-citygen`**, and never `git checkout` there. The shared checkout `F:/projects/polyfactory` is ours. |
| **`conventions.md` `pf_` prefix** | ✅ **FIXED 2026-08-26 (G1).** §12.4, §12.6, §12.7 and §12.8 now spell every attribute `pf_*`; §12.5's keys are deliberately NOT renamed, because template fields inside a data file are not attributes that leave a node. B2 ships `pf_`-prefixed throughout and a check asserts nothing `_*` escapes on any of the four classes or in groups. | ⚠️ **Two things a later reader must not mistake for settled.** `conventions.md` §9b "the CityGen field contract" is a different item — it is the STREET FIELD (`field_type`/`weight`/`angle`/`falloff`), it is still PENDING-Hannes-decides, and **buildings do not touch it**, so G1 neither needed nor made that decision. And `pf_site_id` is **detail** in §12.4 but **prim** in a stream carrying several sites, which is what B2 cooks — B0 owns that conversion. |

### 0.0b Order of work (S8-independent first, deliberately)

Everything here is buildable **without** streets or polyChain, so the run is not idle while
dependencies resolve:

~~`G1`~~ ✅ → `G2` → `B5 cap/straight-skeleton` (largest from-scratch item; Labs supplies nothing) →
`B3 structure tables` → `B1 footprint ops` (the `setback` op is done; `shapeL`/`shapeU`/`shapeO`/
`offset` are not) → `§12.9 module library` → **then** `B4`/`B6` on polyChain → **then, only once
S8 answers**, `B0` identity wiring + finalize/instancing.

### 0.0f G1 round-2 audit — the open queue (2026-08-26)

⛔ **Item 1 blocks G1. Items 2–3 are systemic and affect G2/G3 too, so fix them now, not later.**

1. ⛔ **`pf_collapse.vfl` builds outside the lot, silently. BLOCKING.** Via a *legal* cascade
   level-6 override (`citygen.md` §2.1) on a 20×10 lot — front 0, rear 12, sideStreet 25, alley 0 —
   **both axes invert**. The signed area keeps its sign (+10 from +200) *and shrinks*, so the growth
   test is silent; 10 > 1e-4, so the degeneracy test is silent. Result: 3 volumes, 18 faces at
   **x −5..0, z −2..0, entirely outside a lot at x 0..20, z 0..10**, with
   `pf_warn_footprint_collapsed` = 0 on every face — and `volume_count_matches`, `outward_normals`,
   `party_walls_real` all green.
   → **§12.10a's "Area that *grew* is now the proof" is FALSE as written.** A double inversion
   multiplies two negative extents, so shrinkage proves nothing. **The correct test is already
   free:** `_p0` holds the pre-offset polygon per point — assert every inset corner is *inside* it
   (same crossing-count the checks already use, in VEX). ✅ Confirmed *not* a false positive on the
   `setback(0)` identity case.
2. ⛔ **SYSTEMIC — the runner's `missing` sweep only requires ≥1 mutation per check NAME**, so a
   multi-clause check can ship with clauses nobody ever proved. Live example:
   `party_walls_are_real`'s elevation clause *has* teeth (lifting a cell 30 m took `overlapped`
   22→8) but **has no mutation of its own**. **Fix the sweep to demand a mutation per CLAUSE**
   before G2 writes more multi-clause checks.
3. ⛔ **SYSTEMIC — "a name is not a value".** `pf_warn_topology_arity` is asserted by no check and
   recorded by no baseline row: forcing `warnarity = 0` leaves all 16 checks green and the baseline
   unmoved. **Fix once, permanently: put all four `pf_warn_*` values per site into `record()`**
   (~3 lines, no new check or mutation needed).
4. **`encloses_courtyard` is a MIN-oracle, not per-edge.** Catches rotation, uniform over-depth, the
   4 m slide. **Misses a non-uniform ring**: scaling one pair of opposite edges 1.6× built a
   courtyard of **518.4 m² instead of 864 m²** and the check reported *"12.00–12.00 m against 12.00
   asked for"*. Cause: `_inside()` returns clearance to the *nearest* outer edge, and at a corner
   that is `min(d_prev, d_next)` — one correct neighbour per corner is enough to pass. `pf_inset`
   preserves index correspondence, so **measure courtyard edge *j* against outer edge *j***, or use
   edge midpoints not corners. Not reachable from today's uniform data, but per-role courtyard depth
   or `polyexpand2d`'s per-edge Inside Scale drives straight through it.
5. **`_plain()` is not lossless and the doc overstates it.** A **mixed** numeric list (`[1, 2.5, 3]`)
   returns all-float — shape restored, **element storage lost, which D223 says is the contract** —
   and a **nested list is dropped entirely and silently**, dying at `setGlobalAttribValue` *before*
   saving, so `load()` never sees it and nothing raises. Neither shape is in the four shipped
   templates. **Fix the doc at minimum; enrol a storage check.**
6. **`STORAGE` omits `pf_seed` and all four `pf_warn_*`** (all Int) though its docstring claims
   "every id B2 mints is enrolled here".
7. **Latent false positive:** under `ring`, `volume_count_matches` takes the cell count from the
   footprint's edge count, so a template with a shorter `volumes` list is *legal* (that is what
   `pf_warn_topology_arity` is for) but would fail the check. Fixture-safe today.

**⚠️ THE TEST BUDGET IS 52 % OVER, NOT 8 %.** §12.10a reached "1 025 production" only by counting
`devScripts/create_pf_building_styles.py` (296 lines) — a template-authoring script that **never
cooks**. What ships is `buildings.py` (283) + five `.vfl` (446) = **729**, against 1 108 test lines.
**Delete first (~45–50 lines, more than the overrun):** `degrades_never_refuses` + its mutation row
+ its `run_checks` line (measured redundant — its own paired mutation reddens `volume_count_matches`
too, with a better message; its only unique clause is `len(mine) >= 5`); `Result.as_dict` (never
called); `_plan_key` vs `base()` (two functions, one identity); `record()`'s unused `templates`
parameter; and in `faces()` the unread `pf_storeys` / `pf_face_role` — **but keep the
`pf_warn_topology_arity` read, it is currently the only thing asserting that attribute exists.**

### 0.0c Operational rules — paid for in blood this week, do not rediscover them

1. ⛔ **MACHINE SAFETY — THIS MACHINE HARD-FROZE TWICE** under 15 parallel `hython` processes
   (`build_retrospective.md` §2c #11). **Never raw-parallel `hython`. Never use system `$TEMP`.**
   Go through `tests/polychain/runguard.py` (owns slots via a commit-headroom guard, per-run
   `HOUDINI_TEMP_DIR` on F:, orphan sweep) or copy its pattern exactly. This outranks throughput.
2. ⛔ **TEST-SUITE COLLISION.** polyfactory-f2 is editing `tests/citygen/{cases,checks,run_scene_checks}.py`
   and `baseline.json` on branch `cityGen`. `baseline.json` is a full-value snapshot regenerated by
   `--update-baseline`; two branches regenerating it conflict badly and a careless resolution
   **silently blesses the other branch's numbers.** → **Building checks go in NEW modules**
   (`tests/citygen/checks_buildings.py` + its own baseline file), registered from the runner by a
   **one-line import**, so the eventual merge is one line and not a 14 000-value diff. Agreed with
   f2 2026-08-26.
   ⚠️ **G1 built the new modules and did NOT add that one line, deliberately.** `checks_buildings.py`,
   `run_building_checks.py` and `baseline_buildings.json` exist and are standalone; f2 is editing
   `run_scene_checks.py` *right now* on another branch, and a one-line edit to a file under active
   edit elsewhere is a merge conflict bought for nothing while the two suites are not yet run
   together. **Registering it is a named pickup item for whoever merges the branches** — it is one
   import and one call, and the building suite is `hython tests/citygen/run_building_checks.py`
   until then.
3. **Read every contract off the SHIPPED ASSET, never off prose or a rig** (CLAUDE.md). polyChain
   ships `polyfactory/otls/pf_polychain.hda`, `pf_polychain_facade.hda`, `pf_polychain_slice.hda`;
   kernel `polyfactory/scripts/python/polyfactory/polychain`; VEX `polyfactory/vex/polychain`;
   builders `devScripts/create_pf_polychain*.py`; checks `tests/polychain` + `tests/unit/test_polychain*.py`.
4. **D223 — an attribute's STORAGE is part of its contract.** An `int` `edge_id` shipped a
   different fence *and* a different curve order, with zero test coverage. **Enroll storage checks
   on `pf_site_id` / any id we mint from day one**, not later.
5. **`testing` skill governs** (`~/.claude/skills/testing/SKILL.md`): a check is not written until
   its mutation has been seen RED; state a size budget (test ≤ production) and **delete before
   adding**.
6. **Commit per cycle, named paths only.** No `-A`, no `--amend`, no `rebase`, no `reset`, no
   `checkout` of files we did not edit. **Do not push** — b1 reports the project pushes when green,
   but that is Hannes' call to give, not a peer's; ask in the morning report. A pre-commit hook
   regenerates `graphify-out/` — that churn is normal, do not fight it.

### 0.0d Read before designing B-anything

- ⭐ **`polyfactory/resources/citygen/README.md` §4c** (gitignored KB, added by f2 2026-08-26): a
  read of **metrum_rise**, an open-source city builder that independently converged on our
  architecture. It has a section **directly on the B0 seam**: buildings attach to streets **without
  splitting edges** — store `(edge_idx, side, cell_x, cell_y, width_cells, depth_cells)` plus an
  entrance cache (distance along the edge centreline, door position from the asset anchor, kerb
  handoff point); *"no virtual frontage nodes are inserted."* That is the alternative to splitting
  an edge per driveway, which multiplies nodes and **breaks `edge_id` stability** — i.e. it is a
  direct answer to the S8 identity problem above. Ten minutes, before B0.
- ⛔ **polyChain's miter refusal hits FACADES HARDER THAN FENCES, and B6 walks straight into it.**
  Mechanism, from polyfactory-b1 (the build's owner), 2026-08-26:
  1. **The refusal is per-BUILD, not per-corner.** ONE non-degenerate mitered corner sends the
     *entire* build to the Python reference.
  2. **A facade has corners × storeys.** A 4-corner, 30-storey building is 120 mitered assemblies,
     so virtually every real building lands in the refused class **if its corner treatment is
     miter**.
  3. **And §12.6 B6's primary strategy — "corner module from the kit" — IS the miter path** in
     polyChain terms (corner modules cut at the bisector). Bend mode *is* native but places **no
     corner module** (D37), which is almost certainly not what a building corner wants.
  4. **Cost: correctness NOTHING** (the reference is the oracle, ~1.00x) — **cook time everything**,
     at district scale. Fine for G2 and prototypes.
  → **Do not design B4/B6 assuming native miters. Budget district-scale cook time at reference
  speed.** And ⭐ **record cook time per corner treatment at G2** — those numbers are real evidence
  for Hannes' pending §35.6 miter decision, which is the thing that could change this.
- ⚠️ **polyChain's facade node has two open items that become ours if B4 sits on it**: PC-G7 is
  asserted on `facade.build_many` and **not on the asset**, and `pf_polychain`'s `addWarning` route
  is **invisible on the HDA an artist meets** — which collides with §12.8 (warnings persisted and
  visible) and `citygen.md` §2.2.
- ⚠️ **`polychain.md` has two staleness bugs** (found by polyfactory-47): its top Status line still
  says "Nothing built / parked", and **its §0.0 resume table still says Branch `polychain`** when
  the work is on `worldengine`. A fresh agent reading four lines draws the wrong conclusion and
  checks out the wrong branch. **Not ours to edit** — one owner per topic; asked b1 to fix at source.

### 0.0e Recovery procedure

1. `git log --oneline -25` and `git status` — **the log outranks this block** if they disagree.
2. Re-read this §0.0, then §12, then the relevant §§1–11 the stage cites.
3. `houdini_get_skill("houdini-dev-loop")` — mandatory before any Houdini work; plus
   `houdini-procedural-modeling` for geometry and `houdini-tool-design` for parameters.
4. Apply the `testing` skill: a check is not written until its mutation has been seen RED; keep a
   stated size budget and delete before adding.
5. Nothing is "done" until an **independent** agent has audited it on the current build. Absent
   that, the honest words are "implemented, unverified".
6. Resume at **Next up**. Update this block and commit before ending the cycle.

---

This file exists because buildings are a subsystem, and this repo's convention is one design doc
per subsystem ([`citygen_streets.md`](citygen_streets.md) is the precedent). It is deliberately
*research*, kept separate from design: the survey below has to be settled before the parameter
set, the schema or the APEX question ([`citygen.md`](citygen.md) §4b) can be argued about.

---

## 1. Headline finding

**There is one dominant approach, and it has not changed in 20 years.** Every production system
surveyed — academic, commercial, in-house, free — is the same pipeline with different clothes:

```
coarse mass (blockout / footprint + height)
  → split faces into rectangular regions ("scopes")
    → recursively subdivide until a region matches a module
      → fill regions from a library of feature meshes (window, door, pillar, trim, balcony)
        → special-case the parts splitting cannot express (corners, roofs, ground floor)
          → derive UVs, LODs, collision
```

The invariant is the **split-and-fill loop over an oriented bounding region**. What differs
between tools is (a) *how the artist authors the split rules*, and (b) *where the escape hatch for
hand art direction lives*. Those two axes — not the algorithm — are where every tool succeeds or
fails, and where all the recurring artist complaints land.

Confirming that this is genuine convergence and not one lineage copying itself:

| System | Year | Its name for the same thing |
|---|---|---|
| Wonka et al., *Instant Architecture* | 2003 | split grammar; rules split building → faces → structural sections → components |
| Müller et al., *CGA Shape* (→ CityEngine) | 2006 | shapes identified by symbols, geometry held in an OBB called the **scope** |
| Epic Games, GDC *Building Blocks* | 2010 | extract rectangular **scopes** from faces, recursively break down, fill from feature-mesh library |
| SideFX Labs Building Generator | current | patterns / modules / floor overrides |
| Buildify (Blender geometry nodes) | 2022– | building parts collections, generated per base-mesh face |
| Unreal PCG "grammar" nodes | 5.3+ | grammar string subdivision + modular mesh spawn |
| Embark, *Building Creator* (THE FINALS) | 2024–25 | blockout mesh + composable **Feature Nodes** per element |

Epic's 2010 talk states the problem in the same words a Houdini TD would use today: *creating a
detailed city window-by-window is daunting, and adjusting every window when requirements change is
worse.* That framing is the whole field.

**Consequence for us:** the algorithm is not the risk. `citygen.md` calls buildings the "largest
unknown"; the survey says the unknown is not *how to generate geometry* but *how to let an artist
overrule it*. That is the same problem [`citygen.md`](citygen.md) Contracts 1 and 2 already exist
to solve for streets. This is good news — it means the building subsystem is mostly an
authoring/override problem, which this project has already thought hard about.

---

## 2. The paper map

Three eras. Only the first is directly load-bearing for us.

### Era 1 — Grammars (2001–2014). The canon; still what production runs on.

| Paper | Contribution | Why it matters here |
|---|---|---|
| Parish & Müller, *Procedural Modeling of Cities*, SIGGRAPH 2001 | L-system streets + simple building mass. Already cited in [`citygen_streets.md`](citygen_streets.md) | The other half of the same paper is the building half |
| Wonka et al., *Instant Architecture*, SIGGRAPH 2003 | **Split grammars.** Also introduces a **control grammar** that sets attributes spatially — e.g. "first floor is a shop", "vertical detail on this column of shapes" | The control grammar is the earliest answer to *how do you art-direct a grammar*. Directly relevant to zoning → facade coupling |
| Müller et al., *Procedural Modeling of Buildings*, SIGGRAPH 2006 | **CGA Shape.** Context-sensitive rules; occlusion queries; consistent mass modelling with arbitrarily oriented volumes. Became CityEngine | The reference implementation. Its scope/OBB model is what everyone copied |
| Lipp, Wonka & Wimmer, *Interactive Visual Editing of Grammars*, SIGGRAPH 2008 | Direct visual editing of grammar rules instead of writing text | The first paper to treat "artists can't write grammars" as the actual research problem |
| Wu et al., *Inverse Procedural Modeling of Facade Layouts*, SIGGRAPH 2014 | Derive a split grammar *from* a given facade; cost function on description length | Relevant if we ever want "match this reference photo/plan" |
| Sugihara et al.; Laycock & Day; Aurenhammer et al. | **Straight skeleton** roof generation from footprints, incl. weighted variants for varied roof styles | The standard answer to hip/gable/complex roofs. Non-optional reading — roofs are a named pain point (§5) |

Also: SIGGRAPH Asia 2015 course *Practical grammar-based procedural modeling of architecture*
(Wonka et al.) — the field's own consolidated tutorial. Best single entry point if we want the
canon in one document.

### Era 2 — Layout & optimisation (2010–2020). Interiors and floor plans.

Concerned with *plans*, not shells: residential layout generation, deformable templates,
"good building layouts" via exploration, then the learning-based wave (House-GAN, Graph2Plan,
Building-GAN). Reviewed in *Computer-Aided Layout Generation for Building Design: A Review*
(2025). **Parked** — we have no interior requirement, and [`citygen.md`](citygen.md) §1 does not
ask for one. Flag it only because Embark's experience (§4) shows interiors change the geometry
contract completely (watertight, pre-fractured) if they ever *are* required.

### Era 3 — Neural / hybrid / LLM (2023–2026). Watch, don't adopt.

- *CityDreamer*, *CityGen*, *Proc-GS* (Dec 2024), *GaussianCity* — city-scale generation, mostly
  aimed at novel-view synthesis and 3D Gaussians, **not editable geometry**. Wrong output format
  for an offline-film-render pipeline that must expose per-window edits.
- *BuildingBlock* (2505.04051, 2025) — the most architecturally interesting of the batch:
  transformer diffusion generates a **layout as a point cloud**, an LLM converts that layout into
  **rule-based hierarchical designs**, and conventional PCG builds the geometry. i.e. the neural
  part proposes *structure*, the procedural part still makes the *geometry*.
- *CityGenAgent* (2026) — LLM emits "block programs" / "building programs". Already noted in
  [`citygen.md`](citygen.md) §4b as the analogue for the APEX-as-rule-graph idea.
- The 2025 *3D Scene Generation: A Survey* (2505.05474) splits the whole field into procedural /
  neural-3D / image-based / video-based, and is explicit that procedural is the paradigm with
  "high efficiency and spatial consistency" and real user control, while conceding rule-based
  methods have "limited diversity, requiring extensive human intervention".

**Verdict on Era 3:** the consistent pattern across the credible 2025–26 work is *neural proposes,
procedural builds*. Nothing here replaces the split-and-fill core. Nothing here outputs geometry
an artist can click a single window on. No adoption case for v1.

---

## 3. The tool landscape

Grouped by authoring model, which is the axis that matters.

### 3a. Text grammar

| Tool | Notes |
|---|---|
| **Esri CityEngine** (CGA) | The reference product. Ruled out as a dependency by [`citygen_streets.md`](citygen_streets.md) §1. **Still the most important tool to study** — 20 years of accumulated answers. Note: 2024.0 shipped a **Visual CGA Editor** (node-based, no coding) out of beta, and 2025.1 supports Houdini 21. See §4 — that release is itself evidence. |
| `cityengine_for_houdini` | Runs CGA rules inside Houdini. Explicitly restricted to **single buildings** — no city layout or street tools. Ruled out for us, but the scoping is telling: even Esri treats buildings as the separable, portable half. |

### 3b. Node graph / parametric, artist-facing

| Tool | Host | Notes |
|---|---|---|
| **iToo RailClone** | 3ds Max | The archviz standard. Node editor explicitly positioned as artist-friendly, no programming. Facade from perimeter + height. The most-praised *usability* model in the survey; Unit Image reportedly runs it alongside Houdini. |
| **Buildify** (Pavel Oliva) | Blender geometry nodes | Free, very widely adopted. Modular parts collections; generates from base-mesh faces. **ADE mode** = per-building art-directable editing: viewport extrude/scale, freehand footprint curves. Native `blender-osm` integration for real cities. |
| **SideFX Labs Building Generator** (4.0) | Houdini | Pattern/module system with floor overrides. Per [`citygen.md`](citygen.md) §5 this is a *starting point to study and reimplement*, never a runtime dependency. ⚠️ **It does not generate roofs at all** — flagged by Hannes, verified against the 4.0 docs: it slices volumes into floors and swaps regions for modules, and the only top-related parameter is a decorative **Top Ledge** (height + module pattern). There is no roof parameter, no roof module, no cap. Combined with the corner defects in §5 Theme 4, the two things Labs omits or breaks are **exactly** the two hardest parts of §1's pipeline. |
| **Unreal PCG** | UE5 | Grammar-string subdivision nodes added 5.3; framework declared production-ready in 5.7. Epic's own writeup concedes their focus has been landscape/nature and that **buildings, infrastructure and cities were approached "cautiously"** and are still being made more user-friendly. |
| **SceneCity** (cgchan) | Blender | Node graphs; road networks + mass placement of tens of thousands of buildings; mixes procedural and hand-made assets; procedural facade *textures*. City-scale, not building-detail. |
| **Grasshopper / Rhino** (+ EvoMass, Ladybug, Karamba) | Rhino | The parallel universe: same parametric idea, optimised for performance analysis and BIM interchange rather than render-ready geometry. Worth a look for *massing* vocabulary, not for facades. |

### 3c. Bespoke in-house HDA toolsets — the closest analogues to what we're building

| System | Notes |
|---|---|
| **Embark Studios, Building Creator** (THE FINALS, ARC Raiders) | The single most useful case study found. See §4. |
| **Insomniac, Marvel's Spider-Man** Manhattan | Heavily procedural Manhattan via Houdini; documented across four GDC 2019 sessions (technical postmortem, procedural lighting tools, open-world pipeline, Substance look-dev). ⚠️ Session *descriptions* read only — talks not watched, details unverified. |
| **Epic, GDC 2010 Building Blocks** | Designers place shapes; technical artists author rule graphs; LODs generated incrementally with the blockout as the lowest LOD; offline render bakes low-LOD textures + reflective-window masks. |
| **SideFX Project Skylark** (June 2025) | Free SideFX building generator + tutorial (3h04, H20.5). Takes an artist blockout and places windows and beams. Stylised/medieval. Techniques listed: half-edge topology, 3D→2D vector projection, UV, VEX, trig. **Directly relevant reference, freely available.** |
| **SideFX Project Vitruvius** | Announced architecture/urban toolset — road networks, city layouts, building structures. Still *upcoming*; no release found. [`citygen.md`](citygen.md) §7 item 5 asks about its status — **answer: still unreleased as of this search.** Cannot be a dependency; worth watching. |

### 3d. Discrete / tile-based — a genuinely different family

**Townscaper** (Oskar Stålberg) — Wave Function Collapse over an **irregular quad grid**, plus
marching-cubes-style module resolution. WFC picks which building tiles are legal given
neighbours. Descends from model synthesis (Merrell) rather than from grammars.

Worth knowing because it solves the one thing split grammars are worst at: **corners and joins
are legal by construction**, since adjacency rules are the primitive. The cost is that everything
must live on a grid, and Stålberg has only ever hinted at the real implementation. Not a candidate
for v1, but the right mental model if corner handling (§5) becomes intractable.

### 3e. Asset-library and AI adjacents — not building generators

- **KitBash3D Cargo** — free USD asset browser for KB3D's building library; reference-image search.
  Kitbash, not generation. Relevant only as the "hero building" source in a hybrid workflow.
- **Polygonflow Dash** — UE world-building copilot; scattering, asset tagging, parametric tools.
  Adjacent, not building generation.
- **Text-to-3D** (Meshy, Tripo, Rodin, Sloyd, Hunyuan3D) — surveyed and **rejected for this
  purpose**. Independent 2026 reviews converge on the same failure: dense triangulated topology,
  awkward UVs, collapsing material slots, non-determinism (semantically identical prompts produce
  wholly different meshes), and LOD0 only. Sloyd is the exception precisely because it is
  *parametric templates, not generation* — which is to say, the thing that works is the thing that
  isn't AI. Incompatible with per-window editability.

---

## 4. The pivotal case study: Embark's Building Creator

Best-documented in-house system found, and it reaches conclusions this project already reached
independently. Worth reading in full (both sources in §8).

- **They rejected monolithic generators on purpose.** Their stated taxonomy: procedural tools are
  either *rigid* (enforce consistency) or *creative* (flexible building blocks). They chose
  flexible because their maps span Mediterranean Monaco, parapet-walled Bernal, and wooden Kyoto —
  **one generator cannot hold multiple architectural styles.**
- **Architecture:** object-level HDA containing SOP-level **Feature Nodes**, each owning one
  architectural element (walls, floors, roofs, foundations, windows, doors). Artists *compose*.
- **Everything starts from a blockout mesh**, which is shared spatial context so every Feature Node
  interprets the building consistently.
- **Manual override is a first-class node.** A *Manual Module Node* with a custom viewer state for
  precise placement; non-destructive edits stored as **geometry inside geometry data parameters**.
- **Consistency was imposed by rule where gameplay demanded it** — Monaco's main door always opens
  into a hallway with the staircase on the left — while facades stayed unique. Art direction as a
  *rule*, not as a constant.
- **Automation where artists gain nothing:** collision via a custom 2D convex decomposition in VEX
  running iteratively in a feedback loop; occluders automatic; zero manual authoring.
- **Results:** blockout → fractured asset in **4–6 minutes**; 100+ buildings across two shipped games.
- **Their stated lesson:** *"Get something usable into artists' hands early, then iterate with
  them."* And a smaller one worth stealing — using **correct architectural names** for nodes and
  attributes measurably improved clarity and maintainability. That is exactly
  [`citygen_streets.md`](citygen_streets.md) §1 rule 4 ("standard vocabulary, our own
  implementation"), independently arrived at.

---

## 5. Artist feedback

The user's requirement was corroborated sentiment, not single voices. Each theme below is graded.
**Themes 1–4 are the ones I would actually design against.**

### Theme 1 — Grammar/scripting is the adoption wall — ★★★ strongly corroborated

Repeated across Esri community threads, independent review sites, and Esri's own product
statements: authoring effective CGA requires programming literacy; those expecting a visual tool
hit a steep wall; "companies are not going to fund the overhead needed to learn CGA"; the
long-term limit on adoption in planning firms is *the complexity of learning CGA and maintaining
rules across yearly updates.* Secondary but repeated: **tutorials are stale and no longer match
the current workflow**, so beginners cannot even follow them.

**The strongest corroboration is not a user quote — it's the vendor's behaviour.** Esri shipped a
node-based **Visual CGA Editor** in 2024.0, marketed explicitly as letting designers work
"without programming skills". After ~18 years of CGA, the company that invented the text grammar
replaced its front end with a node graph. Independently, Lipp et al. made this a research problem
in 2008, and Epic's 2010 solution was to hand artists a *graphically presented directed graph*
rather than rules to type.

> **Design consequence:** the authoring surface is the product. Any grammar we build must be
> authored the way [`citygen.md`](citygen.md) already assumes — parameters and graphs, not a
> bespoke text language we invent.

### Theme 2 — One generator = one look — ★★★ strongly corroborated, and Hannes' own finding

Hannes, on the *Procedural Lake House* series he owns (`F:\tutorials\Houdini\Procedural Lake
House`, cmiVFX vols 1–5 + Gumroad vols 2 & 4):

> a very sophisticated building generator but it generates a very specific look

That is the same conclusion Embark reached from the opposite direction — they refused a rigid
generator *because* one ruleset could not span Monaco, Bernal and Kyoto. And it is what the
academic critique of *Instant Architecture* said in 2006: realistic, style-accurate output, but
demonstrated only at town-square scale with an unclear variation ceiling — on a database of
~200 rules and 40 attributes for that one style.

> **Design consequence:** the style must live in **swappable data** (module libraries + rule
> fragments), never in the generator. A monolithic "building HDA" will silently become a
> Lake-House-shaped tool. This is the strongest argument in the survey for the composable
> Feature-Node shape over one big asset — and, separately, for
> [`citygen.md`](citygen.md) §4b's APEX `@subgraph` rule-fragment library.

### Theme 3 — Repetition and "lifeless" output; hero assets stay hand-made — ★★★ strongly corroborated

Recurs across environment-art discourse, developer roundups and the academic critiques alike:
procedural architecture reads lifeless and unrealistic — screwy proportions, dull colour, wrong
details; fine in distant background, exposed in wide cityscapes where repetition in *form* becomes
obvious; buildings are hard to generate precisely *because of their individuality*. The stated
remedy is consistent and near-universal: **hybrid**. Hand-made landmarks to break up procedural
mass, hand-authored hero facades, procedural everything else. Multiple marketplace generators
advertise exactly this seam — hand-placed overrides for hero facades in world space, which the
generator then declines to populate.

#### Correction after reading the primary source (2026-08-17)

The Polycount *Procedural cities* thread has now been **read in full** in a real browser. It
changes the claim in two ways, one weakening and one strengthening.

⚠️ **It is from October 2006.** It is nineteen artists reacting to Müller's original
CityEngine release, not current sentiment. Anything in it about output quality describes 2006
sample renders, not the method after twenty years of practice. I previously cited it as
corroboration without knowing its date; that was wrong.

⚠️ **The "lifeless" phrasing is one person, not a chorus.** It is **noritsune** (lvl 19): the
architecture shots are *"lifeless and unrealistic. The proportions are screwy... the colors are
dull... the details are wrong... it looks like a beginner's 3D building model"*, and wide
cityscapes *"just make the repetitions in the forms more obvious."* Also theirs: *"I'd probably end
up redoing everything to a point that took longer than if I had done it myself from the start."*
Weakly echoed by Eric Chadwick (*"some horrendous looking cities"*) and Sabby (*"blandness"*). One
strong voice plus two glances — not the consensus I implied.

✅ **What IS genuinely multi-voice — about six distinct posters — is the scope claim: background and
filler yes, hero buildings and playable space no.** Eric Chadwick (admin): *"a designer's touch
would still be needed"*, and he *"wouldn't expect a ground-level playable level from it, but could
be used for fly overs."* Mark Dygert (mod): *"the only thing I would use this for is background
noise outside of the playable area."* SHEPEIRO: *"even the best generated cities will not be able to
have the design and points of interest that a human touch can add."* JordanW: *"organizing lego like
pieces that an artist creates"* — an accurate description of split-and-fill — plus random level
generation *"is kinda dumb."* Joao Sapiro flags unexpected cleanup cost. malcolm gives the empirical
data point: Soldier of Fortune 2's random map generator was *"pretty boring since everything was
random and had no polish or design tuning."*

✅ **And the dissent is worth recording, because it won.** CrazyButcher (lvl 20): *"it is meant to be
a tool for artists... technology is there to aid, not to replace... I dont think you would like to
place every blade of grass manually"* — and he notes the output is *"not the 'same' house just
instanced."* okkun: *"Any tool that can take the grunt part out of the work is welcome."*

🎯 **The finding that actually matters.** EarthQuake (mod) specified the solution in 2006:
*"if you can throw in your own level layout, assets (textures and prefabs) and have tweakability on
each asset... this is VERY fucking cool. If only for filler content and non-important landmark
buildings... Of course this wouldnt be to replace awesomely designed intricate buildings."*
**Your own assets, per-asset tweakability, hero buildings excluded.** That is precisely what Embark
shipped eighteen years later (§4), and precisely what marketplace generators now advertise. The
artists named the requirements in 2006; the tools took two decades to meet them. Sabby also spotted
the two features that mattered — windows re-placing automatically when walls are scaled, and
*"morphing architectural styles"*.

> **Design consequence:** the "replace with unique hand-made geometry" affordance in
> [`citygen.md`](citygen.md) §1 is not a nice-to-have, it is the industry's only working answer to
> the field's most-cited failure. Silhouette variation deserves as much attention as facade detail.

### Theme 4 — Corners are the specific, concrete pain — ★★★ strongly corroborated, unusually specific

Multiple separate SideFX forum threads on the Labs Building Generator alone: corner *holes*;
convex/concave corner handling; the corners option for the "building from patterns" presets
reported **broken** (filling in corner module names has no effect); module misalignment producing
gaps because corners with different ledges shift to different depths. Artists route around it with
weighted variations. A separate recurring complaint: the Labs network's **complexity is daunting**
even to people intending to study and refactor it.

This is what makes corners interesting: it is the one failure mode where independent artists name
the *same node and the same parameter*, rather than expressing a general aesthetic dissatisfaction.

Corroborating from theory: corners are exactly what split grammars cannot express, because a split
operates within one face while a corner belongs to two. Epic's 2010 talk called out trim, roofs and
non-rectangular surfaces as the hard cases. Townscaper's WFC family is the one approach where
corner legality is structural rather than patched.

> **Design consequence:** corners, and the roof/wall/ground-floor junctions, are the acceptance
> test for any building prototype. If a candidate approach cannot close a corner cleanly on a
> non-rectangular footprint, it has not been demonstrated. Note the direct rhyme with
> [`citygen_streets.md`](citygen_streets.md): the multi-leg junction is the one open item blocking
> v1 streets. **In both subsystems the junction is the hard part, not the span.** That is a
> pattern worth taking seriously rather than a coincidence.

### Theme 5 — Tools die of bad interfaces, not bad geometry — ★★ moderately corroborated

The claim: hours perfecting a procedural tool end with it gathering dust because other artists
cannot understand the interface; complex node graphs and hidden parameters stall pipelines; a
complex HDA "feels like a black box" where each tweak is a guess. Prescriptions offered: expose
only essentials, name parameters clearly, sensible defaults, hide advanced options, version the
asset.

⚠️ Weaker sourcing — several of these articles come from the same publisher and may be one voice,
and the genre is advice-blog rather than practitioner report. **But** it agrees with two things
that *are* strongly sourced: Esri's Visual CGA pivot (Theme 1) and Embark's "get something usable
into artists' hands early, then iterate with them" (§4). Directionally trustworthy; do not quote
as consensus.

### Theme 6 — Downstream technical debt: UVs, LODs, interiors, performance — ★★ moderately corroborated

Scattered but consistent: UV layouts authored without LOD in mind degrade visibly, producing bake
artifacts and lightmap bleeding; hero assets need a TA to refine UVs by hand; generators typically
emit LOD0 and leave the LOD chain to engine or Houdini tooling. Blender-side, Buildify inherits
geometry-nodes performance limits (booleans are slow; many per-object modifiers make scenes slow),
and ships **no asset kits** — the user must supply the module library, which is a real barrier
that is easy to underestimate.

Most of this is game/real-time framing. [`citygen.md`](citygen.md) fixes our target as **offline
film rendering, no real-time engine** — so the LOD-chain and lightmap concerns largely do not apply
to us. **UVs do**, and Project Skylark treating UV as a named topic alongside half-edge topology
suggests it is not a detail. The "you must supply the module library" point applies to us in full.

---

## 6. What is genuinely unsolved

Distinct from "artists find it annoying". These are open in the literature *and* in the tools:

1. **Corners and junctions on non-rectangular footprints** — §5 Theme 4. The field's real open problem.
2. **Roofs beyond the simple cases.** Straight skeleton is the accepted base, and the weighted
   variants extend the style range, but complex/intersecting/dormered roofs on irregular footprints
   remain case-by-case. Named as hard by Epic in 2010 and still surfacing as a pain point.
3. **Style breadth from one system** — §5 Theme 2. Nobody has solved it; everybody sidesteps it by
   swapping the data.
4. **Interior/exterior consistency**, if interiors are ever required. Embark's answer was to change
   the geometry contract (watertight, pre-fractured, rule-consistent circulation), not to bolt
   interiors on.
5. **Editable neural generation.** Era 3 produces splats and point clouds. Nothing yet produces
   geometry that survives an artist clicking one window — which is [`citygen.md`](citygen.md) §1's
   founding requirement.

---

## 7. Footprint or envelope? — Hannes' two approaches

> we do get a base shape from the lot of the street generation, but depending on what i wanna do i
> either see this lot shape as the actual outline of the building or the allowed area in which we
> can place a building with a different outline

**Correct that they are not that different — and the field settled this.** They are the *same
approach with the identity operation as one special case.* CityEngine does not choose; it ships a
vocabulary of **lot → footprint operations** and the artist picks per lot:

| CGA operation | What it does |
|---|---|
| `setback` | inset selected edges by a distance — the per-edge, role-aware inset |
| `shapeL` / `shapeU` / `shapeO` | derive an L, U or O footprint by setting back a selected subset of edges |
| `offset` | uniform inward/outward inset |
| `convexify` | split a non-convex footprint into parts — used to give an L its two wings different heights |
| `extrude` | footprint → mass |

Their own tutorial pipeline is: *Parcel* applies a setback on all street sides → the street-side
strip becomes `OpenSpace`, the inner part becomes `Footprint` → extrude. So the lot is treated as
the **envelope**, and "footprint = lot outline" is just `setback(0)`.

**This is the right resolution for us, and it is already half-built.** §10a records that the
reference library's frontage/setback research establishes the buildable envelope as *a per-edge
inset keyed to each edge's ROLE* (front / side-street / interior side / rear / alley), with roles
not derivable from geometry — they come from which lot lines touch a street. That is strictly more
information than CGA's `setback` carries.

So: **one stage, `lot → footprint`, with a pluggable operation.** Identity is a legal choice, not a
separate architecture. Two consequences worth recording now:

1. **It is the natural style hook.** Which lot→footprint operation is legal is itself a style fact:
   a Viennese perimeter block is `setback(0)` on the street edges and an `O`/`U` toward the
   courtyard; an Austrian farmstead is a small footprint sitting *inside* a large envelope with a
   strong front setback; a US suburban house is `setback` asymmetric and forward on its lot. Same
   stage, different operation and parameters. That directly serves §8.
2. **It decides where the envelope caps bite.** Coverage and FAR are checked *after* the operation,
   so the operation must be free to fail and be retried or rejected — which means this stage needs
   the advisory-validation treatment ([`citygen_streets.md`](citygen_streets.md) §1 rule 3), not a
   hard constraint solver.

⚠️ Not researched: whether non-convex footprints survive our downstream facade splitting. §5 Theme 4
says corners are already the weak point, and `shapeL`/`shapeU` *manufacture* reflex corners on
purpose. Anything we build must be tested on an L before it is believed.

---

## 8. Architectural style — the variance problem

> i live on the countryside in austria and the buildings here look very different already compared
> to vienna [...] then i see like chinese or japanese buildings again different. then i see old
> buildings made of logs or like in the old egypt made of stone entirely.

This is the correct instinct and it is the field's real frontier. Findings, in the order they change
the design.

### 8a. Style taxonomies exist, and there are two incompatible kinds

**Art-historical / period taxonomy** — the "25 styles" of computer vision (Xu et al., ECCV 2014;
the standard benchmark, ~10k images; also *WikiChurches* for fine-grained). Gothic, Baroque,
Bauhaus, Deconstructivism… Useful for *classification and search*. **Nearly useless for
generation** — it labels appearance, not construction, and its categories are elite/monumental
buildings, which is not what a city is made of.

**Vernacular / typological taxonomy** — Paul Oliver's *Encyclopedia of Vernacular Architecture of
the World* (1997, 3 vols; 2nd ed. 6 vols), over a thousand cultures. Crucially, **Volume 1 is
organised by the axes we would actually parameterise**: *typologies*, *materials and building
resources*, *environment*, *symbolism and decoration*. This is the taxonomy to work from. It
describes exactly the span from Hannes' village to Vienna to Kyoto to log to stone.

**Hannes' own region is a worked example of why the vernacular axis is the right one.** Austrian
*Hausforschung* classifies by **whether functions share a roof**, not by ornament:
*Einhof/Einhaus* (dwelling + stable + hay under one roof — western Austria) vs *Paarhof* (two
buildings) vs *Gruppenhof* (scattered). Named regional types: **Bregenzerwälderhaus** (Einhof),
**Montafonerhaus** (mixed stone-and-timber, 15th–20th c.). Compare the German *Low German house*.
None of that is a facade style — it is a **topology of volumes and a construction system.** Vienna
differs from his village not in window trim but in *typological process*: perimeter block, party
walls, courtyard, four storeys.

> **Design consequence.** Style is not one parameter. At minimum it separates into:
> **(1) construction system** (log/Blockbau, timber frame/Fachwerk, mass masonry, post-and-beam,
> mud brick, RC frame) → **(2) volume topology** (one roof or many; party walls or free-standing;
> courtyard or not) → **(3) bay/opening rhythm** → **(4) roof form** → **(5) ornament and material
> finish**. Layers 1–2 are what makes Austria≠Vienna≠Kyoto. **Almost every surveyed tool only
> parameterises 3–5.** That is the actual reason procedural buildings read samey (§5 Theme 3):
> the tools vary the skin and hold the anatomy constant.

### 8b. Style-specific grammars exist, are proven, and are hand-written each time

This is the direct answer to *"which tools can generate this or that style and what they do"*. The
answer is: **rule sets, not tools** — and each is a research project.

| Style | Work | What it actually encodes |
|---|---|---|
| Palladian villas | **Stiny & Mitchell, 1978** — the landmark | Parametric shape grammar over 3×3 and 5×3 **plan grids**; enumerated complete catalogues; produced 230 new plans. Style as *plan topology* |
| F. L. Wright Prairie houses | **Koning & Eizenberg, 1981** | 99 rules. Starts from a **central fireplace** and additively places Froebel-block masses, then details. 89 basic compositional forms → 200+ designs. Style as *additive massing from a core* |
| Japanese minka / machiya / gassho-zukuri | **Watanabe, 2016** | Implemented **in CGA**, used in real heritage conservation. Each type keyed to a specific feature: minka = *irimoya* hip-and-gable roof; machiya = *koushi-mado* lattice window configuration; gassho-zukuri = the steep praying-hands roof |
| Chinese bracket sets (*dougong*) | *Dougong Revisited*, Shape Machine, 2024 | Parametric shape grammar for one **structural joint family** |
| Ancient Chinese timber frames | Liu, Zhang & Zhao, *Buildings* 15(18):3329, 2025 | Encodes **structural logic** — "column reduction" / "column relocation" — as parametric Grasshopper rules, gated by a **historical authenticity parameter**, validated in Karamba3D + Wallacei. ✅ read in full — **this is the most important source in the survey, see §9c2** |
| Chinese architecture from drawings | Stony Brook, TVCG 2011 | Drawing-driven grammar-based reconstruction |
| Roman masonry | *A Procedural Solution to Model Roman Masonry Structures* | Construction-technique-driven |
| Medieval / Gothic / sci-fi / fantasy | Marketplace HDAs and Blender geo-node kits (ArtStation, Gumroad) | Module libraries + a bespoke rule network per product. One notable Medieval generator drives massing with an **L-system**. **These are §5 Theme 2 in its purest form** — each is one look, sold as a tool |

Two things to take from this table. First: **style has been captured as rules many times, so it is
tractable.** Second: **every single one was hand-authored, and the interesting ones encode topology
or structure, not ornament** — a fireplace core, a plan grid, a roof type, a column rule. Nobody has
a general style *system*; they have N grammars.

And the field knows it lacks the library. A recurring, corroborated CityEngine community request is
for **a curated, shareable repository of rules** — *"CityEngine needs a repository of rules and
models, or a place the community can share those easily"*. Twenty years in, the missing piece is
not the engine, it is the **style library**. That is a direct warning about what our building
subsystem's actual deliverable is.

⚠️ Recorded caveat, because it applies to us: multiple researchers argue Koning & Eizenberg's
grammar captures Wright's *formal* properties while **excluding the social and functional
properties that arguably matter more**. A grammar that reproduces the look can still miss the
thing that generated it.

---

## 9. The tree analogy — can we simulate construction instead of describing style?

> for the trees we simulate what real life is doing and let the tree grow. maybe for a building we
> can figure out how materials behave and simulate how a building should be built to achieve the
> same look. maybe that is complete nonsense

**Not nonsense. Partly right, and wrong in a specific, useful way.** Verdict up front: the material
half fails, the *process* half is strong, and there is a defensible bounded version of the material
half. Detail below, because the reasons are the design.

### 9a. Why the tree approach works

Palubicki et al., *Self-organizing tree models for image synthesis*, SIGGRAPH 2009 (Calgary +
Adobe; Prusinkiewicz). The premise: **tree form emerges from a self-organising process dominated by
competition of buds and branches for light or space, regulated by internal signalling.** Simulate
that and a wide range of realistic trees falls out. Critically for us, it stayed art-directable —
procedural brushes, sketching, pruning, bending.

The reason this works is that the causal chain is **short and entirely physical**:
`light + gravity + hormonal signalling → form`. Nothing in the loop has an opinion.

### 9b. Three reasons the material→form version fails for buildings

Each of these is a load-bearing objection, and each is from the architectural literature rather
than from graphics.

1. **Form outlives its material cause — Semper's *Stoffwechsel* (1851/1861–63).** Semper's whole
   theory is that a structural form *originally bound to one method of processing gets transferred
   to another material, liberated from its original function.* Style, for Semper, is the record of
   those migrations. If form migrates across materials, **material cannot determine form.**
2. **The canonical example is the origin of Western architecture itself.** The *petrification*
   doctrine: the Doric order carries timber construction into stone. Triglyphs read as stylised
   **wooden beam-ends**, guttae as the **pegs** that secured them — skeuomorphs of a construction
   system the building no longer uses. A material simulation of stone would never produce them.
   ⚠️ Note this is Vitruvian tradition and is **archaeologically contested** — it copes poorly with
   late-Geometric/early-Archaic evidence, and the triglyph frieze is not actually demanded by timber
   logic. It is a strong illustration, not settled fact.
3. **Rapoport, *House Form and Culture* (1969), tested this hypothesis and rejected it.** His
   conclusion, still the standard position: house form is **not physically determined**; climate,
   materials and technology are **modifying factors**, and socio-cultural factors are determining.
   Explicitly: *materials in themselves do not seem to determine form, and changes of material do
   not necessarily change the form of the house.* The exact hypothesis, already falsified, in the
   field's most-cited book on precisely Hannes' question.

**So the chain for buildings is long and has culture in the middle:**
`material + climate + structure → space of possible forms → culture selects → form`.
Simulating the physics gives you the middle term, never the last.

### 9c. Where material→form *does* hold rigorously

Genuinely, and with production-grade tooling:

- **Compression-only masonry.** **Thrust Network Analysis** (Block & Ochsendorf, ETH Block Research
  Group) generates funicular compression-only vaulted surfaces under gravity within a defined
  envelope, from graphic statics extended to 3D via projective geometry, duality and linear
  optimisation. Open source as `compas_tna`; RhinoVAULT is the artist-facing form. **This is
  literally "let the material decide the shape", and for vaults and shells it is the correct
  method.** Arches, vaults, domes, cathedral shells — a real subset of buildings.
- **Assembly and fabrication constraints.** Assembly-aware masonry shell design; a 2025 framework
  for structurally-sound and fabrication-aware **modular timber** layouts that co-optimises beam
  placement and generates temporary supports to stay stable *during* assembly. Constructability as a
  generative constraint.
### 9c2. The two-layer model already exists, built, for one style — and it inverts the assumption

Liu, Zhang & Zhao, *Towards a Generative Frame System of Ancient Chinese Timber Architecture*,
**Buildings 15(18):3329, Sept 2025** (Chongqing University). Read in full. **This is the single most
important source in this survey**, because it is §9e's two-layer model actually implemented — and
its results contradict the intuition that motivates it.

**What they built.** A three-stage pipeline: *case-driven → generative system → simulation
validation*. Rhino 8 / Grasshopper + Python 3.10. A **Frame Generation Module** builds a raised-beam
structural line model from a user-supplied **column grid**. A **Frame Optimization Module** applies
structural strategies — ridge-support revision, insertion of inclined members, inclining originally
horizontal members, longitudinal truss formation. Evaluated in **Karamba3D** (FEA), cross-sections
searched with **Wallacei** (multi-objective GA) for self-weight vs maximum displacement.

**The part that matters for us: a `historical authenticity` parameter governs which structural
strategies are allowed to fire.** That is exactly the dial between "engineering-optimal" and
"historically correct", exposed as an artist parameter. And they calibrated it against a corpus of
Song→Qing buildings.

**The finding that inverts the assumption.** The historically authentic frame is *structurally bad*.
The orthogonal raised-beam system is **bending-dominated**: high stress at beam top and bottom
edges, the neutral axis barely stressed, capacity wasted, and span capped as a result. Craftsmen
knew and patched it **locally** — bigger sections, curved "moon" beams, decorative brackets — which
never fixed the load path, because "lacking systematic structural theories, craftsmen relied heavily
on empirical adjustments." The paper's own result: *"the performance ranking aligns with the
calibrated authenticity loss schedule"* — i.e. **structural gain is bought with authenticity loss,
monotonically.**

**And culture actively suppressed the better solution.** Inclined members are the structurally
efficient choice (they carry load axially rather than in bending) and they *existed early* in
Chinese timber building. But they are "notably unconventional within the orthogonal structural
system", and their use "gradually diverged" as construction became **more ritualized**. The
efficient answer was available, understood, and rejected for symbolic reasons over centuries.

> **This is the strongest evidence in the survey for §9b, and it comes from a structural engineering
> paper rather than from architectural theory.** Optimising the engineering does not converge on the
> historical style — it *diverges* from it, measurably. Style is not what you get when you simulate
> construction well; style is the **specific, culturally-chosen deviation from structural optimum**,
> and it has to be authored.

**Two more things worth stealing.** (1) Their historical layer is a *document*: the **Yingzao Fashi**
(1103 AD) codifies four column-grid types and nineteen hall layouts — a medieval rule book, i.e. the
"look it up through history" layer is often literally a written standard. (2) Their input is a
**column grid**, not a mass. Structure is authored first and the envelope follows.

⚠️ **Their stated limits:** line-model idealisation, simplified timber and joint behaviour,
**gravity-only loading**, and a modest historical corpus. They claim extensibility to other
traditional systems "via parameter and rule adaptation" — unproven for any second system.

- **Structural logic as style.** The above is the worked case. Also relevant: Wang et al.'s
  Grasshopper algorithm generating bracket sets and tiles per *Yingzao Fashi*, and Pu et al. using
  Bayesian networks to identify structural combinations from 3D model data.

**The generalisable core is span.** A material and a jointing system impose a maximum practical
span; span sets bay spacing; bay spacing sets the opening rhythm and the wall-to-window ratio; wall
thickness follows from mass-masonry stability. That chain is real, computable, and it is *why* mud
brick gives thick walls and small openings while timber trusses give wide bays. ⚠️ **This is my
reasoning, not a cited result** — I searched for a published vernacular span/bay table and did not
find one. Treat as a hypothesis to test, not a finding.

### 9d. The stronger analogy Hannes may be reaching for: growth, not material

Trees work because they are *grown*. **The building equivalent of growth is not material physics —
it is accretion over time**, and that *is* modelled, in two literatures:

- **Typo-morphology — the Italian school (Muratori 1950s; Caniggia & Maffei).** Its core is the
  **typological process**: urban form as the outcome of historical building processes, where
  elementary types evolve by **successive additions, subdivisions and adaptations**, from the basic
  dwelling up through aggregates to the whole organism. This is a *developmental* theory of building
  form — an L-system for buildings across generations rather than across a facade.
- **Graphics precedent.** Emilien et al., *Procedural Generation of Villages on Arbitrary Terrains*
  (2012), grows settlements from interest maps — a new road attracts settlers, a new house extends
  the road network — then segments parcels by anisotropic conquest and uses an **open shape grammar**
  that adapts geometry to local slope. And *Procedural Generation of Urban Environments through
  Space and Time* simulates urban models **over time**, scheduling development events by a
  **plausibility score function**.

**This is the honest answer to the analogy.** Hannes' farmhouse looks the way it does substantially
*because it grew* — an Einhaus accreting stable and hay barn under one roof, extended across
generations, adapted to slope. That is simulable in the same spirit as tree growth: a process with
local rules, running over time, with the artist pruning. Material physics is a *constraint* inside
that process, not the generator.

### 9e. Verdict

**Reject:** "simulate materials, get style." Semper, the Doric skeuomorph, and Rapoport all say the
mapping does not exist, and the last of those tested it directly.

**Adopt, as a hypothesis worth prototyping:** a **two-layer model** —

1. **A constraint layer that is simulated / derived.** Material + jointing + span + gravity define
   the *space of buildable forms*: legal spans, bay rhythms, wall thickness, roof pitch ranges,
   maximum storeys. Cheap to encode as a per-construction-system data block. TNA available where
   compression shells are actually wanted.
2. **A selection layer that is authored.** Which point in that space a culture picks — the
   typological choices of §8a layers 1–2, plus ornament. Rules and data, per style, in a library.

Then **style variation is mostly layer 1 data plus a small layer-2 grammar**, rather than a whole
new generator per look. That is the only route found in this survey that plausibly escapes §5
Theme 2 without hand-authoring N grammars — and it is consistent with what the successful
style grammars actually encoded (§8b: topology and structure, not ornament).

### 9f. What the style layer actually is — and why it is smaller than it feels

Hannes, 2026-08-17: *"this task feels so big to me that i have a hard time imagining the system
behind it and how it works."* Recorded because the feeling is justified and the answer is a
decomposition, not encouragement.

**First, the MDPI system is not our system.** It is a **heritage conservation and imitation-design**
tool. Its authenticity parameter measures *fidelity to historical fact*, and its optimiser wants
structural performance. Both are the wrong master for us. We take its *architecture* — generate from
structural rules, gate the rules by a named dial — and throw away its *objective*.

**Second, the two dials are one axis, and ours is longer.** MDPI's runs
`structural optimum ←→ historical authenticity`. Ours must run
`structural optimum ←→ historical authenticity ←→ whatever the art director wants`. Same axis,
extended past the end. Which is [`citygen.md`](citygen.md) §2.0 exactly: real-world data supplies
defaults, never limits.

**Third — the part that shrinks the problem.** A style is **not a generator**. It is a data block
read by the *same* pipeline. Sketch of the fields, all of them cascade defaults per
[`citygen.md`](citygen.md) §2.1 and all violations `warn` per §2.2:

| Field | Example: Hannes' Einhof | Example: Viennese perimeter block |
|---|---|---|
| `construction_system` | log (Blockbau) over masonry base | mass masonry, party walls |
| `span_limits` | timber length available → room width | vault/joist span → bay |
| `volume_topology` | **one** volume, three functions under one roof | party-walled perimeter + courtyard |
| `lot_to_footprint` | small footprint inside large envelope, front setback | `setback(0)` street side, `U`/`O` to courtyard |
| `bay_rhythm` | few, small, irregular openings | regular, tall, storey-differentiated |
| `roof_family` | steep gable, deep eaves | shallow, hidden behind parapet |
| `module_library` | ref | ref |
| `ornament_set` | may be structurally dishonest (§9b) | applied pilasters, stucco |

**So the "big system" = one pipeline (§1) + one schema (this table) + N template files.** The
pipeline is the same for every style. **N = 1 ships.** Adding Kyoto later is authoring a data file,
not extending the tool — and that is the whole point of §5 Theme 2 and §10 item 4.

**Precedent that this is the right shape.** The *Yingzao Fashi* (1103 AD) is literally a style
template document — four column-grid types, nineteen hall layouts, codified. CityEngine rule
packages are template files. §8b's finding stands: the mechanism has existed for decades; the
**library** is what nobody has.

⚠️ **The one field that genuinely resists being data: `volume_topology`.** The others are numbers,
ranges and references. Topology is a *graph* — how many volumes, which functions share a roof, party
wall or free-standing, courtyard or not — and each distinct graph needs its own assembly rule, not
just its own parameters. Honest estimate: the vernacular world is covered by a **small** number of
these (Einhof / Paarhof / Gruppenhof / row-and-party-wall / perimeter-and-courtyard / tower /
pavilion-and-veranda is already most of it), so this is *a small library of assembly rules plus
data*, not pure data. **This is the field to prototype first, because it is the one that could
invalidate the template idea.**

### 9g. Stress test — Babel and Coruscant

Hannes, 2026-08-17, challenging §9f: does this hold for fictional structures? Run deliberately,
because [`citygen.md`](citygen.md) already commits to *"Multi-level sci-fi — sky lanes, stacked
streets (Coruscant). Schema must not preclude it."* This is a requirement, not a hypothetical.

**The two cases test different things.** Babel is **real materials at impossible scale**. Coruscant
is **invented materials at impossible scale**. They break different stages.

| Stage | Babel | Coruscant | Verdict |
|---|---|---|---|
| Lot → envelope | fine | **breaks — no ground, no parcel** | ❌ see below |
| Footprint | ziggurat *is* repeated `setback` | needs `footprint(z)`, not one polygon | ⚠️ generalise |
| Mass | fine | FAR/coverage absurd → warn, don't block | ✅ house rule covers it |
| Structure | mud brick *has* a real height limit | no real limit — becomes authored | ✅ and see below |
| Facade | fine | fine — split grammars are recursive, so nested mega-bay → bay → window is free | ✅ |
| Roof | flat temple platform | towers don't have roofs | ⚠️ rename |
| Corners | ramp meets mass | + skybridges, merged towers | ❌ harder, same verdict |

**❌ The one real architectural break: the lot assumption.** Our whole chain is
*streets → blocks → lots → building*, which is **planar**. Coruscant has no ground plane and its
"streets" exist at many altitudes. Everything else in the pipeline generalises gracefully; this does
not. The fix is conceptually small and must be taken **in the schema now**, per
[`citygen.md`](citygen.md)'s own instruction: the building's input contract should be a **volume
with role-tagged faces**, not a polygon with role-tagged edges. §10a's per-edge role work
(front / side-street / interior side / rear / alley) still holds — it just needs to survive being
promoted to faces, and to admit roles our planar vocabulary has no word for (`sky-lane frontage`,
`underside`, `abuts-tower`). ⚠️ Unassessed: whether the frontage/setback research generalises to a
face, or only to a ground-level edge.

**⚠️ "Roof" is the wrong name for the stage.** The stage is *how the top closes* — of which a
pitched, straight-skeleton roof is the **vernacular case**. Flat, parapet, landing platform, spire,
and *continues upward into the next block* are equally legitimate terminations. Rename the stage
**cap / termination**, with roof as one strategy. Cheap to fix now, annoying later.

**✅ The structure layer survives, and the challenge argues *for* it rather than against it.**
Two distinct results:

- **Babel: the layer fires a warning, and the warning is the point.** Mud brick has a real
  compressive limit; that limit is why ziggurats are stepped and not towers. A structure layer would
  correctly report that Babel cannot stand — and per [`citygen.md`](citygen.md) §2.0 the artist
  overrides it and builds it anyway, with the warning persisted on the element. **This is the house
  rule working exactly as designed on the hardest possible case:** the tool knows the building is
  impossible, says so, and builds it.
- **Coruscant: the layer stops being derived and becomes authored — and that is where it earns
  most.** Invent a material with a 400 m span limit and the entire downstream chain — bay rhythm,
  wall thickness, storey height, taper — follows *consistently* from that one invention.
  **Internal structural consistency is the thing that makes invented architecture read as real**,
  and it is the one thing you cannot get by copying reference, because there is no reference to
  copy. For a real style you could skip the structure layer and just imitate photographs. For a
  fictional one you cannot. **The layer is more valuable for fiction, not less.**

**✅ The style template holds, with one substitution.** A fictional style is just another template
file. What changes is the *source* of its data: real styles source layer 2 from the vernacular
literature (§8a); fictional styles source it from concept art and art direction. The mechanism is
identical — only the lookup changes. Worth noting Coruscant is famously an **aesthetic** (verticality
+ Art Deco + Brutalist) rather than a construction system, which is precisely the layer-4/layer-1
split §9e already draws.

**Net.** Six of seven stages survive; one renames, one generalises, one **breaks and must be fixed
in the schema before it is written.** The two coral boxes stay coral, and corners get harder.
Nothing here invalidates the design — but the lot→volume question is now a **blocking schema
decision**, not a future nicety, and it belongs in [`citygen.md`](citygen.md) §7.

---

⚠️ **Status: hypothesis.** No surveyed system does this. It is assembled from parts that each work
separately. It should be prototyped on the narrowest possible pair — *Hannes' local Einhof vs a
Viennese perimeter block* — before any of it is believed. Two styles that differ in construction
system, volume topology and roof, from a region he can verify by looking out of the window, is a
far better first test than a generic "European city".

---

## 10. Where this leaves the building subsystem

Assessment, not a decision. Design still to be written.

1. **The approach is not in doubt.** Blockout/footprint → scope split → module fill → junction
   special-casing → roof. Twenty years of convergence. We should reimplement the canon, not search
   for a novel one. [`citygen.md`](citygen.md)'s "largest unknown" framing can be relaxed on the
   *algorithm* and tightened on the *authoring model*.
2. **Composable per-element nodes beat one building HDA.** Embark's Feature Nodes, Epic's
   designer/TA split, and Theme 2's style-lock problem all point the same way. This also happens to
   be the shape [`citygen.md`](citygen.md) §4b's APEX `@subgraph` idea wants.
3. **Corners are the acceptance test**, and they rhyme with the multi-leg junction already blocking
   v1 streets. Any prototype that dodges corners has proved nothing.
4. **Style lives in data.** Module libraries plus rule fragments, versioned and swappable. Hannes'
   Lake House observation is the design constraint, stated first-hand.
4b. **But style is deeper than the module library.** §8a: the tools that read samey vary the *skin*
   (bay rhythm, ornament, roof trim) and hold the *anatomy* constant (construction system, volume
   topology). Austria≠Vienna≠Kyoto is a layer-1/2 difference. **Our style data must reach
   construction system and volume topology, or we will have rebuilt the same failure with nicer
   modules.**
4c. **`lot → footprint` is one pluggable stage, not two architectures** (§7), and the choice of
   operation is itself a style fact. Identity is `setback(0)`.
4d. **The real deliverable may be the style library, not the generator** (§8b). Twenty years on,
   CityEngine's most-repeated community request is a shareable rule repository — the engine was
   never the bottleneck.
5. **The override path is the feature.** Contracts 1 and 2 are not overhead to be added later —
   §5 Themes 3 and 5 say they are the difference between a tool artists use and a tool that gathers
   dust. Embark's *Manual Module Node* is a concrete precedent, including where the edits are
   stored (geometry in geometry data parameters).
6. **We must supply a module library.** Buildify's biggest practical barrier is that it ships
   without one. Ours needs a real kit and the human-scale reference to build it against — the Lake
   House resources already carry that pattern (`modules/{body,roof,stairs,support,setdressing}`,
   plus `human_scale_reference.obj`).

### 10a. What we already hold locally

Checked against `polyfactory/resources/citygen/README.md` (gitignored; that file owns inventory and
literature, this one owns the survey). Three things matter:

1. **The input contract to the building subsystem is already researched and standards-backed.**
   The library's §4b item 3, *"Frontage, setbacks and the buildable envelope — the interface our
   building subsystem needs"*, already establishes: frontage measured on the **chord** of a curved
   front lot line; lot width checked **at the setback line, not at the street**; and critically that
   **the buildable envelope is a per-edge inset keyed to each edge's ROLE** (front / side-street /
   interior side / rear / alley) — roles *not derivable from geometry alone*, they come from which
   lot lines touch a street. Stacked on top: lot coverage, **FAR** and height. With published
   values noted as art-direction dials — *0.35 reads suburban, ~3 mid-rise, 10+ downtown.*
   → **The building subsystem does not start from a footprint. It starts from an asymmetric,
   role-tagged buildable envelope plus three volume caps.** That is a much better input than any
   surveyed tool takes, and it means the "mass" stage of §1's pipeline is largely pre-solved.
2. **The library already flags precisely this document's gap.** Its §3 item 2 reads: *"Wonka et al.
   2003 / Müller et al. 2006 (CGA shape grammars) — **do not have.** The building half. CGA is what
   CityEngine actually runs. Cited by Chen 2008. **Worth acquiring.**"* §2 above confirms that
   judgement: those two plus the SIGGRAPH Asia 2015 course are the acquisition list.
3. **A reference implementation is on disk** — the UE City Sample citygen HDAs include
   `otls/Building.hda` (300K), a `City_Lot_Processor` exposing building **style / height / size**,
   and caches named `BUILDING_SUBDIVIDED_LOT` and `BUILDING_DNA_POINT_CLOUD`. Note the shape of
   that: buildings carried as a **DNA point cloud** — per-building parameters as points, geometry
   derived later. That is the instancing-substrate question in [`citygen.md`](citygen.md) §7 item 1,
   answered by someone else's shipping pipeline, available to inspect.
   ⚠️ Caveat inherited from the library: its *street* side is kit-quantised (three road widths, a
   handful of legal angles) and judged **fundamentally incompatible** with our requirements. That
   verdict was reached about intersections; whether it also taints the building half is
   **unassessed**. Do not assume `Building.hda` is usable because it is present.

### Order of study before writing the design

1. **Project Skylark** building generator — free, current, H20.5, blockout-driven, and the closest
   available thing to what we need. Highest value per hour.
2. **`Cmivfx - Houdini Building Generation`** — owned locally, and per the library README it ships
   `building.hip` plus `Building.otl`, `buildingShape.otl` and **`DistributeFacadeModules.otl`**,
   with *two shape methods and two facade methods*. That is the §1 pipeline split into exactly the
   two halves this survey says matter, in a network we can open. **Start here for technique.**
   (Also `Houdini Procedural Modeling Of Cities`, 2 vols + `city.hip`.)
3. **Lake House vols 1–5** — owned. Study as the *sophisticated but style-locked* case (§5 Theme 2):
   the module/pattern division, and the wall-pattern and roof-shingle chapters. Its
   `modules/{body,roof,stairs,support,setdressing}` layout plus `human_scale_reference.obj` is a
   ready-made template for the module library we have to supply (§7 item 6).
3b. **UE City Sample `otls/Building.hda`** and the `BUILDING_DNA_POINT_CLOUD` cache — §10a item 3.
   Inspect for the per-building-parameters-as-points substrate, carrying the library's caveat.
4. **Labs Building Generator 4.0** — study and reimplement per [`citygen.md`](citygen.md) §5, with
   its known corner defects as the explicit list of things to do better.
5. **SIGGRAPH Asia 2015 course** *Practical grammar-based procedural modeling of architecture* —
   the canon in one document.
6. **Straight-skeleton roof papers** (Sugihara; Laycock & Day; weighted variants) — before any roof
   work. Note that **Labs gives us nothing here** (§3b): roofs are wholly ours, from scratch.
7. **Oliver, *Encyclopedia of Vernacular Architecture of the World*, Volume 1** — the typology /
   materials / environment / decoration volume. §8a says this is the right taxonomy to parameterise
   against. The single highest-value acquisition for the style problem.
8. **Rapoport, *House Form and Culture*** — short, and it is the direct refutation of the material
   hypothesis (§9b). Read before committing to any simulation-driven style plan.
9. **Watanabe 2016** (minka / machiya / gassho-zukuri **in CGA**) — the best available worked example
   of three genuinely different vernacular types in one grammar formalism.
10. **Emilien et al. 2012** (village growth) and the Caniggia/Muratori typological process — the
   growth/accretion model of §9d.

### The one prototype worth running

Not a generic building generator. **Hannes' local Einhof against a Viennese perimeter block.** They
differ in construction system, volume topology, roof form *and* lot→footprint operation — i.e. in
all the layers §8a says the tools normally hold constant — and Hannes can verify one of them by
looking out of the window (§5 Theme 3's remedy, and this project's own
*show-don't-tell* habit). If one system produces both convincingly, the two-layer hypothesis of §9e
has support. If it cannot, we have learned that cheaply.

---

## 11. Evidence quality

Honest accounting, per this project's rule that unverified claims are labelled.

**Verified by primary source read this session:** Embark's Building Creator architecture (SideFX
community article + 80.lv, though both trace to Embark — one *voice*, two publications);
Project Skylark's scope and technique list; Epic GDC 2010 session description; CityEngine 2024.0
Visual CGA Editor; `cityengine_for_houdini`'s single-building restriction; Wonka 2003 split
grammar including the control grammar and the ~200-rule/40-attribute figure (read from the
Kelly & McCabe survey PDF); the 2025 *3D Scene Generation* survey's paradigms and its stated
procedural strengths/weaknesses; *BuildingBlock*'s two-phase method.

**Corroborated across independent sources but read via search summaries, not primary threads:**
CityEngine's CGA learning-curve complaints; stale-tutorial complaint; the Labs Building Generator
corner defects; the repetition/"lifeless" theme; the hybrid-workflow consensus; text-to-3D
topology/UV failures.

**Both 403s were resolved 2026-08-17 in a real browser. Outcome: one source got better, one got
worse, and both had been mischaracterised.**
- ✅ **Polycount** *Procedural cities* — read in full. See the correction block in §5 Theme 3. It is
  genuinely multi-voice, but it is **from October 2006** and the "lifeless" line is a single poster.
  Net: the scope claim (filler yes / hero no) is now *properly* sourced with named posters; the
  output-quality claim is downgraded to one dated voice.
- ⚠️ **Esri** *City Engine Difficult UI* — reached, but it is **not** what I implied. It is a single
  **Ideas**-board submission by one user (RyanCartwright, now a deactivated account), status
  **Open**, with **3 comments**, one from an Esri Contributor. It is one person's feature request
  plus a vendor reply, **not a multi-voice complaint thread.** I listed it as one of my two best
  multi-voice artist sources; it never was one. Theme 1 does not depend on it — that theme's weight
  comes from Esri shipping the Visual CGA Editor — but the citation was overstated.
  ⚠️ The post body itself did not extract cleanly from the accessibility tree; I have its opening
  line (*"First and for most I love the idea of City Engine and its purpose…"*) and its metadata,
  not its full argument.

**Explicitly not verified:**
- **All GDC talks** — session descriptions only. No talk was watched. Spider-Man's pipeline in
  particular is asserted on four session abstracts.
- **Buildify's** performance limits — inferred from its documentation and general geometry-nodes
  issues, not from a corroborated body of user complaints.
- **Theme 5** sourcing is thin; see the warning inline.
- **Project Vitruvius** — absence of a release was searched for and not found. Absence of evidence.
- **The local library's building material** (§10a) is catalogued from its own README, which carries
  its own verification ledger. I did not open `Building.hda`, the cmiVFX `.otl`s, or any Lake House
  `.hip` this session. Read §10a as *inventory*, not as verified technique.

**Not attempted:** Discord and YouTube comment sentiment (not searchable with these tools);
non-English sources; paywalled GDC Vault video; the AI-and-Games Spider-Man article (paywalled).

### Ledger for the second pass (§§7–9)

**Verified by primary source read:** Labs Building Generator 4.0 has no roof generation — read from
the 4.0 node docs, only a decorative *Top Ledge* (Hannes' correction, confirmed).

**Verified from vendor documentation:** the CGA `setback` / `shapeL` / `shapeU` / `shapeO` /
`offset` / `convexify` vocabulary and the Parcel→OpenSpace/Footprint→extrude tutorial pipeline.

**Corroborated, read via search summaries of primary literature (abstracts, catalogue entries,
review articles) rather than the works themselves:** Stiny & Mitchell's Palladian grammar (3×3 and
5×3 grids, 230 plans); Koning & Eizenberg's Prairie grammar (99 rules, fireplace core, Froebel
blocks, 89→200+ designs) *and* the published criticism of it; Watanabe 2016's three Japanese types
in CGA with their identifying features; Palubicki et al. 2009's premise and its interactive
controls; Semper's four elements and *Stoffwechsel*; Rapoport's rejection of climate/material
determinism; the petrification doctrine **and its contested status**; Thrust Network Analysis and
`compas_tna`; Oliver's *Encyclopedia* structure incl. Volume 1's organisation; Caniggia/Muratori's
typological process; Emilien et al. 2012's three-step village method; the Austrian
*Einhof/Paarhof/Gruppenhof* distinction and the Bregenzerwälderhaus / Montafonerhaus types; the
Xu et al. 25-style benchmark.

**Explicitly not verified:**
- **No book in §§8–9 was read.** Oliver, Rapoport, Semper, Caniggia & Maffei are all characterised
  from secondary sources. The characterisations are consistent across sources, but they are
  second-hand and these are the load-bearing citations of §9.
- ~~The Chinese timber-frame paper returned 403~~ — **resolved: read in full, now §9c2**, the most
  load-bearing source in §9. Its own stated limits (line-model idealisation, simplified joints,
  gravity-only loading, modest corpus) are recorded there.
- **§9c's span → bay → opening-rhythm chain is my own reasoning, labelled as such inline.** I
  searched for a published vernacular span/bay dimensional table and did not find one. It is a
  hypothesis to test.
- **§9e's two-layer model is a synthesis, not a survey finding.** No system does this.
- **No claim in §8b about marketplace style generators** rests on having opened one.

## 12. Design spec v0 — for later pickup

Written 2026-08-17, at the end of the research session, so an agent can start the building
subsystem without re-deriving §§1–11. **This is a spec, not a build order to start today** —
streets v1 still has priority ([`citygen.md`](citygen.md) §7 blocker), and §12.10's gates come
before any stage implementation.

### 12.0 How to pick this up

1. Read [`citygen.md`](citygen.md) §§1–2 (vision, art-direction contracts) and §5 (Labs policy),
   then [`citygen_streets.md`](citygen_streets.md) §1 (hard constraints) and §S8 (lots — the
   upstream producer). Then this file: §1, §5, §9f, §9g. Then
   `polyfactory/resources/citygen/README.md` (gitignored, local).
2. Houdini work starts with `houdini_get_skill("houdini-dev-loop")` — not optional — plus
   `houdini-procedural-modeling` and `houdini-tool-design` before B-stage or parameter work.
3. Run the gates (§12.10) before building stages. Verification is a **viewport repro scene**, not a
   test name — build the thing and look at it, per this project's habit.
4. Nothing may depend on a Labs node at runtime. Study, fork, reimplement.

### 12.1 Scope and non-goals

**v1 delivers:** exterior building shells, generated per lot from the streets chain, in ≥2 genuinely
different styles from one pipeline; instanced, per-element editable, offline-render target.

**Explicit non-goals for v1** (each with the reason):
- **Interiors** — no requirement in [`citygen.md`](citygen.md) §1. ⚠️ If ever required, the geometry
  contract changes wholesale (watertight, circulation rules — Embark, §4). Decide then, not now.
- **LOD chains** — offline film target, §5 Theme 6.
- **Structural simulation (FEA/TNA)** — the structure layer is **table-driven** in v1 (§12.6 B3).
  TNA is a future option for vaults/shells only.
- **Neural/LLM generation** — §2 Era 3 verdict: wrong output format for editability.
- **Building-to-building junctions** (skybridges, merged towers) — v2, but B6 must not preclude
  them (§9g).

### 12.2 Inherited constraints — binding, with sources

| Constraint | Source |
|---|---|
| 100% vanilla Houdini; Labs = study only | [`citygen_streets.md`](citygen_streets.md) §1 |
| Metric metres; offline render; cached topology | [`citygen.md`](citygen.md) §1 |
| No constants — override cascade, 6 levels, last wins | [`citygen.md`](citygen.md) §2.1 |
| Validation advisory: `block`/`warn`/`ignore` + global allow-invalid; warnings persisted on elements | [`citygen.md`](citygen.md) §2.2 |
| Every stage separately runnable, paintable/editable input, one-button full path | [`citygen.md`](citygen.md) §2.3 |
| **Start realistic, end artistic** — real-world data = defaults, never limits | [`citygen.md`](citygen.md) §2.0 |
| Standard vocabulary (bay, eave, parapet, party wall…), own implementation | [`citygen_streets.md`](citygen_streets.md) §1 rule 4 |
| Data format: Houdini attributes, not JSON | [`citygen.md`](citygen.md) §7 resolved list |
| Every instance supports swap and replace | [`citygen.md`](citygen.md) §1 |

### 12.3 Architecture

**One pipeline, N style template files, two rails.** The generator never knows which style it is
making; it reads a template. Composable **feature nodes** (Embark's model, §4), not one monolithic
HDA — an object-level assembly containing SOP-level nodes per architectural element, each
independently usable, each with its own override hooks.

Stage chain, mirroring the streets S-numbering:

```
B0 site contract → B1 footprint → B2 mass → B3 structure → B4 facade → B5 cap → B6 junctions & finalize
```

Corners/junctions are a **first-class stage (B6), not a patch inside B4/B5** — deliberate, because
junctions are the failure point of every surveyed tool (§5 Theme 4) and of our own streets design
(S5a). One stage owns every seam.

### 12.4 B0 — the site contract

**Input is a volume with role-tagged faces.** The planar lot from streets S8 is the degenerate
case: lot polygon extruded to the envelope height, side faces inheriting the lot-edge roles,
`+skyLane`/`underside`/`abuts` reserved for the multi-level future. This resolves
[`citygen.md`](citygen.md) §7 item 0 in the forward-compatible direction (§9g) while costing the
planar case nothing — **proposed here, to be ratified when the schema is written.**

⚠️ **The names below were corrected 2026-08-26 (G1).** The first draft of this
table declared `siteId` / `faceRole` / `setback` / `styleTemplate` / `seed` with **no prefix**,
which [`conventions.md`](conventions.md) §1 makes illegal on anything that leaves a node — flat
`pf_` prefix, descriptive name. The corrected spellings are law and B0 must ship these.
**Template FIELD names are a different thing and are deliberately left alone**: `styleId`,
`volumeTopology`, `lotToFootprint` (§12.5) are keys inside a data file, not Houdini attributes,
and §1 governs attributes.

| Attr | Type | Content |
|---|---|---|
| `pf_site_id` | int — **detail** on a single-site stream, **prim** once a stream carries several sites | stable identity, from streets element identity. ⚠️ G1 cooks four buildings in one stream and therefore carries it per prim; the two forms must stay interchangeable, and B0 owns the conversion |
| `pf_face_role` | string — **prim** on the volume's faces (§12.4's volume form), **vertex** on the degenerate planar lot, where the role belongs to an EDGE and vertex is the only class that can hold one value per edge | `front` · `sideStreet` · `interiorSide` · `rear` · `alley` · `sky` · `skyLane` · `underside` · `abuts` |
| `pf_setback` | vertex/prim, float | per-face inset **authored override**, cascade level 5 — present ⇒ it wins over the template's per-role number, absent ⇒ the template supplies it (§2.1: never *compute* alone) |
| `pf_coverage_max`, `pf_far_max`, `pf_height_max` | detail, float | envelope caps — **advisory** (§2.2). ⚠️ **not implemented by G1** |
| `pf_style_template` | prim/detail, string | template id; resolvable through the cascade (zone default → region → per-site) |
| `pf_seed` | int | per-site determinism: same seed + template + overrides ⇒ identical geometry |
| ground sample | input 2 | optional heightfield/prims for slope — Einhof plinths, Emilien-style slope adaptation |

⚠️ Open (§9g): whether the frontage-measured-on-chord / width-at-setback-line rules (§10a)
generalise from ground-level edges to arbitrary faces. Planar v1 does not need the answer; the
schema must not block it.

### 12.5 The style template

A template is **data + a small set of rule references** — never code of its own (§5 Theme 2,
§9f). Stored Houdini-native (geometry file carrying detail dict attributes + packed module prims),
per the attributes-not-JSON decision. Missing field ⇒ cascade default, so a template may be sparse.

✅ **Tested at its weakest point and it held** — see §12.10a. ⚠️ **Two things this table gets wrong
about its own field names, both worth fixing in a reader's head before using it.** First, the keys
below are **template fields, not Houdini attributes**, so `conventions.md` §1's `pf_` law does not
apply to them and they stay camelCase; §12.4's table, which really was attributes, was corrected.
Second, a template records **provenance per FIELD, not per template**: `sources` in the shipped
templates is a list of one line per number, each saying SOURCED with a URL, DERIVED with the
reasoning, or **UNSOURCED**. That last word is doing real work — the first pass at these templates
was about to commit two numbers that a search returned confidently and that do not exist in the
documents they were attributed to.

| Field | Type | Notes |
|---|---|---|
| `styleId`, `version`, `sources` | meta | `sources` = provenance list; every template records where its numbers came from (this file's evidence-ledger discipline applies to style data too) |
| `constructionSystem` | ref → data block | see B3 table below. **Input to** the engineering, §9e layer 1 |
| `volumeTopology` | assembly rules + params + an ordered `volumes` list | ✅ **Decided by G1 (§12.10a), and the shape is not what this row expected.** There is no "topology library" keyed by type name — an `Einhof` entry and a `perimeterCourtyard` entry would each have been one style's code wearing a rule's name. What there is instead: `rails` (`bar`/`ring`), `cutsAt`, `courtyardDepthM`, `plinth`, and `volumes[]` carrying `role`/`storeys`/`storeyHeightM`/`capGroup`. A farmhouse and an apartment block pick the same rails |
| `lotToFootprint` | op + per-role params | `setback` / `shapeL` / `shapeU` / `shapeO` / `offset` / `identity` (§7) |
| `bayRhythm` | spec | regular/irregular, openings-per-bay, per-storey differentiation (ground floor ≠ upper), wall-to-window ratio |
| `capFamily` | strategy + params | renamed from "roof" per §9g: `skeletonRoof` (pitch range, eave depth) · `flat` · `parapet` · `platform` · `spire` · `continueUp` |
| `moduleLibrary` | ref → kit manifest | §12.9 |
| `ornamentSet` | ref | **may reference a different construction system than the structural one** — skeuomorphs are legal and required (Doric case, §9b) |

**No scalar "authenticity dial" in v1.** The MDPI paper gates rules by an authenticity parameter
(§9c2); for us **the override cascade already is that dial** — template values are the authentic
defaults, overrides are the artistic end. Adding a second mechanism would duplicate §2.1.
Per-rule gating can be revisited if a template ever needs "loose vs strict" modes.

### 12.6 Stage specs

Each stage: separately runnable HDA; consumes B(n−1) output + template fields + cascade; every
value overridable; violations `warn` + persist. Only the deciding details are specced here.

**B1 footprint.** Applies `lotToFootprint` per face role inside the setback envelope.
`identity` = `setback(0)`. Output: footprint polygon(s) + `pf_face_role` tags carried from the lot
edges. Corner lots honoured (`cornerAngleMax` from the streets lot work). Non-convex output is
**legal and expected** — it is B6's acceptance input. Caps checked here and at B2: exceed ⇒
`pf_warn_coverage_exceeded` / `pf_warn_far_exceeded`, never a refusal.

⚠️ **G1 built the `setback` op only, and it is NOT `polyexpand2d`.** Measured on 22.0.398: that
node is the native offsetter, it computes a straight skeleton, it survives non-convex input, its
per-edge Inside Scale really does give non-uniform offsets — **and it treats a non-positive scale
as 1**, so a `setback(0)` street edge silently becomes a 1 m one. That is precisely the Viennese
perimeter block, so B1 uses `pf_inset.vfl` (offset lines of the two edges at a corner,
intersected), which also preserves corner correspondence index-for-index and so carries the edge
roles through for free. **Revisit `polyexpand2d` for the non-zero, non-convex cases** — and note
its Edge Distance Attribute is documented as "raise the roof", i.e. a real head start for B5.
`shapeL` / `shapeU` / `shapeO` / `offset` are **not built**; the courtyard that `shapeO` would cut
is produced in B2 by insetting the footprint a second time with the same rule.

**B2 mass.** Assembles volumes per `volumeTopology`: how many volumes, which functions share a
roof, party walls, courtyard; plinth/foundation adaptation to the ground sample. Output: massing
volumes with `pf_volume_role` (dwelling/stable/barn/stair…) and shared-wall tags. ⚠️ This is the
stage gate G1 exists for. **G1 ran 2026-08-26 and PASSED** — the skeleton is built, see §12.10.

**B3 structure.** **Table-driven, no simulation.** Reads the `constructionSystem` block:

| Field | Example (Blockbau) | Example (mass masonry) |
|---|---|---|
| `maxSpanM` | ~6 (log length) | vault/joist table |
| `bayRangeM` | derived from log lengths | regular, from joist span |
| `wallThicknessM` | log Ø | thick, storey-dependent |
| `maxStoreys` | 2–3 | 4–6 |
| `storeyHeightRangeM` | low | tall, ground floor taller |
| `capPitchRangeDeg` | steep | shallow/parapet |

Output: bay grid (`pf_bay_u`/`pf_bay_v`) on each volume face, storey splits, wall thickness — the
inputs B4 and B5 consume. ⚠️ **B3 owns per-STOREY heights**, and that seam is already load-bearing:
B2 gives a volume one height, so the sourced Gründerzeit fact that the ground floor is taller than
the floors above it is **not expressible until B3 exists** and is recorded in
`at_vienna_perimeter`'s provenance as a known gap rather than averaged away silently.
Exceeding a limit ⇒ `pf_warn_span_exceeded` etc., persisted; the geometry is still
built (Babel case, §9g). Fictional systems are just authored blocks (Coruscant case). ⚠️ The
span→bay chain is this survey's own hypothesis (§9c flag) — G1/G2 double as its first test.

**B4 facade.** The canon (§1): per face, split scopes along the B3 bay grid per `bayRhythm`,
recursive subdivision, fill from the module library. Hero-facade override: a face tagged
`heroFacade` is left untouched or takes hand geometry (the 2006 Polycount requirement, §5 Theme 3
correction, shipped by Embark). Module UVs preserved; generated wall surfaces get seam-stable UVs
(Skylark treats UVs as first-class — study before writing this).

**B5 cap.** Strategy per `capFamily`. `skeletonRoof` = our own straight-skeleton implementation
(§2 Era 1 papers; weighted variants later for style range). **Labs offers nothing here** (§3b) —
this is written from scratch, and it is the second-largest work item after B6. Output includes
tagged eave/verge/ridge edges for B6.

**B6 junctions & finalize.** Owns **every seam**: wall corners (convex and reflex), facade↔cap
(eaves, gables), mass↔mass (party walls, courtyard inner corners), building↔terrain (plinth), and
— reserved, v2 — building↔building. Strategies per seam class: corner module from the kit, trim
piece, or computed patch; selectable through the cascade. Also the finalize pass: instancing
(packed prims + per-building DNA point carrying `styleTemplate`/`seed`/override refs — the City
Sample pattern, §10a; substrate decision stays with [`citygen.md`](citygen.md) §7 item 1),
warning collation, `elem_id` stamping.

### 12.7 Identity and overrides

Every emitted element (module instance, wall panel, corner piece, cap face) carries a stable
`pf_elem_id` derived from `pf_site_id` + stage + structural address (volume/face/bay/storey),
**not** from generation order — so a recook with identical inputs yields identical ids, and the
override layer (keyed by `pf_elem_id`, [`citygen.md`](citygen.md) Contract 2) survives
regeneration. ⚠️ **`pf_elem_id` is a STRING address and its STORAGE is part of the contract**
(D223) — it is the same spelling and the same kind of value as polyChain's `pc_elem_id`, which
`conventions.md` §3 renames to `pf_elem_id` after its parity pass, and sharing the name here is
deliberate (§1: a genuinely shared contract should be spelled the same way).
**Built and checked at G1**: B2 emits `<site>:B2:v<k>` per volume and `<site>:B2:v<k>:<face slot>`
per face, where the face slot is `outer`/`inner`/`crossA`/`crossB`/`cap`/`floor` — structural, and
independent of the winding the cell happened to be built with. The check that guards it cooks the
same lots in the **opposite order** and requires an identical id set. Override kinds,
all per §2.1 level 5–6: parameter override, module **swap** (variant), geometry **replace**
(hand-made), and `heroFacade` face tags.

### 12.8 Warnings

Per §2.2, persisted as attributes on the offending element, viewport-visualisable. Names corrected
to the `pf_` law 2026-08-26 with the rest of §12. Initial set:
`pf_warn_span_exceeded`, `pf_warn_coverage_exceeded`, `pf_warn_far_exceeded`,
`pf_warn_storeys_exceeded`, `pf_warn_unbuildable_corner`, `pf_warn_footprint_collapsed`
(offset degenerate → OBB fallback, §10a), `pf_warn_module_missing` (kit gap — build a blank
stand-in, never fail).

**Shipping from B2 after G1**, all prim ints, all advisory, none of them ever a refusal:

| Warning | Fires when | What is built instead |
|---|---|---|
| `pf_warn_footprint_collapsed` | an inset flipped the polygon's signed area or collapsed it — setback deeper than the lot, or courtyard tract deeper than half the block | ONE solid volume; when it is the footprint that folded, built on the **lot** shape stashed before the offset, since building on the folded polygon puts the building outside its own lot. §12.8 above says "OBB fallback"; the lot polygon is the OBB's own input and never worse |
| `pf_warn_topology_arity` | the template's `volumes` list is not as long as the cell count the rails produced | roles/storeys/cap groups cycle over the list |
| `pf_warn_cap_group_split` | two volumes are told to share a roof and disagree on eave height | both are built at their own heights; ⭐ **this is the one that gives "which functions share a roof" teeth** — without it a cap group is a label nobody checks |
| `pf_warn_unknown_rule` | a template names a rule the library does not have | the default rule is used |

⚠️ **§12.8's other half is not built and is not B2's to build**: these are attributes, and nothing
yet *visualises* them for an artist. That collides with the same open item §0.0d already records
against polyChain's invisible `addWarning` route, and it belongs to the B-stage HDA work.

### 12.9 Module library contract

We ship kits; the tool is unusable without them (Buildify's lesson, §10 item 6). Per kit:
manifest (geometry file, detail attrs) listing modules with `moduleRole`
(window/door/cornerPiece/eave/…), nominal bay size, and cut geometry where the module needs a wall
opening (Lake House `*_cut_*` pattern). `human_scale_reference` mandatory in every kit. Naming
follows the Lake House layout (`modules/{body,cap,stairs,support,setdressing}`) with correct
architectural names (Embark's naming lesson, §4).

### 12.10 Prototype gates — in order, before any B-stage build

- **G1 — topology as data.** ✅ **PASSED 2026-08-26.** Skeleton B2 only. Full result in §12.10a.
  Pass criterion was: both massings emerge from one assembly-rule library + two data files, judged
  in the viewport. Fail: each needs bespoke code ⇒ shrink §12.5's claim to "small rule library +
  data" and re-scope. **§12.5's claim stands as written.**
- **G2 — corner closure.** L-shaped footprint (`shapeL`), walls + `skeletonRoof` cap, through
  B4–B6 at prototype quality. Pass: no holes or misalignments at any convex/reflex corner or
  eave/gable seam, viewport-verified. This is the acceptance test the whole survey points at
  (§5 Theme 4); run it **before** polishing anything.
- **G3 — APEX vs VEX/SOP for rule fragments** ([`citygen.md`](citygen.md) §4b): only after G1+G2,
  using the G1 templates as the test corpus. Fallback is plain SOP/VEX feature nodes; APEX must
  earn its place.

Build order after gates: B0+B1 (thin — most of it exists in the S8 interface) → B3 minimal tables →
B4 → B5 → B6 hardening throughout → finalize/instancing. B2 arrives from G1.

### 12.10a G1 result — topology as data: PASS

**Verdict: `volumeTopology` is data.** Both required massings, and two more, are produced by one
rule library reading four template files. No production source contains a style id — asserted, not
asserted-about: `no_style_branching` greps every shipped `.vfl` and `buildings.py` for every
template id and fails on a hit.

**What was built.** `polyfactory/vex/citygen/pf_mass.vfl` (the rules, a detail wrangle — one
execution over every building in the stream, whatever style each of them is), `pf_inset.vfl`,
`pf_area0.vfl`, `pf_collapse.vfl`, `pf_yard_inset.vfl`;
`polyfactory/scripts/python/polyfactory/citygen/buildings.py` (template load, cascade,
marshalling, network build); `devScripts/create_pf_building_styles.py` →
`polyfactory/library/citygen/styles/*.geo`; checks in `tests/citygen/checks_buildings.py` and
`tests/citygen/run_building_checks.py` with `baseline_buildings.json`.
⚠️ **Both the builder script and the template files sit under git-ignored paths** (`devScripts/`,
`polyfactory/library/`) and were force-added, following the precedent of `create_pf_polychain*.py`.

**The rule vocabulary — four rules, and every one of them serves more than one style:**

| Rule | What it is | Data it reads |
|---|---|---|
| **rails** | two matched point chains spanning the footprint. `bar` = the two long opposite edges of a 4-gon, sampled at the cut fractions. `ring` = the boundary and its courtyard inset, edge for edge | `rails`, `cutsAt`, `courtyardDepthM` |
| **zip** | one cell per rail interval. Consecutive cells share their cross face — **that face IS the party wall, found by construction rather than searched for** | — |
| **prism** | a cell extruded between two datums, every face tagged at creation with the rail it came from, the site role it inherits and the volume it is shared with | `volumes[].role/storeys/storeyHeightM/capGroup` |
| **plinth** | `none`, or `levelToHighest` — one floor datum for the whole building at the highest ground under it, each cell's skirt following the ground down to its own lowest corner | `plinth.mode`, `plinth.minM` |

**Why four templates and not the two the gate names — this is the part that makes the PASS mean
something.** With two templates every rule is used exactly once, and a rule used once is that
template's code wearing a rule's name; the gate would pass vacuously. So the fixture crosses the
family line: **`at_vierkanthof`, an Upper Austrian farm, is built on the perimeter block's `ring`;
`at_zinshaus_row`, a Viennese apartment house, is built on the farmhouse's `bar`.** The check
`rule_reuse` enumerates every value every rule takes and **fails if any is reached by fewer than
two distinct `styleId`s**. Its mutation — the Vierkanthof stops using `ring` — reddens it.

**Honest limits of that argument, and the auditor sharpened two of them.** Reuse is necessary, not
sufficient: two styles could use one rule for architecturally identical buildings. `rails` remains
the one rule with mode-specific code — measured by the audit at ~20 lines `bar` and ~18 `ring`
against ~165 shared downstream, i.e. **~80 % shared** — and the mode is chosen by a data value, not
by a style name. It is genuinely *four* styles, not four families: two Austrian rural, two Viennese
urban. ⚠️ **And `rule_reuse` is weaker than it reads**: of its four rows, `lotToFootprint` is
`setback` in every shipped template and so can never be lonely, and `cuts` is perfectly collinear
with `rails`. **What carries the argument is the 2×2 CROSSING in the fixture** — bar/ring against
`levelToHighest`/`none`, with a farm and an urban block in each column, so `rails` is orthogonal to
farm-vs-urban rather than rigged — **not the check's count.**

**Decisions this gate closes** (they were §12.12 open questions):
1. **`volumeTopology` representation** = an ordered `volumes` list plus a rails/cuts/plinth rule
   selection. Not a graph structure — the adjacency that matters (who shares a wall, who shares a
   roof) is the cell ORDER plus `capGroup`, and both fall out of the rails.
2. **Style template storage format** = a `.geo` carrying the whole template as one detail
   **dictionary** attribute `pf_style_template`. Round-trips losslessly on 22.0.398 (measured;
   note lists come back as tuples), needs no parser at cook time, ~6 KB, and unlike JSON it can
   carry §12.9's packed module prims in the same file when kits arrive. ⚠️ It also carries a
   Houdini `info` block with hostname and date, so rebuilding a template churns its diff.

**What G1 did NOT test, and must not be read as having tested:** no facade, roof, module or
ornament (B4/B5/B6); no HDA, so nothing is driven through a parameter face and none of
`artist_ui.md` §6b applies yet; **no non-convex footprint and no corner lot** — every fixture lot is
a rectangle, which is exactly what G2 stops being; and the storey/cut numbers that could not be
sourced are placeholders, listed as such inside each template's own `sources` field.

**Carried into the next stages, from the audit:**
- `stamp()` loops over VERTICES in Python to write `_inset`. Cheap today (measured above) and the
  first thing to move to VEX if B1 grows.
- `pf_mass` is a **detail** wrangle, so it is a single-threaded serial loop over buildings.
  Irrelevant at 0.044 s for 400 buildings; worth knowing before B5/B6 pile work into it.
- `_merge` treats a dict-valued field as a NAMESPACE, so `setbackM` can be added to but never
  wholesale replaced by an override. Decided deliberately — an override raising the front setback
  must not drop the other three roles — and now stated in the code.

**Evidence.** 16 checks, each paired in a registry with the exact edit that reddens it, 17
mutations, all seen RED. Images at `tests/citygen/gate_images_buildings/` (regenerable, not
committed — the same convention as `tests/polychain/gate_images/`), coloured by `pf_wall_role` so
the party walls and the courtyard — the topology itself — are what the picture actually shows.
⚠️ **An AGENT looked at those images, not Hannes.** Every gate owes a HUMAN viewport pass and this
one is still owed (§0.0 Gates row).
⚠️ **THE SIZE BUDGET, STATED WITH ITS DENOMINATOR — and the breach is 1.53×, not 8 %.** Round 2
recounted it and found the 8 % figure was obtained by putting `devScripts/create_pf_building_styles.py`
in the denominator. That script is a one-shot **data-authoring** tool whose output — the four `.geo`
templates — is the thing under test, and ~70 % of its 255 code lines are source-citation string
literals. Prose in the denominator is not production code, and the same argument that excludes the
tests' docstrings excludes it. **The budget is therefore: test ≤ production, both counted as
non-blank, non-comment, non-docstring source lines, over the artefacts B2 ships.**

| | raw lines | code lines |
|---|---|---|
| production — `buildings.py` + the five `.vfl` | 729 | **433** |
| tests — `checks_buildings.py` + `run_building_checks.py` | 1 108 | **661** |
| **ratio** | 1.52× | **1.53×** |
| *(for reference, with the template builder folded in)* | *1.08×* | *0.96×* |

✅ **Both round-2 auditors recounted this independently and got the same numbers** (729 / 1 108) and
independently rejected the template builder from the denominator for the same reason. The figure is
not in dispute.

**Verdict: over budget by half, and the `testing` skill's "delete before adding" now binds.** It is
not an argument for deleting the mutation registry or the "what this cannot see" lines — the
dev-loop skill mandates both. It IS the reason the missing oracles named below must be *paid for*,
not merely appended: G2 inherits this suite. **The concrete deletion list lives in §0.0f** (~45–50
lines, more than the overrun) and is not repeated here; add `image_contains_subject` to it, which
buys back nothing as written because it cannot fail (R2-2).

⚠️ Whatever is decided, **the runner must print the ratio** so it cannot drift unstated again.

**Independently audited on the current build**, per Rule 0. The auditor signed the verdict above —
"no style id anywhere in production source, and no proxy branch either" — measured the cost curve
(4 / 100 / 400 buildings: marshalling 0.001 / 0.006 / 0.018 s, whole chain 0.011 / 0.019 / 0.044 s,
linear at ~45 µs/building, so CLAUDE.md rule 4's batching holds), confirmed the storage contract
off the cooked output, and looked at the geometry. It then **broke four of the checks**, and that
is the more useful half.

**Defects found by mutation and by audit — recorded because every one is a shape that recurs:**
1. **Houdini's polygon normal is the NEGATIVE of the ordinary cross product of its edges** —
   measured on 22.0.398 after all 78 faces of the first build shipped inside out, which renders
   and measures identically and only shows up as backface shading.
2. **A docstring is not an assertion.** `encloses_courtyard` claimed the courtyard "lies inside the
   outer walls" and never tested it — depth 0 made the whole 2 728 m² footprint read as a
   courtyard. Adding a built-band term closed that ONE case: the auditor then slid the courtyard
   4 m sideways, wrecking the wings under it, and **both areas came back byte-identical**, because
   a rigid translation preserves every area there is. Containment was not enough either — the
   shifted block was still 8 m inside its outer wall. What works is a **differential oracle**: the
   built tract depth re-derived against `courtyardDepthM`, reading 8 and 16 where 12 was asked for.
3. **A fixture property was load-bearing without saying so.** Three checks keyed on style, which
   worked only while every style had exactly one lot. Adding a second Einhof lot made two of the
   three gate criteria FAIL on correct geometry. Everything keys on `pf_site_id` now — and the
   image code had the identical bug.
4. **A collapse test that catches one inversion does not catch two.** The sign flip missed a double
   inversion: a 17 × 26 m lot produced a 3 402 m² "footprint", unflagged, massed outside its own
   lot. Area that *grew* is now the proof, since an inward offset can only reduce area. ⚠️ And
   **strictly** grew — `>=` flags `setback(0)`, which is §12.6 B1's identity op and what both
   Viennese templates use, and it silently degraded two perimeter blocks to one solid mass each
   with every other check green.
5. **A name is not a value.** `pf_warn_footprint_collapsed` and `pf_warn_unknown_rule` were stamped
   on the footprint prim, and `removeprim` keeps an attribute's *definition* while dropping its
   value — so every shipped face read 0 whatever happened upstream, and the published-names
   baseline listed both warnings and looked correct.
6. **A volume can vanish in silence.** `pfb_cell` refuses a non-positive height and returns; the
   auditor measured 7 volumes built where 13 were expected with the suite green, because every
   check reasoned about the volumes that exist. `volume_count_matches` is the one that reasons
   about the ones that do not — and it must be told which sites are *expected* to degrade, because
   the first version read that off the warning and so believed the code's own account of itself.
7. **The `.geo` round trip is not lossless**, and this doc's format decision was about to be
   ratified on that sentence. A numeric list of length 2, 3 or 4 returns as a `hou.Vector2/3/4`;
   other lengths return a tuple. `load()` normalises it; nothing may read the raw attribute.

#### Round 2 (independent, 2026-08-26) — the question is answered, the gate is withheld

⚠️ **TWO round-2 audits ran independently on this build and did not know of each other.** The other
one's queue is **§0.0f** and it is the operational owner — its defect 1 **blocks the gate** and was
**independently reproduced here**: a *legal* cascade level-6 override (20 × 10 lot; front 0,
sideStreet 25, rear 12, alley 0) inverts both axes, `pf_collapse.vfl`'s three guards all stay
silent because a double inversion restores the sign *and shrinks* the area (+200 → +10), and the
result is **3 volumes, 18 faces at x −5..0, z −2..0 — entirely outside a lot at x 0..20, z 0..10 —
with `pf_warn_footprint_collapsed` = 0 on every face** and `outward_normals`, `party_walls_real`,
`no_scratch` all green. §12.10a's "Area that *grew* is now the proof" is **false as written**.
The two audits agree on the budget (1.53×) and on `pf_warn_topology_arity` / `STORAGE`; this
section records only what §0.0f does not, and **§0.0f wins on anything the two disagree about.**

⚠️ **§0.0f defect 1 and R2-1 below are one root cause seen from two sides**: nothing in this suite
asserts where the mass is or how big it is in plan. Fixing only the `pf_collapse` guard leaves the
blind spot; fixing only the checks leaves a building outside its lot unwarned at cook time. Both.

This audit re-ran the gate and attacked it with 20 mutations the registry had never tried. What was
re-verified first: all 16 checks green, all 17 registered mutations still RED, and three things
measured rather than assumed —

- **The 2×2 crossing is genuine, not nominal.** The decisive test is not `rule_reuse`'s count but
  forcing each template onto the *other* mode: `at_einhof` (a bar farm) run with `rails: ring` +
  `courtyardDepthM 1.5` built a correct 4-cell courtyard farm; `at_vienna_perimeter` run with
  `rails: bar` + three cuts built a correct 4-cell bar with `end` walls. **Neither rail branch
  depends on anything else in the template it usually arrives with**, which is the property
  "a rule, not a style's code" actually names. `rails` × `plinth` is a true 2×2 and `rails` is
  orthogonal to farm-vs-urban.
- **§12.4's determinism clause holds**, and it was previously untested. A canonical digest of every
  prim's 18 attributes and every point at full float repr is byte-identical across a second build,
  a forced re-cook of the same node, a template reload from disk, and **a separate hython process**.
- **Plan geometry is correct where it was checked by hand**: the Einhof footprint is 5 × 45 m inside
  a 10 × 90 m lot (the sourced "5 Meter breit"), cut at 0.444/0.722 → a 20 m Wohnteil (the sourced
  "20 Meter lang"); the Vierkanthof is 54 × 30 m (the sourced measured example). **Correct, and
  nothing in the suite asserts any of it** — see R2-1.

**Defects, ranked. The first is the same shape as round 1's courtyard defect and is worse.**

**R2-1 — THE SUITE CANNOT SEE THE MASS'S PLAN DIMENSIONS AT ALL.** Not the footprint, not the cuts.
Proven with a mutation to *shipped production code*, not to a template: making `pf_mass.vfl` cut the
bar at **half** the fraction asked (`append(ts, cuts[c] * 0.5)`) moves the Einhof's volumes from
0.444/0.722 to 0.222/0.361 — the dwelling halves from 20 m to 10 m and the barn grows from 12.5 m to
28.8 m — and **all 16 checks and the baseline stay green.** Likewise `pf_inset.vfl` applying half the
setback it is handed puts sites 1 and 3 metres out of place and reddens only `encloses_courtyard`,
and only *incidentally*: that file also performs the courtyard inset, so a fault confined to B1's
setback pass would be wholly invisible. Template-side proof of the same hole: `at_einhof`'s rear
setback 43 → 10 m (a farmhouse 45 m long becoming 78 m) is green with the baseline unmoved, and cuts
→ `[0.05, 0.10]` (a 2 m dwelling) likewise. **Root cause:** every check measures topology, height or
identity; `heights_follow_data` is the only differential oracle against the template and it measures
Y alone. The baseline records `volumes/faces/roles/capGroups/wallRoles/topY` — **no plan quantity**.
Two oracles close it, both written and proven RED against those two production mutations while green
on the clean build: `footprint_follows_setbacks` (lot rectangle minus the per-role setback table,
re-derived from the data file) and `cuts_follow_data` (each volume's extent along the long axis
against `cutsAt`). ⚠️ First drafts of both read the template through the mutation harness's own
patched `B.load`, so oracle and geometry moved together and both passed on a build they existed to
reject — **a template-side mutation cannot prove a template-reading check; only a production-side one
can.** That trap is why R2-1 survived round 1.

**R2-2 — `image_contains_subject` cannot fail.** `rasterise` builds exactly one segment per vertex
per prim and returns `len(segs)`; the check compares that against `sum(len(p.vertices()))`. The two
are the same number by construction, so `drawn >= edges` is an identity — measured 336 vs 336, and
an **8 × 8 pixel** rendering of the same geometry still reports PASS. It is also the one check
deliberately exempted from the mutation registry, so nobody ever tried to redden it. It must assert
on the written PNG's ink coverage or be deleted; as written it reads as coverage and is decoration.
This is dev-loop §8's own example failing in the file that cites it.

**R2-3 — `pf_warn_topology_arity` is a published name with no assertion, and it is RAISED on the
clean gate build.** Site 5 ships `pf_warn_topology_arity = 1` (3 declared volumes, 1 degraded cell)
and no check reads the attribute. Nailing it shut in production (`warnarity = (0 && ...)`) leaves the
suite green and the baseline unmoved. Round 1's defect 5 ("a name is not a value") was fixed for
three warnings and this fourth one was missed.

**R2-4 — D223 is enforced on 13 of the 18 prim attributes B2 ships,** and `attribute_storage`'s
docstring claims "every id B2 mints is enrolled here from day one" while **`pf_seed` — an id, and a
§12.4 contract row — is not enrolled**, along with all four warnings. Measured: shipping
`pf_warn_topology_arity` as a float leaves `attribute_storage` **green**; only the baseline diff
catches it, and a baseline diff is a human reading a list, not an assertion of the contract. (The
other four resist a storage change only because `stamp()` or `pf_collapse` created them as `Int`
upstream and VEX coerces into an existing attribute — an accident of node order, not a check.)

**R2-5 — `stamp()` clobbers a per-site seed, so §12.4's determinism row is unimplemented.**
`pf_seed` is read from the *template* (`tpl.get("seed", 0)`, a key no template and no `DEFAULTS`
entry defines, so it is always 0) and written over every lot prim. Measured: a lot arriving from B0
carrying `pf_seed = 4242` ships as `0`. §12.4 specifies `pf_seed` as a **per-site** input meaning
"same seed + template + overrides ⇒ identical geometry"; B2 currently overwrites the site's seed with
a constant. Harmless today (nothing consumes it), a silent B0 seam breakage the moment anything does.

**R2-6 — `pf_warn_footprint_collapsed` fires on footprints that did not collapse.** `pf_mass` stamps
`degraded ? 1 : collapsed`, conflating "the offset folded through itself" with "the rails rule could
not run". Trigger: a 5-gon lot with `at_zinshaus_row`, whose setbacks are **0 on every role** — the
inset is provably the identity, yet the output carries `pf_warn_footprint_collapsed = 1`. §12.8 wants
warnings an artist can act on; this one sends them to the wrong cause. The correct signal
(`pf_warn_topology_arity`) is raised alongside it and, per R2-3, is unchecked.

**R2-7 — `plinth.minM` is not measured.** `plinth_follows_ground` asserts one datum, more than one
skirt depth, and `min(depths) > TOL`; the ground itself varies, so the depths vary whatever `minM`
is. Setting it to `0.0` or to `25.0` (buildings sunk 25 m) is green with the baseline unmoved. The
check is also run on site 1 only, so the Vierkanthof's `levelToHighest` is never exercised by it.

**Not defects, checked and cleared:** no proxy branch for a style exists in production (every branch
is on `rails`, `plinth`, `n == 4` or `collapsed`); `_merge`, `_plain` and the cascade behave as
documented; `no_scratch` covers all four attribute classes and all four group types; `elem_ids_structural`
is genuinely order-independent; the 5-gon degraded path never leaves its lot.

**Round-2 verdict.** ✅ **`volumeTopology` is data — CONFIRMED**, on stronger evidence than round 1
had, and the second auditor concurs. ⛔ **But the GATE is withheld, and both auditors reached that
independently.** "The gate produces the right *topology*" is established; **"the gate produces the
right *buildings*" is not, and a legal override currently produces one outside its own lot.**
§12.10a must not be read as having tested more than topology. R2-1 and §0.0f defect 1 must both be
closed before G2, because **G2's L-footprint is a *plan* claim and this suite cannot see one.**

### 12.11 v1 acceptance

1. Einhof and perimeter-block generated by the same pipeline, differing **only** in template file.
2. G2's L-footprint closure holds in the shipped version, plus roofs on non-rectangular footprints
   — i.e. strictly more than Labs (which breaks corners and has no roofs at all, §3b).
3. Any generated value overridable at any cascade level; a per-element edit and a `replace` both
   survive a full recook; warnings persisted and visible.
4. Per-instance swap/replace works at building scale (feeds the §7-item-1 instancing prototype).
5. Every claim demonstrated as a **viewport repro scene**, and independently audited on the current
   build before being called done (dev-loop rule).

### 12.12 Open questions carried into the build

| Question | Where it lands |
|---|---|
| Face-role generalisation of frontage rules | B0; ratify with schema |
| ~~`volumeTopology` representation~~ | ✅ **DECIDED by G1, §12.10a**: ordered `volumes` list + rails/cuts/plinth rule selection |
| Corner strategy per seam class | G2 informs; B6 |
| APEX or SOP/VEX for rule fragments | G3 |
| Instancing substrate | [`citygen.md`](citygen.md) §7 item 1, joint with streets |
| ~~Style template storage format detail~~ | ✅ **DECIDED by G1, §12.10a**: `.geo` + one detail dict attribute `pf_style_template` |
| **NEW — per-storey heights** | B3. B2 gives a volume ONE height, so "the Gründerzeit ground floor is taller" is sourced and inexpressible today (§12.6 B3) |
| **NEW — how a warning reaches an artist** | B-stage HDA. §12.8's attributes exist; nothing visualises them, and this is the same open item §0.0d records against polyChain |
| Straight-skeleton: own implementation scope (weighted? holes?) | B5 design |

---

## Sources

Papers and surveys
- [Müller et al., *Procedural modeling of buildings*, SIGGRAPH 2006](https://dl.acm.org/doi/10.1145/1141911.1141931) · [SIGGRAPH history entry](https://history.siggraph.org/learning/procedural-modeling-of-buildings-by-muller-wonka-haegler-ulmer-and-gool/)
- [Wu et al., *Inverse Procedural Modeling of Facade Layouts*](https://dl.acm.org/doi/10.1145/2601097.2601162) · [arXiv](https://arxiv.org/pdf/1308.0419)
- [*Practical grammar-based procedural modeling of architecture*, SIGGRAPH Asia 2015 course](https://dl.acm.org/doi/10.1145/2818143.2818152)
- [Kelly & McCabe, *A Survey of Procedural Techniques for City Generation*](https://www.citygen.net/files/images/Procedural_City_Generation_Survey.pdf) — source for the Wonka 2003 detail
- [*3D Scene Generation: A Survey*, 2025](https://arxiv.org/html/2505.05474v1)
- [*BuildingBlock: A Hybrid Approach for Structured Building Generation*, 2025](https://arxiv.org/abs/2505.04051)
- [*Proc-GS: Procedural Building Generation for City Assembly with 3D Gaussians*, 2024](https://arxiv.org/html/2412.07660v1)
- [*Computer-Aided Layout Generation for Building Design: A Review*, 2025](https://arxiv.org/pdf/2504.09694)
- [*A Survey on Deep Learning for Design and Generation of Virtual Architecture*, ACM CSUR 2024](https://dl.acm.org/doi/10.1145/3688569)
- [*Straight Skeleton Computation Optimized for Roof Model Generation*](https://www.semanticscholar.org/paper/989d2b0fca889b45d6b4094736047e409d954957) · [Laycock & Day, *Automatically Generating Roof Models from Building Footprints*](https://www.semanticscholar.org/paper/17caae184a7ee6965dd067a1368f6de31fe77de8) · [weighted straight skeletons](https://www.sciencedirect.com/science/article/pii/S0010448517301240)
- [*Procedural Generation of Buildings with Wave Function Collapse* (BA thesis, HAW Hamburg)](https://reposit.haw-hamburg.de/bitstream/20.500.12738/15709/1/BA_Procedural%20Generation%20of%20Buildings_geschw%C3%A4rzt.pdf)

Style, typology and the material question (§§7–9)
- [CGA reference index](https://esri.github.io/cityengine-sdk/html/cgaref/cgareference/cgaindex.html) · [`shapeU`](https://doc.arcgis.com/en/cityengine/2021.0/cga/cga-shapeu.htm) · [`shapeO`](https://doc.arcgis.com/en/cityengine/latest/cga/cga-shapeo.htm) · [Tutorial 8: Mass modeling](https://doc.arcgis.com/en/cityengine/2023.0/tutorials/tutorial-8-mass-modeling.htm)
- [Stiny & Mitchell, *The Palladian grammar*, 1978](https://journals.sagepub.com/doi/abs/10.1068/b050005) · [full text PDF](http://www.contrib.andrew.cmu.edu/~ramesh/teaching/course/48-747/subFrames/readings/Stiny&MItchell-1978-EPB5_5-18.ThePalladianGrammar.pdf) · [*Counting Palladian Plans*](https://journals.sagepub.com/doi/abs/10.1068/b050189) · [a later alternative subdivision grammar](https://papers.cumincad.org/data/works/att/ijac201210404.pdf)
- [Koning & Eizenberg, *The Language of the Prairie*, 1981](https://journals.sagepub.com/doi/10.1068/b080295) · [Semantic Scholar](https://www.semanticscholar.org/paper/6fad56784cc2c996722f37d45339468edc44f860) · [a later plan-graph + massing grammar treatment](https://link.springer.com/article/10.1007/s00004-017-0333-0)
- [Watanabe, *Minka, Machiya, and Gassho-Zukuri: Procedural Generation of Japanese Traditional Houses*, 2016](https://repozitorium.omikk.bme.hu/items/905327e2-91a2-404b-a347-d6dd947d0648)
- [*Dougong Revisited: A Parametric Specification of Chinese Bracket Design in Shape Machine*, 2024](https://link.springer.com/chapter/10.1007/978-3-031-71918-9_15) · [*Drawing-based Procedural Modeling of Chinese Architectures*, TVCG 2011](https://www3.cs.stonybrook.edu/~qin/research/2011-tvcg-chinese-architecture.pdf) · [Liu, Zhang & Zhao, *Towards a Generative Frame System of Ancient Chinese Timber Architecture*, Buildings 15(18):3329, 2025](https://www.mdpi.com/2075-5309/15/18/3329) ✅ read in full — **see §9c2**
- [Palubicki et al., *Self-organizing tree models for image synthesis*, SIGGRAPH 2009](https://algorithmicbotany.org/papers/selforg.sig2009.html) · [PDF](https://algorithmicbotany.org/papers/selforg.sig2009.small.pdf)
- [Rapoport, *House Form and Culture*, 1969 — review](https://www.re-thinkingthefuture.com/rtf-architectural-reviews/a4568-book-in-focus-house-form-and-culture-by-amos-rapoport/) · [*Theoretical Inspirations of Amos Rapoport*](https://isvshome.com/pdf/Amos%20Rapoport%20Paper.pdf)
- [Semper, *The Four Elements of Architecture*, 1851](https://en.wikipedia.org/wiki/The_Four_Elements_of_Architecture) · [Charitonidou on *Stoffwechsel*](https://www.researchgate.net/publication/348907413) · [Moravánszky, *Metamorphism: Material Change in Architecture*](https://catalog.princeton.edu/catalog/10704285)
- [Doric order / petrification](https://en.wikipedia.org/wiki/Doric_order) · [*Tripods, Triglyphs, and the Origin of the Doric Frieze*, AJA 2002](https://doi.org/10.2307/4126279) — the contesting view
- [Oliver, *Encyclopedia of Vernacular Architecture of the World*, 1997](https://en.wikipedia.org/wiki/Encyclopedia_of_Vernacular_Architecture_of_the_World) · [Cambridge UP](https://www.cambridge.org/us/universitypress/subjects/arts-theatre-culture/architecture/encyclopedia-vernacular-architecture-world) · [Internet Archive](https://archive.org/details/encyclopediaofve0001unse_z0h2)
- [Block & Ochsendorf, *Thrust Network Analysis*, IASS 2007](https://web.mit.edu/masonry/thrustNetwork/papers/IASS07_block+ochsendorf.pdf) · [*TNA for Masonry Assessment* (CISM 2023)](https://www.block.arch.ethz.ch/brg/files/MAIA_2023_CISM_thrust-network-analysis-for-masonry-assessment_1692790965.pdf) · [Block Research Group / `compas_tna`](https://github.com/BlockResearchGroup)
- [*A Computational Framework for Structurally-Sound and Fabrication-Aware Layouts of Modular Timber Assemblies*, 2025](https://www.researchgate.net/publication/400868661) · [*Assembly-aware design of masonry shell structures*](https://www.researchgate.net/publication/320188621)
- [*From Muratori to Caniggia: the origins and development of the Italian school of design typology*](https://www.academia.edu/100669339/From_Muratori_to_Caniggia_the_origins_and_development_of_the_Italian_school_of_design_typology) · [*Saverio Muratori and the Italian school of planning typology*](https://www.researchgate.net/publication/242156734)
- [Emilien, Bernhardt & Cani, *Procedural Generation of Villages on Arbitrary Terrains*, 2012](https://perso.liris.cnrs.fr/egalin/Articles/2012-villages.pdf) · [HAL](https://inria.hal.science/hal-00694525) · [*Procedural Generation of Urban Environments through Space and Time*](https://www.researchgate.net/publication/230778858)
- Style classification: [Xu et al., ECCV 2014 (25 styles)](https://www.researchgate.net/publication/275604099) · [25-style dataset](https://github.com/dumitrux/architectural-style-recognition) · [*WikiChurches*](https://arxiv.org/pdf/2108.06959)
- Austrian / German vernacular typology: [Bregenzerwälderhaus](https://en.wikipedia.org/wiki/Bregenzerw%C3%A4lderhaus) · [Montafonerhaus](https://en.wikipedia.org/wiki/Montafonerhaus) · [Low German house](https://en.wikipedia.org/wiki/Low_German_house) · [Vernacular architecture in Germany — Fachwerk](https://www.makeheritagefun.com/vernacular-architecture-germany-fachwerk-grunderzeit/)
- Style-specific marketplace generators: [Gothic Building Generator (Houdini+Blender)](https://b_adman.artstation.com/projects/xJr60E) · [Medieval Building Generator, L-system driven (Houdini)](https://www.artstation.com/artwork/qQmolz) · [SciFi Building Generator HDA](https://www.artstation.com/marketplace/p/J9jy/scifi-building-generator) · [Fantasy Building Generator (Blender geo nodes)](https://gladeforge.gumroad.com/l/FantasyBuildingGenerator)

Production case studies
- [Making the Procedural Buildings of THE FINALS (SideFX)](https://www.sidefx.com/community/making-the-procedural-buildings-of-the-finals-using-houdini/) · [80.lv coverage](https://80.lv/articles/how-embark-studios-built-procedural-environments-for-the-finals-using-houdini)
- [GDC 2010, James Golding (Epic), *Building Blocks: Artist Driven Procedural Buildings*](https://gdcvault.com/play/1012655/Building-Blocks-Artist-Driven-Procedural)
- [GDC 2019, *Marvel's Spider-Man: A Technical Postmortem*](https://www.gdcvault.com/play/1026496/-Marvel-s-Spider-Man) · [Procedural Lighting Tools](https://www.gdcvault.com/play/1026315/-Marvel-s-Spider-Man) · [Look Creation of Manhattan](https://www.gdcvault.com/play/1026495/-Marvel-s-Spider-Man)
- [How Townscaper Works (Game Developer)](https://www.gamedeveloper.com/game-platforms/how-townscaper-works-a-story-four-games-in-the-making)

Tools
- [SideFX Project Skylark — Building Generator](https://www.sidefx.com/tutorials/project-skylark-building-generator/) · [CG Channel coverage](https://www.cgchannel.com/2025/06/download-free-houdini-tools-and-assets-from-sidefxs-project-skylark/)
- [Labs Building Generator 4.0 docs](https://www.sidefx.com/docs/houdini/nodes/sop/labs--building_generator-4.0.html)
- [What's new in CityEngine 2024.0 (Visual CGA Editor)](https://doc.arcgis.com/en/cityengine/latest/whats-new/cityengine-2024-0-whats-new.htm) · [CityEngine 2025.1 release (CG Channel)](https://www.cgchannel.com/2025/12/esri-releases-cityengine-2025/) · [cityengine_for_houdini](https://esri.github.io/cityengine/houdini)
- [iToo RailClone](https://www.itoosoft.com/railclone) · [Mastering Procedural Modelling in 3ds Max](https://www.itoosoft.com/tutorials/mastering-procedural-modelling-in-3ds-max)
- [Buildify (CG Channel)](https://www.cgchannel.com/2022/07/download-free-blender-3d-building-generator-buildify/) · [BlenderNation](https://www.blendernation.com/2022/07/19/buildify-free-city-creation-add-on-with-geometry-nodes-and-osm/) · [Buildify docs](https://studylib.net/doc/26162800/buildify-1.0)
- [SceneCity](http://www.cgchan.com/) · [KitBash3D Cargo](https://kitbash3d.com/pages/cargo) · [Polygonflow Dash (CGPress)](https://cgpress.org/archives/polygonflow-launches-dash-a-user-friendly-tool-for-3d-world-building-in-unreal-engine.html)
- [Unreal PCG overview](https://dev.epicgames.com/documentation/unreal-engine/procedural-content-generation-overview?lang=en-US) · [PCG grammar tutorial](https://dev.epicgames.com/community/learning/tutorials/9d3a/unreal-engine-pcg-grammer-tutorial-procedural-building-generator) · [Procedural Worldbuilding mit Unreal (Digital Production)](https://digitalproduction.com/2024/05/28/procedural-worldbuilding-mit-unreal/)

Artist sentiment
- [Polycount — *Procedural cities*](https://polycount.com/discussion/44850/procedural-cities) ✅ read in full 2026-08-17 — **note: October 2006**
- [Esri Community — *City Engine Difficult UI*](https://community.esri.com/t5/arcgis-cityengine-ideas/city-engine-difficult-ui-user-interface/idi-p/940153) ⚠️ reached — single Ideas post + 3 comments, not a complaint thread · [CityEngine Rules thread](https://community.esri.com/t5/arcgis-cityengine-questions/cityengine-rules/td-p/859158)
- [ArcGIS CityEngine review (Flypix)](https://flypix.ai/arcgis-cityengine-tool-review/)
- SideFX forum, Labs Building Generator: [corner holes](https://www.sidefx.com/forum/post/308577/) · [convex/concave corners](https://www.sidefx.com/forum/post/374851/) · [different patterns per side](https://www.sidefx.com/forum/topic/102108/) · [top floor](https://www.sidefx.com/forum/topic/85158/)
- [Devs weigh in on how to use (but not abuse) procedural generation](https://www.gamedeveloper.com/design/devs-weigh-in-on-the-best-ways-to-use-but-not-abuse-procedural-generation)
- [The Siren Song of Procedural Generation (Wayline)](https://www.wayline.io/blog/procedural-generation-artistic-vision) · [How to Build a HDA That Any Non-Houdini Artist Can Use](https://www.artivoxa.com/how-to-build-a-hda-that-any-non-houdini-artist-can-use/) ⚠️ Theme 5, thin sourcing
- [Sloyd review 2026](https://onyxranked.com/sloyd-review-2026/) · [Tripo P1.0 in a UE5 pipeline](https://www.strayspark.studio/blog/tripo-p1-ai-3d-assets-ue5-pipeline/)
- 80.lv building-generator interviews: [Andrew Guan](https://80.lv/articles/learn-how-to-make-procedural-building-generator-in-houdini) · [cyberpunk building](https://80.lv/articles/001agt-006sdf-making-a-procedural-cyberpunk-building-in-houdini) · [Beijing buildings](https://80.lv/articles/006sdf-procedural-beijing-buildings-in-houdini) · [realistic procedural architecture](https://80.lv/articles/realistic-procedural-architecture-for-games)
