"""
Ingest operation page.

Allows the user to queue PDF files and run the Ingest pipeline.
Shows current document info, queue, pipeline timeline, and execution log.
Always uses a queue-based workflow — no manual/automatic mode distinction.
"""

import shutil
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QLabel, QPushButton, QFileDialog, QPlainTextEdit, QSizePolicy,
    QComboBox,
)
from PySide6.QtCore import Signal, Qt, QTimer

from ..config import WorkspaceConfig, SOURCE_DOCUMENT_EXTENSIONS
from ..components.card import Card
from ..runtime.worker import IngestWorker


# Multi-Model Claude: (display label, CLI --model alias) pairs offered by
# the model selector below. The alias values are the only ones verified
# against the installed Claude CLI (see feasibility analysis) — index 0
# ("sonnet") is also the CLI's own default model, so it is used as the
# combo's default selection to keep pre-revision behavior unchanged.
_MODEL_OPTIONS = [
    ("Claude Sonnet", "sonnet"),
    ("Claude Opus",   "opus"),
    ("Claude Haiku",  "haiku"),
]


_INGEST_STAGES = [
    "PRECHECK",
    "READ_SOURCE",
    "CREATE_SUMMARY",
    "EXTRACT_CANDIDATE_ENTITIES",
    "ENTITY_RESOLUTION",
    "UPDATE_ENTITIES",
    "UPDATE_INDEX",
    "UPDATE_LOG",
    "COMPLETE",
]

_STAGE_LOG_LABELS = {
    "PRECHECK":                   "Pre-check",
    "READ_SOURCE":                "Reading source document",
    "CREATE_SUMMARY":             "Creating summary",
    "EXTRACT_CANDIDATE_ENTITIES": "Extracting candidate entities",
    "ENTITY_RESOLUTION":          "Resolving entities",
    "UPDATE_ENTITIES":            "Updating entity pages",
    "UPDATE_INDEX":               "Updating knowledge index",
    "UPDATE_LOG":                 "Updating operation log",
    "COMPLETE":                   "Complete",
}

# Real progress values derived from pipeline stage completion — these are the
# only trustworthy milestones. The Inspector jumps straight to the current
# stage's milestone; it never interpolates or estimates in-stage progress.
_STAGE_PROGRESS = {
    "PRECHECK":                   10,
    "READ_SOURCE":                22,
    "CREATE_SUMMARY":             35,
    "EXTRACT_CANDIDATE_ENTITIES": 50,
    "ENTITY_RESOLUTION":          60,
    "UPDATE_ENTITIES":            72,
    "UPDATE_INDEX":               84,
    "UPDATE_LOG":                 93,
    "COMPLETE":                  100,
}

# Sub-stage status labels used by the inspector document panel
_STAGE_SUMMARY_STATUS = {
    "PRECHECK": "Pending", "READ_SOURCE": "Pending",
    "CREATE_SUMMARY": "In Progress",
    "EXTRACT_CANDIDATE_ENTITIES": "Completed",
    "ENTITY_RESOLUTION": "Completed", "UPDATE_ENTITIES": "Completed",
    "UPDATE_INDEX": "Completed", "UPDATE_LOG": "Completed",
    "COMPLETE": "Completed",
}
_STAGE_ENTITIES_STATUS = {
    "PRECHECK": "Pending", "READ_SOURCE": "Pending",
    "CREATE_SUMMARY": "Pending",
    "EXTRACT_CANDIDATE_ENTITIES": "In Progress",
    "ENTITY_RESOLUTION": "In Progress",
    "UPDATE_ENTITIES": "In Progress",
    "UPDATE_INDEX": "Completed", "UPDATE_LOG": "Completed",
    "COMPLETE": "Completed",
}
_STAGE_INDEX_STATUS = {
    s: ("Completed" if s in ("UPDATE_LOG", "COMPLETE") else
        "In Progress" if s == "UPDATE_INDEX" else "Pending")
    for s in _INGEST_STAGES
}
_STAGE_LOG_STATUS = {
    s: ("Completed" if s == "COMPLETE" else
        "In Progress" if s == "UPDATE_LOG" else "Pending")
    for s in _INGEST_STAGES
}

