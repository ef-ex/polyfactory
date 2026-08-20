"""CityGen S5 PLANNER — decide on the abstract graph, before geometry exists.

`hou`-free by design, and that is the whole point of the module (§11.2). Every
mechanism in the repair loop used to decide locally and discover next pass what
the others did: three guard variants each measured zero violations at their own
stage while `graph_min_angle` still deleted a street a pass later, because
`graph_resample -> graph_stitch -> graph_fuse -> graph_polypath` reshape the
graph between a decision and its consequence (§11.0). So the footprint of a
junction is computed as a FUNCTION of arms, widths, classes and angles — never
as a measurement of built plates.

⚠️ **THIS IS NOT A RESURRECTION OF THE DELETED `citygen/graph.py`** — that module
solved weld/prune, which the segmenter now owns in VEX, and it died with a green
test suite because nothing consumed it. What is different here is that every
number is calibrated against measured builder output
(`tests/citygen/dump_trims.py` -> `tests/unit/trim_calibration.json`, asserted by
`tests/unit/test_plan.py`).

✅ **AND M3 PAID §11.2's DEBT: it now has a consumer.** `graph_plan`, a thin
Python SOP sitting after `repair_scratch` in `pf_citygen_segmenter`, is the
adapter the architecture calls for — geometry to plain data, plan.py, attributes
written back on `is_node` points. M1 built this module deliberately ahead of
that rule so the K verdict could be measured before any HDA was touched; for two
milestones it was the exact thing the paragraph above warns about.

`crossing_trims` is a transcription of `s5j_solve`'s corner construction into
closed form, in the NODE frame. The one thing it does not model — and cannot,
before geometry exists — is recorded under the constants below and measured by
the calibration test.
"""

import math

# --- the builder's own constants, mirrored ---------------------------------
# `pfsj_corner_radius`, pf_streetjunction.vfl. Turning radius from street class
# via design speed — a default the artist overrides, never a constant.
CORNER_RADIUS = {"highway": 25.0, "arterial": 9.0, "collector": 6.0,
                 "alley": 2.0, "local": 4.0}
DEFAULT_CORNER_RADIUS = 4.0                 # `local`, and anything unclassified

# |sin(angle)| below this and the miter is undefined — pfsj_corner_lines' own
# threshold, ~1.1 degrees. Kept identical so the planner and the builder agree
# about which corners have no finite solution.
COLLINEAR_SIN = 0.02
EPS = 1e-6

# §11.3's schema, named once. The adapter writes these and `checks.py` polices
# them; before these constants existed the set was spelled out in three places
# and a fourth attribute could have been added in one and policed in none.
#
# ⚠️ Two constants because the schema lives in two CLASSES since the artist's
# 2026-08-16 ruling: `junction_type` is a POINT attribute on the node, and the
# principal is a pair of PER-EDGE booleans — `principal_start` / `principal_end`
# on the prim, CityEngine's own shape (`principleStreetStart` / `...End`). The
# node-string form (`principal_edges`) is RETIRED: three audit rounds found four
# defects that were properties of the shape itself — a stranger edge, the same
# edge twice, one edge, and an int-typed value that crashed the gate — and none
# of them is expressible as a boolean an edge carries about itself.
NODE_SCHEMA_ATTRS = ("junction_type",)
EDGE_SCHEMA_ATTRS = ("principal_start", "principal_end")

# ...and the VOCABULARY gets the same single owner. The M4 audit found it
# spelled out in `checks.py` with the reserved subset repeated independently in
# `node_trims` - consistent that day, and a two-file drift hazard the moment M5
# moves `merge` from reserved to built. One definition; `checks.py` reads it
# through the same lazy-import-with-reported-fallback the attribute names use.
JUNCTION_TYPE_VOCAB = ("", "crossing", "junction", "merge", "roundabout")
RESERVED_JUNCTION_TYPES = ("merge", "roundabout")   # in vocab, no builder yet

