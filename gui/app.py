"""Application factory — creates QApplication and MainWindow."""

import sys
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont

from .startup_flow import run_startup
from .styles.theme import APP_STYLESHEET
from .main_window import MainWindow


def create_app(project_root: Path) -> tuple[QApplication, MainWindow | None]:
    """Build the QApplication and, if startup validation passes, MainWindow.

    `project_root` is the default workspace offered when no workspace
    has been persisted yet (see gui/app_config.py and gui/startup_flow.py
    for the full first-launch vs. normal-launch decision).

    Returns (app, None) when startup validation fails — the caller must
    not show a window in that case; a dialog explaining why has already
    been presented to the user.
    """
    app = QApplication.instance() or QApplication(sys.argv)

    # Default font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    # Global stylesheet
    app.setStyleSheet(APP_STYLESHEET)

    workspace_manager = run_startup(project_root)
    if workspace_manager is None:
        return app, None

    window = MainWindow(workspace_manager)
    return app, window
