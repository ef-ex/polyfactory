"""CityGen - street cross-section templates and profile construction.

Design: ideas/citygen.md (system) and ideas/citygen_streets.md (streets).

Runtime data format is Houdini geometry - points and attributes - never JSON
(citygen.md Contract 8). This module builds that geometry. The starter presets
below are an authoring convenience for getting going; they are not the runtime
format and an artist-authored template geometry replaces them entirely.

Art direction rule (citygen.md section 2): every number here is a DEFAULT.
Anything authored on the element wins over anything computed here.

The profile maths is deliberately free of `hou` so it can be tested outside
Houdini - see test_citygen.py.
"""

# ---------------------------------------------------------------------------
# element defaults.  metres.  (height, drivable, walkable, colour)
# height is the kerb offset above the carriageway surface.
# ---------------------------------------------------------------------------

ELEMENT_DEFAULTS = {
    "lane":     (0.00, 1, 0, (0.22, 0.22, 0.24)),
    "bus":      (0.00, 1, 0, (0.45, 0.16, 0.16)),
    "bike":     (0.00, 1, 0, (0.15, 0.38, 0.20)),
    "parking":  (0.00, 1, 0, (0.28, 0.24, 0.24)),
    "turn":     (0.00, 1, 0, (0.26, 0.26, 0.20)),
    "shoulder": (0.00, 1, 0, (0.30, 0.29, 0.26)),
    "median":   (0.15, 0, 0, (0.30, 0.36, 0.26)),
    "verge":    (0.12, 0, 1, (0.26, 0.40, 0.22)),
    "sidewalk": (0.15, 0, 1, (0.62, 0.61, 0.58)),
}

# anything not in the table still works - it just gets flat grey and no flags
UNKNOWN_ELEMENT = (0.00, 0, 0, (0.50, 0.50, 0.50))

DRIVABLE_TYPES = frozenset(t for t, v in ELEMENT_DEFAULTS.items() if v[1])
WALKABLE_TYPES = frozenset(t for t, v in ELEMENT_DEFAULTS.items() if v[2])


def _e(elem_type, width, **kw):
    d = {"type": elem_type, "width": float(width)}
    d.update(kw)
    return d


# ---------------------------------------------------------------------------
# starter templates.  real-world metric widths.
# ---------------------------------------------------------------------------

STARTER_TEMPLATES = {
    "alley": [
        _e("lane", 3.0),
        _e("lane", 3.0),
    ],
    "local_residential": [
        _e("sidewalk", 2.0),
        _e("parking", 2.2),
        _e("lane", 3.0),
        _e("lane", 3.0),
        _e("parking", 2.2),
        _e("sidewalk", 2.0),
    ],
    "collector": [
        _e("sidewalk", 2.5),
        _e("bike", 1.8),
        _e("lane", 3.25),
        _e("lane", 3.25),
        _e("bike", 1.8),
        _e("sidewalk", 2.5),
    ],
    "arterial_median": [
        _e("sidewalk", 3.0),
        _e("parking", 2.4),
        _e("lane", 3.5),
        _e("lane", 3.5),
        _e("median", 2.0),
        _e("lane", 3.5),
        _e("lane", 3.5),
        _e("parking", 2.4),
        _e("sidewalk", 3.0),
    ],
    "boulevard_bus_bike": [
        _e("sidewalk", 4.0),
        _e("verge", 2.0),
        _e("bike", 2.0),
        _e("bus", 3.5),
        _e("lane", 3.5),
        _e("lane", 3.5),
        _e("median", 3.0),
        _e("lane", 3.5),
        _e("lane", 3.5),
        _e("bus", 3.5),
        _e("bike", 2.0),
        _e("verge", 2.0),
        _e("sidewalk", 4.0),
    ],
    "highway": [
        _e("shoulder", 3.0),
        _e("lane", 3.75),
        _e("lane", 3.75),
        _e("lane", 3.75),
        _e("median", 4.0),
        _e("lane", 3.75),
        _e("lane", 3.75),
        _e("lane", 3.75),
        _e("shoulder", 3.0),
    ],
}


# ---------------------------------------------------------------------------
# pure maths - no hou
# ---------------------------------------------------------------------------

def resolve_elements(elements):
    """Fill defaults into a raw element list. Authored keys always win."""
    out = []
    for i, e in enumerate(elements):
        etype = e["type"]
        d_height, d_drive, d_walk, d_cd = ELEMENT_DEFAULTS.get(etype, UNKNOWN_ELEMENT)
        out.append({
            "type": etype,
            "index": i,
            "width": float(e["width"]),
            "height": float(e.get("height", d_height)),
            "drivable": int(e.get("drivable", d_drive)),
            "walkable": int(e.get("walkable", d_walk)),
            "cd": tuple(e.get("cd", d_cd)),
        })
    return out


def total_width(elements):
    return sum(float(e["width"]) for e in elements)


