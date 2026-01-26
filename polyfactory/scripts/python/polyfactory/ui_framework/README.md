# Polyfactory UI Framework

Modern Qt widget library for Polyfactory tools and Houdini Python panels.

## Attribution

This framework is based on **PyOneDark Qt Widgets Modern GUI** by Wanderson M. Pimenta.

- **Original Repository:** https://github.com/Wanderson-Magalhaes/PyOneDark_Qt_Widgets_Modern_GUI
- **Original Author:** Wanderson M. Pimenta
- **License:** MIT License (see LICENSE file)
- **Copyright:** (c) 2021 Wanderson M. Pimenta

We are grateful for the excellent work and for making it available under the MIT license.

## Polyfactory Integration

This fork has been integrated into Polyfactory to provide:
- Consistent UI/UX across all Polyfactory tools
- Modern, polished interface for Houdini Python panels
- Standalone pipeline tool interfaces
- Custom widgets for 3D/asset management workflows

## Structure

```
ui_framework/
  core/          - Core framework components
  widgets/       - UI widget library
  themes/        - OneDark and custom themes
  images/        - UI resources
  qt_core.py     - Qt core imports wrapper
  LICENSE        - MIT License from original project
```

## Usage in Polyfactory

```python
from polyfactory.ui_framework import widgets, themes

# Use themed widgets in your tools
button = widgets.PyPushButton(text="Export")
theme = themes.OneDarkTheme()
```

## Modifications

Modifications from the original include:
- Integration with Polyfactory package structure
- Compatibility with Houdini's PySide6 environment
- Custom widgets for pipeline workflows
- Additional themes and styling options

## Credits

Original work: Wanderson M. Pimenta
Polyfactory integration: Polyfactory Team
