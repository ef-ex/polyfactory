"""
123.py - Auto-loaded on Houdini startup
Registers custom viewer states
"""

import hou
import viewerstate.utils as su


def register_viewer_states():
    """Register all Polyfactory viewer states"""

    # Register kitbash placement state
    try:
        from polyfactory.asset_library.kitbash_placement_state import createViewerStateTemplate
        template = createViewerStateTemplate()
        hou.ui.registerViewerState(template)
    except (hou.NotAvailable, AttributeError):
        # Headless / hython context — viewer states not supported, skip silently
        pass
    except Exception as e:
        print(f"Failed to register kitbash placement state: {e}")

    # Register asset placement state (pf_asset_place HDA)
    try:
        from polyfactory.asset_library.asset_place_state import createViewerStateTemplate as _ap_template
        hou.ui.registerViewerState(_ap_template())
    except (hou.NotAvailable, AttributeError):
        pass
    except Exception as e:
        print(f"Failed to register asset placement state: {e}")


# The in-repo Houdini bridge used to autostart here. It is gone: the bridge
# lives in its own repo (ef-ex/houdini-mcp) and is started by that package.
# Autostarting a second copy bound both to port 9876, so which one actually
# served a request depended on start order.


# Run startup hooks. Each is independently guarded so one failing cannot stop
# the others or raise into Houdini's startup.
try:
    register_viewer_states()
except Exception as exc:
    print(f"[PF] viewer-state registration failed: {type(exc).__name__}: {exc}")
