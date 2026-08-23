"""Create `pf_polychain` - polyChain's artist-facing SOP HDA (spec 5 + 13).

    hython devScripts/create_pf_polychain_hda.py

⚠️ THIS SCRIPT USED TO BUILD TWO NODES.  It now builds a NETWORK, and that is
the whole point of the exercise.  What was here before was:

    pf_polychain
      |- kernel   [python]      <- ~6 000 lines; the ENTIRE tool
      |- OUT      [null]

which violates the project's own law - `artist_ui.md` 6 rule 10, "the graph
stays reachable - unlocked HDAs, macros as the middle tier", and 1c's finding
that artists learn a tool by opening it and toggling nodes off to see what
each one does.  A tool whose entire body is one Python SOP cannot be learned
that way and cannot be steered by anyone who did not write it.

Hannes' rule, verbatim: *"everything geometry related should be either native
nodes, vex or opencl.  Python can be used for ui or processing data which is
not possible to process with the other 3 mentioned options."*

So the body is being rebuilt as named, visible, DISPLAYABLE stages, 13.9's
build order at a time.  What this script builds today:

    pf_polychain                          36 nodes: 12 VEX (all at 64),
      IN_SPLINE IN_KIT IN_STYLE IN_SURFACE      9 native SOPs, 11 nulls,
      [0 CONFIG]     config     [python]        4 Python SOPs
      [1 DECOMPOSE]  pc_unshare pc_curveid pc_curve_index pc_arclength
                     pc_corners pc_markers OUT_sections   VEX + native (N3)
      [2 PLAN]       pc_plan_bridge OUT_plan    [python] SCAFFOLDING (N5)
                     pc_sections pc_sec_only pc_plan_clean pc_plan_solve
                     pc_plan_emit pc_plan_only OUT_plan_native      4.2 (N2)
      [4 PLACE]      pc_frames pc_frames_valid OUT_frames
                     kit_starter pc_kit_id kit_unpack pc_proto
                     pc_frames_native pc_place_valid copy_packed
                     OUT_place_native            the PACKED branch (N4)
      [R REFERENCE]  kernel OUT_reference       [python]  <- the shipped path
      stage_switch -> OUT

⚠️ `Stage` DEFAULTS TO `output`, WHICH IS `kernel`, AND THAT IS DELIBERATE
(D180).  4.3, 4.5 and 4.6 are still the reference, so a native output would
be a fence with no corner assemblies, no conform and no overrides.  The
native stages are reachable as `Stage = plan_native` and `place_native`, at
the parity `tests/polychain/run_native_checks.py` measures.

The VEX bodies are real files under `polyfactory/vex/polychain/*.vfl`, INLINED
here at build time (`polychain.vexsrc`) so the shipped asset needs no
`HOUDINI_VEX_PATH` - hython does not set one, which is a recorded trap.

Every stage begins and ends in a NAMED NULL so an artist can drop a display
flag on any of them (13.7 rule 1), every wrangle carries a one-sentence
comment displayed in the network (rule 2), and one parm was added - `Stage`
(D155) - which is the artist-visible form of "toggle nodes off to see what
each does".

THE PARAMETER PAGE IS artist_ui.md 6 APPLIED, AND IT IS LAW HERE:
  * two disclosure levels, no more - one main page and one Advanced folder;
  * every parm carries a range, a unit in its label and a help string;
  * every parm names a DECISION an art director could say out loud;
  * the defaults build a good fence on the starter kit with nothing wired but
    a curve (6's standalone-usability floor);
  * `display` is on the MAIN page, because an interactive proxy LOD is an
    acceptance criterion and not polish (artist_ui rule 7).

Internal parm names match `polychain.Params` field names on purpose (D80) -
the label is the artist's face, the name is the kernel's.
"""

import os
import sys

import hou

POLYFACTORY = os.environ.get("POLYFACTORY",
                             "F:/projects/polyfactory/polyfactory")
# hython does not load the package (recorded trap), and this script now READS
# the .vfl sources through `polychain.vexsrc` instead of carrying VEX inline.
_PKG = os.path.join(POLYFACTORY, "scripts", "python").replace("\\", "/")
if os.path.isdir(_PKG) and _PKG not in sys.path:
    sys.path.insert(0, _PKG)
HDA_PATH = os.path.join(POLYFACTORY, "otls",
                        "pf_polychain.hda").replace("\\", "/")

# ⚠️ ONE DECLARATION OF THE PLAN CHAIN, NOT TWO.  15.8.4's root cause was that
# `tests/polychain/native.py` and this script were two independent
# declarations of the DECOMPOSE chain: two mutations of the shipped asset
# survived every suite because the checks mutated the rig's copy.  The plan
# chain is built by `native.stage_plan` in BOTH, so there is one.
_TESTS = os.path.normpath(os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "tests", "polychain")).replace("\\", "/")
if _TESTS not in sys.path:
    sys.path.insert(0, _TESTS)
import native as native_rig                                      # noqa: E402

if hou.isUIAvailable() is False:
    hou.hipFile.clear(suppress_save_prompt=True)

if os.path.exists(HDA_PATH):
    os.remove(HDA_PATH)
    print("removed existing: " + HDA_PATH)

# --- the four Python SOP bodies --------------------------------------------
# ⚠️ THE BODIES LIVE IN `native.sop_body`, BESIDE THE NODE DECLARATIONS, for
# the reason 15.8.4 paid for: this script and `tests/polychain/native.py` were
# two independent declarations of one chain, and two mutations of the shipped
# asset survived every suite because the checks mutated the rig's copy.
# The bootstrap is warn-never-block wiring, not logic: a session that already
# has the package on its path skips it entirely.  Every body is ONE call of
# its own plus that bootstrap, because the code belongs in the package where
# it is version-controlled and importable by the headless checks - a fix is a
# commit, not a re-saved binary.

KERNEL_CODE = native_rig.sop_body("cook")
CONFIG_CODE = native_rig.sop_body("cook_config")
PLAN_CODE = native_rig.sop_body("cook_plan_bridge")
KIT_CODE = native_rig.sop_body("cook_kit")

# --- the stages, as data ----------------------------------------------------
# 13.7 rule 3: `Stage` is a menu over the stage output NULLS.  This tuple is
# the ONE place the order lives - the menu, the switch's inputs and the
# HDA-wiring check all read it, so a stage cannot be added to one and not the
# others.  It GROWS as 13.9's build order lands; a stage that cannot cook does
# not appear on it.
STAGES = (
    ("output", "OUT_reference", "Output - the finished run"),
    ("config", "config", "0 - Config (the resolved parameters)"),
    ("sections", "OUT_sections",
     "1 - Decompose (4.1 - arclength, corners, markers)"),
    ("plan", "OUT_plan", "2 - Plan (4.2 - one point per piece)"),
    ("plan_native", "OUT_plan_native",
     "2 - Plan, NATIVE (4.2 - the VEX fitting solve)"),
    ("frames", "OUT_frames", "4 - Frames (4.4 - the transform per piece)"),
    ("gate", "OUT_gate",
     "4 - Deform gate, NATIVE (4.4 - packed or deformed, per piece)"),
    ("place_native", "OUT_place_native",
     "4 - Place, NATIVE (4.4 - packed pieces, no Python)"),
)

