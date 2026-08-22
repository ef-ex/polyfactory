"""What the 2D ROW STACK costs, on the two shapes that decide it.

    hython tests/polychain/facade_bench.py
    hython tests/polychain/facade_bench.py --reps 5 --json out.json

WHY THIS FILE EXISTS, and why it has exactly two shapes in it. 11.9 rule 2:
*"a per-call fixed cost is invisible on a one-call fixture"*. `ray` rebuilds
its surface input on every execution (0.34 ms at 5 022 terrain prims, 2.25 ms
at 80 352 - 11.8 P5c), so a batch taken once per CURVE looked like 1.45x on
one long fence and was 0.94x - a LOSS - on 300 short streets. Phase 2 is N
rows through the same kernel, i.e. many more calls than phase 1 ever made, so
the same trap is bigger here and the fixture that can see it is:

  ONE TOWER          40 storeys x 30 bays - one large facade, many long rows.
  MANY BUILDINGS     100 buildings x 8 storeys = 800 SHORT rows, over terrain.

and the row that matters is the SECOND one measured BOTH WAYS: 800 rows
through one `facade.build_many` call against the same 800 rows through 100
`facade.build` calls. The ratio is the whole return on D115, and if it ever
drops below 1.0 the batch has moved into the wrong loop - the fix is the loop,
not the language.

⚠️ TWO CORRECTIONS, BOTH FOUND BY AUDIT, AND THE HEADLINE MOVED (D144).

1. **The comparand was doing extra work.** The many-call half passed ONE
   shared `out` through all 100 calls, and `place._stamp_bulk` has to hand
   `setPrim*AttribValues` the whole column - so every call re-read and
   re-wrote every prim every earlier call had written. O(n^2), 51 % of that
   half's own runtime, measured 5.210 s against 2.040 s for the identical
   work once `place.build` was given a staging geometry. The recorded
   **2.95x / 3.98x was that defect, not the batch.**
2. **The terrain was too small to test the thing it was there for.** `ray`'s
   per-execution rebuild scales with the SURFACE (11.8 P5c: 0.34 ms at 5 022
   prims, 0.71 ms at 20 088, 2.25 ms at 80 352) and this fixture's ground was
   1 089 prims, so 99 saved executions were worth ~34 ms against a 4 s row.
   It is 19 881 prims now.

Measured honestly on this build: **1.14x with no terrain and 1.00x over a
19 881-prim one, at 1 `ray` execution against 100** (and 1.12x over an
80 089-prim terrain, i.e. the saving grows with the surface exactly as P5c's
per-execution numbers say it must). So the one-call rule is **insurance, not a
speed-up**: what it buys is that the conform cost is O(1) in the number of
rows instead of O(N), which is why the COUNT is the assertion
(`ray_executions_per_build == 1`) and the seconds are only the sanity check.

Memory is the process PEAK working set, the same counter `scale_gate.py` and
`conform_bench.py` read, because 11.8's own headline is that the memory column
can move the other way while the time column improves.
"""

import ctypes
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cases2d                                                   # noqa: E402
import hou                                                       # noqa: E402
from polyfactory.polychain import conform as CONFORM             # noqa: E402


