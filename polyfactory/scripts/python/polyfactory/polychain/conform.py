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


def _sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def _len(v):
    return math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2])


def _unit(v, fallback=(0.0, 1.0, 0.0)):
    n = _len(v)
    return fallback if n < EPS else (v[0] / n, v[1] / n, v[2] / n)


def _dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


class Surface(object):
    """Input 4, as one question: where does a point land when it is dropped?

    The cast starts `reach` metres back up the axis from the point and runs
    `2 * reach`, so the surface may sit ABOVE the spline as well as below it
    (a fence in a valley, a road under a bridge deck). `reach` comes from the
    surface's own bounding box, never from a magic number, so the same code
    works on a 3 m prop and a 3 km terrain.

    ⚠️ `intersect`'s defaults are wrong for metric metres: `tolerance = 0.01`
    means a centimetre of slop on a suite that asserts 1e-4 m, and
    `min_hit = 0.01` refuses a hit within a centimetre of the origin. Both are
    passed explicitly. Measured on 22.0.398: at `tolerance = 1e-6` a 25 %
    ramp reports y = 0.500000 where the analytic answer is 0.5.
    """

    def __init__(self, geo, axis=(0.0, -1.0, 0.0)):
        self.geo = geo if (geo is not None and len(geo.prims())) else None
        self.axis = _unit(axis, (0.0, -1.0, 0.0))
        self.reach = 1.0
        if self.geo is not None:
            bb = self.geo.boundingBox()
            size = bb.sizevec()
            self.reach = max(_len((size[0], size[1], size[2])), 1.0) * 2.0
        self._pos = hou.Vector3()
        self._nrm = hou.Vector3()
        self._uvw = hou.Vector3()
        self.hits = 0
        self.misses = 0

    @property
    def active(self):
        return self.geo is not None

    def drop(self, p):
        """(position, normal, hit). A miss returns `p` unmoved (D53).

        The normal is flipped to OPPOSE the axis (D52), so it always points
        back the way the ray came - which is "up" for the default -Y axis
        whatever the polygon's winding says.
        """
        if self.geo is None:
            return (p, (-self.axis[0], -self.axis[1], -self.axis[2]), False)
        a, r = self.axis, self.reach
        origin = hou.Vector3(p[0] - a[0] * r, p[1] - a[1] * r, p[2] - a[2] * r)
        n = self.geo.intersect(origin, hou.Vector3(*a), self._pos, self._nrm,
                               self._uvw, min_hit=0.0, max_hit=2.0 * r,
                               tolerance=1e-6)
        if n < 0:
            self.misses += 1
            return (p, (-a[0], -a[1], -a[2]), False)
        self.hits += 1
        nrm = _unit((self._nrm[0], self._nrm[1], self._nrm[2]),
                    (-a[0], -a[1], -a[2]))
        if _dot(nrm, a) > 0.0:
            nrm = (-nrm[0], -nrm[1], -nrm[2])
        return ((self._pos[0], self._pos[1], self._pos[2]), nrm, True)


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

    # -- the two questions -------------------------------------------------

    def _at(self, s, forward=True):
        key = (round(float(s), 9), bool(forward))
        hit = self._cache.get(key)
        if hit is None:
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

    def missed(self, sa, sb, n=5):
        """Did any of `n` stations across [sa, sb] fall off the surface?"""
        if not self.surface.active:
            return False
        n = max(int(n), 2)
        for i in range(n):
            s = sa + (sb - sa) * (i / float(n - 1))
            if not self._at(s)[2]:
                return True
        return False

    def deviates(self, sa, sb, tol, n=5):
        """Does the drape between `sa` and `sb` leave the straight chord?

        This is what makes a bendable piece unpack over a HILL that the spline
        itself knows nothing about: `place._needs_deform` looks for interior
        curve vertices, and a dead-straight spline over a ridge has none.
        Measured against the chord between the two conformed ends, so a piece
        on a uniform slope (whose drape IS a straight line) stays packed.
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
        n = max(int(n), 3)
        for i in range(1, n - 1):
            s = sa + (sb - sa) * (i / float(n - 1))
            q = _sub(self.sample(s)[0], a)
            t = _dot(q, u)
            off = _len((q[0] - u[0] * t, q[1] - u[1] * t, q[2] - u[2] * t))
            if off > tol:
                return True
        return False


def wrap(path, surface_geo, params):
    """`path` draped on `surface_geo`, or `path` itself when there is none.

    D34 again: an UNCONNECTED input 4 is not an error, it is a fence on its
    own spline.
    """
    surface = Surface(surface_geo, getattr(params, "conform_axis",
                                           (0.0, -1.0, 0.0)))
    if not surface.active:
        return (path, surface)
    return (ConformPath(path, surface), surface)