# (node name, wrangle class, the input CONFIG is wired to or None, comment).
# The node name IS the .vfl name - one string, so a wrangle cannot be wired to
# a snippet that belongs to a different stage.
# D165 - INPUT NORMALISATION, and it is a NATIVE node.  `pc_arclength` keeps
# a per-(curve, vertex) walk in POINT storage, which is only sound while a
# point belongs to ONE primitive.  citygen's pipeline ends in `graph_fuse`,
# so a street network arrives WELDED at every junction, and the dev-loop trap
# list already records that a welded junction point cannot hold the
# parametrisations of every edge sharing it.  Measured before this node
# existed: two polylines sharing one vertex lost a real 90 deg corner
# outright, and the junction's metre flipped with primitive order alone.
# `splitpoints` is Houdini's own answer (procedural-modeling rule 3 - convert
# the input into the space the tool operates in), it leaves prim attributes,
# detail attributes and stand-alone marker points untouched, and it measured
# 0.00008 s on the 20 001-vertex fixture, where nothing needs splitting.
UNSHARE_COMMENT = (
    "4.1 - INPUT NORMALISATION (D165). One point per vertex, so the\n"
    "per-curve walk below cannot be overwritten by the curve next door.\n"
    "A fused junction - which is what citygen's graph_fuse emits - is\n"
    "where this earns its cook.")

DECOMPOSE = (
    ("pc_curveid", "primitive", None,
     "4.1 - the curve id AND the curve SET: pc_curve_id, else edge_id, else\n"
     "the prim number. A BLANK id is an ABSENT id (D29/D64), and a prim the\n"
     "reference declines - packed, under two points, or holding a marker\n"
     "point - is declined here too and gets no table (D167)."),
    ("pc_curve_index", "detail", 1,
     "4.1 - the id -> prim DICT, so a marker finds its curve by hash and not\n"
     "by scanning every prim (D168). It also stamps CONFIG onto the stream,\n"
     "which is what lets the reference trust these corners (D166)."),
    ("pc_arclength", "primitive", None,
     "4.1 - cumulative metres per point, plus the per-curve SAMPLER table.\n"
     "One curve per thread, the scan sequential inside it. 64-bit, because\n"
     "this is the 20 km expression that returns 0 at 32."),
    ("pc_corners", "point", 1,
     "4.1 - turn angle per vertex, the _cornerpt group and the narrow-\n"
     "corner flag. pc_corner: -1 suppress, 0 auto, 1 force."),
    ("pc_markers", "point", 1,
     "4.1 - each marker's metre along its own curve, clamped, with D35's\n"
     "zero-dist rule."),
)


def vex(name):
    """The .vfl of that name, its includes inlined (`polychain.vexsrc`)."""
    from polyfactory.polychain import vexsrc
    return vexsrc.source(name)


def wrangle(parent, name, cls, comment, precision="64", vfl=None):
    """`vfl` names the SOURCE when it is not the node name - which happens
    exactly once, where `pc_frames.vfl` is instanced twice (the bridge branch
    and the native one). Two nodes, one file."""
    node = parent.createNode("attribwrangle", name)
    node.parm("class").set({"detail": 0, "primitive": 1,
                            "point": 2, "vertex": 3}[cls])
    node.parm("snippet").set(vex(vfl or name))
    node.parm("vex_precision").set(precision)
    node.setComment(comment)
    node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return node


def python_sop(parent, name, code, comment):
    node = parent.createNode("python", name)
    node.parm("python").set(code)
    node.setComment(comment)
    node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    return node


def box(parent, name, title, colour, nodes):
    """13.7 rule 2 - every stage is a network box with a title.

    ⚠️ A NETWORK BOX COMMENT MAY NOT CONTAIN `;` OR A NEWLINE. Houdini writes
    the box file in a semicolon-terminated hscript format, and either one
    corrupts it: `defn.save` returns cleanly, the .hda is written, and the
    NEXT `createNode` of the asset raises "Failed to match node type
    definition / Network box save failed". Characterised this cycle by
    bisection - `"`, backtick, `$`, `#`, `{}`, `,` and `()` all survive; those
    two do not. The assert is here because the failure surfaces one build
    later, in a different script, with a message that names neither the box
    nor the character.
    """
    assert ";" not in title and chr(10) not in title, (
        "network box comment may not contain ';' or a newline: %r" % title)
    nbox = parent.createNetworkBox(name)
    nbox.setComment(title)
    nbox.setColor(hou.Color(colour))
    for node in nodes:
        nbox.addNode(node)
    nbox.fitAroundContents()
    return nbox


# --- build context ----------------------------------------------------------

obj = hou.node("/obj")
build_geo = obj.createNode("geo", "_build_pf_polychain")
subnet = build_geo.createNode("subnet", "pf_polychain")
subnet.createNode("null", "OUT").setDisplayFlag(True)

hda_node = subnet.createDigitalAsset(
    name="pf_polychain",
    hda_file_name=HDA_PATH,
    description="polyChain",
    min_num_inputs=0,
    max_num_inputs=4,
    version="1.0")
hda_node.allowEditingOfContents()
defn = hda_node.type().definition()
defn.setMinNumInputs(0)
defn.setMaxNumInputs(4)

net = hda_node
out_null = net.node("OUT")

# ---- the four inputs, each behind a NAMED NULL ------------------------------
# 13.7 rule 1 applied at the other end: an artist who wants to know what
# actually arrived on input 3 drops a display flag on IN_STYLE.
IN_NAMES = ("IN_SPLINE", "IN_KIT", "IN_STYLE", "IN_SURFACE")
ins = []
for _i, _name in enumerate(IN_NAMES):
    _node = net.createNode("null", _name)
    _node.setInput(0, net.indirectInputs()[_i])
    _node.setPosition(hou.Vector2(0.0, -2.0 * _i))
    ins.append(_node)

# ---- 0 CONFIG ---------------------------------------------------------------
config = python_sop(
    net, "config", CONFIG_CODE,
    "13.3.0 - THE ONLY PYTHON SOP THAT BELONGS IN THE COOK PATH.\n"
    "It resolves the parameter page against the style payload on input 3\n"
    "(the payload wins whole, D77) and writes the result as the pc_cfg\n"
    "detail dict, which VEX reads natively. No geometry; N = the parm\n"
    "count. It must never grow a geometry loop - the wrapper tripwires\n"
    "are pointed at it.")
