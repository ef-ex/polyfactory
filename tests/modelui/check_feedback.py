"""Headless checks of modelUI F12 feedback (modelui/feedback.py: the folder writer, markings rendering, state.json, the log
buffer), each with a paired source mutation that must turn it red.

Run:  hython tests/modelui/check_feedback.py     (exit 0 = all green AND every mutation reddened its paired check)
Writes only under F:/cache/modelui/fb/headless. Throwaway session, never saves a .hip.

What these cannot see: the overlay window (gui_feedback.py), the screen grab of a real GL viewport, the hotkey, the
selection/piece parts of state.json for container pieces (objects only here), text layout beyond "white pixels inside
the note box", Windows file locking of a folder an agent has open.
"""
import datetime
import json
import os
import shutil
import subprocess
import sys
import tempfile
import logging

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import hou  # noqa: E402
from hutil.Qt import QtGui, QtWidgets  # noqa: E402
from PySide6.QtGui import QColor  # noqa: E402,F401

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "polyfactory", "scripts", "python"))
from polyfactory.modelui import feedback  # noqa: E402

APP = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
OUT = "F:/cache/modelui/fb/headless"
WHEN = datetime.datetime(2026, 11, 12, 14, 30, 5)
BLUE = (0, 0, 255)
STROKES = [{"colour": "#ff3b30", "width": 12, "points": [[40, 100], [160, 100]]},
           {"colour": "#ffd60a", "width": 6, "points": [[40, 160], [160, 160]]},
           {"colour": "#2ed3f0", "width": 12, "points": [[300, 40]]}]
NOTES = [{"x": 200, "y": 150, "text": "move this", "colour": "#ffd60a", "width": 160}]
WINDOW = {"width": 200, "height": 150, "pixels_per_point": 2.0}


def shot():
    img = QtGui.QImage(400, 300, QtGui.QImage.Format_RGB32)
    img.fill(QtGui.QColor(*BLUE))
    return img


def rgba(img, x, y):
    c = img.pixelColor(x, y)
    return (c.red(), c.green(), c.blue(), c.alpha())


def listing(folder):
    return sorted(os.path.relpath(os.path.join(d, f), folder).replace("\\", "/")
                  for d, _, fs in os.walk(folder) for f in fs)


def checks(out):
    shutil.rmtree(OUT, ignore_errors=True)
    att = os.path.join(OUT, "att.txt")
    os.makedirs(OUT)
    with open(att, "w") as f:
        f.write("attached")
    state = {"modelui_on": True, "log": ["a"]}
    seen = []   # (file, what existed when it was written): the write order, observed
    orig = feedback._write_json

    def spy(path, data):
        seen.append((os.path.basename(path), listing(os.path.dirname(path))))
        orig(path, data)
    feedback._write_json = spy
    try:
        folder = feedback.save(shot(), STROKES, NOTES, "the comment", [att], state, WINDOW, when=WHEN, base=OUT + "/root",
                               user="tester", build="abc123")
    finally:
        feedback._write_json = orig
    out["folder_layout"] = (folder.replace("\\", "/") == OUT + "/root/tester/2026-11-12_143005"
                            and listing(folder) == ["attachments/att.txt", "feedback.json", "marked.png", "markings.png",
                                                    "screenshot.png", "state.json"])
    full = ["attachments/att.txt", "marked.png", "markings.png", "screenshot.png", "state.json"]
    out["write_order"] = (seen[0] == ("state.json", []) and [s[0] for s in seen] == ["state.json", "feedback.json"]
                          and seen[-1][1] == full)
    fb = json.load(open(folder + "/feedback.json"))
    out["feedback_json"] = (fb["user"] == "tester" and fb["time"] == "2026-11-12T14:30:05" and fb["build"] == "abc123"
                            and fb["comment"] == "the comment" and fb["notes"] == NOTES and fb["strokes"] == STROKES
                            and fb["attachments"] == [{"name": "att.txt", "from": att.replace("\\", "/")}]
                            and fb["window"] == {"width": 200, "height": 150, "pixels_per_point": 2.0, "pixels": [400, 300]}
                            and fb["units"] == "note and stroke positions are pixels of screenshot.png")
    out["state_json"] = json.load(open(folder + "/state.json")) == state
    out["attachment_copied"] = open(folder + "/attachments/att.txt").read() == "attached"
    s, m, mk = (QtGui.QImage(folder + "/" + n) for n in ("screenshot.png", "marked.png", "markings.png"))
    out["screenshot_is_the_frame"] = (not s.isNull() and (s.width(), s.height()) == (400, 300)
                                      and rgba(s, 100, 100) == BLUE + (255,) and rgba(s, 300, 40) == BLUE + (255,))
    out["markings_alpha"] = (rgba(mk, 100, 150) == (0, 0, 0, 0) and rgba(mk, 5, 5) == (0, 0, 0, 0)
                             and rgba(mk, 100, 100)[3] == 255)
    out["marking_colours"] = (rgba(mk, 100, 100) == (255, 59, 48, 255) and rgba(mk, 100, 160) == (255, 214, 10, 255)
                              and rgba(mk, 300, 40) == (46, 211, 240, 255))
    out["marking_width"] = (rgba(mk, 100, 105)[3] == 255 and rgba(mk, 100, 95)[3] == 255   # width 12: +-5 covered
                            and rgba(mk, 100, 108)[3] == 0 and rgba(mk, 100, 92)[3] == 0   # +-8 clear
                            and rgba(mk, 100, 162)[3] == 255 and rgba(mk, 100, 165)[3] == 0)  # width 6
    out["note_box"] = (rgba(mk, 200, 180) == (255, 214, 10, 255)   # its left border, yellow
                       and any(rgba(mk, x, y)[:3] == (255, 255, 255) for x in range(206, 330) for y in range(156, 200))
                       and rgba(mk, 380, 180)[3] == 0)
    out["marked_has_both"] = (rgba(m, 100, 100) == (255, 59, 48, 255) and rgba(m, 100, 150) == BLUE + (255,)
                              and rgba(m, 200, 180) == (255, 214, 10, 255))
    f2 = feedback.save(shot(), [], [], "", [], state, WINDOW, when=WHEN, base=OUT + "/root", user="tester", build="x")
    out["same_second_two_folders"] = (f2 != folder and os.path.exists(f2 + "/feedback.json")
                                      and os.path.exists(folder + "/feedback.json")
                                      and not os.path.exists(f2 + "/attachments"))


