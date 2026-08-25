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
    # v2's differential oracle over GENERATED input, on the shipped asset.
    # It prints exactly two names, deliberately: seed numbers are diagnostics,
    # not check names (a sweep that moves its range would silently retire and
    # invent hundreds of them).
    "generated": "tests/polychain/run_generated.py",
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
IMG = "tests/polychain/gate_images.py"


MUTATIONS = (

    # ---- v2: the generated differential, on the SHIPPED asset -------------
    M("generated_pc_local_scaled", "generated",
      ("generated_output_matches_the_reference",),
      "The v2 oracle's own proof. `pc_deform` writes `v@pc_local = local`; "
      "scaling it 1.5x is a divergence on the NATIVE side of every deformed "
      "build, and `run_generated` compares the shipped node's `Stage = "
      "output` against its `Stage = reference` over generated scenes. The "
      "same edit is `pc_local_scaled` for `native`; registered twice on "
      "purpose, because a mutation is evidence about the pairing it was "
      "examined against and these are two different instruments.",
      ((VEX % "pc_deform.vfl",
        "v@pc_local = local;", "v@pc_local = local * 1.5;"),)),

    M("generated_known_pattern_broken", "generated",
      ("known_divergences_still_occur",
       "generated_output_matches_the_reference"),
      "The other half of a KNOWN divergence: an entry that stops occurring "
      "has either been fixed (delete it deliberately) or stopped being "
      "REACHED, which is the fixture-blindness class the generator exists to "
      "attack. Editing the pattern to one that cannot match must redden BOTH "
      "names - the five pinned seeds lose their exemption and the entry goes "
      "unreached. Measured live before it was registered: 5 red, `0 of 1 "
      "reached`, exit 1.",
      ((GEN, "\".prim: 'pc_module' only on the RIGHT\"",
        "\".prim: 'pc_NEVER' only on the RIGHT\""),),
      rebuild=False),

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

    M("conform_drop_biased_py", "scene",
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

    # ---- 4.2, the fitting solve: one piece too few -------------------------
    M("adaptive_rounds_down", "scene",
      (BASELINE_MOVED, "warnings"),
      "4.2's adaptive rounding, one piece the other way: D14's 'a remainder "
      "over `adaptive_pct` earns another unit' deleted. It is the broadest "
      "cheap mutation in the registry - it changes how many pieces a run "
      "gets, which is the first number an artist reads - and it is here to "
      "prove the fill checks are assertions and not a recording of whatever "
      "the solve happened to do. ⚠️ AND THEY ARE NOT. Measured: "
      "`element_count`, `exact_fill_m`, `max_gap_m` and `section_coverage_m` "
      "ALL STAY GREEN with a piece removed from every adaptive run, because "
      "adaptive mode then stretches the survivors and the fill is still "
      "exact. The whole change shows up as 224 MOVED BASELINE VALUES and one "
      "warning. So on this runner the guard against a re-fit is D210's "
      "baseline diff, NOT the geometry checks - which is why the reserved "
      "name is the paired one here. Third instance of the same shape in this "
      "cycle (see `deviates_branch_disabled`): a name that reads like an "
      "assertion is a recorded value on most cases.",
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
      "failure of input 2. ⚠️ IT USED TO REDDEN NOTHING AT ALL: 31 [PASS] / 0 "
      "with the artist's kit port dead. Thirty of the thirty-one legitimately "
      "cannot tell (they wire no kit and 3.4's `kit_starter` supplies the "
      "same starter kit either way); the one written to tell - "
      "`input2_is_the_kit` - COULD NOT FAIL, because it asserted the module "
      "NAME and `Kit.resolve` ends `return [stand_in(name)]`: a module the "
      "kit cannot supply becomes a blank 1 x 1 x 1 box carrying the requested "
      "name. D272 makes it assert the renamed module's own GEOMETRY off "
      "`pc_local` (2.00 x 0.90 x 0.06 m, the panel, against the stand-in's "
      "1 x 1 x 1), and this entry reddens it.",
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
           "too. Assert truth, not presence (retrospective 4a rule 4). CLOSED "
           "at D272, by the cycle that was already editing `run_hda_checks.py` "
           "for D269 - the survivor was found by running the sweep rather "
           "than by reading, which is the meta-runner doing exactly its job."),

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
        '    rules = [\n        Rule("default", "first", ["panel"]),',
        '    rules = [\n        Rule("default", "sequence", ["post", "panel"]),'),),
      rebuild=False,
      note="⚠️ IT MUTATES THE FIXTURE, NOT THE KERNEL, and that is the point: "
           "the kernel was never wrong. The defect was a COMPOSITION shipped "
           "on the parameter page and a fixture set that could not reach it. "
           "The kernel-side pair for the same check is "
           "`default_slot_composed_again` on the `hda` runner. ⚠️ AND ITS "
           "ANCHOR MOVED AT D269, when `corner_style` grew an optional "
           "`evenly` rule: the registry HARD FAILS on an edit whose target "
           "has moved rather than reporting a silent green, which is how "
           "that was noticed. It now also reddens `EH_block_corner_evenly`, "
           "whose corner module is a 1.20 x 1.30 m BLOCK - before D270 that "
           "same build measured 0.0 and PASSED, because the aspect rule "
           "gated ENTRY and a block is not an upright."),

    # ---- D269: a corner RESERVES space, and the guard has to know it -------
    M("evenly_ignores_the_corner_reserve", "hda",
      ("evenly_clears_the_corner_justify_end",),
      "D269, at source - the corner's reservation stops guarding the evenly "
      "anchors and only a CAP does, which is what shipped. D15 sheds half a "
      "module at a guarded end so the centred piece cannot grow through it, "
      "but `head`/`tail` are built from `section.start_cap`/`end_cap` and "
      "D18 makes both FALSE at a corner: a corner reserves its space through "
      "`trim`, not through a cap, so the shed never ran there. What kept the "
      "shipped defaults clean was `justify='center'`, whose lead is at least "
      "half a spacing - an accident, not a guarantee, and the parm help "
      "claimed the guarantee. ONE Advanced parm reached the defect the whole "
      "of section 28 exists to fix: measured on the shipped asset, "
      "`Evenly Justify = From the end` on a 12.161 m leg drove the evenly "
      "post 0.061 m INTO the mitered corner post, and `Adjust to End` did it "
      "at every corner of every leg (0.06 m on 4.66 / 6.66 / 8.66 / 12.66 / "
      "12.70 / 12.90 m legs, 0.0 with the parm off).",
      ((PY % "plan.py",
        "        guard_a = head is not None or float(trim[0]) > EPS\n"
        "        guard_b = tail is not None or float(trim[1]) > EPS",
        "        guard_a = head is not None\n"
        "        guard_b = tail is not None"),),
      rebuild=False,
      note="⚠️ THE LEG LENGTH IS THE MUTATION'S OTHER HALF. On the 12 x 8 m "
           "rectangle every justification measures 0.0 BOTH BEFORE AND AFTER "
           "the fix, because 12 m is an exact multiple of the 2 m spacing and "
           "the justify leftover never approaches zero - so a fixture on the "
           "round number is green on the broken build and this mutation would "
           "be a SURVIVOR. `evenly_clears_the_corner_*` and the scene cases "
           "EB/EC run 12.161 m for that reason. It also reddens "
           "`double_pillar_m` in `run_scene_checks` (EB, EC) and moves those "
           "cases' baselines; `justify_start` and `justify_center` stay green "
           "on the mutated build, which is the shape of the defect rather "
           "than a weak pairing."),

    # ---- D194: verify an image contains its subject ------------------------
    M("gate_image_not_unpacked", "images",
      ("image_shows_packed_L_bend", "image_shows_packed_L_miter",
       "image_shows_packed_rect_bend"),
      "D194, at source - `unpack` made a no-op. A PACKED PRIM HAS ONE VERTEX, "
      "so a wireframe drawn straight off a 4.6-instanced polyChain output is "
      "EMPTY: PC-G1's committed gate image was 188 segments of a "
      "3 388-segment fence, and four gates were reported PASSED on it. The "
      "check that exists because of that has to be the one that reddens. "
      "⚠️ MEASURED, and the pairing was wrong at first: it does NOT redden "
      "`n5_deformed_image_has_geometry`, because 13.9 N5's crop is the "
      "DEFORMED branch and a deformed piece is a polygon soup, not a packed "
      "prim - unpacking it is the identity. The three rows that see it are "
      "the packed ones, which is the case D194 actually happened on.",
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
      "worst relative error falls back to the FMA floor. It is the exemption "
      "list's own reasoning, made runnable: a mutation-check whose injection "
      "has died fails in the SAFE direction, and this is the evidence for "
      "that sentence rather than the sentence alone.",
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
      "answer instead of two. ⚠️ AND THE FIRST ATTEMPT AT THIS SURVIVED, "
      "correctly - killing ONE of `_needs_deform`'s several deform paths "
      "left the others still producing both answers, so the guard was right "
      "and the mutation was wrong. The mutation has to collapse the whole "
      "function, which is what the check claims to detect.",
      ((PY % "place.py",
        '    """4.4 + the streets float32 lesson: rebuild ONLY when it '
        'changes something."""\n'
        "    if placement.slice_t is not None or placement.cuts:",
        '    """4.4 + the streets float32 lesson: rebuild ONLY when it '
        'changes something."""\n'
        "    return False            # the mutation: one answer, not two\n"
        "    if placement.slice_t is not None or placement.cuts:"),),
      rebuild=False),
)

