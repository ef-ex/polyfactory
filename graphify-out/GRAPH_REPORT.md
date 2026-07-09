# Graph Report - polyfactory  (2026-07-09)

## Corpus Check
- 127 files · ~91,938 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1636 nodes · 2544 edges · 97 communities (86 shown, 11 thin omitted)
- Extraction: 89% EXTRACTED · 11% INFERRED · 0% AMBIGUOUS · INFERRED: 273 edges (avg confidence: 0.66)
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `ba7a6fe3`
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
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]
- [[_COMMUNITY_Community 80|Community 80]]
- [[_COMMUNITY_Community 81|Community 81]]
- [[_COMMUNITY_Community 82|Community 82]]
- [[_COMMUNITY_Community 83|Community 83]]
- [[_COMMUNITY_Community 84|Community 84]]
- [[_COMMUNITY_Community 85|Community 85]]
- [[_COMMUNITY_Community 86|Community 86]]
- [[_COMMUNITY_Community 87|Community 87]]
- [[_COMMUNITY_Community 88|Community 88]]
- [[_COMMUNITY_Community 89|Community 89]]
- [[_COMMUNITY_Community 90|Community 90]]
- [[_COMMUNITY_Community 91|Community 91]]
- [[_COMMUNITY_Community 93|Community 93]]
- [[_COMMUNITY_Community 97|Community 97]]
- [[_COMMUNITY_Community 98|Community 98]]

## God Nodes (most connected - your core abstractions)
1. `AssetBrowserWidget` - 37 edges
2. `TagInputWidget` - 35 edges
3. `AssetDatabase` - 34 edges
4. `CommandExecutor` - 26 edges
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
- `start_bridge_server()` --calls--> `start_server()`  [INFERRED]
  polyfactory/scripts/123.py → polyfactory/scripts/python/polyfactory/houdini_bridge/server.py
- `HoverSlider` --uses--> `PyPushButton`  [INFERRED]
  polyfactory/scripts/python/polyfactory/asset_library/asset_browser_widgets.py → polyfactory/scripts/python/polyfactory/ui_framework/widgets/py_push_button/py_push_button.py
- `HoverSlider` --uses--> `HoverOutlineMixin`  [INFERRED]
  polyfactory/scripts/python/polyfactory/asset_library/asset_browser_widgets.py → polyfactory/scripts/python/polyfactory/widgets/hover_outline.py

