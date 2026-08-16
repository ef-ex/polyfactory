# polyfactory tests

Two layers. Run the fast one constantly, the slow one before you believe a fix.

```bash
# pure logic — no Houdini, ~0.002s
python tests/unit/test_citygen.py
python tests/unit/test_plan.py            # the S5 planner, ~0.02s

# re-measure what the builder's plates actually consume (rewrites the fixture
# tests/unit/test_plan.py calibrates against)
hython tests/citygen/dump_trims.py

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
    test_plan.py         the S5 planner + its calibration (43 tests)
    trim_calibration.json  measured junction footprints, 539 arms
  citygen/
    checks.py            the assertion library — add to this
    cases.py             scene construction + headless env setup
    run_scene_checks.py  the runner
    baseline.json        recorded values
    dump_trims.py        writes trim_calibration.json from the live solve
    closure_gate.py      the loop-closure sweep — harness AND its own checks
```

## The planner's calibration is a baseline too

`plan.crossing_trims` predicts what a junction cuts off each arm without cooking
anything, so `standing` is checkable before the geometry exists (§11.4). It is
only worth something if it agrees with the plates the builder really lays down,
so `dump_trims.py` exports `trim_start` / `trim_end` from
`junction_solve/s5j_solve` on all fifteen cases and `test_plan.py` asserts the
model against every one of the 539 arms.

The residual is **pinned per case, not tolerated globally**: exact (≤ 3.4e-5 m)
on the nine cases whose arms are straight, and up to 4.58 m either way on the six
with curved ones, because `s5j_solve` re-solves each corner in the frame at its
own cut and the planner has no arm shape to do that with. Read those numbers as a
recorded state, the same way `baseline.json` is read.

⚠️ **But the metre is not the property, and the M1 audit caught this file
implying it was.** What the planner is FOR is the answer — does this street still
stand? Over all 318 edges the planner's `standing > 0` verdict never disagrees
with the builder's: **0 false-OK, 0 false-BAD**. That is asserted directly, and
it is the assertion to keep green. The per-case residuals are a tripwire on the
model drifting, not a safety margin — treating them as one is how a 5.88 m
optimistic error got recorded as a 2.02 m bound.

## The node schema, and why a closed vocabulary is not enough

`junction_schema` (M3) watches §11.3's `junction_type` / `principal_edges` on
the graph's `is_node` points. `JUNCTION_TYPE_VOCAB` is the closed set, and it is
only the FIRST of four terms — `LOT_REJECT_VOCAB`'s lesson was that membership
cannot detect an auditor relabelling every rejection to one member of the set.
The other three tie each value to something independently measurable: a junction
of degree >= 3 with no type (the shape of a silently-bypassed adapter), a type on
a node where `s5j_solve` builds no plate, and a `principal_edges` that is not two
`edge_id`s both incident to that node.

Eight injections were shown to fail it — and three of them only after an audit
found them passing: adapter bypassed, a value outside the vocabulary, a type on
a degree-1 node, a principal naming a stranger, a principal naming only one
edge, **a principal naming the SAME edge twice** (a pair that is one street),
**a principal on a dead end** (only `junction_type` had been degree-paired), and
**`is_node` destroyed** — where every term read 0 because the loop never ran,
the same vacuity that let three checks go green on an EMPTY graph in 2026-08-15.

## And a second check, because the first one's blind spot had already bitten

`node_schema_stays_on_the_graph` exists because M3 shipped a FIX with no
detector. The adapter leaked `junction_type` / `principal_edges` onto all 5568
city points; that was found by probing outputs by hand, and after the fix
nothing could have told you if it came back. Measured on frozen geometry with
the leak restored: `no_scratch_attribs_city` **PASS 0** (it is called with
`None, None` — city POINT attributes are deliberately unpoliced) and
`attribute_schema` **PASS 0** (it counts only MISSING attributes). Clearing
`out_detailclean`'s `ptdel` left the entire suite green.

**Four terms**, and it started with two — each of the others was added because
an audit injection walked past what was there:

