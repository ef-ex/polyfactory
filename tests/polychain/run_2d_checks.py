"""Run every polyChain PHASE 2 check in a throwaway Houdini session.

    hython tests/polychain/run_2d_checks.py
    hython tests/polychain/run_2d_checks.py --update-baseline
    hython tests/polychain/run_2d_checks.py --json results.json

Same contract as `run_scene_checks.py` - numbers first, baseline diffed, no
.hip - and its own baseline file so a phase-2 movement can never be confused
with a phase-1 one.

⚠️ MOST OF THE CHECKS HERE ARE PHASE 1'S OWN, RUN UNCHANGED. That is the point
of the whole architecture: a 2D array IS a phase-1 build over a stream of row
curves, so `exact_fill_m`, `max_gap_m`, `corner_seam_m`, `instancing_split`,
`determinism` and `geometry_digest` apply to it verbatim. If a check in that
list had to be forked to pass on a facade, the row stack would have stopped
being a row stack and become a second kernel (D130) - so the reuse is not a
convenience, it is the assertion.
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
    # ...and the end of the walk. A kit with only a corner column has no
    # `default` at all, so 3.4's blank box arrives - WITH the fallback warning
    # beside it, which is PC-G5 condition 5 (`role_fallbacks` asserts the
    # second number is 0).
    # ...and the end of the walk, which also OVERFLOWS: 3.4's stand-in is a
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
}



class Scene(R.Scene):
    """`run_scene_checks.Scene` plus the two things only a 2D build has."""

    def __init__(self, case):
        R.Scene.__init__(self, case)
        self.frame = case["report"].get("frame")

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
    ] + ([C.bay_alignment(scene, aligned=Y_ALIGNED.get(name, False))]
         if name in Y_ALIGNED else [])


# PC-G5 condition 3, and it runs on ONE case on purpose: it is a comparison
# between rows, and it says something only where the rows CAN differ. False =
# the `free` mode's inverted form ("at least one row differs, or the fixture
# is not exercising the mode" - 7.8). D122's `aligned` will add its own entry
# at True when C3 lands.
Y_ALIGNED = {"FW_y_free": False}


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

    res = tripwires()
    results["ZZ_2d_tripwires"] = [r.as_dict() for r in res]
    print("\n=== ZZ_2d_tripwires ===")
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
