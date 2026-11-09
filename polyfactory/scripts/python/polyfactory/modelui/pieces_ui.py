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
import math

import hou
from hutil.Qt import QtCore, QtWidgets

from polyfactory.modelui import containers, input_layer, scene

Qt = QtCore.Qt
PROXY_MARK = "pf_modelui_proxy"
CLICK_PX = 3
COPY_PX = 4
_state = {"on": False, "proxy": None, "bound": None, "writing": False, "drawable": None, "click": None, "drag": None,
          "pending": None}   # pending: a released or cancelled body drag whose commit is deferred


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


def set_xforms(xforms):
    """{pid: world matrix}: one stash edit per container, objects one by one."""
    groups = {}
    for pid, m in xforms.items():
        if isinstance(pid, tuple):
            c, piece = scene.MixedScene._split(pid)
            groups.setdefault(c, {})[piece] = m * c.worldTransform().inverted()
        else:
            hou.nodeBySessionId(pid).setWorldTransform(m)
    for c, local in groups.items():
        containers.set_transforms(c, local)


def copy_of(pid):
    if isinstance(pid, tuple):
        c, piece = scene.MixedScene._split(pid)
        return ("piece", c.sessionId(), containers.copy_pieces(c, [piece])[0])
    node = hou.nodeBySessionId(pid)
    return hou.copyNodesTo([node], node.parent())[0].sessionId()


def _world_box(b, m):
    pts = [hou.Vector3(x, y, z) * m for x in (b.minvec()[0], b.maxvec()[0])
           for y in (b.minvec()[1], b.maxvec()[1]) for z in (b.minvec()[2], b.maxvec()[2])]
    return hou.BoundingBox(*[min(v[i] for v in pts) for i in range(3)], *[max(v[i] for v in pts) for i in range(3)])


def bounds(pid):
    """World bounding box of a piece or an object's display geometry, or None."""
    if not isinstance(pid, tuple):
        n = hou.nodeBySessionId(pid)
        dn = n.displayNode() if n is not None else None
        g = dn.geometry() if dn is not None else None
        return _world_box(g.boundingBox(), n.worldTransform()) if g is not None and g.points() else None
    c, piece = scene.MixedScene._split(pid)
    for pr in c.displayNode().geometry().prims():
        if pr.attribValue("pf_piece") == piece:
            b = pr.boundingBox()
            m = c.worldTransform()
            pts = [hou.Vector3(x, y, z) * m for x in (b.minvec()[0], b.maxvec()[0])
                   for y in (b.minvec()[1], b.maxvec()[1]) for z in (b.minvec()[2], b.maxvec()[2])]
            lo = [min(p_[i] for p_ in pts) for i in range(3)]   # from the corners: an empty hou.BoundingBox() would
            hi = [max(p_[i] for p_ in pts) for i in range(3)]   # start as a box at the origin and stretch to it
            return hou.BoundingBox(lo[0], lo[1], lo[2], hi[0], hi[1], hi[2])
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
    _state["last_hit"] = tuple(pos)   # in the container's space
    return ("piece", c.sessionId(), geo.prim(prim).attribValue("pf_piece")) if prim >= 0 else None


def pick(vp, x, y, mode="replace"):
    """Select the piece or object under viewport pixel (x, y): mode "replace" (nothing there: clear), "add" (Shift)
    or "remove" (Ctrl). Returns the id or None."""
    n = vp.queryNodeAtPixel(x, y)
    _state["last_pick"] = (x, y, n.path() if n is not None else None)
    hit = None
    if n is not None and containers.is_container(n):
        hit = _ray_piece(vp, n, x, y)
    elif n is not None and n.type().name() == "geo":
        hit = n.sessionId()
    elif n is not None and n.userData(PROXY_MARK) == "1":   # the handle's own object
        if mode == "replace":
            return _state["bound"]   # a plain click (or a tiny drag) on the handle: the selection stays as it is
        for c in containers.containers():   # with Shift/Ctrl: the piece behind the handle
            hit = _ray_piece(vp, c, x, y) if c.isDisplayFlagSet() else None
            if hit is not None:
                break
    sc = scene.current()
    cur = sc.selected()
    if mode == "add":
        new = cur + [hit] if hit is not None and hit not in cur else cur
    elif mode == "remove":
        new = [p for p in cur if p != hit]
    elif mode == "toggle":
        new = [p for p in cur if p != hit] if hit in cur else (cur + [hit] if hit is not None else cur)
    else:
        new = [hit] if hit is not None else []
    sc.select(new)
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


