"""
Maintenance operation page.

Allows the user to select a scope and run the Maintenance pipeline.
Displays Wiki Health, Validation Summary, Detected Issues, and Recommendations.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QPushButton, QComboBox
)
from PySide6.QtCore import Signal, Qt

from ..config import WorkspaceConfig
from ..components.card import Card
from ..runtime.worker import MaintenanceWorker


_HEALTH_COLORS = {
    "HEALTHY":  ("#ecfdf5", "#15803d"),
    "WARNING":  ("#fefce8", "#a16207"),
    "CRITICAL": ("#fef2f2", "#dc2626"),
}


class MaintenancePage(QWidget):
    """Maintenance operation workspace."""

    inspector_update = Signal(str, dict)
    footer_update    = Signal(str)

    def __init__(
        self,
        config: WorkspaceConfig,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._worker: MaintenanceWorker | None = None
        self._result: dict | None = None

        self._build_ui()
        self._set_idle_state()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #f4f7fb;")

        self._container = QWidget()
        self._container.setStyleSheet("background: #f4f7fb;")
        self._layout = QVBoxLayout(self._container)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(20)

        # ---- Scope selector card ----
        scope_card = Card("Maintenance Scope")
        scope_inner = QWidget()
        scope_l = QHBoxLayout(scope_inner)
        scope_l.setContentsMargins(18, 16, 18, 16)
        scope_l.setSpacing(16)

        scope_label = QLabel("Scope:")
        scope_label.setStyleSheet("color: #1e293b; font-size: 13px; background: transparent;")

        self._scope_combo = QComboBox()
        self._scope_combo.addItems([
            "Entire Wiki",
            "Entity Pages",
            "Summary Pages",
        ])
        self._scope_combo.setStyleSheet("""
            QComboBox {
                border: 1px solid #d1d5db;
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 13px;
                background: white;
                color: #1e293b;
            }
            QComboBox:focus { border-color: #2563eb; }
        """)

        self._run_btn = QPushButton("Run Maintenance")
        self._run_btn.setStyleSheet("""
            QPushButton { background: #2563eb; color: white; border: none;
                          border-radius: 10px; padding: 10px 18px;
                          font-size: 13px; font-weight: bold; }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #93c5fd; }
        """)
        self._run_btn.clicked.connect(self._run_maintenance)

        self._abort_btn = QPushButton("Abort")
        self._abort_btn.setVisible(False)
        self._abort_btn.setStyleSheet("""
            QPushButton { background: #fee2e2; color: #dc2626; border: none;
                          border-radius: 10px; padding: 10px 16px; font-size: 13px; }
            QPushButton:hover { background: #fecaca; }
        """)
        self._abort_btn.clicked.connect(self._abort)

        scope_l.addWidget(scope_label)
        scope_l.addWidget(self._scope_combo)
        scope_l.addStretch()
        scope_l.addWidget(self._run_btn)
        scope_l.addWidget(self._abort_btn)
        scope_card.add_widget(scope_inner)
        self._layout.addWidget(scope_card)

        # ---- Health card ----
        self._health_card = Card("Wiki Health")
        health_inner = QWidget()
        health_vl = QVBoxLayout(health_inner)
        health_vl.setContentsMargins(24, 20, 24, 20)
        health_vl.setSpacing(6)

        # Top row: Health Score (left) + Overall Status (right)
        top_row = QHBoxLayout()
        top_row.setSpacing(12)

        self._health_score_lbl = QLabel("—")
        self._health_score_lbl.setStyleSheet(
            "font-size: 36px; font-weight: bold; color: #94a3b8; background: transparent;"
        )

        self._health_status_lbl = QLabel("—")
        self._health_status_lbl.setStyleSheet(
            "font-size: 15px; font-weight: bold; color: #94a3b8; background: transparent;"
        )
        self._health_status_lbl.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        top_row.addWidget(self._health_score_lbl)
        top_row.addStretch()
        top_row.addWidget(self._health_status_lbl)

        # Caption beneath the score
        score_caption = QLabel("Health Score")
        score_caption.setStyleSheet(
            "color: #94a3b8; font-size: 11px; background: transparent;"
        )

        # Total issues line
        self._health_total_lbl = QLabel(
            "Run maintenance to check the health of the Persistent Memory."
        )
        self._health_total_lbl.setWordWrap(True)
        self._health_total_lbl.setStyleSheet(
            "color: #475569; font-size: 13px; background: transparent; padding-top: 4px;"
        )

        health_vl.addLayout(top_row)
        health_vl.addWidget(score_caption)
        health_vl.addWidget(self._health_total_lbl)
        self._health_card.add_widget(health_inner)
        self._layout.addWidget(self._health_card)

        # ---- Validation summary card ----
        self._validation_card = Card("Validation Summary")
        validation_inner = QWidget()
        self._validation_layout = QVBoxLayout(validation_inner)
        self._validation_layout.setContentsMargins(18, 10, 18, 10)
        self._validation_layout.setSpacing(0)
        self._show_validation_placeholder()
        self._validation_card.add_widget(validation_inner)
        self._layout.addWidget(self._validation_card)

        # ---- Issues card ----
        self._issues_card = Card("Detected Issues")
        issues_scroll = QScrollArea()
        issues_scroll.setWidgetResizable(True)
        issues_scroll.setFixedHeight(240)
        issues_scroll.setFrameShape(QFrame.Shape.NoFrame)

        self._issues_container = QWidget()
        self._issues_layout = QVBoxLayout(self._issues_container)
        self._issues_layout.setContentsMargins(16, 12, 16, 12)
        self._issues_layout.setSpacing(10)
        self._issues_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._issues_placeholder = QLabel(
            "No maintenance report available.\nRun maintenance to detect issues."
        )
        self._issues_placeholder.setStyleSheet(
            "color: #94a3b8; font-size: 12px; background: transparent;"
        )
        self._issues_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._issues_layout.addWidget(self._issues_placeholder)

        issues_scroll.setWidget(self._issues_container)
        self._issues_card.add_widget(issues_scroll)
        self._layout.addWidget(self._issues_card)

        # ---- Recommendations card ----
        self._rec_card = Card("Recommendations")
        self._rec_container = QWidget()
        self._rec_layout = QVBoxLayout(self._rec_container)
        self._rec_layout.setContentsMargins(16, 12, 16, 12)
        self._rec_layout.setSpacing(10)
        self._rec_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self._rec_placeholder = QLabel(
            "No recommendations yet.\nRun maintenance to generate recommendations."
        )
        self._rec_placeholder.setStyleSheet(
            "color: #94a3b8; font-size: 12px; background: transparent;"
        )
        self._rec_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._rec_layout.addWidget(self._rec_placeholder)
        self._rec_card.add_widget(self._rec_container)
        self._layout.addWidget(self._rec_card)

        self._layout.addStretch()
        scroll.setWidget(self._container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # State
    # ------------------------------------------------------------------

    def _set_idle_state(self) -> None:
        self._run_btn.setEnabled(True)
        self._abort_btn.setVisible(False)
        self.footer_update.emit("Maintenance • Ready")

    def _set_running_state(self) -> None:
        self._run_btn.setEnabled(False)
        self._abort_btn.setVisible(True)
        self.footer_update.emit("Maintenance Running • Analysing Persistent Memory")

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _run_maintenance(self) -> None:
        scope = self._scope_combo.currentText()
        self._set_running_state()
        self.inspector_update.emit("maintenance_started", {})

        self._worker = MaintenanceWorker(scope, self._config.root)
        self._worker.finished.connect(self._on_finished)
        self._worker.start()

    def _abort(self) -> None:
        if self._worker:
            self._worker.abort()
        self._set_idle_state()
        self.footer_update.emit("Maintenance Aborted")

    def _on_finished(self, result: dict) -> None:
        self._result = result

        if result.get("result") == "ABORTED":
            self.inspector_update.emit("maintenance_failed", {})
            self._set_idle_state()
            self.footer_update.emit("Maintenance Aborted")
            return

        from datetime import datetime
        result["last_scan"] = datetime.now().strftime("%Y-%m-%d %H:%M")

        self._update_health(result)
        self._update_validation(result)
        self._update_issues(result)
        self._update_recommendations(result)

        self.inspector_update.emit("maintenance_finished", result)
        self.footer_update.emit("Maintenance Finished • Persistent Memory Unchanged")
        self._set_idle_state()

    # ------------------------------------------------------------------
    # Display helpers
    # ------------------------------------------------------------------

    def _update_health(self, result: dict) -> None:
        overall_status = result.get("overall_status", "HEALTHY")
        bg, fg = _HEALTH_COLORS.get(overall_status, ("#f8fafc", "#64748b"))

        icons = {"HEALTHY": "🟢", "WARNING": "🟡", "CRITICAL": "🔴"}
        icon  = icons.get(overall_status, "⚪")

        # Health Score — computed in the GUI from engine-reported issue counts.
        # WARNING = -5 points, CRITICAL = -15 points, clamped to 0–100.
        stats    = result.get("statistics", {})
        warnings = stats.get("warning_issues", 0)
        critical = stats.get("critical_issues", 0)
        total    = stats.get("total_issues", 0)
        score    = max(0, min(100, 100 - warnings * 5 - critical * 15))

        self._health_score_lbl.setText(f"{score}%")
        self._health_score_lbl.setStyleSheet(
            f"font-size: 36px; font-weight: bold; color: {fg}; background: transparent;"
        )

        # Overall Status comes directly from the engine — never derived from the score.
        self._health_status_lbl.setText(f"{icon} {overall_status}")
        self._health_status_lbl.setStyleSheet(
            f"font-size: 15px; font-weight: bold; color: {fg}; background: transparent;"
        )

        if total == 0:
            total_text = "No issues detected."
        elif total == 1:
            total_text = "1 issue detected."
        else:
            total_text = f"{total} issues detected."
        self._health_total_lbl.setText(total_text)

    def _show_validation_placeholder(self) -> None:
        while self._validation_layout.count():
            item = self._validation_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        placeholder = QLabel("Run maintenance to see validation results.")
        placeholder.setStyleSheet(
            "color: #94a3b8; font-size: 12px; background: transparent; padding: 8px 0;"
        )
        placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._validation_layout.addWidget(placeholder)

    def _update_validation(self, result: dict) -> None:
        validation = result.get("validation_summary", {})

        while self._validation_layout.count():
            item = self._validation_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        _DISPLAY = {"PASS": "PASS", "WARNING": "WARNING", "FAIL": "FAIL"}
        _ICON    = {"PASS": "✔", "WARNING": "⚠", "FAIL": "✗"}
        _COLOR   = {"PASS": "#15803d", "WARNING": "#a16207", "FAIL": "#dc2626"}

        entries = list(validation.items())
        for idx, (category, raw_status) in enumerate(entries):
            display = _DISPLAY.get(raw_status, raw_status)
            icon    = _ICON.get(raw_status, "•")
            color   = _COLOR.get(raw_status, "#64748b")

            row = QWidget()
            row.setStyleSheet("background: transparent;")
            row_l = QHBoxLayout(row)
            row_l.setContentsMargins(0, 9, 0, 9)
            row_l.setSpacing(10)

            icon_lbl = QLabel(icon)
            icon_lbl.setFixedWidth(18)
            icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon_lbl.setStyleSheet(
                f"color: {color}; font-size: 13px; font-weight: bold;"
                " background: transparent;"
            )

            cat_lbl = QLabel(category)
            cat_lbl.setStyleSheet(
                "color: #1e293b; font-size: 13px; background: transparent;"
            )

            status_lbl = QLabel(display)
            status_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
            status_lbl.setStyleSheet(
                f"color: {color}; font-size: 12px; font-weight: bold;"
                " background: transparent;"
            )

            row_l.addWidget(icon_lbl)
            row_l.addWidget(cat_lbl)
            row_l.addStretch()
            row_l.addWidget(status_lbl)
            self._validation_layout.addWidget(row)

            # Thin separator between rows (skip after last)
            if idx < len(entries) - 1:
                sep = QFrame()
                sep.setFrameShape(QFrame.Shape.HLine)
                sep.setStyleSheet("background: #f1f5f9; border: none;")
                sep.setFixedHeight(1)
                self._validation_layout.addWidget(sep)

    def _update_issues(self, result: dict) -> None:
        while self._issues_layout.count():
            item = self._issues_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        issues = result.get("detected_issues", [])
        if not issues:
            no_issues = QLabel("✓ No issues detected.")
            no_issues.setStyleSheet(
                "color: #16a34a; font-size: 13px; background: transparent;"
                " padding: 12px;"
            )
            self._issues_layout.addWidget(no_issues)
            return

        _BORDER = {"CRITICAL": "#dc2626", "WARNING": "#f59e0b"}
        _SEV_FG  = {"CRITICAL": "#dc2626", "WARNING": "#a16207"}

        for i, issue in enumerate(issues):
            severity     = issue.get("severity", "WARNING")
            border_color = _BORDER.get(severity, "#f59e0b")
            sev_color    = _SEV_FG.get(severity, "#a16207")

            frame = QFrame()
            frame.setStyleSheet(f"""
                QFrame {{
                    background: #fafafa;
                    border-left: 4px solid {border_color};
                    border-radius: 8px;
                    padding: 2px;
                }}
            """)
            vl = QVBoxLayout(frame)
            vl.setContentsMargins(12, 10, 12, 10)
            vl.setSpacing(4)

            # Header: issue ID (left) + severity (right)
            header = QHBoxLayout()
            header.setSpacing(8)

            issue_id = issue.get("id", f"ISSUE-{i+1:03d}")
            id_lbl = QLabel(issue_id)
            id_lbl.setStyleSheet(
                "font-weight: bold; font-size: 12px; color: #1e293b; background: transparent;"
            )
            sev_lbl = QLabel(severity)
            sev_lbl.setStyleSheet(
                f"font-size: 11px; font-weight: bold; color: {sev_color};"
                " background: transparent;"
            )
            header.addWidget(id_lbl)
            header.addStretch()
            header.addWidget(sev_lbl)

            # Validation category
            cat_lbl = QLabel(issue.get("category", ""))
            cat_lbl.setStyleSheet(
                "font-size: 12px; color: #64748b; background: transparent;"
            )

            # Affected file (omit when empty)
            file_val = issue.get("file", "")

            # Description
            desc_lbl = QLabel(issue.get("description", ""))
            desc_lbl.setWordWrap(True)
            desc_lbl.setStyleSheet(
                "font-size: 12px; color: #334155; background: transparent;"
            )

            vl.addLayout(header)
            vl.addWidget(cat_lbl)
            if file_val:
                file_lbl = QLabel(file_val)
                file_lbl.setStyleSheet(
                    "font-size: 11px; color: #94a3b8; background: transparent;"
                )
                vl.addWidget(file_lbl)
            vl.addWidget(desc_lbl)
            self._issues_layout.addWidget(frame)

    def _update_recommendations(self, result: dict) -> None:
        while self._rec_layout.count():
            item = self._rec_layout.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

        recs = result.get("recommendations", [])
        if not recs:
            placeholder = QLabel("No recommendations.")
            placeholder.setStyleSheet(
                "color: #94a3b8; font-size: 12px; background: transparent;"
            )
            self._rec_layout.addWidget(placeholder)
            return

        for i, rec in enumerate(recs):
            frame = QFrame()
            frame.setStyleSheet("""
                QFrame {
                    background: #eff6ff;
                    border-left: 4px solid #2563eb;
                    border-radius: 8px;
                }
            """)
            vl = QVBoxLayout(frame)
            vl.setContentsMargins(14, 10, 14, 10)

            rec_id = f"REC-{i+1:03d}"
            text = QLabel(f"<strong>{rec_id}</strong>  {rec}")
            text.setWordWrap(True)
            text.setStyleSheet("font-size: 13px; color: #1e293b; background: transparent;")
            vl.addWidget(text)
            self._rec_layout.addWidget(frame)
