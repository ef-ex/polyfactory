# Quick Setup: pf_kitbash HDA Python Panel

## Step-by-Step Instructions

### 1. Open HDA for Editing

```
Right-click pf_kitbash node → Type Properties
```

### 2. Go to Interactive Tab

In the Type Properties dialog:
- Click **Interactive** tab

### 3. Add Python Panel Section

Scroll to **Python Panel** section at bottom.

### 4. Set Python Panel Code

Click the **Python Panel** editor button.

**Method A: Import from module (recommended)**

```python
from polyfactory.asset_library.kitbash_ui import createInterface
```

That's it! The `createInterface()` function is already exported.

**Method B: Inline (if you need custom logic)**

```python
from polyfactory.asset_library.kitbash_ui import KitbashNodeUI

def createInterface():
    node = kwargs.get('node')
    if not node:
        from PySide6 import QtWidgets
        return QtWidgets.QLabel("No node available")
    return KitbashNodeUI(node)
```

### 5. Enable Python Panel Display

Still in Interactive tab:

- Check ☑ **Show Python Panel by Default**

### 6. Apply and Accept

Click **Apply** then **Accept**

### 7. Test the UI

1. Create a `pf_kitbash` node
2. The Python Panel should appear automatically
3. You should see:
   - Asset browser at top
   - "Placed Assets" section below
   - Empty at first (no assets placed yet)

### 8. Place an Asset

1. Double-click an asset in the browser
2. Viewport enters placement mode
3. Click to place asset
4. Asset appears in "Placed Assets" list below

## Multiparm Structure

The HDA **must** have these exact parameters:

```
num_meshes (Integer, multiparm count)
  ├─ file# (File path string)
  ├─ t# (Vector3: tx#, ty#, tz#)
  ├─ r# (Vector3: rx#, ry#, rz#)
  └─ scale# (Float)
```

**Important naming:**
- Multiparm starts at index **1** (not 0)
- Use `#` token for multiparm instances
- Parameter names are case-sensitive

## Verifying Setup

### Check 1: Python Panel Code

In Type Properties → Interactive → Python Panel editor, you should see:

```python
from polyfactory.asset_library.kitbash_ui import createInterface
```

### Check 2: Parameters

In Type Properties → Parameters tab, you should see:

- `num_meshes` (Integer) with "Multiple" badge
- Under that, a folder with `#` token containing:
  - `file#`
  - `t#` (vector3)
  - `r#` (vector3)
  - `scale#` (float)

### Check 3: UI Appears

When you create the node:
- Python Panel shows automatically (or in separate pane)
- No Python errors in console
- Asset browser loads with thumbnails

## Troubleshooting

### "No module named 'polyfactory'"

**Fix:** Ensure `polyfactory.json` package file is installed in `$HOUDINI_USER_PREF_DIR/packages/`

### "No node available" message

**Fix:** 
1. Check Python Panel code has `kwargs['node']` available
2. Verify you're viewing the UI for an actual node instance (not type properties)

### UI is blank

**Fix:**
1. Check Houdini Console for errors (Window → Python Shell)
2. Reload modules: `from polyfactory.asset_library import reload_modules; reload_modules.reload_asset_library()`
3. Close and reopen Python Panel

### Assets don't show in browser

**Fix:**
1. Check `$PF_ASSET_LIBRARY` environment variable
2. Run asset export workflow to populate library
3. Verify asset database exists

### Placed assets list is empty

**Fix:**
1. Check multiparm is named `num_meshes` (exact name)
2. Verify file path parameters are `file#`
3. Place an asset via placement state first

## Quick Test

In Houdini Python Shell:

```python
# Create test node
geo = hou.node('/obj').createNode('geo')
kitbash = geo.createNode('pf_kitbash')

# Add test asset manually
kitbash.parm('num_meshes').set(1)
kitbash.parm('file1').set('/path/to/test.usd')
kitbash.parmTuple('t1').set((0, 0, 0))
kitbash.parmTuple('r1').set((0, 0, 0))
kitbash.parm('scale1').set(1.0)

# Should see 1 asset in UI list
```

## Next Steps

1. ✅ Verify UI appears and loads
2. ✅ Test asset browser functionality
3. ✅ Place an asset via double-click → placement mode
4. ✅ Edit asset transform in UI
5. ✅ Delete an asset via × button
6. ✅ Check parameters update correctly

## Full Documentation

See `documentation/kitbash_hda_ui_setup.md` for complete details on:
- Custom styling
- Adding features
- Troubleshooting
- Code references
