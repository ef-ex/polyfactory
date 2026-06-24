"""
Hotkey command script to open asset export dialog
This script can be bound to a hotkey in Houdini

Usage:
1. Add to keyboard shortcuts via Edit > Hotkeys
2. Search for "h.pane.wsheet.tool:..." or create custom command
3. Or run directly: execfile("path/to/hotkey_export.py")
"""

import hou


def export_selected_to_library():
    """Main function to trigger asset export dialog"""
    try:
        from polyfactory.asset_library.export_ui import show_export_dialog
        
        # Show dialog (non-modal, so it just displays and returns the dialog object)
        dialog = show_export_dialog()
        
        # Note: Export is now triggered by clicking "Export Asset" button in the dialog
        # The dialog stays open and non-modal so user can preview the network
    
    except ImportError as e:
        hou.ui.displayMessage(
            f"Asset Library module not found: {e}\n\n"
            "Make sure polyfactory is properly loaded.",
            severity=hou.severityType.Error
        )
    except Exception as e:
        import traceback
        error_msg = traceback.format_exc()
        print(error_msg)
        hou.ui.displayMessage(
            f"Error during export:\n{error_msg}",
            severity=hou.severityType.Error
        )


# Execute when script is run
if __name__ == "__main__" or __name__ == "__builtin__":
    export_selected_to_library()
