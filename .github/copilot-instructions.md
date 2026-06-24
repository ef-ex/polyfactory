# Polyfactory - AI Coding Agent Instructions

> **Shared rules** (git workflow, error tracking, temp scripts path, etc.) are in `d:\copilot\.github\copilot-instructions.md`. This file has Polyfactory-specific architecture and rules only.

## Project Overview
Polyfactory is a **Houdini package** (artist-friendly procedural tools) for SideFX Houdini. It provides HDAs (Houdini Digital Assets), Python scripts, custom panels, and USD workflows for procedural modeling and kitbashing.

**Current Branch: `asset-library`** - Active development focuses on USD asset management, export UI, and turntable rendering systems.

## Installation & Setup

### Package Structure
Polyfactory uses Houdini's package system. Installation:
1. Place repo in preferred location (e.g., `f:/projects/polyfactory`)
2. Copy `polyfactory.json` to `$HOUDINI_USER_PREF_DIR/packages/`
3. Edit JSON, replace `"path/to/polyfactory"` with actual install path
4. Launch Houdini - environment variables auto-configured

### Environment Variables
Defined in `polyfactory.json`:
- `$POLYFACTORY` - Root package directory
- `$PF_LDRAW` - LDraw library path (if using brick assets)
- `$PF_ASSET_LIBRARY` - Asset library location (`$POLYFACTORY/library/assets`)
- `$PF_ASSET_DB` - SQLite database for asset management
- `$HOUDINI_TOOLBAR_PATH` - Custom shelf tools

**Always use environment variables in paths**, not hardcoded paths.

## Key Workflows

### Temporary / One-Off Scripts
**All temporary scripts created by the AI agent must be saved to:**
```
d:\copilot\scripts\
```
Never save throwaway scripts inside the project they operate on.

### Houdini Bridge - AI Agent Integration
**Reference:** Read `d:\copilot\docs\polyfactory\ref_houdini_bridge.md` when controlling Houdini programmatically.
WebSocket server (port 9876) + CLI at `devScripts/houdiniBridge/houdini_cmd.py`. Supports create/delete nodes, batch ops, Python exec.

### Developing HDAs
HDAs live in `polyfactory/otls/`. Naming convention: `pf_<descriptive_name>.hda`

Examples: `pf_advanced_tube.hda`, `pf_kitbash.hda`, `pf_axis_gizmo.hda`

When creating new HDAs:
1. Use `pf_` prefix consistently
2. Store in `otls/` directory
3. Reference `$POLYFACTORY` in file paths within HDA
4. Test with environment variable resolution

### Kitbash Workflow (pf_kitbash HDA)
**Reference:** Read `d:\copilot\docs\polyfactory\ref_houdini_bridge.md` for kitbash HDA parameters, workflow, and state details.
Viewport-based kitbashing: library multiparm + Enter to activate placement state + click to place. State is viewport-only, HDA handles geometry.

### Python Scripts
Two locations:
- `devScripts/` - Development/debugging scripts (not loaded by Houdini)
- `polyfactory/scripts/` - Production scripts loaded by Houdini

Dev script examples in `devScripts/`:
- `test_usd_setup.py` - Verify USD export and env vars
- `inspect_render_nodes.py` - Debug render node setup
- `create_kitbash_hda.py` - HDA generation utilities

Always check environment variables at script start:
```python
import hou, os

# Verify environment
polyfactory_path = os.environ.get('POLYFACTORY')
if not polyfactory_path:
    raise RuntimeError("POLYFACTORY environment variable not set")
```

**CRITICAL: Module Reloading Pattern**

When adding new Python modules to a package (e.g., `polyfactory/widgets/`):
1. Create the module file (e.g., `new_module.py`)
2. Import it in the package's `__init__.py`: `from . import new_module`
3. Add it to the reload function in `reload_modules.py`

This ensures:
- Module is loaded into `sys.modules` on first import
- Reload function can find and reload it during development
- No need to restart Houdini to test changes

Example for widgets package:
```python
# In polyfactory/widgets/__init__.py:
from . import parm_utils
from . import ladder_mixin  # ← New module

# In reload_modules.py:
def reload_widgets():
    modules = [
        'polyfactory.widgets.parm_utils',
        'polyfactory.widgets.ladder_mixin',  # ← New module
        'polyfactory.widgets.widgets',
        # ...
    ]
```