# ⚠️ IDS ARE UNIQUE, ASSERTED HERE. Two entries shared the id
# `conform_drop_biased` for one sweep - one on `native`, one on `scene` - and
# the resumable state file is keyed by id, so the second silently REPLAYED the
# first's verdict and was never run. A registry whose own keys collide is the
# defect it exists to catch, one level up.
_ids = [m.id for m in MUTATIONS]
assert len(_ids) == len(set(_ids)),     "duplicate mutation id: %s" % sorted(set(i for i in _ids
                                             if _ids.count(i) > 1))


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
    # asserts the break SHOWS - a difference, a flip, a moved number - so a
    # mutation-of-the-mutation fails in the SAFE direction: if the in-line
    # edit stops matching, the "broken" build equals the sound one, the
    # asserted difference is zero and the check goes RED. That, and not a
    # paired liveness row, is what these exemptions rest on.
    #
    # ⚠️ THIS SENTENCE USED TO CLAIM SOMETHING FALSE. It said each row's
    # liveness was guarded by the paired `*_target_exists` / `*_baseline` row
    # beside it - but exactly FOUR such rows exist against 33 `mutation_*`
    # exemptions (they are listed at the end and they are real; they just do
    # not cover the other 29). An auditor then wrote two of the "impractical"
    # mutations anyway, both RED on the first correct attempt, and both are
    # registered above: `exempt_frames_injection_neutered` neuters an
    # injection and `exempt_gate_parity_collapsed` collapses the reference to
    # one answer. Their two names are GONE from this list as a result. The
    # safe-direction argument is now evidence, not assertion - and the
    # remaining rows are exempt on it, not on a guard they never had.
    #
    # ⚠️ AND EXEMPT IS A CLAIM, WHICH MEANS IT IS A TARGET. Both exemptions
    # attacked in this audit fell. Attack them.
    "native/mutation_anchor_fill_copies_the_plan": "IS a mutation (guard anchor fill)",
    "native/mutation_copy_pivot": "IS a mutation (copytopoints pivot)",
    "native/mutation_copy_useidattrib": "IS a mutation (copytopoints id attrib)",
    "native/mutation_deform_refusals": "IS a mutation (pc_deform_gate refusals)",
    "native/mutation_every_wrangle_ceiling_bites": "IS a mutation (per-wrangle cost)",
    "native/mutation_every_wrangle_ceiling_bites_deformed":
        "IS a mutation (per-wrangle cost, deformed branch)",
    "native/mutation_gate_unplugged": "IS a mutation (gate rewire)",
    "native/mutation_guard_envelope": "IS a mutation (guard envelope rewire)",
    "native/mutation_output_unplugged": "IS a mutation (output rewire)",
    "native/mutation_pc_arclength": "IS a mutation (pc_arclength source)",
    "native/mutation_pc_deform_gate": "IS a mutation (curvature tolerance)",
    "native/mutation_pc_finalize": "IS a mutation (pc_finalize bypassed)",
    "native/mutation_pc_finalize_debatched": "IS a mutation (pc_finalize de-batched)",
    "native/mutation_pc_kit_id": "IS a mutation (pc_kit_id source)",
    "native/mutation_pc_plan_solve_string_arrays": "IS a mutation (solve columns)",
    "native/mutation_pc_sample_array_reads": "IS a mutation (sampler array reads)",
    "native/mutation_pc_sections_a": "IS a mutation (pc_sections source)",
    "native/mutation_pc_sections_t": "IS a mutation (pc_sections source)",
    "native/mutation_pc_splitmix_shift": "IS a mutation (seed chain)",
    "native/mutation_pc_stamp_debatched": "IS a mutation (pc_stamp de-batched)",
    "native/mutation_pc_unshare": "IS a mutation (pc_unshare removed)",
    "native/mutation_place_native_unplugged": "IS a mutation (place rewire)",
    "native/mutation_plan_adaptive_threshold": "IS a mutation (plan threshold)",
    "native/mutation_plan_clean_bypassed": "IS a mutation (pc_plan_clean bypassed)",
    "native/mutation_plan_emit_count": "IS a mutation (emit count)",
    "native/mutation_plan_native_unplugged": "IS a mutation (plan rewire)",
    "native/mutation_plan_pool_per_piece": "IS a mutation (pool hoist)",
    "native/mutation_plan_precision_32": "IS a mutation (solve precision)",
    "native/mutation_reference_unplugged": "IS a mutation (reference rewire)",
    "native/mutation_spline_attr_types": "IS a mutation (spline attr storage)",
    "native/mutation_stage_labels_claim_native": "IS a mutation (stage labels)",
    "native/mutation_stage_wiring": "IS a mutation (four stage rewires)",
    "native/seed_mutation_target_exists":
        "IS the liveness guard for `mutation_pc_splitmix_shift`",
    "native/place_mutation_baseline":
        "IS the un-mutated control for `place_mutation`",
    "native/plan_mutation_baseline":
        "IS the un-mutated control for `plan_mutation`",
    "native/plan_mutation_marker_baseline":
        "IS the un-mutated control for `plan_mutation`'s marker case",
}

