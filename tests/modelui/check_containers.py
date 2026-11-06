"""Headless checks of modelUI containers (pieces packed in container objects) and the mixed scene backend, each with a
paired source mutation that must turn it red.

Run:  hython tests/modelui/check_containers.py     (exit 0 = all green AND every mutation reddened its paired check)
Uses Hannes' kitbash library F:/3d/kitbashLib (two files for the logic, 50 for the 2000-piece costs: an edit's cost is
per point, not per source; the GUI benches load all 605). Throwaway session, never saves a .hip.

What these cannot see: the viewport (picking, handles, drawing), Qt, the Scene Explorer widget, costs with all 605
sources loaded (first cook), hip save/load of the stash.
"""
import glob
import os
import sys
import time

import hou

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import containers, scene  # noqa: E402

FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))
TOL = 1e-4   # float32 P/orient/scale at |values| <= 50


def mclose(a, b):
    return all(abs(x - y) <= TOL for x, y in zip(a.asTuple(), b.asTuple()))


def xf(t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
    return hou.hmath.buildScale(s) * hou.hmath.buildRotate(r) * hou.hmath.buildTranslate(t)


def prims(c):
    return c.displayNode().geometry().prims()


def checks(out, perf):
    hou.hipFile.clear(suppress_save_prompt=True)
    c = containers.create()
    out["create_layout"] = containers.is_container(c) and c.displayNode().name() == "copy" and len(prims(c)) == 0
    m0, m1, m2 = xf((1, 2, 3)), xf((10, 0, 0), (30, 45, 10), (2, 1, 0.5)), xf((-5, 1, 0), (0, 90, 0))
    ids = containers.add_pieces(c, [(FILES[0], "hull", m0), (FILES[1], "wing", m1), (FILES[0], "hull", m2)])
    ps = {p.attribValue("pf_piece"): p for p in prims(c)}
    want = {ids[0]: (FILES[0], "hull", m0), ids[1]: (FILES[1], "wing", m1), ids[2]: (FILES[0], "hull_1", m2)}
    out["add_pieces_places"] = (len(ps) == 3 and all(
        ps[i].attribValue("pf_source") == f and ps[i].attribValue("pf_name") == n and mclose(ps[i].fullTransform(), m)
        and len(ps[i].getEmbeddedGeometry().points()) > 0 for i, (f, n, m) in want.items()))
    usd = [n for n in c.children() if n.type().name() == "usdimport"]
    out["one_source_chain_per_file"] = sorted(n.parm("filepath1").eval() for n in usd) == sorted({FILES[0], FILES[1]})
    m3 = xf((4, 5, 6), (-20, 60, 135), (0.5, 3, 1))
    containers.set_transforms(c, {ids[1]: m3})
    ps = {p.attribValue("pf_piece"): p for p in prims(c)}
    out["transform_roundtrip"] = mclose(containers.transform(c, ids[1]), m3) and mclose(ps[ids[1]].fullTransform(), m3)
    hou.undos.performUndo()
    out["transform_one_undo_step"] = mclose(containers.transform(c, ids[1]), m1)
    new = containers.copy_pieces(c, [ids[1]])
    ps = {p.attribValue("pf_piece"): p for p in prims(c)}
    out["copy_piece"] = (len(ps) == 4 and new[0] not in ids and ps[new[0]].attribValue("pf_source") == FILES[1]
                         and ps[new[0]].attribValue("pf_name") not in ("wing", "hull", "hull_1")
                         and mclose(ps[new[0]].fullTransform(), m1))
    containers.set_hidden(c, [ids[0]], True)
    hidden_gone = ids[0] not in {p.attribValue("pf_piece") for p in prims(c)}
    containers.set_hidden(c, [ids[0]], False)
    out["hide_show"] = hidden_gone and ids[0] in {p.attribValue("pf_piece") for p in prims(c)}
    got = containers.rename_piece(c, ids[2], "wing")
    out["rename_unique"] = got != "wing" and containers.rename_piece(c, ids[2], "nose") == "nose"
    containers.delete_pieces(c, [new[0]])
    again = containers.add_pieces(c, [(FILES[1], "fin", None)])
    out["ids_never_reused"] = again[0] not in ids + new and len(prims(c)) == 4
    n_before = len([n for n in c.children() if n.type().name() == "usdimport"])
    containers.add_pieces(c, [(FILES[2], "new", None)])
    hou.undos.performUndo()
    out["add_is_one_undo_step"] = (len(prims(c)) == 4
                                   and len([n for n in c.children() if n.type().name() == "usdimport"]) == n_before)

    # --- the mixed scene backend (what the Scene Explorer uses) --------------------------------------------------------
    obj_piece = hou.node("/obj").createNode("geo", "loose")
    s = scene.MixedScene()
    hits = []
    s.watch(lambda: hits.append(1))
    listing = s.pieces()
    pids = [p for p in listing if isinstance(p, tuple)]
    out["mixed_lists_objects_and_pieces"] = (obj_piece.sessionId() in listing and c.sessionId() not in listing
                                            and len(pids) == 4 and s.name(("piece", c.sessionId(), ids[2])) == "nose")
    s.select([])
    n0 = len(hits)
    s.select([pids[0]])   # pieces only: no node selection changes, so only the backend itself can tell
    out["mixed_select_notifies"] = len(hits) > n0 and s.selected() == [pids[0]]
    s.select([pids[0], obj_piece.sessionId()])
    out["mixed_select_mixed"] = set(s.selected()) == {pids[0], obj_piece.sessionId()}
    n0 = len(hits)
    containers.set_transforms(c, {ids[0]: m3})
    out["mixed_stash_change_notifies"] = len(hits) > n0
    s.set_hidden([pids[1]], True)
    s.rename(pids[2], "tail")
    s.delete([pids[3]])
    out["mixed_edits"] = (s.hidden(pids[1]) and s.name(pids[2]) == "tail" and pids[3] not in s.pieces()
                          and pids[3] not in s.selected())
    s.unwatch(s._watchers[0])
    st = containers.stash(c)
    out["mixed_unwatch_clean"] = not any(cb[1] == s._event for cb in st.eventCallbacks())

    if perf:
        hou.hipFile.clear(suppress_save_prompt=True)
        big = containers.create("big")
        items = [(FILES[i % 50], "p%d" % i, xf((i % 50, 0, i // 50))) for i in range(2000)]
        t = time.perf_counter()
        bid = containers.add_pieces(big, items)
        len(prims(big))
        t_add = time.perf_counter() - t
        s2 = scene.MixedScene()

        def ms(fn):
            t = time.perf_counter()
            fn()
            return 1000 * (time.perf_counter() - t)

        move = ms(lambda: (containers.set_transforms(big, {bid[7]: xf((1, 1, 1))}), len(prims(big))))
        copy = ms(lambda: (containers.copy_pieces(big, [bid[8]]), len(prims(big))))
        sel = ms(lambda: s2.select([("piece", big.sessionId(), bid[9])]))
        listing = ms(lambda: [(s2.name(p), s2.hidden(p)) for p in s2.pieces()])
        print("  perf 2000 pieces: add all %.2f s, move one %.1f ms, copy one %.1f ms, select one %.1f ms, "
              "list names %.1f ms" % (t_add, move, copy, sel, listing))
        # target from the brief: select/move/copy one piece under ~50 ms at 2000 pieces
        out["perf_2000_edits_under_50ms"] = move < 50 and copy < 50 and sel < 50
        # the Scene Explorer's refresh (names and visibility of all pieces): 3x the measured 55 ms
        out["perf_2000_listing"] = listing < 165
    return out


def mutate(mod, old, new):
    path = mod.__file__
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if src.count(old) != 1:
        raise RuntimeError("mutation snippet not found exactly once: %r" % old)
    exec(compile(src.replace(old, new), path, "exec"), mod.__dict__)
    return lambda: exec(compile(src, path, "exec"), mod.__dict__)


C, S = containers, scene
MUTATIONS = [   # (name, check, module, old, new)
    ("no_source_on_point", "add_pieces_places", C, 'p.setAttribValue("pf_source", path.replace("\\\\", "/"))', 'p.setAttribValue("pf_source", "")'),
    ("chain_per_piece", "one_source_chain_per_file", C, "            return\n    u = container.createNode", "            pass\n    u = container.createNode"),
    ("rotate_order_mismatch", "transform_roundtrip", C, 'hou.hmath.buildRotate(parts["rotate"])', 'hou.hmath.buildRotate(parts["rotate"], "zyx")'),
    ("commit_no_undo", "transform_one_undo_step", C, '    with hou.undos.group("modelUI: " + label):\n        stash(container).parm("stash").set(geo)',
     '    with hou.undos.disabler():\n        stash(container).parm("stash").set(geo)'),
    ("copy_keeps_name", "copy_piece", C, 'p.setAttribValue("pf_name", _unique_name(geo, src.stringAttribValue("pf_name")))',
     'p.setAttribValue("pf_name", src.stringAttribValue("pf_name"))'),
    ("hide_ignored", "hide_show", C, '"if (i@pf_hidden) removepoint(0, @ptnum);"', '"// hide ignored"'),
    ("rename_not_unique", "rename_unique", C, "    name = _unique_name(geo, name)\n    p.setAttribValue", "    p.setAttribValue"),
    ("next_id_not_kept", "ids_never_reused", C, '        geo.setGlobalAttribValue("pf_next_piece", nxt)\n        _commit(container, geo, "add pieces")',
     '        _commit(container, geo, "add pieces")'),
    ("add_split_undo", "add_is_one_undo_step", C, '    with hou.undos.group("modelUI: add pieces"):\n        geo = points(container)',
     '    if True:\n        geo = points(container)'),
    ("containers_as_objects", "mixed_lists_objects_and_pieces", S, '                                     if n.type().name() == "geo" and not containers.is_container(n)]',
     '                                     if n.type().name() == "geo"]'),
    ("select_silent", "mixed_select_notifies", S, "            self._notify()   # piece selection is ours", "            pass   # piece selection is ours"),
    ("stash_not_watched", "mixed_stash_change_notifies", S, "            st.addEventCallback(_STASH_EVENTS, self._event)", "            pass"),
    ("hide_objects_only", "mixed_edits", S, "                containers.set_hidden(c, pieces, hide)", "                pass"),
    ("unwatch_keeps_stash", "mixed_unwatch_clean", S, "                    st.removeEventCallback(_STASH_EVENTS, self._event)", "                    pass"),
    ("display_not_set", "create_layout", C, "        cp.setDisplayFlag(True)", "        pass"),
    ("select_mixed_drops_pieces", "mixed_select_mixed", S, "        super().select([p for p in pids if not isinstance(p, tuple)])\n        if pieces != self._piece_sel:",
     "        super().select([p for p in pids if not isinstance(p, tuple)])\n        pieces = set()\n        if pieces != self._piece_sel:"),
    ("commit_reloads_sources", "perf_2000_edits_under_50ms", C, '        stash(container).parm("stash").set(geo)',
     '        stash(container).parm("stash").set(geo)\n        [n.parm("reload").pressButton() for n in container.children() if n.type().name() == "usdimport"]'),
    ("rows_never_cached", "perf_2000_listing", S, "        if hit is None or hit[0] != st.cookCount():", "        if True:"),
]
PERF = {"perf_2000_edits_under_50ms", "perf_2000_listing"}


def run(perf):
    out = {}
    try:
        checks(out, perf)
    except Exception as e:  # noqa: BLE001 - an exception is a red check; the checks before it keep their values
        out["_exception"] = "%s: %s" % (type(e).__name__, e)
    return out


def main():
    base = run(True)
    bad = [k for k, v in base.items() if v is not True]
    for k, v in base.items():
        print("%-32s %s" % (k, "ok" if v is True else "RED %s" % v))
    names = set(base)
    for name, check, mod, old, new in MUTATIONS:
        restore = mutate(mod, old, new)
        try:
            res = run(check in PERF)
        finally:
            restore()
        red = res.get(check) is False   # credited only when the paired check itself evaluated False
        print("mutation %-24s -> %-32s %s" % (name, check, "red (good)" if red else "NOT RED %s" % res.get("_exception", "")))
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
