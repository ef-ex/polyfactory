# modelUI: comfortable direct modeling with Houdini as the engine

**Status:** F1 framework core (mode switch, input layer, scene model, Scene Explorer) implemented, audit pending (2026-11-05). Branch `modelui`.
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

## Resume pointer (F1 framework core)

- Branch `modelui`; verify against `git log`. F1 code: `polyfactory/scripts/python/polyfactory/modelui/` (`switch.py`,
  `keys.py`, `input_layer.py`, `scene.py`, `explorer.py`, `appfilter/` with `appfilter.cpp`, `build.bat`,
  `pf_appfilter.dll`), `polyfactory/desktop/ModelUI.desk`, `polyfactory/python_panels/pf_modelui_explorer.pypanel`,
  `polyfactory/MainMenuCommon.xml` (polyfactory > modelUI | Houdini), `polyfactory/python3.13libs/uiready.py`
  (toggle hotkey Alt+Ctrl+Shift+X, memory only).
- Checks (all must exit 0):
  - `hython tests/modelui/check_scene_model.py`: 14 checks, 15 paired mutations red.
  - `hython tests/modelui/check_units.py`: keys record and filter construction, 4 checks, 4 paired mutations red.
  - `python tests/modelui/run_gui_f1.py`: own Houdini (prefs and packages in `F:/cache/modelui/f1/gui`, only the
    polyfactory package; every visible window, floating panes included, is kept at x < -5000 and the run aborts
    otherwise). Input goes the real path (QtTest on the QWindow; sendEvent to the window only for auto-repeat, scan
    codes and a lost release). It builds a mutated DLL (no window test) in `F:/cache/modelui/f1/mut`. 44 checks green
    in the first and last baseline (the 2000-object Explorer checks only in warm runs), 44 paired source mutations
    red, 1 exempt (`toggle_key_registered`: startup only). About 6 minutes; `PF_F1_QUICK=1` runs one baseline only
    (diagnosis). Log `F:/cache/modelui/f1/gui/result.json.log` (an auditor's run overwrites it: re-run before quoting).
- Audit round 1 (2026-11-05): 7 findings, all fixed with checks (round 2 pending): C++ filter called back once per
  receiver (3-4 calls per press) -> only for window receivers; lost release kept the mouse -> "cancel"; Explorer kept
  watching after uninstall -> it is a switch feature now; invalid rename raised -> status message; keys record and
  filter construction made strict; Explorer ceiling at 2000 objects.
- Audit round 2 (2026-11-05): 7 findings + check upgrades, fixed (round 3 pending): gestures are offered only for
  the window that receives the event and the widget under the point inside it (keys: its focus widget, never a text
  input); owned keys pair by scan code and end with "cancel" on application/window deactivation; observe mode
  (`OBSERVE`) and `later()` for Shift+drag clone; double-click covered; floating viewers (`hou.ui.paneTabs()`);
  ownership set before the gesture is called; Explorer survives a click on a just-deleted row; Explorer refresh
  rebuilds nothing when nothing changed.

## F1 findings (2026-11-05, Houdini 22.0.442, Windows)

- **The C++ application filter works on Windows.** VS 2022 Build Tools (MSVC 14.44) + `$HFS/toolkit/include` +
  `$HFS/custom/houdini/dsolib/Qt6Core.lib`; `appfilter/build.bat` builds `pf_appfilter.dll` (objects in
  `F:/cache/modelui/appfilter_build`; rebuild for every Houdini with another Qt). The per-window Python fallback is
  kept and tested (fed through the top QWindow).
- Qt runs an application filter once per receiver of an event (window, widget, parents): the C++ filter calls
  back only for window receivers, where input enters, so every press and key reaches the gestures once.
- `QApplication.widgetAt()` and `topLevelAt()` return None where no screen is (an off-screen test window, a point
  between monitors): the layer finds the top-level widget whose QWindow receives the event and asks `childAt()`.
- Shift+LMB over the viewer (and Alt+LMB, a tumble) pass our window filter but the viewer widget's own filters never
  see them: Houdini takes them earlier (assumed: its application filter at the widget). Observing gestures are
  therefore checked at the window. Unverified: that a Shift+drag on a transform handle moves the handle while a
  gesture observes it (needs a handle and a real state; F2 clone).
- `hou.ui.paneTabs()` includes floating panels; `curDesktop().paneTabs()` does not. Floating panes ignore the
  position they are created with (one landed at (0, 1410)): tests move every visible window off screen.
- The 18:56 crash (`crash.untitled.hannes_36228`, pf_appfilter.dll calling a freed callback) was a mutation run
  (`uninstall_keeps_filter`) on the build before the `__del__` fix: that mutation dropped the filter object without
  detaching it. The 19:47 `crash.broadside` file is from 2026-11-04, in the NVIDIA driver, not ours.
- An `_AppFilter` dropped without `detach()` freed its ctypes callback while Qt still called it: Houdini died on the
  next event (seen under a test mutation). `__del__` detaches now.
- Houdini spells hotkeys its own way: `Ctrl+Alt+Shift+X` is stored as `Alt+Ctrl+Shift+X`; compare in its spelling.
- `hutil.Qt` exposes no `QShortcut`; it comes from `PySide6.QtGui`.
- The `L` flag on a desk split (`split 0.118 H L` in Build.desk) collapses that pane: a Python panel there is never
  built. ModelUI.desk drops it (explorer at 20 %).
- Node selection: `setSelected(True)` fires `ChildSwitched` and `ChildSelectionChanged` on `/obj`; a deselect fires only
  `ChildSelectionChanged` (the scene model listens to that one).
- **Viewer-state keys win in some tools, by design**: inside a tool that binds Q/W/E/R itself (sculpt, KineFX, the RBD
  car rig, ...) the tool's own keys apply, not modelUI's (they live in a deeper hotkey context; audit round 1).
- **Explorer cost at 2000 objects** (warm session): build 45 ms, refresh after a rename 42 ms, idle refresh 19 ms,
  select all 138 ms. In the first minute of a fresh Houdini the same steps took ~10x longer (its start-up background
  work), so the ceiling check (4x warm values) runs only in warm runs.
- Preference files: the switch writes no keymap, hotkey or desktop file (checked; `saveOverrides()` would write
  `Houdini.keymap2.overrides`, the mutation shows it). Houdini itself rewrites `animbar.pref` (on quit), `config/Dialogs/*.ui`
  and its help cache on ANY desk switch (the audit saw it with a Build -> Animate switch without our code): not ours;
  the check logs those and does not judge them.

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
- Input layer (F1): Python handles the gestures; the application-level filter itself is C++ (`appfilter.cpp`), because
  a Python QApplication filter makes PySide wrap every receiving QObject and crashed Houdini in the Maya surface project.
  The scene model and the Scene Explorer are Python: node selection, names and flags are HOM calls, no geometry.

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

## Measurements: one object per piece (2026-11-05, Houdini 22.0.442, Windows, Hannes' kitbash library)

Library `F:/3d/kitbashLib` ($PF_ASSET_LIBRARY): 605 USD files, each one mesh (`/asset/mesh_0`, 10 to ~500 points).
Pieces loaded with `usdimport` as polygons, one geometry object each, scattered over 100 x 100 units.
Benches: `tests/modelui/bench_objects.py` (hython), `gui_bench.py` and `gui_bench2.py` (GUI, window off screen,
`houdini.exe -foreground <script>`; exit through `hdefereval`, a direct `hou.exit` from a Qt timer crashes).

| N objects | build | first cook | memory | list names | copy one | delete one |
|---|---|---|---|---|---|---|
| 100 | 0.2 s | 0.7 s | | 0.2 ms | 15 ms | 2.5 ms |
| 500 | 0.9 s | 2.8 s | | 1.0 ms | 20 ms | 3.3 ms |
| 2000 | 3.7 s | 10 s | +1.4 GB | 2.8 ms | 29 ms | 6.9 ms |
| 5000 | 9.8 s | 24 s | +2.0 GB | 6.2 ms | 45 ms | 15 ms |

Viewport, draw only (frame fixed, camera moved, single-frame flipbook 1280x720; the empty scene costs 58.7 ms of
flipbook overhead, so the extra over it is the draw cost): 500 objects +24 ms, 2000 objects +101 ms,
**the same 2000 pieces in one object +9 ms**. With a frame change (everything re-evaluates) 2000 objects cost
~0.9 s per frame.

Reading: per-object cost is about 0.05 ms per object per drawn frame. Up to ~500 objects tumbling stays fluid;
at 2000 it drops to roughly 10 fps, while one object holding all pieces stays fast. Scene operations (list, copy,
delete, select) are fast at every size. Open decision for Hannes: keep one object per piece, or keep plain kitbash
pieces packed in a few container objects and give a piece its own object only when it gets its own stack.

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
