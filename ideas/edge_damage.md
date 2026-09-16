# Edge Damage — paintable, stylised chipped edges

**Status:** built 2026-09-16 on branch `pf-edge-damage`; 10 mutation-paired checks green
(`tests/hda/run_edge_damage_checks.py`), all 10 mutations seen red. One independent audit has
run (2026-09-16) and every finding it raised is fixed and re-checked — see §6; a **re-audit of
those fixes has not run**, so the honest word is *implemented, self-checked, first audit
addressed*. The paint state itself (a brush stroke landing under the cursor) still has only a
human in the viewport as its oracle — no check reaches it. The viewer state is confirmed to
REGISTER in a fresh session (`hou.ui.isRegisteredViewerState` true), which the first audit
could not verify headless.
**This file owns:** `pf_edge_damage` — what it does, why it is built the way it is, and its
decision log. It does not own rock *formation* ([`rocks.md`](rocks.md), parked) — that is
geology; this is wear on a prop.
**Origin:** Hannes liked Quentin King's free *Paintable Stylized Edge Damage*
(quentinking.com/houdini/edgedamage/) while studying the palette-textured low-poly style of
*8-bitBot*, and asked for it in polyfactory. It shipped as an Indie `.hiplc`, which a
Commercial session cannot load, so it was rebuilt from its network — read over the Indie
session's bridge — on native nodes, to polyfactory's conventions. Same algorithm, no copied
sections.

---

## 1. What it does

Paint where a prop is worn; the tool takes low-poly chips out of its edges and corners there.
Flat faces stay flat. Output is the input with the chips cut in, back in the input's own
transform, with the chip faces in prim group **`pf_chipped`** (for a second material, decals,
or a dark palette swatch).

Three ways to say where: **I Paint It** (the default — select the node, enter the viewer state,
paint), **An Attribute Says** (a 0..1 float point attribute from upstream, default `pf_damage`;
strokes add on top) and **Everywhere**.

### Input contract

The cut is a boolean against a VDB cutter, so the input must be a **closed polygon solid** — an
open mesh makes the boolean return nothing, which is exactly how the first build failed on a
wood block with 16 open edges (0 prims out, silently). The tool now **counts open edges and
non-polygons on the input and errors** with the count and the fix ("Fuse or PolyFill it
first"); *Allow Open Input* downgrades the open case to cut-anyway, and an empty result is
itself an error with the reason. Many 8-bitBot OBJs are open — fuse them first.

The other limit is resolution: features **thinner than `Detail`** cannot be represented by the
remesh/VDB stages, so a plank thinner than `Detail` erodes or the boolean goes unstable. Set
`Detail` (and `Paint Resolution`) finer than the thinnest part you care about; the checks hold
the identity guarantee on a cube and a chunky slab, not on sub-`Detail` planks.

## 2. How — the mechanism, in one sentence each

The whole trick is Quentin's and it is worth understanding, because every parameter is a knob
on one of these lines:

1. `matchsize` the input into the unit cube (transform stashed) so every size is a fraction of
   the object.
2. Brick-`divide` it into a dense canvas and paint `_damage` on that.
3. **`attribblur` on `P`.** This is the damage. Blurring positions pulls every edge and corner
   inward while flat faces stay flat. (⚠️ The first build blurred the *mask* instead and cut
   nothing — the reference node's `attributes` parm is at its default, `P`, which is exactly
   the kind of default a survey of non-default parms does not show.)
4. `remesh`, then `attribnoise` along the normal, then `peak` — roughen the worn edges into
   chips (Chip Depth / Chip Size / Seed) and lift the whole cutter (Damage Bias: higher lifts
   more, so fewer chips).
5. A wrangle returns every **unpainted** vertex to its pre-blur position and pushes it OUT
   along the **original's** face normal (found with `xyzdist`/`prim_normal` against the fitted
   input) by more than the bias, voxels and reduction can bring anything back IN
   (`chipdepth + |bias| + detail*0.5 + 0.05`); the noise only ever adds outward. So the cutter
   clears the original wherever nothing was painted. Two earlier forms failed on a thin plank
   and the audit caught the first: adding to the *blurred* position was ~0.09 short at a
   blurred corner, and pushing along an interpolated *rest normal* went nowhere across a thin
   side, where the top and bottom normals cancel to ~0. A face normal read off the original
   cannot cancel.
6. VDB and back to polygons — a watertight cutter whatever the noise did — then either
   `polyreduce` (Low-poly: sharp irregular facets) or `remesh` (Smooth).
7. `boolean` **intersect**: original AND cutter. The cutter's faces inside the original are the
   chips, and that group ships as `pf_chipped`.
8. `matchsize` restores the transform; `attribdelete`/`groupdelete` strip `_*`.

## 3. Decision log

