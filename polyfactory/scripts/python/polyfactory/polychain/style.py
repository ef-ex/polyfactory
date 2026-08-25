"""polyChain 3.3 STYLE PAYLOAD - a `Style` as Houdini geometry, both ways.

This is the missing half of 2.1's TWO-FACE PRINCIPLE. The kernel has always
consumed a `Style` object; until now nothing built one from geometry, so the
pipeline face - "a template may not live inside a node; it arrives on the data
stream" (citygen_streets, quoted in railclone.md 3) - did not exist and gate
PC-G4 had nothing to audit. `read()` is that face, and `write()` is the same
contract in reverse so the parm face's own Style can be expressed as a payload
and fed back through input 3 unchanged.

THE FOUNDATION RULE, AND HOW IT IS ENFORCED HERE
------------------------------------------------
Consumption is a GENERIC LOOP over whatever rules arrive - never a branch per
style name. `read()` therefore contains no style identifier anywhere except as
a value it copies into `styleId`; every rule is read by the same eight lines
regardless of what it says, and a style this file has never heard of works
exactly as well as the starter fence. The kit reader (3.2) already works this
way; this makes the pair complete.

THE FORMAT (3.3, verbatim where the spec is explicit):

  * detail dict `pc_style_meta`: `styleId`, `version`, `seed`, and - see D77 -
    a `params` sub-dict carrying the 5 parm values, because input 3 OVERRIDES
    THE PARMS ENTIRELY (2.1) and a payload that could not say "tile mode"
    would leave half the style behind on the node.
  * one POINT PER RULE, in point order (3.3: "one point per rule, ordered"),
    carrying `pc_slot`, `pc_select`, `pc_modules`, `pc_cond`, `pc_scope`,
    `pc_weights` and the `pc_vexpr` escape hatch.

DECISIONS TAKEN HERE (recorded in polychain.md 10):

  D76 `pc_modules` is a SPACE-SEPARATED STRING, matching `pc_role` in the kit
      manifest (3.2: "One module may carry several (space-separated)"). One
      convention for one kind of list across both payloads beats two. A string
      ARRAY attribute is also accepted on read, because a generator upstream
      may find that easier to author; it is never written.
  D77 A payload OVERRIDES THE PARMS ENTIRELY (2.1's own words), so the parms
      are not merged into it key by key: what the payload does not say takes
      the KERNEL DEFAULT, not whatever the node happened to be set to. The
      alternative - merging - makes the same payload produce different
      geometry on two nodes, which is exactly the property the pipeline face
      exists to guarantee. `write()` always emits the full params dict, so a
      round-tripped style is unaffected either way.
  D78 A MALFORMED RULE DEGRADES, IT DOES NOT DISAPPEAR SILENTLY. Unknown
      select mode -> `first` (the `Rule` constructor's own degrade) and a
      warning; empty `pc_modules` -> the slot's own role is resolved instead
      (`plan.candidates` already does this) and a warning; a module no kit
      knows -> kept, so 3.4's stand-in box is built and `pc_warn_kit_gap`
      rides the element, plus a warning here. The ONE case that is dropped is
      a rule with no usable slot, because a slot nothing reads is a rule that
      cannot degrade into anything - and it is warned by name.
  D92 A PAYLOAD THAT LOSES EVERY RULE DEGRADES *WITHIN* THE PIPELINE FACE.
      `read` used to return None there, which is D34's "input 3 is unwired"
      answer - and a WIRED input that lost its rules is not an unwired one.
      It returns a rule-less `Style` carrying the payload's own styleId, seed
      and params instead, so the node builds nothing and says so rather than
      building a convincing parm-face fence under the pipeline's nose.
  D93 A MARKER SLOT'S ID IS PARSED, NOT JUST PREFIX-MATCHED. `marker:gate`
      used to validate clean and place nothing; it is kept (warn-never-block)
      and named.
  D79 The conditional is NOT re-implemented here. `pc_cond` is read as the
      `{subject, op, value}` dict `plan.evaluate_cond` already takes, and this
      file only VALIDATES it - unknown subject and unknown op are exactly the
      two inputs that make that evaluator return False for every piece, i.e.
      the rule silently declines, which is the failure mode 3.3's
      warn-never-block rule is aimed at.
"""