# ⚠️ THE ONE THING THIS MODEL DOES NOT PREDICT, measured rather than assumed.
#
# `s5j_solve` re-reads each arm's frame at the current cut and re-solves the
# corner THERE, eight times. On a straight arm that is a fixed point and the
# closed form below is exact — measured to 3.4e-5 m on the NINE straight cases
# (E_short_t, F_bend, G_tongue, J_five_star, K_stub_triangle, and M2's
# M_shallow_y_24, N_shallow_y_32, O_shallow_y_host_dies, P_stub_chain). On a
# curved arm the tangent at the cut is not the tangent at the node, and the
# corner moves.
#
# ⚠️ **AND IT IS TWO-SIGNED. The builder does not always cut more.** The VEX
# latches monotone only from its third pass — `dist[i] = (iter < 3) ? dd :
# max(dist[i], dd)` — so passes 1 and 2 are free to RETREAT below the node-frame
# value, and the fixed point lands on either side of it. Measured, predicted
# minus measured, over all 545 arms:
#
#   A_drawn / D_offset / H_offset_strict   -0.347 .. +2.024
#   B_grid                                 -3.995 .. +2.404
#   C_radial / I_offset_radial             -3.581 .. +4.575
#
# It is not modelled here and it must not be: predicting a tangent 17 m along an
# arm needs the arm's SHAPE, which is the geometry §11.1 rule 6 forbids a
# decision from depending on.
#
# WHAT A CONSUMER NEEDS is neither of those numbers. `crossing_trims` exists to
# feed `standing`, where the two ends compound, and only ONE direction is
# dangerous: the planner reporting more standing street than the builder will
# leave. That bound is below, and the calibration test pins it against the
# fixture so it cannot rot the way its first value did.
#
# ⚠️ Both are bounds on the RESIDUAL, not on the verdict. Measured over all 322
# edges of the suite, the planner's `standing > 0` answer never disagrees with
# the builder's — 0 false-OK, 0 false-BAD — and THAT is the property downstream
# milestones actually rely on. `test_plan.py` asserts it directly; do not
# substitute the metres below for it.
STANDING_OPTIMISM_M = 5.88          # measured 5.8763, C_radial / I_offset_radial
CURVED_ARM_RESIDUAL_M = 4.58        # measured 4.5750, worst per-arm either way


class Params(object):
    """The `s5j_params` values the corner solve reads. Defaults are the HDA's.

    `resample_step` is `s5_resample`'s Max Segment Length inside
    `pf_citygen_junction` (4 m), not the segmenter's — the corner solve runs on
    the junction HDA's own resampled copy.
    """

    def __init__(self, miter_limit=4.0, corner_radius_scale=1.0,
                 max_fillet_fraction=0.4, min_end_segment=1.0,
                 resample_step=4.0):
        self.miter_limit = miter_limit
        self.corner_radius_scale = corner_radius_scale
        self.max_fillet_fraction = max_fillet_fraction
        self.min_end_segment = min_end_segment
        self.resample_step = resample_step


DEFAULTS = Params()


class Arm(object):
    """One street as seen FROM a node: which end of it this is, and where it goes.

    `direction` is the unit XZ vector from the node toward the polyline's next
    vertex — the same `dirs[]` s5j_solve sorts and solves in. It is graph data,
    not a geometry measurement: it changes only when a node moves, which is
    itself a planner decision.
    """

    def __init__(self, edge_id, direction, width, street_class, length,
                 at_start=True, principal=False):
        self.edge_id = edge_id
        self.direction = (float(direction[0]), float(direction[1]))
        self.width = float(width)
        self.street_class = street_class
        self.length = float(length)
        self.at_start = bool(at_start)
        # `principal_start` / `principal_end` read at THIS end of the edge: does
        # this street claim to be the principal at this node? Authored or
        # planner-computed on the prim; a boolean an edge carries about itself,
        # so the stranger/duplicate/split-crash class cannot be expressed.
        self.principal = bool(principal)

    @property
    def bearing(self):
        return math.atan2(self.direction[1], self.direction[0])

    @property
    def half_width(self):
        return self.width * 0.5


class Node(object):
    def __init__(self, node_id, pos, arms, junction_type=""):
        self.node_id = node_id
        self.pos = (float(pos[0]), float(pos[1]))
        self.arms = list(arms)
        self.junction_type = junction_type


def corner_radius(street_class):
    return CORNER_RADIUS.get(street_class, DEFAULT_CORNER_RADIUS)


