"""modelUI input layer: one application event filter for gestures hotkeys cannot express (Shift+drag clone, tap/hold).

The filter is ``appfilter/pf_appfilter.dll`` (C++, source and build.bat beside it, loaded with ctypes): it checks the
event type in C++ and calls ``_on_app_event`` with raw pointers for input events reaching a QWindow only (where real
input enters; Qt runs application filters once per receiver), so Python wraps the event, never the receiver (a
pure-Python QApplication filter crashed Houdini in the Maya surface project: PySide wrapped every QObject that got any
event). Without the DLL the layer falls back to Python filters on every QWindow (``_Windows``), which run after
Houdini's own application filter (the Maya project lost RMB/MMB drags there).

Hook API for features:

    add_gesture(name, fn)     fn(kind, event, viewer) -> True | OBSERVE | False
    remove_gesture(name)
    later(fn)                 run fn after the current event (do scene work there, not inside the event)

A gesture is offered "press" (mouse button or double-click) when the widget under the point belongs to a Scene Viewer
(docked or floating) and the window receiving the event is that widget's window, and "key" (key press, not
auto-repeat) when the receiving window's focus widget belongs to a Scene Viewer and is not a text input.
- True: the gesture owns that button or key: this event and every following one of it ("move", "release" / "key"
  repeats, "keyup") go to the gesture only, swallowed, with viewer None.
- OBSERVE: the gesture watches without taking anything: it gets the following "move"/"release" events, and they all
  (and the press) still reach Houdini. Shift+drag clone is this: the handle moves, the gesture copies once a real drag
  starts and acts on release.
- False: the event goes on to the next gesture, then to Houdini.
Ownership is set before the gesture is called (a nested event loop inside it sees it), and ends with "cancel" when the
release never arrives: a move with the owned button up, the application or the focus window going away. Keys are
paired by native scan code (Shift+2 pressed, "@" released is one key). The demo gesture (``DEMO``): Ctrl+Shift+LMB drag
over a viewer is swallowed and reports its length.
"""
import ctypes
import functools
import logging
import os
import traceback

import hou
import shiboken6
from hutil.Qt import QtCore, QtGui, QtWidgets

LOG = logging.getLogger(__name__)
QE = QtCore.QEvent
Qt = QtCore.Qt
SESSION_ATTR = "_pf_modelui_input"
LIB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "appfilter", "pf_appfilter.dll")
OBSERVE = "observe"
_CALLBACK = ctypes.CFUNCTYPE(ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int)
_TYPES = {int(QE.KeyPress): QtGui.QKeyEvent, int(QE.KeyRelease): QtGui.QKeyEvent,
          int(QE.MouseButtonPress): QtGui.QMouseEvent, int(QE.MouseButtonRelease): QtGui.QMouseEvent,
          int(QE.MouseButtonDblClick): QtGui.QMouseEvent, int(QE.MouseMove): QtGui.QMouseEvent}
_TEXT = (QtWidgets.QLineEdit, QtWidgets.QTextEdit, QtWidgets.QPlainTextEdit, QtWidgets.QAbstractSpinBox)

_gestures = {}            # name -> fn, in registration order


def add_gesture(name, fn):
    _gestures[name] = fn


def remove_gesture(name):
    _gestures.pop(name, None)


def later(fn):
    """Run ``fn`` after the current event, from Qt's event loop (scene changes inside an event filter are unsafe)."""
    def run():
        try:
            fn()
        except Exception:  # noqa: BLE001
            LOG.exception("modelUI deferred action failed")
    QtCore.QTimer.singleShot(0, run)


def _ptr(obj):
    return shiboken6.getCppPointer(obj)[0]


def _viewers():
    """Every visible Scene Viewer tab, floating panels included."""
    return [t for t in hou.ui.paneTabs() if isinstance(t, hou.SceneViewer) and t.isCurrentTab()]


def receiving_top(receiver):
    """The top-level widget whose QWindow (pointer ``receiver``) receives the event, else None."""
    for top in QtWidgets.QApplication.topLevelWidgets():
        h = top.windowHandle()
        if h is not None and _ptr(h) == receiver:
            return top
    return None


def viewer_of(widget):
    """The Scene Viewer ``widget`` belongs to: it lies inside the viewer's rectangle and its top-level window covers
    the whole viewer (a window over the viewer, a menu or a dialog does not). Else None."""
    if widget is None:
        return None
    top = widget.window()
    r = QtCore.QRect(widget.mapToGlobal(QtCore.QPoint(0, 0)), widget.size())
    tg = top.frameGeometry()
    for sv in _viewers():
        g = sv.qtScreenGeometry()
        if g.contains(r) and tg.contains(g):
            return sv
    return None


