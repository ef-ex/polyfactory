"""modelUI F12 feedback overlay: a frameless window over Houdini's main window showing the frozen frame, with a pen
(4 colours, 3 widths), an eraser (a stroke or a note), pin notes (click, type), a comment, attachments, Send (Ctrl+Enter)
and Cancel (Esc; asks when there are markings). Saving runs on a thread (``feedback.save``). Python is UI marshalling here
(decision log in ideas/modelui.md).

``show()`` is the entry point (F12 through keys.py, polyfactory > Send feedback). Positions are kept in window px
(logical); ``payload()`` multiplies them by pixels_per_point (= pixels of screenshot.png).
"""
import logging
import threading

import hou
from hutil.Qt import QtCore, QtGui, QtWidgets
from PySide6.QtGui import QShortcut   # hutil.Qt.QtGui has no QShortcut

from polyfactory.modelui import feedback

LOG = logging.getLogger(__name__)
Qt = QtCore.Qt
KEY = "_pf_modelui_feedback_overlay"
ERASE_RADIUS = 10


def _grab(mw):
    """The main window as the screen shows it (GL viewport included); the widget's own render when that is empty."""
    img = QtGui.QImage()
    try:
        img = mw.screen().grabWindow(int(mw.winId()), 0, 0, mw.width(), mw.height()).toImage()
    except Exception:  # noqa: BLE001
        LOG.exception("screen grab failed")
    if img.isNull():
        img = mw.grab().toImage()
    return img


def _near(points, x, y, r):
    pts = points if len(points) > 1 else points * 2
    for (ax, ay), (bx, by) in zip(pts, pts[1:]):
        dx, dy = bx - ax, by - ay
        L2 = dx * dx + dy * dy
        t = 0 if L2 == 0 else max(0, min(1, ((x - ax) * dx + (y - ay) * dy) / L2))
        if (x - ax - t * dx) ** 2 + (y - ay - t * dy) ** 2 <= r * r:
            return True
    return False


class _Note(QtWidgets.QFrame):
    def __init__(self, parent, x, y, colour, on_close):
        super().__init__(parent)
        self.colour = colour
        self.setStyleSheet("QFrame{background:#181818;border:2px solid %s;} QPlainTextEdit{color:white;border:0;}"
                           "QToolButton{color:white;border:0;}" % colour)
        lay = QtWidgets.QHBoxLayout(self)
        lay.setContentsMargins(4, 2, 2, 2)
        self.edit = QtWidgets.QPlainTextEdit()
        self.edit.setFixedHeight(54)
        self.edit.setPlaceholderText("note")
        x_btn = QtWidgets.QToolButton()
        x_btn.setText("x")
        x_btn.clicked.connect(lambda: on_close(self))
        lay.addWidget(self.edit)
        lay.addWidget(x_btn, 0, Qt.AlignTop)
        self.setFixedWidth(feedback.NOTE_WIDTH)
        self.move(int(x), int(y))
        self.show()
        self.edit.setFocus()


