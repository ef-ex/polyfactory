"""THE differential comparator - one snapshot, one compare, used everywhere.

    from tests.polychain.diff import snapshot, compare
    bad = compare(snapshot(reference_geo), snapshot(native_geo))

v2 principle 1: *one oracle beats a thousand assertions*.  The Python
reference IS the baseline, so the strongest check is to run both paths and
compare EVERYTHING - and "everything" has to be produced BY CONSTRUCTION, not
by a list somebody maintains.  Every miss in `ideas/build_retrospective.md`
that this file exists to end had the same shape: a comparator that enumerated
what it knew about, and an attribute that was never on the list.

  * `_snapshot` recorded point attributes by NAME only, so `pc_local` could be
    scaled 1.5x or zeroed and parity still printed "identical" (D246).
  * `dataType()` reads `attribData.Float` for fpreal32 AND fpreal64, so a
    precision change moved nothing (D246 again) - STORAGE is part of an
    attribute's contract (conventions.md, D223), so `numericDataType()` is
    read here for every attribute of every class.
  * VERTEX attributes were compared by nothing at all, on either side.
  * A packed prim's CONTENTS were compared by nothing: two builds agreeing on
    18 packed wrappers can carry different geometry inside them, and a gate
    image "showing" 3 388 segments contained 188.

WHAT IT CANNOT SEE (stated, per the discipline, rather than implied):
  * anything that is not reachable from `hou.Geometry` - node warnings and
    cook errors are NOT geometry, so they are passed in by the caller as
    `warnings=` and compared as data.
  * `geometryid` / `memoryusage` intrinsics are session identity, not
    contract, and are excluded by name - two identical builds differ in both.
  * ordering WITHIN a group is compared, but a group's *type* (ordered vs
    unordered) is not exposed by HOM and is not read.
  * packed recursion stops at `packed_depth`; a pack of a pack of a pack is
    compared as a wrapper at depth 0.
"""

import hou

# Session identity, not contract: excluded by name because two byte-identical
# builds disagree on both.
_VOLATILE_INTRINSICS = frozenset(("geometryid", "memoryusage"))

_CLASSES = ("global", "point", "prim", "vertex")


def _attrs(geo, cls):
    return {"global": geo.globalAttribs, "point": geo.pointAttribs,
            "prim": geo.primAttribs, "vertex": geo.vertexAttribs}[cls]()


def _schema(attribs):
    """Name -> the whole DECLARATION: type, storage width, size, array, default.

    `numericDataType()` is the half `dataType()` cannot see, and it is one
    call per attribute.  `qualifier()` separates a plain float3 from a point,
    vector, normal or colour - which is what decides whether a transform is
    applied to it.
    """
    out = {}
    for a in attribs:
        try:
            numeric = str(a.numericDataType())
        except (AttributeError, hou.OperationFailed):
            numeric = "?"
        try:
            default = repr(a.defaultValue())
        except (AttributeError, hou.OperationFailed, TypeError):
            default = "?"
        out[a.name()] = {"type": str(a.dataType()), "storage": numeric,
                         "size": a.size(), "array": bool(a.isArrayType()),
                         "qualifier": str(a.qualifier()), "default": default}
    return out


def _bulk(geo, cls):
    if cls == "point":
        return (geo.pointIntAttribValues, geo.pointFloatAttribValues,
                geo.pointStringAttribValues, geo.pointIntListAttribValues,
                geo.pointFloatListAttribValues, geo.pointStringListAttribValues)
    if cls == "prim":
        return (geo.primIntAttribValues, geo.primFloatAttribValues,
                geo.primStringAttribValues, geo.primIntListAttribValues,
                geo.primFloatListAttribValues, geo.primStringListAttribValues)
    return (geo.vertexIntAttribValues, geo.vertexFloatAttribValues,
            geo.vertexStringAttribValues, geo.vertexIntListAttribValues,
            geo.vertexFloatListAttribValues, geo.vertexStringListAttribValues)


