"""
Kitbash HDA UI - Python Panel interface for pf_kitbash node

Displays:
1. Asset browser at top for adding new assets
2. List of currently placed assets with transform controls
"""

import hou
from PySide6 import QtWidgets, QtCore, QtGui
from polyfactory.asset_library.browser_ui import AssetBrowserWidget
from polyfactory.ui_framework.widgets.py_push_button import PyPushButton
from polyfactory.widgets.hover_outline import HoverOutlineMixin
from polyfactory.ui_utils import get_scaled_font_size, get_font_stylesheet


class HoverListWidget(HoverOutlineMixin, QtWidgets.QListWidget):
    """QListWidget with animated hover outline"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_hover_outline(color="#61afef", width=1, radius=4, fade_duration=150, inset=0)
    
    def paintEvent(self, event):
        super().paintEvent(event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        self.paint_hover_outline(painter)


class AssetInstanceWidget(QtWidgets.QWidget):
    """Widget representing a single placed asset instance"""
    
    deleteRequested = QtCore.Signal(int)  # mesh_index
    transformChanged = QtCore.Signal(int, dict)  # mesh_index, transform_data
    
    def __init__(self, node: hou.SopNode, mesh_index: int, parent=None):
        super().__init__(parent)
        self.node = node
        self.mesh_index = mesh_index
        self._updating_from_parm = False
        
        self.setStyleSheet("""
            AssetInstanceWidget {
                background-color: #252525;
                border: 1px solid #3a3a3a;
                border-radius: 6px;
                padding: 8px;
            }
            AssetInstanceWidget:hover {
                background-color: #2c2c2c;
                border: 1px solid #61afef;
            }
        """)
        
        self._setup_ui()
        self._load_from_parameters()
    
    def _setup_ui(self):
        """Create UI for single asset instance"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(8)
        
        # Header with name and delete button
        header_layout = QtWidgets.QHBoxLayout()
        
        # Asset name
        self.name_label = QtWidgets.QLabel()
        self.name_label.setStyleSheet(get_font_stylesheet(size=11, weight="bold", color="#dce1ec"))
        header_layout.addWidget(self.name_label)
        
        header_layout.addStretch()
        
        # Delete button
        delete_btn = PyPushButton(
            text="×",
            radius=4,
            color="#ff5555",
            bg_color="#2c2c2c",
            bg_color_hover="#ff5555",
            bg_color_pressed="#cc4444"
        )
        delete_btn.setFixedSize(24, 24)
        delete_btn.setStyleSheet(delete_btn.styleSheet() + get_font_stylesheet(size=14, weight="bold"))
        delete_btn.clicked.connect(lambda: self.deleteRequested.emit(self.mesh_index))
        header_layout.addWidget(delete_btn)
        
        layout.addLayout(header_layout)
        
        # Transform controls
        controls_layout = QtWidgets.QGridLayout()
        controls_layout.setHorizontalSpacing(12)
        controls_layout.setVerticalSpacing(8)
        
        # Position (t)
        controls_layout.addWidget(self._create_label("Position:"), 0, 0)
        self.pos_x = self._create_spinbox(-1000, 1000, "X")
        self.pos_y = self._create_spinbox(-1000, 1000, "Y")
        self.pos_z = self._create_spinbox(-1000, 1000, "Z")
        pos_layout = QtWidgets.QHBoxLayout()
        pos_layout.addWidget(self.pos_x)
        pos_layout.addWidget(self.pos_y)
        pos_layout.addWidget(self.pos_z)
        controls_layout.addLayout(pos_layout, 0, 1)
        
        # Rotation (r)
        controls_layout.addWidget(self._create_label("Rotation:"), 1, 0)
        self.rot_x = self._create_spinbox(-360, 360, "X")
        self.rot_y = self._create_spinbox(-360, 360, "Y")
        self.rot_z = self._create_spinbox(-360, 360, "Z")
        rot_layout = QtWidgets.QHBoxLayout()
        rot_layout.addWidget(self.rot_x)
        rot_layout.addWidget(self.rot_y)
        rot_layout.addWidget(self.rot_z)
        controls_layout.addLayout(rot_layout, 1, 1)
        
        # Scale
        controls_layout.addWidget(self._create_label("Scale:"), 2, 0)
        self.scale = self._create_spinbox(0.01, 100, "Scale")
        self.scale.setDecimals(3)
        self.scale.setSingleStep(0.1)
        controls_layout.addWidget(self.scale, 2, 1)
        
        layout.addLayout(controls_layout)
        
        # Connect value changed signals
        for spinbox in [self.pos_x, self.pos_y, self.pos_z,
                       self.rot_x, self.rot_y, self.rot_z,
                       self.scale]:
            spinbox.valueChanged.connect(self._on_value_changed)
    
    def _create_label(self, text):
        """Create styled label"""
        label = QtWidgets.QLabel(text)
        label.setStyleSheet("color: #abb2bf; font-size: 11px;")
        label.setFixedWidth(70)
        return label
    
    def _create_spinbox(self, min_val, max_val, placeholder):
        """Create styled spinbox"""
        spinbox = QtWidgets.QDoubleSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setDecimals(2)
        spinbox.setSingleStep(0.1)
        spinbox.setStyleSheet("""
            QDoubleSpinBox {
                background-color: #2c2c2c;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                padding: 4px;
                color: #e0e0e0;
            }
            QDoubleSpinBox:focus {
                border: 1px solid #61afef;
            }
        """)
        return spinbox
    
    def _load_from_parameters(self):
        """Load values from node parameters"""
        self._updating_from_parm = True
        
        try:
            # Get file path for name
            file_parm = self.node.parm(f"file{self.mesh_index}")
            if file_parm:
                file_path = file_parm.eval()
                name = file_path.split('/')[-1].replace('.usd', '') if file_path else f"Asset {self.mesh_index}"
                self.name_label.setText(name)
            
            # Position
            t_parm = self.node.parmTuple(f"t{self.mesh_index}")
            if t_parm:
                pos = t_parm.eval()
                self.pos_x.setValue(pos[0])
                self.pos_y.setValue(pos[1])
                self.pos_z.setValue(pos[2])
            
            # Rotation
            r_parm = self.node.parmTuple(f"r{self.mesh_index}")
            if r_parm:
                rot = r_parm.eval()
                self.rot_x.setValue(rot[0])
                self.rot_y.setValue(rot[1])
                self.rot_z.setValue(rot[2])
            
            # Scale
            scale_parm = self.node.parm(f"scale{self.mesh_index}")
            if scale_parm:
                self.scale.setValue(scale_parm.eval())
        
        finally:
            self._updating_from_parm = False
    
    def _on_value_changed(self):
        """Handle spinbox value change"""
        if self._updating_from_parm:
            return
        
        # Update node parameters
        try:
            # Position
            t_parm = self.node.parmTuple(f"t{self.mesh_index}")
            if t_parm:
                t_parm.set((self.pos_x.value(), self.pos_y.value(), self.pos_z.value()))
            
            # Rotation
            r_parm = self.node.parmTuple(f"r{self.mesh_index}")
            if r_parm:
                r_parm.set((self.rot_x.value(), self.rot_y.value(), self.rot_z.value()))
            
            # Scale
            scale_parm = self.node.parm(f"scale{self.mesh_index}")
            if scale_parm:
                scale_parm.set(self.scale.value())
        
        except Exception as e:
            print(f"Error updating parameters: {e}")


