"""Runnable check for street graph construction.  No Houdini needed.

    python polyfactory/scripts/python/polyfactory/citygen/test_graph.py
"""

import os
import sys
import unittest

# tests/unit -> repo root -> the polyfactory python package
REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "polyfactory", "scripts",
                                "python", "polyfactory"))

from citygen import graph  # noqa: E402


def line(a, b, steps=1):
    """Sampled straight line from a to b, so welding sees interior points."""
    return [tuple(a[i] + (b[i] - a[i]) * s / steps for i in range(3))
            for s in range(steps + 1)]


class TestWeld(unittest.TestCase):

    def test_coincident_endpoints_become_one_node(self):
        nodes, seqs = graph.weld([line((0, 0, 0), (10, 0, 0)),
                                  line((10, 0, 0), (10, 0, 10))], tol=0.5)
        self.assertEqual(len(nodes), 3)
        self.assertEqual(seqs[0][-1], seqs[1][0])

    def test_near_coincident_within_tolerance_welds(self):
        nodes, _ = graph.weld([line((0, 0, 0), (10, 0, 0)),
                               line((10.3, 0, 0), (10, 0, 10))], tol=0.5)
        self.assertEqual(len(nodes), 3)

    def test_outside_tolerance_does_not_weld(self):
        nodes, _ = graph.weld([line((0, 0, 0), (10, 0, 0)),
                               line((11.0, 0, 0), (10, 0, 10))], tol=0.5)
        self.assertEqual(len(nodes), 4)

    def test_points_straddling_a_bucket_boundary_still_weld(self):
        """The classic spatial-hash bug: neighbours must be searched too."""
        tol = 0.5
        a = (1.0 - 1e-6, 0.0, 0.0)     # just under a bucket edge
        b = (1.0 + 1e-6, 0.0, 0.0)     # just over it
        nodes, _ = graph.weld([[a, (5, 0, 0)], [b, (5, 0, 5)]], tol=tol)
        self.assertEqual(len(nodes), 3)

    def test_zero_tolerance_is_rejected(self):
        with self.assertRaises(ValueError):
            graph.weld([line((0, 0, 0), (1, 0, 0))], tol=0.0)

    def test_repeated_points_are_collapsed(self):
        nodes, seqs = graph.weld([[(0, 0, 0), (0, 0, 0), (5, 0, 0)]], tol=0.1)
        self.assertEqual(seqs[0], [0, 1])


class TestSplit(unittest.TestCase):

    def _cross(self):
        # a horizontal street sampled through the crossing point, plus a
        # vertical one that shares that middle node
        h = [(0, 0, 0), (10, 0, 0), (20, 0, 0)]
        v = [(10, 0, -10), (10, 0, 0), (10, 0, 10)]
        return graph.weld([h, v], tol=0.1)

    def test_crossing_node_has_degree_four(self):
        nodes, seqs = self._cross()
        deg = graph.segment_degree(seqs, len(nodes))
        self.assertIn(4, deg)

    def test_two_crossing_streets_become_four_edges(self):
        nodes, seqs = self._cross()
        deg = graph.segment_degree(seqs, len(nodes))
        edges = graph.split_at_junctions(seqs, deg)
        self.assertEqual(len(edges), 4)

    def test_edge_interiors_contain_no_junctions(self):
        nodes, seqs = self._cross()
        deg = graph.segment_degree(seqs, len(nodes))
        edges = graph.split_at_junctions(seqs, deg)
        for e in edges:
            for interior in e[1:-1]:
                self.assertEqual(deg[interior], 2)

    def test_plain_polyline_is_not_split(self):
        nodes, seqs = graph.weld([line((0, 0, 0), (30, 0, 0), steps=6)], tol=0.1)
        deg = graph.segment_degree(seqs, len(nodes))
        self.assertEqual(len(graph.split_at_junctions(seqs, deg)), 1)


class TestPrune(unittest.TestCase):

    def test_short_dead_end_stub_is_removed(self):
        """An overshoot past a junction leaves a short tail. It must go.

        Note the crossing point (50,0,0) is present in BOTH curves: weld does
        not compute intersections, so upstream must have split them already.
        """
        nodes, seqs = graph.weld([
            line((0, 0, 0), (100, 0, 0), steps=10),
            [(50, 0, -50), (50, 0, -25), (50, 0, 0), (50, 0, 3)],  # overshoots 3m
        ], tol=0.5)
        deg = graph.segment_degree(seqs, len(nodes))
        edges = graph.split_at_junctions(seqs, deg)
        pruned = graph.prune_stubs(nodes, edges, min_len=8.0)
        self.assertEqual(len(edges) - len(pruned), 1)

    def test_long_dead_end_is_kept(self):
        """A cul-de-sac is legitimate; only SHORT dead ends are noise."""
        nodes, seqs = graph.weld([
            line((0, 0, 0), (100, 0, 0), steps=10),
            line((50, 0, -50), (50, 0, 0), steps=5),
        ], tol=0.5)
        deg = graph.segment_degree(seqs, len(nodes))
        edges = graph.split_at_junctions(seqs, deg)
        self.assertEqual(len(graph.prune_stubs(nodes, edges, 8.0)), len(edges))

    def test_pruning_cascades(self):
        """Removing one stub can expose another behind it."""
        nodes, seqs = graph.weld([
            line((0, 0, 0), (100, 0, 0), steps=10),
            [(50, 0, 0), (50, 0, 2)],
            [(50, 0, 2), (52, 0, 3)],
        ], tol=0.4)
        deg = graph.segment_degree(seqs, len(nodes))
        edges = graph.split_at_junctions(seqs, deg)
        pruned = graph.prune_stubs(nodes, edges, min_len=8.0)
        self.assertEqual(len(pruned), 2)     # only the two halves of the main street

    def test_dedupe_keeps_the_shorter_of_two_parallel_edges(self):
        nodes = [(0, 0, 0), (10, 0, 0)]
        straight = [0, 1]
        nodes.append((5, 0, 4))
        bowed = [0, 2, 1]
        kept = graph.dedupe_edges(nodes, [bowed, straight])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0], straight)