# ⚠️ ONE INPUT CONVENTION, AND THIS NODE USED TO BREAK IT.  Every Python body
# reads its style payload with `_input_geo(node, 2)` - `kernel` and
# `pc_plan_bridge` have four inputs so that index lands on IN_STYLE, and this
# node had IN_STYLE on input 0, so `config_dict` read an UNWIRED input and
# `pc_cfg` carried PARM values under a wired payload.  Measured: a payload
# asking for corner_angle_deg = 77 produced pc_cfg 30, and `Stage = sections`
# then broke the run at two corners where the payload asks for one.  Input 0
# is left empty on purpose - index 2 must mean IN_STYLE on every body.
config.setInput(1, ins[1])
config.setInput(2, ins[2])
# 13.9 N4 - and IN_SURFACE on 3, for one bit: `has_surface`. `pc_proto` needs
# to know whether 4.5 is going to move the piece, because D55's camber
# up-vector and D98's flatten-under datum both come from the surface. The
# index convention is unchanged - 2 still means IN_STYLE on every body.
config.setInput(3, ins[3])
config.setPosition(hou.Vector2(5.0, -3.0))

# ---- 1 DECOMPOSE (4.1) - VEX and native, no Python --------------------------
_prev = ins[0]
unshare = net.createNode("splitpoints", "pc_unshare")
unshare.setInput(0, _prev)
unshare.setPosition(hou.Vector2(10.0, 4.0))
unshare.setComment(UNSHARE_COMMENT)
unshare.setGenericFlag(hou.nodeFlag.DisplayComment, True)
_prev = unshare
dec_nodes = [unshare]
for _i, (_name, _cls, _second, _comment) in enumerate(DECOMPOSE):
    _node = wrangle(net, _name, _cls, _comment)
    _node.setInput(0, _prev)
    if _second is not None:
        _node.setInput(_second, config)
    _node.setPosition(hou.Vector2(10.0, 2.0 - 2.0 * _i))
    dec_nodes.append(_node)
    _prev = _node
out_sections = net.createNode("null", "OUT_sections")
out_sections.setInput(0, _prev)
out_sections.setPosition(hou.Vector2(10.0, 2.0 - 2.0 * len(DECOMPOSE)))
dec_nodes.append(out_sections)

# ---- 2 PLAN (4.2) - still the reference, and the network says so ------------
plan = python_sop(
    net, "pc_plan_bridge", PLAN_CODE,
    "SCAFFOLDING - 13.9 N2 DELETES THIS NODE.\n"
    "4.2's fitting solve is still the reference Python. This only lifts\n"
    "what the reference already computed onto real points, so the NATIVE\n"
    "pc_frames below has something to read: pc_s0r / pc_s1r / pc_proto_* /\n"
    "pc_basey / pc_upref, and pc_frame_valid - 0 where the piece rides a\n"
    "filleted or conformed polyline the native arclength table cannot\n"
    "answer for.")
# INPUT 0 IS `OUT_sections`, NOT `IN_SPLINE` (D166) - the plan is solved on
# the same decomposed stream the shipped run is, so `Stage = plan` and
# `Stage = output` cannot answer about two different curves.
plan.setInput(0, out_sections)
for _i in range(1, 4):
    plan.setInput(_i, ins[_i])
plan.setPosition(hou.Vector2(16.0, 0.0))
out_plan = net.createNode("null", "OUT_plan")
out_plan.setInput(0, plan)
out_plan.setPosition(hou.Vector2(16.0, -2.0))

# ---- 2 PLAN, NATIVE (13.9 N2) - the fitting solve, in VEX --------------------
# ⚠️ THIS DOES NOT REPLACE `pc_plan_bridge` YET AND THE WIRING SAYS SO.  The
# bridge exists to feed `pc_frames` the module geometry the reference measured
# (`pc_proto_*`, `pc_basey`, `pc_yscale`), and that half is 13.9 N4's, not
# N2's.  What IS ported is 4.2 itself: sections, the solve, the expansion and
# the read, at EXACT parity with `plan.plan_sections` on all 92 cases.
# `Stage = plan_native` is how an artist looks at it, and `plan_native_parity`
# in run_native_checks.py is what proves it.
_plan_last, _plan_nodes = native_rig.stage_plan(net, out_sections, config)
plan_native_nodes = []
_PLAN_COMMENTS = {
    "pc_sections":
        "4.1 - THE SECTION LIST. One point per section, and the stream 4.2\n"
        "runs over. A DETAIL wrangle, so the emission order is the loop's\n"
        "order - 13.3.1 wanted a prim wrangle plus a sort SOP, and a sort\n"
        "nobody may delete is a determinism property waiting to be lost.",
    "pc_sec_only":
        "The spline away, the sections kept. Everything below runs over\n"
        "SECTIONS, not vertices.",
    "pc_plan_clean":
        "The spline-side attributes off, before the solve. Not tidying: a\n"
        "Houdini attribute is geometry-wide, so the artist's float32 pc_u on\n"
        "the MARKER CLOUD was still there when the plan wrote 3.4's own pc_u\n"
        "- and a 64-bit wrangle writing into an existing float32 attribute\n"
        "keeps float32. The plan's u was 3e-9 off on both marker cases.",
    "pc_plan_solve":
        "4.2 - THE FITTING SOLVE. One section per thread, the accumulation\n"
        "sequential inside it. It ADDS NO POINTS: the answer leaves as\n"
        "per-section arrays plus _npieces, because addpoint from a\n"
        "multithreaded wrangle emits in thread-completion order (D150).",
    "pc_plan_emit":
        "One point per piece, and 3.4's stamp: pc_elem_id by sprintf,\n"
        "pc_elem_key by the crc32 in pc_rand.h. It replaces 13.3.2's\n"
        "pointgenerate, which copies each SECTION's twelve plan ARRAYS onto\n"
        "every point it generates - quadratic: 2 000 pieces 2.1 s, 10 000\n"
        "pieces 38.6 s, while the solve above is linear. A DETAIL wrangle\n"
        "has one thread, so D150's addpoint objection does not apply.",
    "pc_plan_only":
        "The section points away, the pieces kept. \u26a0 The twelve\n"
        "per-section ARRAYS ride on - a blast removes points, not attribute\n"
        "definitions - which is why they are named _p_* and why _scrub\n"
        "before OUT is what actually removes them.",
    "pc_stamp":
        "3.4's stamp: pc_elem_id by sprintf, pc_elem_key by the crc32 in\n"
        "pc_rand.h. Its own POINT wrangle because the emit above HAS to be\n"
        "single-threaded (D150) and this is the one part of it that is\n"
        "embarrassingly parallel - 23 % of the emit at 10 000 pieces.",
}
for _name, _node in _plan_nodes.items():
    _node.setComment(_PLAN_COMMENTS[_name])
    _node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    plan_native_nodes.append(_node)
for _i, _name in enumerate(("pc_sections", "pc_sec_only", "pc_plan_clean",
                            "pc_plan_solve", "pc_plan_emit", "pc_plan_only",
                            "pc_stamp")):
    _plan_nodes[_name].setPosition(hou.Vector2(16.0, -5.0 - 2.0 * _i))
out_plan_native = net.createNode("null", "OUT_plan_native")
out_plan_native.setInput(0, _plan_last)
out_plan_native.setPosition(hou.Vector2(16.0, -19.0))
plan_native_nodes.append(out_plan_native)