### USD Workflows
Lighting template: `library/lighting_template.usda`

USD assets stored in `library/assets/`. Access via `$PF_ASSET_LIBRARY`.

### Python Panels & HDA UIs
**Reference:** Read `d:\copilot\docs\polyfactory\ref_python_panels.md` when building Python panels, HDA UIs, or widget bindings.
PySide6, `onCreateInterface()` lifecycle, `<showInParametersPane>` optype binding, font scaling via `ui_utils.py`, BindingManager for HDA parameter sync.

### PyOneDark UI Framework
**Reference:** Read `d:\copilot\docs\polyfactory\ref_ui_widgets.md` when building custom UIs, hover effects, or widget styling.
OneDark color scheme (`#61afef` blue accent, `#1e1e1e` bg). Use `HoverOutlineMixin` for animated hover outlines. `FlowLayout` for responsive wrapping. Inherit from `hou.qt.InputField`/`ColorField` for enhanced widgets.

## Project Structure
- `polyfactory/` - Main package directory (loaded by Houdini)
  - `otls/` - HDA digital assets (33 tools)
  - `scripts/` - Python scripts (`python/` subfolder)
  - `python_panels/` - Custom panel definitions
  - `library/` - Asset library, USD templates, OBJ/brick models
  - `icons/`, `hotkeys/`, `toolbar/`, `vex/` - Additional resources
  - `OPmenu.xml`, `PARMmenu.xml`, `PaneTabTypeMenu.xml` - Context menu configs
- `devScripts/` - Development utilities (not in package path)
- `backup/` - Houdini autosave files (`test_bak*.hip`)
- `test.hip` - Main test scene

### Branch Structure
Polyfactory uses feature branches for specialized toolsets:
- **`asset-library` (CURRENT)** - USD asset management, export UI, turntable rendering
  - Python modules: `asset_library/` (database, export_ui, exporter, render)
  - Widgets: ShotGrid-style tag input with auto-completion
  - Active development focus
- `main` - Core HDAs and utilities
- `bricks` - LDraw brick import and building workflows
- `cityGen` - City/street generation tools
- `development` - Integration branch for testing
- `experimental` - R&D features

Branches contain specialized VEX libraries and HDAs. Check branch-specific tools before implementing similar functionality.

### Relationship to Galaxia
Polyfactory is **independent** but used to create content for Galaxia (space game in Godot). Some tools export assets/modules for Galaxia's modular ship system.

**Full spec:** `d:\godotGames\galaxia\documentation\module_set_spec.md` — read this before asking any question about module naming, connection points, grid sizes, or class separation. It is the authoritative source.

---

#### Galaxia Module Pipeline
**Reference:** Read `d:\copilot\docs\polyfactory\ref_galaxia_modules.md` when working on module export, naming conventions, or connection points.
Module naming: `{type}_{SIZE}_{HEIGHT}_{CLASS}_{PATTERN}_{TIER}[_V{n}]`. CP nulls: `CP_D{n}` (default) and `CP_U{n}` (utility). GLB export post-processes to fix null names.

---

## Common Patterns

### Accessing Package Assets
```python
# Asset library
asset_lib = os.path.join(os.environ['PF_ASSET_LIBRARY'], 'subfolder')

# Template files
template = os.path.join(os.environ['POLYFACTORY'], 'library', 'lighting_template.usda')

# Check existence before use
if not os.path.exists(asset_lib):
    hou.ui.displayMessage("Asset library not found", severity=hou.severityType.Error)
```

### HDA Parameter Setup
When building HDAs, use:
- Multiparms for repeating parameter blocks
- Folder tabs for organization
- Menu parameters with callbacks for dynamic menus
- Python callbacks via `kwargs["node"]` access

### Node Type Naming
Follow Houdini conventions:
- SOPs: Geometry operations
- LOPs: USD/Solaris operations  
- ROPs: Render output drivers
- TOPs: Task/dependency graphs (PDG)

Use `pf::` namespace for custom nodes (auto-applied via HDA naming).

### Viewer State Context Menus
Context menus (right-click in viewport) use **`hou.ViewerStateMenu`**:
- API documentation: `$HFS/houdini/python3.11libs/hou.py` (search for "ViewerStateMenu")
- Bind to state template: `template.bindMenu(menu)`
- Handle menu clicks: `onMenuAction(kwargs)` method in state class
- Menu item types:
  - `addActionItem()` - Clickable actions
  - `addToggleItem()` - Checkboxes  
  - `addRadioStrip()` - Mutually exclusive options
  - `addMenu()` - Sub-menus
  - `addSeparator()` - Visual dividers