class TestValidate(unittest.TestCase):

    def test_clean_graph_reports_no_blocking_issues(self):
        res = graph.build([line((0, 0, 0), (100, 0, 0), steps=10),
                           line((50, 0, -50), (50, 0, 50), steps=10)], weld_tol=0.5)
        self.assertEqual(res["stats"]["block"], 0)

    def test_duplicate_edges_are_reported_when_dedupe_is_off(self):
        nodes = [(0, 0, 0), (10, 0, 0)]
        issues = graph.validate(nodes, [[0, 1], [0, 1]], min_len=1.0)
        self.assertTrue(any(i["rule"] == "duplicate_edge" for i in issues))

    def test_zero_length_edge_is_blocking(self):
        issues = graph.validate([(0, 0, 0), (0, 0, 0)], [[0, 1]], min_len=1.0)
        self.assertTrue(any(i["rule"] == "zero_length_edge"
                            and i["severity"] == "block" for i in issues))

    def test_isolated_nodes_are_reported(self):
        issues = graph.validate([(0, 0, 0), (10, 0, 0), (99, 0, 99)],
                                [[0, 1]], min_len=1.0)
        self.assertTrue(any(i["rule"] == "isolated_node" for i in issues))

    def test_validate_never_raises(self):
        graph.validate([], [], min_len=1.0)
        graph.validate([(0, 0, 0)], [[0]], min_len=1.0)


class TestBuildEndToEnd(unittest.TestCase):

    def test_grid_of_streets_closes_faces(self):
        """3x3 crossing streets, each overshooting the outer ones.

        Every street is sampled ON the crossings, standing in for what
        intersectionstitch produces upstream.  Expect 9 crossings of degree 4,
        12 dead ends, and 4 closed interior faces worth of edges: each of the
        6 streets is cut at 3 crossings into 4 edges = 24.  If this is wrong,
        no block can ever be extracted downstream.
        """
        cuts = (0, 50, 100)
        polys = []
        for z in cuts:
            polys.append([(-10, 0, z)] + [(x, 0, z) for x in cuts] + [(110, 0, z)])
        for x in cuts:
            polys.append([(x, 0, -10)] + [(x, 0, z) for z in cuts] + [(x, 0, 110)])

        res = graph.build(polys, weld_tol=0.5, min_len=1.0)

        self.assertEqual(len(res["edges"]), 24)
        self.assertEqual(res["stats"]["block"], 0)
        deg = res["degree"]
        self.assertEqual(sum(1 for d in deg.values() if d == 4), 9)   # crossings
        self.assertEqual(sum(1 for d in deg.values() if d == 1), 12)  # overshoot ends
        # every edge endpoint is flagged as a topological node, interiors are not
        for e in res["edges"]:
            self.assertEqual(res["is_node"][e[0]], 1)
            self.assertEqual(res["is_node"][e[-1]], 1)

    def test_weld_does_not_invent_intersections(self):
        """Guards the documented precondition: two streets that cross without
        sharing a point must stay unconnected."""
        res = graph.build([[(0, 0, 0), (100, 0, 0)],
                           [(50, 0, -50), (50, 0, 50)]],
                          weld_tol=0.5, min_len=1.0)
        self.assertEqual(len(res["edges"]), 2)
        self.assertEqual(max(res["degree"].values()), 1)

    def test_junction_flags_match_edge_endpoints(self):
        res = graph.build([[(0, 0, 0), (50, 0, 0), (100, 0, 0)],
                           [(50, 0, 0), (50, 0, 50)]], weld_tol=0.5, min_len=1.0)
        flagged = {i for i, v in enumerate(res["is_node"]) if v}
        self.assertEqual(flagged, set(res["junctions"]))

    def test_isolated_nodes_are_dropped_and_reindexed(self):
        res = graph.build([line((0, 0, 0), (100, 0, 0), steps=10)],
                          weld_tol=0.5, min_len=1.0)
        for e in res["edges"]:
            for n in e:
                self.assertLess(n, len(res["points"]))

    def test_stats_are_self_consistent(self):
        res = graph.build([[(0, 0, 0), (50, 0, 0), (100, 0, 0)],
                           [(50, 0, -50), (50, 0, 0), (50, 0, 50)]], weld_tol=0.5)
        self.assertEqual(res["stats"]["edges_after_prune"], len(res["edges"]))
        self.assertEqual(res["stats"]["points"], len(res["points"]))
        self.assertEqual(res["stats"]["junctions"], len(res["junctions"]))
        self.assertEqual(len(res["is_node"]), len(res["points"]))

    def test_empty_input_is_survivable(self):
        res = graph.build([], weld_tol=0.5)
        self.assertEqual(res["edges"], [])
        self.assertEqual(res["points"], [])
        self.assertEqual(res["junctions"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
