"""Run every polyChain PHASE 2 check in a throwaway Houdini session.

    hython tests/polychain/run_2d_checks.py
    hython tests/polychain/run_2d_checks.py --update-baseline
    hython tests/polychain/run_2d_checks.py --json results.json

Same contract as `run_scene_checks.py` - numbers first, baseline diffed, no
.hip - and its own baseline file so a phase-2 movement can never be confused
with a phase-1 one.

⚠️ MOST OF THE CHECKS HERE ARE PHASE 1'S OWN, RUN UNCHANGED, and that is
the architecture: a 2D array IS a phase-1 build over a stream of row curves.
A check that had to be FORKED to pass on a facade would mean the row stack had
become a second kernel (D130), so the reuse is the assertion.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import cases                                                     # noqa: E402
import cases2d                                                   # noqa: E402
import checks as C                                               # noqa: E402
import hou                                                       # noqa: E402
import run_scene_checks as R                                     # noqa: E402
from polyfactory.polychain import place as P                      # noqa: E402

BASELINE = os.path.join(HERE, "baseline_2d.json")

# What each case is ALLOWED to warn about, and why. An empty tuple is the
# assertion "this facade builds clean"; the non-empty ones are the cases that
# exist to prove the lattice's detectors are not vacuous.

EXPECTED_WARNS = {
    # 7.2.2's walk, taken four times: the kit has no ground floor and no
    # cornice, so `default_start`, `corner_start`, `default_end` and
    # `corner_end` all degrade - and every element that took one says so.
    "FD_role_fallback": ("pc_warn_role_fallback",),
    "FF_extend_x": ("pc_warn_role_fallback",),
    "FG_extend_y": ("pc_warn_role_fallback",),
    # ...and the Y `corner` row's own two cells, which no kit in the suite has
    # (`default_corner`, `corner_corner`).
    "FH_y_corner": ("pc_warn_role_fallback",),
    # ...and the end of the walk: a kit with only a corner column has no
    # `default` at all, so 3.4's blank box arrives WITH the fallback warning
    # beside it (PC-G5 condition 5). It also OVERFLOWS: 3.4's stand-in is a
    # 1 m nominal box, so a 0.6 m corner reserve on a 12 m leg leaves the run
    # asking for more than the section holds. D13's cascade doing its job, and
    # the honest cost of a kit with nothing in it.
    "FE_stand_in": ("pc_warn_kit_gap", "pc_warn_overflow",
                    "pc_warn_role_fallback"),
    # `evenly` is a row class like any other, so a string course produces
    # `default_evenly` and `corner_evenly` cells - which this kit does not
    # have, so they take the walk. The warning IS the feature.
    "FI_y_evenly": ("pc_warn_role_fallback",),
    # ⚠️ FB DOES NOT WARN, AND THAT IS THE ASSERTION. Bend mode welds the L
    # into one ring (D36) and a 3 m bay then spans a 90 degree vertex - but
    # the bay is `vertical`, i.e. yaw-only, so D27 short-circuits the deform
    # gate before any station has to resolve the turn. A returning
    # `pc_warn_bend_resolution` here means a bay started riding the corner.
    "FB_L_bend": (),
    # D139's two channels, and they are the whole reason FT/FU exist. A
    # warning the Y SOLVE raised belongs to the ROW, so it is renamed on the
    # way out and then carried onto every element the row produced. ⚠️ THE
    # NAMES ARE THE ASSERTION: `pc_warn_overflow` here would mean the element
    # is claiming ITS OWN X run overflowed, when what actually happened is
    # that a whole storey is missing.
    "FT_row_overflow": ("pc_warn_row_overflow",),
    "FU_row_kit_gap": ("pc_warn_row_kit_gap",),
    "FV_area_short": (),
    # 7.4's own degrade, and both names are the assertion. An X `evenly` rule
    # puts anchors on every section, so D122's one-count-per-section cannot
    # say which run holds how many and the row falls back to its free solve -
    # `pc_warn_y_align_lost` on every piece of it. The role fallback beside it
    # is `default_evenly` / `corner_evenly`, cells this kit does not have.
    "FX_y_align_lost": ("pc_warn_role_fallback", "pc_warn_y_align_lost"),
}


Scene = R.Scene


def run_case(name, case):
    """Phase 2's own three properties, plus phase 1's checks run UNCHANGED.

    ⚠️ v2: this used to call 30 checks per case, 26 of which were phase 1's
    own value comparisons re-run over row curves - which `diff.compare` does
    by construction, and which `run_generated.py` does on generated input.
    The reuse was the assertion that no second kernel appeared; the four
    kept calls make the same statement (they ARE phase 1's functions,
    imported, not re-implemented) at a thirtieth of the cost.
    """
    try:
        scene = Scene(case)
    except Exception as exc:
        return [C.Result("scene", False, None, "%s: %s"
                         % (type(exc).__name__, str(exc)[:200]))]
    return [
        # phase 1's own, unchanged - the reuse IS the assertion that no
        # second kernel appeared (D130).
        C.instancing_split(scene, expect_all=False, expect_none=False),
        C.corner_abut(scene),
        C.corner_breach(scene),
        C.warnings(scene, EXPECTED_WARNS.get(name, ())),
        # ...and 7's own: the clip TRANSFER, which is the first unfailable
        # check this project ever recorded and the one the registry's
        # `2d_clip_stamp_zeroed` is paired against.
        C.clip_stamp(scene),
        # PC-G5 condition 4, on every case rather than on the gate figure
        # alone: adaptive on both axes fits whole modules, so a slice_t
        # anywhere in phase 2 is a defect wherever it appears.
        C.no_sliced_cells(scene),
    # ⚠️ THE TWO MODES GET TWO CHECK NAMES. The registry credits a mutation to
    # the check NAME it reddens, and `free` and `aligned` are two different
    # claims about two different code paths - one name for both would let the
    # `free` case's own mutation report D122 as proven.
    ] + ([C.bay_alignment(scene, aligned=Y_ALIGNED[name],
                          name="bay_alignment_aligned" if Y_ALIGNED[name]
                          else "bay_alignment")]
         if name in Y_ALIGNED else [])


# PC-G5 condition 3 on TWO cases: it compares rows to each other and says
# something only where they CAN differ. False is the `free` mode's inverted
# form (7.8); D122's `aligned` is the True entry on the SAME fixture, so the
# condition is answered in both directions rather than asserted in one.
Y_ALIGNED = {"FW_y_free": False, "FW_y_aligned": True}


def gate_pc_g6():
    """PC-G6, 7.8's five conditions, each as a number. Its own function
    rather than a `build_all` case because condition 4 is a property of a
    PAIR of builds - the same clip input with one sub-spline edited."""
    a = cases2d.clip_case()
    scene = Scene(a)
    # sub-spline B (the hole) grown 0.5 m: array A000 must change and the
    # disjoint A003 must not move one id.
    moved = list(cases2d.CLIP_LOOPS)
    moved[1] = [(6, 2.0, 0), (9.5, 5, 0), (6, 8.0, 0), (2.5, 5, 0)]
    # ...and the same input with sub-spline B told to INCLUDE, which is 7.6's
    # per-spline override of the even-odd result - a branch nothing else runs.
    over = cases2d.clip_case(modes=["", "include", "", ""])
    return [
        C.clip_inside_m(scene),
        C.clip_nesting(scene),
        C.clip_caps_closed(scene),
        C.clip_policy(scene),
        C.clip_independence(a, cases2d.clip_case(moved), "A000"),
        C.clip_mode_override(a, over),
        # ...and the OTHER cull policy, on a kit that says nothing about
        # clipping. Without it `preserve` and D126's array-decides branch are
        # both code that no committed run reaches.
        C.clip_preserve(Scene(cases2d.clip_case(clip_mode="preserve",
                                                kit_clip=-1))),
        # D145's channel, PINNED: `pc_warn_clip_convex` fires on exactly one
        # element here - a piece the diamond's vertex falls inside, where an
        # intersection of half-spaces takes more than the polygon does. A
        # declared warning no run raises gets deleted by accident (D139).
        C.warnings(scene, ("pc_warn_clip_convex",)),
    ]


def gate_pc_g6_hostile():
    """PC-G6's own conditions on the input the SHIPPED FIXTURE cannot be.

    C2a's audit: every loop in `CLIP_LOOPS` is counter-clockwise and on the
    origin, and both accidents were load-bearing - reversed, the whole array
    was built one module-height out of its footprint with 57 mutations green;
    500 m out, the cap guard's piece-scaled tolerance deleted 7 of 8 genuine
    caps. One build carries both, because citygen has both. ...and the
    validation station, declared over two cycles and asserted nowhere."""
    hostile = Scene(cases2d.clip_case(loops=cases2d.clip_loops_hostile()))
    bad = cases2d.clip_case(loops=cases2d.CLIP_BAD_LOOPS,
                            open_at=(1,), groups=(0,))
    return [
        C.clip_inside_m(hostile, name="clip_inside_m_hostile"),
        # D290's own number, on the fixture that carries the reversed winding.
        C.array_offplane_m(hostile, name="array_offplane_m_hostile"),
        C.clip_caps_closed(hostile, name="clip_caps_closed_hostile"),
        # ⚠️ FOUR NAMES, NOT FIVE: `pc_warn_clip_tilted` is RETIRED with the
        # defect it announced (D296). `CLIP_BAD_TILTED` stays in the input and
        # is now simply a legal loop - the array it defines builds inside its
        # own region, which `tilt_ladder_offplane_m` is what says.
        C.clip_input_warns(bad, ("pc_warn_clip_group_ignored",
                                 "pc_warn_clip_nonplanar",
                                 "pc_warn_clip_open",
                                 "pc_warn_clip_selfx")),
        # ...and the control: the SHIPPED fixture says none of the five, so
        # the row above is proving detection rather than a constant.
        C.clip_input_warns(cases2d.clip_case(), (),
                           name="clip_input_warns_clean"),
        # ⚠️ AND ON THE MITER PATH, ON THE DISTRICT. The same piece-scaled
        # tolerance left 6 400 mitered elements carrying 18 776 OPEN BOUNDARY
        # EDGES, with every corner check green because they measure where a
        # face LANDS and none asked whether the solid closed. It has to be the
        # DISTRICT: PC-G5's L spans 0..24 m, too near the origin for float32
        # round-off to reach the old tolerance, so the check reads [0 open]
        # there under the mutation - measured before this row was written.
        C.clip_caps_closed(cases2d.build_many_buildings(True)[0],
                           name="caps_closed_mitered"),
    ]


def tilt_ladder():
    """7.6 / D296 - an area array builds inside its own region AT EVERY TILT,
    and stays PACKED while it does.

    Three numbers over the whole ladder, worst row wins, because a per-rung
    row would be twelve names saying one thing. The (0, 0, 0) rung is in the
    ladder deliberately: "nothing that ever ran may move" is a measurement,
    not an assumption.

    The BEFORE column for the six single-axis rungs is in
    `array2d.frame_tilt_deg`'s note (0.005235 -> 0.0 at 2 deg through
    1.850000 -> 0.0 at 90) and is what makes the AFTER column mean something.

    ⚠️ AND THAT LADDER PROVED ONE PARAMETER (C3's audit, F1): every rung
    of it holds `frame.ex` at exactly +X, so `place`'s three remaining
    world-axis spellings cancelled. On HEAD 1a3f1ce the same plate started at
    its SECOND vertex read inside 0.064952 / offplane 0.962501 at 30 deg, and
    a two-axis roll read up to 1.969616 - 12's Cycle C3a has the table. The
    shear test was world-Y too, so those rungs delivered 350 REAL prims where
    the plate is 100 packed ones (`tilt_ladder_packed`, which no containment
    number sees).

    WHAT IT CANNOT SEE: whether the region itself is right (`clip_nesting`'s
    job); any tilted array that is not an axis-aligned plate; and the TILTED
    behaviour of `_stepped_base` / `_y_varies`, which this rigid unbanded kit
    never runs - what holds those is the phase-1 baseline proving them
    bit-identical at `up_ref = UP`.
    """
    worst_in, worst_off, unpacked, noisy, res = None, None, [], [], []
    for rung in cases2d.TILT_LADDER:
        scene = Scene(cases2d.clip_case(loops=[cases2d.tilt_plate(*rung)],
                                        clip_mode="remove"))
        a, b = C.clip_inside_m(scene), C.array_offplane_m(scene)
        # the plate is rigid modules on a straight row, so every piece the
        # region keeps must still be an instance - and a legal plate at any
        # tilt builds CLEAN (`_flat_ratio` measured the span across world XZ,
        # so a row running up its own slope warned on all 100 elements).
        if not C.instancing_split(scene, expect_all=True).ok:
            unpacked.append("%g/%g/%d" % rung)
        if not C.warnings(scene, ()).ok:
            noisy.append("%g/%g/%d" % rung)
        if worst_in is None or a.value > worst_in.value:
            worst_in = a
        if worst_off is None or b.value > worst_off.value:
            worst_off = b
    # ...and the SECOND writer: `_packed_transform` and `_deform_positions`
    # are two functions, so a ladder that never cuts a piece proves one of
    # them - the deform writer's own mutation survived the rungs above by
    # reddening nothing at all.
    n_deformed = 0
    for rung in cases2d.TILT_DEFORM:
        scene = Scene(cases2d.clip_case(loops=cases2d.tilt_loops(*rung)))
        n_deformed += scene.report["deformed"]
        a, b = C.clip_inside_m(scene), C.array_offplane_m(scene)
        if a.value > worst_in.value:
            worst_in = a
        if b.value > worst_off.value:
            worst_off = b
    res.append(C.Result("tilt_ladder_deformed", n_deformed > 0, n_deformed,
                        "%d cut pieces took the deform writer over %d rungs "
                        "of PC-G6's own loops (floor 1 - a ladder that cuts "
                        "nothing measures one of the two writers)"
                        % (n_deformed, len(cases2d.TILT_DEFORM))))
    rungs = " ".join("%g/%g/%d" % t for t in cases2d.TILT_LADDER)
    for r, name in ((worst_in, "tilt_ladder_inside_m"),
                    (worst_off, "tilt_ladder_offplane_m")):
        res.append(C.Result(name, r.ok, r.value,
                            "worst of %d plate + %d cut rungs (rx/rz/start "
                            "%s): %s" % (len(cases2d.TILT_LADDER),
                                         len(cases2d.TILT_DEFORM), rungs,
                                         r.detail)))
    for bad, name, what in ((unpacked, "tilt_ladder_packed",
                             "unpacked a piece the region kept"),
                            (noisy, "tilt_ladder_warns", "warned")):
        res.append(C.Result(name, not bad, len(bad),
                            "%d of %d rungs %s%s"
                            % (len(bad), len(cases2d.TILT_LADDER), what,
                               "" if not bad else ": " + ", ".join(bad))))
    return res


def payload_face():
    """2.1's PIPELINE FACE on the 2D path - P2-4, D293.

    Three questions, and the middle one is the gate: does a 7.3.2 payload
    express everything the 2D entry point's keywords express (round trip),
    does it OVERRIDE them (the sweep, with its own control), and does it
    refuse by name what 7.6 does not build instead of answering wrong.
    """
    def build(nudge, payload):
        return cases2d.payload_build(nudge, payload)[0]
    return [
        C.payload_round_trip_2d(build(None, False), build(None, True)),
        # ⚠️ `none`, AND TWO MEASUREMENTS PICKED IT. `remove` is
        # `build_clipped`'s own default, so a payload that stopped overriding
        # `clip_mode` left the base build on exactly the value this row nudges
        # to and the sweep read [0, 3, 3] with the payload deleted -
        # `2d_payload_does_not_override` SURVIVED it. And `preserve` is not a
        # nudge either: it and `slice` produce identical ROW SPANS, and this
        # kit's modules carry `pc_clip = 2`, so the array's policy never
        # decides anything - [0, 2, 3], the parm measurably not live. `none`
        # is the one value neither a default nor a module can coincide with.
        C.parms_inert_under_payload(build, [{"clip_mode": "none"},
                                            {"expand": 1.5},
                                            {"auto_align": "to_spline"}]),
        # 7.3.2's six `clip` keys, hostile: one the 2D path cannot build at
        # the value asked (`cap_holes = 0`), one whose only buildable value is
        # the default (`hierarchy`), and one that is not a 7.3.2 key at all.
        C.clip_input_warns(
            {"report": cases2d.payload_build(
                payload=True, clip={"cap_holes": 0, "hierarchy": "none",
                                    "nosuchkey": 1})[1]},
            ("pc_warn_payload_malformed", "pc_warn_payload_refused"),
            name="payload_input_warns"),
        # D300 - and the TOP LEVEL, where those same settings live under their
        # KEYWORD names one nesting level up.
        C.payload_meta_warns(
            cases2d.payload_build(payload=True,
                                  meta={"expand": 3.0, "y_parms": {}})[2],
            cases2d.payload_build(payload=True)[2],
            ("pc_warn_payload_malformed",)),
    ]


def gate_pc_g5():
    """PC-G5's two conditions the v2 deletion pass left with no check at all.

    C3a measured all seven on the shipped build; five already have standing
    names (1 `corner_abut`/`corner_breach`, 3 `bay_alignment*`, 4
    `no_sliced_cells`, 5 `warnings` with an EMPTY set on the gate figure, 7
    `packed_pieces`). Conditions 2 and 6 had `cell_grid` and `structural_ids`,
    both deleted in the v2 pass with 7.8 still pointing at them."""
    def facade(footprint):
        return cases2d.case(footprint, cases2d.facade_kit(),
                            cases2d.facade_style())
    L = cases2d.L_FOOTPRINT
    rev = list(reversed(L))
    return [
        C.row_closure(Scene(facade(L))),
        # condition 6, and BYTE-IDENTICAL is stronger than the id SET it asks
        # for. The comparand is reversed AND re-authored from another vertex,
        # so one name covers both of D124's permutations.
        C.payload_round_trip_2d(facade(L)["out"],
                                facade(rev[2:] + rev[:2])["out"],
                                name="structural_ids"),
    ]


def align_scope():
    """7.4's ALIGNED where it must change NOTHING - C3a's D297/D298/D299.
    Three pairs one `y_mode` apart, each against its own free twin;
    `FW_y_aligned`'s [0, 4] is the control that says the mode is live."""
    def facade(aligned, ground_x=cases2d.BAY_X, extra=()):
        return cases2d.case(
            cases2d.L_FOOTPRINT, cases2d.facade_kit(ground_x=ground_x),
            cases2d.facade_style(extra=list(extra),
                                 meta={"y_mode": "aligned"} if aligned
                                 else None))["out"]

    def area(aligned):
        return cases2d.F.build_clipped(
            cases2d.clip_geometry(cases2d.HOLED_PLATE), cases2d.clip_kit(),
            cases2d.clip_style(), height=None, clip_mode="remove",
            y_mode="aligned" if aligned else "free")[0]
    seq = [cases2d.Rule("default", "sequence", ["bay", "pier"])]
    # D297 the area path, where the datum is a SPAN: refusing `aligned` there
    # was proposed and DECLINED, and this row is the measurement (12's Cycle
    # C3a). D298 a SEQUENCE rule (`pc_bays` counts bays, `fit` units); D299 a
    # 0.6 m ground bay the storeys above it cannot hold.
    return [C.payload_round_trip_2d(a, b, ("y_align_lost", "pc_warnings"), n)
            for a, b, n in (
                (area(False), area(True), "align_no_op_area"),
                (facade(False, extra=seq), facade(True, extra=seq),
                 "align_no_op_sequence"),
                (facade(False, ground_x=0.6), facade(True, ground_x=0.6),
                 "align_no_op_floor"))]


def tripwires():
    """11.9's rules 1 and 2, on the shapes phase 2 actually has.

    ⚠️ THE MANY-SHORT-ROWS ROW IS THE ONE THAT CAN FAIL, and it is here from
    this cycle rather than from PC-G7 because a per-call fixed cost is
    invisible on the one tall tower an implementer writes first.
    """
    terrain = cases2d.terrain()
    # prime the row cache OUTSIDE the spy: the fixture builds a kit, and
    # `K.add_module` writes its manifest through point wrappers by design.
    cases2d.tripwire_row_emission()
    return [
        C.rows_wrappers_built(cases2d.tripwire_row_emission, hou),
        C.ray_executions_per_build(
            lambda: cases2d.build_many_buildings(True, terrain), hou,
            name="ray_executions_per_build_2d_rows"),
        C.ray_executions_per_build(
            lambda: cases2d.tripwire_one_tower(), hou,
            name="ray_executions_per_build_2d_tower"),
        # ⚠️ THIS CEILING IS 11.9's P7 AT FACADE SCALE, AND IT IS A LADDER
        # ROW, NOT A FLOOR. 100 buildings x 4 vertices x 8 rows x 2 halves =
        # 6 400 MITERED pieces, and `clip_plane`'s cap tagging plus
        # `dress_caps` are real per-prim loops (`prims_wrappers_built_mitered`
        # reads 571 for ONE rectangle). P7 is the unattempted 11.8 item that
        # would lower it; nothing phase 2 added is in this number, and the row
        # exists so that stops being true visibly rather than silently.
        C.prims_wrappers_built(lambda: cases2d.build_many_buildings(True),
                               hou, expect_max=5000,
                               name="prims_wrappers_built_2d_rows"),
        C.points_wrappers_built(lambda: cases2d.build_many_buildings(True),
                                hou, expect_max=8,
                                name="points_wrappers_built_2d_rows"),
        # ⚠️ THE COUNTER THE OTHER FOUR COULD NOT REACH. `Prim.points` +
        # `Point.position` + `*.attribValue` - reads through a wrapper, which
        # is neither a wrapper materialised through `hou.Geometry` nor a
        # wrapper WRITE. It read 159 242 + 220 488 + 19 150 + 44 256 on this
        # fixture while `points_wrappers_built_2d_rows` said 0 (ceiling 8),
        # which is 11.9 rule 1's own instruction being unanswerable. P7's two
        # bulk rewrites (`clip_plane`'s cap tag, `dress_caps`' cap search) are
        # what the number is now.
        C.wrapper_reads(lambda: cases2d.build_many_buildings(True), hou,
                        expect_max=100000, name="wrapper_reads_2d_rows"),
        # `clip` + `polyfill`, pinned the way `ray` is: 6 400 mitered pieces
        # take 2 executions each and each one rebuilds its own input. A fourth
        # verb name appearing here is 11.9's "three verbs" quietly becoming
        # four.
        C.verb_executions_per_build(
            lambda: cases2d.build_many_buildings(True), P, expect_max=20000,
            name="verb_executions_per_build_2d_rows"),
        C.polyfill_appends_its_patches(P, hou),
    ]


def main():
    update = "--update-baseline" in sys.argv
    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]

    built = cases2d.build_all()
    results, failures = {}, 0
    for name in sorted(built):
        res = run_case(name, built[name])
        results[name] = [r.as_dict() for r in res]
        print("\n=== %s ===" % name)
        for r in res:
            print("  %r" % r)
            if not r.ok and not r.skipped:
                failures += 1

    for label, fn in (("ZY_align_scope", align_scope),
                      ("ZY_gate_pc_g5", gate_pc_g5),
                      ("ZY_gate_pc_g6", gate_pc_g6),
                      ("ZY_gate_pc_g6_hostile", gate_pc_g6_hostile),
                      ("ZY_payload_face", payload_face),
                      ("ZY_tilt_ladder", tilt_ladder),
                      ("ZZ_2d_tripwires", tripwires)):
        res = fn()
        results[label] = [r.as_dict() for r in res]
        print("\n=== %s ===" % label)
        for r in res:
            print("  %r" % r)
            if not r.ok and not r.skipped:
                failures += 1

    base = {}
    if os.path.exists(BASELINE):
        with open(BASELINE) as fh:
            base = json.load(fh)
    # D210, the second half: this runner carried the IDENTICAL advisory
    # baseline - a moved value printed and `1 if failures and not update`
    # exited 0 anyway. It is `run_scene_checks`' rule now, imported rather
    # than copied, because a copied exit rule is how the phase-1 runner and
    # this one drifted apart in the first place.
    moved = R.baseline_movement(results, base)
    if moved:
        print("\n--- MOVED SINCE BASELINE: %d value(s) ---" % len(moved))
        for m in moved:
            print("  " + m)
        print("  ^ each must be an improvement; confirm, then re-run with"
              " --update-baseline")
    if update:
        with open(BASELINE, "w") as fh:
            json.dump(results, fh, indent=2, sort_keys=True)
        print("\nbaseline written: %s" % BASELINE)
    if json_out:
        with open(json_out, "w") as fh:
            json.dump(results, fh, indent=2, sort_keys=True)
    print("\n%d failing checks, %d moved baseline values"
          % (failures, len(moved)))
    sys.exit(R.exit_code(failures, moved, update))


if __name__ == "__main__":
    main()
