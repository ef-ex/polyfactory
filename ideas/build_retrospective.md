# polyChain build — incident log and recurring-failure analysis

**Status:** living document, opened 2026-08-24 at Hannes' request.
**What this is:** every time the loop restarted, a cycle was re-run, or work had to be redone —
what caused it, and whether it is a **one-off** or a **pattern that should become a standing rule**.
**Why:** three days of autonomous multi-agent building produced a clear signal — the same class of
failure kept recurring, and it was almost never the *code*.
**How to use it:** §2 is the raw log. §3 is the analysis — the payload. §4 says what should become
a skill, an instruction, or code. §5 records what already worked and must not be lost.

---

## 1. The one-sentence finding

**Across ~15 cycles, the dominant recurring failure was not a bug in the tool — it was a check that
could not fail.** Roughly twenty distinct instances, found in almost every cycle, every one caught
by an *independent auditor* rather than by the agent that wrote the code. Infrastructure
interruptions (usage limits, 529s) cost far less, because durable on-disk state made them cheap.

---

## 2. Incident log

### 2a. Verification integrity — the dominant class (~20 instances)

| # | Incident | Ref |
|---|---|---|
| 1 | `clip_stamp` written as `ok = area or n == 0` — **unfailable on exactly the area builds it was written for** | P2-3V |
| 2 | Six fixes from one cycle had **no assertion anywhere**; all six could be deleted with the suite green | D147 |
| 3 | Both benches state **"NO CEILING is asserted"** — de-batching the stamp ran **+103 %** and stayed green | D193 |
| 4 | Parity checks ran against a **test rig, not the shipped asset** — the §4.2 port could be unplugged from its own menu entry silently | D192 |
| 5 | **Gate images never contained the fence** — wireframes drawn off packed prims without unpacking; PC-G1's image was 188 segments of a 3 388-segment fence | D194 |
| 6 | `run_scene_checks` **printed a moved baseline value and still exited 0** — every "no baseline movement" claim rested on that exit code | D210 |
| 7 | Stage-label check asserted a label was **non-empty, never that it was true** — two entries could both claim NATIVE, one serving a dead bridge | D207 |
| 8 | A check **read the very table its own mutation edits**, so it passed on the mutation it existed to catch; the headline mutation was actually stopped by an assertion *crash* | D208 |
| 9 | A check **failed once in three runs on an unmutated build** | D209 |
| 10 | **D209's own fix contained D209 again** — two measurements taken in separate blocks, never seeing the same machine | N-4C |
| 11 | Per-node cost ceilings covered **4 of 18 wrangles**; fourteen had no cost assertion at all | D206 |
| 12 | `_snapshot` compared point attributes **by name only** — `pc_local` could be scaled 1.5× or zeroed with parity reporting "identical" | N5 |
| 13 | **Tolerance disguised as exactness** — a check advertising 1e-12 m compared *after* rounding to float32; real tolerance ~0.98 mm at 20 km, and the row reporting `0.000e+00` was genuinely 0.94 mm off | N6 |
| 14 | `CF_resampled_straight` used a rigid kit, so the code under test **returned before the branch it was written to cover** | cycle 6 |
| 15 | `BJ_conform_deck`'s two surfaces were **equidistant**, so a tie-break decided the result and the actual logic was never exercised | cycle 6 |
| 16 | **`pc_variant` was never exercised** — no module in any kit carried one, so both sides of the comparison were `""` | P0 |
| 17 | **0 of 89 parity cases contained a point shared between prims** — while citygen's fused street network is exactly that topology (2.207 m arclength error, phantom corner) | N3 |
| 18 | **`edge_id` had zero occurrences under `tests/`** — citygen streets' own attribute, and an int-typed one shipped a different fence *and a different curve order* | D223 |
| 19 | `parms_inert_under_payload` moved **only `fill` and `seed`**, and compared sorted ids not positions — the `padding` leak it existed to catch was invisible | D91 |
| 20 | `stamp_calls_per_piece` ran on a **100 % packed fixture**, so an 8.4× regression on the deformed branch was invisible | D206 |
| 21 | **A building massed ENTIRELY OUTSIDE ITS LOT with every check green** — 3 volumes at x −5..0 against a lot at x 0..20, collapse warning **0** on every face, `volume_count_matches` / `outward_normals` / `party_walls_real` all passing. Reached through a *legal* cascade override; both axes inverted, so the signed area kept its sign *and shrank* and all three guards stayed silent. **Nothing asserted where the mass was, or how big it was in plan.** | citygen buildings, G1 round 2 |
| 22 | **The suite could not see a plan dimension at all.** Mutating shipped VEX to cut the bar at half the fraction moved the Einhof dwelling 20 m → 10 m and the barn 12.5 m → 28.8 m; **all 16 checks and the baseline stayed green.** `record()` snapshotted volumes/faces/roles/wall-roles/top-height — no plan quantity | G1 `R2-1` |
| 23 | **`image_contains_subject` compared a count against itself by construction** — one segment per vertex per prim, checked against the vertex count. An **8×8 pixel** render passed. Repaired to a byte ratio, which still passes **1 of 97 prims** (40.2×) and **a different scene entirely** (90.7×) | G1 `R2-2` / `R3-6` |
| 24 | **`encloses_courtyard` returned BYTE-IDENTICAL numbers** for a correct block and one whose courtyard was slid 4 m sideways — a rigid translation preserves every area there is. Its repair was still a MIN-oracle: a non-uniform ring built **518.4 m² instead of 864 m²** and it reported *"12.00–12.00 m against 12.00 asked for"* | G1 rounds 1–2 |
| 25 | **The mutation sweep demanded one mutation per check NAME, not per clause** — so a four-clause check shipped **three clauses nobody had ever proved.** Fixing it revealed **12 owed mutations** in one pass | G1 `§0.0f-2` |
| 26 | **`pf_setback` (cascade level 5) was dead code** — the authored branch had never once executed, and would have shipped as a name with a dead value on every wall. Separately, a float `pf_setback` **could not express `setback(0)`** (gated on `> 0.0`), so the one value the spec calls the identity op was the one an artist could not author | G1 fix pass / `R3-3` |
| 27 | **A streets gate reported ALL-GREEN at 1.0°** because `graph_fuse` had eaten the leg and `counts.edges` was 3 — the check had no leg left to disagree with | citygen streets, M5 (polyfactory-f2) |

