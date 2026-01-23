"""
Tag Input Widget - Autocompleting tag input with removable chips
Similar to ShotGrid's entity link field behavior
"""

from PySide6 import QtWidgets, QtCore, QtGui


class TagChip(QtWidgets.QWidget):
    """Individual tag chip with remove button"""
    
    removed = QtCore.Signal(str)  # Emits tag text when removed
    
    def __init__(self, tag_text, parent=None):
        super().__init__(parent)
        self.tag_text = tag_text
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(8)
        
        # Tag label
        self.label = QtWidgets.QLabel(tag_text)
        self.label.setStyleSheet("color: palette(highlighted-text); background: transparent; border: none;")
        self.label.setFrameStyle(QtWidgets.QFrame.NoFrame)
        layout.addWidget(self.label)
        
        # Remove button (X)
        self.remove_btn = QtWidgets.QToolButton()
        self.remove_btn.setText("×")
        self.remove_btn.setFixedSize(16, 16)
        self.remove_btn.setStyleSheet("""
            QToolButton {
                background-color: transparent;
                border: none;
                color: palette(highlighted-text);
                font-size: 16px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.3);
                border-radius: 8px;
            }
        """)
        self.remove_btn.clicked.connect(self._on_remove)
        layout.addWidget(self.remove_btn)
    
    def paintEvent(self, event):
        """Custom paint to draw rounded background"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Get colors from palette
        palette = self.palette()
        bg_color = palette.color(QtGui.QPalette.Highlight)
        
        # Draw rounded rectangle
        painter.setBrush(bg_color)
        painter.setPen(bg_color)
        painter.drawRoundedRect(self.rect(), 14, 14)
    
    def _on_remove(self):
        """Handle remove button click"""
        self.removed.emit(self.tag_text)


class TagInputWidget(QtWidgets.QWidget):
    """Tag input widget with autocomplete and chip display"""
    
    tagsChanged = QtCore.Signal(list)  # Emits list of current tags
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags = []  # Current tags
        self.available_tags = []  # Tags available for autocomplete
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Create UI elements"""
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Container for chips and input
        self.container = QtWidgets.QWidget()
        self.container.setFixedHeight(40)
        self.container.setStyleSheet("""
            QWidget {
                border: 1px solid palette(mid);
                border-radius: 3px;
            }
        """)
        
        # Set size policy to prevent vertical expansion
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Fixed)
        
        # Horizontal layout for chips (simple left-to-right)
        self.chips_layout = QtWidgets.QHBoxLayout(self.container)
        self.chips_layout.setContentsMargins(4, 4, 4, 4)
        self.chips_layout.setSpacing(4)
        
        # Line edit for typing new tags
        self.line_edit = QtWidgets.QLineEdit()
        self.line_edit.setPlaceholderText("Type to add tags...")
        self.line_edit.setFrame(False)
        self.line_edit.setMinimumWidth(150)
        self.line_edit.returnPressed.connect(self._on_return_pressed)
        self.line_edit.textChanged.connect(self._on_text_changed)
        
        # Completer for autocomplete
        self.completer = QtWidgets.QCompleter()
        self.completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.completer.setFilterMode(QtCore.Qt.MatchContains)
        self.completer.setWidget(self.line_edit)
        self.completer.activated[str].connect(self._on_completion_selected)
        self.line_edit.setCompleter(self.completer)
        
        # Dropdown button to show all tags (styled like combobox arrow)
        self.dropdown_btn = QtWidgets.QToolButton()
        self.dropdown_btn.setArrowType(QtCore.Qt.DownArrow)
        self.dropdown_btn.setFixedSize(20, 28)
        self.dropdown_btn.setToolTip("Show all available tags")
        self.dropdown_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: palette(button);
            }
            QToolButton:hover {
                background: palette(light);
            }
            QToolButton:pressed {
                background: palette(mid);
            }
        """)
        self.dropdown_btn.clicked.connect(self._show_tag_menu)
        
        # Add widgets to layout: chips, text field, stretch, then arrow at far right
        self.chips_layout.addWidget(self.line_edit)
        self.chips_layout.addStretch()
        self.chips_layout.addWidget(self.dropdown_btn)
        
        main_layout.addWidget(self.container)
    
    def setAvailableTags(self, tags):
        """Set the list of available tags for autocomplete
        
        Args:
            tags: List of tag strings
        """
        self.available_tags = sorted(set(tags))
        model = QtCore.QStringListModel(self.available_tags)
        self.completer.setModel(model)
    
    def getTags(self):
        """Get current list of tags
        
        Returns:
            List of tag strings
        """
        return self.tags.copy()
    
    def setTags(self, tags):
        """Set the current tags
        
        Args:
            tags: List of tag strings
        """
        # Clear existing chips
        self._clear_chips()
        
        # Add new tags
        for tag in tags:
            if tag and tag not in self.tags:
                self._add_chip(tag)
    
    def clearTags(self):
        """Clear all tags"""
        self._clear_chips()
    
    def _show_tag_menu(self):
        """Show dropdown menu with all available tags"""
        if not self.available_tags:
            return
        
        menu = QtWidgets.QMenu(self)
        current_tags = set(self.tags)
        
        for tag in sorted(self.available_tags):
            action = menu.addAction(tag)
            # Disable if already added
            if tag in current_tags:
                action.setEnabled(False)
                action.setIcon(self.style().standardIcon(QtWidgets.QStyle.SP_DialogApplyButton))
            action.triggered.connect(lambda checked=False, t=tag: self._add_chip(t))
        
        # Show menu below the dropdown button
        menu.exec_(self.dropdown_btn.mapToGlobal(self.dropdown_btn.rect().bottomLeft()))
    
    def _add_chip(self, tag_text):
        """Add a tag chip
        
        Args:
            tag_text: Tag string to add
        """
        tag_text = tag_text.strip()
        if not tag_text or tag_text in self.tags:
            return
        
        # Create chip
        chip = TagChip(tag_text)
        chip.removed.connect(self._on_chip_removed)
        
        # Insert before line edit (at count-2 to keep stretch at end)
        count = self.chips_layout.count()
        self.chips_layout.insertWidget(count - 2, chip)
        
        # Update tags list
        self.tags.append(tag_text)
        self.tagsChanged.emit(self.tags.copy())
    
    def _remove_chip(self, tag_text):
        """Remove a tag chip
        
        Args:
            tag_text: Tag string to remove
        """
        if tag_text not in self.tags:
            return
        
        # Find and remove chip widget
        for i in range(self.chips_layout.count()):
            item = self.chips_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, TagChip) and widget.tag_text == tag_text:
                    self.chips_layout.removeWidget(widget)
                    widget.deleteLater()
                    break
        
        # Update tags list
        self.tags.remove(tag_text)
        self.tagsChanged.emit(self.tags.copy())
    
    def _clear_chips(self):
        """Remove all chip widgets"""
        # Remove all chips (keep line edit, stretch, and dropdown button)
        while self.chips_layout.count() > 3:
            item = self.chips_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        self.tags = []
        self.tagsChanged.emit(self.tags.copy())
    
    def _on_return_pressed(self):
        """Handle return key in line edit"""
        text = self.line_edit.text().strip()
        if text:
            self._add_chip(text)
            self.line_edit.clear()
    
    def _on_completion_selected(self, text):
        """Handle autocomplete selection"""
        # Defer chip insertion to avoid conflict with completer popup closing
        QtCore.QTimer.singleShot(0, lambda: self._deferred_add_chip(text))
    
    def _deferred_add_chip(self, tag_text):
        """Add a tag chip after clearing line edit (deferred to avoid completer conflicts)"""
        self.line_edit.clear()
        self._add_chip(tag_text)
    
    def _on_text_changed(self, text):
        """Handle text change in line edit"""
        # Auto-add tag on comma or semicolon
        if ',' in text or ';' in text:
            parts = text.replace(';', ',').split(',')
            for part in parts[:-1]:
                part = part.strip()
                if part:
                    self._add_chip(part)
            # Keep the last part (after the last comma)
            self.line_edit.setText(parts[-1].strip())
    
    def _on_chip_removed(self, tag_text):
        """Handle chip removal"""
        self._remove_chip(tag_text)
