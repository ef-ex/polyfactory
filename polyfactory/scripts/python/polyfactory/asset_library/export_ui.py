"""
Export UI Panel for Asset Library
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
import os
from polyfactory.widgets.tag_input import TagInputWidget
from polyfactory.ui_framework.widgets.py_push_button import PyPushButton
from polyfactory.ui_framework.widgets.py_line_edit import PyLineEdit
from polyfactory.ui_utils import get_scaled_font_size
from polyfactory.asset_library.batch_ui import AssetGroupRow


class AssetExportDialog(QtWidgets.QDialog):
    """Dialog for exporting selected geometry to asset library"""
    
    def __init__(self, parent=None, selection_node=None, selected_prims=None):
        super(AssetExportDialog, self).__init__(parent)

        self.selection_node = selection_node
        self.selected_prims = selected_prims
        self._groups = []
        self._rows = []

        self.setWindowTitle("Export to Asset Library")
        self.setMinimumWidth(620)
        self.setMinimumHeight(700)
        
        # Get scaled font sizes
        base_font_size = get_scaled_font_size(11)
        label_font_size = get_scaled_font_size(11)
        input_font_size = get_scaled_font_size(11)
        
        # Apply modern dark theme styling with scaled fonts
        self.setStyleSheet(f"""
            QDialog {{
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-size: {base_font_size}px;
            }}
            QGroupBox {{
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                margin-top: 12px;
                padding-top: 16px;
                font-weight: bold;
                font-size: {base_font_size}px;
                color: #e0e0e0;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 8px;
                color: #61afef;
            }}
            QLabel {{
                color: #abb2bf;
                font-size: {label_font_size}px;
            }}
            QLineEdit, QComboBox, QPlainTextEdit {{
                background-color: #2c2c2c;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 6px;
                color: #e0e0e0;
                font-size: {input_font_size}px;
            }}
            QLineEdit:focus, QComboBox:focus, QPlainTextEdit:focus {{
                border: 1px solid #61afef;
            }}
            QComboBox::drop-down {{
                border: none;
                width: 20px;
            }}
            QComboBox::down-arrow {{
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 6px solid #abb2bf;
                margin-right: 6px;
            }}
            QCheckBox {{
                color: #abb2bf;
                spacing: 8px;
                font-size: {base_font_size}px;
            }}
            QCheckBox::indicator {{
                width: 18px;
                height: 18px;
                border-radius: 3px;
                border: 1px solid #3a3a3a;
                background-color: #2c2c2c;
            }}
            QCheckBox::indicator:checked {{
                background-color: #61afef;
                border-color: #61afef;
            }}
        """)
        
        # Make dialog non-modal so user can interact with Houdini
        self.setModal(False)
        
        self._setup_ui()
        self._load_existing_data()
        
    def _setup_ui(self):
        """Create UI elements"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        # Mode toggle
        mode_row = QtWidgets.QHBoxLayout()
        self.batch_mode_checkbox = QtWidgets.QCheckBox("Batch Export  (detect and export multiple assets from one node)")
        self.batch_mode_checkbox.toggled.connect(self._on_batch_mode_toggled)
        mode_row.addWidget(self.batch_mode_checkbox)
        mode_row.addStretch()
        layout.addLayout(mode_row)

        # ── Single-mode widgets ───────────────────────────────────────────────

        # Selection info
        info_group = QtWidgets.QGroupBox("Selection Info")
        info_layout = QtWidgets.QFormLayout()
        
        prim_count = len(self.selected_prims) if self.selected_prims else 0
        self.selection_label = QtWidgets.QLabel(f"{prim_count} primitives selected")
        info_layout.addRow("Selection:", self.selection_label)
        
        if self.selection_node:
            node_path = self.selection_node.path()
            self.node_label = QtWidgets.QLabel(node_path)
            info_layout.addRow("Source Node:", self.node_label)
        
        info_group.setLayout(info_layout)
        layout.addWidget(info_group)
        
        # Asset Information (also acts as batch defaults when in batch mode)
        self.asset_group = QtWidgets.QGroupBox("Asset Information")
        asset_layout = QtWidgets.QFormLayout()
        asset_layout.setVerticalSpacing(10)
        
        self.name_edit = PyLineEdit()
        self.name_edit.setPlaceholderText("Enter asset name")
        self.name_edit.editingFinished.connect(self._on_name_confirmed)
        self.name_edit.returnPressed.connect(self._on_name_confirmed)
        
        # Add completer for existing names
        self.name_completer = QtWidgets.QCompleter()
        self.name_completer.setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.name_completer.setFilterMode(QtCore.Qt.MatchContains)
        self.name_edit.setCompleter(self.name_completer)
        
        asset_layout.addRow("Name:*", self.name_edit)
        
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItem("")  # Empty default
        asset_layout.addRow("Category:*", self.category_combo)
        
        self.tags_widget = TagInputWidget()
        asset_layout.addRow("Tags:", self.tags_widget)
        
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Optional notes about this asset...")
        asset_layout.addRow("Notes:", self.notes_edit)
        
        self.asset_group.setLayout(asset_layout)
        layout.addWidget(self.asset_group)
        
        # Preparation Options
        prep_group = QtWidgets.QGroupBox("Geometry Preparation")
        prep_layout = QtWidgets.QVBoxLayout()
        
        self.use_prepare_mesh = QtWidgets.QCheckBox("Use Prepare Mesh HDA")
        self.use_prepare_mesh.setChecked(True)
        self.use_prepare_mesh.setToolTip("Apply pf_prepare_mesh to normalize the geometry")
        
        prep_layout.addWidget(self.use_prepare_mesh)
        
        # Sub-options for prepare mesh
        prep_options_widget = QtWidgets.QWidget()
        prep_options_layout = QtWidgets.QFormLayout()
        prep_options_layout.setContentsMargins(20, 0, 0, 0)
        
        # Scale To
        self.scale_to_combo = QtWidgets.QComboBox()
        self.scale_to_combo.addItems(["None", "To One", "Normalize"])
        self.scale_to_combo.setCurrentIndex(1)  # Default: To One
        prep_options_layout.addRow("Scale:", self.scale_to_combo)
        
        # Up Axis
        self.up_combo = QtWidgets.QComboBox()
        self.up_combo.addItems(["X", "Y", "Z"])
        self.up_combo.setCurrentIndex(1)  # Default: Y
        prep_options_layout.addRow("Up Axis:", self.up_combo)
        
        # Y/Z Swap
        self.y_z_swap = QtWidgets.QCheckBox("Swap Y and Z")
        self.y_z_swap.setChecked(False)
        prep_options_layout.addRow("", self.y_z_swap)
        
        # Alignment X
        self.align_x_combo = QtWidgets.QComboBox()
        self.align_x_combo.addItems(["None", "Max", "Center", "Min"])
        self.align_x_combo.setCurrentIndex(2)  # Default: Center
        prep_options_layout.addRow("Align X:", self.align_x_combo)
        
        # Alignment Y
        self.align_y_combo = QtWidgets.QComboBox()
        self.align_y_combo.addItems(["None", "Max", "Center", "Min"])
        self.align_y_combo.setCurrentIndex(2)  # Default: Center
        prep_options_layout.addRow("Align Y:", self.align_y_combo)
        
        # Alignment Z
        self.align_z_combo = QtWidgets.QComboBox()
        self.align_z_combo.addItems(["None", "Max", "Center", "Min"])
        self.align_z_combo.setCurrentIndex(2)  # Default: Center
        prep_options_layout.addRow("Align Z:", self.align_z_combo)
        
        prep_options_widget.setLayout(prep_options_layout)
        prep_layout.addWidget(prep_options_widget)
        
        # Remove attributes option
        self.remove_attribs = QtWidgets.QCheckBox("Remove Attributes (keep only N and uv)")
        self.remove_attribs.setChecked(True)
        self.remove_attribs.setToolTip("Remove all attributes except N (normals) and uv (texture coordinates)")
        prep_layout.addWidget(self.remove_attribs)
        
        # Connect checkbox to enable/disable sub-options
        self.use_prepare_mesh.toggled.connect(prep_options_widget.setEnabled)
        
        prep_group.setLayout(prep_layout)
        layout.addWidget(prep_group)
        
        # Export path preview
        path_group = QtWidgets.QGroupBox("Export Destination")
        path_layout = QtWidgets.QVBoxLayout()
        
        self.export_path_label = QtWidgets.QLabel("")
        self.export_path_label.setWordWrap(True)
        self.export_path_label.setStyleSheet("""
            font-family: 'Consolas', 'Courier New', monospace; 
            color: #61afef;
            padding: 8px;
            background-color: #2c2c2c;
            border-radius: 4px;
        """)
        path_layout.addWidget(self.export_path_label)
        
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)

        # Update path preview when name or category changes
        self.name_edit.textChanged.connect(self._update_path_preview)
        self.name_edit.textChanged.connect(self._update_batch_row_placeholders)
        self.category_combo.currentTextChanged.connect(self._update_path_preview)

        # Track single-mode-only groups for easy show/hide
        # prep_group and asset_group excluded — both are shared/always visible
        self._single_widgets = [info_group, path_group]

        # ── Batch-mode widgets ────────────────────────────────────────────────

        # Source node picker
        self.batch_source_group = QtWidgets.QGroupBox("Source Geometry")
        src_row = QtWidgets.QHBoxLayout()
        src_row.addWidget(QtWidgets.QLabel("Node path:"))
        self.batch_node_path_edit = PyLineEdit()
        self.batch_node_path_edit.setPlaceholderText("Click Pick or enter a SOP node path...")
        src_row.addWidget(self.batch_node_path_edit, 1)
        pick_btn = PyPushButton(
            text="Pick", radius=6,
            color="#e0e0e0", bg_color="#2c2c2c",
            bg_color_hover="#3a3a3a", bg_color_pressed="#4a4a4a",
        )
        pick_btn.setMinimumHeight(32)
        pick_btn.setFixedWidth(64)
        pick_btn.clicked.connect(self._batch_pick_node)
        src_row.addWidget(pick_btn)
        self.batch_source_group.setLayout(src_row)
        self.batch_source_group.setVisible(False)
        layout.addWidget(self.batch_source_group)

        # Detect row
        self.batch_detect_widget = QtWidgets.QWidget()
        detect_row = QtWidgets.QHBoxLayout(self.batch_detect_widget)
        detect_row.setContentsMargins(0, 0, 0, 0)
        detect_btn = PyPushButton(
            text="Detect Assets", radius=8,
            color="#61afef", bg_color="#2c2c2c",
            bg_color_hover="#3a5f7d", bg_color_pressed="#4a6f8d",
        )
        detect_btn.setMinimumHeight(36)
        detect_btn.setMinimumWidth(140)
        detect_btn.clicked.connect(self._batch_detect)
        detect_row.addWidget(detect_btn)
        self.batch_detect_status = QtWidgets.QLabel("")
        self.batch_detect_status.setStyleSheet("color: #61afef;")
        detect_row.addWidget(self.batch_detect_status)
        detect_row.addStretch()
        self.batch_detect_widget.setVisible(False)
        layout.addWidget(self.batch_detect_widget)

        # Geometry prep (shared — always visible)
        layout.addWidget(prep_group)

        # Results area (batch only)
        self.batch_results_group = QtWidgets.QGroupBox("Detected Assets")
        results_outer = QtWidgets.QVBoxLayout()
        results_outer.setContentsMargins(0, 0, 0, 0)
        results_outer.setSpacing(0)

        # Column header
        hdr = QtWidgets.QWidget()
        hdr.setStyleSheet("background-color: #1e1e1e;")
        hdr_row = QtWidgets.QHBoxLayout(hdr)
        hdr_row.setContentsMargins(8, 4, 8, 4)
        hdr_row.setSpacing(8)
        hs = "color: #61afef; font-weight: bold;"
        _lbl = QtWidgets.QLabel("")
        _lbl.setFixedWidth(20)
        _lbl.setStyleSheet(hs)
        hdr_row.addWidget(_lbl)
        _lbl2 = QtWidgets.QLabel("#")
        _lbl2.setFixedWidth(32)
        _lbl2.setStyleSheet(hs)
        hdr_row.addWidget(_lbl2)
        for txt, stretch in [("Name", 2), ("Category", 1), ("Tags", 2)]:
            l = QtWidgets.QLabel(txt)
            l.setStyleSheet(hs)
            hdr_row.addWidget(l, stretch)
        _lbl3 = QtWidgets.QLabel("Prims / Islands")
        _lbl3.setFixedWidth(88)
        _lbl3.setStyleSheet(hs)
        hdr_row.addWidget(_lbl3)
        results_outer.addWidget(hdr)

        self.batch_scroll = QtWidgets.QScrollArea()
        self.batch_scroll.setWidgetResizable(True)
        self.batch_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.batch_scroll.setMinimumHeight(160)
        self.batch_rows_container = QtWidgets.QWidget()
        self.batch_rows_container.setStyleSheet("background-color: transparent;")
        self.batch_rows_layout = QtWidgets.QVBoxLayout(self.batch_rows_container)
        self.batch_rows_layout.setContentsMargins(0, 0, 0, 0)
        self.batch_rows_layout.setSpacing(0)
        self.batch_rows_layout.addStretch()
        self.batch_scroll.setWidget(self.batch_rows_container)
        results_outer.addWidget(self.batch_scroll)
        self.batch_results_group.setLayout(results_outer)
        self.batch_results_group.setVisible(False)
        layout.addWidget(self.batch_results_group, stretch=1)

        # Select All / None (batch only)
        self.batch_sel_widget = QtWidgets.QWidget()
        sel_row = QtWidgets.QHBoxLayout(self.batch_sel_widget)
        sel_row.setContentsMargins(0, 0, 0, 0)
        for label, checked in [("All", True), ("None", False)]:
            btn = QtWidgets.QPushButton(label)
            btn.setFixedWidth(52)
            btn.setStyleSheet("""
                QPushButton { background-color:#2c2c2c; border:1px solid #3a3a3a;
                border-radius:4px; color:#abb2bf; padding:4px; }
                QPushButton:hover { border-color:#61afef; }
            """)
            btn.clicked.connect(lambda _=None, c=checked: self._batch_set_all_checked(c))
            sel_row.addWidget(btn)
        sel_row.addStretch()
        self.batch_sel_widget.setVisible(False)
        layout.addWidget(self.batch_sel_widget)

        # ── Shared bottom ─────────────────────────────────────────────────────

        # Debug options
        self.debug_prints = QtWidgets.QCheckBox("Debug Prints")
        self.debug_prints.setChecked(False)
        self.debug_prints.setToolTip("Show detailed debug information in console")
        layout.addWidget(self.debug_prints)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.setSpacing(8)
        self.batch_progress_label = QtWidgets.QLabel("")
        self.batch_progress_label.setStyleSheet("color: #abb2bf;")
        self.batch_progress_label.setVisible(False)
        button_layout.addWidget(self.batch_progress_label)
        button_layout.addStretch()

        self.export_button = PyPushButton(
            text="Export Asset",
            radius=8,
            color="#61afef",
            bg_color="#2c2c2c",
            bg_color_hover="#3a5f7d",
            bg_color_pressed="#4a6f8d"
        )
        self.export_button.setMinimumHeight(40)
        self.export_button.setMinimumWidth(140)
        self.export_button.clicked.connect(self._on_export)
        button_layout.addWidget(self.export_button)

        cancel_button = PyPushButton(
            text="Cancel",
            radius=8,
            color="#abb2bf",
            bg_color="#2c2c2c",
            bg_color_hover="#3a3a3a",
            bg_color_pressed="#4a4a4a"
        )
        cancel_button.setMinimumHeight(40)
        cancel_button.setMinimumWidth(100)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)

        layout.addLayout(button_layout)

        # Spacer
        layout.addStretch()

    # ── Batch mode ────────────────────────────────────────────────────────────

    def _on_batch_mode_toggled(self, checked: bool) -> None:
        for w in self._single_widgets:
            w.setVisible(not checked)
        self.asset_group.setTitle(
            "Batch Defaults  (applied to rows without individual values)"
            if checked else "Asset Information"
        )
        self.batch_source_group.setVisible(checked)
        self.batch_detect_widget.setVisible(checked)
        self.batch_results_group.setVisible(checked)
        self.batch_sel_widget.setVisible(checked)
        self.batch_progress_label.setVisible(checked)
        self.export_button.setText("Export Selected" if checked else "Export Asset")
        self.adjustSize()

    def _batch_pick_node(self) -> None:
        try:
            current = self.batch_node_path_edit.text().strip()
            initial = hou.node(current) if current else None
            path = hou.ui.selectNode(initial_node=initial)
            if path:
                self.batch_node_path_edit.setText(path)
        except Exception as e:
            print(f"Error picking node: {e}")

    def _batch_detect(self) -> None:
        node_path = self.batch_node_path_edit.text().strip()
        if not node_path:
            hou.ui.displayMessage(
                "Please enter or pick a source SOP node path first.",
                severity=hou.severityType.Warning,
            )
            return
        sop_node = hou.node(node_path)
        if not sop_node:
            hou.ui.displayMessage(
                f"Node not found: {node_path}",
                severity=hou.severityType.Error,
            )
            return

        # Clear previous results
        while self.batch_rows_layout.count() > 1:
            item = self.batch_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows = []
        self._groups = []
        self.export_button.setEnabled(False)

        self.batch_detect_status.setText("Running connectivity...")
        QtWidgets.QApplication.processEvents()

        def _on_group(group: dict) -> None:
            """Called by detect_asset_groups each time a cluster is confirmed."""
            self._groups.append(group)
            i: int = len(self._groups) - 1
            row = AssetGroupRow(
                index=i,
                group=group,
                categories=self.db_categories,
                available_tags=self.db_tags,
                parent=self.batch_rows_container,
            )
            self.batch_rows_layout.insertWidget(self.batch_rows_layout.count() - 1, row)
            self._rows.append(row)
            self.batch_detect_status.setText(f"Found {len(self._groups)} groups...")
            self.batch_rows_container.updateGeometry()
            QtWidgets.QApplication.processEvents()

        try:
            from polyfactory.asset_library.batch_importer import detect_asset_groups
            detect_asset_groups(sop_node, on_group_detected=_on_group)
            count = len(self._groups)
            self.batch_detect_status.setText(
                f"{count} asset{'s' if count != 1 else ''} detected"
            )
            self._update_batch_row_placeholders()
            self.export_button.setEnabled(count > 0)
        except Exception as e:
            import traceback
            traceback.print_exc()
            self.batch_detect_status.setText(f"Error: {e}")

    def _batch_populate_rows(self) -> None:
        while self.batch_rows_layout.count() > 1:
            item = self.batch_rows_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._rows = []
        for i, group in enumerate(self._groups):
            row = AssetGroupRow(
                index=i,
                group=group,
                categories=self.db_categories,
                available_tags=self.db_tags,
                parent=self.batch_rows_container,
            )
            self.batch_rows_layout.insertWidget(self.batch_rows_layout.count() - 1, row)
            self._rows.append(row)
        self.batch_rows_container.updateGeometry()
        self._update_batch_row_placeholders()

    def _update_batch_row_placeholders(self) -> None:
        """Keep blank row name fields showing the effective base name they will use."""
        default = self.name_edit.text().strip() if hasattr(self, 'name_edit') else ''
        for row in getattr(self, '_rows', []):
            if not row.name_edit.text():
                row.name_edit.setPlaceholderText(default or "asset")

    def _batch_set_all_checked(self, checked: bool) -> None:
        for row in self._rows:
            row.checkbox.setChecked(checked)

    def _run_batch_export(self) -> None:
        node_path = self.batch_node_path_edit.text().strip()
        sop_node = hou.node(node_path) if node_path else None
        if not sop_node:
            hou.ui.displayMessage(
                "Please pick a source SOP node first.",
                severity=hou.severityType.Warning,
            )
            return
        checked_rows = [r for r in self._rows if r.is_checked()]
        if not checked_rows:
            hou.ui.displayMessage("No assets selected.", severity=hou.severityType.Warning)
            return
        # Dialog-level defaults applied to rows that leave fields blank
        default_name = self.name_edit.text().strip()
        default_category = self.category_combo.currentText().strip()
        default_tags = self.tags_widget.getTags()
        for row in checked_rows:
            if not (row.get_category() or default_category):
                row_name = row.get_name() or default_name or "asset"
                hou.ui.displayMessage(
                    f"Asset #{row.index + 1} ({row_name!r}) has no category.\n"
                    "Set a category in the row or in Batch Defaults above.",
                    severity=hou.severityType.Warning,
                )
                return
        library_path = os.environ.get('PF_ASSET_LIBRARY', '')
        if not library_path:
            hou.ui.displayMessage(
                "PF_ASSET_LIBRARY environment variable is not set.",
                severity=hou.severityType.Error,
            )
            return
        db_path = os.environ.get('PF_ASSET_DB', '')
        if not db_path:
            db_path = os.path.join(library_path, 'asset_library.db')
        elif not db_path.endswith('.db'):
            db_path = os.path.join(db_path, 'asset_library.db')
        prep_settings = {
            'use_prepare_mesh': self.use_prepare_mesh.isChecked(),
            'scale_to': self.scale_to_combo.currentIndex(),
            'up': self.up_combo.currentIndex(),
            'y_z': self.y_z_swap.isChecked(),
            'align_x': self.align_x_combo.currentIndex(),
            'align_y': self.align_y_combo.currentIndex(),
            'align_z': self.align_z_combo.currentIndex(),
            'remove_attribs': self.remove_attribs.isChecked(),
        }
        from polyfactory.asset_library.batch_importer import next_free_filename, export_batch_group
        from polyfactory.asset_library.render import acquire_shared_panel, release_shared_panel
        total = len(checked_rows)
        success_count = 0
        debug = self.debug_prints.isChecked()
        self.export_button.setEnabled(False)
        # Create one shared SceneViewer panel for the whole batch so Houdini doesn't
        # pay the Qt widget construction + 0.5 s init sleep on every single asset.
        acquire_shared_panel()
        try:
            for i, row in enumerate(checked_rows):
                base_name = row.get_name() or default_name or "asset"
                category = row.get_category() or default_category
                tags = row.get_tags() or default_tags
                group = self._groups[row.index]
                self.batch_progress_label.setText(f"Exporting {i + 1}/{total}: {base_name}...")
                row.set_export_status('exporting')
                QtWidgets.QApplication.processEvents()
                final_name = next_free_filename(base_name, category, library_path, db_path)
                try:
                    ok = export_batch_group(
                        sop_node=sop_node,
                        prim_numbers=group['prim_numbers'],
                        name=final_name,
                        category=category,
                        tags=tags,
                        prep_settings=prep_settings,
                        debug=debug,
                    )
                    if ok:
                        success_count += 1
                        row.set_export_status('done')
                    else:
                        row.set_export_status('error')
                        print(f"Warning: export returned False for {final_name!r}")
                except Exception as e:
                    import traceback
                    traceback.print_exc()
                    row.set_export_status('error')
                    print(f"Error exporting {final_name!r}: {e}")
                QtWidgets.QApplication.processEvents()
        finally:
            release_shared_panel()
        self.export_button.setEnabled(True)
        self.batch_progress_label.setText(f"Done: {success_count}/{total} exported")
        if success_count > 0:
            hou.ui.displayMessage(
                f"Batch export complete.\n{success_count}/{total} assets exported successfully.",
                severity=hou.severityType.Message,
            )

    def _load_existing_data(self):
        """Load existing categories from database"""
        # Store for auto-matching
        self.db_categories = []
        self.db_tags = []
        self.db_names = []
        
        try:
            from polyfactory.asset_library.database import AssetDatabase
            
            # Get library path
            library_path = os.environ.get('PF_ASSET_LIBRARY', '')
            if not library_path:
                return
            
            # Construct database path
            db_path = os.environ.get('PF_ASSET_DB', '')
            if not db_path:
                db_path = os.path.join(library_path, 'asset_library.db')
            elif not db_path.endswith('.db'):
                db_path = os.path.join(db_path, 'asset_library.db')
            
            # Only try to load if database exists
            if os.path.exists(db_path):
                with AssetDatabase(db_path) as db:
                    # Load categories
                    self.db_categories = db.get_all_categories()
                    self.category_combo.addItems(self.db_categories)
                    
                    # Load tags
                    self.db_tags = db.get_all_tags()
                    self.tags_widget.setAvailableTags(self.db_tags)
                    
                    # Load existing asset names for autocomplete
                    self.db_names = db.get_all_names()
                    name_model = QtCore.QStringListModel(self.db_names)
                    self.name_completer.setModel(name_model)
        except Exception as e:
            print(f"Could not load existing categories: {e}")
    
    def _on_name_confirmed(self):
        """Handle name confirmation (Enter key or lost focus) - auto-suggest category and tags"""
        text = self.name_edit.text().strip().lower()
        if not text or len(text) < 3:
            return
        
        # Find matching category (case-insensitive substring match)
        matched_category = None
        for category in self.db_categories:
            if category.lower() in text or text in category.lower():
                matched_category = category
                break
        
        # Auto-fill category if found and field is empty
        if matched_category and not self.category_combo.currentText().strip():
            self.category_combo.setCurrentText(matched_category)
        
        # Find matching tags
        current_tags = set(self.tags_widget.getTags())
        new_tags = []
        
        for tag in self.db_tags:
            tag_lower = tag.lower()
            # Check if tag is substring of name or name contains tag as word
            if tag_lower in text or text in tag_lower:
                if tag not in current_tags:
                    new_tags.append(tag)
        
        # Auto-add matching tags
        if new_tags:
            all_tags = list(current_tags) + new_tags
            self.tags_widget.setTags(all_tags)
    
    def _update_path_preview(self):
        """Update the export path preview"""
        name = self.name_edit.text().strip()
        category = self.category_combo.currentText().strip()
        
        if not name or not category:
            self.export_path_label.setText("Enter name and category to see path preview")
            return
        
        # Sanitize filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_name = safe_name.replace(' ', '_')
        safe_category = "".join(c for c in category if c.isalnum() or c in (' ', '_', '-')).strip()
        safe_category = safe_category.replace(' ', '_')
        
        library_path = os.environ.get('PF_ASSET_LIBRARY', '$PF_ASSET_LIBRARY')
        export_path = os.path.join(library_path, safe_category, f"{safe_name}.usd")
        
        self.export_path_label.setText(export_path)
    
    def _validate_inputs(self) -> bool:
        """Validate user inputs"""
        if not self.name_edit.text().strip():
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Please enter an asset name.")
            self.name_edit.setFocus()
            return False
        
        if not self.category_combo.currentText().strip():
            QtWidgets.QMessageBox.warning(self, "Validation Error", "Please select or enter a category.")
            self.category_combo.setFocus()
            return False
        
        if not self.selected_prims:
            QtWidgets.QMessageBox.warning(
                self,
                "No Selection",
                "No primitives selected.\n\n"
                "Select geometry in the viewport and click Export Asset again.",
            )
            return False
        
        return True
    
    
    def _on_export(self):
        """Handle export button click"""
        if self.batch_mode_checkbox.isChecked():
            self._run_batch_export()
            return
        if not self._validate_inputs():
            return
        
        # Collect data
        self.export_data = {
            'name': self.name_edit.text().strip(),
            'category': self.category_combo.currentText().strip(),
            'tags': self.tags_widget.getTags(),
            'notes': self.notes_edit.toPlainText().strip(),
            'use_prepare_mesh': self.use_prepare_mesh.isChecked(),
            'scale_to': self.scale_to_combo.currentIndex(),
            'up': self.up_combo.currentIndex(),
            'y_z': self.y_z_swap.isChecked(),
            'align_x': self.align_x_combo.currentIndex(),
            'align_y': self.align_y_combo.currentIndex(),
            'align_z': self.align_z_combo.currentIndex(),
            'remove_attribs': self.remove_attribs.isChecked(),
            'selection_node': self.selection_node,
            'selected_prims': self.selected_prims
        }
        
        # Execute the export
        from polyfactory.asset_library.exporter import export_asset
        result = export_asset(self.export_data, debug=self.debug_prints.isChecked())
        
        if result:
            QtWidgets.QMessageBox.information(
                self,
                "Export Complete",
                f"Asset '{self.export_data['name']}' exported successfully!"
            )
            self.accept()
        else:
            QtWidgets.QMessageBox.critical(
                self,
                "Export Failed",
                "Export failed. Check the console for details."
            )
    
    def get_export_data(self):
        """Get the export configuration data"""
        return getattr(self, 'export_data', None)