import hou

from . import (DEFAULTS, SELECTORS, SLOTS, WARN_PAYLOAD_MALFORMED,
               Params, Rule, Style)
from . import plan as _plan

STYLE_DETAIL = "pc_style_meta"

# 3.3 + 7.3.2's WHOLE top-level vocabulary, in one place so the reader can name
# what it does not know (D300). `styleId`/`version`/`seed`/`params` are 3.3's;
# `y_params`/`y_mode`/`clip` are 7.3.2's second axis. A name added to the
# payload without a line here is refused, which is the point.
META_KEYS = ("clip", "params", "seed", "styleId", "version", "y_mode",
             "y_params")

# The rule schema, in one list so the writer, the reader and any future
# validator cannot disagree about it: (attribute, default).
RULE_ATTRS = (
    ("pc_slot", ""),
    ("pc_select", "first"),
    ("pc_modules", ""),
    ("pc_cond", {}),
    ("pc_scope", "segment"),
    ("pc_weights", {}),
    ("pc_vexpr", ""),
    # 7.3.2 / D120 - ONE payload, two axes, and one rule scoped to one row
    # class. Both default to "the payload did not say", so every phase-1
    # payload round-trips unchanged and reads as an X payload matching every
    # row.
    ("pc_axis", "x"),
    ("pc_yclass", ""),
)

# Every `Params` field, derived from the object rather than listed - a parm
# added to 5 must not need a second edit here to survive a round trip.
PARAM_KEYS = tuple(sorted(vars(DEFAULTS).keys()))


def _plain(value):
    """A Houdini attribute value as something `Params`/`Rule` can eat.

    A dict attribute hands back `hou.Vector2`/`Vector3` for a list of two or
    three numbers (measured on 22.0.398), which is fine for `conform_axis` and
    wrong for everything that compares equal to a tuple.
    """
    if isinstance(value, (hou.Vector2, hou.Vector3, hou.Vector4)):
        return tuple(float(v) for v in value)
    if isinstance(value, (list, tuple)):
        return tuple(_plain(v) for v in value)
    return value


def params_to_dict(params):
    return dict((k, list(v) if isinstance(v, tuple) else v)
                for k, v in vars(params).items())


def params_from_dict(data, warns=None):
    """A params dict -> `Params`, degrading per key (D78, warn-never-block).

    The `Params` constructor is the validator - it already clamps every
    vocabulary field to a documented default (D6, D17, D51) - so the only work
    here is to keep ONE unreadable key from costing the whole payload its
    parameters. A key that raises is dropped, named, and the rest survive.
    """
    warns = warns if warns is not None else []
    kw = {}
    for key in sorted(data or {}):
        if key not in PARAM_KEYS:
            warns.append("pc_style_meta.params: unknown key %r ignored" % key)
            continue
        kw[key] = _plain(data[key])
    rejected = set()
    try:
        params = Params(**kw)
    except Exception:
        good = {}
        for key in sorted(kw):
            try:
                Params(**{key: kw[key]})
                good[key] = kw[key]
            except Exception as exc:
                rejected.add(key)
                warns.append("pc_style_meta.params: %s=%r rejected (%s)"
                             % (key, kw[key], type(exc).__name__))
        params = Params(**good)
    # ...and say so when the constructor QUIETLY coerced a vocabulary field.
    # `Params` degrades an unknown `fill`/`justify`/`zmode`/`corner_mode` to
    # its documented default by design (D6, D51) - which is right, and which
    # is also how a case-slipped "Vertical" in a payload gets to change every
    # piece without a word. Only string fields are compared, so the numeric
    # normalisations (`fillet_segments` rounding to even, `conform_axis`
    # becoming a unit-checked tuple) do not warn about doing their job.
    for key in sorted(kw):
        if key in rejected:
            continue                 # already named above; one fault, one line
        if isinstance(kw[key], str) and getattr(params, key, None) != kw[key]:
            warns.append("pc_style_meta.params: %s=%r is not a known value - "
                         "using %r" % (key, kw[key], getattr(params, key, None)))
    return params


