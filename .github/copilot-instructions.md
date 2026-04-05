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

### Temporary / One-Off Scripts
**All temporary scripts created by the AI agent — across any workspace (Galaxia, Polyfactory, GalaxiaWork, Graphite) — must be saved to:**
```
F:\projects\galaxiaWork\copilot\
```
This includes: patch scripts, data migration helpers, one-off exporters, inspection scripts, debug utilities. Never save throwaway scripts inside the project they operate on.

### Houdini Bridge - AI Agent Integration

**Location:** `polyfactory/scripts/python/polyfactory/houdini_bridge/`

WebSocket server that enables AI agents to control Houdini programmatically:
- **server.py** - Synchronous WebSocket server (port 9876)
- **commands.py** - Command executor (create nodes, set parameters, execute Python)
- **message_handler.py** - MessagePack protocol handler
- **approval.py** - Safety system (defaults to DISABLED for AI agents)

**Starting the Server (in Houdini Python Shell):**
```python
from polyfactory.houdini_bridge import BridgeServer
server = BridgeServer()
server.start()
```

**AI Agent Interface (Token-Efficient CLI):**
Located in `devScripts/houdiniBridge/houdini_cmd.py` (local dev tool, not in git):

```bash
# Single operations (~200-400 tokens)
python devScripts/houdiniBridge/houdini_cmd.py create_node geo my_geo
python devScripts/houdiniBridge/houdini_cmd.py delete_node /obj/geo1
python devScripts/houdiniBridge/houdini_cmd.py get_selection

# Batch operations (very efficient - ~350 tokens for multiple nodes)
python devScripts/houdiniBridge/houdini_cmd.py batch_create /obj geo:terrain null:cam merge:final

# Query scene structure
python devScripts/houdiniBridge/houdini_cmd.py get_tree /obj
python devScripts/houdiniBridge/houdini_cmd.py get_node_info /obj/geo1
python devScripts/houdiniBridge/houdini_cmd.py get_parms /obj/geo1

# Execute Python code (stdout captured)
python devScripts/houdiniBridge/houdini_cmd.py exec "import hou; print(hou.node('/obj').children())"
```

**Key Features:**
- Direct WebSocket communication (bypasses VS Code API limitations)
- MessagePack binary protocol for efficiency
- Batch operations for multiple nodes in single command
- Stdout capture - Python `print()` statements return to client
- Approval system disabled by default for AI trust

**Token Efficiency:**
- Single operation: ~200-400 tokens (vs 800-1500 with alternatives)
- Batch operation: ~350 tokens for multiple nodes
- Complex Python execution: ~300-600 tokens

**VS Code Extension (Future):**
Full extension exists in `devScripts/houdiniBridge/` (separate git repo) with chat participant and Language Model tools, waiting for Copilot API to expose tools to agents. See `devScripts/houdiniBridge/IMPLEMENTATION_NOTES.md` for details.

### Developing HDAs
HDAs live in `polyfactory/otls/`. Naming convention: `pf_<descriptive_name>.hda`

Examples: `pf_advanced_tube.hda`, `pf_kitbash.hda`, `pf_axis_gizmo.hda`

When creating new HDAs:
1. Use `pf_` prefix consistently
2. Store in `otls/` directory
3. Reference `$POLYFACTORY` in file paths within HDA
4. Test with environment variable resolution

### Kitbash Workflow (pf_kitbash HDA)

**Interactive viewport-based kitbashing system:**

**HDA Parameters:**
- `library` (multiparm) - User-defined library of meshes with `lMesh#` (string) file paths
- `currentMesh` (string) - Path to currently selected mesh for placement
- `currentActive` (toggle) - True when mesh selected, false when idle
- `num_meshes` (multiparm) - Placed instances with `file#`, `t#`, `r#`, `scale#`

