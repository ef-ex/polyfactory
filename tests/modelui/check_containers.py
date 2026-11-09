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
from polyfactory.modelui import containers, pieces_ui, scene  # noqa: E402

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
    out["container_not_selectable"] = not c.isSelectableInViewport()
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

    with hou.undos.disabler():   # a moved and rotated container: promote must keep the WORLD transform
        c.parmTuple("t").set((3, 1, -2))
        c.parmTuple("r").set((0, 30, 0))
    m_p = containers.transform(c, ids[1]) * c.worldTransform()
    pobj = containers.promote(c, ids[1])
    ppath = pobj.path()
    rows = [r[0] for r in containers.piece_rows(c)]
    out["promote_makes_object"] = (pobj.type().name() == "geo" and mclose(pobj.worldTransform(), m_p)
                                   and ids[1] not in rows and pobj.node("source").parm("filepath1").eval() == FILES[1]
                                   and len(pobj.displayNode().geometry().points()) > 0)
    hou.undos.performUndo()
    out["promote_one_undo"] = hou.node(ppath) is None and ids[1] in [r[0] for r in containers.piece_rows(c)]
    pid1 = ("piece", c.sessionId(), ids[1])
    mw = xf((7, 2, 1), (10, 20, 30), (1.5, 1.5, 1.5))
    pieces_ui.set_xform(pid1, mw)
    pr1 = [p for p in prims(c) if p.attribValue("pf_piece") == ids[1]][0]
    out["world_xform_roundtrip"] = (mclose(pieces_ui.get_xform(pid1), mw)
                                    and mclose(pr1.fullTransform() * c.worldTransform(), mw))
    with hou.undos.disabler():
        c.parmTuple("t").set((0, 0, 0))
        c.parmTuple("r").set((0, 0, 0))
    containers.set_transforms(c, {ids[1]: m1})
    c2 = containers.create("broken")
    containers.add_pieces(c2, [(FILES[0], "x", None)])
    c2.node("pieces").destroy()
    try:
        listed = scene.MixedScene().pieces()
        out["broken_container_skipped"] = not any(isinstance(p, tuple) and p[1] == c2.sessionId() for p in listed)
    except Exception:  # noqa: BLE001 - the whole scene failing is the defect
        out["broken_container_skipped"] = False
    c2.destroy()
    u0 = [n for n in c.children() if n.type().name() == "usdimport" and n.parm("filepath1").eval() == FILES[0]][0]
    u0.destroy()   # by hand: the pieces of FILES[0] lose their geometry
    containers.add_pieces(c, [(FILES[0], "again", None)])
    want_n = sum(1 for _, s_, _ in [(0, p.attribValue("pf_source"), 0) for p in containers.stash(c).geometry().points()] if s_ == FILES[0])
    got_n = sum(1 for p in prims(c) if p.attribValue("pf_source") == FILES[0])
    out["broken_chain_repaired"] = want_n == got_n and want_n > 0
    hou.undos.performUndo()

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
        for n_bulk in (2000, 5000):
            hou.hipFile.clear(suppress_save_prompt=True)
            cb = containers.create("bulk")
            items = [(FILES[i % len(FILES)], "b%d" % i, xf((i % 70, 0, i // 70))) for i in range(n_bulk)]
            t = time.perf_counter()
            containers.add_pieces(cb, items)
            out_t = time.perf_counter() - t
            out.setdefault("_bulk", {})[n_bulk] = out_t
        print("  bulk add (605 files, no cook): 2000 %.2f s, 5000 %.2f s" % (out["_bulk"][2000], out["_bulk"][5000]))
        bulk = out.pop("_bulk")
        # ~3x the measured 0.90 s / 1.01 s (2026-11-06; the audit's quadratic version: 18.2 s for 5000)
        out["perf_bulk_add"] = bulk[2000] < 3.0 and bulk[5000] < 3.5
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


C, S, P = containers, scene, pieces_ui
MUTATIONS = [   # (name, check, module, old, new)
    ("no_source_on_point", "add_pieces_places", C, 'p.setAttribValue("pf_source", path.replace("\\\\", "/"))', 'p.setAttribValue("pf_source", "")'),
    ("chain_per_piece", "one_source_chain_per_file", C, "    if path in packs:\n        return", "    if False:\n        return"),
    ("rotate_order_mismatch", "transform_roundtrip", C, 'hou.hmath.buildRotate(parts["rotate"])', 'hou.hmath.buildRotate(parts["rotate"], "zyx")'),
    ("commit_no_undo", "transform_one_undo_step", C, '    with hou.undos.group("modelUI: " + label):\n        stash(container).parm("stash").set(geo)',
     '    with hou.undos.disabler():\n        stash(container).parm("stash").set(geo)'),
    ("copy_keeps_name", "copy_piece", C, 'p.setAttribValue("pf_name", _unique_name(names, src.stringAttribValue("pf_name")))',
     'p.setAttribValue("pf_name", src.stringAttribValue("pf_name"))'),
    ("hide_ignored", "hide_show", C, '"if (i@pf_hidden) removepoint(0, @ptnum);"', '"// hide ignored"'),
    ("rename_not_unique", "rename_unique", C, "    name = _unique_name(names, name)\n    p.setAttribValue", "    p.setAttribValue"),
    ("promote_ignores_container", "promote_makes_object", C, "        m = transform(container, piece) * container.worldTransform()", "        m = transform(container, piece)"),
    ("world_xform_local", "world_xform_roundtrip", P, "        containers.set_transforms(c, {piece: m * c.worldTransform().inverted()})", "        containers.set_transforms(c, {piece: m})"),
    ("broken_container_listed", "broken_container_skipped", C, "    return [] if r is None else [n for n in r.children() if is_intact(n)]", "    return [] if r is None else [n for n in r.children() if is_container(n)]"),
    ("broken_chain_kept", "broken_chain_repaired", C, "        if ac is None or not ac.inputs() or ac.inputs()[0] is None:", "        if False:"),
    ("bulk_add_rescans", "perf_bulk_add", C, "            _ensure_source(container, path, packs)", "            _ensure_source(container, path, _source_packs(container))"),
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
    ("promote_keeps_point", "promote_makes_object", C, '        geo.deletePoints([p])\n        _commit(container, geo, "promote")', '        _commit(container, geo, "promote")'),
    ("promote_split_undo", "promote_one_undo", C, '    with hou.undos.group("modelUI: promote"):', '    if True:'),
    ("container_selectable", "container_not_selectable", C, "        obj.setSelectableInViewport(False)", "        pass"),
    ("display_not_set", "create_layout", C, "        cp.setDisplayFlag(True)", "        pass"),
    ("select_mixed_drops_pieces", "mixed_select_mixed", S, "        super().select([p for p in pids if not isinstance(p, tuple)])\n        if pieces != self._piece_sel:",
     "        super().select([p for p in pids if not isinstance(p, tuple)])\n        pieces = set()\n        if pieces != self._piece_sel:"),
    ("commit_reloads_sources", "perf_2000_edits_under_50ms", C, '        stash(container).parm("stash").set(geo)',
     '        stash(container).parm("stash").set(geo)\n        [n.parm("reload").pressButton() for n in container.children() if n.type().name() == "usdimport"]'),
    ("rows_never_cached", "perf_2000_listing", S, "        if hit is None or hit[0] != st.cookCount():", "        if True:"),
]
PERF = {"perf_2000_edits_under_50ms", "perf_2000_listing", "perf_bulk_add"}


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
