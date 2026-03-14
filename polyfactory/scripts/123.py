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


# Register on startup
register_viewer_states()
