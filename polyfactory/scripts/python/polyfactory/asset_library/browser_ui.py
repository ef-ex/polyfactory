"""
Asset Browser UI - Grid view of assets with search and filtering
"""

import hou
import hdefereval
from PySide6 import QtWidgets, QtCore, QtGui
import os
import json
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
    
    assetSelected = QtCore.Signal(dict)    # Emits when asset is selected for placement
    assetInfoChanged = QtCore.Signal(dict)  # Emits when asset is clicked for info display
    assetDroppedAt = QtCore.Signal(dict, QtCore.QPoint)  # Forwards thumbnail drag drops
    
    def __init__(self, show_info_panel=True, parent=None):
        super().__init__(parent)
        self.all_assets = []
        self.filtered_assets = []
        self.selected_assets: List[Dict] = []   # multi-select list
        self._last_clicked_index: int = -1      # for Shift+click range selection
        self._thumbnail_widgets: List[AssetThumbnailWidget] = []
        self.show_info_panel = show_info_panel

        self._drop_handler = AssetDropHandler(self)
        self._setup_ui()
        self.assetDroppedAt.connect(self._drop_handler.handle_dropped_at)

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

        # Debounce timer — actual resize fires 150 ms after the user stops dragging
        self._resize_timer = QtCore.QTimer(self)
        self._resize_timer.setSingleShot(True)
        self._resize_timer.timeout.connect(self._apply_size_change)
        
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
            thumbnail_widget.assetDroppedAt.connect(self._on_thumbnail_dropped_at)
            thumbnail_widget.assetRightClicked.connect(self._on_asset_right_clicked)
            self.grid_layout.addWidget(thumbnail_widget)
            self._thumbnail_widgets.append(thumbnail_widget)
        
        # Clear selection when grid is rebuilt
        self.selected_assets = []
        self._last_clicked_index = -1

        # Update status
        count = len(self.filtered_assets)
        total = len(self.all_assets)
        self.status_label.setText(f"Showing {count} of {total} assets")
    
    def _on_asset_clicked(self, asset_data: Dict) -> None:
        """Handle asset single-click.  Ctrl+click toggles, Shift+click selects range."""
        modifiers = QtWidgets.QApplication.keyboardModifiers()

        # Find the index of the clicked asset in the current filtered list
        clicked_index = next(
            (i for i, a in enumerate(self.filtered_assets)
             if a.get('id') == asset_data.get('id')),
            -1
        )

        if modifiers & QtCore.Qt.ShiftModifier and self._last_clicked_index >= 0:
            # Shift+click: select the range between the anchor and this asset
            lo = min(self._last_clicked_index, clicked_index)
            hi = max(self._last_clicked_index, clicked_index)
            range_assets = [self.filtered_assets[i] for i in range(lo, hi + 1)]
            if modifiers & QtCore.Qt.ControlModifier:
                # Ctrl+Shift: extend current selection with the range
                existing_ids = {a.get('id') for a in self.selected_assets}
                for a in range_assets:
                    if a.get('id') not in existing_ids:
                        self.selected_assets.append(a)
            else:
                # Shift only: replace selection with the range
                self.selected_assets = range_assets
        elif modifiers & QtCore.Qt.ControlModifier:
            # Ctrl+click: toggle this asset in the selection
            if any(a.get('id') == asset_data.get('id') for a in self.selected_assets):
                self.selected_assets = [a for a in self.selected_assets
                                        if a.get('id') != asset_data.get('id')]
            else:
                self.selected_assets.append(asset_data)
            self._last_clicked_index = clicked_index
        else:
            # Plain click: replace selection
            self.selected_assets = [asset_data]
            self._last_clicked_index = clicked_index
        
        # Sync visual state on all thumbnail widgets
        selected_ids = {a.get('id') for a in self.selected_assets}
        for widget in self._thumbnail_widgets:
            widget.set_selected(widget.asset_data.get('id') in selected_ids)
        
        # Show last-clicked asset in info panel
        if self.info_panel:
            self.info_panel.set_asset(asset_data)
        self.assetInfoChanged.emit(asset_data)
    
    def _on_thumbnail_dropped_at(self, asset_data: dict, pos: QtCore.QPoint) -> None:
        """Forward thumbnail drop to the browser-level signal."""
        self.assetDroppedAt.emit(asset_data, pos)

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

        # Build a custom dialog so the asset list is scrollable and never
        # overflows the screen regardless of how many assets are selected.
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle("Delete Assets")
        dlg.setMinimumWidth(420)
        dlg.setStyleSheet("""
            QDialog      { background-color: #252525; color: #e0e0e0; }
            QLabel       { color: #e0e0e0; }
            QTextEdit    { background-color: #1e1e1e; color: #abb2bf;
                           border: 1px solid #3a3a3a; border-radius: 4px; }
            QPushButton  {
                background-color: #2c2c2c; color: #e0e0e0;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 6px 16px; min-width: 80px;
            }
            QPushButton:hover  { background-color: #3a3a3a; border: 1px solid #61afef; }
            QPushButton#delete_btn { border-color: #ff5555; }
            QPushButton#delete_btn:hover { background-color: #3a1a1a; border-color: #ff5555; }
        """)
        dlg_layout = QtWidgets.QVBoxLayout(dlg)
        dlg_layout.setSpacing(10)
        dlg_layout.setContentsMargins(16, 16, 16, 16)

        question = QtWidgets.QLabel(
            f"Permanently delete {count} asset{'s' if count > 1 else ''} from the library?"
        )
        question.setWordWrap(True)
        question.setStyleSheet("font-weight: bold; font-size: 13px;")
        dlg_layout.addWidget(question)

        names_edit = QtWidgets.QTextEdit()
        names_edit.setReadOnly(True)
        names_edit.setPlainText("\n".join(a['name'] for a in self.selected_assets))
        names_edit.setFixedHeight(180)
        dlg_layout.addWidget(names_edit)

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addStretch()
        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setDefault(True)
        cancel_btn.clicked.connect(dlg.reject)
        delete_btn = QtWidgets.QPushButton(f"Delete {count}")
        delete_btn.setObjectName("delete_btn")
        delete_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(cancel_btn)
        btn_row.addWidget(delete_btn)
        dlg_layout.addLayout(btn_row)

        if dlg.exec() != QtWidgets.QDialog.Accepted:
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

    def _on_asset_right_clicked(self, asset_data: Dict, global_pos: QtCore.QPoint) -> None:
        """Show a context menu on right-click.  If the clicked asset is not already
        selected, select it first (plain-click semantics)."""
        asset_id = asset_data.get('id')
        if not any(a.get('id') == asset_id for a in self.selected_assets):
            self.selected_assets = [asset_data]
            clicked_index = next(
                (i for i, a in enumerate(self.filtered_assets)
                 if a.get('id') == asset_id), -1
            )
            self._last_clicked_index = clicked_index
            selected_ids = {asset_id}
            for widget in self._thumbnail_widgets:
                widget.set_selected(widget.asset_data.get('id') in selected_ids)
            if self.info_panel:
                self.info_panel.set_asset(asset_data)
            self.assetInfoChanged.emit(asset_data)

        count = len(self.selected_assets)
        noun = f"{count} asset{'s' if count > 1 else ''}"

        menu = QtWidgets.QMenu(self)
        menu.setStyleSheet("""
            QMenu {
                background-color: #252525;
                color: #e0e0e0;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 4px;
            }
            QMenu::item {
                padding: 6px 20px;
                border-radius: 3px;
            }
            QMenu::item:selected {
                background-color: #3a3a3a;
                color: #61afef;
            }
            QMenu::separator {
                height: 1px;
                background: #3a3a3a;
                margin: 4px 8px;
            }
        """)

        manage_action = menu.addAction("Manage Tags...")
        menu.addSeparator()
        delete_action = menu.addAction(f"Delete {noun}")

        action = menu.exec(global_pos)
        if action == manage_action:
            self._open_manage_tags_dialog()
        elif action == delete_action:
            self._delete_selected_assets()

    def _open_manage_tags_dialog(self) -> None:
        """Open a dialog to bulk-add or bulk-remove tags on the current selection."""
        if not self.selected_assets:
            return

        count = len(self.selected_assets)
        dlg = QtWidgets.QDialog(self)
        dlg.setWindowTitle(f"Manage Tags  —  {count} asset{'s' if count > 1 else ''}")
        dlg.setMinimumWidth(440)
        dlg.setStyleSheet("""
            QDialog     { background-color: #252525; color: #e0e0e0; }
            QLabel      { color: #e0e0e0; }
            QPushButton {
                background-color: #2c2c2c; color: #e0e0e0;
                border: 1px solid #3a3a3a; border-radius: 4px;
                padding: 6px 16px; min-width: 80px;
            }
            QPushButton:hover { background-color: #3a3a3a; border: 1px solid #61afef; }
            QPushButton#add_btn    { border-color: #98c379; }
            QPushButton#add_btn:hover    { background-color: #1a3a1a; }
            QPushButton#remove_btn { border-color: #e06c75; }
            QPushButton#remove_btn:hover { background-color: #3a1a1a; }
            QLabel#status_lbl { color: #abb2bf; font-style: italic; padding: 4px 0; }
        """)

        dlg_layout = QtWidgets.QVBoxLayout(dlg)
        dlg_layout.setSpacing(12)
        dlg_layout.setContentsMargins(16, 16, 16, 16)

        header = QtWidgets.QLabel(
            f"Enter tags to add or remove across {count} selected asset{'s' if count > 1 else ''}:"
        )
        header.setWordWrap(True)
        dlg_layout.addWidget(header)

        from polyfactory.widgets.tag_input import TagInputWidget
        from polyfactory.asset_library.database import AssetDatabase

        tag_input = TagInputWidget()
        try:
            with AssetDatabase(self._get_db_path()) as db:
                tag_input.setAvailableTags(db.get_all_tags())
        except Exception:
            pass
        dlg_layout.addWidget(tag_input)

        status_lbl = QtWidgets.QLabel("")
        status_lbl.setObjectName("status_lbl")
        status_lbl.setWordWrap(True)
        dlg_layout.addWidget(status_lbl)

        btn_row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add")
        add_btn.setObjectName("add_btn")
        remove_btn = QtWidgets.QPushButton("Remove")
        remove_btn.setObjectName("remove_btn")
        btn_row.addWidget(add_btn)
        btn_row.addWidget(remove_btn)
        btn_row.addStretch()
        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setDefault(True)
        close_btn.clicked.connect(dlg.accept)
        btn_row.addWidget(close_btn)
        dlg_layout.addLayout(btn_row)

        asset_ids = [a['id'] for a in self.selected_assets]

        def _do_add() -> None:
            tags = tag_input.getTags()
            if not tags:
                status_lbl.setText("Enter at least one tag.")
                return
            try:
                with AssetDatabase(self._get_db_path()) as db:
                    db.add_tags_to_assets(asset_ids, tags)
                status_lbl.setText(f"Added {len(tags)} tag(s) to {count} asset(s).")
                self._load_assets()
            except Exception as e:
                status_lbl.setText(f"Error: {e}")

        def _do_remove() -> None:
            tags = tag_input.getTags()
            if not tags:
                status_lbl.setText("Enter at least one tag.")
                return
            try:
                with AssetDatabase(self._get_db_path()) as db:
                    db.remove_tags_from_assets(asset_ids, tags)
                status_lbl.setText(f"Removed {len(tags)} tag(s) from {count} asset(s).")
                self._load_assets()
            except Exception as e:
                status_lbl.setText(f"Error: {e}")

        add_btn.clicked.connect(_do_add)
        remove_btn.clicked.connect(_do_remove)

        dlg.exec()

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
    
    def _on_size_changed(self, value: int) -> None:
        """Update size label immediately; schedule the actual resize with debounce"""
        self.size_value_label.setText(f"{value}px")
        self._resize_timer.start(150)

    def _apply_size_change(self) -> None:
        """Resize all thumbnails — called once after the slider stops moving"""
        value: int = self.size_slider.value()
        for i in range(self.grid_layout.count()):
            item = self.grid_layout.itemAt(i)
            if item and item.widget():
                widget = item.widget()
                if isinstance(widget, AssetThumbnailWidget):
                    widget.set_size(value)
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
    
    def _on_asset_selected(self, asset_data: dict) -> None:
        """Double-click in the floating browser: create and connect the
        asset placement node without entering the viewer state."""
        AssetDropHandler._handle_drop(asset_data, enter_state=False)