VIEW_STATES = ("objview", "view")   # Houdini's view tool, also while Space is held: its clicks turn the camera


def _left_alone(ev, viewer):
    """A left press we may take: over a viewer that is not in a view state (Space+LMB turns the camera) and with no
    other button already down (that drag is Houdini's)."""
    return (ev.button() == Qt.LeftButton and viewer is not None and viewer.currentState() not in VIEW_STATES
            and ev.buttons() == Qt.LeftButton)   # (PySide6: ~Qt.LeftButton is RightButton, no mask)


def _click_gesture(kind, ev, viewer):
    """A plain LMB click over a viewer. On a container it is ours: Houdini never sees it (its click on the unselectable
    container counts as a click on empty space and clears the selection, sometimes after our pick, which loses the
    handle), and the piece is picked at the release. Anywhere else (the handle's proxy, a loose object, empty space)
    Houdini keeps the click and we pick after it. Box selections never pick up a container: containers are not
    selectable in the viewport."""
    if kind == "press":
        mods = ev.modifiers() & ~Qt.KeypadModifier
        modes = {Qt.NoModifier: "replace", Qt.ShiftModifier: "add", Qt.ControlModifier: "remove",
                 Qt.ControlModifier | Qt.ShiftModifier: "toggle"}   # Houdini's select keys (basics/select.html)
        if not _left_alone(ev, viewer) or mods not in modes:
            return False
        g = ev.globalPosition().toPoint()
        n = _under(viewer, g)[3]
        _state["click"] = {"viewer": viewer, "start": g, "mode": modes[mods], "box": False, "band": None,
                           "own": n is not None and containers.is_container(n), "empty": n is None}
        return True if _state["click"]["own"] else input_layer.OBSERVE
    st = _state["click"]
    if st is None:
        return False
    if kind == "move":
        d = ev.globalPosition().toPoint() - st["start"]
        if abs(d.x()) + abs(d.y()) > CLICK_PX:
            # a drag from empty space is Houdini's box selection (we add the pieces in it); a drag on the handle or an
            # object is neither a pick nor a box
            st["box"] = st["empty"] or st["own"]   # Q: a drag that starts on a piece is a box selection (ours)
            if not st["box"]:
                _state["click"] = None
            elif st["own"]:
                _band(st, ev.globalPosition().toPoint())
    elif kind == "release":
        _state["click"] = None
        _band_off(st)
        g = ev.globalPosition().toPoint()
        if st["box"]:
            input_layer.later(lambda: _box_at(st["viewer"], st["start"], g, st["mode"], st["own"]))
        else:
            input_layer.later(lambda: _pick_at(st["viewer"], g, st["mode"]))
    elif kind == "cancel":
        _state["click"] = None
        _band_off(st)
    return False


def _band(st, g):
    """The rubber band of a box that Houdini never sees (it started on a piece)."""
    if st["band"] is None:
        top = next((t for t in QtWidgets.QApplication.topLevelWidgets()
                    if t.isVisible() and t.frameGeometry().contains(st["start"])), None)
        gl = top.childAt(top.mapFromGlobal(st["start"])) if top is not None else None
        if gl is None:
            return
        st["band"] = QtWidgets.QRubberBand(QtWidgets.QRubberBand.Shape.Rectangle, gl)
    b = st["band"]
    b.setGeometry(QtCore.QRect(b.parentWidget().mapFromGlobal(st["start"]), b.parentWidget().mapFromGlobal(g)).normalized())
    b.show()


def _band_off(st):
    if st.get("band") is not None:
        st["band"].hide()
        st["band"].deleteLater()
        st["band"] = None


