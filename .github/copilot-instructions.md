# Polyfactory - AI Coding Agent Instructions

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

### Developing HDAs
HDAs live in `polyfactory/otls/`. Naming convention: `pf_<descriptive_name>.hda`

Examples: `pf_advanced_tube.hda`, `pf_kitbash.hda`, `pf_axis_gizmo.hda`

When creating new HDAs:
1. Use `pf_` prefix consistently
2. Store in `otls/` directory
3. Reference `$POLYFACTORY` in file paths within HDA
4. Test with environment variable resolution

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
Custom UI panels in `polyfactory/python_panels/polyfactory.pypanel` (XML format).

Uses **PySide6** for Qt widgets (Houdini 21+):
```python
from PySide6 import QtWidgets

def createInterface():
    widget = QtWidgets.QWidget()
    # Build UI
    return widget  # Must return top-level widget
```

**Important**: If you see `PySide2` imports in legacy code, migrate to `PySide6`. The API is largely compatible but some signal/slot syntax changed.

### HDA Widget Library
Unified widget system for HDA Python Panel UIs with automatic parameter binding:

```python
from polyfactory.widgets import BindingManager

def createInterface():
    node = kwargs['node']
    manager = BindingManager(node)
    
    # Widgets auto-sync with parameters
    scale = manager.create_float("scale", range=(0.1, 10.0))
    enabled = manager.create_toggle("enabled", label="Enable")
    mode = manager.create_menu("mode", label="Mode")
    
    return manager.build_layout()
```

Features:
- Bidirectional data binding (UI ↔ parameters)
- Houdini-styled widgets (matches native UI)
- Reduced boilerplate for HDA UIs
- Auto-polling for external parameter changes

See `devScripts/hda_ui_example.py` for complete example.
Module: `polyfactory/scripts/python/polyfactory/widgets/`

### PyOneDark UI Framework

**Modern UI Styling for All Tools**

Polyfactory uses the PyOneDark UI framework (based on PyOneDark Qt Widgets by Wanderson M. Pimenta) for consistent, polished tool interfaces across Houdini panels and standalone applications.

**Location:** `polyfactory/scripts/python/polyfactory/ui_framework/`

**Color Palette (OneDark Theme):**
```python
# Primary Colors
BLUE_PRIMARY   = "#61afef"  # Main accent, buttons, highlights
BLUE_HOVER     = "#6c99f4"  # Hover states
BLUE_PRESSED   = "#3f6fd1"  # Pressed/active states

# Backgrounds
BG_DARKEST     = "#1e1e1e"  # Main dialog/window background
BG_DARK        = "#252525"  # Group boxes, panels
BG_MEDIUM      = "#2c2c2c"  # Input fields, thumbnails
BG_LIGHT       = "#3a3a3a"  # Borders, separators

# Text Colors
TEXT_PRIMARY   = "#e0e0e0"  # Main text, input text
TEXT_SECONDARY = "#abb2bf"  # Labels, descriptions
TEXT_DISABLED  = "#4f5b6e"  # Disabled elements
TEXT_ACCENT    = "#dce1ec"  # Highlighted text, titles

# Utility Colors
RED            = "#ff5555"  # Errors, warnings
GREEN          = "#00ff7f"  # Success states
YELLOW         = "#f1fa8c"  # Caution
```

**Usage in Custom UIs:**

```python
from polyfactory.ui_framework.widgets.py_push_button import PyPushButton
from polyfactory.ui_framework.widgets.py_line_edit import PyLineEdit

# Styled button with blue accent
export_btn = PyPushButton(
    text="Export Asset",
    radius=8,
    color="#61afef",
    bg_color="#2c2c2c",
    bg_color_hover="#3a5f7d",
    bg_color_pressed="#4a6f8d"
)

# Styled line edit
name_edit = PyLineEdit()
name_edit.setPlaceholderText("Enter name...")
```

**Standard Widget Styling (for non-framework widgets):**

Apply consistent OneDark theme to standard Qt widgets:

```python
# Dialogs
self.setStyleSheet("""
    QDialog {
        background-color: #1e1e1e;
        color: #e0e0e0;
    }
""")

# Input fields
self.input.setStyleSheet("""
    QLineEdit {
        background-color: #2c2c2c;
        border: 1px solid #3a3a3a;
        border-radius: 4px;
        padding: 6px;
        color: #e0e0e0;
    }
    QLineEdit:focus {
        border: 1px solid #61afef;
    }
""")

# Hover outlines (for thumbnails, cards)
def paintEvent(self, event):
    if self.is_hovered:
        painter = QtGui.QPainter(self)
        pen = QtGui.QPen(QtGui.QColor("#61afef"), 2)
        painter.setPen(pen)
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1), 6, 6)
```

**Design Guidelines:**
- **Consistency:** All Polyfactory tools should use the OneDark color scheme
- **Blue accents:** Primary actions and focus states use `#61afef`
- **Dark backgrounds:** Main windows use `#1e1e1e`, panels use `#252525`
- **Rounded corners:** 4-8px radius for modern look
- **Spacing:** 8-16px margins, 8-12px spacing between elements
- **Hover feedback:** Always provide visual feedback (blue outline, lighter background)

**Attribution:**
Original PyOneDark framework by Wanderson M. Pimenta (MIT License).
See `ui_framework/README.md` for full attribution.

### Animated Hover Outline (Standard Widget Enhancement)

**HoverOutlineMixin** provides animated blue outline on hover for any widget.

**Location:** `polyfactory/scripts/python/polyfactory/widgets/hover_outline.py`

