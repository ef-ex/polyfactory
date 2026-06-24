# Kitbash Placement System - Usage Guide

## Overview

The Kitbash Placement system provides an interactive viewport workflow for placing assets from the asset library into your scene with two placement modes: **Align to Mesh** (surface-aligned) and **Simple Placement** (position-only).

## Architecture

### Components

1. **Viewer State** (`kitbash_placement_state.py`)
   - Interactive viewport placement tool
   - Two modes: align to mesh / simple placement
   - Raycasting for surface detection
   - Transform manipulation (position, rotation, scale)

2. **Viewer Utilities** (`viewer_utils/`)
   - `raycasting.py` - Pure functions for ray-geometry intersection
   - `drawing.py` - Viewport drawing helpers
   - `input_handling.py` - Mouse/keyboard utilities

3. **Asset Browser** (`browser_ui.py`)
   - PyOneDark-styled Qt interface
   - Grid view with thumbnails
   - Search and filtering
   - Double-click to enter placement mode

4. **Kitbash HDA** (`pf_kitbash.hda`)
   - Container node for placed assets
   - Multiparm for asset instances
   - Parameters: file path, transform, enable

## Workflow

### Launching Asset Browser

```python
from polyfactory.asset_library.browser_ui import show_asset_browser
show_asset_browser()
```

Or use shelf tool / hotkey configured in Polyfactory package.

### Placement Workflow

1. **Open Asset Browser**
   - Browse and search asset library
   - View thumbnails and metadata

2. **Double-click Asset**
   - Enters viewport placement state
   - Asset geometry "sticks" to mouse cursor
   - Preview shows where asset will be placed

3. **Position Asset**
   - Move mouse to position
   - Asset follows cursor and snaps to geometry

4. **Adjust Transform**
   - `R` - Rotate 45° around Y axis
   - `S` - Scale up/down (Shift+S for larger increments)
   - `Right-click` - Context menu for mode switching

5. **Place Asset**
   - `Left-click` - Place asset at current position
   - Asset added to kitbash node multiparm
   - Ready to place next instance

6. **Cancel**
   - `ESC` - Exit placement mode

## Placement Modes

### Align to Mesh (Default)

**Behavior:**
- Raycasts to geometry under cursor
- Aligns asset to surface normal
- Rotates asset to match surface orientation
- Y-axis points along surface normal

**Use Cases:**
- Placing details on curved surfaces (ship hulls, terrain)
- Adding greebles to complex geometry
- Surface-mounted equipment or decals

**How It Works:**
```python
# 1. Raycast to find hit point and normal
hit_info = raycasting.get_geometry_under_cursor(ui_event, node)

# 2. Build rotation matrix aligned to normal
align_matrix = raycasting.align_transform_to_normal(hit_info['normal'])

# 3. Extract Euler angles
rotation = raycasting.extract_rotation_from_matrix(align_matrix)
```

### Simple Placement

**Behavior:**
- Raycasts to geometry under cursor
- Uses position (X, Y, Z) only
- Ignores surface normal
- Maintains current rotation

**Use Cases:**
- Placing upright objects (trees, columns, furniture)
- Grid-aligned placement
- When custom rotation is needed

**How It Works:**
```python
# Only use position from raycast
hit_info = raycasting.get_geometry_under_cursor(ui_event, node)
placement_position = hit_info['position']
# Rotation unchanged
```

### Switching Modes

**Via Context Menu:**
1. Right-click in viewport during placement
2. Select mode from radio strip
3. Mode updates immediately

**Programmatically:**
```python
# In state class
self.placement_mode = MODE_ALIGN_TO_MESH  # or MODE_SIMPLE_PLACEMENT
self._update_prompt_message()
```

## Raycasting System

### Core Functions

**`raycast_to_geometry(origin, direction, geometry)`**
- Returns hit info: position, normal, prim_num, uv
- Used for both placement modes

**`raycast_to_ground_plane(origin, direction, height=0.0)`**
- Fallback when no geometry hit
- Projects to XZ plane at specified height

