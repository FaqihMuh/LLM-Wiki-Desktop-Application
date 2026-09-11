"""Operation Log explorer page."""

from PySide6.QtCore import Signal

from .base_explorer import BaseExplorerPage
from ..config import WorkspaceConfig
from ..data.wiki_loader import load_log_entries


class OperationLogPage(BaseExplorerPage):
    """Displays the chronological operation history from wiki/log.md."""

    selection_changed = Signal(dict)

    def __init__(self, config: WorkspaceConfig, parent=None):
        super().__init__(
            config,
            search_placeholder="Search by document, operation, result, or date...",
            parent=parent,
        )
        self._search_card.set_title("Search Operation Log")
        self._table_card.set_title("Operation History")
        self._viewer_card.set_title("Log Viewer")

    def _columns(self) -> list[str]:
        return ["timestamp", "document", "result"]

    def _load_rows(self) -> list[dict]:
        return load_log_entries(self._config.root)

    def _on_row_selected(self, info: dict) -> None:
        self._viewer.show_log_entry(info)
        self.selection_changed.emit(info)
