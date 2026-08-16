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

# §11.3's node schema, named once. The adapter writes these and `checks.py`
# polices them; before this constant existed the set was spelled out in three
# places and a fourth attribute could have been added in one and policed in
# none.
NODE_SCHEMA_ATTRS = ("junction_type", "principal_edges")

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
# minus measured, over all 539 arms:
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
# ⚠️ Both are bounds on the RESIDUAL, not on the verdict. Measured over all 318
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
                 at_start=True):
        self.edge_id = edge_id
        self.direction = (float(direction[0]), float(direction[1]))
        self.width = float(width)
        self.street_class = street_class
        self.length = float(length)
        self.at_start = bool(at_start)

    @property
    def bearing(self):
        return math.atan2(self.direction[1], self.direction[0])

    @property
    def half_width(self):
        return self.width * 0.5


class Node(object):
    def __init__(self, node_id, pos, arms, junction_type="", principal_edges=()):
        self.node_id = node_id
        self.pos = (float(pos[0]), float(pos[1]))
        self.arms = list(arms)
        self.junction_type = junction_type
        self.principal_edges = tuple(principal_edges)


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
    counts were pre-M2; today it is 19 of 318). Sitting
    *exactly* on the integer is the one place `ceil` needs no help. It bites at
    `n + 1e-13 … n + 1e-9`, where a length that is arithmetically `4n` arrives a
    few ulps over and would silently gain a segment, shifting every vertex. On
    today's 318 edges **zero** need it, so nothing in the calibration can pin
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
    190 of the 539 arms in the suite (worst +1.971 m) — big enough that a
    `standing` computed without it is optimistic on a third of the city.

    It is modelled here rather than left as a builder-side residual because it
    needs no geometry: `s5_resample` divides an arm into `ceil(L / step)` EQUAL
    segments — Houdini's All Equal Segments shrinks every segment rather than
    leaving a short last one, verified on all 318 prims — so the vertex grid is
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
    """The computed `principal_edges` default: the two arms of maximal width.

    Tie -> longer, then lexicographic `edge_id` (§11.3, the tongue-rank
    precedent). Artist-authored wins.

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
    return (ranked[0].edge_id, ranked[1].edge_id)


def principal_of(node):
    """Authored `principal_edges` if present, else the computed default."""
    authored = tuple(e for e in node.principal_edges if e)
    return authored if len(authored) == 2 else default_principal(node)


def junction_trims(node, principal=None, params=DEFAULTS):
    """What a `junction` plate consumes: the principal pair runs through unbroken.

    §11.5: the principal pair is ONE continuous street through the node — no
    break, no mouth, no trim contribution from this node. The minors are left
    unchanged, and that IS exact for the model: each arm's cut in
    `crossing_trims` depends only on its own two corners, so removing the
    principal's cut cannot move a minor's.

    ⚠️ **BUT "unchanged minors" IS NOT THE SAME CLAIM AS "this is §11.5's
    plate", and M4 must close three gaps this model cannot decide alone.**
    Recorded with numbers rather than resolved, because the builder contract is
    11.12's call and guessing it here would put M1's verdict behind a fiction:

      1. **Two ADJACENT minors with no principal between them.** This model
         charges their minor-to-minor kerb corner; §11.5's plate is "a rectangle
         on the principal spanning the minor mouths" and has no such corner in
         it. Measured on an E-W arterial principal with 14.4 m minors at 70 deg
         and 110 deg: model 30.772 m against 22.593 m for flank-only — **8.18 m
         apart**, the model the more conservative of the two.
      2. **`max_fillet_fraction` is capped on the principal ARM's length, not
         the through-length** it would have as one continuous street (see
         `_corner`'s `min(a.length, b.length)`). Measured on 30 m principal arms
         with `corner_radius_scale` 4: a minor trims 25.400 m under the arm cap
         and 29.400 m under the 60 m through cap — **4.0 m**, and this one goes
         the UNSAFE way, the model under-charging the minor.
      3. **The default principal need not run through at all.** At K's node A
         the widest pair sits **70.0 deg** apart (node B's is 113.4), and this
         returns zero trim on both arms of it. Nothing here signals that a
         "principal street" bends 110 degrees through its own junction.
    """
    if principal is None:
        principal = principal_of(node)
    trims = crossing_trims(node, params)
    for edge_id in principal:
        if edge_id in trims:
            trims[edge_id] = 0.0
    return trims


def default_junction_type(node):
    """Which node type the planner picks where the artist has not said.

    ⚠️ Today it is `crossing` at every junction — deliberately, and it is the
    whole point of M3: the schema lands, the adapter runs, and the geometry does
    not move by so much as a float. M4 is where this returns `junction` and the
    gate is expected to move (§11.9's rollout: authored-only first, then flip the
    computed default in its own commit).

    Below degree 3 there is no plate to build — `crossing_trims` solves nothing
    there and `s5j_solve` skips the point — so the type stays `""`. That is the
    same `""` the schema uses for "decide for me", and the two are told apart by
    DEGREE, which is why `junction_schema` asserts the pairing rather than just
    checking the vocabulary (the `LOT_REJECT_VOCAB` lesson: a closed set cannot
    detect everything being relabelled to one member of it).
    """
    return "crossing" if len(node.arms) >= 3 else ""


def node_trims(node, params=DEFAULTS):
    """Dispatch on `junction_type`. `""` means decide for me, and the decided
    default is `crossing` — what the builder does today, everywhere (§11.5)."""
    kind = node.junction_type or "crossing"
    if kind == "junction":
        return junction_trims(node, params=params)
    if kind == "crossing":
        return crossing_trims(node, params)
    raise ValueError("no builder contract for junction_type %r" % (kind,))


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
