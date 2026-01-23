"""
Turntable Renderer - Creates rotating preview animations for assets
"""

import hou
import os
import math
from typing import Optional


class TurntableRenderer:
    """Renders turntable animations for asset previews"""
    
    def __init__(self):
        self.temp_nodes = []
        self.temp_panes = []  # Store temporary panes/windows for cleanup
    
    def render_turntable(self, geo_node: hou.SopNode, output_dir: str, 
                        num_frames: int = 36, asset_usd_path: str = None) -> bool:
        """Render a turntable animation of the geometry
        
        Args:
            geo_node: Geometry node to render (can be None if asset_usd_path is provided)
            output_dir: Directory to save frames
            num_frames: Number of frames (360 / num_frames = degrees per frame)
            asset_usd_path: Path to USD asset file (alternative to geo_node)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create render scene
            render_setup = self._create_render_scene(geo_node, num_frames, asset_usd_path)
            if not render_setup:
                return False
            
            lop_net, cam_node = render_setup

            
            # Render frames using Vulkan flipbook
            success = self._render_frames(lop_net, cam_node, output_dir, num_frames)
            
            # Cleanup temporary nodes and windows
            self._cleanup()
            
            return success
            
        except Exception as e:
            import traceback
            print(f"Error during turntable render: {e}")
            traceback.print_exc()
            self._cleanup()
            return False
    
    def _create_render_scene(self, geo_node: hou.SopNode, num_frames: int, asset_usd_path: str = None):
        """Create a temporary USD render scene with geometry, camera, and lights
        
        Args:
            geo_node: Source geometry node (can be None if asset_usd_path is provided)
            num_frames: Number of frames for animation
            asset_usd_path: Path to USD asset file
            
        Returns:
            Tuple of (lop_network, camera_node) or None on error
        """
        try:
            obj_network = hou.node('/obj')
            
            # Create LOP network for rendering
            lop_net = obj_network.createNode('lopnet', 'turntable_stage')
            self.temp_nodes.append(lop_net)
            
            # Load lighting template as sublayer (contains render settings)
            lighting_template = os.path.join(
                os.environ.get('POLYFACTORY', ''), 
                'library', 
                'lighting_template.usda'
            )
            
            if os.path.exists(lighting_template):
                sublayer = lop_net.createNode('sublayer', 'lighting')
                sublayer.parm('filepath1').set(lighting_template)
                last_node = sublayer
            else:
                raise FileNotFoundError(f"Lighting template not found: {lighting_template}")
                last_node = None
            
            # Import asset geometry
            if asset_usd_path and os.path.exists(asset_usd_path):
                # Load USD asset
                ref_asset = lop_net.createNode('reference', 'asset')
                if last_node:
                    ref_asset.setInput(0, last_node)
                ref_asset.parm('filepath1').set(asset_usd_path)
                ref_asset.parm('primpath1').set('/asset')
                last_node = ref_asset
                
            elif geo_node:
                # Import from SOP
                sop_import = lop_net.createNode('sopimport', 'asset')
                if last_node:
                    sop_import.setInput(0, last_node)
                sop_import.parm('soppath').set(geo_node.path())
                sop_import.parm('pathprefix').set('/asset')
                last_node = sop_import
            else:
                raise ValueError("No geometry source provided")
            
            # Get bounding box for camera framing
            last_node.cook()
            stage = last_node.stage()
            
            # Compute bounds using USD BBoxCache
            from pxr import UsdGeom, Gf, Usd
            
            # Create a bounding box cache
            bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
            
            # Get the root prim and compute its bounding box
            root = stage.GetPseudoRoot()
            bbox = bbox_cache.ComputeWorldBound(root)
            bbox_range = bbox.ComputeAlignedRange()
            
            center = bbox_range.GetMidpoint()
            size = bbox_range.GetSize()
            max_size = max(size[0], size[1], size[2])
            
            # Set camera distance based on bounding box
            # Camera is already in lighting template at /cameras/anim/rotate/turntable_cam
            distance = max_size * 3.0
            
            python_node = lop_net.createNode('pythonscript', 'set_camera_distance')
            python_node.setInput(0, last_node)
            
            python_code = f"""
from pxr import UsdGeom, Gf

