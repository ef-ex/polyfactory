"""polyChain 4.2 PLAN - the fitting solve. Pure maths, no geometry, no `hou`.

Per section: reserve the start/end modules, place the evenly and marker
anchors, then fill what is left in the active mode. The output is a
PLACEMENT PLAN - an ordered list of small objects that become inspectable
points in Houdini. That plan is the tool's debuggability contract (4.2), so
everything here stays plain data with an `as_dict()`.

THE FOUR FILL MODES (4.2, and `railclone.md` 1 where the spec is terse):

  tile      floor(L/s) whole pieces plus ONE sliced remainder. The remainder is
            only cut when the module allows it (`pc_deform == 2`); otherwise
            the WHOLE run falls back to `adaptive` and every piece in it
            carries WARN_TILE_FALLBACK (D11).
  scale     ONE piece stretched across the section. Verified against iToo's
            own wording, 2026-08-21: "Scale stretches one segment across the
            entire length of each sub-spline"
            (itoosoft.com/tutorials/mastering-the-linear-generator). It is NOT
            "n pieces stretched" - that is `adaptive`, and giving `scale` the
            same behaviour would make two of the four modes identical (D12).
  adaptive  n whole pieces, all scaled by L/(n*s) - never a cut. `adaptivePct`
            is the add-one-more threshold, in percent of a whole unit: 50 is
            round-to-nearest, 100 never adds. THE DEFAULT MODE.
  count     fixed N pieces scaled to fit. N = 0 places nothing (a legal way to
            switch a slot off); N = 1 is `scale`.

PADDING (RailClone semantics, the load-bearing one): `pc_pad` moves the
NEIGHBOURS, never the padded piece. So the space between two pieces is
`prev.pad[1] + next.pad[0]`, a piece's own pad never displaces it, negative
padding overlaps, and padding is NOT scaled by the fit (D5) - it is a scene
distance. The leading pad of the first piece in a run and the trailing pad of
the last are consumed by whatever piece is next to them (the start/end module,
or nothing at a section end).

FURTHER DECISIONS TAKEN HERE:

  D11 The `tile` fallback re-runs the WHOLE run in `adaptive`, not just the
      last piece. One adaptive piece inside a tiled run reads as a defect in
      the viewport; a uniformly rescaled run reads as a choice.
  D12 see `scale`, above.
  D13 Overflow policy (3.4 names `pc_warn_overflow` and does not define it):
      drop `end` first, then `start`; if the section is shorter than the one
      surviving module, place it SCALED to L and warn. Never an empty section,
      never an exception.
  D14 A run is fitted on its UNIT, not on a single module: for a `sequence`
      rule the unit is the whole pattern (post + panel + post ...), so mixed
      sizes still fill exactly. For every other selector the unit is one
      module, and a per-piece re-selection (random, conditional) is scaled
      into the slot the unit laid out - which is what keeps the exact-fill
      property true for a mixed-size random kit.
  D15 Evenly and marker anchors are CENTRED on their anchor position, and
      marker anchors are never nudged to fit (PC-G1 wants the gate exactly at
      its marker). Evenly anchors divide the free span MINUS half a module at
      each capped end, which is what actually keeps the centred piece off the
      start/end module - subtracting only the padding does not.
  D17 Padding that cancels the unit degrades (one scaled piece, or a count
      clamped to MAX_UNITS) and warns WARN_DEGENERATE_PAD; it never divides by
      zero, never returns a negative scale, and never plans a million pieces.
  D18 Start/end modules cap a RUN, not a section - see decompose.py. A corner
      gets no caps; a spline end and a `pc_section` limit do.
  D19 A closed section wraps, so its run has n inter-unit gaps and not n-1,
      and it starts half a gap in. Otherwise the seam is the one joint on the
      ring where the padding contract does not hold.
  D16 `u` on a placement is 0-1 along the PARENT CURVE at the piece's start.
      That is what 3.4's `pc_u` anchor means downstream. Section-local metres
      (`s0`, `s1`) stay the truth for everything inside this module.
"""

import math

from . import (DEFAULTS, EPS, MAX_UNITS, WARN_DEGENERATE_PAD, WARN_KIT_GAP,
               WARN_OVERFLOW, WARN_ROLE_FALLBACK, WARN_TILE_FALLBACK,
               WARN_VEXPR_IGNORED, WARN_Y_ALIGN_LOST, elem_id, elem_key,
               rng_for, role_2d)