**⭐ THE SUB-SHAPE THIS CLASS KEEPS TAKING, NAMED (2026-08-27, found independently by two sessions
in one night):**

> **The check passed because its subject was ABSENT, not because it was correct.**

Instances 5, 16, 21, 22, 23, 26 and 27 are all this, and 21 and 27 were hit **the same night, in two
different subsystems, by two agents who did not know the other had it** — a building with no
assertion of where it was, and a gate with no leg left to measure. Instance 24 is its near neighbour:
the subject was present but the oracle was invariant under the very error it existed to catch.

**The rule that falls out, and it is cheap:** *assert the subject exists and is where it belongs
before asserting anything about its properties.* A check whose oracle can be satisfied by absence is
not a check. In practice that means a presence/extent assertion **preceding** every quality
assertion — plan bounds before plan quality, segment content before image quality, attribute value
before attribute name.

### 2b. Wrong conclusions that propagated

| # | Incident | Cost |
|---|---|---|
| 1 | **"No VEX verb exists on 22.0.398"** (D103). False — `attribvop` + `vexsrc="snippet"` gives 64-bit VEX from a verb. **Root cause: `nodeVerb` returns `None` for verbless nodes instead of raising, so a `try/except` probe reports every node as verb-backed.** | Closed the door on VEX for the entire build until an audit reopened it |
| 2 | *(mine)* **"Zero native SOP reuse"** — I grepped for `createNode` and missed `nodeVerb`; `clip` and `polyfill` were already in use | Told Hannes something false |
| 3 | A benchmark's parity numbers **could not have come from the script that reported them** (it switches OpenCL precision mid-process, which raises) | Caught at audit |
| 4 | A fixture described as **"8 km world coords" was 224.7 m** | Caught at audit |
| 5 | **"Bit-identical"** actually meant *identical after fp32 storage rounding* — `P` is 32-bit, so the storage floor at 20 km is 9.765e-04 m | Caught at audit |
| 6 | A **2.10× speedup measured against a baseline that would not reproduce**; corrected to 1.81× | Self-corrected |
| 7 | A comparand with **its own O(n²)** inflating the reported gain | Self-corrected |
| 8 | *(mine)* A brief telling an agent to fix **five defects already closed two cycles earlier** | One cycle, spent on re-verification instead (the correct response) |

