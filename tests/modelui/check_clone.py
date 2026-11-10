"""Headless checks of the Clone dialog's work (modelui/clone.py: clone), each with a paired source mutation that must
turn it red.

Run:  hython tests/modelui/check_clone.py     (exit 0 = all green AND every mutation reddened its paired check)
Uses two files of Hannes' kitbash library F:/3d/kitbashLib and a box object. Throwaway session, never saves a .hip.

What these cannot see: the dialog widget (its fields and OK: gui_f2a `clone_dialog_ok`), the viewport, what the
modifier stack (F2c) will do with pf_clone_kind / pf_clone_of on pieces.
"""
import glob
import os
import sys

import hou

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import clone, containers, pieces_ui, scene  # noqa: E402

FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))[3:5]
TOL = 1e-4   # float32 P/orient/scale at |values| <= 30


def vclose(a, b, tol=TOL):
    return (hou.Vector3(a) - hou.Vector3(b)).length() <= tol


def size(node):
    return node.displayNode().geometry().boundingBox().sizevec()


def checks(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    s = scene.current()
    c = containers.create()
    turned = hou.hmath.buildRotate(20, 0, 10) * hou.hmath.buildTranslate(4, 1, -3)
    a, b = containers.add_pieces(c, [(FILES[0], "a", turned), (FILES[1], "b", None)])
    pa = ("piece", c.sessionId(), a)
    obj = hou.node("/obj").createNode("geo", "boxy")
    box = obj.createNode("box")
    box.setDisplayFlag(True)
    obj.parmTuple("t").set((0, 0, 9))

    # steps: copy k sits k moves further, turned k steps about the world axes through its own position, k scales up
    m0 = pieces_ui.get_xform(pa)
    move, rot, sc = (2.0, 0.0, 1.0), (0.0, 30.0, 0.0), 1.1
    new = clone.clone([pa], "copy", 3, move, rot, sc)
    ok = len(new) == 3
    for k, cp in enumerate(new, 1):
        m = pieces_ui.get_xform(cp)
        ax0 = hou.Vector3(1, 0, 0) * m0 - hou.Vector3() * m0   # the original's x axis in world space, with its scale
        ax = hou.Vector3(1, 0, 0) * m - hou.Vector3() * m
        want_ax = ax0 * hou.hmath.buildRotate(0, 30.0 * k, 0).extractRotationMatrix3() * (sc ** k)
        ok = ok and vclose(m.extractTranslates(), m0.extractTranslates() + hou.Vector3(move) * k) and vclose(ax, want_ax)
    out["copies_step_by_step"] = ok
    out["clones_selected"] = sorted(s.selected()) == sorted(new)
    out["piece_copy_independent"] = all(
        not containers.points(c).findPointAttrib("pf_clone_kind")
        or containers.points(c).iterPoints()[i].stringAttribValue("pf_clone_kind") == "" for i in range(2, 5))

    # one undo step for a mixed selection (pieces of a container and an object, several copies each)
    rows0, objs0, u0 = len(containers.piece_rows(c)), len(hou.node("/obj").children()), len(hou.undos.undoLabels())
    mixed = clone.clone([pa, ("piece", c.sessionId(), b), obj.sessionId()], "copy", 2)
    labels = hou.undos.undoLabels()
    made = (len(mixed) == 6 and len(containers.piece_rows(c)) == rows0 + 4
            and len(hou.node("/obj").children()) == objs0 + 2)
    hou.undos.performUndo()
    out["clone_one_undo_step"] = (made and len(labels) - u0 == 1 and labels[0] == "modelUI: clone (copy)"
                                  and len(containers.piece_rows(c)) == rows0
                                  and len(hou.node("/obj").children()) == objs0)

    # pieces: an instance records what it is and of which piece
    inst = clone.clone([pa], "instance", 1)[0]
    p = [q for q in containers.points(c).points() if q.intAttribValue("pf_piece") == inst[2]][0]
    out["piece_instance_recorded"] = (p.stringAttribValue("pf_clone_kind") == "instance"
                                      and p.intAttribValue("pf_clone_of") == a)

    # objects: Copy is independent, Instance (packed) and Reference (unpacked) follow the original
    cp = hou.nodeBySessionId(clone.clone([obj.sessionId()], "copy", 1)[0])
    ins = [hou.nodeBySessionId(i) for i in clone.clone([obj.sessionId()], "instance", 2, move=(0, 0, 3))]
    ref = hou.nodeBySessionId(clone.clone([obj.sessionId()], "reference", 1)[0])
    box.parmTuple("size").set((2, 3, 4))
    out["object_copy_independent"] = vclose(size(cp), (1, 1, 1)) and [n.type().name() for n in cp.children()] == ["box"]
    ig = ins[1].displayNode().geometry()
    out["object_instance_follows_packed"] = (vclose(size(ins[1]), (2, 3, 4)) and len(ig.prims()) == 1
                                             and ig.prims()[0].type() == hou.primType.PackedGeometry
                                             and vclose(ins[1].worldTransform().extractTranslates(), (0, 0, 15)))
    out["object_reference_follows"] = (vclose(size(ref), (2, 3, 4)) and len(ref.displayNode().geometry().prims()) == 6
                                       and ref.userData("pf_clone_kind") == "reference")


def mutate(mod, old, new):
    path = mod.__file__
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if src.count(old) != 1:
        raise RuntimeError("mutation snippet not found exactly once: %r" % old)
    exec(compile(src.replace(old, new), path, "exec"), mod.__dict__)
    return lambda: exec(compile(src, path, "exec"), mod.__dict__)


K, C = clone, containers
MUTATIONS = [   # (name, check, module, old, new)
    ("no_steps", "copies_step_by_step", K, "                xforms[cp] = step(start[pid], k, move, rotate, scale)",
     "                xforms[cp] = step(start[pid], 1, move, rotate, scale)"),
    ("scale_not_compounded", "copies_step_by_step", K, "hou.hmath.buildScale(scale ** k, scale ** k, scale ** k)",
     "hou.hmath.buildScale(scale, scale, scale)"),
    ("turn_about_origin", "copies_step_by_step", K, "    d = (hou.hmath.buildTranslate(-p) * hou.hmath.buildScale(",
     "    d = (hou.hmath.buildTranslate(0, 0, 0) * hou.hmath.buildScale("),
    ("not_selected", "clones_selected", K, "    scene.current().select(new)", "    pass"),
    ("copy_recorded_as_clone", "piece_copy_independent", K, '"" if kind == "copy" else kind', '"instance"'),
    ("no_undo_group", "clone_one_undo_step", K, '    with hou.undos.group("modelUI: clone (%s)" % kind):', "    if True:"),
    ("relation_dropped", "piece_instance_recorded", C, '            p.setAttribValue("pf_clone_kind", kind)', "            pass"),
    ("copy_shares", "object_copy_independent", K, '    if kind == "copy":\n        return hou.copyNodesTo([node], node.parent())[0]',
     '    if False:\n        return hou.copyNodesTo([node], node.parent())[0]'),
    ("instance_unpacked", "object_instance_follows_packed", K, '        om.parm("pack").set(1)', "        pass"),
    ("reference_not_merged", "object_reference_follows", K, '    om.parm("objpath1").set(node.path())', '    om.parm("objpath1").set("")'),
]


def run():
    out = {}
    try:
        checks(out)
    except Exception as e:  # noqa: BLE001 - an exception is a red check
        out["_exception"] = "%s: %s" % (type(e).__name__, e)
    return out


def main():
    base = run()
    bad = [k for k, v in base.items() if v is not True]
    for k, v in base.items():
        print("%-32s %s" % (k, "ok" if v is True else "RED %s" % v))
    names = set(base)
    for name, check, mod, old, new in MUTATIONS:
        restore = mutate(mod, old, new)
        try:
            res = run()
        finally:
            restore()
        red = res.get(check) is False
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
