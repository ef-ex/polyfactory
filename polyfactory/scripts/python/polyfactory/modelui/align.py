"""modelUI Align (F2d): 3ds Max's Align Selection, Quick Align and Normal Align for pieces and objects alike
(ideas/modelui.md, F2d Align).

- Align (Alt+Ctrl+A, polyfactory > Align...): click a target piece or object; the dialog aligns every selected item
  on its own (Max: "the same settings apply to all of them") per world axis: the current item's Minimum / Center /
  Pivot Point / Maximum to the target's, plus Align Orientation (local axes) and Match Scale per axis. The preview runs
  outside the undo history; Apply is one undo step; Cancel puts the stored values back exactly.
- Quick Align (Alt+Ctrl+Shift+A): click a target; one item's pivot, or a selection's centre, goes to the target's pivot.
- Normal Align (Alt+Ctrl+N): click a face of the selection, then a face of the target: the selection turns and moves
  so its face lies on the target face, normals opposed; the dialog adds an offset along the normal, a spin about it
  and Flip.

Bounding boxes are tight world boxes of the item's points (not its local box turned into world space). A piece's
pivot is its origin; an object's pivot is its pivot parameter (``p``, in the object's own space). Scale and
Bounding boxes are tight world boxes of the item's points (not its local box turned into world space). A piece's
pivot is its origin; an object's pivot is its pivot parameter (``p``, in the object's own space). Scale and
orientation are read from the item's WORLD matrix (rows of its 3x3 part: lengths = scale, directions = local axes).
A result the parameters cannot hold (shear: an object with a pivot rotation and a non-uniform scale, a piece in a
non-uniformly scaled container) gets the nearest transform and a status warning (``Session.unstored``).
Picking: a click intersects only the object the viewport draws under the cursor (its pick buffer); on the handle's
proxy null, every piece and object whose box the ray passes. The cross cursor shows only over viewers; Esc ends a
pick wherever the keyboard focus is (outside text fields).
Python here is transform maths and UI marshalling (house rule 2, decision log in ideas/modelui.md).
"""
import numpy as np

import hou
from hutil.Qt import QtCore, QtGui, QtWidgets

from polyfactory.modelui import containers, input_layer, pieces_ui, scene

Qt = QtCore.Qt
POINTS = ("min", "center", "pivot", "max")
LABELS = {"min": "Minimum", "center": "Center", "pivot": "Pivot Point", "max": "Maximum"}
XFORM_PARMS = ("t", "r", "s", "shear", "p", "pr", "scale")   # what setWorldTransform may change on an object
GESTURE = "modelui_align_pick"
_state = {"on": False, "pick": None, "dialog": None, "cursor": False,
          "opts": {"pos": {}, "orient": (), "scale": ()}, "normal": (0.0, 0.0, False)}


# --- what an item is made of -----------------------------------------------------------------------------------------
def _np(m):
    return np.array(m.asTupleOfTuples(), dtype=float)


def _pts(geo):
    if geo is None or not geo.intrinsicValue("pointcount"):
        return None
    return np.array(geo.pointFloatAttribValues("P"), dtype=float).reshape(-1, 3)


def items(pids):
    """Every item's world matrix ``m``, its points in its own space ``pts`` (Nx3, None for no geometry or a hidden
    piece) and its pivot in its own space ``piv`` (a piece: its origin; an object: ``p``, which Houdini rotates and
    scales about, probe). A container's transforms and pieces are read once, however many of its pieces are asked for.
    A piece's own space is its packed geometry's (the packed prim's full transform is the piece transform)."""
    cache, out = {}, []
    for pid in pids:
        if not isinstance(pid, tuple):
            n = hou.nodeBySessionId(pid)
            dn = n.displayNode()
            out.append({"pid": pid, "m": n.worldTransform(), "pts": _pts(dn.geometry() if dn is not None else None),
                        "piv": hou.Vector3(n.parmTuple("p").eval())})
            continue
        c, piece = scene.MixedScene._split(pid)
        d = cache.get(c.sessionId())
        if d is None:
            g = c.displayNode().geometry()
            d = cache[c.sessionId()] = (containers.transforms(c), c.worldTransform(),
                                        dict(zip(g.primIntAttribValues("pf_piece"), g.prims())))
        local, cw, prims = d
        if piece not in local:
            raise KeyError("piece %r is gone" % (pid,))
        pr = prims.get(piece)
        out.append({"pid": pid, "m": local[piece] * cw, "pts": _pts(pr.getEmbeddedGeometry()) if pr is not None else None,
                    "piv": hou.Vector3(0, 0, 0)})
    return out


