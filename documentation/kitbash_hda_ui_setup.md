# Setting Up the Kitbash HDA UI

## Overview

The `pf_kitbash` HDA has a custom Python Panel UI that displays:
1. **Asset Browser** at the top - Browse and select assets to place
2. **Placed Assets List** below - View and edit all placed asset instances

## HDA Setup Steps

### 1. Create the HDA

The HDA should have these parameters:

**Multiparm: `meshes`** (folder)
- **`file#`** (File) - Path to USD asset file
- **`t#`** (Vector3 Float) - Translation/Position
- **`r#`** (Vector3 Float) - Rotation (degrees)
- **`scale#`** (Float) - Uniform scale

### 2. Add Python Panel Interface

In the HDA Type Properties:

1. Go to **Scripts** tab
2. Select **Python Module** section (or create Python Panel interface)
3. Choose **Python Panel** interface type
4. Copy this code:

```python
from polyfactory.asset_library.kitbash_ui import createInterface

# Houdini will call this automatically
```

**OR** if using inline code:

```python
import hou
from polyfactory.asset_library.kitbash_ui import KitbashNodeUI

def createInterface():
    node = kwargs.get('node')
    if not node:
        from PySide6 import QtWidgets
        widget = QtWidgets.QLabel("No node selected")
        widget.setStyleSheet("background: #1e1e1e; color: #e0e0e0;")
        return widget
    return KitbashNodeUI(node)
```

### 3. Set Interface as Default

In HDA Type Properties:

1. **Interactive** tab
2. Under **Viewer Handle Context**:
   - State: `polyfactory.kitbash_placement`
3. Under **Python Panel**:
   - Check "Show Python Panel"
   - Select your created interface

### 4. Configure Multiparm Structure

The multiparm must follow this exact naming:

```
Multiparm: num_meshes (Integer)
  Folder: mesh# (repeating)
    file# (File Path)
    t# (Vector3 - tx#, ty#, tz#)
    r# (Vector3 - rx#, ry#, rz#)
    scale# (Float)
```

Example parameter template code:

```python
# Multiparm folder
folder_parm = hou.FolderParmTemplate("meshes", "Meshes", 
                                     folder_type=hou.folderType.MultiparmBlock)

# File path
file_parm = hou.StringParmTemplate("file#", "File #", 1,
                                   string_type=hou.stringParmType.FileReference)
folder_parm.addParmTemplate(file_parm)

# Translation
t_parm = hou.FloatParmTemplate("t#", "Translate #", 3,
                               default_value=(0, 0, 0),
                               naming_scheme=hou.parmNamingScheme.XYZW)
folder_parm.addParmTemplate(t_parm)

# Rotation
r_parm = hou.FloatParmTemplate("r#", "Rotate #", 3,
                               default_value=(0, 0, 0),
                               naming_scheme=hou.parmNamingScheme.XYZW)
folder_parm.addParmTemplate(r_parm)

# Scale
scale_parm = hou.FloatParmTemplate("scale#", "Scale #", 1,
                                   default_value=(1.0,),
                                   min=0.001, max=100)
folder_parm.addParmTemplate(scale_parm)

# Add to node type
parm_group = node_type.parmTemplateGroup()
parm_group.append(folder_parm)
node_type.setParmTemplateGroup(parm_group)
```

## UI Features

### Asset Browser Section

- **Grid view** of asset thumbnails
- **Search** by name or tags
- **Category filter** dropdown
- **Thumbnail size** slider
- **Double-click asset** to enter placement mode

### Placed Assets List

Each asset instance shows:
- **Asset name** (from file path)
- **Delete button** (× in top-right)
- **Position controls** (X, Y, Z spinboxes)
- **Rotation controls** (X, Y, Z spinboxes)
- **Scale control** (single float spinbox)

**Features:**
- Live sync with node parameters
- Edit in UI → updates node parameters
- Edit in parameter pane → updates UI (500ms polling)
- Hover effect (blue outline from PyOneDark theme)
- Scrollable list for many assets

