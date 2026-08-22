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
| Last completed | **cycle 8** — the three-reviewer pass over cycle 7, worked through: **13 findings, every one reproduced first, 12 confirmed and fixed** (two were the same defect). The big one is **D87 — the curvature budget was measured on the SPINE**, so a 1.2 m tall bendable rail on an R = 55 m climbing arc stayed **15 of 15 PACKED** on a 0.0091 m spine reading while its top corner had really moved **0.0327 m (3.3x `bend_tol`)**; `span_deviation` now takes the module's off-spine radius. It also closed three pre-existing bend-corner defects (`AS` 0.0424 m, `T` 0.0424 m, `CJ` 0.060 m) and **shrank the bend butt wedge 0.0009 -> 0.000193 m²**. Then **D91** (the Gap parm was live under a wired payload — one payload, two fences), **D94** (`attr:<name>` read exactly two names, so streets' own hook declined everything in silence), **D88** (the marker slot was unreachable from the parm face — PC-G1's own bullet), and D89/D90/D92/D93/D95 plus the artist-UX set (units in seven labels, `StringToggle` slot menus, de-duplicated menu, a slow-cook warning naming the proxy). Suite: **76 scene cases / 0 failing**, **22 HDA checks**, **145 unit tests**, `scale_gate` 0 failing rows, three mutations run and all three red. Before it: **cycle 7**, the curvature budget, §3.3's reader, §5's parm face and §6's starter kit
| Next up | **Gates PC-G1 and PC-G2's GUI viewport pass** (the only thing they still owe, and it needs the wedged bridge or Hannes), then **the deform path's VEX rewrite** — the 11.0 s R = 10 m row of `scale_gate.py` is what that number is about — and **§4.4's flatten-under**. Then the deferred acceptance: streets consuming polyChain. **Open findings still standing:** (1) ~~the binary kink test~~ — **CLOSED, D75**; (2) a **corner assembly in BEND mode** on a steep pitch inherits §4.4's deferred flatten-under (0.074 m on a 37° leg) — the *butt wedge* half of this got materially smaller in cycle 8 (D87: 0.0009 → 0.000193 m² on `AS`), the flatten-under half is untouched; (3) a `vertical` piece on a uniform slope is a **pure shear** and could stay packed, but does not, deliberately (D65); (4) a 3D (unflattened) bevel's cut plane is **not** dropped onto the conform surface — harmless while the plane is vertical, which is every case in the suite; (5) **the good-looking default is a board fence, not a picket fence** — making `picket_panel` the default means re-deriving `corner_face_mate` / `corner_breach` / `corner_wedge` for a voided module (D86), a cycle not a patch; (6) ~~`plan_points`' stale docstring~~ — **the camber's own off-spine rotation is NOT in the D87 budget**: a packed piece takes the MIDPOINT surface normal (`_packed_transform`) while the deformed one takes a normal PER STATION, and D87 measures the path's turn only. Unreachable in the suite as it stands — measured this cycle, all 15 conform cases keep **zero** bendable pieces packed, because `Surface.deviates` unpacks them first — so it is a gap in the budget rather than a defect in the output. ⚠️ `/obj/polychain_gate` **may still be sitting in Hannes' GUI session** — the bridge was not touched this cycle either
| Gates | PC-G0 ✅ resolved (§2.3) · **PC-G1 numerically complete + IMAGE-VERIFIED (headless), GUI viewport pass still owed** — the closed rectangle and the L close in both corner modes, all four fill modes, the gate on its marker (1.8e-7 m), convex and reflex corners; the bend corner's butt wedge is MEASURED and baselined as the accepted limit (D36 extended), and cycle 6's mutation of it fails by 1.10e-02 m on `CJ_bend_butt_120`. Cycle 8 closed the last hole in its parm face: the **marker slot is authorable on the page** (D88), so PC-G1's gate-on-a-marker no longer needs a payload, and an unread marker warns · **PC-G2 numerically complete + IMAGE-VERIFIED (headless), INCLUDING the curving-spline variant it used to owe; GUI viewport pass still owed** — cycle 6 built the gate's own wording: a 24 m spline that **turns in plan (±3.6 m S-curve) and climbs 2.4 m**, resampled at 0.25 m, over a 2D terrain (`1.1 sin(2πx/13) + 0.8 cos(2πz/9) + 0.06x`), conform ON. All four modes pass **50 of 50** suite checks with **0 failures and nothing baselined**: `plumb_deg` **0.0** over 14 vertical pieces, `flat_stepped_m` **0.0** over **240 stepped posts, 240/240 still PACKED**, `bank_deg` **27.15°** adaptive, camber ON halving the residual to the surface normal (`camber_deg` 37.31° → **17.20°**), `conform_contact_m` **0.0**, `conform_misses` **0**, `inward_faces` **0**, no warnings. Judged on `VG2P_{vertical,stepped,adaptive}.png` and `VG2C_camber_cu.png`: the pickets' ribs are dead vertical while the run's foot follows the ground line, the adaptive rail's ribs lean perpendicular to the drape, the posts' tops make a clean sawtooth over a smooth ground line, and the cambered rail is visibly rolled onto the cross-fall. The **riser under each stepped piece is there and is expected** — §4.4's flatten-under is deliberately not built — and it measures **0.061 m** on this hill · **PC-G3 numerically MEASURED at scale, and narrower than its headline** — 20 km, 10 005 × 2 m bendable panels: **10 005 packed, 0 deformed, one shared `geometryid`, 10 005 real points, +12.1 MB RSS, 0.42 s** as a two-point spline and **the same numbers at 0.55 s** as a **20 011-vertex resampled polyline** — independently reproduced in cycle 6, and D69 is what buys it (reverting D69 takes the resampled form to 0 packed / 10 005 deformed / 360 180 points / **21.9 s**). ⚠️ ~~The gate holds for a STRAIGHT resampled run only~~ — **CLOSED by D75 in cycle 7**: `hython tests/polychain/scale_gate.py` is the harness now, and R = 12 000 / 2 000 / 80 m all read **10 000 packed / 0 deformed / 10 000 points / +5.1 MB / ~0.60 s**, while R = 10 m (five times the budget) still deforms all 10 000 at 10.8 s. The FLOOR rides the suite: `A_straight`, `CE_all_packed`, `CA_swap_module`, `CF_resampled_straight` and `CG_resampled_bendable` are asserted 100 % packed and `over_unpacked` proves nothing unpacks without a reason. Owed: the deform path's VEX rewrite, which is what the 18.9 s number is about · **PC-G4 ✅ PASSES, measured headlessly** (§10 cycle 7): the same fence driven entirely by a style payload on input 3 with the parms at defaults, asserted in `tests/polychain/run_hda_checks.py` — the payload replaces the modules, the styleId and the ids, matches the kernel built from the `Style` object directly, and **the parms are provably inert while it is wired** — cycle 8 turned that from two parms into a SWEEP of the whole page (`swept 36 parms; moved: none`, ids AND rounded positions, exempting only `display`/`show_warnings`/`kitfile` by name), which is what caught `padding` still being live under a payload (D91). The generic-loop rule is audited by construction: `polychain/style.py` contains no style name and no branch per name, and `style_round_trip` re-proves it on all 73 cases. GUI viewport pass owed like the others |

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
2. **Headless image verification is the standing substitute** — cycle 3v's scratchpad rasteriser
   worked and produced a real judgement ("clean 45° miter seam, unbroken outer arris"). Reuse it;
   do not rebuild it.
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

## 1. Scope and non-goals

**Phase 1 (this spec's build target): the 1D kernel** — RailClone L1S parity minus its warts.
**Phase 2 (directional spec only, §7): the 2D array** — built on phase 1, on the buildings
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

## 7. Phase 2 — the 2D array (directional; detail when buildings picks it up)

Architecture: **a stack of chains** — the 2D generator drives N rows through the phase-1 kernel
(RailClone's own model: "A2S is essentially a stack of L1S"). Decided requirements, from
[`railclone.md`](railclone.md) §6:

1. **Cell-role inventory first-class, ~20 roles** (RailClone's RC Slice piece list is the
   enumeration: start/end/default/top/bottom, start-top…end-bottom, x-corner ± top/bottom,
   x/y-evenly ± edges, evenly×evenly and evenly×corner intersections) — fixing RC's biggest wart
   (intersection cells need macros there). Slot = `pc_role` values; no new mechanism.
2. **Whole-building interface:** one closed footprint spline + height; hard vertex ⇒ corner
   column, smooth ⇒ curved facade (attr-driven per §3.1). Adaptive default; never slice a window.
3. **Clipped-area arrays** as the second primitive: closed spline defines *and* trims the fill
   (floors, flat roofs, cladding fields, per-aperture windows), per-sub-spline independent
   arrays, include/exclude nesting.
4. **`pf_polychain_slice` kit ingestion:** model one facade chunk → auto-slice into the cell
   inventory, pieces jigsaw-clipped to the default cell — the artist on-ramp for kits.
5. Consumers: buildings B4 (facade fill) and B6 (corner/seam modules) — B6's gate G2 (L-footprint
   corner closure) doubles as phase 2's acceptance test.

## 8. Build order and effort

PC-G0 → kernel stages §4.1–4.2 (plan visible early) → §4.4 place/deform → §4.3 corners (budget
the most time here) → §4.5 conform → §4.6 finalize/instancing → §5 parm face → starter kit →
gates PC-G1–G4. Phase-1 estimate for a senior TD: **weeks, not months, dominated by §4.3**
(estimate, not measured). Phase 2 only alongside buildings.

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