def item(pid):
    return items([pid])[0]


def world_pivot(it, m=None):
    return it["piv"] * (it["m"] if m is None else m)


def world_box(it, m=None):
    """(lo, hi) of the item's points under ``m`` (default its own matrix): the tight world box."""
    m = it["m"] if m is None else m
    if it["pts"] is None:
        p = np.array(tuple(world_pivot(it, m)))
        return p, p
    w = _pts_world(it["pts"], m)
    return w.min(0), w.max(0)


def _pts_world(pts, m):
    a = _np(m)
    return pts @ a[:3, :3] + a[3, :3]


def value(it, which, k, m=None):
    """The item's Minimum / Center / Pivot Point / Maximum on world axis k."""
    if which == "pivot":
        return world_pivot(it, m)[k]
    lo, hi = world_box(it, m)
    return {"min": lo[k], "max": hi[k], "center": 0.5 * (lo[k] + hi[k])}[which]


# --- the maths ---------------------------------------------------------------------------------------------------------
def _lin(m):
    t = m.asTupleOfTuples()
    return hou.Matrix4((t[0][:3] + (0.0,), t[1][:3] + (0.0,), t[2][:3] + (0.0,), (0.0, 0.0, 0.0, 1.0)))


def _row(m, k):
    return hou.Vector3(m.at(k, 0), m.at(k, 1), m.at(k, 2))


def _keep_pivot(lin, m_old, piv):
    """``lin`` (no translation) with the translation that keeps the local pivot where ``m_old`` put it."""
    return lin * hou.hmath.buildTranslate(piv * m_old - piv * lin)


def orient(m, piv, mt, axes):
    """Max's Align Orientation (Local): one axis turns the item the shortest way until that local axis points along
    the target's; two or three axes take the target's orientation. Scale stays, the pivot stays in place."""
    if not axes:
        return m
    rs, rt = hou.Matrix4(m.extractRotationMatrix3()), hou.Matrix4(mt.extractRotationMatrix3())
    if len(axes) >= 2:
        rn = rt
    else:
        k = tuple(axes)[0]
        rn = rs * _row(rs, k).normalized().matrixToRotateTo(_row(rt, k).normalized())
    return _keep_pivot(_lin(m) * rs.inverted() * rn, m, piv)


def match_scale(m, piv, mt, axes):
    """Max's Match Scale: the item's scale on local axis k (world) becomes the target's; the pivot stays in place."""
    if not axes:
        return m
    lin, lt = _lin(m), _lin(mt)
    f = [1.0, 1.0, 1.0]
    for k in axes:
        s = _row(lin, k).length()
        f[k] = _row(lt, k).length() / s if s > 1e-12 else 1.0
    return _keep_pivot(hou.hmath.buildScale(f) * lin, m, piv)


def aligned(it, tgt, opts):
    """The item's new world matrix. ``opts``: {"pos": {axis: (current point, target point)}, "orient": axes,
    "scale": axes}; orientation and scale first (about the pivot), then the position on the item's new box."""
    m = match_scale(orient(it["m"], it["piv"], tgt["m"], opts.get("orient", ())), it["piv"], tgt["m"],
                    opts.get("scale", ()))
    d = [0.0, 0.0, 0.0]
    for k, (cur, tg) in opts.get("pos", {}).items():
        d[k] = value(tgt, tg, k) - value(it, cur, k, m)
    return m * hou.hmath.buildTranslate(d)


def solve(items, tgt, opts):
    """{pid: new world matrix} for every item (each on its own, as Max does)."""
    return {it["pid"]: aligned(it, tgt, opts) for it in items}