# --- writing ---------------------------------------------------------------

def _ensure(geo, cls, name, default):
    if cls == hou.attribType.Global:
        found = geo.findGlobalAttrib(name)
    else:
        found = geo.findPointAttrib(name)
    return found or geo.addAttrib(cls, name, default)


def write(geo, style):
    """`style` as a 3.3 payload on `geo`. The inverse of `read`."""
    _ensure(geo, hou.attribType.Global, STYLE_DETAIL, {})
    meta = dict(getattr(style, "meta", None) or {})
    meta.update({
        "styleId": str(style.style_id),
        "version": int(style.version),
        "seed": int(style.seed),
        "params": params_to_dict(style.params or DEFAULTS)})
    geo.setGlobalAttribValue(STYLE_DETAIL, meta)
    for name, default in RULE_ATTRS:
        _ensure(geo, hou.attribType.Point, name, default)
    for rule in style.rules:
        pt = geo.createPoint()
        pt.setAttribValue("pc_slot", str(rule.slot))
        pt.setAttribValue("pc_select", str(rule.select))
        pt.setAttribValue("pc_modules", " ".join(str(m) for m in rule.modules))
        pt.setAttribValue("pc_cond", dict(rule.cond or {}))
        pt.setAttribValue("pc_scope", str(rule.scope))
        pt.setAttribValue("pc_weights", dict(rule.weights or {}))
        pt.setAttribValue("pc_vexpr", str(rule.vexpr or ""))
        pt.setAttribValue("pc_axis", str(getattr(rule, "axis", "x")))
        pt.setAttribValue("pc_yclass", str(getattr(rule, "yclass", "")))
    return geo


# --- reading ---------------------------------------------------------------

def _sattr(pt, name, default=""):
    a = pt.geometry().findPointAttrib(name)
    if a is None:
        return default
    return pt.attribValue(name)


def _dattr(pt, name):
    a = pt.geometry().findPointAttrib(name)
    if a is None:
        return {}
    value = pt.attribValue(name)
    return dict(value) if isinstance(value, dict) else {}


def _modules(pt):
    """D76 - space-separated string, or a string array from a generator."""
    raw = _sattr(pt, "pc_modules", "")
    if isinstance(raw, (list, tuple)):
        return [str(m) for m in raw if str(m).strip()]
    return [m for m in str(raw).split() if m]


def _check_slot(slot, warns, index):
    if slot.startswith("marker:"):
        # D93: the kernel only ever emits `marker:%d` (`plan.plan_section`),
        # so `marker:gate` - an author who reached for the module name where
        # an id belongs - matches nothing and places nothing. Kept, because
        # warn-never-block, and named, because a rule that can never fire is
        # exactly what D78's contract says must not be silent.
        # ⚠️ AND `int()` IS TOO GENEROUS TO BE THE TEST, which is a warning
        # divergence between the two faces.  The kernel emits `marker:%d`, so
        # `marker:03`, `marker:+3` and `marker: 3` match NOTHING on either
        # path - but Python's `int()` parses all three, so
        # `hda._warn_unread_markers` counted id 3 as READ and the reference
        # said nothing at all, while `pc_sections.vfl`'s VEX (`tail !=
        # itoa(atoi(tail))`, which is the canonical test) said the markers
        # were unread.  Two paths, two answers, and the SILENT one was the
        # wrong one: it suppressed the warning for a rule that can never fire,
        # which is exactly what D93 says must not be silent.  Asking for the
        # CANONICAL form here warns on the rule itself, which is the honest
        # sentence, and it makes `_native_ok` refuse the build (it refuses on
        # any style warning), so the two faces agree by construction.
        tail = slot[7:]
        try:
            canonical = str(int(tail)) == tail
        except ValueError:
            canonical = False
        if not canonical:
            warns.append("rule %d: pc_slot %r - a marker id is an INTEGER "
                         "(pc_marker_id) written plainly, so this rule can "
                         "never fire; the kernel only ever emits 'marker:%%d'"
                         % (index, slot))
        return True
    if slot in SLOTS:
        return True
    if not slot:
        warns.append("rule %d: no pc_slot - rule dropped" % index)
    else:
        warns.append("rule %d: unknown pc_slot %r - rule dropped (known: %s, "
                     "marker:<id>)" % (index, slot, ", ".join(SLOTS)))
    return False