def street_summary(elements):
    """Summary attributes stamped onto the street edge.

    Names follow CityEngine where they overlap - a naming convention, not a
    dependency (citygen_streets.md section 1).  sidewalk widths are the
    outermost contiguous sidewalk run on each side, which is what an artist
    means by "the pavement", even when a verge sits inboard of it.
    """
    res = resolve_elements(elements)
    if not res:
        return {"streetWidth": 0.0, "sidewalkWidthLeft": 0.0,
                "sidewalkWidthRight": 0.0, "laneWidth": 0.0}

    def leading_run(seq):
        w = 0.0
        for e in seq:
            if e["type"] != "sidewalk":
                break
            w += e["width"]
        return w

    lanes = [e["width"] for e in res if e["type"] == "lane"]
    return {
        "streetWidth": total_width(res),
        "sidewalkWidthLeft": leading_run(res),
        "sidewalkWidthRight": leading_run(reversed(res)),
        "laneWidth": (sum(lanes) / len(lanes)) if lanes else 0.0,
    }


def build_profile_points(elements, offset=0.0):
    """Cross-section profile, left to right, as a list of point dicts.

    Two points per element - its left and right edge at its own height.  Where
    consecutive elements differ in height the shared x with two different y
    values *is* the kerb riser, so kerbs need no special-casing.

    `offset` shifts the whole profile laterally (streetOffset).
    """
    res = resolve_elements(elements)
    w = total_width(res)
    if w <= 0.0:
        return []

    left = -0.5 * w + offset
    x = left
    pts = []
    for e in res:
        for edge_x in (x, x + e["width"]):
            pts.append({
                "x": edge_x,
                "y": e["height"],
                "elem_type": e["type"],
                "elem_index": e["index"],
                "u_cross": (edge_x - left) / w,
                "drivable": e["drivable"],
                "walkable": e["walkable"],
                "cd": e["cd"],
            })
        x += e["width"]
    return pts


def get_template(name):
    """Starter template by name. Raises KeyError with the valid names listed."""
    try:
        return STARTER_TEMPLATES[name]
    except KeyError:
        raise KeyError("unknown template %r - have: %s"
                       % (name, ", ".join(sorted(STARTER_TEMPLATES))))


# ---------------------------------------------------------------------------
# houdini geometry writers.  imported lazily so the module stays testable.
# ---------------------------------------------------------------------------

_PT_ATTRS = (
    ("elem_type", "string", ""),
    ("elem_index", "int", 0),
    ("u_cross", "float", 0.0),
    ("drivable", "int", 0),
    ("walkable", "int", 0),
    ("width", "float", 0.0),
    ("height", "float", 0.0),
)


def _ensure_point_attribs(geo):
    import hou
    for name, kind, default in _PT_ATTRS:
        if geo.findPointAttrib(name) is None:
            geo.addAttrib(hou.attribType.Point, name, default)
    if geo.findPointAttrib("Cd") is None:
        geo.addAttrib(hou.attribType.Point, "Cd", (1.0, 1.0, 1.0))


def template_to_geo(geo, elements):
    """Write the template itself: one point per element, ordered.

    This is the data-stream representation of a cross-section template.
    """
    _ensure_point_attribs(geo)
    res = resolve_elements(elements)
    x = 0.0
    for e in res:
        pt = geo.createPoint()
        # laid out along +x purely so the template is legible in the viewport
        pt.setPosition((x + 0.5 * e["width"], e["height"], 0.0))
        pt.setAttribValue("elem_type", e["type"])
        pt.setAttribValue("elem_index", e["index"])
        pt.setAttribValue("width", e["width"])
        pt.setAttribValue("height", e["height"])
        pt.setAttribValue("drivable", e["drivable"])
        pt.setAttribValue("walkable", e["walkable"])
        pt.setAttribValue("Cd", e["cd"])
        x += e["width"]
    return geo


def geo_to_elements(geo):
    """Read a template geometry back into an element list.

    The inverse of template_to_geo, so artist-authored template geometry and
    the starter presets are interchangeable everywhere downstream.
    """
    if geo.findPointAttrib("elem_type") is None:
        return []
    pts = list(geo.points())
    if geo.findPointAttrib("elem_index") is not None:
        pts.sort(key=lambda p: p.attribValue("elem_index"))
    out = []
    for p in pts:
        e = {"type": p.attribValue("elem_type"),
             "width": p.attribValue("width")}
        if geo.findPointAttrib("height") is not None:
            e["height"] = p.attribValue("height")
        out.append(e)
    return out


def profile_to_geo(geo, elements, offset=0.0):
    """Write the swept cross-section profile as a single open polyline.

    Output lies in the XY plane so a Sweep can use it as a cross-section.
    """
    import hou
    _ensure_point_attribs(geo)
    pts = build_profile_points(elements, offset)
    if not pts:
        return geo
    created = []
    for d in pts:
        pt = geo.createPoint()
        pt.setPosition((d["x"], d["y"], 0.0))
        pt.setAttribValue("elem_type", d["elem_type"])
        pt.setAttribValue("elem_index", d["elem_index"])
        pt.setAttribValue("u_cross", d["u_cross"])
        pt.setAttribValue("drivable", d["drivable"])
        pt.setAttribValue("walkable", d["walkable"])
        pt.setAttribValue("Cd", d["cd"])
        created.append(pt)
    poly = geo.createPolygon(is_closed=False)
    for pt in created:
        poly.addVertex(pt)
    return geo
