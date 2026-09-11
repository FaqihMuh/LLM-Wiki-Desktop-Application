"""
Query operation page.

Allows the user to type a question and submit it to the Query Agent.
Displays the answer and entities read from wiki/entities/.
Metadata is derived from Claude tool usage, not text markers.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QTextEdit, QPushButton, QComboBox,
)
from PySide6.QtCore import Signal, QTimer

from ..config import WorkspaceConfig
from ..components.card import Card
from ..components.viewer_panel import ViewerPanel
from ..runtime.worker import QueryWorker
from ..state.working_memory import WorkingMemory


# Multi-Model Claude: (display label, CLI --model alias) pairs — kept in
# sync with the identical list in gui/pages/ingest.py. "sonnet" is both
# index 0 (default selection) and the Claude CLI's own default model, so
# leaving it selected reproduces pre-revision behavior exactly.
_MODEL_OPTIONS = [
    ("Claude Sonnet", "sonnet"),
    ("Claude Opus",   "opus"),
    ("Claude Haiku",  "haiku"),
]


class QueryPage(QWidget):
    """
    Query operation workspace.

    Signals:
        inspector_update(str, dict)  → page_id + payload for the Inspector
        footer_update(str)           → footer status text
    """

    inspector_update = Signal(str, dict)
    footer_update    = Signal(str)

    def __init__(
        self,
        config: WorkspaceConfig,
        working_memory: WorkingMemory,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._working_memory = working_memory
        self._worker: QueryWorker | None = None
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)
        self._elapsed_secs = 0

        self._build_ui()
        self._set_idle_state()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setStyleSheet("background: #f4f7fb;")

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(24, 24, 24, 24)
        self._layout.setSpacing(20)

        # ---- Query input card (natural height) ----
        query_card = Card("🔍 Query")
        query_box = QWidget()
        qb_layout = QHBoxLayout(query_box)
        qb_layout.setContentsMargins(18, 18, 18, 18)
        qb_layout.setSpacing(16)

        self._input = QTextEdit()
        self._input.setPlaceholderText(
            "Ask something about your Persistent Memory..."
        )
        self._input.setFixedHeight(90)
        self._input.setStyleSheet("""
            QTextEdit {
                border: 1px solid #d1d5db;
                border-radius: 12px;
                padding: 12px 14px;
                font-size: 13px;
                background: white;
                color: #1e293b;
            }
            QTextEdit:focus { border-color: #2563eb; }
        """)

        model_col = QWidget()
        model_col_l = QVBoxLayout(model_col)
        model_col_l.setContentsMargins(0, 0, 0, 0)
        model_col_l.setSpacing(4)

        model_label = QLabel("MODEL")
        model_label.setStyleSheet(
            "font-size: 10px; color: #64748b; font-weight: bold; background: transparent;"
        )

        self._model_combo = QComboBox()
        for label, alias in _MODEL_OPTIONS:
            self._model_combo.addItem(label, alias)
        self._model_combo.setStyleSheet("""
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

        model_col_l.addWidget(model_label)
        model_col_l.addWidget(self._model_combo)

        self._submit_btn = QPushButton("Query")
        self._submit_btn.setFixedSize(120, 90)
        self._submit_btn.setProperty("primary", True)
        self._submit_btn.setStyleSheet("""
            QPushButton {
                background: #2563eb;
                color: white;
                border-radius: 12px;
                font-size: 14px;
                font-weight: bold;
                border: none;
            }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #93c5fd; }
        """)
        self._submit_btn.clicked.connect(self._submit_query)

        qb_layout.addWidget(self._input)
        qb_layout.addWidget(model_col)
        qb_layout.addWidget(self._submit_btn)
        query_card.add_widget(query_box)
        self._layout.addWidget(query_card)

        # ---- Answer card (stretch=1: fills all remaining vertical space) ----
        self._answer_card = Card("📘 Answer")
        self._answer_browser = ViewerPanel()
        self._answer_card.add_widget(self._answer_browser)
        self._layout.addWidget(self._answer_card, stretch=1)

        # ---- Entities Used card (natural height) ----
        entities_card = Card("🗂 Entities Used")
        self._entities_label = QLabel('<p style="color:#94a3b8;font-style:italic;">No entities read yet.</p>')
        self._entities_label.setWordWrap(True)
        self._entities_label.setContentsMargins(18, 14, 18, 14)
        self._entities_label.setStyleSheet("background: transparent; font-size: 13px;")
        entities_card.add_widget(self._entities_label)
        self._layout.addWidget(entities_card)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _set_idle_state(self) -> None:
        self._submit_btn.setEnabled(True)
        self._model_combo.setEnabled(True)
        self.inspector_update.emit("query_idle", {})
        self.footer_update.emit("Query • Waiting for Question")

    def _tick_elapsed(self) -> None:
        self._elapsed_secs += 1
        self._emit_inspector_running()

    def _emit_inspector_running(self) -> None:
        elapsed = f"{self._elapsed_secs // 60:02d}:{self._elapsed_secs % 60:02d}"
        self.inspector_update.emit("query_running", {"elapsed": elapsed})

    def _set_running_state(self) -> None:
        self._submit_btn.setEnabled(False)
        self._model_combo.setEnabled(False)
        self._elapsed_secs = 0
        self.inspector_update.emit("query_running", {"elapsed": "00:00"})
        self._elapsed_timer.start()
        self.footer_update.emit("Query Running • Persistent Memory Active")

    def _set_finished_state(self, result: dict) -> None:
        self._elapsed_timer.stop()
        self._submit_btn.setEnabled(True)
        self._model_combo.setEnabled(True)
        self.inspector_update.emit("query_result", result)
        self.footer_update.emit("Query Completed • Persistent Memory Ready")

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------

    def _submit_query(self) -> None:
        question = self._input.toPlainText().strip()
        if not question:
            return

        if self._worker and self._worker.isRunning():
            self._worker.abort()
            return

        # Multi-Model Claude: read once, right before the worker is
        # created — the combo is disabled for the entire run by
        # _set_running_state() below, so this is the only read that can
        # ever affect this invocation.
        selected_model = self._model_combo.currentData()

        self._worker = QueryWorker(
            question=question,
            working_memory=self._working_memory.to_context(),
            project_root=self._config.root,
            model=selected_model,
        )
        self._worker.finished.connect(self._on_finished)
        self._worker.error_occurred.connect(self._on_error)

        self._answer_browser.clear()
        self._set_running_state()
        self._worker.start()

    def _on_finished(self, result: dict) -> None:
        if result.get("result") == "ABORTED":
            self.footer_update.emit("Query Aborted")
            self._set_idle_state()
            return

        answer   = result.get("answer",   "")
        question = result.get("question", "")
        entities = result.get("entities", [])

        if answer:
            self._answer_browser.show_query_result(answer)

        if entities:
            items_html = "".join(
                f'<li style="color:#1e293b;font-size:12px;">{e}</li>'
                for e in entities
            )
            self._entities_label.setText(f"<ul style='margin:8px 0 8px 16px;'>{items_html}</ul>")
        else:
            self._entities_label.setText(
                '<p style="color:#94a3b8;font-style:italic;">No entity pages were read.</p>'
            )

        self._working_memory.last_question     = question
        self._working_memory.last_answer       = answer
        self._working_memory.focus             = result.get("focus", "")
        self._working_memory.current_entities = entities

        self._set_finished_state(result)

    def _on_error(self, msg: str) -> None:
        self._elapsed_timer.stop()
        self._submit_btn.setEnabled(True)
        self._answer_browser.show_error(msg)
        self.footer_update.emit(f"Query Failed: {msg}")
        self._set_idle_state()
