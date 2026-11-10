"""Add kitbash pieces: USD files from the kitbash library into a modelUI container, in a neat row on the ground at the
point the viewport looks at, selected afterwards, one undo step.

Artist entry points: polyfactory > Add kitbash pieces... (main menu) and the Scene Explorer's button. ``add_files`` is
the part without a dialog (headless checks: tests/modelui/check_kitbash.py).
"""
import os

import hou

from polyfactory.modelui import containers, scene

LIBRARY = "F:/3d/kitbashLib"   # used when $PF_ASSET_LIBRARY is not set
GAP = 0.1   # space between two pieces of the row, as a fraction of the widest piece


def library():
    return os.environ.get("PF_ASSET_LIBRARY") or LIBRARY


def look_at():
    """Where the current viewport looks, on the ground (y = 0); the origin without a viewer."""
    sv = hou.ui.paneTabOfType(hou.paneTabType.SceneViewer) if hou.isUIAvailable() else None
    if sv is None:
        return hou.Vector3()
    p = sv.curViewport().defaultCamera().pivot()
    return hou.Vector3(p[0], 0.0, p[2])


def target_container():
    """The container of the selected piece, else the first one, else a new one."""
    for pid in scene.current().selected():
        if isinstance(pid, tuple):
            return scene.MixedScene._split(pid)[0]
    found = containers.containers()
    return found[0] if found else containers.create()


def _local_box(container, piece):
    for pr in container.displayNode().geometry().prims():
        if pr.attribValue("pf_piece") == piece:
            return pr.boundingBox()
    return None


def add_files(paths, at=None):
    """Add one piece per file in a row along X centred on ``at`` (default: the viewport's look-at point), each standing
    on the ground and spaced by its bounding box; one undo step; the new pieces are selected. Returns their ids."""
    paths = [p.replace("\\", "/") for p in paths if p]
    if not paths:
        return []
    at = look_at() if at is None else at
    with hou.undos.group("modelUI: add kitbash pieces"):
        c = target_container()
        ids = containers.add_pieces(c, [(p, os.path.splitext(os.path.basename(p))[0], None) for p in paths])
        boxes = [_local_box(c, i) for i in ids]   # each piece at identity: its source's own box
        sizes = [b.sizevec() if b is not None else hou.Vector3(1, 1, 1) for b in boxes]
        gap = GAP * max(s[0] for s in sizes)
        width = sum(s[0] for s in sizes) + gap * (len(ids) - 1)
        x = at[0] - width / 2.0
        inv = c.worldTransform().inverted()   # a moved container: the row still lands where the viewport looks
        xforms = {}
        for i, b, s in zip(ids, boxes, sizes):
            lo, mid = (b.minvec(), b.center()) if b is not None else (hou.Vector3(), hou.Vector3())
            t = hou.Vector3(x - lo[0], at[1] - lo[1], at[2] - mid[2])   # min x on the cursor, on the ground, centred in z
            xforms[i] = hou.hmath.buildTranslate(t) * inv
            x += s[0] + gap
        containers.set_transforms(c, xforms)
    pids = [("piece", c.sessionId(), i) for i in ids]
    scene.current().select(pids)
    return pids


def add_dialog():
    """Ask for USD files (several at once) in the kitbash library and add them."""
    picked = hou.ui.selectFile(start_directory=library() + "/", title="Add kitbash pieces",
                               pattern="*.usd *.usda *.usdc *.usdz", multiple_select=True,
                               chooser_mode=hou.fileChooserMode.Read)
    paths = [hou.text.expandString(p.strip()) for p in (picked or "").split(";") if p.strip()]
    if paths:
        add_files(paths)