* `leaked` — absent from city / blocks / lots on points, VERTICES, prims and
  detail, and from the graph on everything but points. Vertex is in that list
  because `out_detailclean` had the identical hole (`dovtxdel on`, `vtxdel ""`).
* `off_node` — on the graph, a non-empty value of EITHER attribute may sit only
  on an `is_node` point. Testing `junction_type` alone was not enough:
  `principal_edges` on all 497 shape points left both checks green.
* `untyped_plated` — any point with 3+ incident prims that is not a typed node.
  Both checks select by `is_node`, the same attribute the adapter selects by, so
  a cleared `is_node` hid a junction from everything at once while `s5j_solve`
  — which reads `len(pointprims) >= 3` and never `is_node` — still plated it.
* `schema_source` — which definition of the attribute name set was used. The
  shared constant was inert for a whole round because the import path was wrong,
  and a value-identical fallback hid it; now a fallback moves a baseline number.

⚠️ A wrong-TYPE value is a red row, never an exception. `i@principal_edges`
instead of `s@` used to raise out of `run_case` and lose **all 15 cases** with no
JSON and no baseline compare — while a mistyped `junction_type` was already
handled gracefully, which was the tell.

⚠️ **A/B-ing an HDA change needs a guard, or it lies.** With `HOUDINI_PATH`
set the way the gate sets it, Houdini auto-scans `polyfactory/otls` at startup
and those definitions WIN over an explicit `hou.hda.installFile` of a HEAD copy
— so a before/after comparison silently cooks the working-tree asset twice and
comes back byte-identical, md5 and all. Print and assert the library file path
and the node's presence before cooking anything.

⚠️ It deliberately does NOT assert WHICH type a node carries. `junction_type`
is artist-authorable, so "junction everywhere" is a legal state and a check that
forbade it would be asserting taste. Today's choice is pinned by the recorded
`types` histogram in `baseline.json` instead — M4 flipping the computed default
moves that number where anyone can see it.

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
`selfx_city_merged` is that assertion. (What it turned out to be measuring is an
unbuilt feature rather than a broken one — see the note under *Known-failing* —
but that is the point: nothing else could see the seam at all.)

**Every branch.** `lots_params_subdiv_mode` has two settings and the suite only
ever ran mode 0. Mode 1 failed a *committed* check the first time anybody
executed it. Case **D** exists solely to run it. Adding a parameter means adding
a case.

## The cases

| | Input | Why it exists |
|---|---|---|
| **A** `A_drawn` | hand-drawn curves | the artist path; smallest and fastest |
| **B** `B_grid` | grid tensor field | straight streets, 17 blocks |
| **C** `C_radial` | radial tensor field | curved streets — where the seam defects show |
| **D** `D_offset` | A's curves, `subdiv_mode = 1` | the European perimeter block (S8 `offset`) |
| **E** `E_short_t` | a 20 m perpendicular T | the only case that reaches `max_fillet_fraction` |
| **F** `F_bend` | a 90° arterial bend | S3b's curvature clamp at its design amplitude |
| **G** `G_tongue` | a 24 m arm off a four-way | `s5j_params_min_standing_widths` — the tongue |
| **H** `H_offset_strict` | D's input, `max_aspect` 1.9 | the only case that notices the courtyard rung-skip regressing |
| **I** `I_offset_radial` | C's field, `subdiv_mode = 1` | `offset` on block shapes that are NOT A's — expected red on `lots_are_simple_polygons` |
| **J** `J_five_star` | a hand-drawn 5-way star | the first case that EXECUTES the S5a realign |
| **K** `K_stub_triangle` | a 3-cycle of 32 m jogs | the case the repair gate REFUSES — six red rows, one defect |
| **M** `M_shallow_y_24` | a 24° leg, just under the floor | `graph_min_angle` deletes the LEG — 1 in pass 0 |
| **N** `N_shallow_y_32` | a 32° leg, over the floor | the control: nothing deleted, and the junction is still broken |
| **O** `O_shallow_y_host_dies` | 22°, but the leg is LONGER than the host's east half | the other branch: `graph_min_angle` takes the **host's own arterial**, published as a 599.77 m survivor |
| **P** `P_stub_chain` | four junctions on three 30 m links | the flood fill PAST a 3-cycle; 3 edges of 9 ship |

