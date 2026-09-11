"""Reusable search input widget."""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLineEdit
from PySide6.QtCore import Signal


class SearchBar(QWidget):
    """Single-line text input that emits search_changed on every keystroke."""

    search_changed = Signal(str)

    def __init__(self, placeholder: str = "Search...", parent: QWidget | None = None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 16)

        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder)
        self._input.setStyleSheet("""
            QLineEdit {
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 10px 14px;
                font-size: 13px;
                background: white;
                color: #1e293b;
            }
            QLineEdit:focus {
                border-color: #2563eb;
            }
        """)
        self._input.textChanged.connect(self.search_changed.emit)
        layout.addWidget(self._input)

    def text(self) -> str:
        return self._input.text()

    def clear(self) -> None:
        self._input.clear()
