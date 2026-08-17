"""Dump the junction footprint the BUILDER measures, for every case.

    hython tests/citygen/dump_trims.py                 # -> tests/unit/trim_calibration.json
    hython tests/citygen/dump_trims.py --out other.json

⚠️ **CALIBRATE, DO NOT INVENT** (§11.4). `plan.py` predicts what a junction
consumes from each arm as a FUNCTION of arms, widths, classes and angles, so
`standing` is checkable before any geometry exists. That function is only worth
something if it agrees with the plates the builder actually cuts — so this
script exports the builder's own `trim_start` / `trim_end` next to the node data
they were computed from, and `tests/unit/test_plan.py` asserts the model against
every one of them.

⚠️ Not "within 0.5 m", which is what §11.4 asked for and what this docstring
used to claim: the model is exact on straight arms and out by up to 4.58 m on
curved ones, because `s5j_solve` re-solves each corner in the frame at its own
cut. The bounds are pinned per case in `test_plan.py`, and the property to rely
on is the `standing > 0` VERDICT — which agrees with the builder on all 322
edges.

It reads `junction_solve/s5j_solve`, which is where the trims are written and
before `s5j_trim` applies them. The polylines there are the ones the corner
solve saw: resampled at 4 m and fused inside `pf_citygen_junction`, so lengths
and adjacent-vertex directions are the solver's own, not the segmenter's.

Nothing here saves a .hip, and nothing here writes to the repo except the JSON.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import cases                                       # noqa: E402

DEFAULT_OUT = os.path.join(os.path.dirname(HERE), "unit", "trim_calibration.json")

# The `s5j_params` values the corner solve reads. Recorded per case because
# E_short_t drives `corner_radius_scale` to 2.5 and the model must be handed the
# same number the builder used — a calibration against the wrong parameter is
# the kind of green that means nothing.
PARM_NAMES = ("miter_limit", "corner_radius_scale", "max_fillet_fraction",
              "arc_steps", "min_end_segment")


def _same_file(a, b):
    """Do these two spellings name the same file? Case, separators and `..` all
    differ between how a human types this path and how `os.path.join` built it."""
    return (os.path.normcase(os.path.abspath(a))
            == os.path.normcase(os.path.abspath(b)))


def _prim_attr(prim, name, default):
    try:
        return prim.attribValue(name)
    except Exception:
        return default


def _length(prim):
    pts = [p.point().position() for p in prim.vertices()]
    return sum((pts[i] - pts[i - 1]).length() for i in range(1, len(pts)))


def dump_case(built, full=False):
    """{"edges": [...], "nodes": [...]} straight off the solve node.

    `full` also writes every polyline vertex. That is diagnostic material, not
    fixture material — it is ~1.5 MB across the sixteen cases and it is exactly
    the geometry the planner is forbidden to depend on — so it goes to a
    scratch file, never to the committed calibration.
    """
    solve = cases.inner(built, "solve")
    if solve is None:
        raise RuntimeError("no s5j_solve node (or it is in error)")
    geo = solve.geometry()

    streets = [p for p in geo.prims()
               if _prim_attr(p, "is_junction_patch", 0) != 1 and len(p.vertices()) >= 2]

    edges = {}
    for pr in streets:
        pts = [v.point() for v in pr.vertices()]
        edges[pr.number()] = {
            "edge_id": _prim_attr(pr, "edge_id", "prim_%d" % pr.number()),
            "width": float(_prim_attr(pr, "streetWidth", 0.0)),
            "street_class": _prim_attr(pr, "street_class", ""),
            "length": _length(pr),
            "trim_start": float(_prim_attr(pr, "trim_start", 0.0)),
            "trim_end": float(_prim_attr(pr, "trim_end", 0.0)),
            "p0": [pts[0].position()[0], pts[0].position()[2]],
            "p1": [pts[-1].position()[0], pts[-1].position()[2]],
            "npts": len(pts),
        }
        if full:
            edges[pr.number()]["pts"] = [[round(p.position()[0], 6),
                                          round(p.position()[2], 6)] for p in pts]

    # Nodes exactly as s5j_solve finds them: a point with three or more incident
    # streets. Its `dirs[]` is the unit vector toward the ADJACENT VERTEX, which
    # on a curved arm is not the chord to the far node — so the dump carries it
    # rather than letting the model re-derive something subtly different.
    nodes = []
    for pt in geo.points():
        incident = [p for p in pt.prims() if p.number() in edges]
        if len(incident) < 3:
            continue
        pos = pt.position()
        arms = []
        for pr in incident:
            pts = [v.point() for v in pr.vertices()]
            at_start = pts[0].number() == pt.number()
            nb = (pts[1] if at_start else pts[-2]).position()
            dx, dz = nb[0] - pos[0], nb[2] - pos[2]
            n = math.hypot(dx, dz)
            if n < 1e-9:
                continue
            e = edges[pr.number()]
            arms.append({
                "edge_id": e["edge_id"],
                "at_start": bool(at_start),
                "dir": [dx / n, dz / n],
                "width": e["width"],
                "street_class": e["street_class"],
                "length": e["length"],
                # what the builder ended up cutting off THIS end of THIS arm
                "measured_trim": e["trim_start"] if at_start else e["trim_end"],
            })
        if len(arms) < 3:
            continue
        # M4: the node's authored/computed type and each arm's principal claim,
        # so the calibration can dispatch `node_trims` exactly as the builder
        # does - the geometry->planner round trip, tested at last.
        try:
            jt = pt.attribValue("junction_type")
        except Exception:
            jt = ""
        for a in arms:
            e = pr = None
            for cand in incident:
                if edges[cand.number()]["edge_id"] == a["edge_id"]:
                    pr = cand
                    break
            flag = 0
            if pr is not None:
                try:
                    flag = pr.attribValue("principal_start" if a["at_start"]
                                          else "principal_end")
                except Exception:
                    flag = 0
            a["principal"] = int(bool(flag))
        nodes.append({"pos": [pos[0], pos[2]], "arms": arms,
                      "junction_type": jt})

    nodes.sort(key=lambda n: (round(n["pos"][0], 4), round(n["pos"][1], 4)))
    out_edges = sorted(edges.values(), key=lambda e: e["edge_id"])
    return {"edges": out_edges, "nodes": nodes}


def main(argv):
    import hou

    out_path = DEFAULT_OUT
    if "--out" in argv:
        i = argv.index("--out") + 1
        if i >= len(argv):
            raise SystemExit("--out needs a path")
        out_path = argv[i]
    full = "--full" in argv
    # ⚠️ `--full` used to fall through to DEFAULT_OUT and silently replace the
    # 300 KB committed fixture with the 1.5 MB diagnostic one — while this
    # file's own docstring promised it "never" touches the calibration, and
    # while the suite stayed GREEN on the swapped file.
    #
    # ⚠️ AND THE FIRST GUARD COMPARED RAW STRINGS, which five of eight spellings
    # walk straight past: a relative path, forward slashes, `..`, or different
    # case all name the same file and none of them equal `DEFAULT_OUT`. README's
    # own invocation is relative and this doc writes forward slashes throughout,
    # so the two likeliest spellings were both holes. Compare real paths.
    if full and _same_file(out_path, DEFAULT_OUT):
        raise SystemExit("--full is diagnostic and must not overwrite the "
                         "committed fixture: pass --out <scratch path>")

    cases.install_hdas()
    parent, built = cases.build_all()

    data = {"houdini": hou.applicationVersionString(), "cases": {}}
    for name in sorted(built):
        case = built[name]
        case["city"].allowEditingOfContents()
        case["city"].cook(force=True)
        params = {}
        for pn in PARM_NAMES:
            p = cases.parm(case, "s5j_params_" + pn)
            if p is not None:
                params[pn] = p.eval()
        entry = dump_case(case, full)
        entry["params"] = params
        data["cases"][name] = entry
        print("%-18s %3d nodes  %3d edges  %s"
              % (name, len(entry["nodes"]), len(entry["edges"]), params))

    with open(out_path, "w") as fh:
        json.dump(data, fh, indent=1, sort_keys=True)
        fh.write("\n")
    print("\nwrote %s" % out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
