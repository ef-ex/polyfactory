"""polyChain 4.5 SURFACE CONFORM - input 4, the drape onto a surface.

4.5 in full is two sentences: "Ray-project placements along -Z (axis parm)
onto the surface; per-module optional Y-tilt to the surface normal (camber).
Composes with Z-modes exactly as RailClone documents (adaptive/vertical deform
to the surface, stepped sits on it)."

THE WHOLE STAGE IS A SAMPLER, AND THAT IS THE DESIGN DECISION (D54).
Nothing here knows what a module is. `ConformPath` wraps `place.Path` and
answers the same two questions - where is metre `s`, and which way is the
curve pointing there - with the answer dropped onto the surface. Every
consumer downstream is already written against that interface, so the three
Z-modes compose with the conform WITHOUT A SINGLE NEW BRANCH in `place._frame`
or `_deform_positions`:

  * `adaptive` builds its frame from the tangent, and the conformed tangent
    follows the surface, so an adaptive rail BANKS onto it and its chord
    stretches over the drape;
  * `vertical` is yaw-only with each point re-read at its own station, and the
    stations are conformed, so a picket's FOOT follows the surface while the
    picket stays plumb;
  * `stepped` is yaw-only at ONE elevation - the piece's own start - so a
    stepped post SITS on the surface, flat, exactly as RailClone documents.

The fit itself is untouched: `decompose` and `plan` still run on the SPLINE's
own arc length, because the spline is what the artist laid out and the
projection is what the terrain does to it. This is also why a conformed run
does not need a second solve.

DECISIONS TAKEN HERE (recorded in polychain.md 10):

  D51 The axis is a DIRECTION VECTOR parm, `Params.conform_axis`, defaulting
      to (0, -1, 0). 4.5 says "-Z" because RailClone is a 3ds Max plugin and
      Max is Z-up; Houdini is Y-up, so the spec's -Z is -Y here - the same
      translation D20 already makes for the module frame.
  D52 The ray is cast from BEYOND the surface on the far side of the axis and
      takes the FIRST hit, and FACING IS IGNORED for the hit itself: a terrain
      whose normals are flipped (or a closed solid seen from inside) still
      conforms, because warn-never-block does not stop at the artist's
      winding. What facing DOES decide is the camber normal, which is flipped
      to oppose the axis before anything is tilted by it - so a back-facing
      polygon cannot roll a module upside down. Measured on 22.0.398:
      `hou.Geometry.intersect` hits a reversed grid happily and hands back the
      polygon's own normal, unflipped.
  D53 A MISS KEEPS THE UNPROJECTED POSITION and says `pc_warn_conform_miss` on
      the element. That covers all three ways to miss - a hole in the surface,
      a run that leaves its edge, and no surface under that stretch at all -
      with one behaviour: the fence carries on at spline elevation and the
      warning says where it stopped being draped. Dropping the piece, or
      clamping it to the nearest edge, both invent geometry the artist did not
      author.
  D55 CAMBER TILTS `adaptive` PIECES ONLY. Tilting a `vertical` or `stepped`
      piece to the surface normal contradicts the mode's own definition - a
      picket that leans with the camber is not plumb - so a tilt request on a
      yaw-only module is ignored, with no warning, exactly as D27 degrades
      `vertical` to `stepped` on a rigid module. The switch is
      `Params.conform_tilt` with a per-module `pc_tilt` override (-1 = the
      style decides), which is D6's three-state pattern reused.
  D56 A COARSE SURFACE IS NOT A NEW WARNING. A piece whose own stations cannot
      follow the facets under it is exactly D25's condition measured against
      the conformed path, so `_bend_deviation` already reports it as
      `pc_warn_bend_resolution` - the same number, the same name, no second
      detector to keep in step.
"""

import math

import hou

from . import EPS

HIT_PRIM = "pcHitPrim"          # the verb's own hit-primitive attribute


