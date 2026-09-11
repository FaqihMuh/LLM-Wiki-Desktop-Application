"""
Main application window.

Assembles the 3-column layout:
    Sidebar  |  QStackedWidget (Workspace)  |  Inspector

Manages page switching, inspector updates, header status, and footer text.
"""

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget
)
from PySide6.QtCore import Qt

from .workspace_manager import WorkspaceManager
from .components.header import Header
from .components.footer import Footer
from .components.sidebar import Sidebar
from .components.inspector import Inspector
from .state.working_memory import WorkingMemory
from .state.maintenance_state import load_maintenance_state, save_maintenance_state
from .pages.home import HomePage
from .pages.raw_documents import RawDocumentsPage
from .pages.summaries import SummariesPage
from .pages.entities import EntitiesPage
from .pages.knowledge_index import KnowledgeIndexPage
from .pages.operation_log import OperationLogPage
from .pages.query import QueryPage
from .pages.ingest import IngestPage
from .pages.maintenance import MaintenancePage


# Header status labels per page
_HEADER_STATUS = {
    "home":            "Session Ready",
    "raw_documents":   "Raw Documents",
    "summaries":       "Summaries",
    "entities":        "Entity Explorer",
    "knowledge_index": "Knowledge Index",
    "operation_log":   "Operation Log",
    "query":           "Query Mode",
    "ingest":          "Ingest Mode",
    "maintenance":     "Maintenance Mode",
}

# Footer defaults per page
_FOOTER_TEXT = {
    "home":            "Ready • Waiting for Operation",
    "raw_documents":   "Raw Documents • Read Only",
    "summaries":       "Summary Explorer • Read Only",
    "entities":        "Entity Explorer • Read Only",
    "knowledge_index": "Knowledge Index • Read Only",
    "operation_log":   "Operation Log • Read Only",
    "query":           "Query • Waiting for Question",
    "ingest":          "Ingest • Waiting for Document",
    "maintenance":     "Maintenance • Ready",
}


