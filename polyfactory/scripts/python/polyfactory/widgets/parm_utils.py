"""
Parameter Utilities - Helper functions for Houdini parameter handling

Functions for expression detection, parameter styling, and standard Houdini
parameter operations.
"""

import hou
from typing import Optional, Tuple


def has_expression(parm: hou.Parm) -> bool:
    """Check if parameter has an expression (not just a static value)."""
    try:
        # Check if expression is set (even without keyframes)
        expr = parm.expression()
        if expr and expr.strip():
            return True
        
        # Check if any keyframes exist
        if parm.keyframes():
            return True
            
        return False
    except:
        return False


def get_expression_string(parm: hou.Parm) -> Optional[str]:
    """Get the expression string from a parameter."""
    try:
        expr = parm.expression()
        return expr if expr else None
    except:
        return None


def get_expression_language(parm: hou.Parm) -> str:
    """Get expression language (hscript or python)."""
    try:
        return parm.expressionLanguage().name()
    except:
        return "hscript"


def set_expression(parm: hou.Parm, expression: str, language: str = "hscript"):
    """Set an expression on a parameter."""
    try:
        lang = hou.exprLanguage.Hscript if language == "hscript" else hou.exprLanguage.Python
        parm.setExpression(expression, language=lang)
    except Exception as e:
        print(f"Error setting expression on {parm.name()}: {e}")


def delete_expression(parm: hou.Parm):
    """Remove expression from parameter (revert to static value)."""
    try:
        parm.deleteAllKeyframes()
    except Exception as e:
        print(f"Error deleting expression on {parm.name()}: {e}")


def get_parm_color(parm: hou.Parm) -> Tuple[int, int, int]:
    """
    Get appropriate background color for parameter based on state.
    
    Returns RGB tuple:
    - Hscript expression: green (60, 100, 60)
    - Python expression: purple (90, 60, 110)
    - Animated (keyframes): orange (120, 90, 60)
    - Default: dark gray (42, 42, 42)
    """
    if has_expression(parm):
        keyframes = parm.keyframes()
        lang = get_expression_language(parm).lower()
        
        # Check if it's animated (has multiple keyframes, not just expression)
        if keyframes and len(keyframes) > 1:
            return (120, 90, 60)  # Orange for animated (multiple keyframes)
        elif lang == "python":
            return (90, 60, 110)  # Purple for Python
        else:
            return (60, 100, 60)  # Green for Hscript/VEX
    
    return (42, 42, 42)  # Default dark gray


def copy_parameter(parm: hou.Parm):
    """Copy parameter using Houdini's native API."""
    try:
        parm.copyToParmClipboard()
    except Exception as e:
        print(f"Error copying parameter: {e}")


def paste_relative_reference(target_parm: hou.Parm, source_path: str = None):
    """Paste parameter reference using Houdini's parameter clipboard."""
    try:
        # Get clipboard contents
        clipboard = hou.parmClipboardContents()
        if not clipboard or len(clipboard) == 0:
            return
        
        # Get first parm from clipboard
        source_info = clipboard[0]
        source_path = source_info['path']
        
        # Get source parameter
        source_parm = hou.parm(source_path)
        if not source_parm:
            return
        
        # Create relative reference using Houdini's API
        # This mimics what the native UI does
        ref_expr = target_parm.node().relativePathTo(source_parm.node())
        expr = f'ch("{ref_expr}/{source_parm.name()}")'
        
        # Set the expression
        target_parm.setExpression(expr, language=hou.exprLanguage.Hscript)
    except Exception as e:
        print(f"Error pasting reference: {e}")


def revert_to_default(parm: hou.Parm):
    """Revert parameter to its default value."""
    try:
        parm.revertToDefaults()
    except Exception as e:
        print(f"Error reverting to default: {e}")


def get_parm_display_value(parm: hou.Parm) -> str:
    """
    Get display value for parameter (expression or evaluated value).
    
    Returns expression string if present, otherwise formatted value.
    """
    if has_expression(parm):
        expr = get_expression_string(parm)
        return expr if expr else str(parm.eval())
    else:
        return str(parm.eval())
