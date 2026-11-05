"""modelUI input layer: one application event filter for gestures hotkeys cannot express (Shift+drag clone, tap/hold).

The filter is ``appfilter/pf_appfilter.dll`` (C++, source and build.bat beside it, loaded with ctypes): it checks the
event type in C++ and calls ``_on_app_event`` with raw pointers for input events only, so Python wraps the event, never
the receiver (a pure-Python QApplication filter crashed Houdini in the Maya surface project: PySide wrapped every
QObject that got any event). Without the DLL the layer falls back to Python filters on every QWindow (``_Windows``),
which sees real input too but runs after Houdini's own application filter (the Maya project lost RMB/MMB drags there).

Hook API for features (all gestures see only input over a Scene Viewer of the current desk):

    add_gesture(name, fn)     fn(kind, event, viewer) -> bool
    remove_gesture(name)

``kind`` is "press" (mouse button) or "key" (key press, not auto-repeat). Returning True takes ownership: the event is
swallowed and the gesture gets every following event of that button or key ("move", "release" / "key" repeats,
"keyup") with ``viewer`` None, all swallowed, until the release. Returning False passes the event on to Houdini.
If the release never arrives (a move comes with the owned button up), the gesture gets "cancel" and ownership ends.
The demo gesture (``DEMO``): Ctrl+Shift+LMB drag over a viewer is swallowed and reports its length.
"""
import ctypes
import functools
import logging
import os

import hou
import shiboken6
from hutil.Qt import QtCore, QtGui

LOG = logging.getLogger(__name__)
QE = QtCore.QEvent
Qt = QtCore.Qt
SESSION_ATTR = "_pf_modelui_input"
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "appfilter", "pf_appfilter.dll")
_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
_TYPES = {int(QE.KeyPress): QtGui.QKeyEvent, int(QE.KeyRelease): QtGui.QKeyEvent,
          int(QE.MouseButtonPress): QtGui.QMouseEvent, int(QE.MouseButtonRelease): QtGui.QMouseEvent,
          int(QE.MouseMove): QtGui.QMouseEvent}

_gestures = {}            # name -> fn, in registration order
cursor_pos = QtGui.QCursor.pos   # where a key press happens; tests replace it (synthetic keys have no cursor)


def add_gesture(name, fn):
    _gestures[name] = fn


def remove_gesture(name):
    _gestures.pop(name, None)


def viewer_at(pos):
    """The Scene Viewer of the current desk whose visible tab contains the global point ``pos``, else None."""
    for tab in hou.ui.curDesktop().paneTabs():
        if isinstance(tab, hou.SceneViewer) and tab.isCurrentTab() and tab.qtScreenGeometry().contains(pos):
            return tab
    return None


class _Layer:
    def __init__(self):
        self.owner = None     # (fn, token): token ("mouse", button) or ("key", key)
        self.backend = None   # "cpp" or "windows"
        self.attached = None

    def handle(self, ev):
        """True swallows ``ev``."""
        t = ev.type()
        if self.owner is not None:
            fn, (kind, which) = self.owner
            if kind == "mouse" and t == QE.MouseMove:
                if not ev.buttons() & which:   # the release was lost (another window, a dialog): give the mouse back
                    self.owner = None
                    self._call(fn, "cancel", ev, None)
                    return False
                return self._call(fn, "move", ev, None) or True
            if kind == "mouse" and t == QE.MouseButtonRelease and ev.button() == which:
                self.owner = None
                return self._call(fn, "release", ev, None) or True
            if kind == "key" and t in (QE.KeyPress, QE.KeyRelease) and ev.key() == which:
                if t == QE.KeyRelease and not ev.isAutoRepeat():
                    self.owner = None
                    return self._call(fn, "keyup", ev, None) or True
                return self._call(fn, "key", ev, None) or True
            return False
        if t == QE.MouseButtonPress:
            kind, pos, token = "press", ev.globalPosition().toPoint(), ("mouse", ev.button())
        elif t == QE.KeyPress and not ev.isAutoRepeat():
            kind, pos, token = "key", cursor_pos(), ("key", ev.key())
        else:
            return False
        if not _gestures:
            return False
        viewer = viewer_at(pos)
        if viewer is None:
            return False
        for fn in list(_gestures.values()):
            if self._call(fn, kind, ev, viewer):
                self.owner = (fn, token)
                return True
        return False

    def _call(self, fn, kind, ev, viewer):
        try:
            return bool(fn(kind, ev, viewer))
        except Exception:  # noqa: BLE001 - a broken gesture must never break Houdini input
            LOG.exception("modelUI gesture failed")
            self.owner = None
            return False


