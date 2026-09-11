"""Reusable Card widget — white rounded frame with an optional title bar."""

from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt


class Card(QFrame):
    """White rounded card with an optional title bar and a content area."""

    def __init__(self, title: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("Card")
        self.setStyleSheet("""
            QFrame#Card {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
        """)

        self._outer = QVBoxLayout(self)
        self._outer.setContentsMargins(0, 0, 0, 0)
        self._outer.setSpacing(0)

        # Optional title bar
        self._title_label: QLabel | None = None
        if title:
            self._title_label = QLabel(title)
            self._title_label.setStyleSheet("""
                QLabel {
                    background: #f8fafc;
                    border-top-left-radius: 12px;
                    border-top-right-radius: 12px;
                    border-bottom: 1px solid #e5e7eb;
                    padding: 12px 16px;
                    font-size: 14px;
                    font-weight: bold;
                    color: #1e293b;
                }
            """)
            self._outer.addWidget(self._title_label)

        # Content container
        self._content_widget = QWidget()
        self._content_widget.setObjectName("CardContent")
        self._content_layout = QVBoxLayout(self._content_widget)
        self._content_layout.setContentsMargins(0, 0, 0, 0)
        self._content_layout.setSpacing(0)
        self._outer.addWidget(self._content_widget)

    # ------------------------------------------------------------------

    def set_title(self, text: str) -> None:
        if self._title_label is not None:
            self._title_label.setText(text)

    def content_layout(self) -> QVBoxLayout:
        return self._content_layout

    def add_widget(self, widget: QWidget) -> None:
        self._content_layout.addWidget(widget)

    def add_stretch(self) -> None:
        self._content_layout.addStretch()

    def set_content_widget(self, widget: QWidget) -> None:
        """Replace all content with a single widget."""
        while self._content_layout.count():
            item = self._content_layout.takeAt(0)
            w = item.widget()
            if w:
                w.setParent(None)  # type: ignore[arg-type]
        self._content_layout.addWidget(widget)
