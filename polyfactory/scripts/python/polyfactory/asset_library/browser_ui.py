"""
Asset Browser UI - Grid view of assets with search and filtering
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
import os
from typing import Optional, List, Dict
from polyfactory.ui_framework.widgets.py_push_button import PyPushButton
from polyfactory.ui_framework.widgets.py_line_edit import PyLineEdit
from polyfactory.widgets.tag_input import FlowLayout
from polyfactory.widgets.hover_outline import HoverOutlineMixin


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
        self.setMaximumWidth(320)
        
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
        title_label.setStyleSheet("""
            color: #61afef;
            font-size: 14px;
            font-weight: bold;
            padding-bottom: 8px;
        """)
        layout.addWidget(title_label)
        
        # Large preview image with animation support
        self.preview_label = QtWidgets.QLabel()
        self.preview_label.setFixedSize(280, 280)
        self.preview_label.setScaledContents(True)
        self.preview_label.setAlignment(QtCore.Qt.AlignCenter)
        self.preview_label.setStyleSheet("""
            border: 1px solid #3a3a3a;
            background: #2c2c2c;
            border-radius: 4px;
        """)
        self.preview_label.setMouseTracking(True)
        layout.addWidget(self.preview_label)
        
        # Content area (no scroll)
        content_layout = QtWidgets.QFormLayout()
        content_layout.setVerticalSpacing(10)
        content_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        
        # Asset name (read-only)
        self.name_label = QtWidgets.QLabel("—")
        self.name_label.setWordWrap(True)
        self.name_label.setStyleSheet("color: #dce1ec; font-weight: bold;")
        content_layout.addRow(self._create_label("Name:"), self.name_label)
        
        # File path (read-only)
        self.path_label = QtWidgets.QLabel("—")
        self.path_label.setWordWrap(True)
        self.path_label.setStyleSheet("""
            color: #abb2bf;
            font-family: 'Consolas', 'Courier New', monospace;
            font-size: 10px;
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
        
        layout.addLayout(content_layout)
        layout.addStretch()
        
        # Placeholder message when no asset selected
        self.placeholder_label = QtWidgets.QLabel("Select an asset to view details")
        self.placeholder_label.setAlignment(QtCore.Qt.AlignCenter)
        self.placeholder_label.setStyleSheet("color: #4f5b6e; font-style: italic;")
        layout.addWidget(self.placeholder_label)
        
        # Initially hide content, show placeholder
        self.preview_label.hide()
        title_label.hide()
    
    def _create_label(self, text):
        """Create styled label for form"""
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("color: #abb2bf; font-size: 11px;")
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
    
    assetClicked = QtCore.Signal(dict)  # Emits asset data
    
    def __init__(self, asset_data: Dict, size=150, parent=None):
        super().__init__(parent)
        self.asset_data = asset_data
        self._size = size
        
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
        name_label.setStyleSheet("color: #abb2bf; font-size: 11px;")
        layout.addWidget(name_label)
    
    def set_size(self, size):
        """Update thumbnail size dynamically"""
        self._size = size
        self.setFixedSize(size, int(size * 1.2))
        thumb_size = size - 8
        self.thumbnail_label.setFixedSize(thumb_size, thumb_size)
        self._load_static_frame()  # Reload with new size
    
    def paintEvent(self, event):
        """Draw widget with animated hover outline"""
        super().paintEvent(event)
        
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
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
        """Handle click"""
        if event.button() == QtCore.Qt.LeftButton:
            # Single click - emit for info panel
            self.assetClicked.emit(self.asset_data)