def _on_app_event(lay, receiver, event, etype):
    """Called by the C++ filter for the types in _TYPES only. 1 swallows the event."""
    try:
        ev = shiboken6.wrapInstance(event, _TYPES[etype])
        try:
            return 1 if lay.handle(ev) else 0
        finally:
            if not shiboken6.ownedByPython(ev):   # Qt's event dies after delivery and its address is reused
                shiboken6.invalidate(ev)
    except Exception:  # noqa: BLE001
        LOG.exception("modelUI input layer (C++ filter)")
        return 0


class _AppFilter:
    def __init__(self, lay):
        self.lib = ctypes.CDLL(LIB)
        self.lib.pf_install.restype = ctypes.c_void_p
        self.lib.pf_install.argtypes = [_CALLBACK, ctypes.POINTER(ctypes.c_int), ctypes.c_int]
        self.lib.pf_uninstall.argtypes = [ctypes.c_void_p]
        self.callback = _CALLBACK(functools.partial(_on_app_event, lay))   # alive as long as the filter
        types = (ctypes.c_int * len(_TYPES))(*_TYPES)
        self.handle = self.lib.pf_install(self.callback, types, len(_TYPES))
        if not self.handle:
            raise RuntimeError("no QApplication")

    def detach(self):
        if getattr(self, "handle", None):   # __init__ may have failed before the filter existed
            self.lib.pf_uninstall(self.handle)
            self.handle = None

    __del__ = detach   # never leave Qt holding a freed ctypes callback (that crashes Houdini on the next event)


class _WindowFilter(QtCore.QObject):
    def __init__(self, lay):
        super().__init__()
        self.lay = lay

    def eventFilter(self, obj, ev):  # noqa: N802 - Qt name
        try:
            return int(ev.type()) in _TYPES and self.lay.handle(ev)
        except Exception:  # noqa: BLE001
            LOG.exception("modelUI input layer (window filter)")
            return False


class _Windows(QtCore.QObject):
    """Fallback: the Python filter on every QWindow; new windows get it within 500 ms."""

    def __init__(self, lay):
        super().__init__()
        self.filter = _WindowFilter(lay)
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(500)
        self.timer.timeout.connect(self.attach)
        self.attach()
        self.timer.start()

    def attach(self):
        for w in QtGui.QGuiApplication.allWindows():
            w.installEventFilter(self.filter)   # Qt keeps one entry per filter: installing again is a no-op

    def detach(self):
        self.timer.stop()
        for w in QtGui.QGuiApplication.allWindows():
            w.removeEventFilter(self.filter)


def layer():
    return getattr(hou.session, SESSION_ATTR, None)


def install(fallback=False):
    """Install the layer and the demo gesture (switch feature hook). ``fallback`` forces the per-window filters."""
    uninstall()
    lay = _Layer()
    try:
        if fallback:
            raise OSError("fallback requested")
        lay.attached, lay.backend = _AppFilter(lay), "cpp"
    except (OSError, AttributeError, RuntimeError):
        if not fallback:
            LOG.warning("modelUI: C++ filter %s not usable, per-window filters instead", LIB, exc_info=True)
        lay.attached, lay.backend = _Windows(lay), "windows"
    setattr(hou.session, SESSION_ATTR, lay)
    add_gesture("demo_drag", DEMO)


def uninstall():
    remove_gesture("demo_drag")
    lay = layer()
    if lay is not None:
        lay.attached.detach()
        setattr(hou.session, SESSION_ATTR, None)


class _DemoDrag:
    """Ctrl+Shift+LMB drag over a viewer: swallowed (Houdini never sees it), its length goes to the status bar and to
    ``log`` (drags as (pixels, viewer name)). A demo of the hook API; Shift+drag clone will look like this."""

    def __init__(self):
        self.log, self.start, self.viewer = [], None, None

    def __call__(self, kind, ev, viewer):
        if kind == "key":
            return False
        if kind == "press":
            mods = ev.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier)
            if ev.button() != Qt.LeftButton or mods != (Qt.ControlModifier | Qt.ShiftModifier):
                return False
            self.start, self.viewer = ev.globalPosition(), viewer.name()
            return True
        if kind == "release":
            d = ev.globalPosition() - self.start
            px = round((d.x() ** 2 + d.y() ** 2) ** 0.5)
            self.log.append((px, self.viewer))
            hou.ui.setStatusMessage("modelUI demo gesture: Ctrl+Shift drag of %d px in %s" % (px, self.viewer))
        return True


DEMO = _DemoDrag()
