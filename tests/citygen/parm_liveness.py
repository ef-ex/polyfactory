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
SHA-1 all four outputs — counts, P, topology AND every point/prim/vertex/detail
attribute, so an attribute-only change is still seen — then set one parm to a
sane in-range value, re-cook, re-hash.

A parm is LIVE as soon as one digest moves on one case.  A parm is DEAD only
after every value in its list has been tried on every case that can reach it;
"it did nothing at +30%" is not the same finding and the second value in each
list exists to keep the two apart.  Anything unlisted gets a generic
perturbation, so a parm added tomorrow is swept tomorrow rather than silently
skipped.

The nine dead ones as of 2026-08-10, and their causes, are tabled in
`ideas/citygen_streets.md` §4c "Every promoted parameter, measured".
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

    ("trace", "domain"): [600.0],
    ("trace", "res"): [90],
    ("trace", "seed_spacing"): [90.0],
    ("trace", "step"): [10.0],
    ("trace", "max_steps"): [150],
    ("trace", "min_street_sep"): [90.0],
    ("trace", "min_node_dist"): [40.0, 300.0, 0.0],
    ("trace", "d_lookahead"): [40.0, 0.0],
    ("trace", "organic_amp"): [60.0, 90.0, 0.0],
    ("trace", "organic_scale"): [80.0, 3000.0, 1.0],
    ("trace", "close_seam_cells"): [0.5, 0.0],
    ("trace", "close_road_width"): [40.0, 0.0],
    ("trace", "close_max_end_angle"): [15.0, 0.0],
    ("trace", "close_min_pts"): [40, 64, 3],

    ("streets", "graph_prune_min_edge_len"): [30.0],
    ("streets", "graph_params_min_node_dist"): [20.0],
    ("streets", "graph_params_min_join_angle"): [5.0, 90.0],
    ("streets", "graph_params_d_extend"): [30.0],
    ("streets", "graph_params_max_curvature"): [20.0],
    ("streets", "graph_params_turn_radius_scale"): [4.0],
    ("streets", "graph_params_turn_smooth_gain"): [0.0],
    ("streets", "street_params_arterial_len"): [400.0],
    ("streets", "street_params_collector_len"): [140.0],
    ("streets", "street_params_min_junction_angle"): [60.0],
    ("streets", "street_params_region_size"): [600.0],
    ("streets", "street_params_zone_inner"): [0.35],
    ("streets", "street_params_zone_core"): [0.10],
    ("streets", "s5j_params_miter_limit"): [1.5],
    ("streets", "s5j_params_corner_radius_scale"): [2.5],
    ("streets", "s5j_params_arc_steps"): [12],
    ("streets", "s5j_params_max_fillet_fraction"): [0.15],
    ("streets", "s5j_params_min_end_segment"): [3.0],
    ("streets", "lots_params_lot_frontage"): [40.0],
    ("streets", "lots_params_subdiv_mode"): ["flip"],
    ("streets", "lots_params_target_lot_area"): [1800.0],
    ("streets", "lots_params_lot_area_variance"): [0.9],
    ("streets", "lots_params_split_jitter"): [0.45],
    ("streets", "lots_params_lot_depth"): [45.0],
    ("streets", "lots_params_min_lot_area"): [900.0],
    ("streets", "lots_params_min_frontage"): [30.0],
    ("streets", "s5b_params_pier_spacing"): [80.0, 4.0, 300.0],
    ("streets", "s5b_params_max_span"): [20.0, 600.0],
    ("streets", "s5b_params_pier_clearance"): [40.0, 0.0, 120.0],
    ("streets", "include_lots"): ["flip"],
}

# Known dead as of 2026-08-10, with the cause.  The run FAILS when this set and
# the measured set disagree in either direction: a parm going dead is a
# regression, and a parm coming alive means the entry here is stale.
KNOWN_DEAD = {
    ("trace", "organic_amp"): "no `organic` field generator ships (S1)",
    ("trace", "organic_scale"): "no `organic` field generator ships (S1)",
    ("trace", "close_min_pts"): "wired, never the binding gate",
    ("streets", "s5b_params_pier_spacing"): "no case has layer > 0, so no bridge",
    ("streets", "s5b_params_max_span"): "no case has layer > 0, so no bridge",
    ("streets", "s5b_params_pier_clearance"): "no case has layer > 0, so no bridge",
}

# Which cases can reach a parm, cheapest first.  A parm is only DEAD after all
# of them.
FIELD_CASE = {"field_grid": "B_grid", "field_radial": "C_radial"}
TRACE_CASES = ["C_radial", "B_grid"]
STREET_CASES = ["C_radial", "A_drawn", "B_grid", "D_offset", "E_short_t", "F_bend"]