def _corner(a, b, params):
    """The kerb-line corner between two CCW-adjacent arms, in the node frame.

    Returns (reach_a, reach_b): how far along each arm the cut must go to clear
    this corner, tangent run included. This is `pfsj_corner_lines` + the miter
    clamp + `pfsj_fillet` solved once instead of intersected numerically.

    With arm A on the x axis, A's kerb line is offset +hA across it and B's is
    offset -hB across B, so their intersection K sits at (u, hA) with

        u = (hB + hA cos phi) / sin phi

    where `phi` is the SIGNED CCW angle from A to B — the actual gap, which for
    three arms in one half-plane exceeds 180 degrees and makes sin negative.
    That sign is load-bearing: the builder takes the dot product of a real
    intersection point, so a gap of 200 degrees must not be folded to 160.
    """
    dax, daz = a.direction
    dbx, dbz = b.direction
    sin_phi = dax * dbz - daz * dbx           # dA x dB, the builder's `den`
    cos_phi = dax * dbx + daz * dbz
    ha, hb = a.half_width, b.half_width

    if abs(sin_phi) < COLLINEAR_SIN:
        # Parallel kerbs, and the two cases are opposites: angle ~ pi is a street
        # running straight through (nothing to trim), angle ~ 0 is two edges
        # overlapping (push clear of both). s5j_solve's own fallback.
        push = 0.0 if cos_phi < 0 else max(a.width, b.width)
        return push, push

    raw_a = (hb + ha * cos_phi) / sin_phi
    raw_b = (hb * cos_phi + ha) / sin_phi

    # The miter spike is measured from where the two street AXES cross, which in
    # the node frame IS the node. Above the limit the corner is clamped along its
    # own direction rather than collapsed onto the node — using the bevel points
    # there made the trim ~0 and drove a kerb wall across the carriageway.
    max_half = max(a.width, b.width) * 0.5
    k_len = math.hypot(raw_a, ha)
    if max_half < EPS:
        ratio = 1e9
    else:
        ratio = k_len / max_half
    if ratio > params.miter_limit and k_len > EPS:
        scale = (params.miter_limit * max_half) / k_len
        raw_a *= scale
        raw_b *= scale

    ka = max(raw_a, 0.0)
    kb = max(raw_b, 0.0)

    # --- the fillet. `theta` is UNSIGNED here, because pfsj_fillet takes
    # acos(dot) — a 200 degree gap fillets as its 160 degree explement.
    theta = math.acos(max(-1.0, min(1.0, cos_phi)))
    half = theta * 0.5
    if math.sin(half) < COLLINEAR_SIN or math.tan(half) < EPS:
        return ka, kb                         # no arc exists; the cut is the corner

    r = min(corner_radius(a.street_class),
            corner_radius(b.street_class)) * params.corner_radius_scale
    run = r / math.tan(half)
    max_run = params.max_fillet_fraction * min(a.length, b.length)
    if max_run > 0.0 and run > max_run:
        run = max_run
    return max(raw_a + run, ka), max(raw_b + run, kb)


def resample_segments(length, params=DEFAULTS):
    """How many EQUAL segments `s5_resample` cuts an arm of this length into.

    Its own rule, and the premise the whole vertex-push model rests on: Max
    Segment Length 4 m with All Equal Segments on, which Houdini implements by
    shrinking every segment rather than leaving a short last one. Split out of
    `clear_of_vertex` so `test_plan.py` can assert it against the fixture's
    recorded `npts` — the premise had been verified by hand and asserted
    nowhere.

    ⚠️ **THE `- 1e-9` IS A GUARD AGAINST DUST, AND THE FIXTURE DOES NOT EXERCISE
    IT.** An earlier version of this docstring claimed it mattered because "10
    of the 304 edges sit exactly on an integer `L / step`" — backwards (and the
    counts were pre-M2; today it is 21 of 322). Sitting
    *exactly* on the integer is the one place `ceil` needs no help. It bites at
    `n + 1e-13 … n + 1e-9`, where a length that is arithmetically `4n` arrives a
    few ulps over and would silently gain a segment, shifting every vertex. On
    today's 322 edges **zero** need it, so nothing in the calibration can pin
    it; `test_plan.py` pins it directly instead, on both sides of the dust
    threshold.
    """
    if length <= 0.0 or params.resample_step <= 0.0:
        return 1
    return max(1, int(math.ceil(length / params.resample_step - 1e-9)))


