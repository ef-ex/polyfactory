# polyChain — Implementation Spec

**Status:** design spec v0, written 2026-08-21. **Nothing built. Parked behind citygen streets V1**
(multi-leg junction is the open blocker there). Do not start this build without Hannes
reprioritizing explicitly.
**What it is:** a general-purpose modular assembly tool for Houdini — the RailClone workflow
(pieces cloned and fitted along splines, later across facades) as a standalone polyfactory member.
**Owner doc for:** the polyChain tool. Research it is built on: [`railclone.md`](railclone.md)
(engine inventory §1, Houdini gaps §2, buildings follow-up §6, decisions §5.1) — read it first.
**UX law:** [`artist_ui.md`](artist_ui.md) §6 — binding on every parameter decision here.
**First consumers:** citygen streets (Wang-tile transition catalogue, the street-furniture stage)
then buildings B4/B6 ([`citygen_buildings.md`](citygen_buildings.md) §12).

---

## 0.0 BUILD STATE — resume pointer (read this first, keep it current)

⚠️ **If you are a fresh agent, or this session resumed after a usage-limit reset or a crash:
start here.** This block is the single source of truth for where the build stands. Everything
below it is the spec; this is the bookmark. **Every cycle must update this block** (it is cheap,
and it is the only thing that survives a context loss).

**Overnight autonomous build authorized by Hannes 2026-08-21** — this supersedes the
"parked behind streets V1" status line above for the duration of the run. Opus implements,
Fable reviews, headless `hython` verifies, commit per cycle on branch `polychain`, never push.

| Field | Value |
|---|---|
| Branch | `polychain` (created 2026-08-21 off `cityGen`) |
| hython | `"C:/Program Files/Side Effects Software/Houdini 22.0.398/bin/hython.exe"` (verified working headless) |
| Last completed | **CYCLE P2-3V — INDEPENDENT VERIFICATION OF P2-3R (2026-08-22). DEV-LOOP RULE 0 IS DISCHARGED: P2-3R is AUDITED, not merely implemented.** A fresh agent that wrote none of it ran every suite from clean, re-derived both baseline diffs key by key, ran **17 mutations**, and judged PC-G5 on images regenerated from this build. **All 22 of P2-3R's fixes are real and present** — each was reproduced by reverting it and watching something go red. **But SIX of them had no assertion anywhere and could be deleted with the whole suite green**: D139's `pc_warn_row_overflow`/`pc_warn_row_kit_gap` (neither string appeared in a single test file or run log); `clip_stamp`, whose `ok = area or n == 0` made it **unfailable on exactly the area builds it was written for**; the alias-collision drop; `marker:<id>`'s five Y classes (the silent stand-in PC-G5 condition 5 counts at 0); the `extra_roles` slot-pair filter; and `rows_unbuilt` + `pc_warn_row_clipped_out`, which were **dead code** — `FM_area_taper` does not exercise them, its 1.6e-9 m span is still a span and `cell_grid` catches that hole by its own solved-vs-built difference. **D147 closes all six**: cases `FT_row_overflow`, `FU_row_kit_gap` (whose `geometry_digest` is `FC_rect`'s, so the only difference is the warning) and `FV_area_short`, the new `rows_clipped_out` check, `clip_stamp` re-written to assert the TRANSFER from row curve to element, and four `hou`-free unit tests. **All six mutations now go red.** Suites: **22 phase-2 cases / 683 rows**, 90 phase-1 cases / 5 559 rows, `run_hda_checks`, `scale_gate` (9 rows), `gate_images`, **350 unit tests — 0 failing, and the phase-2 baseline diff is ADDITIONS ONLY (not one recorded value moved).** ⚠️ Two numbers in P2-3R's write-up were wrong and are corrected in place: the suite is **346** unit tests, not 386, and `prims_wrappers_built_2d_rows` was **78 148**, not 78 132. One unreported baseline movement: `FC_rect/corner_seam_m` 0.0 → 1e-06, D141's reversed traversal, 1 micron against a 2e-3 tolerance. Read §12's P2-3V entry before touching anything. |
| Next up | **Cycle P2-4 then P2-5** (§7.10) — the payload half from input 3, then the Y fit's `aligned` mode (D122) and `pc_extend` as a parm. ⚠️ **GATE PC-G5 HAS BEEN JUDGED AND IT DOES NOT PASS** — not because the facade is wrong but because two of its seven conditions have nothing behind them. **Conditions 1, 2, 5, 6, 7 PASS and are mutation-proved**, and condition 1 was verified NON-VACUOUS (`_corner_caps` yields **24 groups, 24 paired and measured** — the 6 x 4 the gate asks for, probed rather than read off the label; `corner_seam_m` 0.0). **Condition 4 is TRUE but UNASSERTED** — 0 of 176 placements carry a `slice_t` and no check says so; **write that one line on the way past, it is the cheapest untested truth in the tool.** **Condition 3 needs a FIXTURE as well as a mode**: every row of the L uses the same kit over the same leg lengths, so `aligned` and `free` are indistinguishable on it however `aligned` is implemented — P2-5 must ship unequal leg lengths or a per-row kit with it. **The images were looked at**: the plan is a closed ring with no holes or overlaps and a 45° bisector cut at all five convex vertices and the reflex one; the corner column runs unbroken ground-to-cornice with the cornice band turning round it; bend mode correctly has no corner post. Still owed and unchanged: P2-7's real clipping (per-module `pc_clip`, sub-spline independence, even-odd nesting, `slice`, i.e. all of PC-G6), P2-8, P2-9, §7.7's kit slicer — and phase 1's own GUI viewport pass on PC-G1/PC-G2, the streets acceptance and standing finding (11). Run `hython tests/polychain/run_2d_checks.py` and `python tests/unit/test_polychain_array2d.py` before and after every change. |
| Gates | **ALL FOUR RE-CONFIRMED BY P5cV (2026-08-22) — PC-G1 and PC-G2 through the parm face and judged on images, PC-G3 on the 9-row ladder under both z-modes, PC-G4 mutation-proved (reverting D91 reports `moved: padding`). All four still owe the GUI viewport pass and nothing else changed.** PC-G0 ✅ resolved (§2.3) · **PC-G1 numerically complete + IMAGE-VERIFIED (headless), GUI viewport pass still owed** — the closed rectangle and the L close in both corner modes, all four fill modes, the gate on its marker (1.8e-7 m), convex and reflex corners; the bend corner's butt wedge is MEASURED and baselined as the accepted limit (D36 extended), and cycle 6's mutation of it fails by 1.10e-02 m on `CJ_bend_butt_120`. Cycle 8 closed the last hole in its parm face: the **marker slot is authorable on the page** (D88), so PC-G1's gate-on-a-marker no longer needs a payload, and an unread marker warns. **Cycle 9 rebuilt the whole figure THROUGH THE PARM FACE and looked at it** (`HC_{miter,bend}_{top,iso}.png`, `HG1_*.png`): the miter's two legs terminate into a corner post with the 45° bisector cut clean across it and the tops flush; the bend turns through the elbow as one continuous top arris with no corner post (D36's ring weld) and only the accepted butt notch; all four Fit Methods close flush on the spline; and the gate authored with **Piece at Markers + Marker Id and NO payload** lands at **x 7.200000..8.800000, centre 8.000000, error 1.788e-07 m**, with the unread-marker warning firing beforehand. PC-G1 no longer owes its parm face — only the GUI viewport pass · **PC-G2 numerically complete + IMAGE-VERIFIED (headless), INCLUDING the curving-spline variant it used to owe; GUI viewport pass still owed** — cycle 6 built the gate's own wording: a 24 m spline that **turns in plan (±3.6 m S-curve) and climbs 2.4 m**, resampled at 0.25 m, over a 2D terrain (`1.1 sin(2πx/13) + 0.8 cos(2πz/9) + 0.06x`), conform ON. All four modes pass **50 of 50** suite checks with **0 failures and nothing baselined**: `plumb_deg` **0.0** over 14 vertical pieces, `flat_stepped_m` **0.0** over **240 stepped posts, 240/240 still PACKED**, `bank_deg` **27.15°** adaptive, camber ON halving the residual to the surface normal (`camber_deg` 37.31° → **17.20°**), `conform_contact_m` **0.0**, `conform_misses` **0**, `inward_faces` **0**, no warnings. Judged on `VG2P_{vertical,stepped,adaptive}.png` and `VG2C_camber_cu.png`: the pickets' ribs are dead vertical while the run's foot follows the ground line, the adaptive rail's ribs lean perpendicular to the drape, the posts' tops make a clean sawtooth over a smooth ground line, and the cambered rail is visibly rolled onto the cross-fall. The **riser under each stepped piece is there and is expected** — it IS stepped mode — and it measures **0.061 m** on this hill; §4.4's flatten-under is BUILT as of cycle 10 (D98) and takes the AIR under each piece (`stepped_float_m` 0.054818/0.061280) to **0.0** with all 240 pieces still packed, leaving that riser where it is. **Cycle 9 re-rendered all of it through the HDA's parm page** with the terrain on input 4 (`HG2_*.png`): the pickets' ribs are plumb while the run's foot tracks the ground line, the stepped posts stand plumb with feet on the ground and tops stepping over it, the adaptive rail's ribs rake perpendicular to the drape, Tilt to Surface visibly rolls the rail onto the cross-fall, and the whole 24 m S-curve reads as a fence on a hill. Only the GUI viewport pass is owed · **PC-G3 numerically MEASURED at scale, and narrower than its headline** — 20 km, 10 005 × 2 m bendable panels: **10 005 packed, 0 deformed, one shared `geometryid`, 10 005 real points, +12.1 MB RSS, 0.42 s** as a two-point spline and **the same numbers at 0.55 s** as a **20 011-vertex resampled polyline** — independently reproduced in cycle 6, and D69 is what buys it (reverting D69 takes the resampled form to 0 packed / 10 005 deformed / 360 180 points / **21.9 s**). ⚠️ ~~The gate holds for a STRAIGHT resampled run only~~ — **CLOSED by D75 in cycle 7**: `hython tests/polychain/scale_gate.py` is the harness now, and R = 12 000 / 2 000 / 80 m all read **10 000 packed / 0 deformed / 10 000 points / +5.1 MB / ~0.60 s**, while R = 10 m (five times the budget) still deforms all 10 000 at 10.8 s. ⚠️ **CYCLE 9 RE-MEASURED THIS AFTER D87 AND THE TERMS ARE NARROWER AGAIN.** Those three rows are green because the starter kit's `panel` is **yaw-only** (`pc_zmode = vertical`), so the budget was spent on `rz` = 0.03 m and D87's off-spine term was switched almost all the way off — and `scale_gate.py` was still deciding pass/fail from `4/(8R)`, **the spine sagitta D87 retired**. Re-run under `zmode = adaptive`, where the panel's full 0.90 m height rides the frame: **R = 12 000 m and R = 2 000 m stay 10 000 packed / 10 000 points / ~0.6 s**, but **R = 80 m is 0 packed / 10 000 deformed / 360 000 points / 11.0 s / +34.7 MB** — `0.90 x 0.025 = 0.0225 m`, 2.25x `bend_tol`, so unpacking is CORRECT. D97 put the expectation on each ladder row with its reason and runs the ladder under both z-modes: **9 rows, 0 failing**, and mutating the budget 50x now fails 2 rows where it failed none. **PC-G3 passes on its own terms** — 10 005-piece packed instancing at 20 km, one `geometryid`, sub-second, +12 MB — and those terms are: a straight or gently-turning-IN-PLAN run, or any run whose module is yaw-only. A TALL module on an R = 80 m arc, or ANY module on a climbing run (D65's shear), costs the 11 s / 360 k-point deform path. The FLOOR rides the suite: `A_straight`, `CE_all_packed`, `CA_swap_module`, `CF_resampled_straight` and `CG_resampled_bendable` are asserted 100 % packed and `over_unpacked` proves nothing unpacks without a reason. ~~Owed: the deform path's VEX rewrite~~ — **DONE, cycle 10c (D102/D103)**: profiled first, the cost was the per-prim STAMP (9.023 s of 14.136 s, 4 758 096 `Prim.setAttribValue` calls) and not the deform loop (0.201 s, 1.4 %); through `hou.Geometry`'s bulk array setters the two deformed rows go **11.159 → 1.548 s (7.21x)** and **11.181 → 1.597 s (7.00x)**, bit-identical on all 83 cases, and VEX is measured and declined · **PC-G4 ✅ PASSES — as of cycle 12 (D107); before that its sweep was pretending** (§10 cycle 7): the same fence driven entirely by a style payload on input 3 with the parms at defaults, asserted in `tests/polychain/run_hda_checks.py` — the payload replaces the modules, the styleId and the ids, matches the kernel built from the `Style` object directly, and **the parms are provably inert while it is wired** — cycle 8 turned that from two parms into a SWEEP of the whole page (`swept 36 parms; moved: none`, ids AND rounded positions, exempting only `display`/`show_warnings`/`kitfile` by name), which is what caught `padding` still being live under a payload (D91). The generic-loop rule is audited by construction: `polychain/style.py` contains no style name and no branch per name, and `style_round_trip` re-proves it on all 73 cases. **Cycle 9 re-measured PC-G4 independently, in §2.1's own stronger wording — the SAME fence**: the parm face's own `Style` written out through `style.write` and wired back into input 3 of a second node with the parms at defaults produces output **identical on element ids, module names, rounded point positions AND every packed prim's full transform** across all **8 fill x corner combinations** (adaptive/scale/evenly/count x miter/bend, 35 to 137 prims). The page swept under that payload: **32 parms nudged, 0 moved the geometry**. A style the code has never heard of — `a_style_nobody_wrote_code_for`, carrying a `marker:42` slot — built **52 prims, 4 modules, 0 warnings** with no code change. The branch-per-name grep over the whole kernel returns nothing but `style_from_parms`' DEFAULT VALUE `"pf_polychain"`; the names that do appear in conditionals (`corner`, `default`, `start`, `end`) are §3.3's fixed slot vocabulary — the kernel's own schema, not any style's — and a slot outside it is dispatched generically. ⚠️ **CYCLE 12 MUTATION-TESTED THIS AND FOUND IT BLIND.** Reverting D91 - the `padding` parm applied unconditionally, so a wired payload feels it again - left the whole HDA suite **green**, `parms_inert_under_payload … moved: none`, with a debug print proving `_padded` really ran at 0.37 under the payload. The fixture was the cause, not the sweep: its `Params(fill="scale")` fence does not move for ANY `pc_pad` - `gate.pad` 0.0 -> 0.185 -> 0.400 with the output stuck at 44 prims, 12 elements and an identical point sum. **The fixture is `adaptive` now (D107)** and the same revert reports **`moved: padding`**; the shipped code reports `moved: none`. `scale` coverage is not lost - cycle 9 sweeps all 8 fill x corner combinations separately. GUI viewport pass owed like the others |

**⚠️ NEW 2026-08-22, after phase 1 closed: [§11](#11-nativevexopencl-port-plan) is the ordered
Native/VEX/OpenCL port plan**, synthesised from two independent audits. Read it before optimising
anything. Two of its findings retire recorded conclusions: **D103 is retracted** (`attribvop`'s
`vexsrc="snippet"` gives arbitrary 64-bit VEX from a verb, with no VOP network - verified twice on
this build), and **PC-G0's "fork the Chain SOP" decision should be retired** (Chain builds
12 011 652 points where polyChain builds 10 000 packed prims, and it has no verb). The port's own
headline: **62 % of the real node cook is 14 `hou.Prim.setAttribValue` calls per packed piece** -
D102's fix, never applied to the packed writer. Nothing in §11 is implemented.

**⚠️⚠️ NEWEST, AND IT OUTRANKS THE "Next up" ROW ABOVE: [§13](#13-native-network-architecture--the-rebuild-brief)
is the NATIVE NETWORK ARCHITECTURE, written 2026-08-22.** Hannes opened the HDA, found it is two
nodes — a ~6 000-line Python SOP and a null — and ruled: *"everything geometry related should be
either native nodes, vex or opencl. Python can be used for ui or processing data which is not
possible to process with the other 3 mentioned options."* That is a rebuild of the kernel's **body**
(the parm face, the data contracts and all 6 242 baselined values stay), and it **supersedes
§11.9's "verb-only, no `createNode`" rule (D148)** while carrying every other §11.9 rule forward.
§13 is design only — nothing is implemented — and it was written from live `hython` probes whose
numbers are in §13.2. Its build order is N1..N10 in §13.9, starting with the parity rig and then
**the fitting solve in VEX**. The current Python kernel becomes the **reference implementation and
parity oracle** and is never deleted. ⚠️ It is numbered **§13, not §12** — §12 was already the
phase-2 build log; do not renumber either.

**To resume the autonomous run**, re-arm the loop with exactly this:

```
/loop Implement ideas/polychain.md end to end. Each cycle: pick the next unbuilt item in §8 build order, implement it (Opus), review it (Fable), fix findings, verify headlessly with hython, commit, and append results to the build log in polychain.md. Decide all open questions yourself. Do not stop until phase 1 gates PC-G1..G4 pass.
```

**Recovery procedure after any interruption:**
1. `git log --oneline polychain` — committed work is the truth; the last commit is where you are.
2. `git status` — if the tree is dirty, the interrupted cycle left work mid-flight. Run the tests;
   keep what passes, revert what does not (`git checkout -- <path>`), then redo that cycle.
3. Re-read this block's *Next up* row, then continue the §8 order. Do not restart completed stages.
4. Update this block and the §10 build log before starting the next cycle.

### ⚠️ LIVE BRIDGE IS WEDGED (2026-08-22, verified twice)

`houdini_status` pings fine (answered off-thread) but **every main-thread HOM call times out at
30 s** — the GUI's main thread is blocked (busy cook or a modal dialog). Confirmed independently by
cycle 3v and again by the orchestrator.

**Consequences, decided:**
1. **Do not spend cycles on the live bridge.** Try `houdini_status` once; on any timeout, go
   headless immediately and mark the gate `numerically green, image-verified headless, GUI
   viewport pass owed`.
2. **Headless image verification is the standing substitute** — and as of §11.8 P5V it is
   **COMMITTED**, so the "reuse it, do not rebuild it" line above is finally actionable:
   `hython tests/polychain/gate_images.py [outdir]` drives PC-G1 and PC-G2 through the HDA's own
   parm page, proves page and kernel agree on ids AND rounded positions, runs the committed
   checks on the result, and rasterises the node's output to PNG with `zlib` alone. It had been
   rebuilt from a scratchpad three times before anyone committed it.
3. ⚠️ **`/obj/polychain_gate` may still be sitting in Hannes' session** — cycle 3v could not clear
   it, and neither could the orchestrator. **Morning item for Hannes:** delete that subnet and
   restart the bridge if a GUI viewport pass is wanted. Nothing was ever saved to the hip file.

### Two Houdinis — which one to use for what (updated 2026-08-21, mid-run)

Hannes started the **live MCP bridge** on a clean Houdini 22.0.398 GUI session
(`untitled.hip`, empty `/obj`). Both paths are therefore available, and they are NOT
interchangeable:

| Use | Path | Why |
|---|---|---|
| Building, unit tests, headless scene checks, anything parallel | **hython** (throwaway process) | Parallel-safe: every agent gets its own session. Default to this for ~all work. |
| **Visual gate confirmation** (PC-G1 corners, PC-G2 fence-on-a-hill) | **live bridge** (`houdini_render_view`) | GUI-only; flipbook/viewport rendering does not run under hython (`tests/README.md`). |

**Live-session rules — non-negotiable, it is Hannes' machine:**
1. **Serial access only.** Never let two agents drive the bridge at once; a workflow stage that
   renders must run alone, never inside a `parallel()`.
2. **Build under a dedicated `/obj/polychain_gate` subnet; delete it when done.** Leave the
   session as you found it.
3. **Never `hou.hipFile.save()`** over the user's path, and never `hou.hipFile.clear()` without
   checking `hasUnsavedChanges()` first — if the session ever has unsaved work in it, that is
   Hannes', so stop and use hython instead.
4. Renders are for **judging geometry**, per the show-don't-tell rule — a gate is judged on the
   image, not on a test name. Save gate images to the scratchpad and reference them in §10.

⚠️ If the bridge is unreachable when you wake (`houdini_status` fails — the session may have been
closed), do NOT block: continue the build on hython, mark affected gates
`numerically green, visually unconfirmed`, and leave them for Hannes.

---

## 0. Instructions to the implementing agent

1. **Read before building, in this order:** `houdini_get_skill("houdini-dev-loop")` (mandatory,
   non-negotiable), `houdini-procedural-modeling`, `houdini-tool-design`; then
   [`railclone.md`](railclone.md) in full; then §3–§6 here. The RailClone doc URLs cited in
   `railclone.md` §1 are the behavioral reference — when a mechanism here is underspecified,
   RailClone's documented behavior is the default answer.
2. **Never build from memory.** Probe the live Houdini session for real node parameters; the
   dev-loop skill is the discipline.
3. **Nothing is "done" until independently audited on the current build** — and per the
   show-don't-tell rule, every gate below is judged **in the viewport**, not by test names.
4. Deviations from this spec are fine when the geometry argues for them — record them in this
   file (this repo's convention: the doc is the build log's contract, see
   [`citygen_streets.md`](citygen_streets.md)).

**Data conventions:** [`conventions.md`](conventions.md) — suite-wide attribute naming (`pf_`
prefix) and node hygiene (`_*` internal, deleted before output). Binding here; §3 renames `pc_*`
to `pf_*` after the §12 rebuild reaches parity, and the `_*` rule applies to the rebuild now.

## 1. Scope and non-goals

**Phase 1 (this spec's build target): the 1D kernel** — RailClone L1S parity minus its warts.
**Phase 2 (§7, BUILDABLE SPEC as of 2026-08-22; nothing built): the 2D array** — built on phase 1,
on the buildings
timeline.

**Non-goals, permanent:**
- **No junctions/forks/intersections.** RailClone refused them for 12+ years; citygen streets owns
  that problem. polyChain stops cleanly at spline ends and lets consumers author junction
  geometry. Refuse gracefully, never half-ship.
- **No massing.** polyChain dresses; it never decides building/roof volumes (citygen B2/B5 own
  that).
- **No content library beyond a starter kit.** Domain preset corpora belong to the domain tools
  (decision, [`railclone.md`](railclone.md) §5.1).
- **No new file formats.** Kits and styles are Houdini geometry carrying attributes
  (attributes-not-JSON, [`citygen.md`](citygen.md) contract).

**Binding suite constraints** (sources in [`railclone.md`](railclone.md) §5 and
[`citygen.md`](citygen.md)): 100 % vanilla Houdini, no Labs runtime dependency; metric metres;
offline-render target; warn-never-block with warnings persisted as attributes; every instance
supports swap and replace; deterministic — same inputs + seed ⇒ identical output, ids stable
across recooks.

## 2. Architecture

### 2.1 The two-face principle (load-bearing)

The kernel consumes a **style payload**: kit + slot assignments + selection rules, encoded as
geometry attributes (§3.3). It has two authoring faces over ONE representation:

- **Standalone artist face:** the `pf_polychain` HDA's parameters author the payload internally —
  pick a kit, assign slots, set modes. No wiring beyond spline + kit.
- **Pipeline face:** a style payload wired into the dedicated style input **overrides the parms
  entirely**. This satisfies citygen's foundation requirement — *a template may not live inside a
  node; it arrives on the data stream, and consumption is a generic loop, never a branch per
  name* ([`citygen_streets.md`](citygen_streets.md) §, quoted in `railclone.md` §3).

The port exists from day one even if streets wires it later — the streets doc explicitly warns
the port count must be fixed before its segmenter is cut.

### 2.2 Node family (working names; `pf_` per suite convention)

| Node | Role |
|---|---|
| `pf_polychain` | The flagship artist-facing HDA. Inputs: 1 = spline(s), 2 = kit, 3 = style payload (optional, overrides parms), 4 = surface (optional, conform). |
| `pf_polychain_core` | The kernel SOP network inside it — decompose → plan → place → deform → finalize (§4). Separately instantiable for TD use; unlocked (graph stays reachable, artist_ui rule 10). |
| `pf_polychain_kit` | Kit authoring helper: tag modules with roles/sizes/padding, write the manifest attrs, validate (§3.2). |
| `pf_polychain_slice` | Phase 2 — the RC-Slice-equivalent kit ingestion tool (§7.3). |

Compiled-SOP-safe throughout where feasible; VEX over Python everywhere hot.

### 2.3 Chain SOP seed — gate PC-G0

Decision ([`railclone.md`](railclone.md) §5.1): Chain SOP is the **seed, not a dependency**.
**Answered 2026-08-21 (PC-G0):** `definition()` returns an HDADefinition in `OPlibSop.hda` — it is a
factory HDA, so **fork the network** as the kernel's starting point (copy into the pf namespace;
never edit the factory asset in place). Either way its parameter model — piece patterns,
fit modes, rigidity, boundary behaviors ([docs](https://www.sidefx.com/docs/houdini/nodes/sop/chain.html))
— is the base-layer spec the kernel extends.

## 3. Data contracts

All names prefixed `pc_` to stay collision-free on shared streams.

### 3.1 Input spline schema

Plain polylines (the streets product; NURBS resampled on ingest). Everything derived-by-default,
overridable-by-attribute (start realistic, end artistic):

| Attr | Class | Type | Meaning |
|---|---|---|---|
| `pc_corner` | point | int | −1 suppress / 0 auto / 1 force. Auto = angle > `cornerAngle` parm (default 30°). Replaces Max's vertex types, which Houdini polylines lack. |
| `pc_section` | prim | int | Optional explicit sectioning (RailClone's material-ID limits). Multiple polyChain instances may each claim a section range. |
| `pc_style` | prim | string | Optional per-curve style key into the payload (multi-style streams). |
| curve identity | prim | int/str | Passed through untouched; consumers' ids (e.g. streets `edge_id`) feed `pc_elem_id` (§3.4). |

**Markers** arrive as a separate point cloud merged into input 1 (marker points carry
`pc_marker = 1` so they're never treated as curve points): `pc_curve` (curve ref),
`pc_u` (0–1) **or** `pc_dist` (metres, negative = from end), `pc_marker_id` (int, drives
selection), `pc_marker_data` (dict — free channels, the RC 9-channel analog). Rationale: markers
must not add curve vertices (topology-stable), and a point cloud is the streets-shaped carrier.

### 3.2 Kit format

One geometry file per kit: **packed prim per module** + one point per module carrying manifest
attrs, plus a detail dict `pc_kit` (kitId, version, sources/provenance, `human_scale_reference`
— mandatory, per buildings §12.9). Per module:

| Attr | Type | Meaning |
|---|---|---|
| `pc_role` | string | `default` · `start` · `end` · `corner` · `evenly` · free tags for marker/rule targeting. One module may carry several (space-separated). |
| `pc_size` | vector | Nominal fitted size; falls back to packed bbox. |
| `pc_pad` | vector2 | Left/right padding, metres, negative = overlap. |
| `pc_deform` | int | 0 rigid (stepped) · 1 bendable · 2 sliceable (bend+slice allowed). Governs instancing (§4.6). |
| `pc_zmode` | string | `adaptive` · `vertical` · `stepped` (per-module default, style-overridable). |
| `pc_variant` | string | Variant group for swap; `pc_weight` float for random selection. |

This deliberately matches buildings §12.9 (`moduleRole`, nominal bay size) so building kits and
polyChain kits converge on one manifest convention — reconcile names with the buildings agent
when B-stages start; buildings' `*_cut_*` opening convention composes on top.

### 3.2b Prototype identity — reuse `pf::merge_enum`, and keep it distinct from element identity

Hannes, 2026-08-22, pointing at an existing polyfactory node: **`pf::merge_enum::1.0.0`** ("PF Merge
Enum") is the house workflow for instancing prototype setup — written pre-USD. 500 inputs, a
for-each over them, and one point wrangle:

```c
int iteration = detail(1, 'iteration', 0);
setpointattrib(0, chs("attrib"), @ptnum, iteration);
```

Every input's geometry carries its **input index** under `enum_attr` (default `enum`), with an
optional pack. Merge a pile of assets, keep each identifiable by integer.

**Two consequences for polyChain:**

1. **Emit the house `enum` for prototypes.** §3.2 identifies modules by `pc_module`, a *string*.
   A **USD PointInstancer addresses prototypes by `protoIndices` — an integer array**, so the
   integer is what the instancing path actually wants and the string has to be mapped anyway.
   The kit builder should either reuse `pf::merge_enum` outright or follow its convention, and the
   kit manifest records the index→module mapping so the number is meaningful. This keeps
   [`citygen.md`](citygen.md) §7 item 1 (instancing substrate: PointInstancer vs instanceable prims
   vs primvar-keyed ids) OPEN rather than quietly foreclosing it.
2. ⚠️ **`enum` must NEVER be used as element identity.** It is input-ORDER dependent — insert an
   asset in the middle and every later number shifts. That is fine for prototype setup, where the
   order is fixed at kit-build time; it is fatal for `pc_elem_id`, which is deliberately a
   STRUCTURAL address (§3.4) so the override cascade survives regeneration. **Two distinct
   concepts, both needed:** `enum` = *which prototype*, stable per kit build; `pc_elem_id` =
   *which instance*, stable per recook. Do not conflate them; do not derive one from the other.

**And note the style argument.** `pf_merge_enum.hda` is a ~10-node network — for-each, wrangle,
merge, pack, switch — doing its job idiomatically in VEX, sitting in the same `otls/` directory as
the Python monolith §12 exists to replace. It is the house pattern, and a better brief for the
rebuild than prose.

### 3.3 Style payload

Geometry-as-data on input 3: detail dict `pc_style_meta` (styleId, version, seed policy) + one
point per **rule**, ordered:

| Attr | Meaning |
|---|---|
| `pc_slot` | Which slot the rule feeds (`default`, `start`, `end`, `corner`, `evenly`, `marker:<id>`) |
| `pc_select` | `first` · `sequence` · `random` · `conditional` |
| `pc_modules` | Ordered module list (roles/names/variant groups; weights from kit or inline dict) |
| `pc_cond` | For `conditional`: a **data condition**, not code — dict of `{subject, op, value}` with subjects `sectionLength` · `splineLength` · `u` · `cornerAngle` · `segIndex` · `markerData:<key>` · `attr:<name>` (reads any spline prim attr). Covers RailClone's Conditional node test list. |
| `pc_scope` | Randomness correlation scope: `segment` · `section` · `spline` · `generator` (seed derived from `(styleSeed, scope key)` — never from point numbers). |

Escape hatch for what the dict can't say: `pc_vexpr` string (a VEXpression evaluated per
candidate segment). Data first, expression second, code never — matches the suite's
data-not-grammar law ([`artist_ui.md`](artist_ui.md) §5).

### 3.4 Output

Packed prims (undeformed) + real geometry (deformed, `pc_deformed = 1`), every element carrying:

- `pc_elem_id` — hash of `(curve identity, section index, slot, index-in-section, styleId)` —
  **structural address, never cook order** (buildings §12.7 rule). Survives recooks with
  identical inputs; this is the key the override cascade uses for swap/replace.
- `pc_slot`, `pc_module`, `pc_variant`, `pc_section`, `pc_u` (anchor position), provenance
  `pc_generated = 1`.
- Warnings persisted per element (§5): `pc_warn_kit_gap`, `pc_warn_corner_degenerate`,
  `pc_warn_overflow` (section shorter than mandatory start+end).
- Kit gap behavior: **blank stand-in box at nominal size, never a failure** (buildings
  `warnModuleMissing` rule).

Swap = re-point `pc_module`/`pc_variant` via an override wired upstream of finalize; replace =
hero geometry keyed by `pc_elem_id` swapped in at finalize. Both must work without touching the
style.

## 4. The kernel — phase 1 algorithms

Pipeline stages inside `pf_polychain_core` (each a visible child network, separately debuggable):

### 4.1 Decompose
Per curve: resolve corners (`pc_corner` auto/force/suppress), markers, explicit sections →
ordered **section list** (a section = span between consecutive corners/section-breaks; RailClone
semantics). Emit per-section length, start/end frames, corner angles.

### 4.2 Plan (the fitting solve — pure math, no geometry yet)
Per section, from the style: reserve start/end module lengths, place evenly anchors
(distance/count, justify, adjust-to-end threshold), then fill the remainder in the active mode:

- `tile` — floor(L/s) whole pieces + one **sliced** remainder (slice only if the module's
  `pc_deform = 2`, else adaptive-fallback + `pc_warn`); RailClone Tile.
- `scale` — pieces stretched so Σ = L exactly.
- `adaptive` — n whole pieces, all scaled by L/(n·s); the `adaptivePct` parm is the
  add-one-more threshold. **Default mode** (architecture rule, `railclone.md` §6.3).
- `count` — fixed N scaled.

All modes pack with `pc_pad` (padding moves neighbors, never the piece — RailClone semantics;
negative overlaps). Output: a **placement plan** — points with (section, slot, module, u-range,
scale, slice flags). The plan is inspectable geometry: this is the tool's debuggability
contract.

### 4.3 Corners
Per corner, mode from style: **bend** (default piece deformed across the vertex) or **miter** —
corner module(s) duplicated both sides of the vertex and sliced at the bisector plane
(odd count ⇒ symmetric about the vertex, even ⇒ asymmetric — RailClone's compose rules), with
offset (± % of module length: pull-in and slice vs push-apart gap) and optional fillet radius
(procedurally round the path first). Neighboring default pieces slice against the same plane
(`Reset`/`Extend`/`Symmetric` displacement policies). Narrow angles (< parm, default 15°) fall
back to bend + `pc_warn_corner_degenerate`. This stage is the hard 20 % — see gate PC-G2.

### 4.4 Place + deform
Materialize the plan. Chord-frame construction **reuses the streets mechanism** (capture in
chord frame `u`-along/`v`-across ÷ chord length, rebuild from section nodes —
[`citygen_streets.md`](citygen_streets.md) §, measured; mind its float32 lesson: skip bit-exact
rebuild when unmoved). Z-modes per module/style: `adaptive` (full tangent frame, banks),
`vertical` (yaw-only frame, vertices Z-displaced to elevation — pickets), `stepped` (yaw-only,
constant Z, optional flatten-under). Bend only when `pc_deform ≥ 1`; **no auto-subdivision** —
warn when a bent module's segment count is too low to follow curvature (measurable: chord
deviation > tolerance).

### 4.5 Surface conform (input 4)
Ray-project placements along −Z (axis parm) onto the surface; per-module optional Y-tilt to the
surface normal (camber). Composes with Z-modes exactly as RailClone documents (adaptive/vertical
deform to the surface, stepped sits on it).

### 4.6 Finalize
- **Instancing segregation, automatic:** a piece whose result is expressible as
  transform × uniform-or-axis scale of the kit module stays a **packed prim** (transform on the
  intrinsic); anything sliced/bent/Z-deformed is unpacked real geometry tagged `pc_deformed`.
  The style/parms never ask the artist to manage this (RailClone's deform-aware engine, §1.7 of
  the study).
- Slice caps: polyfill + box UV from the module's mapping, cap material tag.
- Stamp §3.4 ids/attrs, collate warnings, apply swap/replace overrides.
- Output also feeds the undecided citygen instancing-substrate test (PointInstancer vs
  instanceable prims vs primvar-keyed ids, [`citygen.md`](citygen.md) §7 item 1) — polyChain
  emits packed prims + stable ids and stays agnostic; do not decide USD substrate here.

## 5. Parameter surface (artist face)

[`artist_ui.md`](artist_ui.md) §6 rules apply verbatim: page starts from decisions, not graph
values; **two disclosure levels max** (main + one Advanced folder); every parm has range, units,
help text; defaults render a good result on the starter kit out of the box.

**Main page:** kit picker (gallery-thumbnail front door) · slot assignment (per-slot module
menus from the kit manifest) · fill mode (default `adaptive`) · spacing/padding · corner mode
(bend/miter) + fillet · Z-mode · seed. **Advanced:** adaptive %, justify/adjust-to-end, bevel
displacement policy + offset, corner angle thresholds, conform axis/tilt, instancing overrides,
warning visualization toggle.
**Proxy LOD is an acceptance criterion, not polish** (artist_ui rule 7): box/point display mode
must stay interactive at 10k+ segments; the plan stage (§4.2) is cheap — recook full geometry
only on release, plan-preview while dragging.

### 5.1 HDA metadata — REQUIRED, not polish (Hannes, 2026-08-22, looking at the built node)

Two defects found on the shipped asset. Both are **acceptance criteria for any rebuild** — an
artist meets the tool through these before they ever touch a parameter.

**a) It is not in the TAB menu where it belongs.** The asset has **no `Tools.shelf` section at
all**, so it lands wherever Houdini defaults it. Every other polyfactory asset declares one — the
house convention, read off the shipped `.hda` files:

| | |
|---|---|
| Submenu | `Poly Factory/Modeling` (what `pf_citygen_*`, `pf::pf_kitbash`, `pf::advanced_tube` all use; `Poly Factory/Utils` is for helpers, which this is not) |
| Context | SOP |
| Icon | **not** the default `SOP_subnet`. Either a Houdini built-in that reads at a glance (e.g. `SOP_copytopoints`, `SOP_orientalongcurve`) or `$POLYFACTORY/icons/<name>.svg` — both patterns are in use (`pf::box` ships an svg, `pf::fast_clip` uses `SOP_clip`) |

**b) The inputs and the output are unlabelled.** A four-input SOP whose inputs say nothing is
guesswork. Label them, and mark which are optional — this is the §2.2 port table, in artist words:

| Input | Label | Notes |
|---|---|---|
| 1 | `Curves` | the path(s) to build along — required |
| 2 | `Kit` | the modules to build from — required |
| 3 | `Style Payload` | optional; **when wired it overrides the parameters** (the §2.1 pipeline face) |
| 4 | `Surface` | optional; the ground to conform to |

Output 0: label it for what it is (the built geometry). Set input labels via the HDA definition's
input-label API, not by hand-editing the dialog script.

⚠️ Verify by INSPECTING THE BUILT ASSET (read back `Tools.shelf`, the icon and the labels from the
`.hda`), never by trusting the build script — the build script is what got this wrong.

## 6. Phase-1 gates and acceptance

In order; each viewport-judged, then independently audited (dev-loop rule):

- **PC-G0 — Chain SOP probe. ✅ RESOLVED 2026-08-21.** `hou.nodeType(...,'chain').definition()` returns an **HDADefinition** in `$HFS/houdini/otls/OPlibSop.hda` (Houdini 22.0.398) — Chain SOP is a
  factory **HDA, not a compiled C++ SOP**. The fork path is therefore open: copy the definition into
  the polyChain namespace and extend its network, rather than reimplementing distribution/deformation.
  Verify the same on 21.0.631 before shipping if both builds must be supported.
- **PC-G1 — the fence.** Closed rectangle spline + starter kit (post, panel, gate, corner-post).
  All four fill modes; corner mode both bend and miter; a gate placed by marker; a painted
  `pc_section` swap mid-run. Pass: no gaps/overlaps at any corner in either corner mode, gate
  exactly at its marker, adaptive shows whole panels only.
- **PC-G2 — the hill.** Same fence on a sloped, curving spline over a terrain surface (conform
  on): `vertical` pickets stay plumb, `stepped` posts sit flat, `adaptive` rails bank. The
  RailClone picket-fence acceptance image is the reference.
- **PC-G3 — instancing at scale.** ~10k-segment run: count packed vs deformed prims, memory,
  cook time; deformed fraction must be only the sliced/bent pieces. Numbers recorded here.
- **PC-G4 — pipeline face.** The same fence driven entirely by a style payload on input 3 with
  the HDA parms at defaults — proving the two-face principle and the generic-loop rule (no
  branch-per-name anywhere in the kernel; audit the network for it).
- **Acceptance (deferred):** streets consumes it — the Wang-tile transition catalogue expressed
  as a polyChain style over street splines, and a street-furniture pass driven by the streets
  data stream. Defines done-for-v1; runs when streets integration starts.

**Starter kit deliverable:** one fence/railing kit (the PC-G1/G2 kit), authored with
`pf_polychain_kit`, shipped with the HDA — the standalone-usability floor. Domain corpora stay
with domain tools.

## 7. Phase 2 — the 2D array (BUILDABLE SPEC, written 2026-08-22)

**Status:** design complete, nothing built. This section replaces the directional stub that stood
here until 2026-08-22. Read [§11.9](#119-handover-to-phase-2--what-the-ported-architecture-is-and-what-must-not-be-undone)
FIRST — its eight rules are binding on every line below — then
[`railclone.md`](railclone.md) §1 and §6, then this.

**Reference material actually read for this spec** (dev-loop rule 1, not recalled):
the A2S generator reference and the RC Slice modifier reference, both fetched in full on
2026-08-22 (`docs.itoosoft.com/railclone/style-editor/2d-arrays-generator-a2s`,
`docs.itoosoft.com/railclone/rc-slice-modifier`). Every RailClone behaviour quoted below is from
those two pages. The one number that matters most — **RC Slice generates exactly 20 pieces** —
is confirmed there verbatim ("20 nodes will be created, one for each possible slice"), and so is
its piece list, which §7.2 reproduces and then explains.

**The one-sentence architecture:** *a row is a phase-1 curve, the row list is a phase-1 plan run
on the Y axis, and all N rows go through **one** `place.build` call as one curve stream.*
Everything else in this section is consequences of that sentence.

---

### 7.1 The row stack — how the 2D generator drives N rows through the 1D kernel

RailClone's own model is "A2S is essentially a stack of L1S" ([`railclone.md`](railclone.md)
§6.1). Ours is the same claim taken literally enough to be free.

**What a row is.** A row is one 1D run: a polyline in world space plus a band. Concretely, one
row = one `Curve` on input 1 of the kernel, carrying

| Prim attr on the row curve | Meaning |
|---|---|
| `pc_curve_id` | `"<arrayId>#<row>"` — the 2D address prefix (§7.3) |
| `pc_yclass` | the row's Y slot: `start` (bottom) · `default` · `corner` · `evenly` · `end` (top) · `marker:<id>` |
| `pc_row` | int, 0 at the bottom |
| `pc_row_y0` / `pc_row_y1` | the band, metres in the array's local Y |
| `pc_row_scale` | the band height ÷ the row module's nominal height (§7.4) |
| `pc_section` / `pc_corner` / `pc_style` | §3.1, untouched — a row is an ordinary spline |

All of those except `pc_row_scale` are already harvested onto `Section.attrs` by D94, so they
reach the fill rules as `attr:<name>` conditional subjects with **no adapter change**.

**Step 1 — the Y solve is a phase-1 plan.** Build a `Curve` for the Y axis: either the literal Y
spline (§7.5) or a synthetic two-point line of the requested height. Hand it to
`decompose.decompose` + `plan.plan_sections` with the **Y half of the style payload** (§7.3) and
the Y `Params` block. The result is a list of `Placement`s; **each one is a row.** Its `s0..s1`
is the storey band, its `slot` is the row's Y class, its `module` names the row's height source,
its `index` is the storey number.

This is the whole point: `fit`, `evenly`, `pack`, `justify`, `adjust_to_end`, `adaptive_pct`,
the `sequence`/`random`/`conditional` selectors, the D17 degenerate-padding guard and the D13
overflow cascade are **already correct on any 1D length**, and a stack of storeys is a 1D length.
The three row-placement modes §7 owed are therefore not three mechanisms but three `Params`:

| Rows placed by | Y `Params` |
|---|---|
| **Y evenly** (RC's Y Evenly) | `evenly_spacing` or `evenly_count`, `justify`, `adjust_to_end` |
| **Explicit heights** | `fill = "tile"` over a `sequence` rule whose modules are the storey heights in order; or `fill = "count"` + `count = N` |
| **A second spline** | the Y spline's own vertices become sections (§4.1), so a corner vertex is a `corner` row — a string course, a setback line, a cornice band |

**Adaptive on Y is real.** RailClone's own documented wart — *"At present Adaptive mode only
functions on the X axis, the Y axis will be clipped as though the mode is set to Tile"* — does
not survive here, because the Y solve is the same solve. `y_fill = "adaptive"` gives whole
storeys, subtly scaled, and never a sliced one. **That is the second RailClone wart phase 2
fixes** (the first is §7.2).

**Step 2 — emit the row curves.** For each row placement, copy the footprint spline, translate it
to the band's datum, apply the Y spline's plan offset if there is one (§7.5), canonicalise it
(D124), stamp the table above, and merge it into ONE geometry. N rows, one stream.

**Step 3 — ONE build call.** `place.build(rows_geo, kit_geo, x_style, x_params, surface_geo=…,
overrides=…)`, once. Not once per row, not once per band.

⚠️ **This is §11.9 rule 2 and it is the single easiest thing to get wrong in phase 2.** `ray`
rebuilds its surface input on every `execute` (0.34 ms at 5 022 prims, 2.25 ms at 80 352 — P5c),
so a per-row build turns a 40-storey tower into 40 surface rebuilds and a 100-building district
into 800. `place.build` already hoists the conform batch to the outermost loop over ALL curves
(D112) and takes exactly one `ray` execution per build; feeding it N rows in one call inherits
that for free, and feeding it N times throws it away. **`ray_executions_per_build` must read 1 on
the phase-2 fixtures, and PC-G7 is the gate that says so.**

**What the kernel is handed per row — the complete list.** Nothing else:

1. the row polyline (points, closed flag, `pc_corner` flags, `pc_section` ids),
2. the prim attrs in the table above,
3. the shared kit, the shared X style, the shared X `Params`, the shared surface, the shared
   override stream.

**What the kernel must be extended by — the complete list.** Three small things, and no fourth:

| # | Extension | Size |
|---|---|---|
| E1 | `Rule.yclass` (blank = matches every row), filtered in `Style.rules_for`, with the row's class reaching `plan.pick` through `ctx["yclass"]` | 3 lines (D119) |
| E2 | `pc_row_scale` read off the row prim and applied as an axis scale on the frame's up vector, in `_packed_transform` and `_deform_positions` | ~6 lines (D121) |
| E3 | The kit reader's **role closure** (§7.2) — pure data expansion of `Module.roles`, no branch | ~15 lines (D118) |

Everything else phase 2 needs is a new **stage above** the kernel (`polychain/array2d.py`, `hou`-
free like `plan.py`) plus its adapter. **There is no second kernel, no forked `plan.py`, and no
second fitting solve** (D130). If a phase-2 need cannot be met by the 1D kernel plus data, it is
a kernel cycle, not a phase-2 fork.

**Performance posture, stated before anything is built** (§11.9 rules 1–2): the row emission is
bulk `hou.Geometry` array writes — `setPointFloatAttribValues`, `createPolygons` — never a
`hou.Point`/`hou.Prim` wrapper in a loop. The existing tripwires (`stamp_calls_per_piece`,
`prims_wrappers_built*`, `points_wrappers_built*`) are extended with `rows_wrappers_built` and
`ray_executions_per_build`, and the phase-2 bench fixture is **100 buildings × 8 storeys = 800
short rows**, not one tall tower (§11.9 rule 2's "many-short-rows, not one big one").

---

### 7.2 The cell-role inventory — 25 first-class roles, and where they come from

RailClone's biggest documented wart for buildings is that **intersection cells have no slots**
(corner-top, evenly-bottom, corner × evenly …) and need macro/expression workarounds
([`railclone.md`](railclone.md) §6.2). Its RC Slice modifier's 20 auto-generated pieces are the
true inventory it never gave the generator. Here is that list, from the RC Slice reference, read
2026-08-22:

> **12 named slice types:** Start · End · Default · X Evenly · Y Evenly · X Corner · Top ·
> Bottom · Start Top · End Top · Start Bottom · End Bottom
> **8 intersections:** X Corner Top · X Corner Bottom · X Evenly Top · X Evenly Bottom ·
> Y Evenly Start · Y Evenly End · X/Y Evenly · Y Evenly/Corner

**Those 20 are not 20 things. They are a 5 × 4 product table, and the missing fifth column is
RC's own omission.** Every one of them is an ordered pair of a slot on X and a slot on Y, drawn
from **the phase-1 `SLOTS` vocabulary, unchanged**:

> `SLOTS = ("default", "start", "end", "corner", "evenly")`

So:

**D116 — `pc_role` for 2D is the ordered pair `<x_slot>_<y_slot>`, both drawn from `SLOTS`.**
5 × 5 = **25 first-class roles**. RailClone's 20 are exactly our subset with `y_slot != "corner"`
— it has a Y Corner *generator slot* but never slices a Y-corner *piece*, so its inventory is
short by one column. Ours is not, and the extra column costs nothing: it is five strings in a
vocabulary, not five branches in code.

The full table. Column = X slot, row = Y slot. `default_default` is written `default` so that
**a phase-1 kit is a valid phase-2 kit for the middle rows with no edit at all**:

| | X `start` | X `default` | X `corner` | X `evenly` | X `end` |
|---|---|---|---|---|---|
| **Y `end`** (top) | `start_end` | `default_end` | `corner_end` | `evenly_end` | `end_end` |
| **Y `evenly`** | `start_evenly` | `default_evenly` | `corner_evenly` | `evenly_evenly` | `end_evenly` |
| **Y `corner`** | `start_corner` | `default_corner` | `corner_corner` | `evenly_corner` | `end_corner` |
| **Y `default`** | `start` | `default` | `corner` | `evenly` | `end` |
| **Y `start`** (bottom) | `start_start` | `default_start` | `corner_start` | `evenly_start` | `end_start` |

The bottom row of that table is **literally the phase-1 slot list**. That is the compatibility
claim, and it is checkable: `set(SLOTS) == {r for r in ROLES_2D if "_" not in r}`.

**Accepted aliases** (kit reader, same shape as D4's `moduleRole`): artists write the words their
industry uses and the reader normalises. `bottom` → `default_start`, `top` → `default_end`,
`left` → `start`, `right` → `end`, `lt`/`left_top` → `start_end`, `rt` → `end_end`,
`lb` → `start_start`, `rb` → `end_start`, `x_corner` → `corner`, `y_evenly` → `default_evenly`,
`xy_evenly` → `evenly_evenly`. An alias that resolves to a role another module already claims
warns and loses — first module in payload order wins (D63's rule, reused).

**Marker cells are legal by grammar, not by enumeration.** `marker:<id>` is a slot on either
axis, so `marker:7_default` (an authored bay) and `default_marker:2` (an authored storey) parse
and work. They are not in the 25 because they are unbounded; the grammar is
`<x_slot>_<y_slot>` where each is `SLOTS ∪ {marker:<int>}`.

#### 7.2.1 Resolution order — which role wins when two claims overlap

**D117 — precedence is resolved PER AXIS, independently, and only then producted.** There is no
2D tie-break table, because a cell cannot have two roles: it has one X class and one Y class.

*X precedence, unchanged from phase 1* (`plan.plan_section`'s own order, restated so it cannot
drift): a run cap (`start`/`end`, and D18 means a cap is earned only at a real run end — an open
footprint, or a `pc_section` limit, never at a corner) **>** `corner` **>** `marker:<id>` **>**
`evenly` **>** `default`. Authored beats generated; structural beats authored.

*Y precedence, the same order on the Y solve:* `start`/`end` (the array's bottom and top rows —
these ARE the Y run's caps, which is why they are named `start`/`end` and aliased
`bottom`/`top`) **>** `corner` (a Y-spline corner vertex — setback line, string course) **>**
`marker:<id>` **>** `evenly` **>** `default`.

*The one genuine 2D conflict, and its answer.* A corner column crossing a top row: does the
corner column cut through the cornice, or does the cornice run continuous past the corner? Both
are correct in different kits, RailClone exposes it as **Extend To Side**, and so do we:

> **`pc_extend`** (int, kit module attr; generator default `pc_extend_x` / `pc_extend_y`).
> `1` = this class extends to the side, cutting the other axis' band. `0` = it stops at it.

Resolution: the cell's role is always the product `<x>_<y>`. `pc_extend` decides only **which
axis the cell degrades toward when the kit has no product cell** — X-extending means the fallback
keeps X (`corner_end` → `corner`), Y-extending means it keeps Y (`corner_end` → `default_end`).
When the product cell exists in the kit, `pc_extend` changes nothing about role choice; it is a
tie-break for absence, not for presence. This is the whole of the "two claims overlap" rule.

#### 7.2.2 The fallback chain — a lattice walk, warn and stand in, never fail

**D118 — role fallback is a walk on the 5 × 5 lattice, and it is performed as ROLE CLOSURE at kit
read, not as a branch in the kernel.** The kit reader adds the fallback roles to each module's
own `roles` tuple, so plain `Kit.by_role` finds them and `plan.candidates` is untouched.

The default chain for a missing cell `<x>_<y>`, in order:

1. `<x>_<y>` — the exact cell.
2. `<x>` — **drop the Y class, keep X.**
3. `<x>_default`… is the same string as 2; then `default_<y>` — drop X, keep Y.
4. `default` — the base cell.
5. §3.4's blank stand-in box at nominal size + `pc_warn_kit_gap`. Never a failure.

**Why Y is generalised first.** A cell's X class is what makes it *close*: a `corner` piece is
authored to mate at the bisector plane, and dropping its corner-ness leaves a hole or an
interpenetration at the corner — a PC-G5 failure. A cell's Y class is what makes it *read*: a
`top` piece is a cornice profile, and dropping its top-ness leaves a facade that is merely plain.
**Closure beats cosmetics**, so the walk sheds Y before it sheds X. Under `pc_extend = 0` on the
X class the walk is reversed (steps 2 and 3 swap) — that is exactly what "this column stops at
the cornice" means.

Every degrade is named, once per (role, kit), on every element that took it:
**`pc_warn_role_fallback`** (new; joins `WARN_VOCAB`), carrying the role asked for and the role
supplied. A silent stand-in is a defect: PC-G5 condition 5 asserts zero silent stand-ins.

---

### 7.3 Data contracts — extending §3, breaking nothing

#### 7.3.1 Kit (§3.2 + )

| Attr | Type | New? | Meaning |
|---|---|---|---|
| `pc_role` | string | extended | now the 25-role vocabulary + aliases (§7.2); space-separated multi-role unchanged |
| `pc_size` | vector | promoted | **`.y` is now load-bearing** — the module's nominal storey height, the denominator of `pc_row_scale`. It already exists and was already read; phase 1 simply never used it. |
| `pc_extend` | int | **new** | §7.2.1's Extend To Side. `-1` = the generator decides (D6's three-state pattern, reused) |
| `pc_clip` | int | **new** | per-module clip policy: `0` remove · `1` preserve · `2` slice · `-1` generator decides (§7.6) |
| `pc_pad` | vector2 | extended | read as `(left, right)` on X rows and as `(bottom, top)` on the Y solve — the same two numbers, because the Y solve is the same solve |

Everything else in §3.2 is unchanged. `pc_deform`, `pc_zmode`, `pc_variant`, `pc_weight`,
`pc_tilt` mean exactly what they meant.

#### 7.3.2 Style payload (§3.3 + )

**D120 — one payload, two axes.** The payload gains ONE point attribute and ONE detail key:

| Attr | Meaning |
|---|---|
| `pc_axis` | `x` (default, so every phase-1 payload is a valid phase-2 X payload) or `y`. The 2D stage splits the rule list on it into an X `Style` and a Y `Style`. **`Style` itself does not change.** |
| `pc_yclass` | **(D119)** blank = this rule matches every row; otherwise the Y class it is scoped to. Filters in `Style.rules_for`; keeps `pc_select` free for `random`/`sequence` on a row-class-specific rule, which a `conditional`-based encoding would have consumed |
| `pc_style_meta["y_params"]` | a second `Params` dict, read by the *same* `params_from_dict`. `y_fill`, `y_count`, `y_evenly_spacing`, `y_justify`, `y_adaptive_pct`… are not new parms; they are the same `Params` fields on the other axis |
| `pc_style_meta["y_mode"]` | `aligned` · `free` (§7.4) |
| `pc_style_meta["clip"]` | `{mode, projection, expand, auto_align, hierarchy, cap_holes}` (§7.6) |

Rule ordering carries the second half of the fallback: `rules_for(slot, yclass)` returns
yclass-scoped rules in payload order, then blank-yclass rules. So **rule-level fallback
(specific row class → generic) and kit-level fallback (role lattice → stand-in) are two
independent, ordered chains**, and a payload can express "random brick on every row, but the
ground floor is always this shopfront" with two rules and no conditional.

PC-G4's generic-loop law is preserved by construction: `pc_axis`, `pc_yclass` and the role
vocabulary are *schema*, exactly as `corner`/`start`/`end` already are — there is still no branch
per style name anywhere, and the phase-2 audit re-runs the same grep.

#### 7.3.3 Output stamp (§3.4 + ) — the structural address, now 4-dimensional

**D123 — `pc_elem_id` does not change shape, and `elem_id()` is not touched. The 2D address is
composed into the fields that already exist.** citygen_buildings §12.7 requires
volume/face/bay/storey, not cook order. Phase 1's address is
`<curve>|<section>|<slot>|<index>|<styleId>`. Map it:

| §12.7 coordinate | Phase-1 field | Supplied by |
|---|---|---|
| **volume** | the `<arrayId>` half of `pc_curve_id` | the 2D stage (footprint id / sub-spline id) |
| **storey** | the `#<row>` half of `pc_curve_id` | the Y solve's placement index |
| **face** | `<section>` | §4.1's decompose — on a closed footprint a section IS a facade leg |
| **bay** | `<index>` | §4.2's fill |
| cell role | `<slot>` | §7.2 |

An element on the 3rd bay of face 2, storey 4 of volume `B17` under style `civic` therefore reads
`B17#4|2|default|3|civic`. Four coordinates, zero kernel change, and D1's collision-free-by-
construction property holds for the same reason it held before.

**D124 — a closed footprint is CANONICALISED at row emission, so ids survive re-authoring.**
Phase 1 numbers sections from point 0 in the authored direction. On a closed footprint that means
rotating the start vertex, or reversing the spline, renumbers every face and moves every id —
which is precisely what §12.7 forbids and what phase 1 never had to face (its closed cases are
authored once). So the 2D stage, which emits the row curves itself, emits them canonical:
rotate the point list so index 0 is the vertex with the lexicographically smallest
`(round(x,3), round(y,3), round(z,3))`, and reverse if the signed plan area is negative (i.e.
always run counter-clockwise about +Y). **Done at emission, outside the kernel, so not one
phase-1 baseline value moves.** PC-G5 condition 6 is the check.

New stamped attributes, joining §3.4's list: `pc_row` (int), `pc_yclass`, `pc_cell` (the resolved
25-role name — `pc_slot` keeps the X slot, so both halves are readable),
`pc_array` (the sub-spline / array id), `pc_clipped` (0/1).

New warnings, joining `WARN_VOCAB`: `pc_warn_role_fallback` (§7.2.2), `pc_warn_clip_unsliceable`
(§7.6), `pc_warn_row_overflow` (a band shorter than its mandatory bottom+top — the Y twin of
D13's cascade, and it reuses it), `pc_warn_y_align_lost` (§7.4).

---

### 7.4 The Y fit — band heights, and Aligned vs Free

**D121 — the band height is an axis scale carried on the row curve, not a new solve.** Row *r*
gets `pc_row_scale = (row_y1 − row_y0) / module.size.y`, applied at the frame's **up** axis in
`_packed_transform` and `_deform_positions`. §4.6's instancing rule already reads *"transform ×
uniform-or-axis scale of the kit module stays a packed prim"* — an axis scale is on the allowed
side of that sentence by its own wording, so **a scaled storey stays packed** and PC-G3's
property survives into 2D unchanged. This is the second half of "adaptive on Y is real": the Y
solve decides how many whole storeys fit, and `pc_row_scale` is how they fill the height exactly.

**D122 — Aligned vs Free, RailClone's Y Mode, restated as a bay-count rule.** RC: *"In Aligned
mode, all segments along the Y path are scaled to maintain the same alignment as on X.
Alternatively, free mode creates independent rows on Y, so each segment keeps its original size."*

- **Free** — every row solves X on its own length. Nothing to do; it is what one build call over
  N curves already does.
- **Aligned** — every row takes the **datum row's bay count per section**. When the rows are
  congruent (the common case: one footprint at N elevations) Aligned is *free* — a deterministic
  solver on identical input already returns identical stations, and PC-G5 condition 3 measures
  that rather than assuming it. It only bites when rows genuinely differ in length: a setback
  storey, a tapered tower, a Y-spline plan offset. There the 2D stage runs `plan.plan_sections`
  on the datum row (pure math, no geometry, microseconds), reads the bay count per section, and
  emits every other row with `fill = "count"` and that count. Where a row physically cannot hold
  the datum's count (a setback so deep the section is shorter than the count's minimum), the row
  degrades to its own solve and says **`pc_warn_y_align_lost`** — warn, never block.

The datum row is the **bottom** row (`pc_row = 0`), because a facade's ground floor is the row an
artist actually looks at, and because it is the one row that always exists.

---

### 7.5 The whole-building interface, and the Y spline

**Input 1 is one closed footprint spline + a height.** That is the entire required interface
(§7 item 2, and [`railclone.md`](railclone.md) §6.1's production finding: *"the entire building is
a single A2S wrapped around the footprint; facades are never wired per-face"*). Vertex type is
data, exactly as §3.1 already says: `pc_corner = 1` (or an auto turn past `corner_angle_deg`) is a
hard vertex ⇒ a corner column; a suppressed or smooth vertex is a curved facade with no corner
geometry, and the bend/miter machinery of §4.3 handles both without a new mode.

**D128 — the Y spline is a PROFILE, not a second world-space path.** RailClone reads the Y
spline's *local* X/Y and ignores Z. Ours: the along-axis coordinate is **height**, the off-axis
coordinate is an **outward plan offset** applied to the footprint at that height. That gives
batter, setback and taper — and RC's double-curved case — from one 2-D profile curve, without
ever asking the artist to author a second closed loop in 3D. The offset is applied per footprint
vertex along the angle bisector, scaled by `1/sin(θ/2)`; where the offset exceeds the local
inradius the vertex collapses, so it is **clamped and warned** rather than allowed to self-
intersect. `polyexpand2d` is the escape hatch if a consumer ever needs true offsetting with
topology change — noted, not adopted, and if it is adopted it inherits phase 1's measured lesson
that it breaks planarity by ~2e-5 m.

**D127 — the port count is frozen at 5 before any consumer wires it** (the streets lesson, and
open-question 2's precedent):

| Input | Contents |
|---|---|
| 1 | footprint spline(s) + marker point cloud (`pc_marker = 1`) — §3.1 unchanged |
| 2 | kit |
| 3 | style payload (optional; overrides the parms entirely — §2.1, D77) |
| 4 | surface (optional, conform) |
| 5 | **auxiliary splines**, discriminated by a prim attr `pc_purpose` ∈ `clip` · `exclude` · `yspline` |

Input 5 is one port and not three because a Y profile and a clip boundary are both splines, and
the discriminator is data — the same call open-question 2 made for markers.

---

### 7.6 Clipped-area arrays

**A closed spline that both DEFINES and TRIMS the fill** (§7 item 3). RC's own parameter set,
read 2026-08-22, is the behavioural reference; ours is that set with the ambiguities decided.

**Defining.** With `Extend X/Y Size to Area` on, the array's X and Y extents come from the closed
spline instead of from a footprint and a height: the sub-spline's own plane gives the local frame
(**Auto Align**: `x_xy` keeps +X parallel to the world XY plane, `to_spline` aligns +X with the
sub-spline's first segment; +Z is always the plane normal), its bounding box in that frame gives
the extents, `expand` grows them to kill perimeter gaps, and `z_rotation` spins the array inside
the boundary. This is what makes flat roofs, floor plates, cladding fields and per-aperture
window arrays all one primitive.

**D125 — per-sub-spline independence and include/exclude nesting.**

- **Each closed sub-spline is its own array**, with its own local frame, its own row stack, its
  own `arrayId`, and therefore its own `pc_elem_id` namespace. Editing one sub-spline must move
  zero elements in another; PC-G6 measures that as an elem-id set diff.
- **Nesting is even–odd by default.** A sub-spline whose centroid lies inside another is a hole
  in that array, not an array of its own; depth 0/2/4 = solid, 1/3/5 = hole. This is RC's
  `Hierarchy Checking = Complete` and it is our default because it is deterministic and needs no
  authoring.
- `pc_clip_mode` on the sub-spline prim (`include` / `exclude`) **overrides** the even–odd result
  for that spline — RC's `None` mode, per spline instead of globally.
- `pc_clip_group` (int) groups sub-splines into one array — RC's `By Material ID`, renamed to
  something that is not a material.

**D126 — the cull policy is D11's pattern, on a new axis.** RC's "For No Slice" three:

| `pc_clip` | Behaviour |
|---|---|
| `0` remove | a piece intersecting the boundary is dropped. Nothing crosses the line. |
| `1` preserve | it is kept whole and may overhang. |
| `2` slice | it is cut to the boundary exactly, and the hole is capped. |

`slice` requires `pc_deform = 2` (sliceable), exactly as §4.2's tile remainder does. A `slice`
policy on a non-sliceable module **degrades to `remove`** — not to `preserve`, because an
overhanging window is a visible defect and a missing one is a visible gap, and a gap is the one
the artist will notice and fix — and says `pc_warn_clip_unsliceable`. Caps are `dress_caps`
(§4.6), already built, with the box UV from the module's own mapping.

**Cost discipline.** The clip test is a 2-D point-in-polygon in the array's local frame, run on
the piece's four footprint corners — pure math on the *plan*, before any geometry exists, so
`remove` never builds anything and `preserve` never runs a boolean. Only the pieces the plan says
**straddle** reach `clip_plane`, and that is the same `clip` verb §4.3 already uses (§11.9's
"the only compiled SOPs it reaches are three verbs"). No fourth verb, and no boolean SOP.

---

### 7.7 `pf_polychain_slice` — the kit on-ramp

Model one good facade chunk; get the 25 cells. Input: one mesh + the default cell size (x, y) +
which classes to generate. Output: a §3.2 kit — one packed prim per cell, one manifest point per
cell with `pc_role` set to the cell name.

**D131 — it is the `clip` verb `place.clip_plane` already uses, run on a plane grid, plus RC's
jigsaw rule.** RC's `Adjust X/Y Size To Default Segment` (*"geometry is clipped to match the size
of the default segment… all pieces are the correct length and fit together correctly like a
jigsaw"*) is not decoration — it is what makes the pieces mate, so it is **on by default and its
result is asserted**: every generated cell's bbox is the default cell's size on the axes it is not
a cap for, to 1e-6 m. The tool ships the pieces AND the assertion; a kit that fails it cannot
close a facade and should say so at authoring time rather than at PC-G5 time.

---

### 7.8 Gates

Each gate is judged **on an image** (show-don't-tell) and then independently audited (dev-loop
rule 0). The headless rasteriser `tests/polychain/gate_images.py` is the standing substitute while
the live bridge is wedged; extend it, do not rebuild it (it was rebuilt from a scratchpad three
times before anyone committed it).

#### PC-G5 — facade closure. **The acceptance test phase 2 points at.**

The 2D analogue of PC-G1, and the consumer-side twin of citygen_buildings §12.10 **G2**
(*"L-shaped footprint, walls + skeletonRoof cap, through B4–B6. Pass: no holes or misalignments at
any convex/reflex corner or eave/gable seam"*). Aligned deliberately: G2's L-footprint is PC-G5's
L-footprint, so when buildings picks phase 2 up, its corner gate is already passing on our half of
the seam and only the cap seam — B5's, never ours (§7.9) — is left to prove.

**Fixture.** A closed L footprint (6 vertices: 5 convex, 1 reflex), 4 storeys, `y_fill = adaptive`,
`fill = adaptive`, both corner modes (miter and bend), a starter facade kit carrying at minimum
`default`, `corner`, `default_start` (ground), `default_end` (cornice), `corner_start`,
`corner_end`.

**Pass conditions, each a number:**

| # | Condition | Measure |
|---|---|---|
| 1 | **Corner closure, per storey.** | At every (footprint vertex × storey) joint — 6 × 4 = 24 — the gap between the two adjacent cells' mating faces ≤ `bend_tol` (0.01 m). **0 joints over.** Same measurement PC-G1 makes, run 24 times instead of 6. |
| 2 | **Row closure.** | For every vertically adjacent row pair and every bay: \|row_i.y1 − row_{i+1}.y0\| ≤ 1e-6 m, and no cell's geometry crosses a band boundary by more than `bend_tol` unless its X class carries `pc_extend = 1`. |
| 3 | **Bay alignment under `y_mode = aligned`.** | Every row's bay-boundary set is identical to the datum row's to 1e-6 m. Under `free` this check is inverted: at least one row differs, or the fixture is not exercising the mode. |
| 4 | **No sliced windows.** | With adaptive on both axes, `slice_t is None` on **100 %** of non-clip placements. **0 slices.** |
| 5 | **No silent stand-ins.** | Every cell the L-footprint demands is filled by a real module, or reports `pc_warn_role_fallback` naming both roles. Count of `pc_warn_kit_gap` elements with no accompanying fallback warning = **0**. |
| 6 | **Identity is structural.** | Rebuild with the footprint (a) reversed and (b) re-authored starting at a different vertex. The `pc_elem_id` **set** is identical in all three builds, and every element's `(pc_cell, rounded position)` pair is identical. This is D124's whole reason for existing and it is the strongest identity assertion in the tool. |
| 7 | **Instancing survives 2D.** | With a rigid kit, packed fraction = 1.0 except pieces genuinely cut by a miter or a clip boundary; `pc_row_scale ≠ 1` must **not** unpack anything (D121). |

**Image to judge:** a three-quarter view of the whole L at 4 storeys; a close-up of the **reflex**
corner from ground to cornice showing the corner column mating into the cornice; a wireframe with
elements coloured by `pc_cell` so the 25-role table is visible as a pattern. The failure this
image exists to catch is the one no number catches: a corner that closes numerically while the
cornice returns the wrong way round it.

#### PC-G6 — the clipped area

**Fixture.** A flat plate defined by a closed spline with a nested exclude sub-spline (a hole) and
a second, disjoint sub-spline beside it; `extend_to_area` on; a tile kit with one sliceable and
one rigid module.

**Pass:** every emitted piece's plan footprint is inside the include region and outside every
exclude region to within `bend_tol`; sliced pieces are capped (open boundary edge count = 0 except
on the array's own outer boundary); every straddling non-sliceable piece is removed and says
`pc_warn_clip_unsliceable`; **sub-spline independence** — editing sub-spline B moves 0 of
sub-spline A's `pc_elem_id`s; **nesting** — the hole contains 0 elements, and a third sub-spline
nested inside the hole contains elements again (even–odd depth 2).
**Image:** top view of the plate with its hole, elements coloured by clip policy.

#### PC-G7 — the row stack at scale, and the one-call rule

The 2D twin of PC-G3, and the gate that enforces §11.9 rules 1–2 rather than trusting them.

**Fixtures, both:** (a) one tower, 40 storeys × 60 bays = 2 400 cells; (b) **the many-short-rows
fixture** — 100 buildings × 8 storeys = 800 short rows, over a terrain with conform on.

**Pass:**

- `ray_executions_per_build == 1` on **both** fixtures. (b) is the one that can fail.
- `stamp_calls_per_piece == 0`; `prims_wrappers_built*`, `points_wrappers_built*` and the new
  `rows_wrappers_built` at their floors — a wrapper count is the *first* thing measured when a
  phase-2 row is slow, before anyone reaches for a new language (§11.9 rule 1).
- Fixture (b) through one build call is **not slower** than 100 separate builds. If it is, the
  batch is in the wrong loop and the fix is the loop, not the language.
- Packed fraction and `geometryid` count recorded, as PC-G3 records them; peak RSS recorded
  **against pre-phase-2**, because §11.8's own headline is that the memory column can move the
  other way while the time column improves, and that must not be discovered later.
- `geometry_digest` and `determinism` green — batching is reordering, and reordering is where
  determinism dies (§11.9 rule 5).

**Image:** the district at (b), plus one building pulled out of it, to confirm 800 rows are 100
buildings and not one smeared one.

---

### 7.9 What phase 2 does NOT do

Kept honest, because every one of these has a real owner and a shared owner is no owner
([`citygen.md`](citygen.md)'s seam, restated).

1. **No massing.** polyChain dresses a footprint; it never decides how many volumes a building
   has, where the party walls are, or what shape the roof is. citygen **B2** (mass) and **B5**
   (cap / straight skeleton) own that, and B5 is explicitly the gap RailClone never filled.
2. **No junctions, forks or intersections.** Permanent, phase 1's non-goal unchanged. A facade
   array stops cleanly at the footprint; where two buildings meet, the consumer authors the seam.
   citygen **B6** owns every seam.
3. **No boolean openings.** A window is modelled *into* its bay module, or an aperture is pre-cut
   and the window arrives as a per-aperture clipped array (§7.6) — RailClone's own answer, and
   the one that keeps instancing. Cutting a hole in a wall is B4/B6's business.
4. **No roof solving.** A flat roof is a clipped area (§7.6); a pitched roof's *planes* are
   clipped areas once something else has produced them. Producing them is B5's straight skeleton.
5. **No interiors, no LOD generation, no UV atlasing** beyond the cap box-map §4.6 already does.
6. **No expression engine.** `pc_vexpr` stays parsed-ignored-warned (D3). Data first, expression
   second, code never.
7. **No per-face wiring.** One footprint drives the whole building. A style that needs face 3 to
   differ says so with `attr:` data on face 3, not with a fourth generator.
8. **No new file formats.** Kits and styles remain Houdini geometry carrying attributes.
9. **No RC "Slope".** RailClone rotates the whole array about the X spline for a stepped look; our
   z-modes (§4.4) already cover the cases that matters for, and a second rotation mechanism would
   need its own budget in D87's curvature accounting. Recorded as declined, not forgotten.
10. **D130 — and no second kernel.** No forked `plan.py`, no parallel fitting solve, no
    "2D version" of anything phase 1 already does. If phase 2 wants something the 1D kernel
    cannot do, that is a kernel cycle with its own tests, taken in `plan.py` where the 286 unit
    tests already live — never a copy.

---

### 7.10 Build order for the implementation cycles

Each cycle: implement, run the committed suites, spawn an independent audit, fold every new
measurement into the suite, commit, append to the build log. Same loop phase 1 ran twelve times.

| Cycle | What | Done when |
|---|---|---|
| **P2-1** | `polychain/array2d.py` (`hou`-free): the Y solve via `plan.plan_sections`, the row list, canonicalisation (D124). Unit tests only, no geometry. | A 4-storey stack over an L footprint is a list of 4 `Placement`s with correct bands, in milliseconds, with no `hou` imported |
| **P2-2** | The adapter: row emission as bulk array writes, ONE `place.build` call, the new tripwires (`rows_wrappers_built`, `ray_executions_per_build`). | A rectangle × 4 storeys builds; `ray_executions_per_build == 1`; the many-short-rows fixture exists **from this cycle on**, not later |
| **P2-3** | The 25-role lattice: `ROLES_2D`, the alias table, kit role closure (E3/D118), `pc_warn_role_fallback`. Kit reader + unit tests. | `set(SLOTS) == {r for r in ROLES_2D if "_" not in r}`; every fallback chain asserted; a kit with only `default` builds every cell and warns 24 times |
| **P2-4** | Rule scoping: `Rule.yclass`, `Style.rules_for` filter, `pc_axis` split, `y_params` (E1/D119/D120). | A payload with a ground-floor rule and a cornice rule builds a three-band facade; phase-1 payloads byte-identical |
| **P2-5** | The Y fit: `pc_row_scale` (E2/D121), aligned vs free (D122), `pc_extend` (D117). | Storeys fill the height exactly, stay **packed**, and bays line up under `aligned` |
| **P2-6** | **PC-G5** — the L-footprint facade closure gate, all 7 conditions + the images. | All 7 green, image-judged, independently audited |
| **P2-7** | Clipped areas (§7.6) + **PC-G6**. | Both green |
| **P2-8** | The Y spline profile (D128) and `pf_polychain_slice` (§7.7). | A tapered tower; a kit sliced from one chunk passes the jigsaw assertion |
| **P2-9** | The parm face (§5's rules verbatim, two disclosure levels), the starter facade kit, **PC-G7**. | PC-G7 green on both fixtures; every parm has range, units, help; defaults build a good facade out of the box |

**Order rationale.** The row stack comes before roles because a stack of `default` cells is
already a facade and it makes every later cycle visible. The tripwires come in P2-2, not P2-9,
because §11.9 rule 2's defect is invisible on the fixture you would naturally write first.
PC-G5 sits in the middle, not at the end, because it is the acceptance test and everything after
it is either a second primitive (clipping) or an on-ramp (slice, parms) — if PC-G5 cannot pass,
the four cycles after it are wasted.

**Effort:** phase 1 was twelve cycles for the 1D kernel. Phase 2 is nine and most of them are
small, *because* the kernel is done — which is the entire return on the "reuse; do not fork"
constraint. The two that will run long are **P2-6** (closure is where phase 1's time went too)
and **P2-7** (clipping is a second primitive, not a parameter).

## 8. Build order and effort

PC-G0 → kernel stages §4.1–4.2 (plan visible early) → §4.4 place/deform → §4.3 corners (budget
the most time here) → §4.5 conform → §4.6 finalize/instancing → §5 parm face → starter kit →
gates PC-G1–G4. Phase-1 estimate for a senior TD: **weeks, not months, dominated by §4.3**
(estimate, not measured). **Phase 2's own build order is §7.10** — nine cycles, spec written
2026-08-22, nothing built; it runs alongside buildings.

## 9. Open questions (decide during build, record here)

1. ~~Chain SOP fork-vs-reimplement~~ — **closed 2026-08-21: fork** (factory HDA, see §2.3/PC-G0).
2. ~~Marker carrier~~ — **closed 2026-08-21 (cycle 1): merged point cloud on input 1**, per
   §3.1's own recommendation. The port count is now frozen at 4 (spline+markers / kit / style /
   surface) before the streets segmenter is cut, which is what the streets lesson asks for.
   The kernel reads markers as plain `Marker(curve_id, u|dist, marker_id, data)` records, so a
   5th input would only change the adapter, not the kernel.
3. ~~Kit manifest attr names~~ — **closed 2026-08-21 (cycle 1): `pc_role` is authoritative, and
   `moduleRole` is accepted as an alias when `pc_role` is absent** (`kit_from_records`). One
   line, converges with buildings §12.9 without blocking on a meeting; when B-stages start the
   alias is the migration path, not a fork.
4. ~~`pc_cond` schema~~ — **closed 2026-08-21 (cycle 1): a fixed `{subject, op, value}` dict**
   with §3.3's subject list and a dict of seven ops (`lt le gt ge eq ne in`). `pc_vexpr` is
   accepted, **parsed and ignored** in phase 1 and says so per element
   (`pc_warn_vexpr_ignored`) — no expression engine before a real conditional style exists
   (ponytail). Unknown subject, unknown op and type mismatch all evaluate False; nothing raises.
5. ~~HDA namespacing~~ — **closed 2026-08-21 (cycle 1): flat `pf_polychain`** (`Sop/pf_polychain`).
   Measured off the shipped assets rather than chosen: the citygen family, the most recently
   shipped HDAs, is `Sop/pf_citygen_segmenter`; the `Sop/pf_asset_tag::1.0` form is the legacy
   one. Kernel-side this only fixes the names cycle 2 will build under.

---

## 10. Build log

⚠️ **§10 is the PHASE 1 record. Phase 2's cycles are logged in §12, after the port plan.**

⚠️ **The OpenCL decision (D158–D160) is recorded in [§14.10](#1410-the-audit-of-14--what-survived-what-had-to-be-corrected-and-the-verdict), with the measurement in §14 and the cycle entry in §12 (`Cycle P2-OCL`).** It spans both phases, so it lives with the numbers rather than in either build log: **OpenCL is declined everywhere in polyChain, audited and measured on both workload shapes.**

Append one subsection per cycle: what was built, what the reviewers found, what the numbers were,
and every decision taken on an open question. This is the streets convention
([`citygen_streets.md`](citygen_streets.md)) — the doc is the build's memory, so a context loss
costs nothing.

### Cycle 1 — §4.1 decompose + §4.2 plan (2026-08-21)

**Built:** the `hou`-free kernel, mirroring citygen's `plan.py` precedent (decide before geometry
exists, so it is testable in milliseconds and auditable without a licence).

| File | What |
|---|---|
| `polyfactory/scripts/python/polyfactory/polychain/__init__.py` | Contracts: vocabularies, `Params`, `Curve`, `Marker`, `Module`/`Kit`, `Rule`/`Style`, ids and seeding |
| `polyfactory/scripts/python/polyfactory/polychain/decompose.py` | §4.1 — corners, markers, `pc_section` limits, the ordered section list |
| `polyfactory/scripts/python/polyfactory/polychain/plan.py` | §4.2 — `fit`/`evenly`/`pack`, selection, `plan_section` |
| `tests/unit/test_polychain.py` | 45 tests — contracts, decompose, determinism |
| `tests/unit/test_polychain_plan.py` | 72 tests — the fitting solve |

**Numbers.** 117 unit tests, **0.10 s** total, no Houdini imported (asserted). Exact fill holds to
**1e-9 m** in all four modes, with padding, with a mixed-size sequence and with start/end reserved.
Plan scale: a 20 km section plans **10 000 pieces** with 10 000 distinct `pc_elem_id`s.

**Mutation-tested, 13 mutations, 13 killed** — the repo's habit, applied to a file with no
calibration fixture to lean on: padding moved onto the padded piece (7 red), the random pool left
in payload order (1), the tile fallback made silent (1), `adaptivePct` ignored (1), the fill left
1 mm short (56), overflow dropping `start` instead of `end` (2), the element index restarted per
run (2), the corner threshold read as the included angle (9), duplicate points not collapsed (1),
`seed_for` switched to builtin `hash()` (1), the closing vertex excluded from corner candidates
(3), markers landing in every containing section (1), and the section start frame reading the
*incoming* tangent (1).

⚠️ **No calibration fixture exists yet, and that is deliberate.** `test_plan.py`'s
"calibrate, do not invent" discipline needs a builder to measure against, and §4.4 does not
exist. Every number in the polyChain tests is therefore an INVARIANT (exact fill, never-slice,
padding direction, determinism, warn-never-block), never a measurement. When §4.4 places real
geometry, `tests/polychain/dump_placements.py` joins these files the way `dump_trims.py` joined
`test_plan.py` — that is the next debt, and it is named here so it is not forgotten.

**Decisions taken** (open questions §9 items 2–5 are closed above; these are the ambiguities the
spec did not list, each pinned by a test):

| # | Ambiguity | Decision |
|---|---|---|
| D1 | §3.4 calls `pc_elem_id` a *hash* | It is the **string address** `curve\|section\|slot\|index\|styleId`. A 32-bit int over PC-G3's own 10k target collides ~1 % of the time, and this id is what swap/replace matches on. `pc_elem_key` (crc32) ships alongside for grouping/sorting only. **Deviation from §3.4** |
| D2 | §3.1's `cornerAngle` (30°) and §4.3's narrow angle (15°) are the same word for two angles | Two parms: `corner_angle_deg` = the **turn** (deviation from straight), `min_included_angle_deg` = the **included** angle between the legs. Both are stored on every `Corner`, so the ambiguity cannot come back |
| D5 | Does `pc_pad` scale with the fit? | **No** — padding is a scene distance in metres; only module geometry stretches. A scaled pad drifts with section length |
| D6 | §3.2 module `pc_zmode` vs style override | `Params.zmode = ""` means "the module's own value wins"; any non-empty style value overrides every module. The third state is what "the style said nothing" needs |
| D7 | §3.1 types `pc_section` as a **prim** int, but a prim int cannot express a mid-curve break | Read at **point class first** (a change between consecutive points is a break — the faithful analog of a material-ID limit); a scalar is accepted as the documented whole-curve prim key and breaks nothing |
| D8 | Duplicate/degenerate vertices | Collapsed before corner detection (a repeated point has no direction, and a naive `acos` on a zero vector is a crash). Arclen is unchanged. < 2 distinct points ⇒ no sections |
| D9 | A hairpin corner | Still a **corner** — it breaks the section and carries `pc_warn_corner_degenerate` for §4.3 to fall back on. Hiding a hairpin inside a straight run is the worse failure |
| D10 | Closed splines | Breaks are cyclic, the list starts at the first break and the last section wraps through point 0 (`s1 > length`; `Curve.sample` wraps). A corner-free loop is ONE section with `closed = True` and **no start/end slots** (RailClone semantics) |
| D11 | §4.2's "else adaptive-fallback + `pc_warn`" scope | The **whole run** falls back, not just the last piece, and every piece carries `pc_warn_tile_fallback`. One adaptive piece inside a tiled run reads as a defect in the viewport; a uniformly rescaled run reads as a choice |
| D12 | §4.2's `scale` mode: how many pieces? | **One stretched piece.** Verified against iToo's own wording rather than recalled — *"Scale stretches one segment across the entire length of each sub-spline"* ([Mastering the Linear Generator](https://www.itoosoft.com/tutorials/mastering-the-linear-generator)). n stretched pieces IS `adaptive`; giving both the same behaviour would collapse two of the four modes into one |
| D13 | §3.4 names `pc_warn_overflow` and never defines it | Drop `end` first, then `start`; if the section is shorter than the one survivor, place it **scaled onto L** and warn. Never an empty section, never an exception |
| D14 | Mixed-size runs | A run is fitted on its **unit**: for a `sequence` rule the unit is the whole pattern (post+panel+…), so mixed sizes fill exactly; for every other selector the unit is one module and a per-piece re-selection is scaled into the slot the unit laid out. That is what keeps exact fill true for a mixed-size random kit |
| D15 | Where an anchor piece sits | **Centred** on its anchor, and a marker anchor is **never nudged** to tidy the fill — PC-G1's acceptance is "gate exactly at its marker". Evenly anchors divide the FREE span (after start/end are reserved) so they cannot collide with a mandatory piece |
| D16 | §4.2's "u-range" is unqualified | Metres along the **section** (`s0`,`s1`) are the truth; `u` on a placement is 0–1 along the **parent curve** at the piece start, because that is what §3.4's `pc_u` anchor means downstream |

⚠️ **Two warning names are new** (`pc_warn_tile_fallback`, `pc_warn_vexpr_ignored`). §3.4's list
has three; §4.2 and §3.3 each imply a warning it does not name. They live in `WARN_VOCAB` with the
other three so the adapter and the checks read one list.

**Determinism, and the trap avoided.** Seeds come from `zlib.crc32` + one splitmix step over
`(styleSeed, styleId, scope, scopeKey)` — **never builtin `hash()`**, which `PYTHONHASHSEED`
randomises per process: a `hash()`-derived seed is green in one session and a different fence on
the next recook. That is asserted across three child processes with different `PYTHONHASHSEED`
values. The random pool is also **sorted before weighting**, so re-saving a style with its module
list in another order cannot reshuffle a built fence.

**Still open, carried to cycle 2:** the plan is `hou`-free and has **no consumer** — exactly the
debt `citygen/plan.py` carried for two milestones (§11.2 there). The first job of cycle 2 is the
thin Python SOP adapter (geometry → these objects → plan points back as inspectable geometry),
not more kernel.

### Cycle 1b — the review pass over cycle 1 (2026-08-21)

Two independent reviewers (spec-conformance and correctness lenses) returned **15 findings** over
`plan.py`, `decompose.py` and `__init__.py`. Every one reproduced, and every one is fixed —
none was a false positive. Unit tests: **137 green** (48 decompose/contracts + 89 plan), 0.28 s,
still no Houdini imported.

| # | Finding | Fix |
|---|---|---|
| 1 | start/end reserved on **every** section, so caps landed at every corner and 8 of them on a closed rectangle | **D18** below — `Section.start_cap`/`end_cap` |
| 2, 10 | `fit()` divided by a zero `step` when negative padding cancelled the unit (`ZeroDivisionError` out of a function documented "never raises"), and near-cancel planned 90 001 pieces | **D17** — degrade to one scaled unit, clamp to `MAX_UNITS`, warn |
| 3 | tile's sliced remainder always used `mods[0]`, so a sequence's remainder claimed span its first module cannot supply — a real hole | the remainder now **continues the unit**: whole modules, then one sliced |
| 4 | the tile fallback checked the *unit's* sliceability while the remainder **re-chose** the module — a `pc_deform = 0` module could be emitted with a slice | the module that lands on the boundary decides; a rigid pick triggers D11 |
| 5 | marker (and evenly) rules evaluated with `u = section.u0`, so a conditional gate at u = 0.9 tested u = 0 and silently never placed | the rule is read **at the anchor** (and per anchor, so a sequence walks) |
| 6, 11 | a unit whose internal padding exceeds the span returned a **negative scale**: placements with `s1 < s0`, no warning | scale clamps to 0, positions clip into the span, `pc_warn_degenerate_pad` |
| 7 | a `pc_section` change at an open curve's **last point** emitted a zero-length phantom section and shifted every section index | breaks exclude the endpoint, mirroring the corner rule; the last segment keeps the earlier key |
| 8 | `plan_section` never read `Style.params`, so the pipeline face's fill mode was silently dropped | `params=None` resolves to `style.params`; an explicit argument still wins |
| 9 | `Curve.sample` wrapped `s == length` to 0, so a closed loop's `end_frame` reported the **leaving** tangent of the first segment | a backward read at the seam stays on the closing segment |
| 12 | tile's remainder was offset by the inter-unit gap even with **zero** whole units before it — the only piece of a 5 m section was placed 2 … 7 m | the gap is added only after a unit |
| 13 | `justify = "center"` (the default) was not centred: 3.5 m in front of the run, 0.5 m behind; `"end"` put an anchor **on** the span end | centre is symmetric about the anchor pattern; only `adjust_to_end` may land on the end |
| 14 | D15's claimed invariant was false — evenly anchors interpenetrated the start/end modules | half a module comes off each **capped** end |
| 15 | a closed run was laid out as an open one: n−1 gaps, so the wrap seam was the one joint with no spacing | **D19** — n gaps, run starts half a gap in |

**New decisions** (the ambiguities the findings exposed; each pinned by a test):

| # | Decision |
|---|---|
| D17 | Padding that cancels or reverses a unit ("one more piece costs nothing") is an input no solve can answer, and negative padding is an advertised feature, so it cannot be rejected either. It **degrades**: one scaled unit when `step ≤ 0`, a count clamped to `MAX_UNITS = 100 000` above it, scale clamped to ≥ 0, positions clipped into the span — and `pc_warn_degenerate_pad` on every piece. **Sixth warning name**, alongside the two cycle 1 added |
| D18 | Start/end modules cap a **run**, not a section. RailClone puts Start/End at spline ends and *corner* segments at corners, so a section boundary earns a cap only when it is a spline end or a `pc_section` limit (the material-ID analog — where one generator stops and the next starts). Carried as `Section.start_cap`/`end_cap`, which is why a closed spline gets no caps at all and an L-shaped fence grows no post pair at its elbow |
| D19 | A closed section **wraps**, so its run has n inter-unit gaps and not n−1, and it starts half a gap in. Otherwise the seam is the one joint on a ring where the padding contract silently fails (measured: every gap 1.000 m and the seam 0.000 m on a 62.8 m circle). A wrapping run may carry `s0 < 0`; `Curve.sample` resolves it |

**Deviation recorded against D15** (cycle 1): "evenly anchors divide the FREE span so they cannot
collide with a mandatory piece" was **wrong** — the anchor is the piece's *centre*, so the span
must also shed half a module at each capped end. The corrected wording is in `plan.py`.

**Randomised audit** (4 000 random kit/style/section combinations, seeded; a 1 500-case version
is kept as a standing test, `TestRandomisedAudit` — the review's sweep becomes the next review's
assertion, per `tests/README.md`):
reversed placements **526 → 0**, rigid-module slices **22 → 0**, exceptions 0, determinism holds.
Pieces landing outside an **open** section (negative padding overlapping into the neighbouring
section, and oversized centred anchors — both documented semantics, unchanged by this pass)
fell from 295 to 154. On **closed** sections a run now deliberately crosses the seam (D19).

### Cycle 2 — §3.2 kit format + §4.4 place/deform + the scene-check harness (2026-08-21)

**Built:** the plan became geometry. Cycle 1's named debt is paid — the kernel now has a consumer.

| File | What |
|---|---|
| `polyfactory/scripts/python/polyfactory/polychain/kit.py` | §3.2 — the kit as geometry: `add_module`/`write_manifest` (build), `validate` (warn-never-block), `read` (→ `Kit` + module geometry), `starter_kit()` (post / panel / corner_post / gate) |
| `polyfactory/scripts/python/polyfactory/polychain/place.py` | §4.4 — `read_curves` (§3.1 off the stream), `Path` (cached sampler), the chord frame, three Z-modes, slope fixing, slicing + caps, the §3.4 stamps, and `analyse()` for the checks |
| `tests/polychain/cases.py` | 13 scenes. No `.hip` and no node network — §4.4 is a geometry-level adapter, so a case is three `hou.Geometry` objects and a `Style`, and the checks measure the builder and nothing else |
| `tests/polychain/checks.py` | 24 checks, every one carrying a number |
| `tests/polychain/run_scene_checks.py` | the runner + baseline diff, `tests/citygen/`'s structure verbatim |
| `tests/polychain/baseline.json` | **305 recorded values over 13 cases** |

Kernel edits were three lines: `WARN_BEND_RESOLUTION` joins `WARN_VOCAB` (the seventh name) and
`Params.fix_slope` joins the parm set. Nothing else in `__init__/decompose/plan` moved, the 137
cycle-1 unit tests are still green, and `place.py`/`kit.py` are the only files that import `hou`.

**Numbers.** `hython tests/polychain/run_scene_checks.py` → **0 failing over 13 cases**, ~9 s.

| Property | Measured |
|---|---|
| exact fill — built geometry vs the section end | ≤ **1.5e-6 m**, worst over all cases |
| gaps/overlaps between consecutive pieces | **0.0 m** on every curved case; ≤ 1.2e-6 m on straight runs (float32 storage at 20 m) |
| plumb-ness, `vertical` mode | **0.0°** |
| flatness, `stepped` mode | ≤ **3.8e-7 m** |
| bank, `adaptive` mode on a 25 % grade | **14.0365°** (atan 0.25 = 14.0362°) |
| stepped riser on that grade | **0.4909 m** over a 1.9631 m span — the grade, recovered |
| gate at its marker (PC-G1's own wording) | **1.8e-7 m** |
| slope fixing ON / OFF, widest horizontal reach of a 1.60 m gate | **1.5998 m** / **1.5521 m** (= 1.60·cos atan 0.25) |
| determinism | identical positions and ids on a second cook, and **0 moved baseline values across four `PYTHONHASHSEED` values** |
| scale, straight run | **10 000 pieces in 0.31 s**, all 10 000 packed |
| scale, curved run | 1 296 deformed pieces in 1.41 s ≈ **1.1 ms/piece** — the Python cost, and the reason §4.6/PC-G3 will want VEX |

**Mutation-tested, 14 mutations, 14 killed** — but the first pass killed only **10**, and *the four
survivors are the most useful thing this cycle produced*, because every one was a hole in the
checks rather than a hole in the code:

| Survivor | Why nothing saw it | What closed it |
|---|---|---|
| Bent pieces left as packed chords across the bend | `exact_fill` and `max_gap` both measure END POINTS, and a chord has the same end points as the arc it cuts | `axis_on_curve_m` — a bendable piece's axis is checked at **every station**, not only at its ends |
| The packed frame built from the START TANGENT instead of the chord (D21 deleted) | every packed piece in every case sat on a straight span, where the two are the same vector | case `M_rigid_over_bend` — a **rigid** 2.5 m beam straddling a 33.7° vertex is the only input that can tell them apart |
| The yaw-only frame replaced by the full 3D tangent | `across` is then un-normalised, so every piece came out 3 % narrow on a 25 % grade — and plumb, flat, fill, gaps and the axis check *all look along the chain or up it, never across it* | `cross_section_m`, which also kills dropping the across term entirely |
| The slope-fixing remap replaced by the identity | the checks read the section through the **same remap the builder used**, so the check and the defect agreed with each other | `widest_horizontal_m`, derived from the grade and never passing through the remap: 1.60 m fixed, 1.60·cos(atan g) free |

The hill's grade was raised **5 % → 25 %** in the same pass: a 2.86° bank sits close enough to
zero that a half-wired Z-mode still looks plausible.

**Decisions taken** (each pinned by a check; the mechanism notes live in the two modules' docstrings):

| # | Ambiguity | Decision |
|---|---|---|
| D20 | §3.2 never says which way a module points, and §3.4/§4.4 say "Z" for up | **+X along, +Y up, +Z across**; fit origin = bbox **min X**, fit length = `pc_size.x`, so geometry outside `[minX, minX+size.x]` legitimately OVERHANGS and is carried along (RailClone's "fitted size is not the bounding box"). The spec's Z is *Max's* up axis; Houdini is Y-up, so it is **Y** here. **Deviation from §3.2/§4.4's wording, not from its meaning** |
| D21 | §4.4 says "rebuild from the section end nodes" but not what a rigid piece rides on | The **chord** between the piece's own two ends, never the tangent at its start. This makes piece *k*'s end and piece *k+1*'s start the *same curve sample*, so "no gaps or overlaps" is a property of the construction rather than a tolerance; a start-tangent placement opens a gap at every bend |
| D22 | §3.2 asks for "a packed prim per module PLUS one point per module" | They are the **same object** — a packed prim already is one point and one prim — so the manifest rides on it and the two cannot drift apart |
| D23 | Is the starter kit a shipped `.bgeo`? | **No: a builder function.** A binary in the repo is a second source of truth that ages past the format it encodes, and `polyfactory/library/` and `polyfactory/resources/` are both gitignored, so it could not be committed anyway. `write_kit_file()` exists for artists who want one on disk; nothing in the build reads a kit file |
| D24 | §3.2 asks for a validator and does not say what it does on a bad kit | It **returns warning strings and never raises**, and `read()` fills every missing field with a documented default. A kit is exactly the artist-authored input warn-never-block was written for. Nine distinct faults are detected, and `K_broken_kit` pins the count so a lost detector shows |
| D25 | §4.4's "warn when a bent module's segment count is too low to follow curvature" | Measured, not counted: for each pair of adjacent local-x stations, the distance between the built chord and the true curve at their midpoint. `> bend_tol` (default 0.01 m) ⇒ `pc_warn_bend_resolution`, and the piece is **still built** — no auto-subdivision. **Seventh warning name** |
| D26 | "slope fixing" is named in `railclone.md` §1.3 and never defined | Verified against iToo rather than recalled: *"the segment width will remain the same as the source geometry when measured on the horizontal axis, but if switched off the width will be measured along the angle defined by the path spline"* ([Using Deform modes in RailClone Lite](https://www.itoosoft.com/tutorials/using-deform-modes-in-railclone-lite)). Implemented as `Params.fix_slope`, default **off**: the kernel is handed a Y-flattened copy of the curve and a piecewise-linear remap carries every planned distance back onto the real one. ⚠️ Under `adaptive` fill it is a **no-op** — every piece rescales to fill whatever it is given — so it only shows where a piece keeps its own length, which is why the acceptance case is a **tiled** pair and not the obvious one |
| D27 | What does `vertical` mean for a module with `pc_deform = 0`? | It **degrades to `stepped`**, because vertical IS a deformation ("vertices Z-displaced to elevation") and a rigid piece cannot express one. No warning: RailClone cannot deform a non-deformable segment either, and a warning on every post of a hillside fence is noise |
| D28 | §4.6's "slice caps: polyfill + box UV ... cap material tag" | `clip` verb + `polyfill` verb — vanilla Houdini, no hand-written polygon clipper — and the cap is found by the **plane test** (every point of the prim on the cut plane). ⚠️ Measured on 22.0.398: a prim `polyfill` creates **inherits its neighbour's attribute values, not the attribute default**, so the obvious "give `pc_cap` the default 1 before the fill" trick reads 0 on the cap it just built. Box UV is not done |
| D29 | Where does curve identity come from? | `pc_curve_id`, else `edge_id` (the streets id §3.1 says feeds `pc_elem_id`), else the primitive number — always normalised to a **string**, because `pc_elem_id` is a string address (D1) |

**Where the streets lesson landed.** `citygen_streets.md` §11.8's measured warning — *a lossy
identity inside an iterating loop is a random walk*, 68 recorded values moved by a rebuild on
cases where nothing had moved — is honoured structurally rather than by a tolerance: **a span
that holds no interior curve vertex is never rebuilt at all.** Its arc *is* its chord, so the
per-point round trip could only add float noise to a piece the chord already places exactly. The
same test is §4.6's instancing segregation arriving for free, which is why a straight 20 km run
comes out **10 000 packed prims and 0 deformed**.

**Not built, and named here so it is not mistaken for built:**
- **§4.3 corners.** Nothing places a `corner` slot yet: `corner_post` is in the starter kit and in
  `fence_style`, and `B_rect_closed` builds four sections that meet at bare corners. That is the
  next cycle, and §8 budgets the most time for it.
- **The §3.3 style-payload reader.** `build()` takes a `Style` OBJECT. Input 3 and PC-G4's
  two-face proof need a geometry reader; the kernel half (`Rule`/`Style`) already exists.
- **§4.5 conform** (input 4), and the **§5 parm face / the HDA itself** — there is no
  `pf_polychain` asset yet. Cycle 2 is the library layer an HDA will call.
- **A rigid piece straddling a bend cuts the corner and does not warn.** §4.4 specs the warning
  for bent modules only, and that is what shipped; `M_rigid_over_bend` records the behaviour.
- **PC-G3's VEX rewrite.** 1.1 ms per deformed piece is a Python-SOP number.

**Visual confirmation: none.** Every number above is headless. Per the show-don't-tell rule the
fence and the hill still have to be *looked at* before PC-G1/PC-G2 can be called anything, and the
live bridge was deliberately not touched this cycle.

### Cycle 2b — the review pass over cycle 2 (2026-08-21)

Two independent reviewers (spec-conformance and geometry-correctness lenses) returned **11
findings** over `place.py`, `kit.py` and `__init__.py`. **Every one reproduced under `hython`
before it was touched, and every one is fixed** — none was a false positive, and the two
"missing item" findings (§4.4's flatten-under, §4.2's plan writer) resolved in opposite
directions: one built, one written down as deferred below.

Suite after the pass: **19 scene cases, 540 recorded values, 0 failing**, plus **209 unit tests /
9 625 subtests** green in 0.73 s.

| # | Severity | Finding | Fix |
|---|---|---|---|
| 1 | major | A Houdini attribute is geometry-wide, so in a **mixed marker cloud** every `pc_u`-authored marker also carried `pc_dist = 0.0`, and `Marker.distance_on` prefers `dist` — a gate authored at u = 0.75 of a 20 m curve built at **s = 0**, silently | **D35** — `pc_u`/`pc_dist` resolved **per marker**: a zero `dist` beside a real `u` is the attribute default, not an authored 0 (at 0 the two conventions agree anyway, so only a both-non-zero conflict is left, and there `dist` still wins) |
| 2 | minor | `kit.read(None)`, `read_curves(None)` and `build(curves, None, …)` all raised `AttributeError` — out of a function whose contract says *"Never raises"*. An **unconnected kit input** would crash the cook instead of building the stand-in fence warn-never-block promises | **D34** — `None` is an unconnected input: empty results, one warning, stand-in geometry |
| 3 | minor | Kit validation warnings lived only in the transient Python report, so a kit missing `kitId` or carrying a duplicate module name **cooked clean forever** on an HDA. Per-element warnings were persisted; only the kit-level class was lost | detail string array **`pc_kit_warnings`** on the output, and `kit_validation` now reads the attribute instead of the report — so dropping the persist fails the check |
| 4 | minor | `Params.zmode` was deliberately unguarded (for D6's `""` sentinel), so an invalid **style** zmode overrode every module and then resolved to `adaptive`: a case-slipped `"Vertical"` banked every picket on a hillside instead of leaving it plumb. The same typo on the *kit* side is warned | unknown → `""`, i.e. **D6's own third state**: the module wins. The artist's intent is not silently inverted |
| 5 | minor | §4.4's **flatten-under** (RailClone's Flatten Stepped) is not implemented and was not in the not-built list, so it could be silently forgotten | recorded as deferred below — the honest answer, and PC-G2's visual pass now knows to expect the riser gap |
| 6 | minor | §4.2's *"the plan is inspectable geometry"* had no geometry writer; cycle 1 named that adapter as cycle 2's first job and it was never written | **`place.plan_points(geo, report)`** — one point per placement at its own start on the curve, carrying `plan_dicts()`'s payload. `plan_points` is now a standing check on every case |
| 7 | major | **`box_mesh` wound every face inward**: 18 of the starter gate's 18 faces failed a centroid-dot-normal test the Box SOP verb passes 6/6, so every module, every stand-in box and every slice cap was **inside-out** — the slice cap's normal read (−1,0,0) where +X is outward | **D33** — side faces and both end caps rewound; `inward_faces` asserts 0 against the box verb's own convention. ⚠️ Positions did not move: the 8 moved `geometry_digest` values are **vertex reordering only**, proven by rebuilding every case under both windings (worst position difference **0.000e+00 m**) |
| 8 | major | `Path.sample` **clamped** arclength into `[0, total]` on open curves, so a piece that legitimately overhangs the end was crushed into the end plane: a 1.6 m gate on a marker at 19.7 m of a 20.006 m curve built **1.106 m** long with its last two stations on one point, and the only warning stamped (`bend_resolution`) misnamed the fault | **D30** — an open curve **extrapolates** past either end along the end segment (`Path.sample` and `_Remap` both). The gate now builds 1.600 m. D20 already says a module may overhang; the sampler now carries it |
| 9 | major | `_frame` derived `across` from `cross(tangent, up)` **per point with no continuity**, so wherever a tangent's horizontal direction reversed — an overhanging crest, a cliff lip — it flipped 180° mid-piece and the panel twisted through itself (measured: consecutive-station `across` dot **−1**) | **D31** — the frame is **parallel-transported** along the piece: computed once per station in x order, flip-corrected against the previous one (`across` *and* `up`, so handedness is preserved). Also drops sampler calls from one-per-point to one-per-station |
| 10 | major | A yaw-only z-mode on a **vertical span** scaled every piece by `1e-9`: 25 posts of 0.0000 m along-axis width, and `warns = []`. The onset is continuous (0.0852 m at 45°, 0.0021 m at 89°), so it is not a special case for "exactly vertical" | **D32** — `_flat_ratio` under 1 % ⇒ the piece keeps its **3D** length (it stays visible, flat and plumb, which is what the mode still means) and carries the new **`pc_warn_degenerate_frame`, the eighth warning name** |
| 11 | minor | A rigid piece spanning a **suppressed hairpin** was built on a near-zero chord — a 2.5 m beam asked to cover 4 m materialised **0.10 m** long — with no warning of the 25× collapse | **D32**, second half — chord/span below 50 % stamps `pc_warn_corner_degenerate`, whose own meaning (*the corner degenerated*) is exactly the cause. The piece is still built |

**Six new scene cases**, each one a defect that was measured before it was written down:
`N_marker_mixed` (both marker conventions in one cloud), `O_no_kit` (unconnected kit input),
`P_crest_bend` (the overhanging crest), `Q_vertical_stepped` (the vertical run),
`R_hairpin` (the suppressed hairpin) and `S_overhang_gate` (a gate overhanging the curve end).

**Five new checks**, and *the reason they exist is that nothing already on the list could see any
of these defects*:

| Check | What it measures | Why the existing 24 missed it |
|---|---|---|
| `inward_faces` | every face of every kit module, against the Box SOP verb's winding | **not one existing check reads a normal** |
| `frame_dot_min` | the dot of consecutive stations' `across` vectors | every other check looks along or across *one* station; none compares a station's frame with the next one's |
| `station_spacing_m` | the smallest distance between two **distinct** stations of a deformed piece | every position check resolves a station **through the same sampler that had the defect**, so check and defect agreed — this one never asks where a station *should* be |
| `min_piece_span_m` | the piece's own axis span | zero-size geometry passes everything by having nothing left to measure. ⚠️ The first version measured the **bbox diagonal** and the mutation *survived*: the collapse is along the chain axis only, so a post crushed to 1.2e-10 m long still measures 1.2 m tall |
| `plan_points` | the plan written as geometry, one point per placement at its own start | the plan existed only inside one Python call |

**Mutation-tested again — 9 mutations, 9 killed** (each puts one fixed defect back):
marker `dist`-first ⇒ `marker_offset_m = 15.0 m`; the `None` guard removed ⇒ `build_all()` raises,
loudly; `pc_kit_warnings` dropped ⇒ 19 cases fail; `plan_points` removed ⇒ 19 cases fail; inward
winding ⇒ `inward_faces = 64 of 64`; the end clamp restored ⇒ `station_spacing_m = 0.0`; no
transport ⇒ `frame_dot_min = −1.0`; silent degenerate frame ⇒ `min_piece_span_m = 0.0` **and** the
missing warning; silent hairpin ⇒ the missing warning.

**Two checks were loosened, deliberately, and both record what they no longer assert:**
`section_coverage_m` became `[shortfall, overshoot]` — the shortfall is still asserted, but a
piece anchored on a **marker** near the end legitimately overhangs it, and clamping it would move
the gate off the marker PC-G1 accepts it by. `exact_fill_m` / `max_gap_m` skip pieces carrying
`pc_warn_degenerate_frame` and **count the skips**, because a collapsed yaw frame cannot both keep
a piece flat and land its ends on the curve — it keeps flat (still asserted by `flat_stepped_m`
and `plumb_deg`) and says so.

**New decisions:**

| # | Decision |
|---|---|
| D30 | An **open** curve extrapolates past either end along the end segment's own direction; only a **closed** one wraps. Clamping is what crushed an overhanging piece into the end plane, and D20 already promised the module's geometry may overhang its fit length |
| D31 | The frame of a deformed piece is **parallel-transported**, not re-derived per point: one frame per station, flip-corrected against the previous station's `across`. Two of three axes flip together, so the frame stays right-handed |
| D32 | Two silent collapses are measured and warned, and **neither blocks**: a yaw-only mode on a near-vertical span keeps its 3D length and says `pc_warn_degenerate_frame` (the **eighth** warning name), and a rigid piece whose chord covers less than half its planned span says `pc_warn_corner_degenerate` |
| D33 | `box_mesh` winds **outward**, asserted against the Box SOP verb rather than against an opinion about handedness |
| D34 | A `None` input is an **unconnected** input, not an error. Warn-never-block includes the wiring |
| D35 | `pc_u` vs `pc_dist` is resolved **per marker**, because a Houdini attribute is per-geometry and §3.1's own "streets-shaped carrier" is a merged cloud |

**Still not built** (this list replaces cycle 2's, unchanged except where noted):
- **§4.3 corners** — the next cycle, and §8 budgets the most time for it.
- **§4.4's optional flatten-under** (RailClone's Flatten Stepped, `railclone.md` §1 item 3).
  ⚠️ *Named by finding 5 and deferred here rather than silently forgotten:* in stepped mode each
  flat piece steps down a riser — **0.4909 m** on PC-G2's own 25 % hill — leaving a triangular air
  gap under the downhill end of every piece. RailClone fills exactly that gap. polyChain has no
  parm for it yet, so **PC-G2's visual pass should expect the gap and not read it as a defect**.
- **The §3.3 style-payload reader** — `build()` still takes a `Style` object.
- **§4.5 conform**, and the **§5 parm face / the HDA itself** — no `pf_polychain` asset yet.
  `plan_points` is written and waiting for that HDA's second output.
- **A rigid piece straddling a bend cuts the corner** — now *warned* when the chord loses more
  than half the span (D32), still not corrected; §4.4 specs the bend warning for bendable
  modules only.
- **PC-G3's VEX rewrite** — 1.1 ms per deformed piece is a Python-SOP number.

**Visual confirmation: still none.** Unchanged from cycle 2, and finding 7 is the argument for it:
an entire kit was inside-out through 305 green numbers, because not one number on the list read a
normal. The fence and the hill still have to be looked at.

### Cycle 2c — independent verification of cycle 2 / 2b (2026-08-21)

No code was written this cycle. A fresh agent that had authored none of `place.py`, `kit.py`,
`cases.py` or `checks.py` re-ran every suite from scratch, mutation-tested the checks with
defects it chose itself, and tried to put the first picture on the record. Two of the three
succeeded.

**The suites, re-run:**

```
python -m pytest tests/unit/test_polychain.py tests/unit/test_polychain_plan.py -q
    138 passed, 8700 subtests passed in 0.62s
python -m pytest tests/unit -q
    209 passed, 9625 subtests passed in 0.71s
hython tests/polychain/run_scene_checks.py
    19 cases, 474 [PASS] + 66 [SKIP] = 540 recorded values, 0 failing checks
    no "moved since baseline" block printed - every value equals its recorded one
```

⚠️ Cycle 2b's "209 unit tests" is the count for **all of `tests/unit`**, citygen included; the
polyChain half is **138 tests / 8 700 subtests**. Both numbers are real, and the log now says
which is which.

**No citygen regression, proven two ways rather than asserted:**

```
git diff --stat cityGen..polychain -- . ':!ideas' ':!graphify-out'
    12 files changed, 9661 insertions(+)   <- every one of them a polychain/ or tests/polychain/ file
hython tests/citygen/run_scene_checks.py
    16 cases, 774 [PASS], 27 [FAIL], and again NO "moved since baseline" block
```

The branch touches no citygen source at all, and the 27 red citygen checks carry values identical
to `tests/citygen/baseline.json` — they are the streets V1 work-in-progress failures this branch
was cut on top of (`selfx_city_merged`, the shallow-Y trims, the plaza disc), not something
polyChain moved. The citygen unit tests are inside the 209 green above.

**Mutation test — 5 mutations, 5 killed**, each one applied to `place.py` on a clean tree, run
through the full 19-case suite, then reverted (`git checkout -- place.py`; the tree was verified
empty afterwards and the suite re-run green):

| Mutation | Result | What went red |
|---|---|---|
| `vertical` mode follows the 3D tangent (both `_frame` and `_deform_positions`) | **killed** | `plumb_deg` in 4 cases (`F_hill_vertical`, `H_tile_slope_free`, `I_tile_slope_fixed`, `L_ramp_vertical`) |
| the slice is skipped — an over-long piece is built whole | **killed** | `exact_fill_m`, `module_fidelity_m`, `cap_prims`, 3 cases each |
| `pc_elem_id` = the prim's own number | **killed, loudly** | 58 red checks over 12 cases, `element_count` among them |
| `pc_elem_id` = one id per piece, derived from the output **point count** (ids stay unique and 1:1, only the addresses are wrong) | **killed, narrowly** | only `module_fidelity_m` (3 cases) and `marker_offset_m` (2) — **14 of 19 cases never noticed** |
| the last piece of a **closed** curve is dropped | **killed, narrowly** | only `section_coverage_m`, only in `B_rect_closed` |

**Two coverage defects, named plainly — both mutations died, but barely, and the reason is
structural:**

1. **The id-keyed checks fail OPEN.** `exact_fill_m`, `max_gap_m` and `axis_on_curve_m` all
   resolve built geometry by `scene.by_id.get(placement.elem_id)` and `continue` when the lookup
   misses, so a build whose prim ids do not match its plan's ids measures **0.0 m and passes**.
   `element_count` cannot cover for them: it compares `len(by_id)` with `len(plan)`, and a 1:1
   id scramble keeps both. `unique_elem_ids` reads the **plan**, not the geometry. Cheap fix,
   and it is on the *Next up* row: assert that every planned `pc_elem_id` has a built prim, and
   count the misses instead of skipping them.
2. **`element_count` cannot see a defect in the plan.** It measures geometry against the plan the
   same run produced, so dropping a placement *before* it becomes a job moves both sides
   together. Only `section_coverage_m` — which measures against the **section**, an independent
   quantity — caught the missing final piece of the closed rectangle. That is the argument for
   keeping at least one check per property anchored to something the builder did not compute.

**Visual sanity: attempted, and it failed — the honest record.** `houdini_status` was green and
the session was clean (`untitled.hip`, no unsaved changes, `/obj` empty), so per §0.0's live-session
rules a straight fence and a gently curved one were built under **`/obj/polychain_gate`** — two
Python SOPs calling `place.build` on the starter kit, both cooking without error:

| Fence | Curve | Built |
|---|---|---|
| straight | 20 m line | 20 pieces, **20 packed / 0 deformed**, no warnings |
| curved | 16-segment arc, R = 30 m, 75°, 39.27 m long | 38 pieces, **23 packed / 15 deformed**, no warnings |

The first `houdini_render_view` call timed out, and from that moment on **every `hou` call that
touches the node graph timed out** while `houdini_status` kept answering and non-graph HOM calls
(`hou.applicationVersionString()`) still returned — i.e. the node graph is locked, not the
process. `houdini_delete_node("/obj/polychain_gate")` and `hou.setUpdateMode(Manual)` timed out
too, so **the gate subnet could not be removed** and the session was NOT left as it was found.

⚠️ **For Hannes / the next live pass:** `/obj/polychain_gate` is probably still in the GUI session
and a floating flipbook panel with it. Delete the node; nothing was saved, and the .hip on disk is
untouched. **Suspected cause, recorded so the next agent does not repeat it:** the Python SOPs
called `hou.pwd().setComment(...)` *during their own cook* to report the piece counts. Under
hython that cooks once; in a GUI session with auto-update on, modifying the node from inside its
cook dirties the node that is cooking. **Never write to a node from inside its own Python SOP —
return counts through geometry attributes instead.** This is a finding about the *render harness*,
not about `place.py`: the same two fences cook clean and instantly under `hython`.

So PC-G1 and PC-G2 remain **numerically green, visually unconfirmed** — unchanged from cycle 2b,
and now with a named reason rather than a deferral.

**Verdict.** Cycle 2 is real: 540 values, re-derived independently, all green; the mutation kills
show the checks bite; the citygen suites are untouched. It is not "done" in the dev-loop sense,
because nobody has yet *looked* at a polyChain fence.

### Cycle 3 — §4.3 corners (2026-08-22)

**Built:** the stage §8 budgets the most time for. One new kernel module, two new
`Placement` fields, one new warning name, and 14 new scene cases.

| File | What |
|---|---|
| `polyfactory/scripts/python/polyfactory/polychain/corner.py` | §4.3 — `Bevel` (the miter plane), `fillet`, `merge_bend_sections`, `build_assembly` (compose), `displacement`, `solve_corners`, `plan_curve` (the orchestrator that now sits between §4.1 and §4.2) |
| `polychain/{__init__,plan,place}.py` | `Params.corner_displacement` / `fillet_segments`, `WARN_FILLET_CLAMPED`, `Placement.anchor` / `.cuts`, `plan_section(trim=…)`, and in `place.py` the anchored transform, the world-space `clip_plane`, and `pc_corner_cut` |
| `tests/unit/test_polychain_corner.py` | 39 tests, no `hou`: the miter arithmetic, the odd/even compose equality, weld-vs-not, and that every degenerate input still returns a plan |
| `tests/polychain/{cases,checks,run_scene_checks}.py` | 14 new cases and 8 new checks, all `corner_*` |

**The behavioural reference was read, not recalled.** `railclone.md` names the corner
machinery and does not define it, so iToo's own wording was fetched on 2026-08-22 (the
docs host 403s a plain fetch; the quotes came back through search extracts of *How to
Fine Tune Corners* and *Mastering the Linear Generator*) and is quoted verbatim in
`corner.py`'s docstring: **"the segment is repeated on both sides of the corner, and is
sliced to maintain its full length on the outside of the corner … adjust this slice
position using the BC Offset option"**; **"using an odd number of segments always creates
a symmetrical corner composition"** / for an even count **"RailClone centres the segment
immediately before the vertex"**; and Bevel Mode's three — **Reset** "placed in its
default position, and simply sliced at the corner vertex", **Extend** "extends the
geometry of the segments along the bevel, giving an appearance of continuity around the
corner", **Symmetric** "the segment equalised either side of the Corner vertex".

**The whole of §4.3 in one number.** At a turn `t` the miter plane is
`n = unit(tin + tout)`, so `n·tin = n·tout = cos(t/2)` and `n·across = sin(t/2)`: a piece
of half-width `h` reaches `e = h·tan(t/2)` past the vertex on its OUTSIDE edge and is cut
`e` short on its inside. `e` places the corner module, `e` is how far `extend` pushes a
default run, and the offset shifts the plane `e` is measured from. Everything else is
bookkeeping.

**Numbers.** `hython tests/polychain/run_scene_checks.py` → **33 cases, 947 PASS + 283
SKIP = 1 230 recorded values, 0 failing**, ~2 s. Unit: **177 polyChain tests / 8 700
subtests in 0.67 s** (248 / 9 625 over all of `tests/unit`).

| Corner property, measured on built geometry | Worst |
|---|---|
| every point of a mitered cut face lies on its own bisector plane (`corner_plane_dev_m`) | **1.233e-6 m** over all cases |
| the two cut faces are the same polygon once slid together (`corner_face_mate_m`) | **8.06e-7 m** — except `reset`, below |
| the seam at the vertex, offset 0 (`corner_seam_m`) | **1e-6 m** — no hole, no overlap |
| the seam with corner offset ±25 % (requested ±0.056569 m = 2·o·cos 45°) | residual **1e-6 m** |
| single-module outside face keeps `pc_size.x` (`corner_outside_m`) | **0.160000 m**, error ≤ **1.1e-6 m** |
| compose symmetry, THREE corner modules (`corner_symmetry_m`) | **0.0 m** |
| compose symmetry, TWO corner modules | **1.200 m** = the extra module's own length |
| the corner assembly meets the fill that runs up to it (`corner_abut_m`) | **1e-6 m** |
| fillet r = 1.5 m: clearance from the original sharp vertex, analytic `r(1/cos45−1)` = 0.621320 | **0.621320 m** |
| a squeezed corner (three 1.20 m blocks on a 1.50 m leg), analytic 1.20·1.50/2.32 | **0.775862 m** + `pc_warn_overflow` |
| the welded closed rectangle, piece to piece (`max_gap_m`) | **5.38e-7 m** |

⚠️ **`corner_face_mate_m` is 0.042426 m under `reset`, and that is the policy working.**
RailClone's Reset leaves each piece "in its default position, simply sliced", so the two
cut faces are MIRROR images rather than one face and the outside of the corner keeps a
notch of `e·√2` = 0.03·1.41421. `extend` closes it to 6.7e-7 m. That one number is the
difference between the three policies, and the check compares it against the notch the
policy asks for rather than against zero.

**Mutation-tested, 10 mutations, 10 killed** (each puts one 4.3 defect back on a clean
tree, runs all 33 cases, and is reverted; the tree was verified clean and the suite green
afterwards):

| Mutation | What went red |
|---|---|
| plane normal = the incoming tangent, not the bisector | 19 red, 75 moved |
| the corner module is NOT duplicated on both sides | `corner_symmetry_m` in 3 cases, `corner_abut_m` |
| the miter overhang `e` forced to 0 | `corner_outside_m`, `corner_face_mate_m`, 78 moved |
| the corner offset ignored | `corner_seam_m`, both offset cases, and only those |
| the compose straddler is always module 0 | `corner_symmetry_m` in `Y_compose_odd`, 3 more |
| the clip keeps the wrong side of the plane | 23 red — the pieces are deleted, not mitered |
| bend breaks the run again (D36 reverted) | 1 red + 15 moved, `corner_welds` and `corner_turns` among them |
| a squeezed corner assembly no longer warns (D44) | `warnings` in `AD_short_legs` |
| the fillet does nothing | `corner_clearance_m`, `warnings` |
| the dissolved degenerate corner is never stamped | `warnings` in `AC_degenerate_corner` |
| *(cycle 2c's own finding, closed here)* `pc_elem_id` scrambled 1:1 on the built prim | `unresolved_elem_ids` in **all 33 cases** |

**Three checks were written because a mutation would otherwise have survived**, and one
existing check had to be corrected by 4.3 rather than satisfied by it:

* **Cycle 2c's named coverage defect is closed.** `exact_fill_m`, `max_gap_m` and
  `axis_on_curve_m` all reach geometry through `by_id.get(elem_id)` and `continue` on a
  miss, so a build whose prim ids do not match its plan's ids measured 0.0 m and passed;
  `element_count` compares two lengths that move together and `unique_elem_ids` reads the
  plan. **`unresolved_elem_ids`** counts the misses instead, and a 1:1 id scramble now
  turns all 33 cases red instead of two checks in five of them.
* `corner_outside_m` first measured the piece's LOCAL x extent, which is scale-invariant:
  it read a clean 1.200 m on a corner block D44 had squeezed to 0.776 m, so the check
  agreed with a squeeze it could not see. It measures world metres along the leg now.
* `corner_abut_m` first scanned every corner element on the curve, so on the closed
  rectangle it paired a post with the post at the far end of the 8 m side and reported a
  0.226 m "gap" that was really two different corners.
* `corner_turns` exists because the first reflex case **contained no reflex corner** —
  both vertices of the zigzag turned left and it scored `side = +1` twice while calling
  itself coverage. It records `[turn, side, mode, degenerate]` per corner, so that cannot
  happen quietly again.
* **`frame_dot_min`'s threshold was wrong the moment bend stopped breaking the run.** It
  asserted `> 0`, and a panel legitimately wrapping a 90° vertex scores exactly **0.0**.
  The defect it was written for (the un-transported frame, cycle 2b finding 9) scores
  **−1.0** with the path barely turning, so the threshold moved to −0.866 (a 150° turn
  between adjacent stations) and hairpin pieces — which really do turn the frame around,
  and say `pc_warn_corner_degenerate` — are skipped and counted.

**Decisions taken.**

| # | Ambiguity | Decision |
|---|---|---|
| D36 | §4.3 says bend is "the default piece **deforms across the vertex**", but §4.1 breaks a section at every corner — a broken run has no piece to deform across anything | **Bend does not break the run.** The sections either side of a corner are welded and the fill is solved once across the vertex; §4.4's existing interior-vertex test then bends whatever straddles it. RailClone's own wording agrees — *"Bevel Mode should be set to None to prevent the Default segments from continuing through to the corner"*, i.e. by default they DO continue through. A `pc_section` limit is never welded (D18) and neither is a spline end. **Deviation from §4.1's wording, not from its meaning:** decompose still emits the section list; §4.3 decides what to do with the boundaries. **EXTENDED IN CYCLE 4, with the number it was missing:** where the welded run's pieces land on a piece BOUNDARY at the vertex instead of spanning it, the joint is a butt joint, and two square-ended pieces meeting at an angle leave a wedge of doubly-solid geometry inside and the matching notch outside. That is inherent — RailClone's bend corner does the same, and **miter is the fix** — so it is measured and baselined as the ACCEPTED LIMIT rather than asserted to be zero: `corner_breach_m`'s bend branch walks the dissolved vertex and scores every butt piece against `h·cos(t/2)`, the value the butt geometry itself demands (excess **3.2e-7 m** over the suite), and `corner_wedge_m2` measures the solid it leaves — **0.00090 m²** per corner on the starter panel at 90°, **0.0018 m²** where the fatter post arrives. What the pair protects against is the number GROWING |
| D37 | Does the `corner` slot fill in bend mode too? | **No — the corner slot is a miter feature.** A welded run has no joint to fill. `fence_style` therefore uses `corner_post` only when the artist asks for miter, which is exactly how RailClone is used |
| D38 | §4.3's compose rule names odd/even symmetry and does not say what is laid where | Module `floor((N−1)/2)` **straddles** the vertex; earlier modules run back down the incoming leg, later ones out along the outgoing one. The straddler is the one "repeated on both sides", duplicated and sliced, each copy keeping its outside face at full length — so **N = 1 is the same rule with empty flanks**. The reserve per leg is `(L_c − e) + Σ flank`, which makes odd symmetric and even asymmetric by **arithmetic rather than by special case**: measured 0.000 m and 1.200 m |
| D39 | §4.3's "± percentage of corner-module length" — of what, and moving what | **REVISED by the cycle-3 review.** `o = pct/100 · L_straddler`, and it moves **the pieces along their own legs**; the cut plane stays on the vertex. The first answer gave each copy its own plane (`V − o·tin`, `V + o·tout`), which parts them by `2·o·cos(t/2)`: **measured, a 0.056569 m open hole at +25 % and 0.056569 m of DOUBLY SOLID interpenetrating geometry at −25 %**, both baselined as correct. Moving ONE shared plane along the bisector was tried and measured too — it is no better, because the two legs' centrelines meet **only** at the vertex, so any other plane cuts the two boxes at different lateral positions and the faces come out coplanar but slid apart by the same `2·o·cos(t/2)` (`corner_face_mate_m` 0.056569 m). The vertex plane is the only one that mates, so `near_in = near_out = −e + o` keeps the two copies **mirror images about it at every offset**: no hole, no double cover, and what the artist dials is how deep the miter bites into the module — §4.3's own "pull-in and slice". Measured by `corner_reach_m` (`L − e + o`: 0.12 m at +25 %, 0.04 m at −25 %) and by `corner_outside_m` (`L + min(o, 0)`: 0.12 m at −25 %). **Under `reset` with no corner module the parm is a documented no-op** — there is no piece to move, and RailClone's Reset is "simply sliced at the corner vertex" |
| D40 | Reset / Extend / Symmetric, which the spec names and does not define | **REVISED by the cycle-3 review.** The policy is a **one-module corner assembly built out of the DEFAULT module** — the same machinery the corner slot uses, so it is anchored on the straight leg, duplicated both sides and cut on the plane. `reset` builds no boundary piece and the run is simply sliced where it stops; `extend` lays the module with its outside face on the plane (overhang `e`); `symmetric` centres it **exactly** on the vertex (overhang `L/2`). The first answer was an *extension of the fill span*, handed to `plan_section` as a negative trim, and three things were measured wrong with it on the 12+12 m L: under **`tile`** the extension gets TILED INTO (symmetric planted a whole new sliced half-panel entirely past the vertex, which the clip then annihilated to a 3 cm wedge carrying its own `pc_elem_id`; extend planted a 0.03 m sliver); under **`adaptive`** "symmetric" was only approximately symmetric (straddler centred at 12.07 m of a 12.00 m leg); and the piece past the vertex was **deformed around the welded kink**, because a default piece has no anchor — at a 150° turn its cut faces stopped mating (0.0552 m) and the survivor was inside-out. The boundary piece keeps `slot = "default"` and continues the run's own index numbering, so `pc_elem_id` stays an address. Applied only where the default run actually reaches the corner — with a corner assembly in the way the run simply abuts it, which is RailClone's own advice |
| D41 | A mitered `corner_post` has `pc_deform = 0`, and §4.2 may only slice `pc_deform = 2` | **A miter cuts whatever it is given.** §4.2's opt-in is because the FILL chose to cut; the miter is the artist's corner mode, and RailClone's Bevel Corner slices any segment. The piece is unpacked and clipped, `pc_corner_cut = 1` records it, and `rigid_deformed` exempts **and counts** exactly those pieces |
| D42 | Does a filleted corner still break the run, and what is its turn? | The arc's **midpoint vertex is forced** to be a corner and every other arc vertex is suppressed, so a rounded corner breaks in exactly one place and can still carry a corner module. Its turn is the arc's own per-vertex turn, so the miter degenerates into a plain perpendicular cut — which is right: the fillet has already absorbed the corner |
| D43 | A fillet radius too big for its legs | **Clamped, never rejected**: the tangent distance is capped at 45 % of the shorter adjacent leg (two adjacent fillets can never eat each other) and the curve carries `pc_warn_fillet_clamped` — the **ninth** warning name. A **degenerate** corner is not filleted at all: `r·tan(t/2)` at 179.99° is 17 km before the clamp bites, so the "fillet" would be the same hairpin with five more vertices on it |
| D44 | §4.3 item F's "a corner whose adjacent sections are shorter than the corner module" | **Squeezed, not dropped** (D13's policy applied to corners), and **CORRECTED by the cycle-3 review: the squeeze is about the CUT PLANE, not about the vertex.** Scaling `t_near` along with the length pulled the squeezed copy's cut face back off the plane by `e·(1−f)` — measured as a 0.0283 m notch at every corner of a 12 × 0.12 m rectangle, and as a 1.200 m cut face mating against a 0.776 m one where a 12 m leg meets a 1.5 m one (`AD_short_legs` never saw it, because both of its legs squeeze equally). The fixed point is `near`, so the factor is `(L + |near|)/(reserve + |near|)` and the squeezed module still reaches the plane: `AQ_asym_squeeze` mates to **1.1e-8 m**. What is left over on `AP_narrow_rect` — `(L − L·f)·√2` — is the part of the mating diagonal a module shortened below `2e` cannot span at all, and it is asserted as that number rather than as zero. Per SECTION, so the long side's joint stays exact |
| D45 | RailClone documents that it **cannot offset the last corner of a closed spline** | **polyChain can.** `decompose` already pairs a closed curve's sections cyclically (D10) and §4.3 walks the same pairing, so the wrap corner is an ordinary corner with an ordinary offset. `V_rect_miter` measures all four corners of PC-G1's own figure and the wrap one is not special-cased anywhere. ⚠️ It cost one real bug first: the wrap piece's section-local `s0` came out at 39.92 m of a 12 m section until `_wrap_local` folded it |
| D46 | §4.3's narrow-angle fallback "falls back to bend" — in miter mode, what does that mean? | The corner is **welded like a bend corner** even though the mode says miter, because bend means the run continues through. The dissolved vertices are remembered before the weld and `pc_warn_corner_degenerate` is stamped on whichever pieces end up spanning them — otherwise the warning has no boundary left to live on and a hairpin builds silently |
| D48 | §4.3 says nothing about a corner whose legs are **not coplanar** — a hill crest, or a 90°-in-plan corner on a grade | **The bevel is yaw-flattened whenever the pieces cut on it are.** `place._frame` builds a `vertical` or `stepped` piece PLUMB, on the horizontal projection, so a bevel taken from the 3D tangents cuts it on a plane it has nothing to do with: measured, a 40° pitch kink anchored its two copies 0.055 m apart in Y and mated their faces to only **0.0548 m** (a flat L mates to 8e-7 m), and a 90°-in-plan corner on a 25 % grade sliced the plumb 1.30 m post horizontally-obliquely and left a **0.345 m stump** beside a full-height mate — both silent. So: yaw-only modules ⇒ flatten the tangents, the plane goes vertical, the overhang is measured horizontally. `adaptive` modules keep the 3D bisector (they bank with the path), and a **mixed** answer keeps the 3D plane, which is the only one right for either of them. Flattening also splits the two coordinate systems apart: the assembly is laid out in flattened leg metres (that is the space the piece is built in) while `s` is arc length, so the bevel carries `arc_in`/`arc_out = 1/cos(pitch)` and the anchor rides the leg's real 3D line — without it the post reached 0.16 m horizontally where the run had given up 0.16 m of arc. `AL_crest_corner` and `AM_graded_corner` both mate to **0.0** |
| D49 | The offset and the overhang are the same number, and §4.3 clamps neither | **The corner module keeps at least a tenth of its length on its own leg.** The straddler's reserve is `L − e + o`, and both ends of that can drive it to zero: a turn sharp enough that `e ≥ L` (126.87° for the starter kit's 0.16 m post) and a large negative offset. Both were measured building silently: at a 130° turn the negative reserve became a negative trim, the default run built THROUGH the vertex uncut and `place` bent it around the kink into an inside-out panel (volume −0.103 m³) interpenetrating the other leg by 0.031 m; at −100 % offset the post was clipped out of existence (14 elements for a 16-piece plan) and left a 0.23 m hole. Warning list **empty** in both cases. `o` is clamped up to `e − 0.9·L`, `pc_warn_overflow` fires when the clamp bites, and the abutting default run is handed the plane as well. **No upper clamp** — a positive offset that stops the piece short of the plane leaves a notch, which is what the knob is for |
| D50 | Does a default piece abutting a corner **assembly** get the bevel plane too? | **Yes, always.** It used to get it only where the corner slot was empty, so wherever the reserve is shorter than the piece's own across-reach `e` the two legs' square ends crossed inside the corner module's footprint — measured as a real interpenetration on a 1.5 m equilateral triangle (reserve 0.0215 m against a 0.03 m panel half-thickness), invisible from outside and invisible to `max_gap_m`. `_apply_cuts`' own across-reach test already expresses the condition exactly, so it is handed the planes unconditionally and the pieces it actually cuts carry `pc_warn_overflow` — with an empty corner slot the same cut IS `reset` and says nothing, which is the difference |
| D47 | Two corner pieces on one section shared a `pc_elem_id` | A section can receive the "in" half of the corner at its end AND the "out" half of the corner at its start. The index is `2·compose_index + (side == "in")` — structural (D1), and collision-free by construction. **Found by `duplicate_elem_ids`**, which had never fired before: the two colliding posts were merged by `elements()` into one 5.7 m record that then failed five other checks |

**PC-G1's corner criterion, answered.** *"No gaps/overlaps at any corner in either corner
mode"*, on the closed rectangle and on the L, convex and reflex:

* **miter** — the joint is two clipped faces on one plane: coplanar to **1.2e-6 m**,
  mating point-for-point to **8e-7 m**, separated by **1e-6 m** at offset 0 and by exactly
  the requested amount when offset. Both legs' outside faces reach the plane, so there is
  no notch.
* **bend** — there is no joint at all: the run is welded and continuous, `max_gap_m`
  **5.4e-7 m** around the whole ring.

⚠️ **And one honest limit, recorded rather than smoothed over.** In bend mode the corner
is closed **on the axis**, but whether a single piece actually wraps the vertex depends on
where the fit put its boundaries: `corner_welds` reads **[4, 3]** on the rectangle (four
corners dissolved, three wrapped by one panel) and **[1, 0]** on the 24 m L-shape, where
twelve 2 m panels fit exactly and a piece boundary lands on the elbow. That corner is
continuous and still shows the notch a butt joint leaves on its outside. **The fix is
miter with a corner module, which is what corner modules are for** — and it is why
`corner_welds` records both numbers instead of averaging them.

⚠️ **A wrapped panel says `pc_warn_bend_resolution`, and that is D25 working.** A 2 m
panel with 0.25 m stations cannot follow a 90° kink inside `bend_tol`, so the welded
rectangle warns 3 times and §4.4 still refuses to auto-subdivide. The warning IS the
argument for reaching for miter.

**Baseline movement, all of it explained.** Only **two** of the 19 existing cases moved:
`B_rect_closed` (13 values — D36 welded its four sections into one closed ring: 40 pieces
became 38, 40 packed became 35, and it now warns `pc_warn_bend_resolution` 3 times) and
`R_hairpin` (`frame_dot_min` 1.0 → skipped, the hairpin exemption above). The other 17
cases are bit-identical, including every `geometry_digest`.

**No citygen regression**, proven the same two ways cycle 2c used:
`git diff --stat cityGen..polychain -- . ':!ideas'` touches only `polychain/` and
`tests/polychain/` files, and `hython tests/citygen/run_scene_checks.py` prints **27
failing checks and no "moved since baseline" block** — the same streets-V1 work-in-progress
failures this branch was cut on top of, unmoved.

**Not built, and named so it is not mistaken for built:**
- **A corner module in BEND mode** (D37). The layout code exists and is unreachable: bend
  welds the run, so nothing asks for it. If a consumer ever wants a post at a smooth
  corner, that is the branch to open.
- **Adaptive × miter is not gated.** RailClone documents Adaptive and Bevel as *mutually
  exclusive* (`railclone.md` §6.2) and works around it with two generators; polyChain
  simply lets the fit run on the reserved span, and the numbers above say it closes. If a
  case is ever found where it does not, this paragraph is where to start.
- **The fillet and the miter do not compose into a mitered fillet** (D42): the fillet
  absorbs the turn, so the plane becomes a perpendicular cut. That is deliberate, and
  `AB_fillet` runs in bend mode because miter has nothing left to do there.
- Everything cycle 2b listed and this cycle did not touch: **§4.4's flatten-under**, the
  **§3.3 style-payload reader**, **§4.5 conform**, the **§5 parm face / the HDA**, and
  **PC-G3's VEX rewrite**.

**Visual confirmation: still none**, and this is the third cycle to say so. §4.3 is the
stage the show-don't-tell rule was written for — 1 164 numbers cannot tell anyone whether
a mitered fence corner *looks* right — and the live bridge was deliberately not touched
(cycle 2c wedged it, and `/obj/polychain_gate` may still be sitting in the GUI session).
PC-G1 is now **numerically complete and visually unconfirmed**.

### Cycle 3r — the §4.3 review, worked through

Three independent reviewers (spec conformance, corner geometry, adversarial closure)
returned **14 findings**. Every one was reproduced on built geometry before anything was
changed, and every geometric one is a standing scene case now (`tests/README.md`: a
measurement made during a review belongs in `checks.py` afterwards). **11 new cases,
AH–AR**; the suite is **44 cases / 1 725 values (1 371 pass, 354 skip) / 0 failing** and
**196 polyChain unit tests**.

| # | Finding | Verdict |
|---|---|---|
| 1, 7 | `corner_offset_pct` silently dead in the displacement path | **Fixed** — `build_assembly` set the offset only after its empty-mods early return, so 0 %, 25 % and 50 % printed `bevel.offset = 0.000000` and built byte-identical geometry. `solve_corners` sets it off the default module now. `AO_displace_offset` |
| 2 | extend/symmetric tiled INTO the extension; "symmetric" was not symmetric | **Fixed** — D40 revised: one anchored boundary module. `symmetric` reaches exactly `L/2` in every fill mode (`corner_reach_m` 1.000000 against an analytic 1.0), `extend` `L − e`. `AN_tile_symmetric`, `AF`, `AG` |
| 3, 12 | D44's squeeze scaled about the vertex, so the squeezed cut face left the plane | **Fixed** — D44 corrected. `AQ_asym_squeeze` mates to **1.1e-8 m** (was 0.0400 m); `AP_narrow_rect` keeps only the `(L − L·f)·√2` a sub-`2e` module cannot span, asserted as that number |
| 4, 9, 10 | negative reserve at sharp turns / at a large negative offset | **Fixed** — D49's clamp + `pc_warn_overflow` + the plane handed to the run. `AH_sharp_turn` (140°) and `AR_offset_past` (−100 %) both build closed, warn, and score `corner_breach_m` **0.0** |
| 5 | negative offset double-covers a solid wedge; positive opens a hole | **Fixed, but NOT the way the reviewer proposed** — the suggested single shared plane was implemented, measured, and rejected: it turns the hole into a 0.056569 m slide of the same size (see D39). The plane stays on the vertex and the pieces move |
| 6 | non-planar corners mitered on the 3D bisector while pieces are built plumb | **Fixed** — D48. `AL_crest_corner` and `AM_graded_corner` mate to **0.0**; the beheaded post reads its full **0.160000 m** again (was 0.469 m) |
| 8 | `solve_corners` docstring promised a tuple | **Fixed** — one line |
| 11 | `_frame_of` recovered a face's affine map from a pair that varied in two local axes | **Confirmed and fixed, and the reviewer was right that both figures were clean** — least-squares over all face points, with a single-axis pair search as the fallback and **no silent world-axis default**: an unrecoverable frame returns `None` and the caller skips. `AJ_reflex_closed` 0.160000 → **0.0** and `AK_pentagon` 0.128742 → **0.0**. It also removed a phantom from the *existing* baseline: `min_piece_span_m` read 0.113137 m (= 0.08·√2, the artefact itself) on six mitered cases and reads the real module length now |
| 13 | the displacement extension was deformed around the welded kink | **Fixed** — same fix as 2: the boundary piece is anchored on the straight leg. At a 150° turn `corner_face_mate_m` is **9.7e-7 m** (was 0.0552 m) and nothing is inside-out |
| 14 | the run abutting a corner assembly never got the plane | **Fixed** — D50. `AI_triangle` (120° turns, 1.5 m legs) scores `corner_breach_m` **0.0** and says `pc_warn_overflow` |

**Two checks were added, because the existing 33 could not see three of these findings:**

* **`corner_breach_m`** — the interpenetration detector. Every corner check measured the
  JOINT; none of them measured whether a piece stays on its own side of the plane at all.
  It walks the corner's own two legs (a bisector plane is infinite, and the opposite side
  of a triangle crosses it perfectly legitimately) and reports the worst crossing. It
  kills three separate mutations.
* **`corner_reach_m`** — `L − e + o`, read off the built points. This is what the corner
  offset moves now that the plane does not, and it is what makes `symmetric` provably
  symmetric rather than approximately so.

**Three existing checks were corrected rather than satisfied**, each because a finding
proved them wrong rather than the builder:

* `_corner_caps` files every CAP POINT under the corner **it was cut by** (matched against
  the piece's own `cuts`), not under the nearest vertex. Once a default piece can be cut at
  both ends, filing whole elements scored a 0.73 m "plane deviation" on a piece that is
  exactly on both of its own planes — and on a 12 × 0.12 m figure two vertices are 0.12 m
  apart, so "nearest vertex" is not even the right corner.
* `corner_abut_m` looks for the run **on that leg's own section**, and measures in XZ for
  `stepped` pieces (D24's riser, the same exemption `max_gap_m` and `exact_fill_m` already
  carry). A squeezed leg with no run left has no abutment; it has `pc_warn_overflow`.
* `corner_outside_m` compares against the piece's **own planned length**, not the module's
  nominal one: on an asymmetrically squeezed corner it was asserting that the squeeze had
  not happened. `corner_reach_m` asserts the squeeze factor itself.

**Mutation-tested, 8 mutations, 8 killed** (each puts one review defect back, runs all 44
cases, and is reverted):

| Mutation | What went red |
|---|---|
| D44's squeeze scales about the vertex again | `corner_face_mate_m` ×2, `corner_breach_m` |
| D49's clamp removed | `element_count`, `unresolved_elem_ids`, two `corner_face_mate_m` |
| the run abutting a corner assembly is not cut | `corner_breach_m` ×3 (140°, 120°, 90°), `warnings` |
| D48's yaw-flattening removed | `corner_abut_m` ×2, `corner_outside_m` (0.5696), `corner_face_mate_m` |
| D39: the offset moves the cut plane again | **12 red** — mate, breach and seam across every offset case |
| D40's boundary piece is not anchored | `section_coverage_m` ×3, `pc_warn_bend_resolution` returns |
| the ORIGINAL `_frame_of`, whole | `corner_abut_m` **0.160000** and **0.128742** — the reviewer's two numbers, exactly |
| the anchored piece is scaled to its ARC span (D48's arc factor dropped) | `corner_abut_m` ×2, `corner_outside_m` ×2 |

**Baseline movement, all of it explained.** No case went red. `AD_short_legs` moved
(0.775862 → **0.790000**: D44's corrected factor is `(1.5+0.08)/(2.32+0.08)`, not
`1.5/2.32`), `AF`/`AG` moved and **stopped warning** `pc_warn_bend_resolution` (the
boundary piece no longer rides the kink), `W`/`X` moved (`corner_seam_m` is 0 at every
offset now; `X_corner_offset_neg`'s `corner_outside_m` 0.16 → **0.12** = `L + o`, the
miter eating the pull-in), and six mitered cases lost the 0.113137 m `_frame_of` phantom.
`E_hill_adaptive` tightened (1.53e-6 → 5.65e-7) because the same phantom had been
polluting its axis measurements.

⚠ **One thing that changed and is worth a second look in the viewport.** A PURE PITCH
kink — a hill crest with no yaw — flattens to a **0° turn**, so its miter degenerates to a
perpendicular cut and the corner module is duplicated into two full copies back to back
(`AL_crest_corner`: `corner_reach_m` 0.16 m per side, 0.32 m of post in total). It closes,
it mates to 0.0 and it warns nothing, but whether a doubled post reads as right at a crest
is a judgement no number here can make.

### Cycle 3v — independent verification of cycle 3 / 3r (2026-08-22)

A fresh agent that wrote none of §4.3, told to trust nothing. Three things were asked
for: re-run everything, mutation-test the corner checks specifically, and **judge PC-G1
on the image**. All three ran; the third had to take an unplanned route.

**Every claimed number reproduced, exactly.**

| Claim in cycle 3 / 3r | Re-measured here |
|---|---|
| 44 scene cases / 1 725 values (1 371 pass, 354 skip) / 0 failing | **44 / 1 371 PASS + 354 SKIP = 1 725 / 0 failing** ✅ |
| 196 polyChain unit tests | **196 passed, 8 700 subtests, 0.67 s** ✅ (267 / 9 625 over all of `tests/unit`) |
| no citygen regression | `tests/unit/test_citygen.py` + `test_plan.py` **71 passed / 925 subtests**; `hython tests/citygen/run_scene_checks.py` → **27 failing, NO "moved since baseline" block** ✅ |
| no polyChain baseline movement | polyChain run prints **no "moved since baseline" block** ✅ |

**The citygen non-regression is structural, not just observational.**
`git diff --stat $(git merge-base cityGen polychain)..polychain -- . ':!ideas'` touches
`polychain/*.py`, `tests/polychain/*`, `tests/unit/test_polychain*.py`, `tests/README.md`
— and `graphify-out/` — and **not one citygen source or test file**. The 27 failures are
therefore the streets-V1 work-in-progress this branch was cut on top of, by construction.

**Mutation test of the corner machinery — 6 mutations, 4 killed, 2 proved to be no-ops.**
Each was applied to a clean tree, run against all 44 cases, and reverted; `git status` was
verified empty afterwards and the suite re-run green.

| # | Mutation | Result |
|---|---|---|
| M1 | the bevel normal is the INCOMING TANGENT, not `unit(tin+tout)` | **KILLED** — 49 red, 177 moved |
| M2 | the clip keeps the wrong side of the plane (both `plane_in`/`plane_out` signs flipped) | **KILLED** — 47 red, 166 moved (`corner_breach_m`, `corner_symmetry_m`, `element_count`, `unresolved_elem_ids`, `warnings`) |
| M3 | the "out" half of the mitered pair is never built | **KILLED** — 23 red, 175 moved (`corner_face_mate_m`, `corner_symmetry_m`, `corner_abut_m`) |
| M4 | `Bevel.mode` no longer falls back to bend when degenerate | **SURVIVED — and it is a NO-OP, not a coverage hole.** See below |
| M5 | `_joinable` ignores `corner.degenerate`, so miter mode never welds a hairpin | **KILLED** — `warnings` red, 12 moved |
| M6 | `Bevel.degenerate` forced False | **SURVIVED — no-op, same reason** |

⚠️ **M4 and M6 survive because Bevel's own degenerate branch is unreachable code.**
This was not argued, it was instrumented: `Bevel.__init__` was wrapped over the whole
suite and **40 bevels are constructed across the 44 cases, of which 0 are degenerate**.
`merge_bend_sections` welds every degenerate corner away *before* a bevel is ever built
(`_joinable` reads `Corner.degenerate` straight off decompose, whose test at
`decompose.py:216` is the identical `(180 − turn) < min_included_angle_deg`), so
`Bevel.degenerate`, `Bevel.warns` and `self.mode = "bend" if self.degenerate` never fire.
**The real D46 fallback is `_joinable`, and M5 kills it.** The dead branch is harmless but
it is also a decoy: a reviewer reading `corner.py` would reasonably believe it is what
protects a hairpin. Worth deleting, or worth a comment saying it is a belt on top of
braces — recorded rather than changed, because a verification pass does not edit the code
it is verifying.

**PC-G1 was judged on images — rendered headless, because the live bridge is wedged.**
`houdini_status` pings fine, `import hou` returns, `result = 1+1` returns — and **every
call that needs Houdini's main thread (`hou.hipFile.path()`, enumerating `/obj`,
`houdini_get_errors`) times out at 30 s**, repeatedly and after a 90 s wait. The GUI
session is blocked on something; it was left alone rather than fought, so
`/obj/polychain_gate` was **never created this cycle** and the ⚠️ in §0.0 about a leftover
from cycle 3 **still stands and could not be cleared**.

So the gate was rendered another way: a ~130-line orthographic rasteriser in the
scratchpad (`gate_render.py`) that walks the built `hou.Geometry`, expands packed prims
through `fullTransform()`, sorts by depth and paints with a flat lambert — **drawing any
backfacing polygon RED, so an inside-out module cannot hide.** It found its own bug first
and that is worth recording: Houdini winds **clockwise-from-front**, so `prim.normal()` is
the **negated** Newell normal — the first render came out uniformly red until a control
test on `K.box_mesh` (`hou prim.normal() outward: 6 of 6`) settled the sign. Reference
before memory, and it cost one wrong picture.

Images (scratchpad `.../421208db-9a0d-4d26-9c40-1453b001be19/scratchpad/`):
`G1_rect_{bend,miter}_wide.png`, `G1_{bend,miter}_c{0..3}_{top,iso}.png`,
`G1_corner_{bend,miter}_{top,tight,tightiso}.png`, `G1_fill_{tile,scale,adaptive,count}.png`,
`G1_fillmodes.png`, `G1_gate_marker.png`.

**What is actually in the pictures**, not what was expected to be:

* **miter, closed rectangle** — the corner post carries **one clean 45° seam running
  corner-to-corner in plan**, and from outside the post's outer arris is a **single
  unbroken edge**: both halves keep full length on the outside, no notch, no step. The
  runs abut the post square on both legs. **Zero red polygons anywhere** — nothing
  inside-out. The **wrap corner (0,0) of the closed spline is indistinguishable from the
  other three**, which is D45 confirmed in the image rather than in a number.
* **bend, closed rectangle** — from outside, the fence turns as one continuous surface
  with a clean vertical crease; no gap, no red. Inside the corner, the top view shows the
  butt joint the log already names.
* **four fill modes** — `scale` is visibly one 11.377 m stretched panel between two posts
  (4 pieces); `tile`, `adaptive` and `count` are **byte-identical** here, and that is
  D11 working, not a defect: the starter panel is `deform = 1`, so tile cannot slice, the
  whole run falls back to adaptive and **every piece carries `pc_warn_tile_fallback`**
  (confirmed on the prim attribute and in `report["warn_names"]`).
* **gate on its marker** — visible as the one low bay in the run, and measured:
  **world x 7.200000 … 8.800000, centre 8.000000, length 1.600000 m** against a marker at
  `pc_dist = 8.0` — **centre error 1.8e-7 m**, at full nominal length. PC-G1's "gate
  exactly at its marker" holds, on the centred reading.

**One real finding, and it is a coverage gap rather than a wrong number.**

⚠️ **A bend corner is never tested for interpenetration, and it interpenetrates.**
`corner_breach_m` — cycle 3r's own interpenetration detector — starts with
`[b for b in _bevels(scene) if b.mode == "miter"]`, so it reports **SKIP "no mitered
corners"** on *every* bend case: `B_rect_closed`, `T_lshape_bend`, `AB_fillet`,
`AC_degenerate_corner`. Measured on PC-G1's own figure (a 12 × 8 m closed rectangle,
`corner_style("bend")`, sampled at post height on a 5 mm grid, pieces grouped by
`pc_elem_id` — repro: scratchpad `measure2.py`):

| | bend | miter |
|---|---|---|
| doubly-covered area at (0,0) / (12,0) / (12,8) / (0,8) | **0.00090 / 0.00075 / 0.00063 / 0.00075 m²** | **0.0 / 0.0 / 0.0 / 0.0 m²** |
| worst interpenetration depth | **0.015000 m** — exactly half the 0.03 m panel half-width | **0.000000 m** |
| the overlapping pair | elements `default|0` and `default|19` of the ring, both `panel` | — |

**This is the butt joint, seen from the inside.** On this figure twenty 2.00 m panels fit
a 40 m ring exactly, so all four corners land on a piece *boundary* and no piece wraps
anything — the same condition `corner_welds` records as `[4, 0]`. Two square-ended 0.06 m
panels meeting at 90° must leave a wedge of doubly-solid geometry inside and the matching
notch outside; it is inherent, RailClone behaves the same way, and **miter is the fix**.
Cycle 3's log names **only the outside notch**. The inside half was never stated and is
measured by nothing, and `max_gap_m` cannot see it — it walks one run along its axis,
where the two pieces meet exactly.

**Not closed here, deliberately.** A verification pass should not invent a check for the
code it is auditing, and the honest fix is a decision (is the wedge accepted as inherent,
or does bend get a corner treatment?) rather than an assertion. The numbers and the repro
above are what makes the next cycle cheap. **Next cycle's first job on §4.3: give
`corner_breach_m` a bend branch that walks the dissolved vertex instead of the bevel
plane, baseline these four numbers as the accepted butt-joint wedge, and say so in D36.**

**Two things in this pass were the verifier's error, recorded so they are not re-found:**
a bare `marker` rule silently builds nothing (the slot is `marker:<id>`, `SLOTS` in
`__init__.py:56` says so), and the build report's key is **`warn_names`**, not
`warnings` — reading the wrong key made four correctly-warning runs look silent.

**Verdict.** §4.3's numbers hold up under a stranger; the corner checks are strong enough
that four of six mutations die loudly and the two survivors are provably dead code, not
blind spots. **PC-G1: the corners, the four fill modes and the gate-on-its-marker have now
been LOOKED at** — headless, not in the GUI viewport — and the miter closes cleanly in
every image. It is marked **image-verified (headless)**, with the GUI viewport pass still
owed, and with the bend butt-joint wedge named above as the one open item.

### Cycle 4 — the bend butt joint, §4.5 conform, §4.6 finalize (2026-08-22)

Three items in one cycle: close cycle 3v's open finding, then the two stages
§8 has left before the parm face. **Suite at the end: 59 scene cases /
2 902 values (2 021 pass, 881 skip) / 0 failing in ~3.6 s; 206 polyChain unit
tests; 11 mutations, 11 killed.** `tests/unit/test_citygen.py`,
`test_plan.py` and `hython tests/citygen/run_scene_checks.py` are unchanged
(27 failing, **no baseline movement**) — this branch still touches no citygen
file.

#### A. The bend corner is measured (cycle 3v's open finding, closed)

`corner_breach_m` opened with `[b for b in _bevels(scene) if b.mode ==
"miter"]` and there ARE no bevels in bend mode — `merge_bend_sections` welds
the two sections before `solve_corners` sees the boundary — so it reported
SKIP on every bend case while a butt joint sat inside the corner. It walks the
**dissolved vertex** now (`Section.welds`, D36), rebuilds the bisector there
from the path's own arriving/leaving tangents, and scores every piece that
ends or starts on it.

* **T_lshape_bend** — breach **0.021213 m**, wedge **0.00090001 m²**.
  Cycle 3v measured 0.0009 m² on a 5 mm raster with point-in-solid tests;
  this is a convex-hull intersection in XZ, a completely different method,
  and the two agree **to five decimals**.
* **AS_rect_bend_butt** (new, and it is 3v's own figure: 12 × 8 m closed, a
  panel-only default, so twenty 2 m panels fit the 40 m ring exactly and
  `corner_welds` reads **[4, 0]** — all four corners are joints) — breach
  **0.021213 m**, wedge **0.0009 m²** at every corner.
* **B_rect_closed** — breach **0.042426 m**, wedge **0.0018 m²**: the same
  geometry with the fatter 0.12 m post arriving at the seam instead of a
  panel.
* **AB_fillet** — **0.005853 m**: a rounded corner's own per-segment turn,
  which is the fillet working.

⚠️ **The number is NOT asserted against a constant.** A square-ended piece of
across half-extent `h` butting at a turn `t` must cross the bisector by
exactly `h·cos(t/2)`, so that is what it is compared with — derived from the
kit and the turn, never read off a run. **The measured excess over the butt
geometry is 3.2e-7 m across the whole suite**, i.e. the wedge is the joint and
nothing more. Multiplying the packed transform's scale by 1.03 puts it
**4.2e-2 m over**, on three cases.

**And the `id(bevel)` flap, found on the way.** `corner_reach_m` with no
expectation reports `sorted(reaches.items())[0]`, and `_reach_of` keyed its
dict on **`id(bevel)` — a memory address**. `AP_narrow_rect` moved between
0.06 m and 0.08 m across runs of *identical code*. Keyed on the vertex now
(D67); three consecutive runs agree.

#### The "unreachable" hairpin guard is reachable, and cycle 3v's two survivors die

Cycle 3v instrumented `Bevel.__init__` over the whole suite — 40 bevels, 0
degenerate — and concluded that `Bevel.degenerate`, `Bevel.warns` and the
`mode = "bend" if degenerate` line were dead code on top of `_joinable`. They
are dead **at first construction**, for exactly the reason that pass gives.
The route nobody looked at is **`flatten`**, which re-runs the constructor on
the yaw-flattened tangents (D48) — and yaw-flattening changes the turn:

```
path (0,0,0) → (8,6,0) → (0.4,12,0.2), vertical default, miter
    bevel as built : turn 104.837°, degenerate False, mode miter
    after flatten(): turn 178.493°, degenerate True,  mode bend, warns
                     (pc_warn_corner_degenerate)
```

`decompose` reads the **3D** tangents and can never see that hairpin, so this
is the only place it can be caught — and D48 is what made catching it
necessary. So the lines are **annotated, not deleted**, and pinned by
`TestFlattenDegenerate` (4 tests). **3v's M4 and M6, which both survived 44
scene cases, now both fail.** A third mutation is pinned with them: a
degenerate bevel's warning only ever reached an element through
`build_assembly`, so a style with **no corner module** dropped it entirely
(D68).

#### B. §4.5 SURFACE CONFORM — input 4

**The whole stage is a sampler (D54).** `conform.ConformPath` wraps
`place.Path` and answers the same two questions with the answer dropped onto
the surface; the tangent is a one-sided finite difference of *dropped*
positions, which is what makes an adaptive piece bank onto a hill the spline
knows nothing about. Nothing downstream needed a new branch — the three
Z-modes compose exactly as RailClone documents them because `_frame` and
`_deform_positions` were already written against that interface.

| what 4.5 asks for | measured |
|---|---|
| projected pieces touch the surface | `conform_contact_m` **≤ 3e-6 m** on every conformed case |
| adaptive / vertical **deform to** the surface | `conform_drape_m` **≤ 7e-6 m** at every station of every bendable piece |
| plumb-ness preserved **on a slope** | `plumb_deg` **0.0** on `BB_conform_vertical` (a flat spline over a ridge — every bit of the shape comes from the surface) |
| stepped **sits on** it, still flat | `flat_stepped_m` **0.0**, `stepped_riser_m` 0.0677 m, and **167 of 167 posts still PACKED** |
| camber tilt matches the surface normal | `camber_deg` **0.0000** with the tilt on and **14.0362** with it off, against atan(0.25) = 14.0362° |
| rays that miss | `conform_misses` **5** on `BE_conform_holes` (a hole one cell wide, plus a surface that stops at x = 12 of a 20 m run); the pieces keep spline elevation, nothing raises |
| back-facing polygons | `BF_conform_flipped` and `BG_conform_facing` produce a **byte-identical `geometry_digest` (c214fc56d4187466)** |
| a surface coarser than the pieces | `BH_conform_crease`: two 14 m facets, and only the panel straddling the crease says `pc_warn_bend_resolution` |
| a piece straddling a crease | the same case — and the crease sits at **10.2 m** on purpose, because at 10 m it lands on a piece boundary and at 11 m on a station, and in both of those the drape is resolved exactly and nothing warns |

⚠️ **Two things the checks got wrong first, both recorded because they are the
shape of the trap.** `Scene` did not pass the surface into `analyse`, so
`axis_on_curve_m` and `plan_points` measured built geometry against the
**undraped** spline and read **0.800 m** — which is the ridge amplitude, i.e.
the conform working, reported as a failure. And `sampler_matches_kernel`
compares `place.Path` with `Curve.sample`; it must do that on the **base**
path, because the drape is *supposed* to disagree with the spline.

⚠️ **A mutation survived here and the fix is a case, not an argument.** Making
`ConformPath.sample` return the SPLINE's tangent instead of the drape's moved
**not one number** in the whole suite: `bank_deg` was only asserted on the
hill, whose banking comes from the curve. `BA_conform_adaptive` — a dead-flat
spline over a ridge — is in `BANKS` now, and the mutation dies with
`bank_deg 0.0  adaptive pieces did not bank on a slope`.

**PC-G2, rendered headless and looked at** (cycle 3v's rasteriser, reused
unchanged; the live bridge was not touched): `G2_adaptive.png`,
`G2_vertical.png`, `G2_stepped.png`, `G2_camber.png`,
`G2_camber_end_{on,off}.png`, `G2_holes.png` in the scratchpad. The pickets
stand plumb with their feet on the ridge and their tops following it; the 167
stepped posts each sit flat on their own patch of ground; looking straight
down the run, the cambered panel is perpendicular to a ground plane that is
visibly tilted. **No red anywhere** — nothing inside-out.

#### C. §4.6 FINALIZE — the override cascade, the cap, the stamp

Instancing segregation was already automatic (cycle 2's `_needs_deform`), so
this cycle added the rest of §4.6 and then **checked the segregation itself**,
which nothing had:

* **`over_unpacked`** fits every unpacked piece against `world = O + M·local`
  and asks whether `M` is a transform × axis scale. **0 across all 59 cases**
  — and it found two real over-unpackings on the way. `S_overhang_gate`'s gate
  was real geometry that fitted a rigid transform to **1e-7 m**, because an
  open curve's **end vertex** was being read as an interior kink when a piece
  legitimately overhangs it (D30 extrapolates there — nothing bends) — D66.
  Mutating `_needs_deform` to unpack everything now fails on this check **and**
  on the instancing floor.
* **The instancing floor is asserted**, not recorded: `A_straight`,
  `CE_all_packed` (a straight run of rigid beams) and `CA_swap_module` must be
  **100 % packed**.
* **Swap and replace are one override stream** of attribute points wired
  upstream of finalize, and neither is a parm (3.4: "both must work WITHOUT
  touching the style"). `CA_swap_module` re-points all ten panels to gates:
  `override_round_trip` reads **[10 swapped, 0 replaced, 0 ids moved]**
  against a control cooked with the override input unwired.
  `CC_replace_hero` swaps one element for a slab no kit contains and its world
  bbox reads **[2.0, 2.0, 0.4]** exactly. `CD_replace_bent` replaces the piece
  that wraps an elbow and says **`pc_warn_replace_deformed`** (D58).
* **`elem_ids_survive_upstream`** merges an unrelated third curve into input 1
  — the ordinary thing an artist does — and requires every existing id to
  survive. `determinism` never could see this: it cooks the same inputs twice,
  which a cook-order id survives perfectly. It immediately found **D64**: a
  Houdini attribute is geometry-wide, so one prim carrying `pc_curve_id` gives
  every other prim a **blank** one, and reading a blank as an id collapses two
  curves onto the same address. Mutating the id to carry `prim.number()`
  fails **261** checks.
* **Slice caps** are box-UV'd from the module's own local frame at the
  module's own texel density and tagged `<module>_cap` (D59). ⚠️ The first
  version of the check compared the cap's uv diagonal with its **world**
  diagonal and failed 11 cases: a box projection of an OBLIQUE face compresses
  it — the mitered post's cut face is 0.2263 m across in world and 0.16 m in
  projection — which is what box mapping *is*. It measures against the
  projection now, which is what catches the real failure (a uv taken off world
  P, off by 12 on a corner post at x = 12).
* The **§3.4 stamp is complete**: `pc_curve_id`, `pc_style` and `pc_replaced`
  join the eleven that were there (D60), and the warnings are **collated**
  onto one detail array `pc_warnings` of `name:count` (D61), asserted against
  the per-element attributes so the two records cannot drift.

#### Mutations — 11 run, 11 killed

| # | Mutation | Result |
|---|---|---|
| 1 | the packed transform's scale × 1.03 | **KILLED** — `corner_breach_m` 4.2e-2 m over the butt wedge, 3 cases |
| 2 | `Bevel.degenerate` forced False (3v's M6, which survived) | **KILLED** — 5 unit tests |
| 3 | `mode = "bend" if degenerate` deleted (3v's M4, which survived) | **KILLED** — 1 unit test |
| 4 | the flattened-hairpin warning stamp removed | **KILLED** — 1 unit test |
| 5 | the surface normal is not flipped to oppose the axis | **KILLED** — `camber_deg` **165.9638** (a module rolled upside down by a back-facing polygon) |
| 6 | `ConformPath.sample` returns the spline's tangent | **SURVIVED, then killed** by adding `BA_conform_adaptive` to `BANKS` |
| 7 | the conform never asks for a deform | **KILLED** — `conform_drape_m` **0.165687 m**, `axis_on_curve_m` 0.1657 m |
| 8 | `_needs_deform` returns True always | **KILLED** — `over_unpacked` 10, the instancing floor, and four others |
| 9 | the swap does not re-point `pc_module` | **SURVIVED, then killed** by asserting the counts (`module_fidelity_m` compares geometry against whatever `pc_module` SAYS, so a swap that changes neither still agrees with itself) |
| 10 | a replace packs the module instead of the hero | **KILLED** — `replaced_bbox_m` [2.0, 0.9, 0.06] |
| 11 | `pc_elem_id` carries `prim.number()` | **KILLED** — 261 checks |

#### Baseline movement, and why each is an improvement

Eleven values moved across the three commits. `AB_fillet`, `B_rect_closed`
and `T_lshape_bend`'s `corner_breach_m` went from **SKIP to a number** (the
bend branch — the whole point). `S_overhang_gate` moved five values because
its gate is **packed** now (D66): `packed_pieces` 9 → 10, `station_spacing_m`
→ None (no deformed pieces left), and `horizontal_span_m` 1.599998 → **1.6**
with `min_piece_span_m` 1.599998 → **1.600000** — the packed transform does
not round-trip through float32 point positions, so the numbers got *more*
exact. `AK_pentagon/corner_reach_m` moved by 1e-6 because a different (and
now *deterministic*) corner of the pentagon is recorded (D67).

**Decisions taken.**

| # | Ambiguity | Decision |
|---|---|---|
| D51 | §4.5's conform axis is "−Z", and Houdini is Y-up | `Params.conform_axis`, a **direction vector** defaulting to **(0, −1, 0)** — the same Max-to-Houdini translation D20 already makes for the module frame. A direction rather than an axis menu, so a wall-mounted run conforms sideways with the same parm and no new mode; a zero vector degrades to the default rather than casting rays into nothing |
| D52 | Back-facing polygons, and closed solids seen from inside | **Facing is ignored for the HIT and decisive for the NORMAL.** A terrain whose winding is flipped still conforms — warn-never-block does not stop at the artist's winding, and the measurement is that `BF_conform_flipped` and `BG_conform_facing` produce a byte-identical digest. The normal is flipped to oppose the axis before anything tilts by it, because unflipped a back-facing polygon rolls a module **165.96°** — measured, as a mutation |
| D53 | A ray that finds nothing (a hole, an edge, no surface at all) | **Keep the unprojected position and say `pc_warn_conform_miss`** — the tenth warning name. One behaviour for all three ways to miss. Dropping the piece or clamping it to the nearest edge both invent geometry nobody authored; the fence carries on at spline elevation and the warning says where it stopped being draped |
| D54 | How the conform composes with the three Z-modes | **It does not compose — it is a SAMPLER, and the Z-modes are already written against the sampler.** `ConformPath` wraps `place.Path`, so adaptive banks and stretches over the drape, vertical keeps its feet on the ground while staying plumb, and stepped sits flat at its own start elevation, with **no new branch anywhere downstream**. The fit still runs on the SPLINE's arc length: the spline is what the artist laid out and the projection is what the terrain does to it |
| D55 | "per-module optional Y-tilt to the surface normal" — which modules, and who decides | **Camber tilts `adaptive` pieces only**, because a picket that leans with the cross-fall is not plumb and plumb is the mode's definition (D27's precedent, and no warning for the same reason). The switch is `Params.conform_tilt` (off by default — a road wants it, a fence does not) with a per-module `pc_tilt` override in D6's three-state form: −1 = the style decides, 0 = never, 1 = always. The tilt is read **per station** on a deformed piece, so a bent rail rolls along the surface instead of taking one roll from its start |
| D56 | A surface coarser than the pieces | **No new detector.** A piece whose own stations cannot follow the facets under it is exactly D25's condition measured against the conformed path, so `_bend_deviation` already reports `pc_warn_bend_resolution` — the same number, the same name, nothing extra to keep in step |
| D57 | What a SWAP does to the fit | **A swap keeps the fit.** The plan solved a span for the old module and the new one is scaled into that same span — RailClone's own segment-swap behaviour, and the only one that leaves the run intact, because re-solving would move every other piece on the section and make an override a global edit. `pc_elem_id` therefore does not change (D1: the module is not part of the address), which is what lets a swap round-trip |
| D58 | What a REPLACE does to a piece that was deformed | **A replace lands PACKED**, at the transform the piece would have had. Hero geometry is authored to the module's own fit, so bending it round a corner would be inventing a deformation nobody authored. On a piece that WAS deformed it takes the chord's transform and says **`pc_warn_replace_deformed`** — the eleventh warning name. Warn, never block, never silently straighten a bent run |
| D59 | "slice caps polyfilled with box UVs from the module's mapping + cap material tag" | The cap plane is perpendicular to the module's own +X (D20), so the box projection is **(local z, local y)** — no axis choice to get wrong and no seam, a cap being one planar polygon. "From the module's mapping" is a statement about **density**: the texel size is measured off the source's own UV extent versus its geometric extent, so a kit that halves its texel size needs no manifest edit. The tag is `pc_cap_material = "<module>_cap"` on the prim, beside the `pc_cap = 1` that was already there |
| D60 | §3.4's stamp, completed | `pc_curve_id`, `pc_style` and `pc_replaced` join the list. Until they existed, the only way to ask "which curve did this come from" downstream was to **parse `pc_elem_id`** — exactly the string surgery the attribute convention exists to avoid |
| D61 | §4.6's "collate warnings" | A detail array `pc_warnings` of `"name:count"`, alongside the per-element attributes that stay exactly as they were. The per-element ones are the truth; what they could not answer is "did this cook warn, and how much" without walking every prim of a 10k run. `warn_summary` asserts the two agree, because two records of one fact drift |
| D63 | Which override wins when two match | **First match wins, in payload order** — the same rule §3.3 uses for `rules_for`. A narrow `pc_elem_id` rule placed before a broad `pc_module` one is how an artist says "all of these, except that one" |
| D64 | An empty `pc_curve_id` | **A blank id is an ABSENT id**, and it falls through to `edge_id` and then to the prim number (D29's ladder). A Houdini attribute is geometry-wide, so the moment ANY prim upstream carries `pc_curve_id` every other prim carries it too, with the default `""` — reading that as an id gave every unlabelled curve in the stream the SAME id and collapsed their `pc_elem_id`s onto each other. Found by `elem_ids_survive_upstream`, which is the check written for exactly this class of upstream change |
| D65 | Is a SHEAR packable? | **No, deliberately.** A `vertical` piece on a uniform slope is a pure shear — its verticals stay vertical while its ends follow the grade — and 10 of 10 pieces on the conformed ramp fit an affine to float noise, so a packed prim's 4x4 could carry them. They stay unpacked because §4.6's own sentence is "transform × **uniform-or-axis** scale", and because a USD PointInstancer stores an orientation and a scale and **cannot express a shear at all** — packing them would trade a memory win against a substrate citygen §7 has not chosen yet. The count rides in `over_unpacked`'s detail so the size of the prize stays visible |
| D66 | Is an open curve's END vertex an interior kink? | **No.** D30 extrapolates past either end along the end segment's own direction, so nothing bends there — but a piece that legitimately overhangs the end contains that vertex strictly inside its span, and reading it as a kink unpacked the piece for a deformation that does not exist. Measured: `S_overhang_gate`'s gate was real geometry whose points fit a rigid transform to **1e-7 m** |
| D67 | `_reach_of` keyed its dict on `id(bevel)` | **Keyed on the vertex.** `id()` is a memory address, and `corner_reach_m`'s no-expectation branch reports `sorted(...)[0]`, so which corner of a four-corner figure got recorded depended on where Python allocated its `Bevel`s: `AP_narrow_rect` flapped between 0.06 m and 0.08 m across runs of identical code. A baseline value that moves on its own is worse than no baseline value |
| D68 | Cycle 3v's "unreachable" `Bevel.degenerate` | **Not unreachable — `flatten` reaches it**, and it is annotated rather than deleted. `decompose` scores degeneracy on the **3D** tangents and D48's `flatten` re-runs the constructor on the **yaw-flattened** ones, where a 104.837° corner becomes a 178.493° hairpin. That is the only place a plan-hairpin can be caught, and D48 is what made catching it necessary. Its warning also had to be routed: `Bevel.warns` only ever reached an element through `build_assembly`, so a style with no corner module dropped it silently — the vertex is added to `plan_curve`'s degenerate list now, and `_stamp_degenerate`'s inclusive bounds catch the pieces that merely END on it |

**Two open findings, recorded rather than fixed** (both cheap, neither in this
cycle's scope):

1. **A corner assembly in BEND mode is now reachable.** §0.0 has carried "a
   corner module in bend mode — D37 makes it unreachable" since cycle 3;
   D68's flatten route makes it reachable after all, and `build_assembly`'s
   bend branch (one piece centred on the vertex, no duplicate, no cut) then
   runs for the first time. On the repro path
   `(0,0,0) → (8,6,0) → (0.4,12,0.2)` with a `corner_post` and a `vertical`
   default it builds, warns correctly, and leaves a **0.074 m** gap between
   the corner piece and the run — which is §4.4's **deferred flatten-under**
   on a 37° pitch (the same riser PC-G2 shows under every stepped piece), not
   a new defect. The scene case was written and then **pulled**, because
   baselining it would baseline the deferred item; the four-line repro is
   here instead.
2. **A 3D bevel's cut plane is not dropped onto the conform surface.** 4.3
   anchors are dropped (`_drop_anchor`, without which the corner post of a
   conformed fence is the one piece still at spline elevation) but the cut
   PLANE keeps the spline vertex. Harmless while the plane is vertical —
   which D48 guarantees for every yaw-only corner, i.e. every case in the
   suite — and wrong for an `adaptive` corner module on a conformed slope.

---

### Cycle 5 — the cycle-4 review findings, applied (2026-08-22)

Thirteen findings from three independent review lenses (spec conformance,
conform geometry, instancing/determinism), every one demonstrated with numbers
by its reviewer, none of them applied before the session ran out. **All 13
reproduced first and all 13 fixed**; each geometric one is now a standing
scene case. **Suite at the end: 66 scene cases / 3 363 values / 0 failing;
278 unit tests.** New decisions **D69–D74**. No citygen file is touched.

#### The two with the widest blast radius

**A resampled straight line lost instancing entirely (D69).** `_needs_deform`
unpacked on ANY interior curve vertex, and a street handed to this tool is a
resampled polyline. Reproduced: a dead-straight 2 000 m line as two points
builds **1000/1000 packed**; the identical line at 1 m spacing built
**0/1000 packed, 1000 deformed**. `Path` now precomputes the vertices where
the direction actually changes. **PC-G3 re-measured on the shape citygen
authors** — 20 010 collinear vertices, 10 005 pieces: **10 005 packed, one
shared `geometryid`, 10 005 real points, 0.60 s**, against 10 005 deformed /
360 353 points / ~16 s before. That is the difference between the gate being
meaningful and being a statement about two-point splines. `CF_resampled_straight`
is in `ALL_PACKED` so it cannot regress.

**The bend butt-joint allowance used the wrong trig function.** The breach of
a square-ended piece at the bisector is `h·sin(turn/2)`, not `h·cos(turn/2)`;
they agree **only at 90°**, which is the turn every asserted butt case in the
suite happens to make. Measured at four turns on a 4 m + 4 m bend joint: the
physical breach is `h·sin(t/2)` to six decimals every time (0.007765 / 0.015 /
0.021213 / 0.025981 at 30/60/90/120°), and under `cos` a legitimate 120° butt
joint FAILED by **1.10e-02 m** while a 60° one could overrun the vertex by
~0.013 m unnoticed. `AB_fillet`'s own recorded 0.005853 = `0.03·sin(11.25°)`
was the counter-evidence sitting in the baseline. **No baselined value moved**
— at 90° the two are identical — and `CJ_bend_butt_120` now pins a turn where
they are not.

#### 4.5, the four conform findings

* **Topmost, not nearest (D70).** Ground under a bridge deck put six of ten
  pieces on the deck. `BJ_conform_deck` asserts the whole run on the ground.
* **Reach from the surface's bbox alone (D70).** A 5 × 5 m prop 30 m under the
  spline reported `pc_warn_conform_miss` on the whole run. `BK_conform_far`
  pins `conform_misses = 0`.
* **A five-sample gate over a nine-station piece (D71).** A 0.3 m bump between
  the samples shipped a panel packed with the bump **0.400 m** through it.
  `BL_conform_bump` asserts `conform_drape_m` (which scores every station).
* **The same five samples warning about holes (D71).** A hole ON a deform
  station gave a **0.1875 m** V-notch with no warning. `BM_conform_station_hole`
  pins `conform_misses = 1` and the warning.

#### The corner assembly's datum (D72), and what hid it

4.5 dropped each half of a mitered corner on its OWN anchor, so on a ramp the
two cut faces of one post sat **0.02 m** apart (0.28 m with a 1.2 m corner
module). Writing the check the reviewer asked for found a **second** instance
of the same bug with no surface involved at all: on the 20° crest corner the
flattened assembly stepped **0.0583 m** down the leg's 3D line, which is
precisely the defect `flatten`'s docstring claims to have removed. One datum
per assembly fixes both. `corner_mate_axis_m` rides every case, and it exists
because `corner_face_mate_m` structurally cannot see this: its `stepped`
escape drops it to a plan-only metric, and a rigid corner post IS stepped
(D27). `conform_contact_m` also learned that a piece **straddling** the
surface is in contact with it — read unsigned, a post sitting flat at its
datum on a 25 % grade reads as a 0.02 m float.

#### 4.6, the override cascade

A swap re-derives the Z-mode and re-checks the slice (D73): `CI_swap_zmode`
asserts the post's own `stepped` stamp, `CH_swap_tile_slice` asserts the
0.185 m hole is gone (`max_gap_m` 1.19e-07) and that it says
`pc_warn_tile_fallback`. Two curves sharing an authored `pc_curve_id` now warn
(D74) — checked by a control build rather than a scene case, because colliding
ids are the condition under test and every id-keyed check in the suite reads a
merged scene and reports nonsense on it.

#### Baseline movement, all of it explained

* Every `B*` conform digest, and `conform_contact_m` / `conform_drape_m` from
  1e-6–7e-6 **to 0.0**: the ray is cast from the query point now instead of
  from ~14 m away, so the hit is exact instead of carrying float32 error. The
  analytic anchor did NOT move: `BD_camber_off` is still `atan(0.25)` to four
  decimals. `BA`'s `bank_deg` 29.6135 → 29.5063 and `camber_deg` 16.3968 →
  16.3094 are the same cause amplified: the conformed tangent is a finite
  difference over 1e-3 m, so 6e-7 m of position error was ~0.07° of angle.
* `AL_crest_corner` / `AM_graded_corner` digests, and `AM`'s `stepped_riser_m`
  0.04 → 0.029104: D72's datum. The step that was INSIDE one corner post is
  now an ordinary riser between pieces, which is what stepped mode is.
* `BI_conform_corner`'s `stepped_riser_m` 0.029999 → 0.03 — the same, at the
  conformed corner, and now exactly the grade times the post's own reach.

#### Still open, and still named

Both of cycle 4's open findings stand (the reachable bend-mode corner
assembly, and the 3D bevel cut plane that is not dropped), and so do §4.4's
deferred flatten-under and the GUI viewport pass every gate still owes.

**Decisions taken.**

| # | Question | Decision |
|---|---|---|
| D69 | Is a COLLINEAR interior vertex a kink? | **No** — D66's end-vertex lesson, one vertex further in. `Path.interior_vertices` reported every vertex in a span, so a dead-straight run authored at 1 m spacing — **exactly what citygen streets, this tool's first consumer, hands it** — unpacked every piece for a deformation that does not exist. Measured: the same 2 000 m line built **1000/1000 packed** as two points and **0/1000 packed, 1000 deformed** resampled. `Path.kink_s` is precomputed from the adjacent unit tangents at exact-collinearity tolerance (1e-9), which also absorbs a duplicated point for free and leaves the gentle-arc case (2e-4 rad per vertex) unpacking as before |
| D70 | Which surface does a drop land on? | **The NEAREST one along the axis, and a tie goes down-axis** — the ray is cast from the point itself, both ways. It used to start beyond the far side of the surface and take the FIRST hit, which is not "nearest", it is **"topmost"**: with a ground sheet under a run and a bridge-deck sheet over its middle, six of ten pieces sat **on top of the deck**, a 4 m jump with two 3.9 m cliff pieces at its edges, unwarned. The reach is per POINT (`\|p − centre\| + radius`) and not the surface's own bbox: a 5 × 5 m prop under a spline 30 m up used to report a MISS with the surface directly beneath it — the drape flipping on standoff distance alone. Casting from the point is also **more accurate**: the same drops now land on 0.0 exactly where the long ray left 6.4e-7 m of float32 error |
| D71 | How many stations does the conform gate probe? | **The piece's own** (`_Proto.fracs`), not a fixed five. `deviates` GATES a deform that uses exactly those stations, and `missed` warns about a drape that samples exactly those stations, so five fixed probes made both strictly coarser than the thing they describe. Measured: a 0.3 m bump between the probes left a bendable panel PACKED with the bump **0.400 m** through it and no warning; a 0.1 m hole on a station punched a **0.1875 m** V-notch into a rail with `pc_warn_conform_miss` absent — D53's own contract broken exactly where the drape stopped. `ConformPath._cache` dedupes the drops, so the flat case is nearly free |
| D72 | ONE corner assembly, ONE datum | A mitered corner post is one rigid object cut on the bisector, so both halves are placed off the **corner vertex** — dropped once onto the surface, and stepped along the **flattened** tangent when the bevel was flattened. Each half used to take its own anchor: on the suite's 25 % ramp the two cut faces came out y[2.98..4.28] against y[3.00..4.30] (**0.02 m**, and 0.28 m with a 1.2 m corner module), and on the 20° crest corner the flattened assembly shelved by **0.0583 m** — which is the exact defect D48's own docstring says `flatten` removes ("puts both anchors at the vertex elevation"), still there because the code stepped down `tin3`. Both were invisible: `corner_face_mate_m` compares STEPPED pieces in plan only (4.4's deferred flatten-under), so nothing looked along the axis. `corner_mate_axis_m` is the check that does, and it rides every case |
| D73 | What does a SWAP re-derive? | **The Z-mode and the slice**, because both were derived from the module that is no longer there. D6's cascade ran against the old module, so a `panel → post` swap under an empty style zmode built and stamped every post `vertical` — the panel's mode, which on a hillside banks a rail that should sit flat. And the tile remainder kept the gate's `slice_t = 0.125` and cut the RIGID post at 0.125 of ITS 0.12 m, filling 0.015 m of a 0.2 m span: **a silent 0.185 m hole at the end of the fence**. The run cannot be re-solved (D57 — a swap is an exception to a rule, not a global edit), so a non-sliceable swap takes D11's OTHER answer: the whole module scaled into the span it was given, plus `pc_warn_tile_fallback`. Everything else a swap touches is unchanged, so an UNSWAPPED placement stays byte-identical |
| D74 | Two curves authored with ONE `pc_curve_id` | **Warn, never rename.** D1's "collision-free by construction" holds only while the curve half of the address is unique and nothing upstream enforces that — a copy-pasted street prim is how it happens. Measured: 4 prims, **2 distinct ids each stamped twice**, `warn_counts` empty, so an id-keyed override hit both curves and any by-id map downstream dropped half the run. `pc_warn_curve_id_dup` on every element of a repeated id. Renaming was rejected: it would move an address a style or an override may already name, and the point is to make the artist fix the input |

### Cycle 6 - independent verification of cycles 4 and 4b (2026-08-22)

A fresh agent that wrote none of this code. Everything below is a number this
cycle produced, not one it read out of the previous cycle's report.

#### 1. The suites, re-run

```
python -m pytest tests/unit -q
278 passed, 9625 subtests passed in 0.75s

hython tests/polychain/run_scene_checks.py
0 failing checks              (67 cases / 3 363 values, before this cycle's
                               two new cases; 69 / 3 464 after)

hython tests/citygen/run_scene_checks.py
27 failing checks             (pre-existing streets-V1 WIP)
```

Cycle 5's report said "66 scene cases"; the runner prints **67**. Nothing
else in its table was off.

**Baseline movement: none, in either suite.** Both runners print a
`--- moved since baseline ---` block when a value moves and neither printed
one. Cycle 5's own movement was re-derived from `git show 64f3888:...` against
the committed baseline and audited row by row: **8 cases added, 0 removed, 57
values changed in pre-existing cases**, plus `corner_mate_axis_m` added to all
59 and `duplicate_curve_id_warn` to one. Every one of the 57 falls in a bucket
the cycle-5 entry explains - the `B*` conform digests and their
`conform_contact_m`/`conform_drape_m` collapsing to 0.0 (D70's ray now cast
from the query point), `BA`'s `bank_deg`/`camber_deg`, and `AL`/`AM`/`BI`'s
digests and risers (D72's datum). One value sits in a named bucket but was not
named individually: `BC_conform_stepped`'s `stepped_riser_m` 0.067749 ->
0.067747, 2e-6 of the same conform precision. Recorded here so the audit is
complete.

**The citygen 27 cannot be this branch's.** `git diff` from the branch point
`7ce975f` to HEAD over `tests/citygen/`, `polyfactory/vex/`,
`polyfactory/.../citygen*`, `tests/unit/test_citygen.py`, `test_plan.py` and
`trim_calibration.json` is **empty**; the only non-polyChain files this branch
touches are `ideas/*.md`, `tests/README.md` and `graphify-out/`. The failures
are `selfx_city_merged` (14), `selfx_junction_surface` (2),
`plaza_disc_is_clear` (2) and eight singles - all streets-V1 geometry.

#### 2. Mutation testing - ten mutations, TWO SURVIVORS

Each mutation was applied to the tree, the suite run, and the tree restored
with `git checkout --`, with `git diff` verified empty between every pair.

| # | Mutation | Result |
|---|---|---|
| M1 | conform projection axis permuted (-Y -> -Z) | **RED** - 19 checks over 13 conform cases |
| M2 | `_needs_deform`'s `deviates` branch disabled, so a genuinely deformed piece stays packed | **RED** - 5 checks; `BL_conform_bump` `conform_drape_m` **0.5** |
| M3 | swap no longer re-checks the new module's deform class | **RED** - 3 checks; `exact_fill_m` **0.184999943**, the 0.185 m hole back |
| M4 | `cos` restored in the bend breach allowance | **RED** - `CJ_bend_butt_120`, **1.10e-02 m** over the butt wedge |
| M5 | D70's *nearest* comparison cut to a fallback (`back` used only when nothing is below) | **SURVIVOR -> now RED** |
| M6 | D69 reverted - every interior vertex is a kink again | **SURVIVOR -> now RED** |
| M7 | D70's original cast: start beyond the far side, take the first hit | **RED** - `BJ_conform_deck`, `BK_conform_far` |
| M8 | D71 reverted - five fixed probes instead of `_Proto.fracs` | **RED** - 5 checks over `BL`, `BM` |
| M9 | D72 reverted - each corner half drops on its own anchor | **RED** - `BI_conform_corner` **0.02 m** |
| M10 | D72 reverted - a flattened bevel steps down the 3D leg | **RED** - `AL_crest_corner` **0.058298 m**, plus one unit test |

Every number cycle 5 claimed for a repro is reproduced here exactly.

**Survivor M6 - `CF_resampled_straight` cannot see D69.** The case cycle 5
wrote to lock D69 in uses `rigid_kit()`, and `_needs_deform` returns at
`if proto.module.deform <= 0: return False` (D27) **before** the vertex test is
ever consulted. Putting every interior vertex back into `kink_s` left the whole
67-case suite at **0 failures** - while the same revert took PC-G3's resampled
20 km run from 10 005 packed / 0.55 s to **0 packed / 10 005 deformed /
360 180 points / 21.9 s**. Closed by `CG_resampled_bendable`: the same line
with the starter kit's **bendable** panel, in `ALL_PACKED`. M6 now reddens
`packed_pieces` and `over_unpacked`.

**Survivor M5 - nothing ever made D70's *nearest* test run.** `drop` casts
both ways and takes the nearer hit; degrading that to "look up-axis only when
nothing was found down-axis" moved **not one number**. Instrumented: the
up-axis cast wins **12 405 times across the suite and all 12 405 are `nofwd`** -
there was nothing below. `BJ_conform_deck` looks like the case for this and is
not: its deck (+2) and ground (-2) are **equidistant**, so D70's tie-break
decides and the comparison is skipped. Closed by `BN_conform_overhead` - ground
at -3, a deck at +0.4 over the middle, stepped posts - where the middle of the
run must climb **onto** the deck. The assertion is numeric, not a warning:
`stepped_riser_is_m` = **3.4 m** at the deck edge, **0.0** under M5. (Verified
in the build: pieces at x = 6..14 sit at y = 0.5, the rest at -2.9.)

Test-only additions this cycle: `BN_conform_overhead` and
`CG_resampled_bendable` in `cases.py`, `stepped_riser_is` in `checks.py`, and
their wiring plus `ALL_PACKED` in `run_scene_checks.py`. **No production file
was changed.** Re-baselining added exactly those two cases and moved **zero**
values in the other 67.

#### 3. PC-G2 - the hill, on the curving spline the gate actually asks for

The suite conforms straight splines, which cycle 5 flagged as narrower than
PC-G2's wording. Built here: a 24 m spline that **turns in plan** (a +-3.6 m
S-curve) and **climbs 2.4 m**, resampled at 0.25 m, over a 2D terrain
(`1.1 sin(2*pi*x/13) + 0.8 cos(2*pi*z/9) + 0.06x`), conform ON, in all three
Z-modes plus camber. Rendered with cycle 3v's own rasteriser
(`gate_render.py`), not rebuilt - the bridge was not touched.

All four builds pass **50 of 50** suite checks, **0 failures, nothing
baselined**:

| mode | pieces | packed | key numbers |
|---|---|---|---|
| adaptive | 14 | 0 | `bank_deg` **27.15**, `conform_contact_m` **0.0**, `conform_drape_m` 1e-6 |
| vertical | 14 | 0 | `plumb_deg` **0.0** over 14 pieces, `conform_contact_m` **0.0** |
| stepped | 240 | **240** | `flat_stepped_m` **0.0** over 240, `stepped_riser_m` **0.06128** |
| camber ON | 14 | 0 | `camber_deg` **17.20** against **37.31** with tilt off |

`inward_faces` 0, `conform_misses` 0, `over_unpacked` 0 and no warnings in any
of the four.

**What the images show** (`VG2P_{vertical,stepped,adaptive}.png`,
`VG2C_camber_cu.png` in the scratchpad, terrain drawn as an unoccluded ground
line so nothing hides behind the hillside):

* **vertical** - every one of the panel's eight division ribs is dead vertical
  across the whole S-shaped drape, while the run's lower edge tracks the ground
  line at a constant offset. That offset is the panel module's own 0.10 m base
  inset (`box_mesh(..., 0.10, 1.00, ...)`), not a gap.
* **adaptive** - the same ribs **lean**, perpendicular to the local drape. Set
  beside the vertical shot that is the whole difference between the modes,
  visible without measuring anything.
* **stepped** - every post's base sits **on** the ground line and the tops make
  a clean sawtooth. The posts' sides stay parallel: flat, not banked.
* **camber ON**, looking down the run - the rail's cross-section is visibly
  **rolled** onto the cross-fall rather than standing upright.

WARNING: **the riser gap under each stepped piece is there, and it is
expected.** 4.4's flatten-under is deliberately not built, so a 0.12 m post
standing flat on a sloping ground line leaves a wedge under its downhill half.
On this hill it measures **0.061 m** (`stepped_riser_m`). Saying so plainly:
this is a known deferred item, not a PC-G2 failure, and it is the same thing
`AM_graded_corner` and `BI_conform_corner` record in the suite.

Still owed on PC-G2: the **GUI viewport pass**. The bridge is wedged and was
not touched.

#### 4. PC-G3 - instancing at scale, re-measured with memory

20 km, 10 005 x 2 m **bendable** panels (the module class D69 actually
governs). RSS via `GetProcessMemoryInfo`, geometry held live.

| spline | packed | deformed | real points | `geometryid`s | dRSS | cook |
|---|---|---|---|---|---|---|
| straight, 2 points | **10 005** | 0 | 10 005 | **1** | +12.1 MB | **0.42 s** |
| straight, **resampled 1 m** (20 011 verts) | **10 005** | 0 | 10 005 | **1** | +12.1 MB | **0.55 s** |
| straight resampled, rigid module | 10 005 | 0 | 10 005 | 1 | - | 0.52 s |
| **R = 12 km arc, resampled 1 m** | 727 | **9 278** | **334 735** | 1 | **+129.8 MB** | **18.88 s** |

**PC-G3 PASSES on the run it was written for, and the resampled straight line -
the citygen-streets shape - is genuinely identical to the two-point one.** That
is cycle 5's headline claim, independently reproduced. Reverting D69 takes the
resampled row to 0 packed / 10 005 deformed / 360 180 points / 21.93 s, so the
fix is load-bearing.

WARNING: **and the gate is narrower than the headline.** The bottom row is the
same tool on a curve so gentle it is invisible: a 2 m piece on R = 12 km has a
sagitta of **4.2e-05 m**. `_needs_deform` unpacks on the *presence* of a kink,
never its *size*, so 9 278 pieces are rebuilt to move points by 42 microns -
**10.7x the memory and 34x the cook time**. Swept over radii at 1 m resampling,
300 m of run, 150 pieces:

| R | turn / vertex | packed | worst real deform | `over_unpacked` |
|---|---|---|---|---|
| 12 000 m | 8.3e-05 rad | 0 / 150 | below 1e-4 m | **FAILS, 8 pieces** |
| 2 000 m | 5.0e-04 rad | 0 / 150 | 0.0001 m | passes |
| 400 m | 2.5e-03 rad | 0 / 150 | 0.0007 m | passes |
| 80 m | 1.3e-02 rad | 0 / 150 | 0.0035 m | passes |

Every one of those deformations is **under `bend_tol` (0.01 m)**, and at
R = 12 km the 4.6 guard `over_unpacked` - "nothing unpacks that did not have to"
- **fails**. D69's text names the trade-off ("the tolerance is
exact-collinearity, not a curvature budget... which is what keeps every
baseline still"); what it does not record is that the tool's own invariant is
violated by it, or what it costs at scale. Carried as standing open finding (1)
in 0.0 and not patched here: a curvature budget moves baselines and is a
decision, and this was a verification pass, not an implementation one.

#### 5. What this cycle did NOT verify

* The **GUI viewport pass** every gate owes. The bridge was not touched.
* PC-G4 and 5, which are unbuilt.
* Whether the citygen 27 are individually correct - only that this branch
  cannot have caused them.

---

### Cycle 7 — the curvature budget, §3.3's reader, §5's parm face, and the kit (2026-08-22)

Four items, each committed on its own. Everything below was run headlessly on
`hython 22.0.398`; nothing touched the wedged live bridge.

#### 1. D75 — THE CURVATURE BUDGET (cycle 6's standing open finding (1), closed)

`_needs_deform` unpacked on the **presence** of an interior vertex. It now
spends a budget on its **size**: `place.span_deviation(path, sa, sb)` measures
how far the deformed piece would sit from the packed one, at the span's own
interior vertices — which on a polyline is the exact answer, not a sample —
and the piece stays packed while that is under `bend_tol`.

`hython tests/polychain/scale_gate.py` (new, and the home PC-G3's numbers have
been re-derived from scratch in three separate cycles for want of), 20 km of
2 m bendable panels per row, RSS via `GetProcessMemoryInfo`:

```
case            sagitta   packed  deformed    points  gids  seconds  dRSS MB
two_point             -    10000         0     10000     1    0.429     15.2
resampled             -    10000         0     10000     1    0.566      9.6
arc_12000      4.17e-05    10000         0     10000     1    0.598      5.1
arc_2000       2.50e-04    10000         0     10000     1    0.607      5.1
arc_80         6.25e-03    10000         0     10000     1    0.599      4.1
arc_10         5.00e-02        0      9996    359856     0   10.834    168.4
```

Against cycle 6's measurement of the same R = 12 km arc — **727 packed / 9 278
deformed / 334 735 points / +129.8 MB / 18.88 s** — the budget buys **10 000
packed / 10 000 points / +5.1 MB / 0.60 s**, i.e. the resampled-arc row now
matches the straight one. `over_unpacked`, which FAILED on that row, passes.
R = 10 m (sagitta 5.0e-02 m, five times the budget) still bends all 10 000,
which is what keeps the budget from being vacuous.

⚠️ **And the bisect is half the win.** Once the arcs stayed packed the cook was
still 9.4 s: `interior_vertices` scanned the whole kink list per piece, which
is quadratic in the vertex count and had been hidden by the deform cost it sat
behind. `kink_s` is sorted, so it bisects — **9.43 s → 0.60 s**, and the R = 10
control that legitimately deforms went 21.8 s → 10.8 s with it.

**Four new scene cases** on a radius ladder (`CK_arc_12000`, `CL_arc_2000`,
`CM_arc_80`, all asserted 100 % packed; `CN_arc_tight` asserted 0 % packed) and
a new check, **`curvature_budget_m`**, riding all 73 cases: `[worst spent by a
packed piece, worst over all pieces]`, failing if a packed piece is over
`bend_tol`. `axis_on_curve_m` now holds a **packed** bendable piece to
`bend_tol` and a **deformed** one to `TOL_M`, which is the same budget stated
from the other side. **Zero baseline movement on the 69 cases that existed.**

Mutations, both red: budget always exceeded → 51 failures (`over_unpacked` on
12 cases); budget never exceeded → 23 failures, including `axis_on_curve_m`
0.196 m on `B_rect_closed` and `curvature_budget_m` on `CN_arc_tight`.

#### 2. §3.3 — the style-payload reader (`polychain/style.py`)

The missing half of §2.1. `read(geo, kit)` → `(Style, warnings)`,
`write(geo, style)` → the payload. **One generic loop over whatever rules
arrive**; the reader contains no style name and no branch per name, which is
citygen's foundation rule and what PC-G4 audits. `pc_cond` is read as the
`{subject, op, value}` dict `plan.evaluate_cond` already takes and only
*validated* here — no second evaluator.

Two standing checks: **`style_round_trip`** rides every case (the parm-face
`Style` written as a payload, read back, rebuilt — byte-identical ids and
positions, or it fails) and **`style_payload_degrades`** pins a six-fault
payload at **4 rules kept / 14 warnings / 167 elements**. Mutations: payload
drops its params → 34 failures; module order sorted on write → 2.

#### 3. §5 — the parm face, `pf_polychain`

`devScripts/create_pf_polychain_hda.py` (force-added; `devScripts/` is
gitignored) builds `polyfactory/otls/pf_polychain.hda`: a subnet, one Python
SOP, and `polychain/hda.py`, where the work lives so it can be committed and
tested. Four inputs per §2.2. Two disclosure levels exactly — main page +
one Advanced folder — and every parm has a range, a unit in its label and a
help string.

`hython tests/polychain/run_hda_checks.py` — **16 checks, 0 failing**:

* **defaults alone build a fence** — one curve, no kit, no style, no surface:
  137 elements, 35 packed, `post` + `panel` from the built-in starter kit, and
  `corner_post` appearing when corner mode is miter;
* the node's output is **identical to `place.build`** on the same style;
* input 2 is the kit (a renamed module comes through), input 4 is the surface
  (the run drops to y = −2.5);
* **PC-G4** — a payload on input 3 replaces the modules, the styleId and the
  ids, matches the kernel built from the `Style` object directly, and **the
  parms are inert while it is wired** (`fill` and `seed` moved on the node,
  nothing moved in the output);
* **the proxy LOD, at 10 000 pieces**: on a curving run **0.648 s / 10 000
  points** against **10.966 s / 360 000 points** — §5's acceptance criterion,
  met and measured;
* warn-never-block on the wiring: no spline warns, a missing kit file falls
  back to the starter kit and warns. ⚠️ The warnings live on the INNER Python
  SOP; `hou.Node.warnings()` on the asset does not aggregate them.

#### 4. §6 — the starter kit, and one thing measured and reverted

The kit is `post / panel / picket_panel / corner_post / gate`, built by
`kit.starter_kit()` and now reached automatically when input 2 is unwired —
which is what makes the HDA usable with nothing but a curve. Judged on
`D_default_fence.png` and `D_default_bay.png` (scratchpad): posts standing
proud of a continuous run, closing at the L, panels flush with the end posts.

⚠️ **The picket panel was made the DEFAULT first, and reverted** (D86). It
looks better — the solid panel reads as a grey wall with an occasional post in
it — and it took `corner_face_mate_m` from 0.0424 m to **0.1849 m** on
`V_rect_miter`, because the bisector plane cut through a gap between two slats
and there was no face there to mate with. A module with voids along its span
cannot close a mitered corner, and PC-G1's corner gate is measured on this
module. It ships as `picket_panel` on the same 0.25 m station ladder, one menu
pick away (`D_railing_bay.png`); making it the default is a cycle of
re-derived corner expectations, not a patch.

`module_winding` now judges each face against **its own connected shell**: a
multi-box module scored 19 of 122 faces inward while being perfectly correct.
It also fails on faces it cannot judge at all, because the first mutation
SURVIVED on an unwelded mesh where every face was its own component and every
dot product was zero. Re-mutated welded: 92 of 156 inward, red.

#### Decisions taken

| # | Decision |
|---|---|
| D75 | **The curvature budget.** A piece stays packed while `span_deviation` — the distance between where the deformed piece would put a point and where the packed one does, measured at the span's own interior vertices — is under `bend_tol`. The vertex test was binary, and on a curve too gentle to see it cost 10.7x the memory and 31x the cook. `interior_vertices` bisects its sorted kink list, which is the other half of the win |
| D76 | `pc_modules` is a **space-separated string**, matching `pc_role` in the kit manifest. A string ARRAY is accepted on read (a generator upstream may prefer it) and never written |
| D77 | A payload **overrides the parms entirely** (§2.1's own words): keys it omits take the KERNEL default, not the node's. Merging would make one payload build two different fences on two nodes, which is the property the pipeline face exists to guarantee |
| D78 | **A malformed rule degrades, it does not disappear silently.** Unknown select → `first`; empty module list → the slot's own role; unknown module → §3.4's stand-in box. Only a rule with no usable slot is dropped, because a slot nothing reads cannot degrade into anything. Every case is named in a warning |
| D79 | The conditional is **not re-implemented** in the reader. `pc_cond` is validated here and evaluated by `plan.evaluate_cond`; unknown subject and unknown op are exactly the two inputs that make that evaluator decline every piece, so both warn |
| D80 | **Every parm that is a kernel parameter is named after it** (`fill`, `bend_tol`, `conform_axis`…), so the parm → `Params` mapping is a loop over `Params`' own fields and not a table to edit twice. The LABEL is the artist's face and is free to be prose |
| D81 | **The plan is a display mode, not a second output.** One output plus `display` = full / proxy / plan gives §4.2's inspectable plan and §5's preview-while-dragging without a second wire to explain |
| D82 | **The proxy LOD is a proxy KIT, not a second code path.** Every module becomes a rigid box at its nominal size and the unchanged kernel runs on it — rigid short-circuits the deform gate at D27, so the proxy is the same plan, the same corners and the same transforms, at one box per module |
| D83 | **Instancing override = `bend_tol`.** §5 asks for instancing overrides; D75 already made the packed/deformed split a budget in metres, so exposing that number IS the override. A second toggle beside it would be two controls for one decision |
| D84 | **Padding is a kit edit.** The `padding` parm adds metres to every module's own `pc_pad` on a COPY of the kit, so one artist-facing "Gap between pieces" rides §4.2's existing mechanism instead of adding a kernel field |
| D85 | **A conditional rule is payload-only.** No sane parameter page authors a `{subject, op, value}` dict; the parm face offers first / in turn / random and the pipeline face carries conditionals. That is §2.1 working as designed, not a gap |
| D86 | **The default panel stays solid**, measured rather than preferred: a module with voids cannot mate at a mitered corner (0.0424 → 0.1849 m). The picket panel ships beside it as `picket_panel` |


### Cycle 8 — the three-reviewer pass over cycle 7, worked through (2026-08-22)

Thirteen findings from three independent reviewers (spec/two-face, artist UX,
curvature/determinism). Every one reproduced first. **Twelve confirmed and
fixed; one pair was two reviewers describing the same defect.** All headless on
`hython 22.0.398`; the live bridge was not touched.

#### 1. D87 — the curvature budget was measured on the SPINE (the ship-wrong one)

The worst finding, and the direction that ships visibly wrong geometry.
`span_deviation` measured how far the deformed piece's **spine** would sit
from the packed chord — exact for a point at `y = z = 0` and an under-count
for every other point in the module, because `_deform_positions` rebuilds a
frame **per station** while `_packed_transform` builds one from the chord.

Reproduced: a **1.2 m tall bendable rail, `adaptive`, on an R = 55 m arc that
CLIMBS**, resampled at 1 m.

| radius | spine reading | TRUE worst point | packed |
|---|---|---|---|
| R = 50 | 0.0100 | **0.0360** (3.6×) | 14 / 15 |
| R = 55 | 0.0091 | **0.0327** (3.3×) | **15 / 15** |
| R = 80 | 0.0062 | **0.0225** (2.3×) | 15 / 15 |
| R = 120 | 0.0042 | **0.0150** (1.5×) | 15 / 15 |
| R = 200 | 0.0025 | 0.0090 | 15 / 15 |

Anatomy of the R = 55 reading, measured rather than modelled: the worst point
is the module's **far top corner** `(2.0, 1.2, −0.03)`, its spine offset there
is **0.0**, and the whole 0.03273 m is `2·r·sin(θ/2)` with `r = 1.2004` and
`θ = 0.027273 rad` — the angle between the chord and the **forward** tangent
at the piece's last station, which at a piece boundary is the NEXT segment's.
`_Proto` now measures `ry` / `rz` / `radius` off the module's own bounding box
and `span_deviation` takes a radius: the spine term at every kink, plus the
rotation chord at start / kinks / end, paired so each frame rides the larger
spine offset of the interval it holds over. `_needs_deform` passes
`proto.radius` for `adaptive` and `proto.rz` for the yaw-only modes, because
`_frame` keeps `y` world-vertical there.

**PC-G3 is unharmed** — `scale_gate.py` still reads 10 000 packed / 0 deformed
/ 10 000 points / ~0.65 s on R = 12 000 / 2 000 / 80, and R = 10 still bends
all of them at 11.0 s.

New standing check **`packed_true_dev_m`**, on all 76 cases: it never calls the
budget, it BUILDS both answers per packed piece (the packed 4×4 on the module
vs. what `_deform_positions` would have produced) and fails if the distance
exceeds `bend_tol`. Two new cases: **`CP_elev_arc_tall`** (asserted 0 % packed)
and **`CQ_plan_arc_tall`** (the same rail on a plan arc, asserted 100 % packed
— without it the fix could just unpack everything and pass).

Mutation (radius forced to 0): **5 red**, and three of them are pre-existing
defects this closed — `AS_rect_bend_butt` **0.0424 m**, `T_lshape_bend`
**0.0424 m**, `CJ_bend_butt_120` **0.060 m** on pieces that had been staying
packed at a bend corner.

**Baseline movement, and why it is an improvement:** exactly the three bend-
corner cases. Four pieces on `AS`, one on `CJ`, one on `T` now deform, and
`corner_wedge_m2` falls **0.0009 → 0.000193** (AS), **0.00156 → 0.00118** (CJ),
**0.0009 → 0.000195** (T). A deformed piece that ends at the corner takes the
next leg's frame at its final station — and so does the piece that starts
there — so the butt joint closes instead of leaving a wedge. `frame_dot_min`
reads 0.0 on `AS` (a 90° corner) and 0.5 on `CJ` (120°), which is that turn,
inside the check's own −0.866 limit. This is standing open finding (2)
— the bend-corner gap — getting materially smaller, not merely moved.

#### 2. D91 — the Gap parm was live under a wired style payload

Reproduced: 12 m spline, payload on input 3, parms at defaults → 6 prims; set
`padding` to 0.8 → **5 prims, different ids, different positions**. One payload
built two different fences on two nodes, which is the exact property D77 says
the pipeline face exists to guarantee. `_padded` now runs only on the parm-face
arm. It escaped because `parms_inert_under_payload` moved **two** parms and
compared sorted ids only.

**The check is now a sweep**: every parm on the page is nudged in turn while
the payload is wired, and both the ids and the rounded point positions must be
unchanged — `swept 36 parms; moved: none`. Exempt by name and by reason:
`display`, `show_warnings` (viewing decisions, D81/D82) and `kitfile` (the KIT
lane; a payload carries rules and params, never a kit).

#### 3. D94 — `attr:<name>` read exactly two names

§3.3 says the subject "reads any spline prim attr"; the adapter never
harvested prim attributes and `plan_section` hardcoded `pc_section` /
`pc_style`. Reproduced: a 12 m spline whose prim carries `road_width = 9.0`
with an `attr:road_width gt 1.0` conditional → **every piece `panel`**, no
warning. This is the first consumer's own hook (streets selecting off edge
data) declining everything in silence.

`read_curves` harvests the prim's non-`pc_` attributes into `Curve.attrs`,
`decompose` carries them onto `Section` (and the corner weld keeps them), and
`plan`/`corner` merge them under the kernel's own two. The repro now builds
`gate`. One unit test and one scene case, **`CR_attr_conditional`** — two
curves in one stream, `road_width` 9.0 and 0.5, one rule, asserted
`CRa=gate, CRb=panel` by the new **`modules_by_curve`** check. Mutation
(`attrs=None`): red, `CRa=panel`.

#### 4. D88 — the marker slot was unreachable from the parm face

PC-G1's own bullet is "a gate placed by a marker", and `SLOT_PARMS` was a
fixed five-slot list, so it was payload-only *and* undecided. Two parms —
**Piece at Markers** and **Marker Id** — join the same loop (`marker:%d` is
just a slot whose name carries a number), and markers that arrive with no rule
to read them now **warn**, in either face. Asserted headlessly: the unread
marker warns, setting the pair builds **1 gate element at the marker**, and the
warning stops once a rule reads it.

#### 5. The rest, each reproduced and each closed

* **D89** — `style_from_parms` read a `scope` parm the page never had. Passes
  `"segment"` literally now, with the reason on the line; per-scope randomness
  is payload-only, D85's pattern.
* **D92** — a payload whose rules ALL dropped made `read` return `None`, so
  `cook` silently swapped to the PARM face: a convincing fence with parm ids
  and the parm `styleId`, matching nothing a downstream override map is keyed
  on. It now degrades WITHIN the pipeline face (payload meta, empty rule list),
  the "no modules assigned" warning fires, and the node builds **0 prims**.
* **D93** — `marker:gate` (a name where an id belongs) validated clean and
  placed nothing. The suffix is parsed with `int()` now; the rule is kept
  (warn-never-block) and named.
* **Units in labels** — seven numeric parms carried their unit only in hover
  help while the script's own header claimed otherwise. Verified on the built
  asset: `Gap Between Pieces (m)`, `Evenly Spacing (m)`, `Corner Rounding (m)`,
  `Adjust to End (m)`, `Bend Tolerance (m)`, `Corner Angle (deg)`, `Narrow
  Corner Angle (deg)`.
* **The slot menus** — `StringReplace` overwrote the whole space-separated
  field, so an artist with `post panel` who picked a module off the menu lost
  the rhythm and could never build a pattern from the menu at all; and the menu
  listed `post` twice (module and role, identical token). Now
  **`StringToggle`** (Houdini's own append/remove list menu) and de-duplicated:
  verified **11 items, 0 duplicate tokens** (was 14 with 2).
* **D90** — the drag-time LOD switch is MANUAL and nothing said so. Measured
  on the built asset: a 20 km R = 40 m run of 10 000 panels cooks **11.0 s** at
  `display = full` and **0.66 s** at `proxy`. A `full` cook over 2 s now warns
  *"this build took 10.9 s - set Display to 'Proxy Boxes' while dragging"*, and
  the proxy cook is silent.
* **D95** — the kit **gallery** front door (§5's first bullet) is deferred, on
  the record rather than by omission: one kit needs no browser. The `kitfile`
  field is the interim picker; the gallery arrives with a kit corpus.
* **Dead code** — `assert hdr` in `scale_gate.py` sat after an unconditional
  `sys.exit`; removed, and `hdr` with it (nothing else read it).

#### Final state

`python tests/unit/test_polychain.py` **54 OK** · `test_polychain_plan.py`
**91 OK** · `hython tests/polychain/run_scene_checks.py` **76 cases, 0
failing** · `run_hda_checks.py` **22 checks, 0 failing** ·
`scale_gate.py` **0 failing rows**. Three mutations run, all three red.

#### Decisions taken

| # | Decision |
|---|---|
| D87 | **The curvature budget is spent by the piece's WORST POINT, not by its spine.** `span_deviation` takes the module's off-spine radius (measured off its own bbox: `radius` for `adaptive`, `rz` for the yaw-only modes) and adds `2·r·sin(θ/2)` for the frame's turn, paired with the spine offset of the interval each frame holds over. D75's spine-only measure kept a 1.2 m rail packed at 0.0091 m while its top corner had moved 0.0327 m |
| D88 | **A marker slot is NOT payload-only** (D85's sibling, answered the other way). `marker:<id>` is a slot whose name carries a number, so an int parm and a module field put PC-G1's gate on the page inside the same `SLOT_PARMS` loop. Markers that arrive with no rule to read them WARN — in either face |
| D89 | **The randomness scope is payload-only.** The `scope` read pointed at a parm the page never had; `segment` is passed literally now |
| D90 | **The drag-time LOD switch is manual, and the node says so.** A Python SOP cannot see a drag, so D81/D82's menu is the answer; what was missing was the pointer to it. A `full` cook over 2 s warns and names the proxy |
| D91 | **Padding is a PARM-FACE control** (amends D84; D77 is why). Applying it under a wired payload made one payload build two fences. The pipeline face pads with the kit's own `pc_pad` |
| D92 | **A payload that loses every rule degrades WITHIN the pipeline face.** A wired input that lost its rules is not an unwired one: it keeps its own styleId, seed and params with an empty rule list, so the node builds nothing and says so instead of quietly becoming the parm face |
| D93 | **A marker slot's id is parsed, not just prefix-matched.** `marker:gate` is kept and named rather than validating clean and placing nothing |
| D94 | **`attr:<name>` reads the spline prim's OWN attributes**, as §3.3 always said. They are harvested by the adapter, carried on `Section` through the corner weld, and merged under the kernel's own `pc_section`/`pc_style` |
| D95 | **The kit gallery front door is deferred** until a kit corpus beyond the starter kit exists — one kit needs no browser. `kitfile` is the interim picker; recorded so the deviation from §5 is a decision rather than an omission |

### Cycle 9 — independent verification of cycle 8 (2026-08-22)

A fresh agent that wrote none of cycle 8, told to trust nothing and measure
everything. Everything below is a number this cycle produced, not a number it
read. **Two survivors were found and both are now closed**, and the gate
figures were rebuilt for the first time through the HDA's parameter page
rather than through `place.build`.

#### 1. The suite, re-run from clean

| Runner | Result |
|---|---|
| `python -m pytest tests/unit -q` | **279 passed, 9 625 subtests** in 0.77 s |
| `hython tests/polychain/run_scene_checks.py` | **76 cases, 0 failing checks** |
| `hython tests/polychain/run_hda_checks.py` | **0 failing checks** |
| `hython tests/polychain/scale_gate.py` | **0 failing rows** |

**No baseline movement**: `git status` was clean after every scene run, so
`tests/polychain/baseline.json` was not rewritten by any of them.
**citygen is untouched** — `git diff` over `tests/citygen/`,
`tests/unit/test_citygen.py`, `tests/unit/test_plan.py`,
`polyfactory/scripts/python/polyfactory/citygen/` and `pf_citygen_*.hda`
across the whole branch (`git merge-base HEAD cityGen`..HEAD) is **empty**.

#### 2. Mutation testing — four mutations, one survivor

| Mutation | Where | Result |
|---|---|---|
| Curvature budget widened 50x | `place._needs_deform`, `> tol` becomes `> tol * 50` | **RED — 29 failing checks.** `curvature_budget_m` and `packed_true_dev_m` fire on 8 cases; `CN_arc_tight` and `CP_elev_arc_tall` flip to 100 % packed against their asserted 0 %; `axis_on_curve_m` reads 0.196 m and 0.349 m |
| Payload silently ignored | `hda.cook`, `style = None` after `style.read` | **RED — 5 failing checks**, including `parms_inert_under_payload` naming the six parms that came back to life (`corner_mode, fillet_radius, padding, slot_default, style_id, variety`) |
| `pc_cond` subject dispatch broken | `plan.cond_subject`, the `attr:` branch deleted | **RED** — 2 unit tests plus the scene check `modules_by_curve` (`CRa=panel` where `gate` was expected) |
| **Help text, ranges and unit suffixes stripped from every float parm** | `create_pf_polychain_hda._float` | **SURVIVED.** 9 parms lost their help, their range and their `(m)`/`(deg)`/`(%)` suffix, the asset was rebuilt, and **279 unit tests, 76 scene cases and 22 HDA checks all stayed green** |

That survivor is the finding: `artist_ui.md` §6 is called **binding law** at the
top of the builder and **nothing enforced a word of it**. Cycle 8's own UX
items (units in seven labels, the `StringToggle` menus) were verified by a
human reading the printed list once — which is exactly the kind of check that
rots. Closed by **D96**.

#### 3. Gate PC-G4 — re-measured in the spec's own wording, PASSES

The existing check proves a payload *overrides* the parms. §2.1's sentence is
stronger — *the same fence*, driven entirely by a payload, parms at defaults —
so that was measured directly: the parm face's own `Style` written out through
`style.write`, wired into input 3 of a second node, and the two nodes compared
on **element ids, module names, rounded point positions and every packed
prim's full transform**.

| fill | corner | parm face | payload | identical |
|---|---|---|---|---|
| adaptive | miter / bend | 80 / 137 prims | 80 / 137 | **yes / yes** |
| scale | miter / bend | 48 / 35 | 48 / 35 | **yes / yes** |
| evenly | miter / bend | 80 / 137 | 80 / 137 | **yes / yes** |
| count | miter / bend | 48 / 35 | 48 / 35 | **yes / yes** |

Then the whole page swept under the wired payload: **32 parms nudged, 0 moved
the geometry** (exempting `display`/`show_warnings`/`kitfile` by name). And a
style the code has never heard of — `styleId = a_style_nobody_wrote_code_for`,
carrying a `marker:42` slot — built **52 prims, 4 modules, 0 warnings**, with
no code change anywhere.

**The generic-loop rule holds.** `grep` over the whole kernel for a style name
in a conditional returns **nothing**: the only occurrence of a style
identifier is `style_from_parms`' default value `"pf_polychain"`, which is a
default, not a branch. The names that *do* appear in conditionals are `corner`,
`default`, `start` and `end` — §3.3's own fixed slot vocabulary, the kernel's
schema rather than any style's — and a slot outside it (`marker:42`) is
dispatched generically, as the run above proves.

#### 4. PC-G3 re-measured after D87 — and its terms are narrower than stated

Re-run at 10 000 pieces over 20 km, straight and on arcs:

| case | zmode | packed | deformed | points | gids | seconds | dRSS |
|---|---|---|---|---|---|---|---|
| two-point straight | kit (`vertical`) | 10 000 | 0 | 10 000 | 1 | 0.47 s | +15.6 MB |
| resampled straight (20 011 verts) | kit | 10 000 | 0 | 10 000 | 1 | 0.62 s | +9.4 MB |
| R = 12 000 m | kit | 10 000 | 0 | 10 000 | 1 | 0.65 s | +6.0 MB |
| R = 2 000 m | kit | 10 000 | 0 | 10 000 | 1 | 0.66 s | +5.2 MB |
| R = 80 m | kit | 10 000 | 0 | 10 000 | 1 | 0.66 s | +4.0 MB |
| R = 10 m | kit | 0 | 9 996 | 359 856 | 0 | 10.92 s | +158.8 MB |
| R = 12 000 m | **adaptive** | 10 000 | 0 | 10 000 | 1 | 0.60 s | +2.1 MB |
| R = 2 000 m | **adaptive** | 10 000 | 0 | 10 000 | 1 | 0.61 s | +3.0 MB |
| **R = 80 m** | **adaptive** | **0** | **10 000** | **360 000** | 0 | **10.98 s** | +34.7 MB |

**The `arc_80` row was passing for a reason nobody had written down.** The
starter kit's `panel` carries `pc_zmode = vertical`, and a yaw-only mode spends
the curvature budget on the module's Z reach alone (`_needs_deform` passes
`proto.rz` = 0.03 m). D87's off-spine term was therefore switched almost all
the way off in every row of the ladder — and `scale_gate.py` still decided
pass/fail from `4/(8R)`, **the spine sagitta D87 replaced**. Under `adaptive`,
where the panel's full 0.90 m height rides the frame, R = 80 m moves the top
edge `0.90 x 0.025 = 0.0225 m`, **2.25x `bend_tol`**, and unpacking all 10 000
is correct. This is D87 working, not a regression — but the gate's own harness
could not see the term the budget now spends. Closed by **D97**.

Separately measured and **not** a defect: a run that *climbs* deforms under
the starter panel at any radius (R = 12 000 m included) because `vertical` is a
pure shear on a slope — that is D65, standing open finding (3), reconfirmed
rather than newly found.

#### 5. PC-G1 and PC-G2 rebuilt through the PARM FACE and looked at

Both gates were image-verified before the parm face existed, and PC-G1
explicitly still owed *"the parm face + style payload"*. Cycle 3v's rasteriser
was reused unchanged; what is new is the **source**: a cooked `pf_polychain`
node with its parameters set and its inputs wired, never `place.build`.
Images in the scratchpad: `HC_{miter,bend}_{top,iso}.png`,
`HG1_rect_{bend,miter}_{wide,corner}.png`, `HG1_L_{bend,miter}.png`,
`HG1_fillmodes.png`, `HG1_gate_marker.png`, `HG2_{vertical,stepped,adaptive}.png`,
`HG2_camber_{off,on}.png`, `HG2_run_wide.png`.

**What the images show.** *Miter, plan and iso:* the two legs of the 12 x 8 m
rectangle terminate into a corner post standing on the elbow, tops flush at one
height, and the 45° bisector cut is visible as a clean diagonal across the
corner assembly — no gap, no overlap. *Bend, plan and iso:* no corner post at
all (D36's ring weld), the panel turns through the elbow as one continuous top
arris, and the only interruption is the small notch at the outer corner that is
the accepted butt wedge. *Fill modes:* four runs of a 12.3 m spline with
visibly different piece rhythms, every one closing flush at both ends on the
spline. *Gate on a marker, authored on the page* (`Piece at Markers = gate`,
`Marker Id = 1`, no payload anywhere): the wider gate module sits mid-run
between two posts, measured at **x 7.200000 … 8.800000, centre 8.000000, error
1.788e-07 m** against `pc_dist = 8.0`; before the two parms were filled the
node warned *"input 1 carries markers with id 1 and no rule reads them"*.
*PC-G2 vertical:* every rib between pickets is dead plumb while the run's foot
tracks the terrain line. *Stepped:* the posts stand plumb with their feet on
the ground line and their tops stepping over it. *Adaptive:* the same run with
the ribs visibly raked perpendicular to the drape — the difference between the
two images is the mode doing what its label says. *Camber off to on:* the rail
rolls onto the cross-fall, the panel faces swinging from edge-on to fully lit.
*Whole run:* 24 m of S-curve climbing 2.4 m reads as a fence on a hill, foot on
the ground the whole way.

**GUI viewport pass is still owed on both** — the live bridge was not touched
this cycle either.

#### 6. What changed in the tree

* `tests/polychain/run_hda_checks.py` — new section 8, `artist_ui` §6 asserted
  on the built asset (**D96**): `every_parm_has_help` (33 parms, 0 without),
  `two_disclosure_levels` (depth 1, one `Advanced` folder),
  `every_number_has_a_range` (15 numerics, 0 left at `hou`'s untouched 0..10),
  `units_in_the_label` (9 united parms, 0 missing their suffix). Re-running the
  stripping mutation against it now gives **3 failing checks**.
* `devScripts/create_pf_polychain_hda.py` — `fillet_radius` range **0..10 m to
  0..5 m**. The check above found it on its first run: 0..10 is also `hou`'s
  default on every numeric template, so a deliberate 0..10 and a parm that
  never got a range are indistinguishable. 5 m is the better slider anyway —
  10 m of rounding swallows a whole leg of PC-G1's own rectangle — and the
  slider is soft, so a larger number is still typeable.
* `tests/polychain/scale_gate.py` — **D97**: the ladder carries its own
  expectation per row with the reason on the line, instead of deriving one from
  the retired spine formula, and runs three extra rows under `zmode=adaptive`.
  9 rows, 0 failing. Mutating the budget 50x now fails **2 rows**
  (`arc_10/kit` and `arc_80/adaptive`) where it failed none before.

#### Final state

`python -m pytest tests/unit -q` **279 passed** · `run_scene_checks.py`
**76 cases, 0 failing** · `run_hda_checks.py` **0 failing** (26 checks) ·
`scale_gate.py` **9 rows, 0 failing**. Five mutations run this cycle; four
were red before the cycle's edits, the fifth is red after them.

#### Decisions taken

| # | Decision |
|---|---|
| D96 | **The UX law is asserted, not merely obeyed.** `artist_ui.md` §6 is called binding at the top of the HDA builder, and a mutation that stripped the help text, the ranges and the unit suffixes off all nine float parms left the entire suite green. Four checks now read the built asset's own parameter templates: help on every parm, at most two disclosure levels, no numeric left at `hou`'s untouched 0..10 range, and a unit suffix in the label of every parm measured in metres, degrees or percent. A UX rule nothing checks is a UX rule that will be gone in two cycles |
| D97 | **The scale gate's expectation is stated per row, not derived from the sagitta.** `scale_gate.py` decided pass/fail from `4/(8R)` — the SPINE measure D87 retired — so the harness guarding the curvature budget could not see the term the budget now spends, and its `arc_80` row was green only because the starter panel is yaw-only (`rz` = 0.03 m instead of `radius` = 0.90 m). Each row now carries its own expectation with the reason beside it, and the ladder is run a second time under `zmode = adaptive`, where R = 80 m correctly unpacks all 10 000 pieces |

---

### Cycle 10 - §4.4's flatten-under and its two hybrid bands (2026-08-22)

**The last unimplemented sentence of §4.4's kernel**, deferred with eyes open
since cycle 2 and named in three standing findings: "stepped (yaw-only,
constant Z, **optional flatten-under**)". Built here, with the flat-top /
flat-bottom bands RailClone documents beside it.

#### 1. What RailClone actually does (read, not recalled)

`docs.itoosoft.com` returns 403 to the fetcher, so the two behaviours were
read out of iToo's own indexed text rather than from memory:

* **Flatten Stepped** (generator-side) "automatically flattens the path in
  positions where RailClone uses segments in Stepped mode... used to fix
  alignment issues that may appear with railings and sloped paths".
* **Flat Top / Flat Bottom** (segment-side) "enable the top or bottom of a
  segment to deform and follow the spline, leaving the middle area
  stepped... the value defines an area of influence, represented as a
  distance in world units from the top or bottom of the segment's height" -
  the two hybrid modes that combine the Vertical and Stepped algorithms.

#### 2. The defect, measured before the fix

A `stepped` piece is flat at ONE elevation and that elevation was its own
START. Two consequences, both real: going downhill the whole underside hangs
in the air by the drop across the piece, and the same fence drawn the other
way is BURIED by the same amount instead - so the result depended on which
way the artist drew the spline.

Numbers, on **PC-G2's own gate scene rebuilt** (24 m spline turning ±3.6 m
in plan and climbing 2.4 m, resampled at 0.25 m, over
`y = 1.1 sin(2πx/13) + 0.8 cos(2πz/9) + 0.06x`, conform ON) and measured
through the suite's own checks:

| PC-G2 hill, stepped posts | `stepped_float_m` | `stepped_riser_m` | packed |
|---|---|---|---|
| flatten OFF (**before**) | **0.054818** | 0.061280 | 240 / 240 |
| flatten ON (**after**) | **0.0** | 0.061280 | 240 / 240 |
| spline REVERSED, OFF | **0.061280** | 0.061280 | 240 / 240 |
| spline REVERSED, ON | **0.0** | 0.061280 | 240 / 240 |

`0.06128` is the 0.061 m §0.0 has carried since cycle 6, reproduced exactly.
**`stepped_riser_m` does not move and must not**: the step between two flat
pieces IS stepped mode, and removing it would remove the mode. What the
flatten removes is the AIR under each piece, which is the other half of the
same geometry and which nothing measured until now (`stepped_float_m`, new).
**Nothing unpacked**: 240 of 240 pieces are still packed prims, so the fix is
free at PC-G3 scale.

On a 2 m `panel` driven `stepped` the same hill reads **0.98154 -> 0.1 m**
(0.1 is the panel module's own ground clearance - its local y0 is 0.1 - so
0.1 is this module's zero).

#### 3. The bands, measured

`band_hybrid_m` is a PAIR, because the mechanism is two claims and one number
cannot carry both: `[the half that must be level, the half that must have
moved]`. The second is the anti-vacuity half and is asserted non-zero.

| PC-G2 hill | `band_hybrid_m` | `stepped_riser_m` |
|---|---|---|
| `vertical` panel, flat top 0.25 m | **[0.0, 0.96046]** | - |
| `stepped` panel, foot band 0.25 m | **[0.0, 0.96046]** | 0.96046 -> **0.106718** |

The stepped panel's riser collapses by 9x because its feet now follow the
ground while its body stays flat - which is the second of iToo's two hybrids,
and the one that reads as a stepped fence sitting ON a hill rather than over
it.

#### 4. The corner-assembly half of standing finding (2), re-measured

Cycle 4's four-line repro - `(0,0,0) -> (8,6,0) -> (0.4,12,0.2)`,
`corner_post` plus a `vertical` default, the leg pitched 37° - **does not
reproduce on this build**, in either corner mode:

* **bend**: no corner assembly is built at all (D36 welds the vertex), so
  there is nothing to leave a gap under.
* **miter**: one corner post, world y `[6.0000 .. 7.3000]`, i.e. its foot
  exactly on the vertex, and `corner_abut_m` = **0.002105 m**, inside its own
  2 mm budget.

So the 0.074 m figure §0.0 has carried is **stale**, and the anchored half of
the flatten is deliberately NOT built (D98's own exclusion, for D72's reason).

#### 5. Files

* `polychain/__init__.py` - `Params.flatten_stepped`, `Params.flat_band`,
  `Params.flat_band_m`, vocabulary `FLAT_BANDS`. All default to off, which is
  why no baseline moved.
* `polychain/place.py` - `_band`, `_follows`, `_stepped_base`, `_y_varies`;
  `_Proto.y0/.y1`; `base_y` on `_packed_transform` and `_deform_positions`;
  the band in `_needs_deform`; the datum decided once per piece in `build`.
* `devScripts/create_pf_polychain_hda.py` + `polyfactory/otls/pf_polychain.hda`
  - three parms in the Advanced folder, phrased as decisions ("Plant Flat
  Pieces on the Ground", "Level Band", "Level Band Height (m)"), and
  `flat_band_m` added to D96's units-in-the-label list so the UX law binds on
  it too.
* `tests/polychain/checks.py` - `stepped_float`, `band_hybrid`, `_band_case`,
  `_flat_in_y`; the three along-the-chain checks compare a banded piece in XZ
  for the same reason they already do a stepped one.
* `tests/polychain/cases.py` - `DA_hill_flatten`, `DB_hill_flatten_rev`,
  `DC_hill_rev_plain` (the before), `DD_band_flat_top`,
  `DE_band_stepped_foot`.
* `tests/unit/test_polychain.py` - `TestFlattenUnderAndBands`, the hou-free
  contract.

#### 6. The suite

`test_polychain.py` **59** · `test_polychain_plan.py` **91** ·
`test_polychain_corner.py` **63** · `test_citygen.py` and `test_plan.py` OK ·
`run_scene_checks.py` **81 cases, 0 failing** · `run_hda_checks.py`
**0 failing** · `scale_gate.py` **9 rows, 0 failing**.
**No baseline movement** - `tests/polychain/baseline.json` was not rewritten
by any run. (`tests/citygen/run_scene_checks.py` reports 27 failing checks
**both with and without this cycle's diff** - verified by `git stash`; it is
a pre-existing citygen state on this branch, not a regression.)

Suite-carried before/after, from `run_scene_checks.py`:

| case | `stepped_float_m` | `stepped_riser_m` |
|---|---|---|
| `DC_hill_rev_plain` (flatten OFF, downhill) | **0.029089** | 0.029089 |
| `DA_hill_flatten` (ON, uphill) | **0.0** | 0.029089 |
| `DB_hill_flatten_rev` (ON, downhill) | **0.0** | 0.029089 |

DA and DB are the SAME curve drawn both ways and they agree to the digit,
which is the direction-independence claim, asserted.

#### Decisions taken

| # | Decision |
|---|---|
| D98 | **§4.4's FLATTEN-UNDER is a datum choice, not a path edit.** A `stepped` piece has exactly one elevation, so the whole feature is *which* elevation: OFF it is the piece's own start (§4.4's "constant Z", and every baseline before this), ON it is the LOWEST ground under the piece's own span, sampled at the module's own stations so the flatten and the deform read the same ground (D71). That is RailClone's generator-side "Flatten Stepped" expressed on the piece instead of on the path, and it buys the two things the path edit buys - nothing floats, and a minimum does not care which end it started from, so a reversed spline builds the identical fence. It costs NOTHING at scale: the piece stays a packed prim, only its 4x4 changes. **OFF by default** - it is an option in RailClone too, and turning it on would have moved every stepped baseline in the suite. **ANCHORED pieces are excluded on purpose**: §4.3 gives ONE datum to a whole corner assembly (D72) and a per-half minimum would reopen the 0.02 m step at a seam PC-G1 asks to be gapless - and the corner case that motivated it no longer reproduces (§4 above) |
| D99 | **The two hybrid bands are ONE rule: the band is the exception to the z-mode.** iToo describes them from both ends - "flatten a Z-band from the top or bottom" for Vertical and "enable the top or bottom of a segment to deform and follow the spline, leaving the middle area stepped" for Stepped - and those are the same sentence seen from the two modes. So `_follows(y, band, stepped)` is `inside == stepped`, one expression, and with no band it is byte-for-byte what §4.4 did before. `adaptive` gets no band: it rides the full frame and has no flat half to hold. A band forces the piece onto the deform path (a packed prim is one 4x4 and a band is a per-point rule), which is why `DE` is 0/16 packed - and why a RIGID module cannot express a band at all (D27), the honest limit, stated in the case rather than hidden |

---

### Cycle 10b - the camber's off-spine rotation, brought into the budget (2026-08-22)

Standing finding (6), and the one that could ship visibly wrong geometry: a
packed piece takes the **midpoint** surface normal for its camber roll
(`_packed_transform`) while a deformed one takes a normal **per station**
(`_deform_positions`), and D87's budget measured the PATH's turn only. So a
piece whose two ends want materially different camber could stay packed while
its true deviation was many times `bend_tol`. Cycle 8 called it "unreachable
in the suite as it stands". It is reachable.

#### 1. The shape that reaches it

`y = k * x * z`, with the run straight along **+X at z = 0**. Along the spine
that surface is DEAD FLAT and DEAD STRAIGHT, so `Surface.deviates` reads zero,
D87's spine term reads zero, and every pre-existing reason to unpack is
switched off. What moves is the CROSS-FALL: the surface normal rolls by
`atan(k*x)`, which is exactly the rotation the packed piece was not paying
for. That is why the 15 conform cases could not see this - every one of them
bends the spine too, so `deviates` unpacked the piece before the gap could
show.

#### 2. The sweep, before the fix

20 m run, ten 2 m `panel` pieces (0.90 m off-spine radius), `conform_tilt` ON,
`bend_tol` = 0.01 m. `packed_true_dev_m` builds both answers and reports the
worst real distance between them:

| cross-fall gradient `k` | roll over one panel | packed | deformed | `packed_true_dev_m` | |
|---|---|---|---|---|---|
| 0.000 | 0.00° | 10 | 0 | - | ok |
| 0.002 | 0.23° | 10 | 0 | 0.003274 | ok |
| 0.005 | 0.57° | 10 | 0 | 0.005457 | ok |
| **0.010** | 1.13° | **10** | 0 | **0.010913** | **OVER BUDGET** |
| 0.020 | 2.19° | **10** | 0 | **0.021822** | **OVER BUDGET** |
| 0.050 | 4.40° | **10** | 0 | **0.071623** | **OVER BUDGET** |
| 0.100 | 5.19° | **10** | 0 | **0.108408** | **OVER BUDGET** |
| 0.200 | 3.94° | **10** | 0 | **0.212598** | **OVER BUDGET** |

It bites at a cross-fall changing by **1 % per metre of run** - a perfectly
ordinary graded road - and at 20 % per metre it kept all ten panels packed at
**21x** the budget.

#### 3. The sweep, after the fix

| `k` | packed | deformed | verdict |
|---|---|---|---|
| 0.000 / 0.002 / 0.005 | **10** | 0 | inside the budget, still packed |
| 0.010 / 0.020 / 0.050 / 0.100 / 0.200 | **0** | **10** | unpacked, correctly |

The threshold lands exactly on `bend_tol`: 0.005457 m stays, 0.010913 m goes.
Nothing over-unpacks - `k` = 0.005 keeps all ten packed, which is the half
that stops "fix" meaning "unpack every cambered piece".

#### 4. Proving the dangerous direction is closed

Being wrong in the *stayed packed but should not have* direction is the one
that ships, so it is now asserted on every case rather than on the camber
ones: **`deform_gate_m`** is a triple - `[worst deviation left PACKED, pieces
over budget, of those still packed]` - and the last number is asserted zero.
It is read on **44 cases**; the middle number proves the case is still live,
which is what `packed_true_dev_m` cannot do (it goes silent the moment the
gate works, and a silent check proves nothing).

**Mutation, run:** reverting D100 - handing `_needs_deform` a `None` normal -
turns `DF_camber_crossfall` red on **two** checks,
`deform_gate_m` **[0.197163897, 10, 10]** and `packed_true_dev_m`
**0.197163897 (10 packed over bend_tol 0.01)**, and the rest of the suite
stays green. Restoring it returns 0 failing checks.

#### 5. Files

* `polychain/place.py` - `span_deviation(..., normal_at=None)`: when the
  camber is on, the off-spine term is the **full frame rotation** between the
  deformed station's frame and the packed piece's one, taken from the trace of
  the relative rotation (`tr(R) = 1 + 2 cos theta`), so the tangent turn and
  the camber roll are measured once together instead of added twice. With
  `normal_at = None` it is byte-for-byte D87's tangent-only reading, which is
  every case measured before this. `_needs_deform` carries the normal, which
  meant deciding `tilt` **before** the deform gate rather than after it.
* `tests/polychain/checks.py` - `deform_gate`.
* `tests/polychain/cases.py` - `DF_camber_crossfall` (k = 0.2, the worst) and
  `DG_camber_gentle` (k = 0.005, deliberately inside the budget).
* Cycle 10's cases renamed off the `C*` prefixes they collided with:
  `DA_hill_flatten`, `DB_hill_flatten_rev`, `DC_hill_rev_plain`,
  `DD_band_flat_top`, `DE_band_stepped_foot`.

#### 6. The baseline, moved deliberately and audited

`run_scene_checks.py --update-baseline` was run once, for the first time this
cycle, and the result was diffed key by key against `HEAD`'s copy:

* **added cases (7)**: `DA_hill_flatten`, `DB_hill_flatten_rev`,
  `DC_hill_rev_plain`, `DD_band_flat_top`, `DE_band_stepped_foot`,
  `DF_camber_crossfall`, `DG_camber_gentle`
* **removed cases**: none
* **new check names (3)**: `band_hybrid_m`, `deform_gate_m`,
  `stepped_float_m`
* **MOVED VALUES: 0**

Nothing that existed before this cycle changed value. `run_hda_checks.py`
**0 failing**, `scale_gate.py` **9 rows, 0 failing** (the camber is off by
default, so PC-G3's ladder is untouched).

#### Decisions taken

| # | Decision |
|---|---|
| D100 | **The camber's own rotation is part of the curvature budget, measured as the FULL frame rotation.** D87 put the piece's worst POINT into the budget but measured only the tangent's turn, so 4.5's camber - a roll the packed piece takes once at its midpoint and the deformed one takes per station - was spent by nobody. It is not a second term added to D87's: `span_deviation` now compares the two FRAMES when a normal is available (trace of the relative rotation), which counts the tangent turn and the camber roll together exactly once, and degrades to D87's tangent-only reading when there is no camber - so no pre-camber number moved. The gate bites at `bend_tol` to the digit: 0.005457 m stays packed, 0.010913 m unpacks |
| D101 | **A check that goes silent when the bug is fixed is not a standing check.** `packed_true_dev_m` can only see pieces that STAYED packed, so the case built to prove D100 reads `skip` the moment D100 works. `deform_gate_m` reports `[worst deviation left packed, pieces over budget, of those still packed]`: the last number is the assertion (the direction that ships), and the middle one is the liveness - a case that stopped exercising the gate shows a 0 there and reads as vacuous instead of as green. It runs on all 44 cases that have a bendable piece on a path, so it guards D87 and D75 as well as D100 |

---

### Cycle 10c - the deform path's rewrite, profiled first (2026-08-22)

The task was "rewrite the per-point deform inner loop in VEX". **The profiler
says the inner loop was never the cost**, so what shipped is the fix the
measurement pointed at, and the VEX decision is recorded with the numbers that
made it.

#### 1. Where the 11 s actually went

`cProfile` over `scale_gate`'s heaviest row - `arc_10`, 9 996 deformed pieces,
359 856 points:

| | tottime | calls | share |
|---|---|---|---|
| **`_hou.Prim_setAttribValue`** | **9.023 s** | **4 758 096** | **64 %** |
| `_stamp` (the Python around it) | 1.139 s | 339 864 | 8 % |
| `hou.py:setAttribValue` wrapper | 0.811 s | 4 758 096 | 6 % |
| `Path.sample` | 0.475 s | 449 834 | 3 % |
| **`_deform_positions`** - the loop the task named | **0.201 s** | 9 996 | **1.4 %** |
| everything else | | | |
| **total** | **14.136 s** | 21 073 358 | |

339 864 prims x 14 attributes. **The stamp, not the maths.** A perfect VEX
inner loop would have taken 1.4 % off this row.

#### 2. What shipped instead (D102)

`hou.Geometry` already has C++-side ARRAY writers -
`setPrimStringAttribValues` / `setPrimIntAttribValues` /
`setPrimFloatAttribValues` - so a deformed piece is stamped in **14 calls
instead of 14 x its prim count**. Both writers read one list,
`_stamp_values`, so they cannot drift; a packed piece (one prim) still takes
the per-prim path, where bulk would only add overhead.

#### 3. The ladder, before and after - both runs in ONE process

Same session, same curves, the two writers swapped between runs, and the
packed/deformed/point counts asserted equal on every row:

| case | zmode | packed | deformed | points | per-prim s | **bulk s** | speedup |
|---|---|---|---|---|---|---|---|
| two_point | kit | 10 000 | 0 | 10 000 | 0.483 | 0.478 | 1.01x |
| resampled | kit | 10 000 | 0 | 10 000 | 0.602 | 0.624 | 0.96x |
| arc_12000 | kit | 10 000 | 0 | 10 000 | 0.663 | 0.668 | 0.99x |
| arc_2000 | kit | 10 000 | 0 | 10 000 | 0.675 | 0.675 | 1.00x |
| arc_80 | kit | 10 000 | 0 | 10 000 | 0.648 | 0.646 | 1.00x |
| **arc_10** | kit | 0 | 9 996 | 359 856 | **11.159** | **1.548** | **7.21x** |
| arc_12000 | adaptive | 10 000 | 0 | 10 000 | 0.637 | 0.643 | 0.99x |
| arc_2000 | adaptive | 10 000 | 0 | 10 000 | 0.645 | 0.629 | 1.03x |
| **arc_80** | adaptive | 0 | 10 000 | 360 000 | **11.181** | **1.597** | **7.00x** |

The packed rows are unchanged to the noise floor, which is the control: they
stamp one prim per piece and had nothing to gain. **The 11.0 s row PC-G3 owed
is 1.56 s.** The HDA's own measurement moved with it:
`proxy_beats_full_on_a_curve` **[0.648, 11.185] -> [0.649, 1.86]**.

#### 4. Parity - bit-identical, on every case in the suite

The reference implementation is the per-prim `_stamp` loop the build used
before this cycle. Every case built twice in one process and compared on
point positions, every prim attribute value, and every packed prim's full
4x4:

| | |
|---|---|
| cases compared | **83** |
| points compared | **11 800** |
| prim attribute values compared | **163 115** |
| worst `|dP|` | **0** |
| worst `|d packed transform|` | **0** |
| prim attribute values differing | **0** |
| structural differences | **0** |

**PARITY: EXACT (bit-identical)** - not "within float precision", identical.
Plus `run_scene_checks.py` 0 failing with **0 baseline values moved**, and
`run_hda_checks.py` 0 failing.

#### 5. Why NOT VEX or OpenCL, measured

Three numbers and one architectural fact:

1. **The share is too small.** After D102 the whole `arc_10` row is 1.548 s
   and `_deform_positions` costs **0.214 s of it (13.7 %)** across all 9 996
   pieces - and **0.063 s of that 0.214 s is `Path.sample`**, which VEX
   cannot take without reimplementing the path, the conform drape, D26's
   remap and D31's transport as well. So the arithmetic actually available to
   VEX is ~0.15 s, **under 10 % of the row**.
2. **The irreducible per-piece overhead is 0.041 s** for all 9 996 pieces
   (`hou.Geometry` + `merge` + `setPointFloatAttribValues`) - a fifth of the
   loop's own cost, and every design pays it.
3. **There is no VEX verb.** On 22.0.398 `hou.SopNodeTypeCategory.nodeVerb`
   returns `None` for `attribwrangle`, `attribwranglecore`, `vex`,
   `pointwrangle`, `deformationwrangle` and `volumewrangle`; the only one
   that exists is `attribvop`, which needs a VOP network **node**. And
   `place.build` is geometry-in / geometry-out with **no node network at
   all** - that is what lets every headless check and `pf_polychain_core`
   share one kernel. A VEX path would force a node network into it.

So the honest cost/benefit is: under 10 % of one row, in exchange for a
second implementation of `Path.sample`, `_Remap`, the conform drape,
`_transport`, D98's datum and D99's bands that has to be held in parity
forever. **Python stays**, and that is recorded rather than quietly skipped.

#### 6. Files

* `polychain/place.py` - `_stamp_values` (the single description),
  `_stamp_geo` (the bulk writer), `_stamp` (the per-prim one, now a loop over
  the same list). D102 and D103 in the file's own decision list.
* `polychain/hda.py` - `SLOW_COOK_S`'s measurement note updated: the 20 km
  curving run it was chosen against now cooks in 1.86 s, i.e. just under the
  2.0 s threshold, so it no longer warns. The threshold stays at the artist's
  latency rather than following the build.

#### Decisions taken

| # | Decision |
|---|---|
| D102 | ⚠️ **AMENDED BY §11.8 P1 - `_stamp_geo`, the per-PIECE bulk writer this row describes, IS DELETED.** P1 moved the accumulation up one level: pass B collects `(prim count, values)` per piece and `_stamp_bulk` writes one array per attribute over the WHOLE output, on both branches. The packed branch - PC-G3's headline row and every citygen street - never had D102's fix at all and measured as 62 % of the real node cook. `stamp_parity` compares `_stamp_bulk` against the per-prim `_stamp` reference; there is no third writer. Everything below is still why the decision was taken. **The stamp is written in BULK, and that is the deform path's rewrite.** 3.4's stamp was one `Prim.setAttribValue` per attribute per prim, which on a deformed run is 14 x the piece's prim count - profiled at 4 758 096 calls and **9.0 s of a 14.1 s** build, 64 % of the row, against `_deform_positions`' own 1.4 %. `hou.Geometry`'s array setters are the same C++ the wrangle would have called, need no second language, no node network and no second implementation to keep in parity. One `_stamp_values` list feeds both writers so they cannot drift, and the result is bit-identical across all 83 cases. **7.21x on `arc_10`, 7.00x on `arc_80/adaptive`; 11.0 s -> 1.56 s** |
| D103 | ⚠️ **RETRACTED IN PART - THE BLOCKER IS FALSE. SEE [§11.0](#110-two-corrections-and-one-trap).** "`nodeVerb` has no VEX verb at all" is wrong on 22.0.398: `attribvop`'s `vexsrc` menu has `snippet` as its 4th entry with a `vexsnippet` string parm, so `hou.sopNodeTypeCategory().nodeVerb("attribvop")` executes ARBITRARY VEX **with no VOP network node** - which is the whole of this row's architectural objection. Re-probed a third time on this build (2026-08-22): `vexsrc=3, bindclass=2, vexsnippet="f@arc = @P.x*1.0000000001 - @P.x;"` at x = 20 000 returns **2.0000006770715117e-06 under `vex_precision="64"` and exactly 0.0 under `"32"`** - so VEX is reachable AND 64-bit is mandatory for a 20 km arclength. ⚠️ AND THE PROBE THAT PRODUCED THE FALSE ROW: `nodeVerb` returns **`None`** for a verbless node, it does not raise, so a `try/except` probe reports every node as having a verb (re-confirmed: `attribwrangle`, `chain`, `copytocurves`, `pathdeform` all `None`; `attribvop`, `copytopoints`, `ray` all real). The row's *conclusion* - that porting `_deform_positions` alone was not worth it after D102 - still stands on its own numbers and §11.2 P6 re-derives it; only the blocker falls, and anything downstream of the blocker needs re-deriving rather than citing. **The deform's inner loop stays in Python, measured rather than assumed.** After D102 it is 0.214 s of a 1.548 s row (13.7 %), and 0.063 s of that is `Path.sample` - so under 10 % of the row is actually reachable from VEX. Against that: `hou.SopNodeTypeCategory.nodeVerb` has **no VEX verb at all** on 22.0.398 (`attribwrangle`, `attribwranglecore`, `vex`, `pointwrangle`, `deformationwrangle`, `volumewrangle` all return `None`; only `attribvop` exists, and it needs a VOP network node), while `place.build` is deliberately node-free so that the headless checks and `pf_polychain_core` share one kernel. A VEX path would mean a node network in the kernel plus a permanent second implementation of the sampler, the remap, the drape, the transport, D98's datum and D99's bands. The house rule is VEX over Python **in hot paths**; this one is measured not to be the hot path, and the hot path it actually had is now gone |

#### Cycle 10 - final state

`python -m pytest tests/unit -q` **284 passed, 9 625 subtests** in 0.76 s
(279 before this cycle) · `hython tests/polychain/run_scene_checks.py`
**83 cases, 0 failing** (76 before) ·
`hython tests/polychain/run_hda_checks.py` **0 failing** ·
`hython tests/polychain/scale_gate.py` **9 rows, 0 failing**, with
`arc_10` at **1.557 s** and `arc_80/adaptive` at **1.593 s** where both read
~11.0 s at the start of the cycle.

The baseline was rewritten exactly once, and audited key by key against
`HEAD`: **7 cases and 3 checks added, 0 values moved.** Three mutations run
across the cycle - reverting D100 (2 checks red on `DF_camber_crossfall`),
stamping per-prim instead of in bulk (bit-compared, 0 differences, which is
the parity proof rather than a red suite), and the flatten's own before/after
carried in the suite as `DC_hill_rev_plain` against `DA`/`DB`.

`tests/citygen/run_scene_checks.py` reports **27 failing checks both with and
without this cycle's diff** (verified by `git stash`) - a pre-existing citygen
state on this branch, untouched by polyChain.

---

## Cycle 11 - the review's three "stayed packed / sat wrong" findings, reproduced then closed

Three independent reviewers returned four findings against cycle 10. All four were
**reproduced first** on this build, to the digit, before a line was changed; three were real
defects and are fixed with a standing check each, and the fourth was a genuine hole in the
suite's own coverage rather than in the kernel.

#### 1. The D58 hero path never read D98's datum (finding 1, major, confirmed)

`build`'s pass A decides the flatten-under datum once per piece and its own comment claimed it
was "used by BOTH materialisation paths". There are **three**: packed, deformed, and the D58
hero replacement - and the hero branch called `_packed_transform` without it. Reproduced on the
reversed suite hill with `flatten_stepped=True` and one `post` replaced through
`write_override(elem_id=..., hero=...)`:

| | plain | hero-replaced |
|---|---|---|
| `flatten_stepped=True` | y = **3.897902** | y = **3.926991** (+0.029089, one full riser) |
| `flatten_stepped=False` | y = 3.926991 | y = 3.926991 |

So a replaced piece floated one whole piece-drop above its planted neighbours, silently, and
re-inherited the spline-direction dependence D98 exists to remove. Fixed by passing the datum -
as a separate `packed_y`, because a *banded* piece has no one elevation a rigid transform could
place it by, so only `stepped` hands one to `_packed_transform`.

**Standing check:** `DJ_flatten_hero` (reversed hill, flatten on, element 135 replaced by a
1.5 m hero post on the module's own 0.12 m footprint) reads `stepped_float_m` **0.0**,
`stepped_riser_m` 0.029089, 270/270 packed. And `stepped_float_m` **now asserts** when the
flatten is on - it was recorded-only, and the mutation proved that too weak: dropping the datum
from the hero path moved it 0.0 to 0.029089 m with **every check in the suite still green**.

#### 2. A D99 level band levelled to the piece's START (finding 2, major, confirmed)

`base_y` was computed only for `zmode == "stepped"`, so a **banded vertical** piece fell to
`_deform_positions`' default - the elevation at its own start sample. Measured on the suite's
own hill with a 0.25 m top band, the 16 level band tops:

| | forward | reversed |
|---|---|---|
| before | 1.000 / 1.491 / 1.982 / ... / 8.363 | 1.491 / 1.982 / ... / **8.854** |
| flatten ON, before | *byte-identical to the row above* | *byte-identical* |

Every "level top rail" moved **0.490874 m** with the direction the artist drew the spline - the
exact defect class D98 was built to remove - and the parm whose help text promises direction
independence did not reach it. **D105** extends the datum to the level band, taking the extremum
on the band's OWN side: a level top rail takes the **highest** ground under its piece (so it
never dips into the body it caps), a level bottom band takes the lowest, which is D98's
flatten-under seen upside down. `_stepped_base` gained one `pick` argument and nothing else.

**Standing check:** `band_datum_m` - *what* elevation the level half levelled to, which is the
one question `band_hybrid_m` cannot ask - plus the pair `DH_band_flat_datum` /
`DI_band_flat_datum_rev`. Forward and reversed both read **0.0**; `DD_band_flat_top` (flatten
off, RailClone's start-anchored behaviour) records the **0.490874** the defect was worth.
Asserted only when the flatten is on. The pair is load-bearing: mutating the fix red-lines DH
and leaves DI green, because on a descending run the start *is* the maximum.

#### 3. The camber budget was sampled where the deform is not (finding 3, major, confirmed)

D100 read the camber only at the span's ends and the interior spline vertices, while
`_deform_positions` rebuilds a frame at every **module station** (D71/D31). A cross-fall whose
roll inflects between those samples was therefore free. The reviewer's surface -
`y = 0.2 sin(pi x) z`, a superelevation transition whose roll is exactly **zero at every 2 m
piece boundary and at every midpoint** and +/-11.3 deg at the quarter-span - reproduced on HEAD:

| case | before | after |
|---|---|---|
| A = 0.2, 2-point spline | 10/10 **packed**, `deform_gate_m` **[0.197164, 10, 10]** | 0/10 packed, [0.0, 10, 0] |
| A = 0.02, 2-point spline | 10/10 packed at 0.020006 m (2x tol) | 0/10 packed |
| A = 0.2, 1 m-resampled | 10/10 packed at 0.197164 m | 0/10 packed |

0.197164 m is **19.7x `bend_tol`** - the same magnitude cycle 10's own mutation test treats as
the gate failing - and the resampled row is the important one: a dense street polyline whose
vertices happen to land on the ripple's zeros is defeated identically, so "streets hand us
resampled curves" is not a defence. **D104** folds `_Proto.fracs` into both walks of
`span_deviation`, and **only when `normal_at` is given**, which keeps the entire no-camber path
byte-identical (on a polyline the spine term is linear between vertices, so the extra stations
can find nothing the camber roll did not put there). Measured: `DF_camber_crossfall` 0.197164
and `DG_camber_gentle` 0.005002 are unchanged to the last digit, and the threshold still lands
on `bend_tol`.

**Standing check:** `DK_camber_ripple`. Reverting D104 turns it red on **two** checks
(`deform_gate_m` [0.197163909, 10, 10] and `packed_true_dev_m` 0.197163909).

#### 4. The bulk-stamp parity proof was a scratchpad run (finding 4, minor, accepted)

D102's parity was measured once and never re-asked, and every other check reads a stamp from the
**first prim** of an element (`checks.elements` takes `_attrs` from the first prim it sees), so a
future edit to `_stamp_geo`'s isinstance dispatch that corrupted prims 2..n could pass the whole
suite. **`stamp_parity`** is now a per-case check: for every placement the case built, a
throwaway 3-prim geometry is stamped through the bulk writer and through the per-prim writer
with the element's own warnings, and every prim's every attribute value is compared. It reads
`[values compared, differing]` - **0 differing on all 87 cases**. Mutating `_stamp_geo` to write
the correct value only on prim 1 turns it red on **every case with a deformed piece**.

#### Decisions taken

| # | Decision |
|---|---|
| D104 | **The curvature budget is sampled where the deform rebuilds its frame, not only at the spline's kinks.** D100 counted the camber roll at the span's ends and its interior vertices; `_deform_positions` builds a frame per MODULE STATION, so a roll that inflects in between was spent by nobody - a superelevation transition left 10 of 10 panels packed at 0.197164 m, 19.7x `bend_tol`, on a 2-point spline AND on a 1 m-resampled one. `span_deviation` takes `fracs` and folds those stations into both the spine walk and the frame-rotation walk. It does so **only when a camber normal is present**, which is what makes it free: the spine term is linear between polyline vertices, so with no camber the extra samples are provably redundant and every pre-D104 baseline is byte-identical (`DF` 0.197164 and `DG` 0.005002 unchanged to the digit) |
| D105 | **A D99 level band takes its one elevation from an extremum over its own span, on the band's own side.** The band was the last place a piece's flat half still took its height from wherever the walk started, so a "level top rail" moved 0.490874 m when the spline was drawn the other way while `flatten_stepped` - the parm that exists to make that impossible - did not reach it. A level TOP band takes the HIGHEST ground under the piece (it is a rail held over the piece and must not dip into the body it caps); a level bottom band takes the lowest, which is D98 unchanged. One `pick` argument on `_stepped_base`, gated on the same parm as D98 so RailClone's start-anchored default is still what an untouched page builds - and `packed_y` is split from `base_y` because a banded piece has no single elevation a rigid transform could place it by |
| D106 | **A number that is only recorded is not a standing check once a mutation can move it silently.** `stepped_float_m` was never allowed to fail - baseline-diffed only - and the hero-datum defect moved it 0.0 to 0.029089 m with the suite still reporting 0 failing checks. It now asserts whenever `flatten_stepped` is on, and `band_datum_m` was written the same way from the start. Off stays recorded-only, because off IS RailClone's behaviour and the number is then the measured size of the deviation rather than a defect |

#### Cycle 11 - final state

`python -m pytest tests/unit -q` **284 passed, 9 625 subtests** in 0.74 s ·
`hython tests/polychain/run_scene_checks.py` **87 cases, 0 failing** (83 before) ·
`hython tests/polychain/run_hda_checks.py` **0 failing** ·
`hython tests/polychain/scale_gate.py` **9 rows, 0 failing** (`arc_10` 1.559 s,
`arc_80/adaptive` 1.584 s - D104 is invisible there, as designed: no surface means no camber
normal means the old code path exactly).

The baseline was rewritten exactly once and audited key by key against `HEAD`:
**4 cases and 2 checks added, 0 values moved.** Four mutations were run, each against the check
written for it: the hero datum (`DJ/stepped_float_m` 0.0 to 0.029089), the band datum
(`DH/band_datum_m` 0.0 to 0.490874), the `fracs` fold (`DK` red on two checks at 0.197164), and
the bulk stamp (`stamp_parity` red on every case with a deformed piece).

### Cycle 12 — independent verification of cycle 11, and phase 1 closed (2026-08-22)

A fresh agent that wrote none of cycle 11, told to trust nothing. Every number
below was produced by this cycle, not read from the last one. **Cycle 11's four
fixes all hold, and every one of them has a check that dies when the fix is
reverted. Two survivors were found; one is closed here, one is recorded.**

#### 1. The suite, re-run from clean

| Runner | Result |
|---|---|
| `python -m pytest tests/unit -q` | **284 passed, 9 625 subtests** in 0.74 s |
| `hython tests/polychain/run_scene_checks.py` | **87 cases, 5 063 checks, 0 failing** |
| `hython tests/polychain/run_hda_checks.py` | **0 failing** |
| `hython tests/polychain/scale_gate.py` | **9 rows, 0 failing** (`arc_10` 1.565 s, `arc_80/adaptive` 1.593 s) |

**No unexplained baseline movement.** The claim "4 cases and 2 checks added,
0 values moved" was re-derived independently, key by key, by loading
`baseline.json` at `e09bae8^` and at `e09bae8` and comparing every
`(case, check)` pair: **83 → 87 cases, 0 cases removed, 399 entries added,
0 values moved.** The 399 are exactly `band_datum_m` × 87, `stamp_parity` × 87,
`replaced_bbox_m` × 1 (the new override case) and the 57 standing checks on each
of the four new cases `DH_band_flat_datum`, `DI_band_flat_datum_rev`,
`DJ_flatten_hero`, `DK_camber_ripple`. Nothing else moved.

**citygen is untouched by the diff**: `git show --name-only e09bae8` lists
`devScripts/create_pf_polychain_hda.py`, `graphify-out/*`, `ideas/polychain.md`,
`polyfactory/otls/pf_polychain.hda`, `polychain/place.py` and
`tests/polychain/*` and **no citygen path at all**; `tests/unit/test_citygen.py`
rides in the 284. ⚠️ Minor: `graphify-out/` (a generated knowledge-graph dump)
is re-committed by every polychain cycle and churns ~2 400 lines a time. It is
noise in the diff, not a defect — worth gitignoring when someone next touches it.

#### 2. Mutation testing — fourteen mutations, each reverted with `git checkout`

Every row below was run on the committed tree, the tree restored immediately
afterwards, and the restore confirmed by `git status --porcelain` and by md5 of
`place.py`, `hda.py` and `run_hda_checks.py`.

| Mutation | Suite | Result |
|---|---|---|
| **the flatten-under disabled outright** (`_stepped_base` ignores `flatten`) | scene | **RED, 3** — `DB_hill_flatten_rev`/`stepped_float_m` **0.029089**, `DJ_flatten_hero`/`stepped_float_m` **0.029089**, `DH_band_flat_datum`/`band_datum_m` **0.490874** |
| the D58 HERO branch alone loses the datum (cycle 11's finding 1, reverted) | scene | **RED, 1** — `DJ_flatten_hero`/`stepped_float_m` 0.029089 |
| the PLAIN packed branch alone loses the datum | scene | **RED, 2** — `DB` and `DJ`, both 0.029089 |
| D105 reverted — the band datum back to the START sample | scene | **RED, 1** — `DH`/`band_datum_m` 0.490874 (`DI` stays green: on a descending run the start *is* the extremum, which is why the pair exists) |
| the band datum picks the WRONG extremum (a top band takes `min`) | scene | **RED, 2** — `DH` **and** `DI`, both 0.490874 |
| **the camber budget widened 50x**, camber term only, so a mis-cambered piece stays packed | scene | **RED, 4** — `DF_camber_crossfall` and `DK_camber_ripple`, on `deform_gate_m` `[0.197163…, 10, 10]` and `packed_true_dev_m` |
| the whole deform budget widened 50x | scene | **RED, 43** across 14 cases |
| D104 reverted — `fracs` dropped from `span_deviation` | scene | **RED, 2** — `DK_camber_ripple` only, at 0.197163909 |
| **the bulk stamp diverges from the per-prim stamp by 1e-6 on `pc_u`** — there is no VEX path (D103 measured one and declined it), so the bulk/per-prim pair IS this build's two-implementations-of-one-thing | scene | **RED, 87** — `stamp_parity` on every case |
| the same divergence on prims 2..n only, prim 1 left correct — the exact blind spot cycle 11's finding (D) named | scene | **RED, 87** — `stamp_parity` on every case |
| CONTROL: `pc_deformed` inverted in both writers | scene | **RED, 264** across `rigid_deformed`, `deformed_flag_mismatch`, `over_unpacked`, `packed_true_dev_m` |
| every packed piece lifted **5e-5 m** (below the suite's declared `TOL_M` = 1e-4) | scene | 0 FAIL but **352 baseline values move**, `geometry_digest` included — the floor is loud well below the assertion tolerance |
| every packed piece lifted **5e-4 m** | scene | **RED, 71** |
| the deform budget widened 50x, at PC-G3 scale | ladder | **RED, 2 rows** — `arc_10/kit` (9 996 packed, must be 0) and `arc_80/adaptive` (10 000 packed, must be 0) |

#### 3. SURVIVORS

**(A) PC-G4's parm sweep could not see the defect it was written for — CLOSED
here (D107).** Reverting D91 — applying the `padding` parm unconditionally, so a
wired style payload feels it again — left `run_hda_checks.py` **completely
green**: `parms_inert_under_payload … swept 39 parms; moved: none`. A debug
print proved `_padded` really ran at `padding = 0.37` under the payload, so the
mutation was live and the check simply could not see it. The cause is the
fixture, not the sweep: the payload it wires is `Params(fill="scale")` on the
closed 12×8 rectangle, and **under `scale` that fence does not move for any
`pc_pad` at all** — measured directly through `place.build`, `gate.pad` goes
0.0 → 0.185 → 0.400 while the output stays **44 prims, 12 elements and an
identical point sum**. One word — `scale` → `adaptive` — and the same revert
reports **`moved: padding`**. The check's own comment says it exists because an
earlier version "missed `padding` entirely"; on this build it still did.
PC-G4's other legs are unaffected (cycle 9 swept all 8 fill × corner
combinations separately, so `scale` coverage is not lost).

**(B) Three of the fourteen §3.4 stamp attributes are asserted by nothing —
STANDING, finding (10).** `pc_u` set 0.25 too high, `pc_section` off by one and
`pc_variant` blanked, each in **both** writers, leave the suite at **87 cases,
0 failing and 0 baseline values moved**. `stamp_parity` proves the two writers
AGREE; nothing proves either is RIGHT. `pc_elem_id`, `pc_module`, `pc_zmode`,
`pc_deformed`, `pc_slot` and the warning stamps are all covered — the control
mutation on `pc_deformed` is red on 264 checks — so this is a hole in three
named attributes, not in the stamp mechanism. It matters because `pc_u` is the
handle a consumer varies material and decals along a run with, and `pc_section`
is how it addresses a spline section. **Not fixed here**: phase 1 is closing and
a new per-case check rewrites 87 baseline rows; it is the cheapest first job for
the next agent, and the repro above is exact.

#### 4. Gate re-confirmation, after the flatten and the budget both moved

Everything was rebuilt **through the HDA's parm page** with
`scratchpad/vgate_hda.py`, plus a new `scratchpad/vgate_flatten.py` for the one
comparison the standing renderer never made.

**PC-G1 — STILL PASSES, on the same terms.** Both corner modes, the L, all four
Fit Methods and the gate-on-a-marker rebuilt through the page and looked at
(`HG1_*.png`). **Miter** (`HG1_rect_miter_corner.png`): the two legs terminate
into a corner post standing on the vertex, the boards run flush into it from
both sides, the top arrises of the two legs are level with each other and with
the post's shoulder, and there is no gap and no overlap at the seam. **Bend**
(`HG1_rect_bend_corner.png`): no corner post at the vertex at all — the run
turns through the elbow as **one continuous top arris** (D36's ring weld), with
only the accepted butt notch on the inside of the turn. `pc_warn_bend_resolution`
fires on 3 elements in the bend rect, which is the documented, baselined
warning. **The marker leg re-measured on this build**: x **7.200000 .. 8.800000**,
centre **8.000000**, error **1.788e-07 m**, authored with Piece at Markers +
Marker Id and **no payload**, with the unread-marker warning firing beforehand.
⚠️ `vgate_hda.py` prints `len 0.000000 … error 8.000e-01 m` for that same gate —
that is the SCRIPT reading a *packed* prim's single vertex instead of its
embedded geometry through `fullTransform()`. The build is right; the scratchpad
print is not. Measured properly it is the 1.788e-07 m above. GUI viewport pass
still owed.

**PC-G2 — STILL PASSES, and the riser question is answered in the image.** New
`HG2F_{fwd,rev}_flat{0,1}.png`: the same stepped run on the same hill with
**Flatten Under Stepped OFF vs ON**, and with the spline drawn **both ways**.
With it **OFF**, on the descending stretch every post's foot hangs a visible
sliver of dark above the orange ground line and the sliver grows as the slope
steepens — the posts are standing on air. With it **ON**, that sliver is gone in
both directions: every post's underside meets the ground line along the whole
run. What remains is the **sawtooth of flat post tops stepping down over a
smooth ground line** — that is the riser, it IS stepped mode, and it measures
**0.029089 m** on this hill. So: **the air is gone, the riser is deliberately
still there and named.** The other three modes re-judged on `HG2_*.png`: the
vertical pickets' ribs stay dead plumb through the steepest part of the descent
while the run's foot tracks the ground; the adaptive rail's ribs rake
perpendicular to the drape; Tilt to Surface visibly rolls the rail onto the
cross-fall; and the wide shot reads as a fence on a hill for the whole 24 m
S-curve. 0 warnings on every G2 shot, and `inward_faces` is **0** on all 87
suite cases. GUI viewport pass still owed.

**PC-G3 — STILL PASSES, on its own narrower terms.** `scale_gate.py`, both
z-modes, **9 rows 0 failing**: the five packed rows hold **10 000 packed / 0
deformed / 10 000 points / one `geometryid` / ~0.6 s / +2…7 MB RSS**, and the
two rows that MUST unpack (`arc_10/kit` at 5x the budget, `arc_80/adaptive` at
2.25x `bend_tol`) do, at 1.565 s and 1.593 s — D102's bulk stamp still holding
its 7x. D104 is invisible here by design: no surface means no camber normal
means the pre-D104 path exactly. Widening the budget 50x fails 2 rows.

**PC-G4 — PASSES, but only after D107.** `run_hda_checks.py` is 0 failing,
including all four payload legs and the 39-parm sweep. Before this cycle it was
0 failing **with the D91 defect re-introduced**, which is not a pass. With the
fixture corrected the sweep reports `moved: padding` under that revert and
`moved: none` on the shipped code.

#### Decisions taken

| # | Decision |
|---|---|
| D107 | **A parm-inertness sweep is only as strong as the fence its fixture can build.** PC-G4's payload used `fill="scale"`, and under `scale` the fixture's fence does not move for any `pc_pad` — `gate.pad` 0.0 → 0.4 with 44 prims, 12 elements and an identical point sum — so the whole 39-parm sweep was blind to `padding`, the one parm the sweep's own comment says it was widened to catch. The fixture is `adaptive` now, the cheapest fill mode that can express a gap. The rule this generalises to: when a check sweeps inputs, the fixture must be one the input can actually change, and the way you find out is to revert the fix and watch the check |
| D108 | **A batched drop takes only the ALONG-AXIS component from the verb and rebuilds the rest from the double query.** The `ray` verb's ray origins and its hits both live in a point cloud, i.e. float32, while `hou.Vector3` is double — so a naive port loses width, coordinate-scaled (5.5e-07 m under 20 m, 2.3e-05 m at 2 km), and §11.3 had already authorised re-baselining every conformed case for it. But a drop is a *translation along `axis` by construction*: the two components perpendicular to the axis are the query's own, and nothing may be learned about them from a float32 cloud. `Surface.drop_many` therefore reads `dot(hit − q, axis)` and reconstructs — which takes `conform_parity` from 9.5e-07 m to **0.0 on every conformed case** and P5 from 22 moved baseline values to none. The generalisation: **when a native node hands back a number a contract says you already know exactly, keep the one you know.** ⚠️ **SUPERSEDED IN PART BY D111: the 0.0 was a property of the FIXTURES, not of the code.** Reading the along-axis component of the verb's POSITION is one float32 rounding at the magnitude of a world coordinate, and it is bit-identical only where the true answer happens to be exactly representable — which every committed conform case is (`y = 0.25x`, stations at multiples of 0.25 m). On an irrational-slope ramp it reads 2.4e-07 m, and at x = 20 000 m it reads 6.1e-05 m. D111 reads the verb's DISTANCE instead. |
| D109 | **P6 is DECLINED, and the reason is that the deformed branch's cost is not where §11.2 thought.** On the conformed citygen row — 300 streets over terrain, the biggest workload this tool has (**8.8–38.5 % deformed depending on the terrain**, not 100 % — see §11.8 P5c) — pass A is **77 %**, the whole deformed materialisation P6 replaces is **11 %**, and the net after `copytopoints` (0.039 s) and one 64-bit `attribvop` (0.0005 s) is **~9 %**; on an unconformed deformed row it is ~21 %. Bought with HIGH risk to `geometry_digest` (which P5 moved on 0 of 88 cases), `pc_local`, prim and point numbering and the corner-cut hybrid, plus three `attribcast` calls existing only to undo a float32 loss the current code does not have — at 20 km the float32 attribute quantum is 1.95e-03 m against `exact_fill_m`'s 4.4e-07 — that is a worse trade than P4's was. The measurement is in §11.8 P6 and is not to be re-derived. **What the same profile points at is pass A on the conformed row, which no item in §11.2 addresses.** |
| D110 | **OpenCL is not warranted anywhere in phase 1, and this is the number.** `attribvop` with `vexsrc="snippet"` and `vex_precision="64"` runs a per-point trig snippet over **359 856 points in 0.0005 s** — the largest parallel stage the tool has. VEX is never the bottleneck; the Python around it always is. A GPU port would be optimising a stage four orders below the row it lives in. (And the 64-bit trap holds — but **not with the expression this row used to quote, which does not reproduce**: `sin(x·1e-6) − x·1e-6` returns exactly 0.0 at `"32"` only at **x ≈ 360**, where the true value falls under float32 resolution; at a genuine 20 000 m it returns −1.3336539e-06 against a true −1.3333067e-06, i.e. 32-bit is accurate to 3.5e-10 there. D103's expression is the one that demonstrates it at the scale that matters: `@P.x*1.0000000001 - @P.x` at x = 20 000 is **exactly 0.0 at `"32"` and 2.0000006770715117e-06 at `"64"`**, re-measured on 22.0.398. ⚠️ And the parm is `vexsnippet`, not `snippet` — `vexsrc` is the int menu, 3 = snippet.) |
| D111 | **A batched drop reads the verb's DISTANCE, not its POSITION — and a tilted `conform_axis` is not batched at all.** D108 rebuilt the drop from the along-axis component of `ray`'s hit POSITION, which is one float32 rounding at the magnitude of a *world coordinate*; `ray` also writes `dist`, the same number measured from the query, which is one rounding at the magnitude of a *drop*. Measured on an irrational-slope ramp against `Surface.drop`: position **2.384e-07 m** at x < 24 and **9.746e-04 m** at x = 20 000, distance **0.0** at both. ⚠️ **The 20 km figure is corrected by P5cV**: the 6.104e-05 m originally recorded here does not reproduce against the committed `dirty_ramp_20km` trial, the divergence there is entirely in x/z (the y component is 0.0), and — separately — **both** readings sit 8.569e-04 m from the analytic surface at that coordinate, because `hou.Geometry.intersect` is itself float32 at world magnitude. Parity with the reference is what is claimed; accuracy is not. D108's “0.0 on every conformed case” was therefore a property of the FIXTURES — `y = 0.25x` sampled at multiples of 0.25 m has a float32-exact answer — and is a property of the CODE now. **The axis must be a coordinate axis for any of it to hold**: on a tilted axis the float32 ray origin does not lie on the double ray, the divergence is ALONG the ray (1.9e-06 m at 20 m, 1.5e-05 m at 20 km) and no reconstruction removes it, so `Surface.batchable` declines and the per-query reference serves that configuration alone. The generalisation: **when a native node offers the same answer as an absolute and as a delta, take the delta — its exponent is the size of the change, not the size of the world.** |
| D112 | **`place.build` takes ONE `ray` execution for the whole build, not one per curve.** `ray` rebuilds its second input on every execution, so the batch's fixed cost scales with the SURFACE (0.34 ms at 5 022 terrain prims, 2.25 ms at 80 352) and not with the query count. Paid per curve it made the citygen row **slower with the batch on than off** — 0.94–0.99x on four of five conformed rows — while looking like a 1.45x win on the single-curve fence it was measured on. Pass A is split in two (plan every curve → one batch → place), which also builds one `Surface` per build instead of one per curve. `ray_executions_per_build` pins it. The generalisation: **an item whose payoff is per CALL cannot be decided on a fixture that makes one call.** |
| D113 | **A trial that is SYMMETRIC ABOUT THE QUERY cannot see the parm that breaks the tie — found by mutation, in the check that claimed to pin it.** `ray_verb_semantics` names `bridge_deck` (ground y = -2, deck y = +2) and `exact_tie` (sheets at y = ±2) as the trials that hold D70's "look both ways, NEAREST wins". Flipping the verb's `bidirectionalresult` from `closest` to `farthest` left **all ten trials at exactly 0.0**: with the query at y = 0 both hits are equidistant, so the two readings are the same point, and the rule was caught only by `conform_parity` on one scene case (`BJ_conform_deck`, 3.4 m) — a fixture's luck, not a pin. A `deck_offcentre` trial (ground -2, deck **+3**) is added and the same mutation now reads 5.000e+00 m. The generalisation: **a trial can only see a rule it is capable of answering two ways — build the asymmetry in deliberately, and mutation-test the parm, not the code around it.** (A second, DECLARED survivor stands: `rtolerance` 1e-6 -> the node default 0.01 moves nothing in the whole suite, which the code says in place.) |

#### Cycle 12 — final state

`python -m pytest tests/unit -q` **284 passed, 9 625 subtests** ·
`hython tests/polychain/run_scene_checks.py` **87 cases, 0 failing** ·
`hython tests/polychain/run_hda_checks.py` **0 failing** ·
`hython tests/polychain/scale_gate.py` **9 rows, 0 failing**.
One file changed: `tests/polychain/run_hda_checks.py` (D107 — one word in the
fixture, plus the comment that explains why). **No kernel change, no baseline
change, no gate figure moved.**

---

## PHASE 1 CLOSING SUMMARY — read this first in the morning

**What phase 1 delivers.** `pf_polychain` is a working RailClone-L1S-class
modular assembly tool for Houdini 22 — vanilla, deterministic, metric. A spline
into input 1 and nothing else builds a fence. Four inputs (spline, kit, style
payload, surface), a 39-parm artist page in two disclosure levels with help and
units on every control, and a **pipeline face**: a style payload on input 3
overrides the whole page, so one payload builds one fence on any node. The
kernel is `polychain/{__init__,decompose,plan,corner,kit,place,conform,style,
hda}.py`; the asset is `polyfactory/otls/pf_polychain.hda`, regenerated by
`devScripts/create_pf_polychain_hda.py`.

Feature-wise: four fit methods (adaptive / tile / scale / count) with exact
end-fill; slots (default / start / end / corner / evenly / marker) dispatched
generically, so a style the code has never heard of builds; two corner
treatments (miter with a bisector cut, bend with a welded ring); fillets;
padding; per-element overrides including hero replacement; three z-modes
(vertical / stepped / adaptive) with §4.4's flatten-under and two hybrid level
bands; surface conform with camber; a proxy LOD; and warn-never-block throughout.

**The headline numbers.** 284 unit tests / 9 625 subtests · 87 scene cases /
5 063 checks / 0 failing · HDA wiring and UX-law checks 0 failing · a 9-row
scale ladder 0 failing. At scale: **10 005 packed pieces over 20 km, one
`geometryid`, 10 005 real points, +12 MB RSS, 0.42 s**, and the same on a
20 011-vertex resampled polyline. The deform path, when it is genuinely needed,
is 1.5 s for 10 000 pieces / 360 000 points — 7x faster than before D102's bulk
stamp. PC-G1's gate lands on its marker to **1.8e-07 m**.

**What is deliberately NOT built.** No junctions, forks or intersections — ever;
consumers author those. No massing. No content library beyond the starter kit.
No phase 2 (the 2D array, §7) — directional spec only. No VEX in the deform
loop: it was profiled, the loop is under 10 % of the row after D102, and
`nodeVerb` has no VEX verb on 22.0.398 (D103). RailClone's start-anchored
`stepped` behaviour is still the DEFAULT — the flatten-under and the level bands
are opt-in parms, so an untouched page builds what RailClone builds.

**What is owed.** Exactly one thing: **the GUI viewport pass on PC-G1 and PC-G2,
by Hannes.** Both gates are numerically complete and image-verified headlessly,
twice, through the parm page — but the live MCP bridge has been wedged since
2026-08-22 (main-thread HOM calls time out at 30 s), so nobody has looked at
this in a real viewport. ⚠️ **`/obj/polychain_gate` may still be sitting in the
GUI session** — delete that subnet and restart the bridge if a viewport pass is
wanted. Nothing was ever saved to the hip file.

**What the next agent should pick up first**, in order:
1. **Finding (10)** — `pc_u`, `pc_section` and `pc_variant` are asserted by
   nothing (cycle 12 §3B). One per-case check; the repro is exact. Smallest real
   hole in the suite.
2. **The deferred acceptance: citygen streets consuming polyChain** — the whole
   point of the tool, and the first consumer that will hit finding (7): a
   climbing run deforms under the starter `panel` at any radius, because
   `vertical` on a slope is a pure shear (D65). Not a defect, but it is what
   dressing a graded street actually looks like.
3. The standing findings list in §0.0 — (3), (4), (5), (7), (8), (9), (10).
   None of them blocks a gate; (5) (a picket-panel default) is the one an artist
   would notice first, and it is a cycle, not a patch.

---

## 11 Native/VEX/OpenCL port plan

**Status:** written 2026-08-22 from two independent audits (a profile audit and a native-SOP
inventory audit), both measured on Houdini 22.0.398 / hython, branch `polychain`, phase 1 closed
and all four gates green. **Nothing in this section has been implemented.** It is the ordered
brief for the agents that will do the porting, and it is deliberately honest about which items
are worth doing and which are not.

**The premise it was written against was wrong in two places, and both corrections change the
plan.** Read §11.0 before §11.2.

### 11.0 Two corrections, and one trap

**(a) The kernel is not "zero native SOP reuse". It is verb-only by design.** `place.py:138
_verb` already reaches two compiled SOPs through `hou.sopNodeTypeCategory().nodeVerb` - `clip`
(`_Proto.sliced` :629, `clip_plane` :1220) and `polyfill` (:634, :1227). D28 records this. What
the kernel has zero of is `createNode`, which is a different and more useful fact: **there is no
node network inside the builder, and every port below must keep it that way.** A verb executes
inside the Python SOP that already cooks; a node does not.

**(b) D103 IS RETRACTED. VEX is reachable from a verb, and 64-bit VEX is reachable too.** D103
(place.py's docstring, §0.0, cycle 10c) records *"`nodeVerb` has NO VEX verb at all on 22.0.398
(only `attribvop`, which needs a VOP network node)"*. That is false on this build. `attribvop`'s
`vexsrc` menu has `snippet` as its 4th entry with a `vexsnippet` string parm - arbitrary VEX, no
VOP network, executed through the verb. **Re-probed independently while writing this section:**

```python
v = hou.sopNodeTypeCategory().nodeVerb("attribvop")
v.setParms({"vexsrc": 3, "bindclass": 2, "vex_precision": "64",
            "vexsnippet": "@P.y = sin(@P.x*3.0); f@newattr = @P.x*2.0;"})
v.execute(out, [src])
```

Measured here: 40 000 points, **0.0805 s**, and it creates `newattr` as well as writing `P`, so
it is a full read/write pass and not just an edit. The inventory audit measured the same recipe
over 360 000 points at **0.0889 s** for a full frame rebuild and 0.0175 s arithmetic-only.
`vex_precision="64"` works through the verb and is **mandatory for this tool**: at 32 bits a
20 km arclength expression returns `0` where the answer is `-4.983e-04`.

**So both of D103's objections fall.** VEX is available, and using it does *not* mean putting a
node network back into a deliberately node-free builder. D103's *conclusion* - that porting
`_deform_positions` alone was not worth it after D102 - still stands on its own numbers (§11.2
P6 re-derives it); its *blocker* does not, and everything downstream of that blocker needs
re-deriving rather than citing.

**(c) The trap that produced (b): `nodeVerb` returns `None` for a verbless node, it does not
raise.** Probing with `try: cat.nodeVerb(n) except: ...` reports every node as having a verb.
The reliable probe is `v = cat.nodeVerb(n); v is not None`, and then an actual `execute`. Verified
this session: `chain`, `attribwrangle`, `copytocurves`, `pathdeform` all return `None` (they fail
later at `setParms` with `'NoneType' object has no attribute 'setParms'`); `attribvop`,
`copytopoints`, `ray`, `polyframe`, `clip`, `polyfill`, `attribcreate::2.0`, `resample`, `measure`,
`pack`, `blast`, `fuse`, `normal`, `boolean::2.0`, `polybevel::3.0`, `polysplit::2.0` all return
real verbs.

### 11.1 The verdict, per module and per kernel stage

The procedural-modeling skill's hierarchy applied literally: **native node first, then VEX, then
OpenCL only where the data is genuinely large and parallel, and Python only for small-N
orchestration, I/O adapters and the reference implementation.** The honest finding is that this
kernel's hot path is mostly the *fourth* thing the hierarchy does not name - per-element HOM API
calls - and that the biggest wins need no new language at all.

| File | Lines | Verdict | Reason |
|---|---|---|---|
| `__init__.py` | 527 | **KEEP PYTHON, fix one cache** | Contracts, `Curve`, `Marker`, kit schema. `Curve.sample` rebuilds its whole segment table per call - 8.2 ms at 20 001 verts against `place.Path.sample`'s cached 0.80 us. That is a caching bug, not a language problem (§11.2 P2). |
| `decompose.py` | 350 | **KEEP PYTHON** | Per-vertex but linear and cheap: `_clean` is 0.030 s on 20 001 verts, 2-5 % of any profiled row. Its cost is entirely its caller `Curve.sample` (2 calls per section, decompose.py:335/336). Nothing native fits - `resample` unshares points and interpolates point attributes (dev-loop trap list) so it cannot derive arclength on a curve whose topology is contractual, and `measure` is per-prim perimeter, not a per-vertex cumulative. |
| `plan.py` | 707 | **KEEP PYTHON - do not port** | This is the fitting *solve*, not per-element geometry: 5.4 % of the packed row, 4.5 % of the 300-street row, 10 000 pieces planned in 0.0003 s in the inventory audit's prototype. Native has no equivalent for exact-fill adaptive/tile/scale/count with `pc_pad` neighbour displacement, marker slots and compose rules. It runs with **no Houdini imported** (`tests/unit/test_polychain_plan.py`, 89 tests) - a property worth more than the microseconds. |
| `corner.py` | 1169 | **KEEP PYTHON - do not port** | 3.4 % of the corner-heavy case, < 0.4 % everywhere else. Small-N combinatorics per corner, and it is where the tool's correctness lives. The corner-heavy case is slow because of `Curve.sample` and the cut *glue*, not because of `corner.py`. |
| `kit.py` | 375 | **KEEP PYTHON** | Kit authoring and validation, once per cook at kit size, not per piece. `kit.box_mesh`'s hand-built boxes stay explicit construction (procedural-modeling rule 5). |
| `style.py` | 361 | **KEEP PYTHON** | The payload I/O adapter - exactly what the hierarchy reserves Python for. `style_round_trip` runs it on all 87 cases and it never shows up in a profile. |
| `hda.py` | 412 | **KEEP PYTHON, two bulk-write fixes** | Parm face + cook orchestration; measured HDA wrapper overhead over `place.build` is **~0 %** (0.933 s node cook vs 0.916 s direct call). But `colour_warnings` loops `prim.setAttribValue("Cd", ...)` over every prim, and `display = "plan"` cooks **1.55 s against the 0.93 s full build it is supposed to preview** (§11.2 P1). |
| `conform.py` | 317 | **PORT TO A NATIVE NODE (`ray` verb) + one VEX line** | `Surface.drop`/`_cast` is a Python loop over `hou.Geometry.intersect`. Conform is **90 % of a conformed build** (0.544 s of 0.607 s); `hou.Geometry.intersect` itself is only 4.9 % of it - the rest is glue (192 011 `hou.Vector3` constructions in `_cast` alone, 0.176 s). The `ray` verb reproduces it at **52-94x** with 0 hit-flag mismatches. |
| `place.py` | 1801 | **SPLIT** | The stamp and the per-piece geometry plumbing are API-bound and go to bulk writers (no new language). The deformed branch's materialisation is the one genuine **native-node + VEX** target (`copytopoints` + one `attribvop` snippet). `Path.sample` and the deform gate stay Python. |

Per kernel stage:

| Stage | Verdict | What actually changes |
|---|---|---|
| **§4.1 Decompose** | **Python**, with `Curve.sample` cached | Arclength table, corners, markers, sections. Keep. The sampler gets a memoised segment table and a `bisect` (P2). `polyframe` (0.0023 s on 20 001 pts) is *not* adopted: the tool needs a cumulative arclength table and per-side tangents at kinks, which it does not give. |
| **§4.2 Plan** | **Python. Do not port.** | Nothing. |
| **§4.3 Corners** | **Python** for the solve; bulk reads for the cut glue | `clip` + `polyfill` verbs stay (they are 6 % of the corner-heavy case; the Python around them is 6x that). `dress_caps`' per-vertex UV write is a VEX candidate but low priority - caps only exist on sliced/mitered pieces and `n_cut` is single digits across the suite. |
| **§4.4 Place + deform, packed branch** | **Bulk API writes; native `copytopoints` DECLINED** | The stamp goes bulk (P1). `copytopoints(pack=1)` measured 5.2x on the *materialisation* (0.0437 -> 0.0084 s) - but after P1 that materialisation is ~9 % of a packed row, and routing the transform through a float32 point attribute moves it by 4.34e-07 m, against a suite that asserts `marker_offset_m` at 1.788e-07 m. **Not worth the baseline movement. Declined, with the number, so nobody re-derives it.** |
| **§4.4 Place + deform, deformed branch** | **Native `copytopoints(pack=0)` + one `attribvop` VEX(64) pass** | The one place where the hierarchy's answer and the measurement agree: end-to-end prototype of the `arc_10` row, **0.2767 s vs the shipped 1.6559 s = 5.98x**, and it deletes the per-piece `hou.Geometry()` / `merge` / 149 954 `addAttrib` churn with it. The frame construction itself stays ours - nothing native expresses `vertical`/`stepped`, D98's flatten-under datum or D99's bands; the port moves that code from Python into VEX, it does not delegate it. |
| **§4.5 Conform** | **Native `ray` verb**, two-phase | See P5. Also deletes the unbounded `ConformPath._cache` (measured at **53 861 entries ~ 24 MB for one 2 km curve**). |
| **§4.6 Finalize** | **Bulk API writes** | One geometry-wide stamp instead of 14 calls per piece (packed) or 14 array writes per piece (deformed); `_declare` once instead of once per throwaway piece geometry. `polyfill` stays - `polycap` has **no verb** and is unreachable from a verb-only kernel. |
| **OpenCL, anywhere** | **NO - not in phase 1** | The largest parallel workload in the tool is the deformed branch's 360 000 points, which VEX does in **0.089 s**. Adding a GPU transfer and a second language to a sub-0.1 s stage is cost without payoff, and the per-piece work above it is small-N with data-dependent branching, which is the shape OpenCL is worst at. Revisit only for phase 2 (§7, the 2D array - N rows through the same kernel) or a consumer driving > 1e7 points. **Recorded as a decision so the next agent does not re-open it without a workload that justifies it.** |

### 11.2 The ordered work list

Ordered by **measured** payoff over risk. Each item names the checks that pin it. Numbers come
from the two audits; where the two disagree (the stamp bench: 39x vs 16.7x) both are given -
they measured slightly different things and neither is wrong.

**STATUS — §11 IS COMPLETE (2026-08-22, after three review rounds and TWO independent
verification passes, §11.8 P5V and P5cV):** P0, P1, P2, P3, P5R, **P5, P5b and P5c LANDED and
INDEPENDENTLY VERIFIED**; P4, **P6** and OpenCL **DECLINED** with their measurements (§11.8 P4/P6,
D109, D110). **P7 (bulk-read the miter glue) is the only item never attempted** and was rated low
priority. ⚠️ **The predicted "~1e-6 m of baseline movement" for P5/P6 never happened**: P6 was
declined and P5 lands at **0 moved values and `geometry_digest` unmoved on 0 of 89 cases**, because
D111 reads the `ray` verb's DISTANCE rather than its POSITION. §11.8 is the log and it carries
**corrected** figures for the P1 headline, P2's citygen label, P3's wall clock and D111's 20 km
number - read those before quoting anything from this section. **§11.9 is the handover brief for
phase 2 and is the thing to read next.**

**ACHIEVED vs PREDICTED, every landed item, measured against a worktree at the pre-port commit
(P5V, best of 5, two interleaved passes):**

| item | §11.2 predicted | achieved | verdict |
|---|---|---|---|
| **P0** tripwires + the three unasserted stamps | no speedup; close finding (10) | no speedup; finding (10) closed **and** `pc_variant` found never exercised (`DL_variant_kit`) | **DONE, over-delivered** |
| **P1** bulk stamp | `0.933 -> ~0.40 s` on the packed row | the 0.933 baseline **did not reproduce**; real row **0.705 -> 0.393 s (1.81x)**; `stamp_calls_per_piece` 14.005 -> 0.005 | **DONE**, the ratio was wrong, the win is real |
| **P2** `Curve.sample` memo + bisect | `8 218 us -> ~1 us`; `4.32 s -> ~0.65 s` corners | **7 966 -> ~0.95 us (8 000x)**; `corners_200` **11.98 -> 0.97 s (12.3x)**; `streets_300` **nil** | **DONE**; the "citygen shape" label was wrong and is corrected |
| **P3** shared bend stations | 8-10 % of the deformed row | `Path.sample` calls **-37.8 % exactly**; wall clock **-1 to -2.6 %**; `conform_cache_per_element` 23.85 -> 17.55 | **DONE as a correctness/allocation cleanup**, not a 10 % row |
| **P4** one output geometry | ~9.9 % of the deformed row | P1 already took 93 % of it; honest ceiling **~5.7 %** at MEDIUM risk | **DECLINED, with the measurement** |
| **P5R** `span_ends` + 3 API fixes | *(no item existed)* | packed row **16.92 -> 6.92 `Path.sample` per piece (-59 %)**; `_stamp_bulk` peak **49.5 -> 7.6 MB** | **DONE**; its own tripwire was missing and is added in P5V |
| **whole port** | "2.10x on the real node cook" | **1.81x** packed, **2.50x** citygen streets, **12.3x** corner-heavy, **2.48x** Display=Plan, **1.44x** deformed; `geometry_digest` unmoved on all 87 pre-port cases | **DONE** |

---

**P5R - `span_ends`: the PACKED branch was asking the same two questions six times. LANDED.**
*(This list had no item for the packed branch at all, which is the branch PC-G3 and every citygen
street actually run. A reviewer found it by counting.)*

- **What changed:** `_flat_ratio`, `_chord_ratio`, `span_deviation`, `_needs_deform`'s shear test,
  `_packed_transform` and the report's `plan_pos` each opened with `path.sample(s0r)` forward and
  `path.sample(s1r, forward=False)`. Pass A takes the pair once into `span_ends` and threads it -
  bounded, no cache, dropped the moment pass B consumes it, and anchored pieces are excluded so a
  `ConformPath` is never asked for a drop nobody needed.
- **Payoff, measured:** the 20 km packed row goes **169 232 `Path.sample` calls -> 69 232**
  (16.92 -> 6.92 per piece, -59 %), and with the two API fixes beside it (`intrinsicValue`
  instead of `len(prims())`, and the discarded head read) `scale_gate` arc_80/kit reads
  **0.442 -> 0.396 s** and bench `arc_10` **1.424 -> 1.260 s**. That is more than P3 bought on the
  deformed row, on the branch every gate is measured on.
- **Risk:** LOW, and it moved **zero** baseline values. The pair is the same call with the same
  argument, so this is arithmetic identity rather than tolerance.
- **Pinned by:** the whole geometry suite - reading the pair for the WRONG end of the span is RED
  on **205 checks** - plus `plan_points`, `plan_point_provenance` and `over_unpacked`.

---

**P0 - Close the three unasserted stamps, and commit the port's own tripwires. No speedup.**
*(Prerequisite. Do this before touching a writer.)*

- **What changes:** (i) §0.0 standing finding (10) - `pc_u`, `pc_section` and `pc_variant` are
  asserted by **nothing**; corrupt any of them in *both* writers and the suite reports 87 cases,
  0 failing, 0 baseline moves. **Every item below rewrites a stamp writer.** Porting a writer
  while 3 of its 14 values are unasserted is porting blind. One per-case check that reads each of
  the three back against the plan the piece came from. (ii) Three measurements from the audits
  become standing checks, per `tests/README.md`'s compounding rule: `stamp_calls_per_piece` (count
  HOM attribute-write calls per piece - the thing P1 is *for*), a `Curve.sample` cost-vs-vertex-count
  assertion (P2's whole point; it must be O(1) per call, not O(n)), and a bound on
  `ConformPath._cache` size (P5 deletes the cache; nothing currently notices it growing).
- **Payoff:** none in seconds. It is what makes every later item provable.
- **Risk:** LOW. New checks only, no production code.
- **Pinned by:** itself. Mutation-test each new check the way cycles 11/12 did - corrupt the value
  in both writers and confirm the new check goes red.

---

**P1 - Bulk-write every surviving per-element stamp. The biggest single win in the tool.**

- **What changes:** `place._stamp` (place.py:1444) writes 14 attributes one `hou.Prim.setAttribValue`
  at a time, once per packed piece - **2.19 us per call x 14 x N**. D102 fixed exactly this for the
  *deformed* writer (`_stamp_geo`) and the packed branch, which is what PC-G3's headline row and
  every citygen shape actually runs, was never converted. Replace with an accumulate-then-write
  pass: collect the 14 (+ warn) value arrays across the whole output during pass B, then one
  `setPrim{String,Int,Float}AttribValues` per attribute at the end. `_stamp_values` is already the
  single source of truth for both writers, so this adds no third description. Same fix, same pass,
  for `place.plan_points` (15 point attributes per piece, one call each) and `hda.colour_warnings`
  (per-prim `Cd`).
- **Payoff, measured:** the stamp is **62 % of the packed 20 km row, 59 % of the 300-street row,
  and 62 % of the real HDA node cook**. Isolated: 10 000 prims x 14 attrs, **0.3063 s -> 0.0079 s
  (39x)** with identical values; the inventory audit's variant measured 0.3008 -> 0.0180 s (16.7x).
  On the real node: **0.933 s -> ~0.40 s expected**. `Display = Plan` - the interactive preview -
  currently cooks **1.55 s against the 0.93 s full build it previews**; this is the whole reason.
  D82's proxy LOD is also nearly worthless today (0.87 s vs 0.93 s, ~7 %) precisely because the
  cost is the stamp and not the geometry - P1 is what makes the LOD mean something.
- **Risk:** **LOW, and it is the only item with zero expected baseline movement.** No geometry is
  touched, no maths, no float format. Two things to get right: prim ordering (the accumulated
  arrays must line up with `out`'s prim numbering after every `merge`, so accumulate *lengths* as
  you go rather than assuming), and `_declare` must still run before the first write so warn
  attributes exist.
- **Pinned by:** `stamp_parity` (all 87 - it exists to prove the two writers agree),
  `output_schema` (87), `warn_summary` (87), `warnings` (87), `kit_warnings` (87), P0's new
  `pc_u`/`pc_section`/`pc_variant` check, `plan_points` (87), `determinism` (87), and
  **`geometry_digest` (87), which must NOT move.** In the HDA suite: `run_hda_checks.py`'s
  display-mode and warning-colour rows.

---

**P2 - Memoise `Curve.sample`'s segment table.**

- **What changes:** `__init__.py:269` builds `segs` - the full per-segment table - on **every
  call**, then linear-scans it. `place.Path` is the cached twin that already exists in this repo
  (built once in `__init__`, then `bisect`). Cache the table on `Curve` the same way `_cumulative`
  is already cached, and switch the scan to `bisect`.
  WARNING: **do NOT "just point `decompose` at `place.Path`"** (the profile audit offers this as an
  alternative). The two samplers are deliberately not identical: `Path.sample` **extrapolates**
  past an open curve's ends (D30, and there is a measured defect behind it - a 1.6 m gate crushed
  to a 1.11 m zero-thickness plane), while `Curve.sample` clamps. Swapping them changes end
  behaviour on every section frame. Cache in place; keep the semantics.
- **Payoff, measured:** 3.2 us at 10 verts -> **8 218 us at 20 001 verts**, against `Path.sample`'s
  flat **0.80 us** - 10 241x at PC-G3's own input. It is **83 % of the cumulative time** of the
  20 km-resampled + 200-corner run, which at **4.322 s is the worst case either audit found**.
  200 corners on that run cost **+3.67 s** over the same run with none.
  Expected after: ~4.32 s -> ~0.65 s.
- ⚠️ **THE "REAL CITYGEN SHAPE" LABEL WAS WRONG, and the third review round measured it.** The
  200-corner fixture is a SINGLE 20 km curve with 1 198 samples over ONE table - a corner-density
  case, and P2 is worth 10x on it. citygen hands this tool **hundreds of separate short
  polylines**, and `Curve.sample` is called exactly **2x per section**: on 300 x 60 m streets that
  is 600 samples over 300 curves, one hit per table, and P2's measured contribution to
  `streets_300` is **0.260 -> 0.261 s, i.e. nil**. On the 20 km single-curve packed row it is 2
  samples over 1 curve, ~1.5 ms of a 470 ms build. P2 is still right and still cheap; what it buys
  is the corner-dense case, not the many-short-streets one. The cold cost that shape actually pays
  - constructing the table - P2 made ~9 % SLOWER (it builds `his` alongside `segs`), and
  `curve_sample_scaling`'s warm-only reading could not see that at all until the third round gave
  it a second, cold reading.
- **Risk:** **LOW-MEDIUM.** The cache assumes `Curve.points` is not mutated after the first sample -
  which `_cumulative` already assumes, so this adds no new assumption, but say so in the docstring.
- **Pinned by:** **`sampler_matches_kernel` (all 87)** - it exists to assert that the cached
  sampler and the kernel's own agree about where a metre is, which is precisely this change;
  plus `section_coverage_m`, `exact_fill_m`, `corner_turns`, `corner_abut_m`, `corner_seam_m`,
  `geometry_digest` (must not move), and `tests/unit/test_polychain.py`'s decompose tests.

---

**P3 - Stop sampling the path twice for the bend-resolution warning.**

- **What changes:** `place._bend_deviation` (place.py:1090) samples the path **24 times per piece**
  to produce a number used only to raise `pc_warn_bend_resolution` - more sampling than the deform
  itself does (10 per piece). Its `pa`/`pb` per station gap are the *same* stations
  `_deform_positions` rebuilds; only the midpoint `pm` is extra. Compute the station positions
  once per job and let both consumers read them.
  WARNING - ordering constraint: the warning is decided in **pass A** because `warn_names` is
  collated and `_declare`d before pass B runs. So this is "share the samples", not "move the
  pass" - sample the stations once into the job dict in pass A and have pass B reuse them. (If P6
  lands, the deviation folds into its VEX pass instead and this item disappears.)
- **Payoff, measured:** `_bend_deviation` is **cum 20 % of the deformed row profiled, ~15 % clean**.
  Sharing removes the 2-of-3 samples that are duplicates; **expect 8-10 % of the deformed row**,
  not 15. Stated conservatively on purpose.
- **Risk:** **MEDIUM.** The warning must fire on exactly the same pieces it fires on today. It is
  a *warning*, so a silent change is invisible in geometry checks.
- **Pinned by:** `warn_summary` (87) and `warnings` (87) - `pc_warn_bend_resolution` counts are in
  the baseline per case, so a changed trigger moves a recorded value; plus `curvature_budget_m`,
  `deform_gate_m`, `packed_true_dev_m`.

---

**P4 - One output geometry for the deformed branch; declare attributes once.**

- **What changes:** the deformed branch builds `hou.Geometry()` + `merge(src)` + `_declare` +
  `out.merge(piece)` **per piece** - **150 014 `addAttrib` calls for 10 000 pieces**, re-declaring
  the same 14 attributes on 10 000 throwaway geometries. Build all deformed pieces into one
  geometry with attributes declared once. Pieces that take a corner **cut** keep their own
  geometry (the `clip` verb operates on a whole geometry), so this is a hybrid, not a blanket rule.
- **Payoff, measured:** **21 % of the deformed row, 33.6 us/piece**; `_declare` alone is 0.325 s
  cum on the `arc_10` row. It also makes P1's whole-output stamp free on this branch (14 calls
  total instead of 14 per piece - `_stamp_geo` is still **36 % of the deformed row, 57.1 us/piece**,
  of which 7 string writes at 4.26 us dominate).
- ⚠️ **STALE. P1 COLLECTED THIS ITEM'S HEADLINE AND P4 IS DECLINED - see 11.8.** Measured on one
  machine in one session, the same row both ways: at P0 `hou.Geometry.addAttrib` is **149 955
  calls / 0.163 s / 9.9 % of a 1.655 s row** (this section's 150 014, reproduced); after P1 it is
  **10 011 calls / 0.013 s / 1.0 %**, because P1 deleted the per-piece `_declare` outright. What is
  left of P4 is `out.merge(piece)` **0.067 s (4.8 %)**, `piece.merge(src)` 0.017 s, and 9 996 bare
  `hou.Geometry()` constructions 0.013 s - **8.0 % of the row in total, ~5.7 % of it recoverable**,
  at MEDIUM risk, on a branch no gate is measured on. Do not re-derive the 21 %.
- **Risk:** **MEDIUM.** Prim/point numbering and `pc_local` must survive the change; the cut branch
  must stay separate.
- **Pinned by:** `element_count`, `duplicate_elem_ids`, `deformed_flag_mismatch`, `open_edges`,
  `slice_caps_closed`/`cap_prims`, `cap_uv_m`, `module_fidelity_m`, `geometry_digest` (must not
  move), `determinism`, plus the corner suite (`corner_wedge_m2`, `corner_breach_m`, `corner_welds`).

---

**P5 - Replace `Surface.drop` with the `ray` SOP verb, batched.**

- **What changes:** `conform._cast` casts one `hou.Geometry.intersect` per query in Python, twice
  (down-axis then back-axis) with 2 `hou.Vector3` constructions each, memoised into an unbounded
  dict keyed on `(round(s,9), forward)`. Replace with **one `ray` verb execution over a batched
  point cloud**: `method=project`, `dirmethod`/`dir` from `Params.conform_axis`,
  `reverserays=bidirectional`, `bidirectionalresult=closest`, `putnml=1`, `newgrp=1` (the hit
  flag), `rtolerance=1e-6`.
  **This needs a two-phase refactor, and the shape of it matters:** `ConformPath` is a *lazy*
  sampler queried from inside plan/place decisions. The safe form is a **prefetch**: after the plan
  exists, enumerate every arclength that will be asked for (each piece's `proto.fracs` stations
  across its span, the +/-`delta` finite-difference partners, the `deviates`/`missed` probes, the
  anchor drops), run one `ray.execute`, fill `_cache` from the result, and **leave the existing
  per-query Python path in place as the fallback for any key the prefetch missed.** That makes the
  port additive: a missed key is slow, never wrong - and it puts both implementations in one
  process, which is where the parity check gets to ask both (§11.3 rule 4).
- **Payoff, measured:** 20 000 drops **0.1045 s -> 0.0020 s (52x)**; the profile audit's 54 000-point
  variant **0.2755 s -> 0.0029 s (94x)**. Conform is **90 % of a conformed build** and `drop` alone
  is **40 % of the 2 km fence case's clean wall clock**. ~~It also deletes the 24 MB memo
  cache~~ - ⚠️ **THIS DID NOT HAPPEN AND MUST NOT BE PLANNED AGAINST.** P5 KEPT the memo,
  made it the batch's destination and filled it EAGERLY, which took `conform_cache_per_element`
  UP (17.55 -> 18.7) and the peak working set of the conformed street row up **+209 MB**
  (897.4 -> 1 106 MB, fresh hython, kernel32 peak working set). Dropping the gap midpoints from
  the enumeration returns most of it: 917 MB, i.e. +20 MB over pre-P5. See §11.8 P5c.
- **Risk:** **HIGH - the highest of any item here, and the first one that WILL move baselines.**
  Three named differences: (i) agreement with `hou.Geometry.intersect` is **9.5e-07 m max |dP|**
  over every drop a real PC-G2-shaped case makes (862 drops x 3 z-modes, 0 hit-flag mismatches) -
  float32 storage noise, not a wrong answer, but `conform_contact_m` currently baselines at
  **exactly 0.0** and `geometry_digest` hashes positions at **`%.6f`**, so **both will move on
  every conformed case**; (ii) **the `ray` verb does not do D52's normal flip** - max |dN| **1.935**,
  a sign flip; on `abs` it agrees to 1.25e-07. The flip must be re-added as one VEX line (or one
  bulk Python pass) or every camber on a back-facing polygon rolls upside down; (iii) D70's
  tie-breaking ("a tie goes down-axis, because the stage is a drop") and D53's miss semantics
  ("a miss keeps the unprojected position") must be re-derived on the verb's `bidirectionalresult`
  rather than assumed. **Decide the baseline movement explicitly before starting, and record the
  decision.** The defensible position: accept movement <= 1e-6 m as float32 noise, re-baseline the
  conformed cases in a commit that does nothing else, and require every *metric* check to stay
  green at its own tolerance while doing it.
- **Pinned by:** `conform_contact_m` (87, tol 2e-3, baselined 0.0), `conform_drape_m` (87),
  `conform_misses` (87), `camber_deg` (87), `warn_summary` (`pc_warn_conform_miss` counts),
  `stepped_float_m` (87), `band_datum_m` (87), `deform_gate_m` (87), `geometry_digest` (87 - will
  move on conformed cases), and D70's bridge-deck case (ground y=-2, deck y=+2), which the audit
  re-ran at 8 probes and which is the one case a naive `first hit` port gets wrong.

---

**P6 - The deformed branch: `copytopoints(pack=0)` + one `attribvop` VEX(64) pass.**

- **What changes:** the whole of pass B's deformed path. Emit one target point per piece carrying
  its solve (arclength span, scale, z-mode, band, datum, tilt), `copytopoints` the module geometry
  onto them unpacked, then **one `attribvop` snippet in 64-bit** rebuilds every point's position
  from the per-station frame - the same maths `_deform_positions` (place.py:1245) does, moved from
  Python into VEX - followed by one VEX prim-promote for the stamp. This **absorbs P3 and P4**.
- **Payoff, measured:** end-to-end prototype of the `arc_10` row producing the same output size,
  **0.2767 s vs the shipped 1.6559 s = 5.98x** (359 820 vs 359 856 points, 339 830 vs 339 864
  prims - *not* the same output, see risk). Split: plan 0.0003 / target points 0.021 /
  `copytopoints` 0.126 / **VEX deform 0.089** / VEX stamp 0.031.
- **Risk:** **HIGH, and it is a cycle, not a patch.** (i) `vex_precision="64"` is **mandatory** -
  at 32 bits a 20 km arclength expression returns 0. (ii) The prototype's point and prim counts
  differ from the shipped build by 36 and 34 - small, but **not zero, and nobody has explained
  them**; that must be understood before it lands, not after. (iii) The three z-modes, D98's
  flatten-under datum and D99's bands are our own frame construction and must be transcribed into
  VEX exactly; the deformed branch is where `plumb_deg`, `flat_stepped_m`, `band_hybrid_m` and
  `band_datum_m` all live, and each of those has a cycle-11/12 defect behind it. (iv) Corner-cut
  pieces still need the `clip` verb per piece, so they stay on the old path. (v) `Path.sample`
  stays in Python for the gate; the VEX pass should be handed the station frames it needs rather
  than re-deriving arclength in VEX - if it re-derives, **the two samplers must be proven to agree**
  and that is a second parity problem nobody asked for.
- **Honest ceiling, so this is not oversold:** the deformed branch is **1.58 s of a suite whose
  headline case is 0.49 s**, and PC-G3's own row is 100 % packed. This item is worth ~1.3 s on the
  *deformed* workloads and **nothing at all** on PC-G3, the citygen street case, or any packed run.
  D103's original judgement - that the per-point deform is a small share - is re-confirmed by the
  profile audit independently (`_deform_positions` is **18 % of the deformed row, 0.81 us/point**,
  and 26 % of *that* is its own `Path.sample` calls). What makes P6 worth doing is not the deform;
  it is that `copytopoints` deletes the per-piece geometry churn (P4) and the bulk stamp lands for
  free. **Do P1-P5 first and re-measure before starting P6.**
- **Pinned by:** everything P4 is pinned by, plus `plumb_deg`, `flat_stepped_m`, `bank_deg`,
  `band_hybrid_m`, `band_datum_m`, `stepped_riser_m`, `stepped_float_m`, `axis_on_curve_m`,
  `cross_section_m`, `frame_dot_min`, `station_spacing_m`, `min_piece_span_m`, `rigid_deformed`,
  `over_unpacked`, and the scale ladder (`scale_gate.py`, 9 rows under both z-modes).

---

**P7 - Bulk-read the miter glue and `dress_caps`. Low priority.**

- **What changes:** `clip_plane` + `dress_caps` are **40 % of the corner-heavy case**, of which the
  native `clip` + `polyfill` verbs are **6 %** - the surrounding Python (`Prim.points()`,
  `Point.position()`, per-vertex `setAttribValue`) is 6x the verbs' cost. Bulk attribute reads and
  writes, or one `attribvop` UV pass. **Not** `uvproject`: it would fight the `pc_local`
  box-mapping D59 needs.
- **Payoff:** meaningful only on corner-dense runs, and P2 already takes that case from 4.32 s to
  ~0.65 s. Do it last or not at all.
- **Risk:** MEDIUM (winding and cap tagging).
- **Pinned by:** `cap_uv_m`, `cap_prims`, `slice_caps_closed`, `corner_plane_dev_m`,
  `corner_face_mate_m`, `corner_wedge_m2`, `inward_faces`.

---

**Explicitly declined, with the numbers, so they are not re-derived:**

| Declined | Measured reason |
|---|---|
| `copytopoints(pack=1)` for the **packed** branch | 5.2x on the materialisation (0.0437 -> 0.0084 s), but that is ~9 % of a packed row **after P1**, and the transform routes through a float32 point attribute (4.34e-07 m) against `marker_offset_m` baselined at 1.788e-07 m. Cost in baseline movement exceeds the payoff. |
| `polycap` instead of `polyfill` | **No verb.** Unreachable from a verb-only kernel. `polyfill` is already the right node. |
| `boolean::2.0` instead of `clip` | A bisector is a half-space; `clip` is the exact primitive and two inputs cheaper. Keep `boolean::2.0` in mind only if a non-planar cut ever appears. |
| `resample` / `measure` for the arclength table | `resample` **unshares points and interpolates point attributes**; the topology is contractual here. `measure` is per-prim perimeter, not a per-vertex cumulative. The Python table is 0.0090 s for 20 001 points - cost was never the problem. |
| `polyframe` for the frames | Gives `tangentu` + `N` in 0.0023 s, but not per-side tangents at a kink, which decompose's section frames require. |
| OpenCL, anywhere in phase 1 | The largest parallel stage is 360 k points at 0.089 s in VEX. |
| `pathdeform`, `copytocurves`, `bend`, `chain` | **All verbless** - see §11.6. |

### 11.3 Parity strategy - how each port is proven equivalent

**The Python stays. It is the reference implementation, and that is a permanent decision, not a
transition arrangement.** Every item above replaces a *call site*, not a description: the
description (`_stamp_values`, `_deform_positions`, `Surface.drop`) remains importable, testable
without Houdini where it already is, and runnable as the fallback path.

Five rules, in the order a porting agent applies them:

1. **Two writers, one description - the D102 pattern, reused.** `_stamp_values` is already the
   single source of truth for the per-prim and the bulk stamp, which is why `stamp_parity` can
   prove them equal on all 87 cases. Every port follows that shape: the ported path and the Python
   path derive from one description, and a per-case check compares their outputs. `stamp_parity` is
   the template; write `conform_parity` and `deform_parity` the same way.
2. **Parity is asserted per case, in the committed suite, not in a scratchpad.** Cycle 11 finding
   (D) is the precedent: D102's bulk-stamp parity proof *was* a scratchpad run, every check read a
   stamp from an element's **first** prim, and corruption on prims 2..n was invisible until
   `stamp_parity` was committed. A parity run that is not in `tests/polychain/checks.py` did not
   happen.
3. **Mutation-test every parity check before trusting it.** Corrupt the ported path by the
   tolerance you claim to detect (1e-6 on every element, and separately on elements 2..n only)
   and confirm the check goes red. Cycle 12 did exactly this and found `stamp_parity`'s blind spot
   and PC-G4's blind fixture. A parity check that cannot fail is decoration.
4. **The fallback is the parity harness.** P5's prefetch design (batched `ray` fills the cache,
   Python `intersect` serves anything the prefetch missed) means both implementations are live in
   one process, so parity can be asserted by *asking both* rather than by diffing two runs. Prefer
   that shape wherever it is available.
5. **Every port lands in its own commit, with the baseline diff read line by line.** Never a port
   and a re-baseline in the same commit as anything else.

**Where float32-vs-float64 divergence is expected, and what tolerance is defensible:**

| Port | Expected divergence | Defensible tolerance | Why |
|---|---|---|---|
| P1 bulk stamp | **exactly 0** | 0 - assert bit-identical | Same values, same types, different call shape. D102 achieved bit-identical on all 83 cases doing this to the other writer. |
| P2 `Curve.sample` cache | **exactly 0** | 0 - assert bit-identical | Same arithmetic, same order; only the table's lifetime changes. |
| P3 shared stations | **exactly 0** on geometry | 0 on geometry; warning counts must match exactly | It reuses the same samples. |
| P4 one geometry | **exactly 0** | 0 | Container change only. |
| P5 `ray` verb | **<= 9.5e-07 m** on position; hit flags identical (0 mismatches over 862 real drops x 3 z-modes); normals identical on `abs` to 1.25e-07 after the D52 flip is re-added | **1e-6 m**, and say so | float32 storage floor at these coordinates. It sits *inside* the suite's `TOL_M = 1e-4` but **outside** `geometry_digest`'s `%.6f` and outside `conform_contact_m`'s baselined 0.0 - so metric checks stay green while recorded values move, and that must be stated in the commit rather than discovered in the diff. |
| P6 `copytopoints` + VEX(64) | position parity **not yet measured** (the prototype produced a different point count); frame maths in 64-bit should agree to ~1e-9, the float32 *storage* of `P` floors it at ~1e-7 | **1e-6 m**, provisional - re-derive it on the real port | 64-bit VEX is mandatory (32-bit returns 0 for a 20 km arclength expression). The unexplained 36-point / 34-prim delta must be resolved before any tolerance is agreed. |

**The honest sentence about `geometry_digest`:** it hashes world positions at `%.6f`, so it is a
1 um tripwire. P1-P4 must not move it at all. P5 and P6 will move it on every affected case, and
"0 baseline values moved" is not available for them - claiming otherwise would be the failure mode
this section exists to prevent.

### 11.4 What must NOT change

| Invariant | What would catch a regression |
|---|---|
| **The 87 scene cases / 5 063 baselined values** | `hython tests/polychain/run_scene_checks.py`. Read the movement list; **never** `--update-baseline` in the same commit as a code change unless the commit does nothing else and every moved number is explained (P5/P6 only). |
| **§3.1 input schema** (`pc_corner`, `pc_section`, `pc_style`, markers) | `modules_by_curve`, `marker_offset_m` (1.788e-07 m), `duplicate_curve_id_warn`, `run_hda_checks.py`'s input wiring rows. |
| **§3.2 kit format** | `kit_warnings` (87), `module_fidelity_m` (87), `cross_section_m` (87), `tests/unit/test_polychain.py`. |
| **§3.3 style payload** | `style_round_trip` (87), `style_payload_degrades`, and `run_hda_checks.py`'s `parms_inert_under_payload` sweep - **which is `adaptive` since D107 and must stay so**; a `scale` fixture made that sweep blind for a whole cycle. |
| **§3.4 output stamp - all 14 names** | `output_schema` (87), `stamp_parity` (87), `zmode_stamp`, and **P0's new check for `pc_u`/`pc_section`/`pc_variant`, which is why P0 is first.** |
| **The two-face principle (§2.1)** | `style_round_trip` on all 87 + the PC-G4 sweep. A port must not introduce a branch that reads a style *name*: `polychain/style.py` contains no style name and no branch per name, and the grep over the kernel is part of the gate. |
| **Determinism** | `determinism` (87 - same inputs twice, identical positions *and* ids) and `geometry_digest` (87 - the cross-session half, the `PYTHONHASHSEED` class of defect). **A batched port is a reordering**, so this pair is the check that matters most for P5/P6: never let a hit order or a merge order reach a value. |
| **Warn-never-block** | `warnings` (87), `warn_summary` (87), `kit_warnings` (87). No verb may be allowed to raise into the cook: `hou.Geometry.intersect` never raised on a degenerate surface; a verb can, and one exception replaces the whole fence with nothing. **Wrap every new verb call.** |
| **PC-G1 the fence** | `exact_fill_m`, `max_gap_m`, the 12 `corner_*` checks, `marker_offset_m`, all four fill modes x both corner modes. |
| **PC-G2 the hill** | `plumb_deg` (0.0), `flat_stepped_m` (0.0), `bank_deg` (non-zero), `conform_contact_m`, `conform_misses`, `camber_deg`, `stepped_float_m`, `band_datum_m`. |
| **PC-G3 at scale** | `hython tests/polychain/scale_gate.py` - 9 rows under both z-modes, plus `packed_pieces`, `over_unpacked`, `deform_gate_m`, `packed_true_dev_m`, `curvature_budget_m`, and `A_straight` / `CE_all_packed` / `CF_resampled_straight` / `CG_resampled_bendable` asserted 100 % packed. **One shared `geometryid` is the property; a port that quietly stopped sharing the source geometry would pass every metric check.** Add that assertion if it is not already there. |
| **PC-G4 the pipeline face** | `run_hda_checks.py` in full. |
| **The verb-only kernel** | No `createNode` anywhere in `polychain/`. Grep it in the gate. |

Run order after every port step, no exceptions:
`python tests/unit/test_polychain*.py` -> `hython tests/polychain/run_scene_checks.py` ->
`hython tests/polychain/run_hda_checks.py` -> `hython tests/polychain/scale_gate.py`.

### 11.5 Honest risks

1. **Precision is the live risk, not a footnote.** The suite asserts to 1.788e-07 m in one place
   and hashes to 1e-6 m in 87. `copytopoints` routes transforms through a float32 attribute
   (4.34e-07 m); the `ray` verb disagrees with `hou.Geometry.intersect` at 9.5e-07 m. Both are
   float32 noise at these coordinates, not wrong answers - but **"0 baseline values moved" will not
   survive P5 or P6**, and any plan that promises it is lying.
2. **`ray` does not reproduce D52's normal flip.** Max |dN| = 1.935 - a sign flip. Camber rides
   the normal; a missed flip rolls modules upside down on any back-facing polygon, and the suite's
   camber check (`camber_deg`, tol 0.05) is loose enough that a *partial* miss could hide.
3. **Batching is reordering, and reordering is where determinism dies.** P5 and P6 both replace
   per-query / per-piece work with one bulk call. Any place where a result's *index* is used as an
   identity, or where a dict iteration order reaches a value, becomes a cross-session defect that
   only `geometry_digest` can see. Cycle 1 already killed one `PYTHONHASHSEED` defect in this
   kernel.
4. **A verb can raise where the HOM call did not.** Warn-never-block is a contract (D24, D34, D53).
   Degenerate input - an empty surface, a zero-length span, a single-point curve, a NaN in the kit -
   must reach a warning, not a traceback. Every new verb call gets a try/except that degrades to the
   Python path.
5. **`polyfill`'s new prims inherit neighbour attribute values** (D28's plane-test cap tagging
   exists because of it). Any change to how prims are stamped (P1, P4, P6) must keep the cap tagging
   correct - `cap_prims` and `cap_uv_m` are the pins, and they only exist on 3 cases.
6. **The prototype in the inventory audit is not the port.** It produced 359 820 points where the
   shipped build produces 359 856, and 339 830 prims where the shipped build produces 339 864.
   Nobody has explained the 36/34. It is small enough to look like a rounding difference and large
   enough to be a dropped piece. **Resolve it before P6 lands.**
7. **The two audits disagree on the stamp's speedup (39x vs 16.7x).** They benched slightly
   different things. Do not quote either as *the* number in a commit message - re-measure on the
   real node cook, which is the figure that matters (0.933 s today).
8. **`Curve.sample`'s cache assumes immutability.** So does `_cumulative`, so this is not new, but
   a future feature that mutates a `Curve` in place would silently serve stale geometry.
9. **The 11 s case in the old notes is stale.** Post-D102 the R = 10 m row is **1.58 s**, not 11 s.
   Anyone planning from the older number will over-value P6 by a factor of seven.
10. **Scope creep is the biggest project risk here, not any single port.** P1 + P2 are two small,
    low-risk diffs that between them take the dominant packed workload from 0.49 s to ~0.19 s and
    the worst-case citygen run from 4.32 s to ~0.65 s, with zero expected baseline movement. P5 and
    P6 are cycles with baseline consequences. **The tool's actual owed work is the GUI viewport pass
    and the streets acceptance, not this port.** Land P0-P2, re-measure, and only then decide
    whether the rest is worth a cycle.

### 11.6 The Chain SOP question - PC-G0's fork decision should be RETIRED

**Recommendation: mark PC-G0's "fork the network" resolution superseded in §2.3 and §6, and record
that the kernel will not fork Chain - now or later.** The build ignored the decision (grep: **zero
references to `chain` anywhere in the kernel**) and the measurements say it was right to.

- **Chain never produces packed prims.** Same 20 km run: Chain gives **12 011 652 points /
  11 344 338 prims in 3.421 s**; polyChain gives **10 000 packed prims, one `geometryid`, 0.55 s**.
  A 1 200x point-count difference. **PC-G3's entire headline is unreachable through Chain.**
- **It emits no attributes at all** (`point attribs: ['P']`, `prim attribs: []`) - nothing for
  §3.4's 14-name stamp to ride.
- **Its default fit does not fill exactly** - bbox x -0.362..24.324 on a 24.881 m curve, against a
  suite that asserts exact fill to 1e-9 m in all four modes.
- **It has no verb** (`nodeVerb("chain")` returns `None`, verified this session), so forking it
  forces the whole kernel into a node network - giving up the property that makes P1-P6 possible
  in the first place.

What survives of PC-G0 is what §2.3 actually says is load-bearing: **Chain's *parameter model***
- piece patterns, fit modes, rigidity, boundary behaviours - **remains the base-layer spec the
kernel extends.** Its *network* is the wrong seed. Same verdict, same reasons, for the other two
RailClone-shaped natives: **Copy to Curves** (no verb; carries `upvectorattrib`,
`transformbyattribs` and a `pack` toggle - a native camber carrier, worth a second look *only* if
the HDA is ever restructured into a network, and then only for `adaptive`) and **Path Deform** (no
verb; `usepiece`/`pieceattrib`/`posoffsetattrib` would deform many pieces in one cook). Neither
expresses `vertical`/`stepped`, D98's flatten-under datum or D99's bands.

### 11.7 The one-paragraph summary for whoever implements this

The kernel's hot path was never the geometry maths, and porting the maths to VEX is the *last*
thing worth doing, not the first. **Sixty-two percent of the real HDA node cook is 14
`hou.Prim.setAttribValue` calls per packed piece** - the fix D102 already applied to the other
writer and never applied here - and it is a bulk-array diff with zero expected baseline movement
(P1). **The second-biggest cost is a caching bug**: `Curve.sample` rebuilds its whole segment
table on every call, which is 83 % of the worst case either audit found (P2). Those two are half a
day each and they are the whole story for PC-G3 and citygen. After them, the `ray` verb is a
genuine 52-94x on the conform stage (P5) and `copytopoints` + a 64-bit `attribvop` snippet is a
genuine 6x on the deformed branch (P6) - both real, both cycles, both moving baselines by ~1e-6 m,
and **neither of them touching the packed workload PC-G3 is measured on.** `plan.py` and
`corner.py` stay Python, permanently. OpenCL is not warranted anywhere in phase 1. **And D103 is
retracted: `attribvop`'s `vexsrc="snippet"` gives arbitrary VEX from a verb, in 64-bit, with no
node network - verified twice, on this build.**

### 11.8 Port build log — P0..P5c, and P5V/P5cV's verifications of them

The order and the numbers are §11.2's. Every row here was measured on this build with one
harness (`scratchpad/bench.py`, the same rows both audits used), before and after, and the four
suites re-run after each item. **Baseline movement is stated per item, never discovered in the
diff.**

#### P0 — the three unasserted stamps closed, and the port's own tripwires committed (2026-08-22)

**Standing finding (10) is CLOSED, and it was worse than recorded.** `pc_u`, `pc_section` and
`pc_variant` were asserted by nothing; `stamp_provenance` now reads all three back per case
against the plan the piece came from, and `pc_u` is *re-derived* (`section.u_at(placement.s0)`
off the section list the builder used) rather than re-read, so it is a different expression
reaching the same number. Reported as `[worst |du| in u units, pc_section wrong, pc_variant
wrong]`, asserted at 2e-06 u (float32's floor at 0..1 is ~6e-08; the suite's worst real reading
is **2.6e-08**).

⚠️ **`pc_variant` was not merely unasserted — it was never EXERCISED.** Mutation-testing the new
check found the first version of it green under `pc_variant` blanked in *both* writers, because
**no module of any kit in the 87-case suite carried a variant at all**: every value on both sides
of the comparison was `""`. No check, however written, could have caught that. `cases.variant_kit`
and **case `DL_variant_kit`** exist for it (post `oak`, panel `oak_long`), and the same mutation
is red on it. That is tests/README.md's own rule arriving late: adding a value means adding a case.

**And §11.2's three measurements are standing checks now** (`ZZ_port_tripwires`, run once per
suite run, not per case):

| tripwire | reads today | expectation on the line | what it is for |
|---|---|---|---|
| `stamp_calls_per_piece` | **14.005** (2 801 HOM writes / 200 packed pieces) | ceiling 15.0 | P1. A count, so it does not churn the baseline. |
| `curve_sample_scaling` | **O(n)** (3.5 µs at 10 verts, 8 185 µs at 20 001 — **2 339×**) | `expect="O(n)"` | P2. ⚠️ **The VALUE is the class, not the microseconds** — a timing in `baseline.json` moves on every run and drowns the movement list every port commit has to read. The raw µs ride in `detail`, which the runner records but does not diff. |
| `conform_cache_per_element` | **23.85** (477 entries / 20 elements, one path) | ceiling 30 | P5. The memo is unbounded — 53 861 entries / 24 MB on one 2 km curve. |

**Two of the three expectations describe a defect on purpose**, `scale_gate.py`'s LADDER device:
green today means "still the shape the audit measured", and the commit that lands the port flips
the expectation — that flip *is* the proof. Verified reachable both ways: a stub `Curve` subclass
with an O(1) `sample` reports **O(1) at 0.11 µs / 0.12 µs (1×)**, and today's `Curve` asked for
`expect="O(1)"` is **red**.

**FIVE MUTATIONS, five red, each reverted and the tree verified clean afterwards:** `pc_u` +0.25
in `_stamp_values` (both writers) → `stamp_provenance` red on 87; `pc_section` +1 → red on 87;
`pc_variant` blanked → red on `DL_variant_kit` (and green everywhere else, which is the finding
above); one extra `prim.setAttribValue` per piece → `stamp_calls_per_piece` 14.005 → 15.005, red;
`ConformPath._cache` keyed so every call misses → 23.85 → 59.65, red.

**Suites: 89 cases / 5 212 checks / 0 failing** (87 → 89 cases, **149 entries added, 0 values
moved, 0 removed** — re-derived key by key against `HEAD`, not read off the runner's own list),
284 unit tests OK, HDA checks 0 failing, 9 ladder rows 0 failing. No production code was touched.

**Bench, before anything is ported** (`hython scratchpad/bench.py`, best of 2, this machine):

| row | seconds |
|---|---|
| `packed_20km` (R = 80 m, 10 000 packed) | **0.727** |
| `packed_straight` (20 km resampled, 10 000 packed) | **0.676** |
| `streets_300` (300 × 60 m streets, 9 000 packed) | **0.471** |
| `corners_200` (20 km resampled + 200 real kinks, miter) | **11.339** |
| `deformed_10` (R = 10 m, 9 996 deformed, 339 864 prims) | **1.661** |
| `plan_display` (Display = Plan over the packed row) | **1.056** |
| `colour_warn` (4 000 warned prims through `hda.colour_warnings`) | **0.222** |
| `Curve.sample` | 3.09 µs @ 10 verts · 570.99 µs @ 2 001 · **7 966.27 µs @ 20 001** |
| stamp calls | **14.005** per packed piece |

⚠️ `corners_200` is 11.3 s here against the audit's 4.322 s: it is not the audit's fixture — this
one puts a real ±6 m kink at every marked vertex and runs miter, so it builds 1 196 deformed
corner pieces as well. It is used as an A/B against itself, not against the audit's number.

#### P1 — the packed stamp bulk-written, and two more writers nobody was watching (2026-08-22)

**`place._stamp_bulk` replaces the per-prim writer on BOTH branches.** Pass B accumulates
`(prim count, stamp values)` per piece in build order and one array per attribute is written over
the finished geometry at the end. D102 did exactly this for one deformed *piece* at a time; the
packed branch — PC-G3's headline row and every citygen street — never got it, and it measured as
62 % of the real node cook.

**Measured, this build, before → after:**

| row | before | after | × |
|---|---|---|---|
| `scale_gate` **arc_80/kit** — §11's "real node cook" | ~~**0.933 s**~~ ⚠️ **0.72 s, see P5R** | **0.458 s** | ~~2.04~~ **~1.6** |
| `scale_gate` two_point | 0.508 s | 0.281 s | 1.81 |
| `scale_gate` resampled (D69's 20 011-vertex row) | 0.673 s | 0.402 s | 1.67 |
| `scale_gate` arc_10 (deformed, 359 856 pts) | 1.866 s | 1.406 s | 1.33 |
| bench `packed_20km` | 0.727 s | 0.490 s | 1.48 |
| bench `packed_straight` | 0.676 s | 0.425 s | 1.59 |
| bench **`streets_300`** (the citygen shape) | 0.471 s | 0.245 s | **1.92** |
| bench **`plan_display`** (Display = Plan) | 1.056 s | 0.490 s | **2.15** |
| bench `colour_warn` | 0.222 s | 0.106 s | 2.10 |
| `stamp_calls_per_piece` | **14.005** | **0.005** | — |

§11.2 predicted 0.933 → ~0.40 s; measured 0.458 s. **`Display = Plan` cooked 1.55 s against the
0.93 s build it previews and now cooks 0.49 s against 0.46 s** — `plan_points` got the same
treatment (15 point attributes, one `setAttribValue` each, per placement → `createPoints` plus one
column per attribute), and so did `hda.colour_warnings` (one `Cd` array instead of one read per
warn per prim plus one write per hit; the unwarned prims keep whatever `Cd` they already had,
because a kit module may ship its own colour).

**D102's `_stamp_geo` is DELETED.** With the accumulation happening across the whole output there
is no piece-sized write left, and leaving a third writer in the file would have left `stamp_parity`
comparing two paths the build no longer takes — which is precisely the failure mode cycle 11
finding (D) already caught once.

**`stamp_parity` was rewritten to match the new shape, and that is not cosmetic.** It used to stamp
one piece two ways. `_stamp_bulk`'s named risk is that the accumulated columns stop lining up with
`out`'s prim numbering, so the whole case is now stamped in ONE `_stamp_bulk` call — 3 prims per
element — against a twin filled element by element by `_stamp`, and compared over 3.4's whole name
set plus every warn name in the case (an element that did NOT warn has to read 0 where its
neighbour reads 1 — the half a per-element comparison cannot ask). That is why 21 cases' *compared*
counts moved; `diffs` is **0 on all 89**.

**FIVE MUTATIONS, and the first run had TWO SURVIVORS — both holes in writers this item rewrites.**

| mutation | verdict |
|---|---|
| bulk stamp: `pc_u` + 1e-6 on **every** prim | RED — `stamp_parity`, 88 checks |
| bulk stamp: `pc_u` + 1e-6 on **prims 2..n only** | RED — `stamp_parity`, 88 checks |
| bulk stamp: **every column shifted one element** (P1's own named risk) | RED — 678 checks across 24 names |
| `plan_points`: `pc_u` column shifted by one | **first run GREEN** → now RED on `plan_point_provenance`, 87 cases |
| `hda.colour_warnings`: the warn colour never written | **first run GREEN** → now RED on `warned_elements_are_coloured` |

⚠️ **`plan_points` asserted TWO of its fifteen values** — `pc_elem_id` and the position — so
shifting a whole column changed nothing anyone could see. That is standing finding (10) again, in a
second writer. **`plan_point_provenance`** reads all fifteen back against the `Placement` they came
from (note `pc_section` on a plan point is the section KEY, not the section index the prim stamp
carries), float32-relative because a 20 km `pc_s1` cannot be compared at an absolute 1e-9. Worst
real reading **2.4e-08** relative, 0 mismatches on 88 cases.

⚠️ **§11.2 named `run_hda_checks.py`'s "warning-colour rows" as one of P1's pins. THERE WERE NONE.**
Deleting the colour write outright left the entire HDA suite green, and `show_warnings` is exempt
from the PC-G4 parm sweep by design (D81/D82 — it is a viewing decision), so the parm and its
writer were together unexercised. New **section 7**: `warned_elements_are_coloured` (40 warned
prims, 40 at `(1.0, 0.25, 0.1)`) plus `show_warnings_off_paints_nothing` as its control — without
the control a builder that painted everything red unconditionally would pass.

`stamp_calls_per_piece`'s ceiling went **15.0 → 1.0**: restoring the per-piece writer puts it back
at 14.005 and the check goes red.

**Baseline: 89 cases, 5 212 → 5 300 entries; 88 added, 0 removed, 22 moved** — 21 `stamp_parity`
*compared* counts (the check's own widening, `diffs` still 0 everywhere) and `stamp_calls_per_piece`
14.005 → 0.005, the number P1 exists to move. **`geometry_digest` did not move on a single case**,
which is what §11.3's table required of P1. Suites: 89 cases / 5 300 checks / 0 failing, 284 unit
tests OK, HDA checks 0 failing (2 new), 9 ladder rows 0 failing.

#### P2 — `Curve.sample`'s segment table cached and bisected (2026-08-22)

**One cache and one `bisect`.** `__init__.py`'s sampler rebuilt the full per-segment table on
**every call** and then linear-scanned it. `_segments()` builds it once — exactly the way
`_cumulative` above it already did — and the scan is the same predicate written as a bisect:
`his` is strictly increasing (a segment is only kept when its length is ≥ `EPS`), so "the first
`hi` strictly past s" is `bisect_right` and "the first `hi` at or past s" is `bisect_left`, which
is what the forward/backward branches asked for literally.

**Measured, this build:**

| | before | after | × |
|---|---|---|---|
| `Curve.sample` @ 10 verts | 3.09 µs | **0.71 µs** | 4.4 |
| `Curve.sample` @ 2 001 verts | 570.99 µs | **0.78 µs** | 732 |
| `Curve.sample` @ **20 001 verts** | **7 966 µs** | **0.95 µs** | **8 385** |
| bench **`corners_200`** (20 km resampled + 200 real kinks, miter) | **11.10 s** | **1.11 s** | **10.0** |
| bench `packed_20km` | 0.490 s | 0.479 s | 1.02 |
| `scale_gate` resampled | 0.402 s | 0.392 s | 1.03 |

§11.2 predicted "8 218 µs → ~1 µs" and "4.32 s → ~0.65 s"; the per-call figure lands at 0.95 µs —
`place.Path`'s own flat 0.80 µs, which is what it should converge on — and the corner-heavy row is
10× on this harness's own fixture. **The packed and deformed ladders barely move**, and that is
expected: `place.Path` was already cached, so what P2 buys is the corner and decompose work, which
is where citygen's 300-street-with-junctions shape actually lives.

**Parity is BIT-IDENTICAL, and the reference implementation is committed rather than described.**
`TestSamplerCacheParity._linear` in `tests/unit/test_polychain.py` is the pre-P2 body verbatim, and
the test compares `==` on the raw floats (§11.3's table demands "exactly 0" here, not a tolerance)
over 11 curves — open, closed, duplicate points, hairpin, 2 001-vertex resample, 600-vertex arc —
sampled past both ends, on every vertex arclength and at ±EPS and ±1 ULP around each, in both
directions. **0 differing of 3 802**, and `test_the_table_is_built_once` asserts the cache is one
object and that `his` really is the sorted upper bound of the kept segments.

⚠️ The vertex sweep is capped at 40 per curve **because the reference is the O(n) scan**: an
exhaustive sweep of the 2 001-vertex curve took the whole unit file from 0.09 s to 12.4 s, and the
41st vertex of a straight line proves nothing the 3rd did not.

**FIVE MUTATIONS, five red** — and the first one is why the unit test had to exist:

| mutation | unit | scene suite |
|---|---|---|
| `bisect_left`/`bisect_right` **swapped** | RED | **GREEN — 0 failing** |
| the `EPS` dropped from both bisect keys | RED | 1 failing |
| forward and backward collapsed to one branch | RED | 69 failing |
| the table shared between curves of equal vertex count (a stale cache) | RED | 86 failing |
| `his` built from `lo` instead of `hi` | RED | 109 failing |

⚠️ **Swapping the two bisect sides leaves all 89 scene cases green.** That branch decides which
tangent a frame reads AT a vertex — the thing `Curve.sample`'s own docstring warns about — and the
whole geometry suite cannot see it. It is pinned by the unit parity test and by nothing else.

**Baseline: 89 cases, 5 300 entries, 0 added, 0 removed, ONE moved** —
`curve_sample_scaling: O(n) -> O(1)` (0.75 µs at 10 verts, 0.86 µs at 20 001, **1×**), the
expectation flip this tripwire was written for. `geometry_digest` did not move on any case, nor did
`sampler_matches_kernel`. Suites: 89 cases / 5 300 checks / 0 failing, 286 unit tests OK, HDA
checks 0 failing, 9 ladder rows 0 failing.

#### P3 — the bend-resolution warning stops sampling the path three times a gap (2026-08-22)

Two halves, both bit-identical by construction rather than by tolerance:

1. **`_bend_deviation` samples each station once.** It read three positions per station gap and
   two of them were the same station twice — gap *i*'s end is gap *i+1*'s start. Now `2n-1`
   samples instead of `3n-3`, and `n` `remap` calls instead of `2n-2`.
2. **The deform pass reads those samples back.** Pass A hands the `{s: (pos, tan)}` it built to
   `job["stations"]`; `_deform_positions` looks up the same `s` it would have computed and only
   samples on a miss. A miss is slow, never wrong — a rigid module, which never reaches the
   warning pass, simply pays as before.

**Measured, this build:** `Path.sample` calls on the `arc_10` row **449 834 → 279 902 (−37.8 %)`;
`_bend_deviation` cum 0.639 → 0.500 s; `_deform_positions` out of the profile's top four.
~~`scale_gate` **arc_10 1.494 → 1.345 s (−10.0 %)**, `arc_80/adaptive` 1.506 → 1.382 s, bench
`deformed_10` 1.483 → 1.351 s (−8.9 %).~~

⚠️ **THE WALL-CLOCK HALF OF THAT IS RETRACTED — SEE P5R.** The call-count reduction reproduces
exactly (449 834 → 279 902, re-counted twice). The seconds do not: fresh hython per worktree, best
of 9, two interleaved passes, `arc_10` **1.3685 / 1.3754 → 1.3501 / 1.3610 s (−1.0 to −1.3 %)**
and `arc_80/adaptive` **1.4852 / 1.5135 → 1.4648 / 1.4741 s (−1.4 to −2.6 %)**. The −10.0 % was a
single-rep `scale_gate` reading, and cProfile over-weights a removed Python-level call by roughly
10×, which is exactly how a −37.8 % call count becomes a claimed −10 % of wall clock. The removed
samples were replaced by per-station dict inserts and lookups. **The packed rows do not move at
all**, which is right: they never deform — and the packed branch's own duplicate sampling was left
untouched until P5R, which is where the 10 000 × 10 removed calls actually were.

**A second, unbudgeted win:** `conform_cache_per_element` **23.85 → 17.55 (−26 %)**. The backward
reads at stations are gone, and `ConformPath._cache` is keyed on `(s, forward)` — so a quarter of
P5's 24 MB memo was the warning pass asking for the same point from the other side.

⚠️ **ONE SEMANTIC CHANGE, and it is the item's whole risk.** A gap's END used to be read
BACKWARD; it is now the next station's FORWARD read. The two differ only at a vertex and only in
the TANGENT, which `_bend_deviation` never asks for. Measured before writing the change: **8 000
samples on PC-G3's own arc, 4 000 of them landing exactly on a vertex — 0 differing, worst 0 m**,
and `proto.stations == sorted(set(local x)) - ax` exactly, which is what makes half 2 a lookup
rather than an approximation.

**§11.2's ordering warning is now stale, and the reason matters.** It says the bend warning is
decided in pass A "because `warn_names` is collated and `_declare`d before pass B runs". **After
P1 that is no longer true** — nothing in pass B touches a stamp attribute, the whole stamp is
written after it. Sharing was still done as "share the samples, not move the pass", because moving
it buys ~34 MB of retained station dicts and nothing else; **measured, the retention costs
nothing** — peak RSS on the 10 k-piece deformed row is **238.9 MB with it and 239.9 MB without**,
because the dicts are popped as pass B consumes them and the 360 k-point geometry dominates.
A future P6 can drop the retention for free.

**SIX MUTATIONS, four red — and BOTH survivors were pre-existing holes, one of them the exact risk
§11.2 P3 names.**

| mutation | verdict |
|---|---|
| the gap end reused as its own start | RED — 30 checks, `warnings` |
| the shared cache serving the piece's START for every station | RED — 216 checks |
| the deform pass reading the shared TANGENT off by a station | RED — 4 checks, `over_unpacked` |
| the deviation short-circuited to zero (nothing ever warns) | RED — 10 checks |
| **the midpoint probe moved 1 mm** | **GREEN, and it moved ONE value in the whole suite** |
| `base_y` taken from the last station instead of the first | GREEN — 0 failing, but **6 values moved including 3 `geometry_digest`** |

⚠️ **§11.2 P3's risk line said "it is a WARNING, so a silent change is invisible in geometry
checks", and it was literally right: moving D25's probe 1 mm changed NOTHING.** `warnings`,
`warn_summary`, `curvature_budget_m` and `deform_gate_m` all record the BOOLEAN's consequences and
1 mm does not cross the 0.01 m `bend_tol` on any case, so the measurement behind the warning could
be re-aimed by any refactor with the suite fully green. **`bend_deviation_m`** records it now — the
worst deviation `build` actually computed, per case — and the same mutation moves **40** values.
Recorded rather than asserted: what the number should BE is the geometry's business and
`geometry_digest` owns that; what this owns is that it cannot change unseen.

The `base_y` survivor is pre-existing (that line predates P3; P3 only added a cache read past it)
and it is **caught by the baseline diff rather than by an assertion** — 3 `geometry_digest` hashes,
`band_datum_m` on two cases and `stepped_float_m` 0.1 → 0.590874 all move. That is the mechanism
§11.3 rule 5 and §11.4 both require every port commit to use, so it is recorded here as such rather
than papered over with a new assertion.

**Baseline: 5 300 → 5 388 entries; 88 added (`bend_deviation_m`), 0 removed, ONE moved** —
`conform_cache_per_element` 23.85 → 17.55. `geometry_digest` did not move on a single case. Suites:
89 cases / 5 388 checks / 0 failing, 286 unit tests OK, HDA checks 0 failing, 9 ladder rows 0
failing.

#### P4 — DECLINED, with the measurement that declines it (2026-08-22)

**P1 collected this item's headline, so P4 as written no longer exists.** Measured on one machine
in one session, the same `arc_10` row both ways, with `place.py` and `__init__.py` swapped to the
P0 commit (`b5d3637`) and restored md5-identical afterwards:

| | at P0 | now (post-P3) |
|---|---|---|
| `hou.Geometry.addAttrib` | **149 955 calls, 0.163 s, 9.9 % of a 1.655 s row** | **10 011 calls, 0.013 s, 1.0 % of a 1.391 s row** |

§11.2 P4's own figure was "150 014 `addAttrib` calls" and "`_declare` alone is 0.325 s cum" — the
call count reproduces to 0.04 %, and **P1 deleted 93 % of it** by removing the per-piece
`_declare(piece, warn_names)` when the stamp moved to the whole output. The 10 011 that remain are
one `pc_local` declaration per piece.

**What is left of P4, measured by identity rather than by size** (`build(out=...)` so the two merge
sites can be told apart without a `prims()` call polluting the timing; the instrumented build ran
1.403 s against the clean 1.383 s, so the measurement is not distorting what it measures):

| site | calls | seconds | share of the 1.383 s row |
|---|---|---|---|
| `out.merge(piece)` | 9 996 | **0.067** | **4.8 %** |
| `piece.merge(src)` | 9 996 | 0.017 | 1.3 % |
| `hou.Geometry()` per piece | 9 996 | 0.013 | 0.9 % |
| `addAttrib` | 10 011 | 0.013 | 1.0 % |
| **total** | | **0.110** | **8.0 %** |

Of that, `piece.merge(src)` is not recoverable — one geometry for all pieces still has to get the
module's points in — so the honest ceiling is **~5.7 % of the deformed row**.

**Against:** §11.2 rates P4 MEDIUM risk (prim and point numbering plus `pc_local` must survive, and
the corner-cut branch has to stay its own path because `clip` operates on a whole geometry, so it
is a hybrid rather than a rule). And the row it improves is **not measured by any gate**: PC-G3's
own row is 100 % packed, `A_straight` / `CE_all_packed` / `CF_resampled_straight` /
`CG_resampled_bendable` are asserted 100 % packed, and the citygen street case is packed. §11.5
risk 10 says it in the plan's own words: *"Land P0–P2, re-measure, and only then decide whether the
rest is worth a cycle."*

**Declined.** ~5.7 % of a 1.35 s branch, bought with MEDIUM risk to `geometry_digest`,
`pc_local` and the corner-cut path, is a worse trade than leaving it. If P6 is ever taken up it
absorbs P4 anyway (§11.2), and by then the numbers will need re-deriving regardless.

---

#### P5R — the third review round: four fixes, six checks, and three numbers corrected (2026-08-22)

Three independent reviewers (parity/regression, performance truth, native idiom) returned fifteen
findings against P0–P4. **Every one was reproduced on this build before a line was changed**, and
two of them are corrections to numbers this very section had already committed — which is the
failure mode §11.5 risk 9 exists for, arriving on schedule.

**⚠️ (1) THE HEADLINE MULTIPLIER WAS BUILT ON AN UNREPRODUCIBLE BASELINE.** The table below used
to read *"`scale_gate` arc_80/kit 0.933 → 0.444 s = 2.10×"*. The **0.933 s** does not reproduce.
Re-run on this machine, the pre-port worktree (`69db56c`) and HEAD back to back, two interleaved
passes each:

| harness | pre-port `69db56c` | at P4 `830cf0c` | after this round |
|---|---|---|---|
| `scale_gate` arc_80/kit | **0.718 / 0.728 s** | 0.442 s | **0.397 / 0.395 s** |
| `bench` arc_80/kit, best of 9 | **0.696 / 0.708 s** | 0.476 / 0.475 s | **0.408 / 0.413 s** |

0.933 is **28 % above P0's own bench row for the identical workload** (`packed_20km` **0.727 s**,
the P0 table above) — and it is the 0.727 that reproduces, twice, on two harnesses. §11.5 risk 7
said *"do not quote either as THE number… re-measure on the real node cook"*, and the re-measure
landed on the outlier. **The honest reading of the P0→P3 row is ~0.72 → ~0.49 = 1.5×** (an
independent re-run got 0.749 → 0.490 = 1.53×), and **~0.72 → ~0.40 = 1.8× after this round.** The
win is real and large; only the multiplier was wrong. The 2.04× at P1 is the same error and is
corrected in place there.

**⚠️ (2) P3's 8–10 % DOES NOT REPRODUCE EITHER — its call-count reduction does.** Measured with a
fresh hython per worktree, best of 9, two interleaved passes, `6f1eb00` (pre-P3) vs `2a5ed89`:

| | pre-P3 | P3 | Δ |
|---|---|---|---|
| `Path.sample` calls on `arc_10` | **449 834** | **279 902** | **−37.8 %** (exactly as claimed) |
| bench `arc_10`, best of 9 | 1.3685 / 1.3754 s | 1.3501 / 1.3610 s | **−1.0 to −1.3 %** |
| bench `arc_80/adaptive`, best of 9 | 1.4852 / 1.5135 s | 1.4648 / 1.4741 s | **−1.4 to −2.6 %** |

The recorded *"arc_10 1.494 → 1.345 s (−10.0 %)"* was a single-rep `scale_gate` reading, and the
profile that motivated the item over-weights a removed Python-level call by roughly 10×. The
removed samples were replaced by per-station dict inserts and lookups, which is where the time
went. **P3 stands as a correctness/allocation cleanup that unblocks P6 and as the item
`station_share_hit_rate` now pins — it is not a 10 % row, and the table below no longer says it
is.**

**⚠️ (3) P2's "the real citygen shape" LABEL WAS WRONG.** Measured `24efd41` (P1) vs `6f1eb00`
(P2), best of 5, two passes: `corners_200` **10.93 / 10.99 → 1.128 / 1.123 s (9.7×)**, and
`streets_300` **0.2429 / 0.2423 → 0.2424 / 0.2409 s — nil**. The 200-corner fixture is ONE 20 km
curve with 1 198 samples over one table; citygen hands hundreds of separate short polylines with
`Curve.sample` called twice per section, which is the shape P2 buys nothing on. Corrected in
§11.2 P2, and `curve_sample_scaling` grew the COLD reading that made the difference visible.

---

**WHAT CHANGED IN THE CODE.** Four fixes, all on the packed/hot path, none touching geometry:

- **`span_ends` — the packed branch was asking the same two questions six times.** `_flat_ratio`,
  `_chord_ratio`, `span_deviation`, `_needs_deform`, `_packed_transform` and `plan_pos` each
  opened with the forward hit at the span's start and the backward hit at its end. Counted on the
  20 km packed row: **169 232 `Path.sample` calls for 10 000 pieces — 16.92 each, at two distinct
  arguments**. Pass A takes the pair once and threads it; **69 232 calls, 6.92 per piece, −59 %**.
  It is P3's own idea on the branch P3 never reached, and it lands on the only branch PC-G3 and
  the citygen street case measure. Anchored pieces are excluded: no consumer of the pair runs for
  them, and a `ConformPath` drop nobody needed would grow the memo `conform_cache_per_element`
  pins (that row is unmoved at 17.55).
- **`len(piece.prims())` in the deformed hot loop** built a tuple of 34 `hou.Prim` wrappers 9 996
  times to read a number `intrinsicValue("primitivecount")` returns for free — profiled at 0.090 s
  of a 1.40 s row, the 3rd-largest built-in, **6.4 %**, for a one-token change. Measured 24×
  cheaper on the real piece shape. Same at `stamp_base` and in `hda.colour_warnings`, which pays
  it on the 340 000-prim display path.
- **`_stamp_bulk` read and discarded a whole existing column per attribute** even though `base` is
  0 for every caller in the tree — ~15 columns of 339 864 values pulled through HOM and sliced to
  `[]`. Guarded; same in `plan_points`, on the interactive `Display = Plan` path.
- **P1's memory regression, measured and cut.** `_stamp_bulk` materialised all fifteen columns
  before writing any of them. It is real and it was reported nowhere:

| arc_10, one build, fresh process | pre-port `69db56c` | at P4 `830cf0c` | after this round |
|---|---|---|---|
| peak working-set delta | **132.8 MB** | **247.4 MB** | **221.5 MB** |
| working set after the report is released | 119.8 MB | 191.5 MB | **154.5 MB** |
| Python peak over the whole build (`tracemalloc`) | **18.2 MB** | **80.4 MB** | **39.9 MB** |
| `_stamp_bulk`'s own peak | — | **49.5 MB** | **7.6 MB** |

  One column is expanded and written at a time now. **The rest of the gap is P1's design and is
  recorded rather than fixed**: `stamp_rows` holds ~10 000 `(count, 14 (name, value) pairs)` rows
  live until the writer runs (~13 MB) because accumulate-then-write is what buys the 2×, and the
  Python allocator keeps the high-water mark of the 339 864-entry columns. **`scale_gate`'s `dRSS`
  column is NOT asserted and should not be**: on this machine the same `arc_80/adaptive` row read
  34.1, 54.7, 58.6, 60.2 and 82.2 MB across runs. The assertion lives in **`stamp_bulk_peak_kb`**
  instead — `tracemalloc`, deterministic to the byte, **801 kB against 4 252 kB** for the
  fifteen-column shape.

**SEVEN CHECKS, EACH FOR A HOLE A REVIEWER DEMONSTRATED.**

| check | the hole it closes | mutation |
|---|---|---|
| `stamp_calls_per_piece_deformed` | the tripwire ran on a 100 % PACKED fixture, so the branch where a per-prim stamp costs 14 × PRIM COUNT was the branch it could not reach — the D102-era writer restored there is an **8.4× wall-clock regression** with all three suites and the ladder green | **476.033**, RED |
| `station_share_hit_rate` | P3's fallback branch is **dead as tested** (2 691 hits, 0 misses over the suite), so a key drifting by one ULP would silently delete P3's whole win | one station's key nudged → **0.033**, RED |
| `stamp_bulk_peak_kb` | P1's memory shape was measured by nothing; `baseline.json` carries no memory value at all | fifteen columns at once → **4 252 kB**, RED |
| `build_out_keeps_upstream_stamps` | `build(out=…)` and the whole `base` path have **no caller anywhere** in the package or the suite — dev-loop Rule 0 | head corrupted → **[0, 10]**, RED |
| `only_the_warned_prims_are_coloured` | painting **every** prim red left all three suites green, because section 7's fixture warns on every element and its control only proves the toggle gates the write | paint all → **[10, 3, 7, 0]**, RED |
| `curve_sample_scaling` COLD reading | the check warmed the cache before timing, so it measured only the path a many-samples curve takes — never table construction, the only cost the many-short-streets shape pays | table rebuilt per segment → **['O(n)', 'O(n^2)']**, RED |

A seventh, from the same round's only near-parity finding: P3's docstring claimed its one
semantic change was *"bit-identical by construction… 0 differing, worst 0 m"*. It is not - the
measurement behind it was taken on PC-G3's axis-aligned arc with round coordinates. Re-measured
over the vertex arclengths of seven curves (open, closed, diagonal, hairpin, climbing,
sub-millimetre, plus the axis-aligned control): **166 arclengths, 2 differing, worst |dP|
4.4e-16 m**; an independent sweep of seven other curves read 344 / 74 / 7.1e-15 m. That is
double-precision ULP on a segment endpoint (the backward branch lands on the previous segment with
t clamped to 1.0, which is float-exactly `pts[k]` only under Sterbenz), seven orders below
`bend_tol`. The docstring says the measured truth now, and **`path_read_direction_m`** is that
measurement as a standing assertion at a 1e-12 m ceiling - ULP passes, a dropped sub-EPS segment
would be metres.

Two more, from the same round: `stamp_provenance` had **one `where` slot for three quantities**,
so the single run in which it has ever fired recorded a detail identical to a passing run's and
named none of the failing elements — three slots now, and the `pc_variant` mutation reports
`X|0|start|0|corner pc_variant 'X' != ''` on 88 cases. And `ends_swapped` — the threaded pair read
for the wrong end of the span — is **RED on 205 checks**, which is the parity net doing its job.

**⚠️ THE REPORTED NON-DETERMINISM DID NOT REPRODUCE.** One reviewer saw
`DL_variant_kit/stamp_provenance` report all 20 elements' `pc_variant` wrong in 1 of 12 clean runs,
and `over_unpacked` fail on two cases in another. **Run here 68 times** — 48 on the pre-round tree,
20 on this one, `--json` each, diffed pairwise key by key: **5 387 (then 5 391) values, 0 differing
runs, 0 failing checks, every time.** It is recorded rather than closed: a 2-in-12 flake that will
not show in 68 runs on another machine is still a fact about the harness, and `stamp_provenance`'s
detail is now able to say which elements failed if it happens again.

**HOM TRAP, found while mutation-testing the `out=` branch:**
`hou.Geometry.setPrimStringAttribValues` treats `""` as **leave unchanged** — writing
`("", "NEW")` over `("KEEP", "ALSO")` yields `("KEEP", "NEW")`. Harmless here (`build`'s own `out`
is fresh, so every string default is already `""`), and Houdini catches the other half itself: a
short array raises `Incorrect attribute value sequence size`. Written down in the check's
docstring and in this log so the next agent does not lose an afternoon to it.

**Baseline: 89 cases, 5 387 → 5 392 entries; 5 added, 0 removed, ONE moved** —
`curve_sample_scaling` `O(1)` → `['O(1)', 'O(n)']`, the check's own widening. **`geometry_digest`
did not move on a single case.** Suites: 89 cases / 5 392 checks / 0 failing, 286 unit tests OK,
HDA checks 0 failing (1 new), 9 ladder rows 0 failing.

---

#### Where P0–P5R leave the tool

⚠️ **EVERY ROW HERE IS A FRESH BACK-TO-BACK MEASUREMENT** of `69db56c` (pre-port) against this
commit, two interleaved passes on one machine, `scale_gate` as it runs and `bench` best-of-9. The
old table's "at P0" column mixed readings from different sessions and that is what produced the
2.10× that would not reproduce.

| row | pre-port `69db56c` | at P4 `830cf0c` | now | × over pre-port |
|---|---|---|---|---|
| `scale_gate` **arc_80/kit** — §11's "real node cook" | **0.718 / 0.728 s** | 0.442 s | **0.397 / 0.395 s** | **1.83** |
| `scale_gate` two_point | 0.486 / 0.491 s | 0.280 s | 0.215 / 0.216 s | 2.27 |
| `scale_gate` resampled (20 011 vertices) | 0.636 / 0.638 s | 0.394 s | 0.317 / 0.317 s | 2.01 |
| `scale_gate` arc_2000 | 0.735 / 0.720 s | 0.445 s | 0.377 / 0.371 s | 1.94 |
| `scale_gate` **arc_10** (deformed, 359 856 pts) | 1.700 / 1.722 s | 1.494 s | **1.230 / 1.243 s** | 1.38 |
| `scale_gate` arc_80/adaptive (deformed) | 1.730 / 1.745 s | 1.530 s | 1.298 / 1.269 s | 1.36 |
| bench two_point | 0.488 s | 0.245 s | **0.194 s** | 2.51 |
| bench **arc_80/kit** (= `packed_20km`) | 0.696 s | 0.476 s | **0.408 s** | **1.71** |
| bench **`streets_300`** (the citygen shape) | 0.478 s | 0.256 s | **0.206 s** | **2.32** |
| bench **`corners_200`** (20 km + 200 kinks, miter) | **11.28 s** | 1.121 s | **1.040 s** | **10.85** |
| bench **`plan_display`** (Display = Plan) | 1.080 s | 0.507 s | **0.444 s** | **2.43** |
| bench arc_10 (deformed) | 1.676 s | 1.424 s | **1.260 s** | 1.33 |
| `Path.sample` calls, packed row / 10 000 pieces | **169 232** | 169 232 | **69 232** | 2.44 |
| `Path.sample` calls, `arc_10` / 9 996 pieces | 449 834 (at P2) | 279 902 | **239 918** | 1.87 |
| `Curve.sample` @ 20 001 verts, warm | 7 966 µs | 0.95 µs | **~1.0 µs** | **~8 000** |
| stamp writes per packed piece | 14.005 | 0.005 | 0.005 | — |
| `ConformPath._cache` per element | 23.85 | 17.55 | 17.55 | 1.36 |
| arc_10 peak working set | 132.8 MB | 247.4 MB | 221.5 MB | — |

**Every gate still passes and `geometry_digest` has not moved on a single case across all five
commits.** The suite went 87 cases / 5 063 checks to **89 / 5 392**; of the 5 063 original values
**exactly three moved**, each of them a tripwire whose movement is the item's own proof:
`stamp_calls_per_piece` 14.005 → 0.005 (P1), `curve_sample_scaling` O(n) → O(1) (P2, and widened
to `['O(1)', 'O(n)']` in P5R when it gained its cold reading), `conform_cache_per_element`
23.85 → 17.55 (P3). The 21 `stamp_parity` counts that moved are the check's own widening, with
`diffs` 0 throughout.

**No render was made, and that is deliberate.** These five commits assert that nothing changed:
`geometry_digest` hashes every world position at `%.6f` on all 89 cases and is byte-identical
before and after, and the scale ladder's packed/deformed/point counts are unchanged. A picture of
provably identical geometry would be evidence of nothing. The GUI viewport pass §0.0 owes is a
separate, still-open item and none of this touches it.

**⚠️ WHAT P5R SHOULD TEACH THE NEXT AGENT, because it cost three reviewers to find it.** Of the
port's four committed speed claims, **two did not reproduce** — and both failed the same way: a
single-rep reading taken in one session, or a cProfile share read as a wall-clock share. The
discipline that would have caught both is cheap and is now the standing rule for this section:

1. **Two trees, back to back, interleaved, best of N ≥ 5.** A worktree at the before-commit and
   the working tree, alternating passes, on the same machine in the same hour. `git worktree add`
   makes this three commands.
2. **Never quote a cProfile share as a time saving.** Profiling inflates a removed Python-level
   call by roughly 10×. Profile to find WHERE, measure unprofiled to say HOW MUCH.
3. **A call count is evidence of a call count.** −37.8 % of `Path.sample` bought −1 % of wall
   clock, because the removed calls were replaced by dict work. Both numbers belong in the log,
   and only one of them is the payoff.
4. **State the memory column too.** P1 doubled peak working set on the deformed row and nothing —
   not `scale_gate`, which prints it, not `baseline.json`, which carries no memory value —
   noticed. `stamp_bulk_peak_kb` is the deterministic instrument that does.

---

#### P5 — the `ray` verb, batched: LANDED, with the port's first ZERO-movement conform (2026-08-22)

> ⚠️ **READ §11.8 P5c FIRST. THREE OF THIS SECTION'S CLAIMS DID NOT SURVIVE REVIEW.**
> (i) the “bit-identical” parity was a property of the FIXTURES, not of the code — the
> position reading is 2.4e-07 m on an irrational-slope ramp and 6.1e-05 m at 20 km, and a TILTED
> `conform_axis` diverges by 1.9e-06 m and is not batchable at all; (ii) the batch was taken once
> per CURVE, and `ray`'s per-execution cost scales with the SURFACE, so the citygen row it was
> aimed at was **0.94–0.99x — slower with the batch on than off**; (iii) 47 % of every
> batch (the gap midpoints) was never consumed, and no committed check could see that direction.
> The rows below are also un-re-runnable as written — they name no terrain size and no
> packed/deformed split, and neither did they exist anywhere in the repo. They do now:
> `tests/polychain/conform_bench.py`.

**§11.5 risk 10 says re-measure before starting, and the re-measure says P5 still pays — more
than the plan claimed, on a bigger row than the plan named.** Measured on the POST-PORT build,
unprofiled, by recording every query the real row makes and re-running just those:

| row | wall clock | `Surface.drop` | share | per drop |
|---|---|---|---|---|
| `fence_2km` (2 km conformed fence, 1 000 pieces) | 0.383 s | 34 002 drops, **0.187 s** | **48.9 %** | 5.51 µs |
| **`streets_300c`** (the citygen shape, conformed) | 4.221 s | 306 600 drops, **1.662 s** | **39.4 %** | 5.42 µs |
| `hill_2km_adaptive` (adaptive + camber over a ridge) | 0.327 s | 24 338 drops, **0.134 s** | **40.8 %** | 5.48 µs |

⚠️ **That is a share of WALL CLOCK, not of a cProfile column** — P5R's rule 2. The 39–49 % is the
Python drop loop re-run on its own recorded queries, outside the profiler.

**WHAT LANDED.** `Surface.drop_many` casts every query in ONE `ray` verb execution
(`method=project`, `dirmethod=vector`, `reverserays=bidirectional`, `bidirectionalresult=closest`,
`putnml=1`, `newgrp=1`, `bias=0`, `maxraydistcheck=0`), and `ConformPath.prefetch` fills `_cache`
from it once per curve, before any placement asks anything. **The per-query Python path is
untouched and is still the reference**: every key the prefetch misses is served by it, so the port
is additive and both implementations are live in one process — which is what lets `conform_parity`
prove them equal by asking BOTH (§11.3 rule 4) rather than by diffing two runs.

**§11.2 P5 PREDICTED THREE DIFFERENCES. TWO OF THE THREE ARE NOT THERE, and that was measured
before a line was written.** Over eight adversarial surfaces — D70's bridge deck (ground y = −2
under a deck y = +2), an **exact tie** between sheets at ±2, D52's reversed winding, D53's hole
and its edge, two coincident sheets, a query from BELOW, the camber cross-fall and the two-facet
tent — the verb and `hou.Geometry.intersect` agree on **385 points to 0.000e+00 m, with 0
hit-flag mismatches and 0 difference in the normal**, ties included (both take the down-axis
sheet, which is D70's rule). `bidirectionalresult=closest` IS "nearest wins"; `maxraydistcheck=0`
is equivalent to the per-point reach because every surface point lies within `radius` of the
centre. That measurement is committed as **`ray_verb_semantics`**, so it is not re-derived.
The third difference IS real and is re-added on read: the verb hands back the polygon's own
normal, so **D52's flip-to-oppose-the-axis is applied in `drop_many`** — dropping it is RED on
`ray_verb_semantics`, `conform_parity` and `camber_deg`, 19 checks.

**⚠️ AND THE PRECISION STORY IN §11.2/§11.3 IS WRONG IN ITS PREMISE, WHICH IS WHY THIS PORT MOVED
NOTHING.** §11.3 authorised "≤ 9.5e-07 m, re-baseline the conformed cases". The first working
build did exactly that — 22 moved values on 5 cases including 4 `geometry_digest` hashes. Then the
divergence was decomposed instead of accepted:

* the verb is **not** a different intersector. Its answer is **exactly**
  `Surface.drop(float32(p))` — 0.000e+00 over 34 002 queries on the 2 km fence;
* what differs is the **width of the number**: the verb's ray origins and its hits both live in a
  point cloud, i.e. float32, while `hou.Vector3` is **double** (probed: it round-trips
  2000.1234567890123 exactly). So the loss is real, not a lateral move, and it is
  coordinate-scaled — **5.5e-07 m under 20 m, 7.1e-06 m at 200 m, 2.3e-05 m at 2 km**;
* casting the query cloud's `P` to `fpreal64` does **not** fix it (the cast survives the verb for
  an untouched point; a hit is computed and written in float32 either way);
* **but a drop is a translation along the axis by construction.** The two components
  perpendicular to `axis` are the query's own and nothing may be learned about them from a float32
  cloud. `drop_many` therefore takes only the along-axis component from the verb and rebuilds the
  rest from the double query.

**Result: `conform_parity` reads 0.0 — bit-identical — on every conformed case, and the whole item
moves ONE baseline value.** Leaving the hit in float32 instead reads 9.5e-07 m and moves 22, which
is why `conform_parity`'s tolerance is **1e-09 m and not §11.3's 1e-06**: asserting the allowance
would have made the check unable to see the difference between the two builds.

**MEASURED, TWO TREES INTERLEAVED, BEST OF 5, TWO PASSES** (`git worktree` at `930b642`, fresh
hython per invocation):

| row | pre-P5 `930b642` | P5 | × |
|---|---|---|---|
| **`fence_2km`** (2 km conformed fence) | 0.3776 / 0.3741 s | **0.2573 / 0.2576 s** | **1.45** |
| `hill_2km_adaptive` (adaptive + camber) | 0.3223 / 0.3224 s | 0.2661 / 0.2624 s | 1.23 |
| **`streets_300c`** (300 conformed streets) | 4.1459 / 4.1936 s | **3.4168 / 3.4290 s** | **1.21** |
| `streets_300` (no surface — the control) | 0.1935 / 0.1956 s | 0.1968 / 0.2026 s | 0.98 |
| `fence_2km_flat` (no surface — the control) | 0.0286 / 0.0286 s | 0.0287 / 0.0284 s | 1.01 |

The two unconformed controls do not move, which is the point: `prefetch` does not exist on a plain
`place.Path`, so the branch is not taken. **The batch itself is 34 002 drops in 0.0018 s against
0.187 s — 104× — and the row only goes 1.45× because the `Path.sample` calls behind those drops
were always the other half of the cost and are unchanged.** Quoting the 104× as the row's win
would be P5R's own correction (2) repeated.

**EIGHT MUTATIONS, SEVEN RED, ONE NO-OP that is a finding.** Every one applied by byte-exact
replacement and reverted md5-exact; `git diff` clean afterwards.

| mutation | verdict |
|---|---|
| `prefetch` fills NOTHING (P5V's X1 shape — a pure cache silently disabled) | **RED** — `conform_prefetch_hit_rate`; **0 baseline values moved**, which is exactly why the tripwire exists |
| D52's normal flip dropped | **RED** — 19 checks (`ray_verb_semantics`, `conform_parity`, `camber_deg`) |
| `bidirectionalresult` = **farthest** (D70 inverted) | **RED** — 3 checks, 5 values moved |
| `reverserays` = forward only (no back-look) | **RED** — 62 checks, 119 values moved |
| the hit left in float32 (no double rebuild) | **RED** — 18 `conform_parity`, 22 values moved |
| every hit reported as a MISS | **RED** — 97 checks, 224 values moved |
| the gap midpoints dropped from the enumeration | **RED** — `conform_prefetch_hit_rate` |
| **`rtolerance` 1e-6 → the node default 0.01** | **GREEN, 0 failing, 0 extra values moved** |

⚠️ **The `rtolerance` no-op is recorded rather than papered over.** Nothing probed can tell 1e-6
from 0.01: a **1 mm hole in a 1 mm grid** and a query **1 mm past a sheet's edge** both give 0
hit-flag mismatches and 0 m at either setting, and so does the whole scene suite. It is set to
match `intersect`'s explicit tolerance on principle, and the docstring says so rather than
implying a case pins it.

**THE PREFETCH SERVES EVERYTHING.** `conform_prefetch_hit_rate` reads **0 fallback keys against
374 batched** on the tripwire fixture, and the recording harness measures **0 drops** reaching the
per-query path on all three benchmark rows. The fallback is therefore live-but-unused, exactly as
P3's station cache was, which is why it has a tripwire from day one instead of after a review.

> ⚠️ **AND THAT PARAGRAPH IS THE FINDING, NOT THE REASSURANCE (§11.8 P5c).** “SERVES
> EVERYTHING” and “0 fallback” are the same sentence as “the batch fetched
> 306 600 keys and 172 520 were wanted” — `fallback / batched` is **0.0 by construction
> when the batch over-fetches**, so the tripwire could only ever fail in one direction, and the
> direction it could not test is the one that was wrong. It reads `[used/batched,
> fallback/batched, batched]` now, on two fixtures. And the fallback branch really was never
> executed by any of the 88 cases; it is now, by the gap midpoints, which is a live reference
> rather than a dead one.

**Baseline: 89 cases, 5 395 → 5 485 values; 90 added, 0 removed, ONE moved, 0 ok/skip flag
changes** — re-derived key by key against `930b642`, index-aware. The one move is
`conform_cache_per_element` **17.55 → 18.7** (ceiling 30): the prefetch enumerates ~1.15 keys per
element that no consumer asks for — the `+delta` partner of a last station, and gap midpoints on
pieces that never reach `_bend_deviation`. **`geometry_digest` moved on 0 of 88 cases.** The 90
added are `conform_parity` × 88, `conform_prefetch_hit_rate` and `ray_verb_semantics`.
Suites: **89 cases / 5 485 check rows / 0 failing**, 286 unit tests / 9 625 subtests OK, HDA checks
0 failing, 9 ladder rows 0 failing.

**Warn-never-block held by construction and by measurement:** `drop_many` returns `None` rather
than raising if the verb is missing or throws, `prefetch` then returns and every key falls through
to the Python path — and mutation 1 is that state, with the whole suite green and only the
tripwire red.

---

#### P5b — the fourth `len(geo.prims())`, found while re-measuring for P6 (2026-08-22)

Profiling the conformed citygen row for P6 put a **surprise at the top of it**:
`_hou.Geometry_prims`, **303 calls, 0.530 s tottime of a 3.46 s row — 15 %, the largest single
entry**. P5R cut three `len(geo.prims())` sites that only wanted a NUMBER; the fourth is
`conform.Surface.__init__`, it runs **once per CURVE on the SURFACE**, and on 300 conformed
streets over a 7 712-prim terrain it built 300 tuples of 7 712 `hou.Prim` wrappers to ask whether
the geometry was empty. Same one-token change at the other three sites it reaches
(`clip_plane`'s, and `hda.py`'s kit and curve emptiness tests).

**Two trees interleaved, best of 5, two passes** (`git worktree` at `6c51bb2`):
`streets_300c` **3.417 / 3.420 → 2.781 / 2.806 s = 1.23×**, and **4.146 → 2.781 s = 1.49×**
against pre-P5. The single-curve rows do not move, which is right — they read the surface once.

**`prims_wrappers_built` is the tripwire, and it counts WRAPPERS, not calls**, because the cost
is the geometry's size: a call count reads 3 on a one-curve fixture whether the surface is being
wrapped or not. Three rows — packed/conformed **11** and deformed **11** against a ceiling of 64,
and a new `tripwire_mitered_run` at **571 against 600**. The miter row exists because
`clip_plane` is the one site no other fixture reaches (the packed, deformed and conformed runs
have no corners at all), and its ceiling is **§11.2 P7's shape rather than zero**: `clip_plane`'s
cap tagging and `dress_caps` are REAL per-prim loops — 280 wrappers each on that fixture — and P7
is the item that bulk-reads them, so landing P7 lowers this number. Mutations: the surface site
restored reads **347, RED**; `clip_plane`'s restored reads **843, RED**. ⚠️ The `hda.py` pair is
**pinned by nothing** — it is once per cook on a five-module kit and the scene suite does not run
`hda.py` — and that is recorded rather than fixtured.

Baseline: 5 485 → 5 488 values, **3 added, 0 removed, ZERO moved**, 0 flag changes.

---

#### P6 — DECLINED, with the measurement that declines it (2026-08-22)

**§11.5 risk 10 said re-measure before starting, and the re-measure moves the ground under P6 in
two directions at once. One of them is in P6's favour and the other is decisive against it.**

**FIRST, THE CORRECTION THAT FAVOURS P6.** §11.2 P6's honest-ceiling paragraph says the item is
*"worth ~1.3 s on the deformed workloads and nothing at all on PC-G3, the citygen street case, or
any packed run"*. **The citygen street case is 100 % DEFORMED the moment a terrain is connected**,
which is the obvious next consumer and the one §11.2 P5 names itself:

| row | packed | deformed | prims |
|---|---|---|---|
| `streets_300` (300 × 60 m streets, no surface) | **9 000** | 0 | 9 000 |
| **`streets_300c`** (the same, over terrain) | 0 | **9 000** | 306 000 |
| `fence_2km` (2 km fence over terrain) | 0 | **1 000** | 34 000 |

⚠️ **THAT TABLE IS ONE TERRAIN, AND THE SENTENCE ABOVE IT IS FALSE AS WRITTEN.** What sets
the deformed fraction is not whether a terrain is connected, it is **how much the surface curves
WITHIN a 2 m piece** - so the same 300 × 60 m streets over four heightfields, read off `build`'s
own report through the committed `tests/polychain/conform_bench.py`, are:

| terrain | prims | packed | deformed | deformed |
|---|---|---|---|---|
| 10 m cell, 2 m amplitude, 120 m wave | 2 376 | **8 208** | 792 | **8.8 %** |
| 5 m cell, 2 m, 60 m | 9 504 | 7 536 | 1 464 | 16.3 % |
| 2.5 m cell, 2 m, 60 m | 38 016 | 6 512 | 2 488 | 27.6 % |
| 2.5 m cell, 0.6 m, **8 m wave** | 38 016 | 5 532 | 3 468 | **38.5 %** |
| 2 km fence, 10 m cell, 60 m wave | 2 376 | **998** | **2** | **0.2 %** |

A smooth heightfield - which is what citygen most often produces - leaves **91 % of the same run
PACKED**, and the 2 km conformed fence in the row above is **0.2 % deformed, not 100 %**. This
does not change P6's verdict; it makes the decline stronger, because P6 touches only the deformed
branch. But it is committed guidance a next agent would size a branch against, so the packed/
deformed split now belongs on any conformed row alongside its prim count.

So the deformed branch is not a corner of the tool - but it is not what conformed work is made
of either, and which of the two it is on any given row is a property of the terrain.

**SECOND, THE MEASUREMENT THAT DECLINES IT.** `place.build` instrumented with
`time.perf_counter` at the four sites P6 would delete — the per-piece `hou.Geometry()` +
`piece.merge(src)`, `_deform_positions` and its two per-piece attribute writes, and
`out.merge(piece)` — best of 4, unprofiled, on the post-P5b build:

| row | total | pass A | pass B loop | `_stamp_bulk` | **what P6 replaces** |
|---|---|---|---|---|---|
| **`streets_300c`** (conformed citygen, 9 000 deformed) | 2.776 s | **2.129 s (77 %)** | 0.348 s (13 %) | 0.298 s (11 %) | churn 0.033 + maths 0.213 + merge 0.061 = **0.307 s, 11.0 %** |
| `fence_2km` (conformed, 1 000 deformed) | 0.270 s | **0.206 s (76 %)** | 0.036 s (13 %) | 0.028 s (10 %) | **0.032 s, 11.8 %** |
| `arc_10` (NO surface, 9 996 deformed) | 1.200 s | 0.531 s (44 %) | 0.357 s (30 %) | 0.311 s (26 %) | **0.314 s, 26.2 %** |

And what the replacement itself costs, measured on this build at the real shape (9 996 copies of
the 36-point / 34-prim panel → 359 856 points / 339 864 prims):

| part | measured |
|---|---|
| build the 9 996 target points | 0.0028 s |
| **`copytopoints(pack=0)`** | **0.0387 s** (§11.2 said 0.126 s) |
| **one `attribvop` snippet, `vex_precision="64"`, over 359 856 points** | **0.0005 s** |
| what it replaces (per-piece `Geometry()` + `merge(src)` + `out.merge`) | 0.0919 s |

**Net, therefore: ~0.25 s on `arc_10` (21 %, 1.27×) and ~0.25 s on `streets_300c` (8.9 %,
1.10×).** The deform MATHS on its own — the VEX half — is **0.136 s, 11.7 % of `arc_10`**,
measured independently by stubbing `_deform_positions` to return the source positions unchanged
(1.163 → 1.027 s).

**THAT IS THE WHOLE CASE AGAINST IT, and it is arithmetic rather than taste:**

1. **P6 is aimed at the wrong half of the row that matters.** On `streets_300c`, **pass A is
   77 %** and the deformed materialisation P6 replaces is **11 %**. The cost there is the conform
   sampler's own Python — `prefetch` + `_at` + `ConformPath.sample` + `drop_many`'s per-point loop
   is ~50 % of that profile — and P6 does not touch any of it. `_deform_positions` is 6 %.
2. **The 5.98× in §11.2 P6 cannot be reached from here, and the reason is structural.** That
   prototype was measured against the **pre-port 1.656 s** row, before P1 took the stamp out; the
   same row is 1.200 s now, of which 26 % is the stamp's own bulk writes and 44 % is pass A.
   Even a free pass B floors the row at ~0.84 s. §11.2 P6's risk (v) is what does it: `Path.sample`
   must stay in Python for the gate, so the VEX pass has to be HANDED its station frames and the
   239 918 `Path.sample` calls behind them remain. Re-deriving arclength in VEX instead is the
   *"second parity problem nobody asked for"* the item's own text forbids.
3. **The precision trap is worse than §11.2 knew.** §11.2 already DECLINED `copytopoints(pack=1)`
   for the packed branch because the transform routes through a **float32 point attribute**
   (4.34e-07 m against `marker_offset_m` baselined at 1.788e-07 m). The deformed port needs the
   per-station FRAMES to travel the same way, and at PC-G3's 20 km the float32 quantum is
   **1.95e-03 m** — four orders above `exact_fill_m`'s own 4.4e-07 reading. Every frame attribute
   would need an `fpreal64` `attribcast`, and `P` cast to 64 and back around the VEX pass. **P5
   just spent its whole risk budget on exactly this class of defect** and got to bit-identical
   only by refusing to let a float32 attribute carry a number it did not have to.
4. **`geometry_digest` would move on every deformed case.** P5 moved it on **0 of 88**. Trading
   that for 9 % of the conformed row is a worse deal than P4's was.
5. **§11.5 risk 6 is still open**: the prototype produced 359 820 points where the shipped build
   produces 359 856, and 339 830 prims against 339 864. §11.2 requires that resolved *before* P6
   lands. Nothing in this session resolved it.

**DECLINED.** ~9 % of the conformed row and ~21 % of an unconformed one, bought with HIGH risk to
`geometry_digest`, `pc_local`, prim and point numbering and the corner-cut hybrid, plus three new
`attribcast` calls existing only to undo a precision loss the current code does not have, is a
worse trade than leaving it. **What P6's own logic points at instead is `pass A` on the conformed
row, which is 77 % of it and which no item in §11.2 addresses.**

**AND OPENCL IS DECLINED WITH A NUMBER, since the brief asks either way.** The largest parallel
stage this tool has is 359 856 points, and `attribvop` with `vexsrc="snippet"` and
`vex_precision="64"` runs a per-point trig snippet over exactly that many in **0.0005 s** (32-bit:
0.0002 s). **There is no workload in phase 1 where VEX is the bottleneck** — the bottleneck is
always the Python around it — so moving anything to the GPU would be optimising a stage that is
already four orders below the row it lives in. §11.2's own "OpenCL, anywhere in phase 1" row is
re-confirmed rather than re-derived.

⚠️ **AND D103'S RETRACTION IS RE-CONFIRMED A FOURTH TIME, INCLUDING ITS 64-BIT TRAP.** The
20 km arclength expression `sin(x·1e-6) − x·1e-6` over 359 856 points returns **exactly 0.0 at
`vex_precision="32"`** and **−7.766608428431965e-12 at `"64"`**. `attribvop`'s snippet mode does
run arbitrary VEX through a verb with no VOP network, and 64-bit is mandatory — both true on this
build, measured again here.

**ONE THING P6's INVESTIGATION FOUND THAT IS WORTH THE NEXT AGENT'S TIME, AND ITS MEASUREMENT.**
On `streets_300c`, `Surface.drop_many` is **0.585 s of the 2.78 s row (21 %)**, split
`createPoints` + `ray.execute` **0.090 s**, the attribute and point-group reads **0.112 s** (of
which the group → set-of-point-numbers conversion alone is **0.078 s** — it builds 306 600
`hou.Point` wrappers, the same defect class P5b just closed), and **the per-point Python loop
0.384 s, 65 % of it**. Moving that loop's D52 flip into a second `attribvop` was prototyped and
**REJECTED ON PARITY**: VEX writes the flipped normal back through a float32 attribute, which
reads **2.566e-08 m against the Python path's 0.0**, and `conform_parity` is asserted at 1e-09
precisely so that a change like that cannot pass unnoticed. What is left is a bookkeeping change
(a cheaper hit flag than a point group, and flat-array construction), not a language change.

---

#### P5c — the review of P5: its parity was the fixtures', its batch was per curve, and both are fixed (2026-08-22)

Two independent reviewers took P5, P5b and P6 apart. **Ten findings, ten reproduced, none
dismissed** — one of them critical and one of them a parity divergence, which §11.3 rule 1 puts
first. The corrections below are the item; the numbers are all re-measured on this build.

**1. `conform_parity`'s 0.0 WAS A PROPERTY OF THE SCENES, NOT OF THE CODE (D111).** P5 read the
verb's hit POSITION and took its along-axis component (D108). That is one float32 rounding at the
magnitude of a **world coordinate**, and it is bit-identical only where the true answer happens
to be exactly representable — which every committed conform case is, because their surfaces are
`y = 0.25x` and their stations are multiples of 0.25 m. Measured against `Surface.drop` over 60
queries on an **irrational-slope ramp** (`y = 0.2718281828x + 0.0314159z`, dirty stations):

| reading | ramp, x < 24 m | the same ramp at x = 20 000 m |
|---|---|---|
| the verb's **position** (P5's) | **2.384e-07 m** | **6.104e-05 m** |
| the verb's **distance** (this) | **0.0** | **0.0** |

`ray` writes `dist` as well as `P`, and `dist` is the same number measured **from the query** —
one rounding at the magnitude of a *drop* instead of at the magnitude of a *coordinate*. A drop
is a translation along `axis` by construction, so `q + axis*dist` rebuilds the whole answer.
`drop_many` reads that now. **`geometry_digest` moved on 0 of 88 cases**, so this is a strictly
better number for free — and it makes the claim a property of the code.

**⚠️ AND THE TILTED AXIS IS GATED OFF, WHICH IS THE FINDING THE REVIEWER LED WITH.**
`Params.conform_axis` is a free direction vector (D51) and every conformed case in the suite cast
straight down, so the whole suite ran ONE configuration of it. On a tilted axis the float32 ray
origin no longer lies on the double ray, the divergence is **ALONG** the ray, and no
reconstruction removes it: **1.9e-06 m on the ramp above and 1.5e-05 m at 20 km with axis
(0.2, −1, 0.13)**, against 0.0 for every coordinate axis. (Rounding the axis to float32 first was
tried: 1.9e-06 → 1.7e-06. It does not help.) `Surface.batchable` therefore declines the batch
there and the per-query path — the reference — serves that configuration alone, `BJ_tilted_axis`
is the case that builds in it, and `conform_parity` reports it as a SKIP rather than as agreement
it never tested.

**2. THE BATCH WAS PER CURVE, AND THAT MADE IT A LOSS ON THE ROW IT WAS AIMED AT.** `ray` rebuilds
its second input on every execution, so each call carries a **fixed cost that scales with the
SURFACE and not with the query count** — 0.34 ms at 5 022 terrain prims, 2.25 ms at 80 352. P5 paid
it once per CURVE, which is invisible on the one-curve fence it was measured on. Measured
in-process, best of 3, toggling only the batch (a pure cache fill, so the output is identical):

| row | P5, batch ON/OFF | after the hoist |
|---|---|---|
| `fence_2km` (one curve) | 1.06x | **1.39x** |
| `streets_300c_smooth` (300 curves, 2 376 terrain prims) | **0.99x** | **1.28x** |
| `streets_300c_mid` (9 504 prims) | **0.96x** | **1.21x** |
| `streets_300c_big` (38 016 prims) | **0.94x** | **1.20x** |
| `streets_300c_rough` (38 016 prims, 38.5 % deformed) | 0.99x | **1.15x** |

Four of the five rows were **slower with the batch on than without it**. `place.build`'s pass A is
split in two now — plan every curve, take ONE `ray` execution for the whole build, then place —
and `conform.prefetch_all` is that execution. The same split also builds **one `Surface` per
build instead of one per curve**, which was 300 traversals of the same terrain's bounding box.
**`ray_executions_per_build` is the tripwire**: reverting to per-curve reads 40 against a ceiling
of 1.

**3. 47 % OF EVERY BATCH WAS FETCHED FOR NOTHING, AND NO CHECK COULD SEE IT.**
`conform_prefetch_hit_rate` reported `fallback / batched`, which is **0.0 by construction when the
batch over-fetches** — it could only ever fail on fetching too little. Counted by class over the
ladder:

| enumerated | batched | consumed |
|---|---|---|
| stations, their `delta` partners, the two end reads | 90 300 | **100 %** |
| **gap midpoints and their `delta` partners** | 144 000 | **0 % on the fence, 9 % on 300 streets** |

The midpoints are read only by `_bend_deviation`, which runs only for a piece that will actually
DEFORM — and the enumeration cannot know that yet. They are not enumerated any more; they fall
through to `_at`, which costs a deformed piece one Python drop per gap and a packed piece nothing.
The check now reports **`[used/batched, fallback/batched, batched]`** with both ceilings on the
call, and there is a second row of it on a **many-short-curve, packed-dominant fixture**
(`tripwire_streets_conformed`, 40 × 20 m over one heightfield, 87 % packed) because a single long
curve cannot represent the shape.

**4. THE HIT TEST BUILT ONE `hou.Point` WRAPPER PER QUERY — P5b's defect, one object down.**
`set(pt.number() for pt in grp.points())` was **5x the verb execution it decorated** (0.0081 s
against 0.0016 s over 34 002 queries) and 306 600 wrappers on the conformed street row.
`useprimnumattrib` makes the verb write `hitprim` instead: −1 on a miss, the primitive number on a
hit, and measured against the group over three surfaces including **40 zero-distance hits** they
disagree on 0 points. (`putdist` + `dist != 0` is NOT a substitute — it calls all 40 of those a
miss.) **`points_wrappers_built` is the new tripwire**, ceiling 8; restoring the group read reads
**208 / 7 280**.

**5. `Surface.hits` / `Surface.misses` ARE DELETED.** Written by both drop paths, read by nothing
(`grep`), and since P5 they counted prefetched probes rather than placements — so the obvious
thing to build on them would have reported a hit rate over points that never reached geometry.

**6. THE MEMORY COLUMN P5 NEVER STATED, and it moved the OPPOSITE way to §11.2 P5's promise.**
§11.2 said P5 "deletes the 24 MB memo cache". It kept it, made it the batch's destination and
filled it eagerly. Peak working set, kernel32, fresh hython per invocation, best of 5:

| row | pre-P5 `930b642` | P5-era `32f7345` | **this cycle** |
|---|---|---|---|
| `fence_2km` | 473.6 MB | 518.5 / 514.4 MB | **480.7 MB** |
| `streets_300c_smooth` | 897.4 MB | 1 103.5 / 1 114.9 MB | **917.2 / 918.6 MB** |
| `streets_300c_big` | 992.8 MB | 1 188.0 / 1 189.8 MB | **1 041.7 / 1 026.4 MB** |

**P5 cost +209 MB of peak on the conformed street row and this returns 188 MB of it.** What is
left is real and is recorded rather than hidden: the `ray` path takes a **one-time ~16 MB step**
per session on the 2 km fence that is never returned (12 cooks with the batch off plateau at
440.9 MB, 12 with it on step to 456.9 MB, 12 more with it off again stay at 456.9). It plateaus —
it is Houdini's own allocator holding the verb's scratch, not a growing leak.

**7. AND THE ROWS ARE COMMITTED NOW — `tests/polychain/conform_bench.py`.** Every headline number
in §11.8 P5/P5b/P6 came from rows (`fence_2km`, `streets_300c`, `hill_2km_adaptive`) that `grep`
could not find anywhere in the repo, and the reviewer who rebuilt them got the **opposite sign**
for P5. The bench is a ladder over the **two variables that decide the item** — the terrain's prim
count and its roughness — the same way `scale_gate.py` ladders radius and z-mode, and it prints
the packed/deformed split, the batched/consumed counts and the peak working set on every row.

**MEASURED ACROSS TWO TREES, FRESH HYTHON PER INVOCATION, BEST OF 5, TWO PASSES** (`git worktree`
at `32f7345` and at the pre-P5 `930b642`):

| row | pre-P5 | P5-era HEAD | **this cycle** | × vs HEAD | × vs pre-P5 |
|---|---|---|---|---|---|
| `fence_2km` | 0.1572 s | 0.1454 / 0.1432 s | **0.1086 / 0.1111 s** | **1.32** | **1.45** |
| `streets_300c_smooth` | 1.9106 s | 1.7790 / 1.7757 s | **1.2044 / 1.2072 s** | **1.47** | **1.58** |
| `streets_300c_big` | 5.5613 s | 2.2343 / 2.2139 s | **1.5003 / 1.5117 s** | **1.48** | **3.70** |
| `streets_300c_rough` | — | 2.3019 / 2.3112 s | **1.6943 / 1.6905 s** | **1.36** | — |
| `streets_300` (no surface — the control) | — | 0.2027 / 0.2005 s | 0.1931 / 0.1896 s | 1.05 | — |

⚠️ The `streets_300c_big` column against pre-P5 is **P5b's** win, not this one — that row reads
5.56 s at `930b642` because `Surface.__init__` wrapped 38 016 prims once per curve there. The
column that belongs to this item is "× vs HEAD".

**SIX MUTATIONS, SIX RED**, each applied by byte-exact replacement and reverted md5-exact
(`git diff` clean afterwards):

| mutation | verdict |
|---|---|
| the **position** reading restored (P5's own D108) | **RED** — `ray_verb_semantics` alone, and **0 other values moved**: the dirty trials are the ONLY thing in the suite that can see it |
| the point **group** hit test restored alongside `hitprim` | **RED** — `points_wrappers_built` 208, `_streets` 7 280 against a ceiling of 8 |
| the tilted-axis gate removed | **RED** — `ray_verb_semantics` and `conform_parity` on `BJ_tilted_axis`, 7 values moved |
| the batch back to **one execution per curve** | **RED** — `ray_executions_per_build` 40 against 1 |
| the **gap midpoints back** in the enumeration | **RED** — both `conform_prefetch_hit_rate` rows and `conform_cache_per_element_streets` |
| `prefetch_all` fills NOTHING (P5V's X1 shape) | **RED** — both `conform_prefetch_hit_rate` rows |

**Baseline: 89 → 90 cases, 5 488 → 5 555 values; 67 added, 0 removed, TWO moved, 0 ok/skip flag
changes** — re-derived key by key, index-aware. The two moves are the two conform tripwires whose
own definitions changed: `conform_cache_per_element` **18.7 → 17.6** (the midpoints leaving the
memo) and `conform_prefetch_hit_rate` **[0.0, 0, 374] → [0.9952, 0.6923, 208]** (a different pair
of ratios). **`geometry_digest` moved on 0 of 88 cases** and no other recorded value moved at all.
The 67 added are `BJ_tilted_axis`'s 62 and five new tripwire rows.
Suites: **90 cases / 5 555 check rows / 0 failing**, 286 unit tests / 9 625 subtests OK, HDA
checks 0 failing, 9 ladder rows 0 failing.

**TWO SMALLER CORRECTIONS TO COMMITTED TEXT, both re-measured.** D110's 64-bit trap expression
does not reproduce at the scale it claims — `sin(x·1e-6) − x·1e-6` returns exactly 0.0 at
`vex_precision="32"` only at **x ≈ 360**, and at 20 000 it returns −1.3336539e-06 against a true
−1.3333067e-06, i.e. 32-bit is accurate to 3.5e-10 there. D103's `@P.x*1.0000000001 - @P.x` is the
one that demonstrates it at 20 km (**exactly 0.0 at 32, 2.0000006770715117e-06 at 64**), and the
parm is `vexsnippet`, not `snippet`. And §11.8 P6's *"the citygen street case is 100 % DEFORMED
the moment a terrain is connected"* is one terrain: the same 300 × 60 m streets are **8.8 % / 16.3 %
/ 27.6 % / 38.5 % deformed** over four heightfields and the 2 km conformed fence is **0.2 %**. That
makes P6's decline stronger, not weaker.

**WHAT THIS SHOULD TEACH THE NEXT AGENT — a sharper form of P5R's own rules, numbered on from
them:**

5. **A parity check green at exactly 0.0 is a claim about the FIXTURES until a dirty fixture says
   otherwise.** Analytic surfaces with round slopes, sampled at round stations, have float32-exact
   answers. Every one of `ray_verb_semantics`' original eight was one. Add an irrational one, and
   add it at scale.
6. **A ratio that can only fail in one direction is half a check.** `fallback / batched` cannot
   see over-fetch; it read a perfect 0.0 while 47 % of the batch was dead weight.
7. **A fixed per-call cost is invisible on a one-call fixture.** The row that decides a batching
   item is the one with MANY calls, and if it is not in the suite the item's sign is unknown.
8. **An artist parameter with one value in the suite is an untested parameter.** `conform_axis`
   had 89 cases and one configuration, and the configuration nobody ran is the one that diverged.

---

#### P5V — independent verification of P0–P5R: everything reproduces, and one fix was pinned by nothing (2026-08-22)

A fresh agent that wrote none of the port re-ran it from clean, re-derived the baseline movement
key by key, mutation-tested it, re-measured the headline against a `git worktree` at the pre-port
commit, and re-confirmed all four gates. **The port stands.** One survivor was found and closed,
one pre-existing geometric gap was found and is recorded as standing finding (11), and one line of
§11.8's own bookkeeping is corrected.

**1. FROM CLEAN, ACTUAL COMMANDS.** `python -m pytest tests/unit -q` → **286 passed, 9 625
subtests, 1.27 s**. `hython tests/polychain/run_scene_checks.py` → **89 cases, 5 393 check rows,
0 failing, no baseline movement printed**. `hython tests/polychain/run_hda_checks.py` → **0
failing** (8 sections). `hython tests/polychain/scale_gate.py` → **9 rows, 0 failing**
(arc_80/kit **0.409 s**, arc_10 **1.229 s**, arc_80/adaptive **1.261 s**).

**2. BASELINE MOVEMENT, RE-DERIVED KEY BY KEY** against `ea010e5` (the commit before the port),
index-aware so the one duplicate name in `N_marker_mixed` is not silently collapsed:

| | pre-port `ea010e5` | HEAD `52fc4fa` |
|---|---|---|
| cases | 87 | 89 |
| recorded values | **5 063** | **5 393** |
| added / removed / **moved** | — | 330 / 0 / **21** |
| `geometry_digest` moved | — | **0 of 87** |
| `ok`/`skipped` flags changed | — | **0** |

All 21 moves are `stamp_parity`'s *compared* count, `diffs` 0 throughout — the check's own
widening, exactly as P1 recorded.

⚠️ **§11.8's closing paragraph is wrong on one point and is corrected here.** It says *"of the
5 063 original values exactly three moved… `stamp_calls_per_piece`, `curve_sample_scaling`,
`conform_cache_per_element`"*. Those three live in `ZZ_port_tripwires`, a case **P0 created** —
they were never among the 5 063. Of the pre-port values **the 21 `stamp_parity` counts are the
only ones that moved**, which is a stronger statement, not a weaker one. (The same paragraph says
5 392 where the runner emits **5 393** rows; `baseline.json` is keyed by name, so
`N_marker_mixed`'s two `marker_offset_m` rows collapse to one entry. Both figures are right about
different things.)

**3. CITYGEN IS UNTOUCHED, PROVEN TWO WAYS.** `git diff --name-only ea010e5 HEAD` contains **no
citygen path**, and no module outside `polychain/` imports it. Run anyway:
`tests/citygen/run_scene_checks.py` reports **27 failing at HEAD and 27 failing in a worktree at
`69db56c`** — identical, pre-existing, unrelated.

**4. MUTATION TESTING — TWELVE MUTATIONS, ELEVEN KILLED, ONE SURVIVOR.** Every mutation applied
by exact byte-level string replacement (line terminators honoured, so the revert is md5-exact)
and the tree verified against a pristine md5 list afterwards. `git diff -- polyfactory/` is
**empty** at the end: no production file moved.

| # | mutation | verdict |
|---|---|---|
| M1 | bulk stamp writes `pc_u` + 1e-6 on **prims 2..n only** | **RED** — `stamp_parity`, 88 checks |
| M2 | the sampler's segment table shared between curves of equal vertex count (a stale memo) | **RED** — 92 scene checks (43 `sampler_matches_kernel`, 18 `corner_breach_m`, 16 `corner_abut_m`…) **and** a unit test |
| M3 | P3 suppresses **one** `pc_warn_bend_resolution` where the name still fires elsewhere in the case | **assertion SURVIVOR** — see below |
| M3b | …the first one of **every build**, so single-warning cases lose theirs | **RED** — 7 `warnings` |
| M3c | the warning suppressed outright | **RED** — 10 `warnings` |
| **X1** | **`span_ends`' threaded pair forced to `None`** | **TRUE SURVIVOR — see below** |
| X2 | P3's station cache built and then never consumed | **RED** — `station_share_hit_rate` |
| X3 | the stamp row's prim count off by one | Houdini's own guard: `Incorrect attribute value sequence size` |
| X4 | `_stamp_bulk` writes one column's values under another name | Houdini's own guard: `TypeError` on the int column |
| X5 | `hda.colour_warnings`' prim count off by one | **RED** — `warned_elements_are_coloured` `[40, 39, 0]` |
| X6 | `_stamp_bulk` materialises all fifteen columns before writing | **RED** — `stamp_bulk_peak_kb` |
| X7 | the two `bisect` **expressions** swapped (function *and* EPS sign) | **RED** — 44 scene checks + the unit parity test |
| X7b | the two `bisect` **function names only** swapped | **GREEN on all 89 scene cases, 0 baseline movement** — RED on the unit parity test alone |

X7b reproduces P2's own recorded claim exactly, which is the point of re-running it: that branch
is pinned by `TestSamplerCacheParity` and by nothing else, and the geometry suite genuinely
cannot see it.

**⚠️ THE SURVIVOR: `span_ends` — P5R's own largest fix — WAS PINNED BY NOTHING.** P5R added
`stamp_calls_per_piece_deformed` for P1's blind branch and `station_share_hit_rate` for P3's dead
fallback, and then shipped its own biggest packed-branch change with no tripwire at all. Forcing
`ends` to `None` inside `span_ends` — which is legal, because the pair is a pure cache and a miss
re-samples to the identical value — leaves **the scene suite, the HDA suite, the unit tests and
the baseline diff completely green** while the packed fixture goes from **3.0 to 13.0
`Path.sample` calls per piece (4.33x)**, and the deformed one from 23.267 to 25.267. That is P0's
lesson and P5R's own lesson, missed on the third pass.

**Closed: `path_sample_calls_per_piece`**, on BOTH fixtures the way `stamp_calls_per_piece`
learned to run on both — **3.0 (ceiling 4.0)** packed, **23.267 (ceiling 24.0)** deformed. The
same mutation is now **RED on both rows**. Baseline: 5 393 → **5 395**, 2 added, 0 removed,
**0 moved**.

**The M3 survivor is a different animal and is recorded, not fixed.** `warnings` and
`warn_summary` assert the *set of warning names*, so dropping one of three occurrences of a name
that still fires elsewhere in the case is invisible to every assertion — but it **moved two
recorded values** (`B_rect_closed/warnings` `3 → 2` and its `warn_summary`), so the baseline diff
catches it. That is §11.3 rule 5's mechanism working as designed, the same category as P3's
`base_y` survivor, and it is why the movement list is read on every port commit.

**5. THE HEADLINE, RE-MEASURED INDEPENDENTLY.** `git worktree add` at `69db56c`, a bench written
from scratch (not P0's), best of 5, **two interleaved passes**, a fresh `hython` per invocation:

| row | pre-port `69db56c` | HEAD `52fc4fa` | × |
|---|---|---|---|
| `packed_20km` (R = 80 m, 10 000 packed) — the "real node cook" | 0.7053 / 0.7114 s | **0.3929 / 0.3899 s** | **1.81** |
| `packed_straight` (20 km resampled) | 0.6694 / 0.6786 | 0.3532 / 0.3297 | 2.03 |
| `deformed_10` (R = 10 m, 339 864 prims) | 1.7229 / 1.7289 | 1.2975 / 1.1939 | 1.44 |
| **`streets_300`** (the citygen shape) | 0.4959 / 0.5046 | **0.2113 / 0.1981** | **2.50** |
| **`corners_200`** (20 km + 200 real ±6 m kinks, miter) — **the worst case** | **11.9802 / 12.2177** | **1.0753 / 0.9740** | **12.30** |
| `plan_display` (Display = Plan) | 1.1134 / 1.0598 | 0.4663 / 0.4273 | 2.48 |
| `colour_warn` (340 000 prims, every third warned) | 0.7628 / 0.7210 | 0.1263 / 0.1157 | 6.23 |

And the same ladder through the committed harness, one run each:

| `scale_gate` row | pre-port `69db56c` | HEAD | × |
|---|---|---|---|
| two_point | 0.493 s | 0.232 s | 2.13 |
| resampled | 0.650 | 0.328 | 1.98 |
| arc_2000 / kit | 0.705 | 0.386 | 1.83 |
| **arc_80 / kit** | **0.695** | **0.409** | **1.70** |
| arc_10 (deformed) | 1.636 | 1.229 | 1.33 |
| arc_80 / adaptive (deformed) | 1.801 | 1.261 | 1.43 |

**P5R's correction (1) is independently confirmed: the pre-port arc_80/kit row is ~0.70 s on this
machine, not 0.933 s.** Two harnesses, two trees, four passes, and nothing read above 0.712. The
1.8x headline is the honest one and the 2.10x was an artefact.

⚠️ **AND THE MEMORY COLUMN, WHICH P5R'S OWN RULE 4 ASKS FOR.** `scale_gate`'s `dRSS` on the
deformed row is **152.5 MB pre-port against 200.4 MB now** — the P1 regression is real, is
reduced but not gone, and the log already says so. It is not asserted (that column is noisy by
±50 MB); `stamp_bulk_peak_kb` is.

**6. ALL FOUR GATES RE-CONFIRMED — and the harness that does it is committed this time**
(`tests/polychain/gate_images.py`, §0.0's "reuse it, do not rebuild it" honoured on the third
rebuild). It drives the HDA's own parm page, asserts the page and the kernel agree on ids AND
rounded point positions, hands the result to the committed checks, and rasterises the NODE's
output to PNG with `zlib` alone.

* **PC-G1 — PASSES.** The closed 12 × 8 rectangle, a 10 × 6 L and a 3 m close-up L, each in
  **both** corner modes, all driven from the page: `g1_*_parm_face` agree on every element,
  `exact_fill_m` ≤ 4.4e-07, `max_gap_m` ≤ 5.4e-07, `axis_on_curve_m` ≤ 5.0e-07, `corner_abut_m`
  **0.0**, `corner_seam_m` **0.0**, `corner_breach_m` **0.0**, `corner_turns` four 90° miters on
  the rectangle, `inward_faces` **0**. Judged on `VG1_closeup_{miter,bend}_top.png`: the miter's
  two legs terminate into a corner post with the 45° bisector drawn clean across it; the bend
  turns through the elbow as one continuous chamfered band with no corner post (D36's ring weld)
  and only the accepted butt notch.
* **PC-G2 — PASSES, on terms one notch narrower than recorded (see finding 11).** A 20 m spline
  turning ±3.6 m in plan and climbing 2.4 m, resampled at ~0.21 m, over the 2D terrain, conform
  ON, all three z-modes plus Tilt to Surface, all from the page: `conform_contact_m` **0.0**,
  `conform_drape_m` **1e-06**, `plumb_deg` **0.0** over 26 vertical pieces, `flat_stepped_m`
  **9.7e-08**, `bank_deg` **32.79**, `inward_faces` **0**, `over_unpacked` **0**, no warnings.
  Judged on `VG2_{vertical,stepped,adaptive}_side.png` and `VG2_camber_front.png`: the pickets'
  ribs are dead plumb while the foot tracks the ground line; the adaptive ribs rake perpendicular
  to the drape; the stepped posts make the expected flat-top sawtooth; and the front elevation
  shows the cambered run visibly rolled onto the cross-fall.
* **PC-G3 — PASSES.** `scale_gate` 9 rows, 0 failing, both z-modes, 10 000 packed / one
  `geometryid` on five rows and the two correct unpacks at 360 000 points.
* **PC-G4 — PASSES.** `run_hda_checks` section 4: the payload replaces the modules and the
  styleId, matches the kernel built from the `Style` object, and **`parms_inert_under_payload`
  sweeps 39 parms, `moved: none`** — on D107's `adaptive` fixture, the one that can see `padding`.

**⚠️ NEW STANDING FINDING (11) — D98's FLATTEN-UNDER HAS A RESOLUTION LIMIT AND NOTHING WARNS.**
On the PC-G2 fixture above, `stepped_float_m` reads **0.1 m of air** under one panel with
`flatten_stepped` ON, and `warnings` is **empty**. `_stepped_base` takes the minimum of the drape
at the **module's own stations** (0.25 m on the starter panel); where the conformed ground dips
between two of them, the piece is planted on a datum that is not the lowest ground under it.
D25 warns when a piece cannot resolve the path it bends along; the flatten has no equivalent.
**This is NOT a port regression** — the identical fixture, run against a worktree at `69db56c`,
reads **0.1 and `warnings` []** as well. It is recorded in `gate_images.py`'s `KNOWN` map as the
accepted limit, the way D36's butt wedge is, and the honest fix is a kernel change (sample the
datum on the underside's own points, or emit a resolution warning) — a cycle, not a patch.

**Suites after this round: 89 cases / 5 395 checks / 0 failing** (2 added, 0 removed, 0 moved),
**286 unit tests OK**, **HDA 0 failing**, **9 ladder rows 0 failing**, **gate_images 0 failing**,
`geometry_digest` unmoved on all 87 pre-port cases. **No production code was changed by this
round.**

---

#### P5cV — independent verification of P5/P5c: everything reproduces, and the check that pinned D70 could not see it (2026-08-22)

A fresh agent that wrote none of P5, P5b, P6 or P5c re-ran the suites from clean, re-derived the
baseline key by key, mutation-tested the ported surface, re-confirmed all four gates and
re-measured the headline against a `git worktree` at the pre-port commit. **Every substantive
claim in P5c reproduces.** One check was pretending, one committed number does not reproduce, and
one fact nobody had written down is now written down.

**1. SUITES, FROM CLEAN.** 286 unit tests OK (61 + 91 + 63 + 49 + 22). `run_scene_checks`
**90 cases / 5 555 rows / 0 failing** in 7.3 s. `run_hda_checks` **0 failing**. `scale_gate`
**9 rows / 0 failing**, both z-modes. `gate_images` **0 failing**, 11 PNGs. `conform_bench`
runs and reproduces P5c's ladder exactly (**0.2 % / 8.8 % / 16.3 % / 27.6 % / 38.5 % deformed**).
`git diff 930b642..HEAD --name-only` touches **nothing under citygen**.

**2. BASELINE, KEY BY KEY, INDEX-AWARE.** Against `32f7345` (the commit before P5c):
**89 -> 90 cases, 5 488 -> 5 555 values, 67 added, 0 removed, 2 moved, 0 flag changes** — exactly
as reported. Against `930b642` (the commit before the whole P5 cycle): **160 added, 0 removed,
ONE moved.** Both of the first two are the tripwires whose own definitions changed; the third,
smaller move has a stated cause:

| key | before | after | cause |
|---|---|---|---|
| `conform_prefetch_hit_rate` | `[0.0, 0, 374]` | `[0.9952, 0.6923, 208]` | the check was rewritten to report used/batched (P5c finding 6) |
| `conform_cache_per_element` (vs P5) | 18.7 | 17.6 | 374 -> 352 cached keys: the gap midpoints left the enumeration |
| `conform_cache_per_element` (vs pre-P5) | 17.55 | 17.6 | 351 -> 352: **the prefetch names one key on this fixture that no consumer reads**, which is the same key the rewritten hit-rate row reports as 207 of 208 used |

**`geometry_digest` moved on 0 of 89 shared cases**, and so did every other value in the suite.
The port's predicted "~1e-6 m of baseline movement" (§11.5 risk 1) **never happened** — D111 is
why, and that is the single most valuable outcome of the P5 cycle.

**3. MUTATION TEST — 17 mutations, 17 RED at suite level, one internal survivor found and closed.**
The tree was restored md5-exact after every one (`git status` clean, both kernel files hashing to
their committed value). ⚠️ **The brief's first two mutations do not exist to make: there is no VEX
in the shipped kernel at all.** P6 is declined, `grep` finds no `attribvop`, no `vexsrc` and no
`vex_precision` outside the docs, and the only verbs the kernel executes are `ray`, `clip` and
`polyfill`. They were translated onto the real float32 surface instead.

| # | mutation | verdict |
|---|---|---|
| M1 | read the verb's POSITION, all three components (a bigger downgrade than P5's) | RED — **19 rows**, `conform_parity` on 18 committed cases + `ray_verb_semantics` |
| M1b | read the along-axis component of the POSITION (**exactly P5's code**) | RED — `ray_verb_semantics` **alone**, everything else still 0.0. P5c's claim reproduces exactly |
| M2 | the batch diverges from the reference by **one ULP** from query index 2 on | RED — `ray_verb_semantics` at 8.9e-16 m (it asserts `== 0.0`, so one ULP is enough) |
| M3 | `bidirectionalresult` `closest` -> `farthest` (D70's nearest-wins) | RED — but see 4 below |
| M4 | drop D52's normal flip in the batched path | RED — 19 rows, `camber_deg` 180.0 |
| M5 | take `dist` unsigned (lose the backward-hit sign) | RED — **56 rows**, 9 distinct checks |
| M6 | `hitprim` miss test broken (a miss reads as a hit) | RED — `conform_misses`, `warnings`, both parity checks |
| M7 | the batch's answers paired to the wrong key (§11.5 risk 3, index identity) | RED — **63 rows**, 8 distinct checks |
| M8 | `batchable = True` (batch a tilted axis) | RED — `ray_verb_semantics` gate + `conform_parity` at 1.391e-06 m |
| M10 | `prefetch_all` fills nothing | RED — both hit-rate rows, `[-1.0, -1.0, 0]` |
| M11 | the batch back to once per CURVE | RED — `ray_executions_per_build` **40** |
| M12 | the gap midpoints back in the enumeration | RED — `conform_prefetch_hit_rate` 0.7555 used |
| M13 | one `Surface` per curve again | RED — `ray_executions_per_build` 40 |
| M14 | the hit test back to a point-group read | RED — `points_wrappers_built` **208 / 7 280**, the reported numbers exactly |
| S2 | the enumeration loses the module's own station fractions | RED — both hit-rate rows, 4 016 fallback keys on streets |
| S6 | the shared `Surface` silently ignores `params.conform_axis` | RED — `axis_on_curve_m` 1.16 m on `BJ_tilted_axis` |
| PC-G4 | D91 reverted (`padding` applied under a wired payload) | RED — `parms_inert_under_payload` **`moved: padding`**. Cycle 12's fixture fix is not pretending |

**4. THE SURVIVOR (D113), and it is the one the brief said to hunt for.** M3 flipped
`bidirectionalresult` to `farthest` — the parm that IMPLEMENTS D70's "look both ways, nearest
wins". `ray_verb_semantics` **stayed green**, and its own docstring names `bridge_deck` and
`exact_tie` as the trials that exist for exactly this. Probed directly: **all ten trials still
read 0.0**, because both surfaces are symmetric about the query (ground -2 / deck +2 / query 0),
so `closest` and `farthest` are the same point. The rule was caught only by `conform_parity` on
one scene case (`BJ_conform_deck`, 3.4 m) — luck of a fixture, not the pin the docstring claims.
**Closed in this round:** a `deck_offcentre` trial (ground -2, deck **+3**) is added, and the same
mutation now reads `ray_verb_semantics ... deck_offcentre: |dP| 5.000e+00 m`. 554 points over 11
surfaces, still `[0.0, 0, 0.0]`, no baseline value moved. `rtolerance` 1e-6 -> 0.01 is also a
survivor — **0 failing rows in the whole suite** — but that one the code already declares in
place ("nothing probed here can tell 1e-6 from the node default"), so it is a known gap and not
a hidden one.

**5. ONE COMMITTED NUMBER DOES NOT REPRODUCE.** D111's table quotes the position route at
**6.104e-05 m at x = 20 000**. Re-measured on the committed `dirty_ramp_20km` trial data, max
over x/y/z: **9.746e-04 m** — sixteen times larger — and the **y component there is 0.0**; the
whole 20 km divergence is in x/z, where the float32 ray origin sits up to an ulp of 20 000 from
the double query. (The ramp figure is right and is the y component: 2.384e-07 m; max over xyz it
is 9.172e-07 m.) The direction of D111 is unaffected — the distance route is **0.0 at both** —
but the number is corrected in `conform.py` and in D111.

**6. AND PARITY IS NOT ACCURACY.** At x = 20 000 **both** readings sit **8.569e-04 m from the
analytic surface**: `hou.Geometry.intersect` is itself float32 at world magnitude, so the
reference `drop_many` is measured against quantises the drop at the ulp of the COORDINATE. This
is pre-existing and identical pre-port — the port reproduces the reference exactly, which is what
was claimed — but nothing anywhere said it, and phase 2 at city scale needs to know it.

**7. THE HEADLINE, RE-MEASURED INDEPENDENTLY** — `git worktree` at the pre-port commit
`69db56c`, two interleaved passes, best of 5 per process, fresh `hython` per row, **prim count
asserted identical on both trees**, peak working set (kernel32) stated because P5R's rule 4 says
the memory column is part of the measurement:

| row | pre-port `69db56c` | HEAD | x | peak MB, pre -> now | prims |
|---|---|---|---|---|---|
| `streets_300` (300 x 60 m, no surface — the citygen control) | 0.4356 s | **0.1949 s** | **2.23x** | 452 -> 468 | 9 000 |
| `streets_300c_smooth` (the same, conformed, 2 376-prim terrain) | 1.7403 s | **1.0436 s** | **1.67x** | 562 -> **666** | 9 000 |
| `streets_300c_rough` | 1.7457 s | **1.0304 s** | **1.69x** | 558 -> **667** | 9 000 |
| `fence_2km` conformed | 0.1670 s | **0.0838 s** | **1.99x** | 439 -> 448 | 1 066 |
| tight-arc deformed row | 0.0750 s | **0.0504 s** | **1.49x** | 439 -> 441 | 16 966 |
| 20 km resampled (20 001 verts) + 200 real 62-degree kinks, miter | 4.2732 s | **0.6517 s** | **6.55x** | 488 -> 519 | 26 332 |
| the same corners at 201 verts (no dense sampler load) | 0.8880 s | **0.4875 s** | **1.82x** | 479 -> 506 | 26 332 |

⚠️ **THE MEMORY COLUMN GOES THE WRONG WAY ON THE CONFORMED ROWS, AND THAT IS THE HONEST RESULT:
+104 MB and +109 MB of peak working set against pre-port.** P5c's "-188 MB" is measured against
the P5-era commit and is real; measured against **pre-port** the conform batch plus P1's bulk
stamp arrays still cost ~19 % more peak memory for ~1.68x the speed. That is a trade worth taking
on this workload and it is not a free win. (These are this audit's own fixtures at fresh sizes,
so they are not comparable row-for-row with P5c's absolute seconds — the ratios are.)

**8. GATES, GATE BY GATE.** PC-G1 **PASS** (headless): both corner modes through the parm face on
the rectangle, the L and the closeup, node output == `place.build` on `style_from_parms(node)`,
`exact_fill_m` 1.5e-08 to 4.4e-07 m, `corner_seam_m` 0.0, `inward_faces` 0; judged on
`VG1_rect_miter_top.png` (four legs closing on the spline, corner posts cut on the 45-degree
bisector) and `VG1_closeup_bend_top.png` (the elbow turning as one arris, no corner post).
PC-G2 **PASS** (headless): all three z-modes plus camber through the parm face,
`conform_contact_m` 0.0, `plumb_deg` 0.0, `flat_stepped_m` 9.7e-08, `bank_deg` 32.79 deg, 0
warnings; judged on `VG2_vertical_side.png` (ribs dead plumb, foot on the ground line, the spline
ignored), `VG2_stepped_side.png` (flat blocks stepping over the ground), `VG2_adaptive_side.png`
(ribs raking perpendicular to the drape) and `VG2_camber_front.png` (the rail visibly rolled onto
the cross-fall). PC-G3 **PASS**: 9 ladder rows, 0 failing, both z-modes, 10 000 packed and one
`geometryid` on five rows and the two correct unpacks at 360 000 points. PC-G4 **PASS**, and
**mutation-proved this round**: 39 parms swept `moved: none`, and reverting D91 reports
`moved: padding`. **All four gates still owe their GUI viewport pass** (§0.0's wedged bridge),
unchanged.

**§11 IS COMPLETE.** P0-P3, P5R, P5, P5b and P5c landed and verified; P4, P6 and OpenCL declined
with their measurements (§11.8 P4/P6, D109, D110). **P7 (bulk-read the miter glue and
`dress_caps`) is the only item never attempted** — rated low priority, worth something only on
corner-dense runs, and `prims_wrappers_built_mitered` (571 against a 600 ceiling) is the number
it would move. Nothing in §11 should be re-opened without a workload that justifies it.

**Suites after this round: 90 cases / 5 555 rows / 0 failing, 0 baseline values moved**, 286 unit
tests OK, HDA 0 failing, 9 ladder rows 0 failing, `gate_images` 0 failing. The only production
change this round is a docstring correction in `conform.py`; the only test change is the
`deck_offcentre` trial that closes D113.

---

### 11.9 HANDOVER TO PHASE 2 — what the ported architecture is, and what must not be undone

**Read this before touching §7's 2D array.** The port is finished and the shape it left behind is
load-bearing.

⚠️ **ONE CLAUSE OF THIS SECTION IS SUPERSEDED (D148, 2026-08-22).** "The kernel is verb-only and
node-free … a node would put a network back inside the builder" is **reversed** by
[§13](#13-native-network-architecture--the-rebuild-brief): the kernel becomes a readable node
network, because a one-Python-SOP body violates [`artist_ui.md`](artist_ui.md) §6 rule 10. **Every
other rule below stands and several get stronger** — rule 1 (never touch a wrapper in a loop),
rule 3 (read the smallest number a node offers), rule 4 (a batch stays additive), rule 5
(reordering is where determinism dies), rule 6 (the three trials) and rule 7 (warn-never-block, now
a *design requirement* — see D153). Rule 2's batching problem is structurally deleted for `ray`
and reborn as a per-NODE cost on many short curves (§13.9 R7).

**What it looks like now.** The kernel is **verb-only and node-free**: there is no `createNode`
anywhere in `polyfactory/polychain/`, and the only compiled SOPs it reaches are three verbs
executed inside the Python SOP that is already cooking — `ray` (`conform.Surface.drop_many`),
`clip` and `polyfill` (`place.clip_plane`, the corner cut). A verb runs in-process; a node would
put a network back inside the builder and cost the property that makes all of this possible.
**There is no VEX and no OpenCL in the shipped kernel** — P6 measured `copytopoints` + a 64-bit
`attribvop` snippet at ~9 % of the conformed row against HIGH risk to `geometry_digest`,
`pc_local` and prim numbering, and declined it (D109); OpenCL is declined for phase 1 outright
(D110). **Python stays where it earns its place**: `plan.py` (the fitting solve — it runs with no
Houdini imported, 89 unit tests, and native has no equivalent for exact-fill adaptive/tile/scale/
count with padding, markers and compose rules), `corner.py` (small-N combinatorics, where the
tool's correctness lives), `style.py` (the payload I/O adapter), `kit.py`, and `decompose.py`.
**The bulk of the win was never a language change**: it was 14 `hou.Prim.setAttribValue` calls per
piece becoming one bulk array write (P1), a segment table that was being rebuilt on every
`Curve.sample` becoming a memo plus a `bisect` (P2), four `len(geo.prims())` calls becoming
`intrinsicValue("primitivecount")` (P5R/P5b), and one `ray` execution per BUILD replacing 306 600
`hou.Geometry.intersect` calls (P5/P5c).

**What phase 2 must respect, or it reintroduces exactly what this removed:**

1. **Never touch a `hou.Prim` / `hou.Point` / `hou.Vertex` wrapper in a loop.** That is the single
   defect class this whole port removed, and it came back three times under three different
   names. Use `hou.Geometry`'s bulk array setters and `intrinsicValue`. Four standing tripwires
   watch it: `stamp_calls_per_piece`, `prims_wrappers_built(+_deformed/_mitered)`,
   `points_wrappers_built(+_streets)`. If a phase-2 row is slow, count wrappers before you
   consider a new language.
2. **A per-call fixed cost is invisible on a one-call fixture.** `ray` rebuilds its surface input
   on every `execute` (0.34 ms at 5 022 prims, 2.25 ms at 80 352). Batched per curve it looked
   like 1.45x on one long fence and was 0.94x — a LOSS — on 300 short streets. Phase 2 is N rows
   through the same kernel, i.e. many more calls: **any batch it adds must be hoisted to the
   outermost loop and pinned by a counter** (`ray_executions_per_build` is the pattern), and it
   must be benched on a many-short-curve fixture, not a long one.
3. **Read a native node's answer as the smallest number it offers.** `ray` gives the hit as both
   a position and a distance; the distance is one float32 rounding at the size of a *drop*, the
   position one at the size of the *world* (D111). At 20 km that is the difference between 0.0
   and 9.7e-04 m of baseline movement. And **parity is not accuracy**: `hou.Geometry.intersect`
   is itself float32 at world magnitude, so at 20 km both agree exactly on a value 8.6e-04 m from
   the analytic surface. If phase 2 works at city coordinates, that floor is what it inherits.
4. **A batch is a cache fill and must stay additive.** `prefetch_all` enumerates only the keys the
   plan can NAME; everything else falls through to the per-query Python path, which is slower and
   never different. That is what keeps both implementations live in one process and lets
   `conform_parity` prove them equal by asking BOTH rather than by diffing two runs. Do not let a
   phase-2 batch become the only implementation.
5. **Batching is reordering, and reordering is where determinism dies.** M7 in P5cV — shifting the
   batch's answers by one key — went red on 63 rows across 8 checks, and that is the check
   population phase 2 must keep intact. `geometry_digest` and `determinism` are the pins.
6. **A parity check green at exactly 0.0 is a claim about the FIXTURES until a dirty fixture says
   otherwise**, and **a trial that is symmetric about the query cannot see the parm that breaks
   the tie** (D113). Every new native call gets an irrational-slope trial, one at 20 km, and one
   asymmetric case.
7. **Warn-never-block is a contract.** Every verb call is wrapped so that a raise degrades to the
   Python path (D24/D34/D53). A tilted `conform_axis` already takes that route by design.
8. **The open item is not performance.** All four gates still owe their **GUI viewport pass**, the
   streets acceptance is unrun, and standing finding (11) — `_stepped_base` samples the drape at
   the module's own stations, so ground that dips between two of them leaves 0.1 m of air under a
   `flatten_stepped` piece with nothing warning — is a kernel cycle nobody has taken. **§11's only
   unattempted item is P7**, and it is worth less than any of those.

---

## 12. Phase 2 build log

Same convention as §10 — one subsection per cycle, every decision recorded. Phase 2's cycles live
here rather than in §10 so that §10 stays the phase-1 record and §11's port plan sits between
them in the order it was written. The build order these cycles follow is
[§7.10](#710-build-order-for-the-implementation-cycles).

### Cycle P2-0 — §7 written as a buildable spec (2026-08-22)

**No code.** §7 had been directional since 2026-08-21 ("detail when buildings picks it up"); that
time arrived, so this cycle turned it into something an implementing agent can build from, and
nothing else. §7 is replaced end to end; §§1–6 and §11 are untouched.

**Reference material read for it, not recalled** (dev-loop rule 1). The two RailClone pages that
actually define the 2D behaviour were fetched in full on this build:
`docs.itoosoft.com/railclone/style-editor/2d-arrays-generator-a2s` (the A2S slot list, Y Mode
Aligned/Free, the Evenly rules, the X Corner bevel rules, the whole Clipping Area block, and the
documented limit *"At present Adaptive mode only functions on the X axis"*) and
`docs.itoosoft.com/railclone/rc-slice-modifier` (**"20 nodes will be created, one for each
possible slice"**, plus the 12 named slice types and the 8 intersections by name). Both 403 to a
plain fetch and were read through the browser. The kernel was re-read rather than remembered:
`plan.pick` / `plan.candidates` / `Kit.resolve` / `Style.rules_for` / `place.read_curves` /
`place.build`'s two-pass structure and `style._check_slot` are what the three named extensions
(E1–E3) are sized against.

**The finding that shaped the whole section.** RC Slice's 20 pieces are not an enumeration to
copy — they are a **5 × 4 product table**, and the missing fifth column is RailClone's own
omission. Both axes draw from *the phase-1 `SLOTS` vocabulary unchanged*, so the inventory is
5 × 5 = 25 ordered pairs `<x_slot>_<y_slot>`, RailClone's 20 are exactly our subset with
`y_slot != "corner"`, and the bottom row of the table **is** the phase-1 slot list — which is why
a phase-1 kit is a valid phase-2 kit for the middle rows with no edit. The whole ~20-role
requirement therefore costs a vocabulary and a lattice walk, not a mechanism.

**That claim was checked, not asserted.** All 20 RC Slice piece names were mapped by hand to `(x_slot, y_slot)` pairs and the mapping run: 25 roles generated, all unique; `set(SLOTS) == {r for r in ROLES_2D if "_" not in r}` → **True**; the 20 mapped names are **exactly** our `y_slot != "corner"` subset (bijective, no leftovers on either side); and the column RailClone is missing is precisely `{start,default,corner,evenly,end}_corner`. That check is three lines and belongs in `tests/unit` as `roles_2d_is_the_slot_product` the moment `ROLES_2D` exists — cycle P2-3 owns it.

**The second finding.** A row is a phase-1 curve and the row list is a phase-1 *plan run on the Y
axis*, so §7's three row-placement modes (Y evenly / explicit heights / a second spline) are three
`Params` on one existing solver, not three features — and Y-adaptive, RailClone's documented
X-only wart, falls out for free.

**What the spec commits the implementation to.** One build call for N rows (§11.9 rule 2, and the
many-short-rows fixture exists from cycle P2-2, not from the gate); exactly three kernel
extensions (E1 `Rule.yclass`, E2 `pc_row_scale`, E3 kit role closure) totalling ~24 lines; no
forked solve; five inputs, frozen; and three gates — **PC-G5** facade closure (7 numbered pass
conditions, aligned with citygen_buildings §12.10 G2's L-footprint), **PC-G6** clipped areas,
**PC-G7** the row stack at scale and the one-call rule.

#### Decisions taken

| # | Decision |
|---|---|
| D114 | **A row is a phase-1 `Curve`, and the row list is a phase-1 PLAN run on the Y axis.** `decompose` + `plan.plan_sections` on a Y curve returns one `Placement` per storey: band = `s0..s1`, Y class = `slot`, storey number = `index`. There is no second solver, and `fit`/`evenly`/`justify`/`adjust_to_end`/`adaptive_pct`/D13's overflow cascade/D17's degenerate-pad guard are correct on the Y axis for the same reason they are correct on the X one |
| D115 | **N rows go through ONE `place.build` call as one curve stream**, never one call per row or per band. `place.build` already hoists the conform batch to the outermost loop over all curves (D112) and takes one `ray` execution per build; feeding it N rows inherits that, feeding it N times throws it away. This is §11.9 rule 2 and it is pinned by `ray_executions_per_build == 1` from cycle P2-2 on |
| D116 | **`pc_role` for 2D is the ordered pair `<x_slot>_<y_slot>`, both drawn from the phase-1 `SLOTS` vocabulary — 25 first-class roles.** RC Slice's 20 are the subset with `y_slot != "corner"`; RailClone has a Y Corner generator slot but never slices a Y-corner piece, so its inventory is short by one column and ours is not. `default_default` is written `default`, so `set(SLOTS) == {r for r in ROLES_2D if "_" not in r}` — an assertable compatibility claim. Aliases (`top`, `bottom`, `left`, `right`, `lt/rt/lb/rb`, `x_corner`, `y_evenly`, `xy_evenly`) normalise at kit read, the same shape as D4's `moduleRole` |
| D117 | **Precedence is resolved PER AXIS and only then producted** — a cell cannot have two roles, it has one X class and one Y class, so there is no 2D tie-break table. X order is phase 1's own, restated: run cap (D18) > `corner` > `marker:<id>` > `evenly` > `default`; Y order is identical on the Y solve, with `start`/`end` aliased `bottom`/`top` because they ARE the Y run's caps. The one genuine 2D conflict — does a corner column cut the cornice, or does the cornice run past it — is RailClone's **Extend To Side**, exposed as `pc_extend`, and it decides only which axis the cell degrades toward when the product cell is ABSENT. It is a tie-break for absence, never for presence |
| D118 | **The role fallback is a lattice walk performed as ROLE CLOSURE at kit read, not as a kernel branch.** The reader adds fallback roles to each module's own `roles` tuple, so `Kit.by_role` and `plan.candidates` are untouched. Order: exact cell → drop Y, keep X → drop X, keep Y → `default` → §3.4's stand-in box. **Y is shed first because closure beats cosmetics**: a `corner` piece is authored to mate at the bisector and dropping its corner-ness leaves a hole (a PC-G5 failure), while dropping a cornice's top-ness leaves a facade that is merely plain. Under `pc_extend = 0` the two middle steps swap — which is exactly what "this column stops at the cornice" means. Every degrade says `pc_warn_role_fallback` naming both roles; a silent stand-in is a defect and PC-G5 condition 5 counts them |
| D119 | **Rule scoping is a field, not a conditional.** `Rule.yclass` (blank = matches every row) filtered in `Style.rules_for`, with the row's class reaching `plan.pick` through `ctx["yclass"]` — three lines. Encoding row classes as `select = "conditional"` on `attr:pc_yclass` would have worked with zero kernel change, and was rejected: `choose`'s conditional branch consumes `select`, so a top-row rule could then never also be `random` or `sequence` — and random variant selection per row class is exactly what a facade wants |
| D120 | **One payload, two axes.** `pc_axis` (`x` default, so every phase-1 payload is a valid phase-2 X payload) splits the rule list into an X `Style` and a Y `Style`; `pc_style_meta["y_params"]` is a second `Params` dict read by the *same* `params_from_dict`. `Style` itself does not change, and the Y axis gets `sequence`/`random`/`conditional` for free — random storey heights and a conditional ground floor are the same mechanism as everything else |
| D121 | **A band height is an axis scale carried on the row curve (`pc_row_scale`), not a new solve.** Applied at the frame's up axis in `_packed_transform` and `_deform_positions`. §4.6's instancing rule already reads "transform × uniform-or-axis scale of the kit module stays a packed prim", so **a scaled storey stays packed** and PC-G3's property survives into 2D. PC-G5 condition 7 asserts `pc_row_scale != 1` unpacks nothing |
| D122 | **Y Mode Aligned = the datum row's bay COUNT per section; Free = each row solves its own length.** Aligned is free when rows are congruent (a deterministic solver on identical input already returns identical stations — PC-G5 condition 3 measures that rather than assuming it) and only bites on setbacks, tapers and Y-spline plan offsets, where the 2D stage runs `plan.plan_sections` on the datum row and re-emits the rest with `fill = "count"`. A row that physically cannot hold the count degrades to its own solve and says `pc_warn_y_align_lost`. The datum is the BOTTOM row: it is the one an artist looks at and the one that always exists |
| D123 | **`pc_elem_id` keeps its shape and `elem_id()` is not touched — the 2D address is COMPOSED into fields that already exist.** citygen_buildings §12.7 wants volume/face/bay/storey: volume and storey are the two halves of `pc_curve_id` (`"<arrayId>#<row>"`), face is the section index (on a closed footprint a section IS a facade leg), bay is the fill index. `B17#4|2|default|3|civic` reads as volume B17, storey 4, face 2, bay 3. D1's collision-free-by-construction property holds for the same reason it held before |
| D124 | **A closed footprint is CANONICALISED at row emission, so ids survive re-authoring.** Phase 1 numbers sections from point 0 in the authored direction, so rotating a closed footprint's start vertex or reversing it renumbers every face and moves every id — which §12.7 forbids and which phase 1 never had to face. The 2D stage rotates the point list so index 0 is the vertex with the lexicographically smallest millimetre-rounded position, and reverses when the signed plan area is negative. **Done at emission, outside the kernel, so not one phase-1 baseline value moves.** PC-G5 condition 6 is the check, and it is the strongest identity assertion in the tool |
| D125 | **Each closed sub-spline of the clip input is its own array**, with its own local frame, `arrayId` and `pc_elem_id` namespace — editing one moves zero elements in another (PC-G6 measures it as an elem-id set diff). **Nesting is even–odd by depth** (RC's `Hierarchy Checking = Complete`) because it is deterministic and needs no authoring; `pc_clip_mode` on the sub-spline prim overrides it per spline (RC's `None`), and `pc_clip_group` groups splines into one array (RC's `By Material ID`, renamed to something that is not a material) |
| D126 | **The clip cull policy is D11's pattern on a new axis.** RC's three: `0` remove · `1` preserve · `2` slice. Slice requires `pc_deform = 2` exactly as §4.2's tile remainder does, and a slice policy on a non-sliceable module **degrades to REMOVE, not preserve** — an overhanging window and a missing one are both defects, and the missing one is the one the artist notices and fixes — saying `pc_warn_clip_unsliceable`. The straddle test is 2-D point-in-polygon on the PLAN, before geometry exists, so `remove` builds nothing and `preserve` runs no boolean; only genuine straddlers reach `place.clip_plane`, which is the `clip` verb §4.3 already uses. No fourth verb |
| D127 | **The port count is frozen at 5 before any consumer wires it** (the streets lesson, and open-question 2's precedent): 1 footprint + markers, 2 kit, 3 style, 4 surface, 5 **auxiliary splines** discriminated by a prim attr `pc_purpose` ∈ `clip`/`exclude`/`yspline`. Input 5 is one port and not three because a Y profile and a clip boundary are both splines and the discriminator is data — the same call open-question 2 made for markers |
| D128 | **The Y spline is a PROFILE, not a second world-space path.** RailClone reads the Y spline's local X/Y and ignores Z; ours reads along-axis as height and off-axis as an outward plan offset applied to the footprint at that height, which gives batter, setback, taper and RC's double-curved case from one 2-D curve without asking anyone to author a second closed loop in 3D. The offset runs along each vertex's angle bisector scaled by `1/sin(θ/2)`, **clamped and warned** where it exceeds the local inradius rather than allowed to self-intersect. `polyexpand2d` is the noted escape hatch if true topology-changing offset is ever needed — and it inherits phase 1's measured lesson that it breaks planarity by ~2e-5 m |
| D129 | **PC-G5 is the acceptance gate and it is deliberately citygen_buildings §12.10 G2's own fixture** — the L-shaped footprint, 5 convex corners and 1 reflex. Seven numbered pass conditions, each a number: 24 corner joints within `bend_tol`, band boundaries within 1e-6 m, bay alignment under `aligned`, **zero slices** under adaptive-on-both-axes, zero silent stand-ins, an identical `pc_elem_id` set across three re-authorings of the same footprint, and packed fraction unaffected by `pc_row_scale`. Judged on an image of the reflex corner from ground to cornice, because the failure no number catches is a corner that closes numerically while the cornice returns the wrong way round it |
| D130 | **No second kernel.** No forked `plan.py`, no parallel fitting solve, no "2D version" of anything phase 1 already does. Phase 2 is one `hou`-free stage above the kernel (`polychain/array2d.py`) plus its adapter, plus exactly three named kernel extensions (E1–E3, ~24 lines). If phase 2 wants something the kernel cannot do, that is a kernel cycle taken in `plan.py` where the 286 unit tests already live — never a copy. Non-goals restated and kept: no massing (B2/B5), no junctions (B6), no boolean openings, no roof solving, no interiors, no expression engine, no per-face wiring, no new file formats, and RC's "Slope" declined with its reason |
| D131 | **`pf_polychain_slice` is the `clip` verb `place.clip_plane` already uses, run on a plane grid, plus RC's jigsaw rule asserted rather than assumed.** RC's `Adjust X/Y Size To Default Segment` is what makes the pieces mate, so it is on by default AND checked: every generated cell's bbox matches the default cell's size on the axes it is not a cap for, to 1e-6 m. A kit that fails that cannot close a facade, and it should say so at authoring time instead of at PC-G5 time |

#### Cycle P2-0 — final state

No code changed; the suites were not re-run because nothing they cover moved
(`git diff --stat` is `ideas/polychain.md` alone). Phase 1 remains closed and verified: 286 unit
tests, 89 scene cases, `run_hda_checks.py`, `scale_gate.py`, gates PC-G0..PC-G4.

**Next up: cycle P2-1** — `polychain/array2d.py`, the Y solve, `hou`-free, unit tests only.


---

### Cycle P2-1..P2-3 — the row stack, the 25 cells, and the four defects the suite found (2026-08-22)

**Built:** §7.10's first three cycles in one pass, plus the 2D data contracts (§7.3) and enough of
§7.6's clipped area to fill a rectangular facade panel. Commits `5ace508` (kernel + stage),
`37631cb` (harness + the defects it found), `fbd3112` (the images).

**What shipped**

| File | What it is |
|---|---|
| `polychain/array2d.py` (new, **`hou`-free**) | the Y solve, the row list, 7.2.1's Y precedence, D124's canonical footprint, D118's role closure, and §7.6 reduced to a frame plus a per-row span |
| `polychain/facade.py` (new, the adapter) | row emission through bulk array writes only, then **ONE** `place.build` call |
| `polychain/__init__.py` | `role_2d` / `split_role` / `ROLES_2D` / `ROLE_ALIASES` / `canonical_role`, `WARN_ROLE_FALLBACK`, `Rule.yclass`, `Rule.axis`, `Style.meta`, `Style.rules_for(slot, yclass)`, `Kit.role_fallbacks`, `Module.extend` |
| `plan.py` | E1's tail: `cell_role`, `candidates(rule, kit, role)`, `pick`'s scoped rule list, `ctx["yclass"]` |
| `place.py` | E2's axis scale on three materialisation paths, `_stamp_2d`, `ROW_ATTRS_2D`, and the one `array2d.classify` call |
| `kit.py` / `style.py` | `pc_extend`, `role_fallbacks` on the manifest; `pc_axis` / `pc_yclass` on the rule points |

**The Y solve is a phase-1 plan and nothing else.** `plan_rows` is `decompose.decompose` +
`plan.plan_sections` on a vertical profile — no fitting maths was written for phase 2 at all, which
is D130 measured rather than asserted. `13.0 m` of shopfront + storeys + cornice comes back as five
`Placement`s whose bands tile the height to 1e-9 m, at every height tried, with nothing sliced.

**The 25 cells resolve by ROLE, not by rule.** The facade style names no modules at all
(`Rule("default")`, `Rule("corner")`); `plan.candidates` resolves the cell role against the kit,
and E3's closure has already made sure the kit can answer. On the L footprint that produces
`default` 64, `corner` 24, `default_start` 32, `corner_start` 12, `default_end` 32, `corner_end`
12 — six cells, six different modules, zero warnings, and the same figure in **bend** mode produces
exactly the three `default_*` cells because D36 welds the ring and there is no corner slot to fill.

**FOUR DECISIONS, and one of them is a correction to §7.**

| # | Decision |
|---|---|
| D132 | **The Y solve runs on a TRANSPOSED kit** (`pc_size.x` ↔ `pc_size.y`). The 1D solver fits on `Module.length`, which is `pc_size.x`; a storey's nominal length is its HEIGHT. Data, not a fork — and `pc_row_scale` then falls out of the same solve. `pc_pad` is not swapped: §7.3.1 already says the same two numbers read as (left, right) on X and (bottom, top) on Y |
| D133 | **The `<slot>` field of `pc_elem_id` stays the X SLOT; `pc_cell` is stamped beside it.** §7.3.3's table maps "cell role → `<slot>`", but D123's own sentence is "`elem_id()` is not touched", and the address is already unique without the Y half because `pc_curve_id` carries the row. Keeping the X slot also keeps an id stable when a row's Y class changes (adding a cornice band would otherwise move every top-row id) |
| D134 | **A Y `corner` class is a PROFILE VERTEX, named on the plan.** §7.1 says a Y-spline corner vertex is a `corner` row, but 4.3's corner machinery places a corner MODULE at a vertex in world space and a string course is not that — it is the BAND that starts at the setback. So `y_class` names the row whose band starts on a profile corner, in the documented order (`start`/`end` > `corner` > `marker` > `evenly` > `default`), eight lines, no second solve |
| D135 | **A row is never sliced.** A `tile` Y fill whose remainder would be cut gives a SCALED row instead: half a storey is a defect and a storey 4 % short is a choice — D11's own argument, on the other axis |
| D136 | **The role closure is written back onto the KIT PAYLOAD**, not passed into the kernel as an object. `place.build` reads its own kit from input 2 (D77's two-face rule), so a closure computed beside it would be thrown away; expressed as `pc_role` on a copy of the kit geometry plus a `role_fallbacks` entry in the manifest, it is data — inspectable by the artist, read by the existing reader, needing no new argument |
| D137 | **The clip is a SPAN, not a cull.** §7.6's cost discipline says the boundary test runs on the plan before geometry exists; taken literally that is better than culling pieces, because the ROW's own span can be trimmed to the boundary and the fill then exactly fills what is left. `remove` is the intersection of the band's two scanlines, `preserve` their union; a rectangle is the identity case and a taper narrows every row with nothing built outside the line. Slicing a piece ON the boundary is still P2-7 |
| D138 | ⚠️ **A CORRECTION TO D121. `pc_row_scale` is the ROW's number — band ÷ the height of the module the Y solve chose — and it is right only while the cell is filled by that same module.** D118's lattice walk breaks that by design: a kit with no cornice puts a 3.2 m bay in a 1.0 m band, and the row then overshot the roof by **2.200000048 m** with `row_closure_m` at 0.0 and every other number green. The row carries its BAND (`pc_row_y0`/`y1`) and each piece scales its OWN nominal height into it; `pc_row_scale` remains the row's number and the fallback for a module that declares no height. Found by `row_fill_y_m`, which exists because "exact fill on both axes" has to be measured on the geometry and not on the solve |

**Two things §7 got wrong, both found by building it.**

1. §7.1 says the row's six prim attrs "are already harvested onto `Section.attrs` by D94, so they
   reach the fill rules with **no adapter change**". They are not: `place._prim_attrs` skips every
   `pc_` name on purpose, because the kernel's own attributes are not the spline's. `ROW_ATTRS_2D`
   names the five that must come through. Nothing moves in phase 1 — a curve that does not carry
   the attribute never gains it — and `attr:pc_yclass` becomes a usable conditional subject as a
   side effect.
2. §7.1's extension budget ("~24 lines, and no fourth") holds for E1–E3 themselves but not for
   their plumbing: `cell_role` has to reach `plan.candidates` for the closure to bite at all, and
   `corner.py`'s two ctx builders need `yclass` or a corner column on the top row resolves
   `corner` where the kit has `corner_end` — the PC-G5 case. Still no fork, still no second solve;
   just more call sites than the estimate.

**The harness** (`tests/README.md` has the commands):

* `tests/unit/test_polychain_array2d.py` — **59 tests, and it asserts `hou` was never imported**,
  because that property is what lets the whole Y solve be tested without a licence and one
  convenience import in a later cycle would take it away silently.
* `tests/polychain/cases2d.py` + `run_2d_checks.py` + `baseline_2d.json` — 13 cases, 27 checks
  each. **Most of those checks are phase 1's own, run unchanged** (`exact_fill_m`, `max_gap_m`,
  `corner_seam_m`, `determinism`, `geometry_digest`): a 2D array IS a phase-1 build over row
  curves, so the reuse is the assertion that no second kernel appeared, and a check that had to be
  forked would have been the finding.
* `tests/polychain/facade_bench.py` — the one-call/many-call ladder.
* `tests/polychain/facade_images.py` — PC-G5's pictures, on `gate_images.py`'s rasteriser
  **extended, not rebuilt** (§7.8 says so by name).

**FOUR DEFECTS THE SUITE FOUND ON ITS FIRST RUN**, none visible in the smoke build: D138 above;
`band` already being taken in the job loop (D99's flat band, `None` when there is none) so the
second piece of every build read `None`; `role_fallbacks` reading `scene.warns` as `{warn: ids}`
when it is `{id: {warn}}`, so **PC-G5 condition 5 was passing vacuously** at 0 degrades on a case
whose `warnings` row said 1 194; and a fixture that deleted the shopfront MODULE to test a missing
`default_start` CELL, which also removed the Y solve's height source and made the case measure two
variables at once.

**AND ONE THE IMAGE FOUND, which is exactly what §7.8 says the image is for.** The first render
skipped every non-packed prim — and a mitered corner column carries a world-space cut, so it can
never be packed (4.3). Every `corner` cell was absent from the picture that exists to judge the
corner, and the reflex vertex drew as an open gap. Fixed; it now reads ground-to-cornice as
`pier_base` → `pier` → `pier_cap` with the cornice band turning continuously round it.

**MEASURED** (`hython tests/polychain/facade_bench.py`, best of 3, Houdini 22.0.398):

| row | curves | elements | seconds | `ray` execs | prim wrappers | peak WS MB |
|---|---|---|---|---|---|---|
| `one_tower_40x30` (one large facade) | 42 | 2 856 | 0.1369 | 0 | 4 110 | 448.6 |
| `many_800rows_1call` | 800 | 17 600 | **1.7928** | 0 | 78 148 | 636.0 |
| `many_800rows_100calls` | 800 | 17 600 | 5.2907 | 0 | 79 336 | 636.0 |
| `many_800rows_1call_terrain` | 800 | 17 600 | **4.1792** | **1** | 78 148 | 971.7 |
| `many_800rows_100calls_terrain` | 800 | 17 600 | 16.6395 | **100** | 79 336 | 971.7 |

**800 short rows through ONE `place.build` call are 2.95x faster with no terrain and 3.98x faster
over one, at ONE `ray` execution against 100.** That is D115 / §11.9 rule 2, measured on the
many-short-rows fixture rather than on the one tall tower — and the tower row is in the table to
show why: it reads 0 `ray` executions and 0.14 s either way, so it could never have decided this.

`rows_wrappers_built` = **0** (row emission touches no wrapper — §11.9 rule 1). The 78 148 prim
wrappers are **§11's unattempted P7** — `clip_plane`'s cap tagging and `dress_caps` are real
per-prim loops, and 100 buildings × 4 vertices × 8 rows × 2 halves is 6 400 mitered pieces — so
that row is pinned as a LADDER with its reason, not as a floor. Nothing phase 2 added is in it.

**Suites after this cycle:** 90 phase-1 scene cases / **0 failing / 0 baseline values moved**,
13 phase-2 cases / 0 failing, **345 unit tests** OK (286 phase-1 + 59 new), `run_hda_checks.py`
0 failing, `gate_images.py` 0 failing.

**HONEST STATUS: implemented, UNVERIFIED.** Dev-loop rule 0 — no independent agent has audited
this build, so it is not "done". What is *not* built from §7.10: P2-4's payload half is only
partly exercised (`pc_axis`/`pc_yclass` round-trip through `style.write`/`read` but no scene case
drives a facade from input 3), P2-5's **aligned** Y mode (D122) is absent — every row solves its
own length, which is `free` — and `pc_extend` is honoured in the closure but not as a generator
parm; PC-G5's seven conditions are partly covered (1 via `corner_seam_m`/`corner_abut_m`, 2, 5, 6
and 7 directly; **3 is not, because `aligned` does not exist yet**, and 4 is implied by adaptive
never slicing rather than asserted as `slice_t is None`); P2-7's real clipping (sub-spline
independence, even–odd nesting, `slice`), P2-8 and P2-9 are untouched.

**Next up: cycle P2-4/P2-5** — the payload half driven from input 3 as a scene case, then the Y fit's
`aligned` mode (D122) and `pc_extend` as a parm, which together close PC-G5 conditions 3 and 4.


---

### Cycle P2-3R — the three-reviewer pass over P2-1..P2-3, reproduced then closed (2026-08-22)

**Twenty-two findings from three independent reviewers** (spec conformance, cell coverage,
architecture regression). **Every one was reproduced against the shipped build before it was
touched**, and every geometric one left a standing scene check behind. Two commits.

#### The six that were holes in a facade — cell coverage first

| Finding | Reproduced as | Now |
|---|---|---|
| `plan._unit` asked `candidates(rule, kit)` with **no cell role** | `select="sequence"` on a rule that names no modules (the `cases2d` idiom) filled `default_start` with `bay` x 14 where `select="first"` filled it with `shopfront` x 14 — and D138's yscale then stretched a 3.2 m module into the 4.0 m ground band with every check green | `candidates(rule, kit, cell_role(ctx, ...))`, the same expression `choose` already used. `corner.compose_modules` had the identical hole and the identical fix. **FS_sequence_cells** |
| `corner._corner_rule` called `rules_for("corner")` **without the row class** | `Rule("corner","first",["pier_cap"], yclass="end")` resolved `pier_cap` on `start`, `default` AND `end` rows | `rules_for("corner", ctx.get("yclass") or None)`. ⚠️ **And `plan.plan_section`'s default fill had the same bug on the `default` slot** — nobody reported it; it was found by grepping the other call sites of the reported one. **FR_rule_scoped** |
| `close_roles` treated every module NAME a rule mentions as a cell role | `role_fallbacks` had 22 entries for a 19-cell gap (`bay`, `cornice`, `shopfront`), the `bay` module carried the role `cornice`, and `by_role("cornice")` returned `bay` — D136's "inspectable by the artist" was wrong to inspect | `extra_roles` filtered to strings whose `split_role` halves are both real slots. 19 entries, `by_role("cornice")` returns nothing |
| §7.2's `marker:<id>` cells never took the lattice walk | a kit with `pc_role = marker:7`: `close_roles` had no `marker:7_start`, `resolve` returned a stand-in with `missing=True` — a **silent** stand-in, the one thing PC-G5 condition 5 asserts at 0 | marker X and Y slots are expanded across the five classes before the walk. `marker:7_start` degrades to `marker:7` and says so |
| §7.2's alias-collision rule was not implemented | `shopfront` (`default_start`) + `arcade` (`bottom`) both landed in `by_role("default_start")` and a `random` rule drew the ground floor 50/50 between two modules the artist believes are distinct cells | first module in payload order wins, the loser's claim is dropped, and the notice rides `pc_kit_warnings`. ⚠️ Only an **alias** loses — a module that authors the role literally is a legitimate pool member, which is what `pc_variant`/`random` selection by role is made of |
| **D141 — the canonical winding was the opposite sign from §7.3.3's own parenthetical** | `_signed_area_xz` is the shoelace in the (x, z) chart, whose right-handed normal is **-Y**, so a positive area there is CLOCKWISE about +Y and the code forced "reverse if negative", i.e. the opposite of "always run counter-clockwise about +Y". Consequence, which no number measured: `_frame`'s `across = cross(tangent, +Y)` pointed INTO the building, so D20's "front on +Z" would have put every window on every building facing the courtyard | the test is `> 0`. The unit test no longer checks the sign — it steps 0.01 m along `across` from every leg midpoint of the L, in all three re-authorings, and asserts that point is **outside** the footprint and the other side is inside |

#### The two identity findings, and why `structural_ids` could not see them

**D124 permuted the POINTS and left `pc_corner` in authored order.** `facade.rows_geometry` walked
the canonical point list indexing the authored flag list by position, so the same L re-authored from
its 4th vertex put the suppression on a different physical vertex: 64 `pc_elem_id`s differed and 104
of 168 elements moved. `array2d.canonical_order` is now the permutation `canonical_loop` applies, and
`facade.canonical_flags` takes the flags through it.

The reason this survived: **FJ/FK never pass `corner_flags`**, so the only committed identity check
ran on the one input where authored and canonical order coincide. **FN_flags / FO_flags_reversed /
FP_flags_rotated** are the same L with its reflex vertex suppressed, authored three ways, through
`structural_ids` — 0 ids differ, 0 moved.

#### D139 — every warning the Y solve raised was computed and thrown away

`Row.warns` was collected and `rows_geometry` wrote five row attributes and no warning, so:

* `F.build(RECT, kit, style, height=3.2)` — a band shorter than its mandatory bottom+top — dropped
  the `end` row entirely and returned `warn_counts == {}` with **no `pc_warn_*` attribute on the
  output at all**. The artist gets a building with no cornice and no notice.
* Y rules that name no modules (what §7.2's "a phase-1 kit is a valid phase-2 kit" invites) resolved
  the row's height source to §3.4's 1 m stand-in, so the ground floor built 1.0 m tall instead of
  4.0 m — and `role_fallbacks` scored `[0, 0]`, "0 silent stand-ins".

§7.3.3's **`pc_warn_row_overflow` did not exist anywhere in the code** (grep returned only the
spec line). It exists now, plus **`pc_warn_row_kit_gap`** — deliberately not `pc_warn_kit_gap`,
because that name means "this ELEMENT is a blank box" and PC-G5 condition 5 counts an unexplained
one; a real element in a wrongly-sized band is a different defect. Both ride `pc_row_warns` on the
row curve into `plan.classify`, which unions them onto every placement of that row. Measured after:
`{'pc_warn_row_overflow': 26}` and `{'pc_warn_row_kit_gap': 64}` on those two builds.

#### D142 — a storey vanished and `cell_grid` reported "0 empty"

`cell_grid` derived its row list from the OUTPUT, so a row that was solved and never built could not
read as a hole. The committed case `FM_area_taper` had lost the whole top band of its roof panel: the
Y solve returns 3 rows, `remove` is the intersection of the band's two scanlines, and at 8..9 m on
that triangle the boundary is 1.5556 m wide at the bottom and 0 at the apex — **1.6e-9 m of row
survives**. Correct for the mode; silent was not. `cell_grid` takes its row set from
`report["rows"]` now and reports `[3, 1, 0, 1]`, with the one unbuilt row named in `UNBUILT` with its
reason the way `BENT` names bend mode's unpacked pieces.

#### `preserve` bridged every concave notch

`row_spans(..., "preserve")` returned one span over the min and max of both scanlines. On a U panel
with a 4 m notch the band 4..8 came back as one span straight across it and **three whole bays were
built 2.0 m inside the hole**, `clip_inside_m` 0.3333 m against a 0.01 m tolerance. Both committed
area cases use the default `remove`, i.e. the only mode that cannot fail it. Each interval is now
widened individually to the union of the scanline intervals it overlaps — overhang your own interval,
never bridge a gap between two. **FQ_area_preserve** runs the mode, and because "may overhang" means
`clip_inside_m` is legitimately nonzero there, the sharp assertion moved to **`clip_hole_elements`**
(nothing wholly outside the boundary) with `clip_inside_m`'s ceiling declared per case.
§7.3.3's **`pc_clipped`** is stamped too (`clip_stamp`: FL 0 of 12, FM 4 of 4, FQ 6 of 9).
§7.3.1's per-module `pc_clip` policy is still **not built** — that is P2-7, with real slicing.

#### D140 — the kernel was importing the stage above it, twice

`place.py` carried `from . import array2d as _array2d` on two adjacent lines and called
`array2d.classify` on every build, 1D included. `classify` touches `Placement` and
`Kit.role_fallbacks` and nothing else, so it is **kernel work**: it lives in `plan.py` now, `place.py`
imports no phase-2 module at all, and the `hou`-free unit tests that covered it still do.

#### FH_y_corner was named for a column it never built

`FH`'s profile turned **9.46 degrees** — under the 30-degree `corner_angle_deg` default — so it
produced no `corner` row and not one `*_corner` cell, while its `pc_warn_role_fallback` expectation
was satisfied by unrelated missing modules. At 33.69 degrees it yields
`['start','default','corner','default','end']` and builds `corner_corner` and `default_corner`, i.e.
**the fifth column RailClone omits**, now in `CELLS` and `CELL_MODULES` rather than assumed.

#### D143/D144 — the one-call rule had no caller, and its headline was an artefact

**`facade.build` took ONE footprint and made ONE `place.build`.** Driving a 100-building district
through the only shipped 2D entry point measured **100 `place.build` calls, 100 `ray` executions,
300 `kit.read` calls** — exactly the column the bench labelled the loser — while
`ray_executions_per_build == 1` was asserted on `cases2d.build_many_buildings(True)`, which
hand-assembled loops and called `place.build` directly. **`facade.build_many` is the entry point
now and `build` is it with one footprint**, so the fixture and the API are one body; the tripwire
runs the shipped call.

**And the 2.95x / 3.98x was the comparand.** `build_many_buildings(False)` passed one shared `out`
through all 100 calls, and `place._stamp_bulk` must hand `setPrim*AttribValues` the whole column, so
every call re-read and re-wrote everything every earlier call had written. Measured: **5.210 s
against 2.040 s** for byte-identical output. `place.build` builds into a staging geometry when the
caller's `out` is non-empty and merges once; an empty `out` — every caller in the tree and every
committed case — takes the path it always took, so no baseline could move.

The bench terrain was also **1 089 prims**, 4.6x smaller than the cheapest surface §11.8 P5c ever
measured a `ray` rebuild on, so 99 saved executions were worth ~34 ms against a 4 s row. It is
19 881 prims now (P5c's middle rung). **The honest table:**

| row | curves | elems | seconds | `ray` | primWrap |
|---|---|---|---|---|---|
| `one_tower_40x30` | 42 | 2 856 | 0.1118 | 0 | 78 |
| `many_800rows_1call` | 800 | 17 600 | **1.4480** | 0 | 836 |
| `many_800rows_100calls` | 800 | 17 600 | 1.6440 | 0 | 4 400 |
| `many_800rows_100calls_accum` | 800 | 17 600 | 1.6732 | 0 | 4 400 |
| `many_800rows_1call_terrain` | 800 | 17 600 | **4.3387** | **1** | 836 |
| `many_800rows_100calls_terrain` | 800 | 17 600 | 4.3405 | **100** | 4 400 |

**1.14x with no terrain, 1.00x over 19 881 prims, 1.12x over 80 089.** So D115 is restated: the
one-call rule is **insurance, not a speed-up** — what it buys is that the conform cost is O(1) in the
number of rows instead of O(N), which grows with the surface exactly as P5c's per-execution numbers
say it must. The COUNT stays the assertion and the seconds are the sanity check.

#### D145 — §11's unattempted P7, landed, because phase 2 made it the biggest item in the row

cProfile of the 800-row district: `place.clip_plane` **1.557 s of 3.398 s, 46 %**, all of it the
per-prim, per-point plane test that tagged the miter cap (156 000 `hou.Prim` wrappers, 198 408
`Point.position` calls); `dress_caps` walked every prim to find the caps. **`polyfill` appends its
patches contiguously at the tail** — probed on this build against a three-hole cut, not recalled, and
`polyfill_appends_its_patches` re-probes it against the original plane test — so the tag is one bulk
write and the cap search is an int column.

⚠️ **The tag is an OR, not an assignment.** A default piece is cut at BOTH ends as soon as a leg is
shorter than twice the miter overhang, and the first cut's `pc_cap` rides through the second `clip`
on the verb's own attribute promotion. Overwriting the column took `AI_triangle`'s
`corner_face_mate_m` from 1.29e-07 to **0.035248 m** — caught by the committed check, which is what
it is for.

| | before | after |
|---|---|---|
| `prims_wrappers_built_mitered` (phase 1) | 571 (ceiling 600) | **11** (ceiling 200) |
| `prims_wrappers_built_2d_rows` | 78 132 (ceiling 80 000) | **836** (ceiling 5 000) |
| 800-row district, no terrain | 1.7989 s | **1.4480 s** |

Output bit-identical on all 109 cases.

#### D146 — two tripwires the existing four could not reach

* **`wrapper_reads`** — reads THROUGH a wrapper (`hou.Prim.points` by length, `Point.position`,
  `Point.attribValue`, `Prim.attribValue`). That class is neither a wrapper *materialised* through
  `hou.Geometry`/`hou.PointGroup` nor a wrapper *write*, so `points_wrappers_built_2d_rows` read
  **0 against a ceiling of 8** on a build doing **443 136** of them. §11.9 rule 1's instruction
  *"if a phase-2 row is slow, COUNT WRAPPERS"* was literally unanswerable. Reads 65 816 now (the
  remainder is `dress_caps`' vertex loop — HOM has no bulk vertex-to-point map; probed).
* **`verb_executions_per_build`** — `clip`/`polyfill` pinned per verb NAME the way
  `ray_executions_per_build` pins `ray`. 12 800 executions on the district against the 100 `ray`
  calls the port cycle went to war over, and a fourth verb name appearing is §11.9's "three verbs"
  quietly becoming four.
* `prims_wrappers_built_2d_rows` sat at 78 148 under a ceiling of 80 000 — 2.4 % headroom, a false
  alarm on a one-storey fixture change and blind to a 2 % regression. Both wrapper ceilings are
  class boundaries now.

#### Decisions taken

| # | Decision |
|---|---|
| D139 | **A warning the Y solve raises is the ROW's, and it is carried onto every element of that row.** §7.3.3's `pc_warn_row_overflow` is implemented (D13's cascade on the Y axis: a mandatory cap the Y style asked for that the solve could not place, plus the Y solve's own overflow), and `pc_warn_row_kit_gap` joins it for the other Y failure — the module that was to give the row its nominal height was missing. Deliberately NOT `pc_warn_kit_gap`: that name means "this element is a blank box" and PC-G5 condition 5 counts an unexplained one. Both ride `pc_row_warns` on the row curve into `plan.classify`, which unions them the way it already unions `WARN_ROLE_FALLBACK` |
| D140 | **`classify` belongs to `plan.py`, not to `array2d.py`.** §7 says phase 2 is a stage ABOVE the kernel; `place.build` importing `array2d` pointed the arrow the wrong way and made the kernel untestable without the 2D stage. `classify` touches `Placement` and `Kit.role_fallbacks` and nothing else, so it is kernel work the 2D stage merely feeds. `place.py` now imports no phase-2 module |
| D141 | **The canonical winding reverses when the (x, z) shoelace is POSITIVE, and the assertion is the OUTWARD FACING, not the sign.** That chart's right-handed normal is -Y, so a positive number there is clockwise about +Y — the opposite of §7.3.3/D124's own parenthetical. The consequence no number measured: `_frame`'s `across = cross(tangent, +Y)` pointed into the building, so D20's "front on +Z" would face every window at the courtyard. The unit test steps along `across` from every leg midpoint and asserts the point is outside the footprint |
| D142 | **`cell_grid` takes its row set from the SOLVE, not from the output.** A row that was solved and never built cannot read as a hole otherwise, and `FM_area_taper` lost the whole top band of its roof panel at "2 rows x 1 faces, 0 empty". A row the clip legitimately empties is named per case with its reason (`UNBUILT`), the way `BENT` names bend mode's unpacked pieces |
| D143 | **`facade.build_many` is the 2D entry point, and `facade.build` is it with one footprint.** D115's one-call property was unreachable from the shipped API — the only public entry took one footprint and therefore one `place.build`, so a district cost 100 builds, 100 `ray` executions and 300 kit reads, while `ray_executions_per_build == 1` was asserted on a bench fixture that bypassed the adapter. One body, so the fixture and the API cannot diverge |
| D144 | ⚠️ **A CORRECTION TO D115's HEADLINE. The 2.95x / 3.98x was the comparand's own O(n^2), not the batch.** The many-call half shared one `out`, and `_stamp_bulk` must write the whole prim column, so every call re-wrote every earlier call's prims (5.210 s against 2.040 s for byte-identical output). `place.build` stages into a fresh geometry when `out` is non-empty and merges once. Re-measured fairly and over a terrain big enough to test the thing (19 881 prims, not 1 089): **1.14x with no terrain, 1.00x over 19 881, 1.12x over 80 089, at 1 `ray` execution against 100**. The one-call rule is insurance — conform cost O(1) in rows instead of O(N) — and the COUNT, not the ratio, is what PC-G7 asserts |
| D145 | **§11's P7 is done, and `polyfill` appending its patches at the tail is what buys it.** `clip_plane`'s cap tag was a per-prim, per-point plane test through wrappers — 46 % of the 800-row district — and `dress_caps` walked every prim to find the caps. Probed, not recalled: `polyfill` appends the primitives it creates contiguously after the ones it was given, so the caps are the tail and the tag is one bulk write; `polyfill_appends_its_patches` is the standing re-probe. ⚠️ It is an **OR**, because a piece cut at both ends carries the first cut's flag through the second `clip`. 571 to 11 wrappers on the phase-1 miter fixture, 78 148 to 836 on the district, output bit-identical |
| D146 | **A wrapper READ is a defect class the four existing tripwires cannot see.** They count wrappers materialised through `hou.Geometry`/`hou.PointGroup` and wrapper writes; a read through `hou.Prim` is neither, so `points_wrappers_built_2d_rows` read 0 against a ceiling of 8 on a build doing 443 136 of them. `wrapper_reads` is that counter and `verb_executions_per_build` is the same idea for compiled SOP executions (`clip`/`polyfill`, per verb name). Both wrapper ceilings are class boundaries, not values plus 2 % |

#### Cycle P2-3R — final state

**Phase 1 untouched and green:** 90 scene cases, `run_hda_checks.py`, `scale_gate.py` (9 rows),
`gate_images.py`, 346 unit tests (P2-3R wrote 386; corrected by P2-3V) — 0 failing. **One phase-1 baseline value moved and it is P7:**
`prims_wrappers_built_mitered` 571 to 11.

**Phase 2:** 19 cases (13 + FN/FO/FP/FQ/FR/FS), 0 failing. Baseline movement, all explained above:
`geometry_digest` on every closed-footprint case (D141's winding), `cell_grid` gaining a fourth
number, `FH_y_corner`'s inventory gaining the column it never built, and
`prims_wrappers_built_2d_rows` 78 148 to 836 (P2-3R wrote 78 132; the baseline says 78 148).

**Judged on the image** (`facade_images.py`, rasteriser extended not rebuilt): the reflex corner
reads ground-to-cornice with the corner column continuous and the cornice band turning round it, and
the L closes at every storey — the failure no number catches.

**HONEST STATUS: implemented, UNVERIFIED.** Dev-loop rule 0 — this cycle's fixes have not themselves
been independently audited. What is still not built from §7.10 is unchanged: P2-5's **aligned** Y mode
(D122) and `pc_extend` as a parm, PC-G5 conditions 3 and 4, P2-7's real clipping (per-module `pc_clip`,
sub-spline independence, even-odd nesting, `slice`), P2-8 and P2-9.

**Next up: cycle P2-4/P2-5** — unchanged.

---

### Cycle P2-3V — independent verification of P2-3R (2026-08-22)

**Dev-loop rule 0, discharged.** A fresh agent that wrote none of P2-3R ran every suite from
clean, re-derived the baseline movement key by key, mutation-tested phase 2, and judged PC-G5
on images. **All 22 of P2-3R's reported fixes are real and present in the shipped build** — every
one of them was reproduced here by reverting it and watching something go red, *except six, which
went red nowhere at all.* Those six are the finding of this cycle.

#### 1. Suites, from clean

| Suite | Result |
|---|---|
| Unit tests | **346 OK** (61 + 60 + 63 + 91 + 49 + 22), 0 failing |
| `run_scene_checks.py` (phase 1) | **90 cases / 5 559 check rows / 0 failing**, and **no baseline movement** |
| `run_2d_checks.py` (phase 2) | **19 cases / 571 rows / 0 failing**, no baseline movement |
| `run_hda_checks.py` | 0 failing |
| `scale_gate.py` | 9 rows, 0 failing |
| `gate_images.py` | 0 failing gate checks |
| `facade_bench.py` | reproduced: **1 `ray` vs 100**, 836 vs 4 400 prim wrappers, **1.08x / 1.00x** — D144's "insurance, not a speed-up" reading is honest |

`git diff 4f1b0c2..a4a2488` touches no citygen file. The phase-1 baseline diff is exactly P7 plus
four added tripwires, as claimed.

⚠️ **Two numbers in P2-3R's write-up are wrong, and both are the write-up's and not the build's.**
**The suite is 346 unit tests, not 386** (P2-1..P2-3 counted 345; D141 added one). And
`prims_wrappers_built_2d_rows` went **78 148 → 836**, not 78 132 — 78 148 is the value in the
committed baseline, and §0.0 already had it right.

⚠️ **One baseline movement went unreported: `FC_rect/corner_seam_m` 0.0 → 1e-06.** It is D141's
doing (reverting the winding sign puts it back to exactly 0.0), it is 1 micron against a 2e-3
tolerance, and it is the reversed traversal order accumulating differently. Not a defect —
but "movement: `geometry_digest`, `cell_grid`, `FH_y_corner`, `prims_wrappers_built_2d_rows`" was
not the whole list, and the whole list is the point of reading a baseline diff.

#### 2. Mutation test — 17 mutations, and **SIX SURVIVED**

Every mutation was applied to the shipped source, run against the full phase-2 suite **and** the
unit tests, then reverted by file copy — never a tree-wide git command, per §11.2's own warning.
The tree was verified byte-clean afterwards.

**Caught, as they should be** — the eleven that prove the suite is not decorative:

| Mutation | Caught by |
|---|---|
| a cell role deleted from the kit at close time | `cell_modules`, `fallback_map`, `warnings` — 12 red + 2 unit |
| the 2D cell address assembled `y_x` instead of `x_y` | 9 red + 1 unit |
| **7.2.2's "Y sheds first" inverted** | `cell_modules`, `fallback_map` — 5 red + 4 unit, **and both `extend` branches** |
| a missing role recorded no fallback (the silent stand-in) | `role_fallbacks` **[24, 360]** — PC-G5 condition 5, working |
| `preserve` bridging a concave notch again | `clip_inside_m` 2.0 m + `clip_hole_elements` 3 |
| `canonical_flags` reverted to the identity | `structural_ids` — 32/64 ids differ, 104 moved |
| a row silently dropped from the curve stream | 37 red, `cell_grid` leading |
| `_corner_rule` unscoped from the row class | `cell_modules` |
| `sequence` asking for the bare X slot | `cell_modules` |
| an inert per-prim wrapper loop in the 2D clip path | `prims_wrappers_built_2d_rows` **39 484** and `wrapper_reads_2d_rows` **221 608** — *the tripwires do catch a wrapper loop that changes no output* |
| `build_many` looping per footprint | `ray_executions_per_build_2d_rows` 1 → 2 |
| D145's cap tag at the wrong end / as an assignment | 60 red / `corner_face_mate_m` on `AI_triangle` 1.29e-07 → 0.0352 — exactly the trap P2-3R named |
| the winding sign reverted (D141) | 2 unit tests. **Nothing in the scene suite** — the digest moves, and that is all |

**THE SIX SURVIVORS.** Each is a P2-3R fix whose "final actual output" was measured by hand in the
fix pass and **never committed**, so the whole fix could be deleted and 19 cases, 5 400 rows and
346 unit tests stayed green. This is dev-loop's compounding rule not being applied, and it is the
same shape every previous verification cycle found.

| # | The fix that had no assertion | The mutation that survived |
|---|---|---|
| S1 | **D139's row warnings** — `WARN_ROW_OVERFLOW` / `WARN_ROW_KIT_GAP` | `extra = ()` in `plan.classify`. **Neither string appeared in a single test file, `EXPECTED_WARNS` entry, unit test or run log.** The channel that stops a truncated building shipping silent was itself silent |
| S2 | **`clip_stamp` could not fail on an area build** — `ok = area or n == 0`, so on the only builds where `pc_clipped` can legitimately be 1 the check was `True` unconditionally | `p.clipped = 0` for every placement: **0 failing checks**, two baseline lines. P2-3R's "`pc_clipped` is now stamped **and asserted**" was half true |
| S3 | **the alias-collision drop** (finding 8) | re-pooling colliding aliases — green everywhere |
| S4 | **`marker:<id>`'s five Y classes** (finding 5) | deleting the expansion — green everywhere. This is *precisely* the silent stand-in PC-G5 condition 5 counts at 0 |
| S5 | **`extra_roles` filtered to real slot pairs** (finding 15/19) | letting module names become cell roles — green everywhere |
| S6 | **`rows_unbuilt` + `pc_warn_row_clipped_out` were DEAD CODE** | zero references in the suite, zero occurrences in any run. `FM_area_taper` is *not* what exercises them: its top band leaves 1.6e-9 m, which is still a span, so `area_rows` records nothing and `cell_grid` catches the hole by its own solved-vs-built difference. D142's artist-facing channel had never once fired |

#### 3. The six, closed — D147

| ID | Decision |
|---|---|
| D147 | **A warning with no case is a warning that can be deleted by accident.** Three cases and one check now stand behind the four channels that had none. **`FT_row_overflow`** — 3.2 m of height cannot hold a 4.0 m ground floor *and* a 1.0 m cornice, so D13's cascade drops the mandatory `end`: `pc_warn_row_overflow` x 26, and `CELLS` asserts the whole `end` column is gone so the warning cannot be a lie. **`FU_row_kit_gap`** — the Y style names a module the kit has not got: `pc_warn_row_kit_gap` x 26, and its `geometry_digest` is `FC_rect`'s, i.e. the *only* difference is the warning. **`FV_area_short`** — a 13 m stack over a 9 m plate, the only case in which `rows_unbuilt` is non-empty, with the new **`rows_clipped_out`** check asserting that the count and the `pc_warn_row_clipped_out` lines agree. **`clip_stamp` now asserts the TRANSFER** — the row curve's `pc_clipped` against every element of that row — instead of returning `True` for every area build. And four `hou`-free unit tests cover S3/S4/S5. **All six mutations now go red.** |

**Baseline: additions only.** 22 phase-2 cases / 683 rows; the three new cases and the new
`rows_clipped_out` row on all nineteen old ones are added, and **not one previously recorded value
moved.** Phase 1 untouched. 350 unit tests.

#### 4. GATE PC-G5 — judged, and it does NOT pass

Judged on images regenerated from *this* build with the committed rasteriser
(`facade_images.py`), plus four extra views rendered in the scratchpad that the committed set does
not cover: the **bend-mode** corner, the **plan**, and both a convex and the reflex corner cropped
tighter. §7.8's fixture names both corner modes and only miter had an image.

**What I actually see.** The plan view of the miter L is a closed ring of cells with **no holes and
no overlaps** anywhere on the boundary; all five convex vertices *and* the reflex vertex carry a
corner piece with a visible 45° bisector cut. In the reflex close-up the corner column runs
**unbroken from the ground band to the cornice**, red (`corner_start`) → orange (`corner`) →
yellow (`corner_end`), and the cornice band turns round it with its outer edge continuous through
the apex — the failure §7.8 says no number catches (*"a corner that closes numerically while the
cornice returns the wrong way round it"*) **is not present**. The convex corner at (0,0) reads the
same. Every band boundary closes at the apex at the same height on both legs. In **bend** mode
there is correctly **no corner post at all** and the bands turn through the elbow as continuous
surfaces. The front elevation shows four bands whose boundaries are straight, continuous lines
across the whole width. `FE_stand_in` renders almost entirely red, which is right: that kit has
only a column, and warn-never-block fills the rest with §3.4 boxes that say so.

⚠️ One honest limitation of the picture, not of the build: the "front" elevation is an orthographic
projection of a *closed* footprint, so all six legs superimpose. It reads the BANDS correctly and
it cannot read §7.8's "role table visible as a pattern". A per-leg elevation is what that line
actually wants.

**Condition by condition, and two of them are not there:**

| # | Condition | Verdict |
|---|---|---|
| 1 | corner closure per storey, 6 x 4 = 24 joints | ✅ **PASS, and verified non-vacuous**: `_corner_caps` yields **24 groups, 24 of them paired and measured** — probed directly, not read off the label. `corner_seam_m` **0.0**, `corner_abut_m` 1e-06, `corner_breach_m` 0.0 on FA |
| 2 | row closure | ✅ **PASS** — `row_closure_m` 0.0, `row_fill_y_m` 0.0 on FA and FB |
| 3 | bay alignment under `y_mode = aligned` | ❌ **NOT PRESENT.** `aligned` does not exist (D122, unbuilt), so every row solves `free`. And the inverted `free` form §7.8 offers cannot be run either: every row of the L uses the same kit over the same leg lengths, so the fixture cannot distinguish the two modes even in principle. **This condition needs a fixture as well as a mode** |
| 4 | no sliced windows, `slice_t is None` on 100 % | ⚠️ **TRUE BUT UNASSERTED.** Measured here: **0 of 176 placements** on FA carry a `slice_t`. No committed check says so; nothing would notice if it changed |
| 5 | no silent stand-ins | ✅ **PASS** — `role_fallbacks` [0, 0] on FA, and mutation-proved: making a missing role fail silently reports **[24, 360]**. The `marker:` half of it had no assertion until D147 |
| 6 | identity is structural | ✅ **PASS** — `structural_ids` 0 on FJ/FK and on FN/FO/FP *with flags*; reverting `canonical_flags` reports 64 ids differ / 104 moved |
| 7 | instancing survives 2D | ✅ **PASS** — `row_scale_packed` [88, 24, 0] miter and [64, 0, 12] bend, `pc_row_scale != 1` unpacking nothing |

**PC-G5 VERDICT: DOES NOT PASS.** Five of seven conditions pass and are mutation-proved; condition
**4** is factually satisfied on the fixture but has no check; condition **3** has neither a mode nor
a fixture that can exercise it. The picture is clean and the corner closure is real — the gate is
short two conditions, not short a facade.

#### 5. What phase 2 still owes

Unchanged from P2-3R except that S1–S6 are closed and PC-G5 now has a measured verdict rather than
a claim:

1. **P2-5 — the `aligned` Y mode (D122) and `pc_extend` as a parm.** Closes PC-G5 condition 3, and
   it needs a **fixture with unequal leg lengths or a per-row kit**, or `aligned` and `free` remain
   indistinguishable however the mode is implemented.
2. **PC-G5 condition 4** — one line: assert `slice_t is None` on every non-clip placement. It is
   true today; nothing is watching it.
3. **P2-4 — the payload half from input 3.**
4. **P2-7 — the real clipping**: per-module `pc_clip` (§7.3.1), sub-spline independence, even–odd
   nesting, and `slice`. `pc_clipped` is D137's span flag and nothing more; PC-G6 is unbuilt.
5. **P2-8, P2-9**, and §7.7's kit slicer `pf_polychain_slice`.
6. **Phase 1's own unchanged debts**: the GUI viewport pass on PC-G1/PC-G2 (bridge still wedged),
   the streets acceptance, and standing finding (11).

**The next cycle should build P2-4 then P2-5**, and should write PC-G5 condition 4's one-line check
on the way past, because it is free and it is currently the cheapest untested truth in the tool.

---

### Cycle P2-OCL — OpenCL benchmarked, then audited, then declined (2026-08-22)

**Measurement-only cycle. No production file and no HDA was touched.** Hannes' question was
*"which processes could use OpenCL, and check whether it is actually faster"*. Three candidates
were implemented three ways each (Python / VEX-64 / OpenCL, verb **and** node) and measured on both
of polyChain's real workload shapes; a second pass then audited that benchmark and re-ran every
headline comparison. **The measurement is [§14](#14-opencl-benchmarked--three-candidates-three-implementations-each-both-shapes);
the audited verdict and the corrections are
[§14.10](#1410-the-audit-of-14--what-survived-what-had-to-be-corrected-and-the-verdict).**

**The answer is no, everywhere, and it is measured rather than assumed.** The deform point
transform loses to VEX at every size on both shapes up to 2×10⁷ points (360 000 pts: VEX 0.00122 s
vs OpenCL 0.00242 s). The deform gate is the one place OpenCL wins — by 163–215 µs on one big
execution — and the same candidate is a **6.1× loss** on `streets_300`, the shape citygen actually
produces, against a ~0.1 s first-cook compile and a ~120 MiB VRAM floor. Everything else is either
a sequential prefix solve, small-N branching, zero-arithmetic attribute writes, or already inside a
native verb.

**Decisions: D158** (OpenCL declined, audited; the reopen criterion becomes four conditions, and
§13's native rebuild carries no OpenCL node), **D159** (64-bit mandatory, justified by baseline
movement — fp64 reproduces the shipped answer exactly, fp32 moves it 5.4e-04 m at 20 km — and
§14.0's `marker_offset_m` framing withdrawn), **D160** (§14.4's "`attribvop` is single-threaded
below ~5 000 elements" downgraded to an unexplained anomaly; `vex_threadjobsize` is not its cause).

**What the study actually points at, and it is not a language:** one execution per build instead of
one per piece is worth **55×** to VEX and **407×** to OpenCL, and skipping it makes an OpenCL port
**6.6× slower than the Python it replaces**. Then Python → VEX-64 on the gate, 84×. Then stop.


## 13. Native network architecture — the rebuild brief

**Status:** written 2026-08-22. **No production code in this cycle.** Every mechanism below was
probed live in headless `hython` on Houdini 22.0.398 before it was written down; §13.2 is the
evidence and it carries the numbers. Nothing here is implemented.

⚠️ **Numbering.** The brief that commissioned this asked for "§12 Native network architecture".
**§12 was already taken** by the phase-2 build log (written earlier the same day), so this is
**§13**. There is exactly one section per number; do not renumber §12.

### 13.0 Why this section exists

Phase 1 works. 350 unit tests, 90 + 22 scene cases, 5 559 + 683 baselined values, four gates
green, 12.3x on the citygen corner-heavy row. **And it was built the wrong way.** Hannes opened
`pf_polychain` and found two nodes:

```
pf_polychain
  |- kernel   [python]      <- ~6 000 lines; the ENTIRE tool
  |- OUT      [null]
```

Sectioning, the fitting solve, placement, deformation, conform, mitring, capping and stamping all
run inside ONE Python SOP. §11's port made that Python faster and reached three compiled SOPs
through `nodeVerb`; it deliberately kept the builder **node-free** (§11.9). That decision is now
reversed, because it violated the project's own law — [`artist_ui.md`](artist_ui.md) §6 rule 10,
*"the graph stays reachable — unlocked HDAs, macros as the middle tier"*, and §1c's finding that
artists learn a tool by opening it and toggling nodes off to see what each one does. A tool whose
entire body is one Python SOP cannot be learned that way, and it cannot be steered by anyone who
did not write it.

**Hannes' rule, verbatim:** *"everything geometry related should be either native nodes, vex or
opencl. Python can be used for ui or processing data which is not possible to process with the
other 3 mentioned options."*

So the fitting solve is geometry and goes to VEX. Python survives only where it is named and
justified below, and the burden of proof is on **keeping** Python, not on removing it.

**What does not change.** [§3](#3-data-contracts)'s data contracts, [§5](#5-parameter-surface-artist-face)'s
parm face, the four gates, and the 6 242 baselined values. The Python at
`polyfactory/scripts/python/polyfactory/polychain/` becomes the **reference implementation** and
stays runnable with its unit tests — it is how the rewrite proves itself.

---

### 13.1 The shape of the answer, in one paragraph

Every stage of [§4](#4-the-kernel--phase-1-algorithms) becomes a named, visible, displayable run
of wrangles and native SOPs inside the HDA. The fitting solve is a **two-pass VEX pattern**: a
point wrangle run over *section* points does each section's sequential accumulation inside one
thread and writes the result as **per-section arrays**; a `pointgenerate` expands each section to
exactly its piece count; a second point wrangle reads element *k* of those arrays. That pattern is
deterministic (probed), needs no `addpoint`, and keeps the solve's sequential nature without
serialising the whole graph. Placement is **one `copytopoints`** that picks each piece's kit module
by a string attribute and honours a per-point 3x3 `transform` (probed). The packed branch writes
the packed `transform` intrinsic from VEX; the deformed branch is one 64-bit point wrangle over
~360 000 points. Conform is the **`ray` node** reading its `dist` output, once per build. Python
keeps the parm face, the payload adapter, the kit-authoring helpers, the HDA build script, the
reference implementation and the test harness — and one named piece of 64-bit integer arithmetic
VEX has no type for.

---

### 13.2 What was probed, and what it measured

Everything in this table was run in headless `hython` on 22.0.398 this cycle. Scripts are
throwaway; the numbers are why each decision below is a decision and not a guess.

| Probe | Result | Consequence |
|---|---|---|
| `nodeVerb` inventory | `pathdeform`, `bend`, `copytocurves`, `chain`, `attribwrangle`, `attribdelete`, `polycap`, `polypath`, `block_begin/end`, `python`, `subnet`, `solver` all return **None**; `attribvop`, `ray`, `clip`, `polyfill`, `copytopoints`, `resample`, `polyframe`, `measure`, `boolean::2.0`, `polybevel::3.0`, `polysplit::2.0`, `sweep::2.0`, `polyexpand2d`, `carve`, `invoke`, `switch`, `null`, `merge`, `pack`, `sort`, `divide`, `connectivity` return real verbs | **In a network the verb list stops mattering.** `attribwrangle` and `polycap` — both verbless — become first-class. That is the unlock §11.9 could not have. |
| `attribwrangle` node | 4 inputs; `class` menu `detail/primitive/point/vertex/number`; `vex_precision` menu `auto/32/64` | One wrangle can read spline + kit + style + surface at once. No VOP network needed, unlike the `attribvop` verb §11.0 had to use. |
| 64-bit through a node | `vex_precision=64`: `L-(L-4.883e-4)` at L=20 000 returns **4.883000000e-04**; at 32 it returns 4.882999929e-04 | §11.0(b)'s 64-bit finding holds for nodes, not just verbs. |
| **float attribute storage under 64-bit VEX** | `f@big = 20000.0 + 4.883e-4` under `vex_precision=64` reads back **20000.000488300000, error 0.0** — Houdini stored a **float64** attribute | **This is the load-bearing one.** A 64-bit pipeline can carry 64-bit values *between* nodes. Intermediates do not have to be rounded to float32 at every node boundary. |
| packed prim position at 20 km | a point at x = 20000.0004883 stores as **20000.0** (float32 `P`) | The world-scale floor is real and unchanged: it is where the *reference* already lives too (§11.9 rule 3). Only `P` and packed transforms are forced float32; everything upstream can stay 64-bit. |
| VEX integer width | `long x = 5;` → *"Invalid declaration type for variable x: long"*. `>>>` → parse error | **VEX has no int64 and no unsigned shift.** `_splitmix`'s 64-bit mixing has no direct expression. This is risk R1 and the one honest Python candidate outside the parm face. |
| VEX strings | `strlen`, `split(s,"")`, `ord`, `atoi`, `sprintf`, `random_shash` all compile | `elem_key`'s crc32 **is** expressible in VEX. `elem_id` is `sprintf` — see next row. |
| `elem_id` parity | `sprintf("%s\|%d\|%s\|%d\|%s", …)` reproduced Python's `elem_id()` **exactly** on every tested tuple | §3.4's structural address ports with no format risk. |
| VEX containers | `dict`, `s[]@`, `f[]@`, `resize`, `append`, `while`, user functions all compile | §3.3's payload dicts, the rule table and the per-section arrays all have a VEX expression. |
| **the fitting-solve prototype** | a point wrangle over 4 section points ran an adaptive fill with reserved start/end, wrote `f[]@pc_starts / f[]@pc_ends / s[]@pc_slots / f[]@pc_scales / i@pc_npieces`, `pc_fill_err` = 0.0 on every section | The solve fits the two-pass pattern. §13.3.2. |
| `pointgenerate` | `ptsperpt=1, nptsperpt=1, doattrib=pc_npieces` gives **exactly** `pc_npieces` points per input point (⚠️ the attribute **multiplies** `nptsperpt`, so `nptsperpt` must be 1); `dopointnum`/`dopointidx` stamp source point and index-within-source; `docopyattribs` carries the arrays through. **10 000 sections → 19 999 pieces in 0.0002 s** | The deterministic expander. No `addpoint`, so no thread-order dependence. |
| expansion determinism | 3 forced cooks of solve → expand → read: **identical digest** | The pattern is safe for `determinism` and `geometry_digest`. |
| cumulative arclength | prim wrangle scanning `primpoints` and writing `pc_s` per point: **0.0032 s (32-bit) / 0.0037 s (64-bit)** on a 20 001-vertex 20 km line; last `pc_s` = 20000.000000000 | Against `decompose._clean`'s recorded 0.030 s (§11.1). Parallel across curves, sequential within — the right decomposition. |
| the deform kernel | a representative frame-rebuild point wrangle over **360 000 points**: **0.00055 s (32-bit) / 0.00071 s (64-bit)**, best of 6, dirtied through the node's own spare parm and `cookCount` confirmed | Against the shipped deformed row's 1.5 s. ⚠️ This is a node-only micro-bench, not a build; the real number must come from `scale_gate.py`. |
| `copytopoints::2.0` | `useidattrib` with a **string** `pc_module` attribute picks the right packed kit module per point; a per-point **`transform` 3x3** attribute is honoured (rotation present with it, absent without it); 10 000 pieces at ~1e-4 s packed and unpacked | §4.4's materialisation is one node, and the frame VEX writes straight into it. |
| packed transform from VEX | `setprimintrinsic(0,"transform",@primnum,m)` with a typed `matrix3` writes the packed prim's transform; rotation confirmed on the `bounds` intrinsic. ⚠️ the uniform-scale component did **not** show up in `bounds` and must be re-checked against `packedfulltransform` | Risk R8. The mechanism exists; the scale semantics are unverified. |
| `ray` node | with `dotrans=0, putdist=1, newgrp=1` it leaves `P` untouched and writes a **`dist` point attribute** plus a `rayHitGroup`; 10 000 packed pieces against a 200x200 grid in **0.005 s** | D111's "read the DISTANCE, not the position" is available at node level, and §11.9 rule 2's per-call rebuild cost **structurally disappears**: a node cooks once per build, so there is no batch to hoist. |
| `polycap` | verbless, so unreachable before; as a node it caps a tube in one cook | Slice caps get a proper node beside `polyfill`. |
| `attribcast` | exists, with per-attribute `precision` and `typeinfo` casts | The explicit lever for pinning an intermediate to 64-bit or dropping it to 32-bit at a named place. |
| readability API | `createNetworkBox` + `setComment` + `setGenericFlag(DisplayComment)` + `setColor` + `createStickyNote` all work headless | §13.7's layout is scriptable from the HDA builder. |
| OpenCL SOP | present (`opencl`); the kernel compiled and cooked with no errors — **but `cookCount` incremented once across six timed passes, so the timing is NOT a measurement** | §13.5. OpenCL is declined again, and this time the reason is recorded as *unmeasured*, not as *slower*. |
| `chain` SOP | 10 m line, a box 0.2 m along its Z: **50 pieces filling 0.000..10.000**; `Explicit Number = 7` gives 7 pieces over 1.4 m and does **not** stretch to fill | Real fill behaviour, and real limits. §13.4. |
| `copytocurves` | 3 curves of 15 points total produced **15 copies** — one **per curve point**, rigid, source **Z** axis to the tangent. It does not stretch a piece across a curve | It is `copytopoints` with curve frames. Not a deformer. §13.4. |
| `pathdeform` | `usepiece`/`pieceattrib` matches a piece of geometry to a **curve**; `curve_posoffsetattrib` / `curve_posendattrib` are read as **primitive attributes on the curves**, one value per curve | It can place-and-deform per piece — but only if every piece gets its own curve. §13.4. |

---

### 13.3 Stage by stage

Read this against [§4](#4-the-kernel--phase-1-algorithms). Each heading names the mechanism, then
says what the candidate nodes cannot do.

#### 13.3.0 Stage 0 — `config` (new, and it is the only Python SOP left in the cook path)

**Mechanism: one Python SOP.** It evaluates the 39-parm page ([§5](#5-parameter-surface-artist-face)),
reads the style payload from input 3 through `style.py`, resolves the two-face precedence
(payload beats parms, §2.1), and writes the result as **detail dictionaries** on a single point:
`pc_cfg` (the resolved parameters), `pc_rules` (§3.3's ordered rule list, as a `dict[]`), and
`pc_kitmeta`. Nothing downstream reads a parm directly except through `chf()`/`chs()` where a
scalar is genuinely a scalar.

**Why Python is right here and nowhere else.** This is parameter and payload marshalling — the
exact case Hannes' rule reserves. It touches no geometry, its N is the parm count, and its output
is a dict VEX reads natively (probed). It is also what makes the rest of the graph *generic*: no
wrangle downstream contains a style name, which is what PC-G4 audits.

**Warning:** this SOP must never grow a geometry loop. The four standing wrapper tripwires
(§11.9 rule 1) stay pointed at it.

#### 13.3.1 §4.1 Decompose — **native + VEX, no Python**

| Step | Mechanism | Notes |
|---|---|---|
| cumulative arclength | `pc_arclength` — **primitive wrangle, `vex_precision=64`** | Scans `primpoints()` per curve, writes `pc_s` per point and `pc_seclen` per prim. Parallel across curves, sequential within one. **0.0037 s at 20 001 verts** vs the reference's 0.030 s. 64-bit is mandatory: this is the 20 km expression §11.0 measured returning 0 at 32 bits. |
| corner resolution | `pc_corners` — **point wrangle** | Turn angle from the two adjacent edges, `pc_corner` −1/0/1 honoured, `cornerAngle` from `pc_cfg`. Emits point group `pc_cornerpt` and `pc_corner_angle`. |
| markers | `pc_markers` — **point wrangle over the marker cloud** | `pc_u` **or** `pc_dist` (negative = from end) → `pc_s`, bound to its curve by `pc_curve`. Marker points are already segregated by `pc_marker = 1` (§3.1). |
| sections | `pc_sections` — **primitive wrangle emitting one point per section** | Walks each curve's corner/section-break list and `addpoint`s the section records. ⚠️ `addpoint` from a prim wrangle is thread-order dependent; the section points are **re-sorted by `(curve_id, section_index)` with a `sort` SOP** immediately after, which makes the order structural rather than cook-ordered. That sort is not optional and gets its own mutation test. |
| output | `OUT_sections` — **null** | Displayable. This is the section list §4.1 already promises. |

**What was rejected and why.** `resample` unshares points and interpolates point attributes
(dev-loop trap list), so it cannot derive arclength on a curve whose topology is contractual.
`measure` gives per-prim perimeter, not a per-vertex cumulative. `polyframe` (0.0023 s on 20 001
points) gives a frame per point but not the cumulative table or the per-side tangents at a kink —
§11.1 declined it for the same reason and the reason has not changed.

#### 13.3.2 §4.2 Plan — the fitting solve — **VEX, three nodes**

This is the hard one, and under Hannes' rule it is geometry. It ports.

**The shape: solve → expand → read.**

```
OUT_sections
   |
   +-- pc_plan_solve    [attribwrangle, run over POINTS (= sections), vex_precision 64]
   |       one section per thread; the fill accumulation is a sequential loop
   |       INSIDE that thread. Writes PER-SECTION ARRAYS, adds no points.
   |         f[]@pc_starts  f[]@pc_ends   f[]@pc_scales
   |         s[]@pc_modules s[]@pc_slots  i[]@pc_flags   i@pc_npieces
   |         f@pc_fill_err                       <- exact-fill residual, asserted 0
   |
   +-- pc_plan_expand   [pointgenerate: ptsperpt=1, nptsperpt=1, doattrib=pc_npieces,
   |                     dopointnum=pc_secpt, dopointidx=pc_index, docopyattribs=*]
   |       exactly pc_npieces points per section, in section-major/index-minor order.
   |
   +-- pc_plan_read     [attribwrangle, run over POINTS (= pieces), vex_precision 64]
   |       k = i@pc_index; reads element k of each array; resolves the world station
   |       pair; stamps pc_elem_id (sprintf), pc_slot, pc_module, pc_scale, pc_u;
   |       deletes the arrays.
   |
   +-- OUT_plan         [null]   <- §4.2's inspectable plan; Display=Plan shows THIS
```

**Why point-class and not detail-class.** A detail wrangle runs once, on one thread, and would
serialise every section in the build — 10 000 sections through one thread is the shape that made
the Python slow in the first place. Running over section points makes sections the parallel axis
while each section's accumulation stays sequential inside its own thread, which is exactly the
data dependency the solve actually has.

**Why arrays and not `addpoint`.** `addpoint` from a multithreaded wrangle produces points in
thread-completion order. `determinism` and `geometry_digest` are pinned on all 90 cases and would
become a lottery. `pointgenerate` expands deterministically — probed, 3 forced cooks, identical
digest — and index *k* is then a pure function of `(section, k)` with no ordering at all.

**The four fill modes.** All four are arithmetic on `(L, nominal, pad, adaptivePct, N)` and all
four are a `for` loop that accumulates `cur`:

- `adaptive` — `n = floor(avail/(s+pad))`, `+1` when the remainder fraction ≥ `adaptivePct`,
  then one global `scale = avail/(n*(s+pad))`. Prototyped in VEX this cycle, `pc_fill_err` 0.0.
- `scale` — `n` fixed by the nominal count, per-piece scale to close exactly.
- `count` — `N` from the parm, scale to close.
- `tile` — whole pieces plus one **sliced** remainder; the slice flag goes into `i[]@pc_flags`
  and is consumed by §13.3.3's cut, not by the plan.

**Padding** stays RailClone semantics — `pc_pad` moves the *neighbours*, never the piece — which
in the accumulation is just `cur += (s + padL + padR) * scale` with the piece's own span being
`[cur+padL, cur+padL+s*scale]`. Negative overlaps fall out for free.

**Markers, `evenly` anchors and compose rules** are reservations made **before** the fill loop, in
the same wrangle: anchored spans are appended to a sorted reservation array, and the fill runs on
each free gap between reservations. That is what the reference does; it is a loop over a
small sorted array and VEX expresses it directly.

**Selection rules (§3.3).** `pc_rules` is a `dict[]` read from `pc_cfg`. For each candidate slot
the wrangle assembles a **subject dictionary** (`sectionLength`, `splineLength`, `u`,
`cornerAngle`, `segIndex`, `markerData:<key>`, `attr:<name>`) and evaluates `pc_cond` as
`{subject, op, value}` against it. **There is no branch per style name and no branch per slot
name** — the slot string is a dict key, which is what keeps PC-G4's generic-loop audit passing by
construction. The `pc_vexpr` escape hatch becomes an actual VEX snippet parm on a dedicated
`pc_style_vexpr` wrangle that is always present and empty by default, so an artist expression
never forces the main solve to recompile.

**What genuinely does not port: `_splitmix`.** §3.3's `pc_scope` seeding runs a 64-bit
splitmix mix, and **VEX has no int64 and no unsigned shift** (probed: `long` is an invalid
declaration type). Two options, and the burden of proof says try the first:

1. **Implement splitmix64 in VEX as four 16-bit limbs.** Every partial product fits in 31 bits, so
   signed 32-bit ints suffice with explicit masking. ~25 lines, in a shared `pc_rand.h` VEX
   include, with a unit test comparing 10 000 values against `polychain.__init__._splitmix`.
   Bit-exact or it does not land. **This is the recommended path** and it is the first risk item
   in the build order.
2. **Fallback if (1) cannot be made bit-exact in one cycle:** the `config` Python SOP emits a seed
   **table** keyed by scope key. That is small-N for `generator`/`spline`/`section` scope, and
   degenerates to per-piece only for `segment` scope — which is precisely the per-element Python
   loop §11 spent five items removing. **So the fallback is not acceptable for `segment` scope**;
   if (1) fails, `segment` scope gets a VEX-expressible PRNG and its random-selection baselines
   are re-derived case by case, deliberately, with the moves listed.

**What the port costs, stated honestly.** `plan.py` runs today **with no Houdini imported** — 89
unit tests, and §11.1 called that property "worth more than the microseconds". Porting to VEX
loses it for the shipped path. **Mitigation:** `plan.py` stays as the reference, those 89 tests
keep running against it unchanged, and a new `plan_parity` scene check compares the VEX plan
against the Python plan on every case. The property does not disappear; it moves from the shipped
code to the oracle.

**What was rejected.** `chain` and `pathdeform` — see §13.4. Nothing native does exact-fill
adaptive with `pc_pad` neighbour displacement, marker reservations and compose rules.

#### 13.3.3 §4.3 Corners — **VEX for the geometry, native SOPs for the cut**

| Step | Mechanism |
|---|---|
| bisector planes, offsets, fillet radius, the narrow-angle fallback | `pc_corner_planes` — **point wrangle over corner points**. Pure per-corner maths: plane origin + normal, the ± offset, the `Reset`/`Extend`/`Symmetric` displacement policy, `pc_warn_corner_degenerate`. |
| the fillet | the path is rounded **before** the plan by inserting arc points — a **prim wrangle** on the spine, upstream of `pc_arclength`. |
| the cut itself | two candidates, **and this is the one mechanism the probe did not settle** (§13.9 R5). |
| the bend corner's welded ring (D36) | no cut at all: the plan welds the sections into one span and §13.3.4's deform wrangle follows it. `fuse` closes the ring. |
| caps | `polyfill` (as today) or **`polycap`** — verbless before, a real node now — then `pc_cap_uv`, a **vertex wrangle** for the box UV and the cap material tag. |

**The cut, candidate A — `block_begin`/`block_end` over the cut pieces with a `clip` inside.**
Faithful to the reference (`clip` + `polyfill` is what ships today). `clip` takes one plane per
cook, so the loop is unavoidable. `n_cut` is single digits across the whole suite, so N is small
— **but the per-iteration cost is unmeasured** (the probe's fixture failed to build) and §11.9
rule 2's lesson is that a per-call fixed cost is invisible until you bench many short curves.
**Bench it on `streets_300`, not on one fence.**

**The cut, candidate B — one `boolean::2.0` against a merged cutting surface.** All bisector
planes emitted as one polygon soup by a wrangle, one boolean cook for the whole build, no loop.
**Try this first**, because it removes the loop entirely; fall back to A if boolean's tolerances
move `corner_plane_dev_m`, `corner_face_mate_m` or `corner_seam_m`.

`corner.py` stays as the reference and keeps its unit tests. This stage is **last** in the build
order: it is small-N, it is where the tool's correctness lives, and its mechanism is the least
certain thing in this document.

#### 13.3.4 §4.4 Place + deform — **`copytopoints` + VEX; two visible branches**

```
OUT_plan
   |
   +-- pc_frames        [attribwrangle, POINTS, 64]  chord frame per piece:
   |                     u-along / v-across / chord length, the three z-modes
   |                     (adaptive | vertical | stepped), D98's flatten-under datum,
   |                     D99's two hybrid level bands, D87's off-spine camber term.
   |                     Writes 3x3 @transform + @P + @pscale + @pc_module.
   |
   +-- pc_deform_gate   [attribwrangle, POINTS]  D87's curvature budget ->
   |                     point group `pc_needs_deform`. One place, one rule.
   |
   +-- blast(packed) --- copy_packed   [copytopoints::2.0, pack=1, useidattrib=pc_module]
   |                       |
   |                       +- pc_pack_xform [attribwrangle, PRIMS, 64]
   |                          setprimintrinsic("transform") + P
   |
   +-- blast(deformed) - copy_deformed [copytopoints::2.0, pack=0, useidattrib=pc_module]
   |                       |
   |                       +- pc_stations [attribwrangle, POINTS, 64]  per-piece station
   |                       |                table (shared stations, P3's saving, as arrays)
   |                       +- pc_deform   [attribwrangle, POINTS, 64]  <- THE HOT NODE
   |                                        every point rebuilt from (piece, local xyz)
   |                                        through its frame. ~360 000 points.
   |
   +-- MERGE -> OUT_place [null]
```

**Why `copytopoints` and not `copytocurves`/`chain`/`pathdeform`.** Because the frame is ours.
Probed: `copytopoints` picks the kit module per point from a **string** `pc_module` attribute and
honours a per-point 3x3 `transform` — which is precisely the output `pc_frames` produces. Nothing
native expresses `vertical` (yaw-only frame with vertices Z-displaced to elevation), `stepped`
(yaw-only, constant Z, flatten-under), D98's datum or D99's bands. **The port moves that code from
Python into VEX; it does not delegate it.**

**§11.1 declined `copytopoints(pack=1)` for the packed branch** because routing the transform
through a float32 point attribute moved the result by 4.34e-07 m against a suite asserting
`marker_offset_m` at 1.788e-07 m. **That objection is now answerable and must be tested, not
assumed:** `vex_precision=64` writes a **float64** attribute (probed, error 0.0 at 20 km), so the
frame can reach `copytopoints` in 64 bits. What is *not* answerable is the packed prim's own
storage — `P` at 20 km rounds to float32 (probed) — but that is where the **reference already
lives**, so it is parity, not regression. **N4 in the build order is the experiment that settles
it**, and if it moves `geometry_digest` on any case, the packed branch keeps a VEX-written
intrinsic instead of an attribute round-trip.

**The deform is one node.** A representative 64-bit frame-rebuild wrangle over 360 000 points
measured **0.00071 s**. The shipped deformed row is 1.5 s. Do not quote that ratio as the expected
speedup — the micro-bench excludes materialisation, stamping and conform; `scale_gate.py` is the
number that counts.

#### 13.3.5 §4.5 Conform — **the `ray` node, once per build**

```
OUT_place --> ray [dotrans=0, putdist=1, newgrp=1, dirz=-1 from pc_cfg]
                |     -> `dist` point attribute + `rayHitGroup`
                +-- pc_drop [attribwrangle, POINTS, 64]
                      applies the drop along the axis, composes with the z-mode
                      (adaptive/vertical deform to the surface, stepped sits on it),
                      applies the per-module Y-tilt camber, warns on a miss.
```

**Three things this fixes at once.** (1) D111 stands: the drop is read as the **distance**, which
is one float32 rounding at the size of a drop instead of at the size of the world. (2) `ray`
rebuilds its surface input on every `execute` (§11.9 rule 2: 0.34 ms at 5 022 prims, 2.25 ms at
80 352) — as a **node** it cooks once per build, so the batching problem is not solved, it is
**structurally absent**, and `ray_executions_per_build` becomes 1 by construction. (3) the
unbounded `ConformPath._cache` (53 861 entries, ~24 MB for one 2 km curve) has nothing to cache.

**A tilted `conform_axis`** already takes the Python path today by design (D24/D34/D53). In the
network it takes a `switch`: the `ray` branch when the axis is a world axis, a VEX
`intersect()` branch otherwise. Both visible.

#### 13.3.6 §4.6 Finalize — **VEX wrangles, and one new hazard**

| Step | Mechanism |
|---|---|
| the §3.4 stamp | `pc_stamp` — **point and prim wrangles**. `pc_elem_id` via `sprintf` (probed bit-exact); `pc_elem_key`'s crc32 hand-written in VEX (`ord`/`split`/`strlen` all exist) with a parity unit test; `pc_slot`/`pc_module`/`pc_variant`/`pc_section`/`pc_u`/`pc_generated`. |
| instancing segregation | already decided upstream by `pc_deform_gate`; finalize only stamps `pc_deformed`. |
| slice caps | `polyfill` / `polycap` + `pc_cap_uv` vertex wrangle. |
| overrides, swap, replace | a **detail wrangle** builds an index `dict` from the override stream, a **point/prim wrangle** applies swap; hero replacement is a second `copytopoints` branch keyed by `pc_elem_id`, merged. |
| warnings | each detecting wrangle writes its own `pc_warn_*`; one **detail wrangle** collates the summary. |
| the starter kit | ⚠️ **becomes native.** `kit.starter_kit()` builds four boxes in Python today, and `hda._padded` loops `pt.setAttribValue` over kit points. In the network that is four `box` SOPs + `pack` + one manifest wrangle, and padding is one line of VEX. Python keeps kit *authoring* for external kits, not kit *construction* in the cook path. |

**⚠️ THE NEW HAZARD: warn-never-block is not free in a network.** Today every verb call is wrapped
so a raise degrades to the Python path. **A node that errors stops the cook.** Every native node
that can fail on degenerate input — `ray`, `clip`, `boolean`, `polyfill`, `polycap`, `polybevel` —
must sit behind a guard: a `switch` driven by an emptiness/validity test written by the wrangle
above it, with a pass-through `null` on the other branch. This is a **design requirement, not
polish**; it is the contract in §11.9 rule 7 and the whole warn-never-block house rule. It gets
its own check: a case that feeds each guarded node its degenerate input and asserts a warning
plus geometry, not an error.

---

### 13.4 The nodes that were tested and rejected — and exactly what they cannot do

**`chain`** — *the closest native node to this whole tool, and PC-G0 already found it is a factory
HDA that could be forked.* Probed: a 10 m line with a 0.2 m piece gives **50 pieces filling
0.000..10.000**; `Explicit Number = 7` places 7 and does **not** stretch to fill. It has piece
patterns, start/end caps, exact-pattern-length, fuse, and a "Deform Between Pivots" rigid mode
that is shaped like `stepped`. **What it cannot do:** `pc_pad` neighbour displacement with
negative overlaps; marker reservations at an exact arclength; §4.2's `adaptivePct` add-one-more
threshold; §3.3's conditional selection; per-section compose rules; and §4.4's three z-modes.
Adopting its fill would move every one of the 90 cases' `exact_fill_m`, `section_coverage_m` and
`max_gap_m` to *chain's* semantics rather than RailClone's. **Rejected for the fill.** §0.0
already records that PC-G0's fork decision should be retired (chain builds 12 011 652 points
where polyChain builds 10 000 packed prims); this cycle does not reopen it.

**`copytocurves`** — probed: 3 curves totalling 15 points produced **15 copies, one per curve
point**, rigid, with the source's **Z** axis aligned to the tangent. The docs confirm it: *"copies
geometry from the first input onto **points** in the second input"*. It is `copytopoints` with
curve-derived frames. **It does not stretch a piece along a span**, so it cannot materialise a
plan. **Rejected.**

**`pathdeform`** — probed: `usepiece`/`pieceattrib` matches a piece of geometry to a **curve**, and
`curve_posoffsetattrib` / `curve_posendattrib` are **primitive attributes on the curves** — one
value per curve, not per piece. So it *can* place-and-deform every piece in one node, **but only
if the plan emits one span curve per piece**. That is a real design: ~2 extra points per piece and
one node. **Rejected anyway**, for one reason: its frame model is fixed (forward axis, up vector,
capture region) and cannot express `vertical`'s Z-displacement-to-elevation, `stepped`'s constant
Z, D98's flatten-under datum or D99's bands. Adopting it for `adaptive` only would mean two
different deform mechanisms with two different rounding behaviours in one tool — and
`module_fidelity_m`, `plumb_deg`, `flat_stepped_m` and `bank_deg` are asserted on all 90 cases.
**Keep one deform, in VEX.** Revisit if a future mode is purely `adaptive`.

**`bend`** — a single-axis deformer with a capture region. No per-piece mapping, no arclength
placement. **Rejected.**

**`polyexpand2d`, `sweep::2.0`, `polybevel::3.0`** — solve problems this tool does not have
(offsetting a planar skeleton, generating from cross-sections, rounding an edge). `polyexpand2d`
additionally breaks planarity by ~2e-5 (dev-loop trap list). **Rejected.**

**`resample`** — unshares points and interpolates point attributes. The spine's topology is
contractual (§3.1). **Rejected**, as in §11.1.

**`measure` / `polyframe`** — per-prim perimeter and per-point frames respectively; neither gives
the cumulative arclength table or the per-side tangents at a kink. **Rejected**, as in §11.1.

**`boolean::2.0`** — **not** rejected; it is candidate B for the corner cut (§13.3.3).

**`polycap`** — **adopted as a candidate.** Verbless, and therefore unreachable from the old
verb-only kernel; a real node now.

---

### 13.5 OpenCL — declined again, and this time with a criterion

The only genuinely large parallel workload in phase 1 is the deformed branch's ~360 000 points,
and **VEX does a representative kernel for it in 0.00071 s at 64-bit precision** (probed). Adding
a GPU transfer and a second language to a sub-millisecond stage is cost without payoff, and every
stage above it is small-N with data-dependent branching — the shape OpenCL is worst at.

**The OpenCL probe is reported as unmeasured, not as slower.** The kernel compiled and cooked with
no errors, but `cookCount` incremented once across six timed passes, so the number it produced is
not evidence and is not quoted here.

**The criterion for reopening it, so nobody reopens it without one:** OpenCL becomes worth
measuring when a *single* deform cook exceeds **50 ms** — i.e. roughly **> 2.5e7 points**, which
phase 1 cannot reach and phase 2 (§7's N rows through the same kernel) plausibly can. The way to
be ready without paying for it now is architectural: **`pc_deform` is written as one self-contained
kernel over (piece index, local xyz, station arrays) with no VEX-only constructs in its inner
loop** — no strings, no dicts, no `prim()`/`point()` random access outside the station arrays — so
that the OpenCL SOP version is a transliteration rather than a redesign. That constraint costs
nothing today and is the whole preparation. **Decision D149.**

---

### 13.6 What stays Python — the complete list, each justified

| What | Why it survives |
|---|---|
| `config` Python SOP (new) — parm evaluation, payload read, two-face precedence, `pc_cfg`/`pc_rules` dicts | **UI/parameter marshalling** — the exact case Hannes' rule reserves. No geometry, N = the parm count, output is a dict VEX reads natively. |
| `style.py` — the §3.3 payload I/O adapter | Reading and validating an external data format, with warn-and-degrade. Not geometry. Runs once per cook. |
| `kit.py` — kit **authoring** and validation (`pf_polychain_kit`) | Authoring a file, not cooking geometry. ⚠️ **`kit.starter_kit()`'s box construction leaves Python** and becomes native `box` SOPs inside the HDA (§13.3.6). |
| `devScripts/create_pf_polychain_hda.py` — the HDA build script | Builds the network, the parm interface, the network boxes, the comments and the colours. Tooling, not a cook. It gets **larger** in this rewrite, which is correct. |
| `polychain/*.py` — the whole current kernel | **The reference implementation and the parity oracle.** Not shipped in the cook path once a stage lands, never deleted, keeps its unit tests. |
| `tests/` — the harness | Already Python and stays Python. |
| **`_splitmix`'s 64-bit mixing** — *conditionally* | VEX has **no int64 and no unsigned shift** (probed). This is the one algorithm with no direct VEX expression. §13.3.2 gives the limb implementation as the required first attempt and says exactly what happens if it fails. **This is the only entry on this list that is a concession rather than a fit.** |

Everything else in `polychain/` — `decompose`, `plan`, `corner`, `place`, `conform`, the `hda`
cook path — leaves the cook. That is roughly 5 900 of the ~6 000 lines.

---

### 13.7 The graph must be readable — the layout, specified

The HDA ships with **unlocked contents** and a network an artist can dive into and understand
without reading source. [`artist_ui.md`](artist_ui.md) §6 rule 10 and §1c are the requirement.

```
pf_polychain                          (subnet, unlocked, 4 inputs as today)
│
├── IN_SPLINE  IN_KIT  IN_STYLE  IN_SURFACE     [4 named nulls, one per input]
│
├─┤ 0 · CONFIG ├───────────────────────────────────── network box, grey
│   config                       [python]  the ONLY Python SOP in the cook path
│   starter_kit                  [box x4 -> pack -> manifest wrangle]  used when input 2 is empty
│
├─┤ 1 · DECOMPOSE  (§4.1) ├───────────────────────── network box, blue
│   pc_fillet · pc_arclength · pc_corners · pc_markers · pc_sections · sort
│   OUT_sections                 [null]
│
├─┤ 2 · PLAN  (§4.2) ├────────────────────────────── network box, green
│   pc_plan_solve · pc_plan_expand · pc_style_vexpr · pc_plan_read
│   OUT_plan                     [null]   <- Display=Plan renders this
│
├─┤ 3 · CORNERS  (§4.3) ├─────────────────────────── network box, orange
│   pc_corner_planes · (boolean | foreach+clip) · polyfill/polycap · pc_cap_uv
│   OUT_corners                  [null]
│
├─┤ 4 · PLACE + DEFORM  (§4.4) ├──────────────────── network box, red
│   pc_frames · pc_deform_gate
│   ├── copy_packed   -> pc_pack_xform
│   └── copy_deformed -> pc_stations -> pc_deform
│   merge · OUT_place            [null]
│
├─┤ 5 · CONFORM  (§4.5) ├─────────────────────────── network box, cyan
│   switch(axis) · ray · pc_drop
│   OUT_conform                  [null]
│
├─┤ 6 · FINALIZE  (§4.6) ├────────────────────────── network box, purple
│   pc_stamp · pc_overrides · hero branch · pc_warn_collate
│   OUT_finalize                 [null]
│
└── stage_switch [switch] ──> OUT [null] ──> output
```

Rules the build script enforces, and the HDA-wiring check asserts:

1. **Every stage begins and ends in a named `null`.** An artist can drop a display flag on any of
   them and see that stage's output. Nothing important happens in an unnamed node.
2. **Every stage is a network box with a title and a one-line comment** naming its §4 subsection.
   Every wrangle carries `setComment` + `DisplayComment` saying what it computes in one sentence.
3. **One new parm, on the Debug folder: `Stage`** — a menu over the `OUT_*` nulls, driving
   `stage_switch`. That is the artist-visible version of "toggle nodes off to see what each does"
   (§1c) and it costs exactly one parameter. It does **not** replace the existing `Display`
   (plan / full / proxy) parm, which is a §5 art-direction control, not a debug control.
4. **No expression may reference a node by absolute path.** Copied `foreach` blocks keeping
   absolute `blockpath`/`templatepath` is a recorded trap; every internal reference is relative.
5. **Working groups are prefixed `pc_`** and deleted before `OUT` — a group-name collision between
   two stages silently corrupts one of them (dev-loop trap list).
6. **The parm face does not change.** §5 is settled and audited; this is a rebuild of the body,
   not of the face. Exactly one parm is added (rule 3).

---

### 13.8 Parity strategy — how each stage is proven, and what tolerance is defensible

**The rule: the reference stays live in the same process, and parity is proven by asking BOTH,
not by diffing two runs** (§11.9 rule 4 — it is what makes `conform_parity` meaningful).

**Per stage, in this order:**

1. **A `*_parity` scene check per stage**, run on all 90 phase-1 cases (and later all 22 phase-2
   cases): build the stage natively and with the reference on the *same* input, compare
   element-by-element. `conform_parity` is the existing pattern; `plan_parity`, `decompose_parity`,
   `frames_parity`, `stamp_parity` (already exists) follow it.
2. **The 6 242 baselined values move only deliberately.** `run_scene_checks.py` already prints
   every moved value whether or not the check passes. **Every moved value is explained key by key
   in the build log before `--update-baseline` is run.** A blanket update is forbidden.
3. **A mutation per landed node.** The suite's existing device: revert or corrupt the new node and
   confirm something goes red. A node whose removal leaves the suite green is untested, not
   correct — this is exactly what cycle P2-3V found six times.
4. **`geometry_digest` and `determinism` are the ordering pins.** `pointgenerate` emits
   section-major / index-minor, which **is** the reference's order — but that is a claim to verify
   per case, not to assume, and it is the first thing to check when a digest moves.

**Tolerances, and why each is defensible:**

| Where | Tolerance | Why |
|---|---|---|
| the plan (`pc_starts`/`pc_ends`/`pc_scales`, `exact_fill_m`, `section_coverage_m`, `max_gap_m`) | **exact — 1e-12 relative, no absolute slack** | 64-bit VEX against 64-bit Python doing the same arithmetic in the same order. The fitting solve must not need a tolerance; if it does, the accumulation order differs and that is a defect, not float noise. |
| any intermediate that feeds another stage | **1e-12 relative** | Because `vex_precision=64` writes **float64** attributes (probed, error 0.0 at 20 km). **Design rule: no intermediate is allowed to round-trip through float32.** `attribcast` is the explicit lever where a value must be pinned. |
| final `P`, packed transforms, anything the viewport sees | **1e-6 m absolute at fixture scale (≤ 100 m); 1e-3 m at 20 km** | float32 ULP at those magnitudes. `geometry_digest` already quantises the world transform at 1e-6 m, and the **reference writes float32 too** — so this is parity, not a new floor. §11.9 rule 3 measured the same thing from the other side. |
| conform | **0.0 expected**, as today | D111: the drop is read as a distance, not a position. P5 landed at 0 moved values on 89 cases and the node path reads the same `dist`. If it is not 0, something else changed. |
| corner cut geometry (`corner_plane_dev_m`, `corner_face_mate_m`, `corner_seam_m`) | **their existing baselined tolerances**, and boolean must meet them or candidate A wins | This is the decision procedure for §13.3.3's two candidates, written down before either is built. |

**Three trials every new native call gets** (D113, §11.9 rule 6, non-negotiable): an
**irrational-slope** case, a case at **20 km**, and an **asymmetric** case. A parity check green at
exactly 0.0 on symmetric fixtures is a claim about the fixtures.

**The tripwires carry forward unchanged** — `stamp_calls_per_piece(_deformed)`,
`prims_wrappers_built(+_deformed/_mitered)`, `points_wrappers_built(+_streets)`,
`path_sample_calls_per_piece(_deformed)`, `conform_cache_per_element`,
`ray_executions_per_build`. Several of them will read **0** once their stage is native; **that
flip is the proof the stage landed**, and the expectation moves with it on the same commit
(the ladder device §11.2 already uses). Two new ones:

- **`sop_cooks_per_build`** — the node count the graph actually cooks. A network's failure mode is
  cook count, the way the Python's was wrapper count.
- **`streets_300_wall_clock`** — because §11.9 rule 2 is reborn in a new form: **a per-NODE fixed
  cost is invisible on one long fence and multiplies by 300 on the citygen shape.** Bench the
  many-short-curve fixture from N1 onward, not at the end.

---

### 13.9 Build order, and the risk list

Highest risk and highest value first, so a later cycle that runs out of road has landed the parts
that mattered. **Each item is one cycle: implement, run all suites, explain every moved value,
mutation-test, commit, then an independent audit before any completion claim** (dev-loop rule 0).

| # | Item | Why here | Risk |
|---|---|---|---|
| **N1** | **The parity rig.** A `pf_polychain_native` sibling HDA and a `*_parity` harness so both implementations cook side by side on the same input, plus `sop_cooks_per_build` and the `streets_300` bench. Nothing of the reference is touched. | Everything below is measured against this. Building it first is what makes the rest cheap. | LOW |
| **N2** | **§4.2 the fitting solve in VEX** — solve / expand / read, all four fill modes, padding, markers, `evenly`, compose rules, selection rules, and **the splitmix64 limb implementation with its bit-exactness test**. | The hardest thing, the thing Hannes' rule most obviously reclassifies, and the thing every stage below consumes. If splitmix cannot be made bit-exact, that must surface in cycle one, not cycle six. | **HIGH** |
| **N3** | **§4.1 decompose** — arclength, corners, markers, sections, the sort. | Feeds N2; small and well understood; the 64-bit arclength is already measured. | LOW |
| **N4** | **§4.4 packed branch** — `pc_frames`, `pc_deform_gate`, `copytopoints(pack=1)`, `pc_pack_xform`. **This is the experiment that settles §11.1's declined `copytopoints`**: does a 64-bit frame attribute reach the packed prim without moving `geometry_digest`? | The branch PC-G3 and every citygen street actually run. Answers an open question with a number. | **HIGH** |
| **N5** | **§4.4 deformed branch** — `pc_stations` + `pc_deform`, written under §13.5's OpenCL-portability constraint. | The largest measured win and the largest parallel workload. | MEDIUM |
| **N6** | **§4.5 conform** — `ray` as a node, `pc_drop`, the axis `switch`. | Structurally deletes §11.9 rule 2's batching problem and the 24 MB cache. Well-understood, D111 already proved the distance read. | LOW |
| **N7** | **§4.6 finalize** — stamp, crc32-in-VEX, caps, overrides, hero, warnings, **and the guard switches for warn-never-block**. | The guards are a contract, and they are cheapest to design in while the stages are still being wired. | MEDIUM |
| **N8** | **§4.3 corners** — planes in VEX, then boolean (candidate B) with foreach+clip (candidate A) as the fallback. | Last: small-N, least certain mechanism, and it is where the tool's correctness lives — it should be ported when everything around it is already proven. | **HIGH** |
| **N9** | **The HDA rebuild** — layout, network boxes, comments, colours, the `Stage` parm, unlocked contents, help. The parm face is unchanged but for one parm. | The readability deliverable. It is the *point* of the exercise, and it is cheap once the stages exist. | LOW |
| **N10** | **Decide the reference's fate** — kernel path retired from the cook, `polychain/*.py` kept as the oracle. | A decision to take with the numbers in hand, not now. | LOW |

**The risks, named:**

- **R1 — no int64 in VEX.** Probed. `_splitmix` has no direct expression; the limb implementation
  is unproven. Blocks every `random`-selection baseline. **N2, first thing.**
- **R2 — float32 at world scale.** A packed point at 20 km stores as 20000.0 (probed). Unchanged
  from today, but **every new intermediate must stay 64-bit or the tool gets worse than it is**.
  The mitigation is a design rule (§13.8) and `attribcast` is the lever.
- **R3 — element ORDER.** `pointgenerate`'s order is believed to match the reference's
  section-major/index-minor order. **Verified on a 4-section fixture, not on 90 cases.**
  `geometry_digest` is the pin and it will be the first thing to move if this is wrong.
- **R4 — warn-never-block regresses.** A node errors where a verb wrapper degraded. Guards are
  designed in at N7 but every stage before it can introduce an ungarded failure. Add the
  degenerate-input case with the first guarded node, not at the end.
- **R5 — the corner cut mechanism is unmeasured.** The probe's foreach fixture failed to build, so
  neither candidate has a number. Two candidates, a written decision procedure, and it is last in
  the order for exactly that reason.
- **R6 — `plan.py`'s 89 `hou`-free unit tests** stop covering the shipped path. Mitigated by
  keeping them on the reference and adding `plan_parity`; stated so nobody discovers it later.
- **R7 — per-NODE fixed cost on many short curves.** §11.9 rule 2 in a new costume: 300 streets
  cook the graph 300 times' worth of fixed overhead that one 20 km fence never shows.
  `streets_300` is benched from N1.
- **R8 — the packed `transform` intrinsic's scale component** did not appear in the probe's
  `bounds` reading. Re-check against `packedfulltransform` before N4 relies on it.
- **R9 — OpenCL is unmeasured**, not measured-and-rejected. §13.5 records the criterion so the
  next agent does not reopen it without a workload, and does not cite a number that does not exist.

---

### 13.10 Decisions recorded this cycle

- **D148 — the kernel becomes a node network; the verb-only rule of §11.9 is superseded.** §11.9's
  "no `createNode` anywhere" was correct for a Python builder and is wrong for the tool the artist
  has to read. Everything else in §11.9's handover — the wrapper rule, the batching rule, the
  smallest-number rule, the additive-batch rule, the determinism rule, the trial rule and
  warn-never-block — **carries forward unchanged** and several are strengthened by the move.
- **D149 — OpenCL is declined for phase 1 again, with a criterion, and `pc_deform` is written to be
  transliterable.** Reopen at a single deform cook > 50 ms (~2.5e7 points). The probe's OpenCL
  timing was invalid and is not quoted.
- **D150 — the fitting solve ports to VEX as solve/expand/read over per-section arrays, not as
  `addpoint`.** `addpoint` from a multithreaded wrangle is thread-order dependent and would make
  `determinism` and `geometry_digest` a lottery on 90 cases. `pointgenerate` with an
  attribute-driven count is deterministic (probed, 3 cooks, identical digest) and costs 0.0002 s
  for 10 000 sections.
- **D151 — `chain`, `copytocurves`, `pathdeform` and `bend` are all rejected for the fill and the
  deform, each for a named limitation** (§13.4), and the reasons are written down so nobody
  re-derives them. The deform stays ours, in VEX, in one node.
- **D152 — `plan.py` loses its `hou`-free property for the shipped path and keeps it as the
  oracle.** 89 unit tests keep running against the reference; `plan_parity` covers the shipped
  path. Stated as a cost, not hidden as a detail.
- **D153 — every native node that can fail gets a guard `switch`.** Warn-never-block was free in a
  verb-only kernel and is not free in a network. This is a design requirement with its own check.
- **D154 — `kit.starter_kit()`'s geometry construction leaves Python** and becomes native `box`
  SOPs plus a manifest wrangle inside the HDA; `hda._padded`'s per-point loop becomes one line of
  VEX. Kit *authoring* stays Python; kit *construction in the cook path* does not.
- **D155 — one parm is added to §5 and no more: `Stage`**, a Debug-folder menu over the stage
  output nulls. It is the artist-visible form of §1c's "toggle nodes off to see what each does".


---

## 14. OpenCL, benchmarked — three candidates, three implementations each, both shapes

**Status:** measurement only, 2026-08-22, Houdini 22.0.398 / hython, branch `polychain`. **No
production file and no HDA was touched by this cycle** — every script lives in the scratchpad
(`pcbench.py`, `candA*.py`, `candB*.py`, `candC*.py`, `cand_extras.py`, `vexbump.py`,
`gpumem.py`). This section owns the *measurement*; §11.1's "OpenCL, anywhere — NO" row and
§13.5's reopen criterion (D149) own the *decision*, and both survive. What was missing from them
was numbers, and the numbers are here.

Hannes' question was **"which processes could use OpenCL, and is it actually faster?"** The answer
has three parts and only one of them is a yes.

### 14.0 The answer in five lines

1. **Candidate A (the deform point loop, ~10 FLOP/point): OpenCL LOSES to VEX at every size, on
   every shape, up to 20 000 000 points** — a flat 2.6× loss at fp64, 1.4× at fp32. There is no
   crossover to find; the kernel is transfer-bound and fp64 doubles the transfer.
2. **Candidate B (the deform gate, ~55 FLOP/station): OpenCL WINS — by 215 microseconds.** At
   polyChain's real size (9 996 pieces / 89 964 stations, one execution) VEX-64 is 492 µs and
   OpenCL-64 is 277 µs. The kernel's own **compile is 93 ms**, so the first cook of a session pays
   back over **433 cooks**. This is a win that is real, reproducible, and not worth having.
3. **The shape decides the sign, exactly as §11's architecture rule 2 says.** On `streets_300` —
   300 short curves — OpenCL is a **6.1× LOSS** on the same candidate B (0.0306 s vs VEX's
   0.0050 s), and it does not turn positive until ~666 pieces *per execution*, ~20× more than
   citygen hands the tool.
4. **The worst number in the study: keep today's per-piece call structure and swap Python for
   OpenCL and the stage gets 6.6× SLOWER.** 9 996 executions of 36 points: Python 0.158 s, VEX
   0.071 s, **OpenCL 1.043 s**. One execution of the same 359 856 points: Python 0.162 s, VEX
   0.00129 s, OpenCL 0.00256 s. Batching is worth 400× to OpenCL and 55× to VEX; the *language*
   is worth −2×.
5. **32-bit is inadmissible and that is now measured, not asserted.** Candidate A at 32 bits is
   **1.526e-05 m** off a Python/VEX-64 answer that is bit-identical, on an 8 km run — 85× the
   `marker_offset_m` tolerance (1.788e-07 m) the suite already asserts. Candidate B at 32 bits
   moves the curvature budget by **1.035e-04 m**, 1 % of `bend_tol`. So every OpenCL number below
   that matters is the fp64 one, and fp64 is where OpenCL is weakest on consumer silicon.

**Verdict, plainly: OpenCL is not warranted anywhere in polyChain today.** VEX-64 is the correct
member of the trio for the deform, and the gate's OpenCL win is 0.2 ms against a 1.36 s row. §13's
native rebuild should not carry an OpenCL node.

### 14.1 What was measured, and how

Three implementations of each candidate over **identical data**, parity checked before any timing:

| | Candidate A — `_deform_positions` | Candidate B — the deform gate |
|---|---|---|
| the kernel | `out = pos[s] + across[s]*z + up[s]*y` per point, station frames given | `span_deviation`'s spine walk + D87's off-spine chord term, reduced to a max per piece |
| arithmetic | ~10 FLOP/point (6 mul, 6 add) | ~55 FLOP/station: sqrt, acos, sin, 9 stations per piece |
| parallel over | points (the station loop above it is `_transport`, a sequential sign-carry — NOT ported) | pieces |
| (a) Python | the shipped loop shape, frames dict keyed by local x | the shipped `normal_at = None` path |
| (b) VEX | `attribvop` verb **and** a real `attribwrangle` node, `vex_precision 64` | same |
| (c) OpenCL | `opencl` verb **and** a real OpenCL SOP node, `precision` 32 and 64 | same |

Method, following §11's P5R rules: implementations **interleaved** (rep 0 of every implementation,
then rep 1, …, so a thermal or scheduler excursion hits all of them), **best-of-5** for the sweeps
and **best-of-25** for the crossover hunts, verb `setParms` **hoisted out of the timed region**,
kernel compile reported **separately**, and a memory column on every table. Node cooks are timed
by dirtying an upstream O(1) **detail** attribute; a `null` on the same input is cooked the same
way as the control and is printed, never subtracted.

**Hardware / device:** AMD Ryzen 7 9700X (8C/16T), 125.6 GiB RAM, **NVIDIA GeForce RTX 5060 Ti**
(OpenCL 3.0 CUDA 13.3.44, 36 CUs, `MAX_MEM_ALLOC_SIZE` 4.276 GB, `cl_khr_fp64` present but
`NATIVE_VECTOR_WIDTH_DOUBLE = 1`), stock configuration — **no `HOUDINI_OCL_*` variables set**. The
device selection is established by measurement, not by a HOM call: forcing
`HOUDINI_OCL_DEVICETYPE=CPU` changes every number (§14.5), so the default is the discrete GPU.

### 14.2 PARITY — measured first, because a fast wrong kernel is worthless

| candidate | implementation | max abs diff vs Python (fp64) | verdict |
|---|---|---|---|
| A (8 km world coords) | **VEX-64** (verb and node) | **0.000e+00** | bit-identical |
| A | **OpenCL-64** (verb and node) | **0.000e+00** | bit-identical |
| A | VEX-32 | 1.526e-05 m | 85× `marker_offset_m` — **inadmissible** |
| A | OpenCL-32 | 1.526e-05 m | **inadmissible** |
| B (2 000 pieces) | **VEX-64** | **0.000e+00** | bit-identical |
| B | **OpenCL-64** | **0.000e+00** | bit-identical |
| B | OpenCL-32 | 1.035e-04 m | 1 % of `bend_tol`; 0 / 2 000 gate decisions flipped on this fixture, but the budget moves |
| C | OpenCL `runover = worksets` vs plain | **0.000e+00** | the workset dispatch is exact |

The gate fired on 1 711 of 2 000 pieces on the parity fixture, so the branch under test was
genuinely exercised rather than short-circuited.

### 14.3 CANDIDATE A — the deform point transform. OpenCL loses everywhere.

`precision 64`, VEX 64, best of 5, interleaved. `null_nd` is the forced-cook floor of the network,
printed and not subtracted. Peak WS is the **process** peak (kernel32), so only the first rows read
as deltas.

| shape | N total | N / exec | execs | Python | py_loop | vex64 verb | ocl64 verb | vex64 node | ocl64 node | null node | winner | peak WS |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| one | 1 008 | 1 008 | 1 | 0.00039 | 0.00030 | **0.00004** | 0.00012 | 0.00007 | 0.00014 | 0.00004 | **VEX** | 579 MB |
| one | 10 008 | 10 008 | 1 | 0.00444 | 0.00332 | **0.00024** | 0.00041 | 0.00023 | 0.00033 | 0.00011 | **VEX** | 609 MB |
| one | 100 008 | 100 008 | 1 | 0.04418 | 0.03265 | **0.00066** | 0.00104 | 0.00047 | 0.00096 | 0.00025 | **VEX** | 719 MB |
| one | **360 000** | 360 000 | 1 | 0.16478 | 0.12432 | **0.00123** | 0.00253 | 0.00109 | 0.00230 | 0.00025 | **VEX** | 965 MB |
| one | 1 000 008 | 1 000 008 | 1 | 0.46875 | 0.35505 | **0.00284** | 0.00671 | 0.00278 | 0.00645 | 0.00031 | **VEX** | 1 512 MB |
| **s300** | 100 008 | 324 | 300 | 0.03829 | 0.03060 | **0.00426** | 0.03465 | 0.01066 | 0.04455 | 0.00399 | **VEX** | 1 512 MB |
| **s300** | 360 000 | 1 188 | 300 | 0.14286 | 0.11893 | **0.01112** | 0.04435 | 0.01822 | 0.06022 | 0.00468 | **VEX** | 1 512 MB |
| **s300** | 1 000 008 | 3 312 | 300 | 0.41355 | 0.34452 | **0.02601** | 0.05794 | 0.03281 | 0.07150 | 0.00402 | **VEX** | 1 512 MB |

At 32-bit OpenCL — which parity has already ruled out — the loss narrows but never closes: 0.00157 s
vs VEX-64's 0.00122 s at 360 000 points.

**The crossover hunt, pushed 55× past anything polyChain can produce** (its largest measured
single-cook point set is 359 856), one execution, best of 5:

| N | vex64 | ocl64 | ocl/vex | ocl32 | ocl32/vex | winner | peak WS | device mem |
|---|---|---|---|---|---|---|---|---|
| 1 000 008 | 0.0028 | 0.0068 | **2.44** | 0.0035 | 1.32 | VEX | 812 MB | — |
| 4 000 032 | 0.0107 | 0.0284 | **2.65** | 0.0164 | 1.49 | VEX | 2 088 MB | +335 MiB |
| 10 000 008 | 0.0285 | 0.0754 | **2.65** | 0.0418 | 1.44 | VEX | 4 267 MB | — |
| 20 000 016 | 0.0581 | 0.1534 | **2.64** | 0.0838 | 1.44 | VEX | 7 915 MB | +1 295 MiB |

**There is no crossover N for candidate A.** The ratio is flat at 2.6× from 10⁶ to 2×10⁷, which is
the signature of a bandwidth-bound kernel: at fp64 a 20 M-point pass moves ~950 MB of buffers for
10 FLOPs of work per point. §13.5's reopen criterion — "a single deform cook exceeding 50 ms,
i.e. > 2.5e7 points" — is now **measured and refuted for this kernel**: at 2×10⁷ points the cook is
58 ms and OpenCL is still 2.6× behind. **D156.**

**Device memory, actually measured** (nvidia-smi polled between executions inside a 3 s loop, idle
baseline 8 769 MiB): 360 000 points → **+139 MiB** against 17 MB of computed fp64 buffers;
20 000 016 points → **+1 295 MiB** against 954 MB computed. So OpenCL costs roughly **~120 MiB of
VRAM just to exist**, plus ~1.35× the raw buffer bytes. At polyChain's real size the buffers are
irrelevant and the fixed footprint is 7× larger than the data.

### 14.4 CANDIDATE B — the deform gate. OpenCL wins, and the win is 215 microseconds.

Same method. 9 stations per piece (D71). `precision 64`.

| shape | pieces | pieces / exec | station evals | execs | Python | py_loop | vex64 verb | ocl64 verb | vex64 node | ocl64 node | null node | winner |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| one | 1 000 | 1 000 | 9 000 | 1 | 0.00586 | 0.00542 | 0.00026 | **0.00019** | 0.00029 | 0.00020 | 0.00007 | **OpenCL** |
| one | **9 996** | 9 996 | 89 964 | 1 | 0.06124 | 0.05452 | 0.00073 | **0.00057** | 0.00060 | 0.00047 | 0.00023 | **OpenCL** |
| one | 100 000 | 100 000 | 900 000 | 1 | 0.65951 | 0.57907 | 0.00281 | **0.00141** | 0.00288 | 0.00137 | 0.00026 | **OpenCL** |
| one | 1 000 000 | 1 000 000 | 9 000 000 | 1 | 6.74555 | 5.83276 | 0.02810 | **0.00900** | 0.02780 | 0.00887 | 0.00028 | **OpenCL** |
| **s300** | 1 000 | 3 | 9 000 | 300 | 0.00652 | 0.00488 | **0.00254** | 0.03028 | 0.01038 | 0.04037 | 0.00393 | **VEX (ocl 11.9× worse)** |
| **s300** | **9 996** | 33 | 89 964 | 300 | 0.06373 | 0.05653 | **0.00501** | 0.03061 | 0.01270 | 0.04038 | 0.00396 | **VEX (ocl 6.1× worse)** |
| **s300** | 100 000 | 333 | 900 000 | 300 | 0.64571 | 0.58595 | **0.02581** | 0.03842 | 0.03435 | 0.05027 | 0.00403 | **VEX (ocl 1.5× worse)** |
| **s300** | 1 000 000 | 3 333 | 9 000 000 | 300 | 6.53177 | 6.04936 | 0.22968 | **0.05310** | 0.24249 | 0.06929 | 0.00424 | **OpenCL 4.3×** |

Peak WS 588 MB at 1 000 pieces rising to 6 638 MB at 1 000 000 — the Python column's lists, not
the kernels'. The 1 000 000-piece rows are crossover hunting only: polyChain's real maximum is
~10 000 pieces.

**The fine sweep that locates the crossover** (best of **25**, interleaved, one execution):

| pieces | station evals | vex64 µs | ocl64 µs |
|---|---|---|---|
| 500 | 4 500 | **118.7** | 203.4 |
| 1 000 | 9 000 | 221.4 | **127.2** |
| 2 000 | 18 000 | 603.5 | **173.5** |
| 4 000 | 36 000 | 1 179.6 | **179.7** |
| 6 000 | 54 000 | 480.1 | **196.5** |
| **9 996** | **89 964** | **492.1** | **276.6** |
| 20 000 | 180 000 | 818.4 | **358.7** |

**Crossover: ~700 pieces / ~6 300 station evaluations, in ONE execution.** Above it OpenCL wins by
1.4–6.6×.

**And an `attribvop` behaviour worth writing down: VEX has a threading cliff at ~5 000 elements.**
The VEX column rises linearly 500 → 4 000 (119 → 1 180 µs) and then **falls** at 6 000 (480 µs).
Reproduced over 25 reps in three separate processes. It is not noise, and it means a VEX stage
sized between 1 000 and 5 000 elements is running single-threaded — which is exactly where the
gate would sit on a short street. That is a **VEX** tuning finding, and it is worth more than the
OpenCL question: batching the gate across curves gets it over the cliff.

**What the win is actually worth.** At the real size the OpenCL advantage is
492 − 277 = **215 µs**, against a `deform_20km` row of 1.3618 s — **0.016 % of the row.** The
kernel's cold compile is **93 ms**, so the first cook of a session pays back after **433 cooks**.
And the portable arithmetic is only part of the stage: the shipped `_needs_deform` +
`_bend_deviation` cost 0.4366 s on `deform_20km`, of which this kernel's Python equivalent is
0.0612 s — the other 0.375 s is `path.sample`, the dict plumbing and the per-piece call overhead,
none of which any language change touches.

**So candidate B's honest reading is: Python → VEX-64 is 84× (0.0612 → 0.00073 s) and worth doing;
VEX → OpenCL is 1.8× of a number that is already sub-millisecond, costs a second language, a 93 ms
compile and a 120 MiB VRAM floor, and reverses to a 6.1× loss on the citygen shape.**

### 14.5 CANDIDATE C — the batch-shape control. The floor, the device, and worksets.

**(1) The per-execution floor** (best of 25, `setParms` outside the timer, one execution):

| pieces | ocl64 µs | vex64 µs | ocl/vex |
|---|---|---|---|
| 1 | 93.9 | 10.1 | 9.30 |
| 10 | 92.3 | 11.7 | 7.89 |
| 100 | 96.5 | 31.1 | 3.10 |
| 300 | 119.0 | 72.8 | 1.63 |

**OpenCL's floor is ~92 µs per execution; VEX's is ~10 µs.** (§11's earlier 300 µs / 100 µs
reading was taken with `setParms` inside the timer and on a different kernel; with parms hoisted
the floors are 92 µs and 10 µs, and the *ratio* — 9× — is what matters and is unchanged.)

**(2) The floor is PART transfer, not all binding layer — this corrects the prior cycle.** Forcing
`HOUDINI_OCL_DEVICETYPE=CPU` (Intel OpenCL runtime on the Ryzen, `HOST_UNIFIED_MEMORY = 1`, no
PCIe) drops the floor from **93.9 µs to 37.9 µs** at N = 1 and from 96.5 µs to 53.5 µs at N = 100.
So ~55 µs of the GPU's floor is the transfer/queue and ~38 µs is Houdini's binding layer — and
**38 µs is still 4× VEX's 9 µs**, so no device choice removes the penalty. (The CPU device also
*beats* the GPU up to ~30 000 pieces on this kernel and loses above 100 000: 1 367 µs vs 1 039 µs.)

**(3) `runover = worksets` recovers a third of the loss and is still the wrong answer.** One
execution over 300 worksets, bit-identical to the plain dispatch:

| total pieces | 300 separate executions | ONE execution, 300 worksets | ONE plain execution | VEX 300× | VEX 1× |
|---|---|---|---|---|---|
| 9 000 | 0.02932 | **0.00896** | **0.00029** | 0.00480 | 0.00063 |
| 9 900 | 0.02920 | 0.00888 | 0.00035 | 0.00499 | 0.00071 |
| 99 900 | 0.04349 | 0.01687 | 0.00105 | 0.03586 | 0.00296 |
| 999 900 | 0.05236 | 0.01913 | 0.00810 | 0.23089 | 0.02743 |

Worksets are **3.3× better than 300 host executions and still 31× worse than one plain execution**
— the internal dispatch costs ~29 µs per workset. The prediction that worksets are "the only way
an OpenCL port survives `streets_300`" is **half right and beside the point**: they do recover most
of the launch cost, and they are still beaten by simply doing one execution, in either language.

**(4) The s300 crossover for candidate B** (300 executions, best of 5): VEX wins at 333 pieces per
execution (0.0356 vs 0.0413) and OpenCL wins from 666 (0.0660 vs 0.0426). `streets_300` hands the
tool **30** pieces per curve.

### 14.6 The batch shape is worth more than the language — the number that says it

Candidate A, 359 856 points, the same arithmetic, only the call structure changed:

| call structure | Python | VEX-64 | OpenCL-64 |
|---|---|---|---|
| **1 call × 359 856 points** | 0.16196 | **0.00129** | 0.00256 |
| **9 996 calls × 36 points** (what `place.py` does today) | 0.15771 | 0.07088 | **1.04293** |

Batching is worth **55× to VEX and 407× to OpenCL**; the language is worth **−2×**. And in the
shape the tool currently has, **OpenCL is 6.6× slower than the Python it would replace.** This is
§11's architecture rule 2 in its most extreme form and it is the single most useful number in this
section: **any port that keeps a per-piece call is a regression regardless of language.**

### 14.7 Compile time, stated separately (P5R rule 5)

| kernel | cold, first execution in a fresh process | warm execution | compile | across sessions? |
|---|---|---|---|---|
| Candidate A, OpenCL | 0.1414 s (never-seen text) | 0.00042 s | **0.1409 s** | partially disk-cached: same text in a new process 0.1313 → **0.0919 → 0.0924 s** |
| Candidate B, OpenCL | 0.0932 s | 0.00032 s | **0.0929 s** | same behaviour |
| Candidate A, VEX | 0.0730 s (first VEX verb in the process) | 0.00018 s | 0.0728 s | **no** — 0.0700 / 0.0654 / 0.0690 across three processes |
| Candidate B, VEX | 0.0116 s (VEX runtime already up) | 0.00032 s | **0.0112 s** | n/a |

Within one process a **second** verb object with the same kernel text is already warm (0.00043 s),
so compile is once per distinct kernel text per session. **A ~0.09–0.14 s OpenCL compile is 28–41 %
of the entire `packed_20km` cook (0.338 s) and 45–67 % of `streets_300` (0.209 s)** — an OpenCL
stage makes the first cook of a session visibly worse to make later cooks imperceptibly better.
VEX's compile, once the runtime is up, is **8× cheaper**.

### 14.8 Two Houdini behaviours found while doing this, both worth not rediscovering

**(a) The `opencl` verb cannot change `precision` twice in one process.** 32-then-64 and
64-then-32 both raise `Invalid attribute 'P'`; the same precision twice is fine, and the OpenCL
**node** switches cleanly. Every sweep here therefore runs **one precision per process**.

**(b) A mismatched integer binding precision silently destroys the OpenCL context.** With node
`precision = 64` the generated signature's `exint` is 64-bit; leaving an int binding at 32 does not
error — it writes past the buffer, and the *session* then fails with
`clFinish -36 CL_INVALID_COMMAND_QUEUE` followed by `CL_OUT_OF_RESOURCES` on **every later kernel,
including ones that worked a moment earlier**. Bisected to a single binding. It cost an hour and it
looks exactly like "the GPU is out of memory". Set every binding to the node's precision.

*(Also: `houdini_validate_opencl` in the MCP validates **COP/Copernicus** kernels — it demands
`src`/`dst` layer bindings and rejects a valid SOP kernel with "No output matching runover mode
provided". SOP OpenCL is validated by executing the verb, which is what was done here.)*

### 14.9 What this changes, and what it does not

- **§11.1's "OpenCL, anywhere in phase 1 — NO" stands, now with numbers.** It said the deformed
  branch's 360 000 points are done by VEX in 0.089 s and a GPU transfer is cost without payoff.
  Measured: the point pass is **0.00123 s** in VEX and **0.00253 s** in OpenCL. The conclusion was
  right and the reasoning was right.
- **§13.5's D149 criterion is refuted for the deform kernel and should be restated.** "> 2.5e7
  points in one cook" does not make OpenCL win: at 2×10⁷ points it is still 2.6× behind, because
  the limit is arithmetic intensity, not N. **The correct criterion is per-element work, not
  element count: OpenCL becomes worth measuring when a single stage does more than roughly
  50 FLOP per element AND runs as ONE execution of more than ~1 000 elements.** Candidate B is the
  first stage in the tool to satisfy both, and it satisfies them by 1.8× on a 0.5 ms stage. **D157.**
- **D149's architectural preparation was still right and should be kept.** `pc_deform` written as
  one self-contained kernel over (piece index, local xyz, station arrays) is exactly what made
  candidate A a 40-line transliteration in both languages, and it is what makes the VEX version
  fast. The constraint costs nothing; only the OpenCL conclusion changes.
- **The real optimisation this study points at is not a language.** In descending order of measured
  payoff: (1) **one execution per build instead of one per piece** — 55× to VEX, 407× to OpenCL,
  and a 6.6× *regression* if skipped; (2) **Python → VEX-64 on the gate** — 84× on the portable
  arithmetic; (3) **batching the gate across curves to clear `attribvop`'s ~5 000-element
  threading cliff**; (4) OpenCL — 215 µs, minus a 93 ms compile.

**One sentence for Hannes: the geometry work does belong in native nodes, VEX or OpenCL, and on
this workload the right member of that trio is native verbs first and VEX-64 second — OpenCL is
measurably slower for the deform at every size up to 20 million points, measurably faster for the
gate by 0.2 ms, and a 6.1× loss on the 300-short-curves shape citygen actually produces.**

---

### 14.10 The audit of §14 — what survived, what had to be corrected, and the VERDICT

**Status:** independent audit of §14, 2026-08-22, same machine and build (Houdini 22.0.398 /
hython, RTX 5060 Ti, Ryzen 7 9700X, stock `HOUDINI_OCL_*`). Every headline comparison in §14 was
**re-run from scratch** rather than read; the audit scripts are `audit_parity.py`,
`audit_B_vex.py`, `audit_jobsize.py`, `audit_extra.py`, `audit_compile.py`, `audit_compile2.py`,
`audit_vexprec.py` in the same scratchpad. **No production file and no HDA was touched.**

*(The brief for this pass asked for the verdict as "§12.x". §12 became the phase-2 build log and
§14 is the section that owns the OpenCL measurement, so the verdict lives here and §12's
`Cycle P2-OCL` entry points at it — one owner per topic, per the doc convention.)*

#### 14.10.1 What reproduced — the load-bearing numbers all held

| claim | §14 | re-measured | verdict |
|---|---|---|---|
| A, one exec, 360 000 pts | vex 0.00123 / ocl 0.00253 | vex **0.00122** / ocl **0.00242** | reproduced |
| A, one exec, 1 000 008 pts | vex 0.00284 / ocl 0.00671 | vex **0.00292** / ocl **0.02356** | sign reproduced; ocl noisier than quoted |
| A, s300, 360 000 pts | vex 0.01112 / ocl 0.04435 | vex **0.01604** / ocl **0.05044** | reproduced |
| B, one exec, 9 996 pieces | vex 0.00073 / ocl 0.00057 | vex **0.00083** / ocl **0.00052** | reproduced |
| B, one exec, 100 000 pieces | vex 0.00281 / ocl 0.00141 | vex **0.00285** / ocl **0.00134** | reproduced |
| **B, s300, 9 996 pieces** | vex 0.00501 / ocl 0.03061 | vex **0.00486** / ocl **0.02959** | **6.1× loss confirmed** |
| B, s300, 1 000 000 pieces | vex 0.22968 / ocl 0.05310 | vex **0.23088** / ocl **0.05798** | reproduced |
| per-execution floor, N = 1 | ocl 93.9 µs / vex 10.1 µs | ocl **93.8 µs** / vex **9.7 µs** | reproduced to 1 % |

**Candidate A's result is not fragile.** VEX beat OpenCL in every row of both shapes on the re-run,
as it did in §14. **Candidate B's inversion between the two shapes is not fragile either** — it is
the same 6× loss on the citygen shape and the same ~1.6× win the other way on one big execution.

#### 14.10.2 Seven things that had to be corrected

1. **§14.2's OpenCL-64 parity row could not have been produced by the script that reports it.**
   `candA_parity.py` runs `ocl32` and then `ocl64` in one process — which §14.8(a) itself documents
   as impossible. Re-run today it raises `Invalid attribute 'P'` on the ocl64 row. Re-measured one
   precision per process, **the claim is true**: ocl64 matches the Python reference exactly. The
   conclusion stands; the evidence for it was broken.
2. **The parity fixture is a 225 m run, not "~8 km world coords".** `candA.make(3600)` is 100
   pieces / 900 stations at 0.25 m spacing — `max|coord| = 224.7 m`, measured. Every parity number
   in §14.2 is a 225 m number wearing an 8 km label.
3. **"Bit-identical, 0.000e+00" means identical *after* 32-bit storage rounding.** `P` on a
   `hou.Geometry` is a 32-bit float attribute, so every implementation — including both fp64 ones —
   is quantised on write. Measured against a Python fp64 result that never went through a geometry:

   | fixture | max coord | fp32 **storage** floor | vex32 vs raw fp64 | vex64 vs raw fp64 |
   |---|---|---|---|---|
   | §14.2's fixture | 224.7 m | 7.624e-06 m | 1.428e-05 m | **7.624e-06 m** |
   | 320 004 pts, R = 8 km | 14 409 m | 4.883e-04 m | 9.714e-04 m | **4.883e-04 m** |
   | 320 004 pts, 20 km run | 19 992 m | 9.765e-04 m | 1.513e-03 m | **9.765e-04 m** |

   fp64 compute lands **exactly on the storage floor** — it reproduces what the shipped Python
   already produces, bit for bit. fp32 compute lands **1.55× beyond it**.
4. **So §14.0's "85× `marker_offset_m`" argument is not a discriminator and should not be quoted.**
   At 20 km the fp32 *storage* of `P` alone is 9.765e-04 m — 5 500× that tolerance — and the tool
   ships with it today. **The correct statement of the same conclusion is stronger:** an fp64
   kernel moves the shipped answer by **0.000e+00**, an fp32 kernel moves it by **5.4e-04 m at
   20 km**, and §11.1 declined `copytopoints` for a baseline movement of 4.34e-07 m. fp32 is
   inadmissible by three orders of magnitude, for the reason "it moves the baseline", not for the
   reason §14.0 gives.
5. **Candidate B's VEX baseline was mildly handicapped, and the win survives it.** The shipped VEX
   kernel calls `resize(spine, K)` — a heap-allocated VEX array per element — while the OpenCL
   kernel uses a fixed private `fpreal spine[9]`. An array-free unrolled VEX (parity identical) is
   10–40 % faster, best of 25:

   | pieces | vex shipped µs | **vex unrolled µs** | ocl64 µs | unrolled/ocl |
   |---|---|---|---|---|
   | 500 | 122.8 | **89.3** | 136.0 | **0.66 — VEX wins** |
   | 1 000 | 216.8 | 169.4 | **127.1** | 1.33 |
   | 2 000 | 587.8 | 447.8 | **178.9** | 2.50 |
   | 4 000 | 1 115.2 | 666.4 | **189.1** | 3.52 |
   | **9 996** | 496.6 | **444.3** | **281.4** | **1.58** |
   | 20 000 | 854.4 | 715.9 | **370.8** | 1.93 |
   | 100 000 | 2 688.5 | 2 165.0 | **1 139.4** | 1.90 |

   OpenCL's advantage at the real size falls from **215 µs to 163 µs**. It does not vanish.
6. **The "VEX threading cliff" is real but its stated mechanism is unsupported.** `attribvop` does
   expose `vex_threadjobsize` (default **1024**) and `vex_multithread`, which would explain a
   thread-starved pass below ~16 000 elements — but driving it 1024 → 256 → 64 → 16 changes
   nothing (at 9 996 pieces: 518.5 / 493.2 / 515.2 / 533.4 µs, best of 25, parity identical). The
   non-monotonic shape (4 000 slower than 6 000 and 9 996) reproduces across every job size and
   across processes. **It is a reproducible `attribvop` anomaly with an unknown cause; §14.4's
   "a VEX stage sized 1 000–5 000 runs single-threaded" is a hypothesis, not a measurement.**
7. **"VEX's compile is 8× cheaper" is a marginal cost, not a first-cook cost.** Both are true and
   §14.7 quotes only one:

   | | first kernel in a fresh process | each additional distinct kernel |
   |---|---|---|
   | OpenCL | **0.1013–0.1774 s** (0.101 disk-cached, 0.167 never-seen text) | **0.0563–0.0576 s** |
   | VEX | **0.0690–0.0760 s** | **0.0081–0.0082 s** |

   The first pass in either language costs ~0.07–0.17 s because the *runtime* comes up; the
   language difference at the margin is 7×. An HDA that carries one OpenCL node pays ~0.1 s on the
   session's first cook — 30 % of `packed_20km`, 48 % of `streets_300` — and ~0.056 s for every
   further kernel it carries.

#### 14.10.3 The ceiling §14 never applied to candidate B — and it decides the case

Candidate B's kernel does not read a geometry today; the gate runs in Python over station arrays.
To hand those arrays to *either* language they must first exist as a `hou.Geometry`. Measured at
9 996 pieces / 89 964 stations, best of 5:

| | seconds |
|---|---|
| build the station geometry that feeds the kernel (`createPoints` + one vector attribute) | **0.02704** |
| VEX-64 kernel | 0.00044 |
| OpenCL-64 kernel | 0.00028 |
| **the device advantage** | **0.00015** |

**Feeding the kernel costs 180× what choosing the device is worth.** If §13's rebuild does not put
the stations in a geometry, OpenCL's win is 0.55 % of the price of the data it consumes; if it
does, the win is 0.016 % of the row it sits in. There is no arrangement in which it is visible.

#### 14.10.4 DOUBLE PRECISION — what 64-bit costs on this device, and whether it flips anything

polyChain needs 64-bit at world scale (§11.0b; 14.10.2(3)–(4) above now measure *why*: fp64 is the
only precision that reproduces the shipped answer exactly). The cost, both languages, candidate B's
kernel, best of 25 — OpenCL's two precisions measured in **separate processes**, because the verb
cannot switch precision (§14.8a):

| pieces | vex32 µs | vex64 µs | **VEX fp64 tax** | ocl32 µs | ocl64 µs | **OpenCL fp64 tax** |
|---|---|---|---|---|---|---|
| 1 000 | 160.7 | 218.5 | 1.36× | 120 | 160 | 1.33× |
| **9 996** | 403.4 | 530.1 | **1.31×** | 440 | 520 | **1.18×** |
| 100 000 | 2 314.0 | 3 021.6 | 1.31× | 790 | 1 340 | **1.70×** |
| 1 000 000 | 21 094.6 | 27 318.3 | 1.30× | 3 110 | 8 520 | **2.74×** |

**The honest reading, which is not the one §14 implies:** at polyChain's real size fp64 costs VEX
slightly *more* than it costs OpenCL (1.31× vs 1.18×), so requiring 64-bit does **not** flip
candidate B — it flips only above ~10⁵ elements, where the GPU's `NATIVE_VECTOR_WIDTH_DOUBLE = 1`
bites and the tax climbs to 2.74×. For candidate A the fp64 tax is what makes the loss permanent:
it doubles the traffic on a kernel that was already transfer-bound, and the ocl/vex ratio sits flat
at 2.6× from 10⁶ to 2×10⁷ points. **64-bit does not change the verdict on either candidate; it
removes any reason to look at the 32-bit numbers at all.**

#### 14.10.5 THE VERDICT, per candidate and per shape

**No OpenCL anywhere in polyChain. Not now, and not at any size this tool or citygen produces.**

| candidate | one long run (20 km, 1 cook) | **citygen shape (300 short curves)** | is OpenCL worth it? |
|---|---|---|---|
| **A — deform point transform** (~10 FLOP/pt, 359 856 pts) | VEX **0.00122** s, OpenCL **0.00242** s | VEX **0.01604** s, OpenCL **0.05044** s | **NO — at every size, on both shapes, up to 2×10⁷ points.** There is no crossover to wait for. |
| **B — the deform gate** (~55 FLOP/station, 9 996 pieces) | VEX **0.00083** s, OpenCL **0.00052** s → OpenCL by **163–215 µs** | VEX **0.00486** s, OpenCL **0.02959** s → **6.1× LOSS** | **NO.** The win is real, reproducible, and worth 0.016 % of the row it lives in — against a ~0.1 s first-cook compile (payback ~500 cooks), a ~120 MiB VRAM floor, a second language in the HDA, and a 6× regression on the shape the first consumer actually produces. |
| **everything else** (plan, corners, stamp, conform ray-cast, sampler) | — | — | **NO, and not close.** Sequential prefix solves, N = 199 branching combinatorics, string attribute writes with zero arithmetic, and a native `ray` verb already running at 0.32 µs/query. |

**The conditions under which this would change, stated so nobody reopens it without one.** All four
must hold: a stage doing **> ~50 FLOP per element**; dispatched as **ONE execution over > ~1 000
elements**; over data **already resident in a geometry**, so the 0.027 s marshalling is not charged
to it; in a row long enough that a ~0.1 s first-cook compile is invisible. Candidate B satisfies
the first two and fails the last two. Nothing in phase 1 or the phase-2 row stack satisfies all
four.

**And the number that actually matters is not about OpenCL at all.** Candidate A, 359 856 points,
identical arithmetic, only the call structure changed: one execution — Python 0.16196, VEX
**0.00129**, OpenCL 0.00256; 9 996 executions of 36 points, which is what `place.py` does today —
Python 0.15771, VEX 0.07088, OpenCL **1.04293**. **Batching is worth 55× to VEX and 407× to
OpenCL; the language is worth −2×.** In today's per-piece shape OpenCL is 6.6× slower than the
Python it would replace. Fix the call structure, then use VEX-64, and stop there.

#### 14.10.6 Decisions

- **D158 — OpenCL is DECLINED for polyChain, audited, and the reopen criterion is now four
  conditions rather than one.** §11.1's row and §13.5's D149 both stand. D149's "> 2.5e7 points" is
  withdrawn (D156 already refuted it); D157's "> 50 FLOP/element in one execution of > 1 000
  elements" is **necessary but not sufficient** — add "data already in a geometry" and "a row long
  enough to hide a ~0.1 s first-cook compile". **§13's native rebuild carries no OpenCL node.**
- **D159 — 64-bit is mandatory for any ported kernel, and the reason is baseline movement, not a
  tolerance ratio.** An fp64 kernel reproduces the shipped Python answer with max |dP| =
  **0.000e+00**; an fp32 kernel moves it by **5.4e-04 m at 20 km**. §14.0's "85× `marker_offset_m`"
  framing is withdrawn — `P`'s own 32-bit storage exceeds that tolerance by 5 500× and always has.
  fp64 costs VEX a flat 1.30–1.36× on this CPU; that is the price of not moving the baseline, and
  it is paid.
- **D160 — §14.4's "`attribvop` runs single-threaded below ~5 000 elements" is downgraded to an
  unexplained anomaly.** The non-monotonic timing reproduces; `vex_threadjobsize` (default 1024) is
  **not** its cause — 1024 → 16 changes nothing. Do not size a VEX stage around this claim until
  the mechanism is known.
