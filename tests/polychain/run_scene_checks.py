"""Run every polyChain geometry check in a throwaway Houdini session.

    hython tests/polychain/run_scene_checks.py
    hython tests/polychain/run_scene_checks.py --update-baseline
    hython tests/polychain/run_scene_checks.py --json results.json

Nothing is saved and no .hip exists. Numbers first, renders second: every
check records a value, and the runner diffs every value against baseline.json
and prints movement even where a check still passes. Read that list and
confirm each move is an improvement before running --update-baseline.
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
    # DM is 13.9 N5's own coverage case (a smooth 24 m ripple with no corner,
    # which is what `place_deformed_covers_the_reference` compares a real
    # element set on).  Five of its thirteen panels wrap a crest their own
    # 0.25 m stations cannot resolve inside `bend_tol` - 0.0153 m against
    # 0.0100 - so D25's warning is the RIGHT answer here for exactly the
    # reason `P_crest_bend`'s is, and a clean build would mean the fixture
    # had stopped bending anything.
    "DM_ripple_deformed": ("pc_warn_bend_resolution",),
    "K_broken_kit": ("pc_warn_kit_gap",),
    "O_no_kit": ("pc_warn_kit_gap",),
    # A 2 m panel resolves the crest with its own 0.25 m stations, and 4.4
    # forbids auto-subdividing it - so D25's measured warning is the right
    # answer here, not a clean build.
    "P_crest_bend": ("pc_warn_bend_resolution",),
    "Q_vertical_stepped": ("pc_warn_degenerate_frame",),
    "R_hairpin": ("pc_warn_corner_degenerate",),
    # 4.3/D36: bend welds the four sections of the rectangle into one ring, so
    # a 2 m panel now WRAPS each 90 degree vertex - and its own 0.25 m stations
    # cannot resolve a right angle inside `bend_tol`. D25's warning is the
    # correct answer, and it is also the argument for reaching for miter.
    "B_rect_closed": ("pc_warn_bend_resolution",),
    "AB_fillet": ("pc_warn_bend_resolution",),
    # The 170 degree fallback is bend, so a panel wraps a 10 degree included
    # angle: it says BOTH that the corner degenerated and that its own 0.25 m
    # stations cannot follow what it was asked to wrap.
    "AC_degenerate_corner": ("pc_warn_bend_resolution",
                             "pc_warn_corner_degenerate"),
    "AD_short_legs": ("pc_warn_overflow",),
    # AS is 3v's own figure: twenty 2 m panels fit the 40 m ring exactly, so
    # every corner is a BUTT JOINT and no piece is asked to wrap one. A clean
    # build is the assertion - the wedge those joints leave is measured by
    # `corner_wedge_m2`, not warned about (D36: it is inherent, miter is the
    # fix).
    "AS_rect_bend_butt": (),
    # D58: hero geometry cannot follow a bend, and the piece this replaces is
    # the one that wraps the elbow. The warning IS the feature.
    "CD_replace_bent": ("pc_warn_bend_resolution",
                        "pc_warn_replace_deformed"),
    # 4.5's own two. BE leaves the terrain twice by construction (a hole and
    # an edge), which is D53's warning and nothing else; the two
    # `bend_resolution` pieces are the ones STRADDLING those boundaries, where
    # the drape steps by the full ramp height inside one panel and 0.25 m
    # stations cannot follow a cliff - D25 measuring the conform, exactly as
    # D56 says it should.
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
    # The cycle-3 review cases. Every one of these overflows for a REASON the
    # case name gives, and every one of them used to build silently:
    # AH  a 140 degree turn is sharper than the 0.16 m post's own 0.2198 m
    #     miter overhang, so D49 pulls the post back onto the vertex;
    # AI  a 1.5 m triangle leaves 0.0215 m of reserve against a 0.03 m panel
    #     half-thickness, so the run itself has to be cut on the plane;
    # AP  a 12 x 0.12 m figure is narrower than one corner post (D44);
    # AQ  a 1.5 m leg against a 12 m one, squeezed on the short side only;
    # AR  a -100 % offset would push the post clean past the vertex (D49).
    "AH_sharp_turn": ("pc_warn_overflow",),
    "AI_triangle": ("pc_warn_overflow",),
    "AP_narrow_rect": ("pc_warn_overflow",),
    "AQ_asym_squeeze": ("pc_warn_overflow",),
    "AR_offset_past": ("pc_warn_overflow",),
    # ⚠️ AF/AG USED TO WARN `pc_warn_bend_resolution` HERE and no longer do.
    # That was D40's first implementation extending the FILL SPAN past the
    # vertex, so the straddling panel rode the welded kink and could not
    # resolve a right angle with its own 0.25 m stations. The boundary piece
    # is now ANCHORED on the straight leg like every other 4.3 piece, so
    # there is no bend left to fail to resolve - a clean build is the
    # assertion, and a returning warning means the anchor was lost.
}

DOUBLE_PILLAR = {
    "A_straight": 0.12,
    "DL_variant_kit": 0.12,
    "ED_rect_evenly_adjust": 0.12,
}

CORNER_MATE = {
    "AE_displace_reset": 0.03 * math.sqrt(2.0),
    # A figure NARROWER THAN ITS OWN FENCE. Each 0.12 m side must host two
    # corner posts of 0.16 m, so D44 squeezes them to L*(0.12+2e)/(2L-... )
    # - concretely (0.12 + 0.16)/(0.16 + 0.16) = 0.875 of 0.16 m = 0.14 m -
    # and a 0.14 m module cannot span the 2e = 0.16 m mating diagonal. What is
    # left over is exactly the shortfall, on the diagonal: (L - L*f)*sqrt(2).
    # It is a squeeze artefact and it says `pc_warn_overflow`; it is here as a
    # NUMBER so that a squeeze that gets worse cannot pass as this one.
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
    # D49's clamp, as a distance: -100 % is out of range, so the offset stops
    # at `e - 0.9*L` and the outside face is `L + o` = 0.9*L - e + L... i.e.
    # the post keeps a tenth of its length on its leg and the miter has eaten
    # the rest of the overhang.
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
              # ...and the same line with a BENDABLE module, which is the
              # path D69 actually fixed - CF's rigid beam short-circuits
              # `_needs_deform` at D27 before the vertex test is reached, so
              # CF alone left the fix unguarded (a mutation survived it).
              "CG_resampled_bendable",
              # D75: THE CURVATURE BUDGET. A resampled arc has a real interior
              # vertex in every span, so the binary vertex test unpacked all
              # three of these; the deviation they would actually suffer is
              # 4.2e-05 m, 2.5e-04 m and 6.2e-03 m, every one of them under
              # `bend_tol`. CN_arc_tight is the control that keeps this from
              # being vacuous - 0.05 m, five times the budget, and it must
              # unpack all of them.
              "CK_arc_12000", "CL_arc_2000", "CM_arc_80",
              # D87's own control: the SAME 1.2 m tall rail on a plan arc,
              # where `across` barely turns and `up` is world up - so the
              # off-spine term is real but tiny and every piece may stay
              # packed. Without it the D87 fix could simply unpack everything
              # and pass CP.
              "CQ_plan_arc_tall")

# ...and the other side of D75: the tight arc may not keep a single piece
# packed. Without this the budget could be widened until nothing ever bends.
# D87: a 1.2 m tall bendable rail on an R = 55 m ELEVATION arc. The spine
# sagitta is 0.0091 m, inside `bend_tol` - and the piece's top corner
# really moves 0.0327 m, so not one of them may stay packed.
NONE_PACKED = ("CN_arc_tight", "CP_elev_arc_tall")

class Scene(object):
    """One case, read once - so a check never re-derives what another already
    measured, and every check sees the same sections the builder used."""

    def __init__(self, case):
        self.case = case
        self.geo = case["out"]
        self.report = case["report"]
        self.plan = self.report["plan"]
        self.params = case["style"].params
        self.by_id = dict((r["pc_elem_id"], r) for r in C.elements(self.geo))
        self.plan_by_id = dict((p.elem_id, p) for p in self.plan)
        self.warns = C.collect_warns(self.geo, self.report["warn_names"])
        self.kit, self.sources, _kw = cases.K.read(case["kit"])
        # 4.3 lives between decompose and plan, so the tracks must be read
        # THROUGH it: in bend mode it welds sections (D36) and in miter mode
        # it reserves span for the corner assembly. Re-deriving the raw 4.1
        # list here would measure the builder against a section list the
        # builder never used.
        # ⚠️ THE SURFACE GOES IN HERE TOO (4.5). `analyse` wraps the Path in
        # the conform, so a check that omits input 4 measures the built
        # geometry against the UNDRAPED spline: `axis_on_curve_m` and
        # `plan_points` both read 0.800 m on the ridge cases - which is the
        # ridge amplitude, i.e. the conform working, reported as a failure.
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
    """The sixteen properties of a built fence that the differential
    comparator structurally cannot state.

    ⚠️ v2: this used to call ~60 checks per case.  Every one that compared
    the built geometry against the plan that built it - element counts, ids,
    fill spans, frames, digests, round-trips - is subsumed by `diff.compare`
    over generated scenes (`run_generated.py`), which compares EVERY
    attribute of both paths by construction rather than the subset somebody
    remembered to list.  What survives is the checks that say whether the
    answer is RIGHT: the corner assembly, the conform, the deform gate, and
    the warnings a case is allowed to raise.
    """
    try:
        scene = Scene(case)
    except Exception as exc:
        return [C.Result("scene", False, None, "%s: %s"
                         % (type(exc).__name__, str(exc)[:200]))]
    return [
        C.stamp_parity(scene, cases.P),
        # ⚠️ BA IS IN HERE DELIBERATELY: taking the SPLINE's tangent instead
        # of the drape's inside `ConformPath.sample` moved not one number in
        # the whole suite without it.  The conformed run is dead flat as a
        # spline, so only "does an adaptive piece bank over a ridge that only
        # the SURFACE knows about" can see that tangent at all.
        C.bank_adaptive(scene, require_bank=(name in BANKS)),
        C.conform_parity(scene),
        C.instancing_split(scene, expect_all=(name in ALL_PACKED),
                           expect_none=(name in NONE_PACKED)),
        C.warnings(scene, EXPECTED_WARNS.get(name, ())),
        # --- 4.3, on every case: a corner check that finds no corner reports
        # SKIP, so the corner numbers ride the whole suite rather than only
        # the cases written for them.  A corner appearing where none was
        # expected shows up as a value, not as silence.
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


# 11.2's tripwires - the port plan's own measurements, standing up as
# assertions (tests/README.md's compounding rule). They belong to no scene
# case, so they run once under their own pseudo-case and land in the baseline
# beside everything else.
#
# ⚠️ THE EXPECTATION LIVES ON THE CALL, `scale_gate.py`'s LADDER device: when
# an expectation still describes a DEFECT, green here means "still the shape
# the audit measured", and the commit that lands the port flips it - the flip
# IS the proof. Two have flipped so far: P1 took `stamp_calls_per_piece`'s
# ceiling from 15.0 to 1.0 (14.005 -> 0.005) and P2 took
# `curve_sample_scaling` from `O(n)` to `O(1)` (2 339x -> ~1x). Restoring
# either implementation turns its own row red.
def port_tripwires():
    return [
        C.stamp_calls_per_piece(cases.tripwire_packed_run, expect_max=1.0),
        # ⚠️ AND THE DEFORMED ROW. The packed fixture reports `deformed == 0`,
        # so the one branch where a per-prim stamp costs 14 x the piece's PRIM
        # COUNT was the branch the tripwire could not reach: the D102-era
        # writer restored there is an 8.4x regression on `scale_gate` arc_10
        # (2.361 -> 19.854 s) with every suite green and this row unmoved.
        C.stamp_calls_per_piece(cases.tripwire_deformed_run, expect_max=1.0,
                                name="stamp_calls_per_piece_deformed"),
        C.station_share_hit_rate(cases.tripwire_deformed_run, cases.P,
                                 cases.CONFORM),
        # P5R's `span_ends` had no tripwire at all: forcing the threaded pair
        # to `None` left all three suites AND the baseline green while the
        # packed fixture went 3.0 -> 13.0 calls per piece. Both branches, the
        # way `stamp_calls_per_piece` learned to run on both.
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
        # ⚠️ TWO ROWS, AND THE CEILING IS THE FIXTURE'S OWN. The fallback
        # keys are the gap midpoints of whatever fraction of the run
        # DEFORMS, so the 100 %-deformed single curve reads 0.69 and the
        # 87 %-packed street row reads 0.11 - and the `used` floor is 1.0
        # on both, which is the direction the first version of this check
        # structurally could not test (it read `fallback / batched`, which
        # is 0.0 by construction when the batch over-fetches).
        # ⚠️ AND THE `used` FLOOR IS 0.99 ON THIS ROW AND 1.0 ON THE OTHER,
        # for ONE named key: `s = 20.001`, the forward `delta` partner of the
        # last station of the last piece of an OPEN run. Nothing reads it,
        # because the end of a run is read BACKWARD (`span_ends`). It is one
        # key per open curve at worst; the street row reads exactly 1.0.
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
        # ⚠️ THE MITER ROW WAS 11.2 P7's SHAPE, AND P7 HAS NOW LANDED.
        # `clip_plane`'s cap tagging and `dress_caps`' cap search were
        # REAL per-prim loops - 280 wrappers each on this fixture, 571
        # in total against a 600 ceiling, and 156 000 on a phase-2
        # district. Both read in bulk now (`polyfill` appends its
        # patches at the tail, and `pc_cap` is an int column), so the
        # row is at the class boundary a genuine regression would have
        # to cross rather than 5 % above the value.
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

    D210 - THIS USED TO BE ADVISORY.  The block printed and the run still
    exited 0, so every "no baselined value moved" claim in the build log was
    resting on an exit code that structurally could not carry it.  Pulled out
    of `main` so `exit_code` below is a testable rule and not a line nobody
    can reach without a Houdini session.
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
    """D210 - a MOVED baselined value fails the run exactly like a failing
    check does.  `--update-baseline` is the one path that accepts movement,
    because that is a human saying "I read it and it is an improvement".
    """
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
