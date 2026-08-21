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
      its marker). Evenly anchors divide the FREE span - what is left after
      start/end are reserved - so they cannot collide with a mandatory piece.
  D16 `u` on a placement is 0-1 along the PARENT CURVE at the piece's start.
      That is what 3.4's `pc_u` anchor means downstream. Section-local metres
      (`s0`, `s1`) stay the truth for everything inside this module.
"""

import math

from . import (DEFAULTS, EPS, WARN_KIT_GAP, WARN_OVERFLOW, WARN_TILE_FALLBACK,
               WARN_VEXPR_IGNORED, elem_id, elem_key, rng_for)


class Placement(object):
    """ONE plan point: what goes where, at what scale, and what went wrong."""

    def __init__(self, curve_id, section_index, slot, index, module,
                 s0, s1, u=0.0, scale=1.0, slice_t=None, deform=0,
                 zmode="adaptive", variant="", section_key=0, style_id="",
                 warns=()):
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
        self.warns = tuple(warns)

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
                "pc_zmode": self.zmode, "warns": list(self.warns)}

    def __repr__(self):
        return "Placement(%s %s[%d] %.4f..%.4f x%.4f)" % (
            self.slot, self.module, self.index, self.s0, self.s1, self.scale)


# --- the pure fitting maths -------------------------------------------------

def fit(length, nominal, mode="adaptive", params=DEFAULTS, gap=0.0, fixed=0.0):
    """How many units fit in `length`, and by how much they stretch.

    `nominal` is the SCALABLE length of one unit (the module geometry);
    `fixed` is the non-scalable length inside a unit (padding between the
    modules of a sequence) and `gap` the non-scalable length between two
    units. Padding never scales (D5), so it is carried separately rather than
    folded into `nominal`.

    -> {"count", "scale", "remainder", "slice"}. `remainder` is the sliced
    tail `tile` leaves (0 otherwise); `scale` multiplies module geometry only.
    """
    L = float(length)
    s = float(nominal)
    if s <= EPS or L <= EPS:
        return {"count": 0, "scale": 1.0, "remainder": 0.0, "slice": False}
    step = s + fixed + gap                       # one more unit costs this much
    whole = int(math.floor((L + gap + EPS) / step)) if step > EPS else 0

    if mode == "tile":
        n = max(whole, 0)
        used = n * (s + fixed) + max(n - 1, 0) * gap
        rem = L - used - (gap if n > 0 else 0.0)
        return {"count": n, "scale": 1.0, "remainder": max(rem, 0.0),
                "slice": rem > EPS}

    if mode == "scale":
        n = 1                                    # D12 - one stretched piece
    elif mode == "count":
        n = max(int(params.count), 0)
    else:                                        # adaptive, and any unknown
        exact = (L + gap) / step
        n = int(math.floor(exact + EPS))
        if (exact - n) * 100.0 >= params.adaptive_pct - EPS:
            n += 1
        n = max(n, 1)
    if n <= 0:
        return {"count": 0, "scale": 1.0, "remainder": 0.0, "slice": False}
    # positive padding can eat the whole section; drop units until it cannot
    while n > 1 and (L - n * fixed - (n - 1) * gap) <= EPS:
        n -= 1
    scale = (L - n * fixed - (n - 1) * gap) / (n * s)
    return {"count": n, "scale": scale, "remainder": 0.0, "slice": False}


def evenly(length, params=DEFAULTS):
    """Anchor positions in metres along a span of `length` (4.2).

    Count mode divides the span into `evenly_count + 1` equal parts and
    anchors the interior divisions. Distance mode steps by `evenly_spacing`,
    then `justify` shifts the whole run inside the leftover (RailClone's
    Justify "adjusts the first and last space so the evenly segments fit") and
    `adjust_to_end` stretches the spacing so the last anchor lands exactly on
    the end when the leftover is small enough.
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
        leftover = 0.0
    shift = {"start": 0.0, "center": leftover * 0.5, "end": leftover}[params.justify]
    return [shift + d * (i + 1) for i in range(n)]


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


def candidates(rule, kit):
    """The rule's module list as real modules: name, then role, then stand-in."""
    out = []
    for name in rule.modules:
        out.extend(kit.resolve(name))
    if not out:
        out.extend(kit.resolve(rule.slot))
    return out


def choose(rule, kit, ctx, style):
    """One module for one piece, or None when a conditional rule declines."""
    cand = candidates(rule, kit)
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
    """(rule, module) for `slot`: payload order, first rule that yields wins."""
    for rule in style.rules_for(slot):
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
        mods = candidates(rule, kit)
        return mods if mods else None
    m = choose(rule, kit, ctx, style)
    return [m] if m is not None else None