⚠️ **This table listed seven cases while the suite ran eleven** — found by the M1
audit, 2026-08-15, alongside a stale block count for B. Two of the four missing
ones — J and K — are the only cases that carry the S5a junction work at all, so a
reader looking for them found nothing. Whole suite: **fifteen**.

Five of the fifteen exist because a mechanism shipped green and unexercised at
its design amplitude — `max_fillet_fraction` (E), the S3b clamp (F), the tongue
drop (G), the realign (J) and its refusal (K). Adding a parameter means adding a
case.

**M–P are M2, and they are CASES BEFORE MECHANISM.** They document what today's
build does with a shallow approach and with a stub cluster larger than a
triangle — the two things §11.5's `merge` type and §11.8's spread exist to
resolve. Their value is that they are red, and specifically red in a way that
will go green for a *reason* when M5 lands. A family added after its fix could
never show the fix changed anything.

⚠️ **AND THE FIRST VERSION OF L / M / O PUBLISHED AN EMPTY GRAPH** — city 0,
edges 0 — while the suite reported three tidy red rows. §11.11's own warning,
arriving on schedule: *read `counts` before believing any green*. The cause was
a chain of two by-design mechanisms, not a bug: `graph_min_angle` removes the
shallow leg, the Y node drops to degree 2, the component now holds no junction
at all, and `graph_drop_orphans` correctly deletes the whole thing. A host with
one leg is one deletion away from nothing. Each shallow-Y now carries a second,
plain T 300 m west whose only job is to keep the component alive so the case
measures the ANGLE rather than the orphan filter.

D reuses A's input rather than sweeping the mode over all three: the mode only
changes S8, so a sweep would re-run every street and junction check for no new
information. Whole suite: ~17 s.

## Known-failing — re-measured 2026-08-15, 20 rows

Not noise — real, tracked defects, most of them findings in
`ideas/citygen_streets.md` §4e. **Do not `--update-baseline` these away.**

⚠️ **THIS TABLE HAD DRIFTED OUT OF DATE AND WAS POINTING THE NEXT READER AT
PHANTOMS.** Found during the M1 audit, 2026-08-15: it listed six checks that
pass on today's build (`trim_metric_is_consistent`, `no_sweep_fold_after_trim`,
`no_downward_faces`, `selfx_roads`, `lot_aspect_ratio`, `lots_tile_blocks`),
attributed rows to the wrong cases, and omitted the six K_stub_triangle rows
that are the honest form of an unrepaired jog. Rebuilt below from a gate run
rather than edited. Why the six went green is **not recorded anywhere** and this
table is not the place to guess — treat their §4e findings as unverified rather
than closed. A stale known-failing list is worse than none: it makes a real
regression look expected.

| Case | Check | Value | Finding |
|---|---|---|---|
| A B C D F G H I J K | `selfx_city_merged` | 9 / 101 / 127 / 9 / 2 / 6 / 9 / 127 / 6 / 87 | **NOT A DEFECT — it measures a declared v1 non-goal.** See below. |

⚠️ **`selfx_city_merged` is the standing measure of an unbuilt feature, and reading it as
breakage wasted a review round.** Diagnosed in the viewport 2026-08-15. At every crossing site
the incident prims are a road band at y = 0.15 with its kerb riser, and the junction plate at
y = 0 — the street's raised elements arrive at the junction still at their own height, because a
street is swept as ONE ribbon and nothing brings the section down at the seam. Per-segment
cross-section transitions are an **explicit §10 non-goal for v1**; the approach when it is built
is the Wang-tile segmentation recorded in `citygen_streets.md` §9. So this number is a progress
bar on a feature, not a fault to trim away: it goes to zero when the end pieces exist and not
before. **Do not chase it with thresholds.** Keep it recorded — it is the only thing that will
tell you the transition work is actually landing.

