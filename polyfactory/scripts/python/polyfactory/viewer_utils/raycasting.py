"""
Raycasting utilities for viewer states
Pure functions for ray-geometry intersection and surface queries
"""

import hou
from typing import Optional, Tuple


def raycast_to_geometry(origin: hou.Vector3, direction: hou.Vector3, 
                        geometry: hou.Geometry) -> Optional[dict]:
    """
    Raycast against geometry and return hit information.
    
    Args:
        origin: Ray origin position
        direction: Ray direction (should be normalized)
        geometry: Geometry to raycast against
        
    Returns:
        Dictionary with hit info or None if no hit:
        {
            'position': hou.Vector3,      # Hit point position
            'normal': hou.Vector3,        # Surface normal at hit
            'prim_num': int,              # Primitive number hit
            'uv': tuple[float, float]     # UV coordinates on prim
        }
    """
    if not geometry:
        return None
    
    # Perform intersection
    intersect = geometry.intersect(origin, direction)
    
    if intersect == -1:
        # No hit
        return None
    
    # Get hit primitive
    prim = geometry.prim(intersect)
    if not prim:
        return None
    
    # Compute hit position
    # Use nearPoint to find closest point for better accuracy
    points = prim.points()
    if not points:
        return None
    
    # Get position and normal
    # For more accurate results, we'd compute barycentric coords
    # For now, use primitive attrib or vertex normal
    hit_pos = prim.positionAtInterior(0.5, 0.5, 0.5)  # Approximate
    
    # Get normal - try point normal, then compute from prim
    normal = prim.normal()
    if normal.length() < 0.001:
        # Fallback: compute from vertices
        vertices = prim.vertices()
        if len(vertices) >= 3:
            v0 = vertices[0].point().position()
            v1 = vertices[1].point().position()
            v2 = vertices[2].point().position()
            edge1 = v1 - v0
            edge2 = v2 - v0
            normal = edge1.cross(edge2).normalized()
        else:
            normal = hou.Vector3(0, 1, 0)  # Default up
    else:
        normal = normal.normalized()
    
    return {
        'position': hit_pos,
        'normal': normal,
        'prim_num': intersect,
        'uv': (0.5, 0.5)  # TODO: Compute actual UV coords
    }


def raycast_to_ground_plane(origin: hou.Vector3, direction: hou.Vector3, 
                            plane_height: float = 0.0) -> Optional[hou.Vector3]:
    """
    Raycast to horizontal plane (XZ plane at given height).
    
    Args:
        origin: Ray origin
        direction: Ray direction
        plane_height: Y coordinate of plane
        
    Returns:
        Intersection point or None if ray doesn't hit plane
    """
    if abs(direction.y()) < 0.0001:
        # Ray is parallel to plane
        return None
    
    # Solve for t: origin.y + t * direction.y = plane_height
    t = (plane_height - origin.y()) / direction.y()
    
    if t < 0:
        # Intersection is behind ray origin
        return None
    
    return origin + direction * t


def get_geometry_under_cursor(ui_event, node: hou.SopNode) -> Optional[dict]:
    """
    Get geometry under cursor using ray intersection.
    
    Args:
        ui_event: Houdini UI event with ray information
        node: SOP node to get geometry from
        
    Returns:
        Hit info dict or None
    """
    origin, direction = ui_event.ray()
    
    if not node:
        return None
    
    # Try to get geometry from node inputs
    geo = None
    for i in range(node.inputConnectors()[0].size()):
        input_geo = node.inputGeometry(i)
        if input_geo and len(input_geo.prims()) > 0:
            geo = input_geo
            break
    
    if not geo:
        return None
    
    return raycast_to_geometry(origin, direction, geo)


def align_transform_to_normal(normal: hou.Vector3, up_vector: hou.Vector3 = None) -> hou.Matrix4:
    """
    Create transformation matrix to align object to surface normal.
    
    Args:
        normal: Surface normal (will be used as local +Y)
        up_vector: Optional up hint for rotation
        
    Returns:
        Transformation matrix
    """
    if up_vector is None:
        # Default up is world Y, unless normal is very close to Y
        if abs(normal.dot(hou.Vector3(0, 1, 0))) > 0.95:
            up_vector = hou.Vector3(1, 0, 0)
        else:
            up_vector = hou.Vector3(0, 1, 0)
    
    # Normalize inputs
    normal = normal.normalized()
    
    # Build coordinate frame
    # Normal is the Y axis (up)
    # X axis is perpendicular to normal and up hint
    x_axis = up_vector.cross(normal).normalized()
    if x_axis.length() < 0.001:
        # Up and normal are parallel, choose arbitrary perpendicular
        x_axis = hou.Vector3(1, 0, 0) if abs(normal.x()) < 0.9 else hou.Vector3(0, 0, 1)
        x_axis = x_axis.cross(normal).normalized()
    
    # Z axis completes the frame
    z_axis = normal.cross(x_axis).normalized()
    
    # Build matrix (column vectors)
    mat = hou.Matrix4((
        x_axis.x(), x_axis.y(), x_axis.z(), 0,
        normal.x(), normal.y(), normal.z(), 0,
        z_axis.x(), z_axis.y(), z_axis.z(), 0,
        0, 0, 0, 1
    ))
    
    return mat


def extract_rotation_from_matrix(mat: hou.Matrix4) -> hou.Vector3:
    """
    Extract Euler rotation angles (XYZ order) from transformation matrix.
    
    Args:
        mat: Transformation matrix
        
    Returns:
        Rotation as Vector3 (degrees)
    """
    # Get rotation component (ignore translation/scale)
    quat = hou.Quaternion()
    quat.setToRotationMatrix(mat)
    
    # Convert to Euler angles
    return quat.extractEulerRotates()
