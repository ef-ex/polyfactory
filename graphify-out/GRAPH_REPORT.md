# Graph Report - polyfactory  (2026-05-02)

## Corpus Check
- 133 files · ~102,022 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 1268 nodes · 1866 edges · 61 communities detected
- Extraction: 86% EXTRACTED · 14% INFERRED · 0% AMBIGUOUS · INFERRED: 260 edges (avg confidence: 0.65)
- Token cost: 0 input · 0 output

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
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 71|Community 71]]

## God Nodes (most connected - your core abstractions)
1. `AssetBrowserWidget` - 37 edges
2. `TagInputWidget` - 35 edges
3. `AssetDatabase` - 33 edges
4. `AssetInfoPanel` - 23 edges
5. `AssetExportDialog` - 23 edges
6. `PyPushButton` - 22 edges
7. `BindingManager` - 22 edges
8. `BaseParmWidget` - 22 edges
9. `PyLeftMenuButton` - 21 edges
10. `HoverOutlineMixin` - 21 edges

## Surprising Connections (you probably didn't know these)
- `createInterface()` --calls--> `BindingManager`  [INFERRED]
  devScripts\hda_ui_example.py → polyfactory\scripts\python\polyfactory\widgets\binding_manager.py
- `AssetBrowserState` --uses--> `AssetBrowserDialog`  [INFERRED]
  devScripts\viewer_state_context_menu_example.py → polyfactory\scripts\python\polyfactory\asset_library\browser_ui.py
- `pf_perlin_d()` --calls--> `pf_qerp_td()`  [INFERRED]
  polyfactory\ocl\include\pf_noise.h → polyfactory\ocl\include\pf_util.h
- `HoverSlider` --uses--> `HoverOutlineMixin`  [INFERRED]
  polyfactory\scripts\python\polyfactory\asset_library\asset_browser_widgets.py → polyfactory\scripts\python\polyfactory\widgets\hover_outline.py
- `HoverComboBox` --uses--> `HoverOutlineMixin`  [INFERRED]
  polyfactory\scripts\python\polyfactory\asset_library\asset_browser_widgets.py → polyfactory\scripts\python\polyfactory\widgets\hover_outline.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.02
Nodes (88): AssetInfoPanel, AssetThumbnailWidget, HoverComboBox, HoverSlider, _load_pixmap_cached(), Asset Browser Widgets - Low-level widget classes extracted from browser_ui.py., Handle resize to update preview image size, Create styled label for form (+80 more)

