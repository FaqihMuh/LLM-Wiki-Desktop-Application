"""Colored inline badge label for status values."""

from PySide6.QtWidgets import QLabel, QWidget

_PALETTE = {
    "SUCCESS":     ("#ecfdf5", "#15803d"),
    "HEALTHY":     ("#ecfdf5", "#15803d"),
    "PASSED":      ("#ecfdf5", "#15803d"),
    "Available":   ("#ecfdf5", "#15803d"),
    "Established": ("#eff6ff", "#2563eb"),
    "Emerging":    ("#fffbeb", "#ca8a04"),
    "Experimental":("#fff7ed", "#c2410c"),
    "WARNING":     ("#fefce8", "#a16207"),
    "Deprecated":  ("#fef2f2", "#dc2626"),
    "FAILED":      ("#fef2f2", "#dc2626"),
    "CRITICAL":    ("#fef2f2", "#dc2626"),
    "ABORTED":     ("#fef2f2", "#dc2626"),
    "Running":     ("#eff6ff", "#2563eb"),
    "Completed":   ("#ecfdf5", "#15803d"),
    "Idle":        ("#f8fafc", "#64748b"),
    "Ready":       ("#ecfdf5", "#15803d"),
    "Indexed":     ("#eff6ff", "#2563eb"),
    "High":        ("#ecfdf5", "#15803d"),
    "Medium":      ("#fffbeb", "#ca8a04"),
    "Low":         ("#fef2f2", "#dc2626"),
}


class StatusBadge(QLabel):
    """Pill-shaped label coloured according to the status string."""

    def __init__(self, status: str = "", parent: QWidget | None = None):
        super().__init__(parent)
        self.set_status(status)

    def set_status(self, status: str) -> None:
        bg, fg = _PALETTE.get(status, ("#f1f5f9", "#475569"))
        self.setText(status or "—")
        self.setStyleSheet(
            f"background: {bg}; color: {fg};"
            " border-radius: 999px;"
            " padding: 2px 10px;"
            " font-size: 11px;"
            " font-weight: bold;"
            " border: none;"
        )
