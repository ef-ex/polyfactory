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


def start_bridge_server():
    """Auto-start the Houdini Bridge (AI-agent control) on interactive launch.

    `123.py` runs once at Houdini startup (per SideFX docs), so the session-level
    bridge starts a single time. Skipped in headless/hython (HDA build scripts
    must not open a socket) and when PF_BRIDGE_AUTOSTART=0.

    Fully hardened: no failure here may raise into Houdini startup. On any
    problem we emit ONE controlled line and let Houdini carry on.
    """
    try:
        import os
        if not hou.isUIAvailable():
            return
        if os.environ.get("PF_BRIDGE_AUTOSTART", "1") == "0":
            return
        from polyfactory.houdini_bridge import start_server
        server = start_server()
        if server is not None and server.is_running():
            print(f"[PF Bridge] started on {server.host}:{server.port}")
        else:
            print("[PF Bridge] did not start (port busy or server not running). "
                  "Houdini is unaffected; start manually from the AI Bridge shelf.")
    except Exception as exc:
        # Controlled, single-line report — never a traceback at startup.
        print(f"[PF Bridge] autostart failed: {type(exc).__name__}: {exc}. "
              "Houdini is unaffected; start manually from the AI Bridge shelf.")


# Run startup hooks. Each is independently guarded so one failing cannot stop
# the others or raise into Houdini's startup.
try:
    register_viewer_states()
except Exception as exc:
    print(f"[PF] viewer-state registration failed: {type(exc).__name__}: {exc}")
start_bridge_server()