def _check_cond(cond, select, warns, index):
    """D79 - validate the dict the kernel's own evaluator will read."""
    if not cond:
        if select == "conditional":
            warns.append("rule %d: pc_select conditional with no pc_cond - "
                         "the condition is always true" % index)
        return
    if select != "conditional":
        warns.append("rule %d: pc_cond is ignored, pc_select is %r not "
                     "'conditional'" % (index, select))
    subject = str(cond.get("subject", ""))
    known = (subject in _plan.COND_SUBJECTS
             or subject.startswith("markerData:") or subject.startswith("attr:"))
    if not known:
        warns.append("rule %d: unknown pc_cond subject %r - the rule will "
                     "decline every piece (known: %s, markerData:<key>, "
                     "attr:<name>)" % (index, subject,
                                       ", ".join(_plan.COND_SUBJECTS)))
    if str(cond.get("op", "eq")) not in _plan._OPS:
        warns.append("rule %d: unknown pc_cond op %r - the rule will decline "
                     "every piece (known: %s)"
                     % (index, cond.get("op"), ", ".join(sorted(_plan._OPS))))


def _int(value, default, name, warns):
    try:
        return int(value)
    except (TypeError, ValueError):
        if value is not None:
            warns.append("%s: %s=%r is not a number - using %r"
                         % (STYLE_DETAIL, name, value, default))
        return default


