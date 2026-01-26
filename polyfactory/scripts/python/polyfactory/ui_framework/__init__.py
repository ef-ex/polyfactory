"""
Polyfactory UI Framework
=========================

Modern Qt widget library based on PyOneDark Qt Widgets.

ATTRIBUTION:
This module is derived from PyOneDark Qt Widgets Modern GUI
Original Author: Wanderson M. Pimenta
Repository: https://github.com/Wanderson-Magalhaes/PyOneDark_Qt_Widgets_Modern_GUI
License: MIT License (see LICENSE file in this directory)

Modifications and integration for Polyfactory by the Polyfactory team.

The original work provides:
- Modern dark-themed Qt widgets
- Animated UI components
- Professional styling system
- Responsive layouts

Polyfactory-specific additions:
- Integration with Houdini Python panels
- Custom widgets for 3D/pipeline workflows
- Unified theming across standalone and embedded tools
"""

# Core imports
from . import qt_core
from . import core
from . import widgets
from . import themes

__all__ = ['qt_core', 'core', 'widgets', 'themes']
