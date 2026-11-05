"""Headless checks of the modelUI scene model (ObjectScene), each paired with a mutation that must turn it red.

Run:  hython tests/modelui/check_scene_model.py      (exit 0 = baseline green AND every mutation reddened its check)
Throwaway session, never saves a .hip. Mutations are monkeypatches of polyfactory.modelui.scene applied in-process,
one at a time, then restored.

What these cannot see: the GUI (viewport selection, the panel), packed-piece backends, nested objects (only /obj's
direct children are pieces), and the timing/coalescing of notifications (only that they arrive).
"""
import os
import sys

import hou

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import scene  # noqa: E402


def build():
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj")
    geos = [obj.createNode("geo", n) for n in ("a", "b", "c")]
    obj.createNode("null", "not_a_piece")
    obj.createNode("cam", "cam1")
    return geos


def checks():
    out = {}
    a, b, c = build()
    s = scene.ObjectScene()
    hits = []
    s.watch(lambda: hits.append(1))
    ids = [n.sessionId() for n in (a, b, c)]
    out["pieces_are_the_geo_objects"] = s.pieces() == ids and [s.name(i) for i in ids] == ["a", "b", "c"]

    n0 = len(hits)
    got = s.rename(ids[0], "hull")
    clash = s.rename(ids[1], "hull")
    out["rename_unique"] = got == "hull" == a.name() and clash == b.name() and clash != "hull"
    out["watch_rename"] = len(hits) > n0
    hou.undos.performUndo()
    out["rename_undoable"] = b.name() == "b"

    a.setSelected(True)
    n0 = len(hits)
    s.select([ids[1]])
    out["select_replaces"] = s.selected() == [ids[1]] and b.isSelected() and not a.isSelected()
    n0 = len(hits)
    s.select([])   # a pure deselect fires only ChildSelectionChanged (a select also fires ChildSwitched)
    out["watch_selection"] = len(hits) > n0 and s.selected() == []

    n0 = len(hits)
    s.set_hidden([ids[2]], True)
    hidden_ok = s.hidden(ids[2]) and not c.isDisplayFlagSet()
    s.set_hidden([ids[2]], False)
    out["hide_show"] = hidden_ok and not s.hidden(ids[2]) and c.isDisplayFlagSet()
    out["watch_flag"] = len(hits) > n0

    n0 = len(hits)
    d = hou.node("/obj").createNode("geo", "d")
    out["watch_create"] = len(hits) > n0 and d.sessionId() in s.pieces()
    n0 = len(hits)
    d.setName("d2")
    out["watch_rename_new_piece"] = len(hits) > n0

    n0 = len(hits)
    s.delete([ids[0]])
    out["delete"] = hou.nodeBySessionId(ids[0]) is None and ids[0] not in s.pieces() and len(s.pieces()) == 3
    out["watch_delete"] = len(hits) > n0
    hou.undos.performUndo()
    out["delete_undoable"] = len(s.pieces()) == 4

    s.unwatch(s._watchers[0])
    nodes = [hou.node("/obj")] + list(hou.node("/obj").children())
    out["unwatch_stops"] = not any(cb[1] == s._event for n in nodes for cb in n.eventCallbacks())
    return out


def _patch(obj, name, value):
    old = getattr(obj, name)
    setattr(obj, name, value)
    return lambda: setattr(obj, name, old)


# mutation -> (the check it must redden, the patch)
MUTATIONS = {
    "no_type_filter": ("pieces_are_the_geo_objects",
                       lambda: _patch(scene.ObjectScene, "_geos", lambda self: list(hou.node(self.root).children()))),
    "rename_not_unique": ("rename_unique", lambda: _patch(scene.ObjectScene, "rename",
                          lambda self, pid, name: (self._node(pid).setName(name), self._node(pid).name())[1])),
    "rename_no_undo_group": ("rename_undoable", lambda: _patch(scene.ObjectScene, "rename",
                             lambda self, pid, name: _no_undo(lambda: self._node(pid).setName(name, unique_name=True))
                             or self._node(pid).name())),
    "select_adds": ("select_replaces", lambda: _patch(scene.ObjectScene, "select",
                    lambda self, pids: [self._node(p).setSelected(True) for p in pids])),
    "hide_noop": ("hide_show", lambda: _patch(scene.ObjectScene, "set_hidden", lambda self, pids, hide: None)),
    "no_piece_events": ("watch_rename", lambda: _patch(scene, "_PIECE_EVENTS", ())),
    "no_selection_event": ("watch_selection", lambda: _patch(scene, "_OBJ_EVENTS", (
        hou.nodeEventType.ChildCreated, hou.nodeEventType.ChildDeleted))),
    "no_create_event": ("watch_create", lambda: _patch(scene, "_OBJ_EVENTS", (
        hou.nodeEventType.ChildDeleted, hou.nodeEventType.ChildSelectionChanged))),
    "no_delete_event": ("watch_delete", lambda: _patch(scene, "_OBJ_EVENTS", (
        hou.nodeEventType.ChildCreated, hou.nodeEventType.ChildSelectionChanged))),
    "no_flag_event": ("watch_flag", lambda: _patch(scene, "_PIECE_EVENTS", (hou.nodeEventType.NameChanged,))),
    "delete_no_undo_group": ("delete_undoable", lambda: _patch(scene.ObjectScene, "delete",
                             lambda self, pids: _no_undo(lambda: [self._node(p).destroy() for p in pids]))),
    "new_piece_not_armed": ("watch_rename_new_piece", lambda: _patch(scene.ObjectScene, "_event",
                            lambda self, event_type, **kw: self._notify())),
    "delete_noop": ("delete", lambda: _patch(scene.ObjectScene, "delete", lambda self, pids: None)),
    "unwatch_keeps_callbacks": ("unwatch_stops", lambda: _patch(scene.ObjectScene, "_arm",
                                _arm_only_on)),
}


def _no_undo(fn):
    with hou.undos.disabler():
        fn()


_orig_arm = scene.ObjectScene._arm


def _arm_only_on(self, on):
    if on:
        _orig_arm(self, on)


def run(fn):
    try:
        return fn()
    except Exception as e:  # noqa: BLE001 - an exception is a red check
        return {"_exception": "%s: %s" % (type(e).__name__, e)}


def main():
    base = run(checks)
    bad = [k for k, v in base.items() if v is not True]
    for k, v in base.items():
        print("%-28s %s" % (k, "ok" if v is True else "RED %s" % v))
    names = set(base)
    for mut, (check, patch) in MUTATIONS.items():
        undo = patch()
        try:
            res = run(checks)
        finally:
            undo()
        red = res.get(check) is not True
        print("mutation %-26s -> %-28s %s" % (mut, check, "red (good)" if red else "STILL GREEN"))
        if not red:
            bad.append("mutation " + mut)
        names.discard(check)
    if names:
        print("checks without a mutation:", sorted(names))
        bad.append("unpaired checks")
    print("FAIL" if bad else "PASS", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    code = main()
    sys.stdout.flush()
    sys.exit(code)