## Import Cycles
- 1-file cycle: `polyfactory/scripts/python/polyfactory/ui_framework/__init__.py -> polyfactory/scripts/python/polyfactory/ui_framework/__init__.py`
- 1-file cycle: `polyfactory/scripts/python/polyfactory/viewer_utils/__init__.py -> polyfactory/scripts/python/polyfactory/viewer_utils/__init__.py`
- 1-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 2-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_base.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 2-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_numeric.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 3-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_numeric.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_base.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 3-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/widgets.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_base.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 3-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/widgets.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_numeric.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`
- 4-file cycle: `polyfactory/scripts/python/polyfactory/widgets/__init__.py -> polyfactory/scripts/python/polyfactory/widgets/widgets.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_numeric.py -> polyfactory/scripts/python/polyfactory/widgets/parm_widgets_base.py -> polyfactory/scripts/python/polyfactory/widgets/__init__.py`

## Communities (97 total, 11 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.07
Nodes (21): HoverComboBox, QComboBox with animated hover outline, AssetBrowserWidget, Asset browser with grid view, search, and filters, Load assets from database, Filter assets based on search, category, and tags, Update grid with filtered assets, Handle asset single-click.  Ctrl+click toggles, Shift+click selects range. (+13 more)

### Community 1 - "Community 1"
Cohesion: 0.08
Nodes (17): BaseParmWidget, ExpressionDialog, Base class for parameter-bound widgets., Get current parameter value. Override in subclasses., Set parameter value. Override in subclasses., Update widget from parameter (called by BindingManager)., Update widget display. Override in subclasses., Update visual feedback for expression state.                  This base implem (+9 more)

### Community 2 - "Community 2"
Cohesion: 0.20
Nodes (3): Ui_RightColumn, SetupMainWindow, UI_MainWindow

### Community 3 - "Community 3"
Cohesion: 0.17
Nodes (15): _build_export_network(), _cleanup(), export_asset(), _export_geometry(), _get_geometry_stats(), _prims_to_group_string(), Asset Exporter - Builds node network and exports geometry, Export asset with the given configuration          Args:         export_data: (+7 more)

### Community 4 - "Community 4"
Cohesion: 0.11
Nodes (16): CommandExecutor, Set node parameter value, Get node parameter value, Get current node selection, Get detailed node information, Executes commands from AI agent in Houdini session, Execute arbitrary Python code (requires approval), Execute a command on Houdini's MAIN thread and return the result.          The (+8 more)

### Community 5 - "Community 5"
Cohesion: 0.10
Nodes (22): _help_base(), houdini_doc(), houdini_get_skill(), houdini_list_skills(), houdini_node_help(), houdini_set_parameter(), houdini_status(), houdini_write_network() (+14 more)

### Community 7 - "Community 7"
Cohesion: 0.22
Nodes (6): AssetInstanceWidget, Create styled spinbox, Load values from node parameters, Handle spinbox value change, Widget representing a single placed asset instance, Create UI for single asset instance

### Community 8 - "Community 8"
Cohesion: 0.12
Nodes (3): PyDiv, PyLeftMenu, PyDiv

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (9): BridgeServer, Run synchronous WebSocket server in background thread, Handle client connection, Check if server is running, Get number of active connections, Broadcast message to all connected clients, WebSocket server for AI agent communication, Start server in background thread (+1 more)

### Community 10 - "Community 10"
Cohesion: 0.16
Nodes (4): AssetPlaceState, Key DOWN / UP transitions for clean drag start/end.         Works as a suppleme, Show or hide the xform handle and update the prompt message., Interactive placement state for the pf_asset_place HDA.

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (29): float2, float3, float4, pf_hash1(), pf_hash21(), pf_hash22(), pf_hash2d(), pf_hash43() (+21 more)

### Community 12 - "Community 12"
Cohesion: 0.05
Nodes (38): Done when, Normalize the input with Match Size (not custom VEX), Production reference — `pf::mesh_to_quad` (the battle-tested pattern), Skill: Conform a tile onto every prim of a surface (VEX + primuv), The conform (Detail wrangle: input0 = target+N, input1 = unit tile), The pipeline, The three gotchas (these are why a naive build looks wrong despite no errors), Use VEX (or OpenCL), never Python (+30 more)

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
Cohesion: 0.05
Nodes (36): Architecture, Automated verification via hython, Binding Types, Building, Copernicus OpenCL HDA Development Guide, Critical OpenCL vs GLSL Differences, Critical Rules, devScript Structure (+28 more)

### Community 18 - "Community 18"
Cohesion: 0.21
Nodes (6): AssetPlaceNodeUI, Python Panel widget for pf_asset_place HDA.      Embeds the full AssetBrowserW, Called by onNodePathChanged — updates which node we drive., Reload asset list (called on pane activation)., Highlight the thumbnail matching the node's current asset_id., User double-clicked an asset — push into node parms.

### Community 19 - "Community 19"
Cohesion: 0.23
Nodes (13): Module reloader for Polyfactory development  Intelligently reloads modules for, Reload widget library modules., Reload asset library modules., Reload viewer utilities modules., Reload UI framework modules (PyOneDark-based)., Reload all Polyfactory modules., Internal helper to reload a list of modules., reload_all() (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.22
Nodes (8): Any, BridgeClient, BridgeError, Bridge client — thin sync WebSocket + MessagePack client for the in-Houdini bri, Run a CommandExecutor command. Returns the raw response dict         ({'success, houdini_execute_python(), Execute arbitrary Python in the Houdini session (`hou` is in scope).     Assign, RuntimeError

### Community 21 - "Community 21"
Cohesion: 0.24
Nodes (12): get_skill(), list_skills(), _parse_frontmatter(), Skills registry — the extendable recipe library the MCP serves to agents.  Pur, Split `---`-delimited frontmatter from the markdown body.      Frontmatter is, Discovery: summary metadata for every skill (not the bodies)., Retrieval: the full markdown of one skill, by `name` or filename stem., Self-extension: write a new skill (or update an existing one). Returns the path. (+4 more)

### Community 22 - "Community 22"
Cohesion: 0.16
Nodes (13): Geometry, Matrix4, align_transform_to_normal(), extract_rotation_from_matrix(), get_geometry_under_cursor(), Raycasting utilities for viewer states Pure functions for ray-geometry intersec, Get geometry under cursor using ray intersection.          Args:         ui_e, Raycast against geometry and return hit information.          Args:         o (+5 more)

### Community 23 - "Community 23"
Cohesion: 0.06
Nodes (19): AssetDatabase, Manages the asset library SQLite database, Add a new asset to the database                  Args:             name: Asse, Initialize database connection                  Args:             db_path: Pa, Associate tags with an asset, Get asset by ID                  Args:             asset_id: Asset ID, Get all tags for an asset                  Args:             asset_id: Asset, Search assets with various filters                  Args:             search_ (+11 more)

### Community 25 - "Community 25"
Cohesion: 0.05
Nodes (36): 1. Create the HDA, 2. Add Python Panel Interface, 3. Set Interface as Default, 4. Configure Multiparm Structure, Add Custom Controls, Adding Assets, Asset Browser Empty, Asset Browser Section (+28 more)

### Community 26 - "Community 26"
Cohesion: 0.05
Nodes (37): 1. Start Server in Houdini, 2. Connect from External Python, 3. Connect from VS Code Extension (TypeScript), Approval Modes, Architecture, Batch Commands, Connection Timeout, Dependencies (+29 more)

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
Cohesion: 0.07
Nodes (17): AssetThumbnailWidget, HoverSlider, _load_pixmap_cached(), Asset Browser Widgets - Low-level widget classes extracted from browser_ui.py., Return a cached, pre-scaled pixmap for path, loading from disk on miss., Individual asset thumbnail with animated hover outline, Update thumbnail size dynamically without re-reading disk, Scale the cached pixmap to the current thumb size (no disk I/O) (+9 more)

### Community 33 - "Community 33"
Cohesion: 0.06
Nodes (33): Adding New Placement Modes, Adding Viewer Utils Functions, Align to Mesh (Default), Alignment Issues, Architecture, Asset Data Flow, Components, Core Functions (+25 more)

### Community 34 - "Community 34"
Cohesion: 0.09
Nodes (14): Tag input widget with autocomplete and chip display, Set the list of available tags for autocomplete                  Args:, Get current list of tags                  Returns:             List of tag st, Set the current tags                  Args:             tags: List of tag str, Show dropdown menu with all available tags, Add a tag chip                  Args:             tag_text: Tag string to add, Remove a tag chip                  Args:             tag_text: Tag string to, Remove all chip widgets (+6 more)

### Community 35 - "Community 35"
Cohesion: 0.12
Nodes (13): EnhancedInputField, Base Parameter Widgets - Label, InputField, BaseParmWidget, ExpressionDialog, Enhanced InputField with all Houdini parameter polish features:     - Hover eff, ParmInt, Numeric Parameter Widgets - ParmFloat, ParmInt  Float and integer parameter wi, Integer parameter widget using Enhanced InputField with slider.          Combi, Handle value change from InputField., Update widget from parameter value. (+5 more)

### Community 36 - "Community 36"
Cohesion: 0.09
Nodes (13): AssetInfoPanel, Handle resize to update preview image size, Create styled label for form, Load turntable frames for animation, Display a specific frame, Display asset information, Load full turntable sequence on hover, Return to frame 5 on leave (+5 more)

### Community 37 - "Community 37"
Cohesion: 0.10
Nodes (12): HoverOutlineMixin, PyLineEdit, Fallback if hover_outline not available, QLineEdit, HoverOutlineMixin, Initialize hover outline animation.                  Args:             color:, Get current hover outline opacity (0.0 to 1.0), Set hover outline opacity (0.0 to 1.0) (+4 more)

### Community 38 - "Community 38"
Cohesion: 0.08
Nodes (25): 1. Start Bridge Server in Houdini, 2. Test Connection, 3. Try AI Agent Example, Approval Modes, AUTO (Default), "Command cancelled by user", "Connection refused", Debug mode (+17 more)

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
Cohesion: 0.18
Nodes (3): Ui_LeftColumn, PyIcon, PyLeftColumn

### Community 44 - "Community 44"
Cohesion: 0.67
Nodes (3): dropAccept(), get_drop_context(), get the context where the drop happened      Returns:         hou.NetowrkEdit

### Community 45 - "Community 45"
Cohesion: 0.08
Nodes (26): _call(), houdini_create_node(), houdini_delete_node(), houdini_get_errors(), houdini_get_node_info(), houdini_get_parameter(), houdini_get_selection(), houdini_read_network() (+18 more)

### Community 46 - "Community 46"
Cohesion: 0.10
Nodes (19): Asset Browser as Pane, Asset Browser Redesign, Asset Library & Kitbash Workflow Redesign, Asset Placement Workflow, Browser Structure (Blender-Style Layout), Custom HDA Design, Drag & Drop, Export Workflow (+11 more)

### Community 47 - "Community 47"
Cohesion: 0.13
Nodes (7): AssetExportDialog, Dialog for exporting selected geometry to asset library, Keep blank row name fields showing the effective base name they will use., Load existing categories from database, Handle name confirmation (Enter key or lost focus) - auto-suggest category and t, Update the export path preview, Get the export configuration data

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
Cohesion: 0.18
Nodes (9): MessageHandler, Handle batch of commands, Check if command modifies scene state, Generate human-readable command description, Handles incoming messages and routes to appropriate handlers, Generate preview of command effects, Handle binary MessagePack message.                  Args:             data: M, Handle decoded message and return response.                  Args: (+1 more)

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
Cohesion: 0.11
Nodes (7): FlowLayout, Tag Input Widget - Autocompleting tag input with removable chips Similar to Sho, Layout that wraps widgets to multiple lines like text flow, Custom paint to draw rounded background with darker blue + animated hover outlin, Handle remove button click, Individual tag chip with remove button, TagChip

### Community 60 - "Community 60"
Cohesion: 0.17
Nodes (12): createViewerStateTemplate(), _ground_plane_hit(), _normal_to_euler(), Asset Placement Viewer State for pf_asset_place HDA.  Two modes (toggle with Q, Intersect against ONLY the geometry connected to SOP input 0.          Input g, Raycast against input geometry only, set t/r parms on node., Return XYZ Euler angles (degrees) that rotate +Y to align with normal.      Bu, Intersect ray with Y=0 ground plane. Returns hit position or None. (+4 more)

### Community 61 - "Community 61"
Cohesion: 0.14
Nodes (6): AssetGroupRow, Asset Group Row widget used by the inline batch mode in AssetExportDialog., Returns the per-row name, or empty string if blank (caller applies dialog-level, Fill in category/tags only if the prim had no attributes for them., Update the status dot to reflect export progress.          Args:, One row in the detected-assets list.      Displays a checkbox, sequential inde

### Community 62 - "Community 62"
Cohesion: 0.20
Nodes (10): Command Executor - Handles AI agent commands in Houdini session  Supports: -, Houdini Bridge - AI Agent WebSocket Server  Enables AI agents in VS Code to co, Message Handler - Processes WebSocket messages with MessagePack  Protocol: -, get_server(), Bridge Server - WebSocket server for AI agent communication  Uses synchronous, Get or create global server instance (survives module reload), Start global server instance, Stop global server instance (+2 more)

### Community 63 - "Community 63"
Cohesion: 0.16
Nodes (14): _aabbs_overlap(), detect_asset_groups(), export_batch_group(), next_free_filename(), Batch Kitbash Importer - AABB-based asset detection and batch export backend, Find the next available numbered filename (no extension).      Scans both the, Export a single asset group detected by detect_asset_groups.      Converts pri, Detect asset groups in a SOP node using connectivity + AABB overlap.      Each (+6 more)

### Community 64 - "Community 64"
Cohesion: 0.17
Nodes (5): Settings, Themes, object, PyWindow, Styles

### Community 67 - "Community 67"
Cohesion: 0.09
Nodes (16): AssetBrowserDialog, AssetDropHandler, _handle_drop(), Asset Browser UI - Grid view of assets with search and filtering, Standalone asset browser dialog, Double-click in the floating browser: create and connect the         asset plac, Show the asset browser dialog, Handles drops from the asset browser onto Houdini's viewport or network     edi (+8 more)

### Community 69 - "Community 69"
Cohesion: 0.18
Nodes (8): createInterface(), KitbashNodeUI, Kitbash HDA UI - Python Panel interface for pf_kitbash node  NEW WORKFLOW: -, Main UI for pf_kitbash node, Handle placed assets group box toggle, Refresh the UI - called when pane becomes active, Add selected asset from browser to library multiparm, Entry point for Python Panel UI.     Called by Houdini when creating the interf

### Community 70 - "Community 70"
Cohesion: 0.33
Nodes (5): 123.py - Auto-loaded on Houdini startup Registers custom viewer states, Register all Polyfactory viewer states, Auto-start the Houdini Bridge (AI-agent control) on interactive launch.      `, register_viewer_states(), start_bridge_server()

