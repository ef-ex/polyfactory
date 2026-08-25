"""THE MUTATION REGISTRY - every polyChain check paired with the edit that
proves it can fail.

    hython tests/polychain/run_mutation_registry.py          # the meta-runner
    hython tests/polychain/pdg_build.py --full               # in parallel

⚠️ WHY THIS FILE EXISTS. `ideas/build_retrospective.md`: across ~15 build
cycles the dominant recurring failure was not a bug in the tool - it was a
check that COULD NOT FAIL. ~20 instances, one in almost every cycle, every
one found by an independent auditor running a mutation by hand and never by
the suite, which was green through all twenty. This file is "a check is not
written until its mutation has been seen to fail" as DATA; the meta-runner is
it as a RUNNER.

WHAT AN ENTRY IS. One `M(...)`: an id, the runner that owns the paired
checks, exact source edits, and `kills` - the check names that MUST go red.
Three properties, each an incident:

  * the edit is an exact string swap and the runner asserts it matched
    EXACTLY ONCE - a mutation whose target line has moved reports a green
    forever (D208);
  * `kills` names the check, so the pairing is falsifiable, and ONLY the
    declared pairing is credited - crediting a mutation's blast radius
    silently marked 47 unexamined names as proven;
  * A CRASH IS NOT A RED (21.5): an `AssertionError` raised inside a check
    while the check credited with the catch printed PASS. That is ABORT and
    it fails the run unless the entry says `expect="abort"` and why.

OUT OF SCOPE BY CONSTRUCTION: `scale_gate.py` prints a failing-ROW count and
`tests/hda/run_attrib_checks.py` prints a name only when it FAILS, so neither
has an inventory a green run can be asked for and there is no name to pair
against. That is a property of their output format, not a judgement.
"""

# --- the runners the registry can pair against ------------------------------

RUNNERS = {
    "native": "tests/polychain/run_native_checks.py",
    "scene":  "tests/polychain/run_scene_checks.py",
    "2d":     "tests/polychain/run_2d_checks.py",
    "hda":    "tests/polychain/run_hda_checks.py",
    "images": "tests/polychain/gate_images.py",
    # v2's differential oracle over GENERATED input, on the shipped asset.
    # It prints exactly THREE names, deliberately: seed numbers are
    # diagnostics, not check names (a sweep that moves its range would
    # silently retire and invent hundreds of them).
    "generated": "tests/polychain/run_generated.py",
    # 7.7's on-ramp, on BOTH shipped assets: the slicer's own inverse as the
    # oracle, then the kit it emits through `pf_polychain`.
    "slice": "tests/polychain/run_slice_checks.py",
}

# `run_scene_checks` and `run_2d_checks` carry a baseline, and D210 made a
# MOVED baselined value fail the run exactly like a failing check.  Movement
# has no check name, so it gets a reserved one and a mutation can be paired
# against it.
BASELINE_MOVED = "ZZ_BASELINE_MOVED"


class M(object):
    """One registered mutation.

    `edits`   ((repo-relative path, exact old text, new text), ...)
    `kills`   check names that must go RED when it is applied
    `runner`  which runner owns those names
    `rebuild` re-run `devScripts/create_pf_polychain_hda.py` in the export
              afterwards, so the SHIPPED ASSET and its declaration move
              together (21.4's rule - a source mutation that does not rebuild
              is testing the rig, not the deliverable)
    `expect`  "red" (the default) or "abort", for the handful whose edit stops
              the runner before it can print a verdict.  An "abort" entry
              credits no coverage.
    """

    def __init__(self, mid, runner, kills, why, edits,
                 rebuild=True, expect="red", note=""):
        assert runner in RUNNERS, runner
        assert kills, "a mutation with no paired check proves nothing"
        assert expect in ("red", "abort")
        self.id = mid
        self.runner = runner
        self.kills = tuple(kills)
        self.why = why
        self.edits = tuple(edits)
        self.rebuild = rebuild
        self.expect = expect
        self.note = note


GEN = "tests/polychain/run_generated.py"
VEX = "polyfactory/vex/polychain/%s"
PY = "polyfactory/scripts/python/polyfactory/polychain/%s"
RIG = "tests/polychain/native.py"
RUNNER_NATIVE = "tests/polychain/run_native_checks.py"
BUILD = "devScripts/create_pf_polychain_hda.py"
SLICE_BUILD = "devScripts/create_pf_polychain_slice_hda.py"
IMG = "tests/polychain/gate_images.py"


