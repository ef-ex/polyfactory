"""modelUI containers: plain kitbash pieces packed together in container geometry objects (ideas/modelui.md, F2a).

A container is a geometry object holding ONE POINT PER PIECE in a Stash SOP (``pieces``): ``P``, ``orient``,
``scale``, ``pf_source`` (file), ``pf_name``, ``pf_piece`` (int, unique in the container), ``pf_hidden``. One chain
per distinct source file (usdimport -> Attribute Create ``pf_source`` -> Pack) feeds one Copy to Points that places
every piece in one cook. Every edit here builds the new point set in Python and sets the stash once: one undo step,
saved in the hip, no per-piece nodes or cooking (Python only marshals the edit: house rule 2).
"""
import re

import hou

MARK = "pf_modelui_container"
_STRING = ("pf_source", "pf_name")


def is_container(node):
    return node is not None and node.userData(MARK) == "1"


def containers(root="/obj"):
    r = hou.node(root)
    return [] if r is None else [n for n in r.children() if is_container(n)]


def create(name="pieces", parent="/obj"):
    """A new empty container object. Returns the object node."""
    with hou.undos.group("modelUI: new container"):
        obj = hou.node(parent).createNode("geo", name)
        obj.setUserData(MARK, "1")
        obj.setSelectableInViewport(False)   # Houdini's own click must never select or drag the whole container:
        # its pieces are picked by modelUI (queryNodeAtPixel still reports it, a ray finds the piece)
        src = obj.createNode("merge", "sources")
        st = obj.createNode("stash", "pieces")
        st.parm("stash").set(_empty())
        vis = obj.createNode("attribwrangle", "visible")
        vis.setFirstInput(st)
        vis.parm("class").set("point")
        vis.parm("snippet").set("if (i@pf_hidden) removepoint(0, @ptnum);")
        cp = obj.createNode("copytopoints::2.0", "copy")
        cp.setInput(0, src)
        cp.setInput(1, vis)
        cp.parm("useidattrib").set(1)
        cp.parm("idattrib").set("pf_source")
        cp.parm("targetattribs").set(1)
        cp.parm("applyto1").set("prims")
        cp.parm("applyattribs1").set("pf_*")
        cp.setDisplayFlag(True)
        cp.setRenderFlag(True)
        obj.layoutChildren()
    return obj


def _empty():
    g = hou.Geometry()
    g.addAttrib(hou.attribType.Point, "orient", (0.0, 0.0, 0.0, 1.0))
    g.addAttrib(hou.attribType.Point, "scale", (1.0, 1.0, 1.0))
    for n in _STRING:
        g.addAttrib(hou.attribType.Point, n, "")
    g.addAttrib(hou.attribType.Point, "pf_piece", 0)
    g.addAttrib(hou.attribType.Point, "pf_hidden", 0)
    g.addAttrib(hou.attribType.Global, "pf_next_piece", 1)
    return g


def stash(container):
    return container.node("pieces")


def points(container):
    """An editable copy of the container's piece points."""
    return stash(container).geometry().freeze()


def _commit(container, geo, label):
    with hou.undos.group("modelUI: " + label):
        stash(container).parm("stash").set(geo)


def _point(geo, piece):
    for p in geo.points():
        if p.intAttribValue("pf_piece") == piece:
            return p
    raise KeyError("piece %r is not in this container" % piece)


def _ensure_source(container, path):
    """The source chain for ``path`` (created once per distinct file)."""
    path = path.replace("\\", "/")
    merge = container.node("sources")
    for node in merge.inputs():
        if node is not None and node.parm("pf_source_path") is not None and node.parm("pf_source_path").eval() == path:
            return
    u = container.createNode("usdimport")
    u.parm("filepath1").set(path)
    u.parm("input_unpack").set(1)
    u.parm("unpack_geomtype").set(1)
    ac = container.createNode("attribcreate::2.0")
    ac.setFirstInput(u)
    ac.parm("name1").set("pf_source")
    ac.parm("class1").set("primitive")
    ac.parm("type1").set("index")   # Attribute Create's "String"
    ac.parm("string1").set(path)    # a parameter, never VEX text (Windows paths became escapes)
    pk = container.createNode("pack")
    pk.setFirstInput(ac)
    pk.parm("transfer_attributes").set("pf_source")
    tg = pk.parmTemplateGroup()
    tg.append(hou.StringParmTemplate("pf_source_path", "pf source path", 1, (path,)))
    pk.setParmTemplateGroup(tg)
    merge.setNextInput(pk)


def _unique_name(geo, name):
    names = {p.stringAttribValue("pf_name") for p in geo.points()}
    if name not in names:
        return name
    i = 1
    while "%s_%d" % (name, i) in names:
        i += 1
    return "%s_%d" % (name, i)