- Example: `devScripts/viewer_state_context_menu_example.py`

Finding API patterns:
```powershell
# Search Houdini installation for implementation examples
Get-ChildItem "$HFS" -Recurse -Filter "*.py" | Select-String -Pattern "onMenuAction|ViewerStateMenu"
```

### Python State Development
**Design Philosophy: Modular, Composable, Functional**

Viewer states should be built from reusable library components (like Qt widgets):
- **Separate concerns** - Extract gizmos, drawing utilities, raycasting, etc. into standalone modules
- **Reusable libraries** - Create `polyfactory/scripts/python/polyfactory/viewer_utils/` for shared functionality:
  - `gizmos.py` - Draw rotation/scale/transform gizmos
  - `raycasting.py` - Ground plane intersection, object snapping
  - `drawing.py` - Custom viewport drawing (lines, shapes, labels)
  - `input_handling.py` - Mouse/keyboard utilities
- **Follow functional programming guidelines** - See "Code Style: Functional Over Object-Oriented" in Critical Conventions

Example structure:
```python
# Good: Reusable function library
# polyfactory/viewer_utils/gizmos.py
def draw_rotation_gizmo(drawable, position, rotation, size=1.0):
    """Draw 3-axis rotation gizmo at position"""
    # Pure function - no state, reusable
    pass

def raycast_to_ground_plane(ui_event, y_offset=0.0):
    """Returns intersection point with Y=0 plane"""
    # Pure function
    return hou.Vector3(x, y_offset, z)

# Usage in state (class required by Houdini API):
from polyfactory.viewer_utils import gizmos, raycasting

class MyViewerState:
    def onDraw(self, kwargs):
        pos = raycasting.raycast_to_ground_plane(kwargs['ui_event'])
        gizmos.draw_rotation_gizmo(kwargs['draw_handle'], pos, self.rotation)
```

## Critical Conventions

### Creative / Procedural Tool Requests Require Design Breakdown First

**Never start implementing a creative or generative tool from a vague prompt.**

Words like "create a node that generates X", "make a shader for Y", or "build a texture tool" describe a *goal*, not a design. Jumping straight to implementation always produces something that does not match what the user had in mind.

**When a request involves creative or procedural content** (OpenCL kernels, texture generators, procedural HDAs, shaders, visual tools) **stop before writing any code and ask the user to answer these four questions:**

1. **Look:** What does the output look like? Reference images, adjectives, comparisons to known games/materials.
2. **Controls:** What are the key artistic parameters the user wants to tweak (count, depth, color, roughness, variation, etc.)?
3. **Outputs:** What channels / output wires are needed, and what do they drive downstream (albedo, height, normals, roughness, AO, masks)?
4. **References:** Are there existing nodes, tools, or resources that capture the target look?

Only start coding once all four questions have concrete answers.

See also: [`known_pitfalls.md`](.github/known_pitfalls.md) — *Proceeding on a vague creative/design prompt without breaking it down first*.

---

### Code Style: Functional Over Object-Oriented
**Prefer function libraries with pure functions over classes.**

Classes should only be used when there's a clear benefit:
- Required by APIs (viewer states, Qt widgets, HDA callbacks)
- Complex objects with lifecycle (database connections, caches, file handles)
- Clear encapsulation benefit (data + behavior tightly coupled)

**Default to pure functions for:**
- Utility functions (math, conversions, validation, formatting)
- Data transformations and processing
- Calculations and algorithms
- Any stateless operations

Benefits:
- Easier to test (no setup/teardown)
- Easier to reuse and compose
- No hidden state or side effects
- Clearer function signatures and contracts

### Code Quality - Error Handling

**CRITICAL: Error Prints vs Debug Prints**

Error prints in exception handlers are NOT debug prints - always keep them:

```python
# CORRECT - Error handling with logging
def set_expression(parm: hou.Parm, expression: str):
    try:
        parm.setExpression(expression)
    except Exception as e:
        print(f"Error setting expression on {parm.name()}: {e}")  # Keep this!

# WRONG - Silencing errors
def set_expression(parm: hou.Parm, expression: str):
    try:
        parm.setExpression(expression)
    except Exception:
        pass  # Never do this - hides real problems
```

