"""modelUI Scene Explorer (Python panel ``pf_modelui_explorer``): every piece by name; select, rename, hide, delete.

Follows the selection both ways: clicking rows selects the pieces (and so the objects in the viewport), selecting in
the viewport selects the rows. Double-click (or F2) renames, the check box shows/hides, Delete deletes the selected
pieces. It only talks to ``scene.current()``, so another scene backend needs no change here.
"""
from hutil.Qt import QtCore, QtWidgets
from PySide6.QtGui import QShortcut   # not exposed by hutil.Qt

import hou

from polyfactory.modelui import scene as scene_mod

Qt = QtCore.Qt
ID_ROLE = Qt.UserRole


class Explorer(QtWidgets.QWidget):
    def __init__(self, model=None, parent=None):
        super().__init__(parent)
        self.model = model or scene_mod.current()
        self._syncing = False
        self._watching = False
        self.list = QtWidgets.QListWidget()
        self.list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.list.setEditTriggers(QtWidgets.QAbstractItemView.DoubleClicked | QtWidgets.QAbstractItemView.EditKeyPressed)
        self.list.itemSelectionChanged.connect(self._rows_selected)
        self.list.itemChanged.connect(self._row_changed)
        delete = QtWidgets.QPushButton("Delete")
        delete.clicked.connect(self.delete_selected)
        QShortcut(Qt.Key_Delete, self.list, self.delete_selected, context=Qt.WidgetShortcut)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(2, 2, 2, 2)
        lay.addWidget(self.list)
        lay.addWidget(delete)
        self._timer = QtCore.QTimer(self, singleShot=True, interval=0, timeout=self.refresh)   # coalesce callbacks
        self.set_watching(True)

    def set_watching(self, on):
        """Follow the scene (and refresh now) or stop following it: off while modelUI is off, so normal Houdini pays
        nothing for a panel that is not shown."""
        if on and not self._watching:
            self.model.watch(self._timer.start)
            self.refresh()
        elif not on and self._watching:
            self.model.unwatch(self._timer.start)
        self._watching = on

    def close_down(self):
        self.set_watching(False)

    def _rows(self):
        return [self.list.item(i) for i in range(self.list.count())]

    def refresh(self):
        """Rebuild the rows from the model when pieces, names or visibility changed; then mirror its selection."""
        self._syncing = True
        try:
            m = self.model
            want = [(pid, m.name(pid), m.hidden(pid)) for pid in m.pieces()]
            have = [(it.data(ID_ROLE), it.text(), it.checkState() != Qt.Checked) for it in self._rows()]
            if want != have:
                self.list.clear()
                for pid, name, hidden in want:
                    it = QtWidgets.QListWidgetItem(name)
                    it.setData(ID_ROLE, pid)
                    it.setFlags(it.flags() | Qt.ItemIsEditable | Qt.ItemIsUserCheckable)
                    it.setCheckState(Qt.Unchecked if hidden else Qt.Checked)
                    self.list.addItem(it)
            sel = set(m.selected())
            for it in self._rows():
                it.setSelected(it.data(ID_ROLE) in sel)
        finally:
            self._syncing = False

    def selected_ids(self):
        return [it.data(ID_ROLE) for it in self.list.selectedItems()]

    def _rows_selected(self):
        if not self._syncing:
            try:
                self.model.select(self.selected_ids())
            except KeyError:   # a row of a piece deleted a moment ago (its refresh is queued): show the scene now
                self.refresh()

    def _row_changed(self, it):
        if self._syncing:
            return
        pid = it.data(ID_ROLE)
        try:
            if it.text() != self.model.name(pid):
                try:
                    self.model.rename(pid, it.text())
                except hou.Error as e:   # an invalid name ("my hull", ""): keep the old one, say why
                    hou.ui.setStatusMessage("modelUI: cannot rename to %r: %s" % (it.text(), e.instanceMessage()),
                                            hou.severityType.Warning)
            hide = it.checkState() != Qt.Checked
            if hide != self.model.hidden(pid):
                self.model.set_hidden([pid], hide)
        except KeyError:   # the piece was deleted a moment ago
            pass
        finally:
            self._timer.start()   # show the name and state Houdini actually has

    def delete_selected(self):
        ids = self.selected_ids()
        if ids:
            self.model.delete(ids)


def create_interface():
    w = Explorer()
    hou.session._pf_modelui_explorer = w
    return w


def destroy_interface(w):
    if w is not None:
        w.close_down()
    if getattr(hou.session, "_pf_modelui_explorer", None) is w:
        hou.session._pf_modelui_explorer = None


def _panel():
    return getattr(hou.session, "_pf_modelui_explorer", None)


def install():
    """Switch feature hook: the desk's panel (if Houdini built it already) follows the scene again."""
    if _panel() is not None:
        _panel().set_watching(True)


def uninstall():
    """Switch feature hook: the panel stops following the scene (no callbacks left while modelUI is off)."""
    if _panel() is not None:
        _panel().set_watching(False)