class Placement(object):
    """ONE plan point: what goes where, at what scale, and what went wrong."""

    def __init__(self, curve_id, section_index, slot, index, module,
                 s0, s1, u=0.0, scale=1.0, slice_t=None, deform=0,
                 zmode="adaptive", variant="", section_key=0, style_id="",
                 warns=(), anchor=None, cuts=()):
        self.curve_id = curve_id
        self.section_index = int(section_index)
        self.section_key = section_key
        self.slot = slot
        self.index = int(index)
        self.module = module
        self.variant = variant
        self.s0 = float(s0)
        self.s1 = float(s1)
        self.u = float(u)
        self.scale = float(scale)
        self.slice_t = slice_t
        self.deform = int(deform)
        self.zmode = zmode
        self.style_id = style_id
        # 7.3.3 - the 2D half of the address. Blank on every 1D placement, and
        # NOT part of `elem_id` (D133): `pc_curve_id` already carries the row,
        # so the address is unique without it and `elem_id()` stays untouched.
        self.yclass = ""
        self.cell = ""
        # 7.3.3's `pc_clipped`: this piece sits on a row whose span the clip
        # boundary trimmed (D137 - the clip is a span, not a cull).
        self.clipped = 0
        self.warns = tuple(warns)
        # 4.3. `anchor` = ((ox,oy,oz), (dx,dy,dz)) - build this piece on a
        # STRAIGHT line instead of on the curve, which is what a mitered corner
        # piece rides on (the leg, extrapolated past the vertex). `cuts` =
        # ((origin, normal, keep_sign), ...) world-space half-space clips; a
        # piece carrying one can never stay a packed prim.
        self.anchor = anchor
        self.cuts = tuple(cuts)

    @property
    def length(self):
        return self.s1 - self.s0

    @property
    def elem_id(self):
        return elem_id(self.curve_id, self.section_index, self.slot,
                       self.index, self.style_id)

    def as_dict(self):
        return {"pc_elem_id": self.elem_id, "pc_elem_key": elem_key(self.elem_id),
                "curve_id": self.curve_id, "section": self.section_index,
                "pc_section": self.section_key, "pc_slot": self.slot,
                "index": self.index, "pc_module": self.module,
                "pc_variant": self.variant, "s0": self.s0, "s1": self.s1,
                "length": self.length, "pc_u": self.u, "scale": self.scale,
                "slice_t": self.slice_t, "pc_deform": self.deform,
                "pc_zmode": self.zmode, "warns": list(self.warns),
                "pc_corner_cut": 1 if self.cuts else 0,
                "pc_anchored": 1 if self.anchor else 0}

    def __repr__(self):
        return "Placement(%s %s[%d] %.4f..%.4f x%.4f)" % (
            self.slot, self.module, self.index, self.s0, self.s1, self.scale)


# --- the pure fitting maths -------------------------------------------------

def fit(length, nominal, mode="adaptive", params=DEFAULTS, gap=0.0, fixed=0.0,
        count=None):
    """How many units fit in `length`, and by how much they stretch.

    `nominal` is the SCALABLE length of one unit (the module geometry);
    `fixed` is the non-scalable length inside a unit (padding between the
    modules of a sequence) and `gap` the non-scalable length between two
    units. Padding never scales (D5), so it is carried separately rather than
    folded into `nominal`.

    -> {"count", "scale", "remainder", "slice", "warns"}. `remainder` is the
    sliced tail `tile` leaves (0 otherwise); `scale` multiplies module geometry
    only. `warns` is D17's degenerate-padding flag, never an exception.
    """
    L = float(length)
    s = float(nominal)
    if s <= EPS or L <= EPS:
        return {"count": 0, "scale": 1.0, "remainder": 0.0, "slice": False,
                "warns": ()}
    step = s + fixed + gap                       # one more unit costs this much
    if step <= EPS:
        # D17: the padding cancels (or reverses) the unit, so one more piece
        # costs nothing and "how many fit" has no answer. Degrade to a single
        # scaled unit rather than dividing by zero or planning a million.
        return {"count": 1, "scale": max((L - fixed) / s, 0.0),
                "remainder": 0.0, "slice": False, "warns": (WARN_DEGENERATE_PAD,)}
    whole = int(math.floor((L + gap + EPS) / step))
    # padding that leaves under 1% of the module as the step is obeyed, but it
    # is a mistake worth seeing in the viewport - it plans thousands of pieces
    # overlapping by 99%, which reads as one solid blob
    dense = (WARN_DEGENERATE_PAD,) if step < s * 0.01 else ()

    def clamp(n):
        return (min(n, MAX_UNITS),
                dense if n <= MAX_UNITS else (WARN_DEGENERATE_PAD,))

    if mode == "tile":
        n, warns = clamp(max(whole, 0))
        used = n * (s + fixed) + max(n - 1, 0) * gap
        rem = L - used - (gap if n > 0 else 0.0)
        return {"count": n, "scale": 1.0, "remainder": max(rem, 0.0),
                "slice": rem > EPS, "warns": warns}

    if mode == "scale":
        n = 1                                    # D12 - one stretched piece
    elif mode == "count":
        # D122 - `count` is the ALIGNED datum's bay count for THIS section,
        # and it wins over the parm because it is not a parm: it is the
        # measurement of another row that this one has to agree with.
        n = max(int(params.count if count is None else count), 0)
    else:                                        # adaptive, and any unknown
        exact = (L + gap) / step
        n = int(math.floor(exact + EPS))
        if (exact - n) * 100.0 >= params.adaptive_pct - EPS:
            n += 1
        n = max(n, 1)
    if n <= 0:
        return {"count": 0, "scale": 1.0, "remainder": 0.0, "slice": False,
                "warns": ()}
    n, warns = clamp(n)
    # positive padding can eat the whole section; drop units until it cannot
    while n > 1 and (L - n * fixed - (n - 1) * gap) <= EPS:
        n -= 1
    scale = (L - n * fixed - (n - 1) * gap) / (n * s)
    if scale < 0.0:
        # D17 again, the n == 1 case the drop loop cannot reach: the unit's own
        # internal padding is longer than the span. A negative scale is
        # geometry built backwards, so it degenerates to zero length and warns.
        scale, warns = 0.0, warns + (WARN_DEGENERATE_PAD,)
    return {"count": n, "scale": scale, "remainder": 0.0, "slice": False,
            "warns": warns}


