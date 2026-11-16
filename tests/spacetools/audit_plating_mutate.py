"""AUDIT: mutations of things the author's checks do not read, run against the author's full suite.
GREEN = the suite cannot see that bug (unfailable area).
hython tests/spacetools/audit_plating_mutate.py"""
import os, sys, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import run_plating_checks as R
from run_plating_checks import sub


def bypass(*names):
    return lambda n: [n.node(c).bypass(True) for c in names]


PL, GR = "pf_plating_generator", "pf_greeble_scatter"
MUTS = [
    ("rivets never added", PL, lambda n: n.node("rivets_on").parm("input").setExpression("0")),
    ("rim+corner bevels bypassed", PL, bypass("rim_bevel", "corner_bevel")),
    ("taper ignored", PL, lambda n: n.node("raise").parm("inset").setExpression("0")),
    ("random colour never applied", PL, lambda n: n.node("color_on").parm("input").setExpression("0")),
    ("pf_plate_side group = top", PL, lambda n: sub(n, "finalize", 'setprimgroup(0,"pf_plate_side",@primnum, pt==2,"set");', 'setprimgroup(0,"pf_plate_side",@primnum, pt==1,"set");')),
    ("pf_plate_bottom group dropped", PL, lambda n: sub(n, "finalize", 'setprimgroup(0,"pf_plate_bottom",@primnum, pt==4,"set");', '')),
    ("pf_plate_area x2", PL, lambda n: sub(n, "finalize", 'f@pf_plate_area = point(0,"_a",pp);', 'f@pf_plate_area = 2*point(0,"_a",pp);')),
    ("greeble pf_host off by one", GR, lambda n: sub(n, "place", 'setpointattrib(0, "pf_host", pt, p, "set");', 'setpointattrib(0, "pf_host", pt, p+1, "set");')),
    ("greeble kit filter ignores kit choice", GR, lambda n: sub(n, "kit_filter", 'k != "all" && s@pf_kit_set != k', '0')),
    ("greeble keep_surface switch stuck off", GR, lambda n: n.node("keep_surface").parm("input").setExpression("0")),
    ("greeble random_color never", GR, lambda n: n.node("color_on").parm("input").setExpression("0")),
]


def main():
    for name, typ, fn in MUTS:
        R.MUT.clear(); R.MUT[typ] = fn
        try:
            n = R.run_all()
        except Exception as e:
            n = -1; print("driver error", name, repr(e)[:200])
        print("AUDIT-MUTATION %-42s -> %s" % (name, "RED" if n > 0 else ("DRIVER ERROR" if n < 0 else "GREEN = UNFAILABLE")), flush=True)
    R.MUT.clear()


if __name__ == "__main__":
    main()
