"""
Color palette and application-wide QSS stylesheet.
Derived from the HTML/CSS mockups in mockup/.
"""

COLORS = {
    'bg_app':           '#eef2f7',
    'bg_header':        '#1f2937',
    'bg_sidebar':       '#f8fafc',
    'bg_workspace':     '#f4f7fb',
    'bg_inspector':     '#fafafa',
    'bg_card':          '#ffffff',
    'bg_card_title':    '#f8fafc',
    'bg_footer':        '#f1f5f9',
    'bg_active_nav':    '#2563eb',
    'bg_hover_nav':     '#e2e8f0',
    'bg_selected_row':  '#dbeafe',
    'bg_success':       '#ecfdf5',
    'bg_warning_row':   '#fefce8',
    'bg_recommend':     '#eff6ff',

    'border_main':      '#e5e7eb',
    'border_divider':   '#dbe4ee',
    'border_input':     '#d1d5db',

    'text_white':       '#ffffff',
    'text_main':        '#1e293b',
    'text_secondary':   '#475569',
    'text_muted':       '#64748b',

    'accent_blue':      '#2563eb',
    'accent_blue_dark': '#1d4ed8',
    'accent_green':     '#16a34a',
    'accent_yellow':    '#ca8a04',
    'accent_amber':     '#f59e0b',

    'status_success':   '#15803d',
    'status_warning':   '#a16207',
    'status_critical':  '#dc2626',
}

APP_STYLESHEET = """
/* ==================== Base ==================== */

QWidget {
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 13px;
    color: #1e293b;
}

QMainWindow {
    background-color: #eef2f7;
}

/* ==================== Scrollbars ==================== */

QScrollBar:vertical {
    width: 9px;
    background: transparent;
    margin: 0;
}

QScrollBar::handle:vertical {
    background: #cbd5e1;
    border-radius: 4px;
    min-height: 20px;
}

QScrollBar::handle:vertical:hover {
    background: #94a3b8;
}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical,
QScrollBar::sub-page:vertical {
    background: transparent;
    height: 0;
}

QScrollBar:horizontal {
    height: 9px;
    background: transparent;
}

QScrollBar::handle:horizontal {
    background: #cbd5e1;
    border-radius: 4px;
    min-width: 20px;
}

QScrollBar::handle:horizontal:hover {
    background: #94a3b8;
}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal,
QScrollBar::add-page:horizontal,
QScrollBar::sub-page:horizontal {
    background: transparent;
    width: 0;
}

/* ==================== Tables ==================== */

QTableWidget {
    background-color: white;
    border: none;
    outline: none;
    gridline-color: #eef2f7;
    selection-background-color: #dbeafe;
    selection-color: #1e293b;
}

QTableWidget::item {
    padding: 10px 16px;
    border-bottom: 1px solid #eef2f7;
    color: #1e293b;
}

QTableWidget::item:selected {
    background-color: #dbeafe;
    color: #1e293b;
}

QTableWidget::item:hover:!selected {
    background-color: #f8fafc;
}

QHeaderView::section {
    background-color: #f8fafc;
    border: none;
    border-bottom: 1px solid #e5e7eb;
    padding: 10px 16px;
    font-size: 12px;
    color: #64748b;
    font-weight: bold;
}

QHeaderView {
    border: none;
}

/* ==================== Inputs ==================== */

QLineEdit {
    border: 1px solid #d1d5db;
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 13px;
    background: white;
    color: #1e293b;
}

QLineEdit:focus {
    border-color: #2563eb;
}

QTextEdit {
    border: 1px solid #d1d5db;
    border-radius: 12px;
    padding: 12px 14px;
    font-size: 13px;
    background: white;
    color: #1e293b;
}

QTextEdit:focus {
    border-color: #2563eb;
}

QTextBrowser {
    border: none;
    background: white;
    font-size: 13px;
    color: #1e293b;
}

QPlainTextEdit {
    border: none;
    background: #1e293b;
    color: #94a3b8;
    font-family: Consolas, "Courier New", monospace;
    font-size: 12px;
}

/* ==================== Buttons ==================== */

QPushButton {
    border: none;
    border-radius: 10px;
    padding: 9px 14px;
    font-size: 13px;
    background-color: #e2e8f0;
    color: #1e293b;
}

QPushButton:hover {
    background-color: #cbd5e1;
}

QPushButton:pressed {
    background-color: #94a3b8;
}

QPushButton:disabled {
    background-color: #f1f5f9;
    color: #94a3b8;
}

QPushButton[primary="true"] {
    background-color: #2563eb;
    color: white;
    font-weight: bold;
}

QPushButton[primary="true"]:hover {
    background-color: #1d4ed8;
}

QPushButton[primary="true"]:disabled {
    background-color: #93c5fd;
}

QPushButton[danger="true"] {
    background-color: #fee2e2;
    color: #dc2626;
}

QPushButton[danger="true"]:hover {
    background-color: #fecaca;
}

/* ==================== Radio Buttons ==================== */

QRadioButton {
    font-size: 13px;
    color: #1e293b;
    spacing: 10px;
}

/* ==================== Progress Bar ==================== */

QProgressBar {
    border: none;
    border-radius: 5px;
    background-color: #dbe4ee;
    height: 10px;
    text-align: center;
    color: transparent;
}

QProgressBar::chunk {
    background-color: #2563eb;
    border-radius: 5px;
}

/* ==================== Frame ==================== */

QFrame[role="card"] {
    background: white;
    border: 1px solid #e5e7eb;
    border-radius: 12px;
}

QFrame[role="card-title"] {
    background: #f8fafc;
    border-bottom: 1px solid #e5e7eb;
    border-top-left-radius: 12px;
    border-top-right-radius: 12px;
}
"""