def clear_of_vertex(cut, length, params=DEFAULTS, at_start=True):
    """`pfsg_clear_of_vertex` in closed form — and it belongs to the PLAN.

    The builder pushes a cut past a resample vertex when it would otherwise
    leave the road a sliver of a terminal segment: measured 0.028 m against a
    13.4 m half-width, and a ribbon swept along a segment that short folds. It
    moves the cut by up to `2 x min_end_segment`, one-signed, and it happens on
    190 of the 545 arms in the suite (worst +1.971 m) — big enough that a
    `standing` computed without it is optimistic on a third of the city.

    It is modelled here rather than left as a builder-side residual because it
    needs no geometry: `s5_resample` divides an arm into `ceil(L / step)` EQUAL
    segments — Houdini's All Equal Segments shrinks every segment rather than
    leaving a short last one, verified on all 322 prims — so the vertex grid is
    a function of the arm's LENGTH, which is plain edge data.

    ⚠️ Latent, and recorded because it is invisible when it bites: `length` here
    is the polyline's CHORD-SUM, while `s5_resample` counts from the input
    curve's arc length. They agree to <1e-4 relative today only because the
    input is already resampled at ~4 m. An arm whose `L / step` lands inside
    that margin of an integer flips `nseg` by one and shifts the whole grid.

    ⚠️ The VEX's two branches are NOT mirror images, and the asymmetry is
    deliberate upstream: the start branch skips vertices with `acc[i] <= s` so it
    takes the first vertex STRICTLY beyond the cut, while the end branch works
    off `acc[i-1]`, the last one at or below — which read from the arm's own end
    is the first vertex AT or beyond. They differ only for a cut landing exactly
    on a vertex, where the start branch sees a full segment of road and the end
    branch sees a zero-length sliver and pushes. Reproduced rather than
    smoothed over, because a closed form that is right except on the grid is the
    kind of thing that stays right until some case lands on it.
    """
    minseg = params.min_end_segment
    if minseg <= 0.0 or length <= 0.0 or params.resample_step <= 0.0:
        return cut
    nseg = resample_segments(length, params)
    seg = length / nseg
    if seg < 2.0 * minseg:
        return cut                      # the push would land closer than it started
    if at_start:
        i = int(math.floor(cut / seg + 1e-12)) + 1      # strictly beyond
    else:
        i = int(math.ceil(cut / seg - 1e-12))           # at or beyond
    if i < 1 or i >= nseg:
        return cut                      # no vertex past it, or it is the far end
    if i * seg - cut >= minseg:
        return cut                      # the terminal segment is already long enough
    push = i * seg + minseg
    return cut if push > length - minseg else push


def crossing_trims(node, params=DEFAULTS):
    """What today's `crossing` plate consumes from each arm: {edge_id: metres}.

    Each arm is cut past the reach of BOTH its corners, because the paved
    junction has to reach past where the kerb stops curving or the boundary
    doubles back on itself and the surface self-intersects.
    """
    arms = [a for a in node.arms
            if math.hypot(a.direction[0], a.direction[1]) > 1e-9]
    if len(arms) < 3:
        # s5j_solve solves nothing below degree 3: a corner is not a junction.
        return dict((a.edge_id, 0.0) for a in node.arms)

    order = sorted(range(len(arms)), key=lambda i: arms[i].bearing)
    n = len(order)
    reach = [_corner(arms[order[i]], arms[order[(i + 1) % n]], params)
             for i in range(n)]

    trims = dict((a.edge_id, 0.0) for a in node.arms)
    for i in range(n):
        arm = arms[order[i]]
        ahead = reach[i][0]                       # this arm as A of the next corner
        behind = reach[(i - 1 + n) % n][1]        # ...and as B of the previous one
        trims[arm.edge_id] = clear_of_vertex(max(ahead, behind, 0.0),
                                             arm.length, params, arm.at_start)
    return trims


# The noise floor this project already works to: float32 at 800 m coordinates
# drifts ~1 mm per round trip, and `graph_reaches_a_fixed_point` tolerates
# exactly that. Anything closer than this is not a difference.
RANK_TOL_M = 0.001


