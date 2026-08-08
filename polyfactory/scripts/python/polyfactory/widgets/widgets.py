"""
Widget Components - Houdini-styled Qt widgets with parameter binding

String, toggle, menu, color, and button widgets.
Base classes and numeric widgets are in parm_widgets_base.py and parm_widgets_numeric.py.
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
from typing import Optional
from . import parm_utils

# Re-export base and numeric classes for backward compatibility
from .parm_widgets_base import EnhancedLabel, EnhancedInputField, BaseParmWidget, ExpressionDialog
from .parm_widgets_numeric import ParmFloat, ParmInt

__all__ = [
    "EnhancedLabel", "EnhancedInputField", "BaseParmWidget", "ExpressionDialog",
    "ParmFloat", "ParmInt",
    "ParmString", "ParmToggle", "ParmMenu", "ParmColor", "ParmButton",
]

# ============================================================================
# Remaining Widgets (string, toggle, menu, color, button)
# ============================================================================

class ParmString(BaseParmWidget):
    """String input widget with enhanced label."""
    
    def __init__(
        self,
        parm: hou.Parm,
        label: Optional[str] = None,
        multiline: bool = False
    ):
        super().__init__(parm)
        
        layout = QtWidgets.QVBoxLayout() if multiline else QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Use EnhancedLabel with polish features
        label_text = label or parm.description()
        self.label = EnhancedLabel(label_text)
        if not multiline:
            self.label.setMinimumWidth(100)
        
        # Connect label signals
        self.label.resetRequested.connect(self._reset_to_default)
        
        layout.addWidget(self.label)
        
        if multiline:
            self.input = QtWidgets.QTextEdit()
            self.input.setPlainText(parm.eval())
            self.input.textChanged.connect(self._on_changed)
        else:
            self.input = QtWidgets.QLineEdit()
            self.input.setText(parm.eval())
            self.input.textChanged.connect(self._on_changed)
        
        layout.addWidget(self.input, 1)
        self.setLayout(layout)
        
        self.setStyleSheet("""
            QLineEdit, QTextEdit {
                background: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #cccccc;
                padding: 2px;
            }
        """)
    
    def _reset_to_default(self):
        """Reset parameter to default value (Ctrl+MMB on label)."""
        if self.parm:
            self.parm.revertToDefaults()
            self.update_from_parm()
    
    def _on_changed(self):
        if not self._updating_from_parm:
            if isinstance(self.input, QtWidgets.QTextEdit):
                value = self.input.toPlainText()
            else:
                value = self.input.text()
            self._set_parm_value(value)
    
    def _update_widget_value(self, value):
        if isinstance(self.input, QtWidgets.QTextEdit):
            self.input.blockSignals(True)
            self.input.setPlainText(str(value))
            self.input.blockSignals(False)
        else:
            self.input.blockSignals(True)
            self.input.setText(str(value))
            self.input.blockSignals(False)
        
        # Update expression styling
        self._update_expression_style()
    
    def _update_expression_style(self):
        """Update visual feedback for expression state."""
        if not self.parm:
            return
        
        has_expr = parm_utils.has_expression(self.parm)
        r, g, b = parm_utils.get_parm_color(self.parm)
        
        # Disable input when expression is active
        self.input.setEnabled(not has_expr)
        
        # Set expression background color
        if has_expr:
            self.input.setStyleSheet(f"""
                QLineEdit, QTextEdit {{
                    background-color: rgb({r},{g},{b});
                    border: 1px solid #3a3a3a;
                    color: rgb(204,204,204);
                    padding: 2px;
                }}
            """)
        else:
            # Reset to default stylesheet
            self.input.setStyleSheet("""
                QLineEdit, QTextEdit {
                    background: #2a2a2a;
                    border: 1px solid #3a3a3a;
                    color: #cccccc;
                    padding: 2px;
                }
            """)


class ParmToggle(BaseParmWidget):
    """Checkbox widget."""
    
    def __init__(self, parm: hou.Parm, label: Optional[str] = None):
        super().__init__(parm)
        
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        label_text = label or parm.description()
        self.checkbox = QtWidgets.QCheckBox(label_text)
        self.checkbox.setChecked(bool(parm.eval()))
        self.checkbox.stateChanged.connect(self._on_changed)
        
        layout.addWidget(self.checkbox)
        layout.addStretch()
        self.setLayout(layout)
        
        self.setStyleSheet("""
            QCheckBox {
                color: #cccccc;
            }
            QCheckBox::indicator {
                width: 16px;
                height: 16px;
                border: 1px solid #3a3a3a;
                background: #2a2a2a;
            }
            QCheckBox::indicator:checked {
                background: #5a8ab4;
            }
        """)
    
    def _on_changed(self, state):
        if not self._updating_from_parm:
            self._set_parm_value(1 if state == QtCore.Qt.Checked else 0)
    
    def _update_widget_value(self, value):
        self.checkbox.blockSignals(True)
        self.checkbox.setChecked(bool(value))
        self.checkbox.blockSignals(False)
        
        # Update expression styling
        self._update_expression_style()
    
    def _update_expression_style(self):
        """Update visual feedback for expression state."""
        if not self.parm:
            return
        
        has_expr = parm_utils.has_expression(self.parm)
        r, g, b = parm_utils.get_parm_color(self.parm)
        
        # When expression active: disable but still show visual state
        # Don't call setEnabled - it prevents visual updates
        # Instead, intercept clicks in event filter
        
        # Set expression background color
        if has_expr:
            # Show expression color but keep checked state visible
            checked_r, checked_g, checked_b = max(r, 90), max(g, 138), max(b, 180)  # Slightly brighter for checked
            self.checkbox.setStyleSheet(f"""
                QCheckBox {{
                    color: rgb(204,204,204);
                }}
                QCheckBox::indicator {{
                    width: 16px;
                    height: 16px;
                    border: 1px solid #3a3a3a;
                    background-color: rgb({r},{g},{b});
                }}
                QCheckBox::indicator:checked {{
                    background-color: rgb({checked_r},{checked_g},{checked_b});
                    border: 2px solid rgb(255,255,255);
                }}
            """)
            # Block user input via event filter instead of setEnabled
            if not self.checkbox.eventFilter:
                self.checkbox.installEventFilter(self)
        else:
            # Reset to default stylesheet
            self.checkbox.setStyleSheet("""
                QCheckBox {
                    color: #cccccc;
                }
                QCheckBox::indicator {
                    width: 16px;
                    height: 16px;
                    border: 1px solid #3a3a3a;
                    background: #2a2a2a;
                }
                QCheckBox::indicator:checked {
                    background: #5a8ab4;
                }
            """)
            # Remove event filter
            try:
                self.checkbox.removeEventFilter(self)
            except Exception:
                pass
    
    def eventFilter(self, obj, event):
        """Block user input when expression is active."""
        if obj == self.checkbox and parm_utils.has_expression(self.parm):
            if event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
                return True  # Block click
        return super().eventFilter(obj, event)


class ParmMenu(BaseParmWidget):
    """Dropdown menu widget with enhanced label."""
    
    def __init__(self, parm: hou.Parm, label: Optional[str] = None):
        super().__init__(parm)
        
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Use EnhancedLabel with polish features
        label_text = label or parm.description()
        self.label = EnhancedLabel(label_text)
        self.label.setMinimumWidth(100)
        
        # Connect label signals
        self.label.resetRequested.connect(self._reset_to_default)
        
        layout.addWidget(self.label)
        
        self.combo = QtWidgets.QComboBox()
        
        # Get menu items from parm template
        template = parm.parmTemplate()
        if hasattr(template, 'menuItems'):
            menu_items = template.menuItems()
            menu_labels = template.menuLabels()
            for item, label in zip(menu_items, menu_labels):
                self.combo.addItem(label, item)
        
        # Set current value
        current = parm.eval()
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == current:
                self.combo.setCurrentIndex(i)
                break
        
        self.combo.currentIndexChanged.connect(self._on_changed)
        
        layout.addWidget(self.combo, 1)
        self.setLayout(layout)
        
        self.setStyleSheet("""
            QLabel { color: #cccccc; }
            QComboBox {
                background: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #cccccc;
                padding: 2px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                image: url(none);
                border: none;
            }
        """)
    
    def _get_parm_value(self):
        """Menu parms can be int or string - get the string token."""
        if self.parm:
            try:
                # Try to get as string token (preferred)
                return self.parm.evalAsString()
            except Exception:
                # If that fails, get as int and convert to token
                index = self.parm.eval()
                template = self.parm.parmTemplate()
                if hasattr(template, 'menuItems'):
                    menu_items = template.menuItems()
                    if 0 <= index < len(menu_items):
                        return menu_items[index]
                return index
        return None
    
    def _on_changed(self, index):
        if not self._updating_from_parm:
            value = self.combo.itemData(index)
            self._set_parm_value(value)
    
    def _update_widget_value(self, value):
        self.combo.blockSignals(True)
        
        # Try to find matching item - handle type conversion
        found = False
        for i in range(self.combo.count()):
            item_data = self.combo.itemData(i)
            # Compare with type coercion (menu can be int or string)
            if item_data == value or str(item_data) == str(value) or (isinstance(value, (int, float)) and item_data == int(value)):
                self.combo.setCurrentIndex(i)
                found = True
                break
        
        self.combo.blockSignals(False)
        
        # Update expression styling
        self._update_expression_style()
    
    def _update_expression_style(self):
        """Update visual feedback for expression state."""
        if not self.parm:
            return
        
        has_expr = parm_utils.has_expression(self.parm)
        r, g, b = parm_utils.get_parm_color(self.parm)
        
        # When expression active: show color but still display current value
        # Block user input via event filter instead of setEnabled
        
        # Set expression background color
        if has_expr:
            self.combo.setStyleSheet(f"""
                QComboBox {{
                    background-color: rgb({r},{g},{b});
                    border: 1px solid #3a3a3a;
                    color: rgb(204,204,204);
                    padding: 2px;
                }}
                QComboBox::drop-down {{
                    border: none;
                }}
                QComboBox::down-arrow {{
                    image: url(none);
                    border: none;
                }}
            """)
            # Block user input via event filter
            if not self.combo.eventFilter:
                self.combo.installEventFilter(self)
        else:
            # Reset to default stylesheet
            self.combo.setStyleSheet("""
                QComboBox {
                    background: #2a2a2a;
                    border: 1px solid #3a3a3a;
                    color: #cccccc;
                    padding: 2px;
                }
                QComboBox::drop-down {
                    border: none;
                }
                QComboBox::down-arrow {
                    image: url(none);
                    border: none;
                }
            """)
            # Remove event filter
            try:
                self.combo.removeEventFilter(self)
            except Exception:
                pass
    
    def eventFilter(self, obj, event):
        """Block user input when expression is active."""
        if obj == self.combo and parm_utils.has_expression(self.parm):
            if event.type() in (QtCore.QEvent.MouseButtonPress, QtCore.QEvent.MouseButtonRelease):
                return True  # Block clicks to prevent dropdown
        return super().eventFilter(obj, event)
    
    def _reset_to_default(self):
        """Reset parameter to default value (Ctrl+MMB on label)."""
        if self.parm:
            self.parm.revertToDefaults()
            self.update_from_parm()


class ParmColor(BaseParmWidget):
    """Color picker widget using Houdini's native ColorField."""
    
    def __init__(self, parm_tuple: hou.ParmTuple, label: Optional[str] = None, include_alpha: bool = False):
        # Store the tuple and pass first component to base class for polling
        self.parm_tuple = parm_tuple
        super().__init__(parm_tuple[0])
        
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Use EnhancedLabel with polish features
        label_text = label or parm_tuple.name().replace("_", " ").title()
        self.label = EnhancedLabel(label_text)
        self.label.setMinimumWidth(100)
        
        # Connect label signals
        self.label.resetRequested.connect(self._reset_to_default)
        
        layout.addWidget(self.label)
        
        # Use Houdini's native ColorField
        num_components = len(parm_tuple)
        self.color_field = hou.qt.ColorField(include_alpha=(num_components == 4))
        
        # Set initial value from parameter tuple
        color_values = [p.eval() for p in parm_tuple]
        
        if num_components >= 3:
            # ColorField expects QtGui.QColor, not hou.Color
            qcolor = QtGui.QColor.fromRgbF(color_values[0], color_values[1], color_values[2])
            if num_components == 4:
                qcolor.setAlphaF(color_values[3])
            self.color_field.setColor(qcolor)
        
        # Connect signal
        self.color_field.colorChanged.connect(self._on_color_changed)
        
        layout.addWidget(self.color_field, 1)
        self.setLayout(layout)
    
    def _on_color_changed(self):
        """Handle color change from ColorField."""
        if not self._updating_from_parm:
            color = self.color_field.color()  # Returns QColor
            # Set all components of the color tuple
            self.parm_tuple[0].set(color.redF())
            self.parm_tuple[1].set(color.greenF())
            self.parm_tuple[2].set(color.blueF())
            
            # Set alpha if tuple has 4 components
            if len(self.parm_tuple) == 4:
                self.parm_tuple[3].set(color.alphaF())
    
    def _get_parm_value(self):
        """Get color as tuple."""
        return tuple(p.eval() for p in self.parm_tuple)
    
    def _update_widget_value(self, value):
        """Update widget from parameter value."""
        self.color_field.blockSignals(True)
        if isinstance(value, (list, tuple)) and len(value) >= 3:
            qcolor = QtGui.QColor.fromRgbF(value[0], value[1], value[2])
            if len(value) == 4:
                qcolor.setAlphaF(value[3])
            self.color_field.setColor(qcolor)
        self.color_field.blockSignals(False)
        
        # Update expression styling
        self._update_expression_style()
    
    def _update_expression_style(self):
        """Update visual feedback for expression state."""
        if not self.parm_tuple:
            return
        
        # Check if any component has an expression
        has_expr = any(parm_utils.has_expression(p) for p in self.parm_tuple)
        
        # Disable color field when expression is active
        self.color_field.setEnabled(not has_expr)
        
        # ColorField has internal styling, expression color is indicated by disabled state
    
    def _reset_to_default(self):
        """Reset parameter to default value (Ctrl+MMB on label)."""
        if self.parm_tuple:
            # Reset all components in the tuple
            for component_parm in self.parm_tuple:
                component_parm.revertToDefaults()
            self.update_from_parm()


class ParmButton(QtWidgets.QWidget):
    """Button widget (not parameter-bound)."""
    
    def __init__(self, label: str, callback):
        super().__init__()
        
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        self.button = QtWidgets.QPushButton(label)
        self.button.clicked.connect(callback)
        
        layout.addWidget(self.button)
        layout.addStretch()
        self.setLayout(layout)
        
        self.setStyleSheet("""
            QPushButton {
                background: #3a3a3a;
                border: 1px solid #5a5a5a;
                color: #cccccc;
                padding: 4px 12px;
                border-radius: 2px;
            }
            QPushButton:hover {
                background: #4a4a4a;
            }
            QPushButton:pressed {
                background: #2a2a2a;
            }
        """)