class PlacedAssetsListWidget(QtWidgets.QWidget):
    """Widget displaying list of placed assets with controls"""
    
    def __init__(self, node: hou.SopNode, parent=None):
        super().__init__(parent)
        self.node = node
        self.asset_widgets = []
        
        self._setup_ui()
        self._refresh_list()
        
        # Set up timer for polling parameter changes
        self.poll_timer = QtCore.QTimer()
        self.poll_timer.timeout.connect(self._poll_parameters)
        self.poll_timer.start(500)  # Poll every 500ms
    
    def _setup_ui(self):
        """Create UI"""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)
        
        # Header
        header_layout = QtWidgets.QHBoxLayout()
        
        title = QtWidgets.QLabel("Placed Assets")
        title.setStyleSheet("color: #61afef; font-size: 13px; font-weight: bold;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Refresh button
        refresh_btn = PyPushButton(
            text="⟳",
            radius=4,
            color="#61afef",
            bg_color="#2c2c2c",
            bg_color_hover="#3a5f7d",
            bg_color_pressed="#4a6f8d"
        )
        refresh_btn.setFixedSize(28, 28)
        refresh_btn.setStyleSheet(refresh_btn.styleSheet() + get_font_stylesheet(size=13))
        refresh_btn.clicked.connect(self._refresh_list)
        header_layout.addWidget(refresh_btn)
        
        layout.addLayout(header_layout)
        
        # Scroll area for asset list
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #1e1e1e;
            }
            QScrollBar:vertical {
                background: #252525;
                width: 12px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: #3a3a3a;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background: #61afef;
            }
        """)
        
        self.list_container = QtWidgets.QWidget()
        self.list_layout = QtWidgets.QVBoxLayout(self.list_container)
        self.list_layout.setSpacing(8)
        self.list_layout.addStretch()
        
        scroll.setWidget(self.list_container)
        layout.addWidget(scroll)
    
    def _refresh_list(self):
        """Refresh asset list from multiparm"""
        # Clear existing widgets
        for widget in self.asset_widgets:
            self.list_layout.removeWidget(widget)
            widget.deleteLater()
        self.asset_widgets.clear()
        
        # Get multiparm count
        num_meshes_parm = self.node.parm("num_meshes")
        if not num_meshes_parm:
            return
        
        num_meshes = num_meshes_parm.eval()
        
        # Create widget for each asset
        for i in range(1, num_meshes + 1):
            widget = AssetInstanceWidget(self.node, i)
            widget.deleteRequested.connect(self._delete_asset)
            self.asset_widgets.append(widget)
            self.list_layout.insertWidget(i - 1, widget)
    
    def _delete_asset(self, mesh_index: int):
        """Delete asset from multiparm"""
        try:
            num_meshes_parm = self.node.parm("num_meshes")
            if not num_meshes_parm:
                return
            
            # Remove multiparm instance
            num_meshes = num_meshes_parm.eval()
            if mesh_index > 0 and mesh_index <= num_meshes:
                num_meshes_parm.removeMultiParmInstance(mesh_index - 1)
                self._refresh_list()
        
        except Exception as e:
            hou.ui.displayMessage(f"Error deleting asset: {e}", severity=hou.severityType.Error)
    
    def _poll_parameters(self):
        """Poll for parameter changes from external sources"""
        num_meshes_parm = self.node.parm("num_meshes")
        if not num_meshes_parm:
            return
        
        num_meshes = num_meshes_parm.eval()
        
        # Check if multiparm count changed
        if len(self.asset_widgets) != num_meshes:
            self._refresh_list()
        else:
            # Update existing widgets
            for widget in self.asset_widgets:
                widget._load_from_parameters()


class KitbashNodeUI(QtWidgets.QWidget):
    """Main UI for pf_kitbash node"""
    
    def __init__(self, node: hou.SopNode = None, parent=None):
        super().__init__(parent)
        self.node = node
        
        base_font_size = get_scaled_font_size(11)
        self.setStyleSheet(f"""
            QWidget {{
                background-color: #1e1e1e;
                color: #e0e0e0;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: {base_font_size}px;
            }}
        """)
        
        self._setup_ui()
        
        # If node provided, initialize immediately
        if node:
            self._initialize_with_node(node)
    
    def _setup_ui(self):
        """Create main UI"""
        # Main layout for scroll area
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Scroll area
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QtWidgets.QFrame.NoFrame)
        scroll.setStyleSheet("""
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
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
        """)
        main_layout.addWidget(scroll)
        
        # Content widget inside scroll area
        content = QtWidgets.QWidget()
        scroll.setWidget(content)
        
        layout = QtWidgets.QVBoxLayout(content)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(16)
        
        # Asset Browser
        browser_label = QtWidgets.QLabel("Asset Library")
        browser_label.setStyleSheet(get_font_stylesheet(size=13, weight="bold", color="#61afef"))
        layout.addWidget(browser_label)
        
        self.browser = AssetBrowserWidget(show_info_panel=True)
        self.browser.setMinimumHeight(600)  # At least twice as high
        self.browser.assetSelected.connect(self._on_asset_selected)
        layout.addWidget(self.browser)
        
        # Separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setStyleSheet("background-color: #3a3a3a;")
        separator.setFixedHeight(1)
        layout.addWidget(separator)
        
        # Placed assets list - collapsible group box
        self.placed_assets_group = QtWidgets.QGroupBox("Placed Assets")
        self.placed_assets_group.setCheckable(True)
        self.placed_assets_group.setChecked(False)  # Collapsed by default
        self.placed_assets_group.toggled.connect(self._on_placed_assets_toggled)
        
        group_font_size = get_scaled_font_size(13)
        self.placed_assets_group.setStyleSheet(f"""
            QGroupBox {{
                font-size: {group_font_size}px;
                font-weight: bold;
                color: #61afef;
                border: 1px solid #3a3a3a;
                border-radius: 4px;
                margin-top: 12px;
                padding-top: 12px;
                background-color: #252525;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 4px 8px;
                background-color: #2c2c2c;
                border-radius: 4px;
            }}
            QGroupBox::indicator {{
                width: 12px;
                height: 12px;
                margin-left: 4px;
            }}
            QGroupBox::indicator:checked {{
                image: none;
                background-color: #61afef;
                border: 1px solid #61afef;
            }}
            QGroupBox::indicator:unchecked {{
                image: none;
                background-color: #2c2c2c;
                border: 1px solid #3a3a3a;
            }}
        """)
        
        # Container widget for placed assets content
        self.placed_assets_container = QtWidgets.QWidget()
        self.placed_assets_layout = QtWidgets.QVBoxLayout(self.placed_assets_container)
        self.placed_assets_layout.setContentsMargins(0, 0, 0, 0)
        
        # Add container to group box
        group_layout = QtWidgets.QVBoxLayout(self.placed_assets_group)
        group_layout.setContentsMargins(8, 8, 8, 8)
        group_layout.addWidget(self.placed_assets_container)
        
        # Placeholder label
        self.placeholder_label = QtWidgets.QLabel("Waiting for node...")
        self.placeholder_label.setStyleSheet("color: #abb2bf; font-style: italic;")
        self.placeholder_label.setAlignment(QtCore.Qt.AlignCenter)
        self.placed_assets_layout.addWidget(self.placeholder_label)
        
        # Initially hide content
        self.placed_assets_container.setVisible(False)
        
        layout.addWidget(self.placed_assets_group)
        layout.addStretch()
        
        self.placed_assets = None
    
    def _on_placed_assets_toggled(self, checked):
        """Handle placed assets group box toggle"""
        self.placed_assets_container.setVisible(checked)
    
    def _initialize_with_node(self, node: hou.SopNode):
        """Initialize UI components that require a node"""
        if not node:
            return
        
        # Remove placeholder
        if self.placeholder_label:
            self.placeholder_label.setParent(None)
            self.placeholder_label.deleteLater()
            self.placeholder_label = None
        
        # Create placed assets list if not exists
        if not self.placed_assets:
            self.placed_assets = PlacedAssetsListWidget(node)
            self.placed_assets_layout.addWidget(self.placed_assets)
    
    def refresh(self):
        """Refresh the UI - called when pane becomes active"""
        if self.placed_assets:
            self.placed_assets._refresh_list()
    
    def set_node(self, node: hou.SopNode):
        """Update the node reference - called when node path changes"""
        if node is None:
            return
        
        self.node = node
        
        # Initialize if this is first time getting a node
        if not self.placed_assets:
            self._initialize_with_node(node)
        else:
            # Update existing list
            self.placed_assets.node = node
            self.placed_assets._refresh_list()
    
    def _on_asset_selected(self, asset_data):
        """Handle asset selection from browser"""
        import json
        
        # Get the scene viewer
        scene_viewer = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer)
        if not scene_viewer:
            hou.ui.displayMessage("No scene viewer found", severity=hou.severityType.Warning)
            return
        
        # Store asset data globally for state to access
        if not hasattr(hou.session, 'kitbash_asset_data'):
            hou.session.kitbash_asset_data = {}
        hou.session.kitbash_asset_data['current'] = asset_data
        
        # Activate the kitbash placement state
        try:
            scene_viewer.setCurrentState("polyfactory.kitbash_placement", 
                                        generate=hou.stateGenerateMode.Insert)
            
            print(f"Entering placement mode for: {asset_data['name']}")
            
        except Exception as e:
            hou.ui.displayMessage(f"Error activating placement state: {e}", severity=hou.severityType.Error)
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


def createInterface():
    """
    Entry point for Python Panel UI.
    Called by Houdini when creating the interface for pf_kitbash node.
    
    Returns:
        QWidget: Root widget
    """
    # Get node from kwargs
    node = kwargs.get('node')
    
    if not node:
        # Fallback widget
        widget = QtWidgets.QLabel("No node selected")
        widget.setStyleSheet("background: #1e1e1e; color: #e0e0e0;")
        return widget
    
    # Create main UI
    return KitbashNodeUI(node)
