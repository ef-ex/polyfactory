"""Headless checks of the modelUI modifier stack model (stack.py, operations.py), each with a paired source mutation
that must turn it red.

Run:  hython tests/modelui/check_stack.py     (exit 0 = all green AND every mutation reddened its paired check)
Throwaway session, never saves a .hip. Uses two files of Hannes' kitbash library (F:/3d/kitbashLib) for the
container piece cases.

Oracle: every geometry check compares point positions (exact floats, the same nodes cook the same numbers) against
a reference chain built by hand next to the object, never against the code under test.
What these cannot see: the Modify panel (Qt, the viewer state, the parameter editor: gui_f2c.py), Houdini's own
handle edits, hip save/load, time-dependent chains (collapse bakes the current frame), nodes with several outputs
feeding the chain from outside it (a side consumer of a collapsed entry below the collapse point keeps it alive).
"""
import glob
import os
import sys

import hou

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import containers, operations, scene, stack  # noqa: E402

FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))
PT, ED, PR = hou.geometryType.Points, hou.geometryType.Edges, hou.geometryType.Primitives


def pos(node_or_geo):
    g = node_or_geo.geometry() if isinstance(node_or_geo, hou.Node) else node_or_geo
    return [tuple(p.position()) for p in g.points()] if g is not None else None


def names(obj):
    return [n.name() for n in stack.chain(obj)]


def ref(obj, recipe):
    """A reference chain in a separate object: recipe = [(type, {parm: value})], first entry the base."""
    with hou.undos.disabler():   # never an undo entry: the checks count and undo the stack's own steps
        r = obj.parent().createNode("geo", "ref")
        prev = None
        for t, parms in recipe:
            n = r.createNode(t)
            for k, v in parms.items():
                n.parm(k).set(v)
            if prev is not None:
                n.setFirstInput(prev)
            prev = n
        out = pos(prev)
        r.destroy()
    return out


def fixture():
    hou.hipFile.clear(suppress_save_prompt=True)
    obj = hou.node("/obj").createNode("geo", "hull")
    b = obj.createNode("box", "base")
    ex = obj.createNode("polyextrude::2.0", "ex")
    ex.setFirstInput(b)
    ex.parm("group").set("0")
    ex.parm("dist").set(0.5)
    sd = obj.createNode("subdivide", "sd")
    sd.setFirstInput(ex)
    sd.setDisplayFlag(True)
    sd.setRenderFlag(True)
    return obj, b, ex, sd


BOX = ("box", {})
EX = ("polyextrude::2.0", {"group": "0", "dist": 0.5})
SD = ("subdivide", {})