def evenly(length, params=DEFAULTS):
    """Anchor positions in metres along a span of `length` (4.2).

    Count mode divides the span into `evenly_count + 1` equal parts and
    anchors the interior divisions. Distance mode steps by `evenly_spacing`,
    and `justify` sets the LEADING space, which is what RailClone's "adjust
    the first and last space so the evenly segments fit" asks for:

      start   lead = d           - a full spacing in, leftover trails
      center  lead = trail       - SYMMETRIC about the span. n anchors span
                                   (n-1)*d, so the leading space is half of
                                   what is left of the span, NOT half of the
                                   leftover: a centred fence must read
                                   symmetric to the artist, and centring on
                                   the span MULTIPLE instead shoves the whole
                                   run to the far end.
      end     lead = leftover    - mirror of `start`: a full spacing trails.

    `adjust_to_end` overrides all three when the leftover is small enough,
    stretching the spacing so the last anchor lands exactly on the end.
    """
    L = float(length)
    if L <= EPS:
        return []
    if params.evenly_count > 0:
        n = int(params.evenly_count)
        step = L / (n + 1)
        return [step * (i + 1) for i in range(n)]
    d = params.evenly_spacing
    if d <= EPS:
        return []
    n = int(math.floor((L - EPS) / d))
    if n <= 0:
        return []
    leftover = L - n * d
    if 0.0 < leftover <= params.adjust_to_end + EPS:
        d = L / n                                # last anchor lands on the end
        return [d * (i + 1) for i in range(n)]
    lead = {"start": d,
            "center": (L - (n - 1) * d) * 0.5,
            "end": leftover}[params.justify]
    return [lead + d * i for i in range(n)]


def pack(cursor, module, scale, prev=None):
    """Place one piece. Padding moves the NEIGHBOUR, so the gap belongs here.

    -> (s0, s1, next_cursor). `prev` is the module before it in the run, or
    None at the head of a run (its own left pad has nothing to push).
    """
    gap = (prev.pad[1] + module.pad[0]) if prev is not None else 0.0
    s0 = cursor + gap
    s1 = s0 + module.length * scale
    return (s0, s1, s1)


# --- selection (3.3) --------------------------------------------------------

_OPS = {
    "lt": lambda a, b: a < b,
    "le": lambda a, b: a <= b,
    "gt": lambda a, b: a > b,
    "ge": lambda a, b: a >= b,
    "eq": lambda a, b: a == b,
    "ne": lambda a, b: a != b,
    "in": lambda a, b: a in b,
}

COND_SUBJECTS = ("sectionLength", "splineLength", "u", "cornerAngle",
                 "segIndex")


def cond_subject(subject, ctx):
    """3.3's subject list. `markerData:<k>` and `attr:<n>` read the ctx bags."""
    if subject.startswith("markerData:"):
        return ctx.get("marker_data", {}).get(subject.split(":", 1)[1])
    if subject.startswith("attr:"):
        return ctx.get("attrs", {}).get(subject.split(":", 1)[1])
    return ctx.get(subject)