def _values(geo, cls):
    """Every value of every attribute of one class, read in BULK.

    Bulk because a deformed 20 km build carries ~300 000 points and a Python
    loop over them is the check nobody runs.  Floats are kept at FULL
    precision here - rounding is a decision for `compare`, which states the
    tolerance it applies (never round inside the oracle).
    """
    if cls == "global":
        out = {}
        for a in geo.globalAttribs():
            try:
                out[a.name()] = _plain(geo.attribValue(a.name()))
            except (hou.OperationFailed, TypeError):
                out[a.name()] = "<unreadable>"
        return out
    gi, gf, gs, gil, gfl, gsl = _bulk(geo, cls)
    out = {}
    for a in _attrs(geo, cls):
        name, dt = a.name(), a.dataType()
        try:
            if a.isArrayType():
                reader = {hou.attribData.Int: gil, hou.attribData.Float: gfl,
                          hou.attribData.String: gsl}.get(dt)
                out[name] = [_plain(v) for v in reader(name)] if reader \
                    else "<unreadable>"
            elif dt == hou.attribData.String:
                out[name] = list(gs(name))
            elif dt == hou.attribData.Int:
                out[name] = list(gi(name))
            elif dt == hou.attribData.Float:
                out[name] = list(gf(name))
            else:                        # Dict, and anything HOM adds later
                out[name] = _per_element(geo, cls, name)
        except (hou.OperationFailed, TypeError, AttributeError) as exc:
            out[name] = "<unreadable: %s>" % type(exc).__name__
    return out


def _plain(v):
    return list(v) if isinstance(v, (tuple, list)) else v


def _per_element(geo, cls, name):
    src = geo.points() if cls == "point" else geo.prims() if cls == "prim" \
        else [v for p in geo.prims() for v in p.vertices()]
    return [repr(e.attribValue(name)) for e in src]


def _topology(geo):
    """Per prim: type, closed, and its vertices' POINT NUMBERS, in order.

    This is what sees element ORDER and SHARED POINTS - the topology present
    in production and in zero v1 parity fixtures.  A build that renumbers its
    points, reverses a face, or unshares a corner differs here and nowhere
    else.
    """
    rows = []
    for prim in geo.prims():
        closed = None
        try:
            closed = bool(prim.isClosed())
        except (AttributeError, hou.OperationFailed):
            pass
        rows.append([prim.type().name(), closed,
                     [v.point().number() for v in prim.vertices()]])
    return rows


def _groups(geo):
    out = {}
    for cls, getter in (("point", geo.pointGroups), ("prim", geo.primGroups),
                        ("vertex", geo.vertexGroups)):
        out[cls] = dict((g.name(), [e.number() for e in _members(g, cls)])
                        for g in getter())
    out["edge"] = dict(
        (g.name(), sorted((e.points()[0].number(), e.points()[1].number())
                          for e in g.edges()))
        for g in geo.edgeGroups())
    return out


def _members(group, cls):
    if cls == "point":
        return group.points()
    if cls == "prim":
        return group.prims()
    return group.vertices()


def _intrinsics(geo, packed_depth):
    """Every non-volatile intrinsic of every prim, plus the packed CONTENTS."""
    rows, nested = [], []
    for prim in geo.prims():
        vals = {}
        for name in sorted(prim.intrinsicNames()):
            if name in _VOLATILE_INTRINSICS:
                continue
            try:
                vals[name] = _plain(prim.intrinsicValue(name))
            except (hou.OperationFailed, TypeError):
                vals[name] = "<unreadable>"
        rows.append(vals)
        embedded = None
        if packed_depth > 0 and hasattr(prim, "getEmbeddedGeometry"):
            try:
                geo2 = prim.getEmbeddedGeometry()
                if geo2 is not None:
                    embedded = snapshot(geo2, packed_depth=packed_depth - 1)
            except (AttributeError, hou.OperationFailed):
                embedded = None
        nested.append(embedded)
    return rows, nested


