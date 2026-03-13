"""
Asset Browser UI - Grid view of assets with search and filtering
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
import os
import shutil
from typing import Optional, List, Dict
from polyfactory.ui_framework.widgets.py_push_button import PyPushButton
from polyfactory.ui_framework.widgets.py_line_edit import PyLineEdit
from polyfactory.widgets.tag_input import FlowLayout
from polyfactory.ui_utils import get_scaled_font_size
from polyfactory.asset_library.asset_browser_widgets import (
    HoverSlider, HoverComboBox, AssetInfoPanel, AssetThumbnailWidget,
)


class AssetBrowserWidget(QtWidgets.QWidget):
    """Asset browser with grid view, search, and filters"""
    
    assetSelected = QtCore.Signal(dict)  # Emits when asset is selected for placement
    assetInfoChanged = QtCore.Signal(dict)  # Emits when asset is clicked for info display
    
    def __init__(self, show_info_panel=True, parent=None):
        super().__init__(parent)
        self.all_assets = []
        self.filtered_assets = []
        self.selected_assets: List[Dict] = []   # multi-select list
        self._thumbnail_widgets: List[AssetThumbnailWidget] = []
        self.show_info_panel = show_info_panel
        
        self._setup_ui()
        
        # Delete key removes selected assets from the library
        delete_shortcut = QtGui.QShortcut(QtGui.QKeySequence.Delete, self)
        delete_shortcut.activated.connect(self._delete_selected_assets)
        
        self._load_assets()
    
    def _setup_ui(self):
        """Create UI elements"""
        # Main layout
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Splitter for resizable panels
        self.splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.splitter.setHandleWidth(4)
        self.splitter.setStyleSheet("""
            QSplitter::handle {
                background-color: #3a3a3a;
            }
            QSplitter::handle:hover {
                background-color: #61afef;
            }
        """)
        main_layout.addWidget(self.splitter)
        
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
        
        # Add browser to splitter
        self.splitter.addWidget(browser_widget)
        
        # Right side - info panel (optional)
        if self.show_info_panel:
            self.info_panel = AssetInfoPanel()
            self.info_panel.categoryChanged.connect(self._on_asset_category_changed)
            self.info_panel.tagsChanged.connect(self._on_asset_tags_changed)
            self.info_panel.setStyleSheet("background-color: #252525;")
            self.splitter.addWidget(self.info_panel)
            
            # Set initial sizes (browser gets 70%, info panel gets 30%)
            self.splitter.setSizes([700, 300])
        else:
            self.info_panel = None
    
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
        self._thumbnail_widgets = []
        for asset in self.filtered_assets:
            thumbnail_widget = AssetThumbnailWidget(asset, size=size)
            thumbnail_widget.assetClicked.connect(self._on_asset_clicked)
            thumbnail_widget.assetDoubleClicked.connect(self._on_asset_double_clicked)
            self.grid_layout.addWidget(thumbnail_widget)
            self._thumbnail_widgets.append(thumbnail_widget)
        
        # Clear selection when grid is rebuilt
        self.selected_assets = []
        
        # Update status
        count = len(self.filtered_assets)
        total = len(self.all_assets)
        self.status_label.setText(f"Showing {count} of {total} assets")
    
    def _on_asset_clicked(self, asset_data: Dict) -> None:
        """Handle asset single-click.  Ctrl+click to toggle multi-select."""
        modifiers = QtWidgets.QApplication.keyboardModifiers()
        
        if modifiers & QtCore.Qt.ControlModifier:
            # Ctrl+click: toggle this asset in the selection
            if any(a.get('id') == asset_data.get('id') for a in self.selected_assets):
                self.selected_assets = [a for a in self.selected_assets
                                        if a.get('id') != asset_data.get('id')]
            else:
                self.selected_assets.append(asset_data)
        else:
            # Plain click: replace selection
            self.selected_assets = [asset_data]
        
        # Sync visual state on all thumbnail widgets
        selected_ids = {a.get('id') for a in self.selected_assets}
        for widget in self._thumbnail_widgets:
            widget.set_selected(widget.asset_data.get('id') in selected_ids)
        
        # Show last-clicked asset in info panel
        if self.info_panel:
            self.info_panel.set_asset(asset_data)
        self.assetInfoChanged.emit(asset_data)
    
    def _on_asset_double_clicked(self, asset_data):
        """Handle asset double-click - trigger placement"""
        self.assetSelected.emit(asset_data)
    
    def _get_db_path(self) -> str:
        """Return the resolved path to the asset database."""
        db_path = os.environ.get('PF_ASSET_DB', '')
        if not db_path:
            library_path = os.environ.get('PF_ASSET_LIBRARY', '')
            db_path = os.path.join(library_path, 'asset_library.db')
        elif not db_path.endswith('.db'):
            db_path = os.path.join(db_path, 'asset_library.db')
        return db_path

    def _delete_selected_assets(self) -> None:
        """Delete all selected assets from the library database (Delete key)."""
        if not self.selected_assets:
            return
        
        count = len(self.selected_assets)
        names = "\n".join(f"  {a['name']}" for a in self.selected_assets)
        
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Delete Assets")
        msg.setText(f"Permanently delete {count} asset{'s' if count > 1 else ''} from the library?")
        msg.setInformativeText(names)
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setStandardButtons(QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.Cancel)
        msg.setDefaultButton(QtWidgets.QMessageBox.Cancel)
        msg.setStyleSheet("""
            QMessageBox  { background-color: #252525; color: #e0e0e0; }
            QLabel       { color: #e0e0e0; }
            QPushButton  {
                background-color: #2c2c2c; color: #e0e0e0;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 6px 16px; min-width: 80px;
            }
            QPushButton:hover  { background-color: #3a3a3a; border: 1px solid #61afef; }
            QPushButton:focus  { border: 1px solid #61afef; }
        """)
        
        if msg.exec() != QtWidgets.QMessageBox.Yes:
            return
        
        try:
            from polyfactory.asset_library.database import AssetDatabase
            with AssetDatabase(self._get_db_path()) as db:
                for asset in self.selected_assets:
                    db.delete_asset(asset['id'])
                    self._delete_asset_files(asset)
            self.selected_assets = []
            self._thumbnail_widgets = []
            self._load_assets()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Delete failed", f"Could not delete assets:\n{e}")

    def _delete_asset_files(self, asset: Dict) -> None:
        """Delete USD file, static thumbnail, and turntable folder for an asset."""
        file_path = asset.get('file_path', '')
        if file_path and os.path.isfile(file_path):
            os.remove(file_path)

        static = asset.get('thumbnail_static', '')
        if static and os.path.isfile(static):
            os.remove(static)

        turntable = asset.get('thumbnail_turntable', '')
        if turntable and os.path.isdir(turntable):
            shutil.rmtree(turntable)

    def _on_asset_category_changed(self, asset_path, new_category):
        """Handle category change from info panel"""
        try:
            from polyfactory.asset_library.database import AssetDatabase
            
            with AssetDatabase(self._get_db_path()) as db:
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
            
            with AssetDatabase(self._get_db_path()) as db:
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
