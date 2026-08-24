"""THE MUTATION REGISTRY - every polyChain check paired with the edit that
proves it can fail.

    hython tests/polychain/run_mutation_registry.py          # the meta-runner

⚠️ WHY THIS FILE EXISTS.  `ideas/build_retrospective.md` 1: across ~15 build
cycles the dominant recurring failure was **not a bug in the tool - it was a
check that could not fail**.  Roughly twenty distinct instances, one in almost
every cycle, and every single one was found by an INDEPENDENT AUDITOR running
a mutation by hand, never by the agent that wrote the check and never by the
suite.  The suite was green through all twenty.

The retrospective's 4a rule 1 is therefore: *a check is not written until its
mutation has been seen to fail*.  That rule lived in prose, which is exactly
where the twenty defects lived too.  This file is the rule as DATA, and
`run_mutation_registry.py` is the rule as a RUNNER: it exports the repo, breaks
the thing a check guards, runs that check's own runner, and asserts the check
goes RED.

WHAT A REGISTRY ENTRY IS
------------------------
One `M(...)`: an id, the runner that owns the paired checks, the exact source
edits, and `kills` - the check names that MUST go red.  Three properties are
deliberate:

  * **The edit is an exact string swap and the runner asserts it matched
    exactly once.**  A mutation whose target line has moved is a HARD FAIL, not
    a silent no-op.  D208's lesson generalised: an unfailable mutation is worse
    than no mutation, because it reports a green.

  * **`kills` names the check, so the pairing is falsifiable.**  A mutation
    that reddens twenty checks but not the one it is registered against is a
    SURVIVOR of that check, and the run fails.  This is 27.7b m5 as a standing
    rule: the corner bisector reddens 51 checks in `run_scene_checks` and none
    in `run_native_checks`, so it is registered against `scene` and its
    survival of `native` is written down rather than rediscovered.

  * **A CRASH IS NOT A RED.**  21.5 recorded a mutation "caught" by an
    `AssertionError` raised inside a check while the check credited with the
    catch printed PASS.  The meta-runner reports that as ABORT and fails the
    run unless the entry says `expect="abort"` and says why.

WHAT IT DOES NOT COVER, and this is stated rather than implied
-------------------------------------------------------------
`scale_gate.py` prints a table and a failing-ROW count, and
`tests/hda/run_attrib_checks.py` prints a name only when it FAILS - so neither
has an inventory a green run can be asked for, and there is no name to pair a
mutation with.  Both are out of scope by construction, and that is a property
of their output format rather than a judgement about their value.
`gate_images.py` IS in scope: it prints `[PASS] <name>` in the same shape as
the rest (checked, not assumed - an earlier draft of this file asserted the
opposite and was wrong).
"""

# --- the runners the registry can pair against ------------------------------

