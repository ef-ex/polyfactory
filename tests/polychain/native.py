"""The NATIVE stage chain, built as real SOP nodes, for the parity harness.

    13.9 N1 - "both implementations cook side by side on the same input".

This is the rig, not the asset: it builds the same wrangles the HDA build
script installs, in a throwaway `/obj/geo`, so a stage can be cooked and
compared against `polychain/*.py` on the SAME `hou.Geometry` in ONE process.
Diffing two runs would prove much less (11.9 rule 4).

`create_pf_polychain_hda.py` and this file both call `stage_*` below, so the
network the checks measure IS the network the asset ships.  A stage that only
exists here would be a check of nothing.
"""

import os

import hou

from polyfactory.polychain import vexsrc


def wrangle(parent, name, cls, vfl, precision="64"):
    """One Attribute Wrangle, its VEX inlined from the .vfl of the same name.

    `vex_precision = 64` is the default here on purpose: 11.0 measured a 20 km
    arclength expression returning 0.0 at 32 bits, and a probe this cycle
    measured that a 64-bit wrangle writes a FLOAT64 attribute - so the value
    survives the node boundary too.  A stage that genuinely does not need it
    says so by passing "32".
    """
    node = parent.createNode("attribwrangle", name)
    node.parm("class").set({"detail": 0, "primitive": 1, "point": 2,
                            "vertex": 3}[cls])
    node.parm("snippet").set(vexsrc.source(vfl))
    node.parm("vex_precision").set(precision)
    return node


def stage_decompose(parent, spline, config):
    """4.1 - unshare, arclength, the curve-id table, corners, markers.

    Returns (last node, {name: node}).  Wired, not cooked.

    `pc_unshare` is a NATIVE `splitpoints`, not a wrangle, and it is the first
    node on purpose (D165): `pc_arclength` walks each curve into POINT
    storage, so a junction point shared by two primitives is written twice and
    one curve carries the other's metre.  It is in the RIG as well as in the
    asset because a normalisation the checks skip is a normalisation the
    checks cannot measure.
    """
    nodes = {}
    unshare = parent.createNode("splitpoints", "pc_unshare")
    unshare.setInput(0, spline)
    nodes["pc_unshare"] = unshare
    prev = unshare
    order = (("pc_curveid",     "primitive", "pc_curveid",     None),
             ("pc_curve_index", "detail",    "pc_curve_index", config),
             ("pc_arclength",   "primitive", "pc_arclength",   None),
             ("pc_corners",     "point",     "pc_corners",     config),
             ("pc_markers",     "point",     "pc_markers",     config))
    for name, cls, vfl, second in order:
        node = wrangle(parent, name, cls, vfl)
        node.setInput(0, prev)
        if second is not None:
            node.setInput(1, second)
        nodes[name] = node
        prev = node
    return prev, nodes


# --- the rig ---------------------------------------------------------------

_TMP = []


def feed(parent, geometry, name="IN"):
    """A `file` SOP serving `geometry` - the rig's way of putting a
    `hou.Geometry` the reference already built onto a real node stream.

    A .bgeo round trip rather than a Python SOP on purpose: it is what the
    asset's own input wire looks like to every wrangle downstream, and it
    cannot smuggle a live Python object into a cook.
    """
    import tempfile
    handle, path = tempfile.mkstemp(suffix=".bgeo.sc")
    os.close(handle)
    path = path.replace("\\", "/")
    geometry.saveToFile(path)
    _TMP.append(path)
    node = parent.createNode("file", name)
    node.parm("file").set(path)
    node.parm("filemode").set(0)
    return node


def cleanup():
    for path in _TMP:
        try:
            os.remove(path)
        except OSError:
            pass
    del _TMP[:]


def config_stub(parent, params, name="config"):
    """The CONFIG stream, until 13.3.0's Python SOP exists: one detail point
    carrying `pc_cfg`.  Written from `Params` so the rig cannot drift from the
    parameters the reference was actually run with.
    """
    node = parent.createNode("attribwrangle", name)
    node.parm("class").set(0)
    lines = ["dict c;"]
    for field in ("corner_angle_deg", "min_included_angle_deg"):
        lines.append('c["%s"] = %.17g;' % (field, float(getattr(params, field))))
    lines.append("d@pc_cfg = c;")
    node.parm("snippet").set("\n".join(lines))
    node.parm("vex_precision").set("64")
    return node
