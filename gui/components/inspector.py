"""
Right Inspector panel.

Adapts to the active page:
  - Knowledge Explorer pages → shows Selected Object metadata
  - Operation pages          → shows Runtime Inspector panels
"""

from PySide6.QtWidgets import (
    QFrame, QScrollArea, QVBoxLayout, QHBoxLayout,
    QLabel, QWidget, QProgressBar
)
from PySide6.QtCore import Qt


# ---------------------------------------------------------------------------
# Individual panel (titled box with key–value rows)
# ---------------------------------------------------------------------------

class _Panel(QFrame):
    """A white rounded panel with a title and key–value rows."""

    def __init__(self, title: str, parent: QWidget | None = None):
        super().__init__(parent)
        self.setStyleSheet("""
            QFrame {
                background: white;
                border: 1px solid #e5e7eb;
                border-radius: 12px;
            }
        """)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(16, 14, 16, 14)
        self._layout.setSpacing(0)

        title_lbl = QLabel(title)
        title_lbl.setStyleSheet(
            "font-size: 14px; font-weight: bold; color: #1e293b;"
            " background: transparent; border: none; margin-bottom: 10px;"
        )
        self._layout.addWidget(title_lbl)

    def add_row(self, key: str, value: str, value_color: str = "") -> QLabel:
        """Add a key/value row and return the value QLabel for later in-place updates."""
        row = QHBoxLayout()
        row.setContentsMargins(0, 6, 0, 6)

        key_lbl = QLabel(key)
        key_lbl.setStyleSheet(
            "color: #475569; font-size: 12px; background: transparent; border: none;"
        )
        val_lbl = QLabel(value)
        color = value_color or "#1e293b"
        val_lbl.setStyleSheet(
            f"color: {color}; font-size: 12px; background: transparent; border: none;"
        )
        val_lbl.setWordWrap(True)
        val_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)

        row.addWidget(key_lbl)
        row.addStretch()
        row.addWidget(val_lbl)
        self._layout.addLayout(row)
        return val_lbl

    def add_label(self, text: str, color: str = "#64748b") -> QLabel:
        """Add a full-width, word-wrapping label and return it for later in-place updates."""
        lbl = QLabel(text)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(
            f"color: {color}; font-size: 12px;"
            " background: transparent; border: none; padding: 4px 0;"
        )
        self._layout.addWidget(lbl)
        return lbl

    def add_list(self, items: list[str], item_color: str = "#16a34a") -> None:
        for item in items:
            self.add_label(item, item_color)

    def add_progress(self, value: int, indeterminate: bool = False) -> tuple[QProgressBar, QLabel]:
        bar = QProgressBar()
        if indeterminate:
            # No real stage signal has arrived yet — Qt renders range (0, 0)
            # as a busy/marquee animation instead of a stalled 0% bar.
            bar.setRange(0, 0)
        else:
            bar.setRange(0, 100)
            bar.setValue(value)
        bar.setFixedHeight(10)
        bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 5px;
                background: #dbe4ee;
            }
            QProgressBar::chunk {
                background: #2563eb;
                border-radius: 5px;
            }
        """)
        bar.setTextVisible(False)
        self._layout.addSpacing(10)
        self._layout.addWidget(bar)

        pct_lbl = QLabel("Working…" if indeterminate else f"{value}%")
        pct_lbl.setAlignment(Qt.AlignmentFlag.AlignRight)
        pct_lbl.setStyleSheet(
            "color: #64748b; font-size: 11px; background: transparent; border: none;"
        )
        self._layout.addWidget(pct_lbl)
        return bar, pct_lbl


# ---------------------------------------------------------------------------
# Inspector helpers
# ---------------------------------------------------------------------------

_ROW_VAL_STYLE = "font-size: 12px; background: transparent; border: none;"


def _set_row_val(lbl: QLabel, text: str, color: str = "#1e293b") -> None:
    """Update a key/value row's value label in place."""
    lbl.setText(text)
    lbl.setStyleSheet(f"color: {color}; {_ROW_VAL_STYLE}")


