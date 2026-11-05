"""modelUI | Houdini: switch the window between the modeling mode and Houdini's own UI in a running session.

``install()`` is all-or-nothing: it shows the ModelUI desk ($POLYFACTORY/desktop/ModelUI.desk) and installs FEATURES
in order; if any step fails, the steps already done are undone, newest first, and Hannes sees a message.
``uninstall()`` undoes everything and shows the desk that was current before. Nothing is written to Houdini's
preference files. Reachable through ``toggle_later()``: the hotkey TOGGLE_KEY (registered by uiready.py, memory only)
and the main menu entry polyfactory > modelUI | Houdini. Pattern: the Maya surface project's ``switch.py``.
"""
import importlib
import logging
import traceback

import hou

LOG = logging.getLogger(__name__)

DESK = "ModelUI"
FALLBACK_DESK = "Build"
TOGGLE_SYMBOL = "h.pf_modelui_toggle"   # = the menu item id in MainMenuCommon.xml
TOGGLE_KEY = "Alt+Ctrl+Shift+X"   # Houdini's own spelling (it reorders modifiers)
FEATURES = ["polyfactory.modelui.keys", "polyfactory.modelui.input_layer"]   # install order; uninstall reverses

_state = hou.session.__dict__.setdefault(
    "_pf_modelui_switch", {"on": False, "prev_desk": None, "done": [], "busy": False, "error": None})


def is_on():
    return _state["on"]


def _set_desk(desk):
    with hou.undos.disabler():   # Maya surface R3r: a desk change records a "Clear Node Selection" undo step
        desk.setAsCurrent()


def _rollback():
    """Undo what install() did so far, newest first. Never raises."""
    for step in reversed(_state["done"]):
        try:
            if step == "desk":
                _set_desk(hou.ui.desktop(_state["prev_desk"] or FALLBACK_DESK) or hou.ui.desktop(FALLBACK_DESK))
            else:
                importlib.import_module(step).uninstall()
        except Exception:  # noqa: BLE001
            LOG.exception("modelUI rollback of %s failed", step)
    _state["done"] = []


def install():
    """Switch modelUI on. Returns True when it is on afterwards."""
    if _state["on"]:
        return True
    _state["done"], _state["error"] = [], None
    try:
        desk = hou.ui.desktop(DESK)
        if desk is None:
            raise RuntimeError("desk %r not found on HOUDINI_PATH" % DESK)
        cur = hou.ui.curDesktop().name()
        _state["prev_desk"] = cur if cur != DESK else _state["prev_desk"]
        _set_desk(desk)
        _state["done"].append("desk")
        for name in FEATURES:
            importlib.import_module(name).install()
            _state["done"].append(name)
    except Exception:  # noqa: BLE001 - all or nothing
        _state["error"] = traceback.format_exc()
        LOG.error("modelUI install failed, rolling back\n%s", _state["error"])
        _rollback()
        try:
            hou.ui.setStatusMessage("modelUI could not start (see the console). Houdini runs as usual.",
                                    hou.severityType.Warning)
        except Exception:  # noqa: BLE001
            pass
        return False
    _state["on"] = True
    return True


def uninstall():
    """Back to Houdini's UI: everything off, the previous desk shows."""
    if _state["on"]:
        _rollback()
        _state["on"] = False


def toggle():
    uninstall() if _state["on"] else install()


def toggle_later():
    """``toggle()`` after the current UI event (hotkey, menu). A second request while one waits is dropped."""
    if _state["busy"]:
        return
    _state["busy"] = True
    import hdefereval

    def run():
        try:
            toggle()
        finally:
            _state["busy"] = False
    hdefereval.executeDeferred(run)


def register_toggle_hotkey():
    """The toggle key, in memory only (never saved). Called from uiready.py. Never raises."""
    try:
        hou.hotkeys.addCommand(TOGGLE_SYMBOL, "modelUI | Houdini", "Switch between modelUI and Houdini's UI")
        if TOGGLE_KEY not in hou.hotkeys.assignments("h", TOGGLE_SYMBOL):
            hou.hotkeys.addAssignment("h", TOGGLE_SYMBOL, TOGGLE_KEY)
    except Exception:  # noqa: BLE001
        LOG.exception("modelUI: could not register the toggle hotkey")