def _pick_at(sv, g, mode="replace"):
    """Pick at global point ``g`` in viewer ``sv``."""
    if not _state["on"]:   # a deferred pick that outlived uninstall
        return
    vp, x, y, _ = _under(sv, g)
    if vp is not None:
        pick(vp, x, y, mode)


def piece_centres(vp):
    """{pid: (x, y) viewport pixel} of every piece's bounding-box centre."""
    out = {}
    for c in containers.containers():
        if not c.isDisplayFlagSet():
            continue
        m = c.worldTransform()
        for pr in c.displayNode().geometry().prims():
            v = vp.mapToScreen(pr.boundingBox().center() * m)
            out[("piece", c.sessionId(), pr.attribValue("pf_piece"))] = (v[0], v[1])
    return out


def _object_centres(vp):
    """{object id: (x, y) viewport pixel} of every displayed loose object's bounding-box centre."""
    out = {}
    for n in hou.node("/obj").children():
        if (n.type().name() == "geo" and not containers.is_container(n) and n.userData(PROXY_MARK) != "1"
                and n.isDisplayFlagSet()):
            b = bounds(n.sessionId())
            if b is not None:
                v = vp.mapToScreen(b.center())
                out[n.sessionId()] = (v[0], v[1])
    return out


def _apply(mode, cur, boxed):
    if mode == "add":
        return cur + [p for p in boxed if p not in cur]
    if mode == "remove":
        return [p for p in cur if p not in boxed]
    if mode == "toggle":
        return [p for p in cur if p not in boxed] + [p for p in boxed if p not in cur]
    return list(boxed)


def _box_at(sv, g0, g1, mode, ours=False):
    """A box selection. Houdini's own (it started on empty space): its object result stands and the pieces whose
    centre is in the box join with the mode. Ours (it started on a piece, Houdini never saw it): objects too, by their
    centres."""
    if not _state["on"]:
        return
    vp, x0, y0, _ = _under(sv, g0)
    vp1, x1, y1, _ = _under(sv, g1)
    if vp is None:
        return
    lo_x, hi_x, lo_y, hi_y = min(x0, x1), max(x0, x1), min(y0, y1), max(y0, y1)
    boxed = [pid for pid, (x, y) in piece_centres(vp).items() if lo_x <= x <= hi_x and lo_y <= y <= hi_y]
    sc = scene.current()
    cur = sc.selected()
    pieces = [p for p in cur if isinstance(p, tuple)]
    objs = [p for p in cur if not isinstance(p, tuple)]
    if ours:
        boxed_objs = [o for o, (x, y) in _object_centres(vp).items() if lo_x <= x <= hi_x and lo_y <= y <= hi_y]
        objs = _apply(mode, objs, boxed_objs)
    sc.select(objs + _apply(mode, pieces, boxed))


# --- the proxy: Houdini's handle on a piece --------------------------------------------------------------------------
# One proxy null per binding: binding another piece destroys the old proxy (outside the undo history) and makes a new
# one. Houdini's undo entries for an old drag then point at a node that is gone, so undoing them restores only that
# piece's own stash entry and can never write into the newly bound piece; the live proxy writes every change (handle
# drags and typed values alike). The null is never saved (removed before a save) and never left behind (install and
# uninstall delete every marked null).
_EVENTS = (hou.nodeEventType.ParmTupleChanged,)


def proxy():
    """The live proxy null of the bound piece, or None."""
    p = _state["proxy"]
    try:
        return p if p is not None and p.path() else None
    except hou.ObjectWasDeleted:
        _state["proxy"] = None
        return None


def _delete_marked(sids=None, tries=50):
    """Every handle null (or only ``sids``). Houdini refuses while it cooks (a timer can fire inside a long cook):
    those are tried again every 100 ms, up to 5 s; the caller goes on (an uninstall must still finish)."""
    busy = []
    with hou.undos.disabler():
        for n in list(hou.node("/obj").children()):
            if n.userData(PROXY_MARK) == "1" and (sids is None or n.sessionId() in sids):
                try:
                    n.destroy()
                except hou.OperationFailed:   # "Cannot delete nodes while cooking"
                    busy.append(n.sessionId())
    _state["proxy"] = None
    if busy and tries:
        QtCore.QTimer.singleShot(100, lambda: _delete_marked(busy, tries - 1))


