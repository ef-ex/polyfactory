"""polyChain's pure-Python solve, under GENERATED input (v2 principle 2).

    python -m pytest tests/unit/test_polychain_properties.py -q

Hypothesis replaces the enumerated case grids in `test_polychain_plan.py`
(4 modes x 6 lengths, hand-picked) with the property those grids were
approximating.  The retrospective's single commonest failure class was "the
check was fine but no fixture ever reached the code"; a grid of six lengths
cannot reach a length that breaks the solve, and a generator can.

Determinism is part of the contract: a failing example prints its input, and
Hypothesis's own `.hypothesis/examples` database re-runs it first next time.
A failure worth keeping becomes a one-line `@example(...)` pin above the
property it broke - that is what a regression fixture is FOR, and the only
thing a hand fixture is still for.

WHAT THESE CANNOT SEE: anything that needs Houdini.  The scene-side generator
is `tests/polychain/gen_cases.py`; this file must never import `hou`, and the
last test in it asserts exactly that.
"""

import math
import os
import sys

from hypothesis import assume, example, given, settings, strategies as st

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "polyfactory", "scripts", "python",
                                "polyfactory"))

import polychain as pc                                          # noqa: E402
from polychain import array2d as a2                             # noqa: E402
from polychain import corner as cn                              # noqa: E402
from polychain import decompose as dc                           # noqa: E402
from polychain import plan                                      # noqa: E402

# The span is asserted RELATIVE, because "1e-9 m" on a 20 km run is a claim
# about float64 that is not true: 20000.0 carries an ulp of ~3.6e-12, and 5000
# accumulated pieces of it is already past 1e-9.  1e-12 relative is 2e-8 m at
# 20 km and 1e-12 m at 1 m - the tolerance stated at the magnitude it applies
# at, which the skill's rule 4 asks for.
REL = 1e-12

# Per cycle this file has to fit inside a 5-minute budget shared with the
# differential and mutation runs, so the example counts are scaled by one env
# var rather than tuned per test: `PC_EXAMPLES=1000` is the milestone sweep,
# the default is the per-cycle pass.  Hypothesis re-runs every previously
# failing example from `.hypothesis/examples` FIRST regardless of the budget,
# so a shrunk count never loses a known counterexample.
EX = int(os.environ.get("PC_EXAMPLES", "120"))

lengths = st.floats(1e-3, 20000.0, allow_nan=False, allow_infinity=False)
nominals = st.floats(1e-3, 50.0, allow_nan=False, allow_infinity=False)
pads = st.floats(-2.0, 5.0, allow_nan=False, allow_infinity=False)
modes = st.sampled_from(sorted(pc.FILL_MODES))


def params(**kw):
    return pc.Params(**kw)


def total(res, nominal, gap=0.0, fixed=0.0):
    """The span a fit result claims to occupy.  One identity, every mode."""
    n = res["count"]
    if n == 0:
        return res["remainder"]
    t = n * (nominal * res["scale"] + fixed) + max(n - 1, 0) * gap
    if res["slice"]:
        t += gap + res["remainder"]
    return t


# --- fit --------------------------------------------------------------------

@given(L=lengths, s=nominals, mode=modes, gap=pads, fixed=pads,
       count=st.integers(0, 12), pct=st.floats(0.0, 100.0))