### Community 72 - "Community 72"
Cohesion: 0.20
Nodes (8): Asset Place HDA UI - Python Panel for pf_asset_place node.  Shows the full ass, apply_houdini_font(), get_font_stylesheet(), get_houdini_font(), UI utilities for matching Houdini's font sizes and scaling, Get Houdini's default application font.          Returns:         QFont objec, Generate font stylesheet matching Houdini's scaling.          Args:         s, Apply Houdini's font to a widget with optional size override.          Args:

### Community 73 - "Community 73"
Cohesion: 0.31
Nodes (5): Initialize UI components that require a node, Update the node reference - called when node path changes, get_scaled_font_size(), Get font size scaled to match Houdini's UI scaling.          Args:         ba, SopNode

### Community 74 - "Community 74"
Cohesion: 0.22
Nodes (3): PyCircularProgress, QColor, Set background color for expression state.

### Community 75 - "Community 75"
Cohesion: 0.19
Nodes (11): SQLite database management for asset library, Asset Library Module for Polyfactory Handles kitbash asset management, export,, _cleanup(), _create_render_scene(), Turntable Renderer - Creates rotating preview animations for assets, Render frames using viewport flipbook          Args:         lop_net: LOP net, Remove temporary nodes and panes          Args:         temp_nodes: List of n, Render a turntable animation of the geometry          Args:         geo_node: (+3 more)

