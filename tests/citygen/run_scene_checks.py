"""Run every CityGen geometry check in a throwaway Houdini session.

    hython tests/citygen/run_scene_checks.py
    hython tests/citygen/run_scene_checks.py --update-baseline
    hython tests/citygen/run_scene_checks.py --json results.json

The scene is built from scratch and never saved.

Numbers first, renders second. Almost every real defect found during the audit
rounds was diagnosed numerically; the renders showed that something was wrong,
the numbers said what. So this runs headless and cheap, and rendering is a
separate, GUI-only step for whatever this flags.

BASELINE: several regressions were only ever visible as "this number got
worse" — a lot-winding collision, a block count that tripled. Bare pass/fail
would have missed both. The runner diffs every value against baseline.json and
reports movement even when a check still passes.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import checks as C          # noqa: E402
import cases                # noqa: E402

BASELINE = os.path.join(HERE, "baseline.json")


def run_case(name, city, field=None):
    """All checks for one city. Returns [Result]."""
    out = []
    city.allowEditingOfContents()
    try:
        city.cook(force=True)
    except Exception as exc:
        return [C.Result("cook", False, None, "cook failed: %s" % str(exc)[:200])]
    if city.errors():
        return [C.Result("cook", False, None, city.errors()[0][:300])]

    def inner(nm):
        n = city.node(nm)
        return None if (n is None or n.errors()) else n

    def out_geo(role):
        g = city.geometry(cases.OUTPUT_INDEX[role])
        if g is None:
            raise RuntimeError("output %r (index %d) produced no geometry"
                               % (role, cases.OUTPUT_INDEX[role]))
        return g

    try:
        g_city = out_geo("city")
        g_blocks = out_geo("blocks")
        g_lots = out_geo("lots")
        g_graph = out_geo("graph")
    except RuntimeError as exc:
        return [C.Result("outputs", False, None, str(exc))]

    out.append(C.no_zero_area_prims(g_city))
    out.append(C.no_loose_points(g_city))
    out.append(C.no_downward_faces(g_city))
    out.append(C.no_scratch_groups(g_city))
    out.append(C.no_scratch_groups(g_blocks))
    out[-1].name = "no_scratch_groups_blocks"
    out.append(C.no_scratch_groups(g_lots))
    out[-1].name = "no_scratch_groups_lots"
    out.append(C.no_scratch_attribs(g_lots, C.LOT_PRIM_ATTRS, C.LOT_POINT_ATTRS,
                                    name="no_scratch_attribs_lots"))

    # the union, not the parts — see merged_city_self_intersections
    out.append(C.merged_city_self_intersections(city))
    # and the other half of the union: not "do the parts overlap" but "do the
    # parts between them leave anything unpaved"
    out.append(C.city_is_fully_paved(city, inner(cases.INTERNAL["corridor"])))

    out.append(C.graph_is_planar(g_graph))
    out.append(C.no_orphan_components(g_graph))
    out.append(C.dead_ends(g_graph))
    out.append(C.attribute_schema(g_graph, g_city))

    patches = inner(cases.INTERNAL["patches"])
    surface = inner(cases.INTERNAL["surface"])
    solve = inner(cases.INTERNAL["solve"])
    rscale = city.parm("s5j_params_corner_radius_scale")
    maxfrac = city.parm("s5j_params_max_fillet_fraction")
    if patches and surface:
        out.append(C.no_degenerate_corner_segments(patches.geometry()))
        out.append(C.every_corner_is_an_arc(
            patches.geometry(),
            solve.geometry() if solve else None,
            rscale.eval() if rscale else 1.0,
            maxfrac.eval() if maxfrac else 0.4))
        out.append(C.sidewalk_bands_match_corners(patches.geometry(),
                                                  surface.geometry()))
        out.append(C.junction_boundary_is_simple(patches.geometry()))
        out.append(C.self_intersections(surface, "selfx_junction_surface"))
    else:
        for nm in ("no_degenerate_corner_segments", "every_corner_is_an_arc",
                   "sidewalk_bands_match_corners",
                   "junction_boundary_is_simple", "selfx_junction_surface"):
            out.append(C.Result(nm, True, None, "internal node missing", skipped=True))

    roads = inner(cases.INTERNAL["roads"])
    if roads:
        out.append(C.self_intersections(roads, "selfx_roads"))

    # the S5 seam: the road and the patch must agree where the junction ends
    trimmed = inner(cases.INTERNAL["trim"])
    if solve and trimmed:
        out.append(C.trim_metric_is_consistent(solve.geometry(), trimmed.geometry()))
        out.append(C.every_mouth_has_a_road(solve.geometry(), trimmed.geometry()))
    if trimmed:
        out.append(C.no_sweep_fold_after_trim(trimmed.geometry()))

    out.append(C.no_nonplanar_y(g_lots))
    out[-1].name = "lots_planar"
    out.append(C.lots_tile_blocks(g_lots, g_blocks))
    out.append(C.no_duplicate_lot_footprints(g_lots))
    out.append(C.lot_aspect_ratio(g_lots))
    out.append(C.lots_are_simple_polygons(g_lots))

    # only the radial field declares a plaza; the others report a skip rather
    # than nothing, so a check that stops running is visible instead of silent
    plaza = field.parm("plaza_radius") if field else None
    if plaza is None:
        out.append(C.Result("plaza_disc_is_clear", True, None,
                            "no plaza declared by this case", skipped=True))
    else:
        out.append(C.plaza_disc_is_clear(g_blocks, g_graph,
                                         field.parm("cx").eval(),
                                         field.parm("cz").eval(),
                                         plaza.eval()))
    out.append(C.no_downward_faces(g_lots))
    out[-1].name = "no_downward_lots"
    out.append(C.no_downward_faces(g_blocks))
    out[-1].name = "no_downward_blocks"

    out.append(C.Result("counts", True,
                        {"city": len(g_city.prims()), "blocks": len(g_blocks.prims()),
                         "lots": len(g_lots.prims()), "edges": len(g_graph.prims())},
                        "informational"))
    return out


def main():
    import hou
    update = "--update-baseline" in sys.argv
    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]

    cases.install_hdas()
    parent, built = cases.build_all()

    results, failures = {}, 0
    for name in sorted(built):
        res = run_case(name, built[name]["city"], built[name].get("field"))
        results[name] = [r.as_dict() for r in res]
        print("\n=== %s ===" % name)
        for r in res:
            print("  %r" % r)
            if not r.ok and not r.skipped:
                failures += 1

    # any node erroring at all is a failure in its own right
    cook_errors = [n.path() for n in parent.allSubChildren() if n.errors()]
    if cook_errors:
        failures += 1
        print("\nCOOK ERRORS: %s" % cook_errors[:5])

    base = {}
    if os.path.exists(BASELINE):
        with open(BASELINE) as fh:
            base = json.load(fh)

    moved = []
    for case, rs in results.items():
        prev = {d["name"]: d for d in base.get(case, [])}
        for d in rs:
            old = prev.get(d["name"])
            if old is not None and old["value"] != d["value"]:
                moved.append("%s/%s: %s -> %s" % (case, d["name"], old["value"], d["value"]))
    if moved:
        print("\n--- moved since baseline (check each is an improvement) ---")
        for m in moved:
            print("  " + m)

    if update:
        with open(BASELINE, "w") as fh:
            json.dump(results, fh, indent=2, sort_keys=True)
        print("\nbaseline written: %s" % BASELINE)
    if json_out:
        with open(json_out, "w") as fh:
            json.dump(results, fh, indent=2, sort_keys=True)

    print("\n%d failing checks" % failures)
    # never save the hip
    sys.exit(1 if failures and not update else 0)


if __name__ == "__main__":
    main()