### 2c. Harness and infrastructure

| # | Incident | Recovery |
|---|---|---|
| 1 | **Session usage limit** killed fix+verify mid-cycle | Findings recovered from the workflow journal; implementation had self-committed. Cost ~0 |
| 2 | **Weekly usage limit** killed all 6 agents | One fix had landed; rest relaunched. Cost ~1 cycle |
| 3 | **API 529 Overloaded** killed the verify agent | Resumed; 5 cached agents replayed |
| 4 | *(mine)* Workflow script crashed on `fixReport.slice` when the fix agent returned `null` | Patched null-safety |
| 5 | Saved workflow scripts pick up **CRLF on Windows** → permission handler rejects them as control characters | Strip to LF |
| 6 | **Backticks inside the script's template literal** terminated the string → parse error | No backticks in inserted text |
| 7 | **git index lock contention** between concurrent workflows | Retry loop |
| 8 | **`git commit --amend` on a shared branch rolled another workstream's committed HDAs out of HEAD twice** | Recovered, md5-verified. Now a standing prohibition |
| 9 | **Scratchpad filename collision** between concurrent agents — one overwrote three of another's files | Namespaced copies |
| 10 | **Houdini GUI bridge wedged** — answers pings (off-thread) while every main-thread call times out | Fell back to hython + a headless rasteriser |
| 11 | **The build machine HARD-FROZE twice** (Kernel-Power 41, services starving before the log stops, no GPU/WHEA events) — the PDG runner's default of CPU-1 = **15 parallel hython sessions** met a fixed 5.7 GB pagefile (commit limit ≈ RAM) and work items that had grown to 123k-prim builds | Default capped to 4 slots IN CODE (`--slots N` is the deliberate opt-up); recommendation to Hannes: system-managed pagefile, close the GUI Houdini during unattended sweeps |

### 2d. My own spec and briefing failures

| # | Incident | Consequence |
|---|---|---|
| 1 | I specced the kernel as **"PURE PYTHON with NO Houdini imports"** so it would unit-test in milliseconds | Produced a 6 000-line Python monolith inside a two-node HDA, violating the house rule that Python is the last resort. Cost: a full architectural rebuild |
| 2 | I scoped **phase 1 as the build target** and set the loop's stop condition at its gates | The loop stopped at half the tool; Hannes had to ask why |
| 3 | **No review lens ever looked at the built asset's metadata** | Hannes found the missing TAB-menu entry and unlabelled ports himself |
| 4 | I relayed **image-verified gate results** from a pipeline that had never been independently checked | The images did not contain the fence |

---

## 3. The patterns

**P1 — A test written by the same agent that wrote the code asserts the code's shape, not its
contract.** The strongest signal in the log: ~20 instances, and the *only* reliable detector was an
independent agent applying mutations. Green suites here have consistently meant less than they
appeared to.

**P2 — The commonest concrete form is a fixture that cannot reach the code.** Rigid kits that
return early, equidistant surfaces where a tie-break decides, no case with a shared point, no kit
with a variant, no test using `edge_id`. The check is well-written; nothing ever runs it.

**P3 — The second commonest is an assertion weaker than its claim.** "No ceiling", non-emptiness
instead of truth, names instead of values, sorted ids instead of positions, comparison after
rounding, a runner that prints failure and exits 0.