**Debug prints to remove:**
- Flow control indicators: `print("Entering function X")`
- Intermediate values: `print(f"Value is {x}")`
- UI event tracking: `print("Button clicked")`

**Error prints to keep:**
- Exception messages in try/except blocks
- API call failures
- Invalid parameter states
- File/resource access errors

### Environment Variable Priority
Always prefer environment variables over hardcoded paths. Makes package portable across machines and Houdini versions.

### Houdini Version Support
Package targets Houdini 21.0+ (workspace includes 21.0.631 installation reference).

Test compatibility with:
- Python 3.11 (Houdini 21's Python version)
- **PySide6** (NOT PySide2) - Houdini 21's Qt binding

### Asset Database
`$PF_ASSET_DB` points to SQLite database for asset management. Scripts should handle gracefully if DB doesn't exist:
```python
db_path = os.environ.get('PF_ASSET_DB')
if db_path and os.path.exists(db_path):
    # Use asset database
else:
    # Fallback to file-based asset discovery
```

### Library Organization
- `library/assets/` - 3D models, textures
- `library/bricks/` - LDraw brick assets
- `library/obj/` - OBJ format meshes
- `library/lighting_template.usda` - USD lighting setup template

## Development Tools

### Houdini Source Reference
**The Houdini installation is loaded in the workspace** (`C:\Program Files\Side Effects Software\Houdini 21.0.631`) for reference when documentation is unclear.

Useful locations for implementation examples:
- `bin/*.py` - Command-line tools (hrender, usdBake, etc.)
- `python311/lib/` - Python standard library and packages
- `houdini/python3.11libs/` - Houdini Python modules
- Search for Python/VEX patterns when docs are insufficient

### Testing Scripts
Run dev scripts from Houdini Python Shell or external Python with `hou` module:
```bash
# External (requires hython or hou module in PYTHONPATH)
hython devScripts/test_usd_setup.py

# Or in Houdini Python Shell
execfile(hou.expandString("$POLYFACTORY/devScripts/test_usd_setup.py"))
```

### Debugging HDAs
Use `inspect_*.py` scripts in `devScripts/` to debug:
- Render nodes: `inspect_render_nodes.py`
- USD stages: `debug_usd_stage.py`
- LOP networks: `list_lop_nodes.py`

### Inspection/Analysis Utilities
**Reference:** Read `d:\copilot\docs\polyfactory\ref_hda_cop_vop.md` when building HDAs, COPs, or VOPs.
`devScripts/` contains inspection scripts for analyzing Houdini nodes. Use `temp_inspect_hda.py` pattern for HDA params, `list_lop_nodes.py`/`list_rop_nodes.py` for node type discovery.

### HDA Development Workflow
**Reference:** Read `d:\copilot\docs\polyfactory\ref_hda_cop_vop.md` for HDA creation patterns, COP development, and VOP HDA builds.
Every HDA in `otls/` must have a `devScripts/create_pf_<name>_hda.py` that recreates it. The `.hda` is a build artifact; the devScript is source of truth.

---

## When You're Stuck
1. Verify `polyfactory.json` environment variables are correct
2. Check Houdini console for Python errors
3. Use `os.environ` inspection in Python Shell to debug paths
4. Review existing HDAs in `otls/` for similar functionality
5. Test scripts in `devScripts/` folder for environment verification
6. Ensure Houdini version matches package requirements (21.0+)

## graphify

Before answering architecture or codebase questions, read `graphify-out/GRAPH_REPORT.md` if it exists.
If `graphify-out/wiki/index.md` exists, navigate it for deep questions.
Type `/graphify` in Copilot Chat to build or update the knowledge graph.
Polyfactory uses the shared Graphify environment at `F:\projects\graphify\.venv`.
This checkout uses `.githooks/pre-commit` to rebuild Graphify and stage `graphify-out/GRAPH_REPORT.md`, `graphify-out/graph.json`, and `graphify-out/graph.html` on commit. Fresh clones need `git config core.hooksPath .githooks`.

## Package Maintenance
- Keep `backup/` folder for autosaves but don't commit to version control
- Test environment variable resolution after editing `polyfactory.json`
- Maintain backward compatibility for HDAs when possible
- Document any external dependencies (LDraw, USD, etc.)