def _key_id(ev):
    return ev.nativeScanCode() or ev.key()   # synthetic events have no scan code


class _Layer:
    def __init__(self):
        self.owner = None     # [fn, (kind, which), swallow]
        self.backend = None   # "cpp" or "windows"
        self.attached = None
        app = QtGui.QGuiApplication.instance()
        app.focusWindowChanged.connect(self._focus_changed)
        app.applicationStateChanged.connect(self._state_changed)

    def shutdown(self):
        app = QtGui.QGuiApplication.instance()
        for sig, slot in ((app.focusWindowChanged, self._focus_changed),
                          (app.applicationStateChanged, self._state_changed)):
            try:
                sig.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        self.cancel()

    def _focus_changed(self, w):
        if w is not None and w.type() in (Qt.Popup, Qt.ToolTip):
            return   # a menu or tooltip does not take input away from the viewer
        self.cancel()

    def _state_changed(self, state):
        if state != Qt.ApplicationActive:
            self.cancel()

    def cancel(self, ev=None):
        """The owner loses its button or key (its release will not come)."""
        if self.owner is not None:
            fn = self.owner[0]
            self.owner = None
            self._call(fn, "cancel", ev, None)

    def handle(self, ev, receiver):
        """True swallows ``ev``. ``receiver``: pointer of the QWindow receiving it."""
        t = ev.type()
        if self.owner is not None:
            return self._follow(ev, t)
        if t in (QE.MouseButtonPress, QE.MouseButtonDblClick):
            kind, token = "press", ("mouse", ev.button())
            if not _gestures:
                return False
            top = receiving_top(receiver)   # widgetAt() would need a screen under the point
            w = top and (top.childAt(top.mapFromGlobal(ev.globalPosition().toPoint())) or top)
            viewer = viewer_of(w)
        elif t == QE.KeyPress and not ev.isAutoRepeat():
            kind, token = "key", ("key", _key_id(ev))
            if not _gestures:
                return False
            top = receiving_top(receiver)
            focus = top and top.focusWidget()
            viewer = None if isinstance(focus, _TEXT) else viewer_of(focus)
        else:
            return False
        if viewer is None:
            return False
        for fn in list(_gestures.values()):
            owner = [fn, token, True]
            self.owner = owner          # before the call: a nested event loop inside fn must see it
            res = self._call(fn, kind, ev, viewer)
            if res is True or res == OBSERVE:
                if res == OBSERVE:
                    owner[2] = False
                return res is True
            if self.owner is owner:
                self.owner = None
        return False

    def _follow(self, ev, t):
        owner = self.owner
        fn, (kind, which), swallow = owner
        if kind == "mouse" and t == QE.MouseMove:
            if not ev.buttons() & which:   # the release was lost (another window, a dialog): give the mouse back
                self.cancel(ev)
                return False
            self._call(fn, "move", ev, None)
            return swallow
        if kind == "mouse" and t == QE.MouseButtonDblClick and ev.button() == which:
            return swallow   # Qt sends it after the second press of a double-click: part of the owned press
        if kind == "mouse" and t == QE.MouseButtonRelease and ev.button() == which:
            self.owner = None
            self._call(fn, "release", ev, None)
            return swallow
        if kind == "key" and t in (QE.KeyPress, QE.KeyRelease) and _key_id(ev) == which:
            if t == QE.KeyRelease and not ev.isAutoRepeat():
                self.owner = None
                self._call(fn, "keyup", ev, None)
                return swallow
            self._call(fn, "key", ev, None)
            return swallow
        return False

    def _call(self, fn, kind, ev, viewer):
        try:
            return fn(kind, ev, viewer)
        except Exception:  # noqa: BLE001 - a broken gesture must never break Houdini input
            LOG.error("modelUI gesture failed\n%s", traceback.format_exc())
            if self.owner is not None and self.owner[0] is fn:
                self.owner = None
            return False


def _on_app_event(lay, receiver, event, etype):
    """Called by the C++ filter for the types in _TYPES reaching a window only. 1 swallows the event."""
    try:
        ev = shiboken6.wrapInstance(event, _TYPES[etype])
        try:
            return 1 if lay.handle(ev, receiver) else 0
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
            return int(ev.type()) in _TYPES and self.lay.handle(ev, _ptr(obj))
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
        lay.shutdown()
        setattr(hou.session, SESSION_ATTR, None)


class _DemoDrag:
    """Ctrl+Shift+LMB drag over a viewer: swallowed (Houdini never sees it), its length goes to the status bar and to
    ``log`` (drags as (pixels, viewer name)). A demo of the hook API."""

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