class MainWindow(QMainWindow):
    def __init__(self, workspace_manager: WorkspaceManager):
        super().__init__()
        self._workspace_manager = workspace_manager
        self._config = workspace_manager.current_workspace()
        self._working_memory = WorkingMemory()
        self._maintenance_state: dict = load_maintenance_state()
        self._current_page = "home"

        self.setWindowTitle("LLM Wiki ISTN")
        self.setMinimumSize(1280, 800)
        self.resize(1440, 900)

        self._build_ui()
        self._navigate("home")

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        central.setStyleSheet("background: #eef2f7;")

        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # Header
        self._header = Header()
        root.addWidget(self._header)

        # Middle: Sidebar + Workspace + Inspector
        middle = QWidget()
        mid_layout = QHBoxLayout(middle)
        mid_layout.setContentsMargins(0, 0, 0, 0)
        mid_layout.setSpacing(0)

        # Sidebar
        self._sidebar = Sidebar()
        self._sidebar.page_requested.connect(self._navigate)
        mid_layout.addWidget(self._sidebar)

        # Stacked workspace
        self._stack = QStackedWidget()
        self._stack.setStyleSheet("background: #f4f7fb;")
        mid_layout.addWidget(self._stack, stretch=1)

        # Inspector
        self._inspector = Inspector()
        mid_layout.addWidget(self._inspector)

        root.addWidget(middle, stretch=1)

        # Footer
        self._footer = Footer()
        root.addWidget(self._footer)

        # Build all pages
        self._pages: dict[str, QWidget] = {}
        self._build_pages()

    def _build_pages(self) -> None:
        config = self._config
        wm = self._working_memory

        # Home
        home = HomePage(config)
        home.navigate.connect(self._navigate)
        self._add_page("home", home)

        # Knowledge Explorer
        raw = RawDocumentsPage(config)
        raw.selection_changed.connect(self._inspector.show_selected_document)
        self._add_page("raw_documents", raw)

        summ = SummariesPage(config)
        summ.selection_changed.connect(self._inspector.show_selected_summary)
        self._add_page("summaries", summ)

        ent = EntitiesPage(config)
        ent.selection_changed.connect(self._inspector.show_selected_entity)
        self._add_page("entities", ent)

        ki = KnowledgeIndexPage(config)
        ki.selection_changed.connect(self._inspector.show_selected_index_entry)
        self._add_page("knowledge_index", ki)

        log = OperationLogPage(config)
        log.selection_changed.connect(self._inspector.show_selected_log)
        self._add_page("operation_log", log)

        # Operation pages
        query = QueryPage(config, wm)
        query.inspector_update.connect(self._on_inspector_update)
        query.footer_update.connect(self._footer.set_text)
        self._add_page("query", query)

        ingest = IngestPage(config)
        ingest.inspector_update.connect(self._on_inspector_update)
        ingest.footer_update.connect(self._footer.set_text)
        ingest.wiki_changed.connect(self._on_wiki_changed)
        self._add_page("ingest", ingest)

        maint = MaintenancePage(config)
        maint.inspector_update.connect(self._on_inspector_update)
        maint.footer_update.connect(self._footer.set_text)
        self._add_page("maintenance", maint)

    def _add_page(self, page_id: str, widget: QWidget) -> None:
        self._pages[page_id] = widget
        self._stack.addWidget(widget)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _navigate(self, page_id: str) -> None:
        if page_id not in self._pages:
            return

        self._current_page = page_id
        self._stack.setCurrentWidget(self._pages[page_id])
        self._sidebar.set_active(page_id)
        self._header.set_status(_HEADER_STATUS.get(page_id, page_id))
        self._footer.set_text(_FOOTER_TEXT.get(page_id, ""))

        # Reset inspector for non-operation pages
        if page_id == "home":
            self._inspector.show_home_welcome()

        elif page_id in ("raw_documents", "summaries",
                         "entities", "knowledge_index", "operation_log"):
            self._pages[page_id].reassert_selection()

        elif page_id == "query":
            self._inspector.show_query_idle()

        elif page_id == "ingest":
            self._inspector.show_ingest_idle()

        elif page_id == "maintenance":
            if self._maintenance_state:
                self._inspector.show_maintenance_result(self._maintenance_state)
            else:
                self._inspector.show_maintenance_idle()

    # ------------------------------------------------------------------
    # Inspector updates from operation pages
    # ------------------------------------------------------------------

    def _on_inspector_update(self, event: str, payload: dict) -> None:
        if event == "query_idle":
            self._inspector.show_query_idle()
        elif event == "query_running":
            self._inspector.show_query_running(payload.get("elapsed", "—"))
        elif event == "query_result":
            self._inspector.show_query_result(payload)
        elif event == "ingest_idle":
            self._inspector.show_ingest_idle()
        elif event == "ingest_tick":
            self._inspector.show_ingest_elapsed(payload.get("elapsed", "—"))
        elif event == "ingest_running":
            self._inspector.show_ingest_running(payload)
        elif event == "ingest_result":
            self._inspector.show_ingest_result(payload)
        elif event == "maintenance_started":
            self._inspector.show_maintenance_running(
                self._maintenance_state.get("last_scan", "—"),
                self._maintenance_state.get("duration",  "—"),
            )
        elif event == "maintenance_finished":
            self._inspector.show_maintenance_result(payload)
            self._maintenance_state = {
                "overall_status": payload.get("overall_status", "CRITICAL"),
                "last_scan":      payload.get("last_scan", "—"),
                "duration":       payload.get("duration",  "—"),
            }
            save_maintenance_state(self._maintenance_state)
        elif event == "maintenance_failed":
            if self._maintenance_state:
                self._inspector.show_maintenance_result(self._maintenance_state)
            else:
                self._inspector.show_maintenance_idle()

    # ------------------------------------------------------------------
    # Wiki changed — refresh explorer pages
    # ------------------------------------------------------------------

    def _on_wiki_changed(self) -> None:
        for page_id in ("home", "raw_documents", "summaries", "entities",
                        "knowledge_index", "operation_log"):
            page = self._pages.get(page_id)
            if page and hasattr(page, "reload"):
                page.reload()
