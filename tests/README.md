# polyfactory tests

Two layers. Run the fast one constantly, the slow one before you believe a fix.

```bash
# pure logic — no Houdini, ~0.002s
python tests/unit/test_citygen.py

# geometry — throwaway Houdini session, never saves a .hip
hython tests/citygen/run_scene_checks.py
hython tests/citygen/run_scene_checks.py --update-baseline

# the loop-closure gate, swept over a sep/step ladder — ~1 min / ~20 min
hython tests/citygen/closure_gate.py
hython tests/citygen/closure_gate.py --full --table
```

## Why this exists

Four review passes over CityGen each rewrote the *same* measurements from
scratch — self-intersection counts, the sidewalk-wrap test, degenerate-poly
counts, lot double-coverage — because they lived nowhere. That cost roughly
850k tokens. Every check in `citygen/checks.py` caught a real bug; each one is
now written down so the next pass starts where the last finished.

**A measurement written during a review belongs in `checks.py` afterwards.**
That is the whole point: round N's ad-hoc query becomes round N+1's standing
assertion, and reviews get cheaper instead of repeating themselves.

## Numbers first, renders second

Nearly every real defect was *diagnosed* numerically. Renders showed that
something was wrong; the numbers said what. The arc-fit bug came from counting
degenerate corner segments, the group-name collision from comparing winding
counts, the duplicate lots from prim count vs distinct footprints.

So the scene checks run headless and cheap, and rendering is a separate,
GUI-only step for whatever they flag. Rendering everything is the expensive and
least diagnostic half.

⚠️ The flipbook render path needs a UI and **will not run in hython**. The
offscreen OpenGL ROP was tried and is unreliable on some drivers. Headless
rendering would need husk/Karma and has not been proven here.

## The baseline

`citygen/baseline.json` records every value, not just pass/fail. Several
regressions were only ever visible as *"this number got worse"*: a lot-winding
group collision, a block count that tripled during a failed fix. Bare pass/fail
misses those. The runner diffs against the baseline and prints movement even
where a check still passes — **read that list, and confirm each move is an
improvement before running `--update-baseline`.**

## Layout

```
tests/
  unit/                  pure Python, no Houdini
    test_citygen.py      cross-section profile maths (22 tests)
  citygen/
    checks.py            the assertion library — add to this
    cases.py             scene construction + headless env setup
    run_scene_checks.py  the runner
    baseline.json        recorded values
    closure_gate.py      the loop-closure sweep — harness AND its own checks
```

## The closure sweep, and why it is a file rather than a habit

`closure_gate.py` is the third rule applied to a review that kept repeating itself. The
loop-closure gate has now been swept from scratch and thrown away **three times** — the same
questions each round (how many welds close backwards, how much road a closure lays down twice,
whether the accepted seams leave room for a threshold), at four figures of tokens a round. It
is committed so round four starts where round three finished.

It does not cook an A/B. In the trace wrangle `closeloop` is used in exactly one place —
`if (closeloop) addvertex(0, prim, firstpt)` — so the traced geometry is identical for every
build of the gate, and any candidate gate can be evaluated by exporting the raw inputs once
and recomputing the booleans in Python. That also keeps `hou.HDADefinition.updateFromNode()`
out of the loop entirely: it writes the definition back to its own library file, and it has
already silently overwritten one agent's "pristine baseline" copy mid-comparison.

The transcription is only worth something if it still matches the VEX, so **`gate_matches_vex`
asserts exactly that**, on every street in the sweep, against the wrangle's own `closeloop`
flag. Edit the gate in the HDA and not here and that check fails first and loudest.

