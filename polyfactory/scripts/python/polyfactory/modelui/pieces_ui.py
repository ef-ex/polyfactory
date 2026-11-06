"""modelUI pieces in the viewport (F2a): pick container pieces and objects with a click, move/rotate/scale them with
Houdini's own handle, Shift+drag on the handle makes a Copy (ideas/modelui.md).

Why no Python viewer state: handles cannot be bound to node-less states (Houdini docs), and a piece is not a node.
So the handle is Houdini's: a hidden proxy null object is bound to the selected piece (placed at its transform and
node-selected), W/E/R (F1 keys: Houdini's own transform states) show Houdini's handle on it, and every change of the
proxy's transform is written to the piece (one stash edit, inside Houdini's own undo step for the drag).
Picking: an OBSERVE gesture (F1 input layer) sees every plain LMB click over a viewer; a click without a drag picks
the object under it (``queryNodeAtPixel``) and, in a container, the piece hit by a ray through that pixel.
Shift+drag Copy: an OBSERVE gesture stores the bound piece's transform at the press; past 4 px, if the proxy is
really moving (the handle is being dragged), ``later()`` copies the piece, puts the original back and binds the
proxy to the copy, so the handle carries the copy (verified for the pose handle in F1 audit 3).
"""
import hou
from hutil.Qt import QtCore, QtWidgets

from polyfactory.modelui import containers, input_layer, scene

Qt = QtCore.Qt
PROXY_MARK = "pf_modelui_proxy"
CLICK_PX = 3
COPY_PX = 4
_state = {"proxy": None, "bound": None, "writing": False, "drawable": None, "click": None, "clone": None}


# --- pieces and objects alike --------------------------------------------------------------------------------------
def get_xform(pid):
    if isinstance(pid, tuple):
        c, piece = scene.MixedScene._split(pid)
        return containers.transform(c, piece) * c.worldTransform()
    return hou.nodeBySessionId(pid).worldTransform()


def set_xform(pid, m):
    if isinstance(pid, tuple):
        c, piece = scene.MixedScene._split(pid)
        containers.set_transforms(c, {piece: m * c.worldTransform().inverted()})
    else:
        hou.nodeBySessionId(pid).setWorldTransform(m)


def copy_of(pid):
    if isinstance(pid, tuple):
        c, piece = scene.MixedScene._split(pid)
        return ("piece", c.sessionId(), containers.copy_pieces(c, [piece])[0])
    node = hou.nodeBySessionId(pid)
    return hou.copyNodesTo([node], node.parent())[0].sessionId()


def bounds(pid):
    if not isinstance(pid, tuple):
        return None
    c, piece = scene.MixedScene._split(pid)
    for pr in c.displayNode().geometry().prims():
        if pr.attribValue("pf_piece") == piece:
            b = pr.boundingBox()
            out = hou.BoundingBox()
            for x in (b.minvec()[0], b.maxvec()[0]):
                for y in (b.minvec()[1], b.maxvec()[1]):
                    for z in (b.minvec()[2], b.maxvec()[2]):
                        out.enlargeToContain(hou.Vector3(x, y, z) * c.worldTransform())
            return out
    return None


# --- picking ---------------------------------------------------------------------------------------------------------
def viewport_at(sv, gl, gpos):
    """(viewport, x, y): the viewport of ``sv`` under global Qt point ``gpos`` in its own pixels (origin bottom left,
    device pixels), or (None, 0, 0)."""
    dpr = gl.devicePixelRatioF()
    local = gl.mapFromGlobal(gpos)
    px, py = local.x() * dpr, (gl.height() - local.y()) * dpr
    for vp in sv.viewports():
        x0, y0, w, h = vp.size()
        if x0 <= px < x0 + w and y0 <= py < y0 + h:
            return vp, int(px - x0), int(py - y0)
    return None, 0, 0


def _ray_piece(vp, c, x, y):
    d, o = vp.mapToWorld(x, y)
    inv = c.worldTransform().inverted()
    o2 = hou.Vector3(o) * inv
    d2 = (hou.Vector3(o) + hou.Vector3(d)) * inv - o2
    geo = c.displayNode().geometry()
    pos, nrm, uvw = hou.Vector3(), hou.Vector3(), hou.Vector3()
    prim = geo.intersect(o2, d2.normalized(), pos, nrm, uvw)
    _state["last_ray"] = (tuple(o2), tuple(d2.normalized()), prim)   # for diagnosis and checks
    return ("piece", c.sessionId(), geo.prim(prim).attribValue("pf_piece")) if prim >= 0 else None