RUNNERS = {
    "native": "tests/polychain/run_native_checks.py",
    "scene":  "tests/polychain/run_scene_checks.py",
    "2d":     "tests/polychain/run_2d_checks.py",
    "hda":    "tests/polychain/run_hda_checks.py",
    "images": "tests/polychain/gate_images.py",
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


VEX = "polyfactory/vex/polychain/%s"
PY = "polyfactory/scripts/python/polyfactory/polychain/%s"
RIG = "tests/polychain/native.py"
BUILD = "devScripts/create_pf_polychain_hda.py"
IMG = "tests/polychain/gate_images.py"


MUTATIONS = (

    # ---- 13.9 N10, the guard switch: the flip, and its undo ----------------
    M("stage_output_repointed", "native",
      ("output_guard_takes_the_native_chain",
       "output_runs_the_native_chain_inside_the_envelope",
       "native_stages_are_really_native"),
      "27.7b m3 / 21.4 M1 - the exact source-level UNDO of the whole native "
      "flip: `Stage = output` pointed back at the Python reference. It stayed "
      "94 [PASS] / 0 once, because no check read `STAGES` at all (D203).",
      ((RIG,
        '    ("output", "OUT_final", "guard_envelope",',
        '    ("output", "OUT_reference", "kernel",'),)),

    M("guard_never_refuses", "native",
      ("output_guard_parity", "no_case_pays_the_guard_fallback"),
      "27.7b m6 - level 1 admits every build, including the classes the "
      "native chain cannot answer (corners, conform, flatten). The guard "
      "being wrong in the GENEROUS direction is the one that ships a "
      "different fence than yesterday.",
      ((VEX % "pc_envelope.vfl",
        "i@_native_ok = (ok && corners == 0 && ndup == 0",
        "i@_native_ok = (1 || ok && corners == 0 && ndup == 0"),)),

    # ---- D223 / D262, storage as a contract --------------------------------
    M("vex_precision_32", "native",
      ("native_intermediates_are_64bit", "decompose_arclength_parity",
       "trials_irrational_20km_asymmetric"),
      "27.7b m4 / 21.4 M4 - every wrangle dropped to 32-bit. 11.0 measured a "
      "20 km arclength expression returning 0.0 at 32 bits; this is the "
      "mutation that proves the 64-bit declaration is load-bearing rather "
      "than decorative.",
      ((RIG,
        'def wrangle(parent, name, cls, vfl, precision="64"):',
        'def wrangle(parent, name, cls, vfl, precision="32"):'),)),

    M("out_cast_pc_local_fpreal64", "native",
      ("output_guard_parity", "output_snapshot_sees_the_deformed_branch"),
      "D246's STORAGE demonstration, and the reason `_snapshot` grew a "
      "`numericDataType()` dimension: `pc_local` shipped at fpreal64 where "
      "the reference ships fpreal32. `hou.Attrib.dataType()` reads "
      "`attribData.Float` for BOTH, so before D246 this moved NOTHING in the "
      "entire safety net over all 92 cases - which is D223's own rule (an "
      "attribute's storage is part of its contract) unasserted on the OUTPUT "
      "side.",
      ((RIG, 'cast.parm("precision2").set("fpreal32")',
        'cast.parm("precision2").set("fpreal64")'),),
      note="⚠️ NOT `numcasts` 3 -> 1, which is what this entry tried first: "
           "the build script goes on to set `class2`/`class3` unconditionally, "
           "so the rebuild RAISES and the run reports STALE rather than red. "
           "A mutation has to leave the thing under test buildable."),

    M("out_cast_ints_int64", "native",
      ("output_guard_parity",),
      "27.7b m10 / D262 - the OUTPUT's integer storage. A 64-bit wrangle "
      "writes `i@` at int64 and `place.build` declares the same attributes at "
      "int32, so six prim ints plus every `pc_warn_*` shipped at twice the "
      "reference's storage on EVERY admitted build, over 29 of 93 cases, with "
      "`output_guard_parity` printing 'identical' throughout.",
      ((RIG, 'cast.parm("precision3").set("int32")',
        'cast.parm("precision3").set("int64")'),)),

    # ---- D246's other half: point-attribute VALUES -------------------------
    M("pc_local_scaled", "native",
      ("output_snapshot_sees_the_deformed_branch", "output_guard_parity"),
      "D246's VALUES demonstration #1. `_snapshot` recorded point attributes "
      "by NAME ONLY, so `pc_local` - the one output attribute 13.9 N5 added - "
      "was compared by nothing at all. Scaling it 1.5x is a 100 %-of-the-"
      "build divergence that the whole net reported as `identical`.",
      ((VEX % "pc_deform.vfl",
        "v@pc_local = local;", "v@pc_local = local * 1.5;"),)),

    M("pc_local_zeroed", "native",
      ("output_snapshot_sees_the_deformed_branch", "output_guard_parity"),
      "D246's VALUES demonstration #2, and the harsher of the two: the "
      "attribute is not merely wrong, it is GONE, and by name it is still "
      "there. Registered separately from the scale because a check that only "
      "sees magnitude changes would pass one and fail the other.",
      ((VEX % "pc_deform.vfl",
        "v@pc_local = local;", "v@pc_local = set(0.0, 0.0, 0.0);"),)),

    # ---- D247, the tolerance that was disguised as exactness ---------------
    M("conform_drop_biased", "native",
      ("conform_drop_is_portable_to_vex",),
      "13.9 N6's deciding experiment, biased by 1e-5 m along the drop axis. "
      "The check advertised a 1e-12 m ceiling while applying `f32()` to BOTH "
      "sides before subtracting, so its real tolerance was half a float32 "
      "ULP - 0.98 mm at 20 km - and the row that decides N6 printed "
      "`0.000e+00` on a genuine 9.375e-04 m disagreement (D247).",
      ((RIG.replace("native.py", "run_native_checks.py"),
        "if (hit) { float t = dot(best - q, a); best = q + a * t; }",
        "if (hit) { float t = dot(best - q, a); "
        "best = q + a * t + a * 1e-5; }"),),
      rebuild=False),

    # ---- D241 / D257, the array-and-dict subject ---------------------------
    M("array_subject_test_equals_3", "native",
      ("plan_fixture_parity",),
      "27.7b m8 - `t >= 3` back to `t == 3`. `primattribtype` returns 3 only "
      "for an INT array, so a FLOAT array, a STRING array and a DICT were all "
      "read as scalars: 12 gate prims natively against the reference's 10 "
      "panels, admitted by the guard, no warning on either side.",
      ((VEX % "pc_sections.vfl",
        "if (t >= 3 || primattribsize(0, name) != 1)",
        "if (t == 3 || primattribsize(0, name) != 1)"),)),

    # ---- D242 / D265, the markerData slot ----------------------------------
    M("marker_data_cross_type_read", "native",
      ("guard_marker_data_types", "plan_fixture_parity"),
      "27.7b m9, THE SURVIVOR THAT MATTERED MOST: reverting the "
      "`!unreadable:` branch left the suite 144 [PASS] / 0, i.e. a guard hole "
      "was closed by a fix nothing in the tree could see. D265 is the rule "
      "that came out of it - every hole closed in a cycle must be re-opened "
      "AT SOURCE and the suite must go red, or the closure is a comment.",
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
      "the order key left the suite 136 [PASS] / 0, because Houdini's `sort` "
      "happens to be STABLE and equal keys kept the emission order. The term "
      "exists to make the key TOTAL - so that the answer does not depend on "
      "how ties break - and `piece_order_key_is_total` asserts that directly.",
      ((VEX % "pc_piece_key.vfl",
        "f@_pkeyp = (float)i@_pkey0 * (float)PC_PIECE_SPAN "
        "+ (float)i@_srcpt;",
        "f@_pkeyp = (float)i@_pkey0 * (float)PC_PIECE_SPAN;"),)),

    # ---- 4.3 corners: killed by the SCENE suite, survives the native one ---
    M("corner_bisector_negated", "scene",
      ("corner_abut_m", "corner_outside_m", "corner_breach_m",
       "corner_face_mate_m"),
      "21.4 M5 / 27.7b m5 - the corner bisector taken as the INCOMING TANGENT "
      "instead of `unit(tin + tout)`. ⚠️ REGISTERED AGAINST `scene` ON "
      "PURPOSE: it is a SURVIVOR of `run_native_checks` (145 [PASS] / 0), "
      "because 4.3 is N8, level 1 refuses every cornered build and both sides "
      "of the parity go through the same `corner.py`. A mutation sweep that "
      "runs only the native runner cannot judge anything the guard refuses.",
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
      note="⚠️ WHAT THIS MEASURED, and it is a blind spot worth writing down: "
           "`conform_drape_m` and `conform_contact_m` DO NOT SEE IT. A "
           "permuted axis makes the cast MISS, and a missed drop leaves the "
           "run unmoved (D53), so the two checks that carry `drape` and "
           "`contact` in their names read 0.0 and pass. What sees it is the "
           "miss count and the warning - which is why those are the paired "
           "names here and not the ones a reader would guess."),

    M("conform_drop_biased", "scene",
      ("conform_parity", "ray_verb_semantics"),
      "The drape displaced 5 cm along the surface normal in `Surface.drop` - "
      "the REFERENCE half of 11.2 P5's pair. `drop_many` is what the build "
      "runs and `drop` is what proves it right, so this is the mutation that "
      "proves the pair is a comparison and not two readings of one path.",
      ((PY % "conform.py",
        "        return (best[0], nrm, True)",
        "        return ((best[0][0], best[0][1] + 0.05, best[0][2]), "
        "nrm, True)"),),
      rebuild=False),

    # ---- 3.4's stamp: two writers, one description -------------------------
    M("stamp_bulk_u_offset", "scene",
      ("stamp_parity",),
      "D102's bulk writer drifted from the per-prim reference by 1e-6 on "
      "`pc_u`, on every prim but the first. `_stamp_bulk` is what the build "
      "runs and `_stamp` is the one-prim reference nothing else cooks, so "
      "without this mutation `stamp_parity` could be comparing the same list "
      "with itself.",
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
      "D75's budget widened by 1e6, so nothing ever unpacks. The pair "
      "`ALL_PACKED` / `NONE_PACKED` in `run_scene_checks` exists precisely "
      "because a build can pass every geometry check by keeping everything "
      "packed - this is the mutation that proves the NONE_PACKED half bites.",
      ((PY % "place.py",
        "        return True                              # D75, D87, D100, D104",
        "        return True and False                    # D75, D87, D100, D104"),),
      rebuild=False),

    M("deviates_branch_disabled", "scene",
      ("packed_true_dev_m", "deform_gate_m", "warnings"),
      "cycle 6 M2 - a genuinely deformed piece stays packed because the "
      "`deviates` branch is gone. 4.5's dead-straight spline over a ridge has "
      "no interior vertex, so without this branch a bendable rail crosses the "
      "hill as one rigid chord with its two ends on the ground. "
      "⚠️ MEASURED: `packed_pieces` DOES NOT SEE IT. It is a recorded value "
      "on 91 of the 93 cases and an assertion only on the two hand-listed "
      "sets `ALL_PACKED` / `NONE_PACKED` - and not one case in either of them "
      "reaches the `deviates` branch, so the count changes and nothing "
      "complains. What catches it is D87's own `packed_true_dev_m` (the "
      "deviation a piece that STAYED packed really suffers) and the gate "
      "margin. That is the difference between a value and an assertion, "
      "measured rather than argued.",
      ((PY % "place.py",
        '    if zmode != "stepped" and getattr(path, "deviates", None) '
        "is not None             and path.deviates(sa, sb, tol, "
        "fracs=proto.fracs):",
        '    if False and zmode != "stepped" and getattr(path, "deviates", '
        "None) is not None             and path.deviates(sa, sb, tol, "
        "fracs=proto.fracs):"),),
      rebuild=False),

    # ---- D210: a moved baselined value fails the run ------------------------
    M("scene_baseline_perturbed", "scene",
      (BASELINE_MOVED,),
      "D210, live rather than argued: `run_scene_checks` used to PRINT a "
      "moved baseline value and still exit 0, so every 'no baseline movement' "
      "claim in this build rested on that exit code. The mutation perturbs a "
      "recorded value and the run must report movement AND exit non-zero.",
      (("tests/polychain/baseline.json", None, None),),
      rebuild=False),

    # ---- 7.3.3 / P2-3V incident 1: the check that could not fail -----------
    M("2d_clip_stamp_zeroed", "2d",
      ("clip_stamp",),
      "P2-3V incident 1, the FIRST unfailable check this project recorded: "
      "`clip_stamp` was `ok = area or n == 0`, so on an area build - the only "
      "kind where the stamp can legitimately be 1, and the only kind it was "
      "written for - `ok` was True whatever the value was. Zeroing the stamp "
      "left the whole suite green with one baseline line to show for it. The "
      "assertion is the TRANSFER now, and this is the mutation it owes its "
      "existence to.",
      ((PY % "plan.py",
        "        p.clipped = int(clipped)",
        "        p.clipped = 0"),),
      rebuild=False,
      note="⚠️ IT HAS TO BE THE TRANSFER'S DESTINATION, NOT ITS SOURCE. "
           "Zeroing `array2d`'s own `attrs['pc_clipped']` instead leaves the "
           "check GREEN, because the row curve is where `clip_stamp` reads "
           "its expectation from - the mutation and the oracle would move "
           "together. D208's rule, met head-on while writing this entry: a "
           "check may not read the same declaration its mutation edits."),

    # ---- the artist face: the four input ports -----------------------------
    M("kit_input_unplugged", "hda",
      ("input2_is_the_kit",),
      "THE KIT PORT WIRED TO NOTHING inside the asset - the bluntest possible "
      "failure of input 2. ⚠️ IT REDDENS NOTHING AT ALL: 31 [PASS] / 0 with "
      "the artist's kit port dead. Thirty of the thirty-one legitimately "
      "cannot tell (they wire no kit and 3.4's `kit_starter` supplies the "
      "same starter kit either way); the one written to tell - "
      "`input2_is_the_kit` - CANNOT FAIL. This entry stays RED until that is "
      "fixed, which is the meta-runner doing its job rather than a bug in it.",
      ((BUILD,
        "    _node.setInput(0, net.indirectInputs()[_i])",
        "    _node.setInput(0, None if _i == 1 "
        "else net.indirectInputs()[_i])"),),
      note="⚠️ THE MECHANISM, read out of the source rather than guessed: "
           "`Kit.resolve(name)` ends `return [stand_in(name)]`, so a module "
           "the kit cannot supply is replaced by a blank box CARRYING THE "
           "REQUESTED NAME. `input2_is_the_kit` renames panel -> plank in the "
           "kit it wires and then asserts `plank` appears in `pc_module` - "
           "which is the name the STYLE asked for, stamped by the stand-in "
           "too. Assert truth, not presence (retrospective 4a rule 4): the "
           "fix is to assert the renamed module's own GEOMETRY. D266; "
           "`run_hda_checks.py` is not this cycle's file to edit."),

    M("hda_input_ports_swapped", "hda",
      ("payload_overrides_modules", "payload_matches_kernel",
       "parms_inert_under_payload_native"),
      "2d 3 - no review lens ever looked at the built asset's metadata, and "
      "Hannes found the missing TAB-menu entry and the unlabelled ports "
      "himself. The kit and the style ports swapped is what an artist meets "
      "first, and it is invisible to every geometry check in the tree.",
      ((BUILD,
        "    _node.setInput(0, net.indirectInputs()[_i])",
        "    _node.setInput(0, net.indirectInputs()"
        "[{0: 0, 1: 2, 2: 1, 3: 3}[_i]])"),),
      note="⚠️ IT HAS TO SWAP THE WIRING, NOT THE NAMES. Swapping the two "
           "entries in `IN_NAMES` reddens NOTHING - measured - because every "
           "consumer downstream takes `ins[i]` by INDEX, so the mutation only "
           "renames two nulls and the asset behaves identically. A source "
           "edit is not a mutation until something moves."),

    # ---- D266: the shipped defaults that built TWO pillars at a corner ----
    M("default_slot_composed_again", "hda",
      ("starter_fence_one_pillar_miter",),
      "D266 - the exact source-level UNDO of this cycle's fix. The shipped "
      "`Repeating Pieces` default was `post panel`, so every section opened "
      "with a post and a mitered corner shipped the corner assembly's 1.30 m "
      "pillar with the run's own 1.20 m post butted against it at EXACTLY "
      "0.0 m. Hannes counted the two pillars in the viewport; 3 600 numeric "
      "checks did not, because `no_gaps_or_overlaps`, `corner_abut` and "
      "`corner_seam` are CLOSURE checks and a double pillar is perfectly "
      "closed. Applying this reddens `starter_fence_one_pillar_miter` at "
      "0.111698 m - the corner post's own footprint overshot by the post.",
      ((BUILD,
        'ptg.append(_slot("slot_default", "Repeating Pieces", "panel",',
        'ptg.append(_slot("slot_default", "Repeating Pieces", "post panel",'),
       (BUILD,
        'ptg.append(_slot("slot_evenly", "Evenly Spaced Piece", "post",',
        'ptg.append(_slot("slot_evenly", "Evenly Spaced Piece", "",')),
      note="⚠️ IT REDDENS ONLY THE `miter` ROW, and that is correct rather "
           "than a weakness in the pairing: `bend` mode places no corner "
           "assembly at all (D36 welds the ring), so there is no reserved "
           "pillar for the fill to double and `starter_fence_one_pillar_bend` "
           "stays 0.0 on the mutated build - measured. It also reddens "
           "NOTHING in `run_scene_checks`, because every scene case builds "
           "its style in Python and none of them ever expressed this "
           "composition: that gap is why the defect shipped."),

    M("evenly_doubles_the_fill", "hda",
      ("starter_fence_one_pillar_bend", "starter_fence_one_pillar_miter"),
      "D267's OTHER direction, and the row that would otherwise be "
      "unfailable. `starter_fence_one_pillar_bend` cooks a CLOSED rectangle, "
      "where bend mode places no corner assembly (D36 welds the ring) and a "
      "closed run has no start/end cap - so no reserved slot exists for the "
      "fill to double and `default_slot_composed_again` leaves that row at "
      "0.0 by construction. This mutation makes the FILL the rhythm element "
      "as well as the `evenly` slot, so every evenly post stands against a "
      "run of default posts: 11.975 m on bend and 12.0 m on miter, measured. "
      "It is a real composition defect, not a contrivance - it is what an "
      "artist does the first time they type `post` into Repeating Pieces "
      "without clearing Evenly Spaced Piece.",
      ((BUILD,
        'ptg.append(_slot("slot_default", "Repeating Pieces", "panel",',
        'ptg.append(_slot("slot_default", "Repeating Pieces", "post",'),)),

    M("corner_style_composed_default", "scene",
      ("double_pillar_m",),
      "D266's other half - THE FIXTURE GAP, as a mutation. `cases.corner_style` "
      "fills the run with `panel` alone, so the suite's 20-odd corner cases "
      "never expressed the one composition the SHIPPED PARM DEFAULTS did "
      "(`post panel` in sequence). That is why 3 600 numeric checks were green "
      "on a fence with two pillars at every corner. Composing the fixture the "
      "way the page used to reddens `double_pillar_m` on 19 cases - "
      "V_rect_miter at 0.111698 m, the exact number Hannes measured.",
      (("tests/polychain/cases.py",
        '    return Style("corner", 1, 9, rules=[',
        '    return Style("corner", 1, 9, rules=[\n'
        '        Rule("default", "sequence", ["post", "panel"]),'),),
      rebuild=False,
      note="⚠️ IT MUTATES THE FIXTURE, NOT THE KERNEL, and that is the point: "
           "the kernel was never wrong. The defect was a COMPOSITION shipped "
           "on the parameter page and a fixture set that could not reach it. "
           "The kernel-side pair for the same check is "
           "`default_slot_composed_again` on the `hda` runner."),

    # ---- D194: verify an image contains its subject ------------------------
    M("gate_image_not_unpacked", "images",
      ("n5_deformed_image_has_geometry",),
      "D194, at source - `unpack` made a no-op. A PACKED PRIM HAS ONE VERTEX, "
      "so a wireframe drawn straight off a 4.6-instanced polyChain output is "
      "EMPTY: PC-G1's committed gate image was 188 segments of a "
      "3 388-segment fence, and four gates were reported PASSED on it. The "
      "check that exists because of that has to be the one that reddens.",
      ((IMG,
        'def unpack(geo):\n    """A flat copy with every PACKED prim '
        "expanded, for the rasteriser.",
        'def unpack(geo):\n    return geo    # the D194 mutation\n    """A '
        "flat copy with every PACKED prim expanded, for the rasteriser."),),
      rebuild=False),

    M("2d_baseline_perturbed", "2d",
      (BASELINE_MOVED,),
      "The same rule on the OTHER runner that carries a baseline. "
      "`run_2d_checks` had its own COPY of the advisory exit rule and it drifted; "
      "it exits through `run_scene_checks.exit_code` now, and this is the "
      "mutation that proves the shared rule is reached from here too.",
      (("tests/polychain/baseline_2d.json", None, None),),
      rebuild=False),
)


# --- the coverage meta-check -------------------------------------------------
#
# Every check name a runner prints must be in exactly one of three states:
#   1. PROVEN   - some registered mutation was SEEN to redden it;
#   2. EXEMPT   - a mutation is genuinely impractical or the check IS a
#                 mutation, one line saying which;
#   3. UNPROVEN - a declared, dated debt entry.
# A name in none of the three FAILS the meta-runner, so a check cannot be added
# without a decision about how it can fail.

EXEMPT = {
    # ---- the checks that ARE mutations. Each one breaks something and
    # asserts the break shows; its own liveness is guarded by the paired
    # `*_target_exists` / `*_baseline` row beside it, which is the second
    # source D208 asks for.
    "mutation_anchor_fill_copies_the_plan": "IS a mutation (guard anchor fill)",
    "mutation_copy_pivot": "IS a mutation (copytopoints pivot)",
    "mutation_copy_useidattrib": "IS a mutation (copytopoints id attrib)",
    "mutation_deform_refusals": "IS a mutation (pc_deform_gate refusals)",
    "mutation_every_wrangle_ceiling_bites": "IS a mutation (per-wrangle cost)",
    "mutation_every_wrangle_ceiling_bites_deformed":
        "IS a mutation (per-wrangle cost, deformed branch)",
    "mutation_gate_unplugged": "IS a mutation (gate rewire)",
    "mutation_guard_envelope": "IS a mutation (guard envelope rewire)",
    "mutation_output_unplugged": "IS a mutation (output rewire)",
    "mutation_pc_arclength": "IS a mutation (pc_arclength source)",
    "mutation_pc_deform_gate": "IS a mutation (curvature tolerance)",
    "mutation_pc_finalize": "IS a mutation (pc_finalize bypassed)",
    "mutation_pc_finalize_debatched": "IS a mutation (pc_finalize de-batched)",
    "mutation_pc_frames": "IS a mutation (pc_frames VEX)",
    "mutation_pc_kit_id": "IS a mutation (pc_kit_id source)",
    "mutation_pc_plan_solve_string_arrays": "IS a mutation (solve columns)",
    "mutation_pc_sample_array_reads": "IS a mutation (sampler array reads)",
    "mutation_pc_sections_a": "IS a mutation (pc_sections source)",
    "mutation_pc_sections_t": "IS a mutation (pc_sections source)",
    "mutation_pc_splitmix_shift": "IS a mutation (seed chain)",
    "mutation_pc_stamp_debatched": "IS a mutation (pc_stamp de-batched)",
    "mutation_pc_unshare": "IS a mutation (pc_unshare removed)",
    "mutation_place_native_unplugged": "IS a mutation (place rewire)",
    "mutation_plan_adaptive_threshold": "IS a mutation (plan threshold)",
    "mutation_plan_clean_bypassed": "IS a mutation (pc_plan_clean bypassed)",
    "mutation_plan_emit_count": "IS a mutation (emit count)",
    "mutation_plan_native_unplugged": "IS a mutation (plan rewire)",
    "mutation_plan_pool_per_piece": "IS a mutation (pool hoist)",
    "mutation_plan_precision_32": "IS a mutation (solve precision)",
    "mutation_reference_unplugged": "IS a mutation (reference rewire)",
    "mutation_spline_attr_types": "IS a mutation (spline attr storage)",
    "mutation_stage_labels_claim_native": "IS a mutation (stage labels)",
    "mutation_stage_wiring": "IS a mutation (four stage rewires)",
    "seed_mutation_target_exists":
        "IS the liveness guard for `mutation_pc_splitmix_shift`",
    "place_mutation_baseline":
        "IS the un-mutated control for `place_mutation`",
    "plan_mutation_baseline":
        "IS the un-mutated control for `plan_mutation`",
    "plan_mutation_marker_baseline":
        "IS the un-mutated control for `plan_mutation`'s marker case",
    "gate_parity_sees_both_answers":
        "IS the vacuity guard for `gate_parity` (both answers occur)",
}

# Dated debt. Each line says what it would take. This list going up is a
# regression; it is printed with its count on every run.
UNPROVEN = {}
