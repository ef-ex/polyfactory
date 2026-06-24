"""
Input handling utilities for viewer states
Functions for processing mouse/keyboard input
"""

import hou


def is_click(ui_event, button='left') -> bool:
    """
    Check if UI event is a click (Picked reason with button down).
    
    Args:
        ui_event: Houdini UI event
        button: 'left', 'middle', or 'right'
        
    Returns:
        True if click detected
    """
    device = ui_event.device()
    
    if ui_event.reason() != hou.uiEventReason.Picked:
        return False
    
    if button == 'left':
        return device.isLeftButton()
    elif button == 'middle':
        return device.isMiddleButton()
    elif button == 'right':
        return device.isRightButton()
    
    return False


def is_key_pressed(ui_event, key: str) -> bool:
    """
    Check if specific key is pressed.
    
    Args:
        ui_event: Houdini UI event
        key: Key string (e.g. 'r', 'Return', 'Escape')
        
    Returns:
        True if key is pressed
    """
    device = ui_event.device()
    return device.isKeyPressed(key)


def get_modifier_state(ui_event) -> dict:
    """
    Get state of modifier keys.
    
    Args:
        ui_event: Houdini UI event
        
    Returns:
        Dictionary with modifier states:
        {
            'shift': bool,
            'ctrl': bool,
            'alt': bool
        }
    """
    device = ui_event.device()
    return {
        'shift': device.isShiftKey(),
        'ctrl': device.isCtrlKey(),
        'alt': device.isAltKey()
    }