def default_principal(node):
    """The computed principal pair: the two arms of maximal width, as
    `principal_start` / `principal_end` claims (§11.3, artist-ratified
    2026-08-16 — widest pair, continuity is street identity, not bearing).

    Tie -> longer, then lexicographic `edge_id` (§11.3, the tongue-rank
    precedent). Artist-authored wins.

    ⚠️ **A PAIR IS TWO STREETS, so the two edge_ids must DIFFER.** A self-loop
    puts one `edge_id` on two arms, and the naive top-two returned
    ('E_loop', 'E_loop') — the boolean audit measured it — which downstream
    collapses to ONE key in any `edge_id`-keyed trim dict (`crossing_trims`
    today) and silently drops an arm ("edge_id is not a valid arm key", the
    recorded defect, still unowned). So the second pick is the best arm with a
    DIFFERENT edge_id, and a node whose arms are all one street has no pair at
    all.

    ⚠️ **THE TIE-BREAK ONLY WORKS IF THE TIE IS DETECTED, and on raw floats it
    never is.** Measured on K's third corner: three arms all 14.4 m wide, two of
    them the same 32.249 m long — and ranked, the widths differ by 5e-6 m and
    the lengths by 1.3e-12 m, so `-width` alone decided it and the documented
    lexicographic step was unreachable dead code. Which of the two identical
    triangle sides became principal, and therefore which one survived, turned on
    1.3e-12 m. Quantising to RANK_TOL_M makes the rule the doc describes the rule
    that runs. Same defect class as S8's argmin instability at `max_aspect` 1.8.
    """
    if len(node.arms) < 2:
        return ()

    def rank(a):
        return (-round(a.width / RANK_TOL_M), -round(a.length / RANK_TOL_M),
                a.edge_id)

    ranked = sorted(node.arms, key=rank)
    first = ranked[0].edge_id
    for other in ranked[1:]:
        if other.edge_id != first:
            return (first, other.edge_id)
    return ()                            # every arm is one street: no pair


def principal_of(node):
    """The authored principal pair if the booleans name one, else computed.

    An arm's `principal` flag is `principal_start` / `principal_end` read at
    this node. The authored channel wins only when it is WELL-FORMED — exactly
    two arms claiming — which is the artist ruling of 2026-08-16 made
    mechanical: cardinality is the one failure the boolean shape still permits,
    `junction_schema` reds it on the geometry, and the planner falls back down
    to the computed default rather than guessing which of one/three claims was
    meant.

    Returned sorted by `edge_id` — first-come-first-served on the DETERMINISTIC
    list, never arm order, which is cook-dependent and flipped K's outcome in
    three separate audit rounds.
    """
    flagged = sorted(a.edge_id for a in node.arms if a.principal)
    if len(flagged) == 2 and flagged[0] != flagged[1]:
        return tuple(flagged)
    return default_principal(node)


def default_junction_type(node):
    """Which node type the planner picks where the artist has not said.

    It is `crossing` at every junction, and since the 2026-08-17 ruling that is
    the END STATE, not a staging step: the crossing's open-mouth carriageway
    solve is the only correct geometry for every type (§11.5 ⛔). The planned M4
    flip to `junction` is dead — the type and the principal booleans are DATA
    for markings (zebra decals, the conditional median) and for street identity,
    and they move no geometry.

    Below degree 3 there is no plate to build — `crossing_trims` solves nothing
    there and `s5j_solve` skips the point — so the type stays `""`. That is the
    same `""` the schema uses for "decide for me", and the two are told apart by
    DEGREE, which is why `junction_schema` asserts the pairing rather than just
    checking the vocabulary (the `LOT_REJECT_VOCAB` lesson: a closed set cannot
    detect everything being relabelled to one member of it).
    """
    return "crossing" if len(node.arms) >= 3 else ""


