---
name: houdini-procedural-modeling
description: Core principles for procedural geometry work in Houdini — language choice (OpenCL/VEX, not Python), native tools, input normalization. Read BEFORE building any SOP/geometry node.
when_to_use: BEFORE writing any geometry-manipulation node, wrangle, or SOP HDA (copy, scatter, deform, conform, project, etc.). Always consult first — this is the constitution for SOP work.
tags: sop, vex, opencl, geometry, performance, procedural, principles
---

# Skill: Procedural modeling principles (read first)

Hard-won rules from a 10-year Houdini user. Violating these produces tools that
"have no errors" but are slow, brittle, or just wrong. Consult before any SOP work.

## 1. Language — almost NEVER Python for geometry

A SOP cooks every time anything upstream changes — potentially **thousands of
times**. Python looping over points/prims/vertices is orders of magnitude too slow.

Preference order (best first):
1. **OpenCL** — GPU, fastest. Use when the op is parallel per-element work.
   Caveat: not every function/operation is available; some logic can't be expressed.
2. **VEX** — purpose-built for geometry, *multiples* faster than Python. The default
   for per-point / per-prim / per-vertex work (Attribute Wrangle). Use when OpenCL
   doesn't fit.
3. **Compiled C++ SOPs (the built-in nodes)** — sometimes faster than VEX for
   specialized cases. **Prefer an existing native node over rolling your own.**
4. **Python SOP** — almost always WRONG for geometry. Acceptable only for
   orchestration, tooling/UI, calling external APIs, or trivial one-offs — never
   per-element geometry in a node that re-cooks.

Rule of thumb: **if you're looping over points/prims/verts, it belongs in VEX or
OpenCL.** (This is why the Copernicus pipeline is OpenCL — see [[copernicus-opencl-hda]].)

## 2. Use Houdini's native tools — don't reinvent

- **Surface mapping / conform / shrinkwrap:** `xyzdist` (closest point on a surface
  → fills the prim number + parametric `uv` + returns distance) together with
  `primuv` (evaluate an attribute — `P`, `N`, `uv` — at a prim's parametric uv).
  This pair is the canonical way to get geometry onto/along a surface. Far more
  robust than hand-rolled corner interpolation.
  - VEX shape: `int prim; vector puv; float d = xyzdist(1, @P, prim, puv);`
    then `vector surfP = primuv(1, "P", prim, puv); vector surfN = primuv(1, "N", prim, puv);`
- **Copying/instancing:** `copytopoints`, copy stamping, For-Each blocks.
- Before writing any VEX, check whether a native SOP already does it
  (`houdini_node_help` / search the help server). Reuse beats rebuild.

## 3. Normalize the input — never assume the user's mesh

Whatever mesh the user plugs in, **convert it into the coordinate/parametric space
your tool operates in** before processing. Do not assume size, origin, orientation,
or that it lies flat in a plane.
- Rest it: fit to a known bounding box / unit space (bbox + transform), or rest by
  UV, so ANY input works.
- Handle the awkward cases: non-quad prims / n-gons, missing `N` or `uv`, arbitrary
  scale and transform.

## 4. Altitude & cook cost

The node lives in a network that re-cooks constantly. Keep it efficient and
stateless; push heavy work to VEX/OpenCL; expose tunables as **parameters**
(data-driven), never hardcoded. See [[no-throwaway-data-driven-code]] in spirit.

## Worked anti-example (learn from it)
The first `pf_conform_to_prims` prototype used a **Python SOP** with hand-rolled
bilinear corner interpolation and **no input normalization**. It cooked without
errors but was slow and brittle — "not a useful tool." The correct build: **VEX**
(or OpenCL), using **xyzdist + primuv**, on a **normalized** input tile.

## Done-right checklist
- [ ] No Python SOP doing per-element geometry (VEX/OpenCL instead).
- [ ] Reused a native node where one exists.
- [ ] Input normalized into the tool's space before processing.
- [ ] Tunables exposed as parms; verified visually with `houdini_render_view`.
