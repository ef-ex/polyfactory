"""modelUI F12 feedback (ideas/modelui.md "F12 feedback"): the artist presses F12, draws on the frozen window, pins notes,
writes a comment and sends; agents read the saved folder. Behaviour copied from Vela's feedback (not its code).

This file is the part without a window: the state snapshot, the markings rendering, the folder writer and the log
buffer (switch feature: ``install`` / ``uninstall``). The overlay is ``feedback_overlay.py``.

Folder: ``<root>/<person>/<YYYY-MM-DD_HHMMSS>/`` with ``state.json`` (written first), ``screenshot.png``, ``marked.png``,
``markings.png``, ``attachments/``, and ``feedback.json`` LAST: a folder that has feedback.json is complete.
Root ``$PF_FEEDBACK_ROOT`` (default F:/ai/feedback/modelui); person = the Windows user name.
"""
import collections
import datetime
import getpass
import json
import logging
import os
import shutil
import subprocess

DEFAULT_ROOT = "F:/ai/feedback/modelui"
LOGGER = "polyfactory.modelui"
LOG_LINES = 200
NOTE_WIDTH = 220          # a note box, in px of the window (scaled by pixels_per_point in the file)
UNITS = "note and stroke positions are pixels of screenshot.png"
COLOURS = {"red": "#ff3b30", "yellow": "#ffd60a", "cyan": "#2ed3f0", "white": "#ffffff"}
WIDTHS = {"S": 3, "M": 6, "L": 12}

LOG = logging.getLogger(__name__)


# --- log buffer ------------------------------------------------------------------------------------------------------
class _Ring(logging.Handler):
    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = collections.deque(maxlen=LOG_LINES)
        self.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))

    def emit(self, record):
        try:
            self.lines.append(self.format(record))
        except Exception:  # noqa: BLE001 - a log handler never raises
            pass


def _session():
    import hou
    return hou.session.__dict__


def log_lines():
    r = _session().get("_pf_modelui_feedback_log")
    return list(r.lines) if r else []


def install():
    """Switch feature hook: start the log buffer, and take the key (keys.py binds it)."""
    s = _session()
    if "_pf_modelui_feedback_log" not in s:
        r, lg = _Ring(), logging.getLogger(LOGGER)
        s["_pf_modelui_feedback_log"] = r
        s["_pf_modelui_feedback_level"] = lg.level
        lg.addHandler(r)
        if lg.level == logging.NOTSET:   # INFO lines reach the buffer; the console is unchanged (no INFO handler)
            lg.setLevel(logging.INFO)


def uninstall():
    s = _session()
    r = s.pop("_pf_modelui_feedback_log", None)
    if r is not None:
        lg = logging.getLogger(LOGGER)
        lg.removeHandler(r)
        lg.setLevel(s.pop("_pf_modelui_feedback_level", logging.NOTSET))


# --- state.json ------------------------------------------------------------------------------------------------------
def _part(out, key, fn):
    try:
        out[key] = fn()
    except Exception as e:  # noqa: BLE001 - one broken section never loses the rest
        out[key] = {"error": "%s: %s" % (type(e).__name__, e)}


def collect_state():
    """modelUI's state now, as plain JSON data. Each section stands alone (an error string replaces a broken one)."""
    import hou
    from hutil.Qt import QtWidgets

    from polyfactory.modelui import containers, scene, switch
    out = {}
    _part(out, "modelui_on", switch.is_on)
    _part(out, "houdini", hou.applicationVersionString)
    _part(out, "hip_file", hou.hipFile.path)

    def viewer():
        sv = hou.ui.curDesktop().paneTabOfType(hou.paneTabType.SceneViewer)
        if sv is None:
            return None
        return {"state": sv.currentState(), "pwd": sv.pwd().path()}
    _part(out, "viewer", viewer)

    def selection():
        sc = scene.current()
        return [{"id": list(p) if isinstance(p, tuple) else p, "kind": "piece" if isinstance(p, tuple) else "object",
                 "name": sc.name(p)} for p in sc.selected()]
    _part(out, "selection", selection)

    def pieces():
        cs = containers.containers()
        return {"containers": len(cs), "pieces": sum(1 for p in scene.current().pieces() if isinstance(p, tuple)),
                "objects": sum(1 for p in scene.current().pieces() if not isinstance(p, tuple))}
    _part(out, "scene", pieces)

    def modify():
        p = _session().get("_pf_modelui_stack")
        if p is None:
            return None
        o, e = p.obj(), p.entry()
        return {"object": o.path() if o is not None else None, "entry": e.name() if e is not None else None}
    _part(out, "modify_panel", modify)

    def dialogs():
        return [type(w).__name__ for w in QtWidgets.QApplication.topLevelWidgets()
                if w.isVisible() and isinstance(w, QtWidgets.QDialog) and type(w).__module__.startswith("polyfactory.")]
    _part(out, "open_dialogs", dialogs)
    out["log"] = log_lines()
    return out


