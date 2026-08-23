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
             "^pc_start_cap ^pc_end_cap ^pc_corner_angle ^_style_key "
             "^pc_trim_* ^_mk_* ^_attr_* ^pc_yclass ^_is_section ^_sec_* ^P")


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
    only.parm("group").set("@_is_section==1")
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

    # ⚠️ 13.3.2's `pointgenerate` EXPANDER IS GONE, AND A MEASUREMENT IS WHY.
    # It copies the SECTION's attributes onto every point it generates, and
    # the plan is twelve ARRAYS of one element per piece - so one section of
    # N pieces copies 12 x N elements N times.  Measured on the 20 km fence:
    # 2 000 pieces 2.1 s, 10 000 pieces 38.6 s, while the SOLVE itself is
    # linear (0.113 / 0.229 / 0.469 / 0.956 s as the count doubles).  D150's
    # reason for choosing it - `addpoint` from a MULTITHREADED wrangle emits
    # in thread-completion order - is still right and does not apply to a
    # DETAIL wrangle, which has one thread and therefore one order.
    emit = wrangle(parent, "pc_plan_emit" + suffix, "detail", "pc_plan_emit")
    emit.setInput(0, solve)
    emit.setInput(1, config)
    nodes["pc_plan_emit"] = emit

    only = parent.createNode("blast", "pc_plan_only" + suffix)
    only.setInput(0, emit)
    only.parm("group").set("@_is_section==1")
    only.parm("grouptype").set(3)
    nodes["pc_plan_only"] = only

    # ⚠️ 3.4's STAMP IS ITS OWN POINT WRANGLE, and the reason is that
    # `pc_plan_emit` above HAS to be single-threaded (D150's `addpoint`
    # ordering) while `sprintf` + `pc_elem_key`'s per-byte crc32 is the one
    # part of the emit that is embarrassingly parallel. Measured at 10 000
    # pieces: stubbing `pc_elem_key` alone took the plan chain from 0.777 s to
    # 0.596 s. It reads only per-point values the emit already wrote, so the
    # lift has no ordering exposure - and 13.3.6 asks for this node at N7.
    stamp = wrangle(parent, "pc_stamp" + suffix, "point", "pc_stamp")
    stamp.setInput(0, only)
    stamp.setInput(1, config)
    nodes["pc_stamp"] = stamp
    return stamp, nodes


# 13.9 N4.  The PACKED branch, in one declaration for the same reason the plan
# chain is: two independent copies is how two mutations of the shipped asset
# survived every suite in cycle N-1V.
# ⚠️ THE LIST IS THE REFERENCE'S OWN, AND IT USED TO BE THREE NAMES LONGER.
# `pc_deform`, `pc_index` and `pc_scale` were being copied onto the packed
# prims where `place.build` publishes none of them - measured side by side,
# the reference's prims carry pc_corner_cut pc_curve_id pc_deformed pc_elem_id
# pc_elem_key pc_generated pc_module pc_replaced pc_section pc_slot pc_style
# pc_u pc_variant pc_warn_degenerate_frame pc_zmode, and 3.4's contract names
# none of the three either. A native branch that publishes MORE than the
# reference is a contract nobody wrote.
# ⚠️ `pc_section` IS NOT ON THIS LIST AND `_sec_out` IS, AND THAT IS THE
# WHOLE OF A DIVERGENCE NOTHING SAW.  The reference calls one attribute name
# by two meanings - on a PLAN POINT `pc_section` is the artist's section KEY
# (`Placement.as_dict`), on the BUILT PRIM it is the section INDEX as an int
# (`_stamp_values`) - and copying the plan point's value straight through
# published the key, as a float, on every prim.  `pc_plan_emit` writes the
# index as `_sec_out`, this carries it, and `pc_finalize` turns it into
# `pc_section`; `_scrub` deletes the `_*` name before OUT for free.
# `pc_style` joined the list at the same time: 3.4 names it and it was absent.
COPY_ATTRIBS = ("pc_elem_id pc_elem_key pc_module pc_slot _sec_out "
                "pc_u pc_variant pc_curve_id pc_zmode pc_warn_*")

# The body every Python SOP in the asset runs.  ⚠️ IT LIVES HERE, BESIDE THE
# CHAIN, for the reason 15.8.4 gives: `create_pf_polychain_hda.py` imports
# this module for the node declarations, so a second copy of the bodies would
# be a second thing that can drift.  The bootstrap is warn-never-block wiring,
# not logic - a session that already has the package on its path skips it.
BOOTSTRAP = """import os
import sys

import hou

_root = hou.text.expandString("$POLYFACTORY")
if _root:
    _pkg = _root.replace(chr(92), "/").rstrip("/") + "/scripts/python"
    if os.path.isdir(_pkg) and _pkg not in sys.path:
        sys.path.append(_pkg)

from polyfactory.polychain import hda as _hda

_hda.%s(hou.pwd())
"""


def sop_body(func):
    """The Python SOP body that calls `polychain.hda.<func>` on this node."""
    return BOOTSTRAP % func


