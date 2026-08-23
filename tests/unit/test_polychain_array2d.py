"""polyChain 7 ARRAY2D - the row stack and the cell lattice. No Houdini.

    python tests/unit/test_polychain_array2d.py

Same discipline as `test_polychain_plan.py`: every number here is an INVARIANT
of the solve (what must be true of any correct row stack or any correct
lattice walk), never a value copied off a build. The geometry-side numbers -
which module landed in which cell, how many warnings a kit gap costs, what one
build call costs against a hundred - are in `tests/polychain/run_2d_checks.py`
and its baseline, because those need a builder.

⚠️ THIS FILE ASSERTS THAT `hou` WAS NEVER IMPORTED. `array2d.py` is the
`hou`-free half of phase 2 exactly as `plan.py` is the `hou`-free half of
phase 1, and that property is what lets the whole Y solve be tested in
milliseconds without a licence. It is one line and it has to be here, because
one convenience import in a later cycle would take it away silently.
"""

import math
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "polyfactory", "scripts", "python"))

from polyfactory.polychain import (DEFAULTS, ROLES_2D, ROLE_ALIASES, SLOTS,
                                   WARN_KIT_GAP, WARN_ROLE_FALLBACK, Curve,
                                   Kit, Module, Params, Rule, Style,
                                   canonical_role, role_2d, split_role)
from polyfactory.polychain import array2d as A
from polyfactory.polychain import decompose as D
from polyfactory.polychain import plan as PL

BAY_Y, GROUND_Y, CORNICE_Y = 3.2, 4.0, 1.0


def kit_of(*roles):
    """One module per role, each 3 m wide and named after its role."""
    mods = []
    for r in roles:
        y = {"default_start": GROUND_Y, "corner_start": GROUND_Y,
             "default_end": CORNICE_Y, "corner_end": CORNICE_Y}.get(r, BAY_Y)
        mods.append(Module(r, (3.0, y, 0.3), roles=r))
    return Kit("k", 1, mods)


def _inside_xz(loop, x, z):
    """Even-odd point-in-polygon in the plan, for the winding assertion."""
    inside = False
    n = len(loop)
    for i in range(n):
        (ax, _ay, az), (bx, _by, bz) = loop[i], loop[(i + 1) % n]
        if (az > z) != (bz > z):
            if x < ax + (bx - ax) * (z - az) / (bz - az):
                inside = not inside
    return inside


def y_style(**kw):
    return Style("y", 1, 3, rules=[
        Rule("start", "first", ["default_start"], axis="y"),
        Rule("default", "first", ["default"], axis="y"),
        Rule("end", "first", ["default_end"], axis="y"),
    ], params=Params(**kw))