def _new_proxy(m):
    with hou.undos.disabler():
        n = hou.node("/obj").createNode("null", "modelui_handle")
        n.setUserData(PROXY_MARK, "1")
        if n.parm("controltype") is not None:
            n.parm("controltype").set(0)   # draws nothing itself: Houdini's handle and our box show the piece
        _state["writing"] = True
        try:
            n.setWorldTransform(m)
        finally:
            _state["writing"] = False
        n.addEventCallback(_EVENTS, _proxy_moved)
        n.setSelected(True)   # Houdini's handle moves only this null (probe: rotate_ring_probe.py); the selected
        # pieces and objects follow it by their offsets (_set_rel)
    return n


def _proxy_moved(**kw):
    if not _state["on"]:
        return
    pid = _state["bound"]
    if pid is None or _state["writing"] or kw.get("node") != _state["proxy"]:   # a new wrapper each call: compare, never "is"
        return
    _state["writes"] = _state.get("writes", 0) + 1
    m = kw["node"].worldTransform()
    try:   # every driven item keeps its offset to the null (one piece: identity)
        set_xforms({i: r * m for i, r in _state.get("rel", {}).items()})
    except KeyError:   # a piece is gone
        _state["bound"] = None
    _draw()


def _set_rel(items, p):
    """Every driven item's offset to the null (they follow it)."""
    if p is None or not items:
        _state["rel"] = {}
        return
    inv = p.worldTransform().inverted()
    _state["rel"] = {o: get_xform(o) * inv for o in items}


def _handle_xform(items):
    """Where the handle sits: on one piece its own transform; on a selection the centre of the selection's box (Max),
    so rotate and scale pivot there for pieces and objects alike."""
    if len(items) == 1:
        return get_xform(items[0])
    boxes = [b for b in (bounds(i) for i in items) if b is not None]
    if not boxes:
        return get_xform(items[0])
    lo = [min(b.minvec()[k] for b in boxes) for k in range(3)]
    hi = [max(b.maxvec()[k] for b in boxes) for k in range(3)]
    return hou.hmath.buildTranslate([(lo[k] + hi[k]) / 2.0 for k in range(3)])


def bind(pid, m=None):
    """Bind Houdini's handle to piece ``pid`` (a new proxy at ``m``, default the piece), or unbind with None."""
    old = proxy()
    _state["bound"] = pid
    _state["proxy"] = None
    if old is not None:
        with hou.undos.disabler():
            old.destroy()
    if pid is not None:
        _state["proxy"] = _new_proxy(m if m is not None else get_xform(pid))
    _draw()


def _hip_event(event_type):
    if event_type == hou.hipFileEventType.BeforeSave:
        _state["saved_bound"] = _state["bound"]
        bind(None)   # the null never goes into a hip
        _set_containers_selectable(True)   # nor the unselectable flag: plain Houdini must be able to click them
    elif event_type == hou.hipFileEventType.AfterSave:
        _set_containers_selectable(False)
        if _state.pop("saved_bound", None) is not None:
            input_layer.later(_follow_selection)
    elif event_type in (hou.hipFileEventType.BeforeLoad, hou.hipFileEventType.BeforeClear):
        _state.update(bound=None, proxy=None, click=None, drag=None)
    elif event_type in (hou.hipFileEventType.AfterLoad, hou.hipFileEventType.AfterClear):
        _delete_marked()   # a hip saved by an older version may carry one
        _set_containers_selectable(False)


def _set_containers_selectable(on):
    with hou.undos.disabler():
        for c in containers.containers():
            c.setSelectableInViewport(on)


