---
name: houdini-procedural-modeling
description: Core principles for procedural geometry work in Houdini — language choice (OpenCL/VEX, not Python), native tools, input normalization. Read BEFORE building any SOP/geometry node.
when_to_use: BEFORE writing any geometry-manipulation node, wrangle, or SOP HDA (copy, scatter, deform, conform, project, etc.). Always consult first — this is the constitution for SOP work.
tags: sop, vex, opencl, geometry, performance, procedural, principles
---

# Skill: Procedural modeling principles (read first)

Hard-won rules from a 10-year Houdini user. Violating these produces tools that
"have no errors" but are slow, brittle, or just wrong. Consult before any SOP work.

## The default posture: Houdini already has the answer — find it, don't invent it
Houdini is a deeply mature product. Across a 10-year career the problem was *never
Houdini* — it was always not yet knowing or understanding something. It almost always
already has a node, a workflow, or an idiom for what you want.

So the **first move on any task is to find the existing solution, not build a new
one.** Reframe "how do I make X?" into **"how does Houdini already do X, and where do
I find it?"** This is humility doing work: friction means *you're missing something*,
not that the tool is broken — which turns the urge to hack/reinvent into the urge to
search. This posture is the *parent* of rule #0 (investigate) and #2 (use native
tools) below — both are just ways of finding the answer that's already there.
(Generalizes to any mature DCC / framework: ride the maturity, don't fight it.)

## 0. Investigate before you assume — reverse-engineer, read, reason
The most expensive mistake is assuming Houdini *can't* do something and building a
workaround. Before you route around a wall:
- **Reason about what the app must store.** If Houdini saves and reloads it (ramps,
  parameters, networks), there is an API to read it. (That logic is how you find that
  ramp keys are readable in VEX as multiparm channels — see [[ramp-driven-curve]].)
- **Reverse-engineer it.** `node.asCode()` dumps any node as Python, revealing exactly
  how its parameters are addressed. Inspect a working node to learn the real API.
- **Read the docs.** `houdini_doc` / the local help server is version-correct truth.

A hack that routes around an *assumed* limitation usually means you skipped this step.
(The junior `ramp-curve` attempt oversampled-and-thinned because it *assumed* VEX
couldn't read ramp keys — it can.)

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

**Canonicalize the OUTPUT too.** Emit geometry in a predictable space — known origin,
orientation, bounds (e.g. a curve that always starts at origin and runs +X for its
width). Normalize in, canonicalize out → tools compose reliably. See [[houdini-tool-design]].

## 4. Altitude & cook cost

The node lives in a network that re-cooks constantly. Keep it efficient and
stateless; push heavy work to VEX/OpenCL; expose tunables as **parameters**
(data-driven), never hardcoded. See [[no-throwaway-data-driven-code]] in spirit.

## 5. Explicit construction > configurable nodes (when predictability matters)
When the exact result matters, **build the geometry yourself** (e.g. `addpoint` the
point you need) rather than configuring a black-box node and hoping it does what you
assume. You know exactly what happens → fewer latent bugs surfacing later, and a point
or two is no performance concern. Predictability is a feature — see [[houdini-tool-design]].

## Worked anti-example (learn from it)
The first `pf_conform_to_prims` prototype used a **Python SOP** with hand-rolled
bilinear corner interpolation and **no input normalization**. It cooked without
errors but was slow and brittle — "not a useful tool." The correct build: **VEX**
(or OpenCL), using **xyzdist + primuv**, on a **normalized** input tile.

## Done-right checklist
- [ ] Searched for an existing Houdini solution/workflow/idiom before inventing one.
- [ ] Investigated the real API (`node.asCode()` / docs) before assuming a limitation.
- [ ] No Python SOP doing per-element geometry (VEX/OpenCL instead).
- [ ] Reused a native node where one exists.
- [ ] Input normalized into the tool's space; output canonical (predictable origin/orientation/bounds).
- [ ] Tunables exposed as parms; verified visually with `houdini_render_view`.
