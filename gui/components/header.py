"""Application header bar."""

from PySide6.QtWidgets import QFrame, QHBoxLayout, QVBoxLayout, QLabel, QWidget


class Header(QFrame):
    """Fixed-height header with logo, subtitle, and a status badge."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedHeight(72)
        self.setStyleSheet("""
            QFrame {
                background-color: #1f2937;
                border-bottom: 1px solid rgba(255,255,255,0.08);
            }
        """)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(28, 0, 28, 0)

        # Left column: logo + subtitle
        left = QVBoxLayout()
        left.setSpacing(3)

        self._logo = QLabel("LLM Wiki ISTN")
        self._logo.setStyleSheet(
            "color: white; font-size: 18px; font-weight: bold; border: none; background: transparent;"
        )

        self._subtitle = QLabel("Persistent Memory Research Assistant")
        self._subtitle.setStyleSheet(
            "color: rgba(255,255,255,0.75); font-size: 11px; border: none; background: transparent;"
        )

        left.addWidget(self._logo)
        left.addWidget(self._subtitle)
        layout.addLayout(left)
        layout.addStretch()

        # Right: status badge
        self._status = QLabel("Session Ready")
        self._status.setStyleSheet("""
            QLabel {
                background: #2563eb;
                color: white;
                padding: 6px 16px;
                border-radius: 999px;
                font-size: 12px;
                font-weight: bold;
                border: none;
            }
        """)
        layout.addWidget(self._status)

    def set_status(self, text: str) -> None:
        self._status.setText(text)