def show_export_dialog(parent=None):
    """Show the export dialog with current selection
    
    Args:
        parent: Parent widget (typically hou.qt.mainWindow())
        
    Returns:
        Export data dict if accepted, None if cancelled
    """
    # Get current selection
    geo_viewer = None
    selected_prims = []
    selection_node = None
    
    try:
        # Get scene viewer
        desktop = hou.ui.curDesktop()
        scene_viewer = desktop.paneTabOfType(hou.paneTabType.SceneViewer)
        
        if scene_viewer:
            # Get geometry selection
            geo_selection = scene_viewer.currentGeometrySelection()
            if geo_selection:
                nodes = geo_selection.nodes()
                if nodes:
                    selection_node = nodes[0]
                    geo = selection_node.geometry()
                    if geo:
                        # Get the selection strings - returns list of selection strings
                        sel_strings = geo_selection.selectionStrings(empty_string_selects_all=False)
                        if sel_strings and len(sel_strings) > 0:
                            # Parse the selection string to get primitives
                            selected_prims = list(geo.globPrims(sel_strings[0]))
    except Exception as e:
        print(f"Error getting selection: {e}")
        import traceback
        traceback.print_exc()
    
    # Show dialog (non-modal) — selection may be empty; validation runs on Export click
    if parent is None:
        parent = hou.qt.mainWindow()
    
    dialog = AssetExportDialog(parent, selection_node, selected_prims)
    dialog.show()  # Use show() instead of exec_() for non-modal
    
    return dialog  # Return the dialog itself instead of result
