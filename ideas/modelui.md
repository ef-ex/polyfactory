# modelUI: comfortable direct modeling with Houdini as the engine

**Status:** decisions and feature list only (2026-11-05, with Hannes). Nothing is built yet. Branch `modelui`.
**This file owns:** the modelUI framework and its modeling mode: goal, decisions, the mapping to Houdini, the
feature list, and the references. Not to be confused with `pf_modeler` ([`modeler.md`](modeler.md), the
ZSphere-style skinning tool). Kitbash browsing builds on the asset library plan in
[`asset_library_redesign.md`](asset_library_redesign.md) and the existing `asset_library` package
(`kitbash_placement_state.py`, `kitbash_ui.py`); artist-facing UI rules: [`artist_ui.md`](artist_ui.md).

## Goal

A scene Hannes can manipulate without thinking about or managing nodes, with the comfort of 3ds Max (where he learned
modeling), and Houdini doing all the work underneath. Not a 1:1 copy of Max, not a replacement of Houdini's UI.
It is the base of his spaceship modeling tool (front/side/top/perspective views, primitives, Boxcutter-style cutters,
copy/transform, clean game mesh).

Why it matters: every time he reaches the modeling part he gets annoyed by the node workflow and does something else.

## Decisions (Hannes, 2026-11-05)

- Part of polyfactory, branch `modelui`.
- Built on **SOPs**, not Solaris ("you cannot model in Solaris").
- **Houdini's viewport and Houdini's own selection** stay (points, vertices, primitives, detail; it works almost like
  Max). No own renderer, no Max look, no Maya UI.
- **Own layout** (desk + Python panels), switchable with normal Houdini, not a full UI replacement.
- **Modifier stack = Houdini nodes.** The stack lists real SOP nodes; Max modifiers are recreated only if one is
  really good. Multi-input nodes and group fields become UI elements (pick an object, use the current selection),
  as Max's modifiers asked for picks (ProBoolean operand, Path Deform path, Attach).
- Modifiers he used most (Max 2012 era): Extrude, Subdivide, Bevel, Lattice, Edit Poly.
- **Clone:** Shift+drag makes a normal **Copy** by default. **Instance** and **Reference** are special options
  (Clone dialog). Instances will need packed primitives.
- **Align tools are a must** (he used them all the time).
- **Framework first:** the core must carry other modes later (texturing named, others likely).
- Piece count per scene is unknown (he never got far enough); measure object-level performance early.
- The Maya surface project (`F:\cache\houdini_maya_anim`) is a **read-only reference**: never write code there.

## Decision log (house rule 2: why Python)

- The whole tool is UI and parameter marshalling (panels, input gestures, node creation, selection). Geometry work
  stays in native SOP nodes, which is the point of the tool. Any geometry code that shows up later follows rule 2.

## Framework (layers shared by every mode)

1. **Mode switch**: install/uninstall all-or-nothing, own desk, run-time hotkeys with exact revert, nothing written
   to Houdini's preferences. Pattern: `switch.py` of the Maya surface project.
2. **Input layer**: one application event filter for gestures hotkeys cannot express (Shift+drag clone, tap/hold).
   The Maya project's C++ filter exists only as a Linux .so; Windows needs its own build (or the per-window Python
   fallback, which loses some gestures).
3. **Scene model**: objects, selection, clipboard (copy/paste between hip files), undo groups.
4. **Panels kit**: shared Python-panel widgets for lists, stacks, parameter rows.
5. **Operation registry**: Houdini nodes wrapped with a little metadata (name, icon, which inputs/groups become pick
   buttons, defaults). Modeling lists SOPs; a later texturing mode would list COPs.
6. **Mode** = a bundle of desk, keymap table, panels, viewer states and operation list.

## Mapping to Houdini

| Comfort feature | Houdini underneath |
|---|---|
| Object in the scene | one geometry object per mesh (object level) |
| Modifier stack | that object's SOP chain, shown as a list |
| Edit Poly | Houdini's component selection + its modeling SOPs (PolyExtrude, PolyBevel, Subdivide, Lattice, Edit...) |
| Copy | duplicate the object with its stack |
| Instance | object that shares the source's stack output, packed |
| Reference | shares the source's stack output, own nodes on top |
| Pick-an-object input | Object Merge into the stack |

## Feature list

First milestone (the kitbash loop), preceded by the object-count measurement (100 / 500 / 2000 objects):
- Framework core (mode switch, input layer, scene model).
- Scene Explorer: every object by name; select, rename, hide, freeze, isolate, delete, group.
- Click-select objects in the viewport without the network editor; Houdini's component selection inside.
- Shift+drag clone (Copy); Clone dialog with Copy / Instance / Reference and number of copies.
- Copy and paste objects between scenes (open a kitbash scene, copy a part, paste into the working scene).
- Modify panel: the stack (add from the node list, reorder, on/off, delete, collapse to mesh, open as nodes).
- Align: Align to target (position min/center/pivot/max per axis, orientation, scale), quick align, normal align.
- Snapping, pivot editing, undo for everything.

Next:
- Kitbash browser: USD files and the meshes inside; drop a single mesh into the scene (with the asset library).
- Quad menu on right-click; Create panel with interactive primitives (drag base, then height).
- Mirror, Array, Boolean as stack entries; scene tabs; layers; materials; export to game/DCC.

## References

- Maya surface for Houdini (Hannes' studio project, copy, read only): `F:\cache\houdini_maya_anim` (architecture:
  `tracks/ui/workers/c_arch/ARCHITECTURE.md`; 27 SideFX bugs with workarounds: `docs/SIDEFX_BUGS.md`).
- BsMax (Blender, GPL-3, reference only, do not copy code into polyfactory): `F:\cache\max_ref\BsMax`;
  https://github.com/NevilArt/BsMax. Its Shift-drag clone is an empty stub; Clone dialog, Align, primitives exist.
- Jake Denham, "I Rebuilt 3ds Max With AI" (Blender underneath, Max panels on top; modifiers were the hardest part;
  scene tabs, copy/paste between scenes): https://www.youtube.com/watch?v=74TsKdNWEaA (no code).
- Max Stack by kleinARt (27 Max modifiers as Blender Geometry Nodes; selections flow down the stack):
  https://effectbay.com/plugin/max-stack-max-modifiers-and-stack/
- Modeler for Houdini (Alexey Vanzhula, paid): direct modeling in one SOP node; Ctrl+D duplicate.