class TestVocabulary(unittest.TestCase):
    """7.2 / D116 - the 20 RC Slice pieces are a 5 x 4 product table."""

    def test_twenty_five_unique_roles(self):
        self.assertEqual(len(ROLES_2D), 25)
        self.assertEqual(len(set(ROLES_2D)), 25)

    def test_bottom_row_is_the_phase_1_slot_list(self):
        """The compatibility claim, and it is checkable: a phase-1 kit is a
        valid phase-2 kit for the middle rows because the Y-`default` column
        IS the phase-1 vocabulary."""
        self.assertEqual(set(SLOTS),
                         set(r for r in ROLES_2D if "_" not in r))

    def test_rc_slice_twenty_map_bijectively(self):
        """RailClone's own inventory, by name, and the column it is missing.

        The 12 named slice types and the 8 intersections from the RC Slice
        reference. They must land on exactly the 20 roles with
        `y_slot != "corner"` - no leftovers on either side - and what is left
        over on ours must be precisely the Y-corner column RailClone omits.
        """
        rc = ["start", "end", "default", "x_evenly", "y_evenly", "x_corner",
              "top", "bottom", "start_top", "end_top", "start_bottom",
              "end_bottom", "x_corner_top", "x_corner_bottom", "x_evenly_top",
              "x_evenly_bottom", "y_evenly_start", "y_evenly_end",
              "xy_evenly", "y_evenly_corner"]
        got = [canonical_role(n) for n in rc]
        self.assertEqual(len(got), 20)
        self.assertEqual(len(set(got)), 20, "the mapping is not injective")
        for role in got:
            self.assertIn(role, ROLES_2D)
        missing = set(ROLES_2D) - set(got)
        self.assertEqual(missing, set(role_2d(x, "corner") for x in SLOTS))

    def test_split_and_join_round_trip(self):
        for role in ROLES_2D:
            x, y = split_role(role)
            self.assertIn(x, SLOTS)
            self.assertIn(y, SLOTS)
            self.assertEqual(role_2d(x, y), role)

    def test_marker_cells_parse_by_grammar(self):
        self.assertEqual(split_role("marker:7"), ("marker:7", "default"))
        self.assertEqual(split_role("default_marker:2"),
                         ("default", "marker:2"))
        self.assertEqual(canonical_role("marker:7"), "marker:7")
        self.assertEqual(canonical_role("marker:7_default"), "marker:7")

    def test_an_invented_name_survives_whole(self):
        """A role the vocabulary has never heard of is a NAME, not a broken
        role: a rule can still ask for it and the kit can still answer."""
        self.assertEqual(canonical_role("corner_post"), "corner_post")
        self.assertEqual(split_role("corner_post"), ("corner_post", "default"))

    def test_default_default_is_written_default(self):
        self.assertEqual(role_2d("default", "default"), "default")
        self.assertEqual(canonical_role("default_default"), "default")

    def test_every_alias_lands_in_the_vocabulary(self):
        for alias, role in ROLE_ALIASES.items():
            self.assertIn(role, ROLES_2D, alias)


class TestFallbackChain(unittest.TestCase):
    """7.2.2 - the lattice walk, and why Y sheds first."""

    def test_y_sheds_before_x(self):
        self.assertEqual(A.fallback_chain("corner_end"),
                         ["corner_end", "corner", "default_end", "default"])

    def test_extend_y_reverses_steps_two_and_three(self):
        self.assertEqual(A.fallback_chain("corner_end", extend="y"),
                         ["corner_end", "default_end", "corner", "default"])

    def test_a_phase_1_role_is_its_own_chain_head(self):
        self.assertEqual(A.fallback_chain("corner"), ["corner", "default"])
        self.assertEqual(A.fallback_chain("default"), ["default"])

    def test_every_chain_ends_at_default(self):
        for role in ROLES_2D:
            for extend in ("x", "y"):
                self.assertEqual(A.fallback_chain(role, extend)[-1], "default")


