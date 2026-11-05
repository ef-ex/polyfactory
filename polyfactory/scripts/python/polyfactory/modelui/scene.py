"""modelUI scene model: the pieces of the scene, behind one small interface the panels use.

``current()`` returns the backend. Today: ``ObjectScene`` (one geometry object under /obj = one piece). A second
backend (pieces packed in container objects, see the measurements in ideas/modelui.md) implements the same methods
and ``current()`` picks it; the panels do not change. Piece ids are opaque to callers (here: node session ids, stable
across renames).

Interface: pieces() -> [id]; name(id); rename(id, name) -> the name it got; selected() -> [id]; select(ids);
hidden(id); set_hidden(ids, hide); delete(ids); watch(fn) / unwatch(fn): fn() after any change of the list, names,
visibility or selection (called inside Houdini's callback: defer real work).
"""
import hou

_OBJ_EVENTS = (hou.nodeEventType.ChildCreated, hou.nodeEventType.ChildDeleted,
               hou.nodeEventType.ChildSelectionChanged)
_PIECE_EVENTS = (hou.nodeEventType.NameChanged, hou.nodeEventType.FlagChanged)


class ObjectScene:
    def __init__(self, root="/obj"):
        self.root = root
        self._watchers = []

    def _node(self, pid):
        n = hou.nodeBySessionId(pid)
        if n is None:
            raise KeyError("piece %r is gone" % pid)
        return n

    def _geos(self):
        r = hou.node(self.root)
        return [] if r is None else [n for n in r.children() if n.type().name() == "geo"]

    def pieces(self):
        return [n.sessionId() for n in self._geos()]

    def name(self, pid):
        return self._node(pid).name()

    def rename(self, pid, name):
        n = self._node(pid)
        with hou.undos.group("modelUI: rename"):
            n.setName(name, unique_name=True)
        return n.name()

    def selected(self):
        return [n.sessionId() for n in self._geos() if n.isSelected()]

    def select(self, pids):
        with hou.undos.group("modelUI: select"):
            for n in self._geos():
                if n.isSelected():
                    n.setSelected(False)
            for pid in pids:
                self._node(pid).setSelected(True)

    def hidden(self, pid):
        return not self._node(pid).isDisplayFlagSet()

    def set_hidden(self, pids, hide):
        with hou.undos.group("modelUI: hide" if hide else "modelUI: show"):
            for pid in pids:
                self._node(pid).setDisplayFlag(not hide)

    def delete(self, pids):
        nodes = [self._node(pid) for pid in pids]
        with hou.undos.group("modelUI: delete"):
            for n in nodes:
                n.destroy()

    # --- change notification -------------------------------------------------------------------------------------
    def watch(self, fn):
        if not self._watchers:
            self._arm(True)
            hou.hipFile.addEventCallback(self._hip_event)
        self._watchers.append(fn)

    def unwatch(self, fn):
        if fn in self._watchers:
            self._watchers.remove(fn)
            if not self._watchers:
                self._arm(False)
                hou.hipFile.removeEventCallback(self._hip_event)

    def _arm(self, on):
        r = hou.node(self.root)
        pairs = ([(r, _OBJ_EVENTS)] if r is not None else []) + [(n, _PIECE_EVENTS) for n in self._geos()]
        for node, events in pairs:
            try:
                (node.addEventCallback if on else node.removeEventCallback)(events, self._event)
            except hou.OperationFailed:   # remove: was never registered
                pass

    def _event(self, event_type, **kw):
        child = kw.get("child_node")
        if event_type == hou.nodeEventType.ChildCreated and child is not None and child.type().name() == "geo":
            child.addEventCallback(_PIECE_EVENTS, self._event)
        self._notify()

    def _hip_event(self, event_type):
        if event_type in (hou.hipFileEventType.AfterClear, hou.hipFileEventType.AfterLoad):
            self._arm(True)
            self._notify()

    def _notify(self):
        for fn in list(self._watchers):
            fn()


def current():
    """The scene backend the panels use (one per session)."""
    s = getattr(hou.session, "_pf_modelui_scene", None)
    if s is None:
        s = ObjectScene()
        hou.session._pf_modelui_scene = s
    return s
