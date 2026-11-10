"""modelUI modifier stack (F2c): an object's SOP chain as a Max-like stack of real Houdini nodes (ideas/modelui.md).

The stack of a geometry object is its display node and that node's first-input ancestors; ``chain(obj)`` lists them
bottom (base) first, the panel shows them top first. Every edit here is ONE undo step (``hou.undos.group``) and works
on plain Houdini nodes, so the network editor and the stack always show the same thing. Side inputs (a picked object,
a lattice cage) hang off a stack entry's other inputs and are not entries of their own.

A container piece has no nodes: its first modifier promotes it (``containers.promote``) inside the same undo step.
Python here only creates, wires and flags nodes (house rule 2: marshalling); geometry work is the nodes' own.
"""
import hou

from polyfactory.modelui import containers, operations, scene

TOKENS = {hou.geometryType.Points: "points", hou.geometryType.Edges: "edges", hou.geometryType.Primitives: "prims"}
TYPES = {v: k for k, v in TOKENS.items()}


def chain(obj):
    """The object's stack, base first: the display node and its first-input ancestors."""
    out, seen = [], set()
    n = obj.displayNode() if obj is not None else None
    while n is not None and n.sessionId() not in seen:
        seen.add(n.sessionId())
        out.append(n)
        ins = n.inputs()
        n = ins[0] if ins else None
    return out[::-1]


def object_of(pid):
    """The geometry object node of a scene id, or None for a container piece (it has no nodes yet)."""
    return None if isinstance(pid, tuple) else hou.nodeBySessionId(pid)


def _set_top(node):
    node.setDisplayFlag(True)
    node.setRenderFlag(True)


def _ancestors(nodes):
    """Every node feeding ``nodes`` through any input, recursively (``nodes`` included)."""
    seen, todo = {}, list(nodes)
    while todo:
        n = todo.pop()
        if n is None or n.sessionId() in seen:
            continue
        seen[n.sessionId()] = n
        todo.extend(n.inputs())
    return seen


def _destroy_unneeded(obj, doomed):
    """Destroy the nodes of ``doomed`` ({sid: node}) that the display node no longer needs."""
    needed = _ancestors([obj.displayNode()])
    for sid, n in doomed.items():
        if sid not in needed:
            n.destroy()


def _own_object(pid):
    """The object for ``pid``; a container piece is promoted to its own object first (call inside an undo group)."""
    if not isinstance(pid, tuple):
        return hou.nodeBySessionId(pid)
    c, piece = scene.MixedScene._split(pid)
    obj = containers.promote(c, piece)
    scene.current().select([obj.sessionId()])
    return obj


def _apply_group(node, spec, selection):
    """Set group field ``spec`` from ``selection`` = (pattern, hou.geometryType); the selection's type is converted to
    one the field accepts (``types``) or written to its type menu (``type_parm``)."""
    pattern, gtype = selection
    token = TOKENS.get(gtype)
    tp = spec.get("type_parm")
    if tp:
        menu = node.parm(tp).parmTemplate().menuItems()
        if token in menu:
            node.parm(tp).set(token)
        else:
            raise ValueError("%s cannot take a %s selection" % (node.type().name(), gtype))
    elif token not in spec["types"]:
        geo = node.input(0).geometry()
        sel = hou.Selection(geo, gtype, pattern)
        sel.convert(geo, TYPES[spec["types"][0]])   # in place
        pattern = sel.selectionString(geo)
    node.parm(spec["parm"]).set(pattern)


def add(pid, key, above=None, selection=None, mode="model"):
    """Add operation ``key`` to the stack of ``pid`` (an object, or a container piece: promoted first), above stack
    entry ``above`` (default: the top). ``selection`` = (pattern, hou.geometryType) of the component selection on the
    entry the new node reads, or None. One undo step. Returns the new node."""
    op = operations.get(key, mode)
    steps = len(hou.undos.undoLabels())
    try:
        return _add(pid, op, above, selection)
    except Exception:
        if len(hou.undos.undoLabels()) > steps:   # the failed add recorded its step: take it all back
            hou.undos.performUndo()               # (none recorded: an undo here would drop the user's previous action)
        raise


def _add(pid, op, above, selection):
    with hou.undos.group("modelUI: add " + op["label"]):
        obj = _own_object(pid)
        nodes = chain(obj)
        below = above if above is not None else (nodes[-1] if nodes else None)
        n = obj.createNode(op["type"])
        if below is not None:
            n.setFirstInput(below)
            i = [x.sessionId() for x in nodes].index(below.sessionId())
            if i + 1 < len(nodes):
                nodes[i + 1].setInput(0, n)
            else:
                _set_top(n)
        else:
            _set_top(n)
        for parm, v in op.get("defaults", {}).items():
            n.parm(parm).set(v)
        if selection is not None and selection[0] and op.get("groups"):
            _apply_group(n, op["groups"][0], selection)
        if op.get("build"):
            BUILDERS[op["build"]](n)
        n.moveToGoodPosition()
    return n


def lattice_cage(lat):
    """Lattice Deform with its own cage, like Max's FFD: rest lattice = a Bound with divisions around the lattice's
    input, deformed lattice = an Edit of it (the stack shows that Edit's handles for the entry)."""
    obj, src = lat.parent(), lat.input(0)
    bd = obj.createNode("bound", lat.name() + "_rest")
    bd.setFirstInput(src)
    bd.parm("dodivs").set(1)
    ed = obj.createNode("edit", lat.name() + "_cage")
    ed.setFirstInput(bd)
    for a in "xyz":   # the divisions must match (Lattice Deform docs): the lattice follows the bound's
        lat.parm("divs" + a).setExpression('ch("../%s/divs%s")' % (bd.name(), a))
    lat.setInput(1, bd)
    lat.setInput(2, ed)
    for x in (bd, ed):
        x.moveToGoodPosition()


