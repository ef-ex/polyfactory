"""modelUI Modify panel (Python panel ``pf_modelui_stack``, F2c): the modifier stack of the selected object.

Like 3ds Max's Modify panel: the Modifier List adds an operation from the registry (``operations.py``) above the
selected entry (default the top; with the component selection made on the node it reads); the stack lists the
object's real Houdini nodes top first (``stack.chain``); its buttons move, delete, collapse and open the network; the
check box is on/off (bypass). The selected entry's parameters show below (Houdini's own parameter editor,
``hou.qt.ParmDialog``), with a "Pick" button per input the registry names (Object Merge into the stack) and a
"Use selection" button per group field.

Selecting an entry takes the viewer into the object (SOP level) and shows the entry's own viewer state (PolyExtrude's
handle, Edit's tools, a lattice's cage); clearing it or selecting another object goes back to object level. A
container piece shows as one row; its first modifier promotes it (stack.add). Every edit is one undo step (stack.py);
selecting entries and moving the viewer are not undo entries. The panel follows the scene's selection
(``scene.current()``), and every node of the shown object (network editor edits, undo) through node callbacks.
"""
import contextlib
import functools
import logging
import time

from hutil.Qt import QtCore, QtWidgets
from PySide6.QtGui import QShortcut   # not exposed by hutil.Qt

import hou

from polyfactory.modelui import containers, operations, scene as scene_mod, stack

Qt = QtCore.Qt
LOG = logging.getLogger(__name__)   # debug: the viewer decisions (the GUI checks log them)
SID = Qt.UserRole
_NODE_EVENTS = (hou.nodeEventType.InputRewired, hou.nodeEventType.FlagChanged, hou.nodeEventType.NameChanged)
_OBJ_EVENTS = (hou.nodeEventType.ChildCreated, hou.nodeEventType.ChildDeleted)
# object-level states the viewer goes back to (Q = select, W/E/R = pose). Never another: back at object level Houdini
# enters the current object's own tool state ("geo"), where a click CREATES a geometry object (seen in a GUI run)
OBJ_STATES = ("select", "pose")
SETTLE = 1.0   # s after the panel brought the viewer out (and finished) in which Houdini's late change is put back


def viewer():
    return hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)


def _status(msg):
    hou.ui.setStatusMessage("modelUI: " + msg, hou.severityType.Warning)


def _alive(sid):
    return hou.nodeBySessionId(sid) if sid is not None else None


def _action(fn):
    """A user action of the panel: no list rebuild while it runs (ModifyPanel._hold)."""
    @functools.wraps(fn)
    def run(self, *a, **kw):
        with self._hold():
            return fn(self, *a, **kw)
    return run


