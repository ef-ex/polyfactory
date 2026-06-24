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


if __name__ == "__main__":
    # Print instructions
    print(HDA_CREATION_INSTRUCTIONS)
    print("\n\nRun test_workflow() when HDA is ready")