**P4 — A wrong technical conclusion, once recorded, propagates until an audit re-probes it.** D103
closed VEX for the whole build on a probe artefact. The generalisable trap: **an API that returns a
falsy value instead of raising makes `try/except` probing silently wrong.**

**P5 — Measurement is as error-prone as code, and in the same ways.** Non-reproducing baselines,
comparands with their own complexity, fixtures smaller than the thing measured, profile shares
quoted as time savings, compile time hidden in warm-up.

**P6 — Storage and call structure are part of the contract and were in no spec.** Attribute storage
(int vs float vs string) changed geometry *and curve order*; call structure (one batched execution
vs per-piece) was worth 55×, dwarfing the language choice the whole port was about.

**P7 — Infrastructure interruptions were cheap *because* state was durable.** Every limit and 529
cost ~0–1 cycle, recovered from committed work plus the on-disk resume pointer. The one thing that
consistently worked.

---

## 4. What should become a skill, an instruction, or code

### 4a. HIGHEST VALUE — a verification-integrity discipline (P1, P2, P3; ~20 incidents)

Belongs in `houdini-dev-loop`, whose rule 0 already says "no independent audit, no done". It needs
the *how*. Each rule below is earned by an incident above:

1. **A check is not written until its mutation has been seen to fail.** Write it, break the thing it
   guards, watch it go red, restore. Unproven checks are this project's default failure mode.
2. **State what the check CANNOT see** — one line per check naming its blind spot. The
   `_snapshot`-by-name and float32-rounding cases were honest code with an unstated limit.
3. **A check may not read the same declaration its mutation would edit** — every declaration needs
   an independent second source (D208).
4. **Assert truth, not presence.** Non-empty ≠ correct; a name ≠ a value; a sorted set ≠ an order.
5. **Never compare after rounding** unless the rounding *is* the contract — and then state the real
   tolerance at the real magnitude (0.98 mm at 20 km, not "1e-12").
6. **A cost check needs a measured ceiling.** "No ceiling asserted" is not a check.
7. **A runner must exit non-zero on any movement it prints.**
8. **Parity runs against the shipped asset**, never a parallel rig.
9. **Verify an image contains its subject** — count drawn primitives against expected before judging
   anything by eye (packed prims draw as nothing).
10. **Ask before writing a fixture: what would this fail to reach?** Rigid modules, equidistant
    surfaces, unshared points, absent variants — all invisible this way.

### 4b. Houdini domain gotchas → extend `houdini-procedural-modeling`

Each cost real time here; none is discoverable from the docs:

- **`nodeVerb` returns `None` for verbless nodes instead of raising** — never probe with
  `try/except`. Verbless on 22.0.398: `chain`, `copytocurves`, `pathdeform`, `bend`,
  `attribwrangle`, `polycap`. And `attribvop` + `vexsrc="snippet"` *does* give VEX from a verb.
- **A PRIM wrangle writing per-POINT attributes double-writes any point shared between prims.**
  Unshare first, or make the attributes vertex-class.
- **An attribute's STORAGE is part of its contract.** int vs float vs string `edge_id` changed both
  the geometry and the curve ORDER. Refuse, never coerce (`str(2.0)` is "2.0"; `sprintf("%g")` is "2").
- **`P` is float32.** At 20 km the storage floor is 9.765e-04 m regardless of compute precision.
  Use `vex_precision=64` for world-scale arithmetic and know where the floor sits.
- **Call structure beats language by ~55×.** One wrangle execution over all data, never per piece:
  1 call × 359 856 pts = 0.00129 s; 9 996 calls × 36 pts = 0.0709 s. Same arithmetic.
- **OpenCL is transfer-bound below ~10 FLOPs/point** — measured slower than VEX at every N up to
  2e7 on this hardware. Measure before reaching for it.
- **Packed prims have one vertex** — unpack before drawing wireframes or the image is empty.