class ModifyPanel(QtWidgets.QWidget):
    def __init__(self, model=None, mode="model", parent=None):
        super().__init__(parent)
        self.model = model or scene_mod.current()
        self.mode = mode
        self._syncing = False
        self._busy = False      # inside one of our actions or a refresh: a refresh asked for now runs after it
        self._pending = False
        self._settle_until = 0.0   # time.monotonic() until which Houdini's late viewer changes are put back
        self._sv = None         # the scene viewer with our event callback
        self._watching = False
        self._armed = {}       # node session id -> (node, events) with our callback
        self._rows = None      # what the list shows: [(sid, text, bypassed)]
        self._pid = None       # the scene id whose stack shows (object session id or container piece)
        self._entry = None     # session id of the selected entry
        self._picking = None   # (entry sid, input index, owner pid) while a Pick button waits for an object
        self._obj_state = None  # the viewer state at object level before we went into an object
        self._went_in = False   # we took the viewer into an object (so we bring it back)
        self.parms = None
        self.title = QtWidgets.QLabel()
        self.title.setWordWrap(True)
        self.ops = QtWidgets.QComboBox()
        self.ops.addItem("Modifier List", None)
        for op in operations.ops(mode):
            self.ops.addItem(hou.qt.Icon(operations.icon(op)), op["label"], op["key"])
        self.ops.activated.connect(self._op_chosen)
        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list.itemSelectionChanged.connect(self._entry_chosen)
        self.list.itemChanged.connect(self._row_changed)
        QShortcut(Qt.Key_Delete, self.list, self.delete_entry, context=Qt.WidgetShortcut)
        self.buttons = {}
        row = QtWidgets.QHBoxLayout()
        for key, text, fn in (("up", "Up", lambda: self.move_entry(+1)), ("down", "Down", lambda: self.move_entry(-1)),
                              ("delete", "Delete", self.delete_entry), ("collapse", "Collapse", self.collapse),
                              ("nodes", "Open as nodes", self.open_as_nodes)):
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(fn)
            row.addWidget(b)
            self.buttons[key] = b
        self.buttons["collapse"].setToolTip("Bake the stack up to the selected entry (all of it with none selected) "
                                            "into a plain mesh")
        self.extras = QtWidgets.QVBoxLayout()
        self.parm_box = QtWidgets.QVBoxLayout()
        top, bottom = QtWidgets.QWidget(), QtWidgets.QWidget()   # stack above, parameters below: a splitter between
        t = QtWidgets.QVBoxLayout(top)
        t.setContentsMargins(0, 0, 0, 0)
        t.addWidget(self.title)
        t.addWidget(self.ops)
        t.addWidget(self.list, 1)
        t.addLayout(row)
        t.addLayout(self.extras)
        bottom.setLayout(self.parm_box)
        self.parm_box.setContentsMargins(0, 0, 0, 0)
        self.list.setMinimumHeight(90)
        split = QtWidgets.QSplitter(Qt.Vertical)
        split.addWidget(top)
        split.addWidget(bottom)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 2)
        split.setSizes([350, 650])   # Houdini's parameter editor has no size hint: without this it got a sliver
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(split)
        self._timer = QtCore.QTimer(self, singleShot=True, interval=0, timeout=self.refresh)   # coalesce callbacks
        # deleted without close_down (Houdini destroys a pane's panel; onDestroyInterface may name another one): its
        # callbacks go with it, or they would keep acting on a dead widget (seen in a GUI run: a stray panel's settle)
        self.destroyed.connect(functools.partial(_forget, self.__dict__, self.model, self._timer.start,
                                                 self._viewer_event, self._node_event))
        self.set_watching(True)

    # --- following the scene ----------------------------------------------------------------------------------------
    def set_watching(self, on):
        """Follow the scene (and refresh now) or stop: off while modelUI is off (no callbacks left in Houdini)."""
        if on and not self._watching:
            self.model.watch(self._timer.start)
            self._sv = viewer()   # its state changes after ours (see _settle)
            if self._sv is not None:
                self._sv.addEventCallback(self._viewer_event)
            self._watching = True
            self.refresh()
        elif not on and self._watching:
            self.model.unwatch(self._timer.start)
            if self._sv is not None:
                try:
                    self._sv.removeEventCallback(self._viewer_event)
                except hou.Error:   # the viewer is gone
                    pass
                self._sv = None
            self._arm(None)
            self._picking = None
            self._show_parms(None)   # the parameter editor lets go of its node while modelUI is off
            self._watching = False

    def close_down(self):
        self.set_watching(False)

    def _node_event(self, **kw):
        self._timer.start()   # never work inside Houdini's callback

    def _arm(self, obj):
        """Callbacks on the shown object (children created/deleted) and on each of its nodes (wiring, flags, names)."""
        want = {}
        if obj is not None:
            want[obj.sessionId()] = (obj, _OBJ_EVENTS)
            for n in obj.children():
                want[n.sessionId()] = (n, _NODE_EVENTS)
        for sid in [s for s in self._armed if s not in want]:
            node, events = self._armed.pop(sid)
            try:
                node.removeEventCallback(events, self._node_event)
            except hou.Error:   # deleted, or never registered
                pass
        for sid, (node, events) in want.items():
            if sid not in self._armed:
                node.addEventCallback(events, self._node_event)
                self._armed[sid] = (node, events)

    def _inside(self):
        """The geometry object the viewer is inside (SOP level), or None. Never a container: its nodes are modelUI's
        storage, not a stack (Houdini itself moved the viewer into one after an undo of a promote)."""
        sv = viewer()
        try:
            p = sv.pwd() if sv is not None else None
            return p if (p is not None and p.type().name() == "geo" and p.parent() == hou.node("/obj")
                         and not containers.is_container(p)) else None
        except hou.Error:
            return None

    def target(self):
        """The scene id whose stack shows: the one selected item; inside an object, that object while nothing else is
        selected (Houdini may drop the object-level selection when the viewer goes into it)."""
        if self._picking is not None:
            return self._picking[2]
        sel = self.model.selected()
        ins = self._inside()
        if ins is not None and (not sel or sel == [ins.sessionId()]):
            return ins.sessionId()
        return sel[0] if len(sel) == 1 else None

    def obj(self):
        return stack.object_of(self._pid) if self._pid is not None else None

    def entry(self):
        return _alive(self._entry)

    @contextlib.contextmanager
    def _hold(self):
        """No refresh inside: Houdini runs Qt events inside some HOM calls (SceneViewer.setPwd ran our coalescing
        timer), and a list rebuilt there deleted the item whose click was being handled: Houdini segfaulted (fault
        stack 2026-11-10, ideas/modelui.md F2c). A refresh asked for meanwhile runs from the event loop afterwards."""
        if self._busy:
            yield
            return
        self._busy = True
        try:
            yield
        finally:
            self._busy = False
            if self._settle_until == float("inf"):   # Houdini's nested event loops made our own leave take seconds
                self._settle_until = time.monotonic() + SETTLE   # on a loaded PC: the window starts when it is done
            if self._pending:   # a timer of its own: restarting self._timer here (often inside its own timeout, with
                LOG.debug("deferred refresh scheduled")   # Houdini's nested events) lost the refresh in GUI runs
                self._pending = False
                QtCore.QTimer.singleShot(0, self, self.refresh)

    def refresh(self):
        """Show the stack of the target; keep the selected entry when it is still there."""
        if self._busy:
            LOG.debug("refresh deferred (busy)")
            self._pending = True
            return
        with self._hold():
            self._refresh()

    def _refresh(self):
        if time.monotonic() < self._settle_until:
            self._settle()
        if self._picking is not None:
            self._take_pick()
        if self._entry is not None and _alive(self._entry) is None:
            self._entry = None   # deleted (undo, network editor): back to object level, as without an entry
            self._leave_object()
        self._syncing = True
        try:
            try:
                pid = self.target()
                if isinstance(pid, tuple):
                    self.model.name(pid)   # raises KeyError when the piece is gone
            except (KeyError, hou.Error):
                pid = None
            ins = self._inside()
            LOG.debug("refresh: target %s inside %s went_in %s selected %s state %s", pid, ins and ins.path(),
                      self._went_in, self.model.selected(), viewer() and viewer().currentState())
            if self._picking is None and (ins is None and self._went_in or ins is not None and pid != ins.sessionId()):
                self._leave_object()   # another target; or Houdini took the viewer out itself (its state is ours to restore)
            if pid != self._pid:
                self._entry = None
            self._pid = pid
            obj = self.obj()
            self._arm(obj)
            nodes = stack.chain(obj)[::-1]
            if isinstance(pid, tuple):
                self.title.setText("%s (kitbash piece: its first modifier makes it an object)" % self.model.name(pid))
                rows = [(None, "%s (piece)" % self.model.name(pid), False)]
            elif obj is not None:
                self.title.setText(obj.name())
                rows = [(n.sessionId(), "%s  (%s)" % (n.type().description(), n.name()), n.isBypassed()) for n in nodes]
            else:
                n_sel = len(self.model.selected())
                self.title.setText("%d selected: select one object" % n_sel if n_sel else "Nothing selected")
                rows = []
            if rows != self._rows:
                self.list.clear()
                base = nodes[-1].sessionId() if nodes else None
                for sid, text, bypassed in rows:
                    it = QtWidgets.QListWidgetItem(text)
                    it.setData(SID, sid)
                    node = _alive(sid)
                    if node is not None:
                        it.setIcon(hou.qt.Icon(node.type().icon()))
                    if sid is not None and sid != base:   # the base is always on (as in Max)
                        it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
                        it.setCheckState(Qt.Unchecked if bypassed else Qt.Checked)
                    self.list.addItem(it)
                self._rows = rows
            if self._entry is not None and self._entry not in [r[0] for r in rows]:
                self._entry = None
            for i in range(self.list.count()):
                it = self.list.item(i)
                it.setSelected(it.data(SID) is not None and it.data(SID) == self._entry)
            self._update()
        finally:
            self._syncing = False

    def _update(self):
        """Buttons, pick/selection rows and the parameter editor of the selected entry."""
        obj, node = self.obj(), self.entry()
        nodes = stack.chain(obj) if obj is not None else []
        i = [n.sessionId() for n in nodes].index(node.sessionId()) if node is not None else -1
        self.ops.setEnabled(self._pid is not None)
        self.buttons["up"].setEnabled(0 < i < len(nodes) - 1)
        self.buttons["down"].setEnabled(i > 1)
        self.buttons["delete"].setEnabled(i > 0)
        self.buttons["collapse"].setEnabled(obj is not None and bool(nodes))
        self.buttons["nodes"].setEnabled(obj is not None)
        self._build_extras(node)
        self._show_parms(node)

    def _build_extras(self, node):
        while self.extras.count():
            w = self.extras.takeAt(0).widget()
            if w is not None:
                w.hide()
                w.deleteLater()
        self.pick_buttons, self.group_buttons = {}, {}
        op = operations.for_node(node, self.mode) if node is not None else None
        if op is None:
            return
        for index, spec in sorted(op.get("inputs", {}).items()):
            waiting = self._picking is not None and self._picking[:2] == (node.sessionId(), index)
            got = stack.picked(node, index)
            text = ("Click an object for %s (click here to cancel)" % spec["label"] if waiting else
                    "Pick %s: %s" % (spec["label"], got.rsplit("/", 1)[-1] if got else "none"))
            b = QtWidgets.QPushButton(text)
            b.clicked.connect(lambda _=False, n=node, i=index: self.arm_pick(n, i))
            self.extras.addWidget(b)
            self.pick_buttons[index] = b
        for g in op.get("groups", []):
            b = QtWidgets.QPushButton("Use selection for %s: %s" % (g["parm"], node.parm(g["parm"]).eval() or "all"))
            b.clicked.connect(lambda _=False, n=node, p=g["parm"]: self.use_selection(n, p))
            self.extras.addWidget(b)
            self.group_buttons[g["parm"]] = b

    def _show_parms(self, node):
        if self.parms is not None:
            try:
                shown = self.parms.node()
            except hou.Error:
                shown = None
            if node is None or shown is None:
                self.parms.hide()
                self.parms.deleteLater()   # its node is gone or nothing is selected: a fresh editor next time
                self.parms = None
        if node is None:
            return
        if self.parms is None:
            self.parms = hou.qt.ParmDialog(node)
            self.parm_box.addWidget(self.parms)
        elif self.parms.node() != node:
            self.parms.setNode(node)

    # --- the viewer: into the object for an entry, back to object level without one --------------------------------
    def _enter(self, node):
        """Show ``node``'s own viewer state inside its object (its handle), or Houdini's component selection."""
        sv = viewer()
        if sv is None:
            return
        obj = node.parent()
        if self._inside() is None and sv.currentState() in OBJ_STATES:
            self._obj_state = sv.currentState()
        self._went_in = True
        with hou.undos.disabler():
            if sv.pwd() != obj:
                sv.setPwd(obj)
            st = stack.state_node(node, self.mode)
            st.setCurrent(True, clear_all_selected=False)
            try:
                sv.enterCurrentNodeState()
            except hou.Error:
                sv.setCurrentState("select")
        # Houdini drops the object-level selection when the viewer goes into the object; selecting the object again
        # takes the viewer back out (probe 2026-11-09), so the stack keeps showing the object it is inside (target())

    def _leave_object(self):
        sv, ins = viewer(), self._inside()
        if sv is None or (ins is None and not self._went_in):
            return
        LOG.debug("leave object")
        self._went_in = False
        self._settle_until = float("inf")   # armed; the SETTLE s count from the end of this action (_hold)
        sel = self.model.selected()
        self._to_object_level(sv)
        if not self.model.selected():   # Houdini drops the object selection on the way (in, and out with setPwd): what
            want = sel or ([ins.sessionId()] if ins is not None else [])   # was chosen stays, else the object we were in
            if want:
                self.model.select(want)

    def _to_object_level(self, sv):
        with hou.undos.disabler():
            if sv.pwd() != hou.node("/obj"):   # ours, or wherever Houdini put it when our object went away
                sv.setPwd(hou.node("/obj"))
            if sv.currentState() not in OBJ_STATES:   # also when Houdini took it out (the object was deleted, undo)
                try:
                    sv.setCurrentState(self._obj_state or "select")
                except hou.Error:
                    sv.setCurrentState("select")

    def _settle(self):
        """Houdini changes the viewer once more AFTER we brought it out, in its own deferred update: into the object's
        "geo" tool state (choosing another object while inside), into the container after an undo of a promote (GUI
        runs 2026-11-10). Within SETTLE s of our leaving, a viewer state change at object level is put back."""
        sv = viewer()
        if sv is not None and self._inside() is None:
            self._to_object_level(sv)

    def _viewer_event(self, **kw):
        LOG.debug("viewer event %s %s (panel %x busy %s)", kw.get("event_type"), kw.get("state_name"), id(self), self._busy)
        if kw.get("event_type") == hou.sceneViewerEvent.StateEntered:
            self._timer.start()   # never work inside Houdini's callback

    # --- user actions (each stack edit is one undo step in stack.py) ---------------------------------------------------
    @_action   # the list is inside its own click here: it must not be rebuilt before that returns
    def _entry_chosen(self):
        if self._syncing:
            return
        items = self.list.selectedItems()
        self._entry = items[0].data(SID) if items else None
        node = self.entry()
        if node is not None:
            self._enter(node)
        else:
            self._leave_object()
        self._update()

    @_action
    def _row_changed(self, it):
        if self._syncing:
            return
        node = _alive(it.data(SID))
        if node is not None and (it.checkState() == Qt.Checked) == node.isBypassed():
            stack.set_enabled(node, it.checkState() == Qt.Checked)
        self.refresh()

    def _selection_for(self, node):
        """(pattern, type) of the viewer's component selection when it was made on ``node``'s geometry, else None."""
        sv = viewer()
        if sv is None or node is None or self._inside() != node.parent():
            return None
        try:
            gs = sv.currentGeometrySelection()
        except hou.Error:
            return None
        if gs is None or not gs.nodes() or not gs.mergedSelectionString():
            return None
        if gs.nodes()[0] != node:
            _status("the component selection is on %s, not on %s: not used" % (gs.nodes()[0].name(), node.name()))
            return None
        return gs.mergedSelectionString(), gs.geometryType()

    @_action
    def add(self, key):
        """Add operation ``key`` above the selected entry (default the top) and select it."""
        if self._pid is None:
            return None
        obj, above = self.obj(), self.entry()
        below = above if above is not None else (stack.chain(obj)[-1] if obj is not None else None)
        try:
            n = stack.add(self._pid, key, above=above, selection=self._selection_for(below), mode=self.mode)
        except (hou.Error, ValueError, KeyError) as e:
            _status("could not add %s: %s" % (key, e))
            return None
        self._pid = n.parent().sessionId()   # a promoted piece is an object now
        self._entry = n.sessionId()
        self.refresh()
        self._enter(n)
        return n

    def _op_chosen(self, index):
        key = self.ops.itemData(index)
        self.ops.setCurrentIndex(0)
        if key:
            self.add(key)

    @_action
    def move_entry(self, step):
        node = self.entry()
        if node is not None:
            stack.move(node, step)
            self.refresh()

    @_action
    def delete_entry(self):
        node = self.entry()
        if node is None:
            return
        self._show_parms(None)   # the editor lets go of the node first
        if stack.delete(node):
            self._entry = None
            self._leave_object()
        self.refresh()

    @_action
    def collapse(self):
        obj = self.obj()
        if obj is None:
            return
        node = self.entry()
        self._show_parms(None)
        try:
            st = stack.collapse(node, obj=obj)
        except hou.Error as e:
            _status(str(e.instanceMessage() if hasattr(e, "instanceMessage") else e))
            return
        self._entry = st.sessionId() if node is not None else None
        self.refresh()

    @_action
    def open_as_nodes(self):
        """The network editor shows the object's nodes with the selected entry (or the top) current and in view."""
        obj = self.obj()
        ne = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.NetworkEditor)
        if obj is None or ne is None:
            return
        nodes = stack.chain(obj)
        node = self.entry() or (nodes[-1] if nodes else None)
        with hou.undos.disabler():
            ne.setIsCurrentTab()
            ne.setPwd(obj)
            if node is not None:
                node.setCurrent(True, clear_all_selected=False)
                b = hou.BoundingRect(node.position(), node.position())
                b.expand((6, 4))
                ne.setVisibleBounds(b)

    @_action
    def arm_pick(self, node, index):
        """The next object selected (viewport or Scene Explorer) goes into input ``index``; again cancels."""
        if self._picking is not None and self._picking[:2] == (node.sessionId(), index):
            self._picking = None
        else:
            self._picking = (node.sessionId(), index, self._pid)
            self._leave_object()   # viewport clicks pick objects again
            hou.ui.setStatusMessage("modelUI: click the object to use (viewport or Scene Explorer)")
        self._update()

    def _take_pick(self):
        """While a Pick waits: a newly selected other object is wired in and the selection goes back. True if taken."""
        entry_sid, index, owner = self._picking
        sel = self.model.selected()
        if not sel or sel == [owner]:
            return False
        self._picking = None
        node = _alive(entry_sid)
        if node is not None:
            try:
                stack.pick_input(node, index, sel[0], self.mode)
            except (ValueError, KeyError, hou.Error) as e:
                _status("could not pick: %s" % e)
        self.model.select([owner])
        self._entry = entry_sid
        return True

    @_action
    def use_selection(self, node, parm):
        sel = self._selection_for(node.input(0)) if node.input(0) is not None else None
        if sel is None:
            _status("select components on %s first (Houdini's own state for this entry can reselect too)"
                    % (node.input(0).name() if node.input(0) is not None else "its input"))
            return
        try:
            stack.use_selection(node, parm, sel, self.mode)
        except (ValueError, hou.Error) as e:
            _status(str(e))
        self._update()


