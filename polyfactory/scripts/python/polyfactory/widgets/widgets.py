"""
Widget Components - Houdini-styled Qt widgets with parameter binding

Simplified to use Houdini's native hou.qt.InputField for numeric parameters.
Each widget handles bidirectional sync with a Houdini parameter.
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
from typing import Optional
from . import parm_utils


# ============================================================================
# Label Enhancement - Shared hover/click features for all widgets
# ============================================================================

class EnhancedLabel(QtWidgets.QLabel):
    """
    Enhanced QLabel with Houdini parameter polish features:
    - Hover effects (lighter background, black outline)
    - Ctrl+MMB to reset to default
    - LMB for custom action (e.g., toggle slider)
    - Alt+LMB for keyframes (placeholder)
    """
    
    # Signals
    resetRequested = QtCore.Signal()
    actionRequested = QtCore.Signal()  # Generic action (LMB)
    
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setCursor(QtCore.Qt.PointingHandCursor)
        self._is_hovered = False
    
    def enterEvent(self, event):
        """Add hover effect."""
        self._is_hovered = True
        self._update_style()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Remove hover effect."""
        self._is_hovered = False
        self._update_style()
        super().leaveEvent(event)
    
    def _update_style(self):
        """Update visual style based on hover state."""
        if self._is_hovered:
            # Houdini style: lighter background + black outline
            self.setStyleSheet("""
                QLabel {
                    background-color: rgb(70, 70, 70);
                    border: 1px solid rgb(0, 0, 0);
                    padding: 1px;
                }
            """)
        else:
            # Clear stylesheet
            self.setStyleSheet("")
    
    def mousePressEvent(self, event):
        """Handle mouse clicks."""
        button = event.button()
        modifiers = event.modifiers()
        
        if button == QtCore.Qt.LeftButton and modifiers == QtCore.Qt.NoModifier:
            # LMB: Generic action
            self.actionRequested.emit()
            event.accept()
        elif button == QtCore.Qt.MiddleButton and modifiers == QtCore.Qt.ControlModifier:
            # Ctrl+MMB: Reset to default
            self.resetRequested.emit()
            event.accept()
        elif button == QtCore.Qt.LeftButton and modifiers == QtCore.Qt.AltModifier:
            # Alt+LMB: Keyframe (not implemented)
            event.accept()
        else:
            super().mousePressEvent(event)


# ============================================================================
# Enhanced InputField - Inherit from native with polish features
# ============================================================================

class EnhancedInputField(hou.qt.InputField):
    """
    Enhanced InputField with all Houdini parameter polish features:
    - Hover effects (lighter background, outline)
    - Ctrl+MMB on label to reset to default
    - LMB on label to toggle slider visibility
    - Alt+LMB for keyframes (placeholder)
    """
    
    # Signal for when user wants to reset to default
    resetRequested = QtCore.Signal()
    # Signal for when user toggles slider visibility
    sliderToggleRequested = QtCore.Signal()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Find internal widgets
        self._line_edit = self.findChild(QtWidgets.QLineEdit)
        self._label = self.findChild(QtWidgets.QLabel)
        
        # Store original background and label colors
        if self._line_edit:
            self._original_bg = self._line_edit.palette().color(QtGui.QPalette.Base)
        else:
            self._original_bg = QtGui.QColor(58, 58, 58)
        
        if self._label:
            self._original_label_color = self._label.palette().color(QtGui.QPalette.WindowText)
        else:
            self._original_label_color = QtGui.QColor(204, 204, 204)
        
        # Install event filter on label for interactions
        if self._label:
            self._label.installEventFilter(self)
            # Make label look clickable
            self._label.setCursor(QtCore.Qt.PointingHandCursor)
        
        self._is_hovered = False
        self._label_hovered = False
    
    def enterEvent(self, event):
        """Add hover glow effect."""
        self._is_hovered = True
        self._update_hover_style()
        super().enterEvent(event)
    
    def leaveEvent(self, event):
        """Remove hover glow effect."""
        self._is_hovered = False
        self._update_hover_style()
        super().leaveEvent(event)
    
    def _update_hover_style(self):
        """Apply or remove hover visual feedback."""
        if not self._line_edit:
            return
        
        pal = self._line_edit.palette()
        if self._is_hovered:
            # Lighter background on hover
            pal.setColor(QtGui.QPalette.Base, QtGui.QColor(70, 70, 70))
        else:
            # Restore original background
            pal.setColor(QtGui.QPalette.Base, self._original_bg)
        
        self._line_edit.setPalette(pal)
        
        # Update label hover state with background and outline
        if self._label:
            if self._label_hovered:
                # Houdini style: lighter background + black outline
                self._label.setStyleSheet("""
                    QLabel {
                        background-color: rgb(70, 70, 70);
                        border: 1px solid rgb(0, 0, 0);
                        padding: 1px;
                    }
                """)
            else:
                # Clear stylesheet to restore default
                self._label.setStyleSheet("")
    
    def eventFilter(self, obj, event):
        """Intercept label interactions."""
        if obj == self._label:
            # Handle hover on label
            if event.type() == QtCore.QEvent.Enter:
                self._label_hovered = True
                self._update_hover_style()
            elif event.type() == QtCore.QEvent.Leave:
                self._label_hovered = False
                self._update_hover_style()
            elif event.type() == QtCore.QEvent.MouseButtonPress:
                button = event.button()
                modifiers = event.modifiers()
                
                if button == QtCore.Qt.LeftButton and modifiers == QtCore.Qt.NoModifier:
                    # LMB: Toggle slider visibility
                    self.sliderToggleRequested.emit()
                    return True
                
                elif button == QtCore.Qt.MiddleButton and modifiers == QtCore.Qt.ControlModifier:
                    # Ctrl+MMB: Reset to default
                    self.resetRequested.emit()
                    return True
                
                elif button == QtCore.Qt.LeftButton and modifiers == QtCore.Qt.AltModifier:
                    # Alt+LMB: Add keyframe (not implemented)
                    return True
                return True
        
        return super().eventFilter(obj, event)
    
    def set_expression_color(self, color: QtGui.QColor):
        """Set background color for expression state."""
        self._original_bg = color
        if self._line_edit:
            # Apply stylesheet directly to the internal line edit
            stylesheet = f"""
                QLineEdit {{
                    background-color: rgb({color.red()},{color.green()},{color.blue()});
                    color: rgb(204,204,204);
                    border: 1px solid #3a3a3a;
                    padding: 2px;
                }}
            """
            self._line_edit.setStyleSheet(stylesheet)
            self._line_edit.update()