| C I | `plaza_disc_is_clear` | 8,364 of 11,310 m² built over, −1.14 m gap | 4e-2 — the plaza ring is emitted correctly and deleted before it ships |
| I | `lots_are_simple_polygons` | 1 lot, 1 viable | 4e-5 — Sutherland–Hodgman bowties on non-convex blocks; I exists to reach the 96% of block rings D and H are not |
| I | `every_block_is_subdivided` | 1 empty of 28, at (21.31, 33.04) | S8 on a radial block I's `offset` mode cannot fill |
| K | `trim_leaves_road_standing` | min_standing **−13.434 m**, ratio −0.933, 3 under | §S5a — the stub triangle's plates overlap. **This is the number §11.4's planner reproduces.** |
| K | `selfx_junction_surface` | 50 | same cause: three crossing plates 42 m across on 32 m gaps |
| K | `every_mouth_has_a_road` | 6 of 11 | the streets those plates ate |
| K | `block_boundary_closes` | 6 open loops, 12 unpaired ends | the kerb cannot close around an overlapped junction |
| K | `lots_clear_of_junctions` | 54.2 m² over 8 junctions | lots on the overlap |
| K | `lots_clear_of_roads` | 54.2 m², worst edge 56.3 m at (15.74, 12.92) | same |

K's six rows are one defect, not six, and they are what M4/M5/M6 exist to
close. They are the honest form of a jog the repair loop refuses to collapse —
see `cases.py`'s note on K and §S5a.

**M2 added four cases and six rows, 20 → 26.** Three of the six are the declared
v1 non-goal already recorded on ten other cases; the other three are defects the
build had and nothing could see:

| Case | Check | Value | Finding |
|---|---|---|---|
| M O N | `selfx_city_merged` | 4 / 5 / 6 | the v1 non-goal again, see above — **not** new information. N is highest because it keeps its leg, so it has one more junction seam |
| N | `block_boundary_closes` | 1 open loop, 2 unpaired ends at (0.000, ±13.400) | ⚠️ ONE defect with the row below, and it is **not** the missing merge — see the trim-under-a-step gap |
| N | `trim_metric_is_consistent` | max **4.00 m** at (−4.0, 0.0), 1 end over 0.05 | the only case with an end OVER the 0.05 m threshold; B/C/I sit at 0.0001 |
| P | `connections_are_never_refused` | `graph_stub_kill` **3** pass 0 (by design), `graph_drop_orphans` **2 late** | §S5a item 5, reproduced exactly — and by the specified mechanism: `cluster 4, narm 6, ok 1` measured live. Collapse a wide cluster, let the realign work on what it makes, and two components fall off — **3 edges of 9 ship** |

