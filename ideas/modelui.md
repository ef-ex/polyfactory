# modelUI: comfortable direct modeling with Houdini as the engine

**Status:** F1 framework core (mode switch, input layer, scene model, Scene Explorer) done: 5 independent audits, final verdict yes; merged into `main` (4aea050, from `modelui` fed05d1) on 2026-11-05. F2 waits for Hannes' backend choice (one object per piece or mixed). Branch `modelui`.
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

## Resume pointer (F2a: container backend, piece selection, Shift+drag Copy)

- 2026-11-10: **F2b Clone dialog** (polyfactory > Clone... and the Scene Explorer's button; `modelui/clone.py`),
  implemented, unverified by an audit. Max's Clone Options plus an Array-lite: Copy / Instance / Reference, number of
  copies, and per copy a move (world units), a turn (degrees, about the world axes through the item's own position)
  and a scale (% per copy, compounding); copy k gets k steps. The dialog opens with the values used last. Mixed
  selections: every item clones by its kind; one undo step; the clones are selected.
  - Objects: Copy = the object with its whole network (`copyNodesTo`). Instance = a new object whose only node is an
    Object Merge of the original ("original", transform none, packed, pivot origin): it always shows the original's
    result. Reference = the same Object Merge unpacked, the place for its own nodes on top (user data
    `pf_clone_kind`). Houdini follows a rename of the original in the merge path.
  - Pieces: Copy = a new piece (`containers.copy_pieces`). Instance / Reference = a new piece too (pieces share their
    source file already) with point attributes `pf_clone_kind` (string, "instance"/"reference") and `pf_clone_of`
    (int, the original's pf_piece; 0 = none). Open for F2c (modifier stack): what a modifier on the original does to
    its piece instances and references (decision for Hannes: follow Max, so instances get it too).
  - Shift+drag stays an immediate Copy without the dialog (Hannes' decision 2026-11-05; Max opens the dialog after a
    Shift+drag).
  - Checks: hython `tests/modelui/check_clone.py` (copies step by step: position, axes with turn and compounding
    scale computed as vectors; selected; one undo for pieces and objects together; piece copies carry no relation;
    piece instance recorded; object Copy independent, Instance packed and following the original, Reference
    unpacked and following; 10 mutations red) and gui_f2a `clone_dialog_ok` (the dialog's fields reach clone:
    Instance x3, 2 units each; mutation `dialog_count_ignored`). Blind spots: the dialog is never shown in the tests
    (layout, off-screen guard), what F2c does with the piece relation.
- 2026-11-10: **Add kitbash pieces...** (the artist's way to get pieces in; Hannes could not try F2a without it):
  polyfactory menu and the Scene Explorer's button. A file dialog at $PF_ASSET_LIBRARY (default F:/3d/kitbashLib),
  several USD files at once; the pieces go into the current container (the selected piece's, else the first, else a
  new one) in a row along X, centred where the viewport looks (camera pivot dropped to the ground), each standing on
  the ground and spaced by its bounding box (gap 10 % of the widest), selected afterwards, one undo step
  (`modelui/kitbash.py`). Checks: hython `tests/modelui/check_kitbash.py` (row on the ground with the gaps, centred;
  one undo; selected; current container reused; a moved and turned container still puts the row at the look-at point;
  6 mutations red) and gui_f2a `kitbash_at_look_at` (camera pivot at (7, 3, -4): the piece lands at x 7, z -4 on the
  ground; mutation `look_at_ignored`). Blind spot: the dialog itself (hou.ui.selectFile with multiple_select returns
  the files separated by ';', parsed by `add_dialog`, untested), the menu entry and button clicks.
- 2026-11-09: F2a audit 5 (agent-195, evidence `F:/cache/modelui/audit_f2a5/`) confirmed the leak fix; its five items
  are fixed, each with a gui_f2a check seen red under its mutation (no sixth audit, per Hannes' coordinator: modelui
  goes to main and Hannes tries it himself; next for this builder: F2b Clone dialog):
  1 Space+LMB on a piece turned no camera in W: the click gesture owned every plain left press on a container, also
    in Houdini's view state (Space puts the viewer in "objview"). Both piece gestures now decline in `VIEW_STATES`
    (objview, view). Check `space_lmb_on_piece_turns_camera` (W and Q, press on a container, camera restored after with
    `setDefaultCamera` so the next run frames the same; mutation `view_state_ignored`). Why Q looked different in the
    audit: not the state. With the press on mid's body, the pre-fix code (the mutation run) owned it in Q exactly as
    in W (camera still); the audit's S2 press got `owned False`, which this gesture only answers when no container is
    under the point, so its Q press most likely landed off the piece (the probe did not log the node under it:
    unverified).
  2 A gesture that raises got no "cancel" (a drag's preview stayed): `_call` now sends it "cancel" when it loses what
    it held (`gesture_error_reverts_preview`, an injected error in the preview write; `cancel_on_error_dropped`).
  3 A stale swallowed button after a lost release: a new press of that button clears it
    (`stale_eaten_cleared_by_press`; `eaten_kept_on_press`). Blind spot: a move with the button up already clears the
    entry, so the check seeds it (audit 5 probe L_altmmb_after_lost is how it survives in the wild). QTest note: a
    press of a button QTest still holds sends a release first.
  4 A left press with another button down is Houdini's (`left_with_other_down_declined`; `other_down_ignored`). Found:
    in PySide6 `~Qt.LeftButton` is RightButton (no mask), so `buttons() & ~LeftButton` missed the middle button; the
    test is `buttons() == LeftButton`. The check hides the whole chord from Houdini (a half-seen chord left Houdini's
    drag and its undo group open).
  5 Blind spots closed: `no_drag_buttons_reach_houdini` (MMB/RMB press and release reach the window with no drag;
    `non_left_always_swallowed`), `off_before_commit_restores` (modelUI off between release and the deferred commit,
    the commit held back from QTest's timer pump; `off_ignores_pending`).
  Test hygiene: in the first full run the mutation proxy_reused_unfiltered put a kept handle null under the body press,
  so Houdini got the drag and the synthetic lost release left its undo group open for every later run (then a hang).
  The audit-5 drag cases now hide every left event modelUI did not take or gave up from Houdini (`hide_left`).
  GUI suites of different builders must not overlap on this PC: a concurrent test Houdini (F2d's) slowed F1's
  `perf_explorer_2000` past its ceiling, and two off-screen Houdinis can take focus from each other (a focus change
  cancels drags). The gate script waits for other test Houdinis and holds `F:/cache/modelui/gui.lock`.
  Load-robust checks (the PC ran at 62-100 % CPU from another session's audio job): F1's `perf_explorer_2000` is
  judged as a ratio to a fixed reference workload measured right beside it (a plain QListWidget filled with the same
  2000 names and selected, 10 times); ceilings 3x the highest ratio of the 2026-11-09 warm runs (build 7, after
  rename 8, idle 9, select all 22); `slow_refresh` stays red (ratio ~2700-6000). Blind spot: a load that slows the
  Explorer's HOM calls much more than plain Qt lists. gui_f2a's handle click waits until the handle is under the click
  point (`queryNodeAtPixel` sees its null; a loaded PC drew it late and the click cleared the selection).
  Found in a final baseline: switching modelUI off while Houdini cooked ("Cannot delete nodes while cooking", a timer
  fires inside a long cook) left the handle null and stopped the rest of `pieces_ui.uninstall` (containers stayed
  unselectable). `_delete_marked` now retries the refused nodes every 100 ms (up to 5 s) and lets uninstall finish;
  check `uninstall_retries_busy_delete` (the first delete refused like that; mutation `no_delete_retry`).
  Verified 2026-11-09: PF_GUI_SCRIPT=gui_f2a.py run_gui_f1.py exit 0 (62 / 62 checks green in the baselines, 68 paired mutations red); run_gui_f1.py exit 0 (64 mutations red); hython check_containers, check_scene_model, check_units exit 0.
- 2026-11-09: F2a audit-4 finding 1 fixed, checks green; F2a audit 5 pending (implemented, not audited). Audit 4
  (evidence `F:/cache/modelui/audit_f2a4/`): a middle click during a modelUI body drag reached Houdini, which started
  its own handle drag (MMB drags the handle anywhere in "pose") and left its undo group open ("Cannot undo within an
  undo group" through the MMB release, Esc and a later click).
  - input_layer: while a gesture owns a mouse button, every other button's press is swallowed into the eaten set, so
    its release and double-click are swallowed too (also a release that comes after the drag ended).
  - pieces_ui: a body drag never opens an undo group while it runs (preview under `undos.disabler()`, the commit is
    one `with undos.group`). `_revert_preview` puts the start state back (copies deleted) without an entry: cancel
    (focus loss, lost release) uses it through the deferred commit; uninstall mid-drag, or between release and the
    deferred commit (`_state["pending"]`), reverts synchronously and commits nothing (before: the preview stayed,
    with no undo entry).
  - gui_f2a checks + mutations: `middle_click_mid_drag_swallowed` (MMB press, release, double-click;
    `other_button_passes`, `other_release_passes`), `right_click_mid_drag_swallowed` (`other_button_passes_rmb`),
    `middle_release_after_drag_swallowed` (`eaten_lost_at_release`), `cancel_mid_drag_restores` (`cancel_commits`),
    `off_mid_drag_restores` (Shift+drag, pieces_ui off then the layer's cancel, the order switch.uninstall uses;
    `off_keeps_preview`). Each: nothing got past the layer (a spy filter on the viewer's window records and swallows
    any non-left button event that did), `undo_open()` finds no open group, exactly one "modelUI: move" and undo puts
    the piece back exactly (cancel/off: no entry, no move, no new rows).
  - The real failure, not only the routing: `PF_F2A_SPY_PASS=1 PF_F2A_ONLY=other_button_passes` lets the middle button
    through the spy to Houdini. Run 2026-11-09 (`F:/cache/modelui/f2a5/leak`): baseline green (nothing reached the
    spy); under the mutation Houdini recorded "Transform Handle Change", `undo_open()` = "Cannot undo within an undo
    group", undo did not move the piece back, the check red. The normal suite keeps the spy swallowing because a
    leaked group stays open for the rest of the session and poisons every later run.
  - Blind spots: the desk switch during a drag (the off check skips it; F1 and the end of gui_f2a switch for real);
    the Qt focus signal (the check calls `layer().cancel()`, which the signal calls; F1's
    `key_cancel_on_focus_window` covers the signal). Esc mid-drag has no modelUI code path: logged in the
    2026-11-08 runs (commits once, no open group), not a check.
  - Test hygiene found: an Esc case in the suite let Houdini leave "pose" for "objview" under some mutations; the next
    run then framed differently (mid's pixel (332, 294) -> (339, 291) / (332, 312)), so camera-dependent checks of
    every later run went wrong (`redo_lost` stayed green, `offsets_wrong` leaked Houdini's group). Removed; now 63
    runs at (332, 294). A run's leftovers in Houdini's UI state carry into the next run: log `pick mid at` per run.
  - Verified 2026-11-09: `PF_GUI_SCRIPT=gui_f2a.py run_gui_f1.py` exit 0 (55 checks green in both baselines, 61
    paired mutations red, no undo leak); `run_gui_f1.py` exit 0 (64 paired mutations red); hython
    `check_containers.py`, `check_scene_model.py`, `check_units.py` exit 0. One earlier F1 run segfaulted in its
    final baseline (12:07, `crash.untitled.hannes_11720.hip`, no stack written); the rerun passed; not reproduced.
- 2026-11-07: all F2a audit-3 items are in; F2a audit 4 pending. gui_f2a: 50 checks per baseline, 55 paired
  mutations red; F1 suite 61 / 64. The "Cannot undo within an undo group" failure of one earlier full run did not
  come back in three full runs; every run's cleanup now probes undo (a throwaway null, then undo) and, on a leak, logs
  it and sends a mouse release (an unfinished Houdini handle drag holds an undo group open). Found while pairing
  checks: Houdini's TRANSLATE handle also moves node-selected objects (scale moved only the null, rotate_ring_probe);
  modelUI's offset write is the one that counts (mutation offsets_wrong turns handle_moves_selected_object red). A
  mutation of scene.py must give the cached scene object the mutant class (the Explorer holds that object).
  Audit 3 (agent-179), each with a check in gui_f2a:
  1 a body drag past the horizon keeps its last valid point (no point behind the camera or beyond 20x the grab
  distance); 3 in Q, Shift+drag from a piece adds by box, copy only in W/E/R; 6 highlight checked for every selected
  piece, horizon drag at a camera angle, Shift box from a piece.
  - 2 (held objects): evidence `tests/modelui/rotate_ring_probe.py`, plain Houdini, a box object A and a null N both
    selected, N current: a handle drag (stock E = scale; modelUI maps W/E/R the Max way) changed only N, never A.
    Houdini's object handle transforms only the node it sits on, so a "double move" of selected objects does not
    happen: the hold was removed (objects stay in Houdini's selection with its highlight; modelUI moves them by their
    offsets to the handle null). That removes the out-of-step states A2/A6. A4: modelUI's selection changes are no
    longer undo entries (piece selection cannot be undone; check `pick_adds_no_undo_entry`).
  - Checked and dropped: "a handle drag that starts over empty space becomes our box selection". Along the scale
    arrow `queryNodeAtPixel` reports the handle's null wherever the handle grabs (40 px; nothing from 50 to 120 px was
    both empty and on the arrow), so the click gesture never boxes there. Rotate rings were not probed (open).
  - 4 Ctrl step (decision): the cell of the grid the user sees: an orthographic view's own grid
    (`settings().orthoGridSpacing()`), else the construction plane when visible, else the reference grid
    (`referencePlane().cellSize()`). Houdini's handle Translate Step (handle parameters dialog) is not readable from
    HOM (no getter for the built-in transform handle; `hou.Handle.settingValue` serves Python-state handles only), so
    body-drag snap follows the visible grid instead. Rotate/scale body drags have no Ctrl step.
  - 5 body drag mode follows W/E/R (an observing key gesture, so it needs the keyboard focus in the viewer, which a
    click there gives): E turns about the view axis through the pivot (0.5 degrees per pixel of horizontal drag),
    R scales uniformly (e^(0.01 * dx)), W moves; Shift copies in all three.
- 2026-11-07: all F2a audit-2 items are in; F2a audit 3 pending. Audit 2 (agent-178) fixes, each with a check: 1
  highlight box from the piece's corners (compared with the piece's own points, far from the origin), 2 containers
  saved selectable (restored around a save), 3 a plain click on the handle keeps the selection, 4 observers get
  "cancel", 5 measurements (GUI vs hython add, select range), 6 per-run scratch (save_check.hip, mutated DLL), 9
  Houdini's select keys (found: F1's demo gesture took Ctrl+Shift+LMB in every viewer; it now installs only with
  PF_MODELUI_DEMO=1, set by the runner for the F1 suite).
- Comfort decisions (Sunita for Hannes, 2026-11-07), built and checked:
  - Selection keys are Houdini's own (`basics/select.html`): Shift add, Ctrl remove, Ctrl+Shift toggle; not Max's.
  - Pivot of a multi-selection = centre of the selection's bounding box (Max default): the handle null sits there,
    and every selected piece AND object follows it by its offset, so rotate/scale pivot there for both. To keep
    Houdini from moving the objects a second time, they leave Houdini's node selection and the scene "holds" them
    (`MixedScene.hold`, still in `selected()`, cleared by the next `select`). One piece alone: the handle has that
    piece's own transform. Check `mixed_rotate_about_pivot` drives a rotation through the handle's null (the value a
    rotate drag writes); a rotate DRAG on Houdini's ring is not driven (blind spot).
  - Body drag (move tool, W/E/R state "pose"): pieces and loose objects alike; in perspective views on the ground
    plane through the grabbed point (the view plane when looking almost level), in orthographic views on the view
    plane; Ctrl snaps the move to the construction grid's cell size (the move snaps, not the position); Shift = Copy.
  - With Q (select tool) a drag that starts on a piece is a box selection (ours, with a rubber band; objects and
    pieces by their centres); a drag from empty space stays Houdini's box (pieces added by centre).
- Limit: a piece stores translate, orient and scale, no shear. Scaling a multi-selection non-uniformly while its
  pieces are rotated relative to the scale axes would need shear on each piece: it cannot be stored (the pieces keep
  their own orientation and get the nearest scale). Same for a non-uniformly scaled container.
- Branch `modelui`. 2026-11-07: all F2a audit-1 items are in; second F2a audit pending.
  - Input layer (F1 framework): several OBSERVE gestures share one press (every gesture is still asked; one that
    answers True after them takes the press and the observers are dropped; observers get move/release/keyup and
    "cancel", nothing they see is swallowed). Check `two_observers_share_press` (mutation: stop after the first).
  - 9b multi-selection in `pieces_ui`: Shift-click adds, Ctrl-click removes, a box from empty space adds the pieces
    whose centres are in it to Houdini's object result, the handle null moves every selected piece (offsets to the
    null) while Houdini moves the selected objects, body drag and Shift+drag move/copy the whole selection in one
    undo step, one highlight box per selected piece.
  - Checks: `run_gui_f1.py` (F1 suite with pieces_ui installed): 60 checks green in both baselines, 63 paired
    mutations red. `PF_GUI_SCRIPT=gui_f2a.py ...`: 33 checks green in both baselines, 34 paired mutations red.
    `check_containers.py`: 25 checks, every paired mutation red. Both GUI runs take 10-17 minutes: run in the background.
  - Known limits: Shift+drag Copy moves in the view plane (no axis constraint); rotate/scale handle DRAGS are not
    driven by any check (typed rotate/scale on the null are); rotation of a multi-selection pivots on the first
    selected piece (Max uses the selection centre).
- Shift+drag on Houdini's own handle after a session's first run: NOT a Houdini behaviour. Probe
  `tests/modelui/shift_handle_probe.py` (plain Houdini, no modelUI, a box object in "pose", three rounds with a hip
  clear between): plain drag 0.542 and Shift drag 0.661 units in every round. The failure only happened with modelUI's
  proxy null and gestures in play (cause not found); modelUI now owns every Shift drag, so it no longer matters. No
  pitfall entry.
- Code: `modelui/containers.py` (storage, promote), `scene.MixedScene` (`scene.current()`), `modelui/pieces_ui.py`
  (in `switch.FEATURES`: click pick, Houdini's handle on a proxy null, Shift+drag Copy, highlight).
- Checks (all exit 0):
  - `hython tests/modelui/check_containers.py`: 21 checks, 21 paired mutations red.
  - `PF_GUI_SCRIPT=gui_f2a.py PF_F1_SCRATCH=F:/cache/modelui/f2/gui python tests/modelui/run_gui_f1.py`: 17 checks
    green in both baselines, 19 paired mutations red; passed twice in a row (about 6 minutes, run in the background).
  - `python tests/modelui/run_gui_f1.py` (F1 suite, with `pieces_ui` installed by the switch): 59 checks per
    baseline, 62 paired mutations red.
  - Bench: `python tests/modelui/bench_f2a.py` (numbers below).
- Probes (evidence): `tests/modelui/state_probe.py` (why no Python viewer state), `keys_probe.py`, `shortcut_probe.py`.
- Why no Python viewer state: a node-less state cannot carry a handle (Houdini docs) and is entered through
  onGenerate, so Houdini's own handle runs on a proxy null bound to the selected piece.
- Root causes of the earlier flaky handle drag (per-run logs of on-screen drag, proxy writes, undo labels,
  selection, state): the session's first entry into "pose" needs a moment before a press grabs the handle (the test
  waits); a world-unit threshold depended on the camera (now on-screen pixels); an unselectable proxy was dropped by
  "pose" on entry (the proxy is selectable now); Houdini's own click on a container raced our pick (now Houdini never
  gets clicks on containers, and containers are not selectable in the viewport, so box selections skip them too).
- Known limits: plain LMB clicks over a viewer are observed by the pick gesture (a later plain-click gesture must be
  registered before it); a drag that starts on a piece but not on the handle does nothing (Houdini never sees clicks
  on containers); only translate drags are driven by the checks (rotate/scale are Houdini's own handle modes);
  promote has no caller yet (F2c's first modifier); copy/paste between hips is F2e.

## F2a measurements (`tests/modelui/bench_f2a.py` in the GUI; `check_containers.py` headless; all 605 library files)

| Pieces | add, GUI (bench) | add, hython (check) | first cook | draw over the empty scene |
|---|---|---|---|---|
| 100 | 2.0 s | | 0.6 s | +4.0 ms |
| 500 | 1.2 s | | 2.8 s | +11.7 ms |
| 2000 | 7.7 s before the audit-1 fix, 5.6 s after (audit 2) | 0.9 s | 3.8 s | +12.1 ms |
| 5000 | | 1.0 s (18.2 s before the fix) | | |

- Why the two add columns differ: both add through `containers.add_pieces` (one edit, one Copy to Points). The GUI
  number includes creating the 605 source chains (1815 nodes) with the network and parameter panes open, which
  costs several seconds in the GUI and almost nothing in hython; it is paid once per container, the first time each
  file is used. The audit-1 fix removed the quadratic name/source rescan (the hython column, gated at 3.0 / 3.5 s).
- Draw: single-frame flipbooks 1280x720 while the camera orbits, median of 20 (the empty scene's 38.3 ms is flipbook
  overhead). Against the object-level numbers below: 2000 objects +101 ms, the same 2000 pieces as polygons in one
  object +9 ms; packed pieces in a container land next to the one-object number.
- One piece at 2000 pieces in the GUI (edit + recook + redraw; target < 50 ms): move 5.4 ms, copy 5.0 ms, select
  (including placing the handle null) 2.8-6.6 ms (2026-11-06 run and audit 2's run). Measured on this PC only.

## F2a design: pieces packed in container objects (Hannes' choice: mixed backend)

Probes 2026-11-05 (hython, scratch `F:/cache/modelui/f2/probe*.py`):
- Stash SOP: its `stash` data parm takes a whole `hou.Geometry`; setting it is one undo step (undo restored the
  previous geometry) and it is saved with the hip.
- Copy to Points 2.0 with `useidattrib` + `idattrib` copies, per target point, the source piece whose attribute
  matches (control: sources a, b; points a, b, a -> three packed copies at the right positions). Target point
  attributes reach the copies only through `targetattribs` with `applyto` = `prims`.
- Real library, 2000 pieces over all 605 files: 2000 packed prims; build 1.1 s, first cook 14 s (loading 605 USD
  files once), moving one piece (new stash geometry) + recook 0.8-2.8 ms.
- Paths from `glob` carry backslashes on Windows; never put a path into VEX source text (it became escapes and
  matched nothing): pass it as a string parameter.

Layout of one container (a geometry object marked as a modelUI container):
- `sources`: per DISTINCT source file one chain usdimport (polygons) -> Attribute Create (`pf_source`, the file path
  as a string parameter) -> Pack; merged. A file used by 300 pieces is loaded once.
- `pieces`: a Stash SOP holding ONE POINT PER PIECE: `P`, `orient`, `scale`, `pf_source` (string), `pf_name`
  (string), `pf_piece` (int, unique in the container), `pf_hidden` (int).
  Clone dialog (F2b) adds, on instance/reference clones only: `pf_clone_kind` (string), `pf_clone_of` (int).
- `visible` (one wrangle over all points: drop hidden pieces) -> `copy` (Copy to Points, matched by `pf_source`,
  `pf_*` onto the packed prims): the display and render output.
- Why: native nodes and one batched cook for all pieces (rule 2/4); every edit (move, copy, hide, delete, rename) is
  one new stash geometry: one undo step, saved in the hip, no per-piece nodes, no per-piece Python cooking (Python
  only marshals the edit, house rule 2). Instance/Reference (F2b) can reuse the same points.
- Piece ids for the panels: container pieces are `("piece", <container session id>, pf_piece)`; objects keep their
  node session id. Piece selection is the scene model's own (pieces are not nodes); the viewport state draws it.
- Promote (first modifier): the piece becomes its own geometry object (its source, object transform = the piece
  transform) and its point leaves the stash, in one undo group.

## Resume pointer (F1 framework core: done; F2 next)

- Branch `modelui`; verify against `git log`. F1 code: `polyfactory/scripts/python/polyfactory/modelui/` (`switch.py`,
  `keys.py`, `input_layer.py`, `scene.py`, `explorer.py`, `appfilter/` with `appfilter.cpp`, `build.bat`,
  `pf_appfilter.dll`), `polyfactory/desktop/ModelUI.desk`, `polyfactory/python_panels/pf_modelui_explorer.pypanel`,
  `polyfactory/MainMenuCommon.xml` (polyfactory > modelUI | Houdini), `polyfactory/python3.13libs/uiready.py`
  (toggle hotkey Alt+Ctrl+Shift+X, memory only).
- Checks (all must exit 0):
  - `hython tests/modelui/check_scene_model.py`: 14 checks, 15 paired mutations red.
  - `hython tests/modelui/check_units.py`: keys record and filter construction, 4 checks, 4 paired mutations red.
  - `python tests/modelui/run_gui_f1.py`: own Houdini (prefs and packages in its output folder, only the polyfactory
    package; every visible window kept at x < -5000 by a 200 ms guard, the run stops otherwise; start waits for the
    main window and exits on any start error). Input goes the real path (QtTest on the QWindow; sendEvent to the
    window only for auto-repeat, scan codes and a lost release). It builds a mutated DLL (no window test) in
    `F:/cache/modelui/f1/mut`. All checks green in the first baseline (58, cold) and the last (60: plus the two
    2000-object Explorer checks, warm runs only), 62 paired source mutations red (credited only when the paired check itself is False; a
    mutation that cannot be applied fails the run), 1 exempt (`toggle_key_registered`: startup only); hotkeys are
    restored to the session start after every run. About 10 minutes: run it in the background; `PF_F1_QUICK=1` runs
    one baseline only. Output folder `F:/cache/modelui/f1/gui` (log `result.json.log`), or `PF_F1_SCRATCH=<folder>`:
    auditors set their own, a shared folder gets overwritten.
  - Probes (evidence, not checks): `tests/modelui/keys_probe.py` (hotkey routing, Q in pose),
    `tests/modelui/shortcut_probe.py` (shortcut override, inconclusive).
- Audits: 5 independent rounds on 2026-11-05 (findings and fixes below); the fifth gave the verdict yes.
- Next: F2 (Shift+drag clone with OBSERVE + later(), Clone dialog, Align, modifier stack panel) after Hannes chooses
  the scene backend (one object per piece, or kitbash pieces packed in container objects).
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
- Audit round 3 (2026-11-05): Shift+drag-on-handle answered yes (above). Fixed with checks: one owner per device
  (a held key and a drag run together; the holder of a key gets "other" for other keys and clicks, and may swallow
  them), a focus-window change cancels a held key but a popup does not, keys with focus outside the viewer are never
  offered, hidden Scene View tabs are ignored; the unreachable double-click offer was removed (Qt 6 sends the press
  first; the double-click is still swallowed under ownership). The GUI runner now fails a mutation it cannot apply.
- Audit round 4 (2026-11-05): fixed with checks: a key or click the key holder swallows via "other" takes its
  repeats and release with it (also after the holder's own key-up); "other" carries the viewer under the click or
  focus (a holder should only swallow clicks in a viewer); a deactivation ends a drag too; keys are offered during a
  drag; a key-up never ends a drag. The runner credits a mutation only when its paired check itself is False.
- **Max keys after off/on: not a defect, a test artefact.** Houdini sends a hotkey to the viewer under the
  cursor, not to Qt's focus widget. The check pressed keys without a cursor over the viewer, so after a desk switch they
  went nowhere visible (59 of 61 runs). Probe `tests/modelui/keys_probe.py`: plain hou.hotkeys add/remove/add and
  keys.apply/revert/apply work every time; switch on without a hover: Q/W do nothing; with the cursor over the viewer:
  Q, W, Q = select, pose, select on every switch-on. The check now hovers first, as a person does.
- **Hotkeys go to the viewer under the cursor, not to Qt's focus widget.** A check (or a feature) that presses keys
  must have the cursor over the viewer; without it a key after a desk switch reaches no visible viewer.
- **W then Q stayed in "pose" (root cause):** once the scene has objects, Houdini's own Q in the parent context
  (`h.pane.gview.repeat_current`, repeat current tool) wins over our Q in `h.pane.gview.state` while in "pose"
  (empty scene: ours wins). Probe `tests/modelui/keys_probe.py`, objects present, W then Q, keys only: Build and
  ModelUI desk x `new_select` and `volatile_select`: with that binding removed always "select", with it always "pose".
  Fix: a recorded "-" row in `keys.KEYS` unbinds it while modelUI is on (exact revert as for every change); Q stays
  on `new_select`. Check `w_then_q_selects` (W, E, R, T, then Q; mutations `repeat_current_kept`, `no_q_binding`).
- `max_keys_work` passed 58 of 61 runs: the 3 others were mutation runs that break keys (`demo_owns_keys` swallows
  them, `no_q_binding`, `wrong_desk`), not flakes; both baselines passed.
- Test hygiene: a mutation run can leave the session's hotkeys changed (`removals_not_reverted` deleted Houdini's Q
  for the rest of the session, which made `repeat_current_kept` stay green). The GUI suite now restores the hotkeys of
  the session start after every run.
- F2: two key gestures cannot chord: registration order decides, and while a key is held a second gesture is never
  offered its own key (only the holder's "other").

## F1 findings (2026-11-05, Houdini 22.0.442, Windows)

- **The C++ application filter works on Windows.** VS 2022 Build Tools (MSVC 14.44) + `$HFS/toolkit/include` +
  `$HFS/custom/houdini/dsolib/Qt6Core.lib`; `appfilter/build.bat` builds `pf_appfilter.dll` (objects in
  `F:/cache/modelui/appfilter_build`; rebuild for every Houdini with another Qt). The per-window Python fallback is
  kept and tested (fed through the top QWindow).
- Qt runs an application filter once per receiver of an event (window, widget, parents): the C++ filter calls
  back only for window receivers, where input enters, so every press and key reaches the gestures once.
- `QApplication.widgetAt()` and `topLevelAt()` return None where no screen is (an off-screen test window, a point
  between monitors): the layer finds the top-level widget whose QWindow receives the event and asks `childAt()`.
- Shift+LMB / Alt+LMB on the default viewer state (object level, select) pass our window filter but the viewer
  widget's own filters do not see them (Houdini takes them earlier there); this is NOT general: in the 'pose' state the
  GL widget saw press, move and release (audit 3). Observing gestures are therefore checked at the window.
- **Verified (audit 3, real path, 'pose' state): Shift+drag on a transform handle with an OBSERVE gesture.** The gesture
  sees the whole drag, the handle moves, and a copy made with `later(copyNodesTo)` after the first move is the one the
  handle then moves: the original stays at tx 0, the copy `a1` ends at tx 0.45. Shift is neutral on the handle in stock
  H22 (Ctrl = grid snap).
- For F2 (clone): store the original's transform at press and restore it after copying; which node the handle moves
  depends on when the copy lands (timing, not guaranteed).
- Unverified: Qt's shortcut-override event (type 51) path. Tried (audit 4, option a): `tests/modelui/shortcut_probe.py`
  feeds W through Qt's platform entry points with a test DLL (`tests/modelui/keyfeed/`: handleShortcutEvent, then
  handleExtendedKeyEvent). Result: the owned W was seen by the gesture (key, keyup) and the state stayed "objview",
  but the control (no gesture) did not switch the state either, so the probe cannot decide. Settling it needs a key
  path that triggers Houdini's hotkeys (a physical key press, or posting WM_KEYDOWN: not done without Hannes' OK).
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
- **Scene backend: mixed (Hannes, 2026-11-05, "definitely b").** Plain kitbash pieces live packed together in a few
  container objects (fast viewport with thousands of pieces); a piece becomes its own object with its own stack the
  moment it gets a modifier. The Scene Explorer and viewport selection still show every piece separately.
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