### 4c. Multi-agent operations → workflow-brief boilerplate (or a skill)

- **Never rewrite history on a shared branch** — no `--amend`, `rebase`, `reset`, or `checkout` of a
  file you did not edit. (Cost: two silent rollbacks.)
- **Commit incrementally, per item.** Interruptions are routine; only committed work survives.
- **Keep a durable resume pointer on disk** naming branch, gate status, next item and recovery steps.
  This is what made every usage limit cheap — see §5.
- **Namespace scratchpad files per agent.**
- **Workflow scripts: LF only, no backticks in inserted text, null-safe post-processing.**
- **Verify the brief against `git log` before acting on it** — a stale brief cost a cycle, and the
  agent that checked was right to.

### 4d. Spec-level rules for this project

- **Never choose an implementation language for test convenience.** The Python monolith came from my
  wanting millisecond unit tests. Test the contract, not the convenience.
- **Acceptance criteria must include what an artist meets first** — TAB-menu placement, icon, port
  labels, defaults that build something good. None were in any lens until Hannes opened the node.
- **Verify by reading the built asset back**, never by trusting the build script.

---

## 5. What worked and must not be lost

1. **The independent-auditor role.** Every one of the ~20 unfailable checks was found by an agent
   that wrote none of the code. The builder never found its own.
2. **Mutation testing as the auditor's instrument** — "revert the fix and watch something go red" is
   what turned "implemented" into "verified", and what exposed decorative checks.
3. **The durable resume pointer** ([`polychain.md`](polychain.md) §0.0) — branch, gates, next item,
   recovery steps. Three interruptions, near-zero loss.
4. **A reference implementation kept runnable** so a rewrite proves itself instead of hoping.
5. **Declining work on measurement** — P4, P6 (VEX at ~9 % gain), OpenCL suite-wide, `kit_starter`.
   A measured "no" is a real deliverable.
6. **Letting measurement re-order the brief.** Twice the measured payoff contradicted the plan and
   the measurement was right (the citygen shape is curved, not cornered; deform before conform).

---

## 6. Status — what of §4 is ENFORCED IN CODE, what is IN SKILLS, what is still prose

Opened 2026-08-24, after the mutation registry landed and was independently audited. §4 is a list
of *rules*, and this retrospective's own §1 finding is that a rule living in prose is a rule that
gets violated ~20 times without anyone noticing. So each item below says where it actually lives.
**"Enforced in code" means a runner exits non-zero when the rule is broken** — not that a comment
mentions it.

### 6a. §4a — verification integrity

| §4a rule | Where it lives now |
|---|---|
| 1. A check is not written until its mutation has been seen to fail | **ENFORCED IN CODE.** `tests/polychain/mutations.py` + `run_mutation_registry.py`: every check name the five polyChain runners print must be PROVEN (a registered mutation reddened it), EXEMPT (one line saying why) or UNPROVEN (dated debt). A name in none of the three fails the sweep. **AND IN SKILLS** — `houdini-dev-loop` "how to prove a check can fail" items 1 and 9 |
| 2. State what the check CANNOT see | **PROSE.** Convention in `run_native_checks.py` / `checks.py` docstrings and in the skill; nothing asserts it |
| 3. A check may not read the same declaration its mutation edits | **PROSE** (D208, D274). The registry makes a violation *visible* — such a mutation SURVIVES and fails the sweep — but only for pairings someone has written |
| 4. Assert truth, not presence | **PROSE** (skill item 3) |
| 5. Never compare after rounding unless the rounding is the contract | **PROSE** (skill item 4), with D247/D278 as the worked example |
| 6. A cost check needs a measured ceiling | **ENFORCED IN CODE** for polyChain: `mutation_every_wrangle_ceiling_bites` (+ `_deformed`) asserts every wrangle's ceiling bites on both branches. **AND IN SKILLS** — promoted to its own numbered item, carrying both numbers (+103 % de-batch, 4 of 18 wrangles covered) |
| 7. A runner exits non-zero on any movement it prints | **ENFORCED IN CODE.** D210's exit rule, plus `ZZ_BASELINE_MOVED` as a reserved registry name so both baselined runners have a mutation proving the rule is reached from them |
| 8. Parity runs against the shipped asset | **ENFORCED IN CODE.** `asset_decompose_matches_the_rig`, `native_stages_are_really_native`, and the `stage_output_repointed` mutation. **AND IN SKILLS** — corrected this cycle: the incident was the asset's *Stage-menu* entry, not the TAB menu |
| 9. Verify an image contains its subject | **ENFORCED IN CODE.** `gate_images.py`'s drawn-primitive counts, with `gate_image_not_unpacked` as the registered mutation |
| 10. Ask what a fixture cannot reach | **PROSE** (skill item 2), with one instance mechanised: `gate_parity_sees_both_answers` is a vacuity guard, and it now has its own registered mutation (`exempt_gate_parity_collapsed`) |