**Workflow:**
1. User populates `library` multiparm with USD/geometry file paths
2. HDA displays all library meshes in viewport (with `mesh_index` attribute for picking)
3. User presses **Enter** in viewport → activates kitbash placement state
4. User clicks library mesh in viewport → state sets `currentMesh` parameter and `currentActive=true`
5. HDA updates to show preview of selected mesh following cursor
6. User clicks to place → state adds entry to `num_meshes` multiparm, clears `currentMesh`, sets `currentActive=false`
7. User can press ESC to cancel selection or Enter again to exit state

**Python State:** `polyfactory/scripts/python/polyfactory/asset_library/kitbash_placement_state.py`
- State name: `polyfactory.kitbash_placement`
- Registered in `polyfactory/scripts/123.py` on Houdini startup
- Uses raycasting to detect clicks on library meshes (via `mesh_index` primitive attribute)
- Handles placement by setting transform parameters in multiparm
- HDA handles all geometry loading and preview rendering (state doesn't load USD files)

**Python Panel UI:** `polyfactory/scripts/python/polyfactory/asset_library/kitbash_ui.py`
- Asset browser for browsing available meshes
- "Add to Library" button to populate library multiparm from browser
- List of placed assets with transform controls
- Instructions: "Press Enter in viewport to activate kitbash mode"
- No double-click integration - browser is kept generic for reuse

**Key Design Principle:** State is viewport-interaction only. HDA handles geometry, preview, and display. This keeps the state simple and performant.

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

def onCreateInterface():
    widget = QtWidgets.QWidget()
    # Build UI
    return widget  # Must return top-level widget
```

**Important**: If you see `PySide2` imports in legacy code, migrate to `PySide6`. The API is largely compatible but some signal/slot syntax changed.

**Python Panel Lifecycle Functions:**

Python panels require specific callback functions:
- `onCreateInterface()` - Creates and returns the root widget (NOT `createInterface()`)
- `onActivateInterface()` - Called when pane becomes active
- `onDeactivateInterface()` - Called when pane becomes inactive
- `onDestroyInterface()` - Called when interface is destroyed
- `onNodePathChanged(node)` - Called when node path changes

**Automatic Node Binding with `<showInParametersPane>`:**

To automatically show a Python Panel for specific node types, use the `<showInParametersPane>` tag with the correct optype syntax:

```xml
<interface name="my_ui" label="My Tool" ...>
  <script><![CDATA[
    # Python code with onCreateInterface(), etc.
  ]]></script>
  <showInParametersPane optype="namespace::context/nodename::version"/>
</interface>
```

**Critical optype Syntax:**
- Format: `namespace::context/nodename::version`
- Use `*` wildcard for any part
- Example: `pf::Sop/pf_kitbash::*` matches all versions of pf_kitbash SOP
- Example: `*::Sop/mynode::*` matches mynode in any namespace
- Get exact node type: `node.type().nameWithCategory()` (e.g., `Sop pf::pf_kitbash::1.0`)
- Context is `Sop`, `Lop`, `Object`, `Cop2`, etc.

**Note:** The `node` variable is automatically available in the script scope (passed by Houdini), so you don't need to extract it from kwargs.

**Font Scaling for Houdini UI:**

**CRITICAL:** Always use Houdini's UI scaling for all custom Qt interfaces. Never hardcode font sizes.

Module: `polyfactory/scripts/python/polyfactory/ui_utils.py`

```python
from polyfactory.ui_utils import get_scaled_font_size, get_font_stylesheet

# Get scaled font size (respects hou.ui.globalScaleFactor())
base_font_size = get_scaled_font_size(11)  # Default Houdini base size

# Use in stylesheets (f-strings require doubled braces)
widget.setStyleSheet(f"""
    QWidget {{
        font-size: {base_font_size}px;
        color: #e0e0e0;
    }}
""")

# Or use helper function
label.setStyleSheet(get_font_stylesheet(size=11, weight="bold", color="#61afef"))
```

**Why this matters:**
- Houdini's UI scale can be changed by users (View → Display Options → Global UI Size)
- Custom panels with hardcoded font sizes will look too small or too large
- `hou.ui.globalScaleFactor()` returns the current scale multiplier
- All Polyfactory UIs must respect this setting for consistency

**Guidelines:**
- Use `get_scaled_font_size(11)` for default text (Houdini's base size)
- Use `get_scaled_font_size(13)` for section headers
- Use `get_scaled_font_size(9)` for small labels/captions
- Always double curly braces `{{` `}}` in f-string stylesheets
- Apply to all Qt widgets: QLabel, QLineEdit, QComboBox, QGroupBox, etc.

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

**Creating Hover-Enabled Wrapper Classes:**

When PyOneDark framework widgets need hover effects, create thin wrapper classes:

```python
from polyfactory.widgets.hover_outline import HoverOutlineMixin

class HoverComboBox(HoverOutlineMixin, QtWidgets.QComboBox):
    """QComboBox with animated hover outline"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_hover_outline(color="#61afef", width=1, radius=4, fade_duration=150)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.paint_hover_outline(painter)
```

**Optional Dependency Pattern:**

For framework widgets that may be used outside Polyfactory, use try/except import:

```python
try:
    from polyfactory.widgets.hover_outline import HoverOutlineMixin
    _has_hover_mixin = True
except ImportError:
    _has_hover_mixin = False
    class HoverOutlineMixin:
        """Fallback if hover_outline not available"""
        pass

class PyLineEdit(HoverOutlineMixin, QLineEdit):
    def __init__(self, ...):
        super().__init__()
        # ... setup code
        if _has_hover_mixin:
            self.setup_hover_outline(...)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        if _has_hover_mixin and hasattr(self, 'paint_hover_outline'):
            painter = QPainter(self)
            self.paint_hover_outline(painter)
```

### FlowLayout - Responsive Widget Wrapping

**Location:** `polyfactory/widgets/tag_input.py` (FlowLayout class)

Custom QLayout subclass that wraps widgets like text flow. Used for tag chips and asset thumbnails.

**Features:**
- Automatic wrapping to multiple lines based on width
- Dynamic height calculation (implements `hasHeightForWidth()`)
- Configurable horizontal/vertical spacing
- Works with any QWidget

**Usage:**

```python
from polyfactory.widgets.tag_input import FlowLayout

container = QtWidgets.QWidget()
layout = FlowLayout(container)
layout.spacing_x = 8
layout.spacing_y = 8

# Add widgets - they wrap automatically
for item in items:
    widget = MyWidget(item)
    layout.addWidget(widget)

# Force layout recalculation after size changes
container.updateGeometry()
```

**When to Use:**
- Tag chips that need to wrap in narrow panels
- Asset thumbnails with variable sizes
- Any grid that should reflow responsively
- Alternative to QGridLayout with fixed columns

**Important:**
- Does NOT support `addStretch()` - add fixed widgets instead
- Layout recalculates on resize automatically
- Use `updateGeometry()` to force immediate recalculation

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

**Full spec:** `d:\godotGames\galaxia\documentation\module_set_spec.md` — read this before asking any question about module naming, connection points, grid sizes, or class separation. It is the authoritative source.

---

#### Galaxia Module Naming Convention

```
{type}_{SIZE}_{HEIGHT}_{CLASS}_{PATTERN}_{TIER}[_V{n}]
```

| Segment | Examples | Notes |
|---------|----------|-------|
| `type` | `chassis`, `reactorThorium`, `cargo_solid`, `Hull_Mid` | Module function — **free-form**: any mix of letters, digits and underscores. No casing rule. |
| `SIZE` | `S`, `M`, `L` | Short / Medium / Long (1/2/3 grid units) — uppercase |
| `HEIGHT` | `H1`, `H2` | 1 deck (0.25m) / 2 decks (0.50m) — uppercase |
| `CLASS` | `D`, `G`, `T`, `L` | Drake / Goliath / Titan / Leviathan — uppercase |
| `PATTERN` | `SCI`, `IND`, `LOG`, `LIV` | Scientific / Industrial / Logistic / Living — uppercase |
| `TIER` | `T2`, `T3`, `T4` | Uppercase |
| `VARIANT` | `V1`, `V2`, `V3` | **Optional.** Only present when 2+ designs exist for the same functional slot. All designs get numbered starting at V1. Absent = single design. |

**Pattern modules:** `chassis_S_H1_D_SCI_T2`, `cargo_solid_M_H1_D_LOG_T2`  
**Pattern modules with variants:** `chassis_S_H1_D_SCI_T2_V1`, `hull_mid_M_H2_D_IND_T2_V2`  
**Utility modules** (no pattern field): `radiator_S_H1_D_T2`, `sensors_S_H1_D_T2`

**Variant rule:** Each chassis/hull design variant is a fully independent module with its own stats, mesh, and CP layout. `_V{n}` is NOT a skin — it is a separate entry in the data registry.

#### Houdini Scene Structure

```
/obj/{CLASS_TIER}/                                     <- class/tier OBJ subnet (e.g. DRAKE_T2)
    geometry/                                          <- single modeling subnet
        OUT_{module_id}                                <- final geo SOP per module
    {module_id}/                                       <- module OBJ subnet
        {module_id}/                                   <- inner geo subnet (SOP context)
            object_merge1                              <- pulls geo from modeling subnet
            bbox_cp                                    <- bounding box mesh (faces = CPs)
            rop_gltf1                                  <- GLB exporter (pre-configured)
        CP_D1, CP_D2...                                <- null OBJs (generated by tool)
        CP_U1, CP_U2...                                <- utility null OBJs
```

#### Houdini Node Naming

The SOP output node inside the inner geo subnet is named `OUT_{module_id}`.

Examples:
- `OUT_chassis_S_H1_D_SCI_T2`
- `OUT_cargo_solid_M_H1_D_LOG_T2`

#### Connection Point Naming (CP_ Nulls)

```
CP_D{n}   — Default connection point  (modules connect structurally here)
CP_U{n}   — Utility connection point  (solar, radiator, sensors, mining)
```

- `CP_D` connects only to `CP_D` — hard rule enforced by ship designer
- `CP_U` connects only to `CP_U` — hard rule enforced by ship designer
- Numbered from 1: `CP_D1`, `CP_D2`... `CP_U1`, `CP_U2`...
- All CPs point outward along **+Z axis** from the surface they sit on
- Godot reads them via `name.begins_with("CP_")`; the existing exporter matches `CP_*`
- CP type (default vs utility) is stored as an integer prim attribute `cp_type` on the
  bounding box mesh face (`bbox_cp` SOP): `0` = default, `1` = utility
- `bbox_cp` lives inside each module's inner geo subnet alongside `object_merge1` and `rop_gltf1`

#### Grid Specification (Drake Class)
- Grid unit: **0.25 m** (smallest snap increment)
- `h1` = 0.25 m tall (1 deck), `h2` = 0.50 m tall (2 decks)
- Drake base unit: **0.5 m** (2 grid units)
- All module dimensions are multiples of 0.25 m

---

**Critical Export Workflow (glTF Connection Points):**

Houdini's glTF exporter has a bug - it **loses null node names**. Since Galaxia uses nulls for module connection points, we post-process GLB files with Python:

```python
# In Houdini Python Shell or shelf tool
from polyfactory.gltf_export import export_module_with_connection_points

# Export module with connection points preserved
# node = the OUT_{module_id} SOP inside the module's inner geo subnet
node = hou.node("/obj/DRAKE_T2/chassis_S_H1_D_SCI_T2/chassis_S_H1_D_SCI_T2/OUT_chassis_S_H1_D_SCI_T2")
export_module_with_connection_points(node, "D:/galaxia/mods/core/assets/modules/chassis_S_H1_D_SCI_T2.glb")
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
- Connection point nulls match pattern `CP_*`
- Output path: `d:\godotGames\galaxia\mods\core\assets\modules\{class_tier}\{module_id}.glb`
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

**HDA files can be created entirely from the command line using hython — no interactive Houdini session required.**

**Houdini installation paths:**
- Houdini 22 (current): `C:\Program Files\Side Effects Software\Houdini 22.0.240\`
- hython: `C:\Program Files\Side Effects Software\Houdini 22.0.240\bin\hython.exe`
- Houdini 21 (legacy): `C:\Program Files\Side Effects Software\Houdini 21.0.631\`

**Creating an HDA from a devScript (preferred workflow):**
```powershell
# Set POLYFACTORY so the script can resolve paths
$env:POLYFACTORY = "f:/projects/polyfactory/polyfactory"
$env:PF_ASSET_LIBRARY = "f:/projects/polyfactory/polyfactory/library/assets"
$env:PF_ASSET_DB = "f:/projects/polyfactory/polyfactory/library/assets/asset_library.db"
& "C:\Program Files\Side Effects Software\Houdini 22.0.240\bin\hython.exe" `
    "f:/projects/polyfactory/devScripts/create_pf_my_node_hda.py"
```

**When to use hython vs interactive Houdini:**
- Use hython for: creating/rebuilding HDA files from devScripts, batch operations, CI
- Use interactive Houdini for: iterative parameter tweaking, visual testing, node wiring inspection

**devScript convention:** Every HDA in `otls/` must have a corresponding `devScripts/create_pf_<name>_hda.py` that fully recreates it from scratch. This is the source of truth — the `.hda` file is a build artifact.

**Standard devScript structure:**
```python
# 1. Remove existing HDA file
# 2. Build a temporary geo node + subnet in /obj for construction context
# 3. Build inner network (SOPs/LOPs/COPs)
# 4. Wrap with createDigitalAsset(name='pf::<name>::1.0', ...)
# 5. allowEditingOfContents() then re-wire (createDigitalAsset resets connections)
# 6. Build ParmTemplateGroup and setParmTemplateGroup()
# 7. defn.save(HDA_PATH, template_node=hda_node)
# 8. Destroy temp nodes (hda_node.destroy(); build_geo.destroy())
```

1. Create/edit HDA via devScript in `devScripts/create_pf_<name>_hda.py`
2. Run with hython to produce the `.hda` file in `otls/`
3. Test in interactive Houdini (install with `hou.hda.installFile(path)`)
4. Document parameters and usage in HDA help
5. Add to shelf if frequently used

---

## Copernicus COP Development

### Architecture: Copernicus vs COP2

**Copernicus** (Houdini 20.5+, `cop` node context) is architecturally different
from the old **COP2** (`copnet` / `cop2` context):

| Aspect | COP2 (old) | Copernicus (new) |
|---|---|---|
| Output model | One wire = layer stream (multiple named layers) | Each output = separate independent wire/cable |
| HDA outputs | Single connector, layers referenced by name | N connectors, one per output |
| Network container | `img.createNode("copnet", ...)` | `copnet` container works, but subnet node is `cop` category |
| Output node | `outputs` routing node | Single `output` COP: i-th input -> i-th output wire |

**Do NOT** use COP2 "number of layers in stream" thinking when building
Copernicus HDAs. Each named output becomes a distinct wire the user connects
to a downstream node.

---

### Building a Multi-Output Copernicus OpenCL HDA (hython script pattern)

```python
# 1. Create build context
img = hou.node("/img") or hou.node("/").createNode("img", "img")
copnet = img.createNode("copnet", "_build_ctx")

# 2. Create the subnet that will become the HDA
subnet = copnet.createNode("subnet", "_my_node")

# 3. Set the number of output wires BEFORE createDigitalAsset
subnet.parm("outputs").set(N_OUTPUTS)
# Parm names are outputlabelN / outputtypeN  (no underscore)
for i, (name, _ocl_t, subnet_type_idx) in enumerate(OUTPUTS, start=1):
    subnet.parm("outputlabel" + str(i)).set(name)
    subnet.parm("outputtype"  + str(i)).set(subnet_type_idx)

# 4. Create opencl node, configure Signature outputs, add inner wiring
ocl = subnet.createNode("opencl", "my_kernel")
# ... configure ocl ...

# 5. Find/create the single inner output node, wire all opencl outputs
#    The auto-created output node is named "outputs" with type "output"
out_node = next((n for n in subnet.children()
                 if n.type().name() == "output" and n is not ocl), None)
if out_node is None:
    out_node = subnet.createNode("output", "OUT")
for idx in range(N_OUTPUTS):
    out_node.setInput(idx, ocl, idx)   # i-th input -> i-th output wire
out_node.setDisplayFlag(True)

# 6. Wrap as HDA
hda_node = subnet.createDigitalAsset(name="my_hda", hda_file_name=path, ...)

# 7. Fix wiring post-wrap (createDigitalAsset inserts a passthrough)
hda_node.allowEditingOfContents()
inner = {n.name(): n for n in hda_node.children()}
inner_out = inner["outputs"]   # auto-created by createDigitalAsset
inner_ocl = inner["my_kernel"]
for slot in range(20):         # clear passthrough
    try: inner_out.setInput(slot, None)
    except Exception: break
for idx in range(N_OUTPUTS):   # re-wire opencl -> output
    inner_out.setInput(idx, inner_ocl, idx)

# 8. Save, capturing live wiring
definition = hda_node.type().definition()
definition.save(path, template_node=hda_node)
```

---

### Copernicus Subnet Output Multiparm Reference

Set output count with `subnet.parm("outputs").set(N)`.

Multiparm entry parm names (note: **no underscore**):
- `outputlabelN` -- display label of wire N (shown when connecting in network)
- `outputtypeN`  -- data type of wire N

Type index values for `outputtypeN` (Copernicus subnet):

| Type | Index |
|------|-------|
| ID | 0 |
| Mono (float) | 1 |
| UV (float2) | 2 |
| RGB (float3) | 3 |
| RGBA (float4) | 4 |
| Geometry | 5 |
| Integer VDB | 6 |
| Float VDB | 7 |
| Vector VDB | 8 |
| Cable | 9 |

**These are different from the opencl Signature tab `outputN_type` indices:**

| Type | opencl `outputN_type` index | subnet `outputtypeN` index |
|------|----------------------------|---------------------------|
| Varying | 0 | -- |
| ID | 1 | 0 |
| Mono | 2 | 1 |
| UV | 3 | 2 |
| RGB | 4 | 3 |
| RGBA | 5 | 4 |

Always track both indices separately in your OUTPUTS definition:
```python
# (wire_name, opencl_signature_type_idx, subnet_outputtype_idx)
OUTPUTS = [
    ("C",      5, 4),   # RGBA
    ("height", 2, 1),   # Mono
    ("N",      4, 3),   # RGB
    ("rough",  2, 1),   # Mono
    ("ao",     2, 1),   # Mono
]
```

---

### Clearing COP Node Inputs

`nInputs()` does NOT exist on COP nodes (AttributeError). To clear all
input connections:

```python
for slot in range(20):
    try:
        node.setInput(slot, None)
    except Exception:
        break  # ran out of valid input slots
```

---

### Diagnosing Unknown Parm Names

When unsure of exact multiparm parameter names, probe them at runtime:

```python
# After setting the count parm
subnet.parm("outputs").set(5)
print([p.name() for p in subnet.parms() if p.name().startswith("output")])
# -> ['outputlabel1', 'outputtype1', 'outputlabel2', 'outputtype2', ...]
```

This pattern is universally useful for any node whose multiparm entry parm
names are unclear from docs.


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