### Community 1 - "Community 1"
Cohesion: 0.02
Nodes (84): BaseParmWidget, BindingManager, Binding Manager - Central coordinator for parameter-widget synchronization  Ma, Create a dropdown menu widget bound to a parameter., Create a color picker widget bound to a parameter tuple., Manages parameter bindings for an HDA Python Panel UI.          Coordinates up, Create a button widget (not bound to parameter)., Register a widget-parameter binding. (+76 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (25): Ui_LeftColumn, Ui_RightColumn, Functions, Settings, Themes, SetupMainWindow, UI_MainWindow, object (+17 more)

### Community 3 - "Community 3"
Cohesion: 0.03
Nodes (63): _aabbs_overlap(), detect_asset_groups(), export_batch_group(), next_free_filename(), Batch Kitbash Importer - AABB-based asset detection and batch export backend, Find the next available numbered filename (no extension).      Scans both the, Export a single asset group detected by detect_asset_groups.      Converts pri, Detect asset groups in a SOP node using connectivity + AABB overlap.      Each (+55 more)

### Community 4 - "Community 4"
Cohesion: 0.03
Nodes (48): Enum, ApprovalManager, ApprovalMode, Approval System - Safety controls for AI commands  Modes: - AUTO: Execute rea, Command approval modes for safety, Manages command approval flow with UI dialogs, Check if command requires user approval, Show approval dialog to user.                  Args:             command: Com (+40 more)

### Community 5 - "Community 5"
Cohesion: 0.04
Nodes (40): AssetInstanceWidget, createInterface(), HoverListWidget, KitbashNodeUI, PlacedAssetsListWidget, Kitbash HDA UI - Python Panel interface for pf_kitbash node  NEW WORKFLOW: -, Create styled spinbox, Load values from node parameters (+32 more)

### Community 6 - "Community 6"
Cohesion: 0.07
Nodes (8): PyLeftButton, _ToolTip, _ToolTip, PyTitleBar, PyTitleButton, _ToolTip, QLabel, QPushButton

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (14): Hover Outline Mixin - Animated blue outline on hover for any widget, FlowLayout, Tag Input Widget - Autocompleting tag input with removable chips Similar to Sho, Layout that wraps widgets to multiple lines like text flow, Custom paint to draw rounded background with darker blue + animated hover outlin, Handle remove button click, Set the current tags                  Args:             tags: List of tag str, Show dropdown menu with all available tags (+6 more)

### Community 8 - "Community 8"
Cohesion: 0.1
Nodes (11): AssetPlaceState, _ground_plane_hit(), _normal_to_euler(), Asset Placement Viewer State for pf_asset_place HDA.  Two modes (toggle with Q, Key DOWN / UP transitions for clean drag start/end.         Works as a suppleme, Intersect against ONLY the geometry connected to SOP input 0.          Input g, Raycast against input geometry only, set t/r parms on node., Show or hide the xform handle and update the prompt message. (+3 more)

### Community 9 - "Community 9"
Cohesion: 0.11
Nodes (5): registerChatParticipant(), activate(), deactivate(), HoudiniBridgeClient, registerLanguageModelTools()

### Community 10 - "Community 10"
Cohesion: 0.13
Nodes (22): pf_hash1(), pf_hash21(), pf_hash2d(), pf_ihash(), pf_lattice(), pf_fbm(), pf_fbm_t(), pf_perlin() (+14 more)

### Community 11 - "Community 11"
Cohesion: 0.1
Nodes (2): PyLeftMenuButton, PyLeftMenu

### Community 12 - "Community 12"
Cohesion: 0.1
Nodes (14): createViewerStateTemplate(), KitbashPlacementState, Kitbash Placement State - Interactive viewport placement for assets  NEW WORKF, Place the currently selected mesh at cursor position, Handle keyboard events, Update menu state before opening, Interactive state for placing kitbash assets in viewport, Handle context menu selections (+6 more)

### Community 13 - "Community 13"
Cohesion: 0.11
Nodes (21): copy_parameter(), delete_expression(), get_expression_language(), get_expression_string(), get_parm_color(), get_parm_display_value(), has_expression(), paste_relative_reference() (+13 more)

### Community 14 - "Community 14"
Cohesion: 0.13
Nodes (13): createInterface(), Example HDA Python Panel UI using hda_widgets library  This demonstrates how t, Main entry point for Python Panel UI.     Called by Houdini when panel is creat, Example button callback., reset_node(), Build a layout containing all registered widgets.                  Args:, HoudiniGroupBox, HoudiniHLayout (+5 more)

### Community 15 - "Community 15"
Cohesion: 0.18
Nodes (2): PyIconButton, _ToolTip

### Community 16 - "Community 16"
Cohesion: 0.13
Nodes (10): addAssetBrowserToNodeState(), AssetBrowserState, createViewerStateTemplate(), Viewer State Context Menu Example  This shows how to add a context menu to a v, Open the asset browser dialog, Example of creating a viewer state template with a context menu          The c, Add asset browser to a node's viewer state context menu          Args:, Example viewer state with context menu (+2 more)

### Community 17 - "Community 17"
Cohesion: 0.15
Nodes (9): EnhancedInputField, Test inheritance from hou.qt.InputField to verify we can add custom features. R, Test inheriting from InputField to add custom features., Try to locate internal QLineEdit and QLabel widgets., Override to add hover effect., Override to remove hover effect., Intercept events on child widgets (like label)., Create test dialog with enhanced InputField. (+1 more)

### Community 18 - "Community 18"
Cohesion: 0.18
Nodes (7): AssetPlaceNodeUI, Asset Place HDA UI - Python Panel for pf_asset_place node.  Shows the full ass, Python Panel widget for pf_asset_place HDA.      Embeds the full AssetBrowserW, Called by onNodePathChanged — updates which node we drive., Reload asset list (called on pane activation)., Highlight the thumbnail matching the node's current asset_id., User double-clicked an asset — push into node parms.

### Community 19 - "Community 19"
Cohesion: 0.23
Nodes (13): Module reloader for Polyfactory development  Intelligently reloads modules for, Reload widget library modules., Reload asset library modules., Reload viewer utilities modules., Reload UI framework modules (PyOneDark-based)., Reload all Polyfactory modules., Internal helper to reload a list of modules., reload_all() (+5 more)

### Community 20 - "Community 20"
Cohesion: 0.2
Nodes (1): MainFunctions

### Community 21 - "Community 21"
Cohesion: 0.18
Nodes (11): align_transform_to_normal(), extract_rotation_from_matrix(), get_geometry_under_cursor(), Raycasting utilities for viewer states Pure functions for ray-geometry intersec, Get geometry under cursor using ray intersection.          Args:         ui_e, Raycast against geometry and return hit information.          Args:         o, Create transformation matrix to align object to surface normal.          Args:, Extract Euler rotation angles (XYZ order) from transformation matrix. (+3 more)

### Community 22 - "Community 22"
Cohesion: 0.29
Nodes (10): add_cp_empties(), apply_material(), build_module(), clear_scene(), compute_dimensions(), create_module_box(), parse_module_id(), Galaxia Module Scaffolder for Blender.  Usage:     Set MODULE_ID at the top, (+2 more)

### Community 23 - "Community 23"
Cohesion: 0.31
Nodes (8): _build_parm_template_group(), _configure_opencl(), create(), Create pf_hull_panels.hda — procedural sci-fi hull panel texture generator.  O, Set kernel code, outputs (Signature tab), and constant bindings., Drive inner opencl binding value parms via ch() expressions pointing to HDA oute, Build pf_hull_panels.hda and install it in polyfactory/otls/.      Copernicus, _wire_channel_refs()

### Community 24 - "Community 24"
Cohesion: 0.28
Nodes (4): HoverOutlineMixin, PyLineEdit, Fallback if hover_outline not available, QLineEdit

### Community 25 - "Community 25"
Cohesion: 0.22
Nodes (2): PyToggle, QCheckBox

### Community 26 - "Community 26"
Cohesion: 0.32
Nodes (5): ExampleTool, main(), Example: Using Polyfactory UI Framework in a standalone tool  This demonstrate, Example standalone tool using UI framework., Launch the example tool.

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
Cohesion: 0.53
Nodes (5): _build_ptg(), _configure_opencl(), create(), create_pf_bnw_spots_hda.py — Build pf_bnw_spots.hda for Houdini Copernicus.  V, _wire_channel_refs()

### Community 32 - "Community 32"
Cohesion: 0.53
Nodes (5): _build_ptg(), _configure_opencl(), create(), create_pf_caustic_fbm_hda.py — Build pf_caustic_fbm.hda for Houdini Copernicus., _wire_channel_refs()

### Community 33 - "Community 33"
Cohesion: 0.53
Nodes (5): _build_ptg(), _configure_opencl(), create(), create_pf_caustic_trig_hda.py — Build pf_caustic_trig.hda for Houdini Copernicus, _wire_channel_refs()

### Community 34 - "Community 34"
Cohesion: 0.53
Nodes (5): _build_ptg(), _configure_opencl(), create(), create_pf_crater_noise_hda.py — Build pf_crater_noise.hda for Houdini Copernicus, _wire_channel_refs()

### Community 35 - "Community 35"
Cohesion: 0.53
Nodes (5): _build_ptg(), _configure_opencl(), create(), create_pf_gyroid_noise_hda.py — Build pf_gyroid_noise.hda for Houdini Copernicus, _wire_channel_refs()

### Community 36 - "Community 36"
Cohesion: 0.53
Nodes (5): _build_ptg(), _configure_opencl(), create(), create_pf_landmass_noise_hda.py — Build pf_landmass_noise.hda for Houdini Copern, _wire_channel_refs()

### Community 37 - "Community 37"
Cohesion: 0.53
Nodes (5): _build_ptg(), _configure_opencl(), create(), create_pf_nebula_noise_hda.py — Build pf_nebula_noise.hda for Houdini Copernicus, _wire_channel_refs()

### Community 38 - "Community 38"
Cohesion: 0.33
Nodes (5): draw_crosshair(), draw_normal_indicator(), Drawing utilities for viewer states Pure functions for viewport drawing helpers, Draw simple crosshair at position.          Args:         drawable: Houdini d, Draw line indicating surface normal.          Args:         drawable: Houdini

### Community 39 - "Community 39"
Cohesion: 0.4
Nodes (5): Parameter Panel Utilities - Helper functions for creating floating parameter win, Open a floating parameter panel for a node using Houdini's native API., Show floating parameter panel for currently selected node.          Useful for, show_floating_parm_panel(), show_selected_node_parms()

### Community 40 - "Community 40"
Cohesion: 0.5
Nodes (4): main(), Lightweight Houdini Bridge command-line client Connects directly to WebSocket s, Send command to Houdini Bridge and return response, send_command()

### Community 41 - "Community 41"
Cohesion: 0.4
Nodes (4): get_prims_at_path(), get_sdf_type(), generator which returns all prims of type     which are child of given path, get Sdf Value Type      Args:         typ (str) : requested usd type     Ret

### Community 42 - "Community 42"
Cohesion: 0.5
Nodes (3): create_pf_kitbash_hda(), Script to create the pf_kitbash HDA Run this in Houdini Python shell to create, Create the pf_kitbash HDA definition

### Community 43 - "Community 43"
Cohesion: 0.5
Nodes (3): 123.py - Auto-loaded on Houdini startup Registers custom viewer states, Register all Polyfactory viewer states, register_viewer_states()

### Community 44 - "Community 44"
Cohesion: 0.67
Nodes (3): dropAccept(), get_drop_context(), get the context where the drop happened      Returns:         hou.NetowrkEdit

### Community 45 - "Community 45"
Cohesion: 0.67
Nodes (2): Send command to Houdini Bridge and return response, send_command()

### Community 46 - "Community 46"
Cohesion: 0.67
Nodes (1): create_pf_caustic_trig_vop_hda.py -- Build pf_caustic_trig_vop.hda for VOP netwo

### Community 47 - "Community 47"
Cohesion: 0.67
Nodes (1): Minimal WebSocket server test in Houdini  Run this in Houdini Python Shell to

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): Create pf_asset_place SOP HDA.  Run in Houdini Python Shell:     execfile(r'f

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): Create pf_asset_tag SOP HDA.  Run in Houdini Python Shell:     execfile(r'f:/pro

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): Debug USD stage composition - check what's actually in the turntable render scen

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Inspect renderproduct and rendersettings node parameters

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): Inspect USD Render node parameters

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): List LOP node types related to rendering

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): List available ROP node types in Houdini

