# Graph Report - polyfactory  (2026-08-09)

## Corpus Check
- 122 files · ~117,074 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1618 nodes · 2481 edges · 103 communities (85 shown, 18 thin omitted)
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 290 edges (avg confidence: 0.67)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `50e51f3d`
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
- [[_COMMUNITY_Community 103|Community 103]]

## God Nodes (most connected - your core abstractions)
1. `AssetBrowserWidget` - 37 edges
2. `TagInputWidget` - 35 edges
3. `AssetDatabase` - 34 edges
4. `Result` - 33 edges
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

## Communities (103 total, 18 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.05
Nodes (29): AssetBrowserWidget, Asset browser with grid view, search, and filters, Load assets from database, Filter assets based on search, category, and tags, Update grid with filtered assets, Handle asset single-click.  Ctrl+click toggles, Shift+click selects range., Handle asset double-click - trigger placement, Return the resolved path to the asset database. (+21 more)

### Community 1 - "Community 1"
Cohesion: 0.10
Nodes (15): BaseParmWidget, Base class for parameter-bound widgets., Get current parameter value. Override in subclasses., Set parameter value. Override in subclasses., Update widget from parameter (called by BindingManager)., Update widget display. Override in subclasses., Update visual feedback for expression state.                  This base implem, Show Houdini-style parameter context menu. (+7 more)

### Community 2 - "Community 2"
Cohesion: 0.05
Nodes (36): Architecture, Automated verification via hython, Binding Types, Building, Copernicus OpenCL HDA Development Guide, Critical OpenCL vs GLSL Differences, Critical Rules, devScript Structure (+28 more)

### Community 3 - "Community 3"
Cohesion: 0.12
Nodes (19): export_batch_group(), Export a single asset group detected by detect_asset_groups.      Converts pri, _build_export_network(), _cleanup(), export_asset(), _export_geometry(), _get_geometry_stats(), _prims_to_group_string() (+11 more)

