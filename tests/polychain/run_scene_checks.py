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

# How many kit validation warnings each case is allowed to persist. Pinned
# exactly, never as a range: a moved count means the validator gained or lost
# a detector, which is the thing worth seeing.
EXPECTED_KIT_WARNS = {"K_broken_kit": 9, "O_no_kit": 1}

# ...and how many warnings the 3.3 READER is allowed on the same cases. Both
# of them are "this kit has no such module", which is true - the style names
# a module the broken/absent kit cannot supply, and 3.4's stand-in box is what
# gets built. Everything else in the suite must round-trip in silence.
EXPECTED_STYLE_WARNS = {"K_broken_kit": 1, "O_no_kit": 5}

# 4.3 item C, derived from the parm and the geometry rather than read off a
# run. D39 (revised): the offset does NOT move the cut plane - it slides both
# copies along their own legs, so the two faces stay mirror images and the
# seam stays 0 AT EVERY OFFSET. That is the assertion, and it is the one the
# first version failed: +25 % parted the two planes by 2*o*cos(45) = 0.0566 m
# of open hole and -25 % crossed them over into 0.0566 m of doubly solid,
# interpenetrating geometry, both baselined as correct.
#
# What the offset DOES move is measured instead:
#   * `corner_reach_m` - how far the corner module reaches back down its leg,
#     `L - e + o` (0.12 m at +25 %, 0.04 m at -25 %);
#   * `corner_outside_m` - the outside face, which a NEGATIVE offset pushes
#     past the plane and the miter then eats: `L + min(o, 0)`.
_CORNER_O = 0.25 * cases.CORNER_POST_LENGTH             # 0.04 m
_CORNER_E = 0.08 * math.tan(math.pi / 4.0)              # 0.08 m at 90 degrees
CORNER_SEAM = {}
CORNER_REACH = {
    "U_lshape_miter": cases.CORNER_POST_LENGTH - _CORNER_E,
    "V_rect_miter": cases.CORNER_POST_LENGTH - _CORNER_E,
    "W_corner_offset_pos": cases.CORNER_POST_LENGTH - _CORNER_E + _CORNER_O,
    "X_corner_offset_neg": cases.CORNER_POST_LENGTH - _CORNER_E - _CORNER_O,
    # 4.3 item D as a distance. D40's boundary piece is one whole default
    # module anchored on the leg, so `extend` reaches `L - e` back down it and
    # `symmetric` reaches exactly `L/2` - which IS the centring the first
    # implementation only approximated (12.07 m of a 12.00 m leg) and which
    # `tile` broke outright by tiling into the extension.
    "AF_displace_extend": 2.0 - 0.03,
    "AG_displace_symmetric": 1.0,
    "AN_tile_symmetric": cases.GATE_LENGTH * 0.5,
    # ...and the offset the no-corner-module path used to ignore completely:
    # -10 % of the 2 m panel, so `L - e + o`.
    "AO_displace_offset": 2.0 - 0.03 - 0.2,
}

# 4.3 item B, the odd/even compose rule as a distance. An ODD count reaches
# equally down both legs; an EVEN count carries one extra module on the
# outgoing leg, so the difference is exactly that module's length.
# 4.3 item D, the one number that separates the three policies. `reset`
# leaves each piece where the fit put it and slices it at the vertex, so the
# two cut faces are mirror images and the corner keeps a notch of
# e*sqrt(2) = h*tan(45)*sqrt(2) on the outside - 0.03*1.41421 for the starter
# panel. `extend` and `symmetric` both push the run to (or through) the plane,
# so their faces mate exactly and their expected mismatch is 0.
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

# D44's squeeze, derived from the input rather than from the run: three 1.20 m
# corner blocks reserve (1.20 - e) + 1.20 = 2.32 m of a 1.50 m leg, so every
# corner module on that side is scaled by 1.50/2.32 and the outside face that
# should have measured 1.20 m measures 0.7759 m - and says pc_warn_overflow.
# D44, CORRECTED: the squeeze is about the CUT PLANE, so the fixed point is
# the 0.08 m the straddler reaches PAST the vertex and only the rest scales -
# the factor is (L_leg + e)/(reserve + e), not L_leg/reserve, and the squeezed
# module still reaches the plane instead of leaving an e*(1-f) notch.
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

CORNER_SYMMETRY = {
    "U_lshape_miter": 0.0,
    "V_rect_miter": 0.0,
    "AA_reflex_miter": 0.0,
    "Y_compose_odd": 0.0,
    "Z_compose_even": cases.CORNER_BLOCK_LENGTH,
}


