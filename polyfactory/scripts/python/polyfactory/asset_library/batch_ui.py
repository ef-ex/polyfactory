"""
Asset Group Row widget used by the inline batch mode in AssetExportDialog.
"""

from PySide6 import QtWidgets
from typing import Dict, List, Optional

from polyfactory.widgets.tag_input import TagInputWidget


# ── Asset group row ───────────────────────────────────────────────────────────

class AssetGroupRow(QtWidgets.QWidget):
    """One row in the detected-assets list.

    Displays a checkbox, sequential index, name field, category combo,
    tags widget, and a prim/island count label.
    """

    def __init__(
        self,
        index: int,
        group: Dict,
        categories: List[str],
        available_tags: List[str],
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.index: int = index
        self.group: Dict = group
        self._setup_ui(group, categories, available_tags)

    def _setup_ui(
        self,
        group: Dict,
        categories: List[str],
        available_tags: List[str],
    ) -> None:
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(8, 4, 8, 4)
        layout.setSpacing(8)

        # Enabled checkbox
        self.checkbox = QtWidgets.QCheckBox()
        self.checkbox.setChecked(True)
        self.checkbox.setFixedWidth(20)
        layout.addWidget(self.checkbox)

        # Row index label
        idx_label = QtWidgets.QLabel(f"{self.index + 1:03d}")
        idx_label.setFixedWidth(32)
        idx_label.setStyleSheet("color: #4f5b6e;")
        layout.addWidget(idx_label)

        # Name field
        self.name_edit = QtWidgets.QLineEdit(group.get('name', ''))
        self.name_edit.setPlaceholderText("e.g. rock, pillar, crate...")
        self.name_edit.setMinimumWidth(150)
        layout.addWidget(self.name_edit, 2)

        # Category combo
        self.category_combo = QtWidgets.QComboBox()
        self.category_combo.setEditable(True)
        self.category_combo.addItem('')
        self.category_combo.addItems(categories)
        if group.get('category'):
            self.category_combo.setCurrentText(group['category'])
        self.category_combo.setMinimumWidth(120)
        layout.addWidget(self.category_combo, 1)

        # Tags
        self.tags_widget = TagInputWidget()
        self.tags_widget.setAvailableTags(available_tags)
        if group.get('tags'):
            self.tags_widget.setTags(group['tags'])
        self.tags_widget.setMinimumWidth(150)
        layout.addWidget(self.tags_widget, 2)

        # Prim / island count
        count_label = QtWidgets.QLabel(
            f"{group['prim_count']}p / {group['island_count']}i"
        )
        count_label.setFixedWidth(88)
        count_label.setToolTip(
            f"{group['prim_count']} primitives, {group['island_count']} islands"
        )
        count_label.setStyleSheet("color: #4f5b6e;")
        layout.addWidget(count_label)

        # Status dot — updated during export via set_export_status()
        self.status_dot = QtWidgets.QLabel(" ")
        self.status_dot.setFixedWidth(16)
        self.status_dot.setToolTip("Pending")
        layout.addWidget(self.status_dot)

        # Alternating row background
        bg = "#252525" if self.index % 2 == 0 else "#2a2a2a"
        self.setStyleSheet(f"AssetGroupRow {{ background-color: {bg}; }}")

    # ── Accessors ────────────────────────────────────────────────────────────

    def get_name(self) -> str:
        """Returns the per-row name, or empty string if blank (caller applies dialog-level default)."""
        return self.name_edit.text().strip()

    def get_category(self) -> str:
        return self.category_combo.currentText().strip()

    def get_tags(self) -> List[str]:
        return self.tags_widget.getTags()

    def is_checked(self) -> bool:
        return self.checkbox.isChecked()

    def apply_defaults(self, category: str, tags: List[str]) -> None:
        """Fill in category/tags only if the prim had no attributes for them."""
        if not self.category_combo.currentText().strip() and category:
            self.category_combo.setCurrentText(category)
        if not self.tags_widget.getTags() and tags:
            self.tags_widget.setTags(tags)

    def set_export_status(self, state: str) -> None:
        """Update the status dot to reflect export progress.

        Args:
            state: 'pending' | 'exporting' | 'done' | 'error'
        """
        _dot_styles: Dict[str, tuple] = {
            'pending':   (" ",  "color: #4f5b6e;",  "Pending"),
            'exporting': ("●",  "color: #f1fa8c;",  "Exporting..."),
            'done':      ("●",  "color: #00ff7f;",  "Done"),
            'error':     ("●",  "color: #ff5555;",  "Failed"),
        }
        symbol, style, tip = _dot_styles.get(state, _dot_styles['pending'])
        self.status_dot.setText(symbol)
        self.status_dot.setStyleSheet(style)
        self.status_dot.setToolTip(tip)


