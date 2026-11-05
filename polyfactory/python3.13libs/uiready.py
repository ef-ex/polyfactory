"""polyfactory: register the modelUI toggle hotkey (memory only) once Houdini's UI is ready. Never raises."""
try:
    from polyfactory.modelui import switch
    switch.register_toggle_hotkey()
except Exception:  # noqa: BLE001 - never stop Houdini's start
    import logging
    logging.getLogger(__name__).exception("modelUI toggle hotkey not registered")