@settings(max_examples=EX * 3, deadline=None)
def test_every_mode_fills_the_span_exactly(L, s, mode, gap, fixed, count, pct):
    """THE property the 4x6 grid was sampling - and `tile`'s honest half.

    Excluded, and stated rather than silently skipped: a fit that WARNS is a
    degenerate one (D17 - the padding cancels or reverses the unit, or the
    count hit MAX_UNITS), and its contract is "a plan and a warning, never an
    exception", not exact fill.

    ⚠️ `tile` DOES NOT ALWAYS FILL EXACTLY, and the hand grid could not see
    it: it only ever ran tile at `gap = 0`, where the leftover always becomes
    a slice and the identity closes.  Generation found `L=2, s=1, gap=1` in
    under a second - one whole tile, one trailing gap, `slice` False and a
    metre of span unclaimed.  That is tile's actual contract (whole units, and
    what is left over is left over), so the property is the TRUE one: tile
    never overruns, and never leaves room for one more unit.
    """
    res = plan.fit(L, s, mode, params(fill=mode, count=count,
                                      adaptive_pct=pct), gap, fixed)
    assume(not res["warns"])
    assume(res["count"] > 0)
    got, tol = total(res, s, gap, fixed), REL * max(L, 1.0)
    if mode == "tile":
        # ⚠️ The overrun bound is `fit`'s OWN admission slack, not zero, and
        # generation is what put a number on it: `whole` is floored on
        # `(L + gap + EPS) / step`, so a unit that misses by under EPS is
        # admitted and the run ends up to `n * EPS` past the span.  EPS is
        # 1e-9 METRES (`polychain.EPS`) - one nanometre, absolute, at any
        # world scale - and that is the tolerance stated at its real
        # magnitude rather than a REL that would silently grow to 20 nm at
        # 20 km.  Counterexample that produced this line: L=1, s=1,
        # fixed=1e-9, which overran by exactly 1.0000000827e-09.
        slack = pc.EPS * max(res["count"], 1) + tol
        assert got <= L + slack, "tile overran the span by %.17g" % (got - L)
        assert L - got < s + fixed + gap + slack, (
            "tile left %.17g of a %.17g span, and one more unit costs %.17g"
            % (L - got, L, s + fixed + gap))
    else:
        assert abs(got - L) <= tol, (
            "mode %s: fit claims %.17g of a %.17g span" % (mode, got, L))


@given(L=lengths, s=nominals, gap=pads, fixed=pads, pct=st.floats(0.0, 100.0))
@settings(max_examples=EX * 2, deadline=None)
def test_adaptive_never_slices(L, s, gap, fixed, pct):
    """`adaptive` is the default precisely because a window may not be cut."""
    res = plan.fit(L, s, "adaptive", params(fill="adaptive",
                                            adaptive_pct=pct), gap, fixed)
    assert not res["slice"] and res["remainder"] == 0.0


@given(L=lengths, s=nominals, mode=modes, gap=pads, fixed=pads,
       count=st.integers(-5, 500000))
@settings(max_examples=EX * 2, deadline=None)
@example(L=1.0, s=1e-3, mode="count", gap=0.0, fixed=0.0, count=500000)
def test_fit_warns_but_never_blocks(L, s, mode, gap, fixed, count):
    """Warn-never-block, and the MAX_UNITS ceiling, on any input at all."""
    res = plan.fit(L, s, mode, params(fill=mode, count=count), gap, fixed)
    assert 0 <= res["count"] <= pc.MAX_UNITS
    assert res["scale"] >= 0.0 and res["remainder"] >= 0.0
    assert not math.isnan(res["scale"])


# --- evenly -----------------------------------------------------------------

@given(L=lengths, d=st.floats(0.0, 50.0), n=st.integers(0, 30),
       j=st.sampled_from(sorted(pc.JUSTIFY)), ate=st.floats(0.0, 5.0))
@settings(max_examples=EX * 2, deadline=None)
def test_evenly_anchors_are_ordered_and_inside_the_span(L, d, n, j, ate):
    # ⚠️ BOUNDED, AND THE BOUND IS ITSELF A FINDING - see
    # `test_evenly_ignores_the_MAX_UNITS_ceiling` below.  `evenly` returns one
    # anchor per step with NO ceiling, so `d` a few orders below `L` hangs the
    # process rather than failing it.  Hypothesis at 1500 examples reached it
    # and the run stopped being a test.
    assume(d <= 0.0 or L / d <= 20000.0)
    a = plan.evenly(L, params(evenly_spacing=d, evenly_count=n, justify=j,
                              adjust_to_end=ate))
    assume(a)
    assert all(a[i] < a[i + 1] for i in range(len(a) - 1)), "not increasing"
    assert a[0] > 0.0 and a[-1] <= L + REL * max(L, 1.0)
    if n > 0:
        assert len(a) == n, "count mode must give exactly n anchors"


@given(L=lengths, d=st.floats(1e-3, 50.0))
@settings(max_examples=EX, deadline=None)
def test_evenly_center_is_symmetric_about_the_span(L, d):
    """RailClone's Justify=center: the LEADING space equals the trailing one.

    Centring on the span MULTIPLE instead shoves the whole run to the far end,
    and reads as an off-centre fence in the viewport - a defect no count-based
    assertion can see.
    """
    # `evenly` returns ONE ANCHOR PER STEP, so a 20 km span at 1 mm spacing
    # builds a 20-million-element list.  Bounded here because this property is
    # about symmetry, not about the list's size; the cost of a dense run is a
    # COST question, and it belongs in a ceiling with a number on it
    # (`checks.py`'s tripwires), not in a correctness assertion.
    assume(L / d <= 20000.0)
    a = plan.evenly(L, params(evenly_spacing=d, justify="center"))
    assume(a)
    assert abs(a[0] - (L - a[-1])) <= REL * max(L, 1.0)