def _draw():
    """One box per selected piece; ``shown_box`` records the bound piece's box (for tools and checks)."""
    d = _state["drawable"]
    b = bounds(_state["bound"]) if _state["bound"] is not None else None
    if d is None:
        return
    if b is None:
        d.show(False)
        _state["shown_box"] = None
        return
    g = hou.Geometry()
    try:
        boxes = [bounds(p) for p in scene.current().selected()]   # held objects are not highlighted by Houdini
    except hou.Error:
        boxes = [b]
    _state["shown_boxes"] = [x for x in boxes if x is not None] or [b]   # what is drawn (for tools and checks)
    for bb in _state["shown_boxes"]:
        lo, hi = bb.minvec(), bb.maxvec()
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
    if not _state["on"]:   # a deferred follow that outlived uninstall must not create a handle null
        return
    sc = scene.current()
    try:
        sel = sc.selected()
    except hou.Error:
        sel = []
    pieces = [p for p in sel if isinstance(p, tuple)]
    objs = [p for p in sel if not isinstance(p, tuple)]
    items = pieces + objs if pieces else []
    want = pieces[0] if pieces else None
    if QtWidgets.QApplication.mouseButtons() != Qt.NoButton and want == _state["bound"]:
        _draw()   # mid-drag: never move the handle or re-measure offsets (float32 storage would pull it back)
        return
    m = _handle_xform(items) if items else None
    p = proxy()
    if want != _state["bound"] or (want is not None and p is None):
        bind(want, m)
    elif want is not None and p is not None:   # after an undo or an edit elsewhere: the proxy sits on its place again
        if any(abs(a - b) > 1e-5 for a, b in zip(m.asTuple(), p.worldTransform().asTuple())):
            _state["writing"] = True
            try:
                with hou.undos.disabler():
                    p.setWorldTransform(m)
            finally:
                _state["writing"] = False
    _set_rel(items, proxy())
    _draw()


# --- dragging like Max: a piece's or an object's body (move tool), or Shift on it or on the handle = Copy ----------------
# Ours, not Houdini's handle: in perspective views on the ground plane through the grabbed point, in orthographic views
# on the view plane; Ctrl snaps the move to the construction grid. The preview runs outside the undo history; the
# release puts the start state back and commits copy + move as ONE undo step. Plain drags on the handle stay Houdini's.
MOVE_STATES = ("pose",)
MODES = {Qt.NoModifier: "replace", Qt.ShiftModifier: "add", Qt.ControlModifier: "remove",
         Qt.ControlModifier | Qt.ShiftModifier: "toggle"}   # Houdini's select keys (basics/select.html)


def _plane_point(vp, x, y, origin, normal):
    """Where the ray through pixel (x, y) meets the plane, or None: parallel, behind the camera (past the horizon) or
    beyond 20 times the grab distance. A drag then keeps its last valid point."""
    d, o = vp.mapToWorld(x, y)
    d, o = hou.Vector3(d), hou.Vector3(o)
    den = d.dot(normal)
    if abs(den) < 1e-9:
        return None
    t = (origin - o).dot(normal) / den
    if t <= 0 or t * d.length() > 20.0 * (origin - o).length():
        return None
    return o + d * t


def _grid_step(sv, vp=None):
    """Ctrl's step: the cell of the grid the user sees (Houdini's handle Translate Step is not readable from HOM):
    an orthographic view's own grid, else the construction plane when it is shown, else the reference grid."""
    try:
        if vp is not None and vp.type() != hou.geometryViewportType.Perspective:
            return float(vp.settings().orthoGridSpacing()[0]) or 1.0
        cp = sv.constructionPlane()
        if cp.isVisible():
            return float(cp.cellSize()[0]) or 1.0
        return float(sv.referencePlane().cellSize()[0]) or 1.0
    except (AttributeError, TypeError, IndexError, hou.Error):
        return 1.0


XMODES = {"W": "move", "E": "rotate", "R": "scale"}


def _key_gesture(kind, ev, viewer):
    """Remembers the transform mode (W/E/R, Houdini's handle keys) for body drags; never takes a key."""
    if (kind == "key" and viewer is not None and not ev.isAutoRepeat()
            and (ev.modifiers() & ~Qt.KeypadModifier) == Qt.NoModifier and ev.text().upper() in XMODES):
        _state["xmode"] = XMODES[ev.text().upper()]
    return False