def checks(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    tmp = hou.node("/obj").createNode("geo", "registry")
    # --- the registry agrees with Houdini ----------------------------------------------------------------------------
    bad = []
    for op in operations.ops():
        t = hou.nodeType(hou.nodeTypeCategories()[op["context"]], op["type"])
        if t is None:
            bad.append(op["type"])
            continue
        n = tmp.createNode(op["type"])
        parms = [g_["parm"] for g_ in op.get("groups", [])] + [g_["type_parm"] for g_ in op.get("groups", []) if g_.get("type_parm")]
        parms += list(op.get("defaults", {})) + [k for i in op.get("inputs", {}).values() for k in i.get("set", {})]
        bad += ["%s.%s" % (op["type"], p) for p in parms if n.parm(p) is None]
        bad += ["%s input %d" % (op["type"], i) for i in op.get("inputs", {}) if i >= t.maxNumInputs()]
        bad += ["%s.%s=%s" % (op["type"], k, v) for i in op.get("inputs", {}).values() for k, v in i.get("set", {}).items()
                if n.parm(k) is not None and v not in n.parm(k).parmTemplate().menuItems()]
        n.destroy()
    out["registry_matches_houdini"] = not bad and len(operations.ops()) >= 5
    if bad:
        print("  registry:", bad)
    tmp.destroy()
    obj, b, ex, sd = fixture()
    out["chain_base_first"] = names(obj) == ["base", "ex", "sd"]

    # --- add ---------------------------------------------------------------------------------------------------
    n_undo = len(hou.undos.undoLabels())
    e2 = stack.add(obj.sessionId(), "extrude", selection=("1", PR))
    out["add_on_top"] = (obj.displayNode() == e2 and e2.isRenderFlagSet() and e2.input(0) == sd
                         and pos(obj.displayNode()) == ref(obj, [BOX, EX, SD, ("polyextrude::2.0", {"group": "1", "dist": 0.1})]))
    out["add_defaults"] = e2.parm("dist").eval() == 0.1
    out["add_group_from_selection"] = e2.parm("group").eval() == "1"
    out["add_one_undo"] = len(hou.undos.undoLabels()) == n_undo + 1
    hou.undos.performUndo()
    out["add_undo_restores"] = names(obj) == ["base", "ex", "sd"] and obj.displayNode() == sd and len(obj.children()) == 3
    mid = stack.add(obj.sessionId(), "subdivide", above=b)
    out["add_above_entry"] = (names(obj) == ["base", mid.name(), "ex", "sd"] and ex.input(0) == mid
                              and pos(obj.displayNode()) == ref(obj, [BOX, SD, EX, SD]))
    hou.undos.performUndo()

    # --- group fields from a component selection ------------------------------------------------------------------
    bv = stack.add(obj.sessionId(), "bevel", above=ex, selection=("0 1", PR))
    out["group_type_parm_set"] = bv.parm("grouptype").evalAsString() == "prims" and bv.parm("group").eval() == "0 1"
    hou.undos.performUndo()
    s2 = stack.add(obj.sessionId(), "subdivide", above=b, selection=("0 1 2 3", PT))
    g = b.geometry()
    want = sorted(p.number() for p in g.prims() if any(v.point().number() in (0, 1, 2, 3) for v in p.vertices()))
    got = sorted(p.number() for p in g.globPrims(s2.parm("subdivide").eval()))
    out["group_converted_to_field_type"] = got == want and len(want) == 5
    hou.undos.performUndo()
    edn = stack.add(obj.sessionId(), "edit")
    n_undo = len(hou.undos.undoLabels())
    stack.use_selection(edn, "group", ("p0-1", ED))
    out["use_selection_one_undo"] = (edn.parm("grouptype").evalAsString() == "edges" and edn.parm("group").eval() == "p0-1"
                                     and len(hou.undos.undoLabels()) == n_undo + 1)
    hou.undos.performUndo()
    hou.undos.performUndo()

    # --- reorder --------------------------------------------------------------------------------------------------
    n_undo = len(hou.undos.undoLabels())
    moved = stack.move(ex, +1)
    out["move_up_reorders"] = (moved and names(obj) == ["base", "sd", "ex"] and obj.displayNode() == ex
                               and ex.isRenderFlagSet() and pos(obj.displayNode()) == ref(obj, [BOX, SD, EX]))
    out["move_one_undo"] = len(hou.undos.undoLabels()) == n_undo + 1
    hou.undos.performUndo()
    out["move_undo_restores"] = names(obj) == ["base", "ex", "sd"] and obj.displayNode() == sd
    out["move_base_refused"] = (not stack.move(ex, -1)) and not stack.move(b, +1) and names(obj) == ["base", "ex", "sd"]

    # --- on/off ---------------------------------------------------------------------------------------------------
    n_undo = len(hou.undos.undoLabels())
    stack.set_enabled(ex, False)
    out["off_bypasses"] = ex.isBypassed() and pos(obj.displayNode()) == ref(obj, [BOX, SD])
    out["onoff_one_undo"] = len(hou.undos.undoLabels()) == n_undo + 1
    stack.set_enabled(ex, True)
    out["on_restores"] = not ex.isBypassed() and pos(obj.displayNode()) == ref(obj, [BOX, EX, SD])
    out["base_always_on"] = not stack.set_enabled(b, False) and not b.isBypassed()

    # --- delete ---------------------------------------------------------------------------------------------------
    n_undo = len(hou.undos.undoLabels())
    stack.delete(ex)
    out["delete_rewires"] = (names(obj) == ["base", "sd"] and pos(obj.displayNode()) == ref(obj, [BOX, SD]))
    out["delete_one_undo"] = len(hou.undos.undoLabels()) == n_undo + 1
    hou.undos.performUndo()
    ex = obj.node("ex")
    stack.delete(sd)
    out["delete_top_shows_below"] = names(obj) == ["base", "ex"] and ex.isDisplayFlagSet() and ex.isRenderFlagSet()
    hou.undos.performUndo()
    sd = obj.node("sd")
    out["base_never_deleted"] = not stack.delete(b) and names(obj) == ["base", "ex", "sd"]

    # --- lattice with its own cage --------------------------------------------------------------------------------
    la = stack.add(obj.sessionId(), "lattice")
    cage = [n for n in obj.children() if n.type().name() == "edit"][0]   # found by type, not by the wiring under test
    before = pos(la)
    with hou.undos.disabler():   # what a cage edit does: move every cage point up 1
        cage.parm("group").set("*")
        cage.parm("grouptype").set("points")
        cage.parmTuple("t").set((0, 1, 0))
    after = pos(la)
    out["lattice_cage_deforms"] = (not la.errors() and cage is not None and cage.type().name() == "edit"
                                   and before is not None and after is not None and len(before) == len(after) > 0
                                   and all(abs(a[1] - b_[1] - 1) < 1e-5 and abs(a[0] - b_[0]) < 1e-5
                                           for a, b_ in zip(after, before)))
    with hou.undos.disabler():
        la.input(1).parm("divsx").set(4)
    out["lattice_divs_follow_cage"] = not la.errors() and la.parm("divsx").eval() == 4
    out["lattice_state_on_cage"] = stack.state_node(la) == cage
    n_children = len(obj.children())
    stack.delete(la)
    out["delete_takes_side_inputs"] = len(obj.children()) == n_children - 3 and names(obj) == ["base", "ex", "sd"]
    out["delete_top_shows_below"] = (out["delete_top_shows_below"] and obj.displayNode() == obj.node("sd")
                                     and obj.node("sd").isRenderFlagSet())
    hou.undos.performUndo()
    hou.undos.performUndo()

    # --- pick inputs (Object Merge) --------------------------------------------------------------------------------
    spine = hou.node("/obj").createNode("geo", "spine")
    ln = spine.createNode("line")
    ln.parm("dist").set(2)
    with hou.undos.disabler():
        spine.parmTuple("t").set((1, 2, 3))
        obj.parmTuple("t").set((-4, 0, 1))
        obj.parmTuple("r").set((0, 30, 0))
    m = spine.worldTransform() * obj.worldTransform().inverted()
    want = [tuple(hou.Vector3(p) * m) for p in pos(ln)]
    n_undo = len(hou.undos.undoLabels())
    om = stack.pick_input(ex, 1, spine.sessionId())
    got = pos(ex.input(1))
    out["pick_wires_object_merge"] = (om.parm("objpath1").eval() == spine.path() and ex.input(1) == om
                                      and ex.parm("spinetype").evalAsString() == "external"
                                      and stack.picked(ex, 1) == spine.path())
    out["pick_in_object_space"] = got is not None and len(got) == len(want) and all(
        (hou.Vector3(a) - hou.Vector3(b_)).length() < 1e-4 for a, b_ in zip(got, want))
    out["pick_one_undo"] = len(hou.undos.undoLabels()) == n_undo + 1
    n_children = len(obj.children())
    stack.pick_input(ex, 1, spine.sessionId())
    out["pick_again_replaces"] = len(obj.children()) == n_children
    try:
        stack.pick_input(ex, 1, obj.sessionId())
        out["pick_self_refused"] = False
    except ValueError:
        out["pick_self_refused"] = True
    with hou.undos.disabler():
        obj.parmTuple("t").set((0, 0, 0))
        obj.parmTuple("r").set((0, 0, 0))
    # deleting a top entry with a side input: Houdini's own fallback moved the display flag to another input
    # (probe: a merge's second input), so the stack must put it on the entry below itself
    n_children = len(obj.children())
    top = stack.add(obj.sessionId(), "extrude")
    stack.pick_input(top, 1, spine.sessionId())
    x = stack.add(obj.sessionId(), "subdivide", above=obj.node("sd"))
    stack.delete(top)
    try:
        shown = obj.displayNode() == x
    except hou.ObjectWasDeleted:   # the display flag went to a node the delete then removed
        shown = False
    out["delete_top_shows_below"] = (out["delete_top_shows_below"] and shown and x.isRenderFlagSet()
                                     and len(obj.children()) == n_children + 1)
    for _ in range(4):
        hou.undos.performUndo()

    # --- collapse ---------------------------------------------------------------------------------------------------
    full = pos(obj.displayNode())
    n_prims = len(obj.displayNode().geometry().prims())
    n_undo = len(hou.undos.undoLabels())
    st = stack.collapse(obj=obj)
    out["collapse_equals_chain"] = (names(obj) == ["mesh"] and st.type().name() == "stash" and obj.displayNode() == st
                                    and pos(st) == full and len(st.geometry().prims()) == n_prims)
    out["collapse_removes_chain"] = sorted(n.name() for n in obj.children()) == ["mesh"]
    out["collapse_one_undo"] = len(hou.undos.undoLabels()) == n_undo + 1
    hou.undos.performUndo()
    out["collapse_undo_restores"] = names(obj) == ["base", "ex", "sd"] and pos(obj.displayNode()) == full
    ex, sd = obj.node("ex"), obj.node("sd")
    at_ex = pos(ex)
    st = stack.collapse(ex)
    out["collapse_to_entry"] = (names(obj) == ["mesh", "sd"] and pos(st) == at_ex and pos(obj.displayNode()) == full
                                and obj.node("ex") is None and obj.node("base") is None)
    hou.undos.performUndo()

    # --- a container piece: promote + first modifier = one undo step ------------------------------------------------
    c = containers.create()
    m_piece = hou.hmath.buildScale(2, 2, 2) * hou.hmath.buildRotate(0, 45, 0) * hou.hmath.buildTranslate(5, 0, 2)
    ids = containers.add_pieces(c, [(FILES[0], "wing", m_piece), (FILES[1], "fin", None)])
    pid = ("piece", c.sessionId(), ids[0])
    n_undo = len(hou.undos.undoLabels())
    n_objs = len(hou.node("/obj").children())
    sub = stack.add(pid, "subdivide")
    newobj = sub.parent()
    rows = [r[0] for r in containers.piece_rows(c)]
    out["promote_then_modifier"] = (newobj.parent() == hou.node("/obj") and [n.type().name() for n in stack.chain(newobj)]
                                    == ["usdimport", "subdivide"] and ids[0] not in rows
                                    and all(abs(a - b_) < 1e-4 for a, b_ in zip(newobj.worldTransform().asTuple(), m_piece.asTuple())))
    out["promote_selects_object"] = scene.current().selected() == [newobj.sessionId()]
    out["promote_add_one_undo"] = len(hou.undos.undoLabels()) == n_undo + 1
    hou.undos.performUndo()
    out["promote_undo_restores"] = (len(hou.node("/obj").children()) == n_objs
                                    and ids[0] in [r[0] for r in containers.piece_rows(c)])
    # a piece picked as an input: only that piece, unpacked, in world space
    with hou.undos.disabler():
        c.parmTuple("t").set((0, 3, 0))
    stack.pick_input(ex, 1, ("piece", c.sessionId(), ids[1]))
    g = ex.input(1).geometry()
    src = hou.node("/obj").createNode("geo", "src")
    u = src.createNode("usdimport")
    u.parm("filepath1").set(FILES[1])
    u.parm("input_unpack").set(1)
    u.parm("unpack_geomtype").set(1)
    want = [tuple(hou.Vector3(p) * c.worldTransform()) for p in pos(u)]
    src.destroy()
    out["pick_piece_only_that_piece"] = (g is not None and len(g.points()) == len(want) > 0
                                         and all(isinstance(p, hou.Polygon) for p in g.prims())
                                         and all((hou.Vector3(a) - hou.Vector3(b_)).length() < 1e-4
                                                 for a, b_ in zip(pos(g), want)))

    return out


def mutate(mod, old, new):
    path = mod.__file__
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if src.count(old) != 1:
        raise RuntimeError("mutation snippet not found exactly once: %r" % old)
    exec(compile(src.replace(old, new), path, "exec"), mod.__dict__)
    return lambda: exec(compile(src, path, "exec"), mod.__dict__)


S, O = stack, operations
MUTATIONS = [   # (name, check, module, old, new)
    ("chain_top_first", "chain_base_first", S, "    return out[::-1]", "    return out"),
    ("new_top_not_shown", "add_on_top", S, "            else:\n                _set_top(n)\n        else:", "            else:\n                pass\n        else:"),
    ("no_defaults", "add_defaults", S, "            n.parm(parm).set(v)\n        if selection", "            pass\n        if selection"),
    ("selection_ignored", "add_group_from_selection", S, "        if selection is not None and selection[0] and op.get(\"groups\"):", "        if False:"),
    ("add_split_undo", "add_one_undo", S, '    with hou.undos.group("modelUI: add " + op["label"]):', "    if True:"),
    ("add_not_inserted", "add_above_entry", S, "                nodes[i + 1].setInput(0, n)", "                pass"),
    ("undo_leaves_node", "add_undo_restores", S, "        n.moveToGoodPosition()\n    return n", "        n.moveToGoodPosition()\n    with hou.undos.disabler():\n        n.parent().createNode('null', 'stray')\n    return n"),
    ("type_parm_ignored", "group_type_parm_set", S, "            node.parm(tp).set(token)", "            pass"),
    ("no_conversion", "group_converted_to_field_type", S, "        sel.convert(geo, TYPES[spec[\"types\"][0]])   # in place", "        pass"),
    ("use_selection_split", "use_selection_one_undo", S, '    with hou.undos.group("modelUI: use selection"):', "    if True:"),
    ("move_keeps_display", "move_up_reorders", S, "        if new[-1].sessionId() != nodes[-1].sessionId():\n            _set_top(new[-1])", "        pass"),
    ("move_split_undo", "move_one_undo", S, '    with hou.undos.group("modelUI: move modifier"):', "    if True:"),
    ("move_undo_partial", "move_undo_restores", S, "        for k in range(1, len(new)):   # bottom up", "        for k in range(1, len(new)):\n            if k == len(new) - 1:\n                with hou.undos.disabler():\n                    new[k].setInput(0, new[k - 1])\n                continue\n            # bottom up"),
    ("base_moves", "move_base_refused", S, "    if i == 0 or j < 1 or j >= len(nodes):", "    if j < 0 or j >= len(nodes):"),
    ("bypass_inverted", "off_bypasses", S, "        node.bypass(not on)", "        node.bypass(on)"),
    ("onoff_no_undo", "onoff_one_undo", S, '    with hou.undos.group("modelUI: modifier on" if on else "modelUI: modifier off"):', "    with hou.undos.disabler():"),
    ("on_ignored", "on_restores", S, "        node.bypass(not on)", "        node.bypass(True)"),
    ("base_bypassed", "base_always_on", S, "    if chain(node.parent())[0].sessionId() == node.sessionId():\n        return False\n    with", "    with"),
    ("delete_no_rewire", "delete_rewires", S, "            conn.outputNode().setInput(conn.inputIndex(), below)", "            conn.outputNode().setInput(conn.inputIndex(), None)"),
    ("delete_split_undo", "delete_one_undo", S, '    with hou.undos.group("modelUI: delete modifier"):', "    if True:"),
    ("delete_top_no_display", "delete_top_shows_below", S, "        if i == len(nodes) - 1:\n            _set_top(below)", "        pass"),
    ("base_deleted", "base_never_deleted", S, "    if i == 0:\n        return False\n    below", "    if i < 0:\n        return False\n    below"),
    ("cage_not_wired", "lattice_cage_deforms", S, "    lat.setInput(2, ed)", "    lat.setInput(2, bd)"),
    ("divs_not_linked", "lattice_divs_follow_cage", S, """        lat.parm("divs" + a).setExpression('ch("../%s/divs%s")' % (bd.name(), a))""", "        pass"),
    ("state_on_lattice", "lattice_state_on_cage", O, '         "build": "lattice_cage", "state": 2},', '         "build": "lattice_cage"},'),
    ("side_inputs_kept", "delete_takes_side_inputs", S, "        _destroy_unneeded(obj, doomed)\n    return True", "    return True"),
    ("pick_not_wired", "pick_wires_object_merge", S, "        node.setInput(index, last)", "        pass"),
    ("pick_world_space", "pick_in_object_space", S, '        om.parm("xformtype").set("local")   # into this object\'s space', '        om.parm("xformtype").set("none")'),
    ("pick_split_undo", "pick_one_undo", S, '    with hou.undos.group("modelUI: pick " + (spec.get("label") or "input %d" % index)):', "    if True:"),
    ("pick_keeps_old", "pick_again_replaces", S, "        if old is not None:\n            _destroy_unneeded(obj, _ancestors([old]))", "        pass"),
    ("pick_self_allowed", "pick_self_refused", S, "    if src is None or src.sessionId() == obj.sessionId():", "    if src is None:"),
    ("collapse_input_geo", "collapse_equals_chain", S, "    geo = node.geometry()\n    if geo is None", "    geo = node.inputs()[0].geometry()\n    if geo is None"),
    ("collapse_keeps_chain", "collapse_removes_chain", S, "        _destroy_unneeded(obj, doomed)\n        st.moveToGoodPosition()", "        st.moveToGoodPosition()"),
    ("collapse_split_undo", "collapse_one_undo", S, '    with hou.undos.group("modelUI: collapse"):', "    if True:"),
    ("collapse_undo_partial", "collapse_undo_restores", S, "        _destroy_unneeded(obj, doomed)\n        st.moveToGoodPosition()", "        with hou.undos.disabler():\n            _destroy_unneeded(obj, doomed)\n        st.moveToGoodPosition()"),
    ("collapse_no_rewire", "collapse_to_entry", S, "            conn.outputNode().setInput(conn.inputIndex(), st)", "            pass"),
    ("promote_lost", "promote_then_modifier", S, "    obj = containers.promote(c, piece)", "    obj = c"),
    ("promote_not_selected", "promote_selects_object", S, "    scene.current().select([obj.sessionId()])", "    pass"),
    ("promote_split_undo", "promote_add_one_undo", S, '    with hou.undos.group("modelUI: add " + op["label"]):', '    with hou.undos.group("modelUI: add " + op["label"]):\n        pass\n    if True:'),
    ("promote_undo_partial", "promote_undo_restores", S, "    obj = containers.promote(c, piece)", "    with hou.undos.disabler():\n        obj = containers.promote(c, piece)"),
    ("piece_whole_container", "pick_piece_only_that_piece", S, '            om.parm("group1").set("@pf_piece=%d" % piece)', "            pass"),
    ("registry_wrong_parm", "registry_matches_houdini", O, '"defaults": {"offset": 0.05}}', '"defaults": {"offsett": 0.05}}'),
]


def run():
    out = {}
    try:
        checks(out)
    except Exception as e:  # noqa: BLE001 - an exception is a red check; the checks before it keep their values
        import traceback
        out["_exception"] = traceback.format_exc()
    return out


def main():
    base = run()
    bad = [k for k, v in base.items() if v is not True]
    for k, v in base.items():
        print("%-32s %s" % (k, "ok" if v is True else "RED %s" % v))
    names_ = set(base) - {"_exception"}
    for name, check, mod, old, new in MUTATIONS:
        restore = mutate(mod, old, new)
        try:
            res = run()
        finally:
            restore()
        red = res.get(check) is False   # credited only when the paired check itself evaluated False
        print("mutation %-24s -> %-32s %s" % (name, check, "red (good)" if red else "NOT RED %s" % res.get("_exception", "")))
        if not red:
            bad.append("mutation " + name)
        names_.discard(check)
    if names_:
        print("checks without a mutation:", sorted(names_))
        bad.append("unpaired checks")
    print("FAIL" if bad else "PASS", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
