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


def step(m, k, move, rotate, scale, pivot=None):
    """World matrix of the k-th copy of an item at ``m``: scaled and turned k steps about ``pivot`` (world; default its
    position), then moved k steps."""
    p = m.extractTranslates() if pivot is None else hou.Vector3(pivot)
    d = (hou.hmath.buildTranslate(-p) * hou.hmath.buildScale(scale ** k, scale ** k, scale ** k)
         * hou.hmath.buildRotate(hou.Vector3(rotate) * k) * hou.hmath.buildTranslate(p)
         * hou.hmath.buildTranslate(hou.Vector3(move) * k))
    return m * d


NOT_COPIED = {"t", "r", "s", "scale"}   # an Instance/Reference takes every object setting of the original but these
# (material, display, render, pivot, ...); clone() places it with setWorldTransform
SKIP_TYPES = (hou.parmTemplateType.Button, hou.parmTemplateType.FolderSet, hou.parmTemplateType.Folder,
              hou.parmTemplateType.Separator, hou.parmTemplateType.Label)


def original_of(node):
    """The object an Instance/Reference object shows (None for any other object)."""
    om = node.node("original") if node.userData("pf_clone_kind") else None
    return hou.node(om.parm("objpath1").evalAsString()) if om is not None else None


def root_original(node):
    """Follows Instance/Reference objects back to an object with its own network."""
    for _ in range(100):
        o = original_of(node)
        if o is None:
            return node
        node = o
    return node


def hand_over(nodes):
    """Before ``nodes`` are deleted: an original whose Instances/References stay gets an heir, like Max: its first
    remaining clone receives the original's network (in place of its "original" Object Merge, under its own nodes)
    and the other clones show the heir. Without this every instance of a deleted original went empty for good."""
    going = {n.path() for n in nodes}
    for node in nodes:
        clones = sorted((n for n in node.parent().children()
                         if n.path() not in going and original_of(n) is not None and original_of(n).path() == node.path()),
                        key=lambda n: n.sessionId())
        if not clones:
            continue
        heir, om = clones[0], clones[0].node("original")
        kids = node.children()
        copied = hou.copyNodesTo(kids, heir) if kids else []
        twin = dict(zip(kids, copied))
        disp, rend = twin.get(node.displayNode()), twin.get(node.renderNode())
        if disp is not None:
            for out in om.outputs():   # a Reference's own nodes now sit on the original's network
                for i, src in enumerate(out.inputs()):
                    if src == om:
                        out.setInput(i, disp)
            if om.isDisplayFlagSet():
                disp.setDisplayFlag(True)
            if om.isRenderFlagSet():
                (rend or disp).setRenderFlag(True)
        om.destroy()
        heir.destroyUserData("pf_clone_kind")
        for other in clones[1:]:
            other.node("original").parm("objpath1").set(heir.path())


def _copy_settings(src, dst):
    for pt in src.parmTuples():
        if pt.name() in NOT_COPIED or pt.parmTemplate().type() in SKIP_TYPES:
            continue
        d = dst.parmTuple(pt.name())
        if d is None:
            continue
        for sp, dp in zip(pt, d):
            try:
                dp.setExpression(sp.expression(), sp.expressionLanguage())
            except hou.OperationFailed:   # no expression: the value (strings unexpanded: $HIP stays $HIP)
                dp.set(sp.unexpandedString() if pt.parmTemplate().type() == hou.parmTemplateType.String else sp.eval())


def _clone_object(node, kind):
    if kind == "copy":   # always independent: a copy of an Instance/Reference copies the network it shows
        src = root_original(node)
        n = hou.copyNodesTo([src], node.parent())[0]
        if src is not node:
            _copy_settings(node, n)
        n.setFirstInput(node.input(0))   # keeps the parent link
        return n
    if node.userData("pf_clone_kind") == "instance":   # an instance of an instance shares the same original
        node = root_original(node)
    n = node.parent().createNode("geo", node.name() + ("_inst" if kind == "instance" else "_ref"))
    for ch in n.children():   # a geo object may come with a default node
        ch.destroy()
    _copy_settings(node, n)
    n.setFirstInput(node.input(0))
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
    label = "modelUI: clone (%s)" % kind
    n_undo = len(hou.undos.undoLabels())
    try:
        new = _clone(pids, kind, count, move, rotate, scale, start, label)
    except Exception:
        labels = hou.undos.undoLabels()
        if len(labels) > n_undo and labels[0] == label:   # a half-made clone goes away again
            hou.undos.performUndo()
        raise
    scene.current().select(new)
    return new


def _clone(pids, kind, count, move, rotate, scale, start, label):
    new, xforms = [], {}
    with hou.undos.group(label):
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
            pivot = None
            if not isinstance(pid, tuple):
                node = hou.nodeBySessionId(pid)
                made[pid] = [_clone_object(node, kind).sessionId() for _ in range(count)]
                pivot = hou.Vector3(node.parmTuple("p").eval()) * node.worldTransform()   # Max turns about the pivot
            for k, cp in enumerate(made[pid], 1):
                xforms[cp] = step(start[pid], k, move, rotate, scale, pivot)
                new.append(cp)
        pieces_ui.set_xforms(xforms)
    return new


class CloneDialog(QtWidgets.QDialog):
    """Clone Options: kind, number of copies, and what each copy adds to the one before (move, rotate, scale)."""

    def __init__(self, pids=None, parent=None):
        super().__init__(parent)
        self.pids = list(scene.current().selected() if pids is None else pids)   # what was selected when it opened:
        # it is not modal, the viewport selection may change while it is open
        self.setWindowTitle("Clone %d item%s" % (len(self.pids), "" if len(self.pids) == 1 else "s"))
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
        clone(self.pids, **v)
        super().accept()


def show_dialog():
    """The Clone dialog for the current selection (a status message when nothing is selected)."""
    if not scene.current().selected():
        hou.ui.setStatusMessage("Clone: select pieces or objects first", hou.severityType.Warning)
        return None
    dlg = CloneDialog(parent=hou.qt.mainWindow())
    dlg.setAttribute(QtCore.Qt.WA_DeleteOnClose)
    dlg.show()
    return dlg