def state_checks(out):
    hou.hipFile.clear(suppress_save_prompt=True)
    lg = logging.getLogger(feedback.LOGGER)
    level0, n0 = lg.level, len(lg.handlers)
    feedback.install()
    child = logging.getLogger("polyfactory.modelui.pieces_ui")
    for i in range(300):
        child.warning("line %d", i)
    hou.node("/obj").createNode("geo", "box_a").setSelected(True)
    st = feedback.collect_state()
    out["log_last_200"] = (len(st["log"]) == 200 and st["log"][-1].endswith("line 299") and st["log"][0].endswith("line 100"))
    out["state_fields"] = (st["modelui_on"] is False and st["houdini"] == hou.applicationVersionString()
                           and st["hip_file"] == hou.hipFile.path() and isinstance(st["open_dialogs"], list)
                           and st["scene"] == {"containers": 0, "pieces": 0, "objects": 1}
                           and st["modify_panel"] is None)
    out["state_selection"] = [(x["kind"], x["name"]) for x in st["selection"]] == [("object", "box_a")]
    json.dumps(st)
    feedback.uninstall()
    out["log_uninstalled"] = len(lg.handlers) == n0 and lg.level == level0 and feedback.log_lines() == []


def case(out, name, fn):
    """One check: an exception inside it is that check red (not the whole run)."""
    try:
        out[name] = bool(fn())
    except Exception:  # noqa: BLE001
        out[name] = False


def under(path, folder):
    return path.replace("\\", "/").startswith(folder)