class TestRoleClosure(unittest.TestCase):
    """E3 / D118 - the walk, performed once as data at kit read."""

    def test_a_full_kit_records_no_fallback_for_what_it_has(self):
        kit, fb = A.close_roles(kit_of("default", "corner", "default_start",
                                       "corner_start", "default_end",
                                       "corner_end"))
        for role in ("default", "corner", "default_start", "corner_start",
                     "default_end", "corner_end"):
            self.assertNotIn(role, fb)
            self.assertEqual([m.name for m in kit.by_role(role)], [role])

    def test_a_default_only_kit_serves_every_cell_and_says_so(self):
        """"a kit with only `default` builds every cell and warns" - §7.10."""
        kit, fb = A.close_roles(kit_of("default"))
        for role in ROLES_2D:
            self.assertEqual([m.name for m in kit.by_role(role)], ["default"],
                             role)
        self.assertEqual(len(fb), 24)
        self.assertEqual(set(fb.values()), {"default"})

    def test_corner_end_prefers_the_corner_over_the_cornice(self):
        kit, fb = A.close_roles(kit_of("default", "corner", "default_end"))
        self.assertEqual(fb["corner_end"], "corner")
        self.assertEqual([m.name for m in kit.by_role("corner_end")],
                         ["corner"])

    def test_extend_zero_on_the_column_sends_it_to_the_cornice(self):
        """7.2.1's Extend To Side: `pc_extend = 0` means "this column STOPS at
        the cornice", so its fallback keeps Y instead of X. The pair is the
        assertion - the same kit, one integer apart, two different answers."""
        mods = [Module("default", (3.0, BAY_Y, 0.3), roles="default"),
                Module("corner", (0.6, BAY_Y, 0.3), roles="corner", extend=0),
                Module("cornice", (3.0, CORNICE_Y, 0.3), roles="default_end")]
        kit, fb = A.close_roles(Kit("k", 1, mods))
        self.assertEqual(fb["corner_end"], "default_end")
        mods[1] = Module("corner", (0.6, BAY_Y, 0.3), roles="corner", extend=1)
        _kit, fb2 = A.close_roles(Kit("k", 1, mods))
        self.assertEqual(fb2["corner_end"], "corner")

    def test_the_walk_can_run_out_and_says_so_with_an_empty_supplier(self):
        _kit, fb = A.close_roles(kit_of("corner"))
        self.assertEqual(fb["default"], "")
        self.assertEqual(fb["default_start"], "")

    def test_closure_never_edits_the_kit_it_was_given(self):
        src = kit_of("default")
        _kit, _fb = A.close_roles(src)
        self.assertEqual(src.modules[0].roles, ("default",))
        self.assertEqual(src.role_fallbacks, {})

    def test_a_colliding_alias_loses_and_says_so(self):
        """7.2's alias-collision rule, which nothing ran.

        Two modules claim `default_start`, one LITERALLY and one through the
        `bottom` alias. First in payload order wins, the alias's claim is
        dropped, and the drop is announced. Re-pooling them instead - one
        deleted `continue` - left 19 scene cases and every other unit test
        green, so the rule had no assertion behind it at all.
        """
        kit, _fb = A.close_roles(Kit("k", 1, [
            Module("shopfront", (3.0, GROUND_Y, 0.3), roles="default_start"),
            Module("arcade", (3.0, GROUND_Y, 0.3), roles="bottom")]))
        self.assertEqual([m.name for m in kit.by_role("default_start")],
                         ["shopfront"])
        self.assertEqual(len(kit.role_collisions), 1)
        self.assertIn("pc_warn_role_collision", kit.role_collisions[0])

    def test_a_literal_second_claim_stays_a_pool_member(self):
        """...and the control: only an ALIAS loses. Two modules authoring the
        same role literally are a `random`/`pc_weight` pool, which is what
        phase 1's variants are made of, and dropping those would break them."""
        kit, _fb = A.close_roles(Kit("k", 1, [
            Module("bay_a", (3.0, BAY_Y, 0.3), roles="default"),
            Module("bay_b", (3.0, BAY_Y, 0.3), roles="default")]))
        self.assertEqual(sorted(m.name for m in kit.by_role("default")),
                         ["bay_a", "bay_b"])
        self.assertEqual(list(kit.role_collisions), [])

    def test_a_marker_cell_closes_over_all_five_y_classes(self):
        """7.2's marker cells are legal BY GRAMMAR and therefore unbounded, so
        they cannot live in `ROLES_2D` - but `marker:7` still owes its five Y
        classes a closure or `marker:7_start` arrives on the ground row as a
        SILENT stand-in, which is the one thing PC-G5 condition 5 counts at 0.
        Deleting the expansion left the whole suite green."""
        kit, fb = A.close_roles(Kit("k", 1, [
            Module("entrance", (3.0, GROUND_Y, 0.3), roles="marker:7"),
            Module("bay", (3.0, BAY_Y, 0.3), roles="default")]))
        for y in SLOTS:
            role = role_2d("marker:7", y)
            self.assertTrue(role in fb or kit.by_role(role),
                            "marker cell %r never closed" % role)
        self.assertEqual([m.name for m in kit.by_role("marker:7_start")],
                         ["entrance"])

    def test_a_module_name_is_not_a_cell_role(self):
        """`facade.build` hands the style's module NAMES in as `extra_roles`.
        Taking a name for a role wrote `cornice` onto the `bay` module, so
        `by_role("cornice")` returned `bay` and D136's inspectable manifest
        was wrong to read. Nothing in the scene suite could see it."""
        kit, fb = A.close_roles(kit_of("default"),
                                extra_roles=("cornice", "bay", "corner_end"))
        self.assertEqual(list(kit.by_role("cornice")), [])
        self.assertNotIn("cornice", fb)
        self.assertIn("corner_end", fb)

    def test_aliases_are_normalised_before_the_walk(self):
        kit, fb = A.close_roles(Kit("k", 1, [
            Module("ground", (3.0, GROUND_Y, 0.3), roles="bottom")]))
        self.assertEqual([m.name for m in kit.by_role("default_start")],
                         ["ground"])
        self.assertNotIn("default_start", fb)