⚠️ **N's TWO ROWS ARE ONE DEFECT, IT LIVES IN `s5j_trim`, AND THE TRIGGER IS NOT
"TRIM == 0".** This table first blamed the missing merge, then blamed a zero
trim; both were wrong, and the second one matters because the fix it implied
would not have worked. `s5j_trim` deletes a junction's shared point
unconditionally (*"a shared junction point belongs to several edges; only ever
delete it"*), and the surviving last point is only moved to the cut by
`if (de < te)`. **The predicate is in that line and it is not a constant**:
`de` is the arm's own TERMINAL SEGMENT, which `s5_resample` sets to
`L / ceil(L / step)` — bounded by `(step/2, step]`, so a 2.00 m floor in
principle, and measured **3.5832 .. 4.0000 m** across the 539 junction-side ends
of the suite, equal to 4.00 only on the 22 ends whose arm length is an exact
multiple of the step. So the endpoint is re-created only when
**`trim > de`**, and the hole is **`de − trim`**. ⚠️ Two earlier versions of this
paragraph said "when the trim is non-zero" and then "when `trim > 4.00 m`";
4.00 m is the resample CAP, not the threshold, and writing the fix as
`if (te < 4.0)` would detach it from the geometry it was measured on — and break
outright the day anyone changes Max Segment Length. Swept live on the shallow-Y
rig, where `de` happens to be 4.000:

| leg angle | junction-side `trim_end` | gap |
|---|---|---|
| 25.5–45° | 0.0000 | **4.000 m** |
| 50° | 1.4107 | **2.589 m** |
| 55° | 2.9575 | **1.043 m** |
| 60° and up | 4.4454+ | 0.000 |

**A non-zero trim of 1.41 m still leaves a 2.59 m hole.** Anyone who "fixes"
this by snapping when the trim is zero gets a green gate — the corpus contains
no arm with a trim strictly between 0 and 4 — and leaves the defect live for
every arm in that band. Four arms already sit at 4.35–5.00 m, **0.35 m** from
the trigger.

⚠️ And the generalisation was wrong three times. It is **not** "every junction
with one wide arm pair": of **539 arms** exactly **one** has a junction-side trim
≤ 4 m, and **87 of the 88 junctions with two or more arterial arms do not exhibit
it** — `G_tongue` is two collinear arterials plus a third and trims 22.4 all
round. Nor is it "the arm opposite a near-floor pair at a 3-arm node", which
generalised one rig.

**The hole condition is just `trim < de`**, and nothing narrower. An arm's trim
is `max(reach_ahead, reach_behind, 0)` — in `plan.crossing_trims` and in the
builder alike (`dd = max(max(ta[i], tb[(i-1+n)%n]), 0.0)`) — so ANY arm whose
larger corner reach falls short of its own terminal segment gapping. ⚠️ "Both
corner reaches ≤ 0" is a **sub**-condition, not the condition: it produces
`trim == 0` and therefore the MAXIMAL hole, the full `de`. Both `_corner`
implementations floor their return at ≥ 0, so "≤ 0" can only ever mean "== 0",
and the precise form is `raw + run ≤ 0` on both corners — the fillet run counts,
so "the kerb lines cross behind the node" (`raw < 0`) is not enough on its own.

It is **degree-independent** either way. Driving `plan.crossing_trims` over legal
degree-4 nodes (every gap ≥ 25°, so `graph_min_angle` deletes nothing) finds
**964 distinct bearing sets** with an arm at trim ≤ 4 m — e.g. bearings
(0, 25, 150, 275) at widths (26.8, 15.1, 26.8, 15.1) → trim **2.957**, whose two
reaches are both **+2.957**, i.e. a real gap of `de − 2.957` with neither reach
at zero. Degree 5 reaches it too. And the angle floor is not part of it at all:
on the 3-arm rig the opposite arterial sits at trim 0.000 for **every** gap from
5° to 45°, and symmetrically at 135–175° — 25.5–45° is only the window where
`graph_min_angle` stops deleting the leg first. On N, `104.53 m²` was wrong too
— the hole is **107.20 m² = 4.00 × 26.80 exactly**, a clean rectangle, which is
what the root cause predicts.

⚠️ **AND `city_is_fully_paved` IS STRUCTURALLY BLIND TO IT** — it builds the
must-be-paved region from the corridor's own outer boundary, which the same
defect breaks: on N those prims span x −518.09..−4.00 and 0.00..518.09 (the
second not even closed), so the hole falls **outside the region by construction**
and the check reports `unpaved_m2 0.0` and passes. The one check written to find
holes cannot see a hole that also opens the block boundary. Same shape as the
`selfx_*` lesson above: a check whose input is produced by the thing it checks.

⚠️ **M and O are GREEN on `connections_are_never_refused` while deleting a
street each**, and that is not an oversight in the check: pass 0 is exempt by
design, because `graph_min_angle` exists to remove the near-parallel duplicates
tracing produces. The deletion is recorded in the check's `deleted_in_pass0`
value (`graph_min_angle: 1`) rather than asserted, so the baseline pins it and
M5 turning it to 0 is visible. Whether a 15° approach should cost a street at
all is §S5a item 6 — the artist's call, not the implementer's.

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
