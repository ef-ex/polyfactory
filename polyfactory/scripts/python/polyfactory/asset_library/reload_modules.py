"""
Quick module reloader for development
Run this in Houdini's Python Shell to reload all asset_library modules
"""

import sys
import importlib

# List of modules to reload
modules_to_reload = [
    'polyfactory.asset_library.database',
    'polyfactory.asset_library.exporter',
    'polyfactory.asset_library.render',
    'polyfactory.asset_library.export_ui',
]

print("Reloading asset_library modules...")
for module_name in modules_to_reload:
    if module_name in sys.modules:
        importlib.reload(sys.modules[module_name])
        print(f"  Reloaded: {module_name}")
    else:
        print(f"  Not loaded: {module_name}")

print("Done! Modules reloaded.")