# ---- the INVENTORY, pinned ---------------------------------------------------
#
# ⚠️ HOW MANY CHECK NAMES EACH RUNNER MUST PRINT.  Growth already fails the
# sweep (a new name is UNDECLARED), but SHRINKAGE was silent: filtering one
# check out of every 2d case took the control from 40 names to 39 and the
# sweep still reported `0 UNDECLARED`, exit 0, with the vanished check still
# sitting in the debt list describing something that no longer existed.  A
# check that stops being emitted is exactly retrospective P2 - "the check is
# well written; nothing ever runs it" - and it may not leave in silence.
#
# Measured 2026-08-24 from a pristine `git archive HEAD` export, all five
# runners green.  Moving a number here is a deliberate act, like every other
# baseline in this project.
EXPECT_CHECKS = {
    "native": 144,
    "scene": 97,
    "images": 43,
    "2d": 40,
    "hda": 37,
    "generated": 2,
}

# ---- the DATED DEBT ---------------------------------------------------------
#
# ⚠️ THIS IS NOT AN EXEMPTION LIST AND IT IS NOT CALLED ONE.  An EXEMPTION says
# "a mutation for this is genuinely impractical, and here is the one-line
# reason".  A DEBT ENTRY says "nobody has written the mutation yet", which is a
# different sentence and deserves a different word - writing 283 fake reasons
# to make the runner green would be the exact move this whole file exists to
# stop.
#
# ⚠️ THE COUNT IS `len(UNPROVEN)` AND NOTHING ELSE, because it was three
# different numbers in three places for one list.  2026-08-24, after the audit
# of the instrument: **283 names of 361, against 30 mutations and 36
# exemptions** (42 declared runner/name pairings + 36 exempt + 283 debt = 361).
# It went UP by 47 on purpose - see the block at the end of the list: coverage
# now credits only the pairing a mutation was examined against, and 47 names
# that a mutation's blast radius had marked PROVEN turned out never to have
# been looked at.
#
# It is printed with its count on every run.  Growth by any other route is a
# regression: a new check lands here only by a deliberate edit, which is the
# decision the meta-check exists to force.  The way to shrink it is one
# registered mutation at a time, and the cheap runners are where the leverage
# is (`scene`, `2d`, `hda` and `images` are seconds; only `native` costs six
# minutes a mutation).
UNPROVEN = {}
UNPROVEN.update(dict.fromkeys((
    "2d/cell_grid",
    "2d/cell_inventory",
    "2d/cell_modules",
    "2d/cell_set",
    "2d/clip_hole_elements",
    "2d/clip_inside_m",
    "2d/corner_abut_m",
    "2d/corner_breach_m",
    "2d/corner_seam_m",
    "2d/deformed_flag_mismatch",
    "2d/determinism",
    "2d/duplicate_elem_ids",
    "2d/element_count",
    "2d/exact_fill_m",
    "2d/fallback_map",
    "2d/geometry_digest",
    "2d/inward_faces",
    "2d/max_gap_m",
    "2d/min_piece_span_m",
    "2d/module_fidelity_m",
    "2d/output_schema",
    "2d/packed_pieces",
    "2d/points_wrappers_built_2d_rows",
    "2d/polyfill_appends_its_patches",
    "2d/prims_wrappers_built_2d_rows",
    "2d/ray_executions_per_build_2d_rows",
    "2d/ray_executions_per_build_2d_tower",
    "2d/rigid_deformed",
    "2d/role_fallbacks",
    "2d/row_closure_m",
    "2d/row_fill_y_m",
    "2d/row_scale_packed",
    "2d/rows_clipped_out",
    "2d/rows_wrappers_built",
    "2d/section_coverage_m",
    "2d/structural_ids",
    "2d/verb_executions_per_build_2d_rows",
    "2d/warnings",
    "2d/wrapper_reads_2d_rows",
    "hda/bad_kit_file_warns",
    "hda/every_number_has_a_range",
    "hda/every_parm_has_help",
    "hda/input4_is_the_surface",
    "hda/marker_gate_survives_the_native_chain",
    "hda/marker_read_is_silent",
    "hda/marker_slot_on_the_page",
    "hda/no_errors",
    "hda/no_spline_warns",
    "hda/node_matches_kernel",
    "hda/only_the_warned_prims_are_coloured",
    "hda/plan_is_one_point_per_piece",
    "hda/proxy_beats_full_on_a_curve",
    "hda/proxy_is_interactive",
    "hda/proxy_matches_piece_count",
    "hda/show_warnings_off_paints_nothing",
    "hda/starter_fence_corners",
    "hda/starter_fence_packed",
    "hda/starter_fence_prims",
    "hda/two_disclosure_levels",
    "hda/units_in_the_label",
    "hda/warned_elements_are_coloured",
    "images/axis_on_curve_m",
    "images/bank_deg",
    "images/conform_contact_m",
    "images/conform_drape_m",
    "images/corner_abut_m",
    "images/corner_breach_m",
    "images/corner_seam_m",
    "images/corner_turns",
    "images/double_pillar_m",
    "images/element_count",
    "images/exact_fill_m",
    "images/flat_stepped_m",
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
    "images/inward_faces",
    "images/max_gap_m",
    "images/n5_deformed_image_has_geometry",
    "images/n5_deformed_is_native",
    "images/n5_deformed_matches_the_reference",
    "images/over_unpacked",
    "images/partb_curved_is_native",
    "images/partb_curved_matches_the_reference",
    "images/plumb_deg",
    "images/stepped_float_m",
    "images/warnings",
    "native/asset_wiring_comparison_is_load_bearing",
    "native/bench_guard_fallback",
    "native/bench_long_curve_really_cooked",
    "native/bench_plan_long_curve",
    "native/bench_plan_long_curve_really_cooked",
    "native/bench_plan_streets_300",
    "native/bench_plan_streets_300_really_cooked",
    "native/bench_streets_6000_really_cooked",
    "native/config_cost_per_module",
    "native/config_reads_the_payload",
    "native/copy_useimplicitn_is_a_noop",
    "native/declared_limit_dup_id_marker",
    "native/decompose_corner_parity",
    "native/decompose_long_curve_wall_clock",
    "native/decompose_marker_parity",
    "native/decompose_streets_6000_wall_clock",
    "native/deform_wrangle_rig_really_deforms",
    "native/emit_cost_is_flat_in_piece_count",
    "native/every_python_sop_comment_is_checkable",
    "native/every_stage_ends_in_a_named_null",
    "native/every_stage_entry_serves_the_node_it_names",
    "native/every_stage_has_a_second_source",
    "native/every_stage_is_a_network_box",
    "native/every_wrangle_has_a_cost_ceiling",
    "native/every_wrangle_says_what_it_computes",
    "native/frames_cost_is_flat_in_segment_count",
    "native/gate_parity",
    "native/guard_deform_refusals",
    "native/guard_refusal_list_is_true",
    "native/instances_do_not_fork_the_network",
    "native/locked_instance_shows_its_network",
    "native/native_branch_cooks_on_output",
    "native/native_branch_is_load_bearing",
    "native/native_id_and_curve_set_parity",
    "native/native_place_says_why_it_is_empty",
    "native/no_absolute_node_paths",
    "native/payload_thresholds_reach_the_corners",
    "native/place_deformed_covers_the_reference",
    "native/place_deformed_is_not_empty",
    "native/place_duplicate_module_name",
    "native/place_packed_is_not_empty",
    "native/place_stamp_owed_is_live",
    "native/plan_cost_is_flat_in_kit_size",
    "native/plan_digest_is_not_empty",
    "native/plan_distinct_ids_are_input_order_free",
    "native/plan_ignores_payload_order",
    "native/plan_recook_is_identical",
    "native/plan_sections_emitted",
    "native/plan_shared_id_is_order_sensitive",
    "native/plan_span_transport_at_20km",
    "native/scene_baseline_movement_fails_the_run",
    "native/seed_corpus_has_multibyte",
    "native/seed_elem_key_parity",
    "native/solve_cost_is_flat_in_piece_count",
    "native/stage_labels_are_true",
    "native/stage_menu_reaches_every_stage",
    "native/stamp_cost_is_flat_in_piece_count",
    "native/the_note_matches_the_build",
    "native/working_groups_are_prefixed",
    "native/wrangle_ceilings_are_tight",
    "native/wrangle_ceilings_are_tight_deformed",
    "native/wrangle_cost_is_flat_in_piece_count_deformed",
    "scene/band_datum_m",
    "scene/band_hybrid_m",
    "scene/bend_deviation_m",
    "scene/build_out_keeps_upstream_stamps",
    "scene/cap_prims",
    "scene/cap_uv_m",
    "scene/conform_cache_per_element",
    "scene/conform_cache_per_element_streets",
    "scene/conform_contact_m",
    "scene/conform_prefetch_hit_rate",
    "scene/corner_mate_axis_m",
    "scene/corner_plane_dev_m",
    "scene/corner_reach_m",
    "scene/corner_seam_m",
    "scene/corner_symmetry_m",
    "scene/corner_turns",
    "scene/corner_wedge_m2",
    "scene/corner_welds",
    "scene/cross_section_m",
    "scene/curve_sample_scaling",
    "scene/deformed_flag_mismatch",
    "scene/determinism",
    "scene/duplicate_curve_id_warn",
    "scene/duplicate_elem_ids",
    "scene/elem_ids_upstream",
    "scene/element_count",
    "scene/flat_stepped_m",
    "scene/frame_dot_min",
    "scene/geometry_digest",
    "scene/horizontal_span_m",
    "scene/inward_faces",
    "scene/kit_warnings",
    "scene/marker_offset_m",
    "scene/min_piece_span_m",
    "scene/module_fidelity_m",
    "scene/modules_by_curve",
    "scene/open_edges",
    "scene/output_schema",
    "scene/over_unpacked",
    "scene/override_round_trip",
    "scene/path_read_direction_m",
    "scene/path_sample_calls_per_piece",
    "scene/plan_point_provenance",
    "scene/plan_points",
    "scene/plumb_deg",
    "scene/points_wrappers_built",
    "scene/points_wrappers_built_streets",
    "scene/polyfill_appends_its_patches",
    "scene/prims_wrappers_built",
    "scene/prims_wrappers_built_deformed",
    "scene/prims_wrappers_built_mitered",
    "scene/ray_executions_per_build",
    "scene/replaced_bbox_m",
    "scene/rigid_deformed",
    "scene/sampler_matches_kernel",
    "scene/section_coverage_m",
    "scene/stamp_bulk_peak_kb",
    "scene/stamp_calls_per_piece",
    "scene/stamp_calls_per_piece_deformed",
    "scene/stamp_provenance",
    "scene/station_share_hit_rate",
    "scene/station_spacing_m",
    "scene/stepped_float_m",
    "scene/stepped_riser_m",
    "scene/style_payload_degrades",
    "scene/style_round_trip",
    "scene/unresolved_elem_ids",
    "scene/verb_executions_per_build_mitered",
    "scene/warn_summary",
    "scene/widest_horizontal_m",
    "scene/wrapper_reads_mitered",
    "scene/wrapper_reads_streets",
    "scene/zmode_stamp",
), "no mutation yet"))

