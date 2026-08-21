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
| Last completed | **cycle 1 — §4.1 decompose + §4.2 plan**, the `hou`-free kernel. 117 unit tests green, 13 mutations killed. Files under §10 |
| Next up | §8 build order: **§4.4 place/deform** (the Python SOP adapter first — geometry → kernel → plan points), then §4.3 corners → §4.5 conform → §4.6 finalize/instancing → §5 parm face → starter kit → gates PC-G1–G4 |
| Gates | PC-G0 ✅ resolved (§2.3) · PC-G1 ⬜ · PC-G2 ⬜ · PC-G3 ⬜ · PC-G4 ⬜ |

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