def _forget(d, model, watch_cb, viewer_cb, node_cb, *_):
    """Drop the callbacks of a deleted panel (its Python attributes outlive the widget)."""
    if d.get("_watching"):
        model.unwatch(watch_cb)
    if d.get("_sv") is not None:
        try:
            d["_sv"].removeEventCallback(viewer_cb)
        except hou.Error:   # the viewer is gone
            pass
    for node, events in d.get("_armed", {}).values():
        try:
            node.removeEventCallback(events, node_cb)
        except hou.Error:   # deleted
            pass
    d.update(_sv=None, _armed={}, _watching=False)


def create_interface():
    w = ModifyPanel()
    hou.session._pf_modelui_stack = w
    return w


def destroy_interface(w):
    if w is not None:
        w.close_down()
    if getattr(hou.session, "_pf_modelui_stack", None) is w:
        hou.session._pf_modelui_stack = None


def _panel():
    return getattr(hou.session, "_pf_modelui_stack", None)


def install():
    """Switch feature hook: the desk's panel (if Houdini built it already) follows the scene again; re-armed here, as
    Houdini builds it during the desk switch, when the current desk (and so its viewer) may still be the old one."""
    p = _panel()
    if p is not None:
        p.set_watching(False)
        p.set_watching(True)


def uninstall():
    """Switch feature hook: the panel stops following the scene (no callbacks left while modelUI is off)."""
    if _panel() is not None:
        _panel().set_watching(False)