def _set_xform(p, m):
    parts = m.explode(transform_order="srt", rotate_order="xyz")
    p.setPosition(parts["translate"])
    p.setAttribValue("orient", tuple(hou.Quaternion(hou.hmath.buildRotate(parts["rotate"]).extractRotationMatrix3())))
    p.setAttribValue("scale", tuple(parts["scale"]))


def transform(container, piece):
    """The piece's transform (scale, then orient, then P: what Copy to Points applies)."""
    p = _point(stash(container).geometry(), piece)
    q = hou.Quaternion(p.attribValue("orient"))
    s = hou.hmath.buildScale(p.attribValue("scale"))
    return s * hou.Matrix4(q.extractRotationMatrix3()) * hou.hmath.buildTranslate(p.position())


def add_pieces(container, items):
    """Add pieces in one edit: ``items`` is a list of (source path, name, hou.Matrix4 or None). Returns their ids."""
    with hou.undos.group("modelUI: add pieces"):
        geo = points(container)
        nxt = geo.intAttribValue("pf_next_piece")
        ids = []
        for path, name, m in items:
            _ensure_source(container, path)
            p = geo.createPoint()
            p.setAttribValue("pf_source", path.replace("\\", "/"))
            p.setAttribValue("pf_name", _unique_name(geo, name))
            p.setAttribValue("pf_piece", nxt)
            _set_xform(p, m or hou.hmath.identityTransform())
            ids.append(nxt)
            nxt += 1
        geo.setGlobalAttribValue("pf_next_piece", nxt)
        _commit(container, geo, "add pieces")
    return ids


def set_transforms(container, xforms):
    """``xforms``: {piece: hou.Matrix4}, one edit."""
    geo = points(container)
    for piece, m in xforms.items():
        _set_xform(_point(geo, piece), m)
    _commit(container, geo, "transform")


def copy_pieces(container, pieces):
    """Copies of ``pieces`` (same source, transform and visibility, a new unique name). Returns the new ids in order."""
    geo = points(container)
    nxt = geo.intAttribValue("pf_next_piece")
    ids = []
    for piece in pieces:
        src = _point(geo, piece)
        p = geo.createPoint()
        p.setPosition(src.position())
        for n in ("orient", "scale", "pf_source", "pf_hidden"):
            p.setAttribValue(n, src.attribValue(n))
        p.setAttribValue("pf_name", _unique_name(geo, src.stringAttribValue("pf_name")))
        p.setAttribValue("pf_piece", nxt)
        ids.append(nxt)
        nxt += 1
    geo.setGlobalAttribValue("pf_next_piece", nxt)
    _commit(container, geo, "copy")
    return ids


def delete_pieces(container, pieces):
    geo = points(container)
    geo.deletePoints([_point(geo, piece) for piece in pieces])
    _commit(container, geo, "delete")


def rename_piece(container, piece, name):
    """Renames a piece (unique within its container). Returns the name it got."""
    geo = points(container)
    p = _point(geo, piece)
    if p.stringAttribValue("pf_name") == name:
        return name
    name = _unique_name(geo, name)
    p.setAttribValue("pf_name", name)
    _commit(container, geo, "rename")
    return name


def set_hidden(container, pieces, hide):
    geo = points(container)
    for piece in pieces:
        _point(geo, piece).setAttribValue("pf_hidden", int(bool(hide)))
    _commit(container, geo, "hide" if hide else "show")


def piece_rows(container):
    """[(pf_piece, pf_name, hidden)] in point order (one read, no cooking beyond the stash)."""
    g = stash(container).geometry()
    return list(zip(g.pointIntAttribValues("pf_piece"), g.pointStringAttribValues("pf_name"),
                    g.pointIntAttribValues("pf_hidden")))


def promote(container, piece):
    """The piece becomes its own geometry object (its source, world transform and visibility; ready for a stack) and
    leaves the container, in one undo step. Returns the new object."""
    with hou.undos.group("modelUI: promote"):
        geo = points(container)
        p = _point(geo, piece)
        src, name = p.stringAttribValue("pf_source"), p.stringAttribValue("pf_name")
        hidden = p.intAttribValue("pf_hidden")
        m = transform(container, piece) * container.worldTransform()
        obj = container.parent().createNode("geo", re.sub(r"[^A-Za-z0-9_]", "_", name) or "piece")
        u = obj.createNode("usdimport", "source")
        u.parm("filepath1").set(src)
        u.parm("input_unpack").set(1)
        u.parm("unpack_geomtype").set(1)
        u.setDisplayFlag(True)
        u.setRenderFlag(True)
        obj.setWorldTransform(m)
        obj.setDisplayFlag(not hidden)
        geo.deletePoints([p])
        _commit(container, geo, "promote")
    return obj