# 4.5 / D55, derived from the surface and not from a run: `camber_z` falls
# 25 % ACROSS the run, so a piece that takes the camber ends up with its own
# up ON the surface normal (0 degrees) and one that refuses it keeps world up,
# which is atan(0.25) = 14.0362 degrees away from that normal. The pair is the
# assertion; one of them alone would pass with the parm wired to nothing.
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

# D94: the conditional keyed on the SPLINE'S OWN prim attribute. Two
# curves, one rule, two answers - the assertion is the pair, because
# "a gate exists" would also pass on a rule that ignores the attribute.
MODULES_BY_CURVE = {"CR_attr_conditional": {"CRa": ["gate"],
                                            "CRb": ["panel"]}}

# [swapped, replaced, ids that moved] per override case, derived from the
# override stream and not from a run: CA re-points all ten panels, CC and CD
# replace exactly one element each, and NOTHING may move an id.
OVERRIDES = {
    "CA_swap_module": [10, 0, 0],
    "CC_replace_hero": [0, 1, 0],
    "CD_replace_bent": [0, 1, 0],
}


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
    try:
        scene = Scene(case)
    except Exception as exc:
        return [C.Result("scene", False, None, "%s: %s"
                         % (type(exc).__name__, str(exc)[:200]))]
    out = [
        C.element_count(scene),
        C.unique_elem_ids(scene),
        C.element_resolution(scene),
        C.stamp_provenance(scene),
        C.output_schema(scene),
        C.sampler_matches_kernel(scene),
        C.section_coverage(scene),
        C.exact_fill(scene),
        C.no_gaps_or_overlaps(scene),
        C.stepped_riser(scene),
        C.stepped_float(scene),
        C.band_hybrid(scene),
        C.band_datum(scene),
        C.stamp_parity(scene, cases.P),
        C.plumb_vertical(scene),
        C.flat_stepped(scene),
        # ⚠️ BA IS IN HERE FOR THE SAME REASON E IS, and it was added because a
        # mutation survived without it: taking the SPLINE's tangent instead of
        # the drape's inside `ConformPath.sample` moved not one number in the
        # whole suite. The conformed run is dead flat as a spline, so nothing
        # but "does an adaptive piece bank over a ridge that only the SURFACE
        # knows about" can see that tangent at all.
        C.bank_adaptive(scene, require_bank=(name in BANKS)),
        C.conform_parity(scene),
        C.slice_caps_closed(scene),
        C.axis_follows_curve(scene),
        C.cross_section_width(scene),
        C.module_fidelity(scene),
        C.rigid_never_deformed(scene),
        C.deformed_flag_matches_geometry(scene),
        C.instancing_split(scene, expect_all=(name in ALL_PACKED),
                           expect_none=(name in NONE_PACKED)),
        C.horizontal_spacing(scene),
        C.module_winding(scene),
        C.frame_continuity(scene),
        C.station_spacing(scene),
        C.piece_extent(scene),
        C.plan_geometry(scene, cases.P),
        C.plan_point_provenance(scene, cases.P),
        C.bend_deviation(scene),
        C.warnings(scene, EXPECTED_WARNS.get(name, ())),
        C.determinism(scene, cases.rebuild),
        C.geometry_digest(scene),
        # --- 4.3, on every case: a corner check that finds no corner reports
        # SKIP, so the corner numbers ride the whole suite rather than only the
        # cases that were written for them. A corner appearing where none was
        # expected therefore shows up as a value, not as silence.
        C.corner_abut(scene),
        C.corner_turns(scene),
        C.corner_welds(scene),
        C.corner_plane_dev(scene),
        C.corner_face_mate(scene, expected=CORNER_MATE.get(name, 0.0),
                           tol=2e-3),
        # ...and the half `corner_face_mate_m` structurally cannot see,
        # because its `stepped` escape drops it to a plan-only metric (D72).
        C.corner_mate_axis(scene),
        C.corner_symmetry(scene, expected=CORNER_SYMMETRY.get(name)),
        C.corner_outside_length(scene,
                                expected=CORNER_OUTSIDE.get(name)),
        C.corner_reach(scene, expected=CORNER_REACH.get(name)),
        C.corner_breach(scene),
        C.corner_wedge(scene),
        # --- 4.5, on every case: no surface reports SKIP, so a conform that
        # appears where none was wired shows up as a value rather than as
        # silence - the same rule the corner checks ride on.
        C.conform_contact(scene),
        C.conform_drape(scene),
        C.conform_camber(scene, expected=CAMBER_DEG.get(name)),
        C.conform_misses(scene, expected=CONFORM_MISSES.get(name)),
        # --- 4.6, on every case for the same reason: an override or a
        # replaced element appearing where none was wired is a value, not
        # silence, and `over_unpacked` is only meaningful across the whole
        # suite (it is the check that a build cannot pass by unpacking
        # everything).
        C.over_unpacked(scene),
        C.curvature_budget(scene, cases.P),
        C.deform_gate(scene, cases.P),
        C.packed_true_deviation(scene, cases.P),
    ]
    if name in MODULES_BY_CURVE:
        out.append(C.modules_by_curve(scene, MODULES_BY_CURVE[name]))
    out += [
        # 3.3 / PC-G4, on EVERY case: the same style, expressed as a payload
        # and read back through input 3, must build the same geometry.
        C.style_round_trip(scene, cases.via_payload,
                           EXPECTED_STYLE_WARNS.get(name, 0)),
        C.override_round_trip(scene, cases.rebuild_plain,
                              expected=OVERRIDES.get(name)),
        C.elem_ids_survive_upstream(scene, cases.with_extra_curve),
        C.cap_dressing(scene),
        C.warning_summary(scene),
    ]
    out.append(C.corner_seam(scene, expected=CORNER_SEAM.get(name, 0.0)))
    if name in ("C_tile_slice", "H_tile_slope_free", "I_tile_slope_fixed"):
        out.append(C.cap_tagged(scene, expect=1))
    if name == "DJ_flatten_hero":
        # the hero is the post's own 0.12 m footprint at 1.5 m instead of
        # 1.20 m, so its bbox is the proof the replacement actually happened
        # and `stepped_float_m` is the proof it was planted (D98 on the D58
        # path). Recorded rather than asserted: the fit scales x.
        out.append(C.replaced_geometry(scene, expected=None))
    if name in ("CC_replace_hero", "CD_replace_bent"):
        # the hero is a 2.0 x 2.0 x 0.4 m slab and no kit module is anything
        # like it, so its own world bbox is the proof it arrived. CD's piece
        # spans a 90 degree elbow, so its bbox is the slab's diagonal there
        # and is recorded rather than asserted.
        out.append(C.replaced_geometry(
            scene, expected=(2.0, 2.0, 0.4)
            if name == "CC_replace_hero" else None))
    if name == "A_straight":
        # 3.3's warn-and-degrade contract, cooked by the check: the payload is
        # the thing under test, so it is wired to exactly one case.
        out.append(C.style_payload_degrades(scene, cases.malformed_payload,
                                            cases.build_with_payload))
        # D74's control build, cooked by the check because colliding ids are
        # the condition under test and every id-keyed check above would read
        # a merged scene and report nonsense on it. It does not depend on the
        # case it is wired to, so it is wired to exactly one.
        out.append(C.duplicate_curve_id_warns(scene, cases.duplicate_curve_ids))
    if name == "BN_conform_overhead":
        # D70's NEAREST test, which nothing else in the suite exercises: the
        # deck is 0.4 m up and the ground 3.0 m down, so the middle of the run
        # is on the deck and its edge is a 3.4 m riser.
        out.append(C.stepped_riser_is(scene, 3.4))
    if name == "CI_swap_zmode":
        # D73: the post's own manifest default, not the panel's `vertical`.
        out.append(C.zmode_stamp(scene, "stepped"))
    if name == "D_marker_gate":
        out.append(C.marker_offset(scene, 7, (10.0, 0.0, 0.0)))
    # D26's two halves, derived from the grade rather than copied off a run:
    # slope fixing ON keeps the gate's own 1.60 m when measured horizontally,
    # OFF measures that width along the path's angle instead.
    if name == "I_tile_slope_fixed":
        out.append(C.horizontal_span_is(scene, cases.GATE_LENGTH))
    if name == "H_tile_slope_free":
        out.append(C.horizontal_span_is(
            scene, cases.GATE_LENGTH / math.hypot(1.0, cases.HILL_GRADE)))
    if name == "N_marker_mixed":
        # The whole point of the case: marker 7 is authored in metres and
        # marker 8 in u, in ONE cloud, and both must land where they say.
        out.append(C.marker_offset(scene, 7, (5.0, 0.0, 0.0)))
        out.append(C.marker_offset(scene, 8, (15.0, 0.0, 0.0)))
    if name == "AB_fillet":
        # 4.3 item E: a 1.5 m fillet on a 90 degree corner holds the path
        # 1.5*(1/cos45 - 1) = 0.6213 m off the original sharp vertex, and the
        # pieces are on the path.
        out.append(C.corner_clearance(
            scene, (12.0, 0.0, 0.0),
            1.5 * (1.0 / math.cos(math.pi / 4.0) - 1.0)))
    n = EXPECTED_KIT_WARNS.get(name, 0)
    out.append(C.kit_validation(scene, n, n))
    return out


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
