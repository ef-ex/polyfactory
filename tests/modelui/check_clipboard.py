"""Headless checks of modelUI copy and paste between scenes (F2e, clipboard.py): a copy in one hython session, the
paste in a SECOND hython process (a real other scene: nothing shared but the clipboard folder). Each check has a
paired source mutation that must turn it red (applied in both processes).

Run:  hython tests/modelui/check_clipboard.py     (exit 0 = all green AND every mutation reddened its paired check)
Throwaway sessions, never saves a .hip; the clipboard goes to F:/cache/modelui/check_clipboard (PF_MODELUI_CLIPBOARD).
Uses two kitbash library files (F:/3d/kitbashLib).

Oracle, independent of clipboard.py: every item's WORLD points (an Object Merge into world, unpacked and filtered by
pf_piece for pieces), keyed by name, in the copying scene and in the pasting one. Fixture A: two visible pieces and a
hidden one in a moved, rotated, 1.5x container; a loose box object with a pivot, parented to a null (the null is not
copied); a promoted piece (its own object, a usdimport). Scene B: a container moved, turned and scaled 2x with one
piece selected (the paste goes there), and a node named like A's box (Houdini renames the pasted one).
TOL = 1e-4 world units at |values| <= 30 (float32 piece storage).

What these cannot see: Ctrl+C / Ctrl+V and the menu (gui_f2e.py), the look-at point itself (kitbash.look_at, a viewer;
here the point is given), sources missing on the pasting machine, objects whose nodes reference others (an Object
Merge, a material path: they come as they were saved), shear (a container with a non-uniform scale), a copy with
nothing selected (left as it is, not checked).
"""
import glob
import json
import os
import subprocess
import sys

import numpy as np

import hou

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import clipboard, containers, scene  # noqa: E402

FILES = sorted(f.replace("\\", "/") for f in glob.glob("F:/3d/kitbashLib/*/*.usd"))
CLIP = "F:/cache/modelui/check_clipboard"
TOL = 1e-4
AT = (10.0, 0.0, -5.0)
HYTHON = sys.executable if "hython" in os.path.basename(sys.executable).lower() else \
    "C:/Program Files/Side Effects Software/Houdini 22.0.442/bin/hython.exe"


def xf(t=(0, 0, 0), r=(0, 0, 0), s=(1, 1, 1)):
    return hou.hmath.buildScale(s) * hou.hmath.buildRotate(r) * hou.hmath.buildTranslate(t)


def world_points(pids):
    """{name: Nx3 world points} of the items (pieces by pf_name, objects by node name) through an Object Merge."""
    with hou.undos.disabler():
        o = hou.node("/obj").createNode("geo", "oracle")
        o.setDisplayFlag(False)
        out = {}
        for pid in pids:
            node = hou.nodeBySessionId(pid[1] if isinstance(pid, tuple) else pid)
            om = o.createNode("object_merge")
            om.parm("objpath1").set(node.path())
            om.parm("xformtype").set(1)
            if isinstance(pid, tuple):
                un = o.createNode("unpack")
                un.setFirstInput(om)
                un.parm("transfer_attributes").set("pf_piece")
                g = un.geometry()
                prims = [p for p in g.prims() if p.attribValue("pf_piece") == pid[2]]
                idx = sorted({v.point().number() for p in prims for v in p.vertices()})
                pts = [g.point(i).position() for i in idx]
                row = [r for r in containers.piece_rows(node) if r[0] == pid[2]][0]
                out[row[1]] = np.array([tuple(p) for p in pts])
            else:
                out[node.name()] = np.array([tuple(p.position()) for p in om.geometry().points()])
        o.destroy()
    return out


def mutate(mod, old, new):
    path = mod.__file__
    with open(path, encoding="utf-8") as fh:
        src = fh.read()
    if src.count(old) != 1:
        raise RuntimeError("mutation snippet not found exactly once: %r" % old)
    exec(compile(src.replace(old, new), path, "exec"), mod.__dict__)
    return lambda: exec(compile(src, path, "exec"), mod.__dict__)


C = clipboard
MUTATIONS = [   # (name, check, module, old, new)
    ("world_as_local", "paste_same_world", C, "hou.Matrix4(p[\"world\"]) * shift * inv)", "hou.Matrix4(p[\"world\"]) * shift)"),
    ("objects_not_placed", "paste_same_world", C, "                    n.setWorldTransform(hou.Matrix4(o[\"world\"]) * shift)", "                    pass"),
    ("new_container", "paste_into_selected_container", C, "            c = kitbash.target_container()", "            c = containers.create()"),
    ("no_undo_group", "paste_one_undo", C, '    with hou.undos.group("modelUI: paste"):', "    if True:"),
    ("not_selected", "pasted_selected", C, "        scene.current().select(pids)\n", "        pass\n"),
    ("hidden_dropped", "hidden_kept", C, "            if hidden:", "            if False:"),
    ("at_ignores_box", "paste_at_point", C, 'shift = hou.hmath.buildTranslate(at[0] - 0.5 * (lo[0] + hi[0]), at[1] - lo[1], at[2] - 0.5 * (lo[2] + hi[2]))',
     "shift = hou.hmath.buildTranslate(at)"),
    ("at_centre_height", "paste_at_point", C, "at[1] - lo[1]", "at[1] - 0.5 * (lo[1] + hi[1])"),
    ("stale_files_kept", "old_object_files_removed", C, '        if f.startswith("object_") and f.endswith(".cpio"):', "        if False:"),
    ("json_kept_on_failure", "failed_copy_not_mixed", C, '    if os.path.exists(os.path.join(d, "clipboard.json")):', "    if False:"),
    ("all_into_one_file", "objects_pasted_once", C, '            f = "object_%d.cpio" % len(objects)', '            f = "object_0.cpio"'),
]


