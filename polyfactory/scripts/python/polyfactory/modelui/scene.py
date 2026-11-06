"""modelUI scene model: the pieces of the scene, behind one small interface the panels use.

``current()`` returns the backend: ``MixedScene`` (Hannes' choice): every geometry object that is not a container is
one piece (``ObjectScene``), and every point of a container object (``containers.py``) is one piece too. The panels
do not know the difference. Piece ids are opaque to callers: node session ids for objects (stable across renames),
``("piece", <container session id>, pf_piece)`` for container pieces.

Interface: pieces() -> [id]; name(id); rename(id, name) -> the name it got; selected() -> [id]; select(ids);
hidden(id); set_hidden(ids, hide); delete(ids); watch(fn) / unwatch(fn): fn() after any change of the list, names,
visibility or selection (called inside Houdini's callback: defer real work).
"""
import hou

from polyfactory.modelui import containers

_OBJ_EVENTS = (hou.nodeEventType.ChildCreated, hou.nodeEventType.ChildDeleted,
               hou.nodeEventType.ChildSelectionChanged)
_PIECE_EVENTS = (hou.nodeEventType.NameChanged, hou.nodeEventType.FlagChanged)
_STASH_EVENTS = (hou.nodeEventType.ParmTupleChanged,)


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
        return [] if r is None else [n for n in r.children()
                                     if n.type().name() == "geo" and not containers.is_container(n)]

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
        s = MixedScene()
        hou.session._pf_modelui_scene = s
    return s


class MixedScene(ObjectScene):
    """Objects (ObjectScene) plus the pieces packed in container objects."""

    def __init__(self, root="/obj"):
        super().__init__(root)
        self._piece_sel = set()
        self._cache = {}      # container session id -> (stash cook count, {pf_piece: (name, hidden)})
        self._armed = {}      # stash node session id -> stash node, while watching

    @staticmethod
    def _split(pid):
        c = hou.nodeBySessionId(pid[1])
        if c is None or not containers.is_container(c):
            raise KeyError("container of piece %r is gone" % (pid,))
        return c, pid[2]

    def _rows(self, c):
        st = containers.stash(c)
        st.geometry()   # cooks the stash if it changed, so its cook count tells
        hit = self._cache.get(c.sessionId())
        if hit is None or hit[0] != st.cookCount():
            hit = (st.cookCount(), {i: (n, bool(h)) for i, n, h in containers.piece_rows(c)})
            self._cache[c.sessionId()] = hit
        return hit[1]

    def _row(self, pid):
        c, piece = self._split(pid)
        row = self._rows(c).get(piece)
        if row is None:
            raise KeyError("piece %r is gone" % (pid,))
        return c, piece, row

    def _by_container(self, pids):
        groups = {}
        for pid in pids:
            c, piece = self._split(pid)
            groups.setdefault(c, []).append(piece)
        return groups

    def pieces(self):
        out = super().pieces()
        for c in containers.containers(self.root):
            if self._watchers:
                self._arm_stash(c)
            out += [("piece", c.sessionId(), i) for i in self._rows(c)]
        return out

    def name(self, pid):
        return self._row(pid)[2][0] if isinstance(pid, tuple) else super().name(pid)

    def rename(self, pid, name):
        if not isinstance(pid, tuple):
            return super().rename(pid, name)
        c, piece, _ = self._row(pid)
        return containers.rename_piece(c, piece, name)

    def hidden(self, pid):
        return self._row(pid)[2][1] if isinstance(pid, tuple) else super().hidden(pid)

    def set_hidden(self, pids, hide):
        with hou.undos.group("modelUI: hide" if hide else "modelUI: show"):
            super().set_hidden([p for p in pids if not isinstance(p, tuple)], hide)
            for c, pieces in self._by_container([p for p in pids if isinstance(p, tuple)]).items():
                containers.set_hidden(c, pieces, hide)

    def delete(self, pids):
        with hou.undos.group("modelUI: delete"):
            groups = self._by_container([p for p in pids if isinstance(p, tuple)])
            super().delete([p for p in pids if not isinstance(p, tuple)])
            for c, pieces in groups.items():
                containers.delete_pieces(c, pieces)

    def selected(self):
        live = set()
        for pid in self._piece_sel:
            try:
                self._row(pid)
                live.add(pid)
            except KeyError:
                pass
        self._piece_sel = live
        return super().selected() + sorted(live)

    def select(self, pids):
        pieces = {p for p in pids if isinstance(p, tuple)}
        super().select([p for p in pids if not isinstance(p, tuple)])
        if pieces != self._piece_sel:
            self._piece_sel = pieces
            self._notify()   # piece selection is ours: no Houdini event tells the watchers

    # --- change notification: a container's pieces change with its stash ------------------------------------------
    def _arm_stash(self, c):
        st = containers.stash(c)
        if st.sessionId() not in self._armed:
            st.addEventCallback(_STASH_EVENTS, self._event)
            self._armed[st.sessionId()] = st

    def _arm(self, on):
        super()._arm(on)
        if on:
            for c in containers.containers(self.root):
                self._arm_stash(c)
        else:
            for st in self._armed.values():
                try:
                    st.removeEventCallback(_STASH_EVENTS, self._event)
                except hou.Error:   # deleted with its container
                    pass
            self._armed = {}