**The registry's own failure modes, found by the audit that followed it and now fixed in code:**
coverage credited a mutation's whole blast radius instead of the pairing it was examined against
(57 of 97 "proven" names had never been looked at); the resumable state cache was keyed to HEAD
alone while the registry is read from the working tree, so an entry edited into one that cannot
fail replayed its old RED; a check that stopped being printed was deleted from the meta-check in
silence; and the name parser truncated at the first non-word character, folding a new
`clip_stamp.v2` into the already-proven `clip_stamp`. **An instrument built to catch unfailable
checks had four ways of reporting a green it had not earned** — which is §3's P1 applied one level
up, and the reason the instrument itself needed an independent auditor.

### 6b. §4b — Houdini domain gotchas

**IN SKILLS.** All seven are in `houdini-procedural-modeling` (§1 language + call structure, §6
traps). Two are additionally **enforced in code** for polyChain: attribute STORAGE as a contract
(`out_cast_pc_local_fpreal64`, `out_cast_ints_int64`, `mutation_spline_attr_types`) and batching
(`mutation_pc_stamp_debatched`, `mutation_pc_finalize_debatched`). The OpenCL ranking was corrected
this cycle — the list is a *reach order* with a measured entry criterion, not a ranking, because
OpenCL lost to VEX at every size up to 2e7 points on this hardware.

### 6c. §4c — multi-agent operations

**IN SKILLS** as of this cycle (`houdini-dev-loop` Rule 2, the ownership block): named git paths
only, no history rewriting, per-agent scratchpad namespacing, the durable on-disk resume pointer,
incremental commits, and workflow-script hygiene (LF, no backticks, null-safe, retry a locked
index). Also **in prose** in `polyfactory/CLAUDE.md`. Nothing here is enforced by code, and the
git half arguably cannot be from inside an agent.

### 6d. §4d — spec-level rules

**PROSE**, in `polyfactory/CLAUDE.md` (language hierarchy; never choose a language for test
convenience; acceptance criteria include what an artist meets first; verify by reading the built
asset back). One is partly enforced: `run_hda_checks.py` reads the BUILT asset rather than the
build script, and `kit_input_unplugged` / `hda_input_ports_swapped` are its registered mutations.

### 6e. §1 and §5, MEASURED: what the v2 regime did to v1 (2026-08-25, cycle V4, verified independently on HEAD `7fabfff`)