def evaluate_cond(cond, ctx):
    """A DATA condition, never code (D3). Anything unreadable is False."""
    if not cond:
        return True
    op = _OPS.get(cond.get("op", "eq"))
    if op is None:
        return False
    value = cond_subject(cond.get("subject", ""), ctx)
    if value is None:
        return False
    try:
        return bool(op(value, cond.get("value")))
    except TypeError:
        return False                             # warn-never-block


def cell_role(ctx, slot=None):
    """E1's tail - the 2D cell this piece is, or its plain X slot in 1D.

    `yclass` reaches here from the ROW PRIM through `Section.attrs` (D94) and
    `plan_section`'s ctx, so a 2D build resolves `corner_end` where a 1D build
    resolves `corner`, with no branch anywhere: 7.2's role name IS the role
    the kit is asked for, and E3's closure has already made sure the kit can
    answer it (D118).
    """
    slot = ctx.get("slot", "") if slot is None else slot
    y = ctx.get("yclass") or ""
    return role_2d(slot, y) if y else slot


def classify(placements, kit, yclass, row_warns=(), clipped=0):
    """Stamp the 2D half of every placement of ONE row. E1's other tail.

    ONE site, deliberately: `corner.plan_curve` builds the corner assembly's
    placements itself and never passes through `_module_warns`, so a fallback
    warning written in the fill path would have been silent on exactly the
    cell PC-G5 cares most about (a corner column meeting the cornice). Every
    placement of the row is here, whatever built it.

    ⚠️ IT LIVES IN `plan.py`, NOT IN `array2d.py`. 7 says phase 2 is a stage
    ABOVE the kernel; `place.build` importing `array2d` pointed the dependency
    arrow the wrong way and made the kernel untestable without the 2D stage
    (D140). This touches `Placement` and `Kit.role_fallbacks` and nothing
    else, so it is kernel work that the 2D stage merely feeds.

    `row_warns` is D139's channel: a warning the Y SOLVE raised belongs to the
    whole row, and the row curve carries it in `pc_row_warns` so it reaches
    every element the row produced - which is the difference between a
    truncated building that says so and one that ships silent.
    """
    if not yclass and not row_warns and not clipped:
        return placements
    for p in placements:
        if yclass:
            p.yclass = yclass
            p.cell = role_2d(p.slot, yclass)
            if p.cell in kit.role_fallbacks \
                    and WARN_ROLE_FALLBACK not in p.warns:
                p.warns = tuple(p.warns) + (WARN_ROLE_FALLBACK,)
        p.clipped = int(clipped)
        extra = tuple(w for w in row_warns if w and w not in p.warns)
        if extra:
            p.warns = tuple(p.warns) + extra
    return placements


def candidates(rule, kit, role=None):
    """The rule's module list as real modules: name, then role, then stand-in.

    `role` is the CELL role (7.2) when the caller knows it and the rule's own
    slot otherwise - which is the 1D case and every phase-1 call.
    """
    out = []
    for name in rule.modules:
        out.extend(kit.resolve(name))
    if not out:
        out.extend(kit.resolve(role or rule.slot))
    return out


def choose(rule, kit, ctx, style):
    """One module for one piece, or None when a conditional rule declines."""
    cand = candidates(rule, kit, cell_role(ctx, ctx.get("slot", rule.slot)))
    if not cand:
        return None
    if rule.select == "sequence":
        return cand[int(ctx.get("index", 0)) % len(cand)]
    if rule.select == "random":
        # sorted, so the pick cannot depend on the order the payload happens
        # to list the modules in - the determinism property under shuffle
        pool = sorted(cand, key=lambda m: (m.name, m.variant))
        weights = [rule.weights.get(m.name, m.weight) for m in pool]
        total = sum(weights)
        r = rng_for(style, rule.scope, ctx).random() * total
        if total <= 0.0:
            return pool[0]
        acc = 0.0
        for m, w in zip(pool, weights):
            acc += w
            if r < acc:
                return m
        return pool[-1]
    if rule.select == "conditional":
        if evaluate_cond(rule.cond, ctx):
            return cand[0]
        return cand[1] if len(cand) > 1 else None
    return cand[0]                               # first


def pick(style, slot, ctx, kit):
    """(rule, module) for `slot`: payload order, first rule that yields wins.

    D119 - with a row class in `ctx` the rule list is SCOPED first and generic
    second, so the rule-level chain (this row class -> any row) and the
    kit-level chain (the role lattice -> the stand-in box) are two independent
    ordered walks and neither has to know about the other.
    """
    for rule in style.rules_for(slot, ctx.get("yclass") or None):
        m = choose(rule, kit, dict(ctx, slot=slot), style)
        if m is not None:
            return (rule, m)
    return (None, None)