def snapshot(geo, packed_depth=1, warnings=()):
    """Everything a consumer of this geometry can see, as plain JSON data.

    Not a digest: a digest says two builds differ and nothing else, and the
    whole point is that a divergence must be NAMEABLE - which attribute, which
    element, which number.
    """
    snap = {
        "counts": dict((k, geo.intrinsicValue(k)) for k in
                       ("pointcount", "primitivecount", "vertexcount",
                        "precision")),
        "attribs": dict((c, _schema(_attrs(geo, c))) for c in _CLASSES),
        "values": dict((c, _values(geo, c)) for c in _CLASSES),
        "topology": _topology(geo),
        "groups": _groups(geo),
        "warnings": sorted(warnings),
    }
    snap["intrinsics"], snap["packed"] = _intrinsics(geo, packed_depth)
    return snap


# --- the comparison ---------------------------------------------------------

class _Report(object):
    """Differences, most structural first, with the float magnitudes kept."""

    def __init__(self, tol, limit):
        self.tol, self.limit = float(tol), int(limit)
        self.rows, self.total, self.worst = [], 0, (0.0, 0.0, "")

    def say(self, fmt, *a):
        self.total += 1
        if len(self.rows) < self.limit:
            self.rows.append(fmt % a if a else fmt)

    def numbers(self, where, u, v):
        """Floats, compared against a STATED tolerance at the real magnitude.

        The skill's rule: never compare after rounding unless the rounding IS
        the contract.  Nothing is rounded here - the deviation is measured and
        the worst one is reported next to the value it sits on, so a "1e-12"
        that is really 0.98 mm at 20 km cannot hide.
        """
        d = abs(float(u) - float(v))
        if d > self.worst[0]:
            self.worst = (d, max(abs(float(u)), abs(float(v))), where)
        if d > self.tol:
            self.say("%s: %r != %r (|d| %.6g)", where, u, v, d)

    def finish(self):
        out = list(self.rows)
        if self.total > len(out):
            out.append("... and %d more difference(s)" % (self.total - len(out)))
        if out and self.worst[0]:
            out.append("worst float |d| %.6g at %s (magnitude %.6g, tol %.6g)"
                       % (self.worst[0], self.worst[2], self.worst[1], self.tol))
        return out


def _seq(rep, where, u, v):
    if isinstance(u, (int, float)) and isinstance(v, (int, float)) \
            and not isinstance(u, bool) and not isinstance(v, bool):
        if isinstance(u, float) or isinstance(v, float):
            rep.numbers(where, u, v)
        elif u != v:
            rep.say("%s: %r != %r", where, u, v)
        return
    if isinstance(u, list) and isinstance(v, list):
        if len(u) != len(v):
            rep.say("%s: length %d != %d", where, len(u), len(v))
            return
        for i, (x, y) in enumerate(zip(u, v)):
            _seq(rep, "%s[%d]" % (where, i), x, y)
        return
    if isinstance(u, dict) and isinstance(v, dict):
        for k in sorted(set(u) | set(v)):
            if k not in u:
                rep.say("%s: %r only on the RIGHT (%r)", where, k, v[k])
            elif k not in v:
                rep.say("%s: %r only on the LEFT (%r)", where, k, u[k])
            else:
                _seq(rep, "%s.%s" % (where, k), u[k], v[k])
        return
    if u != v:
        rep.say("%s: %r != %r", where, u, v)


def compare(a, b, tol=0.0, limit=25):
    """-> [] when the two snapshots are identical, else NAMED differences.

    `tol` is an ABSOLUTE tolerance on every float, and it is printed with the
    worst deviation and that value's magnitude.  Default 0.0: exact, because a
    port that is supposed to answer the same question should answer it
    bit-for-bit until somebody states why it cannot.
    """
    rep = _Report(tol, limit)
    for key in ("counts", "attribs", "values", "topology", "groups",
                "intrinsics", "packed", "warnings"):
        _seq(rep, key, a.get(key), b.get(key))
    return rep.finish()