def selection_centre(items):
    los, his = zip(*(world_box(it) for it in items))
    return hou.Vector3(tuple(0.5 * (np.min(los, 0) + np.max(his, 0))))


def quick(items, tgt):
    """Quick Align (Max): one item's pivot, or several items' selection centre (their tight box), to the target's
    pivot. Returns {pid: new world matrix}."""
    src = world_pivot(items[0]) if len(items) == 1 else selection_centre(items)
    d = hou.hmath.buildTranslate(world_pivot(tgt) - src)
    return {it["pid"]: it["m"] * d for it in items}


def normal_delta(ps, ns, pt, nt, offset=0.0, angle=0.0, flip=False):
    """World matrix that puts the source face (point ps, normal ns) onto the target face (pt, nt): normals opposed
    (``flip``: the same way), then ``offset`` along the target normal and ``angle`` degrees about it."""
    ns, nt = hou.Vector3(ns).normalized(), hou.Vector3(nt).normalized()
    turn = ns.matrixToRotateTo(nt if flip else -nt)
    spin = hou.hmath.buildRotateAboutAxis(nt, angle)
    return (hou.hmath.buildTranslate(-hou.Vector3(ps)) * turn * spin
            * hou.hmath.buildTranslate(hou.Vector3(pt) + nt * offset))


# --- hits: which item and face is under a ray ------------------------------------------------------------------------
def _pickable(n):
    """A displayed container or loose geometry object (never the handle's proxy null)."""
    if n is None or not n.isDisplayFlagSet() or n.displayNode() is None:
        return False
    return containers.is_intact(n) or (n.type().name() == "geo" and not containers.is_container(n)
                                       and n.userData(pieces_ui.PROXY_MARK) != "1")


def _ray_box(o, d, bb):
    """Does the ray o + t d (t >= 0) pass through box ``bb`` (slab test)?"""
    t0, t1 = 0.0, float("inf")
    for k in range(3):
        lo, hi = bb.minvec()[k], bb.maxvec()[k]
        if abs(d[k]) < 1e-12:
            if o[k] < lo or o[k] > hi:
                return False
            continue
        a, b = (lo - o[k]) / d[k], (hi - o[k]) / d[k]
        t0, t1 = max(t0, min(a, b)), min(t1, max(a, b))
        if t0 > t1:
            return False
    return True


def hit_ray(o, d, nodes=None):
    """(pid, world point, world normal facing the ray's origin) of the nearest piece or object face on the world
    ray o + t d, or None. ``nodes``: the containers and objects to try (default every pickable one, each box-tested
    before its geometry). Pieces: the ray in the container's space hits the packed piece (modelUI's pick does the
    same); objects: their display geometry. ``_state["last_scan"]``: how many geometries were intersected."""
    o, d = hou.Vector3(o), hou.Vector3(d)
    best = None
    scan = 0
    if nodes is None:
        nodes = [n for n in hou.node("/obj").children() if _pickable(n)]
        boxed = True
    else:
        boxed = False
    for n in nodes:
        m = n.worldTransform()
        inv = m.inverted()
        o2 = o * inv
        d2 = ((o + d) * inv - o2).normalized()
        geo = n.displayNode().geometry()
        if boxed and not _ray_box(o2, d2, geo.boundingBox()):
            continue
        scan += 1
        pos, nrm, uvw = hou.Vector3(), hou.Vector3(), hou.Vector3()
        prim = geo.intersect(o2, d2, pos, nrm, uvw)
        if prim < 0:
            continue
        w = pos * m
        dist = (w - o).length()
        if best is not None and dist >= best[0]:
            continue
        pid = n.sessionId()
        if containers.is_container(n):   # the piece's own geometry in its own space: Geometry.intersect turns a packed
            pr = geo.prim(prim)           # prim's face normal like a direction (wrong under a non-uniform piece scale)
            pid = ("piece", n.sessionId(), pr.attribValue("pf_piece"))
            m = pr.fullTransform() * m
            inv = m.inverted()
            o2 = o * inv
            d2 = ((o + d) * inv - o2).normalized()
            if pr.getEmbeddedGeometry().intersect(o2, d2, pos, nrm, uvw) < 0:
                continue
        nw = hou.Vector4(nrm[0], nrm[1], nrm[2], 0.0) * inv.transposed()   # normals: inverse transpose
        nw = hou.Vector3(nw[0], nw[1], nw[2]).normalized()
        if nw.dot(d) > 0:   # the side that was clicked faces the camera
            nw = -nw
        best = (dist, pid, w, nw)
    _state["last_scan"] = scan
    return best[1:] if best is not None else None


