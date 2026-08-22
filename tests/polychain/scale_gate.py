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
  * `arc_80`      - 6.2e-03 m of SPINE sagitta, just inside the budget.
  * `arc_10`      - 5.0e-02 m, five times the budget. This one MUST unpack,
                    and it is what keeps the budget from being vacuous.

D97 - AND THE LADDER IS RUN TWICE, ONCE PER Z-MODE, BECAUSE THE BUDGET IS NOT
THE SAGITTA ANY MORE. The starter kit's `panel` carries `pc_zmode = vertical`,
and a yaw-only mode measures the curvature budget on the module's Z reach only
(`_needs_deform` passes `proto.rz` = 0.03 m) - so every row above was measured
with D87's off-spine term switched almost all the way off, and the pass/fail
rule below was the SPINE formula D87 replaced. Under `adaptive`, where the
panel's full 0.90 m height rides the frame, R = 80 m genuinely moves the top
edge 0.0225 m - 2.25x `bend_tol` - and 10 000 pieces correctly unpack:
measured 360 000 points, 11.1 s, +139 MB against 10 000 points / 0.66 s
packed. That is D87 working, not a regression, but it is the number PC-G3's
row has to state. So each row now carries its OWN expectation with the reason
on the line, instead of deriving one from a formula the kernel stopped using.

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


def _run(kind, radius, kit_geo, style, zmode=""):
    geo = _curve(kind, radius)
    before = _rss_mb()
    t0 = time.time()
    out, report = P.build(geo, kit_geo, style)
    dt = time.time() - t0
    row = {
        "case": kind,
        "zmode": zmode or "kit",
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


# (kind, radius, zmode, expect_all_packed, why). `zmode=""` is the kit's own
# value - `vertical` for the starter panel, so its off-spine reach is
# `rz` = 0.03 m. `adaptive` rolls the panel's full 0.90 m height with the
# frame, which is what D87 measures and what moves the boundary.
LADDER = (
    ("two_point", None, "", True, "the floor: a straight line, two points"),
    ("resampled", None, "", True, "D69 - 20 011 vertices, still no movement"),
    ("arc_12000", 12000.0, "", True, "4.2e-05 m, under `over_unpacked` itself"),
    ("arc_2000", 2000.0, "", True, "2.5e-04 m, 40x under `bend_tol`"),
    ("arc_80", 80.0, "", True, "6.2e-03 m of spine, and rz = 0.03 m of roll"),
    ("arc_10", 10.0, "", False, "5.0e-02 m, 5x the budget - MUST unpack"),
    # D97 - the same ladder with the panel's 0.90 m height on the frame.
    ("arc_12000", 12000.0, "adaptive", True, "0.90 m x 1.7e-04 rad = 1.5e-04 m"),
    ("arc_2000", 2000.0, "adaptive", True, "0.90 m x 1.0e-03 rad = 9.0e-04 m"),
    ("arc_80", 80.0, "adaptive", False,
     "0.90 m x 0.025 rad = 0.0225 m, 2.25x `bend_tol` - THE ROW D87 MOVED"),
)


def main():
    kit_geo = K.starter_kit()
    rows = []
    print("%-12s %9s %10s %8s %9s %9s %5s %8s %8s"
          % ("case", "zmode", "sagitta", "packed", "deformed", "points",
             "gids", "seconds", "dRSS MB"))
    for kind, radius, zmode, expect, why in LADDER:
        style = Style("scale", 1, 3,
                      rules=[Rule("default", "first", ["panel"])],
                      params=Params(fill="adaptive", zmode=zmode))
        row = _run(kind, radius, kit_geo, style, zmode)
        row["expect_all_packed"] = expect
        row["why"] = why
        rows.append(row)
        print("%-12s %9s %10s %8d %9d %9d %5d %8.3f %8.1f"
              % (row["case"], row["zmode"],
                 "-" if row["sagitta_m"] is None else "%.2e" % row["sagitta_m"],
                 row["packed"], row["deformed"], row["points"],
                 row["geometryids"], row["seconds"], row["rss_delta_mb"]))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as fh:
            json.dump(rows, fh, indent=2, sort_keys=True)
    # The gate, asserted rather than merely printed. The expectation is on the
    # LADDER's own line now: deriving it from the sagitta re-implemented the
    # measure D87 retired, so the harness agreed with a budget the kernel had
    # already stopped spending (D97).
    bad = []
    for row in rows:
        total = row["packed"] + row["deformed"]
        if row["expect_all_packed"] and row["packed"] != total:
            bad.append("%s/%s: %d of %d packed - %s"
                       % (row["case"], row["zmode"], row["packed"], total,
                          row["why"]))
        elif not row["expect_all_packed"] and row["packed"]:
            bad.append("%s/%s: %d packed, expected 0 - %s"
                       % (row["case"], row["zmode"], row["packed"], row["why"]))
    for b in bad:
        print("FAIL " + b)
    print("\n%d failing rows" % len(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
