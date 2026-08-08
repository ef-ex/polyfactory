---
name: ramp-driven-curve
description: Generate an artist-directable SOP curve from a ramp parameter with adaptive, controllable resolution — points only where the shape needs them. Includes how to READ ramp keys in VEX (not just evaluate).
when_to_use: When turning a ramp/spline parameter into a curve, controlling curve resolution from ramp keys, or any time you need a ramp's KEY positions/interpolation in VEX (chramp only evaluates)
tags: sop, vex, ramp, curve, chramp, resample, resolution, procedural
---

# Skill: Ramp-driven curve with controllable resolution

**Intent (the why):** curves are the backbone of procedural modeling, but point
count is everything — a curve with too many points makes heavy, miserable meshes
downstream. Goal: **artist-friendly shape (a ramp) + surgical control over the
technical cost (resolution)**. Don't uniformly oversample.

## The key technique — read ramp keys in VEX (no Python)
A ramp parameter is a **multiparm**: every key is exposed as individual channels.
Read them directly with `ch()` + `sprintf` in VEX:
```c
int   nkeys = ch("ramp");                         // ch on a ramp returns its key count
float pos   = ch(sprintf("ramp%dpos",   i));      // key position
float val   = ch(sprintf("ramp%dvalue", i));      // key value
float interp= ch(sprintf("ramp%dinterp", i));     // key interpolation (menu int)
```
`chramp("ramp", t)` only *evaluates*; the channels above read the actual **keys** —
that is the no-Python key access. (Found by reverse-engineering — see
[[houdini-procedural-modeling]] "investigate, don't assume".)

## Pipeline
1. **Line** with `points = ch("ramp")` (one point per key).
2. **Wrangle** (points): place each point at `@P.x = ch(sprintf("ramp%dpos",i+1)) * width`
   and read its interpolation into `f@inter`.
3. **Split by interp:** linear/constant segments keep just their endpoints; smooth
   segments **resample to one `segs` control** (the single resolution knob).
4. **Wrangle** `@P.y = chramp("ramp", @P.x/width + 1e-5) * depth` so resampled smooth
   points follow the real curve.
5. **Constant interp:** build the doubled "step" point yourself with `addpoint`
   (explicit > configurable — predictable; one point is free).

## Gotchas / domain knowledge (these are the non-obvious parts)
- **B-spline needs ≥3 points.** An isolated B-spline key (no B-spline neighbor on
  either side) can't form a spline → it's effectively linear, so treat it as linear
  and don't spend `segs` on it. Check the neighbor interps.
- **Sampling exactly on a key/boundary is fragile.** Float precision makes points
  land at wrong positions right on a key. A tiny epsilon (`+1e-5`) on the `chramp`
  sample position is a legitimate pragmatic fix (a real battle-scar, not elegance).
- **Curve bevel workaround.** Older Houdini couldn't bevel a *curve*, so the optional
  bevel detours mesh → bevel corners → reconstruct curve. **Re-check in H21** —
  `polybevel` may now bevel curves directly and the detour may be removable.

## Output is canonical (predictability)
The curve always starts at world origin and runs **+X for `width`**, with defined
height — so anything downstream knows its bounds/orientation with zero guessing.
See [[houdini-tool-design]] (predictable I/O) — this is deliberate, not incidental.

## Reference
The author's `pf::ramp_curve` HDA. Output is the curve; mesh nodes (skin/polybevel)
exist only to service the optional bevel.
