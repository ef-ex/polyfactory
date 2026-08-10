# Graph Report - polyfactory  (2026-08-10)

## Corpus Check
- 123 files · ~132,688 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1678 nodes · 2590 edges · 96 communities (83 shown, 13 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 290 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `f993cfd1`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]
- [[_COMMUNITY_Community 38|Community 38]]
- [[_COMMUNITY_Community 39|Community 39]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 55|Community 55]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 114|Community 114]]

## God Nodes (most connected - your core abstractions)
1. `AssetBrowserWidget` - 37 edges
2. `Result` - 36 edges
3. `TagInputWidget` - 35 edges
4. `AssetDatabase` - 34 edges
5. `PyPushButton` - 24 edges
6. `BaseParmWidget` - 24 edges
7. `AssetInfoPanel` - 23 edges
8. `AssetExportDialog` - 23 edges
9. `HoverOutlineMixin` - 23 edges
10. `PyLeftMenuButton` - 22 edges

## Surprising Connections (you probably didn't know these)
- `pf_perlin_d()` --calls--> `pf_qerp_td()`  [INFERRED]
  polyfactory/ocl/include/pf_noise.h → polyfactory/ocl/include/pf_util.h
- `pf_vnoise()` --calls--> `pf_interp()`  [INFERRED]
  polyfactory/ocl/include/pf_noise.h → polyfactory/ocl/include/pf_util.h
- `HoverSlider` --uses--> `PyPushButton`  [INFERRED]
  polyfactory/scripts/python/polyfactory/asset_library/asset_browser_widgets.py → polyfactory/scripts/python/polyfactory/ui_framework/widgets/py_push_button/py_push_button.py
- `HoverSlider` --uses--> `HoverOutlineMixin`  [INFERRED]
  polyfactory/scripts/python/polyfactory/asset_library/asset_browser_widgets.py → polyfactory/scripts/python/polyfactory/widgets/hover_outline.py
- `HoverSlider` --uses--> `TagInputWidget`  [INFERRED]
  polyfactory/scripts/python/polyfactory/asset_library/asset_browser_widgets.py → polyfactory/scripts/python/polyfactory/widgets/tag_input.py

