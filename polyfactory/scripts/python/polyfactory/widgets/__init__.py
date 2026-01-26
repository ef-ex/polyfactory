"""
Polyfactory Widgets Module

Qt widgets for Houdini workflows.

Submodules:
- tag_input: ShotGrid-style tag input with auto-completion (asset-library branch)
- HDA widgets: Unified widget system for HDA Python Panel UIs with parameter binding
- parm_utils: Parameter utility functions for expression handling

HDA Widget Example:
    ```python
    from polyfactory.widgets import BindingManager
    
    def createInterface():
        node = kwargs['node']
        manager = BindingManager(node)
        
        # Create widget bound to parm "scale"
        scale_widget = manager.create_float("scale", label="Scale", range=(0.1, 10.0))
        
        # Create widget bound to parm "enabled"
        enabled_widget = manager.create_toggle("enabled", label="Enable Effect")
        
        # Layout automatically handles updates
        return manager.build_layout()
    ```

Status: WIP - Core architecture
TODO: Add color picker, ramp, file path widgets
TODO: Add validation and constraints
"""

# Import submodules to ensure they're loaded for reloading
from . import parm_utils
from . import hover_outline

from .binding_manager import BindingManager
from .widgets import (
    ParmFloat,
    ParmInt,
    ParmString,
    ParmToggle,
    ParmMenu,
    ParmColor,
    ParmButton
)
from .layouts import HoudiniVLayout, HoudiniHLayout, HoudiniGroupBox
from .parm_panel import (
    show_floating_parm_panel,
    show_selected_node_parms
)
from .hover_outline import HoverOutlineMixin

__all__ = [
    'BindingManager',
    'ParmFloat',
    'ParmInt', 
    'ParmString',
    'ParmToggle',
    'ParmMenu',
    'ParmColor',
    'ParmButton',
    'HoudiniVLayout',
    'HoudiniHLayout',
    'HoudiniGroupBox',
    'show_floating_parm_panel',
    'show_selected_node_parms',
    'HoverOutlineMixin'
]