class Overlay(QtWidgets.QWidget):
    def __init__(self, mw, shot, state):
        super().__init__(mw, Qt.Window | Qt.FramelessWindowHint)
        self.setObjectName("pf_feedback_overlay")
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.shot, self.state = shot, state
        self.ppp = shot.width() / max(1, mw.width())
        self.pix = QtGui.QPixmap.fromImage(shot)
        self.strokes, self.notes, self.files = [], [], []
        self.tool, self.colour, self.width = "pen", feedback.COLOURS["red"], feedback.WIDTHS["M"]
        self.cur = None
        self.done = False
        self.setGeometry(mw.geometry())
        self.setMouseTracking(True)
        self._ui()
        for seq in ("Ctrl+Return", "Ctrl+Enter"):
            QShortcut(QtGui.QKeySequence(seq), self, activated=self.send)
        QShortcut(QtGui.QKeySequence("Esc"), self, activated=self.cancel)

    # --- toolbar -------------------------------------------------------------------------------------------------------
    def _ui(self):
        bar = self.bar = QtWidgets.QFrame(self)
        bar.setObjectName("bar")
        bar.setStyleSheet("QFrame#bar{background:#202020;border:1px solid #555;} QPushButton{color:white;padding:3px 8px}"
                          "QPushButton:checked{background:#4a6fa5}")
        lay = QtWidgets.QHBoxLayout(bar)
        group = QtWidgets.QButtonGroup(self)
        self.buttons = {}

        def btn(text, key, checked=False, group_=None, slot=None):
            b = QtWidgets.QPushButton(text)
            b.setCheckable(group_ is not None)
            b.setChecked(checked)
            if group_ is not None:
                group_.addButton(b)
            b.clicked.connect(slot)
            b.setFocusPolicy(Qt.NoFocus)
            lay.addWidget(b)
            self.buttons[key] = b
            return b
        for t in ("pen", "note", "eraser"):
            btn(t.capitalize(), t, t == "pen", group, lambda _=False, t=t: setattr(self, "tool", t))
        cg = QtWidgets.QButtonGroup(self)
        for name, hexc in feedback.COLOURS.items():
            b = btn("", name, name == "red", cg, lambda _=False, c=hexc: setattr(self, "colour", c))
            b.setStyleSheet("QPushButton{background:%s;min-width:16px;max-width:16px}"
                            "QPushButton:checked{border:3px solid #4a6fa5}" % hexc)
        wg = QtWidgets.QButtonGroup(self)
        for name, px in feedback.WIDTHS.items():
            btn(name, "w" + name, name == "M", wg, lambda _=False, w=px: setattr(self, "width", w))
        btn("Attach...", "attach", slot=self.attach)
        self.count = QtWidgets.QLabel("")
        self.count.setStyleSheet("color:#ccc")
        lay.addWidget(self.count)
        self.comment = QtWidgets.QPlainTextEdit(self)
        self.comment.setPlaceholderText("Comment (Ctrl+Enter sends, Esc cancels)")
        self.comment.setFixedSize(560, 64)
        self.comment.setStyleSheet("background:#202020;color:white;border:1px solid #555")
        self.row = QtWidgets.QFrame(self)
        self.row.setStyleSheet("QPushButton{color:white;padding:3px 10px}")
        rl = QtWidgets.QHBoxLayout(self.row)
        rl.setContentsMargins(0, 0, 0, 0)
        self.send_button = QtWidgets.QPushButton("Send")
        self.cancel_button = QtWidgets.QPushButton("Cancel")
        self.send_button.clicked.connect(self.send)
        self.cancel_button.clicked.connect(self.cancel)
        rl.addWidget(self.send_button)
        rl.addWidget(self.cancel_button)
        bar.adjustSize()
        bar.move(12, 12)
        self._layout_bottom()

    def _layout_bottom(self):
        self.comment.move(12, self.height() - 76)
        self.row.adjustSize()
        self.row.move(self.comment.x() + self.comment.width() + 8, self.height() - 76)

    def resizeEvent(self, ev):  # noqa: N802
        self._layout_bottom()

    def _refresh_count(self):
        n = len(self.files)
        self.count.setText("%d file%s" % (n, "" if n == 1 else "s") if n else "")

    # --- painting and drawing ------------------------------------------------------------------------------------------
    def paintEvent(self, ev):  # noqa: N802
        p = QtGui.QPainter(self)
        p.drawPixmap(self.rect(), self.pix)
        p.setRenderHint(QtGui.QPainter.Antialiasing)
        for s in self.strokes + ([self.cur] if self.cur else []):
            pts = [QtCore.QPointF(x, y) for x, y in s["points"]]
            p.setPen(QtGui.QPen(QtGui.QColor(s["colour"]), s["width"], Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            if len(pts) == 1:
                p.drawPoint(pts[0])
            else:
                p.drawPolyline(QtGui.QPolygonF(pts))

    def mousePressEvent(self, ev):  # noqa: N802
        if ev.button() != Qt.LeftButton:
            return
        x, y = ev.position().x(), ev.position().y()
        if self.tool == "pen":
            self.cur = {"colour": self.colour, "width": self.width, "points": [(x, y)]}
        elif self.tool == "note":
            self.notes.append(_Note(self, x, y, self.colour, self._drop_note))
        else:
            self._erase(x, y)
        self.update()

    def mouseMoveEvent(self, ev):  # noqa: N802
        x, y = ev.position().x(), ev.position().y()
        if self.cur is not None:
            self.cur["points"].append((x, y))
            self.update()
        elif self.tool == "eraser" and ev.buttons() & Qt.LeftButton:
            self._erase(x, y)

    def mouseReleaseEvent(self, ev):  # noqa: N802
        if self.cur is not None:
            self.strokes.append(self.cur)
            self.cur = None
            self.update()

    def _erase(self, x, y):
        self.strokes = [s for s in self.strokes if not _near(s["points"], x, y, ERASE_RADIUS + s["width"] / 2)]
        self.update()

    def _drop_note(self, note):
        self.notes.remove(note)
        note.deleteLater()

    # --- actions -------------------------------------------------------------------------------------------------------
    def attach(self):
        files, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Attach files")
        self.files += files
        self._refresh_count()

    def _live_notes(self):
        return [n for n in self.notes if n.edit.toPlainText().strip()]

    def has_markings(self):
        return bool(self.strokes or self._live_notes())

    def cancel(self):
        if self.done:
            return
        if self.has_markings() and not self._confirm_discard():
            return
        self.done = True
        self.close()

    def _confirm_discard(self):
        return QtWidgets.QMessageBox.question(
            self, "Discard feedback?", "Discard your markings?",
            QtWidgets.QMessageBox.Discard | QtWidgets.QMessageBox.Cancel) == QtWidgets.QMessageBox.Discard

    def payload(self):
        """Strokes and notes for ``feedback.save``, positions in px of screenshot.png."""
        k = self.ppp
        strokes = [{"colour": s["colour"], "width": s["width"] * k, "points": [[x * k, y * k] for x, y in s["points"]]}
                   for s in self.strokes]
        notes = [{"x": n.x() * k, "y": n.y() * k, "text": n.edit.toPlainText().strip(), "colour": n.colour,
                  "width": feedback.NOTE_WIDTH * k} for n in self._live_notes()]
        return strokes, notes

    def send(self):
        if self.done:
            return
        self.done = True
        strokes, notes = self.payload()
        args = (self.shot, strokes, notes, self.comment.toPlainText().strip(), list(self.files), self.state,
                {"width": self.rect().width(), "height": self.rect().height(), "pixels_per_point": self.ppp})
        self.close()
        threading.Thread(target=_save_thread, args=args, daemon=True).start()

    def closeEvent(self, ev):  # noqa: N802
        hou.session.__dict__.pop(KEY, None)
        super().closeEvent(ev)


def _status(msg, severity=None):
    try:
        hou.ui.setStatusMessage(msg, severity or hou.severityType.Message)
    except Exception:  # noqa: BLE001
        pass


def _save_thread(*args):
    import hdefereval
    try:
        folder = feedback.save(*args)
        msg, sev = "Feedback saved: " + folder.replace("\\", "/"), None
    except Exception as e:  # noqa: BLE001
        LOG.exception("feedback save failed")
        msg, sev = "Feedback NOT saved: %s" % e, hou.severityType.Error
    hdefereval.executeDeferred(lambda: _status(msg, sev))


def show():
    """Freeze the window and open the overlay (one at a time). Returns the overlay, or None."""
    if hou.session.__dict__.get(KEY) is not None:
        return None
    mw = hou.qt.mainWindow()
    state = feedback.collect_state()   # before the overlay changes anything
    ov = Overlay(mw, _grab(mw), state)
    hou.session.__dict__[KEY] = ov
    ov.show()
    ov.raise_()
    ov.activateWindow()
    ov.setFocus()
    return ov
