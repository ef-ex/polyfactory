"""
UI utilities for matching Houdini's font sizes and scaling
"""

import hou
from PySide6 import QtWidgets, QtGui


def get_scaled_font_size(base_size=11):
    """
    Get font size scaled to match Houdini's UI scaling.
    
    Args:
        base_size: Base font size in points (default 11, Houdini's default)
    
    Returns:
        Scaled font size as integer
    """
    scale_factor = hou.ui.globalScaleFactor()
    return int(base_size * scale_factor)


def get_houdini_font():
    """
    Get Houdini's default application font.
    
    Returns:
        QFont object matching Houdini's UI font
    """
    return QtWidgets.QApplication.font()


def get_font_stylesheet(size=None, weight=None, color=None, **kwargs):
    """
    Generate font stylesheet matching Houdini's scaling.
    
    Args:
        size: Font size in points (will be scaled)
        weight: Font weight ('normal', 'bold')
        color: Text color (hex string)
        **kwargs: Additional CSS properties
    
    Returns:
        CSS stylesheet string
    """
    styles = []
    
    if size is not None:
        scaled_size = get_scaled_font_size(size)
        styles.append(f"font-size: {scaled_size}px")
    
    if weight is not None:
        styles.append(f"font-weight: {weight}")
    
    if color is not None:
        styles.append(f"color: {color}")
    
    for key, value in kwargs.items():
        css_key = key.replace('_', '-')
        styles.append(f"{css_key}: {value}")
    
    return "; ".join(styles)


def apply_houdini_font(widget, size=None):
    """
    Apply Houdini's font to a widget with optional size override.
    
    Args:
        widget: QWidget to apply font to
        size: Font size in points (will be scaled), None uses Houdini default
    """
    font = get_houdini_font()
    
    if size is not None:
        scaled_size = get_scaled_font_size(size)
        font.setPointSize(scaled_size)
    
    widget.setFont(font)