MUTATIONS = (

    # ---- v2: the generated differential, on the SHIPPED asset -------------
    M("generated_pc_local_scaled", "generated",
      ("generated_output_matches_the_reference",),
      "The v2 oracle's own proof.",
      ((VEX % "pc_deform.vfl",
        "v@pc_local = local;", "v@pc_local = local * 1.5;"),)),

    M("generated_known_pattern_broken", "generated",
      ("known_divergences_still_occur",
       "generated_output_matches_the_reference"),
      "The other half of a KNOWN divergence: an entry that stops occurring "
      "has either been fixed (delete it deliberately) or stopped being "
      "REACHED, which is the fixture-blindness class the generator exists "
      "to attack.",
      ((GEN, "\".prim: 'pc_module' only on the RIGHT\"",
        "\".prim: 'pc_NEVER' only on the RIGHT\""),),
      rebuild=False),

    # ---- 13.9 N10, the guard switch: the flip, and its undo ----------------
    M("stage_output_repointed", "native",
      ("output_guard_takes_the_native_chain",
       "output_runs_the_native_chain_inside_the_envelope",
       "native_stages_are_really_native"),
      "27.7b m3 / 21.4 M1 - the exact source-level UNDO of the whole native "
      "flip: `Stage = output` pointed back at the Python reference.",
      ((RIG,
        '    ("output", "OUT_final", "guard_envelope",',
        '    ("output", "OUT_reference", "kernel",'),)),

    M("guard_never_refuses", "native",
      ("output_guard_parity", "no_case_pays_the_guard_fallback"),
      "27.7b m6 - level 1 admits every build, including the classes the "
      "native chain cannot answer (corners, conform, flatten).",
      ((VEX % "pc_envelope.vfl",
        "i@_native_ok = (ok && corners == 0 && ndup == 0",
        "i@_native_ok = (1 || ok && corners == 0 && ndup == 0"),)),

    # ---- D223 / D262, storage as a contract --------------------------------
    M("vex_precision_32", "native",
      ("native_intermediates_are_64bit", "decompose_arclength_parity",
       "trials_irrational_20km_asymmetric"),
      "27.7b m4 / 21.4 M4 - every wrangle dropped to 32-bit.",
      ((RIG,
        'def wrangle(parent, name, cls, vfl, precision="64"):',
        'def wrangle(parent, name, cls, vfl, precision="32"):'),)),

    M("out_cast_pc_local_fpreal64", "native",
      ("output_guard_parity", "output_snapshot_sees_the_deformed_branch"),
      "D246's STORAGE demonstration, and the reason `_snapshot` grew a "
      "`numericDataType()` dimension: `pc_local` shipped at fpreal64 where "
      "the reference ships fpreal32.",
      ((RIG, 'cast.parm("precision2").set("fpreal32")',
        'cast.parm("precision2").set("fpreal64")'),),
      note="⚠️ NOT `numcasts` 3 -> 1, which is what this entry tried first: "
           "the build script goes on to set `class2`/`class3` "
           "unconditionally, so the rebuild RAISES and the run reports "
           "STALE rather than red."),

    M("out_cast_ints_int64", "native",
      ("output_guard_parity",),
      "27.7b m10 / D262 - the OUTPUT's integer storage.",
      ((RIG, 'cast.parm("precision3").set("int32")',
        'cast.parm("precision3").set("int64")'),)),

    # ---- D246's other half: point-attribute VALUES -------------------------
    M("pc_local_scaled", "native",
      ("output_snapshot_sees_the_deformed_branch", "output_guard_parity"),
      "D246's VALUES demonstration #1.",
      ((VEX % "pc_deform.vfl",
        "v@pc_local = local;", "v@pc_local = local * 1.5;"),)),

    M("pc_local_zeroed", "native",
      ("output_snapshot_sees_the_deformed_branch", "output_guard_parity"),
      "D246's VALUES demonstration #2, and the harsher of the two: the "
      "attribute is not merely wrong, it is GONE, and by name it is still "
      "there.",
      ((VEX % "pc_deform.vfl",
        "v@pc_local = local;", "v@pc_local = set(0.0, 0.0, 0.0);"),)),

    # ---- D247, the tolerance that was disguised as exactness ---------------
    M("conform_drop_biased", "native",
      ("conform_drop_is_portable_to_vex",),
      "13.9 N6's deciding experiment, biased by 1e-5 m along the drop axis.",
      ((RIG.replace("native.py", "run_native_checks.py"),
        "if (hit) { float t = dot(best - q, a); best = q + a * t; }",
        "if (hit) { float t = dot(best - q, a); "
        "best = q + a * t + a * 1e-5; }"),),
      rebuild=False),

    # ---- D241 / D257, the array-and-dict subject ---------------------------
    M("array_subject_test_equals_3", "native",
      ("plan_fixture_parity",),
      "27.7b m8 - `t >= 3` back to `t == 3`.",
      ((VEX % "pc_sections.vfl",
        "if (t >= 3 || primattribsize(0, name) != 1)",
        "if (t == 3 || primattribsize(0, name) != 1)"),)),

    # ---- D242 / D265, the markerData slot ----------------------------------
    M("marker_data_cross_type_read", "native",
      ("guard_marker_data_types", "plan_fixture_parity"),
      "27.7b m9, THE SURVIVOR THAT MATTERED MOST: reverting the "
      "`!unreadable:` branch left the suite 144 [PASS] / 0, i.e.",
      ((VEX % "pc_plan_solve.vfl",
        "            } else {\n"
        "                csi[concat(PC_UNREADABLE, key)] = \"\";\n"
        "            }",
        "            } else {\n"
        "                float v = md[k]; cfi[key] = v;\n"
        "            }"),)),

    # ---- 13.9 N5, the output's ORDER is a number ---------------------------
    M("piece_key_within_piece_dropped", "native",
      ("piece_order_key_is_total",),
      "26's SURVIVOR: dropping the within-piece term from the point half of "
      "the order key left the suite 136 [PASS] / 0, because Houdini's "
      "`sort` happens to be STABLE and equal keys kept the emission order.",
      ((VEX % "pc_piece_key.vfl",
        "f@_pkeyp = (float)i@_pkey0 * (float)PC_PIECE_SPAN "
        "+ (float)i@_srcpt;",
        "f@_pkeyp = (float)i@_pkey0 * (float)PC_PIECE_SPAN;"),)),

    # ---- 4.3 corners: killed by the SCENE suite, survives the native one ---
    M("corner_bisector_negated", "scene",
      ("corner_abut_m", "corner_outside_m", "corner_breach_m",
       "corner_face_mate_m"),
      "21.4 M5 / 27.7b m5 - the corner bisector taken as the INCOMING "
      "TANGENT instead of `unit(tin + tout)`.",
      ((PY % "corner.py",
        "        self.n = _unit(summed, self.tin)",
        "        self.n = _unit(self.tin, self.tin)"),),
      rebuild=False,
      note="survives run_native_checks by design - see 27.7b"),

    # ---- 4.5 conform -------------------------------------------------------
    M("conform_axis_permuted", "scene",
      ("conform_misses", "warnings", "camber_deg", "bank_deg"),
      "cycle 6 M1 - the projection axis permuted -Y to -Z. The drape stops "
      "being a drop and becomes a sideways cast.",
      ((PY % "conform.py",
        "        self.axis = _unit(axis, (0.0, -1.0, 0.0))",
        "        self.axis = _unit((0.0, 0.0, -1.0), (0.0, -1.0, 0.0))"),),
      rebuild=False,
      note="⚠️ WHAT THIS MEASURED, and it is a blind spot worth writing "
           "down: `conform_drape_m` and `conform_contact_m` DO NOT SEE IT. "
           "A permuted axis makes the cast MISS, and a missed drop leaves "
           "the run unmoved (D53), so the two checks that carry `drape` and "
           "`contact` in their names read 0.0 and pass."),

    M("conform_drop_biased_py", "scene",
      ("conform_parity", "ray_verb_semantics"),
      "The drape displaced 5 cm along the surface normal in `Surface.drop` "
      "- the REFERENCE half of 11.2 P5's pair.",
      ((PY % "conform.py",
        "        return (best[0], nrm, True)",
        "        return ((best[0][0], best[0][1] + 0.05, best[0][2]), "
        "nrm, True)"),),
      rebuild=False),

    # ---- 3.4's stamp: two writers, one description -------------------------
    M("stamp_bulk_u_offset", "scene",
      ("stamp_parity",),
      "D102's bulk writer drifted from the per-prim reference by 1e-6 on "
      "`pc_u`, on every prim but the first.",
      ((PY % "place.py",
        "            col.extend([values.get(name, blank)] * n)",
        "            _v = values.get(name, blank)\n"
        '            if name == "pc_u" and col:\n'
        "                _v = _v + 1e-6\n"
        "            col.extend([_v] * n)"),),
      rebuild=False),

    # ---- 4.6 instancing: the curvature budget ------------------------------
    M("curvature_budget_widened", "scene",
      ("packed_pieces", "curvature_budget_m"),
      "D75's budget widened by 1e6, so nothing ever unpacks.",
      ((PY % "place.py",
        "        return True                              # D75, D87, D100, D104",
        "        return True and False                    # D75, D87, D100, D104"),),
      rebuild=False),

    M("deviates_branch_disabled", "scene",
      ("packed_true_dev_m", "deform_gate_m", "warnings"),
      "cycle 6 M2 - a genuinely deformed piece stays packed because the "
      "`deviates` branch is gone.",
      ((PY % "place.py",
        '    if zmode != "stepped" and getattr(path, "deviates", None) '
        "is not None             and path.deviates(sa, sb, tol, "
        "fracs=proto.fracs):",
        '    if False and zmode != "stepped" and getattr(path, "deviates", '
        "None) is not None             and path.deviates(sa, sb, tol, "
        "fracs=proto.fracs):"),),
      rebuild=False),

    # ---- 4.2, the fitting solve: one piece too few -------------------------
    M("adaptive_rounds_down", "scene",
      (BASELINE_MOVED, "warnings"),
      "4.2's adaptive rounding, one piece the other way: D14's 'a remainder "
      "over `adaptive_pct` earns another unit' deleted.",
      ((PY % "plan.py",
        "        if (exact - n) * 100.0 >= params.adaptive_pct - EPS:\n"
        "            n += 1",
        "        if False and (exact - n) * 100.0 >= params.adaptive_pct - "
        "EPS:\n            n += 1"),),
      rebuild=False),

    # ---- D210: a moved baselined value fails the run ------------------------
    M("scene_baseline_perturbed", "scene",
      (BASELINE_MOVED,),
      "D210, live rather than argued: `run_scene_checks` used to PRINT a "
      "moved baseline value and still exit 0, so every 'no baseline "
      "movement' claim in this build rested on that exit code.",
      (("tests/polychain/baseline.json", None, None),),
      rebuild=False),

    # ---- 7.3.3 / P2-3V incident 1: the check that could not fail -----------
    M("2d_clip_stamp_zeroed", "2d",
      ("clip_stamp",),
      "P2-3V incident 1, the FIRST unfailable check this project recorded: "
      "`clip_stamp` was `ok = area or n == 0`, so on an area build - the "
      "only kind where the stamp can legitimately be 1, and the only kind "
      "it was written for - `ok` was True whatever the value was.",
      ((PY % "plan.py",
        "        p.clipped = int(clipped)",
        "        p.clipped = 0"),),
      rebuild=False,
      note="⚠️ IT HAS TO BE THE TRANSFER'S DESTINATION, NOT ITS SOURCE. "
           "Zeroing `array2d`'s own `attrs['pc_clipped']` instead leaves "
           "the check GREEN, because the row curve is where `clip_stamp` "
           "reads its expectation from - the mutation and the oracle would "
           "move together."),

    # ---- the artist face: the four input ports -----------------------------
    M("kit_input_unplugged", "hda",
      ("input2_is_the_kit",),
      "THE KIT PORT WIRED TO NOTHING inside the asset - the bluntest "
      "possible failure of input 2.",
      ((BUILD,
        "    _node.setInput(0, net.indirectInputs()[_i])",
        "    _node.setInput(0, None if _i == 1 "
        "else net.indirectInputs()[_i])"),),
      note="⚠️ THE MECHANISM, read out of the source rather than guessed: "
           "`Kit.resolve(name)` ends `return [stand_in(name)]`, so a module "
           "the kit cannot supply is replaced by a blank box CARRYING THE "
           "REQUESTED NAME. `input2_is_the_kit` renames panel -> plank in "
           "the kit it wires and then asserts `plank`..."),

    M("hda_input_ports_swapped", "hda",
      ("payload_overrides_modules", "payload_matches_kernel",
       "parms_inert_under_payload_native"),
      "2d 3 - no review lens ever looked at the built asset's metadata, and "
      "Hannes found the missing TAB-menu entry and the unlabelled ports "
      "himself.",
      ((BUILD,
        "    _node.setInput(0, net.indirectInputs()[_i])",
        "    _node.setInput(0, net.indirectInputs()"
        "[{0: 0, 1: 2, 2: 1, 3: 3}[_i]])"),),
      note="⚠️ IT HAS TO SWAP THE WIRING, NOT THE NAMES. Swapping the two "
           "entries in `IN_NAMES` reddens NOTHING - measured - because "
           "every consumer downstream takes `ins[i]` by INDEX, so the "
           "mutation only renames two nulls and the asset behaves "
           "identically."),

    # ---- D266: the shipped defaults that built TWO pillars at a corner ----
    M("default_slot_composed_again", "hda",
      ("starter_fence_one_pillar_miter",),
      "D266 - the exact source-level UNDO of this cycle's fix.",
      ((BUILD,
        'ptg.append(_slot("slot_default", "Repeating Pieces", "panel",',
        'ptg.append(_slot("slot_default", "Repeating Pieces", "post panel",'),
       (BUILD,
        'ptg.append(_slot("slot_evenly", "Evenly Spaced Piece", "post",',
        'ptg.append(_slot("slot_evenly", "Evenly Spaced Piece", "",')),
      note="⚠️ IT REDDENS ONLY THE `miter` ROW, and that is correct rather "
           "than a weakness in the pairing: `bend` mode places no corner "
           "assembly at all (D36 welds the ring), so there is no reserved "
           "pillar for the fill to double and "
           "`starter_fence_one_pillar_bend` stays 0.0 on the mutated build "
           "- measured."),

    M("evenly_doubles_the_fill", "hda",
      ("starter_fence_one_pillar_bend", "starter_fence_one_pillar_miter"),
      "D267's OTHER direction, and the row that would otherwise be "
      "unfailable.",
      ((BUILD,
        'ptg.append(_slot("slot_default", "Repeating Pieces", "panel",',
        'ptg.append(_slot("slot_default", "Repeating Pieces", "post",'),)),

    M("corner_style_composed_default", "scene",
      ("double_pillar_m",),
      "D266's other half - THE FIXTURE GAP, as a mutation.",
      (("tests/polychain/cases.py",
        '    rules = [\n        Rule("default", "first", ["panel"]),',
        '    rules = [\n        Rule("default", "sequence", ["post", "panel"]),'),),
      rebuild=False,
      note="⚠️ IT MUTATES THE FIXTURE, NOT THE KERNEL, and that is the "
           "point: the kernel was never wrong."),

    # ---- D269: a corner RESERVES space, and the guard has to know it -------
    M("evenly_ignores_the_corner_reserve", "hda",
      ("evenly_clears_the_corner_justify_end",),
      "D269, at source - the corner's reservation stops guarding the evenly "
      "anchors and only a CAP does, which is what shipped.",
      ((PY % "plan.py",
        "        guard_a = head is not None or float(trim[0]) > EPS\n"
        "        guard_b = tail is not None or float(trim[1]) > EPS",
        "        guard_a = head is not None\n"
        "        guard_b = tail is not None"),),
      rebuild=False,
      note="⚠️ THE LEG LENGTH IS THE MUTATION'S OTHER HALF. On the 12 x 8 m "
           "rectangle every justification measures 0.0 BOTH BEFORE AND "
           "AFTER the fix, because 12 m is an exact multiple of the 2 m "
           "spacing and the justify leftover never approaches zero - so a "
           "fixture on the round number is green on the broken..."),

    # ---- D194: verify an image contains its subject ------------------------
    M("gate_image_not_unpacked", "images",
      ("image_shows_packed_L_bend", "image_shows_packed_L_miter",
       "image_shows_packed_rect_bend"),
      "D194, at source - `unpack` made a no-op.",
      ((IMG,
        'def unpack(geo):\n    """A flat copy with every PACKED prim '
        "expanded, for the rasteriser.",
        'def unpack(geo):\n    return geo    # the D194 mutation\n    """A '
        "flat copy with every PACKED prim expanded, for the rasteriser."),),
      rebuild=False),

    M("2d_baseline_perturbed", "2d",
      (BASELINE_MOVED,),
      "The same rule on the OTHER runner that carries a baseline.",
      (("tests/polychain/baseline_2d.json", None, None),),
      rebuild=False),

    # ---- the two entries that were EXEMPT until an audit wrote them --------
    #
    # ⚠️ BOTH OF THESE WERE ON THE EXEMPT LIST, and the list said a mutation
    # for them was impractical. An independent auditor wrote both on the first
    # correct attempt. That is the whole argument for keeping EXEMPT small and
    # attacking it: an exemption is a claim, and a claim in this project is
    # something to falsify, not something to file.

    M("exempt_frames_injection_neutered", "native",
      ("mutation_pc_frames",),
      "The `mutation_*` checks apply their own in-line edit and assert the "
      "break SHOWS. This neuters one - the injected scale error becomes the "
      "sound line, so `frames_parity`'s `broken` build is byte-identical to "
      "the sound one - and `mutation_pc_frames` must go red because its "
      "worst relative error...",
      ((RUNNER_NATIVE,
        '    broken = vexsrc.source("pc_frames").replace(\n'
        '        "float scale = max(clen / plen, 1e-9);",\n'
        '        "float scale = max(clen / plen, 1e-9) * 1.0000001;")',
        '    broken = vexsrc.source("pc_frames").replace(\n'
        '        "float scale = max(clen / plen, 1e-9);",\n'
        '        "float scale = max(clen / plen, 1e-9);")'),),
      rebuild=False),

    M("exempt_gate_parity_collapsed", "native",
      ("gate_parity_sees_both_answers",),
      "The vacuity guard on `gate_parity`, attacked directly: the Python "
      "reference's `_needs_deform` returns False for every piece, so the "
      "reference answers a constant and the compared pieces contain one "
      "answer instead of two.",
      ((PY % "place.py",
        '    """4.4 + the streets float32 lesson: rebuild ONLY when it '
        'changes something."""\n'
        "    if placement.slice_t is not None or placement.cuts:",
        '    """4.4 + the streets float32 lesson: rebuild ONLY when it '
        'changes something."""\n'
        "    return False            # the mutation: one answer, not two\n"
        "    if placement.slice_t is not None or placement.cuts:"),),
      rebuild=False),

    # ---- 7.7, the kit slicer. `rebuild=False` on every entry that edits the
    #      PACKAGE, and that is not a rig exemption: `pf_polychain_slice`'s
    #      two Python SOPs each import `polychain.kit` at cook time, so the
    #      committed .hda plus the mutated package IS the shipped path. Only
    #      the entry that edits the BUILD SCRIPT needs the rebuild, and it
    #      gets it (`BUILD_SCRIPTS` now covers both assets).
    M("slice_cell_frame_offset", "slice",
      ("slice_recovers_the_authored_kit", "slice_keeps_the_manifest",
       "sliced_kit_builds_the_same_fence", "slice_reports_a_void"),
      "D270's whole claim: the cell frame is the CELL. Move the module "
      "origin 10 mm and the kit still validates, still carries every "
      "manifest field, and lays a fence with a 10 mm gap at every joint.",
      ((PY % "kit.py",
        "src.transform(hou.hmath.buildTranslate(-cell.x0, -cell.y0, -zc))",
        "src.transform(hou.hmath.buildTranslate(-cell.x0 + 0.01, -cell.y0, "
        "-zc))"),),
      rebuild=False),

    M("slice_top_clip_missing", "slice",
      ("slice_recovers_the_authored_kit", "sliced_kit_builds_the_same_fence"),
      "One of the four half-spaces pushed out of reach - the cell keeps "
      "everything above its own top edge. The oracle is what sees it: a "
      "count-based check would still report nine modules.",
      ((PY % "kit.py", "((0.0, cell.y1, 0.0), (0.0, 1.0, 0.0), -1)",
        "((0.0, cell.y1 + 100.0, 0.0), (0.0, 1.0, 0.0), -1)"),),
      rebuild=False),

    M("slice_cut_plane_short", "slice",
      ("slice_refit_gap_m", "slice_recovers_the_authored_kit",
       "sliced_kit_builds_the_same_fence"),
      "The X cut 10 mm short of the band boundary - the jigsaw failure the "
      "tool exists to prevent, and the one D131 asserts against.",
      ((PY % "kit.py", "((cell.x1, 0.0, 0.0), (1.0, 0.0, 0.0), -1)",
        "((cell.x1 - 0.01, 0.0, 0.0), (1.0, 0.0, 0.0), -1)"),),
      rebuild=False),

    M("slice_jigsaw_off", "slice",
      ("slice_jigsaw_size_m",),
      "D131's rule deleted. It reddens ONE name, and that is the point: the "
      "jigsaw check runs on an UNEVEN-band fixture on purpose, because the "
      "even one it would naturally be written against cannot fail.",
      ((PY % "slicer.py", "    if not jigsaw:\n        return bands",
        "    if True:\n        return bands"),),
      rebuild=False),

    M("slice_role_forced_default", "slice",
      ("slice_keeps_the_manifest", "slice_defaults_build_a_kit",
       "slice_guides_name_a_cell", "sliced_kit_fills_a_facade"),
      "Every cell shipped as `default`. The kit still validates and still "
      "has nine modules; what dies is 7.2's vocabulary and, downstream, the "
      "closed facade's corner.",
      ((PY % "kit.py", "roles=cell.role, variant=cell.variant)",
        "roles=\"default\", variant=cell.variant)"),),
      rebuild=False),

    M("slice_void_detector_off", "slice",
      ("slice_reports_a_void",),
      "D270's other half: a cell whose geometry does not reach its own low "
      "corner is placed that far off its bay, silently.",
      ((PY % "kit.py", "        if gap > 1e-6:", "        if False:"),),
      rebuild=False),

    M("slice_preview_empty", "slice",
      ("slice_cells_view_draws_every_cell", "slice_image_shows_the_kit"),
      "The `Where The Cuts Land` branch emits nothing. It is paired with "
      "the IMAGE check deliberately - that check scored `0 >= 4 * 0` on a "
      "black frame until it also asserted a prim floor.",
      ((PY % "kit.py", "        geo.merge(piece)\n        col = list(",
        "        col = list("),),
      rebuild=False),

    M("slice_human_scale_negative", "slice",
      ("slice_hda_kit_is_valid", "slice_keeps_the_manifest",
       "sliced_kit_builds_the_same_fence"),
      "buildings 12.9's mandatory manifest field, written nonsense. The "
      "kit reader's own validator is what catches it, on the SHIPPED node's "
      "output rather than on a kit built in the check.",
      ((PY % "kit.py",
        "                   human_scale_reference=human_scale_reference)",
        "                   human_scale_reference=-1.0)"),),
      rebuild=False),

    M("slice_guide_normal_unguarded", "slice",
      ("slice_degenerates_warn_never_block",),
      "D24 is warn-never-block, and the input this tool exists to ingest is "
      "hand-authored. A guide point with no `N` at all is the commonest "
      "thing an artist wires in; without the guard the bulk read raises and "
      "the node goes red instead of saying what is wrong.",
      ((PY % "kit.py", "    if geo.findPointAttrib(\"N\") is None:",
        "    if False:"),),
      rebuild=False),

    # ---- C1's audit: five findings, five checks, five mutations. Every one
    #      of these was invisible to the acceptance evidence C1 shipped with,
    #      and four of the five were invisible to every image as well.
    M("slice_polyfill_closes_everything", "slice",
      ("slice_keeps_the_artists_surface",),
      "`polyfill` closing EVERY open boundary in the chunk again, not only "
      "the ones the clip opened - C1's shipped behaviour. A plain single-"
      "sided 9 x 6 wall came back at 108.000 m2 from 54.000 and a wall with "
      "a window came back with the WINDOW FILLED IN plus ten zero-area "
      "polygons, kit valid and gate image unchanged. Nothing else in the "
      "suite moves: the oracle's nine modules are closed solids cut on "
      "planes their own faces already lie in, so it cannot reach this.",
      ((PY % "place.py",
        "        stray = _off_plane_patches(filled, n_cut, n_all, origin, "
        "normal)",
        "        stray = []"),),
      rebuild=False),

    M("slice_notes_never_reach_the_page", "slice",
      ("slice_notes_reach_the_artist", "slice_reports_a_void",
       "slice_cell_frame_gap_m"),
      "D24 made decorative, which is the state C1 shipped in: every warning "
      "still computed, every one of them written on a Python SOP inside the "
      "asset, and the artist's node clean on an unwired input.",
      ((PY % "kit.py", "    write_notes(geo, warns)",
        "    write_notes(geo, [])"),),
      rebuild=False),

    M("slice_high_corner_unmeasured", "slice",
      ("slice_cell_frame_gap_m",),
      "The cell-frame gap back to the LOW corner only. A 0.4 m chunk asked "
      "for a 5 m bay then ships `pc_size = (5, 5, 0.1)` around 0.4 m of "
      "wall, validates clean, and pf_polychain lays out 5 m bays.",
      ((PY % "kit.py",
        '                (sx - hi[0], "high x"), (sy - hi[1], "high y")),',
        '                (lo[0], "low x"), (lo[1], "low y")),'),),
      rebuild=False),

    M("slice_z_left_as_authored", "slice",
      ("slice_kit_z_is_canonical",),
      "D272 reverted - X and Y normalised, Z left exactly where the artist "
      "modelled it. A facade modelled IN PLACE on a building, which is the "
      "normal workflow, then builds a fence 49.90 m behind its own curve "
      "with nothing said.",
      ((PY % "kit.py", "    zc = _kit_z_centre(pairs)", "    zc = 0.0"),),
      rebuild=False),

    M("slice_cap_uv_collapsed", "slice",
      ("slice_cap_uv_spans_two_axes",),
      "`dress_caps` back to the fixed (local z, local y) projection it was "
      "written for on the miter cut. On a Y cut plane local y is constant "
      "across the face, so half of every sliced module's cut faces ship a "
      "zero-area UV island - on real, visible 0.6 m2 faces.",
      ((PY % "place.py",
        "        u, v = (flat + 2) % 3, (flat + 1) % 3",
        "        u, v = 2, 1"),),
      rebuild=False),

    M("slice_input_label_lost", "slice",
      ("slice_hda_metadata",),
      "5.1b on the new asset - a port label an artist meets before any "
      "parameter. The ONLY slice entry that rebuilds, because the labels "
      "are written into the .hda at build time and nowhere else.",
      ((SLICE_BUILD, 'INPUT_LABELS = ("Chunk", "Guides (optional)")',
        'INPUT_LABELS = ("Input 1", "Guides (optional)")'),)),
)