def read(geo, kit=None):
    """A 3.3 payload -> (`Style` or None, warnings).

    ⚠️ ONE GENERIC LOOP OVER WHATEVER ARRIVES (PC-G4). There is no style name
    in here, no table of known styles, and no branch that reads one - a rule
    is a rule.

    Returns `None` for the style when input 3 is UNWIRED or carries no rules,
    which is D34's rule again: an unconnected input is not an error, it is the
    artist face driving the node. The caller then keeps its parm-built style.
    """
    warns = []
    if geo is None:
        return (None, warns)
    points = list(geo.points())
    has_slot = geo.findPointAttrib("pc_slot") is not None
    if not points or not has_slot:
        if points or geo.findGlobalAttrib(STYLE_DETAIL) is not None:
            warns.append("input 3 carries %d points but no pc_slot attribute "
                         "- not a 3.3 style payload, ignored" % len(points))
        return (None, warns)

    meta = {}
    if geo.findGlobalAttrib(STYLE_DETAIL) is not None:
        value = geo.attribValue(STYLE_DETAIL)
        meta = dict(value) if isinstance(value, dict) else {}
    else:
        warns.append("no %s detail dict - styleId, version and seed default"
                     % STYLE_DETAIL)
    # C3a / D300 - THE ONE PAYLOAD LAYER THAT NAMED NOTHING. Every layer below
    # this says what it does not know - `params` ("unknown key %r ignored"),
    # `clip` ("is not a 7.3.2 key"), `pc_slot`, `pc_select`, `pc_weights` - and
    # the TOP LEVEL, the dict an author writes FIRST, took anything in silence.
    # The likeliest authoring error there is MIS-NESTING: `clip_mode`, `expand`
    # and `auto_align` are the 2D entry point's own KEYWORD names, so writing
    # them one level up instead of inside `clip` read as a payload that asked
    # for nothing and got the defaults, and a misspelt `y_params` lost the
    # whole Y `Params` block the same way. D294's rule, on the layer it
    # skipped. WHAT IT CANNOT SEE: a key that IS in the vocabulary carrying
    # something absurd - `payload_2d` and `params_from_dict` judge values.
    for key in sorted(k for k in meta if k not in META_KEYS):
        warns.append("%s: %s.%s is not a 3.3 or 7.3.2 key - ignored (known: "
                     "%s)" % (WARN_PAYLOAD_MALFORMED, STYLE_DETAIL, key,
                              ", ".join(sorted(META_KEYS))))
    params = params_from_dict(meta.get("params"), warns)

    rules = []
    for index, pt in enumerate(points):
        slot = str(_sattr(pt, "pc_slot", ""))
        if not _check_slot(slot, warns, index):
            continue
        # An EMPTY string is "the payload did not say", not "the payload said
        # something wrong": a point created before its attribute was set reads
        # blank rather than the attribute's declared default, so warning on it
        # would put a line in the log for every rule a generator leaves at the
        # default. Anything non-empty and unknown IS worth a line.
        select = str(_sattr(pt, "pc_select", "first")) or "first"
        if select not in SELECTORS:
            warns.append("rule %d (%s): unknown pc_select %r - using 'first' "
                         "(known: %s)"
                         % (index, slot, select, ", ".join(SELECTORS)))
        modules = _modules(pt)
        if not modules:
            warns.append("rule %d (%s): empty pc_modules - the slot's own "
                         "role is resolved instead" % (index, slot))
        cond = _dattr(pt, "pc_cond")
        _check_cond(cond, select, warns, index)
        vexpr = str(_sattr(pt, "pc_vexpr", ""))
        if vexpr:
            warns.append("rule %d (%s): pc_vexpr is accepted and IGNORED in "
                         "phase 1 (D3); every element it touches says "
                         "pc_warn_vexpr_ignored" % (index, slot))
        weights = dict(_dattr(pt, "pc_weights"))
        for name in sorted(weights):
            if name not in modules:
                warns.append("rule %d (%s): pc_weights names %r, which is not "
                             "in pc_modules" % (index, slot, name))
        if kit is not None:
            for name in modules:
                if kit.by_name(name) is None and not kit.by_role(name):
                    warns.append("rule %d (%s): kit %r has no module or role "
                                 "%r - a stand-in box will be built"
                                 % (index, slot, kit.kit_id, name))
        yclass = str(_sattr(pt, "pc_yclass", ""))
        if yclass and yclass not in SLOTS and not yclass.startswith("marker:"):
            warns.append("rule %d (%s): unknown pc_yclass %r - the rule is "
                         "scoped to a row class no solve can produce (known: "
                         "%s, marker:<id>)" % (index, slot, yclass,
                                               ", ".join(SLOTS)))
        rules.append(Rule(slot, select, modules, cond or None,
                          str(_sattr(pt, "pc_scope", "segment")) or "segment",
                          weights, vexpr, yclass,
                          str(_sattr(pt, "pc_axis", "x")) or "x"))

    if not rules:
        # D92: DEGRADE WITHIN THE PIPELINE FACE, never across to the other
        # one. Returning None here sent the caller back to the PARM face, so
        # a generator that misspelled every `pc_slot` got a plausible
        # parm-built fence with parm-derived ids and the parm `styleId` -
        # convincing, wrong, and keyed to nothing a downstream override map
        # would match. An empty rule list keeps the payload's own meta and
        # trips `cook`'s "no modules assigned" instead, so the output is
        # visibly empty rather than quietly someone else's.
        warns.append("style payload carries no usable rule - the node builds "
                     "nothing (it does NOT fall back to the parms)")
        return (Style(str(meta.get("styleId", "")),
                      _int(meta.get("version"), 1, "version", warns),
                      _int(meta.get("seed"), 0, "seed", warns), [], params,
                      meta),
                warns)
    return (Style(str(meta.get("styleId", "")), _int(meta.get("version"), 1, "version", warns),
                  _int(meta.get("seed"), 0, "seed", warns), rules, params,
                  meta),
            warns)