class AssetBrowserWidget(QtWidgets.QWidget):
    """Asset browser with grid view, search, and filters"""
    
    assetSelected = QtCore.Signal(dict)  # Emits when asset is selected for placement
    assetInfoChanged = QtCore.Signal(dict)  # Emits when asset is clicked for info display
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_assets = []
        self.filtered_assets = []
        self.selected_asset = None  # Track selected asset
        
        self._setup_ui()
        self._load_assets()
    
    def _setup_ui(self):
        """Create UI elements"""
        # Main horizontal layout: browser on left, info panel on right
        main_layout = QtWidgets.QHBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # Left side - browser
        browser_widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(browser_widget)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(12)
        
        # Search bar
        search_layout = QtWidgets.QHBoxLayout()
        search_label = QtWidgets.QLabel("Search:")
        search_label.setStyleSheet("color: #abb2bf; font-weight: bold;")
        search_layout.addWidget(search_label)
        
        self.search_edit = PyLineEdit()
        self.search_edit.setPlaceholderText("Search by name...")
        self.search_edit.textChanged.connect(self._filter_assets)
        search_layout.addWidget(self.search_edit)
        
        layout.addLayout(search_layout)
        
        # Size slider
        size_layout = QtWidgets.QHBoxLayout()
        size_label = QtWidgets.QLabel("Thumbnail Size:")
        size_label.setStyleSheet("color: #abb2bf; font-weight: bold;")
        size_layout.addWidget(size_label)
        
        self.size_slider = HoverSlider(QtCore.Qt.Horizontal)
        self.size_slider.setMinimum(100)
        self.size_slider.setMaximum(300)
        self.size_slider.setValue(150)
        self.size_slider.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.size_slider.setTickInterval(50)
        self.size_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                background: #2c2c2c;
                height: 6px;
                border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #61afef;
                width: 16px;
                height: 16px;
                margin: -5px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #6c99f4;
            }
        """)
        self.size_slider.valueChanged.connect(self._on_size_changed)
        size_layout.addWidget(self.size_slider)
        
        self.size_value_label = QtWidgets.QLabel("150px")
        self.size_value_label.setStyleSheet("color: #abb2bf; min-width: 50px;")
        size_layout.addWidget(self.size_value_label)
        
        layout.addLayout(size_layout)
        
        # Filter bar
        filter_layout = QtWidgets.QFormLayout()
        filter_layout.setVerticalSpacing(8)
        
        # Category filter
        self.category_combo = HoverComboBox()
        self.category_combo.addItem("All Categories")
        self.category_combo.currentTextChanged.connect(self._filter_assets)
        self.category_combo.setStyleSheet("""
            QComboBox {
                background-color: #2c2c2c;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px;
                color: #e0e0e0;
            }
            QComboBox:hover {
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
        
        category_label = QtWidgets.QLabel("Category:")
        category_label.setStyleSheet("color: #abb2bf;")
        filter_layout.addRow(category_label, self.category_combo)
        
        # Tag filter
        from polyfactory.widgets.tag_input import TagInputWidget
        self.tag_filter = TagInputWidget()
        self.tag_filter.tagsChanged.connect(self._filter_assets)
        
        tags_label = QtWidgets.QLabel("Tags:")
        tags_label.setStyleSheet("color: #abb2bf;")
        filter_layout.addRow(tags_label, self.tag_filter)
        
        layout.addLayout(filter_layout)
        
        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        separator.setStyleSheet("background-color: #3a3a3a;")
        layout.addWidget(separator)
        
        # Scroll area for asset grid
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        scroll_area.setStyleSheet("""
            QScrollArea {
                background-color: #1e1e1e;
                border: none;
            }
            QScrollBar:vertical {
                background-color: #2c2c2c;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background-color: #61afef;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #6c99f4;
            }
        """)
        
        # Container for flow layout
        self.grid_container = QtWidgets.QWidget()
        self.grid_layout = FlowLayout(self.grid_container)
        self.grid_layout.spacing_x = 8
        self.grid_layout.spacing_y = 8
        
        scroll_area.setWidget(self.grid_container)
        layout.addWidget(scroll_area)
        
        # Status bar
        self.status_label = QtWidgets.QLabel("Loading assets...")
        self.status_label.setStyleSheet("""
            color: #abb2bf;
            padding: 4px;
            background-color: #252525;
            border-radius: 4px;
        """)
        layout.addWidget(self.status_label)
        
        # Add browser to main layout
        main_layout.addWidget(browser_widget, stretch=1)
        
        # Vertical separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.VLine)
        separator.setStyleSheet("background-color: #3a3a3a;")
        separator.setFixedWidth(1)
        main_layout.addWidget(separator)
        
        # Right side - info panel
        self.info_panel = AssetInfoPanel()
        self.info_panel.categoryChanged.connect(self._on_asset_category_changed)
        self.info_panel.tagsChanged.connect(self._on_asset_tags_changed)
        self.info_panel.setStyleSheet("background-color: #252525;")
        main_layout.addWidget(self.info_panel)
    
    def _load_assets(self):
        """Load assets from database"""
        try:
            from polyfactory.asset_library.database import AssetDatabase
            
            library_path = os.environ.get('PF_ASSET_LIBRARY', '')
            if not library_path:
                self.status_label.setText("PF_ASSET_LIBRARY not set")
                return
            
            db_path = os.environ.get('PF_ASSET_DB', '')
            if not db_path:
                db_path = os.path.join(library_path, 'asset_library.db')
            elif not db_path.endswith('.db'):
                db_path = os.path.join(db_path, 'asset_library.db')
            
            if not os.path.exists(db_path):
                self.status_label.setText("Asset database not found")
                return
            
            with AssetDatabase(db_path) as db:
                    # Load categories
                    categories = sorted(set(asset['category'] for asset in db.search_assets()))
                    self.category_combo.addItems(categories)
                    
                    # Load all tags for filter
                    all_tags = db.get_all_tags()
                    self.tag_filter.setAvailableTags(all_tags)
                    
                    # Load assets
                    self.all_assets = db.search_assets()
            self._filter_assets()
            
        except Exception as e:
            self.status_label.setText(f"Error loading assets: {e}")
    
    def _filter_assets(self):
        """Filter assets based on search, category, and tags"""
        search_text = self.search_edit.text().lower()
        selected_category = self.category_combo.currentText()
        filter_tags = set(self.tag_filter.getTags())
        
        self.filtered_assets = []
        for asset in self.all_assets:
            # Category filter
            if selected_category != "All Categories" and asset['category'] != selected_category:
                continue
            
            # Search filter (name only)
            if search_text and search_text not in asset['name'].lower():
                continue
            
            # Tag filter (all selected tags must match)
            if filter_tags:
                asset_tags = set(asset.get('tags', []))
                if not filter_tags.issubset(asset_tags):
                    continue
            
            self.filtered_assets.append(asset)
        
        self._update_grid()
    
    def _update_grid(self):
        """Update grid with filtered assets"""
        # Clear existing widgets
        while self.grid_layout.count():
            item = self.grid_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Get current size from slider
        size = self.size_slider.value()
        
        # Add all thumbnails to flow layout (wraps automatically)
        for asset in self.filtered_assets:
            thumbnail_widget = AssetThumbnailWidget(asset, size=size)
            thumbnail_widget.assetClicked.connect(self._on_asset_clicked)
            self.grid_layout.addWidget(thumbnail_widget)
        
        # Update status
        count = len(self.filtered_assets)
        total = len(self.all_assets)
        self.status_label.setText(f"Showing {count} of {total} assets")
    
    def _on_asset_clicked(self, asset_data):
        """Handle asset single-click - show in info panel"""
        self.selected_asset = asset_data
        self.info_panel.set_asset(asset_data)
        self.assetInfoChanged.emit(asset_data)
    
    def _on_asset_double_clicked(self, asset_data):
        """Handle asset double-click - trigger placement"""
        self.assetSelected.emit(asset_data)
    
    def _on_asset_category_changed(self, asset_path, new_category):
        """Handle category change from info panel"""
        try:
            from polyfactory.asset_library.database import AssetDatabase
            
            db_path = os.environ.get('PF_ASSET_DB', '')
            if not db_path:
                library_path = os.environ.get('PF_ASSET_LIBRARY', '')
                db_path = os.path.join(library_path, 'asset_library.db')
            
            with AssetDatabase(db_path) as db:
                db.update_asset_category(asset_path, new_category)
            
            # Reload assets to reflect changes
            self._load_assets()
            
            hou.ui.displayMessage(f"Category updated to: {new_category}", severity=hou.severityType.Message)
        except Exception as e:
            hou.ui.displayMessage(f"Error updating category: {e}", severity=hou.severityType.Error)
    
    def _on_asset_tags_changed(self, asset_path, new_tags):
        """Handle tags change from info panel"""
        try:
            from polyfactory.asset_library.database import AssetDatabase
            
            db_path = os.environ.get('PF_ASSET_DB', '')
            if not db_path:
                library_path = os.environ.get('PF_ASSET_LIBRARY', '')
                db_path = os.path.join(library_path, 'asset_library.db')
            
            with AssetDatabase(db_path) as db:
                db.update_asset_tags(asset_path, new_tags)
            
            # Reload assets to reflect changes
            self._load_assets()
            
            hou.ui.displayMessage(f"Tags updated", severity=hou.severityType.Message)
        except Exception as e:
            hou.ui.displayMessage(f"Error updating tags: {e}", severity=hou.severityType.Error)
    
    def _on_size_changed(self, value):
        """Handle thumbnail size slider change"""
        self.size_value_label.setText(f"{value}px")
        
        # Update all existing thumbnails
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, AssetThumbnailWidget):
                    widget.set_size(value)
        
        # Force layout recalculation
        self.grid_container.updateGeometry()
    
    def resizeEvent(self, event):
        """Handle resize - flow layout will automatically reflow"""
        super().resizeEvent(event)


