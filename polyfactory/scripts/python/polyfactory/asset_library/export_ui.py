"""
Export UI Panel for Asset Library
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
import os


class AssetExportDialog(QtWidgets.QDialog):
    """Dialog for exporting selected geometry to asset library"""
    
    def __init__(self, parent=None, selection_node=None, selected_prims=None):
        super(AssetExportDialog, self).__init__(parent)
        
        self.selection_node = selection_node
        self.selected_prims = selected_prims
        
        self.setWindowTitle("Export to Asset Library")
        self.setMinimumWidth(500)
        self.setMinimumHeight(600)
        
        # Make dialog non-modal so user can interact with Houdini
        self.setModal(False)
        
        self._setup_ui()
        self._load_existing_data()
        
    def _setup_ui(self):
        """Create UI elements"""
        layout = QtWidgets.QVBoxLayout(self)
        
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
        
        # Asset Information
        asset_group = QtWidgets.QGroupBox("Asset Information")
        asset_layout = QtWidgets.QFormLayout()
        
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("Enter asset name...")
        asset_layout.addRow("Name:*", self.name_edit)
        
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItem("")  # Empty default
        asset_layout.addRow("Category:*", self.category_combo)
        
        self.tags_edit = QtWidgets.QLineEdit()
        self.tags_edit.setPlaceholderText("tag1, tag2, tag3")
        asset_layout.addRow("Tags:", self.tags_edit)
        
        self.notes_edit = QtWidgets.QPlainTextEdit()
        self.notes_edit.setMaximumHeight(80)
        self.notes_edit.setPlaceholderText("Optional notes about this asset...")
        asset_layout.addRow("Notes:", self.notes_edit)
        
        asset_group.setLayout(asset_layout)
        layout.addWidget(asset_group)
        
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
        
        # Connect checkbox to enable/disable sub-options
        self.use_prepare_mesh.toggled.connect(prep_options_widget.setEnabled)
        
        prep_group.setLayout(prep_layout)
        layout.addWidget(prep_group)
        
        # Export path preview
        path_group = QtWidgets.QGroupBox("Export Destination")
        path_layout = QtWidgets.QVBoxLayout()
        
        self.export_path_label = QtWidgets.QLabel("")
        self.export_path_label.setWordWrap(True)
        self.export_path_label.setStyleSheet("font-family: monospace; color: #666;")
        path_layout.addWidget(self.export_path_label)
        
        path_group.setLayout(path_layout)
        layout.addWidget(path_group)
        
        # Update path preview when name or category changes
        self.name_edit.textChanged.connect(self._update_path_preview)
        self.category_combo.currentTextChanged.connect(self._update_path_preview)
        
        # Debug options
        self.debug_prints = QtWidgets.QCheckBox("Debug Prints")
        self.debug_prints.setChecked(False)
        self.debug_prints.setToolTip("Show detailed debug information in console")
        layout.addWidget(self.debug_prints)
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()
        
        self.export_button = QtWidgets.QPushButton("Export Asset")
        self.export_button.setDefault(True)
        self.export_button.clicked.connect(self._on_export)
        button_layout.addWidget(self.export_button)
        
        cancel_button = QtWidgets.QPushButton("Cancel")
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(cancel_button)
        
        layout.addLayout(button_layout)
        
        # Spacer
        layout.addStretch()
    
    def _load_existing_data(self):
        """Load existing categories from database"""
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
                    categories = db.get_all_categories()
                    self.category_combo.addItems(categories)
        except Exception as e:
            print(f"Could not load existing categories: {e}")
    
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
            QtWidgets.QMessageBox.warning(self, "Selection Error", "No primitives selected.")
            return False
        
        return True
    
    
    def _on_export(self):
        """Handle export button click"""
        if not self._validate_inputs():
            return
        
        # Collect data
        self.export_data = {
            'name': self.name_edit.text().strip(),
            'category': self.category_combo.currentText().strip(),
            'tags': [t.strip() for t in self.tags_edit.text().split(',') if t.strip()],
            'notes': self.notes_edit.toPlainText().strip(),
            'use_prepare_mesh': self.use_prepare_mesh.isChecked(),
            'scale_to': self.scale_to_combo.currentIndex(),
            'up': self.up_combo.currentIndex(),
            'y_z': self.y_z_swap.isChecked(),
            'align_x': self.align_x_combo.currentIndex(),
            'align_y': self.align_y_combo.currentIndex(),
            'align_z': self.align_z_combo.currentIndex(),
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
    
    # Check if we have a valid selection
    if not selected_prims:
        hou.ui.displayMessage(
            "No primitives selected. Please select geometry in the viewport first.",
            severity=hou.severityType.Warning
        )
        return None
    
    # Show dialog (non-modal)
    if parent is None:
        parent = hou.qt.mainWindow()
    
    dialog = AssetExportDialog(parent, selection_node, selected_prims)
    dialog.show()  # Use show() instead of exec_() for non-modal
    
    return dialog  # Return the dialog itself instead of result