def test_evenly_ignores_the_MAX_UNITS_ceiling():
    """RECORDED DEFECT, 2026-08-25, found by the property above at 1500
    examples: `plan.fit` clamps its count to `MAX_UNITS` and warns; `evenly`
    does not clamp at all.

    `Evenly Spacing` is an artist parm in metres.  Typing 0.000001 into it
    asks `evenly` to build a list of one million floats on a 1 m span, and a
    smaller value asks for more than memory holds - measured: `evenly(1000.0,
    spacing=1e-6)` does not return within 60 s.  There is no exception and no
    warning, so `warn-never-block` is not what happens either; the node hangs.

    This test asserts what the build DOES, not what it should do - the M2
    "cases before mechanism" convention.  It is fast (1e6 floats, ~0.1 s) and
    it FAILS the day a ceiling lands, which is when this whole docstring gets
    deleted along with it.  Not fixed here: this is the test cycle.
    """
    n = len(plan.evenly(1.0, params(evenly_spacing=1e-6)))
    assert n == 999999, "the anchor count changed: %d" % n
    assert n > pc.MAX_UNITS, (
        "`evenly` now respects a ceiling - delete this test and the note in "
        "`test_evenly_anchors_are_ordered_and_inside_the_span`")


# --- pack: padding moves the NEIGHBOUR --------------------------------------

@given(la=nominals, lb=nominals, pa=st.tuples(pads, pads),
       pb=st.tuples(pads, pads), scale=st.floats(0.0, 4.0),
       cursor=st.floats(-100.0, 100.0))
@settings(max_examples=EX * 2, deadline=None)
def test_padding_moves_the_neighbour_not_the_padded_piece(la, lb, pa, pb,
                                                          scale, cursor):
    """The RailClone semantic a naive "add the pad to the piece" gets backwards.

    Its symptom is a drift down a long run, which no single-piece assertion
    reaches - so it is stated as an identity on any two adjacent pieces.
    """
    a = pc.Module("a", (la, 1.0, 0.1), pad=pa)
    b = pc.Module("b", (lb, 1.0, 0.1), pad=pb)
    s0, s1, cur = plan.pack(cursor, a, scale)
    t0, t1, _ = plan.pack(cur, b, scale, prev=a)
    assert abs((s1 - s0) - la * scale) <= REL * max(abs(la * scale), 1.0)
    assert abs((t1 - t0) - lb * scale) <= REL * max(abs(lb * scale), 1.0)
    assert abs((t0 - s1) - (pa[1] + pb[0])) <= REL * max(abs(t0), 1.0)


# --- the whole solve, end to end --------------------------------------------

KIT = pc.Kit("gen_kit", human_scale_reference=1.8, modules=[
    pc.Module("panel", (2.0, 1.0, 0.1), deform=pc.DEFORM_BEND,
              roles="default"),
    pc.Module("tile", (1.3, 1.0, 0.1), deform=pc.DEFORM_SLICE,
              roles="default"),
])


@given(L=st.floats(1e-3, 5000.0), mode=modes, gap=st.floats(-0.5, 2.0),
       count=st.integers(0, 8), pct=st.floats(0.0, 100.0),
       which=st.sampled_from(("panel", "tile")))
