"""
Base Parameter Widgets - Label, InputField, BaseParmWidget, ExpressionDialog

Foundational classes shared by all parameter-bound widgets.
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
