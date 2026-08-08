---
name: copernicus-opencl-hda
description: Build a procedural OpenCL noise/texture generator HDA for Houdini's Copernicus (COP) context
when_to_use: When asked to create a custom Copernicus/COP OpenCL noise or texture generator as a reusable HDA (not for built-in noises Houdini already ships)
tags: copernicus, opencl, hda, cop, noise, texture, procedural
---

# Skill: Build a Copernicus OpenCL HDA

Create a COP node wrapping an OpenCL kernel, packaged as an HDA. Built headless
via `hython` from a Python devScript — no interactive Houdini session required.

**Validated 2026-06-24:** a fresh `pf_worley_noise` HDA was authored one-shot from
this recipe (build → structural verify → OpenCL cook, zero errors). The recipe holds.

## Inputs you need from the user
- What the noise/texture should look like (or a Shadertoy/GLSL reference).
- A name → `pf_<name>` (HDA) + `create_pf_<name>_hda.py` (devScript).

## Live reference (pull the real docs, don't guess)
- OpenCL COP node params/bindings/signature: `houdini_node_help("cop", "opencl")`
- HOM used in the devScript: `houdini_doc("hom/hou/NodeType")`, `houdini_doc("hom/hou/HDADefinition")`

## Workflow
1. **Read the full guide first:** [`documentation/copernicus_opencl_hda_guide.md`](../../../../../documentation/copernicus_opencl_hda_guide.md) — it has the kernel structure, binding tables, and the Copernicus output-type index map. Do not skip it.
2. **Copy a worked exemplar** as your starting point: `devScripts/create_pf_gyroid_noise_hda.py` (full, with layer inputs) or the minimal `@ix/@xres` template in the guide.
3. **Write the kernel** (OpenCL C). Port GLSL with the fixes below. Prefix all helper functions `pf_` to avoid OpenCL builtin collisions.
4. **Write `devScripts/create_pf_<name>_hda.py`** — set `OUTPUTS`, `CONST_BINDINGS`, `KERNEL`, and the parm template group.
5. **Build headless:**
   ```
   $env:POLYFACTORY = "F:/projects/polyfactory/polyfactory"
   & "C:/Program Files/Side Effects Software/Houdini 21.0.631/bin/hython.exe" "F:/projects/polyfactory/devScripts/create_pf_<name>_hda.py"
   ```
6. **Verify** parms + `ch()` bindings + kernel via the hython verification snippet in the guide. Optionally cook to confirm the kernel compiles.
7. **Document it** — embed a Help section so the node is discoverable in the help server. Follow the `houdini-node-documentation` skill (`houdini_get_skill("houdini-node-documentation")`); add `defn.addSection("Help", HELP_TEXT)` before `defn.save(...)`. An undocumented HDA is invisible to future agents.

## The non-obvious traps (these are why a naive attempt fails)
1. **`defn.setParmTemplateGroup()` — NOT `hda_node.setParmTemplateGroup()`.** The node-instance version only adds spare parms; they do not persist into the HDA. Always: `defn = hda_node.type().definition()`.
2. **Re-wire the inner network AFTER `createDigitalAsset()`** — it inserts a passthrough that breaks `opencl → output`. Call `allowEditingOfContents()`, clear inputs, re-wire.
3. **Clear output-node inputs with `for slot in range(20): try/except`** — COP nodes have no `nInputs()`.
4. **Copernicus output-type indices differ by 1** between the OpenCL signature menu and the subnet `outputtypeN` menu. Track both (see the guide's table).
5. **`#bind parm` declarations in the kernel must exactly match `CONST_BINDINGS`.**

## GLSL → OpenCL fixes
- `fract(x)` → no 1-arg form; use `#define pf_fract(x) ((x) - floor(x))` or `x - floor(x)`.
- `vec2(x,y)` → `(float2)(x, y)`.
- `abs(x)` on floats → `fabs(x)`.
- `mix`, `smoothstep`, `clamp`, `fmin` exist as OpenCL builtins.

## Done when
- `polyfactory/otls/pf_<name>.hda` exists, all bindings show `ch("../parm")`, and (ideally) it cooks without OpenCL errors.
- If Houdini ships an equivalent natively (e.g. Worley), do NOT build a custom one — expose the built-in instead.
