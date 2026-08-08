"""
Numeric Parameter Widgets - ParmFloat, ParmInt

Float and integer parameter widgets using Houdini's native InputField
with built-in ladder dragging and slider support.
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
from typing import Optional
from . import parm_utils
from .parm_widgets_base import EnhancedInputField, BaseParmWidget


# ============================================================================
# Numeric Widgets (using Houdini's native InputField with built-in ladder)
# ============================================================================

class ParmFloat(BaseParmWidget):
    """
    Float parameter widget using Enhanced InputField with slider.
    
    Combines EnhancedInputField (with polish features) and QSlider for visual feedback.
    """
    
    def __init__(self, parm: hou.Parm, label: Optional[str] = None, range: Optional[tuple] = None, decimals: int = 3):
        """
        Args:
            parm: Houdini parameter to bind to
            label: Optional custom label (defaults to parm description)
            range: Optional (min, max) tuple for slider range
            decimals: Number of decimal places (not used - InputField handles internally)
        """
        super().__init__(parm)
        
        # Get range from parameter template or use provided
        parm_template = parm.parmTemplate()
        if range:
            self.min_val, self.max_val = range
        else:
            try:
                self.min_val = parm_template.minValue() if parm_template.minIsStrict() else 0.0
                self.max_val = parm_template.maxValue() if parm_template.maxIsStrict() else 100.0
            except (AttributeError, TypeError):
                self.min_val = 0.0
                self.max_val = 100.0
        
        # Store default value for reset
        self.default_value = parm_template.defaultValue()[0] if hasattr(parm_template, 'defaultValue') else 0.0
        
        # Create layout
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Use Enhanced InputField with polish features
        label_text = label or parm.description()
        self.input_field = EnhancedInputField(
            hou.qt.InputField.FloatType,
            1,  # Single component
            label=label_text
        )
        
        # Set initial value
        initial_value = parm.eval()
        self.input_field.setValues([initial_value])
        
        # Create slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(0)
        self.slider.setMaximum(1000)  # Use 0-1000 for precision
        self.slider.setValue(self._value_to_slider(initial_value))
        self.slider.setMinimumWidth(150)
        
        # Connect signals
        self.input_field.valueChanged.connect(self._on_input_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        # Connect enhanced features
        self.input_field.resetRequested.connect(self._reset_to_default)
        self.input_field.sliderToggleRequested.connect(self._toggle_slider)
        
        # Layout: InputField (with label) + Slider
        layout.addWidget(self.input_field)
        layout.addWidget(self.slider, 1)
        self.setLayout(layout)
        
        # Apply initial expression styling
        self._update_expression_style()
    
    def _value_to_slider(self, value: float) -> int:
        """Convert float value to slider position (0-1000)."""
        if self.max_val == self.min_val:
            return 0
        normalized = (value - self.min_val) / (self.max_val - self.min_val)
        return int(normalized * 1000)
    
    def _slider_to_value(self, pos: int) -> float:
        """Convert slider position to float value."""
        normalized = pos / 1000.0
        return self.min_val + normalized * (self.max_val - self.min_val)
    
    def _on_input_changed(self):
        """Handle value change from InputField."""
        if not self._updating_from_parm:
            value = self.input_field.value()
            # Update slider
            self.slider.blockSignals(True)
            self.slider.setValue(self._value_to_slider(value))
            self.slider.blockSignals(False)
            # Update parameter
            self._set_parm_value(value)
    
    def _on_slider_changed(self, pos: int):
        """Handle slider drag."""
        if not self._updating_from_parm:
            value = self._slider_to_value(pos)
            # Update input field
            self.input_field.blockSignals(True)
            self.input_field.setValues([value])
            self.input_field.blockSignals(False)
            # Update parameter
            self._set_parm_value(value)
    
    def _update_widget_value(self, value):
        """Update widget from parameter value."""
        self.input_field.blockSignals(True)
        self.slider.blockSignals(True)
        self.input_field.setValues([float(value)])
        self.slider.setValue(self._value_to_slider(float(value)))
        self.slider.blockSignals(False)
        self.input_field.blockSignals(False)
        self._update_expression_style()
    
    def _update_expression_style(self):
        """Update visual feedback for expression state."""
        if not self.parm:
            return
        
        has_expr = parm_utils.has_expression(self.parm)
        r, g, b = parm_utils.get_parm_color(self.parm)
        
        # Disable slider when expression is active
        self.slider.setEnabled(not has_expr)
        
        # Disable input field and set expression color
        line_edits = self.input_field.findChildren(QtWidgets.QLineEdit)
        for line_edit in line_edits:
            line_edit.setEnabled(not has_expr)
        
        # Set expression background color
        if has_expr:
            self.input_field.set_expression_color(QtGui.QColor(r, g, b))
        else:
            self.input_field.set_expression_color(QtGui.QColor(58, 58, 58))
    
    def _reset_to_default(self):
        """Reset parameter to default value (Ctrl+MMB on label)."""
        if self.parm:
            self.parm.revertToDefaults()
            self.update_from_parm()
    
    def _toggle_slider(self):
        """Toggle slider visibility (LMB on label)."""
        self.slider.setVisible(not self.slider.isVisible())


class ParmInt(BaseParmWidget):
    """
    Integer parameter widget using Enhanced InputField with slider.
    
    Combines EnhancedInputField (with polish features) and QSlider for visual feedback.
    """
    
    def __init__(self, parm: hou.Parm, label: Optional[str] = None, range: Optional[tuple] = None):
        super().__init__(parm)
        
        # Get range from parameter template or use provided
        parm_template = parm.parmTemplate()
        if range:
            self.min_val, self.max_val = range
        else:
            try:
                self.min_val = int(parm_template.minValue()) if parm_template.minIsStrict() else 0
                self.max_val = int(parm_template.maxValue()) if parm_template.maxIsStrict() else 100
            except (AttributeError, TypeError):
                self.min_val = 0
                self.max_val = 100
        
        # Store default value for reset
        self.default_value = int(parm_template.defaultValue()[0]) if hasattr(parm_template, 'defaultValue') else 0
        
        # Create layout
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        
        # Use Enhanced InputField with polish features
        label_text = label or parm.description()
        self.input_field = EnhancedInputField(
            hou.qt.InputField.IntegerType,
            1,  # Single component
            label=label_text
        )
        
        # Set initial value
        initial_value = int(parm.eval())
        self.input_field.setValues([initial_value])
        
        # Create slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimum(self.min_val)
        self.slider.setMaximum(self.max_val)
        self.slider.setValue(initial_value)
        self.slider.setMinimumWidth(150)
        
        # Connect signals
        self.input_field.valueChanged.connect(self._on_input_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        # Connect enhanced features
        self.input_field.resetRequested.connect(self._reset_to_default)
        self.input_field.sliderToggleRequested.connect(self._toggle_slider)
        
        # Layout: InputField (with label) + Slider
        layout.addWidget(self.input_field)
        layout.addWidget(self.slider, 1)
        self.setLayout(layout)
        
        # Apply initial expression styling
        self._update_expression_style()
    
    def _on_input_changed(self):
        """Handle value change from InputField."""
        if not self._updating_from_parm:
            value = int(self.input_field.value())
            # Update slider
            self.slider.blockSignals(True)
            self.slider.setValue(value)
            self.slider.blockSignals(False)
            # Update parameter
            self._set_parm_value(value)
    
    def _on_slider_changed(self, value: int):
        """Handle slider drag."""
        if not self._updating_from_parm:
            # Update input field
            self.input_field.blockSignals(True)
            self.input_field.setValues([value])
            self.input_field.blockSignals(False)
            # Update parameter
            self._set_parm_value(value)
    
    def _update_widget_value(self, value):
        """Update widget from parameter value."""
        int_value = int(value)
        self.input_field.blockSignals(True)
        self.slider.blockSignals(True)
        self.input_field.setValues([int_value])
        self.slider.setValue(int_value)
        self.slider.blockSignals(False)
        self.input_field.blockSignals(False)
        self._update_expression_style()
    
    def _update_expression_style(self):
        """Update visual feedback for expression state."""
        if not self.parm:
            return
        
        has_expr = parm_utils.has_expression(self.parm)
        r, g, b = parm_utils.get_parm_color(self.parm)
        
        # Disable slider when expression is active
        self.slider.setEnabled(not has_expr)
        
        # Disable input field and set expression color
        line_edits = self.input_field.findChildren(QtWidgets.QLineEdit)
        for line_edit in line_edits:
            line_edit.setEnabled(not has_expr)
        
        # Set expression background color
        if has_expr:
            self.input_field.set_expression_color(QtGui.QColor(r, g, b))
        else:
            self.input_field.set_expression_color(QtGui.QColor(58, 58, 58))
    
    def _reset_to_default(self):
        """Reset parameter to default value (Ctrl+MMB on label)."""
        if self.parm:
            self.parm.revertToDefaults()
            self.update_from_parm()
    
    def _toggle_slider(self):
        """Toggle slider visibility (LMB on label)."""
        self.slider.setVisible(not self.slider.isVisible())
