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


def is_intact(node):
    """A container whose storage and output nodes are there (one deleted by hand breaks only that container)."""
    return is_container(node) and node.node("pieces") is not None and node.node("copy") is not None


def containers(root="/obj"):
    """Intact containers (broken ones are skipped, never break the whole scene)."""
    r = hou.node(root)
    return [] if r is None else [n for n in r.children() if is_intact(n)]


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
    st = container.node("pieces")
    if st is None:
        raise RuntimeError("modelUI container %s lost its 'pieces' node" % container.path())
    return st


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


def _by_id(geo):
    """A lookup piece -> point, built in one pass: an edit of many pieces stays linear (``_point`` per piece was
    quadratic: 100 pieces x 30 clones took 18 s, F2b audit)."""
    pts = dict(zip(geo.pointIntAttribValues("pf_piece"), geo.points()))

    def get(piece):
        if piece not in pts:
            raise KeyError("piece %r is not in this container" % piece)
        return pts[piece]
    return get


def _source_packs(container):
    """{file: its Pack node} for the container's intact source chains; broken chains (a node deleted by hand) are
    removed so they get rebuilt."""
    out = {}
    for pk in container.node("sources").inputs():
        if pk is None or pk.parm("pf_source_path") is None:
            continue
        ac = pk.inputs()[0] if pk.inputs() else None
        if ac is None or not ac.inputs() or ac.inputs()[0] is None:
            with hou.undos.disabler():
                if ac is not None:
                    ac.destroy()
                pk.destroy()
            continue
        out[pk.parm("pf_source_path").eval()] = pk
    return out


def _ensure_source(container, path, packs):
    """The source chain for ``path`` (created once per distinct file); ``packs`` from _source_packs, kept current."""
    path = path.replace("\\", "/")
    if path in packs:
        return
    merge = container.node("sources")
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
    packs[path] = pk


def _unique_name(names, name):
    """A name not in ``names`` (a set, built once per edit), added to it."""
    if name in names:
        i = 1
        while "%s_%d" % (name, i) in names:
            i += 1
        name = "%s_%d" % (name, i)
    names.add(name)
    return name


def _names(geo):
    return set(geo.pointStringAttribValues("pf_name"))


def _set_xform(p, m):
    parts = m.explode(transform_order="srt", rotate_order="xyz")
    p.setPosition(parts["translate"])
    p.setAttribValue("orient", tuple(hou.Quaternion(hou.hmath.buildRotate(parts["rotate"]).extractRotationMatrix3())))
    p.setAttribValue("scale", tuple(parts["scale"]))


def transform(container, piece):
    """The piece's transform (scale, then orient, then P: what Copy to Points applies). Limit: a piece stores no shear,
    so a piece rotated inside a container with a non-uniform scale loses the shear that combination makes (keep
    container scales uniform)."""
    p = _point(stash(container).geometry(), piece)
    q = hou.Quaternion(p.attribValue("orient"))
    s = hou.hmath.buildScale(p.attribValue("scale"))
    return s * hou.Matrix4(q.extractRotationMatrix3()) * hou.hmath.buildTranslate(p.position())


def transforms(container):
    """{piece: its transform} for every piece, read in one pass (as ``transform`` per piece)."""
    g = stash(container).geometry()
    ids, P = g.pointIntAttribValues("pf_piece"), g.pointFloatAttribValues("P")
    O, S = g.pointFloatAttribValues("orient"), g.pointFloatAttribValues("scale")
    return {piece: hou.hmath.buildScale(S[3 * i:3 * i + 3])
            * hou.Matrix4(hou.Quaternion(O[4 * i:4 * i + 4]).extractRotationMatrix3())
            * hou.hmath.buildTranslate(P[3 * i:3 * i + 3]) for i, piece in enumerate(ids)}


def add_pieces(container, items):
    """Add pieces in one edit: ``items`` is a list of (source path, name, hou.Matrix4 or None). Returns their ids."""
    with hou.undos.group("modelUI: add pieces"):
        geo = points(container)
        nxt = geo.intAttribValue("pf_next_piece")
        ids = []
        names, packs = _names(geo), _source_packs(container)   # once per call: a bulk add stays linear
        for path, name, m in items:
            _ensure_source(container, path, packs)
            p = geo.createPoint()
            p.setAttribValue("pf_source", path.replace("\\", "/"))
            p.setAttribValue("pf_name", _unique_name(names, name))
            p.setAttribValue("pf_piece", nxt)
            _set_xform(p, m or hou.hmath.identityTransform())
            ids.append(nxt)
            nxt += 1
        geo.setGlobalAttribValue("pf_next_piece", nxt)
        _commit(container, geo, "add pieces")
    return ids


def set_transforms(container, xforms):
    """``xforms``: {piece: hou.Matrix4}, one edit (one pass over the points: linear in the container size)."""
    geo = points(container)
    pt = _by_id(geo)
    for piece, m in xforms.items():
        _set_xform(pt(piece), m)
    _commit(container, geo, "transform")


def copy_pieces(container, pieces, kind=""):
    """Copies of ``pieces`` (same source, transform and visibility, a new unique name). Returns the new ids in order.
    ``kind`` "instance" or "reference" (Clone dialog) records the relation on the new points: ``pf_clone_kind``
    (string) and ``pf_clone_of`` (int, the original's pf_piece; 0 = none). Pieces share their source file anyway; the
    relation is for the modifier stack (F2c): what a modifier on the original does to its instances and references."""
    geo = points(container)
    if kind:
        for n, d in (("pf_clone_kind", ""), ("pf_clone_of", 0)):
            if geo.findPointAttrib(n) is None:   # containers made before the Clone dialog
                geo.addAttrib(hou.attribType.Point, n, d)
    nxt = geo.intAttribValue("pf_next_piece")
    ids = []
    names, pt = _names(geo), _by_id(geo)
    for piece in pieces:
        src = pt(piece)
        p = geo.createPoint()
        p.setPosition(src.position())
        for n in ("orient", "scale", "pf_source", "pf_hidden"):
            p.setAttribValue(n, src.attribValue(n))
        p.setAttribValue("pf_name", _unique_name(names, src.stringAttribValue("pf_name")))
        p.setAttribValue("pf_piece", nxt)
        if kind:
            p.setAttribValue("pf_clone_kind", kind)
            p.setAttribValue("pf_clone_of", piece)
        ids.append(nxt)
        nxt += 1
    geo.setGlobalAttribValue("pf_next_piece", nxt)
    _commit(container, geo, "copy")
    return ids


def delete_pieces(container, pieces):
    geo = points(container)
    pt = _by_id(geo)
    geo.deletePoints([pt(piece) for piece in pieces])
    _commit(container, geo, "delete")


def rename_piece(container, piece, name):
    """Renames a piece (unique within its container). Returns the name it got."""
    geo = points(container)
    p = _point(geo, piece)
    if p.stringAttribValue("pf_name") == name:
        return name
    names = _names(geo)
    names.discard(p.stringAttribValue("pf_name"))
    name = _unique_name(names, name)
    p.setAttribValue("pf_name", name)
    _commit(container, geo, "rename")
    return name


def set_hidden(container, pieces, hide):
    geo = points(container)
    pt = _by_id(geo)
    for piece in pieces:
        pt(piece).setAttribValue("pf_hidden", int(bool(hide)))
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
