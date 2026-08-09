# polyfactory tests

Two layers. Run the fast one constantly, the slow one before you believe a fix.

```bash
# pure logic — no Houdini, ~0.002s
python tests/unit/test_citygen.py
python tests/unit/test_graph.py

# geometry — throwaway Houdini session, never saves a .hip
hython tests/citygen/run_scene_checks.py
hython tests/citygen/run_scene_checks.py --update-baseline
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
    test_graph.py        street graph construction (25 tests)
  citygen/
    checks.py            the assertion library — add to this
    cases.py             scene construction + headless env setup
    run_scene_checks.py  the runner
    baseline.json        recorded values
```

`cases.py` sets `POLYFACTORY`, `HOUDINI_VEX_PATH` and `sys.path` itself, because
hython does not load the polyfactory package: without it `#include
<pf_streetgraph.vfl>` cannot resolve and Python SOPs cannot import
`polyfactory.citygen`. The harness found that portability bug on its first run.

## Known-failing at time of writing

Not noise — real, tracked defects:

| Case | Check | Value | What it is |
|---|---|---|---|
| A | `selfx_junction_surface` | 4 | dark dart at junction (60.8, −111.3) |
| C | `no_downward_faces` | 10 | radial-centre sweep fold, 62.7° kink on a degree-2 node |
| C | `selfx_roads` | 46 | same fold, plus 2 cross-street corridor overlaps |
| all | `attribute_schema` | 1 | `land_use` never written to the graph |