def digest(geo):
    """Everything that could distinguish two cooks of the same node."""
    import hou
    h = hashlib.sha1()
    if geo is None:
        return "NONE"
    h.update(("c %s %s %s\n" % (geo.intrinsicValue("pointcount"),
                                geo.intrinsicValue("primitivecount"),
                                geo.intrinsicValue("vertexcount"))).encode())
    if geo.intrinsicValue("pointcount"):
        h.update(array.array("f", geo.pointFloatAttribValues("P")).tobytes())
    if geo.intrinsicValue("primitivecount"):
        try:
            h.update(array.array("i", geo.primIntrinsicValues("vertexcount")).tobytes())
        except Exception:
            pass
    for attribs, fg, ig, sg in (
            (geo.pointAttribs(), geo.pointFloatAttribValues,
             geo.pointIntAttribValues, geo.pointStringAttribValues),
            (geo.primAttribs(), geo.primFloatAttribValues,
             geo.primIntAttribValues, geo.primStringAttribValues),
            (geo.vertexAttribs(), geo.vertexFloatAttribValues,
             geo.vertexIntAttribValues, geo.vertexStringAttribValues)):
        for a in sorted(attribs, key=lambda x: x.name()):
            h.update(a.name().encode())
            try:
                if a.dataType() == hou.attribData.Float:
                    h.update(array.array("f", fg(a.name())).tobytes())
                elif a.dataType() == hou.attribData.Int:
                    h.update(array.array("i", ig(a.name())).tobytes())
                else:
                    h.update(repr(sg(a.name())).encode())
            except Exception as exc:
                h.update(("ERR %s" % exc).encode())
    for a in sorted(geo.globalAttribs(), key=lambda x: x.name()):
        try:
            h.update(("%s=%r" % (a.name(), geo.attribValue(a.name()))).encode())
        except Exception:
            pass
    return h.hexdigest()[:16]


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
    trace = {"B_grid": built["B_grid"]["input"], "C_radial": built["C_radial"]["input"]}

    def dig(ck):
        city[ck].cook(force=True)
        if city[ck].errors():
            raise RuntimeError("%s: %s" % (ck, city[ck].errors()[0][:200]))
        return [digest(city[ck].geometry(i)) for i in range(4)]

    base = {k: dig(k) for k in city}

    def owner(hda, ck):
        if hda in field:
            return field[hda]
        if hda == "trace":
            return trace[ck]
        return city[ck]

    plan = []
    for hda, ck_list in (("field_grid", [FIELD_CASE["field_grid"]]),
                         ("field_radial", [FIELD_CASE["field_radial"]]),
                         ("trace", TRACE_CASES),
                         ("streets", STREET_CASES)):
        node = owner(hda, ck_list[0])
        for pt in node.type().definition().parmTemplateGroup().entriesWithoutFolders():
            if pt.type() in (hou.parmTemplateType.Separator,
                             hou.parmTemplateType.Label):
                continue
            plan.append((hda, pt.name(), ck_list))

    rows, dead = [], []
    for hda, pname, ck_list in plan:
        vals = PERTURB.get((hda, pname))
        first = owner(hda, ck_list[0]).parm(pname)
        if first is None:
            continue
        if vals is None:
            vals = generic(first)
            print("  (no perturbation listed for %s/%s, using %r)" % (hda, pname, vals))
        moved, where = False, ""
        for ck in ck_list:
            p = owner(hda, ck).parm(pname)
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
                mv = [i for i in range(4) if d[i] != base[ck][i]]
                if VERBOSE:
                    print("    %s/%s %s=%s on %s -> %s"
                          % (hda, pname, pname, new, ck, mv or "no change"))
                if mv:
                    moved, where = True, "%s %s=%s outputs %s" % (ck, pname, new, mv)
                    break
            if moved:
                break
        rows.append((hda, pname, moved, where))
        if not moved:
            dead.append((hda, pname))
        print("%-12s %-36s %s  %s" % (hda, pname, "LIVE" if moved else "DEAD", where))

    post = {k: dig(k) for k in city}
    drift = [k for k in city if post[k] != base[k]]

    print("\n%d parms swept: %d live, %d dead" % (len(rows), len(rows) - len(dead),
                                                  len(dead)))
    fails = 0
    for key in dead:
        if key not in KNOWN_DEAD:
            print("REGRESSION: %s/%s moves no output at any tested value and is not "
                  "a known dead parm" % key)
            fails += 1
    for key, why in KNOWN_DEAD.items():
        if key not in dead:
            print("STALE: %s/%s is recorded dead (%s) but it moved an output"
                  % (key[0], key[1], why))
            fails += 1
    if drift:
        print("RESTORE DRIFT on %s -- a perturbation was not undone" % drift)
        fails += 1
    print("\n%s" % ("OK" if not fails else "%d problems" % fails))
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main()