def stage_place(parent, plan, config, kit, sections, suffix="", kit_code=None):
    """4.4's packed half: the kit's copy id, the module's numbers, the frame,
    and ONE `copytopoints`.  Returns (last, {name: node}).

    `kit_code` is the `kit_starter` Python SOP's body; the rig passes None and
    wires the kit straight in, because a check that already has a kit does not
    need 6's standalone fallback.
    """
    nodes = {}
    src = kit
    if kit_code is not None:
        starter = parent.createNode("python", "kit_starter" + suffix)
        starter.parm("python").set(kit_code)
        starter.setInput(0, kit)
        nodes["kit_starter"] = starter
        src = starter

    kit_id = wrangle(parent, "pc_kit_id" + suffix, "primitive", "pc_kit_id")
    kit_id.setInput(0, src)
    nodes["pc_kit_id"] = kit_id

    # ⚠️ THE KIT IS UNPACKED BEFORE IT IS COPIED.  3.2 / D22 ships one PACKED
    # prim per module and `copytopoints(pack=1)` over a packed source NESTS
    # the packs: exact in world space - the parity was 0.0 with the nesting -
    # and unviewable, because `getEmbeddedGeometry()` then hands back one
    # packed prim instead of polygons.
    unpack = parent.createNode("unpack", "kit_unpack" + suffix)
    unpack.setInput(0, kit_id)
    unpack.parm("transfer_attributes").set("pc_module")
    nodes["kit_unpack"] = unpack

    proto = wrangle(parent, "pc_proto" + suffix, "point", "pc_proto")
    proto.setInput(0, plan)
    proto.setInput(1, config)
    proto.setInput(2, kit_id)
    nodes["pc_proto"] = proto

    # 13.9 N5 - THE DEFORM GATE, and it is the rule PC-G3 rides on. One node
    # decides packed or deformed for every piece in the build; see
    # `pc_deform_gate.vfl` for the reference's own order and for the two steps
    # it declares unanswerable instead of guessing.
    gate = wrangle(parent, "pc_deform_gate" + suffix, "point",
                   "pc_deform_gate")
    gate.setInput(0, proto)
    gate.setInput(1, config)
    gate.setInput(2, sections)
    nodes["pc_deform_gate"] = gate

    frames = wrangle(parent, "pc_frames_native" + suffix, "point", "pc_frames")
    frames.setInput(0, gate)
    frames.setInput(1, config)
    frames.setInput(2, sections)
    nodes["pc_frames_native"] = frames

    valid = parent.createNode("blast", "pc_place_valid" + suffix)
    valid.parm("group").set("@pc_frame_valid==0")
    valid.parm("grouptype").set(3)
    valid.setInput(0, frames)
    nodes["pc_place_valid"] = valid

    # 13.3.4's `blast(packed)`, and until this cycle it did not exist: EVERY
    # piece went to `copytopoints`, including the ones the curvature budget
    # unpacks, so a bending panel shipped as a rigid chord. It was invisible
    # because `place_packed_parity` matches on `pc_elem_id` against the
    # reference's PACKED prims, and a piece the reference deformed simply had
    # no counterpart to disagree with.
    packed = parent.createNode("blast", "pc_packed_only" + suffix)
    packed.parm("group").set("@pc_deformed==1")
    packed.parm("grouptype").set(3)
    packed.setInput(0, valid)
    nodes["pc_packed_only"] = packed

    copy = parent.createNode("copytopoints::2.0", "copy_packed" + suffix)
    copy.setInput(0, unpack)
    copy.setInput(1, packed)
    copy.parm("pack").set(True)
    # `pivot` defaults to CENTROID and this needs ORIGIN: `_packed_transform`
    # maps the module's OWN local space.  Measured in isolation, `centroid`
    # moves the world result by 9.54e-07 m.
    copy.parm("pivot").set("origin")
    # a measured NO-OP with an explicit `transform` present (exactly 0.0);
    # set so the branch does not depend on which one Houdini prefers
    copy.parm("useimplicitn").set(False)
    copy.parm("useidattrib").set(True)
    copy.parm("idattrib").set("pc_module")
    copy.parm("targetattribs").set(1)
    copy.parm("applyto1").set("prims")
    copy.parm("applyattribs1").set(COPY_ATTRIBS)
    nodes["copy_packed"] = copy

    # 13.9 N7's first half - 4.6's stamp, on the prim the copy just made.
    # Everything above this node reproduces the reference's GEOMETRY; this is
    # what makes it reproduce the reference's ELEMENT.  See `pc_finalize.vfl`
    # for why each of the four constants is a statement about this branch and
    # not a placeholder.
    fin = wrangle(parent, "pc_finalize" + suffix, "primitive", "pc_finalize")
    fin.setInput(0, copy)
    fin.setInput(1, config)
    nodes["pc_finalize"] = fin

    # 13.2's named lever, used for the one place it is actually needed.  The
    # whole chain runs at `vex_precision = 64` on purpose (R2), and a 64-bit
    # wrangle writes FLOAT64 STORAGE - so `pc_u` left this branch carrying
    # 0.003703703703703704 where the reference's float32 attribute carries
    # 0.003703703638166189.  Both are the same number; only one of them is
    # what 3.4 ships.  The 64 bits are right for every intermediate and wrong
    # for the output, and `attribcast` is where that line is drawn.
    cast = parent.createNode("attribcast", "pc_out_cast" + suffix)
    cast.setInput(0, fin)
    cast.parm("class1").set("primitive")
    cast.parm("attribs1").set("pc_u")
    cast.parm("precision1").set("fpreal32")
    nodes["pc_out_cast"] = cast
    return cast, nodes


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
