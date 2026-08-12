"""Does every promoted parameter on the four CityGen HDAs actually do anything?

    hython tests/citygen/parm_liveness.py
    hython tests/citygen/parm_liveness.py --verbose

Written 2026-08-10 after the artist reported "the ui of the nodes is not
connected [...] I think I found only 2 or 3 that work across all nodes."  It is
committed rather than thrown away because it is the only thing in this project
that can answer "is this slider wired?" without a human dragging it, and
because a parameter that quietly stops mattering is invisible to every other
check here — `run_scene_checks.py` only ever cooks the defaults.

Method, and it is the whole point: build every case fresh from `cases.py`, cook,
SHA-1 all four outputs, then set one parm to a sane in-range value, re-cook,
re-hash.

⚠️ TWO DIGESTS, NOT ONE, and this is the correction an audit forced on
2026-08-10.  The first version hashed geometry and attributes together and
called a parm LIVE if anything moved — which certified sliders that move no
geometry at all.  `lots_params_min_lot_area` was the proof: at 50, 900, 5000
and 20000 m² C_radial ships the same 773 lot prims in the same places, because
S8 viability is ADVISORY by design (`citygen.md` §2.2 — flag and explain, never
delete), so only `lot_reject` / `lot_viable` / `Cd` move.  Recorded LIVE, and to
the artist dragging it, dead.  So the sweep now reports three states:

    GEOM  counts, P or topology moved   — the slider changes the city
    ATTR  only attribute values moved   — the slider changes labels, not shapes
    DEAD  nothing moved at any value

A parm is GEOM/ATTR as soon as one digest moves on one case.  A parm is DEAD
only after every value in its list has been tried on every case that can reach
it; "it did nothing at +30%" is not the same finding and the second value in
each list exists to keep the two apart.  Anything unlisted gets a generic
perturbation, so a parm added tomorrow is swept tomorrow rather than silently
skipped.

⚠️ DEAD is scoped to the shipped slider range.  `close_min_pts` at 1000 — far
outside its `{3 64}` range — does move C_radial.  That confirms its recorded
reason ("wired, never the binding gate") rather than contradicting it, but a
value outside the range is not evidence about the parameter as shipped.

The dead and attribute-only ones as of 2026-08-10, and their causes, are tabled
in `ideas/citygen_streets.md` §4c "Every promoted parameter, measured".
"""

import array
import hashlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cases                                   # noqa: E402

VERBOSE = "--verbose" in sys.argv