### Community 76 - "Community 76"
Cohesion: 0.25
Nodes (5): Handle export button click, acquire_shared_panel(), Create a shared floating panel for batch renders.      Call once before starti, Close the shared panel acquired by acquire_shared_panel().      Call once afte, release_shared_panel()

### Community 77 - "Community 77"
Cohesion: 0.19
Nodes (7): ApprovalManager, _display_message(), Request approval for batch of commands.                  Returns list of appro, hou.ui.displayMessage marshaled onto the main thread. Approval runs on the, Manages command approval flow with UI dialogs, Check if command requires user approval, Show approval dialog to user.                  Args:             command: Com

### Community 78 - "Community 78"
Cohesion: 0.32
Nodes (3): _ToolTip, _ToolTip, QLabel

### Community 79 - "Community 79"
Cohesion: 0.10
Nodes (6): PySlider, PyTableWidget, PyToggle, QCheckBox, QSlider, QTableWidget

### Community 80 - "Community 80"
Cohesion: 0.25
Nodes (6): Export UI Panel for Asset Library, Show the export dialog with current selection          Args:         parent:, show_export_dialog(), export_selected_to_library(), Hotkey command script to open asset export dialog This script can be bound to a, Main function to trigger asset export dialog

### Community 81 - "Community 81"
Cohesion: 0.32
Nodes (5): PlacedAssetsListWidget, Widget displaying list of placed assets with controls, Refresh asset list from multiparm, Delete asset from multiparm, Poll for parameter changes from external sources

