"""Run-time hotkeys of the modeling mode: applied with ``hou.hotkeys`` and reverted exactly.

Nothing is saved: ``addAssignment`` / ``removeAssignment`` change memory only (``saveOverrides()`` would write the
overrides file and is never called), and no keymap file is selected (that choice lives in ``hotkeys.pref``).
``apply()`` records every add/remove, ``revert()`` undoes exactly that, newest first. Pattern: the Maya surface
project's ``keymap.py``.
"""
import logging

LOG = logging.getLogger(__name__)

STATE = "h.pane.gview.state"   # every viewer state
# (context, action symbol, key): 3ds Max transform keys; a symbol starting with "-" removes that binding instead.
KEYS = [
    (STATE, STATE + ".new_select", "Q"),
    # a "-" row unbinds: Houdini's own Q (repeat current tool) in the parent context wins over ours in "pose" once the
    # scene has objects, on any desk and for any select action (probe: tests/modelui/keys_probe.py)
    ("h.pane.gview", "-h.pane.gview.repeat_current", "Q"),
    (STATE, STATE + ".new_move", "W"),
    (STATE, STATE + ".new_rotate", "E"),
    (STATE, STATE + ".new_scale", "R"),
]


def _changes():
    """The change record, on ``hou.session`` so a module reload cannot lose what must be reverted."""
    import hou
    return hou.session.__dict__.setdefault("_pf_modelui_key_changes", [])


def apply(H=None):
    """Apply KEYS. A key first loses its other bindings in the same context. Raises when a row could not be applied
    (the switch then rolls back, which reverts the rows that were)."""
    import hou
    H = H or hou.hotkeys
    changes, failed = _changes(), []
    if changes:
        # a record left by an apply that was never reverted: undo it first, so the record matches the live keys
        revert(H)
        if changes:
            raise RuntimeError("modelUI keys: %d earlier change(s) could not be reverted" % len(changes))
    for ctx, sym, key in KEYS:
        if sym.startswith("-"):
            if key in H.assignments(ctx, sym[1:]) and H.removeAssignment(ctx, sym[1:], key):
                changes.append(("remove", ctx, sym[1:], key))
            continue
        for other in H.findConflicts(ctx, sym, key):
            octx, _, osym = other.partition("?")
            if octx == ctx and osym != sym and key in H.assignments(ctx, osym) and H.removeAssignment(ctx, osym, key):
                changes.append(("remove", ctx, osym, key))
        if key in H.assignments(ctx, sym):
            continue
        if H.addAssignment(ctx, sym, key):
            changes.append(("add", ctx, sym, key))
        else:
            failed.append("%s %s" % (sym, key))
    if failed:
        raise RuntimeError("modelUI keys not applied: " + ", ".join(failed))


def revert(H=None):
    """Undo ``apply()`` exactly, newest first. Returns the number of changes undone; a change that could not be undone
    is logged and stays in the record."""
    import hou
    H = H or hou.hotkeys
    changes, n, kept = _changes(), 0, []
    while changes:
        op, ctx, sym, key = changes.pop()
        try:
            undo = H.removeAssignment if op == "add" else H.addAssignment
            present = key in H.assignments(ctx, sym)
            ok = present != (op == "add") or undo(ctx, sym, key)   # already in the undone state counts
        except Exception:  # noqa: BLE001 - revert the rest
            LOG.exception("key revert raised: %s %s %s %s", op, ctx, sym, key)
            ok = False
        if ok:
            n += 1
        else:
            LOG.error("modelUI key change not reverted: %s %s %s %s", op, ctx, sym, key)
            kept.append((op, ctx, sym, key))
    changes.extend(reversed(kept))
    return n


def snapshot(H=None):
    """Every assignment of the contexts KEYS touches, {"ctx?symbol": sorted keys}: equal before and after = exact."""
    import hou
    H = H or hou.hotkeys
    out = {}
    for ctx in sorted({c for c, _, _ in KEYS}):
        for b in H.commandBindingsInContext(ctx):
            keys = tuple(sorted(H.assignments(ctx, b["symbol"])))
            if keys:
                out["%s?%s" % (ctx, b["symbol"])] = keys
    return out


install, uninstall = apply, revert   # switch feature hooks