def pick(vp, x, y):
    """Select the piece or object under viewport pixel (x, y) (nothing: clear). Returns the id or None."""
    n = vp.queryNodeAtPixel(x, y)
    _state["last_pick"] = (x, y, n.path() if n is not None else None)
    hit = None
    if n is not None and containers.is_container(n):
        hit = _ray_piece(vp, n, x, y)
    elif n is not None and n.type().name() == "geo":
        hit = n.sessionId()
    elif n is not None and n.userData(PROXY_MARK) == "1":   # the handle's own object: the piece behind it
        for c in containers.containers():
            hit = _ray_piece(vp, c, x, y) if c.isDisplayFlagSet() else None
            if hit is not None:
                break
        else:
            hit = _state["bound"]
    scene.current().select([hit] if hit is not None else [])
    return hit


def _under(sv, g):
    """(viewport, x, y, object under the point) for global point ``g`` in viewer ``sv``."""
    for top in QtWidgets.QApplication.topLevelWidgets():
        if top.isVisible() and top.frameGeometry().contains(g):
            gl = top.childAt(top.mapFromGlobal(g))
            if gl is not None:
                vp, x, y = viewport_at(sv, gl, g)
                if vp is not None:
                    return vp, x, y, vp.queryNodeAtPixel(x, y)
            break
    return None, 0, 0, None


def _click_gesture(kind, ev, viewer):
    """A plain LMB click over a viewer. On a container it is ours: Houdini never sees it (its click on the unselectable
    container counts as a click on empty space and clears the selection, sometimes after our pick, which loses the
    handle), and the piece is picked at the release. Anywhere else (the handle's proxy, a loose object, empty space)
    Houdini keeps the click and we pick after it. Box selections never pick up a container: containers are not
    selectable in the viewport."""
    if kind == "press":
        mods = ev.modifiers() & ~Qt.KeypadModifier
        if ev.button() != Qt.LeftButton or mods != Qt.NoModifier or viewer is None:   # any modifier: not a plain click
            return False
        g = ev.globalPosition().toPoint()
        n = _under(viewer, g)[3]
        _state["click"] = {"viewer": viewer, "start": g}
        return True if n is not None and containers.is_container(n) else input_layer.OBSERVE
    st = _state["click"]
    if st is None:
        return False
    if kind == "move":
        d = ev.globalPosition().toPoint() - st["start"]
        if abs(d.x()) + abs(d.y()) > CLICK_PX:
            _state["click"] = None   # a drag (handle, box select): not a pick
    elif kind == "release":
        _state["click"] = None
        g = ev.globalPosition().toPoint()
        input_layer.later(lambda: _pick_at(st["viewer"], g))
    elif kind == "cancel":
        _state["click"] = None
    return False


def _pick_at(sv, g):
    """Pick at global point ``g`` in viewer ``sv``."""
    vp, x, y, _ = _under(sv, g)
    if vp is not None:
        pick(vp, x, y)


# --- the proxy: Houdini's handle on a piece --------------------------------------------------------------------------
def proxy():
    p = _state["proxy"]
    if p is not None:
        try:
            p.path()
            return p
        except hou.ObjectWasDeleted:
            pass
    for n in hou.node("/obj").children():
        if n.userData(PROXY_MARK) == "1":
            _state["proxy"] = n
            break
    else:
        with hou.undos.disabler():
            n = hou.node("/obj").createNode("null", "modelui_handle")
            n.setUserData(PROXY_MARK, "1")
            if n.parm("controltype") is not None:
                n.parm("controltype").set(0)   # draws nothing itself: Houdini's handle and our box show the piece
            n.addEventCallback((hou.nodeEventType.ParmTupleChanged,), _proxy_moved)
        _state["proxy"] = n
    return _state["proxy"]


def _proxy_moved(**kw):
    pid = _state["bound"]
    if pid is None or _state["writing"]:
        return
    if QtWidgets.QApplication.mouseButtons() == Qt.NoButton:
        return   # not the handle: an undo/redo put the proxy back (the piece has its own undo entry), never write it
    _state["writes"] = _state.get("writes", 0) + 1
    try:
        set_xform(pid, kw["node"].worldTransform())
    except KeyError:   # the piece is gone
        _state["bound"] = None
    _draw()


def bind(pid):
    """Bind the proxy (and so Houdini's handle) to piece ``pid``, or unbind with None."""
    _state["bound"] = pid
    p = proxy()
    if pid is not None:
        _state["writing"] = True
        try:
            with hou.undos.disabler():   # placing the proxy is not an edit
                p.setWorldTransform(get_xform(pid))
                p.setDisplayFlag(True)   # Houdini's handle needs a displayed object
                p.setSelected(True, clear_all_selected=True)
        finally:
            _state["writing"] = False
    else:
        with hou.undos.disabler():
            p.setSelected(False)
            p.setDisplayFlag(False)   # hidden while unbound: queryNodeAtPixel must reach the pieces
    _draw()