# Values to try, in order, per parameter.  The second entry is deliberately at
# or near an end of the shipped range: several of these gates are simply not
# binding at their default and "no change at +30%" would misreport them as
# unwired.  Parms not listed here get GENERIC.
PERTURB = {
    ("field_grid", "cx"): [120.0],
    ("field_grid", "cz"): [120.0],
    ("field_grid", "weight"): [8.0, 0.0],
    ("field_grid", "falloff"): [1500.0],
    ("field_grid", "angle"): [63.0],
    ("field_radial", "cx"): [120.0],
    ("field_radial", "cz"): [120.0],
    ("field_radial", "weight"): [5.0, 8.0, 0.0],
    ("field_radial", "falloff"): [1000.0],
    ("field_radial", "angle"): [45.0, 90.0, -180.0],
    ("field_radial", "plaza_radius"): [120.0],

    ("tracer", "domain"): [600.0],
    ("tracer", "res"): [90],
    ("tracer", "seed_spacing"): [90.0],
    ("tracer", "step"): [10.0],
    ("tracer", "max_steps"): [150],
    ("tracer", "min_street_sep"): [90.0],
    ("tracer", "min_node_dist"): [40.0, 300.0, 0.0],
    ("tracer", "d_lookahead"): [40.0, 0.0],
    ("tracer", "organic_amp"): [60.0, 90.0, 0.0],
    ("tracer", "organic_scale"): [80.0, 3000.0, 1.0],
    ("tracer", "close_seam_cells"): [0.5, 0.0],
    ("tracer", "close_road_width"): [40.0, 0.0],
    ("tracer", "close_max_end_angle"): [15.0, 0.0],
    ("tracer", "close_min_pts"): [40, 64, 3],

    ("trace", "graph_prune_min_edge_len"): [30.0],
    ("trace", "graph_params_min_node_dist"): [20.0],
    ("trace", "graph_params_min_join_angle"): [5.0, 90.0],
    ("trace", "graph_params_d_extend"): [30.0],
    ("trace", "graph_params_max_curvature"): [20.0],
    ("trace", "graph_params_turn_radius_scale"): [4.0],
    ("trace", "graph_params_turn_smooth_gain"): [0.0],
    ("trace", "street_params_arterial_len"): [400.0],
    ("trace", "street_params_collector_len"): [140.0],
    ("trace", "street_params_min_junction_angle"): [60.0],
    ("trace", "street_params_region_size"): [600.0],
    ("trace", "street_params_zone_inner"): [0.35],
    ("trace", "street_params_zone_core"): [0.10],
    ("trace", "s5j_params_miter_limit"): [1.5],
    ("trace", "s5j_params_corner_radius_scale"): [2.5],
    ("trace", "s5j_params_arc_steps"): [12],
    ("trace", "s5j_params_max_fillet_fraction"): [0.15],
    ("trace", "s5j_params_min_end_segment"): [3.0],
    # ⚠️ THREE PARMS USED TO FALL THROUGH TO generic() AND IT GOT ALL THREE
    # WRONG, one of them badly enough to fail the run.
    #
    # `graph_params_repair_passes` is a CAP and every case converges well
    # inside it, so generic()'s cur*2 = 16 clamped to the range max of 12 was a
    # guaranteed no-op: it swept the one direction in which a cap cannot
    # matter, reported DEAD, and exited 1. Downwards it is the liveliest parm
    # on the node — 1 is the documented single-pass build and it moves the
    # geometry of every case.
    ("trace", "graph_params_repair_passes"): [1],
    # ...and the tolerance the loop is measured against. 0 asks for a bit-exact
    # fixed point that float32 re-accumulation cannot deliver, so it runs to
    # the cap; 0.1 m stops it early. Either way the graph moves.
    ("trace", "graph_params_repair_tolerance"): [0.1, 0.0],
    # These two read GEOM only by luck of the doubling. Both are thresholds
    # whose interesting direction is DOWN (or off), and the case that was
    # written for the first of them is G_tongue — which is why STREET_CASES now
    # includes it.
    ("trace", "s5j_params_min_standing_widths"): [0.0, 3.0],
    ("trace", "s5j_params_culdesac_radius"): [30.0, 0.0],
    ("mesh", "lots_params_lot_frontage"): [40.0],
    ("mesh", "lots_params_subdiv_mode"): ["flip"],
    ("mesh", "lots_params_target_lot_area"): [1800.0],
    ("mesh", "lots_params_lot_area_variance"): [0.9],
    ("mesh", "lots_params_split_jitter"): [0.45],
    ("mesh", "lots_params_lot_depth"): [45.0],
    ("mesh", "lots_params_min_lot_area"): [900.0],
    ("mesh", "lots_params_min_frontage"): [30.0],
    # Two values each, one at a range end, per this table's own convention — the
    # generic cur*2 gives a single mid-range probe, and for a THRESHOLD the
    # interesting direction is the one that switches the rung off entirely.
    # ⚠️ The sweep stops at the first value that classifies, so a live parm never
    # reaches its second entry; these exist for the day one of them goes quiet,
    # which is exactly when a single mid-range probe would lie.
    ("mesh", "lots_params_min_street_edge"): [16.0, 0.0],
    ("mesh", "lots_params_min_lot_width"): [12.0, 0.0],
    ("mesh", "lots_params_max_aspect"): [8.0, 20.0],
    ("mesh", "s5b_params_pier_spacing"): [80.0, 4.0, 300.0],
    ("mesh", "s5b_params_max_span"): [20.0, 600.0],
    ("mesh", "s5b_params_pier_clearance"): [40.0, 0.0, 120.0],
    ("mesh", "include_lots"): ["flip"],
}

