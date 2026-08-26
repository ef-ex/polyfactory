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


# 13.7 rule 3 - `Stage` IS A MENU OVER THE STAGE OUTPUT NULLS, and this tuple
# is the one declaration of it.
#
# (token, the NULL the switch input must be wired to, the node that NULL must
#  be fed by, the menu label).
#
# IT LIVES HERE, NOT IN `create_pf_polychain_hda.py`, AND THAT IS D203.  The
# build script's own comment claimed "the menu, the switch's inputs and the
# HDA-wiring check all read it, so a stage cannot be added to one and not the
# others" - and `grep -rn STAGES tests/` returned one prose mention inside a
# docstring.  No check read it, which is exactly how these three mutations of
# the shipped asset stayed 94 [PASS] / 0:
#   * `stage_switch` input 1 (`reference`) moved onto `OUT_final`, so
#     `output_guard_parity` compared the guarded native output WITH ITSELF
#     over all 92 cases and still printed "identical";
#   * input 0 (`output`) moved onto `OUT_reference` - the exact undo of the
#     cycle - which only `output_runs_the_native_chain_inside_the_envelope`
#     and `mutation_guard_envelope` could see;
#   * input 6 (`frames`) moved onto `OUT_reference`, so the Frames stage
#     showed the Python kernel's finished fence (18 packed prims carrying only
#     `P`) instead of 18 points carrying 33 attributes.
# The THIRD column closes the other half: `OUT_frames` re-pointed from
# `pc_frames_valid` to `pc_frames` - an UNPLUG, which `asset_stages_match_the_rig`'s
# `isBypassed()` scan structurally cannot see - was 94 / 0 too.
# `every_stage_entry_serves_the_node_it_names` reads both columns.
STAGES = (
    ("output", "OUT_final", "guard_envelope",
     "Output - the finished run"),
    ("reference", "OUT_reference", "kernel",
     "R - the Python reference (13.6 - the parity oracle)"),
    # `config` is a Python SOP, not a null with a feeder - the one row whose
    # third column is None, and the check skips the feeder half for it rather
    # than pretending the stage has one.
    ("config", "config", None,
     "0 - Config (the resolved parameters)"),
    ("sections", "OUT_sections", "pc_markers",
     "1 - Decompose (4.1 - arclength, corners, markers)"),
    ("plan", "OUT_plan", "pc_plan_bridge",
     "2 - Plan, via the PYTHON BRIDGE (4.2 - the scaffolding N5 deletes)"),
    ("plan_native", "OUT_plan_native", "pc_stamp",
     "2 - Plan, NATIVE (4.2 - the VEX fitting solve)"),
    ("frames", "OUT_frames", "pc_frames_valid",
     "4 - Frames, via the PYTHON BRIDGE (4.4 - the transform per piece)"),
    # D203 - the frames branch `Stage = output` ACTUALLY USES had no menu
    # entry, while both entries that named the stage showed the dead bridge.
    # 13.7 rule 1 is that an artist can drop a display flag on any stage and
    # see THAT stage's output; asking "what transform did my piece get" and
    # being shown a branch the output does not cook is the rule broken.
    ("frames_native", "OUT_frames_native", "pc_frames_native",
     "4 - Frames, NATIVE (4.4 - the transform Stage = output uses)"),
    ("gate", "OUT_gate", "pc_deform_gate",
     "4 - Deform gate, NATIVE (4.4 - packed or deformed, per piece)"),
    ("place_native", "OUT_place_native", "pc_out_cast",
     "4 - Place, NATIVE (4.4 - packed pieces, no Python)"),
)


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
             "^pc_trim_* ^_mk_* ^_attr_* ^pc_yclass ^_is_section ^_sec_* ^P "
             # 13.9 N8 stage 2 - 4.3 item F's dissolved degenerate vertices
             # and the CURVE's own closed flag, which `pc_plan_emit` stamps
             # with.  ⚠️ THIS LIST IS A DENY-BY-DEFAULT, so a new
             # `pc_sections` output that is not named here is DELETED before
             # the solve ever sees it - silently, and with the whole warning
             # simply absent from the build (measured, before this line).
             "^_degen_s ^_curve_closed")


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
# ⚠️ `pc_deformed` IS IN THIS LIST SINCE 13.9 N5 AND IT USED TO BE A
# CONSTANT IN `pc_finalize`.  Both branches feed that node now, so the
# flag has to ride across from the plan point the gate wrote it on - a
# constant 0 would stamp every DEFORMED prim against the reference's 1.
#
# ⚠️ AND `_pkey0` IS NOT IN THIS LIST, WHICH IS A `copytopoints` FACT WORTH
# WRITING DOWN.  A target attribute named in TWO `targetattribs` entries is
# applied by the LAST one ONLY - measured on 22.0.398: with entry 1 = prims
# and entry 2 = points both naming `_pkey0`, the copies came out with the
# point attribute and NO prim attribute at all, silently, and every prim key
# read 0.  So the piece index crosses on the POINT alone and `pc_finalize`
# reads it off the prim's own first point.
COPY_ATTRIBS = ("pc_elem_id pc_elem_key pc_module pc_slot _sec_out "
                "pc_u pc_variant pc_curve_id pc_zmode pc_warn_* _warns "
                "pc_deformed")

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