def _draw():
    d = _state["drawable"]
    b = bounds(_state["bound"]) if _state["bound"] is not None else None
    if d is None:
        return
    if b is None:
        d.show(False)
        _state["shown_box"] = None
        return
    g = hou.Geometry()
    lo, hi = b.minvec(), b.maxvec()
    pts = g.createPoints([(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    for i, j in ((0, 1), (2, 3), (4, 5), (6, 7), (0, 2), (1, 3), (4, 6), (5, 7), (0, 4), (1, 5), (2, 6), (3, 7)):
        poly = g.createPolygon(is_closed=False)
        poly.addVertex(pts[i])
        poly.addVertex(pts[j])
    d.setGeometry(g)
    d.show(True)
    _state["shown_box"] = b   # what the highlight shows (for tools and checks)


def _scene_changed():
    input_layer.later(_follow_selection)   # never inside Houdini's callback


def _follow_selection():
    try:
        pieces = [p for p in scene.current().selected() if isinstance(p, tuple)]
    except hou.Error:
        pieces = []
    want = pieces[0] if pieces else None
    if want != _state["bound"]:
        bind(want)
        return
    p = proxy()
    if want is not None:   # after an undo or an edit elsewhere: the proxy sits on its piece again
        m = get_xform(want)
        if any(abs(a - b) > 1e-5 for a, b in zip(m.asTuple(), p.worldTransform().asTuple())):
            _state["writing"] = True
            try:
                with hou.undos.disabler():
                    p.setWorldTransform(m)
            finally:
                _state["writing"] = False
    _draw()


# --- Shift+drag on the handle = Copy ---------------------------------------------------------------------------------
def _copy_gesture(kind, ev, viewer):
    if kind == "press":
        mods = ev.modifiers() & (Qt.ControlModifier | Qt.ShiftModifier | Qt.AltModifier)
        if viewer is None or _state["bound"] is None or ev.button() != Qt.LeftButton or mods != Qt.ShiftModifier:
            return False
        pid = _state["bound"]
        _state["clone"] = {"orig": pid, "xform": get_xform(pid), "start": ev.globalPosition(), "done": False}
        return input_layer.OBSERVE
    st = _state["clone"]
    if st is None:
        return False
    if kind == "move" and not st["done"]:
        d = ev.globalPosition() - st["start"]
        if abs(d.x()) + abs(d.y()) > COPY_PX:
            st["done"] = True
            input_layer.later(_make_copy)
    elif kind in ("release", "cancel"):
        _state["clone"] = None
    return False


def _make_copy():
    st = _state["clone"]
    if st is None or _state["bound"] != st["orig"]:
        return
    moved = get_xform(st["orig"])
    if all(abs(a - b) < 1e-9 for a, b in zip(moved.asTuple(), st["xform"].asTuple())):
        # the handle has not moved the piece (yet): Houdini starts the handle drag a few events after the press.
        # Look again while the Shift drag lasts; a Shift+drag beside the handle never moves it: no copy.
        QtCore.QTimer.singleShot(30, _make_copy)
        return
    new = copy_of(st["orig"])   # runs inside the drag: copy + restore + the rest of the move are one undo step
    set_xform(st["orig"], st["xform"])
    _state["bound"] = new
    scene.current().select([new])


# --- switch feature hooks --------------------------------------------------------------------------------------------
def install():
    """Idempotent: a second install replaces the first (one watcher, one drawable)."""
    scene.current().unwatch(_scene_changed)
    if _state["drawable"] is not None:
        _state["drawable"].enable(False)
        _state["drawable"] = None
    proxy()
    sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    if sv is not None:
        _state["drawable"] = hou.SimpleDrawable(sv, hou.Geometry(), "pf_modelui_selection")
        _state["drawable"].setWireframeColor(hou.Color(1.0, 0.8, 0.1))
        _state["drawable"].enable(True)
    input_layer.add_gesture("modelui_copy_drag", _copy_gesture)
    input_layer.add_gesture("modelui_click_pick", _click_gesture)
    scene.current().watch(_scene_changed)


def uninstall():
    scene.current().unwatch(_scene_changed)
    input_layer.remove_gesture("modelui_click_pick")
    input_layer.remove_gesture("modelui_copy_drag")
    if _state["drawable"] is not None:
        _state["drawable"].show(False)
        _state["drawable"].enable(False)
        _state["drawable"] = None
    p = _state["proxy"]
    _state.update(proxy=None, bound=None, click=None, clone=None)
    if p is not None:
        try:
            with hou.undos.disabler():
                p.destroy()
        except hou.ObjectWasDeleted:
            pass