@settings(max_examples=EX, deadline=None)
def test_plan_section_reaches_both_ends_and_is_deterministic(L, mode, gap,
                                                             count, pct, which):
    kit = pc.Kit("gen_kit", human_scale_reference=1.8, modules=[
        pc.Module(m.name, m.size, deform=m.deform, roles="default",
                  pad=(gap, gap)) for m in KIT.modules])
    style = pc.Style("s", seed=0, rules=[
        pc.Rule("default", select="first", modules=[which])])
    p = params(fill=mode, count=count, adaptive_pct=pct)
    sec = dc.Section("c", 0, 0.0, L, L)
    got = plan.plan_section(sec, kit, style, p)
    again = plan.plan_section(sec, kit, style, p)
    assert plan.plan_dicts(got) == plan.plan_dicts(again), "not deterministic"
    assume(got)
    assume(not any(pl.warns for pl in got))
    # ⚠️ EXCLUDED, AND THE EXCLUSION IS ITSELF A FINDING - see
    # `test_count_mode_overhangs_the_section_on_negative_padding`.  `count`
    # mode with an overlapping pad places pieces OUTSIDE the section, with no
    # warning.  Every other mode holds the contract at every pad.
    assume(not (mode == "count" and gap < 0.0))
    assert abs(min(pl.s0 for pl in got)) <= REL * max(L, 1.0)
    end = max(pl.s1 for pl in got)
    if mode == "tile":
        # tile's honest half again, one level up - see the note on
        # `test_every_mode_fills_the_span_exactly`.  Generation reached it
        # here too (L=2, gap=1, module `tile`: the run ends at 1.3 of 2.0).
        assert end <= L + REL * max(L, 1.0), "tile overran by %.17g" % (end - L)
    else:
        assert abs(end - L) <= REL * max(L, 1.0)
    for a, b in zip(got, got[1:]):
        assert b.s0 >= a.s0, "placements are not in span order"


def test_count_mode_overhangs_the_section_on_negative_padding():
    """RECORDED DEFECT, 2026-08-25, found by the property above.

    `fill = count` with a NEGATIVE pad (RailClone's legal overlap) lays the
    run outside its own section and says nothing.  Measured on a 0.5 m
    section, module 2.0 m, pad -0.5 both sides, count 2: the pieces land at
    (-0.25, 0.5) and (0.0, 0.75) - a 0.25 m overhang at BOTH ends, a run
    extent of 1.0 m over a 0.5 m span, and no `warns` entry at all.  At
    pad -1.0 the same input DOES warn (`pc_warn_degenerate_pad`), and
    `adaptive`, `tile` and `scale` all stay inside the section at every pad,
    so this is neither the degenerate-pad guard firing nor a general property
    of overlap - it is `count`'s own.

    Asserted as what the build DOES (M2's "cases before mechanism"), so the
    day the run is clamped or the overhang is warned, this test fails and
    gets deleted with its finding.  Not fixed here: this is the test cycle.
    """
    kit = pc.Kit("k", human_scale_reference=1.8, modules=[
        pc.Module("panel", (2.0, 1.0, 0.1), deform=pc.DEFORM_BEND,
                  roles="default", pad=(-0.5, -0.5))])
    style = pc.Style("s", seed=0,
                     rules=[pc.Rule("default", "first", ["panel"])])
    got = plan.plan_section(dc.Section("c", 0, 0.0, 0.5, 0.5), kit, style,
                            params(fill="count", count=2))
    spans = [(round(p.s0, 4), round(p.s1, 4)) for p in got]
    assert spans == [(-0.25, 0.5), (0.0, 0.75)], spans
    assert not any(p.warns for p in got), "it warns now - delete this test"


# --- decompose, on generated topology ---------------------------------------

point = st.tuples(st.floats(-500, 500), st.floats(-500, 500),
                  st.floats(-500, 500))


@given(pts=st.lists(point, min_size=0, max_size=24),
       closed=st.booleans(), corner_deg=st.floats(0.0, 180.0))
@settings(max_examples=EX * 2, deadline=None)
@example(pts=[(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)],
         closed=False, corner_deg=30.0)      # DUPLICATE POINTS - `_clean`
@example(pts=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)], closed=True,
         corner_deg=30.0)                    # a closed 2-point curve
def test_decompose_tiles_the_curve_and_never_raises(pts, closed, corner_deg):
    """Sections abut, in order, and together they are the curve - or there are
    none at all (D8: a curve with under two distinct points is not placeable).

    Duplicate points and closed 2-point curves are pinned as `@example`s
    because they are the shapes a hand fixture never carries and `_clean`
    exists for.
    """
    curve = pc.Curve("c", [tuple(p) for p in pts], closed=closed)
    secs = dc.decompose(curve, params=params(corner_angle_deg=corner_deg))
    if not secs:
        return
    assert all(s.s1 - s.s0 >= 0.0 for s in secs)
    for a, b in zip(secs, secs[1:]):
        assert abs(b.s0 - a.s1) <= 1e-9, "sections do not abut"
    span = sum(s.s1 - s.s0 for s in secs)
    assert span <= curve.length + 1e-6
    if not closed:
        assert abs(span - curve.length) <= 1e-6 * max(curve.length, 1.0)


# --- 4.3 corners: the hand grids these replace are named in polychain.md 33.1