# ============================================================================
# Base Parameter Widget
# ============================================================================

class BaseParmWidget(QtWidgets.QWidget):
    """Base class for parameter-bound widgets."""
    
    def __init__(self, parm: Optional[hou.Parm] = None):
        super().__init__()
        self.parm = parm
        self.last_parm_value = None
        self._updating_from_parm = False
        self._showing_expression = False
        
        # Subclasses register widgets that should be disabled when expression is active
        self._value_widgets = []
        
        # Subclasses register stylesheet template with {r}, {g}, {b} placeholders
        self._stylesheet_template = ""
        
        if parm:
            self.last_parm_value = self._get_parm_value()
            
        # Enable context menu
        self.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
    
    def _get_parm_value(self):
        """Get current parameter value. Override in subclasses."""
        if self.parm:
            return self.parm.eval()
        return None
    
    def _set_parm_value(self, value):
        """Set parameter value. Override in subclasses."""
        if self.parm and not self._updating_from_parm:
            try:
                self.parm.set(value)
            except Exception as e:
                print(f"Error setting parm {self.parm.name()}: {e}")
    
    def update_from_parm(self):
        """Update widget from parameter (called by BindingManager)."""
        if not self.parm:
            return
        
        current_value = self._get_parm_value()
        if current_value != self.last_parm_value:
            self._updating_from_parm = True
            self._update_widget_value(current_value)
            self.last_parm_value = current_value
            self._updating_from_parm = False
    
    def _update_widget_value(self, value):
        """Update widget display. Override in subclasses."""
        pass
    
    def _update_expression_style(self):
        """
        Update visual feedback for expression state.
        
        This base implementation handles:
        - Getting expression state and color
        - Enabling/disabling registered value widgets
        - Applying stylesheet template with color variables
        
        Subclasses should:
        1. Populate self._value_widgets list with widgets to disable
        2. Set self._stylesheet_template with {r}, {g}, {b} placeholders
        """
        if not self.parm:
            return
        
        has_expr = parm_utils.has_expression(self.parm)
        r, g, b = parm_utils.get_parm_color(self.parm)
        
        # Enable/disable value input widgets
        for widget in self._value_widgets:
            widget.setEnabled(not has_expr)
        
        # Apply stylesheet if template is set
        if self._stylesheet_template:
            self.setStyleSheet(self._stylesheet_template.format(r=r, g=g, b=b))

    def _show_context_menu(self, pos):
        """Show Houdini-style parameter context menu."""
        if not self.parm:
            return
        
        menu = QtWidgets.QMenu(self)
        
        # Expression actions
        has_expr = parm_utils.has_expression(self.parm)
        
        if has_expr:
            action = menu.addAction("Show Value")
            action.triggered.connect(lambda: self._toggle_expression_display(False))
            
            action = menu.addAction("Edit Expression...")
            action.triggered.connect(self._edit_expression)
            
            menu.addSeparator()
            
            action = menu.addAction("Delete Channels")
            action.triggered.connect(self._delete_expression)
        else:
            action = menu.addAction("Set Expression...")
            action.triggered.connect(self._edit_expression)
        
        menu.addSeparator()
        
        # Copy/Paste
        action = menu.addAction("Copy Parameter")
        action.triggered.connect(self._copy_parameter)
        
        action = menu.addAction("Paste Copied Relative References")
        action.triggered.connect(self._paste_reference)
        
        menu.addSeparator()
        
        # Revert
        action = menu.addAction("Revert to Defaults")
        action.triggered.connect(self._revert_to_defaults)
        
        # Show menu
        menu.exec_(self.mapToGlobal(pos))
    
    def _toggle_expression_display(self, show_expr: bool):
        """Toggle between showing expression text vs evaluated value."""
        self._showing_expression = show_expr
        self.update_from_parm()
    
    def _edit_expression(self):
        """Open dialog to edit expression."""
        if not self.parm:
            return
        
        current_expr = parm_utils.get_expression_string(self.parm) or ""
        current_lang = parm_utils.get_expression_language(self.parm)
        
        dialog = ExpressionDialog(self.parm, current_expr, current_lang, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            expr, lang = dialog.get_expression()
            if expr:
                parm_utils.set_expression(self.parm, expr, lang)
            else:
                parm_utils.delete_expression(self.parm)
            # Force style update
            self._update_expression_style()
            self.update_from_parm()
    
    def _delete_expression(self):
        """Remove expression from parameter."""
        if self.parm:
            parm_utils.delete_expression(self.parm)
            # Force style update immediately
            self._update_expression_style()
            self.update_from_parm()
    
    def _copy_parameter(self):
        """Copy parameter path to clipboard."""
        if self.parm:
            parm_utils.copy_parameter(self.parm)
    
    def _paste_reference(self):
        """Paste parameter reference from clipboard."""
        if not self.parm:
            return
        
        try:
            # Use Houdini's internal parameter clipboard
            parm_utils.paste_relative_reference(self.parm)
            # Force style update
            self._update_expression_style()
            self.update_from_parm()
        except Exception as e:
            pass
    
    def _revert_to_defaults(self):
        """Revert parameter to default value."""
        if self.parm:
            parm_utils.revert_to_default(self.parm)
            self.update_from_parm()


class ExpressionDialog(QtWidgets.QDialog):
    """Dialog for editing parameter expressions."""
    
    def __init__(self, parm: hou.Parm, expression: str, language: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Edit Expression - {parm.name()}")
        self.resize(500, 300)
        
        layout = QtWidgets.QVBoxLayout()
        
        # Info label
        info = QtWidgets.QLabel(f"Parameter: {parm.path()}")
        layout.addWidget(info)
        
        # Language selector
        lang_layout = QtWidgets.QHBoxLayout()
        lang_layout.addWidget(QtWidgets.QLabel("Language:"))
        
        self.lang_combo = QtWidgets.QComboBox()
        self.lang_combo.addItems(["hscript", "python"])
        self.lang_combo.setCurrentText(language.lower())
        lang_layout.addWidget(self.lang_combo)
        lang_layout.addStretch()
        
        layout.addLayout(lang_layout)
        
        # Expression editor
        self.expr_edit = QtWidgets.QTextEdit()
        self.expr_edit.setPlainText(expression)
        self.expr_edit.setFont(QtGui.QFont("Consolas", 10))
        layout.addWidget(self.expr_edit)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        accept_btn = QtWidgets.QPushButton("Accept")
        accept_btn.clicked.connect(self.accept)
        button_layout.addWidget(accept_btn)
        
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        layout.addLayout(button_layout)
        
        self.setLayout(layout)
        
        # Style
        self.setStyleSheet("""
            QDialog {
                background: #1e1e1e;
                color: #cccccc;
            }
            QLabel { color: #cccccc; }
            QTextEdit {
                background: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #cccccc;
            }
            QPushButton {
                background: #3a3a3a;
                border: 1px solid #4a4a4a;
                color: #cccccc;
                padding: 4px 12px;
            }
            QPushButton:hover {
                background: #4a4a4a;
            }
        """)
    
    def get_expression(self):
        """Get expression and language from dialog."""
        expr = self.expr_edit.toPlainText().strip()
        lang = self.lang_combo.currentText()
        return expr, lang


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


# ============================================================================
# Other Widgets (custom implementations)
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
            except:
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
            except:
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
            except:
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
