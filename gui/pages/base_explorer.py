"""
Base class for Knowledge Explorer pages.

All explorer pages share:
  - Search card at the top
  - Data table card with pagination
  - Viewer card at the bottom
  - Emit selection_changed signal for the Inspector

Subclasses override:
  - _columns()       → list of column names for the table
  - _load_rows()     → list of row dicts
  - _on_row_selected(info) → populate viewer + emit selection_changed
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QScrollArea, QFrame
)
from PySide6.QtCore import Signal

from ..config import WorkspaceConfig
from ..components.card import Card
from ..components.search_bar import SearchBar
from ..components.data_table import DataTable
from ..components.viewer_panel import ViewerPanel


class BaseExplorerPage(QWidget):
    """
    Template for Read-Only Knowledge Explorer pages.

    Subclasses MUST implement:
        _columns() -> list[str]
        _load_rows() -> list[dict]
        _on_row_selected(info: dict) -> None
            (should populate self._viewer and emit self.selection_changed)
    """

    selection_changed = Signal(dict)   # emitted with row data when selection changes

    def __init__(
        self,
        config: WorkspaceConfig,
        search_placeholder: str = "Search...",
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._last_selection: dict | None = None

        # Build scroll container
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #f4f7fb;")

        self._container = QWidget()
        self._container.setStyleSheet("background: #f4f7fb;")
        self._inner = QVBoxLayout(self._container)
        self._inner.setContentsMargins(24, 24, 24, 24)
        self._inner.setSpacing(20)

        # ---- Search card ----
        self._search_card = Card("Search")
        self._search_bar = SearchBar(search_placeholder)
        self._search_card.add_widget(self._search_bar)
        self._inner.addWidget(self._search_card)

        # ---- Table card ----
        self._table_card = Card("Results")
        self._table = DataTable(self._columns())
        self._table_card.add_widget(self._table)
        self._inner.addWidget(self._table_card)

        # ---- Viewer card ----
        self._viewer_card = Card("Viewer")
        self._viewer = ViewerPanel()
        self._viewer_card.add_widget(self._viewer)
        self._inner.addWidget(self._viewer_card)

        # Extra widgets (e.g. graph) added by subclasses via _add_extra_card()
        self._inner.addStretch()

        scroll.setWidget(self._container)
        outer.addWidget(scroll)

        # Connections
        self._search_bar.search_changed.connect(self._table.filter)
        self._table.row_selected.connect(self._handle_row_selected)

        # Load initial data
        self.reload()

    # ------------------------------------------------------------------
    # Subclass API
    # ------------------------------------------------------------------

    def _columns(self) -> list[str]:
        raise NotImplementedError

    def _load_rows(self) -> list[dict]:
        raise NotImplementedError

    def _on_row_selected(self, info: dict) -> None:
        raise NotImplementedError

    def _add_extra_card(self, card: Card) -> None:
        """Insert an additional card before the stretch item."""
        self._inner.insertWidget(self._inner.count() - 1, card)

    # ------------------------------------------------------------------
    # Selection tracking (for the Inspector)
    # ------------------------------------------------------------------

    def _handle_row_selected(self, info: dict) -> None:
        self._last_selection = info
        self._on_row_selected(info)

    def reassert_selection(self) -> None:
        """
        Re-emit the current selection (or an empty placeholder) so the
        Inspector's Selected-Object panel reflects this page immediately
        on navigation, without requiring a fresh row click.
        """
        self._on_row_selected(self._last_selection or {})

    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Reload data from disk."""
        try:
            rows = self._load_rows()
        except Exception:
            rows = []
        self._table.set_data(rows)
        if rows:
            self._table.select_row(0)