# ---- 2026-08-24, THE AUDIT OF THE INSTRUMENT: 47 NAMES THAT WERE
# CREDITED WITHOUT BEING EXAMINED. Coverage used to credit every check a
# mutation happened to redden, not the check it was PAIRED with, so a
# mutation's blast radius marked names PROVEN that nobody had looked at -
# permuting the conform axis credited `stepped_riser_is_m`, a step-height
# check with no mutation of its own, and removed it from this list for good.
# Crediting is `kills`-only now, and these 47 are what fell out: they were
# never proven, so they are debt, and the debt list going UP is the honest
# direction here.
UNPROVEN.update(dict.fromkeys((
    "hda/evenly_clears_the_corner_adjust_to_end",
    "hda/evenly_clears_the_corner_justify_center",
    "hda/evenly_clears_the_corner_justify_start",
    "hda/junk_payload_builds_nothing",
    "hda/parms_inert_under_payload",
    "hda/payload_overrides_styleid",
    "hda/starter_fence_modules",
    "hda/unread_marker_warns",
    "native/asset_stages_match_the_rig",
    "native/bench_deform_20km",
    "native/decompose_length_parity",
    "native/decompose_turn_parity",
    "native/every_cited_check_exists",
    "native/every_wrangle_comment_is_checkable",
    "native/frames_arithmetic_linear_parity",
    "native/frames_arithmetic_position_parity",
    "native/guard_anchor_cost_is_linear",
    "native/guard_deform_ladder",
    "native/guard_kit_mismatch",
    "native/guard_padding_parity",
    "native/guard_row_warns_wrong_storage",
    "native/guard_spline_attr_types",
    "native/kit_starter_cooks_once",
    "native/native_ok_refuses_an_unreadable_cond",
    "native/output_guard_cost",
    "native/payload_cond_values_survive_the_round_trip",
    "native/place_packed_covers_the_reference",
    "native/place_packed_parity",
    "native/place_stamp_parity",
    "native/plan_shared_id_matches_reference_in_both_orders",
    "native/plan_solve_parity",
    "native/plan_solve_section_shape",
    "native/plan_stress_parity",
    "native/r8_packed_scale_survives",
    "native/seed_crc32_parity",
    "native/seed_random01_parity",
    "native/seed_splitmix64_parity",
    "native/union_matches_the_python_path",
    "native/wrangle_cost_is_flat_in_piece_count",
    "scene/axis_on_curve_m",
    "scene/conform_drape_m",
    "scene/conform_prefetch_hit_rate_streets",
    "scene/corner_clearance_m",
    "scene/exact_fill_m",
    "scene/max_gap_m",
    "scene/path_sample_calls_per_piece_deformed",
    "scene/stepped_riser_is_m",
), "no mutation yet - was credited by a mutation's blast radius until 2026-08-24"))
