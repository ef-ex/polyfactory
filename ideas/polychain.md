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
| Last completed | **cycle 2c** — independent verification of cycle 2/2b by an agent that wrote none of it. Every suite re-run from scratch: **19 cases / 540 values (474 pass, 66 skip) / 0 failing**, **0 moved baseline values**, and **138 polyChain unit tests / 8 700 subtests** in 0.62 s. Five fresh mutations, **5 killed** — but two of them died narrowly and named two coverage defects (§10 "Cycle 2c"). citygen: no regression, proven twice. ⚠️ **Visual confirmation still none** — the live bridge wedged on the first `houdini_render_view` and `/obj/polychain_gate` could not be deleted; see §10 |
| Next up | §8 build order: **§4.3 corners** (bend/miter, the budgeted-hard stage — nothing places a `corner` slot yet), then §4.5 conform → §4.6 finalize/instancing (partly landed: packed-vs-deformed segregation and slice caps are in) → §5 parm face + the §3.3 style-payload reader → gates PC-G1–G4. Deferred and named so it is not forgotten: **§4.4's flatten-under** (see §10 Cycle 2b's not-built list — PC-G2 will see a 0.49 m riser gap under every stepped piece, by design for now) | Also open, raised by cycle 2c and cheap: **a check that every planned `pc_elem_id` resolves to a built prim** (`exact_fill_m`/`max_gap_m`/`axis_on_curve_m` fail OPEN on a lookup miss), and **`/obj/polychain_gate` may still be sitting in Hannes' GUI session** — delete it before the next live pass |
| Gates | PC-G0 ✅ resolved (§2.3) · PC-G1 ⬜ · PC-G2 ⬜ · PC-G3 ⬜ · PC-G4 ⬜ — none of them can pass yet (§4.3 corners and the §5 parm face are unbuilt), and **every polyChain number to date is headless**: cycle 2c tried the live bridge and it wedged, so nothing has been LOOKED at |

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