_QUEUE_ITEM_STYLE = """
QFrame {{
    background: #fafafa;
    border: 1px solid #e5e7eb;
    border-radius: 10px;
    padding: 4px;
}}
"""

_STATUS_COLORS = {
    "Completed": "#16a34a",
    "Running":   "#2563eb",
    "Waiting":   "#ca8a04",
    "Failed":    "#dc2626",
    "Aborted":   "#64748b",
}


class _QueueItem(QFrame):
    """Single item in the document queue."""

    remove_requested = Signal()

    def __init__(self, filename: str, status: str = "Waiting", parent=None):
        super().__init__(parent)
        self.setStyleSheet(_QUEUE_ITEM_STYLE)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 8, 8)
        layout.setSpacing(8)

        self._name_lbl = QLabel(filename)
        self._name_lbl.setStyleSheet(
            "background: transparent; font-size: 12px; color: #334155;"
        )
        self._name_lbl.setMinimumWidth(60)
        self._name_lbl.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )

        self._status_lbl = QLabel(status)
        self._status_lbl.setStyleSheet(
            f"background: transparent; color: {_STATUS_COLORS.get(status, '#64748b')};"
            " font-size: 12px; font-weight: bold;"
        )

        self._remove_btn = QPushButton("×")   # × character
        self._remove_btn.setFixedSize(22, 22)
        self._remove_btn.setToolTip("Remove from queue")
        self._remove_btn.setStyleSheet("""
            QPushButton {
                background: #f1f5f9;
                color: #64748b;
                border: none;
                border-radius: 11px;
                font-size: 14px;
                font-weight: bold;
                padding: 0;
            }
            QPushButton:hover { background: #fee2e2; color: #dc2626; }
        """)
        self._remove_btn.clicked.connect(self.remove_requested)
        self._remove_btn.setVisible(status == "Waiting")

        layout.addWidget(self._name_lbl)
        layout.addStretch()
        layout.addWidget(self._status_lbl)
        layout.addWidget(self._remove_btn)

    def set_status(self, status: str) -> None:
        self._status_lbl.setText(status)
        color = _STATUS_COLORS.get(status, "#64748b")
        self._status_lbl.setStyleSheet(
            f"background: transparent; color: {color};"
            " font-size: 12px; font-weight: bold;"
        )
        # Remove button only makes sense for items not yet started
        self._remove_btn.setVisible(status == "Waiting")


