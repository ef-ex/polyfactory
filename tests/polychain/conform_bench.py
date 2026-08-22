"""The CONFORMED ladder: what a drape costs, as a function of the two things
that decide it.

    hython tests/polychain/conform_bench.py
    hython tests/polychain/conform_bench.py --reps 5 --json out.json
    hython tests/polychain/conform_bench.py --ab          # prefetch ON vs OFF

WHY THIS FILE EXISTS. 11.8's P5, P5b and P6 headline numbers were all measured
on rows called `fence_2km`, `streets_300c`, `hill_2km_adaptive` and `arc_10`
that existed only in a scratchpad - `grep` over the repo found none of them.
An independent reviewer had to rebuild them to check P5, built them slightly
differently, and THE SIGN OF P5 FLIPPED: 1.40x on one long curve, 0.70x on 300
short ones over an 80 352-prim terrain. That is the failure `scale_gate.py`
was written to stop, one section of the doc later.

THE TWO VARIABLES, because a single row cannot decide this item:

  * the terrain's PRIM COUNT. `ray` rebuilds its second input on every
    `execute`, so the batch carries a FIXED per-execution cost that scales
    with the SURFACE and not with the query count. Measured on this build:
    0.34 ms at 5 022 prims, 0.71 ms at 20 088, 2.25 ms at 80 352, against a
    marginal ~2 us per query. One execution per BUILD is therefore a different
    item from one per CURVE, and the row shape is what tells them apart.
  * the terrain's ROUGHNESS, which sets the packed/deformed split. 11.8's P6
    says "the citygen street case is 100 % DEFORMED the moment a terrain is
    connected"; that is true of ONE rough terrain. What actually decides it is
    how much the surface curves WITHIN a 2 m piece, so a smooth 20 m-cell
    heightfield leaves the same run almost entirely packed.

Memory is the PEAK working set of the process (kernel32, the same counter
`scale_gate.py` reads), because P5R's rule 4 says the memory column is part of
the measurement and P5 shipped without one.
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
from polyfactory.polychain import conform as CONFORM             # noqa: E402
from polyfactory.polychain import kit as K                       # noqa: E402
from polyfactory.polychain import place as P                     # noqa: E402


class _PMC(ctypes.Structure):
    _fields_ = ([("cb", ctypes.c_uint32), ("PageFaultCount", ctypes.c_uint32)]
                + [(n, ctypes.c_size_t) for n in
                   ("PeakWorkingSetSize", "WorkingSetSize",
                    "QuotaPeakPagedPoolUsage", "QuotaPagedPoolUsage",
                    "QuotaPeakNonPagedPoolUsage", "QuotaNonPagedPoolUsage",
                    "PagefileUsage", "PeakPagefileUsage")])


def mem_mb():
    """(working set, PEAK working set) MB of this hython, through kernel32 -
    `scale_gate.py`'s own instrument. There is no `hou.hmemory` on 22.0.398
    and hython ships no psutil."""
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


# --- the inputs -------------------------------------------------------------

def terrain(cell, amp, wave, x0=-20.0, x1=640.0, z0=-20.0, z1=340.0):
    """A quad heightfield, `cell` metres per quad, `y = amp*sin*sin` at `wave`
    metres per full wave. `cell` sets the PRIM COUNT and `amp`/`wave` set how
    much the surface curves inside a 2 m piece, i.e. the deformed fraction."""
    geo = hou.Geometry()
    nx = int(round((x1 - x0) / cell))
    nz = int(round((z1 - z0) / cell))
    k = 2.0 * math.pi / wave
    pts = {}
    for i in range(nx + 1):
        x = x0 + cell * i
        for j in range(nz + 1):
            z = z0 + cell * j
            pt = geo.createPoint()
            pt.setPosition((x, amp * math.sin(k * x) * math.sin(k * z), z))
            pts[(i, j)] = pt
    for i in range(nx):
        for j in range(nz):
            poly = geo.createPolygon()
            for pt in (pts[(i, j)], pts[(i, j + 1)],
                       pts[(i + 1, j + 1)], pts[(i + 1, j)]):
                poly.addVertex(pt)
    return geo


def streets(n, length):
    """`n` straight runs of `length` m - the citygen shape: MANY SHORT curves,
    which is the row a once-per-CURVE batch is worst on."""
    geo = hou.Geometry()
    per = max(1, int(math.sqrt(n)))
    for i in range(n):
        r, c = divmod(i, per)
        cases.polyline(geo, [(c * (length + 2.0), 40.0, r * 6.0),
                             (c * (length + 2.0) + length, 40.0, r * 6.0)],
                       curve_id="S%03d" % i)
    return geo


def one_run(length, spacing=1.0):
    """One LONG curve - the 2 km fence. The shape P5 was measured on, and the
    only one it was ever a clear win for."""
    geo = hou.Geometry()
    n = int(length / spacing)
    cases.polyline(geo, [(i * spacing, 40.0, 0.0) for i in range(n + 1)],
                   curve_id="F")
    return geo


def _style():
    return Style("bench", 1, 3, rules=[Rule("default", "first", ["panel"])],
                 params=Params(fill="adaptive", zmode="adaptive"))


# --- the ladder -------------------------------------------------------------
#
# (name, curve fn, terrain args or None, why). `cell` is metres per quad, so
# 660 x 360 m of ground is 5 022 prims at 10 m and 80 352 at 2.5 m.

LADDER = (
    ("fence_2km", lambda: one_run(2000.0), (10.0, 2.0, 60.0),
     "ONE long curve - P5's own headline row, and the shape it wins on"),
    ("streets_300", lambda: streets(300, 60.0), None,
     "the citygen shape with NO surface: the control, which must not move"),
    ("streets_300c_smooth", lambda: streets(300, 60.0), (10.0, 2.0, 120.0),
     "300 short curves, 5 022 prims, gentle - mostly PACKED"),
    ("streets_300c_mid", lambda: streets(300, 60.0), (5.0, 2.0, 60.0),
     "the same over 20 088 prims"),
    ("streets_300c_big", lambda: streets(300, 60.0), (2.5, 2.0, 60.0),
     "the same over 80 352 prims - where the per-execution cost bites"),
    ("streets_300c_rough", lambda: streets(300, 60.0), (2.5, 0.6, 8.0),
     "80 352 prims and a wave a 2 m piece cannot chord - mostly DEFORMED"),
)


def build_spied(curve_geo, surf_geo, kit_geo, style, consumed=None):
    """`P.build`, keeping the `ConformPath`s it made so the batch's own
    counters can be read off the row.

    ⚠️ `consumed` (a set, collecting the DISTINCT `(path, key)` pairs `_at` is
    actually asked for) wraps a hot method and is NOT free - it is filled on a
    separate, untimed rep. Timing a run with the spy in it would be P5R's
    rule 2 in a different costume.
    """
    made = []
    real_init = CONFORM.ConformPath.__init__
    real_at = CONFORM.ConformPath._at

    def spy(self, *a, **k):
        real_init(self, *a, **k)
        made.append(self)

    def spy_at(self, s, forward=True):
        consumed.add((id(self), round(float(s), 9), bool(forward)))
        return real_at(self, s, forward)
    CONFORM.ConformPath.__init__ = spy
    if consumed is not None:
        CONFORM.ConformPath._at = spy_at
    try:
        out, report = P.build(curve_geo, kit_geo, style, surface_geo=surf_geo)
    finally:
        CONFORM.ConformPath.__init__ = real_init
        CONFORM.ConformPath._at = real_at
    return out, report, made


def run_row(name, curve_fn, terr, kit_geo, reps, prefetch_on=True):
    """Best-of-`reps` on one row. `prefetch_on=False` replaces the batch with
    a no-op, which is a pure A/B: the cache then fills from the per-query
    Python path and the OUTPUT IS IDENTICAL either way."""
    curve_geo = curve_fn()
    surf_geo = None if terr is None else terrain(*terr)
    style = _style()
    real = CONFORM.prefetch_all
    if not prefetch_on:
        CONFORM.prefetch_all = lambda items: None
    try:
        best = None
        for _ in range(reps):
            t0 = time.time()
            out, report, made = build_spied(curve_geo, surf_geo, kit_geo,
                                            style)
            dt = time.time() - t0
            if best is None or dt < best[0]:
                best = (dt, out, report, made)
        consumed = set()
        if terr is not None:
            build_spied(curve_geo, surf_geo, kit_geo, style, consumed)
    finally:
        CONFORM.prefetch_all = real
    dt, out, report, made = best
    _ws, peak = mem_mb()
    pieces = report["packed"] + report["deformed"]
    return {
        "row": name,
        "prefetch": bool(prefetch_on),
        "surface_prims": (0 if surf_geo is None
                          else surf_geo.intrinsicValue("primitivecount")),
        "curves": len(made),
        "packed": report["packed"],
        "deformed": report["deformed"],
        "deformed_pct": round(100.0 * report["deformed"] / max(1, pieces), 1),
        "points": out.intrinsicValue("pointcount"),
        "batched": sum(p.batched for p in made),
        "fallback": sum(p.fallback for p in made),
        "cache_keys": sum(len(p._cache) for p in made),
        # what `_at` was actually ASKED for, against what the batch filled.
        # `conform_prefetch_hit_rate` can only see the batch fetching too
        # LITTLE; this is the other direction.
        "consumed": len(consumed),
        "seconds": round(dt, 4),
        "peak_ws_mb": round(peak, 1),
    }


HEAD = ("%-22s %4s %8s %7s %7s %9s %9s %8s %9s %8s"
        % ("row", "pf", "surfprim", "curves", "def%", "batched", "consumed",
           "seconds", "cacheKeys", "peakMB"))


def fmt(r):
    return ("%-22s %4s %8d %7d %6.1f%% %9d %9d %8.4f %9d %8.1f"
            % (r["row"], "on" if r["prefetch"] else "OFF", r["surface_prims"],
               r["curves"], r["deformed_pct"], r["batched"], r["consumed"],
               r["seconds"], r["cache_keys"], r["peak_ws_mb"]))


def main():
    reps = 3
    if "--reps" in sys.argv:
        reps = int(sys.argv[sys.argv.index("--reps") + 1])
    ab = "--ab" in sys.argv
    only = None
    if "--row" in sys.argv:
        only = sys.argv[sys.argv.index("--row") + 1]
    kit_geo = K.starter_kit()
    rows = []
    print(HEAD)
    for name, curve_fn, terr, _why in LADDER:
        if only and name != only:
            continue
        got = {}
        for on in ((True, False) if ab else (True,)):
            r = run_row(name, curve_fn, terr, kit_geo, reps, on)
            got[on] = r
            rows.append(r)
            print(fmt(r))
        if ab and terr is not None:
            print("%-22s   prefetch ON/OFF = %.2fx"
                  % ("", got[False]["seconds"] / got[True]["seconds"]))
    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as fh:
            json.dump(rows, fh, indent=2, sort_keys=True)


if __name__ == "__main__":
    main()