### Community 4 - "Community 4"
Cohesion: 0.07
Nodes (24): build_profile_points(), _ensure_point_attribs(), geo_to_elements(), get_template(), profile_to_geo(), CityGen - street cross-section templates and profile construction.  Design: idea, Fill defaults into a raw element list. Authored keys always win., Summary attributes stamped onto the street edge.      Names follow the common in (+16 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (14): line(), Runnable check for street graph construction.  No Houdini needed.      python, A cul-de-sac is legitimate; only SHORT dead ends are noise., Removing one stub can expose another behind it., 3x3 crossing streets, each overshooting the outer ones.          Every street, Sampled straight line from a to b, so welding sees interior points., Guards the documented precondition: two streets that cross without         shar, The classic spatial-hash bug: neighbours must be searched too. (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (15): attribute_schema(), no_downward_faces(), no_duplicate_lot_footprints(), no_orphan_components(), no_scratch_attribs(), no_scratch_groups(), no_zero_area_prims(), Working ATTRIBUTES leak out of the asset; `no_scratch_groups` only ever     chec (+7 more)

### Community 8 - "Community 8"
Cohesion: 0.13
Nodes (5): Ui_LeftColumn, PyIcon, PyLeftColumn, PySlider, QSlider

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
Cohesion: 0.15
Nodes (3): Ui_RightColumn, Functions, PyTitleBar

### Community 13 - "Community 13"
Cohesion: 0.10
Nodes (14): createViewerStateTemplate(), KitbashPlacementState, Kitbash Placement State - Interactive viewport placement for assets  NEW WORKF, Place the currently selected mesh at cursor position, Handle keyboard events, Update menu state before opening, Interactive state for placing kitbash assets in viewport, Handle context menu selections (+6 more)

### Community 14 - "Community 14"
Cohesion: 0.12
Nodes (22): Parm, copy_parameter(), delete_expression(), get_expression_language(), get_expression_string(), get_parm_color(), get_parm_display_value(), has_expression() (+14 more)

### Community 15 - "Community 15"
Cohesion: 0.19
Nodes (8): Build a layout containing all registered widgets.                  Args:, HoudiniGroupBox, HoudiniHLayout, HoudiniVLayout, Layout Helpers - Houdini-styled layouts  Provides layout classes styled to mat, Vertical layout with Houdini spacing., Horizontal layout with Houdini spacing., Group box styled like Houdini folders.

### Community 16 - "Community 16"
Cohesion: 0.05
Nodes (41): Accessing Package Assets, Asset Database, Branch Structure, Code Quality - Error Handling, Code Style: Functional Over Object-Oriented, Common Patterns, Creative / Procedural Tool Requests Require Design Breakdown First, Critical Conventions (+33 more)

### Community 17 - "Community 17"
Cohesion: 0.04
Nodes (49): 10. Explicit non-goals for v1, 1. Hard constraints, 2. Diagnosis: why the previous attempts produced unsatisfying output, 3. Architecture: staged pipeline with schema contracts, 3b. The unanimous baseline — where all four sources agree, 4. Stage design, 4c. Implementation status — 2026-08-09, 4d. Measured state of the shipped build — 2026-08-09 (pre-fix) (+41 more)

### Community 18 - "Community 18"
Cohesion: 0.31
Nodes (5): Initialize UI components that require a node, Update the node reference - called when node path changes, get_scaled_font_size(), Get font size scaled to match Houdini's UI scaling.          Args:         ba, SopNode

### Community 19 - "Community 19"
Cohesion: 0.23
Nodes (13): Module reloader for Polyfactory development  Intelligently reloads modules for, Reload widget library modules., Reload asset library modules., Reload viewer utilities modules., Reload UI framework modules (PyOneDark-based)., Reload all Polyfactory modules., Internal helper to reload a list of modules., reload_all() (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.16
Nodes (5): HoverOutlineMixin, PyLineEdit, Fallback if hover_outline not available, PyPushButton, QLineEdit

### Community 21 - "Community 21"
Cohesion: 0.21
Nodes (6): AssetPlaceNodeUI, Python Panel widget for pf_asset_place HDA.      Embeds the full AssetBrowserW, Called by onNodePathChanged — updates which node we drive., Reload asset list (called on pane activation)., Highlight the thumbnail matching the node's current asset_id., User double-clicked an asset — push into node parms.

### Community 22 - "Community 22"
Cohesion: 0.16
Nodes (13): Geometry, Matrix4, align_transform_to_normal(), extract_rotation_from_matrix(), get_geometry_under_cursor(), Raycasting utilities for viewer states Pure functions for ray-geometry intersec, Get geometry under cursor using ray intersection.          Args:         ui_e, Raycast against geometry and return hit information.          Args:         o (+5 more)

### Community 23 - "Community 23"
Cohesion: 0.25
Nodes (4): Initialize database connection                  Args:             db_path: Pa, Create database directory if it doesn't exist, Establish database connection, Create database tables if they don't exist

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (36): 1. Create the HDA, 2. Add Python Panel Interface, 3. Set Interface as Default, 4. Configure Multiparm Structure, Add Custom Controls, Adding Assets, Asset Browser Empty, Asset Browser Section (+28 more)

### Community 26 - "Community 26"
Cohesion: 0.20
Nodes (8): Asset Place HDA UI - Python Panel for pf_asset_place node.  Shows the full ass, apply_houdini_font(), get_font_stylesheet(), get_houdini_font(), UI utilities for matching Houdini's font sizes and scaling, Get Houdini's default application font.          Returns:         QFont objec, Generate font stylesheet matching Houdini's scaling.          Args:         s, Apply Houdini's font to a widget with optional size override.          Args:

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
Cohesion: 0.09
Nodes (14): HoverOutlineMixin, Hover Outline Mixin - Animated blue outline on hover for any widget, Initialize hover outline animation.                  Args:             color:, Get current hover outline opacity (0.0 to 1.0), Set hover outline opacity (0.0 to 1.0), Start fade-in animation on hover, Start fade-out animation on leave, Paint the hover outline. Call this in your paintEvent.                  Args: (+6 more)

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (33): Adding New Placement Modes, Adding Viewer Utils Functions, Align to Mesh (Default), Alignment Issues, Architecture, Asset Data Flow, Components, Core Functions (+25 more)

### Community 34 - "Community 34"
Cohesion: 0.08
Nodes (17): QEvent, QObject, Tag input widget with autocomplete and chip display, Set the list of available tags for autocomplete                  Args:, Get current list of tags                  Returns:             List of tag st, Set the current tags                  Args:             tags: List of tag str, Show dropdown menu with all available tags, Add a tag chip                  Args:             tag_text: Tag string to add (+9 more)

### Community 35 - "Community 35"
Cohesion: 0.08
Nodes (29): BaseParmWidget, Binding Manager - Central coordinator for parameter-widget synchronization  Ma, Polyfactory Widgets Module  Qt widgets for Houdini workflows.  Submodules:, EnhancedInputField, ExpressionDialog, Base Parameter Widgets - Label, InputField, BaseParmWidget, ExpressionDialog, Dialog for editing parameter expressions., Enhanced InputField with all Houdini parameter polish features:     - Hover eff (+21 more)

### Community 36 - "Community 36"
Cohesion: 0.09
Nodes (13): AssetInfoPanel, Handle resize to update preview image size, Create styled label for form, Load turntable frames for animation, Display a specific frame, Display asset information, Load full turntable sequence on hover, Return to frame 5 on leave (+5 more)

### Community 37 - "Community 37"
Cohesion: 0.19
Nodes (12): _aabbs_overlap(), detect_asset_groups(), next_free_filename(), Batch Kitbash Importer - AABB-based asset detection and batch export backend, Find the next available numbered filename (no extension).      Scans both the, Detect asset groups in a SOP node using connectivity + AABB overlap.      Each, Return True if two AABBs (min_x,min_y,min_z,max_x,max_y,max_z) overlap., Read a string primitive attribute value; return default if absent. (+4 more)

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
Cohesion: 0.13
Nodes (13): QWidget, BindingManager, Create a dropdown menu widget bound to a parameter., Create a color picker widget bound to a parameter tuple., Manages parameter bindings for an HDA Python Panel UI.          Coordinates up, Create a button widget (not bound to parameter)., Register a widget-parameter binding., Poll for external parameter changes (from UI, expressions, etc). (+5 more)

### Community 43 - "Community 43"
Cohesion: 0.13
Nodes (15): every_mouth_has_a_road(), lots_tile_blocks(), no_degenerate_corner_segments(), no_nonplanar_y(), no_sweep_fold_after_trim(), plaza_disc_is_clear(), PolyExpand2D breaks planarity by ~2e-5. Intersection Analysis is a true     3D t, Zero-length boundary segments mean the fillet arc collapsed.      pfsj_arc_centr (+7 more)

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
Cohesion: 0.13
Nodes (7): AssetExportDialog, Dialog for exporting selected geometry to asset library, Keep blank row name fields showing the effective base name they will use., Load existing categories from database, Handle name confirmation (Enter key or lost focus) - auto-suggest category and t, Update the export path preview, Get the export configuration data

### Community 48 - "Community 48"
Cohesion: 0.10
Nodes (9): ParmMenu, Block user input when expression is active., Dropdown menu widget with enhanced label., Menu parms can be int or string - get the string token., Update visual feedback for expression state., Block user input when expression is active., Reset parameter to default value (Ctrl+MMB on label)., Update widget from parameter value. (+1 more)

### Community 49 - "Community 49"
Cohesion: 0.11
Nodes (17): Alternative: Manual Python Panel Assignment, Asset browser is empty, Automatic Setup via HDA Type Properties, Check 1: Python Panel Definition Exists, Check 2: HDA Type Properties, Check 3: Test the Node, Complete Verification Script, HDA Configuration for pf_kitbash Python Panel (+9 more)

### Community 50 - "Community 50"
Cohesion: 0.11
Nodes (17): Categories, Copernicus COP, Houdini / HDA Python API, How to Use This File, Known Pitfalls Log, OPEN -- Asking questions already answered in Galaxia documentation, OPEN -- `hda_node.setParmTemplateGroup()` does NOT persist into HDA file, OPEN -- menuType.Normal with item generator renders as full combobox, not text+arrow (+9 more)

### Community 51 - "Community 51"
Cohesion: 0.12
Nodes (8): ParmTuple, EnhancedLabel, Add hover glow effect., Remove hover glow effect., Apply or remove hover visual feedback., Intercept label interactions., Enhanced QLabel with Houdini parameter polish features:     - Hover effects (li, Update visual style based on hover state.

### Community 53 - "Community 53"
Cohesion: 0.24
Nodes (3): PyGrips, Widgets, QFrame

### Community 55 - "Community 55"
Cohesion: 0.18
Nodes (6): Handle value change from InputField., Update widget from parameter value., Update widget from parameter value., Update visual feedback for expression state., Args:             parm: Houdini parameter to bind to             label: Option, Convert float value to slider position (0-1000).

### Community 59 - "Community 59"
Cohesion: 0.33
Nodes (6): build_all(), install_hdas(), CityGen test cases — builds every scene the checks run against.  Scenes are buil, hython does not load the polyfactory package, so $POLYFACTORY is unset     and `, Build every case. Returns {case_name: {role: node}}., setup_env()

### Community 60 - "Community 60"
Cohesion: 0.17
Nodes (12): createViewerStateTemplate(), _ground_plane_hit(), _normal_to_euler(), Asset Placement Viewer State for pf_asset_place HDA.  Two modes (toggle with Q, Intersect against ONLY the geometry connected to SOP input 0.          Input g, Raycast against input geometry only, set t/r parms on node., Return XYZ Euler angles (degrees) that rotate +Y to align with normal.      Bu, Intersect ray with Y=0 ground plane. Returns hit position or None. (+4 more)

### Community 61 - "Community 61"
Cohesion: 0.14
Nodes (6): AssetGroupRow, Asset Group Row widget used by the inline batch mode in AssetExportDialog., Returns the per-row name, or empty string if blank (caller applies dialog-level, Fill in category/tags only if the prim had no attributes for them., Update the status dot to reflect export progress.          Args:, One row in the detected-assets list.      Displays a checkbox, sequential inde

### Community 62 - "Community 62"
Cohesion: 0.22
Nodes (8): Known-failing at time of writing, Layout, Numbers first, renders second, polyfactory tests, Test the union, and every branch, The baseline, The four cases, Why this exists

### Community 63 - "Community 63"
Cohesion: 0.50
Nodes (4): main(), Run every CityGen geometry check in a throwaway Houdini session.      hython tes, All checks for one city. Returns [Result]., run_case()

### Community 69 - "Community 69"
Cohesion: 0.22
Nodes (6): AssetInstanceWidget, Create styled spinbox, Load values from node parameters, Handle spinbox value change, Widget representing a single placed asset instance, Create UI for single asset instance

### Community 70 - "Community 70"
Cohesion: 0.50
Nodes (3): 123.py - Auto-loaded on Houdini startup Registers custom viewer states, Register all Polyfactory viewer states, register_viewer_states()

### Community 71 - "Community 71"
Cohesion: 0.25
Nodes (9): _blobs(), city_is_fully_paved(), lots_clear_of_junctions(), _raster_grid(), _rasterise(), Even-odd fill of every polygon in `geo` onto a boolean XZ grid., Connected components of a boolean mask as (area, cx, cz), largest first.      Ru, No lot may lie inside a junction. The other half of city_is_fully_paved.      `c (+1 more)

### Community 72 - "Community 72"
Cohesion: 0.11
Nodes (4): Themes, MainFunctions, SetupMainWindow, UI_MainWindow

### Community 73 - "Community 73"
Cohesion: 0.18
Nodes (6): _ToolTip, _ToolTip, _ToolTip, QColor, QLabel, Set background color for expression state.

### Community 74 - "Community 74"
Cohesion: 0.22
Nodes (9): _arc_lengths(), every_corner_is_an_arc(), _fit_circle(), _pos_at_length(), Kasa algebraic circle fit in XZ. Returns (cx, cz, r, max_residual) or     None w, Position at arc length `s` along a polyline — what s5j_trim's     pfsg_pos_at_le, A junction corner that is not a correctly-placed fillet arc.      Measured 50/50, THE S5 SEAM: the road's terminal cross-section IS the mouth's cap segment. (+1 more)

### Community 76 - "Community 76"
Cohesion: 0.24
Nodes (4): Settings, object, PyWindow, Styles

### Community 77 - "Community 77"
Cohesion: 0.11
Nodes (14): AssetBrowserDialog, AssetDropHandler, _handle_drop(), Asset Browser UI - Grid view of assets with search and filtering, Forward thumbnail drop to the browser-level signal., Standalone asset browser dialog, Double-click in the floating browser: create and connect the         asset plac, Show the asset browser dialog (+6 more)

### Community 78 - "Community 78"
Cohesion: 0.07
Nodes (19): AssetThumbnailWidget, HoverComboBox, HoverSlider, _load_pixmap_cached(), Asset Browser Widgets - Low-level widget classes extracted from browser_ui.py., Return a cached, pre-scaled pixmap for path, loading from disk on miss., Individual asset thumbnail with animated hover outline, Update thumbnail size dynamically without re-reading disk (+11 more)

### Community 79 - "Community 79"
Cohesion: 0.19
Nodes (11): SQLite database management for asset library, Asset Library Module for Polyfactory Handles kitbash asset management, export,, _cleanup(), _create_render_scene(), Turntable Renderer - Creates rotating preview animations for assets, Render frames using viewport flipbook          Args:         lop_net: LOP net, Remove temporary nodes and panes          Args:         temp_nodes: List of n, Render a turntable animation of the geometry          Args:         geo_node: (+3 more)

### Community 80 - "Community 80"
Cohesion: 0.25
Nodes (6): Export UI Panel for Asset Library, Show the export dialog with current selection          Args:         parent:, show_export_dialog(), export_selected_to_library(), Hotkey command script to open asset export dialog This script can be bound to a, Main function to trigger asset export dialog

### Community 83 - "Community 83"
Cohesion: 0.12
Nodes (3): PyDiv, PyLeftMenu, PyDiv

### Community 84 - "Community 84"
Cohesion: 0.25
Nodes (7): Attribution, Credits, Modifications, Polyfactory Integration, Polyfactory UI Framework, Structure, Usage in Polyfactory

### Community 85 - "Community 85"
Cohesion: 0.32
Nodes (5): PlacedAssetsListWidget, Widget displaying list of placed assets with controls, Refresh asset list from multiparm, Delete asset from multiparm, Poll for parameter changes from external sources

### Community 86 - "Community 86"
Cohesion: 0.50
Nodes (4): lot_aspect_ratio(), _obb(), Minimum-area oriented bounding box in XZ, by rotating calipers over the     edge, Ribbons, not rectangles. Parcels 6.2 m wide and 62 m deep ship viable.      city

### Community 87 - "Community 87"
Cohesion: 0.25
Nodes (5): Handle export button click, acquire_shared_panel(), Create a shared floating panel for batch renders.      Call once before starti, Close the shared panel acquired by acquire_shared_panel().      Call once afte, release_shared_panel()

### Community 88 - "Community 88"
Cohesion: 0.50
Nodes (4): merged_city_self_intersections(), Intersection Analysis reports 0 for a valid box, grid and kerb step —     verifi, THE gap. Roads and junction patches interpenetrate at every junction and     the, self_intersections()

### Community 89 - "Community 89"
Cohesion: 0.17
Nodes (12): dead_ends(), graph_is_planar(), junction_boundary_is_simple(), lots_are_simple_polygons(), no_loose_points(), CityGen geometry checks — the assertions, in one place.  Every check here caught, Points belonging to no primitive. They ship as stray dots and blow out     every, No two segments may cross except at a shared node. Planarity is a     PER-LAYER (+4 more)

### Community 90 - "Community 90"
Cohesion: 0.18
Nodes (8): createInterface(), KitbashNodeUI, Kitbash HDA UI - Python Panel interface for pf_kitbash node  NEW WORKFLOW: -, Main UI for pf_kitbash node, Handle placed assets group box toggle, Refresh the UI - called when pane becomes active, Add selected asset from browser to library multiparm, Entry point for Python Panel UI.     Called by Houdini when creating the interf

### Community 92 - "Community 92"
Cohesion: 0.33
Nodes (3): Add a new asset to the database                  Args:             name: Asse, Associate tags with an asset, Add tags to multiple assets.  Existing tag associations are left intact.

### Community 96 - "Community 96"
Cohesion: 0.40
Nodes (5): Parameter Panel Utilities - Helper functions for creating floating parameter win, Open a floating parameter panel for a node using Houdini's native API., Show floating parameter panel for currently selected node.          Useful for, show_floating_parm_panel(), show_selected_node_parms()

### Community 97 - "Community 97"
Cohesion: 0.50
Nodes (4): block_boundary_closes(), centreline_curvature_within_class(), S7's collect-and-close invariant, which nothing else asserts.      The block bou, No centreline may bend tighter than its class minimum curve radius.      S3b. A

## Knowledge Gaps
- **274 isolated node(s):** `Project Overview`, `Package Structure`, `Environment Variables`, `Temporary / One-Off Scripts`, `Houdini Bridge - AI Agent Integration` (+269 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PyPushButton` connect `Community 20` to `Community 0`, `Community 26`, `Community 36`, `Community 69`, `Community 38`, `Community 72`, `Community 8`, `Community 77`, `Community 78`, `Community 47`, `Community 18`, `Community 85`, `Community 90`?**
  _High betweenness centrality (0.096) - this node is a cross-community bridge._
- **Why does `HoverOutlineMixin` connect `Community 32` to `Community 34`, `Community 35`, `Community 36`, `Community 69`, `Community 78`, `Community 20`, `Community 85`, `Community 24`, `Community 90`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `Result` connect `Community 7` to `Community 97`, `Community 71`, `Community 74`, `Community 43`, `Community 76`, `Community 86`, `Community 88`, `Community 89`?**
  _High betweenness centrality (0.061) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `AssetBrowserWidget` (e.g. with `AssetPlaceNodeUI` and `._setup_ui()`) actually correct?**
  _`AssetBrowserWidget` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TagInputWidget` (e.g. with `AssetInfoPanel` and `._setup_ui()`) actually correct?**
  _`TagInputWidget` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AssetDatabase` (e.g. with `next_free_filename()` and `AssetBrowserDialog`) actually correct?**
  _`AssetDatabase` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 19 inferred relationships involving `PyPushButton` (e.g. with `AssetInfoPanel` and `._setup_ui()`) actually correct?**
  _`PyPushButton` has 19 INFERRED edges - model-reasoned connections that need verification._