def hit_at(vp, x, y):
    """The hit under viewport pixel (x, y): only in the object the viewport draws there (its pick buffer), or, on
    the handle's proxy null, in every piece and object whose box the ray passes."""
    d, o = vp.mapToWorld(x, y)
    n = vp.queryNodeAtPixel(x, y)
    if n is None:
        _state["last_scan"] = 0
        return None
    return hit_ray(o, d, [n] if _pickable(n) else None)


# --- preview, Apply, Cancel -------------------------------------------------------------------------------------------
def _snapshot(pids):
    """The stored values the items' transforms live in: a container's whole piece points, an object's transform
    parameters. Put back by _restore bit for bit."""
    snap = {}
    for pid in pids:
        if isinstance(pid, tuple):
            c, _ = scene.MixedScene._split(pid)
            if ("c", c.sessionId()) not in snap:   # once per container (500 pieces of one container: one copy)
                snap[("c", c.sessionId())] = (c, containers.points(c))
        else:
            n = hou.nodeBySessionId(pid)
            snap[pid] = (n, {k: n.parmTuple(k).eval() for k in XFORM_PARMS if n.parmTuple(k) is not None})
    return snap


def _restore(snap):
    with hou.undos.disabler():
        for key, (node, val) in snap.items():
            try:
                if isinstance(key, tuple):
                    containers.stash(node).parm("stash").set(val)
                else:
                    for k, v in val.items():
                        node.parmTuple(k).set(v)
            except hou.ObjectWasDeleted:
                pass


def commit(xforms, label):
    """{pid: world matrix} as ONE undo step."""
    with hou.undos.group("modelUI: " + label):
        pieces_ui.set_xforms(xforms)


def stored(pids):
    """{pid: the world matrix the scene holds now}; each container is read once."""
    out, cache = {}, {}
    for pid in pids:
        if isinstance(pid, tuple):
            c, piece = scene.MixedScene._split(pid)
            if c.sessionId() not in cache:
                cache[c.sessionId()] = (containers.transforms(c), c.worldTransform())
            local, cw = cache[c.sessionId()]
            out[pid] = local[piece] * cw
        else:
            out[pid] = hou.nodeBySessionId(pid).worldTransform()
    return out


def unstored(xforms, rel=1e-4):
    """The items whose requested world matrix the scene could not hold (an object with a pivot rotation and a
    non-uniform scale, or a piece in a non-uniformly scaled container, would need shear): its parameters got the
    nearest transform instead. ``rel``: per element, relative to 1 + |value| (float32 piece storage is ~1e-7)."""
    have = stored(list(xforms))
    return [p for p, m in xforms.items()
            if any(abs(a - b) > rel * (1.0 + abs(b)) for a, b in zip(have[p].asTuple(), m.asTuple()))]


def _warn_unstored(pids):
    if pids:
        _status("Align: %d item(s) got the nearest transform: the exact result needs shear (a pivot rotation with a "
                "non-uniform scale, or a non-uniformly scaled container), which their parameters cannot hold."
                % len(pids), True)


