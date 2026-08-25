"""7.7's decision half - `polychain/slicer.py`, under plain python.

    python -m pytest tests/unit/test_polychain_slice.py -q

Generated inputs (v2 principle 2): a band layout is arithmetic on four
numbers and a guide list, so Hypothesis attacks it directly instead of three
hand fixtures agreeing with the code that wrote them. The properties are the
tool's own claims - D131's jigsaw, D267's auto layout, D269's variants - not
restatements of the implementation.

WHAT THIS CANNOT SEE: any geometry. Whether a cell actually contains what the
plan says is `run_slice_checks.py`, which is the only place polygons exist.
"""

import os
import sys

from hypothesis import given, settings
from hypothesis import strategies as st

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "polyfactory", "scripts", "python"))

from polyfactory.polychain import ROLES_2D, SLOTS, split_role   # noqa: E402
from polyfactory.polychain import slicer as S                   # noqa: E402

coords = st.floats(-500.0, 500.0, allow_nan=False, allow_infinity=False)
spans = st.floats(0.01, 200.0, allow_nan=False, allow_infinity=False)
sizes = st.floats(0.0, 50.0, allow_nan=False, allow_infinity=False)


@given(lo=coords, span=spans, size=sizes, caps=st.booleans())
@settings(max_examples=200, deadline=None)
def test_bands_tile_the_span_with_no_gap(lo, span, size, caps):
    """Contiguity is the property a cut PLANE has: band i ends where band
    i+1 begins, whatever the sizes are."""
    bands = S.axis_bands(lo, lo + span, size, (), caps, jigsaw=False)
    assert bands
    assert bands[0].a == lo and abs(bands[-1].b - (lo + span)) < 1e-9
    for i in range(len(bands) - 1):
        assert bands[i].b == bands[i + 1].a


@given(lo=coords, span=spans, size=sizes,
       guides=st.lists(st.floats(0.001, 0.999), max_size=4))
@settings(max_examples=200, deadline=None)
def test_jigsaw_gives_every_fill_cell_one_size(lo, span, size, guides):
    """D131, as a number: with the jigsaw rule on, every cell that is not a
    run cap is the same size on both axes, to 1e-9 m."""
    g = [("x", lo + f * span, "") for f in guides]
    cells, _w = S.plan((lo, lo + span, lo, lo + span), size, size, g)
    rep = S.jigsaw_report(cells)
    assert rep["x"] < 1e-9 and rep["y"] < 1e-9, (rep, size, guides)


@given(lo=coords, span=spans)
@settings(max_examples=100, deadline=None)
def test_the_default_layout_is_three_equal_bands(lo, span):
    """D267 - nothing set turns any chunk into start | default | end, which
    is what makes the HDA usable with only a wire."""
    bands = S.axis_bands(lo, lo + span, 0.0, (), True)
    assert [b.cls for b in bands] == ["start", "default", "end"]
    for b in bands:
        assert abs(b.size - span / 3.0) < 1e-6 * max(1.0, abs(span))


@given(lo=coords, span=spans, size=sizes,
       gx=st.lists(st.tuples(st.floats(0.001, 0.999),
                             st.sampled_from(SLOTS + ("",))), max_size=3),
       gy=st.lists(st.tuples(st.floats(0.001, 0.999),
                             st.sampled_from(SLOTS)), max_size=3))
@settings(max_examples=200, deadline=None)
def test_every_cell_is_a_72_role_with_a_unique_name(lo, span, size, gx, gy):
    """The vocabulary claim: slicing invents no role. D269's variants are
    NAMES, and two modules may share a role only if they share a variant."""
    guides = [("x", lo + f * span, c) for f, c in gx] + \
             [("y", lo + f * span, c) for f, c in gy]
    cells, _w = S.plan((lo, lo + span, lo, lo + span), size, size, guides)
    names, roles = set(), {}
    for c in cells:
        assert c.role in ROLES_2D, c.role
        assert split_role(c.role)[0] in SLOTS
        assert c.name not in names, c.name
        names.add(c.name)
        roles.setdefault(c.role, []).append(c)
    for role, group in roles.items():
        if len(group) > 1:
            assert all(c.variant == role for c in group)