def _module_warns(module, rule):
    w = []
    if module.missing:
        w.append(WARN_KIT_GAP)
    if rule is not None and rule.vexpr:
        w.append(WARN_VEXPR_IGNORED)             # D3: parsed, ignored, warned
    return w


def _zmode(module, params):
    return params.zmode if params.zmode else module.zmode


# --- the section solve ------------------------------------------------------

def _unit(rule, kit, ctx, style):
    """The repeating unit of a run (D14): a whole sequence, or one module."""
    if rule.select == "sequence":
        # ⚠️ THE CELL ROLE, exactly as `choose` asks for it. A `sequence` rule
        # that names no modules is the cases2d idiom (the kit's roles decide
        # every cell), and asking `candidates` without the role resolved the
        # bare X slot - so a `sequence` ground floor silently filled with the
        # `default` bay and D138's yscale stretched a 3.2 m module into a
        # 4.0 m band with every check green.
        mods = candidates(rule, kit, cell_role(ctx, ctx.get("slot", rule.slot)))
        return mods if mods else None
    m = choose(rule, kit, ctx, style)
    return [m] if m is not None else None


def _unit_metrics(mods):
    """(scalable length, fixed padding inside the unit, gap between units)."""
    s = sum(m.length for m in mods)
    fixed = sum(mods[j].pad[1] + mods[j + 1].pad[0] for j in range(len(mods) - 1))
    gap = mods[-1].pad[1] + mods[0].pad[0]
    return (s, fixed, gap)


def _aligned_count(attrs, index):
    """D122's `pc_bays`, read off the ROW CURVE: the DATUM row's default-fill
    piece count for this section, or None where the row is the datum itself
    (or the Y fit is `free`, which stamps nothing at all).

    A STRING of `<section>:<count>` tokens, D76's convention for the third
    time - one list format across the kit manifest, the row warnings and this,
    and a storage every one of them can carry (D223). Junk degrades to None
    rather than raising: it is a prim attribute and an artist can author it.
    """
    for tok in str(attrs.get("pc_bays", "") or "").split():
        sec, _sep, n = tok.partition(":")
        if sec == str(index):
            try:
                return max(int(n), 0)
            except ValueError:
                return None
    return None