class Session:
    """A live preview over the selection: ``preview`` moves the items outside the undo history, ``apply`` puts the
    stored values back and commits the last preview as one undo step, ``cancel`` puts the stored values back.
    ``unstored``: the items the last preview or apply could not place exactly (a status warning says so)."""

    def __init__(self, pids, label):
        self.label = label
        self.items = items(pids)
        self.snap = _snapshot(pids)
        self.last = None
        self.done = False
        self.unstored = []

    def preview(self, xforms):
        with hou.undos.disabler():
            pieces_ui.set_xforms(xforms)
        self.last = xforms
        self.unstored = unstored(xforms)
        _warn_unstored(self.unstored)

    def apply(self):
        if self.done:
            return
        self.done = True
        _restore(self.snap)
        if self.last:
            commit(self.last, self.label)
            self.unstored = unstored(self.last)
            _warn_unstored(self.unstored)

    def cancel(self):
        if self.done:
            return
        self.done = True
        _restore(self.snap)


class AlignSession(Session):
    def __init__(self, pids, target):
        super().__init__(pids, "align")
        self.target = item(target)

    def update(self, opts):
        self.preview(solve(self.items, self.target, opts))


class NormalSession(Session):
    def __init__(self, pids, src_hit, tgt_hit):
        super().__init__(pids, "normal align")
        self.src, self.tgt = src_hit, tgt_hit

    def update(self, offset=0.0, angle=0.0, flip=False):
        d = normal_delta(self.src[1], self.src[2], self.tgt[1], self.tgt[2], offset, angle, flip)
        self.preview({it["pid"]: it["m"] * d for it in self.items})