## Workflow

### Adding Assets

1. User opens HDA UI (Python Panel)
2. Browses asset library at top
3. Double-clicks asset thumbnail
4. Enters viewport placement mode
5. Clicks to place asset
6. Asset appears in "Placed Assets" list below
7. Repeat to place more assets

### Editing Placed Assets

1. Scroll to asset in list
2. Adjust position/rotation/scale spinboxes
3. Changes immediately update node parameters
4. Geometry updates in viewport

### Deleting Assets

1. Click × button on asset card
2. Removes multiparm instance
3. List refreshes automatically

## PyOneDark Styling

The UI follows Polyfactory's OneDark theme:

```python
# Color scheme
BLUE_PRIMARY   = "#61afef"  # Accents, hover states
BG_DARKEST     = "#1e1e1e"  # Main background
BG_DARK        = "#252525"  # Asset cards
BG_MEDIUM      = "#2c2c2c"  # Input fields
TEXT_PRIMARY   = "#e0e0e0"  # Main text
TEXT_SECONDARY = "#abb2bf"  # Labels
```

**Hover Effects:**
- Asset cards: Blue border on hover
- Spinboxes: Blue border on focus
- Buttons: Lighter background on hover

## Technical Implementation

### Parameter Binding

```python
# Read from parameters
t_parm = node.parmTuple(f"t{mesh_index}")
position = t_parm.eval()  # Returns (x, y, z)

# Write to parameters
t_parm.set((new_x, new_y, new_z))
```

### Polling for External Changes

The UI polls parameters every 500ms to catch changes from:
- Parameter pane edits
- Python scripts
- Expression updates
- Copy/paste operations

```python
self.poll_timer = QtCore.QTimer()
self.poll_timer.timeout.connect(self._poll_parameters)
self.poll_timer.start(500)  # 500ms interval
```

### Preventing Feedback Loops

```python
def _load_from_parameters(self):
    self._updating_from_parm = True
    # ... update UI widgets
    self._updating_from_parm = False

def _on_value_changed(self):
    if self._updating_from_parm:
        return  # Ignore changes from parameter updates
    # ... update parameters
```

### Multiparm Management

```python
# Get count
num_meshes = node.parm("num_meshes").eval()

# Add instance
node.parm("num_meshes").set(num_meshes + 1)

# Remove instance
node.parm("num_meshes").removeMultiParmInstance(index)
```

## Integration with Placement State

When user double-clicks asset in browser:

```python
def _on_asset_selected(self, asset_data):
    scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
    state_parms = {"asset_data": json.dumps(asset_data)}
    scene_viewer.enterViewerState("polyfactory.kitbash_placement", state_parms)
```

State places asset and adds to multiparm:

```python
def _place_asset(self):
    num_assets = self.kitbash_node.evalParm("num_meshes")
    self.kitbash_node.parm("num_meshes").set(num_assets + 1)
    
    idx = num_assets + 1
    self.kitbash_node.parm(f"file{idx}").set(self.asset_file)
    self.kitbash_node.parmTuple(f"t{idx}").set(self.placement_position)
    # ... etc
```

UI automatically detects new instance via polling and adds card to list.

## Module Reloading

For development iteration:

```python
from polyfactory.asset_library import reload_modules

# Reload kitbash UI
reload_modules.reload_asset_library()

# Then close and reopen Python Panel in Houdini
```

**Important:** After reloading, you must:
1. Close the HDA's Python Panel
2. Reopen it (or restart node)
3. UI will use reloaded code

## Troubleshooting

### UI Doesn't Appear

**Problem:** Python Panel shows blank or error

**Solutions:**
1. Check Houdini console for Python errors
2. Verify `createInterface()` function exists
3. Ensure `kwargs['node']` is available
4. Test standalone: `python polyfactory/asset_library/kitbash_ui.py`