def _ray_object(vp, n, x, y):
    """World point where the ray through pixel (x, y) hits object ``n``'s display geometry, or None."""
    dn = n.displayNode()
    if dn is None:
        return None
    d, o = vp.mapToWorld(x, y)
    inv = n.worldTransform().inverted()
    o2 = hou.Vector3(o) * inv
    d2 = (hou.Vector3(o) + hou.Vector3(d)) * inv - o2
    pos, nrm, uvw = hou.Vector3(), hou.Vector3(), hou.Vector3()
    if dn.geometry().intersect(o2, d2.normalized(), pos, nrm, uvw) < 0:
        return None
    return pos * n.worldTransform()


def _drag_gesture(kind, ev, viewer):
    if kind == "press":
        mods = ev.modifiers() & ~Qt.KeypadModifier
        if not _left_alone(ev, viewer) or mods not in MODES:
            return False
        g = ev.globalPosition().toPoint()
        vp, x, y, n = _under(viewer, g)
        if vp is None or n is None:
            return False
        shift = bool(mods & Qt.ShiftModifier)
        moving = viewer.currentState() in MOVE_STATES   # Q: Shift adds by box like Houdini; copy only in W/E/R
        px = proxy()
        if n.userData(PROXY_MARK) == "1" and shift and moving and _state["bound"] is not None and px is not None:
            pid, grab = _state["bound"], px.worldTransform().extractTranslates()   # Shift on the handle
        elif containers.is_container(n) and moving:
            pid = _ray_piece(vp, n, x, y)
            if pid is None:
                return False
            grab = hou.Vector3(_state["last_hit"]) * n.worldTransform()
        elif n.type().name() == "geo" and n.userData(PROXY_MARK) != "1" and moving:
            grab = _ray_object(vp, n, x, y)
            if grab is None:
                return False
            pid = n.sessionId()
        else:
            return False
        view = hou.Vector3(vp.mapToWorld(x, y)[0]).normalized()
        persp = vp.type() == hou.geometryViewportType.Perspective
        normal = hou.Vector3(0, 1, 0) if persp and abs(view[1]) > 0.15 else view
        sel = scene.current().selected()
        items = sel if pid in sel else [pid]   # the whole selection when the grabbed piece is in it
        pivot = _handle_xform(items).extractTranslates()   # E/R turn and scale about the handle's pivot
        _state["drag"] = {"vp": vp, "viewer": viewer, "pid": pid, "items": items,
                          "start": {i: get_xform(i) for i in items}, "grab": grab, "normal": normal, "p0": g,
                          "shift": shift, "mode": MODES[mods], "snap": bool(mods & Qt.ControlModifier),
                          "step": _grid_step(viewer, vp), "moving": None, "copies": None,
                          "xmode": _state.get("xmode", "move"), "pivot": pivot,
                          "axis": (pivot - hou.Vector3(vp.mapToWorld(x, y)[1])).normalized()}
        return True   # ours: Houdini never sees this drag
    st = _state["drag"]
    if st is None:
        return False
    if kind == "move":
        g = ev.globalPosition().toPoint()
        d = g - st["p0"]
        if st["moving"] is None:
            if abs(d.x()) + abs(d.y()) <= COPY_PX:
                return True
            with hou.undos.disabler():   # preview only: the release commits one undo step
                st["moving"] = {i: copy_of(i) for i in st["items"]} if st["shift"] else {i: i for i in st["items"]}
            st["copies"] = list(st["moving"].values()) if st["shift"] else None
        if st["xmode"] in ("rotate", "scale"):   # E: about the view axis through the pivot; R: uniform (Max)
            dx = g.x() - st["p0"].x()
            if st["xmode"] == "rotate":
                k = hou.hmath.buildRotateAboutAxis(st["axis"], -0.5 * dx)
            else:
                f = max(0.01, math.exp(0.01 * dx))
                k = hou.hmath.buildScale(f, f, f)
            dm = hou.hmath.buildTranslate(st["pivot"] * -1.0) * k * hou.hmath.buildTranslate(st["pivot"])
            with hou.undos.disabler():
                set_xforms({st["moving"][i]: st["start"][i] * dm for i in st["items"]})
            return True
        vp, x, y, _ = _under(st["viewer"], g)
        if vp is None:
            return True
        p = _plane_point(vp, x, y, st["grab"], st["normal"])
        if p is not None:
            dv = p - st["grab"]
            if st["snap"]:
                dv = hou.Vector3([round(v / st["step"]) * st["step"] for v in dv])
            dm = hou.hmath.buildTranslate(dv)
            with hou.undos.disabler():
                set_xforms({st["moving"][i]: st["start"][i] * dm for i in st["items"]})
        return True
    if kind in ("release", "cancel"):
        _state["drag"] = None
        if st["moving"] is None:
            if kind == "release":   # a click: pick what was under it, with Houdini's select keys
                input_layer.later(lambda: _pick_at(st["viewer"], st["p0"], st["mode"]))
            return True
        final = {i: get_xform(st["moving"][i]) for i in st["items"]}
        _state["pending"] = st
        input_layer.later(lambda: _commit_drag(st, final, kind == "release"))
        return True
    return True


