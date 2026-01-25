"""
Parameter Panel Utilities - Helper functions for creating floating parameter windows

Uses Houdini's native parameter panel API to create floating windows.
"""

import hou


def show_floating_parm_panel(node: hou.Node):
    """
    Open a floating parameter panel for a node using Houdini's native API.
    
    This uses the same mechanism as Houdini's built-in "Show LOP Network Parameter Dialog"
    button in the Scene Graph Tree.
    
    Args:
        node: The Houdini node whose parameters to display
    
    Example:
        >>> node = hou.node("/obj/geo1")
        >>> show_floating_parm_panel(node)
    """
    if not node:
        raise ValueError("Node cannot be None")
    
    # Get the current network editor
    network_editor = None
    for pane in hou.ui.paneTabs():
        if isinstance(pane, hou.NetworkEditor):
            network_editor = pane
            break
    
    if not network_editor:
        # If no network editor found, create one temporarily or use any pane
        desktop = hou.ui.curDesktop()
        network_editor = desktop.paneTabOfType(hou.paneTabType.NetworkEditor)
    
    if network_editor:
        # Use Houdini's native floating parameter editor
        network_editor.openFloatingParameterEditor(node)
    else:
        hou.ui.displayMessage(
            "Could not find a network editor to open the parameter panel",
            severity=hou.severityType.Warning
        )

# Convenience function for shelf tools / hotkeys
def show_selected_node_parms():
    """
    Show floating parameter panel for currently selected node.
    
    Useful for shelf tools or hotkeys to quickly pop out parameters.
    """
    selected = hou.selectedNodes()
    if not selected:
        hou.ui.displayMessage("No node selected", severity=hou.severityType.Warning)
        return
    
    # Open floating parameter editor for each selected node
    for node in selected:
        show_floating_parm_panel(node)