§1's finding was that the suite had become the main cost; v2 replaced accretion with four
standard techniques (a generic differential comparator against the reference, generated inputs,
Google's changed-code mutation policy, PDG/TOPs as the parallel cached runner) and then **deleted
what they subsume**, and the result is now a measurement rather than a claim: **27 162 test lines
became 15 381** and **361 printed check names became 122**, while **every one of the 32 registered
mutations is still `[ok] RED` with 0 unreached names and 0 survivors** — so the cut removed
weight, not the rail. The **80-minute sequential sweep is 3.1 minutes** (186.8 s wall for 1 526 s
of work, 8.2x on 16 cores) and the per-cycle gate is **12.9 s**; the 15-minute floor turned out to
be arithmetic rather than scheduling — the shared control must finish before any mutation
starts and the longest mutation was itself a `native` one, so deleting the 126 subsumed names in
`run_native_checks.py` (9 065 → 2 240 lines, 430 s → 27 s) removed the floor that no
scheduler could have out-run. **The budget is the one target missed, and it is red at 1.05x**
(15 381 against a tool that measures **14 682** — this document's own “~6 000-line
tool” was never measured and is wrong by 2.4x in the direction that matters); the residue is
coverage rather than accretion, and the cheapest real fix is a layering one —
`devScripts/create_pf_polychain_hda.py` **imports `tests/polychain/native.py`** to build the
shipped asset, so 645 lines of production source are counted, and stored, on the test side.
**Four gaps in `~/.claude/skills/testing/SKILL.md` are worth folding back, each earned here.**
(i) *“An image check must prove the image contains its subject” is stated for checks but
the failure is in the RASTERISER*: `gate_images.rasterise` returns early on empty input, which
silently turned `facade_images.py` — PC-G5's only image evidence — into 145 committed
lines that write zero PNGs and exit 0, the same class as the two benches this cycle deleted; the
rule should be *the renderer raises on zero drawn segments*, so every script downstream of it
inherits the floor. (ii) *“Run parallel” and the wall-clock ceilings CONFLICT, silently*:
contention does not make a runner slow, it makes it **drop checks**, which is indistinguishable
from a check that cannot fail — a SURVIVED verdict with unreached names is not a survivor
until it has been re-run alone, and a cost ceiling that reddens only under load is a flaky check,
i.e. a defect in the check. (iii) *“Generate inputs” is not enough when the system under
test has a GUARD*: 97 % of the generated differential was reference-against-reference because the
native envelope refused the cases, and only a mutation could tell “reached the code path”
from “reached the branch inside it” — measure the fraction of generated input that
actually reaches the compared path and **assert a floor**. (iv) *The skill's own ordering
(replacements first, deletions later) guarantees a window in which the budget check is red*, and
it should say so, or the first person to run it treats a working gate as a broken one; the
corollary it also omits is that a deletion pass **ends** by re-measuring the control and rebuilding
the EXEMPT/UNPROVEN declarations from it, because deleting checks breaks the pinned inventory,
orphans declarations and strands a mutation's `kills` — all three are good failures, and all
three read as a broken instrument to anyone not expecting them. Two practical notes belong with
them: **mutmut 3.x refuses to run on native Windows** (2.5.0 works, needs `PYTHONIOENCODING=utf-8`,
and **rewrites source files in place** — an interrupted run leaves a mutant on disk), and a
sweep that exports pristine per work item still needs a real `.git` to run **from**.

**And the audit's own headline, which is §2's P1 one level further down:** the `mutmut` lane
— the only automated mutation coverage over the pure-Python kernel, and the half of principle 3
no hand-written registry covers — **was configured and never run**. Its first execution, on
one of the five configured files (`decompose.py`, 387 lines), returned **352 mutants, 227 killed,
124 survived — a 64.5 % kill rate in 600 s**, and the first survivor chased to the end,
`turn <= params.corner_angle_deg` → `turn <`, **survives everything**: 238 pytest tests, the
properties at 1 500 Hypothesis examples, 405 generated scenes through the differential oracle,
`run_native_checks.py` and `run_scene_checks.py`, all exit 0 — while changing whether an exact
90° turn at `corner_angle_deg = 90.0` gets a corner post (0 corners vs 1). Neither the 89 hand
fixtures nor the seeded generator ever lands a turn exactly on the threshold. That is §3's
fixture-blindness pattern surviving into v2 in its generated form, and it is the sentence the skill
is missing: **generated inputs do not reach a boundary unless the generator is told the boundary
exists** — so a generator over a thresholded system must sample the threshold itself, and a
mutation lane that is configured but never executed buys exactly as much confidence as a check that
cannot fail.
