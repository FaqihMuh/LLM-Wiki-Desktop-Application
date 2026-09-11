"""Reusable data table widget with pagination and row selection."""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QHeaderView, QPushButton, QLabel, QAbstractItemView
)
from PySide6.QtCore import Signal, Qt

PAGE_SIZE = 15


class DataTable(QWidget):
    """
    Table widget with filterable rows and Previous/Next pagination.
    Emits row_selected(row_data: dict) when the user clicks a row.
    """

    row_selected = Signal(dict)

    def __init__(self, columns: list[str], parent: QWidget | None = None):
        super().__init__(parent)
        self._columns = columns
        self._all_rows: list[dict] = []
        self._filtered_rows: list[dict] = []
        self._page = 0

        self.setMinimumHeight(240)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Table
        self._table = QTableWidget(0, len(columns))
        self._table.setMinimumHeight(160)
        self._table.setHorizontalHeaderLabels(columns)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(False)
        self._table.verticalHeader().setVisible(False)
        self._table.horizontalHeader().setStretchLastSection(True)
        self._table.setShowGrid(False)
        self._table.setStyleSheet("""
            QTableWidget {
                background: white;
                border: none;
                outline: none;
                selection-background-color: #dbeafe;
                selection-color: #1e293b;
            }
            QTableWidget::item {
                padding: 10px 16px;
                border-bottom: 1px solid #eef2f7;
                color: #1e293b;
                font-size: 13px;
            }
            QTableWidget::item:selected {
                background: #dbeafe;
                color: #1e293b;
            }
            QTableWidget::item:hover:!selected {
                background: #f8fafc;
            }
            QHeaderView::section {
                background: #f8fafc;
                border: none;
                border-bottom: 1px solid #e5e7eb;
                padding: 10px 16px;
                font-size: 12px;
                color: #64748b;
                font-weight: bold;
            }
        """)
        # Stretch columns evenly except last
        header = self._table.horizontalHeader()
        for i in range(len(columns) - 1):
            header.setSectionResizeMode(i, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(len(columns) - 1, QHeaderView.ResizeMode.Stretch)

        self._table.itemSelectionChanged.connect(self._on_selection_changed)
        layout.addWidget(self._table)

        # Pagination bar
        pg_widget = QWidget()
        pg_widget.setStyleSheet(
            "background: white; border-top: 1px solid #e5e7eb;"
        )
        pg_layout = QHBoxLayout(pg_widget)
        pg_layout.setContentsMargins(18, 10, 18, 10)

        self._prev_btn = QPushButton("◀ Previous")
        self._prev_btn.setStyleSheet("""
            QPushButton {
                background: #e2e8f0;
                border: none;
                border-radius: 8px;
                padding: 7px 12px;
                font-size: 12px;
                color: #1e293b;
            }
            QPushButton:hover { background: #cbd5e1; }
            QPushButton:disabled { background: #f1f5f9; color: #94a3b8; }
        """)
        self._prev_btn.clicked.connect(self._prev_page)

        self._page_label = QLabel("Page 1 of 1")
        self._page_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_label.setStyleSheet(
            "color: #64748b; font-size: 12px; background: transparent;"
        )

        self._next_btn = QPushButton("Next ▶")
        self._next_btn.setStyleSheet(self._prev_btn.styleSheet())
        self._next_btn.clicked.connect(self._next_page)

        pg_layout.addWidget(self._prev_btn)
        pg_layout.addStretch()
        pg_layout.addWidget(self._page_label)
        pg_layout.addStretch()
        pg_layout.addWidget(self._next_btn)

        layout.addWidget(pg_widget)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_data(self, rows: list[dict]) -> None:
        self._all_rows = rows
        self._page = 0
        self._apply_filter("")
        self._update_display()

    def filter(self, text: str) -> None:
        self._page = 0
        self._apply_filter(text)
        self._update_display()

    def get_data(self) -> list[dict]:
        """Return the full, unfiltered row list currently held by the table.

        Lets a page reuse the rows already loaded via set_data() (e.g.
        EntitiesPage feeding its Knowledge Graph) instead of reloading
        the same data from disk a second time. Pagination/search only
        affect what's displayed, never self._all_rows, so this always
        reflects the complete dataset regardless of current filter/page.
        """
        return list(self._all_rows)

    def select_row(self, index: int) -> None:
        if 0 <= index < self._table.rowCount():
            self._table.selectRow(index)

    def select_row_by_value(self, key: str, value: str) -> bool:
        """Navigate to and silently select the first row where row_data[key] == value.

        Blocks QTableWidget signals so that no recursive callbacks fire.
        Returns True if the row was found and selected.
        """
        for i, row in enumerate(self._filtered_rows):
            if str(row.get(key, "")) == value:
                target_page = i // PAGE_SIZE
                if target_page != self._page:
                    self._page = target_page
                    self._update_display()
                local_idx = i % PAGE_SIZE
                if 0 <= local_idx < self._table.rowCount():
                    self._table.blockSignals(True)
                    self._table.selectRow(local_idx)
                    self._table.blockSignals(False)
                return True
        return False

    # ------------------------------------------------------------------

    def _apply_filter(self, text: str) -> None:
        q = text.lower().strip()
        if not q:
            self._filtered_rows = list(self._all_rows)
        else:
            self._filtered_rows = [
                r for r in self._all_rows
                if any(q in str(v).lower() for v in r.values())
            ]

    def _update_display(self) -> None:
        start = self._page * PAGE_SIZE
        end = start + PAGE_SIZE
        page_rows = self._filtered_rows[start:end]

        self._table.setRowCount(len(page_rows))
        for row_idx, row_data in enumerate(page_rows):
            for col_idx, col_name in enumerate(self._columns):
                value = str(row_data.get(col_name, ""))
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, row_data)
                self._table.setItem(row_idx, col_idx, item)

        total_pages = max(1, (len(self._filtered_rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        self._page_label.setText(f"Page {self._page + 1} of {total_pages}")
        self._prev_btn.setEnabled(self._page > 0)
        self._next_btn.setEnabled(self._page < total_pages - 1)

    def _prev_page(self) -> None:
        if self._page > 0:
            self._page -= 1
            self._update_display()

    def _next_page(self) -> None:
        total_pages = max(1, (len(self._filtered_rows) + PAGE_SIZE - 1) // PAGE_SIZE)
        if self._page < total_pages - 1:
            self._page += 1
            self._update_display()

    def _on_selection_changed(self) -> None:
        rows = self._table.selectedItems()
        if not rows:
            return
        row_data = rows[0].data(Qt.ItemDataRole.UserRole)
        if row_data:
            self.row_selected.emit(row_data)
