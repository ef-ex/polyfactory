"""
Drawing utilities for viewer states
Pure functions for viewport drawing helpers
"""

import hou


def draw_crosshair(drawable, position: hou.Vector3, size: float = 1.0, 
                  color: tuple = (1, 1, 1)):
    """
    Draw simple crosshair at position.
    
    Args:
        drawable: Houdini drawable geometry
        position: Center position
        size: Crosshair size
        color: RGB color tuple
    """
    half_size = size * 0.5
    
    # Create line geometry for crosshair
    lines = hou.Geometry()
    
    # X axis line
    p1 = lines.createPoint()
    p1.setPosition(position + hou.Vector3(-half_size, 0, 0))
    p2 = lines.createPoint()
    p2.setPosition(position + hou.Vector3(half_size, 0, 0))
    lines.createPolygon([p1, p2], False)
    
    # Z axis line
    p3 = lines.createPoint()
    p3.setPosition(position + hou.Vector3(0, 0, -half_size))
    p4 = lines.createPoint()
    p4.setPosition(position + hou.Vector3(0, 0, half_size))
    lines.createPolygon([p3, p4], False)
    
    # Set color attribute
    cd_attrib = lines.addAttrib(hou.attribType.Point, "Cd", (1.0, 1.0, 1.0))
    for pt in lines.points():
        pt.setAttribValue(cd_attrib, color)
    
    drawable.setGeometry(lines)
    drawable.show(True)


def draw_normal_indicator(drawable, position: hou.Vector3, normal: hou.Vector3,
                         length: float = 1.0, color: tuple = (0, 1, 1)):
    """
    Draw line indicating surface normal.
    
    Args:
        drawable: Houdini drawable geometry
        position: Base position
        normal: Normal direction
        length: Line length
        color: RGB color tuple
    """
    lines = hou.Geometry()
    
    p1 = lines.createPoint()
    p1.setPosition(position)
    p2 = lines.createPoint()
    p2.setPosition(position + normal * length)
    
    lines.createPolygon([p1, p2], False)
    
    # Set color
    cd_attrib = lines.addAttrib(hou.attribType.Point, "Cd", (1.0, 1.0, 1.0))
    for pt in lines.points():
        pt.setAttribValue(cd_attrib, color)
    
    drawable.setGeometry(lines)
    drawable.show(True)
