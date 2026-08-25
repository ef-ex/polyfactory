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

from polyfactory.polychain import SLOTS, split_role             # noqa: E402
from polyfactory.polychain import slicer as S                   # noqa: E402


def _slot(name):
    return name in SLOTS or (name.startswith("marker:")
                             and name[7:].isdigit())

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


@given(lo=coords, span=spans, frac=st.floats(0.05, 0.45),
       guides=st.lists(st.floats(0.001, 0.999), max_size=4))
@settings(max_examples=200, deadline=None)
def test_jigsaw_gives_every_fill_cell_the_size_that_was_asked_for(
        lo, span, frac, guides):
    """D131, as a number: with the jigsaw rule on, every cell that is not a
    run cap is EXACTLY THE BAY THE ARTIST TYPED, to 1e-9 m at metre scale.

    ⚠️ This asserted `jigsaw_report(cells)` with no `want`, which is the
    SPREAD of the fill extents - and `axis_bands` sets every fill band to
    `a + w` by construction, so that number is structurally zero and proved
    nothing. `want` ties it to an input instead. The bay stays under half the
    chunk so the auto layout never reaches its own "no middle band" fallback,
    which is a different contract with its own test below.
    """
    size = span * frac
    g = [("x", lo + f * span, "") for f in guides]
    cells, warns = S.plan((lo, lo + span, lo, lo + span), size, size, g)
    rep = S.jigsaw_report(cells, want=(size, size))
    tol = 1e-9 * max(1.0, abs(lo) + span)
    assert not any("no middle band" in w for w in warns), warns
    assert rep["x"] <= tol and rep["y"] <= tol, (rep, size, guides)


@given(lo=coords, span=spans, size=sizes,
       cuts=st.lists(st.floats(0.01, 0.99), min_size=1, max_size=3),
       nudge=st.floats(0.0, 1e-9))
@settings(max_examples=200, deadline=None)
def test_two_guides_in_one_place_are_one_cut(lo, span, size, cuts, nudge):
    """Duplicated guides must change NOTHING about the layout.

    Undeduped they made a zero-width band that the jigsaw then grew to a full
    cell: a byte-identical duplicate module shipped into the same
    `pc_variant` group - doubling that geometry's weight in every random pick
    - and an `end` cap holding the default bay's frame. The measured pair was
    5.0 and 5.0000000001, so `set()` would not have caught it either.
    """
    g = [("x", lo + f * span, "") for f in cuts]
    twice = g + [(a, c + nudge * span, n) for a, c, n in g]
    once, _w = S.plan((lo, lo + span, lo, lo + span), size, size, g)
    dup, warns = S.plan((lo, lo + span, lo, lo + span), size, size, twice)
    assert [(c.name, c.x0, c.x1) for c in dup] == \
           [(c.name, c.x0, c.x1) for c in once], (cuts, nudge)
    assert any("same cut" in w for w in warns), warns
    # and the merged cut KEEPS THE CLASS, whichever of the pair carried it -
    # dropping that carry-over survived the suite (mutmut #90).
    named, _w = S.plan((0.0, 10.0, 0.0, 4.0), 0.0, 0.0,
                       [("x", 5.0, ""), ("x", 5.0 + 1e-10, "corner")],
                       ycaps=False)
    assert [c.role for c in named] == ["start", "corner"], \
        [c.role for c in named]


@given(lo=coords, span=spans)
@settings(max_examples=100, deadline=None)
def test_the_default_layout_is_three_equal_bands(lo, span):
    """D267 - nothing set turns any chunk into start | default | end, which
    is what makes the HDA usable with only a wire."""
    bands = S.axis_bands(lo, lo + span, 0.0, (), True)
    assert [b.cls for b in bands] == ["start", "default", "end"]
    for b in bands:
        assert abs(b.size - span / 3.0) < 1e-6 * max(1.0, abs(span))
    # WITH THE CAPS OFF the whole chunk is one repeating piece - which is what
    # a fence or a wall run wants, and what `Cut Side Pieces` off means.
    # Halving that divisor survived the suite (mutmut #105): the one band
    # would have been half the chunk with nothing said.
    bands = S.axis_bands(lo, lo + span, 0.0, (), False)
    assert len(bands) == 1 and bands[0].cls == "default"
    assert abs(bands[0].size - span) < 1e-6 * max(1.0, abs(span)), bands


# ⚠️ `SLOTS + ("",)` ALONE CANNOT REACH THE BUG THIS TEST EXISTS FOR. `pc_slot`
# is a string an artist types, and it went straight into `role_2d`: an X guide
# named `default_end` composed to the SAME role as (x `default`, y `end`), so
# two structurally different cells were merged into one D269 variant group,
# and `default_end_start` parsed under no grammar at all. Invented names are
# generated here, and a class outside the vocabulary must be refused.
classes = st.one_of(st.sampled_from(SLOTS + ("", "marker:7")),
                    st.sampled_from(("default_end", "shopfront", "corner_x",
                                     "fenêtre", "店面", "_")))


@given(lo=coords, span=spans, size=sizes,
       gx=st.lists(st.tuples(st.floats(0.001, 0.999), classes), max_size=3),
       gy=st.lists(st.tuples(st.floats(0.001, 0.999), classes), max_size=3))
@settings(max_examples=300, deadline=None)
def test_every_cell_is_a_72_role_with_a_unique_name(lo, span, size, gx, gy):
    """The vocabulary claim: slicing invents no role. D269's variants are
    NAMES, and two modules may share a role only if they share a variant."""
    guides = [("x", lo + f * span, c) for f, c in gx] + \
             [("y", lo + f * span, c) for f, c in gy]
    cells, _w = S.plan((lo, lo + span, lo, lo + span), size, size, guides)
    names, roles = set(), {}
    for c in cells:
        # THE GRAMMAR, not the 25-role table: `marker:<n>` is a slot on either
        # axis by construction and is deliberately not enumerable. Anything
        # else the artist typed must have been refused before it got here.
        x, y = split_role(c.role)
        assert _slot(x) and _slot(y), c.role
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
    # ⚠️ AND IT MUST NOT TAKE THE REST WITH IT. `continue` -> `break` in that
    # filter survived the whole suite (mutmut #71) because no case ever put a
    # stray guide BEFORE a real one - one plane an artist left outside the
    # chunk would then have voided every guide after it, silently.
    mid = lo + 0.5 * span
    bands = S.axis_bands(lo, lo + span, 0.0,
                         [(lo + span + off, ""), (mid, "")], True, True, [])
    assert len(bands) == 2 and bands[0].b == mid, [(b.a, b.b) for b in bands]


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
    # ⚠️ AND THE Y AXIS, BY EXTENT. Nothing asserted that a Y guide cuts at
    # all: routing `gy` to a list that is always empty survived the WHOLE
    # suite (mutmut #164), because the auto layout still emits three rows
    # with the same class names in the same order. Found by the mutmut lane
    # `slicer.py` had never been in.
    cells, warns = S.plan((0.0, 6.0, 0.0, 9.0), 2.0, 3.0,
                          [("y", 3.0, "corner")], ycaps=False)
    rows = sorted(set((c.y0, c.y1) for c in cells))
    assert rows == [(0.0, 3.0), (3.0, 6.0)], rows
    assert [c.role for c in cells if c.y0 == 3.0] == \
           ["start_corner", "default_corner", "end_corner"]


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