class IngestPage(QWidget):
    """Ingest operation workspace."""

    inspector_update = Signal(str, dict)
    footer_update    = Signal(str)
    wiki_changed     = Signal()   # emitted whenever Persistent Memory is updated

    def __init__(
        self,
        config: WorkspaceConfig,
        parent: QWidget | None = None,
    ):
        super().__init__(parent)
        self._config = config
        self._worker: IngestWorker | None = None
        # Multi-Model Claude: the CLI model alias locked in for the
        # currently running (or most recently started) batch. Read once
        # from the combo in _start_ingest() and reused unchanged for every
        # document in that batch — see _process_next().
        self._batch_model: str | None = None

        # Queue state — always processed front-to-back
        self._queue: list[str] = []            # raw/ paths in order
        self._queue_items: list[_QueueItem] = []
        # Paths that were COPIED into raw/ by the GUI (eligible for deletion on removal)
        self._queue_copied: set[str] = set()

        # Batch tracking for inspector
        self._done_in_batch = 0

        self._elapsed_secs  = 0
        self._current_stage = ""
        # True once a genuine stage_changed signal has arrived for the
        # document currently running — gates determinate vs indeterminate
        # progress in the Inspector (see _emit_inspector_update).
        self._stage_seen    = False
        self._elapsed_timer = QTimer(self)
        self._elapsed_timer.setInterval(1000)
        self._elapsed_timer.timeout.connect(self._tick_elapsed)

        self._build_ui()
        self._set_idle_state()

    # ------------------------------------------------------------------
    # UI Construction
    # ------------------------------------------------------------------

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
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        # ---- Queue + Current Document (split) ----
        split = QWidget()
        split.setStyleSheet("background: transparent;")
        split_layout = QHBoxLayout(split)
        split_layout.setContentsMargins(0, 0, 0, 0)
        split_layout.setSpacing(20)

        # Queue card
        queue_card = Card("Queue")
        queue_inner = QWidget()
        queue_vl = QVBoxLayout(queue_inner)
        queue_vl.setContentsMargins(16, 12, 16, 0)
        queue_vl.setSpacing(8)

        self._queue_container = QWidget()
        self._queue_layout = QVBoxLayout(self._queue_container)
        self._queue_layout.setContentsMargins(0, 0, 0, 0)
        self._queue_layout.setSpacing(8)
        self._queue_layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        queue_scroll = QScrollArea()
        queue_scroll.setWidgetResizable(True)
        queue_scroll.setFixedHeight(280)
        queue_scroll.setFrameShape(QFrame.Shape.NoFrame)
        queue_scroll.setWidget(self._queue_container)

        self._queue_placeholder = QLabel(
            "Queue is empty.\nClick “Add Documents” to select PDF or image files."
        )
        self._queue_placeholder.setStyleSheet(
            "color: #94a3b8; font-size: 12px; background: transparent;"
        )
        self._queue_placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._queue_layout.addWidget(self._queue_placeholder)

        queue_vl.addWidget(queue_scroll)

        q_actions = QWidget()
        q_act_l = QHBoxLayout(q_actions)
        q_act_l.setContentsMargins(0, 8, 0, 12)
        q_act_l.setSpacing(10)

        _btn_style = (
            "QPushButton { background: #e2e8f0; border: none; border-radius: 10px;"
            " padding: 8px 14px; font-size: 12px; color: #1e293b; }"
            " QPushButton:hover { background: #cbd5e1; }"
        )

        add_btn = QPushButton("Add Documents")
        add_btn.setStyleSheet(_btn_style)
        add_btn.clicked.connect(self._add_documents)

        clear_btn = QPushButton("Clear Queue")
        clear_btn.setStyleSheet(_btn_style)
        clear_btn.clicked.connect(self._clear_queue)

        q_act_l.addWidget(add_btn)
        q_act_l.addWidget(clear_btn)
        q_act_l.addStretch()
        queue_vl.addWidget(q_actions)
        queue_card.add_widget(queue_inner)

        # Current Document card
        doc_card = Card("Current Document")
        doc_inner = QWidget()
        doc_grid = QVBoxLayout(doc_inner)
        doc_grid.setContentsMargins(20, 18, 20, 18)
        doc_grid.setSpacing(14)

        info_row = QWidget()
        info_layout = QHBoxLayout(info_row)
        info_layout.setContentsMargins(0, 0, 0, 0)
        info_layout.setSpacing(40)

        def _info_col(label: str) -> tuple[QWidget, QLabel]:
            col = QWidget()
            col_l = QVBoxLayout(col)
            col_l.setContentsMargins(0, 0, 0, 0)
            col_l.setSpacing(4)
            lbl = QLabel(label.upper())
            lbl.setStyleSheet(
                "font-size: 10px; color: #64748b; font-weight: bold; background: transparent;"
            )
            val = QLabel("—")   # em dash
            val.setStyleSheet("font-size: 13px; color: #1e293b; background: transparent;")
            col_l.addWidget(lbl)
            col_l.addWidget(val)
            return col, val

        col_fn, self._doc_filename = _info_col("Filename")
        col_sz, self._doc_size     = _info_col("Size")
        col_st, self._doc_status   = _info_col("Status")

        info_layout.addWidget(col_fn)
        info_layout.addWidget(col_sz)
        info_layout.addWidget(col_st)
        info_layout.addStretch()
        doc_grid.addWidget(info_row)

        actions = QWidget()
        act_layout = QHBoxLayout(actions)
        act_layout.setContentsMargins(0, 0, 0, 0)
        act_layout.setSpacing(12)

        model_label = QLabel("Model:")
        model_label.setStyleSheet(
            "color: #1e293b; font-size: 13px; background: transparent;"
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

        self._start_btn = QPushButton("Start Ingest")
        self._start_btn.setStyleSheet("""
            QPushButton { background: #2563eb; color: white; border: none;
                          border-radius: 10px; padding: 10px 16px;
                          font-size: 13px; font-weight: bold; }
            QPushButton:hover { background: #1d4ed8; }
            QPushButton:disabled { background: #93c5fd; }
        """)
        self._start_btn.clicked.connect(self._start_ingest)

        self._abort_btn = QPushButton("Abort")
        self._abort_btn.setVisible(False)
        self._abort_btn.setStyleSheet("""
            QPushButton { background: #fee2e2; color: #dc2626; border: none;
                          border-radius: 10px; padding: 10px 16px; font-size: 13px; }
            QPushButton:hover { background: #fecaca; }
        """)
        self._abort_btn.clicked.connect(self._abort_ingest)

        act_layout.addWidget(model_label)
        act_layout.addWidget(self._model_combo)
        act_layout.addWidget(self._start_btn)
        act_layout.addWidget(self._abort_btn)
        act_layout.addStretch()
        doc_grid.addWidget(actions)
        doc_card.add_widget(doc_inner)

        split_layout.addWidget(queue_card)
        split_layout.addWidget(doc_card)
        layout.addWidget(split)

        # ---- Execution log card ----
        log_card = Card("Execution Log")
        log_inner = QWidget()
        log_inner.setStyleSheet("background: transparent;")
        log_vl = QVBoxLayout(log_inner)
        log_vl.setContentsMargins(0, 0, 0, 0)
        log_vl.setSpacing(0)

        log_toolbar = QWidget()
        log_toolbar.setStyleSheet("background: transparent;")
        log_toolbar_l = QHBoxLayout(log_toolbar)
        log_toolbar_l.setContentsMargins(16, 10, 16, 10)
        log_toolbar_l.addStretch()

        clear_log_btn = QPushButton("Clear Log")
        clear_log_btn.setStyleSheet(_btn_style)
        clear_log_btn.clicked.connect(self._clear_log)
        log_toolbar_l.addWidget(clear_log_btn)
        log_vl.addWidget(log_toolbar)

        self._exec_log = QPlainTextEdit()
        self._exec_log.setReadOnly(True)
        self._exec_log.setFixedHeight(280)
        self._exec_log.setStyleSheet("""
            QPlainTextEdit {
                background: #1e293b;
                color: #94a3b8;
                font-family: Consolas, "Courier New", monospace;
                font-size: 12px;
                border: none;
                padding: 16px;
                border-radius: 0 0 12px 12px;
            }
        """)
        log_vl.addWidget(self._exec_log)
        log_card.add_widget(log_inner)
        layout.addWidget(log_card)

        layout.addStretch()
        scroll.setWidget(container)
        outer.addWidget(scroll)

    # ------------------------------------------------------------------
    # State management
    # ------------------------------------------------------------------

    def _set_idle_state(self) -> None:
        self._start_btn.setEnabled(True)
        self._abort_btn.setVisible(False)
        # Multi-Model Claude: only reached at true batch boundaries (see
        # _on_all_done() and the ABORTED branch of _on_ingest_finished()) —
        # never between documents of an in-progress batch — so re-enabling
        # here cannot let the model change mid-batch.
        self._model_combo.setEnabled(True)
        self.inspector_update.emit("ingest_idle", {})
        self.footer_update.emit("Ingest • Waiting for Document")

    def _set_running_state(self) -> None:
        self._start_btn.setEnabled(False)
        self._abort_btn.setVisible(True)
        # Locked for the running document AND re-asserted (already
        # disabled, so this is a no-op) for every subsequent document in
        # the same batch, since _process_next() calls this again per
        # document without an intervening _set_idle_state() call.
        self._model_combo.setEnabled(False)
        self._elapsed_secs = 0
        self._elapsed_timer.start()
        self.footer_update.emit("Ingest Running • Persistent Memory Updating")

    def _tick_elapsed(self) -> None:
        self._elapsed_secs += 1
        m, s = divmod(self._elapsed_secs, 60)
        self.inspector_update.emit("ingest_tick", {"elapsed": f"{m:02d}:{s:02d}"})

    def _emit_inspector_update(self, elapsed: str = "—", new_document: bool = False) -> None:
        """Push the current ingest state to the inspector."""
        stage = self._current_stage
        self.inspector_update.emit("ingest_running", {
            "elapsed":          elapsed,
            "filename":         self._doc_filename.text(),
            "queue_pos":        str(self._done_in_batch + 1),
            "queue_total":      str(self._done_in_batch + len(self._queue)),
            "summary_status":   _STAGE_SUMMARY_STATUS.get(stage, "Pending"),
            "entities_status":  _STAGE_ENTITIES_STATUS.get(stage, "Pending"),
            "index_status":     _STAGE_INDEX_STATUS.get(stage, "Pending"),
            "log_status":       _STAGE_LOG_STATUS.get(stage, "Pending"),
            "progress":         _STAGE_PROGRESS.get(stage, 0),
            "new_document":     new_document,
            "has_stage":        self._stage_seen,
        })

    # ------------------------------------------------------------------
    # Source document management
    # ------------------------------------------------------------------

    def _ensure_in_raw(self, path: str) -> str | None:
        """
        Ensure the PDF exists inside raw/.  Reuses the existing raw/ file when
        available; copies from elsewhere only when needed.
        Returns the canonical raw/ path, or None on failure.
        """
        p = Path(path)
        if not p.exists() or not p.is_file():
            return None

        raw_dir = self._config.raw
        raw_dir.mkdir(exist_ok=True)
        raw_path = raw_dir / p.name

        # Source IS the raw/ file — no copy needed
        try:
            if p.samefile(raw_path):
                return str(raw_path)
        except (FileNotFoundError, OSError):
            pass

        # A raw/ file with the same name already exists — reuse it as-is
        if raw_path.exists():
            return str(raw_path)

        # Copy the file into raw/
        try:
            shutil.copy2(str(p), str(raw_path))
        except Exception:
            return None

        return str(raw_path)

    # ------------------------------------------------------------------
    # Queue management
    # ------------------------------------------------------------------

    def _add_documents(self) -> None:
        """Open a multi-file dialog and add all selected source documents to the queue."""
        patterns = " ".join(f"*{ext}" for ext in SOURCE_DOCUMENT_EXTENSIONS)
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select Source Documents",
            str(self._config.raw),
            f"Supported Documents ({patterns});;PDF Files (*.pdf);;"
            "Image Files (*.png *.jpg *.jpeg)",
        )
        for path in paths:
            self._queue_add(path)

    def _queue_add(self, path: str) -> None:
        """Add a source document to the queue, copying it into raw/ if necessary."""
        p = Path(path)
        raw_dir = self._config.raw
        raw_candidate = raw_dir / p.name

        # Decide BEFORE the copy whether a new file will be created in raw/.
        # If raw_candidate already exists (same file or same-name file), no copy is made.
        will_create_copy = not raw_candidate.exists()

        raw_path = self._ensure_in_raw(path)
        if raw_path is None:
            return
        if raw_path in self._queue:
            return   # already queued

        if will_create_copy:
            self._queue_copied.add(raw_path)

        self._queue.append(raw_path)
        self._queue_placeholder.setVisible(False)

        filename = Path(raw_path).name
        item = _QueueItem(filename, "Waiting")
        item.remove_requested.connect(lambda p=raw_path: self._queue_remove_path(p))
        self._queue_items.append(item)
        self._queue_layout.addWidget(item)

        if self._worker and self._worker.isRunning():
            m, s = divmod(self._elapsed_secs, 60)
            self._emit_inspector_update(f"{m:02d}:{s:02d}")

    def _queue_remove_path(self, path: str) -> None:
        """Remove a Waiting item from the queue by path."""
        if path not in self._queue:
            return
        idx = self._queue.index(path)

        # Never remove the item that is currently running (always at index 0)
        if idx == 0 and self._worker and self._worker.isRunning():
            return

        # Double-check: only Waiting items may be removed
        if idx < len(self._queue_items):
            status = self._queue_items[idx]._status_lbl.text()
            if status not in ("Waiting",):
                return

        self._queue.pop(idx)
        item = self._queue_items.pop(idx)
        self._queue_layout.removeWidget(item)
        item.setParent(None)
        item.deleteLater()

        # Delete the PDF from raw/ only if the GUI copied it there
        if path in self._queue_copied:
            self._queue_copied.discard(path)
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

        if not self._queue:
            self._queue_placeholder.setVisible(True)

        if self._worker and self._worker.isRunning():
            m, s = divmod(self._elapsed_secs, 60)
            self._emit_inspector_update(f"{m:02d}:{s:02d}")

    def _clear_queue(self) -> None:
        """Remove all queued items, preserving the currently running document."""
        running_path: str | None = None
        running_item: _QueueItem | None = None

        if self._worker and self._worker.isRunning() and self._queue:
            # Preserve the front item — it is currently being processed
            running_path = self._queue[0]
            running_item = self._queue_items[0] if self._queue_items else None
            self._queue       = [running_path]
            self._queue_items = [running_item] if running_item else []

        # Delete copied PDFs for every item that will be cleared
        for path in list(self._queue_copied):
            if path == running_path:
                continue   # don't delete the running document
            self._queue_copied.discard(path)
            try:
                Path(path).unlink(missing_ok=True)
            except Exception:
                pass

        # Remove all widgets from the layout except the running item and placeholder
        for i in range(self._queue_layout.count() - 1, -1, -1):
            w = self._queue_layout.itemAt(i).widget()
            if w is None or w is running_item or w is self._queue_placeholder:
                continue
            self._queue_layout.removeWidget(w)
            w.setParent(None)
            w.deleteLater()

        if not running_item:
            self._queue       = []
            self._queue_items = []
            self._queue_layout.addWidget(self._queue_placeholder)
            self._queue_placeholder.setVisible(True)

        if self._worker and self._worker.isRunning():
            m, s = divmod(self._elapsed_secs, 60)
            self._emit_inspector_update(f"{m:02d}:{s:02d}")

    def _schedule_remove_widget(self, item: _QueueItem) -> None:
        """Schedule a completed/failed queue item for removal after a short delay."""
        def _do_remove() -> None:
            self._queue_layout.removeWidget(item)
            item.setParent(None)
            item.deleteLater()
            # Show placeholder only when the queue is empty and no items remain
            if not self._queue and not self._queue_items:
                self._queue_layout.addWidget(self._queue_placeholder)
                self._queue_placeholder.setVisible(True)

        QTimer.singleShot(1500, _do_remove)

    # ------------------------------------------------------------------
    # Ingest execution
    # ------------------------------------------------------------------

    def _start_ingest(self) -> None:
        if not self._queue:
            return
        self._done_in_batch = 0
        # Multi-Model Claude: read the model selector exactly once, at the
        # start of the batch. Every document processed by _process_next()
        # below reuses this same value — the combo itself is locked for
        # the whole batch (see _set_running_state()/_set_idle_state()), so
        # this is also the only read that can ever matter.
        self._batch_model = self._model_combo.currentData()
        self._process_next()

    def _process_next(self) -> None:
        """Start processing the front of the queue."""
        if not self._queue:
            self._on_all_done()
            return

        pdf_path = self._queue[0]
        p = Path(pdf_path)
        size_mb = p.stat().st_size / (1024 * 1024) if p.exists() else 0

        # Update document info panel
        self._doc_filename.setText(p.name)
        self._doc_size.setText(f"{size_mb:.1f} MB")
        self._doc_status.setText("Processing")
        self._doc_status.setStyleSheet(
            "font-size: 13px; color: #2563eb; font-weight: bold; background: transparent;"
        )

        self._append_log_header(p.name)
        self._current_stage = ""
        self._stage_seen = False
        self._set_running_state()

        if self._queue_items:
            self._queue_items[0].set_status("Running")

        self._emit_inspector_update("00:00", new_document=True)

        self._worker = IngestWorker(pdf_path, self._config.root, model=self._batch_model)
        self._worker.stage_changed.connect(self._on_stage_changed)
        self._worker.log_appended.connect(self._on_log_appended)
        self._worker.document_completed.connect(self._on_document_completed)
        self._worker.finished.connect(self._on_ingest_finished)
        self._worker.start()

    def _abort_ingest(self) -> None:
        if self._worker:
            self._worker.abort()

    # ------------------------------------------------------------------
    # Worker callbacks
    # ------------------------------------------------------------------

    def _on_stage_changed(self, stage: str) -> None:
        self._current_stage = stage
        self._stage_seen = True
        m, s = divmod(self._elapsed_secs, 60)
        self._emit_inspector_update(f"{m:02d}:{s:02d}")

    def _on_log_appended(self, msg: str) -> None:
        """
        Single append pipeline for the execution log: every runtime event,
        stage marker, tool event, and Claude output line arrives here in
        exact worker-emission order and is appended exactly once.
        """
        self._exec_log.appendPlainText(self._humanize_stage_marker(msg))

    def _append_log_header(self, filename: str) -> None:
        """Start a new document's block in the batch log without clearing prior history."""
        if self._exec_log.toPlainText():
            self._exec_log.appendPlainText("")
        separator = "=" * 10
        self._exec_log.appendPlainText(separator)
        self._exec_log.appendPlainText(filename)
        self._exec_log.appendPlainText(separator)

    def _clear_log(self) -> None:
        self._exec_log.clear()

    @staticmethod
    def _humanize_stage_marker(msg: str) -> str:
        """Rewrite a raw '<timestamp>  ▶ STAGE_NAME' line into its human label."""
        marker = "▶ "
        idx = msg.find(marker)
        if idx == -1:
            return msg
        raw_stage = msg[idx + len(marker):].strip()
        label = _STAGE_LOG_LABELS.get(raw_stage)
        if label is None:
            return msg
        return f"{msg[:idx]}{marker}{label}"

    def _on_document_completed(self, filename: str, result: str) -> None:
        """Update the queue item status when the worker reports completion."""
        if not self._queue_items:
            return
        status_map = {"SUCCESS": "Completed", "FAILED": "Failed", "ABORTED": "Aborted"}
        self._queue_items[0].set_status(status_map.get(result, "Failed"))

    def _on_ingest_finished(self, result: dict) -> None:
        self._elapsed_timer.stop()
        res = result.get("result", "SUCCESS")
        self.inspector_update.emit("ingest_result", result)

        self._exec_log.appendPlainText("")
        self._exec_log.appendPlainText(res)

        # Capture and remove the processed document before calling _process_next()
        processed_path: str | None = self._queue.pop(0) if self._queue else None
        popped_item: _QueueItem | None = self._queue_items.pop(0) if self._queue_items else None

        if popped_item is not None:
            self._schedule_remove_widget(popped_item)

        # A processed file (success OR failure) stays in raw/ — remove from
        # the copy-tracking set so it won't be deleted by future clear/remove.
        if processed_path:
            self._queue_copied.discard(processed_path)

        if res == "ABORTED":
            # Stop the queue; remaining items stay for the user to re-run.
            self._set_idle_state()
            self.footer_update.emit("Ingest Aborted")
            return

        self._done_in_batch += 1

        if res == "SUCCESS":
            self.wiki_changed.emit()

        # FAILED result: surface it in the log and continue with remaining queue
        if res == "FAILED":
            fname = result.get("filename", "")
            self._exec_log.appendPlainText(
                f"  ✗ {fname} failed — continuing with next document"
            )

        self._process_next()

    def _on_all_done(self) -> None:
        self._set_idle_state()
        self.footer_update.emit("Ingest Complete • Persistent Memory Updated")
        self.wiki_changed.emit()

        # Document info: reset to idle state
        self._doc_filename.setText("—")
        self._doc_size.setText("—")
        self._doc_status.setText("Done")
        self._doc_status.setStyleSheet(
            "font-size: 13px; color: #16a34a; font-weight: bold; background: transparent;"
        )

        # Ensure the placeholder is visible; individual removal timers may
        # not have fired yet, so show it now and let the timer no-op later.
        self._queue_placeholder.setVisible(True)