# --- markings rendering ----------------------------------------------------------------------------------------------
def _note_doc(text, width, px):
    from hutil.Qt import QtGui
    d = QtGui.QTextDocument()
    f = QtGui.QFont()
    f.setPixelSize(px)
    d.setDefaultFont(f)
    d.setTextWidth(width)
    d.setPlainText(text)
    return d


def render_markings(size, strokes, notes, scale=1.0):
    """The markings alone on a transparent image of ``size`` (w, h) px. Strokes {colour, width, points}, notes {x, y,
    text, colour} in px of that image; ``scale``: window px -> image px for the note box and its text."""
    from hutil.Qt import QtCore, QtGui
    img = QtGui.QImage(int(size[0]), int(size[1]), QtGui.QImage.Format_ARGB32)
    img.fill(0)
    p = QtGui.QPainter(img)
    p.setRenderHint(QtGui.QPainter.Antialiasing)
    for s in strokes:
        pts = [QtCore.QPointF(x, y) for x, y in s["points"]]
        pen = QtGui.QPen(QtGui.QColor(s["colour"]), s["width"], QtCore.Qt.SolidLine, QtCore.Qt.RoundCap,
                         QtCore.Qt.RoundJoin)
        p.setPen(pen)
        if len(pts) == 1:
            p.drawPoint(pts[0])
        elif pts:
            p.drawPolyline(QtGui.QPolygonF(pts))
    pad = 6 * scale
    for n in notes:
        w = n.get("width", NOTE_WIDTH * scale)
        d = _note_doc(n["text"], w - 2 * pad, max(1, int(round(14 * scale))))
        d.setDefaultStyleSheet("")
        h = d.size().height() + 2 * pad
        r = QtCore.QRectF(n["x"], n["y"], w, h)
        p.setPen(QtGui.QPen(QtGui.QColor(n["colour"]), max(1.0, 2 * scale)))
        p.setBrush(QtGui.QColor(24, 24, 24, 235))
        p.drawRect(r)
        p.save()
        p.translate(n["x"] + pad, n["y"] + pad)
        ctx = QtGui.QAbstractTextDocumentLayout.PaintContext()
        ctx.palette.setColor(QtGui.QPalette.Text, QtGui.QColor("white"))
        d.documentLayout().draw(p, ctx)
        p.restore()
    p.end()
    return img


def render_marked(shot, markings):
    from hutil.Qt import QtGui
    img = shot.convertToFormat(QtGui.QImage.Format_ARGB32)
    p = QtGui.QPainter(img)
    p.drawImage(0, 0, markings)
    p.end()
    return img


# --- the folder ------------------------------------------------------------------------------------------------------
def root():
    return (os.environ.get("PF_FEEDBACK_ROOT") or DEFAULT_ROOT).replace("\\", "/")


def person():
    try:
        return getpass.getuser()
    except Exception:  # noqa: BLE001
        return os.environ.get("USERNAME") or "unknown"


def build_id():
    """The polyfactory commit this Houdini runs, else "unknown"."""
    here = os.path.dirname(os.path.abspath(__file__))
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=here, capture_output=True, text=True, timeout=5)
        return r.stdout.strip() or "unknown"
    except Exception:  # noqa: BLE001
        return "unknown"


def _write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def save(shot, strokes, notes, comment, attachments, state, window, when=None, base=None, user=None, build=None):
    """Write one feedback folder; returns its path. ``shot``: QImage (the frozen frame); ``attachments``: file paths;
    ``window``: {width, height, pixels_per_point} (``pixels`` is added). Order: state.json, the images, attachments,
    feedback.json last. A folder name taken by a second send in the same second gets ``-2``, ``-3``..."""
    when = when or datetime.datetime.now()
    user = user or person()
    base = os.path.join(base or root(), user)
    name = when.strftime("%Y-%m-%d_%H%M%S")
    folder, k = os.path.join(base, name), 1
    while True:
        try:
            os.makedirs(folder)
            break
        except FileExistsError:
            k += 1
            folder = os.path.join(base, "%s-%d" % (name, k))
    _write_json(os.path.join(folder, "state.json"), state)
    scale = shot.width() / max(1, window["width"])
    mk = render_markings((shot.width(), shot.height()), strokes, notes, scale)
    for fn, img in (("screenshot.png", shot), ("marked.png", render_marked(shot, mk)), ("markings.png", mk)):
        if not img.save(os.path.join(folder, fn)):
            raise OSError("could not write " + fn)
    att = []
    if attachments:
        os.makedirs(os.path.join(folder, "attachments"))
        for src in attachments:
            n, dst = os.path.basename(src), None
            dst = os.path.join(folder, "attachments", n)
            i = 1
            while os.path.exists(dst):
                i += 1
                dst = os.path.join(folder, "attachments", "%d_%s" % (i, n))
            shutil.copy2(src, dst)
            att.append({"name": os.path.basename(dst), "from": src.replace("\\", "/")})
    _write_json(os.path.join(folder, "feedback.json"), {
        "user": user, "time": when.isoformat(timespec="seconds"), "build": build or build_id(),
        "comment": comment, "notes": notes, "strokes": strokes, "attachments": att,
        "window": dict(window, pixels=[shot.width(), shot.height()]), "units": UNITS})
    return folder
