"""Application footer status bar."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QWidget


class Footer(QFrame):
    """Thin bottom bar displaying the current system status."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(42)
        self.setStyleSheet("""
            QFrame {
                background: #f1f5f9;
                border-top: 1px solid #dbe4ee;
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(18, 0, 18, 0)

        self._label = QLabel("Ready • Waiting for Operation")
        self._label.setStyleSheet(
            "color: #64748b; font-size: 12px; background: transparent; border: none;"
        )
        layout.addWidget(self._label)

    def set_text(self, text: str) -> None:
        self._label.setText(text)