# ⚠️ IDS ARE UNIQUE, ASSERTED HERE. Two entries shared the id
# `conform_drop_biased` for one sweep - one on `native`, one on `scene` - and
# the resumable state file is keyed by id, so the second silently REPLAYED the
# first's verdict and was never run. A registry whose own keys collide is the
# defect it exists to catch, one level up.
_ids = [m.id for m in MUTATIONS]
assert len(_ids) == len(set(_ids)),     "duplicate mutation id: %s" % sorted(set(i for i in _ids
                                             if _ids.count(i) > 1))


# ---- the coverage meta-check ------------------------------------------------
#
# Every check name a runner prints is in exactly one of three states: PROVEN
# (a registered mutation was SEEN to redden it), EXEMPT (a mutation is
# impractical, or the check IS a mutation), or UNPROVEN (declared, dated
# debt). A name in none of the three FAILS the meta-runner, so a check cannot
# be added without a decision about how it can fail.
#
# ⚠️ EXEMPT IS A CLAIM, WHICH MAKES IT A TARGET. It held 36 rows; an auditor
# attacked two of the "impractical" ones and both fell on the first correct
# attempt (`exempt_frames_injection_neutered`, `exempt_gate_parity_collapsed`
# are registered mutations now). The v2 deletion took the rest with the
# checks they described. Two remain, and both are safe in the same direction:
# each applies its own in-line edit and asserts the break SHOWS, so if the
# edit stops matching, the "broken" build equals the sound one, the asserted
# difference is zero and the check goes RED.

