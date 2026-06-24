# HDA Configuration for pf_kitbash Python Panel

## Automatic Setup via HDA Type Properties

### Method 1: Set Python Panel in HDA (Recommended)

1. **Open HDA for editing:**
   - Right-click `pf_kitbash` node → **Type Properties**

2. **Go to Interactive tab:**
   - Click **Interactive** tab in Type Properties

3. **Enable Python Panel:**
   - Scroll down to **Python Panel** section
   - Check ☑ **Has Python Panel**
   
4. **Select the interface:**
   - In the dropdown, select: **pf_kitbash_ui** (Kitbash Assets)
   - OR click **Edit...** button to create inline code

5. **Set as default:**
   - Check ☑ **Show Python Panel by Default**

6. **Apply changes:**
   - Click **Apply**
   - Click **Accept**

### Method 2: Inline Python Panel Code (Alternative)

If you want to embed the code directly in the HDA instead of using the .pypanel file:

1. In Type Properties → Interactive → Python Panel
2. Click **Edit...** button
3. Paste this code:

```python
from PySide6 import QtWidgets
from polyfactory.asset_library.kitbash_ui import KitbashNodeUI

def createInterface():
    node = kwargs.get('node')
    if not node:
        widget = QtWidgets.QLabel("No node selected")
        widget.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")
        return widget
    return KitbashNodeUI(node)
```

## Verify Setup

### Check 1: Python Panel Definition Exists

The file `polyfactory/python_panels/polyfactory.pypanel` should now contain:
- `<interface name="pf_kitbash_ui" ...>`
- Script with `KitbashNodeUI` import

### Check 2: HDA Type Properties

In Type Properties → Interactive:
- ☑ Has Python Panel
- Interface: **pf_kitbash_ui** (selected from dropdown)
- ☑ Show Python Panel by Default

### Check 3: Test the Node

1. Create a new `pf_kitbash` node
2. Python Panel should appear automatically showing:
   - Asset browser at top
   - "Placed Assets" section below
3. If not visible, manually open it:
   - Right-click node → **Show Python Panel**

## Troubleshooting

### "pf_kitbash_ui not found in dropdown"

**Fix:**
1. Save and close Houdini scene
2. Restart Houdini (to reload .pypanel files)
3. The interface should now appear in the dropdown

OR use Method 2 (inline code) which doesn't require restart.

### Python Panel shows but is blank

**Fix:**
1. Check Houdini console for Python errors (Window → Python Shell)
2. Test the module manually:
   ```python
   from polyfactory.asset_library.kitbash_ui import KitbashNodeUI
   # Should not error
   ```
3. Reload modules:
   ```python
   from polyfactory.asset_library import reload_modules
   reload_modules.reload_asset_library()
   ```

### "No node selected" message appears

**Fix:**
- The UI is working, but `kwargs['node']` is not being passed
- This is normal when viewing the panel outside of a node context
- Create an actual pf_kitbash node instance to see the full UI

### Asset browser is empty

**Fix:**
1. Check `$PF_ASSET_LIBRARY` environment variable is set
2. Verify assets exist in the library
3. Check asset database (`$PF_ASSET_DB`)
4. Run asset export workflow to populate library

## Python Panel File Location

The interface is defined in:
```
polyfactory/python_panels/polyfactory.pypanel
```

This file is automatically loaded by Houdini from the package path.

**To verify it's loaded:**
1. Window → Python Panels
2. You should see **Kitbash Assets** in the list
3. Click it to open as a floating panel
4. When attached to a pf_kitbash node, it shows full functionality

## Alternative: Manual Python Panel Assignment

If you want to open the panel manually (not embedded in node):

```python
# In Houdini Python Shell
import hou

# Get or create a pf_kitbash node
node = hou.node('/obj/geo1/pf_kitbash1')

# Open Python Panel for this node
desktop = hou.ui.curDesktop()
pane = desktop.createFloatingPane(hou.paneTabType.PythonPanel)
pane.setCurrentNode(node)
pane.showToolbar(False)
```

## Complete Verification Script

Run this in Houdini Python Shell to verify everything is set up:

```python
import hou

# Check pypanel file exists
import os
pypanel_path = os.path.join(
    os.environ.get('POLYFACTORY', ''),
    'python_panels',
    'polyfactory.pypanel'
)
print(f"PyPanel file exists: {os.path.exists(pypanel_path)}")

# Check interface is available
interfaces = hou.pypanel.interfaces()
has_kitbash_ui = any('kitbash' in name.lower() for name in interfaces)
print(f"pf_kitbash_ui interface found: {has_kitbash_ui}")

# Check module imports
try:
    from polyfactory.asset_library.kitbash_ui import KitbashNodeUI
    print("✓ kitbash_ui module imports successfully")
except Exception as e:
    print(f"✗ Error importing kitbash_ui: {e}")

# Test creating node with panel
try:
    geo = hou.node('/obj').createNode('geo', 'test_kitbash')
    kitbash = geo.createNode('pf_kitbash')
    print(f"✓ Created test node: {kitbash.path()}")
    
    # Try to get Python Panel
    # Note: This may not work in batch mode
    print("Open the node in the UI and check for Python Panel")
except Exception as e:
    print(f"✗ Error creating test node: {e}")
```

## Next Steps

After configuring the HDA:

1. ✅ Create a pf_kitbash node
2. ✅ Python Panel appears automatically
3. ✅ Asset browser loads at top
4. ✅ "Placed Assets" list shows below
5. ✅ Double-click asset → enters placement mode
6. ✅ Place asset → appears in list
7. ✅ Edit transforms in UI
8. ✅ Delete via × button

The Python Panel should now be fully integrated with the HDA!