## Import Cycles
- 1-file cycle: `polyfactory/scripts/python/polyfactory/ui_framework/__init__.py -> polyfactory/scripts/python/polyfactory/ui_framework/__init__.py`
- 1-file cycle: `polyfactory/scripts/python/polyfactory/viewer_utils/__init__.py -> polyfactory/scripts/python/polyfactory/viewer_utils/__init__.py`
- 1-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 2-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_numeric.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 2-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_base.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 3-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_numeric.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_base.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 3-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/widgets.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_numeric.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 3-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/widgets.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_base.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 4-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/widgets.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_numeric.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_base.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`

## Communities (96 total, 13 thin omitted)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (17): BaseParmWidget, ExpressionDialog, Base class for parameter-bound widgets., Get current parameter value. Override in subclasses., Set parameter value. Override in subclasses., Update widget from parameter (called by BindingManager)., Update widget display. Override in subclasses., Update visual feedback for expression state.                  This base implem (+9 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (36): Architecture, Automated verification via hython, Binding Types, Building, Copernicus OpenCL HDA Development Guide, Critical OpenCL vs GLSL Differences, Critical Rules, devScript Structure (+28 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (33): export_batch_group(), Export a single asset group detected by detect_asset_groups.      Converts pri, SQLite database management for asset library, Handle export button click, _build_export_network(), _cleanup(), export_asset(), _export_geometry() (+25 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (24): build_profile_points(), _ensure_point_attribs(), geo_to_elements(), get_template(), profile_to_geo(), CityGen - street cross-section templates and profile construction.  Design: idea, Fill defaults into a raw element list. Authored keys always win., Summary attributes stamped onto the street edge.      Names follow the common in (+16 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (14): line(), Runnable check for street graph construction.  No Houdini needed.      python, A cul-de-sac is legitimate; only SHORT dead ends are noise., Removing one stub can expose another behind it., 3x3 crossing streets, each overshooting the outer ones.          Every street, Sampled straight line from a to b, so welding sees interior points., Guards the documented precondition: two streets that cross without         shar, The classic spatial-hash bug: neighbours must be searched too. (+6 more)

### Community 6 - "Community 6"
Cohesion: 0.22
Nodes (3): PyCircularProgress, QColor, Set background color for expression state.

### Community 7 - "Community 7"
Cohesion: 0.10
Nodes (17): graph_is_planar(), no_duplicate_lot_footprints(), no_loose_points(), no_orphan_components(), no_scratch_attribs(), no_scratch_groups(), no_short_graph_segments(), no_zero_area_prims() (+9 more)

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (14): HoverComboBox, QComboBox with animated hover outline, AssetBrowserDialog, AssetDropHandler, Asset Browser UI - Grid view of assets with search and filtering, Standalone asset browser dialog, Show the asset browser dialog, Handles drops from the asset browser onto Houdini's viewport or network     edi (+6 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (26): build(), dedupe_edges(), _dist(), _dist2(), edge_length(), endpoint_degree(), junctions(), prune_stubs() (+18 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (4): AssetPlaceState, Key DOWN / UP transitions for clean drag start/end.         Works as a suppleme, Show or hide the xform handle and update the prompt message., Interactive placement state for the pf_asset_place HDA.

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (29): float2, float3, float4, pf_hash1(), pf_hash21(), pf_hash22(), pf_hash2d(), pf_hash43() (+21 more)

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (14): createViewerStateTemplate(), KitbashPlacementState, Kitbash Placement State - Interactive viewport placement for assets  NEW WORKF, Place the currently selected mesh at cursor position, Handle keyboard events, Update menu state before opening, Interactive state for placing kitbash assets in viewport, Handle context menu selections (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (22): Parm, copy_parameter(), delete_expression(), get_expression_language(), get_expression_string(), get_parm_color(), get_parm_display_value(), has_expression() (+14 more)

### Community 15 - "Community 15"
Cohesion: 0.10
Nodes (19): Node, Binding Manager - Central coordinator for parameter-widget synchronization  Ma, Initialize binding manager for a node.                  Args:             nod, Hover Outline Mixin - Animated blue outline on hover for any widget, Polyfactory Widgets Module  Qt widgets for Houdini workflows.  Submodules:, HoudiniGroupBox, HoudiniHLayout, HoudiniVLayout (+11 more)

### Community 16 - "Community 16"
Cohesion: 0.05
Nodes (41): Accessing Package Assets, Asset Database, Branch Structure, Code Quality - Error Handling, Code Style: Functional Over Object-Oriented, Common Patterns, Creative / Procedural Tool Requests Require Design Breakdown First, Critical Conventions (+33 more)

### Community 17 - "Community 17"
Cohesion: 0.14
Nodes (14): 4. Stage design, Chaotic / organic patterns — clarified, not scrapped, Dead ends are the exception, not the norm — and the fix is in the papers, Layers — the change bridges force, Networks are typed, S0 — Domain, S1 — Field (pluggable generators), S2 — Trace (+6 more)

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (19): 10. Explicit non-goals for v1, 1. Hard constraints, 2. Diagnosis: why the previous attempts produced unsatisfying output, 3. Architecture: staged pipeline with schema contracts, 4d. Measured state of the shipped build — 2026-08-09 (pre-fix), 4e. Independent audit findings — 2026-08-09, 4f. Civil-engineering sweep — 2026-08-09. What it changes, 4g. Second audit — the dead-end build, 2026-08-09 (+11 more)

### Community 19 - "Community 19"
Cohesion: 0.23
Nodes (13): Module reloader for Polyfactory development  Intelligently reloads modules for, Reload widget library modules., Reload asset library modules., Reload viewer utilities modules., Reload UI framework modules (PyOneDark-based)., Reload all Polyfactory modules., Internal helper to reload a list of modules., reload_all() (+5 more)

### Community 21 - "Community 21"
Cohesion: 0.18
Nodes (7): AssetPlaceNodeUI, Asset Place HDA UI - Python Panel for pf_asset_place node.  Shows the full ass, Python Panel widget for pf_asset_place HDA.      Embeds the full AssetBrowserW, Called by onNodePathChanged — updates which node we drive., Reload asset list (called on pane activation)., Highlight the thumbnail matching the node's current asset_id., User double-clicked an asset — push into node parms.

### Community 22 - "Community 22"
Cohesion: 0.12
Nodes (3): PyDiv, PyLeftMenu, PyDiv

### Community 23 - "Community 23"
Cohesion: 0.04
Nodes (38): HoverSlider, QSlider with animated hover outline, AssetBrowserWidget, Asset browser with grid view, search, and filters, Load assets from database, Filter assets based on search, category, and tags, Update grid with filtered assets, Handle asset single-click.  Ctrl+click toggles, Shift+click selects range. (+30 more)

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (36): 1. Create the HDA, 2. Add Python Panel Interface, 3. Set Interface as Default, 4. Configure Multiparm Structure, Add Custom Controls, Adding Assets, Asset Browser Empty, Asset Browser Section (+28 more)

### Community 26 - "Community 26"
Cohesion: 0.16
Nodes (13): Geometry, Matrix4, align_transform_to_normal(), extract_rotation_from_matrix(), get_geometry_under_cursor(), Raycasting utilities for viewer states Pure functions for ray-geometry intersec, Get geometry under cursor using ray intersection.          Args:         ui_e, Raycast against geometry and return hit information.          Args:         o (+5 more)

### Community 27 - "Community 27"
Cohesion: 0.32
Nodes (7): open_asset_browser(), Setup and test script for kitbash workflow  To use: 1. First create the pf_ki, Register the kitbash placement Python state, Open the asset browser dialog, Test the complete workflow, register_kitbash_state(), test_workflow()

### Community 28 - "Community 28"
Cohesion: 0.25
Nodes (7): get_modifier_state(), is_click(), is_key_pressed(), Input handling utilities for viewer states Functions for processing mouse/keybo, Check if UI event is a click (Picked reason with button down).          Args:, Check if specific key is pressed.          Args:         ui_event: Houdini UI, Get state of modifier keys.          Args:         ui_event: Houdini UI event

### Community 29 - "Community 29"
Cohesion: 0.33
Nodes (4): get_multiparm(), get_multiparm_dict(), Get parms of multiparm parameter      Args:         multi (hou.Parm): multipa, Get parms of multiparm as dictionary      Args:         multi (hou.Parm): mul

### Community 30 - "Community 30"
Cohesion: 0.29
Nodes (4): chunk_array(), Chunks input array into multiple arrays with length of chunksize      Args:, unpacks arrays to defined number of elements assigning default value if not exis, unpack()

### Community 31 - "Community 31"
Cohesion: 0.05
Nodes (37): 1. Context Window Management, 1. Houdini Python Panel (PySide6 UI), 2. Error Recovery, 2. LLM Integration Layer, 3. Scene Context Extractor, 3. Undo/Redo Integration, 4. Code Executor, 4. Cost Control (+29 more)

### Community 32 - "Community 32"
Cohesion: 0.08
Nodes (16): HoverListWidget, QListWidget with animated hover outline, HoverOutlineMixin, HoverOutlineMixin, Initialize hover outline animation.                  Args:             color:, Get current hover outline opacity (0.0 to 1.0), Set hover outline opacity (0.0 to 1.0), Start fade-in animation on hover (+8 more)

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (33): Adding New Placement Modes, Adding Viewer Utils Functions, Align to Mesh (Default), Alignment Issues, Architecture, Asset Data Flow, Components, Core Functions (+25 more)

### Community 34 - "Community 34"
Cohesion: 0.07
Nodes (16): FlowLayout, Layout that wraps widgets to multiple lines like text flow, Tag input widget with autocomplete and chip display, Set the list of available tags for autocomplete                  Args:, Get current list of tags                  Returns:             List of tag st, Set the current tags                  Args:             tags: List of tag str, Show dropdown menu with all available tags, Add a tag chip                  Args:             tag_text: Tag string to add (+8 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (13): EnhancedInputField, Base Parameter Widgets - Label, InputField, BaseParmWidget, ExpressionDialog, Enhanced InputField with all Houdini parameter polish features:     - Hover eff, ParmInt, Numeric Parameter Widgets - ParmFloat, ParmInt  Float and integer parameter wi, Integer parameter widget using Enhanced InputField with slider.          Combi, Handle value change from InputField., Update widget from parameter value. (+5 more)

### Community 36 - "Community 36"
Cohesion: 0.08
Nodes (13): AssetInfoPanel, Handle resize to update preview image size, Create styled label for form, Load turntable frames for animation, Display a specific frame, Display asset information, Load full turntable sequence on hover, Return to frame 5 on leave (+5 more)

### Community 37 - "Community 37"
Cohesion: 0.29
Nodes (7): Higher-degree junctions — untested, and structurally unreachable from the field, Plazas and roundabouts at degenerate points, S5 — Intersections, The invariant that was violated: **every corner is an arc, always**, Three constructions adopted from the civil sweep — 2026-08-09, Two rules the design left open, decided 2026-08-09, What the literature adds

### Community 39 - "Community 39"
Cohesion: 0.38
Nodes (4): draw_normal_indicator(), Drawing utilities for viewer states Pure functions for viewport drawing helpers, Draw line indicating surface normal.          Args:         drawable: Houdini, Viewer utilities for Houdini viewer states Reusable library components for rayc

### Community 40 - "Community 40"
Cohesion: 0.08
Nodes (24): 1. Open HDA for Editing, 2. Go to Interactive Tab, 3. Add Python Panel Section, 4. Set Python Panel Code, 5. Enable Python Panel Display, 6. Apply and Accept, 7. Test the UI, 8. Place an Asset (+16 more)

### Community 41 - "Community 41"
Cohesion: 0.40
Nodes (4): get_prims_at_path(), get_sdf_type(), generator which returns all prims of type     which are child of given path, get Sdf Value Type      Args:         typ (str) : requested usd type     Ret

### Community 42 - "Community 42"
Cohesion: 0.12
Nodes (14): QWidget, BindingManager, Create a dropdown menu widget bound to a parameter., Create a color picker widget bound to a parameter tuple., Manages parameter bindings for an HDA Python Panel UI.          Coordinates up, Create a button widget (not bound to parameter)., Register a widget-parameter binding., Poll for external parameter changes (from UI, expressions, etc). (+6 more)

### Community 43 - "Community 43"
Cohesion: 0.12
Nodes (17): block_boundary_closes(), every_mouth_has_a_road(), lots_tile_blocks(), no_nonplanar_y(), no_sweep_fold_after_trim(), plaza_disc_is_clear(), S7's collect-and-close invariant, which nothing else asserts.      The block bou, Run the SHIPPED S3b clamp on the inputs that broke the first one.      This is t (+9 more)

### Community 44 - "Community 44"
Cohesion: 0.67
Nodes (3): dropAccept(), get_drop_context(), get the context where the drop happened      Returns:         hou.NetowrkEdit

### Community 45 - "Community 45"
Cohesion: 0.07
Nodes (27): 1. The vision (Hannes, 2026-08-08), 2.1 No constants — the override cascade, 2.2 Validation is advisory, never a wall, 2.3 Intervene at any stage — the authoring model, 2. Art direction is the first principle, 3. Terminology: "biome" was overloaded — split it, 4. Cross-subsystem contracts, 4b. APEX — assessed 2026-08-08. Real fit, but not yet (+19 more)

### Community 46 - "Community 46"
Cohesion: 0.10
Nodes (19): Asset Browser as Pane, Asset Browser Redesign, Asset Library & Kitbash Workflow Redesign, Asset Placement Workflow, Browser Structure (Blender-Style Layout), Custom HDA Design, Drag & Drop, Export Workflow (+11 more)

### Community 47 - "Community 47"
Cohesion: 0.10
Nodes (13): AssetExportDialog, Export UI Panel for Asset Library, Dialog for exporting selected geometry to asset library, Load existing categories from database, Handle name confirmation (Enter key or lost focus) - auto-suggest category and t, Update the export path preview, Get the export configuration data, Show the export dialog with current selection          Args:         parent: (+5 more)

### Community 48 - "Community 48"
Cohesion: 0.15
Nodes (7): ParmMenu, Block user input when expression is active., Dropdown menu widget with enhanced label., Menu parms can be int or string - get the string token., Update visual feedback for expression state., Block user input when expression is active., Reset parameter to default value (Ctrl+MMB on label).

### Community 49 - "Community 49"
Cohesion: 0.11
Nodes (17): Alternative: Manual Python Panel Assignment, Asset browser is empty, Automatic Setup via HDA Type Properties, Check 1: Python Panel Definition Exists, Check 2: HDA Type Properties, Check 3: Test the Node, Complete Verification Script, HDA Configuration for pf_kitbash Python Panel (+9 more)

### Community 50 - "Community 50"
Cohesion: 0.11
Nodes (17): Categories, Copernicus COP, Houdini / HDA Python API, How to Use This File, Known Pitfalls Log, OPEN -- Asking questions already answered in Galaxia documentation, OPEN -- `hda_node.setParmTemplateGroup()` does NOT persist into HDA file, OPEN -- menuType.Normal with item generator renders as full combobox, not text+arrow (+9 more)

### Community 51 - "Community 51"
Cohesion: 0.16
Nodes (7): EnhancedLabel, Add hover glow effect., Remove hover glow effect., Apply or remove hover visual feedback., Intercept label interactions., Enhanced QLabel with Houdini parameter polish features:     - Hover effects (li, Update visual style based on hover state.

### Community 53 - "Community 53"
Cohesion: 0.24
Nodes (3): PyGrips, Widgets, QFrame

### Community 55 - "Community 55"
Cohesion: 0.11
Nodes (12): BaseParmWidget, ParmFloat, Handle value change from InputField., Update widget from parameter value., Update visual feedback for expression state., Reset parameter to default value (Ctrl+MMB on label)., Toggle slider visibility (LMB on label)., Float parameter widget using Enhanced InputField with slider.          Combine (+4 more)

### Community 56 - "Community 56"
Cohesion: 0.13
Nodes (7): ParmTuple, ParmColor, Color picker widget using Houdini's native ColorField., Handle color change from ColorField., Update widget from parameter value., Update visual feedback for expression state., Reset parameter to default value (Ctrl+MMB on label).

### Community 59 - "Community 59"
Cohesion: 0.33
Nodes (6): build_all(), install_hdas(), CityGen test cases — builds every scene the checks run against.  Scenes are buil, hython does not load the polyfactory package, so $POLYFACTORY is unset     and `, Build every case. Returns {case_name: {role: node}}., setup_env()