EXEMPT = {
    "native/mutation_pc_arclength":
        "IS a mutation (pc_arclength's merge removed)",
    "native/mutation_pc_unshare":
        "IS a mutation (pc_unshare bypassed)",
}


# ---- the INVENTORY, pinned --------------------------------------------------
#
# ⚠️ HOW MANY CHECK NAMES EACH RUNNER MUST PRINT. Growth already fails the
# sweep (a new name is UNDECLARED), but SHRINKAGE was silent: filtering one
# check out of every 2d case took the control from 40 names to 39 and the
# sweep still reported `0 UNDECLARED`, exit 0. Moving a number here is a
# deliberate act.
#
# Measured 2026-08-25 from a pristine `git archive HEAD` export, all six
# runners green, AFTER the v2 deletion pass (was 144/97/43/40/37/3 = 361).
EXPECT_CHECKS = {
    "2d": 13,
    "generated": 3,
    "hda": 18,
    "images": 30,
    "native": 19,
    "scene": 39,
    # 7.7, added 2026-08-25 with 10 mutations covering all 14 names.
    # C1's audit added five, 2026-08-25: 19 names, 15 mutations.
    "slice": 19,
}


# ---- the DATED DEBT ---------------------------------------------------------
#
# ⚠️ NOT AN EXEMPTION LIST. An EXEMPTION says "a mutation for this is
# genuinely impractical, and here is the reason". A DEBT ENTRY says "nobody
# has written the mutation yet", which is a different sentence.
#
# 2026-08-25, after the v2 deletion pass: **76 names of 122**, against 32
# mutations and 2 exemptions. It was 283 of 361. The list did not shrink by
# being proven - it shrank because the checks it described were DELETED, and
# what is left falls into four groups, each with its own reason below.

