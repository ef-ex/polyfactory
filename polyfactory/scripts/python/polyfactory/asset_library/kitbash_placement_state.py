"""
Kitbash Placement State - Interactive viewport placement for assets

NEW WORKFLOW:
1. HDA has 'library' multiparm with lMesh# paths (setup by user)
2. HDA displays library meshes in viewport  
3. Enter state with Enter key (not double-click)
4. Click library mesh → sets currentMesh parameter and currentActive=true
5. Click to place → adds to multiparm, clears currentMesh, sets currentActive=false
6. HDA handles all geometry loading and preview rendering
"""

import hou
import viewerstate.utils as su


# Placement modes
MODE_ALIGN_TO_MESH = "align_to_mesh"
MODE_SIMPLE_PLACEMENT = "simple_placement"


class KitbashPlacementState(object):
    """Interactive state for placing kitbash assets in viewport"""
    
    def __init__(self, state_name, scene_viewer):
        self.state_name = state_name
        self.scene_viewer = scene_viewer
        
        # Placement state
        self.placement_position = hou.Vector3(0, 0, 0)
        self.placement_rotation = hou.Vector3(0, 0, 0)
        self.placement_scale = hou.Vector3(1, 1, 1)
        
        # Surface alignment  
        self.current_normal = hou.Vector3(0, 1, 0)
        self.placement_mode = MODE_ALIGN_TO_MESH
        
        # Kitbash node (from state context)
        self.kitbash_node = None
        self.node = None
    
    def onEnter(self, kwargs):
        """Called when state is entered"""
        self.node = kwargs.get('node')
        
        # Find kitbash node from current context
        current_node = self.scene_viewer.pwd()
        if current_node and current_node.childTypeCategory() == hou.sopNodeTypeCategory():
            # Look for pf_kitbash node
            for child in current_node.children():
                if child.type().name() == "pf::pf_kitbash":
                    self.kitbash_node = child
                    break
        
        if not self.kitbash_node:
            hou.ui.displayMessage("No pf_kitbash node found in current network", 
                                severity=hou.severityType.Warning)
            return
        
        print(f"Kitbash mode active on: {self.kitbash_node.path()}")
        self._update_prompt_message()
    
    def onExit(self, kwargs):
        """Called when exiting state"""
        # Deactivate placement mode
        if self.kitbash_node:
            active_parm = self.kitbash_node.parm("currentActive")
            if active_parm:
                active_parm.set(False)
    
    def onDraw(self, kwargs):
        """Draw in viewport - HDA handles preview rendering"""
        pass
    
    def onMouseEvent(self, kwargs):
        """Handle mouse events"""
        ui_event = kwargs["ui_event"]
        device = ui_event.device()
        reason = ui_event.reason()
        
        # Left click
        if device.isLeftButton() and reason == hou.uiEventReason.Picked:
            # Check if currentActive is true (mesh selected for placement)
            active_parm = self.kitbash_node.parm("currentActive")
            current_mesh_parm = self.kitbash_node.parm("currentMesh")
            
            if active_parm and active_parm.eval():
                # Mesh is selected - place it
                if current_mesh_parm and current_mesh_parm.eval():
                    self._place_current_mesh(ui_event)
                    return True
            else:
                # No mesh selected - check if clicking on library mesh
                self._select_library_mesh(ui_event)
                return True
        
        return False
    
    def _select_library_mesh(self, ui_event):
        """Detect click on library mesh and set currentMesh parameter"""
        # Get geometry under cursor
        origin, direction = ui_event.ray()
        
        # Raycast to find geometry
        position, normal, prim_num, prim_uvw = self.kitbash_node.geometry().intersect(origin, direction)
        
        if prim_num >= 0:
            # Hit geometry - check if it's a library mesh
            prim = self.kitbash_node.geometry().prim(prim_num)
            
            # Check for mesh_index attribute (HDA should set this on library meshes)
            if prim.hasAttrib("mesh_index"):
                mesh_index = prim.attribValue("mesh_index")
                
                # Get library mesh path from multiparm
                library_parm = self.kitbash_node.parm(f"lMesh{mesh_index}")
                if library_parm:
                    mesh_path = library_parm.eval()
                    
                    # Set currentMesh and activate
                    current_mesh_parm = self.kitbash_node.parm("currentMesh")
                    active_parm = self.kitbash_node.parm("currentActive")
                    
                    if current_mesh_parm and active_parm:
                        current_mesh_parm.set(mesh_path)
                        active_parm.set(True)
                        print(f"Selected library mesh: {mesh_path}")
                        self._update_prompt_message()
    
    def _place_current_mesh(self, ui_event):
        """Place the currently selected mesh at cursor position"""
        # Get current mesh path
        current_mesh_parm = self.kitbash_node.parm("currentMesh")
        if not current_mesh_parm:
            return
        
        mesh_path = current_mesh_parm.eval()
        if not mesh_path:
            return
        
        # Get placement position from raycast
        origin, direction = ui_event.ray()
        position, normal, prim_num, prim_uvw = self.kitbash_node.geometry().intersect(origin, direction)
        
        if prim_num >= 0:
            self.placement_position = position
            self.current_normal = normal
        else:
            # Fallback to ground plane
            ground_y = 0.0
            t = (ground_y - origin.y()) / direction.y()
            if t > 0:
                self.placement_position = origin + direction * t
                self.current_normal = hou.Vector3(0, 1, 0)
        
        # Calculate rotation based on mode
        if self.placement_mode == MODE_ALIGN_TO_MESH:
            # Align to surface normal (simplified - just point Y up along normal)
            up = self.current_normal
            # Create rotation from up vector (this is simplified, real implementation needs proper matrix)
            # For now, use identity rotation
            self.placement_rotation = hou.Vector3(0, 0, 0)
        
        # Add to placement multiparm
        num_meshes_parm = self.kitbash_node.parm("num_meshes")
        if not num_meshes_parm:
            print("Error: num_meshes parameter not found")
            return
        
        num_meshes = num_meshes_parm.eval()
        new_index = num_meshes + 1
        
        # Add new instance
        num_meshes_parm.set(new_index)
        
        # Set parameters for new instance
        file_parm = self.kitbash_node.parm(f"file{new_index}")
        t_parm = self.kitbash_node.parmTuple(f"t{new_index}")
        r_parm = self.kitbash_node.parmTuple(f"r{new_index}")
        scale_parm = self.kitbash_node.parm(f"scale{new_index}")
        
        if file_parm:
            file_parm.set(mesh_path)
        if t_parm:
            t_parm.set(self.placement_position)
        if r_parm:
            r_parm.set(self.placement_rotation)
        if scale_parm:
            scale_parm.set(self.placement_scale.x())
        
        print(f"Placed mesh: {mesh_path} at {self.placement_position}")
        
        # Deactivate placement mode
        active_parm = self.kitbash_node.parm("currentActive")
        if active_parm:
            active_parm.set(False)
        current_mesh_parm.set("")
        
        self._update_prompt_message()
    
    def onKeyEvent(self, kwargs):
        """Handle keyboard events"""
        ui_event = kwargs["ui_event"]
        device = ui_event.device()
        
        # Mouse wheel for scale
        if device.isMouseWheel():
            # Scale up/down based on shift key
            scale = self.placement_scale.x()
            if ui_event.device().isShiftKey():
                scale = scale * 1.1
            else:
                scale = scale * 0.9
            self.placement_scale = hou.Vector3(scale, scale, scale)
            return True
        
        # ESC to cancel current selection
        if ui_event.key() == "Escape":
            current_mesh_parm = self.kitbash_node.parm("currentMesh")
            active_parm = self.kitbash_node.parm("currentActive")
            if current_mesh_parm and active_parm:
                current_mesh_parm.set("")
                active_parm.set(False)
                self._update_prompt_message()
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
        if not self.kitbash_node:
            return
        
        mode_name = "Align to Mesh" if self.placement_mode == MODE_ALIGN_TO_MESH else "Simple Placement"
        
        # Check if mesh is selected
        active_parm = self.kitbash_node.parm("currentActive")
        current_mesh_parm = self.kitbash_node.parm("currentMesh")
        
        if active_parm and active_parm.eval() and current_mesh_parm:
            mesh_name = current_mesh_parm.eval().split('/')[-1]
            message = f"Placing: {mesh_name} | Mode: {mode_name} | LMB: Place | ESC: Cancel | Wheel: Scale"
        else:
            message = f"Kitbash Mode | Mode: {mode_name} | LMB: Select library mesh | ESC: Exit"
        
        self.scene_viewer.setPromptMessage(message)


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
