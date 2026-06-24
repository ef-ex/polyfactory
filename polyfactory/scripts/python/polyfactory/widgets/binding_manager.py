"""
Binding Manager - Central coordinator for parameter-widget synchronization

Manages bidirectional data flow between Qt widgets and Houdini parameters.
Handles updates, callbacks, and lifecycle.
"""

import hou
from PySide6 import QtWidgets, QtCore
from typing import Dict, Any, Optional, Callable


class BindingManager:
    """
    Manages parameter bindings for an HDA Python Panel UI.
    
    Coordinates updates between Qt widgets and Houdini parameters,
    ensuring changes in either direction are synchronized.
    
    Example:
        >>> manager = BindingManager(kwargs['node'])
        >>> scale_widget = manager.create_float("scale", label="Scale")
        >>> layout = manager.build_layout()
    """
    
    def __init__(self, node: hou.Node):
        """
        Initialize binding manager for a node.
        
        Args:
            node: The HDA node whose parameters will be bound
        """
        self.node = node
        self.bindings: Dict[str, 'ParmBinding'] = {}
        self.widgets: list = []
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self._poll_parm_changes)
        self.update_timer.start(100)  # Poll every 100ms for external parm changes
        
    def create_float(
        self,
        parm_name: str,
        label: Optional[str] = None,
        range: Optional[tuple] = None,
        decimals: int = 3
    ) -> QtWidgets.QWidget:
        """Create a float slider widget bound to a parameter."""
        from .widgets import ParmFloat
        
        parm = self.node.parm(parm_name)
        if not parm:
            raise ValueError(f"Parameter '{parm_name}' not found on node {self.node.path()}")
        
        widget = ParmFloat(parm, label=label, range=range, decimals=decimals)
        self._register_binding(parm_name, widget)
        return widget
    
    def create_int(
        self,
        parm_name: str,
        label: Optional[str] = None,
        range: Optional[tuple] = None
    ) -> QtWidgets.QWidget:
        """Create an integer spinbox widget bound to a parameter."""
        from .widgets import ParmInt
        
        parm = self.node.parm(parm_name)
        if not parm:
            raise ValueError(f"Parameter '{parm_name}' not found on node {self.node.path()}")
        
        widget = ParmInt(parm, label=label, range=range)
        self._register_binding(parm_name, widget)
        return widget
    
    def create_string(
        self,
        parm_name: str,
        label: Optional[str] = None,
        multiline: bool = False
    ) -> QtWidgets.QWidget:
        """Create a string input widget bound to a parameter."""
        from .widgets import ParmString
        
        parm = self.node.parm(parm_name)
        if not parm:
            raise ValueError(f"Parameter '{parm_name}' not found on node {self.node.path()}")
        
        widget = ParmString(parm, label=label, multiline=multiline)
        self._register_binding(parm_name, widget)
        return widget
    
    def create_toggle(
        self,
        parm_name: str,
        label: Optional[str] = None
    ) -> QtWidgets.QWidget:
        """Create a checkbox widget bound to a parameter."""
        from .widgets import ParmToggle
        
        parm = self.node.parm(parm_name)
        if not parm:
            raise ValueError(f"Parameter '{parm_name}' not found on node {self.node.path()}")
        
        widget = ParmToggle(parm, label=label)
        self._register_binding(parm_name, widget)
        return widget
    
    def create_menu(
        self,
        parm_name: str,
        label: Optional[str] = None
    ) -> QtWidgets.QWidget:
        """Create a dropdown menu widget bound to a parameter."""
        from .widgets import ParmMenu
        
        parm = self.node.parm(parm_name)
        if not parm:
            raise ValueError(f"Parameter '{parm_name}' not found on node {self.node.path()}")
        
        widget = ParmMenu(parm, label=label)
        self._register_binding(parm_name, widget)
        return widget
    
    def create_color(
        self,
        parm_name: str,
        label: Optional[str] = None,
        include_alpha: bool = False
    ) -> QtWidgets.QWidget:
        """Create a color picker widget bound to a parameter tuple."""
        from .widgets import ParmColor
        
        # Color parameters are tuples (RGB or RGBA)
        parm_tuple = self.node.parmTuple(parm_name)
        if not parm_tuple:
            raise ValueError(f"Parameter tuple '{parm_name}' not found on node {self.node.path()}")
        
        widget = ParmColor(parm_tuple, label=label, include_alpha=include_alpha)
        self._register_binding(parm_name, widget)
        return widget
    
    def create_button(
        self,
        label: str,
        callback: Callable[[], None]
    ) -> QtWidgets.QWidget:
        """Create a button widget (not bound to parameter)."""
        from .widgets import ParmButton
        
        widget = ParmButton(label=label, callback=callback)
        self.widgets.append(widget)
        return widget
    
    def _register_binding(self, parm_name: str, widget) -> None:
        """Register a widget-parameter binding."""
        self.bindings[parm_name] = widget
        self.widgets.append(widget)
    
    def _poll_parm_changes(self) -> None:
        """Poll for external parameter changes (from UI, expressions, etc)."""
        for parm_name, widget in self.bindings.items():
            if hasattr(widget, 'update_from_parm'):
                widget.update_from_parm()
    
    def build_layout(self, direction: str = "vertical") -> QtWidgets.QWidget:
        """
        Build a layout containing all registered widgets.
        
        Args:
            direction: "vertical" or "horizontal"
            
        Returns:
            QWidget with layout containing all widgets
        """
        from .layouts import HoudiniVLayout, HoudiniHLayout
        
        root = QtWidgets.QWidget()
        
        if direction == "vertical":
            layout = HoudiniVLayout()
        else:
            layout = HoudiniHLayout()
        
        for widget in self.widgets:
            layout.addWidget(widget)
        
        layout.addStretch()
        root.setLayout(layout)
        return root
    
    def cleanup(self) -> None:
        """Stop polling and clean up resources."""
        self.update_timer.stop()