CKIT = pc.Kit("ck", 1, [
    pc.Module("panel", (2.0, 0.9, 0.06), deform=pc.DEFORM_BEND,
              roles="default"),
    pc.Module("post", (0.16, 1.3, 0.16), deform=0, roles="corner"),
    pc.Module("block", (1.2, 1.3, 0.16), deform=0, roles="corner"),
], 1.8)

dirs = st.tuples(st.floats(-1.0, 1.0), st.floats(-1.0, 1.0),
                 st.floats(-1.0, 1.0))


def bev(tin, tout, params=pc.DEFAULTS):
    """A corner-less `Bevel` - `corner=None` is `_bevel_between`'s own call
    for a boundary `decompose` scored non-degenerate."""
    return cn.Bevel(None, (0.0, 0.0, 0.0), tin, tout, params)


def _leg(deg):
    return (math.cos(math.radians(deg)), 0.0, math.sin(math.radians(deg)))


@given(tin=dirs, tout=dirs, h=st.floats(0.0, 5.0), thr=st.floats(0.0, 90.0))
@settings(max_examples=EX * 2, deadline=None)
@example(tin=(1.0, 0.0, 0.0), tout=(-1.0, 0.0, 0.0), h=0.03, thr=15.0)
# ⚠️ THE CLAMP WINDOW IS PINNED - 174.3 to 179.999 degrees, which random
# directions do not reach and a deleted clamp SURVIVED without.  33.1.
@example(tin=(1.0, 0.0, 0.0), tout=_leg(178.0), h=0.03, thr=0.0)
@example(tin=(1.0, 0.0, 0.0), tout=_leg(176.0), h=0.03, thr=0.0)
def test_the_bevel_bisects_overhangs_by_tan_half_and_never_nans(tin, tout, h,
                                                                thr):
    """4.3's trigonometry on any pair of legs, plus D39's ONE unmoving plane.
    33.1.  CANNOT SEE: where a piece is cut, only what it is cut on."""
    assume(cn._len(tin) > 1e-6 and cn._len(tout) > 1e-6)
    b = bev(tin, tout, pc.Params(min_included_angle_deg=thr))
    assert all(v == v for v in b.n), "the bisector went NaN"
    assert abs(cn._len(b.n) - 1.0) <= 1e-9
    assert abs(b.tan_half) <= cn.MAX_TAN_HALF
    assert b.side in (1.0, -1.0)
    assert b.e_for(h) == b.e_for(-h) >= 0.0
    summed = cn._len(cn._add(b.tin, b.tout))
    assert b.degenerate == (summed < 1e-6 or (180.0 - b.turn) < thr)
    assert (pc.WARN_CORNER_DEGENERATE in b.warns) == b.degenerate
    if b.degenerate:
        assert b.mode == "bend", "a hairpin must not be cut on noise"
        return
    half = math.radians(b.turn) * 0.5
    # Bounded, and the bound is the code's own: past 179.999 degrees
    # `tan_half` is CLAMPED to MAX_TAN_HALF on purpose, so the identity below
    # is asserted where it is claimed and the clamp is asserted above.
    assume(summed > 1e-3 and b.turn < 179.999
           and math.tan(half) <= cn.MAX_TAN_HALF)
    assert abs(cn._dot(b.n, b.tin) - cn._dot(b.n, b.tout)) <= 1e-9
    assert abs(cn._dot(b.n, b.tin) - math.cos(half)) <= 1e-9
    assert abs(b.e_for(h) - h * math.tan(half)) <= 1e-9 * max(h, 1.0)
    for o in (0.0, 0.04, -0.04, 5.0):        # D39: the PIECES move, not it
        b.offset = o
        assert b.plane_in()[0] == b.plane_out()[0] == b.v
        assert (b.plane_in()[2], b.plane_out()[2]) == (-1.0, 1.0)
    # A REFLEX CORNER IS THE SAME MITER, MIRRORED, and `side` is all that
    # moves - as the MIRROR, not as the code's own test (33.1).  CANNOT SEE a
    # leg plumb enough for `across` to take its fallback.  1e-6 DEGREES
    # because `_turn_deg` is an acos.
    d = cn._dot(b.tout, b.across)
    if abs(d) > 1e-6:
        m = bev(b.tin, cn._sub(b.tout, cn._mul(b.across, 2.0 * d)),
                pc.Params(min_included_angle_deg=thr))
        assert m.side == -b.side and abs(m.turn - b.turn) <= 1e-6