def node_trims(node, params=DEFAULTS):
    """Dispatch on `junction_type` — MIRRORING THE BUILDER EXACTLY.

    Since the 2026-08-17 ruling (§11.5 ⛔) that is one line: **every vocabulary
    type builds the crossing's carriageway solve**, because an uncut principal's
    through-kerb and through-median block turning traffic — the artist ruled the
    M4 junction render a bug, and its build path (`jtrim_*`, `is_plate`, the
    through-end re-extension) was reverted the same day. `junction_type` and
    the principal booleans still ride the graph: they are DATA for markings
    (zebra decals, the conditional median) and street identity, not for trims.

    ⚠️ The mirror duty is the surviving lesson, not the branch table. M4's
    first version had fallbacks the builder didn't (the audit measured a
    12.93 m planner/builder disagreement under a green gate, on the
    cardinality-0 authored junction), and the fix was to make this function
    the builder's shadow, state for state. If a typed build path ever returns
    — a merge that consumes length along the principal is still M5's contract
    — it lands HERE and in `s5j_solve` in the same commit, or `standing` lies.

    A type OUTSIDE the vocabulary still raises: that is a programming error in
    the caller, not an authorable state — geometry-side it is `bad_vocab`.
    """
    kind = node.junction_type or "crossing"
    if kind not in JUNCTION_TYPE_VOCAB:
        raise ValueError("junction_type %r is outside JUNCTION_TYPE_VOCAB"
                         % (kind,))
    return crossing_trims(node, params)


def graph_trims(nodes, params=DEFAULTS):
    """{edge_id: (trim_start, trim_end)} over a whole graph.

    Which end an arm is decides which of the two it writes, exactly as
    s5j_solve's `atstart` does — a street with a junction at both ends gets one
    cut from each, which is what makes `standing` a two-ended quantity.

    The `max` mirrors the VEX's `max(dist[i], prev)` and guards something else:
    the SAME end written twice. No case in the suite produces that, so it is
    faithfulness to the builder rather than a tested path — do not read it as
    the two-junction case, which the `at_start` branch already handles.
    """
    out = {}
    for node in nodes:
        trims = node_trims(node, params)
        for arm in node.arms:
            start, end = out.get(arm.edge_id, (0.0, 0.0))
            if arm.at_start:
                start = max(start, trims.get(arm.edge_id, 0.0))
            else:
                end = max(end, trims.get(arm.edge_id, 0.0))
            out[arm.edge_id] = (start, end)
    return out


def standing(length, trim_start, trim_end):
    """What is left of a street once both its junctions have taken their bite.

    Checkable before any geometry exists, which is the point: `standing <= 0`
    means the plates have consumed more street than exists and physically
    overlap. `standing > 0` on a short street is a short street, not an error
    (§11.1 rule 2 — firing on `standing < ratio * width` instead cost a build).
    """
    return length - trim_start - trim_end


# ---------------------------------------------------------------------------
# M5 — the merge. §11.5's one type whose contract consumes carriageway.
# ---------------------------------------------------------------------------

# The parallel run: how far the re-routed minor travels ALONGSIDE the principal,
# tangent and touching, before the two fuse. §11.5 makes it a new artist parm
# with no measured default, so this is the placeholder the control rig sweeps —
# ⚠️ it is NOT a measurement, and nothing may pin a bound to it until the artist
# rules. Sized as one resample step so a merge always owns at least one full
# segment of the principal, which is the shortest run the builder can express.
MERGE_PARALLEL_RUN_M = 4.0

# The re-route swings the minor through its whole approach angle at `R_min`, so
# a merge is only possible where the minor is long enough to give that arc up.
# `R_min = 0.5 * width * turn_radius_scale` — S3b's legible floor, the same
# expression `centreline_curvature_within_class` measures against, NOT the
# junction's `corner_radius(class)`. ⚠️ Two radii live in this file now and they
# are unrelated: `corner_radius` is the KERB fillet at a crossing (4–25 m by
# class), `min_turn_radius` is the CENTRELINE's bend limit (~width). Mixing them
# silently scales every number below by ~3 (26.8 / 9.0 = 2.98).
TURN_RADIUS_SCALE = 2.0             # `graph_params_turn_radius_scale`'s default


def min_turn_radius(minor_width, turn_radius_scale=TURN_RADIUS_SCALE):
    """S3b's centreline bend floor for a street of this width.

    26.8 m arterial -> 26.8 m. Verified against §11.5's own worked number: the
    swing it quotes for "an arterial at 25°" is ~11.7 m, and
    26.8 * radians(25) = 11.694.
    """
    return 0.5 * float(minor_width) * float(turn_radius_scale)