**`get_geometry_under_cursor(ui_event, node)`**
- Convenience wrapper
- Gets ray from UI event
- Searches node inputs for geometry

**`align_transform_to_normal(normal, up_vector=None)`**
- Builds transformation matrix
- Normal becomes local +Y axis
- Returns hou.Matrix4

**`extract_rotation_from_matrix(mat)`**
- Converts matrix to Euler angles
- Returns hou.Vector3 (degrees)

### Geometry Source

The placement state raycasts against **kitbash node inputs**:

```python
# Searches all inputs for geometry
for i in range(node.inputConnectors()[0].size()):
    input_geo = node.inputGeometry(i)
    if input_geo and len(input_geo.prims()) > 0:
        geo = input_geo
        break
```

**Best Practice:** Connect base geometry (terrain, ship hull, etc.) to kitbash node input 0.

## Technical Details

### State Registration

State template is created in `kitbash_placement_state.py`:

```python
def createViewerStateTemplate():
    state_name = "polyfactory.kitbash_placement"
    state_label = "PolyFactory Kitbash Placement"
    state_category = hou.sopNodeTypeCategory()
    
    template = hou.ViewerStateTemplate(state_name, state_label, state_category)
    template.bindFactory(KitbashPlacementState)
    
    # Context menu
    menu = hou.ViewerStateMenu("kitbash_placement_menu", "Kitbash Placement")
    menu.addRadioStrip("placement_mode", "Placement Mode", MODE_ALIGN_TO_MESH)
    menu.addRadioStripItem("placement_mode", "mode_align", "Align to Mesh")
    menu.addRadioStripItem("placement_mode", "mode_simple", "Simple Placement")
    
    template.bindMenu(menu)
    template.bindAsDefault(True)
    
    return template
```

State is automatically registered when Houdini loads the module.

### Asset Data Flow

```
Browser UI (double-click)
    ↓ (JSON serialized)
scene_viewer.enterViewerState("polyfactory.kitbash_placement", 
                             {"asset_data": json.dumps(asset_data)})
    ↓
State onEnter(kwargs)
    ↓ (deserialize)
self.asset_data = json.loads(kwargs['asset_data'])
self.asset_file = asset_data['file_path']
    ↓
Load preview geometry (USD file)
    ↓
Place asset → Add to multiparm
```

### Module Reloading

For rapid development iteration:

```python
from polyfactory.asset_library import reload_modules

# Reload specific subsystem
reload_modules.reload_viewer_utils()  # Just viewer utils
reload_modules.reload_asset_library()  # Asset library + state

# Or reload everything
reload_modules.reload_all()
```

Modules are registered in `reload_modules.py`:
- `polyfactory.viewer_utils.*`
- `polyfactory.asset_library.kitbash_placement_state`

## Extending the System

### Adding New Placement Modes

1. **Define Mode Constant**
```python
MODE_CUSTOM = "custom_placement"
```

2. **Add to State Class**
```python
def onMouseEvent(self, kwargs):
    if self.placement_mode == MODE_CUSTOM:
        # Custom logic here
        pass
```

3. **Add to Context Menu**
```python
menu.addRadioStripItem("placement_mode", "mode_custom", "Custom Mode")
```

4. **Handle Menu Action**
```python
def onMenuAction(self, kwargs):
    if item == "mode_custom":
        self.placement_mode = MODE_CUSTOM
        return True
```

### Adding Viewer Utils Functions

Create new module in `viewer_utils/`:

```python
# polyfactory/viewer_utils/snapping.py
def snap_to_grid(position, grid_size=1.0):
    """Snap position to grid."""
    return hou.Vector3(
        round(position.x() / grid_size) * grid_size,
        round(position.y() / grid_size) * grid_size,
        round(position.z() / grid_size) * grid_size
    )
```

Import in `__init__.py`:
```python
from . import snapping
__all__ = ['raycasting', 'drawing', 'input_handling', 'snapping']
```

Add to reload list:
```python
# reload_modules.py
'polyfactory.viewer_utils.snapping',
```

### Custom Preview Rendering

Override `_update_preview()` in state class:

```python
def _update_preview(self):
    """Update preview drawable with custom visualization."""
    if not self.preview_drawable:
        return
    
    # Create custom geometry
    geo = hou.Geometry()
    
    # Add preview mesh
    # ... build geometry
    
    # Apply transform
    xform = hou.Matrix4()
    xform.setToTranslation(self.placement_position)
    # ... apply rotation and scale
    
    geo.transform(xform)
    
    # Update drawable
    self.preview_drawable.setGeometry(geo)
    self.preview_drawable.show(True)
```

## Troubleshooting

### State Not Activating

**Problem:** `enterViewerState()` fails or state doesn't respond

**Solutions:**
1. Check state is registered: `hou.ui.viewerStates()` should list `"polyfactory.kitbash_placement"`
2. Verify module loaded: `import polyfactory.asset_library.kitbash_placement_state`
3. Check Houdini console for errors
4. Reload modules: `reload_modules.reload_asset_library()`

### Raycasting Not Working

**Problem:** No hit detected even when cursor over geometry

**Solutions:**
1. Ensure kitbash node has geometry connected to input 0
2. Check geometry has primitives: `len(node.inputGeometry(0).prims()) > 0`
3. Verify ray direction is normalized (done automatically in `ui_event.ray()`)
4. Test with simple geometry (box, grid) first

### Alignment Issues

**Problem:** Asset rotates incorrectly or oddly

**Solutions:**
1. Check normal calculation in `raycast_to_geometry()` - may need smoothing
2. Verify asset has correct up axis (should be +Y in Houdini)
3. Test with `MODE_SIMPLE_PLACEMENT` to isolate rotation issue
4. Add custom rotation offset in `align_transform_to_normal()`

### Performance Issues

**Problem:** Viewport lag during placement

**Solutions:**
1. Simplify preview geometry (use proxy mesh)
2. Reduce raycasting frequency (throttle mouse events)
3. Optimize geometry search (cache input geometry)
4. Use viewport display flags (reduce detail level)

## PyOneDark UI Styling

The asset browser uses the PyOneDark theme for consistent Polyfactory look:

```python
# Color scheme (from copilot instructions)
BLUE_PRIMARY   = "#61afef"  # Main accent, buttons, highlights
BG_DARKEST     = "#1e1e1e"  # Main dialog/window background
BG_DARK        = "#252525"  # Group boxes, panels
BG_MEDIUM      = "#2c2c2c"  # Input fields, thumbnails
TEXT_PRIMARY   = "#e0e0e0"  # Main text, input text
```

See [copilot-instructions.md](.github/copilot-instructions.md) for full design guidelines.

## Future Enhancements

### Planned Features

- [ ] **Grid snapping mode** - Snap to regular grid
- [ ] **Multiple asset selection** - Place multiple assets in batch
- [ ] **Paint mode** - Click rapidly to "paint" multiple instances
- [ ] **Scatter mode** - Procedurally scatter assets in area
- [ ] **Collision detection** - Prevent overlapping placement
- [ ] **Undo/redo support** - Proper Houdini undo integration
- [ ] **Preview material** - Show materials during placement
- [ ] **Transform gizmo** - Visual handles for rotation/scale
- [ ] **Hotkey customization** - User-definable keybinds

### Extension Points

- **Custom raycasting** - Implement heightfield or volume raycasting
- **Physics simulation** - Drop assets with gravity
- **Procedural variation** - Random rotation/scale per instance
- **Layer system** - Organize placed assets in groups
- **Asset baking** - Merge placed instances into single mesh

## Resources

- **Houdini Viewer State API**: `$HFS/houdini/help/hom/state.html`
- **PyOneDark Theme**: `polyfactory/ui_framework/`
- **Asset Library System**: `polyfactory/asset_library/`
- **Viewer Utils**: `polyfactory/viewer_utils/`
- **Example States**: `$HFS/houdini/viewer_states/`

## Questions?

Contact Polyfactory development team or check:
- GitHub Issues
- Houdini forums (SideFX)
- Polyfactory documentation folder
