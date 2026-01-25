"""
Asset Browser UI - Grid view of assets with search and filtering
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
import os
from typing import Optional, List, Dict


class AssetThumbnailWidget(QtWidgets.QWidget):
    """Individual asset thumbnail with turntable animation on hover"""
    
    assetClicked = QtCore.Signal(dict)  # Emits asset data
    
    def __init__(self, asset_data: Dict, parent=None):
        super().__init__(parent)
        self.asset_data = asset_data
        self.turntable_frames = []
        self.full_sequence_loaded = False  # Track if full sequence is loaded
        self.current_frame = 4  # Frame 5 (0-indexed)
        self.mouse_enter_x = 0
        self.drag_start_pos = QtCore.QPoint()
        
        self.setFixedSize(200, 240)
        self.setToolTip(f"{asset_data['name']}\n{asset_data['category']}")
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Thumbnail image
        self.thumbnail_label = QtWidgets.QLabel()
        self.thumbnail_label.setFixedSize(192, 192)
        self.thumbnail_label.setScaledContents(True)
        self.thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self.thumbnail_label.setStyleSheet("border: 1px solid palette(mid); background: palette(base);")
        
        # Enable mouse tracking for turntable animation
        self.setMouseTracking(True)
        self.thumbnail_label.setMouseTracking(True)
        
        # Load only frame 5 initially for performance
        self._load_initial_frame()
        self._display_frame(self.current_frame)
        
        layout.addWidget(self.thumbnail_label)
        
        # Asset name
        name_label = QtWidgets.QLabel(asset_data['name'])
        name_label.setWordWrap(True)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setMaximumHeight(40)
        layout.addWidget(name_label)
    
    def _load_initial_frame(self):
        """Load only frame 5 for initial display - lazy load full sequence on hover"""
        turntable_path = self.asset_data.get('thumbnail_turntable', '')
        static_path = self.asset_data.get('thumbnail_static', '')
        
        frame_loaded = False
        
        # Try to load frame 5 from turntable directory
        if turntable_path and os.path.isdir(turntable_path):
            frame_file = os.path.join(turntable_path, "frame_0005.png")
            if os.path.exists(frame_file):
                self.turntable_frames = [QtGui.QPixmap(frame_file)]
                frame_loaded = True
        
        # If no turntable frame 5, try static thumbnail
        if not frame_loaded and static_path and os.path.exists(static_path):
            self.turntable_frames = [QtGui.QPixmap(static_path)]
            frame_loaded = True
        
        if not frame_loaded:
            self.turntable_frames = []
    
    def _load_turntable_frames(self):
        """Load full turntable sequence (called on first hover)"""
        if self.full_sequence_loaded:
            return
        
        turntable_path = self.asset_data.get('thumbnail_turntable', '')
        static_path = self.asset_data.get('thumbnail_static', '')
        
        full_frames = []
        
        # Check if turntable_path is a directory containing turntable frames
        if turntable_path and os.path.isdir(turntable_path):
            # Look for frame_####.png files
            for frame in range(1, 37):
                frame_file = os.path.join(turntable_path, f"frame_{frame:04d}.png")
                if os.path.exists(frame_file):
                    full_frames.append(QtGui.QPixmap(frame_file))
        
        # If no turntable frames, check if turntable_path has $F pattern
        elif turntable_path and '$F' in turntable_path:
            import re
            
            # Extract directory and pattern
            dir_path = os.path.dirname(turntable_path)
            filename = os.path.basename(turntable_path)
            
            # Replace $F4 or similar with format string
            pattern = re.sub(r'\$F(\d+)', lambda m: '{:0' + m.group(1) + 'd}', filename)
            
            # Load frames 1-36 (typical turntable)
            for frame in range(1, 37):
                frame_file = os.path.join(dir_path, pattern.format(frame))
                if os.path.exists(frame_file):
                    full_frames.append(QtGui.QPixmap(frame_file))
        
        # Fall back to static thumbnail if no frames loaded
        if not full_frames and static_path and os.path.exists(static_path):
            full_frames = [QtGui.QPixmap(static_path)]
        
        # Update frames if we loaded a full sequence
        if len(full_frames) > 1:
            self.turntable_frames = full_frames
            self.full_sequence_loaded = True
    
    def _display_frame(self, frame_index):
        """Display a specific frame"""
        if not self.turntable_frames:
            self.thumbnail_label.setText("No Preview")
            return
        
        # Clamp frame index
        frame_index = max(0, min(frame_index, len(self.turntable_frames) - 1))
        self.thumbnail_label.setPixmap(self.turntable_frames[frame_index])
    
    def enterEvent(self, event):
        """Start turntable animation on mouse enter"""
        # Load full sequence on first hover
        if not self.full_sequence_loaded:
            self._load_turntable_frames()
        
        if len(self.turntable_frames) > 1:
            # Store mouse enter position
            self.mouse_enter_x = event.position().x()
    
    def leaveEvent(self, event):
        """Stop animation and return to frame 5"""
        self.current_frame = 4  # Frame 5 is index 4
        self._display_frame(self.current_frame)
    
    def mouseMoveEvent(self, event):
        """Update frame based on mouse X position"""
        if len(self.turntable_frames) <= 1:
            return
        
        # Map mouse X position to frame index
        widget_width = self.thumbnail_label.width()
        mouse_x = event.position().x()
        
        # Calculate frame based on position (0 to num_frames-1)
        normalized_x = max(0, min(1, mouse_x / widget_width))
        frame_index = int(normalized_x * (len(self.turntable_frames) - 1))
        
        if frame_index != self.current_frame:
            self.current_frame = frame_index
            self._display_frame(self.current_frame)
    
    def mousePressEvent(self, event):
        """Store drag start position"""
        if event.button() == QtCore.Qt.LeftButton:
            self.drag_start_pos = event.pos()
    
    def mouseReleaseEvent(self, event):
        """Handle click without drag"""
        if event.button() == QtCore.Qt.LeftButton:
            if (event.pos() - self.drag_start_pos).manhattanLength() < QtWidgets.QApplication.startDragDistance():
                # It's a click, not a drag
                pass
    
    def mouseDoubleClickEvent(self, event):
        """Emit signal on double-click"""
        if event.button() == QtCore.Qt.LeftButton:
            self.assetClicked.emit(self.asset_data)


class AssetBrowserWidget(QtWidgets.QWidget):
    """Asset browser with grid view, search, and filters"""
    
    assetSelected = QtCore.Signal(dict)  # Emits when asset is selected for placement
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_assets = []
        self.filtered_assets = []
        
        self._setup_ui()
        self._load_assets()
    
    def _setup_ui(self):
        """Create UI elements"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)
        
        # Search bar
        search_layout = QtWidgets.QHBoxLayout()
        search_layout.addWidget(QtWidgets.QLabel("Search:"))
        
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("Search by name...")
        self.search_edit.textChanged.connect(self._filter_assets)
        search_layout.addWidget(self.search_edit)
        
        layout.addLayout(search_layout)
        
        # Filter bar
        filter_layout = QtWidgets.QFormLayout()
        
        # Category filter
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.addItem("All Categories")
        self.category_combo.currentTextChanged.connect(self._filter_assets)
        filter_layout.addRow("Category:", self.category_combo)
        
        # Tag filter
        from polyfactory.widgets.tag_input import TagInputWidget
        self.tag_filter = TagInputWidget()
        self.tag_filter.tagsChanged.connect(self._filter_assets)
        filter_layout.addRow("Tags:", self.tag_filter)
        
        layout.addLayout(filter_layout)
        
        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        layout.addWidget(separator)
        
        # Scroll area for asset grid
        scroll_area = QtWidgets.QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        # Container for grid
        self.grid_container = QtWidgets.QWidget()
        self.grid_layout = QtWidgets.QGridLayout(self.grid_container)
        self.grid_layout.setSpacing(8)
        self.grid_layout.setAlignment(QtCore.Qt.AlignTop | QtCore.Qt.AlignLeft)
        
        scroll_area.setWidget(self.grid_container)
        layout.addWidget(scroll_area)
        
        # Status bar
        self.status_label = QtWidgets.QLabel("Loading assets...")
        layout.addWidget(self.status_label)
    
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
        
        # Fixed 4 columns
        columns = 4
        
        for i, asset in enumerate(self.filtered_assets):
            row = i // columns
            col = i % columns
            
            thumbnail_widget = AssetThumbnailWidget(asset)
            thumbnail_widget.assetClicked.connect(self._on_asset_double_clicked)
            self.grid_layout.addWidget(thumbnail_widget, row, col)
        
        # Update status
        count = len(self.filtered_assets)
        total = len(self.all_assets)
        self.status_label.setText(f"Showing {count} of {total} assets")
    
    def _on_asset_double_clicked(self, asset_data):
        """Handle asset double-click"""
        self.assetSelected.emit(asset_data)
    
    def resizeEvent(self, event):
        """Handle resize - grid is fixed at 4 columns so no need to recalculate"""
        super().resizeEvent(event)


class AssetBrowserDialog(QtWidgets.QDialog):
    """Standalone asset browser dialog"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Asset Browser")
        self.setMinimumSize(800, 600)
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.browser = AssetBrowserWidget()
        self.browser.assetSelected.connect(self._on_asset_selected)
        layout.addWidget(self.browser)
        
        # Close button
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        close_button = QtWidgets.QPushButton("Close")
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
