"""Clone (Max's Clone Options, with an Array-lite): copies of the selection as Copy, Instance or Reference, any number of
them, each one moved, turned and scaled a step further than the one before. One undo step; the clones are selected.

- Copy: an independent duplicate (a piece: a new piece; an object: the object with its whole node network).
- Instance: shares the original. An object: a new object whose only node is an Object Merge of the original, packed,
  so it always shows the original's result. A piece: a new piece (pieces share their source file anyway) marked
  ``pf_clone_kind`` "instance" / ``pf_clone_of`` for the modifier stack.
- Reference: shares the original and adds its own nodes on top. An object: a new object starting with an Object Merge
  of the original (unpacked), the place for its own modifiers. A piece: marked "reference" like an instance.

Entry points: polyfactory > Clone... and the Scene Explorer's button. ``clone`` is the part without a dialog
(headless checks: tests/modelui/check_clone.py).
"""
import hou
from hutil.Qt import QtCore, QtWidgets

from polyfactory.modelui import containers, pieces_ui, scene

KINDS = ("copy", "instance", "reference")
LAST = {"kind": "copy", "count": 1, "move": (0.0, 0.0, 0.0), "rotate": (0.0, 0.0, 0.0), "scale": 1.0}   # the dialog
# opens with what was used last (Max does the same)


def step(m, k, move, rotate, scale):
    """World matrix of the k-th copy of an item at ``m``: scaled and turned k steps about its own position, then moved
    k steps."""
    p = m.extractTranslates()
    d = (hou.hmath.buildTranslate(-p) * hou.hmath.buildScale(scale ** k, scale ** k, scale ** k)
         * hou.hmath.buildRotate(hou.Vector3(rotate) * k) * hou.hmath.buildTranslate(p)
         * hou.hmath.buildTranslate(hou.Vector3(move) * k))
    return m * d


def _clone_object(node, kind):
    if kind == "copy":
        return hou.copyNodesTo([node], node.parent())[0]
    n = node.parent().createNode("geo", node.name() + ("_inst" if kind == "instance" else "_ref"))
    om = n.createNode("object_merge", "original")
    om.parm("objpath1").set(node.path())   # Houdini follows a rename of the original
    om.parm("xformtype").set("none")   # the original's own geometry; this object's transform places it
    if kind == "instance":
        om.parm("pack").set(1)
        om.parm("pivot").set("origin")
    om.setDisplayFlag(True)
    om.setRenderFlag(True)
    n.setUserData("pf_clone_kind", kind)   # for the modifier stack: a reference's own nodes go after "original"
    return n


def clone(pids, kind="copy", count=1, move=(0, 0, 0), rotate=(0, 0, 0), scale=1.0):
    """``count`` clones of every item in ``pids``; returns the new pids (selected), in item order then copy order."""
    if kind not in KINDS:
        raise ValueError("kind must be one of %s" % (KINDS,))
    pids, count = list(pids), int(count)
    if not pids or count < 1:
        return []
    local = {}   # one read per container (get_xform per piece scans every point: quadratic)
    for pid in pids:
        if isinstance(pid, tuple):
            c = scene.MixedScene._split(pid)[0]
            if c not in local:
                local[c] = containers.transforms(c)
    start = {pid: (local[scene.MixedScene._split(pid)[0]][pid[2]] * scene.MixedScene._split(pid)[0].worldTransform()
                   if isinstance(pid, tuple) else pieces_ui.get_xform(pid)) for pid in pids}
    new, xforms = [], {}
    with hou.undos.group("modelUI: clone (%s)" % kind):
        per_container = {}
        for pid in pids:
            if isinstance(pid, tuple):
                per_container.setdefault(scene.MixedScene._split(pid)[0], []).append(pid)
        made = {}
        for c, items in per_container.items():   # one edit per container for all its clones
            ids = containers.copy_pieces(c, [p[2] for p in items for _ in range(count)],
                                         "" if kind == "copy" else kind)
            for j, pid in enumerate(items):
                made[pid] = [("piece", c.sessionId(), i) for i in ids[j * count:(j + 1) * count]]
        for pid in pids:
            if not isinstance(pid, tuple):
                node = hou.nodeBySessionId(pid)
                made[pid] = [_clone_object(node, kind).sessionId() for _ in range(count)]
            for k, cp in enumerate(made[pid], 1):
                xforms[cp] = step(start[pid], k, move, rotate, scale)
                new.append(cp)
        pieces_ui.set_xforms(xforms)
    scene.current().select(new)
    return new


class CloneDialog(QtWidgets.QDialog):
    """Clone Options: kind, number of copies, and what each copy adds to the one before (move, rotate, scale)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Clone")
        form = QtWidgets.QFormLayout(self)
        self.kind = {}
        row = QtWidgets.QHBoxLayout()
        for k in KINDS:
            self.kind[k] = QtWidgets.QRadioButton(k.capitalize())
            row.addWidget(self.kind[k])
        self.kind[LAST["kind"]].setChecked(True)
        form.addRow("Object", row)
        self.count = QtWidgets.QSpinBox(minimum=1, maximum=1000, value=LAST["count"])
        form.addRow("Number of copies", self.count)
        self.move = self._vec(form, "Move each copy", LAST["move"], -1e6, 1e6)
        self.rotate = self._vec(form, "Rotate each copy", LAST["rotate"], -360.0, 360.0)
        self.scale = QtWidgets.QDoubleSpinBox(minimum=1.0, maximum=1000.0, value=LAST["scale"] * 100.0, suffix=" %")
        form.addRow("Scale each copy", self.scale)
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    @staticmethod
    def _vec(form, label, values, lo, hi):
        row, boxes = QtWidgets.QHBoxLayout(), []
        for v in values:
            b = QtWidgets.QDoubleSpinBox(minimum=lo, maximum=hi, decimals=3, value=v)
            row.addWidget(b)
            boxes.append(b)
        form.addRow(label, row)
        return boxes

    def values(self):
        return {"kind": next(k for k, b in self.kind.items() if b.isChecked()), "count": self.count.value(),
                "move": tuple(b.value() for b in self.move), "rotate": tuple(b.value() for b in self.rotate),
                "scale": self.scale.value() / 100.0}

    def accept(self):
        v = self.values()
        LAST.update(v)
        clone(scene.current().selected(), **v)
        super().accept()


def show_dialog():
    """The Clone dialog for the current selection (a status message when nothing is selected)."""
    if not scene.current().selected():
        hou.ui.setStatusMessage("Clone: select pieces or objects first", hou.severityType.Warning)
        return None
    dlg = CloneDialog(hou.qt.mainWindow())
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    dlg.show()
    return dlg