UNPROVEN = {}
UNPROVEN.update(dict.fromkeys((
    "2d/points_wrappers_built_2d_rows",
    "2d/polyfill_appends_its_patches",
    "2d/prims_wrappers_built_2d_rows",
    "2d/ray_executions_per_build_2d_rows",
    "2d/ray_executions_per_build_2d_tower",
    "2d/rows_wrappers_built",
    "2d/verb_executions_per_build_2d_rows",
    "2d/wrapper_reads_2d_rows",
    "hda/plan_is_one_point_per_piece",
    "hda/proxy_beats_full_on_a_curve",
    "hda/proxy_is_interactive",
    "hda/proxy_matches_piece_count",
    "scene/build_out_keeps_upstream_stamps",
    "scene/conform_cache_per_element",
    "scene/conform_cache_per_element_streets",
    "scene/conform_prefetch_hit_rate",
    "scene/conform_prefetch_hit_rate_streets",
    "scene/curve_sample_scaling",
    "scene/path_read_direction_m",
    "scene/path_sample_calls_per_piece",
    "scene/path_sample_calls_per_piece_deformed",
    "scene/points_wrappers_built",
    "scene/points_wrappers_built_streets",
    "scene/polyfill_appends_its_patches",
    "scene/prims_wrappers_built",
    "scene/prims_wrappers_built_deformed",
    "scene/prims_wrappers_built_mitered",
    "scene/ray_executions_per_build",
    "scene/stamp_bulk_peak_kb",
    "scene/stamp_calls_per_piece",
    "scene/stamp_calls_per_piece_deformed",
    "scene/station_share_hit_rate",
    "scene/verb_executions_per_build_mitered",
    "scene/wrapper_reads_mitered",
    "scene/wrapper_reads_streets",
), "a measured COST ceiling. The number IS the assertion and the row "
    "goes red when a build crosses it - but nothing yet MUTATES the "
    "code path to prove the ceiling bites, so it is debt, not proof."))