class AssetBrowserDialog(QtWidgets.QDialog):
    """Standalone asset browser dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Asset Browser")
        self.resize(1100, 700)
        self.setMinimumSize(800, 600)
        
        # Apply PyOneDark styling to dialog
        self.setStyleSheet("""
            QDialog {
                background-color: #1e1e1e;
                color: #e0e0e0;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.browser = AssetBrowserWidget()
        self.browser.assetSelected.connect(self._on_asset_selected)
        layout.addWidget(self.browser)
        
        # Close button
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setContentsMargins(16, 8, 16, 16)
        button_layout.addStretch()
        
        close_button = PyPushButton(
            text="Close",
            radius=8,
            color="#abb2bf",
            bg_color="#2c2c2c",
            bg_color_hover="#3a3a3a",
            bg_color_pressed="#4a4a4a"
        )
        close_button.setMinimumHeight(40)
        close_button.setMinimumWidth(120)
        close_button.clicked.connect(self.accept)
        button_layout.addWidget(close_button)
        
        layout.addLayout(button_layout)
    
    def _on_asset_selected(self, asset_data):
        """Handle asset selection - trigger viewport placement"""
        import json
        
        # Get the scene viewer
        scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if not scene_viewer:
            hou.ui.displayMessage("No scene viewer found", severity=hou.severityType.Warning)
            return
        
        # Activate the kitbash placement state
        try:
            # Pass asset data to the state
            state_parms = {"asset_data": json.dumps(asset_data)}
            scene_viewer.enterViewerState("polyfactory.kitbash_placement", state_parms)
            
            print(f"Entering placement mode for: {asset_data['name']}")
            
            # Optionally close the dialog
            # self.accept()
            
        except Exception as e:
            hou.ui.displayMessage(f"Error activating placement state: {e}", severity=hou.severityType.Error)
            print(f"Error: {e}")


def show_asset_browser():
    """Show the asset browser dialog"""
    dialog = AssetBrowserDialog(hou.qt.mainWindow())
    dialog.show()