def _axis_aligned(a):
    """Is `a` EXACTLY a coordinate axis (+/-X, +/-Y, +/-Z)?

    D111: this is the condition under which the batched `ray` answer is
    bit-identical to `Surface.drop`, and it is asserted rather than assumed -
    see `drop_many`.
    """
    return sorted(abs(c) for c in a) == [0.0, 0.0, 1.0]


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _len(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _unit(v, fallback=(0.0, 1.0, 0.0)):
    n = _len(v)
    return fallback if n < EPS else (v[0] / n, v[1] / n, v[2] / n)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def _probe_s(sa, sb, n, fracs=None, interior=False):
    """Where to sample [sa, sb] - the piece's own stations when it has them.

    D71: `fracs` are the module's station positions as fractions of its span,
    so the two probes below sample exactly what `_deform_positions` will. The
    even fallback is for a caller that has no module (and for the ends, which
    the stations already carry). `interior` drops the two ends, which is what
    a chord-deviation measure wants and a hit test does not.
    """
    if fracs:
        vals = sorted(set(min(max(float(f), 0.0), 1.0) for f in fracs))
    else:
        n = max(int(n), 2)
        vals = [i / float(n - 1) for i in range(n)]
    if interior:
        vals = [f for f in vals if 1e-9 < f < 1.0 - 1e-9]
    return [sa + (sb - sa) * f for f in vals]


class Surface(object):
    """Input 4, as one question: where does a point land when it is dropped?

    THE CAST STARTS AT THE POINT AND LOOKS BOTH WAYS ALONG THE AXIS, and the
    NEAREST hit wins (D70). The surface may therefore sit above the spline as
    well as below it (a fence in a valley, a road under a bridge deck), which
    is what the first version was reaching for - but it reached for it by
    starting the ray beyond the far side of the surface and taking the FIRST
    hit, which is not "nearest", it is "topmost". Measured: a ground sheet at
    y = -2 under a run with a bridge-deck sheet at y = +2 over part of it put
    six of ten pieces ON TOP OF THE DECK, a 4 m jump onto the wrong surface
    with two 3.9 m cliff pieces at its edges and no warning anywhere.

    THE REACH IS PER POINT, NOT PER SURFACE (D70). It used to be twice the
    surface's own bbox diagonal, which says nothing about how far away the
    query is: a 5 x 5 m prop under a spline 30 m up reported a MISS, and the
    same prop under the same spline 10 m up hit - the drape flipping on
    standoff distance alone, stamping `pc_warn_conform_miss` (whose meaning is
    "there is a hole or an edge here") on a run with the surface directly
    beneath it. Every surface point lies within `radius` of the bbox centre,
    so `|p - centre| + radius` is exactly the distance that cannot miss one,
    and it is still derived rather than a magic number.

    ⚠️ `intersect`'s defaults are wrong for metric metres: `tolerance = 0.01`
    means a centimetre of slop on a suite that asserts 1e-4 m, and
    `min_hit = 0.01` refuses a hit within a centimetre of the origin. Both are
    passed explicitly. Measured on 22.0.398: at `tolerance = 1e-6` a 25 %
    ramp reports y = 0.500000 where the analytic answer is 0.5.
    """

    def __init__(self, geo, axis=(0.0, -1.0, 0.0)):
        # `intrinsicValue`, not `len(geo.prims())`: P5R cut three of these
        # and missed this one, which is the worst of the four because it
        # runs ONCE PER CURVE on the SURFACE. On 300 conformed streets over
        # a 7 712-prim terrain it built 300 tuples of 7 712 `hou.Prim`
        # wrappers - 0.530 s of a 3.46 s row, 15 %, the largest single entry
        # in that profile - to ask whether the geometry is empty.
        self.geo = geo if (geo is not None
                           and geo.intrinsicValue("primitivecount")) else None
        self.axis = _unit(axis, (0.0, -1.0, 0.0))
        self.centre = (0.0, 0.0, 0.0)
        self.radius = 1.0
        if self.geo is not None:
            bb = self.geo.boundingBox()
            c, size = bb.center(), bb.sizevec()
            self.centre = (c[0], c[1], c[2])
            self.radius = max(0.5 * _len((size[0], size[1], size[2])), 1e-6)
        self._pos = hou.Vector3()
        self._nrm = hou.Vector3()
        self._uvw = hou.Vector3()
        # D111's gate, decided once. A tilted axis is served by the per-query
        # path alone, because the batch cannot answer it to the same number.
        self.batchable = _axis_aligned(self.axis)

    @property
    def active(self):
        return self.geo is not None

    def _cast(self, p, d, far):
        """(position, normal, distance) of the first hit, or None."""
        if far <= 0.0:
            return None
        n = self.geo.intersect(hou.Vector3(*p), hou.Vector3(*d), self._pos,
                               self._nrm, self._uvw, min_hit=0.0, max_hit=far,
                               tolerance=1e-6)
        if n < 0:
            return None
        pos = (self._pos[0], self._pos[1], self._pos[2])
        nrm = (self._nrm[0], self._nrm[1], self._nrm[2])
        return (pos, nrm, _len(_sub(pos, p)))

    def drop_many(self, pts):
        """The same question as `drop`, asked for every point in ONE `ray`.

        11.2 P5. `drop` is two `hou.Geometry.intersect` calls plus four
        `hou.Vector3` constructions per query - 5.5 us, and 39-49 % of the
        wall clock of every conformed row on this build (measured post-port:
        the 2 km fence 0.383 s of which 0.187 s is 34 002 drops; 300 conformed
        streets 4.22 s of which 1.66 s is 306 600). The `ray` verb answers
        34 002 of them in 0.0018 s.

        ⚠️ IT IS THE SAME ANSWER, NOT A CLOSE ONE, AND THAT WAS MEASURED
        BEFORE THIS WAS WRITTEN. Over eight adversarial surfaces - D70's
        bridge deck (ground y=-2 under a deck y=+2), an EXACT tie between two
        sheets at +/-2, D52's reversed winding, D53's hole and edge, two
        coincident sheets, a query from BELOW, the camber cross-fall and the
        two-facet tent - the verb and `hou.Geometry.intersect` agree to
        **0.000e+00 m on every point, with 0 hit-flag mismatches and 0
        difference in the normal after D52's flip**, ties included (both take
        the down-axis sheet). The verb's parms say the same three things this
        class says in Python: `reverserays=bidirectional` +
        `bidirectionalresult=closest` is "look both ways, nearest wins"
        (D70), `rtolerance` is `intersect`'s `tolerance`, and `maxraydistcheck
        =0` is the per-point reach - unlimited is equivalent because every
        surface point lies within `radius` of the centre, so nothing can be
        further than the `far` the Python path computes.

        ⚠️ THE ONE PLACE THEY DIVERGE IS STORAGE, AND IT IS THE WHOLE DESIGN
        OF THIS METHOD (D111). The verb takes its ray origins from a point
        cloud and writes its answer back into one, so both ends of it are
        float32; `intersect` is handed a `hou.Vector3`, which is DOUBLE
        (probed: a Vector3 round-trips 2000.1234567890123 exactly). Two
        readings of that answer are available and they are NOT equally good:

          * the hit POSITION `P`, which the verb writes as
            `float32(origin + dir * dist)` - one rounding at the magnitude of
            a WORLD COORDINATE;
          * the hit DISTANCE `dist`, which is the same number measured from
            the query - one rounding at the magnitude of a DROP.

        A drop is a translation along `axis` by construction, so `q + a*dist`
        reconstructs the whole answer from the second. Measured on 22.0.398
        against `Surface.drop`, over 60 queries on an irrational-slope ramp:

        | reading | ramp at x < 24 | the same ramp at x = 20 000 |
        |---|---|---|
        | position | 2.384e-07 m | 6.104e-05 m |
        | **distance** | **0.0** | **0.0** |

        ⚠️ AND THE FIRST COLUMN IS WHY THE FIXTURES COULD NOT SEE IT. Read off
        the POSITION, this is bit-identical only when the true answer happens
        to be exactly representable in float32 - which every committed
        conform case is, because their surfaces are `y = 0.25x` and their
        stations are multiples of 0.25 m. `conform_parity` read 0.0 as a
        property of the SCENES; read off the distance it is a property of the
        CODE, and `ray_verb_semantics`' `dirty_ramp` and `dirty_ramp_20km`
        trials are the two that tell those apart.

        ⚠️ AND THE AXIS MUST BE A COORDINATE AXIS, WHICH IS ASSERTED, NOT
        ASSUMED. `Params.conform_axis` is a free direction vector (D51). On a
        TILTED axis the float32 ray origin no longer lies on the double ray,
        the divergence is ALONG the ray, and the reconstruction cannot remove
        it: measured 1.9e-06 m on the same ramp and 1.5e-05 m at 20 km with
        axis (0.2, -1, 0.13), against 0.0 for every coordinate axis. So
        `batchable` gates the batch off there and the per-query path - the
        reference - serves that configuration alone. Rounding the axis to
        float32 first was tried and does not help (1.9e-06 -> 1.7e-06).

        Returns `None` rather than raising if the axis is tilted, or if the
        verb is unavailable or fails - warn-never-block (D24/D34/D53): the
        caller falls back to the per-query Python path, which is slower and
        never different.
        """
        if self.geo is None or not pts or not self.batchable:
            return None
        try:
            verb = hou.sopNodeTypeCategory().nodeVerb("ray")
            if verb is None:
                return None
            src = hou.Geometry()
            src.createPoints(pts)
            res = hou.Geometry()
            verb.setParms({
                "method": 1,                  # project rays
                "dirmethod": 0,               # ...along a vector
                "dir": hou.Vector3(*self.axis),
                "reverserays": 2,             # bidirectional (D70)
                "bidirectionalresult": 0,     # ...nearest wins (D70)
                "putnml": 1,                  # the polygon normal, unflipped
                "putdist": 1,                 # ...and the drop DISTANCE
                # THE HIT FLAG IS AN INTEGER, NOT A GROUP. `newgrp` + reading
                # `grp.points()` builds one `hou.Point` WRAPPER per query -
                # the defect class P5b closed for `hou.Prim` - and it was
                # 5x the verb execution it decorated (0.0081 s against
                # 0.0016 s over 34 002 queries). `hitprim` is -1 on a miss
                # and the primitive number on a hit; measured against the
                # group over three surfaces including 40 ZERO-DISTANCE hits,
                # they disagree on 0 points. (`dist != 0` is NOT a
                # substitute: it calls every zero-distance hit a miss.)
                "useprimnumattrib": 1,
                "primnumattrib": HIT_PRIM,
                # `intersect`'s own explicit tolerance. ⚠️ NOTHING PROBED
                # HERE CAN TELL 1e-6 FROM THE NODE DEFAULT 0.01: a 1 mm hole
                # in a 1 mm grid and a query 1 mm past a sheet's edge both
                # give 0 hit-flag mismatches and 0 m at either setting, and so
                # does the whole scene suite. It is set to match the Python
                # path on principle, not because a case distinguishes them.
                "rtolerance": 1e-6,
                "maxraydistcheck": 0,         # the reach cannot cut a hit off
                "bias": 0.0,                  # `intersect`'s min_hit = 0.0
            })
            verb.execute(res, [src, self.geo])
            ps = res.pointFloatAttribValues("P")
            ds = res.pointFloatAttribValues("dist")
            hp = res.pointIntAttribValues(HIT_PRIM)
            na = res.findPointAttrib("N")
            ns = res.pointFloatAttribValues("N") if na is not None else None
            if len(ps) != 3 * len(pts) or len(ds) != len(pts) \
                    or len(hp) != len(pts):
                return None
        except Exception:                     # a verb may raise where HOM did
            return None                       # not - degrade, never block
        a = self.axis
        up = (-a[0], -a[1], -a[2])
        out = []
        for i in range(len(pts)):
            if hp[i] < 0:
                out.append((pts[i], up, False))
                continue
            nrm = up if ns is None else _unit(
                (ns[3 * i], ns[3 * i + 1], ns[3 * i + 2]), up)
            if _dot(nrm, a) > 0.0:            # D52's flip, re-added
                nrm = (-nrm[0], -nrm[1], -nrm[2])
            # `dist` is UNSIGNED - a hit found by the backward half of the
            # bidirectional cast reports the same positive number as a forward
            # one - so the sign comes from the position, which is the one
            # thing float32 is perfectly good enough for: it is wrong only
            # when the drop is within an ULP of zero, and there both signs
            # give the same point.
            q = pts[i]
            t = _dot(_sub((ps[3 * i], ps[3 * i + 1], ps[3 * i + 2]), q), a)
            d = ds[i] if t >= 0.0 else -ds[i]
            out.append(((q[0] + a[0] * d, q[1] + a[1] * d, q[2] + a[2] * d),
                        nrm, True))
        return out

    def drop(self, p):
        """(position, normal, hit). A miss returns `p` unmoved (D53).

        The normal is flipped to OPPOSE the axis (D52), so it always points
        back the way the ray came - which is "up" for the default -Y axis
        whatever the polygon's winding says.
        """
        a = self.axis
        up = (-a[0], -a[1], -a[2])
        if self.geo is None:
            return (p, up, False)
        far = _len(_sub(p, self.centre)) + self.radius
        along = self._cast(p, a, far)
        # ...then look BACK, but only as far as the hit already found: a
        # closer one up-axis is the nearer surface, anything further is not.
        # A TIE GOES DOWN-AXIS, because the stage is a DROP: a deck 2 m over
        # the spline and ground 2 m under it puts the road on the ground.
        back = self._cast(p, up, far if along is None else along[2])
        best = along
        if back is not None and (along is None or back[2] < along[2] - EPS):
            best = back
        if best is None:
            return (p, up, False)
        nrm = _unit(best[1], up)
        if _dot(nrm, a) > 0.0:
            nrm = (-nrm[0], -nrm[1], -nrm[2])
        return (best[0], nrm, True)


class ConformPath(object):
    """A `place.Path` seen through the surface. Same interface, draped answers.

    The tangent is a FINITE DIFFERENCE OF DROPPED POSITIONS rather than the
    spline's own: without it an adaptive rail over a 25 % slope stays dead
    level while its ends sit on the hill. The difference is one-sided in the
    direction the caller asked for, which keeps `place.Path.sample`'s own
    forward/backward contract at a vertex - a central difference there would
    average the two legs and point a corner piece down neither of them.
    """

    def __init__(self, path, surface, delta=1e-3):
        self.base = path
        self.surface = surface
        self.delta = float(delta)
        self.closed = path.closed
        self.total = path.total
        self.vertex_s = path.vertex_s
        self.first = path.first
        self._cache = {}
        self.batched = 0            # keys filled by the `ray` verb
        self.fallback = 0           # keys the prefetch missed, served by HOM

    # -- the prefetch ------------------------------------------------------

    def plan_keys(self, spans):
        """`[(key, s, forward)]` - the drops this curve's plan can NAME.

        `spans` is `(s0, s1, fracs)` per piece - the piece's own arclength
        span and the module's station fractions, which is exactly what
        `_probe_s` turns into the places `missed`, `deviates`, `_stepped_base`,
        `_y_varies` and `_deform_positions` all sample (D71). Each station is
        asked forward, its `delta` partner is asked with it (that is what
        `sample`'s one-sided finite difference needs), and the span's end is
        asked backward.

        ⚠️ THE GAP MIDPOINTS ARE DELIBERATELY NOT HERE, AND THAT IS A MEASURED
        REVERSAL. P5 enumerated them because `_bend_deviation` probes them -
        but `_bend_deviation` runs ONLY for a piece that will actually deform,
        and the enumeration cannot know that yet. Counted over the whole
        ladder: stations, their `delta` partners and the two end reads are
        **100 % consumed**, and the midpoints were **0 % on the 2 km fence and
        9 % on 300 conformed streets** - 47 % of every batch, and 47 % of the
        memo it fills, fetched for nothing. They fall through to `_at` instead,
        which costs a deformed piece one Python drop per gap and costs a
        packed piece nothing at all.

        ⚠️ THE PREFETCH IS ADDITIVE, AND THAT IS THE WHOLE SAFETY ARGUMENT.
        It enumerates the keys it can name from the plan; anything it misses -
        a gap midpoint, a `fix_slope` remap that is not affine over the span,
        an interior curve vertex `span_deviation` finds, a corner assembly's
        own drop - falls through to the per-query Python path in `_at`, which
        is slower and never different. Both implementations are therefore live
        in one process, which is what lets `conform_parity` prove them equal by
        asking BOTH rather than by diffing two runs (11.3 rule 4).
        `conform_prefetch_hit_rate` is the tripwire that stops the batch
        quietly becoming dead code - in BOTH directions since this reversal.
        """
        if not self.surface.active:
            return []
        d = self.delta
        want, seen = [], set()

        def add(s, forward):
            key = (round(float(s), 9), bool(forward))
            if key in self._cache or key in seen:
                return
            seen.add(key)
            want.append((key, s, forward))

        for (sa, sb, fracs) in spans:
            for s in _probe_s(sa, sb, 5, fracs):
                add(s, True)
                add(s + d, True)
            add(sb, False)
            add(sb - d, False)
        return want

    def prefetch(self, spans):
        """This curve's keys, on their own. `prefetch_all` is what `build`
        calls; this exists for a caller that has one curve and no build."""
        prefetch_all([(self, spans)])

    # -- the two questions -------------------------------------------------

    def _at(self, s, forward=True):
        key = (round(float(s), 9), bool(forward))
        hit = self._cache.get(key)
        if hit is None:
            self.fallback += 1
            p, t = self.base.sample(s, forward)
            hit = self.surface.drop(p) + (t,)
            self._cache[key] = hit
        return hit

    def sample(self, s, forward=True):
        pos, _n, _ok, tan = self._at(s, forward)
        d = self.delta
        other = self._at(s + d, forward)[0] if forward \
            else self._at(s - d, forward)[0]
        step = _sub(other, pos) if forward else _sub(pos, other)
        if _len(step) < EPS:
            return (pos, tan)               # a vertical drop keeps the spline
        return (pos, _unit(step, tan))

    def normal(self, s, forward=True):
        return self._at(s, forward)[1]

    def interior_vertices(self, s0, s1, tol=1e-7):
        return self.base.interior_vertices(s0, s1, tol)

    # -- what `place` needs to decide with ---------------------------------

    def missed(self, sa, sb, n=5, fracs=None):
        """Did any station across [sa, sb] fall off the surface?

        `fracs` is THE PIECE'S OWN STATIONS as fractions of its span, and
        passing them is the whole point (D71): `_deform_positions` drops every
        module station, so a hole that falls between five evenly spaced probes
        but ON a station dipped the built geometry to spline elevation with no
        warning at all. Measured: a 0.1 m hole at x = 0.70..0.80 under a 2 m
        panel whose stations are 0.25 m apart punched a 0.1875 m V-notch into
        the rail while `pc_warn_conform_miss` stayed absent - which is D53's
        contract ("the warning says where it stopped being draped") broken
        exactly where the drape stopped.
        """
        if not self.surface.active:
            return False
        for s in _probe_s(sa, sb, n, fracs):
            if not self._at(s)[2]:
                return True
        return False

    def deviates(self, sa, sb, tol, n=5, fracs=None):
        """Does the drape between `sa` and `sb` leave the straight chord?

        This is what makes a bendable piece unpack over a HILL that the spline
        itself knows nothing about: `place._needs_deform` looks for interior
        curve vertices, and a dead-straight spline over a ridge has none.
        Measured against the chord between the two conformed ends, so a piece
        on a uniform slope (whose drape IS a straight line) stays packed.

        ⚠️ AND IT IS PROBED ON THE PIECE'S OWN STATIONS (D71), because this is
        the GATE on a deform that would use exactly those. Five fixed samples
        made the gate strictly coarser than the thing it gates: a 0.3 m wide,
        0.5 m tall bump centred between them left a bendable panel PACKED as a
        straight chord with the bump 0.400 m through its bottom edge and no
        warning, while the panel's own 0.25 m stations would have resolved it.
        """
        if not self.surface.active or abs(sb - sa) <= EPS:
            return False
        a = self.sample(sa)[0]
        b = self.sample(sb, forward=False)[0]
        ab = _sub(b, a)
        n_ab = _len(ab)
        if n_ab < EPS:
            return False
        u = (ab[0] / n_ab, ab[1] / n_ab, ab[2] / n_ab)
        for s in _probe_s(sa, sb, max(int(n), 3), fracs, interior=True):
            q = _sub(self.sample(s)[0], a)
            t = _dot(q, u)
            off = _len((q[0] - u[0] * t, q[1] - u[1] * t, q[2] - u[2] * t))
            if off > tol:
                return True
        return False


def prefetch_all(items):
    """ONE `ray` execution for the WHOLE BUILD. `items` is `[(path, spans)]`.

    ⚠️ THIS IS PER BUILD AND NOT PER CURVE, AND THE DIFFERENCE IS THE SIGN OF
    THE ITEM. `ray` rebuilds its second input on every `execute`, so the batch
    carries a FIXED cost that scales with the SURFACE and not with the query
    count - measured on this build, minimum of five calls on one warm
    `Surface`: **0.34 ms at 5 022 terrain prims, 0.71 ms at 20 088, 2.25 ms at
    80 352**, against a marginal ~2 us per query. P5 paid that once per CURVE,
    which is invisible on the 2 km fence it was measured on (one curve) and is
    a LOSS on the citygen shape it was aimed at: 300 x 60 m streets read
    0.94-0.99x with the batch on, i.e. slower than not batching at all, and
    an independent reviewer measured 0.70x over an 80 352-prim terrain.
    Hoisted here the fixed cost is paid once for 300 curves instead of 300
    times, and the row is a win at every terrain size on the ladder
    (`tests/polychain/conform_bench.py`, which exists because those rows lived
    in a scratchpad and could not be re-run).

    Grouped by `Surface` identity rather than assuming one: `place.build`
    shares a single `Surface` across every curve (that is also what stops 300
    bounding-box computations of the terrain), but nothing here needs to
    depend on it.
    """
    groups = {}
    for path, spans in items:
        want = path.plan_keys(spans)
        if want:
            groups.setdefault(id(path.surface),
                              (path.surface, []))[1].append((path, want))
    for surf, members in groups.values():
        pts, index = [], []
        for path, want in members:
            for (key, s, forward) in want:
                pts.append(path.base.sample(s, forward))
                index.append((path, key))
        drops = surf.drop_many([hit[0] for hit in pts])
        if drops is None:                     # the verb declined; stay lazy
            continue
        for (path, key), (_pos, tan), got in zip(index, pts, drops):
            path._cache[key] = got + (tan,)
            path.batched += 1


def wrap(path, surface_geo, params, surface=None):
    """`path` draped on `surface_geo`, or `path` itself when there is none.

    D34 again: an UNCONNECTED input 4 is not an error, it is a fence on its
    own spline.

    `surface` lets a caller with many curves build the `Surface` ONCE and hand
    it to all of them: its constructor reads the terrain's bounding box, which
    on 300 conformed streets was 300 traversals of the same 80 352 prims.
    """
    surface = surface or Surface(surface_geo,
                                 getattr(params, "conform_axis",
                                         (0.0, -1.0, 0.0)))
    if not surface.active:
        return (path, surface)
    return (ConformPath(path, surface), surface)
