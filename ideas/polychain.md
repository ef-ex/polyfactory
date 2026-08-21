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
| Last completed | *(cycle 1 in flight — update on completion)* |
| Next up | §8 build order: §4.1/§4.2 → §4.4 place/deform → §4.3 corners → §4.5 conform → §4.6 finalize/instancing → §5 parm face → starter kit → gates PC-G1–G4 |
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

⚠️ **Known limitation, by design:** flipbook/viewport rendering needs a GUI and will not run under
hython (`tests/README.md`). Overnight verification is therefore **numeric** — headless checks,
baseline diffs, mutation-tested suites. The viewport-judged half of PC-G1/PC-G2 is confirmed with
Hannes at the machine. Never mark a viewport gate passed on numbers alone; mark it
`numerically green, visually unconfirmed`.

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
2. Marker carrier: merged point cloud (§3.1 recommendation) vs separate 5th input — fix before
   the port count freezes (the streets lesson).
3. Kit manifest attr names: reconcile with buildings §12.9 (`moduleRole` vs `pc_role`) — one
   convention, decided with the buildings agent.
4. `pc_cond` dict schema vs a tiny fixed attr set — resolve when the first real conditional
   style is authored; do not over-generalize before then (ponytail).
5. HDA namespacing: `pf::polychain::1.0` vs flat `pf_polychain` — follow whatever the suite's
   first shipped HDA convention is at build time.

---

## 10. Build log

Append one subsection per cycle: what was built, what the reviewers found, what the numbers were,
and every decision taken on an open question. This is the streets convention
([`citygen_streets.md`](citygen_streets.md)) — the doc is the build's memory, so a context loss
costs nothing.

*(cycle 1 in flight — decompose + plan)*