class TestYSolve(unittest.TestCase):
    """7.1 - the row list IS a phase-1 plan, so it inherits phase-1's fit."""

    def test_four_storeys_over_thirteen_metres(self):
        rows = A.plan_rows(13.0, kit_of("default", "default_start",
                                        "default_end"), y_style())
        self.assertEqual([r.yclass for r in rows],
                         ["start", "default", "default", "default", "end"])
        self.assertEqual([r.index for r in rows], [0, 1, 2, 3, 4])
        self.assertAlmostEqual(rows[0].y0, 0.0, 9)
        self.assertAlmostEqual(rows[-1].y1, 13.0, 9)

    def test_bands_tile_the_height_exactly(self):
        """EXACT FILL ON THE Y AXIS. Every band meets the next to 1e-9 m and
        the stack spans the whole height - the same property `exact_fill_m`
        measures on X, asserted on the axis RailClone documents as clipped."""
        for h in (9.0, 13.0, 20.0, 31.7):
            rows = A.plan_rows(h, kit_of("default", "default_start",
                                         "default_end"), y_style())
            self.assertAlmostEqual(rows[0].y0, 0.0, 9)
            self.assertAlmostEqual(rows[-1].y1, h, 9)
            for a, b in zip(rows, rows[1:]):
                self.assertAlmostEqual(a.y1, b.y0, 9, "band gap at %g" % h)

    def test_row_scale_is_the_band_over_the_nominal_height(self):
        rows = A.plan_rows(13.0, kit_of("default", "default_start",
                                        "default_end"), y_style())
        self.assertAlmostEqual(rows[0].scale, 1.0, 9)       # the ground floor
        self.assertAlmostEqual(rows[-1].scale, 1.0, 9)      # the cornice
        for r in rows[1:-1]:
            self.assertAlmostEqual(r.scale, r.height / BAY_Y, 9)
            self.assertNotAlmostEqual(r.scale, 1.0, 3)

    def test_adaptive_on_Y_never_slices(self):
        """D114 - RailClone's documented wart does not survive, because the Y
        solve is the same solve. Whole storeys, subtly scaled, at every
        height."""
        for h in [7.0 + 0.37 * i for i in range(20)]:
            rows = A.plan_rows(h, kit_of("default", "default_start",
                                         "default_end"), y_style())
            for r in rows:
                self.assertGreater(r.height, 0.0)
            self.assertAlmostEqual(sum(r.height for r in rows), h, 9)

    def test_count_mode_places_exactly_n_rows(self):
        rows = A.plan_rows(20.0, kit_of("default"), Style(
            "y", 1, 1, rules=[Rule("default", "first", ["default"], axis="y")],
            params=Params(fill="count", count=5)))
        self.assertEqual(len(rows), 5)
        self.assertAlmostEqual(sum(r.height for r in rows), 20.0, 9)

    def test_evenly_on_Y_is_a_string_course(self):
        rows = A.plan_rows(24.0, kit_of("default", "evenly"), Style(
            "y", 1, 1, rules=[Rule("default", "first", ["default"], axis="y"),
                              Rule("evenly", "first", ["evenly"], axis="y")],
            params=Params(fill="adaptive", evenly_spacing=8.0)))
        self.assertIn("evenly", [r.yclass for r in rows])

    def test_no_Y_rules_is_one_row_and_no_class(self):
        """The compatibility claim on the other axis: a phase-1 payload is one
        row spanning the whole height with no Y class at all - i.e. a 1D run,
        which is what makes `classify` a no-op and `cell_role` the identity."""
        rows = A.plan_rows(13.0, kit_of("default"), Style("y", 1, 1, rules=[]))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].yclass, "")
        self.assertAlmostEqual(rows[0].height, 13.0, 9)

    def test_the_row_list_is_deterministic(self):
        a = [r.as_dict() for r in A.plan_rows(
            13.0, kit_of("default", "default_start", "default_end"), y_style())]
        b = [r.as_dict() for r in A.plan_rows(
            13.0, kit_of("default", "default_start", "default_end"), y_style())]
        self.assertEqual(a, b)

    def test_a_degenerate_height_yields_a_plan_and_no_exception(self):
        for h in (0.0, -3.0, 1e-12):
            rows = A.plan_rows(h, kit_of("default"), y_style())
            self.assertIsInstance(rows, list)

    def test_curve_ids_carry_the_row(self):
        rows = A.plan_rows(13.0, kit_of("default", "default_start",
                                        "default_end"), y_style(),
                           array_id="B17")
        self.assertEqual([r.curve_id for r in rows],
                         ["B17#0", "B17#1", "B17#2", "B17#3", "B17#4"])


