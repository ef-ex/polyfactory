"""
Setup and test script for kitbash workflow

To use:
1. First create the pf_kitbash HDA manually (see instructions below)
2. Register the Python state
3. Open the asset browser
"""

import hou


def register_kitbash_state():
    """Register the kitbash placement Python state"""
    from polyfactory.asset_library import kitbash_placement_state
    
    template = kitbash_placement_state.createViewerStateTemplate()
    print(f"Registered state: {template.name()}")


def open_asset_browser():
    """Open the asset browser dialog"""
    from polyfactory.asset_library.browser_ui import show_asset_browser
    show_asset_browser()


def test_workflow():
    """Test the complete workflow"""
    print("=" * 60)
    print("PolyFactory Kitbash Workflow Test")
    print("=" * 60)
    
    # Register state
    print("\n1. Registering Python state...")
    register_kitbash_state()
    
    # Open browser
    print("\n2. Opening asset browser...")
    open_asset_browser()
    
    print("\n3. Instructions:")
    print("   - Double-click an asset in the browser")
    print("   - Move mouse in viewport to position")
    print("   - Press R to rotate (45° increments)")
    print("   - Press S (with Shift) to scale up/down")
    print("   - Click to place")
    print("   - ESC to cancel")
    print("\nNote: Make sure pf_kitbash HDA is installed!")
    print("=" * 60)


# Instructions for creating the HDA manually
HDA_CREATION_INSTRUCTIONS = """
=== Creating pf_kitbash HDA ===

1. Create a new Geometry node at SOP level
2. Inside, create this network:

   [ForEach Begin]
        |
   [Python/File] - Load USD based on multiparm index
        |
   [Transform] - Apply translate/rotate/scale from multiparm
        |
   [Switch] - Enable/disable based on multiparm toggle
        |
   [ForEach End]
        |
   [Merge] - Combine all assets
        |
   [OUT]

3. Create Digital Asset:
   - Right-click node → Create Digital Asset
   - Name: pf_kitbash
   - Label: PolyFactory Kitbash
   - Save to: $HOUDINI_USER_PREF_DIR/otls/pf_kitbash.hda

4. Edit Type Properties → Parameters:
   - Add Multiparm Block named "assets_folder" with label "Assets"
   - Inside multiparm add:
     * String: asset_file# (File) - USD File path
     * Vector3: asset_t# - Translate
     * Vector3: asset_r# - Rotate  
     * Vector3: asset_s# (default 1,1,1) - Scale
     * Toggle: asset_enable# (default On) - Enable

5. In the ForEach node:
   - Method: By Count
   - Count: ch("../assets_folder")

6. In the Python/File node for loading:
   - Use expression to get: chs("../asset_file" + chs("../_iterated_name"))
   - Or use Python SOP to load USD programmatically

7. In Transform node:
   - Translate: ch("../asset_t" + chs("../_iterated_name") + "x/y/z")
   - Rotate: ch("../asset_r" + chs("../_iterated_name") + "x/y/z")
   - Scale: ch("../asset_s" + chs("../_iterated_name") + "x/y/z")

8. Save and install the HDA

Alternative: Use the provided create_kitbash_hda.py script
(Note: Script creates basic structure, manual refinement recommended)
"""


if __name__ == "__main__":
    # Print instructions
    print(HDA_CREATION_INSTRUCTIONS)
    print("\n\nRun test_workflow() when HDA is ready")
