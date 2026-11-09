"""modelUI input layer: one application event filter for gestures hotkeys cannot express (Shift+drag clone, tap/hold).

The filter is ``appfilter/pf_appfilter.dll`` (C++, source and build.bat beside it, loaded with ctypes): it checks the
event type in C++ and calls ``_on_app_event`` with raw pointers for input events reaching a QWindow only (where real
input enters; Qt runs application filters once per receiver), so Python wraps the event, never the receiver (a
pure-Python QApplication filter crashed Houdini in the Maya surface project: PySide wrapped every QObject that got any
event). Without the DLL the layer falls back to Python filters on every QWindow (``_Windows``), which run after
Houdini's own application filter (the Maya project lost RMB/MMB drags there).

Hook API for features:

    add_gesture(name, fn, first=False)   fn(kind, event, viewer) -> True | OBSERVE | False; first: asked first
    remove_gesture(name)
    later(fn)                 run fn after the current event (do scene work there, not inside the event)

A gesture is offered "press" (mouse button) when the widget under the point belongs to a Scene Viewer
(docked or floating) and the window receiving the event is that widget's window, and "key" (key press, not
auto-repeat) when the receiving window's focus widget belongs to a Scene Viewer and is not a text input.
- True: the gesture owns that button or key: this event and every following one of it ("move", "release" / "key"
  repeats, "keyup") go to the gesture only, swallowed, with viewer None.
- OBSERVE: the gesture watches without taking anything: it gets the following "move"/"release" events, and they all
  (and the press) still reach Houdini. Several gestures can observe the same press (every gesture is still asked);
  one that answers True after them takes the press and the observers are dropped. Shift+drag clone is this: the handle moves, the gesture copies once a real drag
  starts and acts on release.
- False: the event goes on to the next gesture, then to Houdini.
Mouse and keyboard have one owner each, so a held key and a drag run side by side; while a key is owned,
its gesture is told about every other key press and click first ("other", with the viewer under the click or holding
the focus, else None; True swallows it with its repeats and release; a holder should only swallow clicks in a viewer).
While a gesture owns a mouse button, every other button's press, release and double-click is swallowed too.
A second key is never offered to the other gestures, so two key gestures cannot chord (registration order decides). Ownership is set before the gesture is called (a nested event loop inside it sees it), and ends with "cancel" when the
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


def add_gesture(name, fn, first=False):
    """``first``: asked before every other gesture (a modal pick, e.g. Align's target, must beat the click gestures)."""
    _gestures.pop(name, None)
    rest = list(_gestures.items()) if first else []
    if first:
        _gestures.clear()
    _gestures[name] = fn
    _gestures.update(rest)


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


SLOT = {"press": "mouse", "key": "key"}   # one owner per device: a held key and a mouse drag run side by side


class _Layer:
    def __init__(self):
        self.owners = {"mouse": None, "key": None}   # slot -> [fn, button or key id, swallow]
        self.eaten = {"mouse": set(), "key": set()}  # buttons / key ids a key holder swallowed via "other"
        self.watchers = {"mouse": [], "key": []}     # OBSERVE gestures of the current press: [fn, id, False]
        self.backend = None   # "cpp" or "windows"
        self.attached = None
        app = QtGui.QGuiApplication.instance()
        app.focusWindowChanged.connect(self._focus_changed)
        app.applicationStateChanged.connect(self._state_changed)

    @property
    def owner(self):
        """Any current owner (None when nothing is owned)."""
        return self.owners["mouse"] or self.owners["key"]

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
        """Every owner loses its button or key (its release will not come)."""
        self.eaten["mouse"].clear()
        self.eaten["key"].clear()
        for slot in ("mouse", "key"):
            ws, self.watchers[slot] = self.watchers[slot], []
            for w in ws:
                self._call(w[0], "cancel", ev, None)
        for slot in ("mouse", "key"):
            o = self.owners[slot]
            if o is not None:
                self.owners[slot] = None
                self._call(o[0], "cancel", ev, None)

    def handle(self, ev, receiver):
        """True swallows ``ev``. ``receiver``: pointer of the QWindow receiving it."""
        t = ev.type()
        if t in (QE.MouseMove, QE.MouseButtonRelease, QE.MouseButtonDblClick):
            o = self.owners["mouse"]
            if o is not None:
                if t != QE.MouseMove and ev.button() != o[1] and ev.button() in self.eaten["mouse"]:
                    if t == QE.MouseButtonRelease:
                        self.eaten["mouse"].discard(ev.button())
                    return True   # the rest of another button pressed during the owned drag
                return self._follow_mouse(o, ev, t)
            for w in list(self.watchers["mouse"]):   # observers share the press: all of them, nothing swallowed
                self._follow_mouse(w, ev, t)
            eaten = self.eaten["mouse"]
            if not eaten:
                return False
            if t == QE.MouseMove:
                eaten.intersection_update([b for b in eaten if ev.buttons() & b])   # a lost release
                return bool(eaten)
            if ev.button() in eaten:
                if t == QE.MouseButtonRelease:
                    eaten.discard(ev.button())
                return True
            return False
        if t == QE.KeyRelease or (t == QE.KeyPress and ev.isAutoRepeat()):
            kid = _key_id(ev)
            o = self.owners["key"]
            if o is not None and kid == o[1]:
                return self._follow_key(o, ev, t)
            for w in [w for w in self.watchers["key"] if w[1] == kid]:
                self._follow_key(w, ev, t)
            if kid in self.eaten["key"]:   # the rest of a key the holder swallowed (outlives the holder's key-up)
                if t == QE.KeyRelease and not ev.isAutoRepeat():
                    self.eaten["key"].discard(kid)
                return True
            return False
        if t == QE.MouseButtonPress:
            if self.owners["mouse"] is not None:   # another button during an owned drag: swallowed with its release
                self.eaten["mouse"].add(ev.button())   # (Houdini's MMB would start its handle drag and leave its undo
                return True                            # group open under ours: F2a audit 4)
            kind, which = "press", ev.button()
        elif t == QE.KeyPress:
            kind, which = "key", _key_id(ev)
        else:
            return False
        held = self.owners["key"]
        if held is None and not _gestures:
            return False
        top = receiving_top(receiver)   # widgetAt() would need a screen under the point
        if kind == "press":
            w = top and (top.childAt(top.mapFromGlobal(ev.globalPosition().toPoint())) or top)
            viewer = viewer_of(w)
        else:
            focus = top and top.focusWidget()
            viewer = None if isinstance(focus, _TEXT) else viewer_of(focus)
        if held is not None and self._call(held[0], "other", ev, viewer) is True:
            self.eaten["mouse" if kind == "press" else "key"].add(which)   # its repeats and release go too
            return True   # the gesture holding a key took this key or click
        slot = SLOT[kind]
        if not _gestures or self.owners[slot] is not None or viewer is None:
            return False   # a second key while one is held is only the holder's "other"
        watchers = []
        for fn in list(_gestures.values()):
            owner = [fn, which, True]
            self.owners[slot] = owner          # before the call: a nested event loop inside fn must see it
            res = self._call(fn, kind, ev, viewer)
            if res is True:
                for w in watchers + self.watchers[slot]:   # a gesture that takes the press wins: observers get cancel
                    self._call(w[0], "cancel", ev, None)
                self.watchers[slot] = []
                return True
            if self.owners[slot] is owner:
                self.owners[slot] = None
            if res == OBSERVE:
                watchers.append([fn, which, False])   # observers share the press; every later gesture is still asked
        for w in self.watchers[slot]:   # a new press replaces the observers of an older one: they get cancel
            self._call(w[0], "cancel", ev, None)
        self.watchers[slot] = watchers
        return False

    def _end(self, slot, o):
        if o[2]:
            self.owners[slot] = None
        elif o in self.watchers[slot]:
            self.watchers[slot].remove(o)

    def _follow_mouse(self, o, ev, t):
        fn, which, swallow = o
        if t == QE.MouseMove:
            if not ev.buttons() & which:   # the release was lost (another window, a dialog): give the mouse back
                self._end("mouse", o)
                self._call(fn, "cancel", ev, None)
                return False
            self._call(fn, "move", ev, None)
            return swallow
        if t == QE.MouseButtonDblClick:
            return ev.button() == which and swallow   # Qt sends it after the second press of a double-click
        if ev.button() == which:   # release
            self._end("mouse", o)
            self._call(fn, "release", ev, None)
            return swallow
        return False

    def _follow_key(self, o, ev, t):
        fn, which, swallow = o
        if t == QE.KeyRelease and not ev.isAutoRepeat():
            self._end("key", o)
            self._call(fn, "keyup", ev, None)
        else:
            self._call(fn, "key", ev, None)
        return swallow

    def _call(self, fn, kind, ev, viewer):
        try:
            return fn(kind, ev, viewer)
        except Exception:  # noqa: BLE001 - a broken gesture must never break Houdini input
            LOG.error("modelUI gesture failed\n%s", traceback.format_exc())
            for slot, o in self.owners.items():
                if o is not None and o[0] is fn:
                    self.owners[slot] = None
            for slot in self.watchers:
                self.watchers[slot] = [w for w in self.watchers[slot] if w[0] is not fn]
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
    """Install the layer (switch feature hook); the demo gesture only with PF_MODELUI_DEMO=1 (the F1 checks): its
    Ctrl+Shift+LMB is Houdini's toggle-select key. ``fallback`` forces the per-window filters."""
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
    if os.environ.get("PF_MODELUI_DEMO") == "1":
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