class TestYProfile(unittest.TestCase):
    """7.1's third row mode, and D134's Y `corner`."""

    def test_a_profile_vertex_is_a_corner_row(self):
        prof = A.Curve("p", [(0, 0, 0), (0.0, 7.0, 0), (4.0, 13.0, 0)])
        rows = A.plan_rows(prof, kit_of("default", "default_start",
                                        "default_end"), y_style())
        self.assertIn("corner", [r.yclass for r in rows])

    def test_the_caps_outrank_the_corner(self):
        """7.2.1's Y order: `start`/`end` beat `corner`. A profile that turns
        immediately still has a `start` row at the bottom."""
        prof = A.Curve("p", [(0, 0, 0), (0.0, 4.0, 0), (6.0, 13.0, 0)])
        rows = A.plan_rows(prof, kit_of("default", "default_start",
                                        "default_end"), y_style())
        self.assertEqual(rows[0].yclass, "start")
        self.assertEqual(rows[-1].yclass, "end")
        self.assertIn("corner", [r.yclass for r in rows])

    def test_the_profile_offset_is_read_and_not_yet_applied(self):
        """D128 is P2-8. The offset must be READ now - a number nothing uses
        is still the number the later cycle needs - and it must not move a
        single row's height in the meantime."""
        prof = A.Curve("p", [(0, 0, 0), (3.0, 13.0, 0)])
        rows = A.plan_rows(prof, kit_of("default"), Style(
            "y", 1, 1, rules=[Rule("default", "first", ["default"], axis="y")]))
        self.assertGreater(rows[-1].off1, 0.0)

    def test_y_class_precedence_in_isolation(self):
        self.assertEqual(A.y_class("start", 7.0, [7.0]), "start")
        self.assertEqual(A.y_class("end", 7.0, [7.0]), "end")
        self.assertEqual(A.y_class("evenly", 7.0, [7.0]), "corner")
        self.assertEqual(A.y_class("marker:3", 7.0, [7.0]), "corner")
        self.assertEqual(A.y_class("default", 7.0, [7.0]), "corner")
        self.assertEqual(A.y_class("default", 7.0, [2.0]), "default")


