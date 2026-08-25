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
    # BENCH question and belongs in `facade_bench.py`, not in an assertion.
    assume(L / d <= 20000.0)
    a = plan.evenly(L, params(evenly_spacing=d, justify="center"))
    assume(a)
    assert abs(a[0] - (L - a[-1])) <= REL * max(L, 1.0)


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


def test_the_kernel_never_imports_hou():
    """The property that keeps this file runnable under plain python."""
    assert "hou" not in sys.modules