def _fill(a, b, rule, kit, style, ctx_base, params, section, index0,
          lead_pad=None, trail_pad=None, mode=None, extra_warns=(),
          cyclic=False, count=None):
    """Fill [a, b] with one run. Returns (placements, next index).

    `lead_pad` / `trail_pad` are the facing pads of the neighbouring pieces,
    or None where there is no neighbour - at a section end nothing is there to
    be pushed, so the run's own outer pad must NOT displace it (padding moves
    neighbours, never the padded piece).

    `cyclic` is a closed section with nothing else on it (D19): the run wraps,
    so it has n inter-unit gaps and not n-1, and it starts half a gap in - or
    the seam is the one joint on an otherwise uniform ring where two pieces
    touch (or, with negative padding, fail to overlap).
    """
    if rule is None:
        return ([], index0)
    ctx0 = dict(ctx_base, slot="default", index=index0, segIndex=index0)
    mods = _unit(rule, kit, ctx0, style)
    if not mods:
        return ([], index0)
    span_a = a if lead_pad is None else a + lead_pad + mods[0].pad[0]
    span_b = b if trail_pad is None else b - trail_pad - mods[-1].pad[1]
    L = span_b - span_a
    if L <= EPS:
        return ([], index0)

    s, fixed, gap = _unit_metrics(mods)
    # D122 - the ALIGNED row does not choose a fill mode: it is handed the
    # datum row's piece count and scales its own modules into the span, which
    # is RC's "all segments along the Y path are scaled to maintain the same
    # alignment as on X" said in this solver's own vocabulary.
    mode = "count" if count is not None else (mode or params.fill)
    lead = 0.0
    if cyclic and L - gap > EPS:                 # D19: fold the wrap gap in
        L -= gap
        lead = gap * 0.5
    res = fit(L, s, mode, params, gap=gap, fixed=fixed, count=count)
    extra_warns = tuple(extra_warns) + tuple(res["warns"])
    if count is not None and res["count"] != count:
        # 7.4's own case: "where a row physically cannot hold the datum's
        # count (a setback so deep the section is shorter than the count's
        # minimum), the row degrades to its own solve and says so". `fit`
        # already dropped units until the padding stopped eating the span;
        # this is what makes that visible instead of silently unaligned.
        extra_warns = extra_warns + (WARN_Y_ALIGN_LOST,)

    def fallback():
        """D11: the whole run falls back to adaptive, and says so on each piece."""
        return _fill(a, b, rule, kit, style, ctx_base, params, section, index0,
                     lead_pad, trail_pad, mode="adaptive",
                     extra_warns=extra_warns + (WARN_TILE_FALLBACK,),
                     cyclic=cyclic)

    out = []
    idx = index0
    cursor = span_a + lead
    scale = res["scale"]

    def clip(x):
        """Degenerate padding walks the cursor out of the span; nothing may be
        planned outside the section it belongs to, so it stops at the edge."""
        return min(max(x, span_a), span_b) if WARN_DEGENERATE_PAD in extra_warns \
            else x
    for u_i in range(res["count"]):
        if u_i > 0:
            cursor += gap
        for j, proto in enumerate(mods):
            if j > 0:
                cursor += mods[j - 1].pad[1] + proto.pad[0]
            target = proto.length * scale
            ctx = dict(ctx_base, slot="default", index=idx, segIndex=idx,
                       u=section.u_at(cursor))
            m = proto if rule.select == "sequence" else choose(rule, kit, ctx,
                                                               style)
            if m is None:
                m = proto
            out.append(Placement(
                section.curve_id, section.index, "default", idx, m.name,
                clip(cursor), clip(cursor + target), u=section.u_at(cursor),
                scale=(target / m.length) if m.length > EPS else 1.0,
                deform=m.deform, zmode=_zmode(m, params), variant=m.variant,
                section_key=section.section_key, style_id=style.style_id,
                warns=extra_warns + tuple(_module_warns(m, rule))))
            cursor += target
            idx += 1
    if res["slice"] and res["remainder"] > EPS:
        # The tile remainder CONTINUES the unit rather than being one cut copy
        # of its first module: whole modules until one straddles the boundary,
        # and only that one is sliced. A 3 m panel cannot supply a 2 m tail
        # just because the unit happens to start with a 1 m post.
        if res["count"] > 0:
            cursor += gap                        # no unit before it => no gap
        stop = cursor + res["remainder"]
        prev = None
        for proto in mods:
            if prev is not None:
                cursor += prev.pad[1] + proto.pad[0]
            avail = stop - cursor
            if avail <= EPS:
                break
            ctx = dict(ctx_base, slot="default", index=idx, segIndex=idx,
                       u=section.u_at(cursor))
            m = proto if rule.select == "sequence" else choose(rule, kit, ctx,
                                                               style)
            if m is None:
                m = proto
            if m.length <= avail + EPS:
                length, slice_t = m.length, None
            elif not m.sliceable:
                # the module that ACTUALLY lands on the boundary decides this,
                # not the unit's first module: a re-selected rigid piece may
                # never be cut (4.2), so the whole run falls back instead
                return fallback()
            else:
                length = avail
                slice_t = min(avail / m.length, 1.0) if m.length > EPS else 1.0
            out.append(Placement(
                section.curve_id, section.index, "default", idx, m.name,
                clip(cursor), clip(cursor + length), u=section.u_at(cursor),
                scale=1.0, slice_t=slice_t, deform=m.deform,
                zmode=_zmode(m, params), variant=m.variant,
                section_key=section.section_key, style_id=style.style_id,
                warns=extra_warns + tuple(_module_warns(m, rule))))
            cursor += length
            idx += 1
            prev = m
            if slice_t is not None:
                break
    return (out, idx)


def _anchor_placement(section, style, params, slot, index, rule, module, at,
                      warns=()):
    """A piece CENTRED on an anchor (D15), at nominal size."""
    half = module.length * 0.5
    return Placement(
        section.curve_id, section.index, slot, index, module.name,
        at - half, at + half, u=section.u_at(at - half), scale=1.0,
        deform=module.deform, zmode=_zmode(module, params),
        variant=module.variant, section_key=section.section_key,
        style_id=style.style_id,
        warns=tuple(warns) + tuple(_module_warns(module, rule)))