Two configs are pinned as `ADVERSARIAL` and always swept. Both need `step ≳ min_street_sep`
so nobody would ship them — and both refute a claim this project had recorded as measured
(`radial 22/30`: a retrograde weld at seam 8.412 against a recorded "0 with seam ≥ 8 m";
`radial 23/20`: a welded loop that crosses itself, against a recorded "0 chord
self-intersections"). A grid that happens to miss its own counterexamples is not a sweep.

`cases.py` sets `POLYFACTORY`, `HOUDINI_VEX_PATH` and `sys.path` itself, because
hython does not load the polyfactory package: without it `#include
<pf_streetgraph.vfl>` cannot resolve and Python SOPs cannot import
`polyfactory.citygen`. The harness found that portability bug on its first run.

## Test the union, and every branch

Two lessons the suite learned the hard way, both worth applying to any check
added from here on.

**The union.** `selfx_junction_surface` cooked Intersection Analysis on the
junction patch alone and reported 0. `selfx_roads` cooked it on the roads alone
and reported 0. Nothing cooked it on the merged city, which carried 102 / 529 /
863 intersection points through four commits. Two green checks, one broken seam,
no signal. If two subsystems have to meet, assert on the merged result —
`selfx_city_merged` is that assertion.

**Every branch.** `lots_params_subdiv_mode` has two settings and the suite only
ever ran mode 0. Mode 1 failed a *committed* check the first time anybody
executed it. Case **D** exists solely to run it. Adding a parameter means adding
a case.

## The cases

| | Input | Why it exists |
|---|---|---|
| **A** `A_drawn` | hand-drawn curves | the artist path; smallest and fastest |
| **B** `B_grid` | grid tensor field | straight streets, 9 blocks |
| **C** `C_radial` | radial tensor field | curved streets — where the seam defects show |
| **D** `D_offset` | A's curves, `subdiv_mode = 1` | the European perimeter block (S8 `offset`) |
| **E** `E_short_t` | a 20 m perpendicular T | the only case that reaches `max_fillet_fraction` |
| **F** `F_bend` | a 90° arterial bend | S3b's curvature clamp at its design amplitude |
| **G** `G_tongue` | a 24 m arm off a four-way | `s5j_params_min_standing_widths` — the tongue |

Three of the seven exist because a mechanism shipped green and unexercised at its
design amplitude — `max_fillet_fraction` (E), the S3b clamp (F), the tongue drop
(G). Adding a parameter means adding a case.

D reuses A's input rather than sweeping the mode over all three: the mode only
changes S8, so a sweep would re-run every street and junction check for no new
information. Whole suite: ~17 s.

## Known-failing at time of writing

Not noise — real, tracked defects, all of them findings in
`ideas/citygen_streets.md` §4e. **Do not `--update-baseline` these away.**

| Case | Check | Value | Finding |
|---|---|---|---|
| A B C D | `selfx_city_merged` | 102 / 529 / 863 / 86 | 4e-1 — roads and junction patches interpenetrate at every junction |
| A B C D | `trim_metric_is_consistent` | max 0.30 / 2.75 / 3.34 / 0.30 m | 4e-1 root cause — `s5j_solve` cuts by axial distance, `s5j_trim` by arc length |
| B C | `every_mouth_has_a_road` | 2 / 1 | 4e-3 — `pfsj_fillet` has no radius clamp, `s5j_trim` deletes the street, the mouth stays |
| C | `no_sweep_fold_after_trim` | ratio 3.21, 2 folds | 4e-7 — the CAUSE of C's `no_downward_faces`: 0.022 m segments under a 7.2 m half-width |
| C | `no_downward_faces` | 4 | 4e-7 symptom of the above |
| C | `selfx_roads` | 12 | 4e-8 — two degree-1 streets 6.7 m apart driving through each other |
| C | `plaza_disc_is_clear` | 10,363 of 11,310 m² built over, 2.45 m gap | 4e-2 — the plaza ring is emitted correctly and deleted before it ships |
| A B C | `lot_aspect_ratio` | max 10.6 / 31.5 / 25.6 | 4e-4 — ribbons, not rectangles; S8 names the test and never implemented it |
| B C D | `lots_are_simple_polygons` | 24 / 47 / 1 | 4e-5 — Sutherland–Hodgman bowties on non-convex blocks |
| D | `lots_tile_blocks` | 0.0061 | 4e-6 — `offset` mode resamples the contour and chords across block vertices |

`no_scratch_attribs_lots` was on this list at 27 / 28 / 28 / 27 and is **fixed**
(4e-10). `lots_normal` now deletes the seven blocks-branch duplicates and a
`lots_publish` node drops `Cd` on the published branch only — the city keeps the
green/red viability colour. ⚠️ An allow-list only detects EXTRA attributes, never
MISSING ones: `LOT_PRIM_ATTRS` still promises `layer`, which the lots output has
never shipped. Ship it or drop it from the list; the check cannot tell you.

Passing, and that is the point — each has been shown to fail under fault
injection or on another case, so none of them is decoration:

- `every_corner_is_an_arc` now fits a circle to every corner. Its three new
  terms were verified by perturbing a detached copy of the patch geometry: one
  point moved 5 cm trips `fit`; the arc grown 0.5 m trips `radius` while `fit`
  stays at baseline; the arc *translated* 7 cm trips `tangent` alone, invisible
  to both others. It also reports `mixed_class`, which is 100% everywhere —
  4e-3's arbitrary corner radius, recorded rather than asserted because the
  design doc names no tie-break rule.
- `no_sweep_fold_after_trim` passes on B despite 0.25 m segments, because they
  are straight. Short *and* turning is the failure; short alone is not.
