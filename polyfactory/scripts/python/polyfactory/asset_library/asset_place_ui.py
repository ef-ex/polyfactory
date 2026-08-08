"""Asset Place HDA UI - Python Panel for pf_asset_place node.

Shows the full asset browser inside the HDA's parameters pane.
The currently loaded asset is pre-selected when the panel opens.
Double-clicking a different asset updates the node's asset_id and asset_path parms.
"""

import hou
from PySide6 import QtWidgets, QtCore
from polyfactory.asset_library.browser_ui import AssetBrowserWidget
from polyfactory.ui_utils import get_font_stylesheet


class AssetPlaceNodeUI(QtWidgets.QWidget):
    """Python Panel widget for pf_asset_place HDA.

    Embeds the full AssetBrowserWidget. Asset double-clicks are wired to
    write asset_id / asset_path / asset_name back into the node's parameters.
    """

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._node: hou.SopNode | None = None
        self._setup_ui()

    # ── Setup ─────────────────────────────────────────────────────────────────

    def _setup_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.setStyleSheet("background-color: #1e1e1e; color: #e0e0e0;")

        # Header strip showing which node is being driven
        self._header = QtWidgets.QLabel("No node selected")
        self._header.setStyleSheet(
            get_font_stylesheet(size=10, color="#4f5b6e") + " padding: 4px 8px;"
        )
        layout.addWidget(self._header)

        # Full-featured browser including the info/preview panel on the right
        self._browser = AssetBrowserWidget(show_info_panel=True, parent=self)
        self._browser.assetSelected.connect(self._on_asset_selected)
        layout.addWidget(self._browser, stretch=1)

    # ── Public API ────────────────────────────────────────────────────────────

    def set_node(self, node: hou.SopNode | None) -> None:
        """Called by onNodePathChanged — updates which node we drive."""
        self._node = node
        if node:
            asset_name = node.parm("asset_name").eval() if node.parm("asset_name") else ""
            display_name = asset_name if asset_name else node.name()
            self._header.setText(f"Driving: {display_name}")
            self._pre_select_current_asset()
        else:
            self._header.setText("No node selected")

    def refresh(self) -> None:
        """Reload asset list (called on pane activation)."""
        self._browser._load_assets()
        self._pre_select_current_asset()

    # ── Private helpers ───────────────────────────────────────────────────────

    def _pre_select_current_asset(self) -> None:
        """Highlight the thumbnail matching the node's current asset_id."""
        if not self._node:
            return

        asset_id_parm = self._node.parm("asset_id")
        if not asset_id_parm:
            return

        current_id = asset_id_parm.eval()
        if not current_id:
            return

        # Deselect all, then select the matching thumbnail
        for widget in self._browser._thumbnail_widgets:
            is_match = (widget.asset_data.get("asset_id") == current_id or
                        widget.asset_data.get("name") == current_id)
            widget.set_selected(is_match)

    def _on_asset_selected(self, asset_data: dict) -> None:
        """User double-clicked an asset — push into node parms."""
        if not self._node:
            return

        asset_id = asset_data.get("asset_id") or asset_data.get("name", "")
        asset_path = asset_data.get("file_path", "")
        asset_name = asset_data.get("name", "")

        parm_map = {
            "asset_id": asset_id,
            "asset_path": asset_path,
            "asset_name": asset_name,
        }
        for parm_name, value in parm_map.items():
            parm = self._node.parm(parm_name)
            if parm:
                parm.set(value)

        # Update header
        self._header.setText(f"Driving: {asset_name or self._node.name()}")