### Parameters Not Updating

**Problem:** Spinboxes don't update node parameters

**Solutions:**
1. Check parameter names match exactly (`t#`, `r#`, `scale#`)
2. Verify multiparm naming scheme (starts at 1, not 0)
3. Check for exceptions in `_on_value_changed()`
4. Ensure node reference is valid

### List Doesn't Refresh

**Problem:** New assets don't appear in list after placement

**Solutions:**
1. Check polling timer is running
2. Verify `num_meshes` parameter exists
3. Call `_refresh_list()` manually for testing
4. Check if placement state is actually adding to multiparm

### Asset Browser Empty

**Problem:** No assets show in browser

**Solutions:**
1. Check `$PF_ASSET_LIBRARY` environment variable is set
2. Verify asset database exists (`$PF_ASSET_DB`)
3. Run asset export workflow to populate library
4. Check database connection in browser widget

## Customization

### Change Polling Interval

```python
# In PlacedAssetsListWidget.__init__()
self.poll_timer.start(1000)  # Poll every 1 second (slower)
self.poll_timer.start(100)   # Poll every 100ms (faster, more CPU)
```

### Add Custom Controls

```python
# In AssetInstanceWidget._setup_ui()

# Add enable/disable toggle
self.enable_check = QtWidgets.QCheckBox("Enabled")
self.enable_check.setStyleSheet("color: #e0e0e0;")
self.enable_check.stateChanged.connect(self._on_enable_changed)
layout.addWidget(self.enable_check)

def _on_enable_changed(self, state):
    enable_parm = self.node.parm(f"enable{self.mesh_index}")
    if enable_parm:
        enable_parm.set(state == QtCore.Qt.Checked)
```

### Custom Asset Card Styling

```python
# Override stylesheet in AssetInstanceWidget.__init__()
self.setStyleSheet("""
    AssetInstanceWidget {
        background-color: #2c2c2c;  # Lighter default
        border: 2px solid #61afef;   # Thicker border
        border-radius: 8px;          # More rounded
        padding: 12px;               # More padding
    }
    AssetInstanceWidget:hover {
        background-color: #3a3a3a;
        box-shadow: 0 4px 8px rgba(97, 175, 239, 0.3);
    }
""")
```

## Future Enhancements

### Planned Features

- [ ] **Drag to reorder** assets in list
- [ ] **Copy/paste** transform values between assets
- [ ] **Select in viewport** - click card to highlight in viewport
- [ ] **Thumbnail previews** in asset cards
- [ ] **Batch operations** - scale all, delete all, etc.
- [ ] **Groups/layers** - organize assets into folders
- [ ] **Visibility toggles** - show/hide individual assets
- [ ] **Lock transforms** - prevent accidental edits
- [ ] **Randomize** button - random rotation/scale variations

### Extension Points

- Custom parameter types (color, material override, etc.)
- Asset variants (swap between LODs)
- Instance painting (scatter mode integration)
- Export selected instances to separate geometry
- Merge/combine instances into single mesh

## Code Reference

**Main Files:**
- `kitbash_ui.py` - Python Panel UI implementation
- `kitbash_placement_state.py` - Viewport placement state
- `browser_ui.py` - Asset browser widget

**Key Classes:**
- `KitbashNodeUI` - Root widget for HDA UI
- `AssetBrowserWidget` - Asset library browser
- `PlacedAssetsListWidget` - List of placed assets
- `AssetInstanceWidget` - Single asset card with controls

**Key Functions:**
- `createInterface()` - Entry point for Python Panel
- `_refresh_list()` - Rebuild asset list from multiparm
- `_poll_parameters()` - Sync UI with parameter changes
- `_on_asset_selected()` - Enter placement mode

## Questions?

- Check Polyfactory documentation
- Review example HDAs in `polyfactory/otls/`
- Inspect Houdini's built-in Python Panel HDAs
- Contact development team