@given(tin=dirs, tout=dirs)
@settings(max_examples=EX, deadline=None)
def test_flatten_is_vertical_carries_its_arc_factor_and_refuses_a_plumb_leg(
        tin, tout):
    """D48 - the plane that cuts a plumb piece is vertical too, and the leg
    coordinate it measures in is HORIZONTAL, so `arc_*` converts back."""
    assume(cn._len(tin) > 1e-6 and cn._len(tout) > 1e-6)
    b = bev(tin, tout)
    tin3, tout3 = b.tin, b.tout
    lin = math.hypot(tin3[0], tin3[2])
    lout = math.hypot(tout3[0], tout3[2])
    b.flatten()
    if lin < 1e-6 or lout < 1e-6:
        assert not b.flat and b.arc_in == 1.0 and b.arc_out == 1.0
        return
    assert b.flat and abs(b.n[1]) <= 1e-9, "the flattened plane is not vertical"
    # RELATIVE: a near-plumb leg makes `arc` 7e4 (rule 4).
    assert abs(b.arc_in - 1.0 / lin) <= REL * max(1.0 / lin, 1.0)
    assert abs(b.arc_out - 1.0 / lout) <= REL * max(1.0 / lout, 1.0)
    assert b.tin3 == tin3 and b.tout3 == tout3, "the 3D leg was lost"
    n1, turn1 = b.n, b.turn
    b.flatten()          # a flat corner is not flattened twice
    assert abs(b.arc_in - 1.0) <= 1e-12 and abs(b.arc_out - 1.0) <= 1e-12
    assert abs(b.turn - turn1) <= 1e-6           # acos noise, 33.1
    if b.degenerate:
        assert b.mode == "bend"
    else:
        assert max(abs(x - y) for x, y in zip(b.n, n1)) <= 1e-12


@given(names=st.lists(st.sampled_from(("post", "block")), min_size=1,
                      max_size=6),
       mode=st.sampled_from(("miter", "bend")), pct=st.floats(-40.0, 40.0))
