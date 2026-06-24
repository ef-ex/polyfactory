"""
Layout Helpers - Houdini-styled layouts

Provides layout classes styled to match Houdini's native UI.
"""

from PySide6 import QtWidgets


class HoudiniVLayout(QtWidgets.QVBoxLayout):
    """Vertical layout with Houdini spacing."""
    
    def __init__(self):
        super().__init__()
        self.setSpacing(2)
        self.setContentsMargins(4, 4, 4, 4)


class HoudiniHLayout(QtWidgets.QHBoxLayout):
    """Horizontal layout with Houdini spacing."""
    
    def __init__(self):
        super().__init__()
        self.setSpacing(4)
        self.setContentsMargins(4, 4, 4, 4)


class HoudiniGroupBox(QtWidgets.QGroupBox):
    """Group box styled like Houdini folders."""
    
    def __init__(self, title: str = ""):
        super().__init__(title)
        self.setStyleSheet("""
            QGroupBox {
                border: 1px solid #3a3a3a;
                border-radius: 3px;
                margin-top: 8px;
                padding-top: 4px;
                background: #2a2a2a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 4px;
                color: #cccccc;
                background: transparent;
            }
        """)
