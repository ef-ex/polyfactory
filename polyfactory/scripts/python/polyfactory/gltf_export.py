"""
glTF Export Utilities

Export Houdini models to glTF/GLB with null node names preserved.
Fixes Houdini's glTF exporter bug where null node names are lost during export.

General-purpose utility for any workflow requiring named null/empty nodes in glTF output.

TODO: UNTESTED - Needs validation with real module exports
TODO: Add transform-based matching as fallback for node ordering
TODO: Add unit tests
"""

import hou
from pygltflib import GLTF2
from typing import List, Dict, Optional
import os


def export_module_with_connection_points(
    geometry_node: hou.Node,
    output_path: str,
    connection_point_pattern: str = "*connection*"
) -> bool:
    """
    Export module to GLB with connection points preserved.
    
    Workflow:
    1. Export from Houdini to GLB (loses null names)
    2. Extract connection point data from Houdini scene
    3. Post-process GLB to restore null names
    4. Save corrected GLB file
    
    Args:
        geometry_node: SOP node containing module geometry
        output_path: Output .glb file path
        connection_point_pattern: Pattern to match connection point nulls
        
    Returns:
        True if export successful, False otherwise
        
    Example:
        >>> geo = hou.node("/obj/module_chassis/OUT")
        >>> export_module_with_connection_points(geo, "D:/galaxia/assets/chassis_basic.glb")
    """
    try:
        # 1. Export to GLB using Houdini ROP
        if not _export_gltf_from_houdini(geometry_node, output_path):
            return False
        
        # 2. Extract connection point metadata from Houdini
        connection_data = _extract_connection_points(geometry_node, connection_point_pattern)
        
        if not connection_data:
            print(f"Warning: No connection points found matching '{connection_point_pattern}'")
            return True  # Still valid export, just no connection points
        
        # 3. Post-process GLB to fix null names
        _fix_gltf_null_names(output_path, connection_data)
        
        print(f"✓ Exported {output_path} with {len(connection_data)} connection points")
        return True
        
    except Exception as e:
        print(f"✗ Export failed: {str(e)}")
        return False


def _export_gltf_from_houdini(geometry_node: hou.Node, output_path: str) -> bool:
    """Export geometry to glTF using Houdini's ROP"""
    # Create temporary ROP gltf node
    obj_context = hou.node("/obj")
    rop = obj_context.createNode("rop_gltf", "temp_gltf_export")
    
    try:
        # Configure ROP
        rop.parm("soppath").set(geometry_node.path())
        rop.parm("file").set(output_path)
        rop.parm("exportformat").set("glb")  # Binary format
        
        # Execute export
        rop.render()
        
        # Verify file was created
        if not os.path.exists(output_path):
            print(f"✗ GLB file not created: {output_path}")
            return False
            
        return True
        
    finally:
        # Cleanup temporary ROP
        rop.destroy()


def _extract_connection_points(geometry_node: hou.Node, pattern: str) -> List[Dict]:
    """
    Extract connection point data from Houdini scene.
    
    Looks for null objects in the scene hierarchy matching the pattern.
    Connection points are typically null nodes with specific naming.
    
    Returns list of dicts with:
        - name: Node name (e.g., "connection_top", "connection_bottom")
        - transform: World transform matrix
        - node_index: Index in scene hierarchy (for GLB matching)
    """
    connection_points = []
    
    # Walk up to find parent OBJ node
    obj_node = geometry_node
    while obj_node and obj_node.type().category().name() != "Object":
        obj_node = obj_node.parent()
    
    if not obj_node:
        print("Warning: Could not find parent OBJ context")
        return []
    
    # Find all children matching pattern
    for child in obj_node.children():
        if child.type().name() == "null" and hou.patternMatch(pattern, child.name()):
            connection_points.append({
                "name": child.name(),
                "transform": child.worldTransform().asTuple(),
                "node_index": len(connection_points)  # Track order
            })
            print(f"  Found connection point: {child.name()}")
    
    return connection_points


def _fix_gltf_null_names(gltf_path: str, connection_data: List[Dict]) -> None:
    """
    Post-process GLB file to restore null node names.
    
    Houdini's glTF exporter creates unnamed nodes for nulls.
    This function matches them to our connection point data and restores names.
    """
    # Load GLB
    gltf = GLTF2().load(gltf_path)
    
    # Find nodes without meshes (nulls/empties)
    null_nodes = []
    for i, node in enumerate(gltf.nodes):
        if node.mesh is None:
            null_nodes.append(i)
    
    if len(null_nodes) != len(connection_data):
        print(f"Warning: Found {len(null_nodes)} null nodes but have {len(connection_data)} connection points")
        print("  Matching by order may be inaccurate")
    
    # Match by order and restore names
    # TODO: Could match by transform similarity for more robustness
    for i, null_index in enumerate(null_nodes):
        if i < len(connection_data):
            gltf.nodes[null_index].name = connection_data[i]["name"]
            print(f"  Restored name: {connection_data[i]['name']}")
    
    # Save modified GLB
    gltf.save(gltf_path)


def batch_export_modules(module_definitions: List[Dict], output_dir: str) -> None:
    """
    Batch export multiple modules.
    
    Args:
        module_definitions: List of dicts with 'node_path', 'output_name', 'pattern'
        output_dir: Output directory for GLB files
        
    Example:
        >>> modules = [
        ...     {"node_path": "/obj/chassis_basic/OUT", "output_name": "chassis_basic.glb"},
        ...     {"node_path": "/obj/reactor_small/OUT", "output_name": "reactor_small.glb"}
        ... ]
        >>> batch_export_modules(modules, "D:/galaxia/assets/models/")
    """
    os.makedirs(output_dir, exist_ok=True)
    
    success_count = 0
    for module_def in module_definitions:
        node = hou.node(module_def["node_path"])
        if not node:
            print(f"✗ Node not found: {module_def['node_path']}")
            continue
            
        output_path = os.path.join(output_dir, module_def["output_name"])
        pattern = module_def.get("pattern", "*connection*")
        
        if export_module_with_connection_points(node, output_path, pattern):
            success_count += 1
    
    print(f"\n{'='*60}")
    print(f"Batch Export Complete: {success_count}/{len(module_definitions)} successful")
    print(f"{'='*60}")


# Example usage for testing
if __name__ == "__main__":
    # Test export - adjust paths to your scene
    test_node = hou.node("/obj/test_module/OUT")
    if test_node:
        export_module_with_connection_points(
            test_node,
            "D:/test_export.glb",
            "*connection*"
        )
    else:
        print("Create a test module at /obj/test_module/OUT to test export")
