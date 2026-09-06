"""Focused M5.4c check against the shipped assets; run with hython.

The shallow-Y keeps five streets and exercises the capped gore at 8/6/4/2
degrees. Assert the remaining road's width floor without rounding. This does
not certify corner appearance, coplanar overlap, or general two-junction roads.
No HIP or baseline is written. Removing the cap margin must fail at 6 and 2.
"""

import json

import cases
import checks
import dump_trims


def main():
    cases.install_hdas()
    parent, built = cases.build_all()
    case = built["R_shallow_y_12_subfloor"]
    failures = 0
    try:
        for angle in (12, 8, 6, 4, 2):
            case["input"].parm("python").set(cases._DRAW_SNIPPET.replace(
                repr(cases.DRAWN_STREETS),
                repr(cases._shallow_y(angle, 300.0, 200.0))))
            case["city"].cook(force=True)
            data = dump_trims.dump_case(case)
            margins = [e["length"] - e["trim_start"] - e["trim_end"]
                       - e["width"] for e in data["edges"]]
            missing = checks.every_mouth_has_a_road(
                cases.inner(case, "solve").geometry(),
                cases.inner(case, "trim").geometry())
            errors = [n.path() for n in parent.allSubChildren() if n.errors()]
            ok = (len(margins) == 5 and min(margins) >= 0.0
                  and missing.ok and not missing.skipped and not errors)
            failures += not ok
            print(json.dumps({"angle_degrees": angle, "ok": ok,
                              "edges": len(margins),
                              "min_standing_above_width_m": min(margins) if margins else None,
                              "missing_mouths": missing.value,
                              "cook_errors": errors}), flush=True)
    finally:
        parent.destroy()
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