# ---- 4 PLACE + DEFORM (4.4) - the frame, in VEX ------------------------------
frames = wrangle(
    net, "pc_frames", "point",
    "4.4 - place._packed_transform, in VEX. The 3x3 that maps module local\n"
    "space onto the chord A->B (D21), with the three z-modes, D98's\n"
    "flatten-under datum and D55's camber up-vector.\n"
    "Measured against the reference on 1 650 real calls drawn from all 89\n"
    "cases: the 3x3 agrees BIT FOR BIT, and P agrees exactly with the\n"
    "reference rounded to float32 P storage.\n"
    "Nothing in it random-accesses a point outside the per-curve segment\n"
    "arrays - 13.5's OpenCL transliterability constraint (D149).")
frames.setInput(0, out_plan)
frames.setInput(1, config)
frames.setInput(2, out_sections)
frames.setPosition(hou.Vector2(22.0, 0.0))

valid = net.createNode("blast", "pc_frames_valid")
valid.parm("group").set("@pc_frame_valid==0")
valid.parm("grouptype").set(3)
valid.setInput(0, frames)
valid.setPosition(hou.Vector2(22.0, -2.0))
valid.setComment(
    "The pieces the native frame is ANSWERABLE for. A piece on a filleted\n"
    "or conformed path is dropped here rather than handed a wrong frame -\n"
    "warn-never-block, while 13.9 N6 and N8 are still ahead.")
valid.setGenericFlag(hou.nodeFlag.DisplayComment, True)

out_frames = net.createNode("null", "OUT_frames")
out_frames.setInput(0, valid)
out_frames.setPosition(hou.Vector2(22.0, -4.0))

# ---- 4 PLACE, NATIVE (13.9 N4) - the packed branch ---------------------------
# ⚠️ THIS BRANCH HAS NO PYTHON IN IT AT ALL. Spline -> VEX decompose -> VEX
# plan -> VEX frames -> a native `copytopoints`, with `config` the only Python
# SOP anywhere upstream. `place_packed_parity` measures it against the
# reference's own packed prims, matched on `pc_elem_id`.
#
# ⚠️ AND IT IS NOT THE WHOLE OF 4.4. There is no deform gate yet (13.9 N5), so
# every piece here is PACKED - a piece the curvature budget would have
# unpacked is drawn as a chord. And there is no 4.3 (N8), so a run with
# corners shows no corner assembly and no reserve. `Stage = output` is
# untouched, which is what the switch is for.
_place_last, _place_nodes = native_rig.stage_place(
    net, out_plan_native, config, ins[1], out_sections, kit_code=KIT_CODE)
place_native_nodes = []
_PLACE_COMMENTS = {
    "kit_starter":
        "The kit stream, and it MOVES Python rather than adding it. 6's\n"
        "standalone floor says a curve and nothing else must make a fence,\n"
        "so kit_geometry already ran inside `kernel` on every cook with\n"
        "input 2 unwired - 15.6 lists kit.box_mesh as unported. Here the\n"
        "fallback is VISIBLE, and D154's native box SOPs replace this body.",
    "pc_kit_id":
        "4.4 - the copy id, and it is not optional. 13.2's copytopoints\n"
        "probe assumed a STRING pc_module on the kit PRIMS; 3.2 / D22 puts\n"
        "the whole manifest on the packed prim's own POINT, so useidattrib\n"
        "matched nothing and every target point received the ENTIRE KIT -\n"
        "measured, a 0.124 m post came out 2.07 m wide with no warning.",
    "kit_unpack":
        "copytopoints(pack=1) over a PACKED source nests the packs. Exact\n"
        "in world space - the parity was 0.0 with the nesting - and\n"
        "unviewable: getEmbeddedGeometry() then returns one packed prim\n"
        "instead of polygons, so the stage drew one vertex per piece.",
    "pc_proto":
        "4.4 - place.Proto's two load-bearing fields, read off the KIT: the\n"
        "module's nominal fitted length and its local origin (D20 - the\n"
        "fitted size is not the bounding box). Without them pc_frames had\n"
        "to be fed by pc_plan_bridge, which is the Python N2 deletes.\n"
        "It also declares what it CANNOT answer: a surface, a fillet, a\n"
        "slope flatten or D98's flatten-under need numbers only 4.5 has.",
    "pc_frames_native":
        "4.4 - THE SAME pc_frames.vfl as the node above, on the NATIVE\n"
        "plan. One source file, two instances: D170's float32 head-plus-\n"
        "residual is read only where a PYTHON SOP wrote the span, and this\n"
        "branch reads pc_ws0 / pc_ws1 straight - a 64-bit wrangle writes\n"
        "float64 storage, so 15.6's 'N2 deletes both' is discharged here.",
    "pc_place_valid":
        "The pieces this branch is ANSWERABLE for. Warn-never-block while\n"
        "N5, N6 and N8 are ahead: a piece whose frame needs 4.5's surface\n"
        "normal is dropped, not guessed.",
    "pc_deform_gate":
        "4.4 - THE DEFORM GATE (13.9 N5). D87's curvature budget in VEX:\n"
        "one node decides packed or deformed for every piece, which is the\n"
        "rule PC-G3 rides on - 10 005 pieces at 0.42 s and 12 MB against\n"
        "21.9 s and 360 180 points. Profiled, it is the biggest single\n"
        "Python item left on the shipped path: 0.133 s of place.build's\n"
        "0.813 s at 20 km, more than the fitting solve and the packed\n"
        "transform together. D99's band and 4.5's drape test are NOT\n"
        "ported and it says so on pc_frame_valid rather than guessing.",
    "pc_packed_only":
        "13.3.4's blast(packed), and until this cycle it did not exist -\n"
        "EVERY piece went to copytopoints, so a bending panel shipped as a\n"
        "rigid chord. Invisible, because the parity matches on pc_elem_id\n"
        "against the reference's PACKED prims and a deformed piece has no\n"
        "counterpart to disagree with.",
    "pc_out_cast":
        "13.2's lever, at the one place it is needed. The chain runs at\n"
        "vex_precision = 64 (R2) and a 64-bit wrangle writes FLOAT64\n"
        "STORAGE, so pc_u left here as 0.003703703703703704 where 3.4's\n"
        "own float32 attribute carries 0.003703703638166189. 64 bits are\n"
        "right for every intermediate and wrong for the output.",
    "pc_finalize":
        "4.6 - 3.4's STAMP, and it closes a hole nothing looked in.\n"
        "`place_packed_parity` measures P and the packed prim's world\n"
        "bounds and reads 0.0 m over 471 prims, so this branch was\n"
        "believed to reproduce the reference - it reproduced the\n"
        "GEOMETRY. Four of 3.4's fourteen prim attributes were ABSENT\n"
        "and pc_section carried the section KEY as a float where\n"
        "_stamp_values writes the section INDEX as an int.\n"
        "`place_stamp_parity` is the check that now says so.",
    "copy_packed":
        "4.4's materialisation, in ONE native node. R8, measured: the\n"
        "uniform scale DOES reach packedfulltransform (1.0 / 2.5 / 0.37\n"
        "exactly), and a 64-bit transform attribute reproduces the\n"
        "reference's packed prims bit for bit - 11.1's declined 4.34e-07 m\n"
        "is retired. pivot must be ORIGIN (centroid moves it 9.5e-07 m).",
}
_PLACE_ORDER = ("kit_starter", "pc_kit_id", "kit_unpack", "pc_proto",
                "pc_deform_gate", "pc_frames_native", "pc_place_valid",
                "pc_packed_only", "copy_packed", "pc_finalize",
                "pc_out_cast")
