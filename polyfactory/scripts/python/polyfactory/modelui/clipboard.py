"""modelUI copy and paste between scenes (F2e, ideas/modelui.md): copy the selected pieces and loose objects in one
hip, paste them into another (or the same) with the same world transforms, or with the copied set standing on the
ground at the point the viewport looks at.

Artist entry points: Ctrl+C / Ctrl+V / Ctrl+Shift+V over a viewer while modelUI is on, and polyfactory > Copy /
Paste / Paste at the look-at point (main menu, any time).

The clipboard is a folder (``$PF_MODELUI_CLIPBOARD``, default ``F:/cache/modelui/clipboard``): ``clipboard.json``
holds each piece's source file, name, visibility and world matrix (pieces are USD library files: no geometry is
copied) and each loose object's world matrix; each object's nodes are in their own ``object_<i>.cpio``
(``saveItemsToFile``), so a paste knows which new node is which. The JSON is written last (a rename), so a paste never
reads half a copy.
"""
import json
import os

import numpy as np

import hou

from polyfactory.modelui import align, containers, kitbash, scene

DEFAULT = "F:/cache/modelui/clipboard"
VERSION = 1


def folder():
    return (os.environ.get("PF_MODELUI_CLIPBOARD") or DEFAULT).replace("\\", "/")


def _status(text, warn=False):
    if hou.isUIAvailable():
        hou.ui.setStatusMessage(text, hou.severityType.Warning if warn else hou.severityType.Message)


def copy(pids=None):
    """The selection (or ``pids``) to the clipboard. Changes nothing in the scene. Returns how many items were
    copied (0: nothing selected, the clipboard stays as it was)."""
    pids = scene.current().selected() if pids is None else list(pids)
    if not pids:
        _status("Copy: select pieces or objects first.", True)
        return 0
    d = folder()
    os.makedirs(d, exist_ok=True)
    for f in os.listdir(d):   # an older copy's object files must not survive into this one
        if f.startswith("object_") and f.endswith(".cpio"):
            os.remove(os.path.join(d, f))
    its = align.items(pids)
    los, his = zip(*(align.world_box(it) for it in its))
    rows, pieces, objects = {}, [], []
    for it in its:
        pid, world = it["pid"], list(it["m"].asTuple())
        if isinstance(pid, tuple):
            c, piece = scene.MixedScene._split(pid)
            if c.sessionId() not in rows:
                g = containers.stash(c).geometry()
                rows[c.sessionId()] = dict(zip(g.pointIntAttribValues("pf_piece"),
                                               zip(g.pointStringAttribValues("pf_source"),
                                                   g.pointStringAttribValues("pf_name"),
                                                   g.pointIntAttribValues("pf_hidden"))))
            src, name, hidden = rows[c.sessionId()][piece]
            pieces.append({"source": src, "name": name, "hidden": hidden, "world": world})
        else:
            n = hou.nodeBySessionId(pid)
            f = "object_%d.cpio" % len(objects)
            n.parent().saveItemsToFile([n], os.path.join(d, f))
            objects.append({"file": f, "name": n.name(), "world": world})
    data = {"version": VERSION, "from": hou.hipFile.path(), "pieces": pieces, "objects": objects,
            "box": [list(map(float, np.min(los, 0))), list(map(float, np.max(his, 0)))]}
    tmp = os.path.join(d, "clipboard.json.tmp")
    with open(tmp, "w") as fh:
        json.dump(data, fh, indent=1)
    os.replace(tmp, os.path.join(d, "clipboard.json"))
    _status("Copied %d piece(s) and %d object(s)." % (len(pieces), len(objects)))
    return len(pieces) + len(objects)


def read():
    """The clipboard's data, or None (nothing copied yet, or another version)."""
    try:
        with open(os.path.join(folder(), "clipboard.json")) as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return None
    return data if data.get("version") == VERSION else None


def paste(at=None):
    """The clipboard into this scene, one undo step, the pasted items selected. ``at`` (a world point): the copied
    set moves as a whole so the centre of its box is over ``at`` and its bottom on ``at``'s height; default: the same
    world transforms. Pieces go into the container of the selected piece, else the first, else a new one. Returns the
    new item ids."""
    data = read()
    if not data or not (data["pieces"] or data["objects"]):
        _status("Paste: the clipboard is empty (copy pieces or objects first).", True)
        return []
    shift = hou.hmath.identityTransform()
    if at is not None:
        lo, hi = data["box"]
        shift = hou.hmath.buildTranslate(at[0] - 0.5 * (lo[0] + hi[0]), at[1] - lo[1], at[2] - 0.5 * (lo[2] + hi[2]))
    obj = hou.node("/obj")
    pids = []
    with hou.undos.group("modelUI: paste"):
        if data["pieces"]:
            c = kitbash.target_container()
            inv = c.worldTransform().inverted()
            ids = containers.add_pieces(c, [(p["source"], p["name"], hou.Matrix4(p["world"]) * shift * inv)
                                            for p in data["pieces"]])
            hidden = [i for i, p in zip(ids, data["pieces"]) if p["hidden"]]
            if hidden:
                containers.set_hidden(c, hidden, True)
            pids += [("piece", c.sessionId(), i) for i in ids]
        for o in data["objects"]:
            before = {n.sessionId() for n in obj.children()}
            obj.loadItemsFromFile(os.path.join(folder(), o["file"]), ignore_load_warnings=True)
            for n in obj.children():
                if n.sessionId() not in before:
                    n.setWorldTransform(hou.Matrix4(o["world"]) * shift)   # its parent, if any, stayed behind
                    pids.append(n.sessionId())
        scene.current().select(pids)
    _status("Pasted %d item(s)." % len(pids))
    return pids


def paste_at_look_at():
    return paste(at=kitbash.look_at())
