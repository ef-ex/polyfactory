"""
Module reloader for Polyfactory development

Intelligently reloads modules for rapid iteration without restarting Houdini.
Can be used from Python Shell or integrated into shelf tools.

Usage:
    from polyfactory.asset_library import reload_modules
    reload_modules.reload_all()  # Reload everything
    reload_modules.reload_widgets()  # Just widget library
    reload_modules.reload_asset_library()  # Just asset library
"""

import sys
import importlib


def reload_widgets():
    """Reload widget library modules."""
    modules = [
        'polyfactory.widgets.parm_utils',
        'polyfactory.widgets.binding_manager',
        'polyfactory.widgets.widgets',
        'polyfactory.widgets.layouts',
        'polyfactory.widgets.parm_panel',
        'polyfactory.widgets'
    ]
    return _reload_modules(modules, "widget library")


def reload_asset_library():
    """Reload asset library modules."""
    modules = [
        'polyfactory.asset_library.database',
        'polyfactory.asset_library.exporter',
        'polyfactory.asset_library.render',
        'polyfactory.asset_library.export_ui',
        'polyfactory.asset_library.browser_ui'
    ]
    return _reload_modules(modules, "asset library")


def reload_ui_framework():
    """Reload UI framework modules (PyOneDark-based)."""
    modules = [
        'polyfactory.ui_framework.qt_core',
        'polyfactory.ui_framework.core',
        'polyfactory.ui_framework.themes',
        'polyfactory.ui_framework.widgets',
        'polyfactory.ui_framework'
    ]
    return _reload_modules(modules, "UI framework")


def reload_all():
    """Reload all Polyfactory modules."""
    print("="*60)
    print("Reloading all Polyfactory modules...")
    print("="*60)
    
    reload_widgets()
    reload_asset_library()
    reload_ui_framework()
    
    print("="*60)
    print("All modules reloaded!")
    print("="*60)
    return True


def _reload_modules(module_list, context_name="modules"):
    """Internal helper to reload a list of modules."""
    print(f"\nReloading {context_name}...")
    reloaded = 0
    
    for module_name in module_list:
        if module_name in sys.modules:
            try:
                importlib.reload(sys.modules[module_name])
                print(f"  ✓ Reloaded: {module_name}")
                reloaded += 1
            except Exception as e:
                print(f"  ✗ Failed: {module_name} - {e}")
        else:
            print(f"  - Not loaded: {module_name}")
    
    print(f"Reloaded {reloaded}/{len(module_list)} modules")
    return reloaded > 0


# Legacy compatibility - auto-reload when imported directly
if __name__ != "__main__":
    # Being imported, not executed
    pass
else:
    # Being executed directly
    reload_all()