### Community 83 - "Community 83"
Cohesion: 0.25
Nodes (7): 1. The rig — use Otto (native, skinned biped), 2. Rigging YOUR OWN character meshes, 3. Pose library (native — this is the "pose library" answer), 4. Animation sources, 5. Retargeting workflow (any source → Otto/custom), Canonical docs, Done when

### Community 84 - "Community 84"
Cohesion: 0.25
Nodes (7): Attribution, Credits, Modifications, Polyfactory Integration, Polyfactory UI Framework, Structure, Usage in Polyfactory

### Community 85 - "Community 85"
Cohesion: 0.29
Nodes (6): 1. Install MCP server deps (one time), 2. Start the in-Houdini bridge, 3. Register the MCP server with your client, Houdini Bridge MCP — Setup, Notes, Tools

### Community 86 - "Community 86"
Cohesion: 0.29
Nodes (6): Done when, Learn the format from real nodes (don't guess), Skill: Document a custom HDA (so it's discoverable), Style, The format (Houdini wiki markup), Where the help goes

### Community 87 - "Community 87"
Cohesion: 0.29
Nodes (4): ParmString, Update visual feedback for expression state., String input widget with enhanced label., Reset parameter to default value (Ctrl+MMB on label).

### Community 88 - "Community 88"
Cohesion: 0.40
Nodes (5): houdini_render_view(), houdini_save_skill(), Bank a new skill/recipe so future agents can discover and reuse it.     Call thi, Render a deterministic screenshot of a node's geometry and return it as an, Bank a new skill/recipe so future agents can discover and reuse it.     Call th