# Known dead as of 2026-08-10, with the cause.  The run FAILS when this set and
# the measured set disagree in either direction: a parm going dead is a
# regression, and a parm coming alive means the entry here is stale.
KNOWN_DEAD = {
    ("tracer", "organic_amp"): "no `organic` field generator ships (S1)",
    ("tracer", "organic_scale"): "no `organic` field generator ships (S1)",
    ("tracer", "close_min_pts"): "wired, never the binding gate in range",
    ("mesh", "s5b_params_pier_spacing"): "no case has layer > 0, so no bridge",
    ("mesh", "s5b_params_max_span"): "no case has layer > 0, so no bridge",
    ("mesh", "s5b_params_pier_clearance"): "no case has layer > 0, so no bridge",
}

# Moves attributes and no geometry, at the value swept.  Same contract as
# KNOWN_DEAD: a disagreement either way fails the run.
KNOWN_ATTR_ONLY = {
    ("trace", "street_params_region_size"): "region_id / block_id / lot_id only",
    ("trace", "street_params_zone_inner"): "land_use string only",
    ("trace", "street_params_zone_core"): "land_use string only",
    # NOT lots_params_lot_depth: it is only a frontage tolerance in
    # recursive_obb, so it reads attribute-only on C_radial -- but it is the
    # ring inset in `offset` mode and moves geometry on D_offset. Escalating to
    # the next case is what tells those apart; one case is not a measurement.
    ("mesh", "lots_params_min_lot_area"): (
        "S8 viability is ADVISORY by design (citygen.md 2.2) -- it writes "
        "lot_reject / lot_viable / Cd and deletes nothing. 50 -> 20000 m2 "
        "leaves C_radial's 773 lot prims untouched"),
    # The two SHAPE tests added 2026-08-11. Same contract as min_lot_area and
    # for the same reason: they are the other three quarters of the same
    # advisory ladder, so they move lot_reject / lot_viable / lot_width /
    # lot_aspect / Cd and no geometry. If either ever reads GEOM, S8 has started
    # deleting parcels and that is a contract change, not a passing test.
    ("mesh", "lots_params_min_lot_width"): (
        "advisory shape test -- writes lot_reject = \"too_narrow\" and never "
        "deletes"),
    ("mesh", "lots_params_max_aspect"): (
        "advisory shape test -- writes lot_reject = \"elongated\" and never "
        "deletes"),
    ("mesh", "lots_params_min_street_edge"): (
        "advisory shape test -- writes lot_reject = \"no_street_edge\" and "
        "never deletes"),
}

# Which cases can reach a parm, cheapest first.  A parm is only DEAD after all
# of them.
FIELD_CASE = {"field_grid": "B_grid", "field_radial": "C_radial"}
TRACE_CASES = ["C_radial", "B_grid"]
# ⚠️ G_tongue belongs here. `s5j_params_min_standing_widths` is swept over this
# list, and G_tongue is the case that was WRITTEN for it (cases.py) — the sweep
# was running the tongue parameter on every case except the tongue.
STREET_CASES = ["C_radial", "A_drawn", "B_grid", "D_offset", "E_short_t",
                "F_bend", "G_tongue"]

# S3/S4/S5 moved onto the tracer with the stages they steer, so `pf_citygen_trace`
# now carries two populations of parameter: the field/trace ones, which only the
# two generated cases can reach, and these, which every case reaches because a
# hand-drawn spline enters the same node.  They share a definition and need
# different case lists, so the split is by name.
GRAPH_PARMS = {
    "graph_prune_min_edge_len", "graph_params_min_node_dist",
    "graph_params_min_join_angle", "graph_params_d_extend",
    "graph_params_max_curvature", "graph_params_turn_radius_scale",
    "graph_params_turn_smooth_gain", "street_params_arterial_len",
    "street_params_collector_len", "street_params_min_junction_angle",
    "street_params_region_size", "street_params_zone_inner",
    "street_params_zone_core", "s5j_params_miter_limit",
    "s5j_params_corner_radius_scale", "s5j_params_arc_steps",
    "s5j_params_max_fillet_fraction", "s5j_params_min_end_segment",
    "s5j_params_min_standing_widths", "s5j_params_culdesac_radius",
}


