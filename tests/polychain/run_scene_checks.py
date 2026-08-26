"""Run every polyChain geometry check in a throwaway Houdini session.

    hython tests/polychain/run_scene_checks.py
    hython tests/polychain/run_scene_checks.py --update-baseline
    hython tests/polychain/run_scene_checks.py --json results.json

Nothing is saved and no .hip exists. Every check records a value, diffed
against baseline.json; confirm each move is an improvement before
--update-baseline.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import cases                                                     # noqa: E402
import checks as C                                               # noqa: E402
import hou                                                       # noqa: E402
from polyfactory.polychain import place as P                      # noqa: E402

BASELINE = os.path.join(HERE, "baseline.json")

# What each case is ALLOWED to warn about. An empty tuple is the assertion
# "clean input raises nothing"; the two non-empty entries are the cases that
# exist to prove the detectors are not vacuous.

EXPECTED_WARNS = {
    "J_coarse_bend": ("pc_warn_bend_resolution",),
    # BQ - F3's wall bumps are finer than a 2 m panel's 0.25 m stations.
    "BQ_conform_wall_bumps": ("pc_warn_bend_resolution",),
    # DM - 13.9 N5's coverage case: 5 of 13 panels wrap a crest 0.25 m
    # stations cannot resolve (0.0153 vs 0.0100 m), so D25's warning is right.
    "DM_ripple_deformed": ("pc_warn_bend_resolution",),
    "K_broken_kit": ("pc_warn_kit_gap",),
    "O_no_kit": ("pc_warn_kit_gap",),
    # A 2 m panel resolves the crest with its own 0.25 m stations, and 4.4
    # forbids auto-subdividing it - so D25's measured warning is the right
    # answer here, not a clean build.
    "P_crest_bend": ("pc_warn_bend_resolution",),
    "Q_vertical_stepped": ("pc_warn_degenerate_frame",),
    "R_hairpin": ("pc_warn_corner_degenerate",),
    # 4.3/D36: bend welds the rectangle into one ring, so a panel wraps each
    # 90 degree vertex; D25's warning is correct (and the argument for miter).
    "B_rect_closed": ("pc_warn_bend_resolution",),
    "AB_fillet": ("pc_warn_bend_resolution",),
    # The 170 degree fallback is bend, so a panel wraps a 10 degree included
    # angle: it says BOTH that the corner degenerated and that its own 0.25 m
    # stations cannot follow what it was asked to wrap.
    "AC_degenerate_corner": ("pc_warn_bend_resolution",
                             "pc_warn_corner_degenerate"),
    # AT/AU - 13.9 N8 stage 1 (31.2); AU's hairpin says what AC does.
    "AT_ring_seam_marked": ("pc_warn_bend_resolution",),
    "AU_degenerate_bend": ("pc_warn_corner_degenerate",),
    # AV/AW - stage 2 (33.3). The warning IS what the two cases are for: AV
    # says a degenerate corner falls back to bend in MITER too, and AW says
    # the stamp folds by the curve length on a span that wraps the seam.
    # Neither may pick up a second name: a piece that WRAPS the vertex is a
    # `pc_warn_bend_resolution` case, and both of these place a panel that
    # does exactly that - so `bend_resolution`'s ABSENCE here is the panel
    # resolving its own 90 degrees, not the check looking away.
    "AV_degenerate_miter": ("pc_warn_corner_degenerate",),
    "AW_ring_section_degenerate": ("pc_warn_corner_degenerate",),
    "AD_short_legs": ("pc_warn_overflow",),
    # AS - 3v's figure: every corner is a butt joint, no piece wraps one. A
    # clean build IS the assertion; the wedge is `corner_wedge_m2`'s (D36).
    "AS_rect_bend_butt": (),
    # D58: hero geometry cannot follow a bend, and the piece this replaces is
    # the one that wraps the elbow. The warning IS the feature.
    "CD_replace_bent": ("pc_warn_bend_resolution",
                        "pc_warn_replace_deformed"),
    # 4.5's own two. BE leaves the terrain twice by construction (hole + edge,
    # D53); the two `bend_resolution` pieces straddle those boundaries, where
    # the drape steps by the full ramp height (D25 measuring the conform, D56).
    "BE_conform_holes": ("pc_warn_bend_resolution", "pc_warn_conform_miss"),
    # BH is the coarse surface: only the panel ON the crease cannot resolve it.
    "BH_conform_crease": ("pc_warn_bend_resolution",),
    # ---- cycle 5's cases. Each warning here IS the assertion the case was
    # written for; an empty tuple below is equally load-bearing.
    # D73: a rigid post cannot take a sliceable gate's tile remainder, so the
    # remainder falls back to the whole module scaled into the span (D11).
    "CH_swap_tile_slice": ("pc_warn_tile_fallback",),
    # D71: the 0.3 m bump is narrower than the panel's own 0.25 m station
    # spacing, so D25/D56 is the correct answer once the piece unpacks - and
    # the piece unpacking at all is what the case is for.
    "BL_conform_bump": ("pc_warn_bend_resolution",),
    # D71: the hole IS the case. The bend warning rides with it because the
    # drape steps by the full ramp height inside one panel, exactly as on BE.
    "BM_conform_station_hole": ("pc_warn_bend_resolution",
                                "pc_warn_conform_miss"),
    # Cycle-3 review cases - each overflows for the reason its name gives and
    # used to build silently: AH 140 deg turn vs the post's 0.2198 m miter
    # overhang (D49); AI 0.0215 m reserve vs 0.03 m panel half-thickness;
    # AP figure narrower than one corner post (D44); AQ squeezed on the short
    # side only; AR -100 % offset clamped (D49).
    "AH_sharp_turn": ("pc_warn_overflow",),
    "AI_triangle": ("pc_warn_overflow",),
    "AP_narrow_rect": ("pc_warn_overflow",),
    "AQ_asym_squeeze": ("pc_warn_overflow",),
    "AR_offset_past": ("pc_warn_overflow",),
    # ⚠️ AF/AG used to warn `pc_warn_bend_resolution` (D40's first cut
    # extended the fill span past the vertex). The boundary piece is anchored
    # now: clean build is the assertion; a returning warning = anchor lost.
}

DOUBLE_PILLAR = {
    "A_straight": 0.12,
    "DL_variant_kit": 0.12,
    "ED_rect_evenly_adjust": 0.12,
}

CORNER_MATE = {
    "AE_displace_reset": 0.03 * math.sqrt(2.0),
    # AP: D44 squeezes each 0.16 m post to (0.12 + 0.16)/(0.16 + 0.16) =
    # 0.875 -> 0.14 m, which cannot span the 2e = 0.16 m mating diagonal;
    # leftover is (L - L*f)*sqrt(2), warned `pc_warn_overflow`. A NUMBER so
    # a worse squeeze cannot pass as this one.
    "AP_narrow_rect": (cases.CORNER_POST_LENGTH
                       * (1.0 - (0.12 + 0.16) / (0.16 + 0.16))
                       * math.sqrt(2.0)),
}

_CORNER_O = 0.25 * cases.CORNER_POST_LENGTH             # 0.04 m
_CORNER_E = 0.08 * math.tan(math.pi / 4.0)              # 0.08 m at 90 degrees
_AD_RESERVE = (cases.CORNER_BLOCK_LENGTH - 0.08) + cases.CORNER_BLOCK_LENGTH
_AD_FACTOR = (1.5 + 0.08) / (_AD_RESERVE + 0.08)
CORNER_OUTSIDE = {
    "AD_short_legs": cases.CORNER_BLOCK_LENGTH * _AD_FACTOR,
    # A negative offset pushes the post PAST the plane and the miter eats the
    # overhang off its outside face: L + o, read off the built face.
    "X_corner_offset_neg": cases.CORNER_POST_LENGTH - _CORNER_O,
    # D49's clamp: -100 % stops at `e - 0.9*L`, so the outside face is
    # `L + o` - the post keeps a tenth of its length on its leg.
    "AR_offset_past": (cases.CORNER_POST_LENGTH
                       + (_CORNER_E - 0.9 * cases.CORNER_POST_LENGTH)),
}

CAMBER_DEG = {
    "BD_camber_on": 0.0,
    "BD_camber_off": math.degrees(math.atan(0.25)),
}

# BE is the only case built to miss: a hole one grid cell wide and a surface
# that stops at x = 12 of a 20 m run. Pinned exactly - a miss count that grows
# means the drape is finding less ground than it did.
CONFORM_MISSES = {"BE_conform_holes": 5,
                  # D71: the hole sits on a deform station and between the
                  # five fixed probes the old warning used - it was 0 here.
                  "BM_conform_station_hole": 1,
                  # D70: the prop IS under the run, 30 m down. This was the
                  # whole run reporting a miss because of standoff distance.
                  "BK_conform_far": 0}

BANKS = ("E_hill_adaptive", "BA_conform_adaptive")

# 4.6's instancing floor, asserted rather than recorded: a straight run of
# rigid modules has nothing to deform, so anything less than 100 % packed is a
# defect that no other check would call one.
ALL_PACKED = ("A_straight", "CE_all_packed", "CA_swap_module",
              # D69: a straight line authored at 1 m spacing is still a
              # straight line. Before the kink test this built 0 % packed.
              "CF_resampled_straight",
              # ...and the same line with a BENDABLE module - the path D69
              # actually fixed; CF's rigid beam short-circuits `_needs_deform`
              # at D27, so CF alone left the fix unguarded.
              "CG_resampled_bendable",
              # D75: THE CURVATURE BUDGET. Deviations 4.2e-05, 2.5e-04 and
              # 6.2e-03 m, all under `bend_tol`; CN_arc_tight (0.05 m, five
              # times the budget) is the control that must unpack all.
              "CK_arc_12000", "CL_arc_2000", "CM_arc_80",
              # D87's control: the same tall rail on a plan arc, where the
              # off-spine term is tiny and every piece may stay packed.
              "CQ_plan_arc_tall")

# The other side of D75: the tight arc may not keep a single piece packed.
# D87: the tall rail on the R = 55 m ELEVATION arc - spine sagitta 0.0091 m,
# inside `bend_tol`, top corner moves 0.0327 m, so none may stay packed.
NONE_PACKED = ("CN_arc_tight", "CP_elev_arc_tall")

class Scene(object):
    """One case, read once - so a check never re-derives what another already
    measured, and every check sees the same sections the builder used."""

    def __init__(self, case):
        self.case = case
        self.geo = case["out"]
        self.report = case["report"]
        self.frame = self.report.get("frame")   # 7.6's array frame, 2D only
        self.plan = self.report["plan"]
        self.params = case["style"].params
        self.by_id = dict((r["pc_elem_id"], r) for r in C.elements(self.geo))
        self.plan_by_id = dict((p.elem_id, p) for p in self.plan)
        self.warns = C.collect_warns(self.geo, self.report["warn_names"])
        self.kit, self.sources, _kw = cases.K.read(case["kit"])
        # Tracks must be read THROUGH 4.3 (bend welds sections D36, miter
        # reserves span) - the raw 4.1 list is one the builder never used.
        # The surface goes in too (4.5): omitting input 4 reads 0.800 m (the
        # ridge amplitude, the conform working) as a failure.
        self.tracks = cases.P.analyse(case["curve"], self.params,
                                      kit=cases.K.read(case["kit"])[0],
                                      style=case["style"],
                                      surface_geo=case.get("surface"))
        self.track_of = dict((str(t["curve"].curve_id), t)
                             for t in self.tracks)
        self.section_of = dict(
            ((str(t["curve"].curve_id), s.index), s)
            for t in self.tracks for s in t["sections"])

def run_case(name, case):
    """The sixteen properties the differential comparator cannot state.

    v2: was ~60 checks per case; everything comparing built geometry against
    its own plan is subsumed by `diff.compare` over generated scenes
    (`run_generated.py`). What survives says whether the answer is RIGHT.
    """
    try:
        scene = Scene(case)
    except Exception as exc:
        return [C.Result("scene", False, None, "%s: %s"
                         % (type(exc).__name__, str(exc)[:200]))]
    return [
        C.stamp_parity(scene, cases.P),
        # BA is in here deliberately: only "does an adaptive piece bank over
        # a ridge only the SURFACE knows about" can see the drape's tangent
        # (vs the spline's) inside `ConformPath.sample` at all.
        C.bank_adaptive(scene, require_bank=(name in BANKS)),
        C.conform_parity(scene),
        C.instancing_split(scene, expect_all=(name in ALL_PACKED),
                           expect_none=(name in NONE_PACKED)),
        C.warnings(scene, EXPECTED_WARNS.get(name, ())),
        # --- 4.3, on every case: no corner -> SKIP, so corner numbers ride
        # the whole suite; a surprise corner shows as a value, not silence.
        C.corner_abut(scene),
        C.corner_face_mate(scene, expected=CORNER_MATE.get(name, 0.0),
                           tol=2e-3),
        C.corner_outside_length(scene, expected=CORNER_OUTSIDE.get(name)),
        C.corner_breach(scene),
        # ...and the one that says the corner READS as one pillar.  Every
        # check above it is a CLOSURE check, and a double pillar is perfectly
        # closed - see `checks.single_pillar`.
        C.single_pillar(scene, expected=DOUBLE_PILLAR.get(name, 0.0)),
        # --- 4.5, on every case for the same reason.
        C.conform_camber(scene, expected=CAMBER_DEG.get(name)),
        C.conform_misses(scene, expected=CONFORM_MISSES.get(name)),
        # --- 4.6: the packed/deformed decision and what it costs in accuracy.
        C.curvature_budget(scene, cases.P),
        C.deform_gate(scene, cases.P),
        C.packed_true_deviation(scene, cases.P),
    ]


# 11.2's tripwires - the port plan's measurements standing as assertions,
# run once under their own pseudo-case. The expectation lives on the call
# (`scale_gate.py`'s LADDER): green on a defect-shaped expectation means
# "still the shape the audit measured"; the landing commit flips it. Flipped
# so far: P1 `stamp_calls_per_piece` 15.0 -> 1.0 (14.005 -> 0.005), P2
# `curve_sample_scaling` O(n) -> O(1) (2 339x -> ~1x).
def port_tripwires():
    return [
        C.stamp_calls_per_piece(cases.tripwire_packed_run, expect_max=1.0),
        # The DEFORMED row: a per-prim stamp there costs 14 x the PRIM COUNT
        # - the restored D102-era writer was an 8.4x regression on arc_10
        # (2.361 -> 19.854 s) with every suite green and the packed row unmoved.
        C.stamp_calls_per_piece(cases.tripwire_deformed_run, expect_max=1.0,
                                name="stamp_calls_per_piece_deformed"),
        C.station_share_hit_rate(cases.tripwire_deformed_run, cases.P,
                                 cases.CONFORM),
        # P5R's `span_ends` had no tripwire: forcing the threaded pair to
        # `None` left everything green while packed went 3.0 -> 13.0 calls.
        C.path_sample_calls_per_piece(cases.tripwire_packed_run, cases.P,
                                      expect_max=4.0),
        C.path_sample_calls_per_piece(cases.tripwire_deformed_run, cases.P,
                                      expect_max=24.0,
                                      name="path_sample_calls_per_piece_deformed"),
        C.stamp_bulk_peak_kb(cases.P),
        C.path_read_direction_m(cases.P, cases.Curve),
        C.build_out_keeps_upstream_stamps(cases.tripwire_out_build, cases.P),
        C.curve_sample_scaling(cases.Curve, expect="O(1)", cold_expect="O(n)"),
        C.conform_cache_per_element(cases.tripwire_conformed_run,
                                    cases.CONFORM, expect_max=30.0),
        # Two rows, ceilings the fixture's own: fallback keys are the gap
        # midpoints of the deforming fraction (0.69 single curve, 0.11
        # street) - the direction `fallback / batched` structurally could not
        # test. The `used` floor is 0.99 here (1.0 on streets) for one key,
        # `s = 20.001`: the forward `delta` partner of an open run's last
        # station, unread because run ends are read BACKWARD (`span_ends`).
        C.conform_prefetch_hit_rate(cases.tripwire_conformed_run,
                                    cases.CONFORM, expect_max_fallback=0.8,
                                    expect_min_used=0.99),
        # ...and the MANY-SHORT-CURVE row, because `ray`'s fixed cost is per
        # EXECUTION: batching once per curve was 0.94x - slower than not
        # batching - on 300 conformed streets and invisible on one fence.
        C.conform_prefetch_hit_rate(cases.tripwire_streets_conformed,
                                    cases.CONFORM, expect_max_fallback=0.2,
                                    name="conform_prefetch_hit_rate_streets"),
        C.conform_cache_per_element(cases.tripwire_streets_conformed,
                                    cases.CONFORM, expect_max=30.0,
                                    name="conform_cache_per_element_streets"),
        C.ray_executions_per_build(cases.tripwire_streets_conformed, hou),
        C.prims_wrappers_built(cases.tripwire_conformed_run, hou),
        # the same defect one object down: `drop_many`'s hit test used to
        # build one `hou.Point` wrapper per query - 5x the verb execution
        # it decorated, and 306 600 of them on the conformed street row.
        C.points_wrappers_built(cases.tripwire_conformed_run, hou),
        C.points_wrappers_built(cases.tripwire_streets_conformed, hou,
                                name="points_wrappers_built_streets"),
        C.prims_wrappers_built(cases.tripwire_deformed_run, hou,
                               name="prims_wrappers_built_deformed"),
        # The miter row was 11.2 P7's shape; P7 landed. `clip_plane` and
        # `dress_caps` were real per-prim loops (571 wrappers vs a 600
        # ceiling; 156 000 on a phase-2 district); both read in bulk now,
        # so the ceiling sits at the class boundary.
        C.prims_wrappers_built(cases.tripwire_mitered_run, hou,
                               expect_max=200,
                               name="prims_wrappers_built_mitered"),
        # 11.9 rule 1's counter, for reads THROUGH a wrapper - the class
        # the four counters above cannot see, and the one phase 2 grew
        # 1 676x while every committed tripwire stayed green.
        C.wrapper_reads(cases.tripwire_mitered_run, hou, expect_max=4000,
                        name="wrapper_reads_mitered"),
        C.wrapper_reads(cases.tripwire_streets_conformed, hou,
                        expect_max=2000, name="wrapper_reads_streets"),
        # `clip` and `polyfill` pinned the way `ray` is: each rebuilds its
        # own input on every execution, and nothing counted them.
        C.verb_executions_per_build(cases.tripwire_mitered_run, P,
                                    expect_max=64,
                                    name="verb_executions_per_build_mitered"),
        # ...and the verb property the bulk cap tag rests on, re-probed.
        C.polyfill_appends_its_patches(P, hou),
        C.ray_verb_semantics(cases.CONFORM, cases),
    ]


def baseline_movement(results, base):
    """Every baselined value this run did not reproduce, as text.

    D210: used to be advisory (printed, still exited 0). Pulled out of `main`
    so `exit_code` below is a testable rule.
    """
    moved = []
    for case in sorted(results):
        prev = dict((d["name"], d) for d in base.get(case, []))
        for d in results[case]:
            old = prev.get(d["name"])
            if old is not None and old["value"] != d["value"]:
                moved.append("%s/%s: %s -> %s"
                             % (case, d["name"], old["value"], d["value"]))
    return moved


def exit_code(failures, moved, update):
    """D210 - a moved baselined value fails the run like a failing check;
    `--update-baseline` is the one path that accepts movement."""
    return 1 if (failures or moved) and not update else 0


def main():
    update = "--update-baseline" in sys.argv
    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]

    built = cases.build_all()
    results, failures = {}, 0
    for name in sorted(built):
        res = run_case(name, built[name])
        results[name] = [r.as_dict() for r in res]
        print("\n=== %s ===" % name)
        for r in res:
            print("  %r" % r)
            if not r.ok and not r.skipped:
                failures += 1

    res = port_tripwires()
    results["ZZ_port_tripwires"] = [r.as_dict() for r in res]
    print("\n=== ZZ_port_tripwires ===")
    for r in res:
        print("  %r" % r)
        if not r.ok and not r.skipped:
            failures += 1

    base = {}
    if os.path.exists(BASELINE):
        with open(BASELINE) as fh:
            base = json.load(fh)

    moved = baseline_movement(results, base)
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
    sys.exit(exit_code(failures, moved, update))


if __name__ == "__main__":
    main()
