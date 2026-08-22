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
}

# 7.2's headline, as an inventory rather than a total: WHICH cells the figure
# produced. Derived from the figure and not read off a run - an L footprint in
# miter mode has 6 vertices x 2 halves = 12 corner elements per row, and 5
# rows of which one is `start`, three `default` and one `end`.
CELLS = {
    "FA_L_facade": {"default", "corner", "default_start", "corner_start",
                    "default_end", "corner_end"},
    "FC_rect": {"default", "corner", "default_start", "corner_start",
                "default_end", "corner_end"},
    # bend mode welds the ring, so there is no corner slot at all - the
    # control that says FA's corner cells are the corner MODE's doing and not
    # the lattice inventing them.
    "FB_L_bend": {"default", "default_start", "default_end"},
    "FD_role_fallback": {"default", "corner", "default_start", "corner_start",
                         "default_end", "corner_end"},
    # ⚠️ THE FIFTH COLUMN, THE ONE RAILCLONE OMITS. A Y `corner` row (D134 -
    # a profile vertex, i.e. a setback line) crosses the X `corner` column, so
    # `corner_corner` and `default_corner` are cells and the 25-role table is
    # exercised end to end. The profile this case shipped with turned 9.46
    # degrees - under `corner_angle_deg` - so it produced no `corner` row at
    # all and this whole column was assumed rather than asserted.
    "FH_y_corner": {"default", "corner", "default_start", "default_end",
                    "corner_start", "corner_end",
                    "default_corner", "corner_corner"},
    # the suppressed reflex vertex: 5 faces instead of 6, same six cells.
    "FN_flags": {"default", "corner", "default_start", "corner_start",
                 "default_end", "corner_end"},
    "FO_flags_reversed": {"default", "corner", "default_start", "corner_start",
                          "default_end", "corner_end"},
    "FP_flags_rotated": {"default", "corner", "default_start", "corner_start",
                         "default_end", "corner_end"},
    "FR_rule_scoped": {"default", "corner", "default_start", "corner_start",
                       "default_end", "corner_end"},
    "FS_sequence_cells": {"default", "corner", "default_start", "corner_start",
                          "default_end", "corner_end"},
}

# ...and WHICH MODULE each cell was filled with, which is the half an
# inventory cannot see: a lattice that resolved every cell to `bay` would pass
# `cell_inventory` and fail here.
CELL_MODULES = {
    "FA_L_facade": {"default": ["bay"], "corner": ["pier"],
                    "default_start": ["shopfront"],
                    "corner_start": ["pier_base"],
                    "default_end": ["cornice"], "corner_end": ["pier_cap"]},
    # the SAME figure with a kit that has none of the four: everything
    # degrades one step down the lattice, Y first (7.2.2).
    "FD_role_fallback": {"default": ["bay"], "corner": ["pier"],
                         "default_start": ["bay"], "corner_start": ["pier"],
                         "default_end": ["bay"], "corner_end": ["pier"]},
    # the walk running out: no module claims `default` at all, so 3.4's blank
    # box arrives in every non-corner cell and says both warnings.
    "FE_stand_in": {"default": ["default"], "corner": ["pier"],
                    "default_start": ["default_start"],
                    "corner_start": ["pier"],
                    "default_end": ["default_end"], "corner_end": ["pier"]},
    # D117's two answers, one integer apart. Both kits have a cornice and no
    # pier cap; `pc_extend = 1` (the default) keeps the COLUMN through the
    # cornice band, `pc_extend = 0` stops the column at it and the cornice
    # runs on.
    "FF_extend_x": {"default": ["bay"], "corner": ["pier"],
                    "default_start": ["bay"], "corner_start": ["pier"],
                    "default_end": ["cornice"], "corner_end": ["pier"]},
    "FG_extend_y": {"default": ["bay"], "corner": ["pier"],
                    "default_start": ["bay"], "corner_start": ["pier"],
                    "default_end": ["cornice"], "corner_end": ["cornice"]},
    # the Y-corner column, and what fills it: this kit has neither
    # `default_corner` nor `corner_corner`, so both take the lattice walk and
    # say so (`role_fallbacks` reads 68, `fallback_map` names all four).
    "FH_y_corner": {"default": ["bay"], "corner": ["pier"],
                    "default_start": ["shopfront"], "corner_start": ["pier"],
                    "default_end": ["cornice"], "corner_end": ["pier"],
                    "default_corner": ["bay"], "corner_corner": ["pier"]},
    # E1/D119 on both slots: `pier_cap` ONLY on the cornice row. The unscoped
    # `["pier"]` rule names a module, so it beats the cell role on the ground
    # row too - which is the rule saying what it says.
    "FR_rule_scoped": {"default": ["bay"], "corner": ["pier"],
                       "default_start": ["shopfront"], "corner_start": ["pier"],
                       "default_end": ["cornice"], "corner_end": ["pier_cap"]},
    # ...and the `sequence` selector resolving the CELL role: the ground floor
    # is the shopfront, not the 3.2 m bay stretched into a 4.0 m band.
    "FS_sequence_cells": {"default": ["bay"], "corner": ["pier"],
                          "default_start": ["shopfront"],
                          "corner_start": ["pier_base"],
                          "default_end": ["cornice"],
                          "corner_end": ["pier_cap"]},
}