def apply_mutation(name):
    for m in MUTATIONS:
        if m[0] == name:
            return mutate(m[2], m[3], m[4])
    return lambda: None


def _visible(pids):
    """The items that draw something (a hidden piece has no points to compare)."""
    out = []
    for p in pids:
        if isinstance(p, tuple):
            hidden = {r[0]: r[2] for r in containers.piece_rows(hou.nodeBySessionId(p[1]))}
            if hidden[p[2]]:
                continue
        out.append(p)
    return out


# --- session B: a second hython process -------------------------------------------------------------------------------
def paste_session(out_path):
    restore = apply_mutation(os.environ.get("PF_CLIP_MUT"))
    res = {}
    try:
        hou.hipFile.clear(suppress_save_prompt=True)
        cb = containers.create("mine")
        with hou.undos.disabler():
            cb.parmTuple("t").set((-7, 2, 4))
            cb.parmTuple("r").set((15, -40, 5))
            cb.parmTuple("s").set((2, 2, 2))
        own = containers.add_pieces(cb, [(FILES[5], "x", xf((1, 0, 1)))])[0]
        hou.node("/obj").createNode("geo", "box").createNode("box")   # A's box comes in under another name
        scene.current().select([("piece", cb.sessionId(), own)])
        u0 = len(hou.undos.undoLabels())
        pids = clipboard.paste()
        labels = hou.undos.undoLabels()
        res["n_labels"] = len(labels) - u0
        res["label0"] = labels[0] if labels else None
        res["containers"] = sorted({p[1] for p in pids if isinstance(p, tuple)})
        res["mine"] = cb.sessionId()
        res["selected_ok"] = sorted(map(str, scene.current().selected())) == sorted(map(str, pids))
        res["hidden"] = {r[1]: r[2] for c in containers.containers() for r in containers.piece_rows(c)}
        visible = _visible(pids)
        res["world"] = {k: v.tolist() for k, v in world_points(visible).items()}
        res["object_names"] = sorted(hou.nodeBySessionId(p).name() for p in pids if not isinstance(p, tuple))
        hou.undos.performUndo()
        res["undo_clean"] = (len(containers.piece_rows(cb)) == 1 and len(containers.containers()) == 1
                             and all(not isinstance(p, tuple) and hou.nodeBySessionId(p) is None for p in pids
                                     if not isinstance(p, tuple)))
        pids = clipboard.paste(at=AT)
        res["world_at"] = {k: v.tolist() for k, v in world_points(_visible(pids)).items()}
    except Exception:  # noqa: BLE001
        import traceback
        res["_exception"] = traceback.format_exc()
    finally:
        restore()
    with open(out_path, "w") as fh:
        json.dump(res, fh)


# --- session A: the copy, then B, then the comparison -------------------------------------------------------------------
def fixture():
    hou.hipFile.clear(suppress_save_prompt=True)
    ca = containers.create("kit")
    with hou.undos.disabler():
        ca.parmTuple("t").set((3, 1, -2))
        ca.parmTuple("r").set((0, 30, 10))
        ca.parmTuple("s").set((1.5, 1.5, 1.5))
    ids = containers.add_pieces(ca, [(FILES[3], "a", xf((-4, 2, 1), (20, 35, -15), (10, 6, 8))),
                                     (FILES[5], "b", xf((2, -1, 3), (-30, 10, 50), (7, 9, 5))),
                                     (FILES[3], "h", xf((0, 3, 0), (0, 0, 0), (5, 5, 5))),
                                     (FILES[5], "promo", xf((6, 0, -3), (0, 70, 0), (6, 6, 6)))])
    containers.set_hidden(ca, [ids[2]], True)
    promo = containers.promote(ca, ids[3])
    null = hou.node("/obj").createNode("null", "rig")
    null.parmTuple("t").set((1, 2, 3))
    null.parmTuple("r").set((0, 45, 0))
    box = hou.node("/obj").createNode("geo", "box")
    b = box.createNode("box")
    b.parmTuple("size").set((2, 1, 3))
    box.setFirstInput(null)
    box.parmTuple("t").set((5, 3, -7))
    box.parmTuple("r").set((15, 40, -20))
    box.parmTuple("s").set((1.2, 1.2, 1.2))
    box.parmTuple("p").set((0.4, -0.3, 0.6))
    pieces = [("piece", ca.sessionId(), i) for i in ids[:3]]
    return pieces, [box.sessionId(), promo.sessionId()], ca