### Community 90 - "Community 90"
Cohesion: 0.50
Nodes (3): Conventions, Houdini bridge — Skills, Skill file format

### Community 97 - "Community 97"
Cohesion: 0.50
Nodes (4): Enum, ApprovalMode, Approval System - Safety controls for AI commands  Modes: - AUTO: Execute rea, Command approval modes for safety

## Knowledge Gaps
- **309 isolated node(s):** `Project Overview`, `Package Structure`, `Environment Variables`, `Temporary / One-Off Scripts`, `Houdini Bridge - AI Agent Integration` (+304 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **11 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `PyPushButton` connect `Community 67` to `Community 32`, `Community 0`, `Community 65`, `Community 36`, `Community 69`, `Community 7`, `Community 72`, `Community 73`, `Community 47`, `Community 79`, `Community 81`, `Community 24`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `HoverOutlineMixin` connect `Community 37` to `Community 32`, `Community 0`, `Community 34`, `Community 36`, `Community 69`, `Community 7`, `Community 15`, `Community 81`, `Community 59`?**
  _High betweenness centrality (0.074) - this node is a cross-community bridge._
- **Why does `AssetBrowserWidget` connect `Community 0` to `Community 32`, `Community 34`, `Community 67`, `Community 36`, `Community 37`, `Community 69`, `Community 7`, `Community 73`, `Community 81`, `Community 18`, `Community 23`, `Community 59`?**
  _High betweenness centrality (0.047) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `AssetBrowserWidget` (e.g. with `AssetPlaceNodeUI` and `._setup_ui()`) actually correct?**
  _`AssetBrowserWidget` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TagInputWidget` (e.g. with `AssetInfoPanel` and `._setup_ui()`) actually correct?**
  _`TagInputWidget` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AssetDatabase` (e.g. with `next_free_filename()` and `AssetBrowserDialog`) actually correct?**
  _`AssetDatabase` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `CommandExecutor` (e.g. with `MessageHandler` and `.__init__()`) actually correct?**
  _`CommandExecutor` has 2 INFERRED edges - model-reasoned connections that need verification._