def plan_section(section, kit, style, params=None, trim=(0.0, 0.0)):
    """The placement plan for one section. Never raises (warn-never-block).

    `params` defaults to the STYLE's own params (2.1: a wired style payload
    "overrides the parms entirely"), and to `DEFAULTS` only when the style
    carries none. An explicit argument still wins - that is the artist face.

    `trim` is 4.3's contribution: (head, tail) metres taken off the FILL span
    at each end - positive shrinks it (a corner assembly reserves the space),
    NEGATIVE grows it past the section boundary (the `extend`/`symmetric`
    displacement policies push the default run through the corner so the
    bisector slice has something to cut). It never moves a start/end cap,
    because a capped boundary is a spline end or a `pc_section` limit and is
    never a corner (D18).
    """
    params = params or (style.params if style is not None else None) or DEFAULTS
    L = section.length
    if L <= EPS:
        return []

    ctx_base = {"curve_id": section.curve_id,
                "section_index": section.index,
                "sectionLength": L,
                "splineLength": section.curve_length,
                "cornerAngle": section.corner_angle,
                "u": section.u0,
                # D94: the SPLINE PRIM'S OWN attributes first, then the two
                # the kernel names itself - so `attr:pc_section` keeps its
                # meaning and `attr:road_width` (the streets hook; 3.3's own
                # wording is "reads any spline prim attr") finally has a value.
                "attrs": dict(getattr(section, "attrs", None) or {},
                              pc_section=section.section_key,
                              pc_style=section.style_key),
                "marker_data": {}}
    # E1 - the ROW's own class, straight off the row prim (D94 harvests it
    # onto `Section.attrs`, so there is no adapter change). Blank on every 1D
    # curve, and blank is what makes `cell_role` the identity and
    # `rules_for(slot, None)` the phase-1 call.
    yclass = str(ctx_base["attrs"].get("pc_yclass", "") or "")
    ctx_base["yclass"] = yclass

    # --- mandatory start / end, and D13's overflow policy -------------------
    ends = []
    # D18: caps end a RUN, not a section. `start_cap`/`end_cap` are true at a
    # spline end and at a `pc_section` limit, false at a corner - so an
    # L-shaped fence grows no post pair at its elbow and a closed spline gets
    # no caps at all (RailClone semantics).
    for slot, capped in (("start", section.start_cap), ("end", section.end_cap)):
        if not capped:
            continue
        rule, mod = pick(style, slot, dict(ctx_base, index=0), kit)
        if mod is not None:
            ends.append([slot, rule, mod])

    def needed(items):
        tot = sum(it[2].length for it in items)
        for k in range(len(items) - 1):
            tot += items[k][2].pad[1] + items[k + 1][2].pad[0]
        return tot

    overflow = False
    while len(ends) > 1 and needed(ends) > L + EPS:
        ends.pop()                               # drop `end` first
        overflow = True
    squeeze = 1.0
    if ends and needed(ends) > L + EPS:
        squeeze = L / ends[0][2].length          # scale the survivor onto L
        overflow = True

    out = []
    warn_end = (WARN_OVERFLOW,) if overflow else ()
    head = tail = None
    for slot, rule, mod in ends:
        length = mod.length * squeeze
        if slot == "start":
            p = Placement(section.curve_id, section.index, "start", 0, mod.name,
                          0.0, length, u=section.u_at(0.0), scale=squeeze,
                          deform=mod.deform, zmode=_zmode(mod, params),
                          variant=mod.variant, section_key=section.section_key,
                          style_id=style.style_id,
                          warns=warn_end + tuple(_module_warns(mod, rule)))
            head = (p, mod)
        else:
            p = Placement(section.curve_id, section.index, "end", 0, mod.name,
                          L - length, L, u=section.u_at(L - length),
                          scale=squeeze, deform=mod.deform,
                          zmode=_zmode(mod, params), variant=mod.variant,
                          section_key=section.section_key,
                          style_id=style.style_id,
                          warns=warn_end + tuple(_module_warns(mod, rule)))
            tail = (p, mod)
        out.append(p)

    free_a = head[0].s1 if head else float(trim[0])
    free_b = tail[0].s0 if tail else L - float(trim[1])
    lead_pad = head[1].pad[1] if head else None
    trail_pad = tail[1].pad[0] if tail else None

    # --- anchors: evenly, then markers (D15) --------------------------------
    anchors = []
    e_rule, e_mod = pick(style, "evenly", dict(ctx_base, index=0), kit)
    if e_mod is not None:
        # D15, corrected: the anchor divides the free span, but the PIECE is
        # centred on it, so half a module has to come off each guarded end -
        # otherwise the last evenly post grows through the end cap.
        #
        # D269: a RESERVED boundary is guarded, not only a CAPPED one. D18
        # makes `start_cap`/`end_cap` false at a corner - a corner assembly
        # reserves its space through `trim`, not through a cap - so `head`
        # and `tail` are both None there and the shed never ran. Measured on
        # the shipped asset: `Evenly Justify = From the end` on a 12.161 m
        # leg drove the evenly post HALF ITS WIDTH INTO the mitered corner
        # post (0.061 m of interpenetration), and `Adjust to End` did it at
        # every corner of every leg. Same shed, same reason, one more way of
        # spelling "something is already standing here".
        half = e_mod.length * 0.5
        guard_a = head is not None or float(trim[0]) > EPS
        guard_b = tail is not None or float(trim[1]) > EPS
        base = free_a + (lead_pad or 0.0) + (e_mod.pad[0] + half if guard_a else 0.0)
        top = free_b - (trail_pad or 0.0) - (e_mod.pad[1] + half if guard_b else 0.0)
        for i, at in enumerate(evenly(max(top - base, 0.0), params)):
            at += base
            # the rule is re-read AT THE ANCHOR: 3.3 lists `u` as a
            # per-candidate subject, and a sequence must walk per anchor
            a_rule, a_mod = pick(style, "evenly",
                                 dict(ctx_base, index=i, u=section.u_at(at)),
                                 kit)
            if a_mod is None:
                continue
            anchors.append(_anchor_placement(
                section, style, params, "evenly", i, a_rule, a_mod, at))
    m_index = {}
    for mk in section.markers:
        slot = "marker:%d" % mk["marker_id"]
        # the marker's OWN u, not the section start: a conditional marker rule
        # on `u` otherwise tests a position the marker is not at
        ctx = dict(ctx_base, index=m_index.get(slot, 0),
                   u=mk.get("u", ctx_base["u"]),
                   marker_data=dict(mk.get("data", {})))
        rule, mod = pick(style, slot, ctx, kit)
        if mod is None:
            continue
        i = m_index.get(slot, 0)
        m_index[slot] = i + 1
        anchors.append(_anchor_placement(
            section, style, params, slot, i, rule, mod,
            mk.get("s_local", mk["s"] - section.s0)))
    anchors.sort(key=lambda p: (p.s0, p.slot, p.index))
    out.extend(anchors)

    # --- the default fill, in the gaps the anchors leave --------------------
    # D119 again - the default fill picks its rule here rather than through
    # `pick`, so without the row class a `yclass`-scoped default rule leaked
    # onto every row exactly as the corner one did.
    d_rules = style.rules_for("default", ctx_base.get("yclass") or None)
    if d_rules:
        ctx = dict(ctx_base, index=0)
        rule = None
        for r in d_rules:
            if choose(r, kit, dict(ctx, slot="default"), style) is not None:
                rule = r
                break
        idx = 0
        a, lead = free_a, lead_pad
        # D19: only a closed section with nothing else on it wraps as one run
        cyclic = section.closed and not anchors and not out
        # 7.4 / D122 - the ALIGNED row's bay count for THIS section, off the
        # row curve. ⚠️ A SECTION WITH ANCHORS ON IT CANNOT TAKE ONE COUNT:
        # the default fill is then several runs and the datum's number says
        # nothing about which run holds how many, so the row falls back to its
        # own free solve and every piece of it says `pc_warn_y_align_lost` -
        # warn, never block (7.4's own wording).
        n_align = _aligned_count(ctx_base["attrs"], section.index)
        lost = ()
        if n_align is not None and anchors:
            n_align, lost = None, (WARN_Y_ALIGN_LOST,)
        for p in anchors + [None]:
            b = p.s0 if p is not None else free_b
            # the anchor's own pad pushes its neighbours, this run included
            trail = _pad_of(kit, p.module, 0) if p is not None else trail_pad
            runs, idx = _fill(a, b, rule, kit, style, ctx_base, params,
                              section, idx, lead_pad=lead, trail_pad=trail,
                              cyclic=cyclic, count=n_align, extra_warns=lost)
            out.extend(runs)
            if p is None:
                break
            a = p.s1
            lead = _pad_of(kit, p.module, 1)
    out.sort(key=lambda p: (p.s0, p.slot, p.index))
    return out


def _pad_of(kit, module_name, side):
    m = kit.by_name(module_name)
    return m.pad[side] if m is not None else 0.0


def plan_sections(sections, kit, style, params=None):
    """Every section's plan, in a deterministic order."""
    out = []
    for sec in sorted(sections, key=lambda s: (str(s.curve_id), s.index)):
        out.extend(plan_section(sec, kit, style, params))
    return out


def plan_dicts(placements):
    """What the Python SOP adapter writes onto the plan points."""
    return [p.as_dict() for p in placements]


def warnings_of(placements):
    """{warning name: count} - the gate reads this, nothing raises."""
    out = {}
    for p in placements:
        for w in p.warns:
            out[w] = out.get(w, 0) + 1
    return out


def coverage(placements):
    """(first s0, last s1) over a plan - the exact-fill property, measured."""
    if not placements:
        return (0.0, 0.0)
    return (min(p.s0 for p in placements), max(p.s1 for p in placements))
