"""Knowledge Index (Source Registry) explorer page."""

from PySide6.QtCore import Signal

from .base_explorer import BaseExplorerPage
from ..config import WorkspaceConfig
from ..data.wiki_loader import load_index


class KnowledgeIndexPage(BaseExplorerPage):
    """Displays the Source Registry from wiki/index.md."""

    selection_changed = Signal(dict)

    def __init__(self, config: WorkspaceConfig, parent=None):
        super().__init__(
            config,
            search_placeholder="Search by title, arXiv ID, filename, or summary...",
            parent=parent,
        )
        self._search_card.set_title("Search Source Registry")
        self._table_card.set_title("Source Registry")
        self._viewer_card.set_title("Index Viewer")

    def _columns(self) -> list[str]:
        return ["title", "arxiv", "entities", "ingest_date"]

    def _load_rows(self) -> list[dict]:
        return load_index(self._config.root)

    def _on_row_selected(self, info: dict) -> None:
        self._viewer.show_index_entry(info)
        self.selection_changed.emit(info)
