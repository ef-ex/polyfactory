"""The loop-closure gate: sweep harness and the metrics that judge a weld.

    hython tests/citygen/closure_gate.py            # fast grid, ~50 configs
    hython tests/citygen/closure_gate.py --full     # the 470-config grid
    hython tests/citygen/closure_gate.py --table    # + per-gate sole-rejector table
    hython tests/citygen/closure_gate.py --json out.json

**This sweep has now been derived from scratch and thrown away three times.**
Each round re-measured the same things — how many welds close backwards, how
much road a closure lays down twice, whether the accepted seams leave room for
a bound — at four figures of tokens a round. It lives here so round N+1 starts
where round N finished. Do not re-derive it; extend it.

THE STRUCTURAL FACT THAT MAKES AN A/B FREE
------------------------------------------
In the trace wrangle `closeloop` is used in exactly one place:

    if (closeloop) addvertex(0, prim, firstpt);

It does not feed occupancy, the lookahead store, or anything else. So the
TRACED GEOMETRY IS IDENTICAL for every build of the gate, and any candidate
gate can be evaluated by exporting the raw inputs once and recomputing the
booleans in Python. No A/B cook, and — see the dev-loop skill — no
`updateFromNode`, which writes the definition back to its own library file and
has already destroyed one agent's "pristine" baseline copy.

The Python transcription is only worth anything if it still matches the VEX,
so `gate_matches_vex` asserts exactly that on every street in the sweep,
against the wrangle's own `closeloop` flag. If someone edits the gate in the
HDA and not here, that check fails first and loudest.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

import cases                                                    # noqa: E402

W_DEFAULT = 14.4          # close_road_width; the one number both bounds come off


# --------------------------------------------------------------- instrument
# Export the RAW inputs to every gate, not the gate booleans, plus the
# wrangle's own verdict so the transcription below can be checked against it.

_ANCHOR = 'setprimattrib(0, "src_id", prim, sprintf("trace_%d_%d_%d", pass, ix, iz));'

_RAW = '''
            setprimattrib(0, "x_np",      prim, np);
            setprimattrib(0, "x_seam",    prim, seam);
            setprimattrib(0, "x_len",     prim, tracelen);
            setprimattrib(0, "x_turn",    prim, turn);
            setprimattrib(0, "x_enddot",  prim, enddot);
            setprimattrib(0, "x_cell",    prim, cell);
            setprimattrib(0, "x_cfwd",    prim, chord_forward);
            setprimattrib(0, "x_loose",   prim, both_ends_loose);
            setprimattrib(0, "x_shipped", prim, closeloop);'''

# `rad_est` and `sagitta` used to be computed in the wrangle for the gate that
# is now gone, so they are derived here instead — same formulae, no dead code
# left in the HDA to keep them alive. They remain useful as diagnostics: the
# welds this gate refuses are all r 283-389 outer rings.


def instrument(snippet):
    if _ANCHOR not in snippet:
        raise RuntimeError("src_id anchor not found — the trace wrangle changed shape")
    if "x_seam" in snippet:
        return snippet
    return snippet.replace(_ANCHOR, _ANCHOR + _RAW, 1)


def build_trace(parent, field, name="T", domain=800.0):
    """field -> trace, with the trace wrangle instrumented.

    Only the INSTANCE is unlocked. The definition is never written and
    updateFromNode is never called.
    """
    if field == "grid":
        fn = parent.createNode("pf_citygen_field_grid", "F_" + name)
        fn.parm("angle").set(18.0)
        fn.parm("weight").set(1.0)
        fn.parm("falloff").set(3000.0)
    else:
        fn = parent.createNode("pf_citygen_field_radial", "F_" + name)
        fn.parm("weight").set(2.5)
        fn.parm("falloff").set(2000.0)
    tr = parent.createNode("pf_citygen_trace", name)
    tr.setInput(0, fn)
    tr.parm("domain").set(domain)
    tr.allowEditingOfContents()
    w = tr.node("trace")
    w.parm("snippet").set(instrument(w.parm("snippet").eval()))
    return fn, tr


# ------------------------------------------------------ the gate, in Python

GATE_ORDER = ("chord", "loop", "loose", "seam", "len", "ang", "pts", "invent")


def gates(r, road_width=W_DEFAULT, seam_cells=1.42, end_angle=60.0, min_pts=8,
          invent_widths=5.0):
    """Transcribed from the trace wrangle. Keep in step with it — the
    `gate_matches_vex` check exists to make a drift impossible to miss."""
    return {
        "chord":  bool(r["cfwd"]) or r["seam"] <= road_width,
        "loop":   abs(r["turn"]) <= 2.0 * math.pi,
        "loose":  bool(r["loose"]),
        "seam":   r["seam"] <= seam_cells * r["cell"],
        "len":    r["tracelen"] > 10.0 * r["seam"],
        "ang":    r["enddot"] >= math.cos(math.radians(end_angle)),
        "pts":    r["np"] >= min_pts,
        "invent": r["seam"] <= invent_widths * road_width,
    }


def gates_sagitta(r, road_width=W_DEFAULT, **kw):
    """The f0edcc6 build, for the before/after column only: the last gate was
    `sagitta <= 0.5 * close_road_width`."""
    g = gates(r, road_width=road_width, **kw)
    g["invent"] = r["sag"] <= 0.5 * road_width
    return g


def accepted(g):
    return all(g[k] for k in GATE_ORDER)


def sole_rejector(g):
    bad = [k for k in GATE_ORDER if not g[k]]
    return bad[0] if len(bad) == 1 else None


# ------------------------------------------------------------------ readout

def read_streets(geo, want_paths=False):
    recs = []
    for pr in geo.prims():
        sid = pr.attribValue("src_id")
        if not sid.startswith("trace_"):
            continue
        r = dict(src_id=sid,
                 np=int(pr.attribValue("x_np")),
                 seam=float(pr.attribValue("x_seam")),
                 tracelen=float(pr.attribValue("x_len")),
                 turn=float(pr.attribValue("x_turn")),
                 enddot=float(pr.attribValue("x_enddot")),
                 cell=float(pr.attribValue("x_cell")),
                 cfwd=int(pr.attribValue("x_cfwd")),
                 loose=int(pr.attribValue("x_loose")),
                 shipped=int(pr.attribValue("x_shipped")))
        r["rad"] = (r["tracelen"] / abs(r["turn"])) if abs(r["turn"]) > 1e-6 else 1e18
        r["sag"] = r["seam"] ** 2 / (8.0 * r["rad"])
        if want_paths:
            path = [(p.position()[0], p.position()[2]) for p in pr.points()]
            if len(path) > 1 and path[0] == path[-1]:
                path = path[:-1]          # drop the weld's repeated first point
            r["path"] = path
        recs.append(r)
    return recs


# --------------------------------------------------------------- geometry

def _cross(ax, az, bx, bz):
    return ax * bz - az * bx


def seg_cross(p, p2, q, q2):
    rx, rz = p2[0] - p[0], p2[1] - p[1]
    sx, sz = q2[0] - q[0], q2[1] - q[1]
    d = _cross(rx, rz, sx, sz)
    if abs(d) < 1e-12:
        return None
    t = _cross(q[0] - p[0], q[1] - p[1], sx, sz) / d
    u = _cross(q[0] - p[0], q[1] - p[1], rx, rz) / d
    if 1e-9 < t < 1 - 1e-9 and 1e-9 < u < 1 - 1e-9:
        return (t, u)
    return None


def shoelace(poly):
    a = 0.0
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % n]
        a += x1 * z2 - x2 * z1
    return 0.5 * a


def lobes(path):
    """Split the CLOSED loop at its first proper self-intersection.

    Returns (big, small, (i, j), point). A clean ring gives (area, 0.0, None,
    None); a weld that folds the loop back on itself gives a big lobe and the
    sliver face the block extractor will see. No exclusion parameter, so it
    sees a 0.5 m2 lobe as readily as a 400 m2 one.
    """
    n = len(path)
    segs = [(path[i], path[(i + 1) % n]) for i in range(n)]
    for i in range(n):
        for j in range(i + 2, n):
            if i == 0 and j == n - 1:
                continue
            hit = seg_cross(segs[i][0], segs[i][1], segs[j][0], segs[j][1])
            if hit is None:
                continue
            t = hit[0]
            X = (segs[i][0][0] + t * (segs[i][1][0] - segs[i][0][0]),
                 segs[i][0][1] + t * (segs[i][1][1] - segs[i][0][1]))
            loopA = [X] + [path[k] for k in range(i + 1, j + 1)]
            loopB = [X] + [path[k] for k in range(j + 1, n)] + \
                    [path[k] for k in range(0, i + 1)]
            aA, aB = abs(shoelace(loopA)), abs(shoelace(loopB))
            return (max(aA, aB), min(aA, aB), (i, j), X)
    return (abs(shoelace(path)), 0.0, None, None)


def pavement_deficit(path, width=W_DEFAULT, res=0.5):
    """DOUBLED PAVEMENT = w*L - area(Minkowski(closed loop, w/2)).

    THE METRIC THAT REPLACED "road under the chord". That one excluded a
    Euclidean ball of one road width around each chord end and counted what
    was left; it reported 0 m of road under any chord. The same idea with an
    ARC-LENGTH exclusion of the same 14.4 m reports 265 of 325 welds with road
    under the chord and a closest approach of 1.00 m — the opposite answer from
    the same geometry. The number was an artefact of the exclusion's shape, so
    the metric was ill-posed, not merely loose.

    This one has no exclusion and no blind scale. For any simple closed
    centreline the w-neighbourhood has area exactly w*L, because the two offset
    curves' area terms (+/- the turning integral) cancel on a closed curve. Any
    shortfall is pavement the loop lays down twice. It sees a 0.5 m2 sliver and
    a 400 m2 doubling alike.

    Rasterised, so it is O(cells x segments) — pass a coarser `res` for a big
    loop. Needs numpy; returns None without it.
    """
    try:
        import numpy as np
    except ImportError:
        return None
    n = len(path)
    ax = np.array([p[0] for p in path])
    az = np.array([p[1] for p in path])
    bx, bz = np.roll(ax, -1), np.roll(az, -1)
    L = float(np.hypot(bx - ax, bz - az).sum())
    h = width * 0.5
    gx = np.arange(ax.min() - h - res, ax.max() + h + res, res)
    gz = np.arange(az.min() - h - res, az.max() + h + res, res)
    GX, GZ = np.meshgrid(gx, gz, indexing="ij")
    px, pz = GX.ravel(), GZ.ravel()
    inside = np.zeros(GX.shape, dtype=bool)
    for k in range(n):
        dx, dz = bx[k] - ax[k], bz[k] - az[k]
        L2 = dx * dx + dz * dz
        if L2 < 1e-18:
            continue
        t = np.clip(((px - ax[k]) * dx + (pz - az[k]) * dz) / L2, 0.0, 1.0)
        d2 = (px - ax[k] - t * dx) ** 2 + (pz - az[k] - t * dz) ** 2
        inside |= (d2 < h * h).reshape(GX.shape)
    area = float(inside.sum()) * res * res
    return dict(L=L, ideal=width * L, area=area, deficit=width * L - area)


def predicted_doubling(path, seam, width=W_DEFAULT):
    """The closed form for a RETROGRADE weld, which needs no sweep at all.

    The two halves passed each other; project the end-to-start vector onto the
    start tangent and you get an `overshoot` along the road and a `lateral`
    across it, with overshoot^2 + lateral^2 = seam^2. The chord runs back over
    the overshoot and then the seam closes it, so

        doubled pavement = (overshoot + seam) * (w - lateral)

    Predicted vs rasterised on the four worst welds in the sweep:
    213.5/212.6, 203.2/208.9, 191.8/191.5, 58.8/48.0 m2.

    Maximising over overshoot^2 + lateral^2 = seam^2 <= w^2 (the floor's own
    bound) puts the worst case at lateral = 0, overshoot = seam = w:

        2 * w * w  =  414.7 m2 at w = 14.4  =  28.8 m of doubled road,

    always ONE 14.4 x 28.8 m patch at the seam, never a run along the ring.
    """
    ta = (path[1][0] - path[0][0], path[1][1] - path[0][1])
    la = math.hypot(*ta) or 1.0
    ta = (ta[0] / la, ta[1] / la)
    d = (path[-1][0] - path[0][0], path[-1][1] - path[0][1])
    overshoot = d[0] * ta[0] + d[1] * ta[1]
    lateral = abs(-d[0] * ta[1] + d[1] * ta[0])
    return max(0.0, (max(overshoot, 0.0) + seam) * max(0.0, width - lateral))


# ------------------------------------------------------------------ sweeps

# The fast grid must contain every GROUND_TRUTH config or the check that
# guards them is decoration: sep 150 is here for (150, 3) alone.
FAST = dict(seps=[40, 65, 90, 130, 150, 180, 260], steps=[2, 3, 6, 12])
FULL = dict(seps=[40, 50, 60, 70, 80, 90, 100, 110, 120, 130, 140,
                  150, 160, 180, 200, 220, 240, 260],
            steps=[2, 3, 4, 5, 6, 8, 9, 10, 12, 14, 18, 25, 30],
            lo_seps=[30, 35, 40, 45, 50, 55, 60, 65, 70],
            lo_steps=[2, 3, 4, 6, 8])

# The welds the design has committed to: refusing any of these puts two dead
# ends back on the ground, the defect class S2 and 4d rank as the worst here.
GROUND_TRUTH = ((130, 2, 31.25), (150, 3, 52.24), (90, 6, 62.32))

# The two ADVERSARIAL configs, always swept. Both need step >~ min_street_sep,
# so nobody would ship them — and both refute a claim that was recorded as
# measured, which is exactly why they are pinned here rather than left to a
# grid that happens to miss them:
#   (22, 30) trace_1_2_1  seam 8.412 retrograde at r 285 — breaks the recorded
#            "0 retrograde welds with seam >= 8 m";
#   (23, 20) trace_1_3_2  seam 7.301 retrograde, and its welded loop CROSSES
#            ITSELF at segments 0/39 for a 0.50 m2 lobe — breaks the recorded
#            "0 chord self-intersections".
ADVERSARIAL = (("radial", 22, 30), ("radial", 23, 20))

# ...and that second one is a known, tracked defect, so the simplicity check
# fails on anything OUTSIDE this set rather than being switched off.
KNOWN_SELFX = {("radial", 23, 20, "trace_1_3_2")}


def configs(full):
    g = FULL if full else FAST
    out = set(ADVERSARIAL)
    for f in ("grid", "radial"):
        for s in g["seps"]:
            for h in g["steps"]:
                out.add((f, s, h))
        for s in g.get("lo_seps", ()):
            for h in g.get("lo_steps", ()):
                out.add((f, s, h))
    return sorted(out)


def sweep(full=False, want_paths=True, progress=True):
    """Cook every config once and return the flat list of traced streets."""
    import hou
    cases.install_hdas()
    root = hou.node("/obj").createNode("geo", "closure_sweep")
    for c in root.children():
        c.destroy()
    nodes = {f: build_trace(root, f, "T_" + f) for f in ("grid", "radial")}
    cfgs = configs(full)
    rows = []
    for i, (field, sep, step) in enumerate(cfgs):
        _, tr = nodes[field]
        tr.parm("min_street_sep").set(float(sep))
        tr.parm("step").set(float(step))
        geo = tr.geometry()
        if geo is None:
            # A VEX compile error reads as geometry() == None, which as a bare
            # `continue` produced a sweep of 0 streets and a green run. Never
            # swallow it — print the wrangle's own error and stop.
            errs = tr.node("trace").errors() or tr.errors()
            raise RuntimeError("%s sep %s step %s did not cook: %s"
                               % (field, sep, step, (errs or ["(no error text)"])[0][:400]))
        recs = read_streets(geo, want_paths=want_paths)
        for r in recs:
            r.update(field=field, sep=sep, step=step)
        rows.extend(recs)
        if progress and (i + 1) % 25 == 0:
            sys.stderr.write("  %d/%d configs, %d streets\n"
                             % (i + 1, len(cfgs), len(rows)))
            sys.stderr.flush()
    return rows, len(cfgs)


# ------------------------------------------------------------------ checks

class R(object):
    def __init__(self, name, ok, value, note=""):
        self.name, self.ok, self.value, self.note = name, ok, value, note

    def __repr__(self):
        return "%-28s %s  %r%s" % (self.name, "ok  " if self.ok else "FAIL",
                                   self.value, "  # " + self.note if self.note else "")

    def as_dict(self):
        return dict(name=self.name, ok=self.ok, value=self.value, note=self.note)


def gate_matches_vex(rows):
    """The Python gate above must reproduce the wrangle's own verdict.

    Nothing else in this file is worth reading if this fails: every number it
    reports would be describing a gate the HDA does not implement.
    """
    bad = [r["src_id"] for r in rows
           if int(accepted(gates(r))) != r["shipped"]]
    return R("gate_matches_vex", not bad, len(bad),
             "" if not bad else "transcription drifted from the HDA: %s" % bad[:5])


def no_multi_lap_weld(rows):
    """A closure closes ONE loop. At sep 260 a 15.03-lap, 9,360 m spiral once
    welded shut across a 623 m circumference."""
    laps = [abs(r["turn"]) / (2 * math.pi) for r in rows if accepted(gates(r))]
    worst = max(laps) if laps else 0.0
    return R("no_multi_lap_weld", worst <= 1.0 + 1e-9, round(worst, 4),
             "laps of the worst accepted weld")


def retrograde_welds_bounded(rows, width=W_DEFAULT):
    """Every weld the magnitude floor admits against a backwards chord, and
    the closed-form pavement it doubles. Both are bounded by the floor itself:
    seam <= w, doubling <= 2*w*w."""
    retro = [r for r in rows if accepted(gates(r)) and not r["cfwd"]]
    worst_seam = max([r["seam"] for r in retro] or [0.0])
    dbl = [predicted_doubling(r["path"], r["seam"], width)
           for r in retro if r.get("path") and len(r["path"]) > 2]
    worst_dbl = max(dbl or [0.0])
    ok = worst_seam <= width + 1e-6 and worst_dbl <= 2.0 * width * width + 1e-6
    return R("retrograde_welds_bounded", ok,
             dict(n=len(retro), max_seam=round(worst_seam, 3),
                  max_doubled_m2=round(worst_dbl, 1),
                  bound_seam=width, bound_doubled_m2=round(2 * width * width, 1)),
             "floor-admitted backwards chords")


def weld_pavement_deficit(rows, width=W_DEFAULT, limit=None):
    """Rasterised doubled pavement over every accepted weld — the metric with
    no exclusion parameter. Limit defaults to the closed-form worst case."""
    if limit is None:
        limit = 2.0 * width * width
    worst, where, n = 0.0, None, 0
    for r in rows:
        if not accepted(gates(r)) or not r.get("path") or len(r["path"]) < 4:
            continue
        p = r["path"]
        span = max(max(q[0] for q in p) - min(q[0] for q in p),
                   max(q[1] for q in p) - min(q[1] for q in p))
        d = pavement_deficit(p, width, max(0.5, span / 700.0))
        if d is None:
            return R("weld_pavement_deficit", True, None, "numpy unavailable")
        n += 1
        if d["deficit"] > worst:
            worst, where = d["deficit"], "%s sep%s step%s %s" % (
                r["field"], r["sep"], r["step"], r["src_id"])
    return R("weld_pavement_deficit", worst <= limit,
             dict(n=n, max_m2=round(worst, 1), limit_m2=round(limit, 1),
                  at=where),
             "w*L - area(Minkowski(loop, w/2))")


def weld_loop_is_simple(rows):
    """A welded loop must not cross itself: the small lobe is a sliver face the
    block extractor will happily parcel up."""
    bad, known = [], []
    for r in rows:
        if not accepted(gates(r)) or not r.get("path") or len(r["path"]) < 4:
            continue
        _, small, at, _ = lobes(r["path"])
        if at is None:
            continue
        rec = dict(cfg="%s sep%s step%s %s" % (r["field"], r["sep"], r["step"],
                                               r["src_id"]),
                   lobe_m2=round(small, 2), segs=list(at),
                   seam=round(r["seam"], 3))
        key = (r["field"], r["sep"], r["step"], r["src_id"])
        (known if key in KNOWN_SELFX else bad).append(rec)
    return R("weld_loop_is_simple", not bad,
             dict(n=len(bad), known=len(known), worst=(bad or known)[:3]),
             "self-intersecting welded loops (known ones tracked, not waived)")


def ground_truth_welds(rows):
    """The three seams the design has committed to closing."""
    missing = []
    for sep, step, seam in GROUND_TRUTH:
        hit = [r for r in rows
               if r["field"] == "radial" and r["sep"] == sep and r["step"] == step
               and abs(r["seam"] - seam) < 0.02 and accepted(gates(r))]
        if not hit:
            missing.append((sep, step, seam))
    return R("ground_truth_welds", not missing,
             dict(want=len(GROUND_TRUTH), missing=missing),
             "sep/step/seam that must still weld")


def accepted_seam_distribution(rows):
    """Informational, and the reason the invented-road bound sits where it
    does: the gaps in this distribution are the room a threshold has to live
    in, and they are 6-10x wider than the 2.7% window the sagitta bound had."""
    s = sorted(r["seam"] for r in rows if accepted(gates(r)))
    if not s:
        return R("accepted_seam_distribution", True, None, "no welds")
    gaps = sorted(((s[i + 1] - s[i], s[i], s[i + 1]) for i in range(len(s) - 1)),
                  reverse=True)[:5]
    # window as a fraction of the LOWER edge: that edge is a weld that must
    # keep welding, so it is what a threshold placed in the gap has room above.
    return R("accepted_seam_distribution", True,
             dict(n=len(s), min=round(s[0], 2), median=round(s[len(s) // 2], 2),
                  max=round(s[-1], 2),
                  gaps=[dict(lo=round(a, 2), hi=round(b, 2),
                             window_pct=round(100.0 * g / a, 1)) for g, a, b in gaps]),
             "informational")


def sole_rejector_table(rows, gatefn=gates):
    """A gate is PROVEN when it is the sole rejector of at least one street —
    the same thing as "deleting it would let a weld through". Two of the eight
    have never been that, and are recorded as unproven rather than as passing."""
    tally = dict((k, 0) for k in GATE_ORDER)
    for r in rows:
        k = sole_rejector(gatefn(r))
        if k:
            tally[k] += 1
    return tally


# -------------------------------------------------------------------- main

def main():
    full = "--full" in sys.argv
    rows, ncfg = sweep(full=full)
    checks = [gate_matches_vex(rows),
              ground_truth_welds(rows),
              no_multi_lap_weld(rows),
              retrograde_welds_bounded(rows),
              weld_loop_is_simple(rows),
              weld_pavement_deficit(rows),
              accepted_seam_distribution(rows)]
    nweld = sum(1 for r in rows if accepted(gates(r)))
    print("\n=== loop-closure sweep: %d configs, %d streets, %d welds ==="
          % (ncfg, len(rows), nweld))
    for c in checks:
        print("  %r" % c)

    if "--table" in sys.argv:
        now = sole_rejector_table(rows, gates)
        was = sole_rejector_table(rows, gates_sagitta)
        print("\n  per-gate SOLE rejector (sagitta build -> invented-road build)")
        for k in GATE_ORDER:
            print("    %-8s %5d -> %5d   %s" % (k, was[k], now[k],
                  "proven" if now[k] else "UNPROVEN"))

    if "--json" in sys.argv:
        with open(sys.argv[sys.argv.index("--json") + 1], "w") as fh:
            json.dump(dict(configs=ncfg, streets=len(rows), welds=nweld,
                           checks=[c.as_dict() for c in checks],
                           sole=sole_rejector_table(rows, gates)), fh, indent=2)

    bad = [c for c in checks if not c.ok]
    print("\n%d failing" % len(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
