"""
Home page — application entry screen.

Displays system status, wiki statistics, and quick navigation cards.
Does not invoke any workflow automatically (per gui.md).
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QScrollArea, QFrame, QPushButton
)
from PySide6.QtCore import Signal, Qt

from ..config import WorkspaceConfig
from ..components.card import Card
from ..data.wiki_loader import load_wiki_stats


class _StatCard(QFrame):
    def __init__(self, value: str, label: str, color: str = "#2563eb", parent=None):
        super().__init__(parent)
        self.setStyleSheet(f"""
            QFrame {{
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
                border-left: 4px solid {color};
            }}
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)

        val_lbl = QLabel(value)
        val_lbl.setStyleSheet(
            f"font-size: 28px; font-weight: bold; color: {color};"
            " background: transparent; border: none;"
        )
        lbl = QLabel(label)
        lbl.setStyleSheet(
            "font-size: 12px; color: #64748b; background: transparent; border: none;"
        )
        layout.addWidget(val_lbl)
        layout.addWidget(lbl)


class _QuickCard(QFrame):
    clicked = Signal(str)

    def __init__(self, icon: str, title: str, desc: str, page_id: str, parent=None):
        super().__init__(parent)
        self._page_id = page_id
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
            QFrame:hover {
                border-color: #2563eb;
                background: #eff6ff;
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)
        layout.setSpacing(6)

        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet(
            "font-size: 24px; background: transparent; border: none;"
        )
        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1e293b;"
            " background: transparent; border: none;"
        )
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet(
            "font-size: 12px; color: #64748b; background: transparent; border: none;"
        )
        desc_lbl.setWordWrap(True)

        layout.addWidget(icon_lbl)
        layout.addWidget(title_lbl)
        layout.addWidget(desc_lbl)

    def mousePressEvent(self, event):
        self.clicked.emit(self._page_id)
        super().mousePressEvent(event)


class HomePage(QWidget):
    """Landing page shown when the application starts."""

    navigate = Signal(str)  # emitted when user clicks a quick-nav card

    def __init__(self, config: WorkspaceConfig, parent: QWidget | None = None):
        super().__init__(parent)
        self._config = config
        self._build_ui()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #f4f7fb;")

        container = QWidget()
        container.setStyleSheet("background: #f4f7fb;")
        layout = QVBoxLayout(container)
        layout.setContentsMargins(28, 28, 28, 28)
        layout.setSpacing(22)

        # ---- Welcome header ----
        welcome = QLabel("Welcome to LLM Wiki")
        welcome.setStyleSheet(
            "font-size: 22px; font-weight: bold; color: #1e293b;"
            " background: transparent;"
        )
        sub = QLabel(
            "Persistent Knowledge Management System  •  "
            "AI Literature Review Assistant"
        )
        sub.setStyleSheet("font-size: 13px; color: #64748b; background: transparent;")

        layout.addWidget(welcome)
        layout.addWidget(sub)

        # ---- Stats row ----
        stats = self._load_stats()
        stats_layout = QHBoxLayout()
        stats_layout.setSpacing(16)
        stats_layout.addWidget(
            _StatCard(str(stats["raw_documents"]), "Raw Documents", "#2563eb")
        )
        stats_layout.addWidget(
            _StatCard(str(stats["summaries"]), "Summaries", "#16a34a")
        )
        stats_layout.addWidget(
            _StatCard(str(stats["entities"]), "Entity Pages", "#ca8a04")
        )
        stats_layout.addWidget(
            _StatCard(str(stats["indexed"]), "Indexed Sources", "#7c3aed")
        )
        layout.addLayout(stats_layout)

        # ---- Knowledge Explorer section ----
        section_lbl = QLabel("Knowledge Explorer")
        section_lbl.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #64748b;"
            " text-transform: uppercase; letter-spacing: 1px; background: transparent;"
        )
        layout.addWidget(section_lbl)

        explorer_grid = QGridLayout()
        explorer_grid.setSpacing(16)
        explorer_items = [
            ("📄", "Raw Documents",   "Browse source PDF files",          "raw_documents"),
            ("📑", "Summaries",       "View generated summary pages",     "summaries"),
            ("🧠", "Entities",        "Explore the knowledge graph",      "entities"),
            ("📚", "Knowledge Index", "Source registry and index",        "knowledge_index"),
            ("📜", "Operation Log",   "History of all operations",        "operation_log"),
        ]
        for i, (icon, title, desc, pid) in enumerate(explorer_items):
            card = _QuickCard(icon, title, desc, pid)
            card.clicked.connect(self.navigate.emit)
            explorer_grid.addWidget(card, i // 3, i % 3)
        layout.addLayout(explorer_grid)

        # ---- Operations section ----
        ops_lbl = QLabel("Operations")
        ops_lbl.setStyleSheet(
            "font-size: 11px; font-weight: bold; color: #64748b;"
            " text-transform: uppercase; letter-spacing: 1px; background: transparent;"
        )
        layout.addWidget(ops_lbl)

        ops_layout = QHBoxLayout()
        ops_layout.setSpacing(16)
        ops_items = [
            ("🔍", "Query",       "Ask questions about the wiki",          "query",       "#2563eb"),
            ("📥", "Ingest",      "Add new research documents",           "ingest",      "#16a34a"),
            ("🩺", "Maintenance", "Validate and audit Persistent Memory", "maintenance", "#ca8a04"),
        ]
        for icon, title, desc, pid, color in ops_items:
            card = _QuickCard(icon, title, desc, pid)
            card.clicked.connect(self.navigate.emit)
            ops_layout.addWidget(card)
        layout.addLayout(ops_layout)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    def _load_stats(self) -> dict:
        try:
            return load_wiki_stats(self._config.root)
        except Exception:
            return {"raw_documents": 0, "summaries": 0, "entities": 0, "indexed": 0}

    def reload(self) -> None:
        """Reload stats and rebuild the UI (called by main_window on wiki changes)."""
        layout = self.layout()
        if layout:
            # Transfer layout ownership to a throwaway widget so it gets cleaned up
            QWidget().setLayout(layout)
        self._build_ui()

    def refresh(self) -> None:
        """Alias kept for compatibility."""
        self.reload()