class TestCanonicalFootprint(unittest.TestCase):
    """D124 - ids survive re-authoring, or 12.7's identity rule is a wish."""

    L = [(0, 0, 0), (24, 0, 0), (24, 0, 12), (12, 0, 12), (12, 0, 24),
         (0, 0, 24)]

    def test_rotation_and_reversal_produce_one_answer(self):
        base = A.canonical_loop(self.L)
        for k in range(len(self.L)):
            rot = self.L[k:] + self.L[:k]
            self.assertEqual(A.canonical_loop(rot), base, "rotation %d" % k)
            self.assertEqual(A.canonical_loop(list(reversed(rot))), base,
                             "reversed rotation %d" % k)

    def test_the_winding_is_fixed(self):
        # 7.3.3/D124: "always run counter-clockwise about +Y". The shoelace
        # here is taken in the (x, z) chart, whose right-handed normal is -Y,
        # so counter-clockwise about +Y is a NEGATIVE number in it. The code
        # used to force the opposite sign and nothing measured the
        # consequence, which is the next test (D141).
        self.assertLess(A._signed_area_xz(A.canonical_loop(self.L)), 0.0)
        self.assertLess(
            A._signed_area_xz(A.canonical_loop(list(reversed(self.L)))), 0.0)

    def test_the_across_axis_points_out_of_the_building(self):
        """D141 - THE SIGN, MEASURED AS THE THING IT DECIDES.

        `place._frame` builds `across = cross(tangent, +Y)`, and D20 models a
        bay centred across its local Z with its FRONT on +Z. So the winding is
        correct exactly when a step along `across` from any leg's midpoint
        leaves the footprint - which is what makes a window face the street.
        The sign test above cannot see this; on the old winding every window
        on every building faced inward and every number in the suite was
        green. Point-in-polygon rather than a centroid dot, because on a
        reflex leg of an L the centroid sits ON the leg's own line.
        """
        for pts in (self.L, list(reversed(self.L)), self.L[3:] + self.L[:3]):
            loop = A.canonical_loop(pts)
            n = len(loop)
            for i in range(n):
                a, b = loop[i], loop[(i + 1) % n]
                tx, tz = b[0] - a[0], b[2] - a[2]
                L = math.hypot(tx, tz)
                # cross((tx, 0, tz), (0, 1, 0)) = (-tz, 0, tx)
                ax, az = -tz / L, tx / L
                mx = 0.5 * (a[0] + b[0]) + 0.01 * ax
                mz = 0.5 * (a[2] + b[2]) + 0.01 * az
                self.assertFalse(_inside_xz(loop, mx, mz),
                                 "leg %d of %s faces inward" % (i, pts[0]))
                self.assertTrue(
                    _inside_xz(loop, 0.5 * (a[0] + b[0]) - 0.01 * ax,
                               0.5 * (a[2] + b[2]) - 0.01 * az),
                    "leg %d of %s: the other side is not the interior"
                    % (i, pts[0]))

    def test_the_vertex_set_is_untouched(self):
        got = A.canonical_loop(self.L)
        self.assertEqual(len(got), len(self.L))
        self.assertEqual(sorted(got), sorted(tuple(float(c) for c in p)
                                             for p in self.L))

    def test_a_repeated_closing_vertex_is_dropped(self):
        self.assertEqual(len(A.canonical_loop(self.L + [self.L[0]])), 6)

    def test_an_open_run_is_left_exactly_as_authored(self):
        pts = [(3, 0, 0), (0, 0, 0)]
        self.assertEqual(A.canonical_loop(pts, closed=False),
                         [(3.0, 0.0, 0.0), (0.0, 0.0, 0.0)])

    def test_rows_translate_the_canonical_loop(self):
        rows = A.plan_rows(13.0, kit_of("default", "default_start",
                                        "default_end"), y_style())
        loops = A.row_loops(self.L, rows)
        self.assertEqual(len(loops), len(rows))
        base = A.canonical_loop(self.L)
        for (pts, closed, attrs), row in zip(loops, rows):
            self.assertTrue(closed)
            self.assertEqual([p[1] for p in pts], [row.y0] * len(pts))
            self.assertEqual([(p[0], p[2]) for p in pts],
                             [(b[0], b[2]) for b in base])