# 7.2.2's "naming both roles", per case: which cell walked to which role.
FALLBACKS = {
    "FA_L_facade": [],
    "FF_extend_x": [("corner_end", "corner"), ("corner_start", "corner"),
                    ("default_start", "default")],
    "FG_extend_y": [("corner_end", "default_end"), ("corner_start", "corner"),
                    ("default_start", "default")],
}

# PC-G5 condition 7, and its ONE legitimate exception per case. A scaled
# storey must stay a packed prim (D121) - the whole point of making the Y fit
# an axis scale - so anything unpacked has to be named with its reason.
# FB is BEND mode: D36 welds the L into one ring, so one bay wraps each of the
# 6 vertices on each of the 2 scaled rows. That is the mode working, and it is
# also why FA (miter) reads 0: there the corner is a cut, not a bend.
BENT = {"FB_L_bend": 12,
        # 7.5: a SUPPRESSED vertex is "a curved facade with no corner
        # geometry", so the two legs either side of the L's reflex vertex are
        # one section and the bay that spans the turn is deformed. That is the
        # flag doing its job - and it is why these three cases prove the flag
        # reached the vertex the artist named, in all three re-authorings.
        "FN_flags": 2, "FO_flags_reversed": 2, "FP_flags_rotated": 2}

# D124 / PC-G5 condition 6 - the same footprint, re-authored two ways.
REAUTHORED = {"FA_L_facade": ("FJ_reversed", "FK_rotated"),
              # ...and the same three re-authorings WITH `pc_corner` flags on.
              # FJ/FK carry none, so the only committed identity check ran on
              # the one input where authored and canonical order happen to
              # coincide - and the flags were being indexed by canonical
              # position while the points had already been permuted (D124).
              "FN_flags": ("FO_flags_reversed", "FP_flags_rotated")}

# 7.6 - how far outside the boundary a piece is ALLOWED to sit. `remove` is
# 0 by definition ("nothing crosses the line"); `preserve` is "kept whole and
# may overhang", so a number here is the mode working and the sharp assertion
# moves to `clip_hole_elements` (nothing wholly outside).
CLIP_TOL = {
    # the U panel's ground band runs 0..4 m: the boundary is solid across at
    # y = 0 and notched from y = 3, so a preserved bay standing on the solid
    # part overhangs 1.0 m of notch at its top. That IS `preserve`.
    "FQ_area_preserve": 1.0,
}

# D142 - rows the SOLVE produced that the clip boundary left nothing of. Named
# per case with its reason, the way `BENT` names bend mode's unpacked pieces;
# `cell_grid` takes its row list from the solve so an unbuilt one is a HOLE.
UNBUILT = {
    # the triangle's top band is 8..9 m: the boundary is 1.5556 m wide at the
    # bottom of it and 0 m at the apex, and `remove` is the INTERSECTION of
    # the two scanlines, so 1.6e-9 m of row survives and nothing can stand in
    # it. Correct for the mode - and it used to be SILENT, with `cell_grid`
    # reporting "2 rows x 1 faces, 0 empty" for a roof panel that had lost its
    # whole cornice band (D142).
    "FM_area_taper": 1,
}

# The 2D cases where every cell is filled by a real module, so the instancing
# floor applies exactly as it does in phase 1: a straight facade leg has
# nothing to deform.
CLEAN = ("FA_L_facade", "FC_rect", "FJ_reversed", "FK_rotated")