for _i, _name in enumerate(_PLACE_ORDER):
    _node = _place_nodes[_name]
    _node.setComment(_PLACE_COMMENTS[_name])
    _node.setGenericFlag(hou.nodeFlag.DisplayComment, True)
    _node.setPosition(hou.Vector2(22.0 + 6.0 * (_i > 2), -6.0 - 2.0 * _i))
    place_native_nodes.append(_node)
out_place_native = net.createNode("null", "OUT_place_native")
out_place_native.setInput(0, _place_last)
out_place_native.setPosition(hou.Vector2(28.0, -21.0))
place_native_nodes.append(out_place_native)

# 13.9 N5 - the gate's own stage.  It is upstream of `pc_packed_only`, so it
# carries BOTH answers: one point per piece with `_needs_deform` on it, which
# is what `gate_parity` compares against the reference's own `pc_deformed`
# and what an artist looks at to see why a run unpacked.
out_gate = net.createNode("null", "OUT_gate")
out_gate.setInput(0, _place_nodes["pc_deform_gate"])
out_gate.setPosition(hou.Vector2(22.0, -23.0))
place_native_nodes.append(out_gate)

# ---- R REFERENCE - the shipped cook path ------------------------------------
kernel = python_sop(
    net, "kernel", KERNEL_CODE,
    "THE REFERENCE IMPLEMENTATION (13.6) - ~6 000 lines of Python, and\n"
    "still the whole tool. Every stage above is measured against it, and\n"
    "it is retired one 13.9 item at a time. It is never deleted: it is the\n"
    "oracle the parity checks ask.")
# ⚠️ THIS ONE WIRE IS WHAT MAKES THE REBUILD REAL (D166). `kernel` used to
# take IN_SPLINE, so the whole DECOMPOSE box sat BESIDE the tool: measured on
# the build before this line, all six native nodes reported `cookCount == 0`
# after an Output cook, and bypassing them - or destroying them outright -
# left the output hash byte-identical. Behind OUT_sections the arclengths,
# the cleaned index table and the corners `place.read_curves` picks up are
# the ones the 64-bit wrangles computed, so the 89 scene cases and all four
# gates now exercise the VEX instead of walking past it.
kernel.setInput(0, out_sections)
for _i in range(1, 4):
    kernel.setInput(_i, ins[_i])
kernel.setPosition(hou.Vector2(28.0, 4.0))
out_reference = net.createNode("null", "OUT_reference")
out_reference.setInput(0, kernel)
out_reference.setPosition(hou.Vector2(28.0, 2.0))

# ---- the stage switch and the output ----------------------------------------
stage_switch = net.createNode("switch", "stage_switch")
for _i, (_token, _node_name, _label) in enumerate(STAGES):
    stage_switch.setInput(_i, net.node(_node_name))
stage_switch.parm("input").setExpression(
    "{%s}.get(hou.pwd().parent().evalParm('stage'), 0)"
    % ", ".join("'%s': %d" % (t[0], i) for i, t in enumerate(STAGES)),
    hou.exprLanguage.Python)
stage_switch.setPosition(hou.Vector2(34.0, 0.0))
stage_switch.setComment(
    "D155 - the Stage parm, wired. Input 0 is the finished run, so a node\n"
    "nobody has touched builds exactly what it built before this rebuild.\n"
    "A switch cooks only its selected input, so a stage you are not\n"
    "looking at costs nothing.")
stage_switch.setGenericFlag(hou.nodeFlag.DisplayComment, True)

# ---- conventions.md 2 and 5: the `_*` sweep, immediately before OUT ---------
#
# \u26a0 IT IS A WILDCARD ON ALL FOUR CLASSES, NOT A LIST OF NAMES, and that is
# the whole rule.  `pf::prepare_mesh` named `__scalefactor __scaleX __scaleY
# __scaleZ` explicitly - in the POINT class, while the wrangles wrote them as
# DETAIL - so its cleanup node had never removed anything and all four rode
# out of a shipped asset through a survey, a migration and a review pass.
#
# This cycle created about fifty internal attributes (the plan's twelve
# per-section arrays, the section record, the marker bag, the `attr:` bag, the
# sampler table) and named every one of them as if it were contract.  They are
# `_*` now and this pair is what makes that checkable.  The `pc_*` names that
# remain are named in 16 with their reason: six of them are 13.10's UNION
# interface that `place._native_tables` reads, `hda.FRAME_POINT_ATTRS` is the
# plan->frames bridge, and the rest are 3.1 input or 3.4 output contract -
# which conventions.md 3 rule 2 renames in the `pc_*` -> `pf_*` pass AFTER
# parity, because renaming one side of a parity comparison destroys it.
#
# The collateral is deliberate (conventions.md 2): an upstream `_*` name that
# was never ours is destroyed too, and `tests/hda/run_attrib_checks.py`
# records that under its `upstream/` keys so it is a diff a human reads.
scrub = net.createNode("attribdelete", "_scrub")
scrub.setInput(0, stage_switch)
for _parm in ("ptdel", "vtxdel", "primdel", "dtldel"):
    scrub.parm(_parm).set("_*")
scrub.setPosition(hou.Vector2(34.0, -2.0))
scrub.setComment(
    "conventions.md 2 - the `_*` sweep, on all four attribute classes.\n"
    "A WILDCARD and not a list: pf::prepare_mesh named its four internals\n"
    "explicitly, in the wrong class, and had never deleted one of them.")
scrub.setGenericFlag(hou.nodeFlag.DisplayComment, True)

scrub_groups = net.createNode("groupdelete", "_scrub_groups")
scrub_groups.setInput(0, scrub)
scrub_groups.parm("group1").set("_*")
scrub_groups.setPosition(hou.Vector2(34.0, -4.0))
scrub_groups.setComment(
    "conventions.md 5 - the same sweep for GROUPS. `pc_corners` builds\n"
    "`_cornerpt` and a group-name collision between two stages has already\n"
    "silently corrupted one of them in this codebase.")
scrub_groups.setGenericFlag(hou.nodeFlag.DisplayComment, True)

out_null.setInput(0, scrub_groups)
out_null.setPosition(hou.Vector2(34.0, -6.0))
out_null.setDisplayFlag(True)
out_null.setRenderFlag(True)

# ---- the network boxes (13.7 rule 2) ----------------------------------------
box(net, "stage0_config", "0 - CONFIG (13.3.0)", (0.55, 0.55, 0.58), [config])
box(net, "stage1_decompose", "1 - DECOMPOSE (4.1) - VEX + native",
    (0.29, 0.42, 0.68), dec_nodes)
box(net, "stage2_plan",
    "2 - PLAN (4.2) - the VEX solve, and the bridge N4 still needs",
    (0.35, 0.60, 0.38),
    [plan, out_plan] + plan_native_nodes)
