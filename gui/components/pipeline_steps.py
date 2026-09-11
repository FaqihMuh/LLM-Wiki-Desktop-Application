"""
Pipeline timeline widget — vertical list of labelled steps
with done / running / pending visual states.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QColor, QBrush, QPen


_STATE_COLORS = {
    "done":    "#16a34a",
    "running": "#2563eb",
    "pending": "#cbd5e1",
    "failed":  "#dc2626",
}


class PipelineSteps(QWidget):
    """Vertical timeline of pipeline stages."""

    def __init__(self, stages: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self._stages = stages
        self._states: dict[str, str] = {s: "pending" for s in stages}

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 16, 16, 16)
        self._layout.setSpacing(0)

        self._labels: dict[str, QLabel] = {}
        for stage in stages:
            lbl = self._make_step(stage)
            self._labels[stage] = lbl

    # ------------------------------------------------------------------

    def set_state(self, stage: str, state: str) -> None:
        """state: 'done' | 'running' | 'pending' | 'failed'"""
        if stage in self._states:
            self._states[stage] = state
            self._refresh(stage)

    def mark_done_up_to(self, stage: str) -> None:
        found = False
        for s in self._stages:
            if s == stage:
                self._states[s] = "running"
                self._refresh(s)
                found = True
            elif not found:
                self._states[s] = "done"
                self._refresh(s)

    def reset(self) -> None:
        for s in self._stages:
            self._states[s] = "pending"
            self._refresh(s)

    # ------------------------------------------------------------------

    def _make_step(self, stage: str) -> QLabel:
        row = QWidget()
        row.setStyleSheet("background: transparent;")
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 4, 0, 4)
        hl.setSpacing(10)

        bullet = QLabel("○")
        bullet.setFixedWidth(20)
        bullet.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bullet.setObjectName(f"bullet_{stage}")
        bullet.setStyleSheet("color: #cbd5e1; font-size: 14px; background: transparent;")

        lbl = QLabel(stage)
        lbl.setObjectName(f"label_{stage}")
        lbl.setStyleSheet("color: #64748b; font-size: 13px; background: transparent;")

        hl.addWidget(bullet)
        hl.addWidget(lbl)
        hl.addStretch()
        self._layout.addWidget(row)
        return lbl

    def _refresh(self, stage: str) -> None:
        state = self._states[stage]
        color = _STATE_COLORS.get(state, "#64748b")
        bullet_text = {"done": "✓", "running": "●", "pending": "○", "failed": "✗"}.get(state, "○")
        bold = "bold" if state in ("done", "running") else "normal"

        lbl = self._labels.get(stage)
        if not lbl:
            return

        parent_row = lbl.parent()
        if not parent_row:
            return

        # Update bullet
        bullet = parent_row.findChild(QLabel, f"bullet_{stage}")
        if bullet:
            bullet.setText(bullet_text)
            bullet.setStyleSheet(f"color: {color}; font-size: 14px; background: transparent;")

        # Update label
        lbl.setStyleSheet(
            f"color: {color}; font-size: 13px; font-weight: {bold}; background: transparent;"
        )