def merge_swing_length(minor_width, angle_rad,
                       turn_radius_scale=TURN_RADIUS_SCALE):
    """Arc length the minor must spend to arrive PARALLEL: `R_min * θ`.

    θ is the whole approach angle, because the merge's target is 0° — the minor
    arrives alongside the principal, not at some softened T. This is the term
    that makes a merge cost real length rather than a corner.
    """
    return min_turn_radius(minor_width, turn_radius_scale) * abs(float(angle_rad))


def merge_feasible(minor_length, minor_width, angle_rad,
                   parallel_run=MERGE_PARALLEL_RUN_M,
                   turn_radius_scale=TURN_RADIUS_SCALE):
    """§11.5's gate: `minor length >= R_min(class) * θ + a parallel run`.

    Infeasible is NOT a failure and NOT a deletion — §11.1 rule 5, the
    resolution ladder: the planner falls back to a T realign, then to the
    spread. `False` here means "choose another rung", never "refuse the
    connection".
    """
    need = merge_swing_length(minor_width, angle_rad, turn_radius_scale) + \
        float(parallel_run)
    return float(minor_length) >= need


def merge_tangent_length(minor_width, angle_rad,
                         turn_radius_scale=TURN_RADIUS_SCALE):
    """Where the re-routed minor LANDS on the principal: `R * tan(theta/2)`.

    §11.6's construction is "a curve through pinned endpoints, tangency at the
    landing". ⚠️ **The landing is NOT the node**, and that is forced rather
    than chosen: a circle tangent to the principal AT the node has its centre
    on the normal there, and its distance to the minor's line is then
    `R*cos(theta)`, which equals `R` only at `theta = 0`. So no arc can be
    tangent to the principal at the node AND leave the minor tangentially.

    What does exist is the arc inscribed in the corner between the minor's ray
    and the principal's CONTINUING direction - an angle of `pi - theta` - whose
    two tangent points both sit `T = R*tan(theta/2)` from the node: one back
    along the minor, one forward along the principal. The minor gives up its
    last `T` and gains an arc of `R*theta` in its place; the principal gives up
    `T` of its downstream arm.
    """
    r = min_turn_radius(minor_width, turn_radius_scale)
    return r * abs(math.tan(0.5 * float(angle_rad)))


def merge_consumed_along_principal(minor_width, angle_rad,
                                   parallel_run=MERGE_PARALLEL_RUN_M,
                                   turn_radius_scale=TURN_RADIUS_SCALE):
    """What the merge takes from the principal's DOWNSTREAM arm - a length,
    not a radius (§11.5), and a per-ARM number so `standing` can use it.

    `T + run`: the arc lands `T` along the principal and the two run together
    for `parallel_run` before fusing. The UPSTREAM arm pays nothing - the
    construction never reaches it - so this belongs to exactly one arm's trim.

    ⚠️ **THIS RETURNED `R*sin(theta) + run` UNTIL 2026-08-17, WHICH IS A
    DIFFERENT QUANTITY AND NOT A PER-ARM ONE.** `R*sin(theta)` is the span
    between the fillet's two tangent points measured along the principal, so it
    STRADDLES the node; written into one arm's trim it over-charges that arm
    (15.33 m against 9.94 m at 25° on an arterial, 54%) and under-charges the
    other by everything. An audit caught it before a consumer existed. The
    identity that connects them, and the reason the wrong one looked
    plausible: `T*(1 + cos theta) = R*sin(theta)`.
    """
    return merge_tangent_length(minor_width, angle_rad, turn_radius_scale) \
        + float(parallel_run)


def merge_arc_length(minor_width, angle_rad,
                     turn_radius_scale=TURN_RADIUS_SCALE):
    """The arc the minor travels instead of its last straight `T`: `R*theta`.

    So a merge LENGTHENS the minor by `R*(theta - tan(theta/2))` - 5.75 m on an
    arterial at 25°. It is the same number `merge_feasible` charges, which is
    why that gate is conservative: the construction only needs `T` of minor
    (3.35 m for a collector at 25°) while the gate asks for `R*theta + run`
    (10.59 m). Conservative is the safe direction for a feasibility test; do
    not "fix" it into the tighter bound without the artist ruling on the
    parallel run first.
    """
    return merge_swing_length(minor_width, angle_rad, turn_radius_scale)
