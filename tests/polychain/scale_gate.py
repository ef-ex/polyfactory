"""PC-G3 at scale, and D75's curvature budget measured across radii.

    hython tests/polychain/scale_gate.py            # the ~10k-piece ladder
    hython tests/polychain/scale_gate.py --json out.json

WHY THIS FILE EXISTS. PC-G3's numbers - packed vs deformed, points, memory,
cook time - have now been measured ad hoc in three separate cycles, each time
from a throwaway script in a scratchpad, and each time the numbers went into
the doc without the harness that produced them. Cycle 6 then found that the
headline number only held for a STRAIGHT resampled run: the same 20 km at
R = 12 km curvature cost 727 packed / 9 278 deformed / 334 735 points /
+130 MB / 18.9 s. That finding is D75, and this file is the measurement it
argued about, written down so the next cycle re-runs it instead of rebuilding
it (tests/README.md's rule).

THE LADDER. One 20 km run of 2 m BENDABLE panels, authored five ways:
  * `two_point`   - the straight line as two points. The floor.
  * `resampled`   - the same line resampled at 1 m. D69's case.
  * `arc_12000`   - R = 12 000 m, resampled at 1 m. 4.2e-05 m of sagitta per
                    2 m span, which is BELOW `over_unpacked`'s own 1e-4 m
                    tolerance, so unpacking it is measurably pointless.
  * `arc_2000`    - 2.5e-04 m. Still an order of magnitude under `bend_tol`.
  * `arc_80`      - 6.2e-03 m, just inside the budget: the last radius that
                    stays packed at the default tolerance.
  * `arc_10`      - 5.0e-02 m, five times the budget. This one MUST unpack,
                    and it is what keeps the budget from being vacuous.

Memory is RSS delta around the build, read through `hou.hmemory` (Houdini's
own counter; no psutil in hython).
"""

import ctypes
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cases                                                     # noqa: E402
import hou                                                       # noqa: E402
from polyfactory.polychain import Params, Rule, Style            # noqa: E402
from polyfactory.polychain import kit as K                       # noqa: E402
from polyfactory.polychain import place as P                     # noqa: E402

LENGTH = 20000.0        # metres of run - PC-G3's own 20 km
SPACING = 1.0           # metres between authored vertices


class _PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32)]         + [(n, ctypes.c_size_t) for n in
           ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


def _rss_mb():
    """Working-set MB of THIS hython. `hou` exposes no memory counter (there
    is no `hou.hmemory` on 22.0.398) and hython ships no psutil, so this is
    the OS's own number through `kernel32`. The argtypes are load-bearing: a
    HANDLE truncated to a 32-bit int makes the call fail and return 0."""
    if os.name != "nt":
        return float("nan")
    k = ctypes.WinDLL("kernel32")
    k.GetCurrentProcess.restype = ctypes.c_void_p
    fn = k.K32GetProcessMemoryInfo
    fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMC), ctypes.c_uint32]
    c = _PMC()
    c.cb = ctypes.sizeof(_PMC)
    if not fn(k.GetCurrentProcess(), ctypes.byref(c), c.cb):
        return float("nan")
    return c.WorkingSetSize / (1024.0 * 1024.0)


def _curve(kind, radius):
    geo = hou.Geometry()
    if kind == "two_point":
        pts = [(0.0, 0.0, 0.0), (LENGTH, 0.0, 0.0)]
    elif radius is None:
        n = int(LENGTH / SPACING)
        pts = [(i * SPACING, 0.0, 0.0) for i in range(n + 1)]
    else:
        n = int(LENGTH / SPACING)
        pts = []
        for i in range(n + 1):
            a = (i * SPACING) / radius
            pts.append((radius * math.sin(a), 0.0,
                        radius * (1.0 - math.cos(a))))
    cases.polyline(geo, pts, curve_id=kind)
    return geo


def _run(kind, radius, kit_geo, style):
    geo = _curve(kind, radius)
    before = _rss_mb()
    t0 = time.time()
    out, report = P.build(geo, kit_geo, style)
    dt = time.time() - t0
    row = {
        "case": kind,
        "radius_m": radius,
        "sagitta_m": (None if radius is None
                      else round(4.0 / (8.0 * radius), 9)),
        "packed": report["packed"],
        "deformed": report["deformed"],
        "points": len(out.iterPoints()),
        "geometryids": len(set(
            p.intrinsicValue("geometryid") for p in out.prims()
            if p.type() == hou.primType.PackedGeometry)),
        "seconds": round(dt, 3),
        "rss_delta_mb": round(_rss_mb() - before, 1),
    }
    return row


def main():
    kit_geo = K.starter_kit()
    style = Style("scale", 1, 3, rules=[Rule("default", "first", ["panel"])],
                  params=Params(fill="adaptive"))
    ladder = (("two_point", None), ("resampled", None), ("arc_12000", 12000.0),
              ("arc_2000", 2000.0), ("arc_80", 80.0), ("arc_10", 10.0))
    rows = []
    hdr = ("case", "sagitta_m", "packed", "deformed", "points", "geometryids",
           "seconds", "rss_delta_mb")
    print("%-12s %10s %8s %9s %9s %5s %8s %8s"
          % ("case", "sagitta", "packed", "deformed", "points", "gids",
             "seconds", "dRSS MB"))
    for kind, radius in ladder:
        row = _run(kind, radius, kit_geo, style)
        rows.append(row)
        print("%-12s %10s %8d %9d %9d %5d %8.3f %8.1f"
              % (row["case"],
                 "-" if row["sagitta_m"] is None else "%.2e" % row["sagitta_m"],
                 row["packed"], row["deformed"], row["points"],
                 row["geometryids"], row["seconds"], row["rss_delta_mb"]))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as fh:
            json.dump(rows, fh, indent=2, sort_keys=True)
    # The gate, asserted rather than merely printed: every radius inside the
    # budget must be 100 % packed and the one outside it must be 0 % packed.
    bad = []
    for row in rows:
        sag = row["sagitta_m"]
        total = row["packed"] + row["deformed"]
        if sag is None or sag <= 0.01:
            if row["packed"] != total:
                bad.append("%s: %d of %d packed" % (row["case"], row["packed"],
                                                    total))
        elif row["packed"]:
            bad.append("%s: %d packed, expected 0" % (row["case"],
                                                      row["packed"]))
    for b in bad:
        print("FAIL " + b)
    print("\n%d failing rows" % len(bad))
    sys.exit(1 if bad else 0)
    assert hdr


if __name__ == "__main__":
    main()