def robust_checks(out):
    shutil.rmtree(OUT + "/rb", ignore_errors=True)
    os.makedirs(OUT + "/rb/tmp")
    tempfile.tempdir = OUT + "/rb/tmp"   # the fallback goes here, never the real temp
    kw = dict(when=WHEN, user="tester", build="x")
    args = (shot(), STROKES, NOTES, "c", [], {}, WINDOW)
    open(OUT + "/rb/afile", "w").close()

    def good():
        f, err = feedback.save_safe(*args, base=OUT + "/rb/ok", **kw)
        return err is None and os.path.exists(f + "/feedback.json") and under(f, OUT + "/rb/ok")
    case(out, "good_save_no_error", good)

    def unwritable():   # a plain file where the root's folder should be
        f, err = feedback.save_safe(*args, base=OUT + "/rb/afile/root", **kw)
        return (err is not None and under(f, OUT + "/rb/tmp/pf_feedback/tester/")
                and os.path.exists(f + "/feedback.json") and os.path.exists(f + "/screenshot.png"))
    case(out, "fallback_when_root_unwritable", unwritable)

    def half():   # feedback.json refused under the root: no half folder is left there, the fallback is complete
        orig = feedback._write_json

        def refuse(path, data):
            if "/rb/half/" in path.replace("\\", "/") and path.endswith("feedback.json"):
                raise OSError("disk full")
            orig(path, data)
        feedback._write_json = refuse
        try:
            f, err = feedback.save_safe(*args, base=OUT + "/rb/half", **kw)
        finally:
            feedback._write_json = orig
        return (os.listdir(OUT + "/rb/half/tester") == [] and err is not None and "disk full" in err
                and os.path.exists(f + "/feedback.json") and under(f, OUT + "/rb/tmp"))
    case(out, "no_half_folder_left", half)

    def attach():   # an unreadable attachment is listed, the feedback is kept
        f, err = feedback.save_safe(*args[:4], [OUT + "/rb/nofile.txt"], *args[5:], base=OUT + "/rb/att", **kw)
        a = json.load(open(f + "/feedback.json"))["attachments"]
        return err is None and len(a) == 1 and a[0]["name"] is None and "error" in a[0]
    case(out, "bad_attachment_kept", attach)

    def prerendered():   # the images made on the main thread are the ones written
        mk = QtGui.QImage(400, 300, QtGui.QImage.Format_ARGB32)
        mk.fill(0)
        mk.setPixelColor(7, 9, QColor(0, 255, 0))
        mrk = shot()
        mrk.fill(QColor(255, 0, 255))
        orig_r = feedback.render_markings

        def no_render(*a, **k):
            raise AssertionError("save rendered on its own")
        feedback.render_markings = no_render
        try:
            f = feedback.save(*args, base=OUT + "/rb/pre", rendered=(mrk, mk), **kw)
        finally:
            feedback.render_markings = orig_r
        return (QtGui.QImage(f + "/markings.png").pixelColor(7, 9).green() == 255
                and QtGui.QImage(f + "/marked.png").pixelColor(50, 50).red() == 255
                and QtGui.QImage(f + "/marked.png").pixelColor(50, 50).blue() == 255)
    case(out, "prerendered_images_written", prerendered)

    def black():
        blk = QtGui.QImage(64, 40, QtGui.QImage.Format_RGB32)
        blk.fill(QColor(0, 0, 0))
        one = QtGui.QImage(blk)
        one.setPixelColor(63, 39, QColor(0, 0, 1))
        return feedback.is_black(blk) and not feedback.is_black(one) and not feedback.is_black(shot())
    case(out, "black_detected", black)

    def black_json():
        f = feedback.save(*args, base=OUT + "/rb/blk", black=True, **kw)
        f2 = feedback.save(*args, base=OUT + "/rb/blk2", **kw)
        return (json.load(open(f + "/feedback.json"))["screenshot_black"] is True
                and json.load(open(f2 + "/feedback.json"))["screenshot_black"] is False)
    case(out, "black_flag_in_json", black_json)

    def build():   # this repo yes; any other git repo, or none: "unknown"
        other = "F:/cache/modelui/fb/other_repo"
        if not os.path.isdir(other + "/.git"):
            os.makedirs(other, exist_ok=True)
            git = ["git", "-c", "user.name=t", "-c", "user.email=t@t"]
            subprocess.run(git + ["init", "-q"], cwd=other, check=True)
            open(other + "/a.txt", "w").write("x")
            subprocess.run(git + ["add", "a.txt"], cwd=other, check=True)
            subprocess.run(git + ["commit", "-qm", "x"], cwd=other, check=True)
        mine = feedback.build_id()
        return (len(mine) == 7 and all(c in "0123456789abcdef" for c in mine)
                and feedback.build_id(other) == "unknown" and feedback.build_id(OUT + "/rb") == "unknown")
    case(out, "build_id_only_polyfactory", build)

    def off():   # modelUI off closes an open overlay
        w = QtWidgets.QWidget()
        w.show()
        w.done = False
        hou.session.__dict__["_pf_modelui_feedback_overlay"] = w
        feedback.install()
        feedback.uninstall()
        return not w.isVisible() and w.done is True and "_pf_modelui_feedback_overlay" not in hou.session.__dict__
    case(out, "off_closes_overlay", off)


def mutate(mod, pairs):
    path = mod.__file__
    with open(path, encoding="utf-8") as f:
        src = f.read()
    new = src
    for old, rep in pairs:
        if new.count(old) != 1:
            raise RuntimeError("mutation snippet not found exactly once: %r" % old)
        new = new.replace(old, rep)
    exec(compile(new, path, "exec"), mod.__dict__)
    return lambda: exec(compile(src, path, "exec"), mod.__dict__)


