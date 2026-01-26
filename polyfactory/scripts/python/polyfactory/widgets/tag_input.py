"""
Tag Input Widget - Autocompleting tag input with removable chips
Similar to ShotGrid's entity link field behavior
"""

from PySide6 import QtWidgets, QtCore, QtGui
from .hover_outline import HoverOutlineMixin


class FlowLayout(QtWidgets.QLayout):
    """Layout that wraps widgets to multiple lines like text flow"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.item_list = []
        self.spacing_x = 4
        self.spacing_y = 4
    
    def __del__(self):
        item = self.takeAt(0)
        while item:
            item = self.takeAt(0)
    
    def addItem(self, item):
        self.item_list.append(item)
    
    def count(self):
        return len(self.item_list)
    
    def itemAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list[index]
        return None
    
    def takeAt(self, index):
        if 0 <= index < len(self.item_list):
            return self.item_list.pop(index)
        return None
    
    def expandingDirections(self):
        return QtCore.Qt.Orientation(0)
    
    def hasHeightForWidth(self):
        return True
    
    def heightForWidth(self, width):
        height = self._do_layout(QtCore.QRect(0, 0, width, 0), True)
        return height
    
    def setGeometry(self, rect):
        super().setGeometry(rect)
        self._do_layout(rect, False)
    
    def sizeHint(self):
        return self.minimumSize()
    
    def minimumSize(self):
        size = QtCore.QSize()
        for item in self.item_list:
            size = size.expandedTo(item.minimumSize())
        return size
    
    def _do_layout(self, rect, test_only):
        x = rect.x()
        y = rect.y()
        line_height = 0
        
        for item in self.item_list:
            widget = item.widget()
            space_x = self.spacing_x
            space_y = self.spacing_y
            
            next_x = x + item.sizeHint().width() + space_x
            if next_x - space_x > rect.right() and line_height > 0:
                x = rect.x()
                y = y + line_height + space_y
                next_x = x + item.sizeHint().width() + space_x
                line_height = 0
            
            if not test_only:
                item.setGeometry(QtCore.QRect(QtCore.QPoint(x, y), item.sizeHint()))
            
            x = next_x
            line_height = max(line_height, item.sizeHint().height())
        
        return y + line_height - rect.y()


class TagChip(HoverOutlineMixin, QtWidgets.QWidget):
    """Individual tag chip with remove button"""
    
    removed = QtCore.Signal(str)  # Emits tag text when removed
    
    def __init__(self, tag_text, parent=None):
        super().__init__(parent)
        self.tag_text = tag_text
        
        # Setup animated hover outline with bright blue
        self.setup_hover_outline(color="#61afef", width=2, radius=14, fade_duration=150, inset=1)
        
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(12, 6, 8, 6)
        layout.setSpacing(8)
        
        # Tag label
        self.label = QtWidgets.QLabel(tag_text)
        self.label.setStyleSheet("color: #dce1ec; background: transparent; border: none; font-size: 11px;")
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
                color: #abb2bf;
                font-size: 16px;
                font-weight: bold;
            }
            QToolButton:hover {
                background-color: rgba(255, 255, 255, 0.2);
                color: #dce1ec;
                border-radius: 8px;
            }
        """)
        self.remove_btn.clicked.connect(self._on_remove)
        layout.addWidget(self.remove_btn)
    
    def paintEvent(self, event):
        """Custom paint to draw rounded background with darker blue + animated hover outline"""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Darker blue background (pressed state color)
        bg_color = QtGui.QColor("#3f6fd1")
        
        # Draw rounded rectangle background
        painter.setBrush(bg_color)
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(self.rect(), 14, 14)
        
        # Draw animated hover outline on top
        self.paint_hover_outline(painter)
    
    def _on_remove(self):
        """Handle remove button click"""
        self.removed.emit(self.tag_text)


class TagInputWidget(HoverOutlineMixin, QtWidgets.QWidget):
    """Tag input widget with autocomplete and chip display"""
    
    tagsChanged = QtCore.Signal(list)  # Emits list of current tags
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.tags = []  # Current tags
        self.available_tags = []  # Tags available for autocomplete
        
        # Setup animated hover outline
        self.setup_hover_outline(color="#61afef", width=1, radius=3, fade_duration=150, inset=0)
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Create UI elements"""
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Container for chips and input
        self.container = QtWidgets.QWidget()
        self.container.setMinimumHeight(40)  # Minimum height, can expand
        self.container.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        self.container.setStyleSheet("""
            QWidget {
                border: 1px solid palette(mid);
                border-radius: 3px;
            }
        """)
        
        # Set size policy to allow vertical expansion with tags
        self.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Preferred)
        
        # Flow layout for chips (wraps to multiple lines)
        self.chips_layout = FlowLayout(self.container)
        self.chips_layout.spacing_x = 4
        self.chips_layout.spacing_y = 4
        
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
        
        # Add input and dropdown at the end (no stretch needed with flow layout)
        self.chips_layout.addWidget(self.line_edit)
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
        
        # Get the index of the line edit (last widget before dropdown)
        line_edit_index = -1
        for i in range(self.chips_layout.count()):
            item = self.chips_layout.itemAt(i)
            if item and item.widget() == self.line_edit:
                line_edit_index = i
                break
        
        # Insert chip before line edit
        if line_edit_index >= 0:
            # Remove line edit and dropdown temporarily
            self.chips_layout.takeAt(line_edit_index + 1)  # Remove dropdown
            self.chips_layout.takeAt(line_edit_index)  # Remove line edit
            
            # Add chip
            self.chips_layout.addWidget(chip)
            
            # Re-add line edit and dropdown
            self.chips_layout.addWidget(self.line_edit)
            self.chips_layout.addWidget(self.dropdown_btn)
        else:
            # Fallback: just add the chip
            self.chips_layout.addWidget(chip)
        
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
        # Remove all chips (keep line edit and dropdown button which are the last 2 items)
        while self.chips_layout.count() > 2:
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
    
    def paintEvent(self, event):
        """Paint widget with animated hover outline"""
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.paint_hover_outline(painter)
