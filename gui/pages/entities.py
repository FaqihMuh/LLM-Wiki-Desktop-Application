"""Entities explorer page — table, viewer, and interactive Knowledge Graph."""

from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QHBoxLayout, QLabel, QPushButton

from .base_explorer import BaseExplorerPage
from ..config import WorkspaceConfig
from ..components.card import Card
from ..components.knowledge_graph import EntityGraphWidget
from ..components.recommended_papers import RecommendedPapersWidget
from ..data.wiki_loader import load_entities


class EntitiesPage(BaseExplorerPage):
    """
    Displays wiki/entities/ pages with:
      - Searchable metadata table
      - Entity viewer (markdown body)
      - Interactive Knowledge Graph (draggable nodes, bidirectional selection)

    Bidirectional sync:
      table row selected  → graph node highlighted + viewer + inspector updated
      graph node selected → table row highlighted + viewer + inspector updated
    """

    selection_changed = Signal(dict)

    def __init__(self, config: WorkspaceConfig, parent=None):
        self._syncing = False   # prevents circular table ↔ graph updates

        super().__init__(
            config,
            search_placeholder="Search by entity name, type, or status...",
            parent=parent,
        )
        self._search_card.set_title("Search Entity")
        self._table_card.set_title("Entities")
        self._viewer_card.set_title("Entity Viewer")

        # Knowledge Graph card
        graph_card = Card("Knowledge Graph")

        graph_toolbar = QWidget()
        graph_toolbar.setStyleSheet("background: transparent;")
        toolbar_layout = QHBoxLayout(graph_toolbar)
        toolbar_layout.setContentsMargins(16, 10, 16, 0)
        toolbar_layout.setSpacing(10)

        hint = QLabel(
            "Node size reflects Entity Representation (Degree Centrality) · "
            "Scroll to zoom · Drag empty space to pan"
        )
        hint.setStyleSheet("color: #94a3b8; font-size: 11px; background: transparent;")
        toolbar_layout.addWidget(hint)
        toolbar_layout.addStretch()

        reset_view_btn = QPushButton("Reset View")
        reset_view_btn.setStyleSheet(
            "QPushButton { background: #e2e8f0; border: none; border-radius: 8px;"
            " padding: 6px 12px; font-size: 12px; color: #1e293b; }"
            " QPushButton:hover { background: #cbd5e1; }"
        )
        reset_view_btn.clicked.connect(self._reset_graph_view)
        toolbar_layout.addWidget(reset_view_btn)

        graph_card.add_widget(graph_toolbar)

        self._graph_widget = EntityGraphWidget()
        graph_card.add_widget(self._graph_widget)
        self._add_extra_card(graph_card)

        # Connect graph → page
        self._graph_widget.node_selected.connect(self._on_graph_node_selected)

        # Recommended Papers card — client-side, read-only visualization aid
        # (same category as the Knowledge Graph). Never goes through the
        # Operating System, never writes to the Workspace / Persistent Memory.
        papers_card = Card("Recommended Papers")
        self._papers_widget = RecommendedPapersWidget(self._config)
        papers_card.add_widget(self._papers_widget)
        self._add_extra_card(papers_card)

        # Populate graph with entities that were already loaded by super().__init__
        self._refresh_graph()

    # ------------------------------------------------------------------
    # BaseExplorerPage interface
    # ------------------------------------------------------------------

    def _columns(self) -> list[str]:
        return ["name", "type", "status", "confidence", "last_updated"]

    def _load_rows(self) -> list[dict]:
        return load_entities(self._config.root)

    def _on_row_selected(self, info: dict) -> None:
        """Table row selected — update viewer, inspector, graph node, and recommendations."""
        self._viewer.show_entity(info)
        self.selection_changed.emit(info)

        # Guard: _graph_widget is assigned after super().__init__ returns
        if self._syncing or not hasattr(self, "_graph_widget"):
            return

        if hasattr(self, "_papers_widget"):
            self._papers_widget.set_entity(
                info, self._graph_widget._entities, self._graph_widget._degrees
            )

        self._syncing = True
        try:
            for i, e in enumerate(self._graph_widget._entities):
                if e.get("name") == info.get("name"):
                    self._graph_widget.select_node_silent(i)
                    break
        finally:
            self._syncing = False

    # ------------------------------------------------------------------
    # Graph → table / viewer / inspector sync
    # ------------------------------------------------------------------

    def _on_graph_node_selected(self, idx: int) -> None:
        """Graph node selected → update viewer, inspector, and table row."""
        entities = self._graph_widget._entities
        if not (0 <= idx < len(entities)):
            return
        info = entities[idx]

        if self._syncing:
            return
        self._syncing = True
        try:
            self._viewer.show_entity(info)
            self.selection_changed.emit(info)
            if hasattr(self, "_papers_widget"):
                self._papers_widget.set_entity(
                    info, self._graph_widget._entities, self._graph_widget._degrees
                )
            # Select the matching row in the table (silently — no signal)
            self._table.select_row_by_value("name", info.get("name", ""))
        finally:
            self._syncing = False

    # ------------------------------------------------------------------
    # Canvas view
    # ------------------------------------------------------------------

    def _reset_graph_view(self) -> None:
        """Reset the Knowledge Graph's zoom/pan (node positions are unaffected)."""
        self._graph_widget.reset_view()

    # ------------------------------------------------------------------
    # Reload
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Reload entity data, refresh table, and update the Knowledge Graph."""
        super().reload()
        if hasattr(self, "_graph_widget"):
            self._refresh_graph()
            self._sync_graph_from_table()

    def _refresh_graph(self) -> None:
        """Populate the graph from the entity rows already loaded into the
        table (by _load_rows()/reload()), instead of re-reading every
        wiki/entities/*.md file from disk a second time. self._table.get_data()
        always holds the full, unfiltered dataset regardless of search text
        or pagination.
        """
        self._graph_widget.set_entities(self._table.get_data())

    def _sync_graph_from_table(self) -> None:
        """Highlight the graph node that matches the currently selected table row."""
        selected_items = self._table._table.selectedItems()
        if not selected_items:
            return
        row_data = selected_items[0].data(Qt.ItemDataRole.UserRole)
        if not row_data:
            return
        name = row_data.get("name", "")
        for i, e in enumerate(self._graph_widget._entities):
            if e.get("name") == name:
                self._graph_widget.select_node_silent(i)
                return
