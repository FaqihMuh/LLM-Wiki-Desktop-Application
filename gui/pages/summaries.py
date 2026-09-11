"""Summaries explorer page."""

from PySide6.QtCore import Signal

from .base_explorer import BaseExplorerPage
from ..config import WorkspaceConfig
from ..data.wiki_loader import load_summaries


class SummariesPage(BaseExplorerPage):
    """Displays wiki/summaries/ pages in a searchable table with a viewer."""

    selection_changed = Signal(dict)

    def __init__(self, config: WorkspaceConfig, parent=None):
        super().__init__(
            config,
            search_placeholder="Search by title, topic, or filename...",
            parent=parent,
        )
        self._search_card.set_title("Search Summary")
        self._table_card.set_title("Summary Pages")
        self._viewer_card.set_title("Summary Viewer")

    def _columns(self) -> list[str]:
        return ["title", "topic", "source", "entities", "updated"]

    def _load_rows(self) -> list[dict]:
        return load_summaries(self._config.root)

    def _on_row_selected(self, info: dict) -> None:
        self._viewer.show_summary(info)
        self.selection_changed.emit(info)