class TestClippedArea(unittest.TestCase):
    """7.6 / D137 - enough of the clipped area to fill a facade panel."""

    RECT = [(0, 0, 0), (12, 0, 0), (12, 9, 0), (0, 9, 0)]
    TRI = [(0, 0, 0), (14, 0, 0), (0, 9, 0)]

    def test_a_vertical_rectangle_gives_its_own_extents(self):
        f = A.area_frame(self.RECT)
        self.assertAlmostEqual(f.width, 12.0, 9)
        self.assertAlmostEqual(f.height, 9.0, 9)
        self.assertAlmostEqual(abs(f.ez[2]), 1.0, 9)

    def test_the_frame_round_trips_a_point(self):
        f = A.area_frame(self.RECT)
        for x, y in ((0.0, 0.0), (12.0, 9.0), (3.5, 4.25)):
            self.assertEqual(
                tuple(round(v, 9) for v in f.local(f.world(x, y))),
                (round(x, 9), round(y, 9)))

    def test_expand_grows_the_extents_symmetrically(self):
        f = A.area_frame(self.RECT, expand=0.5)
        self.assertAlmostEqual(f.width, 13.0, 9)
        self.assertAlmostEqual(f.height, 10.0, 9)

    def test_a_rectangle_clips_nothing(self):
        f = A.area_frame(self.RECT)
        rows = A.plan_rows(f.height, kit_of("default"), Style(
            "y", 1, 1, rules=[Rule("default", "first", ["default"], axis="y")]))
        for row in rows:
            self.assertEqual([(round(a, 9), round(b, 9))
                              for a, b in A.row_spans(f, row)],
                             [(0.0, round(f.width, 9))])

    def test_a_taper_narrows_every_row_and_never_leaves_the_line(self):
        f = A.area_frame(self.TRI)
        rows = A.plan_rows(f.height, kit_of("default"), Style(
            "y", 1, 1, rules=[Rule("default", "first", ["default"], axis="y")],
            params=Params(fill="count", count=6)))
        widths = []
        for row in rows:
            spans = A.row_spans(f, row)
            self.assertEqual(len(spans), 1)
            x0, x1 = spans[0]
            self.assertGreaterEqual(x0, -1e-9)
            # `remove` is the INTERSECTION of the band's two scanlines, so the
            # span is inside the boundary at every height it spans - which is
            # the whole of "nothing crosses the line", decided on the plan.
            self.assertLessEqual(x1, 14.0 * (1.0 - row.y1 / 9.0) + 1e-6)
            widths.append(x1 - x0)
        self.assertEqual(widths, sorted(widths, reverse=True))

    def test_preserve_is_wider_than_remove_and_remove_never_wider(self):
        f = A.area_frame(self.TRI)
        rows = A.plan_rows(f.height, kit_of("default"), Style(
            "y", 1, 1, rules=[Rule("default", "first", ["default"], axis="y")],
            params=Params(fill="count", count=6)))
        for row in rows:
            rem = A.row_spans(f, row, "remove")[0]
            pre = A.row_spans(f, row, "preserve")[0]
            self.assertLessEqual(pre[0], rem[0] + 1e-9)
            self.assertGreaterEqual(pre[1], rem[1] - 1e-9)

    def test_area_rows_are_open_spans_in_world_space(self):
        f = A.area_frame(self.RECT)
        rows = A.plan_rows(f.height, kit_of("default"), Style(
            "y", 1, 1, rules=[Rule("default", "first", ["default"], axis="y")],
            params=Params(fill="count", count=3)))
        loops = A.area_rows(f, rows)
        self.assertEqual(len(loops), 3)
        for pts, closed, _a in loops:
            self.assertFalse(closed)
            self.assertEqual(len(pts), 2)
            self.assertAlmostEqual(pts[1][0] - pts[0][0], 12.0, 6)


