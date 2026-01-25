"""
Kitbash Placement State - Interactive viewport placement for assets
"""

import hou
import viewerstate.utils as su


class KitbashPlacementState(object):
    """Interactive state for placing kitbash assets in viewport"""
    
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        
        # Asset data passed from browser
        self.asset_data = None
        self.asset_file = None
        
        # Preview geometry
        self.preview_geo = None
        self.preview_drawable = None
        
        # Placement state
        self.placement_position = hou.Vector3(0, 0, 0)
        self.placement_rotation = hou.Vector3(0, 0, 0)
        self.placement_scale = hou.Vector3(1, 1, 1)
        
        # Kitbash node
        self.kitbash_node = None
    
    def onEnter(self, kwargs):
        """Called when state is entered"""
        # Get asset data from kwargs if provided
        if 'asset_data' in kwargs:
            import json
            self.asset_data = json.loads(kwargs['asset_data'])
            self.asset_file = self.asset_data.get('file_path', '')
        
        # Find or create kitbash node
        self.kitbash_node = self._get_or_create_kitbash_node()
        
        # Load preview geometry
        self._load_preview()
        
        # Set up drawable
        self._setup_drawable()
        
        # Show guide message
        self.scene_viewer.setPromptMessage("Click to place asset, R to rotate, S to scale, ESC to cancel")
    
    def onExit(self, kwargs):
        """Called when exiting state"""
        self._cleanup_preview()
    
    def onMouseEvent(self, kwargs):
        """Handle mouse events"""
        ui_event = kwargs["ui_event"]
        device = ui_event.device()
        
        # Get mouse position in viewport
        origin, direction = ui_event.ray()
        
        # Raycast to ground plane (Y=0)
        if direction.y() != 0:
            t = -origin.y() / direction.y()
            if t > 0:
                hit_point = origin + direction * t
                self.placement_position = hit_point
                
                # Update preview position
                if self.preview_drawable:
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
            self.placement_rotation.setY(self.placement_rotation.y() + 45)
            self._update_preview()
            return True
        
        # S to scale
        if key == "s" or key == "S":
            scale = self.placement_scale.x()
            scale = scale * 1.1 if ui_event.device().isShiftKey() else scale * 0.9
            self.placement_scale = hou.Vector3(scale, scale, scale)
            self._update_preview()
            return True
        
        return False
    
    def onDraw(self, kwargs):
        """Draw preview in viewport"""
        handle = kwargs["draw_handle"]
        
        if self.preview_geo:
            # Draw preview geometry at current position
            # This would use the drawable geometry
            pass
    
    def _get_or_create_kitbash_node(self):
        """Find or create the kitbash container node"""
        # Get current geometry network
        network_editor = self.scene_viewer.networkEditor()
        if network_editor:
            pwd = network_editor.pwd()
            
            # Look for existing kitbash node
            for node in pwd.children():
                if node.type().name() == "pf_kitbash":
                    return node
            
            # Create new one
            kitbash = pwd.createNode("pf_kitbash", "kitbash")
            kitbash.moveToGoodPosition()
            return kitbash
        
        return None
    
    def _load_preview(self):
        """Load asset geometry for preview"""
        if not self.asset_file:
            return
        
        # Create temporary geometry container
        # In practice, we'd load the USD file
        # For now, create a simple box as placeholder
        self.preview_geo = hou.Geometry()
        box = hou.sopNodeTypeCategory().nodeVerb("box")
        box.execute(self.preview_geo, [])
    
    def _setup_drawable(self):
        """Set up viewport drawable for preview"""
        # TODO: Create drawable geometry
        # This requires using hou.GeometryDrawable
        pass
    
    def _update_preview(self):
        """Update preview transform"""
        # Update drawable position/rotation/scale
        # This will be called when mouse moves or transform changes
        pass
    
    def _place_asset(self):
        """Add asset to kitbash node"""
        if not self.kitbash_node:
            return
        
        # Add new asset entry to multiparm
        num_assets = self.kitbash_node.evalParm("num_assets")
        self.kitbash_node.parm("num_assets").set(num_assets + 1)
        
        # Set parameters for new asset
        idx = num_assets + 1
        self.kitbash_node.parm(f"file{idx}").set(self.asset_file)
        self.kitbash_node.parmTuple(f"t{idx}").set(self.placement_position)
        self.kitbash_node.parmTuple(f"r{idx}").set(self.placement_rotation)
        self.kitbash_node.parmTuple(f"s{idx}").set(self.placement_scale)
        self.kitbash_node.parm(f"enable{idx}").set(True)
        
        # Force recook
        self.kitbash_node.cook(force=True)
        
        print(f"Placed asset: {self.asset_data.get('name', 'Unknown')} at {self.placement_position}")
        
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
    
    # Bind to pf_kitbash node type
    template.bindAsDefault(True)
    
    return template
