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
  - F2b audit (agent-204, `F:/cache/modelui/audit_f2b/`) follow-ups, done 2026-11-10 (commits 5e030c6, 4e58ca0):
    C1 piece edits linear (`containers._by_id`; clone reads each container's transforms once): 100 pieces x 30
    instances 18 s -> 0.4 s, check `perf_clone_3000` (ratio to a reference beside it, ceiling 10; scanning
    mutations 16 / 83). S1 deleting an original (scene delete, Explorer delete) hands its network to the first
    remaining clone (`clone.hand_over`: the original's nodes copied in place of its "original" Object Merge, under a
    Reference's own nodes; the other clones show the heir; same undo step). S2 Instance/Reference copy every object
    setting but t/r/s/scale (material, display, render, pivot; expressions kept) and the parent link; objects turn
    about their pivot. S3 Copy of an Instance/Reference copies the root original's network (independent) with the
    clone's settings; an instance of an instance points at the root original (a reference of a reference keeps its
    own target). Low: an error halfway undoes the half-made clone; the dialog clones what was selected when it
    opened (not modal). Checks in check_clone (23 mutations) and gui_f2a `clone_dialog_ok` (`dialog_live_selection`).
    Blind spots: hand-over for clones in another network than the original's (only siblings are searched), piece
    clones of a deleted piece keep a dangling `pf_clone_of`.
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

## F2d Align (branch `modelui-align`; audit 1 by agent-202 fixed; no second audit, per Hannes' coordinator)

- What: Max's Align Selection, Quick Align and Normal Align for pieces and loose objects alike (`modelui/align.py`, a
  switch feature after `pieces_ui`). Align: Alt+Ctrl+A or polyfactory > Align..., click a target, the dialog. Quick
  Align: Alt+Ctrl+Shift+A, click a target (one undo step). Normal Align: Alt+Ctrl+N, click a face of the selection,
  then a face of the target, the dialog. While picking: a cross cursor over viewers only; Esc (wherever the keyboard
  focus is, except text fields) or a right click ends the pick; Alt and Space (Houdini's view states) and the middle
  button stay Houdini's; a selected target is refused (Max).
- Reference read: Autodesk help 2024 (Align, Quick Align, Normal Align, Aligning Objects).
- Decisions: every selected item is aligned on its own (Max); the current and target point (Minimum / Center / Pivot
  Point / Maximum) per axis, on tight world boxes (the item's points, not its local box turned into world space); a
  piece's pivot is its origin, an object's is `p` (probe: the fixed point of Houdini's rotation is
  `Vector3(p) * worldTransform()`); orientation: one axis turns the shortest way, two or three take the target's
  orientation, pivot and scale stay; Match Scale matches world row lengths; orientation and scale first, then the
  position on the new box. The preview runs outside the undo history; Apply is one undo step; Cancel, Esc, the close
  box and modelUI going off put the stored values back bit for bit (container stash points, object transform
  parameters). A result that needs shear (an object with a pivot rotation and a non-uniform scale under Match Scale, a
  piece in a non-uniformly scaled container) gets the nearest transform and a status warning (`Session.unstored`).
  Keys: `keys.KEYS` rows in context `h` on the menu item ids (commands registered in memory, reverted exactly); Max's
  own keys are Houdini's (Alt+A textport and network editor, Shift+A viewer loop select / home / pose, Alt+N File >
  New); the chosen ones had no binding in any of the 277 hotkey contexts (probe 2026-11-09). The pick gesture is asked
  first and gets Esc anywhere (`input_layer.add_gesture(first=True, keys_anywhere=True)`); a click intersects only the
  object the viewport draws under the cursor (`queryNodeAtPixel`), on the handle's proxy null every piece and object
  whose box the ray passes.
- Differences from Max: Houdini is Y up (Max's Z Position is Y here); points per axis and Apply closes the dialog
  (Max: one point choice for all axes, step by step with Apply); Match Scale is world scale (includes a container's or
  parent's scale); Normal Align offsets only along the normal (no in-plane X/Y offset) and moves a multi-selection
  rigidly; no normal arrows while picking (status prompts instead).
- Findings: `Geometry.intersect` on a packed prim turns the face normal like a direction (about 16 degrees off under a
  (10, 6, 8) piece scale): Align intersects the piece's own geometry in its space and uses the inverse transpose.
  `intersect` returns the geometric face normal, not `N`. `Geometry.boundingBox(transform)` transforms the box's
  corners (not tight). An object with a pivot rotation and a non-uniform scale is sheared: a full orientation match
  can still be stored, Match Scale cannot.
- Costs (hython, 2026-11-09): open + one preview with 500 of 2000 pieces 89-241 ms (6.9 s + 1 s before audit 1: a
  per-piece walk of the container's prims and points; now each container is read once, `containers.transforms`, and
  `containers.set_transforms` is linear); a scan over 2000 loose library meshes 51-106 ms, intersecting 2 of 2001
  geometries (box test first); a viewport click intersects 1.
- Checks: `hython tests/modelui/check_align.py`: 26 checks, 34 paired mutations red (oracle independent of align.py:
  Object Merge into world, Unpack, a least-squares local-to-world fit; the cost ceiling is a ratio to a reference
  workload timed in the same run, the scan is judged by its count). `PF_GUI_SCRIPT=gui_f2d.py run_gui_f1.py`: 19
  checks, each with its paired mutation (`view_state_click_passes` added at the merge with F2a's view-state rule).
  Blind spots: hidden pieces align by their pivot; the exact result for sheared items (only that it is reported);
  animated or locked parameters; the dialog's look; Esc and the close box on a dialog (Qt's reject(), the path Cancel
  takes, not driven); the menu bar itself (the check runs the shipped items' scripts; the keys reach the same items);
  the real mouse cursor (checked through `_cursor_tick` with points, the test windows are off screen); orthographic
  and multi-viewer picking.

## F2e copy/paste between scenes (branch `modelui-align`)

Ctrl+C / Ctrl+V (Ctrl+Shift+V = paste at the look-at point) over a viewer while modelUI is on; the same as polyfactory > Copy Selection / Paste / Paste at Look-at Point. The keys are main-menu symbols assigned in the viewer context (`h.pane.gview`), so they fire over viewers only and revert exactly on off; with nothing selected (copy) or an empty clipboard (paste) they warn in the status bar and do **not** fall back to Houdini's node copy/paste. Copy writes a clipboard folder (`$PF_MODELUI_CLIPBOARD`, default `F:/cache/modelui/clipboard`): `clipboard.json` (each piece's USD source, name, hidden flag, world matrix; each object's world matrix), written last by rename, and one `object_<i>.cpio` per loose object (`saveItemsToFile`). Copy is atomic: `clipboard.json` and the old object files are deleted first, so a copy that fails half way leaves an empty clipboard, never a JSON naming missing files. No geometry is copied; pieces are library references, so their USD source must be reachable from the target hip.

Paste keeps world transforms, or ("at look-at point") moves the set as a whole so its box centre and bottom stand on the point. Pieces go into the selected piece's container, else the first, else a new one; objects are reloaded under `/obj` and placed by world matrix. Pasted items end up selected; the paste is one undo step ("modelUI: paste"; menu pastes are deferred past Houdini's "Menu Action" group). Limits: an object inside a subnet pastes to `/obj` (its parent stays behind, world transform kept); channel references to other nodes dangle. Checks: `tests/modelui/check_clipboard.py` (copy and paste in separate hython processes, 9 checks, 11 paired mutations red), `tests/modelui/gui_f2e.py` (keys, menu, key revert).

## Feedback round 1 (2026-11-10, branch `modelui-fb1`)

Hannes' first-use notes. (1) `ModelUI.desk` no longer has the network editor / tree view / material palette section;
the stack panel's "open as nodes" floats a network editor when the desk has none. (2) The Explorer's "Add kitbash
pieces..." button is gone (menu item and `kitbash.add_dialog()` stay). (3) Asset Browser drops: with modelUI on and the
drop point over a Scene Viewer, `AssetDropHandler.handle_dropped_at` calls `kitbash.drop_asset`: one kitbash piece in the
mixed container, standing where the cursor ray meets y = 0 (look-at point when it misses), selected, one undo step.
Old failure: the handler created a SOP-type `pf_asset_place` node in the network editor's pwd (`/obj`, which is not an
`ObjNode`, so no geo was made) and `createNode` raised, which the handler's `except` only printed. (4) Alt+A / Alt+Shift+A /
Alt+N are bound to Align / Quick Align / Normal Align in context `h.pane.gview` only (reverted by `keys.revert`);
Alt+Ctrl variants kept; the Explorer has Align, Quick Align, Normal Align buttons with the keys in the tooltip.
Checks: `tests/modelui/gui_fb1.py` (13 mutations, each seen red). Unverified: a real OS drag from the browser, the exact
exception of the old drop in a GUI session (the cause is from reading the code and a headless createNode), Alt+A with a
real keyboard (QTest key events only).

## F12 feedback (branch `modelui-feedback`; implemented, unverified by an audit)

Press F12 anywhere in Houdini's main window while modelUI is on (or polyfactory > Send feedback (F12) any time): the
window freezes (a screen grab of the main window, all panes) under a full-window overlay. Draw with the pen (red / yellow /
cyan / white, S / M / L = 3 / 6 / 12 px), erase (a stroke or a note), click with Note to pin a 220 px note and type, write a
comment, Attach... files, then Ctrl+Enter (or Send) saves, Esc (or Cancel) closes (it asks first when there are markings).
Behaviour copied from Vela's feedback (`feedback.rs`), not its code. Status bar: "Feedback saved: <folder>".

Where it goes: `$PF_FEEDBACK_ROOT` (default `F:/ai/feedback/modelui`) `/<Windows user>/<YYYY-MM-DD_HHMMSS>/` (a second send in the
same second gets `-2`): `state.json` (written first), `screenshot.png`, `marked.png` (frame + markings + notes),
`markings.png` (transparent), `attachments/`, `feedback.json` LAST, so a folder with feedback.json is complete.
feedback.json: user, time (ISO), build (git short hash of the running polyfactory), comment, notes [{x, y, text, colour,
width}], strokes [{colour, width, points}], attachments [{name, from}], window {width, height, pixels_per_point, pixels},
"units": note and stroke positions are pixels of screenshot.png. state.json (taken when F12 is pressed): modelui_on,
houdini, hip_file, viewer {state, pwd}, selection [{id, kind, name}], scene {containers, pieces, objects}, modify_panel
{object, entry}, open_dialogs (visible polyfactory dialogs), log (last 200 lines of the `polyfactory.modelui` loggers; the
buffer exists while modelUI is on and sets that logger to INFO, restored on off). Each state section stands alone: an error
string replaces a broken one.

Code: `modelui/feedback.py` (state, markings rendering, folder writer, log buffer; the switch feature), `feedback_overlay.py`
(the window; the PNGs are rendered on the UI thread, files are written on a thread). Key: `("h", "h.pf_modelui_feedback",
"F12")` in `keys.py`, so it is reverted exactly with the other keys (Houdini 22 binds nothing to F12 by default: grep of
`config/Hotkeys`; the context is `h`, not the viewer's: a viewer-only binding did not fire over the viewer in the GUI run,
mutation `f12_viewer_only`). The menu item runs the overlay 250 ms later so its popup is not in the frozen frame.
Audit fixes (agent-231): a failed save removes its half folder and writes the same feedback to `%TEMP%/pf_feedback/<user>/...`,
then a dialog names where it went (`feedback.save_safe`); an unreadable attachment is listed with its error, not fatal; the
images are rendered on the UI thread, the worker only writes files (no `hou` there); a black screen grab retries with the
widget render and sets `"screenshot_black"` in feedback.json; `build` comes from git at F12 time, only when the repo above is
polyfactory's; switching modelUI off closes an open overlay (nothing sent).
Decision log (rule 2): Python is UI marshalling here (Qt overlay, file writing, HOM reads); no geometry.

Checks: hython `tests/modelui/check_feedback.py` (25 checks, 29 mutations red: write order observed at write time, every
json field, pixel colours / widths / alpha of markings.png and marked.png from given strokes, note box and text, same-second
collision, state sections, log ring 200 lines and removal); GUI `PF_GUI_SCRIPT=gui_feedback.py` through `run_gui_f1.py`
(F12 over the viewer and over the network editor opens the overlay; a stroke + note + comment + Ctrl+Enter writes a complete
folder with the right values; Esc asks with markings, Cancel keeps, Discard closes, nothing written; one overlay at a time;
key reverted exactly when off and F12 dead then; 15 mutations red). Blind spots: the real screen grab (the test window is
off screen, so screenshot.png there is black: only its size is judged; a real GL viewport grab and overlapping windows are
unchecked), pixels_per_point other than 1 in the GUI (the headless check uses 2.0 for the file maths), the Attach file
dialog, the menu entry itself, the look of the toolbar, text input inside the overlay (Ctrl+Enter works from the comment
field), key repeat, multi-monitor.

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

## F2c modifier stack (Modify panel; branch `modelui-stack`)

Status: implemented, unverified (independent audit pending). Resume: branch `modelui-stack` (worktree
`F:/projects/polyfactory-stack`), merged with `modelui` up to cc0f407; verify against `git log`. Next: the audit, then
merge into `modelui` (F2b's e18f8a5 and later come in then). Next item after that (coordinator decision 2026-11-10, not
built): stacks of clones follow Max: a modifier added to an original reaches its instances, a reference gets the
original's modifiers below its own, a modifier added to an instance goes on the shared stack; promoting an instanced
piece (`pf_clone_kind` / `pf_clone_of`) must keep the sharing (promote the original's stack once, instances point at it
through a packed Object Merge, as F2b does for objects).

Decisions (Hannes, 2026-11-05 and the F2c brief), as built:
- The stack lists **real Houdini SOP nodes**: an object's stack is its display node and that node's first-input
  ancestors (`stack.chain`), top = the display node, like Max. Nodes added in the network editor show too (their
  type's name and icon); the panel and the network editor always show the same thing.
- **No Max sub-object levels**: Houdini's own component selection is the "Edit Poly". Choosing a stack entry takes the
  viewer into the object (SOP level) and enters that entry's own viewer state (PolyExtrude's handle, Edit's tools,
  Subdivide, the lattice cage's Edit); clearing the entry, or choosing another object, brings the viewer back to object
  level in Q/W's state (select/pose).
- **Operation registry** `modelui/operations.py` (framework layer 5): one entry per node (label, node type, context,
  icon from the node type, group fields, pick inputs with the parms a pick sets, defaults, optional helper network,
  optional "whose viewer state"). First list: Extrude (PolyExtrude 2.0, dist 0.1), Subdivide, Bevel (PolyBevel 3.0,
  offset 0.05), Lattice (Lattice Deform with its own cage), Edit, plus PolyWire. A texturing mode adds a
  `MODES["texture"]` list of COPs; the panel takes a `mode`.
- **"Lattice" is ambiguous** (open question for Hannes): Max's Lattice modifier turns edges into struts and joints;
  Houdini's Lattice SOP is Max's FFD. Both are listed: "Lattice (Lattice Deform)" (FFD-like) and "PolyWire (Max's
  Lattice struts)"; removing one is deleting one registry line.
- **Lattice cage like FFD**: adding Lattice Deform builds a Bound (with divisions) of the lattice's input as the rest
  lattice and an Edit of it as the deformed lattice; the lattice's divisions follow the Bound's by expression (the docs
  require equal divisions). Choosing the Lattice entry shows the cage Edit's state.
- **Multi-input nodes and group fields as UI**: a "Pick <input>" button per registry input (the next object selected
  in the viewport or the Scene Explorer goes in through an Object Merge "Into This Object"; a container piece through an
  Object Merge with `@pf_piece=N` + Unpack; picking again replaces the old merge; the parms the input needs are set,
  e.g. PolyExtrude spine "Curve From Second Input", PolyBevel profile "Curve"), and a "Use selection" button per group
  field. Adding an operation uses the component selection when it was made on the node the new entry reads (the top,
  by default); its type goes to the node's group-type menu, or is converted (`hou.Selection.convert`) to the type the
  field takes.
- **Container pieces**: a selected piece shows as one row; its first modifier calls `containers.promote()` and adds
  the node inside ONE undo group ("modelUI: add <op>"); the stack then works on the new object.
- **Undo**: every stack edit is one undo step (add, move, on/off, delete, collapse, pick, use selection). Choosing
  entries and moving the viewer in and out are not undo entries.
- **Collapse** = Max's "Collapse To": a Stash SOP holding the chosen entry's evaluated geometry replaces it and
  everything below (the whole stack with no entry chosen); entries above stay; side inputs nothing else needs are
  deleted. **Delete** rewires whatever read the entry (any input) to the entry below, moves the display/render flags
  when it was the top and removes its side inputs (picked merges, cage). The base cannot be deleted, moved or switched
  off (as in Max). **Open as nodes**: the network editor goes into the object with the entry (or the top) current.
- **Desk**: the Modify panel (`pf_modelui_stack`) is the first, current tab of the top-right pane of ModelUI.desk; the
  parameter editor of the chosen entry is embedded below the stack (`hou.qt.ParmDialog`, a splitter between, 350/650).

Findings (H22.0.442; probes `F:/cache/modelui/f2c/probe*.py`, `F:/cache/modelui/f2c2/`):
- **Houdini runs Qt events inside `SceneViewer.setPwd()`** (and possibly other HOM calls): the panel's 0 ms coalescing
  timer fired there and rebuilt the stack list (`list.clear()`) while the list was still handling the click on an
  entry; the clicked item was deleted under Qt's mouse handler and Houdini segfaulted. Seen 4 times on 2026-11-09 (the
  run after the `enter_recorded` mutation, which left the viewer in "showhandle"; the next run's rows changed while
  going in), reproduced in one short run on 2026-11-10 with `faulthandler` (stack: `_entry_chosen` -> `_enter` ->
  `setPwd` -> `refresh` -> `list.clear`). Fix: every user action and every refresh runs under `ModifyPanel._hold()`; a
  refresh asked for meanwhile is deferred to the event loop after the action (`_pending`). Houdini writes no crash
  log for these; the GUI suites now write a Python fault stack (`result.json.fault.txt`) and the runner kills a
  crashed Houdini after 30 s (it hung after saving its crash .hip, which used to cost the 90 min timeout).
- **Houdini's viewer calls run long nested event loops**: `setPwd` / `setCurrentState` took up to ~2 s on the loaded PC,
  with Qt timers (the panel's, the test's steps) firing inside. Going out with `setPwd("/obj")` the viewer passes
  through "showhandle" and "geo" before ours ("select"), `currentState()` read right after can be stale, and in most
  runs Houdini entered the object's "geo" tool state once more AFTER the panel had finished (choosing another object
  while inside; after an undo of a promote it moved the viewer into the container, copytopoints::2.0). In "geo" a
  click (and Python's `setCurrentState("geo")`) CREATES a geometry object. Fix: the panel listens to the viewer's
  `StateEntered` events (`SceneViewer.addEventCallback`, removed when modelUI goes off) and, for `SETTLE` = 1 s after
  its own leave has finished, puts a non-select/pose state at object level (or a viewer inside a container) back to
  object level in Q/W's state (`_settle`). The window counts from the END of the leave because the nested loops made
  the leave itself take seconds. Also: when Houdini takes the viewer out first, the panel restores the state itself
  (`_went_in`), and `setPwd` may drop the object selection on the way out (some runs): the chosen object stays chosen
  (before: the object the viewer had been in was re-selected, overriding the person's choice).
- A panel deleted without `close_down` (Houdini destroying a pane's panel; `onDestroyInterface` names the panel in
  `hou.session`, which need not be the one going) kept its viewer and node callbacks and acted as a stray panel (seen
  in a GUI run). Its `destroyed` signal now drops them (`_forget`, from the panel's Python attributes).
- The previous builder's "panel not found" was an early form of the suite (the desk's panel keeps the class it was
  built with, so a mutation could not reach it): fixed before this round by driving a fresh panel from the live module
  in its own off-screen window. "entry_select_no_undo False / enter_recorded False" in its logs was the mutation run
  turning its paired check red, as intended, not a failing baseline.
- `hou.NodeType.defaultState()` returns "" for PolyExtrude/Edit/Lattice/Subdivide even in the GUI, but
  `SceneViewer.enterCurrentNodeState()` enters "polyextrude::2.0", "edit", "lattice", "subdivide".
- `SceneViewer.setPwd(<object>)` drops the object-level node selection; selecting the object again while the viewer
  is inside moves the viewer back to /obj (linked panes). So while the viewer is inside an object with nothing else
  selected, the stack shows that object; leaving puts its selection back.
- Back at /obj, Houdini may enter the current object's own tool state "geo", where a click CREATES a geometry object:
  the panel always returns to "select" or "pose". After an undo of a promote Houdini moved the viewer into the
  container (state copytopoints::2.0): a container is never a stack and the viewer comes back to /obj.
- `hou.Node.destroy()` splices: outputs are reconnected to the destroyed node's first input and the display flag moves
  to an input Houdini picks (a merge's second input in a probe), hence the explicit rewire and flags in `stack.delete`.
- Nested `hou.undos.group`s are one undo entry (promote's own group inside the add group).
- PolyExtrude 2.0 has no group-type parm (it guesses prims or edges); PolyBevel 3.0 and Edit have one; Subdivide's
  group parm is `subdivide`; Lattice Deform's method is its folder tab (`stdswitcher1`).
- `hou.qt.ParmDialog(node)` embeds Houdini's parameter editor (`setNode` to switch); it reports no size hint, and
  `QWidget.grab()` does not draw its contents (the panel pictures show an empty area there).
- A desk switch keeps the Python panel Houdini built first (onCreateInterface is not called again, nor by
  `setActiveInterface`); replacing that widget in its pane crashed Houdini in a test run.
- With an entry chosen the viewer is inside the object and the network editor (same link group) is there too.

Checks (every check paired with a source mutation seen red):
- `hython tests/modelui/check_stack.py`: 42 checks, 42 paired mutations red. Oracle: point positions compared exactly
  with a reference chain built next to the object (never with the code under test). Covers chain order, add (top,
  above an entry, defaults, group from the selection, type-menu and converted group, one undo, undo restores), move,
  on/off, delete (rewire, flags, side inputs, base never), lattice cage, pick (Object Merge, object space, replace,
  self refused, a container piece unpacked in world space), collapse (equals the chain, one undo, undo restores,
  collapse to an entry), promote + first modifier, registry matches Houdini (types, parms, menu tokens, input counts).
  Cannot see: Qt, viewer states, the parameter editor, hip save/load, time-dependent chains (collapse bakes the
  current frame), a side consumer below the collapse point keeps the nodes it reads.
- `PF_GUI_SCRIPT=gui_f2c.py PF_F1_SCRATCH=<own folder> python tests/modelui/run_gui_f1.py` through
  `bash F:/cache/modelui/gui_lock.sh`: CHECKS_GUI checks green in both baselines, MUTS_GUI paired mutations red
  (`MUTATIONS` in the file); a mutation run ends at its paired check (shorter; nothing a broken build does afterwards
  spills into later runs); every run starts with an empty undo history and leaves the viewer at /obj in "select"; a stray panel's viewer
  callback is removed between runs; the next step waits while the panel is inside a HOM call (nested loop); each step
  logs its suite line, the panel logs its viewer decisions (logger `polyfactory.modelui.stack_panel`, debug), and a
  segfault leaves its Python stack in `result.json.fault.txt` (the runner kills a crashed Houdini after 30 s).
  `PF_F2C_ONLY=<mutations>` (one baseline + those), `PF_F2C_ISOLATE=1` (a baseline after each), `PF_F1_QUICK=1`.
  Covered: in the desk and following the switch; follows the Scene Explorer, a viewport pick, network-editor inserts
  and deletes; `no_rebuild_inside_click` (the segfault above: setPwd made to run Qt's events, a pending refresh that
  changes a row, the entry chosen: the row item must still exist when the choice returns; mutation
  `refresh_inside_action`); an entry shows its state inside the object, its parameters (editor at least 200 px), no
  undo entry, stays inside with the object shown; no entry = back to object level; another object
  = back to object level in select/pose with that object chosen, also when setPwd drops the selection (emulated:
  setPwd + clearAllSelected) and when a late state change follows (emulated with "showhandle"; mutations
  `stays_inside_other`, `settle_ignored`, `leave_reselects_old`);
  Modifier List add (on top, its state, one undo, undo follows); component selection -> group; Up and Down, on/off
  box, Delete, Collapse, Open as nodes (from object level), each with undo followed; Pick wires the picked object and
  returns to the object; a piece shows one row, its first modifier promotes (one undo, undo restores, viewer back at
  object level); no stray object made during the whole run (`no_stray_objects`; mutation `wrong_object_state`
  leaves the viewer in "geo": 40+ objects); a panel deleted without close_down leaves no callback
  (`deleted_panel_lets_go`); modelUI off leaves no node or viewer callback.
  Not the real input path: the Modifier List dropdown (its `activated` signal is emitted), the on/off box
  (`setCheckState`), the component selection (`setCurrentGeometrySelection`), the entry in `no_rebuild_inside_click`
  (`setSelected`: under the mutation a real click kills Houdini and every later run).
  Cannot see: the look (and the parameter editor's contents: grab() leaves them empty), a handle DRAG inside an
  entry's state, Houdini's own reselect in a node state, hip reload, floating panels, the Delete key, Qt events run
  inside other HOM calls than setPwd (the guard covers every action; the check drives setPwd only), pieces_ui clicks
  inside an object (SOP level).

GUI run state (2026-11-10): "panel not found" was an early failure, gone since the 11-09 21:02 runs (`panel_in_desk`
green in every baseline since: the .pypanel is registered from this worktree's `python_panels/`, the desk names
`pf_modelui_stack`, the check finds it by `activeInterface().name()`). Full run full3 (`F:/cache/modelui/f2c2`): all
baselines green, two mutations green: `undo_not_followed` (fixed before full4, red there) and `leave_reselects_old`
(Houdini had already taken the viewer out, so the emulated selection drop in setPwd never ran; the check now drops it
after the panel's own `_to_object_level` too). full4 died in the harness (`cleanup` printed a deleted panel; now its
`id()`). Later runs: f2c6 showed the final baseline's follows_* red: a dead panel's scene watcher raised inside
`MixedScene._notify` and silenced the next panel; fixed in the product (each watcher isolated, dead ones removed,
check `dead_watcher_isolated`), and `no_stray_objects` now also spies on the states asked for. f2c8 full: PASS, all
mutations red. On the merged tree (2026-11-10, m1): 70 baseline lines ok, every mutation red except
`leave_reselects_old`, which is timing-dependent (red in f2c4 and f2c8, green in m1: it only differs from the product
when the panel is still inside the object at leave time). Known weak check; making it deterministic is open.

Known limits:
- "Use selection" takes the viewer's component selection only when it was made on the entry's INPUT node; Houdini
  selects on the displayed (top) node, so for an existing entry the practical way is the entry's own state
  (PolyExtrude/PolyBevel/Edit reselect themselves). At add time the default (top) works.
- One object at a time (Max can add one modifier to several objects as an instance): several selected = no stack.
- A lattice moved above other entries keeps its cage built from where it was added.

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
- Align (F2d): Python, as transform maths on a handful of matrices plus UI marshalling (dialogs, picking); tight boxes
  read point positions once per item (`pointFloatAttribValues`) and transform them with numpy; no geometry is created or
  changed, the result goes through `pieces_ui.set_xforms` (one stash edit per container).
- Modifier stack (F2c): `stack.py`, `operations.py` and the Modify panel `stack_panel.py` only create, wire, flag and
  select nodes, follow the viewer and build Qt widgets (marshalling). The geometry work is the nodes': collapse stores
  the evaluated geometry in a Stash SOP (`geometry().freeze()` is a copy, no per-element Python), a picked piece is
  chosen by an Object Merge group expression, the selection conversion is `hou.Selection.convert`.

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
- Align: Align to target (position min/center/pivot/max per axis, orientation, scale), quick align, normal align
  (F2d: built, see F2d Align).
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
