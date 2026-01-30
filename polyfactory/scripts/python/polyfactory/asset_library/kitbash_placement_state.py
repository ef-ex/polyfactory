"""
Kitbash Placement State - Interactive viewport placement for assets
"""

import hou
import viewerstate.utils as su
import os
from polyfactory.viewer_utils import raycasting


# Placement modes
MODE_ALIGN_TO_MESH = "align_to_mesh"
MODE_SIMPLE_PLACEMENT = "simple_placement"


class KitbashPlacementState(object):
    """Interactive state for placing kitbash assets in viewport"""
    
    def __init__(self, state_name, scene_viewer):
        print(f"=== KitbashPlacementState.__init__ called ===")
        print(f"State name: {state_name}")
        print(f"Scene viewer: {scene_viewer}")
        
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        
        # Asset data passed from browser
        self.asset_data = None
        self.asset_file = None
        
        # Get asset data from session storage (set by UI before entering state)
        if hasattr(hou.session, 'kitbash_asset_data'):
            asset_data = hou.session.kitbash_asset_data.get('current')
            if asset_data:
                self.asset_data = asset_data
                # Database uses 'file_path' key
                self.asset_file = asset_data.get('file_path')
                print(f"Loaded asset for placement: {asset_data.get('name')}")
                print(f"Asset file path: {self.asset_file}")
        
        # Preview geometry
        self.preview_geo = None
        self.preview_drawable = None
        
        # Placement state
        self.placement_position = hou.Vector3(0, 0, 0)
        self.placement_rotation = hou.Vector3(0, 0, 0)
        self.placement_scale = hou.Vector3(1, 1, 1)
        
        # Surface alignment
        self.current_normal = hou.Vector3(0, 1, 0)
        self.placement_mode = MODE_ALIGN_TO_MESH
        
        # Kitbash node
        self.kitbash_node = None
        self.node = None
        
        # Initialize on creation
        print("Finding/creating kitbash node...")
        self.kitbash_node = self._get_or_create_kitbash_node()
        print(f"Kitbash node: {self.kitbash_node}")
        
        if self.kitbash_node:
            # Load preview geometry
            self._load_preview()
            
            # Set up drawable
            self._setup_drawable()
            
            # Show guide message
            self._update_prompt_message()
    
    def onEnter(self, kwargs):
        """Called when state is entered"""
        print("=== onEnter called ===")
        self.node = kwargs.get('node')
        print(f"Node from kwargs: {self.node}")
        
        # Get asset data from session storage
        if hasattr(hou.session, 'kitbash_asset_data'):
            asset_data = hou.session.kitbash_asset_data.get('current')
            if asset_data:
                self.asset_data = asset_data
                self.asset_file = asset_data.get('file')  # Use 'file' key from database
                print(f"Loaded asset for placement: {asset_data.get('name')}")
                print(f"Asset file path: {self.asset_file}")
        
        # Find or create kitbash node
        print("Calling _get_or_create_kitbash_node...")
        self.kitbash_node = self._get_or_create_kitbash_node()
        print(f"Kitbash node result: {self.kitbash_node}")
        
        if not self.kitbash_node:
            print("ERROR: Failed to get or create kitbash node!")
            return
        
        # Load preview geometry
        self._load_preview()
        
        # Set up drawable
        self._setup_drawable()
        
        # Show guide message
        self._update_prompt_message()
    
    def _get_or_create_kitbash_node(self):
        """Find existing pf_kitbash node or create one"""
        # Get current SOP network
        current_node = self.scene_viewer.pwd()
        print(f"Current node: {current_node.path() if current_node else 'None'}")
        print(f"Category: {current_node.childTypeCategory() if current_node else 'None'}")
        
        # If we're inside a SOP network, look for pf_kitbash nodes
        if current_node and current_node.childTypeCategory() == hou.sopNodeTypeCategory():
            # Look for existing pf_kitbash node
            for child in current_node.children():
                if child.type().name() == "pf::pf_kitbash":
                    print(f"Found existing kitbash node: {child.path()}")
                    return child
            
            # Create new pf_kitbash node
            try:
                kitbash_node = current_node.createNode("pf::pf_kitbash", "kitbash1")
                kitbash_node.moveToGoodPosition()
                kitbash_node.setDisplayFlag(True)
                kitbash_node.setRenderFlag(True)
                print(f"Created new kitbash node: {kitbash_node.path()}")
                return kitbash_node
            except Exception as e:
                print(f"Error creating kitbash node: {e}")
                return None
        else:
            # Not in a SOP network - need to navigate to /obj or create geo node
            obj_context = hou.node("/obj")
            
            # Look for existing geo node with pf_kitbash
            for geo_node in obj_context.children():
                if geo_node.type().name() == "geo":
                    for child in geo_node.children():
                        if child.type().name() == "pf::pf_kitbash":
                            print(f"Found kitbash node in {geo_node.path()}")
                            return child
            
            # Create new geo container and kitbash node
            try:
                geo_node = obj_context.createNode("geo", "kitbash_geo")
                geo_node.moveToGoodPosition()
                
                # Delete default file node
                for child in geo_node.children():
                    child.destroy()
                
                kitbash_node = geo_node.createNode("pf::pf_kitbash", "kitbash1")
                kitbash_node.setDisplayFlag(True)
                kitbash_node.setRenderFlag(True)
                
                # Set scene viewer to this node
                self.scene_viewer.setPwd(geo_node)
                
                print(f"Created new geo node with kitbash: {kitbash_node.path()}")
                return kitbash_node
            except Exception as e:
                print(f"Error creating kitbash setup: {e}")
                return None
    
    def onExit(self, kwargs):
        """Called when exiting state"""
        self._cleanup_preview()
    
    def onDraw(self, kwargs):
        """Draw in viewport"""
        # Drawable handles its own rendering, just request redraw
        handle = kwargs["draw_handle"]
        if self.preview_drawable:
            # Force viewport update
            self.scene_viewer.curViewport().draw()
    
    def onMouseEvent(self, kwargs):
        """Handle mouse events"""
        ui_event = kwargs["ui_event"]
        device = ui_event.device()
        origin, direction = ui_event.ray()
        
        # Update preview position based on mode
        if self.placement_mode == MODE_ALIGN_TO_MESH:
            # Raycast to geometry and align to surface
            hit_info = raycasting.get_geometry_under_cursor(ui_event, self.kitbash_node)
            
            if hit_info:
                self.placement_position = hit_info['position']
                self.current_normal = hit_info['normal']
                
                # Calculate rotation to align with surface
                align_matrix = raycasting.align_transform_to_normal(self.current_normal)
                self.placement_rotation = raycasting.extract_rotation_from_matrix(align_matrix)
            else:
                # Fallback to ground plane
                ground_hit = raycasting.raycast_to_ground_plane(origin, direction)
                if ground_hit:
                    self.placement_position = ground_hit
                    self.current_normal = hou.Vector3(0, 1, 0)
                    self.placement_rotation = hou.Vector3(0, 0, 0)
        
        else:  # MODE_SIMPLE_PLACEMENT
            # Raycast to geometry but only use position
            hit_info = raycasting.get_geometry_under_cursor(ui_event, self.kitbash_node)
            
            if hit_info:
                self.placement_position = hit_info['position']
            else:
                # Fallback to ground plane
                ground_hit = raycasting.raycast_to_ground_plane(origin, direction)
                if ground_hit:
                    self.placement_position = ground_hit
            
            # Keep current rotation (no alignment)
        
        # Update preview
        self._update_preview()
        
        # Left click to place
        if device.isLeftButton() and ui_event.reason() == hou.uiEventReason.Picked:
            self._place_asset()
            return True
        
        return False
    
    def onKeyEvent(self, kwargs):
        """Handle keyboard events"""
        ui_event = kwargs["ui_event"]
        key = ui_event.device().keyString()
        
        # ESC to cancel
        if key == "Escape":
            self.scene_viewer.endCurrentState()
            return True
        
        # R to rotate
        if key == "r" or key == "R":
            # Rotate 45 degrees around Y axis
            current_y = self.placement_rotation.y()
            self.placement_rotation.setY(current_y + 45)
            self._update_preview()
            return True
        
        # S to scale
        if key == "s" or key == "S":
            # Scale up/down based on shift key
            scale = self.placement_scale.x()
            if ui_event.device().isShiftKey():
                scale = scale * 1.1
            else:
                scale = scale * 0.9
            self.placement_scale = hou.Vector3(scale, scale, scale)
            self._update_preview()
            return True
        
        return False
    
    def onMenuPreOpen(self, kwargs):
        """Update menu state before opening"""
        menu_id = kwargs["menu"]
        menu_states = kwargs.get("menu_states", {})
        
        # Set current mode in menu
        if "placement_mode" in menu_states:
            menu_states["placement_mode"] = self.placement_mode
    
    def onMenuAction(self, kwargs):
        """Handle context menu selections"""
        item = kwargs["menu_item"]
        
        if item == "mode_align":
            self.placement_mode = MODE_ALIGN_TO_MESH
            self._update_prompt_message()
            return True
        
        elif item == "mode_simple":
            self.placement_mode = MODE_SIMPLE_PLACEMENT
            self._update_prompt_message()
            return True
        
        return False
    
    def _update_prompt_message(self):
        """Update viewport prompt with current mode and controls"""
        mode_name = "Align to Mesh" if self.placement_mode == MODE_ALIGN_TO_MESH else "Simple Placement"
        asset_name = self.asset_data.get('name', 'Asset') if self.asset_data else 'Asset'
        
        message = (
            f"Placing: {asset_name} | Mode: {mode_name} | "
            f"LMB: Place | R: Rotate | S: Scale | Right-click: Menu | ESC: Cancel"
        )
        self.scene_viewer.setPromptMessage(message)
    
    def onDraw(self, kwargs):
        """Draw preview in viewport"""
        handle = kwargs["draw_handle"]
        
        if self.preview_geo:
            # Draw preview geometry at current position
            # This would use the drawable geometry
            pass
    
    def _load_preview(self):
        """Load asset geometry for preview"""
        if not self.asset_file:
            print("No asset file to load")
            return
        
        print(f"Loading preview from: {self.asset_file}")
        
        # Create geometry container
        self.preview_geo = hou.Geometry()
        
        # Load geometry based on file type
        import os
        if os.path.exists(self.asset_file):
            ext = os.path.splitext(self.asset_file)[1].lower()
            
            if ext in ['.usd', '.usda', '.usdc']:
                # Load USD by creating temporary node
                try:
                    # Create temp geometry container
                    temp_geo = hou.node("/obj").createNode("geo", "temp_usd_loader")
                    
                    # Delete default file node
                    for child in temp_geo.children():
                        child.destroy()
                    
                    # Create USD import node
                    usd_node = temp_geo.createNode("usdimport")
                    usd_node.parm("filepath").set(self.asset_file)
                    usd_node.cook(force=True)
                    
                    # Copy geometry
                    self.preview_geo = usd_node.geometry().freeze()
                    
                    # Clean up
                    temp_geo.destroy()
                    
                    print(f"Loaded USD: {self.preview_geo.intrinsicValue('pointcount')} points")
                except Exception as e:
                    print(f"USD load failed: {e}")
                    import traceback
                    traceback.print_exc()
                    self._create_placeholder_geo()
            
            elif ext in ['.obj', '.fbx', '.bgeo', '.geo']:
                # Load via file verb
                try:
                    file_verb = hou.sopNodeTypeCategory().nodeVerb("file")
                    file_verb.setParms({"file": self.asset_file})
                    file_verb.execute(self.preview_geo, [])
                    print(f"Loaded file: {self.preview_geo.intrinsicValue('pointcount')} points")
                except Exception as e:
                    print(f"File load failed: {e}")
                    self._create_placeholder_geo()
            else:
                print(f"Unsupported file type: {ext}")
                self._create_placeholder_geo()
        else:
            print(f"File not found: {self.asset_file}")
            self._create_placeholder_geo()
    
    def _create_placeholder_geo(self):
        """Create placeholder box geometry"""
        box = hou.sopNodeTypeCategory().nodeVerb("box")
        box.execute(self.preview_geo, [])
        print("Created placeholder box geometry")
    
    def _setup_drawable(self):
        """Set up viewport drawable for preview"""
        if not self.preview_geo:
            print("No preview geometry to draw")
            return
        
        try:
            # Create drawable that will render in viewport
            self.preview_drawable = hou.GeometryDrawable(
                self.scene_viewer,
                hou.drawableGeometryType.Face,
                "kitbash_preview"
            )
            self.preview_drawable.setGeometry(self.preview_geo)
            self.preview_drawable.show(True)
            self._update_preview()  # Set initial transform
            print("Preview drawable created")
        except Exception as e:
            print(f"Error creating drawable: {e}")
            import traceback
            traceback.print_exc()
    
    def _update_preview(self):
        """Update preview transform"""
        if not self.preview_drawable:
            return
        
        # Build transform matrix
        translate = hou.hmath.buildTranslate(self.placement_position)
        
        # Convert rotation vector (degrees) to matrix
        rotate_x = hou.hmath.buildRotate(self.placement_rotation.x(), 0, 0)
        rotate_y = hou.hmath.buildRotate(0, self.placement_rotation.y(), 0)
        rotate_z = hou.hmath.buildRotate(0, 0, self.placement_rotation.z())
        rotate = rotate_z * rotate_y * rotate_x
        
        # Scale
        scale = hou.hmath.buildScale(self.placement_scale)
        
        # Combined transform
        transform = translate * rotate * scale
        
        self.preview_drawable.setTransform(transform)
    
    def _place_asset(self):
        """Add asset to kitbash node"""
        print(f"=== _place_asset called ===")
        print(f"Kitbash node: {self.kitbash_node}")
        
        if not self.kitbash_node:
            print("Error: No kitbash node found")
            return
        
        # Add new asset entry to multiparm (parameter name is 'num_meshes')
        num_meshes_parm = self.kitbash_node.parm("num_meshes")
        if not num_meshes_parm:
            print("Error: num_meshes parameter not found on kitbash node")
            return
        
        num_meshes = num_meshes_parm.eval()
        num_meshes_parm.set(num_meshes + 1)
        
        # Set parameters for new asset (indices start at 1)
        idx = num_meshes + 1
        
        # File path
        file_parm = self.kitbash_node.parm(f"file{idx}")
        if file_parm:
            file_parm.set(self.asset_file)
        
        # Position (t#)
        t_parm = self.kitbash_node.parmTuple(f"t{idx}")
        if t_parm:
            t_parm.set(tuple(self.placement_position))
        
        # Rotation (r#)
        r_parm = self.kitbash_node.parmTuple(f"r{idx}")
        if r_parm:
            r_parm.set(tuple(self.placement_rotation))
        
        # Scale (scale#) - single float parameter
        scale_parm = self.kitbash_node.parm(f"scale{idx}")
        if scale_parm:
            # Use uniform scale (X component)
            scale_parm.set(self.placement_scale.x())
        
        # Force recook
        self.kitbash_node.cook(force=True)
        
        asset_name = self.asset_data.get('name', 'Unknown') if self.asset_data else 'Unknown'
        print(f"Placed asset: {asset_name} at {self.placement_position}")
        
        # Reset for next placement
        self.placement_rotation = hou.Vector3(0, 0, 0)
        self.placement_scale = hou.Vector3(1, 1, 1)
    
    def _cleanup_preview(self):
        """Clean up preview geometry"""
        if self.preview_drawable:
            self.preview_drawable = None
        if self.preview_geo:
            self.preview_geo.clear()
            self.preview_geo = None


def createViewerStateTemplate():
    """Register the state with Houdini"""
    state_name = "polyfactory.kitbash_placement"
    state_label = "PolyFactory Kitbash Placement"
    state_category = hou.sopNodeTypeCategory()
    
    template = hou.ViewerStateTemplate(state_name, state_label, state_category)
    template.bindFactory(KitbashPlacementState)
    
    # Create context menu
    menu = hou.ViewerStateMenu("kitbash_placement_menu", "Kitbash Placement")
    
    # Add mode selection submenu
    menu.addRadioStrip("placement_mode", "Placement Mode", "mode_align")
    menu.addRadioStripItem("placement_mode", "mode_align", "Align to Mesh")
    menu.addRadioStripItem("placement_mode", "mode_simple", "Simple Placement")
    
    template.bindMenu(menu)
    
    return template
