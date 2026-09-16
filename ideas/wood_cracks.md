# Wood Cracks — lens-shaped splits along the grain

**Status:** built 2026-09-16 on branch `pf-edge-damage`; mutation-paired checks in
`tests/hda/run_wood_cracks_checks.py`; tried on the two 8-bitBot props that motivated it
(Hannes' viewport). Not independently audited — *implemented, self-checked*.
**This file owns:** `pf_wood_cracks` — what the reference cracks look like, the cutter design,
the controls, and what is deliberately not attempted. Sibling of [`edge_damage.md`](edge_damage.md)
(same cutter-and-boolean family, same group vocabulary).

## 1. What the reference cracks are

Read off `prop-log.obj` and `tile-wood-panel-v.obj` in `F:\game\8bitbot-extract\data-full`:
thin **lens-shaped slits along the grain**, tapered at both ends, each a handful of triangles.
Two kinds: closed lenses in the middle of a board, and slits at the ends that run out through
the end grain so the tip gapes open. Nothing crosses the grain.

## 2. The design (Hannes chose this over a true split, 2026-09-16)

A cutter-and-boolean tool, like edge damage:

* **fit** into the unit cube (all sizes are fractions of the object);
* **grain** = a chosen axis or the longest bbox axis (right for a log or one board; a panel of
  several boards wants it set explicitly);
* **scatter** one point per crack on the surface, optionally gated by a density attribute (a
  painted mask works);
* **place**: *End Bias* slides that share of the points along the grain onto an end face, so
  the lens straddles the end; a frame with x along the grain projected into the surface, y out
  along N, ± *Angle Jitter*; `scale` = (length, depth, width) with per-crack variance;
* **lens**: an ellipse ring at y = +0.5 (so it pokes above a faceted surface) and a two-point
  ridge at y = −1 tapered to 70 % of the length, **convex-hulled by `shrinkwrap`** — a
  watertight wedge with correct winding for free, no hand-wound faces;
* **one cut per crack, guarded**: a feedback loop over the crack points copies the wedge to
  one point, subtracts it, and **refuses the cut if the volume would halve** — that is a
  boolean that failed, not a crack. Refused cuts are counted in the detail attribute
  **`pf_cracks_skipped`**. Crack walls are remembered across the loop as an attribute (the
  boolean regroups A's faces on every cut), and the three groups are rebuilt exactly at the
  end: `pf_seam` = every edge a crack face shares with an original face.
  *Why:* on the log (9 self-intersection points, out of contract but exactly what game props
  are) one wedge at count 12 / seed 0 made a single boolean of all wedges collapse the log to
  234 floating faces; counts 10, 11 and other seeds were fine. Resolving A's
  self-intersections first (`boolean` *resolve*) never collapsed but always left 20–40 open
  edges — worse. Per crack, the guard refuses that one cut and the log keeps the other eleven.

Output groups, the edge-damage vocabulary: prim **`pf_crack`** (the crack walls), prim
**`pf_original`** (the kept surface), edge **`pf_seam`** (the mouth of every crack — bevel it,
or give it the dark swatch).

**Probed on 22.0.398, each of these cost a red check first:**
* `scatter::2.0` **drops detail attributes** (`detailattribs` is empty by default) — `_grain`
  read off the scatter output was a zero vector and every crack took the fallbacks. `place`
  reads the grain off a second input, the grain node.
* `scatter` outputs `N` only if the input has it, and an interpolated point `N` **tilts near
  edges**. `place` reads the exact face normal instead: scatter's `useprimnumattrib` gives each
  point its source prim (`_sourceprim`), `prim_normal(1, …)` gives the face.
* A **point-class** density attribute ramps across each cell; a **prim-class** one is sharp.
  The Density Attribute help says so.
* On a face whose normal *is* the grain (end grain) the crack runs across it by design.
* A bare `hou.BoundingBox()` is a zero box at the origin — a measurement trap, not the tool's.

**Not attempted:** a physical gape at the ends (PolySplit along the crack and push the halves
apart). The boolean carves into the wood; it cannot open it. Hannes: ship this first, see if the
gape is missed.

## 3. Measured on the props (defaults, 12 cracks)

| | prims in → out | crack faces | seam edges | closed | cuts refused |
|---|---|---|---|---|---|
| log | 486 → 605 | 81 | 237 | yes | 0 |
| planks (grain Z) | 500 → 596 | 67 | 189 | yes | 0 |

(Per-crack cutting, face-normal frames. Note the log's count-12 wedge that collapsed the
all-at-once boolean cuts fine on its own — the failure was the wedges' interaction inside one
boolean, so the guard did not even have to fire here.)

At the defaults the new cracks are subtler than the modelled ones; Width 0.03 / Depth 0.06 are
starting points, not the look.

## 4. Checks, and what they cannot see

Fixture: a closed 2 × 0.3 × 1 board. Seven checks, each with a mutation seen red: cracks
remove material and the mesh stays closed (union); *Cracks* is the number of connected crack
pieces (count unwired); every crack's footprint is longer along the grain than across it, on
the longest-axis default and on an explicit Z (grain pinned); End Bias 1 puts every crack on an
end face, 0 none (bias ignored); the groups partition the output, the seam is non-empty, no
`_*` leaves (cleanup bypassed); a density attribute on the +X half keeps every crack there
(density ignored); zero cracks hands the board back unchanged (a crack cut anyway).

Blind spots: how a crack **looks**; the input contract — a closed polygon solid, exactly as
edge damage — is not checked here; the two props are judged by eye, not by a number.
