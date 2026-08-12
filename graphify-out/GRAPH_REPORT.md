# Graph Report - polyfactory  (2026-08-12)

## Corpus Check
- 124 files · ~220,911 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1836 nodes · 2795 edges · 109 communities (99 shown, 10 thin omitted)
- Extraction: 90% EXTRACTED · 10% INFERRED · 0% AMBIGUOUS · INFERRED: 291 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `021c8c57`
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
- [[_COMMUNITY_Community 24|Community 24]]
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
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 92|Community 92]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 96|Community 96]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]
- [[_COMMUNITY_Community 99|Community 99]]
- [[_COMMUNITY_Community 100|Community 100]]
- [[_COMMUNITY_Community 101|Community 101]]
- [[_COMMUNITY_Community 102|Community 102]]
- [[_COMMUNITY_Community 103|Community 103]]
- [[_COMMUNITY_Community 104|Community 104]]
- [[_COMMUNITY_Community 105|Community 105]]
- [[_COMMUNITY_Community 106|Community 106]]
- [[_COMMUNITY_Community 107|Community 107]]
- [[_COMMUNITY_Community 108|Community 108]]

## God Nodes (most connected - your core abstractions)
1. `Result` - 47 edges
2. `AssetBrowserWidget` - 37 edges
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

## Communities (109 total, 10 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.14
Nodes (3): PyDiv, PyTitleBar, Polyfactory UI Framework =========================  Modern Qt widget library

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (17): BaseParmWidget, ExpressionDialog, Base class for parameter-bound widgets., Get current parameter value. Override in subclasses., Set parameter value. Override in subclasses., Update widget from parameter (called by BindingManager)., Update widget display. Override in subclasses., Update visual feedback for expression state.                  This base implem (+9 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (36): Architecture, Automated verification via hython, Binding Types, Building, Copernicus OpenCL HDA Development Guide, Critical OpenCL vs GLSL Differences, Critical Rules, devScript Structure (+28 more)

### Community 3 - "Community 3"
Cohesion: 0.17
Nodes (15): _build_export_network(), _cleanup(), export_asset(), _export_geometry(), _get_geometry_stats(), _prims_to_group_string(), Asset Exporter - Builds node network and exports geometry, Export asset with the given configuration          Args:         export_data: (+7 more)

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
Cohesion: 0.07
Nodes (27): attribute_schema(), connections_are_never_refused(), dead_ends(), graph_is_planar(), junction_boundary_is_simple(), no_downward_faces(), no_loose_points(), no_orphan_components() (+19 more)

### Community 8 - "Community 8"
Cohesion: 0.11
Nodes (14): AssetBrowserDialog, AssetDropHandler, _handle_drop(), Asset Browser UI - Grid view of assets with search and filtering, Forward thumbnail drop to the browser-level signal., Standalone asset browser dialog, Double-click in the floating browser: create and connect the         asset plac, Show the asset browser dialog (+6 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (26): build(), dedupe_edges(), _dist(), _dist2(), edge_length(), endpoint_degree(), junctions(), prune_stubs() (+18 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (4): AssetPlaceState, Key DOWN / UP transitions for clean drag start/end.         Works as a suppleme, Show or hide the xform handle and update the prompt message., Interactive placement state for the pf_asset_place HDA.

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (29): float2, float3, float4, pf_hash1(), pf_hash21(), pf_hash22(), pf_hash2d(), pf_hash43() (+21 more)

### Community 12 - "Community 12"
Cohesion: 0.18
Nodes (11): _area_xz(), _expected_reject(), lot_aspect_ratio(), _obb(), Point-segment distance on (x, z) tuples. Plain arithmetic on purpose:     this i, `pfsl_street_edge` and `pfsl_frontage`, re-derived here in Python.      ⚠️ This, The S8 ladder, recomputed from the evidence and the node's thresholds.      Retu, Ribbons, not rectangles — and whether S8 both SAYS SO and SHOWS ITS WORK.      ⚠ (+3 more)

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
Cohesion: 0.18
Nodes (11): 4. Stage design, ⚠️ AREA WAS NOT ENOUGH EITHER. The fifth wrong seam — 2026-08-10, Chaotic / organic patterns — clarified, not scrapped, S0 — Domain, S1 — Field (pluggable generators), S4 — Classify, S5b — Bridges, tunnels, ramps, S6 — Cross-section → road geometry (+3 more)

### Community 18 - "Community 18"
Cohesion: 0.11
Nodes (19): 10. Explicit non-goals for v1, 1. Hard constraints, 2. Diagnosis: why the previous attempts produced unsatisfying output, 3. Architecture: staged pipeline with schema contracts, 4d. Measured state of the shipped build — 2026-08-09 (pre-fix), 4e. Independent audit findings — 2026-08-09, 4f. Civil-engineering sweep — 2026-08-09. What it changes, 4g. Second audit — the dead-end build, 2026-08-09 (+11 more)

### Community 19 - "Community 19"
Cohesion: 0.23
Nodes (13): Module reloader for Polyfactory development  Intelligently reloads modules for, Reload widget library modules., Reload asset library modules., Reload viewer utilities modules., Reload UI framework modules (PyOneDark-based)., Reload all Polyfactory modules., Internal helper to reload a list of modules., reload_all() (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.07
Nodes (23): HoverComboBox, HoverSlider, Asset Browser Widgets - Low-level widget classes extracted from browser_ui.py., QSlider with animated hover outline, QComboBox with animated hover outline, AssetBrowserWidget, Asset browser with grid view, search, and filters, Load assets from database (+15 more)

### Community 21 - "Community 21"
Cohesion: 0.18
Nodes (7): AssetPlaceNodeUI, Asset Place HDA UI - Python Panel for pf_asset_place node.  Shows the full ass, Python Panel widget for pf_asset_place HDA.      Embeds the full AssetBrowserW, Called by onNodePathChanged — updates which node we drive., Reload asset list (called on pane activation)., Highlight the thumbnail matching the node's current asset_id., User double-clicked an asset — push into node parms.

### Community 22 - "Community 22"
Cohesion: 0.14
Nodes (6): AssetGroupRow, Asset Group Row widget used by the inline batch mode in AssetExportDialog., Returns the per-row name, or empty string if blank (caller applies dialog-level, Fill in category/tags only if the prim had no attributes for them., Update the status dot to reflect export progress.          Args:, One row in the detected-assets list.      Displays a checkbox, sequential inde

### Community 23 - "Community 23"
Cohesion: 0.06
Nodes (19): AssetDatabase, Manages the asset library SQLite database, Add a new asset to the database                  Args:             name: Asse, Initialize database connection                  Args:             db_path: Pa, Associate tags with an asset, Get asset by ID                  Args:             asset_id: Asset ID, Get all tags for an asset                  Args:             asset_id: Asset, Search assets with various filters                  Args:             search_ (+11 more)

### Community 24 - "Community 24"
Cohesion: 0.19
Nodes (12): _aabbs_overlap(), detect_asset_groups(), next_free_filename(), Batch Kitbash Importer - AABB-based asset detection and batch export backend, Find the next available numbered filename (no extension).      Scans both the, Detect asset groups in a SOP node using connectivity + AABB overlap.      Each, Return True if two AABBs (min_x,min_y,min_z,max_x,max_y,max_z) overlap., Read a string primitive attribute value; return default if absent. (+4 more)

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (36): 1. Create the HDA, 2. Add Python Panel Interface, 3. Set Interface as Default, 4. Configure Multiparm Structure, Add Custom Controls, Adding Assets, Asset Browser Empty, Asset Browser Section (+28 more)

### Community 26 - "Community 26"
Cohesion: 0.20
Nodes (11): Geometry, Matrix4, align_transform_to_normal(), extract_rotation_from_matrix(), get_geometry_under_cursor(), Raycasting utilities for viewer states Pure functions for ray-geometry intersec, Get geometry under cursor using ray intersection.          Args:         ui_e, Raycast against geometry and return hit information.          Args:         o (+3 more)

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
Nodes (15): HoverListWidget, QListWidget with animated hover outline, HoverOutlineMixin, Initialize hover outline animation.                  Args:             color:, Get current hover outline opacity (0.0 to 1.0), Set hover outline opacity (0.0 to 1.0), Start fade-in animation on hover, Start fade-out animation on leave (+7 more)

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (33): Adding New Placement Modes, Adding Viewer Utils Functions, Align to Mesh (Default), Alignment Issues, Architecture, Asset Data Flow, Components, Core Functions (+25 more)

### Community 34 - "Community 34"
Cohesion: 0.06
Nodes (19): QEvent, QObject, FlowLayout, Layout that wraps widgets to multiple lines like text flow, Tag input widget with autocomplete and chip display, Set the list of available tags for autocomplete                  Args:, Get current list of tags                  Returns:             List of tag st, Set the current tags                  Args:             tags: List of tag str (+11 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (13): EnhancedInputField, Base Parameter Widgets - Label, InputField, BaseParmWidget, ExpressionDialog, Enhanced InputField with all Houdini parameter polish features:     - Hover eff, ParmInt, Numeric Parameter Widgets - ParmFloat, ParmInt  Float and integer parameter wi, Integer parameter widget using Enhanced InputField with slider.          Combi, Handle value change from InputField., Update widget from parameter value. (+5 more)

### Community 36 - "Community 36"
Cohesion: 0.09
Nodes (13): AssetInfoPanel, Handle resize to update preview image size, Create styled label for form, Load turntable frames for animation, Display a specific frame, Display asset information, Load full turntable sequence on hover, Return to frame 5 on leave (+5 more)

### Community 37 - "Community 37"
Cohesion: 0.29
Nodes (7): Higher-degree junctions — untested, and structurally unreachable from the field, Plazas and roundabouts at degenerate points, S5 — Intersections, The invariant that was violated: **every corner is an arc, always**, Three constructions adopted from the civil sweep — 2026-08-09, Two rules the design left open, decided 2026-08-09, What the literature adds

### Community 38 - "Community 38"
Cohesion: 0.15
Nodes (14): _ends(), every_block_is_subdivided(), _graph_geometry_delta(), graph_reaches_a_fixed_point(), _nearest(), no_duplicate_lot_footprints(), _point_grid(), (cell -> [point index], flat P) for order-independent nearest lookup. (+6 more)

### Community 39 - "Community 39"
Cohesion: 0.28
Nodes (6): draw_crosshair(), draw_normal_indicator(), Drawing utilities for viewer states Pure functions for viewport drawing helpers, Draw simple crosshair at position.          Args:         drawable: Houdini d, Draw line indicating surface normal.          Args:         drawable: Houdini, Viewer utilities for Houdini viewer states Reusable library components for rayc

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
Cohesion: 0.11
Nodes (19): block_boundary_closes(), every_mouth_has_a_road(), lots_tile_blocks(), no_degenerate_corner_segments(), no_nonplanar_y(), no_sweep_fold_after_trim(), plaza_disc_is_clear(), PolyExpand2D breaks planarity by ~2e-5. Intersection Analysis is a true     3D t (+11 more)

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
Cohesion: 0.15
Nodes (8): AssetInstanceWidget, Create styled spinbox, Handle spinbox value change, Widget representing a single placed asset instance, Create UI for single asset instance, get_font_stylesheet(), Generate font stylesheet matching Houdini's scaling.          Args:         s, PyPushButton

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

### Community 52 - "Community 52"
Cohesion: 0.13
Nodes (5): Ui_RightColumn, Themes, SetupMainWindow, UI_MainWindow, Ui_MainPages

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
Cohesion: 0.14
Nodes (16): build_all(), _chain(), inner(), install_hdas(), parm(), CityGen test cases — builds every scene the checks run against.  Scenes are buil, The four-node pipeline: TRACER · SEGMENTER · SOLVER · MESHER.      Split from th, Build every case. Returns {case_name: {role: node}}. (+8 more)

### Community 60 - "Community 60"
Cohesion: 0.17
Nodes (12): createViewerStateTemplate(), _ground_plane_hit(), _normal_to_euler(), Asset Placement Viewer State for pf_asset_place HDA.  Two modes (toggle with Q, Intersect against ONLY the geometry connected to SOP input 0.          Input g, Raycast against input geometry only, set t/r parms on node., Return XYZ Euler angles (degrees) that rotate +Y to align with normal.      Bu, Intersect ray with Y=0 ground plane. Returns hit position or None. (+4 more)

### Community 62 - "Community 62"
Cohesion: 0.20
Nodes (9): Known-failing at time of writing, Layout, Numbers first, renders second, polyfactory tests, Test the union, and every branch, The baseline, The cases, The closure sweep, and why it is a file rather than a habit (+1 more)

### Community 63 - "Community 63"
Cohesion: 0.18
Nodes (11): ⚠️ …AND `lots_moved` WAS LATENT HOLE 1 AGAIN — the count kept, the magnitude discarded, ⚠️ AND THE EXPERIMENT NEVER VERIFIED THAT IT RAN, ⚠️ AND THE EXPERIMENT THAT CAUGHT THE VERDICT WAS ASSERTING THE VERDICT'S OWN BLIND SPOT, ⚠️ AND THE FIX LEFT THE SAME PATTERN ONE LEVEL DOWNSTREAM, ⚠️ …AND THEN IT STOPPED TOO EARLY, BECAUSE FOUR AGGREGATES CANNOT SEE A REDISTRIBUTION, Layers — the change bridges force, Networks are typed, `pf_citygen_mesh` input 0 is NOT dead — it is under-observed (+3 more)

### Community 67 - "Community 67"
Cohesion: 0.29
Nodes (4): ParmString, Update visual feedback for expression state., String input widget with enhanced label., Reset parameter to default value (Ctrl+MMB on label).

### Community 69 - "Community 69"
Cohesion: 0.24
Nodes (4): _ToolTip, _ToolTip, _ToolTip, QLabel

### Community 70 - "Community 70"
Cohesion: 0.50
Nodes (3): 123.py - Auto-loaded on Houdini startup Registers custom viewer states, Register all Polyfactory viewer states, register_viewer_states()

### Community 71 - "Community 71"
Cohesion: 0.24
Nodes (11): _blobs(), city_is_fully_paved(), lots_clear_of_junctions(), lots_clear_of_roads(), _raster_grid(), _rasterise(), Even-odd fill of every polygon in `geo` onto a boolean XZ grid., Connected components of a boolean mask as (area, cx, cz), largest first.      Ru (+3 more)

### Community 73 - "Community 73"
Cohesion: 0.33
Nodes (6): digest(), generic(), main(), Does every promoted parameter on the CityGen HDAs actually do anything?  ⚠️ It s, (geometry digest, attribute digest) for one output.      Split so an attribute-o, A perturbation for a parm nobody has written a value for yet.

### Community 74 - "Community 74"
Cohesion: 0.18
Nodes (11): _arc_lengths(), culdesac_bulbs_are_circles(), every_corner_is_an_arc(), _fit_circle(), _pos_at_length(), Kasa algebraic circle fit in XZ. Returns (cx, cz, r, max_residual) or     None w, Position at arc length `s` along a polyline — what s5j_trim's     pfsg_pos_at_le, A junction corner that is not a correctly-placed fillet arc.      Measured 50/50 (+3 more)

### Community 76 - "Community 76"
Cohesion: 0.24
Nodes (4): Settings, object, PyWindow, Styles

### Community 77 - "Community 77"
Cohesion: 0.19
Nodes (11): SQLite database management for asset library, Asset Library Module for Polyfactory Handles kitbash asset management, export,, _cleanup(), _create_render_scene(), Turntable Renderer - Creates rotating preview animations for assets, Render frames using viewport flipbook          Args:         lop_net: LOP net, Remove temporary nodes and panes          Args:         temp_nodes: List of n, Render a turntable animation of the geometry          Args:         geo_node: (+3 more)

### Community 78 - "Community 78"
Cohesion: 0.09
Nodes (11): AssetThumbnailWidget, _load_pixmap_cached(), Return a cached, pre-scaled pixmap for path, loading from disk on miss., Individual asset thumbnail with animated hover outline, Update thumbnail size dynamically without re-reading disk, Scale the cached pixmap to the current thumb size (no disk I/O), Toggle selection highlight on this thumbnail., Draw widget with selection highlight and animated hover outline. (+3 more)

### Community 79 - "Community 79"
Cohesion: 0.09
Nodes (41): accepted(), accepted_seam_distribution(), build_trace(), configs(), _cross(), gate_matches_vex(), gates(), gates_sagitta() (+33 more)

### Community 80 - "Community 80"
Cohesion: 0.25
Nodes (6): Export UI Panel for Asset Library, Show the export dialog with current selection          Args:         parent:, show_export_dialog(), export_selected_to_library(), Hotkey command script to open asset export dialog This script can be bound to a, Main function to trigger asset export dialog

### Community 83 - "Community 83"
Cohesion: 0.20
Nodes (7): export_batch_group(), Export a single asset group detected by detect_asset_groups.      Converts pri, Handle export button click, acquire_shared_panel(), Create a shared floating panel for batch renders.      Call once before starti, Close the shared panel acquired by acquire_shared_panel().      Call once afte, release_shared_panel()

### Community 84 - "Community 84"
Cohesion: 0.25
Nodes (7): Attribution, Credits, Modifications, Polyfactory Integration, Polyfactory UI Framework, Structure, Usage in Polyfactory

### Community 85 - "Community 85"
Cohesion: 0.14
Nodes (5): Ui_LeftColumn, PyIcon, PyLeftColumn, PySlider, QSlider

### Community 86 - "Community 86"
Cohesion: 0.15
Nodes (14): centreline_curvature_within_class(), Mirror of `pfsg_turn_at`: |turn| at b and the two edge lengths.      ⚠️ THE ANGL, Per-vertex turn (radians) and its ceiling, from geometry alone.      Returns (ph, No centreline may bend tighter than its class minimum curve radius.      S3b. A, Run the SHIPPED S3b clamp on the inputs that broke the first one.      This is t, Worst discrete curvature x R_min over one rig polyline., One cook of the control rig, read back per rig polyline., [] when every rig behaved; otherwise the rigs that did not, named. (+6 more)

### Community 87 - "Community 87"
Cohesion: 0.27
Nodes (4): HoverOutlineMixin, PyLineEdit, Fallback if hover_outline not available, QLineEdit

### Community 88 - "Community 88"
Cohesion: 0.50
Nodes (4): merged_city_self_intersections(), Intersection Analysis reports 0 for a valid box, grid and kerb step —     verifi, THE gap. Roads and junction patches interpenetrate at every junction and     the, self_intersections()

### Community 89 - "Community 89"
Cohesion: 0.17
Nodes (15): _attrib_values(), hou_vec3(), input0_reaches_an_output(), lot_clip_control_rig(), lots_are_simple_polygons(), _orient_xz(), CityGen geometry checks — the assertions, in one place.  Every check here caught, Every value of one attribute, in element order.      Bulk-read where the type al (+7 more)

### Community 90 - "Community 90"
Cohesion: 0.07
Nodes (29): 1. The assertion first, and it is a tripwire rather than a measurement, 1. The gate now counts the cluster, and it reads 5 where it read 4 / 3 / 3, 2. ⚠️ AND A COUNTER READ THE INPUT AND SHIPPED A CONFIDENT ZERO, 2. `graph_realign`, with the defect removed, 3. ⚠️ AND IT DID NOTHING AT ALL FOR A WHOLE SUITE RUN, ON ONE WRONG FUNCTION, 3. Two hand-drawn cases, and the suite executes the machinery for the first time, 4. It works, and the artist's own junction is the proof, 4. The tripwire watches five nodes, and it was watching one (+21 more)

### Community 91 - "Community 91"
Cohesion: 0.12
Nodes (17): Junction repair used to be recorded here — moved to §S5a, 2026-08-12, New case: `H_offset_strict`, ⚠️ On shipped data the new rung is decision-identical to raising `min_frontage` to 8, ⚠️ Round seven — the fold fix is PARTIAL, and three claims made for it were false, ⚠️ Round six — the first PIPELINE defect, and `offset` mode was shipping broken parcels, Round two — the fix for round one's finding did not fix it, Rounds three and four — the verification was wrong one level deeper each time, S8 — Lots (+9 more)

### Community 92 - "Community 92"
Cohesion: 0.13
Nodes (7): AssetExportDialog, Dialog for exporting selected geometry to asset library, Keep blank row name fields showing the effective base name they will use., Load existing categories from database, Handle name confirmation (Enter key or lost focus) - auto-suggest category and t, Update the export path preview, Get the export configuration data

### Community 96 - "Community 96"
Cohesion: 0.20
Nodes (10): ⚠️ `2aba0a9` raised six numbers and recorded one — 2026-08-10, 4c. Implementation status — 2026-08-09, ⚠️ C's east sector subdivides into long ribbons, and `ac64636` recorded only the improvements, Every promoted parameter, measured — 2026-08-10, Overnight run — 2026-08-09/10, Recorded, not fixed — from the same audit, The loop-closure gate, per-gate — measured, and two entries in `80dc19c` were wrong, ⚠️ The road-under-chord metric was ill-posed. Use the pavement deficit (+2 more)

### Community 97 - "Community 97"
Cohesion: 0.10
Nodes (19): createInterface(), KitbashNodeUI, PlacedAssetsListWidget, Kitbash HDA UI - Python Panel interface for pf_kitbash node  NEW WORKFLOW: -, Load values from node parameters, Widget displaying list of placed assets with controls, Refresh asset list from multiparm, Delete asset from multiparm (+11 more)

### Community 98 - "Community 98"
Cohesion: 0.11
Nodes (3): Functions, PyDiv, PyLeftMenu

### Community 99 - "Community 99"
Cohesion: 0.15
Nodes (13): Before and after, per criterion, Before and after, per criterion, Real at non-default scale — recorded, not fixed, S3b — Turns: a bend is not a junction, and gets its own solver, Still unguarded after this pass — recorded, not fixed, The clamp is a radius floor and that is not the same as a smooth street — 2026-08-10, ⚠️ The clamp must be a SOLVE, not a fixed sweep count — measured 2026-08-09, The control rig was calibrated to one slider position, and now is not (+5 more)

### Community 101 - "Community 101"
Cohesion: 0.50
Nodes (4): forced_extra_repair_pass(), _lot_area_delta(), (parcels over 1 m2, worst m2) between two rank-sorted parcel-area lists.      ⚠️, Turn OFF the loop's early exit, run one pass MORE than it asked for, and     see

### Community 102 - "Community 102"
Cohesion: 0.18
Nodes (11): ✅ BUILT — the next boundary: SEGMENTER and SOLVER, Naming — settled 2026-08-11, Open decisions, to settle before building, The criterion, and why the cut is clean, ⚠️ The harness could not reach the Tracer at all, The Labs Building Generator precedent — checked, and it half-holds, ⚠️ The repair loop decides the cut, and it makes the solver thin, The residual circularity, and the rule that settles it (+3 more)

### Community 103 - "Community 103"
Cohesion: 0.22
Nodes (9): 6b. Shipped V1 assets, ✅ AUDIT OF THE TRIM — and the monolith was NOT a control, it was a divergence hazard, `closure_gate.py` ported onto `tracer → segmenter`, Every promoted parameter, measured by who READS it, ⚠️ Never change a shared VEX signature under existing callers — 2026-08-11, ⚠️ The boundary moved — 2026-08-10. It is now between DATA and GEOMETRY, The old chain is being retired — status 2026-08-12, The original V1 assets (+1 more)

### Community 104 - "Community 104"
Cohesion: 0.33
Nodes (6): _junction_graph(), junctions_not_too_close(), no_multileg_junctions(), Endpoint degree, edge lengths, and the clusters a multi-leg junction hides     i, No edge may join two junctions closer together than `floor` metres.      THE JOG, No junction may carry more than `cap` arms - counted AFTER near-coincident     j

### Community 106 - "Community 106"
Cohesion: 0.40
Nodes (5): apply_houdini_font(), get_houdini_font(), UI utilities for matching Houdini's font sizes and scaling, Get Houdini's default application font.          Returns:         QFont objec, Apply Houdini's font to a widget with optional size override.          Args:

### Community 107 - "Community 107"
Cohesion: 0.50
Nodes (4): ⚠️ A CONNECTION WAS BEING REFUSED FOR BEING TOO CLOSE — fixed 2026-08-10, Dead ends are the exception, not the norm — and the fix is in the papers, S2 — Trace, ⚠️ The node merge: attempted, measured, reverted — and the blocker is NOT the clamp

### Community 108 - "Community 108"
Cohesion: 0.67
Nodes (3): 3b. The unanimous baseline — where all four sources agree, Decision — 2026-08-09, What this changes

## Knowledge Gaps
- **356 isolated node(s):** `Project Overview`, `Package Structure`, `Environment Variables`, `Temporary / One-Off Scripts`, `Houdini Bridge - AI Agent Integration` (+351 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **10 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PyPushButton` connect `Community 47` to `Community 32`, `Community 97`, `Community 64`, `Community 36`, `Community 8`, `Community 72`, `Community 78`, `Community 20`, `Community 85`, `Community 92`?**
  _High betweenness centrality (0.099) - this node is a cross-community bridge._
- **Why does `Result` connect `Community 7` to `Community 101`, `Community 38`, `Community 71`, `Community 104`, `Community 74`, `Community 43`, `Community 12`, `Community 76`, `Community 86`, `Community 88`, `Community 89`?**
  _High betweenness centrality (0.078) - this node is a cross-community bridge._
- **Why does `HoverOutlineMixin` connect `Community 32` to `Community 97`, `Community 34`, `Community 36`, `Community 78`, `Community 47`, `Community 15`, `Community 20`, `Community 87`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `AssetBrowserWidget` (e.g. with `AssetPlaceNodeUI` and `._setup_ui()`) actually correct?**
  _`AssetBrowserWidget` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TagInputWidget` (e.g. with `AssetInfoPanel` and `._setup_ui()`) actually correct?**
  _`TagInputWidget` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AssetDatabase` (e.g. with `next_free_filename()` and `AssetBrowserDialog`) actually correct?**
  _`AssetDatabase` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `PyPushButton` (e.g. with `AssetInfoPanel` and `._setup_ui()`) actually correct?**
  _`PyPushButton` has 19 INFERRED edges - model-reasoned connections that need verification._