**Features:**
- Smooth fade-in/fade-out animation (150ms by default)
- PyOneDark blue accent color (#61afef)
- Customizable color, width, radius, duration
- Works with any QWidget subclass

**Usage:**

```python
from polyfactory.widgets.hover_outline import HoverOutlineMixin

class MyWidget(HoverOutlineMixin, QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Setup animated hover outline (call in __init__)
        self.setup_hover_outline(
            color="#61afef",      # Outline color
            width=2,              # Pen width
            radius=6,             # Corner radius
            fade_duration=150,    # Animation duration (ms)
            inset=1              # Inset from edge
        )
        
        # Your widget setup...
    
    def paintEvent(self, event):
        super().paintEvent(event)
        
        # Paint hover outline with animation
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.paint_hover_outline(painter)  # Mixin handles opacity
```

**How It Works:**
- Uses `QPropertyAnimation` on `hover_outline_opacity` property (0.0 to 1.0)
- `enterEvent()` fades in, `leaveEvent()` fades out
- `paint_hover_outline()` applies alpha channel to outline color
- Animation triggers `update()` to repaint during transition

**Example (Asset Thumbnail):**
```python
class AssetThumbnailWidget(HoverOutlineMixin, QtWidgets.QWidget):
    def __init__(self, asset_data, size=150, parent=None):
        super().__init__(parent)
        self.setup_hover_outline(color="#61afef", width=2, radius=6, fade_duration=150)
        # ... widget setup
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.paint_hover_outline(painter)  # Animated outline
```

**Design Philosophy:**
- Default widget enhancement for all Polyfactory tools
- Consistent hover feedback across UI
- Smooth, polished user experience
- Minimal boilerplate (just 2 lines to enable)

### Enhanced Widget System - Advanced Patterns

**Architecture: Inherit from Houdini Native Widgets**

Build custom widgets by inheriting from Houdini's native Qt widgets rather than building from scratch:
- `hou.qt.InputField` - Numeric inputs with built-in ladder dragging
- `hou.qt.ColorField` - Color picker with alpha support
- Inherit and enhance with polish features (hover effects, expression coloring, etc.)

**Key Components:**

1. **EnhancedLabel** - Shared polish features for all widgets
   - Hover effects: Lighter background (70,70,70), black outline
   - Ctrl+MMB on label: Reset parameter to default
   - LMB on label: Custom action (e.g., toggle slider visibility)
   - Alt+LMB: Keyframe placeholder
   - Emits signals: `resetRequested`, `actionRequested`

2. **EnhancedInputField** - Inherits from `hou.qt.InputField`
   - Finds internal widgets: `findChild(QtWidgets.QLineEdit)` for accessing internals
   - Event filter on label for non-intrusive behavior modification
   - Expression color feedback via stylesheet (not QPalette)

**Expression Handling - Critical Pattern:**

```python
def _update_expression_style(self):
    """Update visual feedback for expression state."""
    if not self.parm:
        return
    
    has_expr = parm_utils.has_expression(self.parm)
    
    if has_expr:
        lang = parm_utils.get_expression_language(self.parm).lower()
        # Green (60,100,60) for hscript, Purple (90,60,110) for python
        color = (90, 60, 110) if lang == "python" else (60, 100, 60)
        self.input_field.set_expression_color(QtGui.QColor(*color))
        
        # CRITICAL: Use event filter to block input, NOT setEnabled()
        # setEnabled(False) prevents visual updates when expression value changes
        self.input_field.installEventFilter(self._block_input_filter)
    else:
        self.input_field.removeEventFilter(self._block_input_filter)
        self.input_field.set_expression_color(QtGui.QColor(58, 58, 58))
```

**Why Event Filters Over setEnabled():**
- `setEnabled(False)` blocks ALL updates including visual refresh when parameter value changes
- Event filter blocks user input while allowing widget to update visually
- Expression-driven parameters can animate/update while remaining non-editable

**Parameter Clipboard Integration:**

Use Houdini's native parameter clipboard API for seamless copy/paste between Qt and native UI:

```python
# Copy parameter
def copy_parameter(parm: hou.Parm):
    parm.copyToParmClipboard()  # Native Houdini clipboard

# Paste relative reference
def paste_relative_reference(target_parm: hou.Parm):
    clipboard = hou.parmClipboardContents()  # Returns list of dicts
    if not clipboard:
        return
    
    source_info = clipboard[0]  # Dict with 'path', 'value', 'expression', 'expressionLanguage'
    source_parm = hou.parm(source_info['path'])
    
    # Create relative reference
    ref_expr = target_parm.node().relativePathTo(source_parm.node())
    expr = f'ch("{ref_expr}/{source_parm.name()}")'
    target_parm.setExpression(expr, language=hou.exprLanguage.Hscript)
```

**Multi-Component Parameters (Color, Vector):**

```python
# WRONG - single component
parm = node.parm("color")  # Only gets 'colorr', not the tuple

# CORRECT - full tuple
parm_tuple = node.parmTuple("color")  # Gets all components (r,g,b,a)
for component in parm_tuple:
    component.set(value)

# ColorSquare look requires 4 components with RGBA naming
parm_template = hou.FloatParmTemplate(
    "color", "Color", 4,
    naming_scheme=hou.parmNamingScheme.RGBA,
    look=hou.parmLook.ColorSquare
)
```

**Qt Color Integration:**

```python
# Houdini's ColorField expects QtGui.QColor, NOT hou.Color
qcolor = QtGui.QColor.fromRgbF(r, g, b)
qcolor.setAlphaF(a)
color_field.setColor(qcolor)  # Works

# WRONG - causes AttributeError
hou_color = hou.Color((r, g, b))
color_field.setColor(hou_color)  # Error: 'Color' object has no attribute 'redF'
```

**Widget Polling Pattern:**

All widgets inherit from `ParmWidget` base class that handles automatic parameter polling:

```python
class ParmWidget(QtWidgets.QWidget):
    def __init__(self, parm: hou.Parm):
        super().__init__()
        self.parm = parm
        self._updating_from_parm = False  # Prevent feedback loops
        
    def update_from_parm(self):
        """Called by BindingManager polling - update widget from parameter."""
        if not self.parm:
            return
        
        self._updating_from_parm = True  # Block widget → parm updates
        current_value = self._get_parm_value()
        self._update_widget_value(current_value)
        self._updating_from_parm = False
        
    def _on_value_changed(self, value):
        """Widget changed - update parameter."""
        if not self._updating_from_parm:  # Ignore if updating FROM parm
            self.parm.set(value)
```

**Finding Internal Widgets:**

When inheriting from Houdini's native widgets, access internal components:

```python
class EnhancedInputField(hou.qt.InputField):
    def __init__(self):
        super().__init__()
        
        # Find internal widgets (no recursive flag needed usually)
        self._line_edit = self.findChild(QtWidgets.QLineEdit)
        self._label = self.findChild(QtWidgets.QLabel)
        
        # Apply styles/filters to internal widgets
        if self._line_edit:
            self._line_edit.setStyleSheet("background-color: rgb(60,100,60);")
        
        if self._label:
            self._label.installEventFilter(self)  # Intercept label events
```

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

**Critical Export Workflow (glTF Connection Points):**

Houdini's glTF exporter has a bug - it **loses null node names**. Since Galaxia uses nulls for module connection points, we post-process GLB files with Python:

```python
# In Houdini Python Shell or shelf tool
from polyfactory.gltf_export import export_module_with_connection_points

# Export module with connection points preserved
node = hou.node("/obj/chassis_basic/OUT")
export_module_with_connection_points(node, "D:/galaxia/assets/chassis_basic.glb")
```

The script:
1. Exports to GLB via Houdini ROP (loses null names)
2. Extracts connection point data from Houdini scene
3. Post-processes GLB with `pygltflib` to restore names
4. Saves corrected GLB

See `polyfactory/scripts/python/polyfactory/gltf_export.py` for implementation.

**Export Guidelines:**
- Use glTF/GLB for runtime-loaded modules (best Godot performance)
- Use USD for editor-imported assets (preserves more data)
- Connection point nulls must match pattern `*connection*`
- Follow Galaxia's module specifications (see Galaxia's copilot-instructions.md)
- Use consistent scale (1 unit = 1 meter for Godot compatibility)

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
Package targets Houdini 21.0+ (workspace includes 21.0.603 installation reference).

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
**The Houdini installation is loaded in the workspace** (`C:\Program Files\Side Effects Software\Houdini 21.0.603`) for reference when documentation is unclear.

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
`devScripts/` contains inspection scripts for analyzing Houdini files and nodes:

**HDA Inspection:**
- `temp_inspect_hda.py` - Loads HDA, creates node, prints all parameters with types and defaults
  - Useful pattern: Load HDA → Create node → Iterate `node.parms()` → Print parmTemplate info

**Node Type Discovery:**
- `list_lop_nodes.py` - Lists LOP node types by keyword (render, light, camera, material)
- `list_rop_nodes.py` - Lists ROP (render output) node types
- Pattern: `hou.lopNodeTypeCategory().nodeTypes()` to enumerate all available nodes

**Parameter/Network Inspection:**
- `inspect_render_nodes.py` - Creates temporary nodes to inspect renderproduct/rendersettings parameters
- `inspect_usdrender.py` - Inspects USD render node setup
- Pattern: Create temp node → Print parameters → Destroy cleanup

**Database/Environment:**
- `check_database.py` - Validates asset database structure
- `test_usd_setup.py` - Verifies USD environment variables and export setup

**Common inspection patterns:**
```python
# List all parameters on a node
for parm in node.parms():
    pt = parm.parmTemplate()
    print(f"{parm.name()} | {pt.type().name()} | {pt.label()}")

# Find node types by keyword
category = hou.sopNodeTypeCategory()  # or lopNodeTypeCategory(), ropNodeTypeCategory()
for node_type in category.nodeTypes().values():
    if 'keyword' in node_type.name().lower():
        print(f"{node_type.name()} - {node_type.description()}")

# Get parameter defaults
if hasattr(pt, 'defaultValue'):
    default = pt.defaultValue()
elif hasattr(pt, 'defaultExpression'):
    default = pt.defaultExpression()
```

These scripts serve as templates for creating new inspection utilities when exploring unfamiliar Houdini APIs.

### HDA Development Workflow
1. Create/edit HDA in Houdini (unlocked)
2. Test thoroughly with various inputs
3. Lock HDA and save to `otls/`
4. Document parameters and usage in HDA help
5. Add to shelf if frequently used

## When You're Stuck
1. Verify `polyfactory.json` environment variables are correct
2. Check Houdini console for Python errors
3. Use `os.environ` inspection in Python Shell to debug paths
4. Review existing HDAs in `otls/` for similar functionality
5. Test scripts in `devScripts/` folder for environment verification
6. Ensure Houdini version matches package requirements (21.0+)

## Package Maintenance
- Keep `backup/` folder for autosaves but don't commit to version control
- Test environment variable resolution after editing `polyfactory.json`
- Maintain backward compatibility for HDAs when possible
- Document any external dependencies (LDraw, USD, etc.)
