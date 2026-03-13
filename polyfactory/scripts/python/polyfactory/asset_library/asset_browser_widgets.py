"""
Asset Browser Widgets - Low-level widget classes extracted from browser_ui.py.

Contains:
    HoverSlider         - QSlider with animated hover outline
    HoverComboBox       - QComboBox with animated hover outline
    AssetInfoPanel      - Right-hand details / edit panel for a selected asset
    AssetThumbnailWidget - Individual asset thumbnail in the grid
"""

from PySide6 import QtWidgets, QtCore, QtGui
import os
from typing import Optional, Dict

from polyfactory.ui_framework.widgets.py_push_button import PyPushButton
from polyfactory.widgets.hover_outline import HoverOutlineMixin
from polyfactory.ui_utils import get_scaled_font_size, get_font_stylesheet


class HoverSlider(HoverOutlineMixin, QtWidgets.QSlider):
    """QSlider with animated hover outline"""
    def __init__(self, orientation, parent=None):
        super().__init__(orientation, parent)
        self.setup_hover_outline(color="#61afef", width=1, radius=3, fade_duration=150, inset=0)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.paint_hover_outline(painter)


class HoverComboBox(HoverOutlineMixin, QtWidgets.QComboBox):
    """QComboBox with animated hover outline"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_hover_outline(color="#61afef", width=1, radius=4, fade_duration=150, inset=0)

    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.paint_hover_outline(painter)


class AssetInfoPanel(QtWidgets.QWidget):
    """Info panel displaying selected asset details with editable fields"""

    categoryChanged = QtCore.Signal(str, str)  # asset_path, new_category
    tagsChanged = QtCore.Signal(str, list)  # asset_path, new_tags

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_asset = None
        self.turntable_frames = []
        self.current_frame = 0
        self.full_sequence_loaded = False
        self.mouse_enter_x = 0

        self.setMinimumWidth(280)
        # No maximum width - allow resizing via splitter

        # Enable mouse tracking for turntable animation
        self.setMouseTracking(True)

        self._setup_ui()

    def _setup_ui(self):
        """Create info panel UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        # Title
        title_label = QtWidgets.QLabel("Asset Information")
        title_font_size = get_scaled_font_size(13)
        title_label.setStyleSheet(f"""
            color: #61afef;
            font-size: {title_font_size}px;
            font-weight: bold;
            padding-bottom: 8px;
        """)
        layout.addWidget(title_label)

        # Large preview image with animation support (responsive sizing)
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setMinimumSize(280, 280)
        self.preview_label.setMaximumSize(512, 512)
        self.preview_label.setScaledContents(True)
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            border: 1px solid #3a3a3a;
            background: #2c2c2c;
            border-radius: 4px;
        """)
        self.preview_label.setMouseTracking(True)
        # Make it square - height follows width
        self.preview_label.setSizePolicy(
            QtWidgets.QSizePolicy.Expanding,
            QtWidgets.QSizePolicy.Fixed
        )
        layout.addWidget(self.preview_label)

        # Scroll area for content
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2c2c2c;
                width: 8px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background-color: #61afef;
                border-radius: 4px;
                min-height: 20px;
            }
        """)

        # Content widget
        content_widget = QtWidgets.QWidget()
        scroll_area.setWidget(content_widget)

        # Content area
        content_layout = QtWidgets.QFormLayout(content_widget)
        content_layout.setVerticalSpacing(10)
        content_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        content_layout.setContentsMargins(0, 8, 0, 8)

        # Asset name (read-only)
        self.name_label = QtWidgets.QLabel("—")
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("color: #dce1ec; font-weight: bold;")
        content_layout.addRow(self._create_label("Name:"), self.name_label)

        # File path (read-only)
        self.path_label = QtWidgets.QLabel("—")
        self.path_label.setWordWrap(True)
        path_font_size = get_scaled_font_size(9)
        self.path_label.setStyleSheet(f"""
            color: #abb2bf;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: {path_font_size}px;
        """)
        content_layout.addRow(self._create_label("Path:"), self.path_label)

        # Polycount (read-only)
        self.polycount_label = QtWidgets.QLabel("—")
        self.polycount_label.setStyleSheet("color: #abb2bf;")
        content_layout.addRow(self._create_label("Polycount:"), self.polycount_label)

        # Category (editable)
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.setStyleSheet("""
            QComboBox {
                background-color: #2c2c2c;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px;
                color: #e0e0e0;
            }
            QComboBox:focus {
                border: 1px solid #61afef;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #abb2bf;
                margin-right: 6px;
            }
        """)
        self.category_combo.currentTextChanged.connect(self._on_category_changed)
        content_layout.addRow(self._create_label("Category:"), self.category_combo)

        # Tags (editable)
        from polyfactory.widgets.tag_input import TagInputWidget
        self.tags_widget = TagInputWidget()
        self.tags_widget.tagsChanged.connect(self._on_tags_changed)
        content_layout.addRow(self._create_label("Tags:"), self.tags_widget)

        # Save button
        self.save_button = PyPushButton(
            text="Save Changes",
            radius=6,
            color="#61afef",
            bg_color="#2c2c2c",
            bg_color_hover="#3a5f7d",
            bg_color_pressed="#4a6f8d"
        )
        self.save_button.setMinimumHeight(36)
        self.save_button.clicked.connect(self._save_changes)
        self.save_button.setEnabled(False)
        content_layout.addRow("", self.save_button)

        # Add scroll area to main layout
        layout.addWidget(scroll_area, stretch=1)

        # Placeholder message when no asset selected
        self.placeholder_label = QtWidgets.QLabel("Select an asset to view details")
        self.placeholder_label.setAlignment(QtCore.Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #4f5b6e; font-style: italic;")
        layout.addWidget(self.placeholder_label)

        # Initially hide content, show placeholder
        self.preview_label.hide()
        title_label.hide()

    def resizeEvent(self, event):
        """Handle resize to update preview image size"""
        super().resizeEvent(event)

        # Calculate preview size (square, based on panel width with padding)
        panel_width = self.width() - 24  # Subtract margins
        preview_size = max(280, min(512, panel_width))  # Clamp between 280 and 512

        # Update preview label size (square)
        self.preview_label.setFixedSize(preview_size, preview_size)

    def _create_label(self, text):
        """Create styled label for form"""
        label = QtWidgets.QLabel(text)
        label.setStyleSheet(get_font_stylesheet(size=11, color="#abb2bf"))
        return label

    def _load_turntable_frames(self, asset_data: Dict):
        """Load turntable frames for animation"""
        if self.full_sequence_loaded:
            return

        turntable_path = asset_data.get('thumbnail_turntable', '')
        static_path = asset_data.get('thumbnail_static', '')

        full_frames = []

        if turntable_path and os.path.isdir(turntable_path):
            for frame in range(1, 37):
                frame_file = os.path.join(turntable_path, f"frame_{frame:04d}.png")
                if os.path.exists(frame_file):
                    full_frames.append(QtGui.QPixmap(frame_file))

        if not full_frames and static_path and os.path.exists(static_path):
            full_frames = [QtGui.QPixmap(static_path)]

        if len(full_frames) > 1:
            self.turntable_frames = full_frames
            self.full_sequence_loaded = True
        else:
            self.turntable_frames = full_frames

    def _display_frame(self, frame_index):
        """Display a specific frame"""
        if not self.turntable_frames:
            self.preview_label.setText("No Preview")
            return

        frame_index = max(0, min(frame_index, len(self.turntable_frames) - 1))
        self.preview_label.setPixmap(self.turntable_frames[frame_index])

    def set_asset(self, asset_data: Dict):
        """Display asset information"""
        self.current_asset = asset_data
        self.full_sequence_loaded = False
        self.current_frame = 4  # Frame 5

        # Show content, hide placeholder
        self.layout().itemAt(0).widget().show()  # title
        self.preview_label.show()
        self.placeholder_label.hide()

        # Load initial frame 5
        turntable_path = asset_data.get('thumbnail_turntable', '')
        static_path = asset_data.get('thumbnail_static', '')

        if turntable_path and os.path.isdir(turntable_path):
            frame_file = os.path.join(turntable_path, "frame_0005.png")
            if os.path.exists(frame_file):
                self.turntable_frames = [QtGui.QPixmap(frame_file)]
                self._display_frame(0)
            elif static_path and os.path.exists(static_path):
                self.turntable_frames = [QtGui.QPixmap(static_path)]
                self._display_frame(0)
        elif static_path and os.path.exists(static_path):
            self.turntable_frames = [QtGui.QPixmap(static_path)]
            self._display_frame(0)
        else:
            self.turntable_frames = []
            self.preview_label.setText("No Preview")

        # Populate fields
        self.name_label.setText(asset_data.get('name', '—'))
        self.path_label.setText(asset_data.get('file_path', '—'))

        polycount = asset_data.get('polycount', 0)
        if polycount > 0:
            self.polycount_label.setText(f"{polycount:,}")
        else:
            self.polycount_label.setText("—")

        # Category (populate combo if needed)
        category = asset_data.get('category', '')
        if self.category_combo.findText(category) == -1 and category:
            self.category_combo.addItem(category)
        self.category_combo.setCurrentText(category)

        # Tags
        tags = asset_data.get('tags', [])
        self.tags_widget.setTags(tags)

        self.save_button.setEnabled(False)

    def enterEvent(self, event):
        """Load full turntable sequence on hover"""
        if self.current_asset and not self.full_sequence_loaded:
            self._load_turntable_frames(self.current_asset)

        if len(self.turntable_frames) > 1:
            self.mouse_enter_x = event.position().x()

    def leaveEvent(self, event):
        """Return to frame 5 on leave"""
        self.current_frame = 4
        self._display_frame(self.current_frame)

    def mouseMoveEvent(self, event):
        """Update frame based on mouse X position"""
        if len(self.turntable_frames) <= 1:
            return

        # Map mouse X to frame (0 to len-1)
        width = self.width()
        if width > 0:
            frame = int((event.position().x() / width) * len(self.turntable_frames))
            frame = max(0, min(frame, len(self.turntable_frames) - 1))

            if frame != self.current_frame:
                self.current_frame = frame
                self._display_frame(self.current_frame)

    def clear(self):
        """Clear the info panel"""
        self.current_asset = None
        self.turntable_frames = []
        self.full_sequence_loaded = False

        # Hide content, show placeholder
        self.layout().itemAt(0).widget().hide()
        self.preview_label.hide()
        self.preview_label.clear()
        self.placeholder_label.show()

    def _on_category_changed(self):
        """Mark as modified when category changes"""
        if self.current_asset:
            self.save_button.setEnabled(True)

    def _on_tags_changed(self):
        """Mark as modified when tags change"""
        if self.current_asset:
            self.save_button.setEnabled(True)

    def _save_changes(self):
        """Save category and tag changes"""
        if not self.current_asset:
            return

        asset_path = self.current_asset.get('file_path', '')
        new_category = self.category_combo.currentText().strip()
        new_tags = self.tags_widget.getTags()

        # Emit signals for parent to handle
        self.categoryChanged.emit(asset_path, new_category)
        self.tagsChanged.emit(asset_path, new_tags)

        self.save_button.setEnabled(False)


class AssetThumbnailWidget(HoverOutlineMixin, QtWidgets.QWidget):
    """Individual asset thumbnail with animated hover outline"""

    assetClicked = QtCore.Signal(dict)  # Emits asset data on single-click
    assetDoubleClicked = QtCore.Signal(dict)  # Emits asset data on double-click

    def __init__(self, asset_data: Dict, size=150, parent=None):
        super().__init__(parent)
        self.asset_data = asset_data
        self._size = size
        self._is_selected: bool = False

        # Setup animated hover outline
        self.setup_hover_outline(color="#61afef", width=2, radius=6, fade_duration=150)

        self.setFixedSize(size, int(size * 1.2))  # 1.2 aspect ratio
        self.setToolTip(f"{asset_data['name']}\n{asset_data['category']}")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Thumbnail image - fixed size based on widget size
        thumb_size = size - 8
        self.thumbnail_label = QtWidgets.QLabel()
        self.thumbnail_label.setFixedSize(thumb_size, thumb_size)
        self.thumbnail_label.setScaledContents(True)
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("""
            border: 1px solid #3a3a3a;
            background: #2c2c2c;
            border-radius: 4px;
        """)

        # Load only frame 5 - no animation on thumbnails
        self._load_static_frame()

        layout.addWidget(self.thumbnail_label)

        # Asset name
        name_label = QtWidgets.QLabel(asset_data['name'])
        name_label.setWordWrap(True)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setMaximumHeight(40)
        name_label.setStyleSheet(get_font_stylesheet(size=11, color="#abb2bf"))
        layout.addWidget(name_label)

    def set_size(self, size):
        """Update thumbnail size dynamically"""
        self._size = size
        self.setFixedSize(size, int(size * 1.2))
        thumb_size = size - 8
        self.thumbnail_label.setFixedSize(thumb_size, thumb_size)
        self._load_static_frame()  # Reload with new size

    def set_selected(self, selected: bool) -> None:
        """Toggle selection highlight on this thumbnail."""
        self._is_selected = selected
        self.update()

    def paintEvent(self, event):
        """Draw widget with selection highlight and animated hover outline."""
        super().paintEvent(event)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        if self._is_selected:
            # Semi-transparent blue fill
            painter.fillRect(self.rect(), QtGui.QColor(97, 175, 239, 50))
            # Solid blue border
            pen = QtGui.QPen(QtGui.QColor("#61afef"), 2)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRoundedRect(self.rect().adjusted(1, 1, -1, -1), 6, 6)
        else:
            self.paint_hover_outline(painter)

    def _load_static_frame(self):
        """Load only frame 5 for static display (no animation)"""
        turntable_path = self.asset_data.get('thumbnail_turntable', '')
        static_path = self.asset_data.get('thumbnail_static', '')

        pixmap = None

        # Try to load frame 5 from turntable directory
        if turntable_path and os.path.isdir(turntable_path):
            frame_file = os.path.join(turntable_path, "frame_0005.png")
            if os.path.exists(frame_file):
                pixmap = QtGui.QPixmap(frame_file)

        # Fall back to static thumbnail
        if not pixmap and static_path and os.path.exists(static_path):
            pixmap = QtGui.QPixmap(static_path)

        if pixmap:
            self.thumbnail_label.setPixmap(pixmap)
        else:
            self.thumbnail_label.setText("No Preview")

    def mousePressEvent(self, event):
        """Handle single-click"""
        if event.button() == QtCore.Qt.LeftButton:
            # Single click - emit for info panel
            self.assetClicked.emit(self.asset_data)

    def mouseDoubleClickEvent(self, event):
        """Handle double-click"""
        if event.button() == QtCore.Qt.LeftButton:
            # Double-click - emit for placement
            self.assetDoubleClicked.emit(self.asset_data)