def run(mut=None):
    out = {}
    restore = apply_mutation(mut)
    try:
        pieces, objs, ca = fixture()
        os.environ["PF_MODELUI_CLIPBOARD"] = CLIP
        sel = pieces + objs
        clipboard.copy(sel)
        clipboard.copy([pieces[0], objs[0]])   # after a copy of two objects, one: the older second file must go
        files = sorted(f for f in os.listdir(CLIP) if f.endswith(".cpio"))
        out["old_object_files_removed"] = len(files) == 1
        clipboard.copy(sel)
        try:   # a copy that dies half way (a stale id) must not leave a clipboard whose JSON names deleted files
            clipboard.copy([sel[-1], 2 ** 30])
        except Exception:  # noqa: BLE001
            pass
        d = clipboard.read()
        out["failed_copy_not_mixed"] = d is None or all(os.path.exists(os.path.join(CLIP, o["file"])) for o in d["objects"])
        clipboard.copy(sel)
        want = world_points([p for p in sel if p != pieces[2]])   # the hidden piece draws nothing
        with hou.undos.disabler():   # the whole copied set's box (the hidden piece too): where "paste at" puts it
            containers.set_hidden(ca, [pieces[2][2]], False)
        every = np.vstack(list(world_points(sel).values()))
        lo_all = every.min(0)
        c_all = 0.5 * (lo_all + every.max(0))
        expect_shift = np.array([AT[0] - c_all[0], AT[1] - lo_all[1], AT[2] - c_all[2]])
        res_path = CLIP + "_result.json"
        if os.path.exists(res_path):
            os.remove(res_path)
        env = dict(os.environ, PF_CLIP_ROLE="paste", PF_CLIP_OUT=res_path, PF_CLIP_MUT=mut or "")
        subprocess.run([HYTHON, os.path.abspath(__file__)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=600)
        with open(res_path) as fh:
            r = json.load(fh)
        if "_exception" in r:
            out["_exception"] = r["_exception"].strip().splitlines()[-1]
            print(r["_exception"])
            return out
        got = {k: np.array(v) for k, v in r["world"].items()}
        names = {"a": "a", "b": "b", "promo": "promo", "box": None}
        boxname = [n for n in r["object_names"] if n != "promo" and n.startswith("box")]
        names["box"] = boxname[0] if len(boxname) == 1 else None
        ok = all(names[k] in got and got[names[k]].shape == v.shape and np.abs(got[names[k]] - v).max() <= TOL
                 for k, v in want.items())
        out["paste_same_world"] = bool(ok and names["box"] != "box")
        out["objects_pasted_once"] = sorted(r["object_names"]) == sorted([names["box"] or "?", "promo"])
        out["paste_into_selected_container"] = r["containers"] == [r["mine"]]
        out["paste_one_undo"] = r["n_labels"] == 1 and r["label0"] == "modelUI: paste" and r["undo_clean"]
        out["pasted_selected"] = bool(r["selected_ok"])
        out["hidden_kept"] = r["hidden"].get("h") == 1 and r["hidden"].get("a") == 0
        at = {k: np.array(v) for k, v in r["world_at"].items()}
        shifts = [at[names[k]] - got[names[k]] for k in want if names[k] in at and names[k] in got]
        out["paste_at_point"] = bool(len(shifts) == len(want) and all(np.abs(d - expect_shift).max() <= TOL for d in shifts))
        if not out["paste_at_point"] and shifts:
            print("  paste at: want shift", expect_shift, "got", shifts[0][0])
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        out["_exception"] = "%s: %s" % (type(e).__name__, e)
    finally:
        restore()
    return out


def main():
    only = os.environ.get("PF_CLIP_ONLY")
    base = run()
    bad = [k for k, v in base.items() if v is not True]
    for k, v in base.items():
        print("%-32s %s" % (k, "ok" if v is True else "RED %s" % v))
    names = set(base) - {"_exception"}
    for name, check, mod, old, new in MUTATIONS:
        if only and name not in only.split(","):
            names.discard(check)
            continue
        res = run(name)
        red = res.get(check) is False
        print("mutation %-22s -> %-30s %s" % (name, check, "red (good)" if red else "NOT RED %s" % res.get("_exception", res.get(check))))
        if not red:
            bad.append("mutation " + name)
        names.discard(check)
    if names:
        print("checks without a mutation:", sorted(names))
        bad.append("unpaired checks")
    print("FAIL" if bad else "PASS", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    if os.environ.get("PF_CLIP_ROLE") == "paste":
        paste_session(os.environ["PF_CLIP_OUT"])
        sys.exit(0)
    sys.exit(main())