* **Python survives in one place: the viewer state** (CLAUDE.md rule 2 — UI). A locked asset
  cannot be painted with the inner `attribpaint`'s own state, because that state is entered on
  the node it belongs to. `sidefx_stroke.StrokeState` is SideFX's base class for exactly this:
  subclass it, return the inner canvas from `intersectGeometry`, and let it write strokes into
  the asset's own `stroke_*` parms. The inner `attribpaint` follows through channel links, and
  its per-stroke instance parms through `opmultiparm` — a plain `ch()` cannot express a
  per-instance link. ~40 lines, no HUD, no hotkeys, no menu: the viz switch parm does what the
  reference's radio menu did.
  * ⚠️ **The install/uninstall/module sections must be flagged as Python**
    (`ExtraFileOptions` `<section>/IsPython`, `/IsScript`, and `/IsViewerState` on the three
    viewer-state sections), or Houdini runs `ViewerStateInstall` as HSCRIPT — "Unknown
    command: __import__" — and the state never registers. The audit caught this; it is why the
    build script mirrors attribpaint's own `ExtraFileOptions`, and why registration is now
    asserted (`hou.ui.isRegisteredViewerState`).
* **No stroke caching in v1.** The reference bakes strokes into the paint node's Data parms
  after each stroke so a long session stays fast. On a 0.05-resolution canvas the un-cached
  cook is well under a second; add the cache when a real prop makes it hurt, not before.
* **You paint in the unit cube.** Entering the state shows the canvas in fitted space, so a
  prop at scale 100 jumps to the origin while you paint and comes back when you leave. The
  reference has the same wart. Painting in world space would need the intersection geometry
  restored while the paint node stays fitted — a transform mismatch the stroke projection
  cannot see through. Accepted for v1; recorded so nobody "fixes" it by restoring one side.
* **Mask attribute is `_damage`, group is `pf_chipped`** (conventions.md §1–2). Nothing else
  leaves the node; `run_attrib_checks.py` records the asset with no leaks at any of its 316
  branches.
* **Defaults are the reference's** (chip depth 0.07, size 0.1, bias 0.04, detail 0.2, 13
  blur iterations, low-poly at 10 %) — they render a good cube out of the box, which
  artist_ui.md §6.5 demands. The noise range stays `positive` (outward only) as in the
  reference: the blur does the cutting, the noise only roughens.
* **`Edge Wear` is in canvas cells, so `Paint Resolution` is on the main page, not hidden.**
  The blur distance is `paintres × edgewear` — the audit found `paintres` was the real damage
  knob while sitting in Advanced labelled "canvas density". Both now carry help that says so,
  and `paintres` is capped at 0.2 (above that the flat faces go too).
* **The low-poly reduction has a 200-polygon floor.** As a raw percentage a small cutter
  reduced to nothing and the output was empty (audit); `polyreduce` now targets
  `max(count × pct/100, 200)`.

## 4. Checks, and what they cannot see

`hython tests/hda/run_edge_damage_checks.py` — 10 checks, each paired with the one edit that
reddens it, all 10 seen red: material removed (union ≠ intersect), no strokes → no damage
(inverted push), an upstream *non-default* attribute localises chips (mode ignored), chips ship
as a group inside the solid (group renamed), the transform comes back (restore bypassed), both
styles wired and sound (switch pinned), the seed moves chips (offset unwired), bias trades
chips for surface (bias unwired), an open input is refused with the reason (contract bypassed),
the cutter never reduces to nothing (polygon floor removed). ~3 s plus hython boot.

Blind spots, stated: the **paint state itself** — nothing scripts a brush stroke, so "a stroke
lands where the cursor is" has only a human oracle; how chips **look**; the pass-through noise
menus, cooked at defaults only; the unit-cube **fit** (every fixture is already unit-ish, so a
bypassed fit passes — c5 only proves the transform comes *back*); **`cutn` and the VDB round
trip** (bypassing either still cooks a plausible solid on a cube).

## 5. What the first audit found, and where each fix landed

An independent agent audited `0693df3` and returned eight findings; all are fixed on this
branch and re-checked:

1. **Open/non-poly input cooked to nothing, silently** → `contract`+`warn` error nodes with the
   count and fix, *Allow Open Input* escape, `empty` error node (c9, c10).
2. **Viewer-state sections ran as HSCRIPT** (not flagged Python) → `IsPython`/`IsScript`/
   `IsViewerState` set; registration asserted true in a fresh session.
3. **Reset button threw on the locked inner node** → it only clears the asset's own multiparm.
4. **Push clearance failed on thin/blurred corners** → face-normal push off the original (c2 on
   cube + slab); sub-`Detail` planks declared out of contract (§1).
5. **`Paint Resolution` was the real damage knob but hidden** → promoted to the main page with
   honest help; `Edge Wear` help corrected.
6. **Check blind spots** (bias, open input, cutter floor untested) → c8/c9/c10 added; remaining
   blind spots stated in §4.
7. **Artist face** — help on every visible parm; `stroke_attrib` now defaults to `_damage`.
8. **Doc honesty** — this section, §1's contract, and §3's corrections.

## 6. Next, if wanted

A re-audit of these fixes (Rule 0 — not yet run). Stroke caching (§3); a `pf_damage` float on
the output for shading falloff; painting in world space. None started.
