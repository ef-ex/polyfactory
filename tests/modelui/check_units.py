"""Headless checks of modelUI's small contracts (keys record, filter construction), each with a paired source mutation.

Run:  hython tests/modelui/check_units.py      (exit 0 = all green AND every mutation reddened its paired check)
Mutations are source edits exec'd into the live module and restored afterwards.

What these cannot see: the real hou.hotkeys (a fake stands in; the GUI runner checks the real one), Qt events.
"""
import gc
import os
import sys

import hou

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import input_layer, keys  # noqa: E402

ST = keys.STATE


class FakeHotkeys:
    """assignments per (context, symbol); conflicts = same key in the same context; removals listed in fail_remove
    are refused (return False), as Houdini does for a binding it will not drop."""

    def __init__(self, fail_remove=()):
        self.a = {(ST, ST + ".new_scale"): ["E"], (ST, ST + ".new_rotate"): ["R"]}   # Houdini's defaults
        self.fail_remove = set(fail_remove)

    def assignments(self, ctx, sym):
        return tuple(self.a.get((ctx, sym), ()))

    def findConflicts(self, ctx, sym, key):  # noqa: N802
        return ["%s?%s" % (c, s) for (c, s), ks in self.a.items() if c == ctx and s != sym and key in ks]

    def addAssignment(self, ctx, sym, key):  # noqa: N802
        self.a.setdefault((ctx, sym), []).append(key)
        return True

    def removeAssignment(self, ctx, sym, key):  # noqa: N802
        ks = self.a.get((ctx, sym), [])
        if (ctx, sym, key) in self.fail_remove or key not in ks:
            return False
        ks.remove(key)
        return True


def checks():
    out = {}
    rec = keys._changes()
    del rec[:]
    H = FakeHotkeys(fail_remove={(ST, ST + ".new_move", "W")})
    keys.apply(H)
    n_applied = len(rec)
    n = keys.revert(H)
    out["revert_keeps_failed"] = rec == [("add", ST, ST + ".new_move", "W")] and n == n_applied - 1

    del rec[:]
    H = FakeHotkeys()
    keys.apply(H)
    first = {k: list(v) for k, v in H.a.items()}
    H.a[(ST, ST + ".new_move")].remove("W")      # the live keys changed under a record that was never reverted
    keys.apply(H)
    out["apply_after_leftover_record"] = H.a == first and len(rec) == len(set(rec))
    keys.revert(H)
    out["revert_restores_defaults"] = H.a.get((ST, ST + ".new_scale")) == ["E"] and not rec

    seen = []
    old_hook, sys.unraisablehook = sys.unraisablehook, (lambda u: seen.append(u.exc_type.__name__))
    old_lib, input_layer.LIB = input_layer.LIB, os.path.join(os.path.dirname(input_layer.LIB), "missing.dll")
    try:
        try:
            input_layer._AppFilter(object())
        except OSError:
            pass
        gc.collect()
    finally:
        sys.unraisablehook, input_layer.LIB = old_hook, old_lib
    out["appfilter_failed_init_quiet"] = seen == []
    del rec[:]
    return out


def mutate(mod, old, new):
    path = mod.__file__
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if src.count(old) != 1:
        raise RuntimeError("mutation snippet not found exactly once: %r" % old)
    exec(compile(src.replace(old, new), path, "exec"), mod.__dict__)
    return lambda: exec(compile(src, path, "exec"), mod.__dict__)


MUTATIONS = [   # (name, check, module, old, new)
    ("revert_ignores_result", "revert_keeps_failed", keys, "            ok = present != (op == \"add\") or undo(ctx, sym, key)   # already in the undone state counts",
     "            undo(ctx, sym, key)\n            ok = True"),
    ("leftover_noop", "apply_after_leftover_record", keys, "        revert(H)\n        if changes:\n            raise",
     "        return\n        if changes:\n            raise"),
    ("revert_does_nothing", "revert_restores_defaults", keys, "    while changes:\n        op, ctx, sym, key = changes.pop()",
     "    changes.clear()\n    while changes:\n        op, ctx, sym, key = changes.pop()"),
    ("detach_assumes_handle", "appfilter_failed_init_quiet", input_layer, 'if getattr(self, "handle", None):', "if self.handle:"),
]


def run():
    try:
        return checks()
    except Exception as e:  # noqa: BLE001 - an exception is a red check
        return {"_exception": "%s: %s" % (type(e).__name__, e)}


def main():
    base = run()
    bad = [k for k, v in base.items() if v is not True]
    for k, v in base.items():
        print("%-30s %s" % (k, "ok" if v is True else "RED %s" % v))
    names = set(base)
    for name, check, mod, old, new in MUTATIONS:
        restore = mutate(mod, old, new)
        try:
            res = run()
        finally:
            restore()
        red = res.get(check) is not True
        print("mutation %-24s -> %-30s %s" % (name, check, "red (good)" if red else "STILL GREEN"))
        if not red:
            bad.append("mutation " + name)
        names.discard(check)
    if names:
        print("checks without a mutation:", sorted(names))
        bad.append("unpaired checks")
    print("FAIL" if bad else "PASS", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