class Scene(R.Scene):
    """`run_scene_checks.Scene` plus the two things only a 2D build has."""

    def __init__(self, case):
        R.Scene.__init__(self, case)
        self.frame = case["report"].get("frame")


def run_case(name, case, scenes):
    try:
        scene = Scene(case)
    except Exception as exc:
        return [C.Result("scene", False, None, "%s: %s"
                         % (type(exc).__name__, str(exc)[:200]))]
    cells = CELLS.get(name)
    out = [
        # --- phase 1's own, unchanged. See the module docstring: the reuse IS
        # the assertion that no second kernel appeared.
        C.element_count(scene),
        C.unique_elem_ids(scene),
        C.output_schema(scene),
        C.section_coverage(scene),
        C.exact_fill(scene),
        C.no_gaps_or_overlaps(scene),
        C.module_fidelity(scene),
        C.rigid_never_deformed(scene),
        C.deformed_flag_matches_geometry(scene),
        C.instancing_split(scene, expect_all=False, expect_none=False),
        C.module_winding(scene),
        C.piece_extent(scene),
        C.corner_abut(scene),
        C.corner_seam(scene, expected=0.0),
        C.corner_breach(scene),
        C.warnings(scene, EXPECTED_WARNS.get(name, ())),
        C.determinism(scene, cases2d.rebuild),
        C.geometry_digest(scene),
        # --- 7's own
        # RECORDED, not asserted: the per-cell COUNT is a baseline value (a
        # count that moves is the thing worth seeing), while the cell NAMES
        # are asserted below against the figure.
        C.cell_inventory(scene),
        C.cell_modules(scene, CELL_MODULES.get(name)),
        C.cell_grid(scene, UNBUILT.get(name, 0)),
        C.row_closure(scene),
        C.row_fill_y(scene),
        C.row_scale_stays_packed(scene, BENT.get(name, 0)),
        C.role_fallbacks(scene),
        C.fallback_map(scene, FALLBACKS.get(name)),
        C.clip_inside(scene, CLIP_TOL.get(name, 1e-6)),
        C.clip_hole_elements(scene),
    ]
    if cells is not None:
        out.append(C.Result("cell_set", set(_inv(scene)) == cells,
                            sorted(_inv(scene)),
                            "" if set(_inv(scene)) == cells
                            else "expected %s" % sorted(cells)))
    if name in REAUTHORED:
        others = [(n, scenes[n]) for n in REAUTHORED[name] if n in scenes]
        out.append(C.structural_ids(scene, others))
    return out


def _inv(scene):
    inv = {}
    for r in C._cells(scene.geo):
        inv[r["pc_cell"]] = inv.get(r["pc_cell"], 0) + 1
    return inv


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
                               hou, expect_max=80000,
                               name="prims_wrappers_built_2d_rows"),
        C.points_wrappers_built(lambda: cases2d.build_many_buildings(True),
                                hou, expect_max=8,
                                name="points_wrappers_built_2d_rows"),
    ]


def main():
    update = "--update-baseline" in sys.argv
    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]

    built = cases2d.build_all()
    scenes = {}
    for name in sorted(built):
        try:
            scenes[name] = Scene(built[name])
        except Exception:
            pass
    results, failures = {}, 0
    for name in sorted(built):
        res = run_case(name, built[name], scenes)
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
    moved = []
    for case, rows in results.items():
        prev = dict((d["name"], d) for d in base.get(case, []))
        for d in rows:
            old = prev.get(d["name"])
            if old is not None and old["value"] != d["value"]:
                moved.append("%s/%s: %s -> %s"
                             % (case, d["name"], old["value"], d["value"]))
    if moved:
        print("\n--- moved since baseline (check each is an improvement) ---")
        for m in moved:
            print("  " + m)
    if update:
        with open(BASELINE, "w") as fh:
            json.dump(results, fh, indent=2, sort_keys=True)
        print("\nbaseline written: %s" % BASELINE)
    if json_out:
        with open(json_out, "w") as fh:
            json.dump(results, fh, indent=2, sort_keys=True)
    print("\n%d failing checks" % failures)
    sys.exit(1 if failures and not update else 0)


if __name__ == "__main__":
    main()