def digest(geo):
    """(geometry digest, attribute digest) for one output.

    Split so an attribute-only change reads as ATTR rather than as LIVE. The
    geometry half is counts + P + real vertex->point topology; it is walked in
    Python on purpose, because `hou.Geometry.primIntrinsicValues("vertexcount")`
    DOES NOT EXIST in H22 and the first version of this file called it inside a
    bare `except`, so the topology term was silently absent for a whole commit.
    """
    import hou
    if geo is None:
        return ("NONE", "NONE")
    g = hashlib.sha1()
    a = hashlib.sha1()
    npt = geo.intrinsicValue("pointcount")
    g.update(("c %s %s %s\n" % (npt, geo.intrinsicValue("primitivecount"),
                                geo.intrinsicValue("vertexcount"))).encode())
    if npt:
        g.update(array.array("f", geo.pointFloatAttribValues("P")).tobytes())
    topo = array.array("i")
    for pr in geo.prims():
        vs = pr.vertices()
        topo.append(len(vs))
        for v in vs:
            topo.append(v.point().number())
    g.update(topo.tobytes())
    for attribs, fg, ig, sg in (
            (geo.pointAttribs(), geo.pointFloatAttribValues,
             geo.pointIntAttribValues, geo.pointStringAttribValues),
            (geo.primAttribs(), geo.primFloatAttribValues,
             geo.primIntAttribValues, geo.primStringAttribValues),
            (geo.vertexAttribs(), geo.vertexFloatAttribValues,
             geo.vertexIntAttribValues, geo.vertexStringAttribValues)):
        for at in sorted(attribs, key=lambda x: x.name()):
            if at.name() == "P":
                continue                      # already in the geometry half
            a.update(at.name().encode())
            try:
                if at.dataType() == hou.attribData.Float:
                    a.update(array.array("f", fg(at.name())).tobytes())
                elif at.dataType() == hou.attribData.Int:
                    a.update(array.array("i", ig(at.name())).tobytes())
                else:
                    a.update(repr(sg(at.name())).encode())
            except Exception as exc:
                a.update(("ERR %s" % exc).encode())
    for at in sorted(geo.globalAttribs(), key=lambda x: x.name()):
        try:
            a.update(("%s=%r" % (at.name(), geo.attribValue(at.name()))).encode())
        except Exception:
            pass
    return (g.hexdigest()[:16], a.hexdigest()[:16])


def generic(parm):
    """A perturbation for a parm nobody has written a value for yet."""
    import hou
    t = parm.parmTemplate()
    cur = parm.eval()
    if t.type() == hou.parmTemplateType.Toggle or t.type() == hou.parmTemplateType.Menu:
        return ["flip"]
    lo, hi = t.minValue(), t.maxValue()
    want = cur * 2.0 if cur else (hi * 0.5 if hi else 1.0)
    want = min(max(want, lo), hi)
    if want == cur:
        want = lo if cur != lo else hi
    return [type(cur)(want)]


