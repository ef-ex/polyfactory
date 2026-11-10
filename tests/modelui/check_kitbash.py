"""Headless checks of "Add kitbash pieces" (modelui/kitbash.py: add_files), each with a paired source mutation that must
turn it red.

Run:  hython tests/modelui/check_kitbash.py     (exit 0 = all green AND every mutation reddened its paired check)
Uses three files of Hannes' kitbash library F:/3d/kitbashLib. Throwaway session, never saves a .hip.

What these cannot see: the file dialog (hou.ui.selectFile with multiple_select: its ';'-separated return is parsed
by add_dialog, untested), the viewport's look-at point (look_at() needs a Scene Viewer; the checks pass `at`), the
menu entry and the Explorer button (GUI).
"""
import glob
import os
import sys

import hou

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import containers, kitbash, scene  # noqa: E402

FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))[3:6]
TOL = 1e-4


def exact_box(pid):
    """World box from the piece's own points (pieces_ui.bounds boxes the container-space box, which grows when the
    container is turned)."""
    c, piece = scene.MixedScene._split(pid)
    pr = [q for q in c.displayNode().geometry().prims() if q.attribValue("pf_piece") == piece][0]
    m = pr.fullTransform() * c.worldTransform()
    pts = [pt.position() * m for pt in pr.getEmbeddedGeometry().points()]
    return hou.BoundingBox(*[min(v[i] for v in pts) for i in range(3)], *[max(v[i] for v in pts) for i in range(3)])


def row_ok(pids, at):
    """World boxes: every piece on the ground, left to right with the gap, the row centred on ``at`` in x and z."""
    bs = [exact_box(p) for p in pids]
    widest = max(b.sizevec()[0] for b in bs)
    gaps = [bs[k + 1].minvec()[0] - bs[k].maxvec()[0] for k in range(len(bs) - 1)]
    cx = (bs[0].minvec()[0] + bs[-1].maxvec()[0]) / 2.0
    return (all(abs(b.minvec()[1] - at[1]) < TOL for b in bs)
            and all(abs(g - kitbash.GAP * widest) < TOL for g in gaps)
            and abs(cx - at[0]) < TOL and all(abs(b.center()[2] - at[2]) < TOL for b in bs)), bs


def checks(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    s = scene.current()
    at = hou.Vector3(10, 0, -5)
    u0 = len(hou.undos.undoLabels())
    pids = kitbash.add_files(FILES, at=at)
    labels = hou.undos.undoLabels()
    ok, bs = row_ok(pids, at)
    out["row_layout"] = ok and len(pids) == 3
    out["new_pieces_selected"] = sorted(s.selected()) == sorted(pids)
    hou.undos.performUndo()
    out["add_one_undo_step"] = (len(labels) - u0 == 1 and labels[0] == "modelUI: add kitbash pieces"
                                and containers.containers() == [])
    # into the current container, also when it is moved and turned: the row still lands at `at`, on the ground
    c = containers.create()
    c.parmTuple("t").set((3, 1, 2))
    c.parmTuple("r").set((0, 30, 0))
    first = kitbash.add_files(FILES[:1], at=hou.Vector3(-20, 0, 0))
    s.select(first)
    at2 = hou.Vector3(4, 0, 6)
    more = kitbash.add_files(FILES[1:], at=at2)
    ok2, _ = row_ok(more, at2)
    out["uses_current_container"] = containers.containers() == [c] and all(p[1] == c.sessionId() for p in more)
    out["row_in_moved_container"] = ok2


def mutate(mod, old, new):
    path = mod.__file__
    with open(path, encoding="utf-8") as f:
        src = f.read()
    if src.count(old) != 1:
        raise RuntimeError("mutation snippet not found exactly once: %r" % old)
    exec(compile(src.replace(old, new), path, "exec"), mod.__dict__)
    return lambda: exec(compile(src, path, "exec"), mod.__dict__)


K = kitbash
MUTATIONS = [   # (name, check, module, old, new)
    ("no_undo_group", "add_one_undo_step", K, '    with hou.undos.group("modelUI: add kitbash pieces"):', "    if True:"),
    ("no_spacing", "row_layout", K, "            x += s[0] + gap", "            x += 0"),
    ("not_on_ground", "row_layout", K, "at[1] - lo[1]", "at[1]"),
    ("container_moves_row", "row_in_moved_container", K, "            xforms[i] = hou.hmath.buildTranslate(t) * inv",
     "            xforms[i] = hou.hmath.buildTranslate(t)"),
    ("new_container_each_time", "uses_current_container", K, "    found = containers.containers()\n    return found[0] if found else containers.create()",
     "    return containers.create()"),
    ("not_selected", "new_pieces_selected", K, "    scene.current().select(pids)", "    pass"),
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
        print("%-28s %s" % (k, "ok" if v is True else "RED %s" % v))
    names = set(base)
    for name, check, mod, old, new in MUTATIONS:
        restore = mutate(mod, old, new)
        try:
            res = run()
        finally:
            restore()
        red = res.get(check) is False
        print("mutation %-24s -> %-26s %s" % (name, check, "red (good)" if red else "NOT RED %s" % res.get("_exception", "")))
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
