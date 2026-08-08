"""CityGen - street graph construction.

Design: ideas/citygen_streets.md section S3.

This is the stage whose absence broke every previous attempt.  Tracing curves
through a field gives you a pile of curves; a city is defined by the *closed
faces of a planar graph*, and independent curves never close a face.  So this
module turns curves into topology:

    weld  ->  split at junctions  ->  prune  ->  validate

Representation (citygen_streets.md S3):
  * the POINT table holds every point, shape points included
  * a JUNCTION is a point whose incident-segment count is not 2 - a crossing,
    a branch, or a dead end.  This is the schema's `is_node` flag
  * an edge is a polyline whose FIRST and LAST points are junctions; interior
    points carry shape only, so a street can be reshaped without any
    topological change
  * points are shared, so degree falls out of incidence

PRECONDITION - crossings must already be split.  `weld` merges coincident and
near-coincident points; it does NOT compute segment intersections.  Two streets
that cross without sharing a point stay unconnected, and no amount of welding
will join them.  Upstream must insert the crossing points first - in Houdini
that is the `intersectionstitch` SOP, run once per layer.

Planarity is per LAYER, never global - two edges crossing on different layers
are an overpass and must not share a node.  Callers partition by layer and
call in here once per layer.

Everything here is pure Python on plain tuples so it can be tested outside
Houdini - see test_graph.py.
"""

from collections import Counter, defaultdict

# defaults, in metres.  art direction rule: these are defaults, not constants.
DEFAULT_WELD_TOL = 0.5
DEFAULT_MIN_EDGE_LEN = 8.0
DEFAULT_MIN_ANGLE_DEG = 12.0


# ---------------------------------------------------------------------------
# small vector helpers
# ---------------------------------------------------------------------------

def _dist2(a, b):
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    dz = a[2] - b[2]
    return dx * dx + dy * dy + dz * dz


def _dist(a, b):
    return _dist2(a, b) ** 0.5


def edge_length(nodes, edge):
    return sum(_dist(nodes[a], nodes[b]) for a, b in zip(edge, edge[1:]))


# ---------------------------------------------------------------------------
# 1. weld - coincident and near-coincident points become one node
# ---------------------------------------------------------------------------