box(net, "stage4_frames",
    "4 - PLACE + DEFORM (4.4) - the frame in VEX, and the packed copy",
    (0.70, 0.35, 0.32),
    [frames, valid, out_frames] + place_native_nodes)
box(net, "stageR_reference", "R - THE REFERENCE (13.6) - the oracle",
    (0.45, 0.38, 0.55), [kernel, out_reference])

note = net.createStickyNote("what_is_left")
note.setText(
    "WHERE THIS TOOL ACTUALLY IS (13.9's build order, cycle N-2):\n"
    "\n"
    "  4.1  decompose            N3  DONE, on the shipped cook path\n"
    "  4.2  the fitting solve    N2  DONE, EXACT on 92 cases + a\n"
    "                                170-build stress matrix. R1 was\n"
    "                                dissolved: VEX's int IS int64 at\n"
    "                                vex_precision = 64 and shrz is the\n"
    "                                unsigned shift, so splitmix64 and\n"
    "                                MT19937 are both native.\n"
    "  4.4  the PACKED branch    N4  DONE, 0.0 m against the reference's\n"
    "                                own packed prims. R8 closed: the\n"
    "                                uniform scale DOES survive\n"
    "                                packedfulltransform.\n"
    "  4.4  the DEFORM gate      N5  NOT STARTED - so every piece on the\n"
    "                                native branch is PACKED, whether or\n"
    "                                not D87's budget would unpack it.\n"
    "  4.5  conform              N6  NOT STARTED - `ray` as a node\n"
    "  4.6  finalize + guards    N7  NOT STARTED - D153\n"
    "  4.3  corners              N8  NOT STARTED - so a run with corners\n"
    "                                shows no corner assembly and no\n"
    "                                reserve on the native branch.\n"
    "\n"
    "STAGE STILL DEFAULTS TO `output`, WHICH IS `kernel`. That is the\n"
    "switch doing its job, not an oversight: 4.3, 4.5 and 4.6 are still\n"
    "the reference, so a native output would be a fence with no corner\n"
    "assemblies, no conform and no overrides (D180).\n"
    "\n"
    "THE PYTHON THAT IS LEFT, and what each one is:\n"
    "\n"
    "  config           parm/payload marshalling. PERMANENT, and it is\n"
    "                   the half of Hannes' rule Python keeps.\n"
    "  kit_starter      6's standalone floor. It MOVES Python onto a\n"
    "                   node rather than adding it - kit_geometry always\n"
    "                   ran inside `kernel`. D154 replaces the body with\n"
    "                   native box SOPs.\n"
    "  pc_plan_bridge   SCAFFOLDING. N5 deletes it: it exists only to\n"
    "                   feed pc_frames, whose deform half is N5's.\n"
    "  kernel           THE UNPORTED TOOL, and still what ships.\n"
    "\n"
    "⚠️ EVERY WRANGLE HERE NEEDS vex_precision = 64. pc_rand.h and\n"
    "pc_plan.h both COMPILE at 32 and both answer WRONGLY.\n"
    "\n"
    "Nothing above is 'done' in the dev-loop sense - no independent\n"
    "audit has run on this build. Every number is MEASURED in\n"
    "tests/polychain/run_native_checks.py, not asserted here.")
note.setPosition(hou.Vector2(36.0, -13.0))
note.setSize(hou.Vector2(15.0, 16.0))
note.setColor(hou.Color((0.85, 0.80, 0.55)))


# --- parameter page ---------------------------------------------------------

def _menu(name, label, items, default, help_text):
    """A STRING menu, never an ordinal one: the value the kernel reads is the
    token itself, so a menu reordered tomorrow cannot silently change what an
    existing node means."""
    tokens = [i[0] for i in items]
    labels = [i[1] for i in items]
    parm = hou.StringParmTemplate(name, label, 1,
                                  default_value=(default,),
                                  menu_items=tokens, menu_labels=labels)
    parm.setHelp(help_text)
    return parm


def _float(name, label, default, lo, hi, help_text):
    parm = hou.FloatParmTemplate(name, label, 1, default_value=(default,),
                                 min=lo, max=hi,
                                 min_is_strict=False, max_is_strict=False)
    parm.setHelp(help_text)
    return parm


def _int(name, label, default, lo, hi, help_text):
    parm = hou.IntParmTemplate(name, label, 1, default_value=(default,),
                               min=lo, max=hi,
                               min_is_strict=False, max_is_strict=False)
    parm.setHelp(help_text)
    return parm


def _toggle(name, label, default, help_text):
    parm = hou.ToggleParmTemplate(name, label, default_value=default)
    parm.setHelp(help_text)
    return parm


def _slot(name, label, default, help_text):
    """A module list with the kit's own manifest as its menu (5).

    `StringToggle`, NOT `StringReplace`: the value is a SPACE-SEPARATED list
    (D76) and the help sells patterns ("post panel" is a picket fence), but a
    Replace menu overwrites the whole field - an artist with "post panel" who
    picks `picket_panel` off the menu loses the post rhythm and cannot build a
    two-name pattern from the menu at all. Toggle appends and removes tokens,
    which is what a list field wants, and typing two names still works.
    """
    parm = hou.StringParmTemplate(
        name, label, 1, default_value=(default,),
        menu_type=hou.menuType.StringToggle,
        item_generator_script_language=hou.scriptLanguage.Python,
        item_generator_script=(
            "from polyfactory.polychain import hda as _h\n"
            "return _h.slot_menu(kwargs['node'])\n"))
    parm.setHelp(help_text)
    return parm


ptg = hou.ParmTemplateGroup()

# ---- MAIN PAGE: the decisions, in the order they are made -------------------

ptg.append(hou.StringParmTemplate(
    "kitfile", "Kit File", 1, default_value=("",),
    string_type=hou.stringParmType.FileReference,
    file_type=hou.fileType.Geometry,
    help=("Kit geometry (3.2) to dress the spline with. Leave EMPTY to use "
          "input 2, and leave input 2 unwired to use the built-in starter "
          "fence - post, panel, corner post and gate. Metric metres.")))

ptg.append(_slot("slot_default", "Repeating Pieces", "post panel",
                 "The modules that fill the run, by kit module name or by "
                 "role. Two or more names make a repeating pattern - "
                 "'post panel' is a picket fence. From the kit manifest."))
ptg.append(_menu("variety", "Piece Order",
                 [("first", "Always the first"),
                  ("sequence", "In turn"),
                  ("random", "Random (uses Seed)")],
                 "sequence",
                 "How the repeating pieces are chosen. 'In turn' walks the "
                 "list in order; 'Random' picks by the kit's own weights and "
                 "is repeatable for a given Seed. Conditional rules are a "
                 "style-payload feature (input 3), not a parm."))
ptg.append(_slot("slot_start", "Piece at the Start", "post",
                 "Module reserved for the first piece of every section. "
                 "Empty means the run just starts with a repeating piece."))
ptg.append(_slot("slot_end", "Piece at the End", "post",
                 "Module reserved for the last piece of every section. "
                 "Empty means the run just ends with a repeating piece."))