### Community 60 - "Community 60"
Cohesion: 0.17
Nodes (12): createViewerStateTemplate(), _ground_plane_hit(), _normal_to_euler(), Asset Placement Viewer State for pf_asset_place HDA.  Two modes (toggle with Q, Intersect against ONLY the geometry connected to SOP input 0.          Input g, Raycast against input geometry only, set t/r parms on node., Return XYZ Euler angles (degrees) that rotate +Y to align with normal.      Bu, Intersect ray with Y=0 ground plane. Returns hit position or None. (+4 more)

### Community 61 - "Community 61"
Cohesion: 0.07
Nodes (19): _aabbs_overlap(), detect_asset_groups(), next_free_filename(), Batch Kitbash Importer - AABB-based asset detection and batch export backend, Find the next available numbered filename (no extension).      Scans both the, Detect asset groups in a SOP node using connectivity + AABB overlap.      Each, Return True if two AABBs (min_x,min_y,min_z,max_x,max_y,max_z) overlap., Read a string primitive attribute value; return default if absent. (+11 more)

### Community 62 - "Community 62"
Cohesion: 0.20
Nodes (9): Known-failing at time of writing, Layout, Numbers first, renders second, polyfactory tests, Test the union, and every branch, The baseline, The closure sweep, and why it is a file rather than a habit, The four cases (+1 more)

### Community 63 - "Community 63"
Cohesion: 0.50
Nodes (4): main(), Run every CityGen geometry check in a throwaway Houdini session.      hython tes, All checks for one city. Returns [Result]., run_case()

### Community 67 - "Community 67"
Cohesion: 0.29
Nodes (4): ParmString, Update visual feedback for expression state., String input widget with enhanced label., Reset parameter to default value (Ctrl+MMB on label).

### Community 69 - "Community 69"
Cohesion: 0.67
Nodes (3): 3b. The unanimous baseline — where all four sources agree, Decision — 2026-08-09, What this changes

### Community 70 - "Community 70"
Cohesion: 0.50
Nodes (3): 123.py - Auto-loaded on Houdini startup Registers custom viewer states, Register all Polyfactory viewer states, register_viewer_states()

### Community 71 - "Community 71"
Cohesion: 0.25
Nodes (9): _blobs(), city_is_fully_paved(), lots_clear_of_junctions(), _raster_grid(), _rasterise(), Even-odd fill of every polygon in `geo` onto a boolean XZ grid., Connected components of a boolean mask as (area, cx, cz), largest first.      Ru, No lot may lie inside a junction. The other half of city_is_fully_paved.      `c (+1 more)

### Community 72 - "Community 72"
Cohesion: 0.13
Nodes (6): Ui_RightColumn, Themes, SetupMainWindow, UI_MainWindow, object, Ui_MainPages

### Community 73 - "Community 73"
Cohesion: 0.24
Nodes (4): _ToolTip, _ToolTip, _ToolTip, QLabel

### Community 74 - "Community 74"
Cohesion: 0.22
Nodes (9): _arc_lengths(), every_corner_is_an_arc(), _fit_circle(), _pos_at_length(), Kasa algebraic circle fit in XZ. Returns (cx, cz, r, max_residual) or     None w, Position at arc length `s` along a polyline — what s5j_trim's     pfsg_pos_at_le, A junction corner that is not a correctly-placed fillet arc.      Measured 50/50, THE S5 SEAM: the road's terminal cross-section IS the mouth's cap segment. (+1 more)

### Community 76 - "Community 76"
Cohesion: 0.26
Nodes (3): Settings, PyWindow, Styles

### Community 78 - "Community 78"
Cohesion: 0.10
Nodes (12): AssetThumbnailWidget, _load_pixmap_cached(), Asset Browser Widgets - Low-level widget classes extracted from browser_ui.py., Return a cached, pre-scaled pixmap for path, loading from disk on miss., Individual asset thumbnail with animated hover outline, Update thumbnail size dynamically without re-reading disk, Scale the cached pixmap to the current thumb size (no disk I/O), Toggle selection highlight on this thumbnail. (+4 more)

### Community 79 - "Community 79"
Cohesion: 0.09
Nodes (41): accepted(), accepted_seam_distribution(), build_trace(), configs(), _cross(), gate_matches_vex(), gates(), gates_sagitta() (+33 more)

### Community 80 - "Community 80"
Cohesion: 0.50
Nodes (3): export_selected_to_library(), Hotkey command script to open asset export dialog This script can be bound to a, Main function to trigger asset export dialog

### Community 84 - "Community 84"
Cohesion: 0.25
Nodes (7): Attribution, Credits, Modifications, Polyfactory Integration, Polyfactory UI Framework, Structure, Usage in Polyfactory

### Community 86 - "Community 86"
Cohesion: 0.50
Nodes (4): lot_aspect_ratio(), _obb(), Minimum-area oriented bounding box in XZ, by rotating calipers over the     edge, Ribbons, not rectangles. Parcels 6.2 m wide and 62 m deep ship viable.      city

### Community 88 - "Community 88"
Cohesion: 0.50
Nodes (4): merged_city_self_intersections(), Intersection Analysis reports 0 for a valid box, grid and kerb step —     verifi, THE gap. Roads and junction patches interpenetrate at every junction and     the, self_intersections()

### Community 89 - "Community 89"
Cohesion: 0.14
Nodes (14): attribute_schema(), centreline_curvature_within_class(), dead_ends(), junction_boundary_is_simple(), lots_are_simple_polygons(), no_downward_faces(), CityGen geometry checks — the assertions, in one place.  Every check here caught, Conformance with the schema table. Identity must survive to the final     geomet (+6 more)

### Community 90 - "Community 90"
Cohesion: 0.06
Nodes (31): AssetInstanceWidget, createInterface(), KitbashNodeUI, PlacedAssetsListWidget, Kitbash HDA UI - Python Panel interface for pf_kitbash node  NEW WORKFLOW: -, Create styled spinbox, Load values from node parameters, Handle spinbox value change (+23 more)

### Community 91 - "Community 91"
Cohesion: 0.09
Nodes (5): Ui_LeftColumn, PyIcon, PyLeftColumn, PySlider, QSlider

### Community 96 - "Community 96"
Cohesion: 0.33
Nodes (6): 4c. Implementation status — 2026-08-09, Before and after, per criterion, Overnight run — 2026-08-09/10, The loop-closure gate, per-gate — measured, and two entries in `80dc19c` were wrong, ⚠️ The road-under-chord metric was ill-posed. Use the pavement deficit, The sagitta gate is gone. The seam is bounded instead — 2026-08-10

### Community 99 - "Community 99"
Cohesion: 0.40
Nodes (5): Before and after, per criterion, S3b — Turns: a bend is not a junction, and gets its own solver, Still unguarded after this pass — recorded, not fixed, The clamp is a radius floor and that is not the same as a smooth street — 2026-08-10, ⚠️ The clamp must be a SOLVE, not a fixed sweep count — measured 2026-08-09

### Community 105 - "Community 105"
Cohesion: 0.10
Nodes (8): _handle_drop(), Forward thumbnail drop to the browser-level signal., Double-click in the floating browser: create and connect the         asset plac, Called after a drag completes. If the cursor is outside our own         window,, Create a pf_asset_place node in the current network, wire it to the         cur, PyToggle, QCheckBox, QPoint

### Community 114 - "Community 114"
Cohesion: 0.67
Nodes (3): S8 — Lots, The three subdivision modes — both of the first two are required, ⚠️ Voronoi is wrong for lots. Rewritten 2026-08-09.

## Knowledge Gaps
- **278 isolated node(s):** `Project Overview`, `Package Structure`, `Environment Variables`, `Temporary / One-Off Scripts`, `Houdini Bridge - AI Agent Integration` (+273 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **13 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PyPushButton` connect `Community 8` to `Community 32`, `Community 36`, `Community 101`, `Community 38`, `Community 78`, `Community 47`, `Community 23`, `Community 90`, `Community 91`?**
  _High betweenness centrality (0.101) - this node is a cross-community bridge._
- **Why does `HoverOutlineMixin` connect `Community 32` to `Community 34`, `Community 36`, `Community 8`, `Community 78`, `Community 15`, `Community 47`, `Community 23`, `Community 90`?**
  _High betweenness centrality (0.073) - this node is a cross-community bridge._
- **Why does `Result` connect `Community 7` to `Community 71`, `Community 72`, `Community 74`, `Community 43`, `Community 20`, `Community 86`, `Community 88`, `Community 89`, `Community 92`?**
  _High betweenness centrality (0.057) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `AssetBrowserWidget` (e.g. with `AssetPlaceNodeUI` and `._setup_ui()`) actually correct?**
  _`AssetBrowserWidget` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TagInputWidget` (e.g. with `AssetInfoPanel` and `._setup_ui()`) actually correct?**
  _`TagInputWidget` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AssetDatabase` (e.g. with `next_free_filename()` and `AssetBrowserDialog`) actually correct?**
  _`AssetDatabase` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `PyPushButton` (e.g. with `AssetInfoPanel` and `._setup_ui()`) actually correct?**
  _`PyPushButton` has 19 INFERRED edges - model-reasoned connections that need verification._