BUILDERS = {"lattice_cage": lattice_cage}


def state_node(node, mode="model"):
    """The node whose viewer state the stack shows for entry ``node`` (the lattice's cage, else the node)."""
    op = operations.for_node(node, mode)
    i = op.get("state") if op else None
    return node.input(i) if i is not None and node.input(i) is not None else node


def move(node, step):
    """Move a stack entry up (+1) or down (-1); the base never moves. One undo step. Returns True if it moved."""
    nodes = chain(node.parent())
    i = [x.sessionId() for x in nodes].index(node.sessionId())
    j = i + step
    if i == 0 or j < 1 or j >= len(nodes):
        return False
    new = list(nodes)
    new[i], new[j] = new[j], new[i]
    with hou.undos.group("modelUI: move modifier"):
        for k in range(1, len(new)):   # bottom up: each node's new input is already wired below it, so no cycle
            new[k].setInput(0, new[k - 1])
            op = operations.for_node(new[k])
            if op and op.get("build") == "lattice_cage" and new[k].input(1) is not None:
                new[k].input(1).setInput(0, new[k - 1])   # the cage's rest Bound follows the lattice's input
        if new[-1].sessionId() != nodes[-1].sessionId():
            _set_top(new[-1])
    return True


def set_enabled(node, on):
    """Modifier on/off = Houdini's bypass flag (the base is always on). One undo step."""
    if chain(node.parent())[0].sessionId() == node.sessionId():
        return False
    with hou.undos.group("modelUI: modifier on" if on else "modelUI: modifier off"):
        node.bypass(not on)
    return True


def delete(node):
    """Delete a stack entry with its side inputs (picked-object merges, a lattice cage) that nothing else needs;
    whatever read it reads the entry below. The base is never deleted. One undo step."""
    obj = node.parent()
    nodes = chain(obj)
    i = [x.sessionId() for x in nodes].index(node.sessionId())
    if i == 0:
        return False
    below = nodes[i - 1]
    with hou.undos.group("modelUI: delete modifier"):
        doomed = _ancestors([node])
        for conn in node.outputConnections():
            conn.outputNode().setInput(conn.inputIndex(), below)
        if i == len(nodes) - 1:
            _set_top(below)
        node.destroy()
        doomed.pop(node.sessionId(), None)
        _destroy_unneeded(obj, doomed)
    return True


def collapse(node=None, obj=None):
    """Collapse the stack up to entry ``node`` (default: the whole stack of ``obj``) into a plain mesh: a Stash SOP
    holding that entry's evaluated geometry replaces it and everything below; entries above stay. One undo step.
    Returns the stash node."""
    obj = node.parent() if node is not None else obj
    nodes = chain(obj)
    node = node or nodes[-1]
    k = [x.sessionId() for x in nodes].index(node.sessionId())
    geo = node.geometry()
    if geo is None or node.errors():
        raise hou.OperationFailed("cannot collapse: %s has an error" % node.path())
    geo = geo.freeze()
    with hou.undos.group("modelUI: collapse"):
        st = obj.createNode("stash", "mesh")
        st.parm("stash").set(geo)
        doomed = _ancestors(nodes[:k + 1])
        for conn in node.outputConnections():
            conn.outputNode().setInput(conn.inputIndex(), st)
        if k == len(nodes) - 1:
            _set_top(st)
        _destroy_unneeded(obj, doomed)
        st.moveToGoodPosition()
    return st


def pick_input(node, index, pid, mode="model"):
    """Wire object (or container piece) ``pid`` into input ``index`` of stack entry ``node`` through an Object Merge
    (into this object's space), replacing what was picked there before. One undo step. Returns the merge node."""
    obj = node.parent()
    op = operations.for_node(node, mode)
    spec = (op or {}).get("inputs", {}).get(index, {})
    if isinstance(pid, tuple):
        src, piece = scene.MixedScene._split(pid)
    else:
        src, piece = hou.nodeBySessionId(pid), None
    if src is None or src.sessionId() == obj.sessionId():
        raise ValueError("pick another object")
    with hou.undos.group("modelUI: pick " + (spec.get("label") or "input %d" % index)):
        old = node.input(index) if index < len(node.inputs()) else None
        om = obj.createNode("object_merge", "pick_" + src.name())
        om.parm("objpath1").set(src.path())
        om.parm("xformtype").set("local")   # into this object's space
        last = om
        if piece is not None:   # one piece of a container: its packed prim, unpacked to plain geometry
            om.parm("group1").set("@pf_piece=%d" % piece)
            last = obj.createNode("unpack", "pick_unpack")
            last.setFirstInput(om)
        node.setInput(index, last)
        for parm, v in spec.get("set", {}).items():
            node.parm(parm).set(v)
        if old is not None:
            _destroy_unneeded(obj, _ancestors([old]))
        for x in (om, last):
            x.moveToGoodPosition()
    return om


def picked(node, index):
    """The object path picked into input ``index`` (through our Object Merge), or None."""
    n = node.input(index) if index < len(node.inputs()) else None
    if n is not None and n.type().name() == "unpack":
        n = n.input(0)
    return n.parm("objpath1").eval() if n is not None and n.type().name() == "object_merge" else None


def use_selection(node, parm, selection, mode="model"):
    """Set group field ``parm`` of ``node`` from ``selection`` = (pattern, hou.geometryType). One undo step."""
    op = operations.for_node(node, mode)
    spec = next((g for g in (op or {}).get("groups", []) if g["parm"] == parm), {"parm": parm, "types": ("prims", "edges", "points")})
    with hou.undos.group("modelUI: use selection"):
        _apply_group(node, spec, selection)
