"""Left sidebar with navigation buttons for all pages."""

from PySide6.QtWidgets import (
    QFrame, QVBoxLayout, QLabel, QPushButton, QWidget, QButtonGroup
)
from PySide6.QtCore import Signal, Qt

# (page_id, display_label)
HOME_ITEM = ("home", "🏠 Home")

NAV_ITEMS = [
    ("raw_documents",  "📄 Raw Documents"),
    ("summaries",      "📑 Summaries"),
    ("entities",       "🧠 Entities"),
    ("knowledge_index","📚 Index"),
    ("operation_log",  "📜 Operation Log"),
]

OP_ITEMS = [
    ("query",       "🔍 Query"),
    ("ingest",      "📥 Ingest"),
    ("maintenance", "🩺 Maintenance"),
]

_BTN_STYLE = """
QPushButton {
    border: none;
    border-radius: 10px;
    padding: 10px 12px;
    font-size: 13px;
    background: transparent;
    color: #1e293b;
    text-align: left;
}
QPushButton:hover {
    background: #e2e8f0;
}
QPushButton:checked {
    background: #2563eb;
    color: white;
    font-weight: bold;
}
"""

_SECTION_LABEL_STYLE = """
    color: #64748b;
    font-size: 10px;
    font-weight: bold;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 0 12px 8px;
    background: transparent;
    border: none;
"""


class Sidebar(QFrame):
    """Left navigation panel.  Emits page_requested(page_id) on click."""

    page_requested = Signal(str)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(250)
        self.setStyleSheet("""
            QFrame {
                background: #f8fafc;
                border-right: 1px solid #dbe4ee;
            }
        """)

        self._buttons: dict[str, QPushButton] = {}
        self._btn_group = QButtonGroup(self)
        self._btn_group.setExclusive(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 20, 16, 20)
        layout.setSpacing(2)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        # ---- Home ----
        pid, label = HOME_ITEM
        layout.addWidget(self._make_button(pid, label))
        layout.addSpacing(4)

        # ---- Knowledge Explorer section ----
        nav_lbl = QLabel("Knowledge Explorer")
        nav_lbl.setStyleSheet(_SECTION_LABEL_STYLE)
        layout.addWidget(nav_lbl)

        for page_id, label in NAV_ITEMS:
            btn = self._make_button(page_id, label)
            layout.addWidget(btn)

        # Divider
        divider = QFrame()
        divider.setFixedHeight(1)
        divider.setStyleSheet("background: #dbe4ee; margin: 10px 0;")
        layout.addWidget(divider)

        # ---- Operations section ----
        op_lbl = QLabel("Operations")
        op_lbl.setStyleSheet(_SECTION_LABEL_STYLE)
        layout.addWidget(op_lbl)

        for page_id, label in OP_ITEMS:
            btn = self._make_button(page_id, label)
            layout.addWidget(btn)

        layout.addStretch()

    # ------------------------------------------------------------------

    def _make_button(self, page_id: str, label: str) -> QPushButton:
        btn = QPushButton(label)
        btn.setCheckable(True)
        btn.setStyleSheet(_BTN_STYLE)
        btn.clicked.connect(lambda _checked=False, pid=page_id: self.page_requested.emit(pid))
        self._btn_group.addButton(btn)
        self._buttons[page_id] = btn
        return btn

    def set_active(self, page_id: str) -> None:
        btn = self._buttons.get(page_id)
        if btn:
            btn.setChecked(True)
