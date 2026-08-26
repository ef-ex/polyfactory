"""THE MUTATION REGISTRY - every polyChain check paired with the edit that
proves it can fail.

    hython tests/polychain/run_mutation_registry.py          # the meta-runner
    hython tests/polychain/pdg_build.py --full               # in parallel

⚠️ WHY THIS FILE EXISTS: `ideas/build_retrospective.md` 2a - ~20 checks
that COULD NOT FAIL across ~15 cycles, every one found by an auditor running a
mutation by hand and never by the green suite. This file is "a check is not
written until its mutation has been seen to fail" as DATA.

WHAT AN ENTRY IS. One `M(...)`: an id, the runner that owns the paired checks,
exact source edits, and `kills` - the check names that MUST go red. Three
properties, each an incident: the edit is an exact string swap the runner
asserts matched EXACTLY ONCE (a moved target line reports green forever,
D208); ONLY the declared pairing is credited (crediting a blast radius
silently marked 47 unexamined names as proven); and A CRASH IS NOT A RED
(21.5) - an abort fails the run unless the entry says `expect="abort"`.

OUT OF SCOPE BY CONSTRUCTION: `scale_gate.py` and `tests/hda/
run_attrib_checks.py` print no green-run inventory, so there is no name to
pair against - a property of their output format, not a judgement.
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
    # P2-9's node, judged against the shipped 2D entry point by the same
    # differential comparator - plus 5.1's metadata on all THREE assets.
    "facade": "tests/polychain/run_facade_hda_checks.py",
}

# D210 made a MOVED baselined value fail the run like a failing check.
# Movement has no check name, so it gets a reserved one to pair against.
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
FACADE_BUILD = "devScripts/create_pf_polychain_facade_hda.py"
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
       "native_stages_are_really_native",
       # with `output` pointed back at Python both shapes read ~1.0x, over
       # the many-short-curves ceiling of 0.45 - the direction it holds.
       "output_guard_cost"),
      "27.7b m3 / 21.4 M1 - the exact source-level UNDO of the whole native "
      "flip: `Stage = output` pointed back at the Python reference.",
      ((RIG,
        '    ("output", "OUT_final", "guard_envelope",',
        '    ("output", "OUT_reference", "kernel",'),)),

    M("guard_never_refuses", "native",
      ("output_guard_parity", "no_case_pays_the_guard_fallback"),
      "27.7b m6 - level 1 admits every build, including the classes the "
      "native chain cannot answer (corners, conform, flatten).",
      # ⚠️ RE-POINTED BY 13.9 N8 STAGE 1 - the verdict line's own text moved
      # (`corners == 0` became `!corner_refuse`), and an edit whose target
      # line has moved is D208 exactly: it reports green forever.
      ((VEX % "pc_envelope.vfl",
        "i@_native_ok = (ok && !corner_refuse && ndup == 0",
        "i@_native_ok = (1 || ok && !corner_refuse && ndup == 0"),)),

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
      ((RUNNER_NATIVE,
        "if (hit) best = set((a.x != 0.0) ? best.x : q.x,",
        "if (hit) best = a * 1e-5 + set((a.x != 0.0) ? best.x : q.x,"),),
      rebuild=False),

    # ---- 13.9 N6, THE CONFORM PORT -----------------------------------------
    #
    # ⚠️ THE FIRST OF THESE IS THE ONE THAT MATTERS, and it is the shape the
    # whole differential is built to survive: `Stage = output` is a GUARDED
    # fork, so the day level 1 stops admitting a surface every conformed case
    # silently goes back to comparing the Python kernel WITH ITSELF and the
    # sweep prints a green.  This puts the refusal back and the tripwire must
    # see it.
    M("conform_refused_at_level_1", "generated",
      ("conformed_cases_reach_the_native_chain",),
      "13.9 N6 undone at level 1 - a surface refuses the build again, so "
      "every conformed case compares Python with Python.",
      ((PY % "hda.py",
        '        if getattr(params, "conform_tilt", False):',
        "        if True:"),)),

    M("conform_surface_type_admitted", "native",
      ("output_guard_parity",),
      "F1: level 1 stops asking what the surface is MADE OF, so "
      "`BO_conform_strays`' debug polylines take the drape - the reference "
      "drapes to y = -2.0 and the native chain to y = +0.5, ON the debug "
      "curve, with both guard levels reading 1.",
      ((PY % "hda.py",
        "        if not _surface_is_droppable(surface):",
        "        if False:"),)),

    M("conform_drop_biased_vex", "generated",
      ("conform_parity_spends_its_tolerance",),
      "The native drape stretched by 1e-11 RELATIVE to the drop - far under "
      "the float32 `P` the fence ships, so the only things that can see it are "
      "the packed 3x3 read as a double and the row that MEASURES what the "
      "stated tolerance is being spent on. A stated tolerance nothing reads "
      "back is a number any later cycle widens for free. "
      "⚠️ RELATIVE, and that is not decoration: a CONSTANT bias along "
      "the axis CANCELS in the chord `b - a` the packed frame is built from, "
      "and every POSITION in this comparison is float32 - measured, 1e-10 m of "
      "constant bias moved NOTHING over 45 cases and 5e-13 m moved nothing "
      "over 405. Only a drop that varies along the run reaches a compared "
      "double.",
      ((VEX % "pc_conform.h",
        "    if (!hit) return;",
        "    if (!hit) return;\n"
        "    best = best + axis * (dot(best - q, axis) * 1e-11);"),)),

    M("transport_stations_dropped", "native",
      ("output_guard_parity",),
      "F3: `pc_frames_transportable` stops adding the piece's OWN STATIONS "
      "to its sample set. `BQ_conform_wall_bumps` is the one shape that "
      "reaches it (`pc_gate.h` says why): shipped 10 planned / 0 built, "
      "mutated 10 built and level 2 ADMITS a fence that is not the "
      "reference's.",
      ((VEX % "pc_gate.h",
        "    if (conformed)\n"
        "        foreach (float x; st) push(ss, s0 + (x - ax) * scale);",
        "    if (0)\n"
        "        foreach (float x; st) push(ss, s0 + (x - ax) * scale);"),)),

    # F4, `conform_deviates_never_fires`' other half: that proves the drape
    # gate FIRES, this that it fires at the threshold it advertises.
    M("deviates_tol_10x", "native",
      ("output_guard_parity",),
      "4.5's drape test at TEN TIMES its tolerance. `BR_conform_bump_at_tol` "
      "is `BL_conform_bump`'s ridge at 0.03 m instead of 0.5 m - 3x "
      "`bend_tol`, inside the mutated 10x - so its one bending panel ships "
      "PACKED and the output loses `pc_local` entirely.",
      ((VEX % "pc_conform.h",
        "        if (length(q - u * t) > tol) return 1;",
        "        if (length(q - u * t) > tol * 10.0) return 1;"),)),

    M("conform_deviates_never_fires", "native",
      ("gate_parity",),
      "4.5's drape test switched off - `deviates` returns 0, so a bendable "
      "piece crossing a HILL a dead-straight spline has no vertex for stays "
      "PACKED as a rigid chord with its two ends on the ground.  It is the "
      "one term of `_needs_deform` that only a conformed build can reach.",
      ((VEX % "pc_conform.h",
        "    if (!pc_surf_active(surf) || abs(sb - sa) <= PC_EPS) return 0;",
        "    return 0;\n    if (!pc_surf_active(surf) "
        "|| abs(sb - sa) <= PC_EPS) return 0;"),)),

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

    # ---- PC-G5's two conditions that had nothing behind them ---------------
    M("2d_adaptive_slices", "2d",
      ("no_sliced_cells",),
      "PC-G5 condition 4 was TRUE AND UNASSERTED - 0 of 176 placements carry "
      "a slice_t and no check said so. This gives the adaptive fit a "
      "remainder to cut, so a facade ships half windows.",
      ((PY % "plan.py",
        '    return {"count": n, "scale": scale, "remainder": 0.0, '
        '"slice": False,\n            "warns": warns}',
        '    return {"count": n, "scale": scale, "remainder": s * 0.5, '
        '"slice": True,\n            "warns": warns}'),
       (PY % "plan.py",
        "            elif not m.sliceable:",
        "            elif False:")),
      rebuild=False,
      note="⚠️ TWO EDITS, AND THE SECOND ONE IS WHY. The facade kit's bay is "
           "`pc_deform = 1` (BEND), so the remainder alone sends the run "
           "through `fallback()` - which re-enters the fill and aborted the "
           "runner with a RecursionError rather than reddening anything "
           "(21.5: a crash is not a red). Lifting the sliceable veto is what "
           "makes the remainder become a CUT. ⚠️ And it also says what the "
           "check cannot claim: on this kit 4.2 could not slice even under "
           "`tile`, so `no_sliced_cells` is asserting the FIT's choice, not "
           "the slicer's veto."),

    M("2d_cell_role_dropped", "2d",
      ("bay_alignment",),
      "PC-G5 condition 3 needed a FIXTURE as well as a check: every row of "
      "the L fitted the same kit over the same legs, so `aligned` and `free` "
      "were indistinguishable. `FW_y_free` gives the ground floor a wider "
      "module; dropping the CELL role from the fill's candidate lookup - the "
      "exact regression `FS_sequence_cells` was written for - resolves the "
      "bare `default` slot on every row and the rows fit identically again.",
      ((PY % "plan.py",
        '    cand = candidates(rule, kit, cell_role(ctx, ctx.get("slot",'
        ' rule.slot)))',
        "    cand = candidates(rule, kit)"),),
      rebuild=False),

    # ---- P2-5 / D122: the Y fit's ALIGNED mode ------------------------------
    M("2d_aligned_never_stamped", "2d",
      ("bay_alignment_aligned",),
      "`aligned` stops stamping the datum row's bay count onto the other "
      "rows, so every row solves free again and the mode is a no-op that "
      "reads exactly like `free`. PC-G5 condition 3's whole question.",
      ((PY % "facade.py",
        '        if y_mode == "aligned":',
        "        if False:"),),
      rebuild=False),

    M("2d_aligned_count_ignored", "2d",
      ("bay_alignment_aligned",),
      "The count REACHES the fill and the fill ignores it: `_fill` keeps the "
      "style's own mode instead of switching to `count`. A subtler shape than "
      "the one above and the one an optimiser would produce - the attribute "
      "is stamped, harvested and read, and the geometry is still free.",
      ((PY % "plan.py",
        '    mode = "count" if count is not None else (mode or params.fill)',
        "    mode = mode or params.fill"),),
      rebuild=False),

    # ---- P2-4 / D293: 2.1's pipeline face on the 2D path --------------------
    M("2d_payload_does_not_override", "2d",
      ("payload_round_trip_2d", "parms_inert_under_payload"),
      "The payload stops overriding the 2D path's own keywords, which is "
      "2.1's pipeline face deleted: the same payload then builds differently "
      "on two nodes because each keeps whatever its keywords happened to say. "
      "⚠️ ONE EDIT, TWO PAIRED CHECKS, DELIBERATELY: they are the two halves "
      "of one property and no edit separates them - a payload that does not "
      "override cannot round-trip either, because the parm face's own "
      "settings are exactly what the round trip is carrying.",
      ((PY % "facade.py",
        '    clip_mode = settings.get("clip_mode", clip_mode)',
        "    clip_mode = clip_mode"),),
      rebuild=False),

    M("2d_payload_refusal_silent", "2d",
      ("payload_input_warns",),
      "7.3.2's three unbuildable `clip` keys stop being refused and are "
      "ignored instead, so a payload asking for `cap_holes = 0` gets capped "
      "holes back and is told nothing. D294's whole point is that ignoring "
      "is answering wrong.",
      ((PY % "array2d.py",
        "            if isinstance(value, bool) or value != CLIP_FIXED[key]:",
        "            if False:"),),
      rebuild=False),

    # ---- PC-G6: the clipped area (7.6 / P2-7) ------------------------------
    M("2d_clip_slice_becomes_preserve", "2d",
      ("clip_inside_m",),
      "The `slice` policy stops cutting and keeps the piece whole instead, "
      "so every straddler overhangs the boundary. PC-G6 condition 1 is the "
      "distance a delivered point lies outside the region and this is the "
      "bluntest way to move it off zero.",
      ((PY % "array2d.py",
        "        if policy == CLIP_PRESERVE:",
        "        if policy != CLIP_REMOVE:"),),
      rebuild=False),

    M("2d_clip_nesting_area_rule", "2d",
      ("clip_nesting",),
      "THE INCIDENT, AS A MUTATION. Nesting drops the rule that a loop can "
      "only sit inside a strictly LARGER one - and three concentric squares "
      "share one centroid, so the plate, its hole and its island each "
      "'contain' the other two, depth comes back [2, 2, 2] and the hole is "
      "built solid. Found by looking at the array ids, not by a check, which "
      "is why there is a check now.",
      ((PY % "array2d.py",
        "    return [[j != i and areas[j] > areas[i] + EPS",
        "    return [[j != i and True"),),
      rebuild=False,
      note="⚠️ D208 CAUGHT THIS ONE MOVING. C2a extracted the containment "
           "matrix into `_contains` (so `Region`'s own `depth` default stops "
           "being the loop INDEX) and the registered line changed its "
           "indentation and its keyword. The sweep reported STALE - 'the "
           "registered edit matches 0 times' - rather than a green."),

    M("2d_clip_caps_deleted", "2d",
      ("clip_caps_closed",),
      "Every patch `polyfill` appended is treated as a stray and deleted, so "
      "a clip cut opens a hole and never closes it. The C1 trap's exact "
      "mirror image - that one capped boundaries the cut never opened, this "
      "one caps nothing at all - and both are invisible in a wireframe. "
      "⚠️ `deletePrims` takes hou.Prim OBJECTS: the index spelling aborted "
      "the runner instead of reddening anything (21.5).",
      ((PY % "place.py",
        "        stray = _off_plane_patches(filled, n_cut, n_all, origin, "
        "normal)",
        "        stray = [filled.prim(i) for i in range(n_cut, n_all)]"),),
      rebuild=False),

    M("2d_clip_unsliceable_cut_anyway", "2d",
      ("clip_policy",),
      "D126's degrade-to-remove is lifted, so a RIGID module asked to slice "
      "is cut anyway: nothing warns and the kit's own `pc_deform` stops "
      "meaning anything at the boundary.",
      ((PY % "array2d.py",
        "        if not module.sliceable:",
        "        if False:"),),
      rebuild=False),

    M("2d_clip_arrays_merged", "2d",
      ("clip_independence",),
      "Every sub-spline is folded into ONE array instead of one array per "
      "depth-0 loop, so D125's independence is gone: the disjoint plate "
      "beside the first one stops having an `arrayId` of its own and its "
      "`pc_elem_id`s move whenever anything else is edited.",
      ((PY % "array2d.py",
        "        out.setdefault(r, []).append(i)",
        "        out.setdefault(0, []).append(i)"),),
      rebuild=False),

    M("2d_clip_mode_override_ignored", "2d",
      ("clip_mode_override",),
      "7.6's per-sub-spline `pc_clip_mode` stops overriding the even-odd "
      "result, so RC's `None` hierarchy mode silently does nothing and the "
      "whole attribute is a branch the build never executes.",
      ((PY % "array2d.py",
        '        include.append(True if m == "include" else\n'
        '                       False if m == "exclude" else (d % 2 == 0))',
        "        include.append(d % 2 == 0)"),),
      rebuild=False),

    M("2d_clip_convex_never_warns", "2d",
      ("warnings",),
      "D145's channel, and the reason it is PINNED rather than merely "
      "declared. An intersection of half-spaces equals the polygon only "
      "where the polygon is locally convex, so a REFLEX vertex of the region "
      "inside one piece takes too much material away - a gap, never a "
      "breach, so PC-G6's containment condition passes and the defect is "
      "silent. This stops the detection firing; `warnings` compares the "
      "EXACT set, so it goes red on an absence.",
      ((PY % "array2d.py",
        "            if (cross < -EPS) if self.include[pi] else "
        "(cross > EPS):",
        "            if False:"),),
      rebuild=False),

    M("2d_clip_preserve_is_remove", "2d",
      ("clip_preserve",),
      "D126's three policies collapse to two: `preserve` stops being reached, "
      "so a piece that should be kept whole and allowed to overhang falls "
      "through to `remove` and is dropped instead.",
      ((PY % "array2d.py",
        "        if policy == CLIP_PRESERVE:",
        "        if False:  # the preserve mutation"),),
      rebuild=False,
      note="⚠️ THE OBVIOUS EDIT IS INERT, and it is the dev-loop's "
           "own rule about mutating something the code does not read "
           "symmetrically: setting `CLIP_PRESERVE = 0` in the constants "
           "changes NOTHING, because `CLIP_POLICIES[\"preserve\"]` and the "
           "test against it both move together. It SURVIVED a full sweep."),

    # ---- C2a: the audit's findings, each as the edit that reddens ----------
    M("2d_clip_frame_winding", "2d",
      ("array_offplane_m_hostile",),
      "C2a's F1 AS A MUTATION: the array's plane normal goes back to being "
      "whatever the artist's WINDING made it, so a clockwise clip loop gives "
      "the frame an `ey` of -Y. ⚠️ RE-PAIRED IN C3a, and the re-pairing "
      "is the finding: it used to kill `clip_inside_m_hostile` at 2.0 m "
      "because the kernel grew every module along +Y while the plan trimmed "
      "against -Y. D296a made the kernel follow the ROW's up axis, so a "
      "flipped array is now built consistently INSIDE its own footprint - "
      "upside down - and this mutation SURVIVED the C3a sweep reddening "
      "nothing at all. What D290 guarantees is ORIENTATION, not containment.",
      ((PY % "array2d.py",
        "    if _dot(ey, UP) < -EPS:",
        "    if False:  # the winding mutation"),),
      rebuild=False),

    M("2d_clip_cap_tol_unscaled", "2d",
      ("clip_caps_closed_hostile", "caps_closed_mitered"),
      "FINDING F2, AS A MUTATION. The cap guard's tolerance goes back to "
      "scaling with the PIECE (2e-06 m on a 2 x 2 x 0.3 module) while the "
      "error it must absorb is float32 round-off on the WORLD position. "
      "PC-G6's own fixture 500 m out measured 1.3e-05..2.0e-05 m on GENUINE "
      "caps and lost seven of eight; the district's 6 400 mitered elements "
      "shipped 18 776 open boundary edges. ⚠️ IT REDDENS ON THE DISTRICT AND "
      "NOT ON PC-G5's L: 0..24 m is too near the origin for the round-off to "
      "reach 2e-06, which is why the mitered row is not measured on the L.",
      ((PY % "place.py",
        "    tol = min(1e-6 * max(1.0, reach, size[0], size[1], size[2]),"
        " 0.25 * thin)",
        "    tol = 1e-6 * max(1.0, size[0], size[1], size[2])"),),
      rebuild=False),

    M("2d_clip_selfx_accepted", "2d",
      ("clip_input_warns",),
      "FINDING F3, AS A MUTATION. A self-intersecting boundary is taken as a "
      "region again: its lobes wind opposite ways, `_area2` of a symmetric "
      "one is exactly 0.0 so `_ccw` is a no-op, and the half-planes "
      "`Region.cuts` emits point OUT of one lobe - a bowtie plate breached "
      "its own region by 0.8839 m with nothing warned. D145's reflex channel "
      "structurally cannot see it: a self-intersection is never a VERTEX.",
      ((PY % "facade.py",
        "        if not _array2d.is_simple(loop):",
        "        if False:  # the self-intersection mutation"),),
      rebuild=False),

    M("2d_clip_nonplanar_accepted", "2d",
      ("clip_input_warns",),
      "FINDING F4, AS A MUTATION. 7.6 says a closed PLANAR sub-spline and "
      "nothing tested the second word: a 20 x 20 m plate with one corner "
      "lifted built with no word said and delivered points 0.0112 m outside "
      "the region against PC-G6's own 0.010 m - a gate condition failing "
      "silently on input the spec already excluded.",
      ((PY % "facade.py",
        "        planar, off = _array2d.is_planar(loop)",
        "        planar, off = True, 0.0"),),
      rebuild=False),

    # ⚠️ `2d_clip_tilt_never_warns` IS DELETED, NOT MOVED. It paired
    # `clip_input_warns` with `CLIP_TILT_DEG`, and D296 RETIRED that warning
    # by fixing the defect it announced - a tilted array builds inside its own
    # region now. The channel it proved is covered by the four remaining
    # detectors; the tilt itself is `tilt_ladder_*` below, on numbers rather
    # than on a warning name.

    M("2d_clip_nonplanar_warns_always", "2d",
      ("clip_input_warns_clean",),
      "THE CONTROL, AND IT IS INHERITED FROM THE ROW D296 DELETED. A detector "
      "that fires on EVERYTHING passes an exact-set check that only ever "
      "looks at hostile input, so the shipped fixture asserts the validation "
      "station says NOTHING - and this is the edit that makes that assertion "
      "falsifiable rather than decorative. The planarity tolerance is the "
      "cheapest detector to jam open now that the tilt one is gone.",
      ((PY % "array2d.py",
        "def is_planar(points, rel_tol=1e-3):",
        "def is_planar(points, rel_tol=-1.0):"),),
      rebuild=False),

    # ---- P2-5 / D296: the row's own up reference ----------------------------
    M("2d_row_up_is_world_up", "2d",
      ("tilt_ladder_offplane_m",),
      "The row stops carrying the ARRAY's up axis and takes the world's, "
      "which is the state C2a shipped and warned about. Measured on the "
      "ladder before the fix: 2 deg 0.0697 m, 5 deg 0.1737, 10 deg 0.3450, "
      "30 deg 0.9799, 90 deg 1.8500 m off the array's own plane - a 2 m "
      "module standing vertically out of its own floor plate.",
      ((PY % "array2d.py",
        '            attrs["pc_upref"] = frame.ey',
        '            attrs["pc_upref"] = UP'),),
      rebuild=False),

    M("2d_yaw_frame_world_up", "2d",
      ("tilt_ladder_inside_m",),
      "The attribute is stamped, harvested and passed in, and the KERNEL "
      "throws it away: the yaw-only branch grows the module along the world "
      "up axis again. The subtler half of the same defect, and the one a "
      "reader would call a harmless simplification - `clip_inside_m` goes "
      "0.0052 / 0.0131 / 0.0260 / 0.0750 m across the ladder against PC-G6's "
      "0.010 m tolerance.",
      ((PY % "place.py",
        "    return (d, _cross(d, up_ref), up_ref)",
        "    return (d, _cross(d, UP), UP)"),),
      rebuild=False),

    # ---- C3a: PC-G5's two conditions the v2 deletion pass left unchecked ----
    M("2d_row_band_published_wrong", "2d",
      ("row_closure",),
      "`pc_row_y1` is published 0.05 m high, so the band an element is "
      "stamped with stops matching the band it was BUILT in. 7.8 condition 2 "
      "asks for that seam at 1e-6 m and nothing had re-run it since the v2 "
      "pass deleted `cell_grid`.",
      ((PY % "array2d.py",
        '                "pc_row_y1": self.y1, "pc_row_scale": self.scale,',
        '                "pc_row_y1": self.y1 + 0.05, "pc_row_scale": self.scale,'),),
      rebuild=False),

    M("2d_footprint_not_canonical", "2d",
      ("structural_ids",),
      "D124's canonical winding is dropped, so the same L drawn the other "
      "way round renumbers every section and moves every `pc_elem_id` - "
      "citygen_buildings 12.7's own prohibition, 7.8 condition 6, and a check "
      "the v2 pass deleted.",
      ((PY % "array2d.py",
        "    if _signed_area_xz(pts) > 0.0:",
        "    if False:"),),
      rebuild=False),

    # ---- C3a / D300: the payload layer that named nothing ------------------
    M("2d_payload_meta_unchecked", "2d",
      ("payload_meta_warns",),
      "`style.read` stops naming an unknown TOP-LEVEL `pc_style_meta` key - "
      "the state C3 shipped, where every layer below said what it did not "
      "know and the dict an author writes FIRST took anything in silence.",
      ((PY % "style.py",
        "    for key in sorted(k for k in meta if k not in META_KEYS):",
        "    for key in ():"),),
      rebuild=False),

    # ---- C3a / D297-D299: ALIGNED, where 7.4 says it changes nothing --------
    M("2d_align_count_is_units", "2d",
      ("align_no_op_sequence",),
      "`pc_bays` (BAYS) is handed to `fit` (UNITS) again, so a SEQUENCE "
      "default rule doubles every non-datum row - 120 / 168 / 168 / 168 "
      "against free's 120 four times, on CONGRUENT rows.",
      ((PY % "plan.py",
        "        count, rem = divmod(int(count), len(mods))",
        "        count, rem = int(count), 0"),),
      rebuild=False),

    M("2d_align_no_minimum_scale", "2d",
      ("align_no_op_floor", "align_no_op_area"),
      "7.4's named degrade loses its threshold and can then not fire at all "
      "on a kit without padding: `fit(0.5, 3.0, 'count', count=7)` returns 7 "
      "units at scale 0.02381, and its drop loop only runs when `fixed` or "
      "`gap` is non-zero. It kills the AREA row too, which IS D297's answer: "
      "the holed plate's strips build at 0.125 m because the FLOOR is gone, "
      "not because the datum is a span.",
      ((PY % "plan.py",
        '                              or res["scale"] < MIN_ALIGN_SCALE):',
        '                              or res["scale"] < 0.0):'),),
      rebuild=False),

    # ---- C3a / D296a: the yaw sites D296 did not sweep ----------------------
    # ⚠️ ALL FOUR WERE GREEN ON THE SIX-RUNG LADDER, whose `frame.ex` is
    # +X at every rung, so each spelling agreed with the generalised one. What
    # reddens them is a rung that moves `ex`.
    M("2d_packed_chord_world_flat", "2d",
      ("tilt_ladder_inside_m",),
      "`_packed_transform` squashes the chord into the world XZ plane again, "
      "one line before handing it to the frame D296 generalised. On HEAD "
      "1a3f1ce: 30 deg started at vertex 1 reads `clip_inside_m` 0.064952 m "
      "against PC-G6's 0.010 tolerance, at vertex 3 1.797003 m.",
      ((PY % "place.py",
        "        flat = _flat(chord, up_ref)",
        "        flat = (chord[0], 0.0, chord[2])"),),
      rebuild=False),

    M("2d_deform_grows_world_y", "2d",
      ("tilt_ladder_offplane_m",),
      "The deform's yaw branch adds the module's local y to the WORLD Y "
      "component and drops the `up` it just built - D296's own fix, left "
      "standing in the writer beside the one it edited. On HEAD 1a3f1ce a "
      "30/20 roll is 0.906580 m off its own plane, 90/45 1.339214 m.",
      ((PY % "place.py",
        "            out[i] = b[0] + across[0] * z + up_ref[0] * sy",
        "            out[i] = b[0] + across[0] * z"),
       (PY % "place.py",
        "            out[i + 1] = b[1] + across[1] * z + up_ref[1] * sy",
        "            out[i + 1] = b[1] + sy"),
       (PY % "place.py",
        "            out[i + 2] = b[2] + across[2] * z + up_ref[2] * sy",
        "            out[i + 2] = b[2] + across[2] * z"),),
      rebuild=False),

    M("2d_shear_test_world_y", "2d",
      ("tilt_ladder_packed",),
      "`_needs_deform`'s `vertical` shear test asks whether the span rises in "
      "the WORLD again. Every span of a tilted array does, so 100 packed "
      "prims become 350 real ones and D121's 'a scaled storey stays packed' "
      "stops surviving a tilt. ⚠️ THE GEOMETRY IS STILL RIGHT, which is "
      "why no containment number can see it.",
      ((PY % "place.py",
        "        return abs(_dot(_sub(b, a), up_ref)) > 1e-6",
        "        return abs(b[1] - a[1]) > 1e-6"),),
      rebuild=False),

    M("2d_flat_ratio_world_xz", "2d",
      ("tilt_ladder_warns",),
      "D32's degenerate-frame ratio measures the span across world XZ again, "
      "so a row running UP its own array's slope reads 0.0 surviving the "
      "flatten and a buildable plate ships `pc_warn_degenerate_frame` on all "
      "100 elements - a detector firing on correct work.",
      ((PY % "place.py",
        "    return _len(_flat(_sub(b, a), up_ref)) / span",
        "    return math.hypot(b[0] - a[0], b[2] - a[2]) / span"),),
      rebuild=False),

    # ---- D295: the native chain does not read C3's row attributes ----------
    M("native_reads_no_pc_bays", "native",
      ("output_guard_parity",),
      "The envelope stops refusing a curve carrying `pc_bays`, so the native "
      "chain builds a FREE fence where the reference builds an ALIGNED one - "
      "D122's count has no term in `pc_plan_solve` and a missing term reads "
      "as no constraint. `T4_row_bays_1d` is the case; the guard's rule is "
      "that a build this chain cannot answer takes the reference, and a bay "
      "count it cannot read is exactly that (D223's own argument).",
      ((VEX % "pc_envelope.vfl",
        'if (primattribtype(0, "pc_bays") >= 0) row_2d = 1;',
        'if (0) row_2d = 1;'),)),

    M("native_reads_no_pc_upref", "native",
      ("output_guard_parity",),
      "The same refusal's other half: a curve carrying D296's per-row up axis "
      "is admitted, and `pc_proto.vfl` writes the WORLD up axis there as a "
      "constant - so the native fence is built along an axis the reference "
      "did not use. On `T5_row_upref_1d` that is a 45 degree difference on "
      "every piece.",
      ((VEX % "pc_envelope.vfl",
        "if (up_t >= 0) {",
        "if (0) {"),),
      note="⚠️ THE EDIT IS THE OUTER `if`, not the inner storage test. "
           "Jamming the storage branch shut only sends every input to the "
           "VALUE test, which refuses on its own - the mutation SURVIVES and "
           "reports the refusal as unproven while it is working."),

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

    # ---- the two that were EXEMPT until an audit wrote them ----------------
    # ⚠️ The list said a mutation for both was impractical; an auditor wrote
    # both on the first correct attempt. An exemption is a claim, and a claim
    # in this project is something to falsify, not something to file.

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
      "D286 reverted - X and Y normalised, Z left exactly where the artist "
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

    # ---- P2-9: the 2D node ------------------------------------------------
    #
    # ⚠️ THE THREE DIFFERENTIAL ROWS ARE MUTATED AT THE NODE'S OWN SEAM, not
    # in the builder. A builder edit moves BOTH sides of the comparison and
    # reddens nothing - the shape D296a's ladder had - so every entry here
    # breaks the marshalling between the page and `facade.build*`, which is
    # the only thing the node adds and therefore the only thing this runner
    # can see.

    M("facade_starter_kit_loses_a_cell", "facade",
      ("facade_defaults_build_a_facade",),
      "D315's floor, one cell short: the shopfront stops claiming "
      "`default_start`, so the ground floor takes 7.2.2's lattice walk and "
      "the bare node builds five cells where the kit promises six. The row "
      "asserts the SIX CELLS and the six modules rather than a prim count, "
      "because a stand-in box is geometry too.",
      ((PY % "kit.py", 'roles="default_start")', 'roles="spare")'),),
      rebuild=False),

    M("facade_kit_port_unplugged", "facade",
      ("facade_matches_entry_point",),
      "The kit port dropped: every case builds the starter facade kit while "
      "the oracle builds the one on input 2. It is the broadest of the "
      "three and it proves input 2 is read at all.",
      ((PY % "hda.py",
        "    return kit_geometry(node, parms, fallback=_kit.starter_facade_kit,"
        " say=say)",
        "    return _kit.starter_facade_kit()"),), rebuild=False),

    M("facade_surface_port_unplugged", "facade",
      ("facade_matches_entry_point",),
      "The narrow half of the same claim: only ONE generated case wires a "
      "terrain, so this reddens through that case alone and proves the "
      "fixture reaches input 4 rather than merely declaring it.",
      ((PY % "hda.py", "surface_geo=surface_geo)",
        "surface_geo=None)"),), rebuild=False),

    M("facade_clip_policy_never_reaches_the_build", "facade",
      ("facade_matches_entry_point_area",),
      "7.6's cull policy stuck at `remove`: the five `slice` cases diverge "
      "and the five `remove` ones do not, which is the parm-to-argument "
      "class this runner exists for.",
      ((PY % "hda.py", 'clip_mode=_parm_str(parms, "clip_mode", "remove"),',
        'clip_mode="remove",'),), rebuild=False),

    M("facade_extend_never_reaches_the_build", "facade",
      ("facade_extend_picks_the_fallback",),
      "D117's `Corners Extend Into` stuck at X: the parm stops reaching "
      "`build_many` and both directions build the corner pier. ⚠️ EVERY "
      "OTHER FACADE CASE USES A KIT WITH ALL SIX CELLS, where 7.2.2's "
      "fallback never runs at all - so before this pairing existed the parm "
      "was inert on every fixture the runner had and no differential could "
      "have seen it. The check's kit is missing `corner_end` on purpose.",
      ((PY % "hda.py", 'extend=_parm_str(parms, "extend", "x"),',
        'extend="x",'),), rebuild=False),

    M("facade_payload_port_misread", "facade",
      ("facade_matches_entry_point_payload", "facade_payload_beats_the_page"),
      "D77 on the 2D node, undone: the payload is read off input 4 instead "
      "of input 3, so the page builds the facade and a wired payload does "
      "nothing.",
      ((PY % "hda.py", "style, style_warns = _style.read(payload_geo,",
        "style, style_warns = _style.read(surface_geo,"),),
      rebuild=False),

    M("facade_payload_cannot_override_expand", "facade",
      ("facade_payload_beats_the_page",),
      "D293's precedence broken on ONE key: a payload that names `expand` "
      "loses to the page, so nudging the parm moves a build the payload was "
      "supposed to own. The leak the sweep exists for, one key wide.",
      ((PY % "facade.py", 'expand = settings.get("expand", expand)',
        "expand = expand"),), rebuild=False),

    M("facade_markers_never_refused", "facade",
      ("facade_input_refusals_are_named",),
      "7.9's marker refusal silenced. ⚠️ The obvious edit - renaming "
      "`WARN_MARKERS_IGNORED` - proves NOTHING, because the check reads that "
      "same constant; the guard is what has to go.",
      ((PY % "facade.py",
        "    if geo.findPointAttrib(MARKER_ATTR) is not None:",
        "    if False and geo.findPointAttrib(MARKER_ATTR) is not None:"),),
      rebuild=False),

    M("facade_aux_exclude_not_converted", "facade",
      ("facade_aux_exclude_cuts_the_hole",),
      "D316's port-word to prim-word conversion dropped, so an `exclude` "
      "sub-spline builds like any other and even-odd decides alone.",
      ((PY % "facade.py",
        '            "exclude" if str(p).strip().lower() == "exclude" else c',
        "            c"),), rebuild=False),

    M("facade_stage_rows_shows_the_output", "facade",
      ("facade_stage_menu_reaches_every_stage",),
      "13.7 rule 1: a Stage entry that shows a DIFFERENT stage than it "
      "names. `rows` falls through to the finished build, so two entries "
      "draw the same thing.",
      ((PY % "hda.py", '    if stage == "rows":', '    if stage == "rowsX":'),),
      rebuild=False),

    M("facade_output_port_unlabelled", "facade",
      ("facade_hda_metadata",),
      "5.1b on the 2D asset. It rebuilds, because the label is written into "
      "the .hda at build time and nowhere else - and the build script's own "
      "read-back assertion stays green, which is exactly why the check has "
      "to read the SAVED file rather than trust the script.",
      ((FACADE_BUILD, 'OUTPUT_LABEL = "Facade"', 'OUTPUT_LABEL = "Output"'),)),

    M("facade_height_label_loses_its_unit", "facade",
      ("facade_parm_page_obeys_the_ux_law",),
      "artist_ui 6's ranged/united/helped, on the built asset. A verifier "
      "once stripped the help, the ranges and the units off `pf_polychain` "
      "with every other check green; this is that attack, registered.",
      ((FACADE_BUILD, '"height", "Building Height (m)"',
        '"height", "Building Height"'),)),

    M("facade_height_never_greys_out", "facade",
      ("facade_parm_page_obeys_the_ux_law",),
      "artist_ui 6's RAMP: Building Height means nothing in Boundary Shape "
      "and stops saying so. Greyed out rather than hidden is the rule, and "
      "`hou.Parm.isDisabled()` does not answer it in hython - the assertion "
      "is the saved DialogScript's own `disablewhen`, per parm and by VALUE.",
      ((FACADE_BUILD,
        "    _tpl.setConditional(hou.parmCondType.DisableWhen, _cond)",
        "    _tpl.setHelp(_tpl.help())"),)),

    # ---- P2-9a: the audit's six findings, each with its own edit ----------

    M("facade_y_defaults_name_a_module_again", "facade",
      ("facade_defaults_survive_a_renamed_kit",),
      "P2-9a F1, exactly as it shipped: one Y slot goes back to naming the "
      "STARTER KIT's own module instead of 7.2's role. Any kit that calls "
      "its storey piece something else then resolves that slot against "
      "nothing and the building collapses into 1 m stand-in bands - 858 "
      "prims over 13 rows, page saying `ok`. ⚠️ EVERY OTHER FACADE FIXTURE "
      "IS AUTHORED WITH THE PAGE'S OWN DEFAULT NAMES, which is why the whole "
      "suite agreed with a page that resolved nothing.",
      ((FACADE_BUILD, '"yslot_default", "Repeating Storey", "default",',
        '"yslot_default", "Repeating Storey", "bay",'),)),

    M("facade_page_modules_never_validated", "facade",
      ("facade_page_modules_checked_against_kit",),
      "P2-9a F1's other half: the parm face stops checking its module names "
      "against the kit, so a slot naming a piece no kit has builds stand-in "
      "boxes in silence. `style.read` has validated the PAYLOAD face since "
      "C3a - this is the asymmetry, registered.",
      ((PY % "hda.py",
        "            for warn in _style.kit_gaps(index, rule.slot,"
        " rule.modules, kit):",
        "            for warn in []:"),), rebuild=False),

    M("facade_kit_file_warning_off_the_page", "facade",
      ("facade_kit_file_failure_reaches_the_page",),
      "P2-9a F2: the Kit File failure goes back to `addWarning` alone, which "
      "`cook_facade`'s own block records as reaching NOBODY on this asset. A "
      "typo'd path then builds a plausible building out of the starter kit "
      "and the page says `ok`.",
      ((PY % "hda.py", "kit_geo = facade_kit_geometry(node, parms, say)",
        "kit_geo = facade_kit_geometry(node, parms)"),), rebuild=False),

    M("facade_clip_menu_loses_a_policy", "facade",
      ("facade_clip_menu_is_the_payload_vocabulary",),
      "P2-9a F3: the Boundary Treatment menu drops back to three entries, so "
      "a cull policy the payload face accepts and `row_spans` builds is "
      "unreachable from the parm face - 2.1's two faces disagreeing about "
      "the vocabulary. The menu is built from `CLIP_WORDS` and the check "
      "compares the two, so a hand-written third list cannot creep back.",
      ((FACADE_BUILD,
        '    [(k, _CLIP_LABELS[k]) for k in ("remove", "preserve", "slice",'
        ' "none")',
        '    [(k, _CLIP_LABELS[k]) for k in ("remove", "preserve", "slice")'),
       )),

    M("facade_unknown_purpose_stays_silent", "facade",
      ("facade_unknown_purpose_is_named",),
      "P2-9a F4: D88's silent no-op on D316's port. `_keep(geo, (\"\",))` "
      "keeps the UNTAGGED prims, so a footprint tagged `pc_purpose = "
      "footprint` is deleted and the page blames the artist for not drawing "
      "one. `yspline` is refused by name one branch over; D294 says every "
      "other unknown gets the same courtesy.",
      ((PY % "facade.py",
        "    unknown = sorted(set(purposes) - set(AUX_PURPOSES))",
        "    unknown = []"),), rebuild=False),

    M("polychain_icon_back_to_subnet", "facade",
      ("polychain_assets_carry_5_1_metadata",),
      "5.1a undone on the 1D node - the exact state it SHIPPED in for four "
      "cycles after 5.1 was written about it. The build script's own "
      "assertion is `icon() == ICON` and stays green through this, which is "
      "how it went unnoticed.",
      ((BUILD, 'ICON = "SOP_orientalongcurve"', 'ICON = "SOP_subnet"'),)),


    M("n8_bend_never_welds", "native",
      ("output_guard_parity", "plan_fixture_parity"),
      "D36 undone: each leg is fitted separately where the reference fits "
      "ONE run across the vertex.",
      ((VEX % "pc_sections.vfl",
        "        if (corner && !is_secbreak[i] && (bend || degen)) {",
        "        if (0 && corner && !is_secbreak[i] && (bend || degen)) {"),)),

    M("n8_ring_seam_ignored", "native", ("output_guard_parity",),
      "`_weld` keeps the FIRST section's `s0`: a dissolved ring starts at "
      "the FIRST CORNER, and vertex 0 is a different fill phase.",
      ((VEX % "pc_sections.vfl",
        "            int a = max(seam, 0);", "            int a = 0;"),)),

    M("n8_weld_is_never_whole", "native", ("output_guard_parity",),
      "`_weld`'s `whole` deleted, so a welded ring carries a `cornerAngle` "
      "and ships `pc_sec_closed = 0`. Only the ANGLE is observable - the caps "
      "were already 0 and `Section.closed` moves no placement (31.2).",
      ((VEX % "pc_sections.vfl",
        "        int whole = closed && (abs((s1 - s0) - total) <= 1e-6);",
        "        int whole = 0;"),)),

    M("n8_welded_markers_unsorted", "native", ("output_guard_parity",),
      "A WELDED section re-sorts markers by `s_local`, `decompose` does not.",
      ((VEX % "pc_sections.vfl",
        "        if (welded) {", "        if (0) {"),)),

    M("n8_guard_admits_miter", "native",
      ("output_runs_the_native_chain_inside_the_envelope",
       "output_guard_parity"),
      "[vex:corners] widened too far: MITER admitted, so the chain answers a "
      "build with no assembly and no cut plane in it.",
      ((VEX % "pc_envelope.vfl",
        'if (corners && cmode != "bend") {', "if (0) {"),)),

    M("n8_weld_renumbers_later_sections", "generated",
      ("generated_output_matches_the_reference",),
      "D336 restored: counting SURVIVING spans, where the reference numbers "
      "over ALL the breaks, shifts `pc_sec_index` - and `pc_elem_id`, the "
      "override key - after a dissolved corner. `_kink` (seed 2) reaches it.",
      ((VEX % "pc_sections.vfl",
        "push(r_index, span_ix[k]);", "push(r_index, k);"),)),

    M("n8_guard_reads_the_degeneracy_backwards", "native",
      ("output_guard_parity",),
      "13.9 N8 stage 2's own test inverted: a NON-degenerate miter corner is "
      "admitted (no assembly, no cut plane) and a degenerate one refused.",
      ((VEX % "pc_envelope.vfl",
        "        if (!degen) { corner_refuse = 1; break; }",
        "        if (degen) { corner_refuse = 1; break; }"),)),

    M("n8_miter_keeps_a_degenerate_corner", "native",
      ("output_guard_parity",),
      "D46's SECOND reason dropped: `_joinable` dissolves a degenerate corner "
      "in EITHER mode, so a miter build whose corners are all degenerate gets "
      "the reference's welded section list and the native chain a broken one "
      "(`AV_degenerate_miter`).",
      ((VEX % "pc_sections.vfl", "(bend || degen)", "(bend)"),)),

    M("n8_degenerate_warning_dropped", "native", ("output_guard_parity",),
      "4.3 item F: `_stamp_degenerate` deleted, so a dissolved degenerate "
      "corner builds natively and SILENTLY - the divergence that kept the "
      "whole class refused until stage 2.",
      ((VEX % "pc_plan_emit.vfl",
        "            if (hit) warns = pc_warn_join(warns, PC_W_CORNERDEG);",
        "            if (0) warns = pc_warn_join(warns, PC_W_CORNERDEG);"),)),

    M("n8_degenerate_stamp_ignores_the_ring", "native",
      ("output_guard_parity",),
      "`_stamp_degenerate`'s `reps`: on a CLOSED curve a span can wrap past "
      "the seam, so a vertex is only inside it as `s + total`. Reached by "
      "`AW_ring_section_degenerate` and by nothing else in the corpus.",
      ((VEX % "pc_plan_emit.vfl",
        "                if (!c_closed) continue;",
        "                continue;"),)),

    M("n8_plan_keep_drops_the_degenerate_list", "native",
      ("output_guard_parity",),
      "`PLAN_KEEP` is DENY-BY-DEFAULT: an output `pc_sections` adds that is "
      "not named there is deleted before the solve sees it, and the warning "
      "is simply absent. This is how stage 2 failed its first run.",
      ((RIG, '"^_degen_s ^_curve_closed"', '""'),)),
)

# ⚠️ IDS ARE UNIQUE, ASSERTED HERE. Two entries once shared an id, and the
# resumable state file is keyed by id, so the second silently REPLAYED the
# first's verdict and was never run.
_ids = [m.id for m in MUTATIONS]
assert len(_ids) == len(set(_ids)),     "duplicate mutation id: %s" % sorted(set(i for i in _ids
                                             if _ids.count(i) > 1))


# ---- the coverage meta-check ------------------------------------------------
#
# Every check name a runner prints is PROVEN (a registered mutation was SEEN
# to redden it), EXEMPT (a mutation is impractical, or the check IS one) or
# UNPROVEN (declared, dated debt); a name in none of the three FAILS the
# meta-runner. ⚠️ EXEMPT IS A CLAIM AND THEREFORE A TARGET: it held 36 rows,
# an auditor attacked two of the "impractical" ones and both fell on the first
# correct attempt. The two that remain each apply their own in-line edit and
# assert the break SHOWS, so an edit that stops matching goes RED.

EXEMPT = {
    "native/mutation_pc_arclength":
        "IS a mutation (pc_arclength's merge removed)",
    "native/mutation_pc_unshare":
        "IS a mutation (pc_unshare bypassed)",
}


# ---- the INVENTORY, pinned --------------------------------------------------
#
# ⚠️ HOW MANY CHECK NAMES EACH RUNNER MUST PRINT. Growth already fails the
# sweep (a new name is UNDECLARED); SHRINKAGE was silent until this existed -
# filtering one check out of every 2d case took 40 names to 39 with the sweep
# reporting `0 UNDECLARED`, exit 0.
EXPECT_CHECKS = {
    # ⚠️ THE PER-CYCLE CHANGELOG THAT USED TO LIVE HERE IS DELETED (C3a). It
    # duplicated polychain.md 12 line for line, it grew by a paragraph every
    # cycle, and the budget it was spending is the budget PC-G5's own missing
    # checks needed. 12's cycle entries name every check each cycle added and
    # why; this is the pinned COUNT, and moving a number here is a deliberate
    # act - growth already fails the sweep, shrinkage used not to.
    # ...`array_offplane_m_hostile` is where D290's property moved when
    # D296a stopped it being a containment failure.
    "2d": 43,
    # 13.9 N6 added `conformed_cases_reach_the_native_chain` and
    # `conform_parity_spends_its_tolerance`, both with a mutation.
    "generated": 5,
    "hda": 18,
    "images": 30,
    # C4a restored `output_guard_cost` (F2) - the v2 pass deleted it and 0.0
    # went on citing it, so nothing held a cost ceiling for several cycles.
    "native": 20,
    "scene": 39,
    # 7.7, added 2026-08-25 with 10 mutations covering all 14 names.
    # C1's audit added five, 2026-08-25: 19 names, 15 mutations.
    "slice": 19,
    # P2-9, added 2026-08-26: 11 names, 13 mutations, 0 unproven.
    # +1 name / +1 mutation for `facade_extend_picks_the_fallback` - D117's
    # parm, which needed a kit with a GAP in it before any fixture could
    # reach 7.2.2's fallback at all. 12 names, 14 mutations.
    # P2-9a, the audit: +5 names / +5 mutations, one per finding F1..F4 (F1
    # is two claims and therefore two rows). All five are things the suite
    # could not have seen, and four of the five for the SAME structural
    # reason - every fixture kit was authored with the page's own default
    # module names, so the page and the oracle resolved the same nothing.
    # 17 names, 19 mutations.
    "facade": 17,
}


# ---- the DATED DEBT ---------------------------------------------------------
#
# ⚠️ NOT AN EXEMPTION LIST. An EXEMPTION says "a mutation for this is
# genuinely impractical, and here is the reason"; a DEBT ENTRY says "nobody
# has written the mutation yet". After the v2 deletion pass it holds 76 names
# of 122 (it was 283 of 361), and it shrank because the checks it described
# were DELETED, not because they were proven. Four groups, reasons below.

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
), "a measured COST ceiling: the number IS the assertion, but nothing "
    "yet MUTATES the code path to prove it bites - debt, not proof."))

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
), "a gate figure's own row: the gate is the IMAGE plus D194's drawn-"
    "primitive count and the human at the milestone judges it; only the "
    "`image_shows_packed_*` rows have a mutation."))

UNPROVEN.update(dict.fromkeys((
    "hda/every_number_has_a_range",
    "hda/every_parm_has_help",
    "hda/two_disclosure_levels",
    "hda/units_in_the_label",
), "artist_ui 6 on the built asset. A verifier once stripped the help, "
    "the ranges and the units with every other check green, which is why "
    "these exist; no mutation is registered for them yet."))

UNPROVEN.update(dict.fromkeys((
    "2d/corner_abut_m",
    "2d/corner_breach_m",
    "2d/packed_pieces",
    "generated/generated_cases_reach_the_native_chain",
    "hda/evenly_clears_the_corner_adjust_to_end",
    "hda/evenly_clears_the_corner_justify_center",
    "hda/evenly_clears_the_corner_justify_start",
    "native/every_stage_has_a_second_source",
), "no mutation yet"))