# --- dialogs (Houdini's look: plain Qt widgets under Houdini's main window) ------------------------------------------
class AlignDialog(QtWidgets.QDialog):
    """Max's Align Selection dialog; the current and target points are chosen per axis (one row per axis replaces
    Max's intermediate Apply). Every change previews; Apply keeps it as one undo step; Cancel (Esc, the close box)
    puts everything back."""

    def __init__(self, session, title, opts, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Align Selection (%s)" % title)
        self.setModal(True)
        lay = QtWidgets.QVBoxLayout(self)
        pos = QtWidgets.QGroupBox("Align Position (World)")
        grid = QtWidgets.QGridLayout(pos)
        grid.addWidget(QtWidgets.QLabel("Current Object"), 0, 1)
        grid.addWidget(QtWidgets.QLabel("Target Object"), 0, 2)
        self.pos = []
        for k, a in enumerate("XYZ"):
            cb = QtWidgets.QCheckBox("%s Position" % a)
            cur, tg = QtWidgets.QComboBox(), QtWidgets.QComboBox()
            for w in (cur, tg):
                w.addItems([LABELS[p] for p in POINTS])
                w.setCurrentIndex(POINTS.index("center"))
            have = opts.get("pos", {}).get(k)
            cb.setChecked(have is not None)
            if have:
                cur.setCurrentIndex(POINTS.index(have[0]))
                tg.setCurrentIndex(POINTS.index(have[1]))
            for col, w in enumerate((cb, cur, tg)):
                grid.addWidget(w, k + 1, col)
            self.pos.append((cb, cur, tg))
        lay.addWidget(pos)
        self.orient = self._axes(lay, "Align Orientation (Local)", opts.get("orient", ()))
        self.scale = self._axes(lay, "Match Scale", opts.get("scale", ()))
        bb = QtWidgets.QDialogButtonBox()
        self.apply_button = bb.addButton("Apply", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        self.cancel_button = bb.addButton("Cancel", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        lay.addWidget(bb)
        for cb, cur, tg in self.pos:
            cb.toggled.connect(self.refresh)
            cur.currentIndexChanged.connect(self.refresh)
            tg.currentIndexChanged.connect(self.refresh)
        for cb in self.orient + self.scale:
            cb.toggled.connect(self.refresh)
        self.refresh()

    @staticmethod
    def _axes(lay, title, on):
        box = QtWidgets.QGroupBox(title)
        h = QtWidgets.QHBoxLayout(box)
        out = []
        for k, a in enumerate("XYZ"):
            cb = QtWidgets.QCheckBox("%s Axis" % a)
            cb.setChecked(k in on)
            h.addWidget(cb)
            out.append(cb)
        lay.addWidget(box)
        return out

    def options(self):
        return {"pos": {k: (POINTS[cur.currentIndex()], POINTS[tg.currentIndex()])
                        for k, (cb, cur, tg) in enumerate(self.pos) if cb.isChecked()},
                "orient": tuple(k for k, cb in enumerate(self.orient) if cb.isChecked()),
                "scale": tuple(k for k, cb in enumerate(self.scale) if cb.isChecked())}

    def refresh(self, *_):
        self.session.update(self.options())

    def done(self, r):   # every way out (Apply, Cancel, Esc, the close box) passes here
        if getattr(r, "value", r) == 1:   # QDialog.Accepted (an int or an enum member)
            _state["opts"] = self.options()   # the next Align starts from these (Max remembers them)
            self.session.apply()
        else:
            self.session.cancel()
        _finished()
        super().done(r)


class NormalDialog(QtWidgets.QDialog):
    """Max's Normal Align dialog: offset along the normal, spin about it, Flip; Apply / Cancel as in Align."""

    def __init__(self, session, last, parent=None):
        super().__init__(parent)
        self.session = session
        self.setWindowTitle("Normal Align")
        self.setModal(True)
        form = QtWidgets.QFormLayout(self)
        self.offset = QtWidgets.QDoubleSpinBox()
        self.offset.setRange(-1e6, 1e6)
        self.offset.setDecimals(4)
        self.angle = QtWidgets.QDoubleSpinBox()
        self.angle.setRange(-360.0, 360.0)
        self.angle.setDecimals(2)
        self.flip = QtWidgets.QCheckBox("Flip Normal")
        self.offset.setValue(last[0])
        self.angle.setValue(last[1])
        self.flip.setChecked(last[2])
        form.addRow("Offset", self.offset)
        form.addRow("Angle", self.angle)
        form.addRow(self.flip)
        bb = QtWidgets.QDialogButtonBox()
        self.apply_button = bb.addButton("Apply", QtWidgets.QDialogButtonBox.ButtonRole.AcceptRole)
        self.cancel_button = bb.addButton("Cancel", QtWidgets.QDialogButtonBox.ButtonRole.RejectRole)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        form.addRow(bb)
        self.offset.valueChanged.connect(self.refresh)
        self.angle.valueChanged.connect(self.refresh)
        self.flip.toggled.connect(self.refresh)
        self.refresh()

    def values(self):
        return self.offset.value(), self.angle.value(), self.flip.isChecked()

    def refresh(self, *_):
        self.session.update(*self.values())

    def done(self, r):
        if getattr(r, "value", r) == 1:   # QDialog.Accepted (an int or an enum member)
            _state["normal"] = self.values()
            self.session.apply()
        else:
            self.session.cancel()
        _finished()
        super().done(r)


def _finished():
    _state["dialog"] = None
    input_layer.later(pieces_ui._follow_selection)   # the handle goes where the pieces are now


def _show(dlg):
    _state["dialog"] = dlg
    mw = hou.qt.mainWindow()
    if mw is not None:
        dlg.adjustSize()
        dlg.move(mw.geometry().center() - dlg.rect().center())
    dlg.show()


# --- picking a target or a face: one owned click in a viewer ----------------------------------------------------------
PROMPTS = {"align": "Align: click the target piece or object (Esc or right click cancels)",
           "quick": "Quick Align: click the target piece or object (Esc or right click cancels)",
           "normal_src": "Normal Align: click a face of the selection (Esc or right click cancels)",
           "normal_tgt": "Normal Align: now click a face of the target (Esc or right click cancels)"}


def _status(text, warn=False):
    try:
        hou.ui.setStatusMessage(text, hou.severityType.Warning if warn else hou.severityType.Message)
    except Exception:  # noqa: BLE001 - no UI
        pass


def _gesture(kind, ev, viewer):
    """While picking: a left click in a viewer is ours (Houdini never sees it) and picks at the release; Alt+drag
    (tumble) and the middle button stay Houdini's; a right click or Esc ends the pick."""
    st = _state["pick"]
    if st is None:
        return False
    if kind == "press":
        mods = ev.modifiers() & ~Qt.KeypadModifier
        if viewer is None or mods & Qt.AltModifier:
            return False
        if ev.button() == Qt.RightButton:
            input_layer.later(cancel_pick)
            return True
        if ev.button() != Qt.LeftButton:
            return False
        st["press"] = (viewer, ev.globalPosition().toPoint())
        return True
    if kind == "key":
        if ev.key() == Qt.Key_Escape:
            input_layer.later(cancel_pick)
            return True
        return False
    if kind == "release" and st.get("press") is not None:
        viewer, _ = st.pop("press")
        g = ev.globalPosition().toPoint()
        input_layer.later(lambda: _picked(viewer, g))
    elif kind == "cancel":
        st.pop("press", None)
    return True


def _picked(viewer, g):
    st = _state["pick"]
    if st is None or not _state["on"]:
        return
    vp, x, y, _ = pieces_ui._under(viewer, g)
    h = hit_at(vp, x, y) if vp is not None else None
    st["last_hit"] = h
    if h is None:
        _status(PROMPTS[st["step"]])
        return
    pid = h[0]
    if st["step"] == "normal_src":
        if pid not in st["sel"]:
            _status("Normal Align: that is not in the selection. " + PROMPTS["normal_src"], True)
            return
        st["src"], st["step"] = h, "normal_tgt"
        _status(PROMPTS["normal_tgt"])
        return
    if pid in st["sel"]:
        _status("The target must not be selected. " + PROMPTS[st["step"]], True)
        return
    _end_pick()
    parent = hou.qt.mainWindow()
    if st["kind"] == "align":
        name = scene.current().name(pid)
        _show(AlignDialog(AlignSession(st["sel"], pid), name, _state["opts"], parent))
    elif st["kind"] == "quick":
        commit(quick([item(p) for p in st["sel"]], item(pid)), "quick align")
        _finished()
    else:
        _show(NormalDialog(NormalSession(st["sel"], st["src"], h), _state["normal"], parent))


def _start(kind):
    if not _state["on"]:
        _status("Align works while modelUI is on (polyfactory > modelUI | Houdini).", True)
        return False
    if _state["pick"] is not None or _state["dialog"] is not None:
        return False
    sel = scene.current().selected()
    if not sel:
        _status("Select the pieces or objects to align first.", True)
        return False
    step = "normal_src" if kind == "normal" else kind
    _state["pick"] = {"kind": kind, "step": step, "sel": sel}
    # before modelUI's own click and drag gestures; Esc wherever the keyboard focus is
    input_layer.add_gesture(GESTURE, _gesture, first=True, keys_anywhere=True)
    if _state.get("timer") is None:
        _state["timer"] = QtCore.QTimer(interval=50, timeout=_cursor_tick)
    _state["timer"].start()
    _cursor_tick()
    _status(PROMPTS[step])
    return True


def _cursor_tick(pos=None):
    """Max's pick cursor: the cross while a pick runs and the cursor (``pos``, default where it is) is over a viewer;
    Houdini's own cursor everywhere else."""
    pos = QtGui.QCursor.pos() if pos is None else pos
    over = _state["pick"] is not None and any(sv.qtScreenGeometry().contains(pos) for sv in input_layer._viewers())
    if over and not _state["cursor"]:
        QtWidgets.QApplication.setOverrideCursor(Qt.CrossCursor)
        _state["cursor"] = True
    elif not over and _state["cursor"]:
        QtWidgets.QApplication.restoreOverrideCursor()
        _state["cursor"] = False


def _end_pick():
    _state["pick"] = None
    input_layer.remove_gesture(GESTURE)
    if _state.get("timer") is not None:
        _state["timer"].stop()
    _cursor_tick()


def cancel_pick():
    if _state["pick"] is not None:
        _end_pick()
        _status("")


def align():
    """Align Selection: pick the target, then the dialog."""
    return _start("align")


def quick_align():
    return _start("quick")


def normal_align():
    return _start("normal")


# --- switch feature hooks ---------------------------------------------------------------------------------------------
def install():
    _end_pick()
    _state["on"] = True


def uninstall():
    """Off: a pick ends; an open dialog cancels (everything back as it was)."""
    _state["on"] = False
    _end_pick()
    d = _state["dialog"]
    if d is not None:
        d.reject()