def weld(polylines, tol=DEFAULT_WELD_TOL):
    """Merge points within `tol` into shared nodes.

    Returns (nodes, seqs) where nodes is a list of positions and seqs is the
    input polylines rewritten as lists of node indices.

    Neighbouring buckets are searched as well as the home bucket, so two points
    that straddle a bucket boundary still weld - the classic spatial-hash bug.
    """
    if tol <= 0.0:
        raise ValueError("weld tolerance must be positive, got %r" % (tol,))

    nodes = []
    buckets = defaultdict(list)
    tol2 = tol * tol

    def node_for(p):
        bx, by, bz = int(p[0] // tol), int(p[1] // tol), int(p[2] // tol)
        best, best_d2 = -1, tol2
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for idx in buckets.get((bx + dx, by + dy, bz + dz), ()):
                        d2 = _dist2(p, nodes[idx])
                        if d2 <= best_d2:
                            best, best_d2 = idx, d2
        if best >= 0:
            return best
        nodes.append(tuple(p))
        buckets[(bx, by, bz)].append(len(nodes) - 1)
        return len(nodes) - 1

    seqs = []
    for poly in polylines:
        seq = []
        for p in poly:
            i = node_for(p)
            if not seq or seq[-1] != i:      # collapse repeats created by welding
                seq.append(i)
        if len(seq) >= 2:
            seqs.append(seq)
    return nodes, seqs


# ---------------------------------------------------------------------------
# 2. split at junctions - one prim per graph edge
# ---------------------------------------------------------------------------

def segment_degree(seqs, node_count):
    """Incident segment count per node.  Interior-of-one-polyline == 2."""
    deg = [0] * node_count
    for seq in seqs:
        for a, b in zip(seq, seq[1:]):
            deg[a] += 1
            deg[b] += 1
    return deg


def split_at_junctions(seqs, deg):
    """Cut every polyline wherever an interior point is not a simple pass-through.

    After this, each returned edge starts and ends on a node and has no
    junction in its interior - which is exactly the invariant the rest of the
    pipeline relies on.
    """
    edges = []
    for seq in seqs:
        start = 0
        for i in range(1, len(seq) - 1):
            if deg[seq[i]] != 2:
                edges.append(seq[start:i + 1])
                start = i
        edges.append(seq[start:])
    return [e for e in edges if len(e) >= 2 and e[0] != e[-1] or len(e) > 2]


def endpoint_degree(edges):
    """Node degree counted over graph edges (not segments)."""
    deg = Counter()
    for e in edges:
        deg[e[0]] += 1
        deg[e[-1]] += 1
    return deg


def junctions(seqs, node_count):
    """Indices of topological nodes - the schema's `is_node` points.

    A point interior to exactly one polyline has degree 2 and is shape only.
    Note a corner where two streets merely meet end-to-end is also degree 2:
    geometrically a corner, topologically a pass-through.  That is correct.
    """
    deg = segment_degree(seqs, node_count)
    return {i for i, d in enumerate(deg) if d != 2}


# ---------------------------------------------------------------------------
# 3. cleanup
# ---------------------------------------------------------------------------

def prune_stubs(nodes, edges, min_len=DEFAULT_MIN_EDGE_LEN):
    """Iteratively drop dead-end edges shorter than `min_len`.

    Iterative because removing one stub can expose another behind it - which is
    what kills overshoot tails left by tracing past an intersection.
    """
    edges = list(edges)
    while True:
        deg = endpoint_degree(edges)
        keep = [e for e in edges
                if not ((deg[e[0]] == 1 or deg[e[-1]] == 1)
                        and edge_length(nodes, e) < min_len)]
        if len(keep) == len(edges):
            return keep
        edges = keep


def dedupe_edges(nodes, edges):
    """Collapse duplicate edges between the same node pair, keeping the shortest."""
    best = {}
    for e in edges:
        key = (min(e[0], e[-1]), max(e[0], e[-1]))
        length = edge_length(nodes, e)
        if key not in best or length < best[key][0]:
            best[key] = (length, e)
    return [v[1] for v in best.values()]


def remove_isolated_nodes(nodes, edges):
    """Drop nodes no edge references, and reindex. Returns (nodes, edges, removed)."""
    used = sorted({n for e in edges for n in e})
    remap = {old: new for new, old in enumerate(used)}
    new_nodes = [nodes[i] for i in used]
    new_edges = [[remap[n] for n in e] for e in edges]
    return new_nodes, new_edges, len(nodes) - len(used)


# ---------------------------------------------------------------------------
# 4. validate - advisory, never a wall (citygen.md section 2.2)
# ---------------------------------------------------------------------------

def validate(nodes, edges, min_len=DEFAULT_MIN_EDGE_LEN):
    """Return a list of {rule, severity, detail} findings.

    Nothing here raises.  Validation is advisory: the artist is allowed to
    build the wrong thing on purpose, they just get told.
    """
    issues = []

    def add(rule, severity, detail):
        issues.append({"rule": rule, "severity": severity, "detail": detail})

    for i, e in enumerate(edges):
        if len(e) < 2:
            add("degenerate_edge", "block", "edge %d has %d nodes" % (i, len(e)))
            continue
        if edge_length(nodes, e) <= 0.0:
            add("zero_length_edge", "block", "edge %d has zero length" % i)
        elif edge_length(nodes, e) < min_len:
            add("short_edge", "warn",
                "edge %d is %.2fm, below min_edge_len %.2fm"
                % (i, edge_length(nodes, e), min_len))

    pairs = Counter((min(e[0], e[-1]), max(e[0], e[-1])) for e in edges if len(e) >= 2)
    for pair, count in pairs.items():
        if count > 1:
            add("duplicate_edge", "warn",
                "%d edges share endpoints %s" % (count, pair))

    used = {n for e in edges for n in e}
    orphans = [i for i in range(len(nodes)) if i not in used]
    if orphans:
        add("isolated_node", "warn", "%d nodes referenced by no edge" % len(orphans))

    deg = endpoint_degree(edges)
    dead = [n for n, d in deg.items() if d == 1]
    if dead:
        add("dead_end", "ignore", "%d dead-end nodes" % len(dead))

    return issues


def summarise(issues):
    """Counts per severity, for reporting on the node."""
    c = Counter(i["severity"] for i in issues)
    return {"block": c.get("block", 0), "warn": c.get("warn", 0),
            "ignore": c.get("ignore", 0), "total": len(issues)}


# ---------------------------------------------------------------------------
# top level
# ---------------------------------------------------------------------------

def build(polylines, weld_tol=DEFAULT_WELD_TOL, min_len=DEFAULT_MIN_EDGE_LEN,
          prune=True, dedupe=True):
    """Curves in, graph out.

    Returns dict with nodes, edges, degree, issues, stats.  Callers pass ONE
    layer's curves at a time - planarity is a per-layer invariant.
    """
    before_curves = len(polylines)
    nodes, seqs = weld(polylines, weld_tol)
    deg = segment_degree(seqs, len(nodes))
    junction_set = {i for i, d in enumerate(deg) if d != 2}
    edges = split_at_junctions(seqs, deg)
    after_split = len(edges)

    if dedupe:
        edges = dedupe_edges(nodes, edges)
    after_dedupe = len(edges)

    if prune:
        edges = prune_stubs(nodes, edges, min_len)
    after_prune = len(edges)

    nodes, edges, dropped = remove_isolated_nodes(nodes, edges)
    issues = validate(nodes, edges, min_len)

    # after splitting, every edge endpoint IS a topological node by construction
    # and every interior point is shape.  Derive it from the final edges so the
    # flags survive pruning and reindexing.
    node_set = {e[0] for e in edges} | {e[-1] for e in edges}

    return {
        "points": nodes,
        "edges": edges,
        "junctions": sorted(node_set),
        "is_node": [1 if i in node_set else 0 for i in range(len(nodes))],
        "degree": endpoint_degree(edges),
        "issues": issues,
        "stats": {
            "input_curves": before_curves,
            "edges_after_split": after_split,
            "edges_after_dedupe": after_dedupe,
            "edges_after_prune": after_prune,
            "points": len(nodes),
            "junctions": len(node_set),
            "isolated_points_dropped": dropped,
            **summarise(issues),
        },
    }