@given(lo=coords, span=spans, off=st.floats(0.01, 100.0))
@settings(max_examples=100, deadline=None)
def test_a_guide_that_misses_the_chunk_is_ignored_and_says_so(lo, span, off):
    """Reachability, stated: a plane outside the bounding box cuts nothing,
    and a silently dropped guide is how an artist loses an afternoon."""
    warns = []
    bands = S.axis_bands(lo, lo + span, 0.0, [(lo + span + off, "")], True,
                         True, warns)
    assert len(bands) == 3
    assert any("outside the chunk" in w for w in warns), warns


def test_a_guide_names_the_band_that_starts_at_it():
    """The corner cell an artist actually wants, and the intersection cells
    that come with it for free."""
    cells, warns = S.plan((0.0, 6.0, 0.0, 9.0), 2.0, 3.0,
                          [("x", 2.0, "corner"), ("x", 4.0, "")])
    assert not warns, warns
    got = sorted(c.role for c in cells)
    assert got == sorted(["start", "corner", "end",
                          "start_start", "corner_start", "end_start",
                          "start_end", "corner_end", "end_end"]), got
    corner = [c for c in cells if c.role == "corner"][0]
    assert (corner.x0, corner.x1) == (2.0, 4.0)


def test_a_cap_is_free_the_first_bay_sets_the_size_and_a_repeat_is_a_variant():
    """Three decisions in one layout, because they only exist together.

    D268: a run cap keeps the width the artist's chunk gives it, and every
    other band is forced to the default cell size. D267: with guides and no
    Bay Width, the FIRST non-cap band is what a bay is. D269: the second band
    of the same class is a variant, not a collision.
    """
    bands = S.axis_bands(0.0, 10.0, 0.0, [(2.0, ""), (5.0, ""), (9.0, "")],
                         True)
    assert [(b.cls, b.a, b.b) for b in bands] == [
        ("start", 0.0, 2.0), ("default", 2.0, 5.0),
        ("default", 5.0, 8.0), ("end", 9.0, 10.0)]
    cells, _w = S.plan((0.0, 10.0, 0.0, 4.0), 0.0, 0.0,
                       [("x", 2.0, ""), ("x", 5.0, ""), ("x", 9.0, "")],
                       ycaps=False)
    names = [(c.name, c.role, c.variant) for c in cells]
    assert ("default", "default", "default") in names
    assert ("default_2", "default", "default") in names
    assert ("start", "start", "") in names


def test_guides_own_the_layout_once_there_is_one():
    """The rule that keeps the tool predictable, asserted rather than left in
    a help string: guides ARE the cuts. One guide is two bands, and the auto
    layout does not quietly add caps beside them."""
    bands = S.axis_bands(0.0, 6.0, 2.0, [(2.0, "")], True)
    assert [(b.cls, b.a, b.b) for b in bands] == [("start", 0.0, 2.0),
                                                  ("end", 2.0, 6.0)]


def test_a_bay_too_wide_for_the_chunk_falls_back_and_warns():
    """The degenerate the auto layout can be handed: two caps that would
    overlap. Falling back silently is what makes a tool untrustworthy."""
    warns = []
    bands = S.axis_bands(0.0, 3.0, 1.6, (), True, True, warns)
    # ⚠️ THE EXTENTS, NOT THE CLASS NAMES. Asserting the three labels left
    # this check green under a mutation that deleted the fallback entirely:
    # the bands are still called start / default / end when they are in the
    # wrong places and the middle one runs off the end of the chunk.
    assert [(b.cls, b.a, b.b) for b in bands] == [("start", 0.0, 1.0),
                                                  ("default", 1.0, 2.0),
                                                  ("end", 2.0, 3.0)]
    assert any("no middle band" in w for w in warns), warns
