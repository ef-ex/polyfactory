"""Run every polyChain geometry check in a throwaway Houdini session.

    hython tests/polychain/run_scene_checks.py
    hython tests/polychain/run_scene_checks.py --update-baseline
    hython tests/polychain/run_scene_checks.py --json results.json

Nothing is saved and no .hip exists. Numbers first, renders second: every
check records a value, and the runner diffs every value against baseline.json
and prints movement even where a check still passes. Read that list and
confirm each move is an improvement before running --update-baseline.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

import cases                                                     # noqa: E402
import checks as C                                               # noqa: E402

BASELINE = os.path.join(HERE, "baseline.json")

# What each case is ALLOWED to warn about. An empty tuple is the assertion
# "clean input raises nothing"; the two non-empty entries are the cases that
# exist to prove the detectors are not vacuous.
EXPECTED_WARNS = {
    "J_coarse_bend": ("pc_warn_bend_resolution",),
    "K_broken_kit": ("pc_warn_kit_gap",),
}


class Scene(object):
    """One case, read once - so a check never re-derives what another already
    measured, and every check sees the same sections the builder used."""

    def __init__(self, case):
        self.case = case
        self.geo = case["out"]
        self.report = case["report"]
        self.plan = self.report["plan"]
        self.params = case["style"].params
        self.by_id = dict((r["pc_elem_id"], r) for r in C.elements(self.geo))
        self.plan_by_id = dict((p.elem_id, p) for p in self.plan)
        self.warns = C.collect_warns(self.geo, self.report["warn_names"])
        self.tracks = cases.P.analyse(case["curve"], self.params)
        self.kit = cases.K.read(case["kit"])[0]
        self.track_of = dict((str(t["curve"].curve_id), t)
                             for t in self.tracks)
        self.section_of = dict(
            ((str(t["curve"].curve_id), s.index), s)
            for t in self.tracks for s in t["sections"])


def run_case(name, case):
    try:
        scene = Scene(case)
    except Exception as exc:
        return [C.Result("scene", False, None, "%s: %s"
                         % (type(exc).__name__, str(exc)[:200]))]
    out = [
        C.element_count(scene),
        C.unique_elem_ids(scene),
        C.output_schema(scene),
        C.sampler_matches_kernel(scene),
        C.section_coverage(scene),
        C.exact_fill(scene),
        C.no_gaps_or_overlaps(scene),
        C.stepped_riser(scene),
        C.plumb_vertical(scene),
        C.flat_stepped(scene),
        C.bank_adaptive(scene, require_bank=(name == "E_hill_adaptive")),
        C.slice_caps_closed(scene),
        C.axis_follows_curve(scene),
        C.cross_section_width(scene),
        C.module_fidelity(scene),
        C.rigid_never_deformed(scene),
        C.deformed_flag_matches_geometry(scene),
        C.instancing_split(scene),
        C.horizontal_spacing(scene),
        C.warnings(scene, EXPECTED_WARNS.get(name, ())),
        C.determinism(scene, cases.rebuild),
        C.geometry_digest(scene),
    ]
    if name in ("C_tile_slice", "H_tile_slope_free", "I_tile_slope_fixed"):
        out.append(C.cap_tagged(scene, expect=1))
    if name == "D_marker_gate":
        out.append(C.marker_offset(scene, 7, (10.0, 0.0, 0.0)))
    # D26's two halves, derived from the grade rather than copied off a run:
    # slope fixing ON keeps the gate's own 1.60 m when measured horizontally,
    # OFF measures that width along the path's angle instead.
    if name == "I_tile_slope_fixed":
        out.append(C.horizontal_span_is(scene, cases.GATE_LENGTH))
    if name == "H_tile_slope_free":
        out.append(C.horizontal_span_is(
            scene, cases.GATE_LENGTH / math.hypot(1.0, cases.HILL_GRADE)))
    # Pinned exactly, not as a range: the broken kit carries one distinct
    # fault per warning (see cases.broken_kit), so a moved count means the
    # validator gained or lost a detector, which is exactly what should show.
    out.append(C.kit_validation(scene, 9, 9) if name == "K_broken_kit"
               else C.kit_validation(scene, 0, 0))
    return out


def main():
    update = "--update-baseline" in sys.argv
    json_out = None
    if "--json" in sys.argv:
        json_out = sys.argv[sys.argv.index("--json") + 1]

    built = cases.build_all()
    results, failures = {}, 0
    for name in sorted(built):
        res = run_case(name, built[name])
        results[name] = [r.as_dict() for r in res]
        print("\n=== %s ===" % name)
        for r in res:
            print("  %r" % r)
            if not r.ok and not r.skipped:
                failures += 1

    base = {}
    if os.path.exists(BASELINE):
        with open(BASELINE) as fh:
            base = json.load(fh)

    moved = []
    for case, rows in results.items():
        prev = dict((d["name"], d) for d in base.get(case, []))
        for d in rows:
            old = prev.get(d["name"])
            if old is not None and old["value"] != d["value"]:
                moved.append("%s/%s: %s -> %s"
                             % (case, d["name"], old["value"], d["value"]))
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
    sys.exit(1 if failures and not update else 0)


if __name__ == "__main__":
    main()