def main():
    import hou
    cases.install_hdas()
    parent, built = cases.build_all()
    city = {k: v["city"] for k, v in built.items()}
    field = {"field_grid": built["B_grid"]["field"],
             "field_radial": built["C_radial"]["field"]}
    trace = {k: v["trace"] for k, v in built.items()}
    tracer = {k: v.get("tracer") for k, v in built.items()}

    def dig(ck):
        city[ck].cook(force=True)
        if city[ck].errors():
            raise RuntimeError("%s: %s" % (ck, city[ck].errors()[0][:200]))
        return [digest(city[ck].geometry(i)) for i in range(4)]

    base = {k: dig(k) for k in city}

    def owner(hda, ck):
        if hda in field:
            return field[hda]
        if hda == "tracer":
            return tracer[ck]
        if hda == "trace":
            return trace[ck]
        return city[ck]

    # ⚠️ THE TRACER WAS SWEPT BY NOTHING. When the pipeline split, `_chain`
    # started returning the SEGMENTER as the "trace" role, so every S1/S2
    # parameter — the whole tracing stage — was perturbed on a node where it is
    # dead and reported as a regression, while the node it actually drives was
    # never swept at all. Ten false regressions, and zero coverage of the stage
    # that generates the streets.
    plan = []
    for hda, ck_list in (("field_grid", [FIELD_CASE["field_grid"]]),
                         ("field_radial", [FIELD_CASE["field_radial"]]),
                         ("tracer", TRACE_CASES),
                         ("trace", TRACE_CASES),
                         ("mesh", STREET_CASES)):
        node = owner(hda, ck_list[0])
        if node is None:
            continue
        for pt in node.type().definition().parmTemplateGroup().entriesWithoutFolders():
            if pt.type() in (hou.parmTemplateType.Separator,
                             hou.parmTemplateType.Label):
                continue
            # ⚠️ The three assets forked from `pf_citygen_trace` inherited its
            # WHOLE promoted interface, so most parms on any one of them belong
            # to a different node. Sweeping the Tracer's copy of a Segmenter parm
            # measures a decoy and reports it dead. The Tracer is therefore swept
            # only on the S1/S2 parms it actually owns — the ones this table
            # names — and the Segmenter keeps the rest.
            if hda == "tracer" and (hda, pt.name()) not in PERTURB:
                continue
            if hda == "trace" and (("tracer", pt.name()) in PERTURB):
                continue
            cks = STREET_CASES if pt.name() in GRAPH_PARMS else ck_list
            if hda == "tracer":
                cks = [c for c in cks if built[c].get("tracer") is not None]
                if not cks:
                    continue
            plan.append((hda, pt.name(), cks))

    rows, dead, attr_only = [], [], []
    for hda, pname, ck_list in plan:
        vals = PERTURB.get((hda, pname))
        first = owner(hda, ck_list[0]).parm(pname)
        if first is None:
            continue
        if vals is None:
            vals = generic(first)
            print("  (no perturbation listed for %s/%s, using %r)" % (hda, pname, vals))
        state, where = "DEAD", ""
        for ck in ck_list:
            _own = owner(hda, ck)
            if _own is None:
                continue
            p = _own.parm(pname)
            if p is None:
                continue
            old = p.eval()
            for v in vals:
                new = (0 if old else 1) if v == "flip" else v
                if new == old:
                    continue
                p.set(new)
                try:
                    d = dig(ck)
                finally:
                    p.set(old)
                geom = [i for i in range(4) if d[i][0] != base[ck][i][0]]
                attr = [i for i in range(4) if d[i][1] != base[ck][i][1]]
                if VERBOSE:
                    print("    %s/%s=%s on %s -> geom %s attr %s"
                          % (hda, pname, new, ck, geom or "-", attr or "-"))
                if geom:
                    state = "GEOM"
                    where = "%s %s=%s geometry moved on outputs %s" % (ck, pname, new, geom)
                    break
                if attr and state == "DEAD":
                    state = "ATTR"
                    where = "%s %s=%s ATTRIBUTES ONLY on outputs %s" % (ck, pname, new, attr)
            if state == "GEOM":
                break
        rows.append((hda, pname, state, where))
        if state == "DEAD":
            dead.append((hda, pname))
        elif state == "ATTR":
            attr_only.append((hda, pname))
        print("%-12s %-36s %-4s  %s" % (hda, pname, state, where))

    post = {k: dig(k) for k in city}
    drift = [k for k in city if post[k] != base[k]]

    print("\n%d parms swept: %d move geometry, %d move attributes only, %d dead"
          % (len(rows), len(rows) - len(dead) - len(attr_only), len(attr_only),
             len(dead)))
    fails = 0
    for label, got, known in (("dead", dead, KNOWN_DEAD),
                              ("attribute-only", attr_only, KNOWN_ATTR_ONLY)):
        for key in got:
            if key not in known:
                print("REGRESSION: %s/%s is %s and is not a known %s parm"
                      % (key[0], key[1], label, label))
                fails += 1
        for key, why in known.items():
            if key not in got:
                print("STALE: %s/%s is recorded %s (%s) but it did something else"
                      % (key[0], key[1], label, why))
                fails += 1
    if drift:
        print("RESTORE DRIFT on %s -- a perturbation was not undone" % drift)
        fails += 1
    print("\n%s" % ("OK" if not fails else "%d problems" % fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
