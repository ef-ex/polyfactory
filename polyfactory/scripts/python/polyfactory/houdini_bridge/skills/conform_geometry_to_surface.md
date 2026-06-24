---
name: conform-geometry-to-surface
description: Conform/copy a tile mesh onto every primitive of a target surface in VEX via primuv (e.g. weave a pattern onto a form to make baskets)
when_to_use: When asked to wrap, conform, weave, or tile a pattern/tile mesh onto another mesh's surface so it follows the form (not a rigid scatter — copytopoints already does that)
tags: sop, vex, primuv, matchsize, conform, weave, normals, geometry
---

# Skill: Conform a tile onto every prim of a surface (VEX + primuv)

Map a flat relief-tile into each target primitive's parametric space so it bends
around the form. Validated building a woven-basket-on-a-torus. Read
[[houdini-procedural-modeling]] first — this obeys those principles.

## The pipeline
```
tile (flat in XZ, relief in +Y)
  -> Match Size            # normalise input to a unit box (NATIVE, not hand-rolled VEX)
target surface
  -> Normal                # ensure point N on the target for primuv("N")
tile + target -> Attribute Wrangle (Detail)   # the conform, in VEX
```

## Normalize the input with Match Size (not custom VEX)
`matchsize` SOP: **Justify With = Origin and Unit Size**, **Justify X/Y/Z = Min**.
The tile lands in `[0,1]^3` (uniform scale, so it keeps its relief proportion).
Then in VEX the tile point position IS its parametric coord: `x=u`, `z=v`, `y=relief`.

## The conform (Detail wrangle: input0 = target+N, input1 = unit tile)
```c
int np = nprimitives(0);
int tn = npoints(1);
int tnp = nprimitives(1);
float relief = chf("relief");
for (int p = 0; p < np; p++) {
    int newpts[]; resize(newpts, tn);
    for (int i = 0; i < tn; i++) {
        vector tp  = point(1, "P", i);             // unit-boxed tile: x=u, z=v, y=relief
        vector puv = set(tp.x, tp.z, 0.0);
        vector sp  = primuv(0, "P", p, puv);       // surface position at this prim's (u,v)
        vector sn  = normalize(primuv(0, "N", p, puv));
        int q = addpoint(0, sp + sn * (tp.y * relief));
        setpointattrib(0, "N", q, sn);             // GOTCHA 3 — see below
        newpts[i] = q;
    }
    for (int pr = 0; pr < tnp; pr++) {
        int tpts[] = primpoints(1, pr);
        int poly = addprim(0, "poly");
        for (int k = len(tpts) - 1; k >= 0; k--)   // GOTCHA 2 — reversed winding
            addvertex(0, poly, newpts[tpts[k]]);
    }
}
for (int p = 0; p < np; p++) removeprim(0, p, 1);  // drop the original target geo
```

## The three gotchas (these are why a naive build looks wrong despite no errors)
1. **Normalize the input with Match Size, not hand-rolled bbox VEX.** Houdini has
   the node; use it (and it handles arbitrary input meshes).
2. **`primuv` conform inverts the winding.** Copying the flat tile's vertex order
   onto the surface flips face orientation, so normals point *into* the surface
   (bluish backface overlay in the viewport). **Reverse the vertex order** when
   building each prim.
3. **`addpoint` gives `N = (0,0,0)`.** The wrangle's input (the target) has an `N`
   point attribute, so every `addpoint` inherits that schema with the *default*
   zero value → zero-length normals → the geometry renders **black/unshaded**.
   **Set `N` explicitly** (`setpointattrib(0,"N",q,sn)`), or remove the inherited
   `N` and recompute downstream.

## Use VEX (or OpenCL), never Python
The first attempt used a Python SOP — slow and wrong for a node that re-cooks.
See [[houdini-procedural-modeling]].

## Production reference — `pf::mesh_to_quad` (the battle-tested pattern)
The author's own HDA (`pf_mesh_to_quad`, made years ago) solves this with **native
nodes** instead of one monolithic wrangle — cleaner, faster, and more complete.
Pipeline:
```
input tile  -> matchsize                     # normalise (confirmed: the right tool)
target      -> extractcentroid               # one point per prim (native)
            -> attribwrangle  i@primID=@primnum   # piece id per prim (class=primitives)
            -> copytopoints (piece=primID)   # instance the tile per prim (native, fast)
            -> attribvop  (primuv P + primuv N)   # conform onto the surface (primuv, as VOP)
            -> reverse                        # GOTCHA 2: fix the inverted winding (native SOP)
            -> fuse                           # weld the seams into a continuous weave
            -> attribwrangle  @N=@N           # recompute / promote normals
            -> uvunwrap                       # give the result UVs
            -> attribdelete                   # strip temp attribs (primID, etc.)
```
It also exposes a **`conform` toggle** (rigid copy vs conform) and **align + full
TRS** controls on the input tile — i.e. a real tool, not a one-shot.

**Takeaways for any future build:**
- Prefer `copytopoints` (+ a piece attribute from `extractcentroid`) over building
  geometry in a wrangle — native, faster, modular.
- `reverse` (native SOP) is the clean fix for the primuv winding inversion.
- **Weld seams with `fuse`** and **add UVs with `uvunwrap`** — a conformed weave
  isn't finished until it's continuous and UV'd.
- Expose a conform on/off toggle + input transform controls.

## Done when
- The output renders **gray** (shaded), not black (zero N) and not bluish
  (inverted winding). Verify by eye in the viewport.
- Tiles bend continuously around the form (a real weave), not scattered.
- Seams welded (`fuse`) and UVs present (`uvunwrap`) for a production-ready result.