UNPROVEN.update(dict.fromkeys((
    "images/bank_deg",
    "images/corner_abut_m",
    "images/corner_breach_m",
    "images/double_pillar_m",
    "images/g1_L_bend_parm_face",
    "images/g1_L_miter_parm_face",
    "images/g1_closeup_bend_parm_face",
    "images/g1_closeup_miter_parm_face",
    "images/g1_rect_bend_parm_face",
    "images/g1_rect_miter_parm_face",
    "images/g2_adaptive_parm_face",
    "images/g2_camber_parm_face",
    "images/g2_stepped_parm_face",
    "images/g2_vertical_parm_face",
    "images/image_shows_packed_adaptive",
    "images/image_shows_packed_camber",
    "images/image_shows_packed_closeup_bend",
    "images/image_shows_packed_closeup_miter",
    "images/image_shows_packed_rect_miter",
    "images/image_shows_packed_stepped",
    "images/image_shows_packed_vertical",
    "images/n5_deformed_image_has_geometry",
    "images/n5_deformed_is_native",
    "images/n5_deformed_matches_the_reference",
    "images/partb_curved_is_native",
    "images/partb_curved_matches_the_reference",
    "images/warnings",
), "a gate figure's own row. The gate is the IMAGE plus D194's "
    "drawn-primitive count, and the human at the milestone is what "
    "judges it; only the three `image_shows_packed_*` rows have a "
    "mutation."))

UNPROVEN.update(dict.fromkeys((
    "hda/every_number_has_a_range",
    "hda/every_parm_has_help",
    "hda/two_disclosure_levels",
    "hda/units_in_the_label",
), "artist_ui 6 on the built asset - the page an artist meets first. "
    "An independent verifier once stripped the help, the ranges and "
    "the units and every other check stayed green, which is why these "
    "exist; no mutation is registered for them yet."))

UNPROVEN.update(dict.fromkeys((
    "2d/corner_abut_m",
    "2d/corner_breach_m",
    "2d/packed_pieces",
    "2d/warnings",
    "generated/generated_cases_reach_the_native_chain",
    "hda/evenly_clears_the_corner_adjust_to_end",
    "hda/evenly_clears_the_corner_justify_center",
    "hda/evenly_clears_the_corner_justify_start",
    "native/every_stage_has_a_second_source",
    "native/gate_parity",
), "no mutation yet"))