def stage_place(parent, plan, config, kit, sections, suffix="", kit_code=None,
                surface=None):
    """4.4's packed half: the kit's copy id, the module's numbers, the frame,
    and ONE `copytopoints`.  Returns (last, {name: node}).

    `kit_code` is the `kit_starter` Python SOP's body; the rig passes None and
    wires the kit straight in, because a check that already has a kit does not
    need 6's standalone fallback.

    `surface` is 13.9 N6's IN_SURFACE, on the fourth input of the three stages
    that SAMPLE the path.  `None` leaves those ports unwired, which every
    sampler call reads as "no surface" and answers with `pc_sample` itself - so
    a caller that has no terrain gets the identical graph it got before N6.
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

    # 13.9 N5 - the deformed branch's own copy source, and it is a SEPARATE
    # branch off `kit_unpack` rather than an edit of it: `copy_packed` copies
    # its source with `pack = 1`, so a `_srcpt` written on `kit_unpack` would
    # be baked INSIDE every packed prim's embedded geometry, where `_scrub`
    # cannot reach it.
    kit_rank = wrangle(parent, "pc_kit_rank" + suffix, "detail", "pc_kit_rank")
    kit_rank.setInput(0, unpack)
    nodes["pc_kit_rank"] = kit_rank

    # ...and the per-module STATION table, on the packed prim the plan
    # resolves against.  D71: the stations are where 4.4's deform rebuilds a
    # frame and where D25's `_bend_deviation` measures the sag between, so
    # both read one table.
    kit_meta = wrangle(parent, "pc_kit_meta" + suffix, "detail", "pc_kit_meta")
    kit_meta.setInput(0, kit_id)
    kit_meta.setInput(1, kit_rank)
    nodes["pc_kit_meta"] = kit_meta

    proto = wrangle(parent, "pc_proto" + suffix, "point", "pc_proto")
    proto.setInput(0, plan)
    proto.setInput(1, config)
    proto.setInput(2, kit_meta)
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
    # ⚠️ INPUT 3 WAS `pc_kit_meta` UNTIL 13.9 N6.  A wrangle has four inputs and
    # this node used all four, so the station table travels on the PLAN POINT
    # now (`pc_proto` writes it off the kit it already holds) and the port is
    # free for the surface.  Without the move the conform port stalls on wiring.
    gate.setInput(3, surface)
    nodes["pc_deform_gate"] = gate

    frames = wrangle(parent, "pc_frames_native" + suffix, "point", "pc_frames")
    frames.setInput(0, gate)
    frames.setInput(1, config)
    frames.setInput(2, sections)
    frames.setInput(3, surface)
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
    copy.parm("targetattribs").set(2)
    copy.parm("applyto1").set("prims")
    copy.parm("applyattribs1").set(COPY_ATTRIBS)
    # the piece index, on the POINT as well, because `pc_piece_key` needs it
    # on both classes and a packed prim's single point carries nothing else.
    copy.parm("applyto2").set("points")
    copy.parm("applyattribs2").set("_pkey0")
    nodes["copy_packed"] = copy

    # --- 13.9 N5, THE DEFORMED BRANCH -------------------------------------
    #
    # The complement of `pc_packed_only`, built the way `place.build` builds
    # it: the module's own polygons, every point re-read at its own arc
    # position.  Until this landed ONE bending panel in a ten-thousand-piece
    # run sent the whole build to the reference - measured on the citygen
    # shape (300 gently hilly streets, 9 000 pieces, 8 999 deformed) at
    # 1 237 ms of Python, 98.7 % of the cook.
    deformed = parent.createNode("blast", "pc_deformed_only" + suffix)
    deformed.parm("group").set("@pc_deformed==0")
    deformed.parm("grouptype").set(3)
    deformed.setInput(0, valid)
    nodes["pc_deformed_only"] = deformed

    prep = wrangle(parent, "pc_deform_prep" + suffix, "point",
                   "pc_deform_prep")
    prep.setInput(0, deformed)
    prep.setInput(1, sections)
    prep.setInput(2, surface)
    nodes["pc_deform_prep"] = prep

    copy_def = parent.createNode("copytopoints::2.0", "copy_deformed" + suffix)
    copy_def.setInput(0, kit_rank)
    copy_def.setInput(1, prep)
    # ⚠️ `pack = 0` AND `transform = 0` - the module has to arrive in its OWN
    # local space, because `pc_deform` rewrites every position from scratch
    # exactly as `_deform_positions` does.  `pc_deform_prep` zeroes the
    # target's `P` and its 3x3 as well: probed on 22.0.398, `transform = 0`
    # still TRANSLATES a copy to its target point.
    copy_def.parm("pack").set(False)
    copy_def.parm("transform").set(False)
    copy_def.parm("useimplicitn").set(False)
    copy_def.parm("useidattrib").set(True)
    copy_def.parm("idattrib").set("pc_module")
    copy_def.parm("targetattribs").set(2)
    copy_def.parm("applyto1").set("prims")
    copy_def.parm("applyattribs1").set(COPY_ATTRIBS)
    copy_def.parm("applyto2").set("points")
    copy_def.parm("applyattribs2").set("_pkey0 _d*")
    nodes["copy_deformed"] = copy_def

    deform = wrangle(parent, "pc_deform" + suffix, "point", "pc_deform")
    deform.setInput(0, copy_def)
    deform.setInput(1, config)
    deform.setInput(2, sections)
    deform.setInput(3, surface)
    nodes["pc_deform"] = deform

    merge = parent.createNode("merge", "pc_pieces" + suffix)
    merge.setInput(0, copy)
    merge.setInput(1, deform)
    nodes["pc_pieces"] = merge

    # ⚠️ AND THE ALL-PACKED BUILD MUST NOT SEE THE DEFORMED BRANCH AT ALL.
    # An EMPTY `copy_deformed` still carries its source's attribute
    # DEFINITIONS, so merging it into a run with nothing to deform would
    # publish `pc_local` - and any `uv`/`N`/`Cd` an artist's kit carries - as
    # point attributes on a fence where the reference has none, which
    # `output_guard_parity` reads as a differing point attribute LIST on all
    # 92 cases.  A switch is the cheapest correct answer; its selector reads
    # `pc_deformed_only`, which this branch cooks anyway.
    built = parent.createNode("switch", "pc_built" + suffix)
    built.setInput(0, copy)
    built.setInput(1, merge)
    built.parm("input").setExpression(
        'npoints("../%s") > 0' % deformed.name())
    nodes["pc_built"] = built

    # 13.9 N7's first half - 4.6's stamp, on the prim the copy just made.
    # Everything above this node reproduces the reference's GEOMETRY; this is
    # what makes it reproduce the reference's ELEMENT.  See `pc_finalize.vfl`
    # for why each of the four constants is a statement about this branch and
    # not a placeholder.
    fin = wrangle(parent, "pc_finalize" + suffix, "primitive", "pc_finalize")
    fin.setInput(0, built)
    fin.setInput(1, config)
    nodes["pc_finalize"] = fin

    # 13.9 N5 - the two streams put back into `place.build`'s own job order.
    # `pc_finalize` writes the PRIM half of the key, this the POINT half, and
    # one `sort` applies both.  See `PC_PIECE_SPAN` in pc_path.h.
    key = wrangle(parent, "pc_piece_key" + suffix, "point", "pc_piece_key")
    key.setInput(0, fin)
    nodes["pc_piece_key"] = key

    order = parent.createNode("sort", "pc_order" + suffix)
    order.setInput(0, key)
    order.parm("primsort").set("attribute")
    order.parm("primattrib").set("_pkey")
    order.parm("ptsort").set("attribute")
    order.parm("pointattrib").set("_pkeyp")
    nodes["pc_order"] = order

    # 13.2's named lever, used for the one place it is actually needed.  The
    # whole chain runs at `vex_precision = 64` on purpose (R2), and a 64-bit
    # wrangle writes FLOAT64 STORAGE - so `pc_u` left this branch carrying
    # 0.003703703703703704 where the reference's float32 attribute carries
    # 0.003703703638166189.  Both are the same number; only one of them is
    # what 3.4 ships.  The 64 bits are right for every intermediate and wrong
    # for the output, and `attribcast` is where that line is drawn.
    cast = parent.createNode("attribcast", "pc_out_cast" + suffix)
    cast.parm("class1").set("primitive")
    cast.parm("attribs1").set("pc_u")
    cast.parm("precision1").set("fpreal32")
    # 13.9 N5 - and the deformed branch's own 64-bit leak.  `pc_local` is a
    # float32 point attribute in `place.build` (`addAttrib` with a 3-float
    # default) and `pc_deform` is a 64-bit wrangle, so without this line the
    # shipped fence carries the module's local frame at twice the reference's
    # storage.  It is the same line `pc_u` needed, for the same reason.
    cast.parm("numcasts").set(3)
    cast.parm("class2").set("point")
    cast.parm("attribs2").set("pc_local")
    cast.parm("precision2").set("fpreal32")
    # ⚠️ D262 - AND EVERY INT OF 3.4's STAMP, FOR EXACTLY THE SAME REASON,
    # WHICH NOTHING COULD SEE UNTIL D246.  A 64-bit wrangle writes `i@` at
    # int64; `place.build` declares the same attributes with
    # `geo.addAttrib(Prim, name, 0)`, which is int32.  So the shipped fence
    # carried SIX prim ints plus every `pc_warn_*` at twice the reference's
    # storage on every admitted build, and `_snapshot`'s types dimension read
    # `hou.Attrib.dataType()`, which is `attribData.Int` for both - so
    # `output_guard_parity` printed "identical" over all 92 cases.  Measured
    # the moment `numericDataType()` went into the snapshot: 29 of 93 cases
    # differ, on `pc_elem_key`, `pc_section`, `pc_corner_cut`, `pc_deformed`,
    # `pc_generated`, `pc_replaced` and `pc_warn_*`.
    #
    # The list is EXPLICIT rather than `pc_*`: `attribcast` would happily
    # convert `pc_u` - a float - to an integer, so a pattern that is wider
    # than the int columns is a data-loss bug wearing a tidiness costume.
    # `pc_row` and `pc_clipped` are `ELEM_2D_ATTRS`, declared only on a 2D
    # build, and a pattern that names an absent attribute is a no-op.
    cast.parm("class3").set("primitive")
    cast.parm("attribs3").set("pc_elem_key pc_section pc_generated "
                              "pc_deformed pc_corner_cut pc_replaced "
                              "pc_row pc_clipped pc_warn_*")
    cast.parm("precision3").set("int32")
    nodes["pc_out_cast"] = cast

    # 4.6's warning summary, and the per-element fan-out that goes with it.
    # A DETAIL wrangle because `setprimattrib` with a name that comes from
    # DATA creates the attribute at runtime and the creation order in a
    # multithreaded wrangle is thread order - D150's objection, in a new place.
    #
    # ⚠️ AND IT RAISES D88's UNREAD-MARKER WARNING, which is why it has three
    # inputs rather than one.  The warning was in `pc_sections` and that node
    # cooks on the L1-admit / L2-refuse class too, beside `kernel`'s own copy
    # of the same sentence; this node's cookCount is `kernel`'s exact
    # complement, so the artist reads it once.  See `pc_warn_collate.vfl`.
    warn = wrangle(parent, "pc_warn_collate" + suffix, "detail",
                   "pc_warn_collate")
    warn.setInput(0, order)
    warn.setInput(1, config)
    warn.setInput(2, sections)
    nodes["pc_warn_collate"] = warn
    # ⚠️ D262 - THE CAST IS THE LAST NODE OF THE STAGE, NOT THE SECOND
    # TO LAST, AND THE ORDER IS THE POINT.  `pc_warn_collate` CREATES prim
    # attributes at cook time (`setprimattrib` with a name that comes from
    # data), and a 64-bit wrangle creates them at int64 - so with the cast
    # upstream of it, `pc_warn_bend_resolution` shipped at twice the
    # reference's storage on every deformed build while every other int of
    # 3.4's stamp was correctly 32.  Casting AFTER the last node that can
    # create an attribute is the only placement that cannot be outgrown by
    # the next warning somebody adds.
    cast.setInput(0, warn)
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
