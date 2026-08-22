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


# 13.9 N2.  The names, classes and parameters of the PLAN chain, in ONE place -
# `create_pf_polychain_hda.py` builds it from this same function, and
# `asset_plan_matches_the_rig` reads it back off the shipped asset, because
# `native.py` and the build script drifting apart is exactly how two mutations
# survived in cycle N-1V.
PLAN_KEEP = ("* ^pc_curve_id ^pc_curveprim ^pc_sec_* ^pc_curve_len "
             "^pc_start_cap ^pc_end_cap ^pc_corner_angle ^pc_style_key "
             "^pc_trim_* ^pc_mk_* ^pc_attr_* ^pc_yclass ^pc_is_section ^P")


def stage_plan(parent, sections, config, suffix=""):
    """4.2 - sections, then solve / expand / read.  Returns (last, {name: node}).

    ⚠️ `pc_plan_clean` IS NOT TIDYING, IT IS A PRECISION FIX.  A Houdini
    attribute is geometry-wide, so `pc_u` - which 3.1 puts on the MARKER
    CLOUD, in float32, because the artist authored it - already exists on the
    stream when `pc_plan_read` writes 3.4's own `pc_u`.  Writing into an
    existing float32 attribute from a 64-bit wrangle keeps the float32
    storage, and the plan's `u` came back 3e-9 off the reference on exactly
    the two marker cases.  Deleting the spline-side names before the solve
    lets the wrangle create the attribute fresh at 64 bits - and it is also
    what conventions.md asks for, since none of them are the plan's output.
    """
    nodes = {}
    sec = wrangle(parent, "pc_sections" + suffix, "detail", "pc_sections")
    sec.setInput(0, sections)
    sec.setInput(1, config)
    nodes["pc_sections"] = sec

    only = parent.createNode("blast", "pc_sec_only" + suffix)
    only.setInput(0, sec)
    only.parm("group").set("@pc_is_section==1")
    only.parm("grouptype").set(3)
    only.parm("negate").set(True)
    nodes["pc_sec_only"] = only

    clean = parent.createNode("attribdelete", "pc_plan_clean" + suffix)
    clean.setInput(0, only)
    clean.parm("ptdel").set(PLAN_KEEP)
    nodes["pc_plan_clean"] = clean

    solve = wrangle(parent, "pc_plan_solve" + suffix, "point", "pc_plan_solve")
    solve.setInput(0, clean)
    solve.setInput(1, config)
    nodes["pc_plan_solve"] = solve

    gen = parent.createNode("pointgenerate", "pc_plan_expand" + suffix)
    gen.setInput(0, solve)
    # ⚠️ `nptsperpt` MUST BE 1: the attribute MULTIPLIES it, so a default of 10
    # silently plans ten times the fence (13.2 probed this).
    gen.parm("ptsperpt").set(True)
    gen.parm("nptsperpt").set(1)
    gen.parm("doattrib").set(True)
    gen.parm("attrib").set("pc_npieces")
    gen.parm("dopointnum").set(True)
    gen.parm("spointnum").set("pc_secpt")
    gen.parm("dopointidx").set(True)
    gen.parm("spointidx").set("pc_pindex")
    gen.parm("docopyattribs").set(True)
    gen.parm("attribstocopy").set("*")
    nodes["pc_plan_expand"] = gen

    read = wrangle(parent, "pc_plan_read" + suffix, "point", "pc_plan_read")
    read.setInput(0, gen)
    read.setInput(1, config)
    nodes["pc_plan_read"] = read
    return read, nodes


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


# 13.9 N2.  The Python SOP body the ASSET's `config` node runs, minus the parm
# page: the rig has no parms to read, so it is handed the SAME `Params`,
# `Style` and `Kit` the reference was called with and marshals them through
# `hda`'s OWN table writers.  A second copy of the flattening here would be a
# check of nothing (15.8.4's root cause, in a new place).
CONFIG_BODY = """import json
import sys

import hou

sys.path.insert(0, %r)
from polyfactory.polychain import hda as H

geo = hou.pwd().geometry()
geo.clear()
geo.addAttrib(hou.attribType.Global, "pc_cfg", {})
geo.setGlobalAttribValue("pc_cfg", json.loads(%r))
H.write_tables(geo, json.loads(%r))
geo.createPoint()
"""


def config_full(parent, params, style, kit, name="config"):
    """The whole CONFIG stream: `pc_cfg` plus 13.9 N2's kit and rule tables."""
    import json

    from polyfactory.polychain import hda as H

    cfg = {}
    for key in H.CONFIG_KEYS:
        value = getattr(params, key, None)
        if value is None:
            continue
        cfg[key] = float(value) if isinstance(value, bool) else value
    cfg["style_id"] = str(getattr(style, "style_id", "") or "")
    cfg["seed"] = float(getattr(style, "seed", 0) or 0)
    cfg["from_payload"] = 0.0
    tables = H.kit_table(kit)
    tables.update(H.rule_table(style))
    pkg = os.path.normpath(os.path.join(
        os.path.dirname(os.path.abspath(H.__file__)),
        "..", "..")).replace("\\", "/")
    node = parent.createNode("python", name)
    node.parm("python").set(CONFIG_BODY % (pkg, json.dumps(cfg),
                                           json.dumps(tables)))
    return node
