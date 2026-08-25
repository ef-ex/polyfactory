"""THE BUDGET: polyChain's tests may not outweigh polyChain.

    python -m pytest tests/unit/test_polychain_budget.py -q       # ~0.02 s

v2 principle 5, and the one rule in the whole regime that is a LIMIT rather
than a technique: **test code <= production code, enforced by a check in the
repo, not by intention**.  v1 reached 25 137 lines of tests around a tool that
had never been measured; every audit added checks and nothing was ever
deleted, and the machinery became the main cost and twice the main defect.

Adding a test to a full budget means deleting one.  That is the point: it
forces the differential oracle and the generated inputs to REPLACE the
enumerated cases they subsume, instead of sitting next to them.

⚠️ THIS CHECK IS RED ON THE COMMIT THAT INTRODUCED IT, AND THAT IS THE POINT.
The v2 pieces landed before the v1 deletions (deliberately - the replacements
have to be proven before anything is removed), so the debt is real and this is
what states its size.  It is not a "known failure" to be tolerated: it is the
gate the consolidation cycle has to close.

WHAT IT CANNOT SEE: whether a line is any good.  A 500-line file of decorative
checks and a 500-line file of real ones weigh the same here.  Weight is the
only thing a budget can measure; the mutation registry is what measures worth.
"""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))

# The tool, MEASURED rather than remembered.  The retrospective says "a
# ~6 000-line tool"; the three things that actually ship are 14 643 lines, and
# a budget written against the remembered number would have been wrong by 2.4x
# in the direction that matters.
PRODUCTION = (
    ("polyfactory/scripts/python/polyfactory/polychain", (".py",)),
    ("polyfactory/vex/polychain", (".vfl", ".h")),
    ("devScripts/create_pf_polychain_hda.py", None),
)

# Everything that exists only to test polyChain.  Images and JSON baselines
# are not code and are not counted; if a baseline ever grows past the tool it
# is a different problem with a different fix.
TESTS = (
    ("tests/polychain", (".py",)),
    ("tests/unit/test_polychain.py", None),
    ("tests/unit/test_polychain_plan.py", None),
    ("tests/unit/test_polychain_corner.py", None),
    ("tests/unit/test_polychain_array2d.py", None),
    ("tests/unit/test_polychain_properties.py", None),
    ("tests/unit/test_polychain_budget.py", None),
)


def count(spec, root=REPO):
    """-> {repo-relative path: line count} for one (path, extensions) spec."""
    out = {}
    path, exts = spec
    full = os.path.join(root, path.replace("/", os.sep))
    if os.path.isfile(full):
        files = [full]
    elif os.path.isdir(full):
        files = [os.path.join(dp, f)
                 for dp, _dn, fn in os.walk(full) for f in fn
                 if exts and f.endswith(exts) and "__pycache__" not in dp]
    else:
        raise AssertionError("%s does not exist - the budget is measuring "
                             "nothing" % path)
    for f in sorted(files):
        with open(f, "rb") as fh:
            out[os.path.relpath(f, root).replace(os.sep, "/")] = \
                fh.read().count(b"\n") + 1
    return out


def totals(specs, root=REPO):
    merged = {}
    for spec in specs:
        merged.update(count(spec, root))
    return merged


def test_the_budget_measures_something():
    """The guard on the guard: an empty side would make the budget pass by
    measuring nothing, which is how a check becomes decoration."""
    prod, tests = totals(PRODUCTION), totals(TESTS)
    assert len(prod) >= 30, "only %d production files found" % len(prod)
    assert len(tests) >= 10, "only %d test files found" % len(tests)
    assert min(prod.values()) > 0 and min(tests.values()) > 0


def test_the_budget_can_fail(tmp_path):
    """The mutation, run as a test rather than by hand: the same counter, on a
    tree built to be over budget and a tree built to be under it.  Without
    this the assertion below is a claim about one repo state and nothing
    else."""
    (tmp_path / "prod.py").write_text("x = 1\n" * 10)
    (tmp_path / "test_big.py").write_text("y = 1\n" * 25)
    over = totals((("test_big.py", None),), str(tmp_path))
    under = totals((("prod.py", None),), str(tmp_path))
    assert sum(over.values()) > sum(under.values()), "the counter is inert"
    assert sum(under.values()) <= sum(over.values())


def test_tests_do_not_outweigh_the_tool():
    prod, tests = totals(PRODUCTION), totals(TESTS)
    p, t = sum(prod.values()), sum(tests.values())
    if t > p:
        worst = sorted(tests.items(), key=lambda kv: -kv[1])[:8]
        pytest.fail(
            "OVER BUDGET by %d lines: %d lines of tests guard %d lines of "
            "tool (%.2fx).\n"
            "Delete %d lines before adding any more. The heaviest test "
            "files:\n%s\n"
            "The v2 replacements are landed and proven: `diff.compare` "
            "subsumes the per-attribute assertions, `gen_cases` subsumes the "
            "enumerated case grids, and `test_polychain_properties` subsumes "
            "the hand-written parameter grids in test_polychain_plan.py."
            % (t - p, t, p, float(t) / p, t - p,
               "\n".join("    %6d  %s" % (n, f) for f, n in worst)))
