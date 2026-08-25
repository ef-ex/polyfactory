"""polyChain 7.7 - `pf_polychain_slice`, the kit on-ramp. THE DECISION HALF.

Model one good facade chunk (or one fence run); get a 3.2 kit. This module
decides WHERE the cuts go and WHAT each cell is called; `kit.slice_chunk`
does the clipping and the packing. The split is the same one `array2d.py` /
`facade.py` already draw: everything here is `hou`-free arithmetic on a
bounding box, so it runs under plain `python` in the fast unit lane, and the
only geometry call in the whole tool is the `clip` verb `place.clip_plane`
already uses (D131).

DECISIONS TAKEN HERE (recorded in polychain.md 10):

  D267 GUIDES ARE PLANES ON THE SECOND INPUT, AND THE AUTO LAYOUT IS THREE
       BANDS PER AXIS. RailClone ships guides, so guides are the mechanism
       (`railclone.md` 6.3); "bay rhythm detection" is declined because a
       detector that guesses a rhythm off vertex positions is exactly the
       "clever automation the artist cannot steer" the tool-design skill
       names as the #1 reason procedural tools are abandoned. When no guide
       is placed the layout is derived from ONE number the artist already has
       to think about - the bay width - and defaults to a third of the chunk,
       which tiles any chunk into start | default | end with nothing set.
  D268 A BAND'S CLASS DECIDES WHETHER ITS SIZE IS FREE, NOT ITS POSITION.
       D131's jigsaw rule says "the default cell's size on the axes it is not
       a cap for". A cap is a RUN cap - X `start`/`end` and Y `start`/`end` -
       so those keep whatever width the artist's chunk gives them, and every
       other class (`default`, `corner`, `evenly`, `marker:<id>`) is clipped
       to exactly the default cell size on that axis. That is what makes the
       pieces mate, so it is on by default (`jigsaw`) and asserted.
  D269 TWO BANDS OF THE SAME CLASS ARE VARIANTS, NOT A COLLISION. A chunk
       with five bays and no guides on the middle three yields three
       `default` cells; they ship as `default`, `default_2`, `default_3`
       sharing `pc_variant = "default"`, which is exactly RailClone's
       Sequence/Randomize over bays and costs the vocabulary nothing.
  D270 THE CELL FRAME IS THE CELL, NOT THE GEOMETRY. Each cell is translated
       so the cell's own (x0, y0) sits at the module origin, and Z is left
       exactly as authored (the artist's wall plane is where they put it).
       `place._Proto` takes a module's fit origin from its bbox MIN X, so a
       cell whose geometry does not reach its own low edge would be placed
       shifted - that is a void in the artist's chunk at a cut line, and it
       is reported (`pc_slice: ... does not reach`) rather than hidden.
"""

from . import EPS, role_2d, split_role

# Cap classes, per D268. A cap's extent on its own axis is the artist's.
CAPS = ("start", "end")

WARN = "pc_slice"


class Band(object):
    """One interval on one axis, with the cell class it carries."""

    __slots__ = ("cls", "a", "b", "cap")

    def __init__(self, cls, a, b):
        self.cls = cls
        self.a = float(a)
        self.b = float(b)
        self.cap = cls in CAPS

    @property
    def size(self):
        return self.b - self.a

    def __repr__(self):
        return "Band(%r, %.6f, %.6f)" % (self.cls, self.a, self.b)


class Cell(object):
    """One emitted module: a role, a name and the box to clip it out of."""

    __slots__ = ("role", "name", "variant", "x0", "x1", "y0", "y1")

    def __init__(self, role, name, variant, x0, x1, y0, y1):
        self.role = role
        self.name = name
        self.variant = variant
        self.x0, self.x1, self.y0, self.y1 = (float(x0), float(x1),
                                              float(y0), float(y1))

    @property
    def size(self):
        return (self.x1 - self.x0, self.y1 - self.y0)

    def __repr__(self):
        return "Cell(%r, x=[%.4f %.4f], y=[%.4f %.4f])" % (
            self.name, self.x0, self.x1, self.y0, self.y1)


def _fill_width(bands, lo, hi, caps):
    """The default cell size when the artist did not name one.

    The first NON-CAP band's own width, because a guide the artist placed at
    a bay boundary already says what a bay is. With no guide at all there is
    exactly one non-cap band and it is a third of the chunk.
    """
    for bd in bands:
        if not bd.cap and bd.size > EPS:
            return bd.size
    return max(hi - lo, EPS) / (3.0 if caps else 1.0)