@settings(max_examples=EX, deadline=None)
def test_compose_lays_out_the_odd_even_rule(names, mode, pct):
    """D38, recovered rather than special-cased: the straddler is
    `floor((N-1)/2)`, miter duplicates it one copy per leg, and `symmetry` is
    exactly the difference of the two flanks.  33.1."""
    mods = [CKIT.by_name(n) for n in names]
    b = bev((1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    b.mode = mode
    a = cn.build_assembly(b, mods, None,
                          pc.Params(corner_mode=mode, corner_offset_pct=pct))
    n, c = len(mods), (len(mods) - 1) // 2
    dupes = [p for p in a.pieces if p.duplicate]
    assert len(a.pieces) == n + (1 if mode == "miter" else 0)
    assert all(p.compose_index == c and p.module is mods[c] for p in dupes)
    if mode == "bend":
        assert not dupes                       # D37: no joint, so no slice
        assert abs(a.pieces[0].t_far - mods[c].length * 0.5) <= 1e-9
        assert abs(a.pieces[0].t_near + mods[c].length * 0.5) <= 1e-9
    else:
        assert sorted(p.side for p in dupes) == ["in", "out"]
        e = b.e_for(cn._half_width(mods[c]))
        for p in dupes:
            assert abs(p.t_near - (-e + b.offset)) <= 1e-9
            assert abs((p.t_far - p.t_near) - mods[c].length) <= 1e-9
    flanks = (sum(m.length for m in mods[:c]),
              sum(m.length for m in mods[c + 1:]))
    assert abs(a.symmetry - abs(flanks[0] - flanks[1])) <= 1e-9
    if len(set(names)) == 1:
        assert abs(a.symmetry - (0.0 if n % 2 else mods[0].length)) <= 1e-9


@given(policy=st.sampled_from(sorted(pc.CORNER_DISPLACEMENTS)),
       mode=st.sampled_from(("miter", "bend")), off=st.floats(-1.0, 1.0),
       turn=st.floats(0.5, 179.0), missing=st.booleans())
@settings(max_examples=EX, deadline=None)
def test_the_three_displacement_policies_are_three_numbers(policy, mode, off,
                                                           turn, missing):
    """D40 revised - three policies, three numbers, miter only, and the
    offset is NOT folded in (D39 already moves the pieces).  33.1."""
    t = math.radians(turn)
    b = bev((1.0, 0.0, 0.0), (math.cos(t), 0.0, math.sin(t)))
    b.mode, b.offset = mode, off
    mod = None if missing else CKIT.by_name("panel")
    p = pc.Params(corner_displacement=policy)
    got = cn.displacement(b, mod, p)
    if mode != "miter" or mod is None:
        assert got == 0.0
        return
    want = {"reset": 0.0, "extend": b.e_for(cn._half_width(mod)),
            "symmetric": mod.length * 0.5}[policy]
    assert abs(got - want) <= 1e-12
    b2 = bev((1.0, 0.0, 0.0), (math.cos(t), 0.0, math.sin(t)))
    b2.mode, b2.offset = mode, 0.0
    assert cn.displacement(b2, mod, p) == got, "the offset leaked back in"
    assert pc.Params(corner_displacement=policy.title()
                     ).corner_displacement == "reset"


@given(pts=st.lists(st.tuples(st.floats(-30, 30), st.floats(-4, 4),
                              st.floats(-30, 30)), min_size=0, max_size=7),
       closed=st.booleans(), mode=st.sampled_from(sorted(pc.CORNER_MODES)),
       pct=st.floats(-40.0, 40.0), radius=st.floats(0.0, 4.0))
@settings(max_examples=EX, deadline=None)
def test_plan_curve_never_raises_addresses_uniquely_and_repeats(pts, closed,
                                                                mode, pct,
                                                                radius):
    """Warn-never-block over the WHOLE orchestrator, plus D1's address rule -
    a closed footprint corners every section at both ends.  33.1."""
    p = pc.Params(fill="adaptive", corner_mode=mode, corner_offset_pct=pct,
                  fillet_radius=radius)
    style = pc.Style("t", 1, 1, rules=[
        pc.Rule("default", "first", ["panel"]),
        pc.Rule("corner", "first", ["post"])], params=p)
    curve = pc.Curve("c", [tuple(q) for q in pts], closed=closed)
    assert cn.fillet(curve, pc.Params(fillet_radius=0.0)) == (curve, ())
    curve, _w = cn.fillet(curve, p)
    secs = dc.decompose(curve, (), p)
    out, _b, _s = cn.plan_curve(curve, secs, CKIT, style, p)
    assert isinstance(out, list)
    assert pc.Params(fillet_segments=5).fillet_segments == 6       # D42
    ids = [pl.elem_id for pl in out]
    assert len(ids) == len(set(ids)), "two pieces share one address"
    again = cn.plan_curve(curve, dc.decompose(curve, (), p), CKIT, style, p)[0]
    assert [pl.as_dict() for pl in out] == [pl.as_dict() for pl in again]


# --- 7 array2d: the hand grids these replace are named in polychain.md 33.1

YKIT = pc.Kit("yk", 1, [
    pc.Module("default", (3.0, 3.2, 0.3), roles="default"),
    pc.Module("default_start", (3.0, 4.0, 0.3), roles="default_start"),
    pc.Module("default_end", (3.0, 1.0, 0.3), roles="default_end"),
], 1.8)
YRULES = [pc.Rule("start", "first", ["default_start"], axis="y"),
          pc.Rule("default", "first", ["default"], axis="y"),
          pc.Rule("end", "first", ["default_end"], axis="y")]


@given(x=st.sampled_from(sorted(pc.SLOTS) + ["marker:7"]),
       y=st.sampled_from(sorted(pc.SLOTS) + ["marker:2"]),
       invented=st.sampled_from(("corner_post", "sill", "my_own_thing")))
@settings(max_examples=EX, deadline=None)
def test_role_names_round_trip_through_the_grammar(x, y, invented):
    """7.2's names are a GRAMMAR, not a 25-entry table, and a name it has
    never heard of survives whole so a rule can still ask for it.  33.1."""
    role = pc.role_2d(x, y)
    assert pc.split_role(role) == (x, y)
    assert pc.canonical_role(role) == role
    assert pc.split_role(invented) == (invented, "default")
    assert pc.canonical_role(invented) == invented
    assert pc.role_2d(x, "default") == x and pc.role_2d(x, "") == x
    assert len(set(pc.ROLES_2D)) == len(pc.ROLES_2D) == 25
    for alias, role in pc.ROLE_ALIASES.items():
        assert pc.canonical_role(alias) == role and role in pc.ROLES_2D


@given(role=st.sampled_from(sorted(pc.ROLES_2D)),
       extend=st.sampled_from(("x", "y")))
@settings(max_examples=EX, deadline=None)
def test_every_fallback_chain_starts_at_the_cell_and_ends_at_default(role,
                                                                     extend):
    """7.2.2 - the walk terminates at the one role a kit must carry."""
    chain = a2.fallback_chain(role, extend)
    assert chain[0] == role and chain[-1] == "default"
    assert len(chain) == len(set(chain)), "the walk repeats a role"


YKIT1 = pc.Kit("yk1", 1, [pc.Module("default", (3.0, 3.2, 0.3),
                                    roles="default")], 1.8)
YRULES1 = [pc.Rule("default", "first", ["default"], axis="y")]


@given(h=st.floats(0.0, 300.0), mode=modes, count=st.integers(1, 8),
       caps=st.booleans())
@settings(max_examples=EX * 2, deadline=None)
def test_the_y_bands_tile_the_height(h, mode, count, caps):
    """7.1's exact fill on the axis RailClone documents as CLIPPED, plus
    `tile`'s honest half again.  ⚠️ `count` IS BOUNDED AT 1 AND THE BOUND IS A
    DEFECT - the next test.  33.1."""
    kit, rules = (YKIT, YRULES) if caps else (YKIT1, YRULES1)
    style = pc.Style("y", 1, 1, rules=rules,
                     params=pc.Params(fill=mode, count=count))
    rows = a2.plan_rows(h, kit, style)
    assert isinstance(rows, list)
    again = a2.plan_rows(h, kit, style)
    assert [r.as_dict() for r in rows] == [r.as_dict() for r in again]
    assume(rows)
    assert all(r.height > 0.0 for r in rows)
    assert [r.index for r in rows] == list(range(len(rows)))
    for a, b in zip(rows, rows[1:]):
        assert abs(a.y1 - b.y0) <= REL * max(h, 1.0), "band gap"
    assert abs(rows[0].y0) <= REL * max(h, 1.0)
    span = sum(r.height for r in rows)
    if mode == "tile":
        assert span <= h + REL * max(h, 1.0)
    else:
        assert abs(span - h) <= REL * max(h, 1.0)
        assert abs(rows[-1].y1 - h) <= REL * max(h, 1.0)
    if mode == "count" and not caps:
        assert len(rows) == count       # count is the DEFAULT band count


def test_count_zero_leaves_a_hole_between_the_caps():
    """RECORDED DEFECT, 2026-08-26, found by the property above and owned by
    33.2: `fill = count` with `Count = 0` lays the ground floor and the
    cornice with a 1.0 m band of NOTHING between them and no warning.
    Asserted as what the build DOES, so the day it is fixed this goes red and
    is deleted with its finding."""
    style = pc.Style("y", 1, 1, rules=YRULES,
                     params=pc.Params(fill="count", count=0))
    rows = a2.plan_rows(6.0, YKIT, style)
    assert [(r.yclass, round(r.y0, 6), round(r.y1, 6)) for r in rows] == \
        [("start", 0.0, 4.0), ("end", 5.0, 6.0)]
    assert not any(r.warns for r in rows), "it warns now - delete this test"


@given(pts=st.lists(st.tuples(st.floats(-100, 100), st.floats(-5, 5),
                              st.floats(-100, 100)), min_size=3, max_size=8),
       k=st.integers(0, 7), rev=st.booleans())
@settings(max_examples=EX, deadline=None)
def test_the_canonical_footprint_survives_rotation_and_reversal(pts, k, rev):
    """D124 - or 12.7's identity rule is a wish.  One winding (7.3.3's
    counter-clockwise about +Y is a NEGATIVE shoelace in the (x, z) chart)
    and the vertex SET untouched.  33.1."""
    pts = [tuple(float(c) for c in q) for q in pts]
    assume(len(set((round(q[0], 3), round(q[2], 3)) for q in pts)) == len(pts))
    base = a2.canonical_loop(pts)
    assume(abs(a2._signed_area_xz(base)) > 1e-3)
    j = k % len(pts)
    rot = pts[j:] + pts[:j]
    if rev:
        rot = list(reversed(rot))
    assert a2.canonical_loop(rot) == base
    assert a2.canonical_loop(pts + [pts[0]]) == base, "the closing repeat"
    assert sorted(base) == sorted(pts), "the vertex set moved"
    assert a2._signed_area_xz(base) < 0.0, "the winding flipped"


def test_the_kernel_never_imports_hou():
    """The property that keeps this file runnable under plain python."""
    assert "hou" not in sys.modules