# ---------------------------------------------------------------------------
# Inspector
# ---------------------------------------------------------------------------

_STATUS_COLORS = {
    "Running": "#2563eb",
    "Finished": "#16a34a",
    "Completed": "#16a34a",
    "SUCCESS": "#16a34a",
    "FAILED": "#dc2626",
    "ABORTED": "#ca8a04",
    "WARNING": "#a16207",
    "CRITICAL": "#dc2626",
    "HEALTHY": "#16a34a",
    "Idle": "#64748b",
    "Ready": "#16a34a",
}


def _status_color(value: str) -> str:
    return _STATUS_COLORS.get(value, "#1e293b")


class Inspector(QFrame):
    """Right-side context panel with scrollable panels."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setFixedWidth(320)
        self.setStyleSheet("""
            QFrame {
                background: #fafafa;
                border-left: 1px solid #e5e7eb;
            }
        """)

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #fafafa;")

        self._container = QWidget()
        self._container.setStyleSheet("background: #fafafa;")
        self._inner = QVBoxLayout(self._container)
        self._inner.setContentsMargins(16, 18, 16, 18)
        self._inner.setSpacing(14)
        self._inner.setAlignment(Qt.AlignmentFlag.AlignTop)

        scroll.setWidget(self._container)
        outer.addWidget(scroll)

        # Persistent query widget refs — built once per query, updated in place.
        # All refs are invalidated by _clear() → _reset_query_persistent().
        self._qp_built:        bool          = False
        self._qp_status_lbl:   QLabel | None = None
        self._qp_elapsed_lbl:  QLabel | None = None
        self._qp_entities_lbl: QLabel | None = None
        self._qp_focus_lbl:    QLabel | None = None
        self._qp_question_lbl: QLabel | None = None
        self._qp_answer_lbl:   QLabel | None = None

        # Persistent ingest widget refs — built once per document, updated in place.
        # All refs are invalidated by _clear() → _reset_ingest_persistent().
        self._ip_built:        bool                = False
        self._ip_status_lbl:   QLabel | None       = None
        self._ip_elapsed_lbl:  QLabel | None       = None
        self._ip_queue_lbl:    QLabel | None       = None
        self._ip_filename_lbl: QLabel | None       = None
        self._ip_summary_lbl:  QLabel | None       = None
        self._ip_entities_lbl: QLabel | None       = None
        self._ip_index_lbl:    QLabel | None       = None
        self._ip_log_lbl:      QLabel | None       = None
        self._ip_progress_bar: QProgressBar | None = None
        self._ip_pct_lbl:      QLabel | None       = None

        # The displayed value is always the milestone of the last completed
        # pipeline stage — no interpolation or animation between stages.
        self._ip_progress_value: int = 0

        # True until the first genuine stage_changed signal has been observed
        # for the current document — while true, the bar is indeterminate
        # (busy) rather than showing a stalled, potentially misleading 0%.
        self._ip_indeterminate: bool = True

        # Persistent maintenance widget refs — built once per run, updated in place.
        # All refs are invalidated by _clear() → _reset_maintenance_persistent().
        self._mp_built:        bool          = False
        self._mp_status_lbl:   QLabel | None = None
        self._mp_scan_lbl:     QLabel | None = None
        self._mp_duration_lbl: QLabel | None = None

        # Show idle state by default
        self.show_idle()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _clear(self) -> None:
        # Persistent refs point into the widgets about to be destroyed.
        self._reset_query_persistent()
        self._reset_ingest_persistent()
        self._reset_maintenance_persistent()
        while self._inner.count():
            item = self._inner.takeAt(0)
            w = item.widget()
            if w:
                w.deleteLater()

    def _add_panel(self, panel: _Panel) -> None:
        self._inner.addWidget(panel)

    def _reset_query_persistent(self) -> None:
        """Invalidate all persistent query refs. Called by _clear() before destroying widgets."""
        self._qp_built        = False
        self._qp_status_lbl   = None
        self._qp_elapsed_lbl  = None
        self._qp_entities_lbl = None
        self._qp_focus_lbl    = None
        self._qp_question_lbl = None
        self._qp_answer_lbl   = None

    def _reset_ingest_persistent(self) -> None:
        """Invalidate all persistent ingest refs. Called by _clear() before destroying widgets."""
        self._ip_built        = False
        self._ip_status_lbl   = None
        self._ip_elapsed_lbl  = None
        self._ip_queue_lbl    = None
        self._ip_filename_lbl = None
        self._ip_summary_lbl  = None
        self._ip_entities_lbl = None
        self._ip_index_lbl    = None
        self._ip_log_lbl      = None
        self._ip_progress_bar = None
        self._ip_pct_lbl      = None
        self._ip_progress_value = 0
        self._ip_indeterminate  = True

    def _reset_maintenance_persistent(self) -> None:
        """Invalidate all persistent maintenance refs. Called by _clear() before destroying widgets."""
        self._mp_built        = False
        self._mp_status_lbl   = None
        self._mp_scan_lbl     = None
        self._mp_duration_lbl = None

    # ------------------------------------------------------------------
    # Idle / default
    # ------------------------------------------------------------------

    def show_idle(self) -> None:
        self._clear()
        p = _Panel("Inspector")
        p.add_row("Mode", "Idle")
        p.add_row("Status", "Ready", _status_color("Ready"))
        self._add_panel(p)

    # ------------------------------------------------------------------
    # Home
    # ------------------------------------------------------------------

    def show_home_welcome(self) -> None:
        self._clear()
        w = _Panel("Welcome")
        w.add_label(
            "LLM Wiki maintains a persistent, incremental knowledge base "
            "built from ingested research documents.",
            "#475569",
        )
        self._add_panel(w)

    # ------------------------------------------------------------------
    # Knowledge Explorer inspectors
    # ------------------------------------------------------------------

    def show_selected_document(self, info: dict) -> None:
        self._clear()
        p = _Panel("Selected Document")
        p.add_row("Filename", info.get("filename", "—"))
        p.add_row("Status", info.get("status", "—"), _status_color("Ready"))
        p.add_row("Modified", info.get("modified", "—"))
        p.add_row("Size", info.get("size", "—"))
        self._add_panel(p)

    def show_selected_summary(self, info: dict) -> None:
        self._clear()
        p = _Panel("Selected Summary")
        p.add_row("Topic", info.get("topic", "—"))
        p.add_row("Entities", info.get("entities", "—"))
        p.add_row("Updated", info.get("updated", "—"))
        p.add_row("Source", info.get("source", "—"))
        self._add_panel(p)

    def show_selected_entity(self, info: dict) -> None:
        self._clear()
        p = _Panel("Selected Entity")
        p.add_row("Name", info.get("name", "—"))
        p.add_row("Type", info.get("type", "—"))
        p.add_row("Status", info.get("status", "—"))
        p.add_row("Confidence", info.get("confidence", "—"))
        p.add_row("Updated", info.get("last_updated", "—"))
        self._add_panel(p)

    def show_selected_index_entry(self, info: dict) -> None:
        self._clear()
        p = _Panel("Selected Registry Entry")
        p.add_row("arXiv", info.get("arxiv", "—"))
        p.add_row("Entities", info.get("entities", "—"))
        p.add_row("Status", info.get("status", "Indexed"), _status_color("Ready"))
        p.add_row("Ingest", info.get("ingest_date", "—"))
        self._add_panel(p)

    def show_selected_log(self, info: dict) -> None:
        self._clear()
        p = _Panel("Selected Log")
        result = info.get("result", "—")
        p.add_row("Status", result, _status_color(result))
        p.add_row("Document", info.get("document", "—"))
        self._add_panel(p)

    # ------------------------------------------------------------------
    # Query runtime
    # ------------------------------------------------------------------

    def show_query_idle(self) -> None:
        self._clear()
        p = _Panel("Runtime")
        p.add_row("Status", "Idle")
        p.add_row("Duration", "—")
        self._add_panel(p)

        wm = _Panel("Working Memory")
        wm.add_row("Focus", "—")
        wm.add_row("Last Question", "—")
        wm.add_row("Last Answer", "—")
        self._add_panel(wm)

    def _build_query_panels(self) -> None:
        """
        Build query panels exactly once per query run.
        Stores label references for in-place updates throughout the query lifetime.
        Called by show_query_running() on the first invocation after _clear().
        """
        self._clear()  # invalidates refs via _reset_query_persistent()

        # ── Runtime ──────────────────────────────────────────────────────
        p = _Panel("Runtime")
        self._qp_status_lbl  = p.add_row("Status",  "Running", _status_color("Running"))
        self._qp_elapsed_lbl = p.add_row("Elapsed", "00:00")
        self._add_panel(p)

        # ── Evidence ─────────────────────────────────────────────────────
        ev = _Panel("Evidence")
        self._qp_entities_lbl = ev.add_row("Entities", "—")
        self._add_panel(ev)

        # ── Working Memory ────────────────────────────────────────────────
        wm = _Panel("Working Memory")
        self._qp_focus_lbl    = wm.add_row("Focus",         "—")
        self._qp_question_lbl = wm.add_row("Last Question", "—")
        self._qp_answer_lbl   = wm.add_row("Last Answer",   "—")
        self._add_panel(wm)

        self._qp_built = True

    def show_query_running(self, elapsed: str = "—") -> None:
        """
        Update the query inspector during streaming.
        Builds panels on the first call; every subsequent call updates
        only QLabel text and colour — no widget recreation.
        """
        if not self._qp_built:
            self._build_query_panels()

        if self._qp_status_lbl:
            _set_row_val(self._qp_status_lbl, "Running", _status_color("Running"))
        if self._qp_elapsed_lbl:
            _set_row_val(self._qp_elapsed_lbl, elapsed)

    def show_query_result(self, result: dict) -> None:
        """
        Finalise the query inspector without recreating any widgets.
        Panels are already present from show_query_running(); only labels change.
        """
        if not self._qp_built:
            self._build_query_panels()

        if self._qp_status_lbl:
            _set_row_val(self._qp_status_lbl, "Finished", _status_color("Finished"))
        if self._qp_elapsed_lbl:
            _set_row_val(self._qp_elapsed_lbl, result.get("duration", "—"))

        if self._qp_entities_lbl:
            _set_row_val(self._qp_entities_lbl, str(result.get("entities_used", 0)))

        if self._qp_focus_lbl:
            _set_row_val(self._qp_focus_lbl, result.get("focus", "—") or "—")
        if self._qp_question_lbl:
            _set_row_val(self._qp_question_lbl,
                         "Available" if result.get("question") else "—")
        if self._qp_answer_lbl:
            _set_row_val(self._qp_answer_lbl,
                         "Available" if result.get("answer") else "—")

    # ------------------------------------------------------------------
    # Ingest runtime
    # ------------------------------------------------------------------

    def show_ingest_idle(self) -> None:
        self._clear()
        p = _Panel("Runtime")
        p.add_row("Status", "Idle")
        p.add_row("Elapsed", "—")
        p.add_row("Queue", "—")
        self._add_panel(p)

    def _build_ingest_panels(self, status: dict) -> None:
        """
        Build ingest panels exactly once per document run.
        Stores label references for in-place updates throughout the document lifetime.
        Called by show_ingest_running() on the first invocation after _clear().
        """
        self._clear()  # invalidates refs via _reset_ingest_persistent()

        # ── Runtime ──────────────────────────────────────────────────────
        p = _Panel("Runtime")
        self._ip_status_lbl  = p.add_row("Status", "Running", _status_color("Running"))
        self._ip_elapsed_lbl = p.add_row("Elapsed", status.get("elapsed", "—"))
        queue_pos   = status.get("queue_pos",   "—")
        queue_total = status.get("queue_total", "—")
        self._ip_queue_lbl = p.add_row("Queue", f"{queue_pos} / {queue_total}")
        self._add_panel(p)

        # ── Current Document ─────────────────────────────────────────────
        doc = _Panel("Current Document")
        self._ip_filename_lbl = doc.add_row("Filename", status.get("filename", "—"))
        self._ip_summary_lbl  = doc.add_row("Summary",  status.get("summary_status",  "Pending"))
        self._ip_entities_lbl = doc.add_row("Entities", status.get("entities_status", "Pending"))
        self._ip_index_lbl    = doc.add_row("Index",    status.get("index_status",    "Pending"))
        self._ip_log_lbl      = doc.add_row("Log",      status.get("log_status",      "Pending"))
        self._add_panel(doc)

        # ── Progress ─────────────────────────────────────────────────────
        progress = _Panel("Progress")
        self._ip_progress_value = status.get("progress", 0)
        # Only trust the incoming percentage once a real stage_changed
        # signal has actually been observed (see IngestPage._stage_seen).
        self._ip_indeterminate  = not status.get("has_stage", False)
        self._ip_progress_bar, self._ip_pct_lbl = progress.add_progress(
            self._ip_progress_value, indeterminate=self._ip_indeterminate
        )
        self._add_panel(progress)

        self._ip_built = True

    def show_ingest_running(self, status: dict) -> None:
        """
        Update the ingest inspector during processing.
        Builds panels on the first call; every subsequent call updates
        only QLabel text and the progress bar value — no widget recreation.
        """
        if not self._ip_built:
            self._build_ingest_panels(status)
            return

        if status.get("new_document"):
            # A new document's run begins — reset the progress bar in place
            # rather than carrying over the previous document's 100%, and
            # go back to indeterminate until its first real stage arrives.
            self._ip_progress_value = 0
            self._ip_indeterminate  = True
            self._apply_ingest_progress_bar()

        if self._ip_status_lbl:
            _set_row_val(self._ip_status_lbl, "Running", _status_color("Running"))
        if self._ip_elapsed_lbl:
            _set_row_val(self._ip_elapsed_lbl, status.get("elapsed", "—"))

        queue_pos   = status.get("queue_pos",   "—")
        queue_total = status.get("queue_total", "—")
        if self._ip_queue_lbl:
            _set_row_val(self._ip_queue_lbl, f"{queue_pos} / {queue_total}")

        if self._ip_filename_lbl:
            _set_row_val(self._ip_filename_lbl, status.get("filename", "—"))
        if self._ip_summary_lbl:
            _set_row_val(self._ip_summary_lbl, status.get("summary_status", "Pending"))
        if self._ip_entities_lbl:
            _set_row_val(self._ip_entities_lbl, status.get("entities_status", "Pending"))
        if self._ip_index_lbl:
            _set_row_val(self._ip_index_lbl, status.get("index_status", "Pending"))
        if self._ip_log_lbl:
            _set_row_val(self._ip_log_lbl, status.get("log_status", "Pending"))

        self._ip_progress_value = status.get("progress", 0)
        self._ip_indeterminate  = not status.get("has_stage", False)
        self._apply_ingest_progress_bar()

    def show_ingest_elapsed(self, elapsed: str) -> None:
        """Update only the elapsed time label — called on timer ticks."""
        if self._ip_built and self._ip_elapsed_lbl:
            _set_row_val(self._ip_elapsed_lbl, elapsed)

    # ---- Progress bar ----------------------------------------------------
    #
    # The stage marker emitted by the worker is the only authoritative
    # progress signal. The bar jumps straight to that stage's fixed
    # milestone — no interpolation, no estimation of in-stage work.
    #
    # Until the first genuine stage_changed signal for the current document
    # has been observed, the bar stays indeterminate (busy/marquee) instead
    # of showing a stalled, potentially misleading 0% — the `claude` CLI
    # subprocess does not guarantee that stage markers are delivered in real
    # time (its stdout may arrive in a single late burst), so a determinate
    # value can only be trusted once a real signal has actually arrived.

    def _apply_ingest_progress_bar(self) -> None:
        if self._ip_progress_bar:
            if self._ip_indeterminate:
                self._ip_progress_bar.setRange(0, 0)
            else:
                self._ip_progress_bar.setRange(0, 100)
                self._ip_progress_bar.setValue(self._ip_progress_value)
        if self._ip_pct_lbl:
            self._ip_pct_lbl.setText(
                "Working…" if self._ip_indeterminate else f"{self._ip_progress_value}%"
            )

    def show_ingest_result(self, result: dict) -> None:
        if not self._ip_built:
            self._clear()
            p = _Panel("Runtime")
            res = result.get("result", "SUCCESS")
            p.add_row("Status",   res,                       _status_color(res))
            p.add_row("Duration", result.get("duration", "—"))
            p.add_row("Tokens",   result.get("tokens",   "—"))
            self._add_panel(p)
            return

        # The operation has finished — always settle back to determinate
        # 100%, regardless of whether the bar was still indeterminate.
        self._ip_progress_value = 100
        self._ip_indeterminate  = False

        res = result.get("result", "SUCCESS")
        if self._ip_status_lbl:
            _set_row_val(self._ip_status_lbl, res, _status_color(res))
        if self._ip_elapsed_lbl:
            _set_row_val(self._ip_elapsed_lbl, result.get("duration", "—"))
        self._apply_ingest_progress_bar()

    # ------------------------------------------------------------------
    # Maintenance runtime
    # ------------------------------------------------------------------

    def show_maintenance_idle(self) -> None:
        self._clear()
        p = _Panel("Maintenance")
        p.add_row("Status", "Ready")
        p.add_row("Last Scan", "—")
        p.add_row("Duration", "—")
        self._add_panel(p)

    def _build_maintenance_panels(self, status: str, last_scan: str, duration: str) -> None:
        """
        Build the maintenance panel exactly once per run.
        Stores label references for in-place updates throughout the run.
        Called by show_maintenance_running()/show_maintenance_result() on first invocation.
        """
        self._clear()  # invalidates refs via _reset_maintenance_persistent()

        p = _Panel("Maintenance")
        self._mp_status_lbl   = p.add_row("Status",    status, _status_color(status))
        self._mp_scan_lbl     = p.add_row("Last Scan", last_scan)
        self._mp_duration_lbl = p.add_row("Duration",  duration)
        self._add_panel(p)

        self._mp_built = True

    def show_maintenance_running(self, last_scan: str, duration: str) -> None:
        """
        Update the maintenance inspector while the run is in progress.
        Builds the panel on the first call; subsequent calls update labels only.
        """
        if not self._mp_built:
            self._build_maintenance_panels("Running", last_scan, duration)
            return

        _set_row_val(self._mp_status_lbl, "Running", _status_color("Running"))
        _set_row_val(self._mp_scan_lbl, last_scan)
        _set_row_val(self._mp_duration_lbl, duration)

    def show_maintenance_result(self, result: dict) -> None:
        """
        Finalise the maintenance inspector without recreating any widgets
        when the panel is already present from show_maintenance_running().
        """
        status = result.get("overall_status", "—")
        last_scan = result.get("last_scan", "—")
        duration = result.get("duration", "—")

        if not self._mp_built:
            self._build_maintenance_panels(status, last_scan, duration)
            return

        _set_row_val(self._mp_status_lbl, status, _status_color(status))
        _set_row_val(self._mp_scan_lbl, last_scan)
        _set_row_val(self._mp_duration_lbl, duration)

