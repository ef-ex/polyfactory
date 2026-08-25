# polyfactory tests — the v2 regime (2026-08-25)

**Why v2:** v1 grew to 27 162 lines guarding a tool that turned out to be 14 682
(the retrospective's "~6 000" was never measured), with 80-minute mutation sweeps.
It caught real bugs, but by accretion: every audit added checks, nothing was ever deleted, and the
machinery itself became the main cost (and, twice, the main defect). v2 replaces accretion with
four standard techniques. The incident evidence is `ideas/build_retrospective.md`.

## The five pieces

1. **One oracle: differential testing against the reference.** The Python reference implementation
   IS the baseline. One generic comparator — every attribute, every value, storage, order,
   groups — over both paths. Comparing EVERYTHING by construction is what makes it impossible to
   forget an attribute (the `_snapshot`-by-name defect class). This replaces the recorded-value
   baselines and most bespoke assertions in `checks.py`. Golden numbers survive only where a
   number IS the contract (a gate criterion, a measured ceiling).
2. **Generated inputs, not hand fixtures.** Hypothesis for the pure-Python solve; a seeded scene
   generator for hython (curves with random corners, duplicate points, shared points, attribute
   storages, non-ASCII ids). Every fixture-blindness miss in the retrospective — shared points,
   int `edge_id`, absent variants — was "no fixture reached it"; generation attacks that
   mechanically, and shrinks failures to minimal repros.
3. **Google's mutation policy: changed code per cycle, everything at milestones.** Google runs
   mutation analysis per-changelist, on changed+covered lines only, arid lines filtered, mutants
   per line capped. Ours: per cycle, run only registry entries whose touched files changed
   (entries already carry digests) plus `mutmut` (coverage-guided, incremental) over the changed
   pure-Python kernel files. The FULL registry sweep runs at gate closures and releases only.
   The hand-written registry is capped at ~30 entries, HDA/VEX layer only (no tool can mutate
   that layer), one-line notes.
4. **PDG/TOPs as the runner.** Scene cases and mutations become TOP work items: parallel,
   out-of-process (a clean hython per item — isolation we previously scripted by hand), cached
   with dependency-aware dirtying so only affected items recook. Sequential 80 min → parallel
   ~10-15 min on this machine, and the test graph is itself an inspectable Houdini artifact.
5. **A hard budget.** Test code may not exceed tool code — enforced by a check, and adding means
   deleting. Audits target production code only; the test machinery is never itself the subject
   of an audit cycle (that recursion is where the days went).

## What stays from v1

- The independent audit before any "done" (dev-loop Rule 0) — one round per cycle, mutation-armed.
- The mutation *idea*: a check is not written until it has been seen to fail.
- Human eyes at milestones: the viewport found what 3 600 checks could not, twice.
- Fast pure-logic tests under plain python; scene work headless under hython; never save a .hip.

## v1 → v2 migration — DONE (2026-08-25)

The five pieces landed first and were proven before anything was removed; the deletion pass
then removed what they subsume. Both halves are measured below, and the one target that was
missed says so.

| | state |
|---|---|
| 1. generic differential comparator | `tests/polychain/diff.py`, 19 mutations all seen red |
| 2a. Hypothesis over the kernel | `tests/unit/test_polychain_properties.py`, 11 properties, 1.6 s |
| 2b. seeded scene generator | `tests/polychain/gen_cases.py` + `run_generated.py`, 400 scenes |
| 3. PDG/TOPs runner | `tests/polychain/pdg_build.py` |
| 4. mutmut | `setup.cfg` `[mutmut]`, **pin 2.5.0** |
| 5. budget check | `tests/unit/test_polychain_budget.py` — **still RED at 1.05x**, see below |
| the deletions | **done** — 27 162 → 15 381 lines, 361 → 122 check names |

### What the deletion pass removed, and what it kept

| file | before | after |
|---|---|---|
| `run_native_checks.py` | 9 065 | 2 240 |
| `checks.py` | 5 110 | 2 532 |
| `mutations.py` | 1 087 | 632 |
| `test_polychain_plan.py` | 1 060 | 548 |
| `run_hda_checks.py` | 812 | 448 |
| `run_scene_checks.py` | 711 | 476 |
| `run_2d_checks.py` | 442 | 228 |
| `cases.py` | 1 829 | 1 728 |
| `conform_bench.py`, `facade_bench.py` | 488 | **deleted** |

The rule applied, in one sentence: **a bespoke assertion that compares a subset of what the
comparator compares is subsumed by it.** 126 of `run_native_checks`' 144 names and two thirds
of `checks.py` were exactly that — the built geometry against the plan that built it, attribute
by remembered attribute, over 92 hand-written cases — and `diff.compare` does it over EVERY
attribute by construction, on 400 generated scenes, against the SHIPPED asset.

Three categories were kept on purpose, and they are the reason the budget is still red:

* **the names with a registered mutation** — all 44 of them;
* **the measured COST ceilings** (`checks.py`'s port tripwires, the proxy LOD rows). A ceiling is
  a contract, and every one of those rows was bought by a regression that left every geometry
  check green;
* **the gate figures** — PC-G1/PC-G2's images and D194's drawn-primitive counts — and the
  artist-facing parameter page, neither of which any comparator can see.

### What the sweep measured after the deletion (2026-08-25, 16-core machine)

| | before | after | target |
|---|---|---|---|
| full sweep, 32 mutations, PDG | 1 757 s (29.3 min) | **200 s (3.3 min)** | < 15 min ✅ |
| the shared control (6 runners, pristine export) | 425 s | **68 s** | |
| `run_native_checks.py` alone | 430 s | **27 s** | |
| per-cycle gate (no mutations) | 13.5 s | **~13 s** | < 5 min ✅ |
| mutations RED | 32 of 32 | **32 of 32, 0 unreached names** | all ✅ |
| tests vs tool | 27 162 / 14 682 = 1.85x | **15 381 / 14 682 = 1.05x** | ≤ 1.0 ❌ |

⚠️ **THE 15-MINUTE FLOOR WAS `run_native_checks.py`, AND IT WAS ARITHMETIC RATHER THAN
SCHEDULING.** The control must finish before any mutation starts, and the longest mutation was
itself a `native` one, so 430 s of native runner put a ~15 min floor under the sweep at infinite
parallelism. Deleting the 126 subsumed names took the runner to 27 s and the whole sweep to
3.3 minutes — the same 32 mutations, all still red.

⚠️ **THE BUDGET IS STILL 699 LINES OVER, and the remaining candidates are coverage rather than
accretion.** Named, so the next pass starts from the argument instead of the number:
`test_polychain_corner.py` + `test_polychain_array2d.py` (1 418 lines) are the hand grids over
`corner.py` and `array2d.py`, for which **no property coverage exists yet** — the Hypothesis file
covers `plan` and `decompose` only, so mutmut's kill rate on those two kernel files rests
entirely on them, and deleting them would be deleting coverage to make a number. And
`tests/polychain/native.py` (644) is counted on the TEST side while
`devScripts/create_pf_polychain_hda.py`, which is on the PRODUCTION side, imports it to build
the shipped asset's stages: that single mis-attribution is a 1 288-line swing. It was left where
it is rather than reclassified, because moving it is a production change and reclassifying it
without moving it would be arithmetic rather than deletion.

⚠️ **AND PARALLELISM CAN TURN A RED INTO A FALSE SURVIVOR.** In the first 32-item sweep
`piece_key_within_piece_dropped` came back **SURVIVED with 15 of `native`'s check names never
printed**; run on its own it was **RED in 354 s**. Fifteen concurrent hython processes made the
native runner lose checks, and a lost check reads exactly like a check that cannot fail. The
runner **re-runs any SURVIVED verdict that has unreached names** before believing it, and
`--slots N` is the blunt instrument for a machine that is also doing something else.

### Independently verified — cycle V4 audit, 2026-08-25, HEAD `7fabfff`

A fresh agent that wrote none of this re-ran everything from a pristine `git archive HEAD`
export and measured its own numbers. **The build report's timings reproduce.**

| | audit's own measurement | target |
|---|---|---|
| per-cycle gate, `hython tests/polychain/pdg_build.py` | **12.9 s wall / 84.2 s summed work** | < 5 min ✅ |
| full sweep, `--full`, 32 mutations | **186.8 s = 3.1 min wall / 1 526 s work (8.2x)** | < 15 min ✅ |
| mutations red | **32 of 32 `[ok] RED`, 0 unreached names, 0 survivors** | all ✅ |
| six of them re-run ALONE on the lean suite | all RED — `corner_style_composed_default` 11.1 s, `corner_bisector_negated` 10.9 s, `out_cast_ints_int64` 58.6 s (storage), `piece_key_within_piece_dropped` 59.0 s, `generated_pc_local_scaled` 10.7 s, `hda_input_ports_swapped` 24.0 s | ✅ |
| gates | `gate_images.py` 0 failing / 3.5 s, `scale_gate.py` 9 rows 0 failing / 7.0 s, `run_hda_checks.py` 18 checks 0 failing / 9.4 s; **PC-G1..G4 pass, PC-G5 unchanged and still does not pass** | ✅ |
| the tool | `git diff --stat 20a9179 HEAD -- polyfactory devScripts otls` is **EMPTY** — this cycle was tests-only | ✅ |
| budget | **red**, re-counted independently with `wc -l`: **15 357 test / 14 643 tool = 1.05x, 714 over** (the check's own counter, +1 per file on both sides, says 15 381 / 14 682 = 699 over) | ≤ 1.0 ❌ |

Three things the audit found that the build report did not say:

1. ⚠️ **`facade_images.py` — PC-G5's ONLY image evidence — CANNOT FAIL, and it is 145 lines
   inside the budget.** `rasterise` returns early on `if not segs`, and `facade_images.main()`
   returns `None`. Demonstrated: with every facade's geometry replaced by an empty
   `hou.Geometry()`, the script writes **zero PNGs, prints nothing and exits 0**. It is the
   same class as `conform_bench.py` / `facade_bench.py`, which this cycle deleted for exactly
   that reason, and the discipline it breaks — *an image check must prove the image contains
   its subject* — is one `gate_images.py` itself honours (`image_shows_packed_*`). The fix is
   a drawn-segment floor per image, and it is the cheapest thing left in the suite.
2. ⚠️ **`--full` CANNOT BE RUN FROM AN EXPORT** — it resolves `git rev-parse HEAD` at `REPO`
   and dies with `not a git repository`. The pristine-export guarantee is real but it is
   **per work item and internal**: `run_mutation_registry.export()` archives HEAD for the
   control and for every mutation. So run the *gate* wherever you like; run the *sweep* in
   the repo.
3. ⚠️⚠️ **THE `mutmut` LANE HAD NEVER BEEN RUN, AND ITS FIRST RUN FINDS REAL
   SURVIVORS IN PRODUCTION CODE.** `setup.cfg`'s `[mutmut]` section is configured and 2.5.0 does
   work on native Windows as documented, but nothing in the cycle report shows it having been
   executed. The auditor ran it on **one** of the five configured kernel files, `decompose.py`
   (387 lines), inside the throwaway export: **352 mutants, 227 killed, 124 SURVIVED, 1
   suspicious — a 64.5 % kill rate — in 600 s.** The first five survivors opened were
   all substantive rather than arid, and one was chased to the end:

   > **mutant #209, `resolve_corners`: `if not forced and turn <= params.corner_angle_deg`
   > → `turn <`.** The docstring one line above states the contract as *corner iff
   > `turn > corner_angle_deg`*, so the mutant moves the corner-detection threshold onto its own
   > boundary. On an EXACT 90° turn with `corner_angle_deg = 90.0` the shipped code finds
   > **0 corners** and the mutant finds **1** — a corner post placed or not placed.
   > **It survives the ENTIRE lean suite**: 238 pytest tests, the properties at
   > `PC_EXAMPLES=1500`, 405 generated scenes through the differential oracle (`0 RED`),
   > `run_native_checks.py` (`0 failing`) and `run_scene_checks.py` (`0 failing, 0 moved`) —
   > every one of them exit 0. Neither the 89 hand fixtures nor `gen_cases` ever lands a turn
   > exactly on the threshold, and no property asserts the boundary. This is principle 2's own
   > failure mode surviving into v2: **generated inputs do not reach a boundary unless the
   > generator is told the boundary exists.**

   Two caveats stated rather than buried: mutmut's 2.5.0 mutant set is unfiltered (Google's
   policy filters arid lines; `setup.cfg` does not), so 124 is an upper bound on real gaps, and
   mutmut can only run pytest — some survivors may be killed by the hython lanes, though
   #209 demonstrably is not. And **600 s for one of five files** means the milestone form of
   this lane is on the order of hours, which no target in this file budgets for.
4. ⚠️ **A wall-clock ceiling flaked under the 32-way sweep.** `proxy_is_interactive` reddened
   as collateral for `hda_input_ports_swapped` in the parallel sweep and did **not** redden
   when the same mutation ran alone. It credits nothing, so no verdict moved — but by the
   skill's own rule a flaky check is a defect in the check, and this is the second time
   contention has moved a `native`/`hda` result (see the false survivor above).

The three PRODUCTION defects the new instruments found are **recorded, not fixed** — this was a
test cycle — and each is a standing check that fails the day it is fixed, so none can be closed
by accident: `pc_module` inside the packed geometry on the native path only
(`run_generated.KNOWN`, 207 of the 208 cases the guard admits); `plan.evenly` with **no
`MAX_UNITS` ceiling** where `plan.fit` clamps and warns
(`test_evenly_ignores_the_MAX_UNITS_ceiling`; re-measured by the audit — 999 999 anchors on a
1 km span at 1 mm spacing, 0.039 s, no warning, and the artist-facing *Evenly Spacing (m)* parm
is `min_is_strict=False`, so the value is typeable); and `fill = count` with a negative pad
laying the run outside its own section in silence
(`test_count_mode_overhangs_the_section_on_negative_padding`).

## The v2 commands

```bash
# THE PER-CYCLE GATE - kernel + comparator battery + budget + 400 generated
# scenes through the differential oracle, cooked as one parallel TOP graph.
# ~13 s wall for ~90 s of work. Exits non-zero on any red work item.
hython tests/polychain/pdg_build.py

# ... plus the mutations whose edited files actually moved (Google's policy)
hython tests/polychain/pdg_build.py --changed HEAD~1

# THE MILESTONE SWEEP - all 32 registry entries, one work item each, behind
# one shared control build. 200 s wall for 1 647 s of work.
# `--slots N` trades wall time for stability on a busy machine.
hython tests/polychain/pdg_build.py --full
hython tests/polychain/pdg_build.py --full --slots 6

# the pieces on their own, when a red needs looking at
python -m pytest tests/unit/test_polychain_properties.py -q      # 1.8 s
PC_EXAMPLES=1500 python -m pytest tests/unit/test_polychain_properties.py -q   # 23 s
python -m pytest tests/unit/test_polychain_budget.py -q          # 0.3 s
hython tests/polychain/run_diff_selftest.py                      # 1.9 s
hython tests/polychain/run_generated.py --seeds 400 --quiet      # 41 s
hython tests/polychain/run_generated.py --seeds 1 --start 27     # one seed
hython tests/polychain/run_native_checks.py                      # 27 s
hython tests/polychain/run_scene_checks.py                       #  4 s
hython tests/polychain/run_2d_checks.py                          # 14 s
hython tests/polychain/run_hda_checks.py                         # 10 s
hython tests/polychain/gate_images.py [outdir]                   #  4 s

# the registry on its own, sequentially - the meta-check the PDG sweep does
# NOT make: every printed check name PROVEN / EXEMPT / UNPROVEN, both
# directions of the inventory pinned, and no dead or stale declaration.
python tests/polychain/run_mutation_registry.py
python tests/polychain/run_mutation_registry.py --list
python tests/polychain/run_mutation_registry.py --only pc_local_scaled
python tests/polychain/run_mutation_registry.py --runner scene --state s.json

# MUTMUT, on the pure-Python kernel. ⚠️ PIN 2.5.0: mutmut 3.x refuses to run
# on native Windows ("please use the WSL") and does nothing else. ⚠️ And set
# PYTHONIOENCODING: its banner is emoji and this machine's stdout is cp1252
# whenever it is piped. ⚠️ And it REWRITES SOURCE FILES IN PLACE - an
# interrupted run leaves a mutant on disk; check `git status` after one.
pip install "mutmut==2.5.0"
export PYTHONIOENCODING=utf-8

# per cycle - only the kernel files git says moved
python -m mutmut run --paths-to-mutate "$(git diff --name-only HEAD~1 \
  -- 'polyfactory/scripts/python/polyfactory/polychain/*.py' | paste -sd,)"

# at a milestone - the whole kernel, from setup.cfg's [mutmut] section
python -m mutmut run
python -m mutmut results
python -m mutmut show <id>          # the diff of one surviving mutant
```

⚠️ **mutmut only ever sees the `hou`-free kernel** — `plan`, `decompose`, `corner`, `array2d`,
`__init__`. `place`, `conform`, `hda`, `kit`, `style` and `facade` import `hou`, so a mutant in
them would be "killed" by an ImportError under a Houdini-less pytest: a green earned by nothing.
Those layers belong to the hand-written registry, which is the division the skill draws.

---

# The v1 history

polyChain's v1 test regime — 25 137 lines of checks around a tool nobody had
measured, 80-minute sweeps, ~20 checks that could not fail — is **not
summarised here**. It is one document, with the incident log that earned every
rule in v2: [`ideas/build_retrospective.md`](../ideas/build_retrospective.md),
§2a (the unfailable checks) and §3–§4 (what to read before an autonomous
cycle). `ideas/polychain.md` carries the cycle-by-cycle build log. This file
describes what runs **now**.

---

# The other runners

Everything above is polyChain. citygen and the shared HDA hygiene suite are
unchanged by v2 and run on their own:

```bash
# pure logic — no Houdini, milliseconds
python tests/unit/test_citygen.py         # cross-section profile maths
python tests/unit/test_plan.py            # the S5 planner + its calibration

# re-measure what the builder's plates actually consume (rewrites the fixture
# tests/unit/test_plan.py calibrates against)
hython tests/citygen/dump_trims.py

# attribute hygiene — EVERY polyfactory SOP HDA cooked in a throwaway session,
# at defaults AND once per non-default toggle/menu value (236 branches, ~23 s),
# because `verts`, `scalefactor` and `__scalefactor` were all invisible at
# defaults. Asserts conventions.md §2 (no output name begins with `_`), that no
# retired spelling survives in any library file (the only check that can reach
# a Vop), and diffs every published name against tests/hda/baseline.json. A
# baseline move FAILS the run; --update-baseline is how you accept one.
hython tests/hda/run_attrib_checks.py
hython tests/hda/run_attrib_checks.py --update-baseline

# citygen geometry — throwaway Houdini session, never saves a .hip
hython tests/citygen/run_scene_checks.py
hython tests/citygen/run_scene_checks.py --update-baseline

# the loop-closure gate, swept over a sep/step ladder — ~1 min / ~20 min
hython tests/citygen/closure_gate.py
hython tests/citygen/closure_gate.py --full --table

# polyChain at scale: PC-G3's 10k-piece run and D75's curvature budget across
# radii (packed vs deformed, points, seconds, RSS) - ~30 s. Out of the
# registry's scope by construction: it prints a failing-ROW count, not check
# names, so there is nothing to pair a mutation against.
hython tests/polychain/scale_gate.py

# PC-G5's images - the L in three-quarter view, the reflex corner
# ground-to-cornice, and the facade coloured by `pc_cell`
hython tests/polychain/facade_images.py [outdir]
```

## Why this exists

Four review passes over CityGen each rewrote the *same* measurements from
scratch — self-intersection counts, the sidewalk-wrap test, degenerate-poly
counts, lot double-coverage — because they lived nowhere. That cost roughly
850k tokens.

**A measurement written during a review belongs in the suite afterwards.**
Round N's ad-hoc query becomes round N+1's standing assertion, and reviews get
cheaper instead of repeating themselves. v2 adds the other half of that rule,
learned the hard way: **it belongs there as an assertion with a ceiling and a
mutation, not as a script that prints.** Two wall-clock benches were deleted in
the v2 pass for exactly that reason — they could not fail.

## Numbers first, renders second

Nearly every real defect is *diagnosed* numerically. Renders show that
something is wrong; the numbers say what. So the scene checks run headless and
cheap, and rendering is a separate step for whatever they flag plus the fixed
gate set a human looks at.

⚠️ An image check must prove the image CONTAINS its subject before anything
judges it — a gate image that "showed" a 3 388-segment fence contained 188,
because a packed prim has one vertex and the wireframe was drawn off it.
`gate_images.py` counts drawn primitives against the packed count (D194).

⚠️ The flipbook render path needs a UI and **will not run in hython**. The
offscreen OpenGL ROP was tried and is unreliable on some drivers.

## The baselines

`citygen/baseline.json`, `polychain/baseline.json` and
`polychain/baseline_2d.json` record every value, not just pass/fail: several
regressions were only ever visible as *"this number got worse"*. The runner
diffs against the baseline and prints movement even where a check still passes
— **read that list and confirm each move is an improvement before running
`--update-baseline`** — and a moved value FAILS the run (D210: it used to print
the movement and exit 0).

⚠️ v2 shrank polyChain's baseline from 967 KB to 244 KB, because a recorded
value is only worth its weight where a NUMBER is the contract. Where the
question is "do the two implementations agree", the reference IS the baseline
and `diff.compare` asks it directly, on generated input, every run.

## Layout

```
tests/
  unit/                  pure Python, no Houdini
    test_citygen.py            cross-section profile maths
    test_plan.py               the S5 planner + its calibration
    trim_calibration.json      measured junction footprints, 545 arms
    test_polychain*.py         polyChain's kernel: contracts, the fitting
                               solve's lookup tables, corners, the 2D array
    test_polychain_properties.py  v2: Hypothesis over the hou-free kernel
    test_polychain_budget.py      v2: tests <= tool, enforced
  citygen/               checks.py / cases.py / run_scene_checks.py + baseline
  polychain/
    diff.py                v2: THE comparator - every attribute, both paths
    gen_cases.py           v2: a whole scene from one integer
    run_generated.py       v2: generated scenes through the oracle, on the .hda
    run_diff_selftest.py   v2: the comparator's own 19-mutation battery
    pdg_build.py           v2: the parallel cached runner (a TOP net)
    mutations.py           the registry: every check paired with its mutation
    run_mutation_registry.py   the meta-runner
    checks.py              the 16 geometric properties + the cost tripwires
    cases.py               the hand fixtures, each named for the defect that
                           created it - and what 22 of the 32 mutations reach
                           their target THROUGH, which is what keeps them
    run_scene_checks.py    the scene runner + baseline
    run_2d_checks.py       phase 2, its own cases and its own baseline
    run_native_checks.py   the native stages vs the reference, in ONE process
    run_hda_checks.py      the ASSET: wiring, the parm face, the artist page
    gate_images.py         PC-G1/PC-G2 through the parm page + a rasteriser
    scale_gate.py          PC-G3's ladder, both z-modes
```

## The planner's calibration is a baseline too

`plan.crossing_trims` predicts what a junction cuts off each arm without
cooking anything, so `standing` is checkable before the geometry exists
(§11.4). It is only worth something if it agrees with the plates the builder
really lays down, so `dump_trims.py` exports `trim_start` / `trim_end` from
`junction_solve/s5j_solve` on all sixteen cases and `test_plan.py` asserts the
model against every one of the 545 arms.

The residual is **pinned per case, not tolerated globally**: exact (≤ 1e-4 m)
on the ten cases whose arms are straight — Q_junction_ring among them,
dispatched through `node_trims`, which since the 2026-08-17 ruling asserts
type-INVARIANCE (every vocabulary type builds the crossing solve; the
uncut-principal junction render was ruled a bug and reverted), and up to 4.58 m
either way on the six with curved ones, because `s5j_solve` re-solves each
corner in the frame at its own cut and the planner has no arm shape to do that
with. Read those numbers as a recorded state, the same way `baseline.json` is
read.

⚠️ **But the metre is not the property, and the M1 audit caught this file
implying it was.** What the planner is FOR is the answer — does this street
still stand? Over all 322 edges the planner's `standing > 0` verdict never
disagrees with the builder's: **0 false-OK, 0 false-BAD**. That is asserted
directly, and it is the assertion to keep green. The per-case residuals are a
tripwire on the model drifting, not a safety margin — treating them as one is
how a 5.88 m optimistic error got recorded as a 2.02 m bound.

## The node schema, and why a closed vocabulary is not enough

`junction_schema` (M3) watches §11.3's node schema: `junction_type` on the
graph's `is_node` points, and — since the artist ruling of 2026-08-16 — the
principal as `principal_start` / `principal_end`, **int booleans on the prim**,
CityEngine's own shape. `JUNCTION_TYPE_VOCAB` is the closed set, and it is only
the FIRST of five terms — `LOT_REJECT_VOCAB`'s lesson was that membership cannot
detect an auditor relabelling every rejection to one member of the set. The
other three tie each value to something independently measurable: a junction of
degree >= 3 with no type (the shape of a silently-bypassed adapter), a type on a
node where `s5j_solve` builds no plate, and principal claims that number
anything but **0 or 2 at a node**, or sit at a dead end, or at a prim end that
is not a node at all.

⚠️ **The boolean shape retired four defects by making them inexpressible.** The
first schema was a node-side string of two `edge_id`s, and three audit rounds
found a stranger edge, the same edge twice, one edge of two, and an int-typed
value that crashed the whole gate through `.split()` — all properties of the
SHAPE. A boolean an edge carries about itself can express none of them; what it
can still express is wrong cardinality, which is one small term instead of a
parser. Injections re-proven on the boolean shape: one claim at a four-way,
three claims at one node, claims at all eight dead ends, a string-typed boolean
authored upstream (red rows, no crash), a point-class `principal_start` on the
graph, the stale `principal_edges` reappearing, and the city-prim leak with the
cleaner's `primdel` cleared — every one a red row with a clean restore, and a
WELL-FORMED authored pair stays green.

Two claims only make a pair when they come from two DIFFERENT prims — a
closed street claiming at both of its own ends is one street twice, red (built
synthetically and measured; no committed case can reach it while
`graph_mark_orphans` eats loop-only components). And the recorded value carries
**`claims`**, the total of claiming prim-ends, because it is the principal's pin
the way `types` is `junction_type`'s: without it, turning the computed principal
default on would move ZERO baseline values and §11.9's "the gate movement is its
own diff" would be false for exactly the attribute it was written for. (That
flip is BLOCKED since the 2026-08-17 ruling — the pin outlives it, because the
booleans still ship as markings/identity data and something must see them
move.) The normal authored state — a principal street claiming end-at-one-node,
start-at-the-next — passes green with `claims` counting it.

Historical injections from the string era, kept because the vacuity lesson
outlives the shape: **`is_node` destroyed** made every term read 0 because the
loop never ran — the same vacuity that let three checks go green on an EMPTY
graph on 2026-08-15. That guard survives unchanged.

## And a second check, because the first one's blind spot had already bitten

`node_schema_stays_on_the_graph` exists because M3 shipped a FIX with no
detector. The adapter leaked `junction_type` / `principal_edges` onto all 5568
city points; that was found by probing outputs by hand, and after the fix
nothing could have told you if it came back. Measured on frozen geometry with
the leak restored: `no_scratch_attribs_city` **PASS 0** (it is called with
`None, None` — city POINT attributes are deliberately unpoliced) and
`attribute_schema` **PASS 0** (it counts only MISSING attributes). Clearing
`out_detailclean`'s `ptdel` left the entire suite green.

**Four terms**, and it started with two — each of the others was added because
an audit injection walked past what was there:

* `leaked` — every (attribute, class) pair except each attribute's own HOME,
  on all four geometries and all four classes. Two homes since the boolean
  ruling: `junction_type` on graph POINTS, the principal booleans on graph
  PRIMS — so a point-class `principal_start` on the graph is a leak exactly as
  a prim-class `junction_type` is, and the booleans riding the sweep onto the
  published city's ROAD PRIMS is the new channel the point-class schema never
  had (cleaned by `out_detailclean`'s `primdel`, now non-empty). The retired
  `principal_edges` stays on the scan list: nothing creates it any more, so its
  appearance anywhere means something stale is writing it. Vertex is scanned
  because `out_detailclean` had the identical hole (`dovtxdel on`, `vtxdel ""`).
* `off_node` — on the graph, a non-empty `junction_type` may sit only on an
  `is_node` point (497 shape points once wore a value while `junction_schema`,
  nodes-only, stayed green). The principal booleans' twin of this term lives in
  `junction_schema`'s claim accounting, because they are prim-class.
* `untyped_plated` — any point with 3+ incident prims that is not a typed node.
  Both checks select by `is_node`, the same attribute the adapter selects by, so
  a cleared `is_node` hid a junction from everything at once while `s5j_solve`
  — which reads `len(pointprims) >= 3` and never `is_node` — still plated it.
* `schema_source` — which definition of the attribute name set was used. The
  shared constant was inert for a whole round because the import path was wrong,
  and a value-identical fallback hid it; now a fallback moves a baseline number.

⚠️ A wrong-TYPE value is a red row, never an exception. The string era's
`i@principal_edges` raised out of `run_case` and lost **all 15 cases** with no
JSON and no baseline compare; the boolean era's `_schema_flag` reads any type
without raising, and a string-typed boolean authored upstream was measured as
red rows, not a dead gate.

⚠️ **A/B-ing an HDA change needs a guard, or it lies.** With `HOUDINI_PATH`
set the way the gate sets it, Houdini auto-scans `polyfactory/otls` at startup
and those definitions WIN over an explicit `hou.hda.installFile` of a HEAD copy
— so a before/after comparison silently cooks the working-tree asset twice and
comes back byte-identical, md5 and all. Print and assert the library file path
and the node's presence before cooking anything.

⚠️ It deliberately does NOT assert WHICH type a node carries. `junction_type`
is artist-authorable, so "junction everywhere" is a legal state and a check that
forbade it would be asserting taste. Today's choice is pinned by the recorded
`types` histogram in `baseline.json` instead — any change to what the planner
computes moves that number where anyone can see it. (The specific change this
sentence used to name, M4's computed-default flip, is BLOCKED since the
2026-08-17 ruling; the pin is what makes ANY future default move visible, which
is why it outlives the flip.)

## The closure sweep, and why it is a file rather than a habit

`closure_gate.py` is the third rule applied to a review that kept repeating itself. The
loop-closure gate has now been swept from scratch and thrown away **three times** — the same
questions each round (how many welds close backwards, how much road a closure lays down twice,
whether the accepted seams leave room for a threshold), at four figures of tokens a round. It
is committed so round four starts where round three finished.

It does not cook an A/B. In the trace wrangle `closeloop` is used in exactly one place —
`if (closeloop) addvertex(0, prim, firstpt)` — so the traced geometry is identical for every
build of the gate, and any candidate gate can be evaluated by exporting the raw inputs once
and recomputing the booleans in Python. That also keeps `hou.HDADefinition.updateFromNode()`
out of the loop entirely: it writes the definition back to its own library file, and it has
already silently overwritten one agent's "pristine baseline" copy mid-comparison.

The transcription is only worth something if it still matches the VEX, so **`gate_matches_vex`
asserts exactly that**, on every street in the sweep, against the wrangle's own `closeloop`
flag. Edit the gate in the HDA and not here and that check fails first and loudest.

Two configs are pinned as `ADVERSARIAL` and always swept. Both need `step ≳ min_street_sep`
so nobody would ship them — and both refute a claim this project had recorded as measured
(`radial 22/30`: a retrograde weld at seam 8.412 against a recorded "0 with seam ≥ 8 m";
`radial 23/20`: a welded loop that crosses itself, against a recorded "0 chord
self-intersections"). A grid that happens to miss its own counterexamples is not a sweep.

`cases.py` sets `POLYFACTORY`, `HOUDINI_VEX_PATH` and `sys.path` itself, because
hython does not load the polyfactory package: without it `#include
<pf_streetgraph.vfl>` cannot resolve and Python SOPs cannot import
`polyfactory.citygen`. The harness found that portability bug on its first run.

## Test the union, and every branch

Two lessons the suite learned the hard way, both worth applying to any check
added from here on.

**The union.** `selfx_junction_surface` cooked Intersection Analysis on the
junction patch alone and reported 0. `selfx_roads` cooked it on the roads alone
and reported 0. Nothing cooked it on the merged city, which carried 102 / 529 /
863 intersection points through four commits. Two green checks, one broken seam,
no signal. If two subsystems have to meet, assert on the merged result —
`selfx_city_merged` is that assertion. (What it turned out to be measuring is an
unbuilt feature rather than a broken one — see the note under *Known-failing* —
but that is the point: nothing else could see the seam at all.)

**Every branch.** `lots_params_subdiv_mode` has two settings and the suite only
ever ran mode 0. Mode 1 failed a *committed* check the first time anybody
executed it. Case **D** exists solely to run it. Adding a parameter means adding
a case.

## The cases

| | Input | Why it exists |
|---|---|---|
| **A** `A_drawn` | hand-drawn curves | the artist path; smallest and fastest |
| **B** `B_grid` | grid tensor field | straight streets, 17 blocks |
| **C** `C_radial` | radial tensor field | curved streets — where the seam defects show |
| **D** `D_offset` | A's curves, `subdiv_mode = 1` | the European perimeter block (S8 `offset`) |
| **E** `E_short_t` | a 20 m perpendicular T | the only case that reaches `max_fillet_fraction` |
| **F** `F_bend` | a 90° arterial bend | S3b's curvature clamp at its design amplitude |
| **G** `G_tongue` | a 24 m arm off a four-way | `s5j_params_min_standing_widths` — the tongue |
| **H** `H_offset_strict` | D's input, `max_aspect` 1.9 | the only case that notices the courtyard rung-skip regressing |
| **I** `I_offset_radial` | C's field, `subdiv_mode = 1` | `offset` on block shapes that are NOT A's — expected red on `lots_are_simple_polygons` |
| **J** `J_five_star` | a hand-drawn 5-way star | the first case that EXECUTES the S5a realign |
| **K** `K_stub_triangle` | a 3-cycle of 32 m jogs | the case the repair gate REFUSES — six red rows, one defect |
| **M** `M_shallow_y_24` | a 24° leg, just under the floor | `graph_min_angle` deletes the LEG — 1 in pass 0 |
| **N** `N_shallow_y_32` | a 32° leg, over the floor | the control: nothing deleted, and the junction is still broken |
| **O** `O_shallow_y_host_dies` | 22°, but the leg is LONGER than the host's east half | the other branch: `graph_min_angle` takes the **host's own arterial**, published as a 599.77 m survivor |
| **P** `P_stub_chain` | four junctions on three 30 m links | the flood fill PAST a 3-cycle; 3 edges of 9 ship |
| **Q** `Q_junction_ring` | two AUTHORED `junction` Ts on a ring | the S7 T-case. Since the 2026-08-17 ruling the type moves NO geometry (builds as crossing; type + principal booleans are markings/identity data) — Q now proves the authored schema flows while the build stays the crossing's |

⚠️ **This table listed seven cases while the suite ran eleven** — found by the M1
audit, 2026-08-15, alongside a stale block count for B. Two of the four missing
ones — J and K — are the only cases that carry the S5a junction work at all, so a
reader looking for them found nothing. Whole suite: **sixteen**.

Five of the sixteen exist because a mechanism shipped green and unexercised at
its design amplitude — `max_fillet_fraction` (E), the S3b clamp (F), the tongue
drop (G), the realign (J) and its refusal (K). Adding a parameter means adding a
case.

**M–P are M2, and they are CASES BEFORE MECHANISM.** They document what today's
build does with a shallow approach and with a stub cluster larger than a
triangle — the two things §11.5's `merge` type and §11.8's spread exist to
resolve. Their value is that they are red, and specifically red in a way that
will go green for a *reason* when M5 lands. A family added after its fix could
never show the fix changed anything.

⚠️ **AND THE FIRST VERSION OF L / M / O PUBLISHED AN EMPTY GRAPH** — city 0,
edges 0 — while the suite reported three tidy red rows. §11.11's own warning,
arriving on schedule: *read `counts` before believing any green*. The cause was
a chain of two by-design mechanisms, not a bug: `graph_min_angle` removes the
shallow leg, the Y node drops to degree 2, the component now holds no junction
at all, and `graph_drop_orphans` correctly deletes the whole thing. A host with
one leg is one deletion away from nothing. Each shallow-Y now carries a second,
plain T 300 m west whose only job is to keep the component alive so the case
measures the ANGLE rather than the orphan filter.

D reuses A's input rather than sweeping the mode over all three: the mode only
changes S8, so a sweep would re-run every street and junction check for no new
information. Whole suite: ~17 s.

## Known-failing — 27 rows (re-measured 2026-08-17, post-M5.3)

Not noise — real, tracked defects, most of them findings in
`ideas/citygen_streets.md` §4e. **Do not `--update-baseline` these away.**

⚠️ **THIS TABLE HAD DRIFTED OUT OF DATE AND WAS POINTING THE NEXT READER AT
PHANTOMS.** Found during the M1 audit, 2026-08-15: it listed six checks that
pass on today's build (`trim_metric_is_consistent`, `no_sweep_fold_after_trim`,
`no_downward_faces`, `selfx_roads`, `lot_aspect_ratio`, `lots_tile_blocks`),
attributed rows to the wrong cases, and omitted the six K_stub_triangle rows
that are the honest form of an unrepaired jog. Rebuilt below from a gate run
rather than edited. Why the six went green is **not recorded anywhere** and this
table is not the place to guess — treat their §4e findings as unverified rather
than closed. A stale known-failing list is worse than none: it makes a real
regression look expected.

| Case | Check | Value | Finding |
|---|---|---|---|
| A B C D F G H I J K | `selfx_city_merged` | 9 / 101 / 127 / 9 / 2 / 6 / 9 / 127 / 6 / 87 | **NOT A DEFECT — it measures a declared v1 non-goal.** See below. |

⚠️ **`selfx_city_merged` is the standing measure of an unbuilt feature, and reading it as
breakage wasted a review round.** Diagnosed in the viewport 2026-08-15. At every crossing site
the incident prims are a road band at y = 0.15 with its kerb riser, and the junction plate at
y = 0 — the street's raised elements arrive at the junction still at their own height, because a
street is swept as ONE ribbon and nothing brings the section down at the seam. Per-segment
cross-section transitions are an **explicit §10 non-goal for v1**; the approach when it is built
is the Wang-tile segmentation recorded in `citygen_streets.md` §9. So this number is a progress
bar on a feature, not a fault to trim away: it goes to zero when the end pieces exist and not
before. **Do not chase it with thresholds.** Keep it recorded — it is the only thing that will
tell you the transition work is actually landing.

| C I | `plaza_disc_is_clear` | 8,364 of 11,310 m² built over, −1.14 m gap | 4e-2 — the plaza ring is emitted correctly and deleted before it ships |
| I | `lots_are_simple_polygons` | 1 lot, 1 viable | 4e-5 — Sutherland–Hodgman bowties on non-convex blocks; I exists to reach the 96% of block rings D and H are not |
| I | `every_block_is_subdivided` | 1 empty of 28, at (21.31, 33.04) | S8 on a radial block I's `offset` mode cannot fill |
| K | `trim_leaves_road_standing` | min_standing **−13.434 m**, ratio −0.933, 3 under | §S5a — the stub triangle's plates overlap. **This is the number §11.4's planner reproduces.** |
| K | `selfx_junction_surface` | 50 | same cause: three crossing plates 42 m across on 32 m gaps |
| K | `every_mouth_has_a_road` | 6 of 11 | the streets those plates ate |
| K | `block_boundary_closes` | 6 open loops, 12 unpaired ends | the kerb cannot close around an overlapped junction |
| K | `lots_clear_of_junctions` | 54.2 m² over 8 junctions | lots on the overlap |
| K | `lots_clear_of_roads` | 54.2 m², worst edge 56.3 m at (15.74, 12.92) | same |

K's six rows are one defect, not six, and they are what **M5/M6** exist to
close. (M4 was the third candidate and it closed none of them: the junction
type that might have dissolved K was ruled a bug on 2026-08-17 and reverted, so
K's rescue is back with the resolution ladder — see §11.9.) They are the honest form of a jog the repair loop refuses to collapse —
see `cases.py`'s note on K and §S5a.

**M2 added four cases and six rows, 20 → 26** (M4's Q later added its
`selfx_city_merged` row, 26 → 27; **M5.2 closed N's two, 27 → 25**;
**M5.3's merge added O's two mouth rows, 25 → 27** — the streets SHIP now,
and the mouth that ships them has recorded defects, below).
Three of the six were the declared v1 non-goal already recorded on ten other
cases; the other three were defects the build had and nothing could see — **two
of them N's, fixed 2026-08-17 and no longer in the table below**:

| Case | Check | Value | Finding |
|---|---|---|---|
| M O N | `selfx_city_merged` | 6 / 19 / 6 | the v1 non-goal again, see above — mostly. The row read 4 / 5 / 6 pre-merge; M and O rose because their legs now SHIP (more seams), and O's 19 is dominated by the ~100 m gore wedge overlapping its own mouth — the same defect as O's two rows above, counted a second way. Goes down with the merge mouth contract, not with Wang tiles alone |
| Q | `selfx_city_merged` | 4 | the v1 non-goal, ordinary seams. It read **122** while M4's junction plate spanned the through principal (coplanar overlap — the z-fight the artist saw); the 2026-08-17 revert took 118 of those with it |
| O | `selfx_junction_surface` | 2 | **the merge MOUTH, M5.3's recorded open half.** The mover ships O's leg as a merge (nothing deleted, `killed_in_pass0` 0) and the landing builds as a crossing — an ~12° arterial pair, **below the 25° floor the corner solve was designed against** (`min_junction_angle` used to guarantee it). The ~100 m miter-clamped gore wedge self-touches twice. M (collector widths) builds the same shape green; the failure is width-driven. The mouth contract in `s5j_solve` is the remaining M5 work — see §11.6 |
| O | `every_corner_is_an_arc` | tangent **3.17** | same defect, same wedge: one corner arc's end tangent disagrees with its street. One mechanism, two rows — the N precedent |
| P | `connections_are_never_refused` | `graph_stub_kill` **3** pass 0 (by design), `graph_drop_orphans` **2 late** | §S5a item 5, reproduced exactly — and by the specified mechanism: `cluster 4, narm 6, ok 1` measured live. Collapse a wide cluster, let the realign work on what it makes, and two components fall off — **3 edges of 9 ship** |

✅ **N's TWO ROWS WERE ONE DEFECT AND M5.2 FIXED IT (2026-08-17), in TWO wrangles.** The
diagnosis below is kept because it is the fix's derivation and because the second cause was
only visible once the first was fixed: closing the carriageway hole put the road ON the
node with `trim_end` 0, and `blocks_kerb` read `trim <= 0` as "dead end" and laid a cap across
a live junction — 1 open loop became 3. The dead-end test is now cap PRESENCE, asked of
the patch. Result: `trim_metric_is_consistent` max **4.00 → 0.00 m**, `block_boundary_closes`
**1 open loop / 2 unpaired ends → 0 / 0**, and no other value in the suite moved.

⚠️ **THE TRIGGER WAS NOT "TRIM == 0".** This table first blamed the missing merge, then blamed a zero
trim; both were wrong, and the second one matters because the fix it implied
would not have worked. `s5j_trim` deletes a junction's shared point
unconditionally (*"a shared junction point belongs to several edges; only ever
delete it"*), and the surviving last point is only moved to the cut by
`if (de < te)`. **The predicate is in that line and it is not a constant**:
`de` is the arm's own TERMINAL SEGMENT, which `s5_resample` sets to
`L / ceil(L / step)` — bounded by `(step/2, step]`, so a 2.00 m floor in
principle, and measured **3.5832 .. 4.0000 m** across the 545 junction-side ends
of the suite, equal to 4.00 only on the 22 ends whose arm length is an exact
multiple of the step. So the endpoint is re-created only when
**`trim > de`**, and the hole is **`de − trim`**. ⚠️ Two earlier versions of this
paragraph said "when the trim is non-zero" and then "when `trim > 4.00 m`";
4.00 m is the resample CAP, not the threshold, and writing the fix as
`if (te < 4.0)` would detach it from the geometry it was measured on — and break
outright the day anyone changes Max Segment Length. Swept live on the shallow-Y
rig, where `de` happens to be 4.000:

| leg angle | junction-side `trim_end` | gap |
|---|---|---|
| 25.5–45° | 0.0000 | **4.000 m** |
| 50° | 1.4107 | **2.589 m** |
| 55° | 2.9575 | **1.043 m** |
| 60° and up | 4.4454+ | 0.000 |

**A non-zero trim of 1.41 m still leaves a 2.59 m hole.** Anyone who "fixes"
this by snapping when the trim is zero gets a green gate — the corpus contains
no arm with a trim strictly between 0 and 4 — and leaves the defect live for
every arm in that band. Four arms already sit at 4.35–5.00 m, **0.35 m** from
the trigger.

⚠️ And the generalisation was wrong three times. It is **not** "every junction
with one wide arm pair": of **545 arms** exactly **one** has a junction-side trim
≤ 4 m — N's zero-trim arm. (It read five while M4's four deliberately-uncut Q
arms existed; the 2026-08-17 revert gave them real crossing trims.) And **89 of
the 90 junctions with two or more arterial arms do not exhibit
it** — `G_tongue` is two collinear arterials plus a third and trims 22.4 all
round. ⚠️ That row read `87 of the 88` and **both halves were wrong**: the
denominator was the pre-Q count, stale since M4 added a sixteenth case, and the
numerator moved when the revert gave Q's four arms real trims. Recomputed from
`trim_calibration.json`, 2026-08-17. Nor is it "the arm opposite a near-floor
pair at a 3-arm node", which
generalised one rig.

**The hole condition is just `trim < de`**, and nothing narrower. An arm's trim
is `max(reach_ahead, reach_behind, 0)` — in `plan.crossing_trims` and in the
builder alike (`dd = max(max(ta[i], tb[(i-1+n)%n]), 0.0)`) — so ANY arm whose
larger corner reach falls short of its own terminal segment gapping. ⚠️ "Both
corner reaches ≤ 0" is a **sub**-condition, not the condition: it produces
`trim == 0` and therefore the MAXIMAL hole, the full `de`. Both `_corner`
implementations floor their return at ≥ 0, so "≤ 0" can only ever mean "== 0",
and the precise form is `raw + run ≤ 0` on both corners — the fillet run counts,
so "the kerb lines cross behind the node" (`raw < 0`) is not enough on its own.

It is **degree-independent** either way. Driving `plan.crossing_trims` over legal
degree-4 nodes (every gap ≥ 25°, so `graph_min_angle` deletes nothing) finds
**964 distinct bearing sets** with an arm at trim ≤ 4 m — e.g. bearings
(0, 25, 150, 275) at widths (26.8, 15.1, 26.8, 15.1) → trim **2.957**, whose two
reaches are both **+2.957**, i.e. a real gap of `de − 2.957` with neither reach
at zero. Degree 5 reaches it too. And the angle floor is not part of it at all:
on the 3-arm rig the opposite arterial sits at trim 0.000 for **every** gap from
5° to 45°, and symmetrically at 135–175° — 25.5–45° is only the window where
`graph_min_angle` stops deleting the leg first. On N, `104.53 m²` was wrong too
— the hole is **107.20 m² = 4.00 × 26.80 exactly**, a clean rectangle, which is
what the root cause predicts.

⚠️ **AND `city_is_fully_paved` IS STRUCTURALLY BLIND TO IT** — it builds the
must-be-paved region from the corridor's own outer boundary, which the same
defect breaks: on N those prims span x −518.09..−4.00 and 0.00..518.09 (the
second not even closed), so the hole falls **outside the region by construction**
and the check reports `unpaved_m2 0.0` and passes. The one check written to find
holes cannot see a hole that also opens the block boundary. Same shape as the
`selfx_*` lesson above: a check whose input is produced by the thing it checks.

⚠️ **M and O are GREEN on `connections_are_never_refused` while deleting a
street each**, and that is not an oversight in the check: pass 0 is exempt by
design, because `graph_min_angle` exists to remove the near-parallel duplicates
tracing produces. The deletion is recorded in the check's `deleted_in_pass0`
value (`graph_min_angle: 1`) rather than asserted, so the baseline pins it and
M5 turning it to 0 is visible. Whether a 15° approach should cost a street at
all is §S5a item 6 — the artist's call, not the implementer's.

`no_scratch_attribs_lots` was on this list at 27 / 28 / 28 / 27 and is **fixed**
(4e-10). `lots_normal` now deletes the seven blocks-branch duplicates and a
`lots_publish` node drops `Cd` on the published branch only — the city keeps the
green/red viability colour. ⚠️ An allow-list only detects EXTRA attributes, never
MISSING ones: `LOT_PRIM_ATTRS` still promises `layer`, which the lots output has
never shipped. Ship it or drop it from the list; the check cannot tell you.

Passing, and that is the point — each has been shown to fail under fault
injection or on another case, so none of them is decoration:

- `every_corner_is_an_arc` now fits a circle to every corner. Its three new
  terms were verified by perturbing a detached copy of the patch geometry: one
  point moved 5 cm trips `fit`; the arc grown 0.5 m trips `radius` while `fit`
  stays at baseline; the arc *translated* 7 cm trips `tangent` alone, invisible
  to both others. It also reports `mixed_class`, which is 100% everywhere —
  4e-3's arbitrary corner radius, recorded rather than asserted because the
  design doc names no tie-break rule.
- `no_sweep_fold_after_trim` passes on B despite 0.25 m segments, because they
  are straight. Short *and* turning is the failure; short alone is not.