F = feedback
ST = '        _write_json(os.path.join(folder, "state.json"), state)\n'
MUTATIONS = [   # (name, check, [(old, new)])
    ("state_last", "write_order", [(ST, ""), ("    except BaseException:\n", ST + "    except BaseException:\n")]),
    ("feedback_early", "write_order", [(ST, ST + '        _write_json(os.path.join(folder, "feedback.json"), {})\n')]),
    ("marked_without_markings", "marked_has_both", [("    p.drawImage(0, 0, markings)", "    pass")]),
    ("markings_opaque", "markings_alpha", [("    img.fill(0)\n", "    img.fill(0xff000000)\n")]),
    ("width_ignored", "marking_width", [('QtGui.QColor(s["colour"]), s["width"]', 'QtGui.QColor(s["colour"]), 1')]),
    ("colour_ignored", "marking_colours", [('QtGui.QPen(QtGui.QColor(s["colour"])', 'QtGui.QPen(QtGui.QColor("#000000")')]),
    ("note_box_missing", "note_box", [("        p.drawRect(r)\n", "")]),
    ("note_text_missing", "note_box", [("        d.documentLayout().draw(p, ctx)\n", "")]),
    ("screenshot_has_markings", "screenshot_is_the_frame", [('("screenshot.png", shot)', '("screenshot.png", rendered[0])')]),
    ("same_folder_reused", "same_second_two_folders", [("os.makedirs(folder)", "os.makedirs(folder, exist_ok=True)")]),
    ("units_dropped", "feedback_json", [('"units": UNITS', '"units": ""')]),
    ("pixels_are_window", "feedback_json", [('dict(window, pixels=[shot.width(), shot.height()])', 'dict(window, pixels=[window["width"], window["height"]])')]),
    ("no_person_folder", "folder_layout", [("base = os.path.join(base or root(), user)", "base = base or root()")]),
    ("attachment_not_copied", "attachment_copied", [("            shutil.copy2(src, dst)\n", "            open(dst, 'w').close()\n")]),
    ("log_unbounded", "log_last_200", [("collections.deque(maxlen=LOG_LINES)", "collections.deque()")]),
    ("log_handler_stays", "log_uninstalled", [("        lg.removeHandler(r)\n", "")]),
    ("state_not_written", "state_json", [(ST, '        _write_json(os.path.join(folder, "state.json"), {})\n')]),
    ("modelui_always_on", "state_fields", [('_part(out, "modelui_on", switch.is_on)', '_part(out, "modelui_on", lambda: True)')]),
    ("no_fallback", "fallback_when_root_unwritable", [("    return save(*args, **dict(kw, base=os.path.join(tempfile.gettempdir(), \"pf_feedback\"))), err", "    raise RuntimeError(err)")]),
    ("half_folder_kept", "no_half_folder_left", [("        shutil.rmtree(folder, ignore_errors=True)\n        raise", "        raise")]),
    ("failure_unreported", "fallback_when_root_unwritable", [('pf_feedback"))), err', 'pf_feedback"))), None')]),
    ("false_alarm", "good_save_no_error", [("        return save(*args, **kw), None", "        return save(*args, **kw), 'x'")]),
    ("attachment_error_fatal", "bad_attachment_kept", [("                except OSError as e:", "                except ZeroDivisionError as e:")]),
    ("renders_again", "prerendered_images_written", [("        if rendered is None:\n", "        if True:\n")]),
    ("black_never", "black_detected", [("    return b.count(0) == 3 * (len(b) // 4)", "    return False")]),
    ("black_flag_dropped", "black_flag_in_json", [('"screenshot_black": bool(black),', '"screenshot_black": False,')]),
    ("any_repo_build", "build_id_only_polyfactory", [("return head[:7] if mine else \"unknown\"", "return head[:7]")]),
    ("overlay_stays_on_off", "off_closes_overlay", [("        ov.close()\n    r = s.pop", "        pass\n    r = s.pop")]),
    ("selection_empty", "state_selection", [("for p in sc.selected()]", "for p in []]")]),
]


def run():
    out = {}
    for fn in (checks, state_checks, robust_checks):
        try:
            fn(out)
        except Exception as e:  # noqa: BLE001 - an exception is a red check
            out["_exception"] = "%s: %s" % (type(e).__name__, e)
    return out


def main():
    base = run()
    bad = [k for k, v in base.items() if v is not True]
    for k, v in base.items():
        print("%-28s %s" % (k, "ok" if v is True else "RED %s" % v))
    names = set(base)
    for name, check, pairs in MUTATIONS:
        restore = mutate(F, pairs)
        try:
            res = run()
        finally:
            restore()
        red = res.get(check) is False
        print("mutation %-26s -> %-26s %s" % (name, check, "red (good)" if red else "NOT RED %s" % res.get("_exception", "")))
        if not red:
            bad.append("mutation " + name)
        names.discard(check)
    names.discard("_exception")
    if names:
        print("checks without a mutation:", sorted(names))
        bad.append("unpaired checks")
    print("FAIL" if bad else "PASS", bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