### Community 55 - "Community 55"
Cohesion: 1.0
Nodes (1): Test script to verify pf_kitbash node type name Run in Houdini Python Shell

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Test script to manually open the kitbash Python Panel Run in Houdini Python She

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): Quick test to verify USD export and lighting template

### Community 60 - "Community 60"
Cohesion: 2.0
Nodes (1): Polyfactory UI Framework =========================  Modern Qt widget library

### Community 61 - "Community 61"
Cohesion: 2.0
Nodes (1): Viewer utilities for Houdini viewer states Reusable library components for rayc

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): Create a pf_asset_place node in the current network, wire it to the         cur

## Knowledge Gaps
- **399 isolated node(s):** `Galaxia Module Scaffolder for Blender.  Usage:     Set MODULE_ID at the top,`, `Extract ship class, size, height from a module id string.`, `Place CP_D# ARROWS empties at the centre of each face, pointing outward (+Z).`, `Send command to Houdini Bridge and return response`, `Script to create the pf_kitbash HDA Run this in Houdini Python shell to create` (+394 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 11`** (27 nodes): `PyLeftMenuButton`, `.change_style()`, `.enterEvent()`, `.icon_active()`, `.icon_paint()`, `.is_active()`, `.is_active_tab()`, `.leaveEvent()`, `.mousePressEvent()`, `.mouseReleaseEvent()`, `.move_tooltip()`, `.paintEvent()`, `.set_active()`, `.set_active_tab()`, `.set_active_toggle()`, `.set_icon()`, `PyLeftMenu`, `.add_menus()`, `.btn_clicked()`, `.btn_released()`, `.deselect_all()`, `.deselect_all_tab()`, `.__init__()`, `.select_only_one()`, `.select_only_one_tab()`, `.setup_ui()`, `.toggle_animation()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (17 nodes): `__init__.py`, `py_icon_button.py`, `PyIconButton`, `.change_style()`, `.enterEvent()`, `.icon_paint()`, `.__init__()`, `.is_active()`, `.leaveEvent()`, `.mousePressEvent()`, `.mouseReleaseEvent()`, `.move_tooltip()`, `.paintEvent()`, `.set_active()`, `.set_icon()`, `_ToolTip`, `.__init__()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 20`** (12 nodes): `MainFunctions`, `.get_left_menu_btn()`, `.get_title_bar_btn()`, `.__init__()`, `.left_column_is_visible()`, `.right_column_is_visible()`, `.set_left_column_menu()`, `.set_page()`, `.set_right_column_menu()`, `.start_box_animation()`, `.toggle_left_column()`, `.toggle_right_column()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (9 nodes): `__init__.py`, `py_toggle.py`, `position()`, `PyToggle`, `.hitButton()`, `.__init__()`, `.paintEvent()`, `.setup_animation()`, `QCheckBox`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (3 nodes): `copilot_houdini_helper.py`, `Send command to Houdini Bridge and return response`, `send_command()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (3 nodes): `create()`, `create_pf_caustic_trig_vop_hda.py`, `create_pf_caustic_trig_vop_hda.py -- Build pf_caustic_trig_vop.hda for VOP netwo`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (3 nodes): `handle_connection()`, `test_websocket_minimal.py`, `Minimal WebSocket server test in Houdini  Run this in Houdini Python Shell to`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (2 nodes): `create_pf_asset_place_hda.py`, `Create pf_asset_place SOP HDA.  Run in Houdini Python Shell:     execfile(r'f`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (2 nodes): `create_pf_asset_tag_hda.py`, `Create pf_asset_tag SOP HDA.  Run in Houdini Python Shell:     execfile(r'f:/pro`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (2 nodes): `debug_usd_stage.py`, `Debug USD stage composition - check what's actually in the turntable render scen`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (2 nodes): `inspect_render_nodes.py`, `Inspect renderproduct and rendersettings node parameters`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (2 nodes): `inspect_usdrender.py`, `Inspect USD Render node parameters`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (2 nodes): `list_lop_nodes.py`, `List LOP node types related to rendering`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (2 nodes): `list_rop_nodes.py`, `List available ROP node types in Houdini`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 55`** (2 nodes): `test_kitbash_node_type.py`, `Test script to verify pf_kitbash node type name Run in Houdini Python Shell`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (2 nodes): `test_open_kitbash_panel.py`, `Test script to manually open the kitbash Python Panel Run in Houdini Python She`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (2 nodes): `test_usd_setup.py`, `Quick test to verify USD export and lighting template`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (2 nodes): `__init__.py`, `Polyfactory UI Framework =========================  Modern Qt widget library`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (2 nodes): `__init__.py`, `Viewer utilities for Houdini viewer states Reusable library components for rayc`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `Create a pf_asset_place node in the current network, wire it to the         cur`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `HoverOutlineMixin` connect `Community 5` to `Community 0`, `Community 24`, `Community 7`?**
  _High betweenness centrality (0.150) - this node is a cross-community bridge._
- **Why does `PyPushButton` connect `Community 0` to `Community 2`, `Community 3`, `Community 5`, `Community 6`?**
  _High betweenness centrality (0.112) - this node is a cross-community bridge._
- **Why does `AssetBrowserDialog` connect `Community 0` to `Community 16`, `Community 24`, `Community 7`?**
  _High betweenness centrality (0.093) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `AssetBrowserWidget` (e.g. with `AssetPlaceNodeUI` and `PyPushButton`) actually correct?**
  _`AssetBrowserWidget` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 15 inferred relationships involving `TagInputWidget` (e.g. with `HoverSlider` and `HoverComboBox`) actually correct?**
  _`TagInputWidget` has 15 INFERRED edges - model-reasoned connections that need verification._
- **Are the 12 inferred relationships involving `AssetDatabase` (e.g. with `AssetBrowserWidget` and `AssetBrowserDialog`) actually correct?**
  _`AssetDatabase` has 12 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `AssetInfoPanel` (e.g. with `PyPushButton` and `HoverOutlineMixin`) actually correct?**
  _`AssetInfoPanel` has 7 INFERRED edges - model-reasoned connections that need verification._