def axis_bands(lo, hi, size=0.0, guides=(), caps=True, jigsaw=True,
               warns=None, axis="x"):
    """[Band] low to high across [lo, hi].

    `guides` is [(coord, class or "")] - a plane, and optionally the name of
    the band that STARTS at it. Guides outside the span are ignored (a plane
    that misses the chunk cuts nothing).
    """
    warns = warns if warns is not None else []
    span = float(hi) - float(lo)
    if span <= EPS:
        warns.append("%s: the chunk has no %s extent - nothing to slice"
                     % (WARN, axis))
        return []
    named, cuts = {}, []
    for coord, cls in guides:
        c = float(coord)
        if not (lo + EPS < c < hi - EPS):
            warns.append("%s: %s guide at %.4f is outside the chunk "
                         "[%.4f %.4f] - ignored" % (WARN, axis, c, lo, hi))
            continue
        cuts.append(c)
        if cls:
            named[c] = str(cls)
    cuts.sort()
    # ⚠️ ONE `w` FOR BOTH JOBS. The bay size decides where the auto cuts go
    # AND how wide a fill cell is, and computing it twice let the overlap
    # fallback below fix the cut planes while the jigsaw pass went on using
    # the size that caused the overlap - a mutation that deleted the fallback
    # outright stayed green because both checks read the band's CLASS.
    w = float(size) if float(size) > EPS else 0.0
    if not cuts:
        # D267's auto layout: one bay in from each end, so a chunk with
        # nothing set becomes start | default | end.
        if w <= EPS:
            w = span / (3.0 if caps else 1.0)
        if caps:
            if 2.0 * w >= span - EPS:
                warns.append(
                    "%s: %s bay size %.4f leaves no middle band in a %.4f "
                    "chunk - using a third of the chunk instead"
                    % (WARN, axis, w, span))
                w = span / 3.0
            cuts = [lo + w, hi - w]
    edges = [lo] + cuts + [hi]
    bands, n = [], len(edges) - 1
    for i in range(n):
        a, b = edges[i], edges[i + 1]
        cls = named.get(a)
        if cls is None:
            cls = ("start" if (caps and i == 0)
                   else "end" if (caps and i == n - 1) else "default")
        bands.append(Band(cls, a, b))
    if not jigsaw:
        return bands
    if w <= EPS:
        w = _fill_width(bands, lo, hi, caps)
    for bd in bands:
        if bd.cap:
            continue
        # D268: a fill cell is EXACTLY the default cell size, anchored at its
        # own low edge. Trimming a longer band is the jigsaw rule working; a
        # band SHORTER than the cell means the cell reaches into its
        # neighbour, and that is the artist's to know about.
        if bd.size < w - 1e-9:
            warns.append(
                "%s: %s band [%.4f %.4f] is shorter than the %.4f cell - the "
                "%r cell overlaps its neighbour"
                % (WARN, axis, bd.a, bd.b, w, bd.cls))
        bd.b = bd.a + w
    return bands


def plan(bbox, xsize=0.0, ysize=0.0, guides=(), xcaps=True, ycaps=True,
         jigsaw=True):
    """(bbox, parms, guides) -> ([Cell], [warning strings]).

    `bbox` is (x0, x1, y0, y1). `guides` is [(axis, coord, class)] with axis
    "x" or "y". The cells are the product of the X bands and the Y bands, so
    the role vocabulary is 7.2's `<x_slot>_<y_slot>` with nothing new in it.
    """
    warns = []
    gx = [(c, n) for a, c, n in guides if a == "x"]
    gy = [(c, n) for a, c, n in guides if a == "y"]
    xb = axis_bands(bbox[0], bbox[1], xsize, gx, xcaps, jigsaw, warns, "x")
    yb = axis_bands(bbox[2], bbox[3], ysize, gy, ycaps, jigsaw, warns, "y")
    roles = []
    for y in yb:
        for x in xb:
            roles.append((role_2d(x.cls, y.cls), x, y))
    counts = {}
    for role, _x, _y in roles:
        counts[role] = counts.get(role, 0) + 1
    seen, cells = {}, []
    for role, x, y in roles:
        k = seen.get(role, 0)
        seen[role] = k + 1
        # D269: same role twice = a variant set, not a collision.
        cells.append(Cell(role,
                          role if k == 0 else "%s_%d" % (role, k + 1),
                          role if counts[role] > 1 else "",
                          x.a, x.b, y.a, y.b))
    return (cells, warns)


def guides_from_points(positions, normals, classes=()):
    """The second input, read: [(axis, coord, class)].

    A guide is a POINT WITH A NORMAL - the Houdini spelling of a plane, and
    the one an artist can author with a single Add SOP. The axis is whichever
    of X / Y the normal leans toward; a normal with neither (a guide lying in
    the XY plane) cuts nothing and says so.
    """
    out, warns = [], []
    for i, p in enumerate(positions):
        n = normals[i] if i < len(normals) else (0.0, 0.0, 0.0)
        ax, ay = abs(float(n[0])), abs(float(n[1]))
        if max(ax, ay) <= EPS:
            warns.append("%s: guide %d has no X or Y normal - a guide is a "
                         "point plus the direction it cuts" % (WARN, i))
            continue
        axis = "x" if ax >= ay else "y"
        out.append((axis, float(p[0] if axis == "x" else p[1]),
                    str(classes[i]) if i < len(classes) else ""))
    return (out, warns)


def jigsaw_report(cells, jigsaw=True):
    """D131's assertion, computed rather than asserted: the worst deviation
    (metres) between a non-cap cell's extent and the default cell's size, per
    axis. `{"x": float, "y": float, "cells": int}`.

    WHAT IT CANNOT SEE: whether the GEOMETRY inside a cell fills the cell.
    That is `kit.slice_chunk`'s `does not reach` warning, measured there
    because only there does geometry exist.
    """
    dx = _spread([c.x1 - c.x0 for c in cells if not _is_cap(c.role, 0)])
    dy = _spread([c.y1 - c.y0 for c in cells if not _is_cap(c.role, 1)])
    return {"x": dx, "y": dy, "cells": len(cells), "jigsaw": int(bool(jigsaw))}


def _is_cap(role, axis):
    """Is `role`'s X (axis 0) or Y (axis 1) class a run cap?"""
    return split_role(role)[axis] in CAPS


def _spread(values):
    return (max(values) - min(values)) if values else 0.0
