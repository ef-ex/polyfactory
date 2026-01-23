"""
Turntable Renderer - Creates rotating preview animations for assets
"""

import hou
import os
from typing import Optional, List, Tuple


def render_turntable(geo_node: hou.SopNode, output_dir: str, 
                    num_frames: int = 36, asset_usd_path: str = None, debug: bool = False) -> bool:
    """Render a turntable animation of the geometry
    
    Args:
        geo_node: Geometry node to render (can be None if asset_usd_path is provided)
        output_dir: Directory to save frames
        num_frames: Number of frames (360 / num_frames = degrees per frame)
        asset_usd_path: Path to USD asset file (alternative to geo_node)
        debug: Enable debug print statements
        
    Returns:
        True if successful, False otherwise
    """
    temp_nodes = []
    temp_panes = []
    
    try:
        # Create render scene
        render_setup = _create_render_scene(geo_node, num_frames, asset_usd_path, temp_nodes, debug=debug)
        if not render_setup:
            return False
        
        lop_net, cam_node = render_setup
        
        # Render frames using Vulkan flipbook
        success = _render_frames(lop_net, cam_node, output_dir, num_frames, temp_panes, debug=debug)
        
        # Cleanup temporary nodes and windows
        _cleanup(temp_nodes, temp_panes)
        
        return success
        
    except Exception as e:
        import traceback
        print(f"Error during turntable render: {e}")
        traceback.print_exc()
        _cleanup(temp_nodes, temp_panes)
        return False


def _create_render_scene(geo_node: hou.SopNode, num_frames: int, 
                        asset_usd_path: str, temp_nodes: List, debug: bool = False) -> Optional[Tuple]:
    """Create a temporary USD render scene with geometry, camera, and lights
    
    Args:
        geo_node: Source geometry node (can be None if asset_usd_path is provided)
        num_frames: Number of frames for animation
        asset_usd_path: Path to USD asset file
        temp_nodes: List to track temporary nodes
        debug: Enable debug print statements
        
    Returns:
        Tuple of (lop_network, camera_node) or None on error
    """
    try:
        obj_network = hou.node('/obj')
        
        # Create LOP network for rendering
        lop_net = obj_network.createNode('lopnet', 'turntable_stage')
        temp_nodes.append(lop_net)
        
        # Load lighting template as sublayer
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
        
        # Import asset geometry
        if asset_usd_path and os.path.exists(asset_usd_path):
            # Load USD asset
            ref_asset = lop_net.createNode('reference', 'asset')
            ref_asset.setInput(0, last_node)
            ref_asset.parm('filepath1').set(asset_usd_path)
            ref_asset.parm('primpath1').set('/asset')
            last_node = ref_asset
            
        elif geo_node:
            # Import from SOP
            sop_import = lop_net.createNode('sopimport', 'asset')
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
        
        bbox_cache = UsdGeom.BBoxCache(Usd.TimeCode.Default(), [UsdGeom.Tokens.default_])
        root = stage.GetPseudoRoot()
        bbox = bbox_cache.ComputeWorldBound(root)
        bbox_range = bbox.ComputeAlignedRange()
        
        size = bbox_range.GetSize()
        max_size = max(size[0], size[1], size[2])
        distance = max_size * 3.0
        
        # Set camera distance
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


def _render_frames(lop_net, cam_node, output_dir: str, num_frames: int, temp_panes: List, debug: bool = False) -> bool:
    """Render frames using viewport flipbook
    
    Args:
        lop_net: LOP network containing scene
        cam_node: Camera to render from
        output_dir: Output directory
        num_frames: Number of frames
        temp_panes: List to track temporary panes
        debug: Enable debug print statements
        
    Returns:
        True if successful
    """
    try:
        # Set output path
        output_path = os.path.join(output_dir, 'frame_$F4.png').replace('\\', '/')
        cam_path = '/cameras/anim/rotate/turntable_cam'
        
        # Create floating panel with scene viewer
        desktop = hou.ui.curDesktop()
        floating_panel = desktop.createFloatingPanel(hou.paneTabType.SceneViewer)
        temp_panes.append(floating_panel)
        
        scene_viewer = floating_panel.panes()[0].tabs()[0]
        scene_viewer.setPwd(lop_net)
        cam_node.setDisplayFlag(True)
        
        # Wait for scene viewer to initialize
        import time
        time.sleep(0.5)
        
        # Configure viewport
        viewport = scene_viewer.curViewport()
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
        
        # Configure flipbook
        flipbook_settings = scene_viewer.flipbookSettings().stash()
        flipbook_settings.beautyPassOnly(True)
        flipbook_settings.frameRange((1, num_frames))
        flipbook_settings.output(output_path)
        flipbook_settings.resolution((512, 512))
        flipbook_settings.useResolution(True)
        flipbook_settings.outputToMPlay(False)
        
        # Execute flipbook
        hou.setFrame(1)
        scene_viewer.flipbook(viewport, flipbook_settings)
        
        return True
        
    except Exception as e:
        print(f"Error rendering frames: {e}")
        import traceback
        traceback.print_exc()
        return False


def _cleanup(temp_nodes: List, temp_panes: List):
    """Remove temporary nodes and panes
    
    Args:
        temp_nodes: List of nodes to destroy
        temp_panes: List of panes to close
    """
    for node in temp_nodes:
        try:
            node.destroy()
        except:
            pass
    
    for pane in temp_panes:
        try:
            pane.close()
        except:
            pass
