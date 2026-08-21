# polyKnit — 3D Knitted Garment System — Design Spec

**Status:** design complete, implementation NOT started. Created 2026-08-16.
**Owner of this doc:** vision + architecture + implementation plan. The literature, tool landscape
and all verification ledgers live in `polyfactory/resources/fabric/README.md` (gitignored, local
only — 21 sections, referenced below as **KB §n**). This spec stands alone for *what to build*;
read the KB for *why* and for every citation.

---

## 0. Agent onboarding — read before implementing anything

1. Read `polyfactory/resources/fabric/README.md` first (KB). If it is missing, STOP — you are on
   a machine without the local knowledge base; ask before proceeding.
2. Houdini work follows `houdini_get_skill("houdini-dev-loop")` — reference-first, live-session
   probing, and **nothing is "done" until independently audited on the current build**. Also read
   `houdini-procedural-modeling` (SOP work) and `houdini-tool-design` (before exposing parameters).
3. **Show, don't tell** (memory: citygen-show-dont-tell): every milestone's acceptance is a visual
   repro in the Houdini viewport or a Karma render next to its reference — not a passing assert.
4. Scale: 1 unit = 1 m (matches Fibric's convention and Houdini defaults). Yarn radius in meters
   (typical worsted ≈ 0.001–0.002 m).
5. Do not widen scope. Milestones are ordered by dependency; finish and audit one before the next.
6. [`artist_ui.md`](artist_ui.md) §6b (2026-08-21) audits this spec against the parameter-surface
   evidence — the panel/seam/chart workflow is the *author* tier; a garment-preset front door for
   non-knitter artists is the missing consumer tier (post-M7). Read it before exposing parameters.

## 1. Goal

A Houdini toolset (polyfactory HDA family, working name **polyKnit**) that generates **actual
knitted yarn geometry** for garments — realistic loop structure, patterns, seams — rendered with
fiber-quality shading in Karma, animated via ordinary cloth sim. Hero-close-up capable.

**Non-goals** (explicit, from KB):
- Machine knittability / fabrication (KB §4.4, §9) — never a constraint.
- A yarn-level *solver* — animation comes from Vellum on the stitch mesh; yarn attaches late
  (KB §4.5, the production pattern).
- Colourwork floats (Fair Isle reverse-side strands) — deferred, documented open edge (KB §16.4).
- Woven fabrics — knit first; the architecture doesn't preclude weaves (templates differ), but no
  weave work in v1.

## 2. Architecture (KB §14.3, validated by rtstitch — KB §21.2)

```
authoring (SOPs, cached)                          │ render time (Hydra 2, per frame)
                                                  │
panels/cage ─▶ STITCH MESH ─▶ relax ─▶ Vellum sim ─▶ hdGp procedural ─▶ yarn curves ─▶ Karma Hair/Fur
              (1 face = 1 stitch,     (rest shape)  (the ONLY thing   (knot interp +
               stitch type = attr)                   on the stage)     template fit)
```

Load-bearing decisions, each argued in the KB:
- **The stitch mesh is the product of the SOP side and the only geometry on the USD stage.**
  Yarn curves never exist in the hip file except for preview. (KB §14.3)
- **Yarn generation is a Hydra 2 generative procedural** (`HdGpGenerativeProcedural`, H22 native,
  delegate-agnostic). Karma VK viewport does not resolve procedurals — preview path required
  (§6.7). (KB §14.1)
- **Deformation model: knot-based, from rtstitch** (KB §21.2): knots interpolate from the deformed
  mesh; control points fit to templates by angle+length energies. Phase 1 may ship static template
  placement (MADYPG-style strain lookup optional); knot optimization is the phase 2 upgrade.
- **Shading: Karma Hair VOP / Fur VOP terminals on curves** (Chiang model, XPU-supported).
  No custom BSDF — XPU wall, KB §13.2.

## 3. Data model

### 3.1 Stitch mesh schema (SOP geometry, and its USD mirror)

Quad-dominant mesh, pentagons at inc/dec, one face = one stitch.

| Class | Attr | Type | Meaning |
|---|---|---|---|
| prim | `stitch` | string | stitch type id: `k`, `p`, `y`, `d12`, `d21`, `kp`, `c4f`, `c4b`, `cast) on`, `bindoff`, `rowend` … (§3.2 registry) |
| prim | `row`, `col` | int | course/wale indices within panel (chart addressing) |
| prim | `panel` | int | panel id |
| prim | `flip` | int | wale direction flip (0/1) |
| prim | `aspect` | float | stitch height/width ratio override (default from detail) |
| vertex | (ordering) | — | **convention: vtx 0→1 = bottom course edge, 1→2 = right wale, 2→3 = top course, 3→0 = left wale.** Pentagons: documented per type in the registry. This ordering IS the orientation encoding — no separate edge attrs needed in the common case. |
| edge grp | `seam_<id>` | — | boundary edges participating in seam `<id>` |
| detail | `stitch_size` | float | course width in meters |
| detail | `yarn_radius` | float | |
| detail | `aspect` | float | global stitch height/width (default ≈ 0.75 — stitches are wider than tall, KB §15.7; NEVER assume square) |

Seam metadata (detail dict or companion prims): per seam id — partner curves, mismatch type
(`join`, `split`, `perp_expand`, `perp_contract` — KB §17.2), yarn variant (`extra` | `continue`),
pick-up ratio (e.g. 3:4).

### 3.2 Stitch template library (ours, versioned in repo)

Per stitch type, in face-local UV space (unit square, wale = +v):
- yarn segments as ordered control polylines with **knot markers** (contact points, per rtstitch's
  representation: center + contacts + ±normal offsets — KB §21.2),
- entry/exit points pinned to wale edges, loop top/bottom pinned to course edges,
- metadata: symmetric flag, mirror-of, aspect sensitivity.

Format: JSON, one file per stitch type, in `polyfactory/knit_templates/` (repo-tracked — this is
our IP, authored by us). Loader in Python + C++ (procedural). Design inspired by CMU's `.sf`
concept (KB §21.1-B) but implemented from scratch — **do not copy CMU code** (unlicensed).

**Template sources for authoring/validation** (local, KB §21.1): fit against
`resources/fabric/models/yuksel/*.bcc` (relaxed ground truth; research-use license — reference
only, never ship the data) and MADYPG's MIT-licensed `data/yarnmodels` + `.pyp` pattern files
(`resources/fabric/data/madypg/` — MIT: reuse allowed, attribute in credits).

Initial registry (v1): `k`, `p`, `y`, `d12`, `d21`, `kp`, `caston`, `bindoff`, `rowend`,
`c4f`/`c4b` (cable pair). That is 11 templates; each is a handful of control points (KB §21.2.2).

### 3.3 File readers (small, pure Python)

- **BCC reader** (`bcc.py`): 64-byte header, magic `BCCD`; verified locally (KB §21.1-A). Curve
  count sign encodes closed loops. Spec: cemyuksel.com/cyCodeBase docs. → Houdini polylines with
  `width`.
- **`.pyp` reader** for MADYPG patterns (format documented in that repo).
- Optional later: `.smobj`/`.yarns` readers implemented from the published format description
  (formats are not copyrightable; KB §21.1-B) — unlocks CMU example data locally.

## 4. Milestones

Ordered by dependency. Each ends with an **independent audit** (dev-loop rule) and a visual
deliverable. Estimates assume one focused agent session each unless noted.

### M0 — Look test (GO/NO-GO gate)
Build: `bcc.py` reader → load `flame_ribbing_pattern.bcc` (49,745 pts, 1 closed curve) → width
attr → Karma XPU, Hair VOP terminal, close-up + mid shot, HDRI.
**Accept:** side-by-side with the photo on Yuksel's yarnmodels page and KB §21 references — reads
as knit wool (fiber sheen, loop legibility). If it reads as plastic tubes after honest lookdev
effort, STOP and reassess shading plan before any topology work.

### M1 — Swatch generator (flat, no shaping)
`polyknit_swatch` SOP: rows × cols grid stitch mesh per §3.1 schema; `stitch` attr via preset
(stockinette / garter / 1x1 rib / 2x2 rib / moss) or paint (Attribute Paint) or chart image
(COPs sample, pixel→stitch id — KB §16.6); SOP-side yarn preview: template placement per face
(no deformation, no relaxation) at `stitch_size` scale.
**Accept:** the five presets' yarn topology matches reference photos of those structures
(knit/purl fronts distinguishable); chart-image input reproduces a pixel-art pattern.

### M2 — Templates fitted + rest-shape relaxation
Author the 11 v1 templates (§3.2), fitting loop shapes against Yuksel BCC tiles. Rest shape:
Vellum-based yarn relax on small swatches (bend + collision on yarn curves, pin panel border) to
bake *relaxed* templates and per-pattern aspect. Optional stretch goal: Hwang-2025-style
neighbor kernels (KB §7.6) — only if simple baking visibly fails on knit/purl mixes.
**Accept:** stockinette swatch edge-curls; 2x2 rib rest width contracts vs stockinette of equal
stitch count (measure in viewport); garter lies flat. Compare against KnitDB photos (KB §21.1).

### M3 — Panels + shaping
`polyknit_panel` SOP implementing KB §18.1 mechanics with the UV-seam front end (KB §19):
input mesh with UVs → seams to curves → user pairs opposite boundaries (course vs wale) →
per-edge tessellation nᵢ (auto from `stitch_size`, editable) → row-count interpolation emits
inc/dec faces at marked wale columns (fashioning lines).
**Accept:** a tapered sleeve panel: straight columns, visible paired decrease lines, no square
stitches (aspect respected); stitch counts per row printed and correct.

### M4 — Seams
`polyknit_seam` SOP: select two seam curve sets (or one closed loop for pick-up), choose mismatch
type (KB §17.2 four-type taxonomy) + yarn variant + pick-up ratio; emits the connection faces
(extruded rows per the 2019 constructions) into the stitch mesh.
**Accept:** (a) shoulder join with three-needle-bind-off geometry; (b) sleeve picked up around an
armhole (perpendicular type, 3:4 ratio) — yarn continuity check passes: every loop is held by a
neighbor or a bind-off (topological unravel test, scripted).

### M5 — Pattern language
KnitSpeak-subset parser (Python SOP): `k`/`p`/`yo`/`k2tog`/`ssk`/`c4f`/`c4b`, `*…* to end`
repeats, row lists → writes `stitch` per `row`/`col`. Walker-chart symbol map for image charts.
**Accept:** the flame ribbing chart from KB §16.2 (2012 paper Fig. 14 source) reproduces the
paper's stitch mesh pattern; a cable chart produces correct crossings.

### M6 — Hydra generative procedural
C++ `HdGpGenerativeProcedural` (H22 SDK, link Houdini's USD): input = stitch mesh prim (+ template
lib path + yarn params); output = `BasisCurves` per yarn with widths; deformation = knot
interpolation from face frames + template fit (rtstitch phase 1: direct placement; phase 2:
Gauss-Newton energies — KB §21.2). Bind Karma Hair/Fur material. Registration pattern: copy the
H22 Scatter Instances LOP precedent (KB §14.1). Preview path for VK viewport: a `polyknit_preview`
SOP doing the same expansion CPU-side at reduced density.
**Accept:** M2 swatch on an animated Vellum flag renders in Karma XPU with yarn following
deformation; loops visibly tighten under stretch in phase 2; husk render works headless;
`--disable-hydra-generative-procedurals` cleanly degrades to stitch mesh.

### M7 — Hero garment demo
Full sweater: front/back/sleeve panels (M3) + seams (M4) + rib cuffs/hem and a cable front (M5),
Vellum-simmed on a character, M6 procedural, Karma XPU.
**Accept:** side-by-side vs `alien_sweater_cables.bcc` render and a real sweater photo; a
turntable + stretch shot. This is the ship-quality bar.

**Verify-first items** (do during M0, they gate nothing before M6): H22 "SOPs at render time"
claim (would let M6 be SOP-authored — KB §14.1); Fibric trial (competitive check — KB §2.6).

## 5. Component summary

| Asset | Kind | Milestone |
|---|---|---|
| `bcc.py`, `pyp.py` readers | python module | M0/M2 |
| `polyknit_swatch` | SOP HDA | M1 |
| template library + fitter | JSON + python | M2 |
| `polyknit_panel` | SOP HDA | M3 |
| `polyknit_seam` | SOP HDA | M4 |
| `polyknit_pattern` (parser+chart) | SOP HDA | M5 |
| `polyknit_yarn_procedural` | hdGp C++ plugin | M6 |
| `polyknit_preview` | SOP HDA | M6 |
| yarn material presets | MtlX/VOP | M0, refined M7 |

## 6. Constraints & risks (from KB, with section refs)

1. **Licensing:** Yuksel models = research-use reference only (§21.1-A); CMU repos unlicensed —
   formats reimplementable, code and data not to be copied/shipped (§21.1-B); MADYPG/HYLC = MIT,
   reusable with attribution; Cirio/Seddi yarn-sim patents (§6.2) — irrelevant unless we ship a
   yarn *solver*, which we don't.
2. **Karma XPU has no custom BSDFs** (§13.2) — shading stays within Hair/Fur/MaterialX. Accepted.
3. **VK viewport won't resolve procedurals** (§14.1) — preview SOP is mandatory, not optional.
4. **Square-stitch trap** (§15.7): aspect is a first-class parameter everywhere from M1 on.
5. **No MIP solver needed** on this path — panels are authored, not derived (§15.6). If
   arbitrary-mesh input is ever demanded: evaluate autoknit's field-tracing before Wu 2018's MIP
   (§18.2).
6. **rtstitch has no code release** (§21.2) — knot construction implemented from the paper's
   Eq. 1–2; energies are two lines.

## 7. What done looks like

The M7 demo renders a hero-close-up sweater in Karma XPU where: individual stitches are legible
geometry (knit vs purl vs cable), the silhouette is lumpy with real loops, seams show correct
join structures, stretching tightens loops, and the whole thing was authored from panels + a
chart in under an hour of artist time. Audited, per dev-loop, by an agent that did not build it.