class _PMC(ctypes.Structure):
    _fields_ = [("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32)]         + [(n, ctypes.c_size_t) for n in
           ("PeakWorkingSetSize", "WorkingSetSize", "QuotaPeakPagedPoolUsage",
            "QuotaPagedPoolUsage", "QuotaPeakNonPagedPoolUsage",
            "QuotaNonPagedPoolUsage", "PagefileUsage", "PeakPagefileUsage")]


def mem_mb():
    """(working set, peak working set) in MB - `scale_gate._rss_mb`'s own
    call, argtypes included: a HANDLE truncated to a 32-bit int makes the
    call fail silently and report 0.0, which is what the first version of
    this file printed."""
    if os.name != "nt":
        return (float("nan"), float("nan"))
    k = ctypes.WinDLL("kernel32")
    k.GetCurrentProcess.restype = ctypes.c_void_p
    fn = k.K32GetProcessMemoryInfo
    fn.argtypes = [ctypes.c_void_p, ctypes.POINTER(_PMC), ctypes.c_uint32]
    c = _PMC()
    c.cb = ctypes.sizeof(_PMC)
    if not fn(k.GetCurrentProcess(), ctypes.byref(c), c.cb):
        return (float("nan"), float("nan"))
    return (c.WorkingSetSize / 1048576.0, c.PeakWorkingSetSize / 1048576.0)


def spied(fn, reps):
    """(best seconds, out, report, `ray` executions). Best of `reps`, because
    a single timing on a cold cache measures the cache."""
    real = CONFORM.Surface.drop_many
    calls = [0]

    def spy(self, pts):
        calls[0] += 1
        return real(self, pts)
    CONFORM.Surface.drop_many = spy
    best = None
    try:
        for _ in range(reps):
            calls[0] = 0
            t0 = time.time()
            out, report = fn()
            dt = time.time() - t0
            if best is None or dt < best[0]:
                best = (dt, out, report, calls[0])
    finally:
        CONFORM.Surface.drop_many = real
    return best


def wrappers(fn):
    """(hou.Prim wrappers materialised, wrapper attribute writes) - 11.9 rule
    1's two counters, because "count wrappers before you reach for a new
    language" needs the number to exist."""
    real_prims = hou.Geometry.prims
    real_set = hou.Prim.setAttribValue
    got = [0, 0]

    def spy_prims(self, *a, **k):
        out = real_prims(self, *a, **k)
        got[0] += len(out)
        return out

    def spy_set(self, *a, **k):
        got[1] += 1
        return real_set(self, *a, **k)
    hou.Geometry.prims = spy_prims
    hou.Prim.setAttribValue = spy_set
    try:
        fn()
    finally:
        hou.Geometry.prims = real_prims
        hou.Prim.setAttribValue = real_set
    return tuple(got)


HEAD = ("%-26s %7s %7s %8s %8s %8s %6s %9s %9s %8s"
        % ("row", "curves", "elems", "packed", "deformed", "seconds", "ray",
           "primWrap", "setAttrib", "peakMB"))


def fmt(r):
    return ("%-26s %7d %7d %8d %8d %8.4f %6d %9d %9d %8.1f"
            % (r["row"], r["curves"], r["elements"], r["packed"],
               r["deformed"], r["seconds"], r["ray_executions"],
               r["prim_wrappers"], r["wrapper_writes"], r["peak_ws_mb"]))


def row(name, fn, reps):
    dt, out, report, rays = spied(fn, reps)
    prim_w, set_w = wrappers(fn)
    _ws, peak = mem_mb()
    return {"row": name, "seconds": round(dt, 4), "ray_executions": rays,
            "curves": report["curves"],
            "elements": report["packed"] + report["deformed"],
            "packed": report["packed"], "deformed": report["deformed"],
            "points": out.intrinsicValue("pointcount"),
            "prims": out.intrinsicValue("primitivecount"),
            "prim_wrappers": prim_w, "wrapper_writes": set_w,
            "peak_ws_mb": round(peak, 1)}


def main():
    reps = 3
    if "--reps" in sys.argv:
        reps = int(sys.argv[sys.argv.index("--reps") + 1])
    terrain = cases2d.terrain()
    rows = []
    print(HEAD)
    print("terrain: %d prims" % terrain.intrinsicValue("primitivecount"))
    for name, fn in (
            ("one_tower_40x30", lambda: cases2d.tripwire_one_tower(40, 30)),
            ("many_800rows_1call",
             lambda: cases2d.build_many_buildings(True)),
            ("many_800rows_100calls",
             lambda: cases2d.build_many_buildings(False)),
            # the O(n^2) `build(out=...)` accumulation path, kept as its own
            # row: it used to BE the comparand, which made the one-call ratio
            # an artefact of the comparand rather than a property of the batch.
            ("many_800rows_100calls_accum",
             lambda: cases2d.build_many_buildings(False, accumulate=True)),
            ("many_800rows_1call_terrain",
             lambda: cases2d.build_many_buildings(True, terrain)),
            ("many_800rows_100calls_terrain",
             lambda: cases2d.build_many_buildings(False, terrain))):
        r = row(name, fn, reps)
        rows.append(r)
        print(fmt(r))
    by = dict((r["row"], r) for r in rows)
    for label, one, many in (
            ("no terrain", "many_800rows_1call", "many_800rows_100calls"),
            ("over terrain", "many_800rows_1call_terrain",
             "many_800rows_100calls_terrain")):
        if one in by and many in by:
            print("  800 short rows, %-13s ONE call %.4f s vs %d calls "
                  "%.4f s = %.2fx   (`ray` %d vs %d)"
                  % (label, by[one]["seconds"],
                     by[many]["curves"] and 100, by[many]["seconds"],
                     by[many]["seconds"] / max(by[one]["seconds"], 1e-9),
                     by[one]["ray_executions"], by[many]["ray_executions"]))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as fh:
            json.dump(rows, fh, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
