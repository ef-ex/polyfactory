"""
Widget Components - Houdini-styled Qt widgets with parameter binding

Each widget handles bidirectional sync with a Houdini parameter.
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
from typing import Optional
from . import parm_utils


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
            clipboard = QtWidgets.QApplication.clipboard()
            source_path = clipboard.text()
            if source_path:
                parm_utils.paste_relative_reference(self.parm, source_path)
                # Force style update
                self._update_expression_style()
                self.update_from_parm()
        except Exception as e:
            print(f"Error pasting reference: {e}")
    
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

class ParmFloat(BaseParmWidget):
    """
    Float parameter widget using Houdini's native InputField.
    
    Includes built-in middle-mouse ladder, Houdini styling, and expression support.
    """
    
    def __init__(self, parm: hou.Parm, label: Optional[str] = None, range: Optional[tuple] = None):
        super().__init__(parm)
        
        # Create layout
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Use Houdini's native InputField with built-in ladder
        label_text = label or parm.description()
        self.input_field = hou.qt.InputField(
            hou.qt.InputField.FloatType,
            1,  # Single component
            label=label_text
        )
        
        # Set initial value
        self.input_field.setValues([parm.eval()])
        
        # Connect to parameter
        self.input_field.valueChanged.connect(self._on_value_changed)
        
        layout.addWidget(self.input_field)
        self.setLayout(layout)
        
        # Register for expression handling
        self._value_widgets = [self.input_field]
        self._stylesheet_template = "QLineEdit {{ background-color: rgb({r},{g},{b}); }}"
        self._update_expression_style()
    
    def _on_value_changed(self):
        """Handle value change from widget."""
        if not self._updating_from_parm:
            self._set_parm_value(self.input_field.value())
    
    def _update_widget_value(self, value):
        """Update widget from parameter value."""
        self.input_field.blockSignals(True)
        self.input_field.setValues([float(value)])
        self.input_field.blockSignals(False)
        self._update_expression_style()


class ParmInt(BaseParmWidget):
    """
    Integer parameter widget using Houdini's native InputField.
    
    Includes built-in middle-mouse ladder, Houdini styling, and expression support.
    """
    
    def __init__(self, parm: hou.Parm, label: Optional[str] = None, range: Optional[tuple] = None):
        super().__init__(parm)
        
        # Create layout
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Use Houdini's native InputField with built-in ladder
        label_text = label or parm.description()
        self.input_field = hou.qt.InputField(
            hou.qt.InputField.IntegerType,
            1,  # Single component
            label=label_text
        )
        
        # Set initial value
        self.input_field.setValues([int(parm.eval())])\n        
        # Connect to parameter
        self.input_field.valueChanged.connect(self._on_value_changed)
        
        layout.addWidget(self.input_field)
        self.setLayout(layout)
        
        # Register for expression handling
        self._value_widgets = [self.input_field]
        self._stylesheet_template = "QLineEdit {{ background-color: rgb({r},{g},{b}); }}"
        self._update_expression_style()
    
    def _on_value_changed(self):
        """Handle value change from widget."""
        if not self._updating_from_parm:
            self._set_parm_value(int(self.input_field.value()))
    
    def _update_widget_value(self, value):
        """Update widget from parameter value."""
        self.input_field.blockSignals(True)
        self.input_field.setValues([int(value)])
        self.input_field.blockSignals(False)
        self._update_expression_style()



    """Float slider widget with label and middle-mouse ladder."""
    
    def __init__(
        self,
        parm: hou.Parm,
        label: Optional[str] = None,
        range: Optional[tuple] = None,
        decimals: int = 3
    ):
        super().__init__(parm)
        
        # Create layout
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Label
        label_text = label or parm.description()
        self.label = QtWidgets.QLabel(label_text)
        self.label.setMinimumWidth(100)
        layout.addWidget(self.label)
        
        # Slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimumWidth(150)
        
        # Spinbox
        self.spinbox = QtWidgets.QDoubleSpinBox()
        self.spinbox.setDecimals(decimals)
        self.spinbox.setMinimumWidth(60)
        
        # Set range
        if range:
            min_val, max_val = range
        else:
            # Try to get from parm template
            template = parm.parmTemplate()
            try:
                min_val = template.minValue() if template.minIsStrict() else 0.0
                max_val = template.maxValue() if template.maxIsStrict() else 100.0
            except (AttributeError, TypeError):
                # Fallback if template doesn't have min/max
                min_val = 0.0
                max_val = 100.0
        
        self.min_val = min_val
        self.max_val = max_val
        
        self.slider.setMinimum(0)
        self.slider.setMaximum(1000)
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        
        # Set initial value
        initial = parm.eval()
        self._update_widget_value(initial)
        
        # Connect signals
        self.slider.valueChanged.connect(self._on_slider_changed)
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        
        # Layout order: label / spinbox / slider (Houdini style)
        layout.addWidget(self.spinbox)
        layout.addWidget(self.slider, 1)
        
        self.setLayout(layout)
        
        # Register widgets for expression handling (base class uses these)
        self._value_widgets = [self.slider, self.spinbox]
        
        # Set stylesheet template with color placeholders
        self._stylesheet_template = """
            QLabel {{ color: #cccccc; }}
            QSlider::groove:horizontal {{
                border: 1px solid #3a3a3a;
                height: 4px;
                background: #2a2a2a;
            }}
            QSlider::handle:horizontal {{
                background: #5a8ab4;
                border: 1px solid #3a3a3a;
                width: 12px;
                margin: -4px 0;
                border-radius: 2px;
            }}
            QDoubleSpinBox {{
                background: rgb({r}, {g}, {b});
                border: 1px solid #3a3a3a;
                color: #cccccc;
                padding: 2px;
            }}
            QDoubleSpinBox:disabled {{
                background: rgb({r}, {g}, {b});
                color: #aaaaaa;
            }}
        """
        
        # Apply initial style
        self._update_expression_style()
        
        # Setup middle-mouse ladder
        self._setup_ladder(
            get_value_func=lambda: self.parm.eval(),
            set_value_func=lambda v: self.parm.set(v),
            value_range=(self.min_val, self.max_val),
            step_size=0.01,
            is_integer=False  # Float parameter
        )
    
    def _value_to_slider(self, value):
        """Convert float value to slider position."""
        normalized = (value - self.min_val) / (self.max_val - self.min_val)
        return int(normalized * 1000)
    
    def _slider_to_value(self, pos):
        """Convert slider position to float value."""
        normalized = pos / 1000.0
        return self.min_val + normalized * (self.max_val - self.min_val)
    
    def _on_slider_changed(self, pos):
        if self._updating_from_parm:
            return
        value = self._slider_to_value(pos)
        self.spinbox.blockSignals(True)
        self.spinbox.setValue(value)
        self.spinbox.blockSignals(False)
        self._set_parm_value(value)
    
    def _on_spinbox_changed(self, value):
        if self._updating_from_parm:
            return
        self.slider.blockSignals(True)
        self.slider.setValue(self._value_to_slider(value))
        self.slider.blockSignals(False)
        self._set_parm_value(value)
    
    def _update_widget_value(self, value):
        self.spinbox.blockSignals(True)
        self.slider.blockSignals(True)
        self.spinbox.setValue(value)
        self.slider.setValue(self._value_to_slider(value))
        self.slider.blockSignals(False)
        self.spinbox.blockSignals(False)
        
        # Update visual style based on expression state
        self._update_expression_style()



class ParmInt(LadderMixin, BaseParmWidget):
    """Integer spinbox widget with label, slider, and middle-mouse ladder."""
    
    def __init__(
        self,
        parm: hou.Parm,
        label: Optional[str] = None,
        range: Optional[tuple] = None
    ):
        super().__init__(parm)
        
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        # Label
        label_text = label or parm.description()
        self.label = QtWidgets.QLabel(label_text)
        self.label.setMinimumWidth(100)
        layout.addWidget(self.label)
        
        # Spinbox
        self.spinbox = QtWidgets.QSpinBox()
        self.spinbox.setMinimumWidth(60)
        
        # Slider
        self.slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.slider.setMinimumWidth(150)
        
        # Set range
        if range:
            min_val, max_val = range
        else:
            # Try to get from parm template
            template = parm.parmTemplate()
            try:
                min_val = int(template.minValue()) if template.minIsStrict() else 0
                max_val = int(template.maxValue()) if template.maxIsStrict() else 100
            except (AttributeError, TypeError):
                min_val = 0
                max_val = 100
        
        self.min_val = min_val
        self.max_val = max_val
        
        self.spinbox.setMinimum(min_val)
        self.spinbox.setMaximum(max_val)
        self.slider.setMinimum(min_val)
        self.slider.setMaximum(max_val)
        
        # Set initial value
        initial = int(parm.eval())
        self.spinbox.setValue(initial)
        self.slider.setValue(initial)
        
        # Connect signals
        self.spinbox.valueChanged.connect(self._on_spinbox_changed)
        self.slider.valueChanged.connect(self._on_slider_changed)
        
        # Layout order: label / spinbox / slider (Houdini style)
        layout.addWidget(self.spinbox)
        layout.addWidget(self.slider, 1)
        
        self.setLayout(layout)
        
        # Register widgets for expression handling
        self._value_widgets = [self.spinbox, self.slider]
        
        # Set stylesheet template
        self._stylesheet_template = """
            QLabel {{ color: #cccccc; }}
            QSpinBox {{
                background: rgb({r}, {g}, {b});
                border: 1px solid #3a3a3a;
                color: #cccccc;
                padding: 2px;
            }}
            QSpinBox:disabled {{
                background: rgb({r}, {g}, {b});
                color: #aaaaaa;
            }}
            QSlider::groove:horizontal {{
                border: 1px solid #3a3a3a;
                height: 4px;
                background: #2a2a2a;
            }}
            QSlider::handle:horizontal {{
                background: #5a8ab4;
                border: 1px solid #3a3a3a;
                width: 12px;
                margin: -4px 0;
                border-radius: 2px;
            }}
        """
        
        # Apply initial style
        self._update_expression_style()
        
        # Setup middle-mouse ladder
        self._setup_ladder(
            get_value_func=lambda: int(self.parm.eval()),
            set_value_func=lambda v: self.parm.set(int(v)),
            value_range=(self.min_val, self.max_val),
            step_size=0.1,  # Larger step for integers
            is_integer=True  # Integer parameter
        )
    
    def _on_spinbox_changed(self, value):
        if not self._updating_from_parm:
            self.slider.blockSignals(True)
            self.slider.setValue(value)
            self.slider.blockSignals(False)
            self._set_parm_value(value)
    
    def _on_slider_changed(self, value):
        if not self._updating_from_parm:
            self.spinbox.blockSignals(True)
            self.spinbox.setValue(value)
            self.spinbox.blockSignals(False)
            self._set_parm_value(value)
    
    def _update_widget_value(self, value):
        self.spinbox.blockSignals(True)
        self.slider.blockSignals(True)
        self.spinbox.setValue(int(value))
        self.slider.setValue(int(value))
        self.spinbox.blockSignals(False)
        self.slider.blockSignals(False)
        
        # Update expression style
        self._update_expression_style()


class ParmString(BaseParmWidget):
    """String input widget with label."""
    
    def __init__(
        self,
        parm: hou.Parm,
        label: Optional[str] = None,
        multiline: bool = False
    ):
        super().__init__(parm)
        
        layout = QtWidgets.QVBoxLayout() if multiline else QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        label_text = label or parm.description()
        self.label = QtWidgets.QLabel(label_text)
        if not multiline:
            self.label.setMinimumWidth(100)
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
            QLabel { color: #cccccc; }
            QLineEdit, QTextEdit {
                background: #2a2a2a;
                border: 1px solid #3a3a3a;
                color: #cccccc;
                padding: 2px;
            }
        """)
    
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


class ParmMenu(BaseParmWidget):
    """Dropdown menu widget."""
    
    def __init__(self, parm: hou.Parm, label: Optional[str] = None):
        super().__init__(parm)
        
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        
        label_text = label or parm.description()
        self.label = QtWidgets.QLabel(label_text)
        self.label.setMinimumWidth(100)
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
        """Menu parms can be int or string."""
        if self.parm:
            try:
                return self.parm.eval()
            except:
                return self.parm.evalAsString()
        return None
    
    def _on_changed(self, index):
        if not self._updating_from_parm:
            value = self.combo.itemData(index)
            self._set_parm_value(value)
    
    def _update_widget_value(self, value):
        self.combo.blockSignals(True)
        for i in range(self.combo.count()):
            if self.combo.itemData(i) == value:
                self.combo.setCurrentIndex(i)
                break
        self.combo.blockSignals(False)


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
