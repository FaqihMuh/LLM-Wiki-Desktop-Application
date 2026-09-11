"""Raw Documents explorer page."""

from PySide6.QtCore import Signal

from .base_explorer import BaseExplorerPage
from ..config import WorkspaceConfig
from ..data.wiki_loader import load_raw_documents


class RawDocumentsPage(BaseExplorerPage):
    """Displays all PDF files in raw/ with file metadata."""

    selection_changed = Signal(dict)

    def __init__(self, config: WorkspaceConfig, parent=None):
        super().__init__(
            config,
            search_placeholder="Search by filename, status, or date...",
            parent=parent,
        )
        self._search_card.set_title("Search Document")
        self._table_card.set_title("Raw Documents")
        self._viewer_card.set_title("Document Viewer")

    def _columns(self) -> list[str]:
        return ["filename", "status", "modified"]

    def _load_rows(self) -> list[dict]:
        return load_raw_documents(self._config.root)

    def _on_row_selected(self, info: dict) -> None:
        self._viewer.show_document(info)
        self.selection_changed.emit(info)