stage = hou.pwd().editableStage()
cam_prim = stage.GetPrimAtPath('/cameras/anim/rotate/turntable_cam')
if cam_prim:
    xformable = UsdGeom.Xformable(cam_prim)
    ops = xformable.GetOrderedXformOps()
    if ops:
        xform_op = ops[0]
        if xform_op.GetOpType() == UsdGeom.XformOp.TypeTransform:
            matrix = xform_op.Get()
            matrix.SetTranslateOnly(Gf.Vec3d(0, 0, {distance}))
            xform_op.Set(matrix)
        elif xform_op.GetOpType() == UsdGeom.XformOp.TypeTranslate:
            current_val = xform_op.Get()
            xform_op.Set(Gf.Vec3d(current_val[0], current_val[1], {distance}))
"""
            python_node.parm('python').set(python_code)
            
            last_node = python_node
            
            # Reset to first frame
            hou.setFrame(1)
            
            # Set frame range
            hou.playbar.setFrameRange(1, num_frames)
            hou.playbar.setPlaybackRange(1, num_frames)
            
            return lop_net, last_node
            
        except Exception as e:
            print(f"Error creating render scene: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    
    def _render_frames(self, lop_net, cam_node, output_dir, num_frames):
        """Render frames using USD Render ROP or OpenGL fallback
        
        Args:
            lop_net: LOP network containing scene
            cam_node: Camera to render from
            output_dir: Output directory
            num_frames: Number of frames
            
        Returns:
            True if successful
        """
        try:
            # Create render node in /out context
            rop_context = hou.node('/out')
            if not rop_context:
                rop_context = hou.node('/').createNode('out')
            
            # Set output path for image sequence
            output_path = os.path.join(output_dir, 'frame_$F4.png').replace('\\', '/')
            
            # Camera path from lighting template
            cam_path = '/cameras/anim/rotate/turntable_cam'
            
            # Create a new floating panel with a scene viewer
            desktop = hou.ui.curDesktop()
            
            # Create a floating panel
            floating_panel = desktop.createFloatingPanel(hou.paneTabType.SceneViewer)
            self.temp_panes.append(floating_panel)
            
            # Get the scene viewer pane tab from the floating panel
            scene_viewer = floating_panel.panes()[0].tabs()[0]
            
            # Set the scene viewer to display the LOP network
            scene_viewer.setPwd(lop_net)
            
            # Set the display node to the last node in the network
            cam_node.setDisplayFlag(True)
            
            # Wait a moment for the scene viewer to initialize
            import time
            time.sleep(0.5)
            
            # Get viewport to configure it
            viewport = scene_viewer.curViewport()
            
            # Configure viewport settings
            settings = viewport.settings()
            
            # Hide reference plane
            refPlane = scene_viewer.referencePlane()
            refPlane.setIsVisible(False)
            
            # Set camera and hide guides
            viewport.setCamera(cam_path)
            scene_viewer.setShowCameras(False)
            scene_viewer.setShowLights(False)
            scene_viewer.setShowSelection(False)
            
            # Enable high quality rendering
            settings.setLighting(hou.viewportLighting.HighQualityWithShadows)
            settings.setUseRayTracing(True)
            settings.setAmbientOcclusion(True)
            
            # Configure flipbook settings
            flipbook_settings = scene_viewer.flipbookSettings().stash()
            flipbook_settings.beautyPassOnly(True)
            flipbook_settings.frameRange((1, num_frames))
            flipbook_settings.output(output_path)
            flipbook_settings.resolution((512, 512))
            flipbook_settings.useResolution(True)
            
            # Set flipbook to use the current session (not background)
            flipbook_settings.outputToMPlay(False)
            
            # Make sure we're starting at frame 1
            hou.setFrame(1)
            
            # Execute flipbook
            scene_viewer.flipbook(viewport, flipbook_settings)
            
            return True
            
        except Exception as e:
            print(f"Error rendering frames: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _cleanup(self):
        """Remove temporary nodes and panes"""
        for node in self.temp_nodes:
            try:
                node.destroy()
            except:
                pass
        self.temp_nodes = []
        
        for pane in self.temp_panes:
            try:
                pane.close()
            except:
                pass
        self.temp_panes = []