def _unit_metrics(mods):
    """(scalable length, fixed padding inside the unit, gap between units)."""
    s = sum(m.length for m in mods)
    fixed = sum(mods[j].pad[1] + mods[j + 1].pad[0] for j in range(len(mods) - 1))
    gap = mods[-1].pad[1] + mods[0].pad[0]
    return (s, fixed, gap)


def _fill(a, b, rule, kit, style, ctx_base, params, section, index0,
          lead_pad=None, trail_pad=None, mode=None, extra_warns=()):
    """Fill [a, b] with one run. Returns (placements, next index).

    `lead_pad` / `trail_pad` are the facing pads of the neighbouring pieces,
    or None where there is no neighbour - at a section end nothing is there to
    be pushed, so the run's own outer pad must NOT displace it (padding moves
    neighbours, never the padded piece).
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
    mode = mode or params.fill
    res = fit(L, s, mode, params, gap=gap, fixed=fixed)

    if res["slice"] and not mods[0].sliceable:
        # D11: the whole run falls back, and says so on every piece
        return _fill(a, b, rule, kit, style, ctx_base, params, section, index0,
                     lead_pad, trail_pad, mode="adaptive",
                     extra_warns=tuple(extra_warns) + (WARN_TILE_FALLBACK,))

    out = []
    idx = index0
    cursor = span_a
    scale = res["scale"]
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
                cursor, cursor + target, u=section.u_at(cursor),
                scale=(target / m.length) if m.length > EPS else 1.0,
                deform=m.deform, zmode=_zmode(m, params), variant=m.variant,
                section_key=section.section_key, style_id=style.style_id,
                warns=tuple(extra_warns) + tuple(_module_warns(m, rule))))
            cursor += target
            idx += 1
    if res["slice"] and res["remainder"] > EPS:
        cursor += gap
        proto = mods[0]
        ctx = dict(ctx_base, slot="default", index=idx, segIndex=idx,
                   u=section.u_at(cursor))
        m = proto if rule.select == "sequence" else choose(rule, kit, ctx, style)
        if m is None:
            m = proto
        rem = res["remainder"]
        out.append(Placement(
            section.curve_id, section.index, "default", idx, m.name,
            cursor, cursor + rem, u=section.u_at(cursor),
            scale=1.0, slice_t=min(rem / m.length, 1.0) if m.length > EPS else 1.0,
            deform=m.deform, zmode=_zmode(m, params), variant=m.variant,
            section_key=section.section_key, style_id=style.style_id,
            warns=tuple(extra_warns) + tuple(_module_warns(m, rule))))
        idx += 1
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


def plan_section(section, kit, style, params=DEFAULTS):
    """The placement plan for one section. Never raises (warn-never-block)."""
    L = section.length
    if L <= EPS:
        return []

    ctx_base = {"curve_id": section.curve_id,
                "section_index": section.index,
                "sectionLength": L,
                "splineLength": section.curve_length,
                "cornerAngle": section.corner_angle,
                "u": section.u0,
                "attrs": {"pc_section": section.section_key,
                          "pc_style": section.style_key},
                "marker_data": {}}

    # --- mandatory start / end, and D13's overflow policy -------------------
    ends = []
    if not section.closed:                       # RailClone: closed => no ends
        for slot in ("start", "end"):
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

    free_a = head[0].s1 if head else 0.0
    free_b = tail[0].s0 if tail else L
    lead_pad = head[1].pad[1] if head else None
    trail_pad = tail[1].pad[0] if tail else None

    # --- anchors: evenly, then markers (D15) --------------------------------
    anchors = []
    e_rule, e_mod = pick(style, "evenly", dict(ctx_base, index=0), kit)
    if e_mod is not None:
        base = free_a + (lead_pad or 0.0) + (e_mod.pad[0] if head else 0.0)
        top = free_b - (trail_pad or 0.0) - (e_mod.pad[1] if tail else 0.0)
        for i, at in enumerate(evenly(max(top - base, 0.0), params)):
            anchors.append(_anchor_placement(
                section, style, params, "evenly", i, e_rule, e_mod, base + at))
    m_index = {}
    for mk in section.markers:
        slot = "marker:%d" % mk["marker_id"]
        ctx = dict(ctx_base, index=m_index.get(slot, 0),
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
    d_rules = style.rules_for("default")
    if d_rules:
        ctx = dict(ctx_base, index=0)
        rule = None
        for r in d_rules:
            if choose(r, kit, dict(ctx, slot="default"), style) is not None:
                rule = r
                break
        idx = 0
        a, lead = free_a, lead_pad
        for p in anchors + [None]:
            b = p.s0 if p is not None else free_b
            # the anchor's own pad pushes its neighbours, this run included
            trail = _pad_of(kit, p.module, 0) if p is not None else trail_pad
            runs, idx = _fill(a, b, rule, kit, style, ctx_base, params,
                              section, idx, lead_pad=lead, trail_pad=trail)
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


def plan_sections(sections, kit, style, params=DEFAULTS):
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