class TestKernelExtensions(unittest.TestCase):
    """E1/E2/E3 seen from the kernel's side - the three named things only."""

    def test_cell_role_is_the_identity_without_a_row_class(self):
        self.assertEqual(PL.cell_role({"slot": "corner"}), "corner")
        self.assertEqual(PL.cell_role({"slot": "corner", "yclass": ""}),
                         "corner")
        self.assertEqual(PL.cell_role({"slot": "corner", "yclass": "end"}),
                         "corner_end")

    def test_rules_for_without_a_class_is_the_phase_1_call(self):
        s = Style("s", 1, 0, rules=[Rule("default", "first", ["a"]),
                                    Rule("default", "first", ["b"],
                                         yclass="start")])
        self.assertEqual(len(s.rules_for("default")), 2)

    def test_a_scoped_rule_comes_first_and_a_foreign_one_is_excluded(self):
        s = Style("s", 1, 0, rules=[Rule("default", "first", ["any"]),
                                    Rule("default", "first", ["ground"],
                                         yclass="start"),
                                    Rule("default", "first", ["attic"],
                                         yclass="end")])
        got = s.rules_for("default", "start")
        self.assertEqual([r.modules for r in got], [["ground"], ["any"]])
        self.assertEqual([r.modules for r in s.rules_for("default", "evenly")],
                         [["any"]])

    def test_candidates_resolve_the_cell_when_the_rule_names_nothing(self):
        kit, _fb = A.close_roles(kit_of("default", "default_end"))
        rule = Rule("default", "first", [])
        self.assertEqual([m.name for m in PL.candidates(rule, kit, "default_end")],
                         ["default_end"])
        self.assertEqual([m.name for m in PL.candidates(rule, kit)],
                         ["default"])

    def test_classify_stamps_the_cell_and_warns_the_walk(self):
        kit, _fb = A.close_roles(kit_of("default"))
        p = PL.Placement("A#3", 0, "corner", 0, "default", 0.0, 3.0)
        A.classify([p], kit, "end")
        self.assertEqual(p.cell, "corner_end")
        self.assertEqual(p.yclass, "end")
        self.assertIn(WARN_ROLE_FALLBACK, p.warns)

    def test_classify_is_silent_where_the_kit_has_the_cell(self):
        kit, _fb = A.close_roles(kit_of("default", "corner_end"))
        p = PL.Placement("A#3", 0, "corner", 0, "corner_end", 0.0, 3.0)
        A.classify([p], kit, "end")
        self.assertNotIn(WARN_ROLE_FALLBACK, p.warns)

    def test_classify_does_nothing_without_a_row_class(self):
        kit, _fb = A.close_roles(kit_of("default"))
        p = PL.Placement("A", 0, "corner", 0, "default", 0.0, 3.0)
        A.classify([p], kit, "")
        self.assertEqual((p.cell, p.yclass, p.warns), ("", "", ()))

    def test_the_transposed_kit_fits_on_height(self):
        k = kit_of("default", "default_start")
        t = A.transpose_kit(k)
        self.assertAlmostEqual(t.by_name("default").length, BAY_Y, 9)
        self.assertAlmostEqual(t.by_name("default_start").length, GROUND_Y, 9)
        self.assertAlmostEqual(k.by_name("default").length, 3.0, 9)


class TestStyleSplit(unittest.TestCase):
    """D120 - one payload, two axes, and `Style` itself does not change."""

    def test_the_axis_splits_the_rule_list(self):
        s = Style("s", 1, 0, rules=[Rule("default", "first", ["bay"]),
                                    Rule("default", "first", ["storey"],
                                         axis="y")])
        x, y = A.split_style(s)
        self.assertEqual([r.modules for r in x.rules], [["bay"]])
        self.assertEqual([r.modules for r in y.rules], [["storey"]])

    def test_a_phase_1_payload_is_a_valid_X_payload(self):
        s = Style("s", 1, 0, rules=[Rule("default", "first", ["panel"]),
                                    Rule("corner", "first", ["post"])])
        x, y = A.split_style(s)
        self.assertEqual(len(x.rules), 2)
        self.assertEqual(y.rules, [])

    def test_y_params_are_a_second_params_block(self):
        s = Style("s", 1, 0, rules=[], params=Params(fill="tile"))
        x, y = A.split_style(s, Params(fill="count", count=4))
        self.assertEqual(x.params.fill, "tile")
        self.assertEqual((y.params.fill, y.params.count), ("count", 4))

    def test_an_unknown_axis_is_an_X_rule(self):
        self.assertEqual(Rule("default", axis="diagonal").axis, "x")


class TestNoHoudini(unittest.TestCase):

    def test_hou_was_never_imported(self):
        self.assertNotIn("hou", sys.modules)


if __name__ == "__main__":
    unittest.main(verbosity=1)