def _revert_preview(st):
    """The start state back, outside the undo history (the preview never was an undo entry)."""
    with hou.undos.disabler():
        if st["copies"] is not None:
            scene.current().delete(st["copies"])
        else:
            set_xforms(dict(st["start"]))


def _commit_drag(st, final, keep):
    """Undo the preview, then (on a release) copy + move of every dragged item as one undo step; the copies or the
    moved items are selected."""
    if _state["pending"] is not st:   # modelUI went off first: uninstall already put the start state back
        return
    _state["pending"] = None
    _revert_preview(st)
    if not keep:
        return
    with hou.undos.group("modelUI: copy" if st["shift"] else "modelUI: move"):
        targets = {i: (copy_of(i) if st["shift"] else i) for i in st["items"]}
        set_xforms({targets[i]: final[i] for i in st["items"]})
    scene.current().select(list(targets.values()))


# --- switch feature hooks --------------------------------------------------------------------------------------------
def install():
    """Idempotent: a second install replaces the first (one watcher, one drawable)."""
    scene.current().unwatch(_scene_changed)
    try:
        hou.hipFile.removeEventCallback(_hip_event)
    except hou.OperationFailed:
        pass
    if _state["drawable"] is not None:
        _state["drawable"].enable(False)
        _state["drawable"] = None
    _delete_marked()
    _set_containers_selectable(False)
    sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
    if sv is not None:
        _state["drawable"] = hou.SimpleDrawable(sv, hou.Geometry(), "pf_modelui_selection")
        _state["drawable"].setWireframeColor(hou.Color(1.0, 0.8, 0.1))
        _state["drawable"].enable(True)
    input_layer.add_gesture("modelui_mode_keys", _key_gesture)
    input_layer.add_gesture("modelui_drag", _drag_gesture)
    input_layer.add_gesture("modelui_click_pick", _click_gesture)
    scene.current().watch(_scene_changed)
    hou.hipFile.addEventCallback(_hip_event)
    _state["on"] = True


def uninstall():
    _state["on"] = False
    scene.current().unwatch(_scene_changed)
    try:
        hou.hipFile.removeEventCallback(_hip_event)
    except hou.OperationFailed:
        pass
    input_layer.remove_gesture("modelui_click_pick")
    input_layer.remove_gesture("modelui_drag")
    input_layer.remove_gesture("modelui_mode_keys")
    if _state["drawable"] is not None:
        _state["drawable"].show(False)
        _state["drawable"].enable(False)
        _state["drawable"] = None
    st = _state["drag"] or _state["pending"]
    if st is not None and st["moving"] is not None:   # off mid-drag: the preview goes, nothing is committed
        _revert_preview(st)
    _state.update(bound=None, click=None, drag=None, pending=None)
    _delete_marked()
    _set_containers_selectable(True)   # normal Houdini can click them again
