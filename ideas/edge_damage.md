# Edge Damage — paintable, stylised chipped edges

**Status:** built 2026-09-16 on branch `pf-edge-damage`; 7 mutation-paired checks green
(`tests/hda/run_edge_damage_checks.py`); **not independently audited** (dev-loop Rule 0), so
the honest word is *implemented, self-checked*. The paint state has only been exercised by a
human in the viewport, never by a check — see §4.
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
5. A wrangle pushes every **unpainted** vertex OUT by more than the noise and bias can ever
   pull IN (`chipdepth + |bias| + 0.05`), so the cutter clears the original surface wherever
   nothing was painted. The reference hard-codes 0.1 here; a chip depth above that would have
   cut unpainted surface.
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

## 4. Checks, and what they cannot see

`hython tests/hda/run_edge_damage_checks.py` — 7 checks, each paired with the one edit that
reddens it, all 7 seen red: material removed (union ≠ intersect), no strokes → no damage
(inverted push), an upstream attribute localises chips (mode ignored), chips ship as a group
inside the solid (group renamed), the transform comes back (restore bypassed), both styles are
wired and sound (switch pinned), the seed moves chips (offset unwired). 2.3 s plus hython boot.

Blind spots, stated: the **paint state itself** — nothing scripts a brush stroke, so "a stroke
lands where the cursor is" has only a human oracle; how chips **look**; the pass-through noise
menus, cooked at defaults only.

## 5. Next, if wanted

Stroke caching (§3); a `pf_damage` float on the output for shading falloff; painting in world
space. None started.