ptg.append(_slot("slot_corner", "Piece at Corners", "corner_post",
                 "Module placed where the spline turns by more than the "
                 "Corner Angle. Empty means the run bends through the corner "
                 "with no special piece."))
ptg.append(_slot("slot_evenly", "Evenly Spaced Piece", "",
                 "Module placed at a fixed interval along the run (see "
                 "Evenly Spacing) regardless of the fill - lamps on a "
                 "railing, bollards on a kerb."))

ptg.append(_slot("slot_marker", "Piece at Markers", "",
                 "Module placed on every marker point merged into input 1 "
                 "that carries Marker Id - a gate in a fence, a bus stop on a "
                 "kerb. Empty means markers are ignored (the node warns when "
                 "markers arrive and nothing reads them)."))
ptg.append(_int("marker_id", "Marker Id", 1, 0, 64,
                "Which markers 'Piece at Markers' answers to: the pc_marker_id "
                "the upstream points carry. One id per node; a style payload "
                "on input 3 can address several at once."))

ptg.append(_menu("fill", "Fit Method",
                 [("adaptive", "Adaptive - whole pieces, evenly stretched"),
                  ("tile", "Tile - whole pieces, remainder cut"),
                  ("scale", "Scale - stretch to fit exactly"),
                  ("count", "Count - a fixed number of pieces")],
                 "adaptive",
                 "How the pieces are fitted to each section. ADAPTIVE is the "
                 "default because it never cuts a piece: it uses whole "
                 "modules and stretches them all by the same small amount. "
                 "Tile cuts the leftover (only where the kit allows it)."))
ptg.append(_float("padding", "Gap Between Pieces (m)", 0.0, -0.5, 2.0,
                  "Metres of space added between neighbouring pieces, on top "
                  "of whatever the kit's own padding says. NEGATIVE overlaps "
                  "them, which is how lapped boards are built. The gap moves "
                  "the neighbours; it never stretches the piece."))
ptg.append(_float("evenly_spacing", "Evenly Spacing (m)", 0.0, 0.0, 50.0,
                  "Metres between 'Evenly Spaced Piece' anchors. 0 turns the "
                  "evenly pass off (or set Evenly Count in Advanced "
                  "instead)."))

ptg.append(_menu("corner_mode", "Corner Treatment",
                 [("bend", "Bend - the piece follows the corner"),
                  ("miter", "Miter - two pieces cut on the bisector")],
                 "bend",
                 "What happens where the spline turns. BEND deforms the "
                 "piece around the vertex, which suits rails and hedges; "
                 "MITER cuts a corner module on the angle bisector, which "
                 "suits kerbs, walls and anything with a hard edge."))
# D96: 5 m, not the 10 m this shipped with. The slider is soft
# (`max_is_strict=False`, so a bigger number is still typeable), and 10 m of
# rounding swallows a whole leg of PC-G1's own 12x8 m rectangle - the help
# below says as much. 0..10 is also `hou`'s UNTOUCHED default on every numeric
# template, so leaving it there makes "this parm never got a range" and "this
# parm was given exactly that range" indistinguishable to the UX check.
ptg.append(_float("fillet_radius", "Corner Rounding (m)", 0.0, 0.0, 5.0,
                  "Metres of radius to round the PATH by before any piece is "
                  "placed. 0 leaves the corner sharp. A radius wider than "
                  "the legs allow is clamped and says so."))

ptg.append(_menu("zmode", "Upright Behaviour",
                 [("", "From the kit"),
                  ("adaptive", "Follow the slope (banks)"),
                  ("vertical", "Stay plumb (pickets)"),
                  ("stepped", "Sit flat (steps)")],
                 "",
                 "How a piece meets a slope. FROM THE KIT lets each module "
                 "decide, which is what a mixed kit wants: the starter "
                 "fence's pickets stay plumb while its posts sit flat. Set "
                 "one here to override every module at once."))
ptg.append(_int("seed", "Random Seed", 3, 0, 1000,
                "Changes every random choice. The same seed and the same "
                "inputs always build the same fence, in this session and in "
                "any other."))

ptg.append(_menu("display", "Display",
                 [("full", "Full geometry"),
                  ("proxy", "Proxy boxes (fast)"),
                  ("plan", "Plan points only")],
                 "full",
                 "PROXY BOXES swaps every module for a box at its nominal "
                 "size and keeps the whole run packed - the same plan, the "
                 "same corners, a fraction of the cost. Use it while "
                 "dragging a slider over a long run. PLAN POINTS shows the "
                 "fit solve alone: one point per piece, carrying what it was "
                 "given."))

# ---- ADVANCED: one folder, no folders inside it (artist_ui rule 4) ---------

adv = hou.FolderParmTemplate("advanced", "Advanced",
                             folder_type=hou.folderType.Collapsible)

adv.addParmTemplate(_float(
    "adaptive_pct", "Adaptive Threshold (%)", 50.0, 0.0, 100.0,
    "When Adaptive is deciding whether one more piece fits: the percentage "
    "of a whole piece the leftover must reach before it adds one. 50 rounds "
    "to nearest, 100 never adds one, 0 always does."))
adv.addParmTemplate(_int(
    "count", "Piece Count", 1, 1, 500,
    "How many pieces per section in COUNT mode. Ignored in every other fit "
    "method."))
adv.addParmTemplate(_int(
    "evenly_count", "Evenly Count", 0, 0, 200,
    "Number of evenly spaced anchors per section, as an alternative to "
    "Evenly Spacing. 0 uses the spacing instead."))
adv.addParmTemplate(_menu(
    "justify", "Evenly Justify",
    [("start", "From the start"), ("center", "Centred"),
     ("end", "From the end")], "center",
    "Where the leftover goes when the evenly anchors do not divide the "
    "section exactly."))
adv.addParmTemplate(_float(
    "adjust_to_end", "Adjust to End (m)", 0.0, 0.0, 5.0,
    "Metres. When the trailing leftover is at or under this, the evenly "
    "spacing is stretched so the last anchor lands exactly on the section "
    "end. 0 never adjusts."))

adv.addParmTemplate(_menu(
    "corner_displacement", "Corner Displacement",
    [("reset", "Reset - cut where the fit ended"),
     ("extend", "Extend - push the run to the corner"),
     ("symmetric", "Symmetric - centre the last piece")], "reset",
    "What the ordinary pieces next to a MITERED corner do. Reset leaves each "
    "one where the fit put it and cuts it on the plane; Extend pushes the "
    "run out to the plane; Symmetric centres the last piece on it."))
adv.addParmTemplate(_float(
    "corner_offset_pct", "Corner Offset (%)", 0.0, -100.0, 100.0,
    "Percent of the corner module's length to slide BOTH copies along their "
    "own legs. Positive pulls them back from the vertex, negative pushes "
    "them through it. The cut plane does not move, so the seam stays shut."))
adv.addParmTemplate(_float(
    "corner_angle_deg", "Corner Angle (deg)", 30.0, 0.0, 180.0,
    "Degrees of TURN (deviation from straight) at which a spline vertex "
    "counts as a corner. Below it the run just bends through."))
