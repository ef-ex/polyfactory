"""
Hover Outline Mixin - Animated blue outline on hover for any widget
"""

from PySide6 import QtWidgets, QtCore, QtGui


class HoverOutlineMixin:
    """
    Mixin to add animated blue hover outline to any widget.
    
    Usage:
        class MyWidget(HoverOutlineMixin, QtWidgets.QWidget):
            def __init__(self, parent=None):
                super().__init__(parent)
                self.setup_hover_outline()  # Call this in __init__
    
    The mixin provides:
    - Animated fade-in/out of blue outline on hover
    - PyOneDark blue color (#61afef)
    - Customizable outline properties via parameters
    """
    
    def setup_hover_outline(self, color="#61afef", width=2, radius=6, 
                           fade_duration=150, inset=1):
        """
        Initialize hover outline animation.
        
        Args:
            color: Outline color (hex string)
            width: Outline width in pixels
            radius: Corner radius for rounded rect
            fade_duration: Animation duration in milliseconds
            inset: Pixels to inset from widget edge
        """
        self._hover_outline_color = QtGui.QColor(color)
        self._hover_outline_width = width
        self._hover_outline_radius = radius
        self._hover_outline_inset = inset
        self._hover_outline_opacity = 0.0
        
        # Create animation for opacity
        self._hover_animation = QtCore.QPropertyAnimation(self, b"hover_outline_opacity")
        self._hover_animation.setDuration(fade_duration)
        self._hover_animation.setEasingCurve(QtCore.QEasingCurve.OutCubic)
        self._hover_animation.valueChanged.connect(lambda: self.update())
        
        # Enable mouse tracking (required for hover events)
        self.setMouseTracking(True)
    
    def get_hover_outline_opacity(self):
        """Get current hover outline opacity (0.0 to 1.0)"""
        return self._hover_outline_opacity
    
    def set_hover_outline_opacity(self, value):
        """Set hover outline opacity (0.0 to 1.0)"""
        self._hover_outline_opacity = value
        self.update()  # Trigger repaint
    
    # Qt Property for animation
    hover_outline_opacity = QtCore.Property(float, get_hover_outline_opacity, set_hover_outline_opacity)
    
    def enterEvent(self, event):
        """Start fade-in animation on hover"""
        if hasattr(super(), 'enterEvent'):
            super().enterEvent(event)
        
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_outline_opacity)
        self._hover_animation.setEndValue(1.0)
        self._hover_animation.start()
    
    def leaveEvent(self, event):
        """Start fade-out animation on leave"""
        if hasattr(super(), 'leaveEvent'):
            super().leaveEvent(event)
        
        self._hover_animation.stop()
        self._hover_animation.setStartValue(self._hover_outline_opacity)
        self._hover_animation.setEndValue(0.0)
        self._hover_animation.start()
    
    def paint_hover_outline(self, painter):
        """
        Paint the hover outline. Call this in your paintEvent.
        
        Args:
            painter: QPainter instance
            
        Example:
            def paintEvent(self, event):
                super().paintEvent(event)
                painter = QtGui.QPainter(self)
                painter.setRenderHint(QtGui.QPainter.Antialiasing)
                self.paint_hover_outline(painter)
        """
        if self._hover_outline_opacity <= 0.0:
            return
        
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Create color with animated opacity
        color = QtGui.QColor(self._hover_outline_color)
        color.setAlphaF(self._hover_outline_opacity)
        
        pen = QtGui.QPen(color, self._hover_outline_width)
        painter.setPen(pen)
        painter.setBrush(QtCore.Qt.NoBrush)
        
        # Draw rounded rect outline
        rect = self.rect().adjusted(
            self._hover_outline_inset,
            self._hover_outline_inset,
            -self._hover_outline_inset,
            -self._hover_outline_inset
        )
        painter.drawRoundedRect(rect, self._hover_outline_radius, self._hover_outline_radius)