def show_asset_browser():
    """Show the asset browser dialog"""
    dialog = AssetBrowserDialog(hou.qt.mainWindow())
    dialog.show()


# ── Drag/Drop handler ────────────────────────────────────────────────────

MIME_TYPE = "application/x-polyfactory-asset"
NODE_TYPE = "pf::pf_asset_place::1.0"


class AssetDropHandler(QtCore.QObject):
    """Handles drops from the asset browser onto Houdini's viewport or network
    editor. Houdini's native OpenGL panes do not accept Qt drops, so the
    approach is signal-based: AssetThumbnailWidget emits assetDroppedAt after
    drag.exec() returns, carrying the cursor position. This method checks
    whether that position falls inside a known Houdini pane and acts
    accordingly.

    Usage::
        handler = AssetDropHandler(parent)
        browser.assetDroppedAt.connect(handler.handle_dropped_at)
    """

    def __init__(self, parent: QtCore.QObject | None = None) -> None:
        super().__init__(parent)

    # ── Public API ───────────────────────────────────────────────────────

    def install(self) -> None:
        """No-op — wiring is done via signal connections."""

    def uninstall(self) -> None:
        """No-op."""

    def handle_dropped_at(self, asset_data: dict, pos: QtCore.QPoint) -> None:
        """Called after a drag completes. If the cursor is outside our own
        window, the user dropped onto Houdini — create the node and enter the
        viewer state."""
        # Walk up to find the top-level window that owns this handler
        source_window: QtWidgets.QWidget | None = self.parent()
        while source_window and not source_window.isWindow():
            source_window = source_window.parent()

        if source_window:
            win_rect = QtCore.QRect(
                source_window.mapToGlobal(QtCore.QPoint(0, 0)),
                source_window.size()
            )
            dropped_outside = not win_rect.contains(pos)
        else:
            dropped_outside = True

        if dropped_outside:
            self._handle_drop(asset_data, enter_state=True)

    # ── Private helpers ─────────────────────────────────────────────────

    @staticmethod
    def _handle_drop(asset_data: dict, enter_state: bool) -> None:
        """Create a pf_asset_place node in the current network, wire it to the
        currently selected node (if any), and optionally enter the viewer state."""
        try:
            # Find the SOP context under the current network location
            editor = hou.ui.paneTabOfType(hou.paneTabType.NetworkEditor)
            pwd = editor.pwd() if editor else hou.node("/obj")

            # If pwd is an obj-level subnet, look inside for a SOP context
            if isinstance(pwd, hou.ObjNode):
                # Find an existing geo container or work at obj level
                geo_children = [n for n in pwd.children() if isinstance(n, hou.SopNode)]
                if not geo_children:
                    # Create inside a geometry node
                    geo = pwd.createNode("geo", "asset_place_geo")
                    pwd = geo
                else:
                    pwd = geo_children[0].parent()

            # Create the pf_asset_place node
            node = pwd.createNode(NODE_TYPE, "asset_place")

            # Set asset parameters
            asset_id = asset_data.get("asset_id") or asset_data.get("name", "")
            asset_path = asset_data.get("file_path", "")
            asset_name = asset_data.get("name", "")
            for parm_name, value in (("asset_id", asset_id),
                                     ("asset_path", asset_path),
                                     ("asset_name", asset_name)):
                parm = node.parm(parm_name)
                if parm:
                    parm.set(value)

            # Connect to the currently selected node if it has SOP output
            selected = [n for n in pwd.selectedChildren()
                        if isinstance(n, hou.SopNode) and n is not node]
            if selected:
                upstream = selected[-1]
                node.setInput(0, upstream)
                node.setPosition(upstream.position() + hou.Vector2(0, -2))
            else:
                node.setPosition(hou.Vector2(0, 0))

            node.setSelected(True, clear_all_selected=True)
            node.setDisplayFlag(True)
            node.setRenderFlag(True)

            # Enter viewer state if dropped on viewport
            if enter_state:
                sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
                if sv:
                    # Signal the state to start in surface-align (one-shot).
                    import sys
                    _aps = sys.modules.get("polyfactory.asset_library.asset_place_state")
                    if _aps:
                        _aps._drop_triggered = True
                    sv.setCurrentState("polyfactory.asset_place")
                    def _focus_viewer():
                        sv.setIsCurrentTab()
                        try:
                            hou.qt.mainWindow().activateWindow()
                        except Exception:
                            pass
                    hdefereval.executeDeferred(_focus_viewer)

        except Exception as e:
            print(f"[AssetDropHandler] Drop failed: {e}")