adv.addParmTemplate(_float(
    "min_included_angle_deg", "Narrow Corner Angle (deg)", 15.0, 0.0, 90.0,
    "Degrees of INCLUDED angle between the two legs below which a corner is "
    "too sharp to miter. It falls back to a bend and says so."))
adv.addParmTemplate(_int(
    "fillet_segments", "Corner Rounding Segments", 4, 2, 64,
    "How many segments the Corner Rounding arc is built from. Rounded up to "
    "an even number so the arc always has a midpoint vertex."))

adv.addParmTemplate(_toggle(
    "flatten_stepped", "Plant Flat Pieces on the Ground", False,
    "A piece set to SIT FLAT has one height, and OFF it takes that height "
    "from its uphill end - so going downhill the whole run hangs in the air, "
    "and drawing the same spline the other way buries it instead. ON it "
    "takes the LOWEST ground under itself, so nothing floats and the fence "
    "comes out the same whichever way the spline was drawn. This also "
    "settles the Level Band below, which has the same one height and took "
    "it from the same end: ON, a level top rail sits at the HIGHEST ground "
    "under its piece so it never dips into the piece it caps."))
adv.addParmTemplate(_menu(
    "flat_band", "Level Band",
    [("", "Off - the whole piece follows its Upright Behaviour"),
     ("top", "Top of the piece behaves the other way"),
     ("bottom", "Bottom of the piece behaves the other way")], "",
    "The hybrid post/picket band. On a STAY PLUMB run the named band is held "
    "dead level - a picket fence with a straight top rail over bumpy ground. "
    "On a SIT FLAT run it is the other way round: the named band follows the "
    "ground while the rest stays flat - a stepped panel whose foot hugs the "
    "terrain. Off leaves every piece wholly in its Upright Behaviour."))
adv.addParmTemplate(_float(
    "flat_band_m", "Level Band Height (m)", 0.0, 0.0, 2.0,
    "Metres of the piece's own height the Level Band covers, measured from "
    "its top or its bottom. 0 switches the band off. Bigger than the piece "
    "makes the whole piece behave the other way."))

adv.addParmTemplate(_toggle(
    "fix_slope", "Measure Widths Horizontally", False,
    "ON measures every piece's width on the horizontal, so a fence keeps its "
    "post spacing seen from above as it climbs. OFF measures along the path "
    "itself, which is longer on a slope."))
adv.addParmTemplate(hou.FloatParmTemplate(
    "conform_axis", "Conform Direction", 3, default_value=(0.0, -1.0, 0.0),
    min=-1.0, max=1.0,
    help=("The direction pieces are dropped in to find the surface on input "
          "4. Straight down by default; point it sideways for a run "
          "conformed to a wall.")))
adv.addParmTemplate(_toggle(
    "conform_tilt", "Tilt to Surface", False,
    "ON rolls each piece onto the surface's own normal, so a rail follows "
    "the camber of a road. OFF keeps it upright. Individual kit modules can "
    "veto this."))

adv.addParmTemplate(_float(
    "bend_tol", "Bend Tolerance (m)", 0.01, 0.0, 1.0,
    "Metres of error allowed before a piece is unpacked and bent. This is "
    "also the instancing control: a piece stays a lightweight instance while "
    "following the curve would move it less than this, so a gently curving "
    "road of 10 000 panels stays instanced. 0 bends everything that curves "
    "at all."))
adv.addParmTemplate(_toggle(
    "show_warnings", "Colour Warnings", False,
    "Turns every element that carries a warning red. Warnings never stop the "
    "build - this is how you find them."))
adv.addParmTemplate(hou.StringParmTemplate(
    "style_id", "Style Name", 1, default_value=("pf_polychain",),
    help=("Stamped on every element as `pc_style` and mixed into the random "
          "seed. Give two polyChains different names when they share a kit "
          "and must not repeat the same pattern.")))

# D155, amended - the ONE parm this rebuild adds, and it lives in ADVANCED
# rather than in a new Debug folder.  13.7 rule 3 asked for a Debug folder;
# artist_ui 6's UX law allows exactly TWO disclosure levels and the built
# asset is audited for it (`two_disclosure_levels`), so a third folder would
# have broken a law to satisfy a layout preference.  Advanced is where the
# other technical knobs already live.
#
# It is NOT a second `display`. `display` is an art-direction control (D81/
# D82) that changes what is BUILT; this changes which stage of the build you
# are LOOKING at, and every value but the default shows an intermediate that
# was never meant to be rendered.
adv.addParmTemplate(_menu(
    "stage", "Stage (debug)",
    [(token, label) for token, _node, label in STAGES], STAGES[0][0],
    "Which stage of the network to output. This is 1c's 'open it up and "
    "toggle nodes off to see what each one does', as one menu: the run "
    "itself, the resolved parameters, the decomposed spline, the fit plan, "
    "or the per-piece frames. Leave it on Output for anything but "
    "debugging - the other entries are intermediates, not geometry."))

ptg.append(adv)
defn.setParmTemplateGroup(ptg)

defn.setExtraFileOption("polychain/source", __file__.replace("\\", "/"))

# 13.7 - THE ASSET SHIPS LOCKED, and the trap that said it could not is
# WRONG. It used to read: "unlockNewInstances is the only way the network
# boxes survive the save - a locked instance comes back with
# `networkBoxes() == []`". That observation was real and the diagnosis was
# not: a LOCKED HDA loads its contents LAZILY, so `children()`,
# `networkBoxes()` and `stickyNotes()` are all empty until something touches
# the contents. Control test, one throwaway two-node asset with one box and
# one note, saved twice with the flag as the only difference - locked:
# children 0 / boxes 0 / notes 0 before `n.node("OUT")` and children 2 /
# boxes 1 / notes 1 with the comment intact after it, `cook(force=True)`
# clean. The "Network box save failed" half belongs to the OTHER trap
# (a `;` in a box comment, see `box()` above), which carries the identical
# error string.
#
# ⚠️ AND THE FLAG IS NOT FREE. Measured at citygen scale, 300 chain nodes in
# one scene: unlocked 2.056 s to create against 0.094 s locked, 6 000 child
# nodes materialised against 0, a 20.7 MB .hip against 0.76 MB. Worse than
# any of that, `matchesCurrentDefinition()` is False on a FRESH untouched
# unlocked instance, so every scene an artist saves forks its own private
# copy of the network and never receives a later fix - with nine build-order
# items still ahead, that is every scene built during the rebuild running
# last week's graph forever.
#
# The readability deliverable (`artist_ui.md` 6 rule 10) does not need it:
# diving into a locked instance loads the contents and shows the boxes, the
# comments and the sticky note, and an artist who wants to EDIT one instance
# still has Allow Editing of Contents per node.
_opts = defn.options()
_opts.setUnlockNewInstances(False)
defn.setOptions(_opts)
defn.save(HDA_PATH, template_node=hda_node)

hda_node.destroy()
build_geo.destroy()

print("[pf_polychain] created: " + HDA_PATH)
